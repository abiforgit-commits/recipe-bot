"""Week 8: trajectory eval - score the PATH, not just the answer.

    python w8_trajectory.py --tag baseline
    python w8_trajectory.py --tag mitigated

Runs the Week 7 agent over the 10 Week 7 requests, captures each run's tool
sequence and arguments, and scores:

  tool-choice accuracy   fraction of tool CALLS that were a tool this case
                         legitimately needs
  argument validity      fraction of tool calls whose arguments were real
                         (existing recipe_id, allergen inside the enum,
                         numeric factor) rather than fluent fiction
  step efficiency        steps_taken / steps_needed  (1.0 = perfect,
                         higher = wasteful)
  cost per request       p50 AND max - the mean hides the one run that
                         looped chasing a substitute for a substitute

plus OUTCOME pass (Week 7's checker) and TRAJECTORY pass, whose difference
is the outcome-vs-trajectory gap: right answer, wrong path.

FAILURE MODE ZOO (each run gets zero or more):
  skipped_required_tool  produced the answer without calling a tool the case
                         needed - the "it just knew" time bomb
  wrong_tool             called a tool this case has no use for
  invalid_arguments      hallucinated a recipe_id / allergen / factor
  no_op_call             spent a lap on a call that changes nothing
                         (scale_recipe with factor 1.0)
  redundant_steps        step efficiency > 1.5
  gave_up                terminated on a budget with no final answer
"""
import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

from w7_agent import run_agent
from w7_race import check
from w7_tools import ALLERGENS, CARDS_BY_ID

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent
REDUNDANCY_LIMIT = 1.5


def arg_is_valid(tool, args):
    """Were the arguments real, or fluent fiction?"""
    if tool == "search_recipes":
        return isinstance(args.get("query"), str) and bool(args.get("query", "").strip())
    if tool == "scale_recipe":
        if args.get("recipe_id") not in CARDS_BY_ID:
            return False
        try:
            float(args.get("factor"))
        except (TypeError, ValueError):
            return False
        return True
    if tool == "substitute_ingredient":
        return args.get("recipe_id") in CARDS_BY_ID and args.get("allergen") in ALLERGENS
    return False


def score_run(case, result):
    """Returns a dict of trajectory scores + the failure modes fired."""
    calls = [e for e in result["log"] if e["action"] == "tool_call"]
    seq = [c["tool"] for c in calls]
    needed = set(case["required_tools"])
    allowed = set(case.get("allowed_tools", case["required_tools"]))
    modes = []

    # tool-choice accuracy: calls using a tool ANY accepted path may use.
    # A tool that is allowed-but-not-required (scale_recipe on a factor-1.0
    # request) is wasteful, not wrong - step_efficiency prices that. Scoring
    # it as wrong_tool would penalise a path this eval explicitly accepts.
    good_calls = sum(1 for t in seq if t in allowed)
    tool_acc = good_calls / len(seq) if seq else 0.0
    if any(t not in allowed for t in seq):
        modes.append("wrong_tool")

    # argument validity
    valid_args = sum(1 for c in calls if arg_is_valid(c["tool"], c["args"]))
    arg_rate = valid_args / len(calls) if calls else 0.0
    if valid_args < len(calls):
        modes.append("invalid_arguments")

    # no-op calls: a whole agent lap spent on a call that changes nothing.
    # scale_recipe(factor=1.0) multiplies every quantity by one. The outcome
    # is unaffected, which is exactly why only a trajectory eval can see it.
    no_ops = [c for c in calls
              if c["tool"] == "scale_recipe" and float(c["args"].get("factor", 0)) == 1.0]
    if no_ops:
        modes.append("no_op_call")

    # step efficiency
    steps_taken = len(seq)
    efficiency = steps_taken / case["steps_needed"]
    if efficiency > REDUNDANCY_LIMIT:
        modes.append("redundant_steps")

    # skipped a required tool - the headline mode
    missing = [t for t in needed if t not in seq]
    if missing:
        modes.append("skipped_required_tool")

    if result["final"] is None:
        modes.append("gave_up")

    trajectory_pass = seq in [list(s) for s in case["valid_sequences"]] and not modes
    if not trajectory_pass and not modes:
        modes.append("unrecognised_sequence")
    return {"sequence": seq, "tool_choice_accuracy": tool_acc,
            "argument_validity": arg_rate, "steps_taken": steps_taken,
            "step_efficiency": efficiency, "missing_tools": missing,
            "modes": modes, "trajectory_pass": trajectory_pass}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True, help="baseline | mitigated")
    args = ap.parse_args()

    cases = [json.loads(l) for l in
             (ROOT / "w8_cases.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

    rows = []
    for case in cases:
        result = run_agent(case["request"], verbose=False)
        outcome_pass, outcome_why = check(result, case)
        traj = score_run(case, result)
        rows.append({"id": case["id"], "class": case["class"],
                     "outcome_pass": outcome_pass, "outcome_why": outcome_why,
                     "cost_usd": result["cost_usd"], "latency_s": result["latency_s"],
                     "tokens": result["tokens_total"], "stop_reason": result["stop_reason"],
                     **traj})
        flags = ",".join(traj["modes"]) or "-"
        print(f"  #{case['id']:<2} outcome={'PASS' if outcome_pass else 'FAIL'} "
              f"traj={'PASS' if traj['trajectory_pass'] else 'FAIL'} "
              f"eff={traj['step_efficiency']:.2f} ${result['cost_usd']:.6f}  "
              f"{'>'.join(traj['sequence']) or '(no tools)'}  [{flags}]", flush=True)

    n = len(rows)
    outcome_rate = sum(r["outcome_pass"] for r in rows) / n
    traj_rate = sum(r["trajectory_pass"] for r in rows) / n
    summary = {
        "tag": args.tag,
        "tool_choice_accuracy": round(statistics.mean(r["tool_choice_accuracy"] for r in rows), 3),
        "argument_validity": round(statistics.mean(r["argument_validity"] for r in rows), 3),
        "step_efficiency": round(statistics.mean(r["step_efficiency"] for r in rows), 3),
        "cost_p50": round(statistics.median(r["cost_usd"] for r in rows), 6),
        "cost_max": round(max(r["cost_usd"] for r in rows), 6),
        "latency_p50": round(statistics.median(r["latency_s"] for r in rows), 2),
        "tokens_total": sum(r["tokens"] for r in rows),
        "outcome_pass_rate": round(outcome_rate, 3),
        "trajectory_pass_rate": round(traj_rate, 3),
        "gap": round(outcome_rate - traj_rate, 3),
        "mode_counts": dict(Counter(m for r in rows for m in r["modes"])),
    }

    print(f"\n--- {args.tag} ---")
    print(f"tool-choice accuracy : {summary['tool_choice_accuracy']:.1%}")
    print(f"argument validity    : {summary['argument_validity']:.1%}")
    print(f"step efficiency      : {summary['step_efficiency']:.2f}  (1.00 = no wasted steps)")
    print(f"cost per request     : p50 ${summary['cost_p50']:.6f}   max ${summary['cost_max']:.6f}")
    print(f"outcome pass rate    : {summary['outcome_pass_rate']:.0%}")
    print(f"trajectory pass rate : {summary['trajectory_pass_rate']:.0%}")
    print(f"GAP (outcome - traj) : {summary['gap']:+.0%}")
    print(f"failure modes        : {summary['mode_counts'] or 'none'}")

    out = ROOT / "results" / f"w8_trajectory_{args.tag}.json"
    out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print(f"\nwritten to {out.name}")


if __name__ == "__main__":
    main()
