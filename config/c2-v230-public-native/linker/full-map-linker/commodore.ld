MEMORY { library_symbol_functions (rw) : ORIGIN = 0x2e720, LENGTH = 1590 }
/* Generated v1.8 parent for the owned platform c.ld. */
__rc0 = __basic_zp_start;
INCLUDE imag-regs.ld
__basic_zp_size = __basic_zp_end - __basic_zp_start;
MEMORY { zp : ORIGIN = __rc31 + 1, LENGTH = __basic_zp_end - (__rc31 + 1) }
INPUT(basic-header.o)
REGION_ALIAS("c_readonly", ram)
REGION_ALIAS("c_writeable", ram)
SECTIONS {
    .basic_header 0x2001 : { *(.basic_header) }
    INCLUDE c.ld
}
