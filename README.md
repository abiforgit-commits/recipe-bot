# Pantry-to-Plate: recipe Q&A that checks allergens against the declaration, not the prose

Week 12 capstone (AI Engineering League, Set B: recipes & food). Ask a cooking question
in plain language. The answer comes only from the publisher's recipe library, with a
citation that names the recipe **and its version**. Allergens are checked by exact match
against the CMS declaration fields, quantities scale without scaling cook times, and
safe internal temperatures are always stated.

## Run it (about 15–20 minutes on a fresh machine: `pip install` alone took 13)

You need Python 3.11 or newer and a free Gemini API key from
https://aistudio.google.com/apikey.

```powershell
git clone https://github.com/abiforgit-commits/week3-rag
cd week3-rag
python -m venv .venv
.venv\Scripts\Activate.ps1          # Git Bash on Windows: source .venv/Scripts/activate
                                    # macOS/Linux:         source .venv/bin/activate
pip install -r requirements.txt
```

Create a file named `.env` in the `week3-rag` folder with one line (it is git-ignored and
never committed):

```
GEMINI_API_KEY=paste-your-key-here
```

(An `OPENAI_API_KEY=` line works too, and then the model is gpt-4o-mini. Without any key,
`ask` and `eval` stop with an instruction; every other command works without one.)

Ask a question:

```powershell
python pantry.py ask "My son is allergic to nuts - can he have the nankhatai?"
```

The first run builds the search index. If Chroma has never run on this machine, it
also downloads a ~80 MB local embedding model once. Later runs take 10–30 seconds,
mostly waiting on the free tier's 15 requests/minute limit (single calls have taken
minutes when the free tier is congested).

What you'll see:
- the tools discovered over MCP: **8 tools from 2 servers**, the 6 from `pantry_server.py`
  plus 2 from the Week 9 `ingredient_db_server`;
- each tool call as it happens;
- the answer, citing ids like `[nankhatai-07@reformulated-2025::structure::3]`, with a
  **Sources** list under it mapping each cited id to `file:line` (clickable in VS Code);
- an **Allergen check** block printed by code from the declaration fields, not by the model;
- a trace id.

**Privacy:** the request log removes stated health conditions. `pantry.py trace` shows
the question as e.g. `[health detail removed] - can he have the nankhatai?` and
pseudonymises the user id. Times in the log are UTC.

## Every command

| Command | What it does | Model calls (needs a key) |
|---|---|---|
| `python pantry.py ask "<question>"` | answer one question end to end | yes |
| `python pantry.py trace <trace_id>` | that question's spans across the agent and MCP hops: latency, tokens, cost | no |
| `python pantry.py eval --tag mine --judge judge_v4.txt` | the full eval suite (33 cases) on the integrated system, ~25 min: assertions, then the judge | yes |
| `python pantry.py trajectory --tag mine --judge judge_v4.txt` | tool-choice accuracy and outcome-vs-trajectory gap, from that eval run | no |
| `python pantry.py agreement --tag after --judge judge_v3.txt` | a judge against the blind labels (`pantry_labels_after.json`); add `--labels yours.json` to score your own labels | no |
| `python pantry_judge_holdout.py agree judge_v4.txt` | judge_v4 on the 50 held-out outputs (86.0%) | no |
| `python pantry.py tools` | the tools discovered over MCP (`tools/list`) | no |
| `python pantry.py serve [--http 8765]` | run the MCP server for another client (see below) | no |
| `python pantry.py setup` | rebuild the search index | no |
| `python pantry_hitrate.py` | the Week 4 retriever's hit-rate@3 on this corpus | no |

## Use the MCP server from your own client

`pantry_server.py` is an ordinary MCP server, so any client can use it. Over stdio, point
your client at:

```json
{"command": "<path-to>/week3-rag/.venv/Scripts/python.exe",
 "args": ["<path-to>/week3-rag/pantry_server.py"]}
```

Or run `python pantry.py serve --http 8765` and connect to `http://localhost:8765/mcp`
(e.g. `npx @modelcontextprotocol/inspector`). Tools: `search_recipes`, `get_recipe`,
`check_allergens`, `find_substitutes`, `scale_recipe`, `get_safe_temperature`. The
server needs no API key and never calls a model.

## How it fits together

```
question -> pantry.py -> PantryAgent (Week 7 loop, Week 9 MCP host; the ONLY model calls)
                           | tools/list + tools/call, trace id in _meta
                           v
            pantry_server.py (MCP) -> pantry_corpus.py -> data/cms/ (the CMS export)
            ingredient_db_server   -> ingredients.json (Week 9 content-team server)
```

See `architecture.md` for the one-page sketch with where the money goes. `data/cms/README.md`
describes the data, including the deliberate stale "nut-free" page.

## The capstone write-up

| File | |
|---|---|
| `results_w12.md` | start here: every requirement, with its number |
| `eval_report.md` | suite results per mode, allergy cases, judge agreement, what the suite does NOT cover |
| `taxonomy_w12.md` | error taxonomy re-scored on the integrated system (incl. the mode integration created) |
| `seams.md` | the seam list, unedited, with statuses |
| `weaknesses.md` | top 3 known weaknesses, dated |
| `architecture.md` | one-page sketch: boxes, arrows, model calls, money |
| `cost_10x.md` | cost per query and what breaks first at 50,000 queries/day |
| `trace_e2e.json` | one end-to-end trace, trace id intact across the agent and MCP hops |
| `demo_script.md` | the 10-minute, four-part demo |
| `fresh_eyes.md` | the fresh-eyes run: who ran it, where they stumbled, what changed |

## Earlier weeks (still runnable)

Weeks 3–11 live in the same repo. Their write-ups are `results.md` (Week 3),
`results_w4.md`, `taxonomy.md` (Week 5) and `results_w6.md` … `results_w11.md`. They use
the original six cards in `data/new_cards/` and their own index:

```powershell
python ingest.py --strategy naive
python ingest.py --strategy structure
python measure.py
```

The capstone does not depend on that index, so a fresh clone only needs the steps at
the top.
