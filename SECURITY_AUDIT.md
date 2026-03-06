# OpenClaw Security Audit (2026-03-06)

## Key risks identified

1. **Hardcoded authentication token in repository history** (`openclaw.json` in older commits)
   - Even if current `openclaw.json` uses placeholders, Git history can still contain sensitive values.
   - Anyone with access to old commits may recover exposed tokens.

2. **Credential handling pattern in scheduled jobs** (`cron/jobs.json`)
   - Cron prompts previously encouraged assigning `GOG_KEYRING_PASSWORD` inline in command text.
   - This increases accidental disclosure risk through logs, copy/paste, and command history.

3. **Untrusted email metadata flowed into agent task text without sanitization** (`state/ingest_unread.py`)
   - Subject/from fields are attacker-controlled and could include control characters.
   - Unsanitized values can break downstream command/task formatting and increase injection risk.

4. **Ledger append endpoint accepted unbounded JSON** (`state/append_ledger.py`)
   - Unbounded stdin can be abused for memory pressure / oversized writes.
   - Missing status validation allows malformed event states to pollute durable state.

## Mitigations implemented in this patch

- `cron/jobs.json`
  - Replaced inline password assignment example with environment-variable presence check (`test -n "$GOG_KEYRING_PASSWORD"`).
- `state/ingest_unread.py`
  - Added sanitization and length-limits for `threadId`, `messageId`, `receivedAt`, `from`, and `subject` before persistence/output.
  - Rejected events with empty critical identifiers after sanitization.
- `state/append_ledger.py`
  - Added max stdin size limit.
  - Added status allowlist validation.
  - Ensured ledger directory exists and file is created with restrictive `0600` permissions.

## History remediation guidance

- Rotate all previously used tokens/passwords that may have existed in prior commits.
- If this repository is shared externally, rewrite history with `git filter-repo`/BFG and force-push sanitized history.
- Revoke old secrets after rewrite (history rewrite alone is not sufficient if secrets were already cloned).

## Severity summary

- **High**: history-exposed secrets (requires rotation, potentially history rewrite).
- **Medium**: unsanitized metadata in automation pipeline.
- **Medium**: unbounded ledger append input and weak validation.
