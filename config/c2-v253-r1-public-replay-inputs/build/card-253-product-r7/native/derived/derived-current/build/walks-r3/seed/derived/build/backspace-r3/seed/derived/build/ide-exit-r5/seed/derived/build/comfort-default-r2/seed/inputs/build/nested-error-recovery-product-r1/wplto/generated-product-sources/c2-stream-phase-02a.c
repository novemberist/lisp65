/* The phase-02a wrapper is the sole owner of the CRC tables. */
__asm__(".pushsection .lisp65_rt_c2d_02a,\"ax\",@progbits\n"
        ".global c2_phase02a_shelf_crc16\n"
        "c2_phase02a_shelf_crc16:\n.short 0xa0b1\n.short 0x7bd8\n.short 0xe578\n.short 0x511a\n.short 0x9edb\n.short 0xa3ae\n"
        ".global c2_phase02a_c2d_crc16\n"
        "c2_phase02a_c2d_crc16:\n.short 0xf7c1\n.short 0x31d0\n.short 0xbf0b\n.short 0xe181\n.short 0x0c96\n.short 0x3548\n"
        ".popsection\n");
#define C2_STREAM_PHASE 15
#include "c2-stream-decoder.c"
