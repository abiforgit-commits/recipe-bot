"""Week 11: run the Week-6 suite (+ the new dairy regression case) against the production app.

    python w11_suite.py --version p-v2      before the fix
    python w11_suite.py --version p-v5      after the fix (p-v3, p-v4 failed: results_w11.md)

Cases: every runnable Week-6 case (c01-c25; r01/r02 are replays of c10/c06) plus the
new case from the drill, appended to w6_cases.jsonl. A case passes when the Week-6
judge (judge_v2.txt) says PASS AND every assertion in w6_assertions.ASSERTIONS that
applies to the production app passes. Only the prompt version differs between runs.
"""
import argparse, asyncio, json, sys
from pathlib import Path
from w11_app import RecipeApp, chunk_text
from w4_retriever import _DOC_BY_ID
from w6_judge import judge_case
from w6_assertions import a5_no_dairy_side_for_dairy_free

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent


def cases():
    out = []
    for l in (ROOT / "w6_cases.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            c = json.loads(l)
            if c["case_id"].startswith(("c", "w11")):
                out.append(c)
    return out


async def run(version):
    rows = []
    async with RecipeApp() as app:
        for c in cases():
            r = await app.answer(c["question"], user_id="suite", prompt_version=version, log=False)
            spans = {s["name"]: s for s in r["spans"]}
            ctx = [f"[{cid}]\n{chunk_text(cid)}" for cid in spans["retrieval"]["context_ids"]]
            ctx += [f"[{t['tool']}] {json.dumps(t['args'])}\n{t['result']}" for t in spans["tools"]["calls"]]
            verdict, reason = judge_case("judge_v2.txt", c, r["output"], "\n\n".join(ctx))
            a5_ok = a5_no_dairy_side_for_dairy_free(r["output"], c, _DOC_BY_ID)
            ok = verdict == "PASS" and a5_ok
            rows.append({"case_id": c["case_id"], "question": c["question"], "pass": ok,
                         "judge": verdict, "judge_reason": reason, "A5": a5_ok, "output": r["output"]})
            flag = "" if ok else f"   <- {'judge FAIL' if verdict != 'PASS' else ''}{' ' if verdict != 'PASS' and not a5_ok else ''}{'A5 FAIL' if not a5_ok else ''}"
            print(f"{'PASS' if ok else 'FAIL'}  {c['case_id']:<8} {c['question'][:58]:<60}{flag}", flush=True)
    n_pass = sum(r["pass"] for r in rows)
    print(f"\nSUITE [{version}]: {n_pass}/{len(rows)} pass")
    (ROOT / "results" / f"w11_suite_{version}.json").write_text(
        json.dumps({"version": version, "pass": n_pass, "total": len(rows), "rows": rows},
                   indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--version", required=True)
    asyncio.run(run(ap.parse_args().version))
