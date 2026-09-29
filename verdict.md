# verdict.md — kitchen squad vs single agent

1. **Sunk cost, named first:** I spent a week building the orchestrator, and that effort pulls me toward keeping it. It is not evidence, so it gets no weight below.
2. **Verdict: KILL the squad. Keep the single agent.**
3. **Pass rate:** 10/10 vs 10/10 on the same 10 Week-6 cases, same judge. The squad buys no measured quality.
4. **Tokens:** 70,482 vs 49,167, a **1.4x** re-send multiplier. 80% of the squad's tokens are one hand-off (manager -> substitution worker).
5. **Latency:** p50 **85.3 s vs 46.2 s** (1.8x) and p99 157.1 s vs 104.5 s, net of throttling. Cost per question is $0.000836 vs $0.000550 (1.5x).
6. **The squad loses on three of four numbers and ties on the fourth, so the verdict follows the table.**
7. **Caveat, not an override:** my post-hoc read (not blind) found the single agent wrong on c14 and c15, both cross-recipe comparisons, where the squad was right. The judge missed both, because it grades against what each agent retrieved.
8. The single agent's failure there is under-retrieval: it compared a subset of recipes. A one-line prompt fix at 1.0x cost is the cheaper thing to test before paying 1.4x for a squad.
9. **Would change my mind:** a blind re-label of these 20 answers showing the squad genuinely ahead on comparisons *after* the single agent's retrieval fix.
10. **Also fix before any reuse:** on an injected 500 the squad degraded silently and dropped the allergen check from its answer (`failure_case.md`).
