# Stufe 2 — Bytecode-Libraries von Disk (Design)

Stand: 2026-07-04 (Claude). Ziel: **vorkompilierten Bytecode** von Disk on-demand laden und ins
Directory registrieren — schnell (kein Treewalk), für JEDES Modul (Stdlib-Teile *und* IDE). Der
volle Hebel-F-Gewinn: optionale Module verlassen den residenten Bundle, werden bei Bedarf geladen.
Ermöglicht durch das LOAD-Projekt (EXT-Streaming) + `[[budget-frontier]]`.

## Was wir wiederverwenden (kein Neubau)
- **L65M-Metadaten + Registrierung:** `vm_load_ext_metadata` (`src/vm_embed.c`) liest schon eine
  Metadaten-Struktur (Header, je Eintrag `name`/`bank`/`off`/`len`, Literal-Patches) aus dem
  EXT-RAM und registriert via `vm_register_embedded`→`vm_dir_add` + `md_lit_node`-Patches. Der
  Disk-Lib-Loader nutzt **dieselbe** Per-Eintrag-Schleife, nur mit anderer Quelle/Basis.
- **EXT-Zugriff/DMA:** `mem.c ext_disk_put/get` + `ext_dma` (aus LOAD/Heap).
- **Disk-Leseweg:** die `%disk-*`-Primitive / der 1581-Walk (LOAD-Projekt).

## Format
Eine Lib = **Bytecode-Blob + L65M-Metadaten** als Disk-Datei (baut das Host-Tooling aus dem
Lisp-Quelltext der Lib — wie der Stdlib-Blob, aber eigenständig). Auf einer eingelegten D81.

## Device-Loader (Lane K)
`(load-lib "name")` → 1581-Datei finden → Blob+Metadaten aus Disk in EXT stagen → registrieren:
1. **Platzierung:** Blob an den **Bank-5-High-Water** (direkt hinter dem Stdlib-Blob). Loader hält
   `lib_hw` (Start: `stdlib_off + stdlib_len`).
2. **Registrieren:** je Eintrag `vm_dir_add(sym, 5, lib_hw + rel_off, len)` + Literal-Patch
   (relativ zu `lib_hw`) + Symbol-Bind. `lib_hw += blob_len`.

## KNACKPUNKT 1 — Verträglichkeit mit der Dir-Kompaktierung (K2)
Meine K2-Kompaktierung nimmt an: **EIN** Blob, EINE Bank (`dir_bank0`), Offsets **kontinuierlich**
(`dir_off` sparse: Block-Basis + Σ`dir_len`). Ein Lib-Blob **anderswo/andere Bank** würde den
Guard in `vm_dir_add` auslösen (`bank != dir_bank0 → -1`) UND die Sparse-Rekonstruktion brechen.
**Lösung (K2 bleibt unverändert):** Libs laden **kontinuierlich in Bank 5** hinter dem Stdlib-Blob,
**auf 8er-Block-Grenze ausgerichtet** (Loader padded `dir_n` zur nächsten 8er-Grenze; Stdlib hat
aktuell 240 Objekte = 30 Blöcke, endet exakt auf Grenze). Dann gilt `dir_bank0`=5 weiter und die
Sparse-Rekonstruktion stimmt (jeder Lib-Block hat seine eigene Basis = `lib_hw`, intern
kontinuierlich). **Grenzen:** append-only (kein Unload/Gap), Bank 5 bis zum Namepool ($58000,
~24 KB frei) — reicht für IDE + mehrere Libs. Voll-flexibel (mehrere Bänke / Unload) = späterer
K2-Umbau (Per-8er-Block-Bank + -Offset-Basis, ~+30 B).

## KNACKPUNKT 2 — Budget-Realität (ehrlich)
Eine GELADENE Lib zahlt weiterhin **Symbol- + Directory-Slots + Namepool** (Symbole nie GC't). Der
Gewinn ist NICHT „gratis unbegrenzt", sondern:
- **Caps auf den Arbeitssatz statt auf ALLE Features:** wenn Module optional/exklusiv sind (nicht
  alle gleichzeitig geladen), reichen `VM_DIR_MAX`/`MAX_SYM` = Baseline + max(gleichzeitig geladen)
  statt Baseline + Σ(alle). Bündelt man ALLES, braucht man Σ; sind sie ladbar, nur den Arbeitssatz.
- **Kleinerer Bundle:** der gebündelte EXT-Blob (ships mit PRG) schrumpft; Boot registriert weniger.
- **Aber:** wird die IDE (126 Fns) geladen, kostet sie ihre 126 Slots — die Caps müssen das fassen.
  Der Gewinn kommt daher, dass die IDE beim reinen *Programm-Lauf* NICHT geladen sein muss (Slots
  frei fürs Programm). Also: Baseline schlank, IDE/Stdlib-Extras on-demand.

## Lane-Split & Meilensteine
1. **Design (dies) + Abstimmung.**
2. **T (Codex): Host-Packaging** — Bytecode-Compiler einen eigenständigen Lib-Blob+Metadaten
   emittieren lassen (wie der Stdlib-Blob, aber standalone) + Lib-Disk-Builder (D81 mit dem Blob).
3. **K (Claude): Device-Loader** — `io.c`/`vm_embed.c`: Lib-Blob+Metadaten aus Disk (EXT-Streaming)
   in EXT@`lib_hw` stagen, 8er-Align, registrieren (Reuse `vm_load_ext_metadata`-Schleife). Kleiner
   Lisp/C-`(load-lib name)`-Einstieg.
4. **Integration + HW-Test:** eine kleine Test-Lib (2–3 Bytecode-Fns) von Disk laden, aufrufen
   (analog zum LOAD-Capstone) → beweist schnellen Bytecode-von-Disk.
5. **Ernte:** ein echtes Modul (Stdlib-Teilmenge, dann evtl. IDE) in eine Lib auslagern, aus dem
   Bundle nehmen, Caps auf den Arbeitssatz senken, Footprint messen.

## Codex Host-Packaging (2026-07-04)
Geliefert ist ein erster standalone Host-Pfad ohne `src/**`-Eingriff:

- `make bytecode-p0-disklib-artifacts` kompiliert `tests/bytecode/libs/p0-testlib.json` nach
  `build/bytecode/libs/testlib.{blob.bin,ext.bin,manifest.json,disasm.txt}`.
- Das `.ext.bin` ist **`[blob_len u16][md_len u16][Code-Blob][L65M-Trailer]`**. Es nutzt
  `artifact_role=disk-lib` und `base_addr=0x000000`. Damit sind die Entry-Records bewusst
  runtime-relativ: `bank=0`, `off=rel_off`, `len=obj_len`. Der Device-Loader liest den 4-B-Kopf,
  staget Blob nach `lib_hw`, Trailer nach `lib_hw+blob_len` und registriert mit `bank=5`,
  `off=lib_hw + rel_off`.
- `make bytecode-p0-disklib-d81` packt `build/bytecode/libs/testlib.ext.bin` als `TESTLIB`
  in `build/bytecode/libs/testlib.d81` und schreibt
  `build/bytecode/libs/testlib-d81-manifest.txt`.
- Host-Oracle/Embed-Oracle pruefen die Test-Lib-Funktionen `sq`, `disk-add3`, `disk-tag`
  inklusive Literal-Materialisierung. Das D81 ist nur Packaging; der echte Device-Loader-Test
  bleibt Lane K + HW.

## Pilot-Libs (Codex, 2026-07-06)

Der Host-Packaging-Pfad wird jetzt fuer echte on-demand Libraries wiederverwendet:

- `make bytecode-p0-pilot-libs-check` prueft `ide`, `format`, `fixed`,
  `strings-extra` und `place` gegen den residenten Dev-Core
  (`p0-stdlib-einsuite-core-subset.json`).
- `make bytecode-p0-pilot-libs-artifacts` erzeugt
  `build/bytecode/libs/{ide,fmt,fixed,strx,place}.{ext.bin,manifest.json,disasm.txt}`.
- `make bytecode-p0-pilot-libs-d81` packt ein gemeinsames
  `build/bytecode/libs/pilot-libs.d81` mit den Dateien `IDE`, `FMT`, `FIXED`,
  `STRX`, `PLACE` und schreibt `build/bytecode/libs/pilot-libs-d81-manifest.txt`.

Die Suite-Manifeste deklarieren jetzt `name`, `d81_name`, `provides`,
`requires` und `resident_suite`; die erzeugten Artefakt-Manifeste tragen diese
Felder plus gemessene `cost`-Werte. Letzte Host-Messung:

| Lib | D81 | Dir-Slots | align8 | Blob | Symbol-Schaetzung |
| --- | --- | ---: | ---: | ---: | ---: |
| `ide` | `IDE` | 114 | 120 | 5481 B | 143 |
| `format` | `FMT` | 10 | 16 | 439 B | 14 |
| `fixed` | `FIXED` | 16 | 16 | 489 B | 19 |
| `strings-extra` | `STRX` | 2 | 8 | 48 B | 4 |
| `place` | `PLACE` | 8 | 8 | 423 B | 21 |

`lib/stdlib-places.lisp` ist jetzt die erste Macro-Pilot-Lib. Der Emitter erkennt
`defmacro`-Top-Level-Formen, kompiliert den Expander als Bytecode-Codeobjekt und setzt im L65M-
Entry Byte 3 `flags&1`. Der Loader registriert diese Entries als `T_MACRO(BCODE)` statt als
Funktionszelle; `function-kind` sieht dadurch nach dem Load `macro`.

Wichtig fuer K: das Host-Artefakt fuegt keine Directory-Dummy-Eintraege ein. 8er-Alignment/
Padding zwischen geladenen Libs bleibt Loader-Politik, weil nur der Runtime-Loader `dir_n` und
`lib_hw` kennt.

## IDE-Payoff (das eigentliche Ziel)
Dev-Core laedt die IDE on demand: `edit` bleibt resident, `(load-lib "ide")`
bringt `ide-status`, `ide-syntax`, `ide-buffer` und `ide-ui` als 114 Entries
von Disk. Im reinen Programm-Lauf bleiben diese Slots frei. Der aktuelle
Dev-Core-Pin nutzt `VM_DIR_MAX=448`; Core+IDE belegt nach align8 434 Slots.

---

## Umsetzungsstand K (2026-07-04, Claude) — Registrier-Primitive FERTIG + compile-geprüft
**KNACKPUNKT 3 (neu, wichtig): BOOTFN vs. resident.** Der Boot-Metadaten-Loader liegt teils im
**Boot-Overlay** (`BOOTFN`), das nach dem Boot als Soft-Stack **recycelt** wird. Ein *Runtime*-Lib-
Loader darf solche Funktionen NICHT rufen. Audit: `vm_register_embedded` (eval.c), `vm_ext_write`,
`vm_code_load`, `md_read`/`md_name`/`md_idx`/`md_u16` sind **schon resident** ✓ — NUR `md_lit_node`
war `BOOTFN`. Lösung: `md_lit_node` unter `LISP65_DISK_LIBS` residentisiert (Makro `MDLITFN`).
Kosten feature-gated: +1684 B Objekt (vm_embed.o; reine .text kleiner) — nur der Disk-Libs-Build
zahlt; Default-Build unberührt.

**Gebaut (Lane K):**
- `vm.c`/`vm.h`: `vm_dir_align8()` — padded `dir_n` auf 8er-Block-Grenze (Lib = eigener Block).
- `vm_embed.c`/`vm_embed.h`: `uint8_t vm_load_lib_ext(uint16_t code_base, uint16_t md_at)` (resident,
  `#ifdef LISP65_DISK_LIBS`) — registriert eine bereits nach Bank 5 gestagete Lib. Spiegelt
  `vm_load_ext_metadata`, relokiert Einträge+Patches um `code_base`, forciert Bank=`lisp65_stdlib_bank`,
  8er-Align vorweg. Rückgabe 1=ok / 0=kein L65M-Header. Compile-geprüft (mega65-clang, Load-Flags
  + `-DLISP65_DISK_LIBS`), sauber; Gegenprobe ohne Flag ebenfalls sauber.

**Offen (Lane K, nächster Block):** `io.c`-Staging (Lib-Datei von Disk → EXT@`lib_hw`, `lib_hw`-
Tracking, `vm_load_lib_ext` rufen) + `(load-lib "name")`-Einstieg (1581-Walk wie `(load)` +
Staging). Gegatet auf den Format-Vertrag unten (mit T) + Codex' Host-Packaging + eine Test-Lib.

## Lib-Datei-Format (gepinnt durch Codex-Emitter, 2026-07-04)
```
Lib-Datei = [Header 4 B] + [Blob] + [L65M-Trailer]
  Header : blob_len (u16 LE), md_len (u16 LE)
  Blob   : konkatenierte Code-Objekte (blob_len B) — Offsets BLOB-RELATIV (0-basiert!)
  Trailer: exakt das bestehende L65M-Format (38-B-Header + entries/index/nodes/patches/strings),
           ABER entry.off und patch.blob_offset BLOB-RELATIV (0-basiert) — der Loader addiert lib_hw.
```
`vm_load_lib_ext` konsumiert den L65M-Teil bereits (fertig). Der `io.c`-Loader liest den 4-B-Header,
stagt Blob→EXT@`lib_hw` und Trailer→EXT@(`lib_hw`+blob_len), ruft `vm_load_lib_ext(lib_hw,
lib_hw+blob_len)`, dann `lib_hw += blob_len + md_len`. **Codex-Stand:** `make
bytecode-p0-disklib-artifacts` emittiert dieses Format; `make bytecode-p0-disklib-d81` packt es
als `TESTLIB` in eine D81.

## Umsetzungsstand K-2 (2026-07-04, Claude) — Device-Loader C-Seite FERTIG + compile-geprüft
Die komplette C-Verdrahtung steht, gegen Codex' gepinntes Format, alles unter `LISP65_DISK_LIBS`:
- **`mem.c`/`obj.h`:** `ext_disk_stage(scratch_off, dbank, doff, n)` — EXT→EXT-Copy Scratch(Bank 4)→
  Bank 5 in EINEM gehärteten `ext_dma` (kein Bank-0-Umweg).
- **`io.c`/`io.h`:** `disk_chain_to_scratch` aus `io_disk_load_chain` herausgezogen (LOAD-Profil
  regressionsgeprüft, unverändert); neuer `io_disk_load_lib(t,s)` — Datei→Scratch, 4-B-Kopf lesen,
  Blob+Trailer nach Bank 5 @ `disk_lib_hw` stagen (append-only, bis Namepool $8000), `vm_load_lib_ext`.
- **`vm.c`:** CALLPRIM **case 18 `%disk-load-lib`** → `io_disk_load_lib`. **`bytecode-abi.md`:** ID 18
  eingefroren.
- **Compile:** disklibs-Profil kompiliert sauber (nur vorbestehende Warnungen). LOAD/Default unberührt.

**✅ Codex-Nachzug (2026-07-04): Blocker im T-Profil behoben.** `load-lib` liegt jetzt in
`lib/stdlib-load-lib.lisp` und ruft am Directory-Treffer `%disk-load-lib`. Das Disk-Libs-Produkt
nutzt eine eigene schlanke residente Suite `tests/bytecode/stdlib/p0-stdlib-disklibs-subset.json`
statt der vollen 240-Fn-LOAD-Suite: aktuell 21 Funktionen / 31 Objekte / 1010 Code-Bytes im
Embed-Artefakt inklusive `load-lib`-Registry.
`make mvp-vm-stdlib-disklibs` linkt damit wieder grün; der HW-Test kann gegen
`build/lisp65-mega65-vm-stdlib-disklibs.prg` + `build/bytecode/libs/testlib.d81` laufen.

**Historischer Blocker — 520 B Bank-0-Überlauf (Budget, NICHT Code).** Der residente Loader
(~520 B .text) kippt das disklibs-Profil, das mit VOLLER 240-Fn-Stdlib schon an der Bank-0-Decke war
(`ld.lld: .bss overflow by 520 bytes`). BSS-Treiber sind MAX_SYM-getrieben (`nameoff`/`symval`/`symfn`
je 656 B bei MAX_SYM=328). **Das ist genau der Sinn des Profils:** die residente Baseline muss
schlanker werden. **T-Erledigung für den HW-Test:**
1. **520 B im disklibs-Profil freigemacht** — sauberster Weg: schlankere residente Stdlib NUR fürs
   disklibs-Profil (eigene Suite mit weniger Fns → MAX_SYM/VM_DIR_MAX runter) statt der vollen
   LOAD-Suite. Demonstriert zugleich „Features→Disk". (Alt.: reine Cap-Trims, aber MAX_SYM hat nur
   ~17 Luft → zu wenig.)
2. **`(load-lib)`-Lisp in den disklibs-Stdlib-Satz aufgenommen** — reuse des `(load)`-Dir-Walks, nur terminal
   `%disk-load-lib` statt `%disk-load-file`:
```lisp
(defun %load-lib-from-entry (base)
  (%disk-load-lib (%load-entry-byte base 3) (%load-entry-byte base 4)))
(defun %load-lib-scan-entries (codes entry)
  (if (= entry 8) nil
      (let ((base (* entry 32)))
        (if (%load-entry-match-p codes base)
            (%load-lib-from-entry base)
            (%load-lib-scan-entries codes (1+ entry))))))
(defun %load-lib-scan-directory (codes track sector)
  (if (%disk-read-sector track sector)
      (let ((loaded (%load-lib-scan-entries codes 0)))
        (if loaded loaded
            (let ((nt (%disk-byte 0)) (ns (%disk-byte 1)))
              (if nt (%load-lib-scan-directory codes nt ns) nil))))
      nil))
(defun load-lib (name)
  (if (stringp name) (%load-lib-scan-directory (string->list name) 40 0) nil))
```
Nächster Schritt: deploy → `(load-lib "testlib")` → `(sq 5)`=25 als
**schneller Bytecode**. **Optional-Hebel bei K** (falls Budget eng bleibt): `vm_load_lib_ext` und
`vm_load_ext_metadata` teilen ~250 B Schleife — faktorisierbar (Boot-Pfad-Risiko, daher separat).
