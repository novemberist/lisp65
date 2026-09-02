# lisp65 — Skalierung via Bytecode-VM + Streaming (Architektur-Plan)

**Stand: 2026-07-01. Entscheidung mit User.** Nach der vollständigen HW-Diagnose des
DMA-Extended-Heaps (`docs/extheap-alternatives.md`, `docs/mega65-extram-access.md`) ist dies
der gewählte Weg zur Heap-/Sprachumfang-Skalierung.

## Warum dieser Weg (die HW-Realität als Vorgabe)

Auf echter MEGA65 gilt (erschöpfend getestet):
- 🟢 **Hot-Zugriff (Bank 0)** ist zuverlässig.
- 🟢 **Bulk-/seichter DMA-Zugriff aufs erweiterte RAM** ist zuverlässig (bis 5000 Zellen getestet).
- 🔴 **Wahlfreier DMA-Zugriff auf erweiterte Zellen WÄHREND des rekursiven eval/reader** korrumpiert.

Der tree-walking-eval greift wahlfrei auf beliebige Zellen zu → er kann nicht auf erweitertem RAM
arbeiten. Eine **Bytecode-VM** dagegen fetcht ihren Instruktionsstrom **sequentiell** — der exakt
seiche/bulk-Zugriffsmuster, das auf HW trägt.

## Kernidee: Code ins erweiterte RAM, Daten hot

In Lisp ist Code zunächst Daten (cons-Zellen). Kompilieren **trennt** beides:
- **CODE** (kompilierte Stdlib-Funktionen = Bytecode-Blobs) → **erweitertes RAM**, sequentiell
  per Bulk-DMA in einen kleinen **hot Bytecode-Puffer** gestreamt, dort ausgeführt.
- **DATEN** (Laufzeit-cons-Zellen/Objekte, die Programme erzeugen) → **hot Bank-0-Heap** (passt;
  die ~2200 „Stdlib-Zellen" waren überwiegend CODE, nicht Laufzeitdaten).

Damit braucht der hot-Heap nur noch die Laufzeit-Daten zu fassen, nicht Code+Daten → das
Größenproblem (Bank-0 maxt ~1500 Zellen) entschärft sich, weil der Code auslagert.

## Bausteine (alle nutzen NUR HW-bewiesene Operationen)

1. **Bytecode-ISA** — den Vertrag `bytecode-v1` aus lisp64v2026 übernehmen/anpassen
   (`../lisp64v2026/docs/bytecode-v1.md`: stack-basiert, Opcodes 0–44 eingefroren, Code-Objekt =
   Header + Payload + Literaltabelle). Rein sequentiell interpretierbar.
2. **Compiler (Lisp → Bytecode)** — host-seitig (Python), Vorlage: `../lisp64v2026/tools/host-lisp/
   phase4_*.py`. Läuft beim Build; die Stdlib wird zu Bytecode-Code-Objekten kompiliert und
   eingebettet (analog zum heutigen `-DLISP65_WITH_PRELUDE`, nur Bytecode statt Quelltext).
3. **C-Bytecode-VM im Kern (lisp65)** — führt Bytecode aus, operiert auf dem **hot cons-Heap**
   (car/cdr/cons = die bestehenden hot-Accessoren). NEU zu schreiben (die alte VM ist 25k Zeilen
   ACME-Asm, nicht portierbar — nur der ISA-Vertrag wird übernommen).
4. **Streaming-Loader** — Code-Objekte liegen flach im erweiterten RAM; ein kleiner hot-Puffer
   (z. B. 256–512 B) wird per **Bulk-DMA** (bewiesen 🟢) sequentiell nachgefüllt, während die VM
   die Payload abarbeitet (Program-Counter über die flache Code-Adresse; DMA holt das nächste
   Segment). KEIN Zugriff auf einzelne erweiterte Zellen während der Ausführung.

## Warum das strukturell auf HW trägt
- VM-Instruktions-Fetch = **sequentiell** aus erweitertem RAM per **Bulk-DMA** in einen hot-Puffer
  (🟢 bewiesen).
- Alle **Daten**-Zugriffe (cons/car/cdr, Stack, Literale) = **hot Bank 0** (🟢 bewiesen).
- Nirgends wahlfreier erweiterter Zugriff während der Ausführung (🔴 vermieden).

## Offene Fragen / zuerst zu klären
- **Laufzeit-Datenbudget:** Passen die cons-Zellen, die Programme zur Laufzeit erzeugen, in den
  hot-Heap (~1500)? (Vermutlich ja, da Code auslagert — aber messen.)
- **Compiler-Wiederverwendung:** Wie viel von `phase4_*.py` (lisp64v2026) lässt sich für lisp65
  übernehmen? Der ISA-Vertrag ist gemeinsam; die Frontends/Objektmodelle unterscheiden sich.
- **Literaltabellen/Konstanten** eines Code-Objekts: hot mitladen (klein) oder ebenfalls streamen?
- **Inkrementeller Pfad:** erst eine einzelne Funktion via VM+Streaming end-to-end auf HW grün
  (Minimal-ISA: PUSH/ADD/CALL/RET), dann die ISA + Stdlib ausbauen.

## Phasen
1. **Spike:** Minimal-Bytecode-VM in C (wenige Opcodes) + ein handkompiliertes Code-Objekt im
   erweiterten RAM, per Bulk-DMA gestreamt, Ergebnis auf HW grün. Beweist den Kern-Mechanismus.
2. **Compiler:** Host-Lisp→Bytecode (phase4-Vorlage adaptieren), Stdlib-Teilmenge kompilieren.
3. **Integration:** VM-Dispatch aus dem REPL/eval für kompilierte Funktionen; hot Daten-Heap.
4. **Ausbau:** volle ISA, volle Stdlib als Bytecode, MEGA65-Smokes + HW-Gegenprobe je Stufe.

**Nicht-verhandelbar:** xemu = Smoke, **HW = Schiedsrichter** (der DMA-Extended-Heap war xemu-grün
und HW-rot — jede Stufe am Gerät bestätigen). Deploy bleibt bis dahin Bank-0-Heap.

## Fortschritt (2026-07-01)

- **P0 (ABI) gepinnt** (`docs/bytecode-abi.md`); Codex baut Compiler + Referenz-Host-VM parallel.
- **K1 (VM-Kern) + K2a (CALL/TAILCALL, TCO) + CALLPRIM** — host-validiert, 20 goldene Vektoren grün
  (`src/vm.{h,c}`): die VM führt rekursive/iterative Lisp-Funktionen + Primitive aus.
- **K2b (Streaming-VM) AUF ECHTER HW BESTÄTIGT 🟢 — vollständiger Architektur-Beweis:**
  Einheitliches Streaming-Modell (ein hot-Puffer, Reload-on-return; `vm_code_load` = Plattform-Naht:
  Host memcpy / mega65 Bulk-DMA). **K2b.1:** Einzel-Code-Objekt (`(+ a b)`, `min`) aus erw. RAM
  gestreamt+ausgeführt, grün. **K2b.2:** volle Call-Maschinerie — **geschachtelte CALL + Rekursion**
  (`inc(inc 40)`=42 mit Reload-on-return, rekursive `length(1 2 3 4)`=4), alle Code-Objekte im erw.
  RAM, per Bulk-DMA nachgeladen → **grün auf HW**. Damit führt die VM echte rekursive Lisp-Funktionen
  aus, deren Code im erweiterten RAM liegt — genau der MVP-Bedarf. Der MVP-kritische Skalierungsweg
  ist end-to-end am Schiedsrichter (HW) de-riskt.
- **K3 (eval-Integration) GELANDET — host-validiert (7 Tests) + AUF ECHTER HW BESTÄTIGT 🟢:**
  Voller Interpreter (`-DLISP65_VM`, nativer MEGA65-PRG via `mos-mega65-clang`), Code-Objekte im
  erweiterten RAM (Bank 5), echte Bulk-DMA als `vm_code_load`. Auf echter MEGA65 (etherload,
  Rahmenfarbe grün+blau): `(sq 5)`=25 (tw→vm), `(callit 21)`=42 (vm→tw-Bridge auf `+`-Primitiv),
  `(mixed 5)`=26 (Round-Trip). Der VM-Dispatch wird **aus dem eval-Aufrufstapel** ausgelöst (tiefer
  45GS02-Stack + DMA) und trägt → die HW-spezifische Sorge ist ausgeräumt. Der tree-walking `apply` erkennt
  einen neuen kompilierten Funktionstyp `T_BCODE` (a=Directory-Index) und leitet ihn an die VM
  (`vm_run_dir`). Umgekehrt bricht ein VM-`CALL`/`TAILCALL` auf ein **nicht** kompiliertes Symbol
  über den Hook `vm_treewalk_call` zurück in den Tree-Walker (`apply(sym_function(sym), args)`) —
  so rufen sich kompilierte und interpretierte Funktionen gegenseitig auf. `apply`/`funcall`
  (Prim 7/8) delegieren via `vm_treewalk_apply`. Bewiesen: `(sq 5)`=25 (tw→vm), `(callit 21)`=42
  (vm→tw, CALL auf `+`-Primitiv), `(mixed 5)`=26 (Round-Trip kompiliert↔kompiliert↔Primitiv),
  `(applyit #'sq 5)`=25 / `(applyl #'sq '(7))`=49 (funcall/apply). Alles hinter `-DLISP65_VM`
  gegatet. Das Standard-Gate prueft inzwischen den MEGA65-Compile-Pfad; C64/GO64
  bleibt nur historisch unter `legacy-*`.
- **Inkrementelles Streaming GELANDET — host-validiert:** `vm_run` nutzt jetzt ein Fenster-Modell —
  Header+littab bleiben resident am Puffer-Anfang, das Payload streamt als gleitendes Fenster
  dahinter (`WIN_ENSURE` lädt vor jeder Instruktion `[pc, pc+3)` per Bulk-DMA nach; `RD8()` liest
  fenster-relativ). Objekte **größer als der Puffer** laufen jetzt: 183-Byte-Straight-Line-Payload
  + Schleife mit Rückwärts-`JMPREL` bei `VM_CODEBUF=16` grün; **alle vm-smoke-Vektoren
  (CALL/TAILCALL/Rekursion/TCO) auch bei Puffer=20 grün** (Reload-on-return lädt Header + Fenster am
  `pc`). Fast-Path (Objekt ≤ Puffer): `win=0, winlen=payload_len` → nie ein Reload, ein Fenster-Check
  je Instruktion. Passt zur HW-Realität (Instruktions-Fetch sequentiell + Bulk-DMA, beides
  HW-bewiesen). **AUF ECHTER HW BESTÄTIGT 🟢** (nativer PRG mit `-DVM_CODEBUF=32`, etherload
  grün+blau): 183-Byte-Straight-Line-Payload (Vorwärts-Fenster) = 60 und Schleife mit
  Rückwärts-`JMPREL` = `sum(1..10)`=55/`sum(1..4)`=10 (Rückwärts-Fenster) — echte Bulk-DMA-Fenster-
  Nachladungen **mitten in der Ausführung** tragen.
- **🎉 MVP ERREICHT — END-TO-END AUF ECHTER MEGA65 (2026-07-01, grün+blau):** damaliger Codex-Compiler +
  97-Fn-Stdlib → Bytecode (`stdlib-p0.{h,c}`), Lane Ks Boot-Loader (`vm_load_embedded_stdlib` +
  littab-Materializer + VM-Variadik). Voll-PRG (`make mvp-vm-stdlib`, Bank-0-Profil) via etherload:
  DMA-Staging ins erw. RAM + littab-Materialisierung beim Boot, dann `length`/`nth`/variadisches
  `list`/`reverse` aus der eingebetteten Bytecode-Stdlib via eval — grün auf HW. Die kompilierte
  Stdlib läuft als Bytecode aus dem erweiterten RAM, per Bulk-DMA gestreamt, transparent aus dem REPL.
