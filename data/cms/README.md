# CMS export (Pantry-to-Plate capstone)

The publisher's recipe library as the app sees it. One file per recipe
**version**: `<recipe_id>.<version>.md`.

- **Front matter = the CMS fields.** `allergens`, `may_contain`,
  `allergen_sources` and `serving_suggestion_allergens` are the legal
  declaration. The app checks allergens **only** against these fields, by
  exact match (`pantry_corpus.check_allergens`), never against the text.
- **Body = the page text.** It is chunked and indexed for search. It can be
  wrong: both `reformulated-2025` files still carry the old "## Allergen note"
  that nobody updated after the supplier change. The nankhatai page says
  "nut-free" while its declaration says `nuts`. That is deliberate. It is the
  failure the client described.
- **Versions.** `nankhatai-07` and `kadumanga-06` exist as `original`
  (`status: superseded`) and `reformulated-2025` (`status: current`). Both
  stay in the index, because the client's CMS still has both. The other
  recipes have one version, `original` (`status: current`).
- `food-safety-chart.original.md` is the test kitchen's safe-temperature
  chart. `substitutions.csv` is the test kitchen's substitutions table: each
  swap states the allergen it carries itself.

Scale note: the client has 600 recipes, 80 of them in two versions. This
export has 9 recipes and 11 versions, built for the capstone from the six
Week 3 cards (unchanged text) plus three new ones. The data is synthetic: the
supplier codes and "may contain" fields are invented to exercise the system.
