"""Capstone: the integrated agent. Week 7 loop + Week 9 MCP discovery + Week 11 tracing.

    async with PantryAgent() as agent:
        rec = await agent.ask("My son is allergic to nuts - can he have the nankhatai?")

One question = one trace id. Spans in the record:
    llm/lap-N             every model call: latency, free-tier throttle wait, tokens, cost
    tool/<server>__<tool> every MCP tools/call, host side: latency, arguments, error flag
    mcp.server/<tool>     the server's own span under the same trace id (sent in _meta),
                          attached when the trace is read back (pantry_trace.merged_trace)

The host is the only place a model is called. Tools come from tools/list on every
server in pantry_mcp.json at startup (Week 9): adding a server is a config change.

Two parts of every answer are rendered by CODE from tool results, not written by the
model: the source list (clickable, with version) and the allergen-check block. The
model writes the prose. The block shows what the declaration fields say whatever the
prose claims, and shows "NOT RUN" when an allergy question was never checked.

Conversations (the web page): pass the earlier turns as `history`. Each turn is still one
trace id, and an allergy named in an earlier turn still counts: constraints_detected covers
the whole conversation. `on_token` streams the answer text as the model writes it; without
it, every call is the same non-streamed request the eval suite measured.
"""
import json
import re
import time
import uuid
from contextlib import AsyncExitStack
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from openai.types.chat import ChatCompletionMessage

from ask import DEFAULT_MODEL, call_llm
from w9_agent import PRICE_IN, PRICE_OUT, connect_all, result_text, to_llm_tools

import pantry_corpus as pc
from pantry_trace import CLIENT_LOG, append, pseudonym, redact

ROOT = Path(__file__).parent
CONFIG = ROOT / "pantry_mcp.json"
PROMPT_VERSION = "pv1"
REFUSAL = "I cannot find this in the recipe library."

MAX_ITERS = 10
MAX_TOKENS = 60000
MAX_COST_USD = 0.02
MAX_WALL_SEC = 300

SYSTEM = f"""You are Pantry-to-Plate, the cooking assistant for a recipe publisher. You answer
ONLY from the publisher's recipe library, which you reach through your tools.

How to work:
- Find recipes with search_recipes. Every chunk id names its recipe AND its version,
  e.g. nankhatai-07@reformulated-2025::structure::1. Cite every fact with the chunk id
  in square brackets, one id per bracket.
- Some recipes exist in two versions. Use the CURRENT version unless the user asks about
  the old one. If you mention a superseded version, say it is superseded.
- Allergies: whenever the user mentions an allergy, intolerance or a free-from need, call
  check_allergens for every recipe you suggest, with the allergens to avoid, and report its
  verdict in plain words. Its declaration fields are the only source of truth: never decide
  allergens from recipe text, which can be out of date. "May contain" is a warning, never
  "safe". If you suggest a substitution, check the recipe again as substituted.
- Scaling: use scale_recipe. Quantities scale; cooking and baking times, oven temperatures
  and safe internal temperatures never do. Say so.
- Meat, poultry, fish, eggs, leftovers and cooked rice: call get_safe_temperature and give
  the number.
- If the library does not cover the question, reply exactly: "{REFUSAL}"
- Never guess about safety. If you cannot confirm something is safe from the declarations
  or the food-safety chart, say you cannot confirm it.
Be brief and practical."""

# Throttle accounting (Week 11): ask.call_llm sleeps for free-tier pacing and 429 backoff.
_SLEPT = [0.0]
_real_sleep = time.sleep


def _counting_sleep(seconds):
    _SLEPT[0] += max(0.0, seconds)
    _real_sleep(seconds)


time.sleep = _counting_sleep

CITE_GROUP = re.compile(r"\[([^\[\]]+)\]")
# A chunk (recipe@version::structure::n) or a whole version's CMS record (recipe@version),
# which is what an allergen verdict cites: the declaration is a field, not a chunk (seam S6).
CITE_ID = re.compile(r"^[a-z0-9-]+@[a-z0-9-]+(?:::[a-z]+::\d+)?$")
CITE_LIKE = re.compile(r"^[a-z0-9-]+(?:@[a-z0-9-]+)?(?:::[a-z]+::\d+)?$")
ALLERGY_CUE = re.compile(r"allerg|intoleran|\b[a-z]+[- ]free\b|free from|coeliac|celiac|vegan|"
                         r"can'?t (?:eat|have)|cannot (?:eat|have)|\bavoid", re.I)


def citations(text, strict=True):
    """Ids cited in square brackets; a bracket may hold several, comma-separated.
    strict=False also returns id-shaped tokens WITHOUT a version (a broken citation)."""
    pattern = CITE_ID if strict else CITE_LIKE
    out = []
    for group in CITE_GROUP.findall(text or ""):
        for part in group.split(","):
            p = part.strip().strip("`")
            if pattern.match(p) and ("::" in p or "@" in p) and p not in out:
                out.append(p)
    return out


def resolve_citation(cid):
    """(meta, location) for a citation, or None if it names nothing in the library."""
    if cid in pc.CHUNKS:
        m = pc.chunk_meta(cid)
        return m, m["source"]
    if "::" not in cid and "@" in cid:
        rid, ver = cid.split("@", 1)
        rec = pc.RECORDS.get((rid, ver))
        if rec:
            return ({"recipe_id": rid, "version": ver, "status": rec["status"], "title": rec["title"]},
                    f"{rec['file']}:1")
    return None


def detected_constraints(question):
    """Allergen classes the user named, if the question carries an allergy cue at all."""
    if not ALLERGY_CUE.search(question):
        return []
    q = question.lower()
    return sorted({cls for word, cls in pc.SYNONYMS.items() if re.search(rf"\b{re.escape(word)}\b", q)})


def _parse(text):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


def _model_call(messages, tools, temperature, lap, on_token):
    """One lap's model call: (message, usage, ms to the first streamed text or None)."""
    kwargs = dict(model=DEFAULT_MODEL, temperature=temperature, messages=messages, tools=tools)
    if on_token is None:
        resp = call_llm(**kwargs)
        return resp.choices[0].message, resp.usage, None
    t0 = time.perf_counter()
    stream = call_llm(stream=True, stream_options={"include_usage": True}, **kwargs)
    text, calls, extra, usage, first = [], {}, {}, None, None
    try:
        for chunk in stream:
            usage = chunk.usage or usage
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                if first is None:
                    first = round((time.perf_counter() - t0) * 1000, 1)
                text.append(delta.content)
                on_token(lap, delta.content)
            for i, tc in enumerate(delta.tool_calls or []):
                part = tc.model_dump(exclude_none=True)  # keeps Gemini's thought_signature
                key = part.pop("index", i)
                if key in calls:  # OpenAI streams arguments in pieces; Gemini sends each call whole
                    calls[key]["function"]["arguments"] += part.get("function", {}).get("arguments", "")
                else:
                    calls[key] = part
            extra.update(delta.model_extra or {})
    except Exception:  # broke mid-stream: it can't be resumed, so drop its text and run the lap whole
        on_token(lap, None)
        resp = call_llm(**kwargs)
        if resp.choices[0].message.content:
            on_token(lap, resp.choices[0].message.content)
        return resp.choices[0].message, resp.usage, None
    msg = {"role": "assistant", **extra}
    if text:
        msg["content"] = "".join(text)
    if calls:
        msg["tool_calls"] = [calls[k] for k in sorted(calls)]
    return (ChatCompletionMessage.model_validate(msg),
            usage or SimpleNamespace(prompt_tokens=0, completion_tokens=0), first)


def render(rec, markdown=False):
    """Answer + sources + allergen block, the way the user sees it."""
    lines = [rec["answer"] or f"(no answer: {rec['stop_reason']})", ""]
    cited = citations(rec["answer"])
    if cited:
        lines.append("Sources:")
        for i, cid in enumerate(cited, 1):
            found = resolve_citation(cid)
            if found:
                m, loc = found
                path, line = loc.rsplit(":", 1)
                where = f"[{cid}]({path}#L{line})" if markdown else f"{cid}  ->  {loc}"
                lines.append(f"  [{i}] {where}  ({m['title']}, version {m['version']}, {m['status']})")
            else:
                lines.append(f"  [{i}] {cid}  ->  NOT IN THE LIBRARY (broken citation)")
    checks = rec["allergen_checks"]
    if checks or rec["constraints_detected"]:
        lines += ["", "Allergen check (from the CMS declaration fields, exact match; not the page text):"]
        for c in checks:
            extra = []
            if c.get("contains_avoided"):
                extra.append("declares " + ", ".join(
                    f"{a} ({'; '.join(c.get('sources_of_avoided', {}).get(a, []))})".replace(" ()", "")
                    for a in c["contains_avoided"]))
            if c.get("may_contain_avoided"):
                extra.append("may contain " + ", ".join(c["may_contain_avoided"]))
            if c.get("as_substituted"):
                extra.append("as substituted: " + ", ".join(f"{s['from']} -> {s['to']}"
                                                            for s in c["as_substituted"]))
            if c.get("current_version"):  # r2 guard: a superseded version is history only
                cv = c["current_version"]
                extra.append(f"history only, not offered; today's recipe {cv['cite_as']}: {cv['verdict']}")
            if c.get("serving_suggestions_to_leave_out"):
                extra.append("leave out serving suggestions: " + ", ".join(
                    i for items in c["serving_suggestions_to_leave_out"].values() for i in items))
            lines.append(f"  - {c['cite_as']} ({c['status']}), avoiding {', '.join(c['avoid'])}: "
                         f"{c['verdict']}" + (f" - {'; '.join(extra)}" if extra else ""))
        if rec["constraints_detected"] and not checks and rec.get("turn", 1) > 1:
            lines.append(f"  - NOT RUN. This conversation names {', '.join(rec['constraints_detected'])} but "
                         f"no recipe was checked in this answer. Do not rely on it for an allergy.")
        elif rec["constraints_detected"] and not checks:
            lines.append(f"  - NOT RUN. The question names {', '.join(rec['constraints_detected'])} but no "
                         f"recipe was checked. Do not rely on this answer for an allergy.")
    return "\n".join(lines)


class PantryAgent:
    """Holds the MCP sessions open across questions, like a running service."""

    def __init__(self, config=CONFIG, prompt_version=PROMPT_VERSION, system=SYSTEM):
        self.config, self.prompt_version, self.system = Path(config).resolve(), prompt_version, system

    async def __aenter__(self):
        self._stack = AsyncExitStack()
        await self._stack.__aenter__()
        self.sessions, self.catalogue = await connect_all(self.config, self._stack)
        self.tools = to_llm_tools(self.catalogue)
        return self

    async def __aexit__(self, *exc):
        await self._stack.__aexit__(*exc)

    async def ask(self, question, user="anonymous", log=True, on_event=None, history=None, temperature=0,
                  on_token=None, conversation_id=None):
        """history: this conversation's earlier turns, [{"question", "answer"}], oldest first.
        on_token(lap, text): the answer text as it streams; text None means drop this lap's
        text so far (the stream broke and the lap is re-run)."""
        trace_id, t_req = uuid.uuid4().hex[:16], time.perf_counter()
        spans, usage, n_span = [], {"in": 0, "out": 0}, [0]
        history = history or []
        messages = [{"role": "system", "content": self.system}]
        for turn in history:
            messages += [{"role": "user", "content": turn["question"]},
                         {"role": "assistant", "content": turn["answer"]}]
        messages.append({"role": "user", "content": question})
        stop_reason, final = "completed", None
        say = on_event or (lambda *_: None)

        def span_id():
            n_span[0] += 1
            return f"{trace_id}-{n_span[0]:02d}"

        for lap in range(1, MAX_ITERS + 1):
            cost = (usage["in"] * PRICE_IN + usage["out"] * PRICE_OUT) / 1_000_000
            if usage["in"] + usage["out"] >= MAX_TOKENS:
                stop_reason = f"BUDGET:max_tokens ({usage['in'] + usage['out']})"
                break
            if cost >= MAX_COST_USD:
                stop_reason = f"BUDGET:max_cost (${cost:.5f})"
                break
            if time.perf_counter() - t_req >= MAX_WALL_SEC:
                stop_reason = f"BUDGET:wall_clock (>= {MAX_WALL_SEC}s)"
                break

            slept0, t0 = _SLEPT[0], time.perf_counter()
            msg, u, first_ms = _model_call(messages, self.tools, temperature, lap, on_token)
            wall = time.perf_counter() - t0
            usage["in"] += u.prompt_tokens
            usage["out"] += u.completion_tokens
            spans.append({"span_id": span_id(), "kind": "llm", "name": f"llm/lap-{lap}", "lap": lap,
                          "latency_ms": round(wall * 1000, 1),
                          "throttle_wait_ms": round((_SLEPT[0] - slept0) * 1000, 1),
                          "model": DEFAULT_MODEL, "prompt_tokens": u.prompt_tokens,
                          "completion_tokens": u.completion_tokens,
                          "cost_usd": round((u.prompt_tokens * PRICE_IN + u.completion_tokens * PRICE_OUT)
                                            / 1_000_000, 8)})
            if first_ms is not None:
                spans[-1]["first_token_ms"] = first_ms
            if not msg.tool_calls:
                final = (msg.content or "").strip()
                break
            messages.append(msg.model_dump(exclude_none=True))  # verbatim: Gemini thought_signature
            for tc in msg.tool_calls:
                qualified = tc.function.name
                args = _parse(tc.function.arguments) or {}
                sid, t0 = span_id(), time.perf_counter()
                if qualified not in self.catalogue:
                    is_error, text, server, tool = True, f"no such tool {qualified!r}", None, None
                else:
                    server, tool_obj = self.catalogue[qualified]
                    tool = tool_obj.name
                    res = await self.sessions[server].call_tool(
                        tool, args, meta={"trace_id": trace_id, "span_id": sid})
                    is_error, text = bool(getattr(res, "is_error", False)), result_text(res)
                spans.append({"span_id": sid, "kind": "tool", "name": f"tool/{qualified}", "lap": lap,
                              "server": server, "tool": tool, "args": args, "is_error": is_error,
                              "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                              "result": _parse(text) if not is_error else None,
                              "error": text if is_error else None, "cost_usd": 0.0})
                say("tool", qualified, args, is_error, text)
                messages.append({"role": "tool", "tool_call_id": tc.id,
                                 "content": json.dumps({"is_error": is_error, "result": text},
                                                       ensure_ascii=False)[:6000]})
        else:
            stop_reason = f"BUDGET:max_iters ({MAX_ITERS} laps)"

        checks = [s["result"] for s in spans
                  if s["kind"] == "tool" and isinstance(s.get("result"), dict) and "verdict" in s["result"]]
        asked = [t["question"] for t in history] + [question]
        rec = {"trace_id": trace_id, "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "user": pseudonym(user), "prompt_version": self.prompt_version, "model": DEFAULT_MODEL,
               "temperature": temperature, "conversation_id": conversation_id, "turn": len(history) + 1,
               "question": question, "answer": final,
               "constraints_detected": sorted({c for q in asked for c in detected_constraints(q)}),
               "constraints_checked": sorted({a for c in checks for a in c["avoid"]}),
               "allergen_checks": checks, "citations": citations(final),
               # an unknown tool keeps the name the model called (e.g. pantry__pantry__...) so the
               # trajectory eval sees it as a wrong tool instead of crashing on None
               "tool_sequence": [s["tool"] or s["name"].split("/", 1)[1] for s in spans if s["kind"] == "tool"],
               "spans": spans, "stop_reason": stop_reason,
               "laps": sum(1 for s in spans if s["kind"] == "llm"),
               "tokens_total": usage["in"] + usage["out"],
               "cost_usd_total": round(sum(s["cost_usd"] for s in spans), 8),
               "latency_ms_total": round((time.perf_counter() - t_req) * 1000, 1)}
        rec["rendered"] = render(rec)
        if log:
            append(CLIENT_LOG, _for_log(rec))
        return rec


def _for_log(rec):
    """The PII line (pantry_trace.py): health statements removed from free text."""
    out = json.loads(json.dumps(rec, ensure_ascii=False))
    for key in ("question", "answer", "rendered"):
        out[key] = redact(out[key])
    for s in out["spans"]:
        if s["kind"] == "tool":
            s["args"] = json.loads(redact(json.dumps(s["args"], ensure_ascii=False)))
    return out
