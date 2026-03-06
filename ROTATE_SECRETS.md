# Secret Rotation Runbook (OpenClaw)

Kasuta seda kohe, kui võtmed/tokendid on sattunud Git repofaili.

## Kiire vastus: kas pead ise midagi tegema?

**Jah.** Repo ei saa sinu teenusepakkujate võtmeid sinu eest roteerida.

Tee käsitsi need 4 sammu:
1. **Nexos**: loo uus API key ja tühista vana key.
2. **OpenClaw token**: genereeri uus pikk juhuslik token.
3. **Runtime config**: sea uued väärtused serveris (`.env`/secret manager/deploy vars), mitte Gitis.
4. **Restart + kontroll**: taaskäivita teenus ja kontrolli, et autentimine + cron teavitused töötavad.

Näide tokeni genereerimiseks:

```bash
openssl rand -hex 32
```

## 1) Rotate kõik lekkida võinud väärtused

Selles repos olid varem commititud:
- Nexos API key (`models.providers.nexos.apiKey`)
- OpenClaw hook/gateway token (`hooks.token`, `gateway.auth.token`, `gateway.remote.token`)

Tee provideri/platvormi poolel kohe uued väärtused ja tühista vanad.

## 2) Sea uued väärtused ainult runtime keskkonda

Ära commiti päris võtmeid repofailidesse.

Näide (`.env`, Docker runtime, secret manager):

```bash
OPENCLAW_TOKEN=<uus_pikk_juhuslik_token>
NEXOS_API_KEY=<uus_nexos_api_voti>
```

## 3) Kuidas `openclaw.json` päriselt asendada (praktiline)

Allpool kaks varianti. Kasuta ühte.

### Variant A — lihtne käsitsi asendus serveris

1. Kopeeri repo `openclaw.json` serverisse (või ava olemasolev fail).
2. Asenda placeholderid päris väärtustega:
   - `SET_NEXOS_API_KEY`
   - `SET_OPENCLAW_TOKEN`
3. Salvesta fail serveris asukohta, kust OpenClaw seda loeb.

Näide (kohanda path vastavalt sinu setupile):

```bash
cp openclaw.json /data/.openclaw/openclaw.json
sed -i "s|SET_NEXOS_API_KEY|$NEXOS_API_KEY|g" /data/.openclaw/openclaw.json
sed -i "s|SET_OPENCLAW_TOKEN|$OPENCLAW_TOKEN|g" /data/.openclaw/openclaw.json
```

### Variant B — envsubst/templating (soovituslik)

Hoia repofailis ainult placeholderid ja genereeri runtime fail deploy ajal:

```bash
export NEXOS_API_KEY='<uus_nexos_api_voti>'
export OPENCLAW_TOKEN='<uus_pikk_juhuslik_token>'

cat openclaw.json \
  | sed 's|SET_NEXOS_API_KEY|'"$NEXOS_API_KEY"'|g' \
  | sed 's|SET_OPENCLAW_TOKEN|'"$OPENCLAW_TOKEN"'|g' \
  > /data/.openclaw/openclaw.json
```

> NB! Ära tee commitit genereeritud failiga, kui seal on päris võtmed.

## 4) Taaskäivita teenus

```bash
docker compose up -d
```

## 5) Kontrolli pärast restarti

```bash
# config on loetav
python3 -m json.tool /data/.openclaw/openclaw.json >/dev/null

# kontrolli, et placeholderid on kadunud runtime failist
rg -n "SET_NEXOS_API_KEY|SET_OPENCLAW_TOKEN" /data/.openclaw/openclaw.json

# kontrolli, et vana lekkinud võtme muster ei esine repo failis
rg -n "nexos-team-|Fn2N2s1" openclaw.json
```

## 6) (Soovitus) Lisa secret scanning CI-sse

Näiteks Gitleaks/TruffleHog pre-commit või CI check, et järgmine leke peatada enne merge'i.
