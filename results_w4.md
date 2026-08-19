# Week 4 Practical — Task Set B — results

**Label the failures, then buy back hit-rate@3 with exactly one change.**
App: the Week 3 recipe RAG (structure-aware index, 24 chunks, local MiniLM
embeddings). All retrieval measurements are local and deterministic.

## Headline

| | hit-rate@3 (same 12 questions) | p50 retrieval latency |
|---|---|---|
| **Before** — dense only | 8/12 | 813.7 ms |
| **After** — dense + BM25, RRF k=60 | **11/12** | 859.9 ms (+46.2 ms, +5.7%) |

One retrieval change. Three failures bought back. Latency price: ~6%.

---

## 1. The golden set (golden_set.jsonl)

12 questions, each tagged with its known-correct chunk_id. 5 contain exact
tokens dense retrieval is structurally weak at (Tamil ingredient/utensil
names, precise percentage strings); 2 are cross-recipe comparison questions.

| Q# | Question | Expected chunk | Kind |
|---|---|---|---|
| 1 | What is noi arisi? | ragi-koozh-05::structure::1 | exact-token |
| 2 | What can I cook in an appachatti? | appam-03::structure::2 | exact-token |
| 3 | What is kannimanga? | kadumanga-06::structure::1 | exact-token |
| 4 | What ingredient is 6.7% of the rice weight? | dosa-batter-02::structure::1 | exact-token |
| 5 | What is 72% of the rice weight in one of the batters? | idli-batter-01::structure::1 | exact-token |
| 6 | My dosas keep sticking to the pan — what am I doing wrong? | dosa-batter-02::structure::2 | paraphrase |
| 7 | How do I know the urad dal has been ground enough? | idli-batter-01::structure::2 | paraphrase |
| 8 | Why did my curd become too sour by the evening? | thayir-04::structure::2 | paraphrase |
| 9 | How long until the mango pickle is ready to eat? | kadumanga-06::structure::2 | paraphrase |
| 10 | Which recipe has the highest salt percentage? | kadumanga-06::structure::1 | comparison |
| 11 | Which batter should be thinner than idli batter? | dosa-batter-02::structure::2 | comparison |
| 12 | What gives dosa its crispness? | dosa-batter-02::structure::1 | paraphrase |

**Construction disclosure (honesty over neatness):** we have no real user
logs, so questions were authored in real-user styles. A first draft of the
set scored 12/12 at baseline — and the task itself warns that "a golden set
that only contains questions you already pass measures nothing." Four
always-passing questions were therefore replaced with harder patterns
(precise-percentage tokens, cross-recipe comparisons) screened against the
baseline retriever. Expected chunk_ids were tagged from the cards. The
baseline below was recorded on the final, frozen set before the retrieval
change was chosen or built.

## 2. Baseline (recorded before any change)

**hit-rate@3 = 8/12, p50 latency 813.7 ms** (full per-question dump:
`results/w4_run_dense.md`). Misses: Q4, Q5, Q10, Q11.

## 3. Failure labels — R / G / Not-In-Corpus

Every miss ran through the inspection view (`w4_inspect.py`, output in
`results/w4_inspection.md`: question, top-3 with scores, final answer).

| Q# | Label | One line of evidence |
|---|---|---|
| 4 | **R** | Top-3 were two intro-stubs + the appam table; the token "6.7%" exists only in dosa-batter-02::structure::1, which was absent. |
| 5 | **R** | All three top hits were intro-stub chunks ("Percentages are relative to…"); "72%" exists only in the idli table chunk, absent. |
| 10 | **R** | Fetched the koozh table (rock salt 4%) on "salt" similarity; the actual highest-salt chunk (kadumanga, 15%) never appeared. |
| 11 | **R** | Query words "idli batter" dragged in two idli chunks; the sentence "thinner than idli batter" lives in the dosa method, absent. |

**Tally: R = 4, G = 0, Not-In-Corpus = 0.**

- G = 0 with evidence: on all four misses the model **refused** rather than
  answering from wrong context — the Week 3 forced-grounding held, so no
  failure was generation misusing good context. (Common-mistake check: we
  confirmed the correct chunk was NOT in the top-3 before labelling R.)
- NIC = 0 by construction: every golden question is tagged to an existing chunk.
- Recurring villain: the **intro-stub chunks** identified in Week 3 pollute
  the top-3 of Q4 and Q5 — five of the eight wrong slots.

## 4. The ONE change, justified by the tally

All four failures are retrieval failures, and two of them (Q4, Q5) hinge on
**exact numeric tokens** ("6.7%", "72%") — precisely the tokens dense
embeddings blur into "some percentage" and exactly what keyword matching is
built for. So the change is **BM25 alongside dense, fused with Reciprocal
Rank Fusion (k=60)** — fusing *ranks*, not scores, because cosine (0–1) and
BM25 (unbounded) are not on the same scale. The cross-encoder option was
rejected: the tally shows token-matching failures, not subtle-ranking
failures, and a reranker can only reorder candidates dense already found.
Swapping the embedding model (the "team lead" suggestion) is the one move
the tally rules out structurally: a denser embedding still doesn't do exact
token matching. The comparison failures (Q10, Q11) were predicted to remain
untouched — no retriever computes "highest".

## 5. What actually happened — including the bug

The first hybrid run scored **9/12 with two regressions**: Q1 (noi arisi)
and Q3 (kannimanga) — rank-1 hits at baseline — fell out of the top-3.
Diagnosis: the BM25 tokenizer was plain `.split()`, which keeps punctuation
glued to words. The cards say "(noi arisi)" → tokens `(noi` / `arisi)`; the
query said "arisi?" — nothing matched, BM25 got zero signal on the rare
token, and its stopword noise diluted dense's correct ranking through the
fusion. The exact-match tool failed at exact matching because of parentheses.

Fix: tokenize on `[a-z0-9%.]+` (punctuation stripped, "6.7%" survives as
one token). This is part of the same single retrieval change — the BM25
implementation — and the regression that exposed it is disclosed here
rather than hidden. Caveat, stated honestly: diagnosing a bug from golden-set
regressions is a mild form of tuning on the test set; production practice
would confirm on a held-out second set.

## 6. After — same 12 questions

**hit-rate@3 = 11/12, p50 latency 859.9 ms** (dump: `results/w4_run_hybrid.md`).
Before/after runs were executed back-to-back in one session for a fair
latency pairing.

## 7. Per-question fixed / unfixed

| Q# | Before | After | Verdict |
|---|---|---|---|
| 1 | hit @1 | hit @1 | unchanged (regressed under buggy tokenizer, restored by fix) |
| 2 | hit @1 | hit @1 | unchanged |
| 3 | hit @1 | hit @1 | unchanged (same as Q1) |
| 4 | MISS | **hit @1** | **FIXED** — BM25 matched the "6.7%" token exactly |
| 5 | MISS | **hit @1** | **FIXED** — BM25 matched "72%" |
| 6–9, 12 | hit @1 | hit @1 | unchanged |
| 10 | MISS | **MISS** | **UNTOUCHED** — comparison question; "highest" is not text in any chunk; needs aggregation, not retrieval |
| 11 | MISS | **hit @2** | **FIXED** — BM25 matched the literal words "thinner", "idli", "batter" in the dosa method |

Which R-failures the change fixed: Q4, Q5 (as predicted from the tally) and
Q11 (a bonus — the comparison happened to be answerable by literal word
overlap). Which it did not touch: Q10, exactly as predicted — no retrieval
change fixes a question whose answer requires computing over several chunks.

## 8. Shipping decision

**Ship it.** The change bought back 3 of 4 failures (+37.5 points of
hit-rate@3) for a p50 cost of 46 ms (+5.7%) — on this corpus BM25 scoring is
microseconds and the latency cost is noise against the ~800 ms embedding
step. The number says yes, the price is trivial, and the one remaining
failure is provably outside any retriever's reach.

## 9. Code diff

The single retrieval change (adding BM25 + RRF to `w4_retriever.py`, plus
the rank-bm25 dependency) is captured as a literal diff in
`results/w4_retrieval_change.patch` — baseline dense-only retriever on the
left, hybrid on the right.

## Bonus challenge (MMR)

Not attempted this round; noted for the future: our top-3s do show
near-duplicate pollution (intro stubs), which is MMR's target — but per this
task's own discipline, that would be a second change with its own
before/after measurement.
