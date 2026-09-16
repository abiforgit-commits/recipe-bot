"""Week 5: traced question-answering + replay.

Every call to traced_ask() appends one complete, replayable record to
traces.jsonl. A trace stores everything needed to reproduce the answer from
the trace alone: prompt version, retriever + k, retrieved chunk_ids WITH
scores AND full texts, model + params, and the raw output.

The app being traced is the Week 4 shipping configuration: hybrid retrieval
(dense + BM25, RRF k=60) feeding the grounded, forced-refusal prompt.

Replay:
    python w5_trace.py replay <trace_id>
"""
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ask import call_llm, SYSTEM_PROMPT, DEFAULT_MODEL
from w4_retriever import hybrid_top

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent
TRACES = ROOT / "traces.jsonl"

PROMPT_VERSION = "v1-grounded-forced-refusal"
RETRIEVER = "hybrid-rrf60"
K = 5
TEMPERATURE = 0


def _build_messages(question, chunks):
    context = "\n\n".join(f"[{cid}]\n{doc}" for cid, doc in chunks)
    return [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",
             "content": f"Context chunks:\n\n{context}\n\nQuestion: {question}"}]


def traced_ask(question):
    """Answer a question and append a complete trace record."""
    top = hybrid_top(question, k=K)
    chunks = [(cid, doc) for cid, doc, _ in top]
    resp = call_llm(
        model=DEFAULT_MODEL, temperature=TEMPERATURE,
        messages=_build_messages(question, chunks))
    output = resp.choices[0].message.content.strip()

    record = {
        "trace_id": uuid.uuid4().hex[:8],
        "ts": datetime.now(timezone.utc).isoformat(),
        "prompt_version": PROMPT_VERSION,
        "retriever": RETRIEVER,
        "k": K,
        "model": DEFAULT_MODEL,
        "temperature": TEMPERATURE,
        "question": question,
        "retrieved": [{"chunk_id": cid, "score": round(score, 4), "text": doc}
                      for cid, doc, score in top],
        "output": output,
    }
    with TRACES.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def load_traces():
    return [json.loads(line) for line in
            TRACES.read_text(encoding="utf-8").splitlines() if line.strip()]


def replay(trace_id):
    """Re-run one request using ONLY what the trace stored (no fresh retrieval)."""
    trace = next(t for t in load_traces() if t["trace_id"] == trace_id)
    chunks = [(r["chunk_id"], r["text"]) for r in trace["retrieved"]]
    resp = call_llm(
        model=trace["model"], temperature=trace["temperature"],
        messages=_build_messages(trace["question"], chunks))
    replayed = resp.choices[0].message.content.strip()

    print(f"trace_id: {trace_id}   prompt_version: {trace['prompt_version']}")
    print(f"model: {trace['model']}  temp: {trace['temperature']}  retriever: {trace['retriever']} k={trace['k']}")
    print(f"\nQ: {trace['question']}")
    print(f"\n--- ORIGINAL output ({trace['ts']}) ---\n{trace['output']}")
    print(f"\n--- REPLAYED output (now) ---\n{replayed}")
    print(f"\nIdentical: {replayed == trace['output']}")
    return trace["output"], replayed


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "replay":
        replay(sys.argv[2])
    else:
        print("usage: python w5_trace.py replay <trace_id>")
