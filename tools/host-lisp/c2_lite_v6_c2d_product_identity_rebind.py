#!/usr/bin/env python3
"""Re-emit the Link-40 C2D-v6 plane with the canonical product identity.

This is an artifact-only Class-C correction.  It does not compile or link a
product, and it leaves the Link-40 PRG/ELF and every executable plane intact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_product_probe as V6  # noqa: E402


OUT = ROOT / "build/c2.2/c2d-v6-product-identity-rebind-link40"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link40-c2d-v6-product-identity-rebind-receipt.json"
)
STRUCTURAL_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link40-c2-lite-v6-real-abi-e000-structural-receipt.json"
)
LINK40 = ROOT / (
    "build/c2.2/substitution/product-link-40-c2-lite-v6-real-abi-e000"
)


class RebindError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RebindError(message)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def bind(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def bound(path: Path, row: dict[str, Any], label: str) -> None:
    require(path.is_file(), f"missing {label}: {path}")
    require(row == bind(path), f"{label} binding drift")


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "C2D-v6 identity rebind output already exists")
    require(STRUCTURAL_RECEIPT.is_file(), "Link-40 structural authority absent")
    structural = json.loads(STRUCTURAL_RECEIPT.read_text(encoding="utf-8"))
    require(structural.get("status") ==
            "passed-new-c2-lite-real-abi-identity-hardware-not-run",
            "Link-40 structural authority is not passed")
    product_row = structural.get("product_identity", {}).get("product", {})
    elf_row = structural.get("product_identity", {}).get("elf", {})
    product = LINK40 / "lisp65-c2-substitution-linked.prg"
    elf = LINK40 / "lisp65-c2-substitution-linked.prg.elf"
    bound(product, product_row, "Link-40 product")
    bound(elf, elf_row, "Link-40 ELF")

    old_host = structural.get("fresh_prelink_gates", {}).get(
        "c2d_v6_host_semantics", {})
    old_c2d_row = old_host.get("artifacts", {}).get("c2d", {})
    old_code_row = old_host.get("artifacts", {}).get("code", {})
    require(isinstance(old_c2d_row.get("path"), str)
            and isinstance(old_code_row.get("path"), str),
            "Link-40 structural receipt lacks C2D plane bindings")
    old_c2d_path = ROOT / old_c2d_row["path"]
    old_code_path = ROOT / old_code_row["path"]
    bound(old_c2d_path, old_c2d_row, "old Link-40 C2D-v6 plane")
    bound(old_code_path, old_code_row, "old Link-40 Bank-2 plane")

    OUT.mkdir(parents=True)
    old_out = V6.OUT
    old_emitter = (V6._ENTRY_EMITTER, V6._ENTRY_EMITTER_PATH)
    try:
        V6.OUT = OUT / "v6-semantics"
        V6.OUT.mkdir()
        V6._ENTRY_EMITTER = None
        V6._ENTRY_EMITTER_PATH = None
        host = V6.host_semantics()
    finally:
        V6.OUT = old_out
        V6._ENTRY_EMITTER, V6._ENTRY_EMITTER_PATH = old_emitter

    new_c2d_path = OUT / "v6-semantics/initial.c2d-v6.bin"
    new_code_path = OUT / "v6-semantics/bank2-static-code.bin"
    old_c2d = old_c2d_path.read_bytes()
    new_c2d = new_c2d_path.read_bytes()
    require(len(old_c2d) == len(new_c2d) == V6.C2D_TOTAL_BYTES,
            "C2D-v6 plane width changed during identity rebind")
    changed = [index for index, pair in enumerate(zip(old_c2d, new_c2d))
               if pair[0] != pair[1]]
    require(changed == [44, 45, 46, 47],
            f"identity rebind changed bytes outside header build ID: {changed}")
    old_id = struct.unpack_from("<I", old_c2d, 44)[0]
    new_id = struct.unpack_from("<I", new_c2d, 44)[0]
    canonical = V6.canonical_product_build_id()
    require(old_id == 0x79616F27 and new_id == canonical == 0x69496476,
            "C2D-v6 identity transition is not the diagnosed Link-40 repair")
    require(new_code_path.read_bytes() == old_code_path.read_bytes(),
            "Bank-2 executable plane changed during C2D identity rebind")
    require(host.get("product_build_identity", {}).get("value_u32") == canonical
            and host.get("product_build_identity", {}).get(
                "private_derivation_sites") == 0,
            "fresh host semantics did not consume the canonical identity")
    fixtures = set(host.get("negative_fixtures", []))
    require({"c2d-product-build-identity-mismatch",
             "c2d-zero-product-build-identity"} <= fixtures,
            "fresh identity negatives did not run")

    value = {
        "format": "lisp65-c2-lite-v6-c2d-product-identity-rebind-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-c2d-v6-canonical-product-identity-hardware-not-run",
        "authority": {
            "link40_structural_receipt": bind(STRUCTURAL_RECEIPT),
            "product_identity": bind(V6.PRODUCT_IDENTITY),
        },
        "execution_accounting": {
            "product_compiler_runs": 0,
            "product_linker_runs": 0,
            "product_links": 0,
            "host_entry_emitter_compiles": 1,
            "hardware_runs": 0,
            "product_bytes_changed": 0,
            "c2d_header_bytes_changed": 4,
        },
        "product_identity": {"product": bind(product), "elf": bind(elf)},
        "corrected_c2d": {
            "status": "passed",
            "old": bind(old_c2d_path),
            "new": bind(new_c2d_path),
            "bank2_static": bind(new_code_path),
            "changed_offsets": changed,
            "old_build_id": f"0x{old_id:08x}",
            "new_build_id": f"0x{new_id:08x}",
            "canonical_authority": bind(V6.PRODUCT_IDENTITY),
            "all_nonidentity_bytes_equal": True,
            "executable_plane_byte_identical": True,
        },
        "fresh_host_semantics": host,
        "presmoke_authorization": {
            "candidate": LINK40.relative_to(ROOT).as_posix(),
            "corrected_c2d_path": new_c2d_path.relative_to(ROOT).as_posix(),
            "link40_prg_unchanged": True,
            "link40_elf_unchanged": True,
        },
        "claim_limit": (
            "Fresh C2D-v6 host semantics and an exact four-byte header identity "
            "rebind only. Link-40 executable bytes are unchanged. Hardware, "
            "latency, promotion and acceptance remain not run."
        ),
        "next_gate": "fresh receipt-less hardware presmoke from line 1",
    }
    write_json(OUT / "c2d-v6-product-identity-rebind.json", value)
    value["report"] = bind(OUT / "c2d-v6-product-identity-rebind.json")
    write_json(RECEIPT, value)
    for path in OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    os.chmod(RECEIPT, 0o444)
    return value


def check() -> dict[str, Any]:
    require(RECEIPT.is_file(), "C2D-v6 identity rebind receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status") ==
            "passed-c2d-v6-canonical-product-identity-hardware-not-run",
            "C2D-v6 identity rebind receipt is not passed")
    for row in (
        value["authority"]["link40_structural_receipt"],
        value["authority"]["product_identity"],
        value["product_identity"]["product"],
        value["product_identity"]["elf"],
        value["corrected_c2d"]["old"],
        value["corrected_c2d"]["new"],
        value["corrected_c2d"]["bank2_static"],
        value["report"],
    ):
        bound(ROOT / row["path"], row, "rebind evidence")
    require(struct.unpack_from(
        "<I", (ROOT / value["corrected_c2d"]["new"]["path"]).read_bytes(), 44
    )[0] == V6.canonical_product_build_id(),
        "corrected C2D build identity drift")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("build", "check"))
    args = parser.parse_args()
    value = build() if args.mode == "build" else check()
    print("c2-lite-v6-c2d-product-identity-rebind: " + value["status"])


if __name__ == "__main__":
    main()
