# Design: core Bank-0-Diät — von „Proof" zu „Produkt"

Stand: 2026-07-05 (Claude, Lane K). Status: **SCOPING / Go-No-Go offen.**
Auslöser: Der IDE-Capstone (`(load-lib "ide")` auf `mvp-vm-stdlib-core`) ist HW-grün, aber core sitzt
am 64K-Rand — **330/330 Symbole gesättigt, Reserve 322 (<640), kein natives Render**. Damit core ein
*benutzbares* Produktprofil wird (Render + Symbol-Headroom + gesunde Reserve), muss Bank-0 frei werden.
Dieses Dokument scoped den Weg — und korrigiert die ursprüngliche „nach EXT auslagern"-Annahme.

## 1. Messung: es ist ein `.text`-Problem, kein Daten-Problem

Isolierte Builds (`llvm-size` auf dem core-ELF):

| Feature | Kosten | Segment |
|---|---|---|
| DISK_LIBS (Loader) | **1920 B** | `.text` |
| Render (VM_SCREEN_PRIMS) | **935 B** | `.text` |
| BSS-Anteil beider | ~5 B | vernachlässigbar |

Gesamt-BSS core = 2737 B, und die größten Brocken sind **heiß** (`symfn` 660, `gc_rootstack` 272,
`dir_len`/`dir_off_base` 320, `namelen` 330 — Intern-/CALL-/GC-Pfade). Die DISK_LIBS-BSS ist ~320 B.
**Fazit: Das EXT-Auslagern (das bei Symbolen/Heap/Namepool zog) greift hier nicht — Code führt man
vor Ort aus, man kann ihn nicht per DMA rausschieben und trotzdem ausführen.**

## 2. Warum das naive Overlay NICHT tragfähig ist

Der offensichtliche Gedanke — „den kalten Loader (1920 B) in eine Bank auslagern, per Trampolin nur
bei `(load-lib)` einblenden" — scheitert an vier konkreten Gründen:

1. **Verzahnung mit heißem Code.** `vm_load_lib_ext` (vm_embed.c:219) ruft `vm_register_embedded`
   (→ `intern`/`new_symbol`), `md_lit_node` (Heap-Allokation + Rekursion für verschachtelte Literale),
   `GC_PUSH`, `vm_ext_write` (DMA). Ein gebankter Loader müsste ständig nach Bank 0 zurückrufen.
2. **Kein freies 16-Bit-Fenster.** Der Haupt-Code belegt `$2001–$beb3` durchgehend; darüber liegen
   BSS/Heap/Stack. Es gibt kein leeres Fenster, in das man eine Bank mappen könnte, ohne Haupt-Code
   zu verdecken (den der Loader ja aufruft).
3. **Das Boot-Overlay ist temporal-only.** `scripts/lisp65-mega65-boot-overlay.ld` + `BOOTFN` legen
   boot-only Zeug in Speicher, den der Soft-Stack **nach dem Boot** zurücknimmt. Der Loader läuft aber
   bei *jedem* `(load-lib)` nach dem Boot — der Autor hat ihn deshalb **bewusst resident** gemacht
   (vm_embed.c:212). Passt nicht.
4. **Heap lässt sich nicht verdrängen.** Ein Fenster, das man bei `(load-lib)` mit dem Loader
   überschreibt und sonst dem Heap gibt, ginge nur mit Save/Restore lebender Heap-Daten — teuer und
   fragil ([[overlay-noinit-collision]]: Overlays haben hier schon Blut gekostet).

→ **Das Overlay ist raus.** (Genau das sollte das Scoping klären, bevor Code wandert.)

## 3. Der eigentliche Hebel im `.text`

`.text`-Ranking (core, größte Verbraucher): `vm_run` 6567, `apply` 4302, `vm_callprim` 3401,
`eval_env` 3200, `read_expr_1` 1403, **`md_lit_node` 1388**, `eval_init` 1351, `gc_collect` 1139,
`vm_load_embedded_stdlib` 1058, `repl` 919. Die VM-Giganten sind der Interpreter — kaum ohne
Funktionsverlust schrumpfbar.

**Der auffällige Befund: `md_lit_node` (1388 B) ist DISK_LIBS-spezifisch.** Es rekonstruiert die
Literale einer Disk-Lib beim Laden. Aber der **Boot-Loader** (`vm_load_embedded_stdlib`)
rekonstruiert AUCH Literale — und tut das ohne `md_lit_node` (ein separater, einfacherer Pfad). Wir
haben also **zwei Literal-Rekonstruktoren**. Das ist der Verdacht: Konsolidieren könnte ~1 KB `.text`
sparen — ohne Overlay, ohne Rearchitektur.

## 4. Realistische Optionen (ehrlich gewichtet)

| Option | Gewinn | Risiko | Bewertung |
|---|---|---|---|
| **A. `md_lit_node` mit Boot-Literalpfad vereinen** | bis ~1 KB | mittel | **vielversprechendster nicht-Overlay-Hebel**; muss prüfen, ob die zwei Pfade wirklich unifizierbar sind oder aus gutem Grund getrennt |
| **B. Render-Prims schrumpfen** | <935 B | mittel | vielleicht reicht ein Teil der VM-Screen-Prims für die IDE; ungewiss |
| **C. Loader-Logik als Bytecode** | ~1,4 KB (md_lit_node) | hoch | Rearchitektur + Bootstrap-Henne-Ei; passt aber zur „alles Bytecode"-Vision |
| **D. `.text`-Diät quer** | ~unklar | hoch | die Giganten sind der Interpreter — riskant, ungewiss |
| **E. Split akzeptieren** | 0 | keins | main = interaktiv (embedded+Render), disk-lib = Erweiterung (nicht-rendernd). Umgeht die Wand ganz. |

**Budget-Rechnung als Zielmarke:** Render kostet 935 B; um es bei gesunder Reserve (~640) reinzuholen,
müssen ~1250 B `.text` frei werden. Option A allein (~1 KB) käme nah dran; A + etwas B/D schließt die
Lücke. Danach ist zusätzlich Platz, MAX_SYM 330→~450 zu heben (Symbol-Headroom, ~3 B/Sym).

## 5. Empfehlung + nächster Schritt

Overlay ist tot. **Empfehlung: Option A zuerst proben** — untersuchen, ob `md_lit_node` und der
Boot-Literalpfad (`vm_load_embedded_stdlib`) unifizierbar sind. Konkreter erster Schritt (read-only,
risikofrei): beide Literal-Pfade lesen und vergleichen; wenn sie dieselbe Semantik in zwei
Implementierungen sind → zusammenführen (~1 KB), Render passt. Wenn sie aus gutem Grund getrennt sind
→ ehrlich auf **Option E (Split)** umschwenken: main bleibt die interaktive Workstation, core/disk-lib
ist die nicht-rendernde Erweiterungsschiene. Das ist keine Niederlage — es umgeht eine echte 64K-Wand.

**Ausdrücklich NICHT tun:** blind in ein Overlay oder eine `.text`-Diät der VM-Giganten laufen.

## 6. Lane-Split

- **K (Claude):** die C-Runtime-Analyse + der Literal-Pfad-Merge (`src/vm_embed.c`, `src/vm.c`) bzw.
  die Render-Prim-Schrumpfung sind Lane K.
- **T (Codex):** das core-Profil (Makefile-Flags, MAX_SYM/Render-Flag), Footprint-Gate, HW-Test-Rezept.
- **Gemeinsam:** Go-No-Go nach dem Literal-Pfad-Vergleich; jede Bank-0-Änderung IMMER HW-booten
  (Lektion [[core-profile-no-hw-boot]]: „linkt + Footprint-grün" ≠ „bootet").
