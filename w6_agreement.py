"""Week 6: agreement between the human labels and a judge run.

    python w6_agreement.py judge_v1        (reads results/w6_judge_verdicts_judge_v1.json)

Prints agreement as a percentage plus the disagreement list, so the two
disagreements used as few-shot examples in judge_v2 come from the judge's OWN
mistakes, not from cases hand-picked afterwards.
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent


def main():
    stem = sys.argv[1] if len(sys.argv) > 1 else "judge_v1"
    labels = {l["case_id"]: l for l in
              json.loads((ROOT / "labels_25.json").read_text(encoding="utf-8"))["labels"]}
    verdicts = json.loads(
        (ROOT / "results" / f"w6_judge_verdicts_{stem}.json").read_text(encoding="utf-8"))
    cases = {json.loads(l)["case_id"]: json.loads(l) for l in
             (ROOT / "w6_cases.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}

    agree, total, rows = 0, 0, []
    for cid, lab in labels.items():
        if cid not in verdicts:
            continue
        total += 1
        jv = verdicts[cid]["verdict"]
        ok = jv == lab["label"]
        agree += ok
        rows.append((cid, cases[cid]["mode"], lab["label"], jv, ok,
                     verdicts[cid]["reason"], lab["why"]))

    print(f"\nagreement ({stem}): {agree}/{total} = {agree / total:.0%}\n")
    print(f"{'case':<6}{'mode':<34}{'human':<7}{'judge':<7}")
    for cid, mode, hl, jv, ok, _, _ in rows:
        print(f"{cid:<6}{mode:<34}{hl:<7}{jv:<7}{'' if ok else '  <-- DISAGREE'}")

    dis = [r for r in rows if not r[4]]
    print(f"\ndisagreements: {len(dis)}")
    for cid, mode, hl, jv, _, jreason, hwhy in dis:
        print(f"\n[{cid}] human={hl}  judge={jv}")
        print(f"  judge said : {jreason}")
        print(f"  human said : {hwhy}")


if __name__ == "__main__":
    main()
