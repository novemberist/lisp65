/* The phase-02a wrapper is the sole owner of the CRC tables. */
__asm__(".pushsection .lisp65_rt_c2d_02a,\"ax\",@progbits\n"
        ".global c2_phase02a_shelf_crc16\n"
        "c2_phase02a_shelf_crc16:\n.short 0x154d\n.short 0x0303\n.short 0xa3d9\n.short 0xac18\n.short 0xfb57\n.short 0x47d9\n"
        ".global c2_phase02a_c2d_crc16\n"
        "c2_phase02a_c2d_crc16:\n.short 0xc4dc\n.short 0x2b98\n.short 0xb944\n.short 0x0f62\n.short 0x6cb4\n.short 0x4f92\n"
        ".popsection\n");
#define C2_STREAM_PHASE 15
#include "c2-stream-decoder.c"
