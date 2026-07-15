# Canonical configuration for the single interactive lisp65 product.
# Keep this profile explicit: it must not inherit flags from historical builds.

WORKBENCH_PROFILE_ID := mvp-vm-stdlib-einsuite-core-workbench
WORKBENCH_BUILD_TARGET := workbench-product
WORKBENCH_FOOTPRINT_TARGET := workbench-product-footprint-report

WORKBENCH_REFERENCE_BUILD_TARGET := mvp-vm-stdlib-einsuite-core-workbench
WORKBENCH_REFERENCE_FOOTPRINT_TARGET := mvp-vm-stdlib-einsuite-core-workbench-footprint-report
WORKBENCH_REFERENCE_PRG := build/lisp65-mega65-vm-stdlib-einsuite-core-workbench.prg
WORKBENCH_REFERENCE_FOOTPRINT_REPORT := build/bytecode/mvp-vm-stdlib-einsuite-core-workbench-footprint.txt
WORKBENCH_SUITE := tests/bytecode/stdlib/p0-stdlib-einsuite-core-workbench-subset.json
WORKBENCH_EVAL_SURFACE_FORMAT := lisp65-workbench-eval-surface-v1
WORKBENCH_EVAL_SURFACE_FIXTURE := tests/bytecode/runtime/workbench-eval-surface.json
WORKBENCH_EVAL_SURFACE_INPUTS := \
	config/semantic-contracts.json \
	$(WORKBENCH_EVAL_SURFACE_FIXTURE) \
	tools/host-lisp/semantic_contracts.py \
	tools/host-lisp/workbench_eval_surface.py
WORKBENCH_BANK0_LIFETIME_POLICY := config/bank0-lifetime-workbench.json
WORKBENCH_BANK0_LIFETIME_JSON := build/reports/workbench/bank0-lifetime.json
WORKBENCH_BANK0_LIFETIME_TEXT := build/reports/workbench/bank0-lifetime.txt
WORKBENCH_BYTECODE_DIR := build/bytecode/profiles/workbench
WORKBENCH_STDLIB_PREFIX := $(WORKBENCH_BYTECODE_DIR)/stdlib-p0
WORKBENCH_STDLIB_HEADER := $(WORKBENCH_STDLIB_PREFIX).h
WORKBENCH_STDLIB_C := $(WORKBENCH_STDLIB_PREFIX).c
WORKBENCH_STDLIB_BASE_EXT_BLOB := $(WORKBENCH_STDLIB_PREFIX).ext.bin
WORKBENCH_STDLIB_BASE_MANIFEST := $(WORKBENCH_STDLIB_PREFIX).manifest.json
# Compatibility names remain the raw stdlib inputs inside the build graph.
# Ship recipes override them with the profile-bound combined product artifacts.
WORKBENCH_STDLIB_EXT_BLOB := $(WORKBENCH_STDLIB_BASE_EXT_BLOB)
WORKBENCH_STDLIB_MANIFEST := $(WORKBENCH_STDLIB_BASE_MANIFEST)

# Non-default AP4.3 Workbench overlay prototype.  The resident PRG, raw
# overlay, descriptor and combined EXT preload are bound to one final ELF.
WORKBENCH_OVERLAY_DIR := build/products/workbench/overlay-prototype
WORKBENCH_OVERLAY_LINKED_PRG := $(WORKBENCH_OVERLAY_DIR)/lisp65-workbench-overlay-linked.prg
WORKBENCH_OVERLAY_RESIDENT_PRG := $(WORKBENCH_OVERLAY_DIR)/lisp65-workbench-resident.prg
WORKBENCH_OVERLAY_RAW := $(WORKBENCH_OVERLAY_DIR)/lisp65-workbench-overlay.bin
WORKBENCH_OVERLAY_LAYOUT := $(WORKBENCH_OVERLAY_DIR)/layout.json
WORKBENCH_OVERLAY_STAGE_HEADER := $(WORKBENCH_OVERLAY_DIR)/stage-config.h
WORKBENCH_OVERLAY_STAGE := $(WORKBENCH_OVERLAY_DIR)/overlay-stage.bin
WORKBENCH_OVERLAY_PRELOAD := $(WORKBENCH_OVERLAY_DIR)/stdlib-with-overlay.ext.bin
WORKBENCH_OVERLAY_STAGE_MANIFEST := $(WORKBENCH_OVERLAY_DIR)/stage-manifest.json
WORKBENCH_OVERLAY_AUDIT_REPORT := $(WORKBENCH_OVERLAY_DIR)/footprint-audit.json
WORKBENCH_OVERLAY_RAW_PACKAGE_DIR := $(WORKBENCH_OVERLAY_DIR)/raw-package
WORKBENCH_OVERLAY_RAW_PACKAGE_MANIFEST := $(WORKBENCH_OVERLAY_RAW_PACKAGE_DIR)/manifest.json
WORKBENCH_OVERLAY_ABI_CONTRACT := $(WORKBENCH_OVERLAY_DIR)/resolved-profile.txt
WORKBENCH_OVERLAY_ABI_ID := workbench-staged-overlay-abi-v1
WORKBENCH_OVERLAY_ENTRY := vm_workbench_boot_overlay_entry
WORKBENCH_OVERLAY_CONTROL_AUDIT_REPORT := $(WORKBENCH_OVERLAY_DIR)/control-audit.json
WORKBENCH_F011_WINDOW_AUDIT_REPORT := $(WORKBENCH_OVERLAY_DIR)/f011-mount-window-audit.json
WORKBENCH_OVERLAY_LD := scripts/lisp65-mega65-workbench-overlay.ld
WORKBENCH_OVERLAY_SECTION := .lisp65_workbench_overlay
WORKBENCH_OVERLAY_OBJCOPY := $(LLVM)/llvm-objcopy
WORKBENCH_OVERLAY_OBJDUMP := $(LLVM)/llvm-objdump
WORKBENCH_RUNTIME_OVERLAY_TOOL := tools/host-lisp/runtime_overlay_bank.py
WORKBENCH_RUNTIME_OVERLAY_HEADER := $(WORKBENCH_OVERLAY_DIR)/runtime-overlay-bank.h
WORKBENCH_RUNTIME_OVERLAY_PREPARED_HEADER := $(WORKBENCH_OVERLAY_DIR)/runtime-overlay-bank.prepare.h
WORKBENCH_RUNTIME_OVERLAY_BOOTSTRAP_LINKED_PRG := $(WORKBENCH_OVERLAY_DIR)/runtime-overlay-bootstrap-linked.prg
WORKBENCH_RUNTIME_OVERLAY_BOOTSTRAP_IMAGE := $(WORKBENCH_OVERLAY_DIR)/runtime-overlay-bootstrap.bin
WORKBENCH_RUNTIME_OVERLAY_BOOTSTRAP_MANIFEST := $(WORKBENCH_OVERLAY_DIR)/runtime-overlay-bootstrap-manifest.json
WORKBENCH_RESIDENT_ISLAND_TOOL := tools/host-lisp/resident_island.py
WORKBENCH_RESIDENT_ISLAND_PREPARED_HEADER := $(WORKBENCH_OVERLAY_DIR)/resident-island.prepare.h
WORKBENCH_RESIDENT_ISLAND_HEADER := $(WORKBENCH_OVERLAY_DIR)/resident-island-image.h
WORKBENCH_RESIDENT_ISLAND_SEED_LINKED_PRG := $(WORKBENCH_OVERLAY_DIR)/resident-island-seed-linked.prg
WORKBENCH_RESIDENT_ISLAND_SECTION := .lisp65_resident_island
WORKBENCH_RESIDENT_ISLAND_BASE := 0x1800
WORKBENCH_RESIDENT_ISLAND_LIMIT := 0x2000
WORKBENCH_RESIDENT_ISLAND_CAPACITY := 2048
WORKBENCH_RESIDENT_ISLAND_POLICY := config/bank0-island-workbench.json
WORKBENCH_RESIDENT_ISLAND_INVENTORY_TOOL := tools/host-lisp/bank0_island_inventory.py
WORKBENCH_RESIDENT_ISLAND_INVENTORY_JSON := build/reports/workbench/bank0-island.json
WORKBENCH_RESIDENT_ISLAND_INVENTORY_TEXT := build/reports/workbench/bank0-island.txt
WORKBENCH_SCREEN_BASE := 0x0800
WORKBENCH_SCREEN_COLUMNS := 80
WORKBENCH_SCREEN_ROWS := 50
WORKBENCH_SCREEN_CELL_BYTES := 1
WORKBENCH_SCREEN_LIMIT := 0x17a0
WORKBENCH_RUNTIME_OVERLAY_IMAGE := $(WORKBENCH_OVERLAY_DIR)/lisp65-mvp-workbench.overlays.bin
WORKBENCH_RUNTIME_OVERLAY_MANIFEST := $(WORKBENCH_OVERLAY_DIR)/runtime-overlays-manifest.json
# L65R-v1 retains format tag 3, while Ship-v5 stores the immutable image in
# reset-stable, power-volatile Attic RAM.
WORKBENCH_RUNTIME_OVERLAY_BANK := 3
WORKBENCH_RUNTIME_OVERLAY_ADDRESS := 0x08000000
WORKBENCH_RUNTIME_OVERLAY_MAX_SLICE_BYTES := 1792
WORKBENCH_RUNTIME_OVERLAY_MAX_SLICES := 64
WORKBENCH_RUNTIME_OVERLAY_MAX_VMA := 0xc356
WORKBENCH_RUNTIME_OVERLAY_ENTRY_ABI := 1
WORKBENCH_RUNTIME_OVERLAY_SLICE_COUNT := 38
WORKBENCH_RUNTIME_OVERLAY_VMA_SYMBOL := __lisp65_workbench_runtime_overlay_vma
WORKBENCH_ERROR_TEXT_PROFILE := workbench
WORKBENCH_ERROR_TEXT_SPEC := config/error-texts.json
WORKBENCH_ERROR_TEXT_TOOL := tools/host-lisp/error_text_table.py
WORKBENCH_ERROR_TEXT_HEADER := $(WORKBENCH_OVERLAY_DIR)/error-text-table.h
WORKBENCH_ERROR_TEXT_TABLE := $(WORKBENCH_OVERLAY_DIR)/error-text-table.bin
WORKBENCH_ERROR_OVERLAY_MAX_BYTES := 1320
WORKBENCH_ERROR_CODE_CONTRACT := config/error-code-contract.json
WORKBENCH_ERROR_CODE_TOOL := tools/host-lisp/error_code_contract.py
WORKBENCH_RUNTIME_OVERLAY_SLICE_ARGS := \
	--slice '0:catalog-verifier:.lisp65_rt_rtov_catalog:__lisp65_rt_rtov_catalog_start:__lisp65_rt_rtov_catalog_end:__lisp65_rt_rtov_catalog_entry:runtime+reusable:1:0:vm_runtime_overlay_catalog_verifier' \
	--slice '1:record-verifier:.lisp65_rt_rtov_record:__lisp65_rt_rtov_record_start:__lisp65_rt_rtov_record_end:__lisp65_rt_rtov_record_entry:runtime+reusable:1:0:vm_runtime_overlay_record_verifier' \
	--slice '2:l65m-phase-00:.lisp65_rt_l65m_00:__lisp65_rt_l65m_00_start:__lisp65_rt_l65m_00_end:__lisp65_rt_l65m_00_entry:runtime+reusable:1:0:l65m_overlay_phase_00' \
	--slice '3:l65m-phase-01:.lisp65_rt_l65m_01:__lisp65_rt_l65m_01_start:__lisp65_rt_l65m_01_end:__lisp65_rt_l65m_01_entry:runtime+reusable:1:0:l65m_overlay_phase_01' \
	--slice '4:l65m-phase-02:.lisp65_rt_l65m_02:__lisp65_rt_l65m_02_start:__lisp65_rt_l65m_02_end:__lisp65_rt_l65m_02_entry:runtime+reusable:1:0:l65m_overlay_phase_02' \
	--slice '5:l65m-phase-03:.lisp65_rt_l65m_03:__lisp65_rt_l65m_03_start:__lisp65_rt_l65m_03_end:__lisp65_rt_l65m_03_entry:runtime+reusable:1:0:l65m_overlay_phase_03' \
	--slice '6:l65m-phase-04:.lisp65_rt_l65m_04:__lisp65_rt_l65m_04_start:__lisp65_rt_l65m_04_end:__lisp65_rt_l65m_04_entry:runtime+reusable:1:0:l65m_overlay_phase_04' \
	--slice '7:l65m-phase-05:.lisp65_rt_l65m_05:__lisp65_rt_l65m_05_start:__lisp65_rt_l65m_05_end:__lisp65_rt_l65m_05_entry:runtime+reusable:1:0:l65m_overlay_phase_05' \
	--slice '8:l65m-phase-06:.lisp65_rt_l65m_06:__lisp65_rt_l65m_06_start:__lisp65_rt_l65m_06_end:__lisp65_rt_l65m_06_entry:runtime+reusable:1:0:l65m_overlay_phase_06' \
	--slice '9:l65m-phase-07:.lisp65_rt_l65m_07:__lisp65_rt_l65m_07_start:__lisp65_rt_l65m_07_end:__lisp65_rt_l65m_07_entry:runtime+reusable:1:0:l65m_overlay_phase_07' \
	--slice '10:l65m-phase-08:.lisp65_rt_l65m_08:__lisp65_rt_l65m_08_start:__lisp65_rt_l65m_08_end:__lisp65_rt_l65m_08_entry:runtime+reusable:1:0:l65m_overlay_phase_08' \
	--slice '11:l65m-phase-09:.lisp65_rt_l65m_09:__lisp65_rt_l65m_09_start:__lisp65_rt_l65m_09_end:__lisp65_rt_l65m_09_entry:runtime+reusable:1:0:l65m_overlay_phase_09' \
	--slice '12:l65m-phase-10:.lisp65_rt_l65m_10:__lisp65_rt_l65m_10_start:__lisp65_rt_l65m_10_end:__lisp65_rt_l65m_10_entry:runtime+reusable:1:0:l65m_overlay_phase_10' \
	--slice '13:l65m-phase-11:.lisp65_rt_l65m_11:__lisp65_rt_l65m_11_start:__lisp65_rt_l65m_11_end:__lisp65_rt_l65m_11_entry:runtime+reusable:1:0:l65m_overlay_phase_11' \
	--slice '14:l65m-phase-12:.lisp65_rt_l65m_12:__lisp65_rt_l65m_12_start:__lisp65_rt_l65m_12_end:__lisp65_rt_l65m_12_entry:runtime+reusable:1:0:l65m_overlay_phase_12' \
	--slice '15:l65m-phase-13:.lisp65_rt_l65m_13:__lisp65_rt_l65m_13_start:__lisp65_rt_l65m_13_end:__lisp65_rt_l65m_13_entry:runtime+reusable:1:0:l65m_overlay_phase_13' \
	--slice '16:l65m-phase-14:.lisp65_rt_l65m_14:__lisp65_rt_l65m_14_start:__lisp65_rt_l65m_14_end:__lisp65_rt_l65m_14_entry:runtime+reusable:1:0:l65m_overlay_phase_14' \
	--slice '17:l65m-phase-15:.lisp65_rt_l65m_15:__lisp65_rt_l65m_15_start:__lisp65_rt_l65m_15_end:__lisp65_rt_l65m_15_entry:runtime+reusable:1:0:l65m_overlay_phase_15' \
	--slice '18:l65m-phase-16:.lisp65_rt_l65m_16:__lisp65_rt_l65m_16_start:__lisp65_rt_l65m_16_end:__lisp65_rt_l65m_16_entry:runtime+reusable:1:0:l65m_overlay_phase_16' \
	--slice '19:l65m-phase-17:.lisp65_rt_l65m_17:__lisp65_rt_l65m_17_start:__lisp65_rt_l65m_17_end:__lisp65_rt_l65m_17_entry:runtime+reusable:1:0:l65m_overlay_phase_17' \
	--slice '20:l65m-phase-18:.lisp65_rt_l65m_18:__lisp65_rt_l65m_18_start:__lisp65_rt_l65m_18_end:__lisp65_rt_l65m_18_entry:runtime+reusable:1:0:l65m_overlay_phase_18' \
	--slice '21:l65m-phase-19:.lisp65_rt_l65m_19:__lisp65_rt_l65m_19_start:__lisp65_rt_l65m_19_end:__lisp65_rt_l65m_19_entry:runtime+reusable:1:0:l65m_overlay_phase_19' \
	--slice '22:l65m-phase-20:.lisp65_rt_l65m_20:__lisp65_rt_l65m_20_start:__lisp65_rt_l65m_20_end:__lisp65_rt_l65m_20_entry:runtime+reusable:1:0:l65m_overlay_phase_20' \
	--slice '23:l65m-commit-00:.lisp65_rt_l65c_00:__lisp65_rt_l65c_00_start:__lisp65_rt_l65c_00_end:__lisp65_rt_l65c_00_entry:runtime+reusable:1:0:l65m_commit_phase_verify' \
	--slice '24:l65m-commit-01:.lisp65_rt_l65c_01:__lisp65_rt_l65c_01_start:__lisp65_rt_l65c_01_end:__lisp65_rt_l65c_01_entry:runtime+reusable:1:0:l65m_commit_phase_patch_record' \
	--slice '25:l65m-commit-02:.lisp65_rt_l65c_02:__lisp65_rt_l65c_02_start:__lisp65_rt_l65c_02_end:__lisp65_rt_l65c_02_entry:runtime+reusable:1:0:l65m_commit_phase_materialize_shape' \
	--slice '26:l65m-commit-03:.lisp65_rt_l65c_03:__lisp65_rt_l65c_03_start:__lisp65_rt_l65c_03_end:__lisp65_rt_l65c_03_entry:runtime+reusable:1:0:l65m_commit_phase_materialize_scalars' \
	--slice '27:l65m-commit-04:.lisp65_rt_l65c_04:__lisp65_rt_l65c_04_start:__lisp65_rt_l65c_04_end:__lisp65_rt_l65c_04_entry:runtime+reusable:1:0:l65m_commit_phase_materialize_strings' \
	--slice '28:l65m-commit-05:.lisp65_rt_l65c_05:__lisp65_rt_l65c_05_start:__lisp65_rt_l65c_05_end:__lisp65_rt_l65c_05_entry:runtime+reusable:1:0:l65m_commit_phase_patch_publish' \
	--slice '29:l65m-commit-06:.lisp65_rt_l65c_06:__lisp65_rt_l65c_06_start:__lisp65_rt_l65c_06_end:__lisp65_rt_l65c_06_entry:runtime+reusable:1:0:l65m_commit_phase_entries' \
	--slice '30:lcc-install-00:.lisp65_rt_lcci_00:__lisp65_rt_lcci_00_start:__lisp65_rt_lcci_00_end:__lisp65_rt_lcci_00_entry:runtime+reusable:1:0:lcc_install_phase_00' \
	--slice '31:lcc-install-01:.lisp65_rt_lcci_01:__lisp65_rt_lcci_01_start:__lisp65_rt_lcci_01_end:__lisp65_rt_lcci_01_entry:runtime+reusable:1:0:lcc_install_phase_01' \
	--slice '32:lcc-install-02:.lisp65_rt_lcci_02:__lisp65_rt_lcci_02_start:__lisp65_rt_lcci_02_end:__lisp65_rt_lcci_02_entry:runtime+reusable:1:0:lcc_install_phase_02' \
	--slice '33:boot-fastpath-verify:.lisp65_rt_boot_00:__lisp65_rt_boot_00_start:__lisp65_rt_boot_00_end:__lisp65_rt_boot_00_entry:boot:1:0:vm_boot_fastpath_phase_verify' \
	--slice '34:boot-fastpath-patches:.lisp65_rt_boot_01:__lisp65_rt_boot_01_start:__lisp65_rt_boot_01_end:__lisp65_rt_boot_01_entry:boot:1:0:vm_boot_fastpath_phase_patches' \
	--slice '35:boot-fastpath-entries-freeze:.lisp65_rt_boot_02:__lisp65_rt_boot_02_start:__lisp65_rt_boot_02_end:__lisp65_rt_boot_02_entry:boot:1:0:vm_boot_fastpath_phase_entries' \
	--slice '36:error-text-renderer:.lisp65_rt_l65e:__lisp65_rt_l65e_start:__lisp65_rt_l65e_end:__lisp65_rt_l65e_entry:runtime+reusable:1:0:lisp65_error_overlay_entry' \
	--slice '37:resident-island-installer:.lisp65_rt_island_00:__lisp65_rt_island_00_start:__lisp65_rt_island_00_end:__lisp65_rt_island_00_entry:boot:1:0:vm_resident_island_install'
WORKBENCH_OVERLAY_MIN_BOOT_STACK_GAP := 512
WORKBENCH_OVERLAY_BOOT_STACK_GAP_TARGET := 1024
WORKBENCH_OVERLAY_MIN_POST_BOOT_RESERVE := 1024
WORKBENCH_OVERLAY_POST_BOOT_RESERVE_TARGET := 1536
WORKBENCH_OVERLAY_EXTRA_DEFINES ?=

# AP4.4 is a separate diagnostic build. It must never replace the canonical
# prototype or become a product input implicitly.
WORKBENCH_OVERLAY_PROBE_DIR := build/products/workbench/overlay-stack-probe
WORKBENCH_OVERLAY_PROBE_RESIDENT_PRG := $(WORKBENCH_OVERLAY_PROBE_DIR)/lisp65-workbench-resident.prg
WORKBENCH_OVERLAY_PROBE_ELF := $(WORKBENCH_OVERLAY_PROBE_DIR)/lisp65-workbench-overlay-linked.prg.elf
WORKBENCH_OVERLAY_PROBE_PRELOAD := $(WORKBENCH_OVERLAY_PROBE_DIR)/stdlib-with-overlay.ext.bin
WORKBENCH_OVERLAY_PROBE_RUNTIME_IMAGE := $(WORKBENCH_OVERLAY_PROBE_DIR)/lisp65-mvp-workbench.overlays.bin
WORKBENCH_OVERLAY_PROBE_REPORT_DIR := build/hw/workbench-overlay-stack-probe
WORKBENCH_OVERLAY_PROBE_MIN_SOFT_MARGIN := 256
WORKBENCH_OVERLAY_PROBE_MIN_HW_REMAINING := 32
WORKBENCH_OVERLAY_PROBE_DEFINES := -DLISP65_BOOT_STACK_PROBE -DLISP65_BOOT_OVERLAY_WIPE

WORKBENCH_OVERLAY_GUARD_DIR := build/products/workbench/overlay-stack-guard
WORKBENCH_OVERLAY_GUARD_RESIDENT_PRG := $(WORKBENCH_OVERLAY_GUARD_DIR)/lisp65-workbench-resident.prg
WORKBENCH_OVERLAY_GUARD_ELF := $(WORKBENCH_OVERLAY_GUARD_DIR)/lisp65-workbench-overlay-linked.prg.elf
WORKBENCH_OVERLAY_GUARD_PRELOAD := $(WORKBENCH_OVERLAY_GUARD_DIR)/stdlib-with-overlay.ext.bin
WORKBENCH_OVERLAY_GUARD_RUNTIME_IMAGE := $(WORKBENCH_OVERLAY_GUARD_DIR)/lisp65-mvp-workbench.overlays.bin
WORKBENCH_OVERLAY_GUARD_RUNTIME_MANIFEST := $(WORKBENCH_OVERLAY_GUARD_DIR)/runtime-overlays-manifest.json
WORKBENCH_OVERLAY_GUARD_REPORT_DIR := build/hw/workbench-overlay-stack-guard
WORKBENCH_OVERLAY_GUARD_DEFINES := -DLISP65_STACK_GUARD
WORKBENCH_OVERLAY_GUARD_STAGE_MANIFEST := $(WORKBENCH_OVERLAY_GUARD_DIR)/stage-manifest.json
WORKBENCH_OVERLAY_GUARD_CONTROL_AUDIT_REPORT := $(WORKBENCH_OVERLAY_GUARD_DIR)/control-audit.json
WORKBENCH_OVERLAY_GUARD_FOOTPRINT_REPORT := $(WORKBENCH_OVERLAY_GUARD_DIR)/footprint-audit.json
WORKBENCH_OVERLAY_GUARD_FOOTPRINT := $(WORKBENCH_OVERLAY_GUARD_FOOTPRINT_REPORT)
WORKBENCH_OVERLAY_GUARD_ABI_CONTRACT := $(WORKBENCH_OVERLAY_GUARD_DIR)/resolved-profile.txt

# Canonical interactive product: guarded resident PRG plus its bound combined
# stdlib/overlay preload. The former flat binary is a reference target only.
WORKBENCH_PRG := $(WORKBENCH_OVERLAY_GUARD_RESIDENT_PRG)
WORKBENCH_PRODUCT_ELF := $(WORKBENCH_OVERLAY_GUARD_ELF)
WORKBENCH_PRODUCT_PRELOAD := $(WORKBENCH_OVERLAY_GUARD_PRELOAD)
WORKBENCH_PRODUCT_RUNTIME_OVERLAY := $(WORKBENCH_OVERLAY_GUARD_RUNTIME_IMAGE)
WORKBENCH_PRODUCT_RUNTIME_OVERLAY_MANIFEST := $(WORKBENCH_OVERLAY_GUARD_RUNTIME_MANIFEST)
WORKBENCH_FOOTPRINT_REPORT := $(WORKBENCH_OVERLAY_GUARD_FOOTPRINT_REPORT)

WORKBENCH_CFLAGS := -Oz -Wall
WORKBENCH_HEAP_CELLS := 48
WORKBENCH_TARGET_SRCS := src/mega65_math.s src/l65m_batch_repeat.s src/f011_guarded_write.s
WORKBENCH_MATH_LINK_ALIASES := \
	-Wl,--defsym=__udivhi3=lisp65_hw_udivhi3 \
	-Wl,--defsym=__umodhi3=lisp65_hw_umodhi3 \
	-Wl,--defsym=__udivmodhi4=lisp65_hw_udivmodhi4 \
	-Wl,--defsym=__mulhi3=lisp65_hw_mulhi3 \
	-Wl,--defsym=__divhi3=lisp65_hw_divhi3 \
	-Wl,--defsym=__modhi3=lisp65_hw_modhi3
WORKBENCH_LDFLAGS := -Wl,--icf=all $(WORKBENCH_MATH_LINK_ALIASES)
WORKBENCH_DEFINES := \
	-DLISP65_MEGA65_MATH_OVERRIDE \
	-DLISP65_F011_GUARD_ASM \
	-DVM_CODEBUF=56 \
	-DLISP65_SYMPOOL_EXT \
	-DLISP65_SYMVAL_EXT \
	-DLISP65_NAMEOFF_EXT \
	-DGC_ROOTS=128 \
	-DLISP65_STDLIB_EXT_METADATA \
	-DLISP65_STDLIB_EXTERNAL_BLOB \
	-DLISP65_MARK_BITMAP \
	-DLISP65_EXT_HEAP \
	-DLISP65_SCREEN_DRIVER \
	-DLISP65_VM_SCREEN_PRIMS \
	-DLISP65_VM_STDLIB_IO_WRAPPERS \
	-DLISP65_VM_GLOBAL_PRIMS \
	-DLISP65_MACROEXPAND_PRIM \
	-DLISP65_LCC_INSTALL \
	-DLISP65_LCC_INSTALL_OVERLAY_SLOT_BASE=30 \
	-DLISP65_BOOT_FASTPATH_SLOT_BASE=33 \
	-DLISP65_ERROR_OVERLAY \
	-DLISP65_ERROR_OVERLAY_SLOT=36 \
	-DLISP65_LCC_INSTALL_CLOSURES \
	-DLISP65_TREEWALK_STDLIB_BRIDGES \
	-DLISP65_OUTPUT_WRAPPERS_IN_STDLIB \
	-DLISP65_SCREEN_BULK_P_IN_STDLIB \
	-DLISP65_TREEWALK_STRIP \
	-DMEGA65_F011_LOAD \
	-DLISP65_DISK_LIBS \
	-DMEGA65_F011_WRITE \
	-DIO_BUF_MAX=1 \
	-DEXT_CELLS=1024 \
	-DLISP65_NURSERY_HYSTERESIS=192 \
	-DLISP65_STRING_ARENA \
	-DSTR_ARENA_SIZE=0x2480 \
	-DDISK_EXT_BASE=0x6900 \
	-DDISK_EXT_FILE_MAX=0x9600 \
	-DLISP65_COMPILE_STRING \
	-DLISP65_SYMFN_EXT \
	-DSYMPOOL_EXT_OFF=0xc680 \
	-DNAMEPOOL=10208 \
	-DMAX_SYM=752 \
	-DVM_DIR_MAX=608 \
	-DREPL_BUF_MAX=192 \
	-DHIST_MAX=64 \
	-DLISP65_REPL_HISTORY_IN_BUF

# Derive the staging ceiling from the canonical profile define.  Descriptor
# plus payload must remain below the Bank-5 namepool, not merely below $10000.
WORKBENCH_OVERLAY_STAGE_LIMIT = $(patsubst -DSYMPOOL_EXT_OFF=%,%,$(filter -DSYMPOOL_EXT_OFF=%,$(WORKBENCH_DEFINES)))

WORKBENCH_MIN_STACK_GAP := 1450
WORKBENCH_MIN_BOOT_STACK_GAP := 512
WORKBENCH_MIN_BANK0_RESERVE := 0
WORKBENCH_BANK0_RESERVE_TARGET := 1024
WORKBENCH_MAX_PRG_FILE_END := 0xc0c0
WORKBENCH_MIN_SYMBOL_HEADROOM := 32
WORKBENCH_BOOT_SYMBOL_CORRECTION := 8
# The hardware-minus-manifest calibration was +5/+51 while peek/poke were
# already installed by eval_init but absent from the manifest census.  Their
# LCC Prim rows now make both names statically visible, so subtract that exact
# 2-symbol/10-byte overlap rather than counting the same runtime names twice.
WORKBENCH_COMPOSITION_SYMBOL_CORRECTION := 3
WORKBENCH_COMPOSITION_NAMEPOOL_CORRECTION := 41

WORKBENCH_MIN_LOAD_HEADROOM := 32
WORKBENCH_MIN_POST_ALIGN_HEADROOM := 32
WORKBENCH_MIN_EXT_CODE_PEAK_HEADROOM := 128
WORKBENCH_MIN_EXT_CODE_POST_HEADROOM := 16384
WORKBENCH_MIN_NAMEPOOL_HEADROOM := 384
WORKBENCH_DISK_FILE_MAX := 0x9600

# Compatibility names for scripts and out-of-tree callers. Product rules below
# use the WORKBENCH_* variables directly.
M65VMSTDLIBEINSUITECOREWORKBENCHPRG := $(WORKBENCH_REFERENCE_PRG)
BYTECODE_STDLIB_EINSUITE_CORE_WORKBENCH_SUITE := $(WORKBENCH_SUITE)
MVP_VM_STDLIB_EINSUITE_CORE_WORKBENCH_FOOTPRINT_REPORT := $(WORKBENCH_REFERENCE_FOOTPRINT_REPORT)
M65VMSTDLIB_EINSUITE_CORE_WORKBENCH_EXTRA_CFLAGS := $(WORKBENCH_DEFINES)
M65VMSTDLIB_EINSUITE_CORE_WORKBENCH_LDFLAGS := $(WORKBENCH_LDFLAGS)
WORKBENCH_CANDIDATE_TARGET := $(WORKBENCH_BUILD_TARGET)
WORKBENCH_CANDIDATE_FOOTPRINT_TARGET := $(WORKBENCH_FOOTPRINT_TARGET)

export WORKBENCH_PROFILE_ID WORKBENCH_FOOTPRINT_TARGET WORKBENCH_PRG
export WORKBENCH_SUITE WORKBENCH_FOOTPRINT_REPORT
export WORKBENCH_STDLIB_EXT_BLOB WORKBENCH_STDLIB_MANIFEST
export WORKBENCH_PRODUCT_PRELOAD WORKBENCH_PRODUCT_RUNTIME_OVERLAY
export WORKBENCH_PRODUCT_RUNTIME_OVERLAY_MANIFEST
