# Week 9 Practical — Task Set B — results

**Bolt on the ingredient database server without touching the agent.**
Host agent `w9_agent.py` · MCP Python SDK 2.2.0 · model `gemini-flash-lite-latest`,
temperature 0 · stdio transport · commits pushed to `week3-rag`.

> **In this repo (recipe-bot):** the zero-line proof is commits `f3c0f6b` (server one) -> `67f129d` (server two); see `agent_diff.txt`. Hashes quoted below (`ad65f73`, `2559b3c`, `7fd46db`) are the original working history in the week3-rag repo.

## Headline

| | |
|---|---|
| Lines changed in the agent when server two was added | **0** (identical sha256 at both commits) |
| Tools discovered via `tools/list` | **4 → 6** |
| Server-two tool called in a live query | **`ingredient_db__lookup_allergens`** (×2, lap 3) |
| Raw wire messages captured and annotated | **9 messages, 44 annotations**, every top-level field |
| Recoverable-error rewrite, same failing call | failed calls **3 → 1**, laps **7 → 4**, tokens **−40%** |
| Risk note | **5 lines** — ship, with conditions |

## The three commits that carry the proof

| Commit | What changed | Agent lines changed |
|---|---|---|
| `ad65f73` **A** | agent + our recipe server; config lists server one only | — (baseline) |
| `2559b3c` **B** | `mcp_config.json` +4 lines; `ingredient_db_server/` added | **0** |
| `7fd46db` **C** | `search_recipes` docstring + error rewritten (our server only) | **0** |

## 1. Server two added and provably called (requirement 1)

The config gained one entry (`config_diff.txt`). Then a live query:

```
python w9_agent.py "Is the thayir curd recipe safe for someone with a nut allergy?
                    Check the allergen flags of each of its ingredients."
```

Trace (`results/w9_trace_server2_query.jsonl`):

```
lap 1: recipes__search_recipes           server=recipes        {"dish": "thayir curd"}
lap 2: recipes__get_recipe               server=recipes        {"recipe_id": "thayir-04"}
lap 3: ingredient_db__lookup_allergens   server=ingredient_db  {"ingredient": "Whole milk (full-fat)"}
lap 3: ingredient_db__lookup_allergens   server=ingredient_db  {"ingredient": "Live curd from the previous batch"}
lap 4: FINAL ANSWER — safe for a nut allergy; both ingredients carry dairy, neither carries nuts
```

The agent composed tools from **two servers in one run**, including two it had never
been coded against. The `server__tool` prefix in every name shows which server answered.

## 2. Zero lines changed in the agent (requirement 2)

`agent_diff.txt`:

```
$ git diff A B -- w9_agent.py | wc -l        -> 0
$ git diff A B -- ask.py                     -> (no output)   # the helper it imports
sha256 w9_agent.py at A: e6c0b1a0104e83ac98f675fcd5f39a4f8bfc912c0dea92c38fb5e468c2d685cb
sha256 w9_agent.py at B: e6c0b1a0104e83ac98f675fcd5f39a4f8bfc912c0dea92c38fb5e468c2d685cb
$ git diff --stat A B
 ingredient_db_server/ingredients.json | 767 +++
 ingredient_db_server/server.py        |  89 +++
 mcp_config.json                       |   4 +
```

**Why it works:** `w9_agent.py` never names a tool. At startup it reads the config,
starts each server, calls `initialize` then `tools/list` on each, and hands whatever
comes back to the model. It prefixes every tool name with its server so two servers
can't collide, and strips JSON-Schema keywords Gemini rejects (`title` and friends —
visible in the raw `tools/list` capture). None of that is server-specific, so a new
server needs no code.

## 3. Tool count from tools/list (requirement 3)

`tool_counts.md`, generated from the saved raw `tools/list` responses:

**4 before → 6 after.**
- Before: `recipes__search_recipes`, `recipes__get_recipe`, `recipes__scale_recipe`, `recipes__substitute_ingredient`
- Added by config: `ingredient_db__lookup_allergens`, `ingredient_db__lookup_nutrition`

The ingredient server also offers `allergens://matrix` as a **resource**, not a tool —
the standing allergen matrix is reference context a host attaches, not something the
model should fetch on every turn (the task's common mistake #3). It is correctly
absent from the tool count.

## 4. The raw wire, annotated (requirement 4)

`wire.json` — captured by `w9_wire_capture.py`, which writes JSON lines to the server's
stdin by hand: **no SDK client and no model anywhere.** Sequence:
`initialize → notifications/initialized → tools/list → tools/call` (plus a deliberately
failing `tools/call`). All 9 messages, every top-level field annotated (checked in code).

**Where the model call happens:** *The model is called only by the host
(`w9_agent.py → call_llm`), between `tools/list` and `tools/call`, where it reads the
tool schemas and chooses the call; nothing in this exchange touches a model, and the
server never does.* The capture itself proves the second half: the whole protocol ran
with no model present.

Three things the capture showed that I would not have guessed:

1. **Version negotiation happened live.** The client asked for protocol `2026-07-28`;
   the server replied `2025-11-25`, the newest its handshake supports.
2. **A failed tool is not a failed protocol.** The unknown ingredient came back as a
   successful JSON-RPC `result` carrying `"isError": true` — an error *for the model to
   read*, distinguishable from a dead server (which would be a JSON-RPC `error` or a
   broken pipe).
3. **The docstring travels verbatim** as the tool's `description` — the model reads the
   Python docstring word for word, which is why requirement 5 treats it as a prompt.

## 5. Docstring as a prompt, error made recoverable (requirement 5)

`error_before_after.md` has both full transcripts. One tool on our own server,
`search_recipes`: `"Search recipes."` + `"Error 3"` became a docstring that says when to
call it, what to pass, what comes back and what to do on a miss, and an error that says
it was a name miss, names the closest dish, and gives retry strings verified to match.

Same request (`Halve the "plain dosai" recipe.`), **same failing first call** in both:

| | Before | After |
|---|---|---|
| Failed calls | 3 (blind trimming; one after it had already succeeded) | **1** |
| Laps / tokens | 7 / 8,078 | **4 / 4,827** |
| Told the user a dish was substituted | no | **yes** |

Honest reading: both runs ended with correct amounts — the old error made the model
*flail*, not fail. One of the three saved laps is the after run skipping `get_recipe`
(no method in its answer), not the error fix. n = 1 run each.

## 6. Supply-chain risk note (requirement 6)

`risk_note.md` — exactly 5 lines: who wrote it, what it can reach, what it logs, what a
stolen token could do, ship or don't. Verdict: **ship, with conditions** — read-only
tools, pinned commit, sandboxed low-privilege process with no network, and never the
sole check behind an allergen-free claim. The line worth keeping: over stdio the server
runs with my full OS privileges, so *"the code's restraint is a promise, not a sandbox."*

## Honest limitations

- **The "content team's" server is a stand-in I authored.** There is no content team;
  `ingredient_db_server/` plays that role in its own folder. The risk note is written
  as it should be for a genuine third party, and says so in its first line.
- **Nutrition values are approximate reference figures**, not lab data; six entries are
  deliberately `null`, and the server refuses to estimate them rather than inventing.
- **The before/after comparison is one run each** at temperature 0 — it demonstrates
  the mechanism, not a rate.
- **Resources are discovered but not auto-attached** by the agent; attaching a
  third-party server's text to the prompt would widen the injection surface, so it is
  left opt-in.
- **The bonus (gateway + audit line + scoped token) was not attempted** — optional
  extra credit.

## Files

| File | Contents |
|---|---|
| `w9_agent.py` | the MCP host agent — discovers tools, never names one |
| `w9_recipe_server.py` | server one, ours: 4 tools |
| `ingredient_db_server/` | server two, the content team's: 2 tools + 1 resource |
| `mcp_config.json` | the only thing that changed to add server two |
| `agent_diff.txt` / `config_diff.txt` | the zero-line proof and the config diff |
| `tool_counts.md` | 4 → 6, from tools/list |
| `wire.json` | raw exchange, hand-annotated · raw lines in `results/w9_wire_raw.jsonl` |
| `error_before_after.md` | the docstring/error rewrite and both transcripts |
| `risk_note.md` | 5 lines |
| `w9_wire_capture.py` / `w9_annotate_wire.py` | how the wire was captured and annotated |
| `results/w9_trace_*.jsonl` | every agent run, lap by lap |
