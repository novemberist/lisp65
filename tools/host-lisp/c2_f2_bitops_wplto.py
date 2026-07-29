#!/usr/bin/env python3
"""Qualify the combined F1+F2 candidate with one product-shaped WPLTO."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_bitops_gate as F2  # noqa: E402
import c2_f1_published_value_call_wplto as F1W  # noqa: E402
import c2_top_level_published_value_call_gate as F1  # noqa: E402


BASE = ROOT / "build/post-promotion/f2"
PRODUCT = BASE / "product"
V6 = BASE / "v6-semantics"
BUILD = BASE / "product-shaped"
WPLTO = BUILD / "wplto"
RECEIPTS = BUILD / "receipts"
STATIC_RECEIPT = RECEIPTS / "f2-static-plane-authority.json"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / "c2.2-f2-bitops-wplto-receipt.json"
EXPECTED_STATIC = 34990
EXPECTED_ENTRIES = 602
EXPECTED_RESOLUTIONS = 2299
EXPECTED_ROOTS = 283
SPECS = (
    ("stdlib-p0", "stdlib", BASE / "stdlib-p0.manifest.json"),
    ("ide", "ide", F1W.CAN.STATIC / "libs/ide.manifest.json"),
    ("idex", "idex", F1W.CAN.STATIC / "libs/idex.manifest.json"),
    ("m65d", "m65d", F1W.CAN.STATIC / "libs/m65d.manifest.json"),
    ("buffer", "buffer",
     ROOT / "build/bytecode/dialect-v2/libs/buffer.manifest.json"),
    ("lcc", "lcc", BASE / "lcc.manifest.json"),
)


class ProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"F2 artifact absent: {path}")
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

    def f2_bank2_fixture_product() -> dict[str, Any]:
        artifacts = {
            "c2d": bind(V6 / "initial.c2d-v6.bin"),
            "code": bind(V6 / "bank2-static-code.bin"),
            "shelf": bind(PRODUCT / "product-shelf-v4-direct.bin"),
        }
        require(
            artifacts["c2d"]["bytes"] == 33840
            and artifacts["code"]["bytes"] == EXPECTED_STATIC
            and artifacts["shelf"]["bytes"] == 72236,
            "F2 Bank-2 fixture geometry drift",
        )
        return {"host_c2d_v6": {"artifacts": artifacts}}

    F1W.CAN.fresh_bank2_fixture_product = f2_bank2_fixture_product


def emission_gate() -> dict[str, Any]:
    product = load(PRODUCT / "substitution-artifacts.json")
    stdlib = load(BASE / "stdlib-p0.manifest.json")
    lcc = load(BASE / "lcc.manifest.json")
    require(
        product["product_build_id_hex"] == "0x864a4d53"
        and product["images"] == 6
        and product["entries"] == EXPECTED_ENTRIES
        and product["resolutions"] == EXPECTED_RESOLUTIONS
        and product["roots"] == EXPECTED_ROOTS
        and stdlib["code_bytes"] == 8576
        and lcc["code_bytes"] == 7569
        and (V6 / "bank2-static-code.bin").stat().st_size == EXPECTED_STATIC,
        "F2 single-emitter geometry drift",
    )
    return {
        "status": "passed-F1-plus-F2-single-emitter-geometry",
        "product_build_id": product["product_build_id_hex"],
        "images": product["images"],
        "entries": product["entries"],
        "resolutions": product["resolutions"],
        "roots": product["roots"],
        "bank2_static_code_bytes": EXPECTED_STATIC,
        "stdlib_code_bytes": stdlib["code_bytes"],
        "lcc_code_bytes": lcc["code_bytes"],
        "shelf_bytes": product["artifacts"]["shelf"]["bytes"],
        "bindings": {
            "stdlib": bind(BASE / "stdlib-p0.manifest.json"),
            "lcc": bind(BASE / "lcc.manifest.json"),
            "product": bind(PRODUCT / "substitution-artifacts.json"),
            "bank2": bind(V6 / "bank2-static-code.bin"),
        },
    }


def main() -> int:
    try:
        replay = sys.argv[1:] == ["--replay-existing"]
        require(
            (replay and BUILD.is_dir() and RECEIPT.is_file())
            or (not replay and not BUILD.exists() and not RECEIPT.exists()),
            "F2 WPLTO is one-shot; only --replay-existing may qualify its "
            "already linked artifacts",
        )
        f1_source = F1.validate_source(F1.bundle())
        f1_source["mutations_rejected"] = F1.mutation_tests(F1.bundle())
        f1_execution = F1.executable_fixtures()
        f2_bundle = F2.bundle()
        f2_source = F2.validate(f2_bundle)
        f2_source["mutations_rejected"] = F2.mutation_tests(f2_bundle)
        f2_execution = F2.executable_fixtures()
        emission = emission_gate()
        configure()
        if replay:
            prior = load(RECEIPT)
            plane = prior["static_plane_gate"]
            wplto = prior["wplto"]
        else:
            BUILD.mkdir(parents=True)
            plane = F1W.static_gate()
            wplto = F1W.CAN.run_wplto()
        replacement = wplto["historical_checker_boundary"][
            "current_replacement_gates"]
        walls = replacement["walls"]
        capacity = replacement["capacity"]
        require(
            wplto["status"].startswith("passed-")
            and walls["bank0_text_headroom_bytes"] >= 32
            and walls["e000_headroom_bytes"] >= 54
            and walls["fixed_hot_block_headroom_bytes"] >= 0
            and walls["ordinary_bank0_bss_headroom_bytes"] >= 0
            and walls["resident_island_headroom_bytes"] >= 0
            and capacity["session_family_headroom_bytes"] == 610,
            "F2 WPLTO crossed a bound wall",
        )
        value = {
            "format": "lisp65-c2-f2-bitops-WPLTO-v1",
            "recorded_on": "2026-07-27",
            "status": "passed-F1-plus-F2-product-shaped-WPLTO",
            "promotable": False,
            "hardware_runs": 0,
            "qualification_mode": (
                "read-only-existing-WPLTO-artifacts" if replay
                else "one-new-WPLTO"
            ),
            "F1": {
                "source_gate": f1_source,
                "execution_gate": f1_execution,
            },
            "F2": {
                "source_gate": f2_source,
                "execution_gate": f2_execution,
                "emission_gate": emission,
            },
            "static_plane_gate": plane,
            "freight": {
                "bank2_static_code_F1_bytes": 34748,
                "bank2_static_code_F2_bytes": EXPECTED_STATIC,
                "bank2_delta_bytes": EXPECTED_STATIC - 34748,
                "stdlib_delta_bytes": 44,
                "lcc_delta_bytes": 198,
                "entries_delta": 6,
                "resolutions_delta": 16,
                "roots_delta": 0,
                "resident_state_delta_bytes": 0,
            },
            "walls": walls,
            "capacity": capacity,
            "wplto": wplto,
            "authority": {
                "F1_contract": bind(F1.CONTRACT),
                "F2_contract": bind(F2.CONTRACT),
                "F2_contract_note": bind(
                    ROOT / "docs/planning/c2.2-f2-bitops-contract.md"),
                "ABI_ledger": bind(F2.LEDGER),
                "live_ABI": bind(F2.ABI_DOC),
                "VM_header": bind(F2.VM_H),
                "VM_source": bind(F2.VM_C),
                "Python_model": bind(F2.MODEL),
                "Python_compiler": bind(F2.COMPILER),
                "v2_LCC": bind(F2.LCC),
                "public_wrappers": bind(F2.PUBLIC),
                "gate": bind(Path(F2.__file__)),
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
            "c2-f2-bitops-wplto: PASS "
            f"bank2={EXPECTED_STATIC} delta=+{EXPECTED_STATIC - 34748} "
            f"text={walls['bank0_text_headroom_bytes']} "
            f"e000={walls['e000_headroom_bytes']} "
            f"island={walls['resident_island_headroom_bytes']} "
            f"session={capacity['session_family_headroom_bytes']}"
        )
    except (OSError, ValueError, KeyError, ProbeError,
            F1W.ProbeError, F2.GateError) as exc:
        print(f"c2-f2-bitops-wplto: FIRST RED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
