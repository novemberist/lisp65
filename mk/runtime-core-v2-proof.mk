# Sealed host/G2 proof for the internal dialect-v2 Runtime Core.

.PHONY: v2-runtime-core-proof-selftest v2-runtime-core-proof-contract-check \
	v2-runtime-core-proof-profile v2-runtime-core-proof-host-smoke \
	v2-runtime-core-proof-link v2-runtime-core-proof-reproducibility \
	v2-runtime-core-proof-footprint v2-runtime-core-proof-audit \
	v2-runtime-core-proof-candidate v2-runtime-core-proof-candidate-selftest \
	v2-runtime-core-proof-verify \
	v2-runtime-core-proof-check v2-capability-carrier-runtime-proof-check

V2_RUNTIME_CORE_PROOF_SRCS := $(RUNTIME_CORE_SRCS)
V2_RUNTIME_CORE_PROOF_PRODUCT_INPUTS := \
	$(V2_RUNTIME_CORE_PROOF_SRCS) \
	$(wildcard src/*.h) \
	config/runtime-core.mk \
	config/runtime-core-v2-proof.mk \
	mk/runtime-core.mk \
	mk/runtime-core-v2-proof.mk \
	$(RUNTIME_CORE_INLINE_OVERLAY_LD) \
	tests/bytecode/runtime/p0-runtime-export-app-v2.json \
	tools/host-lisp/bytecode_p0_stdlib.py \
	tools/host-lisp/runtime_export_preload.py
V2_RUNTIME_CORE_PROOF_PRODUCT_SOURCE_ID := $(shell sha256sum $(sort $(V2_RUNTIME_CORE_PROOF_PRODUCT_INPUTS)) | sha256sum | cut -c1-40)
V2_RUNTIME_CORE_PROOF_LINK_INPUTS := \
	$(V2_RUNTIME_CORE_PROOF_SRCS) \
	$(V2_RUNTIME_CORE_PROOF_ARTIFACT_C) \
	$(V2_RUNTIME_CORE_PROOF_ARTIFACT_HEADER) \
	$(V2_RUNTIME_CORE_PROOF_PRELOAD_HEADER) \
	$(RUNTIME_CORE_INLINE_OVERLAY_LD)

$(V2_RUNTIME_CORE_PROOF_ARTIFACT_C) \
$(V2_RUNTIME_CORE_PROOF_ARTIFACT_HEADER) \
$(V2_RUNTIME_CORE_PROOF_ARTIFACT_EXT) \
$(V2_RUNTIME_CORE_PROOF_ARTIFACT_MANIFEST): v2-runtime-core-artifacts
	@test -f '$@'

$(V2_RUNTIME_CORE_PROOF_INVENTORY): v2-runtime-core-service-inventory-check
	@test -f '$@'

v2-runtime-core-proof-selftest:
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v2_runtime_core_proof.py \
		--contract '$(V2_RUNTIME_CORE_PROOF_CONTRACT)' selftest

v2-runtime-core-proof-contract-check: v2-runtime-core-proof-selftest
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v2_runtime_core_proof.py \
		--contract '$(V2_RUNTIME_CORE_PROOF_CONTRACT)' check

$(V2_RUNTIME_CORE_PROOF_PROFILE): $(V2_RUNTIME_CORE_PROOF_CONTRACT) \
	$(V2_RUNTIME_CORE_PROOF_PRODUCT_INPUTS) \
	tools/host-lisp/v2_runtime_core_proof.py scripts/runtime-core-smoke-main.c | build
	@mkdir -p '$(V2_RUNTIME_CORE_PROOF_DIR)'
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v2_runtime_core_proof.py \
		--contract '$(V2_RUNTIME_CORE_PROOF_CONTRACT)' profile \
		--product-source-id '$(V2_RUNTIME_CORE_PROOF_PRODUCT_SOURCE_ID)' --out '$@'

v2-runtime-core-proof-profile: $(V2_RUNTIME_CORE_PROOF_PROFILE)

$(V2_RUNTIME_CORE_PROOF_PRELOAD) $(V2_RUNTIME_CORE_PROOF_PRELOAD_HEADER) &: \
	$(V2_RUNTIME_CORE_PROOF_PROFILE) $(V2_RUNTIME_CORE_PROOF_ARTIFACT_EXT) \
	tools/host-lisp/runtime_export_preload.py
	@set -eu; \
		build_id="$$(sha256sum '$(V2_RUNTIME_CORE_PROOF_PROFILE)' | cut -c1-8)"; \
		python3 tools/host-lisp/runtime_export_preload.py build \
			--payload '$(V2_RUNTIME_CORE_PROOF_ARTIFACT_EXT)' \
			--build-id "0x$$build_id" \
			--out '$(V2_RUNTIME_CORE_PROOF_PRELOAD)' \
			--header '$(V2_RUNTIME_CORE_PROOF_PRELOAD_HEADER)'

define V2_RUNTIME_CORE_PROOF_LINK_RULE
$(1): $(V2_RUNTIME_CORE_PROOF_LINK_INPUTS)
	@mkdir -p '$$(dir $$@)'
	$$(CC_M65) $$(V2_RUNTIME_CORE_PROOF_CFLAGS) \
		-DLISP65_VM -DLISP65_EMBED_STDLIB -DLISP65_EMBED_DMA \
		-DHEAP_CELLS=$$(RUNTIME_CORE_HEAP_CELLS) $$(V2_RUNTIME_CORE_PROOF_DEFINES) \
		-include $$(V2_RUNTIME_CORE_PROOF_PRELOAD_HEADER) \
		'-DLISP65_RUNTIME_ENTRY="$$(RUNTIME_CORE_ENTRY)"' \
		-DLISP65_STDLIB_BOOT_OVERLAY_CODE \
		-Isrc -I$$(dir $$(V2_RUNTIME_CORE_PROOF_ARTIFACT_PREFIX)) \
		$$(V2_RUNTIME_CORE_PROOF_SRCS) $$(V2_RUNTIME_CORE_PROOF_ARTIFACT_C) \
		$$(RUNTIME_CORE_LDFLAGS) -Wl,-T,$$(RUNTIME_CORE_INLINE_OVERLAY_LD) \
		-Wl,--defsym=__lisp65_runtime_core_inline_required_boot_stack_param=$$(RUNTIME_CORE_INLINE_OVERLAY_MIN_BOOT_STACK_GAP) \
		-Wl,--defsym=__lisp65_runtime_core_inline_required_runtime_stack_param=$$(RUNTIME_CORE_INLINE_OVERLAY_RUNTIME_STACK_BUDGET) \
		-Wl,--defsym=__lisp65_runtime_core_inline_required_post_boot_reserve_param=$$(RUNTIME_CORE_INLINE_OVERLAY_MIN_POST_BOOT_RESERVE) \
		-Wl,--defsym=__lisp65_runtime_core_inline_max_file_end_param=$$(RUNTIME_CORE_INLINE_OVERLAY_MAX_FILE_END) \
		-o $$@
endef

$(eval $(call V2_RUNTIME_CORE_PROOF_LINK_RULE,$(V2_RUNTIME_CORE_PROOF_LINK_A)))
$(eval $(call V2_RUNTIME_CORE_PROOF_LINK_RULE,$(V2_RUNTIME_CORE_PROOF_LINK_B)))

v2-runtime-core-proof-link: v2-runtime-core-service-inventory-check \
	$(V2_RUNTIME_CORE_PROOF_LINK_A) $(V2_RUNTIME_CORE_PROOF_LINK_B)

$(V2_RUNTIME_CORE_PROOF_HOST): scripts/runtime-core-smoke-main.c src/interrupt.c \
	src/mem.c src/symbol.c src/vm.c src/vm_embed.c \
	$(V2_RUNTIME_CORE_PROOF_ARTIFACT_C) $(V2_RUNTIME_CORE_PROOF_ARTIFACT_HEADER)
	@mkdir -p '$(V2_RUNTIME_CORE_PROOF_DIR)'
	$(HOSTCC) -std=c99 -Wall -Wextra -Werror -Wno-unused-function \
		-fsanitize=address,undefined -fno-omit-frame-pointer \
		-DLISP65_VM -DLISP65_EMBED_STDLIB -DLISP65_BYTECODE_STDLIB_EMIT_METADATA \
		-DHEAP_CELLS=$(RUNTIME_CORE_HEAP_CELLS) $(V2_RUNTIME_CORE_PROOF_HOST_DEFINES) \
		-Isrc -I$(dir $(V2_RUNTIME_CORE_PROOF_ARTIFACT_PREFIX)) \
		scripts/runtime-core-smoke-main.c src/interrupt.c src/mem.c src/symbol.c \
		src/vm.c src/vm_embed.c $(V2_RUNTIME_CORE_PROOF_ARTIFACT_C) -o '$@'

$(V2_RUNTIME_CORE_PROOF_HOST_REPORT): $(V2_RUNTIME_CORE_PROOF_HOST)
	@set -eu; \
		tmp='$@.tmp'; \
		ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 \
		UBSAN_OPTIONS=halt_on_error=1 '$<' > "$$tmp"; \
		grep -Fx 'runtime-core-smoke: PASS result=42 carrier=cut errors=typeerror' "$$tmp"; \
		mv "$$tmp" '$@'

v2-runtime-core-proof-host-smoke: $(V2_RUNTIME_CORE_PROOF_HOST_REPORT)

$(V2_RUNTIME_CORE_PROOF_REPRO): $(V2_RUNTIME_CORE_PROOF_LINK_A) \
	$(V2_RUNTIME_CORE_PROOF_LINK_B) tools/host-lisp/v2_runtime_core_proof.py
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v2_runtime_core_proof.py \
		--contract '$(V2_RUNTIME_CORE_PROOF_CONTRACT)' repro \
		--prg-a '$(V2_RUNTIME_CORE_PROOF_LINK_A)' \
		--elf-a '$(V2_RUNTIME_CORE_PROOF_LINK_A).elf' \
		--prg-b '$(V2_RUNTIME_CORE_PROOF_LINK_B)' \
		--elf-b '$(V2_RUNTIME_CORE_PROOF_LINK_B).elf' --out '$@'

v2-runtime-core-proof-reproducibility: $(V2_RUNTIME_CORE_PROOF_REPRO)

$(V2_RUNTIME_CORE_PROOF_FOOTPRINT): $(V2_RUNTIME_CORE_PROOF_LINK_A)
	python3 tools/host-lisp/mvp_vm_stdlib_footprint.py \
		--out '$@' --prg '$(V2_RUNTIME_CORE_PROOF_LINK_A)' \
		--manifest '$(V2_RUNTIME_CORE_PROOF_ARTIFACT_MANIFEST)' \
		--header '$(V2_RUNTIME_CORE_PROOF_ARTIFACT_HEADER)' \
		--elf '$(V2_RUNTIME_CORE_PROOF_LINK_A).elf' \
		--nm '$(M65VMSTDLIB_NM)' --size '$(M65VMSTDLIB_SIZE)' \
		--min-stack-gap '$(RUNTIME_CORE_MIN_STACK_GAP)' \
		--min-boot-stack-gap '$(RUNTIME_CORE_INLINE_OVERLAY_MIN_BOOT_STACK_GAP)' \
		--min-bank0-reserve '$(RUNTIME_CORE_MIN_BANK0_RESERVE)' \
		--bank0-reserve-target '$(RUNTIME_CORE_BANK0_RESERVE_TARGET)' \
		--max-prg-file-end '$(RUNTIME_CORE_INLINE_OVERLAY_MAX_FILE_END)' \
		--m65-cflags '$(V2_RUNTIME_CORE_PROOF_CFLAGS)' \
		--heap-cells '$(RUNTIME_CORE_HEAP_CELLS)' \
		--eval-c products/runtime-core/main.c --native-c src/vm.c --native-c src/symbol.c \
		--min-symbol-headroom '$(RUNTIME_CORE_MIN_SYMBOL_HEADROOM)' \
		--boot-symbol-correction 0 \
		--extra-cflags '$(V2_RUNTIME_CORE_PROOF_DEFINES) -include $(V2_RUNTIME_CORE_PROOF_PRELOAD_HEADER) -DLISP65_STDLIB_BOOT_OVERLAY_CODE'

v2-runtime-core-proof-footprint: $(V2_RUNTIME_CORE_PROOF_FOOTPRINT)

$(V2_RUNTIME_CORE_PROOF_AUDIT): $(V2_RUNTIME_CORE_PROOF_LINK_A)
	python3 tools/host-lisp/runtime_core_inline_overlay_audit.py \
		--elf '$(V2_RUNTIME_CORE_PROOF_LINK_A).elf' --prg '$(V2_RUNTIME_CORE_PROOF_LINK_A)' \
		--nm '$(M65VMSTDLIB_NM)' --objdump '$(LLVM)/llvm-objdump' \
		--entry vm_load_embedded_stdlib --boot-caller main --runtime-entry vm_run_dir \
		--min-boot-stack-gap '$(RUNTIME_CORE_INLINE_OVERLAY_MIN_BOOT_STACK_GAP)' \
		--runtime-stack-budget '$(RUNTIME_CORE_INLINE_OVERLAY_RUNTIME_STACK_BUDGET)' \
		--min-post-boot-reserve '$(RUNTIME_CORE_INLINE_OVERLAY_MIN_POST_BOOT_RESERVE)' \
		--max-file-end '$(RUNTIME_CORE_INLINE_OVERLAY_MAX_FILE_END)' --out '$@'

$(V2_RUNTIME_CORE_PROOF_ELF_AUDIT): $(V2_RUNTIME_CORE_PROOF_LINK_A) \
	tools/host-lisp/v2_runtime_core_proof.py
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v2_runtime_core_proof.py \
		--contract '$(V2_RUNTIME_CORE_PROOF_CONTRACT)' elf-audit \
		--elf '$(V2_RUNTIME_CORE_PROOF_LINK_A).elf' --nm '$(M65VMSTDLIB_NM)' --out '$@'

v2-runtime-core-proof-audit: $(V2_RUNTIME_CORE_PROOF_AUDIT) $(V2_RUNTIME_CORE_PROOF_ELF_AUDIT)

$(V2_RUNTIME_CORE_PROOF_TOOLCHAIN): $(CC_M65) $(M65VMSTDLIB_NM)
	@set -eu; \
		mkdir -p '$(V2_RUNTIME_CORE_PROOF_DIR)'; \
		tmp='$@.tmp'; \
		printf '%s\n' \
			'format=lisp65-v2-runtime-core-toolchain-v1' \
			'cc=$(CC_M65)' \
			"cc_sha256=$$(sha256sum '$(CC_M65)' | cut -d' ' -f1)" \
			"cc_version=$$('$(CC_M65)' --version | sed -n '1p')" \
			'nm=$(M65VMSTDLIB_NM)' \
			"nm_sha256=$$(sha256sum '$(M65VMSTDLIB_NM)' | cut -d' ' -f1)" \
			"python_version=$$(python3 --version 2>&1)" > "$$tmp"; \
		mv "$$tmp" '$@'

$(V2_RUNTIME_CORE_PROOF_CANDIDATE)/manifest.json: \
	v2-runtime-core-proof-contract-check v2-runtime-core-proof-host-smoke \
	v2-runtime-core-proof-reproducibility v2-runtime-core-proof-footprint \
	v2-runtime-core-proof-audit $(V2_RUNTIME_CORE_PROOF_PRELOAD) \
	$(V2_RUNTIME_CORE_PROOF_TOOLCHAIN) $(V2_RUNTIME_CORE_PROOF_INVENTORY)
	rm -rf '$(V2_RUNTIME_CORE_PROOF_CANDIDATE)'
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v2_runtime_core_proof.py \
		--contract '$(V2_RUNTIME_CORE_PROOF_CONTRACT)' pack \
		--build-dir '$(V2_RUNTIME_CORE_PROOF_DIR)' \
		--artifact-prefix '$(V2_RUNTIME_CORE_PROOF_ARTIFACT_PREFIX)' \
		--inventory '$(V2_RUNTIME_CORE_PROOF_INVENTORY)' \
		--nm '$(M65VMSTDLIB_NM)' --out '$(V2_RUNTIME_CORE_PROOF_CANDIDATE)'

v2-runtime-core-proof-candidate: $(V2_RUNTIME_CORE_PROOF_CANDIDATE)/manifest.json

v2-runtime-core-proof-candidate-selftest: v2-runtime-core-proof-candidate
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v2_runtime_core_proof.py \
		--contract '$(V2_RUNTIME_CORE_PROOF_CONTRACT)' candidate-selftest \
		--dir '$(V2_RUNTIME_CORE_PROOF_CANDIDATE)' --nm '$(M65VMSTDLIB_NM)'

v2-runtime-core-proof-verify: v2-runtime-core-proof-candidate-selftest
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v2_runtime_core_proof.py \
		--contract '$(V2_RUNTIME_CORE_PROOF_CONTRACT)' verify \
		--dir '$(V2_RUNTIME_CORE_PROOF_CANDIDATE)' --nm '$(M65VMSTDLIB_NM)'

v2-runtime-core-proof-check: v2-runtime-core-proof-verify
	@printf '%s\n' \
		'v2-runtime-core-proof-check: PASS internal-only shippable=false release=none cp5=unchanged g5=none'

v2-capability-carrier-runtime-proof-check: v2-runtime-core-proof-check
	@printf '%s\n' \
		'v2-capability-carrier-runtime-proof-check: PASS evidence-only cp5=4/5 release=none'
