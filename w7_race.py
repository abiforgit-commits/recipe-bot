"""Week 7: race the agent against the fixed workflow over the same 10 requests.

    python w7_race.py            both systems, writes race.csv
    python w7_race.py --system agent

Four numbers per system: pass rate, p50 latency, total tokens, cost/request.

PASS requires all of:
  - output parses as JSON matching the contract
  - correct recipe_id
  - correct scale_factor
  - NO banned allergen survives in the final ingredient list, counting the
    allergen carried by any substitute that was chosen (the cascade check)
"""
import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

from w7_tools import INGREDIENT_ALLERGEN, SUBSTITUTES
from w7_agent import run_agent
from w7_workflow import run_workflow

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent

# name -> allergen it carries, for originals AND every possible substitute
ALLERGEN_OF = {k: v for k, v in INGREDIENT_ALLERGEN.items()}
for opts in SUBSTITUTES.values():
    for name, carries in opts:
        ALLERGEN_OF[name.lower()] = carries


def check(result, case):
    """Returns (passed, reason)."""
    raw = (result.get("final") or "").strip()
    if not raw:
        return False, f"no output ({result['stop_reason']})"
    if "```" in raw:
        raw = raw.split("```json")[-1].split("```")[0]
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return False, "output is not valid JSON"
    if obj.get("recipe_id") != case["recipe_id"]:
        return False, f"wrong recipe_id {obj.get('recipe_id')}"
    try:
        if abs(float(obj.get("scale_factor", 0)) - case["factor"]) > 1e-6:
            return False, f"wrong scale_factor {obj.get('scale_factor')}"
    except (TypeError, ValueError):
        return False, "scale_factor not numeric"
    for ing in obj.get("ingredients", []):
        carried = ALLERGEN_OF.get(str(ing.get("name", "")).lower())
        if carried and carried in case["banned"]:
            return False, f"banned allergen '{carried}' survives via '{ing.get('name')}'"
    return True, "ok"


def race(system, cases):
    runner = run_agent if system == "agent" else run_workflow
    rows = []
    for case in cases:
        r = runner(case["request"], verbose=False)
        ok, why = check(r, case)
        rows.append({"id": case["id"], "class": case["class"], "system": system,
                     "passed": ok, "why": why, "latency_s": r["latency_s"],
                     "tokens": r["tokens_total"], "cost_usd": r["cost_usd"],
                     "laps": r["laps"], "stop_reason": r["stop_reason"]})
        print(f"  [{system}] #{case['id']:<2} {case['class']:<17} "
              f"{'PASS' if ok else 'FAIL'}  {r['latency_s']:>6.2f}s "
              f"{r['tokens_total']:>6} tok  ${r['cost_usd']:.6f}"
              f"{'' if ok else '  <- ' + why}", flush=True)
    return rows


def summarise(rows, system):
    mine = [r for r in rows if r["system"] == system]
    n = len(mine)
    return {"system": system, "pass_rate": f"{sum(r['passed'] for r in mine)}/{n}",
            "p50_latency_s": round(statistics.median(r["latency_s"] for r in mine), 2),
            "total_tokens": sum(r["tokens"] for r in mine),
            "cost_per_request_usd": round(sum(r["cost_usd"] for r in mine) / n, 6)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", choices=["agent", "workflow", "both"], default="both")
    args = ap.parse_args()
    cases = [json.loads(l) for l in
             (ROOT / "w7_requests.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

    rows = []
    for system in (["agent", "workflow"] if args.system == "both" else [args.system]):
        print(f"\n=== {system} ===")
        rows += race(system, cases)

    with (ROOT / "race.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"\n{'system':<10}{'pass rate':>11}{'p50 latency':>13}{'total tokens':>14}{'cost/request':>14}")
    for system in sorted({r["system"] for r in rows}):
        s = summarise(rows, system)
        print(f"{s['system']:<10}{s['pass_rate']:>11}{s['p50_latency_s']:>12}s"
              f"{s['total_tokens']:>14}{'$' + format(s['cost_per_request_usd'], '.6f'):>14}")

    # per-class pass rate: the cascade class is where an agent would earn its keep
    print(f"\n{'class':<18}{'agent':>8}{'workflow':>10}")
    for cls in ["simple-scale", "single-swap", "allergen-cascade"]:
        line = f"{cls:<18}"
        for system in ["agent", "workflow"]:
            sub = [r for r in rows if r["system"] == system and r["class"] == cls]
            line += f"{sum(r['passed'] for r in sub)}/{len(sub):<7}" if sub else f"{'-':>8}"
        print(line)
    print(f"\nrace.csv written")


if __name__ == "__main__":
    main()
