#!/usr/bin/env python3
"""Validated append-only ledger writer for OpenClaw.

Best-practice goals:
- strict schema enforcement
- transition safety
- idempotent writes
- lock-protected append in concurrent cron/agent runs
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

try:
    import fcntl  # Unix only; environment here is Linux
except ImportError:  # pragma: no cover
    fcntl = None

LEDGER = os.environ.get("OPENCLAW_LEDGER_PATH", "/data/.openclaw/state/ledger.jsonl")

TERMINAL_STATUSES = {"NOTIFIED", "SKIPPED", "FAILED"}
ALLOWED_STATUSES = {
    "NEW",
    "TRIAGED",
    "DRAFTED",
    "EDITED",
    "NOTIFIED",
    "SKIPPED",
    "FAILED",
}

ALLOWED_TRANSITIONS = {
    None: {"NEW"},
    "NEW": {"TRIAGED", "SKIPPED", "FAILED"},
    "TRIAGED": {"DRAFTED", "FAILED"},
    "DRAFTED": {"EDITED", "NOTIFIED", "FAILED"},
    "EDITED": {"NOTIFIED", "FAILED"},
    "NOTIFIED": {"NOTIFIED"},
    "SKIPPED": {"SKIPPED"},
    "FAILED": {"FAILED"},
}

MAX_DOC_LINKS = 20
MAX_FIELD = {
    "threadId": 256,
    "messageId": 256,
    "subject": 500,
    "from": 500,
    "receivedAt": 128,
    "lastError": 2000,
}

FORBIDDEN_CONTROL = {"\t", "\n", "\r"}


class ValidationError(ValueError):
    """Raised when payload fails schema / semantic checks."""


def _reject_control_chars(field_name: str, value: str) -> None:
    if any(ch in value for ch in FORBIDDEN_CONTROL):
        raise ValidationError(f"Field '{field_name}' contains forbidden tab/newline/carriage-return")


def _validate_string_field(payload: dict[str, Any], name: str, max_len: int, min_len: int = 1) -> str:
    value = payload.get(name)
    if not isinstance(value, str):
        raise ValidationError(f"Field '{name}' must be a string")
    if not (min_len <= len(value) <= max_len):
        raise ValidationError(f"Field '{name}' length must be {min_len}..{max_len}")
    _reject_control_chars(name, value)
    return value


def _validate_score(payload: dict[str, Any], name: str) -> int | None:
    value = payload.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"Field '{name}' must be integer 0..10 or null")
    if not (0 <= value <= 10):
        raise ValidationError(f"Field '{name}' must be in range 0..10")
    return value


def _normalize_and_validate(payload: dict[str, Any], now: float) -> dict[str, Any]:
    if "staatus" in payload and "status" not in payload:
        payload["status"] = payload.pop("staatus")

    status = payload.get("status")
    if status not in ALLOWED_STATUSES:
        raise ValidationError(f"Invalid status '{status}'")

    payload["event"] = payload.get("event") or status
    if payload["event"] != status:
        raise ValidationError("Field 'event' must match 'status'")

    _validate_string_field(payload, "threadId", MAX_FIELD["threadId"])
    _validate_string_field(payload, "messageId", MAX_FIELD["messageId"])
    _validate_string_field(payload, "subject", MAX_FIELD["subject"])
    _validate_string_field(payload, "from", MAX_FIELD["from"])
    _validate_string_field(payload, "receivedAt", MAX_FIELD["receivedAt"])

    _validate_score(payload, "prescore")
    _validate_score(payload, "finalscore")

    docs_links = payload.get("docsLinks")
    if not isinstance(docs_links, list):
        raise ValidationError("Field 'docsLinks' must be an array")
    if len(docs_links) > MAX_DOC_LINKS:
        raise ValidationError(f"Field 'docsLinks' must have at most {MAX_DOC_LINKS} items")
    cleaned_links = []
    for idx, item in enumerate(docs_links):
        if not isinstance(item, str):
            raise ValidationError(f"docsLinks[{idx}] must be a string")
        if not (1 <= len(item) <= 2000):
            raise ValidationError(f"docsLinks[{idx}] length must be 1..2000")
        _reject_control_chars(f"docsLinks[{idx}]", item)
        cleaned_links.append(item)
    payload["docsLinks"] = cleaned_links

    last_error = payload.get("lastError")
    if last_error is not None:
        if not isinstance(last_error, str):
            raise ValidationError("Field 'lastError' must be string or null")
        if len(last_error) > MAX_FIELD["lastError"]:
            raise ValidationError("Field 'lastError' max length is 2000")
        _reject_control_chars("lastError", last_error)

    created_at = payload.get("createdAt")
    if created_at is None:
        created_at = now
    if isinstance(created_at, bool) or not isinstance(created_at, (int, float)):
        raise ValidationError("Field 'createdAt' must be a number")

    payload["createdAt"] = float(created_at)
    payload["updatedAt"] = float(now)

    idem = payload.get("idempotencyKey")
    if idem is None:
        idem = f"{payload['threadId']}::{payload['messageId']}::{status}"
    if not isinstance(idem, str) or not (1 <= len(idem) <= 512):
        raise ValidationError("Field 'idempotencyKey' must be string length 1..512")
    _reject_control_chars("idempotencyKey", idem)
    payload["idempotencyKey"] = idem

    return payload


def _canonical_for_idempotency(obj: dict[str, Any]) -> dict[str, Any]:
    copy = dict(obj)
    copy.pop("createdAt", None)
    copy.pop("updatedAt", None)
    return copy


def _load_existing_locked(file_obj) -> list[dict[str, Any]]:
    file_obj.seek(0)
    events: list[dict[str, Any]] = []
    for line in file_obj:
        raw = line.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            events.append(obj)
    return events


def _latest_status(events: list[dict[str, Any]], thread_id: str) -> str | None:
    for ev in reversed(events):
        if ev.get("threadId") == thread_id:
            return ev.get("status")
    return None


def _find_by_idempotency(events: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    for ev in reversed(events):
        if ev.get("idempotencyKey") == key:
            return ev
    return None


def _validate_transition(prev_status: str | None, next_status: str) -> None:
    allowed = ALLOWED_TRANSITIONS.get(prev_status, set())
    if next_status not in allowed:
        raise ValidationError(f"Illegal transition: {prev_status!r} -> {next_status!r}")


def _append_line_locked(file_obj, payload: dict[str, Any]) -> None:
    file_obj.seek(0, os.SEEK_END)
    file_obj.write(json.dumps(payload, ensure_ascii=False) + "\n")
    file_obj.flush()
    os.fsync(file_obj.fileno())


def main() -> int:
    raw = sys.stdin.read().strip()
    if not raw:
        print("ERROR: No JSON on stdin", file=sys.stderr)
        return 2

    try:
        incoming = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"ERROR: Invalid JSON: {exc}", file=sys.stderr)
        return 2

    if not isinstance(incoming, dict):
        print("ERROR: Root JSON must be an object", file=sys.stderr)
        return 2

    now = time.time()
    try:
        normalized = _normalize_and_validate(incoming, now)
    except ValidationError as exc:
        print(f"ERROR: Validation failed: {exc}", file=sys.stderr)
        return 2

    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, "a+", encoding="utf-8") as f:
        if fcntl is not None:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            events = _load_existing_locked(f)

            existing = _find_by_idempotency(events, normalized["idempotencyKey"])
            if existing is not None:
                if _canonical_for_idempotency(existing) == _canonical_for_idempotency(normalized):
                    print("IDEMPOTENT_OK")
                    return 0
                print("ERROR: Idempotency key conflict", file=sys.stderr)
                return 2

            previous = _latest_status(events, normalized["threadId"])
            try:
                _validate_transition(previous, normalized["status"])
            except ValidationError as exc:
                print(f"ERROR: Validation failed: {exc}", file=sys.stderr)
                return 2

            _append_line_locked(f, normalized)
            print("OK")
            return 0
        finally:
            if fcntl is not None:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)


if __name__ == "__main__":
    raise SystemExit(main())
