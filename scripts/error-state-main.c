/* Focused numeric/dynamic abort-state and longjmp-cleanup contract. */
#include <stdio.h>
#include <string.h>

#include "interrupt.h"
#include "vm_runtime_overlay.h"

static unsigned commit_cleanups;
static unsigned transport_cleanups;
static unsigned hook_calls;
static uint8_t hook_result;
static lisp65_error_code hook_code;
static obj hook_symbol;
static char output[64];
static unsigned output_len;

void l65m_commit_abort_cleanup(void) { commit_cleanups++; }
vm_runtime_overlay_status vm_runtime_overlay_abort_cleanup(void) {
    transport_cleanups++;
    return VM_RUNTIME_OVERLAY_OK;
}

void emit(char ch) {
    if (output_len + 1u < sizeof(output)) output[output_len++] = ch;
    output[output_len] = 0;
}

void emit_str(const char *text) {
    while (*text) emit(*text++);
}

uint8_t lisp65_error_render_code(lisp65_error_code code, obj symbol) {
    hook_calls++;
    hook_code = code;
    hook_symbol = symbol;
    if (hook_result) emit_str("rendered");
    return hook_result;
}

static void reset_output(void) { output_len = 0; output[0] = 0; }

static int expect(int condition, const char *label) {
    if (condition) return 0;
    printf("FAIL: %s\n", label);
    return 1;
}

int main(void) {
    static const char dynamic[] = "dynamic host text";
    int failed = 0;

    lisp65_error_clear();
    lisp_abort(dynamic);
    failed += expect(lisp_error_msg == dynamic, "dynamic pointer preserved");
    failed += expect(strcmp(lisp_error_msg, dynamic) == 0, "dynamic bytes preserved");
    failed += expect(lisp65_error_pending_code() == LISP65_ERR_NONE,
                     "dynamic has no numeric code");
    reset_output();
#ifdef LISP65_NUMERIC_ERRORS
    failed += expect(lisp65_error_render_pending() == 0,
                     "numeric renderer rejects dynamic text");
    failed += expect(output[0] == 0, "numeric renderer emits no dynamic text");
#else
    failed += expect(lisp65_error_render_pending() == 1, "dynamic renders");
    failed += expect(strcmp(output, dynamic) == 0, "dynamic render exact");
#endif

    lisp_abort_code(LISP65_ERR_WRITE_STRING_TYPE);
    failed += expect(lisp_error_msg != NULL && *lisp_error_msg == 0,
                     "numeric pointer sentinel safe");
    failed += expect(lisp65_error_pending_code() == LISP65_ERR_WRITE_STRING_TYPE,
                     "numeric code pending");
    failed += expect(lisp65_error_pending_symbol() == NIL, "numeric symbol nil");
    hook_result = 0;
    reset_output();
    failed += expect(lisp65_error_render_pending() == 1, "numeric fallback renders");
    failed += expect(strcmp(output, "E09") == 0, "numeric fallback Ehh");

#ifdef LISP65_NUMERIC_ERRORS
    lisp_abort_code(LISP65_ERR_RUNTIME_CATALOG);
    reset_output();
    failed += expect(lisp65_error_render_pending() == 1,
                     "resident catalog renderer succeeds");
    failed += expect(strcmp(output, "E2e catalog missing; redeploy") == 0,
                     "resident catalog renderer output");
    failed += expect(hook_calls == 1, "resident catalog renderer bypasses overlay hook");
#endif

    lisp_abort_symbol(LISP65_ERR_UNDEFINED_FUNCTION, MK_SYMI(17));
    hook_result = 1;
    reset_output();
    failed += expect(lisp65_error_render_pending() == 1, "symbol renderer succeeds");
    failed += expect(hook_code == LISP65_ERR_UNDEFINED_FUNCTION,
                     "symbol renderer code");
    failed += expect(hook_symbol == MK_SYMI(17), "symbol renderer value");
    failed += expect(strcmp(output, "rendered") == 0, "symbol renderer output");

    lisp65_error_clear();
    lisp_toplevel_active = 1;
    if (setjmp(lisp_toplevel) == 0) {
        lisp_abort_code(LISP65_ERR_VM_OOM);
        failed += expect(0, "numeric longjmp returned");
    }
    lisp_toplevel_active = 0;
    failed += expect(commit_cleanups == 1, "commit cleanup exactly once");
    failed += expect(transport_cleanups == 1, "transport cleanup exactly once");
    failed += expect(lisp65_error_pending_code() == LISP65_ERR_VM_OOM,
                     "longjmp keeps numeric state");

    lisp_toplevel_active = 1;
    if (setjmp(lisp_toplevel) == 0) {
        lisp_abort(dynamic);
        failed += expect(0, "dynamic longjmp returned");
    }
    lisp_toplevel_active = 0;
    failed += expect(commit_cleanups == 2, "dynamic commit cleanup exactly once");
    failed += expect(transport_cleanups == 2, "dynamic transport cleanup exactly once");
    failed += expect(strcmp(lisp_error_msg, dynamic) == 0, "dynamic longjmp bytes");
    failed += expect(lisp65_error_pending_code() == LISP65_ERR_NONE,
                     "dynamic longjmp clears code");

    lisp65_error_clear();
    failed += expect(lisp_error_msg == NULL, "clear message");
    failed += expect(lisp65_error_pending_code() == LISP65_ERR_NONE, "clear code");
    failed += expect(lisp65_error_pending_symbol() == NIL, "clear symbol");
    failed += expect(hook_calls == 2, "hook called only for numeric errors");

    if (failed) return 1;
    puts("error-state: PASS dynamic+numeric+symbol+fallback+cleanup");
    return 0;
}
