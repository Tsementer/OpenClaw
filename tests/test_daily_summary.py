"""Unit testid daily_summary.py _parse_entry_date abifunktsiooni jaoks."""
import sys
import os
import time
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "state"))

import daily_summary as ds


class TestParseEntryDate:
    """_parse_entry_date — unix timestamp ja string kuupäevade sõelumine."""

    def test_updatedAt_unix_timestamp(self):
        """updatedAt unix timestamp peab tagastama õige ISO kuupäeva."""
        # 2026-03-08 12:00:00 UTC
        ts = datetime(2026, 3, 8, 12, 0, 0).timestamp()
        entry = {"updatedAt": ts, "createdAt": ts}
        result = ds._parse_entry_date(entry)
        # Peab algama 2026-03-08-ga (timezone sõltuvus)
        assert result is not None
        assert result.startswith("2026-03-0")  # UTC+2 puhul võib olla -07 või -08

    def test_createdAt_used_if_no_updatedAt(self):
        """createdAt kasutatakse, kui updatedAt puudub."""
        ts = datetime(2026, 1, 15, 10, 0, 0).timestamp()
        entry = {"createdAt": ts}
        result = ds._parse_entry_date(entry)
        assert result is not None
        assert "2026-01-1" in result

    def test_invalid_timestamp_returns_none(self):
        """Vigane timestamp peab tagastama None."""
        entry = {"updatedAt": -9999999999999}
        result = ds._parse_entry_date(entry)
        assert result is None

    def test_no_timestamp_fields_returns_none(self):
        """Kui ei updatedAt ega createdAt, tagastatakse None."""
        entry = {"status": "NEW"}
        result = ds._parse_entry_date(entry)
        assert result is None

    def test_zero_timestamp_skipped(self):
        """0 timestamp loetakse kehtetuks."""
        entry = {"updatedAt": 0, "createdAt": 0}
        result = ds._parse_entry_date(entry)
        assert result is None

    def test_today_entry_matches_today(self):
        """Tänase kuupäeva timestamp peab sobima tänase kuupäevaga."""
        from datetime import date
        today = date.today().isoformat()
        ts = time.time()
        entry = {"updatedAt": ts}
        result = ds._parse_entry_date(entry)
        assert result == today


class TestDailyStats:
    """Testib stats agregatsiooni loogika simulatsiooni."""

    def _count_stats(self, entries: list[dict], today: str) -> tuple[dict, list[str]]:
        stats = {"triaged": 0, "drafted": 0, "edited": 0, "skipped": 0, "failed": 0}
        subjects = []
        for entry in entries:
            if ds._parse_entry_date(entry) != today:
                continue
            s = entry.get("status", "").lower()
            if s in stats:
                stats[s] += 1
            if s == "drafted":
                subjects.append(entry.get("subject", "?"))
        return stats, subjects

    def test_empty_entries(self):
        from datetime import date
        today = date.today().isoformat()
        stats, subjects = self._count_stats([], today)
        assert sum(stats.values()) == 0
        assert subjects == []

    def test_today_entries_counted(self):
        from datetime import date
        today = date.today().isoformat()
        now = time.time()
        entries = [
            {"status": "TRIAGED", "subject": "T1", "updatedAt": now},
            {"status": "DRAFTED", "subject": "D1", "updatedAt": now},
            {"status": "SKIPPED", "subject": "S1", "updatedAt": now},
        ]
        stats, subjects = self._count_stats(entries, today)
        assert stats["triaged"] == 1
        assert stats["drafted"] == 1
        assert stats["skipped"] == 1
        assert subjects == ["D1"]

    def test_old_entries_not_counted(self):
        from datetime import date
        today = date.today().isoformat()
        # 2020-01-01
        old_ts = datetime(2020, 1, 1, 10, 0, 0).timestamp()
        entries = [
            {"status": "TRIAGED", "subject": "Vana", "updatedAt": old_ts},
        ]
        stats, subjects = self._count_stats(entries, today)
        assert stats["triaged"] == 0

    def test_unknown_status_not_counted(self):
        from datetime import date
        today = date.today().isoformat()
        now = time.time()
        entries = [{"status": "UNKNOWN_STATUS", "updatedAt": now}]
        stats, subjects = self._count_stats(entries, today)
        assert sum(stats.values()) == 0

    def test_multiple_drafts_all_in_subjects(self):
        from datetime import date
        today = date.today().isoformat()
        now = time.time()
        entries = [
            {"status": "DRAFTED", "subject": "Lugu 1", "updatedAt": now},
            {"status": "DRAFTED", "subject": "Lugu 2", "updatedAt": now},
        ]
        stats, subjects = self._count_stats(entries, today)
        assert stats["drafted"] == 2
        assert set(subjects) == {"Lugu 1", "Lugu 2"}
