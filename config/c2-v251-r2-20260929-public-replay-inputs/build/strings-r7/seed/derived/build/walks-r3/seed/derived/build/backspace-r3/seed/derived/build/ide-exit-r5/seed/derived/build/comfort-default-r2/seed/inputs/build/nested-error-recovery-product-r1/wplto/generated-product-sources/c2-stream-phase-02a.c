/* The phase-02a wrapper is the sole owner of the CRC tables. */
__asm__(".pushsection .lisp65_rt_c2d_02a,\"ax\",@progbits\n"
        ".global c2_phase02a_shelf_crc16\n"
        "c2_phase02a_shelf_crc16:\n.short 0xf7cc\n.short 0xb1c7\n.short 0x4ca4\n.short 0x9e1a\n.short 0xaf6d\n.short 0x5c0c\n"
        ".global c2_phase02a_c2d_crc16\n"
        "c2_phase02a_c2d_crc16:\n.short 0x5dbc\n.short 0x7437\n.short 0x2baf\n.short 0x35a7\n.short 0x34bc\n.short 0x1ec8\n"
        ".popsection\n");
#define C2_STREAM_PHASE 15
#include "c2-stream-decoder.c"
