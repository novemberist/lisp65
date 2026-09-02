#!/usr/bin/env python3
"""Standard-library-only verifier for the lisp65 1.0.1-light bundle."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "manifest.json"
FORMAT = "lisp65-r7-release-manifest-v1"
PRODUCT_SET = "c41b9643ada1195f48c384d9d582a3d870a68c4ccc3dee9500dc86a7f009c165"
SOURCE_COMMIT = "547947116b9660042488a63c0ae336c4cb926eeb"
SOURCE_SEAL_SHA = "b339a274a97c947025ce66b09cd54ce5af73e24d8a99328fcb0659ffa605ddba"
SEALED_SHIP_MANIFEST_SHA = "323d6f497c1849af3916cfbe9c3f0d73936eaa72f271d97412666f25369f6764"
G6_RECEIPT_SHA = "edcca70cc747be2b42ab20ee96c74dceb46e490125dc4c6d740a7d1b4c369b7d"
CURRENT_SHIP_MANIFEST_SHA = "e04f3f99589ba956ec2e9bb21e932a4f4bb5fe18e85a07fe463c42252d2c8801"
PACKAGE_REBIND_SHA = "18b3993cc3b1946ba925dd5ad2f26dd378959e0656d1d44e27b461785131f80a"
STATIC_PREFLIGHT_SHA = "c920bab3dcbdfc4b48e4b9bbd1eb3aec6d8150124910843e246db439171981b6"
PROFILE_APPLICABILITY_SHA = "68004ed076eff7c0c7d1d91030279a18fc061b7ee9cd06df960726a6c4fadd17"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


class VerifyError(RuntimeError):
    pass


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise VerifyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise VerifyError(f"{label} must be a regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerifyError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise VerifyError(f"{label} must contain an object")
    return value


def exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise VerifyError(f"{label} schema drift")
    return value


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def lower_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise VerifyError(f"{label} must be a lowercase SHA-256")
    return value


def relative(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise VerifyError(f"{label} must be a nonempty relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or ".." in path.parts:
        raise VerifyError(f"{label} escapes the bundle")
    return value


def bundle_file(value: Any, digest: Any, label: str) -> Path:
    name = relative(value, label)
    path = ROOT / Path(*PurePosixPath(name).parts)
    if path.is_symlink() or not path.is_file() or sha(path) != lower_sha(digest, label):
        raise VerifyError(f"{label} binding drift")
    return path


def artifact_set_sha(rows: list[dict[str, Any]]) -> str:
    values = [
        {key: row[key] for key in ("role", "name", "bytes", "sha256")}
        for row in sorted(rows, key=lambda row: (row["role"], row["name"]))
    ]
    return sha_bytes(json.dumps(values, sort_keys=True, separators=(",", ":")).encode("ascii"))


def package_set_sha(rows: list[dict[str, Any]]) -> str:
    values = [
        {key: row[key] for key in ("path", "bytes", "sha256", "mode")}
        for row in sorted(rows, key=lambda row: row["path"])
    ]
    return sha_bytes(json.dumps(values, sort_keys=True, separators=(",", ":")).encode("ascii"))


def verify_inventory(manifest: dict[str, Any]) -> None:
    rows = manifest["files"]
    if not isinstance(rows, list) or not rows:
        raise VerifyError("bundle inventory is empty")
    expected: list[str] = []
    for index, raw in enumerate(rows):
        row = exact(raw, {"path", "bytes", "sha256", "mode"}, f"file[{index}]")
        name = relative(row["path"], f"file[{index}].path")
        path = ROOT / Path(*PurePosixPath(name).parts)
        if (
            type(row["bytes"]) is not int or row["bytes"] < 0
            or not isinstance(row["mode"], str) or not re.fullmatch(r"0[0-7]{3}", row["mode"])
            or path.is_symlink() or not path.is_file()
            or path.stat().st_size != row["bytes"]
            or sha(path) != lower_sha(row["sha256"], f"file[{index}].sha256")
            or stat.S_IMODE(path.stat().st_mode) != int(row["mode"], 8)
        ):
            raise VerifyError(f"bundle file drift: {name}")
        expected.append(name)
    if expected != sorted(set(expected)):
        raise VerifyError("bundle paths must be sorted and unique")
    actual: list[str] = []
    for path in ROOT.rglob("*"):
        if path.is_symlink():
            raise VerifyError(f"bundle contains symlink: {path}")
        if path.is_file() and path != MANIFEST:
            actual.append(path.relative_to(ROOT).as_posix())
    if sorted(actual) != expected or package_set_sha(rows) != manifest["package_set_sha256"]:
        raise VerifyError("bundle inventory is not exact")


def safe_extract(archive_path: Path, directory: Path) -> None:
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            for member in archive.getmembers():
                name = PurePosixPath(member.name)
                if name.is_absolute() or ".." in name.parts or not member.isfile():
                    raise VerifyError("source seal contains unsafe/non-file member")
            archive.extractall(directory, filter="data")
    except (OSError, tarfile.TarError) as exc:
        raise VerifyError(f"cannot extract source seal: {exc}") from exc


def verify_source_seal(path: Path) -> tuple[tempfile.TemporaryDirectory[str], Path, dict[str, Any], dict[str, Any]]:
    if sha(path) != SOURCE_SEAL_SHA:
        raise VerifyError("source seal SHA drift")
    temporary = tempfile.TemporaryDirectory(prefix="lisp65-r7-source-seal-")
    directory = Path(temporary.name)
    safe_extract(path, directory)
    verifier = directory / "verify.py"
    if verifier.is_symlink() or not verifier.is_file():
        temporary.cleanup()
        raise VerifyError("source seal lacks verifier")
    completed = subprocess.run(
        [sys.executable, "verify.py"], cwd=directory,
        env={"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "TZ": "UTC"},
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False,
    )
    if completed.returncode:
        temporary.cleanup()
        raise VerifyError(f"source seal verification failed: {completed.stdout.strip()}")
    seal_manifest = load(directory / "manifest.json", "source seal manifest")
    top_path = directory / "payload/build/r6/g6/run-20260715-02-preflight-212f957/g6-hardware-receipt.json"
    ship_path = directory / "payload/build/r6/ship/manifest.json"
    if sha(top_path) != G6_RECEIPT_SHA or sha(ship_path) != SEALED_SHIP_MANIFEST_SHA:
        temporary.cleanup()
        raise VerifyError("source seal G6/Ship binding drift")
    top = load(top_path, "sealed G6 receipt")
    ship = load(ship_path, "sealed R6 Ship manifest")
    return temporary, directory, top, ship


def no_absolute_strings(value: Any) -> bool:
    if isinstance(value, dict):
        return all(no_absolute_strings(item) for item in value.values())
    if isinstance(value, list):
        return all(no_absolute_strings(item) for item in value)
    return not (isinstance(value, str) and value.startswith("/"))


def verify_package_rebind(
    directory: Path,
    sealed_ship: dict[str, Any],
    current_ship: dict[str, Any],
    rebind: dict[str, Any],
    preflight: dict[str, Any],
    profile: dict[str, Any],
) -> None:
    if (
        current_ship.get("product", {}).get("artifact_set_sha256") != PRODUCT_SET
        or current_ship.get("product", {}).get("artifact_count") != 13
        or preflight.get("format") != "lisp65-r6-g6-static-preflight-v2"
        or preflight.get("status") != "passed-hardware-not-run"
        or preflight.get("result") != "passed"
        or preflight.get("ship", {}).get("manifest_sha256") != CURRENT_SHIP_MANIFEST_SHA
        or preflight.get("ship", {}).get("product_artifact_set_sha256") != PRODUCT_SET
        or preflight.get("counts") != {
            "G6_profile_not_applicable": 1, "G6_ready_not_run": 5,
            "sealed_G3_pass": 9, "total": 15,
        }
        or profile.get("format") != "lisp65-r6-g6-profile-applicability-receipt-v1"
        or profile.get("status") != "not-applicable-profile-bound"
        or profile.get("result") != "profile-not-applicable"
        or profile.get("ship", {}).get("manifest_sha256") != CURRENT_SHIP_MANIFEST_SHA
        or profile.get("ship", {}).get("product_artifact_set_sha256") != PRODUCT_SET
        or profile.get("applicability", {}).get("result") != "not-applicable-no-physical-medium-in-SD-D81-configuration"
        or profile.get("applicability", {}).get("synthetic_pass_attempted") is not False
        or profile.get("product_code_path_audit", {}).get("dedicated_F011_write_protect_signal_paths") != []
    ):
        raise VerifyError("1.0.1 preflight/profile semantic drift")

    historical = rebind.get("historical_g6", {})
    identity = rebind.get("product_identity", {})
    new_package = rebind.get("new_package", {})
    policy = rebind.get("receipt_policy", {})
    if (
        rebind.get("format") != "lisp65-r6-package-rebind-101-v1"
        or rebind.get("id") != "lisp65-1.0.1-light-package-rebind"
        or rebind.get("status") != "passed-no-hardware-rerun"
        or rebind.get("result") != "passed"
        or rebind.get("release") != {"scope": "package-and-documentation-only", "version": "1.0.1"}
        or historical.get("archive_sha256") != SOURCE_SEAL_SHA
        or historical.get("ship_manifest_sha256") != SEALED_SHIP_MANIFEST_SHA
        or historical.get("top_receipt_sha256") != G6_RECEIPT_SHA
        or new_package.get("ship_manifest_sha256") != CURRENT_SHIP_MANIFEST_SHA
        or new_package.get("static_preflight_sha256") != STATIC_PREFLIGHT_SHA
        or identity.get("historical_artifact_set_sha256") != PRODUCT_SET
        or identity.get("new_artifact_set_sha256") != PRODUCT_SET
        or identity.get("artifact_count") != 13
        or identity.get("byte_identical_artifacts") != 13
        or identity.get("product_sha_changes") != 0
        or policy.get("hardware_cases_reexecuted") != 0
        or policy.get("hardware_receipts_reused") != 5
        or policy.get("new_static_preflight") != "passed"
        or policy.get("offline_historical_seal_verification") != "passed"
    ):
        raise VerifyError("1.0.1 package-rebind semantic drift")

    sealed_rows = {
        row.get("role"): row for row in sealed_ship.get("artifacts", [])
        if isinstance(row, dict) and isinstance(row.get("role"), str)
    }
    current_rows = {
        row.get("role"): row for row in current_ship.get("artifacts", [])
        if isinstance(row, dict) and isinstance(row.get("role"), str)
    }
    rebound_rows = {
        row.get("role"): row for row in identity.get("artifacts", [])
        if isinstance(row, dict) and isinstance(row.get("role"), str)
    }
    if len(sealed_rows) != 13 or set(current_rows) != set(sealed_rows) or set(rebound_rows) != set(sealed_rows):
        raise VerifyError("1.0.1 artifact closure drift")
    for role, sealed in sealed_rows.items():
        current, rebound = current_rows[role], rebound_rows[role]
        if (
            any(current.get(key) != sealed.get(key) for key in ("name", "bytes", "sha256", "ship_path"))
            or any(rebound.get(key) != sealed.get(key) for key in ("name", "bytes", "sha256"))
            or rebound.get("byte_identical") is not True
        ):
            raise VerifyError(f"1.0.1 rebound product identity drift: {role}")

    cases = historical.get("cases")
    if not isinstance(cases, list) or len(cases) != 5:
        raise VerifyError("1.0.1 historical G6 receipt closure drift")
    for index, raw in enumerate(cases):
        row = exact(raw, {"cycle_id", "historical_receipt", "historical_receipt_sha256", "id", "status"}, f"rebind.case[{index}]")
        receipt_path = directory / "payload" / Path(*PurePosixPath(relative(row["historical_receipt"], "historical receipt")).parts)
        if (
            row["status"] != "passed-product-sha-bound-reused"
            or receipt_path.is_symlink() or not receipt_path.is_file()
            or sha(receipt_path) != lower_sha(row["historical_receipt_sha256"], "historical receipt SHA")
        ):
            raise VerifyError(f"1.0.1 historical G6 receipt drift: {row['id']}")


def verify() -> dict[str, Any]:
    manifest = load(MANIFEST, "release manifest")
    exact(
        manifest,
        {
            "format", "version", "status", "release", "source_commit", "packed_on",
            "packed_on_source", "input", "product", "claims", "toolchain", "evidence",
            "policy", "capacity_delta", "artifacts", "files", "package_set_sha256", "result",
        },
        "release manifest",
    )
    release = exact(manifest["release"], {"product", "version", "tag", "visibility", "dialect"}, "release")
    source = exact(
        manifest["input"],
        {
            "promotion_id", "archive_sha256", "sealed_ship_manifest_sha256", "g6_receipt_sha256",
            "current_ship_manifest_sha256", "package_rebind_receipt_sha256",
            "static_preflight_receipt_sha256", "profile_applicability_receipt_sha256",
        },
        "input",
    )
    product = exact(manifest["product"], {"artifact_set_sha256", "artifact_count", "product_sha_changes"}, "product")
    if (
        manifest["format"] != FORMAT or manifest["version"] != 1
        or manifest["status"] != "private-release"
        or release != {"product": "lisp65", "version": "1.0.1", "tag": "v1.0.1", "visibility": "private-mirror", "dialect": "v2"}
        or manifest["source_commit"] != SOURCE_COMMIT
        or manifest["packed_on_source"] != "tag-target-committer-timestamp"
        or source != {
            "promotion_id": "r6-g6-hardware-acceptance-aed1595",
            "archive_sha256": SOURCE_SEAL_SHA,
            "sealed_ship_manifest_sha256": SEALED_SHIP_MANIFEST_SHA,
            "g6_receipt_sha256": G6_RECEIPT_SHA,
            "current_ship_manifest_sha256": CURRENT_SHIP_MANIFEST_SHA,
            "package_rebind_receipt_sha256": PACKAGE_REBIND_SHA,
            "static_preflight_receipt_sha256": STATIC_PREFLIGHT_SHA,
            "profile_applicability_receipt_sha256": PROFILE_APPLICABILITY_SHA,
        }
        or product != {"artifact_set_sha256": PRODUCT_SET, "artifact_count": 13, "product_sha_changes": 0}
        or manifest["claims"] != {
            "G3": "passed-emulator-prefilter-only",
            "G5": "passed-for-product-artifact-set",
            "G6": "G6: 5/5 anwendbare Hardwarefälle bestanden; product-medium-physical-write-protect n/a: kein physisches Medium in der SD-D81-Konfiguration",
            "release": "private-release-v1.0.1-light",
        }
        or manifest["policy"] != {
            "operation": "documentation-and-package-only",
            "product_byte_source": "registered-r6-g6-seal-only",
            "product_byte_identity": "13/13-byte-identical-to-sealed-r6-ship-and-current-r6-package",
            "hardware_receipt_policy": "5/5-SHA-bound-G6-receipts-reused-0-hardware-cases-reexecuted",
            "offline_verification": "bundle-alone-no-repository-no-network",
        }
        or manifest["result"] != "passed"
        or not no_absolute_strings(manifest["toolchain"])
    ):
        raise VerifyError("release identity/claim drift")
    verify_inventory(manifest)
    rows = manifest["artifacts"]
    if not isinstance(rows, list) or len(rows) != 13 or artifact_set_sha(rows) != PRODUCT_SET:
        raise VerifyError("release product set drift")
    evidence = exact(
        manifest["evidence"],
        {
            "source_seal", "g6_receipt", "prerequisite_manifest", "prerequisite_receipt", "contract", "packer",
            "current_ship_manifest", "package_rebind_receipt", "static_preflight_receipt", "profile_applicability_receipt",
        },
        "evidence",
    )
    evidence_paths: dict[str, Path] = {}
    for name, raw in evidence.items():
        binding = exact(raw, {"path", "sha256"}, f"evidence.{name}")
        evidence_paths[name] = bundle_file(binding["path"], binding["sha256"], f"evidence.{name}")
    seal_row = exact(evidence["source_seal"], {"path", "sha256"}, "source seal evidence")
    seal_path = evidence_paths["source_seal"]
    temporary, directory, top, ship = verify_source_seal(seal_path)
    try:
        if (
            top.get("result") != "passed"
            or top.get("product_artifact_set_sha256") != PRODUCT_SET
            or top.get("claims") != manifest["claims"] | {"release": "not-promoted-until-R7"}
            or ship.get("product", {}).get("artifact_set_sha256") != PRODUCT_SET
        ):
            raise VerifyError("sealed G6 claim/product drift")
        verify_package_rebind(
            directory,
            ship,
            load(evidence_paths["current_ship_manifest"], "current R6 Ship manifest"),
            load(evidence_paths["package_rebind_receipt"], "1.0.1 package-rebind receipt"),
            load(evidence_paths["static_preflight_receipt"], "1.0.1 static-preflight receipt"),
            load(evidence_paths["profile_applicability_receipt"], "1.0.1 profile-applicability receipt"),
        )
        source_rows = {row["role"]: row for row in ship.get("artifacts", []) if isinstance(row, dict)}
        if len(source_rows) != 13:
            raise VerifyError("sealed R6 Ship artifact closure drift")
        for index, raw in enumerate(rows):
            row = exact(raw, {"role", "name", "bytes", "sha256", "bundle_path", "sealed_ship_path"}, f"artifact[{index}]")
            source_row = source_rows.get(row["role"])
            if not isinstance(source_row, dict):
                raise VerifyError(f"sealed product role missing: {row['role']}")
            final_path = bundle_file(row["bundle_path"], row["sha256"], f"artifact[{index}]")
            sealed_path = directory / "payload/build/r6/ship" / Path(*PurePosixPath(relative(row["sealed_ship_path"], "sealed_ship_path")).parts)
            if (
                row["name"] != source_row.get("name")
                or row["bytes"] != source_row.get("bytes")
                or row["sha256"] != source_row.get("sha256")
                or row["sealed_ship_path"] != source_row.get("ship_path")
                or final_path.stat().st_size != row["bytes"]
                or sealed_path.is_symlink() or not sealed_path.is_file()
                or final_path.read_bytes() != sealed_path.read_bytes()
            ):
                raise VerifyError(f"product byte identity drift: {row['role']}")
    finally:
        temporary.cleanup()
    dimensions = exact(manifest["capacity_delta"], {"bank", "ext", "symbols", "namepool", "directory"}, "capacity_delta")
    if any(exact(row, {"baseline", "candidate", "delta"}, f"capacity.{name}")["delta"] != 0 or row["baseline"] != row["candidate"] for name, row in dimensions.items()):
        raise VerifyError("release packaging capacity drift")
    if stat.S_IMODE(MANIFEST.stat().st_mode) != 0o444:
        raise VerifyError("release manifest mode drift")
    print("lisp65-r7-release: PASS version=1.0.1 dialect=v2 product=c41b9643ada1 G6=5/5-applicable-rebound WP=n/a")
    return manifest


def main() -> int:
    try:
        verify()
        return 0
    except (VerifyError, OSError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError, tarfile.TarError) as exc:
        print(f"lisp65-r7-release: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
