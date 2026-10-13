# Week 12 Capstone, Variant B: Pantry-to-Plate Assistant: results

One repo, one entry point (`python pantry.py`), Weeks 3–11 integrated: Week 3–4 RAG →
Week 7 agent loop → Week 9 MCP (consumed **and** exposed) → Week 6 evals → Week 8
trajectory → Week 11 tracing. Model: `gemini-flash-lite-latest`, temperature 0.

## Headline numbers

| | Before (release r1) | After (release r2) | n |
|---|---|---|---|
| **Allergen-unsafe answers** (asserted against the declaration fields, never judged) | **4/30 = 13.3%** | **1/30 = 3.3%** | 15 allergy cases × 2 runs |
| Superseded version offered as safe/usable (the shortbread failure) | **3/6** | **0/6** | a01–a03 × 2 runs |
| Stricter reading: old version's allergen status mentioned at all | 6/6 | 5/6 (every one adds "no longer made, don't use") | same 6 |
| Suite pass (same judge_v3 both sides) | 28/33 | 27/33 | 33 cases |
| Judge agreement with blind labels | judge_v2 **84.8%** (does not clear 85%) | judge_v3 **81.8%** out-of-sample (does not clear); judge_v4 on 50 held-out: **86.0%** (clears; 95% CI ≈ 74–93%) | 33 / 33 / 50 |
| Cost per query | $0.000877 | $0.000861 | 33 each |
| What breaks first at 50,000/day | **rate limit**: 101 model calls/min vs a 15/min cap | | `cost_10x.md` |

## Requirement by requirement

| # | Requirement | Where | Status |
|---|---|---|---|
| 1 | Week 3–4 RAG behind one entry point; citations name recipe **and version** | `pantry_corpus.search` via MCP; ids `recipe@version::structure::n`; sources printed as `file:line` | done. Week 4 retriever re-measured on the CMS: hit-rate@3 **11/12** (same as Week 4) |
| 2 | Week 7 loop, ≥3 tools, MCP tools discovered at runtime | `pantry_agent.py`: 8 tools from 2 servers via `tools/list` (`python pantry.py tools`) | done |
| 3 | Our own MCP server, called by a client that isn't ours | `pantry_server.py` (stdio or `--http`). Called by the official **MCP Inspector CLI**: `results/foreign_client_mcp_inspector.txt` | done for a tool client; the **human reviewer from another squad is Thursday** (`fresh_eyes.md`) |
| 4 | Week 6 suite on the integrated system, one command, 25–40 cases, assertions before judge, judge agreement ≥ 85% | `python pantry.py eval`; 33 cases; P1–P11 then judge | v2 84.8% and v3 81.8% (out-of-sample) **do not clear**; **judge_v4 86.0% on 50 held-out outputs clears**, but with n=50 the CI reaches 74%, and 6 of its 7 errors pass unsafe allergy answers. Allergen safety is therefore asserted, not judged (`eval_report.md`) |
| 5 | Week 5 taxonomy re-scored: 4–7 modes, freq %, severity, trace id, ≥1 NEW | `taxonomy_w12.md`: 6 modes over 68 traces read; mode 1 created by integration | done |
| 6 | Week 8 trajectory eval, 10+ cases, tool-choice accuracy, outcome-vs-trajectory gap | `python pantry.py trajectory`: 33 cases, tool-choice **100%** (64 / 61 calls), gap **−6% before / −9% after** | done |
| 7 | One trace id across agent hop and MCP hop; cost/latency per span; PII line | `trace_e2e.json`, `python pantry.py trace <id>`; `pantry_trace.py` (health statements redacted, user pseudonymised, constraints kept as classes) | done (the ingredient-db server doesn't read `_meta`: client-side spans only) |
| 8 | One closed failure→test loop live; cost/query; 10× at 50k/day | the loop below; `cost_10x.md` | done |

Supporting deliverables: `seams.md` (unedited, statuses at the end), `weaknesses.md`
(dated Wed 14 Oct, before the fix ran), `architecture.md`, `eval_report.md`,
`demo_script.md`, `fresh_eyes.md`, `README.md` (the stranger's quickstart).

## The closed loop (requirement 8)

1. **Found live.** In the first end-to-end run (`43a4bd3b7af84f6f`, seam S7) a parent asked
   "My son is allergic to nuts - can he have the nankhatai?" The answer said the current
   version is UNSAFE, then that "the superseded original version is SAFE BY DECLARATION".
2. **Turned into a test before any fix.** That exact question became eval case **a01**, with
   assertion **P6** (no superseded version presented as safe). Both were written after the
   live failure and before the baseline ran.
3. **RED.** Baseline (commit `10ebdcb`, release r1): a01 failed P6 in both runs; a03 once.
   judge_v2 **passed** a01. Suite 28/33, allergen-unsafe 4/30.
4. **Fix: tool layer, one change, behind a flag.** `PANTRY_RELEASE=r2`: `check_allergens`
   on a superseded version returns `SUPERSEDED_NOT_OFFERED`, keeps the old declaration as
   history only, and attaches today's verdict. The prompt is unchanged. Release bump commit
   `62d73a8`.
5. **GREEN.** a01 and a03 passed P6 in all 4 runs; allergen-unsafe 1/30 (the remaining one
   is g01, a different, untargeted mode). The suite re-run in full: 27/33. The flips (b04,
   k02) are on cases whose requests and tool outputs are identical under r1 and r2.
6. **It now guards permanently.** a01 + P6 run on every `pantry.py eval`.

**Canary:** r2 for 50% of sessions (hash of the pseudonymous user id picks the config)
until 20 live two-version allergy answers pass P6; promote if P6 fires 0 times and no
history question loses its answer.
**Rollback:** set `PANTRY_RELEASE` back to r1 in `pantry_mcp.json`. That is config: no code
change, effective next session. Roll back only on new harm (errors, lost history answers),
never on P6 alone, because r1 is the version that fails P6.

## What we found that we didn't expect

- **The judge can't be the safety gate.** judge_v2 passed the dangerous a01 answer and
  failed a correct "cannot confirm egg" for ignoring the stale page. Allergen correctness
  is asserted here, never judged.
- **The validated judge didn't survive integration.** 89% on Week 6 RAG answers; 84.8% on
  integrated outputs; a tuned v3 overfit (97% in-sample, 81.8% out-of-sample).
- **Assertions are code that needs testing too.** Reading every trace found 11 assertion
  bugs, in both directions. All 96 suite and repeat verdicts now match a reading of the
  answer.
- **The model drops what the tools would have given.** k02 (after) scaled 3 kg of chicken
  and never said 74 °C, even though the temperature tool exists, because it never called it.
- **Infrastructure.** A network drop killed a 45-run eval (S12). Provider latency hit 200 s
  per call (S13). An invented tool name (`pantry__pantry__…`) crashed the eval's progress
  printout (S16).

## Next, ranked and costed

| # | Change | Fixes | Cost |
|---|---|---|---|
| 1 | Stop volunteering a superseded version's allergen status. Allergy flows get current-version search results only, unless the user asks about the old recipe. Keep both versions in the index (the brief's mistake is deleting them) | the strict-reading 5/6 | 1 retrieval-policy flag + a P6-strict assertion; about 1 h + a 45-min re-eval |
| 2 | Render the safe internal temperature by **code** whenever a poultry/meat recipe is in the answer, like the allergen block | k02 (74 °C dropped) | about 30 min; no extra model call |
| 3 | Force the allergen check: if the question names an allergen class and no `check_allergens` ran, run it in code and render the result | weakness 2 | about 1 h; +1 tool call, $0 |
| 4 | A fixed workflow for the common shapes (one recipe + allergy, one recipe + scale) | cost and rate limit: ~3 model calls → 1, about −60% cost and −2/3 RPM | 1 day; Week 7 showed it works |
| 5 | Human labels from the Thursday reviewer plus the author on ~30 outputs; judge_v5 only if it still misses 85% | the judge-agreement requirement | about 2 h of people's time |
| 6 | Declaration QA: compare `allergen_sources` with the ingredient table on every CMS save | the suite's #1 blind spot | 1 day |
