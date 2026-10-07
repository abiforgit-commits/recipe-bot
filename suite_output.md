# suite_output.md: the Week-6 suite + w11_r01, RED before the fix, GREEN after

Same 26 cases both times: every runnable Week-6 case (c01–c25) plus the new case
**w11_r01** (`w11_eval_case.jsonl`, also appended to `w6_cases.jsonl`). A case passes
when the Week-6 judge (`judge_v2.txt`) says PASS **and** assertion A5 passes. Only the
prompt version differs between the runs. Command: `python w11_suite.py --version <v>`.

| | Version | Suite | w11_r01 |
|---|---|---|---|
| **RED** (before the fix) | p-v2 | **18/26** | FAIL (A5) |
| **GREEN** (after the fix) | p-v5 | **20/26** | **PASS** |

## RED: `python w11_suite.py --version p-v2` (pasted verbatim)

```
PASS  c01      How much salt?                                              
PASS  c02      Is it done?                                                 
PASS  c03      Can I make it faster?                                       
PASS  c04      What temperature?                                           
FAIL  c05      How long to ferment?                                           <- judge FAIL
FAIL  c06      How should I store koozh after cooking?                        <- judge FAIL
FAIL  c07      My batter didn't rise, what went wrong?                        <- judge FAIL
PASS  c08      How do I keep the mango pickle from spoiling?               
FAIL  c09      My kitchen is cold and the curd will not set, what can I d     <- judge FAIL
FAIL  c10      What rice do I use for appam?                                  <- judge FAIL
PASS  c11      What flour do I need for ragi koozh?                        
PASS  c12      What dal goes into dosa batter?                             
PASS  c13      Which recipe has the highest salt percentage?               
PASS  c14      Which recipe ferments for the longest time?                 
PASS  c15      Which of these recipes uses the most water?                 
FAIL  c16      Which oil is used on the dosa tawa?                            <- judge FAIL
PASS  c17      Is there sesame in the mango pickle?                        
PASS  c18      Does the idli recipe use asafoetida?                        
PASS  c19      Should the appam batter rest after adding coconut milk?     
PASS  c20      Do I need to stir the idli batter after it has risen?       
PASS  c21      Can I use the same batter for both idli and dosa?           
PASS  c22      How much rock salt goes into the idli batter?               
PASS  c23      How long should idli batter ferment?                        
PASS  c24      How much mustard seed goes in the mango pickle?             
FAIL  c25      How many calories are in one idli?                             <- judge FAIL
FAIL  w11_r01  Give me a dairy-free version of ragi koozh with the usual      <- A5 FAIL
SUITE [p-v2]: 18/26 pass
```

The judge **passed** w11_r01 here. It reads curd chilli as a grounded side because the
card lists it. A5 caught it: curd chilli is offered as a side for the "dairy-free"
koozh, and the dairy is only hedged ("if you are avoiding dairy entirely, you can
substitute"). This run was recorded under A5 v2. Re-scored under the final A5 v3 it is
unchanged: 18/26, w11_r01 FAIL (`python w11_a5_check.py`, results_w11.md).

## GREEN: `python w11_suite.py --version p-v5` (pasted verbatim)

```
PASS  c01      How much salt?                                              
PASS  c02      Is it done?                                                 
FAIL  c03      Can I make it faster?                                          <- judge FAIL
PASS  c04      What temperature?                                           
PASS  c05      How long to ferment?                                        
FAIL  c06      How should I store koozh after cooking?                        <- judge FAIL
FAIL  c07      My batter didn't rise, what went wrong?                        <- judge FAIL
PASS  c08      How do I keep the mango pickle from spoiling?               
PASS  c09      My kitchen is cold and the curd will not set, what can I d  
PASS  c10      What rice do I use for appam?                               
FAIL  c11      What flour do I need for ragi koozh?                           <- judge FAIL
PASS  c12      What dal goes into dosa batter?                             
PASS  c13      Which recipe has the highest salt percentage?               
PASS  c14      Which recipe ferments for the longest time?                 
PASS  c15      Which of these recipes uses the most water?                 
FAIL  c16      Which oil is used on the dosa tawa?                            <- judge FAIL
PASS  c17      Is there sesame in the mango pickle?                        
PASS  c18      Does the idli recipe use asafoetida?                        
PASS  c19      Should the appam batter rest after adding coconut milk?     
PASS  c20      Do I need to stir the idli batter after it has risen?       
PASS  c21      Can I use the same batter for both idli and dosa?           
PASS  c22      How much rock salt goes into the idli batter?               
PASS  c23      How long should idli batter ferment?                        
PASS  c24      How much mustard seed goes in the mango pickle?             
FAIL  c25      How many calories are in one idli?                             <- judge FAIL
PASS  w11_r01  Give me a dairy-free version of ragi koozh with the usual   
SUITE [p-v5]: 20/26 pass
```

## Could a silent regression hide in those counts?

Five cases other than w11_r01 flipped between the two runs: c03 and c11 PASS→FAIL,
c05, c09 and c10 FAIL→PASS. None of them can be a regression caused by the fix:

```
$ python w11_scope.py
p-v3: request differs from p-v2 on 26/26 cases: all
p-v4: request differs from p-v2 on 1/26 cases: ['w11_r01']
p-v5: request differs from p-v2 on 1/26 cases: ['w11_r01']
```

p-v5 keeps p-v2's prompt word for word and only adds the dairy instruction and the
pinned allergen note when the request is flagged dairy-free. So for c01–c25 the model
received **byte-identical requests** in both runs. Those flips are the model and judge
varying run to run (Gemini at temperature 0 is not deterministic). That noise was
measured independently: p-v4, which also sends p-v2's exact request for c01–c25, moved
3 cases too. Every flip is the judge's "outside knowledge" verdict (e.g. c03: "Instant
Pot … Yogurt setting"; c11: "pulse regular white rice"), caused by p-v2's own "fill small
gaps with general cooking knowledge" clause. That is a known, separate issue (see
results_w11.md).

## Is the GREEN one lucky run? (`python w11_repeat.py`)

| | p-v2 (before) | p-v5 (after) |
|---|---|---|
| w11_r01, 3 fresh runs | **0/3** | **3/3** |
| the drill's 6 dairy-free probe questions, once each | 2/6 (only the 2 thayir questions) | **5/6** |
| "I'm dairy-free. How should I serve ragi koozh?" (the probe that failed) ×3 more | not run | **3/3** |

The one p-v5 probe failure is a real defect that **A5 caught and the judge passed**. It
listed curd chilli under "What to avoid", then wrote *"it contains curd (which is made from
milk), **making it dairy-free**"*. Re-running that exact question 3 times passed 3/3, so it
is a one-off slip, not a systematic bug. In total, **12 of 13 fresh dairy-free answers on
p-v5 were correct, against 2 of 9 on p-v2** (0 of 7 for koozh). That residual roughly 1 in 13
is why the canary in results_w11.md runs A5 on live traffic.

## The two fixes that did NOT turn it green (kept on purpose)

Failing lines only. The full rows are in `results/w11_suite_p-v3.json` and `results/w11_suite_p-v4.json`.

```
--- p-v3: one global dairy rule added to every prompt
FAIL  c01      How much salt?                                                 <- judge FAIL
FAIL  c07      My batter didn't rise, what went wrong?                        <- judge FAIL
FAIL  c12      What dal goes into dosa batter?                                <- judge FAIL
FAIL  c25      How many calories are in one idli?                             <- judge FAIL
FAIL  w11_r01  Give me a dairy-free version of ragi koozh with the usual      <- judge FAIL A5 FAIL
SUITE [p-v3]: 21/26 pass

--- p-v4: the rule attached only to dairy-free requests
FAIL  c06      How should I store koozh after cooking?                        <- judge FAIL
FAIL  c07      My batter didn't rise, what went wrong?                        <- judge FAIL
FAIL  c16      Which oil is used on the dosa tawa?                            <- judge FAIL
FAIL  c25      How many calories are in one idli?                             <- judge FAIL
FAIL  w11_r01  Give me a dairy-free version of ragi koozh with the usual      <- judge FAIL
SUITE [p-v4]: 21/26 pass
```

The p-v3 w11_r01 line says "A5 FAIL" under A5 v1. Under the final A5 it passes A5, and
it still FAILs on the judge, so the count stays 21/26.
