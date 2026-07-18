#!/usr/bin/env python3
"""Verify deployed Ship-v5 memory spans against the bound package manifest."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
from typing import Any, Mapping, Sequence


SCHEMA = "lisp65-hw-ship-memory-readback-v2"
RECEIPT_SCHEMA = "lisp65-hw-ship-memory-receipt-v2"
SHIP_FORMAT = "lisp65-workbench-ship-v5"
INTERNAL_G5_FORMAT = "lisp65-v2-capability-carrier-hw-package-v1"
R5_GLOBAL_G5_FORMAT = "lisp65-r5-global-g5-hw-package-v1"
PRG_ARTIFACT = "workbench-prg"
BANK5_ARTIFACT = "workbench-stdlib-blob"
ATTIC_ARTIFACT = "workbench-runtime-overlays"
SHELF_ARTIFACT = "attic-library-shelf"
D81_ARTIFACT = "workbench-d81"
BANK5_ROLE = "workbench-stdlib-boot"
ATTIC_ROLE = "runtime-overlays"
SHELF_ROLE = "attic-library-shelf"
BANK5_ADDRESS = 0x00050000
ATTIC_ADDRESS = 0x08000000
SHELF_ADDRESS = 0x08100000
ATTIC_KIND = "attic-ram"
ATTIC_PERSISTENCE = "reset-stable-power-volatile"
ATTIC_RECOVERY = "redeploy-required"
ATTIC_BINDING_SCHEMA = "lisp65-runtime-overlay-package-v2"
ATTIC_BINARY_FORMAT = "lisp65-runtime-overlay-bank-v1"
ATTIC_LIMIT = 0x08010000
CRC16_ALGORITHM = "crc-16-ccitt-false"
SHA256_LENGTH = 64
ISLAND_ADDRESS = 0x00001800
ISLAND_CAPACITY = 2048
ISLAND_SLOT_ID = 37
ISLAND_SLOT_NAME = "resident-island-installer"
ISLAND_ARTIFACT = "runtime-overlay-slot-37/resident-island"
ISLAND_SECTION = ".lisp65_resident_island"
ISLAND_START_SYMBOL = "__lisp65_resident_island_start"
ISLAND_END_SYMBOL = "__lisp65_resident_island_end"
ISLAND_INSTALLER_SECTION = ".lisp65_rt_island_00"


class ReadbackError(Exception):
    """A fail-closed manifest, artifact, transport or digest error."""


@dataclass(frozen=True)
class Span:
    name: str
    artifact_id: str
    address: int
    data: bytes

    @property
    def size(self) -> int:
        return len(self.data)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


@dataclass(frozen=True)
class Contract:
    manifest_path: Path
    manifest_sha256: str
    prg: Span
    bank5: Span
    attic: Span
    shelf: Span | None
    island: Span

    def spans_for(self, phase: str) -> tuple[Span, ...]:
        if phase == "staged":
            return (self.prg, self.bank5, self.attic) + ((self.shelf,) if self.shelf else ())
        if phase == "post-reset":
            return (self.attic,) + ((self.shelf,) if self.shelf else ()) + (self.island,)
        raise ReadbackError(f"unsupported phase: {phase}")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _crc16_ccitt_false(data: bytes) -> int:
    crc = 0xFFFF
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def _valid_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == SHA256_LENGTH
        and all(character in "0123456789abcdef" for character in value)
    )


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ReadbackError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_manifest(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        if path.is_symlink() or not path.is_file():
            raise ReadbackError(f"ship manifest is not a regular non-symlink file: {path}")
        raw = path.read_bytes()
    except OSError as error:
        raise ReadbackError(f"cannot read ship manifest {path}: {error}") from error
    try:
        manifest = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReadbackError(f"invalid ship manifest {path}: {error}") from error
    if not isinstance(manifest, dict):
        raise ReadbackError("ship manifest root must be an object")
    if manifest.get("manifest_format") not in {SHIP_FORMAT, INTERNAL_G5_FORMAT, R5_GLOBAL_G5_FORMAT}:
        raise ReadbackError(
            f"manifest_format must be {SHIP_FORMAT}, {INTERNAL_G5_FORMAT} or {R5_GLOBAL_G5_FORMAT}"
        )
    return manifest, raw


def _safe_package_path(package_dir: Path, relative: Any, label: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ReadbackError(f"{label} path must be a non-empty string")
    pure = PurePosixPath(relative)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise ReadbackError(f"{label} path is not package-relative: {relative}")
    candidate = package_dir.joinpath(*pure.parts)
    try:
        candidate.resolve().relative_to(package_dir.resolve())
    except (OSError, ValueError) as error:
        raise ReadbackError(f"{label} path escapes the package: {relative}") from error
    return candidate


def _regular_bytes(path: Path, label: str) -> bytes:
    try:
        if path.is_symlink() or not path.is_file():
            raise ReadbackError(f"{label} is not a regular non-symlink file: {path}")
        return path.read_bytes()
    except OSError as error:
        raise ReadbackError(f"cannot read {label} {path}: {error}") from error


def _artifact_records(manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise ReadbackError("artifacts must be an array")
    records: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(artifacts):
        if not isinstance(record, dict):
            raise ReadbackError(f"artifacts[{index}] must be an object")
        artifact_id = record.get("id")
        if not isinstance(artifact_id, str) or not artifact_id:
            raise ReadbackError(f"artifacts[{index}].id must be a non-empty string")
        if artifact_id in records:
            raise ReadbackError(f"duplicate artifact id: {artifact_id}")
        records[artifact_id] = record
    missing = sorted(
        {PRG_ARTIFACT, BANK5_ARTIFACT, ATTIC_ARTIFACT, D81_ARTIFACT} - records.keys()
    )
    if missing:
        raise ReadbackError("required artifacts are missing: " + ",".join(missing))
    return records


def _bound_artifact(
    package_dir: Path,
    record: Mapping[str, Any],
    supplied: Path,
    label: str,
) -> bytes:
    expected_size = record.get("size")
    expected_sha = record.get("sha256")
    if type(expected_size) is not int or expected_size <= 0:
        raise ReadbackError(f"{label} artifact size must be a positive integer")
    if not _valid_sha256(expected_sha):
        raise ReadbackError(f"{label} artifact SHA-256 is invalid")
    package_path = _safe_package_path(package_dir, record.get("path"), label)
    package_data = _regular_bytes(package_path, f"manifest-bound {label}")
    if len(package_data) != expected_size or _sha256(package_data) != expected_sha:
        raise ReadbackError(f"manifest-bound {label} differs from its artifact record")
    supplied_data = _regular_bytes(supplied, f"deployed {label}")
    if len(supplied_data) != expected_size or _sha256(supplied_data) != expected_sha:
        raise ReadbackError(f"deployed {label} differs from the ship manifest")
    return supplied_data


def _preload_record(
    manifest: Mapping[str, Any], artifact_id: str, expected_role: str
) -> dict[str, Any]:
    preloads = manifest.get("preloads")
    if not isinstance(preloads, list):
        raise ReadbackError("preloads must be an array")
    matches = [
        record
        for record in preloads
        if isinstance(record, dict) and record.get("artifact") == artifact_id
    ]
    if len(matches) != 1:
        raise ReadbackError(f"preloads must bind {artifact_id} exactly once")
    record = matches[0]
    if record.get("role") != expected_role:
        raise ReadbackError(f"{artifact_id} preload role must be {expected_role}")
    return record


def _check_preload_artifact(
    preload: Mapping[str, Any], artifact: Mapping[str, Any], size_field: str, label: str
) -> None:
    if preload.get("file") != artifact.get("path"):
        raise ReadbackError(f"{label} preload filename differs from its artifact")
    if preload.get(size_field) != artifact.get("size"):
        raise ReadbackError(f"{label} preload length differs from its artifact")
    if preload.get("sha256") != artifact.get("sha256"):
        raise ReadbackError(f"{label} preload SHA-256 differs from its artifact")


def _island_slot_payload(
    attic: bytes, runtime: Mapping[str, Any], build_id: int
) -> bytes:
    slices = runtime.get("slices")
    if not isinstance(slices, list):
        raise ReadbackError("runtime_overlays.slices must be an array")
    matches = [
        record for record in slices
        if isinstance(record, dict) and record.get("id") == ISLAND_SLOT_ID
    ]
    if len(matches) != 1:
        raise ReadbackError(f"runtime catalog must bind Slot {ISLAND_SLOT_ID} exactly once")
    slot = matches[0]
    if slot.get("name") != ISLAND_SLOT_NAME or slot.get("roles") != ["boot"]:
        raise ReadbackError("runtime catalog Slot 37 is not the boot-only island installer")
    if slot.get("slice_build_id") != build_id:
        raise ReadbackError("resident island Slot 37 build ID differs from the catalog")
    offset = slot.get("file_offset")
    size = slot.get("file_size")
    if type(offset) is not int or type(size) is not int or offset < 0 or size <= 0:
        raise ReadbackError("resident island Slot 37 extent is invalid")
    if offset + size > len(attic):
        raise ReadbackError("resident island Slot 37 exceeds the Attic artifact")
    payload = attic[offset:offset + size]
    if slot.get("sha256") != _sha256(payload):
        raise ReadbackError("resident island Slot 37 SHA-256 differs from its payload")
    if slot.get("crc16") != _crc16_ccitt_false(payload):
        raise ReadbackError("resident island Slot 37 CRC-16 differs from its payload")
    return payload


def _elf_symbol_span(nm: Path, elf: Path) -> tuple[int, int]:
    if nm.is_symlink() or not nm.is_file():
        raise ReadbackError(f"llvm-nm is missing or not regular: {nm}")
    try:
        completed = subprocess.run(
            [str(nm), "--defined-only", str(elf)],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ReadbackError(f"cannot inspect resident island ELF symbols: {error}") from error
    found: dict[str, list[int]] = {ISLAND_START_SYMBOL: [], ISLAND_END_SYMBOL: []}
    for line in completed.stdout.splitlines():
        fields = line.split()
        if len(fields) < 3 or fields[-1] not in found:
            continue
        try:
            found[fields[-1]].append(int(fields[0], 16))
        except ValueError as error:
            raise ReadbackError(f"invalid resident island ELF symbol: {line!r}") from error
    for name, values in found.items():
        if len(values) != 1:
            raise ReadbackError(f"resident island ELF must define {name} exactly once")
    return found[ISLAND_START_SYMBOL][0], found[ISLAND_END_SYMBOL][0]


def _extract_elf_section(objcopy: Path, elf: Path, section: str, label: str) -> bytes:
    if objcopy.is_symlink() or not objcopy.is_file():
        raise ReadbackError(f"llvm-objcopy is missing or not regular: {objcopy}")
    with tempfile.TemporaryDirectory(prefix="lisp65-hw-island-") as raw_tmp:
        output = Path(raw_tmp) / "section.bin"
        try:
            subprocess.run(
                [str(objcopy), "-O", "binary", f"--only-section={section}", str(elf), str(output)],
                check=True,
                capture_output=True,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            raise ReadbackError(f"cannot extract {label} from manifest-bound ELF: {error}") from error
        return _regular_bytes(output, f"extracted {label}")


def _resolve_island(
    elf_path: Path,
    nm: Path,
    objcopy: Path,
    attic: bytes,
    runtime: Mapping[str, Any],
    build_id: int,
) -> Span:
    elf = _regular_bytes(elf_path, "resident island ELF")
    elf_record = runtime.get("elf")
    if not isinstance(elf_record, dict) or not _valid_sha256(elf_record.get("sha256")):
        raise ReadbackError("runtime_overlays.elf SHA-256 binding is missing")
    if elf_record.get("file") != elf_path.name:
        raise ReadbackError("resident island ELF filename differs from runtime_overlays.elf.file")
    if _sha256(elf) != elf_record.get("sha256"):
        raise ReadbackError("resident island ELF differs from runtime_overlays.elf.sha256")
    start, end = _elf_symbol_span(nm, elf_path)
    if start != ISLAND_ADDRESS or not start < end <= ISLAND_ADDRESS + ISLAND_CAPACITY:
        raise ReadbackError(
            f"resident island ELF span must be 0x{ISLAND_ADDRESS:04x}..0x{ISLAND_ADDRESS + ISLAND_CAPACITY:04x}"
        )
    data = _extract_elf_section(objcopy, elf_path, ISLAND_SECTION, "resident island")
    if len(data) != end - start:
        raise ReadbackError("resident island ELF section length differs from its symbol span")
    installer = _extract_elf_section(
        objcopy, elf_path, ISLAND_INSTALLER_SECTION, "resident island installer"
    )
    payload = _island_slot_payload(attic, runtime, build_id)
    if installer != payload:
        raise ReadbackError("manifest-bound ELF installer differs from Attic Slot 37")
    if payload.count(data) != 1:
        raise ReadbackError("resident island image is not uniquely bound inside Slot 37")
    return Span("resident-island", ISLAND_ARTIFACT, ISLAND_ADDRESS, data)


def resolve_contract(
    manifest_path: Path,
    prg_path: Path,
    bank5_path: Path,
    attic_path: Path,
    d81_path: Path,
    island_elf_path: Path,
    nm: Path,
    objcopy: Path,
    shelf_path: Path | None = None,
) -> Contract:
    manifest, raw_manifest = _read_manifest(manifest_path)
    package_dir = manifest_path.parent
    if manifest.get("manifest_format") in {INTERNAL_G5_FORMAT, R5_GLOBAL_G5_FORMAT}:
        expected_profile = (
            "dialect-v2-capability-carrier"
            if manifest.get("manifest_format") == INTERNAL_G5_FORMAT
            else "dialect-v2"
        )
        if (
            manifest.get("profile") != expected_profile
            or manifest.get("shippable") is not False
            or manifest.get("release_authorization") != "none"
            or manifest.get("g5_claim") != "none"
        ):
            raise ReadbackError("G5 hardware package isolation policy drift")
        if manifest.get("manifest_format") == R5_GLOBAL_G5_FORMAT:
            product_set = manifest.get("product_artifact_set_sha256")
            if not _valid_sha256(product_set):
                raise ReadbackError("R5 global G5 package lacks the sealed product-set binding")
        candidate = manifest.get("candidate")
        if not isinstance(candidate, dict) or set(candidate) != {"path", "sha256"}:
            raise ReadbackError("internal G5 package candidate binding is invalid")
        candidate_path = _safe_package_path(package_dir, candidate.get("path"), "candidate")
        candidate_data = _regular_bytes(candidate_path, "internal G5 candidate")
        if not _valid_sha256(candidate.get("sha256")) or _sha256(candidate_data) != candidate.get("sha256"):
            raise ReadbackError("internal G5 package candidate SHA binding drift")
    records = _artifact_records(manifest)
    prg = _bound_artifact(package_dir, records[PRG_ARTIFACT], prg_path, "PRG")
    bank5 = _bound_artifact(package_dir, records[BANK5_ARTIFACT], bank5_path, "Bank-5")
    attic = _bound_artifact(package_dir, records[ATTIC_ARTIFACT], attic_path, "Attic")
    shelf: bytes | None = None
    if SHELF_ARTIFACT in records:
        if shelf_path is None:
            raise ReadbackError("manifest-bound Attic shelf requires --shelf")
        shelf = _bound_artifact(
            package_dir, records[SHELF_ARTIFACT], shelf_path, "Attic shelf"
        )
    elif shelf_path is not None:
        raise ReadbackError("--shelf supplied but the manifest has no Attic shelf artifact")
    _bound_artifact(package_dir, records[D81_ARTIFACT], d81_path, "D81")

    if len(prg) <= 2:
        raise ReadbackError("PRG has no payload after its load address")
    prg_address = int.from_bytes(prg[:2], "little")
    prg_payload = prg[2:]
    if prg_address < 0x0200 or prg_address + len(prg_payload) > 0x10000:
        raise ReadbackError("PRG payload lies outside the 16-bit resident address space")

    bank5_preload = _preload_record(manifest, BANK5_ARTIFACT, BANK5_ROLE)
    _check_preload_artifact(bank5_preload, records[BANK5_ARTIFACT], "size", "Bank-5")
    if bank5_preload.get("bank") != 5 or bank5_preload.get("address") != BANK5_ADDRESS:
        raise ReadbackError("Bank-5 preload must be bound to bank 5 at 0x050000")
    if BANK5_ADDRESS + len(bank5) > 0x00060000:
        raise ReadbackError("Bank-5 preload exceeds bank 5")

    attic_preload = _preload_record(manifest, ATTIC_ARTIFACT, ATTIC_ROLE)
    _check_preload_artifact(attic_preload, records[ATTIC_ARTIFACT], "length", "Attic")
    if attic_preload.get("kind") != ATTIC_KIND:
        raise ReadbackError(f"Attic preload kind must be {ATTIC_KIND}")
    if attic_preload.get("address") != ATTIC_ADDRESS:
        raise ReadbackError(f"Attic preload address must be 0x{ATTIC_ADDRESS:08x}")
    if attic_preload.get("address_bits") != 28:
        raise ReadbackError("Attic preload address_bits must be 28")
    if attic_preload.get("persistence") != ATTIC_PERSISTENCE:
        raise ReadbackError(f"Attic persistence must be {ATTIC_PERSISTENCE}")
    if attic_preload.get("recovery") != ATTIC_RECOVERY:
        raise ReadbackError(f"Attic recovery must be {ATTIC_RECOVERY}")
    attic_crc = _crc16_ccitt_false(attic)
    if attic_preload.get("crc16") != attic_crc:
        raise ReadbackError("Attic preload CRC-16 differs from the deployed artifact")
    if attic_preload.get("crc16_algorithm") != CRC16_ALGORITHM:
        raise ReadbackError(f"Attic CRC algorithm must be {CRC16_ALGORITHM}")
    build_id = attic_preload.get("build_id")
    if type(build_id) is not int or not 0 <= build_id <= 0xFFFFFFFF:
        raise ReadbackError("Attic preload build_id must be a uint32")
    if ATTIC_ADDRESS + len(attic) > 0x10000000:
        raise ReadbackError("Attic preload exceeds the 28-bit address space")

    shelf_span: Span | None = None
    if shelf is not None:
        shelf_preload = _preload_record(manifest, SHELF_ARTIFACT, SHELF_ROLE)
        _check_preload_artifact(
            shelf_preload, records[SHELF_ARTIFACT], "length", "Attic shelf"
        )
        if shelf_preload.get("kind") != ATTIC_KIND:
            raise ReadbackError(f"Attic shelf preload kind must be {ATTIC_KIND}")
        if shelf_preload.get("address") != SHELF_ADDRESS:
            raise ReadbackError(
                f"Attic shelf preload address must be 0x{SHELF_ADDRESS:08x}"
            )
        if shelf_preload.get("address_bits") != 28:
            raise ReadbackError("Attic shelf preload address_bits must be 28")
        if shelf_preload.get("persistence") != ATTIC_PERSISTENCE:
            raise ReadbackError(
                f"Attic shelf persistence must be {ATTIC_PERSISTENCE}"
            )
        if shelf_preload.get("recovery") != ATTIC_RECOVERY:
            raise ReadbackError(f"Attic shelf recovery must be {ATTIC_RECOVERY}")
        if shelf_preload.get("crc16") != _crc16_ccitt_false(shelf):
            raise ReadbackError("Attic shelf preload CRC-16 differs from the artifact")
        if shelf_preload.get("crc16_algorithm") != CRC16_ALGORITHM:
            raise ReadbackError(f"Attic shelf CRC algorithm must be {CRC16_ALGORITHM}")
        if SHELF_ADDRESS + len(shelf) > 0x10000000:
            raise ReadbackError("Attic shelf exceeds the 28-bit address space")
        shelf_span = Span("attic-library-shelf", SHELF_ARTIFACT, SHELF_ADDRESS, shelf)

    runtime = manifest.get("runtime_overlays")
    if not isinstance(runtime, dict) or runtime.get("schema") != ATTIC_BINDING_SCHEMA:
        raise ReadbackError(f"runtime_overlays.schema must be {ATTIC_BINDING_SCHEMA}")
    storage = runtime.get("storage")
    if not isinstance(storage, dict):
        raise ReadbackError("runtime_overlays.storage must be an object")
    expected_storage = {
        "format": ATTIC_BINARY_FORMAT,
        "file": records[ATTIC_ARTIFACT].get("path"),
        "kind": ATTIC_KIND,
        "address": ATTIC_ADDRESS,
        "address_bits": 28,
        "limit": ATTIC_LIMIT,
        "size": len(attic),
        "build_id": build_id,
        "crc16": attic_crc,
        "crc16_algorithm": CRC16_ALGORITHM,
        "sha256": _sha256(attic),
        "persistence": ATTIC_PERSISTENCE,
    }
    for field, expected in expected_storage.items():
        if storage.get(field) != expected:
            raise ReadbackError(f"runtime_overlays.storage.{field} differs from the Attic preload")
    if runtime.get("profile_build_id") != build_id:
        raise ReadbackError("Attic preload build_id differs from runtime_overlays profile")
    island = _resolve_island(island_elf_path, nm, objcopy, attic, runtime, build_id)

    return Contract(
        manifest_path=manifest_path,
        manifest_sha256=_sha256(raw_manifest),
        prg=Span("prg-payload", PRG_ARTIFACT, prg_address, prg_payload),
        bank5=Span("bank5-preload", BANK5_ARTIFACT, BANK5_ADDRESS, bank5),
        attic=Span("attic-catalog", ATTIC_ARTIFACT, ATTIC_ADDRESS, attic),
        shelf=shelf_span,
        island=island,
    )


def compare_readbacks(
    spans: Sequence[Span], readbacks: Mapping[str, bytes]
) -> list[str]:
    expected_names = {span.name for span in spans}
    actual_names = set(readbacks)
    errors = [f"missing readback: {name}" for name in sorted(expected_names - actual_names)]
    errors.extend(f"unexpected readback: {name}" for name in sorted(actual_names - expected_names))
    for span in spans:
        data = readbacks.get(span.name)
        if data is None:
            continue
        if len(data) != span.size:
            errors.append(
                f"{span.name} length mismatch: expected={span.size} actual={len(data)}"
            )
        else:
            actual_sha = _sha256(data)
            actual_crc = _crc16_ccitt_false(data)
            expected_crc = _crc16_ccitt_false(span.data)
            if actual_sha != span.sha256:
                errors.append(
                    f"{span.name} SHA-256 mismatch: expected={span.sha256} actual={actual_sha}"
                )
            if actual_crc != expected_crc:
                errors.append(
                    f"{span.name} CRC-16 mismatch: expected=0x{expected_crc:04x} "
                    f"actual=0x{actual_crc:04x}"
                )
    return errors


def _dump_span(
    m65: Path,
    device: str,
    span: Span,
    out_dir: Path,
    prefix: str,
    dry_run: bool,
    keep_halted: bool,
) -> bytes | None:
    output = out_dir / f"{prefix}-{span.name}.bin"
    spec = f"0x{span.address:08x}:0x{span.address + span.size:08x}={output}"
    command = [str(m65), "-l", device]
    if keep_halted:
        command.append("-H")
    command.extend(("--memsave", spec))
    if dry_run:
        print("DRY-RUN:", " ".join(command))
        print(
            f"DRY-RUN: expect {span.name} address=0x{span.address:08x} "
            f"length={span.size} sha256={span.sha256} "
            f"crc16=0x{_crc16_ccitt_false(span.data):04x}"
        )
        return None
    try:
        if output.exists() or output.is_symlink():
            output.unlink()
        subprocess.run(command, check=True)
        return _regular_bytes(output, f"{span.name} readback")
    except (OSError, subprocess.CalledProcessError) as error:
        raise ReadbackError(f"cannot read {span.name} from hardware: {error}") from error


def _report_lines(
    contract: Contract,
    phase: str,
    device: str,
    dry_run: bool,
    spans: Sequence[Span],
    readbacks: Mapping[str, bytes],
    errors: Sequence[str],
    receipt: Path,
) -> list[str]:
    lines = [
        f"schema={SCHEMA}",
        f"phase={phase}",
        f"manifest={contract.manifest_path}",
        f"manifest_sha256={contract.manifest_sha256}",
        f"device={device}",
        f"dry_run={int(dry_run)}",
        f"receipt={receipt}",
        f"evidence_scope={'pre-execution-halted' if phase == 'staged' else 'post-reset-retention-and-boot-install'}",
    ]
    for span in spans:
        lines.extend(
            (
                f"{span.name}.artifact={span.artifact_id}",
                f"{span.name}.address=0x{span.address:08x}",
                f"{span.name}.length={span.size}",
                f"{span.name}.expected_sha256={span.sha256}",
                f"{span.name}.expected_crc16=0x{_crc16_ccitt_false(span.data):04x}",
            )
        )
        if span.name in readbacks:
            lines.append(f"{span.name}.actual_sha256={_sha256(readbacks[span.name])}")
            lines.append(
                f"{span.name}.actual_crc16=0x{_crc16_ccitt_false(readbacks[span.name]):04x}"
            )
    lines.append(f"status={'DRY-RUN' if dry_run else ('FAIL' if errors else 'PASS')}")
    lines.extend(f"error={error}" for error in errors)
    return lines


def _clear_receipt(path: Path) -> None:
    try:
        if path.exists() or path.is_symlink():
            path.unlink()
    except OSError as error:
        raise ReadbackError(f"cannot clear stale Stage-A receipt {path}: {error}") from error


def _write_receipt(path: Path, contract: Contract, dry_run: bool) -> None:
    payload = {
        "schema": RECEIPT_SCHEMA,
        "manifest_sha256": contract.manifest_sha256,
        "island_sha256": contract.island.sha256,
        "dry_run": dry_run,
    }
    temporary = path.with_name(path.name + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            raise ReadbackError(f"Stage-A receipt must not be a symlink: {path}")
        if temporary.exists() or temporary.is_symlink():
            temporary.unlink()
        temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="ascii")
        temporary.replace(path)
    except OSError as error:
        raise ReadbackError(f"cannot write Stage-A receipt {path}: {error}") from error


def _verify_receipt(path: Path, contract: Contract, dry_run: bool) -> None:
    try:
        if path.is_symlink() or not path.is_file():
            raise ReadbackError(f"Stage-A receipt is missing or not regular: {path}")
        receipt = json.loads(
            path.read_text(encoding="ascii"), object_pairs_hook=_reject_duplicate_keys
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReadbackError(f"cannot read Stage-A receipt {path}: {error}") from error
    if not isinstance(receipt, dict) or set(receipt) != {
        "schema", "manifest_sha256", "island_sha256", "dry_run"
    }:
        raise ReadbackError("Stage-A receipt fields differ from the pinned contract")
    if receipt.get("schema") != RECEIPT_SCHEMA:
        raise ReadbackError(f"Stage-A receipt schema must be {RECEIPT_SCHEMA}")
    if receipt.get("manifest_sha256") != contract.manifest_sha256:
        raise ReadbackError("Ship manifest changed between Stage A and post-reset readback")
    if receipt.get("island_sha256") != contract.island.sha256:
        raise ReadbackError("resident island image changed between Stage A and post-reset readback")
    if receipt.get("dry_run") is not dry_run:
        raise ReadbackError("Stage-A receipt dry-run mode differs from post-reset readback")


def run(args: argparse.Namespace) -> int:
    contract = resolve_contract(
        args.manifest, args.prg, args.bank5, args.attic, args.d81,
        args.elf, args.nm, args.objcopy, args.shelf,
    )
    spans = contract.spans_for(args.phase)
    m65 = args.tools / "m65"
    if not args.dry_run and (m65.is_symlink() or not m65.is_file()):
        raise ReadbackError(f"m65 is missing or not a regular file: {m65}")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    if args.phase == "staged":
        _clear_receipt(args.receipt)
    else:
        _verify_receipt(args.receipt, contract, args.dry_run)
    readbacks: dict[str, bytes] = {}
    for span in spans:
        data = _dump_span(
            m65,
            args.device,
            span,
            args.out_dir,
            args.prefix,
            args.dry_run,
            args.phase == "staged",
        )
        if data is not None:
            readbacks[span.name] = data
    errors = [] if args.dry_run else compare_readbacks(spans, readbacks)
    report = args.out_dir / f"{args.prefix}.txt"
    report.write_text(
        "\n".join(
            _report_lines(
                contract,
                args.phase,
                args.device,
                args.dry_run,
                spans,
                readbacks,
                errors,
                args.receipt,
            )
        )
        + "\n",
        encoding="ascii",
    )
    print(f"wrote {report}")
    if args.dry_run:
        if args.phase == "staged":
            _write_receipt(args.receipt, contract, True)
        print(f"Ship-v5 memory readback {args.phase}: DRY-RUN (readback skipped)")
    elif errors:
        raise ReadbackError("; ".join(errors))
    else:
        if args.phase == "staged":
            _write_receipt(args.receipt, contract, False)
        print(f"Ship-v5 memory readback {args.phase}: PASS ({len(spans)} spans)")
    return 0


def _write_fixture(root: Path) -> tuple[Path, dict[str, Path], dict[str, Any]]:
    files = {
        PRG_ARTIFACT: root / "lisp65-mvp-workbench.prg",
        BANK5_ARTIFACT: root / "lisp65-mvp-workbench.blob.bin",
        ATTIC_ARTIFACT: root / "lisp65-mvp-workbench.overlays.bin",
        D81_ARTIFACT: root / "lisp65-mvp-workbench.d81",
    }
    payloads = {
        PRG_ARTIFACT: b"\x01\x20resident-prg-payload",
        BANK5_ARTIFACT: b"bank5-preload",
        D81_ARTIFACT: b"d81-fixture",
    }
    island = b"resident-island-image"
    installer = b"slot-37-prefix:" + island + b":slot-37-suffix"
    slot_offset = 64
    payloads[ATTIC_ARTIFACT] = bytes(slot_offset) + installer
    elf = root / "lisp65-workbench-overlay-linked.prg.elf"
    elf.write_bytes(b"manifest-bound-island-elf")
    island_section = root / "island-section.bin"
    island_section.write_bytes(island)
    installer_section = root / "island-installer-section.bin"
    installer_section.write_bytes(installer)
    nm = root / "fake-llvm-nm"
    nm.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' '00001800 T {ISLAND_START_SYMBOL}' "
        f"'{ISLAND_ADDRESS + len(island):08x} T {ISLAND_END_SYMBOL}'\n",
        encoding="ascii",
    )
    nm.chmod(0o755)
    objcopy = root / "fake-llvm-objcopy"
    objcopy.write_text(
        "#!/usr/bin/env python3\n"
        "from pathlib import Path\n"
        "import sys\n"
        "section = next(arg.split('=', 1)[1] for arg in sys.argv if arg.startswith('--only-section='))\n"
        f"sources = {{{ISLAND_SECTION!r}: {str(island_section)!r}, "
        f"{ISLAND_INSTALLER_SECTION!r}: {str(installer_section)!r}}}\n"
        "Path(sys.argv[-1]).write_bytes(Path(sources[section]).read_bytes())\n",
        encoding="ascii",
    )
    objcopy.chmod(0o755)
    files["island-elf"] = elf
    files["nm"] = nm
    files["objcopy"] = objcopy
    for artifact_id in (PRG_ARTIFACT, BANK5_ARTIFACT, ATTIC_ARTIFACT, D81_ARTIFACT):
        path = files[artifact_id]
        path.write_bytes(payloads[artifact_id])
    artifacts = [
        {
            "id": artifact_id,
            "path": path.name,
            "size": len(payloads[artifact_id]),
            "sha256": _sha256(payloads[artifact_id]),
        }
        for artifact_id, path in files.items()
        if artifact_id in payloads
    ]
    manifest: dict[str, Any] = {
        "manifest_format": SHIP_FORMAT,
        "artifacts": artifacts,
        "preloads": [
            {
                "role": ATTIC_ROLE,
                "artifact": ATTIC_ARTIFACT,
                "file": files[ATTIC_ARTIFACT].name,
                "kind": ATTIC_KIND,
                "address": ATTIC_ADDRESS,
                "address_bits": 28,
                "length": len(payloads[ATTIC_ARTIFACT]),
                "crc16": _crc16_ccitt_false(payloads[ATTIC_ARTIFACT]),
                "crc16_algorithm": CRC16_ALGORITHM,
                "sha256": _sha256(payloads[ATTIC_ARTIFACT]),
                "build_id": 0x12345678,
                "persistence": ATTIC_PERSISTENCE,
                "recovery": ATTIC_RECOVERY,
            },
            {
                "role": BANK5_ROLE,
                "artifact": BANK5_ARTIFACT,
                "file": files[BANK5_ARTIFACT].name,
                "bank": 5,
                "address": BANK5_ADDRESS,
                "size": len(payloads[BANK5_ARTIFACT]),
                "sha256": _sha256(payloads[BANK5_ARTIFACT]),
            },
        ],
        "runtime_overlays": {
            "schema": ATTIC_BINDING_SCHEMA,
            "profile_build_id": 0x12345678,
            "elf": {
                "file": elf.name,
                "sha256": _sha256(elf.read_bytes()),
            },
            "slices": [
                {
                    "id": ISLAND_SLOT_ID,
                    "name": ISLAND_SLOT_NAME,
                    "roles": ["boot"],
                    "slice_build_id": 0x12345678,
                    "file_offset": slot_offset,
                    "file_size": len(installer),
                    "sha256": _sha256(installer),
                    "crc16": _crc16_ccitt_false(installer),
                }
            ],
            "storage": {
                "format": ATTIC_BINARY_FORMAT,
                "file": files[ATTIC_ARTIFACT].name,
                "kind": ATTIC_KIND,
                "address": ATTIC_ADDRESS,
                "address_bits": 28,
                "limit": ATTIC_LIMIT,
                "size": len(payloads[ATTIC_ARTIFACT]),
                "build_id": 0x12345678,
                "crc16": _crc16_ccitt_false(payloads[ATTIC_ARTIFACT]),
                "crc16_algorithm": CRC16_ALGORITHM,
                "sha256": _sha256(payloads[ATTIC_ARTIFACT]),
                "persistence": ATTIC_PERSISTENCE,
            },
        },
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="ascii")
    return manifest_path, files, manifest


def selftest() -> int:
    failures: list[str] = []
    cases = 0
    with tempfile.TemporaryDirectory(prefix="lisp65-hw-ship-readback-") as raw_tmp:
        root = Path(raw_tmp)
        manifest_path, files, manifest = _write_fixture(root)

        def resolve(
            candidate: Path = manifest_path, shelf: Path | None = None
        ) -> Contract:
            return resolve_contract(
                candidate,
                files[PRG_ARTIFACT],
                files[BANK5_ARTIFACT],
                files[ATTIC_ARTIFACT],
                files[D81_ARTIFACT],
                files["island-elf"],
                files["nm"],
                files["objcopy"],
                shelf,
            )

        contract = resolve()
        cases += 1
        if contract.prg.address != 0x2001 or contract.prg.data != b"resident-prg-payload":
            failures.append("prg-payload")
        cases += 1
        staged = {span.name: span.data for span in contract.spans_for("staged")}
        if compare_readbacks(contract.spans_for("staged"), staged):
            failures.append("valid-staged")
        cases += 1
        post_reset = {span.name: span.data for span in contract.spans_for("post-reset")}
        if compare_readbacks(contract.spans_for("post-reset"), post_reset):
            failures.append("valid-post-reset")
        cases += 1
        corrupt_post_reset = dict(post_reset)
        corrupt_post_reset["resident-island"] = b"X" + contract.island.data[1:]
        if not compare_readbacks(contract.spans_for("post-reset"), corrupt_post_reset):
            failures.append("island-digest-mismatch")
        cases += 1
        missing_island = dict(post_reset)
        del missing_island["resident-island"]
        if not compare_readbacks(contract.spans_for("post-reset"), missing_island):
            failures.append("island-missing-readback")
        cases += 1
        corrupt = dict(staged)
        corrupt["attic-catalog"] = corrupt["attic-catalog"][:-1] + b"X"
        if not compare_readbacks(contract.spans_for("staged"), corrupt):
            failures.append("digest-mismatch")
        cases += 1
        missing = dict(staged)
        del missing["bank5-preload"]
        if not compare_readbacks(contract.spans_for("staged"), missing):
            failures.append("missing-readback")

        shelf_path = root / "lisp65-mvp-workbench.shelf.bin"
        shelf_data = b"attic-library-shelf-fixture"
        shelf_path.write_bytes(shelf_data)
        shelf_manifest = json.loads(json.dumps(manifest))
        shelf_manifest["artifacts"].append({
            "id": SHELF_ARTIFACT,
            "path": shelf_path.name,
            "size": len(shelf_data),
            "sha256": _sha256(shelf_data),
        })
        shelf_manifest["preloads"].append({
            "role": SHELF_ROLE,
            "artifact": SHELF_ARTIFACT,
            "file": shelf_path.name,
            "kind": ATTIC_KIND,
            "address": SHELF_ADDRESS,
            "address_bits": 28,
            "length": len(shelf_data),
            "crc16": _crc16_ccitt_false(shelf_data),
            "crc16_algorithm": CRC16_ALGORITHM,
            "sha256": _sha256(shelf_data),
            "persistence": ATTIC_PERSISTENCE,
            "recovery": ATTIC_RECOVERY,
        })
        shelf_manifest_path = root / "manifest-with-shelf.json"
        shelf_manifest_path.write_text(
            json.dumps(shelf_manifest, sort_keys=True) + "\n", encoding="ascii"
        )
        cases += 1
        shelf_contract = resolve(shelf_manifest_path, shelf_path)
        if (
            shelf_contract.shelf is None
            or shelf_contract.shelf.address != SHELF_ADDRESS
            or shelf_contract.shelf.data != shelf_data
            or shelf_contract.shelf not in shelf_contract.spans_for("staged")
            or shelf_contract.shelf not in shelf_contract.spans_for("post-reset")
        ):
            failures.append("shelf-valid")
        cases += 1
        try:
            resolve(shelf_manifest_path)
            failures.append("shelf-missing-argument")
        except ReadbackError:
            pass

        def reject(name: str, mutate: Any) -> None:
            nonlocal cases
            cases += 1
            candidate = root / f"{name}.json"
            data = json.loads(json.dumps(manifest))
            mutate(data)
            candidate.write_text(json.dumps(data, sort_keys=True) + "\n", encoding="ascii")
            try:
                resolve(candidate)
                failures.append(name)
            except ReadbackError:
                pass

        reject("format-v4", lambda data: data.__setitem__("manifest_format", "lisp65-workbench-ship-v4"))
        reject("attic-address", lambda data: data["preloads"][0].__setitem__("address", ATTIC_ADDRESS + 1))
        reject("attic-crc", lambda data: data["preloads"][0].__setitem__("crc16", 0))
        reject("attic-build-id", lambda data: data["preloads"][0].__setitem__("build_id", 1))
        reject("attic-storage", lambda data: data["runtime_overlays"]["storage"].__setitem__("address", ATTIC_ADDRESS + 1))
        reject("attic-duplicate", lambda data: data["preloads"].append(dict(data["preloads"][0])))
        reject("bank5-size", lambda data: data["preloads"][1].__setitem__("size", 1))
        reject("artifact-sha", lambda data: data["artifacts"][0].__setitem__("sha256", "0" * 64))
        reject("island-elf-sha", lambda data: data["runtime_overlays"]["elf"].__setitem__("sha256", "0" * 64))
        reject("island-slot-name", lambda data: data["runtime_overlays"]["slices"][0].__setitem__("name", "wrong"))
        reject("island-slot-sha", lambda data: data["runtime_overlays"]["slices"][0].__setitem__("sha256", "0" * 64))

        receipt = root / "stage-a-receipt.json"
        cases += 1
        _write_receipt(receipt, contract, False)
        try:
            _verify_receipt(receipt, contract, False)
        except ReadbackError:
            failures.append("receipt-valid")

        cases += 1
        bad_receipt = {
            "schema": RECEIPT_SCHEMA,
            "manifest_sha256": "0" * SHA256_LENGTH,
            "island_sha256": contract.island.sha256,
            "dry_run": False,
        }
        receipt.write_text(json.dumps(bad_receipt, sort_keys=True) + "\n", encoding="ascii")
        try:
            _verify_receipt(receipt, contract, False)
            failures.append("receipt-manifest-drift")
        except ReadbackError:
            pass

        cases += 1
        bad_receipt["manifest_sha256"] = contract.manifest_sha256
        bad_receipt["island_sha256"] = "0" * SHA256_LENGTH
        receipt.write_text(json.dumps(bad_receipt, sort_keys=True) + "\n", encoding="ascii")
        try:
            _verify_receipt(receipt, contract, False)
            failures.append("receipt-island-drift")
        except ReadbackError:
            pass

        cases += 1
        _write_receipt(receipt, contract, True)
        try:
            _verify_receipt(receipt, contract, False)
            failures.append("receipt-mode-drift")
        except ReadbackError:
            pass

    if failures:
        print("hw-ship-memory-readback selftest: FAIL " + ",".join(failures), file=sys.stderr)
        return 1
    print(f"hw-ship-memory-readback selftest: PASS cases={cases}")
    return 0


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--prg", type=Path)
    parser.add_argument("--bank5", type=Path)
    parser.add_argument("--attic", type=Path)
    parser.add_argument("--shelf", type=Path)
    parser.add_argument("--d81", type=Path)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--nm", type=Path, default=Path("tools/llvm-mos/bin/llvm-nm"))
    parser.add_argument("--objcopy", type=Path, default=Path("tools/llvm-mos/bin/llvm-objcopy"))
    parser.add_argument("--phase", choices=("staged", "post-reset"))
    parser.add_argument("--device", default="/dev/ttyUSB1")
    parser.add_argument("--tools", type=Path, default=Path("tools/m65tools"))
    parser.add_argument("--out-dir", type=Path, default=Path("build/hw"))
    parser.add_argument("--prefix", default="hw-ship-memory-readback")
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if not args.selftest:
        missing = [
            name
            for name in ("manifest", "prg", "bank5", "attic", "d81", "elf", "phase", "receipt")
            if getattr(args, name) is None
        ]
        if missing:
            parser.error("required unless --selftest: " + ", ".join(f"--{name}" for name in missing))
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.selftest:
        return selftest()
    try:
        return run(args)
    except ReadbackError as error:
        print(f"hw-ship-memory-readback: FAIL {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
