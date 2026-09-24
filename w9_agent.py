"""Week 9: MCP host agent - discovers its tools from every server in the config.

    python w9_agent.py "Halve the appam recipe"              (uses mcp_config.json)
    python w9_agent.py --config other.json "request"
    python w9_agent.py --list-tools --tag before             (tools/list per server, then exit)

This module never names a tool. Every tool the model can call comes from
tools/list on a server listed in the config file, so adding a server is a
config change and this file does not change.

Roles (MCP vocabulary):
    host    this process - owns the conversation and is the ONLY place the
            model is called (call_llm below)
    client  one ClientSession per configured server, created here
    server  a separate process that exposes tools; it never sees the model
"""
import argparse
import asyncio
import json
import sys
import time
from contextlib import AsyncExitStack
from pathlib import Path

from mcp import ClientSession, StdioServerParameters, stdio_client

from ask import call_llm, DEFAULT_MODEL

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent
SEP = "__"  # model-facing tool names are <server>__<tool>, so two servers can't collide

MAX_ITERS = 8
MAX_TOKENS = 20000
MAX_COST_USD = 0.02
MAX_WALL_SEC = 180
PRICE_IN, PRICE_OUT = 0.10, 0.40  # modelled USD per 1M tokens, as in Week 7

SYSTEM = """You are a recipe assistant. Your tools were discovered at startup from MCP
servers; use them to answer.

Rules:
- Never state an ingredient, amount, allergen flag or nutrition figure that a tool
  did not return in this conversation.
- If a tool returns an error, read it before deciding what to do next.
- When you have what you need, answer the user plainly and briefly."""

# JSON-schema keywords Gemini's function-calling endpoint rejects or ignores.
DROP_KEYS = {"title", "additionalProperties", "$schema", "default", "examples"}


def clean_schema(schema):
    """Strip unsupported keywords, but never touch property NAMES."""
    if isinstance(schema, list):
        return [clean_schema(s) for s in schema]
    if not isinstance(schema, dict):
        return schema
    out = {}
    for key, value in schema.items():
        if key in DROP_KEYS:
            continue
        if key == "properties" and isinstance(value, dict):
            out[key] = {name: clean_schema(sub) for name, sub in value.items()}
        else:
            out[key] = clean_schema(value)
    return out


def result_text(result):
    """Flatten a CallToolResult's content list into text for the model."""
    parts = []
    for item in getattr(result, "content", None) or []:
        parts.append(getattr(item, "text", None) or str(item))
    return "\n".join(parts)


async def connect_all(config_path, stack):
    """Start every configured server, run initialize + tools/list against each.

    Returns (sessions, catalogue): sessions maps server name -> ClientSession,
    catalogue maps model-facing tool name -> (server, tool object).
    """
    config = json.loads(config_path.read_text(encoding="utf-8"))
    sessions, catalogue = {}, {}
    for server, spec in config["mcpServers"].items():
        command = sys.executable if spec["command"] in ("python", "python3") else spec["command"]
        params = StdioServerParameters(command=command, args=spec.get("args", []),
                                       env=spec.get("env"), cwd=str(config_path.parent))
        read, write = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        sessions[server] = session
        for tool in (await session.list_tools()).tools:
            catalogue[f"{server}{SEP}{tool.name}"] = (server, tool)
    return sessions, catalogue


def to_llm_tools(catalogue):
    return [{"type": "function", "function": {
        "name": qualified,
        "description": tool.description or "",
        "parameters": clean_schema(tool.input_schema or {"type": "object", "properties": {}}),
    }} for qualified, (_, tool) in catalogue.items()]


async def list_tools(config_path, tag):
    """Print and save the raw tools/list (and resources/list) of every server."""
    async with AsyncExitStack() as stack:
        sessions, catalogue = await connect_all(config_path, stack)
        report = {"config": config_path.name, "servers": {}}
        for server, session in sessions.items():
            tools = await session.list_tools()
            try:
                resources = [r.model_dump(mode="json", by_alias=True, exclude_none=True)
                             for r in (await session.list_resources()).resources]
            except Exception:
                resources = []
            report["servers"][server] = {
                "tools_list_raw": tools.model_dump(mode="json", by_alias=True, exclude_none=True),
                "resources_list_raw": resources,
            }
            print(f"\n[{server}]  {len(tools.tools)} tool(s) from tools/list")
            for t in tools.tools:
                first = (t.description or "").strip().splitlines()[0] if t.description else ""
                print(f"   - {t.name:<24} {first[:70]}")
            for r in resources:
                print(f"   (resource) {r.get('uri')}")
        report["total_tools"] = len(catalogue)
        report["tool_names"] = list(catalogue)
        print(f"\nTOTAL: {len(catalogue)} tools -> {', '.join(catalogue)}")
        out = ROOT / "results" / f"w9_tools_{tag}.json"
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"saved {out.name}")


async def run(request, config_path, tag):
    t0 = time.time()
    trace = []

    def log(event, **fields):
        entry = {"event": event, **fields}
        trace.append(entry)
        return entry

    async with AsyncExitStack() as stack:
        sessions, catalogue = await connect_all(config_path, stack)
        tools = to_llm_tools(catalogue)
        log("discovered", tools=list(catalogue))
        print(f"discovered {len(catalogue)} tools from {len(sessions)} server(s): {', '.join(catalogue)}\n")

        messages = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": request}]
        usage = {"in": 0, "out": 0}
        stop_reason, final = "completed", None

        for lap in range(1, MAX_ITERS + 1):
            spent = usage["in"] + usage["out"]
            cost = (usage["in"] * PRICE_IN + usage["out"] * PRICE_OUT) / 1_000_000
            if spent >= MAX_TOKENS:
                stop_reason = f"BUDGET:max_tokens ({spent} >= {MAX_TOKENS})"
                break
            if cost >= MAX_COST_USD:
                stop_reason = f"BUDGET:max_cost (${cost:.5f} >= ${MAX_COST_USD})"
                break
            if time.time() - t0 >= MAX_WALL_SEC:
                stop_reason = f"BUDGET:wall_clock (>= {MAX_WALL_SEC}s)"
                break

            # The ONLY model call in the system: the host asks the LLM what to do next.
            resp = call_llm(model=DEFAULT_MODEL, temperature=0, messages=messages, tools=tools)
            usage["in"] += resp.usage.prompt_tokens
            usage["out"] += resp.usage.completion_tokens
            msg = resp.choices[0].message

            if not msg.tool_calls:
                final = (msg.content or "").strip()
                log("final", lap=lap, text=final)
                print(f"[lap {lap}] final answer")
                break

            log("model_turn", lap=lap, text=msg.content,
                tool_calls=[{"name": tc.function.name, "arguments": tc.function.arguments}
                            for tc in msg.tool_calls])
            # Echo verbatim: Gemini's thought_signature rides inside tool_calls.
            messages.append(msg.model_dump(exclude_none=True))

            for tc in msg.tool_calls:
                qualified = tc.function.name
                args = json.loads(tc.function.arguments or "{}")
                if qualified not in catalogue:
                    payload = {"is_error": True, "result": f"no such tool {qualified!r}"}
                    server = tool_name = None
                else:
                    server, tool = catalogue[qualified]
                    tool_name = tool.name
                    result = await sessions[server].call_tool(tool_name, args)  # MCP tools/call
                    payload = {"is_error": bool(getattr(result, "is_error", False)),
                               "result": result_text(result)}
                log("tool_call", lap=lap, qualified=qualified, server=server, tool=tool_name,
                    arguments=args, is_error=payload["is_error"], result=payload["result"])
                flag = "ERROR " if payload["is_error"] else ""
                print(f"[lap {lap}] {qualified}({json.dumps(args, ensure_ascii=False)}) "
                      f"-> {flag}{payload['result'][:110]}")
                messages.append({"role": "tool", "tool_call_id": tc.id,
                                 "content": json.dumps(payload, ensure_ascii=False)[:4000]})
        else:
            stop_reason = f"BUDGET:max_iters ({MAX_ITERS} laps used)"

        cost = (usage["in"] * PRICE_IN + usage["out"] * PRICE_OUT) / 1_000_000
        summary = log("summary", request=request, stop_reason=stop_reason,
                      laps=sum(1 for e in trace if e["event"] in ("model_turn", "final")),
                      tokens_total=usage["in"] + usage["out"], cost_usd=round(cost, 6),
                      latency_s=round(time.time() - t0, 2), model=DEFAULT_MODEL,
                      config=config_path.name)

    out = ROOT / "results" / f"w9_trace_{tag}.jsonl"
    out.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in trace) + "\n",
                   encoding="utf-8")
    print(f"\nstop_reason: {stop_reason}   laps={summary['laps']}  "
          f"tokens={summary['tokens_total']}  cost=${summary['cost_usd']:.6f}  "
          f"latency={summary['latency_s']}s")
    print(f"\n{final}\n\ntrace saved to {out.name}")
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("request", nargs="?")
    ap.add_argument("--config", default="mcp_config.json")
    ap.add_argument("--list-tools", action="store_true")
    ap.add_argument("--tag", default="run")
    args = ap.parse_args()
    config_path = (ROOT / args.config).resolve()
    if args.list_tools:
        asyncio.run(list_tools(config_path, args.tag))
    elif args.request:
        asyncio.run(run(args.request, config_path, args.tag))
    else:
        ap.error("give a request, or --list-tools")


if __name__ == "__main__":
    main()
