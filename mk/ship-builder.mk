# Ship Builder v1: public surface, sample fleet and reproducibility gates.

SHIP_BUILDER_TOOL := tools/host-lisp/ship_builder.py
SHIP_BUILDER_CC := $(abspath $(CC_M65))

.PHONY: ship-builder-contract-check ship-builder-sample-fleet-check
.PHONY: ship-builder-reproducibility-check ship-builder-clean-reproducibility-check

ship-builder-contract-check:
	python3 $(SHIP_BUILDER_TOOL) selftest

ship-builder-sample-fleet-check: ship-builder-contract-check | build
	@tmp=$$(mktemp -d build/ship-builder-fleet.XXXXXX); \
	trap 'rm -rf "$$tmp"' EXIT; \
	python3 $(SHIP_BUILDER_TOOL) fleet --out "$$tmp/fleet" --cc '$(SHIP_BUILDER_CC)'

# Fast permanent lane: two empty output trees, one source tree.  The stricter
# fresh-checkout form below is required by the release/acceptance ritual.
ship-builder-reproducibility-check: ship-builder-contract-check | build
	@tmp=$$(mktemp -d build/ship-builder-repro.XXXXXX); \
	trap 'rm -rf "$$tmp"' EXIT; \
	python3 $(SHIP_BUILDER_TOOL) repro \
		--form '(ship "hello" :entry '\''main)' \
		--project examples/ship/hello/project.l65p \
		--out "$$tmp/repro" --cc '$(SHIP_BUILDER_CC)'

ship-builder-clean-reproducibility-check: ship-builder-contract-check | build
	@tmp=$$(mktemp -d build/ship-builder-clean-repro.XXXXXX); \
	trap 'rm -rf "$$tmp"' EXIT; \
	python3 $(SHIP_BUILDER_TOOL) repro --fresh \
		--form '(ship "hello" :entry '\''main)' \
		--project examples/ship/hello/project.l65p \
		--out "$$tmp/repro" --cc '$(SHIP_BUILDER_CC)'
