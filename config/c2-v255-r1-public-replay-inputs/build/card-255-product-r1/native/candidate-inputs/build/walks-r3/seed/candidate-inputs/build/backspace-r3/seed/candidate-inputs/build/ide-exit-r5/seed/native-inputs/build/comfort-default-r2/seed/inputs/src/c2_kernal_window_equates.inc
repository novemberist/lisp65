; Single authority for the product KERNAL-window fixed addresses.  Exactly
; one linked source selects the owner branch; every split consumer sees the
; same names as externals and therefore cannot create a second definition.

	.ifdef C2K_EQUATE_OWNER
	.globl C2K_EVENT_CODE
	.globl C2K_EVENT_MODIFIERS
	.globl C2K_EVENT_READY
	.globl C2K_FRAME_LO
	.globl C2K_FRAME_HI
	.globl C2K_NMI_COUNT
	.globl C2K_SOURCELESS_IRQS
	.globl C2K_MAP_GENERATION
	.globl C2K_STATE
	.globl C2K_UNOWNED_VIC
	.globl C2K_BREAK_PENDING
	.globl C2K_BREAK_HELD
	.globl C2K_INPUT_RING_HEAD
	.globl C2K_INPUT_RING_TAIL
	.globl C2K_INPUT_RING_BASE
	.globl C2K_INPUT_RING_SLOTS
	.globl C2K_INPUT_EVENTS_RAW
	.globl C2K_INPUT_EVENTS_SEEN
	.globl C2K_INPUT_EVENTS_STORED
	.globl C2K_INPUT_EVENTS_TAKEN
	.equ C2K_EVENT_CODE,       $ff80
	.equ C2K_EVENT_MODIFIERS,  $ff81
	.equ C2K_EVENT_READY,      $ff82
	.equ C2K_FRAME_LO,         $ff83
	.equ C2K_FRAME_HI,         $ff84
	.equ C2K_NMI_COUNT,        $ff85
	.equ C2K_SOURCELESS_IRQS,  $ff86
	.equ C2K_MAP_GENERATION,   $ff87
	.equ C2K_STATE,            $ff88
	.equ C2K_UNOWNED_VIC,      $ff89
	.equ C2K_BREAK_PENDING,    $ff8a
	.equ C2K_BREAK_HELD,       $ff8b
	.equ C2K_INPUT_RING_HEAD,  $ff8c
	.equ C2K_INPUT_RING_TAIL,  $ff8d
	.equ C2K_INPUT_RING_BASE,  $bc90
	; The allocation remains 112 bytes.  The final four cells are monotonic
	; product-health counters; 108 ring positions leave 107 usable events.
	.equ C2K_INPUT_RING_SLOTS, 108
	.equ C2K_INPUT_EVENTS_RAW,    C2K_INPUT_RING_BASE+108
	.equ C2K_INPUT_EVENTS_SEEN,   C2K_INPUT_RING_BASE+109
	.equ C2K_INPUT_EVENTS_STORED, C2K_INPUT_RING_BASE+110
	.equ C2K_INPUT_EVENTS_TAKEN,  C2K_INPUT_RING_BASE+111
	.else
	.extern C2K_EVENT_CODE
	.extern C2K_EVENT_MODIFIERS
	.extern C2K_EVENT_READY
	.extern C2K_FRAME_LO
	.extern C2K_FRAME_HI
	.extern C2K_NMI_COUNT
	.extern C2K_SOURCELESS_IRQS
	.extern C2K_MAP_GENERATION
	.extern C2K_STATE
	.extern C2K_UNOWNED_VIC
	.extern C2K_BREAK_PENDING
	.extern C2K_BREAK_HELD
	.extern C2K_INPUT_RING_HEAD
	.extern C2K_INPUT_RING_TAIL
	.extern C2K_INPUT_RING_BASE
	.extern C2K_INPUT_RING_SLOTS
	.extern C2K_INPUT_EVENTS_RAW
	.extern C2K_INPUT_EVENTS_SEEN
	.extern C2K_INPUT_EVENTS_STORED
	.extern C2K_INPUT_EVENTS_TAKEN
	.endif
