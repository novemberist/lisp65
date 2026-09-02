# Review: Modularisierungs-Strategie + ANSI-Inventur (Lane K, 2026-07-06)

Bewertung von `docs/library-modularization-strategy.md` und `docs/ansi-cl-inventory.md`
(Codex, 96736bb/c89f071) inkl. Kosten/Nutzen — auf Nutzerwunsch.

## Gesamtverdikt

**Beide Dokumente sind tragfähig und können Grundlage der C-Phase werden.** Die Inventur
ist ehrlich (kein ANSI-Versprechen, klare Ist/Host/Fehlt-Trennung), die Strategie trifft
die drei wichtigsten Architektur-Entscheide richtig. Vier Punkte fehlen bzw. brauchen
Schärfung: Session-Budget-Mathematik, Doppel-Load-Schutz als v1-Pflicht, die heutigen
Gate-Lücken als VORBEDINGUNG, und die ABI-Tragweite der Phase-2-Familien.

## Was richtig ist (mit Begründung)

1. **Hub-and-Spoke v1 (Libs hängen nur am Core).** Genau richtig: Bei append-only-Loading
   ohne Unload wird jeder Inter-Lib-Abhängigkeitsfehler zur verbrannten Session. Erst mit
   Manifest-Gate darf das aufweichen.
2. **Grobe Bundles statt Funktionssplit.** Hart quantifizierbar: jedes `load-lib` kostet
   `vm_dir_align8` = bis zu 7 Dummy-Slots + eigenen 8er-Block. Eine Lib pro Funktion würde
   das Directory ~8× schneller verbrennen als eine Lib pro Domain.
3. **Die Ehrlichkeit „on-demand spart nicht rückwirkend".** Symbole werden nie ge-GC't,
   Dir ist append-only — die Formulierung „verschiebt die Grenze zum Arbeitssatz" ist
   exakt die richtige Erwartungssteuerung.
4. **mapcar/Klein-Strings/Output resident.** Richtig: Entkopplungs-Nutzen ≫ Slot-Kosten.
5. **Kein Autoload in v1.** Richtig begründet (Tippfehler verbrennt Slots, Diagnose-Hölle).
6. **Host-gepinnte Deps (Manifest + Orakel).** Das ist die Übertragung unserer
   Beweiskultur auf Module — der Deps-Gate ist das Modular-Analogon zur Äquivalenz-Suite.
7. **Phasen-Schnitt** (reine Lisp-Libs → Runtime-Vertrag → neue Objektarten) folgt sauber
   den echten Abhängigkeiten.

## Was fehlt / nachschärfen (Lane-K-Ergänzungen)

1. **Session-Budget-Mathematik.** Die Strategie sagt nicht, was ein Load KOSTET. Vorschlag:
   jedes Bundle-Manifest bekommt GEMESSENE Felder (`dir_slots` inkl. align8, `symbols`,
   `region_bytes`), und ein Host-Check rechnet „Core + gewählte Libs ≤ Caps" durch.
   Beispiel-Größenordnung: `ide` on-demand ≈ +115 Dir-Slots/+115 Symbole/+8 KB Region —
   ohne diese Tabelle ist „Dev-Core lädt ide+coll+fmt" ein Blindflug (Caps 512/560).
2. **Doppel-Load-Schutz gehört in v1, nicht später.** Ein `load-lib`-Registry (Alist an
   einem Halte-Symbol, ~1 Symbol + wenige Zellen) ist billig; die Alternative — stilles
   Slot-Verbrennen bei erneutem Load — ist genau die Fehlerklasse, die uns heute drei
   HW-Zyklen gekostet hat.
3. **Gate-Lücken sind VORBEDINGUNG, nicht Begleitarbeit.** Der B3-Tag hat gezeigt: Suiten
   können kaputte Zustände grün pinnen (Dir-Überlauf 402/408+align8; 255-B-Objektgrenze
   still). Modularisierung MULTIPLIZIERT Suiten/Manifeste. Reihenfolge daher: erst
   Dir-Headroom-Gate + Objektgrößen-Gate + Deps-Gate, dann Pilot-Libs. (Codex' Schritt 4
   nach vorn ziehen.)
4. **Phase 2 berührt die GEPINNTE Bytecode-ABI v1 — als EIN bewusstes Projekt bündeln.**
   `block`/`return-from`, `catch`/`throw`, `unwind-protect` und Multiple Values sind keine
   Libs, sondern VM-Opcodes + lcc-Arbeit + Nachzug in BEIDEN Referenz-Engines + Korpus-
   Erweiterung (sonst reißt die Drift-Wache). Kostenklasse: das größte Einzelvorhaben seit
   dem Self-Hosting („ABI v1.1"). Nicht inkrementell hineinrutschen.
5. **Runtime-Core: Implikation aussprechen.** Ohne residenten lcc gibt es unter Strip
   KEINEN Evaluator — das Produkt wäre ein reiner Programm-Launcher (load fasl → main),
   ohne REPL. Kann gewollt sein (Spiele/Anwendungen ausliefern!), ist aber eine eigene
   Produktklasse; die Deferral-Entscheidung ist richtig.
6. **FASL×Bundles vereinheitlichen.** Bundles UND user-`compile-file`-Ausgaben sind
   dasselbe Format — Manifest/Packaging/Registry sollten von Anfang an EIN Toolpfad sein,
   sonst entstehen zwei Paketwelten (Host-D81-Packer vs. Geräte-Fasl).

## Kosten/Nutzen-Matrix (Lane-K-Schätzung)

| Vorhaben | Kosten | Nutzen | Verdikt |
| --- | --- | --- | --- |
| 3 Gates (Dir/Objektgröße/Deps) | klein (Host-Python) | verhindert die heutige Fehlerklasse dauerhaft | **SOFORT, Vorbedingung** |
| Pilot-Libs ide/fmt/fixed/strx + Manifeste + Registry | mittel (Tooling existiert: build-bytecode-lib-d81, load-lib HW-bewiesen) | Arbeitssatz-Modell bewiesen; ~+115 Slots/Syms Session-Luft im Dev-Core | **hoch, C-Einstieg** |
| einsuite-core/Dev-Core-Pin | mittel (Profil-/Footprint-Zyklen) | trägt B4-Workflow (IDE on-demand + FASL im selben Profil!) | **hoch — löst die B4-Blockade** |
| lcc-Lücken (nested-qq, &rest-Immediates, do, Fehlermeldungen m. Kontext) | klein–mittel (nur lcc/Lisp + Korpus; Fehlermeldungen kosten Bank-0-Strings!) | größtes „CL-Gefühl"/Byte | **hoch** |
| setf-MVP als BCODE-Makro-Lib (Variablen, car/cdr, getf) | klein (reine Lisp-Lib, 0 Bank-0) | incf/push/pop = Alltag | **hoch** |
| reader-printer-Strings (read-from-string, *-to-string) | klein (kleine C-Naht, eval-string-Mechanik existiert) | IDE-/Tooling-Basis | mittel-hoch |
| ABI v1.1 (nonlocale Exits + Multiple Values) | GROSS (VM+lcc+2 Referenz-Engines+Korpora; Bank-0 .text) | öffnet conditions, CL-Rundung, gethash-API | später, eigenes Projekt mit Budget-Messung VOR Entscheid |
| Phase-3-Objektarten (vectors/hash/struct/packages) | GROSS (Heap-Repräsentation, GC, Printer) | breite CL-Fläche | nach ABI v1.1, je einzeln entscheiden |

## Empfohlene Reihenfolge (minimales Delta zu Codex' Plan)

1. **Gates** (Dir-Headroom, ≤255-B-Objekt, Deps) — Codex.
2. **Pilot-Libs + Manifeste mit Messfeldern + Load-Registry** — gemeinsam.
3. **Dev-Core-Pin** (`einsuite-core`) — Codex pinnt, ich fahre xemu/HW-Gates.
4. **B4-Workflow-Gate** auf dem Dev-Core: editieren → save → compile-file → load-lib —
   der Nutzwert, auf den B wartet; schließt den B-Bogen.
5. **C-Inhalte:** lcc-Lücken + setf-MVP + strx/coll-Erweiterungen als Libs.
6. **ABI-v1.1-Entscheid** separat vorbereiten (Messung, Design-Doc, dann Nutzer-Entscheid).

## Nachtrag Dev-Core-Pin (Codex, 2026-07-06)

`einsuite-core` ist jetzt gepinnt als `make mvp-vm-stdlib-einsuite-core` mit
`VM_DIR_MAX=448` und `MAX_SYM=560`. Die fruehere 512er Directory-Annahme passt
nicht gleichzeitig mit FASL, `load-lib`, 48 Hot-Heap-Zellen und dem 1450-B-
Stack-Gap. Der gepinnte Arbeitssatz ist B4: Dev-Core + IDE on demand
(320 + 114 = 434 Slots) bzw. nach Reboot Dev-Core + FASL-Ausgabe. Alle
Pilot-Libs gleichzeitig bleiben ein separates Diaet-/Cap-Erweiterungsthema.
