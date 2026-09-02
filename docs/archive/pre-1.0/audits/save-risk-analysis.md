# SAVE (Disk-Schreiben) — Risikoanalyse (Lane K, 2026-07-04)

Kontext: `(load)` von der eingelegten Disk ist HW-bewiesen (siehe
`docs/mega65-file-io-research.md`). SAVE ist der **inverse, destruktive** Weg. Diese Analyse
listet die Risiken und ein sicheres Vorgehen — VOR jeder Zeile Schreib-Code. Architektur
bleibt: nur „die eingelegte Disk" per Dateiname, nie rohe SD (F011 erzwingt die Disk-Grenze —
gleiche Sicherheitseigenschaft wie beim Lesen).

## Grundunterschied: Lesen ist harmlos, Schreiben kann zerstören
Lesen mutiert nichts — wir konnten frei am Gerät probieren. **Ein einziger fehlerhafter
Schreibzugriff kann echte Daten unwiederbringlich zerstören** (fremde Dateien, Directory,
BAM). Darum gilt: Schreib-Code muss beim ERSTEN echten HW-Lauf korrekt sein, und Entwicklung
läuft ausschließlich auf Wegwerf-Disks.

## Risiken

### R1 — Falscher Sektor → fremde Daten/Metadaten überschrieben (KERN-RISIKO)
Der F011-Write schreibt in den gesetzten (Track, Seite, Sektor). Ein Geometrie-Fehler (meine
Formel) oder Off-by-one schreibt an die falsche Stelle → zerstört eine andere Datei, das
**Directory (Track 40)** oder die **BAM**. Beim Lesen unkritisch, beim Schreiben fatal.

### R2 — Read-Modify-Write der 512-B-Physiksektoren (SUBTIL, KRITISCH)
Ein CBM-256-B-Logiksektor ist die HÄLFTE eines 512-B-F011-Sektors. Um EINEN Logiksektor zu
schreiben, muss man den 512-B-Sektor **lesen**, nur die betroffene 256-B-Hälfte ändern und die
**vollen 512 B zurückschreiben**. Sonst wird die andere Hälfte genullt → der gepaarte
Logiksektor (S xor 1) ist zerstört. Diese RMW-Pflicht ist die häufigste stille Korruption.

### R3 — BAM/Directory-Konsistenz
SAVE muss freie Sektoren aus der **BAM** allozieren (und als belegt markieren) und einen
**Directory-Eintrag** anlegen (Name, Typ, Start-T/S, Blockzahl). Fehler hier korrumpieren das
Dateisystem-Metadaten → Disk unlesbar oder Dateien „verschwinden". Track 40 ist heilig.

### R4 — Freie-Sektor-Allokation
Falsch als „frei" gelesene, real belegte Sektoren zu überschreiben zerstört Fremddaten.
Interleave-/Allokationsreihenfolge (1581-Konvention) muss stimmen.

### R5 — Partielle Schreibvorgänge / Abbruch
Reset/Absturz mitten im Schreiben (Daten geschrieben, aber BAM/Dir nicht — oder umgekehrt)
lässt die Disk inkonsistent: verwaiste Sektoren, hängende Kette, Dir-Eintrag auf Müll.

### R6 — Mount-/Write-Propagation ungeklärt (HW-UNBEKANNT)
Ist die gemountete D81 überhaupt schreibbar, und propagiert ein F011-Write zurück ins
SD-Image? Analog zum Lesen (wo Mount rohe SD-Reads SPERRTE) kann der Mount Writes anders
behandeln (read-only? nur im RAM-Puffer? persistiert nach Reset?). **Muss am Gerät verifiziert
werden**, bevor irgendetwas darauf gebaut wird.

### R7 — F011-Write-Opcode/Sequenz unbestätigt
Wir haben den READ-Weg am Gerät vermessen ($D081=$40 read, M1-Puffer). Der WRITE-Weg
(Opcode, Puffer-Füllung via $DE00, Write-Command, BUSY/DRQ-Handshake, Verify) ist NICHT
bestätigt — nicht aus dem Kopf annehmen, sondern wie beim Lesen am Gerät nageln.

### R8 — Budget (koppelt an die Verdrahtung)
SAVE-Code (BAM + Dir + Allokation + RMW) ist deutlich GRÖSSER als LOAD. LOAD passt schon
nicht ins Vollprodukt (~510 B .text über). SAVE verschärft das → gated auf dieselbe
Budget-Lösung (Disk-Stdlib-Boot / A-Reclaim). Siehe `docs/memory-budget-strategy.md`.

## Sicheres Vorgehen (verbindlich, in dieser Reihenfolge)

1. **NUR Wegwerf-Disks.** Entwicklung/Test ausschließlich auf einer eigens hochgeladenen,
   entbehrlichen D81 — NIE die echten Disks des Nutzers, auch keine Kopie einer echten.
2. **Read-Back-Verify nach JEDEM Write.** Geschriebenen Sektor sofort über den bewiesenen
   Leseweg zurücklesen und byte-vergleichen; bei Abweichung laut abbrechen.
3. **Kleinste destruktive Einheit zuerst:** EIN Datensektor in einen KNOWN-FREE-Bereich
   (nicht BAM/Dir/Fremddaten), mit RMW, dann Read-Back. Erst damit F011-Write-Mechanik +
   Geometrie + RMW + R6 (Mount-Persistenz über Reset) beweisen.
4. **RMW immer** (R2): physischen 512-B-Sektor lesen → Ziel-Hälfte ändern → 512 B zurück.
5. **Track 40 (Dir/BAM) zuletzt** und erst, wenn der Sektor-Write bombenfest verifiziert ist.
6. **Neue-Datei-Semantik vor Überschreiben/Löschen:** neue Datei anlegen (freie Sektoren +
   1 Dir-Eintrag) ist sicherer als Freigeben/Überschreiben. Anfangs evtl. nur auf frisch
   formatierte Scratch-Disk schreiben.
7. **Schreibreihenfolge für Crash-Sicherheit (R5):** erst Datensektoren, dann BAM, Dir-Eintrag
   ZULETZT — ein Crash hinterlässt dann höchstens harmlos verwaiste Sektoren, keinen
   Dir-Eintrag auf Müll.
8. **Mount-Schreibbarkeit + Persistenz (R6) explizit prüfen:** schreiben, Reset, wieder
   mounten, zurücklesen — persistiert es? Falls Mount read-only ist, ist SAVE ohne anderen
   Weg (SD-direkt ist tabu/Sackgasse) blockiert — das wäre ein früher K.O.-Befund.

## Reihenfolge-Empfehlung
SAVE ERST nach der LOAD-Budget-Lösung angehen (R8). Dann streng nach obigem Protokoll:
Sektor-Write-Primitive + Verify + Mount-Persistenz (R6/R7) als erster, isolierter HW-Meilenstein
— das ist der eigentliche Gate. 1581-BAM/Dir-Logik erst danach. Kein Schreiben auf echte Disks,
bis die Kette Sektor-Write→Read-Back→Reset→Read-Back grün ist.
