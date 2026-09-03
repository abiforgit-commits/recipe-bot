# Week 4 & Week 5 — Likely Questions, Detailed Answers

Everything a grader or mentor is likely to ask about the Week 4 (Debugging
Retrieval) and Week 5 (Error Analysis) submissions, answered in detail and
grounded in this project's real numbers. Each answer has a **short version**
you can say in one breath, then the **detail** behind it, then — where it
applies — **how it shows up in this project**.

**Anchor numbers to memorize**

| Week | Number | Meaning |
|---|---|---|
| 4 | 8/12 → 11/12 | hit-rate@3 before → after the one change |
| 4 | 814 → 860 ms | p50 retrieval latency before → after (+46 ms, +5.7%) |
| 4 | R=4, G=0, NIC=0 | failure tally on the 4 baseline misses |
| 4 | k=60 | the RRF constant |
| 5 | 58 traces, sample of 20 | population and seeded sample size |

---

# PART 1 — WEEK 4: DEBUGGING RETRIEVAL

## A. Concept questions

### Q1. What are the two kinds of failure in a RAG app, and why must you separate them?

**Short:** R = retrieval fetched the wrong context. G = retrieval was right but
the model misused it. Plus Not-In-Corpus = the answer never existed in the
documents. They need completely different fixes.

**Detail:** A RAG answer is produced in two stages — find text, then write
from it. Either stage can fail, and the symptom ("the answer is wrong") looks
identical from the outside. But the fixes are disjoint: an R-failure is fixed
by better search (keyword search, reranking, better chunking); a G-failure is
fixed by better prompting, a stronger model, or tighter grounding rules. If
you don't label first, you can spend weeks paying for the wrong fix — for
example, upgrading to an expensive model when the real problem is that the
right chunk was never retrieved. The model simply writes a *better-sounding*
answer from the *wrong* text.

**In this project:** all four Week 4 misses were R — the correct chunk was
absent from the top-3 every time. And G was zero *with evidence*: on all four,
the model refused rather than inventing, so the Week 3 grounding held.

### Q2. What is the inspection view?

**Short:** One request, laid out side by side — the question, the retrieved
top-3 with scores, the final answer.

**Detail:** It's the debugging instrument that makes R/G labelling honest. For
each failure you ask, in order: Was the correct document retrieved at all? If
yes, was it ranked high enough to be used? If it was there and the answer is
still wrong — that's G, and no retrieval change can help. If it was absent —
that's R. The task's common-mistake list warns against labelling something R
just because the answer was wrong, without opening the view to check whether
the right chunk was sitting in the top-3 all along.

**In this project:** `w4_inspect.py` — its output for the four misses is
saved in `results/w4_inspection.md`. It also revealed *who* was clogging the
top-3: the intro-stub chunks from the structure-aware chunker (five of the
eight wrong slots).

### Q3. What is BM25, and what is it good at?

**Short:** Classic keyword search that scores documents by how well they
contain the query's actual words, giving extra weight to rare words.

**Detail:** BM25 counts term matches, adjusted for two things: rare terms
count more than common ones (a match on "kannimanga" is worth far more than a
match on "the"), and long documents don't get an unfair advantage just for
containing more words. It has no idea what words *mean* — "sticking to the
pan" and "releases itself from the pan" share nothing for BM25. Its strength
is exactly what meaning-based search fumbles: unusual names, precise numbers,
error codes, percentages, units — tokens that embeddings blur into "some
quantity" or "some ingredient".

**In this project:** BM25 fixed Q4 ("6.7%") and Q5 ("72%") — tokens that
appear in exactly one chunk each. It is implemented with the `rank-bm25`
library over the same 24 chunks, built once at import.

### Q4. Keyword vs semantic search — when does each win?

**Short:** Semantic wins on meaning and paraphrase; keyword wins on exact
tokens. Each is blind exactly where the other sees.

**Detail:** Semantic (vector) search embeds meaning, so "why did my curd go
sour?" finds the method sentence about over-fermenting even though they share
no words — but it represents "6.7%" as roughly "a percentage", losing the
exact value. Keyword search matches literal tokens, so "6.7%" hits its one
chunk instantly — but has no concept of synonyms or intent. That
complementary blindness is the whole argument for running both.

**In this project:** semantic-only aced the paraphrase questions (Q6–Q9, Q12)
and missed the numeric-token ones (Q4, Q5). BM25 is the exact mirror image.
Neither alone reaches 11/12; fused, they do.

### Q5. Explain RRF. Why fuse ranks instead of scores?

**Short:** Reciprocal Rank Fusion merges two ranked lists using positions
only — each list gives every chunk 1/(60 + rank) points; sum and re-sort.

**Detail:** After hybrid retrieval you hold two ranked lists with two kinds of
score: cosine similarity (always 0–1) and BM25 (unbounded — 3, 14, 30…).
Adding or averaging them is meaningless — like adding degrees Celsius to
degrees Fahrenheit — and in practice BM25's larger numbers would drown
semantic every time. RRF throws the scores away and keeps only the *rank
position*, which is always comparable across lists. A chunk ranked 1st by one
list and 7th by the other gets 1/61 + 1/67. The constant k=60 is a damper:
without it rank 1 (1/1) would crush rank 2 (1/2); with it, 1/61 and 1/65 are
close, so a chunk needs support from both lists — or a very strong showing in
one — to win. Fusion becomes consensus rather than winner-takes-all.

**In this project:** Q5, "what is 72% of the rice weight?": semantic had the
correct idli table at rank 7 (a miss); BM25 had it at rank 1. Fused, its
combined points beat the intro-stubs that semantic had placed first. That is
exactly how Q5 flipped from MISS to hit@1.

### Q6. What is a cross-encoder reranker, and why didn't you use one?

**Short:** A model that reads the query and one chunk together and outputs a
relevance score — accurate but slow, so it re-orders a shortlist rather than
searching the corpus.

**Detail:** A bi-encoder (our embedding model) fingerprints query and chunks
separately, so searching is fast but the two never "see" each other. A
cross-encoder feeds the pair through the model jointly, seeing exactly how the
words interact — much better judgement, but it must run once per pair, so it's
used on the top 20–50 candidates only. Examples: Cohere Rerank, BGE-Reranker.
Critically, a reranker can only *reorder* what the first stage found. If the
right chunk never enters the candidate pool, reranking can't rescue it.

**In this project:** rejected because the tally showed token-matching
failures, not ranking-subtlety failures — the right chunks weren't being
found at all, so reordering couldn't help. BM25 attacks the actual cause.
Also practical: no 100MB+ model download and no extra latency.

### Q7. The team lead says "swap the embedding model." Why is that the wrong move here?

**Short:** The tally shows exact-term failures, and a denser embedding
*structurally* cannot do exact token matching — it fixes nothing identified
and costs re-embedding everything.

**Detail:** Embedding models differ in quality, but all of them represent
meaning, not literal strings. A better model still turns "6.7%" into "a
percentage". The task's common-mistakes section calls this out explicitly:
agreeing to swap the model because the lead suggested it, when the tally says
the failures are exact-term R-failures, is paying for the one thing that
cannot help. Evidence beats seniority.

### Q8. hit-rate@k, recall@k, MRR — define each.

**Short:** hit-rate@k: did at least one correct result appear in top-k?
recall@k: what fraction of all relevant results made it into top-k? MRR: how
high did the first correct result rank?

**Detail:** hit-rate is yes/no per question, averaged — the simplest,
"did I find it?" recall@k matters when several chunks are relevant (a full
recipe spread across 3 chunks): retrieving 2 of 3 = 66.7%. MRR (Mean
Reciprocal Rank) rewards *position*: rank 1 scores 1.0, rank 2 scores 0.5,
rank 4 scores 0.25, averaged across questions — ranks of 1, 2, 1, 4 give
(1 + 0.5 + 1 + 0.25) / 4 = 0.6875. Higher MRR means the correct chunk sits
nearer the top, which matters because generation reads the top few most.

**In this project:** the graded metric was hit-rate@3, but the per-question
tables also record rank (hit @1 vs hit @2), which is the raw material of MRR.

### Q9. Why measure latency, and what is p50?

**Short:** Every quality improvement has a speed price, and you state it or
the comparison is dishonest. p50 is the median query time.

**Detail:** p50 means half of queries were faster than this, half slower —
more honest than the mean, which one slow outlier can distort. Latency must be
measured in paired conditions (same machine, same session, warmed-up model)
or you compare noise. A change that lifts hit-rate but doubles latency may be
the wrong ship — and saying "not worth the latency" earns the same marks as
shipping, because the rubric rewards the honest read.

**In this project:** 813.7 ms → 859.9 ms, +46 ms, +5.7% — measured
back-to-back in one session after a warm-up query. BM25 scoring on 24 chunks
is microseconds; the ~800 ms is the embedding step, so the fusion's price is
noise.

### Q10. Why exactly ONE change between the two measurements?

**Short:** Two changes and one delta = zero information about which change
earned it.

**Detail:** If you add BM25 *and* a reranker and the number moves, you don't
know whether one helped, both helped, or one helped while the other hurt. One
change, same questions, before → after is the only design where a moved number
teaches you something. Then ship, and consider the next change with its own
measurement. This is the same rule as the Week 3 chunker experiment.

### Q11. What are MMR, query rewriting, and HyDE?

**Short:** MMR = relevant *and* diverse results. Query rewriting = improve the
user's question before searching. HyDE = search with a hypothetical answer's
embedding.

**Detail:** **MMR** (Maximal Marginal Relevance) picks results one at a time,
balancing similarity to the query against dissimilarity to results already
picked — it fixes "top-3 are three near-copies of the same base dough", at the
risk of pushing the correct chunk out in the name of variety. **Query
rewriting** turns "how long do I leave it?" into "how long should the dill
pickles ferment?" — adding missing context and keywords before retrieval.
**HyDE** (Hypothetical Document Embeddings) has the LLM write a plausible
answer first, embeds *that*, and searches with it — because documents look
like documents, an answer-shaped query matches them better than a
question-shaped one; the hypothetical text is used only for retrieval, never
shown to the user.

**In this project:** MMR was the bonus challenge and was deliberately skipped:
it would be a second change with its own before/after — and the week's
discipline is one change at a time. Noted as the natural next experiment.

## B. Questions about this project's Week 4

### Q12. Walk me through your Week 4 result end to end.

"I built a 12-question golden set, five with exact tokens dense retrieval is
structurally bad at. Baseline dense retrieval: 8/12 hit-rate@3 at 814 ms p50,
written down before any change. I ran all four misses through the inspection
view: all R-failures, two hinging on numeric tokens ('6.7%', '72%'). That
justified one change — BM25 alongside dense, fused with RRF k=60. After, on
the same 12: 11/12 at 860 ms. Fixed Q4, Q5, Q11; Q10 stayed broken exactly as
predicted. Shipping decision: ship — three failures bought back for 46 ms."

### Q13. How did you build the golden set — and can I trust it?

**Short:** Honestly — my first draft scored 12/12, which measures nothing, so
four always-passing questions were replaced with harder real-user patterns,
and that's disclosed.

**Detail:** The task warns: "a golden set that only contains questions you
already pass measures nothing." The first draft had no misses at baseline.
Four questions were swapped for percentage-token questions ("what ingredient
is 6.7% of the rice weight?") and cross-recipe comparisons ("which recipe has
the highest salt percentage?"), which are genuinely how users ask. Every
question is tagged with its known-correct chunk_id, and the baseline number
was recorded on the final frozen set *before* the change was chosen or built.
We have no real user logs, so questions were authored in real-user styles —
also disclosed.

### Q14. Show me your tally and the evidence behind each label.

**R=4, G=0, Not-In-Corpus=0.**

- **Q4 — R.** Top-3 were two intro-stub chunks plus the appam table; the
  token "6.7%" exists only in `dosa-batter-02::structure::1`, which was
  absent.
- **Q5 — R.** All three top hits were intro-stubs ("Percentages are relative
  to…"); "72%" exists only in the idli table chunk, absent.
- **Q10 — R.** Fetched the koozh table (rock salt 4%) on "salt" similarity;
  the actual highest-salt chunk (kadumanga, 15%) never appeared.
- **Q11 — R.** The query words "idli batter" dragged in two idli chunks; the
  sentence "thinner than idli batter" lives in the dosa method, absent.

G=0 with evidence: on all four the model *refused* rather than answering from
wrong context — so no failure was generation misusing good context. NIC=0 by
construction: every golden question is tagged to an existing chunk.

### Q15. Which failures did your change fix, which not, and why?

**Fixed:** Q4 and Q5 at rank 1 — BM25 matched the literal tokens, exactly as
the tally predicted. Q11 as a bonus: the dosa method contains the literal
words "thinner than idli batter", so word overlap rescued a question I had
classed as a comparison.

**Not fixed:** Q10, "which recipe has the highest salt percentage?" The word
"highest" is not text in any chunk. Answering requires reading the salt row of
every table and comparing values — that's computation across chunks, not
retrieval. No retrieval change can fix it, and the justification paragraph
predicted this before the after-run. Being able to say in advance which
failures a change *can't* touch is what separates debugging from guessing.

### Q16. Tell me about the tokenizer bug.

"My first hybrid run scored 9/12 with two regressions — 'noi arisi' and
'kannimanga', both rank-1 hits at baseline, fell out of the top-3. The
inspection showed why: my BM25 tokenizer was plain `.split()`, which keeps
punctuation glued to words. The cards say '(noi arisi)' — tokens `(noi` and
`arisi)` — and the query said 'arisi?'. Nothing matched. BM25 got zero signal
on the rare token, and its stopword noise diluted dense's correct ranking
through the fusion. The exact-match tool failed at exact matching because of
parentheses. One fix — tokenize on `[a-z0-9%.]+`, stripping punctuation but
keeping '6.7%' as one token — and the result was 11/12 with no regressions."

### Q17. Isn't fixing the tokenizer after seeing regressions "tuning on the test set"?

**Short:** Mildly, yes — and the write-up says so.

**Detail:** The fix corrected an implementation bug inside the one change
rather than adding a second retrieval mechanism, so the "one change" rule
holds. But the diagnosis did come from golden-set behaviour, which is a form
of tuning on the evaluation data. Production practice would confirm the final
configuration on a held-out second question set that was never looked at
during development. That's the first thing to add. Admitting this is worth
more than hiding it — the rubric explicitly rewards honest reads.

### Q18. Defend your shipping decision.

"Three of four failures bought back for 46 ms p50 — about 6%, and noise
against the ~800 ms embedding step. The number says yes, the price is trivial,
and the one remaining failure is provably outside any retriever's reach. If the
data had said 'not worth the latency', I would have said so — that earns the
same marks."

### Q19. Why hit-rate@3 instead of @5 like Week 3?

The task set it, and it's a better bar for this corpus. Week 3 showed why:
top-5 of 24 chunks is a 21% net and saturated (8/8 vs 8/8). Top-3 is stricter
and separated configurations that top-5 couldn't — the baseline had four real
misses to work with.

### Q20. What would you do next?

One change at a time, each with its own before/after: (1) a held-out golden
set to confirm the tokenizer fix wasn't overfit; (2) merge the structure
chunker's intro-stub chunks into their ingredient chunks — they occupied five
of eight wrong top-3 slots; (3) MMR over the fused list to reduce near-copy
pollution, measuring both hit-rate and diversity; (4) for Q10-type
comparison questions, retrieval can't help — that needs a tool-calling step
that reads the tables and computes.

---

# PART 2 — WEEK 5: ERROR ANALYSIS

## A. Concept questions

### Q1. What is a trace, and what makes one complete?

**Short:** A full record of one request, complete enough to replay the answer
later without the live system.

**Detail:** "Complete" is defined by the replay test: can you reproduce the
output from the record alone? That requires the prompt version (prompts
change), the retrieved chunk_ids with scores (and ideally their texts — the
index may change), the model name and parameters (temperature), and the raw
output. Missing any one and you're reconstructing from memory, which is an
anecdote, not evidence.

**In this project:** `w5_trace.py` writes one JSON line per request to
`traces.jsonl` with: trace_id, timestamp, prompt_version, retriever
(hybrid-rrf60) and k, retrieved chunk_ids with scores *and full texts*, model,
temperature, question, and output. Full texts were stored deliberately so
replay never depends on today's index matching the trace's day.

### Q2. Why does replay matter?

**Short:** A failure you can't reproduce is a failure you can't study.

**Detail:** Next month the prompt or index will have changed; without replay,
old failures become unverifiable stories. Replay also separates
non-determinism from real change: with temperature 0 the replayed output
should match nearly exactly; drift indicates the provider updated the model
behind the alias — itself worth knowing, and why the trace stores the model
name.

### Q3. Random vs curated sampling — why does it matter so much?

**Short:** Frequency is half of the fix order, and a curated sample gives
fictional frequencies.

**Detail:** If you sample the recipes you remember breaking, your taxonomy
describes your memory, not your app — and the demo set you show at reviews is
the most biased sample of all. A seeded random draw is *provable*: same seed +
same trace file = same 20 ids, so anyone can verify you didn't cherry-pick.
The bonus challenge makes the point sharply: open-code 10 traces from your
curated demo set too, and compare the top mode's frequency in random vs demo
— "the paragraph explaining what your team has been telling itself."

### Q4. What is open coding, and what are its rules?

**Short:** One honest sentence per trace describing what you *saw* — before
any categories exist.

**Detail:** Three rules. (1) Observations, not diagnoses: "answered 18g from
the dosa card for an appam question" is an observation; "retrieval issue" is a
diagnosis smuggled in as an observation — the diagnosis is next week's job.
(2) Zero fixes during reading — a two-minute fix at trace 6 means traces 7–20
describe a different system and your taxonomy describes an app that no longer
exists. The zero is graded. (3) "I don't know why this failed" is a permitted
and valuable sentence — pretending to know is the failure.

### Q5. Why is deciding categories first "the whole failure this week exists to prevent"?

**Short:** Because you'll find exactly the modes you expected and nothing else.

**Detail:** Categories decided in advance act as a filter on perception —
every trace gets forced into the nearest pre-made bucket, and anything that
fits no bucket becomes invisible. Categories built *from* the observations
can contain surprises, and the surprises are the entire value of reading by
hand. The order — observe all 20, *then* cluster — is not bureaucracy; it's
the mechanism that makes discovery possible.

### Q6. What makes a good failure-mode name?

**Short:** A stranger — your manager — should know what to do from the name
alone.

**Detail:** "Scales the salt but not the yeast" tells the manager something
concrete happened with quantity scaling and points at a specific behaviour.
"Quantity issue" or "hallucination" are diagnoses that tell nobody what to do.
The test: could someone who never saw the traces read the name and picture the
failing output?

### Q7. Why rank by frequency × severity?

**Short:** You can't fix everything at once; rank tells you what to fix first.

**Detail:** Frequency comes from the random sample — which is why sampling
honesty matters. Severity is a stated judgment on a stated scale; the task's
scale is "poisons or ruins the dish" vs "merely annoys the cook". A mode that
poisons the dish in 30% of traces outranks one that annoys in 10%. A rare mode
that gives dangerous advice may still outrank a common cosmetic one — ranking
is a judgment you defend with both numbers visible.

### Q8. Why must the prediction be falsifiable, numeric, and committed before any fix?

**Short:** "This should improve things" can never be wrong, so it can never
teach anything.

**Detail:** "Fixing X drops mode Y from 35% to under 15% on a fresh 20-trace
sample" can be wrong — and being wrong is the informative outcome, because it
means your diagnosis of the mode was mistaken. Committing it to git with a
date makes it impossible to quietly rewrite after seeing the result. It's the
same discipline as Week 4's baseline-written-first and Week 3's
questions-frozen-first: decide what would count as failure *before* you can
be tempted.

### Q9. Why wouldn't a public benchmark (MMLU, HumanEval) surface your failures?

**Short:** Benchmarks measure a model's general ability on public questions;
your failures live in the seam between your chunks, your prompt, and your
users' phrasing.

**Detail:** MMLU tests knowledge across academic subjects; HumanEval tests
code generation. Neither contains your recipe cards, your chunker's boundary
decisions, or your users' "how mch salt in idlly". A model could top every
leaderboard and still orphan a salt row, refuse an answerable question, or
answer from the wrong card, because those failures are properties of *the
system you built*, not of the model. Benchmark scores don't move when your
chunker changes; your trace sample does.

### Q10. Why read traces by hand — can't an LLM do it?

**Short:** Automation can label what you already know to look for; reading
discovers what you didn't know existed.

**Detail:** An LLM judge needs a rubric — which means categories decided
first, which is the cardinal sin (Q5). Hand-reading is the discovery step for
unknown unknowns. Once the taxonomy exists, automation is excellent for
*counting* modes at scale — Week 6's territory. Discovery, then automate; not
the reverse. That order is why this module is called the core of the course.

## B. Questions about this project's Week 5

### Q11. Where did your traces come from — you have no real users. Isn't that a problem?

**Short:** Disclosed up front: a week of usage was simulated in one batch —
58 questions written as a realistic population.

**Detail:** The population covers how real cooks ask: direct quantity
questions, how-tos, vague one-liners ("how much salt?"), typos ("how mch salt
in idlly batter"), comparisons, out-of-scope asks (calories, biryani, wine
pairing), multi-part requests, and food-safety worries ("white film on my
pickle"). It was written *before* sampling and not engineered to trigger
failures we expected. It's a real limitation versus organic traffic — but the
method (seeded sampling, open coding, taxonomy, prediction) is exactly what
runs on real logs, unchanged. The traced app is the Week 4 shipping config:
hybrid retrieval (k=5) feeding the grounded forced-refusal prompt.

### Q12. Prove your sample was random.

The seed value and the 20 selected trace_ids are pasted in notes.md.
Re-running `python w5_sample.py 20 --seed <seed>` on the same traces.jsonl
reproduces the identical 20 ids. The seed chose them, not me.

### Q13. Show me your replay evidence.

One trace_id was chosen by seed and re-run from the trace alone — stored chunk
texts, prompt version, model, temperature 0, no fresh retrieval. Original and
replayed outputs sit side by side in notes.md. Anything that could not be
reconstructed is stated there (e.g. the exact provider-side model build behind
the `gemini-flash-latest` alias, which the trace can name but not pin).

### Q14. What are your top failure modes?

*(Filled in after the open-coding session — template below.)*

"My taxonomy has N modes from the 20-trace sample. The top mode is
‹plain-language name›: X of 20 traces (Y%), severity ‹poisons the dish /
annoys the cook›, example trace ‹id›. Second: ‹name›, ‹count›, ‹%›,
‹severity›, ‹id›. The full one-screen table is taxonomy.md; the 20 verbatim
observation sentences are in notes.md."

### Q15. What is your prediction for next week?

*(Filled in after the taxonomy exists — template below.)*

"Committed on ‹date›, commit ‹hash›: making ‹one specific change› will drop
‹mode name› from ‹Y%› to under ‹Z%› on a fresh seeded 20-trace sample. If it
doesn't, the prediction is falsified — and that tells me my diagnosis of the
mode was wrong, which is exactly why it's written down first."

---

# PART 3 — CURVEBALLS (BOTH WEEKS)

### "Your whole corpus is 6 cards and 24 chunks. Does any of this mean anything?"

The numbers are small-scale; the *method* is full-scale — seeded sampling,
frozen questions, one change at a time, before/after with a stated cost. The
small corpus even taught its own lesson: it saturated the Week 3 metric (8/8
vs 8/8), which had to be detected and diagnosed instead of trusted. Swap in a
bigger corpus and every script re-runs unchanged — that was proved when the
identical measurement reproduced on a second machine from a fresh clone.

### "If I re-ran your pipeline, would I get your numbers?"

Retrieval: yes, exactly — the embedding model is local and deterministic
(same text → same 384 numbers), and BM25 is arithmetic. Generation:
near-exactly — temperature 0, with drift possible only if the provider rotates
the model behind the alias, which is why traces record the model name.

### "Two people could cluster the same 20 sentences differently. Isn't your taxonomy just opinion?"

It's judgment, but *checkable* judgment: all 20 verbatim sentences are in
notes.md, each mode names an example trace_id, and the counts are countable.
Someone who disagrees can re-cluster my own evidence — that's the difference
between subjective and unaccountable.

### "Why only 20 traces? Why not 200?"

Twenty hand-read traces is roughly where discovery saturates for one reader
in one sitting, and it's the task's design: frequencies from 20 are rough, but
the goal is finding the modes and their *order*, not their third decimal. With
200 I'd automate counting — after hand-reading discovered what to count.

### "You used AI tools to build this. Do you actually understand it?"

The honest answer is the demonstration: explain the tokenizer bug, say why
RRF fuses ranks, name which Week 4 failure no retriever can fix and why,
and state the anchor numbers from memory. Tools wrote code; the reasoning
behind every decision — one change at a time, baseline first, refuse rather
than invent, observe before categorize — is what's being examined, and it's
in this document because I can defend it.

---

# APPENDIX — the numbers, one screen

| Item | Value |
|---|---|
| Corpus | 6 recipe cards → 24 chunks (structure-aware) |
| Embedding model | all-MiniLM-L6-v2, 384 dims, local, deterministic |
| Week 3 | naive 8/8 vs structure 8/8 hit-in-top-5 (saturated); structure ships |
| Week 3 refusals | 3/3 refused, 3/3 cited answers with resolving chunk_ids |
| Week 4 golden set | 12 questions: 5 exact-token, 5 paraphrase, 2 comparison |
| Week 4 baseline | 8/12 hit-rate@3, p50 813.7 ms |
| Week 4 tally | R=4, G=0, NIC=0 |
| Week 4 change | BM25 + RRF (k=60), tokenizer `[a-z0-9%.]+` |
| Week 4 after | 11/12 hit-rate@3, p50 859.9 ms (+46 ms, +5.7%) |
| Week 4 fixed / untouched | Q4, Q5, Q11 fixed; Q10 untouched (needs computation) |
| Week 5 traces | 58 simulated-usage traces, hybrid k=5, temp 0 |
| Week 5 sample | 20, seeded (seed in notes.md) |
