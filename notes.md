# Week 5 — Open-coding notes

## Sample provenance

- **Population:** 58 traces in `traces.jsonl`, all produced by one configuration
  (retriever `hybrid-rrf60`, k=5, prompt `v1-grounded-forced-refusal`, model
  `gemini-flash-lite-latest`, temperature 0).
- **Sampling command:** `python w5_sample.py 20 --seed 20260917`
- **Seed:** `20260917`. Re-running that command on the same `traces.jsonl`
  reproduces the identical 20 trace_ids.
- **The 20 sampled trace_ids:**
  `15466577, 6947fda6, 8c2b5e88, d19072d0, f6873d76, b1882cdf, 4b3ae3f7,
  a27ce0d0, b964339e, 39fe9c73, 24d85a22, be389e3f, ac1aa143, 97da638b,
  407b4250, eb9ee143, 08b2ff45, 7c7023dc, 00e338e3, d8af00bd`

**Traffic disclosure.** This app has no organic users. The 58-trace population
was generated in one batch from a question list written to mirror how cooks
actually ask — direct quantity questions, how-tos, vague one-liners, typos,
comparisons, out-of-scope asks, multi-part requests and food-safety worries.
The list was written as a population *before* any sampling and was not
engineered to trigger failures we expected. Limitation versus organic logs is
acknowledged; the method below is what would run unchanged on real logs.

**Model-homogeneity note.** An earlier partial population mixed two models
after `gemini-flash-latest` exhausted its free-tier daily quota mid-run. Since
the model is part of the system under study, that population was archived
(`archive/traces_flash_latest_partial.jsonl`) and all 58 traces were
regenerated on a single model rather than analysed as a mixture.

## Replay evidence (requirement 1)

Trace chosen by the same seed: **`d8af00bd`**, replayed with
`python w5_trace.py replay d8af00bd` using only what the trace stored — the
saved chunk texts, prompt version, model and temperature. No fresh retrieval
was performed.

```
trace_id: d8af00bd   prompt_version: v1-grounded-forced-refusal
model: gemini-flash-lite-latest  temp: 0  retriever: hybrid-rrf60 k=5

Q: When do I add the salt to the koozh?

--- ORIGINAL output (2026-09-16T22:19:06Z) ---
You add the rock salt at the end of cooking the porridge [ragi-koozh-05::structure::2].

--- REPLAYED output (now) ---
You add the rock salt at the end of cooking the koozh [ragi-koozh-05::structure::2].

Identical: False
```

**Fields present and sufficient to replay:** prompt version, retriever + k,
retrieved chunk_ids *with scores and full texts*, model, temperature,
question, raw output, timestamp. Nothing had to be added — chunk texts were
stored at trace time precisely so replay does not depend on today's index.

**What could not be reconstructed:** byte-identical output. The replay is
semantically identical and cites the same chunk, but one noun differs
("porridge" → "koozh") despite temperature 0. The trace can name the model
alias (`gemini-flash-lite-latest`) but cannot pin the provider-side build
behind that alias, so exact-token reproducibility is outside the trace's
control. Everything the trace *does* control reproduced exactly.

---

## The 20 open-coding sentences

One sentence per trace, written while reading, describing what was seen.
No categories were decided before this list was complete, and **no code was
changed during coding**.

1. **`15466577`** — "My batter didn't rise, what went wrong?": refused,
   although the retrieved chunks included both the idli and dosa method
   sections, which state fermentation times and temperatures.

2. **`6947fda6`** — "There is a white film on top of my pickle, is it safe?":
   refused a food-safety question; the retrieved pickle chunks describe how
   the ferment should look ("olive-drab") but say nothing about surface film.

3. **`8c2b5e88`** — "Can I make it faster?": refused a question that names no
   recipe, and did not ask back which recipe was meant.

4. **`d19072d0`** — "Which recipe has the highest salt percentage?": refused;
   the top-5 chunks contained two ingredient tables with salt rows but not all
   six, and no chunk states which recipe is highest.

5. **`f6873d76`** — "What rice do I use for appam?": answered "raw rice
   (pachari), soaked, and cooked rice", listing the cooked-rice row next to
   the raw-rice row without distinguishing which is the base grain.

6. **`b1882cdf`** — "How much Kashmiri chilli powder in kadumanga achar?":
   answered 50g and 5% of mango weight; both figures match the cited row.

7. **`4b3ae3f7`** — "How much salt?": refused; the five retrieved chunks were
   five different ingredient tables, each carrying a different salt quantity.

8. **`a27ce0d0`** — "How much mustard seed goes in the mango pickle?":
   answered 10g, matching the cited table row.

9. **`b964339e`** — "Can I microwave idlis instead of steaming?": refused; the
   retrieved idli method specifies steaming for 12 minutes and says nothing
   about microwaving.

10. **`39fe9c73`** — "How much coconut milk goes into appam?": answered 400g /
    80% and additionally explained the split between grinding and finishing,
    citing two different chunks.

11. **`24d85a22`** — "How long should idli batter ferment?": answered 8 to 12
    hours at 28–32°C, matching the cited method sentence.

12. **`be389e3f`** — "What is the difference between idli and dosa batter?":
    produced a three-bullet comparison across soaking, grinding and
    fermentation, citing one chunk per recipe; far longer than any other
    answer in the sample.

13. **`ac1aa143`** — "Which oil is used on the dosa tawa?": answered gingelly
    (sesame) oil, citing the allergen-note chunk rather than the method chunk
    that actually describes oiling the tawa.

14. **`97da638b`** — "Should the appam batter rest after adding coconut milk?":
    quoted the stir-in instruction, then added a second sentence saying the
    text does not state the batter should rest; both sentences quote the same
    fragment and one carries a bracketed "[j]ust".

15. **`407b4250`** — "How thin should dosa batter be?": answered "thinner than
    idli batter… pouring-cream consistency", matching the cited method.

16. **`eb9ee143`** — "How much starter curd do I need for 1 litre of milk?":
    answered 30g per 1000g, silently treating the card's 1000g of milk as the
    asked-for litre.

17. **`08b2ff45`** — "Give me a biryani recipe.": refused; no retrieved chunk
    mentions biryani.

18. **`7c7023dc`** — "Is it done?": refused a question with no referent; the
    retrieved chunks were five method sections, three of which contain
    doneness cues.

19. **`00e338e3`** — "How should I store koozh after cooking?": refused,
    although the retrieved koozh method chunk says the porridge is cooled,
    thinned to drinking consistency and traditionally enjoyed the next day.

20. **`d8af00bd`** — "When do I add the salt to the koozh?": answered "at the
    end of cooking the porridge", matching the cited method; the replay of
    this same trace produced "at the end of cooking the koozh" instead.

---

## Counts behind the taxonomy

- Behaved correctly: **11 / 20 (55%)** — 8 answered correctly with a resolving
  citation (6, 8, 10, 11, 12, 15, 16, 20) and 3 correctly refused
  out-of-corpus questions (2, 9, 17).
- Showed a problem: **9 / 20 (45%)** — traces 1, 3, 4, 5, 7, 13, 14, 18, 19,
  clustered in `taxonomy.md`.

## Why a public benchmark would not have surfaced these (requirement 6)

MMLU and HumanEval measure a model's general knowledge and coding ability on
public question sets; not one of their items contains my six recipe cards, my
chunk boundaries, or my grounding prompt, so no score they produce can move
when those change. Every top-3 mode below is a property of *the system I
assembled* — an over-strict refusal rule meeting a vague question, a citation
pointing at the chunk that repeats a fact rather than the one that instructs
it, a table row surfaced without the context that says which row the cook
needs — and none of them is a property of the model in isolation. A model
could rank first on every public leaderboard and still produce all nine of
the failures above on my corpus, which is exactly why the traces, not the
benchmarks, tell me what to fix first.

---

## Committed prediction (requirement 5)

`prediction.txt` was committed **before any fix was applied**:

- **Commit:** `2c67827e5950412e2ae45bed5987bd57cc50948c`
- **Date:** 2026-09-17 03:54:46 +0530
- **Target:** Mode 1 (refuses one-line questions instead of asking which
  recipe), 15% → under 5% on a fresh seeded 20-trace sample, with
  out-of-corpus refusals and invented-quantity checks held at 100%.

Verify the ordering with `git log --follow prediction.txt` — no commit
touching the grounding prompt exists before that hash.
