/* The phase-02a wrapper is the sole owner of the CRC tables. */
__asm__(".pushsection .lisp65_rt_c2d_02a,\"ax\",@progbits\n"
        ".global c2_phase02a_shelf_crc16\n"
        "c2_phase02a_shelf_crc16:\n.short 0xefe4\n.short 0x232e\n.short 0x13f6\n.short 0x2b72\n.short 0xcfb0\n.short 0x2701\n"
        ".global c2_phase02a_c2d_crc16\n"
        "c2_phase02a_c2d_crc16:\n.short 0xd12f\n.short 0x0273\n.short 0xb2ec\n.short 0xace4\n.short 0xd275\n.short 0xf801\n"
        ".popsection\n");
#define C2_STREAM_PHASE 15
#include "c2-stream-decoder.c"
