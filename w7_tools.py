"""Week 7: the three tools, shared by the agent and the fixed workflow.

Tool descriptions are written so no two overlap. Each names exactly one job:
  search_recipes        -> WHICH recipe (identity only, no quantities)
  scale_recipe          -> HOW MUCH (arithmetic only, no allergen knowledge)
  substitute_ingredient -> WHAT TO SWAP (allergen swaps only, no scaling)

The substitution table is deliberately CASCADING: several first-choice
substitutes are themselves allergens, so a request banning two allergen
classes needs a second swap. That is the input class the race is designed
to separate agent from workflow on.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
CARDS = ROOT / "data" / "new_cards"

ALLERGENS = ["dairy", "sesame", "nuts", "coconut", "soy", "gluten", "mustard"]

# ingredient -> (allergen class it carries)
INGREDIENT_ALLERGEN = {
    "whole milk (full-fat)": "dairy",
    "live curd from the previous batch": "dairy",
    "gingelly (sesame) oil": "sesame",
    "fresh thick coconut milk": "coconut",
    "mustard seeds": "mustard",
    "asafoetida (hing)": "gluten",
}

# ingredient -> ordered substitute preferences; each substitute carries its
# own allergen class (or None). First choice may itself be banned -> cascade.
SUBSTITUTES = {
    "whole milk (full-fat)": [("cashew milk", "nuts"), ("oat milk", "gluten"), ("soy milk", "soy")],
    "live curd from the previous batch": [("cashew curd starter", "nuts"), ("coconut yoghurt starter", "coconut")],
    "gingelly (sesame) oil": [("groundnut oil", "nuts"), ("sunflower oil", None)],
    "fresh thick coconut milk": [("almond milk", "nuts"), ("oat milk", "gluten"), ("sunflower-seed milk", None)],
    "mustard seeds": [("nigella seeds", None)],
    "asafoetida (hing)": [("gluten-free asafoetida", None)],
}


def _load_cards():
    cards = {}
    for p in sorted(CARDS.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        _, fm, body = text.split("---", 2)
        meta = dict(line.split(":", 1) for line in fm.strip().splitlines())
        meta = {k.strip(): v.strip() for k, v in meta.items()}
        rows = []
        for line in body.splitlines():
            m = re.match(r"\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", line)
            if m and "---" not in line and "Ingredient" not in m.group(1):
                rows.append({"name": m.group(1).strip(), "amount": m.group(2).strip()})
        method = body.split("## Method", 1)[1].split("## Allergen")[0].strip() if "## Method" in body else ""
        cards[meta["recipe_id"]] = {"recipe_id": meta["recipe_id"], "title": meta["title"],
                                    "cuisine": meta["cuisine"], "dietary_tags": meta["dietary_tags"],
                                    "ingredients": rows, "method": method}
    return cards


CARDS_BY_ID = _load_cards()


# ---------------------------------------------------------------- tool 1
def search_recipes(query: str):
    """Identity lookup only."""
    q = query.lower()
    hits = []
    for r in CARDS_BY_ID.values():
        score = sum(w in r["title"].lower() or w in r["recipe_id"] for w in q.split() if len(w) > 3)
        if score:
            hits.append((score, r))
    if not hits:
        for r in CARDS_BY_ID.values():
            if any(w[:4] in r["title"].lower() for w in q.split() if len(w) > 3):
                hits.append((1, r))
    hits.sort(key=lambda t: -t[0])
    return [{"recipe_id": r["recipe_id"], "title": r["title"], "cuisine": r["cuisine"],
             "dietary_tags": r["dietary_tags"]} for _, r in hits[:3]]


# ---------------------------------------------------------------- tool 2
def scale_recipe(recipe_id: str, factor: float):
    """Arithmetic only."""
    r = CARDS_BY_ID.get(recipe_id)
    if not r:
        return {"error": f"unknown recipe_id {recipe_id}"}
    out = []
    for row in r["ingredients"]:
        m = re.match(r"~?(\d+(?:\.\d+)?)\s*(g|kg)?", row["amount"])
        if m:
            val = float(m.group(1)) * float(factor)
            unit = m.group(2) or ""
            amt = f"{val:g}{unit}"
        else:
            amt = f"{row['amount']} x{factor:g}"
        out.append({"name": row["name"], "amount": amt})
    return {"recipe_id": recipe_id, "scale_factor": factor, "ingredients": out}


# ---------------------------------------------------------------- tool 3
def substitute_ingredient(recipe_id: str, allergen: str):
    """Allergen swaps only. Returns the swap AND the allergen the substitute
    itself carries, so a caller can detect a cascade."""
    if allergen not in ALLERGENS:
        return {"error": f"allergen must be one of {ALLERGENS}"}
    r = CARDS_BY_ID.get(recipe_id)
    if not r:
        return {"error": f"unknown recipe_id {recipe_id}"}
    swaps = []
    for row in r["ingredients"]:
        key = row["name"].lower()
        if INGREDIENT_ALLERGEN.get(key) == allergen:
            options = SUBSTITUTES.get(key, [])
            swaps.append({
                "from": row["name"],
                "options": [{"to": name, "carries_allergen": carries} for name, carries in options],
            })
    return {"recipe_id": recipe_id, "allergen_removed": allergen, "swaps": swaps,
            "note": "each option lists the allergen it carries; pick one the request permits"}


TOOL_FUNCS = {"search_recipes": search_recipes, "scale_recipe": scale_recipe,
              "substitute_ingredient": substitute_ingredient}

TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "search_recipes",
        "description": "Find which recipe card matches a dish name. Returns recipe identity only: recipe_id, title, cuisine, dietary tags. Does not return quantities, methods, or allergen advice.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "dish name to look up, e.g. 'appam' or 'mango pickle'"}},
            "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "scale_recipe",
        "description": "Multiply every ingredient quantity of one known recipe_id by a numeric factor. Pure arithmetic on amounts. Does not choose recipes and knows nothing about allergens or substitutes.",
        "parameters": {"type": "object", "properties": {
            "recipe_id": {"type": "string", "description": "exact recipe_id from search_recipes"},
            "factor": {"type": "number", "description": "multiplier, e.g. 0.5 to halve, 2 to double"}},
            "required": ["recipe_id", "factor"]}}},
    {"type": "function", "function": {
        "name": "substitute_ingredient",
        "description": "List replacement options for the ingredients of one recipe_id that carry a given allergen class. Each option states the allergen it itself carries, so a follow-up swap can be made if the first choice is also banned. Does not scale quantities and does not search for recipes.",
        "parameters": {"type": "object", "properties": {
            "recipe_id": {"type": "string", "description": "exact recipe_id from search_recipes"},
            "allergen": {"type": "string", "enum": ALLERGENS,
                         "description": "the allergen class to remove from the recipe"}},
            "required": ["recipe_id", "allergen"]}}},
]

OUTPUT_CONTRACT = """Return ONLY a JSON object with exactly these keys:
{"recipe_id": str, "title": str, "scale_factor": number,
 "ingredients": [{"name": str, "amount": str}],
 "substitutions": [{"from": str, "to": str}],
 "allergens_avoided": [str]}
Ingredients must already have the substitutions applied and the scaling applied.
No prose before or after the JSON."""


def call_tool(name, args):
    try:
        return TOOL_FUNCS[name](**args)
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    print(json.dumps(search_recipes("appam"), indent=2))
    print(json.dumps(substitute_ingredient("appam-03", "coconut"), indent=2))
    print(json.dumps(scale_recipe("idli-batter-01", 0.5)["ingredients"][:3], indent=2))
