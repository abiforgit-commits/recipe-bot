"""Capstone: the CMS export, its search index, and the exact-match lookups.

Everything the MCP server exposes is a plain function here, so the eval can check
an answer against the same source of truth without a model or a server:

    load              data/cms/<recipe_id>.<version>.md  -> RECORDS[(recipe_id, version)]
    chunk             Week 3 structure-aware chunker; ids  <recipe_id>@<version>::structure::<n>
    search            Week 4 hybrid retrieval (dense + BM25, RRF k=60), same algorithm
    check_allergens   exact set match on the declaration FIELDS, never the page text
    scale             quantities only; times and temperatures come back unchanged
    substitutes       the test kitchen's table; every swap states what it carries
    safe_temperature  the food-safety chart, by category

    python pantry_corpus.py --build      (re)build the Chroma collection pantry_cms
"""
import argparse
import csv
import os
import re
import sys
from pathlib import Path

from rank_bm25 import BM25Okapi

from chunkers import chunk_structure_aware

ROOT = Path(__file__).parent
CMS = ROOT / "data" / "cms"
DB_DIR = ROOT / "chroma_db"
COLLECTION = "pantry_cms"
K = 5
RRF_K = 60

# Server release flag, set per server in pantry_mcp.json ("env": {"PANTRY_RELEASE": ...}).
#   r1  baseline: check_allergens returns a verdict for any version, superseded included
#   r2  superseded guard: a superseded version never gets a safety verdict (fix for the
#       failure where the agent offered the pre-2025 nankhatai as "safe" to a nut allergy)
# Flipping the flag back is the rollback: no code change, no deploy.
RELEASE = os.getenv("PANTRY_RELEASE", "r1")

ALLERGEN_CLASSES = ["dairy", "sesame", "nuts", "coconut", "soy", "gluten", "mustard"]
SYNONYMS = {
    "nut": "nuts", "nuts": "nuts", "tree nut": "nuts", "tree nuts": "nuts", "tree-nuts": "nuts",
    "peanut": "nuts", "peanuts": "nuts", "groundnut": "nuts", "groundnuts": "nuts",
    "cashew": "nuts", "cashews": "nuts", "almond": "nuts", "almonds": "nuts",
    "dairy": "dairy", "milk": "dairy", "lactose": "dairy", "cow's milk": "dairy",
    "gluten": "gluten", "wheat": "gluten", "coeliac": "gluten", "celiac": "gluten",
    "sesame": "sesame", "gingelly": "sesame", "coconut": "coconut",
    "soy": "soy", "soya": "soy", "mustard": "mustard",
}
LIST_FIELDS = {"allergens", "may_contain"}
MAP_FIELDS = {"allergen_sources", "serving_suggestion_allergens"}


class LookupError_(ValueError):
    """A recoverable miss: the message says what to retry and never implies 'safe'."""


# ----------------------------------------------------------------- load
def _parse_value(key, value):
    value = value.strip()
    if key in LIST_FIELDS:
        return [] if value.lower() == "none" else [v.strip() for v in value.split(",")]
    if key in MAP_FIELDS:
        if value.lower() == "none":
            return {}
        out = {}
        for part in value.split(";"):
            cls, _, names = part.partition("=")
            out[cls.strip()] = [n.strip() for n in names.split("|") if n.strip()]
        return out
    return value


def _parse_table(body):
    rows = []
    for line in body.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if (len(cells) >= 2 and line.strip().startswith("|") and not set(cells[0]) <= {"-"}
                and cells[0] not in ("Ingredient", "Food")):
            rows.append({"name": cells[0], "amount": cells[1]})
    return rows


def _load():
    records = {}
    for path in sorted(CMS.glob("*.*.md")):
        text = path.read_text(encoding="utf-8")
        _, front, body = text.split("---", 2)
        meta = {}
        for line in front.strip().splitlines():
            key, _, value = line.partition(":")
            meta[key.strip()] = _parse_value(key.strip(), value)
        meta.setdefault("doc_type", "recipe")
        section = lambda name: (body.split(f"## {name}", 1)[1].split("\n## ")[0].strip()
                                if f"## {name}" in body else "")
        records[(meta["recipe_id"], meta["version"])] = {
            **meta, "body": body.strip(), "file": path.relative_to(ROOT).as_posix(),
            "ingredients": _parse_table(section("Ingredients")) if meta["doc_type"] == "recipe" else [],
            "method": section("Method"),
            "serve_with": next((l.split(":", 1)[1].strip() for l in body.splitlines()
                                if l.startswith("Serve with:")), ""),
        }
    return records


RECORDS = _load()
VERSIONS = {}
for (rid, ver), rec in RECORDS.items():
    VERSIONS.setdefault(rid, []).append(ver)


# ---------------------------------------------------------------- chunk
def _chunks():
    """Same chunker as Week 3. The version is in the id AND in every chunk's title
    line, so neither the model nor a citation can lose track of which page it was."""
    chunks, where = {}, {}
    for (rid, ver), rec in RECORDS.items():
        card = {"meta": {"title": f"{rec['title']} — version: {ver}"}, "body": rec["body"]}
        file_lines = (ROOT / rec["file"]).read_text(encoding="utf-8").splitlines()
        headings = [i + 1 for i, l in enumerate(file_lines) if l.startswith("#")]
        for i, text in enumerate(chunk_structure_aware(card)):
            cid = f"{rid}@{ver}::structure::{i}"
            chunks[cid] = text
            where[cid] = f"{rec['file']}:{headings[i] if i < len(headings) else 1}"
    return chunks, where


CHUNKS, CHUNK_LOCATION = _chunks()
SUPERSEDED_CHUNKS = {cid for cid in CHUNKS
                     if RECORDS[tuple(cid.split("::")[0].split("@"))]["status"] == "superseded"}


def chunk_meta(cid):
    rid, ver = cid.split("::")[0].split("@")
    rec = RECORDS[(rid, ver)]
    return {"recipe_id": rid, "version": ver, "status": rec["status"], "title": rec["title"],
            "source": CHUNK_LOCATION[cid]}


# --------------------------------------------------------------- search
def _tokenize(text):
    """Week 4's tokenizer: punctuation stripped, '%' and '.' kept inside tokens."""
    return re.findall(r"[a-z0-9%.]+", text.lower())


_IDS = sorted(CHUNKS)
_BM25 = BM25Okapi([_tokenize(CHUNKS[c]) for c in _IDS])
_COL = [None]


def _collection():
    if _COL[0] is None:
        import chromadb
        client = chromadb.PersistentClient(path=str(DB_DIR))
        try:
            col = client.get_collection(COLLECTION)
            if sorted(col.get()["ids"]) != _IDS:  # the CMS changed since the last build
                col = build_index(client)
        except Exception:
            col = build_index(client)
        _COL[0] = col
    return _COL[0]


def build_index(client=None):
    import chromadb
    client = client or chromadb.PersistentClient(path=str(DB_DIR))
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    col = client.create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})
    col.add(ids=_IDS, documents=[CHUNKS[c] for c in _IDS],
            metadatas=[{k: v for k, v in chunk_meta(c).items()} for c in _IDS])
    return col


def search(query, k=K):
    """Week 4 hybrid: dense + BM25 candidate lists over every chunk, fused by RRF.
    Both versions of a two-version recipe stay in the index (the CMS has both)."""
    res = _collection().query(query_texts=[query], n_results=len(_IDS))
    fused = {}
    for rank, cid in enumerate(res["ids"][0], 1):
        fused[cid] = fused.get(cid, 0.0) + 1.0 / (RRF_K + rank)
    scores = _BM25.get_scores(_tokenize(query))
    for rank, i in enumerate(sorted(range(len(_IDS)), key=lambda i: -scores[i]), 1):
        fused[_IDS[i]] = fused.get(_IDS[i], 0.0) + 1.0 / (RRF_K + rank)
    top = sorted(fused, key=fused.get, reverse=True)[:k]
    return [{"chunk_id": c, **chunk_meta(c), "score": round(fused[c], 4), "text": CHUNKS[c]}
            for c in top]


# -------------------------------------------------------------- records
def resolve(recipe_id, version=None):
    if recipe_id not in VERSIONS:
        raise LookupError_(f"unknown recipe_id {recipe_id!r}. Known recipe_ids: "
                           f"{', '.join(sorted(VERSIONS))}. Use search_recipes to find one.")
    if version in (None, "", "current"):
        version = next(v for v in VERSIONS[recipe_id] if RECORDS[(recipe_id, v)]["status"] == "current")
    if version not in VERSIONS[recipe_id]:
        raise LookupError_(f"{recipe_id} has no version {version!r}; versions: "
                           f"{', '.join(VERSIONS[recipe_id])} (omit version for the current one).")
    return RECORDS[(recipe_id, version)]


def _other_versions(rec):
    return [{"version": v, "status": RECORDS[(rec["recipe_id"], v)]["status"]}
            for v in VERSIONS[rec["recipe_id"]] if v != rec["version"]]


def recipe(recipe_id, version=None):
    """The page as structured data. Allergen fields are deliberately NOT here:
    check_allergens is the only allergen path, so it is the one that gets tested."""
    rec = resolve(recipe_id, version)
    return {"recipe_id": rec["recipe_id"], "version": rec["version"], "status": rec["status"],
            "title": rec["title"], "yield": rec.get("yield"), "prep_time_min": rec.get("prep_time_min"),
            "passive_time": rec.get("passive_time"), "cook_time_min": rec.get("cook_time_min"),
            "oven_temp_c": rec.get("oven_temp_c"), "ingredients": rec["ingredients"],
            "method": rec["method"], "serve_with": rec["serve_with"] or None,
            "revision_note": rec.get("revision_note"), "other_versions": _other_versions(rec),
            "cite_as": f"{rec['recipe_id']}@{rec['version']}", "source": rec["file"]}


# ------------------------------------------------------------ allergens
def normalise_allergen(name):
    key = name.strip().lower()
    if key in SYNONYMS:
        return SYNONYMS[key]
    raise LookupError_(
        f"{name!r} is not an allergen class this CMS declares. Declared classes: "
        f"{', '.join(ALLERGEN_CLASSES)}. Its absence from a declaration is NOT evidence "
        f"a recipe is free of it: tell the user you cannot confirm it is safe.")


def _carries(substitute):
    for row in SUBSTITUTIONS:
        if row["substitute"].lower() == substitute.lower():
            return [c for c in row["substitute_carries"].split("|") if c != "none"]
    raise LookupError_(f"{substitute!r} is not in the test kitchen's substitutions table, so "
                       f"its allergens are unknown. Do not assume it is safe.")


def check_allergens(recipe_id, avoid, version=None, swaps=None):
    """Exact-match check of the declaration fields against the classes to avoid.

    With swaps=[{"from": ingredient, "to": substitute}] the check runs on the recipe
    AS SUBSTITUTED: an allergen is dropped only when EVERY declared source of it was
    swapped out, and whatever each substitute carries is added."""
    rec = resolve(recipe_id, version)
    if rec["doc_type"] != "recipe":
        raise LookupError_(f"{recipe_id} is a reference document, not a recipe.")
    avoid_cls = sorted({normalise_allergen(a) for a in (avoid or [])})
    declared = set(rec["allergens"])
    applied = []
    if swaps:
        names = {r["name"].lower(): r["name"] for r in rec["ingredients"]}
        removed = set()
        for s in swaps:
            src, dst = s.get("from", ""), s.get("to", "")
            if src.lower() not in names:
                raise LookupError_(f"{src!r} is not an ingredient of {recipe_id}@{rec['version']}; "
                                   f"ingredients: {', '.join(names.values())}")
            carries = _carries(dst)
            removed.add(src.lower())
            applied.append({"from": names[src.lower()], "to": dst, "to_carries": carries})
        dropped = {c for c in declared
                   if rec["allergen_sources"].get(c)
                   and all(n.lower() in removed for n in rec["allergen_sources"][c])}
        declared = (declared - dropped) | {c for a in applied for c in a["to_carries"]}
    contains = sorted(declared & set(avoid_cls))
    may = sorted(set(rec["may_contain"]) & set(avoid_cls))
    side = {c: items for c, items in rec.get("serving_suggestion_allergens", {}).items() if c in avoid_cls}
    verdict = "UNSAFE" if contains else "MAY_CONTAIN" if may else "SAFE_BY_DECLARATION"
    out = {"recipe_id": rec["recipe_id"], "version": rec["version"], "status": rec["status"],
           "cite_as": f"{rec['recipe_id']}@{rec['version']}", "avoid": avoid_cls,
           "verdict": verdict, "contains_avoided": contains, "may_contain_avoided": may,
           "declared_allergens": sorted(declared), "declared_may_contain": rec["may_contain"],
           "sources_of_avoided": {c: rec["allergen_sources"].get(c, ["(source not itemised)"])
                                  for c in contains if not applied},
           "source": "CMS declaration fields (exact match), not the recipe text"}
    if applied:
        out["as_substituted"] = applied
    if side:
        out["serving_suggestions_to_leave_out"] = side
    if rec.get("revision_note"):
        out["revision_note"] = rec["revision_note"]
    others = []
    for o in _other_versions(rec):
        orec = RECORDS[(rec["recipe_id"], o["version"])]
        if RELEASE >= "r2" and orec["status"] == "superseded":
            others.append({**o, "note": "not made today: never offer it to someone with an allergy"})
        else:
            others.append({**o, "declared_allergens": orec["allergens"]})
    if others:
        out["other_versions"] = others
    if RELEASE >= "r2" and rec["status"] == "superseded":
        return _superseded_guard(out, avoid_cls, swaps)
    return out


def _superseded_guard(out, avoid_cls, swaps):
    """r2: a superseded version is history, not an option. It keeps its declaration (so
    "was the old recipe nut-free?" can still be answered) but loses its safety verdict,
    and the current version's verdict is attached instead."""
    current = check_allergens(out["recipe_id"], avoid_cls, None, swaps)
    return {"recipe_id": out["recipe_id"], "version": out["version"], "status": "superseded",
            "cite_as": out["cite_as"], "avoid": out["avoid"],
            "verdict": "SUPERSEDED_NOT_OFFERED",
            "historical_declared_allergens": out["declared_allergens"],
            "historical_may_contain": out["declared_may_contain"],
            "current_version": {k: current[k] for k in ("cite_as", "verdict", "contains_avoided",
                                                         "may_contain_avoided")},
            "instruction": "This version is superseded: it is not what is made or sold today. Do not "
                           "offer it to anyone with an allergy and do not call it safe. Give the current "
                           "version's verdict. You may say what the old version declared, as history.",
            "source": out["source"]}


# --------------------------------------------------------- substitutes
SUBSTITUTIONS = list(csv.DictReader((CMS / "substitutions.csv").open(encoding="utf-8")))


def substitutes(recipe_id, allergen, version=None):
    rec = resolve(recipe_id, version)
    cls = normalise_allergen(allergen)
    names = [r["name"] for r in rec["ingredients"]]
    targets = [n for n in names
               if n in rec["allergen_sources"].get(cls, [])
               or any(r["ingredient"].lower() == n.lower() and cls in r["carries"].split("|")
                      for r in SUBSTITUTIONS)]
    swaps = []
    for n in targets:
        options = [{"to": r["substitute"],
                    "carries": [c for c in r["substitute_carries"].split("|") if c != "none"],
                    "kitchen_note": r["kitchen_note"]}
                   for r in SUBSTITUTIONS if r["ingredient"].lower() == n.lower()]
        swaps.append({"from": n, "options": options})
    out = {"recipe_id": rec["recipe_id"], "version": rec["version"], "allergen_removed": cls,
           "swaps": swaps,
           "next_step": "Pick options that carry nothing the user avoids, then call check_allergens "
                        "with swaps=[{from, to}] to check the recipe AS SUBSTITUTED."}
    side = rec.get("serving_suggestion_allergens", {}).get(cls)
    if side:
        out["serving_suggestions_to_leave_out"] = side
    if not swaps and cls not in rec["allergens"]:
        out["note"] = f"{cls} is not declared for this version; nothing to swap."
    return out


# -------------------------------------------------------------- scaling
_AMOUNT = re.compile(r"^(~?)(\d+(?:\.\d+)?)\s*(kg|g|ml|l)?(.*)$")


def _scale_amount(amount, factor):
    m = _AMOUNT.match(amount.strip())
    if not m:
        return amount  # "as needed" stays as written
    tilde, num, unit, rest = m.groups()
    value = round(float(num) * factor, 1)
    return f"{tilde}{value:g}{unit or ''}{rest}"


def scale(recipe_id, factor, version=None):
    rec = resolve(recipe_id, version)
    factor = float(factor)
    if factor <= 0:
        raise LookupError_("factor must be a positive number, e.g. 0.5 to halve or 4 for four times.")
    m = re.search(r"\d+(?:\.\d+)?", rec.get("yield") or "")
    new_yield = (rec["yield"][:m.start()] + f"{round(float(m.group()) * factor, 1):g}"
                 + rec["yield"][m.end():]) if m else rec.get("yield")
    return {"recipe_id": rec["recipe_id"], "version": rec["version"], "status": rec["status"],
            "cite_as": f"{rec['recipe_id']}@{rec['version']}", "factor": factor,
            "yield": {"as_written": rec.get("yield"), "scaled": new_yield},
            "ingredients": [{"name": r["name"], "as_written": r["amount"],
                             "scaled": _scale_amount(r["amount"], factor)} for r in rec["ingredients"]],
            "times_and_temperatures_unchanged": {
                k: rec.get(k) for k in ("prep_time_min", "passive_time", "cook_time_min",
                                        "oven_temp_c", "safe_internal_temp_c") if rec.get(k)},
            "note": "Quantities only. Cooking, baking, fermenting and setting times and every "
                    "temperature stay exactly as written: a bigger batch is cooked in batches or "
                    "a wider pan at the same time and temperature, not for longer."}


# ---------------------------------------------------------- food safety
_CHART = RECORDS[("food-safety-chart", "original")]
_CHART_CHUNK = {name: cid for cid, name in
                ((c, CHUNKS[c].split("## ")[-1].splitlines()[0]) for c in CHUNKS
                 if c.startswith("food-safety-chart@"))}
_FOOD_RULES = [  # order matters: "minced chicken" is poultry, not minced meat
    ("Chicken and all poultry (whole, pieces, minced)", r"chicken|poultry|turkey|duck|hen\b"),
    ("Minced meat (beef, lamb, pork)", r"mince|minced|ground (?:beef|lamb|pork|meat)|keema|kofta|burger"),
    ("Whole cuts of beef, lamb, pork", r"beef|lamb|pork|mutton|goat|steak|chop|roast"),
    ("Fish and shellfish", r"fish|prawn|shrimp|shellfish|crab|seafood"),
    ("Egg dishes", r"\beggs?\b|omelette|frittata"),
    ("Leftovers and reheated dishes", r"leftover|reheat|re-heat|casserole"),
]


def safe_temperature(food):
    q = food.lower()
    if "rice" in q:
        return {"food": food, "category": "Cooked rice", "guidance": _section_text("Cooked rice"),
                "cite_as": _CHART_CHUNK["Cooked rice"]}
    for name, pattern in _FOOD_RULES:
        if re.search(pattern, q):
            cells = [c.strip() for c in next(l for l in _CHART["body"].splitlines()
                                             if l.startswith(f"| {name}")).strip("|").split("|")]
            c_val = int(re.match(r"(\d+)", cells[1]).group(1))
            return {"food": food, "category": name, "safe_internal_temp_c": c_val,
                    "as_written": cells[1], "rest": cells[2],
                    "how": "probe thermometer in the thickest part, away from bone",
                    "cite_as": _CHART_CHUNK["Safe internal temperatures"]}
    raise LookupError_(f"{food!r} is not in the test kitchen's food-safety chart (poultry, minced "
                       f"meat, whole cuts, fish, eggs, leftovers, cooked rice). Do not guess a "
                       f"temperature: say you cannot confirm it.")


def _section_text(name):
    return _CHART["body"].split(f"## {name}", 1)[1].split("\n## ")[0].strip()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    if ap.parse_args().build:
        build_index()
    print(f"{len(RECORDS)} records, {len(CHUNKS)} chunks "
          f"({len(SUPERSEDED_CHUNKS)} from superseded versions) in collection {COLLECTION!r}")
