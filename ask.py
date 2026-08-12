"""Step 5: grounded generation - answer ONLY from retrieved chunks, cite every
claim, refuse when the corpus has no answer.

Usage:
    python ask.py "How much rock salt goes into the 2kg batch of idli batter?"

The refusal is FORCED, not suggested: the system prompt gives the model an
exact refusal sentence and declares an unsupported answer a failure. The task
file's warning is literal - 'use your best judgement' is how an invented gram
weight ends up in a reader's dough.
"""
import argparse
import os
import re
import sys
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from openai import OpenAI

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

# Provider auto-detect: a GEMINI_API_KEY switches us to Google's free tier
# via its OpenAI-compatible endpoint; otherwise we use OpenAI directly.
if os.getenv("GEMINI_API_KEY"):
    LLM = OpenAI(
        api_key=os.environ["GEMINI_API_KEY"],
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    DEFAULT_MODEL = "gemini-flash-latest"  # stable alias, survives model rotations
else:
    LLM = OpenAI()
    DEFAULT_MODEL = "gpt-4o-mini"

REFUSAL = "I cannot find this in the recipe cards."

SYSTEM_PROMPT = f"""You answer questions about recipe cards using ONLY the numbered context chunks provided below.

Rules - no exceptions:
1. Every factual claim must cite the chunk id it came from, in square brackets, e.g. [idli-batter-01::structure::1].
2. If the chunks do not contain the answer, reply with exactly: "{REFUSAL}" - nothing else, no partial guesses.
3. Never use knowledge from outside the chunks, even if you are sure you know the answer. An unsupported answer is a failure. The refusal sentence is a success."""


def ask(question, strategy="structure", k=5, model=None):
    """Retrieve top-k chunks, then generate a grounded, cited answer."""
    model = model or DEFAULT_MODEL
    db = chromadb.PersistentClient(path=str(ROOT / "chroma_db"))
    collection = db.get_collection(f"recipes_{strategy}")
    res = collection.query(query_texts=[question], n_results=k)
    chunks = list(zip(res["ids"][0], res["documents"][0]))

    context = "\n\n".join(f"[{cid}]\n{doc}" for cid, doc in chunks)
    response = LLM.chat.completions.create(
        model=model,
        temperature=0,  # repeatable answers - Week 1 lesson applied
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",
             "content": f"Context chunks:\n\n{context}\n\nQuestion: {question}"},
        ],
    )
    answer = response.choices[0].message.content.strip()
    return answer, chunks


def verify_citations(answer, collection_name="recipes_structure"):
    """Check every [chunk_id] cited in the answer actually exists in the index."""
    cited = re.findall(r"\[([a-z0-9-]+::[a-z]+::\d+)\]", answer)
    if not cited:
        return []
    db = chromadb.PersistentClient(path=str(ROOT / "chroma_db"))
    collection = db.get_collection(collection_name)
    found = set(collection.get(ids=list(set(cited)))["ids"])
    return [(cid, cid in found) for cid in cited]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--strategy", default="structure")
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()

    answer, chunks = ask(args.question, args.strategy, args.k)

    print(f"\nQ: {args.question}\n")
    print("retrieved:", ", ".join(cid for cid, _ in chunks))
    print(f"\nA: {answer}\n")
    for cid, ok in verify_citations(answer):
        print(f"  citation {cid}: {'resolves' if ok else 'BROKEN - no such chunk'}")


if __name__ == "__main__":
    main()
