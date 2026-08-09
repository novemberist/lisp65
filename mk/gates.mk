# Stable gate entry points and provider-neutral CI wrappers.

.PHONY: workspace-capacity-selftest workspace-capacity-check doctor doctor-selftest source-syntax-check ci-selftest document-index-selftest document-index-check c2-product-profile-parity-selftest c2-product-profile-parity-check c2-lite-v6-roots-fronts-product-profile-selftest c2-lite-v6-roots-fronts-product-profile-check c2-lite-media-acceptance-selftest c2-lite-public-clean-build-selftest c2-lite-public-clean-build-qualify c2-final-island-identity-check c2-append-final-hybrid-check c2-vm-badopcode-detail-check c2-install-phase-discriminator-check c2-phase06a-cutpoint-check c2-append-suffix-read-domain-check c2-l-full-keymap-end-to-end-check c2-crc-codegen-selftest c2-historical-gate-inheritance-selftest c2-historical-gate-inheritance-check c2-address-identity-contract-selftest c2-address-identity-contract-check c2-kernal-residency-audit-selftest c2-kernal-residency-audit-check c2-kernal-unmap-contract-check c2-kernal-unmap-contract-receipt-check c2-nested-append-v5-selftest c2-nested-append-v5-check c2-q-check upstream-verification-selftest upstream-verification-check proof-hooks-install evidence-archive-assets-selftest evidence-archive-assets-check evidence-archive-assets-remote-check evidence-archive-index-size-gate evidence-archive-history-size-gate history-transport-bootstrap history-transport-rewrite-check remote-source-binding-selftest remote-source-binding-receipt-check promotion-register-check promotion-preflight-check r4-product-candidate-check r5-global-g5-input-check r5-global-g5-seal-selftest r6-ship-selftest r6-g6-selftest r6-g6-registered-seal-check r7-manifest-prerequisites-tracked-check r7-release-check workbench-product-reproducibility-selftest workbench-product-reproducibility-check workbench-product-reproducibility-preflight media-guard-bank-attribution-check post-capture-planning-capacity-check chain-walker-inventory-check dialect-contract-selftest dialect-contract-check bytecode-abi-ledger-selftest bytecode-abi-ledger-check code-object-arity-contract-selftest code-object-arity-contract-check dialect-migration-selftest dialect-migration-contract-check r3-product-block-build r3-current-product-block-check r3-g3-g6-contract-check r3-g3-g6-environment-check r3-product-block-check r3-product-reproducibility-check r3-g3-static-preflight-check r3-stager-probe-check workbench-ux-harness-selftest semantic-contracts-selftest semantic-contracts-lint semantic-contracts-g0 semantic-contracts-g1 semantic-contracts-g2 bytecode-p0-omission-contract-check ci-check-source ci-check-host check-source check-host check-product check-reference reference-diagnostics check-emulator check-hardware-dry-run check-hardware
.PHONY: c2-bound-artifact-source-parity-selftest c2-bound-artifact-source-parity-required-check
.PHONY: c2-bound-artifact-source-parity-check
.PHONY: c2-interrupt-ownership-selftest
.PHONY: c2-interrupt-ownership-check
.PHONY: c2-mapped-far-service-ownership-selftest
.PHONY: c2-mapped-far-service-ownership-check
.PHONY: c2-mapped-far-asm-equivalence-selftest
.PHONY: c2-mapped-far-asm-equivalence-check
.PHONY: c2-v17-state-ownership-phase-c-selftest
.PHONY: c2-v17-state-ownership-phase-c-check
.PHONY: c2-v18-full-map-phase-c-selftest
.PHONY: c2-v18-full-map-phase-c-check
.PHONY: c2-v19-acceptance-vocabulary-selftest
.PHONY: c2-v19-acceptance-vocabulary-check
.PHONY: c2-v19-full-map-replay-selftest
.PHONY: c2-v19-full-map-replay-check
.PHONY: c2-v19-full-map-recharter-preflight
.PHONY: c2-v19-full-map-recharter-card
.PHONY: comfort-track-selftest
.PHONY: comfort-track-check
.PHONY: c2-v110-persistent-performance-selftest
.PHONY: c2-v110-persistent-performance-check
.PHONY: c2-v111-compiler-locality-selftest
.PHONY: c2-v111-compiler-locality-check
.PHONY: c2-random-base-check
.PHONY: c2-repl-banner-version-selftest
.PHONY: c2-repl-banner-version-check
.PHONY: c2-while-source-check
.PHONY: c2-while-check
.PHONY: c2-v124-time-check
.PHONY: c2-require-prior-append-option-a-check
.PHONY: ship-builder-contract-check ship-builder-sample-fleet-check ship-builder-reproducibility-check c2-ship-input-wait-check c2-ship-boot-inheritance-check c2-code-window-convergence-check c2-v130-static-input-carrier-selftest c2-v130-static-input-carrier-check c2-m65-hw-check
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

c2-product-profile-parity-selftest:
	python3 tools/host-lisp/c2_product_profile_parity.py --selftest

c2-product-profile-parity-check: c2-product-profile-parity-selftest
	python3 tools/host-lisp/c2_product_substitution_link.py --selftest

c2-lite-v6-roots-fronts-product-profile-selftest:
	python3 tools/host-lisp/c2_lite_v6_roots_fronts_product_profile.py selftest

c2-lite-v6-roots-fronts-product-profile-check: c2-lite-v6-roots-fronts-product-profile-selftest
	python3 tools/host-lisp/c2_lite_v6_roots_fronts_product_profile.py check

c2-lite-media-acceptance-selftest:
	python3 tools/host-lisp/c2_lite_product_reproducibility.py selftest
	python3 tools/host-lisp/c2_lite_r4.py selftest
	python3 tools/host-lisp/c2_lite_acceptance.py selftest
	python3 tools/host-lisp/promotion_archive_offline.py --remote-binding-selftest

.PHONY: c2-reset-domain-completeness-selftest c2-reset-domain-completeness-check
c2-reset-domain-completeness-selftest:
	python3 tools/host-lisp/c2_lite_media_product.py reset-domain-selftest

c2-reset-domain-completeness-check: c2-reset-domain-completeness-selftest

PUBLIC_BUILD_SOURCE_REPOSITORY ?= .
PUBLIC_BUILD_SOURCE_COMMIT ?= HEAD
PUBLIC_BUILD_RECEIPT ?= build/c2.3/v1.3.0-public-clean-build/receipt.json

c2-lite-public-clean-build-selftest:
	python3 tools/host-lisp/c2_lite_public_clean_build.py selftest

c2-lite-public-clean-build-qualify: c2-lite-public-clean-build-selftest
	python3 tools/host-lisp/c2_lite_public_clean_build.py qualify \
		--source-repository '$(PUBLIC_BUILD_SOURCE_REPOSITORY)' \
		--source-commit '$(PUBLIC_BUILD_SOURCE_COMMIT)' \
		--output '$(PUBLIC_BUILD_RECEIPT)'

c2-bound-artifact-source-parity-selftest:
	python3 tools/host-lisp/c2_bound_artifact_source_parity.py --selftest

c2-bound-artifact-source-parity-check: c2-bound-artifact-source-parity-selftest
	python3 tools/host-lisp/c2_bound_artifact_source_parity.py

# Acceptance-chain form: absence of the bound product is a hard failure here.
# Wired as a prerequisite of r4-product-candidate-check, where the bound
# authority must be current -- deliberately NOT inside workbench-product,
# because a link cycle repairs a stale binding by building first and
# rebinding after (a mid-build hook would be a chicken-and-egg block).
c2-bound-artifact-source-parity-required-check: c2-bound-artifact-source-parity-selftest
	python3 tools/host-lisp/c2_bound_artifact_source_parity.py --require-artifact

c2-interrupt-ownership-selftest:
	python3 tools/host-lisp/c2_interrupt_ownership_gate.py --selftest

c2-interrupt-ownership-check: c2-interrupt-ownership-selftest
	python3 tools/host-lisp/c2_interrupt_ownership_gate.py \
		--receipt tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.2-interrupt-ownership-source-gate-receipt.json

c2-mapped-far-service-ownership-selftest:
	python3 tools/host-lisp/c2_mapped_far_service_gate.py --selftest

c2-mapped-far-service-ownership-check: c2-mapped-far-service-ownership-selftest
	python3 tools/host-lisp/c2_mapped_far_service_gate.py \
		--receipt tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-stack-overlay-mapped-far-service-ownership-gate-receipt.json

c2-mapped-far-asm-equivalence-selftest:
	python3 tools/host-lisp/c2_mapped_far_asm_equivalence.py --selftest

c2-mapped-far-asm-equivalence-check: c2-mapped-far-asm-equivalence-selftest
	python3 tools/host-lisp/c2_mapped_far_asm_equivalence.py \
		--receipt tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-v1.7-mapped-far-assembly-equivalence-receipt.json

c2-v17-state-ownership-phase-c-selftest:
	python3 tools/host-lisp/c2_v17_state_ownership_phase_c.py --selftest

c2-v17-state-ownership-phase-c-check: c2-v17-state-ownership-phase-c-selftest
	python3 tools/host-lisp/c2_v17_state_ownership_phase_c.py \
		--receipt tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-v1.7-state-ownership-phase-c-receipt.json

c2-v18-full-map-phase-c-selftest:
	python3 tools/host-lisp/c2_v18_full_map_phase_c.py selftest

c2-v18-full-map-phase-c-check: c2-v18-full-map-phase-c-selftest
	python3 tools/host-lisp/c2_v18_full_map_phase_c.py check \
		--receipt tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-v1.8-full-map-phase-c-gate-receipt.json

c2-v19-acceptance-vocabulary-selftest:
	python3 tools/host-lisp/c2_v19_acceptance_vocabulary.py selftest

c2-v19-acceptance-vocabulary-check: c2-v19-acceptance-vocabulary-selftest
	python3 tools/host-lisp/c2_v19_acceptance_vocabulary.py check

c2-v19-full-map-replay-selftest: c2-v19-acceptance-vocabulary-check
	python3 tools/host-lisp/c2_v19_full_map_replay.py selftest

c2-v19-full-map-replay-check: c2-v19-full-map-replay-selftest
	python3 tools/host-lisp/c2_v19_full_map_replay.py check

c2-v19-full-map-recharter-preflight: c2-v19-full-map-replay-check
	python3 tools/host-lisp/c2_v19_full_map_recharter_wplto.py preflight

c2-v19-full-map-recharter-card:
	python3 tools/host-lisp/c2_v19_full_map_recharter_wplto.py card

comfort-track-selftest:
	python3 tools/host-lisp/comfort_track_gate.py selftest

# Host-only development freight.  This target compiles and executes the
# Bank-2 suite, but makes no product, packaging, release or device claim.
comfort-track-check: comfort-track-selftest
	python3 tools/host-lisp/comfort_track_gate.py check

c2-v110-persistent-performance-selftest:
	python3 tools/host-lisp/c2_v110_persistent_performance.py selftest

# Host-only candidate freight.  The gate reuses the exact Link-82
# reconstruction and prices both the complete and post-require lanes; product,
# release, link and device claims remain deferred to an ordinary release block.
c2-v110-persistent-performance-check: c2-v110-persistent-performance-selftest
	python3 tools/host-lisp/c2_v110_persistent_performance_replay.py

c2-v111-compiler-locality-selftest:
	python3 tools/host-lisp/c2_v111_compiler_locality.py selftest

# Host-only compiler-carrier candidate.  The gate regenerates the carrier,
# substitutes it in the exact 1.10 reconstruction, and proves normalized
# emitted-CodeObject equivalence plus the sub-180 structural price.  Product,
# release, link and device claims remain deferred to a release block.
c2-v111-compiler-locality-check: c2-v111-compiler-locality-selftest
	python3 tools/host-lisp/c2_v111_compiler_locality.py check

.PHONY: c2-v112-release-freight-selftest c2-v112-release-freight-check
.PHONY: c2-v112-release-closure-selftest c2-v112-release-closure-check
.PHONY: c2-v112-candidate-product-startup-selftest
.PHONY: c2-v112-candidate-media-startup-selftest
.PHONY: c2-v112-split-media-check
.PHONY: c2-v112-phase-d-boot-choreography-selftest
.PHONY: c2-v112-ownership-opt-in-closure-selftest c2-v112-ownership-opt-in-closure-check
c2-v112-release-freight-selftest:
	python3 tools/host-lisp/c2_v112_release_freight.py selftest

c2-v112-release-freight-check: c2-v112-release-freight-selftest
	python3 tools/host-lisp/c2_v112_release_freight.py check

c2-v112-release-closure-selftest:
	python3 tools/host-lisp/c2_v112_release_closure.py selftest

c2-v112-release-closure-check: c2-v112-release-closure-selftest c2-v112-release-freight-check
	python3 tools/host-lisp/c2_v112_release_closure.py check

c2-v112-candidate-product-startup-selftest:
	python3 tools/host-lisp/c2_v112_candidate_product.py selftest

# Source-only lifecycle closer for the v1.4 two-variant media driver.  The
# readback must run in a fresh process, and a second configure_shared() in one
# process must be rejected by the harness before the one-shot product selector.
c2-v112-candidate-media-startup-selftest:
	python3 tools/host-lisp/c2_v112_candidate_media.py startup-selftest

c2-v112-split-media-check:
	python3 tools/host-lisp/c2_v112_split_media.py check

c2-v112-phase-d-boot-choreography-selftest:
	python3 tools/host-lisp/c2_v112_phase_d_boot_choreography.py selftest

.PHONY: c2-v112-phase-d-d1-smokes-selftest
c2-v112-phase-d-d1-smokes-selftest:
	python3 tools/host-lisp/c2_v112_phase_d_d1_smokes.py selftest

.PHONY: c2-v112-phase-d-d3-selftest
c2-v112-phase-d-d3-selftest:
	python3 tools/host-lisp/c2_v112_phase_d_d3.py selftest

.PHONY: c2-v112-phase-d-d2-selftest
c2-v112-phase-d-d2-selftest:
	python3 tools/host-lisp/c2_v112_phase_d_d2.py selftest

.PHONY: c2-v112-trace-red-attribution-selftest c2-v112-trace-red-attribution-check
c2-v112-trace-red-attribution-selftest:
	python3 tools/host-lisp/c2_v112_trace_red_attribution.py selftest

c2-v112-trace-red-attribution-check:
	python3 tools/host-lisp/c2_v112_trace_red_attribution.py archive-check

.PHONY: c2-v112-trace-fix-scope-selftest c2-v112-trace-fix-scope-check
c2-v112-trace-fix-scope-selftest:
	python3 tools/host-lisp/c2_v112_trace_fix_scope.py selftest

# The commissioned inspect-only fix must fail closed if the delivered Link-92
# ABI cannot expose the exact old function cell or an atomic publication seam.
c2-v112-trace-fix-scope-check: c2-v112-trace-red-attribution-check c2-v112-trace-fix-scope-selftest
	python3 tools/host-lisp/c2_v112_trace_fix_scope.py check

c2-v112-ownership-opt-in-closure-selftest:
	python3 tools/host-lisp/c2_v112_ownership_opt_in_closure.py selftest

# Permanent closure of parked-ownership contamination in the canonical build.
# The check drives the exact v1.4 candidate stack only through its seed link;
# the opt-in sources, defines, linker layout/flags and full-map checker rows
# must all be absent, and the process exits before materialization or product.
c2-v112-ownership-opt-in-closure-check: c2-v112-ownership-opt-in-closure-selftest
	python3 tools/host-lisp/c2_v112_ownership_opt_in_closure.py check

# The random suite extends the generated C2-lite Workbench suite.  A dirty
# proof tree used to provide that file accidentally; a fresh public clone
# does not.  Make the generator a real prerequisite so the public entry point
# never depends on a neighbouring or pre-existing build directory.
c2-random-base-check: v2-workbench-codemod
	python3 tools/host-lisp/c2_random_base_gate.py

c2-repl-banner-version-selftest:
	python3 tools/host-lisp/c2_repl_banner_version_gate.py --selftest

c2-repl-banner-version-check: c2-repl-banner-version-selftest
	python3 tools/host-lisp/c2_repl_banner_version_gate.py

c2-while-source-check:
	python3 tools/host-lisp/c2_while_gate.py --source-only

c2-while-check: equivalence-check
	python3 tools/host-lisp/c2_while_gate.py

c2-q-check:
	python3 tools/host-lisp/c2_q_gate.py

c2-m65-hw-check:
	python3 tools/host-lisp/c2_m65_hw_gate.py

c2-ship-input-wait-check:
	python3 tools/host-lisp/c2_ship_input_wait_gate.py

c2-ship-boot-inheritance-check: c2-ship-input-wait-check
	python3 tools/host-lisp/c2_ship_boot_inheritance_gate.py

c2-code-window-convergence-check: c2-ship-boot-inheritance-check
	python3 tools/host-lisp/c2_code_window_convergence_gate.py

c2-v130-static-input-carrier-selftest:
	python3 tools/host-lisp/c2_v130_static_input_carrier.py selftest

c2-v130-static-input-carrier-check: c2-v130-static-input-carrier-selftest
	python3 tools/host-lisp/c2_v130_static_input_carrier.py check

c2-v124-time-check:
	python3 tools/host-lisp/c2_v124_time_gate.py

c2-require-prior-append-option-a-check:
	python3 tools/host-lisp/c2_require_prior_append_option_a_gate.py

c2-final-island-identity-check:
	python3 tools/host-lisp/c2_final_island_identity_gate.py check-source

c2-vm-badopcode-detail-check:
	python3 tools/host-lisp/c2_vm_badopcode_detail_gate.py check-source

c2-install-phase-discriminator-check:
	python3 tools/host-lisp/c2_install_phase_discriminator_gate.py check-source

c2-phase06a-cutpoint-check:
	python3 tools/host-lisp/c2_phase06a_cutpoint_gate.py check-source

c2-append-suffix-read-domain-check:
	python3 tools/host-lisp/c2_append_suffix_read_domain_gate.py check-source

c2-l-full-keymap-end-to-end-check:
	python3 tools/host-lisp/v11_l_lite_keymap.py selftest
	python3 tools/host-lisp/v11_l_lite_keymap.py check
	python3 tools/host-lisp/c2_l_full_keymap_end_to_end_gate.py

c2-l-full-static-plane-check:
	python3 tools/host-lisp/c2_l_full_static_plane_gate.py

c2-append-final-hybrid-check:
	python3 tools/host-lisp/c2_append_final_hybrid_gate.py
	python3 tools/host-lisp/c2_numeric_early_errors_gate.py

c2-crc-codegen-selftest:
	python3 tools/host-lisp/c2_crc_codegen_gate.py --selftest
	python3 tools/host-lisp/c2_crc_asm_leaf_gate.py --selftest
	python3 tools/host-lisp/c2_asm_leaf_abi_gate.py --selftest
	python3 tools/host-lisp/c2_fixed_block_leaf_gate.py --selftest

c2-historical-gate-inheritance-selftest: c2-crc-codegen-selftest
	python3 tools/host-lisp/c2_historical_gate_inheritance.py --selftest

c2-historical-gate-inheritance-check: c2-historical-gate-inheritance-selftest
	python3 tools/host-lisp/c2_historical_gate_inheritance.py

.PHONY: comment-language-selftest comment-language-check
comment-language-selftest:
	python3 tools/host-lisp/comment_language_gate.py --selftest

comment-language-check: comment-language-selftest
	python3 tools/host-lisp/comment_language_gate.py

.PHONY: post-11-housekeeping-selftest post-11-housekeeping-check
post-11-housekeeping-selftest:
	python3 tools/host-lisp/post_11_housekeeping.py --selftest

post-11-housekeeping-check: post-11-housekeeping-selftest
	python3 tools/host-lisp/post_11_housekeeping.py

c2-address-identity-contract-selftest:
	python3 tools/host-lisp/c2_contract_check.py --selftest

c2-address-identity-contract-check: c2-address-identity-contract-selftest
	python3 tools/host-lisp/c2_contract_check.py

c2-kernal-residency-audit-selftest:
	python3 tools/host-lisp/c2_kernal_residency_audit.py --selftest

c2-kernal-residency-audit-check: c2-kernal-residency-audit-selftest
	python3 tools/host-lisp/c2_kernal_residency_audit.py

c2-kernal-unmap-contract-check:
	python3 tools/host-lisp/c2_kernal_unmap_contract_gate.py

c2-kernal-unmap-contract-receipt-check:
	python3 tools/host-lisp/c2_kernal_unmap_contract_gate.py --verify-receipt

c2-nested-append-v5-selftest:
	python3 tools/host-lisp/c2_nested_append_v5_prelink.py --selftest

c2-nested-append-v5-check: c2-nested-append-v5-selftest
	python3 tools/host-lisp/c2_nested_append_v5_prelink.py

upstream-verification-selftest:
	python3 tools/host-lisp/upstream_verification.py --selftest

upstream-verification-check: upstream-verification-selftest
	python3 tools/host-lisp/upstream_verification.py

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

r4-product-candidate-check: c2-bound-artifact-source-parity-required-check
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

# R3 remains immutable historical evidence after the C2-lite promotion.  The
# live source gate proves the current L65M inputs separately and consumes the
# registered C2 promotion seal; rebuilding the retired Attic-shelf product
# would reintroduce the public v1.1 geometry as a second build truth.
r3-current-product-block-check: l65m-v2-product-check r6-g6-registered-seal-check

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

check-source: comment-language-check post-v1.2-housekeeping-check
check-source: c2-bound-artifact-source-parity-check
# The v1.9 closure consumes immutable historical receipts.  Run it before
# legacy source gates that reconstruct those receipts with today's date.  This
# orders permanent checks only; it does not reopen or retry the terminal card.
check-source: c2-v19-acceptance-vocabulary-check
check-source: c2-v19-full-map-replay-check
check-source: c2-interrupt-ownership-check
check-source: c2-mapped-far-service-ownership-check
check-source: c2-mapped-far-asm-equivalence-check
check-source: c2-v17-state-ownership-phase-c-check
check-source: c2-v18-full-map-phase-c-check
check-source: comfort-track-check
check-source: c2-v110-persistent-performance-check
check-source: c2-v111-compiler-locality-check
check-source: c2-v112-release-freight-check
check-source: c2-v112-release-closure-check
check-source: c2-v112-candidate-product-startup-selftest
check-source: c2-v112-candidate-media-startup-selftest
check-source: c2-v112-split-media-check
check-source: c2-v112-phase-d-boot-choreography-selftest
check-source: c2-v112-phase-d-d1-smokes-selftest
check-source: c2-v112-phase-d-d3-selftest
check-source: c2-v112-phase-d-d2-selftest
check-source: c2-v112-trace-red-attribution-check
check-source: c2-v112-trace-fix-scope-check
check-source: c2-v112-ownership-opt-in-closure-check
check-source: c2-random-base-check
check-source: c2-repl-banner-version-check
check-source: c2-while-source-check
check-source: c2-q-check c2-ship-input-wait-check c2-ship-boot-inheritance-check c2-code-window-convergence-check
check-source: c2-v124-time-check
check-source: c2-require-prior-append-option-a-check
check-source: ship-builder-contract-check
check-source: c2-v126-editor-allocation-check
check-source: c2-reset-domain-completeness-check
check-source: c2-v130-static-input-carrier-check
check-source: c2-m65-hw-check
check-source: c2-v16-defstruct-duration-pricing-check
check-source: c2-v16-defstruct-patience-result-check
check-source: c2-v16-defstruct-vm-cost-closure-check
check-source: c2-v16-vm-progress-noninterference-selftest

.PHONY: c2-v16-defstruct-duration-pricing-selftest c2-v16-defstruct-duration-pricing-check
c2-v16-defstruct-duration-pricing-selftest:
	python3 tools/host-lisp/c2_v16_defstruct_duration_pricing.py selftest

# Permanent observation-floor authority. It rejects bulk-scaling the two-byte
# DMA result and any monitor/screenshot action before the priced 780-second floor.
c2-v16-defstruct-duration-pricing-check: c2-v16-defstruct-duration-pricing-selftest
	python3 tools/host-lisp/c2_v16_defstruct_duration_pricing.py check

.PHONY: c2-v16-defstruct-patience-result-selftest c2-v16-defstruct-patience-result-check
c2-v16-defstruct-patience-result-selftest:
	python3 tools/host-lisp/c2_v16_defstruct_patience_result.py selftest

# Permanent closure of the priced patience contact.  It preserves the
# non-completion claim without upgrading a stopped projection to a live-state
# plateau or an absent timing term to a product mechanism.
c2-v16-defstruct-patience-result-check: c2-v16-defstruct-patience-result-selftest
	python3 tools/host-lisp/c2_v16_defstruct_patience_result.py check

.PHONY: c2-v16-defstruct-vm-cost-closure-selftest c2-v16-defstruct-vm-cost-closure-check
c2-v16-defstruct-vm-cost-closure-selftest: c2-v16-defstruct-patience-result-check
	python3 tools/host-lisp/c2_v16_defstruct_vm_cost_closure.py selftest

# Permanent closure of the missing ordinary-VM cost term.  It preserves the
# distinction between a priced observation floor and an unproved completion
# bound, and rejects hours-scale and product-mechanism overclaims.
c2-v16-defstruct-vm-cost-closure-check: c2-v16-defstruct-vm-cost-closure-selftest
	python3 tools/host-lisp/c2_v16_defstruct_vm_cost_closure.py check

.PHONY: c2-v16-vm-progress-selftest c2-v16-vm-progress-check
c2-v16-vm-progress-selftest: c2-v16-defstruct-vm-cost-closure-check
	python3 tools/host-lisp/c2_v16_vm_progress_witness.py selftest

# Explicit materialized-artifact gate: this non-promotable identity derives
# from the historical Link-82 shadow build.  It therefore stays outside
# check-source while binding its low-RAM ownership, execution vectors and
# contact-not-authorized boundary.
c2-v16-vm-progress-check: c2-v16-vm-progress-selftest
	python3 tools/host-lisp/c2_v16_vm_progress_witness.py check

.PHONY: c2-v16-vm-progress-noninterference-selftest c2-v16-vm-progress-noninterference-check
c2-v16-vm-progress-noninterference-selftest: c2-v16-defstruct-vm-cost-closure-check
	python3 tools/host-lisp/c2_v16_vm_progress_noninterference.py selftest

# Permanent source-side closure of the three sampler hazards.  The explicit
# check additionally binds the materialized non-promotable Link-82 sibling.
c2-v16-vm-progress-noninterference-check: c2-v16-vm-progress-noninterference-selftest
	python3 tools/host-lisp/c2_v16_vm_progress_noninterference.py check

.PHONY: c2-v126-editor-allocation-selftest c2-v126-editor-allocation-check
c2-v126-editor-allocation-selftest:
	python3 tools/host-lisp/c2_v126_editor_allocation_gate.py selftest

c2-v126-editor-allocation-check: c2-v126-editor-allocation-selftest v2-workbench-artifacts
	python3 tools/host-lisp/c2_v126_editor_allocation_gate.py check

.PHONY: c2-v16-defstruct-phase-a-selftest c2-v16-defstruct-phase-a-check
c2-v16-defstruct-phase-a-selftest:
	python3 tools/host-lisp/c2_v16_defstruct_phase_a.py selftest

# Historical Link-82 authorities are deliberately materialized inputs, so this
# diagnosis gate is explicit rather than a fresh-clone check-source dependency.
c2-v16-defstruct-phase-a-check: c2-v16-defstruct-phase-a-selftest
	python3 tools/host-lisp/c2_v16_defstruct_phase_a.py check

.PHONY: c2-v16-defstruct-phase-b-selftest c2-v16-defstruct-phase-b-check
c2-v16-defstruct-phase-b-selftest:
	python3 tools/host-lisp/c2_v16_defstruct_phase_b.py selftest

# Like Phase A, this forensic gate binds released Link-82 materialized inputs.
# It remains explicit rather than imposing historical artifacts on fresh clones.
c2-v16-defstruct-phase-b-check: c2-v16-defstruct-phase-b-selftest
	python3 tools/host-lisp/c2_v16_defstruct_phase_b.py check

.PHONY: c2-v16-defstruct-phase-c-selftest c2-v16-defstruct-phase-c-check c2-v16-defstruct-phase-c-dry-run
c2-v16-defstruct-phase-c-selftest:
	python3 tools/host-lisp/c2_v16_defstruct_phase_c.py selftest

# The prepared diagnostic binds released Link-82 materialized inputs and is
# therefore explicit rather than a fresh-clone check-source dependency.
c2-v16-defstruct-phase-c-check: c2-v16-defstruct-phase-c-selftest
	python3 tools/host-lisp/c2_v16_defstruct_phase_c.py check

c2-v16-defstruct-phase-c-dry-run: c2-v16-defstruct-phase-c-check
	scripts/c2-v16-defstruct-phase-c-hw.sh dry-run

.PHONY: c2-v16-phase-d-desk-attribution-selftest c2-v16-phase-d-desk-attribution-check
c2-v16-phase-d-desk-attribution-selftest:
	python3 tools/host-lisp/c2_v16_phase_d_desk_attribution.py selftest

# This forensic check binds released Link-88 and diagnostic Link-82 materialized
# artifacts, so it is explicit rather than a fresh-clone check-source input.
c2-v16-phase-d-desk-attribution-check: c2-v16-phase-d-desk-attribution-selftest
	python3 tools/host-lisp/c2_v16_phase_d_desk_attribution.py check

.PHONY: c2-v16-d2-choreography-selftest c2-v16-d2-choreography-check c2-v16-d2-choreography-dry-run
c2-v16-d2-choreography-selftest:
	python3 tools/host-lisp/c2_v16_d2_choreography_closure.py selftest

# This closure binds the materialized Link-82 forensic identity and is therefore
# explicit rather than a fresh-clone check-source dependency.
c2-v16-d2-choreography-check: c2-v16-d2-choreography-selftest
	python3 tools/host-lisp/c2_v16_d2_choreography_closure.py check

c2-v16-d2-choreography-dry-run: c2-v16-d2-choreography-check
	scripts/c2-v16-defstruct-closing-d2-hw.sh dry-run

.PHONY: c2-v16-d2-physical-fallback-selftest c2-v16-d2-physical-fallback-check c2-v16-d2-physical-fallback-dry-run
c2-v16-d2-physical-fallback-selftest:
	python3 tools/host-lisp/c2_v16_d2_physical_fallback.py selftest

# Materialized Link-82 forensic inputs keep this physical-owner fallback explicit.
c2-v16-d2-physical-fallback-check: c2-v16-d2-physical-fallback-selftest
	python3 tools/host-lisp/c2_v16_d2_physical_fallback.py check

c2-v16-d2-physical-fallback-dry-run: c2-v16-d2-physical-fallback-check
	scripts/c2-v16-defstruct-closing-d2-physical.sh dry-run

.PHONY: c2-v16-boot-order-durable-witness-selftest c2-v16-boot-order-durable-witness-check
c2-v16-boot-order-durable-witness-selftest:
	python3 tools/host-lisp/c2_v16_boot_order_durable_witness.py selftest

# Desk-only forensic closure over materialized Link-82 and 1.7/1.8 ownership
# authorities.  Keep it explicit rather than making fresh clones materialize
# historical products merely to prove the witness-lifetime rule.
c2-v16-boot-order-durable-witness-check: c2-v16-boot-order-durable-witness-selftest
	python3 tools/host-lisp/c2_v16_boot_order_durable_witness.py check

.PHONY: c2-v16-mapping-data-boot-gc-selftest c2-v16-mapping-data-boot-gc-check
c2-v16-mapping-data-boot-gc-selftest:
	python3 tools/host-lisp/c2_v16_mapping_data_boot_gc.py selftest

# Desk-only closure over materialized Link-82 product and core authorities.
# Keep it explicit: fresh clones need not materialize historical products to
# enforce the stopped-data view and healthy pre-prompt schedule conclusions.
c2-v16-mapping-data-boot-gc-check: c2-v16-mapping-data-boot-gc-selftest
	python3 tools/host-lisp/c2_v16_mapping_data_boot_gc.py check

.PHONY: c2-v16-gc-address-caller-attribution-selftest c2-v16-gc-address-caller-attribution-check
c2-v16-gc-address-caller-attribution-selftest:
	python3 tools/host-lisp/c2_v16_gc_address_caller_attribution.py selftest

# Desk-only closure over the consumed full-ladder packet, materialized Link-82,
# the configured ROM and primary-core mapping rules. Keep it explicit: fresh
# clones need not materialize historical products merely to preserve this claim.
c2-v16-gc-address-caller-attribution-check: c2-v16-gc-address-caller-attribution-selftest
	python3 tools/host-lisp/c2_v16_gc_address_caller_attribution.py check

.PHONY: c2-v16-mem-init-before-after-selftest c2-v16-mem-init-before-after-check c2-v16-mem-init-before-after-dry-run
c2-v16-mem-init-before-after-selftest:
	python3 tools/host-lisp/c2_v16_mem_init_before_after.py selftest
	python3 tools/host-lisp/c2_v16_mem_init_before_after_contact.py selftest

# Diagnostic-only materialized Link-82 witness and one-shot contact closure.
# Explicit because fresh clones need not materialize the historical image.
c2-v16-mem-init-before-after-check: c2-v16-mem-init-before-after-selftest c2-reset-domain-completeness-check
	python3 tools/host-lisp/c2_v16_mem_init_before_after.py check
	python3 tools/host-lisp/c2_v16_mem_init_before_after_contact.py check

c2-v16-mem-init-before-after-dry-run: c2-v16-mem-init-before-after-check
	scripts/c2-v16-defstruct-mem-init-before-after-hw.sh dry-run

.PHONY: c2-v16-mem-init-before-after-result-selftest c2-v16-mem-init-before-after-result-check
c2-v16-mem-init-before-after-result-selftest:
	python3 tools/host-lisp/c2_v16_mem_init_before_after_contact.py result-selftest

# Consumed-contact closure: it preserves both tool/staging First Reds and
# explicitly leaves the mem_init binary question and R/A/I/G unmeasured.
c2-v16-mem-init-before-after-result-check: c2-v16-mem-init-before-after-result-selftest
	python3 tools/host-lisp/c2_v16_mem_init_before_after_contact.py result-check

.PHONY: c2-v16-mem-init-repeat-mapping-recovery-selftest c2-v16-mem-init-repeat-mapping-recovery-check
c2-v16-mem-init-repeat-mapping-recovery-selftest:
	python3 tools/host-lisp/c2_v16_mem_init_repeat_mapping_recovery.py selftest

# Same-stop recovery closure for the consumed repeat contact.  It is explicit
# because the historical Link-82 image and live stopped-state handoff are local.
c2-v16-mem-init-repeat-mapping-recovery-check: c2-v16-mem-init-repeat-mapping-recovery-selftest
	python3 tools/host-lisp/c2_v16_mem_init_repeat_mapping_recovery.py check

.PHONY: c2-v16-mem-init-repeat-mapping-result-selftest c2-v16-mem-init-repeat-mapping-result-check
c2-v16-mem-init-repeat-mapping-result-selftest:
	python3 tools/host-lisp/c2_v16_mem_init_repeat_mapping_recovery.py result-selftest

c2-v16-mem-init-repeat-mapping-result-check: c2-v16-mem-init-repeat-mapping-result-selftest
	python3 tools/host-lisp/c2_v16_mem_init_repeat_mapping_recovery.py result-check

.PHONY: c2-v16-mem-init-witness-write-view-selftest c2-v16-mem-init-witness-write-view-check
c2-v16-mem-init-witness-write-view-selftest: c2-v16-mem-init-repeat-mapping-result-check
	python3 tools/host-lisp/c2_v16_mem_init_witness_write_view.py selftest

c2-v16-mem-init-witness-write-view-check: c2-v16-mem-init-witness-write-view-selftest
	python3 tools/host-lisp/c2_v16_mem_init_witness_write_view.py check

.PHONY: c2-v16-mem-init-preoverlay-status-partition-selftest c2-v16-mem-init-preoverlay-status-partition-check
c2-v16-mem-init-preoverlay-status-partition-selftest: c2-v16-mem-init-witness-write-view-check
	python3 tools/host-lisp/c2_v16_mem_init_preoverlay_status_partition.py selftest

c2-v16-mem-init-preoverlay-status-partition-check: c2-v16-mem-init-preoverlay-status-partition-selftest
	python3 tools/host-lisp/c2_v16_mem_init_preoverlay_status_partition.py check

.PHONY: c2-v16-mem-init-preoverlay-status-salvage-selftest c2-v16-mem-init-preoverlay-status-salvage-check
c2-v16-mem-init-preoverlay-status-salvage-selftest: c2-v16-mem-init-preoverlay-status-partition-check
	python3 tools/host-lisp/c2_v16_mem_init_preoverlay_status_salvage.py selftest

c2-v16-mem-init-preoverlay-status-salvage-check: c2-v16-mem-init-preoverlay-status-salvage-selftest
	python3 tools/host-lisp/c2_v16_mem_init_preoverlay_status_salvage.py check

.PHONY: c2-v16-preinstaller-stretch-attribution-selftest c2-v16-preinstaller-stretch-attribution-check
c2-v16-preinstaller-stretch-attribution-selftest: c2-v16-mem-init-preoverlay-status-salvage-check
	python3 tools/host-lisp/c2_v16_preinstaller_stretch_attribution.py selftest

c2-v16-preinstaller-stretch-attribution-check: c2-v16-preinstaller-stretch-attribution-selftest
	python3 tools/host-lisp/c2_v16_preinstaller_stretch_attribution.py check

.PHONY: c2-v16-preinstaller-micro-ladder-selftest c2-v16-preinstaller-micro-ladder-check
c2-v16-preinstaller-micro-ladder-selftest: c2-v16-preinstaller-stretch-attribution-check
	python3 tools/host-lisp/c2_v16_preinstaller_micro_ladder.py selftest
	python3 tools/host-lisp/c2_v16_preinstaller_micro_ladder_contact.py selftest

c2-v16-preinstaller-micro-ladder-check: c2-v16-preinstaller-micro-ladder-selftest
	python3 tools/host-lisp/c2_v16_preinstaller_micro_ladder.py check
	python3 tools/host-lisp/c2_v16_preinstaller_micro_ladder_contact.py check

.PHONY: c2-v16-preinstaller-micro-ladder-result-selftest c2-v16-preinstaller-micro-ladder-result-check
c2-v16-preinstaller-micro-ladder-result-selftest: c2-v16-preinstaller-micro-ladder-check
	python3 tools/host-lisp/c2_v16_preinstaller_micro_ladder_result.py selftest

c2-v16-preinstaller-micro-ladder-result-check: c2-v16-preinstaller-micro-ladder-result-selftest
	python3 tools/host-lisp/c2_v16_preinstaller_micro_ladder_result.py check

.PHONY: c2-v16-ownership-guard-attribution-selftest c2-v16-ownership-guard-attribution-check
c2-v16-ownership-guard-attribution-selftest: c2-v16-preinstaller-micro-ladder-result-check
	python3 tools/host-lisp/c2_v16_ownership_guard_attribution.py selftest

c2-v16-ownership-guard-attribution-check: c2-v16-ownership-guard-attribution-selftest
	python3 tools/host-lisp/c2_v16_ownership_guard_attribution.py check

.PHONY: c2-v16-ownership-crc-full-run-selftest c2-v16-ownership-crc-full-run-check
c2-v16-ownership-crc-full-run-selftest: c2-v16-ownership-guard-attribution-check
	python3 tools/host-lisp/c2_v16_ownership_crc_full_run.py selftest

c2-v16-ownership-crc-full-run-check: c2-v16-ownership-crc-full-run-selftest
	python3 tools/host-lisp/c2_v16_ownership_crc_full_run.py check

.PHONY: c2-v16-ownership-crc-full-run-result-selftest c2-v16-ownership-crc-full-run-result-check
c2-v16-ownership-crc-full-run-result-selftest: c2-v16-ownership-crc-full-run-check
	python3 tools/host-lisp/c2_v16_ownership_crc_full_run_result.py selftest

# Offline closure over the consumed full run. The expected refill bytes come
# from the captured C2D/Bank-2 source planes, never from refill metadata.
c2-v16-ownership-crc-full-run-result-check: c2-v16-ownership-crc-full-run-result-selftest
	python3 tools/host-lisp/c2_v16_ownership_crc_full_run_result.py check

.PHONY: c2-v16-slot39-provenance-correction-selftest c2-v16-slot39-provenance-correction-check
c2-v16-slot39-provenance-correction-selftest: c2-v16-ownership-crc-full-run-result-check
	python3 tools/host-lisp/c2_v16_slot39_provenance_correction.py selftest

# Loudly supersedes the consumed result's Slot-39/A interpretation while
# preserving its device capture and the valid bounded refill/error facts.
c2-v16-slot39-provenance-correction-check: c2-v16-slot39-provenance-correction-selftest
	python3 tools/host-lisp/c2_v16_slot39_provenance_correction.py check

.PHONY: c2-v16-pre-rollback-shadow-selftest c2-v16-pre-rollback-shadow-check
c2-v16-pre-rollback-shadow-selftest: c2-v16-slot39-provenance-correction-check
	python3 tools/host-lisp/c2_v16_pre_rollback_shadow.py selftest

# Non-promotable identity only.  The hardware question remains owner-gated;
# this target proves placement, pre-rollback ordering and rollback unreachability.
c2-v16-pre-rollback-shadow-check: c2-v16-pre-rollback-shadow-selftest
	python3 tools/host-lisp/c2_v16_pre_rollback_shadow.py check

.PHONY: c2-v16-pre-rollback-shadow-contact-selftest c2-v16-pre-rollback-shadow-contact-check
c2-v16-pre-rollback-shadow-contact-selftest: c2-v16-pre-rollback-shadow-check
	python3 tools/host-lisp/c2_v16_pre_rollback_shadow_contact.py selftest

# Owner-authorized, non-promotable one-shot appointment.  This target prepares
# and audits the choreography only; it never touches the device.
c2-v16-pre-rollback-shadow-contact-check: c2-v16-pre-rollback-shadow-contact-selftest
	python3 tools/host-lisp/c2_v16_pre_rollback_shadow_contact.py check

.PHONY: c2-v16-pre-rollback-shadow-result-selftest c2-v16-pre-rollback-shadow-result-check
c2-v16-pre-rollback-shadow-result-selftest: c2-v16-pre-rollback-shadow-contact-check
	python3 tools/host-lisp/c2_v16_pre_rollback_shadow_result.py selftest

# Offline close over the consumed shadow repeat.  The target keeps the
# pre-registered R/A/I/G table honest: a D01A=0 source-less capture is a loud
# classifier First Red, never a post-hoc pure-I row.
c2-v16-pre-rollback-shadow-result-check: c2-v16-pre-rollback-shadow-result-selftest
	python3 tools/host-lisp/c2_v16_pre_rollback_shadow_result.py check

.PHONY: c2-v16-durable-progress-selftest c2-v16-durable-progress-check
c2-v16-durable-progress-selftest: c2-v16-pre-rollback-shadow-result-check
	@true

# The one-shot preparation was consumed.  Its immutable receipt and staged
# identity are now owned by the result closure, so this historical target is a
# compatibility alias rather than a rebind against the subsequently grown plan.
c2-v16-durable-progress-check: c2-v16-durable-progress-result-check
	@true

.PHONY: c2-v16-durable-progress-result-selftest c2-v16-durable-progress-result-check
c2-v16-durable-progress-result-selftest: c2-v16-identity-view-attribution-selftest
	@true

# The fourth-row classification was consumed and corrected by the identity/view
# attribution below. Its immutable receipt is bound there; do not silently
# rebind it merely because the append-only 1.6 plan grew.
c2-v16-durable-progress-result-check: c2-v16-identity-view-attribution-check
	@true

.PHONY: c2-v16-identity-view-attribution-selftest c2-v16-identity-view-attribution-check
c2-v16-identity-view-attribution-selftest:
	python3 tools/host-lisp/c2_v16_durable_progress_identity_view_attribution.py selftest

# Desk-only closure over the consumed Link-82 contact, configured ROM and
# pinned core/tool monitor semantics. Keep explicit because it binds
# materialized forensic products and a local ROM authority.
c2-v16-identity-view-attribution-check: c2-v16-identity-view-attribution-selftest
	python3 tools/host-lisp/c2_v16_durable_progress_identity_view_attribution.py check

.PHONY: c2-v16-corrected-view-result-selftest c2-v16-corrected-view-result-check
c2-v16-corrected-view-result-selftest:
	python3 tools/host-lisp/c2_v16_corrected_view_result.py selftest

# Corrected CPU-view samples, mapping fields and independent product-window
# separation. Explicit because the closure binds forensic build products.
c2-v16-corrected-view-result-check: c2-v16-corrected-view-result-selftest
	python3 tools/host-lisp/c2_v16_corrected_view_result.py check

.PHONY: c2-v16-corrected-view-quiet-preparation-selftest c2-v16-corrected-view-quiet-preparation-check
c2-v16-corrected-view-quiet-preparation-selftest:
	python3 tools/host-lisp/c2_v16_corrected_view_contact.py selftest

# Owner-authorized one-shot schedule closure. The preparation rejects revoked
# authorization and any first t1 before the bound 27.653-second quiet interval.
c2-v16-corrected-view-quiet-preparation-check: c2-v16-corrected-view-quiet-preparation-selftest
	python3 tools/host-lisp/c2_v16_corrected_view_contact.py check

.PHONY: c2-v16-corrected-view-quiet-result-selftest c2-v16-corrected-view-quiet-result-check
c2-v16-corrected-view-quiet-result-selftest:
	python3 tools/host-lisp/c2_v16_corrected_view_quiet_result.py selftest

# Desk closure over the consumed quiet contact. It reuses the already bound
# historical live-E000 class without inventing an exact backing ROM identity.
c2-v16-corrected-view-quiet-result-check: c2-v16-corrected-view-quiet-result-selftest
	python3 tools/host-lisp/c2_v16_corrected_view_quiet_result.py check

.PHONY: c2-v16-physical-run-handover-desk-selftest c2-v16-physical-run-handover-desk-check
c2-v16-physical-run-handover-desk-selftest:
	python3 tools/host-lisp/c2_v16_physical_run_handover_desk.py selftest

# Artifact/runner comparison only. The leading prelaunch-crossing hypothesis
# remains non-causal and no follow-up contact is authorized here.
c2-v16-physical-run-handover-desk-check: c2-v16-physical-run-handover-desk-selftest
	python3 tools/host-lisp/c2_v16_physical_run_handover_desk.py check

.PHONY: c2-v16-control-shaped-discriminator-selftest c2-v16-control-shaped-discriminator-check
c2-v16-control-shaped-discriminator-selftest:
	python3 tools/host-lisp/c2_v16_control_shaped_discriminator.py selftest

# Owner-authorized one-shot preparation. The source-order mutation rejects any
# prelaunch monitor crossing after READY and any first t1 before 27.653 s.
c2-v16-control-shaped-discriminator-check: c2-v16-control-shaped-discriminator-selftest
	python3 tools/host-lisp/c2_v16_control_shaped_discriminator.py check

.PHONY: c2-v16-control-shaped-result-selftest c2-v16-control-shaped-result-check
c2-v16-control-shaped-result-selftest:
	python3 tools/host-lisp/c2_v16_control_shaped_result.py selftest

# Desk closure over the consumed no-prelaunch discriminator. It falsifies the
# monitor-crossing hypothesis without pretending the remaining boundary is fixed.
c2-v16-control-shaped-result-check: c2-v16-control-shaped-result-selftest
	python3 tools/host-lisp/c2_v16_control_shaped_result.py check

.PHONY: c2-v16-residual-launch-boundary-selftest c2-v16-residual-launch-boundary-check
c2-v16-residual-launch-boundary-selftest:
	python3 tools/host-lisp/c2_v16_residual_launch_boundary.py selftest

# Desk-only closure over materialized Link-82 forensic artifacts. It separates
# physical staging from CPU-visible delivery and authorizes no contact or fix.
c2-v16-residual-launch-boundary-check: c2-v16-residual-launch-boundary-selftest
	python3 tools/host-lisp/c2_v16_residual_launch_boundary.py check

.PHONY: c2-v16-bootstrap-romc-repair-selftest c2-v16-bootstrap-romc-repair-check
c2-v16-bootstrap-romc-repair-selftest:
	python3 tools/host-lisp/c2_v16_bootstrap_romc_repair.py selftest

# Materialized Link-82 diagnostic repair. The linked-image walker enforces the
# mapping-before-transfer rule; it changes no promotable or product artifact.
c2-v16-bootstrap-romc-repair-check: c2-v16-bootstrap-romc-repair-selftest
	python3 tools/host-lisp/c2_v16_bootstrap_romc_repair.py check

.PHONY: c2-v17-state-ownership-phase-a-selftest c2-v17-state-ownership-phase-a-check
c2-v17-state-ownership-phase-a-selftest:
	python3 tools/host-lisp/c2_v17_state_ownership_phase_a.py selftest

# The Phase-A census binds the failed sole 1.5 WPLTO and final Link-90 ELF;
# keep it explicit rather than requiring forensic build products in a clone.
c2-v17-state-ownership-phase-a-check: c2-v17-state-ownership-phase-a-selftest
	python3 tools/host-lisp/c2_v17_state_ownership_phase_a.py check

.PHONY: c2-v17-state-ownership-phase-b-selftest c2-v17-state-ownership-phase-b-check
c2-v17-state-ownership-phase-b-selftest:
	python3 tools/host-lisp/c2_v17_state_ownership_phase_b.py selftest

# Phase B binds the Phase-A forensic inventory and therefore remains an
# explicit architecture check rather than a fresh-clone check-source input.
c2-v17-state-ownership-phase-b-check: c2-v17-state-ownership-phase-b-selftest
	python3 tools/host-lisp/c2_v17_state_ownership_phase_b.py check

check-source: workspace-capacity-check doctor-selftest source-syntax-check ci-selftest document-index-check c2-product-profile-parity-check c2-lite-v6-roots-fronts-product-profile-check c2-lite-media-acceptance-selftest c2-final-island-identity-check c2-append-final-hybrid-check c2-vm-badopcode-detail-check c2-install-phase-discriminator-check c2-phase06a-cutpoint-check c2-append-suffix-read-domain-check c2-l-full-keymap-end-to-end-check c2-l-full-static-plane-check c2-historical-gate-inheritance-check c2-address-identity-contract-check c2-kernal-unmap-contract-check c2-nested-append-v5-selftest c2-overlay-transaction-auth-check promotion-register-check block-bank-delta-policy-check block-capacity-delta-policy-check dialect-contract-check bytecode-abi-ledger-check code-object-arity-contract-check dialect-migration-selftest dialect-migration-contract-check dialect-v2-prelude-control-check dialect-v2-eval-apply-funcall-check dialect-v2-lists-check dialect-v2-lists-p0-selftest dialect-v2-lists-lcc-selftest dialect-v2-lists-type-errors-check dialect-v2-strings-check dialect-v2-strings-p0-selftest dialect-v2-strings-lcc-selftest dialect-v2-system-runtime-check dialect-v2-lcc-surface-selftest dialect-v2-prelude-evidence-check dialect-v2-ide-evidence-check dialect-v2-capacity-ledger-selftest r2-known-open-check directory-only-l65m-v2-probe-check l65m-v2-product-check r3-current-product-block-check r6-g6-registered-seal-check r7-manifest-prerequisites-tracked-check r7-release-check v2-prim-lowering-check v2-carrier-state-selftest v2-workbench-symbol-diff-check v2-workbench-deresidentization-audit-check v2-workbench-deresidentization-prototype-check v2-runtime-core-service-inventory-selftest v2-capability-carrier-internal-g5-check v2-capability-carrier-contract-check workbench-service-call-inventory-selftest v11-surface-delivery-parity-check v11-source-stream-lifetime-selftest v11-function-metadata-check workbench-product-contract-check workbench-ux-harness-selftest runtime-known-open-check semantic-contracts-selftest semantic-contracts-g0 bytecode-p0-omission-contract-check bank0-lifetime-selftest bank0-island-inventory-selftest resident-island-selftest vm-ext-code-reclaim-smoke asm-c-constant-contract-check mega65-math-override-check error-text-table-selftest error-code-contract-selftest error-overlay-smoke workbench-disk-lib-budget-selftest ide-capacity-selftest persistence-contract-check runtime-export-contract-check runtime-core-audit-selftest workbench-overlay-stage-selftest runtime-overlay-bank-selftest hw-ship-memory-readback-selftest xmega65-safety-check bytecode-p0-program-check bytecode-p0-bundle-check workbench-ship-verifier-selftest

check-host: check-source ship-builder-sample-fleet-check ship-builder-reproducibility-check c2-while-check semantic-contracts-g1 host-oracle fixed-point-check closure-surface-check ide-host-slice-check eval-bytecode-equivalence-check equivalence-check dialect-v2-lcc-surface-check dialect-v2-capacity-ledger-check dialect-v2-number-to-string-check v2-fasl-save-host-check v11-m-transactional-fasl-acceptance-check v2-capability-carrier-check-host-3 dialect-v2-prelude-evidence-live-check post-mvp-stdlib-polish-check stdlib-embed-whatif-check bytecode-p0-stdlib-check string-arena-probe bytecode-p0-private-inline-check workbench-private-inline-composition-probe gc-symbol-scan-timing-check bytecode-p0-ide-full-lib-check bytecode-p0-ide-extra-lib-check bytecode-p0-m65d-lib-check bytecode-p0-ide-lib-artifacts d81-persistence-fault-selftest demo-suite-check ide-bytecode-cost-report ide-bytecode-dynamic-report runtime-core-smoke gc-smoke compile-smoke compile-run repl-session lcc-install-device-smoke lcc-install-overlay-smoke vm-boot-fastpath-smoke error-state-smoke prelude-compile-check prelude-load-run eval-prims-smoke save-semantics-check output-smoke screen-smoke v11-wave3-dry-smoke

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
