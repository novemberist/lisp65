#!/usr/bin/env python3
"""Pin the one authorized direct-entry correction product link."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_product_substitution_link as P  # noqa: E402

CANDIDATE = ROOT / "build/c2.2/substitution/product-link-29-direct-entry-encoding"
ARCHIVE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/artifacts/"
    "c2-link29-direct-entry-encoding-pass-20260720/root")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link29-direct-entry-encoding-structural-receipt.json")
CONTRACT_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-direct-entry-encoding-correction-contract-receipt.json")
CAPACITY_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-direct-entry-encoding-correction-capacity-probe-receipt.json")
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link28-direct-entry-hardware-first-red-diagnosis.json")


class PinError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PinError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def tree_hash(root: Path) -> tuple[str, int, int]:
    lines: list[str] = []; total = 0
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        lines.append(f"{sha(path)}  {relative}\n")
        total += path.stat().st_size
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest(), len(lines), total


def archive_candidate() -> tuple[str, int, int]:
    require(CANDIDATE.is_dir() and not ARCHIVE.exists(),
            "candidate absent or archive already exists")
    ARCHIVE.mkdir(parents=True)
    for source in sorted(CANDIDATE.iterdir()):
        info = source.lstat()
        require(stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode),
                f"candidate entry is not a regular file: {source}")
        destination = ARCHIVE / source.name
        shutil.copyfile(source, destination)
        os.chmod(destination, 0o444)
    os.chmod(ARCHIVE, 0o555)
    return tree_hash(ARCHIVE)


def build_receipt() -> dict[str, Any]:
    structural = load(CANDIDATE / "product-substitution-link.json")
    balance = load(CANDIDATE / "substitution-balance.json")
    kernal = load(CANDIDATE / "kernal-freedom-link.json")
    direct = load(CONTRACT_RECEIPT)
    capacity_probe = load(CAPACITY_RECEIPT)
    require(structural.get("status") == "passed"
            and structural.get("direct_entry_encoding_gate")
            == "passed-637-of-637-fixnum-values-zero",
            "candidate direct-entry structural closure")
    require(direct.get("status") == "passed-contract-and-cross-parity-probe-only"
            and direct["cross_parity"]["direct_entry_references"] == 637
            and direct["cross_parity"]["fixnum_decodable_published_values"] == 0,
            "direct-entry contract receipt")
    require(capacity_probe.get("status")
            == "passed-capacity-placement-and-structural-probe-only",
            "capacity probe receipt")
    tree_sha, files, total = archive_candidate()
    product = CANDIDATE / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    sections = P.section_table(elf)
    phase08 = sections[".lisp65_rt_c2d_08"]["bytes"]
    phase12 = sections[".lisp65_rt_c2d_12"]["bytes"]
    phase13 = sections[".lisp65_rt_c2d_13"]["bytes"]
    currencies = balance["currencies"]
    window = kernal["capacity"]
    runtime = currencies["runtime_overlay_bank"]
    reports = {
        name: sha(CANDIDATE / name) for name in (
            "product-substitution-link.json", "substitution-balance.json",
            "kernal-freedom-link.json", "one-truth-closure.json",
            "handoff-z-abi-final.json", "pre-ownership-closure-final.json",
            "profile-data-reference-final.json", "fixed-host-facade-final.json",
            "runtime-family-total-identity.json", "total-publish-last-domain.json",
        )
    }
    return {
        "format": "lisp65-c2-product-link29-direct-entry-encoding-structural-receipt-v1",
        "recorded_on": "2026-07-20",
        "status": "passed-structural-closure-hardware-pending",
        "candidate": {"product": str(product.relative_to(ROOT)),
                      "product_bytes": product.stat().st_size,
                      "product_sha256": sha(product),
                      "elf": str(elf.relative_to(ROOT)), "elf_sha256": sha(elf),
                      "window_sha256": sha(CANDIDATE / "c2-product-kernal-window.bin"),
                      "boot_family_sha256": sha(CANDIDATE / "runtime-overlays-boot-final.bin"),
                      "session_family_sha256": sha(CANDIDATE / "runtime-overlays-session-final.bin")},
        "correction": {
            "root_cause": "target omitted BCODE scale; host oracle omitted image directory base",
            "single_constructor": "src/obj.h:MK_BCODE",
            "direct_references_checked": 637,
            "fixnum_decodable_published_values": 0,
            "target_phase12_negative_classes": 4,
            "phase_08_bytes": phase08, "phase_08_link28_bytes": 1381,
            "phase_08_delta_bytes": phase08 - 1381,
            "phase_12_bytes": phase12, "phase_12_link28_bytes": 1289,
            "phase_12_delta_bytes": phase12 - 1289,
        },
        "capacity": {
            "bank0_ordinary_bss_headroom_bytes": window["ordinary_bank0_bss"]["headroom_bytes"],
            "fixed_bank0_headroom_bytes": structural["fixed_bank0_headroom_bytes"],
            "e000_window_future_margin_bytes": window["actual_future_margin_bytes"],
            "e000_growth_policy": window["growth_policy"],
            "bank5_mutable_plane": currencies["bank5_mutable_plane"],
            "attic_immutable": currencies["attic_immutable"],
            "runtime_overlay_bank": {
                "boot_image_bytes": runtime["boot_image_bytes"],
                "boot_delta_vs_link28_bytes": runtime["boot_image_bytes"] - 12529,
                "boot_headroom_bytes": 65536 - runtime["boot_image_bytes"],
                "session_image_bytes": runtime["session_image_bytes"],
                "session_delta_vs_link28_bytes": runtime["session_image_bytes"] - 50334,
                "session_headroom_bytes": 65536 - runtime["session_image_bytes"],
                "slice_cap_bytes": 1792,
                "largest_slice_bytes": phase13,
            },
            "resident_island_delta_bytes": 0,
            "installer_slice_delta_bytes": 0,
        },
        "structural_gates": {
            "identity": structural["identity_gate"],
            "capacity": structural["capacity_gate"],
            "one_truth": structural["one_truth_gate"],
            "direct_entry_encoding": structural["direct_entry_encoding_gate"],
            "kernal_freedom": structural["kernal_freedom_gate"],
            "fixed_host_facade": structural["fixed_host_facade_gate"],
            "pre_ownership": structural["pre_ownership_gate"],
            "handoff_z_and_io": structural["handoff_z_abi_gate"],
            "reports": reports,
        },
        "immutable_evidence": {
            "root": str(ARCHIVE.relative_to(ROOT)), "files": files,
            "total_file_bytes": total, "file_mode": "0444", "directory_mode": "0555",
            "canonical_tree_hash_rule": "SHA-256 over sorted '<file-sha256>  <relative-path>\\n' lines",
            "canonical_tree_sha256": tree_sha,
        },
        "inputs": {
            "hardware_first_red": bind(FIRST_RED),
            "contract_receipt": bind(CONTRACT_RECEIPT),
            "capacity_probe_receipt": bind(CAPACITY_RECEIPT),
            "product_link_tool": bind(ROOT / "tools/host-lisp/c2_product_substitution_link.py"),
            "abi_bridge": bind(ROOT / "tools/host-lisp/c2_bcode_contract.py"),
            "target_decoder": bind(ROOT / "scripts/c2-stream-v2-decoder.c"),
        },
        "execution_accounting": {"resident_island_seed_links": 1,
                                 "product_closure_links": 1,
                                 "additional_product_links_authorized": 0},
        "next_gate": {"hardware": "not-run", "promotion": "blocked-pending-hardware",
                      "step": "receipt-less fail-fast hardware presmoke of this exact candidate"},
        "claim_limit": (
            "Structural and capacity closure of the sole owner-authorized successor "
            "product link. Hardware execution, promotion and release readiness are not claimed."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("action", choices=("write",))
    parser.parse_args()
    try:
        value = build_receipt()
        RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
        os.chmod(RECEIPT, 0o444)
        print("c2-direct-entry-candidate-pin: WROTE "
              f"product={value['candidate']['product_sha256']} "
              f"files={value['immutable_evidence']['files']} hardware=not-run")
        return 0
    except (OSError, ValueError, RuntimeError, PinError) as error:
        print(f"c2-direct-entry-candidate-pin: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
