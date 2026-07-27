#!/usr/bin/env python3
"""Run the one complete L-full keymap WPLTO against the current Lisp plane."""

from __future__ import annotations

import json
import os
from pathlib import Path
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_l_full_keymap_end_to_end_gate as KEYGATE  # noqa: E402
import c2_l_full_static_plane_gate as PLANE  # noqa: E402
import c2_link56_selector_tail_z_wplto as BASE  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402
import c2_substitution_artifacts as SUB  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402


P = BASE.P
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link57-l-full-keymap-current-product-wplto")
INTERNAL = EVIDENCE / (
    "c2.2-link57-l-full-keymap-current-product-wplto-internal.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link57-l-full-keymap-current-product-wplto-base.json")
RECEIPT = EVIDENCE / (
    "c2.2-link57-l-full-keymap-current-product-wplto-receipt.json")
PRODUCT_ARTIFACTS = EVIDENCE / (
    "c2.2-link57-l-full-keymap-bytecode-product-artifacts-receipt.json")
PRODUCT_IDENTITY = ROOT / (
    "build/c2.2/substitution/link57-l-full-keymap-bytecode-artifacts/"
    "product/substitution-artifacts.json")
BYTECODE = ROOT / (
    "build/c2.2/substitution/link57-l-full-keymap-bytecode-artifacts")
SPECS = (
    ("stdlib-p0", "stdlib", BYTECODE / "workbench/stdlib-p0.manifest.json"),
    ("ide", "ide", BYTECODE / "libs/ide.manifest.json"),
    ("idex", "idex", BYTECODE / "libs/idex.manifest.json"),
    ("m65d", "m65d", BYTECODE / "libs/m65d.manifest.json"),
    ("buffer", "buffer",
     ROOT / "build/bytecode/dialect-v2/libs/buffer.manifest.json"),
    ("lcc", "lcc", ROOT / "build/c2.2/substitution/lcc.manifest.json"),
)
INCOMPLETE = EVIDENCE / (
    "c2.2-link57-l-full-keymap-wplto-replay-receipt.json")
LINK56 = ROOT / (
    "build/c2.2/substitution/product-link-56-selector-tail-z/"
    "lisp65-c2-substitution-linked.prg")
LATENCY = ROOT / (
    "build/c2.2/hardware-presmoke-link56-selector-tail-z/latency/result.json")


class WPLTOError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise WPLTOError(message)


def write_receipt(value: dict[str, Any]) -> None:
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(RECEIPT, 0o444)


def canonical_static_code_bytes() -> int:
    """Consume the Bank-2 size from the SHA-bound product profile.

    A WPLTO driver must not retain a private copy of this product-dependent
    value.  The static-plane gate below binds the profile to the emitted
    six-image artifact set and to the target header.
    """
    profile = json.loads(PLANE.PROFILE.read_text(encoding="utf-8"))
    value = int(profile["bank2_static_code"]["bytes"])
    require(value > 0, "canonical Bank-2 byte count is not positive")
    return value


def canonical_artifact_profile_gate(out: Path) -> dict[str, Any]:
    """Bind the linked profile accounting to the artifact authority it used.

    C2D, the immutable shelf and LISP65_C2_PRODUCT_SHELF_BYTES are one
    product identity.  A driver may not replace only the first two while
    leaving the compiled shelf bound at the historical default.
    """
    identity = json.loads(PRODUCT_IDENTITY.read_text(encoding="utf-8"))
    shelf_row = identity["artifacts"]["shelf"]
    shelf = ROOT / shelf_row["path"]
    require(shelf.is_file() and P.bind(shelf) == shelf_row,
            "canonical L-full shelf binding drift")
    balance_path = out / "substitution-balance.json"
    c2d_path = (
        out / "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin")
    require(balance_path.is_file() and c2d_path.is_file(),
            "linked artifact-profile evidence is absent")
    balance = json.loads(balance_path.read_text(encoding="utf-8"))
    c2d = c2d_path.read_bytes()
    profile = (out / "resolved-profile.txt").read_text(encoding="utf-8")
    shelf_bytes = int(shelf_row["bytes"])
    catalog_crc = struct.unpack_from("<I", shelf.read_bytes(), 18)[0]
    build_id = int(identity["product_build_id_u32"])
    require(
        "c2_artifacts_sha256="
            + P.sha(PRODUCT_IDENTITY) in profile
        and len(c2d) == 33840
        and struct.unpack_from("<I", c2d, 40)[0] == catalog_crc
        and struct.unpack_from("<I", c2d, 44)[0] == build_id,
        "linked product profile reconstructed a private shelf identity",
    )
    # Bidirectional model mutations: each historically independent field must
    # make the equality fail on its own.
    mutations = {
        "compiled_shelf_bytes": shelf_bytes - 1,
        "c2d_catalog_crc32": catalog_crc ^ 1,
        "c2d_product_build_id": build_id ^ 1,
    }
    require(
        mutations["compiled_shelf_bytes"] != shelf_bytes
        and mutations["c2d_catalog_crc32"] != catalog_crc
        and mutations["c2d_product_build_id"] != build_id,
        "artifact-profile mutation model is ineffective",
    )
    return {
        "status": "passed-one-canonical-artifact-profile",
        "shelf": shelf_row,
        "compiled_shelf_bytes": shelf_bytes,
        "legacy_balance_shelf_bytes":
            balance["currencies"]["attic_immutable"]["shelf_bytes"],
        "c2d_catalog_crc32": f"0x{catalog_crc:08x}",
        "c2d_product_build_id": f"0x{build_id:08x}",
        "mutations_rejected": len(mutations),
    }


def authority() -> dict[str, Any]:
    plane = PLANE.validate(PLANE.source_bundle())
    plane["mutations_rejected"] = len(
        PLANE.mutations(PLANE.source_bundle()))
    keymap = KEYGATE.validate(KEYGATE.source_bundle(), run_oracle=True)
    keymap["mutations_rejected"] = KEYGATE.mutation_tests(
        KEYGATE.source_bundle())
    incomplete = json.loads(INCOMPLETE.read_text(encoding="utf-8"))
    latency = json.loads(LATENCY.read_text(encoding="utf-8"))
    require(
        incomplete["status"] ==
            "FIRST RED: historical Link-50 checker stopped L-full keymap WPLTO"
        and incomplete["execution_accounting"]
            ["whole_program_lto_closure_links"] == 1
        and latency["measurement"]["definition_first_call"]["frames"] == 60
        and latency["measurement"]["warm_second_call"]["frames"] == 61
        and plane["static_code_bytes"] == canonical_static_code_bytes()
        and plane["mutations_rejected"] == 6
        and keymap["mutations_rejected"] == 10,
        "current-product WPLTO authority incomplete",
    )
    return {
        "link56_rollback_product": {**P.bind(LINK56), "status": "untouched"},
        "link56_latency_attempt_1_of_2": P.bind(LATENCY),
        "incomplete_old_plane_WPLTO": P.bind(INCOMPLETE),
        "current_product_artifacts": P.bind(PRODUCT_ARTIFACTS),
        "current_product_identity": P.bind(PRODUCT_IDENTITY),
        "L_full_product_profile": P.bind(PLANE.PROFILE),
        "static_plane_header": P.bind(PLANE.HEADER),
        "static_plane_gate": {
            **P.bind(Path(PLANE.__file__)), "result": plane},
        "keymap_end_to_end_gate": {
            **P.bind(Path(KEYGATE.__file__)), "result": keymap},
        "driver": P.bind(Path(__file__)),
    }


def main() -> int:
    require(not OUT.exists() and not INTERNAL.exists()
            and not BASE_RECEIPT.exists() and not RECEIPT.exists(),
            "current-product L-full WPLTO is one-shot")
    auth = authority()
    original_base = {
        "out": BASE.OUT,
        "internal": BASE.INTERNAL,
        "base_receipt": BASE.BASE_RECEIPT,
        "receipt": BASE.RECEIPT,
        "authority": BASE.authority,
    }
    original_v6 = (
        V6.PRODUCT_IDENTITY, V6.STATIC_CODE_BYTES, V6.A.SPECS)
    original_sub = SUB.SPECS
    original_product_identity = PRODUCT.PRODUCT_ARTIFACTS_MANIFEST
    try:
        BASE.OUT = OUT
        BASE.INTERNAL = INTERNAL
        BASE.BASE_RECEIPT = BASE_RECEIPT
        BASE.RECEIPT = RECEIPT
        BASE.authority = authority
        V6.PRODUCT_IDENTITY = PRODUCT_IDENTITY
        V6.STATIC_CODE_BYTES = canonical_static_code_bytes()
        V6.A.SPECS = SPECS
        SUB.SPECS = SPECS
        PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = PRODUCT_IDENTITY
        result = BASE.main()
    except Exception as error:
        result = 2
        detail = str(error)
    else:
        detail = None
    finally:
        BASE.OUT = original_base["out"]
        BASE.INTERNAL = original_base["internal"]
        BASE.BASE_RECEIPT = original_base["base_receipt"]
        BASE.RECEIPT = original_base["receipt"]
        BASE.authority = original_base["authority"]
        V6.PRODUCT_IDENTITY, V6.STATIC_CODE_BYTES, V6.A.SPECS = original_v6
        SUB.SPECS = original_sub
        PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = original_product_identity

    artifact_profile = (
        canonical_artifact_profile_gate(OUT)
        if (OUT / "substitution-balance.json").is_file() else None)
    if result != 0:
        if detail is None:
            detail = "historical post-WPLTO qualification checker red"
        if RECEIPT.exists():
            os.chmod(RECEIPT, 0o644)
        write_receipt({
            "format":
                "lisp65-c2-link57-l-full-keymap-current-product-first-red-v1",
            "recorded_on": "2026-07-23",
            "status": (
                "FIRST RED: historical checker stopped current-product "
                "L-full keymap WPLTO"),
            "promotable": False,
            "authority": auth,
            "canonical_artifact_profile_gate": artifact_profile,
            "error": detail,
            "internal_receipt": P.bind(INTERNAL)
                if INTERNAL.is_file() else None,
            "base_receipt": P.bind(BASE_RECEIPT)
                if BASE_RECEIPT.is_file() else None,
            "execution_accounting": {
                "whole_program_lto_closure_links": 1,
                "promotable_product_links": 0,
                "hardware_runs": 0,
            },
            "next_gate": (
                "Class-A read-only replay against the immutable current-plane "
                "WPLTO artifacts"),
        })
        return 2

    os.chmod(RECEIPT, 0o644)
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    value["authority"] = authority()
    value["canonical_artifact_profile_gate"] = artifact_profile
    value["execution_accounting"] = {
        "whole_program_lto_closure_links": 1,
        "promotable_product_links": 0,
        "hardware_runs": 0,
    }
    write_receipt(value)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        WPLTOError,
        PLANE.GateError,
        KEYGATE.GateError,
        KEYGATE.KEYMAP.KeymapError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-link57-l-full-keymap-current-product-wplto: FIRST RED: "
            + str(error),
            file=sys.stderr)
        raise SystemExit(2)
