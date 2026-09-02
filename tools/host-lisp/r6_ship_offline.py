#!/usr/bin/env python3
"""Standard-library-only verifier for an R6 Workbench ship directory."""

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
FORMAT = "lisp65-r6-ship-v1"
CONTRACT_FORMAT = "lisp65-r6-ship-contract-v2"
PRODUCT_SET = "048639695dd7ad9c35bd8e92b2ec4c0fba1e365385cfc680e90bb3ba1a860024"
PRODUCT_BUILD_ID = "f144fd48"
ARTIFACT_COUNT = 14
R4_ID = "r4-product-candidate-726bdf8"
R4_SHA = "80d3eb000a5657659ed403423f5622c7b1e81b54079e818a9cc60e12a08a1024"
R5_ID = "r5-global-g5-8f66e77"
R5_SHA = "c64cab23c8272eea7e266bca0891331b40c108c9211755945a0d54cc123480c3"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


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
        raise VerifyError(f"{label} must be a regular non-symlink file")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=strict_object,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerifyError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise VerifyError(f"{label} must contain an object")
    return value


def exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise VerifyError(f"{label} keys drift: {actual}")
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
        raise VerifyError(f"{label} escapes the package: {value!r}")
    return value


def package_file(value: Any, digest: Any, label: str) -> Path:
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
    return sha_bytes(
        json.dumps(values, sort_keys=True, separators=(",", ":")).encode("ascii")
    )


def package_set_sha(rows: list[dict[str, Any]]) -> str:
    values = [
        {key: row[key] for key in ("path", "bytes", "sha256", "mode")}
        for row in sorted(rows, key=lambda row: row["path"])
    ]
    return sha_bytes(
        json.dumps(values, sort_keys=True, separators=(",", ":")).encode("ascii")
    )


def verify_inventory(manifest: dict[str, Any]) -> None:
    rows = manifest["files"]
    if not isinstance(rows, list) or not rows:
        raise VerifyError("package file inventory is empty")
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
            raise VerifyError(f"package file drift: {name}")
        expected.append(name)
    if expected != sorted(set(expected)):
        raise VerifyError("package paths must be sorted and unique")
    actual: list[str] = []
    for path in ROOT.rglob("*"):
        if path.is_symlink():
            raise VerifyError(f"package contains symlink: {path}")
        if path.is_file() and path != MANIFEST:
            actual.append(path.relative_to(ROOT).as_posix())
    if sorted(actual) != expected:
        raise VerifyError("package inventory is not exact")
    if package_set_sha(rows) != manifest["package_set_sha256"]:
        raise VerifyError("package set SHA recomputation drift")


def safe_extract(archive_path: Path, directory: Path) -> None:
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive.getmembers()
            for member in members:
                name = PurePosixPath(member.name)
                if name.is_absolute() or ".." in name.parts or not member.isfile():
                    raise VerifyError("nested archive contains unsafe/non-file member")
            archive.extractall(directory, filter="data")
    except (OSError, tarfile.TarError) as exc:
        raise VerifyError(f"cannot extract nested archive: {exc}") from exc


def verify_nested_archive(path: Path, expected_sha: str, label: str) -> tuple[dict[str, Any], Path, tempfile.TemporaryDirectory[str]]:
    if sha(path) != expected_sha:
        raise VerifyError(f"{label} archive SHA drift")
    temporary = tempfile.TemporaryDirectory(prefix=f"r6-{label}-")
    extracted = Path(temporary.name)
    safe_extract(path, extracted)
    verifier = extracted / "verify.py"
    manifest_path = extracted / "manifest.json"
    if verifier.is_symlink() or not verifier.is_file() or manifest_path.is_symlink() or not manifest_path.is_file():
        temporary.cleanup()
        raise VerifyError(f"{label} archive lacks embedded verifier/manifest")
    completed = subprocess.run(
        [sys.executable, "verify.py"], cwd=extracted,
        env={"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0"},
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False,
    )
    if completed.returncode:
        temporary.cleanup()
        raise VerifyError(f"{label} embedded verification failed: {completed.stdout.strip()}")
    return load(manifest_path, f"{label} manifest"), extracted, temporary


def sector(image: bytes, track: int, number: int) -> bytes:
    if not 1 <= track <= 80 or not 0 <= number < 40:
        raise VerifyError("D81 track/sector out of range")
    offset = ((track - 1) * 40 + number) * 256
    return image[offset:offset + 256]


def fold_name(raw: bytes) -> str:
    chars: list[str] = []
    for value in raw:
        value = value - 128 if value > 127 else value
        chars.append(chr(value) if 32 <= value < 127 else "?")
    return "".join(chars).rstrip()


def d81_identity(image: bytes) -> dict[str, str]:
    header = sector(image, 40, 0)
    return {"disk_name": fold_name(header[4:20]), "disk_id": fold_name(header[22:24])}


def d81_directory(image: bytes) -> dict[str, tuple[int, int]]:
    track, number, fuel = 40, 0, 64
    entries: dict[str, tuple[int, int]] = {}
    while fuel:
        fuel -= 1
        data = sector(image, track, number)
        first = 8 if (track, number) == (40, 0) else 0
        for index in range(first, 8):
            record = data[index * 32:(index + 1) * 32]
            if record[2] & 7:
                name = fold_name(record[5:21]).lower()
                if name in entries:
                    raise VerifyError(f"duplicate D81 entry: {name}")
                entries[name] = (record[3], record[4])
        track, number = data[0], data[1]
        if not track:
            return entries
        if track != 40 or number >= 40:
            raise VerifyError("invalid D81 directory chain")
    raise VerifyError("D81 directory chain fuel exhausted")


def d81_file(image: bytes, start: tuple[int, int]) -> bytes:
    track, number = start
    payload = bytearray()
    fuel = 512
    while track and fuel:
        fuel -= 1
        data = sector(image, track, number)
        next_track, next_sector = data[0], data[1]
        count = 254 if next_track else next_sector - 1
        if count < 0 or count > 254:
            raise VerifyError("invalid D81 file tail")
        payload.extend(data[2:2 + count])
        track, number = next_track, next_sector
    if track:
        raise VerifyError("D81 file chain fuel exhausted")
    return bytes(payload)


def verify_capacity_delta(value: Any) -> None:
    delta = exact(value, {"baseline_identity_sha256", "candidate_identity_sha256", "dimensions"}, "capacity_delta")
    if delta["baseline_identity_sha256"] != PRODUCT_SET or delta["candidate_identity_sha256"] != PRODUCT_SET:
        raise VerifyError("R6 packaging changed product identity")
    dimensions = exact(delta["dimensions"], {"bank", "ext", "symbols", "namepool", "directory"}, "capacity dimensions")
    for name, raw in dimensions.items():
        row = exact(raw, {"baseline", "candidate", "delta", "authorization"}, f"capacity {name}")
        if type(row["baseline"]) is not int or row["candidate"] != row["baseline"] or row["delta"] != 0 or row["authorization"] is not None:
            raise VerifyError(f"R6 packaging capacity drift: {name}")


def verify() -> dict[str, Any]:
    manifest = load(MANIFEST, "R6 ship manifest")
    exact(
        manifest,
        {
            "format", "version", "status", "profile", "source_commit", "packed_on",
            "contract", "contract_sha256", "product", "evidence", "toolchain",
            "gates", "policy", "media", "first_session", "artifacts", "files",
            "package_set_sha256", "result",
        },
        "R6 manifest",
    )
    if (
        manifest["format"] != FORMAT or manifest["version"] != 1
        or manifest["status"] != "packaged-g6-not-run"
        or manifest["profile"] != "dialect-v2"
        or not isinstance(manifest["source_commit"], str) or not COMMIT_RE.fullmatch(manifest["source_commit"])
        or not isinstance(manifest["packed_on"], str)
        or not DATE_RE.fullmatch(manifest["packed_on"])
        or manifest["result"] != "passed"
    ):
        raise VerifyError("R6 manifest identity/status drift")
    verify_inventory(manifest)
    contract_path = package_file(manifest["contract"], manifest["contract_sha256"], "R6 contract")
    contract = load(contract_path, "R6 contract")
    if (
        contract.get("format") != CONTRACT_FORMAT or contract.get("version") != 2
        or contract.get("id") != "r6-archive-to-ship" or contract.get("status") != "approved-for-packer"
        or contract.get("claims") != manifest["gates"]
        or contract.get("capacity_delta") != manifest["policy"].get("capacity_delta")
    ):
        raise VerifyError("R6 contract/manifest drift")
    expected_gates = {
        "G3": "passed-emulator-prefilter-only",
        "G5": "passed-for-product-artifact-set",
        "G6": "not-run(5/5-applicable); execution=single-device; product-medium-physical-write-protect=n/a-no-physical-medium-in-SD-D81-configuration",
        "function_metadata": "101-exact/34-unresolved-no-complete-help-claim",
        "hardware_boot_cases": "not-run(5/5-applicable); execution=single-device; n/a(1/1-profile-bound)",
        "release": "not-release-capable",
    }
    if manifest["gates"] != expected_gates:
        raise VerifyError("R6 claim boundary drift")
    policy = exact(manifest["policy"], {"operation", "product_sha_changes", "capacity_delta"}, "R6 policy")
    if policy["operation"] != "transform-and-package-only" or policy["product_sha_changes"] != 0:
        raise VerifyError("R6 packer performed a build/product mutation")
    verify_capacity_delta(policy["capacity_delta"])

    evidence = exact(
        manifest["evidence"],
        {"r4_archive", "r5_archive", "g3_receipt", "g5_receipt", "boot_matrix", "hardware_profile"},
        "R6 evidence",
    )
    profile_binding = exact(evidence["hardware_profile"], {"path", "sha256"}, "G6 hardware profile binding")
    profile_path = package_file(
        profile_binding["path"], profile_binding["sha256"],
        "G6 hardware profile",
    )
    if (
        contract.get("hardware_profile") != {
            "path": "config/g6-hardware-profile.json",
            "sha256": profile_binding["sha256"],
        }
        or load(profile_path, "G6 hardware profile").get("id") != "stock-core-sd-d81"
    ):
        raise VerifyError("R6 hardware profile binding drift")
    r4_binding = exact(evidence["r4_archive"], {"promotion_id", "path", "sha256"}, "R4 binding")
    r5_binding = exact(evidence["r5_archive"], {"promotion_id", "path", "sha256"}, "R5 binding")
    if r4_binding["promotion_id"] != R4_ID or r4_binding["sha256"] != R4_SHA:
        raise VerifyError("R4 evidence authority drift")
    if r5_binding["promotion_id"] != R5_ID or r5_binding["sha256"] != R5_SHA:
        raise VerifyError("R5 evidence authority drift")
    r4_path = package_file(r4_binding["path"], r4_binding["sha256"], "R4 archive")
    r5_path = package_file(r5_binding["path"], r5_binding["sha256"], "R5 archive")
    r4_manifest, r4_root, r4_tmp = verify_nested_archive(r4_path, R4_SHA, "r4")
    r5_manifest, r5_root, r5_tmp = verify_nested_archive(r5_path, R5_SHA, "r5")
    try:
        if r4_manifest.get("id") != R4_ID or r4_manifest.get("kind") != "product-candidate":
            raise VerifyError("nested R4 manifest drift")
        if r5_manifest.get("id") != R5_ID or r5_manifest.get("kind") != "hardware-acceptance":
            raise VerifyError("nested R5 manifest drift")
        r5_top_path = r5_root / "payload" / Path(*PurePosixPath(r5_manifest["top_receipt"]["path"]).parts)
        r5_top = load(r5_top_path, "nested R5 top receipt")
        product = exact(manifest["product"], {"artifact_set_sha256", "product_build_id", "artifact_count", "r4_promotion_id", "r5_promotion_id"}, "R6 product")
        if product != {
            "artifact_set_sha256": PRODUCT_SET,
            "product_build_id": PRODUCT_BUILD_ID,
            "artifact_count": ARTIFACT_COUNT,
            "r4_promotion_id": R4_ID,
            "r5_promotion_id": R5_ID,
        } or r5_top.get("product", {}).get("artifact_set_sha256") != PRODUCT_SET:
            raise VerifyError("R6/R5 product identity drift")
        source_rows = r5_top["product"]["artifacts"]
        rows = manifest["artifacts"]
        if not isinstance(rows, list) or len(rows) != ARTIFACT_COUNT or artifact_set_sha(source_rows) != PRODUCT_SET:
            raise VerifyError("R6 product artifact inventory drift")
        by_role = {row["role"]: row for row in source_rows}
        if len(by_role) != ARTIFACT_COUNT:
            raise VerifyError("nested R5 product roles are not unique")
        seen: set[str] = set()
        ship_bytes: dict[str, bytes] = {}
        for index, raw in enumerate(rows):
            row = exact(raw, {"role", "name", "source_path", "ship_path", "bytes", "sha256", "d81_entry", "identity"}, f"artifact[{index}]")
            source = by_role.get(row["role"])
            if source is None or row["role"] in seen or row["identity"] != "byte-identical-from-R5-archive":
                raise VerifyError(f"R6 artifact role/identity drift: {row['role']}")
            if {key: row[key] for key in ("role", "name", "bytes", "sha256")} != {key: source[key] for key in ("role", "name", "bytes", "sha256")} or row["source_path"] != source["path"]:
                raise VerifyError(f"R6 artifact metadata differs from R5: {row['role']}")
            ship_path = package_file(row["ship_path"], row["sha256"], f"artifact {row['role']}")
            nested_source = r5_root / "payload" / Path(*PurePosixPath(source["path"]).parts)
            if nested_source.is_symlink() or not nested_source.is_file() or ship_path.read_bytes() != nested_source.read_bytes():
                raise VerifyError(f"R6 artifact bytes differ from R5 archive: {row['role']}")
            if ship_path.stat().st_size != row["bytes"]:
                raise VerifyError(f"R6 artifact size drift: {row['role']}")
            seen.add(row["role"])
            ship_bytes[row["role"]] = ship_path.read_bytes()
        if seen != set(by_role):
            raise VerifyError("R6 artifact mapping is not exactly once")

        g3_path = package_file(evidence["g3_receipt"]["path"], evidence["g3_receipt"]["sha256"], "G3 receipt")
        g5_path = package_file(evidence["g5_receipt"]["path"], evidence["g5_receipt"]["sha256"], "G5 receipt")
        matrix_path = package_file(evidence["boot_matrix"]["path"], evidence["boot_matrix"]["sha256"], "boot matrix")
        r4_g3_source = r4_root / "payload/tests/bytecode/dialect-v2/evidence/r3/g3-emulator-receipt.json"
        r4_matrix_source = r4_root / "payload/tests/bytecode/dialect-v2/r3-boot/cases.json"
        if g3_path.read_bytes() != r4_g3_source.read_bytes() or matrix_path.read_bytes() != r4_matrix_source.read_bytes():
            raise VerifyError("G3/matrix bytes are not from sealed R4")
        if g5_path.read_bytes() != r5_top_path.read_bytes():
            raise VerifyError("G5 receipt bytes are not from sealed R5")
        g3 = load(g3_path, "G3 receipt")
        g5 = load(g5_path, "G5 receipt")
        cases = g3.get("cases", [])
        if (
            g3.get("status") != "passed-emulator-prefilter-only"
            or g3.get("product_artifact_set_sha256") != PRODUCT_SET
            or len(cases) != 15
            or sum(case.get("fidelity") == "emulator-valid" and case.get("status") == "pass" for case in cases) != 9
            or sum(case.get("fidelity") == "hardware-only" and case.get("status") == "not-run" for case in cases) != 6
            or g5.get("result") != "passed" or len(g5.get("cases", [])) != 14
            or g5.get("claims") != {
                "G5": "passed-for-product-artifact-set", "G6": "not-run",
                "function_metadata": "101-exact/34-unresolved-no-complete-help-claim",
                "hardware_boot_cases": (
                    "not-run(5/5-applicable); execution=single-device; "
                    "n/a(1/1-profile-bound)"
                ),
                "product_artifact_set_sha256": PRODUCT_SET,
                "release": "not-release-capable",
            }
        ):
            raise VerifyError("sealed G3/G5 result boundary drift")

        media = manifest["media"]
        if media != contract["media"]:
            raise VerifyError("R6 media contract drift")
        product_image = ship_bytes["product-d81"]
        work_image = ship_bytes["work-d81"]
        if len(product_image) != 819200 or len(work_image) != 819200:
            raise VerifyError("R6 D81 size drift")
        if d81_identity(product_image) != {"disk_name": "L65SYS", "disk_id": "65"} or d81_identity(work_image) != {"disk_name": "L65WORK", "disk_id": "65"}:
            raise VerifyError("R6 media identity drift")
        product_dir = d81_directory(product_image)
        work_dir = d81_directory(work_image)
        expected_entries = set(media["product"]["entries"])
        if set(product_dir) != expected_entries or work_dir:
            raise VerifyError("R6 product inventory/work blank-state drift")
        for row in rows:
            entry = row["d81_entry"]
            if entry is not None and d81_file(product_image, product_dir[entry]) != ship_bytes[row["role"]]:
                raise VerifyError(f"L65SYS entry is not byte-identical: {entry}")
        mount = json.loads(ship_bytes["product-mount-descriptor"], object_pairs_hook=strict_object)
        if mount != {
            "disk_id": "65", "disk_name": "L65SYS", "drive": 8,
            "format": "lisp65-product-mount-descriptor-v2",
            "media": "lisp65-product.d81", "media_sha256": sha_bytes(product_image),
            "mutable_entries": False,
            "write_protect": {
                "physical_floppy": "required-if-used",
                "stock_core_SD_D81": "unavailable-no-virtual-read-only-attach-control",
            },
        }:
            raise VerifyError("R6 mount descriptor drift")

        first = manifest["first_session"]
        if first != contract["first_session"]:
            raise VerifyError("R6 first-session contract drift")
        readme = package_file(first["readme"], next(row["sha256"] for row in manifest["files"] if row["path"] == first["readme"]), "README")
        readme_text = readme.read_text(encoding="ascii")
        if (
            any(form not in readme_text for form in first["forms"])
            or "G6: NOT RUN" not in readme_text or "RELEASE: NO" not in readme_text
            or "no virtual write-protect switch" not in readme_text
        ):
            raise VerifyError("R6 README claim/session drift")

        r3_contract = load(r4_root / "payload/config/r3-g3-g6-contract.json", "sealed R3 contract")
        packer = exact(
            manifest["toolchain"]["packer"],
            {"source_commit", "path", "sha256", "packaged_path"},
            "packer binding",
        )
        packaged_packer = package_file(
            packer["packaged_path"], packer["sha256"], "packaged packer source",
        )
        expected_toolchain = {
            "compiler": r3_contract["toolchain_bindings"]["compiler"],
            "c1541": r3_contract["toolchain_bindings"]["c1541"],
            "xmega65": r3_contract["toolchain_bindings"]["xmega65"],
            "rom": r3_contract["toolchain_bindings"]["rom"],
            "sd_base": r3_contract["toolchain_bindings"]["sd_base"],
            "packaging_runtime": "CPython-3.14.6",
            "packer": packer,
        }
        if manifest["toolchain"] != expected_toolchain:
            raise VerifyError("R6 toolchain provenance drift")
        if (
            packer["source_commit"] != manifest["source_commit"]
            or packer["path"] != "tools/host-lisp/r6_ship.py"
            or packer["packaged_path"] != "evidence/r6_ship.py"
            or packaged_packer.read_bytes() != (ROOT / "evidence/r6_ship.py").read_bytes()
        ):
            raise VerifyError("R6 packer source binding drift")
    finally:
        r4_tmp.cleanup()
        r5_tmp.cleanup()
    return manifest


def main() -> int:
    try:
        value = verify()
        print(
            f"r6-ship-offline: PASS artifacts={ARTIFACT_COUNT} L65SYS=10 L65WORK=blank "
            f"product={value['product']['artifact_set_sha256']} "
            "G3=passed G5=passed G6=not-run release=no"
        )
        return 0
    except (VerifyError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"r6-ship-offline: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
