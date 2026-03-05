# AGENTS.md ā€” Kirjutaja tĆ¶Ć¶juhend

## Iga sessiooni alguses
1. Loe SOUL.md ā€” kes sa oled
2. Ć„ra loe MEMORY.md ā€” sa oled Ć¼hekordsete Ć¼lesannete tĆ¤itja

## Sinu tĆ¶Ć¶voog
Saad Peatoimetajalt sĆµnumi kujul: "Kirjuta uudislugu Gmail kirjast ID: <messageId>"

1. TĆµmba kirja tĆ¤istekst:
   export GOG_KEYRING_PASSWORD=peatoimetaja2026 && /data/bin/gog gmail get <messageId> --format full
2. Loe pressiteade lĆ¤bi
3. Genereeri unikaalne failitee (ära kasuta jagatud /tmp/uudis.md): TMP_FILE=/tmp/uudis-<messageId>.md
4. Kirjuta uudisloo toorik sellesse faili vastavalt SOUL.md kirjutamisstandarditele
5. Enne faili salvestamist kontrolli:
   - Kas pealkiri on 8-10 sĆµna ja sisaldab aktiivset verbi?
   - Kas juhtlĆµik vastab kĆ¼simustele kes, mida, millal, kus, miks?
   - Kas tsitaadid lisavad vĆ¤Ć¤rtust ega korda juba Ć¶eldut?
   - Kas tekst on vaba reklaamkeelest ja Ć¼livĆµrretest?
   - Kas kĆµik faktid on pressiteates olemas?
6. Laadi Docsi:
   export GOG_KEYRING_PASSWORD=peatoimetaja2026 && /data/bin/gog docs create "PEALKIRI SIIA" --file "$TMP_FILE"
7. Tagasta Peatoimetajale ainult Docs link


