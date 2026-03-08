#!/usr/bin/env python3
"""ingest_unread.py — Laeb Gmail inbox lugemata kirjad ja lisab NEW evente ledgerisse.

Idempotentsus:
  - Duplikaadi võti on (threadId, messageId) kombinatsioon.
  - Kui sama threadId on juba terminaalses olekus (TRIAGED/DRAFTED/EDITED/NOTIFIED/SKIPPED),
    jäetakse see vahele.
  - Kui sama (threadId, messageId) paar on juba ledgeris NEW-na, jäetakse vahele.
  - Ledger kirjutamine toimub enne UNREAD sildi eemaldamist, et osalise rike korral
    saaks uuesti käivitada.
"""
import os
import sys
import subprocess
import json
import time

_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

GOG = "/data/bin/gog"
LEDGER = os.environ.get("OPENCLAW_LEDGER_PATH", "/data/.openclaw/state/ledger.jsonl")
QUERY = "is:unread in:inbox"

# Olekud, mille puhul pole vaja uuesti triaaži
DONE_STATUSES = {"TRIAGED", "DRAFTED", "EDITED", "NOTIFIED", "SKIPPED"}


def run(cmd):
    env = os.environ.copy()
    if not env.get("GOG_KEYRING_PASSWORD"):
        print("ERROR: GOG_KEYRING_PASSWORD missing", file=sys.stderr)
        sys.exit(2)
    return subprocess.run(cmd, text=True, capture_output=True, env=env)


def load_seen_state() -> tuple[dict[str, str], set[tuple[str, str]]]:
    """Loe ledger ja tagasta:
    - latest_status: threadId -> viimane olek
    - seen_pairs: hulk (threadId, messageId) paare, mis on juba NEW-na lisatud
    """
    latest_status: dict[str, str] = {}
    seen_pairs: set[tuple[str, str]] = set()

    if not os.path.exists(LEDGER):
        return latest_status, seen_pairs

    with open(LEDGER, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            tid = obj.get("threadId")
            mid = obj.get("messageId")
            status = obj.get("status", "")
            if tid:
                latest_status[tid] = status
            if tid and mid:
                seen_pairs.add((tid, mid))

    return latest_status, seen_pairs


def parse_plain(out: str) -> list[tuple[str, str, str, str, str]]:
    """Sõelub gog gmail messages search --plain väljundit.

    Tagastab: list of (thread_id, msg_id, date, from_, subject)
    """
    out = out.strip()
    if not out or out.startswith("No results"):
        return []
    lines = out.splitlines()
    if lines and lines[0].startswith("ID"):
        lines = lines[1:]
    rows = []
    for line in lines:
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        msg_id = parts[0].strip()
        thread_id = parts[1].strip()
        date = parts[2].strip()
        from_ = parts[3].strip()
        subject = parts[4].strip()
        rows.append((thread_id, msg_id, date, from_, subject))
    return rows


def append_event(ev: dict) -> None:
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")


def main():
    r = run([GOG, "gmail", "messages", "search", QUERY, "--plain"])
    if r.returncode != 0:
        print("ERROR: search failed:", (r.stderr or r.stdout).strip(), file=sys.stderr)
        sys.exit(3)

    rows = parse_plain(r.stdout)
    if not rows:
        print("INBOX_EMPTY")
        return

    latest_status, seen_pairs = load_seen_state()
    now = time.time()

    new_items = []
    for thread_id, msg_id, date, from_, subject in rows:
        # Skip: terminaalses olekus thread
        if latest_status.get(thread_id) in DONE_STATUSES:
            continue

        # Skip: täpne (threadId, messageId) paar on juba lisatud (idempotentsus)
        if (thread_id, msg_id) in seen_pairs:
            continue

        ev = {
            "event": "NEW",
            "threadId": thread_id,
            "messageId": msg_id,
            "subject": subject,
            "from": from_,
            "receivedAt": date,
            "prescore": None,
            "finalscore": None,
            "status": "NEW",
            "docsLinks": [],
            "lastError": None,
            "createdAt": now,
            "updatedAt": now,
        }

        # Kirjuta ledgerisse ENNE UNREAD eemaldamist — osalise rike kaitse
        append_event(ev)
        new_items.append((thread_id, msg_id, date, from_, subject))

        # Märgi thread loetuks
        run([GOG, "gmail", "labels", "modify", thread_id, "--remove", "UNREAD"])

    if not new_items:
        print("NO_NEW_AFTER_DEDUPE")
        return

    for thread_id, msg_id, date, from_, subject in new_items:
        print(f"NEW\t{thread_id}\t{msg_id}\t{date}\t{from_}\t{subject}")
    print(f"TOTAL_NEW={len(new_items)}")


if __name__ == "__main__":
    main()
