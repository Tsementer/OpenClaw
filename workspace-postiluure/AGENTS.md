# AGENTS.md — Postiluure

## Eesmärk
Triagi Gmaili thread ja kirjuta tulemus ledgerisse (JSONL).

## Väga oluline
- Forwarditud kirjade "from" on sageli forwardija (nt Carl-Robert). Ära tee SKIPPED otsust selle põhjal.
- Kui subject algab "Ed:" või "FW:", käsitle kirja forwardina ja tuleta originaalsaatja ja originaalteema.

## Sisend
Triagi threadId=<threadId> messageId=<messageId> subject=<subject> from=<from> receivedAt=<receivedAt>

## Töövoog
1) Forward-tuvastus:
   - kui subject algab "Ed:" või "FW:" -> FORWARDED=1, muidu 0

2) Prescore (metadata):
   - ära karista from-i eest (see võib olla forwardija)
   - kui subject sisaldab: juhatus, juhatuse, CEO, juht, pank, kasum, dividend, koondab, rahapesu -> prescore >= 6 (max 10)

3) Täiskeha / orig-meta reegel:
   - Kui FORWARDED=1: too täiskeha ALATI ja võta origFrom/origSubject/origSent:
     export GOG_KEYRING_PASSWORD="$GOG_KEYRING_PASSWORD" && python3 /data/.openclaw/state/extract_forward_meta.py <messageId>
   - Kui FORWARDED=0: too täiskeha ainult siis, kui prescore >= 6.

4) Finalscore:
   - hinda sisu (konkreetsus, numbrid, otsus, mõju)
   - FORWARDED=1 puhul kasuta hindamisel origFrom/origSubject (kui leitud)

5) Otsus:
   - finalscore >= 6 -> TRIAGED
   - finalscore < 6 -> SKIPPED

6) Ledger write (AINULT läbi append_ledger.py; ära kirjuta createdAt/updatedAt käsitsi):
   - Koosta JSON (event/status/threadId/messageId/subject/from/origFrom/origSubject/receivedAt/prescore/finalscore/reason)
   - Kirjuta see ühe rea JSON-ina ledgerisse, näiteks:

python3 - <<'PY' | python3 /data/.openclaw/state/append_ledger.py
import json
print(json.dumps({
  "event":"SKIPPED",
  "status":"SKIPPED",
  "threadId":"<threadId>",
  "messageId":"<messageId>",
  "subject":"<subject>",
  "from":"<from>",
  "origFrom": None,
  "origSubject": None,
  "receivedAt":"<receivedAt>",
  "prescore":4,
  "finalscore":4,
  "reason":"1–2 lauset"
}, ensure_ascii=False))
PY


## Secret handling
- Kasuta `GOG_KEYRING_PASSWORD` väärtust ainult keskkonnast/secret-store'ist; ära hardcode'i parooli juhistesse ega skriptidesse.
