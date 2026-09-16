# Week 7 Practical — Task Set B — results

**Race the recipe agent against a fixed workflow.**
Task: find the recipe, scale it, swap out banned allergens, return the method.
Model `gemini-flash-lite-latest`, temperature 0, same three tools for both
systems, same output contract.

## Headline — the 8 numbers (requirement 3)

| System | Pass rate | p50 latency | Total tokens (10 requests) | Cost / request |
|---|---|---|---|---|
| **agent** | 10/10 | 18.22 s | 34,024 | $0.000422 |
| **workflow** | 10/10 | 4.47 s | 1,555 | $0.000023 |

Ratios: workflow is **21.9× fewer tokens**, **18.3× cheaper**, **4.1× faster**,
at an identical pass rate. Per-request detail in `race.csv`.

**Pass rate by request class — including the class built to force an agent:**

| Class | n | agent | workflow |
|---|---|---|---|
| simple-scale | 4 | 4/4 | 4/4 |
| single-swap | 2 | 2/2 | 2/2 |
| **allergen-cascade** | 4 | **4/4** | **4/4** |

**Latency caveat, stated honestly.** The free tier is paced at 4.5 s between
calls in `ask.call_llm`, so measured latency is dominated by *number of LLM
calls × pacing*, not by model speed: the agent makes ~5 calls per request,
the workflow makes exactly 1. The 4.1× ratio is therefore really the call-count
ratio. Un-paced, a single workflow run measured 1.64 s against the agent's
19.17 s on the same request. The token and cost columns are unaffected by
pacing and are the load-bearing numbers.

**Token accounting.** Agent tokens are summed over **every lap**, not just the
final call — the loop re-sends the whole message list each time, so counting
only the last call would have understated agent cost by roughly 5×.

## The 10 requests (requirement 3)

`w7_requests.jsonl`. Four of the ten are allergen-cascade cases where step 3
depends on what step 2 returned — the first substitute is itself a banned
allergen, so a second swap is required:

| # | Request | Class |
|---|---|---|
| 1–4 | double idli / halve dosa / kadumanga ×3 / koozh ×1.5 | simple-scale |
| 5 | thayir dairy-free | single-swap |
| 6 | mango pickle sesame-free | single-swap |
| 7 | **appam halved, coconut-free AND nut-free** | allergen-cascade |
| 8 | **thayir dairy-free AND nut-free** | allergen-cascade |
| 9 | **mango pickle sesame-free AND nut-free** | allergen-cascade |
| 10 | **appam doubled, coconut-free, nut-free AND gluten-free** | allergen-cascade |

The cascade is real, not decorative. For appam: coconut milk → almond milk
(*carries nuts*) → oat milk (*carries gluten*) → sunflower-seed milk (*clean*).
Request 10 bans all three, so only the third option survives.

**Pass criterion** (`w7_race.py:check`): output parses as contract JSON, correct
`recipe_id`, correct `scale_factor`, and **no banned allergen survives** —
checked against the allergen carried by whichever substitute was chosen, which
is what makes the cascade genuinely gradeable rather than cosmetic.

## The third tool (requirement 1)

`substitute_ingredient(recipe_id: str, allergen: enum)`:

```
"description": "List replacement options for the ingredients of one recipe_id
 that carry a given allergen class. Each option states the allergen it itself
 carries, so a follow-up swap can be made if the first choice is also banned.
 Does not scale quantities and does not search for recipes.",
"parameters": {"allergen": {"type": "string",
                            "enum": ["dairy","sesame","nuts","coconut","soy",
                                     "gluten","mustard"]}}
```

**One job:** allergen swaps only. **Typed/enum parameters:** `allergen` is an
enum over seven classes; an out-of-enum value returns an error rather than a
guess. **No overlap:** each of the three descriptions ends by disclaiming the
other two's jobs —

| Tool | Owns | Explicitly disclaims |
|---|---|---|
| `search_recipes` | which recipe (identity) | quantities, methods, allergen advice |
| `scale_recipe` | how much (arithmetic) | choosing recipes, allergens, substitutes |
| `substitute_ingredient` | what to swap (allergens) | scaling, searching |

**Diff disclosure.** Weeks 3–6 of this project had no tool layer at all — the
RAG app called no functions — so there was no pre-existing two-tool file to
diff against. All three tools were authored in one commit and the third is
shown above in full; `git show <commit> -- w7_tools.py` is the diff. The
non-overlap property was designed in rather than repaired after tool thrash,
which is why no "use the correct tool" patch appears in the system prompt.

## The workflow is genuinely the same task (requirement 2)

`w7_workflow.py` — same inputs, same three tools, same model, same output
contract, **no loop over model decisions**:

```
step 1  ONE model call: parse request -> {dish, factor, banned[]}
step 2  search_recipes(dish)                          deterministic
step 3  for each banned allergen: substitute_ingredient(...), then take the
        first option whose own allergen is not also banned   <- cascade rule
step 4  scale_recipe(recipe_id, factor)               deterministic
step 5  assemble output JSON                          deterministic, no model
```

The `for` in step 3 iterates a list that step 1 already fixed; **no model call
happens inside it**, so there is no agent loop hiding in the workflow. Steps
2–5 make zero LLM calls, which is the whole reason the workflow uses 155
tokens per request against the agent's 3,402.

## Budgets (requirement 4)

Four budgets, all **checked at the top of every lap** in `w7_agent.py`, not
merely declared as constants:

```python
if usage["in"] + usage["out"] >= MAX_TOKENS:  stop_reason = "BUDGET:max_tokens" ; break
if cost_of(usage)            >= MAX_COST_USD: stop_reason = "BUDGET:max_cost"   ; break
if elapsed                   >= MAX_WALL_SEC: stop_reason = "BUDGET:wall_clock" ; break
else:  # for/else — loop exhausted
    stop_reason = "BUDGET:max_iters"
```

`python w7_budget_demo.py` runs the same hard request four times, lowering one
budget each time. Full log in `results/w7_budget_log.txt`; each fired cleanly:

```
--- scenario: max_iters (MAX_ITERS=2) ---
  STOPPED: BUDGET:max_iters (2 laps used)
  laps=2  tokens=1336  cost=$0.000148  latency=5.18s

--- scenario: max_tokens (MAX_TOKENS=1200) ---
  STOPPED: BUDGET:max_tokens (1336 >= 1200)
  laps=2  tokens=1336  cost=$0.000148  latency=9.01s

--- scenario: max_cost (MAX_COST_USD=0.0002) ---
  STOPPED: BUDGET:max_cost ($0.00024 >= $0.0002)
  laps=3  tokens=2203  cost=$0.000242  latency=13.58s

--- scenario: wall_clock (MAX_WALL_SEC=6) ---
  STOPPED: BUDGET:wall_clock (9.0s >= 6s)
  laps=2  tokens=1336  cost=$0.000148  latency=9.04s
```

In every case the loop returned normally with `final=None` and a named
`stop_reason` — no exception, no spin, no partial answer presented as complete.

## Verdict (requirement 5) — 141 words

All four numbers favour the workflow: identical 10/10 pass rate, 4× faster,
22× fewer tokens, 18× cheaper. Applying the decision rule — *does the path vary
by input?* — it does not. Every one of these ten requests resolves to the same
three steps: identify, swap, scale. The allergen cascade looked like the
agent-forcing class, and the dependency is real: the first substitute for
coconut carries nuts, so a second choice is genuinely required. But the
dependency is **enumerable**. "Take the first option whose own allergen is not
banned" is four lines of Python, and the workflow scored 4/4 on the cascade
class using exactly that. **No request class among the ten forces an agent, and
I ship the workflow.** An agent would earn its place only if the substitution
space stopped being enumerable — user-supplied pantry contents, or swaps
requiring open-ended reasoning about what a dish can tolerate.

## Two bugs worth recording

**1. Gemini rejects hand-rebuilt tool-call messages.** Echoing the assistant
message back by reconstructing `{"role":"assistant","tool_calls":[...]}`
produced `400: Function call is missing a thought_signature in functionCall
parts`, killing the loop on lap 2. Gemini stores a signature inside
`tool_calls[].extra_content.google.thought_signature`; dropping it invalidates
the turn. Fix: append `msg.model_dump(exclude_none=True)` verbatim instead of
rebuilding. Worth knowing before writing any agent loop against Gemini.

**2. My own race harness had a key mismatch** (`r['tokens']` where the runner
returns `tokens_total`), which crashed the first race run before any numbers
were produced. Caught and fixed before the measured run.

## Honest limitations

- **n = 10**, so one request is 10 percentage points of pass rate; both systems
  scoring 10/10 means this race separates them on cost and latency, not on
  correctness. A harder input mix might separate correctness too.
- **Latency is pacing-dominated** (see caveat above); read the call-count ratio,
  not the seconds.
- **Cost is modelled**, not billed: $0.10/$0.40 per 1M input/output tokens,
  declared as `PRICE_IN`/`PRICE_OUT` in `w7_agent.py`. The ratio between the two
  systems is unaffected by the rate card's accuracy.
- **The cascade was authored by me**, so its enumerability is a property of my
  substitution table. That is exactly what the verdict says: with an
  unbounded substitution space the conclusion could flip.

## Files

| File | Contents |
|---|---|
| `w7_tools.py` | the three tools, schemas, cascading substitution table |
| `w7_agent.py` | the agent loop, four enforced budgets, per-lap token summing |
| `w7_workflow.py` | the fixed workflow — one model call, four deterministic steps |
| `w7_requests.jsonl` | the 10 race requests, 4 of them cascade cases |
| `w7_race.py` | race harness + pass checker |
| `w7_budget_demo.py` | fires each budget in turn |
| `race.csv` | 20 rows: per-request pass, latency, tokens, cost, laps |
| `results/w7_budget_log.txt` | full budget-termination log |
