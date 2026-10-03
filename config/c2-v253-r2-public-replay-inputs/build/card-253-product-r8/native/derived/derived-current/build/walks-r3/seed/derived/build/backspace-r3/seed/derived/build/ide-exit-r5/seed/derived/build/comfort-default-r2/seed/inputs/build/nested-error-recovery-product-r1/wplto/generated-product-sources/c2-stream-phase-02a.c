/* The phase-02a wrapper is the sole owner of the CRC tables. */
__asm__(".pushsection .lisp65_rt_c2d_02a,\"ax\",@progbits\n"
        ".global c2_phase02a_shelf_crc16\n"
        "c2_phase02a_shelf_crc16:\n.short 0x7eae\n.short 0xa5c7\n.short 0x3b67\n.short 0x8f05\n.short 0x40c4\n.short 0x6b41\n"
        ".global c2_phase02a_c2d_crc16\n"
        "c2_phase02a_c2d_crc16:\n.short 0xf7c1\n.short 0x31d0\n.short 0xbf0b\n.short 0xe181\n.short 0x0c96\n.short 0x8d87\n"
        ".popsection\n");
#define C2_STREAM_PHASE 15
#include "c2-stream-decoder.c"
