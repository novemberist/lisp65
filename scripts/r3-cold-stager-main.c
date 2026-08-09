/* lisp65 R3 autonomous cold-start stager.
 *
 * AUTOBOOT.C65 runs before the Workbench and owns no byte in its final Bank-0
 * image.  It reads a fixed binary descriptor from the mounted L65SYS,65 D81,
 * proves that descriptor against the build id compiled into this artifact,
 * verifies every product-medium member, validates or fully restages Bank 5,
 * the runtime-overlay catalog and the 1.1 library shelf, re-verifies all three
 * destinations, stages the exact product
 * PRG in Bank 4, and only then hands off through the $1800 trampoline.
 *
 * F011 timing remains hardware-only evidence.  This source is nevertheless
 * the real product implementation: the pre-G3 receipt compiles and inspects
 * it but does not execute it in xmega65.
 */
#include <stdint.h>
#include <mega65.h>

#include "r3-cold-stager-contract.h"

#ifndef R3_EXPECTED_PRODUCT_BUILD_ID
#error "R3_EXPECTED_PRODUCT_BUILD_ID must bind the complete product medium"
#endif

#define R3_DESCRIPTOR_NAME "boot.id"
#define R3_DESCRIPTOR_HEADER_BYTES 16u
#define R3_DESCRIPTOR_RECORD_BYTES 32u
#if defined(LISP65_C2_LITE_MEDIA_STAGER) || defined(LISP65_SHIP_MEDIA_STAGER)
#define LISP65_VERIFIED_MEDIA_STAGER 1
#endif

#ifdef LISP65_C2_LITE_MEDIA_STAGER
#define R3_DESCRIPTOR_BYTES 432u
#define R3_DESCRIPTOR_RECORDS 13u
#define R3_DESCRIPTOR_VERSION 2u
#define R3_ROLE_FIRST_STAGE 1u
#define R3_ROLE_LAST_STAGE 8u
#define R3_ROLE_PRODUCT 9u
#define R3_ROLE_LAST 13u
#define R3_ROLE_MASK 0x1fffu
#elif defined(LISP65_SHIP_MEDIA_STAGER)
#define R3_DESCRIPTOR_BYTES 80u
#define R3_DESCRIPTOR_RECORDS 2u
#define R3_DESCRIPTOR_VERSION 3u
#define R3_ROLE_FIRST_STAGE 1u
#define R3_ROLE_LAST_STAGE 1u
#define R3_ROLE_PRODUCT 2u
#define R3_ROLE_LAST 2u
#define R3_ROLE_MASK 0x0003u
#else
#define R3_DESCRIPTOR_BYTES 272u
#define R3_DESCRIPTOR_RECORDS 8u
#define R3_DESCRIPTOR_VERSION 1u
#define R3_ROLE_FIRST_STAGE 1u
#define R3_ROLE_LAST_STAGE 8u
#define R3_ROLE_LAST 8u
#define R3_ROLE_MASK 0x00ffu
#endif
#define R3_RESTAGE_LIMIT 2u
#define R3_LOGICAL_SECTOR_PAYLOAD 254ul
#define R3_MAX_MEDIA_BYTES 819200ul
#define R3_PRODUCT_STAGE 0x00040000ul
#define R3_BANK5_ADDR 0x00050000ul
#define R3_ATTIC_ADDR 0x08000000ul
#define R3_ATTIC_SHELF_ADDR 0x08100000ul
#define R3_NORMAL_F018B_LIMIT 0x00100000ul
#define R3_PHYSICAL_ADDRESS_LIMIT 0x10000000ul

#ifndef LISP65_VERIFIED_MEDIA_STAGER
#define R3_ROLE_BANK5 1u
#define R3_ROLE_ATTIC 2u
#define R3_ROLE_PRODUCT 3u
#define R3_ROLE_PROFILE 4u
#define R3_ROLE_IDE 5u
#define R3_ROLE_IDEX 6u
#define R3_ROLE_M65D 7u
#define R3_ROLE_SHELF 8u
#endif

#define R3_FLAG_STAGE 0x01u
#define R3_FLAG_PRG 0x02u
#define R3_FLAG_PROFILE_ID_AT_12 0x04u
#define R3_DMA_CHAIN 0x04u

#define R3_SCREEN ((volatile uint8_t *)0x0800)
#define R3_BORDER (*(volatile uint8_t *)0xd020)

extern const uint8_t r3_chain_begin[];
extern const uint8_t r3_chain_end[];
#ifdef LISP65_C2_LITE_MEDIA_STAGER
extern void r3_rom_write_enable(void);
#endif

static uint8_t descriptor[R3_DESCRIPTOR_BYTES];
static uint8_t sector_payload[254];
static uint8_t verify_buffer[256];
#ifdef LISP65_VERIFIED_MEDIA_STAGER
static volatile uint8_t c2_target_readback[254];
#endif
#ifdef LISP65_G5_IO_TRIGGER_PROBE
/* Non-promotable G5 attribution only.  The first submission is byte-for-byte
 * the current cold-stager path.  After its timeout, the same immutable job is
 * submitted once more with only an immediately preceding MEGA65-I/O knock.
 * JTAG reads these named BSS witnesses while the probe holds. */
__attribute__((used, section(".bss.g5_trigger_probe")))
static volatile uint8_t g5_trigger_probe[32];
__attribute__((used, aligned(256)))
static volatile uint8_t g5_map_snapshot[256];
static uint8_t g5_trigger_attempts;
#endif

/* G3 executes this source through a deterministic media boundary.  The
 * product build never defines R3_G3_TRACE: its F011 path and bytes therefore
 * remain the release artifact.  The trace build replaces only the domains
 * that the R3 contract explicitly assigns to hardware (F011/SD/DMA timing),
 * while retaining descriptor validation, restage control, re-verification
 * ordering and product-selection logic from this translation unit. */
#ifdef R3_G3_TRACE
static uint8_t r3_g3_memory_valid;
static uint8_t r3_g3_disk_valid;
static uint8_t r3_g3_stage_mask;
static uint8_t r3_g3_stage_order[3];
static uint8_t r3_g3_stage_count;
static uint8_t r3_g3_media_checks;
static uint8_t r3_g3_product_selected;
static uint8_t r3_g3_handoffs;
#endif

struct r3_edma_job {
    uint8_t options[7];
    uint8_t end_option;
    uint8_t list[12];
};

__attribute__((used)) static struct r3_edma_job edma_job;
#ifdef LISP65_VERIFIED_MEDIA_STAGER
struct r3_f018b_job {
    uint8_t list[12];
};

/* One immutable two-job submission owns the media write and its ordered
 * target readback.  This is deliberately the same normal F018B/D700
 * transport used by the hardware-proven product Bank-0 -> Bank-2 writer.
 * G5 must not grow a private Enhanced-DMA interpretation of that edge. */
__attribute__((used)) static struct r3_f018b_job c2_stage_jobs[2];
/* Attic needs the upper-address option tokens of Enhanced F018B.  The first
 * immutable pair performs WRITE -> ordered target READ.  A distinct immutable
 * descriptor performs later target-read retries, so no descriptor that DMAgic
 * may still consume is ever rewritten in place. */
__attribute__((used)) static struct r3_edma_job c2_attic_stage_jobs[2];
__attribute__((used)) static struct r3_edma_job c2_attic_retry_job;
#endif

static uint16_t rd16(const uint8_t *p) {
    return (uint16_t)p[0] | ((uint16_t)p[1] << 8);
}

static uint32_t rd32(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static void wr16(volatile uint8_t *p, uint16_t value) {
    p[0] = (uint8_t)value;
    p[1] = (uint8_t)(value >> 8);
}

static void io_enable(void) {
    *(volatile uint8_t *)0xd02f = 0x47;
    *(volatile uint8_t *)0xd02f = 0x53;
    *(volatile uint8_t *)0xd054 |= 0x40;
}

#ifdef LISP65_G5_IO_TRIGGER_PROBE
static void g5_probe_delay(void) {
    volatile uint16_t fuel = 4096u;
    while (fuel--) __asm__ volatile("nop");
}

static void g5_capture_io(uint8_t base) {
    g5_trigger_probe[base + 0u] = *(volatile uint8_t *)0xd012;
    g5_trigger_probe[base + 1u] = *(volatile uint8_t *)0xd031;
    g5_trigger_probe[base + 2u] = *(volatile uint8_t *)0xd054;
    g5_trigger_probe[base + 3u] = *(volatile uint8_t *)0xd02f;
    g5_trigger_probe[base + 4u] = *(volatile uint8_t *)0xd700;
    g5_trigger_probe[base + 5u] = *(volatile uint8_t *)0xd703;
    g5_probe_delay();
    g5_trigger_probe[base + 6u] = *(volatile uint8_t *)0xd012;
    g5_trigger_probe[base + 7u] = *(volatile uint8_t *)0xd031;
}

static void g5_capture_map(void) {
    __asm__ volatile(
        "ldy #mos16hi(g5_map_snapshot)\n\t"
        "ldx #0\n\t"
        "lda #$74\n\t"
        "sta $d640\n\t"
        "clv\n\t"
        ::: "a", "x", "y", "memory");
}

__attribute__((noreturn))
static void g5_probe_hold(uint8_t second_submission_matched) {
    static const char pass[] = "G5 IO KNOCK A/B PASS";
    static const char fail[] = "G5 IO KNOCK A/B FAIL";
    const char *message = second_submission_matched ? pass : fail;
    uint8_t index;
    g5_trigger_probe[18] = second_submission_matched;
    g5_trigger_probe[19] = g5_trigger_attempts;
    g5_capture_map();
    R3_BORDER = second_submission_matched ? 5u : 2u;
    for (index = 0; index < 21u; index++)
        R3_SCREEN[index] = (uint8_t)message[index];
    for (;;) __asm__ volatile("nop");
}
#endif

#include "../src/f011_context.h"

static void edma_copy(uint32_t src, uint32_t dst, uint16_t count) {
    edma_job.options[0] = ENABLE_F018B_OPT;
    edma_job.options[1] = SRC_ADDR_BITS_OPT;
    edma_job.options[2] = (uint8_t)(src >> 20);
    edma_job.options[3] = DST_ADDR_BITS_OPT;
    edma_job.options[4] = (uint8_t)(dst >> 20);
    edma_job.options[5] = DST_SKIP_RATE_OPT;
    edma_job.options[6] = 1;
    edma_job.end_option = 0;
    edma_job.list[0] = DMA_COPY_CMD;
    edma_job.list[1] = (uint8_t)count;
    edma_job.list[2] = (uint8_t)(count >> 8);
    edma_job.list[3] = (uint8_t)src;
    edma_job.list[4] = (uint8_t)(src >> 8);
    edma_job.list[5] = (uint8_t)((src >> 16) & 0x0f);
    edma_job.list[6] = (uint8_t)dst;
    edma_job.list[7] = (uint8_t)(dst >> 8);
    edma_job.list[8] = (uint8_t)((dst >> 16) & 0x0f);
    edma_job.list[9] = 0;
    edma_job.list[10] = 0;
    edma_job.list[11] = 0;
    __asm__ volatile(
        "lda #1\n\t"
        "sta $d703\n\t"
        "lda #0\n\t"
        "sta $d702\n\t"
        "sta $d704\n\t"
        "lda #mos16hi(edma_job)\n\t"
        "sta $d701\n\t"
        "lda #mos16lo(edma_job)\n\t"
        "sta $d705\n\t"
        ::: "a", "memory");
}

#ifdef LISP65_VERIFIED_MEDIA_STAGER
static void c2_f018b_prepare(struct r3_f018b_job *job, uint32_t src,
                             uint32_t dst, uint16_t count, uint8_t command) {
    job->list[0] = command;
    job->list[1] = (uint8_t)count;
    job->list[2] = (uint8_t)(count >> 8);
    job->list[3] = (uint8_t)src;
    job->list[4] = (uint8_t)(src >> 8);
    job->list[5] = (uint8_t)((src >> 16) & 0x0f);
    job->list[6] = (uint8_t)dst;
    job->list[7] = (uint8_t)(dst >> 8);
    job->list[8] = (uint8_t)((dst >> 16) & 0x0f);
    job->list[9] = 0;
    job->list[10] = 0;
    job->list[11] = 0;
}

static void c2_edma_prepare(struct r3_edma_job *job, uint32_t src,
                            uint32_t dst, uint16_t count, uint8_t command) {
    job->options[0] = ENABLE_F018B_OPT;
    job->options[1] = SRC_ADDR_BITS_OPT;
    job->options[2] = (uint8_t)(src >> 20);
    job->options[3] = DST_ADDR_BITS_OPT;
    job->options[4] = (uint8_t)(dst >> 20);
    job->options[5] = DST_SKIP_RATE_OPT;
    job->options[6] = 1;
    job->end_option = 0;
    job->list[0] = command;
    job->list[1] = (uint8_t)count;
    job->list[2] = (uint8_t)(count >> 8);
    job->list[3] = (uint8_t)src;
    job->list[4] = (uint8_t)(src >> 8);
    job->list[5] = (uint8_t)((src >> 16) & 0x0f);
    job->list[6] = (uint8_t)dst;
    job->list[7] = (uint8_t)(dst >> 8);
    job->list[8] = (uint8_t)((dst >> 16) & 0x0f);
    job->list[9] = 0;
    job->list[10] = 0;
    job->list[11] = 0;
}

static void c2_chip_stage_copy_readback(uint32_t src, uint32_t dst,
                                        uint32_t readback, uint16_t count) {
    c2_f018b_prepare(&c2_stage_jobs[0], src, dst, count,
                     DMA_COPY_CMD | R3_DMA_CHAIN);
    c2_f018b_prepare(
        &c2_stage_jobs[1], dst, readback, count, DMA_COPY_CMD);
#ifdef LISP65_G5_IO_TRIGGER_PROBE
    if (g5_trigger_attempts < 2u)
        g5_capture_io((uint8_t)(g5_trigger_attempts * 8u));
    g5_trigger_attempts++;
#endif
    __asm__ volatile(
        "lda #1\n\t"
        "sta $d703\n\t"
        "lda #0\n\t"
        "sta $d702\n\t"
        "lda #mos16hi(c2_stage_jobs)\n\t"
        "sta $d701\n\t"
        "lda #mos16lo(c2_stage_jobs)\n\t"
        "sta $d700\n\t"
        ::: "a", "memory");
}

static void c2_attic_stage_copy_readback(
        uint32_t src, uint32_t dst, uint32_t readback, uint16_t count) {
    c2_edma_prepare(&c2_attic_stage_jobs[0], src, dst, count,
                    DMA_COPY_CMD | R3_DMA_CHAIN);
    c2_edma_prepare(
        &c2_attic_stage_jobs[1], dst, readback, count, DMA_COPY_CMD);
    c2_edma_prepare(
        &c2_attic_retry_job, dst, readback, count, DMA_COPY_CMD);
    __asm__ volatile(
        "lda #1\n\t"
        "sta $d703\n\t"
        "lda #0\n\t"
        "sta $d702\n\t"
        "sta $d704\n\t"
        "lda #mos16hi(c2_attic_stage_jobs)\n\t"
        "sta $d701\n\t"
        "lda #mos16lo(c2_attic_stage_jobs)\n\t"
        "sta $d705\n\t"
        ::: "a", "memory");
}

static void c2_attic_retry_readback(void) {
    __asm__ volatile(
        "lda #1\n\t"
        "sta $d703\n\t"
        "lda #0\n\t"
        "sta $d702\n\t"
        "sta $d704\n\t"
        "lda #mos16hi(c2_attic_retry_job)\n\t"
        "sta $d701\n\t"
        "lda #mos16lo(c2_attic_retry_job)\n\t"
        "sta $d705\n\t"
        ::: "a", "memory");
}

enum c2_stage_domain {
    C2_STAGE_INVALID = 0,
    C2_STAGE_CHIP = 1,
    C2_STAGE_ATTIC = 2
};

static uint8_t c2_stage_address_domain(uint32_t address, uint32_t length) {
    if (!length) return C2_STAGE_INVALID;
    if (address < R3_NORMAL_F018B_LIMIT &&
        length <= R3_NORMAL_F018B_LIMIT - address)
        return C2_STAGE_CHIP;
    if (address >= R3_ATTIC_ADDR &&
        address < R3_PHYSICAL_ADDRESS_LIMIT &&
        length <= R3_PHYSICAL_ADDRESS_LIMIT - address)
        return C2_STAGE_ATTIC;
    return C2_STAGE_INVALID;
}

static uint8_t c2_stage_record_domain_valid(
        uint8_t role, const uint8_t *record) {
#ifdef LISP65_SHIP_MEDIA_STAGER
    uint8_t expected = C2_STAGE_CHIP;
#else
    uint8_t expected = role <= 3u ? C2_STAGE_CHIP : C2_STAGE_ATTIC;
#endif
    return record && record[0] == role &&
           c2_stage_address_domain(
               rd32(record + 4), rd32(record + 8)) == expected;
}
#endif

/* Read one logical 1581 sector and expose its half in the $DE00 window. */
static uint8_t f011_read(uint8_t track, uint8_t sector, uint16_t *window_off) {
    uint8_t block;
    uint8_t side;
    uint8_t fsector;
    uint16_t fuel;
    if (track < 1 || track > 80 || sector > 39) return 0;
    block = (uint8_t)(sector >> 1);
    side = block >= 10 ? 1 : 0;
    fsector = (uint8_t)((block >= 10 ? block - 10 : block) + 1);
    io_enable();
    lisp65_f011_take_context();
    *(volatile uint8_t *)0xd081 = 0x20;
    for (fuel = 0; fuel < 20000; fuel++) { }
    *(volatile uint8_t *)0xd084 = (uint8_t)(track - 1);
    *(volatile uint8_t *)0xd085 = fsector;
    *(volatile uint8_t *)0xd086 = side;
    *(volatile uint8_t *)0xd081 = 0x40;
    for (fuel = 60000; fuel && (*(volatile uint8_t *)0xd082 & 0x80); fuel--) { }
    if (!fuel) return 0;
    lisp65_f011_map_buffer();
    *window_off = (uint16_t)(sector & 1u) << 8;
    return 1;
}

static uint8_t fold(uint8_t value) {
    if (value > 127) value = (uint8_t)(value - 128);
    if (value >= 'a' && value <= 'z') value = (uint8_t)(value - 32);
    return value;
}

static uint8_t name_matches(const volatile uint8_t *entry, const char *name) {
    uint8_t index;
    uint8_t ended = 0;
    for (index = 0; index < 16; index++) {
        uint8_t expected;
        if (!ended && !name[index]) ended = 1;
        expected = ended ? ' ' : fold((uint8_t)name[index]);
        if (fold(entry[5u + index]) != expected) return 0;
    }
    return 1;
}

static uint8_t product_media_identity(void) {
#ifdef R3_G3_TRACE
    r3_g3_media_checks++;
    return r3_g3_disk_valid;
#else
    uint16_t off;
    volatile uint8_t *p;
#ifdef LISP65_SHIP_MEDIA_STAGER
    static const char name[] = "L65APP";
#else
    static const char name[] = "L65SYS";
#endif
    uint8_t index;
    uint8_t ok = 1;
    if (!f011_read(40, 0, &off)) return 0;
    p = (volatile uint8_t *)0xde00 + off;
    for (index = 0; index < 16; index++) {
        uint8_t expected = index < 6 ? (uint8_t)name[index] : (uint8_t)' ';
        if (fold(p[4u + index]) != expected) ok = 0;
    }
    if (fold(p[22]) != '6' || fold(p[23]) != '5') ok = 0;
    lisp65_f011_unmap_buffer();
    return ok;
#endif
}

static uint8_t find_file(const char *name, uint8_t *start_track, uint8_t *start_sector) {
    uint8_t track = 40;
    uint8_t sector = 0;
    uint8_t fuel = 64;
    while (fuel--) {
        uint16_t off;
        uint8_t entry;
        uint8_t next_track;
        uint8_t next_sector;
        volatile uint8_t *p;
        if (!f011_read(track, sector, &off)) return 0;
        p = (volatile uint8_t *)0xde00 + off;
        for (entry = (track == 40 && sector == 0) ? 1 : 0; entry < 8; entry++) {
            volatile uint8_t *record = p + (uint16_t)entry * 32u;
            if ((record[2] & 7u) && name_matches(record, name)) {
                *start_track = record[3];
                *start_sector = record[4];
                lisp65_f011_unmap_buffer();
                return 1;
            }
        }
        next_track = p[0];
        next_sector = p[1];
        lisp65_f011_unmap_buffer();
        if (next_track != 40 || next_sector >= 40 || next_sector == sector) return 0;
        sector = next_sector;
    }
    return 0;
}

static uint32_t crc32_step(uint32_t crc, uint8_t value) {
    uint8_t bit;
    crc ^= value;
    for (bit = 0; bit < 8; bit++)
        crc = (crc >> 1) ^ (0xedb88320ul & (uint32_t)-(int32_t)(crc & 1u));
    return crc;
}

static uint8_t scan_file(const char *name, uint32_t destination, uint8_t stage,
                         uint32_t expected_length, uint32_t expected_crc) {
    uint8_t track;
    uint8_t sector;
    uint16_t fuel;
    uint32_t length = 0;
    uint32_t crc = 0xfffffffful;
#ifdef LISP65_VERIFIED_MEDIA_STAGER
    uint8_t stage_domain = stage
        ? c2_stage_address_domain(destination, expected_length)
        : C2_STAGE_INVALID;
#endif
    if (!expected_length || expected_length > R3_MAX_MEDIA_BYTES) return 0;
#ifdef LISP65_VERIFIED_MEDIA_STAGER
    if (stage && stage_domain == C2_STAGE_INVALID) return 0;
#endif
    fuel = (uint16_t)((expected_length + R3_LOGICAL_SECTOR_PAYLOAD - 1ul) /
                      R3_LOGICAL_SECTOR_PAYLOAD);
    if (!find_file(name, &track, &sector)) return 0;
    while (track && fuel--) {
        uint16_t off;
        uint16_t count;
        uint16_t index;
        uint8_t next_track;
        uint8_t next_sector;
        volatile uint8_t *p;
        if (!f011_read(track, sector, &off)) return 0;
        p = (volatile uint8_t *)0xde00 + off;
        next_track = p[0];
        next_sector = p[1];
        if (!next_track && !next_sector) {
            lisp65_f011_unmap_buffer();
            return 0;
        }
        count = next_track ? 254u : (uint16_t)(next_sector - 1u);
        if (length + count > expected_length) {
            lisp65_f011_unmap_buffer();
            return 0;
        }
        for (index = 0; index < count; index++) {
            sector_payload[index] = p[2u + index];
            crc = crc32_step(crc, sector_payload[index]);
        }
        lisp65_f011_unmap_buffer();
        if (stage && count) {
#ifdef LISP65_VERIFIED_MEDIA_STAGER
            uint16_t poll;
            uint8_t wraps = 0;
            uint8_t raster = *(volatile uint8_t *)0xd012;
            uint8_t match = 0;
            for (poll = 0; poll < count; poll++)
                c2_target_readback[poll] = 0xa5u;
            if (stage_domain == C2_STAGE_CHIP)
                c2_chip_stage_copy_readback(
                    (uint32_t)(uintptr_t)sector_payload,
                    destination + length,
                    (uint32_t)(uintptr_t)c2_target_readback, count);
            else
                c2_attic_stage_copy_readback(
                    (uint32_t)(uintptr_t)sector_payload,
                    destination + length,
                    (uint32_t)(uintptr_t)c2_target_readback, count);
            while (wraps < 192u) {
                uint8_t now;
                match = 1;
                for (poll = 0; poll < count; poll++) {
                    if (c2_target_readback[poll] != sector_payload[poll]) {
                        match = 0;
                        break;
                    }
                }
                if (match) break;
                if (stage_domain == C2_STAGE_ATTIC) {
                    /* Attic visibility is not inferred from DMA submission.
                     * Re-read the real 28-bit target with an immutable
                     * Enhanced descriptor, then allow one complete raster
                     * frame before judging the newly returned bytes. */
                    c2_attic_retry_readback();
                    do {
                        now = *(volatile uint8_t *)0xd012;
                        if (now < raster) {
                            wraps++;
                            break;
                        }
                        raster = now;
                    } while (wraps < 192u);
                    raster = now;
                    continue;
                }
                now = *(volatile uint8_t *)0xd012;
                if (now < raster) wraps++;
                raster = now;
            }
#ifdef LISP65_G5_IO_TRIGGER_PROBE
            if (!match && g5_trigger_attempts == 1u) {
                g5_trigger_probe[16] = wraps;
                io_enable();
                for (poll = 0; poll < count; poll++)
                    c2_target_readback[poll] = 0xa5u;
                wraps = 0;
                raster = *(volatile uint8_t *)0xd012;
                c2_chip_stage_copy_readback(
                    (uint32_t)(uintptr_t)sector_payload,
                    destination + length,
                    (uint32_t)(uintptr_t)c2_target_readback, count);
                while (wraps < 192u) {
                    uint8_t now;
                    match = 1;
                    for (poll = 0; poll < count; poll++) {
                        if (c2_target_readback[poll]
                            != sector_payload[poll]) {
                            match = 0;
                            break;
                        }
                    }
                    if (match) break;
                    now = *(volatile uint8_t *)0xd012;
                    if (now < raster) wraps++;
                    raster = now;
                }
                g5_trigger_probe[17] = wraps;
                g5_probe_hold(match);
            }
#endif
            if (!match) return 0;
#else
            edma_copy((uint32_t)(uintptr_t)sector_payload,
                      destination + length, count);
#endif
        }
        length += count;
        if (!next_track) {
            track = 0;
            break;
        }
        if (next_track < 1 || next_track > 80 || next_sector > 39 ||
            (next_track == track && next_sector == sector)) return 0;
        track = next_track;
        sector = next_sector;
    }
    if (track) return 0;
    return length == expected_length && (crc ^ 0xfffffffful) == expected_crc;
}

#ifndef LISP65_VERIFIED_MEDIA_STAGER
static uint32_t memory_crc32(uint32_t address, uint32_t length) {
    uint32_t crc = 0xfffffffful;
    while (length) {
        uint16_t count = length > sizeof verify_buffer ? sizeof verify_buffer : (uint16_t)length;
        uint16_t index;
        edma_copy(address, (uint32_t)(uintptr_t)verify_buffer, count);
        for (index = 0; index < count; index++) crc = crc32_step(crc, verify_buffer[index]);
        address += count;
        length -= count;
    }
    return crc ^ 0xfffffffful;
}

static uint32_t memory_u32(uint32_t address) {
    edma_copy(address, (uint32_t)(uintptr_t)verify_buffer, 4);
    return rd32(verify_buffer);
}
#endif

static const uint8_t *record_at(uint8_t index) {
    return descriptor + R3_DESCRIPTOR_HEADER_BYTES +
           (uint16_t)index * R3_DESCRIPTOR_RECORD_BYTES;
}

static void record_name(const uint8_t *record, char *out) {
    uint8_t length = record[2];
    uint8_t index;
    for (index = 0; index < length; index++) out[index] = (char)record[16u + index];
    out[length] = 0;
}

static const uint8_t *find_role(uint8_t role) {
    uint8_t index;
    for (index = 0; index < R3_DESCRIPTOR_RECORDS; index++)
        if (record_at(index)[0] == role) return record_at(index);
    return 0;
}

static uint8_t load_descriptor(void) {
    uint8_t track;
    uint8_t sector;
    uint8_t fuel = 4;
    uint16_t used = 0;
    if (!find_file(R3_DESCRIPTOR_NAME, &track, &sector)) return 0;
    while (track && fuel--) {
        uint16_t off;
        uint16_t count;
        uint16_t index;
        uint8_t next_track;
        uint8_t next_sector;
        volatile uint8_t *p;
        if (!f011_read(track, sector, &off)) return 0;
        p = (volatile uint8_t *)0xde00 + off;
        next_track = p[0];
        next_sector = p[1];
        if ((!next_track && !next_sector) ||
            (next_track && (next_track > 80 || next_sector > 39 ||
                            (next_track == track && next_sector == sector)))) {
            lisp65_f011_unmap_buffer();
            return 0;
        }
        count = next_track ? 254u : (uint16_t)(next_sector - 1u);
        if ((uint16_t)(used + count) > R3_DESCRIPTOR_BYTES) {
            lisp65_f011_unmap_buffer();
            return 0;
        }
        for (index = 0; index < count; index++) descriptor[used++] = p[2u + index];
        lisp65_f011_unmap_buffer();
        if (!next_track) {
            track = 0;
            break;
        }
        track = next_track;
        sector = next_sector;
    }
    return !track && used == R3_DESCRIPTOR_BYTES;
}

static uint8_t validate_descriptor(void) {
    uint16_t byte_index;
    uint32_t records_crc = 0xfffffffful;
    uint16_t seen = 0;
    uint8_t index;
    if (descriptor[0] != 'L' || descriptor[1] != '6' ||
        descriptor[2] != '5' || descriptor[3] != 'B' ||
        descriptor[4] != R3_DESCRIPTOR_VERSION ||
        descriptor[5] != R3_DESCRIPTOR_HEADER_BYTES ||
        descriptor[6] != R3_DESCRIPTOR_RECORDS || descriptor[7] != R3_RESTAGE_LIMIT ||
        rd32(descriptor + 8) != (uint32_t)R3_EXPECTED_PRODUCT_BUILD_ID)
        return 0;
    for (byte_index = R3_DESCRIPTOR_HEADER_BYTES;
         byte_index < R3_DESCRIPTOR_BYTES; byte_index++)
        records_crc = crc32_step(records_crc, descriptor[byte_index]);
    if ((records_crc ^ 0xfffffffful) != (uint32_t)R3_EXPECTED_PRODUCT_BUILD_ID)
        return 0;
    for (index = 0; index < R3_DESCRIPTOR_RECORDS; index++) {
        const uint8_t *record = record_at(index);
        uint8_t role = record[0];
        uint8_t name_length = record[2];
        if (role < 1u || role > R3_ROLE_LAST ||
            (seen & (uint16_t)(1u << (role - 1u))) ||
            name_length < 1 || name_length > 16 || record[3] != 0 ||
            !rd32(record + 8)) return 0;
        seen |= (uint16_t)(1u << (role - 1u));
    }
    return seen == R3_ROLE_MASK;
}

#ifndef LISP65_VERIFIED_MEDIA_STAGER
static uint8_t memory_record_valid(const uint8_t *record,
                                   uint32_t profile_build_id) {
#ifdef R3_G3_TRACE
    uint8_t role = record[0];
    (void)profile_build_id;
    if (role != R3_ROLE_BANK5 && role != R3_ROLE_ATTIC &&
        role != R3_ROLE_SHELF) return 0;
    if (!(record[1] & R3_FLAG_STAGE)) return 0;
    return r3_g3_memory_valid;
#else
    uint32_t destination = rd32(record + 4);
    uint32_t length = rd32(record + 8);
    uint32_t expected_crc = rd32(record + 12);
    if (!(record[1] & R3_FLAG_STAGE) || memory_crc32(destination, length) != expected_crc)
        return 0;
    if ((record[1] & R3_FLAG_PROFILE_ID_AT_12) &&
        memory_u32(destination + 12u) != profile_build_id) return 0;
    return 1;
#endif
}
#endif

static uint8_t disk_record(const uint8_t *record, uint8_t stage) {
#ifdef R3_G3_TRACE
    uint8_t role = record[0];
    if (!r3_g3_disk_valid) return 0;
    if (!stage) return 1;
    if (role == R3_ROLE_BANK5 || role == R3_ROLE_ATTIC ||
        role == R3_ROLE_SHELF) {
        uint8_t bit = role == R3_ROLE_BANK5 ? 1u :
                      (role == R3_ROLE_ATTIC ? 2u : 4u);
        if (!(r3_g3_stage_mask & bit) && r3_g3_stage_count < 3u)
            r3_g3_stage_order[r3_g3_stage_count++] = role;
        r3_g3_stage_mask |= bit;
        if (r3_g3_stage_mask == 7u) r3_g3_memory_valid = 1;
        return 1;
    }
    if (role == R3_ROLE_PRODUCT) {
        r3_g3_product_selected = 1;
        return 1;
    }
    return 0;
#else
    char name[17];
    record_name(record, name);
    return scan_file(name, rd32(record + 4), stage, rd32(record + 8), rd32(record + 12));
#endif
}

#ifndef LISP65_VERIFIED_MEDIA_STAGER
static uint8_t staged_state_valid(uint32_t profile_build_id) {
    const uint8_t *bank5 = find_role(R3_ROLE_BANK5);
    const uint8_t *attic = find_role(R3_ROLE_ATTIC);
    const uint8_t *shelf = find_role(R3_ROLE_SHELF);
    return bank5 && attic && shelf &&
           memory_record_valid(bank5, profile_build_id) &&
           memory_record_valid(attic, profile_build_id) &&
           memory_record_valid(shelf, profile_build_id);
}
#endif

static uint8_t restage_and_reverify(uint32_t profile_build_id) {
#ifdef LISP65_VERIFIED_MEDIA_STAGER
    uint8_t attempt;
    uint8_t role;
    (void)profile_build_id;
    for (attempt = 0; attempt < R3_RESTAGE_LIMIT; attempt++) {
        uint8_t ok = product_media_identity();
        for (role = R3_ROLE_FIRST_STAGE;
             ok && role <= R3_ROLE_LAST_STAGE; role++) {
            const uint8_t *record = find_role(role);
            ok = c2_stage_record_domain_valid(role, record) &&
                 (record[1] & R3_FLAG_STAGE) &&
                 disk_record(record, 1);
        }
        if (ok) return 1;
    }
    return 0;
#else
    uint8_t attempt;
    const uint8_t *bank5 = find_role(R3_ROLE_BANK5);
    const uint8_t *attic = find_role(R3_ROLE_ATTIC);
    const uint8_t *shelf = find_role(R3_ROLE_SHELF);
    if (!bank5 || !attic || !shelf) return 0;
    for (attempt = 0; attempt < R3_RESTAGE_LIMIT; attempt++) {
        if (product_media_identity() && disk_record(bank5, 1) &&
            disk_record(attic, 1) && disk_record(shelf, 1) &&
            staged_state_valid(profile_build_id)) return 1;
    }
    return 0;
#endif
}

static void prepare_chain(const uint8_t *product) {
#ifdef R3_G3_TRACE
    if (product && product[0] == R3_ROLE_PRODUCT &&
        rd32(product + 4) == R3_PRODUCT_STAGE &&
        (product[1] & R3_FLAG_PRG) && r3_g3_product_selected)
        r3_g3_handoffs++;
#else
    uint16_t chain_size = (uint16_t)(r3_chain_end - r3_chain_begin);
    uint16_t index;
    uint32_t file_length = rd32(product + 8);
    volatile uint8_t *chain = (volatile uint8_t *)R3_CHAIN_CODE_ADDR;
    volatile uint8_t *job = (volatile uint8_t *)R3_CHAIN_JOB_ADDR;
    volatile uint8_t *state = (volatile uint8_t *)R3_CHAIN_STATE_ADDR;
    edma_copy(R3_PRODUCT_STAGE, (uint32_t)(uintptr_t)verify_buffer, 2);
    if (rd16(verify_buffer) != R3_PRODUCT_LOAD ||
        chain_size > R3_CHAIN_JOB_ADDR - R3_CHAIN_CODE_ADDR ||
        file_length < 3u)
        return;
    for (index = 0; index < chain_size; index++) chain[index] = r3_chain_begin[index];
    /* The relocated trampoline outlives the C stager.  Bind it to the
     * manifest CRC and exact payload length before the product copy begins;
     * it will recompute that CRC over the CPU-visible destination. */
    state[0] = product[12];
    state[1] = product[13];
    state[2] = product[14];
    state[3] = product[15];
    wr16(state + 4, (uint16_t)(file_length - 2u));
    /* Job 2 publishes $a5 only after the Bank-4 -> Bank-0 copy has completed.
     * DMAgic job submission is not a CPU-stall boundary on the acceptance
     * device, so the relocated trampoline waits on this memory witness before
     * entering the freshly copied product. */
    job[0] = DMA_COPY_CMD | R3_DMA_CHAIN;
    wr16(job + 1, (uint16_t)(file_length - 2u));
    job[3] = 2;
    job[4] = 0;
    job[5] = 4;
    job[6] = (uint8_t)R3_PRODUCT_LOAD;
    job[7] = (uint8_t)(R3_PRODUCT_LOAD >> 8);
    job[8] = 0;
    job[9] = 0;
    job[10] = 0;
    job[11] = 0;
    job[12] = DMA_COPY_CMD;
    wr16(job + 13, 1u);
    job[15] = (uint8_t)(R3_CHAIN_JOB_ADDR + 25u);
    job[16] = (uint8_t)((R3_CHAIN_JOB_ADDR + 25u) >> 8);
    job[17] = 0;
    job[18] = (uint8_t)(R3_CHAIN_JOB_ADDR + 24u);
    job[19] = (uint8_t)((R3_CHAIN_JOB_ADDR + 24u) >> 8);
    job[20] = 0;
    job[21] = 0;
    job[22] = 0;
    job[23] = 0;
    job[24] = 0x5au;
    job[25] = 0xa5u;
    ((void (*)(void))(uintptr_t)R3_CHAIN_CODE_ADDR)();
#endif
}

static void show_disk_error(void) {
#ifdef LISP65_SHIP_MEDIA_STAGER
    static const char message[] = "L65APP DISK ERROR - CHECK MEDIA";
#else
    static const char message[] = "L65SYS DISK ERROR - CHECK MEDIA";
#endif
    uint8_t index;
    R3_BORDER = 2;
    for (index = 0; index < sizeof message - 1u && index < 40u; index++)
        R3_SCREEN[index] = (uint8_t)message[index];
    for (;;) __asm__ volatile("nop");
}

int main(void) {
    uint8_t index;
    uint32_t profile_build_id;
    const uint8_t *product;
    io_enable();
    if (!product_media_identity() || !load_descriptor() || !validate_descriptor())
        show_disk_error();
    profile_build_id = rd32(descriptor + 12);
#ifdef LISP65_VERIFIED_MEDIA_STAGER
    /* Bank 2 and Bank 3 are writable Chip RAM only after the idempotent
     * HYPPO memory-trap service has removed ROM backing-bank protection.
     * Re-establish the I/O personality immediately at this ownership
     * boundary, then enable writes before the first stage-role job. */
    io_enable();
#ifdef LISP65_C2_LITE_MEDIA_STAGER
    r3_rom_write_enable();
#endif
    if (!restage_and_reverify(profile_build_id))
#else
    if (!staged_state_valid(profile_build_id) &&
        !restage_and_reverify(profile_build_id))
#endif
        show_disk_error();
    for (index = 0; index < R3_DESCRIPTOR_RECORDS; index++) {
        const uint8_t *record = record_at(index);
#ifdef LISP65_VERIFIED_MEDIA_STAGER
        if (!(record[1] & R3_FLAG_STAGE) &&
            record[0] != R3_ROLE_PRODUCT &&
#else
        if (record[0] != R3_ROLE_BANK5 && record[0] != R3_ROLE_ATTIC &&
            record[0] != R3_ROLE_SHELF && record[0] != R3_ROLE_PRODUCT &&
#endif
            !disk_record(record, 0)) show_disk_error();
    }
    product = find_role(R3_ROLE_PRODUCT);
    if (!product || rd32(product + 4) != R3_PRODUCT_STAGE ||
        !(product[1] & R3_FLAG_PRG) || !disk_record(product, 1)
#ifndef LISP65_VERIFIED_MEDIA_STAGER
        || !staged_state_valid(profile_build_id)
#endif
        ) show_disk_error();
    prepare_chain(product);
    show_disk_error();
    return 1;
}
