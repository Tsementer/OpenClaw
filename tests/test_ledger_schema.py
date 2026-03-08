"""Unit testid ledger_schema.py validaatori jaoks."""
import sys
import os
import time
import pytest

# Lisame state/ kataloogi path'i
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "state"))

from ledger_schema import validate_event, make_base_event, ALLOWED_TRANSITIONS, VALID_STATUSES


# ── Abifunktsioon kehtiva NEW event loomiseks ────────────────────────────────
def _new_event(**overrides) -> dict:
    now = time.time()
    base = {
        "event": "NEW",
        "status": "NEW",
        "threadId": "thread-abc-123",
        "messageId": "msg-xyz-456",
        "subject": "Testi teema",
        "from": "saatja@näide.ee",
        "receivedAt": "Thu, 01 Jan 2026 10:00:00 +0200",
        "prescore": None,
        "finalscore": None,
        "docsLinks": [],
        "lastError": None,
        "createdAt": now,
        "updatedAt": now,
    }
    base.update(overrides)
    return base


def _triaged_event(**overrides) -> dict:
    now = time.time()
    base = {
        "event": "TRIAGED",
        "status": "TRIAGED",
        "threadId": "thread-abc-123",
        "messageId": "msg-xyz-456",
        "subject": "Testi teema",
        "from": "saatja@näide.ee",
        "receivedAt": "Thu, 01 Jan 2026 10:00:00 +0200",
        "prescore": 7,
        "finalscore": 8,
        "docsLinks": [],
        "lastError": None,
        "createdAt": now,
        "updatedAt": now,
    }
    base.update(overrides)
    return base


def _drafted_event(**overrides) -> dict:
    now = time.time()
    base = {
        "event": "DRAFTED",
        "status": "DRAFTED",
        "threadId": "thread-abc-123",
        "messageId": "msg-xyz-456",
        "subject": "Testi teema",
        "from": "saatja@näide.ee",
        "receivedAt": "Thu, 01 Jan 2026 10:00:00 +0200",
        "prescore": 7,
        "finalscore": 8,
        "docsLinks": ["https://docs.google.com/document/d/abc123"],
        "lastError": None,
        "createdAt": now,
        "updatedAt": now,
    }
    base.update(overrides)
    return base


# ── Kehtivate eventide testid ─────────────────────────────────────────────────

class TestValidEventAccepted:
    def test_new_event_accepted(self):
        validate_event(_new_event(), previous_status=None)

    def test_triaged_event_accepted(self):
        validate_event(_triaged_event(), previous_status="NEW")

    def test_drafted_event_accepted(self):
        validate_event(_drafted_event(), previous_status="TRIAGED")

    def test_edited_event_accepted(self):
        now = time.time()
        ev = {
            "event": "EDITED",
            "status": "EDITED",
            "threadId": "t1",
            "messageId": "m1",
            "subject": "Pealkiri",
            "from": "a@b.ee",
            "receivedAt": "Thu, 01 Jan 2026 10:00:00 +0200",
            "prescore": 7,
            "finalscore": 8,
            "docsLinks": ["https://docs.google.com/document/d/edited123"],
            "lastError": None,
            "createdAt": now,
            "updatedAt": now,
        }
        validate_event(ev, previous_status="DRAFTED")

    def test_skipped_event_accepted(self):
        now = time.time()
        ev = {
            "event": "SKIPPED",
            "status": "SKIPPED",
            "threadId": "t1",
            "messageId": "m1",
            "subject": "Madala skooriga teema",
            "from": "a@b.ee",
            "receivedAt": "Thu, 01 Jan 2026 10:00:00 +0200",
            "prescore": 3,
            "finalscore": 3,
            "docsLinks": [],
            "lastError": None,
            "createdAt": now,
            "updatedAt": now,
        }
        validate_event(ev, previous_status="NEW")

    def test_notified_event_accepted(self):
        now = time.time()
        ev = {
            "event": "NOTIFIED",
            "status": "NOTIFIED",
            "threadId": "t1",
            "messageId": "m1",
            "subject": "Pealkiri",
            "from": "a@b.ee",
            "receivedAt": "Thu, 01 Jan 2026 10:00:00 +0200",
            "prescore": 7,
            "finalscore": 8,
            "docsLinks": ["https://docs.google.com/document/d/abc"],
            "lastError": None,
            "createdAt": now,
            "updatedAt": now,
        }
        validate_event(ev, previous_status="EDITED")

    def test_failed_event_accepted(self):
        now = time.time()
        ev = {
            "event": "FAILED",
            "status": "FAILED",
            "threadId": "t1",
            "messageId": "m1",
            "subject": "Pealkiri",
            "from": "a@b.ee",
            "receivedAt": "Thu, 01 Jan 2026 10:00:00 +0200",
            "prescore": None,
            "finalscore": None,
            "docsLinks": [],
            "lastError": "API timeout",
            "createdAt": now,
            "updatedAt": now,
        }
        validate_event(ev, previous_status="NEW")


# ── Keelatud üleminekute testid ───────────────────────────────────────────────

class TestForbiddenTransitions:
    def test_new_to_drafted_forbidden(self):
        with pytest.raises(ValueError, match="Keelatud üleminek"):
            validate_event(_drafted_event(), previous_status="NEW")

    def test_new_to_edited_forbidden(self):
        now = time.time()
        ev = {
            "event": "EDITED", "status": "EDITED",
            "threadId": "t1", "messageId": "m1", "subject": "S",
            "from": "a@b.ee", "receivedAt": "Thu, 01 Jan 2026 10:00:00 +0200",
            "prescore": 7, "finalscore": 8,
            "docsLinks": ["https://docs.google.com/document/d/x"],
            "lastError": None, "createdAt": now, "updatedAt": now,
        }
        with pytest.raises(ValueError, match="Keelatud üleminek"):
            validate_event(ev, previous_status="NEW")

    def test_notified_to_anything_forbidden(self):
        """NOTIFIED on terminaalne olek — ühtki üleminekut ei lubata."""
        with pytest.raises(ValueError, match="Keelatud üleminek"):
            validate_event(_new_event(threadId="t-notified"), previous_status="NOTIFIED")

    def test_skipped_to_anything_forbidden(self):
        """SKIPPED on terminaalne olek."""
        with pytest.raises(ValueError, match="Keelatud üleminek"):
            validate_event(_triaged_event(threadId="t-skipped"), previous_status="SKIPPED")

    def test_new_without_previous_requires_none(self):
        """NEW ei tohi olla, kui eelmine on NEW — duplikaat."""
        # previous_status="NEW" tähendab, et NEW -> NEW pole lubatud
        with pytest.raises(ValueError, match="Keelatud üleminek"):
            validate_event(_new_event(), previous_status="NEW")


# ── Puuduvate väljade testid ──────────────────────────────────────────────────

class TestMissingFields:
    def test_missing_threadId(self):
        ev = _new_event()
        del ev["threadId"]
        with pytest.raises(ValueError, match="threadId"):
            validate_event(ev)

    def test_missing_status(self):
        ev = _new_event()
        del ev["status"]
        with pytest.raises(ValueError):
            validate_event(ev)

    def test_missing_subject(self):
        ev = _new_event()
        del ev["subject"]
        with pytest.raises(ValueError, match="subject"):
            validate_event(ev)

    def test_triaged_missing_finalscore(self):
        ev = _triaged_event()
        del ev["finalscore"]
        with pytest.raises(ValueError, match="finalscore"):
            validate_event(ev, previous_status="NEW")

    def test_drafted_missing_docsLinks(self):
        ev = _drafted_event()
        del ev["docsLinks"]
        with pytest.raises(ValueError, match="docsLinks"):
            validate_event(ev, previous_status="TRIAGED")


# ── Tüüpide testid ────────────────────────────────────────────────────────────

class TestFieldTypes:
    def test_threadId_must_be_string(self):
        ev = _new_event(threadId=12345)
        with pytest.raises(ValueError, match="threadId"):
            validate_event(ev)

    def test_docsLinks_must_be_list(self):
        ev = _drafted_event(docsLinks="https://docs.google.com/document/d/x")
        with pytest.raises(ValueError, match="docsLinks"):
            validate_event(ev, previous_status="TRIAGED")

    def test_docsLinks_elements_must_be_strings(self):
        ev = _drafted_event(docsLinks=[42, "https://docs.google.com/document/d/x"])
        with pytest.raises(ValueError, match="docsLinks"):
            validate_event(ev, previous_status="TRIAGED")

    def test_prescore_can_be_none(self):
        validate_event(_new_event(prescore=None), previous_status=None)

    def test_prescore_can_be_float(self):
        validate_event(_triaged_event(prescore=7.5, finalscore=8.0), previous_status="NEW")


# ── Pikkuse testid ────────────────────────────────────────────────────────────

class TestMaxLengths:
    def test_subject_too_long(self):
        ev = _new_event(subject="x" * 513)
        with pytest.raises(ValueError, match="subject"):
            validate_event(ev)

    def test_threadId_too_long(self):
        ev = _new_event(threadId="x" * 257)
        with pytest.raises(ValueError, match="threadId"):
            validate_event(ev)

    def test_last_error_too_long(self):
        now = time.time()
        ev = {
            "event": "FAILED", "status": "FAILED",
            "threadId": "t1", "messageId": "m1", "subject": "S",
            "from": "a@b.ee", "receivedAt": "Thu, 01 Jan 2026 10:00:00 +0200",
            "prescore": None, "finalscore": None, "docsLinks": [],
            "lastError": "x" * 2001,
            "createdAt": now, "updatedAt": now,
        }
        with pytest.raises(ValueError, match="lastError"):
            validate_event(ev, previous_status="NEW")


# ── Tühi threadId ─────────────────────────────────────────────────────────────

class TestEmptyThreadId:
    def test_empty_threadId_raises(self):
        ev = _new_event(threadId="")
        with pytest.raises(ValueError, match="threadId"):
            validate_event(ev)

    def test_whitespace_threadId_raises(self):
        ev = _new_event(threadId="   ")
        with pytest.raises(ValueError, match="threadId"):
            validate_event(ev)


# ── Kehtetu status ────────────────────────────────────────────────────────────

class TestInvalidStatus:
    def test_unknown_status_raises(self):
        ev = _new_event(status="PROCESSING", event="PROCESSING")
        with pytest.raises(ValueError, match="Kehtetu status"):
            validate_event(ev)


# ── make_base_event abifunktsioon ─────────────────────────────────────────────

class TestMakeBaseEvent:
    def test_returns_dict_with_required_fields(self):
        ev = make_base_event("NEW", "t1", "m1", "Teema")
        assert ev["status"] == "NEW"
        assert ev["threadId"] == "t1"
        assert ev["messageId"] == "m1"
        assert ev["subject"] == "Teema"
        assert isinstance(ev["createdAt"], float)
        assert isinstance(ev["updatedAt"], float)
        assert ev["docsLinks"] == []

    def test_base_event_passes_validation(self):
        ev = make_base_event("NEW", "thread-1", "msg-1", "Teema")
        # NEW nõuab ka "from" ja "receivedAt" — lisame need
        ev["from"] = "saatja@test.ee"
        ev["receivedAt"] = "Thu, 01 Jan 2026 10:00:00 +0200"
        validate_event(ev, previous_status=None)


# ── ALLOWED_TRANSITIONS täielikkuse kontroll ──────────────────────────────────

class TestAllowedTransitionsCompleteness:
    def test_all_valid_statuses_have_transition_entry(self):
        """Iga kehtiv olek peab olema ALLOWED_TRANSITIONS võtmena."""
        for status in VALID_STATUSES:
            assert status in ALLOWED_TRANSITIONS, (
                f"Puudub üleminkukirje staatusele: {status}"
            )

    def test_all_transition_targets_are_valid_statuses(self):
        """Kõik ülemineku sihtolekud peavad olema VALID_STATUSES-is."""
        for src, targets in ALLOWED_TRANSITIONS.items():
            for tgt in targets:
                assert tgt in VALID_STATUSES, (
                    f"Ülemink {src!r} -> {tgt!r}: siht pole VALID_STATUSES-is"
                )
