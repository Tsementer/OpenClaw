#!/usr/bin/env python3
"""Päeva kokkuvõte Slacki."""

import json, os, sys, subprocess
from datetime import date

LEDGER_PATH = "/root/.openclaw/state/ledger.jsonl"
NOTIFY_SCRIPT = "/root/.openclaw/state/slack_notify.py"

def main():
    today = date.today().isoformat()
    stats = {"triaged": 0, "drafted": 0, "edited": 0, "skipped": 0, "failed": 0}
    subjects = []

    if os.path.exists(LEDGER_PATH):
        with open(LEDGER_PATH) as f:
            for line in f:
                line = line.strip()
                if not line: continue
                try: entry = json.loads(line)
                except: continue
                ts = entry.get("timestamp", entry.get("ts", ""))
                if not ts.startswith(today): continue
                s = entry.get("status", "").upper()
                if s in stats: stats[s] += 1
                if s == "DRAFTED": subjects.append(entry.get("subject", "?"))

    total = sum(stats.values())
    if total == 0:
        subprocess.run([sys.executable, NOTIFY_SCRIPT, f"📊 Päeva kokkuvõte ({date.today().strftime('%d.%m.%Y')}): täna kirju ei laekunud."], check=True, timeout=15)
        return

    lines = [
        f"📊 *Päeva kokkuvõte — {date.today().strftime('%d.%m.%Y')}*", "",
        f"• Triaaž: *{stats['triaged']}* kirja",
        f"• Draftid: *{stats['drafted']}* lugu",
        f"• Toimetatud: *{stats['edited']}*",
        f"• Vahele jäetud: *{stats['skipped']}*",
        f"• Vead: *{stats['failed']}*",
    ]
    if subjects:
        lines += ["", "*Tänased lood:*"] + [f"  → {s}" for s in subjects]

    subprocess.run([sys.executable, NOTIFY_SCRIPT, "\n".join(lines)], check=True, timeout=15)

if __name__ == "__main__":
    main()
