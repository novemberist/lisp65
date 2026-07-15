# Focused Runtime-Core v2 CALLPRIM gate. Invoke with:
#   make -f Makefile -f mk/v2-callprim-runtime.mk v2-callprim-runtime-check

V2_CALLPRIM_RUNTIME_HOST := build/v2-runtime-callprim-host
V2_CALLPRIM_RUNTIME_CUT_HOST := build/v2-runtime-callprim-cut-host
V2_CALLPRIM_RUNTIME_MOS_DIR := build/v2-runtime-callprim-mos
V2_CALLPRIM_RUNTIME_CUT_MOS := $(V2_CALLPRIM_RUNTIME_MOS_DIR)/v2-runtime-callprim-cut.prg
V2_RUNTIME_CORE_ARTIFACT_DIR := build/bytecode/dialect-v2/runtime-core
V2_RUNTIME_CORE_ARTIFACT_PREFIX := $(V2_RUNTIME_CORE_ARTIFACT_DIR)/stdlib-p0
V2_RUNTIME_CORE_SUITE := tests/bytecode/runtime/p0-runtime-export-app-v2.json
V2_RUNTIME_CORE_SERVICE_CONTRACT := config/runtime-core-v2-service-registry.json
V2_RUNTIME_CORE_SERVICE_REPORT := $(V2_RUNTIME_CORE_ARTIFACT_DIR)/service-inventory.json
V2_CALLPRIM_RUNTIME_DEFINES := \
	-DLISP65_VM -DLISP65_RUNTIME_CORE -DLISP65_VM_NATIVE_APPLY \
	-DLISP65_DIALECT_V2 -DLISP65_V2_NATIVE_CAPABILITIES \
	-DLISP65_STRING_ARENA -DLISP65_V2_NATIVE_STRING_CODECS \
	-DVM_CODEBUF=32 \
	-DHEAP_CELLS=96 -DGC_ROOTS=32 -DSTR_ARENA_SIZE=64 \
	-DMAX_SYM=64 -DNAMEPOOL=512 -DVM_DIR_MAX=16
V2_CALLPRIM_RUNTIME_MOS_DEFINES := $(V2_CALLPRIM_RUNTIME_DEFINES) \
	-DLISP65_EXT_HEAP -DEXT_CELLS=1024 -DDISK_EXT_BASE=0x6c00
V2_CALLPRIM_RUNTIME_CUT_DEFINES := $(V2_CALLPRIM_RUNTIME_DEFINES) \
	-DLISP65_TREEWALK_STRIP -DLISP65_V2_SERVICE_REGISTRY_CLOSED \
	-DLISP65_V2_CARRIER_CUT
V2_CALLPRIM_RUNTIME_CUT_MOS_DEFINES := $(V2_CALLPRIM_RUNTIME_CUT_DEFINES) \
	-DLISP65_EXT_HEAP -DEXT_CELLS=1024 -DDISK_EXT_BASE=0x6c00
V2_CALLPRIM_RUNTIME_SOURCES := scripts/v2-runtime-callprim-main.c \
	src/interrupt.c src/mem.c src/symbol.c src/vm.c
V2_CALLPRIM_RUNTIME_MOS_OBJS := $(patsubst %.c,$(V2_CALLPRIM_RUNTIME_MOS_DIR)/%.o,$(V2_CALLPRIM_RUNTIME_SOURCES))

.PHONY: v2-callprim-runtime-host-check v2-callprim-runtime-cut-host-check \
	v2-callprim-runtime-mos-compile v2-callprim-runtime-cut-mos-link \
	v2-runtime-core-service-inventory-selftest v2-runtime-core-artifacts \
	v2-runtime-core-service-inventory-check v2-callprim-runtime-check

$(V2_CALLPRIM_RUNTIME_HOST): $(V2_CALLPRIM_RUNTIME_SOURCES) src/mem.h src/symbol.h src/vm.h | build
	$(HOSTCC) -std=c99 -Wall -Wextra -Werror -Wno-unused-function \
		-fsanitize=address,undefined -fno-omit-frame-pointer \
		$(V2_CALLPRIM_RUNTIME_DEFINES) -Isrc $(V2_CALLPRIM_RUNTIME_SOURCES) -o $@

v2-callprim-runtime-host-check: $(V2_CALLPRIM_RUNTIME_HOST)
	ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 $(V2_CALLPRIM_RUNTIME_HOST)

$(V2_CALLPRIM_RUNTIME_CUT_HOST): $(V2_CALLPRIM_RUNTIME_SOURCES) src/mem.h src/symbol.h src/vm.h | build
	$(HOSTCC) -std=c99 -Wall -Wextra -Werror -Wno-unused-function \
		-fsanitize=address,undefined -fno-omit-frame-pointer \
		$(V2_CALLPRIM_RUNTIME_CUT_DEFINES) -Isrc $(V2_CALLPRIM_RUNTIME_SOURCES) -o $@

v2-callprim-runtime-cut-host-check: $(V2_CALLPRIM_RUNTIME_CUT_HOST)
	@set -eu; \
		forbidden="$$(nm --defined-only '$<' | awk \
			'$$3 == "vm_treewalk_call" || $$3 == "vm_treewalk_apply" || \
			 $$3 == "eval_v2_workbench_service" || \
			 $$3 == "vm_workbench_compile_error" { print $$3 }')"; \
		test -z "$$forbidden" || { printf '%s\n' "unexpected cut symbols: $$forbidden" >&2; exit 1; }; \
		nm --defined-only '$<' | awk '$$3 == "vm_native_apply" { found=1 } END { exit !found }'
	ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 $(V2_CALLPRIM_RUNTIME_CUT_HOST)

$(V2_CALLPRIM_RUNTIME_MOS_DIR)/%.o: %.c
	mkdir -p $(dir $@)
	$(CC_M65) -std=c99 -Oz -Wall -Wextra -Werror -Wno-unused-function \
		$(V2_CALLPRIM_RUNTIME_MOS_DEFINES) -Isrc -c $< -o $@

v2-callprim-runtime-mos-compile: $(V2_CALLPRIM_RUNTIME_MOS_OBJS)
	@printf 'v2-runtime-callprim: llvm-mos compile PASS objects=%s\n' "$(words $(V2_CALLPRIM_RUNTIME_MOS_OBJS))"

$(V2_CALLPRIM_RUNTIME_CUT_MOS): $(V2_CALLPRIM_RUNTIME_SOURCES) src/mem.h src/symbol.h src/vm.h
	mkdir -p $(dir $@)
	$(CC_M65) -std=c99 -Oz -Wall -Wextra -Werror -Wno-unused-function \
		$(V2_CALLPRIM_RUNTIME_CUT_MOS_DEFINES) -Isrc \
		$(V2_CALLPRIM_RUNTIME_SOURCES) -o $@

v2-callprim-runtime-cut-mos-link: $(V2_CALLPRIM_RUNTIME_CUT_MOS)
	@set -eu; \
		forbidden="$$($(M65VMSTDLIB_NM) --defined-only '$<.elf' | awk \
			'$$3 == "vm_treewalk_call" || $$3 == "vm_treewalk_apply" || \
			 $$3 == "eval_v2_workbench_service" || \
			 $$3 == "vm_workbench_compile_error" { print $$3 }')"; \
		test -z "$$forbidden" || { printf '%s\n' "unexpected MOS cut symbols: $$forbidden" >&2; exit 1; }; \
		$(M65VMSTDLIB_NM) --defined-only '$<.elf' | \
			awk '$$3 == "vm_native_apply" { found=1 } END { exit !found }'; \
		printf 'v2-runtime-callprim: llvm-mos link PASS prg_bytes=%s\n' "$$(stat -c%s '$<')"

v2-runtime-core-service-inventory-selftest:
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/runtime_core_service_inventory.py --selftest

v2-runtime-core-artifacts: $(V2_RUNTIME_CORE_SUITE)
	@mkdir -p "$(V2_RUNTIME_CORE_ARTIFACT_DIR)"
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/bytecode_p0_stdlib.py \
		--check --emit-artifacts "$(V2_RUNTIME_CORE_ARTIFACT_PREFIX)" \
		"$(V2_RUNTIME_CORE_SUITE)"

v2-runtime-core-service-inventory-check: v2-runtime-core-service-inventory-selftest v2-runtime-core-artifacts
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/runtime_core_service_inventory.py \
		--contract "$(V2_RUNTIME_CORE_SERVICE_CONTRACT)" \
		--json-out "$(V2_RUNTIME_CORE_SERVICE_REPORT)"

v2-callprim-runtime-check: v2-callprim-runtime-host-check \
	v2-callprim-runtime-cut-host-check v2-callprim-runtime-mos-compile \
	v2-callprim-runtime-cut-mos-link v2-runtime-core-service-inventory-check
