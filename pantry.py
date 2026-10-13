"""Pantry-to-Plate: the Week 12 capstone. ONE entry point for the whole system.

    python pantry.py ask "My son is allergic to nuts - can he have the nankhatai?"
    python pantry.py eval --tag before        full eval suite on the integrated system
    python pantry.py trajectory --tag before  tool-choice accuracy + outcome-vs-trajectory gap
    python pantry.py agreement --tag before   the judge vs the hand labels
    python pantry.py trace <trace_id>         one question, every span, across the agent and MCP hops
    python pantry.py tools                    what the agent discovers over MCP (tools/list)
    python pantry.py serve [--http 8765]      run the MCP server for someone else's client
    python pantry.py setup                    build the search index (ask/eval also do it on first use)

Pipeline per question: agent loop (Week 7) -> tools discovered over MCP (Week 9) ->
pantry_server.py: hybrid RAG search (Weeks 3-4) + exact-match allergen/scaling/safety
tools -> answer with versioned citations, logged under one trace id (Week 11).
"""
import argparse
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent


def need_key():
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    if not (os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")):
        sys.exit("No model key. Create a file named .env in this folder containing\n"
                 "    GEMINI_API_KEY=your-key\n"
                 "(free key: https://aistudio.google.com/apikey), then run the command again.")


def cmd_setup(_):
    import pantry_corpus as pc
    pc.build_index()
    print(f"index built: {len(pc.CHUNKS)} chunks from {len(pc.RECORDS)} CMS records "
          f"({len(pc.SUPERSEDED_CHUNKS)} chunks from superseded versions, kept on purpose)")


def cmd_ask(a):
    need_key()
    import pantry_corpus as pc
    from pantry_agent import PantryAgent

    def show(kind, name, args, is_error, text):
        print(f"   tool  {name}({json.dumps(args, ensure_ascii=False)})"
              f"{'  -> ERROR' if is_error else ''}", flush=True)

    async def run():
        pc._collection()  # builds the index on the very first run
        async with PantryAgent() as agent:
            print(f"discovered {len(agent.catalogue)} tools over MCP: {', '.join(agent.catalogue)}\n")
            return await agent.ask(a.question, user=a.user, on_event=show)

    rec = asyncio.run(run())
    print(f"\n{rec['rendered']}\n")
    print(f"trace {rec['trace_id']}  |  {rec['laps']} model calls, {len(rec['tool_sequence'])} tool calls  |  "
          f"{rec['tokens_total']} tokens  |  ${rec['cost_usd_total']:.6f}  |  "
          f"{rec['latency_ms_total'] / 1000:.1f}s  |  {rec['stop_reason']}")
    print(f"full trace: python pantry.py trace {rec['trace_id']}")


def cmd_trace(a):
    from pantry_trace import merged_trace
    rec = merged_trace(a.trace_id)
    if rec is None:
        sys.exit(f"no trace {a.trace_id} in logs/pantry_requests.jsonl")
    if a.json:
        print(json.dumps(rec, indent=2, ensure_ascii=False))
        return
    server = {s["parent_span_id"]: s for s in rec["server_spans"]}
    print(f"trace {rec['trace_id']}   {rec['ts']}   user {rec['user']}   prompt {rec['prompt_version']}")
    print(f"Q: {rec['question']}\n")
    print(f"{'span':<44}{'latency':>11}{'throttle':>10}{'tokens':>8}{'cost':>12}")
    for s in rec["spans"]:
        if s["kind"] == "llm":
            print(f"{s['name']:<44}{s['latency_ms']:>9.0f}ms{s['throttle_wait_ms']:>8.0f}ms"
                  f"{s['prompt_tokens'] + s['completion_tokens']:>8}{s['cost_usd']:>12.8f}")
        else:
            print(f"{s['name']:<44}{s['latency_ms']:>9.0f}ms{'':>10}{'':>8}{0:>12.8f}"
                  f"{'  ERROR' if s['is_error'] else ''}")
            if s["span_id"] in server:
                sv = server[s["span_id"]]
                print(f"  └ {sv['span']:<40}{sv['latency_ms']:>9.0f}ms   (server, same trace id)")
    print(f"{'TOTAL':<44}{rec['latency_ms_total']:>9.0f}ms{'':>10}{rec['tokens_total']:>8}"
          f"{rec['cost_usd_total']:>12.8f}")
    print(f"\nserver spans under this trace id: {len(rec['server_spans'])}   stop: {rec['stop_reason']}")
    print(f"\n{rec['rendered']}")


def cmd_tools(_):
    from contextlib import AsyncExitStack  # no key needed: tools/list never calls a model
    from pantry_agent import CONFIG
    from w9_agent import connect_all

    async def run():
        async with AsyncExitStack() as stack:
            sessions, catalogue = await connect_all(CONFIG, stack)
            for name, (server, tool) in catalogue.items():
                print(f"{name:<36} {(tool.description or '').strip().splitlines()[0][:80]}")
            print(f"\n{len(catalogue)} tools from {len(sessions)} servers, discovered via tools/list")
    asyncio.run(run())


def cmd_serve(a):
    args = [sys.executable, str(ROOT / "pantry_server.py")] + (["--http", str(a.http)] if a.http else [])
    if a.http:
        print(f"MCP server on http://localhost:{a.http}/mcp (streamable HTTP). Ctrl+C to stop.")
    subprocess.run(args, cwd=ROOT)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ask")
    p.add_argument("question")
    p.add_argument("--user", default="cli-user")
    p = sub.add_parser("trace")
    p.add_argument("trace_id")
    p.add_argument("--json", action="store_true")
    sub.add_parser("tools")
    sub.add_parser("setup")
    p = sub.add_parser("serve")
    p.add_argument("--http", type=int)
    for name in ("eval", "trajectory", "agreement"):
        p = sub.add_parser(name)
        p.add_argument("--tag", default="before")
        p.add_argument("--judge", default="judge_v2.txt", help="judge prompt file (Week 6: judge_v2.txt)")
        if name == "agreement":
            p.add_argument("--labels", help="labels file (default pantry_labels_<tag>.json), e.g. your own")
        if name == "eval":
            p.add_argument("--judge-only", action="store_true", help="re-judge cached outputs, no new runs")
            p.add_argument("--cases", help="comma-separated case ids (default: all)")
            p.add_argument("--repeat", type=int, default=1, help="run each case N times")
            p.add_argument("--no-judge", action="store_true", help="assertions only (repeat runs)")
            p.add_argument("--resume", action="store_true", help="keep finished runs of this tag, do the rest")
    a = ap.parse_args()
    if a.cmd in ("eval", "trajectory", "agreement"):
        if a.cmd == "eval":
            need_key()
        import pantry_eval
        getattr(pantry_eval, f"cmd_{a.cmd}")(a)
    else:
        globals()[f"cmd_{a.cmd}"](a)


if __name__ == "__main__":
    main()
