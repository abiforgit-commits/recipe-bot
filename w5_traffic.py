"""Week 5: generate app traffic to populate traces.jsonl.

We have no organic users, so this simulates a week of realistic usage in one
batch (disclosed in the write-up). The mix mirrors how real cooks ask:
direct quantity questions, how-tos, vague one-liners, typos, comparisons,
out-of-scope asks, multi-part requests, and food-safety worries. It was
written as a population, NOT engineered to trigger failures we expect.

Resumable: questions that already have a trace are skipped, so the script can
be re-run after an interruption without creating duplicates.
"""
import sys
import time

from w5_trace import TRACES, load_traces, traced_ask

sys.stdout.reconfigure(encoding="utf-8")

QUESTIONS = [
    # direct quantity / ingredient
    "How much rock salt goes into the idli batter?",
    "How much water do I need to grind the idli batter?",
    "How much urad dal for the dosa batter?",
    "How much coconut milk goes into appam?",
    "How much sugar is in the appam batter?",
    "How much starter curd do I need for 1 litre of milk?",
    "How much ragi flour for koozh?",
    "How much mustard seed goes in the mango pickle?",
    "How much Kashmiri chilli powder in kadumanga achar?",
    "How much fenugreek in the dosa batter?",
    "How much poha goes into the dosa batter?",
    "What rice do I use for appam?",
    "How much salt in the koozh?",
    "Which oil is used on the dosa tawa?",
    "How much gochugaru do I need?",
    # method / how-to
    "How long should idli batter ferment?",
    "How do I get the lace edge on an appam?",
    "When do I add the salt to the koozh?",
    "How do I know when the curd has set?",
    "How long do I soak the rice for dosa?",
    "How long do I steam idlis?",
    "How long does the mango pickle ferment in the salt?",
    "How should I store koozh after cooking?",
    "What temperature should I keep the curd at while it sets?",
    "Do I grind the rice and dal together for idli?",
    "How thin should dosa batter be?",
    "Should the appam batter rest after adding coconut milk?",
    # vague / underspecified
    "How much salt?",
    "How long to ferment?",
    "What temperature?",
    "Why is it sour?",
    "My batter didn't rise, what went wrong?",
    "It smells weird, is that okay?",
    "Can I make it faster?",
    "Is it done?",
    # typos / informal
    "how mch salt in idlly batter",
    "dosa batter recepie",
    "appam pan calld what",
    "curd not seting help",
    "khoozh raggi porridge how to make",
    # comparison / aggregation
    "Which recipe has the highest salt percentage?",
    "Which of these is quickest to make?",
    "Which recipes are vegan?",
    "What is the difference between idli and dosa batter?",
    "Which recipe needs no cooking at all?",
    # out of scope
    "How many calories are in one idli?",
    "How much protein does koozh have?",
    "Give me a biryani recipe.",
    "Can I use almond milk instead of coconut milk in appam?",
    "What wine pairs well with dosa?",
    "Can I microwave idlis instead of steaming?",
    "How long does dosa batter keep in the fridge?",
    # multi-part
    "Give me the full idli recipe with quantities and steps.",
    "What do I need to buy to make kadumanga achar?",
    "Plan me a vegan and gluten-free breakfast from these recipes.",
    # safety worries
    "There is a white film on top of my pickle, is it safe?",
    "I left the curd out overnight, can I still eat it?",
    "My koozh has been in the clay pot for two days, still fine?",
]

TRANSIENT = ("429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "overloaded")


def main():
    done = {t["question"] for t in load_traces()} if TRACES.exists() else set()
    todo = [q for q in QUESTIONS if q not in done]
    print(f"{len(QUESTIONS)} total, {len(done)} already traced, {len(todo)} to run", flush=True)

    failed = []
    for i, q in enumerate(todo, 1):
        for attempt in range(1, 7):
            try:
                rec = traced_ask(q)
                print(f"{i:>2}/{len(todo)} [{rec['trace_id']}] {q[:60]}", flush=True)
                break
            except Exception as e:
                msg = str(e)
                if any(tok in msg for tok in TRANSIENT):
                    wait = 20 * attempt
                    print(f"   transient error, waiting {wait}s (attempt {attempt})", flush=True)
                    time.sleep(wait)
                else:
                    print(f"   ERROR on '{q[:40]}': {msg[:120]}", flush=True)
                    failed.append(q)
                    break
        else:
            print(f"   gave up on '{q[:40]}' after 6 attempts", flush=True)
            failed.append(q)
        time.sleep(2)  # stay inside free-tier requests-per-minute

    print(f"done. {len(failed)} failed: {failed}", flush=True)


if __name__ == "__main__":
    main()
