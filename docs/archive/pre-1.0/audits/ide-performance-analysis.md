# IDE-Performance-Analyse (Lane K, 2026-07-06)

Erste quantitative Vermessung des Tipp-Pfads am Gerät (JTAG-Harness: Zähler per
`--memsave`, Benchmarks als REPL-Formen über die serielle Tastatur). Diagnose-Bauart:
Core-Profil + `-DLISP65_DMA_PROF` (Zähler: `dma_cell`, `dma_code/wr/sym`, `gc_runs`,
neu `perf_allocs`, `perf_vm_ops`).

## Methode

Benchmarks als reine Lisp-Formen (kein Tastatur-Rauschen):

```lisp
(setq st  (ide-make-state (ide-make-buffer "b" (cons "" nil))))
(setq st2 (%ide-repeat-self-insert st 97 50))   ; Step-Pfad isoliert
(setq st3 (ide-render st2))                     ; Render-Cache etablieren
(dotimes (i 100) (ide-render st3))              ; Fast-Path-Render (Tipp-Realität)
```

Zähler-Deltas vor/nach jeder Phase; Wall-Zeit host-seitig (100 Iterationen
amortisieren die Poll-Granularität). Wichtig: `dma_cell` ist uint16 und wrappt bei
langen Läufen — 32-Bit-Zähler (`perf_allocs`, `perf_vm_ops`) sind die verlässliche
Währung.

## Befunde (pro Taste = ein Fast-Path-Render, Cursor in der Zeile)

| Metrik | Nursery 24 (alt) | Nursery 192 (neu) |
| --- | --- | --- |
| VM-Instruktionen | 7459 | 7459 |
| Allokationen | 181 | 181 |
| GC-Läufe | 7,5 | **0,94** |
| Code-Fenster-DMAs | 310 | 310 |
| Wall (netto) | **~540 ms** | **~210 ms** |

1. **Der Step-Pfad (Insert) ist billig**: 3,7 Allokationen/Taste — der
   Aktive-Zeilen-Cache wirkt. Die Taste kostet der RENDER.
2. **GC-Frequenz war pathologisch**: Nursery-Hysterese `HEAP_CELLS/2 = 24`
   Allokationen stammt aus der 544-Hot-Zellen-Ära; im Dev-Core (48 hot) feuerte der
   GC 7,5× je Taste. Schwelle parametrisiert (`LISP65_NURSERY_HYSTERESIS`), Core auf
   192 gepinnt: **Faktor ~2,5 Wall**, Zell-DMA nur +9 % (Churn wandert in EXT —
   akzeptierter Trade, Watermark-Sweep deckelt).
3. **Restkosten = VM-Interpretation**: 7459 Ops/Render ≈ 1100 Zyklen/Op. Treiber:
   zeichenweises Rendern (`screen-put-char` je Zeichen — Cursor- + Statuszeile
   ≈ 130 Zeichen/Taste) und der Statuszeilen-Neubau (67 der 181 Allokationen).
4. **Nativer Bulk-Writer passt nicht**: `LISP65_SCREEN_WRITE_STRING` kostet gemessen
   +911 B Bank 0; Reserve ist 72 B. (Bestätigt die alte Budget-Notiz.)

## Nächste Hebel (Reihenfolge)

1. **Delta-Render (Lisp, kein Bank-0)**: beim self-insert ändert sich meist genau
   EIN Zeichen — der Fast-Path malt trotzdem Cursor- (Syntax-Overpaint!) und
   Statuszeile komplett. Dirty-Hint im State (Kommando + Spalte) → nur Suffix ab
   Änderungsspalte zeichnen; Statuszeile nur bei Inhaltswechsel (Cache-Key
   name/modified/symbol-count). Erwartung: 130 → ~5 gemalte Zeichen, −67
   Allokationen; grob halbiert die VM-Ops.
2. **VM-Op-Kosten** (1100 Zyklen/Op; `vm_run` = 10 KB .text, Lane-T-Thema) und
   `dma_code` 310/Render (Codefenster-Thrash, `VM_CODEBUF=56`) — größere Projekte,
   erst nach dem Delta-Render neu messen.

## Offene Messlücken

- Wall-Zeiten tragen ~±10 % Poll-Unsicherheit; für Verdikte auf <20-%-Effekte die
  Iterationszahl erhöhen.
- `dma_sym` blieb praktisch konstant (~160/20 Renders) — die Symbol-Root-Storm-These
  (560 × DMA je GC) ist WIDERLEGT; symval-Marking läuft offenbar nicht über
  Einzel-DMAs pro Symbol.

## Runde 2: Delta-Render (2026-07-06, Abend)

Nutzerbefund nach Runde 1: „viel flüssiger", aber (a) leichtes Flackern je Taste,
(b) Zeilenumbruch verzögert. Beides Render-Mechanik:

- **Flackern** = Fast-Path malte je Taste die KOMPLETTE Cursor-Zeile (Basis-Write +
  Syntax-Overpaint) + Statuszeile ≈ 130 put-chars, obwohl sich 1 Zeichen ändert.
- **Umbruch** = Slow-Path (Cursor wechselt Zeile): voller Frame-Neubau + Dirty-
  Vergleich, und `ide-string-prefix/suffix`+Blank-Zeilen erzeugten frische
  String-Objekte → eq-Dirty-Check hielt unveränderte Zeilen für dirty.

Maßnahmen (reines Lisp, 0 B Bank-0-Text):
1. **Dirty-Hint** (`%ide-hint`-Global): self-insert/delete melden (op . spalte);
   der Fast-Path malt nur noch das Suffix ab Änderungsspalte (`%ide-render-code-
   suffix-at`: Scan-Zustand alloc-frei vorspulen, jedes Zeichen EINMAL malen).
2. **Statuszeilen-Cache** (`%ide-stcache`-Global): Text hängt nur an
   (name modified message) — Cache-Treffer ⇒ EQ ⇒ Malen übersprungen.
3. **""-Kanonisierung** (`%ide-empty-str`): Littab-Konstante EINER Funktion ist
   eq-stabil — prefix/suffix/blank-lines teilen DAS Objekt; Split am Zeilenende
   behält das Original-Zeilenobjekt (eq) ⇒ Umbruch am Buffer-Ende malt ≈ nichts.

Messung (100 Fast-Path-Renders, JTAG-Zähler, identisches Szenario wie Runde 1):

| pro Render | Runde 1 (Nursery 192) | + Delta-Render |
| --- | --- | --- |
| VM-Instruktionen | 7459 | **4765 (−36 %)** |
| Allokationen | 181 | 124 |
| Code-Fenster-DMAs | 310 | **11 (−97 %)** |
| Wall (netto) | ~210 ms | **~110 ms** |

Kumuliert seit Runde 0: ~540 → ~110 ms je Taste. HW: B4-Gate pass 10/10.

**Kosten/Nebenbefunde:**
- +7 Lib-Symbole → Symbolwand riss GENAU an der B4-Grenze („too many symbols"
  beim ide-Load nach place; im Selftest als „vm: type error" mitten in der
  incf-Expansion). Fix: `MAX_SYM 560→576` (+42 B Bank 0; stack_gap 1468/1450)
  + `%ide-hint!`-Helfer inlined (−1 Symbol). Messwerte: Boot 425, +place 434,
  +ide ~561. Die Symbol-Skalierungs-Agenda (EXT-Tabelle) wird DRINGENDER.
- Full-Profil: Blob +875 B über Sympool-Grenze → `SYMPOOL_EXT_OFF 0xa000→0xa800`
  (Bank 5 bis 0xd000 frei, Analogie core/fasl 0xb000).
- Host-Nachzüge: Orakel + Host-Bytecode-VM brauchen set-symbol-value/symbol-value/
  boundp; Dynamik-Budgets delete-cached/delete-backward/type-render-5/repeat-10
  um die ehrlichen Hint-Kosten (+12–15 Ops/Step) angehoben, dirty-scan blieb dank
  Kanonisierung unter Budget (1395/1410).

## Nächste Hebel (Stand nach Runde 2)

1. Slow-Path-Frame-Neubau (Umbruch mitten im Buffer, Scrollen) — inkrementelle
   Cache-Pflege statt Neubau+Vergleich.
2. VM-Op-Kosten (~1100 Zyklen/Op; vm_run 10 KB .text, Lane-T) — jetzt klar der
   dominante Rest (4765 Ops ≈ 110 ms).
3. Cursor-Bewegung ohne Malen (Hint für move: alter Cursor-Platz restaurieren,
   neuer setzen — statt Voll-Zeile).

## Runde 2b: Koaleszenz-Artefakt (Nutzerbefund nach Runde 2)

Schnelltippen erzeugte Geister-Leerzeichen/Cursor-Abdrücke, die erst bei
Cursor-Bewegung verschwanden. Ursache: Render-Koaleszenz (%ide-drain-pending)
verarbeitet mehrere Steps je Render — der Dirty-Hint wurde aber je Step
ÜBERSCHRIEBEN, der eine Render malte nur das Suffix des LETZTEN Zeichens; die
Zellen der früheren Burst-Zeichen behielten alten Schirm-Inhalt (Cursor-Block!).

Fix: Hints VERSCHMELZEN statt überschreiben (`%ide-hint-merge`: min-Spalte,
Lösch-Pads summieren; Format jetzt `(spalte . pad)`), Konsum ausschließlich im
Render (beide Pfade setzen nil); Bewegungs-/Umbruch-Kommandos invalidieren
zentral im Dispatch (nil = Voll-Zeilen-Redraw, immer korrekt). Kosten +15 Ops/
Step, +5/Move (Budgets nachgezogen, im Makefile dokumentiert). B4 pass 10/10;
JTAG-Burst-Test: Schirm==Buffer, keine Geister-Zellen.

**Nachtrag Delete-Artefakt:** Backspace hinterließ je Taste einen weißen Block —
der ALTE Cursor-Standplatz liegt eine Zelle HINTER dem neuen Zeilenende und wurde
von Suffix+Pad nicht erfasst. Fix: %ide-render-code-suffix-at löscht (pad+1)
Zellen (Treiber clippt am Rand); deckt auch koaleszierte Delete-Bursts (Pad-Summe
+1 = exakt der Standplatz des Blocks vor dem Burst). B4 pass 10/10.

## Runde 3: RETURN-Spam-Crash (Nutzerbefund) — vier Schichten

Symptom: ~13 Leerzeilen einfügen → "*** vm: type error", (ide) danach teils tot;
JTAG zeigte Müll-bank/off (78) und später Schirm-Schrott. Host-C-Repro
(scripts/return-spam-host-main.c: echter Kern + Subset-Blob + gerätenahe Budgets,
ASan/GC_STRESS/gdb) machte die Kette sezierbar:

1. **Nicht-Tail-Listenhelfer**: %ide-lines-insert/-replace (Umbruch) und
   %ide-take-lines (Sichtfenster je Render!), %ide-lines-delete,
   %ide-buffers-remove/-names consten NACH dem Selbstaufruf -> O(Zeilen) VM-Frames.
   Fix: Akku-Muster (%ide-lines-split-at + %ide-rev-onto + *-into) — Tiefe O(1).
2. **Fehler-Verschlucken**: vm_run setzte vm_status am EINTRITT auf OK — der
   ehrliche STACKOVER innerer Läufe verschwand, NIL lief weiter ("type error"
   drei Frames später, Müll-Closure-Dispatch am Gerät). Fix: kein Entry-Reset;
   vm_check_status räumt VOR lisp_abort auf (Fehler sind klebrig).
3. **Pauschal-Frame-Reservierung**: der Guard reservierte je Frame
   nargs+nlocals+VM_MAXARGS+1 (=13 Operanden-Slots) — Tiefenbudget ~9 Frames;
   der kalte (ide)-Start (~11) lief NUR dank Schicht 2. Fix: Reservierung =
   nargs+nlocals+1; Operanden-Pushes sind einzeln PUSH-geprüft und brechen
   jetzt ehrlich ab. Typischer Frame 17->5 Slots (~3x Tiefe).
4. **Werkzeuglücke**: die D81-Lib-Suite hatte tailcall_self=[] — die
   TCO-VERIFIKATION lief für Disk-Libs nie (Compiler-TCO war aktiv, aber
   unbewacht). p0-ide-lib.json trägt jetzt die 22 Selbstrekursionen.

Beweise: Host-Repro 100 RETURNs sauber (vorher Crash #23), make check ALL PASS,
B4 pass 10/10, HW-JTAG 80 RETURNs + Exit/Re-Entry mit 80-Zeilen-Buffer grün
(vorher Crash bei ~13). Nachtrag 2026-07-08: RUN/STOP verlaesst den Editor per
`lisp_poll`/Longjmp; deshalb muss der aktive Buffer vor jedem blockierenden
`read-key` persistiert werden, nicht erst beim normalen `ide-run`-Return.
Kein Scrolling ab Zeile 24 = separater offener Punkt.

## Runde 4: Scrolling (2026-07-07, Nutzerauftrag)

row-offset war im State verkabelt (alle Leser vorhanden), wurde aber nie gesetzt —
ab Zeile 24 schrieb man unsichtbar. Fix: %ide-scrolled clampt den Offset VOR jedem
Render (Cursor sichtbar im Body); der Versatz macht alle Zeilen un-eq -> der
bestehende Dirty-Vergleich erledigt den Voll-Redraw, der Fast-Path bleibt fuer
Nicht-Scroll-Tasten unberuehrt. +2 Symbole, Host-Case ide-scroll-clamp,
type-render-5-Budget 12400->12700 (Clamp-Kosten je Render). HW-JTAG: 30 Zeilen
tief tippen -> Ansicht folgt; 32x Cursor-hoch -> Zeile 1 wieder oben. B4 10/10.
Bekannter Punkt: Scroll-Schritt = Voll-Redraw (~25 Zeilen) — fluessiger machen
(DMA-Zeilenschieber) ist ein separater Optimierungskandidat.

Nachtrag 2026-07-09: Statusline-Zeilennummer (`L<n>`) hebt den aktuellen
`ide-type-render-5`-Cap weiter auf `13000`; nach Accessor-Reclaim im
Statusline-/Cache-Pfad liegt der Ist-Wert bei `12813`.

**Nachtrag Scroll-Stale (Nutzerbefund):** Stand der Cursor in der obersten/untersten
Fensterzeile, liess ein Scroll-Schritt cursor-row unveraendert -> der Fast-Path
malte nur die Cursor-Zeile und alle uebrigen Zeilen behielten den ALTEN, um eins
verschobenen Inhalt ("Muell-Schirm"). Fix: %ide-state-with-row-offset invalidiert
den Render-Cache (render-lines nil) -> Offset-Wechsel erzwingt den Slow-Path mit
Voll-Redraw. HW-verifiziert mit 40 nummerierten Zeilen (Randscroll beidseitig,
Zeilenfolge konsekutiv). Host-Case im ide-scroll-clamp erweitert.

## Runde 5: Scroll-Zeichenmuell = Stack-Overflow durch Extra-Frame (Nutzerbefund)

**Nachtrag 2026-07-08:** Dieser Abschnitt dokumentiert den historischen Diagnosepfad.
Die starke "BEWEIS"-Formulierung ist durch die spaeter korrigierten HW-Beobachtungen
ueberholt: `STACK_GUARD` bleibt ein wichtiges Indiz/Diagnosewerkzeug, beweist aber nicht
mehr allein, dass der aktuelle Scroll-Muell zwingend ein `vm_run`-Stack-Overflow ist.
Render-/Adress-Bug und ungeprobter C-Leaf-Overflow bleiben offen; siehe
`docs/collaboration.md` Codex-Korrektur vom 2026-07-08.

Symptom: Cursor am oberen/unteren Fensterrand + 1 Zeile scrollen -> GANZER Schirm
voller Reverse-Video-Zufallszeichen (nicht nur eine Stale-Zeile), IDE-Loop
ueberlebt. Diagnose-Odyssee (dokumentiert, weil lehrreich):

- **Host reproduziert NIE** (normal, GC_STRESS, inkrementeller Aufbau, langer
  Buffer): die Render-Logik ist beweisbar korrekt. Der Host hat einen echten
  C-Stack fern vom Heap -> immun gegen Soft-Stack-Overflow.
- **Bisektion am Geraet**: `%ide-scrolled` = Identitaet -> KEIN Muell. Der Scroll
  ist der Ausloeser.
- **Nursery-GC aus** -> immer noch Muell: kein GC-Effekt, reine Aufruftiefe.
- **STACK_GUARD + MARGIN=400** -> Muell wurde in dieser Runde zu sauberen
  `lisp65>`-Prompts. Damals wurde das als Beweis fuer Soft-Stack-Overflow
  gelesen; nach den korrigierten 2026-07-08-Beobachtungen ist es nur noch ein
  starkes Diagnose-Indiz, das mit Watermarks an `vm_run`, `alloc()`/GC und
  `CALLPRIM` korreliert werden muss.

Wurzel: `ide-render` wickelte den Scroll-Clamp in ein WRAPPENDES Lambda
(`((lambda (state) BODY) (%ide-scrolled state rows))`) -> eine zusaetzliche
vm_run-Frame-Ebene ueber dem GANZEN Full-Redraw. Der RETURN-Split-Redraw ist auf
1338 B kalibriert, der Gap ist 1450 -> nur ~112 B Reserve. Der Extra-Frame
(~100-240 B) sprengte ihn NUR wenn row-offset>0 (Scrollen), weil dann der
Full-Redraw + Extra-Frame zusammenkommen.

Fix: Scroll-Clamp als `let*`-BINDUNG statt wrappendes Lambda -> `let*`-Slots
teilen den Frame, kein Extra-Frame. HW-verifiziert: 40 nummerierte Zeilen, hoch
UND runter gescrollt, Ansicht folgt lueckenlos konsekutiv, kein Muell. B4 10/10.

**Offene Haertung (Lane T / Bank-0):** Der Stack-Gap (1458/1450) ist rasiermesser-
duenn; JEDE kuenftige Render-Frame-Ebene kann dies reproduzieren. Empfehlung:
LISP65_STACK_GUARD im Dev-Core aktivieren (verwandelt kuenftige Ueberlaeufe in
saubere Abbrueche statt Speicher-Trampeln) — kostet Bank-0, daher Codex-Entscheid.

## Runde 6: Scroll-Crash Wurzel = O(n)-Cache-Rekonstruktion × Stack-Gap (VORERST DEAKTIVIERT)

Nach Runde 5 (let*-Fold) meldete der Nutzer WEITER Zeichenmuell: aus einem GETIPPTEN
Buffer (mit Aktive-Zeilen-Cache) 3x Cursor runter -> Muell. Tiefen-Analyse:

- Der Crash braucht row-offset>0 (durch vorheriges Scrollen). Bei row-offset=0 ist
  derselbe 40-Zeilen-Buffer sauber (Bisektion: %ide-scrolled=Identitaet -> nie Muell).
- Wurzel: `ide-buffer-lines` rekonstruiert bei einem gecachten (getippten) Buffer die
  GANZE Zeilenliste (~80 Allokationen: %ide-lines-replace + list->string+reverse) und
  wird MEHRFACH pro Render gerufen (region-lines, cursor-row, render-cursor). Bei
  row-offset>0 kommt der %ide-drop-lines-Pfad + die sichtbare Cache-Zeile dazu; die
  wiederholten O(n)-Rekonstruktionen + GC-mitten-im-Render sprengen den 1450-B-Gap.
- Messungen: HEAP_CELLS=16 (Gap +292 B) -> sauber; HEAP=24/32 + static-Puffer (wbuf/
  sympool_streq) -> immer noch Muell. Das Defizit ist ~HEAP=16-Niveau, also zu gross
  fuer Frame-Shaving allein.

**Entscheidung:** Scrolling VORERST DEAKTIVIERT (`%ide-scrolled`=Identitaet) -> stabile,
crash-freie IDE (Cursor sichtbar bis Zeile 24 wie vor dem Scroll-Feature). HW-verifiziert:
50 RETURN + 20 UP crash-frei. Der let*-Fold von ide-render (Runde 5) BLEIBT (generell
flacherer Render).

**Echter Fix (offen, naechster Schritt):** `ide-buffer-lines` EINMAL pro Render am
flachen Top berechnen und die flache Zeilenliste durch frame-lines/cursor-render faedeln
(statt mehrfacher O(n)-Rekonstruktion) -> Render wird flach + alloc-arm, dann Scrolling
wieder aktivieren. Alternativ: O(1)-DMA-Scroll (Screen-RAM-Shift + nur neue Zeile malen)
als natives Prim -> umgeht den Full-Redraw ganz. Beide brauchen eine eigene Runde.

## Runde 7: CRAM2K-Farbfix ZURÜCKGEZOGEN — bricht Disk-Lib-Laden

Der Farb-RAM-Split (obere Haelfte gelb, untere weiss) ist ein 1-KB-Fenster-Artefakt:
80x25 braucht 2000 Farbzellen, $D800 exponiert aber nur 1 KB (Grenze exakt bei
Offset 1024). Fix-Versuch: $D030 Bit0 (CRAM2K) in scr_init -> 2-KB-Fenster. Farbe wurde
einheitlich (HW-bestaetigt), ABER: **CRAM2K bricht das Disk-Lib-Laden** — `(load-lib
"ide")` -> nil, B4-Gate 2/10, save->nil. Bewiesen per Bisektion: screen.c OHNE die
$D030-Zeile -> `(load-lib "ide")` -> t. Auf dieser MEGA65 hat $D030 Bit0 einen
Nebeneffekt auf den DMA-/Bank-5-Staging-Pfad (Color-RAM ueber $DC00-$DFFF kollidiert
mit etwas im Lib-Lade-Weg). ZURUECKGEZOGEN — Funktion vor Kosmetik.

**Richtiger Farbfix (offen):** Option 2 aus der Diagnose — Farb-RAM DIREKT ueber die
28-Bit-Adresse $FF80000 beschreiben (per DMA/Fernzeiger), unabhaengig vom $D800-Fenster
und ohne $D030/CIA-Remap. scr_init fuellt dann alle 2000 Zellen; die per-Zeichen-Farb-
writes (Syntax-Highlight) muessten ebenfalls auf $FF80000+off gehen. Eigene Runde wert.

## Runde 8: Schritt A (compute-lines-once) umgesetzt — HW-Abnahme FEHLGESCHLAGEN

Der in Runde 6 empfohlene „echte Fix" ist gebaut: `ide-render` materialisiert die
Buffer-Zeilenliste EINMAL am flachen Top (let*-Slot `buffer-lines`) und faedelt sie
durch neue `*-from`-Varianten (`ide-region-lines-from`, `ide-visible-frame-lines-from`,
`ide-render-cursor-from`; `%ide-render-fast-same-row` nimmt `lines` als Parameter). Die
allok-schwere Rekonstruktion passiert damit flach (ein GC trifft flachen Stack statt der
tiefen Render-Kette) und nur noch EINMAL statt zweimal pro Render. `%ide-scrolled`
reaktiviert (flache let*-Clamp). Host-grün (p0-ide-lib 16 Fälle + alle stdlib-Subsets).

**HW-Abnahme auf echter MEGA65 (2026-07-07): der Zeichenmüll reproduziert WEITER.**
- Setup: Core `mvp-vm-stdlib-einsuite-core` + IDE-Disk-Lib (ide.ext.bin, geladen
  verifiziert: Symbolzahl 560→563 = +3 neue Funktionen), etherload+JTAG (`/dev/ttyUSB1`).
- Mechanik korrekt: bei 40 Zeilen steht der Cursor auf Buffer-Zeile 40, wird aber in der
  untersten Body-Zeile (row 23) gezeigt → `row-offset=17`, Clamp sauber, Scroll folgt.
- ABER: **3 Müll-Treffer in ~28 Scroll-Bursts** (intermittierend ~10–50 %). Zuverlässigster
  Trigger: Inhalt tippen (heißer Aktive-Zeilen-Cache) → SOFORT schnelle Cursor-Hoch/Runter-
  Wechsel bei row-offset>0. Signatur exakt wie dokumentiert: voller Schirm Zufallszeichen
  (gemessen exakt **1941** Nicht-Leer-Glyphen), obere Hälfte gelb/untere weiß (Boot-Farb-RAM
  scheint durch, vgl. Runde 7); IDE-Loop überlebt, ein Re-Render säubert.
- Deutung: der Fix hat die Frequenz stark gesenkt (Runde 6: „3× Cursor runter → Müll"),
  das ~292-B-Stack-Defizit aber NICHT geschlossen. Frame-/Allok-Shaving reicht nicht — wie
  in Runde 6 bereits vermutet.

**Müll-Detektor angepasst:** Das aktuelle `m65` (20260608) gibt 24-Bit-ANSI aus, NICHT das
alte `[7m` (Reverse-Video). Neuer Detektor: `m65 --screenshot=x.png`, Nicht-Leer-Glyphen
zählen (sauber ~20–40, Müll ~1941). PNG ist direkt inspizierbar. Beweisartefakte unter
`build/hw/ide-typed-scroll.png` (Müll) und `ide-after-40ret.png`/`ide-up25.png` (Scroll ok).

**Entscheidung damals:** Scroll-Reaktivierung wurde revertiert; der
compute-lines-once-Refactor blieb wegen Perf-Gewinn und flacherem/allok-ärmerem
Render. Historisch war danach **Runde 9 = Schritt B (O(1)-DMA-Scroll)** geplant.
Nachtrag 2026-07-08: `screen-scroll`/Plain-Redraw loesten die Root Cause nicht,
und der EDMA-nahe Pfad war footprint-rot. Die spaetere Root Cause steht in
Runde 9 und im retired Postmortem `docs/ide-scroll-diagnostics-plan.md`.

## Runde 9: Root Cause abgeschlossen — `$D800`-Farbfenster, nicht Stack

Nach Claudes REPL-A/B und IDE-HW-Smoke vom 2026-07-08 ist die Runde-8-Deutung
ueberholt: Der Scroll-Muell war kein verbleibendes Stack-/Full-Redraw-Problem,
sondern ein CPU-Farb-Store ausserhalb des 1-KB-Color-RAM-Fensters. Bei 80
Spalten landet z.B. `(screen-put-char 0 16 65 0)` mit `off=1280` auf
`$d800+1280=$dd00` und damit auf CIA2/VIC-Bank-I/O.

Abschluss:

- `src/screen.c` klemmt `scr_init`, `scr_put_at` und `scr_write_span` per
  `CRAM_WINDOW=1024` strikt auf `$d800-$dbff`.
- `%ide-scrolled` ist wieder aktiv. Der HW-Scroll-Smoke mit 30 Zeilen echtem
  Lisp-Code, Highlighting und `row-offset>0` lief sauber: kein Muell, kein
  Magenta.
- Repo-Nachzug: Scrolling vergroessert das Full-Blob knapp; `einsuite-full`
  nutzt deshalb `SYMPOOL_EXT_OFF=$b000`, analog zu `fasl`/`core`.

Offen bleibt nur Kosmetik/Robustheit: volle Per-Zelle-Farbe fuer Zeilen >=13
braucht einen separat gegateten EDMA-/28-bit-Farbpfad nach `$ff80000`; der
bekannte IDE-`out of memory`-Abbruch bei viel Tippen ist ein eigenes Heap-/GC-
Thema und nicht der Scroll-Muell.
