/* Block 2.6 Card 3: execute malformed bytecode against the real VM. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "eval.h"
#include "mem.h"
#include "vm.h"

static uint8_t code_store[96];
static unsigned poke_calls;
static uint8_t poke_index;
static uint8_t poke_value;
static int failures;

/* Device-owned seams are deterministic in this source-bound host fixture. */
unsigned char io_disk_read_sector(unsigned char track, unsigned char sector) {
    (void)track; (void)sector; return 0;
}
unsigned char io_disk_byte(unsigned char index) { (void)index; return 0; }
unsigned char io_disk_load_chain(unsigned char track, unsigned char sector) {
    (void)track; (void)sector; return 0;
}
void io_disk_scratch_poke(unsigned char index, unsigned char value) {
    ++poke_calls; poke_index = index; poke_value = value;
}
unsigned char io_disk_write_sector(unsigned char track, unsigned char sector) {
    (void)track; (void)sector; return 0;
}
void io_disk_transaction_capture_mount_token(void) {}
unsigned char io_disk_transaction_classify_status(unsigned char status) {
    return status;
}
unsigned char io_disk_write_sector_guarded(unsigned char track,
                                            unsigned char sector) {
    return io_disk_write_sector(track, sector);
}
unsigned char io_disk_stage_put(unsigned int index, unsigned char value) {
    (void)index; (void)value; return 1;
}
unsigned char io_disk_save_named(const char *name, unsigned int length) {
    (void)name; (void)length; return 0;
}
const char *io_load_file(const char *name) { (void)name; return NULL; }
int lcc_region_alloc(uint16_t length, uint8_t *bank, uint16_t *off) {
    (void)length; (void)bank; (void)off; return 0;
}
void lcc_region_write(uint8_t bank, uint16_t off,
                      const uint8_t *source, uint16_t length) {
    (void)bank; (void)off; (void)source; (void)length;
}
uint8_t lisp65_error_render_code(lisp65_error_code code, obj symbol) {
    (void)code; (void)symbol; return 0;
}
void vm_code_load(uint8_t bank, uint16_t off, uint16_t len, uint8_t *dst) {
    (void)bank;
    if ((uint16_t)(off + len) > sizeof code_store) {
        memset(dst, 0, len); return;
    }
    memcpy(dst, code_store + off, len);
}

#define CHECK(name, condition) do { \
    if (!(condition)) { \
        fprintf(stderr, "card3-vm-hardening: FAIL %s status=%u poke=%u\n", \
                (name), (unsigned)vm_status, poke_calls); \
        ++failures; \
    } \
} while (0)

static uint16_t emit(const uint8_t *payload, uint8_t payload_len,
                     uint8_t nargs, uint8_t nlocals, uint8_t flags) {
    memset(code_store, 0, sizeof code_store);
    code_store[CO_OFF_MAGIC] = CO_MAGIC;
    code_store[CO_OFF_NARGS] = nargs;
    code_store[CO_OFF_NLOCS] = nlocals;
    code_store[CO_OFF_FLAGS] = flags;
    code_store[CO_OFF_CLEN] = payload_len;
    memcpy(code_store + CO_OFF_LITTAB, payload, payload_len);
    return (uint16_t)(CO_OFF_LITTAB + payload_len);
}

static void reset_observer(void) {
    poke_calls = 0; poke_index = 0xffu; poke_value = 0xffu;
    vm_status = VM_OK; gc_rootsp = 0;
}

static void test_slot_operand(void) {
    static const uint8_t payload[] = {OP_LOADL, 0, OP_RET};
    uint16_t length = emit(payload, sizeof payload, 0, 0,
                           CO_FLAG_STRICT_ARITY);
    reset_observer();
    (void)vm_run(0, 0, length, NULL, 0);
    CHECK("slot operand outside nargs+nlocals", vm_status == VM_BADOPCODE);
}

static void test_rest_transient_bound(void) {
    static const uint8_t payload[] = {OP_PUSHNIL, OP_RET};
    obj args[VM_MAXARGS];
    uint16_t length;
    uint8_t index;
    for (index = 0; index < VM_MAXARGS; ++index) args[index] = MKFIX(index);
    length = emit(payload, sizeof payload, 0, 1,
                  CO_ARITY_FLAGS(0, 1));
    reset_observer();
    gc_rootsp = GC_ROOTS - 8u;
    (void)vm_run(0, 0, length, args, VM_MAXARGS);
    CHECK("REST transient frame bound", vm_status == VM_STACKOVER &&
          gc_rootsp == GC_ROOTS - 8u);
}

static void test_pop_fail_stop(void) {
    static const uint8_t payload[] = {OP_CALLPRIM, 21, 2, OP_RET};
    uint16_t length = emit(payload, sizeof payload, 0, 0,
                           CO_FLAG_STRICT_ARITY);
    reset_observer();
    (void)vm_run(0, 0, length, NULL, 0);
    CHECK("POP underflow exits opcode before disk poke",
          vm_status == VM_BADOPCODE && poke_calls == 0);
}

static void test_disk_poke_domain(void) {
    static const uint8_t bad[] = {OP_PUSHI8, 7, OP_CALLPRIM, 21, 1, OP_RET};
    static const uint8_t good[] = {
        OP_PUSHI8, 4, OP_PUSHI8, 9, OP_CALLPRIM, 21, 2, OP_RET};
    uint16_t length = emit(bad, sizeof bad, 0, 0, CO_FLAG_STRICT_ARITY);
    reset_observer();
    (void)vm_run(0, 0, length, NULL, 0);
    CHECK("disk poke short arity", vm_status == VM_TYPEERROR && poke_calls == 0);

    length = emit(good, sizeof good, 0, 0, CO_FLAG_STRICT_ARITY);
    reset_observer();
    (void)vm_run(0, 0, length, NULL, 0);
    CHECK("disk poke valid control", vm_status == VM_OK && poke_calls == 1 &&
          poke_index == 4u && poke_value == 9u);
}

int main(void) {
    eval_init();
    test_slot_operand();
    test_rest_transient_bound();
    test_pop_fail_stop();
    test_disk_poke_domain();
    if (failures) return 1;
    puts("card3-vm-hardening: PASS slot=badopcode rest=stackover pop=fail-stop disk=domain");
    return 0;
}
