#!/usr/bin/env python3
"""Ühised utiliidid OpenClaw pipeline agentide käivitamiseks.

Importimisel kasutatav: from agent_utils import spawn_agent
"""
from __future__ import annotations

import os
import subprocess
import sys
import time


def spawn_agent(
    agent_id: str,
    task_message: str,
    notify_script: str | None = None,
    timeout: int = 300,
) -> bool:
    """Käivita openclaw agent ja tagasta True, kui õnnestus.

    Args:
        agent_id: Agendi identifikaator (nt 'postiluure', 'kirjutaja').
        task_message: Agendile saadetav ülesanne.
        notify_script: Tee slack_notify.py-le. Kui None, ei saadeta Slacki teavitust veal.
        timeout: subprocess timeout sekundites. Protsessile antakse 20s lisaaega.

    Returns:
        True, kui agent lõpetas exit code 0-ga; False muul juhul.
    """
    cmd = [
        "openclaw", "agent",
        "--agent", agent_id,
        "--message", task_message,
        "--timeout", str(timeout),
    ]
    print(f"SPAWN\t{agent_id}\t{task_message[:80]}...")

    proc_timeout = timeout + 20

    try:
        result = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            timeout=proc_timeout,
            env={
                **os.environ,
                "PATH": "/usr/local/bin:/usr/bin:/bin:" + os.environ.get("PATH", ""),
            },
        )
    except subprocess.TimeoutExpired:
        print(f"SPAWN_TIMEOUT\t{agent_id}", file=sys.stderr)
        return False

    if result.returncode == 0:
        print(f"SPAWN_OK\t{agent_id}")
        if result.stdout:
            print(result.stdout.strip())
        return True

    err = (result.stderr or result.stdout or "").strip()
    print(f"SPAWN_FAIL\t{agent_id}\t{err[:200]}", file=sys.stderr)

    if notify_script:
        try:
            subprocess.run(
                [sys.executable, notify_script, "--error",
                 f"{agent_id} spawn ebaõnnestus: {err[:200]}"],
                timeout=15,
                capture_output=True,
            )
        except Exception:
            pass

    return False


def spawn_with_retry(
    agent_id: str,
    task_message: str,
    notify_script: str | None = None,
    max_retries: int = 2,
    initial_delay: float = 5.0,
) -> bool:
    """Proovi agenti käivitada kuni max_retries korda exponential backoff-iga.

    Args:
        agent_id: Agendi identifikaator.
        task_message: Agendile saadetav ülesanne.
        notify_script: Tee slack_notify.py-le.
        max_retries: Maksimaalne katsete arv pärast esimest ebaõnnestumist.
        initial_delay: Algne ooteaeg sekundites (kahekordistub igal retry-l).

    Returns:
        True, kui mõni katse õnnestus; False, kui kõik katsed ebaõnnestusid.
    """
    delay = initial_delay
    for attempt in range(max_retries + 1):
        if attempt > 0:
            print(f"SPAWN_RETRY\t{agent_id}\tattempt={attempt}\tdelay={delay:.0f}s")
            time.sleep(delay)
            delay *= 2

        if spawn_agent(agent_id, task_message, notify_script=notify_script):
            return True

    return False
