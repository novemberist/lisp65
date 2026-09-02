MEMORY {
    c2_runtime_load (!rwx) : ORIGIN = 0x010000, LENGTH = 0x020000
    c2_kernal_window (!rwx) : ORIGIN = 0xe000, LENGTH = 0x2000
    c2_kernal_window_load (!rwx) : ORIGIN = 0x040000, LENGTH = 0x002000
}

/* Workbench boot-code overlay prototype.
 *
 * The boot loader is linked immediately above the resident BSS/heap floor.
 * It is copied there from EXT RAM before its first call and becomes the shared
 * Bank-3 execution window as soon as vm_workbench_boot_overlay_entry() returns.
 * The entry owns only eval_init; profile-bound stdlib commit and freeze then run
 * as separately verified boot slices.  The
 * shipped prototype PRG is truncated at the resident file-end symbol; the raw
 * overlay is extracted from this same ELF.
 */
__lisp65_workbench_noinit_end = ADDR(.noinit) + SIZEOF(.noinit);
__lisp65_workbench_overlay_min_start = ALIGN(__lisp65_workbench_noinit_end + 1, 2);

__lisp65_workbench_required_boot_stack =
    DEFINED(__lisp65_workbench_required_boot_stack_param)
        ? __lisp65_workbench_required_boot_stack_param : 0x0200;
__lisp65_workbench_required_runtime_stack =
    DEFINED(__lisp65_workbench_required_runtime_stack_param)
        ? __lisp65_workbench_required_runtime_stack_param : 1450;
__lisp65_workbench_required_post_boot_reserve =
    DEFINED(__lisp65_workbench_required_post_boot_reserve_param)
        ? __lisp65_workbench_required_post_boot_reserve_param : 0x0400;
__lisp65_workbench_runtime_overlay_max_vma =
    DEFINED(__lisp65_workbench_runtime_overlay_max_vma_param)
        ? __lisp65_workbench_runtime_overlay_max_vma_param : 0xc356;
__lisp65_workbench_runtime_overlay_fixed_vma =
    DEFINED(__lisp65_workbench_runtime_overlay_vma_param)
        ? __lisp65_workbench_runtime_overlay_vma_param
        : __lisp65_workbench_runtime_overlay_max_vma;
__lisp65_workbench_runtime_transport_max_bytes = 1792;
__lisp65_error_overlay_max_bytes =
    DEFINED(__lisp65_error_overlay_max_bytes_param)
        ? __lisp65_error_overlay_max_bytes_param : 1320;
__lisp65_workbench_screen_base = 0x0800;
__lisp65_workbench_screen_columns = 80;
__lisp65_workbench_screen_rows = 50;
__lisp65_workbench_screen_cell_bytes = 1;
__lisp65_workbench_screen_limit =
    __lisp65_workbench_screen_base +
    (__lisp65_workbench_screen_columns * __lisp65_workbench_screen_rows *
     __lisp65_workbench_screen_cell_bytes);
__lisp65_resident_island_base = 0x1800;
__lisp65_resident_island_limit = 0x2000;
__lisp65_resident_island_payload_capacity = 2048;

SECTIONS {
    /* Boot and runtime slices are distinct load images with one intentional,
     * fixed execution VMA.  The resident-island seed, runtime-bank bootstrap,
     * and final product links have deliberately different LTO inputs; deriving
     * the VMA from their private .noinit stack shapes would make otherwise
     * identical SHA-bound slices embed different absolute addresses. */
    __lisp65_workbench_runtime_overlay_vma =
        __lisp65_workbench_runtime_overlay_fixed_vma;
    OVERLAY __lisp65_workbench_runtime_overlay_vma : NOCROSSREFS AT(ORIGIN(c2_runtime_load)) {
        .lisp65_workbench_overlay { KEEP(*(.lisp65_boot .lisp65_boot.*)) }
        .lisp65_rt_rtov_catalog { KEEP(*(.lisp65_rt_rtov_catalog)) }
        .lisp65_rt_rtov_record { KEEP(*(.lisp65_rt_rtov_record)) }
        .lisp65_rt_c2d_00 { KEEP(*(.lisp65_rt_c2d_00)) }
        .lisp65_rt_c2d_00b { KEEP(*(.lisp65_rt_c2d_00b)) }
        .lisp65_rt_c2d_01 { KEEP(*(.lisp65_rt_c2d_01)) }
        .lisp65_rt_c2d_02a { KEEP(*(.lisp65_rt_c2d_02a)) }
        .lisp65_rt_c2d_02b { KEEP(*(.lisp65_rt_c2d_02b)) }
        .lisp65_rt_c2d_03 { KEEP(*(.lisp65_rt_c2d_03)) }
        .lisp65_rt_c2d_04 { KEEP(*(.lisp65_rt_c2d_04)) }
        .lisp65_rt_c2d_05a { KEEP(*(.lisp65_rt_c2d_05a)) }
        .lisp65_rt_c2d_05b { KEEP(*(.lisp65_rt_c2d_05b)) }
        .lisp65_rt_c2d_06a { KEEP(*(.lisp65_rt_c2d_06a)) }
        .lisp65_rt_c2d_06b { KEEP(*(.lisp65_rt_c2d_06b)) }
        .lisp65_rt_c2d_06c { KEEP(*(.lisp65_rt_c2d_06c)) }
        .lisp65_rt_c2d_07 { KEEP(*(.lisp65_rt_c2d_07)) }
        .lisp65_rt_c2d_08 { KEEP(*(.lisp65_rt_c2d_08)) }
        .lisp65_rt_c2d_09a { KEEP(*(.lisp65_rt_c2d_09a)) }
        .lisp65_rt_c2d_09b { KEEP(*(.lisp65_rt_c2d_09b)) }
        .lisp65_rt_c2d_10a { KEEP(*(.lisp65_rt_c2d_10a)) }
        .lisp65_rt_c2d_10b { KEEP(*(.lisp65_rt_c2d_10b)) }
        .lisp65_rt_c2d_11a { KEEP(*(.lisp65_rt_c2d_11a)) }
        .lisp65_rt_c2d_11b { KEEP(*(.lisp65_rt_c2d_11b)) }
        .lisp65_rt_c2d_11c { KEEP(*(.lisp65_rt_c2d_11c)) }
        .lisp65_rt_c2d_11d { KEEP(*(.lisp65_rt_c2d_11d)) }
        .lisp65_rt_c2d_12 { KEEP(*(.lisp65_rt_c2d_12)) }
        .lisp65_rt_c2d_13a { KEEP(*(.lisp65_rt_c2d_13a)) }
        .lisp65_rt_c2d_13b { KEEP(*(.lisp65_rt_c2d_13b)) }
        .lisp65_rt_c2emit_prepare { KEEP(*(.lisp65_rt_c2emit_prepare)) }
        .lisp65_rt_c2emit_name { KEEP(*(.lisp65_rt_c2emit_name)) }
        .lisp65_rt_c2emit_literal_prep { KEEP(*(.lisp65_rt_c2emit_literal_prep)) }
        .lisp65_rt_c2emit_literal_atom { KEEP(*(.lisp65_rt_c2emit_literal_atom)) }
        .lisp65_rt_c2emit_literal_append { KEEP(*(.lisp65_rt_c2emit_literal_append)) }
        .lisp65_rt_c2emit_code { KEEP(*(.lisp65_rt_c2emit_code)) }
        .lisp65_rt_c2emit_final_meta { KEEP(*(.lisp65_rt_c2emit_final_meta)) }
        .lisp65_rt_c2emit_final_crc { KEEP(*(.lisp65_rt_c2emit_final_crc)) }
        .lisp65_rt_c2append_envelope { KEEP(*(.lisp65_rt_c2append_envelope)) }
        .lisp65_rt_c2append_crc { KEEP(*(.lisp65_rt_c2append_crc)) }
        .lisp65_rt_c2append_metadata { KEEP(*(.lisp65_rt_c2append_metadata)) }
        .lisp65_rt_c2append_capacity { KEEP(*(.lisp65_rt_c2append_capacity)) }
        .lisp65_rt_c2append_stage { KEEP(*(.lisp65_rt_c2append_stage)) }
        .lisp65_rt_c2append_image { KEEP(*(.lisp65_rt_c2append_image)) }
        .lisp65_rt_c2append_entries { KEEP(*(.lisp65_rt_c2append_entries)) }
        .lisp65_rt_c2append_header { KEEP(*(.lisp65_rt_c2append_header)) }
        .lisp65_rt_c2append_publish_names { KEEP(*(.lisp65_rt_c2append_publish_names)) }
        .lisp65_rt_c2append_publish_cells { KEEP(*(.lisp65_rt_c2append_publish_cells)) }
        .lisp65_rt_c2append_rollback { KEEP(*(.lisp65_rt_c2append_rollback)) }
        .lisp65_rt_l65e { KEEP(*(.lisp65_rt_l65e)) KEEP(*(.lisp65_rt_l65e_data)) }
        .lisp65_rt_island_00 { KEEP(*(.lisp65_rt_island_00)) KEEP(*(.lisp65_rt_island_00_data)) }
        .lisp65_rt_buffer_read { KEEP(*(.lisp65_rt_buffer_read)) }
        .lisp65_rt_buffer_write { KEEP(*(.lisp65_rt_buffer_write)) }
        .lisp65_rt_buffer_alloc { KEEP(*(.lisp65_rt_buffer_alloc)) }
    } >ram
} INSERT AFTER .noinit;

__lisp65_resident_island_seed_lma =
    ALIGN(LOADADDR(.lisp65_rt_buffer_alloc) + SIZEOF(.lisp65_rt_buffer_alloc), 0x100);

/* Link at the final CPU address while placing the seed image after all normal
 * Bank-0 load material. The shipped resident PRG is truncated before this LMA;
 * its only deployed load image is the bound Slot-37 payload. Inserting it after
 * the overlay LMAs keeps the fixed low VMA from advancing .basic_header. */
SECTIONS {
    .lisp65_resident_island 0x1800 : AT(__lisp65_resident_island_seed_lma) {
        KEEP(*(.lisp65_resident_island .lisp65_resident_island.*))
    } >ram
    /* Mutable NOLOAD state is adjacent to, but never part of, the immutable
     * island image installed and CRC-bound through Slot 37. */
    .lisp65_resident_island_annex ALIGN(ADDR(.lisp65_resident_island) +
                                           SIZEOF(.lisp65_resident_island), 2) (NOLOAD) : {
        KEEP(*(.lisp65_resident_island_annex.00_before))
        KEEP(*(.lisp65_resident_island_annex.01_stack))
        KEEP(*(.lisp65_resident_island_annex.02_after))
    } >ram
} INSERT AFTER .lisp65_rt_island_00;

__lisp65_workbench_overlay_start = ADDR(.lisp65_workbench_overlay);
__lisp65_workbench_overlay_end =
    ADDR(.lisp65_workbench_overlay) + SIZEOF(.lisp65_workbench_overlay);
__lisp65_workbench_overlay_entry = vm_workbench_boot_overlay_entry;
__lisp65_workbench_resident_file_end = __data_load_start + __data_size;
__lisp65_workbench_runtime_overlay_limit =
    __stack - __lisp65_workbench_required_runtime_stack;
__lisp65_workbench_boot_slice_limit =
    __stack - __lisp65_workbench_required_boot_stack;
__lisp65_rt_rtov_catalog_start = ADDR(.lisp65_rt_rtov_catalog); __lisp65_rt_rtov_catalog_end = ADDR(.lisp65_rt_rtov_catalog) + SIZEOF(.lisp65_rt_rtov_catalog);
__lisp65_rt_rtov_record_start = ADDR(.lisp65_rt_rtov_record); __lisp65_rt_rtov_record_end = ADDR(.lisp65_rt_rtov_record) + SIZEOF(.lisp65_rt_rtov_record);
__lisp65_rt_c2d_00_start = ADDR(.lisp65_rt_c2d_00); __lisp65_rt_c2d_00_end = ADDR(.lisp65_rt_c2d_00) + SIZEOF(.lisp65_rt_c2d_00);
__lisp65_rt_c2d_00b_start = ADDR(.lisp65_rt_c2d_00b); __lisp65_rt_c2d_00b_end = ADDR(.lisp65_rt_c2d_00b) + SIZEOF(.lisp65_rt_c2d_00b);
__lisp65_rt_c2d_01_start = ADDR(.lisp65_rt_c2d_01); __lisp65_rt_c2d_01_end = ADDR(.lisp65_rt_c2d_01) + SIZEOF(.lisp65_rt_c2d_01);
__lisp65_rt_c2d_02a_start = ADDR(.lisp65_rt_c2d_02a); __lisp65_rt_c2d_02a_end = ADDR(.lisp65_rt_c2d_02a) + SIZEOF(.lisp65_rt_c2d_02a);
__lisp65_rt_c2d_02b_start = ADDR(.lisp65_rt_c2d_02b); __lisp65_rt_c2d_02b_end = ADDR(.lisp65_rt_c2d_02b) + SIZEOF(.lisp65_rt_c2d_02b);
__lisp65_rt_c2d_03_start = ADDR(.lisp65_rt_c2d_03); __lisp65_rt_c2d_03_end = ADDR(.lisp65_rt_c2d_03) + SIZEOF(.lisp65_rt_c2d_03);
__lisp65_rt_c2d_04_start = ADDR(.lisp65_rt_c2d_04); __lisp65_rt_c2d_04_end = ADDR(.lisp65_rt_c2d_04) + SIZEOF(.lisp65_rt_c2d_04);
__lisp65_rt_c2d_05a_start = ADDR(.lisp65_rt_c2d_05a); __lisp65_rt_c2d_05a_end = ADDR(.lisp65_rt_c2d_05a) + SIZEOF(.lisp65_rt_c2d_05a);
__lisp65_rt_c2d_05b_start = ADDR(.lisp65_rt_c2d_05b); __lisp65_rt_c2d_05b_end = ADDR(.lisp65_rt_c2d_05b) + SIZEOF(.lisp65_rt_c2d_05b);
__lisp65_rt_c2d_06a_start = ADDR(.lisp65_rt_c2d_06a); __lisp65_rt_c2d_06a_end = ADDR(.lisp65_rt_c2d_06a) + SIZEOF(.lisp65_rt_c2d_06a);
__lisp65_rt_c2d_06b_start = ADDR(.lisp65_rt_c2d_06b); __lisp65_rt_c2d_06b_end = ADDR(.lisp65_rt_c2d_06b) + SIZEOF(.lisp65_rt_c2d_06b);
__lisp65_rt_c2d_06c_start = ADDR(.lisp65_rt_c2d_06c); __lisp65_rt_c2d_06c_end = ADDR(.lisp65_rt_c2d_06c) + SIZEOF(.lisp65_rt_c2d_06c);
__lisp65_rt_c2d_07_start = ADDR(.lisp65_rt_c2d_07); __lisp65_rt_c2d_07_end = ADDR(.lisp65_rt_c2d_07) + SIZEOF(.lisp65_rt_c2d_07);
__lisp65_rt_c2d_08_start = ADDR(.lisp65_rt_c2d_08); __lisp65_rt_c2d_08_end = ADDR(.lisp65_rt_c2d_08) + SIZEOF(.lisp65_rt_c2d_08);
__lisp65_rt_c2d_09a_start = ADDR(.lisp65_rt_c2d_09a); __lisp65_rt_c2d_09a_end = ADDR(.lisp65_rt_c2d_09a) + SIZEOF(.lisp65_rt_c2d_09a);
__lisp65_rt_c2d_09b_start = ADDR(.lisp65_rt_c2d_09b); __lisp65_rt_c2d_09b_end = ADDR(.lisp65_rt_c2d_09b) + SIZEOF(.lisp65_rt_c2d_09b);
__lisp65_rt_c2d_10a_start = ADDR(.lisp65_rt_c2d_10a); __lisp65_rt_c2d_10a_end = ADDR(.lisp65_rt_c2d_10a) + SIZEOF(.lisp65_rt_c2d_10a);
__lisp65_rt_c2d_10b_start = ADDR(.lisp65_rt_c2d_10b); __lisp65_rt_c2d_10b_end = ADDR(.lisp65_rt_c2d_10b) + SIZEOF(.lisp65_rt_c2d_10b);
__lisp65_rt_c2d_11a_start = ADDR(.lisp65_rt_c2d_11a); __lisp65_rt_c2d_11a_end = ADDR(.lisp65_rt_c2d_11a) + SIZEOF(.lisp65_rt_c2d_11a);
__lisp65_rt_c2d_11b_start = ADDR(.lisp65_rt_c2d_11b); __lisp65_rt_c2d_11b_end = ADDR(.lisp65_rt_c2d_11b) + SIZEOF(.lisp65_rt_c2d_11b);
__lisp65_rt_c2d_11c_start = ADDR(.lisp65_rt_c2d_11c); __lisp65_rt_c2d_11c_end = ADDR(.lisp65_rt_c2d_11c) + SIZEOF(.lisp65_rt_c2d_11c);
__lisp65_rt_c2d_11d_start = ADDR(.lisp65_rt_c2d_11d); __lisp65_rt_c2d_11d_end = ADDR(.lisp65_rt_c2d_11d) + SIZEOF(.lisp65_rt_c2d_11d);
__lisp65_rt_c2d_12_start = ADDR(.lisp65_rt_c2d_12); __lisp65_rt_c2d_12_end = ADDR(.lisp65_rt_c2d_12) + SIZEOF(.lisp65_rt_c2d_12);
__lisp65_rt_c2d_13a_start = ADDR(.lisp65_rt_c2d_13a); __lisp65_rt_c2d_13a_end = ADDR(.lisp65_rt_c2d_13a) + SIZEOF(.lisp65_rt_c2d_13a);
__lisp65_rt_c2d_13b_start = ADDR(.lisp65_rt_c2d_13b); __lisp65_rt_c2d_13b_end = ADDR(.lisp65_rt_c2d_13b) + SIZEOF(.lisp65_rt_c2d_13b);
__lisp65_rt_c2emit_prepare_start = ADDR(.lisp65_rt_c2emit_prepare); __lisp65_rt_c2emit_prepare_end = ADDR(.lisp65_rt_c2emit_prepare) + SIZEOF(.lisp65_rt_c2emit_prepare);
__lisp65_rt_c2emit_name_start = ADDR(.lisp65_rt_c2emit_name); __lisp65_rt_c2emit_name_end = ADDR(.lisp65_rt_c2emit_name) + SIZEOF(.lisp65_rt_c2emit_name);
__lisp65_rt_c2emit_literal_prep_start = ADDR(.lisp65_rt_c2emit_literal_prep); __lisp65_rt_c2emit_literal_prep_end = ADDR(.lisp65_rt_c2emit_literal_prep) + SIZEOF(.lisp65_rt_c2emit_literal_prep);
__lisp65_rt_c2emit_literal_atom_start = ADDR(.lisp65_rt_c2emit_literal_atom); __lisp65_rt_c2emit_literal_atom_end = ADDR(.lisp65_rt_c2emit_literal_atom) + SIZEOF(.lisp65_rt_c2emit_literal_atom);
__lisp65_rt_c2emit_literal_append_start = ADDR(.lisp65_rt_c2emit_literal_append); __lisp65_rt_c2emit_literal_append_end = ADDR(.lisp65_rt_c2emit_literal_append) + SIZEOF(.lisp65_rt_c2emit_literal_append);
__lisp65_rt_c2emit_code_start = ADDR(.lisp65_rt_c2emit_code); __lisp65_rt_c2emit_code_end = ADDR(.lisp65_rt_c2emit_code) + SIZEOF(.lisp65_rt_c2emit_code);
__lisp65_rt_c2emit_final_meta_start = ADDR(.lisp65_rt_c2emit_final_meta); __lisp65_rt_c2emit_final_meta_end = ADDR(.lisp65_rt_c2emit_final_meta) + SIZEOF(.lisp65_rt_c2emit_final_meta);
__lisp65_rt_c2emit_final_crc_start = ADDR(.lisp65_rt_c2emit_final_crc); __lisp65_rt_c2emit_final_crc_end = ADDR(.lisp65_rt_c2emit_final_crc) + SIZEOF(.lisp65_rt_c2emit_final_crc);
__lisp65_rt_c2append_envelope_start = ADDR(.lisp65_rt_c2append_envelope); __lisp65_rt_c2append_envelope_end = ADDR(.lisp65_rt_c2append_envelope) + SIZEOF(.lisp65_rt_c2append_envelope);
__lisp65_rt_c2append_crc_start = ADDR(.lisp65_rt_c2append_crc); __lisp65_rt_c2append_crc_end = ADDR(.lisp65_rt_c2append_crc) + SIZEOF(.lisp65_rt_c2append_crc);
__lisp65_rt_c2append_metadata_start = ADDR(.lisp65_rt_c2append_metadata); __lisp65_rt_c2append_metadata_end = ADDR(.lisp65_rt_c2append_metadata) + SIZEOF(.lisp65_rt_c2append_metadata);
__lisp65_rt_c2append_capacity_start = ADDR(.lisp65_rt_c2append_capacity); __lisp65_rt_c2append_capacity_end = ADDR(.lisp65_rt_c2append_capacity) + SIZEOF(.lisp65_rt_c2append_capacity);
__lisp65_rt_c2append_stage_start = ADDR(.lisp65_rt_c2append_stage); __lisp65_rt_c2append_stage_end = ADDR(.lisp65_rt_c2append_stage) + SIZEOF(.lisp65_rt_c2append_stage);
__lisp65_rt_c2append_image_start = ADDR(.lisp65_rt_c2append_image); __lisp65_rt_c2append_image_end = ADDR(.lisp65_rt_c2append_image) + SIZEOF(.lisp65_rt_c2append_image);
__lisp65_rt_c2append_entries_start = ADDR(.lisp65_rt_c2append_entries); __lisp65_rt_c2append_entries_end = ADDR(.lisp65_rt_c2append_entries) + SIZEOF(.lisp65_rt_c2append_entries);
__lisp65_rt_c2append_header_start = ADDR(.lisp65_rt_c2append_header); __lisp65_rt_c2append_header_end = ADDR(.lisp65_rt_c2append_header) + SIZEOF(.lisp65_rt_c2append_header);
__lisp65_rt_c2append_publish_names_start = ADDR(.lisp65_rt_c2append_publish_names); __lisp65_rt_c2append_publish_names_end = ADDR(.lisp65_rt_c2append_publish_names) + SIZEOF(.lisp65_rt_c2append_publish_names);
__lisp65_rt_c2append_publish_cells_start = ADDR(.lisp65_rt_c2append_publish_cells); __lisp65_rt_c2append_publish_cells_end = ADDR(.lisp65_rt_c2append_publish_cells) + SIZEOF(.lisp65_rt_c2append_publish_cells);
__lisp65_rt_c2append_rollback_start = ADDR(.lisp65_rt_c2append_rollback); __lisp65_rt_c2append_rollback_end = ADDR(.lisp65_rt_c2append_rollback) + SIZEOF(.lisp65_rt_c2append_rollback);
__lisp65_rt_l65e_start = ADDR(.lisp65_rt_l65e); __lisp65_rt_l65e_end = ADDR(.lisp65_rt_l65e) + SIZEOF(.lisp65_rt_l65e);
__lisp65_rt_buffer_read_start = ADDR(.lisp65_rt_buffer_read); __lisp65_rt_buffer_read_end = ADDR(.lisp65_rt_buffer_read) + SIZEOF(.lisp65_rt_buffer_read);
__lisp65_rt_buffer_write_start = ADDR(.lisp65_rt_buffer_write); __lisp65_rt_buffer_write_end = ADDR(.lisp65_rt_buffer_write) + SIZEOF(.lisp65_rt_buffer_write);
__lisp65_rt_buffer_alloc_start = ADDR(.lisp65_rt_buffer_alloc); __lisp65_rt_buffer_alloc_end = ADDR(.lisp65_rt_buffer_alloc) + SIZEOF(.lisp65_rt_buffer_alloc);
__lisp65_resident_island_start = ADDR(.lisp65_resident_island); __lisp65_resident_island_end = ADDR(.lisp65_resident_island) + SIZEOF(.lisp65_resident_island);
__lisp65_resident_island_annex_start = ADDR(.lisp65_resident_island_annex); __lisp65_resident_island_annex_end = ADDR(.lisp65_resident_island_annex) + SIZEOF(.lisp65_resident_island_annex);
__lisp65_rt_island_00_start = ADDR(.lisp65_rt_island_00); __lisp65_rt_island_00_end = ADDR(.lisp65_rt_island_00) + SIZEOF(.lisp65_rt_island_00);
__lisp65_rt_rtov_catalog_entry = vm_runtime_overlay_catalog_verifier;
__lisp65_rt_rtov_record_entry = vm_runtime_overlay_record_verifier;
__lisp65_rt_c2d_00_entry = c2_stream_phase_00;
__lisp65_rt_c2d_00b_entry = c2_stream_phase_00b;
__lisp65_rt_c2d_01_entry = c2_stream_phase_01;
__lisp65_rt_c2d_02a_entry = c2_product_decode_02a;
__lisp65_rt_c2d_02b_entry = c2_product_decode_02b;
__lisp65_rt_c2d_03_entry = c2_stream_phase_03;
__lisp65_rt_c2d_04_entry = c2_stream_phase_04;
__lisp65_rt_c2d_05a_entry = c2_product_decode_05a;
__lisp65_rt_c2d_05b_entry = c2_product_decode_05b;
__lisp65_rt_c2d_06a_entry = c2_product_decode_06a;
__lisp65_rt_c2d_06b_entry = c2_product_decode_06b;
__lisp65_rt_c2d_06c_entry = c2_product_decode_06c;
__lisp65_rt_c2d_07_entry = c2_stream_phase_07;
__lisp65_rt_c2d_08_entry = c2_stream_phase_08;
__lisp65_rt_c2d_09a_entry = c2_product_decode_09a;
__lisp65_rt_c2d_09b_entry = c2_product_decode_09b;
__lisp65_rt_c2d_10a_entry = c2_product_decode_10a;
__lisp65_rt_c2d_10b_entry = c2_product_decode_10b;
__lisp65_rt_c2d_11a_entry = c2_product_decode_11a;
__lisp65_rt_c2d_11b_entry = c2_product_decode_11b;
__lisp65_rt_c2d_11c_entry = c2_product_decode_11c;
__lisp65_rt_c2d_11d_entry = c2_product_decode_11d;
__lisp65_rt_c2d_12_entry = c2_stream_phase_12;
__lisp65_rt_c2d_13a_entry = c2_product_decode_13a;
__lisp65_rt_c2d_13b_entry = c2_product_decode_13b;
__lisp65_rt_c2emit_prepare_entry = c2_session_emit_prepare_phase;
__lisp65_rt_c2emit_name_entry = c2_session_emit_name_phase;
__lisp65_rt_c2emit_literal_prep_entry = c2_session_emit_literal_prep_phase;
__lisp65_rt_c2emit_literal_atom_entry = c2_session_emit_literal_atom_phase;
__lisp65_rt_c2emit_literal_append_entry = c2_session_emit_literal_append_phase;
__lisp65_rt_c2emit_code_entry = c2_session_emit_code_phase;
__lisp65_rt_c2emit_final_meta_entry = c2_session_emit_final_meta_phase;
__lisp65_rt_c2emit_final_crc_entry = c2_session_emit_final_crc_phase;
__lisp65_rt_c2append_envelope_entry = c2_append_envelope_phase;
__lisp65_rt_c2append_crc_entry = c2_append_crc_phase;
__lisp65_rt_c2append_metadata_entry = c2_append_metadata_phase;
__lisp65_rt_c2append_capacity_entry = c2_append_capacity_phase;
__lisp65_rt_c2append_stage_entry = c2_append_stage_phase;
__lisp65_rt_c2append_image_entry = c2_append_image_phase;
__lisp65_rt_c2append_entries_entry = c2_append_entries_phase;
__lisp65_rt_c2append_header_entry = c2_append_header_phase;
__lisp65_rt_c2append_publish_names_entry = c2_append_publish_names_phase;
__lisp65_rt_c2append_publish_cells_entry = c2_append_publish_cells_phase;
__lisp65_rt_c2append_rollback_entry = c2_append_rollback_phase;
__lisp65_rt_l65e_entry = lisp65_error_overlay_entry;
__lisp65_rt_buffer_read_entry = lisp65_buffer_overlay_read_entry;
__lisp65_rt_buffer_write_entry = lisp65_buffer_overlay_write_entry;
__lisp65_rt_buffer_alloc_entry = lisp65_buffer_overlay_alloc_entry;
__lisp65_rt_island_00_entry = vm_resident_island_install;

ASSERT(__lisp65_workbench_screen_base == 0x0800 &&
       __lisp65_workbench_screen_columns == 80 &&
       __lisp65_workbench_screen_rows == 50 &&
       __lisp65_workbench_screen_cell_bytes == 1 &&
       __lisp65_workbench_screen_limit == 0x17a0,
       "resident island requires the non-SEAM $0800 80x50x1 screen contract");
ASSERT((!DEFINED(__lisp65_workbench_screen_base_param) || __lisp65_workbench_screen_base_param == 0x0800) &&
       (!DEFINED(__lisp65_workbench_screen_columns_param) || __lisp65_workbench_screen_columns_param == 80) &&
       (!DEFINED(__lisp65_workbench_screen_rows_param) || __lisp65_workbench_screen_rows_param == 50) &&
       (!DEFINED(__lisp65_workbench_screen_cell_bytes_param) || __lisp65_workbench_screen_cell_bytes_param == 1),
       "Workbench screen link parameters drifted from the non-SEAM contract");
ASSERT(__lisp65_resident_island_start == 0x1800 &&
       __lisp65_workbench_screen_limit <= __lisp65_resident_island_start,
       "resident island overlaps the Workbench screen");
ASSERT(LOADADDR(.lisp65_resident_island) ==
           __lisp65_resident_island_seed_lma &&
       (LOADADDR(.lisp65_resident_island) & 0xff) == 0 &&
       LOADADDR(.lisp65_resident_island) >= 0x10000,
       "resident island seed LMA is not aligned directly after the final C2 runtime slice");
ASSERT(SIZEOF(.lisp65_resident_island) > 0 &&
       SIZEOF(.lisp65_resident_island) <= __lisp65_resident_island_payload_capacity &&
       __lisp65_resident_island_end <= __lisp65_resident_island_limit,
       "resident island exceeds its fixed-capacity $1800 window");
ASSERT(__lisp65_resident_island_end <= __lisp65_resident_island_annex_start,
       "rootstack annex overlaps the immutable resident island");
ASSERT((__lisp65_resident_island_annex_start & 1) == 0 &&
       lisp65_rootstack_canary_before == __lisp65_resident_island_annex_start &&
       gc_rootstack == (__lisp65_resident_island_annex_start + 2) &&
       lisp65_rootstack_canary_after == (__lisp65_resident_island_annex_start + 258) &&
       SIZEOF(.lisp65_resident_island_annex) == 260,
       "rootstack annex layout drifted from the pinned 2+256+2-byte contract");
ASSERT(__lisp65_resident_island_annex_end <= __lisp65_resident_island_limit,
       "rootstack annex exceeds the fixed $2000 island limit");
ASSERT((!DEFINED(__lisp65_resident_island_base_param) || __lisp65_resident_island_base_param == 0x1800) &&
       (!DEFINED(__lisp65_resident_island_limit_param) || __lisp65_resident_island_limit_param == 0x2000) &&
       (!DEFINED(__lisp65_resident_island_payload_capacity_param) || __lisp65_resident_island_payload_capacity_param == 2048),
       "resident island link parameters drifted from the pinned contract");
ASSERT(__bss_end < __lisp65_workbench_overlay_start,
       "workbench overlay overlaps resident BSS");
ASSERT(__heap_start <= __lisp65_workbench_overlay_start,
       "workbench overlay moved below the heap floor");
ASSERT(__lisp65_workbench_overlay_entry >= __lisp65_workbench_overlay_start &&
       __lisp65_workbench_overlay_entry < __lisp65_workbench_overlay_end,
       "workbench overlay entry lies outside the raw payload");
ASSERT(eval_init >= __lisp65_workbench_overlay_start &&
       eval_init < __lisp65_workbench_overlay_end,
       "workbench eval_init is not in the boot overlay");
ASSERT(__lisp65_workbench_resident_file_end <= __bss_start,
       "workbench resident file end moved beyond BSS");
ASSERT(__lisp65_workbench_overlay_end <=
           (__stack - __lisp65_workbench_required_boot_stack),
       "workbench overlay leaves too little boot stack");
ASSERT((__stack - __heap_start) >=
           (__lisp65_workbench_required_runtime_stack +
            __lisp65_workbench_required_post_boot_reserve),
       "workbench overlay leaves too little post-boot reserve");
ASSERT(SIZEOF(.lisp65_workbench_overlay) > 0,
       "workbench overlay is empty (missing BOOTFN sections)");
ASSERT(__lisp65_workbench_runtime_overlay_vma <
           __lisp65_workbench_runtime_overlay_limit,
       "workbench runtime-overlay window is empty");
ASSERT(__lisp65_workbench_overlay_min_start <=
           __lisp65_workbench_runtime_overlay_vma,
       "resident/noinit state overlaps the fixed runtime-overlay VMA");
ASSERT(__lisp65_workbench_runtime_overlay_vma <=
           __lisp65_workbench_runtime_overlay_max_vma,
       "workbench runtime-overlay VMA exceeds the product Bank-0 ceiling");
ASSERT((__lisp65_workbench_runtime_overlay_vma +
        __lisp65_workbench_runtime_transport_max_bytes) <=
           __lisp65_workbench_runtime_overlay_limit,
       "workbench runtime-overlay transport window exceeds its stack-safe limit");
ASSERT(SIZEOF(.lisp65_rt_rtov_catalog) > 0 && SIZEOF(.lisp65_rt_rtov_catalog) <= 1792 && __lisp65_rt_rtov_catalog_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay catalog verifier exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_rtov_record) > 0 && SIZEOF(.lisp65_rt_rtov_record) <= 1792 && __lisp65_rt_rtov_record_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay record verifier exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_00) > 0 && SIZEOF(.lisp65_rt_c2d_00) <= 1792 && __lisp65_rt_c2d_00_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 00 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_00b) > 0 && SIZEOF(.lisp65_rt_c2d_00b) <= 1792 && __lisp65_rt_c2d_00b_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 00b exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_01) > 0 && SIZEOF(.lisp65_rt_c2d_01) <= 1792 && __lisp65_rt_c2d_01_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 01 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_02a) > 0 && SIZEOF(.lisp65_rt_c2d_02a) <= 1792 && __lisp65_rt_c2d_02a_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 02a exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_02b) > 0 && SIZEOF(.lisp65_rt_c2d_02b) <= 1792 && __lisp65_rt_c2d_02b_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 02b exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_03) > 0 && SIZEOF(.lisp65_rt_c2d_03) <= 1792 && __lisp65_rt_c2d_03_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 03 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_04) > 0 && SIZEOF(.lisp65_rt_c2d_04) <= 1792 && __lisp65_rt_c2d_04_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 04 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_05a) > 0 && SIZEOF(.lisp65_rt_c2d_05a) <= 1792 && __lisp65_rt_c2d_05a_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 05a exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_05b) > 0 && SIZEOF(.lisp65_rt_c2d_05b) <= 1792 && __lisp65_rt_c2d_05b_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 05b exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_06a) > 0 && SIZEOF(.lisp65_rt_c2d_06a) <= 1792 && __lisp65_rt_c2d_06a_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 06a exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_06b) > 0 && SIZEOF(.lisp65_rt_c2d_06b) <= 1792 && __lisp65_rt_c2d_06b_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 06b exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_06c) > 0 && SIZEOF(.lisp65_rt_c2d_06c) <= 1792 && __lisp65_rt_c2d_06c_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 06c exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_07) > 0 && SIZEOF(.lisp65_rt_c2d_07) <= 1792 && __lisp65_rt_c2d_07_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 07 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_08) > 0 && SIZEOF(.lisp65_rt_c2d_08) <= 1792 && __lisp65_rt_c2d_08_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 08 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_09a) > 0 && SIZEOF(.lisp65_rt_c2d_09a) <= 1792 && __lisp65_rt_c2d_09a_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 09a exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_09b) > 0 && SIZEOF(.lisp65_rt_c2d_09b) <= 1792 && __lisp65_rt_c2d_09b_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 09b exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_10a) > 0 && SIZEOF(.lisp65_rt_c2d_10a) <= 1792 && __lisp65_rt_c2d_10a_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 10a exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_10b) > 0 && SIZEOF(.lisp65_rt_c2d_10b) <= 1792 && __lisp65_rt_c2d_10b_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 10b exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_11a) > 0 && SIZEOF(.lisp65_rt_c2d_11a) <= 1792 && __lisp65_rt_c2d_11a_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 11a exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_11b) > 0 && SIZEOF(.lisp65_rt_c2d_11b) <= 1792 && __lisp65_rt_c2d_11b_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 11b exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_11c) > 0 && SIZEOF(.lisp65_rt_c2d_11c) <= 1792 && __lisp65_rt_c2d_11c_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 11c exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_11d) > 0 && SIZEOF(.lisp65_rt_c2d_11d) <= 1792 && __lisp65_rt_c2d_11d_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 11d exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_12) > 0 && SIZEOF(.lisp65_rt_c2d_12) <= 1792 && __lisp65_rt_c2d_12_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 12 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_13a) > 0 && SIZEOF(.lisp65_rt_c2d_13a) <= 1792 && __lisp65_rt_c2d_13a_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 13a exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_13b) > 0 && SIZEOF(.lisp65_rt_c2d_13b) <= 1792 && __lisp65_rt_c2d_13b_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 13b exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2emit_prepare) > 0 && SIZEOF(.lisp65_rt_c2emit_prepare) <= 1792 && __lisp65_rt_c2emit_prepare_end <= __lisp65_workbench_runtime_overlay_limit, "C2 emitter phase prepare exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2emit_name) > 0 && SIZEOF(.lisp65_rt_c2emit_name) <= 1792 && __lisp65_rt_c2emit_name_end <= __lisp65_workbench_runtime_overlay_limit, "C2 emitter phase name exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2emit_literal_prep) > 0 && SIZEOF(.lisp65_rt_c2emit_literal_prep) <= 1792 && __lisp65_rt_c2emit_literal_prep_end <= __lisp65_workbench_runtime_overlay_limit, "C2 emitter phase literal_prep exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2emit_literal_atom) > 0 && SIZEOF(.lisp65_rt_c2emit_literal_atom) <= 1792 && __lisp65_rt_c2emit_literal_atom_end <= __lisp65_workbench_runtime_overlay_limit, "C2 emitter phase literal_atom exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2emit_literal_append) > 0 && SIZEOF(.lisp65_rt_c2emit_literal_append) <= 1792 && __lisp65_rt_c2emit_literal_append_end <= __lisp65_workbench_runtime_overlay_limit, "C2 emitter phase literal_append exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2emit_code) > 0 && SIZEOF(.lisp65_rt_c2emit_code) <= 1792 && __lisp65_rt_c2emit_code_end <= __lisp65_workbench_runtime_overlay_limit, "C2 emitter phase code exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2emit_final_meta) > 0 && SIZEOF(.lisp65_rt_c2emit_final_meta) <= 1792 && __lisp65_rt_c2emit_final_meta_end <= __lisp65_workbench_runtime_overlay_limit, "C2 emitter phase final_meta exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2emit_final_crc) > 0 && SIZEOF(.lisp65_rt_c2emit_final_crc) <= 1792 && __lisp65_rt_c2emit_final_crc_end <= __lisp65_workbench_runtime_overlay_limit, "C2 emitter phase final_crc exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_envelope) > 0 && SIZEOF(.lisp65_rt_c2append_envelope) <= 1792 && __lisp65_rt_c2append_envelope_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase envelope exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_crc) > 0 && SIZEOF(.lisp65_rt_c2append_crc) <= 1792 && __lisp65_rt_c2append_crc_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase crc exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_metadata) > 0 && SIZEOF(.lisp65_rt_c2append_metadata) <= 1792 && __lisp65_rt_c2append_metadata_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase metadata exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_capacity) > 0 && SIZEOF(.lisp65_rt_c2append_capacity) <= 1792 && __lisp65_rt_c2append_capacity_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase capacity exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_stage) > 0 && SIZEOF(.lisp65_rt_c2append_stage) <= 1792 && __lisp65_rt_c2append_stage_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase stage exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_image) > 0 && SIZEOF(.lisp65_rt_c2append_image) <= 1792 && __lisp65_rt_c2append_image_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase image exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_entries) > 0 && SIZEOF(.lisp65_rt_c2append_entries) <= 1792 && __lisp65_rt_c2append_entries_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase entries exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_header) > 0 && SIZEOF(.lisp65_rt_c2append_header) <= 1792 && __lisp65_rt_c2append_header_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase header exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_publish_names) > 0 && SIZEOF(.lisp65_rt_c2append_publish_names) <= 1792 && __lisp65_rt_c2append_publish_names_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase publish_names exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_publish_cells) > 0 && SIZEOF(.lisp65_rt_c2append_publish_cells) <= 1792 && __lisp65_rt_c2append_publish_cells_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase publish_cells exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_rollback) > 0 && SIZEOF(.lisp65_rt_c2append_rollback) <= 1792 && __lisp65_rt_c2append_rollback_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase rollback exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65e) > 0 && SIZEOF(.lisp65_rt_l65e) <= 1792 && __lisp65_rt_l65e_end <= __lisp65_workbench_runtime_overlay_limit, "L65E renderer exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65e) <= __lisp65_error_overlay_max_bytes, "L65E renderer exceeds its product budget");
ASSERT(SIZEOF(.lisp65_rt_buffer_read) > 0 && SIZEOF(.lisp65_rt_buffer_read) <= 1792 && __lisp65_rt_buffer_read_end <= __lisp65_workbench_runtime_overlay_limit, "buffer reader exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_buffer_write) > 0 && SIZEOF(.lisp65_rt_buffer_write) <= 1792 && __lisp65_rt_buffer_write_end <= __lisp65_workbench_runtime_overlay_limit, "buffer writer exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_buffer_alloc) > 0 && SIZEOF(.lisp65_rt_buffer_alloc) <= 1792 && __lisp65_rt_buffer_alloc_end <= __lisp65_workbench_runtime_overlay_limit, "buffer allocator exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_island_00) > 0 && SIZEOF(.lisp65_rt_island_00) <= 4096 && __lisp65_rt_island_00_end <= __lisp65_workbench_boot_slice_limit, "boot overlay resident-island installer exceeds its 512-byte stack window");
ASSERT(SIZEOF(.lisp65_rt_island_00) <= 1792,
       "resident-island installer exceeds the product Slot-37 budget");

/* Four verifier tuples are the sole publish-last
 * mutation domain.  The input comes from a non-LTO assembler object, and the
 * public labels pin order as boot catalog/record then session catalog/record. */
SECTIONS {
    .lisp65_runtime_overlay_verifier_bindings : {
        __lisp65_rtov_binding_section_start = .;
        KEEP(*(.lisp65_runtime_overlay_verifier_bindings))
        __lisp65_rtov_binding_section_end = .;
    } >ram
} INSERT AFTER .rodata;

ASSERT(SIZEOF(.lisp65_runtime_overlay_verifier_bindings) == 32 &&
       __lisp65_rtov_binding_section_end -
       __lisp65_rtov_binding_section_start == 32,
       "runtime-overlay verifier binding table is not exactly 32 bytes");
ASSERT(__lisp65_rtov_verifier_bindings_start ==
           __lisp65_rtov_binding_section_start &&
       rtov_boot_verifiers == __lisp65_rtov_binding_section_start &&
       rtov_verifiers == __lisp65_rtov_binding_section_start + 16 &&
       __lisp65_rtov_verifier_bindings_end ==
           __lisp65_rtov_binding_section_end,
       "runtime-overlay verifier tuple order or labels drifted");
/* Product-resident handoff code is ordinary PRG material.  Name it here so
 * neither fixed-VMA artifact can capture an orphan section. */
SECTIONS {
    .lisp65_c2_kernal_handoff 0xb481 : {
        KEEP(*(.lisp65_c2_kernal_handoff))
    } >ram
    .lisp65_c2_host_facade 0xb5a2 : {
        KEEP(*(.lisp65_c2_host_facade))
    } >ram
    .lisp65_c2_kernal_map_switch 0xb5d0 : {
        KEEP(*(.lisp65_c2_kernal_map_switch))
    } >ram
    .lisp65_c2_kernal_state 0xb5dd (NOLOAD) : {
        KEEP(*(.lisp65_c2_kernal_state))
    } >ram
} INSERT AFTER .text;

/* Every state cell referenced by the owned window has a declared address.
 * These are storage contracts, not ordinary whole-program allocation. */
SECTIONS {
    .lisp65_c2_fixed_zp 0x89 (NOLOAD) : {
        __lisp65_c2_fixed_zp_phase_owner = .;
        KEEP(*(.lisp65_c2_fixed_zp.phase_owner))
        __lisp65_c2_fixed_zp_pending_roots = .;
        KEEP(*(.lisp65_c2_fixed_zp.pending_roots))
        __lisp65_c2_fixed_zp_ready = .;
        KEEP(*(.lisp65_c2_fixed_zp.ready))
        __lisp65_c2_fixed_zp_str_building = .;
        KEEP(*(.lisp65_c2_fixed_zp.str_building))
        __lisp65_c2_fixed_zp_mem_oom = .;
        KEEP(*(.lisp65_c2_fixed_zp.mem_oom))
    } >zp
} INSERT AFTER .zp;

SECTIONS {
    .lisp65_c2_fixed_bank0 0xc080 (NOLOAD) : {
        __lisp65_c2_fixed_bank0_committed_roots = .;
        KEEP(*(.lisp65_c2_fixed_bank0.committed_roots))
        __lisp65_c2_fixed_bank0_decode_active = .;
        KEEP(*(.lisp65_c2_fixed_bank0.decode_active))
        __lisp65_c2_fixed_bank0_runtime = .;
        KEEP(*(.lisp65_c2_fixed_bank0.runtime))
        __lisp65_c2_fixed_bank0_edma_job = .;
        KEEP(*(.lisp65_c2_fixed_bank0.edma_job))
        __lisp65_c2_fixed_bank0_phase_scratch = .;
        KEEP(*(.lisp65_c2_fixed_bank0.phase_scratch))
        __lisp65_c2_fixed_bank0_sym_name_scratch = .;
        KEEP(*(.lisp65_c2_fixed_bank0.sym_name_scratch))
    } >ram
    .lisp65_c2_fixed_bank0_code 0xc218 : {
        __lisp65_c2_fixed_bank0_code_start = .;
        __lisp65_c2_fixed_bank0_code_kb_cursor_off = .;
        KEEP(*(.lisp65_c2_fixed_bank0_code.kb_cursor_off))
        __lisp65_c2_fixed_bank0_code_c2e_cons = .;
        KEEP(*(.lisp65_c2_fixed_bank0_code.c2e_cons))
        __lisp65_c2_fixed_bank0_code_end = .;
    } >ram
} INSERT AFTER .bss;

/* The owned CPU window has its own load-image counter.  Preserve VMA-relative
 * holes in the LMA so objcopy emits one exact 8-KiB window image. */
SECTIONS {
    .lisp65_c2_kernal_window.typed_queue_driver 0xe000 :
        AT(ORIGIN(c2_kernal_window_load) + 0x0000) {
        KEEP(*(.lisp65_c2_kernal_window.typed_queue_driver))
    } >c2_kernal_window
    .lisp65_c2_kernal_window.frame_source :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.frame_source) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.frame_source))
    } >c2_kernal_window
    .lisp65_c2_kernal_window.irq_handler :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.irq_handler) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.irq_handler))
    } >c2_kernal_window
    .lisp65_c2_kernal_window.nmi_and_freezer_return :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.nmi_and_freezer_return) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.nmi_and_freezer_return))
    } >c2_kernal_window
    .lisp65_c2_kernal_window.map_switch_and_guards :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.map_switch_and_guards) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.map_switch_and_guards))
    } >c2_kernal_window
    .lisp65_c2_kernal_window.post_startup_output_seam :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.post_startup_output_seam) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.post_startup_output_seam))
    } >c2_kernal_window
    .lisp65_c2_kernal_window.event_poll :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.event_poll) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.event_poll))
    } >c2_kernal_window
    .lisp65_c2_kernal_window.session_emitter_code :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.session_emitter_code) - 0xe000) {
        __lisp65_c2_session_emitter_code_start = .;
        KEEP(*(.lisp65_c2_kernal_window.session_emitter_code))
        __lisp65_c2_session_emitter_code_end = .;
    } >c2_kernal_window
    .lisp65_c2_kernal_window.c2_resident :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.c2_resident) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.c2_resident))
    } >c2_kernal_window
    .lisp65_c2_kernal_window.session_emitter_state (NOLOAD) :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.session_emitter_state) - 0xe000) {
        __lisp65_c2_session_emitter_state_start = .;
        KEEP(*(.lisp65_c2_kernal_window.session_emitter_state))
        __lisp65_c2_session_emitter_state_end = .;
    } >c2_kernal_window
    .lisp65_c2_kernal_window.state 0xff80 :
        AT(ORIGIN(c2_kernal_window_load) + 0x1f80) {
        KEEP(*(.lisp65_c2_kernal_window.state))
    } >c2_kernal_window
    .lisp65_c2_vectors 0xfffa :
        AT(ORIGIN(c2_kernal_window_load) + 0x1ffa) {
        KEEP(*(.lisp65_c2_vectors))
    } >c2_kernal_window
} INSERT AFTER .lisp65_resident_island_annex;

ASSERT(ADDR(.basic_header) == 0x2001,
       "C2 load domains moved the product PRG header");
ASSERT(LOADADDR(.lisp65_workbench_overlay) == ORIGIN(c2_runtime_load),
       "C2 runtime-slice load domain did not start at its own origin");
ASSERT(__lisp65_resident_island_seed_lma + SIZEOF(.lisp65_resident_island) <=
       ORIGIN(c2_runtime_load) + LENGTH(c2_runtime_load),
       "C2 runtime-slice load domain exhausted");
ASSERT(LOADADDR(.lisp65_c2_kernal_window.typed_queue_driver) ==
       ORIGIN(c2_kernal_window_load),
       "C2 KERNAL-window load domain did not start at its own origin");
ASSERT(LOADADDR(.lisp65_c2_vectors) + SIZEOF(.lisp65_c2_vectors) ==
       ORIGIN(c2_kernal_window_load) + LENGTH(c2_kernal_window_load),
       "C2 KERNAL-window load image is not exactly 8 KiB");
ASSERT(ADDR(.lisp65_c2_kernal_handoff) < 0xe000 &&
       ADDR(.lisp65_c2_host_facade) < 0xe000 &&
       ADDR(.lisp65_c2_kernal_map_switch) < 0xe000 &&
       ADDR(.lisp65_c2_kernal_state) < 0xe000,
       "C2 low-resident handoff escaped the PRG domain");
ASSERT(ADDR(.lisp65_c2_kernal_handoff) == 0xb481 &&
       ADDR(.lisp65_c2_kernal_handoff) + SIZEOF(.lisp65_c2_kernal_handoff) <= 0xb5a2,
       "C2 handoff overlaps the fixed host facade");
ASSERT(ADDR(.lisp65_c2_host_facade) == 0xb5a2 &&
       SIZEOF(.lisp65_c2_host_facade) == 36,
       "C2 fixed host-facade geometry drift");
ASSERT(c2_facade_vm_code_load == 0xb5a2 && c2_facade_c2_dma == 0xb5a5 &&
       c2_facade_overlay_call_family == 0xb5a8 && c2_facade_c2e_cons == 0xb5ab &&
       c2_facade_c2e_overlay == 0xb5ae && c2_facade_car == 0xb5b1 &&
       c2_facade_cdr == 0xb5b4 && c2_facade_gc_collect == 0xb5b7 &&
       c2_facade_str_open == 0xb5ba && c2_facade_str_putc == 0xb5bd &&
       c2_facade_intern == 0xb5c0 && c2_facade_select_family == 0xb5c3,
       "C2 fixed host-facade vector address drift");
ASSERT(ADDR(.lisp65_c2_kernal_map_switch) == 0xb5d0 &&
       ADDR(.lisp65_c2_kernal_state) == 0xb5dd,
       "C2 fixed low-resident handoff geometry drift");

ASSERT(ADDR(.zp) + SIZEOF(.zp) <= 0x89,
       "ordinary zero-page storage overlaps fixed C2 state");
ASSERT(ADDR(.lisp65_c2_fixed_zp) == 0x89 &&
       SIZEOF(.lisp65_c2_fixed_zp) == 7 &&
       __lisp65_c2_fixed_zp_phase_owner == 0x89 &&
       __lisp65_c2_fixed_zp_pending_roots == 0x8a &&
       __lisp65_c2_fixed_zp_ready == 0x8c &&
       __lisp65_c2_fixed_zp_str_building == 0x8d &&
       __lisp65_c2_fixed_zp_mem_oom == 0x8f,
       "C2 fixed zero-page state geometry drift");
ASSERT(ADDR(.bss) + SIZEOF(.bss) <= 0xc080,
       "ordinary Bank-0 state overlaps fixed C2 state");
ASSERT(ADDR(.lisp65_c2_fixed_bank0) == 0xc080 &&
       SIZEOF(.lisp65_c2_fixed_bank0) == 408 &&
       __lisp65_c2_fixed_bank0_committed_roots == 0xc080 &&
       __lisp65_c2_fixed_bank0_decode_active == 0xc082 &&
       __lisp65_c2_fixed_bank0_runtime == 0xc084 &&
       __lisp65_c2_fixed_bank0_edma_job == 0xc0b2 &&
       __lisp65_c2_fixed_bank0_phase_scratch == 0xc0c6 &&
       __lisp65_c2_fixed_bank0_sym_name_scratch == 0xc1f6,
       "C2 fixed Bank-0 state geometry drift");
ASSERT(ADDR(.lisp65_c2_fixed_bank0) + SIZEOF(.lisp65_c2_fixed_bank0) <=
       ADDR(.lisp65_c2_fixed_bank0_code) &&
       ADDR(.lisp65_c2_fixed_bank0_code) == 0xc218 &&
       SIZEOF(.lisp65_c2_fixed_bank0_code) == 45 &&
       __lisp65_c2_fixed_bank0_code_start == 0xc218 &&
       __lisp65_c2_fixed_bank0_code_kb_cursor_off == 0xc218 &&
       __lisp65_c2_fixed_bank0_code_c2e_cons == 0xc21d &&
       __lisp65_c2_fixed_bank0_code_end == 0xc245 &&
       ADDR(.lisp65_c2_fixed_bank0_code) +
       SIZEOF(.lisp65_c2_fixed_bank0_code) <=
       __lisp65_workbench_runtime_overlay_vma,
       "C2 fixed Bank-0 state overlaps the runtime overlay");

ASSERT(ADDR(.lisp65_c2_kernal_window.c2_resident) +
       SIZEOF(.lisp65_c2_kernal_window.c2_resident) <= 0xff80,
       "C2-owned KERNAL-window residents overlap state");
ASSERT(SIZEOF(.lisp65_c2_kernal_window.session_emitter_code) == 0 &&
       SIZEOF(.lisp65_c2_kernal_window.session_emitter_state) == 346,
       "C2 session-only E000 residency geometry drift");
ASSERT(ADDR(.lisp65_c2_kernal_window.state) == 0xff80 &&
       SIZEOF(.lisp65_c2_kernal_window.state) == 16,
       "C2 KERNAL-window state geometry drift");
ASSERT(ADDR(.lisp65_c2_vectors) == 0xfffa && SIZEOF(.lisp65_c2_vectors) == 6,
       "C2 owned vector geometry drift");

/* Exact non-ALLOC orphan allowlist.  Unknown section names remain fatal. */
SECTIONS {
    .comment 0 (INFO) : { *(.comment) }
    .symtab 0 (INFO) : { *(.symtab) }
    .strtab 0 (INFO) : { *(.strtab) }
    .shstrtab 0 (INFO) : { *(.shstrtab) }
    .lisp65_error_callsites 0 (INFO) : { KEEP(*(.lisp65_error_callsites)) }
}
ASSERT(SIZEOF(.lisp65_error_callsites) > 0,
       "required error-callsite evidence section is absent");
ASSERT(ADDR(.lisp65_error_callsites) == 0,
       "error-callsite evidence section moved from address zero");
