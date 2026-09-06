/* Temporary F011 first-read/first-failure witness, authorized by 5b59fca5.
 * Remove after diagnosis unless separately repriced. Three bytes, no history:
 * a first failure replaces a first success, then the record is immutable.
 * D082 is the consumed sample. D083 (read-only status, Chipset Reference
 * printed pp.128-129) is read only when publishing a record. Never read D087.
 * The owner is explicitly NOLOAD; main resets its tag before any disk read.
 */
#ifndef LISP65_F011_STATUS_WITNESS_H
#define LISP65_F011_STATUS_WITNESS_H
#include <stdint.h>
enum {
    F011_UNSEEN = 0,
    F011_FIRST_SUCCESS = 1,
    F011_MASK_FAILURE = 2,
    F011_SPINUP_TIMEOUT = 3,
    F011_READ_TIMEOUT = 4
};
typedef struct {
    uint8_t tag, d082, d083;
} f011_status_record;
_Static_assert(sizeof(f011_status_record) == 3, "F011 witness owns exactly three bytes");
extern volatile f011_status_record lisp65_f011_status_state;

#ifdef LISP65_F011_INSTRUMENT_BODY
volatile f011_status_record lisp65_f011_status_state
    __attribute__((section(".noinit.lisp65_f011_status"), used));

static __attribute__((noinline)) LISP65_C2_MAPPED_F011_COLD_FN
void f011_status_observe(uint8_t tag, uint8_t consumed_status) {
    if (lisp65_f011_status_state.tag > F011_FIRST_SUCCESS ||
        (lisp65_f011_status_state.tag == F011_FIRST_SUCCESS &&
         tag == F011_FIRST_SUCCESS)) return;
    lisp65_f011_status_state.d082 = consumed_status;
    lisp65_f011_status_state.d083 = LISP65_F011_READ8(0xd083u);
    __asm__ volatile("" ::: "memory");
    lisp65_f011_status_state.tag = tag; /* publish last; read after completion */
}
#endif
#endif
