"""Capstone: validate a judge on HELD-OUT outputs it was never tuned on.

    python pantry_judge_holdout.py sheet                  build the blind label sheet
    python pantry_judge_holdout.py judge judge_v4.txt     judge every held-out item
    python pantry_judge_holdout.py agree judge_v4.txt     agreement vs pantry_labels_holdout.json

Held-out set: the 20 realistic traffic answers and the 30 allergy repeat answers
(before and after the fix). judge_v3 was tuned on the 33 baseline suite outputs and
judge_v4 on the 33 post-fix suite outputs; neither saw these 50.
"""
import json
import sys
from pathlib import Path

from pantry_eval import judge_context, load_jsonl

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent
R = ROOT / "results"
SOURCES = ["pantry_traffic_before.jsonl", "pantry_runs_before_allergy.jsonl", "pantry_runs_after_allergy.jsonl"]


def items():
    out = []
    for src in SOURCES:
        for r in load_jsonl(R / src):
            key = r.get("traffic_id") or f"{'pre' if 'before' in src else 'post'}-{r['case_id']}"
            out.append({"id": key, "trace_id": r["trace_id"], "rec": r})
    return out


def sheet():
    lines = ["# Label sheet: held-out outputs (blind: no judge verdicts, no assertion results)", ""]
    for it in items():
        r = it["rec"]
        lines += [f"## {it['id']}", "", f"**Question:** {r['question']}", "",
                  "**What the assistant was shown (tool results):**", "", "```", judge_context(r), "```", "",
                  "**What the user saw:**", "", "```", r["rendered"], "```", ""]
    (R / "pantry_label_sheet_holdout.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(items())} items -> results/pantry_label_sheet_holdout.md")


def judge(judge_file):
    from w6_judge import judge_case
    out = {}
    for it in items():
        r = it["rec"]
        verdict, reason = judge_case(judge_file, {"question": r["question"]}, r["rendered"], judge_context(r))
        out[it["id"]] = {"verdict": verdict, "reason": reason, "trace_id": it["trace_id"]}
        print(f"  {it['id']:<14} {verdict}  {reason[:90]}", flush=True)
    (R / f"pantry_holdout_verdicts.{Path(judge_file).stem}.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")


def agree(judge_file):
    labels = {l["id"]: l for l in json.loads((ROOT / "pantry_labels_holdout.json").read_text(encoding="utf-8"))["labels"]}
    verdicts = json.loads((R / f"pantry_holdout_verdicts.{Path(judge_file).stem}.json").read_text(encoding="utf-8"))
    rows = [(i, labels[i]["label"], verdicts[i]["verdict"], verdicts[i]["reason"], labels[i]["why"]) for i in labels]
    ok = sum(l == v for _, l, v, _, _ in rows)
    print(f"\n{judge_file} on {len(rows)} HELD-OUT outputs: {ok}/{len(rows)} = {ok / len(rows):.1%}   "
          f"(bar 85.0%: {'CLEARS' if ok / len(rows) >= 0.85 else 'DOES NOT CLEAR'})")
    for i, l, v, jr, lw in rows:
        if l != v:
            print(f"[{i}] label={l} judge={v}\n   judge: {jr[:160]}\n   label: {lw[:160]}")
    (R / f"pantry_holdout_agreement.{Path(judge_file).stem}.json").write_text(json.dumps(
        {"judge": judge_file, "n": len(rows), "agree": ok, "agreement": round(ok / len(rows), 3),
         "disagreements": [{"id": i, "label": l, "judge": v, "judge_reason": jr, "label_why": lw}
                           for i, l, v, jr, lw in rows if l != v]}, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    cmd = sys.argv[1]
    {"sheet": lambda: sheet(), "judge": lambda: judge(sys.argv[2]), "agree": lambda: agree(sys.argv[2])}[cmd]()
