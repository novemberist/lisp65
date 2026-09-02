; Test-Fixture fuer lib-autoload: wird per AUTOLOAD beim ersten Aufruf geladen.
; Setzt ein Flag (damit Tests "wurde geladen?" pruefen koennen) und definiert
; die echte Funktion, die den Stub ueberschreibt.
(SETQ *AUTOLOAD-FIXTURE-LOADED* T)
(DE TRIPLE (X) (TIMES X 3))
