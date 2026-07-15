#ifndef LISP65_F011_CONTEXT_H
#define LISP65_F011_CONTEXT_H

/* A disk transaction must not inherit mutable machine state from the
 * freezer, monitor, ROM or a preceding transaction.  Keep these writes in
 * one shared source so the product, cold stager and hardware carriers cannot
 * disagree about buffer ownership.
 *
 * $D689.7: 0 = F011 buffer, 1 = direct-SD buffer.
 * $D680:   $81 maps the selected buffer at $DE00, $82 removes the window.
 * $D080:   $60 selects drive 0 and establishes the motor/LED context used by
 *           the single-drive product contract.
 */
#define LISP65_F011_REG_CONTROL       0xd080u
#define LISP65_SD_REG_COMMAND         0xd680u
#define LISP65_SD_REG_BUFFER_SELECT   0xd689u
#define LISP65_SD_REG_MOUNT_CONTROL   0xd68bu
#define LISP65_SD_REG_MOUNT_BASE0     0xd68cu
#define LISP65_SD_REG_MOUNT_BASE1     0xd68du
#define LISP65_SD_REG_MOUNT_BASE2     0xd68eu
#define LISP65_SD_REG_MOUNT_BASE3     0xd68fu

#define LISP65_F011_DRIVE0_MOTOR      0x60u
#define LISP65_F011_BUFFER_SELECTED   0x00u
#define LISP65_BUFFER_WINDOW_MAP      0x81u
#define LISP65_BUFFER_WINDOW_UNMAP    0x82u

#ifndef LISP65_F011_WRITE8
#define LISP65_F011_WRITE8(address, value) \
    (*(volatile unsigned char *)(address) = (unsigned char)(value))
#endif

#ifndef LISP65_F011_READ8
#define LISP65_F011_READ8(address) (*(volatile unsigned char *)(address))
#endif

/* Hypervisor-owned mounted-image identity.  The product never writes these
 * registers.  D68B (drive-0 media/image/WP state) and the exact D68C..D68F
 * SD image base form the hardware half of an M65D transaction token. */
static inline unsigned char lisp65_f011_mount_token_matches(
    unsigned char control,
    unsigned char base0,
    unsigned char base1,
    unsigned char base2,
    unsigned char base3
) {
    return (unsigned char)(
        LISP65_F011_READ8(LISP65_SD_REG_MOUNT_CONTROL) == control &&
        LISP65_F011_READ8(LISP65_SD_REG_MOUNT_BASE0) == base0 &&
        LISP65_F011_READ8(LISP65_SD_REG_MOUNT_BASE1) == base1 &&
        LISP65_F011_READ8(LISP65_SD_REG_MOUNT_BASE2) == base2 &&
        LISP65_F011_READ8(LISP65_SD_REG_MOUNT_BASE3) == base3
    );
}

static inline void lisp65_f011_take_context(void) {
    /* Close a window possibly left by ROM/freezer code before selecting the
     * controller and buffer for this transaction. */
    LISP65_F011_WRITE8(LISP65_SD_REG_COMMAND, LISP65_BUFFER_WINDOW_UNMAP);
    LISP65_F011_WRITE8(LISP65_F011_REG_CONTROL, LISP65_F011_DRIVE0_MOTOR);
    LISP65_F011_WRITE8(LISP65_SD_REG_BUFFER_SELECT, LISP65_F011_BUFFER_SELECTED);
}

static inline void lisp65_f011_map_buffer(void) {
    LISP65_F011_WRITE8(LISP65_SD_REG_COMMAND, LISP65_BUFFER_WINDOW_MAP);
}

static inline void lisp65_f011_unmap_buffer(void) {
    LISP65_F011_WRITE8(LISP65_SD_REG_COMMAND, LISP65_BUFFER_WINDOW_UNMAP);
}

#endif
