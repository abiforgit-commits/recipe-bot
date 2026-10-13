"""Capstone: one trace id across the agent hop and the MCP hop, and the PII line.

The host makes a trace id per question and sends it on every MCP tools/call in
the request's `_meta`. The server reads it and writes its own span with the same
id, so `python pantry.py trace <id>` can show question -> model calls -> tool
calls -> server work -> answer as one record.

The PII line: a user's stated allergies are health data. What gets written:
  - user id: pseudonymised (salted SHA-256, 12 hex chars), never the raw id
  - question/answer text: kept, because Week 11 showed the output is what you
    search when a complaint comes in, but any sentence fragment stating a health
    condition ("my son is allergic to nuts") is replaced by [health detail removed]
  - constraints: the allergen CLASSES the system acted on (e.g. ["nuts"]), kept as a
    structured field, because without it an allergen near-miss can't be found
    (that was Week 11's missing field)
  - server logs: tool name, arguments (redacted the same way) and timings. No user
    id ever reaches the server.
"""
import hashlib
import json
import os
import re
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).parent
LOG_DIR = ROOT / "logs"
CLIENT_LOG = LOG_DIR / "pantry_requests.jsonl"
SERVER_LOG = LOG_DIR / "pantry_mcp_spans.jsonl"

HEALTH = r"(?:allergic|allergy|allergies|intolerant|intolerance|coeliac|celiac|anaphyla\w*|epipen)"
_REDACT = [
    # "my kid is (severely) allergic to nuts", "she's lactose intolerant"
    re.compile(r"\b(?:my|our|your|his|her|their|i'?m|i am|you'?re|you are|we'?re|we are|he'?s|she'?s|"
               r"they'?re|he is|she is|"
               r"they are|i have|we have)\b[^.?!;,]{0,40}?\b" + HEALTH + r"\b(?:\s+to\s+[a-z ,-]{1,40}?"
               r"(?=\s+(?:and|but|so|-|—)\s|[.?!;,]|$))?", re.I),
    # "for a child with a (severe) nut allergy"
    re.compile(r"\bwith\s+(?:a|an)\s+(?:severe\s+|mild\s+)?[a-z-]{0,20}\s*" + HEALTH + r"\b", re.I),
]


def redact(text):
    if not text:
        return text
    for pattern in _REDACT:
        text = pattern.sub("[health detail removed]", text)
    return text


def pseudonym(user):
    salt = os.getenv("PANTRY_LOG_SALT", "pantry-dev-salt")  # set a real secret in production
    return hashlib.sha256(f"{salt}:{user}".encode()).hexdigest()[:12]


def append(path, record):
    LOG_DIR.mkdir(exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _meta_value(meta, key):
    if meta is None:
        return None
    if isinstance(meta, dict):
        return meta.get(key)
    return getattr(meta, key, None) or (getattr(meta, "model_extra", None) or {}).get(key)


@contextmanager
def server_span(ctx, server, tool, args):
    """Server side of a tools/call: time it and log it under the caller's trace id."""
    meta = getattr(getattr(ctx, "request_context", None), "meta", None)
    span = {"trace_id": _meta_value(meta, "trace_id") or "untraced",
            "parent_span_id": _meta_value(meta, "span_id"), "server": server,
            "span": f"mcp.server/{tool}", "tool": tool,
            "args": json.loads(redact(json.dumps(args, ensure_ascii=False))),
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "is_error": False}
    t0 = time.perf_counter()
    try:
        yield span
    except Exception as e:
        span["is_error"] = True
        span["error"] = str(e)[:300]
        raise
    finally:
        span["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        span["cost_usd"] = 0.0  # servers never call a model
        append(SERVER_LOG, span)


def load(path):
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def merged_trace(trace_id):
    """The client record for one question with the server's spans attached."""
    rec = next((r for r in load(CLIENT_LOG) if r["trace_id"].startswith(trace_id)), None)
    if rec is None:
        return None
    rec["server_spans"] = [s for s in load(SERVER_LOG) if s["trace_id"] == rec["trace_id"]]
    return rec
