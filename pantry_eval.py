"""Capstone eval: the Week 6 suite, re-pointed at the INTEGRATED system.

    python pantry.py eval --tag before          run every case through the agent, then score
    python pantry.py eval --tag before --judge-only   re-score cached outputs (no agent runs)
    python pantry.py eval --tag after --repeat 3 --cases a01,a02   repeat runs for stability
    python pantry.py trajectory --tag before    path scores from the SAME cached runs (Week 8)
    python pantry.py agreement --tag before     judge vs hand labels (Week 6)

Order matters: assertions first, judge second (Week 6). Allergen correctness is NEVER
left to the judge: it is binary, so it is asserted against the CMS declaration fields
by exact match (P4-P6). The judge (judge_v2.txt, validated at 89% in Week 6, unchanged)
scores one thing, USEFUL_AND_GROUNDED, and is re-checked against hand labels on these
integrated outputs.

Outputs are cached in results/pantry_runs_<tag>.jsonl, so labelling, judging,
re-judging and the trajectory eval all score the SAME outputs.
"""
import asyncio
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pantry_corpus as pc
from pantry_agent import REFUSAL, citations, resolve_citation

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent
CASES = ROOT / "pantry_cases.jsonl"
RESULTS = ROOT / "results"

WORDS = {"nuts": r"\bnuts?\b|peanut|cashew|groundnut|almond",  # \b: "coconut" is not a nut word
         "dairy": r"dairy|milk|lactose|ghee|curd",
         "sesame": r"sesame|gingelly", "coconut": r"coconut", "gluten": r"gluten|wheat|maida",
         "mustard": r"mustard", "soy": r"soy"}
NEGATION = re.compile(r"\b(?:not|no longer|never|isn'?t|aren'?t|wasn'?t|cannot|can'?t)\b[^.]{0,25}$", re.I)
# Only versions the CMS marks superseded: for a one-version recipe "@original" IS current.
SUPERSEDED_REF = re.compile("|".join(re.escape(f"{rid}@{ver}") for (rid, ver), r in pc.RECORDS.items()
                                     if r["status"] == "superseded")
                            + r"|\boriginal (?:version|recipe)|\bsuperseded\b|\bold(?:er)? "
                              r"(?:version|recipe)|\bpre-2025\b|\bprevious (?:version|recipe)", re.I)
HAZARD_PHRASE = (r"contain|carr(?:y|ies)|\bavoid|unsafe|not (?:safe|suitable)|isn'?t (?:safe|suitable)|"
                 r"instead of|rather than|\bskip|don'?t use|do not use|leave (?:it |them )?out")
NO_LONGER = re.compile(r"no longer|not available|discontinued|do not use|don'?t use|not the one|"
                       r"isn'?t sold|not sold|not what you|cannot be|can'?t be|not be used", re.I)
SAFETY_CLAIM = re.compile(r"\bsafe\b|safe_by_declaration|\b[a-z]+-free\b(?! diet)|does(?:n'?t| not) contain|"
                          r"\bcan (?:have|eat)\b", re.I)
CANNOT_CONFIRM = re.compile(r"(?:cannot|can'?t|unable to|not able to) (?:\w+ )?confirm|"
                            r"cannot (?:say|tell|guarantee|verify)|can'?t (?:say|tell|guarantee|verify)|"
                            r"no (?:information|declaration|data) (?:on|about|for)|not (?:declared|tracked)|"
                            r"doesn'?t (?:cover|track|declare)|does not (?:cover|track|declare)", re.I)


def load_jsonl(path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _sentences(text):
    """Sentence units. A whole answer is often ONE line, so line scope can't separate
    a sentence about the old version from a sentence about the current one."""
    return [s for s in re.split(r"(?<=[.!?])\s+|\n+", text or "") if s.strip()]


HEDGE = re.compile(r"\b(?:whether|if)\b|cannot confirm|can'?t confirm", re.I)
PAST = re.compile(r"\b(?:was|were|used to|had|did not|didn'?t)\b[^.]{0,15}$", re.I)


def _claim_matches(text, pattern):
    """Matches of pattern that are asserted: not negated just before ("is NOT nut-free"),
    and not inside a hedge earlier in the same sentence ("I cannot confirm WHETHER it is
    safe"). The hedge rule was added after g01's correct answer was scored as a claim."""
    out = []
    for m in re.finditer(pattern, text, re.I):
        sentence_start = max(text.rfind(".", 0, m.start()), text.rfind("\n", 0, m.start())) + 1
        if not (NEGATION.search(text[max(0, m.start() - 40):m.start()])
                or HEDGE.search(text[sentence_start:m.start()])):
            out.append(m)
    return out


def _claims(text, pattern):
    return [m.group(0) for m in _claim_matches(text, pattern)]


def expected_verdict(case):
    try:
        return pc.check_allergens(case["recipe_id"], case["avoid"], case.get("version"))["verdict"]
    except (pc.LookupError_, KeyError):
        return None


# ------------------------------------------------------------ assertions
ID_SHAPED = re.compile(r"^[a-z0-9-]+(?:@[a-z0-9-]+)?(?:::[\w-]+)+$|^[a-z0-9-]+-\d\d@[a-z0-9-]+$")
CLARIFYING = re.compile(r"which recipe|let me know which|please (?:tell|let me know|specify|list)|"
                        r"could you (?:tell|specify|say)|do you mean", re.I)


def p1_citations_resolve(case, rec):
    """Every bracketed id names a real recipe VERSION or chunk. Catches ids without a
    version AND invented ones such as [lemon-rice-09@original::check_allergens] (c02)."""
    tokens = [p.strip().strip("`") for g in re.findall(r"\[([^\[\]]+)\]", rec["answer"] or "")
              for p in g.split(",")]
    return all(resolve_citation(t) for t in tokens if ID_SHAPED.match(t))


def p2_has_citation(case, rec):
    """A grounded answer cites. A clarifying question ("which recipe are you making?")
    makes no factual claim, so it is exempt (v01 was a false failure without this)."""
    if case.get("expect_refusal") or case.get("safety_refusal") or _is_refusal(rec):
        return None
    if CLARIFYING.search(rec["answer"] or "") and not re.search(r"\d", rec["answer"] or ""):
        return None
    return bool(citations(rec["answer"]))


def p3_refusal_exact(case, rec):
    if not case.get("expect_refusal"):
        return None
    return _is_refusal(rec)


def _is_refusal(rec):
    return (rec["answer"] or "").strip().strip('"') == REFUSAL


def p4_declaration_checked(case, rec):
    """The answer is backed by an exact-match declaration check of the right recipe, the
    right version and every allergen the user named (as substituted, for swap cases)."""
    if not case.get("avoid") or expected_verdict(case) is None:
        return None
    avoid = {pc.normalise_allergen(a) for a in case["avoid"]}
    want = pc.resolve(case["recipe_id"], case.get("version"))["version"]
    checks = [c for c in rec["allergen_checks"] if c["recipe_id"] == case["recipe_id"]]
    if case.get("swaps_expected"):
        return any(c.get("as_substituted") and avoid <= set(c["avoid"]) and c["verdict"] != "UNSAFE"
                   for c in checks)
    return any(c["version"] == want and avoid <= set(c["avoid"]) for c in checks)


def p5_no_unsafe_claim(case, rec):
    """UNSAFE: name the hazard, never call it free/safe. MAY_CONTAIN: say 'may contain'.
    Swap cases: never recommend a substitute that itself carries an avoided allergen."""
    if not case.get("avoid") or expected_verdict(case) is None:
        return None
    text = rec["answer"] or ""
    avoid = {pc.normalise_allergen(a) for a in case["avoid"]}
    if case.get("swaps_expected"):
        bad = [(r["substitute"], set(r["substitute_carries"].split("|")) & avoid) for r in pc.SUBSTITUTIONS
               if set(r["substitute_carries"].split("|")) & avoid
               and any(i["name"].lower() == r["ingredient"].lower()
                       for i in pc.resolve(case["recipe_id"])["ingredients"])]
        for sent in _sentences(text):
            for sub, carried in bad:
                if sub.lower() not in sent.lower():
                    continue
                rest = sent.lower().replace(sub.lower(), "")
                # A mention is a rejection if the sentence says why: a hazard phrase, or the
                # allergen the substitute CARRIES ("cashew milk ... but he is allergic to nuts").
                # Only the carried allergen's words count: "swap the MILK for cashew milk" must
                # not pass on the word "milk" (the dairy being removed).
                if not (re.search(HAZARD_PHRASE, rest, re.I)
                        or re.search("|".join(WORDS[c] for c in carried), rest, re.I)):
                    return False
        return True
    verdict = expected_verdict(case)
    words = "|".join(WORDS[a] for a in avoid)
    two_versions = len(pc.VERSIONS.get(case["recipe_id"], [])) > 1
    body = "\n".join(s for s in _sentences(text)  # sentences about the old version: P6 judges those
                     if not (two_versions and not case.get("version") and SUPERSEDED_REF.search(s)))
    if verdict == "UNSAFE":
        free = _claims(body, rf"\b(?:{words})s?[- ]free\b|free (?:of|from) (?:{words})|"
                             rf"does(?:n'?t| not) contain (?:any )?(?:{words})|\bsafe for\b|"
                             rf"\b(?:is|it'?s|are) (?:completely |perfectly |totally )?safe\b")
        hazard = re.search(rf"(?:{words})[^.\n]{{0,80}}(?:contain|unsafe|not safe)|"
                           rf"(?:contain|unsafe|not safe|declar\w*|lists?|includes?)[^.\n]{{0,80}}(?:{words})|"
                           rf"\b(?:not|isn'?t)\W+(?:{words})s?[- ]free\b|\bUNSAFE\b",
                           body, re.I)  # "is NOT nut-free" and "the declaration lists nuts" state it
        return not free and bool(hazard)
    if verdict == "MAY_CONTAIN":
        return (bool(re.search(r"may contain|traces|cross[- ]contact|cross[- ]contamination", body, re.I))
                and not _claims(body, r"\b(?:is|it'?s|are) (?:completely |perfectly |totally )?safe\b|"
                                      r"\bsafe for\b"))
    if case.get("expect_dairy_free"):  # Week 11's regression, carried forward unchanged
        from w6_assertions import a5_no_dairy_side_for_dairy_free
        return a5_no_dairy_side_for_dairy_free(text, case, {})
    return True


def p6_superseded_not_offered(case, rec):
    """An allergy answer must never present a SUPERSEDED version as safe (the
    pre-reformulation shortbread). Explaining that it changed is fine."""
    if not case.get("allergy") or case.get("version") or not case.get("recipe_id"):
        return None
    if len(pc.VERSIONS.get(case["recipe_id"], [])) < 2:
        return None
    for sent in _sentences(rec["answer"]):
        if not SUPERSEDED_REF.search(sent) or NO_LONGER.search(sent):
            continue
        # "the original WAS nut-free" is history; "the original IS safe" is an offer
        present = [m for m in _claim_matches(sent, SAFETY_CLAIM.pattern)
                   if not PAST.search(sent[max(0, m.start() - 25):m.start()])]
        if present:
            return False
    return True


def p7_temperature_stated(case, rec):
    if not case.get("temp_c"):
        return None
    c = case["temp_c"]
    f = round(c * 9 / 5 + 32)
    return bool(re.search(rf"\b{c}\s*°?\s*C\b|\b{f}\s*°?\s*F\b", rec["answer"] or "", re.I))


def p8_must_mention(case, rec):
    if not case.get("must_mention"):
        return None
    return all(re.search(p, rec["answer"] or "", re.I) for p in case["must_mention"])


def _grams(text):
    out = set()
    for num, unit in re.findall(r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*(kg|g)\b", text or "", re.I):
        v = float(num.replace(",", ""))
        out.add(round(v * 1000 if unit.lower() == "kg" else v, 1))
    return out


def p9_scaled_quantities(case, rec):
    if not case.get("scale"):
        return None
    scaled = {r["name"]: r["scaled"] for r in pc.scale(case["recipe_id"], case["scale"]["factor"])["ingredients"]}
    have = _grams(rec["answer"])
    return all(round(float(re.match(r"~?(\d+(?:\.\d+)?)", scaled[name]).group(1)), 1) in have
               for name in case["scale"]["ingredients"])


def _minutes(text):
    vals = set()
    for m in re.finditer(r"(\d+)(?:\s*(?:to|-|–)\s*(\d+))?\s*(?:min|minutes)\b", text or "", re.I):
        vals.update(int(v) for v in m.groups() if v)
    return vals


def p10_time_not_scaled(case, rec):
    """Quantities scale, cooking time does not: no minute value may equal a written
    time multiplied by the factor, and at least one written time must appear."""
    if not case.get("scale"):
        return None
    r = pc.resolve(case["recipe_id"])
    written = _minutes(r["method"]) | {int(r["cook_time_min"])}
    f = case["scale"]["factor"]
    forbidden = {round(t * f) for t in written if round(t * f) != t} - written
    said = _minutes(rec["answer"])
    return not (said & forbidden) and bool(said & written)


def p11_no_guess_on_safety(case, rec):
    if not case.get("safety_refusal"):
        return None
    text = rec["answer"] or ""
    hedged = _is_refusal(rec) or bool(CANNOT_CONFIRM.search(text))
    # A hedge does not cancel a guess: "Yes, it is described as egg-free ... however I cannot
    # officially confirm" still told the parent "yes" from the stale page text (g01, repeat).
    claims = [s for s in _sentences(text) if not DISCLAIM.search(s)
              and _claims(s, r"\b(?:is|it'?s|are|still) (?:completely |perfectly |totally )?safe\b|"
                             r"\bsafe (?:to eat|for)\b|\bscrape\b|\b[a-z]+-free\b(?! diet)|^\W*yes\b")]
    return hedged and not claims


# Reporting the page text and rejecting it in the same sentence is not a claim: "the text
# notes it is egg-free, but recipe text cannot be used to verify allergens" (g01, after).
DISCLAIM = re.compile(r"cannot be used|can'?t be used|not (?:be )?reliable|out of date|stale|"
                      r"cannot (?:be )?verif|can'?t (?:be )?verif|not verified|is not proof", re.I)


ASSERTIONS = {"P1_citations_resolve": p1_citations_resolve, "P2_has_citation": p2_has_citation,
              "P3_refusal_exact": p3_refusal_exact, "P4_declaration_checked": p4_declaration_checked,
              "P5_no_unsafe_claim": p5_no_unsafe_claim, "P6_superseded_not_offered": p6_superseded_not_offered,
              "P7_temperature_stated": p7_temperature_stated, "P8_must_mention": p8_must_mention,
              "P9_scaled_quantities": p9_scaled_quantities, "P10_time_not_scaled": p10_time_not_scaled,
              "P11_no_guess_on_safety": p11_no_guess_on_safety}
SAFETY = {"P4_declaration_checked", "P5_no_unsafe_claim", "P6_superseded_not_offered", "P11_no_guess_on_safety"}


def run_assertions(case, rec):
    return {name: fn(case, rec) for name, fn in ASSERTIONS.items()}


# ---------------------------------------------------------------- judge
def judge_context(rec):
    parts = []
    for s in rec["spans"]:
        if s["kind"] != "tool":
            continue
        if s["is_error"]:
            parts.append(f"[{s['name']} error]\n{s['error']}")
        elif isinstance(s["result"], dict) and "hits" in s["result"]:
            parts += [f"[{h['chunk_id']}] (status: {h['status']})\n{h['text']}" for h in s["result"]["hits"]]
        else:
            parts.append(f"[{s['name']} {json.dumps(s['args'], ensure_ascii=False)}]\n"
                         f"{json.dumps(s['result'], ensure_ascii=False)}")
    return "\n\n".join(parts) or "(no context: the assistant called no tools)"


# ------------------------------------------------------------------ run
def _cases(a):
    cases = load_jsonl(CASES)
    if getattr(a, "cases", None):
        keep = set(a.cases.split(","))
        cases = [c for c in cases if c["case_id"] in keep]
    return cases


async def _generate(cases, repeat, out_path):
    from pantry_agent import PantryAgent
    done = {(r["case_id"], r["run"]) for r in load_jsonl(out_path)} if out_path.exists() else set()
    rows = []
    async with PantryAgent() as agent:
        for run in range(1, repeat + 1):
            for c in cases:
                if (c["case_id"], run) in done:  # --resume: a crashed run keeps its finished cases
                    continue
                rec = await agent.ask(c["question"], user="eval-suite")
                rec["case_id"], rec["run"] = c["case_id"], run
                rows.append(rec)
                with out_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                print(f"  run {run} [{c['case_id']}] {rec['laps']} laps, "
                      f"{'>'.join(t or '?' for t in rec['tool_sequence']) or '(no tools)'}  ${rec['cost_usd_total']:.6f}", flush=True)
    return rows


def cmd_eval(a):
    RESULTS.mkdir(exist_ok=True)
    cases = _cases(a)
    runs_path = RESULTS / f"pantry_runs_{a.tag}.jsonl"
    if not a.judge_only:
        if runs_path.exists() and not getattr(a, "resume", False):
            runs_path.unlink()
        pc._collection()
        print(f"running {len(cases)} cases x {a.repeat} through the integrated system ...")
        asyncio.run(_generate(cases, a.repeat, runs_path))
    runs = load_jsonl(runs_path)
    by_case = defaultdict(list)
    for r in runs:
        by_case[r["case_id"]].append(r)

    from w6_judge import judge_case
    previous = {}  # --judge-only reuses earlier verdicts on the SAME outputs (no new judge calls)
    prev_path = eval_path(a.tag, a.judge)
    if a.judge_only and prev_path.exists():
        previous = {(r["case_id"], r["run"], r["trace_id"]): r["judge"]
                    for r in json.loads(prev_path.read_text(encoding="utf-8"))["rows"] if r["judge"]}
    rows = []
    for c in cases:
        for rec in by_case.get(c["case_id"], []):
            checks = run_assertions(c, rec)
            failed = [n for n, ok in checks.items() if ok is False]
            judged = None
            if rec["run"] == 1 and not getattr(a, "no_judge", False):  # judge run 1 (the agreement sample)
                judged = previous.get((c["case_id"], 1, rec["trace_id"]))
                if judged is None:
                    verdict, reason = judge_case(a.judge, c, rec["rendered"], judge_context(rec))
                    judged = {"verdict": verdict, "reason": reason}
            rows.append({"case_id": c["case_id"], "mode": c["mode"], "allergy": bool(c.get("allergy")),
                         "run": rec["run"], "trace_id": rec["trace_id"], "assertions": checks,
                         "failed_assertions": failed,
                         "safety_fail": bool(set(failed) & SAFETY), "judge": judged,
                         "pass": not failed and (judged is None or judged["verdict"] == "PASS"),
                         "cost_usd": rec["cost_usd_total"], "latency_ms": rec["latency_ms_total"],
                         "tokens": rec["tokens_total"], "laps": rec["laps"]})
            flag = "PASS" if rows[-1]["pass"] else "FAIL"
            why = ", ".join(failed) + (f"{', ' if failed else ''}judge FAIL" if judged and judged["verdict"] != "PASS" else "")
            print(f"{flag}  {c['case_id']:<8} run {rec['run']}  {c['question'][:60]:<62}{why}", flush=True)
    report(rows, cases, a.tag, a.judge)


def eval_path(tag, judge="judge_v2.txt"):
    stem = Path(judge).stem
    return RESULTS / (f"pantry_eval_{tag}.json" if stem == "judge_v2" else f"pantry_eval_{tag}.{stem}.json")


def report(rows, cases, tag, judge="judge_v2.txt"):
    first = [r for r in rows if r["run"] == 1]
    per_mode = defaultdict(lambda: [0, 0])
    for r in first:
        per_mode[r["mode"]][0] += r["pass"]
        per_mode[r["mode"]][1] += 1
    print(f"\n{'mode':<26}{'pass':>6}{'n':>5}{'rate':>8}")
    for mode, (p, n) in per_mode.items():
        print(f"{mode:<26}{p:>6}{n:>5}{p / n:>8.0%}")
    n_pass = sum(r["pass"] for r in first)
    print(f"{'ALL':<26}{n_pass:>6}{len(first):>5}{n_pass / len(first):>8.0%}")

    allergy = [r for r in rows if r["allergy"]]
    unsafe = [r for r in allergy if r["safety_fail"]]
    print(f"\nALLERGY CASES ({len({r['case_id'] for r in allergy})} cases, {len(allergy)} runs): "
          f"allergen-unsafe answers {len(unsafe)}/{len(allergy)} = {len(unsafe) / max(1, len(allergy)):.0%}")
    for r in allergy:
        if r["run"] == 1 or r["safety_fail"]:
            print(f"   {r['case_id']:<8} run {r['run']}  {'UNSAFE ANSWER' if r['safety_fail'] else 'safe answer':<14}"
                  f"{'pass' if r['pass'] else 'FAIL'}  {', '.join(r['failed_assertions'])}")
    judged = [r for r in first if r["judge"]]
    costs = [r["cost_usd"] for r in rows]
    summary = {
        "tag": tag, "cases": len(first), "runs": len(rows), "suite_pass": n_pass,
        "per_mode": {m: {"pass": p, "n": n} for m, (p, n) in per_mode.items()},
        "allergy_runs": len(allergy), "allergen_unsafe_runs": len(unsafe),
        "allergen_unsafe_rate": round(len(unsafe) / max(1, len(allergy)), 3),
        "judge_fail": sum(r["judge"]["verdict"] != "PASS" for r in judged),
        "assertion_fail_counts": dict(Counter(f for r in first for f in r["failed_assertions"])),
        "cost_per_query": {"mean": round(statistics.mean(costs), 6), "p50": round(statistics.median(costs), 6),
                           "max": round(max(costs), 6)},
        "latency_s_p50": round(statistics.median(r["latency_ms"] for r in rows) / 1000, 1),
        "laps_mean": round(statistics.mean(r["laps"] for r in rows), 2),
    }
    print(f"\nsuite: {n_pass}/{len(first)} pass   judge FAIL on {summary['judge_fail']}/{len(judged)}   "
          f"cost/query mean ${summary['cost_per_query']['mean']:.6f}  p50 latency {summary['latency_s_p50']}s")
    summary["judge"] = judge
    eval_path(tag, judge).write_text(
        json.dumps({"summary": summary, "rows": rows}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"written results/{eval_path(tag, judge).name}")


# ----------------------------------------------------------- trajectory
EXTRA_ALLOWED = {"allergen": {"check_allergens", "find_substitutes"},
                 "substitution_chain": {"check_allergens", "find_substitutes"},
                 "version_history": {"check_allergens"},
                 "scaling": {"scale_recipe", "get_safe_temperature"},
                 "food_safety": {"get_safe_temperature"}, "no_guess": {"check_allergens"}}


def allowed_tools(case):
    allowed = ({"search_recipes", "get_recipe"} | set(case.get("required_tools", []))
               | set(case.get("allowed_extra", [])))
    for key, extra in EXTRA_ALLOWED.items():
        if case["mode"].startswith(key):
            allowed |= extra
    return allowed


def arg_problems(case, call):
    a, t, probs = call["args"], call["tool"], []
    rid = a.get("recipe_id")
    if t in ("get_recipe", "check_allergens", "find_substitutes", "scale_recipe"):
        if rid not in pc.VERSIONS:
            probs.append("invalid_arguments")
        else:
            v = a.get("version") or "current"
            if v != "current" and v not in pc.VERSIONS[rid]:
                probs.append("invalid_arguments")
            elif (t == "check_allergens" and case.get("allergy") and not case.get("version")
                  and v != "current" and pc.RECORDS[(rid, v)]["status"] == "superseded"):
                probs.append("checked_superseded_version")
    if t == "check_allergens":
        for x in a.get("avoid", []):
            try:
                pc.normalise_allergen(x)
            except pc.LookupError_:
                if case["case_id"] != "g01":  # g01 asks about egg ON PURPOSE
                    probs.append("invalid_arguments")
    if t == "scale_recipe":
        try:
            assert float(a.get("factor")) > 0
        except (TypeError, ValueError, AssertionError):
            probs.append("invalid_arguments")
    return probs


def score_trajectory(case, rec):
    calls = [s for s in rec["spans"] if s["kind"] == "tool"]
    seq = [c["tool"] or c["name"].split("/", 1)[1] for c in calls]
    allowed = allowed_tools(case)
    modes = []
    good = sum(1 for t in seq if t in allowed)
    if any(t not in allowed for t in seq):
        modes.append("wrong_tool")
    missing = [t for t in case.get("required_tools", []) if t not in seq]
    if missing:
        modes.append("skipped_required_tool")
    for c in calls:
        modes += arg_problems(case, c)
    if not rec["stop_reason"].startswith("completed"):
        modes.append("gave_up")
    modes = sorted(set(modes))
    return {"sequence": seq, "tool_choice_accuracy": good / len(seq) if seq else 0.0,
            "missing": missing, "modes": modes, "trajectory_pass": not modes}


def cmd_trajectory(a):
    cases = {c["case_id"]: c for c in load_jsonl(CASES)}
    runs = [r for r in load_jsonl(RESULTS / f"pantry_runs_{a.tag}.jsonl") if r["run"] == 1]
    ev = {r["case_id"]: r for r in json.loads(eval_path(a.tag, a.judge).read_text(encoding="utf-8"))["rows"]
          if r["run"] == 1}
    rows = []
    for rec in runs:
        case = cases[rec["case_id"]]
        t = score_trajectory(case, rec)
        rows.append({"case_id": case["case_id"], "mode": case["mode"], "outcome_pass": ev[case["case_id"]]["pass"],
                     **t})
        print(f"  {case['case_id']:<8} outcome={'PASS' if rows[-1]['outcome_pass'] else 'FAIL'} "
              f"traj={'PASS' if t['trajectory_pass'] else 'FAIL'}  acc={t['tool_choice_accuracy']:.2f}  "
              f"{'>'.join(t['sequence']) or '(no tools)'}  {t['modes'] or ''}")
    n = len(rows)
    out_rate = sum(r["outcome_pass"] for r in rows) / n
    traj_rate = sum(r["trajectory_pass"] for r in rows) / n
    calls = sum(len(r["sequence"]) for r in rows)
    acc = sum(r["tool_choice_accuracy"] * len(r["sequence"]) for r in rows) / max(1, calls)
    summary = {"tag": a.tag, "cases": n, "tool_calls": calls,
               "tool_choice_accuracy_per_call": round(acc, 3),
               "tool_choice_accuracy_mean_per_case": round(statistics.mean(r["tool_choice_accuracy"] for r in rows), 3),
               "outcome_pass_rate": round(out_rate, 3), "trajectory_pass_rate": round(traj_rate, 3),
               "gap_outcome_minus_trajectory": round(out_rate - traj_rate, 3),
               "right_answer_wrong_path": [r["case_id"] for r in rows if r["outcome_pass"] and not r["trajectory_pass"]],
               "wrong_answer_right_path": [r["case_id"] for r in rows if not r["outcome_pass"] and r["trajectory_pass"]],
               "mode_counts": dict(Counter(m for r in rows for m in r["modes"]))}
    print(f"\ntool-choice accuracy : {acc:.1%} of {calls} tool calls")
    print(f"outcome pass rate    : {out_rate:.0%}   trajectory pass rate: {traj_rate:.0%}")
    print(f"GAP (outcome - traj) : {out_rate - traj_rate:+.0%}")
    print(f"right answer, wrong path: {summary['right_answer_wrong_path']}")
    print(f"wrong answer, right path: {summary['wrong_answer_right_path']}")
    print(f"path failure modes   : {summary['mode_counts']}")
    (RESULTS / f"pantry_trajectory_{a.tag}.json").write_text(
        json.dumps({"summary": summary, "rows": rows}, indent=2, ensure_ascii=False), encoding="utf-8")


# ------------------------------------------------------------ agreement
def cmd_agreement(a):
    labels = json.loads((ROOT / (getattr(a, "labels", None) or f"pantry_labels_{a.tag}.json")).read_text(encoding="utf-8"))
    ev = {r["case_id"]: r for r in json.loads(eval_path(a.tag, a.judge).read_text(encoding="utf-8"))["rows"]
          if r["run"] == 1}
    agree, rows = 0, []
    for lab in labels["labels"]:
        j = ev[lab["case_id"]]["judge"]["verdict"]
        ok = j == lab["label"]
        agree += ok
        rows.append((lab["case_id"], lab["label"], j, ok, ev[lab["case_id"]]["judge"]["reason"], lab["why"]))
    n = len(rows)
    print(f"\n{a.judge} vs hand labels on integrated outputs ({a.tag}): {agree}/{n} = {agree / n:.1%}"
          f"   (bar 85.0%: {'CLEARS' if agree / n >= 0.85 else 'DOES NOT CLEAR'})\n")
    for cid, hl, j, ok, jr, hw in rows:
        if not ok:
            print(f"[{cid}] label={hl} judge={j}\n   judge: {jr}\n   label: {hw}")
    (RESULTS / f"pantry_agreement_{a.tag}.{Path(a.judge).stem}.json").write_text(json.dumps(
        {"judge": a.judge, "agreement": round(agree / n, 3), "n": n, "agree": agree,
         "disagreements": [{"case_id": r[0], "label": r[1], "judge": r[2], "judge_reason": r[4],
                            "label_why": r[5]} for r in rows if not r[3]]}, indent=2, ensure_ascii=False),
        encoding="utf-8")
