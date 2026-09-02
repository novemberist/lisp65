MEMORY {
  c2lt_window (rx) : ORIGIN = 0xe000, LENGTH = 0x2000
}

ENTRY(c2lt_window_dispatch)

SECTIONS {
  .lisp65_c2lt_window.dispatch 0xe000 : {
    KEEP(*(.lisp65_c2lt_window.dispatch))
  } > c2lt_window
  .lisp65_c2lt_window.queue : {
    KEEP(*(.lisp65_c2lt_window.queue))
  } > c2lt_window
  .lisp65_c2lt_window.irq : {
    KEEP(*(.lisp65_c2lt_window.irq))
  } > c2lt_window
  .lisp65_c2lt_window.nmi : {
    KEEP(*(.lisp65_c2lt_window.nmi))
  } > c2lt_window
  .lisp65_c2lt_window.fail : {
    KEEP(*(.lisp65_c2lt_window.fail))
  } > c2lt_window
  .lisp65_c2lt_vectors 0xfffa : {
    KEEP(*(.lisp65_c2lt_vectors))
  } > c2lt_window
}
