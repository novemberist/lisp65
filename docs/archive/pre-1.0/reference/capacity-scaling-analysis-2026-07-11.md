# Kapazitäts-Skalierung: Directory-, Symbol- und Namepool-Caps anheben (2026-07-11)

Status: Analyse (Claude), kein Produktvertrag. Gegenstück zur Nachfrageseite
in `lisp65-dialect-redesign-2026-07-10.md` (§6 Symbolökonomie) und
`lisp65-ide-diet-2026-07-10.md`. Zeitliche Einordnung: Post-G6 — das
AP4-Layout ist eingefroren; dieses Dokument beantwortet nur die Frage, ob
die Caps an einer Hardware-Grenze liegen.

## Befund: Architektur-Grenze, keine Hardware-Grenze

Die Maschine bietet 384 KB Chip-RAM, 32 KB Colour-RAM und 8 MB Attic. Die
gesamte Benennungsinfrastruktur teilt sich jedoch **eine 64-KB-Bank**:

```text
Bank 5 = Stdlib-Blob (~34 KB)
       + Append-Code-Fenster
       + Namepool (9,5 KB)
       + symval/nameoff/symfn (3 × 2 B × MAX_SYM ≈ 4,3 KB)
       = exakt 64 KB
```

Dazu Bank-0-BSS-Splitter pro Eintrag: `dir_len` 1 B/Slot, `namelen`
1 B/Symbol, Directory-Offsets ~2–3 B/Slot. Beides ist verhandelbar; echte
HW-Wände (16-Bit-`obj`-ABI ≈ 16 K Symbole, 384-KB-Summe, 64-KB-
DMA-Bankgranularität — per EDMA-MB-Bytes umgehbar) liegen mindestens eine
Größenordnung entfernt.

## Entscheidungskriterium: heiß vs. kalt

- **Heiß** (pro CALL im Spiel, muss schnell erreichbar bleiben): `symfn`,
  Directory-Metadaten. „Directory nach EXT“ bleibt zu Recht abgelehnt.
- **Kalt** (nur intern/print/load): Namepool, `nameoff`, Stdlib-Blob —
  beliebig in DMA-erreichbaren Speicher verlagerbar.
- **Ungeeignet:** Banks 1–3 (HYPPO-Reset-Restage, KERNAL-Kollision; siehe
  Reset-Überlebensmatrix im Hardware-DeepDive).

## Aufwärtspfade (nach Kosten/Risiko)

1. **Colour-RAM als Tabellenbank.** ~30 der 32 KB bei `$FF80000` sind
   ungenutzt (Produkt braucht nur die 2-KB-Screen-Farben); EDMA-Zugriff ist
   HW-verifiziert (`hw-color-ram-smoke`), Flat-Access bleibt tabu.
   Namepool + `nameoff` dorthin → NAMEPOOL auf 16–32 KB hebbar, Bank 5
   gewinnt ~9,5 KB.
2. **Stdlib-Blob ins Attic.** Bytecode ist Daten und wird ohnehin per DMA
   ins Bank-0-Fenster gestreamt; im Attic wäre er reset-fest, und Bank 5
   würde fast vollständig zur Tabellenbank (MAX_SYM 1500–2000+,
   Namepool 32 K layoutseitig unkritisch). Preis: Slow-Bus ~2,5 statt
   ~20 MB/s auf Code-Fenster-Loads — nach der Codefenster-Cache-Optimierung
   (`dma_code` 310→11/Render) vermutlich verkraftbar, aber **messpflichtig**.
   Passt konzeptionell zum Runtime-Export-Schnitt (AP7/AP8).
3. **MAX_SYM anheben** (nach 1./2.): EXT-Kosten 6 B/Symbol, resident
   ~1 B/Symbol (`namelen`). 720→1024 ≈ +300 B Bank-0-BSS gegen 1811 B
   Reserve — bezahlbar. Auflage: GC-/Intern-Scan wächst linear →
   GC-Timing-Nachweis (die Symbol-Root-Storm-These war widerlegt, gilt
   aber für den heutigen Bestand).
4. **VM_DIR_MAX nur als letztes Mittel:** ~3–4 B Bank-0-BSS pro Slot und
   Hotpath-Bindung; hier liefert Tiering (IDE/IDEX/M65D) denselben Effekt
   gratis. 552→768 wäre mit ~700–850 B Reserve möglich, ist aber die
   teuerste Option.

## Empfohlene Reihenfolge (Post-G6)

Erst die Nachfrage strukturell senken (Dialekt-Redesign §6: Export-only-
Interning, `unload`), dann das Angebot heben (Colour-RAM-/Attic-Rebalance).
Beides zusammen skaliert die Session-Kapazität um Faktor 3–5, ohne ein
Hardware-Limit zu berühren. Jede Cap-Erhöhung braucht laut Sanierungsplan
einen Decision-Log-Eintrag mit Messung (GC-Timing, Latenz, Footprint-Delta).
