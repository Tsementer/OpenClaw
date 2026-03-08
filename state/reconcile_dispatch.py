#!/usr/bin/env python3
"""reconcile_dispatch.py — Vaatab ledger olekud, käivitab Kirjutaja/Toimetaja."""
import json
import os
import subprocess
import sys
import time

_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

from agent_utils import spawn_agent  # noqa: E402

SCRIPT_DIR = os.path.dirname(__file__)
APPEND_LEDGER = os.path.join(SCRIPT_DIR, "append_ledger.py")
NOTIFY_SCRIPT = os.path.join(SCRIPT_DIR, "slack_notify.py")
LEDGER = os.environ.get("OPENCLAW_LEDGER_PATH", "/data/.openclaw/state/ledger.jsonl")


def load_events():
    if not os.path.exists(LEDGER):
        return []
    events = []
    with open(LEDGER, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                events.append(obj)
    return events


def latest_by_thread(events):
    latest = {}
    for ev in events:
        tid = ev.get("threadId")
        if tid:
            latest[tid] = ev
    return latest


def history_index(events):
    idx = {}
    for ev in events:
        tid = ev.get("threadId")
        status = ev.get("status")
        if tid and status:
            idx.setdefault(tid, set()).add(status)
    return idx


def docs_links_of_thread(events):
    links = {}
    for ev in events:
        tid = ev.get("threadId")
        if not tid:
            continue
        dl = ev.get("docsLinks")
        if isinstance(dl, list) and dl:
            links[tid] = [x for x in dl if isinstance(x, str) and x.strip()]
    return links


def append_notified_event(source_event):
    payload = {
        "event": "NOTIFIED",
        "threadId": source_event.get("threadId", ""),
        "messageId": source_event.get("messageId", ""),
        "subject": source_event.get("subject", ""),
        "from": source_event.get("from", ""),
        "receivedAt": source_event.get("receivedAt", ""),
        "prescore": source_event.get("prescore"),
        "finalscore": source_event.get("finalscore"),
        "status": "NOTIFIED",
        "docsLinks": source_event.get("docsLinks") if isinstance(source_event.get("docsLinks"), list) else [],
        "lastError": None,
        "createdAt": time.time(),
        "updatedAt": time.time(),
    }
    env = os.environ.copy()
    env["OPENCLAW_LEDGER_PATH"] = LEDGER
    result = subprocess.run(
        [sys.executable, APPEND_LEDGER],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        env=env,
    )
    if result.returncode != 0:
        msg = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"append_ledger failed for NOTIFIED: {msg}")


def main():
    events = load_events()
    if not events:
        print("NOOP")
        return 0

    latest = latest_by_thread(events)
    hist = history_index(events)
    links = docs_links_of_thread(events)

    spawned = 0

    for tid, ev in latest.items():
        status = ev.get("status")
        finalscore = ev.get("finalscore")

        # TRIAGED → spawn Kirjutaja
        if status == "TRIAGED" and isinstance(finalscore, (int, float)) and finalscore >= 6:
            h = hist.get(tid, set())
            if not any(x in h for x in ("DRAFTED", "EDITED", "FAILED")):
                task = (
                    f"Koosta draft threadId={tid} messageId={ev.get('messageId', '')}. "
                    f"Loe e-kirja täiskeha ja kirjuta Delfi Ärilehe stiilis uudislugu. "
                    f"Kirjuta DRAFTED ledger event koos docsLinks."
                )
                if spawn_agent("kirjutaja", task, notify_script=NOTIFY_SCRIPT):
                    spawned += 1
                time.sleep(5)

        # DRAFTED → spawn Toimetaja
        if status == "DRAFTED":
            h = hist.get(tid, set())
            dl = links.get(tid, [])
            if dl and not any(x in h for x in ("EDITED", "FAILED")):
                task = (
                    f"Toimeta lugu threadId={tid} docsLink={dl[0]}. "
                    f"Kirjuta EDITED ledger event koos docsLinks."
                )
                if spawn_agent("toimetaja", task, notify_script=NOTIFY_SCRIPT):
                    spawned += 1
                time.sleep(5)

    # Teavitused
    notify_items = []
    for tid, ev in latest.items():
        status = ev.get("status")
        if status not in {"DRAFTED", "EDITED"}:
            continue
        if "NOTIFIED" in hist.get(tid, set()):
            continue
        notify_items.append(ev)

    if not notify_items and spawned == 0:
        print("NO_WORK")
        return 0

    # Append NOTIFIED events
    for ev in notify_items:
        try:
            append_notified_event(ev)
            print(f"NOTIFIED\t{ev.get('threadId')}")
        except Exception as e:
            print(f"NOTIFY_FAIL\t{e}", file=sys.stderr)

    print(f"DONE\tspawned={spawned}\tnotified={len(notify_items)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
