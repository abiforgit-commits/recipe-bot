"""Step 3: hit-in-top-5 for both chunking strategies over the 8 frozen questions.

Search-only - no LLM, no API key. Produces:
  - per-question record printed to console (the rubric forbids summary-only claims)
  - the two numbers: X/8 (naive) vs Y/8 (structure)
  - results/search_dump.md: full top-5 lists for all 8 questions under both
    strategies (a required submission artifact)

Hit criterion (frozen in questions.md BEFORE this script ran):
  some top-5 chunk has metadata recipe_id == expected AND contains the
  answer substring.
"""
import json
import sys
from pathlib import Path

import chromadb

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent
DB_DIR = str(ROOT / "chroma_db")
K = 5
STRATEGIES = ["naive", "structure"]


def run_strategy(collection, questions):
    """Return per-question results: hit yes/no, rank of first hit, top-5 list."""
    records = []
    for q in questions:
        res = collection.query(query_texts=[q["question"]], n_results=K)
        top5 = list(zip(res["ids"][0], res["documents"][0],
                        res["metadatas"][0], res["distances"][0]))
        hit_rank = None
        for rank, (cid, doc, meta, dist) in enumerate(top5, 1):
            if meta["recipe_id"] == q["expected_recipe_id"] and q["answer_substring"] in doc:
                hit_rank = rank
                break
        records.append({"q": q, "hit_rank": hit_rank, "top5": top5})
    return records


def main():
    questions = json.loads((ROOT / "questions.json").read_text(encoding="utf-8"))
    client = chromadb.PersistentClient(path=DB_DIR)

    all_records = {}
    for strategy in STRATEGIES:
        col = client.get_collection(f"recipes_{strategy}")
        all_records[strategy] = run_strategy(col, questions)

    # ---- per-question table ----
    print(f"\nhit-in-top-{K}, per question (rank of first correct chunk, '-' = miss)\n")
    print(f"{'Q#':<4}{'type':<14}{'naive':<10}{'structure':<10}")
    for i, q in enumerate(questions):
        cells = []
        for s in STRATEGIES:
            r = all_records[s][i]["hit_rank"]
            cells.append(f"hit @{r}" if r else "MISS")
        print(f"{q['id']:<4}{q['type']:<14}{cells[0]:<10}{cells[1]:<10}")

    # ---- the two numbers ----
    print()
    for s in STRATEGIES:
        hits = sum(1 for r in all_records[s] if r["hit_rank"])
        at1 = sum(1 for r in all_records[s] if r["hit_rank"] == 1)
        print(f"{s:>10}: {hits}/8 hit-in-top-{K}   ({at1}/8 already at rank 1)")

    # ---- full dump for the submission ----
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    lines = [f"# Search-only dump: 8 questions x 2 strategies (top-{K})\n"]
    for s in STRATEGIES:
        lines.append(f"\n## Strategy: {s}\n")
        for rec in all_records[s]:
            q = rec["q"]
            verdict = f"HIT at rank {rec['hit_rank']}" if rec["hit_rank"] else "MISS"
            lines.append(f"\n### Q{q['id']}: {q['question']}")
            lines.append(f"expected: {q['expected_recipe_id']} / {q['expected_section']}"
                         f" - **{verdict}**\n")
            for rank, (cid, doc, meta, dist) in enumerate(rec["top5"], 1):
                flat = " ".join(doc.split())
                text = flat[:400] + ("..." if len(flat) > 400 else "")
                lines.append(f"{rank}. `{cid}` sim={1 - dist:.3f} recipe={meta['recipe_id']}")
                lines.append(f"   > {text}\n")
    dump = out / "search_dump.md"
    dump.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nFull dump written to {dump}")


if __name__ == "__main__":
    main()
