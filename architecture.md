# Architecture: one page

```
                        python pantry.py ask "<question>"           (ONE entry point)
                                        |
                                        v
 +---------------------------- HOST: pantry_agent.py ----------------------------+
 |  trace_id = new per question                                                  |
 |                                                                               |
 |   Week 7 loop:  model call  ->  tool calls  ->  model call  ->  ... -> answer  |
 |                 ^^^^^^^^^^                                                    |
 |                 THE ONLY MODEL CALLS IN THE SYSTEM ($ = 100% of cost)          |
 |                 gemini-flash-lite, ~2.9 calls/question, ~8.2k tokens,          |
 |                 98% of them re-sent prompt                                    |
 |                 budgets: 10 laps, 60k tokens, $0.02, 300 s                    |
 |                                                                               |
 |   Week 9: tools discovered at startup via tools/list from pantry_mcp.json     |
 |   Week 11: every span logged under trace_id -> logs/pantry_requests.jsonl     |
 |            (health statements redacted, user id pseudonymised)                |
 |   CODE renders: Sources list (recipe@version, file:line) + Allergen-check     |
 |                 block from the check_allergens results (never model text)     |
 +-----------------------+---------------------------------------+---------------+
                         | MCP tools/call  (_meta: trace_id)      | MCP tools/call
                         v                                        v
 +------------- pantry_server.py (MCP, ours) -------------+   +-- ingredient_db_server --+
 | $0 - no model, no key. Server span per call,           |   | Week 9, content team.    |
 | same trace_id -> logs/pantry_mcp_spans.jsonl           |   | Per-INGREDIENT flags and |
 |                                                        |   | nutrition. $0. Does not  |
 |  search_recipes  -> Week 4 hybrid: dense (local        |   | read _meta (seam S-list) |
 |                     MiniLM, Chroma) + BM25, RRF k=60   |   +--------------------------+
 |                     ~300 ms; returns version + status  |
 |  check_allergens -> EXACT set match on declaration     |
 |                     fields (+ as-substituted), ~5 ms   |
 |  get_recipe / scale_recipe (times NEVER scaled)        |
 |  find_substitutes / get_safe_temperature               |
 +---------------------------+----------------------------+
                             | pantry_corpus.py (pure functions; the eval uses them too)
                             v
 +------------------------ data/cms/ (the CMS export) ----------------------------+
 |  <recipe>.<version>.md : front matter = declaration FIELDS (allergens,         |
 |  may_contain, allergen_sources); body = page text (chunked, indexed; can be    |
 |  stale). 9 recipes / 11 versions; superseded versions KEPT in the index.       |
 |  food-safety-chart, substitutions.csv                                          |
 +--------------------------------------------------------------------------------+

 Eval (python pantry.py eval): same agent, 33 cases -> assertions P1-P11 against the
 SAME pantry_corpus functions (allergens asserted, never judged) -> judge_v2 (Week 6)
 for USEFUL_AND_GROUNDED -> trajectory scored from the same traces (Week 8).
```

**Where the money goes:** only the box marked "THE ONLY MODEL CALLS". A question costs
about $0.0009, all of it model tokens. Retrieval, the MCP servers and the allergen
checks are local and cost $0. 98% of the tokens are the conversation being re-sent
on every lap of the loop, so the lap count is the cost.

**Where safety lives:** allergens are decided by an exact match on fields
(`check_allergens`) and shown by code (the Allergen-check block). The model writes the
prose around them, and the eval asserts that the prose doesn't contradict them (P4–P6).
