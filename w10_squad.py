"""Week 10: the kitchen squad - one manager, two narrow workers, over MCP.

    python w10_squad.py "Is there sesame in the mango pickle?"
    python w10_squad.py --fail-allergen "Is there sesame in the mango pickle?"

    manager               no MCP tools; two delegation tools; writes the final answer
    substitution_worker   ONLY the recipes server's tools (search, get, scale, substitute)
    allergen_worker       ONLY the ingredient_db server's tools (allergens, nutrition)

A worker sees only the task text the manager writes for it - never the user's
question and never the other worker's report - so every hand-off is one explicit
message whose token cost can be measured. Tools are discovered over MCP exactly
as in w9_agent; this file reuses its connection code and does not change it.
"""
import argparse
import asyncio
import json
import sys
import time
from contextlib import AsyncExitStack
from pathlib import Path

from ask import call_llm, DEFAULT_MODEL
from w9_agent import PRICE_IN, PRICE_OUT, connect_all, result_text, to_llm_tools

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent

MANAGER_MAX_LAPS = 6
WORKER_MAX_LAPS = 6
MAX_WALL_SEC = 300
INJECTED_500 = {"status": 500, "error": "500 Internal Server Error: allergen worker unavailable"}

# The manager's rules mirror w9_agent.SYSTEM so neither arm gets extra coaching.
MANAGER_SYSTEM = """You are the manager of a two-worker kitchen team. Decompose the user's
cooking question, delegate the parts to your workers, then write the final answer.

- substitution_worker: recipes - finding a recipe by dish name, reading its
  ingredients and method, scaling amounts, listing allergen substitutes.
- allergen_worker: allergen flags and per-100g nutrition for NAMED ingredients.

Workers see only the task text you give them, so include every detail they need.

Rules:
- Never state an ingredient, amount, allergen flag or nutrition figure that a worker
  did not report in this conversation.
- If a worker returns an error, read it before deciding what to do next.
- When you have what you need, answer the user plainly and briefly."""

WORKERS = {
    "substitution_worker": {
        "server": "recipes",
        "system": """You are the substitution worker in a kitchen team. You handle recipe
content: finding a recipe, reading its ingredients and method, scaling amounts, and
listing allergen substitutes. You receive one task from your manager and nothing else.
Never state an ingredient, amount or substitute that a tool did not return. Reply to the
manager with a short factual report, including recipe_ids and exact amounts.""",
    },
    "allergen_worker": {
        "server": "ingredient_db",
        "system": """You are the allergen and nutrition worker in a kitchen team. You look up
allergen flags and per-100g nutrition for named ingredients, one tool call per
ingredient. You receive one task from your manager and nothing else. Never state a flag
or figure that a tool did not return; if an ingredient is not found, say so. Reply to
the manager with a short factual report.""",
    },
}

MANAGER_TOOLS = [
    {"type": "function", "function": {
        "name": "delegate_substitution_worker",
        "description": "Hand a recipe task to the substitution worker: find a recipe by dish "
                       "name, read its ingredients and method, scale amounts, or list allergen "
                       "substitutes. The worker sees ONLY the task text you write, so include "
                       "the dish name and every detail it needs. Returns the worker's report.",
        "parameters": {"type": "object", "properties": {
            "task": {"type": "string", "description": "the complete task for the worker"}},
            "required": ["task"]}}},
    {"type": "function", "function": {
        "name": "delegate_allergen_worker",
        "description": "Hand an ingredient task to the allergen and nutrition worker: allergen "
                       "flags or per-100g nutrition for NAMED ingredients. The worker sees ONLY "
                       "the task text you write, so list the exact ingredient names. Returns the "
                       "worker's report.",
        "parameters": {"type": "object", "properties": {
            "task": {"type": "string", "description": "the complete task for the worker"}},
            "required": ["task"]}}},
]
TOOL_TO_WORKER = {"delegate_substitution_worker": "substitution_worker",
                  "delegate_allergen_worker": "allergen_worker"}


class Ledger:
    """Every LLM call and every hand-off message of one squad run."""

    def __init__(self):
        self.calls, self.handoffs, self.context, self.tool_calls = [], [], [], []

    def llm_call(self, actor, handoff, lap, resp):
        u = resp.usage
        rec = {"actor": actor, "handoff": handoff, "lap": lap,
               "prompt_tokens": u.prompt_tokens, "completion_tokens": u.completion_tokens,
               "tokens": u.prompt_tokens + u.completion_tokens}
        self.calls.append(rec)
        return rec

    def handoff(self, frm, to, text):
        ev = {"seq": len(self.handoffs) + 1, "from": frm, "to": to,
              "chars": len(text), "tokens": None, "note": ""}
        self.handoffs.append(ev)
        return ev

    @property
    def tokens(self):
        return (sum(c["prompt_tokens"] for c in self.calls),
                sum(c["completion_tokens"] for c in self.calls))


async def run_worker(name, task, sessions, catalogue, ledger):
    """One worker's own tool loop. Returns (report, tokens_spent)."""
    server = WORKERS[name]["server"]
    mine = {q: v for q, v in catalogue.items() if v[0] == server}
    tools = to_llm_tools(mine)
    messages = [{"role": "system", "content": WORKERS[name]["system"]},
                {"role": "user", "content": task}]
    spent = 0
    for lap in range(1, WORKER_MAX_LAPS + 1):
        resp = call_llm(model=DEFAULT_MODEL, temperature=0, messages=messages, tools=tools)
        spent += ledger.llm_call(name, f"manager -> {name}", lap, resp)["tokens"]
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return (msg.content or "").strip(), spent
        messages.append(msg.model_dump(exclude_none=True))
        for tc in msg.tool_calls:
            qualified = tc.function.name
            args = json.loads(tc.function.arguments or "{}")
            if qualified in mine:
                srv, tool = mine[qualified]
                result = await sessions[srv].call_tool(tool.name, args)
                text, is_error = result_text(result), bool(getattr(result, "is_error", False))
            else:
                text, is_error = f"no such tool {qualified!r}", True
            ledger.context.append(f"[{qualified}] {json.dumps(args, ensure_ascii=False)} -> {text}")
            ledger.tool_calls.append({"worker": name, "tool": qualified, "arguments": args,
                                      "is_error": is_error, "result": text})
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps({"is_error": is_error, "result": text},
                                                   ensure_ascii=False)[:4000]})
    return "worker stopped: lap budget exhausted before a report", spent


async def run_squad(request, config_path, fail_allergen=False, verbose=True):
    t0 = time.time()
    ledger = Ledger()
    stop_reason, final = "completed", None
    async with AsyncExitStack() as stack:
        sessions, catalogue = await connect_all(config_path, stack)
        messages = [{"role": "system", "content": MANAGER_SYSTEM},
                    {"role": "user", "content": request}]
        awaiting_reader = [ledger.handoff("user", "manager", request)]
        label = "user -> manager (plan)"

        for lap in range(1, MANAGER_MAX_LAPS + 1):
            if time.time() - t0 >= MAX_WALL_SEC:
                stop_reason = f"BUDGET:wall_clock (>= {MAX_WALL_SEC}s)"
                break
            resp = call_llm(model=DEFAULT_MODEL, temperature=0, messages=messages,
                            tools=MANAGER_TOOLS)
            rec = ledger.llm_call("manager", label, lap, resp)
            for ev in awaiting_reader:  # this lap is what re-reads those messages
                ev["tokens"] = rec["tokens"]
                ev["note"] = (f"read by manager lap {lap}" if len(awaiting_reader) == 1
                              else f"read by manager lap {lap}, shared by {len(awaiting_reader)} hand-offs")
            msg = resp.choices[0].message

            if not msg.tool_calls:
                final = (msg.content or "").strip()
                rec["synthesis"] = True
                if verbose:
                    print(f"[manager lap {lap}] final answer")
                break

            messages.append(msg.model_dump(exclude_none=True))
            awaiting_reader, returned = [], []
            for tc in msg.tool_calls:
                worker = TOOL_TO_WORKER.get(tc.function.name)
                task = json.loads(tc.function.arguments or "{}").get("task", "")
                out = ledger.handoff("manager", worker or tc.function.name, task)
                if worker is None:
                    payload = {"status": 400, "error": f"no such worker tool {tc.function.name!r}"}
                    out["tokens"] = 0
                elif worker == "allergen_worker" and fail_allergen:
                    payload = dict(INJECTED_500)
                    out["tokens"], out["note"] = 0, "INJECTED 500 - worker never ran"
                else:
                    report, spent = await run_worker(worker, task, sessions, catalogue, ledger)
                    payload = {"status": 200, "report": report}
                    out["tokens"], out["note"] = spent, "worker loop"
                if verbose:
                    print(f"[manager lap {lap}] -> {worker}: {task[:90]!r}  "
                          f"=> {payload.get('status')} ({out['tokens']} tok)")
                body = json.dumps(payload, ensure_ascii=False)
                awaiting_reader.append(ledger.handoff(worker or "?", "manager", body))
                returned.append(worker or "?")
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": body[:6000]})
            label = f"{'+'.join(dict.fromkeys(returned))} -> manager (re-read)"
        else:
            stop_reason = f"BUDGET:max_iters ({MANAGER_MAX_LAPS} manager laps used)"

    tin, tout = ledger.tokens
    return {"arm": "multi", "request": request, "final": final, "stop_reason": stop_reason,
            "fail_allergen": fail_allergen,
            "tokens_in": tin, "tokens_out": tout, "tokens_total": tin + tout,
            "cost_usd": round((tin * PRICE_IN + tout * PRICE_OUT) / 1_000_000, 6),
            "latency_s": round(time.time() - t0, 2),
            "llm_calls": len(ledger.calls), "calls": ledger.calls,
            "handoffs": ledger.handoffs, "tool_calls": ledger.tool_calls,
            "context": ledger.context}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("request")
    ap.add_argument("--config", default="mcp_config.json")
    ap.add_argument("--fail-allergen", action="store_true")
    args = ap.parse_args()
    r = asyncio.run(run_squad(args.request, (ROOT / args.config).resolve(), args.fail_allergen))
    print(f"\nstop_reason={r['stop_reason']}  llm_calls={r['llm_calls']}  "
          f"tokens={r['tokens_total']}  cost=${r['cost_usd']:.6f}  latency={r['latency_s']}s")
    for h in r["handoffs"]:
        print(f"  #{h['seq']} {h['from']} -> {h['to']}  chars={h['chars']}  "
              f"tokens={h['tokens']}  {h['note']}")
    print(f"\n{r['final']}")


if __name__ == "__main__":
    main()
