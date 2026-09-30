# Dated System/Runtime hosts: identical existing host recipes, new outputs.
# The frozen v1 source export is consumed read-only; its old binary and receipt
# are never rebuilt or overwritten by the r7 differential.
DISK_R7_V1_HOST := build/equivalence-disk-r7-20260930/dialect-v1-equivalence-check
DISK_R7_V2_HOST := build/equivalence-disk-r7-20260930/dialect-v2-equivalence-check
DISK_R7_V1_BUILD := build/equivalence-disk-r7-20260930/dialect-v1-build-receipt.json
DISK_R7_V2_BUILD := build/equivalence-disk-r7-20260930/dialect-v2-build-receipt.json

$(DISK_R7_V1_HOST): $(DIALECT_V1_SOURCE_MANIFEST) scripts/equivalence-main.c Makefile | build
	mkdir -p $(dir $@)
	$(HOSTCC) -std=c99 -Wall -Wno-unused-function \
		-DLISP65_COMPILE_REPL -DLISP65_VM -DLISP65_VM_GLOBAL_PRIMS \
		-DLISP65_EVAL_PRIMS -DLISP65_EVAL_CONTROL_SF -DLISP65_VM_APPLY_OPFN \
		-DLISP65_MACROEXPAND_PRIM -DLISP65_LCC_INSTALL \
		-DLISP65_DIALECT_FAMILY_HARNESS -DLISP65_FROZEN_V1_HARNESS -DLISP65_NUMERIC_ERRORS \
		-DHEAP_CELLS=8192 -DGC_ROOTS=1024 -DMAX_SYM=512 -DNAMEPOOL=8192 \
		-DVM_DIR_MAX=128 -DIO_BUF_MAX=16 -I$(DIALECT_V1_SOURCE_ROOT)/src \
		scripts/equivalence-main.c \
		$(addprefix $(DIALECT_V1_SOURCE_ROOT)/src/,$(DIALECT_EQUIVALENCE_SOURCE_NAMES)) -o $@

$(DISK_R7_V1_BUILD): $(DISK_R7_V1_HOST) Makefile tools/host-lisp/dialect_v2_prelude_control.py
	python3 tools/host-lisp/dialect_v2_prelude_control.py record-build \
		--profile dialect-v1 --binary $(DISK_R7_V1_HOST) \
		--compiler "$(HOSTCC)" --source-root $(DIALECT_V1_SOURCE_ROOT) \
		--source-commit f6527d25e2035eae5a98dae7431d641515e2fd2e --output $@

$(DISK_R7_V2_HOST): scripts/equivalence-main.c src/eval.c src/compile.c src/compile_repl.c src/lcc_install_overlay.c src/vm.c src/mem.c src/symbol.c src/reader.c src/printer.c src/io.c src/interrupt.c src/screen.c $(DIALECT_EQUIVALENCE_HEADERS) | build
	mkdir -p $(dir $@)
	$(HOSTCC) -std=c99 -Wall -Wno-unused-function \
		-DLISP65_COMPILE_REPL -DLISP65_VM -DLISP65_VM_GLOBAL_PRIMS \
		-DLISP65_EVAL_PRIMS -DLISP65_EVAL_CONTROL_SF -DLISP65_VM_APPLY_OPFN \
		-DLISP65_MACROEXPAND_PRIM -DLISP65_LCC_INSTALL -DLISP65_DIALECT_V2 \
		-DLISP65_STRING_ARENA -DLISP65_V2_NATIVE_CAPABILITIES -DLISP65_V2_NATIVE_STRING_CODECS \
		-DLISP65_DIALECT_FAMILY_HARNESS -DLISP65_NUMERIC_ERRORS \
		-DHEAP_CELLS=8192 -DGC_ROOTS=1024 -DMAX_SYM=512 -DNAMEPOOL=8192 \
		-DVM_DIR_MAX=128 -DIO_BUF_MAX=16 -Isrc \
		scripts/equivalence-main.c src/eval.c src/compile.c src/compile_repl.c \
		src/lcc_install_overlay.c src/vm.c src/mem.c src/symbol.c src/reader.c \
		src/printer.c src/io.c src/interrupt.c src/screen.c -o $@

$(DISK_R7_V2_BUILD): $(DISK_R7_V2_HOST) Makefile lib/dialect-v2/prelude-control.lisp tools/host-lisp/dialect_v2_prelude_control.py
	python3 tools/host-lisp/dialect_v2_prelude_control.py record-build \
		--profile dialect-v2 --binary $(DISK_R7_V2_HOST) \
		--compiler "$(HOSTCC)" --source-root . --output $@
