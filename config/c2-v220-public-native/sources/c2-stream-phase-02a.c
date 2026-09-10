/* The phase-02a wrapper is the sole owner of the CRC tables. */
__asm__(".pushsection .lisp65_rt_c2d_02a,\"ax\",@progbits\n"
        ".global c2_phase02a_shelf_crc16\n"
        "c2_phase02a_shelf_crc16:\n.short 0xaa2e\n.short 0xb390\n.short 0xda44\n.short 0x099a\n.short 0x23d1\n.short 0xc246\n"
        ".global c2_phase02a_c2d_crc16\n"
        "c2_phase02a_c2d_crc16:\n.short 0xaa37\n.short 0xdc11\n.short 0x028c\n.short 0x18d5\n.short 0x4e84\n.short 0x1c78\n"
        ".popsection\n");
#define C2_STREAM_PHASE 15
#include "c2-stream-decoder.c"
