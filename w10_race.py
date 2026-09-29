"""Week 10: race the kitchen squad against the single agent on the same 10 cases.

    python w10_race.py run        both arms, interleaved per case, resumable
    python w10_race.py judge      Week-6 judge (judge_v2.txt) on every answer, resumable
    python w10_race.py fail       the injected-500 run on c17 (declared before any run)

single arm = w9_agent.run, the Week 9 agent, unchanged (6 tools, 2 MCP servers)
multi  arm = w10_squad.run_squad (manager + substitution worker + allergen worker)

Latency is measured here, identically for both arms, as wall-clock seconds around
the whole request (MCP server start-up included). Free-tier pacing and 429 backoff
sleep inside ask.call_llm; the harness also records how long each request spent in
time.sleep, so latency is reported both raw and net of throttling.
"""
import asyncio
import io
import json
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path

import w9_agent
from w10_squad import run_squad
from w6_judge import judge_case

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent
CONFIG = (ROOT / "mcp_config.json").resolve()
CASES = json.loads((ROOT / "w10_cases.json").read_text(encoding="utf-8"))["cases"]
ROWS = ROOT / "results" / "w10_race_rows.jsonl"
JUDGED = ROOT / "results" / "w10_judged.jsonl"
FAIL_CASE = "c17"

# --- measurement: how long each request spends sleeping (pacing + 429 backoff) ---
_SLEPT = [0.0]
_real_sleep = time.sleep


def _counting_sleep(seconds):
    _SLEPT[0] += max(0.0, seconds)
    _real_sleep(seconds)


time.sleep = _counting_sleep  # ask.call_llm does `import time as _t; _t.sleep(...)`


def load(path):
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def append(path, row):
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def run_single(case):
    tag = f"w10_single_{case['case_id']}"
    with redirect_stdout(io.StringIO()):
        summary = asyncio.run(w9_agent.run(case["question"], CONFIG, tag))
    trace = load(ROOT / "results" / f"w9_trace_{tag}.jsonl")
    final = next((e["text"] for e in trace if e["event"] == "final"), None)
    tool_calls = [e for e in trace if e["event"] == "tool_call"]
    return {"final": final, "stop_reason": summary["stop_reason"],
            "tokens_total": summary["tokens_total"], "cost_usd": summary["cost_usd"],
            "llm_calls": summary["laps"],
            "tool_calls": [{"tool": e["qualified"], "arguments": e["arguments"],
                            "is_error": e["is_error"], "result": e["result"]} for e in tool_calls],
            "context": [f"[{e['qualified']}] {json.dumps(e['arguments'], ensure_ascii=False)} "
                        f"-> {e['result']}" for e in tool_calls],
            "trace_file": f"results/w9_trace_{tag}.jsonl"}


def run_multi(case, fail_allergen=False):
    return asyncio.run(run_squad(case["question"], CONFIG, fail_allergen=fail_allergen,
                                 verbose=False))


def timed(fn, *args, **kw):
    slept0, t0 = _SLEPT[0], time.perf_counter()
    out = fn(*args, **kw)
    wall = time.perf_counter() - t0
    slept = _SLEPT[0] - slept0
    out["latency_wall_s"] = round(wall, 2)
    out["latency_slept_s"] = round(slept, 2)
    out["latency_net_s"] = round(wall - slept, 2)
    return out


def cmd_run():
    done = {(r["arm"], r["case_id"]) for r in load(ROWS)}
    for case in CASES:
        for arm, fn in (("single", run_single), ("multi", run_multi)):
            if (arm, case["case_id"]) in done:
                continue
            out = timed(fn, case)
            out.update({"arm": arm, "case_id": case["case_id"], "question": case["question"]})
            append(ROWS, out)
            print(f"{arm:<6} {case['case_id']}  calls={out['llm_calls']:<2} "
                  f"tokens={out['tokens_total']:<6} wall={out['latency_wall_s']:>6}s "
                  f"net={out['latency_net_s']:>6}s  {out['stop_reason']}", flush=True)


def cmd_judge():
    done = {(r["arm"], r["case_id"]) for r in load(JUDGED)}
    for row in load(ROWS):
        key = (row["arm"], row["case_id"])
        if key in done:
            continue
        context = "\n\n".join(row["context"]) or "(no tool output)"
        verdict, reason = judge_case("judge_v2.txt", {"question": row["question"]},
                                     row["final"] or "(no answer)", context)
        append(JUDGED, {"arm": row["arm"], "case_id": row["case_id"],
                        "verdict": verdict, "reason": reason})
        print(f"{row['arm']:<6} {row['case_id']}  {verdict}  {reason[:90]}", flush=True)


def cmd_fail():
    case = next(c for c in CASES if c["case_id"] == FAIL_CASE)
    out = timed(run_multi, case, fail_allergen=True)
    out.update({"case_id": FAIL_CASE, "question": case["question"]})
    path = ROOT / "results" / f"w10_failure_{FAIL_CASE}.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    for h in out["handoffs"]:
        print(f"  #{h['seq']} {h['from']} -> {h['to']}  tokens={h['tokens']}  {h['note']}")
    print(f"\nstop_reason={out['stop_reason']}\nFINAL:\n{out['final']}\nsaved {path.name}")


if __name__ == "__main__":
    {"run": cmd_run, "judge": cmd_judge, "fail": cmd_fail}[sys.argv[1]]()
