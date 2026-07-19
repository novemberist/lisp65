# Canonical Workbench product, packaging, and release rules.

.PHONY: v11-c1-repl-latency-check v11-source-stream-lifetime-selftest v11-source-stream-lifetime-check v11-wave2-error-text-library-check v11-wave2-list-unification-selftest v11-wave2-list-unification-check v11-wave2-policy-name-implementation-collect v11-wave2-policy-name-implementation-check v11-wave2-common-repin-collect v11-wave2-common-repin-check v11-function-metadata-selftest v11-function-metadata-check v11-l-lite-keymap-check v11-l-lite-keymap-dry-check v11-color-scroll-binding-check v11-wave3-fail-fast-check v11-wave3-dry-smoke v11-l-lite-probe-check v11-wave3-l-lite-repin-collect v11-wave3-l-lite-repin-check

v11-l-lite-keymap-check:
	python3 tools/host-lisp/v11_l_lite_keymap.py selftest
	python3 tools/host-lisp/v11_l_lite_keymap.py check

v11-color-scroll-binding-check:
	python3 tools/host-lisp/v11_color_scroll_binding.py selftest
	python3 tools/host-lisp/v11_color_scroll_binding.py check

v11-wave3-fail-fast-check: v11-l-lite-keymap-check v11-color-scroll-binding-check
	python3 tools/host-lisp/v11_wave3_fail_fast.py selftest
	python3 tools/host-lisp/v11_wave3_fail_fast.py check

v11-l-lite-keymap-dry-check: v11-l-lite-keymap-check
	python3 tools/host-lisp/ide_ui_eval_oracle.py
	$(MAKE) v2-workbench-codemod
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check \
		build/bytecode/dialect-v2/suites/p0-ide-core-lib.json \
		build/bytecode/dialect-v2/suites/p0-ide-extra-lib.json

v11-wave3-dry-smoke: v11-l-lite-keymap-dry-check v11-wave3-fail-fast-check error-overlay-smoke screen-smoke hw-edma-screen-smoke-prg

v11-l-lite-probe-check:
	python3 tools/host-lisp/v11_l_lite_probe.py selftest
	python3 tools/host-lisp/v11_l_lite_probe.py check

v11-wave3-l-lite-repin-collect: workbench-overlay-stack-guard v2-workbench-library-composition-check
	python3 tools/host-lisp/v11_wave3_l_lite_repin.py collect

v11-wave3-l-lite-repin-check: workbench-overlay-stack-guard v2-workbench-library-composition-check
	python3 tools/host-lisp/v11_wave3_l_lite_repin.py check


v11-wave2-error-text-library-check:
	python3 tools/host-lisp/v11_wave2_error_text_library.py check

v11-wave2-list-unification-selftest:
	python3 tools/host-lisp/v11_wave2_list_unification.py selftest

v11-wave2-list-unification-check: v11-wave2-list-unification-selftest
	python3 tools/host-lisp/v11_wave2_list_unification.py check

v11-wave2-policy-name-implementation-collect: v2-workbench-artifacts
	python3 tools/host-lisp/v11_wave2_policy_name_implementation.py collect

v11-wave2-policy-name-implementation-check: v2-workbench-artifacts
	python3 tools/host-lisp/v11_wave2_policy_name_implementation.py check

v11-wave2-common-repin-collect: workbench-overlay-stack-guard v2-workbench-library-composition-check
	python3 tools/host-lisp/v11_wave2_common_repin.py collect

v11-wave2-common-repin-check: workbench-overlay-stack-guard v2-workbench-library-composition-check
	python3 tools/host-lisp/v11_wave2_common_repin.py check

v11-function-metadata-selftest: v2-workbench-artifacts bytecode-p0-buffer-lib-artifacts v11-c1-compiler-tier-artifacts
	python3 tools/host-lisp/v11_function_metadata.py selftest

v11-function-metadata-check: v11-function-metadata-selftest
	python3 tools/host-lisp/v11_function_metadata.py check

.PHONY: l65m-verdict-equivalence-selftest l65m-verdict-equivalence-gate asm-c-constant-contract-selftest asm-c-constant-contract-check f011-transaction-context-selftest f011-transaction-context-check f011-mount-window-selftest workbench-f011-mount-window-audit

.PHONY: bank0-lifetime-report bank0-lifetime-selftest bank0-island-inventory-report bank0-island-inventory-selftest vm-ext-code-reclaim-smoke mega65-math-override-check error-text-table-selftest error-code-contract-selftest error-overlay-smoke workbench-error-code-contract-check resident-island-selftest runtime-overlay-bank-selftest runtime-overlay-transport-smoke attic-library-shelf-selftest attic-library-shelf-check v11-c1-compiler-tier-artifacts v11-c1-compiler-lifetime-check v11-c1-entry-seam-check v11-c1-gate-check v11-wave1-c1-first-form-selftest v11-wave1-c1-first-form-check v11-first-class-buffer-check l65m-bulkread-fixture-check workbench-l65m-transport-ops-report workbench-l65m-commit-ops-report workbench-runtime-overlay-package-verify workbench-disk-lib-budget-selftest persistence-contract-check d81-persistence-fault-selftest workbench-product-contract-selftest workbench-product-contract-check workbench-product-contract-ship-check workbench-deploy workbench-deploy-dry-run workbench-product workbench-product-footprint-report workbench-product-input-ready workbench-reference workbench-reference-footprint-report workbench-overlay-link-prototype workbench-overlay-prototype workbench-overlay-package-verify workbench-overlay-footprint-audit workbench-overlay-control-audit workbench-overlay-control-audit-selftest workbench-overlay-bootstrap-smoke workbench-overlay-reproducibility-check workbench-overlay-stage-selftest workbench-overlay-stack-probe workbench-overlay-stack-probe-smoke workbench-overlay-stack-guard hw-stack-probe-readback-selftest hw-ship-memory-readback-selftest hw-workbench-overlay-stack-readback hw-workbench-overlay-stack-readback-dry-run hw-workbench-overlay-stack-smoke hw-workbench-overlay-stack-smoke-dry-run hw-workbench-overlay-stack-guard-smoke hw-workbench-overlay-stack-guard-smoke-dry-run hw-workbench-overlay-stack-guard-verified-smoke print-workbench-profile-common print-workbench-reference-resolved-profile print-workbench-resolved-profile print-workbench-overlay-resolved-profile mvp-ship-candidate-artifacts

workbench-product-contract-selftest:
	python3 tools/host-lisp/workbench_product_contract.py --selftest

workbench-product-contract-check: workbench-product-contract-selftest
	python3 tools/host-lisp/workbench_product_contract.py

VM_EXT_CODE_RECLAIM_SMOKE_HOST := build/vm-ext-code-reclaim-smoke-host
WORKBENCH_OVERLAY_BOOTSTRAP_SMOKE_HOST := build/workbench-overlay-bootstrap-smoke-host
WORKBENCH_OVERLAY_STACK_PROBE_SMOKE_HOST := build/workbench-overlay-stack-probe-smoke-host
WORKBENCH_RUNTIME_OVERLAY_SMOKE_HOST := build/runtime-overlay-smoke-host
V11_BUFFER_MEMORY_HOST := build/v11-buffer-smoke-host
V11_BUFFER_CARRIER_HOST := build/v11-buffer-carrier-host
F011_TRANSACTION_CONTEXT_HOST := build/f011-transaction-context-host
WORKBENCH_L65M_TRANSPORT_OPS_HOST := build/l65m-transport-ops-host
WORKBENCH_L65M_TRANSPORT_OPS_REPORT ?= build/bytecode/workbench-l65m-transport-ops.txt
WORKBENCH_L65M_COMMIT_OPS_TOOL := scripts/l65m-commit-ops.py
WORKBENCH_L65M_COMMIT_OPS_REPORT ?= build/bytecode/workbench-l65m-commit-ops.txt
WORKBENCH_L65M_BULKREAD_FIXTURE_TOOL := tools/host-lisp/l65m_bulkread_fixtures.py
WORKBENCH_L65M_BULKREAD_FIXTURE_HEADER := build/l65m-bulkread-cases.h
WORKBENCH_L65M_VERDICT_GATE_TOOL := tools/host-lisp/l65m_verdict_gate.py
WORKBENCH_L65M_VERDICT_GATE_DIR := build/l65m-verdict-diff
WORKBENCH_L65M_VERDICT_GATE_REPORT := build/bytecode/workbench-l65m-verdict-diff.txt
ASM_C_CONSTANT_CONTRACT_TOOL := tools/host-lisp/asm_c_constant_contract.py
ASM_C_CONSTANT_CONTRACT_SPEC := config/asm-c-constant-contract.json
ASM_C_CONSTANT_CONTRACT_GENERATOR := scripts/asm-c-contract-values-main.c
ASM_C_CONSTANT_CONTRACT_INCLUDE := build/generated/asm-c-contract.inc

$(ASM_C_CONSTANT_CONTRACT_INCLUDE): $(ASM_C_CONSTANT_CONTRACT_TOOL) $(ASM_C_CONSTANT_CONTRACT_SPEC) $(ASM_C_CONSTANT_CONTRACT_GENERATOR) src/l65m_batch_contract.h src/l65m_overlay_abi.h src/l65m_commit_overlay.h src/l65m_validate.h src/vm_runtime_overlay.h scripts/r3-cold-stager-contract.h | build
	python3 $(ASM_C_CONSTANT_CONTRACT_TOOL) generate --cc '$(HOSTCC)' --out '$@'

src/l65m_batch_repeat.s scripts/r3-cold-stager-chain.s: | $(ASM_C_CONSTANT_CONTRACT_INCLUDE)

asm-c-constant-contract-selftest:
	python3 $(ASM_C_CONSTANT_CONTRACT_TOOL) selftest

asm-c-constant-contract-check: asm-c-constant-contract-selftest $(ASM_C_CONSTANT_CONTRACT_INCLUDE)
	python3 $(ASM_C_CONSTANT_CONTRACT_TOOL) check --cc '$(HOSTCC)' --out '$(ASM_C_CONSTANT_CONTRACT_INCLUDE)'

$(F011_TRANSACTION_CONTEXT_HOST): scripts/f011-context-main.c src/f011_context.h | build
	$(HOSTCC) -std=c99 -Wall -Wextra -Werror -Isrc scripts/f011-context-main.c -o '$@'

f011-transaction-context-selftest: $(F011_TRANSACTION_CONTEXT_HOST)
	$(F011_TRANSACTION_CONTEXT_HOST)

f011-transaction-context-check: f011-transaction-context-selftest
	python3 tools/host-lisp/f011_transaction_context.py

f011-mount-window-selftest:
	python3 tools/host-lisp/f011_mount_window.py --selftest

$(VM_EXT_CODE_RECLAIM_SMOKE_HOST): scripts/vm-ext-code-reclaim-smoke-main.c src/vm_embed.c src/vm_embed.h mk/workbench.mk | build
	$(HOSTCC) -std=c99 -Wall -Wextra -Wno-unused-function -ffunction-sections -fdata-sections \
		-DLISP65_VM -DLISP65_DISK_LIBS -DLISP65_C1_COMPILER_TIER \
		-DLISP65_VM_EXT_CODE_TEST -DLISP65_SYMPOOL_EXT -DSYMPOOL_EXT_OFF=0x0100 \
		-Isrc scripts/vm-ext-code-reclaim-smoke-main.c src/vm_embed.c \
		-Wl,--gc-sections -o $@

vm-ext-code-reclaim-smoke: $(VM_EXT_CODE_RECLAIM_SMOKE_HOST)
	$(VM_EXT_CODE_RECLAIM_SMOKE_HOST)

$(WORKBENCH_OVERLAY_BOOTSTRAP_SMOKE_HOST): scripts/workbench-overlay-bootstrap-smoke-main.c src/vm_boot_overlay.c src/vm_boot_overlay.h | build
	$(HOSTCC) -std=c99 -Wall -Wextra -Werror \
		-DLISP65_VM -DLISP65_STAGED_BOOT_OVERLAY -DLISP65_BOOT_OVERLAY_HOST_TEST -DLISP65_EXT_HEAP \
		-DLISP65_BOOT_OVERLAY_STAGE_BANK=7 -DLISP65_BOOT_OVERLAY_STAGE_OFF=0x2200 \
		-DLISP65_BOOT_OVERLAY_PROFILE_BUILD_ID=0x91e2a34cUL \
		-Isrc scripts/workbench-overlay-bootstrap-smoke-main.c src/vm_boot_overlay.c -o '$@'

workbench-overlay-bootstrap-smoke: $(WORKBENCH_OVERLAY_BOOTSTRAP_SMOKE_HOST)
	$(WORKBENCH_OVERLAY_BOOTSTRAP_SMOKE_HOST)

$(WORKBENCH_OVERLAY_STACK_PROBE_SMOKE_HOST): scripts/workbench-overlay-stack-probe-smoke-main.c src/vm_boot_overlay.c src/vm_boot_overlay.h | build
	$(HOSTCC) -std=c99 -Wall -Wextra -Werror \
		-DLISP65_VM -DLISP65_STAGED_BOOT_OVERLAY -DLISP65_BOOT_OVERLAY_HOST_TEST -DLISP65_EXT_HEAP \
		-DLISP65_BOOT_STACK_PROBE -DLISP65_BOOT_OVERLAY_WIPE \
		-DLISP65_BOOT_OVERLAY_STAGE_BANK=7 -DLISP65_BOOT_OVERLAY_STAGE_OFF=0x2200 \
		-DLISP65_BOOT_OVERLAY_PROFILE_BUILD_ID=0x91e2a34cUL \
		-Isrc scripts/workbench-overlay-stack-probe-smoke-main.c src/vm_boot_overlay.c -o '$@'

workbench-overlay-stack-probe-smoke: $(WORKBENCH_OVERLAY_STACK_PROBE_SMOKE_HOST)
	$(WORKBENCH_OVERLAY_STACK_PROBE_SMOKE_HOST)

$(WORKBENCH_RUNTIME_OVERLAY_SMOKE_HOST): scripts/runtime-overlay-smoke-main.c src/vm_runtime_overlay.c src/vm_runtime_overlay.h src/vm.h | build
	$(HOSTCC) -std=c99 -Wall -Wextra -Werror -fsanitize=address,undefined \
		-DLISP65_VM -DLISP65_RUNTIME_OVERLAY_HOST_TEST -Isrc \
		scripts/runtime-overlay-smoke-main.c src/vm_runtime_overlay.c -o '$@'

runtime-overlay-transport-smoke: $(WORKBENCH_RUNTIME_OVERLAY_SMOKE_HOST)
	ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 $(WORKBENCH_RUNTIME_OVERLAY_SMOKE_HOST)

$(V11_BUFFER_MEMORY_HOST): scripts/v11-buffer-smoke-main.c src/mem.c src/mem.h src/obj.h src/printer.c src/printer.h src/symbol.c src/interrupt.c | build
	$(HOSTCC) -std=c99 -Wall -Wextra -Werror -O1 -g \
		-fsanitize=address,undefined -fno-omit-frame-pointer \
		-DLISP65_STRING_ARENA -DLISP65_FIRST_CLASS_BUFFER \
		-DHEAP_CELLS=128 -DGC_ROOTS=64 -DSTR_ARENA_SIZE=256 \
		-DMAX_SYM=64 -DNAMEPOOL=512 -Isrc \
		scripts/v11-buffer-smoke-main.c src/mem.c src/printer.c src/symbol.c src/interrupt.c -o '$@'

$(V11_BUFFER_CARRIER_HOST): scripts/v11-buffer-carrier-main.c src/buffer_overlay.c src/buffer_overlay.h src/mem.c src/mem.h src/obj.h src/symbol.c src/interrupt.c | build
	$(HOSTCC) -std=c99 -Wall -Wextra -Werror -O1 -g \
		-fsanitize=address,undefined -fno-omit-frame-pointer \
		-DLISP65_STRING_ARENA -DLISP65_FIRST_CLASS_BUFFER \
		-DHEAP_CELLS=128 -DGC_ROOTS=64 -DSTR_ARENA_SIZE=256 \
		-DMAX_SYM=64 -DNAMEPOOL=512 -Isrc \
		scripts/v11-buffer-carrier-main.c src/buffer_overlay.c src/mem.c \
		src/symbol.c src/interrupt.c -o '$@'

v11-first-class-buffer-check: v2-native-function-registry-check bytecode-p0-buffer-lib-artifacts attic-library-shelf-check v11-buffer-library-composition-check $(V11_BUFFER_MEMORY_HOST) $(V11_BUFFER_CARRIER_HOST)
	output="$$(ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 $(V11_BUFFER_MEMORY_HOST))"; \
		test "$$output" = '?' || { echo "v11-buffer-printer: FAIL output=$$output" >&2; exit 1; }; \
		echo 'v11-buffer-printer: PASS output=?'
	python3 tools/host-lisp/v11_buffer_oracle.py --selftest --binary $(V11_BUFFER_CARRIER_HOST)

V11_C1_FASTPATH_VALIDATOR_HOST := build/v11-c1-fastpath-validator-host

$(V11_C1_FASTPATH_VALIDATOR_HOST): scripts/l65m-transport-ops-main.c src/l65m_validate.c \
		src/vm_runtime_overlay.c src/l65m_overlay_abi.h src/l65m_validate.h \
		src/vm_runtime_overlay.h $(WORKBENCH_L65M_BULKREAD_FIXTURE_HEADER) | build
	$(HOSTCC) -std=c99 -Wall -Wextra -Werror \
		-DLISP65_VM -DLISP65_DISK_LIBS -DLISP65_DIALECT_V2 \
		-DLISP65_RUNTIME_OVERLAY_HOST_TEST \
		-DLISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_OFF=0x1000u \
		-DLISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_FILE_OFF=0x1100u \
		-Isrc -Ibuild scripts/l65m-transport-ops-main.c src/l65m_validate.c \
		src/vm_runtime_overlay.c -o '$@'

v11-c1-compiler-tier-artifacts: v2-workbench-codemod $(V11_C1_FASTPATH_VALIDATOR_HOST)
	python3 $(WORKBENCH_C1_COMPILER_TOOL) --selftest
	python3 $(WORKBENCH_C1_COMPILER_CONTRACT_TOOL) --selftest
	python3 $(WORKBENCH_C1_COMPILER_TOOL) --out '$(WORKBENCH_C1_COMPILER_SUITE)' \
		--receipt '$(WORKBENCH_C1_COMPILER_GENERATION)'
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check --emit-artifacts \
		'$(WORKBENCH_C1_COMPILER_PREFIX)' --artifact-role disk-lib --base-addr 0x000000 \
		'$(WORKBENCH_C1_COMPILER_SUITE)'
	$(V11_C1_FASTPATH_VALIDATOR_HOST) \
		--image '$(WORKBENCH_C1_COMPILER_PREFIX).ext.bin' \
		--integration src/vm_embed.c --scratch-source src/io.c \
		--out '$(WORKBENCH_C1_COMPILER_VALIDATOR_REPORT)'
	python3 $(WORKBENCH_C1_COMPILER_CONTRACT_TOOL) \
		--manifest '$(WORKBENCH_C1_COMPILER_PREFIX).manifest.json' \
		--container '$(WORKBENCH_C1_COMPILER_PREFIX).ext.bin' \
		--shelf-contract '$(WORKBENCH_ATTIC_SHELF_CONTRACT)' \
		--validator-report '$(WORKBENCH_C1_COMPILER_VALIDATOR_REPORT)' \
		--header '$(WORKBENCH_C1_COMPILER_CONTRACT_HEADER)' \
		--receipt '$(WORKBENCH_C1_COMPILER_CONTRACT_RECEIPT)'

V11_C1_COMPILER_LIFETIME_HOST := build/v11-c1-compiler-lifetime-host

V11_C1_TRUST_FASTPATH_HOST := build/v11-c1-trust-fastpath-host

$(V11_C1_TRUST_FASTPATH_HOST): v11-c1-compiler-tier-artifacts \
		scripts/l65m-transport-ops-main.c src/l65m_validate.c \
		src/vm_runtime_overlay.c src/l65m_overlay_abi.h src/l65m_validate.h \
		src/vm_runtime_overlay.h $(WORKBENCH_L65M_BULKREAD_FIXTURE_HEADER) | build
	$(HOSTCC) -std=c99 -Wall -Wextra -Werror \
		-DLISP65_VM -DLISP65_DISK_LIBS -DLISP65_DIALECT_V2 \
		-DLISP65_C1_TRUST_FASTPATH_PROBE \
		-DLISP65_RUNTIME_OVERLAY_HOST_TEST \
		-DLISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_OFF=0x1000u \
		-DLISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_FILE_OFF=0x1100u \
		-Isrc -Ibuild -Ibuild/bytecode scripts/l65m-transport-ops-main.c \
		src/l65m_validate.c src/vm_runtime_overlay.c -o '$@'

v11-c1-trust-fastpath-check: $(V11_C1_TRUST_FASTPATH_HOST)
	$(V11_C1_TRUST_FASTPATH_HOST) --fastpath-selftest \
		--image '$(WORKBENCH_C1_COMPILER_PREFIX).ext.bin'

$(V11_C1_COMPILER_LIFETIME_HOST): v11-c1-compiler-tier-artifacts scripts/v11-c1-compiler-lifetime-main.c src/c1_compiler_overlay.c src/c1_compiler_overlay.h src/buffer_overlay.h src/io.h src/symbol.h src/vm.h src/vm_embed.c src/vm_embed.h | build
	$(HOSTCC) -std=c99 -Wall -Wextra -Werror -Wno-unused-function \
		-ffunction-sections -fdata-sections -fsanitize=address,undefined \
		-DLISP65_VM -DLISP65_DISK_LIBS -DLISP65_C1_COMPILER_TIER \
		-DLISP65_VM_EXT_CODE_TEST -DLISP65_SYMPOOL_EXT -DSYMPOOL_EXT_OFF=0xf000 \
		-DHEAP_CELLS=64 \
		-Isrc -Ibuild/bytecode scripts/v11-c1-compiler-lifetime-main.c \
		src/c1_compiler_overlay.c src/vm_embed.c -Wl,--gc-sections -o '$@'

v11-c1-compiler-lifetime-check: v11-c1-compiler-tier-artifacts $(V11_C1_COMPILER_LIFETIME_HOST)
	ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 \
		$(V11_C1_COMPILER_LIFETIME_HOST)

V11_C1_LEASE_HOST := build/v11-c1-lease-host

$(V11_C1_LEASE_HOST): v11-c1-compiler-tier-artifacts scripts/v11-c1-lease-main.c src/c1_compiler_overlay.c src/c1_compiler_overlay.h src/vm_embed.c src/vm_embed.h | build
	$(HOSTCC) -std=c99 -Wall -Wextra -Werror -Wno-unused-function \
		-ffunction-sections -fdata-sections -fsanitize=address,undefined \
		-DLISP65_VM -DLISP65_DISK_LIBS -DLISP65_C1_COMPILER_TIER \
		-DLISP65_C1_LEASE_ALLOC_GUARD \
		-DLISP65_VM_EXT_CODE_TEST \
		-DLISP65_SYMPOOL_EXT -DSYMPOOL_EXT_OFF=0xf000 -DHEAP_CELLS=64 \
		-Isrc -Ibuild/bytecode scripts/v11-c1-lease-main.c \
		src/c1_compiler_overlay.c src/vm_embed.c -Wl,--gc-sections -o '$@'

v11-c1-lease-check: $(V11_C1_LEASE_HOST)
	ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 $(V11_C1_LEASE_HOST)

v11-c1-entry-seam-check: config/v11-c1-entry-seams.json config/v11-c1-architecture-decision.json tools/host-lisp/v11_c1_entry_seams.py
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v11_c1_entry_seams.py --selftest
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v11_c1_entry_seams.py

v11-c1-repl-latency-check: config/v11-c1-architecture-decision.json tools/host-lisp/v11_c1_repl_latency.py
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v11_c1_repl_latency.py --selftest

v11-wave1-c1-first-form-selftest:
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v11_wave1_c1_first_form.py --selftest

v11-wave1-c1-first-form-check: v11-wave1-c1-first-form-selftest
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v11_wave1_c1_first_form.py --verify

v11-source-stream-lifetime-selftest:
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v11_source_stream_lifetime.py --selftest

v11-source-stream-lifetime-check: workbench-overlay-stack-guard
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v11_source_stream_lifetime.py

v11-c1-gate-check: v2-native-function-registry-check bytecode-abi-ledger-check \
	v11-first-class-buffer-check v11-c1-compiler-lifetime-check v11-c1-entry-seam-check \
	v11-c1-repl-latency-check \
	v2-workbench-library-composition-check v2-workbench-differential \
	bank0-island-inventory-report workbench-product
	python3 $(WORKBENCH_C1_GATE_TOOL) --selftest
	python3 $(WORKBENCH_C1_GATE_TOOL) --out '$(WORKBENCH_C1_GATE_RECEIPT)'

$(WORKBENCH_ATTIC_SHELF_IMAGE) $(WORKBENCH_ATTIC_SHELF_MANIFEST) &: \
		$(WORKBENCH_ATTIC_SHELF_TOOL) $(WORKBENCH_ATTIC_SHELF_CONTRACT) \
		v2-workbench-artifacts bytecode-p0-buffer-lib-artifacts \
		v11-c1-compiler-tier-artifacts
	python3 $(WORKBENCH_ATTIC_SHELF_TOOL) --out '$(WORKBENCH_ATTIC_SHELF_IMAGE)' --manifest-out '$(WORKBENCH_ATTIC_SHELF_MANIFEST)'

$(WORKBENCH_ATTIC_SHELF_HOST): scripts/attic-library-shelf-smoke-main.c src/attic_library_shelf.c src/attic_library_shelf.h src/io.h | build
	$(HOSTCC) -std=c99 -Wall -Wextra -Werror -fsanitize=address,undefined \
		-DLISP65_ATTIC_LIBRARY_SHELF -DLISP65_ATTIC_LIBRARY_SHELF_HOST_TEST \
		-DDISK_EXT_FILE_MAX=0x9600u -Isrc \
		scripts/attic-library-shelf-smoke-main.c src/attic_library_shelf.c -o '$@'

attic-library-shelf-selftest: v2-workbench-artifacts bytecode-p0-buffer-lib-artifacts v11-c1-compiler-tier-artifacts
	python3 $(WORKBENCH_ATTIC_SHELF_TOOL) --selftest \
		--out '$(WORKBENCH_ATTIC_SHELF_IMAGE)' --manifest-out '$(WORKBENCH_ATTIC_SHELF_MANIFEST)'

attic-library-shelf-check: attic-library-shelf-selftest $(WORKBENCH_ATTIC_SHELF_IMAGE) $(WORKBENCH_ATTIC_SHELF_MANIFEST) $(WORKBENCH_ATTIC_SHELF_HOST)
	python3 $(WORKBENCH_ATTIC_SHELF_TOOL) --verify \
		--out '$(WORKBENCH_ATTIC_SHELF_IMAGE)' --manifest-out '$(WORKBENCH_ATTIC_SHELF_MANIFEST)'
	ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 \
		$(WORKBENCH_ATTIC_SHELF_HOST) '$(WORKBENCH_ATTIC_SHELF_IMAGE)'

$(WORKBENCH_L65M_BULKREAD_FIXTURE_HEADER): $(WORKBENCH_L65M_BULKREAD_FIXTURE_TOOL) tools/host-lisp/l65m_contract.py | build
	python3 $(WORKBENCH_L65M_BULKREAD_FIXTURE_TOOL) --emit-c-header '$@'

l65m-bulkread-fixture-check: $(WORKBENCH_L65M_BULKREAD_FIXTURE_HEADER)
	python3 $(WORKBENCH_L65M_BULKREAD_FIXTURE_TOOL) --check-c-header '$<'

l65m-verdict-equivalence-selftest:
	python3 $(WORKBENCH_L65M_VERDICT_GATE_TOOL) --selftest

l65m-verdict-equivalence-gate: l65m-verdict-equivalence-selftest l65m-bulkread-fixture-check
	python3 $(WORKBENCH_L65M_VERDICT_GATE_TOOL) \
		--repo . --hostcc '$(HOSTCC)' \
		--build-dir '$(WORKBENCH_L65M_VERDICT_GATE_DIR)' \
		--report '$(WORKBENCH_L65M_VERDICT_GATE_REPORT)'

$(WORKBENCH_L65M_TRANSPORT_OPS_HOST): scripts/l65m-transport-ops-main.c src/l65m_validate.c src/vm_runtime_overlay.c src/l65m_overlay_abi.h src/l65m_validate.h src/vm_runtime_overlay.h $(WORKBENCH_L65M_BULKREAD_FIXTURE_HEADER) | build
	$(HOSTCC) -std=c99 -Wall -Wextra -Werror \
		-DLISP65_VM -DLISP65_DISK_LIBS -DLISP65_RUNTIME_OVERLAY_HOST_TEST \
		-DLISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_OFF=0x1000u \
		-DLISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_FILE_OFF=0x1100u -Isrc -Ibuild \
		scripts/l65m-transport-ops-main.c src/l65m_validate.c src/vm_runtime_overlay.c -o '$@'

workbench-l65m-transport-ops-report: bytecode-p0-ide-lib-artifacts l65m-contract-check l65m-native-loader-check l65m-bulkread-fixture-check $(WORKBENCH_L65M_TRANSPORT_OPS_HOST)
	$(WORKBENCH_L65M_TRANSPORT_OPS_HOST) --selftest
	$(WORKBENCH_L65M_TRANSPORT_OPS_HOST) \
		--image '$(BYTECODE_IDE_LIB_EXT_BLOB)' \
		--integration src/vm_embed.c \
		--scratch-source src/io.c \
		--out '$(WORKBENCH_L65M_TRANSPORT_OPS_REPORT)' --check

workbench-l65m-commit-ops-report: workbench-product bytecode-p0-ide-lib-artifacts bytecode-p0-workbench-stdlib-artifacts $(WORKBENCH_L65M_COMMIT_OPS_TOOL) src/vm_embed.c src/l65m_commit_overlay.c src/l65m_commit_overlay.h src/l65m_batch_repeat.s src/vm_runtime_overlay.c src/vm_runtime_overlay.h src/io.c src/symbol.c
	python3 $(WORKBENCH_L65M_COMMIT_OPS_TOOL) --selftest
	python3 $(WORKBENCH_L65M_COMMIT_OPS_TOOL) \
		--image '$(BYTECODE_IDE_LIB_EXT_BLOB)' \
		--elf '$(WORKBENCH_PRODUCT_ELF)' \
		--objdump '$(LLVM)/llvm-objdump' \
		--integration src/vm_embed.c \
		--commit-source src/l65m_commit_overlay.c \
		--transport-source src/vm_runtime_overlay.c \
		--scratch-source src/io.c \
		--symbol-source src/symbol.c \
		--predicate-source src/l65m_batch_repeat.s \
		--symbol-manifest '$(WORKBENCH_STDLIB_MANIFEST)' \
		--out '$(WORKBENCH_L65M_COMMIT_OPS_REPORT)' --check

runtime-overlay-bank-selftest:
	python3 $(WORKBENCH_RUNTIME_OVERLAY_TOOL) selftest

resident-island-selftest:
	python3 $(WORKBENCH_RESIDENT_ISLAND_TOOL) selftest

bank0-island-inventory-selftest:
	python3 $(WORKBENCH_RESIDENT_ISLAND_INVENTORY_TOOL) --selftest

bank0-island-inventory-report: workbench-product
	python3 $(WORKBENCH_RESIDENT_ISLAND_INVENTORY_TOOL) \
		--elf '$(WORKBENCH_PRODUCT_ELF)' \
		--policy '$(WORKBENCH_RESIDENT_ISLAND_POLICY)' \
		--nm '$(M65VMSTDLIB_NM)' --size '$(M65VMSTDLIB_SIZE)' \
		--json-out '$(WORKBENCH_RESIDENT_ISLAND_INVENTORY_JSON)' \
		--text-out '$(WORKBENCH_RESIDENT_ISLAND_INVENTORY_TEXT)' \
		--require-annex --check

mega65-math-override-check:
	python3 scripts/mega65-math-override-check.py

error-text-table-selftest:
	python3 $(WORKBENCH_ERROR_TEXT_TOOL) selftest

error-code-contract-selftest:
	python3 $(WORKBENCH_ERROR_CODE_TOOL) selftest

error-overlay-smoke:
	python3 tools/host-lisp/error_overlay_smoke.py

hw-stack-probe-readback-selftest:
	python3 scripts/hw-stack-probe-readback.py --selftest

hw-ship-memory-readback-selftest:
	python3 scripts/hw-ship-memory-readback.py --selftest
	python3 tools/host-lisp/hw_ship_g5_harness_test.py

workbench-disk-lib-budget-selftest:
	python3 tools/host-lisp/workbench_disklib_budget.py --selftest

persistence-contract-check:
	python3 tools/host-lisp/persistence_contract.py --selftest
	python3 tools/host-lisp/persistence_contract.py

d81-persistence-fault-selftest:
	python3 tools/host-lisp/d81_persistence_fault.py --selftest

bank0-lifetime-selftest:
	python3 tools/host-lisp/bank0_lifetime_report.py --selftest

bank0-lifetime-report: workbench-reference-footprint-report
	python3 tools/host-lisp/bank0_lifetime_report.py \
		--elf "$(WORKBENCH_REFERENCE_PRG).elf" \
		--footprint "$(WORKBENCH_REFERENCE_FOOTPRINT_REPORT)" \
		--policy "$(WORKBENCH_BANK0_LIFETIME_POLICY)" \
		--nm "$(M65VMSTDLIB_NM)" \
		--size "$(M65VMSTDLIB_SIZE)" \
		--json-out "$(WORKBENCH_BANK0_LIFETIME_JSON)" \
		--text-out "$(WORKBENCH_BANK0_LIFETIME_TEXT)" \
		--check

mvp-vm-stdlib-einsuite-core-workbench: $(WORKBENCH_REFERENCE_PRG)
$(WORKBENCH_REFERENCE_PRG): $(SRCS) $(VM_SRCS) $(WORKBENCH_TARGET_SRCS) FORCE | build
	$(MAKE) bytecode-p0-workbench-stdlib-artifacts
	$(CC_M65) $(WORKBENCH_CFLAGS) -DLISP65_VM -DLISP65_EMBED_STDLIB -DLISP65_EMBED_DMA \
		-DLISP65_REPL -DHEAP_CELLS=$(WORKBENCH_HEAP_CELLS) \
		$(WORKBENCH_DEFINES) -Isrc -I$(WORKBENCH_BYTECODE_DIR) -Ibuild/bytecode \
		$(SRCS) $(VM_SRCS) $(WORKBENCH_TARGET_SRCS) $(WORKBENCH_STDLIB_C) $(WORKBENCH_LDFLAGS) -o $@
	@printf 'built %s (%s bytes, HEAP_CELLS=%s, einsuite/core-workbench arena+compile-string)\n' "$@" "$$(stat -c%s $@)" "$(WORKBENCH_HEAP_CELLS)"

# Unguarded overlay reference retained for package diagnostics and comparison.
workbench-overlay-link-prototype: $(WORKBENCH_OVERLAY_RESIDENT_PRG) $(WORKBENCH_OVERLAY_RAW)

workbench-overlay-prototype: $(WORKBENCH_OVERLAY_STAGE_MANIFEST) $(WORKBENCH_OVERLAY_RAW_PACKAGE_MANIFEST)

workbench-overlay-stage-selftest:
	python3 tools/host-lisp/workbench_overlay_stage.py selftest

WORKBENCH_RUNTIME_OVERLAY_ABI_HEADERS := src/error_codes.h src/error_overlay.h src/f011_context.h src/l65m_batch_contract.h src/l65m_commit_overlay.h src/l65m_overlay_abi.h src/l65m_validate.h src/lcc_install_overlay.h src/vm_boot_fastpath.h src/vm_runtime_overlay.h
WORKBENCH_RUNTIME_OVERLAY_ABI_INPUTS := $(WORKBENCH_ERROR_TEXT_SPEC) $(WORKBENCH_ERROR_TEXT_TOOL) $(WORKBENCH_ERROR_CODE_CONTRACT) $(WORKBENCH_ERROR_CODE_TOOL) $(WORKBENCH_RESIDENT_ISLAND_TOOL) $(WORKBENCH_EVAL_SURFACE_INPUTS) $(ASM_C_CONSTANT_CONTRACT_SPEC) $(ASM_C_CONSTANT_CONTRACT_GENERATOR) $(ASM_C_CONSTANT_CONTRACT_INCLUDE)

WORKBENCH_RESIDENT_ISLAND_LINK_ARGS = \
	-Wl,--defsym=__lisp65_workbench_screen_base_param=$(WORKBENCH_SCREEN_BASE) \
	-Wl,--defsym=__lisp65_workbench_screen_columns_param=$(WORKBENCH_SCREEN_COLUMNS) \
	-Wl,--defsym=__lisp65_workbench_screen_rows_param=$(WORKBENCH_SCREEN_ROWS) \
	-Wl,--defsym=__lisp65_workbench_screen_cell_bytes_param=$(WORKBENCH_SCREEN_CELL_BYTES) \
	-Wl,--defsym=__lisp65_resident_island_base_param=$(WORKBENCH_RESIDENT_ISLAND_BASE) \
	-Wl,--defsym=__lisp65_resident_island_limit_param=$(WORKBENCH_RESIDENT_ISLAND_LIMIT) \
	-Wl,--defsym=__lisp65_resident_island_payload_capacity_param=$(WORKBENCH_RESIDENT_ISLAND_CAPACITY)

WORKBENCH_RESIDENT_ISLAND_TOOL_ARGS = \
	--nm '$(M65VMSTDLIB_NM)' --objcopy '$(WORKBENCH_OVERLAY_OBJCOPY)' \
	--abi-contract '$(WORKBENCH_OVERLAY_ABI_CONTRACT)'

$(WORKBENCH_OVERLAY_ABI_CONTRACT): bytecode-p0-workbench-stdlib-artifacts config/workbench.mk mk/workbench.mk $(WORKBENCH_OVERLAY_LD) tools/host-lisp/workbench_overlay_stage.py $(WORKBENCH_RUNTIME_OVERLAY_TOOL) $(WORKBENCH_RUNTIME_OVERLAY_ABI_HEADERS) $(WORKBENCH_RUNTIME_OVERLAY_ABI_INPUTS) $(SRCS) $(VM_SRCS) $(WORKBENCH_TARGET_SRCS) | build
	python3 $(WORKBENCH_RUNTIME_OVERLAY_TOOL) lint-layout \
		--linker '$(WORKBENCH_OVERLAY_LD)' \
		--expect-count '$(WORKBENCH_RUNTIME_OVERLAY_SLICE_COUNT)' \
		--expect-capacity '$(WORKBENCH_RUNTIME_OVERLAY_MAX_SLICES)' \
		--expect-bank '$(WORKBENCH_RUNTIME_OVERLAY_BANK)' \
		--expect-address '$(WORKBENCH_RUNTIME_OVERLAY_ADDRESS)' \
		--expect-entry-abi '$(WORKBENCH_RUNTIME_OVERLAY_ENTRY_ABI)' \
		$(WORKBENCH_RUNTIME_OVERLAY_SLICE_ARGS)
	@mkdir -p $(WORKBENCH_OVERLAY_DIR)
	@if [ -n '$(if $(filter --%,$(firstword $(MAKEFLAGS))),,$(findstring n,$(firstword $(MAKEFLAGS))))' ]; then :; \
	else $(MAKE) --no-print-directory print-workbench-overlay-resolved-profile > '$@'; fi
	@printf '%s\n' \
		'toolchain_sha256='"$$(sha256sum '$(CC_M65)' | awk '{print $$1}')" \
		'external_image_sha256='"$$(sha256sum '$(WORKBENCH_STDLIB_EXT_BLOB)' | awk '{print $$1}')" \
		'bytecode_manifest_sha256='"$$(sha256sum '$(WORKBENCH_STDLIB_MANIFEST)' | awk '{print $$1}')" \
		>> '$@'
	@for source in $(sort $(SRCS) $(VM_SRCS) $(WORKBENCH_TARGET_SRCS) $(WORKBENCH_STDLIB_C) $(WORKBENCH_RUNTIME_OVERLAY_ABI_HEADERS) $(WORKBENCH_RUNTIME_OVERLAY_ABI_INPUTS) config/workbench.mk mk/workbench.mk $(WORKBENCH_OVERLAY_LD) tools/host-lisp/workbench_overlay_stage.py $(WORKBENCH_RUNTIME_OVERLAY_TOOL)); do \
		printf 'input_sha256=%s:%s\n' "$$source" "$$(sha256sum "$$source" | awk '{print $$1}')"; \
	done >> '$@'

$(WORKBENCH_OVERLAY_STAGE_HEADER): $(WORKBENCH_OVERLAY_ABI_CONTRACT) $(WORKBENCH_STDLIB_EXT_BLOB) $(WORKBENCH_STDLIB_MANIFEST) tools/host-lisp/workbench_overlay_stage.py
	python3 tools/host-lisp/workbench_overlay_stage.py prepare \
		--stdlib-ext '$(WORKBENCH_STDLIB_EXT_BLOB)' \
		--stdlib-manifest '$(WORKBENCH_STDLIB_MANIFEST)' \
		--contract '$(WORKBENCH_OVERLAY_ABI_CONTRACT)' --out-header '$@'

$(WORKBENCH_RUNTIME_OVERLAY_PREPARED_HEADER): $(WORKBENCH_OVERLAY_ABI_CONTRACT) $(WORKBENCH_RUNTIME_OVERLAY_TOOL)
	python3 $(WORKBENCH_RUNTIME_OVERLAY_TOOL) prepare \
		--abi-contract '$(WORKBENCH_OVERLAY_ABI_CONTRACT)' --header '$@' \
		--profile '$(WORKBENCH_PROFILE_ID)'

$(WORKBENCH_RESIDENT_ISLAND_PREPARED_HEADER): $(WORKBENCH_OVERLAY_ABI_CONTRACT) $(WORKBENCH_RESIDENT_ISLAND_TOOL)
	python3 $(WORKBENCH_RESIDENT_ISLAND_TOOL) prepare \
		--abi-contract '$(WORKBENCH_OVERLAY_ABI_CONTRACT)' --header '$@'

$(WORKBENCH_ERROR_TEXT_HEADER) $(WORKBENCH_ERROR_TEXT_TABLE) &: $(WORKBENCH_OVERLAY_ABI_CONTRACT) $(WORKBENCH_ERROR_TEXT_SPEC) $(WORKBENCH_ERROR_TEXT_TOOL)
	@set -eu; \
		build_id="0x$$(sha256sum '$(WORKBENCH_OVERLAY_ABI_CONTRACT)' | cut -c1-8)"; \
		python3 '$(WORKBENCH_ERROR_TEXT_TOOL)' prepare \
			--spec '$(WORKBENCH_ERROR_TEXT_SPEC)' --profile '$(WORKBENCH_ERROR_TEXT_PROFILE)' \
			--build-id "$$build_id" --header '$(WORKBENCH_ERROR_TEXT_HEADER)' \
			--binary '$(WORKBENCH_ERROR_TEXT_TABLE)'; \
		python3 '$(WORKBENCH_ERROR_TEXT_TOOL)' verify \
			--spec '$(WORKBENCH_ERROR_TEXT_SPEC)' --profile '$(WORKBENCH_ERROR_TEXT_PROFILE)' \
			--build-id "$$build_id" --table '$(WORKBENCH_ERROR_TEXT_TABLE)'

$(WORKBENCH_RESIDENT_ISLAND_SEED_LINKED_PRG): $(SRCS) $(VM_SRCS) $(WORKBENCH_TARGET_SRCS) $(WORKBENCH_OVERLAY_STAGE_HEADER) $(WORKBENCH_RUNTIME_OVERLAY_PREPARED_HEADER) $(WORKBENCH_RESIDENT_ISLAND_PREPARED_HEADER) $(WORKBENCH_ERROR_TEXT_HEADER) $(WORKBENCH_OVERLAY_LD) FORCE | build
	@mkdir -p $(WORKBENCH_OVERLAY_DIR)
	$(CC_M65) $(WORKBENCH_CFLAGS) -DLISP65_VM -DLISP65_EMBED_STDLIB -DLISP65_EMBED_DMA \
		-DLISP65_REPL -DHEAP_CELLS=$(WORKBENCH_HEAP_CELLS) $(WORKBENCH_DEFINES) \
		-DLISP65_STDLIB_BOOT_OVERLAY_CODE -DLISP65_STAGED_BOOT_OVERLAY -DLISP65_RUNTIME_OVERLAY \
		$(WORKBENCH_OVERLAY_EXTRA_DEFINES) \
		-include '$(WORKBENCH_OVERLAY_STAGE_HEADER)' -include '$(WORKBENCH_RUNTIME_OVERLAY_PREPARED_HEADER)' \
		-include '$(WORKBENCH_RESIDENT_ISLAND_PREPARED_HEADER)' \
		-Isrc -I'$(WORKBENCH_OVERLAY_DIR)' -I$(WORKBENCH_BYTECODE_DIR) -Ibuild/bytecode \
		$(SRCS) $(VM_SRCS) $(WORKBENCH_TARGET_SRCS) $(WORKBENCH_STDLIB_C) $(WORKBENCH_LDFLAGS) \
		-Wl,-T,$(WORKBENCH_OVERLAY_LD) \
		-Wl,--defsym=__lisp65_workbench_required_boot_stack_param=$(WORKBENCH_OVERLAY_MIN_BOOT_STACK_GAP) \
		-Wl,--defsym=__lisp65_workbench_required_runtime_stack_param=$(WORKBENCH_MIN_STACK_GAP) \
		-Wl,--defsym=__lisp65_workbench_required_post_boot_reserve_param=$(WORKBENCH_OVERLAY_MIN_POST_BOOT_RESERVE) \
		-Wl,--defsym=__lisp65_workbench_runtime_overlay_vma_param=$(WORKBENCH_RUNTIME_OVERLAY_VMA) \
		-Wl,--defsym=__lisp65_workbench_runtime_overlay_max_vma_param=$(WORKBENCH_RUNTIME_OVERLAY_MAX_VMA) \
		-Wl,--defsym=__lisp65_error_overlay_max_bytes_param=$(WORKBENCH_ERROR_OVERLAY_MAX_BYTES) \
		$(WORKBENCH_RESIDENT_ISLAND_LINK_ARGS) -Wl,-Map='$@.map' -o '$@'
	@if grep -Eq 'divmod\.cc\.obj|mul\.cc\.obj' '$@.map'; then \
		echo 'workbench HW-math aliases did not suppress compiler-rt div/mul bodies' >&2; exit 1; \
	fi

$(WORKBENCH_RESIDENT_ISLAND_HEADER): $(WORKBENCH_RESIDENT_ISLAND_SEED_LINKED_PRG) $(WORKBENCH_OVERLAY_ABI_CONTRACT) $(WORKBENCH_RESIDENT_ISLAND_TOOL)
	python3 $(WORKBENCH_RESIDENT_ISLAND_TOOL) materialize \
		--elf '$(WORKBENCH_RESIDENT_ISLAND_SEED_LINKED_PRG).elf' \
		$(WORKBENCH_RESIDENT_ISLAND_TOOL_ARGS) --header '$@'

$(WORKBENCH_RUNTIME_OVERLAY_BOOTSTRAP_LINKED_PRG): $(SRCS) $(VM_SRCS) $(WORKBENCH_TARGET_SRCS) $(WORKBENCH_OVERLAY_STAGE_HEADER) $(WORKBENCH_RUNTIME_OVERLAY_PREPARED_HEADER) $(WORKBENCH_RESIDENT_ISLAND_HEADER) $(WORKBENCH_ERROR_TEXT_HEADER) $(WORKBENCH_OVERLAY_LD) FORCE | build
	@mkdir -p $(WORKBENCH_OVERLAY_DIR)
	$(CC_M65) $(WORKBENCH_CFLAGS) -DLISP65_VM -DLISP65_EMBED_STDLIB -DLISP65_EMBED_DMA \
		-DLISP65_REPL -DHEAP_CELLS=$(WORKBENCH_HEAP_CELLS) $(WORKBENCH_DEFINES) \
		-DLISP65_STDLIB_BOOT_OVERLAY_CODE -DLISP65_STAGED_BOOT_OVERLAY -DLISP65_RUNTIME_OVERLAY \
		$(WORKBENCH_OVERLAY_EXTRA_DEFINES) \
		-include '$(WORKBENCH_OVERLAY_STAGE_HEADER)' -include '$(WORKBENCH_RUNTIME_OVERLAY_PREPARED_HEADER)' \
		-include '$(WORKBENCH_RESIDENT_ISLAND_HEADER)' \
		-Isrc -I'$(WORKBENCH_OVERLAY_DIR)' -I$(WORKBENCH_BYTECODE_DIR) -Ibuild/bytecode \
		$(SRCS) $(VM_SRCS) $(WORKBENCH_TARGET_SRCS) $(WORKBENCH_STDLIB_C) $(WORKBENCH_LDFLAGS) \
		-Wl,-T,$(WORKBENCH_OVERLAY_LD) \
		-Wl,--defsym=__lisp65_workbench_required_boot_stack_param=$(WORKBENCH_OVERLAY_MIN_BOOT_STACK_GAP) \
		-Wl,--defsym=__lisp65_workbench_required_runtime_stack_param=$(WORKBENCH_MIN_STACK_GAP) \
		-Wl,--defsym=__lisp65_workbench_required_post_boot_reserve_param=$(WORKBENCH_OVERLAY_MIN_POST_BOOT_RESERVE) \
		-Wl,--defsym=__lisp65_workbench_runtime_overlay_vma_param=$(WORKBENCH_RUNTIME_OVERLAY_VMA) \
		-Wl,--defsym=__lisp65_workbench_runtime_overlay_max_vma_param=$(WORKBENCH_RUNTIME_OVERLAY_MAX_VMA) \
		-Wl,--defsym=__lisp65_error_overlay_max_bytes_param=$(WORKBENCH_ERROR_OVERLAY_MAX_BYTES) \
		$(WORKBENCH_RESIDENT_ISLAND_LINK_ARGS) \
		-Wl,-Map='$@.map' \
		-o '$@'
	@if grep -Eq 'divmod\.cc\.obj|mul\.cc\.obj' '$@.map'; then \
		echo 'workbench HW-math aliases did not suppress compiler-rt div/mul bodies' >&2; exit 1; \
	fi

$(WORKBENCH_RUNTIME_OVERLAY_HEADER) $(WORKBENCH_RUNTIME_OVERLAY_BOOTSTRAP_IMAGE) $(WORKBENCH_RUNTIME_OVERLAY_BOOTSTRAP_MANIFEST) &: $(WORKBENCH_RUNTIME_OVERLAY_BOOTSTRAP_LINKED_PRG) $(WORKBENCH_OVERLAY_ABI_CONTRACT) $(WORKBENCH_RUNTIME_OVERLAY_TOOL)
	@set -eu; \
		python3 $(WORKBENCH_RUNTIME_OVERLAY_TOOL) lint-layout \
			--linker '$(WORKBENCH_OVERLAY_LD)' \
			--expect-count '$(WORKBENCH_RUNTIME_OVERLAY_SLICE_COUNT)' \
			--expect-capacity '$(WORKBENCH_RUNTIME_OVERLAY_MAX_SLICES)' \
			--expect-bank '$(WORKBENCH_RUNTIME_OVERLAY_BANK)' \
			--expect-address '$(WORKBENCH_RUNTIME_OVERLAY_ADDRESS)' \
			--expect-entry-abi '$(WORKBENCH_RUNTIME_OVERLAY_ENTRY_ABI)' \
			$(WORKBENCH_RUNTIME_OVERLAY_SLICE_ARGS); \
		vma="$$( $(M65VMSTDLIB_NM) --defined-only '$(WORKBENCH_RUNTIME_OVERLAY_BOOTSTRAP_LINKED_PRG).elf' | \
			awk '$$3 == "$(WORKBENCH_RUNTIME_OVERLAY_VMA_SYMBOL)" { print "0x" $$1 }')"; \
		[ -n "$$vma" ] || { echo 'missing runtime-overlay VMA symbol in bootstrap link' >&2; exit 1; }; \
		python3 $(WORKBENCH_RUNTIME_OVERLAY_TOOL) pack \
			--elf '$(WORKBENCH_RUNTIME_OVERLAY_BOOTSTRAP_LINKED_PRG).elf' --nm '$(M65VMSTDLIB_NM)' \
			--objcopy '$(WORKBENCH_OVERLAY_OBJCOPY)' --profile '$(WORKBENCH_PROFILE_ID)' \
			--abi-contract '$(WORKBENCH_OVERLAY_ABI_CONTRACT)' --vma "$$vma" \
			--max-slice-bytes '$(WORKBENCH_RUNTIME_OVERLAY_MAX_SLICE_BYTES)' \
			$(WORKBENCH_RUNTIME_OVERLAY_SLICE_ARGS) \
			--image '$(WORKBENCH_RUNTIME_OVERLAY_BOOTSTRAP_IMAGE)' \
			--manifest '$(WORKBENCH_RUNTIME_OVERLAY_BOOTSTRAP_MANIFEST)' \
			--header '$(WORKBENCH_RUNTIME_OVERLAY_HEADER)' --header-mode write

$(WORKBENCH_OVERLAY_LINKED_PRG): $(SRCS) $(VM_SRCS) $(WORKBENCH_TARGET_SRCS) $(WORKBENCH_OVERLAY_STAGE_HEADER) $(WORKBENCH_RUNTIME_OVERLAY_HEADER) $(WORKBENCH_RESIDENT_ISLAND_HEADER) $(WORKBENCH_ERROR_TEXT_HEADER) $(WORKBENCH_OVERLAY_LD) FORCE | build
	@mkdir -p $(WORKBENCH_OVERLAY_DIR)
	$(CC_M65) $(WORKBENCH_CFLAGS) -DLISP65_VM -DLISP65_EMBED_STDLIB -DLISP65_EMBED_DMA \
		-DLISP65_REPL -DHEAP_CELLS=$(WORKBENCH_HEAP_CELLS) $(WORKBENCH_DEFINES) \
		-DLISP65_STDLIB_BOOT_OVERLAY_CODE -DLISP65_STAGED_BOOT_OVERLAY -DLISP65_RUNTIME_OVERLAY \
		$(WORKBENCH_OVERLAY_EXTRA_DEFINES) \
		-include '$(WORKBENCH_OVERLAY_STAGE_HEADER)' -include '$(WORKBENCH_RUNTIME_OVERLAY_HEADER)' \
		-include '$(WORKBENCH_RESIDENT_ISLAND_HEADER)' \
		-Isrc -I'$(WORKBENCH_OVERLAY_DIR)' -I$(WORKBENCH_BYTECODE_DIR) -Ibuild/bytecode \
		$(SRCS) $(VM_SRCS) $(WORKBENCH_TARGET_SRCS) $(WORKBENCH_STDLIB_C) $(WORKBENCH_LDFLAGS) \
		-Wl,-T,$(WORKBENCH_OVERLAY_LD) \
		-Wl,--defsym=__lisp65_workbench_required_boot_stack_param=$(WORKBENCH_OVERLAY_MIN_BOOT_STACK_GAP) \
		-Wl,--defsym=__lisp65_workbench_required_runtime_stack_param=$(WORKBENCH_MIN_STACK_GAP) \
		-Wl,--defsym=__lisp65_workbench_required_post_boot_reserve_param=$(WORKBENCH_OVERLAY_MIN_POST_BOOT_RESERVE) \
		-Wl,--defsym=__lisp65_workbench_runtime_overlay_vma_param=$(WORKBENCH_RUNTIME_OVERLAY_VMA) \
		-Wl,--defsym=__lisp65_workbench_runtime_overlay_max_vma_param=$(WORKBENCH_RUNTIME_OVERLAY_MAX_VMA) \
		-Wl,--defsym=__lisp65_error_overlay_max_bytes_param=$(WORKBENCH_ERROR_OVERLAY_MAX_BYTES) \
		$(WORKBENCH_RESIDENT_ISLAND_LINK_ARGS) \
		-Wl,-Map='$@.map' \
		-o '$@'
	@if grep -Eq 'divmod\.cc\.obj|mul\.cc\.obj' '$@.map'; then \
		echo 'workbench HW-math aliases did not suppress compiler-rt div/mul bodies' >&2; exit 1; \
	fi
	@printf 'built %s (%s bytes, staged boot overlay)\n' '$@' "$$(stat -c%s '$@')"

$(WORKBENCH_OVERLAY_LAYOUT): $(WORKBENCH_OVERLAY_LINKED_PRG) $(WORKBENCH_OVERLAY_ABI_CONTRACT) $(WORKBENCH_STDLIB_EXT_BLOB) $(WORKBENCH_STDLIB_MANIFEST) tools/host-lisp/workbench_overlay_stage.py
	python3 tools/host-lisp/workbench_overlay_stage.py layout \
		--elf '$(WORKBENCH_OVERLAY_LINKED_PRG).elf' --nm '$(M65VMSTDLIB_NM)' \
		--linked-prg '$(WORKBENCH_OVERLAY_LINKED_PRG)' \
		--stdlib-ext '$(WORKBENCH_STDLIB_EXT_BLOB)' \
		--stdlib-manifest '$(WORKBENCH_STDLIB_MANIFEST)' \
		--contract '$(WORKBENCH_OVERLAY_ABI_CONTRACT)' \
		--stage-limit '$(WORKBENCH_OVERLAY_STAGE_LIMIT)' --out '$@'

$(WORKBENCH_OVERLAY_RESIDENT_PRG): $(WORKBENCH_OVERLAY_LINKED_PRG) $(WORKBENCH_OVERLAY_LAYOUT) tools/host-lisp/workbench_overlay_stage.py
	python3 tools/host-lisp/workbench_overlay_stage.py extract-resident \
		--linked-prg '$(WORKBENCH_OVERLAY_LINKED_PRG)' \
		--layout '$(WORKBENCH_OVERLAY_LAYOUT)' --out '$@'

$(WORKBENCH_OVERLAY_RAW): $(WORKBENCH_OVERLAY_LINKED_PRG)
	$(WORKBENCH_OVERLAY_OBJCOPY) -O binary --only-section=$(WORKBENCH_OVERLAY_SECTION) '$<.elf' '$@'
	@printf 'built %s (%s bytes)\n' '$@' "$$(stat -c%s '$@')"

$(WORKBENCH_RUNTIME_OVERLAY_IMAGE) $(WORKBENCH_RUNTIME_OVERLAY_MANIFEST) &: $(WORKBENCH_OVERLAY_LINKED_PRG) $(WORKBENCH_OVERLAY_ABI_CONTRACT) $(WORKBENCH_RUNTIME_OVERLAY_HEADER) $(WORKBENCH_RUNTIME_OVERLAY_TOOL)
	@set -eu; \
		vma="$$( $(M65VMSTDLIB_NM) --defined-only '$(WORKBENCH_OVERLAY_LINKED_PRG).elf' | \
			awk '$$3 == "$(WORKBENCH_RUNTIME_OVERLAY_VMA_SYMBOL)" { print "0x" $$1 }')"; \
		[ -n "$$vma" ] || { echo 'missing runtime-overlay VMA symbol' >&2; exit 1; }; \
		python3 $(WORKBENCH_RUNTIME_OVERLAY_TOOL) pack \
			--elf '$(WORKBENCH_OVERLAY_LINKED_PRG).elf' --nm '$(M65VMSTDLIB_NM)' \
			--objcopy '$(WORKBENCH_OVERLAY_OBJCOPY)' --profile '$(WORKBENCH_PROFILE_ID)' \
			--abi-contract '$(WORKBENCH_OVERLAY_ABI_CONTRACT)' --vma "$$vma" \
			--max-slice-bytes '$(WORKBENCH_RUNTIME_OVERLAY_MAX_SLICE_BYTES)' \
			$(WORKBENCH_RUNTIME_OVERLAY_SLICE_ARGS) \
			--image '$(WORKBENCH_RUNTIME_OVERLAY_IMAGE)' \
			--manifest '$(WORKBENCH_RUNTIME_OVERLAY_MANIFEST)' \
			--header '$(WORKBENCH_RUNTIME_OVERLAY_HEADER)' --header-mode verify

workbench-runtime-overlay-package-verify: resident-island-selftest $(WORKBENCH_RUNTIME_OVERLAY_IMAGE) $(WORKBENCH_RUNTIME_OVERLAY_MANIFEST)
	python3 $(WORKBENCH_RESIDENT_ISLAND_TOOL) verify \
		--elf '$(WORKBENCH_OVERLAY_LINKED_PRG).elf' \
		$(WORKBENCH_RESIDENT_ISLAND_TOOL_ARGS) --header '$(WORKBENCH_RESIDENT_ISLAND_HEADER)'
	@set -eu; \
		vma="$$( $(M65VMSTDLIB_NM) --defined-only '$(WORKBENCH_OVERLAY_LINKED_PRG).elf' | \
			awk '$$3 == "$(WORKBENCH_RUNTIME_OVERLAY_VMA_SYMBOL)" { print "0x" $$1 }')"; \
		[ -n "$$vma" ] || { echo 'missing runtime-overlay VMA symbol' >&2; exit 1; }; \
		python3 $(WORKBENCH_RUNTIME_OVERLAY_TOOL) verify \
			--elf '$(WORKBENCH_OVERLAY_LINKED_PRG).elf' --nm '$(M65VMSTDLIB_NM)' \
			--objcopy '$(WORKBENCH_OVERLAY_OBJCOPY)' --profile '$(WORKBENCH_PROFILE_ID)' \
			--abi-contract '$(WORKBENCH_OVERLAY_ABI_CONTRACT)' --vma "$$vma" \
			--max-slice-bytes '$(WORKBENCH_RUNTIME_OVERLAY_MAX_SLICE_BYTES)' \
			$(WORKBENCH_RUNTIME_OVERLAY_SLICE_ARGS) \
			--image '$(WORKBENCH_RUNTIME_OVERLAY_IMAGE)' \
			--manifest '$(WORKBENCH_RUNTIME_OVERLAY_MANIFEST)' \
			--header '$(WORKBENCH_RUNTIME_OVERLAY_HEADER)'; \
		bss_end="$$( $(M65VMSTDLIB_NM) --defined-only '$(WORKBENCH_OVERLAY_LINKED_PRG).elf' | \
			awk '$$3 == "__bss_end" { print $$1 }')"; \
		noinit_end="$$( $(M65VMSTDLIB_NM) --defined-only '$(WORKBENCH_OVERLAY_LINKED_PRG).elf' | \
			awk '$$3 == "__lisp65_workbench_noinit_end" { print $$1 }')"; \
		call_context="$$( $(M65VMSTDLIB_NM) --defined-only '$(WORKBENCH_OVERLAY_LINKED_PRG).elf' | \
			awk '$$3 == "rtov_call_context" { print $$1 }')"; \
		[ -n "$$bss_end" ] && [ -n "$$noinit_end" ] && [ -n "$$call_context" ] || \
			{ echo 'runtime-overlay-installer-shape: missing structural symbol' >&2; exit 1; }; \
		[ "$$bss_end" = "$$noinit_end" ] || \
			{ echo "runtime-overlay-installer-shape: anonymous cross-call spill detected (__bss_end=$$bss_end noinit_end=$$noinit_end)" >&2; exit 1; }; \
		printf '%s\n' "runtime-overlay-installer-shape: PASS explicit-context=$$call_context anonymous-noinit-bytes=0"; \
		printf '%s\n' 'runtime-overlay-final-binding: PASS (44 final-ELF slices, including resident-island installer, exactly match packed image and manifest)'

workbench-error-code-contract-check: workbench-product
	python3 '$(WORKBENCH_ERROR_CODE_TOOL)' check \
		--contract '$(WORKBENCH_ERROR_CODE_CONTRACT)' --header src/error_codes.h \
		--texts '$(WORKBENCH_ERROR_TEXT_SPEC)' --elf '$(WORKBENCH_PRODUCT_ELF)'

$(WORKBENCH_OVERLAY_RAW_PACKAGE_MANIFEST): $(WORKBENCH_OVERLAY_STAGE_MANIFEST) $(WORKBENCH_OVERLAY_RAW) $(WORKBENCH_OVERLAY_RESIDENT_PRG) $(WORKBENCH_OVERLAY_LAYOUT) $(WORKBENCH_OVERLAY_ABI_CONTRACT) tools/host-lisp/overlay_package.py
	@set -eu; \
		value() { python3 -c 'import json,sys; v=json.load(open(sys.argv[1])); print(v[sys.argv[2]][sys.argv[3]])' '$(WORKBENCH_OVERLAY_LAYOUT)' "$$1" "$$2"; }; \
		base="$$(value overlay base)"; end="$$(value overlay end)"; entry="$$(value overlay entry)"; \
		load_base="$$(value resident load_base)"; file_end="$$(value resident file_end)"; \
		stage_base="$$(python3 -c 'import json; print(json.load(open("$(WORKBENCH_OVERLAY_STAGE_MANIFEST)"))["stage"]["address"])')"; \
		header_size="$$(python3 -c 'import json; print(json.load(open("$(WORKBENCH_OVERLAY_STAGE_MANIFEST)"))["descriptor"]["header_size"])')"; \
		payload_load_base="$$((stage_base + header_size))"; \
		python3 tools/host-lisp/overlay_package.py pack \
			--overlay '$(WORKBENCH_OVERLAY_RAW)' --out-dir '$(WORKBENCH_OVERLAY_RAW_PACKAGE_DIR)' \
			--profile '$(WORKBENCH_PROFILE_ID)' --base "$$base" --end "$$end" \
			--entry "$$entry" --entry-symbol '$(WORKBENCH_OVERLAY_ENTRY)' \
			--load-base "$$payload_load_base" --load-mode ext-stage-dma-to-bank0 \
			--staging-mode combined-stdlib-preload --lifetime boot-only \
			--reclaim-point after-boot-transaction \
			--resident '$(WORKBENCH_OVERLAY_RESIDENT_PRG)' \
			--resident-load-base "$$load_base" --resident-file-end "$$file_end" \
			--abi-id '$(WORKBENCH_OVERLAY_ABI_ID)' --abi-contract '$(WORKBENCH_OVERLAY_ABI_CONTRACT)'

$(WORKBENCH_OVERLAY_STAGE_MANIFEST): $(WORKBENCH_OVERLAY_RAW) $(WORKBENCH_OVERLAY_RESIDENT_PRG) $(WORKBENCH_OVERLAY_LAYOUT) $(WORKBENCH_OVERLAY_ABI_CONTRACT) $(WORKBENCH_STDLIB_EXT_BLOB) $(WORKBENCH_STDLIB_MANIFEST) tools/host-lisp/workbench_overlay_stage.py
	python3 tools/host-lisp/workbench_overlay_stage.py pack \
		--profile '$(WORKBENCH_PROFILE_ID)' --layout '$(WORKBENCH_OVERLAY_LAYOUT)' \
		--overlay '$(WORKBENCH_OVERLAY_RAW)' --resident '$(WORKBENCH_OVERLAY_RESIDENT_PRG)' \
		--stdlib-ext '$(WORKBENCH_STDLIB_EXT_BLOB)' \
		--stdlib-manifest '$(WORKBENCH_STDLIB_MANIFEST)' \
		--contract '$(WORKBENCH_OVERLAY_ABI_CONTRACT)' \
		--stage '$(WORKBENCH_OVERLAY_STAGE)' --preload '$(WORKBENCH_OVERLAY_PRELOAD)' \
		--manifest '$@'

$(WORKBENCH_OVERLAY_STAGE) $(WORKBENCH_OVERLAY_PRELOAD): $(WORKBENCH_OVERLAY_STAGE_MANIFEST)
	@test -f '$@'

workbench-overlay-package-verify: $(WORKBENCH_OVERLAY_STAGE_MANIFEST) $(WORKBENCH_OVERLAY_RAW_PACKAGE_MANIFEST)
	@set -eu; \
		value() { python3 -c 'import json,sys; v=json.load(open(sys.argv[1])); print(v[sys.argv[2]][sys.argv[3]])' '$(WORKBENCH_OVERLAY_LAYOUT)' "$$1" "$$2"; }; \
		base="$$(value overlay base)"; end="$$(value overlay end)"; entry="$$(value overlay entry)"; \
		load_base="$$(value resident load_base)"; file_end="$$(value resident file_end)"; \
		stage_base="$$(python3 -c 'import json; print(json.load(open("$(WORKBENCH_OVERLAY_STAGE_MANIFEST)"))["stage"]["address"])')"; \
		header_size="$$(python3 -c 'import json; print(json.load(open("$(WORKBENCH_OVERLAY_STAGE_MANIFEST)"))["descriptor"]["header_size"])')"; \
		payload_load_base="$$((stage_base + header_size))"; \
		python3 tools/host-lisp/overlay_package.py verify --strict \
			--dir '$(WORKBENCH_OVERLAY_RAW_PACKAGE_DIR)' --expect-profile '$(WORKBENCH_PROFILE_ID)' \
			--expect-base "$$base" --expect-end "$$end" \
			--expect-entry "$$entry" --expect-entry-symbol '$(WORKBENCH_OVERLAY_ENTRY)' \
			--expect-load-base "$$payload_load_base" --expect-load-mode ext-stage-dma-to-bank0 \
			--expect-staging-mode combined-stdlib-preload --expect-lifetime boot-only \
			--expect-reclaim-point after-boot-transaction --expect-abi-id '$(WORKBENCH_OVERLAY_ABI_ID)' \
			--resident '$(WORKBENCH_OVERLAY_RESIDENT_PRG)' \
			--expect-resident-load-base "$$load_base" --expect-resident-file-end "$$file_end" \
			--abi-contract '$(WORKBENCH_OVERLAY_ABI_CONTRACT)'
	python3 tools/host-lisp/workbench_overlay_stage.py verify \
		--profile '$(WORKBENCH_PROFILE_ID)' --elf '$(WORKBENCH_OVERLAY_LINKED_PRG).elf' \
		--nm '$(M65VMSTDLIB_NM)' --linked-prg '$(WORKBENCH_OVERLAY_LINKED_PRG)' \
		--layout '$(WORKBENCH_OVERLAY_LAYOUT)' --overlay '$(WORKBENCH_OVERLAY_RAW)' \
		--resident '$(WORKBENCH_OVERLAY_RESIDENT_PRG)' \
		--stdlib-ext '$(WORKBENCH_STDLIB_EXT_BLOB)' \
		--stdlib-manifest '$(WORKBENCH_STDLIB_MANIFEST)' \
		--contract '$(WORKBENCH_OVERLAY_ABI_CONTRACT)' \
		--stage '$(WORKBENCH_OVERLAY_STAGE)' --preload '$(WORKBENCH_OVERLAY_PRELOAD)' \
		--manifest '$(WORKBENCH_OVERLAY_STAGE_MANIFEST)' \
		--stage-limit '$(WORKBENCH_OVERLAY_STAGE_LIMIT)'

# Isoliertes AP4.3-Audit: Boot-Stack und Post-Boot-Reserve haben getrennte
# harte Minima und ambitioniertere Targetwerte. Kein check-*-Aggregat, solange
# der Hardware-Watermark des vollstaendigen Bootpfads fehlt.
workbench-overlay-control-audit: $(WORKBENCH_OVERLAY_LINKED_PRG) tools/host-lisp/workbench_overlay_control_audit.py
	python3 tools/host-lisp/workbench_overlay_control_audit.py \
		--elf '$(WORKBENCH_OVERLAY_LINKED_PRG).elf' --nm '$(M65VMSTDLIB_NM)' \
		--objdump '$(WORKBENCH_OVERLAY_OBJDUMP)' \
		--out '$(WORKBENCH_OVERLAY_CONTROL_AUDIT_REPORT)'

workbench-overlay-control-audit-selftest:
	python3 tools/host-lisp/workbench_overlay_control_audit.py --selftest

workbench-f011-mount-window-audit: $(WORKBENCH_OVERLAY_LINKED_PRG) f011-mount-window-selftest tools/host-lisp/f011_mount_window.py
	python3 tools/host-lisp/f011_mount_window.py \
		--elf '$(WORKBENCH_OVERLAY_LINKED_PRG).elf' --objdump '$(WORKBENCH_OVERLAY_OBJDUMP)' \
		--out '$(WORKBENCH_F011_WINDOW_AUDIT_REPORT)'

workbench-overlay-footprint-audit: workbench-overlay-package-verify workbench-runtime-overlay-package-verify workbench-overlay-control-audit workbench-f011-mount-window-audit
	python3 tools/host-lisp/workbench_overlay_stage.py audit \
		--layout '$(WORKBENCH_OVERLAY_LAYOUT)' --out '$(WORKBENCH_OVERLAY_AUDIT_REPORT)' \
		--min-runtime-stack-gap '$(WORKBENCH_MIN_STACK_GAP)' \
		--min-boot-stack-gap '$(WORKBENCH_OVERLAY_MIN_BOOT_STACK_GAP)' \
		--boot-stack-gap-target '$(WORKBENCH_OVERLAY_BOOT_STACK_GAP_TARGET)' \
		--min-post-boot-reserve '$(WORKBENCH_OVERLAY_MIN_POST_BOOT_RESERVE)' \
		--post-boot-reserve-target '$(WORKBENCH_OVERLAY_POST_BOOT_RESERVE_TARGET)'

workbench-overlay-reproducibility-check:
	rm -rf build/reproducibility/workbench-overlay-a build/reproducibility/workbench-overlay-b
	$(MAKE) --no-print-directory WORKBENCH_OVERLAY_DIR=build/reproducibility/workbench-overlay-a workbench-overlay-package-verify workbench-runtime-overlay-package-verify workbench-overlay-control-audit
	$(MAKE) --no-print-directory WORKBENCH_OVERLAY_DIR=build/reproducibility/workbench-overlay-b workbench-overlay-package-verify workbench-runtime-overlay-package-verify workbench-overlay-control-audit
	@set -eu; for artifact in \
		lisp65-workbench-overlay-linked.prg lisp65-workbench-resident.prg \
		lisp65-workbench-overlay.bin overlay-stage.bin stdlib-with-overlay.ext.bin \
		runtime-overlay-bank.h lisp65-mvp-workbench.overlays.bin runtime-overlays-manifest.json \
		resident-island-image.h \
		layout.json stage-config.h stage-manifest.json control-audit.json resolved-profile.txt \
		raw-package/overlay.bin raw-package/manifest.json; do \
		cmp "build/reproducibility/workbench-overlay-a/$$artifact" \
		    "build/reproducibility/workbench-overlay-b/$$artifact"; \
	done
	@printf '%s\n' 'workbench-overlay-reproducibility-check: PASS (all deploy and binding artifacts are byte-identical)'

# AP4.4 diagnostic variant. It is intentionally absent from G0-G2 and Ship.
workbench-overlay-stack-probe: workbench-overlay-stack-probe-smoke hw-stack-probe-readback-selftest
	$(MAKE) --no-print-directory \
		WORKBENCH_OVERLAY_DIR='$(WORKBENCH_OVERLAY_PROBE_DIR)' \
		WORKBENCH_OVERLAY_EXTRA_DEFINES='$(WORKBENCH_OVERLAY_PROBE_DEFINES)' \
		workbench-overlay-footprint-audit

workbench-overlay-stack-guard: asm-c-constant-contract-check v2-workbench-artifacts attic-library-shelf-check
	$(MAKE) --no-print-directory \
		WORKBENCH_PROFILE_ID=dialect-v2-capability-carrier-workbench-staging \
		WORKBENCH_SUITE=build/bytecode/dialect-v2/suites/p0-stdlib-einsuite-core-workbench-subset.json \
		WORKBENCH_BYTECODE_DIR=build/bytecode/dialect-v2/workbench \
		WORKBENCH_OVERLAY_DIR='$(WORKBENCH_OVERLAY_GUARD_DIR)' \
		WORKBENCH_OVERLAY_EXTRA_DEFINES='-DLISP65_STACK_GUARD $(V2_CAPABILITY_CARRIER_G5_V2_DEFINES) $(WORKBENCH_C1_PHASE_PROBE_DEFINES)' \
		workbench-overlay-footprint-audit

workbench-c1-phase-probe:
	@set -eu; \
	for probe in 1 2 3 4 5 6 7 8 9; do \
		$(MAKE) --no-print-directory \
			WORKBENCH_OVERLAY_GUARD_DIR='$(WORKBENCH_C1_PHASE_PROBE_DIR)-'$$probe \
			WORKBENCH_C1_PHASE_PROBE_DEFINES='-DLISP65_C1_PHASE_TIMING='$$probe \
			workbench-overlay-stack-guard; \
	done

workbench-c1-phase-probe-check: workbench-c1-phase-probe
	python3 scripts/hw-c1-phase-probe.py --selftest

workbench-c1-lease-probe: v11-c1-lease-check
	LISP65_C1_LEASE_PROBE=1 $(MAKE) --no-print-directory \
		V2_WORKBENCH_CODEMOD_TOOL='tools/host-lisp/v11_c1_lease_codemod.py' \
		WORKBENCH_OVERLAY_GUARD_DIR='$(WORKBENCH_C1_PHASE_PROBE_DIR)-10' \
		WORKBENCH_C1_PHASE_PROBE_DEFINES='' \
		workbench-overlay-stack-guard

workbench-c1-fastpath-probe: v11-c1-lease-check v11-c1-trust-fastpath-check
	LISP65_C1_LEASE_PROBE=1 $(MAKE) --no-print-directory \
		V2_WORKBENCH_CODEMOD_TOOL='tools/host-lisp/v11_c1_lease_codemod.py' \
		WORKBENCH_OVERLAY_GUARD_DIR='$(WORKBENCH_C1_PHASE_PROBE_DIR)-11' \
		WORKBENCH_C1_PHASE_PROBE_DEFINES='-DLISP65_C1_TRUST_FASTPATH_PROBE' \
		workbench-overlay-stack-guard

hw-workbench-c1-phase-probe-dry-run: workbench-c1-phase-probe-check
	python3 scripts/hw-c1-phase-probe.py --probe 1 --dry-run

# Canonical product. The recursive generic builder is isolated behind one
# target so G2, candidate packaging and hardware gates share the same files.
workbench-product: asm-c-constant-contract-check f011-transaction-context-check mega65-math-override-check v11-source-stream-lifetime-check

workbench-product-footprint-report: workbench-product
	@test -f '$(WORKBENCH_FOOTPRINT_REPORT)'

# Called by the ship builder after its outer Make target has already built the
# product. Deliberately check-only to avoid a second FORCE-driven overlay link.
workbench-product-input-ready:
	@test -f '$(WORKBENCH_PRG)'
	@test -f '$(WORKBENCH_ATTIC_SHELF_IMAGE)'
	@test -f '$(WORKBENCH_ATTIC_SHELF_MANIFEST)'
	@test -f '$(WORKBENCH_PRODUCT_PRELOAD)'
	@test -f '$(WORKBENCH_PRODUCT_RUNTIME_OVERLAY)'
	@test -f '$(WORKBENCH_PRODUCT_RUNTIME_OVERLAY_MANIFEST)'
	@test -f '$(WORKBENCH_PRODUCT_ELF)'
	@test -f '$(WORKBENCH_OVERLAY_GUARD_STAGE_MANIFEST)'
	@test -f '$(WORKBENCH_OVERLAY_GUARD_ABI_CONTRACT)'
	@test -f '$(WORKBENCH_FOOTPRINT_REPORT)'

hw-workbench-overlay-stack-readback: workbench-overlay-stack-probe
	python3 scripts/hw-stack-probe-readback.py \
		--elf '$(WORKBENCH_OVERLAY_PROBE_ELF)' \
		--out-dir '$(WORKBENCH_OVERLAY_PROBE_REPORT_DIR)' \
		--min-soft-margin '$(WORKBENCH_OVERLAY_PROBE_MIN_SOFT_MARGIN)' \
		--min-hw-remaining '$(WORKBENCH_OVERLAY_PROBE_MIN_HW_REMAINING)'

hw-workbench-overlay-stack-readback-dry-run: workbench-overlay-stack-probe
	python3 scripts/hw-stack-probe-readback.py \
		--elf '$(WORKBENCH_OVERLAY_PROBE_ELF)' \
		--out-dir '$(WORKBENCH_OVERLAY_PROBE_REPORT_DIR)' \
		--min-soft-margin '$(WORKBENCH_OVERLAY_PROBE_MIN_SOFT_MARGIN)' \
		--min-hw-remaining '$(WORKBENCH_OVERLAY_PROBE_MIN_HW_REMAINING)' \
		--dry-run

hw-workbench-overlay-stack-smoke: workbench-overlay-stack-probe workbench-ship-d81
	sh scripts/hw-workbench-overlay-stack-smoke.sh \
		--resident-prg '$(WORKBENCH_OVERLAY_PROBE_RESIDENT_PRG)' \
		--preload '$(WORKBENCH_OVERLAY_PROBE_PRELOAD)' \
		--runtime-overlay '$(WORKBENCH_OVERLAY_PROBE_RUNTIME_IMAGE)' \
		--elf '$(WORKBENCH_OVERLAY_PROBE_ELF)' --d81 '$(WORKBENCH_SHIP_D81)' \
		--out-dir '$(WORKBENCH_OVERLAY_PROBE_REPORT_DIR)' \
		--min-soft-margin '$(WORKBENCH_OVERLAY_PROBE_MIN_SOFT_MARGIN)' \
		--min-hw-remaining '$(WORKBENCH_OVERLAY_PROBE_MIN_HW_REMAINING)'

hw-workbench-overlay-stack-smoke-dry-run: workbench-overlay-stack-probe workbench-ship-d81
	sh scripts/hw-workbench-overlay-stack-smoke.sh --dry-run \
		--resident-prg '$(WORKBENCH_OVERLAY_PROBE_RESIDENT_PRG)' \
		--preload '$(WORKBENCH_OVERLAY_PROBE_PRELOAD)' \
		--runtime-overlay '$(WORKBENCH_OVERLAY_PROBE_RUNTIME_IMAGE)' \
		--elf '$(WORKBENCH_OVERLAY_PROBE_ELF)' --d81 '$(WORKBENCH_SHIP_D81)' \
		--out-dir '$(WORKBENCH_OVERLAY_PROBE_REPORT_DIR)' \
		--min-soft-margin '$(WORKBENCH_OVERLAY_PROBE_MIN_SOFT_MARGIN)' \
		--min-hw-remaining '$(WORKBENCH_OVERLAY_PROBE_MIN_HW_REMAINING)'

# The guard product has LISP65_STACK_GUARD but deliberately no
# LISP65_BOOT_STACK_PROBE canaries/symbols.  Its --no-readback G5 evidence does
# not include the transient post-IDE watermark; the diagnostic probe targets
# above provide that separate proof without changing the product layout.
hw-workbench-overlay-stack-guard-smoke: mvp-ship-artifacts
	sh scripts/hw-workbench-overlay-stack-smoke.sh --no-readback \
		--resident-prg '$(MVP_VM_SHIP_PRG)' \
		--preload '$(MVP_VM_SHIP_BLOB)' \
		--runtime-overlay '$(MVP_VM_SHIP_OVERLAYS)' \
		--ship-manifest '$(MVP_VM_SHIP_MANIFEST)' \
		--elf '$(WORKBENCH_OVERLAY_GUARD_ELF)' --d81 '$(MVP_VM_SHIP_D81)' \
		--out-dir '$(WORKBENCH_OVERLAY_GUARD_REPORT_DIR)' \
		--prefix hw-workbench-overlay-stack-guard

hw-workbench-overlay-stack-guard-smoke-dry-run: mvp-ship-artifacts
	sh scripts/hw-workbench-overlay-stack-smoke.sh --dry-run --no-readback \
		--resident-prg '$(MVP_VM_SHIP_PRG)' \
		--preload '$(MVP_VM_SHIP_BLOB)' \
		--runtime-overlay '$(MVP_VM_SHIP_OVERLAYS)' \
		--ship-manifest '$(MVP_VM_SHIP_MANIFEST)' \
		--elf '$(WORKBENCH_OVERLAY_GUARD_ELF)' --d81 '$(MVP_VM_SHIP_D81)' \
		--out-dir '$(WORKBENCH_OVERLAY_GUARD_REPORT_DIR)' \
		--prefix hw-workbench-overlay-stack-guard

# Canonical G5 entry: fail closed unless the clean-G2 promotion exists and
# verifies strictly, then deploy exactly that immutable package set.
hw-workbench-overlay-stack-guard-verified-smoke: verify-ship workbench-product
	sh scripts/hw-workbench-overlay-stack-smoke.sh --no-readback \
		--resident-prg '$(MVP_VERIFIED_DIR)/lisp65-mvp-workbench.prg' \
		--preload '$(MVP_VERIFIED_DIR)/lisp65-mvp-workbench.blob.bin' \
		--runtime-overlay '$(MVP_VERIFIED_DIR)/lisp65-mvp-workbench.overlays.bin' \
		--ship-manifest '$(MVP_VERIFIED_DIR)/manifest.json' \
		--elf '$(WORKBENCH_OVERLAY_GUARD_ELF)' \
		--d81 '$(MVP_VERIFIED_DIR)/lisp65-mvp-workbench.d81' \
		--out-dir '$(WORKBENCH_OVERLAY_GUARD_REPORT_DIR)' \
		--prefix hw-workbench-overlay-stack-guard-verified

mvp-vm-stdlib-einsuite-core-workbench-footprint-report:
	$(MAKE) mvp-vm-stdlib-einsuite-core-workbench
	python3 tools/host-lisp/mvp_vm_stdlib_footprint.py \
		--out "$(WORKBENCH_REFERENCE_FOOTPRINT_REPORT)" \
		--prg "$(WORKBENCH_REFERENCE_PRG)" \
		--manifest "$(WORKBENCH_STDLIB_MANIFEST)" \
		--header "$(WORKBENCH_STDLIB_HEADER)" \
		--elf "$(WORKBENCH_REFERENCE_PRG).elf" \
		--nm "$(M65VMSTDLIB_NM)" \
		--size "$(M65VMSTDLIB_SIZE)" \
		--min-stack-gap "$(WORKBENCH_MIN_STACK_GAP)" \
		--min-boot-stack-gap "$(WORKBENCH_MIN_BOOT_STACK_GAP)" \
		--min-bank0-reserve "$(WORKBENCH_MIN_BANK0_RESERVE)" \
		--bank0-reserve-target "$(WORKBENCH_BANK0_RESERVE_TARGET)" \
		--max-prg-file-end "$(WORKBENCH_MAX_PRG_FILE_END)" \
		--m65-cflags "$(WORKBENCH_CFLAGS)" \
		--heap-cells "$(WORKBENCH_HEAP_CELLS)" \
		--eval-c src/eval.c \
		--native-c src/vm.c \
		--native-c src/symbol.c \
		--min-symbol-headroom "$(WORKBENCH_MIN_SYMBOL_HEADROOM)" \
		--boot-symbol-correction "$(WORKBENCH_BOOT_SYMBOL_CORRECTION)" \
		--extra-cflags "$(WORKBENCH_DEFINES)"
	@printf '==> geschrieben: %s\n' "$(WORKBENCH_REFERENCE_FOOTPRINT_REPORT)"

workbench-reference: $(WORKBENCH_REFERENCE_BUILD_TARGET)

workbench-reference-footprint-report: $(WORKBENCH_REFERENCE_FOOTPRINT_TARGET)

workbench-candidate: workbench-product

workbench-candidate-footprint-report: workbench-product-footprint-report

workbench-gate: check-product

workbench-disk-lib-budget-check: mvp-ship-artifacts
	python3 tools/host-lisp/workbench_disklib_budget.py \
		--resident-manifest "$(WORKBENCH_STDLIB_MANIFEST)" \
		--disk-lib-manifest "build/bytecode/libs/ide.manifest.json" \
		--disk-lib-manifest "build/bytecode/libs/idex.manifest.json" \
		--disk-lib-manifest "build/bytecode/libs/m65d.manifest.json" \
		--extra-cflags "$(WORKBENCH_DEFINES)" \
		--native-c src/vm.c \
		--native-c src/symbol.c \
		--boot-symbol-calibration "$(WORKBENCH_COMPOSITION_BOOT_SYMBOL_CALIBRATION)" \
		--boot-namepool-calibration "$(WORKBENCH_COMPOSITION_BOOT_NAMEPOOL_CALIBRATION)" \
		--retained-symbols "$(WORKBENCH_COMPOSITION_RETAINED_SYMBOLS)" \
		--retained-namepool-bytes "$(WORKBENCH_COMPOSITION_RETAINED_NAMEPOOL_BYTES)" \
		--boot-align8 \
		--min-load-headroom "$(WORKBENCH_MIN_LOAD_HEADROOM)" \
		--min-post-align-headroom "$(WORKBENCH_MIN_POST_ALIGN_HEADROOM)" \
		--min-ext-code-peak-headroom "$(WORKBENCH_MIN_EXT_CODE_PEAK_HEADROOM)" \
		--min-ext-code-post-headroom "$(WORKBENCH_MIN_EXT_CODE_POST_HEADROOM)" \
		--min-symbol-headroom "$(WORKBENCH_MIN_SYMBOL_HEADROOM)" \
		--min-namepool-headroom "$(WORKBENCH_MIN_NAMEPOOL_HEADROOM)" \
		--disk-file-max "$(WORKBENCH_DISK_FILE_MAX)"

workbench-symfn-dynamic-report: bytecode-p0-ide-lib-check
	python3 tools/host-lisp/ide_bytecode_dynamic_report.py \
		--suite "$(BYTECODE_IDE_LIB_SUITE)" \
		--out "$(WORKBENCH_SYMFN_DYNAMIC_REPORT)" \
		--include-compiler-scenarios \
		$(WORKBENCH_SYMFN_DYNAMIC_BUDGET_ARGS) \
		--check

workbench-persistence-gate: check-product check-hardware-dry-run

bytecode-p0-workbench-stdlib-artifacts:
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check --emit-artifacts $(WORKBENCH_STDLIB_PREFIX) $(WORKBENCH_SUITE)
	$(HOSTCC) -std=c99 -Wall -I. -include $(WORKBENCH_STDLIB_HEADER) -x c -c /dev/null -o $(WORKBENCH_BYTECODE_DIR)/header-smoke.o
	$(HOSTCC) -std=c99 -Wall -DLISP65_VM -I. -Isrc -include $(WORKBENCH_STDLIB_HEADER) -x c -c /dev/null -o $(WORKBENCH_BYTECODE_DIR)/vm-header-smoke.o
	$(HOSTCC) -std=c99 -Wall -DLISP65_VM -I. -Isrc -I$(WORKBENCH_BYTECODE_DIR) -c $(WORKBENCH_STDLIB_C) -o $(WORKBENCH_BYTECODE_DIR)/c-smoke.o
	$(HOSTCC) -std=c99 -Wall -DLISP65_VM -DLISP65_BYTECODE_STDLIB_EMIT_METADATA -I. -Isrc -I$(WORKBENCH_BYTECODE_DIR) -c $(WORKBENCH_STDLIB_C) -o $(WORKBENCH_BYTECODE_DIR)/metadata-c-smoke.o

workbench-ship-d81: bytecode-p0-ide-extra-lib-artifacts bytecode-p0-m65d-lib-artifacts scripts/build-workbench-d81.sh
	WORKBENCH_SHIP_D81="$(WORKBENCH_SHIP_D81)" \
		WORKBENCH_SHIP_D81_MANIFEST="$(WORKBENCH_SHIP_D81_MANIFEST)" \
		sh scripts/build-workbench-d81.sh

print-workbench-profile-common:
	@printf '%s\n' \
		'format=lisp65-resolved-profile-v1' \
		'profile=$(WORKBENCH_PROFILE_ID)' \
		'suite=$(WORKBENCH_SUITE)' \
		'heap_cells=$(WORKBENCH_HEAP_CELLS)' \
		'cflags=$(WORKBENCH_CFLAGS)' \
		'extra_cflags=$(WORKBENCH_DEFINES)' \
		'target_sources=$(WORKBENCH_TARGET_SRCS)' \
		'ldflags=$(WORKBENCH_LDFLAGS)'

print-workbench-reference-resolved-profile: print-workbench-profile-common
	@printf '%s\n' 'build_target=$(WORKBENCH_REFERENCE_FOOTPRINT_TARGET)'

print-workbench-resolved-profile: print-workbench-profile-common
	@printf '%s\n' \
		'product_kind=guarded-staged-overlay' \
		'build_target=$(WORKBENCH_FOOTPRINT_TARGET)' \
		'product_prg=$(WORKBENCH_PRG)' \
		'product_preload=$(WORKBENCH_PRODUCT_PRELOAD)' \
		'product_runtime_overlay=$(WORKBENCH_PRODUCT_RUNTIME_OVERLAY)' \
		'product_elf=$(WORKBENCH_PRODUCT_ELF)' \
		'product_guard=$(WORKBENCH_OVERLAY_GUARD_DEFINES)' \
		'eval_surface_contract=$(WORKBENCH_EVAL_SURFACE_FORMAT)' \
		'eval_surface_fixture=$(WORKBENCH_EVAL_SURFACE_FIXTURE)' \
		'eval_surface_fixture_sha256='"$$(sha256sum '$(WORKBENCH_EVAL_SURFACE_FIXTURE)' | awk '{print $$1}')" \
		'eval_route=internal-eval:treewalk-strip:lcc-run:p0-vm' \
		'eval_forbidden_public_functions=eval,eval-string'
print-workbench-overlay-resolved-profile: print-workbench-profile-common
	@printf '%s\n' \
		'build_target=workbench-overlay-footprint-audit' \
		'product_elf=$(WORKBENCH_PRODUCT_ELF)' \
		'eval_surface_contract=$(WORKBENCH_EVAL_SURFACE_FORMAT)' \
		'eval_surface_fixture=$(WORKBENCH_EVAL_SURFACE_FIXTURE)' \
		'eval_surface_fixture_sha256='"$$(sha256sum '$(WORKBENCH_EVAL_SURFACE_FIXTURE)' | awk '{print $$1}')" \
		'eval_route=internal-eval:treewalk-strip:lcc-run:p0-vm' \
		'eval_forbidden_public_functions=eval,eval-string' \
		'overlay_abi=$(WORKBENCH_OVERLAY_ABI_ID)' \
		'overlay_linker=$(WORKBENCH_OVERLAY_LD)' \
		'overlay_section=$(WORKBENCH_OVERLAY_SECTION)' \
		'overlay_entry=$(WORKBENCH_OVERLAY_ENTRY)' \
		'overlay_extra_defines=$(WORKBENCH_OVERLAY_EXTRA_DEFINES)' \
		'overlay_stage_alignment=256' \
		'overlay_stage_limit=$(WORKBENCH_OVERLAY_STAGE_LIMIT)' \
		'overlay_descriptor=L65O-v1-18-byte-crc16-ccitt-false' \
		'overlay_lifetime=boot-only' \
		'overlay_reclaim_point=after-boot-transaction' \
		'runtime_overlay_binding_schema=lisp65-runtime-overlay-package-v2' \
		'runtime_overlay_binary_format=lisp65-runtime-overlay-bank-v1' \
		'runtime_overlay_format_bank_tag=$(WORKBENCH_RUNTIME_OVERLAY_BANK)' \
		'runtime_overlay_storage_kind=attic-ram' \
		'runtime_overlay_storage_address=$(WORKBENCH_RUNTIME_OVERLAY_ADDRESS)' \
		'runtime_overlay_storage_address_bits=28' \
		'runtime_overlay_storage_persistence=reset-stable-power-volatile' \
		'runtime_overlay_slice_count=$(WORKBENCH_RUNTIME_OVERLAY_SLICE_COUNT)' \
		'runtime_overlay_max_slices=$(WORKBENCH_RUNTIME_OVERLAY_MAX_SLICES)' \
		'runtime_overlay_vma=$(WORKBENCH_RUNTIME_OVERLAY_VMA)' \
		'runtime_overlay_max_vma=$(WORKBENCH_RUNTIME_OVERLAY_MAX_VMA)' \
		'runtime_overlay_max_slice_bytes=$(WORKBENCH_RUNTIME_OVERLAY_MAX_SLICE_BYTES)' \
		'runtime_overlay_entry_abi=$(WORKBENCH_RUNTIME_OVERLAY_ENTRY_ABI)' \
		'runtime_overlay_lifetime=build-bound-reusable' \
		'resident_island_section=$(WORKBENCH_RESIDENT_ISLAND_SECTION)' \
		'resident_island_address=$(WORKBENCH_RESIDENT_ISLAND_BASE)' \
		'resident_island_limit=$(WORKBENCH_RESIDENT_ISLAND_LIMIT)' \
		'resident_island_payload_capacity=$(WORKBENCH_RESIDENT_ISLAND_CAPACITY)' \
		'resident_island_immutable_bytes=1485' \
		'resident_island_annex_section=.lisp65_resident_island_annex' \
		'resident_island_annex_start=0x1dce' \
		'resident_island_annex_end_exclusive=0x1ed2' \
		'resident_island_annex_bytes=260' \
		'resident_island_annex_root_count=128' \
		'resident_island_annex_reserve_bytes=302' \
		'resident_island_annex_lifetime=mutable-noload' \
		'resident_island_slot=37' \
		'resident_island_lifetime=boot-installed-resident' \
		'workbench_screen_base=$(WORKBENCH_SCREEN_BASE)' \
		'workbench_screen_geometry=$(WORKBENCH_SCREEN_COLUMNS)x$(WORKBENCH_SCREEN_ROWS)x$(WORKBENCH_SCREEN_CELL_BYTES)' \
		'workbench_screen_limit=$(WORKBENCH_SCREEN_LIMIT)' \
		'workbench_seam_contract=requires-screen-relocation-before-activation'

WORKBENCH_SHIP_GUARD_ENV = \
	MVP_VM_SHIP_BUILD_TARGET=workbench-product-input-ready \
	WORKBENCH_OVERLAY_GUARD_DIR='$(WORKBENCH_OVERLAY_GUARD_DIR)' \
	WORKBENCH_OVERLAY_GUARD_RESIDENT_PRG='$(WORKBENCH_PRG)' \
	WORKBENCH_OVERLAY_GUARD_PRELOAD='$(WORKBENCH_PRODUCT_PRELOAD)' \
	WORKBENCH_OVERLAY_GUARD_STAGE_MANIFEST='$(WORKBENCH_OVERLAY_GUARD_STAGE_MANIFEST)' \
	WORKBENCH_OVERLAY_GUARD_RUNTIME_IMAGE='$(WORKBENCH_PRODUCT_RUNTIME_OVERLAY)' \
	WORKBENCH_OVERLAY_GUARD_RUNTIME_MANIFEST='$(WORKBENCH_PRODUCT_RUNTIME_OVERLAY_MANIFEST)' \
	WORKBENCH_OVERLAY_GUARD_ABI_CONTRACT='$(WORKBENCH_OVERLAY_GUARD_ABI_CONTRACT)' \
	WORKBENCH_OVERLAY_GUARD_FOOTPRINT='$(WORKBENCH_FOOTPRINT_REPORT)'

.SECONDEXPANSION:
mvp-ship-artifacts: $$(if $$(filter $$(abspath $$(MVP_VERIFIED_DIR)),$$(abspath $$(MVP_VM_SHIP_DIR))),verify-ship,mvp-ship-candidate-artifacts)
	@:

mvp-ship-candidate-artifacts: workbench-product	## unverifizierter Workbench-Kandidat fuer lokale Gates
	$(WORKBENCH_SHIP_GUARD_ENV) sh scripts/build-mvp-vm-ship.sh

mvp-ship-wip: mvp-ship-artifacts

workbench-ship-artifacts-check: mvp-ship-artifacts
	python3 tools/host-lisp/workbench_ship.py verify --expect-format lisp65-workbench-ship-v5 --dir "$(MVP_CANDIDATE_DIR)"

workbench-ship-verifier-selftest:
	python3 tools/host-lisp/workbench_ship.py selftest

workbench-reproducibility-check:
	rm -rf build/reproducibility/workbench-guard-a build/reproducibility/workbench-guard-b \
		build/reproducibility/workbench-package-a build/reproducibility/workbench-package-b
	$(MAKE) --no-print-directory \
		WORKBENCH_OVERLAY_DIR=build/reproducibility/workbench-guard-a \
		WORKBENCH_OVERLAY_EXTRA_DEFINES='$(WORKBENCH_OVERLAY_GUARD_DEFINES)' \
		workbench-overlay-footprint-audit
	$(MAKE) --no-print-directory \
		WORKBENCH_OVERLAY_DIR=build/reproducibility/workbench-guard-b \
		WORKBENCH_OVERLAY_EXTRA_DEFINES='$(WORKBENCH_OVERLAY_GUARD_DEFINES)' \
		workbench-overlay-footprint-audit
	$(MAKE) --no-print-directory bytecode-p0-ide-lib-artifacts
	env -u MVP_VM_SHIP_PRG -u MVP_VM_SHIP_BLOB -u MVP_VM_SHIP_OVERLAYS -u MVP_VM_SHIP_D81 \
		-u MVP_VM_SHIP_MANIFEST -u MVP_VM_SHIP_FOOTPRINT -u MVP_VM_SHIP_D81_MANIFEST \
		-u WORKBENCH_SHIP_D81 -u WORKBENCH_SHIP_D81_MANIFEST \
		MVP_VM_SHIP_SKIP_BUILD=1 MVP_VM_SHIP_REPRODUCIBLE_PATHS=1 \
		MVP_VM_SHIP_DIR=build/reproducibility/workbench-package-a \
		WORKBENCH_OVERLAY_GUARD_DIR=build/reproducibility/workbench-guard-a \
		WORKBENCH_OVERLAY_GUARD_RESIDENT_PRG=build/reproducibility/workbench-guard-a/lisp65-workbench-resident.prg \
		WORKBENCH_OVERLAY_GUARD_PRELOAD=build/reproducibility/workbench-guard-a/stdlib-with-overlay.ext.bin \
		WORKBENCH_OVERLAY_GUARD_STAGE_MANIFEST=build/reproducibility/workbench-guard-a/stage-manifest.json \
		WORKBENCH_OVERLAY_GUARD_RUNTIME_IMAGE=build/reproducibility/workbench-guard-a/lisp65-mvp-workbench.overlays.bin \
		WORKBENCH_OVERLAY_GUARD_RUNTIME_MANIFEST=build/reproducibility/workbench-guard-a/runtime-overlays-manifest.json \
		WORKBENCH_OVERLAY_GUARD_ABI_CONTRACT=build/reproducibility/workbench-guard-a/resolved-profile.txt \
		WORKBENCH_OVERLAY_GUARD_FOOTPRINT=build/reproducibility/workbench-guard-a/footprint-audit.json \
		sh scripts/build-mvp-vm-ship.sh
	env -u MVP_VM_SHIP_PRG -u MVP_VM_SHIP_BLOB -u MVP_VM_SHIP_OVERLAYS -u MVP_VM_SHIP_D81 \
		-u MVP_VM_SHIP_MANIFEST -u MVP_VM_SHIP_FOOTPRINT -u MVP_VM_SHIP_D81_MANIFEST \
		-u WORKBENCH_SHIP_D81 -u WORKBENCH_SHIP_D81_MANIFEST \
		MVP_VM_SHIP_SKIP_BUILD=1 MVP_VM_SHIP_REPRODUCIBLE_PATHS=1 \
		MVP_VM_SHIP_DIR=build/reproducibility/workbench-package-b \
		WORKBENCH_OVERLAY_GUARD_DIR=build/reproducibility/workbench-guard-b \
		WORKBENCH_OVERLAY_GUARD_RESIDENT_PRG=build/reproducibility/workbench-guard-b/lisp65-workbench-resident.prg \
		WORKBENCH_OVERLAY_GUARD_PRELOAD=build/reproducibility/workbench-guard-b/stdlib-with-overlay.ext.bin \
		WORKBENCH_OVERLAY_GUARD_STAGE_MANIFEST=build/reproducibility/workbench-guard-b/stage-manifest.json \
		WORKBENCH_OVERLAY_GUARD_RUNTIME_IMAGE=build/reproducibility/workbench-guard-b/lisp65-mvp-workbench.overlays.bin \
		WORKBENCH_OVERLAY_GUARD_RUNTIME_MANIFEST=build/reproducibility/workbench-guard-b/runtime-overlays-manifest.json \
		WORKBENCH_OVERLAY_GUARD_ABI_CONTRACT=build/reproducibility/workbench-guard-b/resolved-profile.txt \
		WORKBENCH_OVERLAY_GUARD_FOOTPRINT=build/reproducibility/workbench-guard-b/footprint-audit.json \
		sh scripts/build-mvp-vm-ship.sh
	@set -eu; for artifact in \
		lisp65-mvp-workbench.prg lisp65-mvp-workbench.blob.bin lisp65-mvp-workbench.overlays.bin \
		lisp65-mvp-workbench.d81 mvp-vm-stdlib-footprint.txt \
		workbench-d81-manifest.txt stdlib-artifact-manifest.json \
		resolved-profile.txt toolchain-report.txt manifest.json; do \
		cmp "build/reproducibility/workbench-package-a/$$artifact" \
		    "build/reproducibility/workbench-package-b/$$artifact"; \
	done
	@printf '%s\n' 'workbench-reproducibility-check: PASS (all ten package files are byte-identical)'

verify-ship:
	python3 tools/host-lisp/workbench_ship.py verify --strict \
		--expect-format lisp65-workbench-ship-v5 --dir "$(MVP_VERIFIED_DIR)"

workbench-product-contract-ship-check: verify-ship workbench-product-contract-check
	python3 tools/host-lisp/workbench_product_contract.py --ship-dir "$(MVP_VERIFIED_DIR)"

workbench-deploy workbench-deploy-dry-run: override MVP_VERIFIED_DIR := build/ship
workbench-deploy: workbench-product-contract-ship-check
	MVP_VM_SHIP_PRG=build/ship/lisp65-mvp-workbench.prg \
		MVP_VM_SHIP_BLOB=build/ship/lisp65-mvp-workbench.blob.bin \
		MVP_VM_SHIP_OVERLAYS=build/ship/lisp65-mvp-workbench.overlays.bin \
		MVP_VM_SHIP_D81=build/ship/lisp65-mvp-workbench.d81 \
		sh scripts/hw-smoke-vm-stdlib.sh --no-build

workbench-deploy-dry-run: workbench-product-contract-ship-check
	MVP_VM_SHIP_PRG=build/ship/lisp65-mvp-workbench.prg \
		MVP_VM_SHIP_BLOB=build/ship/lisp65-mvp-workbench.blob.bin \
		MVP_VM_SHIP_OVERLAYS=build/ship/lisp65-mvp-workbench.overlays.bin \
		MVP_VM_SHIP_D81=build/ship/lisp65-mvp-workbench.d81 \
		sh scripts/hw-smoke-vm-stdlib.sh --dry-run --no-build

mvp-ship:	## sauberer, G0-G2-verifizierter Workbench-Kandidat
	python3 tools/host-lisp/workbench_ship.py preflight --out build/workbench-ship-preflight.json
	$(MAKE) check-product
	python3 tools/host-lisp/workbench_ship.py finalize --preflight build/workbench-ship-preflight.json --candidate "$(MVP_CANDIDATE_DIR)" --out "$(MVP_VERIFIED_DIR)"
	$(MAKE) verify-ship

workbench-d81-bam-sanity: mvp-ship-artifacts
	python3 tools/host-lisp/d81_bam_sanity.py "$(WORKBENCH_SHIP_D81)" \
		--expect-free-blocks "$(WORKBENCH_D81_EXPECT_FREE_BLOCKS)" \
		--expect-file-blocks "$(WORKBENCH_D81_EXPECT_FILE_BLOCKS)"

workbench-d81-bam-alloc-diff-selftest: mvp-ship-artifacts
	python3 tools/host-lisp/d81_bam_alloc_diff.py --selftest "$(WORKBENCH_SHIP_D81)" \
		--track "$(WORKBENCH_M2_TRACK)" --sector "$(WORKBENCH_M2_SECTOR)"

workbench-d81-chain-write-diff-selftest: mvp-ship-artifacts
	python3 tools/host-lisp/d81_chain_write_diff.py --selftest "$(WORKBENCH_SHIP_D81)" \
		--source "$(M3_CHAIN_SOURCE)" --track "$(WORKBENCH_M3_TRACK)" \
		--first-sector "$(WORKBENCH_M3_FIRST_SECTOR)" \
		--second-sector "$(WORKBENCH_M3_SECOND_SECTOR)"

workbench-d81-dir-write-diff-selftest: mvp-ship-artifacts
	python3 tools/host-lisp/d81_dir_write_diff.py --selftest "$(WORKBENCH_SHIP_D81)" \
		--source "$(M4_DIR_SOURCE)" --name "$(WORKBENCH_M4_NAME)" \
		--track "$(WORKBENCH_M4_TRACK)" \
		--first-sector "$(WORKBENCH_M4_FIRST_SECTOR)" \
		--second-sector "$(WORKBENCH_M4_SECOND_SECTOR)" \
		--dir-track "$(WORKBENCH_M4_DIR_TRACK)" \
		--dir-sector "$(WORKBENCH_M4_DIR_SECTOR)" \
		--dir-entry "$(WORKBENCH_M4_DIR_ENTRY)"

m65-disk-alloc-load-check: $(M65D_ALLOC_LOAD_CHECK)
	$(M65D_ALLOC_LOAD_CHECK) "$(M5_ALLOC_SOURCE)"

m65-disk-alloc-var-load-check: $(M65D_ALLOC_LOAD_CHECK)
	$(M65D_ALLOC_LOAD_CHECK) "$(M7_ALLOC_SOURCE)"

$(M65D_ALLOC_LOAD_CHECK): scripts/m65-disk-alloc-load-check-main.c $(M5_ALLOC_SOURCE) $(M5_SAVE_NEW_SRCS) | build
	$(HOSTCC) -std=c99 -Wall -DHEAP_CELLS=2048 -DGC_ROOTS=1024 -DMAX_SYM=512 -DNAMEPOOL=8192 \
		-Isrc scripts/m65-disk-alloc-load-check-main.c $(M5_SAVE_NEW_SRCS) -o $@

workbench-d81-save-new-diff-selftest: mvp-ship-artifacts
	mkdir -p build/hw
	cp "$(WORKBENCH_SHIP_D81)" "$(WORKBENCH_M5_SELFTEST_D81)"
	$(C1541) "$(WORKBENCH_M5_SELFTEST_D81)" -write "$(M5_ALLOC_SOURCE)" "$(WORKBENCH_M5_ALLOC_NAME),s" >/tmp/lisp65-m5-c1541.log 2>&1 || { cat /tmp/lisp65-m5-c1541.log >&2; exit 3; }
	python3 tools/host-lisp/d81_dir_write_diff.py --selftest "$(WORKBENCH_M5_SELFTEST_D81)" \
		--source "$(M5_NEW_SOURCE)" --name "$(WORKBENCH_M5_NAME)" \
		--track "$(WORKBENCH_M5_TRACK)" \
		--first-sector "$(WORKBENCH_M5_FIRST_SECTOR)" \
		--second-sector "$(WORKBENCH_M5_SECOND_SECTOR)" \
		--dir-track "$(WORKBENCH_M5_DIR_TRACK)" \
		--dir-sector "$(WORKBENCH_M5_DIR_SECTOR)" \
		--dir-entry "$(WORKBENCH_M5_DIR_ENTRY)"

workbench-d81-save-new-scan-diff-selftest: mvp-ship-artifacts
	mkdir -p build/hw
	cp "$(WORKBENCH_SHIP_D81)" "$(WORKBENCH_M6_SELFTEST_D81)"
	$(C1541) "$(WORKBENCH_M6_SELFTEST_D81)" -write "$(M5_ALLOC_SOURCE)" "$(WORKBENCH_M5_ALLOC_NAME),s" >/tmp/lisp65-m6-c1541.log 2>&1 || { cat /tmp/lisp65-m6-c1541.log >&2; exit 3; }
	python3 tools/host-lisp/d81_bam_reserve_sector.py "$(WORKBENCH_M6_SELFTEST_D81)" \
		--track "$(WORKBENCH_M5_TRACK)" \
		--sector "$(WORKBENCH_M6_RESERVE_SECTOR)"
	python3 tools/host-lisp/d81_dir_write_diff.py --selftest "$(WORKBENCH_M6_SELFTEST_D81)" \
		--source "$(M5_NEW_SOURCE)" --name "$(WORKBENCH_M6_NAME)" \
		--track "$(WORKBENCH_M5_TRACK)" \
		--first-sector "$(WORKBENCH_M6_FIRST_SECTOR)" \
		--second-sector "$(WORKBENCH_M6_SECOND_SECTOR)" \
		--dir-track "$(WORKBENCH_M5_DIR_TRACK)" \
		--dir-sector "$(WORKBENCH_M5_DIR_SECTOR)" \
		--dir-entry "$(WORKBENCH_M5_DIR_ENTRY)"

workbench-d81-save-new-var-diff-selftest: mvp-ship-artifacts
	mkdir -p build/hw
	cp "$(WORKBENCH_SHIP_D81)" "$(WORKBENCH_M7_SELFTEST_D81)"
	$(C1541) "$(WORKBENCH_M7_SELFTEST_D81)" -write "$(M7_ALLOC_SOURCE)" "$(WORKBENCH_M7_ALLOC_NAME),s" >/tmp/lisp65-m7-c1541.log 2>&1 || { cat /tmp/lisp65-m7-c1541.log >&2; exit 3; }
	python3 tools/host-lisp/d81_save_new_diff.py --selftest "$(WORKBENCH_M7_SELFTEST_D81)" \
		--source "$(M7_VAR_SOURCE)" --name "$(WORKBENCH_M7_NAME)" \
		--dir-track "$(WORKBENCH_M5_DIR_TRACK)" \
		--dir-sector "$(WORKBENCH_M5_DIR_SECTOR)" \
		--dir-entry "$(WORKBENCH_M5_DIR_ENTRY)"
