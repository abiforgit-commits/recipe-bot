"""Capstone: re-measure the Week 4 retriever's hit-rate on the integrated CMS index.

    python pantry_hitrate.py

The brief: "The Week-4 retriever with a measured hit-rate ships." The retriever is
unchanged, but the corpus is not (11 versions instead of 6 cards, two of them
duplicate pages), so the Week 4 number has to be measured again, not assumed.

Same 12 frozen questions (golden_set.jsonl), same metric (hit-rate@3). Week 4 ids
are mapped to the versioned ids. For the two-version recipe (kadumanga), either
version's chunk counts as a hit, and we also report how often the SUPERSEDED page
outranks the current one. Search only: no model, no API key.
"""
import json
import sys
from pathlib import Path

import pantry_corpus as pc

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent
K = 3


def main():
    golden = [json.loads(l) for l in (ROOT / "golden_set.jsonl").read_text(encoding="utf-8").splitlines() if l]
    hits, superseded_first, rows = 0, 0, []
    for g in golden:
        rid, _, n = g["expected_chunk_id"].split("::")
        targets = [f"{rid}@{v}::structure::{n}" for v in pc.VERSIONS[rid]]
        top = [h["chunk_id"] for h in pc.search(g["question"], k=K)]
        rank = next((i for i, c in enumerate(top, 1) if c in targets), None)
        hits += rank is not None
        sup = rank is not None and top[rank - 1] in pc.SUPERSEDED_CHUNKS
        superseded_first += sup
        rows.append({"id": g["id"], "question": g["question"], "targets": targets, "top3": top,
                     "hit_rank": rank, "superseded_ranked_first": sup})
        print(f"Q{g['id']:<3}{'hit @' + str(rank) if rank else 'MISS':<8}"
              f"{'(superseded page first)' if sup else '':<25}{g['question'][:60]}")
    print(f"\nhit-rate@{K} on the CMS index: {hits}/{len(golden)}   (Week 4 on the 6 cards: 11/12)")
    print(f"questions where the superseded page was the first hit: {superseded_first}")
    (ROOT / "results" / "pantry_hitrate.json").write_text(json.dumps(
        {"k": K, "hits": hits, "n": len(golden), "week4_hybrid": "11/12",
         "superseded_first": superseded_first, "rows": rows}, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
