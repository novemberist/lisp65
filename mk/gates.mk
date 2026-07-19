# Stable gate entry points and provider-neutral CI wrappers.

.PHONY: workspace-capacity-selftest workspace-capacity-check doctor doctor-selftest source-syntax-check ci-selftest document-index-selftest document-index-check proof-hooks-install evidence-archive-assets-selftest evidence-archive-assets-check evidence-archive-assets-remote-check evidence-archive-index-size-gate evidence-archive-history-size-gate history-transport-bootstrap history-transport-rewrite-check remote-source-binding-selftest remote-source-binding-receipt-check promotion-register-check promotion-preflight-check r4-product-candidate-check r5-global-g5-input-check r5-global-g5-seal-selftest r6-ship-selftest r6-g6-selftest r6-g6-registered-seal-check r7-manifest-prerequisites-tracked-check r7-release-check workbench-product-reproducibility-selftest workbench-product-reproducibility-check workbench-product-reproducibility-preflight media-guard-bank-attribution-check post-capture-planning-capacity-check chain-walker-inventory-check dialect-contract-selftest dialect-contract-check bytecode-abi-ledger-selftest bytecode-abi-ledger-check code-object-arity-contract-selftest code-object-arity-contract-check dialect-migration-selftest dialect-migration-contract-check r3-product-block-build r3-current-product-block-check r3-g3-g6-contract-check r3-g3-g6-environment-check r3-product-block-check r3-product-reproducibility-check r3-g3-static-preflight-check r3-stager-probe-check workbench-ux-harness-selftest semantic-contracts-selftest semantic-contracts-lint semantic-contracts-g0 semantic-contracts-g1 semantic-contracts-g2 bytecode-p0-omission-contract-check ci-check-source ci-check-host check-source check-host check-product check-reference reference-diagnostics check-emulator check-hardware-dry-run check-hardware
.NOTPARALLEL: check-source check-host check-product check-hardware-dry-run check-hardware check mvp-ship

DOCTOR_GATE ?= G2
DOCTOR_FORMAT ?= text
DOCTOR_ENV = MAKE="$(MAKE)" HOSTCC="$(HOSTCC)" C1541="$(C1541)" LLVM="$(LLVM)" CC_M65="$(CC_M65)" M65VMSTDLIB_NM="$(M65VMSTDLIB_NM)" M65VMSTDLIB_SIZE="$(M65VMSTDLIB_SIZE)"

workspace-capacity-selftest:
	python3 tools/host-lisp/workspace_capacity_check.py --selftest

workspace-capacity-check: workspace-capacity-selftest
	python3 tools/host-lisp/workspace_capacity_check.py

doctor:
	$(DOCTOR_ENV) python3 tools/host-lisp/project_doctor.py --gate "$(DOCTOR_GATE)" --format "$(DOCTOR_FORMAT)"

doctor-selftest:
	python3 tools/host-lisp/project_doctor.py --selftest

source-syntax-check:
	python3 tools/host-lisp/source_syntax_check.py --selftest
	python3 tools/host-lisp/source_syntax_check.py

ci-selftest:
	python3 tools/host-lisp/ci_gate.py --selftest

document-index-selftest:
	python3 tools/host-lisp/document_index.py --selftest

document-index-check: document-index-selftest
	python3 tools/host-lisp/document_index.py

proof-hooks-install:
	git config core.hooksPath .githooks
	test "$$(git config --get core.hooksPath)" = .githooks

evidence-archive-assets-selftest:
	python3 tools/host-lisp/evidence_archive_assets.py selftest

evidence-archive-index-size-gate: evidence-archive-assets-selftest
	python3 tools/host-lisp/evidence_archive_assets.py index-size-gate

evidence-archive-history-size-gate: evidence-archive-assets-selftest
	python3 tools/host-lisp/evidence_archive_assets.py history-size-gate

evidence-archive-assets-check: evidence-archive-assets-selftest evidence-archive-index-size-gate evidence-archive-history-size-gate
	python3 tools/host-lisp/evidence_archive_assets.py local-check

evidence-archive-assets-remote-check: evidence-archive-assets-selftest
	python3 tools/host-lisp/evidence_archive_assets.py remote-check

history-transport-bootstrap:
	python3 tools/host-lisp/history_transport_rewrite.py install-replace-refs

history-transport-rewrite-check: evidence-archive-assets-selftest history-transport-bootstrap
	python3 tools/host-lisp/history_transport_rewrite.py

remote-source-binding-selftest:
	python3 tools/host-lisp/remote_source_binding.py selftest
	python3 tools/host-lisp/promotion_archive_offline.py --remote-binding-selftest
	python3 tools/host-lisp/r6_g6_seal_offline.py --remote-binding-selftest

remote-source-binding-receipt-check: remote-source-binding-selftest
	python3 tools/host-lisp/remote_source_binding.py receipt-check

promotion-register-check: evidence-archive-assets-check history-transport-rewrite-check remote-source-binding-receipt-check
	python3 tools/host-lisp/promotion_archive.py register-check

workbench-product-reproducibility-selftest:
	python3 tools/host-lisp/workbench_product_reproducibility.py selftest

workbench-product-reproducibility-check: workbench-product-reproducibility-selftest
	python3 tools/host-lisp/workbench_product_reproducibility.py check

workbench-product-reproducibility-preflight: workbench-product-reproducibility-selftest
	python3 tools/host-lisp/workbench_product_reproducibility.py preflight

media-guard-bank-attribution-check:
	python3 tools/host-lisp/media_guard_bank_attribution.py verify

post-capture-planning-capacity-check:
	python3 tools/host-lisp/post_capture_planning_capacity.py selftest
	python3 tools/host-lisp/post_capture_planning_capacity.py check

chain-walker-inventory-check:
	python3 tools/host-lisp/chain_walker_inventory.py --selftest
	python3 tools/host-lisp/chain_walker_inventory.py \
		--out build/bytecode/dialect-v2/wave1-chain-walker-inventory-receipt.json

r4-product-candidate-check:
	python3 tools/host-lisp/promotion_archive.py product-candidate-check

r5-global-g5-input-check:
	python3 tools/host-lisp/promotion_archive.py r5-input-check

promotion-preflight-check: promotion-register-check workbench-product-reproducibility-preflight r3-product-reproducibility-check r4-product-candidate-check r5-global-g5-input-check

dialect-contract-selftest:
	python3 tools/host-lisp/dialect_contract.py --selftest

dialect-contract-check: dialect-contract-selftest
	python3 tools/host-lisp/dialect_contract.py

bytecode-abi-ledger-selftest:
	python3 tools/host-lisp/bytecode_abi_ledger.py --selftest

bytecode-abi-ledger-check: bytecode-abi-ledger-selftest
	python3 tools/host-lisp/bytecode_abi_ledger.py --require-staging-dispatch

code-object-arity-contract-selftest:
	python3 tools/host-lisp/code_object_arity_contract.py --selftest

code-object-arity-contract-check: code-object-arity-contract-selftest
	python3 tools/host-lisp/code_object_arity_contract.py

dialect-migration-selftest:
	python3 tools/host-lisp/dialect_migration_contract.py --selftest

dialect-migration-contract-check: dialect-contract-check bytecode-abi-ledger-check dialect-migration-selftest semantic-contracts-lint
	python3 tools/host-lisp/dialect_migration_contract.py

r3-product-block-build: asm-c-constant-contract-check block-capacity-delta-policy-check workbench-product-reproducibility-check media-guard-bank-attribution-check post-capture-planning-capacity-check chain-walker-inventory-check workbench-overlay-stack-guard v2-workbench-library-composition-check v11-wave3-l-lite-repin-check v11-wave3-dry-smoke
	python3 tools/host-lisp/r3_product_block.py generate \
		--receipt build/r3/product/product-block-receipt.json

# After the final G6 seal, live source gates rebuild the product but do not
# reinterpret immutable R3/R4/R5 receipts against a later harness matrix.
r3-current-product-block-check: r3-product-block-build
	python3 tools/host-lisp/r3_product_block.py check \
		--receipt build/r3/product/product-block-receipt.json

r6-g6-registered-seal-check: promotion-register-check r6-g6-selftest
	python3 tools/host-lisp/r6_g6_seal.py registered-verify

r7-manifest-prerequisites-tracked-check:
	python3 tools/host-lisp/r7_manifest_prerequisites.py selftest
	python3 tools/host-lisp/r7_manifest_prerequisites.py check \
		--manifest tests/bytecode/dialect-v2/evidence/r7/public-manifest-prerequisites.json \
		--receipt tests/bytecode/dialect-v2/evidence/r7/public-manifest-prerequisites-receipt.json

r7-release-check: r7-release-receipt-check

r3-g3-g6-contract-check: r3-product-block-build
	python3 tools/host-lisp/r3_g3_g6_contract.py selftest
	python3 tools/host-lisp/r3_g3_g6_contract.py check

r3-g3-g6-environment-check: r3-g3-g6-contract-check
	python3 tools/host-lisp/r3_g3_g6_contract.py environment-check

r3-product-block-check: r3-g3-g6-contract-check
	python3 tools/host-lisp/r3_product_block.py check

r3-product-reproducibility-check:
	python3 tools/host-lisp/r3_product_reproducibility.py selftest
	python3 tools/host-lisp/r3_product_reproducibility.py check

r3-g3-static-preflight-check: r3-product-block-check r3-product-reproducibility-check
	python3 tools/host-lisp/r3_g3_harness.py selftest
	python3 tools/host-lisp/r3_g3_harness.py check

# Compatibility entry point.  The launcher probe is sealed historical evidence;
# the live gate now validates the implemented product block and exact matrix.
r3-stager-probe-check: r3-g3-static-preflight-check

workbench-ux-harness-selftest:
	python3 tools/host-lisp/repl_screen_check.py --selftest
	python3 tools/host-lisp/hw_jtag_repl_harness_test.py
	python3 tools/host-lisp/workbench_ux_harness_test.py

semantic-contracts-selftest:
	python3 tools/host-lisp/reader_fixture.py --selftest
	python3 tools/host-lisp/l65m_contract.py selftest
	python3 tools/host-lisp/semantic_contracts.py selftest
	python3 tools/host-lisp/eval_surface_contract.py --selftest tests/bytecode/runtime/p0-eval-surface.json
	python3 tools/host-lisp/workbench_eval_surface.py --selftest
	python3 tools/host-lisp/bytecode_p0_native_compile_vectors.py --selftest tests/bytecode/p0-golden-vectors.json
	python3 scripts/lcc-oracle.py --selftest

semantic-contracts-lint:
	python3 tools/host-lisp/semantic_contracts.py lint

semantic-contracts-g0: semantic-contracts-lint
	python3 tools/host-lisp/semantic_contracts.py run --stage G0

semantic-contracts-g1: semantic-contracts-lint bytecode-p0-stdlib-artifacts bytecode-p0-disklib-artifacts $(FASL_EMIT_CHECK_ARTIFACT) $(L65M_NATIVE_LOADER_HOST) $(VM_SMOKE_HOST) $(VM_SMOKE_V2_HOST) $(BYTECODE_P0_NATIVE_COMPILER_HOST) $(EQUIVALENCE_HOST) $(READER_CONFORMANCE_HOST) $(READER_CONFORMANCE_ARENA_HOST) $(READER_ROOT_GUARD_HOST)
	python3 tools/host-lisp/semantic_contracts.py run --stage G1

semantic-contracts-g2: semantic-contracts-lint mvp-ship-candidate-artifacts l65m-verdict-equivalence-gate workbench-l65m-transport-ops-report workbench-l65m-commit-ops-report
	python3 tools/host-lisp/semantic_contracts.py run --stage G2

ci-check-source:
	python3 tools/host-lisp/ci_gate.py source

ci-check-host:
	python3 tools/host-lisp/ci_gate.py host

check-source: workspace-capacity-check doctor-selftest source-syntax-check ci-selftest document-index-check promotion-register-check block-bank-delta-policy-check block-capacity-delta-policy-check dialect-contract-check bytecode-abi-ledger-check code-object-arity-contract-check dialect-migration-contract-check dialect-v2-prelude-control-check dialect-v2-eval-apply-funcall-check dialect-v2-lists-check dialect-v2-lists-p0-selftest dialect-v2-lists-lcc-selftest dialect-v2-lists-type-errors-check dialect-v2-strings-check dialect-v2-strings-p0-selftest dialect-v2-strings-lcc-selftest dialect-v2-system-runtime-check dialect-v2-lcc-surface-selftest dialect-v2-prelude-evidence-check dialect-v2-ide-evidence-check dialect-v2-capacity-ledger-selftest r2-known-open-check directory-only-l65m-v2-probe-check l65m-v2-product-check r3-current-product-block-check r6-g6-registered-seal-check r7-manifest-prerequisites-tracked-check r7-release-check v2-prim-lowering-check v2-carrier-state-selftest v2-workbench-symbol-diff-check v2-workbench-deresidentization-audit-check v2-workbench-deresidentization-prototype-check v2-runtime-core-service-inventory-selftest v2-capability-carrier-internal-g5-check v2-capability-carrier-contract-check workbench-service-call-inventory-selftest v11-surface-delivery-parity-check v11-restart-repl-scope-correction-check v11-wave1-c1-first-form-check v11-source-stream-lifetime-selftest v11-wave2-error-text-library-check v11-wave2-list-unification-check v11-wave2-policy-name-implementation-check v11-wave2-common-repin-check v11-function-metadata-check v11-wave3-fail-fast-check v11-wave3-l-lite-repin-check workbench-product-contract-check workbench-ux-harness-selftest runtime-known-open-check semantic-contracts-selftest semantic-contracts-g0 bytecode-p0-omission-contract-check bank0-lifetime-selftest bank0-island-inventory-selftest resident-island-selftest vm-ext-code-reclaim-smoke asm-c-constant-contract-check mega65-math-override-check error-text-table-selftest error-code-contract-selftest error-overlay-smoke workbench-disk-lib-budget-selftest ide-capacity-selftest persistence-contract-check runtime-export-contract-check runtime-core-audit-selftest workbench-overlay-stage-selftest runtime-overlay-bank-selftest runtime-overlay-transport-smoke hw-ship-memory-readback-selftest xmega65-safety-check bytecode-p0-program-check bytecode-p0-bundle-check workbench-ship-verifier-selftest

check-host: check-source semantic-contracts-g1 host-oracle fixed-point-check closure-surface-check ide-host-slice-check eval-bytecode-equivalence-check equivalence-check dialect-v2-lcc-surface-check dialect-v2-capacity-ledger-check dialect-v2-number-to-string-check v2-fasl-save-host-check v11-m-transactional-fasl-acceptance-check v2-capability-carrier-check-host-3 dialect-v2-prelude-evidence-live-check post-mvp-stdlib-polish-check stdlib-embed-whatif-check bytecode-p0-stdlib-check string-arena-probe bytecode-p0-private-inline-check workbench-private-inline-composition-probe gc-symbol-scan-timing-check bytecode-p0-ide-full-lib-check bytecode-p0-ide-extra-lib-check bytecode-p0-m65d-lib-check bytecode-p0-ide-lib-artifacts d81-persistence-fault-selftest demo-suite-check ide-bytecode-cost-report ide-bytecode-dynamic-report runtime-core-smoke gc-smoke compile-smoke compile-run repl-session lcc-install-device-smoke lcc-install-overlay-smoke vm-boot-fastpath-smoke error-state-smoke prelude-compile-check prelude-load-run eval-prims-smoke save-semantics-check output-smoke screen-smoke v11-wave3-dry-smoke

check-product: check-host mvp-vm-stdlib-boot-budget-check mvp-vm-stdlib-runtime-budget-check bytecode-vm-compile-check workbench-overlay-bootstrap-smoke workbench-overlay-control-audit-selftest hw-stack-probe-readback-selftest workbench-product workbench-error-code-contract-check bank0-lifetime-report bank0-island-inventory-report runtime-core-prototype-check mvp-ship-artifacts bytecode-p0-ide-lib-check ide-capacity-check workbench-symfn-dynamic-report workbench-l65m-transport-ops-report workbench-l65m-commit-ops-report workbench-disk-lib-budget-check v2-workbench-library-composition-check workbench-d81-bam-sanity workbench-d81-bam-alloc-diff-selftest workbench-d81-chain-write-diff-selftest workbench-d81-dir-write-diff-selftest m65-disk-alloc-load-check m65-disk-alloc-var-load-check workbench-d81-save-new-diff-selftest workbench-d81-save-new-scan-diff-selftest workbench-d81-save-new-var-diff-selftest workbench-ship-artifacts-check semantic-contracts-g2

check-hardware-dry-run: hw-workbench-overlay-stack-guard-smoke-dry-run hw-smoke-vm-stdlib-dry-run hw-workbench-ux-smoke-dry-run hw-workbench-bam-read-smoke-dry-run hw-workbench-bam-alloc-smoke-dry-run hw-workbench-chain-write-smoke-dry-run hw-workbench-dir-write-smoke-dry-run hw-workbench-save-new-smoke-dry-run hw-workbench-save-new-scan-smoke-dry-run hw-workbench-save-new-var-smoke-dry-run

check-hardware: override MVP_VM_SHIP_DIR := $(MVP_VERIFIED_DIR)
check-hardware: override MVP_VM_SHIP_PRG := $(MVP_VERIFIED_DIR)/lisp65-mvp-workbench.prg
check-hardware: override MVP_VM_SHIP_BLOB := $(MVP_VERIFIED_DIR)/lisp65-mvp-workbench.blob.bin
check-hardware: override MVP_VM_SHIP_OVERLAYS := $(MVP_VERIFIED_DIR)/lisp65-mvp-workbench.overlays.bin
check-hardware: override MVP_VM_SHIP_D81 := $(MVP_VERIFIED_DIR)/lisp65-mvp-workbench.d81
check-hardware: override MVP_VM_SHIP_MANIFEST := $(MVP_VERIFIED_DIR)/manifest.json
check-hardware: override MVP_VM_SHIP_FOOTPRINT := $(MVP_VERIFIED_DIR)/mvp-vm-stdlib-footprint.txt
check-hardware: override MVP_VM_SHIP_D81_MANIFEST := $(MVP_VERIFIED_DIR)/workbench-d81-manifest.txt
check-hardware: override WORKBENCH_SHIP_D81 := $(MVP_VERIFIED_DIR)/lisp65-mvp-workbench.d81
check-hardware: override WORKBENCH_SHIP_D81_MANIFEST := $(MVP_VERIFIED_DIR)/workbench-d81-manifest.txt
check-hardware: verify-ship hw-workbench-overlay-stack-guard-verified-smoke hw-smoke-vm-stdlib hw-workbench-ux-smoke hw-workbench-bam-read-smoke hw-workbench-bam-alloc-smoke hw-workbench-chain-write-smoke hw-workbench-dir-write-smoke hw-workbench-save-new-smoke hw-workbench-save-new-scan-smoke hw-workbench-save-new-var-smoke

check-reference: legacy-lisp64-oracle mvp-vm-stdlib-s5-proof hw-smoke-vm-stdlib-selftest-dry-run

reference-diagnostics: mvp-vm-stdlib-einsuite-full-footprint-report hw-access-smoke-dry-run hw-color-ram-smoke-dry-run hw-edma-screen-smoke-dry-run

check-emulator:
	@printf '%s\n' 'check-emulator: NOT AVAILABLE (kein echter Workbench-xmega65-Flow)'
	@exit 2

check: check-product
