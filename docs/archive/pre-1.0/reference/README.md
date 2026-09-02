# Reference Material

Stand: 2026-07-08. Dieses Verzeichnis enthaelt kuratierte Projekt- und
Hardware-Referenzen. Die Dateien sind kein aktueller Produktvertrag; verbindlich
sind die jeweiligen Strategie-, Status- und ABI-Dokumente im Haupt-`docs/`
Verzeichnis.

## Lokale PDF-Snapshots

Die PDF-Dateien werden bewusst mitgetrackt, weil mehrere Hardware- und
Library-Audits konkrete lokale Seiten-/Abschnittsvergleiche brauchen. Updates
sollen selten und explizit passieren: Datei ersetzen, Metadaten/Checksumme hier
aktualisieren und betroffene Audits erneut pruefen.

| Datei | Rolle | PDF-Datum | Seiten | Groesse | SHA256 |
| --- | --- | --- | ---: | ---: | --- |
| `MEGA65_BASIC_65_Referenzhandbuch.pdf` | BASIC-65-API-Paritaet fuer Library-Planung. | 2022-04-29 | 328 | 2.6 MB | `7ac0ecbaed122853daad222c460fad43ebb8fbbc335da41c801a1a0185fe2cfa` |
| `mega65-book.pdf` | MEGA65-Buch: 45GS02, MAP, 28-bit-Adressierung, Hardware-Math. | 2026-04-08 | 1455 | 75 MB | `c974a43257a141d30a606d84a3fabc6959c02934749f109244914688c379f786` |
| `mega65-chipset-reference.pdf` | Chipset-Referenz: VIC-IV, F018/F011, DMA, Audio, Memory Map. | 2026-04-08 | 245 | 5.1 MB | `107610ae3ea9f7e3f1e78915dcbe2cae1a6f404ca2e538762524a7e58cced220` |
| `mega65-userguide.pdf` | User Guide: Bedienung, Systemverhalten, praxisnahe Referenz. | 2026-04-08 | 342 | 6.7 MB | `0c2b82b2853689b8becb3cd7c80b60507b942d6902b7d270c851bc7e11f10cc9` |

Die gleichen Hashes stehen maschinenpruefbar in `docs/reference/SHA256SUMS`:

```sh
sha256sum -c docs/reference/SHA256SUMS
```

Hinweis: Vor einer oeffentlichen Weiterverteilung des Repos sollte die
Lizenz-/Redistributionslage dieser Drittmaterialien noch einmal separat
geprueft werden.

## Projektinterne Referenzen

Die Markdown-Dateien in diesem Verzeichnis sind historische oder technische
Referenztexte aus der Projekt-Salvage-Phase. Sie bleiben nuetzlich fuer
Architekturvergleiche, sind aber nicht automatisch aktuelle Roadmap.
