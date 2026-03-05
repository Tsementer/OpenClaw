# Ledger state

File: `state/ledger.jsonl`
Format: one JSON object per line (append-only).

Required fields per event:
- `threadId`
- `messageId`
- `subject`
- `from`
- `receivedAt`
- `prescore`
- `finalscore`
- `status` (`NEW`, `TRIAGED`, `DRAFTED`, `EDITED`, `NOTIFIED`, `SKIPPED`, `FAILED`)
- `docsLinks` (array)
- `lastError`
- `createdAt`
- `updatedAt`

Current state rule:
- Determine current state by latest event per `threadId`.
- Never edit old lines, always append.
