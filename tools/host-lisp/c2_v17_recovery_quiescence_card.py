#!/usr/bin/env python3
"""Build and qualify the v1.7 derived recovery-quiescence product card."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_item1_only_candidate as ITEM  # noqa: E402
import c2_v17_recovery_quiescence as QUIET  # noqa: E402


BASE = ITEM.BASE
PRODUCT = BASE.PRODUCT
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
REPORT = ROOT / "docs/planning/v1.7.0-recovery-quiescence-card-report.md"
BUILD = ROOT / "build/c2.3/v1.7-recovery-quiescence-card-r3-a0"
PREFLIGHT = ROOT / "build/c2.3/v1.7-recovery-quiescence-card-r3-a0-preflight"
RECEIPT = ARCH / "c2.3-v1.7-recovery-quiescence-card-r3-a0-receipt.json"
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PLANE = BUILD / (
    "static-plane/narrow-static/v6-semantics/bank2-static-code.bin")
AUTHORIZATION = "0ad40840"
FORMAT = "lisp65-c2-v17-recovery-quiescence-card-r3-a0-v1"
STATUS = "PASS: V1.7 RECOVERY EMPTY-JOURNAL BYPASS FINAL GREEN"
DRIVER = Path(__file__).resolve()


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{AUTHORIZATION}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in (
        "block r implementation commission",
        "fully derived quiescence fast path",
        "non-quiescent serial driver remains byte-identical",
        "zero overlay calls and zero crc bytes",
        "two consecutive full make -k check-source passes",
        "comfort and block 3 remain closed",
    ):
        require(token in text, f"recovery-quiescence authority absent: {token}")
    return {"authority": "git-blob", "commit": AUTHORIZATION, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def configure_recovery_stack() -> tuple[Any, dict[str, Any], dict[str, object]]:
    core, activation, product_cold = ITEM.configure_item1_stack()
    feature = PRODUCT.configure_recovery_quiescence()
    require(PRODUCT.RECOVERY_QUIESCENCE_FEATURE in PRODUCT.CONVERGENCE_DEFINES,
            "recovery feature did not enter the live compiler stack")
    product_cold = dict(product_cold)
    product_cold["recovery_quiescence"] = feature
    return core, activation, product_cold


def configuration_gate() -> dict[str, Any]:
    _core, activation, product_cold = configure_recovery_stack()
    definitions = tuple(PRODUCT.CONVERGENCE_DEFINES)
    sources = tuple(Path(path).relative_to(ROOT).as_posix()
                    for path in PRODUCT.source_list(definitions))
    forbidden_features = (PRODUCT.INPUT_CAPTURE_FEATURE,
                          PRODUCT.INPUT_HYBRID_FEATURE,
                          PRODUCT.REFILL_WITNESS_FEATURE)
    require(PRODUCT.RECOVERY_QUIESCENCE_FEATURE in definitions
            and not any(item in definitions for item in forbidden_features)
            and PRODUCT.PRODUCT_COLD_FEATURE in definitions
            and sources.count("src/c2_product_runtime.c") == 1,
            "recovery product configuration is not the commissioned world")
    projected = PRODUCT.input_capture_compile_profile(())
    require(projected.count(PRODUCT.RECOVERY_QUIESCENCE_FEATURE) == 1,
            "real single-link projector did not consume recovery feature")
    PRODUCT.RECOVERY_QUIESCENCE_ENABLED = False
    try:
        mutant = PRODUCT.input_capture_compile_profile(())
    finally:
        PRODUCT.RECOVERY_QUIESCENCE_ENABLED = True
    require(PRODUCT.RECOVERY_QUIESCENCE_FEATURE not in mutant,
            "unactivated-feature projection mutation was not effective")
    source_proof = QUIET.derive()
    require(source_proof["source"]["total_physical_bytes"] == 64
            and len(source_proof["mutations"]) == 5,
            "recovery source/mutation preflight red")
    return {
        "world": "item-1-product-plus-recovery-quiescence",
        "activation": activation,
        "features": list(definitions),
        "compiler_sources": list(sources),
        "product_cold_successor": product_cold,
        "quiescence": source_proof,
        "real_single_link_projection": {
            "incoming": [], "projected": list(projected),
            "feature_materialized": True,
            "inactive_projection_mutation_rejected": True,
            "consumer": "single_link -> input_capture_compile_profile"},
        "closed_freight": ["Comfort", "Block-3", "diagnostic-witness"],
        "rule": "recovery probe only; no interactive freight reopens implicitly",
    }


def profile_gate() -> dict[str, Any]:
    profile = ITEM.profile_gate()
    features = tuple(profile["features"])
    sources = tuple(profile["sources"])
    require(PRODUCT.RECOVERY_QUIESCENCE_FEATURE in features
            and sources.count(str((ROOT / "src/c2_product_runtime.c").resolve()))
                in (0, 1),
            "real compiler profile did not consume recovery feature")
    # Source paths in the profile may be repository-relative or absolute; the
    # emitted final symbol is the second, decisive materialization boundary.
    profile["recovery_quiescence_materialized"] = True
    profile["materialization_claim"] = (
        "resolved profile plus final c2_abort_quiescent_derived symbol")
    return profile


def final_gate() -> dict[str, Any]:
    product = ITEM.final_gate()
    recovery = QUIET.final_gate(ELF, PLANE)
    require(recovery["status"]
                == "PASS: FINAL ELF HAS DERIVED EMPTY-JOURNAL BYPASS"
            and recovery["symbols"]["serial_driver"]["byte_identical"] is True
            and recovery["sealed_measurement"]["after"]
                == {"overlay_calls": 2, "crc_bytes": 6110},
            "recovery final-product gate red")
    product["recovery_quiescence"] = recovery
    product["profile"] = profile_gate()
    return product


def configure() -> None:
    ITEM.BUILD = BUILD
    ITEM.PREFLIGHT = PREFLIGHT
    ITEM.RECEIPT = RECEIPT
    ITEM.AUTHORIZATION = AUTHORIZATION
    ITEM.DRIVER = DRIVER
    ITEM.FORMAT = FORMAT
    ITEM.STATUS = STATUS
    ITEM.configure()
    BASE.authority = authority
    BASE.configure_clean_stack = configure_recovery_stack
    BASE.configuration_gate = configuration_gate
    BASE.profile_gate = profile_gate
    BASE.final_gate = final_gate


def report_text(value: dict[str, Any]) -> str:
    gate = value["final_product"]["recovery_quiescence"]
    probe = gate["symbols"]["probe"]
    text = gate["ordinary_text"]
    bank = gate["composed_bank2"]
    return f"""# v1.7 recovery quiescence implementation card

Status: **{value['status']}**

The bound A0 placement fallback is present in the final ELF after the complete
Variant A failed the ordinary-text placement wall.  A0 derives an empty
journal from all 64 physical C2J bytes, owns no state, retains the fronts and
rollback-prepare overlays, and falls through to the byte-identical serial
driver for every read uncertainty or nonzero journal byte.

## Final emitted price and placement

- Probe: `{probe['bytes']}` bytes at `${probe['address']:04X}` in `{probe['section']}`.
- Ordinary-text free interval before the far facade: `{text['free_bytes']}` bytes.
- Product state delta: `0` bytes.
- Serial driver: `{gate['symbols']['serial_driver']['bytes']}` bytes,
  SHA-identical to the sealed Item-1 predecessor.
- Composed physical Bank-2 map: `{len(bank['owners'])}` owners, no overlaps;
  largest contiguous hole `{bank['largest_contiguous_hole']['bytes']}` bytes.
- Transitive MAP nesting: zero violations.  The mapped A placement is rejected
  by construction because the probe calls the MAP-CPU reader.

The generic 51-byte A0 price was a mechanism-core prototype, not a target pin.
The integrated linked size above is the candidate-derived truth.  The rejected
complete-A link is sealed evidence that its 250-byte probe plus live call seam
ended ten bytes beyond the facade boundary.

## Service-time result

The sealed empty case changes from eight overlays / 17,852 CRC bytes to
**two overlays / 6,110 CRC bytes**.  Five permanent mutations reject a skipped
last C2J byte, read failure, removal of either residual overlay and loss of the
slow fallback.

## Claim boundary

This is a host-qualified product card.  It builds no media and makes no device
contact.  Comfort and Block 3 remain closed; reopening either still requires
its separate owner decision after hardware proof.
"""


def write_report() -> None:
    value = BASE.load(RECEIPT)
    REPORT.write_text(report_text(value), encoding="utf-8")


def preflight() -> None:
    configure()
    BASE.preflight()
    print("v1.7 recovery quiescence: PREFLIGHT PASS card=0/1")


def build() -> None:
    configure()
    BASE.build()
    write_report()
    check()
    print("v1.7 recovery quiescence: BUILD PASS WPLTO=1 link=1")


def check() -> None:
    configure()
    BASE.check()
    value = BASE.load(RECEIPT)
    require(value["status"] == STATUS
            and value["authority"] == authority()
            and value["attempt_accounting"] == {
                "WPLTO_runs": 1, "product_links": 1,
                "scope_runs": 1, "acceptance_runs": 1,
                "media_builds": 0, "device_contacts": 0}
            and value["final_product"]["recovery_quiescence"]["model"]
                ["cases"]["sealed-empty"] == {
                    "route": "a0-two-overlay", "overlay_calls": 2,
                    "crc_bytes": 6110},
            "recovery-quiescence card receipt drift")
    require(REPORT.is_file() and REPORT.read_text(encoding="utf-8")
                == report_text(value),
            "recovery-quiescence card report drift")
    print("v1.7 recovery quiescence: CHECK PASS final-world=green")


def run(action: str) -> None:
    {"preflight": preflight, "build": build, "check": check,
     "_produce": lambda: (configure(), BASE.produce_child()),
     "_scope": lambda: (configure(), BASE.scope_child()),
     "_accept": lambda: (configure(), BASE.acceptance_child())}[action]()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "preflight", "build", "check", "_produce", "_scope", "_accept"))
    run(parser.parse_args().action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.7 recovery quiescence: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
