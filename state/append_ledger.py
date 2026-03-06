#!/usr/bin/env python3
import json
import os
import sys
import time

LEDGER = os.environ.get("OPENCLAW_LEDGER_PATH", "/data/.openclaw/state/ledger.jsonl")
MAX_STDIN_BYTES = 100_000
ALLOWED_STATUS = {"NEW", "TRIAGED", "DRAFTED", "EDITED", "NOTIFIED", "SKIPPED", "FAILED"}

MAX_LEN = {
    "threadId": 256,
    "messageId": 256,
    "subject": 500,
    "from": 500,
    "receivedAt": 128,
    "lastError": 2000,
    "docLink": 2000,
}
MAX_DOC_LINKS = 20

REQUIRED_FIELDS = {
    "threadId",
    "messageId",
    "subject",
    "from",
    "receivedAt",
    "prescore",
    "finalscore",
    "status",
    "docsLinks",
    "lastError",
    "createdAt",
    "updatedAt",
}


def fail(message):
    raise SystemExit(message)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_text_field(obj, field, allow_empty=False):
    value = obj.get(field)
    if not isinstance(value, str):
        fail(f"Invalid type for {field}: expected string")
    if len(value) > MAX_LEN[field]:
        fail(f"{field} too long: max {MAX_LEN[field]}")
    if not value.strip() and not allow_empty:
        fail(f"{field} must be non-empty")
    if any(ch in value for ch in ("\n", "\r", "\t")):
        fail(f"{field} contains forbidden control characters")


def _validate_score(obj, field):
    value = obj.get(field)
    if value is None:
        return
    if not isinstance(value, int):
        fail(f"Invalid type for {field}: expected integer or null")
    if value < 0 or value > 10:
        fail(f"Invalid value for {field}: expected 0..10")


def validate_event(obj):
    if not isinstance(obj, dict):
        fail("Input JSON must be an object")

    missing = sorted(REQUIRED_FIELDS - set(obj.keys()))
    if missing:
        fail(f"Missing required fields: {', '.join(missing)}")

    status = obj.get("status")
    if not isinstance(status, str) or status not in ALLOWED_STATUS:
        fail(f"Invalid status: {status}")

    _validate_text_field(obj, "threadId")
    _validate_text_field(obj, "messageId")
    _validate_text_field(obj, "subject")
    _validate_text_field(obj, "from")
    _validate_text_field(obj, "receivedAt")

    _validate_score(obj, "prescore")
    _validate_score(obj, "finalscore")

    docs_links = obj.get("docsLinks")
    if not isinstance(docs_links, list):
        fail("Invalid type for docsLinks: expected array")
    if len(docs_links) > MAX_DOC_LINKS:
        fail(f"docsLinks too long: max {MAX_DOC_LINKS} items")
    for i, link in enumerate(docs_links):
        if not isinstance(link, str):
            fail(f"Invalid type for docsLinks[{i}]: expected string")
        if len(link) > MAX_LEN["docLink"]:
            fail(f"docsLinks[{i}] too long: max {MAX_LEN['docLink']}")
        if not link.strip():
            fail(f"docsLinks[{i}] must be non-empty")
        if any(ch in link for ch in ("\n", "\r", "\t")):
            fail(f"docsLinks[{i}] contains forbidden control characters")

    last_error = obj.get("lastError")
    if last_error is not None:
        if not isinstance(last_error, str):
            fail("Invalid type for lastError: expected string or null")
        if len(last_error) > MAX_LEN["lastError"]:
            fail(f"lastError too long: max {MAX_LEN['lastError']}")

    for field in ("createdAt", "updatedAt"):
        if not _is_number(obj.get(field)):
            fail(f"Invalid type for {field}: expected number")

    event = obj.get("event")
    if event is not None and not isinstance(event, str):
        fail("Invalid type for event: expected string")


def main():
    raw = sys.stdin.read(MAX_STDIN_BYTES + 1).strip()
    if not raw:
        fail("No JSON on stdin")
    if len(raw) > MAX_STDIN_BYTES:
        fail("Input JSON too large")

    obj = json.loads(raw)

    if "staatus" in obj and "status" not in obj:
        obj["status"] = obj.pop("staatus")

    now = time.time()
    obj.setdefault("event", obj.get("status", "UNKNOWN"))
    obj.setdefault("createdAt", now)
    obj["updatedAt"] = now

    validate_event(obj)

    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
    fd = os.open(LEDGER, flags, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    print("OK")


if __name__ == "__main__":
    main()
