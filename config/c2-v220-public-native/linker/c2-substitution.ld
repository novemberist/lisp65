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
__lisp65_workbench_overlay_min_start = 0xc354;

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
        .lisp65_boot_bank3_stage { KEEP(*(.lisp65_boot_bank3_stage_prefix)) KEEP(*(.lisp65_boot_bank3_stage)) }
        .lisp65_rt_rtov_catalog { KEEP(*(.lisp65_rt_rtov_catalog)) }
        .lisp65_rt_rtov_record { KEEP(*(.lisp65_rt_rtov_record)) }
        .lisp65_rt_c2d_00 { KEEP(*(.lisp65_rt_c2d_00)) }
        .lisp65_rt_c2d_00b { KEEP(*(.lisp65_rt_c2d_00b)) }
        .lisp65_rt_c2d_01 { KEEP(*(.lisp65_rt_c2d_01)) }
        .lisp65_rt_c2d_02a { KEEP(*(.lisp65_rt_c2d_02a)) }
        .lisp65_rt_c2d_02b { KEEP(*(.lisp65_rt_c2d_02b)) }
        .lisp65_rt_c2d_03 { KEEP(*(.lisp65_rt_c2d_03)) }
        .lisp65_rt_c2d_03b { KEEP(*(.lisp65_rt_c2d_03b)) }
        .lisp65_rt_c2d_04 { KEEP(*(.lisp65_rt_c2d_04)) }
        .lisp65_rt_c2d_05a { KEEP(*(.lisp65_rt_c2d_05a)) }
        .lisp65_rt_c2d_05b { KEEP(*(.lisp65_rt_c2d_05b)) }
        .lisp65_rt_c2d_06a { KEEP(*(.lisp65_rt_c2d_06a)) }
        .lisp65_rt_c2d_06b { KEEP(*(.lisp65_rt_c2d_06b)) }
        .lisp65_rt_c2d_07 { KEEP(*(.lisp65_rt_c2d_07)) }
        .lisp65_rt_c2d_08 { KEEP(*(.lisp65_rt_c2d_08)) }
        .lisp65_rt_c2d_09 { KEEP(*(.lisp65_rt_c2d_09)) }
        .lisp65_rt_c2d_10 { KEEP(*(.lisp65_rt_c2d_10)) }
        .lisp65_rt_c2d_11a { KEEP(*(.lisp65_rt_c2d_11a)) }
        .lisp65_rt_c2d_11b { KEEP(*(.lisp65_rt_c2d_11b)) }
        .lisp65_rt_c2d_12 { KEEP(*(.lisp65_rt_c2d_12)) }
        .lisp65_rt_c2d_13 { KEEP(*(.lisp65_rt_c2d_13)) }
        .lisp65_rt_bank3_stage_session { KEEP(*(.lisp65_rt_bank3_stage_session)) }
        .lisp65_rt_c2emit_prepare { KEEP(*(.lisp65_rt_c2emit_prepare)) }
        .lisp65_rt_c2emit_name { KEEP(*(.lisp65_rt_c2emit_name)) }
        .lisp65_rt_c2emit_literal_prep { KEEP(*(.lisp65_rt_c2emit_literal_prep)) }
        .lisp65_rt_c2emit_literal_atom { KEEP(*(.lisp65_rt_c2emit_literal_atom)) }
        .lisp65_rt_c2emit_literal_append { KEEP(*(.lisp65_rt_c2emit_literal_append)) }
        .lisp65_rt_c2emit_code { KEEP(*(.lisp65_rt_c2emit_code)) }
        .lisp65_rt_c2emit_final_meta { KEEP(*(.lisp65_rt_c2emit_final_meta)) }
        .lisp65_rt_c2emit_final_crc { KEEP(*(.lisp65_rt_c2emit_final_crc)) }
        .lisp65_rt_c2append_envelope { KEEP(*(.lisp65_rt_c2append_envelope)) }
        .lisp65_rt_c2append_crc_metadata { KEEP(*(.lisp65_rt_c2append_crc_metadata)) }
        .lisp65_rt_c2append_roots_fronts { KEEP(*(.lisp65_rt_c2append_roots_fronts)) }
        .lisp65_rt_c2append_reserve_transient_bounds { KEEP(*(.lisp65_rt_c2append_reserve_transient_bounds)) }
        .lisp65_rt_c2append_reserve_transient_code { KEEP(*(.lisp65_rt_c2append_reserve_transient_code)) }
        .lisp65_rt_c2append_reserve_persistent_bounds { KEEP(*(.lisp65_rt_c2append_reserve_persistent_bounds)) }
        .lisp65_rt_c2append_reserve_persistent_code { KEEP(*(.lisp65_rt_c2append_reserve_persistent_code)) }
        .lisp65_rt_c2append_journal_prepare { KEEP(*(.lisp65_rt_c2append_journal_prepare)) }
        .lisp65_rt_c2append_journal_validate { KEEP(*(.lisp65_rt_c2append_journal_validate)) }
        .lisp65_rt_c2append_journal_reconstruct { KEEP(*(.lisp65_rt_c2append_journal_reconstruct)) }
        .lisp65_rt_c2append_stage_copy { KEEP(*(.lisp65_rt_c2append_stage_copy)) }
        .lisp65_rt_c2append_stage_plane { KEEP(*(.lisp65_rt_c2append_stage_plane)) }
        .lisp65_rt_c2append_image { KEEP(*(.lisp65_rt_c2append_image)) }
        .lisp65_rt_c2append_entries { KEEP(*(.lisp65_rt_c2append_entries)) }
        .lisp65_rt_c2append_publish_plan_scan { KEEP(*(.lisp65_rt_c2append_publish_plan_scan)) }
        .lisp65_rt_c2append_publish_plan_resolve { KEEP(*(.lisp65_rt_c2append_publish_plan_resolve)) }
        .lisp65_rt_c2append_header { KEEP(*(.lisp65_rt_c2append_header)) }
        .lisp65_rt_c2append_publish_clear { KEEP(*(.lisp65_rt_c2append_publish_clear)) }
        .lisp65_rt_c2append_rollback_unpublish { KEEP(*(.lisp65_rt_c2append_rollback_unpublish)) }
        .lisp65_rt_c2append_rollback_wipe_plane { KEEP(*(.lisp65_rt_c2append_rollback_wipe_plane)) }
        .lisp65_rt_c2append_rollback_wipe_chip { KEEP(*(.lisp65_rt_c2append_rollback_wipe_chip)) }
        .lisp65_rt_c2append_rollback_wipe_attic { KEEP(*(.lisp65_rt_c2append_rollback_wipe_attic)) }
        .lisp65_rt_c2append_rollback_finalize { KEEP(*(.lisp65_rt_c2append_rollback_finalize)) }
        .lisp65_rt_c2append_abort_control { KEEP(*(.lisp65_rt_c2append_abort_control)) }
        .lisp65_rt_l65e { KEEP(*(.lisp65_rt_l65e)) KEEP(*(.lisp65_rt_l65e_data)) }
        .lisp65_rt_island_00 { KEEP(*(.lisp65_rt_island_00)) KEEP(*(.lisp65_rt_island_00_data)) }
        .lisp65_rt_buffer_read { KEEP(*(.lisp65_rt_buffer_read)) }
        .lisp65_rt_buffer_write { KEEP(*(.lisp65_rt_buffer_write)) }
        .lisp65_rt_buffer_alloc { KEEP(*(.lisp65_rt_buffer_alloc)) }
        .lisp65_rt_intern_service { KEEP(*(.lisp65_rt_intern_service)) }
    } >ram
} INSERT AFTER .noinit;

__lisp65_resident_island_seed_lma =
    ALIGN(LOADADDR(.lisp65_rt_intern_service) + SIZEOF(.lisp65_rt_intern_service), 0x100);

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
__lisp65_workbench_overlay_len = SIZEOF(.lisp65_workbench_overlay);
__lisp65_boot_bank3_stage_start = ADDR(.lisp65_boot_bank3_stage); __lisp65_boot_bank3_stage_end = ADDR(.lisp65_boot_bank3_stage) + SIZEOF(.lisp65_boot_bank3_stage);
__lisp65_rt_bank3_stage_session_start = ADDR(.lisp65_rt_bank3_stage_session); __lisp65_rt_bank3_stage_session_end = ADDR(.lisp65_rt_bank3_stage_session) + SIZEOF(.lisp65_rt_bank3_stage_session);
__lisp65_rt_rtov_catalog_start = ADDR(.lisp65_rt_rtov_catalog); __lisp65_rt_rtov_catalog_end = ADDR(.lisp65_rt_rtov_catalog) + SIZEOF(.lisp65_rt_rtov_catalog);
__lisp65_rt_rtov_record_start = ADDR(.lisp65_rt_rtov_record); __lisp65_rt_rtov_record_end = ADDR(.lisp65_rt_rtov_record) + SIZEOF(.lisp65_rt_rtov_record);
__lisp65_rt_c2d_00_start = ADDR(.lisp65_rt_c2d_00); __lisp65_rt_c2d_00_end = ADDR(.lisp65_rt_c2d_00) + SIZEOF(.lisp65_rt_c2d_00);
__lisp65_rt_c2d_00b_start = ADDR(.lisp65_rt_c2d_00b); __lisp65_rt_c2d_00b_end = ADDR(.lisp65_rt_c2d_00b) + SIZEOF(.lisp65_rt_c2d_00b);
__lisp65_rt_c2d_01_start = ADDR(.lisp65_rt_c2d_01); __lisp65_rt_c2d_01_end = ADDR(.lisp65_rt_c2d_01) + SIZEOF(.lisp65_rt_c2d_01);
__lisp65_rt_c2d_02a_start = ADDR(.lisp65_rt_c2d_02a); __lisp65_rt_c2d_02a_end = ADDR(.lisp65_rt_c2d_02a) + SIZEOF(.lisp65_rt_c2d_02a);
__lisp65_rt_c2d_02b_start = ADDR(.lisp65_rt_c2d_02b); __lisp65_rt_c2d_02b_end = ADDR(.lisp65_rt_c2d_02b) + SIZEOF(.lisp65_rt_c2d_02b);
__lisp65_rt_c2d_03_start = ADDR(.lisp65_rt_c2d_03); __lisp65_rt_c2d_03_end = ADDR(.lisp65_rt_c2d_03) + SIZEOF(.lisp65_rt_c2d_03);
__lisp65_rt_c2d_03b_start = ADDR(.lisp65_rt_c2d_03b); __lisp65_rt_c2d_03b_end = ADDR(.lisp65_rt_c2d_03b) + SIZEOF(.lisp65_rt_c2d_03b);
__lisp65_rt_c2d_04_start = ADDR(.lisp65_rt_c2d_04); __lisp65_rt_c2d_04_end = ADDR(.lisp65_rt_c2d_04) + SIZEOF(.lisp65_rt_c2d_04);
__lisp65_rt_c2d_05a_start = ADDR(.lisp65_rt_c2d_05a); __lisp65_rt_c2d_05a_end = ADDR(.lisp65_rt_c2d_05a) + SIZEOF(.lisp65_rt_c2d_05a);
__lisp65_rt_c2d_05b_start = ADDR(.lisp65_rt_c2d_05b); __lisp65_rt_c2d_05b_end = ADDR(.lisp65_rt_c2d_05b) + SIZEOF(.lisp65_rt_c2d_05b);
__lisp65_rt_c2d_06a_start = ADDR(.lisp65_rt_c2d_06a); __lisp65_rt_c2d_06a_end = ADDR(.lisp65_rt_c2d_06a) + SIZEOF(.lisp65_rt_c2d_06a);
__lisp65_rt_c2d_06b_start = ADDR(.lisp65_rt_c2d_06b); __lisp65_rt_c2d_06b_end = ADDR(.lisp65_rt_c2d_06b) + SIZEOF(.lisp65_rt_c2d_06b);
__lisp65_rt_c2d_07_start = ADDR(.lisp65_rt_c2d_07); __lisp65_rt_c2d_07_end = ADDR(.lisp65_rt_c2d_07) + SIZEOF(.lisp65_rt_c2d_07);
__lisp65_rt_c2d_08_start = ADDR(.lisp65_rt_c2d_08); __lisp65_rt_c2d_08_end = ADDR(.lisp65_rt_c2d_08) + SIZEOF(.lisp65_rt_c2d_08);
__lisp65_rt_c2d_09_start = ADDR(.lisp65_rt_c2d_09); __lisp65_rt_c2d_09_end = ADDR(.lisp65_rt_c2d_09) + SIZEOF(.lisp65_rt_c2d_09);
__lisp65_rt_c2d_10_start = ADDR(.lisp65_rt_c2d_10); __lisp65_rt_c2d_10_end = ADDR(.lisp65_rt_c2d_10) + SIZEOF(.lisp65_rt_c2d_10);
__lisp65_rt_c2d_11a_start = ADDR(.lisp65_rt_c2d_11a); __lisp65_rt_c2d_11a_end = ADDR(.lisp65_rt_c2d_11a) + SIZEOF(.lisp65_rt_c2d_11a);
__lisp65_rt_c2d_11b_start = ADDR(.lisp65_rt_c2d_11b); __lisp65_rt_c2d_11b_end = ADDR(.lisp65_rt_c2d_11b) + SIZEOF(.lisp65_rt_c2d_11b);
__lisp65_rt_c2d_12_start = ADDR(.lisp65_rt_c2d_12); __lisp65_rt_c2d_12_end = ADDR(.lisp65_rt_c2d_12) + SIZEOF(.lisp65_rt_c2d_12);
__lisp65_rt_c2d_13_start = ADDR(.lisp65_rt_c2d_13); __lisp65_rt_c2d_13_end = ADDR(.lisp65_rt_c2d_13) + SIZEOF(.lisp65_rt_c2d_13);
__lisp65_rt_c2emit_prepare_start = ADDR(.lisp65_rt_c2emit_prepare); __lisp65_rt_c2emit_prepare_end = ADDR(.lisp65_rt_c2emit_prepare) + SIZEOF(.lisp65_rt_c2emit_prepare);
__lisp65_rt_c2emit_name_start = ADDR(.lisp65_rt_c2emit_name); __lisp65_rt_c2emit_name_end = ADDR(.lisp65_rt_c2emit_name) + SIZEOF(.lisp65_rt_c2emit_name);
__lisp65_rt_c2emit_literal_prep_start = ADDR(.lisp65_rt_c2emit_literal_prep); __lisp65_rt_c2emit_literal_prep_end = ADDR(.lisp65_rt_c2emit_literal_prep) + SIZEOF(.lisp65_rt_c2emit_literal_prep);
__lisp65_rt_c2emit_literal_atom_start = ADDR(.lisp65_rt_c2emit_literal_atom); __lisp65_rt_c2emit_literal_atom_end = ADDR(.lisp65_rt_c2emit_literal_atom) + SIZEOF(.lisp65_rt_c2emit_literal_atom);
__lisp65_rt_c2emit_literal_append_start = ADDR(.lisp65_rt_c2emit_literal_append); __lisp65_rt_c2emit_literal_append_end = ADDR(.lisp65_rt_c2emit_literal_append) + SIZEOF(.lisp65_rt_c2emit_literal_append);
__lisp65_rt_c2emit_code_start = ADDR(.lisp65_rt_c2emit_code); __lisp65_rt_c2emit_code_end = ADDR(.lisp65_rt_c2emit_code) + SIZEOF(.lisp65_rt_c2emit_code);
__lisp65_rt_c2emit_final_meta_start = ADDR(.lisp65_rt_c2emit_final_meta); __lisp65_rt_c2emit_final_meta_end = ADDR(.lisp65_rt_c2emit_final_meta) + SIZEOF(.lisp65_rt_c2emit_final_meta);
__lisp65_rt_c2emit_final_crc_start = ADDR(.lisp65_rt_c2emit_final_crc); __lisp65_rt_c2emit_final_crc_end = ADDR(.lisp65_rt_c2emit_final_crc) + SIZEOF(.lisp65_rt_c2emit_final_crc);
__lisp65_rt_c2append_envelope_start = ADDR(.lisp65_rt_c2append_envelope); __lisp65_rt_c2append_envelope_end = ADDR(.lisp65_rt_c2append_envelope) + SIZEOF(.lisp65_rt_c2append_envelope);
__lisp65_rt_c2append_crc_metadata_start = ADDR(.lisp65_rt_c2append_crc_metadata); __lisp65_rt_c2append_crc_metadata_end = ADDR(.lisp65_rt_c2append_crc_metadata) + SIZEOF(.lisp65_rt_c2append_crc_metadata);
__lisp65_rt_c2append_roots_fronts_start = ADDR(.lisp65_rt_c2append_roots_fronts); __lisp65_rt_c2append_roots_fronts_end = ADDR(.lisp65_rt_c2append_roots_fronts) + SIZEOF(.lisp65_rt_c2append_roots_fronts);
__lisp65_rt_c2append_reserve_transient_bounds_start = ADDR(.lisp65_rt_c2append_reserve_transient_bounds); __lisp65_rt_c2append_reserve_transient_bounds_end = ADDR(.lisp65_rt_c2append_reserve_transient_bounds) + SIZEOF(.lisp65_rt_c2append_reserve_transient_bounds);
__lisp65_rt_c2append_reserve_transient_code_start = ADDR(.lisp65_rt_c2append_reserve_transient_code); __lisp65_rt_c2append_reserve_transient_code_end = ADDR(.lisp65_rt_c2append_reserve_transient_code) + SIZEOF(.lisp65_rt_c2append_reserve_transient_code);
__lisp65_rt_c2append_reserve_persistent_bounds_start = ADDR(.lisp65_rt_c2append_reserve_persistent_bounds); __lisp65_rt_c2append_reserve_persistent_bounds_end = ADDR(.lisp65_rt_c2append_reserve_persistent_bounds) + SIZEOF(.lisp65_rt_c2append_reserve_persistent_bounds);
__lisp65_rt_c2append_reserve_persistent_code_start = ADDR(.lisp65_rt_c2append_reserve_persistent_code); __lisp65_rt_c2append_reserve_persistent_code_end = ADDR(.lisp65_rt_c2append_reserve_persistent_code) + SIZEOF(.lisp65_rt_c2append_reserve_persistent_code);
__lisp65_rt_c2append_journal_prepare_start = ADDR(.lisp65_rt_c2append_journal_prepare); __lisp65_rt_c2append_journal_prepare_end = ADDR(.lisp65_rt_c2append_journal_prepare) + SIZEOF(.lisp65_rt_c2append_journal_prepare);
__lisp65_rt_c2append_journal_validate_start = ADDR(.lisp65_rt_c2append_journal_validate); __lisp65_rt_c2append_journal_validate_end = ADDR(.lisp65_rt_c2append_journal_validate) + SIZEOF(.lisp65_rt_c2append_journal_validate);
__lisp65_rt_c2append_journal_reconstruct_start = ADDR(.lisp65_rt_c2append_journal_reconstruct); __lisp65_rt_c2append_journal_reconstruct_end = ADDR(.lisp65_rt_c2append_journal_reconstruct) + SIZEOF(.lisp65_rt_c2append_journal_reconstruct);
__lisp65_rt_c2append_stage_copy_start = ADDR(.lisp65_rt_c2append_stage_copy); __lisp65_rt_c2append_stage_copy_end = ADDR(.lisp65_rt_c2append_stage_copy) + SIZEOF(.lisp65_rt_c2append_stage_copy);
__lisp65_rt_c2append_stage_plane_start = ADDR(.lisp65_rt_c2append_stage_plane); __lisp65_rt_c2append_stage_plane_end = ADDR(.lisp65_rt_c2append_stage_plane) + SIZEOF(.lisp65_rt_c2append_stage_plane);
__lisp65_rt_c2append_image_start = ADDR(.lisp65_rt_c2append_image); __lisp65_rt_c2append_image_end = ADDR(.lisp65_rt_c2append_image) + SIZEOF(.lisp65_rt_c2append_image);
__lisp65_rt_c2append_entries_start = ADDR(.lisp65_rt_c2append_entries); __lisp65_rt_c2append_entries_end = ADDR(.lisp65_rt_c2append_entries) + SIZEOF(.lisp65_rt_c2append_entries);
__lisp65_rt_c2append_publish_plan_scan_start = ADDR(.lisp65_rt_c2append_publish_plan_scan); __lisp65_rt_c2append_publish_plan_scan_end = ADDR(.lisp65_rt_c2append_publish_plan_scan) + SIZEOF(.lisp65_rt_c2append_publish_plan_scan);
__lisp65_rt_c2append_publish_plan_resolve_start = ADDR(.lisp65_rt_c2append_publish_plan_resolve); __lisp65_rt_c2append_publish_plan_resolve_end = ADDR(.lisp65_rt_c2append_publish_plan_resolve) + SIZEOF(.lisp65_rt_c2append_publish_plan_resolve);
__lisp65_rt_c2append_header_start = ADDR(.lisp65_rt_c2append_header); __lisp65_rt_c2append_header_end = ADDR(.lisp65_rt_c2append_header) + SIZEOF(.lisp65_rt_c2append_header);
__lisp65_rt_c2append_publish_clear_start = ADDR(.lisp65_rt_c2append_publish_clear); __lisp65_rt_c2append_publish_clear_end = ADDR(.lisp65_rt_c2append_publish_clear) + SIZEOF(.lisp65_rt_c2append_publish_clear);
__lisp65_rt_c2append_rollback_unpublish_start = ADDR(.lisp65_rt_c2append_rollback_unpublish); __lisp65_rt_c2append_rollback_unpublish_end = ADDR(.lisp65_rt_c2append_rollback_unpublish) + SIZEOF(.lisp65_rt_c2append_rollback_unpublish);
__lisp65_rt_c2append_rollback_wipe_plane_start = ADDR(.lisp65_rt_c2append_rollback_wipe_plane); __lisp65_rt_c2append_rollback_wipe_plane_end = ADDR(.lisp65_rt_c2append_rollback_wipe_plane) + SIZEOF(.lisp65_rt_c2append_rollback_wipe_plane);
__lisp65_rt_c2append_rollback_wipe_chip_start = ADDR(.lisp65_rt_c2append_rollback_wipe_chip); __lisp65_rt_c2append_rollback_wipe_chip_end = ADDR(.lisp65_rt_c2append_rollback_wipe_chip) + SIZEOF(.lisp65_rt_c2append_rollback_wipe_chip);
__lisp65_rt_c2append_rollback_wipe_attic_start = ADDR(.lisp65_rt_c2append_rollback_wipe_attic); __lisp65_rt_c2append_rollback_wipe_attic_end = ADDR(.lisp65_rt_c2append_rollback_wipe_attic) + SIZEOF(.lisp65_rt_c2append_rollback_wipe_attic);
__lisp65_rt_c2append_rollback_finalize_start = ADDR(.lisp65_rt_c2append_rollback_finalize); __lisp65_rt_c2append_rollback_finalize_end = ADDR(.lisp65_rt_c2append_rollback_finalize) + SIZEOF(.lisp65_rt_c2append_rollback_finalize);
__lisp65_rt_c2append_abort_control_start = ADDR(.lisp65_rt_c2append_abort_control); __lisp65_rt_c2append_abort_control_end = ADDR(.lisp65_rt_c2append_abort_control) + SIZEOF(.lisp65_rt_c2append_abort_control);
__lisp65_rt_l65e_start = ADDR(.lisp65_rt_l65e); __lisp65_rt_l65e_end = ADDR(.lisp65_rt_l65e) + SIZEOF(.lisp65_rt_l65e);
__lisp65_rt_buffer_read_start = ADDR(.lisp65_rt_buffer_read); __lisp65_rt_buffer_read_end = ADDR(.lisp65_rt_buffer_read) + SIZEOF(.lisp65_rt_buffer_read);
__lisp65_rt_buffer_write_start = ADDR(.lisp65_rt_buffer_write); __lisp65_rt_buffer_write_end = ADDR(.lisp65_rt_buffer_write) + SIZEOF(.lisp65_rt_buffer_write);
__lisp65_rt_buffer_alloc_start = ADDR(.lisp65_rt_buffer_alloc); __lisp65_rt_buffer_alloc_end = ADDR(.lisp65_rt_buffer_alloc) + SIZEOF(.lisp65_rt_buffer_alloc);
__lisp65_rt_intern_service_start = ADDR(.lisp65_rt_intern_service); __lisp65_rt_intern_service_end = ADDR(.lisp65_rt_intern_service) + SIZEOF(.lisp65_rt_intern_service);
__lisp65_resident_island_start = ADDR(.lisp65_resident_island); __lisp65_resident_island_end = ADDR(.lisp65_resident_island) + SIZEOF(.lisp65_resident_island);
__lisp65_resident_island_annex_start = ADDR(.lisp65_resident_island_annex); __lisp65_resident_island_annex_end = ADDR(.lisp65_resident_island_annex) + SIZEOF(.lisp65_resident_island_annex);
__lisp65_rt_island_00_start = ADDR(.lisp65_rt_island_00); __lisp65_rt_island_00_end = ADDR(.lisp65_rt_island_00) + SIZEOF(.lisp65_rt_island_00);
__lisp65_boot_bank3_stage_entry = vm_bank3_boot_stage_entry;
__lisp65_rt_bank3_stage_session_entry = c2_lite_stage_session_family;
__lisp65_rt_rtov_catalog_entry = vm_runtime_overlay_catalog_verifier;
__lisp65_rt_rtov_record_entry = vm_runtime_overlay_record_verifier;
__lisp65_rt_c2d_00_entry = c2_stream_phase_00;
__lisp65_rt_c2d_00b_entry = c2_stream_phase_00b;
__lisp65_rt_c2d_01_entry = c2_stream_phase_01;
__lisp65_rt_c2d_02a_entry = c2_stream_phase_02a;
__lisp65_rt_c2d_02b_entry = c2_stream_phase_02b;
__lisp65_rt_c2d_03_entry = c2_stream_phase_03;
__lisp65_rt_c2d_03b_entry = c2_stream_phase_03b;
__lisp65_rt_c2d_04_entry = c2_stream_phase_04;
__lisp65_rt_c2d_05a_entry = c2_stream_phase_05a;
__lisp65_rt_c2d_05b_entry = c2_stream_phase_05b;
__lisp65_rt_c2d_06a_entry = c2_stream_phase_06a;
__lisp65_rt_c2d_06b_entry = c2_stream_phase_06b;
__lisp65_rt_c2d_07_entry = c2_stream_phase_07;
__lisp65_rt_c2d_08_entry = c2_stream_phase_08;
__lisp65_rt_c2d_09_entry = c2_stream_phase_09;
__lisp65_rt_c2d_10_entry = c2_stream_phase_10;
__lisp65_rt_c2d_11a_entry = c2_stream_phase_11a;
__lisp65_rt_c2d_11b_entry = c2_stream_phase_11b;
__lisp65_rt_c2d_12_entry = c2_stream_phase_12;
__lisp65_rt_c2d_13_entry = c2_stream_phase_13;
__lisp65_rt_c2emit_prepare_entry = c2_session_emit_prepare_phase;
__lisp65_rt_c2emit_name_entry = c2_session_emit_name_phase;
__lisp65_rt_c2emit_literal_prep_entry = c2_session_emit_literal_prep_phase;
__lisp65_rt_c2emit_literal_atom_entry = c2_session_emit_literal_atom_phase;
__lisp65_rt_c2emit_literal_append_entry = c2_session_emit_literal_append_phase;
__lisp65_rt_c2emit_code_entry = c2_session_emit_code_phase;
__lisp65_rt_c2emit_final_meta_entry = c2_session_emit_final_meta_phase;
__lisp65_rt_c2emit_final_crc_entry = c2_session_emit_final_crc_phase;
__lisp65_rt_c2append_envelope_entry = c2_append_envelope_phase;
__lisp65_rt_c2append_crc_metadata_entry = c2_append_crc_metadata_phase;
__lisp65_rt_c2append_roots_fronts_entry = c2_append_roots_fronts_phase;
__lisp65_rt_c2append_reserve_transient_bounds_entry = c2_append_reserve_transient_bounds_phase;
__lisp65_rt_c2append_reserve_transient_code_entry = c2_append_reserve_transient_code_phase;
__lisp65_rt_c2append_reserve_persistent_bounds_entry = c2_append_reserve_persistent_bounds_phase;
__lisp65_rt_c2append_reserve_persistent_code_entry = c2_append_reserve_persistent_code_phase;
__lisp65_rt_c2append_journal_prepare_entry = c2_append_journal_prepare_phase;
__lisp65_rt_c2append_journal_validate_entry = c2_append_journal_validate_phase;
__lisp65_rt_c2append_journal_reconstruct_entry = c2_append_journal_reconstruct_phase;
__lisp65_rt_c2append_stage_copy_entry = c2_append_stage_copy_phase;
__lisp65_rt_c2append_stage_plane_entry = c2_append_stage_plane_phase;
__lisp65_rt_c2append_image_entry = c2_append_image_phase;
__lisp65_rt_c2append_entries_entry = c2_append_entries_phase;
__lisp65_rt_c2append_publish_plan_scan_entry = c2_append_publish_plan_scan_phase;
__lisp65_rt_c2append_publish_plan_resolve_entry = c2_append_publish_plan_resolve_phase;
__lisp65_rt_c2append_header_entry = c2_append_header_phase;
__lisp65_rt_c2append_publish_clear_entry = c2_append_publish_clear_phase;
__lisp65_rt_c2append_rollback_unpublish_entry = c2_append_rollback_unpublish_phase;
__lisp65_rt_c2append_rollback_wipe_plane_entry = c2_append_rollback_wipe_plane_phase;
__lisp65_rt_c2append_rollback_wipe_chip_entry = c2_append_rollback_wipe_chip_phase;
__lisp65_rt_c2append_rollback_wipe_attic_entry = c2_append_rollback_wipe_attic_phase;
__lisp65_rt_c2append_rollback_finalize_entry = c2_append_rollback_finalize_phase;
__lisp65_rt_c2append_abort_control_entry = c2_append_abort_control_phase;
__lisp65_rt_l65e_entry = lisp65_error_overlay_entry;
__lisp65_rt_buffer_read_entry = lisp65_buffer_overlay_read_entry;
__lisp65_rt_buffer_write_entry = lisp65_buffer_overlay_write_entry;
__lisp65_rt_buffer_alloc_entry = lisp65_buffer_overlay_alloc_entry;
__lisp65_rt_intern_service_entry = lisp65_intern_service_entry;
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
ASSERT(SIZEOF(.lisp65_boot_bank3_stage) > 0 && SIZEOF(.lisp65_boot_bank3_stage) <= 1792 && __lisp65_boot_bank3_stage_end <= __lisp65_workbench_runtime_overlay_limit, "Bank-3 pre-family stage record exceeds its stack-safe window");
ASSERT(__lisp65_boot_bank3_stage_entry >= __lisp65_boot_bank3_stage_start + 18 && __lisp65_boot_bank3_stage_entry < __lisp65_boot_bank3_stage_end, "Bank-3 pre-family stage entry escaped its descriptor-safe record body");
ASSERT(SIZEOF(.lisp65_rt_bank3_stage_session) > 0 && SIZEOF(.lisp65_rt_bank3_stage_session) <= 1792 && __lisp65_rt_bank3_stage_session_end <= __lisp65_workbench_runtime_overlay_limit, "Bank-3 Session stage slice exceeds its stack-safe window");
ASSERT(__lisp65_rt_bank3_stage_session_entry >= __lisp65_rt_bank3_stage_session_start && __lisp65_rt_bank3_stage_session_entry < __lisp65_rt_bank3_stage_session_end, "Bank-3 Session stage entry escaped its slice");
ASSERT(SIZEOF(.lisp65_rt_rtov_catalog) > 0 && SIZEOF(.lisp65_rt_rtov_catalog) <= 1792 && __lisp65_rt_rtov_catalog_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay catalog verifier exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_rtov_record) > 0 && SIZEOF(.lisp65_rt_rtov_record) <= 1792 && __lisp65_rt_rtov_record_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay record verifier exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_00) > 0 && SIZEOF(.lisp65_rt_c2d_00) <= 1792 && __lisp65_rt_c2d_00_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 00 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_00b) > 0 && SIZEOF(.lisp65_rt_c2d_00b) <= 1792 && __lisp65_rt_c2d_00b_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 00b exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_01) > 0 && SIZEOF(.lisp65_rt_c2d_01) <= 1792 && __lisp65_rt_c2d_01_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 01 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_02a) > 0 && SIZEOF(.lisp65_rt_c2d_02a) <= 1792 && __lisp65_rt_c2d_02a_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 02a exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_02b) > 0 && SIZEOF(.lisp65_rt_c2d_02b) <= 1792 && __lisp65_rt_c2d_02b_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 02b exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_03) > 0 && SIZEOF(.lisp65_rt_c2d_03) <= 1792 && __lisp65_rt_c2d_03_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 03 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_03b) > 0 && SIZEOF(.lisp65_rt_c2d_03b) <= 1792 && __lisp65_rt_c2d_03b_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 03b exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_04) > 0 && SIZEOF(.lisp65_rt_c2d_04) <= 1792 && __lisp65_rt_c2d_04_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 04 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_05a) > 0 && SIZEOF(.lisp65_rt_c2d_05a) <= 1792 && __lisp65_rt_c2d_05a_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 05a exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_05b) > 0 && SIZEOF(.lisp65_rt_c2d_05b) <= 1792 && __lisp65_rt_c2d_05b_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 05b exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_06a) > 0 && SIZEOF(.lisp65_rt_c2d_06a) <= 1792 && __lisp65_rt_c2d_06a_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 06a exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_06b) > 0 && SIZEOF(.lisp65_rt_c2d_06b) <= 1792 && __lisp65_rt_c2d_06b_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 06b exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_07) > 0 && SIZEOF(.lisp65_rt_c2d_07) <= 1792 && __lisp65_rt_c2d_07_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 07 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_08) > 0 && SIZEOF(.lisp65_rt_c2d_08) <= 1792 && __lisp65_rt_c2d_08_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 08 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_09) > 0 && SIZEOF(.lisp65_rt_c2d_09) <= 1792 && __lisp65_rt_c2d_09_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 09 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_10) > 0 && SIZEOF(.lisp65_rt_c2d_10) <= 1792 && __lisp65_rt_c2d_10_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 10 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_11a) > 0 && SIZEOF(.lisp65_rt_c2d_11a) <= 1792 && __lisp65_rt_c2d_11a_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 11a exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_11b) > 0 && SIZEOF(.lisp65_rt_c2d_11b) <= 1792 && __lisp65_rt_c2d_11b_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 11b exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_12) > 0 && SIZEOF(.lisp65_rt_c2d_12) <= 1792 && __lisp65_rt_c2d_12_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 12 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2d_13) > 0 && SIZEOF(.lisp65_rt_c2d_13) <= 1792 && __lisp65_rt_c2d_13_end <= __lisp65_workbench_runtime_overlay_limit, "C2 decoder phase 13 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2emit_prepare) > 0 && SIZEOF(.lisp65_rt_c2emit_prepare) <= 1792 && __lisp65_rt_c2emit_prepare_end <= __lisp65_workbench_runtime_overlay_limit, "C2 emitter phase prepare exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2emit_name) > 0 && SIZEOF(.lisp65_rt_c2emit_name) <= 1792 && __lisp65_rt_c2emit_name_end <= __lisp65_workbench_runtime_overlay_limit, "C2 emitter phase name exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2emit_literal_prep) > 0 && SIZEOF(.lisp65_rt_c2emit_literal_prep) <= 1792 && __lisp65_rt_c2emit_literal_prep_end <= __lisp65_workbench_runtime_overlay_limit, "C2 emitter phase literal_prep exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2emit_literal_atom) > 0 && SIZEOF(.lisp65_rt_c2emit_literal_atom) <= 1792 && __lisp65_rt_c2emit_literal_atom_end <= __lisp65_workbench_runtime_overlay_limit, "C2 emitter phase literal_atom exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2emit_literal_append) > 0 && SIZEOF(.lisp65_rt_c2emit_literal_append) <= 1792 && __lisp65_rt_c2emit_literal_append_end <= __lisp65_workbench_runtime_overlay_limit, "C2 emitter phase literal_append exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2emit_code) > 0 && SIZEOF(.lisp65_rt_c2emit_code) <= 1792 && __lisp65_rt_c2emit_code_end <= __lisp65_workbench_runtime_overlay_limit, "C2 emitter phase code exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2emit_final_meta) > 0 && SIZEOF(.lisp65_rt_c2emit_final_meta) <= 1792 && __lisp65_rt_c2emit_final_meta_end <= __lisp65_workbench_runtime_overlay_limit, "C2 emitter phase final_meta exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2emit_final_crc) > 0 && SIZEOF(.lisp65_rt_c2emit_final_crc) <= 1792 && __lisp65_rt_c2emit_final_crc_end <= __lisp65_workbench_runtime_overlay_limit, "C2 emitter phase final_crc exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_envelope) > 0 && SIZEOF(.lisp65_rt_c2append_envelope) <= 1792 && __lisp65_rt_c2append_envelope_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase envelope exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_crc_metadata) > 0 && SIZEOF(.lisp65_rt_c2append_crc_metadata) <= 1792 && __lisp65_rt_c2append_crc_metadata_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase crc_metadata exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_roots_fronts) > 0 && SIZEOF(.lisp65_rt_c2append_roots_fronts) <= 1792 && __lisp65_rt_c2append_roots_fronts_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase roots_fronts exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_reserve_transient_bounds) > 0 && SIZEOF(.lisp65_rt_c2append_reserve_transient_bounds) <= 1792 && __lisp65_rt_c2append_reserve_transient_bounds_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase reserve_transient_bounds exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_reserve_transient_code) > 0 && SIZEOF(.lisp65_rt_c2append_reserve_transient_code) <= 1792 && __lisp65_rt_c2append_reserve_transient_code_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase reserve_transient_code exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_reserve_persistent_bounds) > 0 && SIZEOF(.lisp65_rt_c2append_reserve_persistent_bounds) <= 1792 && __lisp65_rt_c2append_reserve_persistent_bounds_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase reserve_persistent_bounds exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_reserve_persistent_code) > 0 && SIZEOF(.lisp65_rt_c2append_reserve_persistent_code) <= 1792 && __lisp65_rt_c2append_reserve_persistent_code_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase reserve_persistent_code exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_journal_prepare) > 0 && SIZEOF(.lisp65_rt_c2append_journal_prepare) <= 1792 && __lisp65_rt_c2append_journal_prepare_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase journal_prepare exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_journal_validate) > 0 && SIZEOF(.lisp65_rt_c2append_journal_validate) <= 1792 && __lisp65_rt_c2append_journal_validate_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase journal_validate exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_journal_reconstruct) > 0 && SIZEOF(.lisp65_rt_c2append_journal_reconstruct) <= 1792 && __lisp65_rt_c2append_journal_reconstruct_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase journal_reconstruct exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_stage_copy) > 0 && SIZEOF(.lisp65_rt_c2append_stage_copy) <= 1792 && __lisp65_rt_c2append_stage_copy_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase stage_copy exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_stage_plane) > 0 && SIZEOF(.lisp65_rt_c2append_stage_plane) <= 1792 && __lisp65_rt_c2append_stage_plane_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase stage_plane exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_image) > 0 && SIZEOF(.lisp65_rt_c2append_image) <= 1792 && __lisp65_rt_c2append_image_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase image exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_entries) > 0 && SIZEOF(.lisp65_rt_c2append_entries) <= 1792 && __lisp65_rt_c2append_entries_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase entries exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_publish_plan_scan) > 0 && SIZEOF(.lisp65_rt_c2append_publish_plan_scan) <= 1792 && __lisp65_rt_c2append_publish_plan_scan_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase publish_plan_scan exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_publish_plan_resolve) > 0 && SIZEOF(.lisp65_rt_c2append_publish_plan_resolve) <= 1792 && __lisp65_rt_c2append_publish_plan_resolve_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase publish_plan_resolve exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_header) > 0 && SIZEOF(.lisp65_rt_c2append_header) <= 1792 && __lisp65_rt_c2append_header_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase header exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_publish_clear) > 0 && SIZEOF(.lisp65_rt_c2append_publish_clear) <= 1792 && __lisp65_rt_c2append_publish_clear_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase publish_clear exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_rollback_unpublish) > 0 && SIZEOF(.lisp65_rt_c2append_rollback_unpublish) <= 1792 && __lisp65_rt_c2append_rollback_unpublish_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase rollback_unpublish exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_rollback_wipe_plane) > 0 && SIZEOF(.lisp65_rt_c2append_rollback_wipe_plane) <= 1792 && __lisp65_rt_c2append_rollback_wipe_plane_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase rollback_wipe_plane exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_rollback_wipe_chip) > 0 && SIZEOF(.lisp65_rt_c2append_rollback_wipe_chip) <= 1792 && __lisp65_rt_c2append_rollback_wipe_chip_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase rollback_wipe_chip exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_rollback_wipe_attic) > 0 && SIZEOF(.lisp65_rt_c2append_rollback_wipe_attic) <= 1792 && __lisp65_rt_c2append_rollback_wipe_attic_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase rollback_wipe_attic exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_rollback_finalize) > 0 && SIZEOF(.lisp65_rt_c2append_rollback_finalize) <= 1792 && __lisp65_rt_c2append_rollback_finalize_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase rollback_finalize exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c2append_abort_control) > 0 && SIZEOF(.lisp65_rt_c2append_abort_control) <= 1792 && __lisp65_rt_c2append_abort_control_end <= __lisp65_workbench_runtime_overlay_limit, "C2 append phase abort_control exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65e) > 0 && SIZEOF(.lisp65_rt_l65e) <= 1792 && __lisp65_rt_l65e_end <= __lisp65_workbench_runtime_overlay_limit, "L65E renderer exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65e) <= __lisp65_error_overlay_max_bytes, "L65E renderer exceeds its product budget");
ASSERT(SIZEOF(.lisp65_rt_buffer_read) > 0 && SIZEOF(.lisp65_rt_buffer_read) <= 1792 && __lisp65_rt_buffer_read_end <= __lisp65_workbench_runtime_overlay_limit, "buffer reader exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_buffer_write) > 0 && SIZEOF(.lisp65_rt_buffer_write) <= 1792 && __lisp65_rt_buffer_write_end <= __lisp65_workbench_runtime_overlay_limit, "buffer writer exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_buffer_alloc) > 0 && SIZEOF(.lisp65_rt_buffer_alloc) <= 1792 && __lisp65_rt_buffer_alloc_end <= __lisp65_workbench_runtime_overlay_limit, "buffer allocator exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_intern_service) > 0 && SIZEOF(.lisp65_rt_intern_service) <= 1792 && __lisp65_rt_intern_service_end <= __lisp65_workbench_runtime_overlay_limit, "intern Session service exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_island_00) > 0 && SIZEOF(.lisp65_rt_island_00) <= 4096 && __lisp65_rt_island_00_end <= __lisp65_workbench_boot_slice_limit, "boot overlay resident-island installer exceeds its 512-byte stack window");
ASSERT(SIZEOF(.lisp65_rt_island_00) <= 1792,
       "resident-island installer exceeds the product Slot-37 budget");

/* Four verifier tuples retain their historical
 * 32-byte prefix.  C2-lite Bank-3 staging appends two size/CRC tuples in the
 * same non-LTO publish-last section without renumbering the verifier ABI. */
ASSERT(SIZEOF(.lisp65_runtime_overlay_verifier_bindings) == 40 &&
       __lisp65_rtov_binding_section_end -
       __lisp65_rtov_binding_section_start == 40,
       "runtime-overlay publish-last binding table has the wrong width");
ASSERT(__lisp65_rtov_verifier_bindings_start ==
           __lisp65_rtov_binding_section_start &&
       rtov_boot_verifiers == __lisp65_rtov_binding_section_start &&
       rtov_verifiers == __lisp65_rtov_binding_section_start + 16 &&
       __lisp65_rtov_verifier_bindings_end ==
           __lisp65_rtov_binding_section_start + 32,
       "runtime-overlay verifier tuple order or labels drifted");

ASSERT(__lisp65_rtov_family_stage_bindings_start ==
           __lisp65_rtov_binding_section_start + 32 &&
       rtov_family_stage_bindings ==
           __lisp65_rtov_family_stage_bindings_start &&
       __lisp65_rtov_family_stage_bindings_end ==
           __lisp65_rtov_binding_section_end,
       "runtime-family stage binding order or labels drifted");
/* Product-resident handoff code is ordinary PRG material.  Name it here so
 * neither fixed-VMA artifact can capture an orphan section. */
SECTIONS {
    .lisp65_c2_kernal_handoff 0xb4a3 : AT(0xb4a3) {
        KEEP(*(.lisp65_c2_kernal_handoff))
    } >ram

    /* Four terminal-return wrappers address this physical interval directly.
     * Make that ownership visible to the linker instead of treating it as an
     * anonymous gap. */
    .lisp65_c2_terminal_return_raw_owner 0xb582 (NOLOAD) : {
        __lisp65_c2_terminal_return_raw_owner_start = .;
        . += 0x10;
        __lisp65_c2_terminal_return_raw_owner_end = .;
    } >ram


    .lisp65_symbol22_first_fault_latch 0xb592 :
        AT(0xb592) {
        KEEP(*(.lisp65_symbol22_first_fault_latch))
    } >ram

    .lisp65_c2_host_facade 0xb5c4 : AT(0xb5c4) {
        KEEP(*(.lisp65_c2_host_facade))
    } >ram
    .lisp65_c2_kernal_io_reveal 0xb5f4 : AT(0xb5f4) {
        KEEP(*(.lisp65_c2_kernal_io_reveal))
    } >ram
    .lisp65_c2_kernal_map_switch 0xb5ff : AT(0xb5ff) {
        KEEP(*(.lisp65_c2_kernal_map_switch))
    } >ram
    .lisp65_c2_kernal_state 0xb609 (NOLOAD) : {
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
        __lisp65_c2_fixed_bank0_code_rtov_fail = .;
        KEEP(*(.lisp65_c2_fixed_bank0_code.rtov_fail))
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
    .lisp65_c2_kernal_window.irq_handler
        ADDR(.lisp65_c2_kernal_window.typed_queue_driver) +
        SIZEOF(.lisp65_c2_kernal_window.typed_queue_driver) :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.irq_handler) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.irq_handler))
    } >c2_kernal_window
    .lisp65_c2_kernal_window.nmi_and_freezer_return
        ADDR(.lisp65_c2_kernal_window.irq_handler) +
        SIZEOF(.lisp65_c2_kernal_window.irq_handler) :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.nmi_and_freezer_return) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.nmi_and_freezer_return))
    } >c2_kernal_window
    .lisp65_c2_kernal_window.map_switch_and_guards
        ADDR(.lisp65_c2_kernal_window.nmi_and_freezer_return) +
        SIZEOF(.lisp65_c2_kernal_window.nmi_and_freezer_return) :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.map_switch_and_guards) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.map_switch_and_guards))
    } >c2_kernal_window
    .lisp65_c2_kernal_window.post_startup_output_seam
        ADDR(.lisp65_c2_kernal_window.map_switch_and_guards) +
        SIZEOF(.lisp65_c2_kernal_window.map_switch_and_guards) :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.post_startup_output_seam) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.post_startup_output_seam))
    } >c2_kernal_window
    .lisp65_c2_kernal_window.session_emitter_code
        ADDR(.lisp65_c2_kernal_window.post_startup_output_seam) +
        SIZEOF(.lisp65_c2_kernal_window.post_startup_output_seam) :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.session_emitter_code) - 0xe000) {
        __lisp65_c2_session_emitter_code_start = .;
        KEEP(*(.lisp65_c2_kernal_window.session_emitter_code))
        __lisp65_c2_session_emitter_code_end = .;
    } >c2_kernal_window
    .lisp65_c2_kernal_window.c2_resident
        ADDR(.lisp65_c2_kernal_window.session_emitter_code) +
        SIZEOF(.lisp65_c2_kernal_window.session_emitter_code) :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.c2_resident) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.c2_resident))
    } >c2_kernal_window
    .lisp65_c2_kernal_window.session_emitter_state 0xfd22 (NOLOAD) :
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

/* The complete v2 profile adds three immutable service-dispatch tables.  They
 * are post-ownership data, not ordinary Bank-0 state.  Match the three exact
 * input sections before the inherited generic .rodata wildcard can claim
 * them; no other constant becomes an implicit E000 tenant. */
SECTIONS {
    .lisp65_c2_kernal_window.profile_rodata 0xfd2c :
        AT(ORIGIN(c2_kernal_window_load) + 0x1d2c) {
        __lisp65_c2_profile_rodata_start = .;
        __lisp65_c2_profile_rodata_eval_start = .;
        KEEP(*(.rodata.eval_v2_workbench_service))
        __lisp65_c2_profile_rodata_eval_end = .;
        __lisp65_c2_profile_rodata_callprim_start = .;
        KEEP(*(.rodata.vm_callprim))
        . = MAX(., __lisp65_c2_profile_rodata_callprim_start + 168);
        __lisp65_c2_profile_rodata_callprim_end = .;
        __lisp65_c2_profile_rodata_native_start = .;
        KEEP(*(.rodata.vm_native_call))
        __lisp65_c2_profile_rodata_native_end = .;
        __lisp65_c2_profile_rodata_end = .;
    } >c2_kernal_window
} INSERT BEFORE .rodata;

ASSERT(ADDR(.basic_header) == 0x2001,
       "C2 load domains moved the product PRG header");

ASSERT(ADDR(.lisp65_c2_terminal_return_raw_owner) == 0xb582 &&
       SIZEOF(.lisp65_c2_terminal_return_raw_owner) == 16 &&
       __lisp65_c2_terminal_return_raw_owner_end <=
           ADDR(.lisp65_symbol22_first_fault_latch),
       "terminal-return fixed raw owner geometry drift");


ASSERT(ADDR(.lisp65_symbol22_first_fault_latch) ==
           0xb592 &&
       LOADADDR(.lisp65_symbol22_first_fault_latch) ==
           ADDR(.lisp65_symbol22_first_fault_latch) &&
       SIZEOF(.lisp65_symbol22_first_fault_latch) == 48 &&
       ADDR(.lisp65_symbol22_first_fault_latch) +
           SIZEOF(.lisp65_symbol22_first_fault_latch) <=
               ADDR(.lisp65_c2_host_facade),
       "symbol22 first-fault code escaped the derived raw-owner/facade gap");
ASSERT(ADDR(.lisp65_symbol22_first_fault_state) ==
           ADDR(.lisp65_c2_fixed_bank0_hot_bss) +
               SIZEOF(.lisp65_c2_fixed_bank0_hot_bss) &&
       LOADADDR(.lisp65_symbol22_first_fault_state) ==
           ADDR(.lisp65_symbol22_first_fault_state) &&
       SIZEOF(.lisp65_symbol22_first_fault_state) == 5 &&
       ADDR(.lisp65_symbol22_first_fault_state) +
           SIZEOF(.lisp65_symbol22_first_fault_state) <= __heap_start,
       "symbol22 first-fault state escaped the derived pre-heap gap");

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
       ADDR(.lisp65_c2_kernal_io_reveal) < 0xe000 &&
       ADDR(.lisp65_c2_kernal_map_switch) < 0xe000 &&
       ADDR(.lisp65_c2_kernal_state) < 0xe000,
       "C2 low-resident handoff escaped the PRG domain");
ASSERT(ADDR(.lisp65_c2_kernal_handoff) == 0xb4a3 &&
       ADDR(.lisp65_c2_kernal_handoff) + SIZEOF(.lisp65_c2_kernal_handoff) <= 0xb5c4,
       "C2 handoff overlaps the fixed host facade");
ASSERT(ADDR(.lisp65_c2_host_facade) == 0xb5c4 &&
       SIZEOF(.lisp65_c2_host_facade) == 48,
       "C2 fixed host-facade geometry drift");
ASSERT(c2_facade_vm_code_load == 0xb5c4 && c2_facade_c2_dma == 0xb5c7 &&
       c2_facade_overlay_call_family == 0xb5ca && c2_facade_c2e_cons == 0xb5cd &&
       c2_facade_c2e_overlay == 0xb5d0 && c2_facade_car == 0xb5d3 &&
       c2_facade_cdr == 0xb5d6 && c2_facade_gc_collect == 0xb5d9 &&
       c2_facade_str_open == 0xb5dc && c2_facade_str_putc == 0xb5df &&
       c2_facade_intern == 0xb5e2 && c2_facade_select_family == 0xb5e5 &&
       c2_facade_gc_mark == 0xb5e8 &&
       c2_facade_runtime_overlay_exec == 0xb5eb &&
       c2_facade_handle_normalize == 0xb5ee &&
       c2_facade_append_plan_walk == 0xb5f1,
       "C2 fixed host-facade vector address drift");
ASSERT(ADDR(.lisp65_c2_kernal_io_reveal) == 0xb5f4 &&
       SIZEOF(.lisp65_c2_kernal_io_reveal) == 11 &&
       c2_kernal_reveal_io == 0xb5f4 &&
       ADDR(.lisp65_c2_kernal_map_switch) == 0xb5ff &&
       SIZEOF(.lisp65_c2_kernal_map_switch) == 10 &&
       ADDR(.lisp65_c2_kernal_map_switch) +
           SIZEOF(.lisp65_c2_kernal_map_switch) <= 0xb609 &&
       ADDR(.lisp65_c2_kernal_state) == 0xb609,
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
       __lisp65_c2_fixed_bank0_code_start ==
           ADDR(.lisp65_c2_fixed_bank0_code) &&
       __lisp65_c2_fixed_bank0_code_kb_cursor_off ==
           __lisp65_c2_fixed_bank0_code_start &&
       __lisp65_c2_fixed_bank0_code_kb_cursor_off <=
           __lisp65_c2_fixed_bank0_code_c2e_cons &&
       __lisp65_c2_fixed_bank0_code_c2e_cons <=
           __lisp65_c2_fixed_bank0_code_rtov_fail &&
       __lisp65_c2_fixed_bank0_code_rtov_fail <=
           __lisp65_c2_fixed_bank0_code_end &&
       __lisp65_c2_fixed_bank0_code_end ==
           ADDR(.lisp65_c2_fixed_bank0_code) +
           SIZEOF(.lisp65_c2_fixed_bank0_code) &&
       __lisp65_c2_fixed_bank0_code_end <=
           ADDR(.lisp65_c2_fixed_bank0_hot_bss),
       "C2 fixed Bank-0 code escaped its derived member envelope");

ASSERT(ADDR(.lisp65_c2_kernal_window.c2_resident) +
       SIZEOF(.lisp65_c2_kernal_window.c2_resident) <= 0xff80,
       "C2-owned KERNAL-window residents overlap state");
ASSERT(SIZEOF(.lisp65_c2_kernal_window.session_emitter_code) == 0 &&
       SIZEOF(.lisp65_c2_kernal_window.session_emitter_state) == 0,
       "C2 session-only E000 residency geometry drift");
ASSERT(ADDR(.lisp65_c2_kernal_window.session_emitter_state) == 0xfd22 &&
       SIZEOF(.lisp65_c2_kernal_window.session_emitter_state) == 0 &&
       ADDR(.lisp65_c2_kernal_window.profile_rodata) == 0xfd2c,
       "C2 profile rodata is not adjacent to session state");
ASSERT(__lisp65_c2_profile_rodata_eval_end -
       __lisp65_c2_profile_rodata_eval_start == 32 &&
       __lisp65_c2_profile_rodata_callprim_end -
       __lisp65_c2_profile_rodata_callprim_start == 168 &&
       __lisp65_c2_profile_rodata_native_end -
       __lisp65_c2_profile_rodata_native_start == 148 &&
       SIZEOF(.lisp65_c2_kernal_window.profile_rodata) == 348,
       "C2 complete-profile immutable-data geometry drift");
ASSERT(ADDR(.lisp65_c2_kernal_window.profile_rodata) +
       SIZEOF(.lisp65_c2_kernal_window.profile_rodata) <= 0xff80,
       "C2 complete-profile immutable data overlaps owned state");
ASSERT(ADDR(.lisp65_c2_kernal_window.state) == 0xff80 &&
       SIZEOF(.lisp65_c2_kernal_window.state) == 16,
       "C2 KERNAL-window state geometry drift");
ASSERT(ADDR(.lisp65_c2_vectors) == 0xfffa && SIZEOF(.lisp65_c2_vectors) == 6,
       "C2 owned vector geometry drift");

/* Reset the inherited Bank-2 LMA delta at the existing resident PRG chain. */
ASSERT(LOADADDR(.lisp65_c2_kernal_handoff) == ADDR(.lisp65_c2_kernal_handoff),
       ".lisp65_c2_kernal_handoff escaped the resident PRG LMA chain");
ASSERT(LOADADDR(.lisp65_c2_host_facade) == ADDR(.lisp65_c2_host_facade),
       ".lisp65_c2_host_facade escaped the resident PRG LMA chain");
ASSERT(LOADADDR(.lisp65_c2_kernal_io_reveal) == ADDR(.lisp65_c2_kernal_io_reveal),
       ".lisp65_c2_kernal_io_reveal escaped the resident PRG LMA chain");
ASSERT(LOADADDR(.lisp65_c2_kernal_map_switch) == ADDR(.lisp65_c2_kernal_map_switch),
       ".lisp65_c2_kernal_map_switch escaped the resident PRG LMA chain");
/* Halt-1-selected stack/state/far-service owners.
 * Expected addresses live in the reviewed ownership contract; the permanent
 * gate compares this generated script and the final ELF against that
 * independent authority. */
SECTIONS {
    .lisp65_c2_convergence_zp 0x87 (NOLOAD) : {
        KEEP(*(.lisp65_c2_convergence_zp.*))
    } >zp
} INSERT AFTER .lisp65_c2_fixed_zp;

SECTIONS {
    .lisp65_c2_convergence_state 0xc000 (NOLOAD) : {
        KEEP(*(.lisp65_c2_convergence_state.*))
    } >ram
    .lisp65_c2_static_stack 0xc074 (NOLOAD) : {
        KEEP(*(.noinit..Lstatic_stack*))
    } >ram
} INSERT BEFORE .noinit;

SECTIONS {
    .lisp65_c2_mapped_far_facade MAX(0xb3b0, ADDR(.text) + SIZEOF(.text) + 32) : AT((MAX(0xb3b0, ADDR(.text) + SIZEOF(.text) + 32)) + (((0x00030000 - (0x7e8d + SIZEOF(.lisp65_c2_mapped_product_cold))) / 0x100 * 0x100))) {
        KEEP(*(.lisp65_c2_mapped_far_facade.entries))
        KEEP(*(.lisp65_c2_mapped_far_facade.abort))
        __lisp65_c2_mapped_far_facade_padding_start = .;
        KEEP(*(.lisp65_c2_mapped_far_facade.padding))
        __lisp65_c2_mapped_far_facade_padding_end = .;
        KEEP(*(.lisp65_c2_mapped_far_facade.*))
    } >ram

    .lisp65_c2_mapped_f011_cold (0x78b2 - SIZEOF(.lisp65_c2_mapped_f011_cold))
        : AT((((0x78b2 - SIZEOF(.lisp65_c2_mapped_f011_cold))) + (((0x00030000 - (0x7e8d + SIZEOF(.lisp65_c2_mapped_product_cold))) / 0x100 * 0x100)))) {
        KEEP(*(.lisp65_c2_mapped_f011_cold))
        KEEP(*(.lisp65_c2_mapped_f011_cold.*))
    } >ram

    .lisp65_c2_mapped_far_service 0x78b2
        : AT((0x78b2 + ((0x00030000 - (0x7e8d + SIZEOF(.lisp65_c2_mapped_product_cold))) / 0x100 * 0x100))) {
        KEEP(*(.lisp65_c2_mapped_far_service))
        KEEP(*(.lisp65_c2_mapped_far_service.*))
    } >ram
} INSERT AFTER .text;

__lisp65_c2_mapped_far_required =
    DEFINED(__lisp65_c2_mapped_far_required_param)
        ? __lisp65_c2_mapped_far_required_param : 0;
__lisp65_c2_mapped_far_facade_padding_required =
    DEFINED(__lisp65_c2_mapped_far_facade_padding_required_param)
        ? __lisp65_c2_mapped_far_facade_padding_required_param : 0;
__lisp65_c2_mapped_far_service_start =
    ADDR(.lisp65_c2_mapped_far_service);
__lisp65_c2_mapped_far_service_end =
    ADDR(.lisp65_c2_mapped_far_service) +
    SIZEOF(.lisp65_c2_mapped_far_service);
__lisp65_c2_mapped_far_service_load_start =
    LOADADDR(.lisp65_c2_mapped_far_service);
__lisp65_c2_mapped_far_service_load_end =
    LOADADDR(.lisp65_c2_mapped_far_service) +
    SIZEOF(.lisp65_c2_mapped_far_service);
__lisp65_c2_mapped_shared_offset =
    LOADADDR(.lisp65_c2_mapped_far_service) -
    ADDR(.lisp65_c2_mapped_far_service);
__lisp65_c2_mapped_far_maplo_a =
    (__lisp65_c2_mapped_shared_offset / 0x100) & 0xff;
__lisp65_c2_mapped_far_maplo_x =
    0x80 + ((__lisp65_c2_mapped_shared_offset / 0x10000) & 0x0f);

__lisp65_c2_mapped_f011_cold_start = ADDR(.lisp65_c2_mapped_f011_cold);
__lisp65_c2_mapped_f011_cold_end =
    ADDR(.lisp65_c2_mapped_f011_cold) + SIZEOF(.lisp65_c2_mapped_f011_cold);
__lisp65_c2_mapped_f011_cold_load_start = LOADADDR(.lisp65_c2_mapped_f011_cold);
__lisp65_c2_mapped_f011_cold_load_end =
    LOADADDR(.lisp65_c2_mapped_f011_cold) + SIZEOF(.lisp65_c2_mapped_f011_cold);


ASSERT(ADDR(.lisp65_c2_static_stack) == 0xc074 &&
       SIZEOF(.lisp65_c2_static_stack) <= 12 &&
       ADDR(.lisp65_c2_static_stack) +
           SIZEOF(.lisp65_c2_static_stack) <= 0xc080,
       "compiler static stack escaped its owned 12-byte arena");
ASSERT(__lisp65_workbench_overlay_min_start == 0xc354,
       "runtime overlay floor drifted from its owner contract");
ASSERT(__lisp65_c2_mapped_far_required == 0 ||
       (ADDR(.lisp65_c2_convergence_zp) == 0x87 &&
        SIZEOF(.lisp65_c2_convergence_zp) == 2 &&
        ADDR(.lisp65_c2_convergence_state) == 0xc000 &&
        SIZEOF(.lisp65_c2_convergence_state) == 66),
       "convergence state escaped its named owners");
ASSERT(__lisp65_c2_mapped_far_required == 0 ||
       (ADDR(.lisp65_c2_mapped_far_facade) == MAX(0xb3b0, ADDR(.text) + SIZEOF(.text) + 32) &&
        ADDR(.lisp65_c2_mapped_far_facade) -
            (ADDR(.text) + SIZEOF(.text)) >= 32 &&
        LOADADDR(.lisp65_c2_mapped_far_facade) -
            ADDR(.lisp65_c2_mapped_far_facade) ==
                __lisp65_c2_mapped_shared_offset &&
        SIZEOF(.lisp65_c2_mapped_far_facade) == 98 &&
        ADDR(.lisp65_c2_mapped_far_facade) +
            SIZEOF(.lisp65_c2_mapped_far_facade) <= 0xb4a3),
       "mapped far facade escaped its resident wall");
ASSERT(__lisp65_c2_mapped_far_facade_padding_required == 0 ||
       (DEFINED(__lisp65_c2_mapped_far_facade_padding_contract_bytes) &&
        __lisp65_c2_mapped_far_facade_padding_end -
            __lisp65_c2_mapped_far_facade_padding_start ==
                __lisp65_c2_mapped_far_facade_padding_contract_bytes &&
        __lisp65_c2_mapped_far_facade_padding_contract_bytes == 0),
       "mapped far facade explicit padding drift");
ASSERT(__lisp65_c2_mapped_far_required == 0 ||
       (ADDR(.lisp65_c2_mapped_far_service) == 0x78b2 &&
        LOADADDR(.lisp65_c2_mapped_far_service) -
            ADDR(.lisp65_c2_mapped_far_service) ==
                __lisp65_c2_mapped_shared_offset &&
        (__lisp65_c2_mapped_shared_offset & 0xff) == 0 &&
        SIZEOF(.lisp65_c2_mapped_far_service) > 0 &&
        SIZEOF(.lisp65_c2_mapped_far_service) <= 1499 &&
        __lisp65_c2_mapped_far_service_end <= 0x7e8d &&
        LOADADDR(.lisp65_c2_mapped_product_cold) -
            __lisp65_c2_mapped_far_service_load_end ==
        ADDR(.lisp65_c2_mapped_product_cold) -
            __lisp65_c2_mapped_far_service_end),
       "mapped far body escaped its Bank-2 owner");
ASSERT(__lisp65_c2_mapped_far_required == 0 ||
       ADDR(.lisp65_c2_mapped_far_facade) -
           (ADDR(.text) + SIZEOF(.text)) >= 32,
       "ordinary text displaced the mapped far facade");

ASSERT(SIZEOF(.lisp65_c2_mapped_f011_cold) > 0 &&
       ADDR(.lisp65_c2_mapped_f011_cold) >= 0x6000 &&
       ADDR(.lisp65_c2_mapped_f011_cold) + SIZEOF(.lisp65_c2_mapped_f011_cold) ==
           ADDR(.lisp65_c2_mapped_far_service) &&
       LOADADDR(.lisp65_c2_mapped_f011_cold) - ADDR(.lisp65_c2_mapped_f011_cold) ==
           __lisp65_c2_mapped_shared_offset &&
       LOADADDR(.lisp65_c2_mapped_f011_cold) + SIZEOF(.lisp65_c2_mapped_f011_cold) ==
           LOADADDR(.lisp65_c2_mapped_far_service),
       "F011 cold owner escaped its derived mapped interval");

ASSERT(0x6000 == 0x6000 &&
       0x8000 == 0x8000,
       "mapped CPU slab contract drifted");

SECTIONS {
    .lisp65_c2_mapped_product_cold 0x7e8d
        : AT((0x7e8d + ((0x00030000 - (0x7e8d + SIZEOF(.lisp65_c2_mapped_product_cold))) / 0x100 * 0x100))) {
        KEEP(*(.lisp65_c2_mapped_product_cold))
        KEEP(*(.lisp65_c2_mapped_product_cold.*))
    } >ram
} INSERT AFTER .text;

__lisp65_c2_mapped_product_cold_start = ADDR(.lisp65_c2_mapped_product_cold);
__lisp65_c2_mapped_product_cold_end = ADDR(.lisp65_c2_mapped_product_cold) + SIZEOF(.lisp65_c2_mapped_product_cold);
__lisp65_c2_mapped_product_cold_load_start = LOADADDR(.lisp65_c2_mapped_product_cold);
__lisp65_c2_mapped_product_cold_load_end = LOADADDR(.lisp65_c2_mapped_product_cold) + SIZEOF(.lisp65_c2_mapped_product_cold);

__lisp65_c2_mapped_congruence_gap_start =
    __lisp65_c2_mapped_far_service_load_end;
__lisp65_c2_mapped_congruence_gap_end = __lisp65_c2_mapped_product_cold_load_start;
__lisp65_c2_mapped_bank_end_reserve_start = __lisp65_c2_mapped_product_cold_load_end;
__lisp65_c2_mapped_bank_end_reserve_end = 0x00030000;

ASSERT(ADDR(.lisp65_c2_mapped_product_cold) == 0x7e8d &&
       LOADADDR(.lisp65_c2_mapped_product_cold) - ADDR(.lisp65_c2_mapped_product_cold) == __lisp65_c2_mapped_shared_offset && LOADADDR(.lisp65_c2_mapped_product_cold) + SIZEOF(.lisp65_c2_mapped_product_cold) <= 0x00030000 &&
       SIZEOF(.lisp65_c2_mapped_product_cold) > 0 &&
       SIZEOF(.lisp65_c2_mapped_product_cold) <= 371 &&
       __lisp65_c2_mapped_product_cold_end <= 0x8000,
       "product cold tenant escaped its mapped arena");

/* Owner-authorized BSS triage.  The direct hot heap is the sole new fixed
 * tenant; it is reinitialized by mem_init because this NOLOAD section is not
 * part of the CRT ordinary-BSS wipe. */
SECTIONS {
    .lisp65_c2_fixed_bank0_hot_bss 0xc25d (NOLOAD) : {
        __lisp65_c2_fixed_bank0_hot_bss_start = .;
        __lisp65_c2_fixed_bank0_hot_bss_heap = .;
        KEEP(*(.lisp65_c2_fixed_bank0_hot_bss.heap))
        __lisp65_c2_fixed_bank0_hot_bss_end = .;
    } >ram
} INSERT AFTER .lisp65_c2_fixed_bank0_code;

ASSERT(ADDR(.lisp65_c2_fixed_bank0_hot_bss) == 0xc25d &&
       SIZEOF(.lisp65_c2_fixed_bank0_hot_bss) == 240 &&
       heap == 0xc25d &&
       __lisp65_c2_fixed_bank0_hot_bss_end == 0xc34d &&
       __lisp65_c2_fixed_bank0_hot_bss_end <=
           __lisp65_workbench_runtime_overlay_vma,
       "C2 hot-BSS fixed-block geometry drift");
ASSERT(ADDR(.noinit) == 0xc34d &&
       SIZEOF(.noinit) == 0 &&
       __heap_start == 0xc354 &&
       __lisp65_workbench_overlay_min_start == 0xc354 &&
       __lisp65_workbench_overlay_min_start <=
           __lisp65_workbench_runtime_overlay_vma,
       "C2 full-map empty-noinit/heap geometry drift");

/* The llvm-mos .rodata output is inherited from the platform script.  Bind it
 * to the preceding explicit low-resident state rather than to a free-standing
 * location-counter assignment (which does not place inherited outputs). */
ASSERT(ADDR(.rodata) ==
           ADDR(.lisp65_c2_kernal_state) +
           SIZEOF(.lisp65_c2_kernal_state) &&
       LOADADDR(.rodata) == ADDR(.rodata),
       "ordinary rodata predecessor/VMA/LMA relation drift");

SECTIONS {
    .lisp65_symbol22_first_fault_state
        (ADDR(.lisp65_c2_fixed_bank0_hot_bss) +
         SIZEOF(.lisp65_c2_fixed_bank0_hot_bss)) :
        AT(ADDR(.lisp65_c2_fixed_bank0_hot_bss) +
           SIZEOF(.lisp65_c2_fixed_bank0_hot_bss)) {
        KEEP(*(.lisp65_symbol22_first_fault_state))
    } >ram
} INSERT AFTER .lisp65_c2_fixed_bank0_hot_bss;

/* One-time owner-authorized Link-33 reopening.  The three holes are explicit:
 * no wildcard and no unrelated input section can become a tenant. */
SECTIONS {
    .lisp65_c2_kernal_window.reopen_gap0
        ADDR(.lisp65_c2_kernal_window.c2_resident) +
        SIZEOF(.lisp65_c2_kernal_window.c2_resident) :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.reopen_gap0) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.reopen_gap0))
    } >c2_kernal_window

    .lisp65_c2_kernal_window.input_capture_main
        ADDR(.lisp65_c2_kernal_window.reopen_gap0) +
        SIZEOF(.lisp65_c2_kernal_window.reopen_gap0) :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.input_capture_main) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.input_capture_main))
    } >c2_kernal_window
    .lisp65_c2_kernal_window.reopen_gap1
        ADDR(.lisp65_c2_kernal_window.profile_rodata) +
        SIZEOF(.lisp65_c2_kernal_window.profile_rodata) :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.reopen_gap1) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.reopen_gap1))
    } >c2_kernal_window

    .lisp65_c2_kernal_window.input_capture_helper
        ADDR(.lisp65_c2_kernal_window.reopen_gap1) +
        SIZEOF(.lisp65_c2_kernal_window.reopen_gap1) :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.input_capture_helper) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.input_capture_helper))
    } >c2_kernal_window

    .lisp65_c2_kernal_window.input_consumer
        ADDR(.lisp65_c2_kernal_window.input_capture_helper) +
        SIZEOF(.lisp65_c2_kernal_window.input_capture_helper) :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.input_consumer) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.input_consumer))
    } >c2_kernal_window
    .lisp65_c2_kernal_window.reopen_gap2 0xff90 :
        AT(ORIGIN(c2_kernal_window_load) + 0x1f90) {
        KEEP(*(.lisp65_c2_kernal_window.reopen_gap2))
    } >c2_kernal_window
} INSERT AFTER .lisp65_resident_island_annex;

ASSERT(SIZEOF(.lisp65_c2_kernal_window.reopen_gap0) > 0 &&
       ADDR(.lisp65_c2_kernal_window.reopen_gap0) +
       SIZEOF(.lisp65_c2_kernal_window.reopen_gap0) <=
       ADDR(.lisp65_c2_kernal_window.session_emitter_state),
       "C2 reopening gap0 overlaps session-emitter state");
ASSERT(SIZEOF(.lisp65_c2_kernal_window.reopen_gap1) > 0 &&
       ADDR(.lisp65_c2_kernal_window.reopen_gap1) +
       SIZEOF(.lisp65_c2_kernal_window.reopen_gap1) <=
       ADDR(.lisp65_c2_kernal_window.state),
       "C2 reopening gap1 overlaps owned state");

ASSERT(SIZEOF(.lisp65_c2_kernal_window.input_capture_main) > 0,
       "card-owned seed section is zero bytes; missing source owner=v160-input-capture section=.lisp65_c2_kernal_window.input_capture_main");
ASSERT(SIZEOF(.lisp65_c2_kernal_window.input_capture_main) == 28 &&
       ADDR(.lisp65_c2_kernal_window.input_capture_main) ==
           ADDR(.lisp65_c2_kernal_window.reopen_gap0) +
           SIZEOF(.lisp65_c2_kernal_window.reopen_gap0) &&
       ADDR(.lisp65_c2_kernal_window.input_capture_main) +
           SIZEOF(.lisp65_c2_kernal_window.input_capture_main) <=
           ADDR(.lisp65_c2_kernal_window.profile_rodata),
       "Comfort input capture main escaped its final-image-derived hole");
ASSERT(SIZEOF(.lisp65_c2_kernal_window.input_capture_helper) > 0,
       "card-owned seed section is zero bytes; missing source owner=v160-input-capture section=.lisp65_c2_kernal_window.input_capture_helper");
ASSERT(SIZEOF(.lisp65_c2_kernal_window.input_capture_helper) == 40 &&
       ADDR(.lisp65_c2_kernal_window.input_capture_helper) ==
           ADDR(.lisp65_c2_kernal_window.reopen_gap1) +
           SIZEOF(.lisp65_c2_kernal_window.reopen_gap1) &&
       ADDR(.lisp65_c2_kernal_window.input_capture_helper) +
           SIZEOF(.lisp65_c2_kernal_window.input_capture_helper) <=
           ADDR(.lisp65_c2_kernal_window.state),
       "Comfort input capture helper escaped its final-image-derived hole");
ASSERT((ADDR(.lisp65_c2_kernal_window.profile_rodata) -
            (ADDR(.lisp65_c2_kernal_window.input_capture_main) +
             SIZEOF(.lisp65_c2_kernal_window.input_capture_main))) +
       (ADDR(.lisp65_c2_kernal_window.state) -
            (ADDR(.lisp65_c2_kernal_window.input_capture_helper) +
             SIZEOF(.lisp65_c2_kernal_window.input_capture_helper))) >= 57,
       "adaptive input capture breached the 54-byte floor plus 3-byte watch");

ASSERT(SIZEOF(.lisp65_c2_kernal_window.input_consumer) > 0 &&
       SIZEOF(.lisp65_c2_kernal_window.input_consumer) <= 70 &&
       ADDR(.lisp65_c2_kernal_window.input_consumer) ==
           ADDR(.lisp65_c2_kernal_window.input_capture_helper) +
           SIZEOF(.lisp65_c2_kernal_window.input_capture_helper) &&
       ADDR(.lisp65_c2_kernal_window.input_consumer) +
           SIZEOF(.lisp65_c2_kernal_window.input_consumer) <=
           ADDR(.lisp65_c2_kernal_window.state),
       "adaptive input consumer escaped its final-image-derived hole");
ASSERT((ADDR(.lisp65_c2_kernal_window.profile_rodata) -
            (ADDR(.lisp65_c2_kernal_window.input_capture_main) +
             SIZEOF(.lisp65_c2_kernal_window.input_capture_main))) +
       (ADDR(.lisp65_c2_kernal_window.state) -
            (ADDR(.lisp65_c2_kernal_window.input_consumer) +
       SIZEOF(.lisp65_c2_kernal_window.input_consumer))) >= 57,
       "adaptive input consumer breached the 54-byte floor plus 3-byte watch");
ASSERT(SIZEOF(.lisp65_c2_kernal_window.reopen_gap2) > 0 &&
       ADDR(.lisp65_c2_kernal_window.reopen_gap2) +
       SIZEOF(.lisp65_c2_kernal_window.reopen_gap2) <=
       ADDR(.lisp65_c2_vectors),
       "C2 reopening gap2 overlaps vectors");
ASSERT(SIZEOF(.lisp65_c2_host_facade) == 48 &&
       c2_facade_runtime_overlay_exec == 0xb5eb &&
       c2_facade_handle_normalize == 0xb5ee &&
       c2_facade_append_plan_walk == 0xb5f1,
       "C2 reopening appended facade vector drift");
ASSERT(SIZEOF(.lisp65_c2_kernal_window.reopen_gap0) +
       SIZEOF(.lisp65_c2_kernal_window.reopen_gap1) +
       SIZEOF(.lisp65_c2_kernal_window.reopen_gap2) +
       9 <= 450,
       "C2 formal E000 reopening exceeds the owner debit cap");

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

/* Pinned lld diagnoses this LTO bookkeeping input as an orphan even
 * when named.  The exact-warning wrapper and final inventory are
 * therefore the compensating gates for this one INFO section. */
SECTIONS {
    .llvm_sympart 0 (INFO) : { KEEP(*(.llvm_sympart)) }
}
ASSERT(SIZEOF(.llvm_sympart) > 0,
       "required LTO partition metadata section is absent");
ASSERT(ADDR(.llvm_sympart) == 0,
       "LTO partition metadata moved from address zero");


/* v1.8 full-map simultaneous-live closure.  All addresses are duplicated in
 * the independent Phase-B contract and checked by the permanent gate. */
ASSERT(ADDR(.rodata) == 0xb61d &&
       ADDR(.rodata) + SIZEOF(.rodata) <= 0xb98c &&
       ADDR(.lisp65_runtime_overlay_verifier_bindings) == 0xb98c &&
       SIZEOF(.lisp65_runtime_overlay_verifier_bindings) == 40 &&
       ADDR(.data) == 0xb9b4 && LOADADDR(.data) == ADDR(.data) &&
       ADDR(.data) + SIZEOF(.data) <= ADDR(.bss) &&
       ADDR(.bss) == 0xb9ca &&
       ADDR(.bss) + SIZEOF(.bss) + 5 <=
           ADDR(.lisp65_c2_input_raw_owner),
       "ordinary full-map chain drift");
ASSERT(ADDR(.lisp65_c2_convergence_state) == 0xc000 &&
       ADDR(.lisp65_c2_static_stack) == 0xc074 &&
       SIZEOF(.lisp65_c2_static_stack) > 0 &&
       ADDR(.lisp65_c2_static_stack) + SIZEOF(.lisp65_c2_static_stack)
           <= ADDR(.lisp65_c2_fixed_bank0) &&
       ADDR(.lisp65_c2_fixed_bank0) == 0xc080 &&
       ADDR(.lisp65_c2_fixed_bank0_hot_bss) +
           SIZEOF(.lisp65_c2_fixed_bank0_hot_bss) == 0xc34d &&
       ADDR(.noinit) == 0xc34d && SIZEOF(.noinit) == 0 &&
       __heap_start == 0xc354 &&
       __lisp65_workbench_overlay_min_start == 0xc354 &&
       __lisp65_workbench_runtime_overlay_vma >= __heap_start,
       "fixed/full-map/heap/overlay simultaneous-live relation drift");
ASSERT(0xc000 - (ADDR(.bss) + SIZEOF(.bss)) >= 5,
       "five-byte validation margin floor violated; it is not capacity");

/* Final owner-bound E000 floor: no third reopening. */
ASSERT(SIZEOF(.lisp65_c2_kernal_window.typed_queue_driver) +
       SIZEOF(.lisp65_c2_kernal_window.irq_handler) +
       SIZEOF(.lisp65_c2_kernal_window.nmi_and_freezer_return) +
       SIZEOF(.lisp65_c2_kernal_window.map_switch_and_guards) +
       SIZEOF(.lisp65_c2_kernal_window.post_startup_output_seam) +
       SIZEOF(.lisp65_c2_kernal_window.c2_resident) +
       SIZEOF(.lisp65_c2_kernal_window.session_emitter_state) +
       SIZEOF(.lisp65_c2_kernal_window.profile_rodata) +
       SIZEOF(.lisp65_c2_kernal_window.state) +
       SIZEOF(.lisp65_c2_vectors) +
       SIZEOF(.lisp65_c2_kernal_window.input_capture_main) +
       SIZEOF(.lisp65_c2_kernal_window.input_capture_helper) +
       SIZEOF(.lisp65_c2_kernal_window.input_consumer) +
       SIZEOF(.lisp65_c2_kernal_window.reopen_gap0) +
       SIZEOF(.lisp65_c2_kernal_window.reopen_gap1) +
       SIZEOF(.lisp65_c2_kernal_window.reopen_gap2) <= 8138,
       "C2 final E000 floor below 54 bytes");

/* Card 2b: complete carrier, including its alignment prefix. */
MEMORY {
    card2b_carrier (rw) : ORIGIN = 0x2ed56, LENGTH = 1792
    card2b_window (rwx) : ORIGIN = 0xc356, LENGTH = 1622
}
SECTIONS {
    .noinit.card2b_carrier_prefix 0x2ed56 (NOLOAD) : {
        __card2b_carrier_start = .;
        . += 170;
        __card2b_payload_load_start = .;
    } >card2b_carrier
    OVERLAY __lisp65_workbench_runtime_overlay_vma : NOCROSSREFS AT(0x2ee00) {
        .lisp65_rt_card2b_disk {
            KEEP(*(.lisp65_rt_card2b_disk))
            KEEP(*(.rodata.card2b_disk_entry .rodata.card2b_disk_body))
        }
    } >card2b_window
    .noinit.card2b_carrier_tail (LOADADDR(.lisp65_rt_card2b_disk) + SIZEOF(.lisp65_rt_card2b_disk)) (NOLOAD) : {
        . += ORIGIN(card2b_carrier) + LENGTH(card2b_carrier)
             - LOADADDR(.lisp65_rt_card2b_disk) - SIZEOF(.lisp65_rt_card2b_disk);
    } >card2b_carrier
} INSERT BEFORE .rodata;
__card2b_carrier_end = 0x2f456;
__card2b_payload_load_end = LOADADDR(.lisp65_rt_card2b_disk) + SIZEOF(.lisp65_rt_card2b_disk);
__lisp65_rt_card2b_disk_start = ADDR(.lisp65_rt_card2b_disk);
__lisp65_rt_card2b_disk_end = ADDR(.lisp65_rt_card2b_disk) + SIZEOF(.lisp65_rt_card2b_disk);
__lisp65_rt_card2b_disk_entry = card2b_disk_entry;
ASSERT(LOADADDR(.lisp65_rt_card2b_disk) == __card2b_payload_load_start,
       "Card 2b payload LOADADDR differs from reserved prefix end");
ASSERT(ADDR(.noinit.card2b_carrier_tail) + SIZEOF(.noinit.card2b_carrier_tail)
       == __card2b_carrier_end, "Card 2b tail reservation does not close its owner");
ASSERT((LOADADDR(.lisp65_rt_card2b_disk) & 255) == 0,
       "Card 2b L65R source is not page aligned");
ASSERT(SIZEOF(.lisp65_rt_card2b_disk) > 0 && SIZEOF(.lisp65_rt_card2b_disk) <= 1622,
       "Card 2b payload exceeds its own carrier");
ASSERT(__lisp65_rt_card2b_disk_end <= __lisp65_workbench_runtime_overlay_limit,
       "Card 2b member exceeds the CPU window");
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_bank3_stage_session)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_buffer_alloc)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_buffer_read)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_buffer_write)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2append_abort_control)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2append_crc_metadata)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2append_entries)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2append_envelope)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2append_header)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2append_image)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2append_journal_prepare)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2append_journal_reconstruct)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2append_journal_validate)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2append_publish_clear)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2append_publish_plan_resolve)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2append_publish_plan_scan)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2append_reserve_persistent_bounds)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2append_reserve_persistent_code)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2append_reserve_transient_bounds)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2append_reserve_transient_code)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2append_rollback_finalize)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2append_rollback_unpublish)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2append_rollback_wipe_attic)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2append_rollback_wipe_chip)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2append_rollback_wipe_plane)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2append_roots_fronts)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2append_stage_copy)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2append_stage_plane)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2d_00)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2d_00b)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2d_01)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2d_02a)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2d_02b)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2d_03)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2d_03b)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2d_04)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2d_05a)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2d_05b)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2d_06a)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2d_06b)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2d_07)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2d_08)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2d_09)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2d_10)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2d_11a)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2d_11b)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2d_12)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2d_13)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2emit_code)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2emit_final_crc)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2emit_final_meta)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2emit_literal_append)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2emit_literal_atom)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2emit_literal_prep)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2emit_name)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_c2emit_prepare)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_intern_service)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_island_00)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_l65e)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_rtov_catalog)
NOCROSSREFS(.lisp65_rt_card2b_disk .lisp65_rt_rtov_record)

/* GC reader local copy/remap placement; symbols are emitted by its owner. */
ASSERT(!DEFINED(c2_map_cpu_read) ||
       (DEFINED(__lisp65_c2_map_cpu_hot_begin) &&
        DEFINED(__lisp65_c2_map_cpu_hot_end) &&
        (__lisp65_c2_map_cpu_hot_end > __lisp65_c2_map_cpu_hot_begin) &&
        ((__lisp65_c2_map_cpu_hot_begin & 0xff00) ==
         ((__lisp65_c2_map_cpu_hot_end - 1) & 0xff00))),
       "MAP reader local copy/remap range crosses a CPU page");
