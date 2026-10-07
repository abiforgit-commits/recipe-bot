import json, secrets
from datetime import datetime, timedelta, timezone
SP = "results"   # was the session scratchpad - kept out of the repo until the drill was over
LOG = r"D:/AI Learning/week3-rag/logs/w11_requests.jsonl"
probe = next(r for r in json.load(open(SP + "/w11_probe_out.json", encoding="utf-8"))
             if r["query"].startswith("Give me a dairy-free version of ragi koozh"))
assert probe["prompt_version"] == "p-v2"
IST = timezone(timedelta(hours=5, minutes=30))
start = datetime(2026, 10, 1, 7, 0, tzinfo=IST)          # p-v2 window: Thu 1 Oct - Sun 4 Oct
ts = start + timedelta(minutes=secrets.randbelow(4 * 24 * 60 - 7 * 60))
probe["ts"] = ts.isoformat(timespec="seconds")
probe["user_id"] = f"u{secrets.randbelow(24) + 1:03d}"
rows = [json.loads(l) for l in open(LOG, encoding="utf-8") if l.strip()]
rows.append(probe)
rows.sort(key=lambda r: r["ts"])
open(LOG, "w", encoding="utf-8").write("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
json.dump({"planted_trace_id": probe["trace_id"], "ts": probe["ts"], "user_id": probe["user_id"],
           "position": next(i for i, r in enumerate(rows) if r["trace_id"] == probe["trace_id"]) + 1,
           "of": len(rows)}, open(SP + "/w11_drill_answer_key.json", "w"), indent=2)
print("planted. log now has", len(rows), "requests. answer key kept OUTSIDE the repo.")
