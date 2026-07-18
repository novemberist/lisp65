/* Native C-VM execution proof for the generated Workbench banner.
 *
 * The visual P0 oracle proves the compiled drawing contract, but it does not
 * exercise vm.c's small streaming window.  This carrier deliberately uses the
 * product VM_CODEBUF and the generated resident artifact so a large banner
 * helper cannot pass solely in the Python interpreter.
 */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "interrupt.h"
#include "mem.h"
#include "screen.h"
#include "symbol.h"
#include "vm.h"
#include "vm_embed.h"
#include "stdlib-p0.h"

static uint8_t ext_code[65536];

void vm_ext_write(const uint8_t *src, uint16_t len, uint8_t bank,
                  uint16_t off) {
    if (bank != lisp65_stdlib_bank ||
        (uint32_t)off + len > sizeof ext_code)
        return;
    memcpy(ext_code + off, src, len);
}

void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst) {
    if (bank != lisp65_stdlib_bank ||
        (uint32_t)off + len > sizeof ext_code) {
        memset(dst, 0, len);
        return;
    }
    memcpy(dst, ext_code + off, len);
}

/* Only write-char is reached after the direct-at banner operations. */
uint8_t eval_v2_workbench_service(uint8_t id, const obj *args, obj *result) {
    if (id != 45u || !IS_FIX(args[0])) return 0;
    scr_putc((char)(FIXVAL(args[0]) & 0xff));
    *result = args[0];
    return 1;
}

static int fail(const char *message) {
    fprintf(stderr, "v11-repl-banner-vm: FAIL %s status=%u (%s) row=%u\n",
            message, (unsigned)vm_status, vm_status_message(),
            (unsigned)scr_row());
    return 1;
}

int main(void) {
    obj result;

    mem_init();
    vm_dir_reset();
    vm_init();
    scr_init();
    vm_load_embedded_stdlib();
    if (lisp_error_msg) return fail("resident artifact setup");

    vm_status = VM_OK;
    result = vm_run_dir(LISP65_BYTECODE_STDLIB_REPL_BANNER_ENTRY, 0, 0);
    if (vm_status != VM_OK) return fail("native C-VM execution");
    if (result != NIL) return fail("result is not nil");
    if (scr_row() != 9u) return fail("first-prompt row drift");

    puts("v11-repl-banner-vm: PASS native-c-vm codebuf=56 row=9");
    return 0;
}
