# Week 11 Practical — Task Set B — results

**Find the dairy-free swap that wasn't.** Production app: `w11_app.py`, a workflow of
retrieval (local hybrid search) → tools (MCP recipe server) → one generation call
(`gemini-flash-lite-latest`, temperature 0). Every request is logged with its input and
output to `logs/w11_requests.jsonl`.

## Headline

| Req | Result | File |
|---|---|---|
| 1 Drill | Found in **00:18** by the **output-text** slice. Missing field named: `diet_constraints` + `constraint_violation` | `drill.md` |
| 2 Trace | `e6fa2dbb1746`, prompt **p-v2**: retrieval 310.8 ms, tools 2.8 ms, generation 4,517.5 ms / 1,071 tokens / $0.0002085, 5 context ids | `trace.json` |
| 3 Loop | **RED 18/26** (p-v2, w11_r01 FAIL) → **GREEN 20/26** (p-v5, w11_r01 PASS). Repeats: w11_r01 **0/3 → 3/3** | `w11_eval_case.jsonl`, `suite_output.md` |
| 4 Fix | **p-v2 → p-v3 ✗ → p-v4 ✗ → p-v5 ✓**. The fix that worked is in the **retrieval layer** | `w11_app.py`, `knowledge/allergen_notes.md` |
| 5 Cost / 10x | **100% of cost is generation**. At 10x the **rate limit** breaks first: 20 calls/min vs a 15/min cap | `cost_by_stage.md`, `tenx.md` |

## Requirement 1: the drill

See `drill.md`. A separate, freshly started agent with no memory of this session got only
the vague complaint, the log and `w11_logq.py`. It found the planted trace in 00:18 by
searching **output** text (`find --text "dairy"`), because the complaint describes what
the assistant *said*. Searching inputs alone gives 14 dairy-free questions, 13 of them
answered correctly. Honest limits: the log is 100 requests, the finder was an AI agent
rather than a human squadmate, and timestamps are simulated.

## Requirement 2: the trace

`trace.json`: the full record, with per-span latency, tokens and cost, `prompt_version:
p-v2`, and `context_ids` = `ragi-koozh-05::structure::3, ::2, ::1, ::0,
dosa-batter-02::structure::3`. The spans show the root cause:
`substitute_ingredient(ragi-koozh-05, dairy)` returned **`"swaps": []`**, because the tool
checks only the ingredient table. Curd chilli sits on the card's "Serve with" line, and
the card says "Vegan … as written".

## Requirement 3: the loop, RED → GREEN

`w11_r01` = the found request turned into a case (`expect_dairy_free: true`), appended
to the Week-6 suite. It is checked by the Week-6 judge **plus a new deterministic
assertion, A5**: a dairy-free answer that mentions curd chilli must say outright that it
contains dairy.

| | p-v2 (RED) | p-v5 (GREEN) |
|---|---|---|
| Suite (26 cases) | **18/26** | **20/26** |
| w11_r01 in the suite run | FAIL (A5) | **PASS** |
| w11_r01, 3 more fresh runs | 0/3 | **3/3** |
| 6 dairy-free probe questions | 2/6 (just the 2 thayir questions) | **5/6** |

**A silent regression can't hide in those counts, and here is the proof.** p-v5 changes the
request for exactly 1 of 26 cases (`python w11_scope.py` → `['w11_r01']`). For c01–c25 the
model got byte-identical requests in both runs, so the 5 other flips (c03 and c11 PASS→FAIL,
c05, c09 and c10 FAIL→PASS) are run-to-run noise. That noise level was measured: p-v4 also
sends p-v2's exact requests for c01–c25 and moved 3 cases. The full suite was re-run after
every fix, never just the new case.

**Robustness beyond the one case.** The one p-v5 probe failure was a real slip that **A5
caught and the judge passed**. Curd chilli was listed under "What to avoid", but the
answer said "…**making it dairy-free**". The same question then passed 3/3. Across all
fresh dairy-free runs: **p-v5 12/13 correct, p-v2 2/9** (0/7 for koozh).

## Requirement 4: the fix, the two that failed, and the canary

| Version | Change (one at a time) | Suite | w11_r01 | Why |
|---|---|---|---|---|
| p-v2 | shipped Thu 1 Oct: "be helpful, fill small gaps with general knowledge" | 18/26 | ✗ A5 | curd chilli offered as a dairy-free side |
| p-v3 | + one global dairy rule in **every** prompt | 21/26 | ✗ judge | its plant-yoghurt examples were echoed as outside knowledge; **c01 "How much salt?" regressed** (a dairy note leaked in) |
| p-v4 | the rule attached **only** to dairy-free requests | 21/26 | ✗ judge | right answer, but "curd chilli contains dairy" had **no source to cite**: the judge called it ungrounded |
| **p-v5** | the dairy facts moved into a **citable knowledge chunk** pinned into retrieval for dairy-free requests; the prompt keeps only the instruction | **20/26** | **✓** | the model cites `[allergen-notes::dairy::0]` |

**The lesson:** in a grounded RAG app, a fact the model needs belongs in the
**retrieval layer**, where it can be cited, not in the prompt. A prompt can carry
instructions, but a fact it carries has no source. p-v4 proved that: its answer was right,
and the grounded judge still failed it as made up.

How p-v5 works: `knowledge/allergen_notes.md` sits outside the search index. When the
rule-based detector flags a request as dairy-free, the app pins
`allergen-notes::dairy::0` into the context and records it in the retrieval span as
`pinned_ids`. All other requests (85% of logged traffic) get exactly p-v2's request.
Cost: about 217 extra input tokens, roughly $0.00002, only on dairy-free requests
(estimated from characters / 4).

**Version bumps recorded:** each is a separate commit, made **before** its suite run,
with the failures committed as failures (`git log --oneline`: a4fa27c p-v3, 35e9cd7
p-v3 FAILED, d4b2e45 p-v4, ece8080 p-v4 FAILED, 91b651d p-v5). Old versions stay in
`PROMPTS`, so every run can be reproduced.

**Canary and rollback (two lines):**

> **Canary:** send 50% of users (hash of user_id) to p-v5. It changes only dairy-free requests, where p-v2 is already wrong 7 of 7 times, so the blast radius is small. Promote when 20 live dairy-free answers have run A5 with at most 1 hit (the measured residual is ~1 in 13) and a judge-fail rate no worse than p-v2's (about 3 weeks at today's 15 dairy-free requests/week).
> **Rollback:** flip the `prompt_version` flag back to p-v2 (no deploy, effective on the next request) if the canary's error, latency or judge-fail rate exceeds p-v2's. Never on A5 alone: p-v2 fails A5 on nearly every koozh request, so rolling back would restore that bug.

Why 50% and not the usual 10%: at 100 requests a week, a 10% canary sees about 1.5
dairy-free requests a week, so it would take months to show anything.

## Requirement 5: cost by stage and 10x

`cost_by_stage.md`: the found request cost **$0.0002085**: retrieval $0, tools $0,
generation $0.0002085 (**100%**). Mean across the log: $0.0001392 per query. 75% of median
generation time is spent waiting on free-tier pacing.

`tenx.md`: **at 10x, the rate limit breaks first.** The busiest minute had 2 requests, so
10x means 20 model calls/min against Gemini's free-tier cap of 15/min (from a real 429:
`quotaValue: 15`), while 10x cost is only about $0.14/week.

## The grader had bugs too: A5's history

Assertion A5 is the check that turns this failure RED. It needed three versions, and each
fix was checked against data rather than eyeballed:

| A5 | Rule | Agreement with 45 hand-labelled dairy-free answers |
|---|---|---|
| v1 | warning must be in the same **sentence** | false FAIL on a correct p-v3 answer |
| v2 | same **line**, with broad warning words (avoid, skip, without …) | **42/45**: 1 false FAIL (correct p-v5 answer), **2 false PASS** ("Without the buttermilk … you can still enjoy it with curd chilli") |
| v3 | must **say it contains dairy** on a line naming curd chilli; hedges don't count | **45/45** |

`python w11_a5_check.py` reproduces this. A5 v3 was committed (7f0d5ab) **before** the
GREEN run, and it then caught a fresh failure the judge missed (the "making it
dairy-free" slip). Caveat: the 45 labels were written after seeing the outputs, not blind.

## Honest limitations

- **Residual failure rate:** about 1 in 13 fresh p-v5 dairy-free answers still contained a
  wrong sentence. The canary's live A5 check exists for exactly this.
- **Detection is rule-based.** "I can't have milk products" does not match the dairy
  pattern, so it wouldn't trigger the pinned note. That is the same gap as the drill's
  missing `diet_constraints` field.
- **A5 covers curd chilli only.** The allergen note teaches the model every dairy item, but
  only curd chilli has a deterministic test. Ghee in a tempering would need its own case.
- **Only dairy has an allergen note.** Hidden nuts, sesame and so on are not covered yet.
- **p-v2's outside-knowledge clause** causes most remaining suite failures (c03, c06, c07,
  c11, c16, c25: the judge flags general cooking tips). It is a separate, pre-existing
  issue, left alone so this change stays one change.
- **Noise:** the suite count moves about ±3 between runs with identical requests. Counts
  alone can't prove a fix, which is why repeats and the scope proof are included.
- **Bonus not attempted:** adding `constraint_violation` to the log and re-running the drill
  against a second planted answer.

## Files

| File | Contents |
|---|---|
| `drill.md` | time-to-find, slice, finder's commands, missing field |
| `trace.json` | the found trace, every span |
| `w11_eval_case.jsonl` | the new case w11_r01 (also appended to `w6_cases.jsonl`) |
| `suite_output.md` | suite output RED then GREEN, verbatim, plus the failed attempts and the noise proof |
| `cost_by_stage.md`, `tenx.md` | cost per stage, 10x answer |
| `w11_app.py` | the app, prompts p-v1..p-v5, conditional notes, allergen-note pinning |
| `knowledge/allergen_notes.md` | the dairy facts the cards leave out (the p-v5 fix) |
| `w11_logq.py` | the log query tool used in the drill |
| `w11_suite.py`, `w11_repeat.py`, `w11_scope.py`, `w11_a5_check.py` | suite, repeat runs, which-cases-changed proof, A5 validation |
| `w6_assertions.py` | A5 (v3) |
| `w11_traffic.py`, `w11_plant.py`, `w11_probe.py` | traffic simulation, the plant, the probe that found a real failure |
| `results/w11_suite_p-v{2,3,4,5}.json`, `w11_suite_p-v5_run1_a5v2.json` | every suite run, row by row |
| `results/w11_repeat_p-v2.json`, `w11_repeat_p-v5.json`, `w11_repeat_p-v5_q.json` | the repeat runs |
| `results/w11_a5_validation.json` | 45 labelled dairy-free answers |
| `results/w11_drill_answer_key.json`, `w11_probe_out.json` | sealed answer key, probe outputs |
| `logs/w11_requests.jsonl` | the 100-request production log |
