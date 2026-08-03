#!/usr/bin/env python3
"""Rebind the accepted Bank-2 read-line card to the regular v1.3 banner.

The accepted WPLTO established native geometry.  The regular-release banner
changes bytes only in the static Lisp plane, so this step emits that plane
again without invoking the target linker and records the exact byte delta.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import c2_v13_bank2_read_line_wplto as CARD  # noqa: E402


JOINT = CARD.JOINT
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PREFLIGHT = ROOT / "build/ship-builder/v13/banner-identity-rebind-preflight-v2"
RECEIPT = EVIDENCE / "c2.3-v1.3-banner-identity-rebind-receipt.json"
OLD_BANK2 = (
    CARD.PREFLIGHT / "static-plane/narrow-static/v6-semantics/"
    "bank2-static-code.bin"
)
OLD_STDLIB_C2I = (
    CARD.PREFLIGHT / "static-plane/narrow-static/product/stdlib-p0.c2i.bin"
)
PROFILE = ROOT / "config/c2-l-full-product-profile.json"
STATIC_HEADER = ROOT / "src/c2_lite_static_plane.h"
EXECUTION = ROOT / "config/c2-lite-execution-contract.json"
BANNER_AUTHORITY = ROOT / "config/v12-known-issues.json"
BANNER_SOURCE = ROOT / "lib/repl-banner.lisp"
DRIVER = Path(__file__).resolve()


class RebindError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RebindError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def run(command: list[str], label: str) -> str:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False,
    )
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout.strip().splitlines()[-1]


def main() -> int:
    require(not PREFLIGHT.exists() and not RECEIPT.exists(),
            "v1.3 banner identity rebind is one-shot")
    card = load(CARD.RECEIPT)
    old_profile = load(CARD.PROFILE_RECEIPT)
    require(
        card["status"] == "passed-v1.3-joint-one-product-shaped-WPLTO"
        and card["inherited_native_geometry"] == {
            "fixed_host_facade": card["inherited_native_geometry"][
                "fixed_host_facade"],
            "noinit_address": "0xc34d",
            "noinit_bytes": 6,
            "overlay_floor": "0xc354",
            "status": "restored-exactly",
        }
        and old_profile["geometry"]["bank2_static_code_bytes"]
            == CARD.EXPECTED_STATIC,
        "accepted Bank-2 card authority drift",
    )
    banner = load(BANNER_AUTHORITY)
    require(
        banner["release"] == banner["product_banner_release"] == "1.3.0"
        and '"WORKBENCH 1.3.0"' in BANNER_SOURCE.read_text(encoding="utf-8"),
        "regular v1.3 banner is not bound",
    )
    gates = {
        "workbench_suite": run(
            [sys.executable, "tools/host-lisp/v11_c1_lease_codemod.py"],
            "v1.3 current-source Workbench suite generation",
        ),
        "banner": run(
            [sys.executable,
             "tools/host-lisp/c2_repl_banner_version_gate.py", "--selftest"],
            "v1.3 banner gate",
        ),
        "input_wait": run(
            [sys.executable, "tools/host-lisp/c2_ship_input_wait_gate.py"],
            "v1.3 current-banner input/wait execution gate",
        ),
    }
    CARD.PREFLIGHT = PREFLIGHT
    CARD.configure()
    plane = JOINT.emit_plane()
    product = plane["product"]
    old_bytes = OLD_BANK2.read_bytes()
    new_path = (
        PREFLIGHT / "static-plane/narrow-static/v6-semantics/"
        "bank2-static-code.bin"
    )
    new_bytes = new_path.read_bytes()
    require(len(old_bytes) == len(new_bytes) == CARD.EXPECTED_STATIC,
            "banner rebind changed Bank-2 geometry")
    require(old_bytes == new_bytes,
            "regular banner changed Bank-2 executable code")
    old_c2i = OLD_STDLIB_C2I.read_bytes()
    new_c2i_path = (
        PREFLIGHT / "static-plane/narrow-static/product/stdlib-p0.c2i.bin"
    )
    new_c2i = new_c2i_path.read_bytes()
    require(len(old_c2i) == len(new_c2i),
            "regular banner changed stdlib C2I geometry")
    differences = [
        {"offset": index, "before": before, "after": after}
        for index, (before, after) in enumerate(zip(old_c2i, new_c2i))
        if before != after
    ]
    require(
        len(differences) == 2
        and sorted((row["before"], row["after"]) for row in differences)
            == [(ord("2"), ord("3")), (ord("6"), ord("0"))],
        f"banner C2I byte delta is not exactly 1.2.6 -> 1.3.0: {differences}",
    )
    profile = load(PROFILE)
    profile.update({
        "recorded_on": "2026-08-01",
        "product_build_id": product["product_build_id_hex"],
    })
    profile["authority"].update({
        "kind": "fresh-single-emitter-static-plane-dataflow",
        "identity_rebind": "v1.3-regular-banner-linker-free",
        "product_manifest": (
            "build/ship-builder/v13/banner-identity-rebind-preflight-v2/"
            "static-plane/narrow-static/product/substitution-artifacts.json"
        ),
        "bank2_static_plane": new_path.relative_to(ROOT).as_posix(),
        "rule": (
            "The accepted native WPLTO geometry is retained; the regular "
            "v1.3 banner is re-emitted through the canonical static plane."
        ),
    })
    profile["bank2_static_code"].update({
        "bytes": CARD.EXPECTED_STATIC,
        "sha256": plane["bank2_sha256"],
        "headroom_bytes": 65536 - CARD.EXPECTED_STATIC,
    })
    PROFILE.write_bytes(JOINT.CAN.json_bytes(profile))
    gates["q_post_profile"] = run(
        [sys.executable, "tools/host-lisp/c2_q_gate.py"],
        "post-banner q/profile binding",
    )
    value = {
        "format": "lisp65-c2.3-v1.3-banner-identity-rebind-v1",
        "recorded_on": "2026-08-01",
        "status": "passed-linker-free-regular-v1.3-banner-identity-rebind",
        "promotable": False,
        "target_linker_invocations": 0,
        "additional_wplto_probes": 0,
        "product_links": 0,
        "hardware_runs": 0,
        "banner": {
            "before": "WORKBENCH 1.2.6",
            "after": "WORKBENCH 1.3.0",
            "regular_release_divergence_allowed": False,
        },
        "pre_banner_plane": {
            "product_build_id": old_profile["geometry"]["product_build_id"],
            "bank2_sha256": old_profile["geometry"]["bank2_sha256"],
        },
        "final_plane": {
            "product_build_id": product["product_build_id_hex"],
            "bank2_sha256": plane["bank2_sha256"],
        },
        "geometry": {
            "bank2_static_code_bytes": CARD.EXPECTED_STATIC,
            "bank2_headroom_bytes": 65536 - CARD.EXPECTED_STATIC,
            "entries": CARD.EXPECTED_ENTRIES,
            "resolutions": CARD.EXPECTED_RESOLUTIONS,
            "roots": CARD.EXPECTED_ROOTS,
            "direct_entry_refs": CARD.EXPECTED_DIRECT_REFS,
            "resident_delta_bytes": 0,
        },
        "bank2_delta": {
            "executable_code_differing_bytes": 0,
            "stdlib_c2i_differing_bytes": differences,
            "classification": "banner-C2I-text-only",
        },
        "host_gate_summaries": gates,
        "authority": {
            "accepted_WPLTO": JOINT.bind(CARD.RECEIPT),
            "pre_banner_profile": JOINT.bind(CARD.PROFILE_RECEIPT),
            "banner_authority": JOINT.bind(BANNER_AUTHORITY),
            "banner_source": JOINT.bind(BANNER_SOURCE),
            "current_stdlib_manifest": JOINT.bind(JOINT.INPUT_MANIFEST),
            "current_IDE_manifest": JOINT.bind(JOINT.CURRENT_IDE),
            "final_profile": JOINT.bind(PROFILE),
            "static_header": JOINT.bind(STATIC_HEADER),
            "execution_contract": JOINT.bind(EXECUTION),
            "final_static_product": JOINT.bind(
                PREFLIGHT / "static-plane/narrow-static/product/"
                "substitution-artifacts.json"),
            "driver": JOINT.bind(DRIVER),
        },
        "next_gate": "One Link 84 successor under the final v1.3 identity.",
        "claim_limit": (
            "Linker-free static-plane identity rebind only; the accepted "
            "WPLTO supplies native geometry, but no successor product or "
            "hardware claim is made here."
        ),
    }
    RECEIPT.write_bytes(JOINT.CAN.json_bytes(value))
    print(
        "c2-v13-banner-rebind: PASS "
        f"id={product['product_build_id_hex']} bank2={CARD.EXPECTED_STATIC} "
        f"diff={len(differences)} linker=0"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, KeyError, ValueError, RebindError) as error:
        print(f"c2-v13-banner-rebind: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
