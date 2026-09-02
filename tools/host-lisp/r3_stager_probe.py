#!/usr/bin/env python3
"""Build and verify the structural, zero-Bank-0 R3 launcher probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
from typing import Any

import r3_g3_g6_contract as CONTRACT
import workbench_product_reproducibility as REPRO


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "config" / "r3-g3-g6-contract.json"
DEFAULT_RECEIPT = ROOT / "tests/bytecode/dialect-v2/evidence/r3/launcher-probe-receipt.json"
PRODUCT_REPORT = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/directory-only-l65m-v2-product-link-report.json"
DEBIT_AUTHORIZATION = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/directory-only-l65m-v2-bank-debit-authorization.json"
REPRO_RECEIPT = ROOT / "tests/bytecode/dialect-v2/evidence/r3/canonical-product-reproducibility-receipt.json"
IDENTITY_TRANSITION = ROOT / "tests/bytecode/dialect-v2/evidence/r3/canonical-product-identity-transition.json"
FORMAT = "lisp65-r3-stager-probe-receipt-v1"
PRODUCT_FILES = (
    ("workbench-prg", "lisp65.prg", ROOT / "build/products/workbench/overlay-stack-guard/lisp65-workbench-resident.prg"),
    ("bank5-preload", "bank5.bin", ROOT / "build/products/workbench/overlay-stack-guard/stdlib-with-overlay.ext.bin"),
    ("attic-catalog", "overlays.bin", ROOT / "build/products/workbench/overlay-stack-guard/lisp65-mvp-workbench.overlays.bin"),
    ("resolved-profile", "profile", ROOT / "build/products/workbench/overlay-stack-guard/resolved-profile.txt"),
)
PRODUCT_ELF = ROOT / "build/products/workbench/overlay-stack-guard/lisp65-workbench-overlay-linked.prg.elf"
LIBRARY_FILES = (
    ("ide", ROOT / "build/bytecode/dialect-v2/libs/ide.ext.bin"),
    ("idex", ROOT / "build/bytecode/dialect-v2/libs/idex.ext.bin"),
    ("m65d", ROOT / "build/bytecode/dialect-v2/libs/m65d.ext.bin"),
)
WORK_SLOTS = ("demo", "work", "an", "out", "fasl0", "fasl1", "fasl2")


class ProbeError(RuntimeError):
    pass


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProbeError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ProbeError(f"{label} must be an object")
    return value


def require_file(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise ProbeError(f"missing regular {label}: {path}")


def run(argv: list[str], *, label: str) -> str:
    result = subprocess.run(
        argv, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    if result.returncode:
        raise ProbeError(f"{label} failed ({result.returncode}):\n{result.stdout}")
    return result.stdout


def artifact(path: Path, role: str, name: str | None = None) -> dict[str, Any]:
    require_file(path, role)
    return {
        "role": role,
        "name": name or path.name,
        "bytes": path.stat().st_size,
        "sha256": sha_file(path),
    }


def artifact_set_sha(rows: list[dict[str, Any]]) -> str:
    normalized = [
        {"role": row["role"], "name": row["name"], "bytes": row["bytes"], "sha256": row["sha256"]}
        for row in sorted(rows, key=lambda item: (item["role"], item["name"]))
    ]
    return sha_bytes(json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def build_stager(contract: dict[str, Any], output: Path) -> None:
    compiler = ROOT / contract["toolchain_bindings"]["compiler"]["invocation"]
    source = ROOT / contract["probe"]["stager_source"]["path"]
    run(
        [str(compiler), "-Oz", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(output)],
        label="stager probe build",
    )
    payload = output.read_bytes()
    for marker in (b"L65S", b"bank5", b"attic", b"product"):
        if payload.count(marker) != 1:
            raise ProbeError(f"stager descriptor marker drift: {marker!r}")


def build_d81(c1541: str, output: Path, identity: str, entries: list[tuple[Path, str]]) -> str:
    argv = [c1541, "-format", identity, "d81", str(output)]
    for source, name in entries:
        require_file(source, f"D81 input {name}")
        argv.extend(("-write", str(source), name))
    run(argv, label=f"build {output.name}")
    return run([c1541, str(output), "-list"], label=f"list {output.name}")


def parse_identity(listing: str) -> dict[str, str]:
    match = re.search(r'^0\s+"([^"]+)"\s+([0-9A-Za-z]{2})\s+[0-9A-Za-z]{2}\s*$', listing, re.MULTILINE)
    if not match:
        raise ProbeError("cannot parse D81 name/id")
    return {"disk_name": match.group(1).rstrip(), "disk_id": match.group(2)}


def check_listing(listing: str, names: list[str], label: str) -> None:
    observed = set(re.findall(r'^\d+\s+"([^"]+)"\s+', listing, re.MULTILINE))
    missing = sorted(set(names) - observed)
    if missing:
        raise ProbeError(f"{label} lacks entries: {missing}")


def verify_reproducible_product(repro: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        REPRO.validate(repro)
    except REPRO.ReproError as exc:
        raise ProbeError(f"product reproducibility receipt drift: {exc}") from exc
    expected_by_id = {
        row["id"]: row for row in repro["product_artifacts"]
    }
    role_map = {
        "workbench-prg": "resident-prg",
        "bank5-preload": "stdlib-preload",
        "attic-catalog": "runtime-overlays",
        "resolved-profile": "resolved-profile",
    }
    rows: list[dict[str, Any]] = []
    for role, name, path in PRODUCT_FILES:
        row = artifact(path, role, name)
        expected = expected_by_id.get(role_map[role])
        if (
            not isinstance(expected, dict)
            or row["sha256"] != expected.get("sha256")
            or row["bytes"] != expected.get("bytes")
        ):
            raise ProbeError(f"current product artifact is not the reproducible R3 baseline: {role}")
        rows.append(row)
    elf_row = artifact(PRODUCT_ELF, "linked-product-elf", "lisp65.elf")
    expected_elf = expected_by_id.get("product-elf", {})
    if (
        elf_row["sha256"] != expected_elf.get("sha256")
        or elf_row["bytes"] != expected_elf.get("bytes")
    ):
        raise ProbeError("current product artifact is not the reproducible R3 baseline: product-elf")
    rows.append(elf_row)
    return rows


def build_receipt(contract_path: Path) -> dict[str, Any]:
    contract = load(contract_path, "R3 contract")
    # The probe needs the bound compiler and D81 builder, but it must remain a
    # source gate on hosts that do not carry the emulator's ROM/SD installation.
    # The complete local binding is checked separately immediately before G3.
    counts = CONTRACT.validate(contract, verify_environment=False)
    report = load(PRODUCT_REPORT, "Directory-only product report")
    authorization = load(DEBIT_AUTHORIZATION, "Directory-only debit authorization")
    repro = load(REPRO_RECEIPT, "product reproducibility receipt")
    transition = load(IDENTITY_TRANSITION, "product identity transition")
    product_rows = verify_reproducible_product(repro)
    historical = report["candidate"]
    if (
        authorization.get("status") != "authorized"
        or authorization.get("candidate", {}).get("product_sha256") != historical["product_sha256"]
        or authorization.get("candidate", {}).get("banked_headroom_bytes") != 269
        or transition.get("historical_r2_identity", {}).get("product_sha256") != historical["product_sha256"]
        or transition.get("r3_baseline_identity", {}).get("product_sha256") != repro["product_sha256"]
        or transition.get("bank_delta", {}).get("delta_bytes") != 0
    ):
        raise ProbeError("R2-to-R3 product identity transition drift")

    c1541 = contract["toolchain_bindings"]["c1541"]["artifact"]["path"]
    with tempfile.TemporaryDirectory(prefix="lisp65-r3-stager-probe-") as raw:
        directory = Path(raw)
        stager = directory / "autoboot.c65"
        product_d81 = directory / "lisp65-product.d81"
        work_d81 = directory / "lisp65-work.d81"
        mount_descriptor = directory / "lisp65-product.mount.json"
        slot = directory / "empty-slot.bin"
        demo = directory / "demo.seq"
        build_stager(contract, stager)
        slot.write_bytes(bytes(8192))
        demo.write_bytes((ROOT / "demos/d06-numbers.lisp").read_bytes())

        product_entries: list[tuple[Path, str]] = [(stager, "autoboot.c65,p")]
        product_entries.extend((path, f"{name},s" if role != "workbench-prg" else f"{name},p") for role, name, path in PRODUCT_FILES)
        product_entries.extend((path, f"{name},s") for name, path in LIBRARY_FILES)
        product_listing = build_d81(c1541, product_d81, "L65SYS,65", product_entries)
        os.chmod(product_d81, 0o444)

        work_entries = [(demo if name == "demo" else slot, f"{name},s") for name in WORK_SLOTS]
        work_listing = build_d81(c1541, work_d81, "L65WORK,65", work_entries)
        os.chmod(work_d81, 0o644)
        check_listing(
            product_listing,
            ["autoboot.c65", "lisp65.prg", "bank5.bin", "overlays.bin", "profile", "ide", "idex", "m65d"],
            "product D81",
        )
        check_listing(work_listing, list(WORK_SLOTS), "work D81")
        if parse_identity(product_listing) != {"disk_name": "L65SYS", "disk_id": "65"}:
            raise ProbeError("product D81 identity drift")
        if parse_identity(work_listing) != {"disk_name": "L65WORK", "disk_id": "65"}:
            raise ProbeError("work D81 identity drift")
        if stat.S_IMODE(product_d81.stat().st_mode) != 0o444 or stat.S_IMODE(work_d81.stat().st_mode) != 0o644:
            raise ProbeError("media package mode drift")

        product_media_row = artifact(product_d81, "product-d81", "lisp65-product.d81")
        work_media_row = artifact(work_d81, "work-d81", "lisp65-work.d81")
        mount_descriptor.write_bytes(canonical({
            "format": "lisp65-product-mount-descriptor-v2",
            "media": "lisp65-product.d81",
            "media_sha256": product_media_row["sha256"],
            "disk_name": "L65SYS",
            "disk_id": "65",
            "drive": 8,
            "write_protect": {
                "physical_floppy": "required-if-used",
                "stock_core_SD_D81": "unavailable-no-virtual-read-only-attach-control",
            },
            "mutable_entries": False,
        }))
        stager_row = artifact(stager, "cold-stager", "autoboot.c65")
        mount_row = artifact(mount_descriptor, "product-mount-descriptor", "lisp65-product.mount.json")
        library_rows = [artifact(path, f"library-{name}", name) for name, path in LIBRARY_FILES]
        expected_libraries = {
            row["id"]: row for row in repro["product_artifacts"]
            if row["id"].startswith("library-")
        }
        for row in library_rows:
            expected = expected_libraries.get(row["role"])
            if (
                not isinstance(expected, dict)
                or row["sha256"] != expected.get("sha256")
                or row["bytes"] != expected.get("bytes")
            ):
                raise ProbeError(f"current library is not the reproducible R3 baseline: {row['role']}")
        release_rows = product_rows + library_rows + [stager_row, product_media_row, work_media_row, mount_row]

        return {
            "format": FORMAT,
            "id": "r3-separate-stager-zero-bank0-probe",
            "status": "passed-not-implemented",
            "measured_on": "2026-07-13",
            "contract": {
                "path": contract_path.relative_to(ROOT).as_posix(),
                "sha256": sha_file(contract_path),
            },
            "boot_matrix": {
                "path": contract["boot_matrix"]["path"],
                "sha256": contract["boot_matrix"]["sha256"],
                "counts": counts,
            },
            "stager": stager_row | {
                "implementation": "closed-phase-descriptor-no-media-io-no-product-chain",
                "linked_into_workbench_prg": False,
            },
            "media": {
                "product": product_media_row | {
                    "identity": {"disk_name": "L65SYS", "disk_id": "65"},
                    "package_mode": "0444",
                    "mount_write_protect": "physical-floppy-required-stock-core-SD-D81-unavailable",
                    "mount_descriptor": mount_row,
                    "mutable_entries": False,
                    "entries": ["autoboot.c65", "lisp65.prg", "bank5.bin", "overlays.bin", "profile", "ide", "idex", "m65d"],
                },
                "work": work_media_row | {
                    "identity": {"disk_name": "L65WORK", "disk_id": "65"},
                    "package_mode": "0644",
                    "mount_write_protect": False,
                    "entries": list(WORK_SLOTS),
                },
                "drive_scope": "drive-8-only-drive-9-rejected",
            },
            "product_identity": {
                "historical_r2_product_sha256": historical["product_sha256"],
                "baseline_product_sha256": repro["product_sha256"],
                "candidate_workbench_product_sha256": repro["product_sha256"],
                "existing_artifact_parity": "exact",
                "existing_artifacts": product_rows,
                "product_libraries": library_rows,
                "release_artifact_set_sha256": artifact_set_sha(release_rows),
                "new_artifacts": [stager_row, product_media_row, work_media_row, mount_row],
            },
            "bank_delta": {
                "baseline_product_sha256": repro["product_sha256"],
                "candidate_product_sha256": repro["product_sha256"],
                "baseline_banked_headroom_bytes": 269,
                "candidate_banked_headroom_bytes": 269,
                "delta_bytes": 0,
                "authorization": None,
            },
            "source_bindings": [
                {"path": contract["probe"]["runner"]["path"], "sha256": contract["probe"]["runner"]["sha256"]},
                {"path": contract["probe"]["stager_source"]["path"], "sha256": contract["probe"]["stager_source"]["sha256"]},
                {"path": PRODUCT_REPORT.relative_to(ROOT).as_posix(), "sha256": sha_file(PRODUCT_REPORT)},
                {"path": DEBIT_AUTHORIZATION.relative_to(ROOT).as_posix(), "sha256": sha_file(DEBIT_AUTHORIZATION)},
                {"path": REPRO_RECEIPT.relative_to(ROOT).as_posix(), "sha256": sha_file(REPRO_RECEIPT)},
                {"path": IDENTITY_TRANSITION.relative_to(ROOT).as_posix(), "sha256": sha_file(IDENTITY_TRANSITION)},
            ],
            "claims": {
                "separate_artifact": True,
                "product_bank0_delta": 0,
                "media_loader_implemented": False,
                "autoboot_executed": False,
                "G3": "not-run",
                "G6": "not-run",
                "release_effect": "none",
            },
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    generate = sub.add_parser("generate")
    generate.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    generate.add_argument("--output", type=Path, default=DEFAULT_RECEIPT)
    check = sub.add_parser("check")
    check.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    check.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    args = parser.parse_args(argv)
    contract_path = args.contract if args.contract.is_absolute() else ROOT / args.contract
    try:
        receipt = build_receipt(contract_path)
        if args.command == "generate":
            output = args.output if args.output.is_absolute() else ROOT / args.output
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(canonical(receipt))
            print(
                f"r3-stager-probe: WROTE status={receipt['status']} "
                f"stager={receipt['stager']['bytes']} bank_delta=0 output={output.relative_to(ROOT)}"
            )
        else:
            receipt_path = args.receipt if args.receipt.is_absolute() else ROOT / args.receipt
            require_file(receipt_path, "launcher probe receipt")
            if receipt_path.read_bytes() != canonical(receipt):
                raise ProbeError("launcher probe receipt drift")
            print(
                "r3-stager-probe: PASS status=passed-not-implemented "
                f"stager={receipt['stager']['bytes']} bank_delta=0 "
                f"release_set={receipt['product_identity']['release_artifact_set_sha256']}"
            )
        return 0
    except (ProbeError, CONTRACT.ContractError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"r3-stager-probe: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
