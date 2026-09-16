"""Week 6: LLM-as-judge runner - one binary criterion (SAFE_AND_GROUNDED).

The judge sees question + context + answer and returns PASS/FAIL. Which
prompt file to use is a parameter, so v1 and v2 run identically:

    from w6_judge import judge_case
    verdict, reason = judge_case("judge_v1.txt", case, output, context_text)
"""
import re
from pathlib import Path

from ask import call_llm, DEFAULT_MODEL

ROOT = Path(__file__).parent
VERDICT_RE = re.compile(r"VERDICT:\s*(PASS|FAIL)", re.IGNORECASE)


def judge_case(prompt_file, case, output, context_text):
    """Returns ('PASS'|'FAIL', reason_line). Retries once on missing verdict."""
    system = (ROOT / prompt_file).read_text(encoding="utf-8")
    user = (f"QUESTION:\n{case['question']}\n\n"
            f"CONTEXT CHUNKS SHOWN TO THE ASSISTANT:\n{context_text}\n\n"
            f"ASSISTANT'S ANSWER:\n{output}")
    for _ in range(2):
        resp = call_llm(
            model=DEFAULT_MODEL, temperature=0,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}])
        text = resp.choices[0].message.content.strip()
        m = VERDICT_RE.search(text)
        if m:
            reason = text[m.end():].strip().splitlines()
            return m.group(1).upper(), (reason[0] if reason else "")
    return "FAIL", "judge returned no parseable verdict"
