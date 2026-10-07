"""Week 11 traffic: a simulated week (Mon 28 Sep - Sun 4 Oct 2026) of real app runs.
Every answer is a real model call; only the timestamps and user ids are simulated.
p-v1 Mon-Wed, p-v2 from Thu 1 Oct (the mid-week prompt deploy)."""
import asyncio, json, random, sys, os
sys.path.insert(0, r"D:\AI Learning\week3-rag"); os.chdir(r"D:\AI Learning\week3-rag")
from datetime import datetime, timedelta, timezone
from w11_app import RecipeApp, LOG
from w5_traffic import QUESTIONS as W5Q

EXTRA = [
 # dairy / vegan near-misses whose correct answers mention milk or curd
 "Make the thayir curd recipe dairy-free", "Can I make thayir without dairy?",
 "Dairy-free substitute for the whole milk in thayir", "Make thayir vegan",
 "Is appam dairy-free?", "Is the dosa batter vegan?", "Does the idli batter contain milk?",
 "Which recipes are dairy-free?", "Is the mango pickle dairy-free?", "lactose free curd possible?",
 # koozh questions where curd chilli comes up legitimately (no dairy restriction)
 "How do I serve ragi koozh?", "What goes well with ragi koozh?", "What is curd chilli?",
 "Is ragi koozh served hot or cold?",
 # scaling / other substitutions
 "Double the idli batter recipe", "I need half a batch of dosa batter",
 "Make the mango pickle sesame-free", "Halve the appam recipe and make it coconut-free and nut-free",
 "Make the thayir curd recipe dairy-free and nut-free", "Make the idli batter nut-free",
 "Scale the ragi koozh to one and a half times", "Make the appam gluten-free",
]
# the koozh+dairy-free questions are kept OUT of normal traffic: one is planted separately
POOL = [q for q in W5Q if "biryani" not in q] + EXTRA
rng = random.Random(7)
users = [f"u{n:03d}" for n in range(1, 25)]
weights = [8, 6, 5, 5, 4, 4, 3, 3, 3, 3, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1]
qs = POOL + rng.sample(POOL, 20)                       # 100 requests, popular ones repeat
IST = timezone(timedelta(hours=5, minutes=30))
start = datetime(2026, 9, 28, 7, 0, tzinfo=IST)
plan = []
for q in qs:
    day = rng.randrange(7); hour = rng.choice([7,8,9,12,13,18,19,20,21]); minute = rng.randrange(60)
    ts = (start + timedelta(days=day, hours=hour - 7, minutes=minute, seconds=rng.randrange(60)))
    plan.append((ts.isoformat(timespec="seconds"), rng.choices(users, weights)[0], q))
plan.sort()
done = 0
if LOG.exists():
    done = sum(1 for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip())
async def main():
    async with RecipeApp() as app:
        for i, (ts, user, q) in enumerate(plan):
            if i < done: continue
            ver = "p-v1" if ts < "2026-10-01" else "p-v2"
            r = await app.answer(q, user_id=user, prompt_version=ver, ts=ts)
            print(f"{i+1:>3}/{len(plan)} {ts} {user} {ver} {r['input_type']:<14} {q[:50]}", flush=True)
asyncio.run(main())
