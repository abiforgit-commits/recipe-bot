"""Week 4 inspection view: question | top-3 retrieved | final answer, side by side.

Usage:
    python w4_inspect.py 4 5 10 11        (question ids from golden_set.jsonl)

This is the debugging tool the R/G/Not-In-Corpus labels come from:
  R  = correct chunk absent from top-3 (retrieval fetched bad context)
  G  = correct chunk present but the answer still wrong (model misused it)
  NIC = the corpus never contained the answer
"""
import json
import sys
from pathlib import Path

from ask import LLM, SYSTEM_PROMPT, DEFAULT_MODEL
from w4_retriever import dense_top

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent
K = 3


def generate(question, chunks):
    context = "\n\n".join(f"[{cid}]\n{doc}" for cid, doc, _ in chunks)
    resp = LLM.chat.completions.create(
        model=DEFAULT_MODEL, temperature=0,
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": f"Context chunks:\n\n{context}\n\nQuestion: {question}"}])
    return resp.choices[0].message.content.strip()


def main():
    want = {int(a) for a in sys.argv[1:]}
    questions = [json.loads(line) for line in
                 (ROOT / "golden_set.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    lines = ["# Week 4 inspection view (misses)\n"]
    for q in questions:
        if want and q["id"] not in want:
            continue
        top = dense_top(q["question"], k=K)
        answer = generate(q["question"], top)
        in_top = any(cid == q["expected_chunk_id"] for cid, _, _ in top)
        print(f"\n{'='*70}\nQ{q['id']}: {q['question']}")
        lines.append(f"\n## Q{q['id']}: {q['question']}\n")
        lines.append(f"Expected chunk: `{q['expected_chunk_id']}` — in top-{K}: **{in_top}**\n")
        print(f"expected: {q['expected_chunk_id']}   in top-{K}: {in_top}")
        for i, (cid, doc, score) in enumerate(top, 1):
            flat = " ".join(doc.split())[:180]
            print(f"  {i}. [{score:.3f}] {cid}\n     {flat[:110]}...")
            lines.append(f"{i}. `{cid}` score={score:.3f}\n   > {flat}...\n")
        print(f"  ANSWER: {answer}")
        lines.append(f"**Final answer:** {answer}\n")
    out = ROOT / "results" / "w4_inspection.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
