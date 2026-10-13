# Cost per query, and what breaks first at 50,000 queries a day

**One line:** at 50,000 queries/day the **model rate limit breaks first**. 50,000 ×
2.91 model calls = **101 model calls/minute on average** against the **15/minute** cap
this project gets today (a real 429: `quotaValue: 15`). That is **6.7× over the cap
before any meal-time peak**, while cost is only **$43.85/day**.

## Cost per query, by span (33 baseline eval queries, `results/pantry_runs_before.jsonl`)

| | Value |
|---|---|
| Cost per query | mean **$0.000877**, p50 $0.000839, p95 $0.001633, max $0.002083 |
| Where the money goes | **100% model calls** ($0.028925 of $0.028925). The MCP servers, retrieval and every tool cost $0 |
| Model calls per query | mean **2.91** (p50 3, max 6): the agent loop's laps |
| Tool calls per query | mean 1.94 (search 300 ms p50; every exact-match tool ≤ 14 ms) |
| Tokens per query | mean **8,161**, of which **98% are prompt tokens**: each lap re-sends the whole conversation and the tool results |
| Latency per query | p50 13.3 s, p95 19.3 s. **65% of model time is free-tier pacing** (269 s of 414 s); net of pacing, p50 is 4.2 s |
| Tools' share of latency | 5.7% |

Cost is **modelled** at $0.10 / $0.40 per 1M input / output tokens (the rate card used
since Week 7). The free tier bills nothing.

## The 10× plan

| | Today (free tier) | 50,000/day | 500,000/day |
|---|---|---|---|
| Model calls/min (average) | ≤ 15 (capped) | **101** (6.7× the cap) | **1,010** (67× the cap) |
| Input tokens/min (average) | | 283k | 2.83M |
| Cost (modelled) | | **$43.85/day** ($1,316/month) | $438.50/day ($13,155/month) |
| Request + span logs | | 0.39 GB/day | 3.9 GB/day |

**What breaks, in order:**

1. **The rate limit, at about 7,400 queries/day.** That's 15 RPM ÷ 2.91 calls per query
   × 1,440 minutes, and it assumes perfectly flat traffic. Real traffic peaks at meal
   times, so the wall comes sooner. Gemini limits are **per project, not per API key**
   ([rate-limits docs](https://ai.google.dev/gemini-api/docs/rate-limits)), so adding keys
   doesn't help. The fix is a paid tier. That page does not publish paid-tier RPM per
   model (they're shown in AI Studio), so the first task is to read the tier's
   flash-lite RPM there and check it is above **101 average / about 300 at a 3× peak**.
   The 3× peak is an assumption, not a measurement.
2. **Latency, as a side effect.** Requests over the cap queue. Today 65% of model time
   is already pacing.
3. **The billing tier cap, at 500,000/day.** The docs list a $250 cap for Tier 1 and
   $2,000 for Tier 2. $13k/month needs Tier 3, which requires $1,000 of cumulative spend
   and 30 days.
4. **The MCP server, at 500,000/day.** Each agent session starts its own stdio server.
   Search takes about 300 ms of CPU, so 5.6 searches/second is about 1.7 cores on
   average. It has to become a pooled HTTP service (`pantry_server.py --http` already
   exists).

**What would cut cost per query, ranked (attributed first, as Week 11 required):**
98% of tokens are re-sent prompt, so the biggest saving is to stop re-sending. Answering
the most common shapes (one allergen check, one scale) as a fixed workflow would use 1
model call instead of about 3, roughly −60% cost and −2/3 of the rate-limit pressure,
which matches Week 7's verdict. Prompt caching of the system prompt and tool list is
second. A cheaper model doesn't apply: flash-lite is already the cheapest. **Caching
answers is NOT on the list.** A cached allergen answer serves a stale declaration to
everyone after the next reformulation, which is exactly how the shortbread went wrong.

## After the fix (release r2)

The fix is in the tool layer and adds **no model calls**: cost per query is $0.000861 after
vs $0.000877 before (33 suite queries each), with 2.85 vs 2.91 model calls per query. The
10× answer is unchanged: the rate limit breaks first.
