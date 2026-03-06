#!/usr/bin/env python3
import os, sys, json, time

LEDGER="/data/.openclaw/state/ledger.jsonl"
MAX_STDIN_BYTES=100_000
ALLOWED_STATUS={"NEW","TRIAGED","DRAFTED","EDITED","NOTIFIED","SKIPPED","FAILED"}

raw=sys.stdin.read(MAX_STDIN_BYTES + 1).strip()
if not raw:
    raise SystemExit("No JSON on stdin")
if len(raw) > MAX_STDIN_BYTES:
    raise SystemExit("Input JSON too large")

obj=json.loads(raw)
now=time.time()

if "staatus" in obj and "status" not in obj:
    obj["status"]=obj.pop("staatus")

status=obj.get("status")
if status and status not in ALLOWED_STATUS:
    raise SystemExit(f"Invalid status: {status}")

obj.setdefault("event", obj.get("status","UNKNOWN"))
obj.setdefault("createdAt", now)
obj["updatedAt"]=now

os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
flags=os.O_WRONLY | os.O_APPEND | os.O_CREAT
fd=os.open(LEDGER, flags, 0o600)
with os.fdopen(fd, "a", encoding="utf-8") as f:
    f.write(json.dumps(obj, ensure_ascii=False) + "\n")

print("OK")
