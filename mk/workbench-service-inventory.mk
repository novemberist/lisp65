# Stage-2 preparation only: host/link-time inventory, no runtime registry.
WORKBENCH_SERVICE_INVENTORY_CONTRACT := config/workbench-native-service-registry.json
WORKBENCH_SERVICE_INVENTORY_REPORT := build/bytecode/workbench-service-call-inventory.json
V2_WORKBENCH_CODEMOD_RECEIPT := build/bytecode/dialect-v2/codemod-receipt.json
V2_WORKBENCH_DIFFERENTIAL_RECEIPT := tests/bytecode/dialect-v2/evidence/capability-carrier/workbench-artifact-differential-receipt.json
V2_WORKBENCH_SERVICE_REPORT := build/bytecode/dialect-v2/workbench-service-call-inventory.json
V2_WORKBENCH_SUITE_DIR := build/bytecode/dialect-v2/suites
V2_WORKBENCH_ARTIFACT_DIR := build/bytecode/dialect-v2/workbench
V2_WORKBENCH_LIB_DIR := build/bytecode/dialect-v2/libs
V2_WORKBENCH_COMPOSITION_REPORT := build/bytecode/dialect-v2/workbench-library-composition-budget.json
WORKBENCH_SERVICE_INVENTORY_ARTIFACTS := \
	bytecode-p0-workbench-stdlib-artifacts \
	bytecode-p0-ide-lib-artifacts \
	bytecode-p0-ide-extra-lib-artifacts \
	bytecode-p0-m65d-lib-artifacts

.PHONY: workbench-service-call-inventory-selftest workbench-service-call-inventory-current workbench-service-call-inventory-zero-miss v2-workbench-codemod v2-workbench-artifacts v2-workbench-library-composition-check v2-workbench-differential v2-workbench-services-check workbench-service-call-inventory-staging

workbench-service-call-inventory-selftest:
	python3 tools/host-lisp/workbench_service_call_inventory.py --selftest

workbench-service-call-inventory-current: $(WORKBENCH_SERVICE_INVENTORY_ARTIFACTS)
	python3 tools/host-lisp/workbench_service_call_inventory.py \
		--contract "$(WORKBENCH_SERVICE_INVENTORY_CONTRACT)" \
		--mode current --json-out "$(WORKBENCH_SERVICE_INVENTORY_REPORT)"

v2-workbench-codemod:
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v2_workbench_codemod.py --selftest
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v2_workbench_codemod.py

v2-workbench-artifacts: v2-workbench-codemod
	@mkdir -p "$(V2_WORKBENCH_ARTIFACT_DIR)" "$(V2_WORKBENCH_LIB_DIR)"
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/bytecode_p0_stdlib.py --check --emit-artifacts \
		"$(V2_WORKBENCH_ARTIFACT_DIR)/stdlib-p0" \
		"$(V2_WORKBENCH_SUITE_DIR)/p0-stdlib-einsuite-core-workbench-subset.json"
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/bytecode_p0_stdlib.py --check --emit-artifacts \
		"$(V2_WORKBENCH_LIB_DIR)/ide" --artifact-role disk-lib --base-addr 0x000000 \
		"$(V2_WORKBENCH_SUITE_DIR)/p0-ide-core-lib.json"
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/bytecode_p0_stdlib.py --check --emit-artifacts \
		"$(V2_WORKBENCH_LIB_DIR)/idex" --artifact-role disk-lib --base-addr 0x000000 \
		"$(V2_WORKBENCH_SUITE_DIR)/p0-ide-extra-lib.json"
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/bytecode_p0_stdlib.py --check --emit-artifacts \
		"$(V2_WORKBENCH_LIB_DIR)/m65d" --artifact-role disk-lib --base-addr 0x000000 \
		"$(V2_WORKBENCH_SUITE_DIR)/p0-m65d-lib.json"

v2-workbench-library-composition-check: v2-workbench-artifacts
	python3 tools/host-lisp/workbench_disklib_budget.py \
		--resident-manifest "$(V2_WORKBENCH_ARTIFACT_DIR)/stdlib-p0.manifest.json" \
		--disk-lib-manifest "$(V2_WORKBENCH_LIB_DIR)/ide.manifest.json" \
		--disk-lib-manifest "$(V2_WORKBENCH_LIB_DIR)/idex.manifest.json" \
		--disk-lib-manifest "$(V2_WORKBENCH_LIB_DIR)/m65d.manifest.json" \
		--extra-cflags "$(WORKBENCH_DEFINES)" \
		--native-c src/vm.c --native-c src/symbol.c \
		--symbol-correction "$(WORKBENCH_COMPOSITION_SYMBOL_CORRECTION)" \
		--namepool-correction "$(WORKBENCH_COMPOSITION_NAMEPOOL_CORRECTION)" \
		--boot-align8 \
		--min-load-headroom "$(WORKBENCH_MIN_LOAD_HEADROOM)" \
		--min-post-align-headroom "$(WORKBENCH_MIN_POST_ALIGN_HEADROOM)" \
		--min-codebuf-headroom 0 \
		--min-ext-code-peak-headroom "$(WORKBENCH_MIN_EXT_CODE_PEAK_HEADROOM)" \
		--min-ext-code-post-headroom "$(WORKBENCH_MIN_EXT_CODE_POST_HEADROOM)" \
		--min-symbol-headroom "$(WORKBENCH_MIN_SYMBOL_HEADROOM)" \
		--min-namepool-headroom "$(WORKBENCH_MIN_NAMEPOOL_HEADROOM)" \
		--disk-file-max "$(WORKBENCH_DISK_FILE_MAX)" \
		--json-out "$(V2_WORKBENCH_COMPOSITION_REPORT)"

v2-workbench-differential: v2-workbench-artifacts
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v2_workbench_differential.py --selftest
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v2_workbench_differential.py \
		--out "$(V2_WORKBENCH_DIFFERENTIAL_RECEIPT)"

v2-workbench-services-check:
	sh scripts/v2-workbench-services-check.sh

workbench-service-call-inventory-staging: v2-workbench-differential
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/workbench_service_call_inventory.py \
		--contract "$(WORKBENCH_SERVICE_INVENTORY_CONTRACT)" \
		--closure "config/v2-workbench-artifact-closure.json" \
		--mode staging --json-out "$(V2_WORKBENCH_SERVICE_REPORT)"

# This target is intentionally red until every generic CALL/TAILCALL miss has
# a static directory definition, CALLPRIM lowering, or explicit error service.
workbench-service-call-inventory-zero-miss: $(WORKBENCH_SERVICE_INVENTORY_ARTIFACTS)
	python3 tools/host-lisp/workbench_service_call_inventory.py \
		--contract "$(WORKBENCH_SERVICE_INVENTORY_CONTRACT)" \
		--mode zero-miss --json-out "$(WORKBENCH_SERVICE_INVENTORY_REPORT)"
