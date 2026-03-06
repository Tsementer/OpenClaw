#!/usr/bin/env python3
"""intake_dispatch.py — Loeb uued e-kirjad, käivitab Postiluure agendi."""
import os
import subprocess
import sys
import time

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


def spawn_agent(agent_id, task_message):
    """Käivita openclaw agent päriselt."""
    cmd = [
        "openclaw", "agent",
        "--agent", agent_id,
        "--message", task_message,
        "--timeout", "300",
    ]
    print(f"SPAWN\t{agent_id}\t{task_message[:80]}...")
    try:
        result = subprocess.run(
            cmd, text=True, capture_output=True, timeout=320,
            env={**os.environ, "PATH": "/usr/local/bin:/usr/bin:/bin:" + os.environ.get("PATH", "")},
        )
        if result.returncode == 0:
            print(f"SPAWN_OK\t{agent_id}")
            if result.stdout:
                print(result.stdout.strip())
            return True
        else:
            err = (result.stderr or result.stdout or "").strip()
            print(f"SPAWN_FAIL\t{agent_id}\t{err[:200]}", file=sys.stderr)
            # Slack viga
            try:
                subprocess.run(
                    [sys.executable, NOTIFY_SCRIPT, "--error",
                     f"{agent_id} spawn ebaõnnestus: {err[:200]}"],
                    timeout=15, capture_output=True,
                )
            except Exception:
                pass
            return False
    except subprocess.TimeoutExpired:
        print(f"SPAWN_TIMEOUT\t{agent_id}", file=sys.stderr)
        return False


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

        if spawn_agent("postiluure", task):
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
