#!/usr/bin/env python3
"""Create and verify provenance-bound lisp65 Workbench ship packages."""

from __future__ import annotations

import argparse
import ctypes
from dataclasses import replace
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import struct
import subprocess
import tempfile
from typing import Any

import error_text_table as ErrorTextTable
import dialect_ship_guard as DialectShipGuard
import runtime_overlay_bank as RuntimeOverlayBank
import workbench_overlay_stage as WorkbenchOverlayStage


MANIFEST_NAME = "manifest.json"
MANIFEST_FORMAT_V3 = "lisp65-workbench-ship-v3"
MANIFEST_FORMAT_V4 = "lisp65-workbench-ship-v4"
MANIFEST_FORMAT_V5 = "lisp65-workbench-ship-v5"
MANIFEST_FORMAT = MANIFEST_FORMAT_V5
PREFLIGHT_FORMAT = "lisp65-workbench-preflight-v1"
PRODUCT = "lisp65-workbench"
PROFILE = "mvp-vm-stdlib-einsuite-core-workbench"
STDLIB_SUITE = "tests/bytecode/stdlib/p0-stdlib-einsuite-core-workbench-subset.json"
CANDIDATE_STATUS = "unverified-candidate"
VERIFIED_STATUS = "g2-verified-candidate"
SHA256_HEX_LENGTH = 64
OVERLAY_SCHEMA = "lisp65-workbench-staged-overlay-v1"
OVERLAY_ABI_ID = "workbench-staged-overlay-abi-v1"
OVERLAY_ENTRY = "vm_workbench_boot_overlay_entry"
DESCRIPTOR_MAGIC = b"L65O"
DESCRIPTOR_VERSION = 1
DESCRIPTOR_SIZE = 18
STAGE_ALIGNMENT = 0x100
BANK_SIZE = 0x10000

OVERLAY_BINDING_FIELDS = {
    "schema", "profile", "build_id", "abi", "descriptor", "overlay",
    "resident", "stage", "preload", "stdlib",
}
ABI_FIELDS = {"contract", "contract_id", "contract_sha256"}
DESCRIPTOR_FIELDS = {"magic", "version", "header_size", "crc16", "crc16_algorithm"}
OVERLAY_FIELDS = {"base", "end", "entry", "entry_symbol", "file", "sha256", "size"}
RESIDENT_FIELDS = {"file", "load_base", "file_end", "sha256", "size"}
STAGE_FIELDS = {
    "address", "bank", "end_offset", "file", "limit_offset", "offset",
    "padding_after_stdlib", "sha256", "size",
}
PRELOAD_FIELDS = {"base", "end", "file", "sha256", "size"}
STDLIB_FIELDS = {
    "base", "end", "file", "manifest", "manifest_sha256", "sha256", "size",
}
RUNTIME_PRELOAD_FIELDS_V4 = {
    "role", "artifact", "file", "bank", "address", "size", "sha256",
}
RUNTIME_PRELOAD_FIELDS_V5 = {
    "role", "artifact", "file", "kind", "address", "address_bits", "length",
    "crc16", "crc16_algorithm", "sha256", "build_id", "persistence", "recovery",
}
RUNTIME_PRELOAD_RECOVERY = "redeploy-required"
RUNTIME_OVERLAY_ARTIFACT_ID = "workbench-runtime-overlays"
RUNTIME_OVERLAY_ARTIFACT = "lisp65-mvp-workbench.overlays.bin"
RUNTIME_OVERLAY_HEADER = "runtime-overlay-bank.h"
RUNTIME_PRELOAD_ROLE = "runtime-overlays"
STDLIB_PRELOAD_ROLE = "workbench-stdlib-boot"
RUNTIME_OVERLAY_SLICE_FLAGS = (
    RuntimeOverlayBank.FLAG_RUNTIME | RuntimeOverlayBank.FLAG_REUSABLE
)
RUNTIME_OVERLAY_CANONICAL_SLICES = (
    (
        "catalog-verifier",
        ".lisp65_rt_rtov_catalog",
        "__lisp65_rt_rtov_catalog_start",
        "__lisp65_rt_rtov_catalog_end",
        "__lisp65_rt_rtov_catalog_entry",
        RUNTIME_OVERLAY_SLICE_FLAGS,
    ),
    (
        "record-verifier",
        ".lisp65_rt_rtov_record",
        "__lisp65_rt_rtov_record_start",
        "__lisp65_rt_rtov_record_end",
        "__lisp65_rt_rtov_record_entry",
        RUNTIME_OVERLAY_SLICE_FLAGS,
    ),
) + tuple(
    (
        f"l65m-phase-{phase:02d}",
        f".lisp65_rt_l65m_{phase:02d}",
        f"__lisp65_rt_l65m_{phase:02d}_start",
        f"__lisp65_rt_l65m_{phase:02d}_end",
        f"__lisp65_rt_l65m_{phase:02d}_entry",
        RUNTIME_OVERLAY_SLICE_FLAGS,
    )
    for phase in range(21)
) + tuple(
    (
        f"l65m-commit-{phase:02d}",
        f".lisp65_rt_l65c_{phase:02d}",
        f"__lisp65_rt_l65c_{phase:02d}_start",
        f"__lisp65_rt_l65c_{phase:02d}_end",
        f"__lisp65_rt_l65c_{phase:02d}_entry",
        RUNTIME_OVERLAY_SLICE_FLAGS,
    )
    for phase in range(7)
) + tuple(
    (
        f"lcc-install-{phase:02d}",
        f".lisp65_rt_lcci_{phase:02d}",
        f"__lisp65_rt_lcci_{phase:02d}_start",
        f"__lisp65_rt_lcci_{phase:02d}_end",
        f"__lisp65_rt_lcci_{phase:02d}_entry",
        RUNTIME_OVERLAY_SLICE_FLAGS,
    )
    for phase in range(3)
) + tuple(
    (
        ("boot-fastpath-verify", "boot-fastpath-patches",
         "boot-fastpath-entries-freeze")[phase],
        f".lisp65_rt_boot_{phase:02d}",
        f"__lisp65_rt_boot_{phase:02d}_start",
        f"__lisp65_rt_boot_{phase:02d}_end",
        f"__lisp65_rt_boot_{phase:02d}_entry",
        RuntimeOverlayBank.FLAG_BOOT,
    )
    for phase in range(3)
) + (
    (
        "error-text-renderer",
        ".lisp65_rt_l65e",
        "__lisp65_rt_l65e_start",
        "__lisp65_rt_l65e_end",
        "__lisp65_rt_l65e_entry",
        RUNTIME_OVERLAY_SLICE_FLAGS,
    ),
    (
        "resident-island-installer",
        ".lisp65_rt_island_00",
        "__lisp65_rt_island_00_start",
        "__lisp65_rt_island_00_end",
        "__lisp65_rt_island_00_entry",
        RuntimeOverlayBank.FLAG_BOOT,
    ),
)
RUNTIME_OVERLAY_SLICE_COUNT = len(RUNTIME_OVERLAY_CANONICAL_SLICES)
# Ship-v5 allocates Slot 37 to the boot-only resident-island installer.  The
# historical Ship-v4 limit remains pinned separately below.
RUNTIME_OVERLAY_PRODUCT_SLOT_LIMIT = 38
STDLIB_TRUST_SCHEMA = "lisp65-workbench-stdlib-trust-v2"
STDLIB_TRUST_MODEL = "profile-bound-preload"
STDLIB_GATE_PRODUCER = "bytecode_p0_stdlib.py --check --emit-artifacts"
STDLIB_TRUST_FIELDS = {
    "schema", "trust_model", "semantic_gate", "runtime_binding",
    "literal_envelope", "integrity_policy",
}
STDLIB_GATE_FIELDS = {
    "result", "producer", "suite", "artifact", "artifact_sha256",
    "case_count", "function_count", "object_count",
}
STDLIB_RUNTIME_BINDING_FIELDS = {
    "contract", "contract_sha256", "build_id", "artifact", "file", "address",
    "offset", "length", "sha256", "crc16", "crc16_algorithm",
}
STDLIB_LITERAL_ENVELOPE_FIELDS = {
    "mode", "node_count", "patch_count", "fix", "nil", "t", "symbol",
    "cons", "list", "string", "aggregate_policy",
}
STDLIB_INTEGRITY_POLICY_FIELDS = {
    "crc_passes", "covered_bytes", "trigger", "subsequent_append_rechecks",
    "overlay_calls",
}
RUNTIME_OVERLAY_SLOT_SCHEMA = "lisp65-runtime-overlay-slot-budget-v1"
RUNTIME_OVERLAY_SLOT_FIELDS = {
    "schema", "capacity", "product_limit", "used", "reserve_to_limit", "free",
    "assignments",
}
RUNTIME_OVERLAY_SLOT_ASSIGNMENT_FIELDS = {"id", "name", "section"}
ERROR_TEXT_PROFILE = "workbench"
ERROR_TEXT_PROFILE_ID = 1
ERROR_TEXT_SLOT = 36
ERROR_TEXT_CODE_COUNT = 60
ERROR_TEXT_ACTIVE_CODES = (
    1, 2, 3, 4, 5, 6, 7, 8, 10, 14, 15, 17, 18, 20, 21, 22,
    27, 28, 29, 30, 33, 34, 35, 37, 38, 39, 40, 41, 42, 43, 48,
    49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60,
)
ERROR_TEXT_RESIDENT_CODES = (46, 47)
ERROR_TEXT_OMITTED_CODES = tuple(
    code for code in range(1, ERROR_TEXT_CODE_COUNT + 1)
    if code not in ERROR_TEXT_ACTIVE_CODES and code not in ERROR_TEXT_RESIDENT_CODES
)
V4_ERROR_TEXT_CODE_COUNT = 45
V4_ERROR_TEXT_ACTIVE_CODES = (
    1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 14, 15, 17, 18, 20, 21, 22,
    27, 28, 29, 30, 33, 34, 35, 37, 38, 39, 40, 41, 42, 43,
)
V4_ERROR_TEXT_OMITTED_CODES = tuple(
    code for code in range(1, V4_ERROR_TEXT_CODE_COUNT + 1)
    if code not in V4_ERROR_TEXT_ACTIVE_CODES
)
ERROR_TEXT_FORMAT = "L65E-v1-offset-index"
ERROR_TEXT_CRC_ALGORITHM = "crc-16-ccitt-false"
ERROR_TEXT_FALLBACK = "Ehh"
ERROR_TEXT_ALLOCATION = "none"
ERROR_TEXT_FIELDS_V4 = {
    "schema", "format", "profile", "profile_id", "slot", "code_count",
    "active_codes", "omitted_codes", "offset", "size", "build_id", "crc16",
    "crc16_algorithm", "sha256", "contract_sha256", "selection_rule",
    "fallback", "allocation",
}
ERROR_TEXT_FIELDS_V5 = ERROR_TEXT_FIELDS_V4 | {"resident_codes"}
ERROR_TEXT_SPEC_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "error-texts.json"
)

# Ship-v4 is a read-only historical format. Keep its L65R manifest vocabulary
# and constants local so later runtime-overlay binding versions cannot silently
# redefine what an accepted v4 package means.
V4_RUNTIME_FORMAT = "lisp65-runtime-overlay-bank-v1"
V4_RUNTIME_BANK = 3
V4_RUNTIME_BANK_SIZE = 0x10000
V4_RUNTIME_MAX_SLICES = 64
V4_RUNTIME_MAX_SLICE_BYTES = 1396
V4_RUNTIME_MAX_BOOT_SLICE_BYTES = 4096
V4_RUNTIME_PAYLOAD_ALIGNMENT = 0x100
V4_RUNTIME_ENTRY_ABI = 1
V4_RUNTIME_FLAG_BOOT = 0x0001
V4_RUNTIME_FLAG_RUNTIME = 0x0002
V4_RUNTIME_FLAG_REUSABLE = 0x0004
V4_RUNTIME_KNOWN_FLAGS = (
    V4_RUNTIME_FLAG_BOOT | V4_RUNTIME_FLAG_RUNTIME | V4_RUNTIME_FLAG_REUSABLE
)
V4_RUNTIME_SLOT_SCHEMA = "lisp65-runtime-overlay-slot-budget-v1"
V4_RUNTIME_PRODUCT_SLOT_LIMIT = 37
V4_RUNTIME_TOP_FIELDS = {
    "schema", "profile", "profile_build_id", "abi", "elf", "storage",
    "catalog", "config_header", "policy", "slices",
}
V4_RUNTIME_ABI_FIELDS = {"contract", "sha256"}
V4_RUNTIME_FILE_FIELDS = {"file", "sha256"}
V4_RUNTIME_STORAGE_FIELDS = {
    "format", "file", "bank", "base", "limit", "size", "sha256",
}
V4_RUNTIME_CATALOG_FIELDS = {
    "magic", "version", "header_size", "entry_size", "slice_count", "flags",
    "directory_offset", "payload_offset", "directory_crc16", "header_crc16",
    "crc16_algorithm",
}
V4_RUNTIME_POLICY_FIELDS = {
    "max_slices", "max_slice_bytes", "max_boot_slice_bytes", "payload_alignment",
    "common_vma", "entry_abi",
}
V4_RUNTIME_SLICE_FIELDS = {
    "id", "name", "section", "start_symbol", "end_symbol", "entry_symbol",
    "flags", "roles", "file_offset", "file_size", "memory_size", "vma", "end",
    "entry", "entry_offset", "abi_version", "slice_build_id", "capability_mask",
    "crc16", "sha256",
}

V5_RUNTIME_PROFILE_LINES = (
    f"runtime_overlay_binding_schema={RuntimeOverlayBank.BINDING_SCHEMA}",
    f"runtime_overlay_binary_format={RuntimeOverlayBank.FORMAT}",
    f"runtime_overlay_format_bank_tag={RuntimeOverlayBank.BANK}",
    f"runtime_overlay_storage_kind={RuntimeOverlayBank.STORAGE_KIND}",
    f"runtime_overlay_storage_address=0x{RuntimeOverlayBank.STORAGE_BASE:08x}",
    f"runtime_overlay_storage_address_bits={RuntimeOverlayBank.STORAGE_ADDRESS_BITS}",
    f"runtime_overlay_storage_persistence={RuntimeOverlayBank.STORAGE_PERSISTENCE}",
    f"runtime_overlay_slice_count={RUNTIME_OVERLAY_SLICE_COUNT}",
    f"runtime_overlay_max_slices={RuntimeOverlayBank.MAX_SLICES}",
    f"runtime_overlay_max_vma=0x{RuntimeOverlayBank.MAX_VMA:04x}",
    f"runtime_overlay_max_slice_bytes={RuntimeOverlayBank.MAX_SLICE_BYTES}",
    f"runtime_overlay_entry_abi={RuntimeOverlayBank.ENTRY_ABI}",
    "runtime_overlay_lifetime=build-bound-reusable",
    "resident_island_section=.lisp65_resident_island",
    "resident_island_address=0x1800",
    "resident_island_limit=0x2000",
    "resident_island_payload_capacity=2048",
    "resident_island_immutable_bytes=1108",
    "resident_island_annex_section=.lisp65_resident_island_annex",
    "resident_island_annex_start=0x1c54",
    "resident_island_annex_end_exclusive=0x1d58",
    "resident_island_annex_bytes=260",
    "resident_island_annex_root_count=128",
    "resident_island_annex_reserve_bytes=680",
    "resident_island_annex_lifetime=mutable-noload",
    "resident_island_slot=37",
    "resident_island_lifetime=boot-installed-resident",
    "workbench_screen_base=0x0800",
    "workbench_screen_geometry=80x50x1",
    "workbench_screen_limit=0x17a0",
    "workbench_seam_contract=requires-screen-relocation-before-activation",
)

ARTIFACT_SPECS_V3 = (
    ("workbench-prg", "lisp65-mvp-workbench.prg"),
    ("workbench-stdlib-blob", "lisp65-mvp-workbench.blob.bin"),
    ("workbench-d81", "lisp65-mvp-workbench.d81"),
    ("vm-stdlib-footprint", "mvp-vm-stdlib-footprint.txt"),
    ("workbench-d81-manifest", "workbench-d81-manifest.txt"),
    ("stdlib-artifact-manifest", "stdlib-artifact-manifest.json"),
    ("resolved-profile", "resolved-profile.txt"),
    ("toolchain-report", "toolchain-report.txt"),
)
ARTIFACT_SPECS_V4 = ARTIFACT_SPECS_V3 + (
    (RUNTIME_OVERLAY_ARTIFACT_ID, RUNTIME_OVERLAY_ARTIFACT),
)
ARTIFACT_SPECS_V5 = ARTIFACT_SPECS_V4
ARTIFACT_SPECS = ARTIFACT_SPECS_V5
ARTIFACT_PATHS = dict(ARTIFACT_SPECS)
ARTIFACT_PATHS_V3 = dict(ARTIFACT_SPECS_V3)
GATE_NAMES = tuple(f"G{number}" for number in range(6))
CANDIDATE_GATES = {
    "G0": "not-run",
    "G1": "not-run",
    "G2": "not-run",
    "G3": "not-available",
    "G4": "not-run",
    "G5": "not-run",
}
VERIFIED_GATES = {
    "G0": "pass",
    "G1": "pass",
    "G2": "pass",
    "G3": "not-available",
    "G4": "not-run",
    "G5": "not-run",
}
ALLOWED_GATE_VALUES = {"pass", "fail", "not-run", "not-available"}


class ShipError(Exception):
    """A user-facing package or provenance error."""


def _run_git(args: list[str], cwd: Path) -> bytes:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise ShipError(f"cannot run git: {exc}") from exc
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip()
        raise ShipError(f"git {' '.join(args)} failed: {detail or 'no diagnostic'}")
    return proc.stdout


def _repo_root(cwd: Path) -> Path:
    output = _run_git(["rev-parse", "--show-toplevel"], cwd).decode("utf-8", "strict").strip()
    if not output:
        raise ShipError("git returned an empty repository root")
    return Path(output)


def _relative_excludes(root: Path, exclude_paths: tuple[Path, ...]) -> tuple[str, ...]:
    relative_paths: list[str] = []
    resolved_root = root.resolve()
    for path in exclude_paths:
        try:
            relative = path.resolve().relative_to(resolved_root)
        except ValueError:
            continue
        if relative.parts:
            relative_paths.append(relative.as_posix())
    return tuple(relative_paths)


def _git_status(root: Path, excludes: tuple[str, ...] = ()) -> bytes:
    command = ["status", "--porcelain=v1", "-z", "--untracked-files=all"]
    if excludes:
        command.extend(["--", ".", *(f":(exclude,top){path}" for path in excludes)])
    return _run_git(command, root)


def _listed_paths(root: Path, excludes: tuple[str, ...] = ()) -> list[bytes]:
    commands = (
        ["ls-tree", "-r", "--name-only", "-z", "HEAD"],
        ["ls-files", "-z"],
        ["ls-files", "--others", "--exclude-standard", "-z"],
    )
    paths: set[bytes] = set()
    for command in commands:
        paths.update(item for item in _run_git(command, root).split(b"\0") if item)
    raw_excludes = tuple(os.fsencode(path) for path in excludes)
    return sorted(
        path
        for path in paths
        if not any(path == excluded or path.startswith(excluded + b"/") for excluded in raw_excludes)
    )


def _worktree_sha256(root: Path, excludes: tuple[str, ...] = ()) -> str:
    digest = hashlib.sha256()
    digest.update(b"lisp65-worktree-v1\0")
    for raw_path in _listed_paths(root, excludes):
        relative = os.fsdecode(raw_path)
        path = root / relative
        digest.update(len(raw_path).to_bytes(8, "big"))
        digest.update(raw_path)
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError:
            digest.update(b"missing\0")
            continue
        if stat.S_ISLNK(mode):
            kind = b"symlink\0"
            content = os.fsencode(os.readlink(path))
        elif stat.S_ISREG(mode):
            kind = b"file+x\0" if mode & stat.S_IXUSR else b"file\0"
            content = path.read_bytes()
        else:
            raise ShipError(f"unsupported tracked worktree entry: {relative}")
        digest.update(kind)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def capture_source(
    cwd: Path,
    require_clean: bool,
    exclude_paths: tuple[Path, ...] = (),
) -> dict[str, Any]:
    root = _repo_root(cwd)
    excludes = _relative_excludes(root, exclude_paths)
    status_output = _git_status(root, excludes)
    dirty = bool(status_output)
    if require_clean and dirty:
        entries = [
            item.decode("utf-8", "replace")
            for item in status_output.split(b"\0")
            if item
        ]
        summary = ", ".join(entries[:5])
        if len(entries) > 5:
            summary += f", ... ({len(entries)} entries)"
        raise ShipError(f"git worktree is not clean: {summary}")
    commit = _run_git(["rev-parse", "HEAD"], root).decode("ascii", "strict").strip()
    tree = _run_git(["rev-parse", "HEAD^{tree}"], root).decode("ascii", "strict").strip()
    return {
        "commit": commit,
        "tree": tree,
        "dirty": dirty,
        "worktree_sha256": _worktree_sha256(root, excludes),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ShipError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ShipError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ShipError(f"JSON root must be an object: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as output:
            json.dump(value, output, indent=2, sort_keys=True)
            output.write("\n")
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _regular_file(path: Path, label: str) -> os.stat_result:
    try:
        info = path.lstat()
    except OSError as exc:
        raise ShipError(f"{label} is missing or unreadable: {path}: {exc}") from exc
    if stat.S_ISLNK(info.st_mode):
        raise ShipError(f"{label} must not be a symlink: {path}")
    if not stat.S_ISREG(info.st_mode):
        raise ShipError(f"{label} must be a regular file: {path}")
    return info


def _package_dir(path: Path) -> Path:
    try:
        info = path.lstat()
    except OSError as exc:
        raise ShipError(f"package directory is missing or unreadable: {path}: {exc}") from exc
    if stat.S_ISLNK(info.st_mode):
        raise ShipError(f"package directory must not be a symlink: {path}")
    if not stat.S_ISDIR(info.st_mode):
        raise ShipError(f"package path is not a directory: {path}")
    return path


def _safe_artifact_path(package_dir: Path, relative: Any) -> Path:
    if not isinstance(relative, str) or not relative or "\0" in relative or "\\" in relative:
        raise ShipError(f"artifact path is not a safe relative POSIX path: {relative!r}")
    pure = PurePosixPath(relative)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise ShipError(f"artifact path is not a safe relative path: {relative}")
    if pure.as_posix() != relative:
        raise ShipError(f"artifact path is not normalized: {relative}")
    current = package_dir
    for part in pure.parts:
        current = current / part
        try:
            info = current.lstat()
        except OSError as exc:
            raise ShipError(f"artifact path is missing or unreadable: {relative}: {exc}") from exc
        if stat.S_ISLNK(info.st_mode):
            raise ShipError(f"artifact path must not contain symlinks: {relative}")
    return current


def _valid_hex(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == SHA256_HEX_LENGTH
        and value == value.lower()
        and all(character in "0123456789abcdef" for character in value)
    )


def _source_errors(source: Any) -> list[str]:
    if not isinstance(source, dict):
        return ["source must be an object"]
    errors: list[str] = []
    required = {"commit", "tree", "dirty", "worktree_sha256"}
    missing = sorted(required - source.keys())
    if missing:
        errors.append(f"source is missing fields: {','.join(missing)}")
    for key in ("commit", "tree"):
        value = source.get(key)
        if not (
            isinstance(value, str)
            and len(value) >= 40
            and value == value.lower()
            and all(character in "0123456789abcdef" for character in value)
        ):
            errors.append(f"source.{key} must be a full lowercase Git object ID")
    if type(source.get("dirty")) is not bool:
        errors.append("source.dirty must be boolean")
    if not _valid_hex(source.get("worktree_sha256")):
        errors.append("source.worktree_sha256 must be a lowercase SHA-256")
    return errors


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _crc16_ccitt_false(data: bytes) -> int:
    crc = 0xFFFF
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def _stdlib_trust_binding(
    package_dir: Path,
    artifacts: list[dict[str, Any]],
    overlay_binding: dict[str, Any],
) -> dict[str, Any]:
    records = {record["id"]: record for record in artifacts}
    stdlib_manifest = _read_json(
        package_dir / ARTIFACT_PATHS["stdlib-artifact-manifest"]
    )
    blob = (package_dir / ARTIFACT_PATHS["workbench-stdlib-blob"]).read_bytes()
    stdlib = overlay_binding["stdlib"]
    abi = overlay_binding["abi"]
    length = stdlib["size"]
    prefix = blob[:length]
    cases = stdlib_manifest.get("cases")
    functions = stdlib_manifest.get("functions")
    external = stdlib_manifest.get("external_image")
    if not isinstance(external, dict) or type(external.get("metadata_offset")) is not int:
        raise ShipError("stdlib manifest has no literal-envelope metadata offset")
    try:
        envelope = WorkbenchOverlayStage.stdlib_literal_envelope(
            prefix, external["metadata_offset"]
        )
    except WorkbenchOverlayStage.StageError as exc:
        raise ShipError(f"stdlib literal envelope is invalid: {exc}") from exc
    return {
        "schema": STDLIB_TRUST_SCHEMA,
        "trust_model": STDLIB_TRUST_MODEL,
        "semantic_gate": {
            "result": "pass",
            "producer": STDLIB_GATE_PRODUCER,
            "suite": stdlib_manifest.get("suite"),
            "artifact": "stdlib-artifact-manifest",
            "artifact_sha256": records["stdlib-artifact-manifest"]["sha256"],
            "case_count": len(cases) if isinstance(cases, list) else -1,
            "function_count": len(functions) if isinstance(functions, list) else -1,
            "object_count": stdlib_manifest.get("objects"),
        },
        "runtime_binding": {
            "contract": ARTIFACT_PATHS["resolved-profile"],
            "contract_sha256": abi["contract_sha256"],
            "build_id": overlay_binding["build_id"],
            "artifact": "workbench-stdlib-blob",
            "file": ARTIFACT_PATHS["workbench-stdlib-blob"],
            "address": stdlib["base"],
            "offset": 0,
            "length": length,
            "sha256": _sha256_bytes(prefix),
            "crc16": _crc16_ccitt_false(prefix),
            "crc16_algorithm": "crc-16-ccitt-false",
        },
        "literal_envelope": {
            "mode": "profile-bound-flat-literals",
            "node_count": envelope["node_count"],
            "patch_count": envelope["patch_count"],
            "fix": envelope["fix"],
            "nil": envelope["nil"],
            "t": envelope["t"],
            "symbol": envelope["symbol"],
            "cons": envelope["cons"],
            "list": envelope["list"],
            "string": envelope["string"],
            "aggregate_policy": "build-reject",
        },
        "integrity_policy": {
            "crc_passes": 1,
            "covered_bytes": length,
            "trigger": "once-before-first-bank5-boot-mutation",
            "subsequent_append_rechecks": 0,
            "overlay_calls": 3,
        },
    }


def _runtime_overlay_slot_binding(
    runtime_binding: dict[str, Any],
    product_limit: int = RUNTIME_OVERLAY_PRODUCT_SLOT_LIMIT,
) -> dict[str, Any]:
    slices = runtime_binding["slices"]
    used = len(slices)
    capacity = runtime_binding["policy"]["max_slices"]
    return {
        "schema": RUNTIME_OVERLAY_SLOT_SCHEMA,
        "capacity": capacity,
        "product_limit": product_limit,
        "used": used,
        "reserve_to_limit": product_limit - used,
        "free": capacity - used,
        "assignments": [
            {
                "id": record["id"],
                "name": record["name"],
                "section": record["section"],
            }
            for record in slices
        ],
    }


def _error_text_binding_from_image(
    image: bytes,
    runtime_binding: dict[str, Any],
    contract_sha256: str,
    expected_selection: (
        tuple[int, tuple[int, ...], tuple[int, ...], tuple[int, ...]] | None
    ),
    include_resident_codes: bool,
) -> dict[str, Any]:
    try:
        parsed = RuntimeOverlayBank.validate_image(
            image,
            expected_build_id=runtime_binding["profile_build_id"],
            expected_vma=runtime_binding["policy"]["common_vma"],
            max_slice_bytes=(
                RuntimeOverlayBank.MAX_SLICE_BYTES
                if include_resident_codes
                else V4_RUNTIME_MAX_SLICE_BYTES
            ),
            max_vma=(RuntimeOverlayBank.MAX_VMA if include_resident_codes else 0xFFFF),
        )
    except (RuntimeOverlayBank.OverlayBankError, KeyError, TypeError, ValueError) as exc:
        raise ShipError(f"cannot locate L65E table in invalid runtime image: {exc}") from exc
    if len(parsed.slices) <= ERROR_TEXT_SLOT:
        raise ShipError(f"runtime image has no canonical error-text slot {ERROR_TEXT_SLOT}")
    entry = parsed.slices[ERROR_TEXT_SLOT]
    slices = runtime_binding.get("slices")
    if (
        entry.id != ERROR_TEXT_SLOT
        or not isinstance(slices, list)
        or len(slices) <= ERROR_TEXT_SLOT
        or not isinstance(slices[ERROR_TEXT_SLOT], dict)
        or slices[ERROR_TEXT_SLOT].get("name") != "error-text-renderer"
        or slices[ERROR_TEXT_SLOT].get("section") != ".lisp65_rt_l65e"
    ):
        raise ShipError(f"runtime slot {ERROR_TEXT_SLOT} is not the canonical L65E slice")
    payload = image[entry.file_offset:entry.file_offset + entry.file_size]
    try:
        located = ErrorTextTable.find_table(
            payload,
            expected_build_id=runtime_binding["profile_build_id"],
            expected_profile_id=ERROR_TEXT_PROFILE_ID,
        )
    except (ErrorTextTable.ErrorTextTableError, KeyError, TypeError, ValueError) as exc:
        raise ShipError(
            f"canonical runtime slot {ERROR_TEXT_SLOT} has no unique valid L65E table: {exc}"
        ) from exc
    active_codes = tuple(located["active_codes"])
    inactive_codes = tuple(
        code for code in range(1, located["count"] + 1) if code not in active_codes
    )
    if expected_selection is not None:
        expected_count, expected_active, expected_omitted, expected_resident = (
            expected_selection
        )
        classified = expected_active + expected_omitted + expected_resident
        if (
            len(set(classified)) != len(classified)
            or tuple(sorted(classified)) != tuple(range(1, expected_count + 1))
        ):
            raise ShipError("L65E error-code classifications do not form a dense partition")
        if located["count"] != expected_count:
            raise ShipError(
                f"L65E stable code count is {located['count']}, expected {expected_count}"
            )
        if active_codes != expected_active:
            raise ShipError("L65E active-code selection differs from the Workbench contract")
        if inactive_codes != tuple(sorted(expected_omitted + expected_resident)):
            raise ShipError("L65E inactive-code selection differs from the Workbench contract")
        omitted_codes = expected_omitted
        resident_codes = expected_resident
    else:
        omitted_codes = inactive_codes
        resident_codes = ()
    table_offset = located["offset"]
    table_size = located["size"]
    table = payload[table_offset:table_offset + table_size]
    binding = {
        "schema": ErrorTextTable.SCHEMA,
        "format": ERROR_TEXT_FORMAT,
        "profile": ERROR_TEXT_PROFILE,
        "profile_id": ERROR_TEXT_PROFILE_ID,
        "slot": ERROR_TEXT_SLOT,
        "code_count": located["count"],
        "active_codes": list(active_codes),
        "omitted_codes": list(omitted_codes),
        "offset": table_offset,
        "size": table_size,
        "build_id": located["build_id"],
        "crc16": located["crc16"],
        "crc16_algorithm": ERROR_TEXT_CRC_ALGORITHM,
        "sha256": _sha256_bytes(table),
        "contract_sha256": contract_sha256,
        "selection_rule": ErrorTextTable.POLICY["rule"],
        "fallback": ERROR_TEXT_FALLBACK,
        "allocation": ERROR_TEXT_ALLOCATION,
    }
    if include_resident_codes:
        binding["resident_codes"] = list(resident_codes)
    return binding


def _error_text_binding(
    package_dir: Path,
    runtime_binding: dict[str, Any],
    expected_selection: (
        tuple[int, tuple[int, ...], tuple[int, ...], tuple[int, ...]] | None
    ),
    include_resident_codes: bool,
) -> dict[str, Any]:
    image_path = package_dir / ARTIFACT_PATHS[RUNTIME_OVERLAY_ARTIFACT_ID]
    contract_path = package_dir / ARTIFACT_PATHS["resolved-profile"]
    _regular_file(image_path, "runtime overlay bank image for L65E")
    _regular_file(contract_path, "L65E profile contract")
    return _error_text_binding_from_image(
        image_path.read_bytes(), runtime_binding, _sha256(contract_path),
        expected_selection,
        include_resident_codes,
    )


def _error_text_selection(
    manifest_format: str,
) -> tuple[int, tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    if manifest_format == MANIFEST_FORMAT_V4:
        return (
            V4_ERROR_TEXT_CODE_COUNT,
            V4_ERROR_TEXT_ACTIVE_CODES,
            V4_ERROR_TEXT_OMITTED_CODES,
            (),
        )
    if manifest_format == MANIFEST_FORMAT_V5:
        return (
            ERROR_TEXT_CODE_COUNT,
            ERROR_TEXT_ACTIVE_CODES,
            ERROR_TEXT_OMITTED_CODES,
            ERROR_TEXT_RESIDENT_CODES,
        )
    raise ShipError(f"manifest format has no L65E contract: {manifest_format}")


def _error_text_errors(
    package_dir: Path,
    binding: Any,
    runtime_binding: Any,
    manifest_format: str,
) -> list[str]:
    fields = (
        ERROR_TEXT_FIELDS_V5
        if manifest_format == MANIFEST_FORMAT_V5
        else ERROR_TEXT_FIELDS_V4
    )
    errors = _shape_errors(binding, "error_texts", fields)
    if errors or not isinstance(binding, dict):
        return errors
    if not isinstance(runtime_binding, dict):
        return errors + ["error_texts requires the runtime overlay binding"]
    try:
        expected = _error_text_binding(
            package_dir,
            runtime_binding,
            _error_text_selection(manifest_format),
            manifest_format == MANIFEST_FORMAT_V5,
        )
    except (OSError, ShipError) as exc:
        return errors + [f"error_texts binding cannot be reconstructed: {exc}"]
    for name in sorted(fields):
        if binding.get(name) != expected[name]:
            errors.append(
                f"error_texts.{name} differs from canonical runtime slot {ERROR_TEXT_SLOT}"
            )
    return errors


def _shape_errors(value: Any, label: str, fields: set[str]) -> list[str]:
    if not isinstance(value, dict):
        return [f"{label} must be an object"]
    errors: list[str] = []
    missing = sorted(fields - value.keys())
    extra = sorted(value.keys() - fields)
    if missing:
        errors.append(f"{label} is missing fields: {','.join(missing)}")
    if extra:
        errors.append(f"{label} has unexpected fields: {','.join(extra)}")
    return errors


def _record_shape(value: Any, label: str, fields: set[str]) -> list[str]:
    if not isinstance(value, dict):
        return [f"overlay.{label} must be an object"]
    errors: list[str] = []
    missing = sorted(fields - value.keys())
    extra = sorted(value.keys() - fields)
    if missing:
        errors.append(f"overlay.{label} is missing fields: {','.join(missing)}")
    if extra:
        errors.append(f"overlay.{label} has unexpected fields: {','.join(extra)}")
    return errors


def _integer(value: Any, minimum: int, maximum: int) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _overlay_contract_errors(
    package_dir: Path,
    artifacts: Any,
    binding: Any,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(artifacts, list):
        return errors
    records = {
        artifact.get("id"): artifact
        for artifact in artifacts
        if isinstance(artifact, dict) and isinstance(artifact.get("id"), str)
    }
    required_records = (
        "workbench-prg", "workbench-stdlib-blob", "stdlib-artifact-manifest",
        "resolved-profile",
    )
    if any(not isinstance(records.get(name), dict) for name in required_records):
        return errors

    errors.extend(_record_shape(binding, "binding", OVERLAY_BINDING_FIELDS))
    if not isinstance(binding, dict):
        return errors
    for name, fields in (
        ("abi", ABI_FIELDS),
        ("descriptor", DESCRIPTOR_FIELDS),
        ("overlay", OVERLAY_FIELDS),
        ("resident", RESIDENT_FIELDS),
        ("stage", STAGE_FIELDS),
        ("preload", PRELOAD_FIELDS),
        ("stdlib", STDLIB_FIELDS),
    ):
        errors.extend(_record_shape(binding.get(name), name, fields))
    if errors:
        return errors

    abi = binding["abi"]
    descriptor = binding["descriptor"]
    overlay = binding["overlay"]
    resident = binding["resident"]
    stage = binding["stage"]
    preload = binding["preload"]
    stdlib = binding["stdlib"]

    if binding.get("schema") != OVERLAY_SCHEMA:
        errors.append(f"overlay.schema must be {OVERLAY_SCHEMA}")
    if binding.get("profile") != PROFILE:
        errors.append(f"overlay.profile must be {PROFILE}")
    if not _integer(binding.get("build_id"), 0, 0xFFFFFFFF):
        errors.append("overlay.build_id must be a 32-bit integer")

    if abi.get("contract") != ARTIFACT_PATHS["resolved-profile"]:
        errors.append("overlay ABI contract must be the shipped resolved-profile.txt")
    if abi.get("contract_id") != OVERLAY_ABI_ID:
        errors.append(f"overlay ABI contract_id must be {OVERLAY_ABI_ID}")
    if not _valid_hex(abi.get("contract_sha256")):
        errors.append("overlay ABI contract_sha256 must be a lowercase SHA-256")

    if descriptor.get("magic") != DESCRIPTOR_MAGIC.decode("ascii"):
        errors.append("overlay descriptor magic must be L65O")
    if descriptor.get("version") != DESCRIPTOR_VERSION:
        errors.append("overlay descriptor version must be 1")
    if descriptor.get("header_size") != DESCRIPTOR_SIZE:
        errors.append("overlay descriptor header_size must be 18")
    if descriptor.get("crc16_algorithm") != "crc-16-ccitt-false":
        errors.append("overlay descriptor CRC algorithm must be crc-16-ccitt-false")
    if not _integer(descriptor.get("crc16"), 0, 0xFFFF):
        errors.append("overlay descriptor crc16 must be a 16-bit integer")

    if overlay.get("file") != "lisp65-workbench-overlay.bin":
        errors.append("overlay payload source filename is unexpected")
    if overlay.get("entry_symbol") != OVERLAY_ENTRY:
        errors.append(f"overlay entry_symbol must be {OVERLAY_ENTRY}")
    if not _valid_hex(overlay.get("sha256")):
        errors.append("overlay payload sha256 must be a lowercase SHA-256")
    if not _integer(overlay.get("base"), 0, 0xFFFF):
        errors.append("overlay base must be a Bank-0 address")
    if not _integer(overlay.get("end"), 1, BANK_SIZE):
        errors.append("overlay end must be a Bank-0 end address")
    if not _integer(overlay.get("entry"), 0, 0xFFFF):
        errors.append("overlay entry must be a Bank-0 address")
    if not _integer(overlay.get("size"), 1, 0xFFFF):
        errors.append("overlay size must be a positive 16-bit integer")
    if all(type(overlay.get(name)) is int for name in ("base", "end", "size")):
        if overlay["end"] != overlay["base"] + overlay["size"]:
            errors.append("overlay end must equal base plus size")
    if all(type(overlay.get(name)) is int for name in ("base", "end", "entry")):
        if not overlay["base"] <= overlay["entry"] < overlay["end"]:
            errors.append("overlay entry lies outside the payload")

    expected_names = {
        "resident": "lisp65-workbench-resident.prg",
        "stage": "overlay-stage.bin",
        "preload": "stdlib-with-overlay.ext.bin",
        "stdlib_file": "stdlib-p0.ext.bin",
        "stdlib_manifest": "stdlib-p0.manifest.json",
    }
    if resident.get("file") != expected_names["resident"]:
        errors.append("overlay resident source filename is unexpected")
    if stage.get("file") != expected_names["stage"]:
        errors.append("overlay stage source filename is unexpected")
    if preload.get("file") != expected_names["preload"]:
        errors.append("overlay preload source filename is unexpected")
    if stdlib.get("file") != expected_names["stdlib_file"]:
        errors.append("overlay stdlib source filename is unexpected")
    if stdlib.get("manifest") != expected_names["stdlib_manifest"]:
        errors.append("overlay stdlib manifest source filename is unexpected")
    if resident.get("load_base") != 0x2001:
        errors.append("overlay resident load_base must be 0x2001")
    if preload.get("base") != 0x050000 or stdlib.get("base") != 0x050000:
        errors.append("overlay preload and stdlib base must be 0x050000")
    if stage.get("limit_offset") != 0xC9E0:
        errors.append("overlay stage limit must match the canonical 0xc9e0 namepool offset")
    for label, record in (
        ("resident", resident), ("stage", stage), ("preload", preload), ("stdlib", stdlib)
    ):
        if not _valid_hex(record.get("sha256")):
            errors.append(f"overlay {label} sha256 must be a lowercase SHA-256")
        if not _integer(record.get("size"), 1, 0x10000000):
            errors.append(f"overlay {label} size must be a positive integer")
    if not _valid_hex(stdlib.get("manifest_sha256")):
        errors.append("overlay stdlib manifest_sha256 must be a lowercase SHA-256")
    for label, record, names in (
        ("resident", resident, ("load_base", "file_end")),
        ("preload", preload, ("base", "end")),
        ("stdlib", stdlib, ("base", "end")),
    ):
        for name in names:
            if not _integer(record.get(name), 0, 0x10000000):
                errors.append(f"overlay {label}.{name} must be an address integer")
    for name, maximum in (
        ("address", 0x10000000 - 1), ("bank", 0xFF), ("offset", 0xFFFF),
        ("end_offset", BANK_SIZE), ("limit_offset", BANK_SIZE),
        ("padding_after_stdlib", 0xFFFF),
    ):
        if not _integer(stage.get(name), 0, maximum):
            errors.append(f"overlay stage.{name} is out of range")
    if errors:
        return errors

    try:
        prg_path = package_dir / ARTIFACT_PATHS["workbench-prg"]
        blob_path = package_dir / ARTIFACT_PATHS["workbench-stdlib-blob"]
        stdlib_manifest_path = package_dir / ARTIFACT_PATHS["stdlib-artifact-manifest"]
        contract_path = package_dir / ARTIFACT_PATHS["resolved-profile"]
        for path, label in (
            (prg_path, "resident PRG"), (blob_path, "combined preload"),
            (stdlib_manifest_path, "stdlib artifact manifest"),
            (contract_path, "overlay ABI contract"),
        ):
            _regular_file(path, label)
        prg_data = prg_path.read_bytes()
        blob_data = blob_path.read_bytes()
        stdlib_manifest = _read_json(stdlib_manifest_path)
        contract_data = contract_path.read_bytes()
    except ShipError as exc:
        return [str(exc)]

    if resident["size"] != len(prg_data) or resident["sha256"] != _sha256_bytes(prg_data):
        errors.append("overlay resident binding does not match the shipped PRG")
    if resident["file_end"] != resident["load_base"] + resident["size"] - 2:
        errors.append("overlay resident file_end is inconsistent with its PRG size")
    if len(prg_data) < 3:
        errors.append("shipped resident PRG is too short")
    else:
        load_base = prg_data[0] | (prg_data[1] << 8)
        file_end = load_base + len(prg_data) - 2
        if resident["load_base"] != load_base or resident["file_end"] != file_end:
            errors.append("overlay resident address span does not match the shipped PRG")

    contract_sha = _sha256_bytes(contract_data)
    if abi["contract_sha256"] != contract_sha:
        errors.append("overlay ABI hash does not match the shipped resolved profile")
    if binding["build_id"] != int(contract_sha[:8], 16):
        errors.append("overlay build_id is not derived from the shipped ABI contract")
    contract_lines = set(contract_data.decode("ascii", "replace").splitlines())
    for required_line in (
        "format=lisp65-resolved-profile-v1",
        f"profile={PROFILE}",
        "overlay_extra_defines=-DLISP65_STACK_GUARD",
        f"overlay_entry={OVERLAY_ENTRY}",
        "overlay_descriptor=L65O-v1-18-byte-crc16-ccitt-false",
    ):
        if required_line not in contract_lines:
            errors.append(f"guard ABI contract is missing: {required_line}")

    if stdlib_manifest.get("format") != "lisp65-bytecode-p0-stdlib-artifacts-v1":
        errors.append("stdlib artifact manifest has an unexpected format")
    if stdlib_manifest.get("artifact_role") != "stdlib":
        errors.append("stdlib artifact manifest must have artifact_role=stdlib")
    if stdlib_manifest.get("suite") != STDLIB_SUITE:
        errors.append(f"stdlib artifact manifest suite must be {STDLIB_SUITE}")
    if stdlib["manifest_sha256"] != _sha256(stdlib_manifest_path):
        errors.append("overlay binding does not match the shipped stdlib manifest")
    try:
        manifest_base = int(stdlib_manifest.get("base_addr"), 0)
    except (TypeError, ValueError):
        manifest_base = -1
        errors.append("stdlib artifact manifest base_addr is invalid")
    if manifest_base != stdlib["base"]:
        errors.append("stdlib base differs between inner and overlay manifests")
    external_image = stdlib_manifest.get("external_image")
    if not isinstance(external_image, dict):
        errors.append("stdlib artifact manifest external_image must be an object")
    else:
        if external_image.get("format") != "lisp65-bytecode-p0-ext-image-v1":
            errors.append("stdlib external image has an unexpected format")
        if external_image.get("bytes") != stdlib["size"]:
            errors.append("inner stdlib image size differs from the overlay prefix binding")
        if external_image.get("sha256") != stdlib["sha256"]:
            errors.append("inner stdlib image hash differs from the overlay prefix binding")

    if preload["size"] != len(blob_data) or preload["sha256"] != _sha256_bytes(blob_data):
        errors.append("overlay preload binding does not match the shipped combined blob")
    if preload["base"] != stdlib["base"] or preload["end"] != preload["base"] + len(blob_data):
        errors.append("combined preload address span is inconsistent")
    if stdlib["end"] != stdlib["base"] + stdlib["size"]:
        errors.append("stdlib prefix end must equal base plus size")
    if stdlib["size"] > len(blob_data):
        errors.append("stdlib prefix exceeds the combined preload")
        return errors
    stdlib_prefix = blob_data[:stdlib["size"]]
    if _sha256_bytes(stdlib_prefix) != stdlib["sha256"]:
        errors.append("shipped combined blob has the wrong stdlib prefix")

    expected_stage_address = (stdlib["end"] + STAGE_ALIGNMENT - 1) & ~(STAGE_ALIGNMENT - 1)
    if stage["address"] != expected_stage_address:
        errors.append("overlay stage is not at the first 256-byte boundary after stdlib")
    if stage["bank"] != stage["address"] // BANK_SIZE or stage["offset"] != stage["address"] % BANK_SIZE:
        errors.append("overlay stage bank/offset does not match its flat address")
    stage_relative = stage["address"] - preload["base"]
    if stage_relative != stdlib["size"] + stage["padding_after_stdlib"]:
        errors.append("overlay stage padding is inconsistent")
    if not stdlib["size"] <= stage_relative <= len(blob_data):
        errors.append("overlay stage offset lies outside the combined preload")
        return errors
    padding = blob_data[stdlib["size"]:stage_relative]
    if any(padding):
        errors.append("combined preload alignment padding must be zero-filled")
    stage_data = blob_data[stage_relative:]
    if len(stage_data) != stage["size"] or _sha256_bytes(stage_data) != stage["sha256"]:
        errors.append("overlay stage binding does not match descriptor plus payload")
    if stage["size"] != DESCRIPTOR_SIZE + overlay["size"]:
        errors.append("overlay stage size must equal descriptor plus payload")
    if stage["end_offset"] != stage["offset"] + stage["size"]:
        errors.append("overlay stage end_offset is inconsistent")
    if stage["end_offset"] > stage["limit_offset"]:
        errors.append("overlay stage reaches the Bank-5 namepool limit")
    if len(stage_data) < DESCRIPTOR_SIZE:
        errors.append("overlay stage is shorter than its descriptor")
        return errors

    magic, version, header_size, build_id, base, entry, size, crc16 = struct.unpack(
        "<4sBBIHHHH", stage_data[:DESCRIPTOR_SIZE]
    )
    expected_descriptor = (
        DESCRIPTOR_MAGIC, DESCRIPTOR_VERSION, DESCRIPTOR_SIZE, binding["build_id"],
        overlay["base"], overlay["entry"], overlay["size"], descriptor["crc16"],
    )
    if (magic, version, header_size, build_id, base, entry, size, crc16) != expected_descriptor:
        errors.append("shipped stage descriptor does not match manifest bindings")
    payload = stage_data[DESCRIPTOR_SIZE:]
    if len(payload) != overlay["size"] or _sha256_bytes(payload) != overlay["sha256"]:
        errors.append("shipped stage payload does not match the overlay binding")
    actual_crc = _crc16_ccitt_false(payload)
    if actual_crc != descriptor["crc16"] or actual_crc != crc16:
        errors.append("shipped overlay payload CRC-16/CCITT-FALSE mismatch")
    return errors


def _stdlib_trust_errors(
    package_dir: Path,
    artifacts: Any,
    trust: Any,
    overlay_binding: Any,
    runtime_overlay_binding: Any,
) -> list[str]:
    errors = _shape_errors(trust, "stdlib_trust", STDLIB_TRUST_FIELDS)
    if not isinstance(trust, dict):
        return errors
    errors.extend(
        _shape_errors(trust.get("semantic_gate"), "stdlib_trust.semantic_gate", STDLIB_GATE_FIELDS)
    )
    errors.extend(
        _shape_errors(
            trust.get("runtime_binding"),
            "stdlib_trust.runtime_binding",
            STDLIB_RUNTIME_BINDING_FIELDS,
        )
    )
    errors.extend(
        _shape_errors(
            trust.get("literal_envelope"),
            "stdlib_trust.literal_envelope",
            STDLIB_LITERAL_ENVELOPE_FIELDS,
        )
    )
    errors.extend(
        _shape_errors(
            trust.get("integrity_policy"),
            "stdlib_trust.integrity_policy",
            STDLIB_INTEGRITY_POLICY_FIELDS,
        )
    )
    if errors:
        return errors
    if not isinstance(artifacts, list) or not isinstance(overlay_binding, dict):
        return errors
    records = {
        record.get("id"): record
        for record in artifacts
        if isinstance(record, dict) and isinstance(record.get("id"), str)
    }
    if not isinstance(records.get("stdlib-artifact-manifest"), dict):
        return errors
    if not isinstance(records.get("workbench-stdlib-blob"), dict):
        return errors

    semantic_gate = trust["semantic_gate"]
    runtime_binding = trust["runtime_binding"]
    literal_envelope = trust["literal_envelope"]
    integrity_policy = trust["integrity_policy"]
    if trust.get("schema") != STDLIB_TRUST_SCHEMA:
        errors.append(f"stdlib_trust.schema must be {STDLIB_TRUST_SCHEMA}")
    if trust.get("trust_model") != STDLIB_TRUST_MODEL:
        errors.append(f"stdlib_trust.trust_model must be {STDLIB_TRUST_MODEL}")
    expected_gate_constants = {
        "result": "pass",
        "producer": STDLIB_GATE_PRODUCER,
        "suite": STDLIB_SUITE,
        "artifact": "stdlib-artifact-manifest",
    }
    for name, expected in expected_gate_constants.items():
        if semantic_gate.get(name) != expected:
            errors.append(f"stdlib_trust.semantic_gate.{name} must be {expected!r}")
    expected_runtime_constants = {
        "contract": ARTIFACT_PATHS["resolved-profile"],
        "artifact": "workbench-stdlib-blob",
        "file": ARTIFACT_PATHS["workbench-stdlib-blob"],
        "address": 0x050000,
        "offset": 0,
        "crc16_algorithm": "crc-16-ccitt-false",
    }
    for name, expected in expected_runtime_constants.items():
        if runtime_binding.get(name) != expected:
            errors.append(f"stdlib_trust.runtime_binding.{name} must be {expected!r}")
    for name in ("case_count", "function_count", "object_count"):
        if not _integer(semantic_gate.get(name), 0, 0x10000000):
            errors.append(f"stdlib_trust.semantic_gate.{name} must be a non-negative integer")
    if not _valid_hex(semantic_gate.get("artifact_sha256")):
        errors.append("stdlib_trust.semantic_gate.artifact_sha256 must be a lowercase SHA-256")
    if not _valid_hex(runtime_binding.get("contract_sha256")):
        errors.append("stdlib_trust.runtime_binding.contract_sha256 must be a lowercase SHA-256")
    if not _valid_hex(runtime_binding.get("sha256")):
        errors.append("stdlib_trust.runtime_binding.sha256 must be a lowercase SHA-256")
    if not _integer(runtime_binding.get("build_id"), 0, 0xFFFFFFFF):
        errors.append("stdlib_trust.runtime_binding.build_id must be a 32-bit integer")
    if not _integer(runtime_binding.get("length"), 1, 0x10000000):
        errors.append("stdlib_trust.runtime_binding.length must be a positive integer")
    if not _integer(runtime_binding.get("crc16"), 0, 0xFFFF):
        errors.append("stdlib_trust.runtime_binding.crc16 must be a 16-bit integer")
    expected_literal_constants = {
        "mode": "profile-bound-flat-literals",
        "nil": 0,
        "t": 0,
        "cons": 0,
        "list": 0,
        "aggregate_policy": "build-reject",
    }
    for name, expected in expected_literal_constants.items():
        if literal_envelope.get(name) != expected:
            errors.append(f"stdlib_trust.literal_envelope.{name} must be {expected!r}")
    for name in ("node_count", "patch_count", "fix", "symbol", "string"):
        if not _integer(literal_envelope.get(name), 0, 0xFFFF):
            errors.append(f"stdlib_trust.literal_envelope.{name} must be a uint16")
    if (
        all(type(literal_envelope.get(name)) is int for name in ("fix", "symbol", "string"))
        and literal_envelope.get("fix") + literal_envelope.get("symbol")
            + literal_envelope.get("string") != literal_envelope.get("node_count")
    ):
        errors.append("stdlib_trust literal kinds do not cover the flat node envelope")
    expected_integrity = {
        "crc_passes": 1,
        "covered_bytes": runtime_binding.get("length"),
        "trigger": "once-before-first-bank5-boot-mutation",
        "subsequent_append_rechecks": 0,
        "overlay_calls": 3,
    }
    for name, expected in expected_integrity.items():
        if integrity_policy.get(name) != expected:
            errors.append(f"stdlib_trust.integrity_policy.{name} must be {expected!r}")
    if errors:
        return errors

    try:
        stdlib_manifest_path = package_dir / ARTIFACT_PATHS["stdlib-artifact-manifest"]
        contract_path = package_dir / ARTIFACT_PATHS["resolved-profile"]
        blob_path = package_dir / ARTIFACT_PATHS["workbench-stdlib-blob"]
        _regular_file(stdlib_manifest_path, "stdlib semantic gate artifact")
        _regular_file(contract_path, "stdlib trust ABI contract")
        _regular_file(blob_path, "stdlib preload")
        stdlib_manifest = _read_json(stdlib_manifest_path)
        contract_data = contract_path.read_bytes()
        blob = blob_path.read_bytes()
    except (OSError, ShipError) as exc:
        return errors + [str(exc)]

    manifest_sha = _sha256_bytes(stdlib_manifest_path.read_bytes())
    if semantic_gate["artifact_sha256"] != manifest_sha:
        errors.append("stdlib semantic gate hash does not match its shipped result artifact")
    if semantic_gate["artifact_sha256"] != records["stdlib-artifact-manifest"].get("sha256"):
        errors.append("stdlib semantic gate hash differs from the artifact record")
    cases = stdlib_manifest.get("cases")
    functions = stdlib_manifest.get("functions")
    objects = stdlib_manifest.get("objects")
    if not isinstance(cases, list):
        errors.append("stdlib semantic gate artifact cases must be an array")
    elif semantic_gate["case_count"] != len(cases):
        errors.append("stdlib semantic gate case count differs from its result artifact")
    if not isinstance(functions, list):
        errors.append("stdlib semantic gate artifact functions must be an array")
    elif semantic_gate["function_count"] != len(functions):
        errors.append("stdlib semantic gate function count differs from its result artifact")
    if type(objects) is not int or objects < 0:
        errors.append("stdlib semantic gate artifact objects must be a non-negative integer")
    elif semantic_gate["object_count"] != objects:
        errors.append("stdlib semantic gate object count differs from its result artifact")

    contract_sha = _sha256_bytes(contract_data)
    build_id = int(contract_sha[:8], 16)
    if runtime_binding["contract_sha256"] != contract_sha:
        errors.append("stdlib runtime binding contract hash differs from resolved-profile.txt")
    if runtime_binding["build_id"] != build_id:
        errors.append("stdlib runtime binding build ID is not derived from the contract hash")
    try:
        contract_lines = set(contract_data.decode("ascii", "strict").splitlines())
    except UnicodeError:
        errors.append("stdlib runtime binding contract must be ASCII")
        contract_lines = set()
    for required_line in (
        f"bytecode_manifest_sha256={manifest_sha}",
        f"external_image_sha256={runtime_binding['sha256']}",
    ):
        if required_line not in contract_lines:
            errors.append(f"stdlib trust contract is missing: {required_line}")

    offset = runtime_binding["offset"]
    length = runtime_binding["length"]
    if offset + length > len(blob):
        errors.append("stdlib runtime binding span exceeds the shipped Bank-5 blob")
        return errors
    prefix = blob[offset : offset + length]
    if runtime_binding["sha256"] != _sha256_bytes(prefix):
        errors.append("stdlib runtime binding SHA-256 differs from the shipped Bank-5 span")
    if runtime_binding["crc16"] != _crc16_ccitt_false(prefix):
        errors.append("stdlib runtime binding CRC-16 differs from the shipped Bank-5 span")
    external_image = stdlib_manifest.get("external_image")
    if not isinstance(external_image, dict) or type(external_image.get("metadata_offset")) is not int:
        errors.append("stdlib semantic gate artifact has no literal-envelope metadata offset")
    else:
        try:
            actual_envelope = WorkbenchOverlayStage.stdlib_literal_envelope(
                prefix, external_image["metadata_offset"]
            )
        except WorkbenchOverlayStage.StageError as exc:
            errors.append(f"stdlib shipped literal envelope is invalid: {exc}")
        else:
            expected_envelope = {
                "node_count": actual_envelope["node_count"],
                "patch_count": actual_envelope["patch_count"],
                **{
                    name: actual_envelope[name]
                    for name in ("fix", "nil", "t", "symbol", "cons", "list", "string")
                },
            }
            for name, expected in expected_envelope.items():
                if literal_envelope.get(name) != expected:
                    errors.append(
                        f"stdlib_trust.literal_envelope.{name} differs from the shipped image"
                    )

    stdlib = overlay_binding.get("stdlib")
    abi = overlay_binding.get("abi")
    if not isinstance(stdlib, dict) or not isinstance(abi, dict):
        errors.append("stdlib trust requires the existing overlay stdlib and ABI bindings")
    else:
        expected_overlay_fields = {
            "base": runtime_binding["address"],
            "size": runtime_binding["length"],
            "sha256": runtime_binding["sha256"],
            "manifest_sha256": semantic_gate["artifact_sha256"],
        }
        for name, expected in expected_overlay_fields.items():
            if stdlib.get(name) != expected:
                errors.append(f"stdlib trust differs from overlay.stdlib.{name}")
        if abi.get("contract_sha256") != runtime_binding["contract_sha256"]:
            errors.append("stdlib trust differs from the overlay ABI contract hash")
        if overlay_binding.get("build_id") != runtime_binding["build_id"]:
            errors.append("stdlib trust differs from the boot overlay build ID")
    external_image = stdlib_manifest.get("external_image")
    if not isinstance(external_image, dict):
        errors.append("stdlib semantic gate artifact external_image must be an object")
    elif (
        external_image.get("bytes") != runtime_binding["length"]
        or external_image.get("sha256") != runtime_binding["sha256"]
    ):
        errors.append("stdlib semantic gate output differs from the runtime-bound Bank-5 span")
    if isinstance(runtime_overlay_binding, dict):
        if runtime_overlay_binding.get("profile_build_id") != runtime_binding["build_id"]:
            errors.append("stdlib trust differs from the runtime-overlay profile build ID")
        runtime_abi = runtime_overlay_binding.get("abi")
        if (
            not isinstance(runtime_abi, dict)
            or runtime_abi.get("sha256") != runtime_binding["contract_sha256"]
        ):
            errors.append("stdlib trust differs from the runtime-overlay ABI contract hash")
    return errors


def _runtime_overlay_slot_errors(
    binding: Any, slot_budget: Any, manifest_format: str
) -> list[str]:
    errors = _shape_errors(
        slot_budget, "runtime_overlay_slots", RUNTIME_OVERLAY_SLOT_FIELDS
    )
    if not isinstance(slot_budget, dict):
        return errors
    assignments = slot_budget.get("assignments")
    if not isinstance(assignments, list):
        errors.append("runtime_overlay_slots.assignments must be an array")
    else:
        for index, assignment in enumerate(assignments):
            errors.extend(
                _shape_errors(
                    assignment,
                    f"runtime_overlay_slots.assignments[{index}]",
                    RUNTIME_OVERLAY_SLOT_ASSIGNMENT_FIELDS,
                )
            )
    if errors or not isinstance(binding, dict):
        return errors
    slices = binding.get("slices")
    policy = binding.get("policy")
    if not isinstance(slices, list) or not isinstance(policy, dict):
        return errors
    if manifest_format == MANIFEST_FORMAT_V4:
        capacity = V4_RUNTIME_MAX_SLICES
        product_limit = V4_RUNTIME_PRODUCT_SLOT_LIMIT
        slot_schema = V4_RUNTIME_SLOT_SCHEMA
    else:
        capacity = RuntimeOverlayBank.MAX_SLICES
        product_limit = RUNTIME_OVERLAY_PRODUCT_SLOT_LIMIT
        slot_schema = RUNTIME_OVERLAY_SLOT_SCHEMA
    expected = _runtime_overlay_slot_binding(binding, product_limit)
    if slot_budget.get("schema") != slot_schema:
        errors.append(f"runtime_overlay_slots.schema must be {slot_schema}")
    if slot_budget.get("capacity") != capacity:
        errors.append(f"runtime overlay slot capacity must be {capacity}")
    if slot_budget.get("product_limit") != product_limit:
        errors.append(
            f"runtime overlay product slot limit must be {product_limit}"
        )
    if len(slices) > product_limit:
        errors.append(
            f"runtime overlay uses {len(slices)} slots, product limit is "
            f"{product_limit}"
        )
    for name in ("capacity", "used", "reserve_to_limit", "free", "assignments"):
        if slot_budget.get(name) != expected[name]:
            errors.append(f"runtime_overlay_slots.{name} differs from the runtime catalog")
    return errors


def _validate_legacy_runtime_overlay_manifest(binding: dict[str, Any]) -> None:
    """Validate the frozen Ship-v4 Bank-3 manifest vocabulary."""
    def shape(value: Any, fields: set[str], label: str) -> dict[str, Any]:
        if not isinstance(value, dict) or set(value) != fields:
            raise ShipError(f"legacy runtime overlay {label} fields differ")
        return value

    shape(binding, V4_RUNTIME_TOP_FIELDS, "manifest")
    abi = shape(binding.get("abi"), V4_RUNTIME_ABI_FIELDS, "ABI")
    elf = shape(binding.get("elf"), V4_RUNTIME_FILE_FIELDS, "ELF")
    storage = binding.get("storage")
    catalog = binding.get("catalog")
    storage = shape(storage, V4_RUNTIME_STORAGE_FIELDS, "storage")
    catalog = shape(catalog, V4_RUNTIME_CATALOG_FIELDS, "catalog")
    shape(binding.get("config_header"), V4_RUNTIME_FILE_FIELDS, "config header")
    policy = shape(binding.get("policy"), V4_RUNTIME_POLICY_FIELDS, "policy")
    if binding.get("schema") != V4_RUNTIME_FORMAT:
        raise ShipError("legacy runtime overlay schema is not L65R-v1")
    if not isinstance(binding.get("profile"), str) or not binding["profile"]:
        raise ShipError("legacy runtime overlay profile is invalid")
    for label, digest in (
        ("ABI", abi.get("sha256")),
        ("ELF", elf.get("sha256")),
        ("storage", storage.get("sha256")),
        ("config header", binding["config_header"].get("sha256")),
    ):
        if not _valid_hex(digest):
            raise ShipError(f"legacy runtime overlay {label} SHA-256 is invalid")
    expected_build_id = int(abi["sha256"][:8], 16)
    if binding.get("profile_build_id") != expected_build_id:
        raise ShipError("legacy runtime overlay build ID is not derived from its ABI SHA")
    legacy_base = V4_RUNTIME_BANK * V4_RUNTIME_BANK_SIZE
    if (
        storage.get("format") != V4_RUNTIME_FORMAT
        or storage.get("bank") != V4_RUNTIME_BANK
        or storage.get("base") != legacy_base
        or storage.get("limit") != legacy_base + V4_RUNTIME_BANK_SIZE
    ):
        raise ShipError("legacy runtime overlay storage is not dedicated Bank 3")
    if not _integer(storage.get("size"), 1, V4_RUNTIME_BANK_SIZE):
        raise ShipError("legacy runtime overlay storage size is invalid")
    expected_catalog = {
        "magic": "L65R",
        "version": 1,
        "header_size": 32,
        "entry_size": 32,
        "flags": 0,
        "directory_offset": 32,
        "crc16_algorithm": "crc-16-ccitt-false",
    }
    if any(catalog.get(name) != expected for name, expected in expected_catalog.items()):
        raise ShipError("legacy runtime overlay catalog constants are invalid")
    expected_policy = {
        "max_slices": V4_RUNTIME_MAX_SLICES,
        "max_slice_bytes": V4_RUNTIME_MAX_SLICE_BYTES,
        "max_boot_slice_bytes": V4_RUNTIME_MAX_BOOT_SLICE_BYTES,
        "payload_alignment": V4_RUNTIME_PAYLOAD_ALIGNMENT,
        "entry_abi": V4_RUNTIME_ENTRY_ABI,
    }
    if any(policy.get(name) != expected for name, expected in expected_policy.items()):
        raise ShipError("legacy runtime overlay policy constants are invalid")
    if not _integer(policy.get("common_vma"), 0, 0xFFFF):
        raise ShipError("legacy runtime overlay common VMA is invalid")

    slices = binding.get("slices")
    if not isinstance(slices, list) or not 1 <= len(slices) <= V4_RUNTIME_MAX_SLICES:
        raise ShipError("legacy runtime overlay slices are invalid")
    if catalog.get("slice_count") != len(slices):
        raise ShipError("legacy runtime overlay catalog count differs from its slices")
    for name in ("payload_offset", "directory_crc16", "header_crc16"):
        if not _integer(catalog.get(name), 0, 0xFFFF):
            raise ShipError(f"legacy runtime overlay catalog {name} is invalid")
    ids: list[int] = []
    for index, record in enumerate(slices):
        record = shape(record, V4_RUNTIME_SLICE_FIELDS, f"slice[{index}]")
        ids.append(record.get("id"))
        flags = record.get("flags")
        if not _integer(flags, 0, 0xFFFF) or flags & ~V4_RUNTIME_KNOWN_FLAGS:
            raise ShipError(f"legacy runtime overlay slice[{index}] flags are invalid")
        if bool(flags & V4_RUNTIME_FLAG_BOOT) == bool(flags & V4_RUNTIME_FLAG_RUNTIME):
            raise ShipError(f"legacy runtime overlay slice[{index}] flags are ambiguous")
        if flags & V4_RUNTIME_FLAG_REUSABLE and not flags & V4_RUNTIME_FLAG_RUNTIME:
            raise ShipError(f"legacy runtime overlay slice[{index}] reusable flag is invalid")
        roles = []
        if flags & V4_RUNTIME_FLAG_BOOT:
            roles.append("boot")
        if flags & V4_RUNTIME_FLAG_RUNTIME:
            roles.append("runtime")
        if flags & V4_RUNTIME_FLAG_REUSABLE:
            roles.append("reusable")
        if record.get("roles") != roles:
            raise ShipError(f"legacy runtime overlay slice[{index}] roles differ from flags")
        if record.get("abi_version") != V4_RUNTIME_ENTRY_ABI:
            raise ShipError(f"legacy runtime overlay slice[{index}] ABI is invalid")
        if record.get("slice_build_id") != expected_build_id:
            raise ShipError(f"legacy runtime overlay slice[{index}] build ID differs")
        if not _valid_hex(record.get("sha256")):
            raise ShipError(f"legacy runtime overlay slice[{index}] SHA-256 is invalid")
    if ids != list(range(len(slices))):
        raise ShipError("legacy runtime overlay slice IDs are not dense")


def _legacy_runtime_overlay_header(
    profile_build_id: int,
    slices: Any,
) -> bytes:
    if not isinstance(slices, tuple) or len(slices) < 2:
        raise ShipError("legacy runtime overlay verifier slices are missing")
    catalog, record = slices[0], slices[1]
    lines = [
        "/* Generated by runtime_overlay_bank.py; do not edit. */",
        "#ifndef LISP65_RUNTIME_OVERLAY_BANK_CONFIG_H",
        "#define LISP65_RUNTIME_OVERLAY_BANK_CONFIG_H",
        "",
        f"#define LISP65_RUNTIME_OVERLAY_BANK 0x{V4_RUNTIME_BANK:02x}u",
        "#define LISP65_RUNTIME_OVERLAY_CATALOG_OFF 0x0000u",
        f"#define LISP65_RUNTIME_OVERLAY_PROFILE_BUILD_ID 0x{profile_build_id:08x}UL",
        f"#define LISP65_RUNTIME_OVERLAY_MAX_SLICE_BYTES {V4_RUNTIME_MAX_SLICE_BYTES}u",
        f"#define LISP65_RUNTIME_OVERLAY_BOOT_MAX_SLICE_BYTES {V4_RUNTIME_MAX_BOOT_SLICE_BYTES}u",
        f"#define LISP65_RUNTIME_OVERLAY_ENTRY_ABI {V4_RUNTIME_ENTRY_ABI}u",
        "",
        f"#define LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_OFF 0x{catalog.file_offset:04x}u",
        f"#define LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_SIZE 0x{catalog.file_size:04x}u",
        f"#define LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_ENTRY_OFFSET 0x{catalog.entry_offset:04x}u",
        f"#define LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_CRC16 0x{catalog.crc16:04x}u",
        f"#define LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_FILE_OFF 0x{record.file_offset:04x}u",
        f"#define LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_FILE_SIZE 0x{record.file_size:04x}u",
        f"#define LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_ENTRY_OFFSET 0x{record.entry_offset:04x}u",
        f"#define LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_CRC16 0x{record.crc16:04x}u",
        "",
        "#endif /* LISP65_RUNTIME_OVERLAY_BANK_CONFIG_H */",
        "",
    ]
    return "\n".join(lines).encode("ascii")


def _v5_runtime_profile_errors(contract: bytes) -> list[str]:
    try:
        lines = contract.decode("ascii").splitlines()
    except UnicodeDecodeError:
        return ["runtime overlay ABI contract must be ASCII"]
    errors: list[str] = []
    for expected in V5_RUNTIME_PROFILE_LINES:
        key = expected.split("=", 1)[0]
        matches = [line for line in lines if line.startswith(key + "=")]
        if matches != [expected]:
            errors.append(
                f"runtime overlay ABI contract must contain exactly once: {expected}"
            )
    return errors


def _runtime_overlay_contract_errors(
    package_dir: Path,
    artifacts: Any,
    binding: Any,
    preloads: Any,
    boot_binding: Any,
    manifest_format: str,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(artifacts, list):
        return errors
    records = {
        artifact.get("id"): artifact
        for artifact in artifacts
        if isinstance(artifact, dict) and isinstance(artifact.get("id"), str)
    }
    runtime_record = records.get(RUNTIME_OVERLAY_ARTIFACT_ID)
    blob_record = records.get("workbench-stdlib-blob")
    if not isinstance(runtime_record, dict) or not isinstance(blob_record, dict):
        return errors
    if not isinstance(binding, dict):
        return ["runtime_overlays must be an object"]
    try:
        if manifest_format == MANIFEST_FORMAT_V4:
            _validate_legacy_runtime_overlay_manifest(binding)
        else:
            RuntimeOverlayBank.validate_manifest(binding)
    except (ShipError, RuntimeOverlayBank.OverlayBankError, TypeError, ValueError) as exc:
        return [f"runtime_overlays manifest is invalid: {exc}"]

    if binding.get("profile") != PROFILE:
        errors.append(f"runtime_overlays.profile must be {PROFILE}")
    abi = binding["abi"]
    storage = binding["storage"]
    config_header = binding["config_header"]
    if abi.get("contract") != ARTIFACT_PATHS["resolved-profile"]:
        errors.append("runtime_overlays ABI contract must be resolved-profile.txt")
    if storage.get("file") != RUNTIME_OVERLAY_ARTIFACT:
        errors.append(f"runtime_overlays storage file must be {RUNTIME_OVERLAY_ARTIFACT}")
    for label, name in (
        ("config header", config_header.get("file")),
        ("ELF", binding["elf"].get("file")),
    ):
        if (
            not isinstance(name, str)
            or not name
            or name in {".", ".."}
            or PurePosixPath(name).name != name
        ):
            errors.append(f"runtime_overlays {label} file must be a plain basename")
    if config_header.get("file") != RUNTIME_OVERLAY_HEADER:
        errors.append(
            f"runtime_overlays config header file must be {RUNTIME_OVERLAY_HEADER}"
        )
    try:
        image_path = package_dir / ARTIFACT_PATHS[RUNTIME_OVERLAY_ARTIFACT_ID]
        contract_path = package_dir / ARTIFACT_PATHS["resolved-profile"]
        _regular_file(image_path, "runtime overlay bank image")
        _regular_file(contract_path, "runtime overlay ABI contract")
        image = image_path.read_bytes()
        contract = contract_path.read_bytes()
    except (OSError, ShipError) as exc:
        return errors + [str(exc)]
    if abi.get("sha256") != _sha256(contract_path):
        errors.append("runtime_overlays ABI hash does not match resolved-profile.txt")
    if manifest_format == MANIFEST_FORMAT_V5:
        errors.extend(_v5_runtime_profile_errors(contract))
    if storage.get("size") != len(image) or storage.get("sha256") != _sha256_bytes(image):
        errors.append("runtime_overlays storage binding does not match the shipped image")
    if manifest_format == MANIFEST_FORMAT_V5:
        if storage.get("crc16") != _crc16_ccitt_false(image):
            errors.append("runtime_overlays whole-image CRC-16 differs from the shipped image")
        if storage.get("build_id") != binding.get("profile_build_id"):
            errors.append("runtime_overlays storage build ID differs from the profile")
    if runtime_record.get("size") != len(image) or runtime_record.get("sha256") != _sha256_bytes(image):
        errors.append("runtime overlay artifact record does not match the shipped image")

    manifest_slices = binding["slices"]
    canonical_slice_count = (
        V4_RUNTIME_PRODUCT_SLOT_LIMIT
        if manifest_format == MANIFEST_FORMAT_V4
        else RUNTIME_OVERLAY_SLICE_COUNT
    )
    canonical_slices = RUNTIME_OVERLAY_CANONICAL_SLICES[:canonical_slice_count]
    if len(manifest_slices) < canonical_slice_count:
        errors.append(
            "runtime_overlays must begin with all "
            f"{canonical_slice_count} canonical base slices"
        )
    else:
        for index, (record, canonical) in enumerate(
            zip(
                manifest_slices[:canonical_slice_count],
                canonical_slices,
            )
        ):
            expected_contract = {
                "id": index,
                "name": canonical[0],
                "section": canonical[1],
                "start_symbol": canonical[2],
                "end_symbol": canonical[3],
                "entry_symbol": canonical[4],
                "flags": canonical[5],
                "roles": (["boot"] if canonical[5] == RuntimeOverlayBank.FLAG_BOOT
                          else ["runtime", "reusable"]),
                "abi_version": (
                    V4_RUNTIME_ENTRY_ABI
                    if manifest_format == MANIFEST_FORMAT_V4
                    else RuntimeOverlayBank.ENTRY_ABI
                ),
                "capability_mask": 0,
            }
            for name, expected in expected_contract.items():
                if record.get(name) != expected:
                    errors.append(
                        f"runtime_overlays slice[{index}].{name} is not canonical"
                    )

    try:
        parsed = RuntimeOverlayBank.validate_image(
            image,
            expected_build_id=binding["profile_build_id"],
            expected_vma=binding["policy"]["common_vma"],
            max_slice_bytes=binding["policy"]["max_slice_bytes"],
            max_vma=(
                0xFFFF
                if manifest_format == MANIFEST_FORMAT_V4
                else RuntimeOverlayBank.MAX_VMA
            ),
        )
    except (RuntimeOverlayBank.OverlayBankError, TypeError, ValueError) as exc:
        errors.append(f"runtime overlay bank image is invalid: {exc}")
        parsed = None
    if parsed is not None:
        if manifest_format == MANIFEST_FORMAT_V4:
            expected_header = _legacy_runtime_overlay_header(
                binding["profile_build_id"], parsed.slices
            )
        else:
            expected_header = RuntimeOverlayBank.render_header(
                profile_build_id=binding["profile_build_id"],
                verifier_slices=parsed.slices,
            )
        if config_header.get("sha256") != _sha256_bytes(expected_header):
            errors.append(
                "runtime_overlays config header hash is not the exact verifier binding"
            )
        expected_catalog = {
            "slice_count": len(parsed.slices),
            "payload_offset": parsed.payload_offset,
            "directory_crc16": parsed.directory_crc16,
            "header_crc16": parsed.header_crc16,
        }
        for name, expected in expected_catalog.items():
            if binding["catalog"].get(name) != expected:
                errors.append(f"runtime_overlays catalog.{name} differs from the image")
        if len(manifest_slices) != len(parsed.slices):
            errors.append("runtime overlay manifest slice count differs from the image")
        else:
            for index, (record, entry) in enumerate(zip(manifest_slices, parsed.slices)):
                expected_fields = {
                    "id": entry.id,
                    "flags": entry.flags,
                    "file_offset": entry.file_offset,
                    "file_size": entry.file_size,
                    "memory_size": entry.memory_size,
                    "vma": entry.vma,
                    "end": entry.vma + entry.memory_size,
                    "entry": entry.vma + entry.entry_offset,
                    "entry_offset": entry.entry_offset,
                    "abi_version": entry.abi_version,
                    "slice_build_id": entry.slice_build_id,
                    "capability_mask": entry.capability_mask,
                    "crc16": entry.crc16,
                }
                for name, expected in expected_fields.items():
                    if record.get(name) != expected:
                        errors.append(
                            f"runtime_overlays slice[{index}].{name} differs from the image"
                        )
                payload = image[entry.file_offset : entry.file_offset + entry.file_size]
                if record.get("sha256") != _sha256_bytes(payload):
                    errors.append(f"runtime_overlays slice[{index}] SHA-256 differs from the image")

    if not isinstance(preloads, list) or len(preloads) != 2:
        errors.append("preloads must contain exactly the runtime-catalog and Bank-5 records")
        return errors
    for index, record in enumerate(preloads):
        if not isinstance(record, dict):
            errors.append(f"preloads[{index}] must be an object")
        else:
            fields = (
                RUNTIME_PRELOAD_FIELDS_V5
                if manifest_format == MANIFEST_FORMAT_V5 and index == 0
                else RUNTIME_PRELOAD_FIELDS_V4
            )
            missing = sorted(fields - record.keys())
            extra = sorted(record.keys() - fields)
            if missing or extra:
                errors.append(
                    f"preloads[{index}] fields differ: "
                    f"missing={','.join(missing)} extra={','.join(extra)}"
                )
    if errors:
        return errors
    if manifest_format == MANIFEST_FORMAT_V5:
        expected_runtime_preload = {
            "role": RUNTIME_PRELOAD_ROLE,
            "artifact": RUNTIME_OVERLAY_ARTIFACT_ID,
            "file": RUNTIME_OVERLAY_ARTIFACT,
            "kind": RuntimeOverlayBank.STORAGE_KIND,
            "address": RuntimeOverlayBank.STORAGE_BASE,
            "address_bits": RuntimeOverlayBank.STORAGE_ADDRESS_BITS,
            "length": runtime_record.get("size"),
            "crc16": _crc16_ccitt_false(image),
            "crc16_algorithm": "crc-16-ccitt-false",
            "sha256": runtime_record.get("sha256"),
            "build_id": binding.get("profile_build_id"),
            "persistence": RuntimeOverlayBank.STORAGE_PERSISTENCE,
            "recovery": RUNTIME_PRELOAD_RECOVERY,
        }
    else:
        expected_runtime_preload = {
            "role": RUNTIME_PRELOAD_ROLE,
            "artifact": RUNTIME_OVERLAY_ARTIFACT_ID,
            "file": RUNTIME_OVERLAY_ARTIFACT,
            "bank": V4_RUNTIME_BANK,
            "address": V4_RUNTIME_BANK * V4_RUNTIME_BANK_SIZE,
            "size": runtime_record.get("size"),
            "sha256": runtime_record.get("sha256"),
        }
    expected_preloads = [
        expected_runtime_preload,
        {
            "role": STDLIB_PRELOAD_ROLE,
            "artifact": "workbench-stdlib-blob",
            "file": ARTIFACT_PATHS["workbench-stdlib-blob"],
            "bank": 5,
            "address": 0x050000,
            "size": blob_record.get("size"),
            "sha256": blob_record.get("sha256"),
        },
    ]
    if preloads != expected_preloads:
        errors.append("preloads are not the exact canonical runtime-catalog/Bank-5 plan")
    if isinstance(boot_binding, dict) and isinstance(boot_binding.get("preload"), dict):
        boot_preload = boot_binding["preload"]
        if (
            boot_preload.get("base") != expected_preloads[1]["address"]
            or boot_preload.get("size") != expected_preloads[1]["size"]
            or boot_preload.get("sha256") != expected_preloads[1]["sha256"]
        ):
            errors.append("Bank-5 preload differs from the existing combined boot/stdlib binding")
    return errors


def _manifest_errors(package_dir: Path, manifest: dict[str, Any], strict: bool) -> list[str]:
    errors: list[str] = []
    manifest_format = manifest.get("manifest_format")
    common_required = {
        "manifest_format", "product", "profile", "status", "source", "gates",
        "artifacts", "overlay",
    }
    if manifest_format == MANIFEST_FORMAT_V3:
        required = common_required
        artifact_specs = ARTIFACT_SPECS_V3
        artifact_paths = ARTIFACT_PATHS_V3
    elif manifest_format in {MANIFEST_FORMAT_V4, MANIFEST_FORMAT_V5}:
        required = common_required | {
            "runtime_overlays", "runtime_overlay_slots", "preloads", "stdlib_trust",
            "error_texts",
        }
        artifact_specs = (
            ARTIFACT_SPECS_V4
            if manifest_format == MANIFEST_FORMAT_V4
            else ARTIFACT_SPECS_V5
        )
        artifact_paths = ARTIFACT_PATHS
    else:
        required = common_required
        artifact_specs = ARTIFACT_SPECS_V5
        artifact_paths = ARTIFACT_PATHS
    missing = sorted(required - manifest.keys())
    extra = sorted(manifest.keys() - required)
    if missing:
        errors.append(f"manifest is missing fields: {','.join(missing)}")
    if extra:
        errors.append(f"manifest has unexpected fields: {','.join(extra)}")
    if manifest_format not in {
        MANIFEST_FORMAT_V3, MANIFEST_FORMAT_V4, MANIFEST_FORMAT_V5,
    }:
        errors.append(
            "manifest_format must be one of "
            f"{MANIFEST_FORMAT_V3}, {MANIFEST_FORMAT_V4}, {MANIFEST_FORMAT_V5}"
        )
    if manifest.get("product") != PRODUCT:
        errors.append(f"product must be {PRODUCT}")
    if manifest.get("profile") != PROFILE:
        errors.append(f"profile must be {PROFILE}")
    status_value = manifest.get("status")
    if status_value not in {CANDIDATE_STATUS, VERIFIED_STATUS}:
        errors.append(f"invalid status: {status_value!r}")
    if strict and status_value != VERIFIED_STATUS:
        errors.append(f"strict verification requires status={VERIFIED_STATUS}")
    errors.extend(_source_errors(manifest.get("source")))

    gates = manifest.get("gates")
    if not isinstance(gates, dict):
        errors.append("gates must be an object")
    else:
        if set(gates) != set(GATE_NAMES):
            errors.append(f"gates must contain exactly {','.join(GATE_NAMES)}")
        for name, value in gates.items():
            if value not in ALLOWED_GATE_VALUES:
                errors.append(f"invalid gate value {name}={value!r}")
        if strict and gates != VERIFIED_GATES:
            errors.append("strict verification requires the verified G0-G5 gate state")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        errors.append("artifacts must be an array")
        return errors

    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for index, artifact in enumerate(artifacts):
        prefix = f"artifacts[{index}]"
        if not isinstance(artifact, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing_artifact = sorted({"id", "path", "size", "sha256"} - artifact.keys())
        if missing_artifact:
            errors.append(f"{prefix} is missing fields: {','.join(missing_artifact)}")
        artifact_id = artifact.get("id")
        relative = artifact.get("path")
        if not isinstance(artifact_id, str) or not artifact_id:
            errors.append(f"{prefix}.id must be a non-empty string")
        elif artifact_id in seen_ids:
            errors.append(f"duplicate artifact id: {artifact_id}")
        else:
            seen_ids.add(artifact_id)
        if isinstance(relative, str):
            if relative in seen_paths:
                errors.append(f"duplicate artifact path: {relative}")
            seen_paths.add(relative)
        expected_path = artifact_paths.get(artifact_id)
        if expected_path is None:
            errors.append(f"unknown artifact id: {artifact_id!r}")
        elif relative != expected_path:
            errors.append(f"artifact {artifact_id} path must be {expected_path}")
        size = artifact.get("size")
        if type(size) is not int or size < 0:
            errors.append(f"{prefix}.size must be a non-negative integer")
        if not _valid_hex(artifact.get("sha256")):
            errors.append(f"{prefix}.sha256 must be a lowercase SHA-256")
        try:
            artifact_path = _safe_artifact_path(package_dir, relative)
            info = _regular_file(artifact_path, f"artifact {artifact_id}")
            if type(size) is int and info.st_size != size:
                errors.append(
                    f"artifact {artifact_id} size mismatch: manifest={size} actual={info.st_size}"
                )
            expected_sha = artifact.get("sha256")
            if _valid_hex(expected_sha):
                actual_sha = _sha256(artifact_path)
                if actual_sha != expected_sha:
                    errors.append(
                        f"artifact {artifact_id} SHA-256 mismatch: "
                        f"manifest={expected_sha} actual={actual_sha}"
                    )
        except ShipError as exc:
            errors.append(str(exc))

    missing_ids = sorted(set(artifact_paths) - seen_ids)
    if missing_ids:
        errors.append(f"required artifacts are missing: {','.join(missing_ids)}")
    if len(artifacts) != len(artifact_specs):
        errors.append(f"artifacts must contain exactly {len(artifact_specs)} entries")

    expected_entries = {MANIFEST_NAME, *artifact_paths.values()}
    try:
        actual_entries = {entry.name for entry in package_dir.iterdir()}
    except OSError as exc:
        errors.append(f"cannot list package directory: {exc}")
    else:
        unexpected_entries = sorted(actual_entries - expected_entries)
        if unexpected_entries:
            errors.append(f"unexpected package entries: {','.join(unexpected_entries)}")
    errors.extend(_overlay_contract_errors(package_dir, artifacts, manifest.get("overlay")))
    if manifest_format in {MANIFEST_FORMAT_V4, MANIFEST_FORMAT_V5}:
        errors.extend(
            _stdlib_trust_errors(
                package_dir,
                artifacts,
                manifest.get("stdlib_trust"),
                manifest.get("overlay"),
                manifest.get("runtime_overlays"),
            )
        )
        errors.extend(
            _runtime_overlay_contract_errors(
                package_dir,
                artifacts,
                manifest.get("runtime_overlays"),
                manifest.get("preloads"),
                manifest.get("overlay"),
                manifest_format,
            )
        )
        errors.extend(
            _runtime_overlay_slot_errors(
                manifest.get("runtime_overlays"),
                manifest.get("runtime_overlay_slots"),
                manifest_format,
            )
        )
        errors.extend(
            _error_text_errors(
                package_dir,
                manifest.get("error_texts"),
                manifest.get("runtime_overlays"),
                manifest_format,
            )
        )
    return errors


def verify_package(
    package_dir: Path,
    strict: bool = False,
    expected_format: str | None = None,
) -> list[str]:
    try:
        package_dir = _package_dir(package_dir)
        manifest_path = package_dir / MANIFEST_NAME
        _regular_file(manifest_path, "ship manifest")
        manifest = _read_json(manifest_path)
        profile_path = package_dir / ARTIFACT_PATHS["resolved-profile"]
        _regular_file(profile_path, "resolved profile")
        profile_data = profile_path.read_bytes()
        try:
            DialectShipGuard.enforce(
                resolved_profile=profile_data,
                metadata=manifest,
            )
        except DialectShipGuard.DialectShipError as exc:
            raise ShipError(str(exc)) from exc
        errors = _manifest_errors(package_dir, manifest, strict)
        if expected_format is not None and manifest.get("manifest_format") != expected_format:
            errors.append(f"manifest_format must be {expected_format} for this operation")
        return errors
    except ShipError as exc:
        return [str(exc)]


def create_candidate(
    package_dir: Path,
    cwd: Path,
    stage_manifest_path: Path,
    runtime_overlay_manifest_path: Path,
) -> None:
    package_dir = _package_dir(package_dir)
    _regular_file(stage_manifest_path, "guard stage manifest")
    _regular_file(runtime_overlay_manifest_path, "runtime overlay manifest")
    overlay_binding = _read_json(stage_manifest_path)
    runtime_overlay_binding = _read_json(runtime_overlay_manifest_path)
    try:
        RuntimeOverlayBank.validate_manifest(runtime_overlay_binding)
    except (RuntimeOverlayBank.OverlayBankError, TypeError, ValueError) as exc:
        raise ShipError(f"runtime overlay manifest is invalid: {exc}") from exc
    artifacts: list[dict[str, Any]] = []
    for artifact_id, relative in ARTIFACT_SPECS:
        path = package_dir / relative
        info = _regular_file(path, f"artifact {artifact_id}")
        artifacts.append(
            {
                "id": artifact_id,
                "path": relative,
                "size": info.st_size,
                "sha256": _sha256(path),
            }
        )
    records = {record["id"]: record for record in artifacts}
    runtime_image = (
        package_dir / ARTIFACT_PATHS[RUNTIME_OVERLAY_ARTIFACT_ID]
    ).read_bytes()
    preloads = [
        {
            "role": RUNTIME_PRELOAD_ROLE,
            "artifact": RUNTIME_OVERLAY_ARTIFACT_ID,
            "file": ARTIFACT_PATHS[RUNTIME_OVERLAY_ARTIFACT_ID],
            "kind": RuntimeOverlayBank.STORAGE_KIND,
            "address": RuntimeOverlayBank.STORAGE_BASE,
            "address_bits": RuntimeOverlayBank.STORAGE_ADDRESS_BITS,
            "length": records[RUNTIME_OVERLAY_ARTIFACT_ID]["size"],
            "crc16": _crc16_ccitt_false(runtime_image),
            "crc16_algorithm": "crc-16-ccitt-false",
            "sha256": records[RUNTIME_OVERLAY_ARTIFACT_ID]["sha256"],
            "build_id": runtime_overlay_binding["profile_build_id"],
            "persistence": RuntimeOverlayBank.STORAGE_PERSISTENCE,
            "recovery": RUNTIME_PRELOAD_RECOVERY,
        },
        {
            "role": STDLIB_PRELOAD_ROLE,
            "artifact": "workbench-stdlib-blob",
            "file": ARTIFACT_PATHS["workbench-stdlib-blob"],
            "bank": 5,
            "address": 0x050000,
            "size": records["workbench-stdlib-blob"]["size"],
            "sha256": records["workbench-stdlib-blob"]["sha256"],
        },
    ]
    manifest = {
        "manifest_format": MANIFEST_FORMAT,
        "product": PRODUCT,
        "profile": PROFILE,
        "status": CANDIDATE_STATUS,
        "source": capture_source(cwd, require_clean=False),
        "gates": dict(CANDIDATE_GATES),
        "artifacts": artifacts,
        "overlay": overlay_binding,
        "runtime_overlays": runtime_overlay_binding,
        "runtime_overlay_slots": _runtime_overlay_slot_binding(runtime_overlay_binding),
        "preloads": preloads,
        "stdlib_trust": _stdlib_trust_binding(package_dir, artifacts, overlay_binding),
        "error_texts": _error_text_binding(
            package_dir,
            runtime_overlay_binding,
            _error_text_selection(MANIFEST_FORMAT_V5),
            True,
        ),
    }
    manifest_path = package_dir / MANIFEST_NAME
    if manifest_path.exists() or manifest_path.is_symlink():
        _regular_file(manifest_path, "ship manifest")
    _write_json(manifest_path, manifest)
    errors = verify_package(package_dir)
    if errors:
        raise ShipError("generated candidate did not verify: " + "; ".join(errors))


def write_preflight(output: Path, cwd: Path) -> None:
    source = capture_source(cwd, require_clean=True)
    _write_json(
        output,
        {
            "preflight_format": PREFLIGHT_FORMAT,
            "status": "clean",
            "source": source,
        },
    )


def _read_preflight(path: Path) -> dict[str, Any]:
    _regular_file(path, "preflight record")
    preflight = _read_json(path)
    if preflight.get("preflight_format") != PREFLIGHT_FORMAT:
        raise ShipError(f"preflight_format must be {PREFLIGHT_FORMAT}")
    if preflight.get("status") != "clean":
        raise ShipError("preflight status must be clean")
    errors = _source_errors(preflight.get("source"))
    if errors:
        raise ShipError("invalid preflight source: " + "; ".join(errors))
    if preflight["source"]["dirty"]:
        raise ShipError("preflight source must record dirty=false")
    return preflight


def _same_source(expected: dict[str, Any], actual: dict[str, Any], label: str) -> None:
    for key in ("commit", "tree", "dirty", "worktree_sha256"):
        if actual.get(key) != expected.get(key):
            raise ShipError(
                f"{label} source mismatch for {key}: "
                f"expected={expected.get(key)!r} actual={actual.get(key)!r}"
            )


def _rename_exchange(left: Path, right: Path) -> bool:
    try:
        renameat2 = ctypes.CDLL(None, use_errno=True).renameat2
    except AttributeError:
        return False
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    if renameat2(-100, os.fsencode(left), -100, os.fsencode(right), 2) == 0:
        return True
    error = ctypes.get_errno()
    if error in {errno.ENOSYS, errno.EINVAL, errno.ENOTSUP, errno.EXDEV}:
        return False
    raise ShipError(f"atomic output exchange failed: {os.strerror(error)}")


def _replace_output(
    staged: Path,
    output_dir: Path,
    expected_source: dict[str, Any],
    cwd: Path,
) -> None:
    if not output_dir.exists():
        staged.rename(output_dir)
        try:
            _same_source(expected_source, capture_source(cwd, require_clean=True), "final")
        except BaseException:
            shutil.rmtree(output_dir, ignore_errors=True)
            raise
        return

    _package_dir(output_dir)
    if _rename_exchange(staged, output_dir):
        try:
            final_source = capture_source(cwd, require_clean=True, exclude_paths=(staged,))
            _same_source(expected_source, final_source, "final")
        except BaseException:
            _rename_exchange(staged, output_dir)
            shutil.rmtree(staged, ignore_errors=True)
            raise
        shutil.rmtree(staged)
        return

    backup = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.old.", dir=output_dir.parent))
    backup.rmdir()
    output_dir.rename(backup)
    try:
        staged.rename(output_dir)
        final_source = capture_source(cwd, require_clean=True, exclude_paths=(backup,))
        _same_source(expected_source, final_source, "final")
    except BaseException:
        shutil.rmtree(output_dir, ignore_errors=True)
        backup.rename(output_dir)
        raise
    shutil.rmtree(backup)


def finalize_candidate(
    preflight_path: Path,
    candidate_dir: Path,
    output_dir: Path,
    cwd: Path,
) -> None:
    preflight = _read_preflight(preflight_path)
    expected_source = preflight["source"]
    current_source = capture_source(cwd, require_clean=True)
    _same_source(expected_source, current_source, "current")

    candidate_dir = _package_dir(candidate_dir)
    candidate_errors = verify_package(candidate_dir)
    if candidate_errors:
        raise ShipError("candidate verification failed: " + "; ".join(candidate_errors))
    candidate_manifest = _read_json(candidate_dir / MANIFEST_NAME)
    if candidate_manifest.get("manifest_format") != MANIFEST_FORMAT_V5:
        raise ShipError(f"candidate producer requires {MANIFEST_FORMAT_V5}")
    if candidate_manifest.get("status") != CANDIDATE_STATUS:
        raise ShipError(f"candidate status must be {CANDIDATE_STATUS}")
    _same_source(expected_source, candidate_manifest["source"], "candidate")

    if output_dir.is_symlink():
        raise ShipError(f"output directory must not be a symlink: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.new.", dir=output_dir.parent))
    try:
        for _artifact_id, relative in ARTIFACT_SPECS:
            shutil.copyfile(candidate_dir / relative, staged / relative)
        final_manifest = dict(candidate_manifest)
        final_manifest["status"] = VERIFIED_STATUS
        final_manifest["source"] = dict(expected_source)
        final_manifest["gates"] = dict(VERIFIED_GATES)
        _write_json(staged / MANIFEST_NAME, final_manifest)
        final_errors = verify_package(staged, strict=True)
        if final_errors:
            raise ShipError("final package verification failed: " + "; ".join(final_errors))
        staged_source = capture_source(cwd, require_clean=True, exclude_paths=(staged,))
        _same_source(expected_source, staged_source, "staged")
        _replace_output(staged, output_dir, expected_source, cwd)
    except BaseException:
        shutil.rmtree(staged, ignore_errors=True)
        raise


def _write_test_artifacts(
    package_dir: Path,
    stage_manifest_path: Path,
    runtime_overlay_manifest_path: Path,
) -> None:
    package_dir.mkdir(parents=True)
    for index, (_artifact_id, relative) in enumerate(ARTIFACT_SPECS, start=1):
        (package_dir / relative).write_bytes((f"artifact-{index}\n").encode("ascii") * index)

    stdlib_code = b"\x65\x00\x00\x00\x00\x00\x00\x00"
    literal_index = struct.pack("<H", 0)
    literal_node = struct.pack("<BBHHHH", 1, 0, 7, 0, 0, 0)
    literal_patch = struct.pack("<HH", 2, 0)
    metadata_bytes = (
        WorkbenchOverlayStage.L65M_HEADER_SIZE
        + len(literal_index) + len(literal_node) + len(literal_patch)
    )
    stdlib_metadata = struct.pack(
        WorkbenchOverlayStage.L65M_HEADER_FORMAT,
        b"L65M", 1, WorkbenchOverlayStage.L65M_HEADER_SIZE, 0, 0x050000,
        len(stdlib_code), metadata_bytes,
        0, 1, 1, 1,
        WorkbenchOverlayStage.L65M_HEADER_SIZE,
        WorkbenchOverlayStage.L65M_HEADER_SIZE,
        WorkbenchOverlayStage.L65M_HEADER_SIZE + len(literal_index),
        WorkbenchOverlayStage.L65M_HEADER_SIZE + len(literal_index) + len(literal_node),
        metadata_bytes, 0, 0,
    ) + literal_index + literal_node + literal_patch
    stdlib_prefix = stdlib_code + stdlib_metadata
    stdlib_manifest_path = package_dir / ARTIFACT_PATHS["stdlib-artifact-manifest"]
    _write_json(
        stdlib_manifest_path,
        {
            "format": "lisp65-bytecode-p0-stdlib-artifacts-v1",
            "artifact_role": "stdlib",
            "suite": STDLIB_SUITE,
            "base_addr": "0x050000",
            "cases": ["selftest-stdlib-case"],
            "functions": ["selftest-stdlib-function"],
            "objects": 1,
            "external_image": {
                "format": "lisp65-bytecode-p0-ext-image-v1",
                "bytes": len(stdlib_prefix),
                "code_bytes": len(stdlib_code),
                "metadata_bytes": len(stdlib_metadata),
                "metadata_offset": len(stdlib_code),
                "file_header_bytes": 0,
                "file_header_format": "none",
                "sha256": _sha256_bytes(stdlib_prefix),
            },
        },
    )
    contract_path = package_dir / ARTIFACT_PATHS["resolved-profile"]
    contract_path.write_text(
        "\n".join(
            (
                "format=lisp65-resolved-profile-v1",
                f"profile={PROFILE}",
                "overlay_extra_defines=-DLISP65_STACK_GUARD",
                f"overlay_entry={OVERLAY_ENTRY}",
                "overlay_descriptor=L65O-v1-18-byte-crc16-ccitt-false",
                *V5_RUNTIME_PROFILE_LINES,
                f"external_image_sha256={_sha256_bytes(stdlib_prefix)}",
                f"bytecode_manifest_sha256={_sha256(stdlib_manifest_path)}",
            )
        )
        + "\n",
        encoding="ascii",
    )
    contract_sha = _sha256(contract_path)
    build_id = int(contract_sha[:8], 16)

    prg_path = package_dir / ARTIFACT_PATHS["workbench-prg"]
    load_base = 0x2001
    prg_path.write_bytes(struct.pack("<H", load_base) + bytes(range(1, 97)))
    resident_end = load_base + prg_path.stat().st_size - 2

    stdlib_base = 0x50000
    stdlib_end = stdlib_base + len(stdlib_prefix)
    stage_address = (stdlib_end + STAGE_ALIGNMENT - 1) & ~(STAGE_ALIGNMENT - 1)
    padding = stage_address - stdlib_end
    overlay_payload = bytes(range(1, 65))
    overlay_base = 0xB000
    overlay_entry = overlay_base + 8
    overlay_crc = _crc16_ccitt_false(overlay_payload)
    descriptor = struct.pack(
        "<4sBBIHHHH",
        DESCRIPTOR_MAGIC,
        DESCRIPTOR_VERSION,
        DESCRIPTOR_SIZE,
        build_id,
        overlay_base,
        overlay_entry,
        len(overlay_payload),
        overlay_crc,
    )
    stage_data = descriptor + overlay_payload
    combined = stdlib_prefix + bytes(padding) + stage_data
    blob_path = package_dir / ARTIFACT_PATHS["workbench-stdlib-blob"]
    blob_path.write_bytes(combined)
    stage_manifest = {
        "schema": OVERLAY_SCHEMA,
        "profile": PROFILE,
        "build_id": build_id,
        "abi": {
            "contract": ARTIFACT_PATHS["resolved-profile"],
            "contract_id": OVERLAY_ABI_ID,
            "contract_sha256": contract_sha,
        },
        "descriptor": {
            "magic": DESCRIPTOR_MAGIC.decode("ascii"),
            "version": DESCRIPTOR_VERSION,
            "header_size": DESCRIPTOR_SIZE,
            "crc16": overlay_crc,
            "crc16_algorithm": "crc-16-ccitt-false",
        },
        "overlay": {
            "base": overlay_base,
            "end": overlay_base + len(overlay_payload),
            "entry": overlay_entry,
            "entry_symbol": OVERLAY_ENTRY,
            "file": "lisp65-workbench-overlay.bin",
            "sha256": _sha256_bytes(overlay_payload),
            "size": len(overlay_payload),
        },
        "resident": {
            "file": "lisp65-workbench-resident.prg",
            "load_base": load_base,
            "file_end": resident_end,
            "sha256": _sha256(prg_path),
            "size": prg_path.stat().st_size,
        },
        "stage": {
            "address": stage_address,
            "bank": stage_address // BANK_SIZE,
            "end_offset": stage_address % BANK_SIZE + len(stage_data),
            "file": "overlay-stage.bin",
            "limit_offset": 0xC9E0,
            "offset": stage_address % BANK_SIZE,
            "padding_after_stdlib": padding,
            "sha256": _sha256_bytes(stage_data),
            "size": len(stage_data),
        },
        "preload": {
            "base": stdlib_base,
            "end": stdlib_base + len(combined),
            "file": "stdlib-with-overlay.ext.bin",
            "sha256": _sha256(blob_path),
            "size": len(combined),
        },
        "stdlib": {
            "base": stdlib_base,
            "end": stdlib_end,
            "file": "stdlib-p0.ext.bin",
            "manifest": "stdlib-p0.manifest.json",
            "manifest_sha256": _sha256(stdlib_manifest_path),
            "sha256": _sha256_bytes(stdlib_prefix),
            "size": len(stdlib_prefix),
        },
    }
    _write_json(stage_manifest_path, stage_manifest)

    runtime_vma = 0xC200
    runtime_slices: list[RuntimeOverlayBank.ExtractedSlice] = []
    error_table = ErrorTextTable.prepare_table(
        ERROR_TEXT_SPEC_PATH, ERROR_TEXT_PROFILE, build_id
    )
    for slice_id, canonical in enumerate(RUNTIME_OVERLAY_CANONICAL_SLICES):
        runtime_payload = f"{canonical[0]}-selftest".encode("ascii") + bytes((slice_id,))
        if slice_id == ERROR_TEXT_SLOT:
            runtime_payload += error_table.data
        runtime_spec = RuntimeOverlayBank.SliceSpec(
            slice_id,
            canonical[0],
            canonical[1],
            canonical[2],
            canonical[3],
            canonical[4],
            canonical[5],
            RuntimeOverlayBank.ENTRY_ABI,
            0,
        )
        runtime_slices.append(
            RuntimeOverlayBank.ExtractedSlice(
                runtime_spec,
                runtime_vma,
                runtime_vma + len(runtime_payload),
                runtime_vma,
                runtime_payload,
            )
        )
    runtime_image, runtime_parsed = RuntimeOverlayBank.build_image(
        runtime_slices,
        profile_build_id=build_id,
        expected_vma=runtime_vma,
        max_slice_bytes=RuntimeOverlayBank.MAX_SLICE_BYTES,
    )
    runtime_image_path = package_dir / ARTIFACT_PATHS[RUNTIME_OVERLAY_ARTIFACT_ID]
    runtime_image_path.write_bytes(runtime_image)
    runtime_header_path = runtime_overlay_manifest_path.with_name(RUNTIME_OVERLAY_HEADER)
    runtime_header = RuntimeOverlayBank.render_header(
        profile_build_id=build_id,
        verifier_slices=runtime_parsed.slices,
    )
    runtime_header_path.write_bytes(runtime_header)
    runtime_elf_path = runtime_overlay_manifest_path.with_name("runtime-overlay-selftest.elf")
    runtime_elf_path.write_bytes(b"ELF selftest provenance\n")
    runtime_manifest = RuntimeOverlayBank._manifest(
        profile=PROFILE,
        abi_contract=contract_path,
        abi_sha256=contract_sha,
        elf=runtime_elf_path,
        image_path=runtime_image_path,
        header_path=runtime_header_path,
        image=runtime_image,
        header=runtime_header,
        parsed=runtime_parsed,
        slices=runtime_slices,
        expected_vma=runtime_vma,
        max_slice_bytes=RuntimeOverlayBank.MAX_SLICE_BYTES,
    )
    RuntimeOverlayBank.validate_manifest(runtime_manifest)
    _write_json(runtime_overlay_manifest_path, runtime_manifest)


def _git_for_test(repo: Path, *args: str) -> None:
    _run_git(list(args), repo)


def _expect_failure(failures: list[str], name: str, action: Any) -> None:
    try:
        action()
    except ShipError:
        return
    failures.append(f"{name}: expected failure")


def _expect_verify(
    failures: list[str], name: str, package_dir: Path, should_pass: bool, strict: bool = False
) -> None:
    errors = verify_package(package_dir, strict=strict)
    passed = not errors
    if passed != should_pass:
        failures.append(
            f"{name}: expected pass={should_pass}, got pass={passed}: {'; '.join(errors)}"
        )


def _mutated_package(base: Path, root: Path, name: str) -> tuple[Path, dict[str, Any]]:
    target = root / name
    shutil.copytree(base, target)
    manifest = _read_json(target / MANIFEST_NAME)
    return target, manifest


def selftest() -> None:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="lisp65-workbench-ship-") as temporary_name:
        root = Path(temporary_name)
        repo = root / "repo"
        repo.mkdir()
        _git_for_test(repo, "init", "-q")
        _git_for_test(repo, "config", "user.name", "lisp65 selftest")
        _git_for_test(repo, "config", "user.email", "selftest@example.invalid")
        (repo / ".gitignore").write_text(
            "/candidate/\n/final/\n/preflight.json\n/ignored.tmp\n",
            encoding="ascii",
        )
        tracked = repo / "tracked.txt"
        tracked.write_text("clean\n", encoding="ascii")
        _git_for_test(repo, "add", ".gitignore", "tracked.txt")
        _git_for_test(repo, "commit", "-q", "-m", "selftest fixture")

        candidate = repo / "candidate"
        stage_manifest = root / "guard-stage-manifest.json"
        runtime_overlay_manifest = root / "runtime-overlay-manifest.json"
        _write_test_artifacts(candidate, stage_manifest, runtime_overlay_manifest)
        create_candidate(candidate, repo, stage_manifest, runtime_overlay_manifest)
        _expect_verify(failures, "valid-candidate", candidate, True)
        _expect_verify(failures, "unverified-strict", candidate, False, strict=True)
        candidate_manifest = _read_json(candidate / MANIFEST_NAME)
        if candidate_manifest.get("manifest_format") != MANIFEST_FORMAT_V5:
            failures.append("candidate-format: producer did not emit Ship-v5")
        if candidate_manifest.get("runtime_overlay_slots", {}).get("used") != (
            RUNTIME_OVERLAY_SLICE_COUNT
        ):
            failures.append("runtime-slot-budget: canonical product allocation differs")
        expected_error_table = ErrorTextTable.prepare_table(
            ERROR_TEXT_SPEC_PATH,
            ERROR_TEXT_PROFILE,
            candidate_manifest["runtime_overlays"]["profile_build_id"],
        )
        error_binding = candidate_manifest.get("error_texts", {})
        if (
            error_binding.get("active_codes") != list(ERROR_TEXT_ACTIVE_CODES)
            or error_binding.get("omitted_codes") != list(ERROR_TEXT_OMITTED_CODES)
            or error_binding.get("resident_codes") != list(ERROR_TEXT_RESIDENT_CODES)
            or error_binding.get("size") != len(expected_error_table.data)
        ):
            failures.append("error-text-binding: sparse Workbench contract differs")
        if len(list(candidate.iterdir())) != 10:
            failures.append("candidate-file-count: Ship-v5 must contain exactly ten files")

        for label, marker in (
            ("dialect-v2-abi-profile", "abi_profile=dialect-v2\n"),
            ("dialect-v2-profile-id", "profile_id=v2-capability-candidate\n"),
        ):
            target, _manifest = _mutated_package(candidate, root, label)
            profile_path = target / ARTIFACT_PATHS["resolved-profile"]
            profile_path.write_text(
                profile_path.read_text(encoding="ascii") + marker,
                encoding="ascii",
            )
            errors = verify_package(target)
            if not any(
                "internal dialect-v2 staging profile is not shippable" in error
                and "no passed-G5" in error
                for error in errors
            ):
                failures.append(f"{label}: normal Ship verification did not fail closed")

        for required_line in V5_RUNTIME_PROFILE_LINES:
            key = required_line.split("=", 1)[0]
            altered = (
                (candidate / ARTIFACT_PATHS["resolved-profile"])
                .read_text(encoding="ascii")
                .replace(required_line, key + "=selftest-invalid", 1)
                .encode("ascii")
            )
            if not _v5_runtime_profile_errors(altered):
                failures.append(f"runtime-profile-{key}: altered v5 binding was accepted")

        def refresh_artifact(
            target: Path, manifest: dict[str, Any], artifact_id: str
        ) -> Path:
            record = next(
                artifact for artifact in manifest["artifacts"] if artifact["id"] == artifact_id
            )
            path = target / record["path"]
            record["size"] = path.stat().st_size
            record["sha256"] = _sha256(path)
            return path

        def replace_error_table(
            target: Path,
            manifest: dict[str, Any],
            table: bytes,
            expected_selection: (
                tuple[
                    int,
                    tuple[int, ...],
                    tuple[int, ...],
                    tuple[int, ...],
                ] | None
            ),
            slice_count: int | None = None,
        ) -> None:
            runtime = manifest["runtime_overlays"]
            image_path = target / ARTIFACT_PATHS[RUNTIME_OVERLAY_ARTIFACT_ID]
            image = image_path.read_bytes()
            slice_limit = (
                V4_RUNTIME_MAX_SLICE_BYTES
                if manifest["manifest_format"] == MANIFEST_FORMAT_V4
                else runtime["policy"]["max_slice_bytes"]
            )
            parsed = RuntimeOverlayBank.validate_image(
                image,
                expected_build_id=runtime["profile_build_id"],
                expected_vma=runtime["policy"]["common_vma"],
                max_slice_bytes=slice_limit,
                max_vma=(
                    0xFFFF
                    if manifest["manifest_format"] == MANIFEST_FORMAT_V4
                    else RuntimeOverlayBank.MAX_VMA
                ),
            )
            rebuilt_slices: list[RuntimeOverlayBank.ExtractedSlice] = []
            rebuilt_payloads: list[bytes] = []
            selected_entries = (
                parsed.slices if slice_count is None else parsed.slices[:slice_count]
            )
            for entry, canonical in zip(
                selected_entries, RUNTIME_OVERLAY_CANONICAL_SLICES
            ):
                payload = image[entry.file_offset:entry.file_offset + entry.file_size]
                if entry.id == ERROR_TEXT_SLOT:
                    located = ErrorTextTable.find_table(
                        payload,
                        expected_build_id=runtime["profile_build_id"],
                        expected_profile_id=ERROR_TEXT_PROFILE_ID,
                    )
                    start = located["offset"]
                    payload = payload[:start] + table + payload[start + located["size"]:]
                spec = RuntimeOverlayBank.SliceSpec(
                    entry.id,
                    canonical[0],
                    canonical[1],
                    canonical[2],
                    canonical[3],
                    canonical[4],
                    canonical[5],
                    V4_RUNTIME_ENTRY_ABI,
                    entry.capability_mask,
                )
                rebuilt_payloads.append(payload)
                rebuilt_slices.append(RuntimeOverlayBank.ExtractedSlice(
                    spec,
                    entry.vma,
                    entry.vma + len(payload),
                    entry.vma + entry.entry_offset,
                    payload,
                ))
            rebuilt, rebuilt_parsed = RuntimeOverlayBank.build_image(
                rebuilt_slices,
                profile_build_id=runtime["profile_build_id"],
                expected_vma=runtime["policy"]["common_vma"],
                max_slice_bytes=slice_limit,
                max_vma=(
                    0xFFFF
                    if manifest["manifest_format"] == MANIFEST_FORMAT_V4
                    else RuntimeOverlayBank.MAX_VMA
                ),
            )
            image_path.write_bytes(rebuilt)
            artifact_path = refresh_artifact(
                target, manifest, RUNTIME_OVERLAY_ARTIFACT_ID
            )
            storage = runtime["storage"]
            storage["size"] = artifact_path.stat().st_size
            storage["sha256"] = _sha256(artifact_path)
            if "crc16" in storage:
                storage["crc16"] = _crc16_ccitt_false(rebuilt)
            runtime["catalog"]["payload_offset"] = rebuilt_parsed.payload_offset
            runtime["catalog"]["slice_count"] = len(rebuilt_parsed.slices)
            runtime["catalog"]["directory_crc16"] = rebuilt_parsed.directory_crc16
            runtime["catalog"]["header_crc16"] = rebuilt_parsed.header_crc16
            runtime["slices"] = runtime["slices"][:len(rebuilt_parsed.slices)]
            for record, entry, payload in zip(
                runtime["slices"], rebuilt_parsed.slices, rebuilt_payloads
            ):
                record.update({
                    "file_offset": entry.file_offset,
                    "file_size": entry.file_size,
                    "memory_size": entry.memory_size,
                    "vma": entry.vma,
                    "end": entry.vma + entry.memory_size,
                    "entry": entry.vma + entry.entry_offset,
                    "entry_offset": entry.entry_offset,
                    "slice_build_id": entry.slice_build_id,
                    "crc16": entry.crc16,
                    "sha256": _sha256_bytes(payload),
                })
            if manifest["manifest_format"] == MANIFEST_FORMAT_V4:
                header = _legacy_runtime_overlay_header(
                    runtime["profile_build_id"], rebuilt_parsed.slices
                )
            else:
                header = RuntimeOverlayBank.render_header(
                    profile_build_id=runtime["profile_build_id"],
                    verifier_slices=rebuilt_parsed.slices,
                )
            runtime["config_header"]["sha256"] = _sha256_bytes(header)
            preload = manifest["preloads"][0]
            if "length" in preload:
                preload["length"] = artifact_path.stat().st_size
                preload["crc16"] = _crc16_ccitt_false(rebuilt)
            else:
                preload["size"] = artifact_path.stat().st_size
            preload["sha256"] = _sha256(artifact_path)
            manifest["error_texts"] = _error_text_binding(
                target,
                runtime,
                expected_selection,
                manifest["manifest_format"] == MANIFEST_FORMAT_V5,
            )

        legacy_v4 = root / "legacy-v4"
        shutil.copytree(candidate, legacy_v4)
        legacy_v4_manifest = _read_json(legacy_v4 / MANIFEST_NAME)
        legacy_v4_manifest["manifest_format"] = MANIFEST_FORMAT_V4
        legacy_v4_manifest["status"] = VERIFIED_STATUS
        legacy_v4_manifest["gates"] = dict(VERIFIED_GATES)
        error_spec = ErrorTextTable.load_spec(ERROR_TEXT_SPEC_PATH)
        legacy_entries = tuple(
            replace(entry, profiles=tuple(sorted(entry.profiles + (ERROR_TEXT_PROFILE,))))
            if entry.code == 11 and ERROR_TEXT_PROFILE not in entry.profiles
            else entry
            for entry in error_spec.entries[:V4_ERROR_TEXT_CODE_COUNT]
        )
        legacy_table = ErrorTextTable.build_table(
            legacy_entries,
            error_spec.profile(ERROR_TEXT_PROFILE),
            legacy_v4_manifest["runtime_overlays"]["profile_build_id"],
        )
        if legacy_table.active_codes != V4_ERROR_TEXT_ACTIVE_CODES:
            failures.append("legacy-v4-fixture: historical active-code selection drifted")
        replace_error_table(
            legacy_v4,
            legacy_v4_manifest,
            legacy_table.data,
            _error_text_selection(MANIFEST_FORMAT_V4),
            slice_count=V4_RUNTIME_PRODUCT_SLOT_LIMIT,
        )
        legacy_runtime = legacy_v4_manifest["runtime_overlays"]
        legacy_storage = legacy_runtime["storage"]
        legacy_runtime["schema"] = V4_RUNTIME_FORMAT
        legacy_runtime["policy"].update({
            "max_slices": V4_RUNTIME_MAX_SLICES,
            "max_slice_bytes": V4_RUNTIME_MAX_SLICE_BYTES,
            "max_boot_slice_bytes": V4_RUNTIME_MAX_BOOT_SLICE_BYTES,
            "payload_alignment": V4_RUNTIME_PAYLOAD_ALIGNMENT,
            "entry_abi": V4_RUNTIME_ENTRY_ABI,
        })
        legacy_runtime["storage"] = {
            "format": V4_RUNTIME_FORMAT,
            "file": legacy_storage["file"],
            "bank": V4_RUNTIME_BANK,
            "base": V4_RUNTIME_BANK * V4_RUNTIME_BANK_SIZE,
            "limit": (V4_RUNTIME_BANK + 1) * V4_RUNTIME_BANK_SIZE,
            "size": legacy_storage["size"],
            "sha256": legacy_storage["sha256"],
        }
        legacy_runtime["catalog"].pop("format_bank_tag")
        legacy_image = (legacy_v4 / RUNTIME_OVERLAY_ARTIFACT).read_bytes()
        legacy_parsed = RuntimeOverlayBank.validate_image(
            legacy_image,
            expected_build_id=legacy_runtime["profile_build_id"],
            expected_vma=legacy_runtime["policy"]["common_vma"],
            max_slice_bytes=legacy_runtime["policy"]["max_slice_bytes"],
            max_vma=0xFFFF,
        )
        legacy_runtime["config_header"]["sha256"] = _sha256_bytes(
            _legacy_runtime_overlay_header(
                legacy_runtime["profile_build_id"], legacy_parsed.slices
            )
        )
        legacy_runtime_record = next(
            record for record in legacy_v4_manifest["artifacts"]
            if record["id"] == RUNTIME_OVERLAY_ARTIFACT_ID
        )
        legacy_v4_manifest["preloads"][0] = {
            "role": RUNTIME_PRELOAD_ROLE,
            "artifact": RUNTIME_OVERLAY_ARTIFACT_ID,
            "file": RUNTIME_OVERLAY_ARTIFACT,
            "bank": V4_RUNTIME_BANK,
            "address": V4_RUNTIME_BANK * V4_RUNTIME_BANK_SIZE,
            "size": legacy_runtime_record["size"],
            "sha256": legacy_runtime_record["sha256"],
        }
        legacy_v4_manifest["runtime_overlay_slots"] = _runtime_overlay_slot_binding(
            legacy_runtime, V4_RUNTIME_PRODUCT_SLOT_LIMIT
        )
        _write_json(legacy_v4 / MANIFEST_NAME, legacy_v4_manifest)
        _expect_verify(failures, "legacy-v4-strict", legacy_v4, True, strict=True)
        if not verify_package(
            legacy_v4,
            strict=True,
            expected_format=MANIFEST_FORMAT_V5,
        ):
            failures.append("legacy-v4-current-format: Ship-v4 accepted as current Ship-v5")
        if len(list(legacy_v4.iterdir())) != 10:
            failures.append("legacy-v4-file-count: Ship-v4 must contain exactly ten files")

        legacy_v4_mutated = root / "legacy-v4-mutated-selection"
        shutil.copytree(legacy_v4, legacy_v4_mutated)
        legacy_v4_mutated_manifest = _read_json(legacy_v4_mutated / MANIFEST_NAME)
        mutated_entries = tuple(
            replace(
                entry,
                profiles=tuple(
                    profile for profile in entry.profiles
                    if profile != ERROR_TEXT_PROFILE
                ),
            )
            if entry.code == V4_ERROR_TEXT_ACTIVE_CODES[0]
            else entry
            for entry in legacy_entries
        )
        mutated_table = ErrorTextTable.build_table(
            mutated_entries,
            error_spec.profile(ERROR_TEXT_PROFILE),
            legacy_v4_mutated_manifest["runtime_overlays"]["profile_build_id"],
        )
        replace_error_table(
            legacy_v4_mutated,
            legacy_v4_mutated_manifest,
            mutated_table.data,
            None,
        )
        _write_json(legacy_v4_mutated / MANIFEST_NAME, legacy_v4_mutated_manifest)
        mutated_errors = verify_package(legacy_v4_mutated, strict=True)
        if not mutated_errors:
            failures.append("legacy-v4-mutated-selection: semantic mutation was accepted")
        elif not any("active-code selection" in error for error in mutated_errors):
            failures.append(
                "legacy-v4-mutated-selection: rejected for the wrong reason: "
                + "; ".join(mutated_errors)
            )

        legacy_v3 = root / "legacy-v3"
        shutil.copytree(legacy_v4, legacy_v3)
        legacy_manifest = _read_json(legacy_v3 / MANIFEST_NAME)
        legacy_manifest["manifest_format"] = MANIFEST_FORMAT_V3
        legacy_manifest["status"] = VERIFIED_STATUS
        legacy_manifest["gates"] = dict(VERIFIED_GATES)
        legacy_manifest.pop("runtime_overlays")
        legacy_manifest.pop("runtime_overlay_slots")
        legacy_manifest.pop("preloads")
        legacy_manifest.pop("stdlib_trust")
        legacy_manifest.pop("error_texts")
        legacy_manifest["artifacts"] = [
            record
            for record in legacy_manifest["artifacts"]
            if record["id"] != RUNTIME_OVERLAY_ARTIFACT_ID
        ]
        (legacy_v3 / RUNTIME_OVERLAY_ARTIFACT).unlink()
        _write_json(legacy_v3 / MANIFEST_NAME, legacy_manifest)
        _expect_verify(failures, "legacy-v3-strict", legacy_v3, True, strict=True)
        if not verify_package(
            legacy_v3,
            strict=True,
            expected_format=MANIFEST_FORMAT_V5,
        ):
            failures.append("legacy-v3-current-format: Ship-v3 accepted as current Ship-v5")
        if len(list(legacy_v3.iterdir())) != 9:
            failures.append("legacy-v3-file-count: Ship-v3 must contain exactly nine files")

        preflight = repo / "preflight.json"
        try:
            write_preflight(preflight, repo)
            finalize_candidate(preflight, candidate, repo / "final", repo)
        except ShipError as exc:
            failures.append(f"valid-finalize: {exc}")
        _expect_verify(failures, "valid-final-strict", repo / "final", True, strict=True)
        final_prg = repo / "final" / ARTIFACT_SPECS[0][1]
        final_prg.write_bytes(b"stale package\n")
        try:
            finalize_candidate(preflight, candidate, repo / "final", repo)
        except ShipError as exc:
            failures.append(f"replace-stale-final: {exc}")
        _expect_verify(failures, "replaced-final-strict", repo / "final", True, strict=True)

        tracked.write_text("changed after preflight\n", encoding="ascii")
        _expect_failure(
            failures,
            "source-change-after-preflight",
            lambda: finalize_candidate(preflight, candidate, repo / "final", repo),
        )
        _git_for_test(repo, "reset", "--hard", "-q", "HEAD")

        cases_root = root / "cases"
        cases_root.mkdir()

        def remove_table_from_valid_runtime_image(
            target: Path, manifest: dict[str, Any]
        ) -> None:
            runtime = manifest["runtime_overlays"]
            image_path = target / ARTIFACT_PATHS[RUNTIME_OVERLAY_ARTIFACT_ID]
            image = image_path.read_bytes()
            parsed = RuntimeOverlayBank.validate_image(
                image,
                expected_build_id=runtime["profile_build_id"],
                expected_vma=runtime["policy"]["common_vma"],
                max_slice_bytes=runtime["policy"]["max_slice_bytes"],
            )
            rebuilt_slices: list[RuntimeOverlayBank.ExtractedSlice] = []
            rebuilt_payloads: list[bytes] = []
            for entry, canonical in zip(parsed.slices, RUNTIME_OVERLAY_CANONICAL_SLICES):
                payload = bytearray(
                    image[entry.file_offset:entry.file_offset + entry.file_size]
                )
                if entry.id == ERROR_TEXT_SLOT:
                    table_offset = manifest["error_texts"]["offset"]
                    if payload[table_offset:table_offset + 4] != ErrorTextTable.MAGIC:
                        raise ShipError("selftest fixture has no L65E table at its bound offset")
                    payload[table_offset] ^= 0x01
                spec = RuntimeOverlayBank.SliceSpec(
                    entry.id,
                    canonical[0],
                    canonical[1],
                    canonical[2],
                    canonical[3],
                    canonical[4],
                    canonical[5],
                    RuntimeOverlayBank.ENTRY_ABI,
                    entry.capability_mask,
                )
                data = bytes(payload)
                rebuilt_payloads.append(data)
                rebuilt_slices.append(RuntimeOverlayBank.ExtractedSlice(
                    spec,
                    entry.vma,
                    entry.vma + len(data),
                    entry.vma + entry.entry_offset,
                    data,
                ))
            rebuilt, rebuilt_parsed = RuntimeOverlayBank.build_image(
                rebuilt_slices,
                profile_build_id=runtime["profile_build_id"],
                expected_vma=runtime["policy"]["common_vma"],
                max_slice_bytes=runtime["policy"]["max_slice_bytes"],
            )
            image_path.write_bytes(rebuilt)
            artifact_path = refresh_artifact(
                target, manifest, RUNTIME_OVERLAY_ARTIFACT_ID
            )
            runtime["storage"]["size"] = artifact_path.stat().st_size
            runtime["storage"]["sha256"] = _sha256(artifact_path)
            runtime["storage"]["crc16"] = _crc16_ccitt_false(rebuilt)
            runtime["catalog"]["payload_offset"] = rebuilt_parsed.payload_offset
            runtime["catalog"]["directory_crc16"] = rebuilt_parsed.directory_crc16
            runtime["catalog"]["header_crc16"] = rebuilt_parsed.header_crc16
            for record, entry, payload in zip(
                runtime["slices"], rebuilt_parsed.slices, rebuilt_payloads
            ):
                record.update({
                    "file_offset": entry.file_offset,
                    "file_size": entry.file_size,
                    "memory_size": entry.memory_size,
                    "vma": entry.vma,
                    "end": entry.vma + entry.memory_size,
                    "entry": entry.vma + entry.entry_offset,
                    "entry_offset": entry.entry_offset,
                    "slice_build_id": entry.slice_build_id,
                    "crc16": entry.crc16,
                    "sha256": _sha256_bytes(payload),
                })
            manifest["preloads"][0]["length"] = artifact_path.stat().st_size
            manifest["preloads"][0]["crc16"] = _crc16_ccitt_false(rebuilt)
            manifest["preloads"][0]["sha256"] = _sha256(artifact_path)

        duplicate_json = cases_root / "duplicate-key.json"
        duplicate_json.write_text('{"status": "clean", "status": "dirty"}\n', encoding="ascii")
        _expect_failure(
            failures,
            "duplicate-json-key",
            lambda: _read_json(duplicate_json),
        )

        target, manifest = _mutated_package(candidate, cases_root, "byte-mutation")
        artifact_path = target / manifest["artifacts"][0]["path"]
        content = bytearray(artifact_path.read_bytes())
        content[0] ^= 0x01
        artifact_path.write_bytes(content)
        _expect_verify(failures, "byte-mutation", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "truncate")
        artifact_path = target / manifest["artifacts"][0]["path"]
        artifact_path.write_bytes(artifact_path.read_bytes()[:-1])
        _expect_verify(failures, "truncate", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "delete")
        (target / manifest["artifacts"][0]["path"]).unlink()
        _expect_verify(failures, "delete", target, False)

        target, _manifest = _mutated_package(candidate, cases_root, "extra-file")
        (target / "unexpected.bin").write_bytes(b"not declared\n")
        _expect_verify(failures, "extra-file", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "wrong-size")
        manifest["artifacts"][0]["size"] += 1
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "wrong-size", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "wrong-hash")
        manifest["artifacts"][0]["sha256"] = "0" * SHA256_HEX_LENGTH
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "wrong-hash", target, False)

        target, _manifest = _mutated_package(candidate, cases_root, "stdlib-blob-mismatch")
        stdlib_manifest_path = target / ARTIFACT_PATHS["stdlib-artifact-manifest"]
        stdlib_manifest = _read_json(stdlib_manifest_path)
        stdlib_manifest["external_image"]["sha256"] = "0" * SHA256_HEX_LENGTH
        _write_json(stdlib_manifest_path, stdlib_manifest)
        package_manifest = _read_json(target / MANIFEST_NAME)
        stdlib_record = next(
            artifact
            for artifact in package_manifest["artifacts"]
            if artifact["id"] == "stdlib-artifact-manifest"
        )
        stdlib_record["size"] = stdlib_manifest_path.stat().st_size
        stdlib_record["sha256"] = _sha256(stdlib_manifest_path)
        _write_json(target / MANIFEST_NAME, package_manifest)
        _expect_verify(failures, "stdlib-blob-mismatch", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "legacy-v2")
        manifest["manifest_format"] = "lisp65-workbench-ship-v2"
        del manifest["overlay"]
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "legacy-v2", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "descriptor-magic")
        binding = manifest["overlay"]
        blob_path = target / ARTIFACT_PATHS["workbench-stdlib-blob"]
        blob = bytearray(blob_path.read_bytes())
        stage_relative = binding["stage"]["address"] - binding["preload"]["base"]
        blob[stage_relative] ^= 0x01
        blob_path.write_bytes(blob)
        refresh_artifact(target, manifest, "workbench-stdlib-blob")
        binding["preload"]["sha256"] = _sha256(blob_path)
        binding["stage"]["sha256"] = _sha256_bytes(bytes(blob[stage_relative:]))
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "descriptor-magic", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "payload-crc")
        binding = manifest["overlay"]
        blob_path = target / ARTIFACT_PATHS["workbench-stdlib-blob"]
        blob = bytearray(blob_path.read_bytes())
        stage_relative = binding["stage"]["address"] - binding["preload"]["base"]
        blob[-1] ^= 0x01
        blob_path.write_bytes(blob)
        payload = bytes(blob[stage_relative + DESCRIPTOR_SIZE:])
        refresh_artifact(target, manifest, "workbench-stdlib-blob")
        binding["preload"]["sha256"] = _sha256(blob_path)
        binding["stage"]["sha256"] = _sha256_bytes(bytes(blob[stage_relative:]))
        binding["overlay"]["sha256"] = _sha256_bytes(payload)
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "payload-crc", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "nonzero-padding")
        binding = manifest["overlay"]
        blob_path = target / ARTIFACT_PATHS["workbench-stdlib-blob"]
        blob = bytearray(blob_path.read_bytes())
        padding_at = binding["stdlib"]["size"]
        blob[padding_at] = 0xA5
        blob_path.write_bytes(blob)
        refresh_artifact(target, manifest, "workbench-stdlib-blob")
        binding["preload"]["sha256"] = _sha256(blob_path)
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "nonzero-padding", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "non-guard-contract")
        binding = manifest["overlay"]
        contract_path = target / ARTIFACT_PATHS["resolved-profile"]
        contract_text = contract_path.read_text(encoding="ascii").replace(
            "overlay_extra_defines=-DLISP65_STACK_GUARD",
            "overlay_extra_defines=",
        )
        contract_path.write_text(contract_text, encoding="ascii")
        contract_sha = _sha256(contract_path)
        build_id = int(contract_sha[:8], 16)
        binding["abi"]["contract_sha256"] = contract_sha
        binding["build_id"] = build_id
        refresh_artifact(target, manifest, "resolved-profile")
        blob_path = target / ARTIFACT_PATHS["workbench-stdlib-blob"]
        blob = bytearray(blob_path.read_bytes())
        stage_relative = binding["stage"]["address"] - binding["preload"]["base"]
        struct.pack_into("<I", blob, stage_relative + 6, build_id)
        blob_path.write_bytes(blob)
        refresh_artifact(target, manifest, "workbench-stdlib-blob")
        binding["preload"]["sha256"] = _sha256(blob_path)
        binding["stage"]["sha256"] = _sha256_bytes(bytes(blob[stage_relative:]))
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "non-guard-contract", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "resident-load-base")
        binding = manifest["overlay"]
        prg_path = target / ARTIFACT_PATHS["workbench-prg"]
        prg = bytearray(prg_path.read_bytes())
        prg[0:2] = struct.pack("<H", 0x2002)
        prg_path.write_bytes(prg)
        refresh_artifact(target, manifest, "workbench-prg")
        binding["resident"]["sha256"] = _sha256(prg_path)
        binding["resident"]["load_base"] = 0x2002
        binding["resident"]["file_end"] = 0x2002 + len(prg) - 2
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "resident-load-base", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "missing-field")
        del manifest["profile"]
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "missing-field", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "missing-artifact")
        manifest["artifacts"].pop()
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "missing-artifact", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "duplicate-id")
        manifest["artifacts"][1]["id"] = manifest["artifacts"][0]["id"]
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "duplicate-id", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "path-traversal")
        manifest["artifacts"][0]["path"] = "../outside"
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "path-traversal", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "absolute-path")
        manifest["artifacts"][0]["path"] = "/tmp/outside"
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "absolute-path", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "unknown-version")
        manifest["manifest_format"] = "lisp65-workbench-ship-v999"
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "unknown-version", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "symlink")
        artifact_path = target / manifest["artifacts"][0]["path"]
        artifact_path.unlink()
        artifact_path.symlink_to(candidate / manifest["artifacts"][0]["path"])
        _expect_verify(failures, "symlink", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "stdlib-gate-result")
        manifest["stdlib_trust"]["semantic_gate"]["result"] = "not-run"
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "stdlib-gate-result", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "stdlib-gate-hash")
        manifest["stdlib_trust"]["semantic_gate"]["artifact_sha256"] = (
            "0" * SHA256_HEX_LENGTH
        )
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "stdlib-gate-hash", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "stdlib-gate-count")
        manifest["stdlib_trust"]["semantic_gate"]["case_count"] += 1
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "stdlib-gate-count", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "stdlib-contract-sha")
        manifest["stdlib_trust"]["runtime_binding"]["contract_sha256"] = (
            "0" * SHA256_HEX_LENGTH
        )
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "stdlib-contract-sha", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "stdlib-build-id")
        manifest["stdlib_trust"]["runtime_binding"]["build_id"] ^= 1
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "stdlib-build-id", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "stdlib-runtime-length")
        manifest["stdlib_trust"]["runtime_binding"]["length"] += 1
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "stdlib-runtime-length", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "stdlib-runtime-crc")
        manifest["stdlib_trust"]["runtime_binding"]["crc16"] ^= 1
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "stdlib-runtime-crc", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "stdlib-literal-count")
        manifest["stdlib_trust"]["literal_envelope"]["symbol"] += 1
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "stdlib-literal-count", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "stdlib-literal-aggregate")
        manifest["stdlib_trust"]["literal_envelope"]["cons"] = 1
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "stdlib-literal-aggregate", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "stdlib-crc-trigger")
        manifest["stdlib_trust"]["integrity_policy"]["trigger"] = "after-mutation"
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "stdlib-crc-trigger", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "stdlib-overlay-calls")
        manifest["stdlib_trust"]["integrity_policy"]["overlay_calls"] += 1
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "stdlib-overlay-calls", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "error-text-profile")
        manifest["error_texts"]["profile"] = "host"
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "error-text-profile", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "error-text-slot")
        manifest["error_texts"]["slot"] -= 1
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "error-text-slot", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "error-text-active")
        manifest["error_texts"]["active_codes"].pop()
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "error-text-active", target, False)

        target, manifest = _mutated_package(
            candidate, cases_root, "error-text-resident-to-omitted"
        )
        resident_code = manifest["error_texts"]["resident_codes"].pop()
        manifest["error_texts"]["omitted_codes"].append(resident_code)
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "error-text-resident-to-omitted", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "error-text-offset")
        manifest["error_texts"]["offset"] += 1
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "error-text-offset", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "error-text-build-id")
        manifest["error_texts"]["build_id"] ^= 1
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "error-text-build-id", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "error-text-crc")
        manifest["error_texts"]["crc16"] ^= 1
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "error-text-crc", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "error-text-sha")
        manifest["error_texts"]["sha256"] = "0" * SHA256_HEX_LENGTH
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "error-text-sha", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "error-text-contract-sha")
        manifest["error_texts"]["contract_sha256"] = "0" * SHA256_HEX_LENGTH
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "error-text-contract-sha", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "error-text-not-in-slice")
        remove_table_from_valid_runtime_image(target, manifest)
        lower_errors = _runtime_overlay_contract_errors(
            target,
            manifest["artifacts"],
            manifest["runtime_overlays"],
            manifest["preloads"],
            manifest["overlay"],
            MANIFEST_FORMAT_V5,
        )
        if lower_errors:
            failures.append(
                "error-text-not-in-slice: rebuilt runtime binding is invalid: "
                + "; ".join(lower_errors)
            )
        if not _error_text_errors(
            target,
            manifest["error_texts"],
            manifest["runtime_overlays"],
            MANIFEST_FORMAT_V5,
        ):
            failures.append("error-text-not-in-slice: L65E binding accepted missing table")
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "error-text-not-in-slice", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "runtime-slot-limit")
        manifest["runtime_overlay_slots"]["product_limit"] += 1
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "runtime-slot-limit", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "runtime-slot-assignment")
        manifest["runtime_overlay_slots"]["assignments"][0]["name"] = "alternate"
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "runtime-slot-assignment", target, False)

        over_budget_binding = json.loads(json.dumps(candidate_manifest["runtime_overlays"]))
        template = over_budget_binding["slices"][-1]
        while len(over_budget_binding["slices"]) <= RUNTIME_OVERLAY_PRODUCT_SLOT_LIMIT:
            record = dict(template)
            record["id"] = len(over_budget_binding["slices"])
            record["name"] = f"over-budget-{record['id']:02d}"
            record["section"] = f".lisp65_rt_over_budget_{record['id']:02d}"
            over_budget_binding["slices"].append(record)
        over_budget_slots = _runtime_overlay_slot_binding(over_budget_binding)
        if not _runtime_overlay_slot_errors(
            over_budget_binding, over_budget_slots, MANIFEST_FORMAT_V5
        ):
            failures.append("runtime-slot-over-budget: product limit was not enforced")

        target, manifest = _mutated_package(candidate, cases_root, "runtime-missing-block")
        manifest.pop("runtime_overlays")
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "runtime-missing-block", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "runtime-extra-field")
        manifest["runtime_overlays"]["extra"] = 1
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "runtime-extra-field", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "runtime-artifact-hash")
        runtime_record = next(
            record
            for record in manifest["artifacts"]
            if record["id"] == RUNTIME_OVERLAY_ARTIFACT_ID
        )
        runtime_record["sha256"] = "0" * SHA256_HEX_LENGTH
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "runtime-artifact-hash", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "runtime-storage-address")
        manifest["runtime_overlays"]["storage"]["address"] += 1
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "runtime-storage-address", target, False)

        preload_mutations = {
            "role": "alternate-runtime-overlays",
            "artifact": "alternate-runtime-artifact",
            "file": "alternate-overlays.bin",
            "kind": "chip-ram",
            "address": RuntimeOverlayBank.STORAGE_BASE + 1,
            "address_bits": RuntimeOverlayBank.STORAGE_ADDRESS_BITS - 1,
            "length": candidate_manifest["preloads"][0]["length"] + 1,
            "crc16": candidate_manifest["preloads"][0]["crc16"] ^ 1,
            "crc16_algorithm": "crc-16-xmodem",
            "sha256": "0" * SHA256_HEX_LENGTH,
            "build_id": candidate_manifest["preloads"][0]["build_id"] ^ 1,
            "persistence": "power-stable",
            "recovery": "ignore-and-continue",
        }
        for field, value in preload_mutations.items():
            case_name = "runtime-preload-" + field.replace("_", "-")
            target, manifest = _mutated_package(candidate, cases_root, case_name)
            manifest["preloads"][0][field] = value
            _write_json(target / MANIFEST_NAME, manifest)
            _expect_verify(failures, case_name, target, False)

        target, manifest = _mutated_package(candidate, cases_root, "runtime-schema")
        manifest["runtime_overlays"]["schema"] = "lisp65-runtime-overlay-bank-v0"
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "runtime-schema", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "runtime-header-name")
        manifest["runtime_overlays"]["config_header"]["file"] = "alternate.h"
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "runtime-header-name", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "runtime-slice-hash")
        manifest["runtime_overlays"]["slices"][0]["sha256"] = "0" * SHA256_HEX_LENGTH
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "runtime-slice-hash", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "runtime-phase-name")
        manifest["runtime_overlays"]["slices"][0]["name"] = "runtime-test"
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "runtime-phase-name", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "runtime-extra-preload")
        manifest["preloads"].append(dict(manifest["preloads"][0]))
        _write_json(target / MANIFEST_NAME, manifest)
        _expect_verify(failures, "runtime-extra-preload", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "runtime-missing-artifact")
        (target / RUNTIME_OVERLAY_ARTIFACT).unlink()
        _expect_verify(failures, "runtime-missing-artifact", target, False)

        target, manifest = _mutated_package(candidate, cases_root, "runtime-symlink")
        runtime_path = target / RUNTIME_OVERLAY_ARTIFACT
        runtime_path.unlink()
        runtime_path.symlink_to(candidate / RUNTIME_OVERLAY_ARTIFACT)
        _expect_verify(failures, "runtime-symlink", target, False)

        _expect_failure(
            failures,
            "staged-preflight",
            lambda: (
                tracked.write_text("staged\n", encoding="ascii"),
                _git_for_test(repo, "add", "tracked.txt"),
                write_preflight(root / "staged.json", repo),
            ),
        )
        _git_for_test(repo, "reset", "--hard", "-q", "HEAD")

        tracked.write_text("unstaged\n", encoding="ascii")
        _expect_failure(
            failures,
            "unstaged-preflight",
            lambda: write_preflight(root / "unstaged.json", repo),
        )
        _git_for_test(repo, "reset", "--hard", "-q", "HEAD")

        untracked = repo / "untracked.tmp"
        untracked.write_text("untracked\n", encoding="ascii")
        _expect_failure(
            failures,
            "untracked-preflight",
            lambda: write_preflight(root / "untracked.json", repo),
        )
        untracked.unlink()

        (repo / "ignored.tmp").write_text("ignored\n", encoding="ascii")
        try:
            write_preflight(root / "ignored.json", repo)
        except ShipError as exc:
            failures.append(f"ignored-preflight: {exc}")

    if failures:
        raise ShipError("selftest failures:\n  " + "\n  ".join(failures))


def _print_errors(prefix: str, errors: list[str]) -> int:
    for error in errors:
        print(f"workbench-ship {prefix} FAIL: {error}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    candidate_parser = subparsers.add_parser("candidate", help="write an unverified manifest")
    candidate_parser.add_argument("--dir", required=True, type=Path)
    candidate_parser.add_argument("--stage-manifest", required=True, type=Path)
    candidate_parser.add_argument("--runtime-overlay-manifest", required=True, type=Path)

    preflight_parser = subparsers.add_parser("preflight", help="record a clean Git source")
    preflight_parser.add_argument("--out", required=True, type=Path)

    finalize_parser = subparsers.add_parser("finalize", help="create a G2-verified package")
    finalize_parser.add_argument("--preflight", required=True, type=Path)
    finalize_parser.add_argument("--candidate", required=True, type=Path)
    finalize_parser.add_argument("--out", required=True, type=Path)

    verify_parser = subparsers.add_parser("verify", help="verify a package offline")
    verify_parser.add_argument("--dir", required=True, type=Path)
    verify_parser.add_argument("--strict", action="store_true")
    verify_parser.add_argument(
        "--expect-format",
        choices=(MANIFEST_FORMAT_V3, MANIFEST_FORMAT_V4, MANIFEST_FORMAT_V5),
        help="add an operation-specific format requirement",
    )

    subparsers.add_parser("selftest", help="run manifest and Git preflight tests")
    args = parser.parse_args()

    try:
        if args.command == "candidate":
            create_candidate(
                args.dir,
                Path.cwd(),
                args.stage_manifest,
                args.runtime_overlay_manifest,
            )
            print(f"workbench-ship candidate OK: {args.dir / MANIFEST_NAME}")
        elif args.command == "preflight":
            write_preflight(args.out, Path.cwd())
            print(f"workbench-ship preflight OK: {args.out}")
        elif args.command == "finalize":
            finalize_candidate(args.preflight, args.candidate, args.out, Path.cwd())
            print(f"workbench-ship finalize OK: {args.out}")
        elif args.command == "verify":
            errors = verify_package(
                args.dir,
                strict=args.strict,
                expected_format=args.expect_format,
            )
            if errors:
                return _print_errors("verify", errors)
            print(f"workbench-ship verify OK: {args.dir}")
        elif args.command == "selftest":
            selftest()
            print("workbench-ship selftest OK")
        else:
            raise ShipError(f"unknown command: {args.command}")
    except ShipError as exc:
        return _print_errors(args.command, str(exc).splitlines())
    except OSError as exc:
        return _print_errors(args.command, [str(exc)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
