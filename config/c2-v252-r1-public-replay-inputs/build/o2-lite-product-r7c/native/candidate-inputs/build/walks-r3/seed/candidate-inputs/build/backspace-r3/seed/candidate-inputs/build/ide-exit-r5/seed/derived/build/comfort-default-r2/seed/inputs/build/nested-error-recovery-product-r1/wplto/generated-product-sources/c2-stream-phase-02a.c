/* The phase-02a wrapper is the sole owner of the CRC tables. */
__asm__(".pushsection .lisp65_rt_c2d_02a,\"ax\",@progbits\n"
        ".global c2_phase02a_shelf_crc16\n"
        "c2_phase02a_shelf_crc16:\n.short 0x2504\n.short 0x4142\n.short 0xf13c\n.short 0x094d\n.short 0x75fd\n.short 0xa55d\n"
        ".global c2_phase02a_c2d_crc16\n"
        "c2_phase02a_c2d_crc16:\n.short 0x40eb\n.short 0xd92d\n.short 0xdfc2\n.short 0xb14d\n.short 0x092b\n.short 0xe5a8\n"
        ".popsection\n");
#define C2_STREAM_PHASE 15
#include "c2-stream-decoder.c"
