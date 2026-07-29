#!/usr/bin/env python3
"""Qualify F1+F2+F3 with one product-shaped WPLTO and zero resident debit."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_f1_published_value_call_wplto as F1W  # noqa: E402
import c2_f2_bitops_wplto as F2W  # noqa: E402
import c2_state_error_carrier_gate as F3  # noqa: E402


BASE = ROOT / "build/post-promotion/f3"
PRODUCT = BASE / "product"
V6 = BASE / "v6-semantics"
BUILD = BASE / "product-shaped"
WPLTO = BUILD / "wplto"
RECEIPTS = BUILD / "receipts"
STATIC_RECEIPT = RECEIPTS / "f3-static-plane-authority.json"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / "c2.2-f3-state-error-wplto-receipt.json"
EXPECTED_STATIC = 35037
EXPECTED_ENTRIES = 605
EXPECTED_RESOLUTIONS = 2299
EXPECTED_ROOTS = 283
F2_WALLS = {
    "bank0_text_headroom_bytes": 90,
    "e000_headroom_bytes": 151,
    "fixed_hot_block_headroom_bytes": 2,
    "ordinary_bank0_bss_headroom_bytes": 137,
    "resident_island_headroom_bytes": 69,
}
SPECS = (
    ("stdlib-p0", "stdlib", BASE / "stdlib-p0.manifest.json"),
    ("ide", "ide", F1W.CAN.STATIC / "libs/ide.manifest.json"),
    ("idex", "idex", F1W.CAN.STATIC / "libs/idex.manifest.json"),
    ("m65d", "m65d", F1W.CAN.STATIC / "libs/m65d.manifest.json"),
    ("buffer", "buffer",
     ROOT / "build/bytecode/dialect-v2/libs/buffer.manifest.json"),
    ("lcc", "lcc", ROOT / "build/post-promotion/f2/lcc.manifest.json"),
)


class ProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"F3 artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def configure() -> None:
    F1W.BASE = BASE
    F1W.STATIC_PRODUCT = PRODUCT
    F1W.V6 = V6
    F1W.BUILD = BUILD
    F1W.WPLTO = WPLTO
    F1W.RECEIPTS = RECEIPTS
    F1W.STATIC_RECEIPT = STATIC_RECEIPT
    F1W.EXPECTED_STATIC = EXPECTED_STATIC
    F1W.EXPECTED_ENTRIES = EXPECTED_ENTRIES
    F1W.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    F1W.EXPECTED_ROOTS = EXPECTED_ROOTS
    F1W.SPECS = SPECS
    F1W.configure()

    def f3_bank2_fixture_product() -> dict[str, Any]:
        artifacts = {
            "c2d": bind(V6 / "initial.c2d-v6.bin"),
            "code": bind(V6 / "bank2-static-code.bin"),
            "shelf": bind(PRODUCT / "product-shelf-v4-direct.bin"),
        }
        require(
            artifacts["c2d"]["bytes"] == 33840
            and artifacts["code"]["bytes"] == EXPECTED_STATIC
            and artifacts["shelf"]["bytes"] == 72347,
            "F3 Bank-2 fixture geometry drift",
        )
        return {"host_c2d_v6": {"artifacts": artifacts}}

    F1W.CAN.fresh_bank2_fixture_product = f3_bank2_fixture_product


def emission_gate() -> dict[str, Any]:
    product = load(PRODUCT / "substitution-artifacts.json")
    stdlib = load(BASE / "stdlib-p0.manifest.json")
    require(
        product["product_build_id_hex"] == "0xf474a998"
        and product["images"] == 6
        and product["entries"] == EXPECTED_ENTRIES
        and product["resolutions"] == EXPECTED_RESOLUTIONS
        and product["roots"] == EXPECTED_ROOTS
        and stdlib["code_bytes"] == 8623
        and (V6 / "bank2-static-code.bin").stat().st_size == EXPECTED_STATIC,
        "F3 single-emitter geometry drift",
    )
    return {
        "status": "passed-F1-plus-F2-plus-F3-single-emitter-geometry",
        "product_build_id": product["product_build_id_hex"],
        "images": product["images"],
        "entries": product["entries"],
        "resolutions": product["resolutions"],
        "roots": product["roots"],
        "bank2_static_code_bytes": EXPECTED_STATIC,
        "stdlib_code_bytes": stdlib["code_bytes"],
        "shelf_bytes": product["artifacts"]["shelf"]["bytes"],
        "bindings": {
            "stdlib": bind(BASE / "stdlib-p0.manifest.json"),
            "product": bind(PRODUCT / "substitution-artifacts.json"),
            "bank2": bind(V6 / "bank2-static-code.bin"),
        },
    }


def main() -> int:
    try:
        require(not BUILD.exists() and not RECEIPT.exists(),
                "F3 WPLTO is one-shot")
        source_bundle = F3.bundle()
        source = F3.validate(source_bundle)
        source["mutations_rejected"] = F3.mutation_tests(source_bundle)
        execution = F3.executable_fixtures()
        emission = emission_gate()
        configure()
        BUILD.mkdir(parents=True)
        plane = F1W.static_gate()
        wplto = F1W.CAN.run_wplto()
        replacement = wplto["historical_checker_boundary"][
            "current_replacement_gates"]
        walls = replacement["walls"]
        capacity = replacement["capacity"]
        require(wplto["status"].startswith("passed-"),
                "F3 WPLTO did not complete")
        require(
            all(walls[key] == expected
                for key, expected in F2_WALLS.items()),
            "F3 incurred resident demand; park the trio at halt number 2: "
            f"F2={F2_WALLS} F3={walls}",
        )
        require(capacity["session_family_headroom_bytes"] >= 0,
                "F3 session aggregate crossed its bound")
        overlay = load(WPLTO / "runtime-overlays-session-unbound.json")
        slices = {row["name"]: row for row in overlay["slices"]}
        l65e = slices["error-text-renderer"]
        buffer_read = slices["first-class-buffer-read"]
        require(
            l65e["file_size"] <= 1320
            and buffer_read["file_size"] <= 1792,
            "F3 cold carrier crossed a slice cap",
        )
        value = {
            "format": "lisp65-c2-f3-state-error-WPLTO-v1",
            "recorded_on": "2026-07-27",
            "status":
                "passed-F1-plus-F2-plus-F3-product-shaped-WPLTO",
            "promotable": False,
            "hardware_runs": 0,
            "qualification_mode": "one-new-WPLTO",
            "F3": {
                "source_gate": source,
                "execution_gate": execution,
                "emission_gate": emission,
                "resident_baseline": F2_WALLS,
                "resident_candidate": walls,
                "resident_demand_bytes": 0,
                "cold_slices": {
                    "buffer_read": buffer_read,
                    "l65e": l65e,
                },
            },
            "static_plane_gate": plane,
            "freight": {
                "bank2_static_code_F2_bytes": 34990,
                "bank2_static_code_F3_bytes": EXPECTED_STATIC,
                "bank2_delta_bytes": EXPECTED_STATIC - 34990,
                "stdlib_delta_bytes": 47,
                "entries_delta": 3,
                "resolutions_delta": 0,
                "roots_delta": 0,
                "resident_code_delta_bytes": 0,
                "resident_state_delta_bytes": 0,
            },
            "walls": walls,
            "capacity": capacity,
            "wplto": wplto,
            "authority": {
                "contract": bind(F3.CONTRACT),
                "contract_note": bind(
                    ROOT / "docs/planning/"
                    "c2.2-f3-state-error-carrier-contract.md"),
                "public_wrappers": bind(F3.PUBLIC),
                "buffer_header": bind(F3.BUFFER_H),
                "buffer_overlay": bind(F3.BUFFER_C),
                "error_header": bind(F3.ERROR_H),
                "error_overlay": bind(F3.ERROR_C),
                "error_leaf": bind(F3.ERROR_ASM),
                "error_table": bind(F3.ERROR_TABLE),
                "gate": bind(Path(F3.__file__)),
                "profile": bind(F1W.CAN.PROFILE),
                "static_header": bind(F1W.PLANE.HEADER),
                "linked_ELF": bind(
                    WPLTO / "lisp65-c2-substitution-linked.prg.elf"),
                "linked_map": bind(
                    WPLTO / "lisp65-c2-substitution-linked.prg.map"),
            },
        }
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        print(
            "c2-f3-state-error-wplto: PASS "
            f"bank2={EXPECTED_STATIC} delta=+{EXPECTED_STATIC - 34990} "
            f"text={walls['bank0_text_headroom_bytes']} "
            f"e000={walls['e000_headroom_bytes']} "
            f"buffer={buffer_read['file_size']} l65e={l65e['file_size']} "
            f"session={capacity['session_family_headroom_bytes']}"
        )
    except (OSError, ValueError, KeyError, ProbeError,
            F1W.ProbeError, F3.GateError) as exc:
        print(f"c2-f3-state-error-wplto: FIRST RED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
