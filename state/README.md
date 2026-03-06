# Ledger state

File: `state/ledger.jsonl`
Format: one JSON object per line (append-only).

Write path:
- All ledger writes must go through `state/append_ledger.py`.
- Writers must not append to `ledger.jsonl` directly.

Required fields per event:
- `threadId` (string, 1..256)
- `messageId` (string, 1..256)
- `subject` (string, 1..500)
- `from` (string, 1..500)
- `receivedAt` (string, 1..128)
- `prescore` (integer 0..10 or `null`)
- `finalscore` (integer 0..10 or `null`)
- `status` (`NEW`, `TRIAGED`, `DRAFTED`, `EDITED`, `NOTIFIED`, `SKIPPED`, `FAILED`)
- `docsLinks` (array, max 20 items; each string 1..2000)
- `lastError` (string up to 2000 or `null`)
- `createdAt` (number)
- `updatedAt` (number)

Validation behavior:
- Invalid events are rejected immediately by `append_ledger.py`.
- Events containing tab/newline/carriage-return in core text fields are rejected.

Transition validation:
- `append_ledger.py` validates transition legality against latest `threadId` state.
- Allowed transitions:
  - `<none> -> NEW`
  - `NEW -> TRIAGED | SKIPPED | FAILED`
  - `TRIAGED -> DRAFTED | FAILED`
  - `DRAFTED -> EDITED | NOTIFIED | FAILED`
  - `EDITED -> NOTIFIED | FAILED`
  - `NOTIFIED`, `SKIPPED`, `FAILED` are terminal (except idempotent same-status append).
- Illegal transitions are rejected immediately.

Current state rule:
- Determine current state by latest event per `threadId`.
- Never edit old lines, always append.
