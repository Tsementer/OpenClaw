# OpenClaw Security Audit (2026-03-06)

## Key risks identified

1. **Hardcoded authentication token in repository** (`openclaw.json`)
   - `gateway.auth.token` and `gateway.remote.token` are set to a concrete secret value in versioned config.
   - If this repository is shared, anyone with read access can impersonate a trusted client.

2. **Gateway security explicitly weakened** (`openclaw.json`)
   - `allowInsecureAuth`, `dangerouslyDisableDeviceAuth`, and host-header fallback are enabled.
   - Combined with token reuse, this creates a high risk of unauthorized control-plane access.

3. **Browser sandbox disabled** (`openclaw.json`)
   - `browser.noSandbox = true` removes a key containment layer.
   - Increases blast radius if untrusted web content is rendered.

4. **Operational secret present in instructions** (`workspace-kirjutaja/AGENTS.md`, `workspace-postiluure/AGENTS.md`)
   - The password value for `GOG_KEYRING_PASSWORD` appears directly in committed instruction files.
   - This is credential leakage and encourages copy/paste secret handling.

## Immediate mitigations

- Rotate all exposed tokens/passwords immediately.
- Move all credentials to environment variables or secret manager (never commit plaintext).
- Set `gateway.controlUi.allowInsecureAuth=false` and `dangerouslyDisableDeviceAuth=false`.
- Replace static token values with placeholders and fail fast if unset.
- Re-enable browser sandbox where feasible.
- Add secret scanning in CI (e.g., gitleaks/trufflehog) and block commits that include secrets.

## Severity summary

- **Critical**: hardcoded gateway tokens + insecure auth/device auth disabled.
- **High**: plaintext operational password in AGENTS instructions.
- **Medium**: browser sandbox disabled.
