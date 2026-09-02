#!/usr/bin/env python3
"""Package the sealed R4/R5 bytes as the self-verifying R6 two-media ship."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "host-lisp"))

import block_capacity_delta_policy as CAPACITY  # noqa: E402
import history_transport_rewrite as TRANSPORT  # noqa: E402
import r6_ship_offline as OFFLINE  # noqa: E402


CONTRACT = ROOT / "config/r6-ship-contract.json"
HARDWARE_PROFILE = ROOT / "config/g6-hardware-profile.json"
REGISTER = ROOT / "config/promotion-register.json"
PACKER = ROOT / "tools/host-lisp/r6_ship.py"
OFFLINE_VERIFIER = ROOT / "tools/host-lisp/r6_ship_offline.py"
TRACKED_RECEIPT = ROOT / "tests/bytecode/dialect-v2/evidence/post-release/r6-ship-wave3-packer-receipt.json"
FORMAT = "lisp65-r6-ship-v1"
RECEIPT_FORMAT = "lisp65-r6-ship-packer-receipt-v1"
PRODUCT_SET = OFFLINE.PRODUCT_SET
R4_SHA = OFFLINE.R4_SHA
R5_SHA = OFFLINE.R5_SHA
R4_ID = OFFLINE.R4_ID
R5_ID = OFFLINE.R5_ID
PRODUCT_BUILD_ID = OFFLINE.PRODUCT_BUILD_ID
ARTIFACT_COUNT = OFFLINE.ARTIFACT_COUNT
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


class ShipError(RuntimeError):
    pass


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ShipError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ShipError(f"{label} must be a regular non-symlink file: {path}")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=strict_object,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ShipError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ShipError(f"{label} must contain an object")
    return value


def exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise ShipError(f"{label} keys drift: {actual}")
    return value


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii")


def relative(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ShipError(f"{label} must be a nonempty relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or ".." in path.parts:
        raise ShipError(f"{label} is not a canonical relative path")
    return value


def canonical_commit(value: str, *, historical_verification: bool = False) -> str:
    if not COMMIT_RE.fullmatch(value):
        raise ShipError("source commit must be a full lowercase Git commit")
    transport_commit = TRANSPORT.resolve_commit(value)
    completed = subprocess.run(
        ["git", "rev-parse", f"{transport_commit}^{{commit}}"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if completed.returncode or completed.stdout.strip() != transport_commit:
        raise ShipError("source commit is not canonical in this repository")
    for path in (PACKER, CONTRACT, HARDWARE_PROFILE, OFFLINE_VERIFIER):
        name = path.relative_to(ROOT).as_posix()
        materialized = subprocess.run(
            ["git", "show", f"{transport_commit}:{name}"], cwd=ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if materialized.returncode:
            raise ShipError(f"source commit lacks R6 packer input: {name}")
        if historical_verification and path == CONTRACT and materialized.stdout != path.read_bytes():
            raise ShipError("historical R6 receipt contract drift")
        if not historical_verification and materialized.stdout != path.read_bytes():
            raise ShipError(f"source commit does not bind current R6 packer input: {name}")
    return value


def canonical_commit_date(value: str) -> str:
    transport_commit = TRANSPORT.resolve_commit(value)
    completed = subprocess.run(
        ["git", "show", "-s", "--format=%cs", transport_commit], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    result = completed.stdout.strip()
    if completed.returncode or not DATE_RE.fullmatch(result):
        raise ShipError("source commit date is unavailable or non-canonical")
    return result


def contract() -> dict[str, Any]:
    value = load(CONTRACT, "R6 ship contract")
    exact(
        value,
        {
            "format", "version", "id", "status", "input", "policy", "package",
            "artifact_mapping", "media", "first_session", "negative_tests",
            "hardware_profile", "claims", "capacity_delta",
        },
        "R6 ship contract",
    )
    if (
        value["format"] != "lisp65-r6-ship-contract-v2" or value["version"] != 2
        or value["id"] != "r6-archive-to-ship" or value["status"] != "approved-for-packer"
        or value["input"] != {
            "r4_promotion_id": R4_ID,
            "r4_archive_sha256": R4_SHA,
            "r5_promotion_id": R5_ID,
            "r5_archive_sha256": R5_SHA,
            "product_artifact_set_sha256": PRODUCT_SET,
            "product_build_id": PRODUCT_BUILD_ID,
            "artifact_count": ARTIFACT_COUNT,
        }
        or value["policy"] != {
            "operation": "transform-and-package-only",
            "build_tools": "forbidden",
            "product_byte_source": "embedded-R5-hardware-acceptance-archive-only",
            "g3_evidence_source": "embedded-R4-product-candidate-archive-only",
            "live_tree_product_authority": False,
            "artifact_mapping": "every-R5-product-role-exactly-once",
            "byte_identity": "required-for-every-product-artifact-and-every-L65SYS-entry",
            "new_bytes": "manifest-readme-verifier-packer-provenance-and-receipt-only",
        }
        or value["package"] != {
            "format": FORMAT,
            "output": "build/r6/ship",
            "self_contained": True,
            "offline_verification": "package-alone-no-repository-no-network",
            "ship_media_ready": True,
            "release_authorization": "none-until-G6",
            "packaging_runtime": "CPython-3.14.6",
        }
        or value["negative_tests"] != ["product-byte", "manifest", "r5-archive"]
    ):
        raise ShipError("R6 ship contract semantic drift")
    if value["hardware_profile"] != {
        "path": HARDWARE_PROFILE.relative_to(ROOT).as_posix(), "sha256": sha(HARDWARE_PROFILE),
    }:
        raise ShipError("R6 hardware profile binding drift")
    mapping = value["artifact_mapping"]
    if (
        not isinstance(mapping, list) or len(mapping) != ARTIFACT_COUNT
        or len({row.get("role") for row in mapping if isinstance(row, dict)}) != ARTIFACT_COUNT
        or any(not isinstance(row, dict) or set(row) != {"role", "ship_path", "d81_entry"} for row in mapping)
        or any(relative(row["ship_path"], "artifact ship path") != row["ship_path"] for row in mapping)
    ):
        raise ShipError("R6 artifact mapping drift")
    try:
        CAPACITY.validate_policy()
        CAPACITY.validate_capacity_delta(value["capacity_delta"])
    except CAPACITY.CapacityDeltaError as exc:
        raise ShipError(f"R6 capacity delta drift: {exc}") from exc
    return value


def registered_inputs(value: dict[str, Any]) -> tuple[Path, Path]:
    register = load(REGISTER, "promotion register")
    promotions = register.get("promotions")
    if not isinstance(promotions, list):
        raise ShipError("promotion register lacks promotions")
    expected = {
        R4_ID: {
            "subject": "r4-product-candidate-wave3-l-lite", "kind": "product-candidate",
            "source_commit": "726bdf896e075100b44e8550ce72f529b3ea0ffe",
            "archive": f"tests/bytecode/dialect-v2/evidence/promotions/{R4_ID}.tar.gz",
            "archive_sha256": R4_SHA,
        },
        R5_ID: {
            "subject": "r5-global-g5-04863969", "kind": "hardware-acceptance",
            "source_commit": "8f66e77908da5441aa181766f9815b51d9b7c480",
            "archive": f"tests/bytecode/dialect-v2/evidence/promotions/{R5_ID}.tar.gz",
            "archive_sha256": R5_SHA,
        },
    }
    paths: dict[str, Path] = {}
    for promotion_id, fields in expected.items():
        row = next((item for item in promotions if item.get("id") == promotion_id), None)
        if row != {"id": promotion_id, **fields}:
            raise ShipError(f"R6 input is not the registered promotion: {promotion_id}")
        archive = ROOT / Path(*PurePosixPath(fields["archive"]).parts)
        if archive.is_symlink() or not archive.is_file() or sha(archive) != fields["archive_sha256"]:
            raise ShipError(f"registered archive byte drift: {promotion_id}")
        paths[promotion_id] = archive
    if value["input"]["r4_promotion_id"] not in paths or value["input"]["r5_promotion_id"] not in paths:
        raise ShipError("R6 contract/register input mismatch")
    return paths[value["input"]["r4_promotion_id"]], paths[value["input"]["r5_promotion_id"]]


def write_file(root: Path, name: str, data: bytes, mode: int) -> Path:
    relative(name, "package output")
    path = root / Path(*PurePosixPath(name).parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise ShipError(f"duplicate package output: {name}")
    path.write_bytes(data)
    os.chmod(path, mode)
    return path


def readme_bytes(product_set: str) -> bytes:
    return (
        "LISP65 WORKBENCH DIALECT V2 - R6 G6 CANDIDATE\n"
        "================================================\n\n"
        "This package contains the byte-exact R5 hardware-accepted product.\n"
        f"Product artifact set: {product_set}\n"
        "G3: PASSED (emulator prefilter only)\n"
        "G5: PASSED (14/14 hardware cases)\n"
        "G6: NOT RUN\n"
        "RELEASE: NO\n\n"
        "Before use, run:  python3 verify.py\n\n"
        "Two-media, one-drive flow (drive 8):\n"
        "1. Write media/lisp65-product.d81 to a disk labelled L65SYS,65.\n"
        "2. Boot L65SYS in drive 8. For a physical floppy, engage its write-protect tab.\n"
        "   Stock-core SD-backed D81 images have no virtual write-protect switch; M65D still rejects L65SYS by identity.\n"
        "3. Wait for staging, chaining, and the REPL.\n"
        "4. When prompted, swap once to any valid 1581 disk of your own.\n"
        "5. Every valid non-product 1581 disk is writable; only the L65SYS system disk is protected.\n\n"
        "First session:\n"
        "  (+ 20 22)\n"
        "  (load-lib \"ide\")\n"
        "  (load-lib \"idex\")\n"
        "  (load-lib \"m65d\")\n"
        "  ; now swap once to your work disk\n"
        "  (dir)\n"
        "  (edit)\n\n"
        "media/lisp65-work.d81 is a convenient shipped blank work disk.\n"
        "You may instead use any valid 1581 disk without renaming it.\n"
        "There is no on-device formatter in 1.0.\n"
    ).encode("ascii")


def file_inventory(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise ShipError(f"package output contains symlink: {path}")
        if path.is_file() and path != root / "manifest.json":
            rows.append({
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha(path),
                "mode": f"0{stat.S_IMODE(path.stat().st_mode):03o}",
            })
    return rows


def package_set_sha(rows: list[dict[str, Any]]) -> str:
    values = [
        {key: row[key] for key in ("path", "bytes", "sha256", "mode")}
        for row in sorted(rows, key=lambda row: row["path"])
    ]
    return sha_bytes(json.dumps(values, sort_keys=True, separators=(",", ":")).encode("ascii"))


def build(*, source_commit: str, packed_on: str, output: Path) -> dict[str, Any]:
    source_commit = canonical_commit(source_commit)
    if packed_on != canonical_commit_date(source_commit):
        raise ShipError("R6 packed_on must equal the source commit date")
    value = contract()
    if output.exists() or output.is_symlink():
        raise ShipError(f"R6 ship output must be fresh: {output}")
    r4_archive, r5_archive = registered_inputs(value)
    r4_manifest, r4_root, r4_tmp = OFFLINE.verify_nested_archive(r4_archive, R4_SHA, "r4-pack")
    r5_manifest, r5_root, r5_tmp = OFFLINE.verify_nested_archive(r5_archive, R5_SHA, "r5-pack")
    try:
        if r4_manifest.get("id") != value["input"]["r4_promotion_id"] or r5_manifest.get("id") != value["input"]["r5_promotion_id"]:
            raise ShipError("nested promotion identity drift")
        r5_top_path = r5_root / "payload" / Path(*PurePosixPath(r5_manifest["top_receipt"]["path"]).parts)
        r5_top = load(r5_top_path, "sealed R5 top receipt")
        source_rows = r5_top.get("product", {}).get("artifacts")
        if (
            r5_top.get("claims") != {
                "G5": "passed-for-product-artifact-set", "G6": "not-run",
                "function_metadata": "101-exact/34-unresolved-no-complete-help-claim",
                "hardware_boot_cases": (
                    "not-run(5/5-applicable); execution=single-device; "
                    "n/a(1/1-profile-bound)"
                ),
                "product_artifact_set_sha256": PRODUCT_SET,
                "release": "not-release-capable",
            }
            or not isinstance(source_rows, list) or len(source_rows) != ARTIFACT_COUNT
            or OFFLINE.artifact_set_sha(source_rows) != PRODUCT_SET
        ):
            raise ShipError("sealed R5 product/result drift")
        mapping = {row["role"]: row for row in value["artifact_mapping"]}
        if set(mapping) != {row["role"] for row in source_rows}:
            raise ShipError("R6 mapping does not cover the R5 product exactly")
        output.mkdir(parents=True)
        artifact_rows: list[dict[str, Any]] = []
        for source in source_rows:
            route = mapping[source["role"]]
            nested = r5_root / "payload" / Path(*PurePosixPath(source["path"]).parts)
            if nested.is_symlink() or not nested.is_file() or nested.stat().st_size != source["bytes"] or sha(nested) != source["sha256"]:
                raise ShipError(f"sealed R5 product payload drift: {source['role']}")
            mode = 0o644 if source["role"] == "work-d81" else 0o444
            written = write_file(output, route["ship_path"], nested.read_bytes(), mode)
            artifact_rows.append({
                "role": source["role"], "name": source["name"],
                "source_path": source["path"], "ship_path": route["ship_path"],
                "bytes": source["bytes"], "sha256": source["sha256"],
                "d81_entry": route["d81_entry"],
                "identity": "byte-identical-from-R5-archive",
            })
            if written.read_bytes() != nested.read_bytes():
                raise ShipError(f"R6 copy was not byte-identical: {source['role']}")

        r4_g3 = r4_root / "payload/tests/bytecode/dialect-v2/evidence/r3/g3-emulator-receipt.json"
        r4_matrix = r4_root / "payload/tests/bytecode/dialect-v2/r3-boot/cases.json"
        r4_contract = r4_root / "payload/config/r3-g3-g6-contract.json"
        for path, label in ((r4_g3, "G3 receipt"), (r4_matrix, "boot matrix"), (r4_contract, "R3 contract")):
            if path.is_symlink() or not path.is_file():
                raise ShipError(f"sealed R4 lacks {label}")
        r4_package_path = f"evidence/{R4_ID}.tar.gz"
        r5_package_path = f"evidence/{R5_ID}.tar.gz"
        write_file(output, r4_package_path, r4_archive.read_bytes(), 0o444)
        write_file(output, r5_package_path, r5_archive.read_bytes(), 0o444)
        g3_path = write_file(output, "evidence/g3-emulator-receipt.json", r4_g3.read_bytes(), 0o444)
        g5_path = write_file(output, "evidence/g5-hardware-receipt.json", r5_top_path.read_bytes(), 0o444)
        matrix_path = write_file(output, "evidence/r3-boot-cases.json", r4_matrix.read_bytes(), 0o444)
        contract_path = write_file(output, "evidence/r6-ship-contract.json", CONTRACT.read_bytes(), 0o444)
        profile_path = write_file(output, "evidence/g6-hardware-profile.json", HARDWARE_PROFILE.read_bytes(), 0o444)
        write_file(output, "README-FIRST.txt", readme_bytes(PRODUCT_SET), 0o444)
        write_file(output, "verify.py", OFFLINE_VERIFIER.read_bytes(), 0o555)
        packer_path = write_file(output, "evidence/r6_ship.py", PACKER.read_bytes(), 0o444)

        r3 = load(r4_contract, "sealed R3 contract")
        toolchain = {
            "compiler": r3["toolchain_bindings"]["compiler"],
            "c1541": r3["toolchain_bindings"]["c1541"],
            "xmega65": r3["toolchain_bindings"]["xmega65"],
            "rom": r3["toolchain_bindings"]["rom"],
            "sd_base": r3["toolchain_bindings"]["sd_base"],
            "packaging_runtime": value["package"]["packaging_runtime"],
            "packer": {
                "source_commit": source_commit,
                "path": PACKER.relative_to(ROOT).as_posix(),
                "sha256": sha(PACKER),
                "packaged_path": packer_path.relative_to(output).as_posix(),
            },
        }
        files = file_inventory(output)
        manifest = {
            "format": FORMAT, "version": 1, "status": "packaged-g6-not-run",
            "profile": "dialect-v2", "source_commit": source_commit,
            "packed_on": packed_on,
            "contract": contract_path.relative_to(output).as_posix(),
            "contract_sha256": sha(contract_path),
            "product": {
                "artifact_set_sha256": PRODUCT_SET, "product_build_id": PRODUCT_BUILD_ID,
                "artifact_count": ARTIFACT_COUNT,
                "r4_promotion_id": value["input"]["r4_promotion_id"],
                "r5_promotion_id": value["input"]["r5_promotion_id"],
            },
            "evidence": {
                "r4_archive": {"promotion_id": value["input"]["r4_promotion_id"], "path": r4_package_path, "sha256": R4_SHA},
                "r5_archive": {"promotion_id": value["input"]["r5_promotion_id"], "path": r5_package_path, "sha256": R5_SHA},
                "g3_receipt": {"path": g3_path.relative_to(output).as_posix(), "sha256": sha(g3_path)},
                "g5_receipt": {"path": g5_path.relative_to(output).as_posix(), "sha256": sha(g5_path)},
                "boot_matrix": {"path": matrix_path.relative_to(output).as_posix(), "sha256": sha(matrix_path)},
                "hardware_profile": {"path": profile_path.relative_to(output).as_posix(), "sha256": sha(profile_path)},
            },
            "toolchain": toolchain,
            "gates": value["claims"],
            "policy": {"operation": "transform-and-package-only", "product_sha_changes": 0, "capacity_delta": value["capacity_delta"]},
            "media": value["media"], "first_session": value["first_session"],
            "artifacts": artifact_rows, "files": files,
            "package_set_sha256": package_set_sha(files), "result": "passed",
        }
        manifest_path = output / "manifest.json"
        manifest_path.write_bytes(canonical_json(manifest))
        os.chmod(manifest_path, 0o444)
    finally:
        r4_tmp.cleanup()
        r5_tmp.cleanup()
    verify(output)
    print(
        f"r6-ship: WROTE dir={output} artifacts={ARTIFACT_COUNT} files={len(files) + 1} "
        f"package_set={manifest['package_set_sha256']} G6=not-run release=no"
    )
    return manifest


def run_verifier(directory: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "verify.py"], cwd=directory,
        env={"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0"},
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False,
    )


def verify(directory: Path) -> dict[str, Any]:
    if directory.is_symlink() or not directory.is_dir():
        raise ShipError(f"R6 ship directory is missing: {directory}")
    completed = run_verifier(directory)
    if completed.returncode:
        raise ShipError(f"R6 offline verification failed:\n{completed.stdout}")
    print(completed.stdout.strip())
    return load(directory / "manifest.json", "R6 ship manifest")


def mutate_file(path: Path, offset: int = 0) -> None:
    os.chmod(path, 0o644)
    data = bytearray(path.read_bytes())
    if not data:
        raise ShipError(f"cannot mutate empty file: {path}")
    data[offset % len(data)] ^= 1
    path.write_bytes(data)


def negative_test(directory: Path) -> None:
    for mutation in contract()["negative_tests"]:
        with tempfile.TemporaryDirectory(prefix=f"r6-negative-{mutation}-") as raw:
            target = Path(raw) / "ship"
            shutil.copytree(directory, target)
            if mutation == "product-byte":
                mutate_file(target / "components/lisp65.prg")
            elif mutation == "manifest":
                path = target / "manifest.json"
                os.chmod(path, 0o644)
                value = load(path, "mutant manifest")
                value["status"] = "release-capable"
                path.write_bytes(canonical_json(value))
            elif mutation == "r5-archive":
                mutate_file(target / f"evidence/{R5_ID}.tar.gz", 64)
            else:
                raise ShipError(f"unknown R6 mutation: {mutation}")
            completed = run_verifier(target)
            if completed.returncode == 0:
                raise ShipError(f"R6 verifier accepted mutation: {mutation}")
    print("r6-ship: NEGATIVE PASS mutations=3 product-byte+manifest+r5-archive")


def compare(first: Path, second: Path) -> tuple[int, str]:
    def rows(root: Path) -> list[tuple[str, int, str, int]]:
        result: list[tuple[str, int, str, int]] = []
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
            if path.is_symlink():
                raise ShipError(f"R6 comparison found symlink: {path}")
            if path.is_file():
                result.append((path.relative_to(root).as_posix(), path.stat().st_size, sha(path), stat.S_IMODE(path.stat().st_mode)))
        return result
    left, right = rows(first), rows(second)
    if left != right:
        raise ShipError("R6 package double-pack differs")
    digest = sha_bytes(json.dumps(left, separators=(",", ":")).encode("ascii"))
    print(f"r6-ship: REPRO PASS files={len(left)} comparison_sha256={digest}")
    return len(left), digest


def write_receipt(*, source_commit: str, first: Path, second: Path, output: Path) -> None:
    canonical_commit(source_commit)
    first_manifest = verify(first)
    second_manifest = verify(second)
    count, comparison_sha = compare(first, second)
    negative_test(first)
    if first_manifest != second_manifest:
        raise ShipError("R6 package manifests differ")
    value = contract()
    receipt = {
        "format": RECEIPT_FORMAT, "version": 1,
        "id": "r6-two-media-ship-packer", "status": "passed-not-g6",
        "source_commit": source_commit, "measured_on": first_manifest["packed_on"],
        "contract": {"path": CONTRACT.relative_to(ROOT).as_posix(), "sha256": sha(CONTRACT)},
        "inputs": value["input"],
        "product": {
            "artifact_set_sha256": PRODUCT_SET, "artifact_count": ARTIFACT_COUNT,
            "byte_identical_artifacts": ARTIFACT_COUNT, "product_sha_changes": 0,
        },
        "media": {
            "L65SYS": {"bytes": 819200, "entries": 10, "identity": "L65SYS,65", "mode": "0444"},
            "L65WORK": {"bytes": 819200, "entries": 0, "identity": "L65WORK,65", "mode": "0644"},
            "d81_entry_byte_identity": "10/10",
        },
        "package": {
            "format": FORMAT, "manifest_sha256": sha(first / "manifest.json"),
            "package_set_sha256": first_manifest["package_set_sha256"],
            "file_count": count, "self_contained": True,
        },
        "reproducibility": {
            "packs": 2, "byte_and_mode_identical": True,
            "comparison_sha256": comparison_sha,
            "varied_environment": ["PYTHONHASHSEED", "TZ"],
        },
        "verification": {
            "offline_package_only": "passed-both-packs",
            "nested_R4_verifier": "passed", "nested_R5_verifier": "passed",
            "negative_mutations_rejected": ["product-byte", "manifest", "r5-archive"],
        },
        "capacity_delta": value["capacity_delta"], "claims": value["claims"],
        "result": "passed",
    }
    data = canonical_json(receipt)
    if output.exists() or output.is_symlink():
        if output.is_symlink() or not output.is_file() or output.read_bytes() != data:
            raise ShipError(f"refusing to overwrite differing R6 receipt: {output}")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
    print(f"r6-ship: RECEIPT PASS output={output} files={count} mutations=3 G6=not-run")


def verify_receipt(path: Path) -> dict[str, Any]:
    value = load(path, "R6 ship packer receipt")
    exact(
        value,
        {
            "format", "version", "id", "status", "source_commit", "measured_on",
            "contract", "inputs", "product", "media", "package",
            "reproducibility", "verification", "capacity_delta", "claims", "result",
        },
        "R6 ship packer receipt",
    )
    # A passed receipt binds the packer/verifier bytes at its source commit.
    # Later live verifier fixes must not retroactively invalidate that sealed
    # package proof; only its still-live contract must remain byte-identical.
    source_commit = canonical_commit(
        value["source_commit"], historical_verification=True,
    )
    expected = contract()
    reproducibility = exact(
        value["reproducibility"],
        {"packs", "byte_and_mode_identical", "comparison_sha256", "varied_environment"},
        "R6 receipt reproducibility",
    )
    verification = exact(
        value["verification"],
        {"offline_package_only", "nested_R4_verifier", "nested_R5_verifier", "negative_mutations_rejected"},
        "R6 receipt verification",
    )
    if (
        value["format"] != RECEIPT_FORMAT or value["version"] != 1
        or value["id"] != "r6-two-media-ship-packer"
        or value["status"] != "passed-not-g6"
        or not isinstance(value["measured_on"], str)
        or not DATE_RE.fullmatch(value["measured_on"])
        or value["measured_on"] != canonical_commit_date(source_commit)
        or value["result"] != "passed"
        or value["contract"] != {
            "path": CONTRACT.relative_to(ROOT).as_posix(), "sha256": sha(CONTRACT),
        }
        or value["inputs"] != expected["input"]
        or value["product"] != {
            "artifact_set_sha256": PRODUCT_SET, "artifact_count": ARTIFACT_COUNT,
            "byte_identical_artifacts": ARTIFACT_COUNT, "product_sha_changes": 0,
        }
        or value["media"] != {
            "L65SYS": {"bytes": 819200, "entries": 10, "identity": "L65SYS,65", "mode": "0444"},
            "L65WORK": {"bytes": 819200, "entries": 0, "identity": "L65WORK,65", "mode": "0644"},
            "d81_entry_byte_identity": "10/10",
        }
        or reproducibility != {
            "packs": 2, "byte_and_mode_identical": True,
            "comparison_sha256": reproducibility["comparison_sha256"],
            "varied_environment": ["PYTHONHASHSEED", "TZ"],
        }
        or verification != {
            "offline_package_only": "passed-both-packs",
            "nested_R4_verifier": "passed", "nested_R5_verifier": "passed",
            "negative_mutations_rejected": ["product-byte", "manifest", "r5-archive"],
        }
        or value["capacity_delta"] != expected["capacity_delta"]
        or value["claims"] != expected["claims"]
    ):
        raise ShipError("R6 ship packer receipt semantic drift")
    package = exact(
        value["package"],
        {"format", "manifest_sha256", "package_set_sha256", "file_count", "self_contained"},
        "R6 receipt package",
    )
    if (
        package["format"] != FORMAT or package["file_count"] != 25
        or package["self_contained"] is not True
        or not SHA_RE.fullmatch(package["manifest_sha256"])
        or not SHA_RE.fullmatch(package["package_set_sha256"])
        or not SHA_RE.fullmatch(reproducibility["comparison_sha256"])
        or source_commit != value["source_commit"]
    ):
        raise ShipError("R6 ship packer receipt measurement drift")
    print(
        f"r6-ship: RECEIPT CHECK PASS source={source_commit[:12]} "
        f"files={package['file_count']} G6=not-run release=no"
    )
    return value


def selftest() -> None:
    value = contract()
    r4, r5 = registered_inputs(value)
    if sha(r4) != R4_SHA or sha(r5) != R5_SHA:
        raise ShipError("R6 selftest input binding drift")
    if (
        value["claims"]["G6"]
        != "not-run(5/5-applicable); execution=single-device; product-medium-physical-write-protect=n/a-no-physical-medium-in-SD-D81-configuration"
        or value["claims"]["function_metadata"]
        != "101-exact/34-unresolved-no-complete-help-claim"
        or value["claims"]["release"] != "not-release-capable"
    ):
        raise ShipError("R6 selftest claim drift")
    if TRACKED_RECEIPT.exists():
        verify_receipt(TRACKED_RECEIPT)
    print(f"r6-ship: SELFTEST PASS operation=transform-only artifacts={ARTIFACT_COUNT} G6=not-run release=no")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)
    sub.add_parser("selftest")
    pack = sub.add_parser("pack")
    pack.add_argument("--source-commit", required=True)
    pack.add_argument("--packed-on", required=True)
    pack.add_argument("--out", type=Path, required=True)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("directory", type=Path)
    negative = sub.add_parser("negative-test")
    negative.add_argument("directory", type=Path)
    compare_parser = sub.add_parser("compare")
    compare_parser.add_argument("first", type=Path)
    compare_parser.add_argument("second", type=Path)
    receipt = sub.add_parser("receipt")
    receipt.add_argument("--source-commit", required=True)
    receipt.add_argument("--first", type=Path, required=True)
    receipt.add_argument("--second", type=Path, required=True)
    receipt.add_argument("--out", type=Path, required=True)
    receipt_check = sub.add_parser("receipt-check")
    receipt_check.add_argument("receipt", nargs="?", type=Path, default=TRACKED_RECEIPT)
    return result


def rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "selftest":
            selftest()
        elif args.command == "pack":
            build(source_commit=args.source_commit, packed_on=args.packed_on, output=rooted(args.out))
        elif args.command == "verify":
            verify(rooted(args.directory))
        elif args.command == "negative-test":
            negative_test(rooted(args.directory))
        elif args.command == "compare":
            compare(rooted(args.first), rooted(args.second))
        elif args.command == "receipt":
            write_receipt(source_commit=args.source_commit, first=rooted(args.first), second=rooted(args.second), output=rooted(args.out))
        else:
            verify_receipt(rooted(args.receipt))
        return 0
    except (
        ShipError, OFFLINE.VerifyError, CAPACITY.CapacityDeltaError,
        OSError, ValueError, KeyError, TypeError, json.JSONDecodeError,
    ) as exc:
        print(f"r6-ship: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
