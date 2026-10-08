/* The phase-02a wrapper is the sole owner of the CRC tables. */
__asm__(".pushsection .lisp65_rt_c2d_02a,\"ax\",@progbits\n"
        ".global c2_phase02a_shelf_crc16\n"
        "c2_phase02a_shelf_crc16:\n.short 0xd200\n.short 0xd744\n.short 0x60e2\n.short 0xd4f2\n.short 0x8b0d\n.short 0x3fcc\n"
        ".global c2_phase02a_c2d_crc16\n"
        "c2_phase02a_c2d_crc16:\n.short 0x162a\n.short 0x9033\n.short 0xf83c\n.short 0x344d\n.short 0x86a6\n.short 0x7c46\n"
        ".popsection\n");
#define C2_STREAM_PHASE 15
#include "c2-stream-decoder.c"
