"""Week 9 server one: recipe search over the six recipe cards, exposed over MCP.

    python w9_recipe_server.py        (stdio transport; normally launched by the host)

This server exposes capabilities only. It holds no model key and makes no
model call - the host that connects to it runs the model.
"""
import difflib
import re
from typing import Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from w7_tools import CARDS_BY_ID, scale_recipe as _scale, substitute_ingredient as _substitute

mcp = MCPServer("recipe-search", log_level="WARNING")

STOPWORDS = {"the", "recipe", "recipes", "for", "and", "with", "make", "batch", "please"}
Allergen = Literal["dairy", "sesame", "nuts", "coconut", "soy", "gluten", "mustard"]


def _words(text):
    return [w for w in re.findall(r"[a-z]+", text.lower()) if len(w) >= 3 and w not in STOPWORDS]


def _match(dish):
    """Strict: every meaningful word of the query must appear in the title or id."""
    words = _words(dish)
    if not words:
        return []
    hits = []
    for r in CARDS_BY_ID.values():
        haystack = f"{r['title']} {r['recipe_id']}".lower()
        if all(w in haystack for w in words):
            hits.append({"recipe_id": r["recipe_id"], "title": r["title"],
                         "cuisine": r["cuisine"], "dietary_tags": r["dietary_tags"]})
    return hits[:3]


def _short_name(title):
    return re.split(r" \(| — ", title)[0]


def _no_match(dish):
    """A recoverable miss: say it was a name miss, name the closest dish, and
    give retry strings that are guaranteed to match."""
    names = [_short_name(r["title"]) for r in CARDS_BY_ID.values()]
    query = _words(dish) or [dish.lower()]

    def closeness(name):
        return max(difflib.SequenceMatcher(None, q, w).ratio()
                   for q in query for w in _words(name) or [name.lower()])

    closest = max(names, key=closeness)
    return (f"No recipe matched {dish!r} - a name miss; the server is working. "
            f"Closest known dish: {closest!r}. All six dishes: "
            f"{', '.join(repr(n) for n in names)}. Retry search_recipes with one of "
            f"these exact names, and tell the user which dish you used.")


@mcp.tool()
def search_recipes(dish: str) -> list:
    """Find which recipe card matches a dish the user named. Call this FIRST for
    any request about a recipe: every other recipe tool needs the recipe_id it
    returns.

    Pass the dish name only - e.g. "appam", "thayir curd", "mango pickle" - not
    the user's whole sentence. Returns up to 3 matches, each with recipe_id,
    title, cuisine and dietary tags: identity only, no quantities, no method.

    If nothing matches, the error names the closest known dish and lists all
    six; retry with one of those exact names instead of guessing, and tell the
    user which dish you used. Never invent a recipe_id."""
    hits = _match(dish)
    if not hits:
        raise ToolError(_no_match(dish))
    return hits


@mcp.tool()
def get_recipe(recipe_id: str) -> dict:
    """Return the full card for one recipe_id: title, the ingredient table exactly
    as written (name and amount), and the method. Use this when you need to know
    what is IN a recipe or how to make it. Does not scale amounts and does not
    swap allergens."""
    r = CARDS_BY_ID.get(recipe_id)
    if not r:
        raise ToolError(f"unknown recipe_id {recipe_id!r}; valid ids: {', '.join(CARDS_BY_ID)}")
    return {"recipe_id": r["recipe_id"], "title": r["title"],
            "ingredients": r["ingredients"], "method": r["method"]}


@mcp.tool()
def scale_recipe(recipe_id: str, factor: float) -> dict:
    """Multiply every ingredient quantity of one known recipe_id by a numeric
    factor. Pure arithmetic on amounts. Does not choose recipes and knows nothing
    about allergens or substitutes. Call this ONLY when the amounts actually
    change: at factor 1 nothing changes, so skip the tool entirely."""
    return _scale(recipe_id, factor)


@mcp.tool()
def substitute_ingredient(recipe_id: str, allergen: Allergen) -> dict:
    """List replacement options for the ingredients of one recipe_id that carry
    the given allergen class. Each option states the allergen it itself carries,
    so a follow-up swap can be made if the first choice is also banned. Does not
    scale quantities and does not search for recipes."""
    return _substitute(recipe_id, allergen)


if __name__ == "__main__":
    mcp.run()
