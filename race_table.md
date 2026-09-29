# race_table.md — kitchen squad vs single agent

Same 10 Week-6 cases (seeded draw, `w10_cases.json`), same judge (`judge_v2.txt`),
same model (`gemini-flash-lite-latest`, temperature 0), same two MCP servers.

Cases: `c05`, `c08`, `c10`, `c12`, `c13`, `c14`, `c15`, `c16`, `c17`, `c22`

| Metric | Single agent | Kitchen squad | Squad vs single |
|---|---|---|---|
| **Pass rate** (Week-6 judge) | 10/10 | 10/10 | +0 |
| **p50 latency** (net of throttling) | 46.2 s | 85.3 s | 1.8x |
| **p99 latency** (net of throttling) | 104.5 s | 157.1 s | 1.5x |
| **Total tokens** (10 questions) | 49,167 | 70,482 | 1.4x |
| **Cost per question** (modelled) | $0.000550 | $0.000836 | 1.5x |

Raw wall-clock latency, including free-tier pacing and 429 backoff:

| | Single | Squad |
|---|---|---|
| p50 wall | 46.2 s | 85.7 s |
| p99 wall | 105.7 s | 164.6 s |
| LLM calls (10 questions) | 32 | 60 |

**Context re-send multiplier: 70,482 multi / 49,167 single = 1.4x. Largest share: "manager -> substitution_worker" hand-off, 56,504 tokens = 80% of all multi-arm tokens (53,125 of them re-sent prompt tokens, over 37 calls).**

## Per case

| Case | Question | Single | Squad | Single tok | Squad tok | Single net s | Squad net s |
|---|---|---|---|---|---|---|---|
| c05 | How long to ferment? | PASS | PASS | 3,520 | 425 | 42.3 | 19.6 |
| c08 | How do I keep the mango pickle from spoiling? | PASS | PASS | 3,652 | 3,971 | 106.8 | 123.2 |
| c10 | What rice do I use for appam? | PASS | PASS | 3,550 | 3,730 | 35.0 | 82.4 |
| c12 | What dal goes into dosa batter? | PASS | PASS | 3,528 | 3,712 | 47.2 | 68.2 |
| c13 | Which recipe has the highest salt percentage? | PASS | PASS | 9,836 | 19,579 | 46.4 | 136.4 |
| c14 | Which recipe ferments for the longest time? | PASS | PASS | 9,666 | 9,949 | 81.5 | 88.2 |
| c15 | Which of these recipes uses the most water? | PASS | PASS | 5,081 | 15,611 | 46.0 | 148.4 |
| c16 | Which oil is used on the dosa tawa? | PASS | PASS | 3,538 | 3,747 | 40.6 | 63.6 |
| c17 | Is there sesame in the mango pickle? | PASS | PASS | 3,302 | 6,096 | 47.4 | 157.9 |
| c22 | How much rock salt goes into the idli batter? | PASS | PASS | 3,494 | 3,662 | 29.6 | 63.8 |

## Where the squad's tokens went (all 10 questions)

| Hand-off | LLM calls | Tokens | Share | Of which re-sent prompt |
|---|---|---|---|---|
| manager -> substitution_worker | 37 | 56,504 | 80% | 53,125 |
| substitution_worker -> manager (re-read) | 10 | 7,855 | 11% | 7,367 |
| user -> manager (plan) | 10 | 4,253 | 6% | 3,866 |
| manager -> allergen_worker | 2 | 969 | 1% | 879 |
| allergen_worker -> manager (re-read) | 1 | 901 | 1% | 871 |

## Notes on the numbers

- **p99 over 10 samples** is interpolated between the two slowest runs, so it is effectively the worst case; it is reported because it is the number a user notices.
- **Net latency** subtracts time spent sleeping in `ask.call_llm` (4.5 s free-tier pacing between calls, plus 429 backoff). The free tier serialises every call, so the squad cannot run its two workers in parallel here: that possible advantage is not measurable on this quota.
- **Cost** uses the same modelled rate card as Weeks 7-9 ($0.10 / $0.40 per 1M input / output tokens); the ratio between arms does not depend on it.
- **Judge tokens are excluded** from both arms; the same judge scored both.

## Judge caveat: a post-hoc read, not a replacement number

The official pass rate above is the **Week-6 judge's**, as the task requires. After
seeing its verdicts I read all 20 answers against the cards myself. That read is
**not blind**, so it does not replace the judge's number, but four of its findings are
checkable facts:

| Case | Single agent | Squad | Checkable fact |
|---|---|---|---|
| c14 | **wrong**: "Dosa and Kadumanga tie, 10 to 14 hours / days" | right: Kadumanga | dosa ferments 10-14 **hours**, Kadumanga 10-14 **days** |
| c15 | **wrong**: "Appam uses the most water" (compared 3 recipes) | right: Ragi Koozh | Ragi Koozh uses **1500g** water, Idli ~720g; neither was checked |
| c13 | right recipe, **wrong figure**: 12.63% on a 1,188g total | right recipe, **wrong figure**: 11.69% on 1,283g | the ingredients sum to **1,278g**; the card states **15%** |
| c05 | answered for Appam only; the question named no recipe | asked which recipe, but suggested dishes not in the corpus | judgement call |

**Why the judge missed c14 and c15:** `judge_v2.txt` checks claims against the context
the system retrieved. An agent that retrieves only part of the corpus is therefore
graded correct on that part. The judge was validated at 89% on RAG answers in Week 6,
**never on agent answers**, and this is the gap. The Week-6 lesson applies again:
validate the instrument before trusting its number on new outputs.
