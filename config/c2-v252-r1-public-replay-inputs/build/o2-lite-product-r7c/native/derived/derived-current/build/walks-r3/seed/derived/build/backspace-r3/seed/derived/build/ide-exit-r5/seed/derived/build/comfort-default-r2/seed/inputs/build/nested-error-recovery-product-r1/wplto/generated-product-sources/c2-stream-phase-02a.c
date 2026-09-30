/* The phase-02a wrapper is the sole owner of the CRC tables. */
__asm__(".pushsection .lisp65_rt_c2d_02a,\"ax\",@progbits\n"
        ".global c2_phase02a_shelf_crc16\n"
        "c2_phase02a_shelf_crc16:\n.short 0xf257\n.short 0xe3d2\n.short 0x8f7a\n.short 0x0790\n.short 0x3f31\n.short 0x5c1f\n"
        ".global c2_phase02a_c2d_crc16\n"
        "c2_phase02a_c2d_crc16:\n.short 0xb367\n.short 0xe619\n.short 0x12c9\n.short 0x3125\n.short 0x4920\n.short 0x7c86\n"
        ".popsection\n");
#define C2_STREAM_PHASE 15
#include "c2-stream-decoder.c"
