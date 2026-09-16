"""Week 7: the same task as a FIXED WORKFLOW - no agent loop.

    python w7_workflow.py "Halve the appam recipe and make it coconut-free and nut-free"

Identical to the agent in: inputs, tools, model, and output contract.
Different in: the path is hard-coded, not chosen by the model.

    step 1  ONE model call: parse the request into {dish, factor, banned[]}
    step 2  search_recipes(dish)                      - deterministic
    step 3  for each banned allergen:                 - deterministic
              substitute_ingredient(...), then take the first option whose
              own allergen is not also banned  <- this is the cascade rule,
              encoded once instead of re-derived by a model every request
    step 4  scale_recipe(recipe_id, factor)           - deterministic
    step 5  assemble the output JSON                  - deterministic, no model

There is no loop over model decisions. The `for` in step 3 iterates a list
that step 1 already fixed; no model call happens inside it.
"""
import argparse
import json
import sys
import time

from ask import call_llm, DEFAULT_MODEL
from w7_tools import ALLERGENS, call_tool
from w7_agent import PRICE_IN, PRICE_OUT, cost_of

sys.stdout.reconfigure(encoding="utf-8")

PARSE_SYSTEM = f"""Extract the request into JSON with exactly these keys:
{{"dish": str, "factor": number, "banned": [str]}}
- dish: the dish name mentioned
- factor: the scaling multiplier (halve = 0.5, double = 2, "for half the batch" = 0.5); 1 if not mentioned
- banned: allergen classes to remove, each one of {ALLERGENS}; [] if none
Return only the JSON."""


def run_workflow(request, verbose=True):
    t0 = time.time()
    usage = {"in": 0, "out": 0}

    # ---- step 1: the single model call -------------------------------
    resp = call_llm(model=DEFAULT_MODEL, temperature=0,
                    messages=[{"role": "system", "content": PARSE_SYSTEM},
                              {"role": "user", "content": request}])
    usage["in"] += resp.usage.prompt_tokens
    usage["out"] += resp.usage.completion_tokens
    raw = resp.choices[0].message.content.strip()
    raw = raw.split("```json")[-1].split("```")[0] if "```" in raw else raw
    try:
        plan = json.loads(raw)
    except json.JSONDecodeError:
        plan = {"dish": request, "factor": 1, "banned": []}
    dish, factor = plan.get("dish", ""), float(plan.get("factor", 1) or 1)
    banned = [a for a in plan.get("banned", []) if a in ALLERGENS]
    if verbose:
        print(f"[step 1] parsed: dish={dish!r} factor={factor} banned={banned}")

    # ---- step 2: identity --------------------------------------------
    hits = call_tool("search_recipes", {"query": dish})
    if not hits:
        return {"system": "workflow", "request": request, "final": None,
                "stop_reason": "no_recipe_match", "laps": 1,
                "tokens_in": usage["in"], "tokens_out": usage["out"],
                "tokens_total": usage["in"] + usage["out"],
                "cost_usd": round(cost_of(usage), 6),
                "latency_s": round(time.time() - t0, 2)}
    recipe_id, title = hits[0]["recipe_id"], hits[0]["title"]
    if verbose:
        print(f"[step 2] recipe: {recipe_id}")

    # ---- step 3: substitutions, cascade rule encoded ------------------
    subs = {}
    for allergen in banned:
        res = call_tool("substitute_ingredient",
                        {"recipe_id": recipe_id, "allergen": allergen})
        for swap in res.get("swaps", []):
            choice = next((o["to"] for o in swap["options"]
                           if o["carries_allergen"] not in banned), None)
            if choice:
                subs[swap["from"]] = choice
        if verbose:
            print(f"[step 3] {allergen}: {res.get('swaps') and list(subs.items())[-1:] or 'nothing to swap'}")

    # ---- step 4: scale -----------------------------------------------
    scaled = call_tool("scale_recipe", {"recipe_id": recipe_id, "factor": factor})
    if verbose:
        print(f"[step 4] scaled x{factor}")

    # ---- step 5: assemble, no model ----------------------------------
    ingredients = [{"name": subs.get(row["name"], row["name"]), "amount": row["amount"]}
                   for row in scaled["ingredients"]]
    final = json.dumps({"recipe_id": recipe_id, "title": title, "scale_factor": factor,
                        "ingredients": ingredients,
                        "substitutions": [{"from": k, "to": v} for k, v in subs.items()],
                        "allergens_avoided": banned}, ensure_ascii=False)
    if verbose:
        print("[step 5] assembled")

    return {"system": "workflow", "request": request, "final": final,
            "stop_reason": "completed", "laps": 5,
            "tokens_in": usage["in"], "tokens_out": usage["out"],
            "tokens_total": usage["in"] + usage["out"],
            "cost_usd": round(cost_of(usage), 6),
            "latency_s": round(time.time() - t0, 2)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("request")
    a = ap.parse_args()
    r = run_workflow(a.request)
    print(f"\nstop_reason: {r['stop_reason']}")
    print(f"tokens={r['tokens_total']} cost=${r['cost_usd']:.6f} latency={r['latency_s']}s")
    print(f"\n{r['final']}")
