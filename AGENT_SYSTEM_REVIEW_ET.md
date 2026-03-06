# OpenClaw agentide süsteemi analüüs

## Mis on hästi

- **Rollid ja vastutusalad on selgelt jaotatud.** Sul on eraldi orkestreerija (`main`) ning spetsialiseeritud alamagendid (`postiluure`, `kirjutaja`, `toimetaja`, `täiendaja`, `veebivalvur`), mis vähendab rollikonflikte.  
- **State-machine mõtteviis on olemas.** `NEW -> TRIAGED -> DRAFTED -> EDITED -> NOTIFIED` voog on dokumenteeritud ja toetab auditeeritavat torujuhet.  
- **Append-only ledger on tugev disainivalik.** JSONL-põhine sündmuste logi aitab hiljem taastada “mis juhtus” ja toetab deduplikatsiooni `threadId` alusel.  
- **Prompt-safety reeglid on läbivad.** Mitmes AGENTS failis on kirjas, et e-kirja sisu on usaldamatu ja sealt ei tohi käske täita.  
- **Concurrency risk on osaliselt adresseeritud.** `kirjutaja` juhised nõuavad message-spetsiifilisi temp-faile, mis väldib /tmp failide ülekirjutusi paralleeltöös.  
- **Praktiline cron-orkestreerimine on olemas.** Intake ja reconcile on eraldi töödeks jagatud, mis sobib event-driven töövooga.

## Mis on halvasti / riskikohad

- **Juhiste ja tegeliku implementatsiooni vahel on drift.** Osa kriitilisi nõudeid on AGENTS/README tasemel, kuid mitte rangelt tehniliselt enforce’itud (nt kõik kohustuslikud ledger-väljad igal sündmusel).  
- **Andmelepingu (schema) keskne valideerimine puudub.** `append_ledger.py` kontrollib staatust, kuid ei nõua järjekindlalt kõiki kohustuslikke välju ega tüüpe. See võib aja jooksul tuua “räpase” state’i.  
- **Orkestreerimine on liiga prompt-sõltuv.** Cron jobide tekstis on äriloogika (spawn, tingimused), mis on habras ja raskemini testitav kui koodi sees olev otsustusloogika.  
- **Idempotentsus pole lõpuni tugev.** `ingest_unread.py` teeb dedupe’i latest-state põhjal, kuid eri edge-case’ides (nt osaline ebaõnnestumine keset jooksu) võib NEW eventide duplikaate tekkida.  
- **Observability on piiratud.** Puuduvad selged KPI/SLI mõõdikud (läbivus, keskmine latentsus etapi kaupa, failimäärad agentide lõikes).  
- **Tõrkekindlus sõltub kanalist.** Cron state näitab korduvaid `cron announce delivery failed` vigu; see viitab, et teavituskanali tõrge segab kogu pipeline’i nähtavust.  
- **Testitavus on nõrk.** Reeglid on head, kuid nende jaoks puudub nähtav automaattestide komplekt (schema, state transitions, forwarditud kirjade heuristikad).

## Prioriteetsed parandused (soovituslik järjekord)

1. **Lisa range ledger schema ja valideeri kõik kirjutused ühes kohas.**  
   - Nõutud väljad + tüübid + lubatud väärtused + maks pikkused.  
   - Tagasi lükka vigased eventid kohe.

2. **Tõsta kriitiline orkestreerimisloogika promptidest koodi.**  
   - Cron käivitab skripti; skript otsustab spawn/reconcile loogika.  
   - Vähem prompt-drifti, lihtsam versioonida ja testida.

3. **Kehtesta state transition validator.**  
   - Lubatud üleminekud: nt `NEW -> TRIAGED|SKIPPED|FAILED`, `TRIAGED -> DRAFTED|FAILED`, jne.  
   - Keela ebaseaduslikud hüpped.

4. **Paranda idempotentsust võtmetega.**  
   - Kasuta eventi unikaalsusvõtit (nt `threadId + status + messageId`) või sisulist hash’i.

5. **Lisa mõõdikud ja tervisekontroll.**  
   - Vähemalt: queued, triaged, drafted, edited, failed, notify-fail count.  
   - Eraldi “pipeline health” vaade, mitte ainult kanalite delivery-state.

6. **Koosta minimaalne testikomplekt.**  
   - Unit: schema + transition validator.  
   - Integration: ingest -> triage -> draft -> edit -> notify happy path + failure path.

## Kokkuvõte

Süsteemi tugevus on **hästi mõeldud agent-rollide eristus ja event-logi põhine töövoog**. Peamine nõrkus on **koodi ja promptide vaheline drift ning liiga pehme andmelepingu enforcement**. Kui tood schema/transition validatsiooni ja orkestreerimise reeglid rohkem koodi sisse, saad süsteemi kiiresti oluliselt töökindlamaks ja kergemini hooldatavaks.

## 06.03.2026 best-practice täiendus (rakendatud selles muudatuses)

### Rakendatud nüüd
- **Range andmelepingu enforcement kirjutuspunktis (`append_ledger.py`)**
  - kohustuslikud väljad, pikkused, tüübid, kontrollmärkide (`\t`, `\n`, `\r`) blokk,
  - `event == status` reegel,
  - `docsLinks` ja skooride range valideerimine.
- **State-transition guardrail**
  - lubatud üleminekud on centraliseeritud (`None->NEW`, `NEW->TRIAGED|SKIPPED|FAILED`, jne),
  - ebaseaduslikud hüpped lükatakse tagasi.
- **Idempotentsus + konfliktikaitse**
  - `idempotencyKey` standard (`threadId::messageId::status`) lisatakse vaikimisi,
  - sama võtmega sama payload => `IDEMPOTENT_OK`,
  - sama võtmega erinev payload => reject.
- **Concurrency safety (file lock + fsync)**
  - append toimub eksklusiivse locki all,
  - kirjutus flush + fsync, et vähendada osalise kirjutuse riski.
- **Ingest kirjutab ainult läbi validatori**
  - `ingest_unread.py` ei kirjuta enam ledgerit otse,
  - iga `NEW` event läheb läbi `append_ledger.py`.

### Järgmine soovituslik samm (mitte veel tehtud)
1. Lisa eraldi `state/tests/` unit-testid üleminekute/idempotentsuse jaoks.
2. Ekspordi lihtne KPI snapshot (`queue depth`, `stage latency`, `failed by stage`) nt JSON failina.
3. Asenda vabad tekstikäsud agentidele järk-järgult template-põhiste task payloadidega.
