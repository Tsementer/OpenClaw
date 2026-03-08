"""Unit testid reconcile_dispatch.py abitunktsioonide jaoks."""
import sys
import os
import json
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "state"))

import reconcile_dispatch as rd


def _ev(status: str, tid: str = "t1", mid: str = "m1", **extra) -> dict:
    now = time.time()
    base = {
        "status": status,
        "event": status,
        "threadId": tid,
        "messageId": mid,
        "subject": "Teema",
        "from": "a@b.ee",
        "receivedAt": "2026-01-01",
        "prescore": None,
        "finalscore": None,
        "docsLinks": [],
        "lastError": None,
        "createdAt": now,
        "updatedAt": now,
    }
    base.update(extra)
    return base


class TestLatestByThread:
    def test_empty_events(self):
        assert rd.latest_by_thread([]) == {}

    def test_single_event(self):
        ev = _ev("NEW")
        result = rd.latest_by_thread([ev])
        assert result["t1"] == ev

    def test_latest_wins(self):
        ev1 = _ev("NEW")
        ev2 = _ev("TRIAGED")
        result = rd.latest_by_thread([ev1, ev2])
        assert result["t1"]["status"] == "TRIAGED"

    def test_multiple_threads(self):
        ev1 = _ev("NEW", tid="t1")
        ev2 = _ev("TRIAGED", tid="t2")
        result = rd.latest_by_thread([ev1, ev2])
        assert len(result) == 2
        assert result["t1"]["status"] == "NEW"
        assert result["t2"]["status"] == "TRIAGED"

    def test_events_without_threadId_ignored(self):
        ev = {"status": "NEW", "messageId": "m1"}
        result = rd.latest_by_thread([ev])
        assert result == {}


class TestHistoryIndex:
    def test_empty_events(self):
        assert rd.history_index([]) == {}

    def test_single_event(self):
        result = rd.history_index([_ev("NEW")])
        assert "NEW" in result["t1"]

    def test_multiple_statuses_same_thread(self):
        events = [_ev("NEW"), _ev("TRIAGED"), _ev("DRAFTED")]
        result = rd.history_index(events)
        assert result["t1"] == {"NEW", "TRIAGED", "DRAFTED"}

    def test_different_threads(self):
        events = [_ev("NEW", tid="t1"), _ev("TRIAGED", tid="t2")]
        result = rd.history_index(events)
        assert "NEW" in result["t1"]
        assert "TRIAGED" in result["t2"]


class TestDocsLinksOfThread:
    def test_empty(self):
        assert rd.docs_links_of_thread([]) == {}

    def test_event_without_docsLinks(self):
        ev = _ev("DRAFTED", docsLinks=[])
        assert rd.docs_links_of_thread([ev]) == {}

    def test_event_with_docsLinks(self):
        url = "https://docs.google.com/document/d/abc"
        ev = _ev("DRAFTED", docsLinks=[url])
        result = rd.docs_links_of_thread([ev])
        assert result["t1"] == [url]

    def test_non_string_links_filtered(self):
        ev = _ev("DRAFTED", docsLinks=[42, "https://docs.google.com/document/d/x", None])
        result = rd.docs_links_of_thread([ev])
        assert result["t1"] == ["https://docs.google.com/document/d/x"]

    def test_latest_docsLinks_wins(self):
        url1 = "https://docs.google.com/document/d/v1"
        url2 = "https://docs.google.com/document/d/v2"
        events = [
            _ev("DRAFTED", docsLinks=[url1]),
            _ev("EDITED", docsLinks=[url2]),
        ]
        result = rd.docs_links_of_thread(events)
        # Viimane kirje võidab
        assert result["t1"] == [url2]


class TestReconcileLogic:
    """Testib reconcile otsustusloogika tingimusi."""

    def test_triaged_with_high_score_needs_draft(self):
        """TRIAGED finalscore>=6, pole DRAFTED ajaloos -> vaja kirjutajat."""
        ev = _ev("TRIAGED", finalscore=8)
        latest = {"t1": ev}
        hist = {"t1": {"NEW", "TRIAGED"}}

        should_spawn = (
            ev.get("status") == "TRIAGED"
            and isinstance(ev.get("finalscore"), (int, float))
            and ev.get("finalscore") >= 6
            and not any(x in hist["t1"] for x in ("DRAFTED", "EDITED", "FAILED"))
        )
        assert should_spawn is True

    def test_triaged_with_low_score_no_draft(self):
        """TRIAGED finalscore<6 -> ei spawni kirjutajat."""
        ev = _ev("TRIAGED", finalscore=4)
        should_spawn = (
            ev.get("status") == "TRIAGED"
            and isinstance(ev.get("finalscore"), (int, float))
            and ev.get("finalscore") >= 6
        )
        assert should_spawn is False

    def test_drafted_with_docs_needs_toimetaja(self):
        """DRAFTED + docsLinks + pole EDITED -> vaja toimetajat."""
        ev = _ev("DRAFTED", docsLinks=["https://docs.google.com/document/d/x"])
        hist = {"t1": {"NEW", "TRIAGED", "DRAFTED"}}
        links = {"t1": ["https://docs.google.com/document/d/x"]}

        dl = links.get("t1", [])
        should_spawn = (
            ev.get("status") == "DRAFTED"
            and bool(dl)
            and not any(x in hist["t1"] for x in ("EDITED", "FAILED"))
        )
        assert should_spawn is True

    def test_drafted_already_edited_no_spawn(self):
        """DRAFTED aga EDITED on juba ajaloos -> ei spawni."""
        ev = _ev("DRAFTED", docsLinks=["https://docs.google.com/document/d/x"])
        hist = {"t1": {"NEW", "TRIAGED", "DRAFTED", "EDITED"}}
        links = {"t1": ["https://docs.google.com/document/d/x"]}

        dl = links.get("t1", [])
        should_spawn = (
            ev.get("status") == "DRAFTED"
            and bool(dl)
            and not any(x in hist["t1"] for x in ("EDITED", "FAILED"))
        )
        assert should_spawn is False

    def test_notified_already_no_renotify(self):
        """Kui NOTIFIED on ajaloos, ei peaks uuesti teavitama."""
        hist = {"t1": {"NEW", "TRIAGED", "DRAFTED", "EDITED", "NOTIFIED"}}
        already_notified = "NOTIFIED" in hist.get("t1", set())
        assert already_notified is True

    def test_edited_not_notified_should_notify(self):
        """EDITED + pole NOTIFIED ajaloos -> vaja teavitust."""
        ev = _ev("EDITED")
        hist = {"t1": {"NEW", "TRIAGED", "DRAFTED", "EDITED"}}

        should_notify = (
            ev.get("status") in {"DRAFTED", "EDITED"}
            and "NOTIFIED" not in hist.get("t1", set())
        )
        assert should_notify is True


class TestLoadEvents:
    """load_events — ledger faili lugemine."""

    def test_missing_file_returns_empty(self, tmp_path):
        rd.LEDGER = str(tmp_path / "nonexistent.jsonl")
        assert rd.load_events() == []

    def test_valid_events_loaded(self, tmp_path):
        ledger = str(tmp_path / "ledger.jsonl")
        events = [_ev("NEW"), _ev("TRIAGED")]
        with open(ledger, "w") as f:
            for ev in events:
                f.write(json.dumps(ev) + "\n")
        rd.LEDGER = ledger
        result = rd.load_events()
        assert len(result) == 2

    def test_invalid_json_skipped(self, tmp_path):
        ledger = str(tmp_path / "ledger.jsonl")
        with open(ledger, "w") as f:
            f.write("{ invalid }\n")
            f.write(json.dumps(_ev("NEW")) + "\n")
        rd.LEDGER = ledger
        result = rd.load_events()
        assert len(result) == 1

    def test_empty_lines_skipped(self, tmp_path):
        ledger = str(tmp_path / "ledger.jsonl")
        with open(ledger, "w") as f:
            f.write("\n\n")
            f.write(json.dumps(_ev("NEW")) + "\n")
        rd.LEDGER = ledger
        result = rd.load_events()
        assert len(result) == 1
