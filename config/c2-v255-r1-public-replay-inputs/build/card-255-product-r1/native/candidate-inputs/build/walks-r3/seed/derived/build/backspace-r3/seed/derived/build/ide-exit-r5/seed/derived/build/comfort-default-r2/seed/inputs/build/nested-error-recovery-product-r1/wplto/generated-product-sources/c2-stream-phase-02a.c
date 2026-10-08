/* The phase-02a wrapper is the sole owner of the CRC tables. */
__asm__(".pushsection .lisp65_rt_c2d_02a,\"ax\",@progbits\n"
        ".global c2_phase02a_shelf_crc16\n"
        "c2_phase02a_shelf_crc16:\n.short 0x675d\n.short 0x6ed1\n.short 0x2c82\n.short 0x275f\n.short 0x3468\n.short 0xfdee\n"
        ".global c2_phase02a_c2d_crc16\n"
        "c2_phase02a_c2d_crc16:\n.short 0x15b7\n.short 0x9a4b\n.short 0xc6ff\n.short 0x0347\n.short 0xdac0\n.short 0x2818\n"
        ".popsection\n");
#define C2_STREAM_PHASE 15
#include "c2-stream-decoder.c"
