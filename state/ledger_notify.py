#!/usr/bin/env python3
"""Jälgib ledger.jsonl uusi kirjeid ja saadab Slack teavitused."""

import json, os, sys, subprocess

LEDGER_PATH = "/root/.openclaw/state/ledger.jsonl"
CURSOR_PATH = "/root/.openclaw/state/.ledger_notify_cursor"
NOTIFY_SCRIPT = "/root/.openclaw/state/slack_notify.py"


def read_cursor():
    if os.path.exists(CURSOR_PATH):
        with open(CURSOR_PATH) as f:
            try: return int(f.read().strip())
            except ValueError: return 0
    return 0


def write_cursor(n):
    with open(CURSOR_PATH, "w") as f:
        f.write(str(n))


def read_all_entries():
    """Loe kogu ledger."""
    entries = []
    if not os.path.exists(LEDGER_PATH):
        return entries
    with open(LEDGER_PATH) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try: entries.append(json.loads(line))
            except json.JSONDecodeError: continue
    return entries


def find_triaged_for_thread(all_entries, thread_id):
    """Otsi TRIAGED kirje sama threadId-ga — sealt saame subject, from jne."""
    for entry in reversed(all_entries):
        if entry.get("threadId") == thread_id and entry.get("status") == "TRIAGED":
            return entry
    return None


def enrich_entry(entry, all_entries):
    """Täida puuduvad väljad eelmistest kirjetest."""
    tid = entry.get("threadId")
    if not tid:
        # threadId puudub — otsi docsLinks järgi
        for prev in reversed(all_entries):
            if prev.get("status") == "TRIAGED":
                # Kui see on ainus TRIAGED, kasuta seda
                tid = prev.get("threadId")
                break

    if not entry.get("subject") and tid:
        triaged = find_triaged_for_thread(all_entries, tid)
        if triaged:
            entry.setdefault("subject", triaged.get("subject", "?"))
            entry.setdefault("from", triaged.get("from", "?"))
            entry.setdefault("threadId", tid)
            entry.setdefault("score", triaged.get("finalscore", triaged.get("prescore")))
            entry.setdefault("sender", triaged.get("from", "?"))
    return entry


def notify(entry):
    status = entry.get("status", "")
    subject = entry.get("subject", "?")
    sender = entry.get("from", entry.get("sender", "?"))
    score = entry.get("score", entry.get("finalscore", entry.get("newsworthiness", "?")))
    docs_link = ""
    for key in ("docsLinks", "docsLink", "googleDocsUrl"):
        val = entry.get(key)
        if val:
            docs_link = val[0] if isinstance(val, list) else val
            break

    cmd = [sys.executable, NOTIFY_SCRIPT]
    if status == "TRIAGED":
        cmd += ["--triaged", subject, "--score", str(score), "--from-addr", sender]
    elif status == "DRAFTED":
        cmd += ["--drafted", subject]
        if docs_link: cmd += ["--docs-link", docs_link]
    elif status == "EDITED":
        cmd += ["--drafted", f"[TOIMETATUD] {subject}"]
        if docs_link: cmd += ["--docs-link", docs_link]
    elif status == "FAILED":
        cmd += ["--error", f"{subject}: {entry.get('error', entry.get('reason', 'Tundmatu viga'))}"]
    elif status == "SKIPPED":
        return
    else:
        return

    try: subprocess.run(cmd, check=True, timeout=15)
    except Exception as e: print(f"Teavitus ebaõnnestus: {e}", file=sys.stderr)


def main():
    cursor = read_cursor()
    all_entries = read_all_entries()

    if cursor >= len(all_entries):
        return

    new_entries = all_entries[cursor:]
    print(f"Uusi kirjeid: {len(new_entries)} (cursor {cursor} → {len(all_entries)})")

    for entry in new_entries:
        entry = enrich_entry(entry, all_entries)
        notify(entry)

    write_cursor(len(all_entries))


if __name__ == "__main__":
    main()
