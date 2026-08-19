"""Week 4: hit-rate@3 + p50 retrieval latency over the 12-question golden set.

Usage:
    python w4_eval.py --retriever dense

Hit criterion: the tagged expected_chunk_id appears among the top-3 ids.
Latency: retrieval time only (embed + search), measured per query after one
warm-up call so model loading does not pollute the numbers; p50 = median.
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

from w4_retriever import RETRIEVERS

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent
K = 3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--retriever", choices=list(RETRIEVERS), required=True)
    args = parser.parse_args()
    retrieve = RETRIEVERS[args.retriever]

    questions = [json.loads(line) for line in
                 (ROOT / "golden_set.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]

    retrieve("warm-up query", k=K)  # load the embedding model before timing

    records = []
    for q in questions:
        t0 = time.perf_counter()
        top = retrieve(q["question"], k=K)
        ms = (time.perf_counter() - t0) * 1000
        ids = [cid for cid, _, _ in top]
        rank = ids.index(q["expected_chunk_id"]) + 1 if q["expected_chunk_id"] in ids else None
        records.append({"q": q, "top": top, "rank": rank, "ms": ms})

    print(f"\nhit-rate@{K} - retriever: {args.retriever}\n")
    print(f"{'Q#':<4}{'kind':<13}{'result':<10}{'ms':>7}   expected")
    for r in records:
        verdict = f"hit @{r['rank']}" if r["rank"] else "MISS"
        print(f"{r['q']['id']:<4}{r['q']['kind']:<13}{verdict:<10}{r['ms']:>7.1f}   {r['q']['expected_chunk_id']}")

    hits = sum(1 for r in records if r["rank"])
    p50 = statistics.median(r["ms"] for r in records)
    print(f"\n  hit-rate@{K}: {hits}/12   p50 latency: {p50:.1f} ms")

    out = ROOT / "results" / f"w4_run_{args.retriever}.md"
    lines = [f"# Week 4 run - retriever: {args.retriever} (top-{K})\n",
             f"hit-rate@{K}: **{hits}/12**   p50 latency: **{p50:.1f} ms**\n"]
    for r in records:
        verdict = f"HIT at rank {r['rank']}" if r["rank"] else "MISS"
        lines.append(f"\n## Q{r['q']['id']}: {r['q']['question']}")
        lines.append(f"expected `{r['q']['expected_chunk_id']}` - **{verdict}** ({r['ms']:.1f} ms)\n")
        for i, (cid, doc, score) in enumerate(r["top"], 1):
            flat = " ".join(doc.split())[:220]
            lines.append(f"{i}. `{cid}` score={score:.3f}")
            lines.append(f"   > {flat}...\n")
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"  full dump: {out}")


if __name__ == "__main__":
    main()
