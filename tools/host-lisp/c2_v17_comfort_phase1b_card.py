#!/usr/bin/env python3
"""Build the owner-opened v1.7 Comfort Phase 1b Variant-B product world."""

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

import c2_product_callprim_delivery_gate as DELIVERY  # noqa: E402
import c2_v160_clean_product_candidate as BASE  # noqa: E402
import c2_v160_comfort_repl as COMFORT  # noqa: E402
import c2_v160_display_ownership as DISPLAY  # noqa: E402
import c2_v17_comfort_phase1b_pricing as PRICING  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
BUILD = ROOT / "build/c2.3/v1.7-comfort-phase1b-variant-b-card"
PREFLIGHT = ROOT / "build/c2.3/v1.7-comfort-phase1b-variant-b-preflight"
RECEIPT = ARCH / "c2.3-v1.7-comfort-phase1b-variant-b-card-receipt.json"
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
LIBRARY = BUILD / "library/repl-comfort"
LIBRARY_SUITE = BUILD / "library/product-profile-suite.json"
LIBRARY_OBSERVATIONS = BUILD / "library/observations.json"
IMPLEMENTATION = ROOT / "config/c2-v17-comfort-phase1b-implementation-contract.json"
PRICING_RECEIPT = ARCH / "c2.3-v1.7-comfort-phase1b-pricing-receipt.json"
AUTHORIZATION = "65c3b76d"
FORMAT = "lisp65-c2-v17-comfort-phase1b-variant-b-card-v1"
STATUS = "PASS: V1.7 COMFORT PHASE 1B VARIANT B FINAL GREEN"
DRIVER = Path(__file__).resolve()

ORIGINAL_CONFIGURATION_GATE = BASE.configuration_gate
ORIGINAL_FINAL_GATE = BASE.final_gate


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{AUTHORIZATION}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE,
    ).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in (
        "freigegeben. variant b is the implementation ground",
        "comfort freight as one set",
        "any additional named helper is a new price event",
        "host-only through scope and acceptance",
        "emits no medium and opens no device contact",
    ):
        require(token in text, f"Phase 1b authority absent: {token}")
    return {"authority": "git-blob", "commit": AUTHORIZATION, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def configuration_gate() -> dict[str, Any]:
    PRICING.check_implemented_successor()
    host = COMFORT.run_selftest()
    display = DISPLAY.derive()
    product = ORIGINAL_CONFIGURATION_GATE()
    features = product["features"]
    registries = [row["registry"] for row in product["active_registries"]]
    require(BASE.PRODUCT.INPUT_CAPTURE_FEATURE in features
            and BASE.PRODUCT.INPUT_HYBRID_FEATURE in features
            and BASE.PRODUCT.REFILL_WITNESS_FEATURE not in features
            and registries == ["input-fidelity", "product-cold-disk-chain"]
            and host["pricing"]["bias_adjusted_free"]
                == {"symbol_slots": 32, "namepool_bytes": 581}
            and display["status"]
                == "PASS: COMFORT DISPLAY HAS ONE OWNER AND DEFINED HANDOFF",
            "Phase 1b preflight configuration/wall red")
    return {**product, "phase1b": {
        "variant": "B-shipped-fallback",
        "host": host,
        "display": {
            "status": display["status"],
            "composed_framebuffer": display["composed_framebuffer"],
        },
        "capacity": {"bias_adjusted_free": {
            "symbol_slots": 32, "namepool_bytes": 581},
            "minimum": {"symbol_slots": 32, "namepool_bytes": 384}},
        "product_primitive_delta": 0,
        "media_builds": 0,
        "device_contacts": 0,
    }}


def compile_product_profile_library(profile: dict[str, Any]) -> dict[str, Any]:
    LIBRARY.parent.mkdir(parents=True, exist_ok=True)
    LIBRARY_SUITE.write_bytes(canonical({
        "extends": str(COMFORT.COMFORT_SUITE.resolve()),
        "delivered_callprims": profile["delivered_ids"],
    }))
    process = subprocess.run([
        sys.executable, "tools/host-lisp/bytecode_p0_stdlib.py", "--check",
        "--artifact-role", "disk-lib", "--emit-artifacts",
        str(LIBRARY.relative_to(ROOT)), "--observation-report",
        str(LIBRARY_OBSERVATIONS.relative_to(ROOT)),
        str(LIBRARY_SUITE.relative_to(ROOT)),
    ], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(process.returncode == 0,
            "product-profile Comfort artifact red:\n" + process.stdout)
    manifest_path = LIBRARY.with_suffix(".manifest.json")
    manifest = load(manifest_path)
    require(manifest.get("functions")
                == ["%repl-read", "%repl-prompt", "%repl-step", "repl"]
            and manifest.get("objects") == 4
            and manifest.get("code_bytes") > 0
            and manifest["cost"]["largest_code_object_bytes"] <= 255,
            "product-profile Comfort artifact identity/ceiling red")
    return {
        "suite": bind(LIBRARY_SUITE),
        "manifest": bind(manifest_path),
        "blob": bind(LIBRARY.with_suffix(".blob.bin")),
        "directory": bind(LIBRARY.with_suffix(".dir.bin")),
        "observations": bind(LIBRARY_OBSERVATIONS),
        "objects": manifest["objects"],
        "code_bytes": manifest["code_bytes"],
        "largest_code_object_bytes": manifest["cost"]["largest_code_object_bytes"],
        "delivered_callprims": profile["delivered_ids"],
    }


def final_gate() -> dict[str, Any]:
    product = ORIGINAL_FINAL_GATE()
    profile = DELIVERY.derive_profile(ELF)
    require(profile["tombstoned_ids"] == [1, 2, 12, 26, 27, 40]
            and 12 not in profile["delivered_ids"],
            "final product unexpectedly delivers CALLPRIM 12")
    library = compile_product_profile_library(profile)
    pricing = load(PRICING_RECEIPT)["variants"]["B_shipped_fallback"]
    responsiveness = pricing["responsiveness"]
    hybrid = product["hybrid"]
    require(hybrid["loss"]["linked_events_drained"] == 94
            and hybrid["loss"]["linked_dropped"] == 0
            and hybrid["normalization"]["executions"] == 512
            and hybrid["normalization"]["parity"] is True
            and hybrid["responsiveness"]["frames_per_character"] <= 0.8
            and hybrid["responsiveness"]["service_events_per_frame"] >= 1.25
            and hybrid["responsiveness"]["margin_percent"] >= 25.0
            and responsiveness["stationary_frames_per_character"] <= 0.8
            and responsiveness["stationary_service_events_per_frame"] >= 1.25
            and responsiveness["stationary_margin_percent"] >= 25.0
            and product["display"]["result_tail_blank"] is True,
            "Phase 1b final loss/responsiveness/normalization/display wall red")
    return {**product, "phase1b": {
        "status": "PASS: VARIANT B COMFORT SET PROVED ON FINAL PRODUCT WORLD",
        "product_callprim_profile": profile,
        "library": library,
        "capacity": {
            "bias_adjusted_free": {"symbol_slots": 32,
                                    "namepool_bytes": 581},
            "minimum": {"symbol_slots": 32, "namepool_bytes": 384},
            "slot_margin": 0,
            "namepool_margin_bytes": 197,
        },
        "fallback_responsiveness": responsiveness,
        "claims": {
            "balanced_history_cursor_cases": 9,
            "loss": "94/94 ordered, zero dropped",
            "normalization": "512/512 final-linked consumer executions",
            "display": "one owner and defined handoff",
            "claim_world": "final linked ELF plus product-profile library artifact",
        },
        "media_builds": 0,
        "device_contacts": 0,
    }}


def configure() -> None:
    BASE.BUILD = BUILD
    BASE.PREFLIGHT = PREFLIGHT
    BASE.PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
    BASE.INVOCATION = PREFLIGHT / "candidate-invocation.json"
    BASE.ELF = ELF
    BASE.PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
    BASE.PROFILE = BUILD / "wplto/resolved-profile.txt"
    BASE.PRODUCER_RESULT = BUILD / "producer-result.json"
    BASE.SCOPE_RESULT = BUILD / "owner-scope-result.json"
    BASE.ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
    BASE.RECEIPT = RECEIPT
    BASE.DRIVER = DRIVER
    BASE.AUTHORIZATION = AUTHORIZATION
    BASE.FORMAT = FORMAT
    BASE.STATUS = STATUS
    BASE.authority = authority
    BASE.configuration_gate = configuration_gate
    BASE.final_gate = final_gate


def preflight() -> None:
    configure()
    BASE.preflight()
    print("v1.7 Comfort Phase 1b: PREFLIGHT PASS card=0/1")


def build() -> None:
    configure()
    BASE.build()
    print("v1.7 Comfort Phase 1b: BUILD PASS WPLTO=1 link=1")


def check() -> None:
    configure()
    BASE.check()
    value = load(RECEIPT)
    phase = value["final_product"]["phase1b"]
    for key in ("suite", "manifest", "blob", "directory", "observations"):
        require(phase["library"][key]
                == bind(ROOT / phase["library"][key]["path"]),
                f"Phase 1b library {key} drift")
    require(value["status"] == STATUS
            and phase["status"]
                == "PASS: VARIANT B COMFORT SET PROVED ON FINAL PRODUCT WORLD"
            and phase["capacity"]["bias_adjusted_free"]
                == {"symbol_slots": 32, "namepool_bytes": 581}
            and value["attempt_accounting"] == {
                "WPLTO_runs": 1, "product_links": 1, "scope_runs": 1,
                "acceptance_runs": 1, "media_builds": 0,
                "device_contacts": 0},
            "Phase 1b final receipt drift")
    print("v1.7 Comfort Phase 1b: CHECK PASS final-world=green media=0 device=0")


def run(action: str) -> None:
    configure()
    {
        "preflight": BASE.preflight,
        "build": BASE.build,
        "check": check,
        "_produce": BASE.produce_child,
        "_scope": BASE.scope_child,
        "_accept": BASE.acceptance_child,
    }[action]()


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
        print(f"v1.7 Comfort Phase 1b: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
