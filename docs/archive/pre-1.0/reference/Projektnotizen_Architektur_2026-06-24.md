# Architektur-Notizen -- Gespräch vom 24.06.2026

## Zusammenfassung

Im Laufe der Diskussion hat sich ein Perspektivwechsel ergeben:

> Das Projekt ist nicht mehr nur „ein Lisp für den C64", sondern
> entwickelt sich zu einer kleinen Sprach- und Laufzeitplattform mit
> mehreren Backends.

Der C64 bleibt die Minimalplattform und dient als Architektur- und
Effizienztest. Der MEGA65 wird zur Plattform, auf der sich dieselbe
Architektur ohne die engen Beschränkungen des C64 weiterentwickeln kann.

------------------------------------------------------------------------

# Leitgedanken

## 1. Bytecode als zentrale Schnittstelle

Empfohlene Architektur:

``` text
Host (Common Lisp)
        │
   Frontend
        │
        ▼
      IR
        │
        ▼
     Bytecode
   ┌────┴────┐
   ▼         ▼
C64 VM    MEGA65 VM
```

Der Bytecode sollte möglichst früh stabilisiert werden (Version 1),
damit Compiler, Optimierer und spätere native Backends unabhängig
weiterentwickelt werden können.

------------------------------------------------------------------------

## 2. Plattform-Layer

Frühzeitig eine kleine Hardware-Abstraktion definieren.

Beispiele:

-   mouse-position
-   mouse-buttons
-   draw-line
-   draw-rectangle
-   play-sample
-   read-key
-   load-file

Dadurch können Anwendungen dieselbe API auf PC, C64 und MEGA65
verwenden.

------------------------------------------------------------------------

## 3. Module statt großer Sprachkern

Alles, was nicht zwingend Bestandteil der VM sein muss, sollte als
Library implementiert werden.

Beispiele:

-   map
-   reduce
-   append
-   assoc
-   Dispatch-System
-   Objektsystem

Die VM bleibt bewusst klein.

------------------------------------------------------------------------

## 4. Einfaches Modulsystem

Früh ein kleines System wie

``` lisp
(require 'graphics)
(require 'math)
(require 'dispatch)
```

einführen.

Keine komplexe Paketverwaltung, sondern eine schlanke Grundlage.

------------------------------------------------------------------------

## 5. C64 und MEGA65 unterschiedlich nutzen

### C64

-   Referenzplattform
-   Minimalziel
-   Architekturtest
-   Beweis für Effizienz

### MEGA65

-   Skalierungsplattform
-   größere Libraries
-   USB-Maus
-   DMA-Audio
-   größerer Heap
-   komfortablere Entwicklungsumgebung
-   optionale Sprachfeatures

------------------------------------------------------------------------

## 6. Mini-CLOS / Multiple Dispatch

Nicht Bestandteil des Sprachkerns.

Empfehlung:

C64

-   Structs
-   einfache Typinformationen
-   Single Dispatch

MEGA65

-   Structs
-   abstrakte Typen
-   Multiple Dispatch
-   als optionale Library

------------------------------------------------------------------------

## 7. Tukan als Architekturtest

Tukan sollte langfristig nicht nur ein Grafikprogramm sein.

Es validiert:

-   Grafik-API
-   Maus
-   Dateisystem
-   Performance
-   Toolchain
-   Libraries

------------------------------------------------------------------------

## 8. Adventure-Engine

Auch die Adventure-Engine dient als Test der Plattform.

Sie überprüft:

-   VM
-   Garbage Collector
-   Objektmodell
-   Ereignissystem
-   Module
-   Laufzeitbibliotheken

------------------------------------------------------------------------

## 9. Teststrategie

Empfohlene Reihenfolge:

``` text
Host-VM
    ↓
VICE
    ↓
xemu (MEGA65)
    ↓
echter MEGA65
```

------------------------------------------------------------------------

## 10. Performance

Die wichtigste Erkenntnis des Gesprächs:

Der C64 definiert nicht mehr das eigentliche Ziel.

Er definiert die Minimalanforderung.

Der MEGA65 zeigt, wie weit dieselbe Architektur wachsen kann.

------------------------------------------------------------------------

# Langfristige Vision

``` text
                 Lisp Source
                      │
          ┌───────────┴───────────┐
          │                       │
     Bytecode VM             Native Compiler
          │                       │
    ┌─────┼─────┐           ┌─────┼─────┐
    │     │     │           │     │     │
   PC    C64  MEGA65      6510 45GS02
```

------------------------------------------------------------------------

# Persönliche Einschätzung

Das Projekt wirkt inzwischen eher wie der Aufbau einer kleinen
Sprachplattform als wie die Modernisierung eines historischen
Lisp-Systems.

Die Kombination aus

-   Host-Compiler
-   Bytecode
-   reproduzierbaren Tests
-   Referenzport
-   modularen Libraries
-   späterem MEGA65-Backend

bildet eine sehr tragfähige Grundlage.

Eine sinnvolle zusätzliche Projektphase wäre:

**Runtime 2.0**

mit Fokus auf:

-   Plattform-Layer
-   Bytecode v1
-   Module
-   MEGA65-Port
-   DMA-Audio
-   USB-Maus
-   optionale High-Level-Libraries

Diese Punkte müssen nicht sofort umgesetzt werden, sollten aber die
langfristige Architektur beeinflussen.
