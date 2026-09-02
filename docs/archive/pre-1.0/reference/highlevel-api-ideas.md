# High-Level API Ideas

Stand: 2026-06-28. Diese Datei sammelt bewusst nicht-residente Phase-5-Ideen. Sie
ist kein Kernvertrag; verbindlich fuer Residenzentscheidungen ist
`phase5-hardware.md`.

## Prinzip

Die High-Level-API soll Programme lesbar machen, ohne den residenten Kern zu
vergroessern. Sie darf Datenstrukturen, Tabellen und Policy enthalten, solange sie
ladbar bleibt und hostseitig testbar ist.

## Aktuelle Lisp-Bausteine

- `lib-c64hw.lsp`: Registeradressen, Farben, Sprite-X-MSB-Rechnung, SID-Frequenzen.
- `lib-c64fx.lsp`: Linien-/Kreis-Punktlisten, Text-Art zu Sprite-Bytes,
  Melodie-Daten zu Frequenzen.
- `lib-c64io.lsp`: POKE-basierte Wirkung auf Bildschirm, Bitmap, Sprite und SID.

## Platform-Layer-Namen

Diese Namen sind die portable Zielrichtung fuer spaetere C64/MEGA65-Backends:

```lisp
(read-key)
(draw-line x0 y0 x1 y1)
(play-sample id)
(load-file name)
```

Auf dem C64 duerfen diese zunaechst einfach auf vorhandene Bibliotheksfunktionen
und `PEEK`/`POKE` abbilden. Ein Backend wird erst resident, wenn Messungen zeigen,
dass die Bibliotheksvariante fuer eine echte Demo zu teuer ist.

## Demo-Pfad

Ein sinnvoller naechster sichtbarer Meilenstein ist eine kleine Demo, die nur diese
Schicht nutzt:

- Tastatur lesen (`read-key` oder `lib-c64key.lsp`).
- Sprite bewegen (`sprite-at`/`sprite-on`, spaeter optional natives `SPRITE`).
- Linie oder Punkt zeichnen (`line`/`plot`).
- Ton ausloesen (`sound`, spaeter optional natives `SID-VOICE`).

Das ist absichtlich keine VM-/Heap-Arbeit.
