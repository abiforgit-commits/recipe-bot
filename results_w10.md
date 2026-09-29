# Week 10 Practical — Task Set B — results

**Race the kitchen squad against your single agent.**
Model `gemini-flash-lite-latest`, temperature 0. Both arms use the same two MCP servers
from Week 9, the same 10 Week-6 cases and the same Week-6 judge.

## Headline

| | Single agent | Kitchen squad |
|---|---|---|
| Pass rate (Week-6 judge) | 10/10 | 10/10 |
| p50 / p99 latency (net of throttling) | 46.2 s / 104.5 s | 85.3 s / 157.1 s |
| Total tokens, 10 questions | 49,167 | 70,482 |
| Cost per question (modelled) | $0.000550 | $0.000836 |

**Re-send multiplier 1.4×**, and 80% of it is one hand-off: manager → substitution
worker. **Verdict: kill the squad**: it ties on quality and loses on the other three
numbers. On an injected 500 it **retried once, then degraded silently**.

## Requirement 1: same cases, same judge

- **The cases were drawn, not chosen.** `random.Random(20260929).sample` picked 10 from
  Week 6's c01–c25 (r01/r02 excluded: they replay c06/c10 and aren't runnable
  questions). The list was committed in `4db0c60` **before either arm ran**.
- **The cases:** c05, c08, c10, c12, c13, c14, c15, c16, c17, c22.
- **Same judge:** `judge_v2.txt` through `w6_judge.judge_case`, unchanged. Both arms are
  judged against the raw tool outputs they retrieved.
- **Single arm:** `w9_agent.run`, the Week 9 agent, unmodified, with 6 tools on 2 servers.
- **Multi arm:** `w10_squad.py`. A manager with no tools, a substitution worker with only
  the recipes server's 4 tools, and an allergen worker with only the ingredient_db
  server's 2 tools. Each worker sees only the task text the manager writes. The
  manager's rules copy the single agent's rules word for word.
- **Order:** the arms were interleaved per case, so drift over time hits both equally.

## Requirement 2: four numbers × two arms

See `race_table.md`. Latency is wall-clock around each request, including MCP server
start-up. The harness also counts time spent sleeping in `call_llm`.

**Correction of an earlier claim.** During setup I said the 96 s smoke test was mostly
rate-limit backoff. It wasn't: across the whole race only **one** 15 s backoff occurred
(c15, squad). Almost all of the latency is the model's own response time, so the
"net" and "wall" columns barely differ.

**Honesty note on p99:** with 10 samples, p99 is interpolated between the two slowest
runs, so it is effectively the worst case. I report it because a user notices it.

## Requirement 3: multiplier and attribution

> 70,482 multi / 49,167 single = **1.4×**. Largest share: the **manager →
> substitution_worker** hand-off, 56,504 tokens = **80%** of all squad tokens. 53,125 of
> those are prompt tokens re-sent across that worker's 37 LLM calls.

Where the rest went is in `handoffs.log`, which records every hand-off with its token
count; the hand-offs in each case add up exactly to that case's total.

**Why 1.4× and not the 9× the task warns about:** each worker gets a short task and two
to four tools, never the whole corpus or the other worker's output. The expense is
concentrated in the substitution worker's own tool loop, which re-reads recipe cards on
every lap. It peaks on the cross-recipe comparisons: c13 took the squad 19,579 tokens
against the single agent's 9,836, because the manager sent the worker off twice.

## Requirement 4: injected worker failure

See `failure_case.md`. On c17 (declared in advance), every call to the allergen worker
returned a 500. The manager **retried once, then degraded silently**. It answered "contains
gingelly (sesame) oil", which traces to real substitution-worker output, so it was not a
lie. But it never told the user the allergen check had failed. It got this case right
only because the ingredient's *name* contains "sesame".

## Requirement 5: verdict

See `verdict.md`: 10 lines, with the sunk-cost bias named on line 1 and four numbers cited.
**Kill the squad.**

## The finding that matters most: the judge is blind to under-retrieval

After the judge scored everything 10/10 against 10/10, I read all 20 answers against
the cards myself (post-hoc, not blind). The **single agent was factually wrong on c14
and c15**, both cross-recipe comparisons, and the squad was right on both:

- **c14:** the single agent says Dosa and Kadumanga "tie at 10 to 14 hours / days". It
  treated hours and days as the same unit.
- **c15:** the single agent compared only 3 of 6 recipes and never saw Ragi Koozh's
  1,500g of water.

The judge passed both. Its reason for c15, "correctly analyzed the water content across
the three recipes", shows why: **it grades an answer against whatever the agent
retrieved, so an agent that retrieves too little is graded correct on the little it
found.** The judge was validated in Week 6 on RAG answers, not on agent answers. Also,
both arms computed a salt percentage for c13 on a wrong ingredient total, and the judge
called that "correctly calculated" without checking the arithmetic.

The official pass rate stays the judge's, because switching to my own labels after
seeing the results would be moving the ruler. This caveat changes the next experiment,
not the verdict:
1. blind-label these 20 answers to validate the judge on agent output, and
2. fix the single agent's comparison retrieval at 1.0× cost, then re-race.

## Honest limitations

- **n = 10**, one run per arm per case, at temperature 0. One case is 10 points of pass rate.
- **Parallelism untested.** `call_llm` is synchronous and paced, so the two workers never
  run concurrently. The one plausible latency advantage of a squad could not be measured.
- **The failure injection is one case, persistent 500.** The "silent degrade turns into
  a lie" risk for hidden allergens is predicted, not run.
- **The bonus (AgentCard + A2A task lifecycle) was not attempted.**

## Files

| File | Contents |
|---|---|
| `w10_cases.json` | the 10 drawn cases, seed, committed before any run |
| `w10_squad.py` | the manager and two narrow workers |
| `w10_race.py` | `run` / `judge` / `fail` harness, with the sleep-accounting latency counter |
| `w10_report.py` | builds the race table, hand-off log and multiplier from raw rows |
| `race_table.md` | 4 metrics × 2 arms, per-case table, token attribution, judge caveat |
| `handoffs.log` | every hand-off with its token count |
| `failure_case.md` | the injected 500 and what the orchestrator did |
| `verdict.md` | 10 lines, kill |
| `results/w10_race_rows.jsonl`, `w10_judged.jsonl`, `w10_failure_c17.json`, `w10_summary.json` | raw data |
