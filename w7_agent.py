"""Week 7: hand-built agent loop with four enforced budgets.

    python w7_agent.py "Halve the appam recipe and make it coconut-free and nut-free"

The loop is plan -> call tool -> observe -> repeat. Every lap is logged.

FOUR budgets, all CHECKED (not merely declared):
    MAX_ITERS      - laps of the loop
    MAX_TOKENS     - cumulative prompt+completion tokens across all laps
    MAX_COST_USD   - cumulative modelled cost
    MAX_WALL_SEC   - wall-clock seconds since start
Any breach terminates cleanly with stop_reason set, never spins.

Token accounting sums EVERY lap. The loop re-sends the whole message list
each time, so counting only the final call understates cost by multiples.
"""
import argparse
import json
import sys
import time
from pathlib import Path

from ask import call_llm, DEFAULT_MODEL
from w7_tools import TOOL_SCHEMAS, OUTPUT_CONTRACT, call_tool

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent

MAX_ITERS = 8
MAX_TOKENS = 20000
MAX_COST_USD = 0.02
MAX_WALL_SEC = 120

# Modelled rate card for gemini-flash-lite (USD per 1M tokens).
PRICE_IN, PRICE_OUT = 0.10, 0.40

SYSTEM = f"""You adapt recipes using ONLY the three tools provided.

Work in steps. Typical order: find the recipe, remove banned allergens, then
scale. If a substitute you choose itself carries an allergen the user banned,
call substitute_ingredient again or pick a different option from the list you
were already given - never leave a banned allergen in the final ingredients.

When you have everything, reply with the final answer and nothing else.
{OUTPUT_CONTRACT}"""


def cost_of(usage):
    return (usage["in"] * PRICE_IN + usage["out"] * PRICE_OUT) / 1_000_000


def run_agent(request, verbose=True):
    t0 = time.time()
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": request}]
    usage = {"in": 0, "out": 0}
    log = []
    stop_reason = "completed"
    final = None

    for lap in range(1, MAX_ITERS + 1):
        # ---- budget checks BEFORE spending more (all four enforced) ----
        elapsed = time.time() - t0
        if usage["in"] + usage["out"] >= MAX_TOKENS:
            stop_reason = f"BUDGET:max_tokens ({usage['in'] + usage['out']} >= {MAX_TOKENS})"
            break
        if cost_of(usage) >= MAX_COST_USD:
            stop_reason = f"BUDGET:max_cost (${cost_of(usage):.5f} >= ${MAX_COST_USD})"
            break
        if elapsed >= MAX_WALL_SEC:
            stop_reason = f"BUDGET:wall_clock ({elapsed:.1f}s >= {MAX_WALL_SEC}s)"
            break

        resp = call_llm(model=DEFAULT_MODEL, temperature=0, messages=messages,
                        tools=TOOL_SCHEMAS)
        u = resp.usage
        usage["in"] += u.prompt_tokens
        usage["out"] += u.completion_tokens
        msg = resp.choices[0].message

        if not msg.tool_calls:
            final = (msg.content or "").strip()
            log.append({"lap": lap, "action": "final_answer",
                        "tokens_this_lap": u.total_tokens})
            if verbose:
                print(f"[lap {lap}] final answer ({u.total_tokens} tok)")
            break

        # Echo the assistant message back VERBATIM. Gemini puts a
        # thought_signature inside tool_calls[].extra_content.google and
        # rejects the next request if it is dropped, so rebuilding the
        # message by hand breaks the loop on lap 2.
        messages.append(msg.model_dump(exclude_none=True))
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            result = call_tool(tc.function.name, args)
            log.append({"lap": lap, "action": "tool_call", "tool": tc.function.name,
                        "args": args, "tokens_this_lap": u.total_tokens})
            if verbose:
                print(f"[lap {lap}] {tc.function.name}({json.dumps(args)}) "
                      f"-> {str(result)[:90]} ({u.total_tokens} tok)")
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(result)[:2000]})
    else:
        stop_reason = f"BUDGET:max_iters ({MAX_ITERS} laps used)"

    return {"system": "agent", "request": request, "final": final,
            "stop_reason": stop_reason, "laps": len(log),
            "tokens_in": usage["in"], "tokens_out": usage["out"],
            "tokens_total": usage["in"] + usage["out"],
            "cost_usd": round(cost_of(usage), 6),
            "latency_s": round(time.time() - t0, 2), "log": log}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("request")
    args = ap.parse_args()
    r = run_agent(args.request)
    print(f"\nstop_reason: {r['stop_reason']}")
    print(f"laps={r['laps']} tokens={r['tokens_total']} cost=${r['cost_usd']:.6f} "
          f"latency={r['latency_s']}s")
    print(f"\n{r['final']}")
