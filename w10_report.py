"""Week 10: build race_table.md, handoffs.log and the multiplier line from the raw rows.

    python w10_report.py

Reads results/w10_race_rows.jsonl and results/w10_judged.jsonl. Nothing here is
typed by hand: every number in the outputs is computed from those two files.
"""
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent
CASES = json.loads((ROOT / "w10_cases.json").read_text(encoding="utf-8"))["cases"]


def load(name):
    path = ROOT / "results" / name
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def pct(values, q):
    """Percentile by linear interpolation between order statistics (inclusive)."""
    return statistics.quantiles(values, n=100, method="inclusive")[q - 1]


def main():
    rows = {(r["arm"], r["case_id"]): r for r in load("w10_race_rows.jsonl")}
    verdicts = {(j["arm"], j["case_id"]): j for j in load("w10_judged.jsonl")}
    ids = [c["case_id"] for c in CASES]
    arms = ["single", "multi"]

    summary = {}
    for arm in arms:
        rs = [rows[(arm, i)] for i in ids]
        passed = sum(verdicts[(arm, i)]["verdict"] == "PASS" for i in ids)
        summary[arm] = {
            "pass": passed, "n": len(rs),
            "p50_wall": pct([r["latency_wall_s"] for r in rs], 50),
            "p99_wall": pct([r["latency_wall_s"] for r in rs], 99),
            "p50_net": pct([r["latency_net_s"] for r in rs], 50),
            "p99_net": pct([r["latency_net_s"] for r in rs], 99),
            "tokens": sum(r["tokens_total"] for r in rs),
            "cost_per_q": sum(r["cost_usd"] for r in rs) / len(rs),
            "calls": sum(r["llm_calls"] for r in rs),
        }
    s, m = summary["single"], summary["multi"]
    multiplier = m["tokens"] / s["tokens"]

    # --- attribute every multi-arm token to the hand-off that caused it ---
    by_handoff = defaultdict(lambda: {"tokens": 0, "prompt": 0, "calls": 0})
    for i in ids:
        for c in rows[("multi", i)]["calls"]:
            b = by_handoff[c["handoff"]]
            b["tokens"] += c["tokens"]
            b["prompt"] += c["prompt_tokens"]
            b["calls"] += 1
    ranked = sorted(by_handoff.items(), key=lambda kv: -kv[1]["tokens"])
    top_name, top = ranked[0]
    top_share = top["tokens"] / m["tokens"]

    multiplier_line = (f"Context re-send multiplier: {m['tokens']:,} multi / {s['tokens']:,} single "
                       f"= {multiplier:.1f}x. Largest share: \"{top_name}\" hand-off, "
                       f"{top['tokens']:,} tokens = {top_share:.0%} of all multi-arm tokens "
                       f"({top['prompt']:,} of them re-sent prompt tokens, over {top['calls']} calls).")

    # --- race_table.md ---
    L = ["# race_table.md — kitchen squad vs single agent", "",
         "Same 10 Week-6 cases (seeded draw, `w10_cases.json`), same judge (`judge_v2.txt`),",
         "same model (`gemini-flash-lite-latest`, temperature 0), same two MCP servers.", "",
         "Cases: " + ", ".join(f"`{c['case_id']}`" for c in CASES), "",
         "| Metric | Single agent | Kitchen squad | Squad vs single |",
         "|---|---|---|---|",
         f"| **Pass rate** (Week-6 judge) | {s['pass']}/{s['n']} | {m['pass']}/{m['n']} | "
         f"{m['pass'] - s['pass']:+d} |",
         f"| **p50 latency** (net of throttling) | {s['p50_net']:.1f} s | {m['p50_net']:.1f} s | "
         f"{m['p50_net'] / s['p50_net']:.1f}x |",
         f"| **p99 latency** (net of throttling) | {s['p99_net']:.1f} s | {m['p99_net']:.1f} s | "
         f"{m['p99_net'] / s['p99_net']:.1f}x |",
         f"| **Total tokens** (10 questions) | {s['tokens']:,} | {m['tokens']:,} | "
         f"{multiplier:.1f}x |",
         f"| **Cost per question** (modelled) | ${s['cost_per_q']:.6f} | ${m['cost_per_q']:.6f} | "
         f"{m['cost_per_q'] / s['cost_per_q']:.1f}x |",
         "", "Raw wall-clock latency, including free-tier pacing and 429 backoff:", "",
         "| | Single | Squad |", "|---|---|---|",
         f"| p50 wall | {s['p50_wall']:.1f} s | {m['p50_wall']:.1f} s |",
         f"| p99 wall | {s['p99_wall']:.1f} s | {m['p99_wall']:.1f} s |",
         f"| LLM calls (10 questions) | {s['calls']} | {m['calls']} |",
         "", f"**{multiplier_line}**", "",
         "## Per case", "",
         "| Case | Question | Single | Squad | Single tok | Squad tok | Single net s | Squad net s |",
         "|---|---|---|---|---|---|---|---|"]
    for c in CASES:
        i = c["case_id"]
        rs, rm = rows[("single", i)], rows[("multi", i)]
        L.append(f"| {i} | {c['question']} | {verdicts[('single', i)]['verdict']} | "
                 f"{verdicts[('multi', i)]['verdict']} | {rs['tokens_total']:,} | "
                 f"{rm['tokens_total']:,} | {rs['latency_net_s']:.1f} | {rm['latency_net_s']:.1f} |")
    L += ["", "## Where the squad's tokens went (all 10 questions)", "",
          "| Hand-off | LLM calls | Tokens | Share | Of which re-sent prompt |", "|---|---|---|---|---|"]
    for name, b in ranked:
        L.append(f"| {name} | {b['calls']} | {b['tokens']:,} | {b['tokens'] / m['tokens']:.0%} | "
                 f"{b['prompt']:,} |")
    L += ["", "## Notes on the numbers", "",
          "- **p99 over 10 samples** is interpolated between the two slowest runs, so it is "
          "effectively the worst case; it is reported because it is the number a user notices.",
          "- **Net latency** subtracts time spent sleeping in `ask.call_llm` (4.5 s free-tier "
          "pacing between calls, plus 429 backoff). The free tier serialises every call, so the "
          "squad cannot run its two workers in parallel here: that possible advantage is not "
          "measurable on this quota.",
          "- **Cost** uses the same modelled rate card as Weeks 7-9 ($0.10 / $0.40 per 1M "
          "input / output tokens); the ratio between arms does not depend on it.",
          "- **Judge tokens are excluded** from both arms; the same judge scored both."]
    (ROOT / "race_table.md").write_text("\n".join(L) + "\n", encoding="utf-8")

    # --- handoffs.log ---
    H = ["# handoffs.log — every hand-off in the kitchen squad, with its token count",
         "#",
         "# tokens = the LLM tokens that hand-off caused:",
         "#   user -> manager / worker -> manager : the manager lap that re-read it",
         "#   manager -> worker                   : the whole worker loop it started",
         "# Every multi-arm LLM call is counted under exactly one hand-off, so each case's",
         "# hand-off tokens sum to its total (shared = one manager lap read two results).",
         ""]
    for c in CASES:
        r = rows[("multi", c["case_id"])]
        H.append(f"== {c['case_id']}  {c['question']}   total={r['tokens_total']:,} tokens, "
                 f"{r['llm_calls']} LLM calls, {r['stop_reason']}")
        seen_shared = set()
        for h in r["handoffs"]:
            tok = h["tokens"]
            shared = "shared" in h["note"]
            label = f"{tok:,}" if tok is not None else "-"
            if shared and h["note"] in seen_shared:
                label += " (same lap as above)"
            seen_shared.add(h["note"])
            H.append(f"  #{h['seq']:<2} {h['from']:>20} -> {h['to']:<20} chars={h['chars']:<6} "
                     f"tokens={label:<22} {h['note']}")
        H.append("")
    H += ["# totals by hand-off type (all 10 cases)"]
    for name, b in ranked:
        H.append(f"  {name:<48} calls={b['calls']:<3} tokens={b['tokens']:>7,}  "
                 f"({b['tokens'] / m['tokens']:.0%})")
    H += ["", multiplier_line]
    (ROOT / "handoffs.log").write_text("\n".join(H) + "\n", encoding="utf-8")

    (ROOT / "results" / "w10_summary.json").write_text(json.dumps(
        {"summary": summary, "multiplier": round(multiplier, 1), "multiplier_line": multiplier_line,
         "by_handoff": dict(ranked)}, indent=2), encoding="utf-8")
    print("\n".join(L[7:14]))
    print("\n" + multiplier_line)


if __name__ == "__main__":
    main()
