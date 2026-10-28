"""Pantry-to-Plate in the browser: the same agent as `pantry.py ask`, behind a web page.

    python pantry.py web            opens http://127.0.0.1:8000

The pipeline does not change: one PantryAgent (Week 7 loop + Week 9 MCP host) answers, the
MCP servers in pantry_mcp.json do the work, and every question is logged under one trace id
with the PII line applied (pantry_trace.py). The page is a chat:
  - follow-up questions: the page sends the conversation's earlier turns with each question
  - live progress: each MCP tool call shows up as it happens, an allergen verdict as soon as
    check_allergens returns, and the answer text as the model writes it
  - regenerate: the same question again at a higher temperature; the page keeps every version
  - the trace: every span, with the server's own spans under the same trace id
  - chats are kept in the browser (localStorage); the server keeps only the redacted log,
    which the page can also read back (health details removed)

It listens on 127.0.0.1 only: it spends your model key, so it is not for the network.
"""
import asyncio
import concurrent.futures
import json
import re
import sys
import threading
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.routing import Route

import pantry_corpus as pc
from ask import DEFAULT_MODEL, LLM
from pantry_agent import CONFIG, PantryAgent, citations, resolve_citation
from pantry_trace import CLIENT_LOG, SERVER_LOG, load, merged_trace, redact

ROOT = Path(__file__).parent
PAGE = ROOT / "web" / "index.html"
MAX_QUESTION = 1000
MAX_ANSWER = 4000  # per earlier turn sent back as history
MAX_TURNS = 6  # earlier turns the model sees: each one is re-sent on every lap of the loop
REGEN_TEMPERATURE = 0.7
HISTORY = 30
TRACE_ID = re.compile(r"^[0-9a-f]{6,16}$")
CONVERSATION_ID = re.compile(r"^[a-z0-9-]{1,40}$")
# what the page needs to draw an allergen verdict before the answer is finished
ALLERGEN_KEYS = ("recipe_id", "version", "cite_as", "status", "avoid", "verdict", "contains_avoided",
                 "may_contain_avoided", "sources_of_avoided", "as_substituted", "current_version",
                 "serving_suggestions_to_leave_out")
BUSY = ("Another question is still running. One at a time: the free tier allows "
        "15 model calls a minute.")


class AgentService:
    """The agent and its MCP sessions live on their own thread and event loop. ask.call_llm
    blocks (it sleeps for free-tier pacing), so on the web server's loop it would freeze
    the page. The MCP stdio clients must also be opened and closed in one task, so _hold
    keeps them open until stop()."""

    def __init__(self):
        # Proactor explicitly: on Windows only it can start the MCP servers as subprocesses
        self.loop = asyncio.ProactorEventLoop() if sys.platform == "win32" else asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True, name="pantry-agent").start()
        self.agent, self.busy = None, threading.Lock()
        self.ready = concurrent.futures.Future()
        self._stop = asyncio.Event()
        self.holder = asyncio.run_coroutine_threadsafe(self._hold(), self.loop)

    async def _hold(self):
        try:
            pc._collection()  # builds the index on the very first run
            async with PantryAgent() as agent:
                self.agent = agent
                self.ready.set_result(agent)
                await self._stop.wait()
        except Exception as e:
            if not self.ready.done():
                self.ready.set_exception(e)
            raise

    def ask(self, question, user, on_event, on_token, history, temperature, conversation_id):
        return asyncio.run_coroutine_threadsafe(
            self.agent.ask(question, user=user, on_event=on_event, on_token=on_token, history=history,
                           temperature=temperature, conversation_id=conversation_id), self.loop)

    def stop(self):
        self.loop.call_soon_threadsafe(self._stop.set)


SERVICE = None


def _span_view(s):
    """A span without the raw tool payload (search results can be long)."""
    keep = ("span_id", "kind", "name", "lap", "latency_ms", "throttle_wait_ms", "first_token_ms",
            "prompt_tokens", "completion_tokens", "cost_usd", "server", "tool", "args", "is_error")
    out = {k: s[k] for k in keep if k in s}
    if s.get("error"):
        out["error"] = s["error"][:300]
    return out


def view(rec, from_log=False):
    """What the page needs from one record. Sources are resolved here; a cited id that is
    not in this list is not in the library, and the page marks it broken."""
    sources = []
    for cid in citations(rec.get("answer"), strict=False):
        found = resolve_citation(cid)
        if found:
            m, where = found
            sources.append({"id": cid, "title": m["title"], "version": m["version"],
                            "status": m["status"], "where": where})
    servers = rec.get("server_spans")
    if servers is None:
        servers = [s for s in load(SERVER_LOG) if s["trace_id"] == rec["trace_id"]]
    return {"trace_id": rec["trace_id"], "ts": rec["ts"], "user": rec["user"], "model": rec["model"],
            "prompt_version": rec["prompt_version"], "temperature": rec.get("temperature", 0),
            "conversation_id": rec.get("conversation_id"), "turn": rec.get("turn", 1),
            "question": rec["question"],
            "question_logged": redact(rec["question"]), "answer": rec.get("answer"),
            "sources": sources, "allergen_checks": rec.get("allergen_checks", []),
            "constraints_detected": rec.get("constraints_detected", []),
            "spans": [_span_view(s) for s in rec["spans"]],
            "server_spans": [{"parent_span_id": s.get("parent_span_id"), "span": s["span"],
                              "latency_ms": s.get("latency_ms", 0), "is_error": s.get("is_error", False)}
                             for s in servers],
            "laps": rec["laps"], "tool_calls": sum(1 for s in rec["spans"] if s["kind"] == "tool"),
            "tokens_total": rec["tokens_total"], "cost_usd_total": rec["cost_usd_total"],
            "latency_ms_total": rec["latency_ms_total"], "stop_reason": rec["stop_reason"],
            "from_log": from_log}


def _line(obj):
    return json.dumps(obj, ensure_ascii=False) + "\n"


def _history(raw):
    """The earlier turns the page sends back, [{"question", "answer"}]: the last MAX_TURNS."""
    turns = []
    for t in raw if isinstance(raw, list) else []:
        if isinstance(t, dict) and str(t.get("question") or "").strip() and str(t.get("answer") or "").strip():
            turns.append({"question": str(t["question"])[:MAX_QUESTION], "answer": str(t["answer"])[:MAX_ANSWER]})
    return turns[-MAX_TURNS:]


async def page(_):
    return FileResponse(PAGE, headers={"Cache-Control": "no-store"})


async def api_info(_):
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    release = cfg["mcpServers"].get("pantry", {}).get("env", {}).get("PANTRY_RELEASE", "r1")
    return JSONResponse({"model": DEFAULT_MODEL, "release": release, "has_key": LLM is not None,
                         "tools": list(SERVICE.agent.catalogue), "servers": len(SERVICE.agent.sessions),
                         "regen_temperature": REGEN_TEMPERATURE, "max_turns": MAX_TURNS})


async def api_history(_):
    rows = load(CLIENT_LOG)[-HISTORY:][::-1]
    return JSONResponse([{"trace_id": r["trace_id"], "ts": r["ts"], "question": r["question"],
                          "laps": r["laps"], "cost_usd_total": r["cost_usd_total"],
                          "stop_reason": r["stop_reason"],
                          "verdicts": [c["verdict"] for c in r.get("allergen_checks", [])],
                          "not_run": bool(r.get("constraints_detected")) and not r.get("allergen_checks")}
                         for r in rows])


async def api_trace(request):
    trace_id = request.path_params["trace_id"].lower()
    if not TRACE_ID.match(trace_id):
        return JSONResponse({"error": "A trace id is 6-16 hex characters."}, status_code=400)
    rec = merged_trace(trace_id)
    if rec is None:
        return JSONResponse({"error": f"No trace {trace_id} in {CLIENT_LOG.name}."}, status_code=404)
    return JSONResponse(view(rec, from_log=True))


async def api_ask(request):
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"error": "Send JSON: {\"question\": \"...\"}"}, status_code=400)
    question = str(body.get("question") or "").strip()
    user = str(body.get("user") or "web-user")[:64]
    history = _history(body.get("history"))
    conversation_id = str(body.get("conversation_id") or "")
    conversation_id = conversation_id if CONVERSATION_ID.match(conversation_id) else None
    temperature = REGEN_TEMPERATURE if body.get("regenerate") else 0
    if not question:
        return JSONResponse({"error": "Type a question first."}, status_code=400)
    if len(question) > MAX_QUESTION:
        return JSONResponse({"error": f"Keep it under {MAX_QUESTION} characters."}, status_code=400)
    if LLM is None:
        return JSONResponse({"error": "No model key. Create a .env file in the week3-rag folder with "
                                      "GEMINI_API_KEY=your-key, then restart: python pantry.py web"},
                            status_code=400)
    if not SERVICE.busy.acquire(blocking=False):
        return JSONResponse({"error": BUSY}, status_code=409)

    web_loop, events = asyncio.get_running_loop(), asyncio.Queue()

    def on_event(kind, name, args, is_error, text):  # called on the agent thread
        ev = {"type": kind, "name": name, "args": args, "is_error": is_error}
        if is_error:
            ev["error"] = (text or "")[:300]
        elif name.endswith("__check_allergens"):
            try:
                res = json.loads(text)
            except (json.JSONDecodeError, TypeError):
                res = None
            if isinstance(res, dict) and "verdict" in res:
                ev["result"] = {k: res[k] for k in ALLERGEN_KEYS if k in res}
        web_loop.call_soon_threadsafe(events.put_nowait, ev)

    def on_token(lap, text):  # called on the agent thread; text None = drop this lap's text
        web_loop.call_soon_threadsafe(events.put_nowait, {"type": "token", "lap": lap, "text": text})

    job = SERVICE.ask(question, user, on_event, on_token, history, temperature, conversation_id)
    # released when the agent finishes, even if the page was closed mid-question
    job.add_done_callback(lambda _: SERVICE.busy.release())
    done = asyncio.wrap_future(job)

    async def stream():
        yield _line({"type": "start"})
        while True:
            nxt = asyncio.ensure_future(events.get())
            await asyncio.wait({nxt, done}, return_when=asyncio.FIRST_COMPLETED)
            if nxt.done():
                yield _line(nxt.result())
                continue
            nxt.cancel()
            break
        while not events.empty():
            yield _line(events.get_nowait())
        try:
            yield _line({"type": "done", "record": view(done.result())})
        except Exception as e:
            yield _line({"type": "error", "message": str(e)[:500]})

    return StreamingResponse(stream(), media_type="application/x-ndjson")


@asynccontextmanager
async def lifespan(app):
    global SERVICE
    print("starting the MCP servers (first run also builds the search index) ...", flush=True)
    SERVICE = AgentService()
    await asyncio.wrap_future(SERVICE.ready)
    print(f"ready: {len(SERVICE.agent.catalogue)} tools from {len(SERVICE.agent.sessions)} servers")
    print(f"open {app.state.url}   (Ctrl+C to stop)", flush=True)
    if LLM is None:
        print("no model key: recent questions work, asking needs GEMINI_API_KEY in .env")
    if app.state.open_browser:
        webbrowser.open(app.state.url)
    yield
    SERVICE.stop()
    try:
        await asyncio.wait_for(asyncio.wrap_future(SERVICE.holder), timeout=10)
    except Exception:
        pass  # shutting down anyway; the servers are child processes and exit with us


app = Starlette(lifespan=lifespan, routes=[
    Route("/", page),
    Route("/api/info", api_info),
    Route("/api/history", api_history),
    Route("/api/trace/{trace_id}", api_trace),
    Route("/api/ask", api_ask, methods=["POST"]),
])


def serve(port=8000, open_browser=True):
    app.state.url, app.state.open_browser = f"http://127.0.0.1:{port}", open_browser
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
