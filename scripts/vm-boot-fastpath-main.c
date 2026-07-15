/* Native contract harness for the profile-bound three-slice boot transaction. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "interrupt.h"
#include "mem.h"
#include "symbol.h"
#include "vm.h"
#include "vm_boot_fastpath.h"
#include "vm_embed.h"
#include "vm_runtime_overlay.h"

static const uint8_t pristine_image[LISP65_BOOT_STDLIB_IMAGE_BYTES] = {
    0x65,0x00,0xcc,0xcc,0xcc,0xcc,0xcc,0xcc,
    0x4c,0x36,0x35,0x4d,0x01,0x26,0x00,0x00,
    0x00,0x00,0x05,0x00,0x08,0x00,0x6c,0x00,
    0x01,0x00,0x03,0x00,0x03,0x00,0x03,0x00,
    0x26,0x00,0x2e,0x00,0x34,0x00,0x52,0x00,
    0x5e,0x00,0x0e,0x00,0x00,0x00,0x00,0x00,
    0x05,0x00,0x00,0x00,0x08,0x00,0x00,0x00,
    0x01,0x00,0x02,0x00,0x01,0x00,0x2a,0x00,
    0x00,0x00,0x00,0x00,0xff,0xff,0x04,0x00,
    0x00,0x00,0x00,0x00,0x00,0x00,0x07,0x00,
    0x07,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
    0x0b,0x00,0x02,0x00,0x00,0x00,0x04,0x00,
    0x01,0x00,0x06,0x00,0x02,0x00,
    'b','o','o','t','f','n',0,'f','o','o',0,'h','i',0
};

static uint8_t bank5[256];
static int failures;
static unsigned ext_writes;

const uint8_t lisp65_stdlib_blob[] = {0};
const uint16_t lisp65_stdlib_blob_len = LISP65_BOOT_STDLIB_BLOB_BYTES;
const uint8_t lisp65_stdlib_bank = LISP65_BOOT_STDLIB_BANK;
const uint16_t lisp65_stdlib_off = LISP65_BOOT_STDLIB_OFF;
const vm_embed_entry lisp65_embed[] = {{0,0,0,0,0}};
const uint16_t lisp65_embed_count = 0;

void l65m_commit_abort_cleanup(void) {}
vm_runtime_overlay_status vm_runtime_overlay_abort_cleanup(void) {
    return VM_RUNTIME_OVERLAY_OK;
}

void vm_code_load(uint8_t bank, uint16_t off, uint16_t length, uint8_t *dst) {
    if (bank != LISP65_BOOT_STDLIB_BANK || (uint32_t)off + length > sizeof bank5) {
        memset(dst, 0, length); return;
    }
    memcpy(dst, bank5 + off, length);
}

void vm_ext_write(const uint8_t *source, uint16_t length,
                  uint8_t bank, uint16_t off) {
    if (bank == LISP65_BOOT_STDLIB_BANK && (uint32_t)off + length <= sizeof bank5) {
        ext_writes++;
        memcpy(bank5 + off, source, length);
    }
}

uint16_t vm_ext_code_watermark(void) {
    return LISP65_BOOT_STDLIB_BLOB_BYTES;
}

static void expect(int condition, const char *name) {
    if (condition) return;
    fprintf(stderr, "vm-boot-fastpath: FAIL %s\n", name);
    failures++;
}

static uint16_t fixture_crc(void) {
    uint16_t crc = 0xffffu, n;
    uint8_t bits;
    for (n = 0; n < sizeof pristine_image; n++) {
        crc ^= (uint16_t)bank5[n] << 8;
        bits = 8;
        while (bits--)
            crc = crc & 0x8000u ? (uint16_t)((crc << 1) ^ 0x1021u)
                                : (uint16_t)(crc << 1);
    }
    return crc;
}

static void reset_fixture(void) {
    memcpy(bank5, pristine_image, sizeof pristine_image);
    memset(bank5 + sizeof pristine_image, 0xa5,
           sizeof bank5 - sizeof pristine_image);
    lisp_error_msg = 0;
    mem_oom = 0;
    mem_init();
    vm_dir_reset();
    vm_init();
    ext_writes = 0;
}

static obj patched_obj(uint16_t off) {
    return (obj)(uint16_t)(bank5[off] | ((uint16_t)bank5[off + 1u] << 8));
}

static void positive(void) {
    vm_boot_fastpath_work work;
    obj name, function, string, keep;
    uint8_t status;
    reset_fixture();
    vm_boot_fastpath_prepare(&work);
    status = vm_boot_fastpath_phase_verify(&work);
    if (status != VM_BOOT_FASTPATH_OK) {
        uint16_t mismatch = 0;
        while (mismatch < sizeof pristine_image
               && bank5[mismatch] == pristine_image[mismatch]) mismatch++;
        fprintf(stderr, "vm-boot-fastpath: verify status=%u dirs=%u oom=%u crc=%04x\n",
                (unsigned)status, (unsigned)vm_dir_count(), (unsigned)mem_oom,
                fixture_crc());
        if (mismatch < sizeof pristine_image)
            fprintf(stderr, "vm-boot-fastpath: first mutation=%u %02x/%02x\n",
                    (unsigned)mismatch, bank5[mismatch], pristine_image[mismatch]);
    }
    expect(status == VM_BOOT_FASTPATH_OK,
           "full-image CRC");
    expect(work.crc_passes == 1 && work.crc_bytes == sizeof pristine_image,
           "single CRC pass accounting");
    expect(work.fix_literals == 1 && work.string_literals == 1
           && work.symbol_literals == 0,
           "call-0 literal classes");
    expect(patched_obj(2) == MKFIX(42), "call-0 fixnum patch");
    string = patched_obj(6);
    expect(IS_PTR(string) && cell_type(string) == T_STR,
           "call-0 string patch");
    keep = sym_value(intern("%lit-keep"));
    expect(IS_PTR(keep) && cell_type(keep) == T_CONS
           && cell_a(keep) == string,
           "call-0 string rooted before return");
    expect(vm_boot_fastpath_phase_patches(&work) == VM_BOOT_FASTPATH_OK,
           "call-1 symbol patches");
    expect(work.symbol_literals == 1
           && patched_obj(4) == intern("foo"),
           "call-1 symbol class");
    expect(vm_boot_fastpath_phase_entries(&work) == VM_BOOT_FASTPATH_OK,
           "batched entries and freeze");
    expect(work.finished && work.overlay_calls == VM_BOOT_FASTPATH_OVERLAY_CALLS,
           "three-call terminal state");
    expect(vm_dir_count() == 1, "directory publication");
    name = intern("bootfn");
    function = sym_function(name);
    expect(IS_BCODE(function) && BCODE_IDX(function) == 0,
           "published bytecode function");
}

static void corruption(void) {
    vm_boot_fastpath_work work;
    uint8_t before[LISP65_BOOT_STDLIB_IMAGE_BYTES];
    uint16_t symbols_before;
    reset_fixture();
    bank5[17] ^= 1;
    memcpy(before, bank5, sizeof before);
    symbols_before = sym_count();
    vm_boot_fastpath_prepare(&work);
    expect(vm_boot_fastpath_phase_verify(&work) == VM_BOOT_FASTPATH_ERR_CRC,
           "corrupted full image rejected");
    expect(work.finished && vm_dir_count() == 0 && ext_writes == 0
           && sym_count() == symbols_before
           && memcmp(before, bank5, sizeof before) == 0,
           "CRC failure precedes every mutation");
}

static void protocol(void) {
    vm_boot_fastpath_work work;
    reset_fixture();
    vm_boot_fastpath_prepare(&work);
    expect(vm_boot_fastpath_phase_entries(&work) == VM_BOOT_FASTPATH_ERR_PHASE,
           "out-of-order phase rejected");
    vm_boot_fastpath_prepare(&work);
    work.cookie ^= 1;
    expect(vm_boot_fastpath_phase_verify(&work) == VM_BOOT_FASTPATH_ERR_COOKIE,
           "cookie mismatch rejected");
}

static void profile_mismatch(void) {
    vm_boot_fastpath_work work;
    unsigned writes_before;
    uint16_t symbols_before;
    reset_fixture();
    vm_boot_fastpath_prepare(&work);
    expect(vm_boot_fastpath_phase_verify(&work) == VM_BOOT_FASTPATH_OK,
           "profile test call-0");
    work.fix_literals++;
    writes_before = ext_writes;
    symbols_before = sym_count();
    expect(vm_boot_fastpath_phase_patches(&work) == VM_BOOT_FASTPATH_ERR_PROFILE,
           "profile counter mismatch rejected");
    expect(ext_writes == writes_before && sym_count() == symbols_before,
           "profile mismatch fails before call-1 mutation");
}

static void transport_status_mapping(void) {
    static const vm_runtime_overlay_status catalog_statuses[] = {
        VM_RUNTIME_OVERLAY_ERR_MAGIC,
        VM_RUNTIME_OVERLAY_ERR_VERSION,
        VM_RUNTIME_OVERLAY_ERR_HEADER,
        VM_RUNTIME_OVERLAY_ERR_PROFILE,
        VM_RUNTIME_OVERLAY_ERR_DIRECTORY,
        VM_RUNTIME_OVERLAY_ERR_SLOT,
        VM_RUNTIME_OVERLAY_ERR_VMA,
        VM_RUNTIME_OVERLAY_ERR_ENTRY,
        VM_RUNTIME_OVERLAY_ERR_LENGTH,
        VM_RUNTIME_OVERLAY_ERR_ABI,
        VM_RUNTIME_OVERLAY_ERR_CRC
    };
    static const vm_runtime_overlay_status state_statuses[] = {
        VM_RUNTIME_OVERLAY_ERR_ARGUMENT,
        VM_RUNTIME_OVERLAY_ERR_LATCHED,
        VM_RUNTIME_OVERLAY_ERR_BUSY,
        VM_RUNTIME_OVERLAY_ERR_STACK,
        VM_RUNTIME_OVERLAY_ERR_WIPE,
        VM_RUNTIME_OVERLAY_ERR_ABORTED
    };
    unsigned i;

    expect(vm_boot_fastpath_transport_status(VM_RUNTIME_OVERLAY_OK) ==
           VM_BOOT_FASTPATH_OK, "transport success mapping");
    for (i = 0; i < sizeof catalog_statuses / sizeof catalog_statuses[0]; i++)
        expect(vm_boot_fastpath_transport_status(catalog_statuses[i]) ==
               VM_BOOT_FASTPATH_ERR_CATALOG, "catalog transport mapping");
    for (i = 0; i < sizeof state_statuses / sizeof state_statuses[0]; i++)
        expect(vm_boot_fastpath_transport_status(state_statuses[i]) ==
               VM_BOOT_FASTPATH_ERR_STATE, "internal transport mapping");
}

int main(void) {
    positive();
    corruption();
    protocol();
    profile_mismatch();
    transport_status_mapping();
    if (failures) return 1;
    puts("vm-boot-fastpath: PASS crc-once+flat-3-call+protocol");
    return 0;
}
