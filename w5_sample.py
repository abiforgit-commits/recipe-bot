"""Week 5: seeded random sampling of traces, and a reader view for open-coding.

    python w5_sample.py 20 --seed 4242          -> pick and list the sample
    python w5_sample.py 20 --seed 4242 --full   -> print each sampled trace
                                                   (question, top chunks, output)

The seed makes the sample provable: anyone re-running with the same seed on
the same traces.jsonl gets the same 20 trace_ids.
"""
import argparse
import random
import sys

from w5_trace import load_traces

sys.stdout.reconfigure(encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("n", type=int)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()

    traces = load_traces()
    print(f"population: {len(traces)} traces   seed: {args.seed}   sample: {args.n}")
    sample = random.Random(args.seed).sample(traces, args.n)

    print("sampled trace_ids:", ", ".join(t["trace_id"] for t in sample))
    if not args.full:
        return

    for i, t in enumerate(sample, 1):
        print(f"\n{'=' * 72}\n#{i}  trace {t['trace_id']}")
        print(f"Q: {t['question']}")
        print("retrieved: " + ", ".join(
            f"{r['chunk_id']}({r['score']:.3f})" for r in t["retrieved"][:5]))
        print(f"OUTPUT: {t['output']}")


if __name__ == "__main__":
    main()
