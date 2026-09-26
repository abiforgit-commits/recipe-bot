"""Week 9: capture the raw JSON-RPC exchange with the ingredient database server.

    python w9_wire_capture.py

Speaks MCP's stdio transport by hand - one JSON object per line on the
server's stdin/stdout - with no SDK client and no model anywhere, and logs
every line in both directions to results/w9_wire_raw.jsonl.

Sequence: initialize -> notifications/initialized -> tools/list -> tools/call,
plus a second tools/call on an unknown ingredient to show how a TOOL error
differs from a PROTOCOL error on the wire.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

from mcp.types import LATEST_PROTOCOL_VERSION

ROOT = Path(__file__).parent
RAW = ROOT / "results" / "w9_wire_raw.jsonl"

proc = subprocess.Popen(
    [sys.executable, "ingredient_db_server/server.py"], cwd=ROOT,
    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    stderr=open(ROOT / "results" / "w9_wire_server_stderr.log", "w"),
    text=True, encoding="utf-8", bufsize=1)
log = []


def send(message):
    line = json.dumps(message, ensure_ascii=False)
    proc.stdin.write(line + "\n")
    proc.stdin.flush()
    log.append({"t": round(time.time(), 3), "direction": "client -> server", "raw": line})
    print(f">>> {line[:150]}")


def recv():
    line = proc.stdout.readline().strip()
    log.append({"t": round(time.time(), 3), "direction": "server -> client", "raw": line})
    print(f"<<< {line[:150]}{'...' if len(line) > 150 else ''}")
    return json.loads(line)


send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
      "params": {"protocolVersion": LATEST_PROTOCOL_VERSION, "capabilities": {},
                 "clientInfo": {"name": "w9-wire-capture", "version": "1.0"}}})
recv()
send({"jsonrpc": "2.0", "method": "notifications/initialized"})
send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
recv()
send({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
      "params": {"name": "lookup_allergens", "arguments": {"ingredient": "Gingelly (sesame) oil"}}})
recv()
send({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
      "params": {"name": "lookup_allergens", "arguments": {"ingredient": "creme fraiche lite"}}})
recv()

proc.stdin.close()
proc.wait(timeout=10)
RAW.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in log) + "\n", encoding="utf-8")
print(f"\n{len(log)} raw lines captured -> {RAW.name}")
