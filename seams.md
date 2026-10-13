# Seam list: what broke or didn't fit while integrating

**Written during integration (started Mon 12 Oct 2026, 00:30 IST). Unedited:**
entries are appended in the order they were found and are never rewritten. Each
entry's final status (fixed / accepted / ran-out-of-time) is added in the
**Status** table at the end, not by editing the entry.

Honest dating: the brief asks for "Tuesday's seam list". This one was written on
Monday 12 Oct, the day the integration was done.

---

**S1 (00:40). Chunk ids had no version.** Weeks 3–11 cite `recipe::structure::n`.
With two versions of a recipe that id is ambiguous, and the brief says a citation
that doesn't name the version doesn't count. New id: `recipe@version::structure::n`.
Every regex that parses citations (`ask.py`, `w6_assertions.CITE_RE`, `w11_*`) uses the
old shape, so the capstone needs its own citation parser.

**S2 (00:45). The page text and the declaration disagree, and search ranks the wrong
one first.** For "Is the nankhatai nut-free?", hybrid search puts
`nankhatai-07@original::structure::3` (superseded, "nut-free") at rank 1 and the current
version's stale allergen note (also "nut-free") at rank 2. Any answer built from
retrieved text alone says "nut-free". The Week 3 RAG can't be the allergen path.

**S3 (00:45). The safe-temperature table is not in the top 5 for "How do I know the
chicken is cooked?"** The chart's intro and its rice section are; the 74°C row isn't.
The Week 4 retriever is shipped unchanged, as the brief says, so the temperature must
come from an exact lookup (`get_safe_temperature`), not from search.

**S4 (00:50). Week 7–9 tools load `data/new_cards/` (6 cards, no versions, no
declaration fields).** `w7_tools.CARDS_BY_ID` can't see the CMS. The capstone server
reads `data/cms/` through `pantry_corpus.py`. The Week 9 recipe server stays as it was,
so Weeks 7–11 still reproduce.

**S5 (00:50). Week 4/6/11 modules load the old Chroma collection at import time.**
`w4_retriever` calls `get_collection("recipes_structure")` on import. On a fresh clone
that collection doesn't exist, so importing it would crash before the user asked
anything. The capstone code must not import `w4_retriever`, `w6_eval` or `w11_app`; it
reuses their algorithms (RRF k=60, the tokenizer) instead.

**S6 (01:05). Two citation shapes.** First live run: the model cited
`[nankhatai-07@reformulated-2025]`, the `cite_as` value check_allergens returns, rather
than a chunk id, and the source list came out empty. The declaration lives in the
CMS fields, not in any chunk, so `recipe@version` is a legitimate citation for an
allergen verdict. The parser now accepts both shapes, and both must resolve to a real
version.

**S7 (01:05). The agent offers the superseded recipe as "safe".** Same run, question
"My son is allergic to nuts - can he have the nankhatai?". The answer correctly said
the current version is UNSAFE, then volunteered that "the superseded original version
is SAFE BY DECLARATION". The tool lists `other_versions`, and the agent checked the
old one on its own. That recipe no longer exists in what the parent can buy. This
mode was created by integration: no single week's component has versions. Left
unfixed on purpose so the baseline eval sees it (trace `43a4bd3b7af84f6f`).

**S8 (01:50). The judge passed the superseded-shortbread answer.** Baseline a01:
"the older, superseded original version is SAFE_BY_DECLARATION for a nut allergy".
judge_v2 said PASS ("correctly distinguishes current (unsafe) and original (safe)").
Only assertion P6 caught it. This is the brief's warning made concrete: allergen
safety can't be left to the judge.

**S9 (01:50). The judge trusts the stale prose over the declaration.** Baseline g01
(egg allergy): the system answered "I cannot confirm ... egg is not a declared
allergen class", which is the designed behaviour. The judge FAILED it for "ignoring
the explicit 'Egg-free and nut-free' note", which is the same stale paragraph that
wrongly says nut-free. The judge from Weeks 6–11 never had a version or a declaration
field to weigh against prose.

**S10 (01:55). Three assertion bugs, found by reading all 33 baseline traces.** P2
false-failed a clarifying question (v01); P11 false-failed "I cannot confirm WHETHER
it is safe" (g01); P1 false-passed invented ids like
`[lemon-rice-09@original::check_allergens]` (c02). All three were fixed in the eval
code, the same 33 outputs were re-scored (judge verdicts reused), and the original
scoring is kept in `results/pantry_eval_before_assertions_v1.json`. Every assertion
verdict now matches my reading of the 33 answers.

**S11 (01:55). The tools have no chunk ids, so the model invents them.** c02 cited
`[lemon-rice-09@original::find_substitutes]` and a05 cited `[thiyir-04@...]`. Week 6
had no tool results to cite; integration added them.

**S12 (Wed 14 Oct, 00:10). A network drop killed a 45-run eval.** The machine lost DNS
around 01:00 on 12 Oct (`getaddrinfo failed`). `ask.call_llm` retried rate limits but
not connection errors, so one blip crashed the whole run after 6 of 45 cases. Fixed:
connection errors are now retried like a 429, and `pantry.py eval --resume` keeps the
finished runs. The crash also left an **orphaned MCP server process** holding the index
open; it was found and stopped by hand. Nothing reaps orphaned stdio servers.

**S13 (00:25). Provider latency, not our rate limit.** On resume, single model calls
took 37–225 s (baseline: about 4 s) with 0 s of our own throttle wait. A bare
"Say OK." took 201 s; network latency to the API host was 0.8 s. The eval had to be cut
to fit (one extra run per allergy case instead of three, jobs in parallel). Pinning a
specific model isn't an escape either: `gemini-2.5-flash-lite` now returns 404 "no
longer available to new users".

**S14 (00:30). The Week 6 judge does not clear 85% on integrated outputs.** judge_v2
vs blind labels: 28/33 = 84.8%. Disagreements: v02 and g02 (passed refusals that never
searched; the judge doesn't know a search tool existed), a01 (passed the superseded
"safe"), g01 (trusted stale prose), a05 (failed a misspelled citation it was told to
ignore). judge_v3 adds four rules, one per disagreement type. It is tuned on these 33,
so it must be validated on different outputs.

**S15 (00:50). Reading the repeat runs found three more assertion problems.** Fixed,
and the same outputs re-scored: (1) P6 false-failed past-tense history ("the original
WAS nut-free") while the same idea phrased "is no longer current" passed. P6 now fails
only present-tense claims about a superseded version. (2) P6 read "unsafe for a nut-free
DIET" as a safety claim. (3) P5 didn't accept "is NOT nut-free" or "the declaration
lists nuts" as stating the hazard. Also Week 11's A5 lacked "dairy-based"; it was added
and re-validated on its 45 labels (still 45/45). A display filter of mine
(`grep -v warn`) once hid an answer line containing "warning". Lesson: never filter
model output with a word that can appear in an answer.

**S16 (00:55). The model invented a tool name.** After-fix c02 called
`pantry__pantry__get_safe_temperature`: Week 9's `<server>__<tool>` namespacing, doubled.
The host returned "no such tool" and the model recovered on the next lap. But my
eval's progress printout crashed on the unknown tool's empty name and stopped the run
after 13 of 15 cases (resumed with `--resume`). Fixed: the trace keeps the name the
model called, so the trajectory eval scores it as a wrong tool.

**S17 (01:00). Assertion corrections from reading the after-fix traces.** A5 gained
unconditional "leave out / skip" (conditional hedges still fail; Week 11's 45 labels
still 45/45). P11 no longer counts the page text being *quoted and rejected* ("the text
says egg-free, but recipe text cannot be used to verify") as a claim. P5's substitution
rule accepts a sentence that names the carried allergen as the reason ("allergic to
nuts"). The nut pattern got word boundaries: "coconut" had been matching "nut", so a
synthetic bad answer was passing. Every assertion verdict on all 96 suite and repeat
outputs (before and after) now matches my reading of the answer.

**S18 (01:00). The trajectory spec was wrong for one case.** c02 ("leftover cooked
rice …") calling `get_safe_temperature` for the rice was flagged `wrong_tool`; the rice
rule is legitimate there. The spec now allows it for c02 (`allowed_extra`). Path
evals are only as good as the "allowed path" written for each case.

**S19 (01:05). The trace id stops at the Week 9 server.** `ingredient_db_server` (the
content team's server) doesn't read `_meta`, so its calls have client-side spans only, with
no server span under the trace id. Our own server logs both sides.

**S20 (01:05). Two servers, two vocabularies.** Traffic t09 ("calories in one nankhatai")
made 4 nutrition lookups with CMS ingredient names ("Maida (all-purpose flour)") that the
content team's database doesn't know, then refused. t06 ("out of urad dal") used the
allergen-only substitution tool for a pantry swap and got two argument errors. Each server
is fine on its own; the seam is between them.

---

## Status (added at the end; entries above are not edited)

| Seam | Status | Note |
|---|---|---|
| S1 chunk ids had no version | **fixed** | `recipe@version::structure::n` |
| S2 stale page ranks first in search | **accepted** | allergens come only from the declaration tool. Next #1 stops the stale history being repeated |
| S3 safe-temperature row not in the top 5 | **fixed** (exact lookup tool) / **ran out of time** (forcing it) | k02 after the fix still dropped 74 °C. Next #2 renders it in code |
| S4 Week 7–9 tools read the old cards | **fixed** | the capstone server reads `data/cms/` |
| S5 old modules load an old index on import | **fixed** | the capstone imports none of them |
| S6 two citation shapes | **fixed** | both accepted, both must resolve |
| S7 superseded version offered as safe | **fixed** (release r2: 3/6 → 0/6) | the stricter "never mention it" reading: 6/6 → 5/6, next #1 |
| S8 the judge passed the superseded "safe" | **accepted** | by design, allergens are asserted, not judged |
| S9 the judge trusts stale prose | **partly fixed** | judge_v3 rule C; v4 still passes 1 stale-prose answer on held-out |
| S10 three assertion bugs | **fixed** | |
| S11 invented citation ids | **ran out of time** | 2/30 after; P1 catches it |
| S12 network drop killed a run; orphaned server | **fixed** (retry, `--resume`) / **ran out of time** (orphan reaping) | |
| S13 provider latency | **accepted** | outside our control; demo plan B uses recorded traces |
| S14 judge_v2 below 85% on integrated outputs | **fixed, narrowly** | judge_v4 86.0% on 50 held-out (CI ≈ 74–93%) |
| S15 assertion problems in the repeat runs | **fixed** | |
| S16 invented tool name crashed the printout | **fixed** | |
| S17 assertion corrections from the after-fix traces | **fixed** | 96/96 verdicts match a reading |
| S18 trajectory spec wrong for c02 | **fixed** | |
| S19 trace id stops at the Week 9 server | **accepted** | client-side spans only for ingredient-db |
| S20 two servers, two vocabularies | **ran out of time** | nutrition questions refuse after 4 wasted calls |
