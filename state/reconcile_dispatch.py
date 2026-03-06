#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time
from typing import Dict, List

SCRIPT_DIR = os.path.dirname(__file__)
APPEND_LEDGER = os.path.join(SCRIPT_DIR, "append_ledger.py")
LEDGER = os.environ.get("OPENCLAW_LEDGER_PATH", "/data/.openclaw/state/ledger.jsonl")


def load_events() -> List[dict]:
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


def latest_by_thread(events: List[dict]) -> Dict[str, dict]:
    latest = {}
    for ev in events:
        tid = ev.get("threadId")
        if not tid:
            continue
        latest[tid] = ev
    return latest


def history_index(events: List[dict]) -> Dict[str, set]:
    idx: Dict[str, set] = {}
    for ev in events:
        tid = ev.get("threadId")
        status = ev.get("status")
        if not tid or not status:
            continue
        idx.setdefault(tid, set()).add(status)
    return idx


def docs_links_of_thread(events: List[dict]) -> Dict[str, List[str]]:
    links: Dict[str, List[str]] = {}
    for ev in events:
        tid = ev.get("threadId")
        if not tid:
            continue
        dl = ev.get("docsLinks")
        if isinstance(dl, list) and dl:
            links[tid] = [x for x in dl if isinstance(x, str) and x.strip()]
    return links


def append_notified_event(source_event: dict) -> None:
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


def _quote_task_value(value: str) -> str:
    return value.replace("'", "\\'")


def main() -> int:
    events = load_events()
    if not events:
        print("NOOP")
        return 0

    latest = latest_by_thread(events)
    hist = history_index(events)
    links = docs_links_of_thread(events)

    for tid, ev in latest.items():
        status = ev.get("status")
        finalscore = ev.get("finalscore")

        if status == "TRIAGED" and isinstance(finalscore, int) and finalscore >= 6:
            h = hist.get(tid, set())
            if not any(x in h for x in ("DRAFTED", "EDITED", "FAILED")):
                task = f"Koosta draft threadId={tid} messageId={ev.get('messageId','')}. Kirjuta DRAFTED ledger event koos docsLinks."
                print("SPAWN\tkirjutaja\t" + _quote_task_value(task))

        if status == "DRAFTED":
            h = hist.get(tid, set())
            dl = links.get(tid, [])
            if dl and not any(x in h for x in ("EDITED", "FAILED")):
                task = f"Toimeta lugu threadId={tid} docsLink={dl[0]}. Kirjuta EDITED ledger event koos docsLinks."
                print("SPAWN\ttoimetaja\t" + _quote_task_value(task))

    notify_items = []
    for tid, ev in latest.items():
        status = ev.get("status")
        if status not in {"DRAFTED", "EDITED"}:
            continue
        if "NOTIFIED" in hist.get(tid, set()):
            continue
        notify_items.append(ev)

    if not notify_items:
        print("NO_SUMMARY")
        return 0

    notify_items.sort(key=lambda x: x.get("finalscore") or -1, reverse=True)
    lines = ["Uudiste kokkuvõte:"]
    for ev in notify_items[:10]:
        score = ev.get("finalscore")
        tid = ev.get("threadId", "?")
        subject = ev.get("subject", "")
        dl = ev.get("docsLinks") if isinstance(ev.get("docsLinks"), list) else []
        link_txt = f" | {dl[0]}" if dl else ""
        lines.append(f"- [{score}] {subject} (thread {tid}){link_txt}")

    print("SUMMARY\t" + "\\n".join(lines))

    for ev in notify_items:
        append_notified_event(ev)

    print(f"NOTIFIED_APPENDED\t{len(notify_items)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
