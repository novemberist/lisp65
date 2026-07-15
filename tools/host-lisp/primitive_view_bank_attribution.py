#!/usr/bin/env python3
"""Generate or verify the primitive-view Bank-0 credit attribution."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BASELINE_ARCHIVE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/promotions/"
    "r4-product-candidate-91cab98.tar.gz"
)
BASELINE_ELF_MEMBER = (
    "payload/build/products/workbench/overlay-stack-guard/"
    "lisp65-workbench-overlay-linked.prg.elf"
)
BASELINE_FOOTPRINT_MEMBER = (
    "payload/build/products/workbench/overlay-stack-guard/footprint-audit.json"
)
CANDIDATE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/r3/"
    "canonical-product-reproducibility-receipt.json"
)
REPORT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/r3/"
    "primitive-view-bank-attribution-receipt.json"
)
NM = ROOT / "tools/llvm-mos/bin/llvm-nm"
FORMAT = "lisp65-primitive-view-bank-attribution-v1"


class AttributionError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def binding(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha_bytes(path.read_bytes()),
    }


def load(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise AttributionError(f"missing {label}: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AttributionError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise AttributionError(f"{label} must contain an object")
    return value


def archive_member(archive: tarfile.TarFile, name: str) -> bytes:
    try:
        member = archive.getmember(name)
        source = archive.extractfile(member)
    except (KeyError, tarfile.TarError) as exc:
        raise AttributionError(f"missing archive member {name}") from exc
    if source is None or not member.isfile():
        raise AttributionError(f"archive member is not a regular file: {name}")
    return source.read()


def nm_symbols(path: Path) -> dict[str, tuple[int, int, str]]:
    process = subprocess.run(
        [
            str(NM), "--defined-only", "--print-size", "--size-sort",
            "--radix=x", str(path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if process.returncode:
        raise AttributionError(f"llvm-nm failed: {process.stderr.strip()}")
    found: dict[str, list[tuple[int, int, str]]] = {}
    for line in process.stdout.splitlines():
        parts = line.split(None, 3)
        if len(parts) != 4:
            continue
        address, size, kind, name = parts
        found.setdefault(name, []).append((int(address, 16), int(size, 16), kind))
    duplicates = sorted(name for name, rows in found.items() if len(rows) != 1)
    if duplicates:
        raise AttributionError(f"ambiguous duplicate symbols: {duplicates[:5]}")
    return {name: rows[0] for name, rows in found.items()}


def symbol_row(name: str, baseline: tuple[int, int, str] | None,
               candidate: tuple[int, int, str] | None) -> dict[str, Any]:
    baseline_size = 0 if baseline is None else baseline[1]
    candidate_size = 0 if candidate is None else candidate[1]
    return {
        "name": name,
        "baseline_bytes": baseline_size,
        "candidate_bytes": candidate_size,
        "delta_bytes": candidate_size - baseline_size,
    }


def generate() -> dict[str, Any]:
    receipt = load(CANDIDATE_RECEIPT, "canonical product receipt")
    artifacts = receipt.get("product_artifacts")
    if not isinstance(artifacts, list):
        raise AttributionError("canonical product artifact inventory missing")
    rows = [
        row for row in artifacts
        if isinstance(row, dict) and row.get("id") == "product-elf"
    ]
    if len(rows) != 1:
        raise AttributionError("canonical product ELF inventory drift")
    candidate_row = rows[0]
    candidate_elf = ROOT / str(candidate_row.get("path"))
    candidate_bytes = candidate_elf.read_bytes()
    if sha_bytes(candidate_bytes) != candidate_row.get("sha256"):
        raise AttributionError("live candidate ELF does not match the canonical double build")

    with tarfile.open(BASELINE_ARCHIVE, "r:gz") as archive:
        baseline_bytes = archive_member(archive, BASELINE_ELF_MEMBER)
        footprint = json.loads(archive_member(archive, BASELINE_FOOTPRINT_MEMBER))
    if not isinstance(footprint, dict):
        raise AttributionError("baseline footprint is not an object")

    with tempfile.TemporaryDirectory(prefix="l65-primitive-bank-") as directory:
        baseline_path = Path(directory) / "baseline.elf"
        candidate_path = Path(directory) / "candidate.elf"
        baseline_path.write_bytes(baseline_bytes)
        candidate_path.write_bytes(candidate_bytes)
        baseline_symbols = nm_symbols(baseline_path)
        candidate_symbols = nm_symbols(candidate_path)

    expected = {
        "vm_callprim": (7097, 6938),
        "vm_native_call": (1160, 1019),
        "vm_apply_primitive.primfn": (39, 0),
        "vm_byte_args": (0, 97),
    }
    changes = []
    for name, (baseline_size, candidate_size) in expected.items():
        row = symbol_row(name, baseline_symbols.get(name), candidate_symbols.get(name))
        if (row["baseline_bytes"], row["candidate_bytes"]) != (
            baseline_size, candidate_size,
        ):
            raise AttributionError(f"pinned symbol delta drift: {name} {row}")
        changes.append(row)

    named_delta = sum(row["delta_bytes"] for row in changes)
    baseline_vma = baseline_symbols["__lisp65_workbench_runtime_overlay_vma"][0]
    candidate_vma = candidate_symbols["__lisp65_workbench_runtime_overlay_vma"][0]
    resident_delta = candidate_vma - baseline_vma
    alignment_delta = resident_delta - named_delta
    baseline_bank = int(footprint["post_boot_reserve"]) - 1536
    candidate_bank = int(receipt["metrics"]["banked_headroom_bytes"])
    if (
        baseline_bank != 313
        or candidate_bank != 553
        or resident_delta != -240
        or named_delta != -242
        or alignment_delta != 2
        or candidate_bank - baseline_bank != 240
    ):
        raise AttributionError("Bank-0 reconciliation drift")

    return {
        "format": FORMAT,
        "version": 1,
        "id": "primitive-view-single-source-bank-credit",
        "status": "pass",
        "measured_on": "2026-07-14",
        "metric": "paired-real-linked-product-elf-named-symbol-delta",
        "baseline": {
            "product_artifact_set_sha256": (
                "6dc9c48742404f72f266c21d37bffc57d537920f9fd6eda66c0a2cf077701489"
            ),
            "archive": binding(BASELINE_ARCHIVE),
            "elf_member": BASELINE_ELF_MEMBER,
            "elf_sha256": sha_bytes(baseline_bytes),
            "runtime_overlay_vma": f"0x{baseline_vma:04x}",
            "banked_headroom_bytes": baseline_bank,
        },
        "candidate": {
            "canonical_receipt": binding(CANDIDATE_RECEIPT),
            "product_artifact_set_sha256": receipt["artifact_set_sha256"],
            "product_sha256": receipt["product_sha256"],
            "elf_path": candidate_row["path"],
            "elf_sha256": candidate_row["sha256"],
            "runtime_overlay_vma": f"0x{candidate_vma:04x}",
            "banked_headroom_bytes": candidate_bank,
        },
        "attribution": {
            "symbol_changes": sorted(changes, key=lambda row: row["name"]),
            "named_symbol_delta_bytes": named_delta,
            "alignment_delta_bytes": alignment_delta,
            "resident_delta_bytes": resident_delta,
            "bank_credit_bytes": candidate_bank - baseline_bank,
            "reconciliation": (
                "named-symbol-delta-plus-alignment-equals-resident-delta"
            ),
            "cause": (
                "single-registry-generated-primitive-views-consolidate-"
                "dispatch-byte-argument-code"
            ),
        },
        "result": "bank-credit-fully-attributed",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("generate", "verify"))
    parser.add_argument("--output", type=Path, default=REPORT)
    args = parser.parse_args()
    try:
        value = generate()
        if args.command == "generate":
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(canonical(value))
            print(
                "primitive-view-bank-attribution: WROTE "
                f"{args.output.relative_to(ROOT)}"
            )
        else:
            existing = load(args.output, "attribution receipt")
            if canonical(existing) != canonical(value):
                raise AttributionError("attribution receipt drift")
            print(
                "primitive-view-bank-attribution: PASS "
                "bank_credit=240 resident_delta=-240"
            )
    except (AttributionError, OSError, KeyError, ValueError, tarfile.TarError) as exc:
        print(f"primitive-view-bank-attribution: FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
