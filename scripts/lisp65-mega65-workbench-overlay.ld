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
    OVERLAY __lisp65_workbench_runtime_overlay_vma : NOCROSSREFS {
        .lisp65_workbench_overlay {
            KEEP(*(.lisp65_boot .lisp65_boot.*))
        }
        .lisp65_rt_rtov_catalog { KEEP(*(.lisp65_rt_rtov_catalog)) }
        .lisp65_rt_rtov_record { KEEP(*(.lisp65_rt_rtov_record)) }
        .lisp65_rt_l65m_00 {
            KEEP(*(.lisp65_rt_l65m_00))
            KEEP(*(.lisp65_rt_l65m_00_data))
        }
        .lisp65_rt_l65m_01 { KEEP(*(.lisp65_rt_l65m_01)) }
        .lisp65_rt_l65m_02 { KEEP(*(.lisp65_rt_l65m_02)) }
        .lisp65_rt_l65m_03 {
            KEEP(*(.lisp65_rt_l65m_03))
            KEEP(*(.lisp65_rt_l65m_03_data))
        }
        .lisp65_rt_l65m_04 { KEEP(*(.lisp65_rt_l65m_04)) }
        .lisp65_rt_l65m_05 { KEEP(*(.lisp65_rt_l65m_05)) }
        .lisp65_rt_l65m_06 { KEEP(*(.lisp65_rt_l65m_06)) }
        .lisp65_rt_l65m_07 { KEEP(*(.lisp65_rt_l65m_07)) }
        .lisp65_rt_l65m_08 { KEEP(*(.lisp65_rt_l65m_08)) }
        .lisp65_rt_l65m_09 { KEEP(*(.lisp65_rt_l65m_09)) }
        .lisp65_rt_l65m_10 { KEEP(*(.lisp65_rt_l65m_10)) }
        .lisp65_rt_l65m_11 { KEEP(*(.lisp65_rt_l65m_11)) }
        .lisp65_rt_l65m_12 { KEEP(*(.lisp65_rt_l65m_12)) }
        .lisp65_rt_l65m_13 { KEEP(*(.lisp65_rt_l65m_13)) }
        .lisp65_rt_l65m_14 { KEEP(*(.lisp65_rt_l65m_14)) }
        .lisp65_rt_l65m_15 { KEEP(*(.lisp65_rt_l65m_15)) }
        .lisp65_rt_l65m_16 { KEEP(*(.lisp65_rt_l65m_16)) }
        .lisp65_rt_l65m_17 { KEEP(*(.lisp65_rt_l65m_17)) }
        .lisp65_rt_l65m_18 { KEEP(*(.lisp65_rt_l65m_18)) }
        .lisp65_rt_l65m_19 { KEEP(*(.lisp65_rt_l65m_19)) }
        .lisp65_rt_l65m_20 { KEEP(*(.lisp65_rt_l65m_20)) }
        .lisp65_rt_l65c_00 { KEEP(*(.lisp65_rt_l65c_00)) }
        .lisp65_rt_l65c_01 { KEEP(*(.lisp65_rt_l65c_01)) }
        .lisp65_rt_l65c_02 { KEEP(*(.lisp65_rt_l65c_02)) }
        .lisp65_rt_l65c_03 { KEEP(*(.lisp65_rt_l65c_03)) }
        .lisp65_rt_l65c_04 { KEEP(*(.lisp65_rt_l65c_04)) }
        .lisp65_rt_l65c_05 { KEEP(*(.lisp65_rt_l65c_05)) }
        .lisp65_rt_l65c_06 { KEEP(*(.lisp65_rt_l65c_06)) }
        .lisp65_rt_lcci_00 { KEEP(*(.lisp65_rt_lcci_00)) }
        .lisp65_rt_lcci_01 { KEEP(*(.lisp65_rt_lcci_01)) }
        .lisp65_rt_lcci_02 { KEEP(*(.lisp65_rt_lcci_02)) }
        .lisp65_rt_boot_00 { KEEP(*(.lisp65_rt_boot_00)) }
        .lisp65_rt_boot_01 { KEEP(*(.lisp65_rt_boot_01)) }
        .lisp65_rt_boot_02 { KEEP(*(.lisp65_rt_boot_02)) }
        .lisp65_rt_l65e {
            KEEP(*(.lisp65_rt_l65e))
            KEEP(*(.lisp65_rt_l65e_data))
        }
        .lisp65_rt_island_00 {
            KEEP(*(.lisp65_rt_island_00))
            KEEP(*(.lisp65_rt_island_00_data))
        }
        .lisp65_rt_l65s {
            KEEP(*(.lisp65_rt_l65s))
            KEEP(*(.lisp65_rt_l65s_data))
        }
        .lisp65_rt_l65s_name { KEEP(*(.lisp65_rt_l65s_name)) }
        .lisp65_rt_buffer_read { KEEP(*(.lisp65_rt_buffer_read)) }
        .lisp65_rt_buffer_write { KEEP(*(.lisp65_rt_buffer_write)) }
        .lisp65_rt_buffer_alloc { KEEP(*(.lisp65_rt_buffer_alloc)) }
        .lisp65_rt_c1_compiler { KEEP(*(.lisp65_rt_c1_compiler)) }
    } >ram
} INSERT AFTER .noinit;

__lisp65_resident_island_seed_lma =
    ALIGN(LOADADDR(.lisp65_rt_c1_compiler) + SIZEOF(.lisp65_rt_c1_compiler), 0x100);

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
__lisp65_rt_l65m_00_start = ADDR(.lisp65_rt_l65m_00); __lisp65_rt_l65m_00_end = ADDR(.lisp65_rt_l65m_00) + SIZEOF(.lisp65_rt_l65m_00);
__lisp65_rt_l65m_01_start = ADDR(.lisp65_rt_l65m_01); __lisp65_rt_l65m_01_end = ADDR(.lisp65_rt_l65m_01) + SIZEOF(.lisp65_rt_l65m_01);
__lisp65_rt_l65m_02_start = ADDR(.lisp65_rt_l65m_02); __lisp65_rt_l65m_02_end = ADDR(.lisp65_rt_l65m_02) + SIZEOF(.lisp65_rt_l65m_02);
__lisp65_rt_l65m_03_start = ADDR(.lisp65_rt_l65m_03); __lisp65_rt_l65m_03_end = ADDR(.lisp65_rt_l65m_03) + SIZEOF(.lisp65_rt_l65m_03);
__lisp65_rt_l65m_04_start = ADDR(.lisp65_rt_l65m_04); __lisp65_rt_l65m_04_end = ADDR(.lisp65_rt_l65m_04) + SIZEOF(.lisp65_rt_l65m_04);
__lisp65_rt_l65m_05_start = ADDR(.lisp65_rt_l65m_05); __lisp65_rt_l65m_05_end = ADDR(.lisp65_rt_l65m_05) + SIZEOF(.lisp65_rt_l65m_05);
__lisp65_rt_l65m_06_start = ADDR(.lisp65_rt_l65m_06); __lisp65_rt_l65m_06_end = ADDR(.lisp65_rt_l65m_06) + SIZEOF(.lisp65_rt_l65m_06);
__lisp65_rt_l65m_07_start = ADDR(.lisp65_rt_l65m_07); __lisp65_rt_l65m_07_end = ADDR(.lisp65_rt_l65m_07) + SIZEOF(.lisp65_rt_l65m_07);
__lisp65_rt_l65m_08_start = ADDR(.lisp65_rt_l65m_08); __lisp65_rt_l65m_08_end = ADDR(.lisp65_rt_l65m_08) + SIZEOF(.lisp65_rt_l65m_08);
__lisp65_rt_l65m_09_start = ADDR(.lisp65_rt_l65m_09); __lisp65_rt_l65m_09_end = ADDR(.lisp65_rt_l65m_09) + SIZEOF(.lisp65_rt_l65m_09);
__lisp65_rt_l65m_10_start = ADDR(.lisp65_rt_l65m_10); __lisp65_rt_l65m_10_end = ADDR(.lisp65_rt_l65m_10) + SIZEOF(.lisp65_rt_l65m_10);
__lisp65_rt_l65m_11_start = ADDR(.lisp65_rt_l65m_11); __lisp65_rt_l65m_11_end = ADDR(.lisp65_rt_l65m_11) + SIZEOF(.lisp65_rt_l65m_11);
__lisp65_rt_l65m_12_start = ADDR(.lisp65_rt_l65m_12); __lisp65_rt_l65m_12_end = ADDR(.lisp65_rt_l65m_12) + SIZEOF(.lisp65_rt_l65m_12);
__lisp65_rt_l65m_13_start = ADDR(.lisp65_rt_l65m_13); __lisp65_rt_l65m_13_end = ADDR(.lisp65_rt_l65m_13) + SIZEOF(.lisp65_rt_l65m_13);
__lisp65_rt_l65m_14_start = ADDR(.lisp65_rt_l65m_14); __lisp65_rt_l65m_14_end = ADDR(.lisp65_rt_l65m_14) + SIZEOF(.lisp65_rt_l65m_14);
__lisp65_rt_l65m_15_start = ADDR(.lisp65_rt_l65m_15); __lisp65_rt_l65m_15_end = ADDR(.lisp65_rt_l65m_15) + SIZEOF(.lisp65_rt_l65m_15);
__lisp65_rt_l65m_16_start = ADDR(.lisp65_rt_l65m_16); __lisp65_rt_l65m_16_end = ADDR(.lisp65_rt_l65m_16) + SIZEOF(.lisp65_rt_l65m_16);
__lisp65_rt_l65m_17_start = ADDR(.lisp65_rt_l65m_17); __lisp65_rt_l65m_17_end = ADDR(.lisp65_rt_l65m_17) + SIZEOF(.lisp65_rt_l65m_17);
__lisp65_rt_l65m_18_start = ADDR(.lisp65_rt_l65m_18); __lisp65_rt_l65m_18_end = ADDR(.lisp65_rt_l65m_18) + SIZEOF(.lisp65_rt_l65m_18);
__lisp65_rt_l65m_19_start = ADDR(.lisp65_rt_l65m_19); __lisp65_rt_l65m_19_end = ADDR(.lisp65_rt_l65m_19) + SIZEOF(.lisp65_rt_l65m_19);
__lisp65_rt_l65m_20_start = ADDR(.lisp65_rt_l65m_20); __lisp65_rt_l65m_20_end = ADDR(.lisp65_rt_l65m_20) + SIZEOF(.lisp65_rt_l65m_20);
__lisp65_rt_l65c_00_start = ADDR(.lisp65_rt_l65c_00); __lisp65_rt_l65c_00_end = ADDR(.lisp65_rt_l65c_00) + SIZEOF(.lisp65_rt_l65c_00);
__lisp65_rt_l65c_01_start = ADDR(.lisp65_rt_l65c_01); __lisp65_rt_l65c_01_end = ADDR(.lisp65_rt_l65c_01) + SIZEOF(.lisp65_rt_l65c_01);
__lisp65_rt_l65c_02_start = ADDR(.lisp65_rt_l65c_02); __lisp65_rt_l65c_02_end = ADDR(.lisp65_rt_l65c_02) + SIZEOF(.lisp65_rt_l65c_02);
__lisp65_rt_l65c_03_start = ADDR(.lisp65_rt_l65c_03); __lisp65_rt_l65c_03_end = ADDR(.lisp65_rt_l65c_03) + SIZEOF(.lisp65_rt_l65c_03);
__lisp65_rt_l65c_04_start = ADDR(.lisp65_rt_l65c_04); __lisp65_rt_l65c_04_end = ADDR(.lisp65_rt_l65c_04) + SIZEOF(.lisp65_rt_l65c_04);
__lisp65_rt_l65c_05_start = ADDR(.lisp65_rt_l65c_05); __lisp65_rt_l65c_05_end = ADDR(.lisp65_rt_l65c_05) + SIZEOF(.lisp65_rt_l65c_05);
__lisp65_rt_l65c_06_start = ADDR(.lisp65_rt_l65c_06); __lisp65_rt_l65c_06_end = ADDR(.lisp65_rt_l65c_06) + SIZEOF(.lisp65_rt_l65c_06);
__lisp65_rt_lcci_00_start = ADDR(.lisp65_rt_lcci_00); __lisp65_rt_lcci_00_end = ADDR(.lisp65_rt_lcci_00) + SIZEOF(.lisp65_rt_lcci_00);
__lisp65_rt_lcci_01_start = ADDR(.lisp65_rt_lcci_01); __lisp65_rt_lcci_01_end = ADDR(.lisp65_rt_lcci_01) + SIZEOF(.lisp65_rt_lcci_01);
__lisp65_rt_lcci_02_start = ADDR(.lisp65_rt_lcci_02); __lisp65_rt_lcci_02_end = ADDR(.lisp65_rt_lcci_02) + SIZEOF(.lisp65_rt_lcci_02);
__lisp65_rt_boot_00_start = ADDR(.lisp65_rt_boot_00); __lisp65_rt_boot_00_end = ADDR(.lisp65_rt_boot_00) + SIZEOF(.lisp65_rt_boot_00);
__lisp65_rt_boot_01_start = ADDR(.lisp65_rt_boot_01); __lisp65_rt_boot_01_end = ADDR(.lisp65_rt_boot_01) + SIZEOF(.lisp65_rt_boot_01);
__lisp65_rt_boot_02_start = ADDR(.lisp65_rt_boot_02); __lisp65_rt_boot_02_end = ADDR(.lisp65_rt_boot_02) + SIZEOF(.lisp65_rt_boot_02);
__lisp65_rt_l65e_start = ADDR(.lisp65_rt_l65e); __lisp65_rt_l65e_end = ADDR(.lisp65_rt_l65e) + SIZEOF(.lisp65_rt_l65e);
__lisp65_rt_l65s_start = ADDR(.lisp65_rt_l65s); __lisp65_rt_l65s_end = ADDR(.lisp65_rt_l65s) + SIZEOF(.lisp65_rt_l65s);
__lisp65_rt_l65s_name_start = ADDR(.lisp65_rt_l65s_name); __lisp65_rt_l65s_name_end = ADDR(.lisp65_rt_l65s_name) + SIZEOF(.lisp65_rt_l65s_name);
__lisp65_rt_buffer_read_start = ADDR(.lisp65_rt_buffer_read); __lisp65_rt_buffer_read_end = ADDR(.lisp65_rt_buffer_read) + SIZEOF(.lisp65_rt_buffer_read);
__lisp65_rt_buffer_write_start = ADDR(.lisp65_rt_buffer_write); __lisp65_rt_buffer_write_end = ADDR(.lisp65_rt_buffer_write) + SIZEOF(.lisp65_rt_buffer_write);
__lisp65_rt_buffer_alloc_start = ADDR(.lisp65_rt_buffer_alloc); __lisp65_rt_buffer_alloc_end = ADDR(.lisp65_rt_buffer_alloc) + SIZEOF(.lisp65_rt_buffer_alloc);
__lisp65_rt_c1_compiler_start = ADDR(.lisp65_rt_c1_compiler); __lisp65_rt_c1_compiler_end = ADDR(.lisp65_rt_c1_compiler) + SIZEOF(.lisp65_rt_c1_compiler);
__lisp65_resident_island_start = ADDR(.lisp65_resident_island); __lisp65_resident_island_end = ADDR(.lisp65_resident_island) + SIZEOF(.lisp65_resident_island);
__lisp65_resident_island_annex_start = ADDR(.lisp65_resident_island_annex); __lisp65_resident_island_annex_end = ADDR(.lisp65_resident_island_annex) + SIZEOF(.lisp65_resident_island_annex);
__lisp65_rt_island_00_start = ADDR(.lisp65_rt_island_00); __lisp65_rt_island_00_end = ADDR(.lisp65_rt_island_00) + SIZEOF(.lisp65_rt_island_00);
__lisp65_rt_rtov_catalog_entry = vm_runtime_overlay_catalog_verifier;
__lisp65_rt_rtov_record_entry = vm_runtime_overlay_record_verifier;
__lisp65_rt_l65m_00_entry = l65m_overlay_phase_00;
__lisp65_rt_l65m_01_entry = l65m_overlay_phase_01;
__lisp65_rt_l65m_02_entry = l65m_overlay_phase_02;
__lisp65_rt_l65m_03_entry = l65m_overlay_phase_03;
__lisp65_rt_l65m_04_entry = l65m_overlay_phase_04;
__lisp65_rt_l65m_05_entry = l65m_overlay_phase_05;
__lisp65_rt_l65m_06_entry = l65m_overlay_phase_06;
__lisp65_rt_l65m_07_entry = l65m_overlay_phase_07;
__lisp65_rt_l65m_08_entry = l65m_overlay_phase_08;
__lisp65_rt_l65m_09_entry = l65m_overlay_phase_09;
__lisp65_rt_l65m_10_entry = l65m_overlay_phase_10;
__lisp65_rt_l65m_11_entry = l65m_overlay_phase_11;
__lisp65_rt_l65m_12_entry = l65m_overlay_phase_12;
__lisp65_rt_l65m_13_entry = l65m_overlay_phase_13;
__lisp65_rt_l65m_14_entry = l65m_overlay_phase_14;
__lisp65_rt_l65m_15_entry = l65m_overlay_phase_15;
__lisp65_rt_l65m_16_entry = l65m_overlay_phase_16;
__lisp65_rt_l65m_17_entry = l65m_overlay_phase_17;
__lisp65_rt_l65m_18_entry = l65m_overlay_phase_18;
__lisp65_rt_l65m_19_entry = l65m_overlay_phase_19;
__lisp65_rt_l65m_20_entry = l65m_overlay_phase_20;
__lisp65_rt_l65c_00_entry = l65m_commit_phase_verify;
__lisp65_rt_l65c_01_entry = l65m_commit_phase_patch_record;
__lisp65_rt_l65c_02_entry = l65m_commit_phase_materialize_shape;
__lisp65_rt_l65c_03_entry = l65m_commit_phase_materialize_scalars;
__lisp65_rt_l65c_04_entry = l65m_commit_phase_materialize_strings;
__lisp65_rt_l65c_05_entry = l65m_commit_phase_patch_publish;
__lisp65_rt_l65c_06_entry = l65m_commit_phase_entries;
__lisp65_rt_lcci_00_entry = lcc_install_phase_00;
__lisp65_rt_lcci_01_entry = lcc_install_phase_01;
__lisp65_rt_lcci_02_entry = lcc_install_phase_02;
__lisp65_rt_boot_00_entry = vm_boot_fastpath_phase_verify;
__lisp65_rt_boot_01_entry = vm_boot_fastpath_phase_patches;
__lisp65_rt_boot_02_entry = vm_boot_fastpath_phase_entries;
__lisp65_rt_l65e_entry = lisp65_error_overlay_entry;
__lisp65_rt_l65s_entry = l65s_stage_entry;
__lisp65_rt_l65s_name_entry = l65s_name_entry;
__lisp65_rt_buffer_read_entry = lisp65_buffer_overlay_read_entry;
__lisp65_rt_buffer_write_entry = lisp65_buffer_overlay_write_entry;
__lisp65_rt_buffer_alloc_entry = lisp65_buffer_overlay_alloc_entry;
__lisp65_rt_c1_compiler_entry = lisp65_c1_compiler_overlay_entry;
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
       "resident island seed LMA is not aligned directly after Slot 37");
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
ASSERT(SIZEOF(.lisp65_rt_l65m_00) > 0 && SIZEOF(.lisp65_rt_l65m_00) <= 1792 && __lisp65_rt_l65m_00_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay l65m-00 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65m_01) > 0 && SIZEOF(.lisp65_rt_l65m_01) <= 1792 && __lisp65_rt_l65m_01_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay l65m-01 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65m_02) > 0 && SIZEOF(.lisp65_rt_l65m_02) <= 1792 && __lisp65_rt_l65m_02_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay l65m-02 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65m_03) > 0 && SIZEOF(.lisp65_rt_l65m_03) <= 1792 && __lisp65_rt_l65m_03_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay l65m-03 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65m_04) > 0 && SIZEOF(.lisp65_rt_l65m_04) <= 1792 && __lisp65_rt_l65m_04_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay l65m-04 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65m_05) > 0 && SIZEOF(.lisp65_rt_l65m_05) <= 1792 && __lisp65_rt_l65m_05_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay l65m-05 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65m_06) > 0 && SIZEOF(.lisp65_rt_l65m_06) <= 1792 && __lisp65_rt_l65m_06_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay l65m-06 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65m_07) > 0 && SIZEOF(.lisp65_rt_l65m_07) <= 1792 && __lisp65_rt_l65m_07_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay l65m-07 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65m_08) > 0 && SIZEOF(.lisp65_rt_l65m_08) <= 1792 && __lisp65_rt_l65m_08_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay l65m-08 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65m_09) > 0 && SIZEOF(.lisp65_rt_l65m_09) <= 1792 && __lisp65_rt_l65m_09_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay l65m-09 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65m_10) > 0 && SIZEOF(.lisp65_rt_l65m_10) <= 1792 && __lisp65_rt_l65m_10_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay l65m-10 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65m_11) > 0 && SIZEOF(.lisp65_rt_l65m_11) <= 1792 && __lisp65_rt_l65m_11_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay l65m-11 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65m_12) > 0 && SIZEOF(.lisp65_rt_l65m_12) <= 1792 && __lisp65_rt_l65m_12_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay l65m-12 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65m_13) > 0 && SIZEOF(.lisp65_rt_l65m_13) <= 1792 && __lisp65_rt_l65m_13_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay l65m-13 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65m_14) > 0 && SIZEOF(.lisp65_rt_l65m_14) <= 1792 && __lisp65_rt_l65m_14_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay l65m-14 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65m_15) > 0 && SIZEOF(.lisp65_rt_l65m_15) <= 1792 && __lisp65_rt_l65m_15_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay l65m-15 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65m_16) > 0 && SIZEOF(.lisp65_rt_l65m_16) <= 1792 && __lisp65_rt_l65m_16_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay l65m-16 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65m_17) > 0 && SIZEOF(.lisp65_rt_l65m_17) <= 1792 && __lisp65_rt_l65m_17_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay l65m-17 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65m_18) > 0 && SIZEOF(.lisp65_rt_l65m_18) <= 1792 && __lisp65_rt_l65m_18_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay l65m-18 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65m_19) > 0 && SIZEOF(.lisp65_rt_l65m_19) <= 1792 && __lisp65_rt_l65m_19_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay l65m-19 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65m_20) > 0 && SIZEOF(.lisp65_rt_l65m_20) <= 1792 && __lisp65_rt_l65m_20_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay l65m-20 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65c_00) > 0 && SIZEOF(.lisp65_rt_l65c_00) <= 1792 && __lisp65_rt_l65c_00_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay l65c-00 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65c_01) > 0 && SIZEOF(.lisp65_rt_l65c_01) <= 1792 && __lisp65_rt_l65c_01_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay l65c-01 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65c_02) > 0 && SIZEOF(.lisp65_rt_l65c_02) <= 1792 && __lisp65_rt_l65c_02_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay l65c-02 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65c_03) > 0 && SIZEOF(.lisp65_rt_l65c_03) <= 1792 && __lisp65_rt_l65c_03_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay l65c-03 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65c_04) > 0 && SIZEOF(.lisp65_rt_l65c_04) <= 1792 && __lisp65_rt_l65c_04_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay l65c-04 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65c_05) > 0 && SIZEOF(.lisp65_rt_l65c_05) <= 1792 && __lisp65_rt_l65c_05_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay l65c-05 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65c_06) > 0 && SIZEOF(.lisp65_rt_l65c_06) <= 1792 && __lisp65_rt_l65c_06_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay l65c-06 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_lcci_00) > 0 && SIZEOF(.lisp65_rt_lcci_00) <= 1792 && __lisp65_rt_lcci_00_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay lcci-00 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_lcci_01) > 0 && SIZEOF(.lisp65_rt_lcci_01) <= 1792 && __lisp65_rt_lcci_01_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay lcci-01 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_lcci_02) > 0 && SIZEOF(.lisp65_rt_lcci_02) <= 1792 && __lisp65_rt_lcci_02_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay lcci-02 exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_boot_00) > 0 && SIZEOF(.lisp65_rt_boot_00) <= 4096 && __lisp65_rt_boot_00_end <= __lisp65_workbench_boot_slice_limit, "boot overlay phase-00 exceeds its 512-byte stack window");
ASSERT(SIZEOF(.lisp65_rt_boot_01) > 0 && SIZEOF(.lisp65_rt_boot_01) <= 4096 && __lisp65_rt_boot_01_end <= __lisp65_workbench_boot_slice_limit, "boot overlay phase-01 exceeds its 512-byte stack window");
ASSERT(SIZEOF(.lisp65_rt_boot_02) > 0 && SIZEOF(.lisp65_rt_boot_02) <= 4096 && __lisp65_rt_boot_02_end <= __lisp65_workbench_boot_slice_limit, "boot overlay phase-02 exceeds its 512-byte stack window");
ASSERT(SIZEOF(.lisp65_rt_l65e) > 0 && SIZEOF(.lisp65_rt_l65e) <= 1792 && __lisp65_rt_l65e_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay L65E renderer exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65e) <= __lisp65_error_overlay_max_bytes,
       "runtime overlay L65E renderer exceeds its product budget");
ASSERT(SIZEOF(.lisp65_rt_l65s) > 0 && SIZEOF(.lisp65_rt_l65s) <= 1792 && __lisp65_rt_l65s_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay L65S shelf loader exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_l65s_name) > 0 && SIZEOF(.lisp65_rt_l65s_name) <= 1792 && __lisp65_rt_l65s_name_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay L65S name resolver exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_buffer_read) > 0 && SIZEOF(.lisp65_rt_buffer_read) <= 1792 && __lisp65_rt_buffer_read_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay first-class buffer reader exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_buffer_write) > 0 && SIZEOF(.lisp65_rt_buffer_write) <= 1792 && __lisp65_rt_buffer_write_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay first-class buffer writer exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_buffer_alloc) > 0 && SIZEOF(.lisp65_rt_buffer_alloc) <= 1792 && __lisp65_rt_buffer_alloc_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay first-class buffer allocator exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_c1_compiler) > 0 && SIZEOF(.lisp65_rt_c1_compiler) <= 1792 && __lisp65_rt_c1_compiler_end <= __lisp65_workbench_runtime_overlay_limit, "runtime overlay C1 compiler lifetime exceeds its stack-safe window");
ASSERT(SIZEOF(.lisp65_rt_island_00) > 0 && SIZEOF(.lisp65_rt_island_00) <= 4096 && __lisp65_rt_island_00_end <= __lisp65_workbench_boot_slice_limit, "boot overlay resident-island installer exceeds its 512-byte stack window");
ASSERT(SIZEOF(.lisp65_rt_island_00) <= 1792,
       "resident-island installer exceeds the product Slot-37 budget");
