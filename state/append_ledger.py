#!/usr/bin/env python3
"""Lisab event ledger.jsonl faili.

Lugemisviis: python3 append_ledger.py < event.json
Väljund: "OK" stdout-i või veateade stderr-i + exit code 1.

Valideerib sisendi ledger_schema.py kaudu enne kirjutamist.
Ledger path: OPENCLAW_LEDGER_PATH env muutuja või vaikimisi /data/.openclaw/state/ledger.jsonl.
"""
import json
import os
import sys
import time

# Lisame script-kataloogi sys.path'i, et leia ledger_schema.py
_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

from ledger_schema import validate_event, VALID_STATUSES  # noqa: E402

LEDGER = os.environ.get("OPENCLAW_LEDGER_PATH", "/data/.openclaw/state/ledger.jsonl")


def _load_latest_status() -> dict[str, str | None]:
    """Tagasta threadId -> viimane status (None kui pole)."""
    latest: dict[str, str | None] = {}
    if not os.path.exists(LEDGER):
        return latest
    with open(LEDGER, "r", encoding="utf-8") as f:
        for raw_line in f:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                ev = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            tid = ev.get("threadId")
            if tid:
                latest[tid] = ev.get("status")
    return latest


def main() -> int:
    raw = sys.stdin.read().strip()
    if not raw:
        print("VIGA: stdin on tühi, oodati JSON-i", file=sys.stderr)
        return 1

    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"VIGA: vigane JSON — {exc}", file=sys.stderr)
        return 1

    if not isinstance(obj, dict):
        print("VIGA: JSON peab olema objekt", file=sys.stderr)
        return 1

    now = time.time()

    # Tagasiühilduvus: "staatus" -> "status"
    if "staatus" in obj and "status" not in obj:
        obj["status"] = obj.pop("staatus")

    obj.setdefault("event", obj.get("status", "UNKNOWN"))
    obj.setdefault("createdAt", now)
    obj["updatedAt"] = now

    # Lae eelmine olek state transition valideerimiseks
    thread_id = obj.get("threadId")
    previous_status: str | None = None
    if thread_id:
        latest = _load_latest_status()
        previous_status = latest.get(thread_id)

    # Schema ja transition valideerimine
    try:
        validate_event(obj, previous_status=previous_status)
    except ValueError as exc:
        print(f"VIGA: schema/transition validatsioon ebaõnnestus — {exc}", file=sys.stderr)
        return 1

    # Kirjuta ledgerisse
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
