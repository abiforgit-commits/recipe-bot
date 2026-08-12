"""Search the indexed recipe chunks (retrieval only - no LLM, no API key).

Usage:
    python search.py "How much salt goes into the 2kg idli batter?"
    python search.py "..." --strategy structure
    python search.py "..." --tag gluten-free          (metadata filter)
    python search.py "..." --k 3
"""
import argparse
import sys
from pathlib import Path

import chromadb

sys.stdout.reconfigure(encoding="utf-8")

DB_DIR = str(Path(__file__).parent / "chroma_db")


def search(question, strategy="naive", k=5, tag=None):
    client = chromadb.PersistentClient(path=DB_DIR)
    collection = client.get_collection(f"recipes_{strategy}")

    where = None
    if tag:
        where = {"tag_" + tag.replace("-", "_"): True}

    return collection.query(query_texts=[question], n_results=k, where=where)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--strategy", choices=["naive", "structure"], default="naive")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--tag", help="dietary tag filter, e.g. gluten-free")
    args = parser.parse_args()

    res = search(args.question, args.strategy, args.k, args.tag)

    print(f"\nQ: {args.question}")
    print(f"strategy={args.strategy}  k={args.k}  filter={args.tag or 'none'}\n")
    rows = zip(res["ids"][0], res["documents"][0],
               res["metadatas"][0], res["distances"][0])
    for rank, (chunk_id, doc, meta, dist) in enumerate(rows, 1):
        similarity = 1 - dist  # cosine: 1.0 = identical meaning, 0 = unrelated
        preview = " ".join(doc.split())[:110]
        print(f"{rank}. [{similarity:.3f}] {chunk_id}")
        print(f"   recipe={meta['recipe_id']}  tags={meta['dietary_tags']}")
        print(f"   \"{preview}...\"\n")


if __name__ == "__main__":
    main()
