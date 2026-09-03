"""Week 6: deterministic assertions - criteria moved OUT of the LLM judge.

These are checks a rule can do for free, every time, with no off days.
Paying a model to check string presence is common mistake #3 in the task.

Assertions implemented (moved from judge to code):
  A1 citation_present   - a grounded answer must cite at least one [chunk_id]
  A2 citations_resolve  - every cited chunk_id must exist in the index
  A3 refusal_exact      - out-of-corpus cases must produce the exact refusal
  A4 no_invented_grams  - every gram/percent quantity in the answer must
                          appear verbatim in at least one cited chunk
"""
import re

from ask import REFUSAL

CITE_RE = re.compile(r"\[([a-z0-9-]+::[a-z]+::\d+)\]")
QTY_RE = re.compile(r"\b\d+(?:\.\d+)?\s?(?:g|kg|%)\b")


def citation_present(output, case, chunk_lookup):
    """A1: answers (non-refusals) must carry at least one citation."""
    if output.strip().strip('"') == REFUSAL:
        return True
    return bool(CITE_RE.search(output))


def citations_resolve(output, case, chunk_lookup):
    """A2: every cited chunk_id exists in the index."""
    cited = CITE_RE.findall(output)
    return all(cid in chunk_lookup for cid in cited)


def refusal_exact(output, case, chunk_lookup):
    """A3: cases tagged expect_refusal must produce the exact refusal sentence."""
    if not case.get("expect_refusal"):
        return True
    return output.strip().strip('"') == REFUSAL


def no_invented_grams(output, case, chunk_lookup):
    """A4: every quantity (g/kg/%) in the answer appears in a cited chunk."""
    if output.strip().strip('"') == REFUSAL:
        return True
    cited_text = " ".join(chunk_lookup.get(cid, "") for cid in CITE_RE.findall(output))
    if not cited_text:
        cited_text = ""
    for qty in QTY_RE.findall(output.replace("–", "-")):
        if qty not in cited_text:
            return False
    return True


ASSERTIONS = {
    "A1_citation_present": citation_present,
    "A2_citations_resolve": citations_resolve,
    "A3_refusal_exact": refusal_exact,
    "A4_no_invented_grams": no_invented_grams,
}


def run_assertions(output, case, chunk_lookup):
    """Returns {assertion_name: True/False} for one case."""
    return {name: fn(output, case, chunk_lookup) for name, fn in ASSERTIONS.items()}
