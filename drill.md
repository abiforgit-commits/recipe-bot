# drill.md — "Find the dairy-free swap that wasn't"

## Result

| | |
|---|---|
| **Time-to-find** | **00:18** (finder's own clock: `date +%s` 1791315673 → 1791315691) |
| Dispatch-to-report, including agent start-up and an after-the-clock check | 01:00 |
| **Slice that found it** | **output text search** (`find --text "dairy"`, read the 21 hits) |
| Found trace | `e6fa2dbb1746`, **correct**: matches the sealed answer key |
| Under 5 minutes? | yes |

## The complaint, exactly as given to the finder

> "someone said it recommended a dairy-free substitution that wasn't dairy-free, sometime last week."

No trace id, no timestamp, no recipe name, no user.

## Who did what (read this before the time)

There was no human squadmate in this session, so the two roles were split so that
the finder could not rely on memory:

- **Planter: the main session (Claude), playing the squadmate.** It found a
  *genuine* failure by probing the live app (`w11_probe.py`; 5 of 6 koozh dairy-free
  questions failed), then inserted that real trace at a random moment in the prompt-v2
  window and under a random user (`w11_plant.py`). The answer key was written **outside
  the repo**. The traffic, plant and probe scripts were committed only **after** the
  drill, so the finder could not compare the log with the question pool.
- **Finder: a separate, freshly started agent** with no access to this conversation.
  It was given only the complaint, the log file and `w11_logq.py`, and told not to open
  any other file. It reported every command it ran (below), so its method can be audited.
- **Timed by:** the finder's own `date +%s` at its first and last action, then checked
  against the sealed answer key `results/w11_drill_answer_key.json` (planted at
  position 49 of 100, user u005, 2026-10-01 17:50 IST).

**Re-run it with a human:** anyone can repeat the drill with
`python w11_logq.py ...` and the same complaint. That is the version that counts for a
human squadmate, and the obvious next step.

## The finder's commands, verbatim from its report

```
1. date +%s
2. python w11_logq.py stats
3. python w11_logq.py find --text "dairy" --snippet "dairy[- ]free|dairy"
4. (python one-liner over logs/w11_requests.jsonl printing the full output of 13 candidates)
5. date +%s
6. (after the clock) find --out "mor milagai|curd chilli|ghee|paneer|whey|..." to confirm no second bad trace
```

## Why that slice, and why the other five didn't

| Slice | Useful here? | Why |
|---|---|---|
| time | no | "sometime last week" covers the whole log |
| user | no | no user named |
| prompt version | **no** | the failure also happens on **p-v1** (probe: the strict prompt recommended curd chilli to a dairy-free user too), so filtering to p-v2 would not isolate it |
| input type | partly | `--type substitution` narrows 100 → 20, but doesn't pinpoint |
| cost outlier | no | this request cost $0.0002085, not an outlier |
| **output text** | **yes** | the complaint describes what the assistant **said**, and the log indexes the output, not just the query |

This is the task's listed mistake avoided: *"Searching only inputs when the complaint
describes the output."* Searching the queries alone would have found 14 dairy-free
**questions**, 13 of them answered correctly.

## What slowed it down, and the missing field

The finder named one field whose absence cost it time:

> **`detected.diet_constraints` (what the user asked to avoid) compared against the
> allergens of what the answer actually recommended, stored as a flag like
> `constraint_violation: true`.** Then `find --violation dairy` would return this trace
> instantly.

Today the tooling can't tell "mentions dairy" from "presents dairy as dairy-free".
Curd chilli never contains the words *dairy*, *milk* or *buttermilk*, so a regex alone
can't flag it. The finder had to **read** 13 candidate answers. Two smaller tooling
gaps it reported: `--snippet` shows only the first match (it showed the correct "skip
the buttermilk" sentence and hid the bad list further down), and `show` takes one
trace at a time.

## Honest limits on the 00:18

- **The log is 100 requests, not thousands.** Reading 13 candidates is easy at this
  size; at production volume, the same "read every dairy hit" approach would not fit in
  5 minutes. That is exactly why the missing field matters.
- **The finder is an AI agent**, which reads 13 answers far faster than a person would.
  A human run of the same drill would take longer.
- **The traffic is simulated:** real model answers, but simulated timestamps and users
  (Mon 28 Sep to Sun 4 Oct 2026, 24 users, p-v1 then p-v2 from Thu 1 Oct).

## The found trace

`trace.json` holds the full record. The spans:

| Span | Latency | Tokens | Cost | Detail |
|---|---|---|---|---|
| retrieval | 310.8 ms | 0 | $0 | context ids `ragi-koozh-05::structure::3, ::2, ::1, ::0, dosa-batter-02::structure::3` |
| tools | 2.8 ms | 0 | $0 | `recipes.substitute_ingredient(ragi-koozh-05, dairy)` → **`"swaps": []`** |
| generation | 4,517.5 ms (2,859.9 ms waiting on pacing) | 733 in + 338 out | $0.0002085 | `gemini-flash-lite-latest`, prompt **p-v2** |

**The root cause, read from the spans:** the allergen tool only checks the **ingredient
table**, and curd chilli sits on the "Serve with" line, outside it. The tool reported
nothing to swap, retrieval handed the model the serve-with chunk (`::1`), and the model
filed curd chilli under *"The Usual Dairy-Free Sides"*.
