# error_before_after.md — one docstring rewritten as a prompt, one error made recoverable

**Tool:** `search_recipes` on our own server (`w9_recipe_server.py`). One tool only.
**Change:** commit `2559b3c` (before) → commit `7fd46db` (after). The matching logic
is identical in both; only the docstring and the error message changed.
`w9_agent.py` changed by **0 lines** across this change too.

## The change

**Docstring — before:**
```
Search recipes.
```

**Docstring — after (written as a prompt: when to call, what to pass, what comes back, what to do on failure, what never to do):**
```
Find which recipe card matches a dish the user named. Call this FIRST for
any request about a recipe: every other recipe tool needs the recipe_id it
returns.

Pass the dish name only - e.g. "appam", "thayir curd", "mango pickle" - not
the user's whole sentence. Returns up to 3 matches, each with recipe_id,
title, cuisine and dietary tags: identity only, no quantities, no method.

If nothing matches, the error names the closest known dish and lists all
six; retry with one of those exact names instead of guessing, and tell the
user which dish you used. Never invent a recipe_id.
```

**Error path — before:**
```
Error 3
```

**Error path — after:**
```
No recipe matched 'plain dosai' - a name miss; the server is working. Closest known
dish: 'Crisp Dosa Batter'. All six dishes: 'Idli Batter', 'Crisp Dosa Batter', 'Appam',
'Thayir', 'Ragi Koozh', 'Kadumanga Achar'. Retry search_recipes with one of these exact
names, and tell the user which dish you used.
```

The new error does three jobs the old one could not: it says **what kind** of failure
this is (a name miss, not a dead server), it says **what to do** (retry, with the exact
strings), and it says **what the user must be told** (which dish was substituted). Every
suggested retry name was checked to match under the server's own strict matcher — the
docstring's promise is verified, not hoped.

## The same failing call, both runs

Same request, same model (`gemini-flash-lite-latest`), temperature 0, same config:

```
python w9_agent.py 'Halve the "plain dosai" recipe.'
```

**Both runs made the identical first call:** `recipes__search_recipes({"dish": "plain dosai"})`,
and both got an error back — so the comparison is how the model handled that failure.

### Before — `Error 3`  (trace: `results/w9_trace_error_before.jsonl`)

```
lap 1: recipes__search_recipes({"dish": "plain dosai"})
        -> ERROR Error executing tool search_recipes: Error 3
lap 2: recipes__search_recipes({"dish": "dosai"})
        -> ERROR Error executing tool search_recipes: Error 3
lap 3: recipes__search_recipes({"dish": "dosa"})
        -> {"recipe_id": "dosa-batter-02", "title": "Crisp Dosa Batter", ...}
lap 4: recipes__search_recipes({"dish": "plain"})
        -> ERROR Error executing tool search_recipes: Error 3
lap 5: recipes__scale_recipe({"factor": 0.5, "recipe_id": "dosa-batter-02"})
        -> {"recipe_id": "dosa-batter-02", "scale_factor": 0.5, "ingredients": [...]}
lap 6: recipes__get_recipe({"recipe_id": "dosa-batter-02"})
        -> {"recipe_id": "dosa-batter-02", "title": "Crisp Dosa Batter", ...}
lap 7: FINAL ANSWER
        "Here is the halved recipe for **Crisp Dosa Batter**: ..." (+ the method)
```

The model recovered by **blind trial and error** — trimming the query word by word.
Lap 4 is the telling one: it had *already found* the dish at lap 3, then searched
`"plain"` anyway. With nothing but `Error 3`, it could not tell whether the searches were
missing or the server was broken, so it kept probing. The final answer also never tells
the user that "plain dosai" did not exist and a different dish was substituted.

### After — recoverable error  (trace: `results/w9_trace_error_after.jsonl`)

```
lap 1: recipes__search_recipes({"dish": "plain dosai"})
        -> ERROR Error executing tool search_recipes: No recipe matched 'plain dosai' - a
           name miss; the server is working. Closest known dish: 'Crisp Dosa Batter'. ...
lap 2: recipes__search_recipes({"dish": "Crisp Dosa Batter"})
        -> {"recipe_id": "dosa-batter-02", "title": "Crisp Dosa Batter", ...}
lap 3: recipes__scale_recipe({"factor": 0.5, "recipe_id": "dosa-batter-02"})
        -> {"recipe_id": "dosa-batter-02", "scale_factor": 0.5, "ingredients": [...]}
lap 4: FINAL ANSWER
        "*(Using "Crisp Dosa Batter" for "plain dosai")*
         Here is the halved recipe for Crisp Dosa Batter: ..."
```

The model read the error, retried **once**, with the **exact** suggested string, and
followed the instruction to tell the user which dish it used.

## Before vs after

| | Before (`Error 3`) | After (recoverable) |
|---|---|---|
| Same failing first call | `search_recipes("plain dosai")` | `search_recipes("plain dosai")` |
| Failed tool calls | 3 | **1** |
| Retry strategy | blind trimming, word by word | the exact name the error supplied |
| Laps | 7 | **4** |
| Tokens | 8,078 | **4,827** (−40%) |
| Cost (modelled) | $0.000926 | **$0.000538** |
| Latency | 30.57 s | **16.58 s** |
| User told a dish was substituted | no | **yes** |
| Final amounts correct | yes | yes |

## Honest reading

- **Both runs ended with correct amounts.** The old error did not make the model fail;
  it made it *flail* — three failed calls, one of them after it had already succeeded.
  The recoverable error's win is efficiency and transparency, not rescue from failure.
- **Not all of the saving is the error message.** The before run also called
  `get_recipe` to include the method; the after run did not. Of the three laps saved,
  two are fewer blind retries and one is the model not fetching the method this time.
  The after answer is therefore amounts-only, which satisfies "halve the recipe" but is
  a real difference, reported rather than hidden.
- **The most important change is the one a metric barely shows:** the after answer
  tells the user it substituted a dish. An agent that silently swaps what you asked for
  something else is exactly the right-answer-wrong-path problem from Week 8.
- **n = 1 run each**, at temperature 0. It shows the mechanism clearly; it is not a
  statistical claim about how often each version recovers.
