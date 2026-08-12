# The 8 known-answer questions (written BEFORE any measurement runs)

Rule followed: questions were written from the recipe cards directly, not
from retrieval output. Q1 was used once as a pipeline smoke-test demo before
this list was frozen — noted here for transparency.

At least 3 must depend on an ingredient-table row: Q1–Q4 all do (4 of 8).

| # | Question | Expected answer | Recipe | Section | Type |
|---|---|---|---|---|---|
| 1 | How much rock salt goes into the 2kg batch of idli batter? | 20g (2% of rice) | idli-batter-01 | Ingredients table | table row |
| 2 | How much fine sea salt is in the appam batter? | 7g (1.4% of rice) | appam-03 | Ingredients table | table row |
| 3 | What weight of crystal sea salt is used to brine the tender mangoes for kadumanga achar? | 150g (15% of mango) | kadumanga-06 | Ingredients table | table row |
| 4 | How much poha (flattened rice) goes into the crisp dosa batter? | 50g (6.7% of rice) | dosa-batter-02 | Ingredients table | table row |
| 5 | To what temperature should the milk be cooled before adding the curd starter? | 40–43°C | thayir-04 | Method | method prose |
| 6 | How long should the ragi slurry ferment before the koozh is cooked? | 10 to 12 hours (overnight, clay pot) | ragi-koozh-05 | Method | method prose |
| 7 | How long and at what temperature does the dosa batter ferment? | 10 to 14 hours at 26–30°C | dosa-batter-02 | Method | method prose |
| 8 | Why might kadumanga achar not be suitable for a gluten-free diet? | The asafoetida (hing) is usually bound with wheat flour | kadumanga-06 | Allergen note | allergen note |

## Why these 8 (design notes)

- **Q1 + Q2 are the chunker stress test.** Three cards contain salt rows with
  different weights (20g idli, 18g dosa, 7g appam). A chunker that orphans a
  table row from its recipe title lets the wrong salt weight answer the
  question — the exact failure the task describes.
- **Q4 vs the kadumanga card:** "50g" appears in two different cards (poha in
  dosa, chilli powder in kadumanga). A hit only counts if the chunk's
  recipe_id is also correct.
- **Q7 vs Q6:** dosa and idli ferment times are near-identical phrases in
  near-twin cards — tests whether retrieval separates the two batters.
- **Q8** lives in an allergen note, the smallest section — tests whether tiny
  sections survive as findable chunks.

## Hit criterion for the Step 3 measurement

A question counts as a **hit** if any of the top-5 retrieved chunks
(a) has the expected recipe_id in its metadata, AND
(b) contains the expected answer text.
Both conditions, per question, recorded individually — no summary claims.

Gram-weight substrings carry a leading space (" 20g", " 50g") so they cannot
falsely match inside other numbers ("~720g", "250g") — a chunk holding only
the wrong table row must not score as a hit.
