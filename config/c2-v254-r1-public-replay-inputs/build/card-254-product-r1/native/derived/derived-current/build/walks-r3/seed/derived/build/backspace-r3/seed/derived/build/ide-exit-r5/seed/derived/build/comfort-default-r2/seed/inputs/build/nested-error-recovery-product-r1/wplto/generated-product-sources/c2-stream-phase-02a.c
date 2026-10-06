/* The phase-02a wrapper is the sole owner of the CRC tables. */
__asm__(".pushsection .lisp65_rt_c2d_02a,\"ax\",@progbits\n"
        ".global c2_phase02a_shelf_crc16\n"
        "c2_phase02a_shelf_crc16:\n.short 0xdc8b\n.short 0x0c51\n.short 0xb7e0\n.short 0xfdc5\n.short 0xd4a0\n.short 0x675c\n"
        ".global c2_phase02a_c2d_crc16\n"
        "c2_phase02a_c2d_crc16:\n.short 0x162a\n.short 0x9e8b\n.short 0xa25e\n.short 0xd4fd\n.short 0x5bde\n.short 0x8f95\n"
        ".popsection\n");
#define C2_STREAM_PHASE 15
#include "c2-stream-decoder.c"
