# LISP 64 v2 — Architektur-Referenz

Stand: 2026-06-24 · **konsolidierte technische Referenz** (implementierungsnah).
Diese Datei bündelt den dauerhaften technischen Wissensstand. Punkt-in-Zeit-Audits,
Handoffs und Experiment-Logs früherer Sessions wurden entfernt; sie bleiben über die
Git-History abrufbar. Sprach-/Nutzersicht: `language-reference.md`. Plan & Phasen:
`roadmap.md`, `development-plan.md`.

## 1. Quellbaum & Build

- `src/reference/` — handgepflegter Port, **byte-identisch** zum Original-D64-PRG.
  Guard: `make reference-src-compare` (muss immer grün bleiben).
- `src/v2/` — der bearbeitbare Port. Hauptdatei `src/v2/main.acme`, Module
  `src/v2/modules/00-equates … 20-bytecode-vm`. Reihenfolge ist GC-relevant
  (siehe §3).
- `lisp/` — ladbare Lisp-Bibliotheken + Smoke-Fixtures (nicht resident).
- `tools/host-lisp/` — Host-Referenzinterpreter & Modelle (kein Emulator-Ersatz):
  `lisp64.py` (Dialekt-Semantik), `vm-model.py` (Bytecode-VM-Oracle),
  `compact-model.py` (Heap-Layout), u.a.
- Assembler: **ACME**, `-f plain`, via `distrobox-enter arch -e acme`. Verdikt
  ACME vs. 64tass und Makro-Strategie: Git-History `docs/assembler-choice.md`.

Tests laufen als VICE-Screenshot-Smokes (`make <ziel>-screenshot`) mit
Negativ-Zwillingen; viele Build-Varianten sind hinter `-D TERM_TEST_*`-Flags
isoliert, sodass der Default-REPL-Build unberührt bleibt.

## 2. Speicherkarte (C64)

| Bereich | Nutzung in v2 |
| --- | --- |
| `$0000–$00FF` | Zero-Page: Interpreter-Zeiger (`NextPtr`/`NodePtr`/`StringPtr`/`W2`/`ACC32`…), VM-Register |
| `$0100–$01FF` | 6502-Stack |
| `$0200–$0258` | `lBUF` Zeilen-Eingabepuffer (~88 B; nächstes Symbol `lLAT=$0259`) |
| `$0400–$07E7` | Textbildschirm (direkte VIC-Ausgabe via `TermChrOut`) |
| `$07F0+` | `READBUF` (Atom-/Token-Puffer) |
| `$0900–$0911` | Konfigurationsworte (`EndOfProgPtr`, `FSLTOP`, `HashBasePtr=$0910`, Stack-Pointer…) |
| `$0912 …` | `HashBase` (= nil/leere-Liste-Sentinel) + 32 Hash-Ketten (OBLIST) |
| `$0801–$CFF0` | PRG, Interpreter, statische Knoten, dann Freispeicherliste bis `FSLTOP` |
| `$E000+` / `$FFFE↓` | Daten-/Adressstack im `KERNAL_RAM_REPL`-Build (RAM unter Kernal-ROM) |

Default-Heap im normalen v2-Testbuild ~7.2–7.3k freie Knoten; `KERNAL_RAM_REPL`
~8.2–8.3k (819 zusätzliche Zellen `$E000–$EFFA`). Genaue Zahl wandert mit der
Codegröße, weil `EndOfProg` nach hinten rückt.

## 3. Knoten-Layout & GC

**5-Byte-Knoten** (aktiv, „Classic5"):

| Offset | Feld | Konstante |
| --- | --- | --- |
| 0–1 | Car / Data | `NodeDataOffset = 0` |
| 2–3 | Cdr / Next | `NodeNextOffset = 2` |
| 4 | Flag/Typ-Nibble | `NodeFlagOffset = 4`, `NodeTypeMask = $0F` |
| 5+ | Atom-Name (bei Symbolen) | — |

`NodeSize = 5`. Typ im Flag-Nibble: u.a. user-defined Atom (Flag-Pfad `1`),
nil/Cons-Erkennung über **Adressvergleich mit `HashBase`** (`$0912`), nicht über
Typinfo.

**GC** (Mark/Sweep, `10-garbage-collector.acme`): `DoGC1` läuft von `NodeList`
(in `16-oblist-system-nodes.acme`) in 5-Byte-Schritten bis `FSLTOP`. **Invariante:**
zwischen `NodeList` und `EndOfProg` darf **kein** Code und keine beliebige Variable
liegen — nur statische 5-Byte-Lisp-Knoten. Darum: normale Module **vor**
`16-oblist-system-nodes.acme`; `17-end-trampoline.acme` definiert `EndOfProg`
danach. Guard: `make kernal-ram-layout-audit`.

**Verdichtung:** Aktiv ist **Classic5** (5 B/Cons). Die Page/Compact2-Abstraktion
(2-Byte-Zelle + Data-Sidecar) existiert nur als Experiment-Build.

**Status der Cons-Layout-Frage:** Compact2 ist **build-gemessen verworfen**; Classic5
bleibt der Produkt-Default. Ein 4-Byte-Hauptheap ist nur noch als separates
Object-Model-/Encoding-Projekt offen, nicht als aktueller Default-Kandidat.

*Compact2 — belegt (N4-Realbuild, 2026-06-24, reproduziert):*
- `page-experiment-audit`: Main-Heap `6806` Nodes, PRG `15396` B
- `page-experiment-compact2-audit`: Main-Heap `6312` Nodes, PRG `16330` B
  (**+934 B residenter Code**) + Sidecar `$C300-$C6FF` (`1024` B)
- Workload: `7084` vs `6977` freie Nodes; Capacity: `7588` vs `7481` (alle ≤ Default)

→ Compact2s Maschinerie kostet mehr residenten Speicher, als die Packung einspart;
auf realen Builds **kein** Verdichtungsgewinn. Damit als Dichte-Pfad raus.

*Host-Profile — belegt (A2/N2, 2026-06-24/28):*
- cons-lastiger Mix: 2432 Cons; 4-Byte spart 2432 B gegen Classic5, Compact2 bleibt
  +1280 B schlechter als 4-Byte
- symbol-/plist-lastiger Mix: 786 Cons, 21 Symbole, 40 Plist-Einträge; 4-Byte spart
  786 B gegen Classic5, Compact2 bleibt ebenfalls +1280 B schlechter als 4-Byte

*Was das NICHT belegt:* Die Messung läuft auf dem Page-Experiment-Scaffold, das nur
die **Dynamic-Pages** umstellt — der Hauptheap bleibt in allen Builds Classic5. Der
`page-experiment-classic4`-Build (4-Byte-Dynamic-Node) assembliert sauber, hat aber
dasselbe PRG/Main-Heap wie Default; ein **4-Byte-Cons-Hauptheap** ist damit *nicht*
gemessen. Ob 4-Byte (5→4 B/Cons, Immediate-Fixnums, ohne Sidecar) den Hauptheap
real verbessert, bleibt offen, ebenso die **CPU-Indirektionskosten** (auf C64 nicht
gemessen). 4-Byte ist die plausible Richtung, nicht eine belegte Entscheidung
(`development-plan.md` N4/P0).

*Readiness-Report (2026-06-28):* `make page-experiment-mainheap-classic4-readiness-report`
belegt die aktuelle Lücke: Mainheap $440D-$C8FA = 34030 B = 6806 Classic5-Zellen;
dieselbe Byte-Range ergäbe theoretisch 8507 4-Byte-Zellen (+1701), mit statischem
OBLIST-Repack 8543 (+1737). Das ist eine Obergrenze und ersetzt keinen echten
4-Byte-Hauptheap-Build.
`make page-experiment-mainheap-classic4-static-oblist-report` präzisiert den
statischen Anteil: 146 `n...`-Source-Kandidaten, davon 127 im aktuellen Build
aktiv und 19 gegatet/inaktiv; die kopierte `NodeList`-Zone bleibt separat
$413D-$440C = 720 B = 144 Classic5-Zellen. Ein 4-Byte-Repack dieser kopierten Zone
spart 144 B und verschiebt `EndOfProg` rechnerisch nach $437D.

*Blocker-Inventar (2026-06-28):*
`make page-experiment-mainheap-classic4-blocker-inventory` läuft absichtlich rot,
solange ein echter 4-Byte-Hauptheap nicht implementierbar ist. Aktueller Befund:
127 harte aktive Quellinventar-Blocker — 0 verstreute Flag-/Typbyte-Zugriffe, 0
verstreute FSL-Shape-Zugriffe, 127 aktive statische `n...`-OBLIST-Definitionen
im Classic5-Format, 19 gegatete statische Kandidaten und 0 offene
Pointer-Feldkandidaten. Zusätzlich weist der Audit 4 zentrale
`type-policy-surface`-Zugriffe, 10 zentrale `mark-state-policy-surface`-Zugriffe
und 6 zentrale
`fsl-4byte-compatible`-Zugriffe in FSL-Helpern aus; die FSL-Helper schreiben nur
Data/Next innerhalb der ersten vier Bytes. Das präzisiert die nächste Arbeit:
Typ- und Mark/State-Policy ersetzen, statische Systemknoten plus kopierte
`NodeList`-Zone repacken, dann erst Realbuild messen.
Die ersten kleinen Abstraktionsschritte sind erledigt: Listen-Druck, `ATOM`,
`PopNextPtr2ACC32_1`, `PopStringPtr2ARG32_2` und `STRINGP` laufen ueber zentrale
TypeInfo-Helper statt eigener direkter Typbyte-Loads; Reader- und Numeric-Type-
Schreibstellen laufen ueber `SetNodePtrTypeInfo`; GC-Clear-Mark-Schleifen laufen
ueber `ClearNodePtrMarkerFlags`; Final-Mark-Checks und Free-State-Clears laufen
ueber `CheckMarkerFlag8`/`ClearNodePtrState`; Marker-Mask-Checks laufen ueber
`CheckNodePtrMarkerFlags`.

*State-Policy-Report (2026-06-28):*
`make page-experiment-mainheap-classic4-policy-report` quantifiziert, was eine
Ersatzstruktur fuer das verlorene Flagbyte kostet. Ein voller 1-Byte-State-Sidecar
ergibt in derselben Mainheap-Range wieder nur 6806 Zellen (+0). Gepackter
Typ-Nibble plus zwei Markbits ergibt 7164 Zellen (+358), aber noch ohne Code-/CPU-
Kosten. Der volle Rohgewinn 8507 Zellen (+1701) bleibt nur bei cons-only 4-Byte-
Zellen mit tagged immediates oder separater Speicherung fuer Zahlen/Strings/Systemknoten.
Auch wenn die kopierte statische Node-Zone vorab auf 4-Byte-Zellen repacked wuerde,
verschiebt sich diese Entscheidung nicht: Der 1-Byte-Sidecar-Pfad steigt nur auf
6834 Zellen (+28), Typ-Nibble plus zwei Markbits auf 7194 (+388), waehrend der
cons-only/Rohpfad 8543 Zellen (+1737) erreicht.

*Assembly-Probe (2026-06-28):*
`make page-experiment-mainheap-classic4-probe-report` baut einen separaten
`LISP64_MAINHEAP_CLASSIC4_PROBE`-Stand mit `NodeSize=4` fuer den Hauptheap. Er
assembliert und zeigt die rohe Geometrie: PRG 15396 B (+0), Mainheap 8508 statt
6806 Zellen (+1702), KERNAL-Heap 1023 statt 819 Zellen (+204). Der Probe ist
ausdruecklich **nicht lauffaehig als Classic4-Hauptheap**: `NodeFlagOffset=4` liegt
ausserhalb der Zelle, die statische Node-Zone ist nicht repacked, und
Flag/Typ/Mark-State plus GC-Policy fehlen.

*Decision-Report (2026-06-28):*
`make page-experiment-mainheap-classic4-decision-report` fasst die N4-Evidenz als
Gate zusammen. Status ist `KEEP-CLASSIC5-DEFAULT`: Der bestehende Classic4-Build ist
Dynamic-Pages-only, der Probe verliert das Inline-Flagbyte, die kopierte Static-Zone
ist nicht repacked, 127 aktive `n...`-Records brauchen eine Classic4-Kodierung, und
es gibt keine lauffaehige C64-GC-/Free-Node-/CPU-Messbasis fuer Mainheap-Classic4.
Damit ist N4 fuer den aktuellen Produktpfad entschieden; 4-Byte braucht zuerst
Policy- und Static-Encoding, nicht einen breiten Rewrite.

## 4. Reader & Loader

**Reader** (`03-line-input.acme`, `04-reader-allocator.acme`):
`hREAD` → `hRead1` dispatcht `(`/`'`/Atom; Atome akkumuliert `ReadNextLine` in
`READBUF`. Zeichen kommen via `GetNextNoWhiteSpaceChar`/`GetNextFromLBuf` aus
`lBUF`, das `InputLine` füllt.

**lBUF-Chunk-Grenze (wichtig):** `lBUF` liegt bei `$0200`; der naechste bekannte
Puffer `lLAT` beginnt bei `$0259`. `InputLine` liest deshalb pro Aufruf
**max. 88 Nutzzeichen** (`InputLineLimit = 88`) und legt den Nullterminator bei
`lBUF+88` ab, direkt vor `lLAT`. Bei Datei-Input fuellt `InputLine` bei
Bedarf nach. `ReadNextLine` setzt seit dem Fix (2026-06-24) ein Atom über die
Chunk-Grenze fort, wenn die Null mitten im Atom auftritt **und** der Chunk an der
Grenze abgeschnitten war (`InputLength == InputLineLimit`, Datei-Input) — via
`ReadNextLineRefill` → `ReadNextLineDelim`. Der String-Literal-Pfad
`ReadNextLine4` nutzt dieselbe Refill-Logik über `ReadNextLine4Refill` und setzt
`"…"`-Literals über dieselbe Grenze fort. Vorher wurden Atome an der Chunk-Grenze
gespalten (`'SHAPE` → `(QUOTE S) HAPE`). Verifiziert ist Atom+String mit dem SAVE-Format-Smoke
`phase6-stage3-r1-chunk-boundary-savefmt-*` (D64-Readback + VICE-Screenshot).

**LOAD-Pfad:** `hLOAD` (`15-file-editor-primitives.acme`) → `S2E21`-Schleife:
`hREAD` liest eine Form, `sub_26F5` (`12-core-primitives.acme`) verarbeitet sie als
SAVE-Format-Record `(NAME KEY VALUE)` via `hPUTPROP`. **Kein** `CallEval`/`hDE`-Pfad
— d.h. normales Source-`LOAD` evaluiert `DE`-Formen sichtbar, **persistiert sie aber
nicht** für nachfolgende REPL-Aufrufe. Bibliotheken werden daher über SAVE-Format
oder Cross-Compile-Expansion geladen (siehe §6, `development-plan.md`).

## 5. Evaluator, Apply & TCO

`08-eval-apply.acme`: `hEVAL` klassifiziert (Atom/Zahl/Cons), `hEVAL7…` löst
Funktionsköpfe über die Plist (`EXPR`/`FEXPR`/Handler) auf. `hAPPLY`/`hAPPLY2`
appliziert; `S1508` ist der Lambda-Anwendungspfad (Bindungsframe via `sub_149D`,
Body-Schleife `loc_151D`). Dynamisches Scoping: Bindungen hängen an `HashBasePtr`,
`DoUNBIND` baut sie ab.

**TCO** (mehrstufig, Phase 2): letzter `COND`-Zweig springt direkt nach `hEVAL`
(`hCOND6`); `S1508` markiert den letzten Body-Ausdruck als Tail-Kontext über
`TailEvalFlag`; `hEVAL10` wertet Argumente noch im aktuellen Binding, verwirft die
wartende Rückkehradresse, `DoUNBIND` + direkt nach `hAPPLY`. Baseline
`(G 20 0)` → `ASTACK TAIL 18`; `PROGN`/`PROG`-Tails ebenfalls beschränkt.
**Fix (2026-06-24):** `hPROG` setzt `TailEvalFlag` vor der Body-Auswertung zurück,
damit ein vom letzten Lambda-Body gesetztes Tail-Flag nicht in die PROG-Formen
leckt (sonst stoppte ein PROG-Body nach der ersten Form). Guards:
`make kernal-ram-tailrec-test-screenshot`, `…-progn-tailrec-…`.

## 6. Dispatch & Mini-CLOS (Single-Dispatch)

Ladbarer CLOS-Kern (host-validiert, nativ via SAVE-Format/Cross-Compile belegt):

- Klassenhierarchie über Property `CSUP` (Superklasse); Methodentabelle über
  Property `CMETH` (Alist `(klasse . methode)`).
- `CPREC` baut die Präzedenzliste (`(C SUPER… T)`), `CFIND` sucht per `ASSOC`,
  `CDISPATCH` wählt + `APPLY`t die Methode, `CADD` registriert, `CSLOT`/`CSETSLOT`
  greifen auf Instanz-Slots zu.
- **Cross-Compile-Pipeline:** `scripts/lower-mini-clos-to-c64-dispatch.py` lowert
  host-expandierte Mini-CLOS-Formen auf kurze C64-Namen **und** löst
  `MCLOS-DEFINE-CLASS/METHOD` zu **konstanten** `PUTPROP`-Setup-Formen + Dispatcher-
  `DE`s auf (keine param-basierte Property-Akkumulation im LOAD-Lambda-Pfad).
  Zusammen mit `lisp/clos-crosscompile-c64-runtime.lsp` und
  `scripts/make-c64-save-format-fixture.py` erzeugt das den D64-Smoke.
- **Verifiziert (2026-06-24):** `(CXTEST)` → **CXPASS**, `(MCLOSTEST)` → **CDPASS**.
- Multiple Dispatch / volles MOP sind bewusst ausgeschlossen (8-Bit-Kosten).

## 7. Bytecode-VM (Phase 4)

`20-bytecode-vm.acme`. Vollständige Spezifikation: **`bytecode-v1.md`**.

- **Stack-VM mit ~50 Opcodes** (0–44 v1-Kern eingefroren: Arithmetik, Vergleiche,
  Branch `JmpRel`/`JFalseRel`, `CallRoot1/2/3`, `TailSelf1/2/3`, `PushArg0-2`,
  `PushLit*`, `Nil`/`T`/`Not`; 45–50 provisorisch: `PushObj`/`LoadL`/`StoreL`/
  `Drop`/`Closure`/`CallClosure1` für Phase 6). Code-Objekt: Tag `$B4` + Länge +
  Literal-Ptr + Payload. Opcode-Tabelle ist drift-geprüft
  (`phase4_disasm.py --check-acme` → `Drift: 0`).
- **Live-REPL-Hybrid existiert und funktioniert** — hinter
  `TERM_TEST_PHASE4_VM_REPL_DISPATCH` (`06-init-repl.acme:923`):
  `Phase4ReplReadFormIsOwned` lässt `(DE …)` vom VM-Pfad **kompilieren**, Aufrufe
  an bereits kompilierte Code-Roots über die VM **ausführen**, und fällt für alles
  andere sauber auf den Tree-Walker (`CallEval`) zurück. Default bleibt der
  Tree-Walker (Flag aus).
- **Transparenz vollständig (C2→C6, 2026-06-28):** kompilierbare `(DE …)` → VM;
  nicht unterstützte (Mehrform-Body, >3 Params, `PROG`, …) fallen sauber auf den
  Tree-Walker zurück (C3); **Tree-Walker↔VM-Cross-Calls** funktionieren in beiden
  Richtungen (C4: `Phase4TreeWalkerVMCallBridge`, Args via `CallEval`, Ergebnis via
  `hDONE`); VM-`DE` druckt den Namen wie der Tree-Walker. Voll-Regression grün,
  `reference-src-compare` byte-identisch. Coverage-Grenzen + Beispiele: `bytecode-v1.md`.
- **Footprint (gemessen):** Dispatch kostet ~0 (Code-Heap 96 B); der VM-Block
  (Engine+Compiler+Smokes, ein Flag) ~7200 Nodes, davon **~47 % Smoke-Scaffolding**.
- **Flag-Split abgeschlossen (2026-06-28):** `TERM_TEST_PHASE4_VM_ENGINE` baut jetzt
  ein REPL-Dispatch-Engine-Profil ohne das Legacy-Testprofil `TERM_TEST_PHASE4_VM`.
  Das Legacy-Flag setzt intern weiterhin Engine + `TERM_TEST_PHASE4_VM_SMOKE_SCAFFOLD`,
  damit bestehende Smokes kompatibel bleiben. `make phase4-vm-engine-footprint-report`
  zeigt: Engine-only spart 20571 B gegen Legacy und enthaelt 0 `Smoke`-Symbole.
  Vor einem Default-Flip fehlt damit nicht mehr der Split, sondern die reale
  C64-Freenode-/N4-Messung.

**Offen — nur noch eine Produkt-Entscheidung (kein Korrektheits-Blocker):** den
Default-Flip vornehmen. Vorbedingungen: (a) **Flag-Split** (Smoke vom Engine trennen
→ ~47 % Footprint zurück), (b) breitere Compiler-Coverage (C5). Erst danach lohnt der
Flip; darauf der Schnitt dynamisch→lexikalisch (Phase 6 Stufe 2). Siehe
`development-plan.md` (C6/A).

## 8. Hardware-Brücken (Phase 5)

`peek`/`poke`/`sys` als Leaf-Primitive vorhanden (VM-unabhängig). `GETKEY`
(`hGETKEY` → `TermGetIn` → PETSCII) ist nativ, **guarded** hinter
`TERM_TEST_PHASE5_GETKEY_NATIVE`, Default byte-identisch. **VICE-Smoke ✅** (2026-06-28,
`make phase5-getkey-native-c64-smoke-test-screenshot`): Test-Mechanik —
unter `TERM_TEST_KEYS` liest `GETKEY` aus demselben `TermTestKeys`-Stream wie der
REPL (`TermReadKeyboardTest`), die „Taste" steht direkt hinter `(GETKEY)` im Skript;
verifiziert `(GETKEY)`→65 (Taste `A`), leerer Puffer→0. **SID-Ton per POKE-Smoke ✅**
(`make phase5-sid-script-test-screenshot`): setzt Volume, Attack/Decay,
Sustain/Release, Frequenz und Gate/Triangle; OSC3/Random-Readback an `$D41B`
ändert sich (`40`, dann `90`), Marker `SIDOK`. **SID-VOICE nativ gegated ✅**
(`TERM_TEST_PHASE5_SID_VOICE_NATIVE`, `make phase5-sid-voice-native-script-test-screenshot`):
setzt eine SID-Stimme als Registerbuendel; Readback belegt Frequenz `40`, Volume
`15`, Control `33`, ADSR `9/240`, bewegtes `$D41B`, Marker `SIVOK`; Footprint im
Testbuild +158 Bytes gegen den POKE-SID-Smoke, freie Nodes 8195. **VIC-Sprite per POKE** auf dem Gerät
sichtbar (`make phase5-sprite-script-test-screenshot`): poke-basierter Smoke (kein
residenter Code) — füllt Sprite-Daten ($0340) per `PROG`/`GO`-Schleife, setzt
VIC-Register, Datenfüllung per `(PEEK 832)`→255 belegt. **SPRITE nativ gegated ✅**
(`TERM_TEST_PHASE5_SPRITE_NATIVE`, `make phase5-sprite-native-script-test-screenshot`):
setzt X/Y, `$D010`, Pointer, Farbe und `$D015`; NIL loescht X-MSB/Enable; Marker
`SPNOK`; Footprint im Testbuild +293 Bytes gegen den POKE-Sprite-Smoke, freie Nodes
8156 statt 8215. **Native** Komfort-Primitive (`SID-VOICE`, `SPRITE`) sind damit als
gegated Leaf-Buendel vorhanden; Scope-Regel bleibt: alles, was per `POKE`/ladbarer
Lib reicht, bleibt zunächst außerhalb des residenten Kerns.
Der konkrete B5-Entwurf steht in `phase5-hardware.md`: resident nur gemessene
Leaf-Registerbündel, POKE-Fallbacks bleiben in `lib-c64io.lsp`. Host-Brücken
(`lib-c64term`, `lib-c64key`) + CIA-Oracle vorhanden.

**TERM_TEST-Scripte:** Neue scripted REPL-Smokes sollen bevorzugt den generischen
`TERM_TEST_SCRIPT_FILE`-Hook nutzen (`TermTestKeys` lädt dann eine kleine ACME-Datei
direkt). Das entlastet die historische, klammerfragile `TermTestKeys`-Kaskade; alter
Flag-Code bleibt aus Kompatibilitätsgründen bestehen.

## 9. Numerik

Kern: **32-Bit-Integer** mit Vorzeichen/Wraparound (`ACC32`/`ARG32`). Geplant:
**Fixed-Point 16.16** (host-validiert: Add/Sub = Integer-Reuse, Mul/Div per Shift,
Reader/Printer-Kontagion). Voller Zahlenturm (Float/Ratio/Bignum/Complex) ist
bewusst ausgeschlossen.

## 10. FFI & IDE (Phasen 7/8, entworfen)

- **FFI/AOT (Phase 7):** Hybrid zuerst — Aufrufkonvention, Marshalling getaggter
  Werte, GC-Root-Protokoll für nativen Code, Echtzeit-/IRQ-Trennung (Asm treibt
  Raster-IRQ/Sprites/SID, Lisp die Logik zwischen Frames). Cross-Compiler auf dem
  PC als Rückgrat des Workflows „interaktiv prototypen → am PC optimieren →
  cross-kompilieren". Nur Design.
- **On-C64-IDE (Phase 8):** Editor-Logik host-grün (`editor-core`,
  Buffer/Cursor/Auto-Indent/Klammer-Match/Keymap/Paredit-Subset). Flat-Buffer statt
  Cons-Zellen; ein Editierbereich + Modeline + Minibuffer in 40×25; nativ gegated
  nur auf P5-I/O + P6-S3-Lib-Laden.

## 11. Design-Leitplanken

1. **Kompaktheit ist Mittel, kein Selbstzweck** — kompakt machen, wo es billig ist
   und Speicher der Engpass ist; Bytes ausgeben, wo sie Tempo/Einfachheit/Features
   kaufen. Layout-Entscheidungen **messen**, nicht dogmatisch treffen.
2. **Engpass ist mehrdimensional** (RAM, 1 MHz CPU, 40×25, kein FPU) — erst den
   tatsächlichen Engpass des Workloads bestimmen, dann optimieren.
3. **Verifizierbarkeit vor Cleverness** — byte-identische Referenz, Host-Treue,
   Smoke-/Audit-Tests; im Zweifel die prüfbarere Variante.
4. **Erst Host prototypen, dann `.acme`.**
5. **Reihenfolge nach Aufwand/Nutzen, nicht nach Eleganz.**
6. **Kompaktheit ist der VM untergeordnet** (Phase 4 bringt mehr als Zell-Schrumpfen).
7. **Scope-Disziplin / Feature-Gate für den residenten Kern:** jedes KB residenter
   Code geht ~1:1 vom Heap. Vor Residenz prüfen: *Kann es ladbare Lib oder
   Host-Tooling sein?* Nur echte Laufzeit-Mechanismen (VM, GC, Reader, Scope, FFI,
   Hardware-Primitive) gehören in den Kern. Ladbare Libs und Host-Tooling sind
   **kein** Budget-Risiko.
