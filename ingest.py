"""Ingest the 6 recipe cards into ChromaDB under a chosen chunking strategy.

Usage:
    python ingest.py --strategy naive
    python ingest.py --strategy structure

Each strategy gets its own collection (recipes_naive / recipes_structure),
so both indexes exist side by side and can be measured against each other.
"""
import argparse
import sys
from pathlib import Path

import chromadb

from chunkers import STRATEGIES

sys.stdout.reconfigure(encoding="utf-8")

DATA_DIR = Path(__file__).parent / "data" / "new_cards"
DB_DIR = str(Path(__file__).parent / "chroma_db")


def parse_card(path):
    """Split a card file into its frontmatter metadata and its markdown body."""
    text = path.read_text(encoding="utf-8")
    _, frontmatter, body = text.split("---", 2)
    meta = {}
    for line in frontmatter.strip().splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return {"meta": meta, "body": body.strip(), "source_file": path.name}


def build_metadata(card, chunk_index, strategy):
    """The metadata attached to every chunk - Task requirement #1.

    dietary_tags is also expanded into boolean fields (tag_vegan=True, ...)
    because Chroma filters match whole values, not substrings: you cannot
    ask 'vegan' == 'vegan, gluten-free', but you can ask tag_vegan == True.
    """
    meta = card["meta"]
    m = {
        "source_file": card["source_file"],
        "recipe_id": meta["recipe_id"],
        "title": meta["title"],
        "cuisine": meta["cuisine"],
        "dietary_tags": meta["dietary_tags"],
        "chunk_index": chunk_index,
        "strategy": strategy,
    }
    for tag in meta["dietary_tags"].split(","):
        m["tag_" + tag.strip().replace("-", "_")] = True
    return m


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", choices=list(STRATEGIES), required=True)
    args = parser.parse_args()
    chunker = STRATEGIES[args.strategy]

    client = chromadb.PersistentClient(path=DB_DIR)
    name = f"recipes_{args.strategy}"
    try:
        client.delete_collection(name)  # fresh index every run, no duplicates
    except Exception:
        pass
    collection = client.create_collection(name, metadata={"hnsw:space": "cosine"})

    total = 0
    for path in sorted(DATA_DIR.glob("*.md")):
        card = parse_card(path)
        chunks = chunker(card)
        ids = [f"{card['meta']['recipe_id']}::{args.strategy}::{i}"
               for i in range(len(chunks))]
        metadatas = [build_metadata(card, i, args.strategy)
                     for i in range(len(chunks))]

        for m in metadatas:  # "a chunk with no source_file is a failed ingest"
            assert m.get("source_file"), f"chunk missing source_file in {path}"

        collection.add(ids=ids, documents=chunks, metadatas=metadatas)
        total += len(chunks)
        print(f"  {card['source_file']:<30} -> {len(chunks)} chunks")

    print(f"\nIngested {total} chunks into '{name}' at {DB_DIR}")


if __name__ == "__main__":
    main()
