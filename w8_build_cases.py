"""Week 8: build the 10 trajectory cases with their EXPECTED TOOL SEQUENCES.

Reuses the same 10 requests raced in Week 7, so the outcome pass rate is
already known (10/10) and any gap is purely a path problem.

Expected paths are asserted as a SET, not one sequence, because several
orderings are legitimately correct:
  - search_recipes must come first (nothing else has a recipe_id yet)
  - substitute_ingredient and scale_recipe commute: swapping an allergen
    before or after scaling both give the same dish
  - with N banned allergens, 1..N substitute calls are all reasonable -
    one per allergen, or one call that happens to clear several
  - when factor == 1.0 the scale call is optional, not wrong

Over-asserting a single sequence would score correct runs as failures and
inflate the gap, which is the task's listed common mistake.
"""
import json
from itertools import permutations
from pathlib import Path

ROOT = Path(__file__).parent


def valid_sequences(n_banned, factor):
    """Every tool sequence a competent agent could legitimately take."""
    seqs = set()
    sub_counts = range(1, max(n_banned, 1) + 1) if n_banned else [0]
    scale_opts = [1] if factor != 1.0 else [0, 1]  # optional when factor is 1
    for n_sub in sub_counts:
        for n_scale in scale_opts:
            body = ["substitute_ingredient"] * n_sub + ["scale_recipe"] * n_scale
            for order in set(permutations(body)):
                seqs.add(tuple(["search_recipes"] + list(order)))
    return sorted(seqs)


# Two cases replace redundant simple-scale requests so the eval can actually
# expose the headline failure: an allergen the recipe never had. The correct
# answer ("already free") is reachable WITHOUT checking, so an agent that
# skips substitute_ingredient still passes the outcome eval - which is
# exactly the time bomb this week is hunting.
PROBE_CASES = [
    {"id": 3, "request": "Make the idli batter recipe nut-free",
     "recipe_id": "idli-batter-01", "factor": 1.0, "banned": ["nuts"],
     "class": "already-compliant"},
    {"id": 4, "request": "Make the ragi koozh recipe dairy-free",
     "recipe_id": "ragi-koozh-05", "factor": 1.0, "banned": ["dairy"],
     "class": "already-compliant"},
]


def main():
    src = [json.loads(l) for l in
           (ROOT / "w7_requests.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    probes = {c["id"]: c for c in PROBE_CASES}
    src = [probes.get(c["id"], c) for c in src]
    out = []
    for c in src:
        n_banned = len(c["banned"])
        needs_scale = c["factor"] != 1.0
        seqs = valid_sequences(n_banned, c["factor"])
        required = ["search_recipes"]
        if n_banned:
            required.append("substitute_ingredient")
        if needs_scale:
            required.append("scale_recipe")
        allowed = sorted({t for s in seqs for t in s})
        out.append({
            "id": c["id"], "request": c["request"], "class": c["class"],
            "recipe_id": c["recipe_id"], "factor": c["factor"], "banned": c["banned"],
            "required_tools": required,
            # allowed = every tool appearing in ANY accepted sequence. A tool
            # here but not in required_tools is OPTIONAL (e.g. scale_recipe on
            # a factor-1.0 request): calling it is wasteful, not wrong.
            "allowed_tools": allowed,
            # ACHIEVABLE minimum: 1 search + one substitute call per banned
            # allergen (the tool takes a single allergen enum, so N allergens
            # genuinely need N calls) + 1 scale only if the factor changes.
            # len(required_tools) was the earlier, unachievable denominator.
            "steps_needed": 1 + n_banned + (1 if needs_scale else 0),
            "valid_sequences": [list(s) for s in seqs],
            "alternate_paths": len(seqs) > 1,
        })
    path = ROOT / "w8_cases.jsonl"
    path.write_text("\n".join(json.dumps(o, ensure_ascii=False) for o in out) + "\n",
                    encoding="utf-8")
    multi = sum(1 for o in out if o["alternate_paths"])
    print(f"wrote {len(out)} cases to {path.name}; "
          f"{multi} accept more than one valid path")
    for o in out:
        print(f"  #{o['id']:<2} needs {o['steps_needed']} steps, "
              f"{len(o['valid_sequences'])} valid sequence(s): "
              f"{' | '.join('>'.join(s) for s in o['valid_sequences'][:2])}"
              f"{' | ...' if len(o['valid_sequences']) > 2 else ''}")


if __name__ == "__main__":
    main()
