#!/usr/bin/env python3
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(__file__)
INGEST_SCRIPT = os.path.join(SCRIPT_DIR, "ingest_unread.py")


def _quote_task_value(value: str) -> str:
    return value.replace("'", "\\'")


def _build_postiluure_task(thread_id: str, message_id: str, subject: str, from_: str, received_at: str) -> str:
    return (
        "Triagi threadId={threadId} messageId={messageId} subject={subject} from={from_} receivedAt={receivedAt}. "
        "Kirjuta tulemus /data/.openclaw/state/ledger.jsonl: staatus TRIAGED või SKIPPED või FAILED. "
        "Täiskeha too ainult siis, kui esmane hinne >=6."
    ).format(
        threadId=thread_id,
        messageId=message_id,
        subject=subject,
        from_=from_,
        receivedAt=received_at,
    )


def main() -> int:
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
    for line in output.splitlines():
        if not line.startswith("NEW\t"):
            continue
        parts = line.split("\t", 5)
        if len(parts) != 6:
            continue
        _, thread_id, message_id, received_at, from_, subject = parts
        task = _build_postiluure_task(thread_id, message_id, subject, from_, received_at)
        print(
            "SPAWN\tpostiluure\t"
            + _quote_task_value(task)
        )
        spawn_count += 1

    if spawn_count == 0:
        print("NO_NEW_AFTER_DEDUPE")
        return 0

    print(f"QUEUED_OK\t{spawn_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
