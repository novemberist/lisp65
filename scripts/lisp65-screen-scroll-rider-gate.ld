/* C2-ready rider binding fragment. It is deliberately not included by the
 * 44-slice v1.1 product linker: runtime_overlay_bank rejects undeclared,
 * dormant members. C2 must include this fragment together with the declared
 * rider slice and set __lisp65_screen_scroll_required_param=1. */
__lisp65_screen_scroll_required =
    DEFINED(__lisp65_screen_scroll_required_param)
        ? __lisp65_screen_scroll_required_param : 0;

SECTIONS {
    .lisp65_rt_screen_scroll __lisp65_workbench_runtime_overlay_vma : {
        KEEP(*(.lisp65_rt_screen_scroll))
        KEEP(*(.lisp65_rt_screen_scroll_data))
    } >ram
}

__lisp65_rt_screen_scroll_start = ADDR(.lisp65_rt_screen_scroll);
__lisp65_rt_screen_scroll_end =
    ADDR(.lisp65_rt_screen_scroll) + SIZEOF(.lisp65_rt_screen_scroll);
__lisp65_rt_screen_scroll_entry = lisp65_screen_scroll_overlay_entry;

ASSERT(!__lisp65_screen_scroll_required ||
       (SIZEOF(.lisp65_rt_screen_scroll) > 0 &&
        SIZEOF(.lisp65_rt_screen_scroll) <= 1792 &&
        __lisp65_rt_screen_scroll_end <= __lisp65_workbench_runtime_overlay_limit),
       "required runtime overlay color-safe screen scroll section is empty or unsafe");
