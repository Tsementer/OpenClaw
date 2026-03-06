#!/usr/bin/env python3
import sys, json, time

LEDGER="/data/.openclaw/state/ledger.jsonl"
raw=sys.stdin.read().strip()
if not raw:
    raise SystemExit("No JSON on stdin")

obj=json.loads(raw)
now=time.time()

if "staatus" in obj and "status" not in obj:
    obj["status"]=obj.pop("staatus")

obj.setdefault("event", obj.get("status","UNKNOWN"))
obj.setdefault("createdAt", now)
obj["updatedAt"]=now

with open(LEDGER,"a",encoding="utf-8") as f:
    f.write(json.dumps(obj, ensure_ascii=False) + "\n")

print("OK")
