"""Week 11: the production recipe assistant, instrumented so every request can be found.

    python w11_app.py "Make the thayir curd recipe dairy-free" --version p-v2

One request = three spans, each with its own latency, tokens and cost:

    retrieval   hybrid search over the recipe chunks (local - no API cost)
    tools       MCP calls to the recipe server: substitute / scale (local - no API cost)
    generation  ONE model call over the chunks + tool results (the only paid stage)

This is a workflow, not an agent: the steps are fixed and only generation uses the
model - the Week 7 verdict. Every request is appended to logs/w11_requests.jsonl
with both its input AND its output indexed, plus prompt version, user, input type
and the retrieved context ids, so a vague complaint can be traced back to one line.
"""
import argparse
import asyncio
import json
import re
import sys
import time
import uuid
from contextlib import AsyncExitStack
from datetime import datetime, timezone
from pathlib import Path

from ask import DEFAULT_MODEL, call_llm
from w4_retriever import _DOC_BY_ID, hybrid_top
from w9_agent import PRICE_IN, PRICE_OUT, connect_all, result_text

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent
LOG = ROOT / "logs" / "w11_requests.jsonl"
CONFIG = (ROOT / "mcp_config.json").resolve()
K = 5

# Throttle accounting: ask.call_llm sleeps for free-tier pacing and 429 backoff.
# Counting those sleeps lets the generation span report model time separately.
_SLEPT = [0.0]
_real_sleep = time.sleep


def _counting_sleep(seconds):
    _SLEPT[0] += max(0.0, seconds)
    _real_sleep(seconds)


time.sleep = _counting_sleep

PROMPTS = {
    # Mon 28 Sep - Wed 30 Sep: the grounded prompt carried over from Weeks 3-6.
    "p-v1": """You are a recipe assistant. Answer using ONLY the context chunks and tool
results provided below.
Rules:
1. Cite the chunk id or tool name in square brackets for every factual claim.
2. If they do not contain the answer, reply exactly: "I cannot find this in the recipe cards."
3. Never use outside knowledge.""",

    # Thu 1 Oct onwards: shipped to cut the over-refusal Week 5 found (15% of traffic).
    "p-v2": """You are a friendly recipe assistant for home cooks. Use the context chunks and
tool results provided as your main source, and cite them in square brackets.
Be helpful: if they only partly answer the question, give the most useful answer you
can, filling small gaps with general cooking knowledge, and suggest practical
alternatives the cook could use. Only say you cannot help if the question has nothing
to do with these recipes.""",
}

# p-v3 = p-v2 + ONE rule (Week 11 fix for trace e6fa2dbb1746). Nothing else changed, so
# any movement in the suite is attributable to this rule alone.
PROMPTS["p-v3"] = PROMPTS["p-v2"] + """

Dairy rule: milk, curd, buttermilk (mor), ghee, butter, paneer, cream and yoghurt are dairy,
and so is anything made with them, such as curd chilli (mor milagai). When the user wants
dairy-free or vegan food, never recommend any of these, including as sides or serving
suggestions. If a recipe card suggests one, say it contains dairy and leave it out.
Plant milks and plant yoghurts (coconut, soy, oat, cashew, almond) are not dairy."""

# p-v4 = p-v2 again for every request, plus a dairy note attached ONLY when the rule-based
# detector has flagged the request as dairy-free. p-v3 put the rule in every prompt: it
# leaked a dairy note into "How much salt?" (c01), and its plant-yoghurt examples were
# echoed back as outside knowledge. Scoping the note to dairy requests prevents the first;
# dropping the examples and forbidding invented replacements prevents the second.
PROMPTS["p-v4"] = PROMPTS["p-v2"]
CONDITIONAL_NOTES = {
    "p-v4": {"dairy": """

This request is dairy-free. Curd, buttermilk, mor, ghee, butter, paneer, cream, yoghurt
and milk are dairy, and so is anything made with them, including curd chilli (mor
milagai). Do not recommend any of them, including as sides or serving suggestions. If a
chunk suggests one, say it contains dairy and leave it out. Only suggest replacements
that appear in the chunks or tool results. Do not cite this note."""},
}

# p-v5 = the fix moves to the RETRIEVAL layer. p-v4 gave the right answer, but the judge
# failed it: "curd chilli contains dairy" was a fact the model could not cite, and the
# card itself says "Vegan ... as written". In a grounded app every fact needs a source,
# so the dairy facts now live in a knowledge chunk (knowledge/allergen_notes.md) that is
# pinned into the context when the detector bans that allergen. The prompt keeps only
# the instruction.
PROMPTS["p-v5"] = PROMPTS["p-v2"]
CONDITIONAL_NOTES["p-v5"] = {"dairy": """

This request is dairy-free. The allergen note chunk says what counts as dairy. Check
every ingredient, side and serving suggestion against it. Do not recommend anything it
lists as dairy; if a recipe chunk suggests one, say it contains dairy, cite the allergen
note, and leave it out. Only suggest replacements that appear in the chunks or tool
results."""}
PIN_ALLERGEN_NOTES = {"p-v5"}  # versions whose retrieval pins the allergen notes


def _load_notes():
    """{allergen: (chunk_id, text)}, one '## <allergen>' section per allergen."""
    notes = {}
    for section in (ROOT / "knowledge" / "allergen_notes.md").read_text(encoding="utf-8").split("\n## ")[1:]:
        allergen, body = section.split("\n", 1)
        allergen = allergen.strip()
        notes[allergen] = (f"allergen-notes::{allergen}::0",
                           f"# Allergen notes: {allergen}\n\n{body.strip()}")
    return notes


ALLERGEN_NOTES = _load_notes()
_NOTE_BY_ID = dict(ALLERGEN_NOTES.values())


def chunk_text(cid):
    """Text of any context id: a recipe chunk from the index, or a pinned allergen note."""
    return _DOC_BY_ID.get(cid) or _NOTE_BY_ID.get(cid, "")

ALLERGEN_PATTERNS = {
    "dairy": r"\b(dairy|milk|lactose)[- ]?free\b|\bno dairy\b|\bwithout dairy\b|\bvegan\b",
    "nuts": r"\bnut[- ]?free\b|\bno nuts\b|\bwithout nuts\b",
    "sesame": r"\bsesame[- ]?free\b|\bwithout sesame\b",
    "gluten": r"\bgluten[- ]?free\b|\bwithout gluten\b",
    "coconut": r"\bcoconut[- ]?free\b|\bwithout coconut\b",
    "soy": r"\bsoy[- ]?free\b",
    "mustard": r"\bmustard[- ]?free\b",
}
FACTOR_WORDS = {r"\bhalve\b|\bhalf\b": 0.5, r"\bdouble\b|\btwice\b": 2.0,
                r"\btriple\b|\bthree times\b": 3.0, r"\bone and a half\b": 1.5}


def detect(query):
    """Rule-based intent detection - no model call."""
    q = query.lower()
    banned = [a for a, pat in ALLERGEN_PATTERNS.items() if re.search(pat, q)]
    factor = None
    for pat, f in FACTOR_WORDS.items():
        if re.search(pat, q):
            factor = f
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:x\b|times)", q)
    if m and factor is None:
        factor = float(m.group(1))
    if banned:
        kind = "substitution"
    elif factor:
        kind = "scaling"
    elif re.search(r"\bis there\b|\bcontain|\ballerg|\bsafe for\b|\bdoes .* (use|have)\b", q):
        kind = "allergen_check"
    elif re.search(r"\bcalorie|\bprotein\b|\bnutrition|\bfat\b", q):
        kind = "nutrition"
    else:
        kind = "question"
    return {"input_type": kind, "banned": banned, "factor": factor}


class RecipeApp:
    """Holds the MCP sessions open across requests, like a running service would."""

    async def __aenter__(self):
        self._stack = AsyncExitStack()
        await self._stack.__aenter__()
        self.sessions, self.catalogue = await connect_all(CONFIG, self._stack)
        return self

    async def __aexit__(self, *exc):
        await self._stack.__aexit__(*exc)

    async def answer(self, query, user_id="u000", prompt_version="p-v2", ts=None, log=True):
        t_req = time.perf_counter()
        det = detect(query)
        spans = []

        # ---- span 1: retrieval (local) ----
        t0 = time.perf_counter()
        top = hybrid_top(query, k=K)
        pinned = [ALLERGEN_NOTES[a] for a in det["banned"]
                  if prompt_version in PIN_ALLERGEN_NOTES and a in ALLERGEN_NOTES]
        chunks = pinned + [(cid, doc) for cid, doc, _ in top]
        spans.append({"name": "retrieval", "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                      "context_ids": [cid for cid, _ in chunks],
                      "pinned_ids": [cid for cid, _ in pinned],
                      "scores": [None] * len(pinned) + [round(s, 4) for _, _, s in top],
                      "tokens": 0, "cost_usd": 0.0})
        recipe_id = top[0][0].split("::")[0] if top else None

        # ---- span 2: tools over MCP (local) ----
        t0 = time.perf_counter()
        calls = []
        plan = [("substitute_ingredient", {"recipe_id": recipe_id, "allergen": a}) for a in det["banned"]]
        if det["factor"] and det["factor"] != 1.0:
            plan.append(("scale_recipe", {"recipe_id": recipe_id, "factor": det["factor"]}))
        for tool, args in plan:
            res = await self.sessions["recipes"].call_tool(tool, args)
            calls.append({"tool": f"recipes.{tool}", "args": args,
                          "is_error": bool(getattr(res, "is_error", False)),
                          "result": result_text(res)})
        spans.append({"name": "tools", "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                      "calls": calls, "tokens": 0, "cost_usd": 0.0})

        # ---- span 3: generation (the only paid stage) ----
        context = "\n\n".join(f"[{cid}]\n{doc}" for cid, doc in chunks)
        tools_txt = "\n\n".join(f"[{c['tool']}] {json.dumps(c['args'])}\n{c['result']}"
                                for c in calls) or "(no tools were needed)"
        system = PROMPTS[prompt_version] + "".join(
            note for allergen, note in CONDITIONAL_NOTES.get(prompt_version, {}).items()
            if allergen in det["banned"])
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": f"Context chunks:\n\n{context}\n\n"
                                                f"Tool results:\n\n{tools_txt}\n\nQuestion: {query}"}]
        slept0, t0 = _SLEPT[0], time.perf_counter()
        resp = call_llm(model=DEFAULT_MODEL, temperature=0, messages=messages)
        wall = time.perf_counter() - t0
        waited = _SLEPT[0] - slept0
        u = resp.usage
        gen_cost = (u.prompt_tokens * PRICE_IN + u.completion_tokens * PRICE_OUT) / 1_000_000
        spans.append({"name": "generation", "latency_ms": round(wall * 1000, 1),
                      "throttle_wait_ms": round(waited * 1000, 1), "model": DEFAULT_MODEL,
                      "prompt_tokens": u.prompt_tokens, "completion_tokens": u.completion_tokens,
                      "tokens": u.prompt_tokens + u.completion_tokens,
                      "cost_usd": round(gen_cost, 8)})
        output = (resp.choices[0].message.content or "").strip()

        record = {
            "trace_id": uuid.uuid4().hex[:12],
            "ts": ts or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "user_id": user_id,
            "prompt_version": prompt_version,
            "input_type": det["input_type"],
            "query": query,
            "detected": {"recipe_id": recipe_id, "banned": det["banned"], "factor": det["factor"]},
            "spans": spans,
            "output": output,
            "latency_ms_total": round((time.perf_counter() - t_req) * 1000, 1),
            "tokens_total": sum(s["tokens"] for s in spans),
            "cost_usd_total": round(sum(s["cost_usd"] for s in spans), 8),
            "status": "ok",
        }
        if log:
            LOG.parent.mkdir(exist_ok=True)
            with LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record


async def _main(query, version, log):
    async with RecipeApp() as app:
        r = await app.answer(query, prompt_version=version, log=log)
    for s in r["spans"]:
        extra = (f"tokens={s['tokens']}" if s["name"] == "generation"
                 else f"ids={s.get('context_ids', [c['tool'] for c in s.get('calls', [])])}")
        print(f"  {s['name']:<10} {s['latency_ms']:>8} ms  ${s['cost_usd']:.8f}  {extra}")
    print(f"\n[{r['prompt_version']}] {r['input_type']}  {r['detected']}\n\n{r['output']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--version", default="p-v2", choices=list(PROMPTS))
    ap.add_argument("--log", action="store_true", help="append to the production log")
    a = ap.parse_args()
    asyncio.run(_main(a.query, a.version, a.log))
