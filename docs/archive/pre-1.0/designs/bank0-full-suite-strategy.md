# Bank-0-Budget für die volle Suite — Analyse + Strategie

**Stand:** 2026-07-05 (Claude/Lane K), nach HW-Beweis des Lean-Proving-Profils (`2ee771f`).
**Frage:** Wie bekommen wir die VOLLE Suite (Compiler-REPL + volles Prelude + volle Stdlib +
Closures + Disk-Load + IDE-ladbar) ins Bank-0-Budget?

## 1. Kernbefund vorweg (ändert die Fragestellung)

**Das Bank-0-Budget ist für die volle Suite bereits GELÖST — architektonisch durch das
External-Blob-Modell, empirisch durch zwei Links.** Das Profil „Compiler + Blob-Registrierung +
volle Kapazität (MAX_SYM=330, VM_DIR_MAX=242)" linkte heute zweimal (40270 B / 40325 B PRG).
Der eigentliche Blocker der vollen Suite ist der **Laufzeit-Bug an der Dir/Region-Naht**
(`(sq 5)` → `vm_status=3` auf HW), NICHT das Budget. Die Strategie unten behandelt beides,
aber die Prioritäten drehen sich: **Bug-Diagnose zuerst, Budget-Reserven danach.**

## 2. Das Speichermodell (wer zahlt was)

```
Bank 0 (0x2001..0xD000, ≈44,5 KB nutzbar für .text+.rodata+.data+.bss):
  C-Code: VM, Compiler, Reader/Printer/Symbol/Mem, REPL, Screen, Disk-I/O, Boot-Registrierung
  .bss:   Arbeitspuffer (CREPL), symfn[], dir_len/dir_off, heap-hot, gc_rootstack, marks

EXT-RAM (per DMA, kein CPU-Code):
  Bank 4: erweiterter Zell-Heap (EXT_BANK=0x04, EXT_CELLS)
  Bank 5: Stdlib-Blob (Code-Objekte, 19670 B Datei = Code ~12 KB + L65M-Trailer)
          + Disk-Libs (append hinter Blob) + Compiled-Fn-Region (laufzeit-kompilierte Fns)
  EXT:    SYMPOOL/SYMVAL/NAMEOFF (Symbol-Namen/-Werte/-Offsets; genaue Bank: offener Prüfpunkt §5-K3)
```

**Die volle Stdlib (232 Fns inkl. komplettem Prelude — manifest-verifiziert) kostet Bank 0 nur:**
Registrierungs-Code (~2,7 KB .text: `vm_load_embedded_stdlib` 1264 + `md_lit_node` 1388, BOOTFN)
+ `dir_len/dir_off_base` (~340 B) + `symfn[]` (2 B/Symbol). Der 19,7-KB-Blob selbst liegt in Bank 5
(EXTERNAL_BLOB: nicht mal im PRG). **Bytecode im EXT skaliert praktisch bank-0-frei** — das ist der
strukturelle Grund, warum die volle Suite passt.

## 3. Gemessene Ist-Zahlen (llvm-size/nm/readelf, 2026-07-05)

| Profil | .text | .bss | Ende | Luft bis 0xD000 |
|---|---|---|---|---|
| Default (Treewalk + embedded Blob, HW-grün) | 39455 | 3447 | 0xC767 | ~2,2 KB |
| Lean-Proving (Compiler, kein Blob/Prelude, HW-grün) | 37180 | 4323 | 0xC205 | ~3,6 KB |
| Voll (Compiler + ext. Blob + 330/242) | — linkte 2× (40270/40325 B PRG) | | | knapp, >0 |

**Die zwei Welten sind fast gleich groß** (.text):
- Treewalk-Welt: `apply` 4302 + `eval_env` 3198 + `eval_init` 1366 + `qq_list` 639 + Embed-Metadata 2652 + `vm_run` 6557
- Compiler-Welt: `compile_expr` 5649 + `compile_lambda_helper` 1454 + Rest-Compiler ~2,5 KB + `vm_run` 7620 (inkl. Closures) + `vm_native_apply` 1294

→ Der Tausch Treewalk→Compiler ist **etwa bank-0-neutral**. Die frühere Sorge „Compiler passt nie"
galt für BEIDE zusammen; M7 (Treewalk raus) hat sie aufgelöst.

**.bss-Dickschiffe (Lean):** `cf_code` 1280, `symfn` 448 (=224×2; bei 330: 660), `marks` 392,
`heap` 300, `gc_rootstack` 256, `dir_len` 96 (bei 242: 242).

## 4. Was „volle Suite" konkret heißt — und was sie kostet

Vollprofil = Lean + folgende Deltas:
| Delta | Bank-0-Kosten | Beleg |
|---|---|---|
| Blob-Registrierung (EMBED_STDLIB + EXT_METADATA, Blob extern) | ~2,7 KB .text (BOOTFN) | nm Default |
| Kapazität MAX_SYM 224→330 | +212 B .bss (symfn) | Arrays sind EXT bis auf symfn |
| Kapazität VM_DIR_MAX 96→242 | +164 B .bss (dir_len+dir_off_base) | vm.c |
| volles Prelude | **0 B** (im Blob enthalten, manifest-verifiziert; kein prelude_src nötig) | §2 |
| Disk-Load/load-lib (F011 + DISK_LIBS) | im Default-Produkt enthalten → passt | Default-Zahlen |
| IDE | **0 B** (disk-ladbare Bytecode-Lib, schon ausgelagert) | Bestand |
| Closures + native apply | schon im Lean drin | Lean-Zahlen |

Summe ≈ Lean + ~3,1 KB → **randvoll, aber es linkte 2×.** GC-Overflow-Hypothese beim Boot-Patching
wurde geprüft und **widerlegt** (nur 16 der 415 littab-Patches sind Nicht-Symbol-Knoten → GC_PUSH ≤16
bei GC_ROOTS=128; das Default läuft mit denselben 128 HW-grün).

## 5. Der echte Blocker: die Dir/Region-Naht (Laufzeit-Bug)

Symptomatik (HW, Blob-Profil): `(+ 1 2)`→3 ✓, globales setq ✓, `defun sq`→sq ✓, **`(sq 5)`→TYPEERROR**.
Lean (Dir leer, Region@Bank5/0, di klein) läuft; Blob-Welt (di=232+, Region@append_off) bricht.
Ausgeschlossen: Budget (linkte), GC-Overflow (§4). Offene Kandidaten, priorisiert:

- **K1 — fehlendes `vm_dir_align8()` vor dem ersten Region-Add.** Der Disk-Lib-Loader
  (`vm_load_lib_ext`) ruft es EXPLIZIT „damit die sparse dir_off-Rekonstruktion stimmt" — die
  Compiled-Fn-Region tut es NICHT. Billigster Fix-Kandidat: `crepl_reset()` → `vm_dir_align8()` +
  Region-Basis. *(Auch wenn die Papier-Mathe konsistent aussieht: der Lib-Pfad hielt es für nötig.)*
- **K2 — Region-Basis am Code-Ende statt Datei-Ende.** `vm_dir_append_off()` ≈ Code-Ende (~12 KB);
  die Blob-DATEI ist 19670 B (L65M-Trailer dahinter). Die Region überschreibt den Trailer — post-Boot
  meist tot, aber `load-lib` (DISK_LIBS) liest `md_*` zur LAUFZEIT → im Vollprodukt real. Fix: Region-
  Basis = hinter dem Trailer (Blob-DATEI-Länge, buildzeit-bekannt aus dem Manifest), nicht append_off.
- **K3 — EXT-Layout-Kollision:** SYMPOOL/SYMVAL/NAMEOFF-Bank+Offsets gegen Blob@Bank5/Region kartieren
  (Implementierung `sympool_write` unter EMBED_DMA prüfen). Eine Überlappung würde exakt „Boot ok,
  spätere Writes korrumpieren Code" erzeugen.
- **K4 — BCODE-Immediate-Raum bei di≥232** (MK_BCODE-Kodierung): unwahrscheinlich (Default nutzt
  di 0..231 täglich), aber als Randcheck billig.

**Diagnose-Regel: kein HW-Blindflug mehr.** Der xemu-uartmon-Harness (Blob-Upload per Monitor-Socket,
RAM-Dump — Bestand) macht den Zustand SICHTBAR: Boot → `defun sq` → Dump von Bank 5 (liegt sq an
crepl_off? littab-Wort korrekt?) + `.bss` (dir_off_base intakt?). Ein Nachmittag xemu ersetzt fünf
HW-Deploy-Rateschleifen.

## 6. Strategie-Kaskade

**S0 — Bug fixen (Lane K, JETZT):** K1+K2 zusammen umsetzen (`crepl_reset`: `vm_dir_align8()` +
Region-Basis = Blob-Datei-Ende als Profil-Konstante, z. B. `CREPL_REGION_BASE`), K3-Bankkarte
dokumentieren, dann **xemu-verifizieren, erst dann HW.** Zusätzlich Design-Punkt: Disk-Libs UND
Region appenden beide hinter dem Blob → **EIN gemeinsamer Append-Zeiger** (sonst überschreiben sich
`load-lib`-Libs und User-defuns gegenseitig — derselbe Bug in Grün, nur später).

**S1 — Vollprofil schnüren (Lane T + K):** Lean-Recipe + `EMBED_STDLIB`(Registrierung) +
`EXTERNAL_BLOB` + `EXT_METADATA` + Kapazität 330/242 zurück + F011/DISK_LIBS. Endnutzer-Pfad:
Blob von Disk statt etherload (F011-Streaming existiert; Autoboot = Lane T). Gates: prelude-load-run
(Host) + xemu-Smoke (Boot+defun+call+Closure+`(length …)`-Stdlib-Call) + HW.

**S2 — Budget-Reserven (nur bei Bedarf; korrigiert gegen die Budget-Frontier-Erkenntnisse 2026-07-04):**
1. ~~Dir-Kompaktierung −616 B~~ — **SCHON GELANDET** (`298c012`, HW-validiert; steckt bereits in den
   Zahlen aus §3). Nicht doppelt einplanen.
2. ~~`symfn[]`/Dir-Arrays→EXT~~ — **TOTER HEBEL** (Spike 2026-07-04): `dir_find` O(1) via symfn ist
   CALL-Hot-Path, `nameoff` ist absichtlich Bank-0-resident (DMA-freier intern-Vorfilter; EXT kostete
   ~1/3 s pro Reader-Token). Nicht nochmal anlaufen.
3. `cf_code`-Streaming: −~900 B .bss (Helfer sofort assemblieren+wegschreiben statt 8 Parallel-Puffer);
   Umbau des bc_unit-Modells — der einzige neue substanzielle .bss-Hebel der Compiler-Welt.
4. REPL-Kleinkram (hist 120, buf 250) — letzte Reserve, UX-Kosten.
5. Hebel A (Boot-Overlay, ~3,9 KB — `vm_load_embedded_stdlib`/Boot-Code nach Gebrauch freigeben):
   der bekannte GROSSE Hebel, aber hart/eigenes R&D-Sub-Projekt (s. `docs/memory-budget-strategy.md`).
- **Nicht anfassen:** GC_ROOTS=128 (ist zugleich VM-Value-Stack; 16 Boot-Permanents + Tiefe).

**S3 — Wachstums-Architektur (der eigentliche Skalierungs-Hebel, läuft schon):** Alles Neue lebt
als **Bytecode im EXT** — User-defuns (Region), Libs (load-lib), IDE (disk-ladbar). Bank 0 konvergiert
gegen einen festen Sockel (~40 KB: VM + Compiler + Treiber + Registrierung). Es gibt KEIN
Bank-0-Wachstum pro Feature mehr, solange Features Lisp/Bytecode sind statt C. Konsequenz als
Arbeitsregel: **neue Funktionalität zuerst als Lib formulieren, C-Kern nur für Primitive erweitern**
(deckt sich mit der bestehenden Scope-Disziplin).

**S4 — Nordstern (nicht jetzt):** Wenn der C-Sockel selbst drücken sollte: Compiler-Selbst-Hosting
(Compiler in Lisp → Bytecode → EXT; Bank 0 = nur VM+Reader+Treiber ~20-25 KB). Großer Umbau,
erst relevant, wenn S2-Reserven erschöpft UND neue C-Kern-Features nötig sind.

## 7. Empfehlung

1. **S0 sofort** (K, xemu-first): align8 + Region-Basis hinter Trailer + gemeinsamer Append-Zeiger
   mit Disk-Libs; Bankkarte klären.
2. **S1 direkt danach** — das Vollprofil ist nur noch Konfiguration + der S0-Fix.
3. **S2.3 (cf_code-Streaming)** als ersten echten Reserven-Hebel vormerken (die früher „sicheren"
   S2-Gewinne sind schon verbraucht bzw. tot — s. o.); Hebel A bleibt das große, harte R&D.
4. S3 als Arbeitsregel ab jetzt; S4 parken.


## S5 — Source-on-Disk als Budget-Hebel (Nutzer-Einsicht 2026-07-05, GEMESSEN)
**Kern:** Mit F011 (Disk) + residentem Geräte-Compiler braucht man die vorkompilierten Blobs +
ihre REGISTRIERUNGS-Maschinerie NICHT. Stdlib/IDE als QUELLE auf Disk, beim Boot/on-demand vom
residenten Compiler kompiliert (`load_source` existiert schon). Das eliminiert die ~3 KB BOOTFN-
Registrierung (md_lit_node 1388 + vm_load_embedded_stdlib 1188 + L65M-Metadaten-Parser).
**GEMESSEN:** volles IDE-Profil (Compiler+F011+Screen-Prims+dir360/sym400) mit Blob = **-1339 B**;
mit Source-on-Disk = **+28 B (linkt!)** → **~1207 B Netto-Hebel** (Rohgewinn ~3 KB, minus ~1 KB
groessere CREPL-Puffer fuers on-device-Kompilieren grosser Fns, minus F011 721 B).
**Tradeoffs (ehrlich):** (1) Boot kompiliert 300+ Fns → LANGSAM (Sekunden-Minuten; Mitigation:
kleiner Kern-Blob schnell + IDE/Extras source-on-demand beim ersten `(edit)`); (2) Quelle muss auf
D81; (3) 28 B Reserve = Stack-Kollision zurück → Hebel A ODER Trims fuer komfortable Reserve.
**Strategische Auszahlung (der eigentliche Gewinn):** Bank 0 → fester Kern (Compiler+VM+F011+Reader),
alles andere Disk-Quelle; Stdlib/IDE werden EDITIERBARE Quelle (nicht opake Blobs — die IDE kann ihre
eigenen Libs bearbeiten!); F011 gibt Datei-I/O gratis; kein Per-Feature-Bank-0-Wachstum. = die S3/S4-
Trajektorie, jetzt mit Zahl. **Verhaeltnis zu Hebel A:** komplementaer — Source-on-Disk bringt aufs
Fitting-Level, Hebel A obendrauf gibt Luxus-Reserve. Beide zusammen = die Vollsuite mit viel Luft.

**Codex-Nachzug (Lane T, 2026-07-05):** `make mvp-vm-stdlib-s5-proof` baut das schlanke
Source-on-Disk-Proof-PRG fuer `scripts/xemu-s5-verify.py` reproduzierbar, ohne Blob und ohne
automatischen xemu-Start. Das Target haengt in `make check` und prueft nur den nativen Link. Das
volle IDE-S5-Profil (`sym400/dir360` + Screen-Prims) bleibt zu pinnen, sobald das exakte gemessene
Flag-Rezept festliegt. `make s5-source-d81` erzeugt zusaetzlich eine QUELL-D81 aus den
`p0-stdlib-subset.json`-Quellen in Suite-Reihenfolge. Die komplette Quelle ist aktuell groesser als
der einzelne gegatete S5-Disk-Scratch (`0x8700`), deshalb liegt sie im D81 auch als `l00..`-Chunks; Boot-
Chunk-Konsum/Directory-Lookup bleibt der naechste K/T-Join.
