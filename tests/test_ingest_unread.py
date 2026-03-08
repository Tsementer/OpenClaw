"""Unit testid ingest_unread.py parse_plain ja load_seen_state jaoks."""
import sys
import os
import json
import time
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "state"))

import ingest_unread as iu


class TestParsePlain:
    """parse_plain — gog search väljundi sõeluja."""

    def test_empty_output_returns_empty(self):
        assert iu.parse_plain("") == []

    def test_no_results_string_returns_empty(self):
        assert iu.parse_plain("No results found") == []

    def test_header_row_skipped(self):
        lines = "ID\tTHREAD\tDATE\tFROM\tSUBJECT\nabc\tthread1\t2026-01-01\tsaatja@test.ee\tTeema"
        result = iu.parse_plain(lines)
        assert len(result) == 1
        assert result[0] == ("thread1", "abc", "2026-01-01", "saatja@test.ee", "Teema")

    def test_multiple_rows(self):
        lines = (
            "msg1\tthread1\t2026-01-01\ta@b.ee\tPealkiri 1\n"
            "msg2\tthread2\t2026-01-02\tc@d.ee\tPealkiri 2\n"
        )
        result = iu.parse_plain(lines)
        assert len(result) == 2
        assert result[0][0] == "thread1"
        assert result[1][0] == "thread2"

    def test_row_with_fewer_than_5_parts_skipped(self):
        lines = "msg1\tthread1\t2026-01-01"
        assert iu.parse_plain(lines) == []

    def test_whitespace_only_rows_skipped(self):
        lines = "msg1\tthread1\t2026-01-01\ta@b.ee\tTeema\n\n   \n"
        result = iu.parse_plain(lines)
        assert len(result) == 1

    def test_subject_with_spaces_preserved(self):
        lines = "msg1\tthread1\t2026-01-01\ta@b.ee\tPikk Pealkiri Siin"
        result = iu.parse_plain(lines)
        assert result[0][4] == "Pikk Pealkiri Siin"


class TestLoadSeenState:
    """load_seen_state — ledger'i lugemine."""

    def _make_ledger(self, entries: list[dict], path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for ev in entries:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")

    def test_empty_ledger(self, tmp_path):
        ledger = str(tmp_path / "ledger.jsonl")
        # Tühi fail
        open(ledger, "w").close()
        iu.LEDGER = ledger
        latest, seen = iu.load_seen_state()
        assert latest == {}
        assert seen == set()

    def test_missing_ledger(self, tmp_path):
        iu.LEDGER = str(tmp_path / "does_not_exist.jsonl")
        latest, seen = iu.load_seen_state()
        assert latest == {}
        assert seen == set()

    def test_single_new_event(self, tmp_path):
        ledger = str(tmp_path / "ledger.jsonl")
        now = time.time()
        self._make_ledger([{
            "status": "NEW", "threadId": "t1", "messageId": "m1",
            "createdAt": now, "updatedAt": now,
        }], ledger)
        iu.LEDGER = ledger
        latest, seen = iu.load_seen_state()
        assert latest["t1"] == "NEW"
        assert ("t1", "m1") in seen

    def test_latest_status_is_last_entry(self, tmp_path):
        """Viimane kirje sama threadId-ga peab olema latest_status."""
        ledger = str(tmp_path / "ledger.jsonl")
        now = time.time()
        self._make_ledger([
            {"status": "NEW", "threadId": "t1", "messageId": "m1",
             "createdAt": now, "updatedAt": now},
            {"status": "TRIAGED", "threadId": "t1", "messageId": "m1",
             "createdAt": now, "updatedAt": now},
        ], ledger)
        iu.LEDGER = ledger
        latest, seen = iu.load_seen_state()
        assert latest["t1"] == "TRIAGED"

    def test_invalid_json_lines_skipped(self, tmp_path):
        ledger = str(tmp_path / "ledger.jsonl")
        with open(ledger, "w") as f:
            f.write("{ invalid json }\n")
            f.write(json.dumps({"status": "NEW", "threadId": "t1", "messageId": "m1",
                                "createdAt": 1700000000, "updatedAt": 1700000000}) + "\n")
        iu.LEDGER = ledger
        latest, seen = iu.load_seen_state()
        assert "t1" in latest

    def test_multiple_threads(self, tmp_path):
        ledger = str(tmp_path / "ledger.jsonl")
        now = time.time()
        self._make_ledger([
            {"status": "NEW", "threadId": "t1", "messageId": "m1",
             "createdAt": now, "updatedAt": now},
            {"status": "TRIAGED", "threadId": "t2", "messageId": "m2",
             "createdAt": now, "updatedAt": now},
        ], ledger)
        iu.LEDGER = ledger
        latest, seen = iu.load_seen_state()
        assert latest["t1"] == "NEW"
        assert latest["t2"] == "TRIAGED"
        assert ("t1", "m1") in seen
        assert ("t2", "m2") in seen


class TestDeduplication:
    """Kontrollib, et uuesti käivitamisel ei tekita duplikaate."""

    def _write_ledger(self, path: str, events: list[dict]) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for ev in events:
                f.write(json.dumps(ev) + "\n")

    def test_done_thread_skipped(self, tmp_path):
        """Thread terminaalses olekus ei tohi saada uut NEW eventi."""
        ledger = str(tmp_path / "ledger.jsonl")
        now = time.time()
        self._write_ledger(ledger, [{
            "status": "TRIAGED", "threadId": "t1", "messageId": "m1",
            "createdAt": now, "updatedAt": now,
        }])
        iu.LEDGER = ledger

        latest, seen = iu.load_seen_state()
        rows = [("t1", "m1", "2026-01-01", "a@b.ee", "Teema")]

        # Simuleeri main() otsustuslogika
        new_items = []
        for thread_id, msg_id, date_, from_, subject in rows:
            if latest.get(thread_id) in iu.DONE_STATUSES:
                continue
            if (thread_id, msg_id) in seen:
                continue
            new_items.append((thread_id, msg_id))

        assert new_items == [], "Terminaalses olekus thread ei tohi saada uut eventi"

    def test_same_msg_id_pair_skipped(self, tmp_path):
        """Sama (threadId, messageId) paar ei tohi topelt lisatuda."""
        ledger = str(tmp_path / "ledger.jsonl")
        now = time.time()
        self._write_ledger(ledger, [{
            "status": "NEW", "threadId": "t1", "messageId": "m1",
            "createdAt": now, "updatedAt": now,
        }])
        iu.LEDGER = ledger

        latest, seen = iu.load_seen_state()
        rows = [("t1", "m1", "2026-01-01", "a@b.ee", "Teema")]

        new_items = []
        for thread_id, msg_id, date_, from_, subject in rows:
            if latest.get(thread_id) in iu.DONE_STATUSES:
                continue
            if (thread_id, msg_id) in seen:
                continue
            new_items.append((thread_id, msg_id))

        assert new_items == [], "Sama (threadId, messageId) paar ei tohi topelt lisatuda"

    def test_new_thread_accepted(self, tmp_path):
        """Uus thread, mida pole ledgeris, peab läbi minema."""
        ledger = str(tmp_path / "ledger.jsonl")
        iu.LEDGER = ledger
        # Tühi ledger
        open(ledger, "w").close()

        latest, seen = iu.load_seen_state()
        rows = [("t-brand-new", "m-new", "2026-01-01", "a@b.ee", "Uus kiri")]

        new_items = []
        for thread_id, msg_id, date_, from_, subject in rows:
            if latest.get(thread_id) in iu.DONE_STATUSES:
                continue
            if (thread_id, msg_id) in seen:
                continue
            new_items.append((thread_id, msg_id))

        assert new_items == [("t-brand-new", "m-new")]
