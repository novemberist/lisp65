# lisp65 — MVP-HW-Befunde (Voll-Suite-Validierung, 2026-07-01)

Ergebnisse der Validierung der eingebetteten Bytecode-Stdlib gegen die 116 goldenen Fälle
(host + echte MEGA65). Der MVP läuft end-to-end auf HW (`length`/`nth`/variadisches `list`/
`reverse` grün); diese Notiz hält die tieferen Befunde fest.

## 4 echte Bugs gefunden + gefixt (via 116-Fälle-Host-Suite → committed)
Der 4-Funktionen-Test hätte keinen gefunden; erst die volle Suite deckte sie auf:
1. **`function`-Special-Form** rief `sym_function` auf eine **Form** bei `(function (lambda …))`
   (`#'(lambda …)`) → Crash. Fix: Symbol→`sym_function`, sonst evaluieren (Closure).
2. **CALLPRIM Reload-on-return:** `funcall`/`apply` (Prim 7/8) können re-entrant die VM clobbern;
   `vm_codebuf` wird jetzt nach `vm_callprim` nachgeladen (wie `CALL`).
3. **`apply` Funktions-Designator:** `(apply (function mapcar) …)` übergibt das **Symbol**;
   `apply` löst jetzt Symbol→`sym_function` auf (CL-korrekt) → `mapcar`/`append`/… via `apply`.
4. **`numberp`/`symbolp` als Tree-Walker-Primitive** (waren nur VM-CALLPRIM) → `(function numberp)`
   auflösbar → `remove-if`/`find-if`/`count-if`/`position-if`.
Danach: **109/116 host**. Der Interpreter ist **GC-korrekt** (host unter `-DGC_STRESS`, exakte
HW-Konfig, isoliert + in Sequenz — alles sauber).

## Geschlossen 2026-07-03: Native-REPL-Surface
`when`/`unless`/`let*` waren bereits Tree-Walker-Special-Forms; `case` ist jetzt dieselbe
MVP-Footprint-Ausnahme. Die sechs frueheren REPL-Repros sind aus
`tests/bytecode/runtime/p0-runtime-known-open.json` entfernt und laufen aktiv in
`make repl-surface-smoke`.

## Offen 1 (ECHT, HW-only): Higher-Order-Sequenz-Hang
**Symptom:** In einer langen Sequenz *variierender* Fälle hängt der ~11. Fall (z. B. `every`/`some`)
auf echter MEGA65 (interne Endlosschleife). **Erschöpfend eingegrenzt:**
- Host (auch GC-Stress, exakte HW-Konfig): `every`/`some` **grün** → kein Interpreter-Fehler.
- HW isoliert: `every` **grün**; 30× derselbe simple eval **grün** → kein Leck pro eval.
- `every` entfernt → `some` hängt an **derselben Position** → **positions-/heap-timing-abhängig**,
  nicht funktionsspezifisch. Fehler wandert mit der Heap-Größe (512→Hang@10, 720→Fehler@9).
- Es ist die Residual-Manifestation der bekannten **HW/xemu-Divergenz** im DMA-/tiefen-Re-Entrancy-
  Pfad (xemu grün, HW rot; vgl. `docs/mega65-extram-access.md`).
**Nicht weiter auflösbar ohne Speicher-Readback** (m65 über USB-UART — vom User ausgeschlossen,
Hardware-Umbau nötig). xemu-nativ ist hier zu flaky/langsam + Dump-Catch-22 (Sink erzwingt kleineren
Heap, der das Timing verschiebt; hängt es, kein sauberer Exit → kein Dump). **Kandidat für eine
spätere Readback-Sitzung.** Diagnose-Werkzeug dafür ist eingebaut: `-DVM_STEP_LIMIT=N` (Watchdog,
wandelt Endlos-VM-Schleifen in `VM_STEPLIMIT`). Die fokussierten Known-Open-Repros stehen ebenfalls
in `tests/bytecode/runtime/p0-runtime-known-open.json`.

## Offen 2 (Footprint): Bank-0-Profil bleibt eng
Der Multi-Listen-`mapcar` (`(mapcar #'+ l1 l2)`) brauchte mehr als `HEAP_CELLS=512`
(host wie HW); das Profil wurde damals auf `HEAP_CELLS=544` angehoben. Nach der
Post-MVP-P1-Stdlib-Breite (118 eingebettete Bytecode-Funktionen) passt das native
MVP-PRG aber nur mit kleinerem hot Heap wieder unter den harten Stack-Gap-Check:
`HEAP_CELLS=320`, `heap_start=0xcaa2`, `stack_gap_bytes=1374`,
`min_stack_gap_bytes=1200`, `MAX_SYM=144`, `NAMEPOOL=1280`, `GC_ROOTS=48`,
`LISP65_MARK_BITMAP`. Das ist ein Produkt-Tradeoff bis zum groesseren Heap-/Code-
Speichermodell; echte-HW-Validierung der neuen 118-Fn-Breite bleibt separat.

## Lektion (Test-Harness)
Vergleichs-Harnesses müssen das Ergebnis `got` **rooten**, während der erwartete Wert evaluiert wird
(`GC_PUSH(got)` vor `eval(want)`) — sonst sammelt GC unter Druck `got` ein. Ein ungerooteter Harness
hat hier die frühe HW-Fehlersuche verfälscht.

---

## NACHTSITZUNG 2026-07-01/02: Die GC-Freeze-Jagd — Endbefund

**Kernbefund: `gc_collect`/`gc_mark` ist auf echter MEGA65-Hardware (llvm-mos mega65-Target)
noch NIE erfolgreich gelaufen.** Der Interpreter stirbt deterministisch beim ERSTEN
`gc_mark`-Aufruf. Alle grünen HW-Läufe (MVP-Test, hwwm-11) hatten schlicht genug Heap,
dass nie ein GC feuerte. Jeder „wandernde" Fehler dieser Sitzung = der Moment, in dem die
Freelist erstmals leer wurde (heap-/build-abhängig) — plus Farb-Fehllesung (lila=4 vs pink=10),
die tagelang ein Phantom-“Pointer-Mysterium” erzeugte.

**Minimal-Repro (`docs/gcrepro-mega65.c`, 2,6 KB PRG):** `eval_init()` (31 Prims, kein Stdlib,
keine DMA, kein Reader) + `gc_collect()` → dauerhaft gelber Rahmen = Freeze. HW-bestätigt.

**Systematisch entlastet (jeweils per HW-Experiment):** etherload-Transfer (Blocksummen 0-8
byte-identisch mit PRG-Datei), E-/W-Tabellen + variable Indizierung (Grid-Dump = Soll),
DMA-Staging (GC stirbt auch VOR jeder DMA), KERNAL-IRQ (sei), Netzwerk/Listener (Kabel gezogen),
Soft-Stack (Watermark ~366 B bei ≥1,3 KB Lücke), Jump-Tables (-fno-jump-tables), memory-Clobber,
Register-Trigger, mem.c-Optimierungsstufe (-Oz-LTO wie -Os-separat sterben beide).

**Feinlokalisierung:** Stempel U/V/W + Symbolindex: Tod bei s=0, erster/dritter Aufruf —
selbst mit LEEREM gc_mark-Body (Stub!) friert die Schleife ein. Verdacht damit auf
llvm-mos-mega65-Target-Spezifika (45GS02: Base-Page-Register, Extended-SP-Modus, Z-Reg) im
Zusammenspiel mit dem BASIC65/etherload-Bootzustand. WICHTIG: der damalige CI-GC-Smoke
(`xemu-prelude-gc-smoke`, inzwischen `legacy-xc64-prelude-gc-smoke`) testete das
C64-Target — der mega65-Target-GC war damals nirgends abgedeckt.

**Echte, dabei gefixte Bugs (committed):**
1. `new_symbol`: 16-bit-Wrap im NAMEPOOL-Bounds-Check (`npool+len+1`) → bei Müll-Namen
   64K-strcpy-Verwüstung möglich. Jetzt strnlen-Deckel (≤32) + wrap-sichere Prüfung.
2. `gc_mark`: fehlender Bounds-Check → `MARK_SET` schrieb bei korruptem obj bis 32 KB hinter
   `marks[]` (Speicher-Schrotschuss). Jetzt Guard + `gc_badobj`-Zähler.
3. `intern`: libc-`strcmp` ersetzt durch `sym_streq` (Verdachtsentlastung + simplerer Codegen).
4. Diagnose-Infrastruktur (alles gegated `LISP65_HEARTBEAT`/`VM_STEP_LIMIT`/`GC_MARK_STUB`):
   Heartbeat-Ticker, Last-Action-Stempel (inkl. GC-Phasen Q/R/S/T + Symbolindex), Watchdog
   mit pc/op/off-Capture, `sym_pool_used()`.

**Nächste Schritte:**
- Repro in xemu-mega65 reproduzieren (dann offline debugbar; xemu war heute zu flaky) —
  sonst Disassembly von `gc_mark` + Statement-Bisektion am Gerät (Repro ist jetzt 5-Sekunden-Zyklus).
- Bei Bestätigung: Upstream-Report an llvm-mos (+ ggf. MEGA65-Core) mit `gcrepro-mega65.c`.
- MVP-Interim: Heap so dimensionieren, dass GC nicht feuert (de-facto heutiger Zustand) ODER
  GC für mega65 in Inline-Asm/anderer Struktur reimplementieren.
- Stack-Budget-Lektion bleibt gültig: Linker reserviert NULL Stack (`__stack=0xd000`, Region bis
  $D000); jedes Build MUSS die Lücke prüfen (Map: `__heap_start`; ≥1,2 KB für tiefe Ketten).

## LÖSUNG (2026-07-02, ~00:15): Fixpoint-Sweep-Marking — GC LÄUFT AUF HW 🟢

Der GC wurde strukturell neu geschrieben (`mem.c`): statt Markstack-Traversierung
(`gc_mark` mit `markstack[256]`) markiert `gc_collect` jetzt per **Fixpunkt-Iteration
über flache Voll-Scans des Heap-Arrays** (`gc_mark1` markiert einzelne objs ohne
Nachfolger; eine do/while-Schleife propagiert Kind-Markierungen bis nichts mehr
dazukommt). Nur einfachste Schleifen/Array-Zugriffe — die Konstruktklasse, die auf
der HW nachweislich trägt. Kosten O(HEAP_CELLS·Kettentiefe) ≈ ms-Bereich bei ≤512 Zellen.

**HW-bestätigt:** (1) Minimal-Repro grün (erster erfolgreicher GC der Projektgeschichte);
(2) volle 18-Fälle-Suite mit 2 erzwungenen Boot-GCs + organischen GCs bei HEAP=320:
**ALL 18 PASS** — inklusive `every`/`some`, dem Ausgangspunkt der ganzen Jagd.
Host: vm-smoke 11/11, 18/19, GC_STRESS 18/19, embed-116 109/116.

Hinweise: Die alte Markstack-`gc_mark` bleibt (ungenutzt) im File — für einen späteren
llvm-mos-Upstream-Report ist der Freeze über die git-History + `docs/gcrepro-mega65.c`
reproduzierbar (Commit vor diesem Fix auschecken). Das Fixpoint-Marking traversiert
NUR den Hot-Heap (heap[] direkt) — der tote EXT_HEAP-Pfad bräuchte cell_*-Accessoren.

## GC-HÄRTUNG (2026-07-02): Stresstest HW-bewiesen + CI-Smoke ergänzt

**HW-Stresstest bestanden** (`tools/host-lisp/gc-stress-test.c` als PRG, HEAP=320):
400 Zyklen, **4800 GCs**, `badobj=0` — die gerootete lebende Liste (Länge + Prüfsumme)
war nach jedem einzelnen GC intakt. Die GC-Zahl ist **identisch mit dem Host** (4800) →
Gerät und Host verhalten sich beim GC bit-für-bit gleich. Damit ist der Fixpoint-Sweep-GC
nicht nur „läuft mal", sondern unter Dauerdruck verifiziert.

**CI-Lücke geschlossen:** `scripts/gc-smoke-main.c` + `make gc-smoke` (jetzt Teil von
`make check`). Minimal-Link (mem/symbol/interrupt), embed-frei; hält lebende Liste +
interne Symbole über viele GCs korrekt. Host: HEAP=320 PASS (401 GCs), HEAP=120 PASS
(6801 GCs — GC bei fast jedem cons). Bisher testete nur `legacy-xc64-prelude-gc-smoke`
das C64-Target — der mega65-GC war nirgends abgedeckt (genau das versteckte den Freeze).

## PLATTFORM-BEFUND (2026-07-02): KERNAL-Scroll crasht JEDES llvm-mos-PRG

**HW-isoliert bewiesen** (336-Byte-PRG ohne Lisp): Sobald CHROUT den Bildschirm scrollen
laesst (Ausgabe unter Zeile 25), stuerzt die Maschine ab (schwarzer Schirm). Betrifft
JEDES mos-mega65-clang-PRG — vermutlich Editor-Interna vs. unmap-basic. Symptom im REPL:
Absturz exakt nach ~8 Eingaben (Schirm voll).

**Workaround (Lane K, committed):** nie scrollen — `screen_scroll_guard()` (printer.c)
loescht den Schirm (CLR $93) bei >=22 gezaehlten Zeilen, aufgerufen NACH der Eingabe/vor
der Ausgabe (letzte Ausgabe bleibt beim Tippen sichtbar). CLR ist HW-bestaetigt crashfrei.
**⚠ Fuer alle kuenftigen Test-/Ship-PRGs:** keine CHROUT-Ausgabe ueber Schirmhoehe ohne
Guard.

## REPL-UX (2026-07-02, Lane K): History + Eingabe-Robustheit
- 1-Eintrag-History (CRSR-hoch/Ctrl+P), HIST_MAX=120 (Bank-0-Budget), editierbar per DEL.
- Unbehandelte Steuercodes (Cursor-Tasten etc.) werden ignoriert statt in den Puffer
  geschrieben (BASIC-Gewohnheit "uebertippen" desynct sonst Puffer<->Bildschirm ->
  Geister-Formen). Zeilen-Editor/Multi-History = IDE-Territorium (Lane L).
Alles am Geraet user-getestet (inkl. Scroll-Guard-UX).
