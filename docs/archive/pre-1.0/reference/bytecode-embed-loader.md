# lisp65 — Boot-Loader für die Bytecode-Stdlib (K3-B)

**Stand: 2026-07-02 (Lane K/T/L).** Die Andock-Naht zwischen Codex' Compiler/Embed-Artefakt und der
HW-bewiesenen VM. Ziel: beim Boot die kompilierte Stdlib so registrieren, dass jede Funktion
**transparent aus dem REPL/eval** aufrufbar ist (`apply` → `vm_run_dir` → Streaming-VM).

## Was Lane K liefert (GELANDET, host-validiert)

`src/eval.h` / `src/eval.c` (gegatet `-DLISP65_VM`):

```c
typedef struct { const char *name; uint8_t bank; uint8_t flags; uint16_t off; uint16_t len; } vm_embed_entry;
void vm_register_embedded(const vm_embed_entry *tab, uint16_t count);
```

Je Eintrag: `intern(name)` → `vm_dir_add(sym, bank, off, len)` → Registrierung per `flags`.
`flags&1 == 0` installiert eine `T_BCODE`-Funktionszelle; `flags&1 == 1` installiert
`T_MACRO(BCODE)` mit demselben Directory-Index. Alle anderen Flag-Bits sind reserviert und muessen
0 sein. Danach dispatcht der normale eval-Pfad an die VM bzw. der Makro-Pfad an den BCODE-Expander.
Der **Symbolname** (statt eines rohen `obj`) löst die Intern-Ordnungs-Abhängigkeit für die
**Directory-Seite** sauber: der Build kennt die Laufzeit-`obj`-Werte nicht, wohl aber die Namen.

Test: `(emb 7)`=49 über eine `vm_embed_entry`-Tabelle (statt manueller Registrierung).

## Runtime-Hälfte GELANDET (Lane K, host-validiert) — `src/vm_embed.{h,c}`

Die komplette Boot-Runtime steht und ist entscheidungs-**unabhängig** vom Symbol-Encoding gebaut:
- `void vm_load_embedded_stdlib(void)` (nach `eval_init` aufrufen): 1) **Blob-Staging** — den
  konkatenierten Code-Objekt-Blob per `vm_ext_write` ins erw. RAM, oder im MVP-Profil mit
  `LISP65_STDLIB_EXTERNAL_BLOB` ein bereits nach EXT-RAM vorgeladenes Blob verwenden;
  2) **Registrierung** via `vm_register_embedded`; 3) **littab-Auflösung** ueber die
  Literal-Patch-Tabelle.
- `void vm_ext_write(const uint8_t*, uint16_t len, uint8_t bank, uint16_t off)` — Spiegel zu
  `vm_code_load`. mega65: F018-Bulk-DMA (gegatet `LISP65_EMBED_DMA`, in `vm_embed.c` mitgeliefert);
  Host: memcpy. `vm_embed.c` liefert unter `LISP65_EMBED_DMA` **auch `vm_code_load`** (die VM-Naht).
- `main.c`-Hook gegatet `LISP65_EMBED_STDLIB` (nach `eval_init`), Default-Build unberührt.
- Host-Test (`vm-embed-test.c`, Mock-Artefakt): `(sq 6)`=36 / `(dbl 21)`=42 / `(+ (sq 3) (dbl 4))`=17.

## stdlib-p0.{h,c}-Vertrag (exakt) — was Codex' Build emittiert

Ein generiertes `build/bytecode/stdlib-p0.c` plus `build/bytecode/stdlib-p0.h`, das
**genau diese Runtime-Symbole** definiert
(Typen exakt so — `uint16_t` ist auf llvm-mos 16-bit `unsigned int`, **nicht** `unsigned short`):

```c
#include "vm_embed.h"
/* ohne LISP65_STDLIB_EXTERNAL_BLOB: alle Code-Objekte als C-Array */
const uint8_t  lisp65_stdlib_blob[] = { 0xB5, ... };
const uint16_t lisp65_stdlib_blob_len = 2870;
const uint8_t  lisp65_stdlib_bank = 5;                /* Ziel im erw. RAM: bank 5 ... */
const uint16_t lisp65_stdlib_off  = 0;                /* ... off 0 (ext_addr 0x50000) */
const vm_embed_entry lisp65_embed[] = {               /* je Entry, off = blob_offset */
    { "car", 5, 0, 0, 11 }, { "cdr", 5, 0, 11, 11 }, /* ... */
};
const uint16_t lisp65_embed_count = 116;
```

Im aktuellen MVP-Produktprofil wird `stdlib-p0.c` mit `LISP65_STDLIB_EXTERNAL_BLOB` kompiliert:
`lisp65_stdlib_blob[]` wird dann **nicht** ins PRG gelinkt. `make bytecode-p0-stdlib-artifacts`
erzeugt zwei externe Dateien: `.blob.bin` ist weiter der reine Code-Blob; `.ext.bin` ist das
MEGA65-Preload-Image und wird vor dem PRG per `etherload -b 0x050000` ins erweiterte RAM geladen.
`.ext.bin` beginnt bytegleich mit dem Code-Blob und enthaelt direkt danach einen pointerfreien
Metadata-Trailer fuer den naechsten Loader-Schritt. `lisp65_stdlib_blob_len`,
`lisp65_stdlib_bank`, `lisp65_stdlib_off` und `lisp65_embed[]` bleiben im PRG, damit der aktuelle
Runtime-Materializer patchen und registrieren kann.

**Bestaetigt:** `lisp65_embed[].name` traegt den NUL-terminierten Runtime-String des
Funktionssymbols, nicht `name_obj`. Der Header bietet `lisp65_bytecode_stdlib_embed` als
Kompatibilitaetsalias fuer `lisp65_embed`; auch dort ist `.name` derselbe String. Die
Registrierung bleibt damit robust gegen die Laufzeit-Intern-Ordnung (`intern(name)`). `flags`
ist Byte 3 derselben Entry-Daten; Bit0 markiert Macro-Entries.

Der Bundle-Packer (`bytecode_p0_bundle.py`) hat alle Daten bereits: `blob`, je Objekt `name` +
`blob_offset` + `obj_len`; `bank = ext_addr>>16`, `off = ext_addr & 0xFFFF`, `flags` aus der
Suite-Top-Level-Art (`defmacro` -> Bit0). **`name` statt
`name_obj` verwenden** — die Directory-Seite wird zur Laufzeit per `intern(name)` aufgelöst
(robust gegen Intern-Ordnung). Build: `LISP65_VM` + `LISP65_EMBED_STDLIB` (+ `LISP65_EMBED_DMA`)
setzen und `src/vm.c`, `src/vm_embed.c`, `build/bytecode/stdlib-p0.c` in den mega65-Build
aufnehmen. Lane T liefert dafuer `make mvp-vm-stdlib`.

Das Produkt-Artefakt enthaelt nur die Stdlib-Funktions-Codeobjekte (aktuell 116 Objekte). Die
Host-Oracle-Testcases werden nicht eingebettet; `bytecode-p0-stdlib-embed-check` kompiliert sie
transient gegen das rekonstruierte Produkt-Directory.

## Literal-Node-Format (eingefroren fuer den C-Materialisierer)

`stdlib-p0.h` deklariert die Literal-Materialisierungstabellen; `stdlib-p0.c` definiert sie, wenn
es mit `-DLISP65_BYTECODE_STDLIB_EMIT_METADATA` kompiliert wird:

```c
#define LISP65_BC_LIT_INVALID 0
#define LISP65_BC_LIT_FIX     1
#define LISP65_BC_LIT_NIL     2
#define LISP65_BC_LIT_T       3
#define LISP65_BC_LIT_SYMBOL  4
#define LISP65_BC_LIT_CONS    5
#define LISP65_BC_LIT_LIST    6
#define LISP65_BC_LIT_STRING  7

#define LISP65_BC_ENTRY_MACRO 1

typedef struct {
    uint8_t kind;
    int16_t value;
    uint16_t first;
    uint16_t count;
    const char *name;
} lisp65_bc_literal_node;

typedef struct {
    uint16_t blob_offset;
    uint16_t node;
} lisp65_bc_literal_patch;
```

Kind-Codes und Feldbedeutung:

| Kind | Name | Materialisierung |
| ---: | --- | --- |
| 0 | `LISP65_BC_LIT_INVALID` | kein echtes Literal; nur Sentinel/Reject-Wert, Loader muss echte Nodes mit Kind 0 ablehnen |
| 1 | `LISP65_BC_LIT_FIX` | `value` ist der signed 15-bit-Fixnum-Wert; Loader schreibt `MKFIX(value)` |
| 2 | `LISP65_BC_LIT_NIL` | Loader schreibt `NIL`; alle Felder ignoriert |
| 3 | `LISP65_BC_LIT_T` | Loader schreibt das internierte Symbol `t`; alle Felder ignoriert |
| 4 | `LISP65_BC_LIT_SYMBOL` | `name` ist der NUL-terminierte Symbolname; Loader schreibt `intern(name)` |
| 5 | `LISP65_BC_LIT_CONS` | `first` zeigt in `lisp65_bytecode_stdlib_literal_index[]` auf genau zwei Child-Node-Indizes; `count` muss 2 sein; Loader baut `(cons child0 child1)` |
| 6 | `LISP65_BC_LIT_LIST` | `first/count` referenzieren `count` Child-Node-Indizes in `literal_index[]`; Loader baut eine proper list in derselben Reihenfolge |
| 7 | `LISP65_BC_LIT_STRING` | `name` ist der NUL-terminierte Stringinhalt; Loader baut ein `T_STR` nach Kernel-ABI |

`lisp65_bytecode_stdlib_literal_patches[]` ist die primaere Loader-Tabelle: Jeder Eintrag patcht
genau ein 16-Bit-`obj`-Wort im gestageten Blob. `blob_offset` ist der Byte-Offset dieses Wortes
innerhalb des Blob-Artefakts bzw. des optionalen `lisp65_stdlib_blob[]`; `node` ist der Index in
`lisp65_bytecode_stdlib_literal_nodes[]`. `lit_first/lit_count` und
`literal_index[]` bleiben Review-/Konsistenzdaten, aber der native Loader muss fuer das Patching
nur `literal_patches[]` linear abarbeiten.

Footprint-Hinweis fuer den aktuellen MVP-Build: `stdlib-p0.c` definiert `lisp65_embed` und die
dazugehoerigen Runtime-Zaehler immer; `lisp65_stdlib_blob[]` wird nur ohne
`LISP65_STDLIB_EXTERNAL_BLOB` emittiert. Mit `LISP65_BYTECODE_STDLIB_EMIT_METADATA` werden die fuer
den Runtime-Materializer noetigen Literal-Tabellen (`literal_nodes`, `literal_index`,
`literal_patches`) emittiert. Die schweren Review-/Diagnose-Tabellen (raw Directory,
`lisp65_bc_stdlib_entry[]`) sind separat hinter `LISP65_BYTECODE_STDLIB_EMIT_FULL_METADATA`
gegatet und gehoeren nicht in den knappen MVP-PRG-Pfad.

Das Default-Target `make mvp-vm-stdlib` baut mit `LISP65_BYTECODE_STDLIB_EMIT_METADATA`,
`LISP65_STDLIB_EXTERNAL_BLOB` und `LISP65_STDLIB_BOOT_OVERLAY`. Die Boot-Metadaten liegen aktuell
noch in der Linker-Sektion `.lisp65_boot_overlay` strikt hinter `.noinit`; nach
`vm_load_embedded_stdlib()` ist dieser Bereich tot und gehoert dem Soft-Stack. Das aktuelle
HW-sichere Interim-Profil ist `-Oz`, `HEAP_CELLS=254`, `MAX_SYM=192`, `NAMEPOOL=2048`,
`LISP65_SYMPOOL_EXT`, `GC_ROOTS=112`, `LISP65_MARK_BITMAP`; `src/vm_embed.c` ist ueber `$(SRCS)` im
Target enthalten. Der Heap-Deckel ist noetig, solange die Boot-Metadaten als PRG-PROGBITS-Overlay
geladen werden: der PRG-Dateiinhalt muss vor `$C000` enden. `make mvp-vm-stdlib-footprint-report`
gate't `prg_file_end < 0xc000`, `0xd000 - __heap_start >= 1200`, berichtet das
Runtime-Boot-Budget und gate't zusaetzlich `.noinit_end < __lisp65_boot_overlay_start` sowie die
Boot-Stack-Reserve oberhalb des Overlays (`__stack - __lisp65_boot_overlay_end >= 512`). Das
goldene Verhalten bleibt
`bytecode-p0-stdlib-embed-check` aus Manifest+Blob.
Neuere Workbench-Targets verwenden ein separates Footprint-Gate; fuer den
aktuellen Workbench-Pin gilt `docs/workbench-gate.md`, nicht dieses historische
`mvp-vm-stdlib`-Limit.

`make mvp-vm-stdlib-footprint-report` baut die Artefakte und das native PRG frisch und schreibt
`build/bytecode/mvp-vm-stdlib-footprint.txt` mit PRG-Groesse, Build-Profil, Code-/EXT-Image-/
Directory-Groessen und Literal-Patch-Zaehlern.

## littab-Symbolauflösung — Hintergrund (ENTSCHIEDEN: Option 1, s. „Artefaktformat v1" unten)

Die Directory-Namen sind gelöst (s. o.). Offen bleiben **Symbol-Referenzen INNERHALB der
Code-Objekte** — die `littab`-Einträge, die `CALL`/`TAILCALL` (Callee-Symbol) und quotierte Symbole
kodieren. Deren `obj`-Wert hängt an der Laufzeit-Intern-Ordnung, die der Build nicht kennt. (Die
HW-Spikes haben diese Slots zur Laufzeit von Hand gepatcht — für die Stdlib brauchen wir einen
sauberen Mechanismus.)

**Optionen:**

- **(1) Boot-Zeit-Patching (Lane-K-Empfehlung).** Der Compiler legt Symbol-`littab`-Slots als
  **Name-Pool-Referenz** ab (Offset in einen eingebetteten Pool NUL-terminierter Namen) und liefert
  je Code-Objekt die Liste seiner Symbol-Slots. Der Loader interniert den Namen und **patcht den
  Slot im erw.-RAM-Objekt** (DMA read-modify-write) mit dem `obj`. Konsistent mit der Directory-Seite
  (alles namensbasiert). Kosten: einmaliges Boot-Patching + ein Symbol-Slot-Verzeichnis je Objekt.
  → Lane K kann das Patching in `vm_register_embedded` aufnehmen, sobald das Slot-Format steht.
- **(2) Deterministische Intern-Ordnung.** Der Build seedet ALLE Stdlib-Symbole beim Boot in fester,
  bekannter Reihenfolge VOR der Registrierung; der Compiler emittiert die `obj`-Werte direkt. Kein
  Patching, kein Slot-Verzeichnis — aber **fragil** (jede Seed-Änderung verschiebt alle `obj`s) und
  koppelt den Compiler eng an die Laufzeit. Passt evtl. zur bestehenden Symbol-Seed-Struktur
  (vgl. `[[lisp65-symbol-constraints]]`, MAX_SYM fix), wenn Lane T/L die Ordnung garantiert.
- **(3) VM-seitige Auflösung.** `littab` hält Namensindizes; `LIT` löst bei `CALL` über eine
  Name→`obj`-Map auf. Verworfen: belastet den Hot-Path + braucht ein „ist-Symbol"-Bit je Lit.

**Empfehlung: (1)**, wegen Robustheit und Konsistenz mit der (bereits gelösten) Directory-Seite.
Codex besitzt Compiler + Host-VM + Embed und trifft die Wahl; Lane K zieht den Loader nach.

## Codex-Entscheidung: Artefaktformat v1 (2026-07-01)

Codex pinnt fuer den MVP **Option 1**, als allgemeine Boot-Zeit-Materialisierung aller
Literaltabellen-Slots:

- **Code-Staging:** `build/bytecode/stdlib-p0.blob.bin` enthaelt nur die konkatenierten
  Code-Objekte. `build/bytecode/stdlib-p0.ext.bin` ist das MEGA65-Preload-Image:
  Code-Blob ab `LISP65_BYTECODE_STDLIB_BASE_ADDR` (`0x050000`) plus EXT-Metadata-Trailer ab
  `0x050b36`. `build/bytecode/stdlib-p0.c` kann den Code-Blob weiterhin als
  `lisp65_stdlib_blob[]` definieren; das Produktprofil unterdrueckt dieses C-Array mit
  `LISP65_STDLIB_EXTERNAL_BLOB`. F011/Disk-Staging bleibt spaeter austauschbar.
- **Directory-Tabelle:** derselbe Header enthaelt unter `-DLISP65_VM` die Tabelle
  `lisp65_bytecode_stdlib_embed` als Alias fuer `lisp65_embed` vom Typ `vm_embed_entry` sowie
  `LISP65_BYTECODE_STDLIB_EMBED_COUNT`. Die Felder `name/bank/flags/off/len` werden direkt aus
  Bundle-`name`, Entry-Art, `ext_addr` und Objektlaenge abgeleitet; `name` ist immer der
  Runtime-String. `flags&1` bedeutet Macro-Entry (`T_MACRO(BCODE)`).
- **Literale:** rohe `obj`-Worte in den Code-Objekt-Literaltabellen bleiben Host-Platzhalter.
  Der Loader geht linear ueber `lisp65_bytecode_stdlib_literal_patches[]`: `blob_offset` zeigt auf
  das zu ueberschreibende 16-Bit-Littab-Wort im Blob, `node` waehlt den zu materialisierenden
  `lisp65_bytecode_stdlib_literal_nodes[]`-Eintrag. `K_SYMBOL` interniert per Name; `K_STRING`,
  `K_LIST` und `K_CONS` werden rekursiv in den hot Heap aufgebaut. `lit_first/lit_count` und
  `literal_index[]` bleiben als Review-/Konsistenzmetadaten erhalten.
- **Manifest-Spiegel:** `build/bytecode/stdlib-p0.manifest.json` enthaelt dieselbe Entscheidung in
  `embed`, `literal_format` und `external_image`, damit Review-/Loader-Tools nicht den C-Header
  parsen muessen.
- **Host-Gate:** `make bytecode-p0-stdlib-artifacts` rekonstruiert aus Manifest+Blob einen frischen
  Boot-Loader-Blick: Literale werden ueber die Patch-Tabelle materialisiert, die dekodierten
  Code-Objekte damit gepatcht und alle Stdlib-Cases per Host-VM ausgefuehrt
  (`bytecode-p0-stdlib-embed-check`).

Damit ist die Intern-Ordnungs-Abhaengigkeit sowohl fuer Directory-Namen als auch fuer
callee-/Quote-Symbole in Literalen aus dem Build-Artefakt entfernt. Lane K kann das Patching in
oder direkt vor `vm_register_embedded` implementieren, ohne das P0-Code-Objektformat zu aendern.

## EXT-Metadata-Trailer v1

`stdlib-p0.ext.bin` ist rueckwaertskompatibel zum bisherigen externen Blob: Die ersten
`code_bytes` Bytes sind unveraendert die Code-Objekte. Der Trailer beginnt bei
`external_image.metadata_offset` bzw. aktuell Adresse `0x050b36` und ist little-endian.

Header `L65M` (38 Bytes):

```text
char magic[4] = "L65M"
u8   version = 1
u8   header_bytes = 38
u16  flags = 0
u32  code_base_addr
u16  code_bytes
u16  metadata_bytes
u16  entry_count
u16  literal_index_count
u16  literal_node_count
u16  literal_patch_count
u16  entries_off
u16  literal_index_off
u16  literal_nodes_off
u16  literal_patches_off
u16  strings_off
u16  strings_bytes
u16  reserved = 0
```

Records:

```text
entry[entry_count]:     u16 name_off, u8 bank, u8 flags, u16 off, u16 len
literal_index[count]:   u16 node
literal_node[count]:    u8 kind, u8 reserved, i16 value, u16 first, u16 count, u16 name_off
literal_patch[count]:   u16 blob_offset, u16 node
strings[strings_bytes]: NUL-terminierte UTF-8-Strings
```

`name_off=0xffff` bedeutet "kein String". `flags` hat aktuell nur Bit0:
`LISP65_BC_ENTRY_MACRO`/`1` registriert den Entry als `T_MACRO(BCODE)`; ohne Bit0 ist es eine
normale Bytecode-Funktion. Alle Offsets im Header sind relativ zum Trailer-Start, nicht zur
EXT-Basis. Der aktuelle Materializer liest noch die C-Tabellen aus dem PRG; der naechste
Lane-K-Schritt kann dieselben Daten per DMA aus diesem Trailer holen und danach
`LISP65_BYTECODE_STDLIB_EMIT_METADATA`/`LISP65_STDLIB_BOOT_OVERLAY` aus dem Produktpfad entfernen.

## Boot-Sequenz (Ziel)

```
eval_init();                    // Kern + Primitive + VM-Bridges
// MVP-Produkt: Blob liegt schon bei 0x050000; sonst staged der Loader das C-Array.
vm_load_embedded_stdlib();      // 1) literal_patches materialisieren+patchen  2) Directory+T_BCODE
repl();                         // Stdlib läuft als Bytecode aus dem erw. RAM
```

## Status

- **Runtime-Hälfte (Lane K): GELANDET + host-validiert** — `vm_register_embedded` (Directory) +
  `vm_load_embedded_stdlib` (optionales Blob-Staging + Registrierung + Literal-Patching) +
  `vm_ext_write`/DMA-Naht + `main.c`-Hook.
- **Codex' Artefakt (Lane T/L): GEPINNT + host-grün** — **Option 1** (Boot-Patching),
  `stdlib-p0.{h,c}` plus Code-Blob `stdlib-p0.blob.bin` und Preload-Image `stdlib-p0.ext.bin`
  (`lisp65_embed`/Alias
  `lisp65_bytecode_stdlib_embed` als `vm_embed_entry`, optionales `lisp65_stdlib_blob`,
  `literal_nodes`/`literal_index`,
  explizite `literal_patches[]` je Littab-Slot, `LISP65_BYTECODE_STDLIB_BASE_ADDR`); Host-Gate
  `bytecode-p0-stdlib-embed-check` grün. Nutzt bewusst Lane-Ks `vm_embed_entry`/`vm_register_embedded`.
- **Literal-Materializer (Lane K): GELANDET + host-validiert gegen Codex' ECHTES Artefakt.**
  `vm_resolve_littab_symbols` (in `vm_embed.c`, gegatet `LISP65_BYTECODE_STDLIB_EMIT_METADATA`) läuft
  `literal_patches[]` ab und patcht jeden obj-Slot im gestageten Blob; alle Kinds implementiert
  (K_SYMBOL→`intern`, FIX/NIL/T, STRING→`T_STR`, CONS/LIST rekursiv über `literal_index[]`),
  Nicht-Symbol-Literale permanent GC-gerootet. **VM-Variadik** (Rest-Param `flags&1`) ergänzt.
  Beweis: Stdlib aus dem sim-erw-RAM via `eval` — `(length '(1 2 3))`=3, `(nth 1 '(4 5 6))`=5,
  `(length(reverse '(1 2 3 4)))`=4, `(length(member 'c …))`=2, `(nth 2 (list 7 8 9 10))`=9.
- **Build-Glue (Lane T): GELANDET.** `make mvp-vm-stdlib` baut mit
  `LISP65_BYTECODE_STDLIB_EMIT_METADATA`, `LISP65_STDLIB_EXTERNAL_BLOB`,
  `LISP65_STDLIB_BOOT_OVERLAY`, `LISP65_EMBED_STDLIB` und `LISP65_EMBED_DMA`;
  `src/vm_embed.c` ist ueber `$(SRCS)` enthalten. Aktuelles HW-sicheres Interim-Link-Profil: `-Oz`,
  `HEAP_CELLS=254`,
  `MAX_SYM=192`, `NAMEPOOL=2048`, `LISP65_SYMPOOL_EXT`, `GC_ROOTS=112`, `LISP65_MARK_BITMAP`;
  `make mvp-vm-stdlib-footprint-report` meldet `status=ok`, `prg_file_end=0xbfd5` unter dem
  `$C000`-Deploy-Gate, Boot-Budget `157/192` Symbole, `1344/2048` Namepool-Bytes, produktive
  Stack-Luecke 7924 Byte, `.noinit`-Overlay-Gap 1 Byte, Overlay 3785 Byte und Boot-Stack-Reserve
  4139 Byte.
- **🎉 END-TO-END AUF ECHTER MEGA65 BESTÄTIGT (2026-07-01, grün+blau):** Border-Color-Selbsttest-PRG
  (damaliger voller Interpreter + eingebettete 97-Fn-Bytecode-Stdlib, Codex' damaliges
  `mvp-vm-stdlib`-Profil) via etherload:
  DMA-Staging + littab-Materialisierung + Registrierung beim Boot, dann `(length '(1 2 3))`=3,
  `(nth 2 (list 7 8 9 10))`=9 (variadisch), `(length(reverse '(1 2 3 4)))`=4 — grün auf HW.
  **Der MVP ist erreicht:** kompilierte Stdlib als Bytecode im erw. RAM, per Bulk-DMA gestreamt,
  transparent aus dem REPL.
