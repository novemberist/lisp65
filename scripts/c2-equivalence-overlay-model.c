/* Host-only transport seam for the real vm_buffer_call/BUF_ENSURE_MINE path.
 *
 * vm.c and intern_service_overlay.c remain the implementations under test.
 * Only the physical Bank-3 -> $C356 transfer is modeled as a checked memcpy.
 */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "intern_service_overlay.h"
#include "symbol.h"
#include "vm_runtime_overlay.h"

#define MODEL_SERVICE_BYTES 389u
#define MODEL_EXPECTED_CALLS 3u

static uint8_t model_record[MODEL_SERVICE_BYTES];
static uint8_t model_window[MODEL_SERVICE_BYTES];
static unsigned model_calls;
static unsigned model_copies;
static unsigned model_reload_prefixes;
static unsigned model_reload_headers;
static unsigned model_literal_checks;
static uint8_t model_reload_pending;
static uint8_t model_failed;

vm_runtime_overlay_status
vm_runtime_overlay_exec(uint8_t slot, void *context, uint8_t *entry_result) {
    unsigned i;
    if (slot != LISP65_INTERN_SERVICE_SLOT || !context || !entry_result)
        return VM_RUNTIME_OVERLAY_ERR_ARGUMENT;
    for (i = 0; i < MODEL_SERVICE_BYTES; ++i)
        model_record[i] = (uint8_t)(0x5au ^ (uint8_t)i);
    memset(model_window, 0xa5, sizeof model_window);
    memcpy(model_window, model_record, sizeof model_window);
    if (memcmp(model_window, model_record, sizeof model_window))
        model_failed = 1u;
    model_calls++;
    model_copies++;
    model_reload_pending = 1u;
    *entry_result = lisp65_intern_service_entry(context);
    return VM_RUNTIME_OVERLAY_OK;
}

void l65m_commit_abort_cleanup(void) {
}

vm_runtime_overlay_status vm_runtime_overlay_abort_cleanup(void) {
    return VM_RUNTIME_OVERLAY_OK;
}

void c2_equivalence_overlay_after_code_load(
        uint8_t bank, uint16_t off, uint16_t len,
        const uint8_t *source, const uint8_t *destination) {
    obj literal;
    (void)bank;
    (void)off;
    if (memcmp(source, destination, len)) model_failed = 1u;
    if (!model_reload_pending) return;
    if (len == 7u) model_reload_prefixes++;
    if (len < 11u) return;
    memcpy(&literal, destination + 9u, sizeof literal);
    if (literal != intern("%is")) model_failed = 1u;
    model_literal_checks++;
    model_reload_headers++;
    model_reload_pending = 0u;
}

int c2_equivalence_overlay_assert(void) {
    if (model_failed || model_reload_pending
        || model_calls != MODEL_EXPECTED_CALLS
        || model_copies != MODEL_EXPECTED_CALLS
        || model_reload_prefixes != MODEL_EXPECTED_CALLS
        || model_reload_headers != MODEL_EXPECTED_CALLS
        || model_literal_checks != MODEL_EXPECTED_CALLS)
        return 0;
    printf("c2-prim68-buffer-reload: PASS calls=%u copies=%u "
           "prefix-reloads=%u header-reloads=%u literal-checks=%u\n",
           model_calls, model_copies, model_reload_prefixes,
           model_reload_headers, model_literal_checks);
    return 1;
}
