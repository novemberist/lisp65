# lisp65-IDE-Diät: Analyse und Verschlankungsplan (2026-07-10)

Status: Designvorschlag (Claude), Schwesterdokument zu
`lisp65-dialect-redesign-2026-07-10.md` — gleiche Methode (erst messen,
dann schneiden), gleiche Leitwährung (Symbole/Namepool/Directory), gleiche
Einordnung: Umsetzung post-G6 bzw. über AP5-Fixtures; die strukturneutralen
Teile (§4.1) können AP4 entlasten. Der AP7-Produktvertrag („stabiler
Entwicklungsloop: REPL, Editor, lcc, Load/Save, Compile/Load-Lib,
Fehlererholung“) ist der Maßstab dafür, was „Kern“ heißt.

## 1. Ist-Messung (Quellen `lib/ide-*.lisp`, 2026-07-10)

| Datei | Defuns | davon `%`-intern |
| --- | ---: | ---: |
| `ide-ui.lisp` (1053 Z.) | 90 | 62 |
| `ide-buffer.lisp` (818 Z.) | 83 | 35 |
| `ide-disk.lisp` (585 Z.) | 49 | 40 |
| `ide-completion/eval-request/syntax/launch/status` | 28 | 9 |
| **Gesamt** | **250** | **146 (58 %)** |

- Namensmaterial: **4557 B**, davon **2817 B** in internen Helfern.
- Geladen im Pin: `disk_lib=219` Einträge, `load_used=539/552` — die IDE
  ist der Grund für das Directory-Cap-Wachstum 512→536→552, und jeder
  Slot kostet zusätzlich Bank-0-BSS (`dir_len` u. a.).
- Funktionscluster: 24× buffer, je 12× line/dir/disk, 11× minibuffer,
  9× region, 8× render, 5× apply-Dispatcher-Varianten, 5× kill, 5× yank,
  4× page … — plus 109 „sonstige“ Helfer (Dispatch, Char-Listen,
  Prefix-Vergleiche, Clamps).
- Wiederkehrende Muster: (a) `%ide-char-take/-drop/-take-into` — die IDE
  baut sich eigene Zeichenlisten-Stringhelfer, weil die Stdlib-Strings
  historisch listenbasiert sind; (b) fünf `%ide-apply-*-command`-Ketten
  als handgeschriebene Dispatcher; (c) `…-into`-Akkumulator-Splits wie in
  der Stdlib.
- Kommandofläche (laut `project-status.md`): ~45 Tastenbindungen in acht
  Familien, dazu **M-x mit fünf Kommandos, die sämtlich exakte Duplikate
  bestehender Chords sind** (`find-file`=C-x C-f, `save-buffer`=C-x C-s,
  `compile-load`=C-x C-k, `goto-line`=C-l, `eval-buffer`).

**Kernbefund (analog zur Stdlib, nur schärfer):** 58 % der Definitionen
und 62 % des Namensmaterials bezahlen Implementierungstechnik. Dazu kommt
auf der Funktionsebene echte Doppelung (M-x vs. Chords) und ein
Wachstumsmuster, bei dem jeder UX-Slice 2–5 neue Directory-Slots kostet
(dokumentiert in den Budget-Reclaim-Notizen des Status).

## 2. Prinzipien

1. **Der AP7-Loop ist der Kern.** Alles, was Editieren→Speichern→
   Kompilieren→Laden→Fehler-Erholen dient, ist Kernfläche; alles andere
   ist Komfort und muss sich einzeln rechtfertigen.
2. **Eine Bedienung pro Aktion.** Chord *oder* M-x-Name, nicht beides
   resident. M-x wird der Erweiterungspunkt (Discoverability), seltene
   Chords weichen.
3. **Helfer sind gratis zu benennen, aber nicht zu internieren** —
   Entsymbolisierung (Dialekt-Redesign §6.1) gilt für die IDE zuerst,
   denn hier sind die Namen am längsten.
4. **Komfort ist ladbar.** Die IDE wird von einer Monolith-Lib zu einem
   Kern + nachladbaren Tiers (Paketsystem, Dialekt-Redesign §6.2).

## 3. Kommandoflächen-Triage

### Kern (`ide` — immer geladen, deckt den AP7-Loop)

Cursor/Zeile (C-f/b/n/p, C-a/e, RETURN, Backspace, C-d), Scrollen +
Statuszeile, Kill-Line/Yank (C-k/C-y, einzeiliger Ring), Buffer-Wechsel
(C-x C-b + direkter Zyklus), Find/Save/Write mit Slot-Guards
(C-x C-f/C-s/C-w, TAB-Slot-Zyklus), Directory-Buffer (C-x C-d, RETURN),
Compile-and-Load (C-x C-k), `eval-buffer`, Goto-Line (C-l),
Minibuffer-Basis (Prompt, Default, TAB, Backspace/C-u). ≈ 25 Bindungen.

### Komfort-Tier (`ide-extra` — nachladbar)

Wortbewegung/Kill-Word (C-o/C-u/C-w/C-r), Seitenbewegung (C-v/C-z),
Bufferanfang/-ende (C-x C-a/C-x C-e), Mark/Region-Familie (C-SPC,
C-x C-x/C-r/C-y, mehrzeilig), Suche + Repeat (C-s, C-s C-s),
Minibuffer-History (C-p), Completion-Erweiterungen. ≈ 18 Bindungen,
heute grob 45–60 Directory-Einträge.

### Streichen bzw. zusammenlegen

| Heute | Vorschlag |
| --- | --- |
| M-x-Kommandotabelle (5 Duplikate) + `C-x x`/`C-x RET` | M-x bleibt als *einziger* Zugang für seltene Aktionen; die fünf Duplikate entfallen dort — oder umgekehrt: M-x entfällt komplett, bis es Nicht-Chord-Kommandos gibt. **Eine** Entscheidung, kein Sowohl-als-auch |
| 5 `%ide-apply-*-command`-Dispatcherketten | eine Tabelle Key→Directory-Index (nach Entsymbolisierung direkt bindbar); die cond-Ketten und ihre Helfer entfallen |
| `%ide-char-take/-drop/-take-into` u. Verwandte | ersatzlos nach Umstellung der String-Fläche auf Arena/Buffer-Primitive (Dialekt-Redesign §7) |
| `ide-syntax.lisp` (deaktivierter Overpaint-Cluster, 6 Defuns) | aus der Lib entfernen; Syntax-Highlighting kommt, wenn, als eigenes Tier über SEAM/Farb-Attribute (DeepDive §4) |
| Doppelte Guard-Meldungen (`"not source"`, `"not fasl"`, `"source missing"`, …) | Meldungskatalog konsolidieren: ein Code→Kurztext-Vektor statt verstreuter Literale; Statuszeile zeigt Kurztext |

## 4. Strukturdiät (unabhängig von der Kommandofläche)

### 4.1 Entsymbolisierung der 146 Helfer — größter Einzelhebel

Direkt aus Dialekt-Redesign §6.1, hier mit IDE-Zahlen: **−146 Symbole und
−2817 B Namepool im geladenen Zustand** (heute der Löwenanteil der
Session-Symbollast: der Pin springt beim IDE-Load von 319 residenten auf
539 Einträge). Directory-Slots bleiben zunächst gleich; erst die Tiers
(§5) senken auch die.

### 4.2 Dispatcher als Daten statt Code

Die Key→Aktion-Zuordnung ist heute über Dutzende kleine Funktionen und
cond-Ketten verteilt (5 apply-Varianten, `%ide-dispatch-command`,
`%ide-control-command`, `%ide-command-named`, `%ide-command-action` …).
Nach Entsymbolisierung ist eine kompakte Tabelle (Key-Code →
Directory-Index, Flags für Minibuffer-Aktionen) möglich: geschätzt
15–25 Funktionen weniger, weniger Bytecode, und neue Bindungen kosten
einen Tabelleneintrag statt 2–3 Defuns. Das adressiert das dokumentierte
„jeder UX-Slice kostet 2–5 Slots“-Wachstumsmuster an der Wurzel.

### 4.3 Zeilenmodell auf Buffer-Primitive

`ide-buffer.lisp` (83 Defuns) arbeitet auf Cons-/Zeichenlisten mit
`…-into`-Splits. Mit dem Buffer-Typ (Dialekt-Redesign §7) werden
Zeilen zu Arena-/Buffer-Spans: Char-Helfer entfallen, GC-Druck beim
Tippen sinkt (heute der dokumentierte „IDE-OOM beim Tippen“-Verdacht),
und Delta-Render kann Spans direkt in den Screen DMAen. Das ist die
IDE-Seite derselben Umstellung, die die Stdlib-Stringdiät macht —
zusammen planen, nicht doppelt.

## 5. Tiering statt Monolith

```text
ide        (Kern, AP7-Loop)      ~120–140 Einträge, Ziel ≤ 130
ide-extra  (Komfort, nachladbar)  ~50–70 Einträge
ide-syntax (Zukunft, eigenes Tier) 0 heute
```

- `require 'ide-extra` lädt nach — mit Budget-Preflight (der neue
  L65M-Validator prüft Symbol-/Directory-Delta ohnehin vor dem Commit).
- Typische Session (Editieren+Kompilieren) läuft mit dem Kern:
  `load_used` fällt von 539 auf grob **440–460**, womit `VM_DIR_MAX`
  perspektivisch von 552 Richtung ~480 sinken kann — das gibt Bank-0-BSS
  zurück (`dir_len` u. a., ~1–3 B/Slot) und Luft unterm Cap statt
  weiterer Cap-Erhöhungen.
- Entladen (LIFO) macht den Wechsel `ide-extra` ↔ andere Libs möglich,
  ohne die Session zu sprengen.

## 6. Budget-Abschätzung (geladener IDE-Zustand, konservativ)

| Maßnahme | Directory | Symbole | Namepool | Sonstiges |
| --- | ---: | ---: | ---: | --- |
| Entsymbolisierung (146 Helfer) | ±0 | −146 | −2,8 KB | weniger `symfn`-DMA |
| M-x-Duplikate + Syntax-Datei raus | −12…−15 | −8…−10 | −0,3 KB | |
| Dispatcher-Tabelle | −15…−25 | ±0* | −0,4 KB* | Bytecode kleiner |
| Char-Helfer → Buffer/Arena | −10…−15 | ±0* | −0,3 KB* | GC-Druck ↓ |
| Tiering (Kern-Session) | −50…−70 | −30…−40 | −0,8 KB | `VM_DIR_MAX` senkbar |

*nach Entsymbolisierung ohnehin symbolfrei — Zeilen zeigen den
Directory-/Code-Effekt.

Zielbild Kern-Session: **Directory ~440–460/552 statt 539, Symbole
~500 statt 690, Namepool ~6 KB statt 9,3 KB** — zusammen mit der
Stdlib-Diät wird die Session-Kapazität erstmals planbar, statt pro
Feature einen Cap zu verschieben.

## 7. Migration und offene Fragen

1. Reihenfolge: erst Dialekt-§6.1 (Entsymbolisierung, gemeinsame
   Compiler-/Suite-Arbeit), dann Dispatcher-Tabelle, dann Tiering; die
   M-x-Entscheidung (§3) ist unabhängig und billig, braucht aber ein
   UX-Votum des Nutzers.
2. Die 119 Suite-Cases der IDE-Lib hängen an Funktionsnamen — jede
   Streichung ist ein Fixture-Delta (AP5-Andockpunkt, wie beim Dialekt).
3. Offen: Soll der Directory-Buffer (C-x C-d) im Kern bleiben oder ins
   Extra-Tier? Er ist Teil des Load/Save-Workflows (dafür Kern), aber
   mit 12 dir-Funktionen nicht billig. Empfehlung: Kern, aber nach der
   Dispatcher-Tabelle neu messen.
4. Offen: Kill-Ring im Kern einzeilig lassen (Ist) und mehrzeiliges
   Kill/Yank ins Extra-Tier koppeln an die Region-Familie? (Konsistenz-
   frage: Region ohne mehrzeiligen Ring ist sinnlos — beides zusammen.)
