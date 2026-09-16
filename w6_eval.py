"""Week 6: THE one command - runs the whole eval and prints pass rate by mode.

    python w6_eval.py                      assertions only (safe pre-labels)
    python w6_eval.py --judge judge_v1.txt assertions + LLM judge
    python w6_eval.py --regenerate         re-run the app to refresh outputs

Cases live in w6_cases.jsonl (each tagged with a Week-5 taxonomy mode).
App outputs are generated once and cached in w6_outputs.jsonl so that
labelling, judging, and re-judging all score the SAME outputs.

A case passes when ALL assertions pass AND (if a judge is given) the judge
says PASS. Pass rate is reported per mode - one overall average would hide
a regression in one mode behind wins in another (common mistake #5).
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from w4_retriever import _DOC_BY_ID, hybrid_top
from w5_trace import _build_messages
from ask import call_llm, DEFAULT_MODEL
from w6_assertions import ASSERTIONS, run_assertions

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent
CASES = ROOT / "w6_cases.jsonl"
OUTPUTS = ROOT / "w6_outputs.jsonl"
K = 5


def load_jsonl(path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def generate_outputs(cases):
    """Run the app once per case; cache output + the context it saw."""
    rows = []
    for i, case in enumerate(cases, 1):
        if case.get("replay_output"):  # regression case: verbatim from a real trace
            rows.append({"case_id": case["case_id"], "output": case["replay_output"],
                         "context_ids": case.get("replay_context_ids", [])})
            print(f"{i:>2} [{case['case_id']}] (regression - replayed verbatim)")
            continue
        top = hybrid_top(case["question"], k=K)
        chunks = [(cid, doc) for cid, doc, _ in top]
        resp = call_llm(
            model=DEFAULT_MODEL, temperature=0,
            messages=_build_messages(case["question"], chunks))
        rows.append({"case_id": case["case_id"],
                     "output": resp.choices[0].message.content.strip(),
                     "context_ids": [cid for cid, _ in chunks]})
        print(f"{i:>2} [{case['case_id']}] generated")
    OUTPUTS.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                       encoding="utf-8")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", help="judge prompt file, e.g. judge_v1.txt")
    ap.add_argument("--regenerate", action="store_true")
    args = ap.parse_args()

    cases = load_jsonl(CASES)
    if args.regenerate or not OUTPUTS.exists():
        outputs = generate_outputs(cases)
    else:
        outputs = load_jsonl(OUTPUTS)
    out_by_id = {r["case_id"]: r for r in outputs}

    judge_fn = None
    if args.judge:
        from w6_judge import judge_case
        judge_fn = judge_case

    per_mode = defaultdict(lambda: [0, 0])  # mode -> [passed, total]
    judge_verdicts = {}
    failures = []
    for case in cases:
        row = out_by_id[case["case_id"]]
        checks = run_assertions(row["output"], case, _DOC_BY_ID)
        ok = all(checks.values())
        why = [name for name, passed in checks.items() if not passed]
        if judge_fn:  # judge every case, independent of assertions, so the
            # human-vs-judge agreement sample is not truncated by assertion bugs
            context = "\n\n".join(f"[{cid}]\n{_DOC_BY_ID.get(cid, '')}"
                                  for cid in row["context_ids"])
            verdict, reason = judge_fn(args.judge, case, row["output"], context)
            judge_verdicts[case["case_id"]] = {"verdict": verdict, "reason": reason}
            if verdict != "PASS":
                ok = False
                why.append(f"judge: {reason}")
        per_mode[case["mode"]][1] += 1
        per_mode[case["mode"]][0] += ok
        if not ok:
            failures.append((case["case_id"], case["mode"], "; ".join(why)))

    print(f"\n{'mode':<38}{'pass':>6}{'total':>7}{'rate':>8}")
    total_p = total_n = 0
    for mode, (p, n) in sorted(per_mode.items()):
        print(f"{mode:<38}{p:>6}{n:>7}{p / n:>8.0%}")
        total_p += p
        total_n += n
    print(f"{'ALL':<38}{total_p:>6}{total_n:>7}{total_p / total_n:>8.0%}")
    print(f"\nassertions (deterministic): {len(ASSERTIONS)}   judged criteria: "
          f"{'1 (USEFUL_AND_GROUNDED)' if args.judge else '0 (judge not run)'}")
    if failures:
        print("\nfailed cases:")
        for cid, mode, why in failures:
            print(f"  [{cid}] {mode}: {why}")
    if judge_verdicts:
        (ROOT / "results" / f"w6_judge_verdicts_{Path(args.judge).stem}.json").write_text(
            json.dumps(judge_verdicts, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
