#!/usr/bin/env python3
"""Build and verify the immutable C2-lite v1.2 R6/G6 acceptance seal."""

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

import remote_source_binding as REMOTE_BINDING  # noqa: E402


CONTRACT = ROOT / "config/c2-lite-r6-g6-seal-contract.json"
PROMOTION_REGISTER = ROOT / "config/promotion-register.json"
OFFLINE_VERIFIER = ROOT / "tools/host-lisp/c2_lite_g6_offline.py"
ARCHIVE_FORMAT = "lisp65-c2-lite-r6-g6-hardware-archive-v1"
PRODUCT_SET = "37998ce7b6698757fe3839d0af1467e95505fe10e6be6bc7f28a6991cb09941d"
PACKAGE_SET = "82ddc3d7fd8bc048b2803081866aa5320a08bd226d18b063c403a33fc9e7e038"
CONTRACT_ID = "c2-lite-r6-g6-hardware-acceptance-v1.2"
ARCHIVE_ID_PREFIX = "c2-lite-r6-g6-hardware-acceptance"
REGISTERED_SUBJECT = "c2-lite-v1.2-link66-r6-g6"
SEAL_RELEASE_CLAIM = "promoted-v1.2"
RELEASE_LABEL = "v1.2"
SEAL_EQUALS_PROMOTION = True
R5_RECEIPT = (
    ROOT / "build/c2.2/acceptance/r5-successor-v11"
    / "r5-successor-rebind-receipt.json"
)
R6_RECEIPT = (
    ROOT / "build/c2.2/acceptance/r6-successor-v11"
    / "r6-packaging-receipt.json"
)
R6_MANIFEST = (
    ROOT / "build/c2.2/acceptance/r6-successor-v11/ship"
    / "manifest.json"
)
G5_TOP_RECEIPT = (
    ROOT / "build/c2.2/acceptance/g5/replay-v11-hybrid-dma"
    / "session-01/g5-hardware-receipt.json"
)
ACCEPTANCE_CONTRACT = ROOT / "config/c2-lite-acceptance-chain.json"
TOP_RECEIPT = (
    ROOT / "build/c2.2/acceptance/g6-successor-v11/session-01"
    / "g6-hardware-receipt.json"
)
EVIDENCE_TREES = (
    ROOT / "build/c2.2/acceptance/r5",
    ROOT / "build/c2.2/acceptance/g5",
    ROOT / "build/c2.2/acceptance/r5-successor-v11",
    ROOT / "build/c2.2/acceptance/r6-successor-v11",
    ROOT / "build/c2.2/acceptance/g6-successor-v11",
)
STATIC_FILES = (
    "config/c2-lite-acceptance-chain.json",
    "config/c2-lite-media-product.json",
    "config/c2-lite-r6-g6-seal-contract.json",
    "config/promotion-archive-policy.json",
    "scripts/c2-lite-cold-stager-chain.s",
    "scripts/r3-cold-stager-main.c",
    "scripts/r3-rom-write-enable.s",
    "tools/host-lisp/asm_c_constant_contract.py",
    "tools/host-lisp/c2_lite_media_product.py",
    "tools/host-lisp/c2_lite_g5_hardware_close.py",
    "tools/host-lisp/c2_lite_media_g5_dma_path_diff.py",
    "tools/host-lisp/c2_lite_media_g5_entry_repack.py",
    "tools/host-lisp/c2_lite_media_g5_handoff_completion_repack.py",
    "tools/host-lisp/c2_lite_media_g5_hybrid_dma_repack.py",
    "tools/host-lisp/c2_lite_media_g5_io_trigger_attribution.py",
    "tools/host-lisp/c2_lite_media_g5_normal_dma_repack.py",
    "tools/host-lisp/c2_lite_media_g5_rom_write_repack.py",
    "tools/host-lisp/c2_lite_media_g5_write_only_diagnostic.py",
    "tools/host-lisp/c2_lite_r5_r6.py",
    "tools/host-lisp/c2_lite_r6_offline.py",
    "tools/host-lisp/c2_lite_g6.py",
    "tools/host-lisp/c2_lite_g6_offline.py",
    "tools/host-lisp/c2_lite_r6_g6_seal.py",
    "tools/host-lisp/remote_source_binding.py",
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


class SealError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SealError(message)


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
        raise SealError(f"cannot read {label}: {error}") from error
    require(isinstance(value, dict), f"{label} must be an object")
    return value


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    require(
        completed.returncode == 0,
        completed.stderr.strip() or f"git {' '.join(args)} failed",
    )
    return completed.stdout.strip()


def canonical_commit(value: str) -> str:
    require(
        SHA1_RE.fullmatch(value) is not None
        and git("rev-parse", f"{value}^{{commit}}") == value,
        "source commit must be a local canonical commit",
    )
    for relative in STATIC_FILES:
        path = ROOT / relative
        require(path.is_file() and not path.is_symlink(),
                f"static seal input missing: {relative}")
        completed = subprocess.run(
            ["git", "show", f"{value}:{relative}"], cwd=ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        require(
            completed.returncode == 0
            and completed.stdout == path.read_bytes(),
            f"source commit does not bind current input: {relative}",
        )
    return value


def commit_date(value: str) -> str:
    result = git("show", "-s", "--format=%cs", value)
    require(DATE_RE.fullmatch(result) is not None, "source date unavailable")
    return result


def contract() -> dict[str, Any]:
    value = load(CONTRACT, "seal contract")
    expected_input = {
        "G5_top_receipt_sha256": sha(G5_TOP_RECEIPT),
        "G6_top_receipt_sha256": sha(TOP_RECEIPT),
        "R5_successor_receipt_sha256": sha(R5_RECEIPT),
        "R6_manifest_sha256": sha(R6_MANIFEST),
        "R6_package_set_sha256": PACKAGE_SET,
        "R6_receipt_sha256": sha(R6_RECEIPT),
        "acceptance_contract_sha256": sha(ACCEPTANCE_CONTRACT),
        "product_artifact_set_sha256": PRODUCT_SET,
    }
    require(
        value.get("format") == "lisp65-c2-lite-r6-g6-seal-contract-v1"
        and value.get("version") == 1
        and value.get("id") == CONTRACT_ID
        and value.get("status") == "owner-authorized"
        and value.get("kind") == "hardware-acceptance"
        and value.get("input") == expected_input
        and value.get("claims") == {
            "G5": "passed-nine-of-nine",
            "G6": "passed-five-of-five",
            "release": SEAL_RELEASE_CLAIM,
        }
        and value.get("capacity_delta") == {
            "attic_bytes": 0,
            "bank_bytes": 0,
            "directory_slots": 0,
            "ext_bytes": 0,
            "reason": "acceptance-seal-only-no-product-byte-or-layout-change",
            "resident_bytes": 0,
        },
        "seal contract semantic drift",
    )
    promotion = value.get("promotion")
    require(
        isinstance(promotion, dict)
        and promotion.get("product_byte_changes") == 0
        and promotion.get("remote_source_binding")
        == "source-commit-is-remote-ancestor"
        and promotion.get("seal_equals_promotion")
        is SEAL_EQUALS_PROMOTION
        and promotion.get("subject") == REGISTERED_SUBJECT,
        "seal promotion contract drift",
    )
    return value


def repo_relative(path: Path, label: str) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError as error:
        raise SealError(f"{label} must be in repository") from error


def add_file(
    files: dict[str, tuple[bytes, int]], path: Path, label: str,
) -> None:
    require(path.is_file() and not path.is_symlink(),
            f"{label} is not a regular file: {path}")
    relative = repo_relative(path, label)
    value = (path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
    require(
        relative not in files or files[relative] == value,
        f"conflicting archive bytes: {relative}",
    )
    files[relative] = value


def add_tree(
    files: dict[str, tuple[bytes, int]], root: Path, label: str,
) -> None:
    require(root.is_dir() and not root.is_symlink(), f"{label} tree missing")
    for path in sorted(root.rglob("*")):
        require(not path.is_symlink(), f"{label} contains symlink: {path}")
        if path.is_file():
            add_file(files, path, label)


def tar_member(
    name: str, data: bytes, mode: int,
) -> tuple[tarfile.TarInfo, io.BytesIO]:
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
    require(
        SAFE_ID_RE.fullmatch(archive_id) is not None
        and archive_id
        == f"{ARCHIVE_ID_PREFIX}-{source_commit[:7]}",
        "archive id must bind source commit",
    )
    require(sealed_on == commit_date(source_commit),
            "sealed_on must equal source commit date")
    authority = contract()
    for path, key in (
        (R5_RECEIPT, "R5_successor_receipt_sha256"),
        (R6_RECEIPT, "R6_receipt_sha256"),
        (R6_MANIFEST, "R6_manifest_sha256"),
        (G5_TOP_RECEIPT, "G5_top_receipt_sha256"),
        (TOP_RECEIPT, "G6_top_receipt_sha256"),
        (ACCEPTANCE_CONTRACT, "acceptance_contract_sha256"),
    ):
        require(sha(path) == authority["input"][key],
                f"seal authority drift: {key}")

    live_verify = subprocess.run(
        [sys.executable, str(OFFLINE_VERIFIER)], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        check=False,
    )
    require(
        live_verify.returncode == 0
        and "C2-LITE G6 OFFLINE PASS" in live_verify.stdout,
        f"live G6 verification red:\n{live_verify.stdout}",
    )

    files: dict[str, tuple[bytes, int]] = {}
    for tree in EVIDENCE_TREES:
        add_tree(files, tree, tree.name)
    for relative in STATIC_FILES:
        add_file(files, ROOT / relative, "static seal input")
    rows = [
        {
            "path": f"payload/{path}",
            "bytes": len(data),
            "sha256": sha_bytes(data),
            "mode": f"0{mode:03o}",
        }
        for path, (data, mode) in sorted(files.items())
    ]
    manifest = {
        "format": ARCHIVE_FORMAT,
        "version": 2,
        "id": archive_id,
        "kind": "hardware-acceptance",
        "status": "sealed",
        "source_commit": source_commit,
        "sealed_on": sealed_on,
        "remote_source_binding": remote_binding,
        "product_artifact_set_sha256": PRODUCT_SET,
        "R6_package_set_sha256": PACKAGE_SET,
        "top_receipt_sha256": sha(TOP_RECEIPT),
        "claims": authority["claims"],
        "capacity_delta": authority["capacity_delta"],
        "reproducibility": {
            "packs": 2,
            "varied_environment": ["PYTHONHASHSEED", "TZ"],
            "archive_byte_identical": True,
        },
        "immutability": "append-only-never-amend",
        "files": rows,
        "result": "passed",
    }
    manifest_data = (
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    ).encode("ascii")
    verifier_data = OFFLINE_VERIFIER.read_bytes()
    output = io.BytesIO()
    with gzip.GzipFile(
        filename="", mode="wb", fileobj=output, mtime=0,
    ) as zipped:
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
    return output.getvalue()


def safe_extract(archive_path: Path, directory: Path) -> None:
    require(
        archive_path.is_file() and not archive_path.is_symlink(),
        "seal archive missing",
    )
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        for member in members:
            path = PurePosixPath(member.name)
            require(
                member.isfile() and not path.is_absolute()
                and ".." not in path.parts,
                "unsafe archive member",
            )
        archive.extractall(directory)


def run_verifier(directory: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "verify.py"], cwd=directory,
        env={
            "PATH": os.environ.get("PATH", ""),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "TZ": "UTC",
        },
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        check=False,
    )


def verify_archive(path: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="c2-lite-r6-g6-verify-") as raw:
        directory = Path(raw)
        safe_extract(path, directory)
        result = run_verifier(directory)
        require(result.returncode == 0,
                f"isolated verifier red:\n{result.stdout}")
        print(result.stdout.strip())


def mutate_json(path: Path, transform: Any) -> None:
    value = load(path, "mutation JSON")
    transform(value)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )


def negative_test(path: Path) -> None:
    mutations = (
        "product-byte", "case-receipt", "remote-binding", "claim",
    )
    for mutation in mutations:
        with tempfile.TemporaryDirectory(
            prefix=f"c2-lite-r6-g6-negative-{mutation}-",
        ) as raw:
            directory = Path(raw)
            safe_extract(path, directory)
            if mutation == "product-byte":
                target = (
                    directory / "payload"
                    / R6_MANIFEST.parent.relative_to(ROOT)
                    / "media/lisp65-product.d81"
                )
                require(target.is_file(), "negative product target missing")
                data = bytearray(target.read_bytes())
                data[len(data) // 2] ^= 1
                target.write_bytes(data)
            elif mutation == "case-receipt":
                target = (
                    directory / "payload"
                    / TOP_RECEIPT.parent.relative_to(ROOT)
                    / "case-05-product-media"
                    / "receipt.json"
                )
                mutate_json(
                    target,
                    lambda value: value.__setitem__("result", "failed"),
                )
            elif mutation == "remote-binding":
                mutate_json(
                    directory / "manifest.json",
                    lambda value: value["remote_source_binding"].__setitem__(
                        "relation", "unchecked",
                    ),
                )
            else:
                mutate_json(
                    directory / "manifest.json",
                    lambda value: value["claims"].__setitem__(
                        "release", "not-promoted",
                    ),
                )
            result = run_verifier(directory)
            require(result.returncode != 0,
                    f"offline verifier accepted mutation: {mutation}")
    print(
        "c2-lite-r6-g6-seal: NEGATIVE PASS "
        "mutations=4 product+case+remote+claim"
    )


def seal(
    *, archive_id: str, source_commit: str, sealed_on: str, output: Path,
) -> None:
    canonical_commit(source_commit)
    try:
        remote = REMOTE_BINDING.capture(source_commit)
    except REMOTE_BINDING.RemoteBindingError as error:
        raise SealError(f"source is not remotely bound: {error}") from error
    require(not output.exists() and not output.is_symlink(),
            f"seal output must be fresh: {output}")
    results: list[bytes] = []
    old_seed = os.environ.get("PYTHONHASHSEED")
    old_tz = os.environ.get("TZ")
    try:
        for seed, timezone in (
            ("1", "UTC"), ("777", "Pacific/Kiritimati"),
        ):
            os.environ["PYTHONHASHSEED"] = seed
            os.environ["TZ"] = timezone
            results.append(archive_bytes(
                archive_id=archive_id,
                source_commit=source_commit,
                sealed_on=sealed_on,
                remote_binding=remote,
            ))
    finally:
        if old_seed is None:
            os.environ.pop("PYTHONHASHSEED", None)
        else:
            os.environ["PYTHONHASHSEED"] = old_seed
        if old_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old_tz
    require(results[0] == results[1],
            "varied-environment seal packs differ")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    require(not temporary.exists() and not temporary.is_symlink(),
            "temporary seal output is not fresh")
    temporary.write_bytes(results[0])
    try:
        verify_archive(temporary)
        negative_test(temporary)
        temporary.replace(output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    print(
        "c2-lite-r6-g6-seal: WROTE "
        f"packs=2 bytes={output.stat().st_size} sha256={sha(output)} "
        f"source={source_commit} release={RELEASE_LABEL}"
    )


def registered_verify() -> None:
    register = load(PROMOTION_REGISTER, "promotion register")
    rows = register.get("promotions")
    require(isinstance(rows, list), "promotion register malformed")
    matches = [
        row for row in rows
        if isinstance(row, dict)
        and row.get("subject") == REGISTERED_SUBJECT
    ]
    require(len(matches) == 1, "C2-lite promotion entry not unique")
    row = matches[0]
    require(
        set(row) == {
            "id", "subject", "kind", "source_commit",
            "archive", "archive_sha256",
        }
        and row.get("kind") == "hardware-acceptance"
        and isinstance(row.get("source_commit"), str)
        and SHA1_RE.fullmatch(row["source_commit"]) is not None
        and isinstance(row.get("archive_sha256"), str)
        and SHA256_RE.fullmatch(row["archive_sha256"]) is not None,
        "C2-lite promotion schema drift",
    )
    archive_path = ROOT / Path(*PurePosixPath(row["archive"]).parts)
    require(
        archive_path.is_file() and not archive_path.is_symlink()
        and sha(archive_path) == row["archive_sha256"],
        "registered C2-lite archive drift",
    )
    verify_archive(archive_path)
    print(
        "c2-lite-r6-g6-seal: REGISTERED PASS "
        f"id={row['id']} sha256={row['archive_sha256']}"
    )


def selftest() -> None:
    value = contract()
    require(
        value["promotion"]["seal_equals_promotion"]
        is SEAL_EQUALS_PROMOTION,
            "seal/promotion boundary drift")
    print(
        "c2-lite-r6-g6-seal: SELFTEST PASS "
        f"G5=9/9 G6=5/5 product-delta=0 release={RELEASE_LABEL}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
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
    args = parser.parse_args()
    try:
        if args.command == "selftest":
            selftest()
        elif args.command == "registered-verify":
            registered_verify()
        elif args.command == "seal":
            output = args.output
            if not output.is_absolute():
                output = ROOT / output
            seal(
                archive_id=args.id,
                source_commit=args.source_commit,
                sealed_on=args.sealed_on,
                output=output,
            )
        else:
            archive = args.archive
            if not archive.is_absolute():
                archive = ROOT / archive
            if args.command == "verify":
                verify_archive(archive)
            else:
                negative_test(archive)
        return 0
    except (
        OSError, UnicodeError, ValueError, KeyError, TypeError,
        json.JSONDecodeError, tarfile.TarError, SealError,
    ) as error:
        print(f"c2-lite-r6-g6-seal: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
