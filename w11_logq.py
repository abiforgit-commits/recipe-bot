"""Week 11: query the production log - the tool you use when a complaint comes in.

    python w11_logq.py stats                          what is in the log
    python w11_logq.py find --text "dairy-free"       search INPUT and OUTPUT
    python w11_logq.py find --out "curd" --type substitution --version p-v2
    python w11_logq.py find --since 2026-09-30 --until 2026-10-02 --user u007
    python w11_logq.py outliers --top 5               most expensive requests
    python w11_logq.py show <trace_id>                one full trace, every span

Slices: time (--since/--until), user (--user), prompt version (--version),
input type (--type), cost outlier (outliers). Text search covers the query AND
the answer, because complaints describe what the assistant SAID, not what the
user typed.
"""
import argparse
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
LOG = Path(__file__).parent / "logs" / "w11_requests.jsonl"


def load():
    return [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]


def matches(r, a):
    if a.since and r["ts"] < a.since:
        return False
    if a.until and r["ts"] >= a.until:
        return False
    if a.user and r["user_id"] != a.user:
        return False
    if a.version and r["prompt_version"] != a.version:
        return False
    if a.type and r["input_type"] != a.type:
        return False
    if a.text and not re.search(a.text, r["query"] + "\n" + r["output"], re.I):
        return False
    if a.inp and not re.search(a.inp, r["query"], re.I):
        return False
    if a.out and not re.search(a.out, r["output"], re.I):
        return False
    return True


def line(r):
    return (f"{r['trace_id']}  {r['ts']}  {r['user_id']}  {r['prompt_version']}  "
            f"{r['input_type']:<15} ${r['cost_usd_total']:.6f}  {r['query'][:70]}")


def cmd_stats(a):
    rs = load()
    print(f"{len(rs)} requests   {rs[0]['ts']}  ->  {rs[-1]['ts']}")
    for field in ("prompt_version", "input_type", "user_id"):
        c = Counter(r[field] for r in rs)
        print(f"  {field}: " + ", ".join(f"{k}={v}" for k, v in c.most_common(8))
              + (" ..." if len(c) > 8 else ""))


def cmd_find(a):
    hits = [r for r in load() if matches(r, a)]
    for r in hits:
        print(line(r))
        if a.snippet:
            m = re.search(a.snippet, r["output"], re.I)
            if m:
                s = max(0, m.start() - 90)
                print(f"      ...{r['output'][s:m.end() + 90].replace(chr(10), ' ')}...")
    print(f"\n{len(hits)} match(es)")


def cmd_outliers(a):
    rs = load()
    costs = [r["cost_usd_total"] for r in rs]
    med = statistics.median(costs)
    for r in sorted(rs, key=lambda r: -r["cost_usd_total"])[:a.top]:
        print(f"{line(r)}   ({r['cost_usd_total'] / med:.1f}x median)")


def cmd_show(a):
    r = next((r for r in load() if r["trace_id"].startswith(a.trace_id)), None)
    if not r:
        sys.exit(f"no trace {a.trace_id}")
    print(json.dumps(r, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stats")
    f = sub.add_parser("find")
    for opt in ("--since", "--until", "--user", "--version", "--type", "--text", "--inp", "--out",
                "--snippet"):
        f.add_argument(opt)
    o = sub.add_parser("outliers")
    o.add_argument("--top", type=int, default=5)
    s = sub.add_parser("show")
    s.add_argument("trace_id")
    a = ap.parse_args()
    {"stats": cmd_stats, "find": cmd_find, "outliers": cmd_outliers, "show": cmd_show}[a.cmd](a)
