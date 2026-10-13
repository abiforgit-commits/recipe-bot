# Fresh-eyes note

## Rehearsal (done): Wed 14 Oct 2026, 00:59–01:16 IST

**Who:** a freshly started Claude agent with no access to this session or the working
copy. It got only the public repo URL and the instruction to follow `README.md`.
**This was a rehearsal, not the requirement.** The brief wants a person from another
squad (see Thursday, below). It cloned into an empty folder, made its own venv, and was
not allowed to copy `.env`: it passed the key as an environment variable for one command
and never printed it.

**Result:** zero to a working answer from the README alone: **yes**. Clone → first answer
took **15.5 minutes**, 13 of them `pip install`. The answer was correct on release r2
(current nankhatai UNSAFE from the declaration, superseded version "must not be used"),
with trace `19c63cac5ac545c1` showing 3 model calls and 2 MCP calls, each with a matching
server span.

### Where it stumbled, and what changed

| # | Stumble | What changed |
|---|---|---|
| 1 | README had no Git Bash venv line; `source .venv/bin/activate` fails on Windows | README: `source .venv/Scripts/activate` for Git Bash |
| 2 | "About 5 minutes" — pip alone took 13 on a cold machine | README: "about 15–20 minutes on a fresh machine" |
| 3 | `python pantry.py tools` exits "No model key" although it makes no model call | **code fix:** `ask.py` no longer builds the API client when there is no key, so only a real model call fails. While checking this, `trajectory`, `agreement` and `pantry_judge_holdout.py agree` turned out to have the same crash. All fixed; the README table now says which commands need a key |
| 4 | Three files in the README's write-up table were missing in the clone | timing: it cloned at 00:59, and `results_w12.md` / `eval_report.md` were pushed later. Now pushed. `fresh_eyes.md` is this file |
| 5 | "Numbered source list", but the answer cites raw ids, not `[1]` | README: the Sources list maps each cited id to `file:line` |
| 6 | `trace` shows `Q: [health detail removed] …` and UTC times, unexplained | README: a Privacy paragraph |
| 7 | MCP section lists 6 tools; `tools` says 8 | README: "8 tools from 2 servers (6 + 2 from the Week 9 ingredient-db server)" |
| 8 | `OPENAI_API_KEY` works but isn't documented; earlier weeks' file names wrong | README: both fixed |
| 9 | First run took 35 s, not "about a minute", because the embedding model was already cached on this machine | README now says the download only happens if Chroma has never run on the machine. A truly clean machine is still untested |

Not caused by the README: the shell had this project's venv already active, so the first
`python -m venv` used the wrong interpreter. A newcomer's shell wouldn't.

### Found by us while reading its run

The log's PII redaction is generous. It also removed "with a nut allergy" from the
**system's own answer** ("should not be used for someone [health detail removed]") in the
logged copy. The user sees the full answer. Accepted as the safe-side trade-off; noted
here.

---

## Thursday (to do): a person from another squad

The brief's requirement. Please fill in:

| | |
|---|---|
| Name, squad | |
| Date and time | |
| Their machine (OS, Python) | |
| Got from zero to an answer from the README alone? | |
| Time to first answer | |
| **Called our MCP server from their own client** (e.g. Claude Desktop/Code, MCP Inspector, their own host). Which client, which tool, what came back | |
| Where they stumbled (in order) | |
| What we changed because of it | |

To call the server from their client: README → "Use the MCP server from your own client"
(stdio config, or `python pantry.py serve --http 8765` → `http://localhost:8765/mcp`).
Machine evidence that a client that isn't ours already works:
`results/foreign_client_mcp_inspector.txt` (the official MCP Inspector CLI).
