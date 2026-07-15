; Disk-macro-only cases intentionally cannot be compared with the device compiler.
; The compiler currently supports only atomic case keys. The disk-macro tree-walk
; route may be broader because it adds no Bank-0 cost.
(case (quote b) ((a c) 1) ((b d) 2) (otherwise 3))
(case (quote q) ((a c) 1) (otherwise 3))
(case (quote a) ((a) 11) (t 22))
