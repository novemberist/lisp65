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
V11_BUFFER_COMPOSITION_REPORT := build/bytecode/dialect-v2/workbench-buffer-composition-budget.json
V11_REPL_BANNER_VISUAL_REPORT := build/bytecode/dialect-v2/repl-banner-visual-oracle.json
WORKBENCH_SERVICE_INVENTORY_ARTIFACTS := \
	bytecode-p0-workbench-stdlib-artifacts \
	bytecode-p0-ide-lib-artifacts \
	bytecode-p0-ide-extra-lib-artifacts \
	bytecode-p0-m65d-lib-artifacts

.PHONY: workbench-service-call-inventory-selftest workbench-service-call-inventory-current workbench-service-call-inventory-zero-miss v2-workbench-codemod v2-workbench-artifacts v11-surface-delivery-parity-selftest v11-surface-delivery-parity-check v11-repl-banner-visual-selftest v11-repl-banner-visual-check v2-workbench-library-composition-check v11-buffer-library-composition-check v11-m-transactional-fasl-observations v11-m-transactional-fasl-acceptance-selftest v11-m-transactional-fasl-acceptance-collect v11-m-transactional-fasl-acceptance-check v11-g-green-surface-observations v11-g-green-surface-acceptance-selftest v11-g-green-surface-acceptance-collect v11-g-green-surface-acceptance-check v11-restart-repl-scope-correction-selftest v11-restart-repl-scope-correction-collect v11-restart-repl-scope-correction-check v2-workbench-differential v2-workbench-services-check workbench-service-call-inventory-staging

workbench-service-call-inventory-selftest:
	python3 tools/host-lisp/workbench_service_call_inventory.py --selftest

workbench-service-call-inventory-current: $(WORKBENCH_SERVICE_INVENTORY_ARTIFACTS)
	python3 tools/host-lisp/workbench_service_call_inventory.py \
		--contract "$(WORKBENCH_SERVICE_INVENTORY_CONTRACT)" \
		--mode current --json-out "$(WORKBENCH_SERVICE_INVENTORY_REPORT)"

# C1 is the canonical Wave-1 product policy: the generated Workbench sources
# retain the exact compiler tier until a persistent foreign allocation needs
# its region. Diagnostic builds may still override this tool explicitly.
V2_WORKBENCH_CODEMOD_TOOL ?= tools/host-lisp/v11_c1_lease_codemod.py

v2-workbench-codemod:
	PYTHONDONTWRITEBYTECODE=1 python3 $(V2_WORKBENCH_CODEMOD_TOOL) --selftest
	PYTHONDONTWRITEBYTECODE=1 python3 $(V2_WORKBENCH_CODEMOD_TOOL)

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

v11-surface-delivery-parity-selftest:
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v11_surface_delivery_parity.py --selftest

v11-surface-delivery-parity-check: v11-surface-delivery-parity-selftest v2-workbench-artifacts
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v11_surface_delivery_parity.py

v11-repl-banner-visual-selftest:
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v11_repl_banner_visual.py --selftest

v11-repl-banner-visual-check: v11-repl-banner-visual-selftest v2-workbench-artifacts v11-repl-banner-vm-check
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v11_repl_banner_visual.py \
		--suite "$(V2_WORKBENCH_SUITE_DIR)/p0-stdlib-einsuite-core-workbench-subset.json" \
		--json-out "$(V11_REPL_BANNER_VISUAL_REPORT)"

v2-workbench-library-composition-check: v11-repl-banner-visual-check
	python3 tools/host-lisp/workbench_disklib_budget.py \
		--resident-manifest "$(V2_WORKBENCH_ARTIFACT_DIR)/stdlib-p0.manifest.json" \
		--disk-lib-manifest "$(V2_WORKBENCH_LIB_DIR)/ide.manifest.json" \
		--disk-lib-manifest "$(V2_WORKBENCH_LIB_DIR)/idex.manifest.json" \
		--disk-lib-manifest "$(V2_WORKBENCH_LIB_DIR)/m65d.manifest.json" \
		--extra-cflags "$(WORKBENCH_DEFINES)" \
		--native-c src/vm.c --native-c src/symbol.c \
		--boot-symbol-calibration "$(WORKBENCH_COMPOSITION_BOOT_SYMBOL_CALIBRATION)" \
		--boot-namepool-calibration "$(WORKBENCH_COMPOSITION_BOOT_NAMEPOOL_CALIBRATION)" \
		--retained-symbols "$(WORKBENCH_COMPOSITION_RETAINED_SYMBOLS)" \
		--retained-namepool-bytes "$(WORKBENCH_COMPOSITION_RETAINED_NAMEPOOL_BYTES)" \
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

v11-buffer-library-composition-check: v2-workbench-artifacts bytecode-p0-buffer-lib-artifacts
	python3 tools/host-lisp/workbench_disklib_budget.py \
		--resident-manifest "$(V2_WORKBENCH_ARTIFACT_DIR)/stdlib-p0.manifest.json" \
		--disk-lib-manifest "$(V2_WORKBENCH_LIB_DIR)/ide.manifest.json" \
		--disk-lib-manifest "$(V2_WORKBENCH_LIB_DIR)/idex.manifest.json" \
		--disk-lib-manifest "$(V2_WORKBENCH_LIB_DIR)/m65d.manifest.json" \
		--disk-lib-manifest "$(BYTECODE_BUFFER_LIB_PREFIX).manifest.json" \
		--extra-cflags "$(WORKBENCH_DEFINES)" \
		--native-c src/vm.c --native-c src/symbol.c \
		--boot-symbol-calibration "$(WORKBENCH_COMPOSITION_BOOT_SYMBOL_CALIBRATION)" \
		--boot-namepool-calibration "$(WORKBENCH_COMPOSITION_BOOT_NAMEPOOL_CALIBRATION)" \
		--retained-symbols "$(WORKBENCH_COMPOSITION_RETAINED_SYMBOLS)" \
		--retained-namepool-bytes "$(WORKBENCH_COMPOSITION_RETAINED_NAMEPOOL_BYTES)" \
		--boot-align8 \
		--min-load-headroom 0 \
		--min-post-align-headroom 0 \
		--min-codebuf-headroom 0 \
		--min-ext-code-peak-headroom 0 \
		--min-ext-code-post-headroom 0 \
		--min-symbol-headroom "$(WORKBENCH_MIN_SYMBOL_HEADROOM)" \
		--min-namepool-headroom "$(WORKBENCH_MIN_NAMEPOOL_HEADROOM)" \
		--disk-file-max "$(WORKBENCH_DISK_FILE_MAX)" \
		--json-out "$(V11_BUFFER_COMPOSITION_REPORT)"

v11-m-transactional-fasl-observations: v2-workbench-artifacts
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/bytecode_p0_stdlib.py --check \
		--observation-report build/bytecode/dialect-v2/v11-m-implementation-observations.json \
		$(V2_WORKBENCH_SUITE_DIR)/p0-m65d-lib.json
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/chain_walker_inventory.py --selftest
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/chain_walker_inventory.py \
		--out build/bytecode/dialect-v2/chain-walker-inventory.json

v11-m-transactional-fasl-acceptance-selftest:
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v11_m_transactional_fasl_acceptance.py selftest

v11-m-transactional-fasl-acceptance-collect: v11-m-transactional-fasl-acceptance-selftest v11-m-transactional-fasl-observations v2-workbench-library-composition-check workbench-overlay-stack-guard v2-fasl-save-host-check
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v11_m_transactional_fasl_acceptance.py collect

v11-m-transactional-fasl-acceptance-check: v11-m-transactional-fasl-acceptance-selftest v11-m-transactional-fasl-observations v2-workbench-library-composition-check workbench-overlay-stack-guard v2-fasl-save-host-check
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v11_m_transactional_fasl_acceptance.py check

v11-g-green-surface-observations: v2-workbench-artifacts
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/bytecode_p0_stdlib.py --check \
		--observation-report build/bytecode/dialect-v2/v11-g-green-observations.json \
		$(V2_WORKBENCH_SUITE_DIR)/p0-stdlib-einsuite-core-workbench-subset.json

v11-g-green-surface-acceptance-selftest:
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v11_restart_repl_scope_correction.py selftest

v11-g-green-surface-acceptance-collect: v11-g-green-surface-acceptance-selftest v11-g-green-surface-observations v11-surface-delivery-parity-check v2-workbench-library-composition-check workbench-overlay-stack-guard
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v11_restart_repl_scope_correction.py collect

v11-g-green-surface-acceptance-check: v11-g-green-surface-acceptance-selftest v11-g-green-surface-observations v11-surface-delivery-parity-check v2-workbench-library-composition-check workbench-overlay-stack-guard
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v11_restart_repl_scope_correction.py check

v11-restart-repl-scope-correction-selftest:
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v11_restart_repl_scope_correction.py selftest

v11-restart-repl-scope-correction-collect: v11-restart-repl-scope-correction-selftest v11-g-green-surface-observations v11-surface-delivery-parity-check v2-workbench-library-composition-check workbench-overlay-stack-guard
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v11_restart_repl_scope_correction.py collect

v11-restart-repl-scope-correction-check: v11-restart-repl-scope-correction-selftest v11-g-green-surface-observations v11-surface-delivery-parity-check v2-workbench-library-composition-check workbench-overlay-stack-guard
	PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/v11_restart_repl_scope_correction.py check

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
