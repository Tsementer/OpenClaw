#!/usr/bin/env python3
"""Päeva kokkuvõte Slacki.

Loeb ledger.jsonl-ist tänase päeva eventid ja saadab Slacki statistika.
Ledger path: OPENCLAW_LEDGER_PATH env muutuja või vaikimisi /data/.openclaw/state/ledger.jsonl.
"""
import json
import os
import subprocess
import sys
from datetime import date, datetime

_DIR = os.path.dirname(os.path.abspath(__file__))

LEDGER_PATH = os.environ.get(
    "OPENCLAW_LEDGER_PATH",
    "/data/.openclaw/state/ledger.jsonl",
)
NOTIFY_SCRIPT = os.path.join(_DIR, "slack_notify.py")


def _parse_entry_date(entry: dict) -> str | None:
    """Tagasta ISO-kuupäev (YYYY-MM-DD) ledger kirjest.

    Proovib järjekorras: updatedAt (unix), createdAt (unix), receivedAt (string).
    """
    for ts_field in ("updatedAt", "createdAt"):
        val = entry.get(ts_field)
        if isinstance(val, (int, float)) and val > 0:
            try:
                return datetime.fromtimestamp(val).date().isoformat()
            except (OSError, OverflowError, ValueError):
                continue

    # receivedAt on string — proovime levinumaid formaate
    received = entry.get("receivedAt", "")
    if isinstance(received, str) and received:
        for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%d"):
            try:
                return datetime.strptime(received[:25], fmt).date().isoformat()
            except ValueError:
                continue

    return None


def main():
    today = date.today().isoformat()
    stats = {"triaged": 0, "drafted": 0, "edited": 0, "skipped": 0, "failed": 0}
    subjects = []

    if os.path.exists(LEDGER_PATH):
        with open(LEDGER_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if _parse_entry_date(entry) != today:
                    continue

                s = entry.get("status", "").lower()
                if s in stats:
                    stats[s] += 1
                if s == "drafted":
                    subjects.append(entry.get("subject", "?"))

    total = sum(stats.values())
    formatted_date = date.today().strftime("%d.%m.%Y")

    if total == 0:
        msg = f"📊 Päeva kokkuvõte ({formatted_date}): täna kirju ei laekunud."
        subprocess.run([sys.executable, NOTIFY_SCRIPT, msg], check=True, timeout=15)
        return

    lines = [
        f"📊 *Päeva kokkuvõte — {formatted_date}*", "",
        f"• Triaaž: *{stats['triaged']}* kirja",
        f"• Draftid: *{stats['drafted']}* lugu",
        f"• Toimetatud: *{stats['edited']}*",
        f"• Vahele jäetud: *{stats['skipped']}*",
        f"• Vead: *{stats['failed']}*",
    ]
    if subjects:
        lines += ["", "*Tänased lood:*"] + [f"  \u2192 {s}" for s in subjects]

    subprocess.run([sys.executable, NOTIFY_SCRIPT, "\n".join(lines)], check=True, timeout=15)


if __name__ == "__main__":
    main()
