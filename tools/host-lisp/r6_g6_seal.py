#!/usr/bin/env python3
"""Build and verify the immutable R6/G6 hardware-acceptance seal."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
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


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import block_capacity_delta_policy as CAPACITY  # noqa: E402
import r6_g6 as G6  # noqa: E402
import remote_source_binding as REMOTE_BINDING  # noqa: E402


CONTRACT = ROOT / "config/r6-g6-wave3-seal-contract.json"
PROMOTION_REGISTER = ROOT / "config/promotion-register.json"
ARCHIVE_ASSET_INVENTORY = ROOT / "config/evidence-archive-assets.json"
RUN_DIR = ROOT / "build/r6/g6/run-20260719-wave3-01"
TOP_RECEIPT = RUN_DIR / "g6-hardware-receipt.json"
SHIP = ROOT / "build/r6/ship"
OFFLINE_VERIFIER = ROOT / "tools/host-lisp/r6_g6_seal_offline.py"
ARCHIVE_FORMAT = "lisp65-r6-g6-hardware-archive-v1"
PRODUCT_SET = G6.PRODUCT_SET
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

STATIC_FILES = (
    ".gitattributes",
    "config/r6-g6-wave3-seal-contract.json",
    "config/r6-g6-harness.json",
    "config/g6-hardware-profile.json",
    "config/r7-release-prerequisites.json",
    "config/history-transport-rewrite.json",
    "config/block-capacity-delta-policy.json",
    "tests/bytecode/dialect-v2/evidence/post-release/r6-g6-wave3-static-preflight-receipt.json",
    "tests/bytecode/dialect-v2/evidence/post-release/r6-g6-wave3-profile-applicability-receipt.json",
    "tests/bytecode/dialect-v2/evidence/post-release/r6-ship-wave3-packer-receipt.json",
    "tools/host-lisp/r6_g6.py",
    "tools/host-lisp/r6_g6_seal.py",
    "tools/host-lisp/r6_g6_seal_offline.py",
    "tools/host-lisp/g6_two_media_oracle.py",
    "tools/host-lisp/m65d_blank_d81_oracle.py",
    "tools/host-lisp/d81_bam_sanity.py",
    "tools/host-lisp/d81_persistence_fault.py",
    "tools/host-lisp/history_transport_rewrite.py",
    "src/f011_context.h",
    "src/io.c",
    "lib/m65-disk.lisp",
)


class SealError(RuntimeError):
    pass


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SealError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise SealError(f"{label} must be a regular file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SealError(f"cannot load {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise SealError(f"{label} must contain an object")
    return value


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def repo_relative(path: Path, label: str) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError as exc:
        raise SealError(f"{label} must be inside the repository") from exc


def canonical_commit(value: str) -> str:
    if not COMMIT_RE.fullmatch(value):
        raise SealError("source commit must be a full lowercase Git commit")
    completed = subprocess.run(
        ["git", "rev-parse", f"{value}^{{commit}}"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
    )
    if completed.returncode or completed.stdout.strip() != value:
        raise SealError("source commit is unavailable or non-canonical")
    for relative in STATIC_FILES:
        path = ROOT / relative
        if path.is_symlink() or not path.is_file():
            raise SealError(f"static seal input missing: {relative}")
        shown = subprocess.run(
            ["git", "show", f"{value}:{relative}"], cwd=ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if shown.returncode or shown.stdout != path.read_bytes():
            raise SealError(f"source commit does not bind current seal input: {relative}")
    return value


def commit_date(value: str) -> str:
    completed = subprocess.run(
        ["git", "show", "-s", "--format=%cs", value], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
    )
    result = completed.stdout.strip()
    if completed.returncode or not DATE_RE.fullmatch(result):
        raise SealError("source commit date is unavailable")
    return result


def contract() -> dict[str, Any]:
    value = load(CONTRACT, "R6/G6 seal contract")
    if (
        value.get("format") != "lisp65-r6-g6-seal-contract-v1"
        or value.get("version") != 1 or value.get("id") != "r6-g6-hardware-acceptance"
        or value.get("status") != "authorized" or value.get("kind") != "hardware-acceptance"
        or value.get("input") != {
            "run_id": RUN_DIR.name,
            "product_artifact_set_sha256": PRODUCT_SET,
            "ship_manifest_sha256": "706dc97d3811dfa0d362522358a00b7c1dd30264f7409acccec3fce07d46150e",
            "preflight_sha256": "a6340e08d5ee2345cda948afbb17680f3d3fe61f0405b3a2375e50117cbf4330",
            "top_receipt_sha256": "6ecf662e5828560521701446ba907e249990aa27ebd20e9e93046ea5d6460a10",
        }
        or value.get("receipt") != {
            "format": G6.TOP_FORMAT, "applicable_cases": 5,
            "profile_not_applicable_cases": 1,
            "coverage": "exactly-once-per-applicable-case",
            "physical_power_or_reset_cycles": 2,
        }
        or value.get("archive") != {
            "format": ARCHIVE_FORMAT, "self_contained": True,
            "immutability": "append-only-never-amend",
            "offline_verification": "archive-alone-no-repository-no-network",
            "double_pack": "byte-identical-varied-environment",
        }
    ):
        raise SealError("R6/G6 seal contract semantic drift")
    try:
        CAPACITY.validate_policy()
        CAPACITY.validate_capacity_delta(value["capacity_delta"])
    except CAPACITY.CapacityDeltaError as exc:
        raise SealError(f"R6/G6 seal capacity delta drift: {exc}") from exc
    return value


def add_file(files: dict[str, tuple[bytes, int]], path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise SealError(f"{label} must be a regular file: {path}")
    relative = repo_relative(path, label)
    data = path.read_bytes()
    mode = stat.S_IMODE(path.stat().st_mode)
    previous = files.get(relative)
    if previous is not None and previous != (data, mode):
        raise SealError(f"conflicting bytes for archive path: {relative}")
    files[relative] = (data, mode)


def add_tree(files: dict[str, tuple[bytes, int]], root: Path, label: str) -> None:
    if root.is_symlink() or not root.is_dir():
        raise SealError(f"{label} must be a directory: {root}")
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise SealError(f"{label} contains a symlink: {path}")
        if path.is_file():
            add_file(files, path, label)


def add_case_evidence_closure(
    files: dict[str, tuple[bytes, int]], top: dict[str, Any],
) -> None:
    rows = top.get("cases")
    if not isinstance(rows, list) or len(rows) != 5:
        raise SealError("G6 top receipt case closure drift")
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or not isinstance(row.get("receipt"), str):
            raise SealError(f"G6 case closure row malformed: {index}")
        receipt_path = ROOT / row["receipt"]
        add_file(files, receipt_path, "G6 case receipt")
        receipt = load(receipt_path, "G6 case receipt")
        if receipt.get("format") == G6.CASE_REBIND_FORMAT:
            historical_preflight = receipt.get("historical_preflight")
            historical_receipt = receipt.get("historical_case_receipt")
            if (
                not isinstance(historical_preflight, dict)
                or not isinstance(historical_preflight.get("path"), str)
                or not isinstance(historical_receipt, dict)
                or not isinstance(historical_receipt.get("path"), str)
            ):
                raise SealError(f"G6 rebound case closure malformed: {index}")
            add_file(files, ROOT / historical_preflight["path"], "historical G6 preflight")
            receipt_path = ROOT / historical_receipt["path"]
            add_file(files, receipt_path, "historical G6 case receipt")
            receipt = load(receipt_path, "historical G6 case receipt")
        sheet = receipt.get("sheet")
        evidence = receipt.get("evidence")
        if not isinstance(sheet, dict) or not isinstance(sheet.get("path"), str):
            raise SealError(f"G6 case sheet binding malformed: {index}")
        if not isinstance(evidence, list):
            raise SealError(f"G6 case evidence binding malformed: {index}")
        add_file(files, ROOT / sheet["path"], "G6 execution sheet")
        for evidence_index, evidence_row in enumerate(evidence):
            if not isinstance(evidence_row, dict) or not isinstance(evidence_row.get("path"), str):
                raise SealError(f"G6 raw evidence binding malformed: {index}/{evidence_index}")
            add_file(files, ROOT / evidence_row["path"], "G6 raw evidence")


def tar_member(name: str, data: bytes, mode: int = 0o644) -> tuple[tarfile.TarInfo, io.BytesIO]:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = mode
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mtime = 0
    return info, io.BytesIO(data)


def archive_bytes(
    *, archive_id: str, source_commit: str, sealed_on: str,
    remote_binding: dict[str, Any],
) -> bytes:
    if not SAFE_ID_RE.fullmatch(archive_id) or archive_id != f"r6-g6-hardware-acceptance-{source_commit[:7]}":
        raise SealError("R6/G6 archive id must bind the source commit")
    if sealed_on != commit_date(source_commit):
        raise SealError("sealed_on must equal the source commit date")
    seal_contract = contract()
    if sha(TOP_RECEIPT) != seal_contract["input"]["top_receipt_sha256"]:
        raise SealError("G6 top receipt SHA drift")
    top = G6.verify_aggregate_receipt(TOP_RECEIPT)
    ship_manifest = load(SHIP / "manifest.json", "R6 Ship manifest")
    if (
        sha(SHIP / "manifest.json") != seal_contract["input"]["ship_manifest_sha256"]
        or ship_manifest.get("package_set_sha256") != "77518fe589df2fca5480b3d0b85f0baab17faea5deb3291406b36b5e6e7f36b2"
        or top.get("claims") != seal_contract["claims"]
    ):
        raise SealError("G6 Ship or claim binding drift")
    files: dict[str, tuple[bytes, int]] = {}
    add_tree(files, SHIP, "R6 Ship")
    add_tree(files, RUN_DIR, "G6 hardware run")
    add_case_evidence_closure(files, top)
    for relative in STATIC_FILES:
        add_file(files, ROOT / relative, "G6 seal input")
    rows = [
        {"path": f"payload/{path}", "bytes": len(data), "sha256": sha_bytes(data)}
        for path, (data, _mode) in sorted(files.items())
    ]
    manifest = {
        "format": ARCHIVE_FORMAT, "version": 2, "id": archive_id,
        "kind": "hardware-acceptance", "status": "sealed",
        "source_commit": source_commit, "sealed_on": sealed_on,
        "remote_source_binding": remote_binding,
        "immutability": "append-only-never-amend",
        "product_artifact_set_sha256": PRODUCT_SET,
        "ship": {
            "path": "build/r6/ship",
            "manifest_sha256": sha(SHIP / "manifest.json"),
            "package_set_sha256": ship_manifest["package_set_sha256"],
        },
        "top_receipt": {
            "path": repo_relative(TOP_RECEIPT, "G6 top receipt"),
            "sha256": sha(TOP_RECEIPT),
        },
        "claims": top["claims"],
        "capacity_delta": seal_contract["capacity_delta"],
        "reproducibility": {
            "packs": 2, "varied_environment": ["PYTHONHASHSEED", "TZ"],
            "archive_byte_identical": True,
        },
        "files": rows, "result": "passed",
    }
    manifest_data = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("ascii")
    verifier_data = OFFLINE_VERIFIER.read_bytes()
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode="w") as archive:
            for name, data, mode in (
                ("manifest.json", manifest_data, 0o644),
                ("verify.py", verifier_data, 0o755),
            ):
                info, stream = tar_member(name, data, mode)
                archive.addfile(info, stream)
            for path, (data, mode) in sorted(files.items()):
                info, stream = tar_member(f"payload/{path}", data, mode)
                archive.addfile(info, stream)
    return buffer.getvalue()


def safe_extract(archive_path: Path, directory: Path) -> None:
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        for member in members:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or not member.isfile():
                raise SealError("unsafe or non-file R6/G6 archive member")
        archive.extractall(directory)


def run_extracted_verifier(directory: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "verify.py"], cwd=directory,
        env={"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "TZ": "UTC"},
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )


def verify_archive(archive_path: Path) -> None:
    if archive_path.is_symlink() or not archive_path.is_file():
        raise SealError("R6/G6 archive is missing")
    with tempfile.TemporaryDirectory(prefix="r6-g6-seal-offline-") as raw:
        directory = Path(raw)
        safe_extract(archive_path, directory)
        completed = run_extracted_verifier(directory)
        if completed.returncode:
            raise SealError(f"isolated R6/G6 archive verification failed:\n{completed.stdout}")
        print(completed.stdout.strip())


def archive_asset_shas() -> set[str]:
    """SHAs of the archives published as release assets (the declared authority)."""
    inventory = load(ARCHIVE_ASSET_INVENTORY, "evidence archive asset inventory")
    archives = inventory.get("archives")
    if not isinstance(archives, list):
        raise SealError("evidence archive asset inventory lacks archives")
    shas: set[str] = set()
    for index, row in enumerate(archives):
        if not isinstance(row, dict) or not isinstance(row.get("sha256"), str):
            raise SealError(f"archive asset inventory row {index} is malformed")
        shas.add(row["sha256"])
    return shas


def verify_registered_archive() -> None:
    register = load(PROMOTION_REGISTER, "promotion register")
    promotions = register.get("promotions")
    if not isinstance(promotions, list):
        raise SealError("promotion register entries are malformed")
    matches = [
        row for row in promotions
        if isinstance(row, dict)
        and isinstance(row.get("id"), str)
        and row["id"].startswith("r6-g6-hardware-acceptance-")
    ]
    if not matches:
        raise SealError("promotion register contains no R6/G6 acceptance seal")
    for row in matches:
        if set(row) != {"id", "subject", "kind", "source_commit", "archive", "archive_sha256"}:
            raise SealError("registered R6/G6 acceptance schema drift")
        archive_value = row["archive"]
        if not isinstance(archive_value, str):
            raise SealError("registered R6/G6 archive path is malformed")
        archive_pure = PurePosixPath(archive_value)
        if archive_pure.is_absolute() or ".." in archive_pure.parts or archive_pure.as_posix() != archive_value:
            raise SealError("registered R6/G6 archive path is not canonical")
        archive_path = ROOT / archive_pure
        if (
            row["kind"] != "hardware-acceptance"
            or not isinstance(row["archive_sha256"], str)
            or not SHA_RE.fullmatch(row["archive_sha256"])
            or archive_path.is_symlink()
        ):
            raise SealError("registered R6/G6 acceptance binding drift")
        if archive_path.is_file():
            if sha(archive_path) != row["archive_sha256"]:
                raise SealError("registered R6/G6 acceptance binding drift")
        else:
            # config/promotion-archive-policy.json calls the local materialization
            # an "ignored-cache-verified-before-use" whose authority is the asset
            # inventory.  That covers *identity* -- but this check also re-runs the
            # isolated offline verifier from inside the archive, and there is no
            # substitute for those bytes.  Skipping it would turn the gate into a
            # no-op, so the failure stays; it only says what to materialize.
            known = row["archive_sha256"] in archive_asset_shas()
            raise SealError(
                f"registered R6/G6 acceptance archive is not materialized: {row['id']}"
                + (
                    " -- its identity is covered by config/evidence-archive-assets.json;"
                    " download it from the release named there and place it at"
                    f" {archive_value}"
                    if known
                    else " -- and its SHA is in neither the tree nor"
                    " config/evidence-archive-assets.json, so the citation is broken"
                )
            )
        verify_archive(archive_path)
        print(
            f"r6-g6-seal: REGISTERED PASS id={row['id']} "
            f"sha256={row['archive_sha256']}"
        )
    print(f"r6-g6-seal: REGISTERED SET PASS count={len(matches)}")


def negative_test(archive_path: Path) -> None:
    for mutation in ("product-byte", "case-receipt", "top-receipt"):
        with tempfile.TemporaryDirectory(prefix=f"r6-g6-seal-negative-{mutation}-") as raw:
            directory = Path(raw)
            safe_extract(archive_path, directory)
            manifest = load(directory / "manifest.json", "negative-test manifest")
            if mutation == "product-byte":
                target = directory / "payload/build/r6/ship/components/lisp65.prg"
            elif mutation == "case-receipt":
                target = directory / "payload" / manifest["top_receipt"]["path"]
                top = load(target, "negative-test top receipt")
                target = directory / "payload" / top["cases"][0]["receipt"]
            else:
                target = directory / "payload" / manifest["top_receipt"]["path"]
            data = bytearray(target.read_bytes())
            data[len(data) // 2] ^= 1
            target.write_bytes(data)
            completed = run_extracted_verifier(directory)
            if completed.returncode == 0:
                raise SealError(f"R6/G6 verifier accepted mutation: {mutation}")
    print("r6-g6-seal: NEGATIVE PASS mutations=3 product-byte+case-receipt+top-receipt")


def seal(*, archive_id: str, source_commit: str, sealed_on: str, output: Path) -> None:
    canonical_commit(source_commit)
    try:
        remote_binding = REMOTE_BINDING.capture(source_commit)
    except REMOTE_BINDING.RemoteBindingError as exc:
        raise SealError(f"G6 source is not remotely bound: {exc}") from exc
    if output.exists() or output.is_symlink():
        raise SealError(f"R6/G6 archive output must be fresh: {output}")
    environments = (("1", "UTC"), ("777", "Pacific/Kiritimati"))
    results: list[bytes] = []
    for hashseed, timezone in environments:
        old_hashseed, old_timezone = os.environ.get("PYTHONHASHSEED"), os.environ.get("TZ")
        os.environ["PYTHONHASHSEED"], os.environ["TZ"] = hashseed, timezone
        try:
            results.append(archive_bytes(
                archive_id=archive_id, source_commit=source_commit,
                sealed_on=sealed_on, remote_binding=remote_binding,
            ))
        finally:
            if old_hashseed is None:
                os.environ.pop("PYTHONHASHSEED", None)
            else:
                os.environ["PYTHONHASHSEED"] = old_hashseed
            if old_timezone is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = old_timezone
    if results[0] != results[1]:
        raise SealError("R6/G6 varied-environment double pack differs")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    if temporary.exists() or temporary.is_symlink():
        raise SealError(f"R6/G6 temporary archive path is not fresh: {temporary}")
    temporary.write_bytes(results[0])
    try:
        verify_archive(temporary)
        negative_test(temporary)
        temporary.replace(output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    print(
        f"r6-g6-seal: WROTE packs=2 bytes={output.stat().st_size} "
        f"sha256={sha(output)} G6=5/5-applicable release=awaits-R7"
    )


def selftest() -> None:
    value = contract()
    if value["claims"].get("release") != "not-promoted-until-R7":
        raise SealError("R6/G6 seal release boundary drift")
    print("r6-g6-seal: SELFTEST PASS kind=hardware-acceptance G6=5/5-applicable WP=n/a release=awaits-R7")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)
    sub.add_parser("selftest")
    sub.add_parser("registered-verify")
    pack = sub.add_parser("seal")
    pack.add_argument("--id", required=True)
    pack.add_argument("--source-commit", required=True)
    pack.add_argument("--sealed-on", required=True)
    pack.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("archive", type=Path)
    negative = sub.add_parser("negative-test")
    negative.add_argument("archive", type=Path)
    return result


def rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "selftest":
            selftest()
        elif args.command == "registered-verify":
            verify_registered_archive()
        elif args.command == "seal":
            seal(
                archive_id=args.id, source_commit=args.source_commit,
                sealed_on=args.sealed_on, output=rooted(args.output),
            )
        elif args.command == "verify":
            verify_archive(rooted(args.archive))
        else:
            negative_test(rooted(args.archive))
        return 0
    except (
        SealError, G6.G6Error, CAPACITY.CapacityDeltaError, OSError, UnicodeError,
        ValueError, KeyError, TypeError, json.JSONDecodeError, tarfile.TarError,
    ) as exc:
        print(f"r6-g6-seal: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
