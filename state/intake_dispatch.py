#!/usr/bin/env python3
"""intake_dispatch.py — Loeb uued e-kirjad, käivitab Postiluure agendi."""
import os
import subprocess
import sys
import time

_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

from agent_utils import spawn_agent  # noqa: E402

SCRIPT_DIR = os.path.dirname(__file__)
INGEST_SCRIPT = os.path.join(SCRIPT_DIR, "ingest_unread.py")
NOTIFY_SCRIPT = os.path.join(SCRIPT_DIR, "slack_notify.py")


def _build_postiluure_task(thread_id, message_id, subject, from_, received_at):
    return (
        "Triagi threadId={threadId} messageId={messageId} "
        "subject={subject} from={from_} receivedAt={receivedAt}. "
        "Kirjuta tulemus /data/.openclaw/state/ledger.jsonl: "
        "staatus TRIAGED või SKIPPED või FAILED. "
        "Täiskeha too ainult siis, kui esmane hinne >=6."
    ).format(
        threadId=thread_id,
        messageId=message_id,
        subject=subject,
        from_=from_,
        receivedAt=received_at,
    )


def main():
    if not os.environ.get("GOG_KEYRING_PASSWORD"):
        print("ERROR: GOG_KEYRING_PASSWORD missing", file=sys.stderr)
        return 2

    result = subprocess.run([sys.executable, INGEST_SCRIPT], text=True, capture_output=True)
    if result.returncode != 0:
        err = (result.stderr or result.stdout).strip()
        print(f"ERROR: ingest_unread failed: {err}", file=sys.stderr)
        return 3

    output = (result.stdout or "").strip()
    if output in {"INBOX_EMPTY", "NO_NEW_AFTER_DEDUPE"}:
        print(output)
        return 0

    spawn_count = 0
    ok_count = 0
    for line in output.splitlines():
        if not line.startswith("NEW\t"):
            continue
        parts = line.split("\t", 5)
        if len(parts) != 6:
            continue
        _, thread_id, message_id, received_at, from_, subject = parts
        task = _build_postiluure_task(thread_id, message_id, subject, from_, received_at)
        spawn_count += 1

        if spawn_agent("postiluure", task, notify_script=NOTIFY_SCRIPT):
            ok_count += 1
        # Väike paus agentide vahel
        if spawn_count > 1:
            time.sleep(5)

    if spawn_count == 0:
        print("NO_NEW_AFTER_DEDUPE")
    else:
        print(f"SPAWNED\t{ok_count}/{spawn_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
