#!/usr/bin/env python3
"""Replace the Phase-1b card with a path-closed library adapter."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v17_comfort_phase1b_card as CARD  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v1.7-comfort-phase1b-variant-b-adapter-r1"
PREFLIGHT = ROOT / "build/c2.3/v1.7-comfort-phase1b-variant-b-adapter-r1-preflight"
RECEIPT = ARCH / (
    "c2.3-v1.7-comfort-phase1b-variant-b-adapter-r1-receipt.json")
FIRST_RED = ARCH / (
    "c2.3-v1.7-comfort-phase1b-variant-b-card-first-red.json")
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
LIBRARY = BUILD / "library/repl-comfort"
LIBRARY_SUITE = BUILD / "library/product-profile-suite.json"
LIBRARY_OBSERVATIONS = BUILD / "library/observations.json"
RESIDENT = ROOT / "tests/bytecode/libs/p0-repl-comfort-resident.json"
AUTHORIZATION = "870e5f53"
FORMAT = "lisp65-c2-v17-comfort-phase1b-variant-b-adapter-r1-v1"
STATUS = "PASS: V1.7 COMFORT PHASE 1B PATH-CLOSED VARIANT B FINAL GREEN"
DRIVER = Path(__file__).resolve()

ORIGINAL_CONFIGURATION_GATE = CARD.configuration_gate


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def suite_spec(delivered: list[int], *, explicit_resident: bool) -> dict[str, Any]:
    value: dict[str, Any] = {
        "extends": str(CARD.COMFORT.COMFORT_SUITE.resolve()),
        "delivered_callprims": list(delivered),
    }
    if explicit_resident:
        value["resident_suites"] = [str(RESIDENT.resolve())]
    return value


def adapter_preflight_gate() -> dict[str, Any]:
    profile = CARD.load(CARD.PRICING_RECEIPT)["product_callprim_profile"]
    delivered = profile["delivered_ids"]
    with tempfile.TemporaryDirectory(
            prefix="v17-phase1b-adapter-", dir=ROOT / "build") as name:
        root = Path(name)
        good_path = root / "good.json"
        good_path.write_bytes(CARD.canonical(
            suite_spec(delivered, explicit_resident=True)))
        good = CARD.COMFORT.P.check_suite(
            "v1.7-phase1b-path-closed-adapter",
            CARD.COMFORT.P._read_suite(str(good_path)))
        require(good["cases"] == 9 and good["functions"] == 4,
                "path-closed adapter did not reach the real suite consumer")

        mutant_path = root / "relative-mutant.json"
        mutant_path.write_bytes(CARD.canonical(
            suite_spec(delivered, explicit_resident=False)))
        try:
            CARD.COMFORT.P.check_suite(
                "v1.7-phase1b-relative-adapter-mutant",
                CARD.COMFORT.P._read_suite(str(mutant_path)))
        except (FileNotFoundError, CARD.COMFORT.P.StdlibCheckError) as error:
            rejected = str(error)
        else:
            raise RuntimeError(
                "relative nested-suite path mutation survived pre-card")
    return {
        "status": "PASS: REAL CONSUMER RESOLVES DECLARING-SUITE PATH",
        "declaring_suite": CARD.bind(CARD.COMFORT.COMFORT_SUITE),
        "resident_suite": CARD.bind(RESIDENT),
        "resolved_path": str(RESIDENT.resolve()),
        "cases": good["cases"],
        "functions": good["functions"],
        "mutation": {
            "name": "omit-explicit-resident-suite-binding",
            "rejected": rejected,
        },
    }


def configuration_gate() -> dict[str, Any]:
    value = ORIGINAL_CONFIGURATION_GATE()
    return {**value, "library_adapter_closure": adapter_preflight_gate()}


def compile_product_profile_library(profile: dict[str, Any]) -> dict[str, Any]:
    LIBRARY.parent.mkdir(parents=True, exist_ok=True)
    LIBRARY_SUITE.write_bytes(CARD.canonical(suite_spec(
        profile["delivered_ids"], explicit_resident=True)))
    process = CARD.subprocess.run([
        sys.executable, "tools/host-lisp/bytecode_p0_stdlib.py", "--check",
        "--artifact-role", "disk-lib", "--emit-artifacts",
        str(LIBRARY.relative_to(ROOT)), "--observation-report",
        str(LIBRARY_OBSERVATIONS.relative_to(ROOT)),
        str(LIBRARY_SUITE.relative_to(ROOT)),
    ], cwd=ROOT, text=True, stdout=CARD.subprocess.PIPE,
        stderr=CARD.subprocess.STDOUT)
    require(process.returncode == 0,
            "path-closed product-profile Comfort artifact red:\n" + process.stdout)
    manifest_path = LIBRARY.with_suffix(".manifest.json")
    manifest = CARD.load(manifest_path)
    require(manifest.get("functions")
                == ["%repl-read", "%repl-prompt", "%repl-step", "repl"]
            and manifest.get("objects") == 4
            and manifest.get("code_bytes") > 0
            and manifest["cost"]["largest_code_object_bytes"] <= 255,
            "path-closed product-profile artifact identity/ceiling red")
    return {
        "adapter_closure": adapter_preflight_gate(),
        "suite": CARD.bind(LIBRARY_SUITE),
        "manifest": CARD.bind(manifest_path),
        "blob": CARD.bind(LIBRARY.with_suffix(".blob.bin")),
        "directory": CARD.bind(LIBRARY.with_suffix(".dir.bin")),
        "observations": CARD.bind(LIBRARY_OBSERVATIONS),
        "objects": manifest["objects"],
        "code_bytes": manifest["code_bytes"],
        "largest_code_object_bytes": manifest["cost"]["largest_code_object_bytes"],
        "delivered_callprims": profile["delivered_ids"],
    }


def configure() -> None:
    CARD.BUILD = BUILD
    CARD.PREFLIGHT = PREFLIGHT
    CARD.RECEIPT = RECEIPT
    CARD.ELF = ELF
    CARD.LIBRARY = LIBRARY
    CARD.LIBRARY_SUITE = LIBRARY_SUITE
    CARD.LIBRARY_OBSERVATIONS = LIBRARY_OBSERVATIONS
    CARD.AUTHORIZATION = AUTHORIZATION
    CARD.FORMAT = FORMAT
    CARD.STATUS = STATUS
    CARD.DRIVER = DRIVER
    CARD.configuration_gate = configuration_gate
    CARD.compile_product_profile_library = compile_product_profile_library
    CARD.configure()


def check() -> None:
    configure()
    CARD.check()
    value = CARD.load(RECEIPT)
    closure = value["final_product"]["phase1b"]["library"]["adapter_closure"]
    require(value["status"] == STATUS
            and closure["status"]
                == "PASS: REAL CONSUMER RESOLVES DECLARING-SUITE PATH"
            and closure["cases"] == 9
            and closure["functions"] == 4,
            "replacement adapter receipt drift")
    print("v1.7 Comfort Phase 1b adapter replacement: CHECK PASS")


def qualification_check() -> None:
    configure()
    CARD.PRICING.check_implemented_successor()
    host = CARD.COMFORT.run_selftest()
    display = CARD.DISPLAY.check()
    red = CARD.load(FIRST_RED)
    value = CARD.load(RECEIPT)
    phase = value["final_product"]["phase1b"]
    hybrid = value["final_product"]["hybrid"]
    require(red["status"]
                == "FIRST RED: GENERATED SUITE ADAPTER LOST DECLARING-SUITE BASE"
            and red["classification"]["family"]
                == "path-bound adapter projection"
            and red["attempt_accounting"]["WPLTO_runs"] == 1
            and red["attempt_accounting"]["product_links"] == 1
            and value["status"] == STATUS
            and value["authority"] == CARD.authority()
            and value["attempt_accounting"] == {
                "WPLTO_runs": 1, "product_links": 1, "scope_runs": 1,
                "acceptance_runs": 1, "media_builds": 0,
                "device_contacts": 0}
            and phase["status"]
                == "PASS: VARIANT B COMFORT SET PROVED ON FINAL PRODUCT WORLD"
            and phase["library"]["adapter_closure"]["cases"] == 9
            and phase["library"]["adapter_closure"]["functions"] == 4
            and phase["capacity"]["bias_adjusted_free"]
                == {"symbol_slots": 32, "namepool_bytes": 581}
            and phase["product_callprim_profile"]["tombstoned_ids"]
                == [1, 2, 12, 26, 27, 40]
            and 12 not in phase["library"]["delivered_callprims"]
            and hybrid["loss"]["linked_events_drained"] == 94
            and hybrid["loss"]["linked_dropped"] == 0
            and hybrid["normalization"]["executions"] == 512
            and hybrid["responsiveness"]["margin_percent"] >= 25.0
            and host["pricing"]["bias_adjusted_free"]
                == {"symbol_slots": 32, "namepool_bytes": 581}
            and display["composed_framebuffer"]["result_tail_blank"] is True,
            "Phase 1b tracked qualification drift")
    print("v1.7 Comfort Phase 1b: QUALIFICATION PASS tracked-final-world")


def run(action: str) -> None:
    configure()
    {
        "preflight": CARD.BASE.preflight,
        "build": CARD.BASE.build,
        "check": check,
        "qualification-check": qualification_check,
        "_produce": CARD.BASE.produce_child,
        "_scope": CARD.BASE.scope_child,
        "_accept": CARD.BASE.acceptance_child,
    }[action]()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "preflight", "build", "check", "qualification-check",
        "_produce", "_scope", "_accept"))
    run(parser.parse_args().action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.7 Comfort Phase 1b adapter replacement: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
