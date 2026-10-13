"""Capstone: realistic traffic for the error taxonomy (NOT eval cases).

    python pantry_traffic.py --tag before

Twenty questions a home cook might actually type, written without looking at the
eval cases, so the taxonomy is read from traffic the suite was not designed around.
Each runs through the integrated system and is logged like any request; full
records go to results/pantry_traffic_<tag>.jsonl for reading.
"""
import argparse
import asyncio
import json
import random
import sys
from pathlib import Path

import pantry_corpus as pc
from pantry_agent import PantryAgent

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent

TRAFFIC = [
    "What can I bake for a school bake sale that's nut-free?",
    "my daughter is coeliac, can she have dosa?",
    "Is the kadumanga pickle vegan?",
    "Double the appam recipe for a party - how much coconut milk?",
    "How long should I marinate the chettinad chicken?",
    "I'm out of urad dal, can I still make idli?",
    "Can I use the old nankhatai recipe? It had no nuts right?",
    "We have a sesame allergy - what oil can I use for the kadumanga instead?",
    "How many calories are in one nankhatai biscuit?",
    "What goes into the Chettinad masala?",
    "My son has a peanut allergy. Which of your recipes are safe for him?",
    "Can I freeze idli batter?",
    "How do I reheat leftover chettinad chicken safely?",
    "I'm lactose intolerant - can I make the thayir with oat milk instead?",
    "Triple the lemon rice. How long does it cook?",
    "Is appam OK for someone allergic to coconut?",
    "What is kalpasi?",
    "Is the dosa batter gluten free?",
    "my kid is allergic to sesame and nuts, can she have the nankhatai?",
    "Can I make ragi koozh the same morning I want to drink it?",
]


async def main(tag):
    out = ROOT / "results" / f"pantry_traffic_{tag}.jsonl"
    out.unlink(missing_ok=True)
    rng = random.Random(20261012)
    pc._collection()
    async with PantryAgent() as agent:
        for i, q in enumerate(TRAFFIC, 1):
            rec = await agent.ask(q, user=f"u{rng.randint(1, 40):03d}")
            rec["traffic_id"] = f"t{i:02d}"
            with out.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"  t{i:02d} {rec['laps']} laps  {'>'.join(rec['tool_sequence']) or '(no tools)'}  "
                  f"${rec['cost_usd_total']:.6f}  {q[:60]}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="before")
    asyncio.run(main(ap.parse_args().tag))
