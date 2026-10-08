/* The phase-02a wrapper is the sole owner of the CRC tables. */
__asm__(".pushsection .lisp65_rt_c2d_02a,\"ax\",@progbits\n"
        ".global c2_phase02a_shelf_crc16\n"
        "c2_phase02a_shelf_crc16:\n.short 0x2504\n.short 0x9551\n.short 0x50f2\n.short 0x3a38\n.short 0x1547\n.short 0x9628\n"
        ".global c2_phase02a_c2d_crc16\n"
        "c2_phase02a_c2d_crc16:\n.short 0x40eb\n.short 0xeae7\n.short 0x7867\n.short 0xe787\n.short 0xd761\n.short 0x3be2\n"
        ".popsection\n");
#define C2_STREAM_PHASE 15
#include "c2-stream-decoder.c"
