# Week 5 — Failure taxonomy (recipe assistant)

Built from 20 traces drawn at random from 58 (`seed 20260917`), open-coded one
sentence at a time in `notes.md` **before** any category existed.
Behaved correctly: 11/20 (55%). Showed a problem: 9/20 (45%).

Severity scale (from the task): **ruins the dish** = a cook following this
gets a wrong result or a safety risk · **annoys the cook** = they get nothing
useful and must ask again or go read the card themselves.

| # | Failure mode | Count | Freq | Severity | Example trace |
|---|---|---|---|---|---|
| 1 | Refuses a one-line question instead of asking which recipe is meant | 3 | 15% | annoys the cook | `4b3ae3f7` |
| 2 | Refuses even though the answer is in the chunk it just retrieved | 2 | 10% | annoys the cook | `00e338e3` |
| 3 | Lists every matching table row without saying which one the cook needs | 1 | 5% | **ruins the dish** | `f6873d76` |
| 4 | Refuses any question needing one number compared across cards | 1 | 5% | annoys the cook | `d19072d0` |
| 5 | Cites the chunk that repeats a fact instead of the one that instructs it | 1 | 5% | annoys the cook | `ac1aa143` |
| 6 | Answers a yes/no question by re-quoting the method twice | 1 | 5% | annoys the cook | `97da638b` |

## What each mode looks like

**1 — Refuses a one-line question instead of asking which recipe is meant**
(`8c2b5e88`, `4b3ae3f7`, `7c7023dc`). "How much salt?", "Is it done?", "Can I
make it faster?" all retrieve five different recipes' chunks and then produce
the refusal sentence. The cook gets nothing, and is never told that naming a
recipe would work. Biggest single mode in the sample.

**2 — Refuses even though the answer is in the chunk it just retrieved**
(`15466577`, `00e338e3`). The koozh storage question retrieved the koozh
method, which says the porridge is cooled, thinned and traditionally enjoyed
the next day — and was refused anyway. Same shape for "why didn't my batter
rise" with both fermentation-condition chunks in context.

**3 — Lists every matching table row without saying which one the cook needs**
(`f6873d76`). "What rice do I use for appam?" returned "raw rice (pachari),
soaked, and cooked rice" — both rows are in the table, but 500g of raw rice is
the base grain and 100g of cooked rice is a texture addition. A cook who
treats them as interchangeable ruins the batter, which is why this singleton
carries the sample's only dish-ruining severity.

**4 — Refuses any question needing one number compared across cards**
(`d19072d0`). "Which recipe has the highest salt percentage?" — every value
exists on the cards, but no chunk contains the comparison, and top-5 cannot
hold all six tables at once. (Same failure this project's Week 4 measurement
predicted no retrieval change could fix.)

**5 — Cites the chunk that repeats a fact instead of the one that instructs it**
(`ac1aa143`). The tawa-oil answer is correct but cites the allergen note,
which mentions gingelly oil in passing, rather than the method line that tells
you to use it. A reader clicking the citation lands on the wrong sentence.

**6 — Answers a yes/no question by re-quoting the method twice**
(`97da638b`). "Should the appam batter rest?" got the stir-in instruction, then
a second sentence quoting the same fragment to say resting is not mentioned —
including a stray bracketed "[j]ust". The answer is not wrong, it is unusable.

## Fix order

Modes 1 and 2 are the same shape from the cook's side — **the app had
something useful and said nothing** — and together account for 5 of the 9
failures (25% of the sample). Mode 3 is a single trace but the only one that
can ruin a dish, so it stays visible above the merely annoying singletons
4–6 despite its frequency.

Attacking mode 1 first: it is the most frequent, the change is confined to the
grounding prompt, and modes 4–6 either need retrieval work (4) or affect one
trace each. The dated prediction for that attack is in `prediction.txt`.
