"""Week 9: merge the raw wire capture with hand-written annotations -> wire.json.

    python w9_annotate_wire.py

The annotations below were written by reading each captured message; the
script only pairs them with the raw lines from results/w9_wire_raw.jsonl.
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent

MODEL_CALL = ("The model is called only by the host (w9_agent.py -> call_llm), BETWEEN "
              "tools/list and tools/call, where it reads the tool schemas and chooses the "
              "call; nothing in this exchange touches a model, and the server never does.")

ANNOTATIONS = [
    {  # 0 initialize request
        "jsonrpc": "Always the literal '2.0': every MCP message is a JSON-RPC 2.0 message.",
        "id": "1 = a REQUEST that demands a reply; the reply must echo this same id.",
        "method": "'initialize' is always first: the handshake that fixes version and capabilities.",
        "params": "What the client offers the server.",
        "params.protocolVersion": "The newest MCP revision this client speaks (2026-07-28).",
        "params.capabilities": "Empty: this bare client offers no sampling/roots/elicitation back to the server.",
        "params.clientInfo": "Self-reported name/version of the client - informational, not authentication.",
    },
    {  # 1 initialize result
        "jsonrpc": "'2.0' again.",
        "id": "1 - matches the request, which is how the client pairs replies with requests.",
        "result": "Success (a failure would carry an 'error' member instead of 'result').",
        "result.capabilities": "What this server offers: tools, resources and prompts. listChanged:false "
                               "means it will never push a 'my tool list changed' notification.",
        "result.protocolVersion": "2025-11-25, NOT the 2026-07-28 the client asked for: the server "
                                  "negotiated down to the newest revision its handshake supports. "
                                  "The client must accept this version or disconnect.",
        "result.serverInfo": "Self-reported identity 'ingredient-db', version empty. Unverified - it "
                             "tells you what the server CLAIMS to be, which is why the risk note matters.",
    },
    {  # 2 initialized notification
        "jsonrpc": "'2.0'.",
        "method": "'notifications/initialized': the client confirms the handshake is done.",
        "(no id)": "No 'id' field = a NOTIFICATION: fire-and-forget, the server sends no reply. "
                   "That is why no server line follows this one.",
    },
    {  # 3 tools/list request
        "jsonrpc": "'2.0'.",
        "id": "2 - a new request, so a new id.",
        "method": "'tools/list': DISCOVERY. The agent learns its tools from this reply rather than "
                  "from anything hard-coded - the reason server two needed no agent change.",
        "params": "Empty object; a cursor would go here to page through a long tool list.",
    },
    {  # 4 tools/list result
        "jsonrpc": "'2.0'.",
        "id": "2 - pairs with the tools/list request.",
        "result": "Success.",
        "result.tools": "Two tools. For each: 'name' (what tools/call must use), 'description' (the "
                        "docstring VERBATIM - this is the text the model reads to decide when to call "
                        "it, i.e. the docstring is a prompt), and 'inputSchema' (JSON Schema for the "
                        "arguments). The 'title' keys inside inputSchema are why w9_agent.clean_schema "
                        "strips them before handing schemas to Gemini.",
    },
    {  # 5 tools/call request
        "jsonrpc": "'2.0'.",
        "id": "3.",
        "method": "'tools/call': EXECUTE one tool. In the real agent the host builds this from the "
                  "model's chosen function call; here it was typed by hand, proving the protocol "
                  "itself needs no model.",
        "params": "What to run.",
        "params.name": "'lookup_allergens' - the bare server-side name. The agent's model saw it as "
                       "'ingredient_db__lookup_allergens'; the host strips the prefix before this call.",
        "params.arguments": "Must satisfy the inputSchema from tools/list.",
    },
    {  # 6 tools/call result - success
        "jsonrpc": "'2.0'.",
        "id": "3 - pairs with the call.",
        "result": "The tool ran.",
        "result.content": "A list of content blocks; here one text block holding the allergen flags "
                          "as JSON text. This text is what the host feeds back to the model.",
        "result.isError": "false: the lookup succeeded - sesame is true for gingelly oil.",
    },
    {  # 7 tools/call request - unknown ingredient
        "jsonrpc": "'2.0'.",
        "id": "4.",
        "method": "'tools/call' again, deliberately with an ingredient the database lacks.",
        "params": "name 'lookup_allergens', arguments {ingredient: 'creme fraiche lite'}.",
    },
    {  # 8 tools/call result - tool error
        "jsonrpc": "'2.0'.",
        "id": "4.",
        "result": "Note: still a JSON-RPC RESULT, not a JSON-RPC 'error'. A failed TOOL is not a failed "
                  "PROTOCOL - the transport worked perfectly; only the lookup missed.",
        "result.content": "The failure is explained in plain words the model can act on (check the "
                          "spelling; do not assume allergen-free). The SDK prefixed 'Error executing "
                          "tool lookup_allergens:' to the server's own message.",
        "result.isError": "true: tells the host this is an error message, not data - so a spelling miss "
                          "is distinguishable from a dead server (which would be a JSON-RPC error or a "
                          "broken pipe, never an isError result).",
    },
]


def main():
    raw = [json.loads(l) for l in
           (ROOT / "results" / "w9_wire_raw.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(raw) == len(ANNOTATIONS), f"{len(raw)} raw lines vs {len(ANNOTATIONS)} annotation blocks"
    exchange = []
    for i, (entry, notes) in enumerate(zip(raw, ANNOTATIONS)):
        exchange.append({"step": i, "direction": entry["direction"],
                         "raw_line": entry["raw"], "message": json.loads(entry["raw"]),
                         "annotations": notes})
    wire = {
        "what": "Raw MCP JSON-RPC exchange with the ingredient database server over stdio",
        "server": "ingredient_db_server/server.py",
        "captured_with": "w9_wire_capture.py - hand-written JSON lines on stdin/stdout, no SDK client, no model",
        "raw_file": "results/w9_wire_raw.jsonl",
        "sequence": "initialize -> notifications/initialized -> tools/list -> tools/call (+ a failing tools/call)",
        "where_the_model_call_happens": MODEL_CALL,
        "exchange": exchange,
    }
    (ROOT / "wire.json").write_text(json.dumps(wire, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wire.json written: {len(exchange)} messages, "
          f"{sum(len(e['annotations']) for e in exchange)} annotations")


if __name__ == "__main__":
    main()
