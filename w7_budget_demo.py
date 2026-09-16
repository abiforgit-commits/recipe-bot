"""Week 7: prove each budget actually terminates the loop.

    python w7_budget_demo.py

Runs the SAME hard request four times, each time with one budget lowered so
that budget is the one that fires. The point is that the loop stops cleanly
with a stop_reason - it does not spin, and it does not crash.
"""
import sys

import w7_agent
from w7_agent import run_agent

sys.stdout.reconfigure(encoding="utf-8")

REQUEST = ("Double the appam recipe and make it coconut-free, nut-free and "
           "gluten-free, then tell me every substitution you considered")

DEFAULTS = dict(MAX_ITERS=w7_agent.MAX_ITERS, MAX_TOKENS=w7_agent.MAX_TOKENS,
                MAX_COST_USD=w7_agent.MAX_COST_USD, MAX_WALL_SEC=w7_agent.MAX_WALL_SEC)

SCENARIOS = [
    ("max_iters", dict(MAX_ITERS=2)),
    ("max_tokens", dict(MAX_TOKENS=1200)),
    ("max_cost", dict(MAX_COST_USD=0.0002)),
    ("wall_clock", dict(MAX_WALL_SEC=6)),
]

print(f"request: {REQUEST}\n")
for name, overrides in SCENARIOS:
    for k, v in DEFAULTS.items():
        setattr(w7_agent, k, v)
    for k, v in overrides.items():
        setattr(w7_agent, k, v)
    limits = ", ".join(f"{k}={v}" for k, v in overrides.items())
    print(f"--- scenario: {name} ({limits}) ---")
    r = run_agent(REQUEST, verbose=True)
    print(f"  STOPPED: {r['stop_reason']}")
    print(f"  laps={r['laps']}  tokens={r['tokens_total']}  "
          f"cost=${r['cost_usd']:.6f}  latency={r['latency_s']}s")
    print(f"  returned cleanly (no exception, no spin); final is "
          f"{'present' if r['final'] else 'None - terminated before answering'}\n")

for k, v in DEFAULTS.items():
    setattr(w7_agent, k, v)
print("budgets restored to defaults:", DEFAULTS)
