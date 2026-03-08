"""Unit testid agent_utils.py spawn_agent jaoks."""
import sys
import os
import subprocess
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "state"))

import agent_utils as au


class TestSpawnAgent:
    """spawn_agent — openclaw agendi käivitamine."""

    def _mock_run(self, returncode: int, stdout: str = "", stderr: str = "") -> MagicMock:
        result = MagicMock()
        result.returncode = returncode
        result.stdout = stdout
        result.stderr = stderr
        return result

    def test_successful_spawn_returns_true(self, capsys):
        with patch("subprocess.run", return_value=self._mock_run(0, stdout="Agent done")) as mock_run:
            result = au.spawn_agent("postiluure", "Triagi threadId=t1")
        assert result is True
        out = capsys.readouterr().out
        assert "SPAWN_OK" in out

    def test_failed_spawn_returns_false(self, capsys):
        with patch("subprocess.run", return_value=self._mock_run(1, stderr="timeout error")):
            result = au.spawn_agent("postiluure", "Triagi threadId=t1")
        assert result is False
        err = capsys.readouterr().err
        assert "SPAWN_FAIL" in err

    def test_timeout_returns_false(self, capsys):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("openclaw", 320)):
            result = au.spawn_agent("postiluure", "Triagi threadId=t1")
        assert result is False
        err = capsys.readouterr().err
        assert "SPAWN_TIMEOUT" in err

    def test_task_truncated_in_log(self, capsys):
        long_task = "x" * 200
        with patch("subprocess.run", return_value=self._mock_run(0)):
            au.spawn_agent("kirjutaja", long_task)
        out = capsys.readouterr().out
        # Logis kuvatakse ainult 80 esimest tähemärki + "..."
        assert "..." in out

    def test_notify_script_called_on_failure(self):
        """Kui spawn ebaõnnestub ja notify_script on antud, peaks seda kutsuma."""
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            m = MagicMock()
            m.returncode = 1
            m.stdout = ""
            m.stderr = "spawn error"
            return m

        with patch("subprocess.run", side_effect=fake_run):
            au.spawn_agent("postiluure", "task", notify_script="/tmp/fake_notify.py")

        # Esimene kutse on openclaw agent, teine on notify_script
        assert len(calls) == 2
        assert "/tmp/fake_notify.py" in calls[1]

    def test_no_notify_when_script_not_given(self):
        """Ilma notify_script-ta ei kutsu slack_notify."""
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            m = MagicMock()
            m.returncode = 1
            m.stdout = ""
            m.stderr = "error"
            return m

        with patch("subprocess.run", side_effect=fake_run):
            au.spawn_agent("postiluure", "task", notify_script=None)

        assert len(calls) == 1  # Ainult openclaw kutse

    def test_stdout_printed_on_success(self, capsys):
        with patch("subprocess.run", return_value=self._mock_run(0, stdout="DONE")):
            au.spawn_agent("kirjutaja", "task")
        out = capsys.readouterr().out
        assert "DONE" in out


class TestSpawnWithRetry:
    def test_success_on_first_try(self):
        with patch("agent_utils.spawn_agent", return_value=True) as mock_spawn:
            result = au.spawn_with_retry("postiluure", "task", max_retries=2, initial_delay=0)
        assert result is True
        assert mock_spawn.call_count == 1

    def test_retry_on_failure(self):
        with patch("agent_utils.spawn_agent", side_effect=[False, False, True]) as mock_spawn:
            with patch("time.sleep"):
                result = au.spawn_with_retry("postiluure", "task", max_retries=2, initial_delay=0.01)
        assert result is True
        assert mock_spawn.call_count == 3

    def test_all_retries_exhausted_returns_false(self):
        with patch("agent_utils.spawn_agent", return_value=False) as mock_spawn:
            with patch("time.sleep"):
                result = au.spawn_with_retry("postiluure", "task", max_retries=2, initial_delay=0.01)
        assert result is False
        assert mock_spawn.call_count == 3  # 1 algne + 2 retry

    def test_no_retry_when_max_retries_zero(self):
        with patch("agent_utils.spawn_agent", return_value=False) as mock_spawn:
            result = au.spawn_with_retry("postiluure", "task", max_retries=0, initial_delay=0)
        assert result is False
        assert mock_spawn.call_count == 1
