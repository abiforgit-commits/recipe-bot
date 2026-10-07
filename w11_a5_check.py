"""Week 11: validate assertion A5 against hand labels before trusting it.

    python w11_a5_check.py

A5 is the deterministic check behind the new eval case (w11_r01). It is a grader, so
it gets the Week 6 treatment: compare it with human labels. The labels are every
dairy-free answer collected this week (results/w11_a5_validation.json, 13 BAD of 45).
They were written after seeing the outputs, so this proves A5 matches the failures
seen so far, not unseen ones; fresh runs are the out-of-sample test.
"""
import json
import re
import sys
from pathlib import Path

from w6_assertions import DAIRY_SIDE, a5_no_dairy_side_for_dairy_free

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent
CASE = {"expect_dairy_free": True}

# v2, kept only for this comparison: line scope + a broad list of warning words.
_V2_WARNING = re.compile(
    r"contains? dairy|not dairy[- ]free|isn'?t dairy[- ]free|made (?:with|from) (?:curd|buttermilk|yog)"
    r"|\bavoid\b|\bomit\b|\bskip\b|leave (?:it |them )?out|\bwithout\b|\bexclude\b|\bremove\b", re.I)


def a5_v2(output, case, _):
    return all(_V2_WARNING.search(u) for u in re.split(r"\n+", output) if DAIRY_SIDE.search(u))


def score(fn, items):
    agree, wrong = 0, []
    for it in items:
        verdict_ok = fn(it["output"], CASE, {})
        if verdict_ok == (it["label"] == "OK"):
            agree += 1
        else:
            wrong.append(f"{it['id']}: A5 says {'PASS' if verdict_ok else 'FAIL'}, label {it['label']}")
    return agree, wrong


if __name__ == "__main__":
    data = json.loads((ROOT / "results" / "w11_a5_validation.json").read_text(encoding="utf-8"))
    items = data["items"]
    for name, fn in (("A5 v2 (line scope, broad warnings)", a5_v2),
                     ("A5 v3 (stated outright)", a5_no_dairy_side_for_dairy_free)):
        agree, wrong = score(fn, items)
        print(f"{name}: {agree}/{len(items)} agree with labels ({data['bad']} BAD)")
        for w in wrong:
            print(f"    {w}")
