#!/usr/bin/env python3
"""Verify the complete C2-lite R6/G6 acceptance closure without hardware."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any


SCRIPT_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_FORMAT = "lisp65-c2-lite-r6-g6-hardware-archive-v1"
PRODUCT_SET = "37998ce7b6698757fe3839d0af1467e95505fe10e6be6bc7f28a6991cb09941d"
PACKAGE_SET = "82ddc3d7fd8bc048b2803081866aa5320a08bd226d18b063c403a33fc9e7e038"
R6_SHIP_REL = Path(
    "build/c2.2/acceptance/r6-successor-v11/ship"
)
R6_RECEIPT_REL = Path(
    "build/c2.2/acceptance/r6-successor-v11/r6-packaging-receipt.json"
)
G6_SESSION_REL = Path(
    "build/c2.2/acceptance/g6-successor-v11/session-01"
)
TOP_RELEASE_CLAIM = "not-promoted-until-remote-head-seal"
SEAL_RELEASE_CLAIM = "promoted-v1.2"
RELEASE_LABEL = "v1.2"
CASE_IDS = (
    "offline-package-verification",
    "cold-boot-from-exact-R6-product-media",
    "always-restage-and-target-readback",
    "work-media-write-read-power-cycle",
    "product-media-remains-byteidentical",
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SHA1_RE = re.compile(r"^[0-9a-f]{40}$")


class VerifyError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise VerifyError(message)


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path: Path, label: str) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"{label} missing")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=strict_object,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise VerifyError(f"cannot read {label}: {error}") from error
    require(isinstance(value, dict), f"{label} must be an object")
    return value


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def safe_path(root: Path, value: Any, label: str) -> Path:
    require(isinstance(value, str) and value, f"{label} path missing")
    pure = PurePosixPath(value)
    require(
        not pure.is_absolute() and pure.as_posix() == value
        and ".." not in pure.parts,
        f"{label} path unsafe: {value}",
    )
    return root / Path(*pure.parts)


def verify_binding(root: Path, value: Any, label: str) -> Path:
    require(
        isinstance(value, dict)
        and {"path", "bytes", "sha256"} <= set(value),
        f"{label} binding malformed",
    )
    path = safe_path(root, value["path"], label)
    require(
        type(value["bytes"]) is int
        and isinstance(value["sha256"], str)
        and SHA256_RE.fullmatch(value["sha256"]) is not None
        and path.is_file() and not path.is_symlink()
        and path.stat().st_size == value["bytes"]
        and sha(path) == value["sha256"],
        f"{label} byte binding drift",
    )
    return path


def verify_nested_bindings(root: Path, value: Any, label: str) -> int:
    count = 0
    if isinstance(value, dict):
        if {"path", "bytes", "sha256"} <= set(value):
            verify_binding(root, value, label)
            count += 1
        for key, child in value.items():
            count += verify_nested_bindings(root, child, f"{label}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            count += verify_nested_bindings(root, child, f"{label}[{index}]")
    return count


def verify_r6(root: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    ship_root = root / R6_SHIP_REL
    manifest_path = ship_root / "manifest.json"
    receipt_path = root / R6_RECEIPT_REL
    manifest = load(manifest_path, "R6 manifest")
    receipt = load(receipt_path, "R6 receipt")
    require(
        manifest.get("format") == "lisp65-c2-lite-R6-package-v1"
        and manifest.get("status") == "passed-transform-and-package-only"
        and manifest.get("result") == "passed"
        and receipt.get("format") == "lisp65-c2-lite-R6-packaging-receipt-v1"
        and receipt.get("status") == "passed-R6-package"
        and receipt.get("result") == "passed"
        and receipt.get("product_artifact_set_sha256") == PRODUCT_SET
        and receipt.get("package_set_sha256") == PACKAGE_SET,
        "R6 identity or claim drift",
    )
    product = manifest.get("product")
    require(
        isinstance(product, dict)
        and product.get("artifact_count") == 19
        and product.get("artifact_set_sha256") == PRODUCT_SET,
        "R6 product identity drift",
    )
    rows = product.get("artifacts")
    require(isinstance(rows, list) and len(rows) == 19, "R6 role closure drift")
    roles: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        require(
            isinstance(row, dict)
            and isinstance(row.get("role"), str)
            and row["role"] not in roles,
            f"R6 role row malformed: {index}",
        )
        path = safe_path(
            ship_root,
            row.get("ship_path"), f"R6 role {row['role']}",
        )
        require(
            path.is_file() and not path.is_symlink()
            and path.stat().st_size == row.get("bytes")
            and sha(path) == row.get("sha256"),
            f"R6 role byte drift: {row['role']}",
        )
        roles[row["role"]] = row
    files = manifest.get("files")
    require(isinstance(files, list) and files, "R6 package inventory missing")
    for index, row in enumerate(files):
        require(
            isinstance(row, dict) and set(row) == {
                "path", "bytes", "sha256", "mode",
            },
            f"R6 package row malformed: {index}",
        )
        path = safe_path(
            ship_root,
            row["path"], f"R6 package file {index}",
        )
        require(
            path.is_file() and not path.is_symlink()
            and path.stat().st_size == row["bytes"]
            and sha(path) == row["sha256"],
            f"R6 package file drift: {row['path']}",
        )
    verify_nested_bindings(root, receipt, "R6 receipt")
    return manifest, roles


def verify_acceptance(root: Path) -> dict[str, Any]:
    manifest, roles = verify_r6(root)
    session = root / G6_SESSION_REL
    top_path = session / "g6-hardware-receipt.json"
    top = load(top_path, "G6 top receipt")
    require(
        top.get("format") == "lisp65-c2-lite-G6-hardware-receipt-v2"
        and top.get("version") == 2
        and top.get("status") == "passed-five-of-five"
        and top.get("result") == "passed"
        and top.get("product_artifact_set_sha256") == PRODUCT_SET
        and top.get("claims") == {
            "G5": "passed-nine-of-nine",
            "G6": "passed-five-of-five",
            "release": TOP_RELEASE_CLAIM,
        },
        "G6 top receipt drift",
    )
    verify_binding(root, top.get("R6_manifest"), "G6 R6 manifest")
    cases = top.get("cases")
    require(isinstance(cases, list) and len(cases) == 5, "G6 case closure drift")
    case_values: list[dict[str, Any]] = []
    binding_count = verify_nested_bindings(root, top, "G6 top")
    for index, expected in enumerate(CASE_IDS):
        row = cases[index]
        require(
            isinstance(row, dict) and row.get("id") == expected,
            f"G6 case order drift: {index + 1}",
        )
        receipt_path = verify_binding(
            root, row.get("receipt"), f"G6 case {index + 1}",
        )
        receipt = load(receipt_path, f"G6 case {index + 1} receipt")
        require(
            receipt.get("format") == "lisp65-c2-lite-G6-case-receipt-v1"
            and receipt.get("id") == expected
            and receipt.get("status") == "passed"
            and receipt.get("result") == "passed"
            and receipt.get("product_artifact_set_sha256") == PRODUCT_SET,
            f"G6 case {index + 1} claim drift",
        )
        binding_count += verify_nested_bindings(
            root, receipt, f"G6 case {index + 1} receipt",
        )
        case_values.append(receipt)

    case4 = case_values[3]
    require(
        case4.get("procedure", {}).get("read_after_cycle") == {
            "file": "g6r6", "content": ["persist"], "status": 0,
        }
        and isinstance(case4.get("cycle_id"), str),
        "G6 work-media persistence claim drift",
    )
    case5 = case_values[4]
    media = case5.get("media_readback")
    require(
        isinstance(media, dict)
        and media.get("product_comparison") == "byteidentical"
        and media.get("work_comparison")
        == "changed-only-by-authorized-G6-work-write",
        "G6 final-media comparison drift",
    )
    product_after = verify_binding(
        root, media.get("product"), "G6 final product medium",
    )
    work_payload = verify_binding(
        root, media.get("work_payload"), "G6 final work payload",
    )
    require(
        sha(product_after) == roles["product-d81"]["sha256"]
        and b"persist" in work_payload.read_bytes().lower(),
        "G6 final-media content drift",
    )
    require(
        manifest["product"]["artifact_set_sha256"] == PRODUCT_SET,
        "R6/G6 product-set divergence",
    )
    print(
        "C2-LITE G6 OFFLINE PASS "
        f"cases=5 bindings={binding_count} set={PRODUCT_SET}"
    )
    return top


def verify_archive() -> None:
    archive_manifest = load(SCRIPT_ROOT / "manifest.json", "seal manifest")
    require(
        archive_manifest.get("format") == ARCHIVE_FORMAT
        and archive_manifest.get("version") == 2
        and archive_manifest.get("kind") == "hardware-acceptance"
        and archive_manifest.get("status") == "sealed"
        and archive_manifest.get("product_artifact_set_sha256") == PRODUCT_SET
        and archive_manifest.get("R6_package_set_sha256") == PACKAGE_SET
        and archive_manifest.get("result") == "passed",
        "seal manifest identity drift",
    )
    source = archive_manifest.get("source_commit")
    remote = archive_manifest.get("remote_source_binding")
    require(
        isinstance(source, str) and SHA1_RE.fullmatch(source) is not None
        and isinstance(remote, dict)
        and remote.get("source_commit") == source
        and SHA1_RE.fullmatch(str(remote.get("remote_head"))) is not None
        and remote.get("relation") == "source-commit-is-remote-ancestor",
        "seal remote-source binding drift",
    )
    rows = archive_manifest.get("files")
    require(isinstance(rows, list) and rows, "seal file inventory missing")
    expected: set[str] = set()
    for index, row in enumerate(rows):
        require(
            isinstance(row, dict)
            and set(row) == {"path", "bytes", "sha256", "mode"},
            f"seal file row malformed: {index}",
        )
        path = safe_path(SCRIPT_ROOT, row["path"], f"seal file {index}")
        require(
            path.is_file() and not path.is_symlink()
            and path.stat().st_size == row["bytes"]
            and sha(path) == row["sha256"],
            f"seal payload drift: {row['path']}",
        )
        expected.add(row["path"])
    actual = {
        path.relative_to(SCRIPT_ROOT).as_posix()
        for path in SCRIPT_ROOT.rglob("*")
        if path.is_file()
        and path not in {
            SCRIPT_ROOT / "manifest.json",
            SCRIPT_ROOT / "verify.py",
        }
    }
    require(actual == expected, "seal payload file-set drift")
    top = verify_acceptance(SCRIPT_ROOT / "payload")
    require(
        archive_manifest.get("top_receipt_sha256")
        == sha(SCRIPT_ROOT / "payload" / G6_SESSION_REL
               / "g6-hardware-receipt.json")
        and archive_manifest.get("claims") == {
            "G5": "passed-nine-of-nine",
            "G6": "passed-five-of-five",
            "release": SEAL_RELEASE_CLAIM,
        }
        and top["claims"]["release"]
        == TOP_RELEASE_CLAIM,
        "seal promotion boundary drift",
    )
    print(
        "C2-LITE R6/G6 SEAL OFFLINE PASS "
        f"files={len(rows)} source={source} release={RELEASE_LABEL}"
    )


def main() -> int:
    try:
        if (SCRIPT_ROOT / "manifest.json").is_file():
            verify_archive()
        else:
            verify_acceptance(REPOSITORY_ROOT)
        return 0
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, VerifyError) as error:
        print(f"C2-LITE G6 OFFLINE FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
