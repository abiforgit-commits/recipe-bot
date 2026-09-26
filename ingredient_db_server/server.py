"""Ingredient database MCP server (content team).

    python ingredient_db_server/server.py      (stdio transport; launched by the host)

Read-only view of ingredients.json: per-ingredient allergen flags and per-100g
nutrition. It opens one file at startup and never writes, never touches the
network, and never calls a model - it exposes capabilities; the host runs the
model.
"""
import difflib
import json
import re
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

DB = json.loads((Path(__file__).parent / "ingredients.json").read_text(encoding="utf-8"))
CLASSES = DB["meta"]["allergen_classes"]

mcp = MCPServer("ingredient-db", log_level="WARNING")


def _norm(text):
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


INDEX = {}
for entry in DB["ingredients"]:
    for key in [entry["name"], *entry["aliases"]]:
        INDEX.setdefault(_norm(key), entry)


def _find(ingredient):
    """Exact name/alias match, or a recoverable error that says what to retry."""
    entry = INDEX.get(_norm(ingredient))
    if entry:
        return entry
    close = difflib.get_close_matches(_norm(ingredient), INDEX, n=4, cutoff=0.5)
    names = list(dict.fromkeys(INDEX[k]["name"] for k in close))
    if names:
        raise ToolError(f"no ingredient matched {ingredient!r}: closest entries are "
                        f"{', '.join(repr(n) for n in names)}. Retry with one of those names.")
    raise ToolError(f"no ingredient matched {ingredient!r} and nothing is close. The database "
                    f"holds {len(DB['ingredients'])} ingredients; check the spelling rather "
                    f"than assuming the ingredient is allergen-free.")


@mcp.tool()
def lookup_allergens(ingredient: str) -> dict:
    """Look up the allergen flags for ONE ingredient by name, e.g. "urad dal" or
    "Gingelly (sesame) oil". Returns every allergen class (dairy, sesame, nuts,
    coconut, soy, gluten, mustard) as true/false, plus the list it contains.
    Call once per ingredient. If the name is not found, the error lists the
    closest entries - retry with one of them; never assume an unknown
    ingredient is allergen-free. Does not return nutrition."""
    entry = _find(ingredient)
    contains = [c for c in CLASSES if entry["allergens"][c]]
    out = {"ingredient": entry["name"], "allergens": entry["allergens"], "contains": contains}
    if entry["name"] in DB["meta"]["notes"]:
        out["note"] = DB["meta"]["notes"][entry["name"]]
    return out


@mcp.tool()
def lookup_nutrition(ingredient: str) -> dict:
    """Look up approximate nutrition per 100 g for ONE ingredient by name:
    kcal, protein_g, fat_g, carbs_g. Values are reference approximations, not
    lab results. If the ingredient is known but has no nutrition recorded, the
    error says so - do not estimate a figure. Does not return allergens."""
    entry = _find(ingredient)
    if entry["nutrition_per_100g"] is None:
        raise ToolError(f"{entry['name']!r} is in the database but has no nutrition recorded. "
                        f"Report it as unknown; do not estimate.")
    return {"ingredient": entry["name"], "per_100g": entry["nutrition_per_100g"],
            "basis": DB["meta"]["nutrition_basis"]}


@mcp.resource("allergens://matrix")
def allergen_matrix() -> str:
    """The standing allergen matrix: every ingredient against every allergen
    class. Context for the host to attach, not a tool for the model to fetch
    on every turn."""
    return json.dumps({e["name"]: [c for c in CLASSES if e["allergens"][c]]
                       for e in DB["ingredients"]}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
