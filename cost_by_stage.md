# cost_by_stage.md — cost per query, split by stage

## The found request (trace `e6fa2dbb1746`)

| Stage | What runs | Latency | Tokens | Cost |
|---|---|---|---|---|
| **retrieval** | hybrid search (local MiniLM + BM25, RRF) | 310.8 ms | 0 | **$0.0000000** |
| **tools** | `recipes.substitute_ingredient` over MCP (local) | 2.8 ms | 0 | **$0.0000000** |
| **generation** | 1 call to `gemini-flash-lite-latest` | 4,517.5 ms | 733 in + 338 out | **$0.0002085** |
| **total** | | 4,831.3 ms | 1,071 | **$0.0002085** |

**100% of the money is generation.** Retrieval and tools run locally: they cost CPU
time and latency, not API dollars. Of the 4,517.5 ms generation time, 2,859.9 ms was
spent waiting on the free-tier pacing in `ask.call_llm`, not on the model.

## Across all 100 logged requests

| | Value |
|---|---|
| Cost per query | mean **$0.0001392**, p50 $0.0001200, max $0.0003728 |
| Retrieval / tools / generation share of cost | $0 / $0 / $0.013922: **0% / 0% / 100%** |
| p50 latency by stage | retrieval 263.9 ms, tools 0.0 ms, generation 4,210.3 ms |
| p50 generation time spent waiting on pacing | 3,140.8 ms (75% of generation time) |

**What this means for cost work:** any saving has to come from generation:
fewer/shorter prompts, a cheaper model for easy questions, or prompt caching. Making
retrieval faster saves no money. This attribution comes **before** any optimisation
(the task's first listed mistake); no optimisation was applied this week.

Cost is **modelled** at $0.10 / $0.40 per 1M input / output tokens (the rate card used
since Week 7), not billed: the free tier charges nothing.

## What the fix (p-v5) adds

p-v5 pins one allergen-note chunk and a short instruction into **dairy-free requests
only**: about 217 extra input tokens, roughly **$0.00002 per dairy-free request**
(estimated from characters / 4). That's 15 of 100 logged requests, so the mean cost per
query rises by about $0.000003 (+2%). The other 85% of requests are byte-identical to p-v2
(`w11_scope.py`). Retrieval and tools still cost $0, and it adds no model calls, so the
10x answer is unchanged.
