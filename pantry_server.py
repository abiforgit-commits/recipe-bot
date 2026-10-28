"""Capstone MCP server: the publisher's recipe library, with exact-match allergen checks.

    python pantry_server.py                         stdio (launched by the host, or by any MCP client)
    python pantry_server.py --http 8765             streamable HTTP, for a client on another machine

A genuine capability, usable by any MCP client, not only this repo's agent:
search the CMS (Week 4 hybrid retrieval), read a recipe version, check allergens
against the DECLARATION FIELDS, list the test kitchen's substitutions, scale
quantities, and look up safe internal temperatures.

It holds no model key and never calls a model. Every call is logged as a server
span under the trace id the client sends in the request's _meta (pantry_trace.py).
"""
import argparse

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError

import pantry_corpus as pc
from pantry_trace import server_span

mcp = MCPServer("pantry-cms", log_level="WARNING")


def _run(ctx, tool, args, fn):
    with server_span(ctx, "pantry", tool, args):
        try:
            return fn()
        except pc.LookupError_ as e:
            raise ToolError(str(e)) from None


@mcp.tool()
def search_recipes(query: str, ctx: Context) -> dict:
    """Search the recipe library by meaning and keywords (hybrid retrieval) and return
    the 5 best page chunks. Each hit has chunk_id (cite it exactly, e.g.
    [nankhatai-07@reformulated-2025::structure::1]), recipe_id, version, status
    ("current" or "superseded") and the chunk text.

    Use it to find recipes and to read what a page says. The page text can be out
    of date: never use it to decide allergens, use check_allergens. Pass a short
    search phrase, not the user's whole message."""
    return _run(ctx, "search_recipes", {"query": query},
                lambda: {"query": query, "hits": pc.search(query)})


@mcp.tool()
def get_recipe(recipe_id: str, ctx: Context, version: str = "current") -> dict:
    """Return one recipe version as structured data: yield, times, oven temperature,
    the ingredient table, method and serving suggestion. version defaults to the
    current one; pass "original" only when the user asks about the old recipe.
    Allergens are not included: call check_allergens for those."""
    return _run(ctx, "get_recipe", {"recipe_id": recipe_id, "version": version},
                lambda: pc.recipe(recipe_id, version))


@mcp.tool()
def check_allergens(recipe_id: str, avoid: list[str], ctx: Context, version: str = "current",
                    swap_from: list[str] | None = None, swap_to: list[str] | None = None) -> dict:
    """Check a recipe against the allergens a user must avoid, by EXACT MATCH on the
    CMS declaration fields (allergens, may_contain). This is the only reliable
    allergen source: the page text can be out of date.

    avoid: allergen classes or names, e.g. ["nuts"], ["peanut", "dairy"].
    Returns verdict UNSAFE (declared), MAY_CONTAIN (traces warning, never "safe"),
    or SAFE_BY_DECLARATION, plus which ingredient declares it and any serving
    suggestions to leave out. version defaults to the current recipe.

    To check a recipe AS SUBSTITUTED, pass swap_from (ingredient names exactly as
    in the recipe) and swap_to (substitutes exactly as find_substitutes listed
    them), in the same order. An allergen the CMS does not declare (e.g. egg) is an
    error, never a "safe"."""
    swaps = [{"from": f, "to": t} for f, t in zip(swap_from or [], swap_to or [])]
    if len(swap_from or []) != len(swap_to or []):
        raise ToolError("swap_from and swap_to must have the same length, one pair per swap.")
    return _run(ctx, "check_allergens", {"recipe_id": recipe_id, "avoid": avoid, "version": version,
                                         "swaps": swaps},
                lambda: pc.check_allergens(recipe_id, avoid, version, swaps or None))


@mcp.tool()
def find_substitutes(recipe_id: str, allergen: str, ctx: Context, version: str = "current") -> dict:
    """List the test kitchen's substitutes for the ingredients of one recipe that
    carry an allergen. Every option states the allergen it carries itself (a swap
    can bring in a new allergen). Pick options that carry nothing the user avoids,
    then check the result with check_allergens(swap_from=..., swap_to=...)."""
    return _run(ctx, "find_substitutes", {"recipe_id": recipe_id, "allergen": allergen,
                                          "version": version},
                lambda: pc.substitutes(recipe_id, allergen, version))


@mcp.tool()
def scale_recipe(recipe_id: str, factor: float, ctx: Context, version: str = "current") -> dict:
    """Multiply the ingredient quantities of one recipe by factor (0.5 halves, 4 is
    four times) and scale the yield. Times and temperatures are returned UNCHANGED
    on purpose: a bigger batch is cooked in batches or a wider pan at the same time
    and temperature. Arithmetic only: no allergens, no searching."""
    return _run(ctx, "scale_recipe", {"recipe_id": recipe_id, "factor": factor, "version": version},
                lambda: pc.scale(recipe_id, factor, version))


@mcp.tool()
def get_safe_temperature(food: str, ctx: Context) -> dict:
    """Look up the test kitchen's food-safety chart: the safe internal temperature for
    poultry, minced meat, whole cuts, fish, egg dishes and leftovers, or the
    cooked-rice storage rule. Pass the food, e.g. "chicken". Colour and texture
    are not proof of safety: give the user the number. Foods not in the chart
    are an error: say you cannot confirm, never guess."""
    return _run(ctx, "get_safe_temperature", {"food": food}, lambda: pc.safe_temperature(food))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--http", type=int, help="serve streamable HTTP on this port instead of stdio")
    a = ap.parse_args()
    pc.search("warm-up")  # open the index and load the embedding model now (2-7 s), not in the first question
    if a.http:
        mcp.run(transport="streamable-http", port=a.http)
    else:
        mcp.run()
