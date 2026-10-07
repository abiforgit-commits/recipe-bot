"""Week 11: which suite cases can a prompt version change at all?

    python w11_scope.py

A case's request is byte-identical to p-v2's unless the version changes the base
prompt, adds a conditional note this case triggers, or pins an allergen note this case
triggers. Cases that are byte-identical cannot regress because of the version, so a
flip there is run-to-run noise (model and judge), not a silent regression.
"""
import json
import sys
from pathlib import Path

from w11_app import ALLERGEN_NOTES, CONDITIONAL_NOTES, PIN_ALLERGEN_NOTES, PROMPTS, detect

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent
BASE = "p-v2"


def touched(question, version):
    banned = detect(question)["banned"]
    return (PROMPTS[version] != PROMPTS[BASE]
            or any(a in banned for a in CONDITIONAL_NOTES.get(version, {}))
            or (version in PIN_ALLERGEN_NOTES and any(a in ALLERGEN_NOTES for a in banned)))


if __name__ == "__main__":
    cases = [json.loads(l) for l in (ROOT / "w6_cases.jsonl").read_text(encoding="utf-8").splitlines()
             if l.strip() and json.loads(l)["case_id"].startswith(("c", "w11"))]
    for v in ("p-v3", "p-v4", "p-v5"):
        t = [c["case_id"] for c in cases if touched(c["question"], v)]
        print(f"{v}: request differs from {BASE} on {len(t)}/{len(cases)} cases: "
              f"{t if len(t) < len(cases) else 'all'}")
