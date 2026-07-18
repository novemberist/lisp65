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
#define R3_DESCRIPTOR_BYTES 272u
#define R3_DESCRIPTOR_HEADER_BYTES 16u
#define R3_DESCRIPTOR_RECORD_BYTES 32u
#define R3_DESCRIPTOR_RECORDS 8u
#define R3_RESTAGE_LIMIT 2u
#define R3_LOGICAL_SECTOR_PAYLOAD 254ul
#define R3_MAX_MEDIA_BYTES 819200ul
#define R3_PRODUCT_STAGE 0x00040000ul
#define R3_BANK5_ADDR 0x00050000ul
#define R3_ATTIC_ADDR 0x08000000ul
#define R3_ATTIC_SHELF_ADDR 0x08100000ul

#define R3_ROLE_BANK5 1u
#define R3_ROLE_ATTIC 2u
#define R3_ROLE_PRODUCT 3u
#define R3_ROLE_PROFILE 4u
#define R3_ROLE_IDE 5u
#define R3_ROLE_IDEX 6u
#define R3_ROLE_M65D 7u
#define R3_ROLE_SHELF 8u

#define R3_FLAG_STAGE 0x01u
#define R3_FLAG_PRG 0x02u
#define R3_FLAG_PROFILE_ID_AT_12 0x04u

#define R3_SCREEN ((volatile uint8_t *)0x0800)
#define R3_BORDER (*(volatile uint8_t *)0xd020)

extern const uint8_t r3_chain_begin[];
extern const uint8_t r3_chain_end[];

static uint8_t descriptor[R3_DESCRIPTOR_BYTES];
static uint8_t sector_payload[254];
static uint8_t verify_buffer[256];

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
    static const char name[] = "L65SYS";
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
    if (!expected_length || expected_length > R3_MAX_MEDIA_BYTES) return 0;
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
        if (stage && count) edma_copy((uint32_t)(uintptr_t)sector_payload,
                                      destination + length, count);
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
    uint8_t seen = 0;
    uint8_t index;
    if (descriptor[0] != 'L' || descriptor[1] != '6' ||
        descriptor[2] != '5' || descriptor[3] != 'B' ||
        descriptor[4] != 1 || descriptor[5] != R3_DESCRIPTOR_HEADER_BYTES ||
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
        if (role < R3_ROLE_BANK5 || role > R3_ROLE_SHELF ||
            (seen & (uint8_t)(1u << (role - 1u))) ||
            name_length < 1 || name_length > 16 || record[3] != 0 ||
            !rd32(record + 8)) return 0;
        seen |= (uint8_t)(1u << (role - 1u));
    }
    return seen == 0xff;
}

static uint8_t memory_record_valid(const uint8_t *record, uint32_t profile_build_id) {
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

static uint8_t staged_state_valid(uint32_t profile_build_id) {
    const uint8_t *bank5 = find_role(R3_ROLE_BANK5);
    const uint8_t *attic = find_role(R3_ROLE_ATTIC);
    const uint8_t *shelf = find_role(R3_ROLE_SHELF);
    return bank5 && attic && shelf &&
           memory_record_valid(bank5, profile_build_id) &&
           memory_record_valid(attic, profile_build_id) &&
           memory_record_valid(shelf, profile_build_id);
}

static uint8_t restage_and_reverify(uint32_t profile_build_id) {
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
    edma_copy(R3_PRODUCT_STAGE, (uint32_t)(uintptr_t)verify_buffer, 2);
    if (rd16(verify_buffer) != R3_PRODUCT_LOAD || chain_size > 0x40u || file_length < 3u)
        return;
    for (index = 0; index < chain_size; index++) chain[index] = r3_chain_begin[index];
    job[0] = 0;
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
    ((void (*)(void))(uintptr_t)R3_CHAIN_CODE_ADDR)();
#endif
}

static void show_disk_error(void) {
    static const char message[] = "L65SYS DISK ERROR - CHECK MEDIA";
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
    if (!staged_state_valid(profile_build_id) && !restage_and_reverify(profile_build_id))
        show_disk_error();
    for (index = 0; index < R3_DESCRIPTOR_RECORDS; index++) {
        const uint8_t *record = record_at(index);
        if (record[0] != R3_ROLE_BANK5 && record[0] != R3_ROLE_ATTIC &&
            record[0] != R3_ROLE_SHELF && record[0] != R3_ROLE_PRODUCT &&
            !disk_record(record, 0)) show_disk_error();
    }
    product = find_role(R3_ROLE_PRODUCT);
    if (!product || rd32(product + 4) != R3_PRODUCT_STAGE ||
        !(product[1] & R3_FLAG_PRG) || !disk_record(product, 1) ||
        !staged_state_valid(profile_build_id)) show_disk_error();
    prepare_chain(product);
    show_disk_error();
    return 1;
}
