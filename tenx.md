# tenx.md

**At 10x, the rate limit breaks first: last week's busiest minute had 2 requests, so 10x
means 20 model calls in one minute against the free tier's 15 requests/minute cap (+33%),
while 10x cost is only about $0.14/week (1,000 requests x $0.0001392).**

---

Evidence, all from `logs/w11_requests.jsonl`:

- Every request makes exactly **1** model call (retrieval and tools are local), so model
  calls per minute = requests per minute.
- Busiest minute: **2** requests (2026-09-28 08:32). Busiest hour: 5. Busiest day: 23.
  Total: 100 in 7 days.
- The **15 requests/minute** cap comes from a real 429 this project received from Gemini
  in Week 6: `quotaId: GenerateRequestsPerMinutePerProjectPerModel-FreeTier, quotaValue: 15`.
  `ask.call_llm` already paces itself at one call per 4.5 s (~13.3/min), so in practice the
  ceiling is lower still.
- **Already visible today:** in the back-to-back traffic run, 75% of the median
  generation time (3,140.8 of 4,210.3 ms) was spent waiting on that pacing.
- **Latency breaks second, as a consequence:** per-request model time doesn't grow with
  volume, but requests beyond the cap queue, so the 3rd-and-later requests in a 10x peak
  minute wait.
- **Caveat:** the timestamps are simulated, so the busiest-minute figure comes from a
  random schedule. Real traffic clusters around meal times and would be burstier, which
  only strengthens the conclusion.
