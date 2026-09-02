# Load-Mechanismus — Vertrag (Lane K, Entwurf)

Stand: 2026-06-30. Ziel: Quellcode aus einer externen Quelle nachladen und auswerten.
Erst der **Vertrag** (Form, Eingabepfad, Fehlersemantik, Abhängigkeiten), dann die
Implementierung. Abgestimmt mit Codex' Load-Pipeline-Harness (Lane T).

## Phasen (klein anfangen)

- **Phase 0 — `load_source(const char*)` bleibt intern (HEUTE, erledigt).**
  C-Funktion in `eval.c`: liest Formen aus einem NUL-terminierten String und wertet jede
  Top-Level-Form aus (mit Gensym-Watermark je Form). Genutzt für die eingebettete Prelude
  (`prelude_src`) und Codex' Harness (`load_smoke_src`). **Kein user-sichtbares `load`.**
- **Phase 1 — user-sichtbares `(load …)` von Disk (NÄCHSTE Lane-K-Aufgabe).**
- **Phase 2 — Komfort:** Pfade/Geräte, Fehlerobjekte, `*load-verbose*`, Rückgabe der
  letzten Form, REPL-Befehl. Später.

## Form: Primitive, keine Spezialform

`load` ist eine **Primitive Funktion** (kein Special Form): das Argument (der Dateiname)
wird normal ausgewertet. Signatur konzeptionell:

```
(load <name>)  ->  t bei Erfolg, sonst Abbruch (siehe Fehlersemantik)
```

Begründung: nichts am Argument muss unausgewertet bleiben (anders als bei `if`/`quote`).
Wie `eval`/`funcall` ist `load` eine gewöhnliche Funktion.

## Der Dateiname — die zentrale Design-Gabel

lisp65 hat **noch keinen String-Typ** (Objektmodell kennt nur NIL/Fixnum/CONS/SYM/PRIM/
CLOSURE/MACRO). `(load "datei")` braucht also zuerst Strings. Zwei Wege:

- **A) String-Typ zuerst (sauber, CL-nah).** Neuer Zelltyp `T_STR` + Reader für `"…"`
  + Printer. Dann `(load "demo")`. *Kosten:* Objektmodell-Erweiterung (rippelt zu Printer,
  GC, Reader; `src/*.h`-Vertrag → vorher ankündigen). *Nutzen:* Strings braucht die
  Sprache ohnehin (Dateinamen, später `format`/Text). **Empfehlung mittelfristig.**
- **B) Symbol-Name als Dateiname (stringlos, Interim).** `(load demo)` → öffnet die Datei
  zum Symbolnamen. CBM-Dateinamen sind ohnehin meist GROSS/kurz → Symbolname (klein)
  hochcasen. *Grenze:* keine `.`/Sonderzeichen (der Reader nutzt `.` für dotted pairs),
  also nur einfache Namen. *Nutzen:* sofort nutzbar ohne Objektmodell-Änderung.

**Empfehlung:** Phase 1 mit **B** (schnell, kein Vertragsbruch), Phase 2 auf **A**
umstellen, sobald Strings da sind. `load` akzeptiert dann beides (Symbol *oder* String).

## Eingabepfad (plattformabhängig, hinter einer C-Naht)

Eine kleine Abstraktion „Quelle öffnen → Zeichen liefern → schließen", damit `load_source`
unverändert bleibt. Zwei Backends:

- **Gerät (C64/MEGA65):** KERNAL-Datei-I/O — `SETLFS`/`SETNAM`/`OPEN`/`CHKIN`/`CHRIN`/
  `READST`/`CLOSE` (über `<cbm.h>` bzw. KERNAL-Calls). Standardgerät 8 (Disk/SD bzw.
  gemountetes D81). EOF/Fehler über `READST` (Status-Byte).
- **Host (gcc):** `fopen`/`fgetc`/`fclose`.

**Pufferung:** minimal = ganze Datei in einen festen Puffer lesen, dann
`load_source(buf)`. *Achtung Bank-0-Enge auf MEGA65* — Puffergröße begrenzt die Dateigröße
(Konstante dokumentieren). Sauberer langfristig: `load_source` auf einen „nächstes Zeichen"-
Callback umstellen (Streaming, kein großer Puffer). Für Phase 1 reicht der Puffer; den
Stream-Umbau als Folgeschritt vormerken.

## Fehlersemantik (passt zum bestehenden Modell)

- **Öffnen fehlgeschlagen / Datei nicht gefunden:** `lisp_abort("load: cannot open")` →
  die REPL fängt es (setjmp) und zeigt `*** load: cannot open`, erholt sich. (Wie
  „undefined function".) Auf Host/Smoke ohne aktives Toplevel: `lisp_abort` ist No-op →
  Rückgabe NIL (bricht `make check` nicht).
- **I/O-Fehler beim Lesen (`READST` ≠ 0/EOF):** `lisp_abort("load: read error")`.
- **Fehler *in* einer geladenen Form (z. B. undefinierte Funktion):** bricht wie üblich
  zum Toplevel ab; bereits ausgewertete Formen bleiben wirksam (kein Transaktions-Rollback).
- **Erfolg:** Rückgabe `t`. (Phase 2 optional: Wert der letzten Form.)

## Abhängigkeiten / Vertragsänderungen

- Phase 1B: **kein** `src/*.h`-Vertragsbruch (nur neue Primitive + neue `io`-Naht). Lane T:
  ggf. `make`-Target/Smoke für `(load …)` von einem gemounteten D81 (HW-Pipeline).
- Phase 2A: **`obj.h`-Erweiterung** um `T_STR` → vorher in `collaboration.md` ankündigen
  (rippelt zu Printer/GC/Reader = Lane K, und zu L-Tests/T-Harness).

## Abgrenzung zu Codex (Lane T)
Codex besitzt die Harness/den Smoke-Pfad und das Embedding (`load_smoke_src`). Lane K
liefert die Primitive `load` + die `io`-Naht (Datei→Zeichen). Der Datei-Smoke (echtes D81)
ist Lane T und kommt, sobald die Primitive steht.
