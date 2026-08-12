"""Run the 3 answerable + 3 out-of-corpus questions through grounded
generation and save verbatim transcripts (a required submission artifact).
"""
import sys
from pathlib import Path

from ask import ask, verify_citations, REFUSAL

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent

ANSWERABLE = [
    "How much rock salt goes into the 2kg batch of idli batter?",
    "To what temperature should the milk be cooled before adding the curd starter?",
    "Why might kadumanga achar not be suitable for a gluten-free diet?",
]

OUT_OF_CORPUS = [  # nothing on any card answers these - must be refused
    "How many calories are in one idli?",
    "How much protein does the dosa batter contain per 100g?",
    "How long does idli batter keep in the refrigerator?",
]

lines = ["# Generation transcripts: 3 cited answers + 3 forced refusals\n",
         "Strategy: structure-aware index, top-5 retrieval, temperature 0.\n"]

print("=== Answerable (must cite) ===")
lines.append("\n## Answerable questions (citation required)\n")
for q in ANSWERABLE:
    answer, chunks = ask(q)
    checks = verify_citations(answer)
    print(f"\nQ: {q}\nA: {answer}")
    lines.append(f"\n### Q: {q}\n")
    lines.append(f"Retrieved chunk_ids: {', '.join(cid for cid, _ in chunks)}\n")
    lines.append(f"**A:** {answer}\n")
    for cid, ok in checks:
        status = "resolves to a real chunk" if ok else "BROKEN"
        line = f"- citation `{cid}`: {status}"
        print(f"   {line}")
        lines.append(line)

print("\n=== Out of corpus (must refuse) ===")
lines.append("\n## Out-of-corpus questions (refusal required)\n")
refused = 0
for q in OUT_OF_CORPUS:
    answer, chunks = ask(q)
    ok = answer.strip().strip('"') == REFUSAL.strip('"')
    refused += ok
    verdict = "REFUSED correctly" if ok else "!!! DID NOT REFUSE !!!"
    print(f"\nQ: {q}\nA: {answer}\n   -> {verdict}")
    lines.append(f"\n### Q: {q}\n")
    lines.append(f"Retrieved chunk_ids: {', '.join(cid for cid, _ in chunks)}\n")
    lines.append(f"**A:** {answer}\n")
    lines.append(f"Verdict: {verdict}")

print(f"\n{refused}/3 out-of-corpus questions refused.")
out = ROOT / "results" / "generation_transcripts.md"
out.write_text("\n".join(lines), encoding="utf-8")
print(f"Transcripts saved to {out}")
