#!/usr/bin/env python3
"""Ledger schema valideerimine ja state transition kontroll.

Kõik ledger kirjutused peavad läbima selle mooduli validate_event() funktsiooni.
Ebavalidid eventid lükatakse tagasi ValueError-iga.
"""

from __future__ import annotations

import time
from typing import Any

# ----- Lubatud olekud -----
VALID_STATUSES = {"NEW", "TRIAGED", "DRAFTED", "EDITED", "NOTIFIED", "SKIPPED", "FAILED"}

# ----- Lubatud üleminekud -----
# None tähendab: see olek võib olla esimene (eelnevaid pole nõutud)
ALLOWED_TRANSITIONS: dict[str | None, set[str]] = {
    None: {"NEW"},
    "NEW": {"TRIAGED", "SKIPPED", "FAILED"},
    "TRIAGED": {"DRAFTED", "FAILED"},
    "DRAFTED": {"EDITED", "NOTIFIED", "FAILED"},
    "EDITED": {"NOTIFIED", "FAILED"},
    "NOTIFIED": set(),   # terminaalne olek
    "SKIPPED": set(),    # terminaalne olek
    "FAILED": {"NEW", "TRIAGED", "DRAFTED"},  # lubame retry
}

# ----- Kohustuslikud väljad iga event-tüübi jaoks -----
REQUIRED_FIELDS: dict[str, list[str]] = {
    "_all": ["event", "threadId", "messageId", "subject", "status", "createdAt", "updatedAt"],
    "NEW": ["from", "receivedAt"],
    "TRIAGED": ["from", "receivedAt", "prescore", "finalscore"],
    "DRAFTED": ["docsLinks"],
    "EDITED": ["docsLinks"],
    "NOTIFIED": [],
    "SKIPPED": ["finalscore"],
    "FAILED": ["lastError"],
}

# ----- Välja tüübid -----
FIELD_TYPES: dict[str, type | tuple[type, ...]] = {
    "threadId": str,
    "messageId": str,
    "subject": str,
    "status": str,
    "event": str,
    "createdAt": (int, float),
    "updatedAt": (int, float),
    "prescore": (int, float, type(None)),
    "finalscore": (int, float, type(None)),
    "docsLinks": list,
    "lastError": (str, type(None)),
}

# ----- Maksimumpikkused -----
MAX_LENGTHS: dict[str, int] = {
    "threadId": 256,
    "messageId": 256,
    "subject": 512,
    "from": 512,
    "lastError": 2000,
}


def validate_event(obj: dict[str, Any], previous_status: str | None = None) -> None:
    """Valideeri ledger event.

    Args:
        obj: Event dict, mida soovitakse ledgerisse kirjutada.
        previous_status: Selle threadId viimane teadaolev olek (None, kui pole).

    Raises:
        ValueError: Kui validatsioon ebaõnnestub. Veateade kirjeldab probleemi.
    """
    if not isinstance(obj, dict):
        raise ValueError(f"Event peab olema dict, sain: {type(obj)}")

    status = obj.get("status")

    # Olek peab olema kehtiv
    if status not in VALID_STATUSES:
        raise ValueError(f"Kehtetu status: {status!r}. Lubatud: {sorted(VALID_STATUSES)}")

    # Üleminek peab olema lubatud
    allowed = ALLOWED_TRANSITIONS.get(previous_status)
    if allowed is not None and status not in allowed:
        raise ValueError(
            f"Keelatud üleminek {previous_status!r} -> {status!r}. "
            f"Lubatud: {sorted(allowed) if allowed else '(terminaalne olek)'}"
        )

    # Kohustuslikud väljad
    required = list(REQUIRED_FIELDS.get("_all", []))
    required += REQUIRED_FIELDS.get(status, [])
    missing = [f for f in required if f not in obj]
    if missing:
        raise ValueError(f"Puuduvad kohustuslikud väljad status={status!r}: {missing}")

    # Tüübikontroll
    for field, expected_type in FIELD_TYPES.items():
        if field in obj:
            val = obj[field]
            if not isinstance(val, expected_type):
                raise ValueError(
                    f"Väli {field!r}: oodatud tüüp {expected_type}, sain {type(val)} (väärtus: {val!r})"
                )

    # Pikkuskontroll
    for field, max_len in MAX_LENGTHS.items():
        val = obj.get(field)
        if isinstance(val, str) and len(val) > max_len:
            raise ValueError(
                f"Väli {field!r} on liiga pikk: {len(val)} > {max_len}"
            )

    # threadId ei tohi olla tühi string
    if not obj.get("threadId", "").strip():
        raise ValueError("threadId ei tohi olla tühi")

    # docsLinks elemendid peavad olema stringid
    if "docsLinks" in obj:
        for i, link in enumerate(obj["docsLinks"]):
            if not isinstance(link, str):
                raise ValueError(f"docsLinks[{i}] peab olema string, sain: {type(link)}")

    # Ajatemplid peavad olema mõistlikud (> 2020-01-01, < 2100-01-01)
    for ts_field in ("createdAt", "updatedAt"):
        val = obj.get(ts_field)
        if val is not None:
            if val < 1577836800 or val > 4102444800:
                raise ValueError(f"Väli {ts_field!r} on ebamõistlik timestamp: {val}")


def make_base_event(status: str, thread_id: str, message_id: str, subject: str) -> dict[str, Any]:
    """Loo põhi-event kohustuslike väljadega täidetuna."""
    now = time.time()
    return {
        "event": status,
        "status": status,
        "threadId": thread_id,
        "messageId": message_id,
        "subject": subject,
        "from": "",
        "receivedAt": "",
        "prescore": None,
        "finalscore": None,
        "docsLinks": [],
        "lastError": None,
        "createdAt": now,
        "updatedAt": now,
    }
