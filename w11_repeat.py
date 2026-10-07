"""Week 11: is the RED -> GREEN on w11_r01 stable, or one lucky run?

    python w11_repeat.py --version p-v2 --n 3
    python w11_repeat.py --version p-v5 --n 3 --probes
    python w11_repeat.py --version p-v5 --n 3 --question "I'm dairy-free. How should I serve ragi koozh?"

Runs the new case N times on one prompt version, scoring each run exactly as the
suite does (Week-6 judge + A5). The suite count moves about +/-3 cases between runs
with nothing changed, so one green on the new case is not enough evidence.
--probes also runs the 6 dairy-free questions from the drill's probe once each, so a
fix that only passes the one eval case (overfitting) shows up.
"""
import argparse, asyncio, json, sys
from pathlib import Path
from w11_app import RecipeApp, chunk_text
from w4_retriever import _DOC_BY_ID
from w6_judge import judge_case
from w6_assertions import a5_no_dairy_side_for_dairy_free

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent
CASE = json.loads((ROOT / "w11_eval_case.jsonl").read_text(encoding="utf-8").splitlines()[0])
PROBES = ["Make the ragi koozh dairy-free",
          "I'm dairy-free. How should I serve ragi koozh?",
          "Give me a dairy-free version of ragi koozh with the usual sides",
          "Make the thayir curd recipe dairy-free",
          "Can I make thayir without dairy?",
          "Dairy-free swap for the buttermilk in ragi koozh?"]


async def main(version, n, probes, question=None):
    out = []
    jobs = [("w11_r01" if question is None else "repeat", question or CASE["question"])] * n + ([("probe", q) for q in PROBES] if probes else [])
    async with RecipeApp() as app:
        for i, (kind, q) in enumerate(jobs, 1):
            case = {**CASE, "question": q}
            r = await app.answer(q, user_id="repeat", prompt_version=version, log=False)
            spans = {s["name"]: s for s in r["spans"]}
            ctx = [f"[{c}]\n{chunk_text(c)}" for c in spans["retrieval"]["context_ids"]]
            ctx += [f"[{t['tool']}] {json.dumps(t['args'])}\n{t['result']}" for t in spans["tools"]["calls"]]
            verdict, reason = judge_case("judge_v2.txt", case, r["output"], "\n\n".join(ctx))
            a5 = a5_no_dairy_side_for_dairy_free(r["output"], case, _DOC_BY_ID)
            ok = verdict == "PASS" and a5
            out.append({"run": i, "kind": kind, "question": q, "pass": ok, "judge": verdict, "A5": a5,
                        "reason": reason, "output": r["output"]})
            print(f"[{version}] {kind:<7} {i}: {'PASS' if ok else 'FAIL'}  judge={verdict} A5={a5}  "
                  f"{q[:45]:<46} {reason[:80]}", flush=True)
    for kind in ("w11_r01", "repeat", "probe"):
        rs = [o for o in out if o["kind"] == kind]
        if rs:
            print(f"[{version}] {kind}: {sum(o['pass'] for o in rs)}/{len(rs)} pass")
    (ROOT / "results" / f"w11_repeat_{version}{'_q' if question else ''}.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--version", required=True)
    ap.add_argument("--n", type=int, default=3); ap.add_argument("--probes", action="store_true")
    ap.add_argument("--question", help="repeat this question instead of w11_r01")
    a = ap.parse_args(); asyncio.run(main(a.version, a.n, a.probes, a.question))
