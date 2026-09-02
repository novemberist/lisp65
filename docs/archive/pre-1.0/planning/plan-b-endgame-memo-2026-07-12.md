# Plan-B-Memo: v2-Workbench-Endspiel (2026-07-12)

Status: **Obsolet nach autoritativem Produktlink und Neupinnung auf 2397 B.**
Der String-Caps-Split (Prim 26/27 → Tombstone, 2542 B gemessen) schließt
beide Budgets allein: Probelink $bfe2 = 884 B unter VMA-Limit, 2676 B
Reserve (1140 B über Ziel). Insel bleibt unangetastet (korrigiert: 680 B,
nicht 932 B); Slice-Deckel und Stack-Neukalibrierung nicht benötigt.
Der volle CP5-Link weicht um den nun gebundenen 279-B-Graphkorrekturfaktor ab,
bleibt aber mit 861 B ueber dem harten Ziel. Der Baum unten bleibt historische
Referenz; ein weiterer Sweep ist ohne konkreten 1.1-Bedarf nicht autorisiert.
Ursprüngliche Baseline: 1658 B VMA- / 1400 B Reservedefizit.

## Entscheidungsbaum nach dem Marginal-Proben-Sweep

- **A: Sweep ≥ ~400 B** → kein Plan B. Proben + Insel + Slice-Deckel →
  CP5 → G5.
- **B: Sweep 150–400 B** → Hebel: **messbasierte Stack-Neukalibrierung**.
  1450/1536 wurden auf v1 *mit* Treewalk-Rekursion kalibriert; der Carrier
  ist entfernt, das v2-Stack-Profil ist ungemessen. Niedrigeres Ziel nach
  Messung = Kalibrierung, keine Cap-Diät (Decision-Log + Messung gemäß
  Sanierungsplan-Regel).
- **C: Sweep < 150 B** → Reihenfolge: (1) Stack-Neukalibrierung, falls
  nicht schon gezogen; (2) dokumentiert abgesenktes Reserveziel (z. B.
  1200 B > hartes 1024er-Minimum, mit vertraglicher 1.1-Pflicht zur
  Wiederherstellung); (3) zuletzt sichtbare Workbench-De-Scopes vs. v1 —
  teuerste Option (v2 dürfte nie weniger können als das nie ausgelieferte
  v1).
- **D: existiert, wird nicht vorbereitet** — Produktentscheidung
  (Ein-Release-v2) neu aufrollen; nur falls A–C sämtlich scheitern.

## Sofort beauftragt (read-only, szenariounabhängig)

**Stack-Neukalibrierung auf v2:** Canary-/Low-Water-Messung der linkenden
v2-Workbench über die tiefsten Workloads (Compile-Flow, IDE-Session,
GC-Stress, Persistenz). Ergebnis nützt in jedem Ast.

## Nicht tun vor der Sweep-Tabelle

C-Optionen implementieren, Insel reklassifizieren, Release-Kriterium
anfassen.
