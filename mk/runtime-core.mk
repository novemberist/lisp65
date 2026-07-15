# Evaluator-free Runtime Core prototype and measurement gates.

RUNTIME_CORE_SRCS := \
	src/interrupt.c \
	src/mem.c \
	src/symbol.c \
	src/vm.c \
	src/vm_embed.c \
	products/runtime-core/preload_integrity.c \
	products/runtime-core/main.c

.PHONY: runtime-export-contract-check runtime-export-contract-selftest runtime-export-app-artifacts runtime-export-workbench-golden-selftest runtime-export-workbench-golden-check runtime-export-preload-selftest runtime-export-preload-bound runtime-export-ship-selftest runtime-export-hw-selftest runtime-export-hw-oracle runtime-export-g4 runtime-export-g5-mismatch-package runtime-export-g5-ready runtime-export-g5-clean runtime-export-g5-truncated runtime-export-g5-bitflip runtime-export-g5-build-id-mismatch runtime-export-g5-suite-verify runtime-export-candidate-pack runtime-export-candidate-verify runtime-export-candidate-check runtime-core-bytecode-artifacts runtime-core-prototype runtime-core-footprint-report runtime-core-audit runtime-core-prototype-check runtime-core-audit-selftest runtime-core-smoke runtime-preload-integrity-selftest runtime-core-overlay-link-prototype runtime-core-overlay-prototype runtime-core-overlay-package-verify runtime-core-inline-overlay-prototype runtime-core-inline-overlay-footprint-report runtime-core-inline-overlay-audit runtime-core-inline-overlay-audit-selftest runtime-core-inline-overlay-check print-runtime-core-resolved-profile print-runtime-core-overlay-resolved-profile print-runtime-core-inline-overlay-resolved-profile

RUNTIME_CORE_SMOKE_HOST := build/runtime-core-smoke-host

runtime-export-contract-selftest:
	python3 tools/host-lisp/runtime_export_contract.py --selftest

runtime-export-app-artifacts:
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check --emit-artifacts \
		$(RUNTIME_EXPORT_APP_PREFIX) --artifact-role disk-lib --base-addr 0x000000 \
		$(RUNTIME_CORE_SUITE)

runtime-export-workbench-golden-selftest:
	python3 tools/host-lisp/runtime_export_workbench_artifact.py selftest
	python3 tools/host-lisp/runtime_export_workbench_golden.py selftest

runtime-export-workbench-golden-check: runtime-export-workbench-golden-selftest $(RUNTIME_EXPORT_WORKBENCH_GOLDEN_REPORT)

$(RUNTIME_EXPORT_WORKBENCH_GOLDEN_REPORT): $(RUNTIME_EXPORT_APP_IMAGE) $(RUNTIME_EXPORT_WORKBENCH_REEMITTED_IMAGE) $(RUNTIME_EXPORT_WORKBENCH_EMISSION_RECEIPT) $(RUNTIME_EXPORT_WORKBENCH_REEMISSION_RECEIPT) $(RUNTIME_EXPORT_WORKBENCH_SHIP_MANIFEST) tools/host-lisp/runtime_export_workbench_golden.py | runtime-export-app-artifacts runtime-core-bytecode-artifacts
	mkdir -p '$(RUNTIME_EXPORT_STAGING_DIR)'
	python3 tools/host-lisp/runtime_export_workbench_golden.py check \
		--golden-l65m '$(RUNTIME_EXPORT_APP_IMAGE)' \
		--reemitted-l65m '$(RUNTIME_EXPORT_WORKBENCH_REEMITTED_IMAGE)' \
		--first-receipt '$(RUNTIME_EXPORT_WORKBENCH_EMISSION_RECEIPT)' \
		--reemission-receipt '$(RUNTIME_EXPORT_WORKBENCH_REEMISSION_RECEIPT)' \
		--ship-manifest '$(RUNTIME_EXPORT_WORKBENCH_SHIP_MANIFEST)' \
		--host-l65m '$(RUNTIME_EXPORT_HOST_APP_IMAGE)' \
		--host-preload '$(RUNTIME_CORE_STDLIB_BLOB)' \
		--report-out '$(RUNTIME_EXPORT_WORKBENCH_GOLDEN_REPORT)'

runtime-export-contract-check: runtime-export-contract-selftest runtime-export-workbench-golden-check runtime-export-preload-selftest runtime-preload-integrity-selftest
	python3 tools/host-lisp/runtime_export_contract.py $(RUNTIME_EXPORT_CONTRACT) \
		--artifact $(RUNTIME_EXPORT_APP_IMAGE) --manifest $(RUNTIME_EXPORT_APP_MANIFEST)

runtime-export-ship-selftest:
	python3 tools/host-lisp/runtime_export_ship.py selftest

runtime-export-hw-selftest:
	python3 tools/host-lisp/runtime_export_hw_harness_test.py

runtime-export-hw-oracle: runtime-export-candidate-verify
	rm -f '$(RUNTIME_EXPORT_HW_ORACLE)'
	python3 tools/host-lisp/runtime_export_hw_oracle.py create \
		--package '$(RUNTIME_EXPORT_CANDIDATE_DIR)' \
		--elf '$(RUNTIME_CORE_INLINE_OVERLAY_PRG).elf' \
		--nm '$(M65VMSTDLIB_NM)' --objcopy '$(LLVM)/llvm-objcopy' \
		--out '$(RUNTIME_EXPORT_HW_ORACLE)'
	python3 tools/host-lisp/runtime_export_hw_oracle.py verify \
		--package '$(RUNTIME_EXPORT_CANDIDATE_DIR)' \
		--oracle '$(RUNTIME_EXPORT_HW_ORACLE)'

runtime-export-g4: runtime-export-hw-selftest runtime-export-hw-oracle
	@set -eu; \
		tmp='$(RUNTIME_EXPORT_G4_PLAN).tmp'; \
		scripts/runtime-export-deploy.sh --gate G4 --phase clean \
			--package '$(RUNTIME_EXPORT_CANDIDATE_DIR)' \
			--oracle '$(RUNTIME_EXPORT_HW_ORACLE)' \
			--out-dir '$(RUNTIME_EXPORT_DIR)/g4-no-side-effects' > "$$tmp"; \
		python3 tools/host-lisp/runtime_export_hw_oracle.py verify-plan \
			--plan "$$tmp" --phase clean; \
		mv "$$tmp" '$(RUNTIME_EXPORT_G4_PLAN)'

runtime-export-g5-mismatch-package: runtime-export-hw-oracle
	rm -rf '$(RUNTIME_EXPORT_MISMATCH_DIR)'
	python3 tools/host-lisp/runtime_export_hw_oracle.py create-mismatch-package \
		--package '$(RUNTIME_EXPORT_CANDIDATE_DIR)' \
		--out '$(RUNTIME_EXPORT_MISMATCH_DIR)'

runtime-export-g5-ready: runtime-export-g4 runtime-export-g5-mismatch-package
	@set -eu; \
		rm -rf '$(RUNTIME_EXPORT_G4_PHASE_DIR)'; \
		mkdir -p '$(RUNTIME_EXPORT_G4_PHASE_DIR)'; \
		for phase in clean truncated bitflip build-id-mismatch; do \
			extra=''; \
			if test "$$phase" = build-id-mismatch; then \
				extra="--mismatch-package $(RUNTIME_EXPORT_MISMATCH_DIR)"; \
			fi; \
			scripts/runtime-export-deploy.sh --gate G4 --phase "$$phase" \
				--package '$(RUNTIME_EXPORT_CANDIDATE_DIR)' \
				--oracle '$(RUNTIME_EXPORT_HW_ORACLE)' $$extra \
				--out-dir '$(RUNTIME_EXPORT_DIR)/g4-no-side-effects' \
				> '$(RUNTIME_EXPORT_G4_PHASE_DIR)'/"$$phase".json; \
		done; \
		python3 tools/host-lisp/runtime_export_hw_oracle.py verify-plan-suite \
			--plan '$(RUNTIME_EXPORT_G4_PHASE_DIR)/clean.json' \
			--plan '$(RUNTIME_EXPORT_G4_PHASE_DIR)/truncated.json' \
			--plan '$(RUNTIME_EXPORT_G4_PHASE_DIR)/bitflip.json' \
			--plan '$(RUNTIME_EXPORT_G4_PHASE_DIR)/build-id-mismatch.json'

define RUNTIME_EXPORT_G5_PHASE_TARGET
runtime-export-g5-$(1): runtime-export-g5-ready
	@test '$(RUNTIME_EXPORT_G5_POWER_CYCLE_TOKEN)' = POWER-CYCLED || \
		{ printf '%s\n' 'Set RUNTIME_EXPORT_G5_POWER_CYCLE_TOKEN=POWER-CYCLED after a physical power-cycle.' >&2; exit 2; }
	@test -n '$(RUNTIME_EXPORT_G5_CYCLE_ID)' || \
		{ printf '%s\n' 'Set a fresh RUNTIME_EXPORT_G5_CYCLE_ID for this physical power-cycle.' >&2; exit 2; }
	scripts/runtime-export-deploy.sh --gate G5 --phase '$(2)' \
		--package '$(RUNTIME_EXPORT_CANDIDATE_DIR)' \
		--oracle '$(RUNTIME_EXPORT_HW_ORACLE)' $(3) \
		--out-dir '$(RUNTIME_EXPORT_G5_EVIDENCE_DIR)/$(2)' \
		--tools '$(RUNTIME_EXPORT_G5_TOOLS)' --device '$(RUNTIME_EXPORT_G5_DEVICE)' \
		--power-cycle-token '$(RUNTIME_EXPORT_G5_POWER_CYCLE_TOKEN)' \
		--cycle-id '$(RUNTIME_EXPORT_G5_CYCLE_ID)'
endef

$(eval $(call RUNTIME_EXPORT_G5_PHASE_TARGET,clean,clean,))
$(eval $(call RUNTIME_EXPORT_G5_PHASE_TARGET,truncated,truncated,))
$(eval $(call RUNTIME_EXPORT_G5_PHASE_TARGET,bitflip,bitflip,))
$(eval $(call RUNTIME_EXPORT_G5_PHASE_TARGET,build-id-mismatch,build-id-mismatch,--mismatch-package '$(RUNTIME_EXPORT_MISMATCH_DIR)'))

runtime-export-g5-suite-verify: runtime-export-g5-ready
	python3 tools/host-lisp/runtime_export_hw_oracle.py verify-suite \
		--package '$(RUNTIME_EXPORT_CANDIDATE_DIR)' \
		--oracle '$(RUNTIME_EXPORT_HW_ORACLE)' \
		--mismatch-package '$(RUNTIME_EXPORT_MISMATCH_DIR)' \
		--receipt '$(RUNTIME_EXPORT_G5_EVIDENCE_DIR)/clean/receipt-clean.json' \
		--receipt '$(RUNTIME_EXPORT_G5_EVIDENCE_DIR)/truncated/receipt-truncated.json' \
		--receipt '$(RUNTIME_EXPORT_G5_EVIDENCE_DIR)/bitflip/receipt-bitflip.json' \
		--receipt '$(RUNTIME_EXPORT_G5_EVIDENCE_DIR)/build-id-mismatch/receipt-build-id-mismatch.json'

runtime-export-preload-selftest:
	python3 tools/host-lisp/runtime_export_preload.py selftest

runtime-preload-integrity-selftest: | build
	$(HOSTCC) -std=c99 -Wall -Wextra -Werror -O1 -g \
		-fsanitize=address,undefined -fno-omit-frame-pointer \
		-Iproducts/runtime-core scripts/runtime-preload-integrity-main.c \
		products/runtime-core/preload_integrity.c -o build/runtime-preload-integrity-host
	ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 build/runtime-preload-integrity-host

runtime-export-preload-bound: $(RUNTIME_EXPORT_BOUND_PRELOAD) $(RUNTIME_EXPORT_PRELOAD_HEADER)

runtime-export-candidate-pack: runtime-export-contract-check runtime-core-inline-overlay-check $(RUNTIME_EXPORT_RESOLVED_PROFILE) $(RUNTIME_EXPORT_TOOLCHAIN_REPORT)
	python3 tools/host-lisp/runtime_export_ship.py pack \
		--contract '$(RUNTIME_EXPORT_CONTRACT)' \
		--app '$(RUNTIME_EXPORT_APP)' \
		--app-image '$(RUNTIME_EXPORT_APP_IMAGE)' \
		--app-manifest '$(RUNTIME_EXPORT_APP_MANIFEST)' \
		--preload '$(RUNTIME_EXPORT_BOUND_PRELOAD)' \
		--preload-manifest '$(RUNTIME_CORE_STDLIB_MANIFEST)' \
		--prg '$(RUNTIME_CORE_INLINE_OVERLAY_PRG)' \
		--elf '$(RUNTIME_CORE_INLINE_OVERLAY_PRG).elf' \
		--nm '$(M65VMSTDLIB_NM)' \
		--objdump '$(LLVM)/llvm-objdump' \
		--profile '$(RUNTIME_EXPORT_RESOLVED_PROFILE)' \
		--toolchain-report '$(RUNTIME_EXPORT_TOOLCHAIN_REPORT)' \
		--audit-report '$(RUNTIME_CORE_INLINE_OVERLAY_AUDIT_REPORT)' \
		--footprint-report '$(RUNTIME_CORE_INLINE_OVERLAY_FOOTPRINT_REPORT)' \
		--workbench-emission-receipt '$(RUNTIME_EXPORT_WORKBENCH_EMISSION_RECEIPT)' \
		--workbench-reemission-receipt '$(RUNTIME_EXPORT_WORKBENCH_REEMISSION_RECEIPT)' \
		--workbench-ship-manifest '$(RUNTIME_EXPORT_WORKBENCH_SHIP_MANIFEST)' \
		--out-dir '$(RUNTIME_EXPORT_CANDIDATE_DIR)'

runtime-export-candidate-verify: runtime-export-candidate-pack
	python3 tools/host-lisp/runtime_export_ship.py verify --dir '$(RUNTIME_EXPORT_CANDIDATE_DIR)'

runtime-export-candidate-check: runtime-core-smoke runtime-export-ship-selftest runtime-export-hw-selftest runtime-export-candidate-verify
	rm -rf '$(RUNTIME_EXPORT_REPRO_BASELINE_DIR)'
	mkdir -p '$(RUNTIME_EXPORT_REPRO_BASELINE_DIR)'
	cp '$(RUNTIME_EXPORT_CANDIDATE_DIR)'/* '$(RUNTIME_EXPORT_REPRO_BASELINE_DIR)'/
	$(MAKE) --no-print-directory runtime-export-candidate-verify
	@set -eu; \
		for artifact in manifest.json resolved-profile.txt runtime-app.json \
			runtime-app.l65m runtime-preload.bin runtime.prg toolchain-report.txt; do \
			cmp '$(RUNTIME_EXPORT_REPRO_BASELINE_DIR)'/"$$artifact" \
				'$(RUNTIME_EXPORT_CANDIDATE_DIR)'/"$$artifact"; \
		done; \
			printf '%s\n' 'runtime-export-reproducibility: PASS files=7'
	$(MAKE) --no-print-directory runtime-export-g5-ready

runtime-core-bytecode-artifacts:
	python3 tools/host-lisp/bytecode_p0_stdlib.py --check --emit-artifacts $(RUNTIME_CORE_STDLIB_PREFIX) $(RUNTIME_CORE_SUITE)
	$(HOSTCC) -std=c99 -Wall -DLISP65_VM -I. -Isrc -include $(RUNTIME_CORE_STDLIB_HEADER) -x c -c /dev/null -o $(RUNTIME_CORE_BYTECODE_DIR)/header-smoke.o

$(RUNTIME_EXPORT_RESOLVED_PROFILE): $(RUNTIME_EXPORT_CONTRACT) $(RUNTIME_EXPORT_APP) $(RUNTIME_CORE_SUITE) $(RUNTIME_EXPORT_APP_IMAGE) $(RUNTIME_EXPORT_WORKBENCH_EMISSION_RECEIPT) $(RUNTIME_EXPORT_WORKBENCH_REEMISSION_RECEIPT) $(RUNTIME_EXPORT_WORKBENCH_SHIP_MANIFEST) lib/lcc.lisp lib/lcc-fasl.lisp lib/ide-disk.lisp config/runtime-core.mk mk/runtime-core.mk $(RUNTIME_CORE_INLINE_OVERLAY_LD) | build
	@set -eu; \
		mkdir -p '$(RUNTIME_EXPORT_STAGING_DIR)'; \
		tmp='$@.tmp'; \
		printf '%s\n' \
				'format=lisp65-runtime-export-resolved-profile-v2' \
				'profile=runtime-export-v2-candidate' \
			'status=candidate' \
			'layout=inline-boot-overlay' \
			'entry_abi=named-zero-argument-p0' \
			'runtime_entry=$(RUNTIME_CORE_ENTRY)' \
			'runtime_prg_format=mega65-prg' \
			'runtime_prg_load_address=0x2001' \
			'application_preload=bank5-build-bound' \
			'runtime_preload_address=0x050000' \
			'runtime_disk_loader=false' \
			'application_descriptor_format=lisp65-runtime-app-v1' \
			'application_artifact_format=lisp65-bytecode-p0-disk-lib-artifacts-v1' \
			'application_bytecode_abi=P0' \
			'application_l65m_version=1' \
				'application_emitter=workbench-lcc-fasl-v1' \
			'min_boot_stack_gap=$(RUNTIME_CORE_INLINE_OVERLAY_MIN_BOOT_STACK_GAP)' \
			'min_post_boot_reserve=$(RUNTIME_CORE_INLINE_OVERLAY_MIN_POST_BOOT_RESERVE)' \
			'post_boot_reserve_target=$(RUNTIME_CORE_BANK0_RESERVE_TARGET)' \
			'max_prg_file_end=$(RUNTIME_CORE_INLINE_OVERLAY_MAX_FILE_END)' \
			'min_symbol_headroom=$(RUNTIME_CORE_MIN_SYMBOL_HEADROOM)' \
			'g2_elf_surface=passed-by-inline-overlay-audit' \
			'g2_budgets=passed-by-inline-overlay-audit' \
			'g2_inline_overlay_audit=passed' \
			'g2_package_verifier=required-post-pack' \
			'g2_reproducibility=required-post-pack' \
			"contract_sha256=$$(sha256sum '$(RUNTIME_EXPORT_CONTRACT)' | awk '{print $$1}')" \
			"app_descriptor_sha256=$$(sha256sum '$(RUNTIME_EXPORT_APP)' | awk '{print $$1}')" \
			"suite_sha256=$$(sha256sum '$(RUNTIME_CORE_SUITE)' | awk '{print $$1}')" \
			"config_sha256=$$(sha256sum 'config/runtime-core.mk' | awk '{print $$1}')" \
			"make_sha256=$$(sha256sum 'mk/runtime-core.mk' | awk '{print $$1}')" \
				"inline_linker_sha256=$$(sha256sum '$(RUNTIME_CORE_INLINE_OVERLAY_LD)' | awk '{print $$1}')" \
				"workbench_golden_sha256=$$(sha256sum '$(RUNTIME_EXPORT_APP_IMAGE)' | awk '{print $$1}')" \
				"workbench_emission_receipt_sha256=$$(sha256sum '$(RUNTIME_EXPORT_WORKBENCH_EMISSION_RECEIPT)' | awk '{print $$1}')" \
				"workbench_reemission_receipt_sha256=$$(sha256sum '$(RUNTIME_EXPORT_WORKBENCH_REEMISSION_RECEIPT)' | awk '{print $$1}')" \
				"workbench_ship_manifest_sha256=$$(sha256sum '$(RUNTIME_EXPORT_WORKBENCH_SHIP_MANIFEST)' | awk '{print $$1}')" \
			> "$$tmp"; \
		mv "$$tmp" '$@'

$(RUNTIME_EXPORT_TOOLCHAIN_REPORT): mk/toolchain.mk $(CC_M65) $(M65VMSTDLIB_NM) $(M65VMSTDLIB_SIZE) $(LLVM)/llvm-objdump $(RUNTIME_EXPORT_WORKBENCH_GOLDEN_REPORT) | build
	@set -eu; \
		mkdir -p '$(RUNTIME_EXPORT_STAGING_DIR)'; \
		tmp='$@.tmp'; \
		cc='$(CC_M65)'; nm='$(M65VMSTDLIB_NM)'; size='$(M65VMSTDLIB_SIZE)'; objdump='$(LLVM)/llvm-objdump'; \
		printf '%s\n' \
			'format=lisp65-runtime-export-toolchain-report-v1' \
			"cc=$$cc" \
			"cc_sha256=$$(sha256sum "$$cc" | awk '{print $$1}')" \
			"cc_version=$$("$$cc" --version | sed -n '1p')" \
			"nm=$$nm" \
			"nm_sha256=$$(sha256sum "$$nm" | awk '{print $$1}')" \
			"size=$$size" \
			"size_sha256=$$(sha256sum "$$size" | awk '{print $$1}')" \
			"objdump=$$objdump" \
			"objdump_sha256=$$(sha256sum "$$objdump" | awk '{print $$1}')" \
				"python_version=$$(python3 --version 2>&1)" \
				"workbench_golden_report_sha256=$$(sha256sum '$(RUNTIME_EXPORT_WORKBENCH_GOLDEN_REPORT)' | awk '{print $$1}')" \
				"workbench_emission_receipt_sha256=$$(sha256sum '$(RUNTIME_EXPORT_WORKBENCH_EMISSION_RECEIPT)' | awk '{print $$1}')" \
				"workbench_reemission_receipt_sha256=$$(sha256sum '$(RUNTIME_EXPORT_WORKBENCH_REEMISSION_RECEIPT)' | awk '{print $$1}')" \
			> "$$tmp"; \
		mv "$$tmp" '$@'

$(RUNTIME_EXPORT_WORKBENCH_PRELOAD): $(RUNTIME_EXPORT_APP_IMAGE) tools/host-lisp/runtime_export_workbench_artifact.py
	@mkdir -p '$(RUNTIME_EXPORT_STAGING_DIR)'
	python3 tools/host-lisp/runtime_export_workbench_artifact.py rebase \
		--l65m '$(RUNTIME_EXPORT_APP_IMAGE)' --out '$@'

$(RUNTIME_EXPORT_BOUND_PRELOAD) $(RUNTIME_EXPORT_PRELOAD_HEADER) &: $(RUNTIME_EXPORT_WORKBENCH_PRELOAD) $(RUNTIME_EXPORT_RESOLVED_PROFILE) tools/host-lisp/runtime_export_preload.py
	@set -eu; \
		build_id="$$(sha256sum '$(RUNTIME_EXPORT_RESOLVED_PROFILE)' | cut -c1-8)"; \
		python3 tools/host-lisp/runtime_export_preload.py build \
			--payload '$(RUNTIME_EXPORT_WORKBENCH_PRELOAD)' --build-id "0x$$build_id" \
			--out '$(RUNTIME_EXPORT_BOUND_PRELOAD)' --header '$(RUNTIME_EXPORT_PRELOAD_HEADER)'

runtime-core-prototype: $(RUNTIME_CORE_PRG)

# AP4.3 experiment only: build a resident PRG plus one raw, fixed-address boot
# overlay from the same ELF.  Loading/verification remains a separate contract;
# this target is intentionally absent from check-product.
runtime-core-overlay-link-prototype: $(RUNTIME_CORE_OVERLAY_RESIDENT_PRG) $(RUNTIME_CORE_OVERLAY_RAW) $(RUNTIME_CORE_OVERLAY_ABI_CONTRACT)

runtime-core-overlay-prototype: $(RUNTIME_CORE_OVERLAY_MANIFEST)

runtime-core-overlay-package-verify: $(RUNTIME_CORE_OVERLAY_MANIFEST)
	@set -eu; \
		elf='$(RUNTIME_CORE_OVERLAY_LINKED_PRG).elf'; \
		symbols="$$($(M65VMSTDLIB_NM) --defined-only "$$elf")"; \
		sym() { printf '%s\n' "$$symbols" | awk -v name="$$1" '$$3 == name { print "0x" $$1 }'; }; \
		base="$$(sym __lisp65_runtime_core_overlay_vma)"; \
		end="$$(sym __lisp65_runtime_core_overlay_end)"; \
		entry="$$(sym __lisp65_runtime_core_overlay_entry)"; \
		resident_end="$$(sym __lisp65_runtime_core_resident_file_end)"; \
		python3 tools/host-lisp/overlay_package.py verify --strict \
			--dir '$(RUNTIME_CORE_OVERLAY_PACKAGE_DIR)' \
			--expect-profile '$(RUNTIME_CORE_PROFILE_ID)' \
			--expect-base "$$base" --expect-end "$$end" \
			--expect-entry "$$entry" --expect-entry-symbol vm_load_embedded_stdlib \
			--expect-load-base "$$base" --expect-load-mode fixed-vma-raw \
			--expect-staging-mode separate-image --expect-lifetime boot-only \
			--expect-reclaim-point before-deep-stack --expect-abi-id '$(RUNTIME_CORE_OVERLAY_ABI_ID)' \
			--resident '$(RUNTIME_CORE_OVERLAY_RESIDENT_PRG)' \
			--expect-resident-load-base 0x2001 --expect-resident-file-end "$$resident_end" \
			--abi-contract '$(RUNTIME_CORE_OVERLAY_ABI_CONTRACT)'

# AP4.3 Runtime path: reset-safe single-PRG image.  This remains a non-default
# prototype until hardware loading and stack-reclaim behavior have been gated.
runtime-core-inline-overlay-prototype: $(RUNTIME_CORE_INLINE_OVERLAY_PRG)

runtime-core-inline-overlay-footprint-report: $(RUNTIME_CORE_INLINE_OVERLAY_PRG)
	python3 tools/host-lisp/mvp_vm_stdlib_footprint.py \
		--out "$(RUNTIME_CORE_INLINE_OVERLAY_FOOTPRINT_REPORT)" \
		--prg "$(RUNTIME_CORE_INLINE_OVERLAY_PRG)" \
		--manifest "$(RUNTIME_CORE_STDLIB_MANIFEST)" \
		--header "$(RUNTIME_CORE_STDLIB_HEADER)" \
		--elf "$(RUNTIME_CORE_INLINE_OVERLAY_PRG).elf" \
		--nm "$(M65VMSTDLIB_NM)" \
		--size "$(M65VMSTDLIB_SIZE)" \
		--min-stack-gap "$(RUNTIME_CORE_MIN_STACK_GAP)" \
		--min-boot-stack-gap "$(RUNTIME_CORE_INLINE_OVERLAY_MIN_BOOT_STACK_GAP)" \
		--min-bank0-reserve "$(RUNTIME_CORE_INLINE_OVERLAY_MIN_POST_BOOT_RESERVE)" \
		--bank0-reserve-target "$(RUNTIME_CORE_BANK0_RESERVE_TARGET)" \
		--max-prg-file-end "$(RUNTIME_CORE_INLINE_OVERLAY_MAX_FILE_END)" \
		--m65-cflags "$(RUNTIME_CORE_CFLAGS)" \
		--heap-cells "$(RUNTIME_CORE_HEAP_CELLS)" \
		--eval-c products/runtime-core/main.c \
		--native-c src/vm.c \
		--native-c src/symbol.c \
		--min-symbol-headroom "$(RUNTIME_CORE_MIN_SYMBOL_HEADROOM)" \
		--boot-symbol-correction 0 \
		--extra-cflags "$(RUNTIME_CORE_DEFINES) $(RUNTIME_CORE_PRELOAD_DEFINE) -DLISP65_STDLIB_BOOT_OVERLAY_CODE"

runtime-core-inline-overlay-audit: $(RUNTIME_CORE_INLINE_OVERLAY_PRG)
	python3 tools/host-lisp/runtime_core_inline_overlay_audit.py \
		--elf "$(RUNTIME_CORE_INLINE_OVERLAY_PRG).elf" \
		--prg "$(RUNTIME_CORE_INLINE_OVERLAY_PRG)" \
		--nm "$(M65VMSTDLIB_NM)" \
		--objdump "$(LLVM)/llvm-objdump" \
		--entry vm_load_embedded_stdlib --boot-caller main --runtime-entry vm_run_dir \
		--min-boot-stack-gap "$(RUNTIME_CORE_INLINE_OVERLAY_MIN_BOOT_STACK_GAP)" \
		--runtime-stack-budget "$(RUNTIME_CORE_INLINE_OVERLAY_RUNTIME_STACK_BUDGET)" \
		--min-post-boot-reserve "$(RUNTIME_CORE_INLINE_OVERLAY_MIN_POST_BOOT_RESERVE)" \
		--max-file-end "$(RUNTIME_CORE_INLINE_OVERLAY_MAX_FILE_END)" \
		--out "$(RUNTIME_CORE_INLINE_OVERLAY_AUDIT_REPORT)"

runtime-core-inline-overlay-audit-selftest:
	python3 tools/host-lisp/runtime_core_inline_overlay_audit.py --selftest

runtime-core-inline-overlay-check: runtime-core-inline-overlay-footprint-report runtime-core-inline-overlay-audit runtime-core-inline-overlay-audit-selftest

$(RUNTIME_CORE_INLINE_OVERLAY_PRG): $(RUNTIME_CORE_SRCS) $(RUNTIME_CORE_SUITE) lib/runtime-core.lisp $(RUNTIME_CORE_INLINE_OVERLAY_LD) $(RUNTIME_EXPORT_PRELOAD_HEADER) FORCE | build
	$(MAKE) runtime-core-bytecode-artifacts
	mkdir -p $(RUNTIME_CORE_INLINE_OVERLAY_DIR)
	$(CC_M65) $(RUNTIME_CORE_CFLAGS) -DLISP65_VM -DLISP65_EMBED_STDLIB -DLISP65_EMBED_DMA \
		-DHEAP_CELLS=$(RUNTIME_CORE_HEAP_CELLS) $(RUNTIME_CORE_DEFINES) \
		$(RUNTIME_CORE_PRELOAD_DEFINE) \
		'-DLISP65_RUNTIME_ENTRY="$(RUNTIME_CORE_ENTRY)"' \
		-DLISP65_STDLIB_BOOT_OVERLAY_CODE \
		-Isrc -I$(RUNTIME_CORE_BYTECODE_DIR) $(RUNTIME_CORE_SRCS) $(RUNTIME_CORE_STDLIB_C) \
		$(RUNTIME_CORE_LDFLAGS) -Wl,-T,$(RUNTIME_CORE_INLINE_OVERLAY_LD) \
		-Wl,--defsym=__lisp65_runtime_core_inline_required_boot_stack_param=$(RUNTIME_CORE_INLINE_OVERLAY_MIN_BOOT_STACK_GAP) \
		-Wl,--defsym=__lisp65_runtime_core_inline_required_runtime_stack_param=$(RUNTIME_CORE_INLINE_OVERLAY_RUNTIME_STACK_BUDGET) \
		-Wl,--defsym=__lisp65_runtime_core_inline_required_post_boot_reserve_param=$(RUNTIME_CORE_INLINE_OVERLAY_MIN_POST_BOOT_RESERVE) \
		-Wl,--defsym=__lisp65_runtime_core_inline_max_file_end_param=$(RUNTIME_CORE_INLINE_OVERLAY_MAX_FILE_END) \
		-o $@
	@printf 'built %s (%s bytes, reset-safe inline boot overlay)\n' "$@" "$$(stat -c%s $@)"

$(RUNTIME_CORE_OVERLAY_LINKED_PRG): $(RUNTIME_CORE_SRCS) $(RUNTIME_CORE_SUITE) lib/runtime-core.lisp $(RUNTIME_CORE_OVERLAY_LD) $(RUNTIME_EXPORT_PRELOAD_HEADER) FORCE | build
	$(MAKE) runtime-core-bytecode-artifacts
	mkdir -p $(RUNTIME_CORE_OVERLAY_DIR)
	$(CC_M65) $(RUNTIME_CORE_CFLAGS) -DLISP65_VM -DLISP65_EMBED_STDLIB -DLISP65_EMBED_DMA \
		-DHEAP_CELLS=$(RUNTIME_CORE_HEAP_CELLS) $(RUNTIME_CORE_DEFINES) \
		$(RUNTIME_CORE_PRELOAD_DEFINE) \
		'-DLISP65_RUNTIME_ENTRY="$(RUNTIME_CORE_ENTRY)"' \
		-DLISP65_STDLIB_BOOT_OVERLAY_CODE \
		-Isrc -I$(RUNTIME_CORE_BYTECODE_DIR) $(RUNTIME_CORE_SRCS) $(RUNTIME_CORE_STDLIB_C) \
		$(RUNTIME_CORE_LDFLAGS) -Wl,-T,$(RUNTIME_CORE_OVERLAY_LD) -o $@

$(RUNTIME_CORE_OVERLAY_RESIDENT_PRG): $(RUNTIME_CORE_OVERLAY_LINKED_PRG)
	@set -eu; \
		elf='$(RUNTIME_CORE_OVERLAY_LINKED_PRG).elf'; \
		end_hex="$$($(M65VMSTDLIB_NM) --defined-only "$$elf" | awk '$$3 == "__lisp65_runtime_core_resident_file_end" { print $$1 }')"; \
		test -n "$$end_hex"; \
		count=$$((0x$$end_hex - 0x2001 + 2)); \
		test "$$count" -gt 2; \
		dd if='$<' of='$@' bs=1 count="$$count" status=none; \
		printf 'built %s (%s bytes, file_end=$$%s)\n' '$@' "$$count" "$${end_hex#0000}"

$(RUNTIME_CORE_OVERLAY_RAW): $(RUNTIME_CORE_OVERLAY_LINKED_PRG)
	$(RUNTIME_CORE_OBJCOPY) -O binary --only-section=$(RUNTIME_CORE_OVERLAY_SECTION) '$<.elf' '$@'
	@printf 'built %s (%s bytes, VMA=%s)\n' '$@' "$$(stat -c%s '$@')" '$(RUNTIME_CORE_OVERLAY_VMA)'

$(RUNTIME_CORE_OVERLAY_ABI_CONTRACT): $(RUNTIME_CORE_OVERLAY_LINKED_PRG) config/runtime-core.mk mk/runtime-core.mk $(RUNTIME_CORE_OVERLAY_LD) | build
	@mkdir -p $(RUNTIME_CORE_OVERLAY_DIR)
	@$(MAKE) --no-print-directory print-runtime-core-overlay-resolved-profile > '$@'
	@printf '%s\n' \
		'external_blob=$(RUNTIME_CORE_STDLIB_BLOB)' \
		'external_blob_sha256='"$$(sha256sum '$(RUNTIME_CORE_STDLIB_BLOB)' | awk '{print $$1}')" \
		'bytecode_manifest_sha256='"$$(sha256sum '$(RUNTIME_CORE_STDLIB_MANIFEST)' | awk '{print $$1}')" \
		>> '$@'

$(RUNTIME_CORE_OVERLAY_MANIFEST): $(RUNTIME_CORE_OVERLAY_RAW) $(RUNTIME_CORE_OVERLAY_RESIDENT_PRG) $(RUNTIME_CORE_OVERLAY_ABI_CONTRACT) tools/host-lisp/overlay_package.py
	@set -eu; \
		elf='$(RUNTIME_CORE_OVERLAY_LINKED_PRG).elf'; \
		symbols="$$($(M65VMSTDLIB_NM) --defined-only "$$elf")"; \
		sym() { printf '%s\n' "$$symbols" | awk -v name="$$1" '$$3 == name { print "0x" $$1 }'; }; \
		base="$$(sym __lisp65_runtime_core_overlay_vma)"; \
		lma="$$(sym __lisp65_runtime_core_overlay_lma)"; \
		end="$$(sym __lisp65_runtime_core_overlay_end)"; \
		entry="$$(sym __lisp65_runtime_core_overlay_entry)"; \
		resident_end="$$(sym __lisp65_runtime_core_resident_file_end)"; \
		test -n "$$base" && test -n "$$lma" && test -n "$$end" && test -n "$$entry" && test -n "$$resident_end"; \
		test "$$((base))" -eq "$$(( $(RUNTIME_CORE_OVERLAY_VMA) ))"; \
		test "$$((lma))" -eq "$$((base))"; \
		python3 tools/host-lisp/overlay_package.py pack \
			--overlay '$(RUNTIME_CORE_OVERLAY_RAW)' --out-dir '$(RUNTIME_CORE_OVERLAY_PACKAGE_DIR)' \
			--profile '$(RUNTIME_CORE_PROFILE_ID)' --base "$$base" --end "$$end" \
			--entry "$$entry" --entry-symbol vm_load_embedded_stdlib \
			--load-base "$$base" --load-mode fixed-vma-raw --staging-mode separate-image \
			--lifetime boot-only --reclaim-point before-deep-stack \
			--resident '$(RUNTIME_CORE_OVERLAY_RESIDENT_PRG)' \
			--resident-load-base 0x2001 --resident-file-end "$$resident_end" \
			--abi-id '$(RUNTIME_CORE_OVERLAY_ABI_ID)' --abi-contract '$(RUNTIME_CORE_OVERLAY_ABI_CONTRACT)'

$(RUNTIME_CORE_PRG): $(RUNTIME_CORE_SRCS) $(RUNTIME_CORE_SUITE) lib/runtime-core.lisp $(RUNTIME_EXPORT_PRELOAD_HEADER) FORCE | build
	$(MAKE) runtime-core-bytecode-artifacts
	mkdir -p $(RUNTIME_CORE_DIR)
	$(CC_M65) $(RUNTIME_CORE_CFLAGS) -DLISP65_VM -DLISP65_EMBED_STDLIB -DLISP65_EMBED_DMA \
		-DHEAP_CELLS=$(RUNTIME_CORE_HEAP_CELLS) $(RUNTIME_CORE_DEFINES) \
		$(RUNTIME_CORE_PRELOAD_DEFINE) \
		'-DLISP65_RUNTIME_ENTRY="$(RUNTIME_CORE_ENTRY)"' \
		-Isrc -I$(RUNTIME_CORE_BYTECODE_DIR) $(RUNTIME_CORE_SRCS) $(RUNTIME_CORE_STDLIB_C) \
		$(RUNTIME_CORE_LDFLAGS) -o $@
	@printf 'built %s (%s bytes, entry=%s)\n' "$@" "$$(stat -c%s $@)" "$(RUNTIME_CORE_ENTRY)"

runtime-core-footprint-report: $(RUNTIME_CORE_PRG)
	python3 tools/host-lisp/mvp_vm_stdlib_footprint.py \
		--out "$(RUNTIME_CORE_FOOTPRINT_REPORT)" \
		--prg "$(RUNTIME_CORE_PRG)" \
		--manifest "$(RUNTIME_CORE_STDLIB_MANIFEST)" \
		--header "$(RUNTIME_CORE_STDLIB_HEADER)" \
		--elf "$(RUNTIME_CORE_PRG).elf" \
		--nm "$(M65VMSTDLIB_NM)" \
		--size "$(M65VMSTDLIB_SIZE)" \
		--min-stack-gap "$(RUNTIME_CORE_MIN_STACK_GAP)" \
		--min-boot-stack-gap "$(RUNTIME_CORE_MIN_BOOT_STACK_GAP)" \
		--min-bank0-reserve "$(RUNTIME_CORE_MIN_BANK0_RESERVE)" \
		--bank0-reserve-target "$(RUNTIME_CORE_BANK0_RESERVE_TARGET)" \
		--max-prg-file-end "$(RUNTIME_CORE_MAX_PRG_FILE_END)" \
		--m65-cflags "$(RUNTIME_CORE_CFLAGS)" \
		--heap-cells "$(RUNTIME_CORE_HEAP_CELLS)" \
		--eval-c products/runtime-core/main.c \
		--native-c src/vm.c \
		--native-c src/symbol.c \
		--min-symbol-headroom "$(RUNTIME_CORE_MIN_SYMBOL_HEADROOM)" \
		--boot-symbol-correction 0 \
		--extra-cflags "$(RUNTIME_CORE_DEFINES) $(RUNTIME_CORE_PRELOAD_DEFINE)"

runtime-core-audit: $(RUNTIME_CORE_PRG)
	python3 tools/host-lisp/runtime_core_audit.py \
		--elf "$(RUNTIME_CORE_PRG).elf" \
		--manifest "$(RUNTIME_CORE_STDLIB_MANIFEST)" \
		--entry "$(RUNTIME_CORE_ENTRY)" \
		--nm "$(M65VMSTDLIB_NM)"

runtime-core-audit-selftest:
	python3 tools/host-lisp/runtime_core_audit.py --selftest

$(RUNTIME_CORE_SMOKE_HOST): scripts/runtime-core-smoke-main.c src/interrupt.c src/mem.c src/symbol.c src/vm.c src/vm_embed.c src/vm_registry.h | runtime-core-bytecode-artifacts build
	$(HOSTCC) -std=c99 -Wall -Wextra -Wno-unused-function \
		-DLISP65_VM -DLISP65_EMBED_STDLIB -DLISP65_BYTECODE_STDLIB_EMIT_METADATA \
		-DLISP65_RUNTIME_CORE -DLISP65_VM_NATIVE_APPLY -DLISP65_VM_GLOBAL_PRIMS \
		-DVM_CODEBUF=56 -DHEAP_CELLS=48 -DGC_ROOTS=128 -DLISP65_MARK_BITMAP \
		-DLISP65_EXT_HEAP -DEXT_CELLS=1024 -DLISP65_STRING_ARENA -DSTR_ARENA_SIZE=0x2480 \
		-DNAMEPOOL=9536 -DMAX_SYM=720 -DVM_DIR_MAX=552 \
		-Isrc -I$(RUNTIME_CORE_BYTECODE_DIR) scripts/runtime-core-smoke-main.c \
		src/interrupt.c src/mem.c src/symbol.c src/vm.c src/vm_embed.c $(RUNTIME_CORE_STDLIB_C) -o $@

runtime-core-smoke: $(RUNTIME_CORE_SMOKE_HOST)
	$(RUNTIME_CORE_SMOKE_HOST)

runtime-core-prototype-check: runtime-core-footprint-report runtime-core-audit runtime-core-smoke

print-runtime-core-resolved-profile:
	@printf '%s\n' \
		'format=lisp65-resolved-profile-v1' \
		'profile=$(RUNTIME_CORE_PROFILE_ID)' \
		'entry=$(RUNTIME_CORE_ENTRY)' \
		'suite=$(RUNTIME_CORE_SUITE)' \
		'sources=$(RUNTIME_CORE_SRCS)' \
		'cflags=$(RUNTIME_CORE_CFLAGS)' \
		'extra_cflags=$(RUNTIME_CORE_DEFINES)' \
		'ldflags=$(RUNTIME_CORE_LDFLAGS)'

print-runtime-core-overlay-resolved-profile: print-runtime-core-resolved-profile
	@printf '%s\n' \
		'overlay_role=diagnostic-fixed-vma-split' \
		'overlay_abi=$(RUNTIME_CORE_OVERLAY_ABI_ID)' \
		'overlay_section=$(RUNTIME_CORE_OVERLAY_SECTION)' \
		'overlay_vma=$(RUNTIME_CORE_OVERLAY_VMA)' \
		'overlay_linker=$(RUNTIME_CORE_OVERLAY_LD)' \
		'overlay_entry=vm_load_embedded_stdlib' \
		'overlay_lifetime=boot-only' \
		'overlay_reclaim_point=before-deep-stack'

print-runtime-core-inline-overlay-resolved-profile: print-runtime-core-resolved-profile
	@printf '%s\n' \
		'inline_overlay_role=runtime-reset-safe-prototype' \
		'inline_overlay_linker=$(RUNTIME_CORE_INLINE_OVERLAY_LD)' \
		'inline_overlay_entry=vm_load_embedded_stdlib' \
		'inline_overlay_staging=same-flat-prg' \
		'inline_overlay_lifetime=boot-only' \
		'inline_overlay_min_boot_stack_gap=$(RUNTIME_CORE_INLINE_OVERLAY_MIN_BOOT_STACK_GAP)' \
		'inline_overlay_runtime_stack_budget=$(RUNTIME_CORE_INLINE_OVERLAY_RUNTIME_STACK_BUDGET)' \
		'inline_overlay_min_post_boot_reserve=$(RUNTIME_CORE_INLINE_OVERLAY_MIN_POST_BOOT_RESERVE)' \
		'inline_overlay_max_file_end=$(RUNTIME_CORE_INLINE_OVERLAY_MAX_FILE_END)'
