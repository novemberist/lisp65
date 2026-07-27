#ifndef LISP65_C2_LITE_BANK3_STAGE_H
#define LISP65_C2_LITE_BANK3_STAGE_H

#include <stdint.h>
#include "vm_runtime_overlay.h"

#if defined(LISP65_C2_LITE_BANK3_STAGING)
/* Cold product stages.  Boot is an independent pre-family L65O record;
 * Session is the final Boot-family runtime slice after decoder phase 03.
 * Neither is reachable after the Session family publishes. */
vm_runtime_overlay_status c2_lite_stage_boot_family(void);
uint8_t c2_lite_stage_session_family(void *context);
#endif

#endif /* LISP65_C2_LITE_BANK3_STAGE_H */
