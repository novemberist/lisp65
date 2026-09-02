MEMORY {
  c2_window (rx) : ORIGIN = 0xe000, LENGTH = 0x2000
}

ENTRY(c2ku_window_dispatch)

SECTIONS {
  .lisp65_c2_kernal_window.dispatch 0xe000 : {
    KEEP(*(.lisp65_c2_kernal_window.00_dispatch))
  } > c2_window
  .lisp65_c2_kernal_window.typed_queue_driver : {
    KEEP(*(.lisp65_c2_kernal_window.typed_queue_driver))
  } > c2_window
  .lisp65_c2_kernal_window.frame_source : {
    KEEP(*(.lisp65_c2_kernal_window.frame_source))
  } > c2_window
  .lisp65_c2_kernal_window.irq_handler : {
    KEEP(*(.lisp65_c2_kernal_window.irq_handler))
  } > c2_window
  .lisp65_c2_kernal_window.nmi_and_freezer_return : {
    KEEP(*(.lisp65_c2_kernal_window.nmi_and_freezer_return))
  } > c2_window
  .lisp65_c2_kernal_window.map_switch_and_guards : {
    KEEP(*(.lisp65_c2_kernal_window.map_switch_and_guards))
  } > c2_window
  .lisp65_c2_kernal_window.post_startup_output_seam : {
    KEEP(*(.lisp65_c2_kernal_window.post_startup_output_seam))
  } > c2_window
  .lisp65_c2_kernal_window.input_capture_main 0xfd08 : {
    KEEP(*(.lisp65_c2_kernal_window.input_capture_main))
  } > c2_window
  .lisp65_c2_kernal_window.input_capture_helper 0xff67 : {
    KEEP(*(.lisp65_c2_kernal_window.input_capture_helper))
  } > c2_window

  .lisp65_c2_vectors 0xfffa : {
    KEEP(*(.lisp65_c2_vectors))
  } > c2_window
}
