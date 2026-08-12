# Week 3 Practical — Task Set B: Results

Corpus: 6 fermentation-chapter recipe cards (South Indian), self-authored to
the task's card format because the official Set B pack was unavailable.
Honesty notes, recorded up front:

- Q1 was used once as a pipeline smoke-test demo before the question list was
  frozen; the other 7 were never searched before measurement.
- There is no pre-existing "old cards" index in this project, so the corpus is
  the 6 new cards only (24 chunks per strategy). This matters for reading the
  hit-in-top-5 numbers — see section 6.
- Per the task's time-reality rule: only the 6 new cards were indexed. No
  full-corpus re-index was performed at any point.

---

## 1. The 8 known-answer questions (frozen before measurement)

| # | Question | Known answer | Recipe | Section | Type |
|---|---|---|---|---|---|
| 1 | How much rock salt goes into the 2kg batch of idli batter? | 20g (2% of rice) | idli-batter-01 | Ingredients table | table row |
| 2 | How much fine sea salt is in the appam batter? | 7g (1.4% of rice) | appam-03 | Ingredients table | table row |
| 3 | What weight of crystal sea salt brines the kadumanga mangoes? | 150g (15% of mango) | kadumanga-06 | Ingredients table | table row |
| 4 | How much poha goes into the crisp dosa batter? | 50g (6.7% of rice) | dosa-batter-02 | Ingredients table | table row |
| 5 | Milk temperature before adding the curd starter? | 40–43°C | thayir-04 | Method | method prose |
| 6 | How long does the ragi slurry ferment before cooking? | 10–12 hours | ragi-koozh-05 | Method | method prose |
| 7 | Dosa batter fermentation time and temperature? | 10–14 h at 26–30°C | dosa-batter-02 | Method | method prose |
| 8 | Why might kadumanga achar not be gluten-free? | hing is bound with wheat flour | kadumanga-06 | Allergen note | allergen note |

4 of 8 depend on an ingredient-table row (requirement: at least 3).

Hit criterion, frozen with the questions: a top-5 chunk whose metadata
recipe_id matches AND whose text contains the answer substring. Gram-weight
substrings carry a leading space (" 20g") so they cannot false-match inside
"~720g" or "250g" — a bug found and fixed before any measurement ran.

---

## 2. The two hit-in-top-5 numbers (same 8 questions, k=5)

| Strategy | hit-in-top-5 | already at rank 1 |
|---|---|---|
| naive (400-char windows, 50 overlap) | **8/8** | 6/8 |
| structure-aware (section chunks + title on every chunk) | **8/8** | 6/8 |

Per-question record (rank of first correct chunk):

| Q# | Type | Naive | Structure |
|---|---|---|---|
| 1 | table row | hit @1 | hit @1 |
| 2 | table row | hit @1 | hit @2 |
| 3 | table row | hit @1 | hit @2 |
| 4 | table row | hit @1 | hit @1 |
| 5 | method | hit @1 | hit @1 |
| 6 | method | hit @2 | hit @1 |
| 7 | method | hit @1 | hit @1 |
| 8 | allergen | hit @3 | hit @1 |

Full search-only dump for all 8 questions under both strategies:
`results/search_dump.md`.

---

## 3. Metadata filter demonstrably changing retrieval

Query: *"which fermented dish is safe for someone who cannot eat gluten?"*
(structure index, k=3)

**Unfiltered:**

| rank | sim | chunk_id | recipe | dietary_tags |
|---|---|---|---|---|
| 1 | 0.485 | kadumanga-06::structure::3 | kadumanga-06 | vegan, contains-sesame |
| 2 | 0.436 | ragi-koozh-05::structure::3 | ragi-koozh-05 | vegan, gluten-free |
| 3 | 0.430 | idli-batter-01::structure::3 | idli-batter-01 | vegan, gluten-free |

**Filtered with `tag_gluten_free = True`:**

| rank | sim | chunk_id | recipe | dietary_tags |
|---|---|---|---|---|
| 1 | 0.436 | ragi-koozh-05::structure::3 | ragi-koozh-05 | vegan, gluten-free |
| 2 | 0.430 | idli-batter-01::structure::3 | idli-batter-01 | vegan, gluten-free |
| 3 | 0.423 | dosa-batter-02::structure::3 | dosa-batter-02 | vegan, gluten-free |

The top-1 result changes — and the unfiltered top-1 is the dangerous case:
the kadumanga card is NOT gluten-free (its asafoetida contains wheat), yet it
ranked first precisely because its allergen note discusses gluten at length.
Similarity matches topic, not truth; the metadata filter is the hard wall.

---

## 4. Three cited answers (verbatim; model: gemini-flash-latest, temp 0)

Every citation was programmatically verified to resolve to a real chunk_id
in the index (`verify_citations()` in ask.py). Full transcripts with the
retrieved chunk lists: `results/generation_transcripts.md`.

**Q: How much rock salt goes into the 2kg batch of idli batter?**
> 20g of rock salt goes into the 2kg batch of idli batter
> [idli-batter-01::structure::1].

Citation resolves; the cited chunk is the idli ingredients table containing
the row `| Rock salt | 20g | 2% |`. ✔

**Q: To what temperature should the milk be cooled before adding the curd starter?**
> The milk should be cooled to 40–43°C before adding the curd starter
> [thayir-04::structure::2].

Citation resolves; the cited chunk is the thayir Method section containing
"Cool to 40–43°C". ✔

**Q: Why might kadumanga achar not be suitable for a gluten-free diet?**
> Kadumanga achar as written is not gluten-free because it contains
> asafoetida (hing), and most asafoetida is bound with wheat flour
> [kadumanga-06::structure::3].

Citation resolves; the cited chunk is the kadumanga Allergen note stating
exactly this. ✔

## 5. Three refusal transcripts (verbatim)

No card carries nutrition or storage data, so all three must be refused.
The refusal is forced, not suggested: the system prompt supplies an exact
refusal sentence and declares any unsupported answer a failure.

**Q: How many calories are in one idli?**
> I cannot find this in the recipe cards.

REFUSED correctly. ✔

**Q: How much protein does the dosa batter contain per 100g?**
> I cannot find this in the recipe cards.

REFUSED correctly. ✔

**Q: How long does idli batter keep in the refrigerator?**
> I cannot find this in the recipe cards.

REFUSED correctly. ✔ (The riskiest of the three: fermentation times appear
all over the corpus, so semantically-near chunks were retrieved — the model
still refused rather than repurposing a fermentation duration as shelf life.)

---

## 6. Which chunker ships, and why

**Structure-aware ships.** The headline numbers tie (8/8 vs 8/8), but the tie
is an artifact of corpus size: 24 chunks means top-5 covers 21% of the whole
corpus, so hit-in-top-5 saturates. The rank-level record and the retrieved
text tell the real story. Every structure-aware chunk is self-contained —
recipe title plus intact ingredient table — so whatever reaches generation
carries its own context. Naive's hits include headless fragments (a chunk
beginning "0g | 20% | | Sugar...") that rely on metadata alone to identify
their recipe, which invites cross-recipe confusion the moment the corpus
grows or generation reads only the top result.

**The retrieval that embarrassed me:** on Q8 ("why might kadumanga not be
gluten-free?"), the naive index's rank-1 result was a chunk whose entire
content is the 12-character fragment `"Gluten-free."` — sliced off the end
of the thayir card by a 400-character boundary. A meaningless shred outranked
the true answer because its embedding is 100% concentrated on the query's
keyword. Diagnosis: fixed-size cutting created a fragment with pathological
keyword density; the same cutter caused it and the same cutter can't prevent
it. Structure-aware put the correct allergen-note chunk at rank 1.

Structure-aware has a flaw of its own, found in this measurement: it emits
tiny "intro stub" chunks (title + one sentence) that steal rank-1 on
recipe-named queries (Q2, Q3). The fix — merging the stub into the ingredients
chunk — is the next single change to measure, not something to bundle into
this comparison.

---

## 7. Code

- **Code diff for the second chunker:** `results/chunker_diff.patch` — the
  literal `git diff` of the commit that added `chunk_structure_aware`
  (also viewable as commit 2 in the repo history)
- `chunkers.py` — both strategies side by side (the second chunker is
  `chunk_structure_aware`, lines 30–58)
- `ingest.py` — metadata on every chunk: source_file, recipe_id, cuisine,
  dietary_tags (+ boolean tag fields for filtering); ingest asserts
  source_file is present, per the task's failed-ingest rule
- `measure.py` — the hit-in-top-5 harness; `search.py` — search-only CLI;
  `ask.py` / `transcripts.py` — grounded generation with forced refusal
