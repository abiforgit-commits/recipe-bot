# Tool count — before -> after, taken from tools/list

**4 before -> 6 after**

Generated from the raw `tools/list` responses saved by
`python w9_agent.py --list-tools` (`results/w9_tools_before.json` at commit A,
`results/w9_tools_after.json` at commit B) — not from notes.

## Before — 4 tools (config: server one only)
- `recipes__search_recipes`
- `recipes__get_recipe`
- `recipes__scale_recipe`
- `recipes__substitute_ingredient`

## After — 6 tools (config: server one + ingredient_db)
- `recipes__search_recipes`
- `recipes__get_recipe`
- `recipes__scale_recipe`
- `recipes__substitute_ingredient`
- `ingredient_db__lookup_allergens`   ← new, from ingredient_db
- `ingredient_db__lookup_nutrition`   ← new, from ingredient_db

Added by config alone: 2 — `ingredient_db__lookup_allergens`, `ingredient_db__lookup_nutrition`.

## Not a tool: the allergen matrix
The ingredient server also exposes 1 resource via `resources/list`: `allergens://matrix`.
It is deliberately a **resource** (context a host attaches) and not a **tool**
(something the model invokes): the standing allergen matrix is reference data, and
exposing it as a tool would make the model re-fetch it on every turn. It is
correctly absent from the tool count above. (`w9_agent.py` discovers and lists
resources but does not auto-attach them: attaching a third-party server's text
to the prompt would widen the prompt-injection surface, so it stays opt-in.)
