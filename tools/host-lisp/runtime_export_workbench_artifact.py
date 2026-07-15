#!/usr/bin/env python3
"""Extract, seal, and describe a Workbench-emitted Runtime Export artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "host-lisp"))

import d81_persistence_fault as D81  # noqa: E402
import l65m_contract as L65M  # noqa: E402


FORMAT = "lisp65-runtime-export-workbench-artifact-v1"
EMITTER = "workbench-lcc-fasl-v1"
CAPTURE_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{7,63}\Z")
PRELOAD_ADDRESS = 0x050000
L65M_HEADER_BYTES = 38
ENTRY_BYTES = 8
CODE_MAGIC = 0xB5
WORKBENCH_FORMAT = "lisp65-workbench-ship-v5"
WORKBENCH_STATUS = "g2-verified-candidate"
WORKBENCH_PRODUCT = "lisp65-workbench"
WORKBENCH_PROFILE = "mvp-vm-stdlib-einsuite-core-workbench"
WORKBENCH_ROOT_KEYS = {
    "artifacts", "error_texts", "gates", "manifest_format", "overlay",
    "preloads", "product", "profile", "runtime_overlay_slots",
    "runtime_overlays", "source", "status", "stdlib_trust",
}
WORKBENCH_GATES = {
    "G0": "pass",
    "G1": "pass",
    "G2": "pass",
    "G3": "not-available",
    "G4": "not-run",
    "G5": "not-run",
}
WORKBENCH_ARTIFACTS = {
    "workbench-prg": "lisp65-mvp-workbench.prg",
    "workbench-stdlib-blob": "lisp65-mvp-workbench.blob.bin",
    "workbench-d81": "lisp65-mvp-workbench.d81",
    "vm-stdlib-footprint": "mvp-vm-stdlib-footprint.txt",
    "workbench-d81-manifest": "workbench-d81-manifest.txt",
    "stdlib-artifact-manifest": "stdlib-artifact-manifest.json",
    "resolved-profile": "resolved-profile.txt",
    "toolchain-report": "toolchain-report.txt",
    "workbench-runtime-overlays": "lisp65-mvp-workbench.overlays.bin",
}


class ArtifactError(RuntimeError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ArtifactError("duplicate JSON key in Workbench ship manifest: %s" % key)
        result[key] = value
    return result


def _is_hex(value: Any, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(ch in "0123456789abcdef" for ch in value)
    )


def parse_workbench_ship(data: bytes) -> dict[str, Any]:
    try:
        manifest = json.loads(data.decode("utf-8"), object_pairs_hook=_strict_object)
    except ArtifactError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactError("Workbench ship manifest is not valid strict JSON") from exc
    if not isinstance(manifest, dict):
        raise ArtifactError("Workbench ship manifest must be a JSON object")
    missing = sorted(WORKBENCH_ROOT_KEYS - set(manifest))
    extra = sorted(set(manifest) - WORKBENCH_ROOT_KEYS)
    if missing or extra:
        raise ArtifactError(
            "Workbench ship manifest keys differ: missing=%s extra=%s"
            % (",".join(missing) or "-", ",".join(extra) or "-")
        )
    expected_identity = {
        "manifest_format": WORKBENCH_FORMAT,
        "status": WORKBENCH_STATUS,
        "product": WORKBENCH_PRODUCT,
        "profile": WORKBENCH_PROFILE,
    }
    for key, expected in expected_identity.items():
        if manifest[key] != expected:
            raise ArtifactError("Workbench ship %s must be %s" % (key, expected))
    if manifest["gates"] != WORKBENCH_GATES:
        raise ArtifactError("Workbench ship gates must be the verified G0-G2 vector")

    source = manifest["source"]
    if not isinstance(source, dict) or set(source) != {
        "commit", "tree", "dirty", "worktree_sha256",
    }:
        raise ArtifactError("Workbench ship source record has the wrong schema")
    if not _is_hex(source["commit"], 40) or not _is_hex(source["tree"], 40):
        raise ArtifactError("Workbench ship source commit/tree must be lowercase Git hashes")
    if not isinstance(source["dirty"], bool):
        raise ArtifactError("Workbench ship source dirty flag must be boolean")
    if not _is_hex(source["worktree_sha256"], 64):
        raise ArtifactError("Workbench ship source worktree hash must be SHA-256")

    artifacts = manifest["artifacts"]
    if not isinstance(artifacts, list) or len(artifacts) != len(WORKBENCH_ARTIFACTS):
        raise ArtifactError("Workbench ship must contain exactly nine artifact records")
    found: dict[str, str] = {}
    for index, record in enumerate(artifacts):
        if not isinstance(record, dict) or set(record) != {"id", "path", "size", "sha256"}:
            raise ArtifactError("Workbench ship artifact %d has the wrong schema" % index)
        artifact_id = record["id"]
        path = record["path"]
        if artifact_id in found:
            raise ArtifactError("Workbench ship contains duplicate artifact id: %s" % artifact_id)
        if not isinstance(path, str) or not path or "/" in path or "\\" in path:
            raise ArtifactError("Workbench ship artifact path must be a package basename")
        if not isinstance(record["size"], int) or isinstance(record["size"], bool) or record["size"] <= 0:
            raise ArtifactError("Workbench ship artifact size must be positive")
        if not _is_hex(record["sha256"], 64):
            raise ArtifactError("Workbench ship artifact hash must be SHA-256")
        found[artifact_id] = path
    if found != WORKBENCH_ARTIFACTS:
        raise ArtifactError("Workbench ship artifact identities/paths differ from v5")
    for key in (
        "error_texts", "overlay", "runtime_overlay_slots", "runtime_overlays", "stdlib_trust",
    ):
        if not isinstance(manifest[key], dict):
            raise ArtifactError("Workbench ship %s must be an object" % key)
    if not isinstance(manifest["preloads"], list) or not manifest["preloads"]:
        raise ArtifactError("Workbench ship preloads must be a non-empty list")
    return manifest


def _read(path: Path, label: str) -> bytes:
    try:
        if path.is_symlink() or not path.is_file():
            raise ArtifactError("%s must be a regular non-symlink file: %s" % (label, path))
        return path.read_bytes()
    except ArtifactError:
        raise
    except OSError as exc:
        raise ArtifactError("cannot read %s %s: %s" % (label, path, exc)) from exc


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_capture_id(value: Any) -> str:
    if not isinstance(value, str) or CAPTURE_ID_RE.fullmatch(value) is None:
        raise ArtifactError(
            "capture id must contain 8..64 safe ASCII characters "
            "([A-Za-z0-9][A-Za-z0-9._-]*)"
        )
    return value


def _u16(data: bytes | bytearray, offset: int, label: str) -> int:
    if offset < 0 or offset + 2 > len(data):
        raise ArtifactError("%s is truncated at byte %d" % (label, offset))
    return data[offset] | (data[offset + 1] << 8)


def _u32(data: bytes | bytearray, offset: int, label: str) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ArtifactError("%s is truncated at byte %d" % (label, offset))
    return (
        data[offset]
        | (data[offset + 1] << 8)
        | (data[offset + 2] << 16)
        | (data[offset + 3] << 24)
    )


def _put_u32(data: bytearray, offset: int, value: int, label: str) -> None:
    if offset < 0 or offset + 4 > len(data):
        raise ArtifactError("%s is truncated at byte %d" % (label, offset))
    data[offset : offset + 4] = value.to_bytes(4, "little")


def _canonical_name(name: str) -> bytes:
    try:
        raw = name.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ArtifactError("slot name must be ASCII") from exc
    if not 1 <= len(raw) <= 16:
        raise ArtifactError("slot name must contain 1..16 ASCII bytes")
    return bytes(ch - 32 if 97 <= ch <= 122 else ch for ch in raw)


def read_d81_slot(image: bytes, slot: str) -> tuple[bytes, dict[str, int]]:
    if len(image) != D81.IMAGE_SIZE:
        raise ArtifactError(
            "D81 image size %d differs from %d" % (len(image), D81.IMAGE_SIZE)
        )
    wanted = _canonical_name(slot)
    matches = [
        item
        for item in D81.directory_slots(image)
        if item.record[2] != 0 and D81.entry_name(item.record) == wanted
    ]
    if not matches:
        raise ArtifactError("D81 slot not found: %s" % slot)
    if len(matches) != 1:
        raise ArtifactError("D81 contains duplicate slot name: %s" % slot)
    match = matches[0]
    file_type = match.record[2]
    if not (file_type & 0x80) or (file_type & 0x07) != 1:
        raise ArtifactError("D81 slot %s is not a closed SEQ file" % slot)
    try:
        payload = D81.read_record_payload(image, match.record)
        chain = D81.file_chain(image, match.record)
    except ValueError as exc:
        raise ArtifactError("cannot read D81 slot %s: %s" % (slot, exc)) from exc
    return payload, {
        "directory_track": match.track,
        "directory_sector": match.sector,
        "directory_entry": match.index,
        "file_type": file_type,
        "blocks": len(chain),
    }


def canonical_l65m(slot_payload: bytes) -> tuple[bytes, L65M.Summary, int]:
    if len(slot_payload) < 4:
        raise ArtifactError("slot payload is shorter than the L65M container prefix")
    blob_bytes = _u16(slot_payload, 0, "L65M prefix")
    metadata_bytes = _u16(slot_payload, 2, "L65M prefix")
    total = 4 + blob_bytes + metadata_bytes
    if total > len(slot_payload):
        raise ArtifactError(
            "declared L65M length %d exceeds slot payload %d" % (total, len(slot_payload))
        )
    padding = slot_payload[total:]
    bad = next((index for index, value in enumerate(padding) if value != 0x20), None)
    if bad is not None:
        raise ArtifactError(
            "slot padding contains non-space byte 0x%02x at offset %d"
            % (padding[bad], total + bad)
        )
    image = slot_payload[:total]
    try:
        summary = L65M.validate_image(image)
    except L65M.ContractError as exc:
        raise ArtifactError("extracted L65M failed v1 validation: %s" % exc) from exc
    return image, summary, len(padding)


def _metadata_layout(image: bytes) -> tuple[int, int, int]:
    blob_bytes = _u16(image, 0, "L65M prefix")
    metadata_at = 4 + blob_bytes
    if metadata_at + L65M_HEADER_BYTES > len(image):
        raise ArtifactError("L65M metadata header is truncated")
    entry_count = _u16(image, metadata_at + 16, "L65M entry count")
    entries_off = _u16(image, metadata_at + 24, "L65M entry table")
    if entries_off < L65M_HEADER_BYTES:
        raise ArtifactError("L65M entry table overlaps its header")
    if metadata_at + entries_off + entry_count * ENTRY_BYTES > len(image):
        raise ArtifactError("L65M entry table is truncated")
    return metadata_at, entry_count, entries_off


def entry_arity(image: bytes, entry_name: str) -> tuple[int, int]:
    metadata_at, entry_count, entries_off = _metadata_layout(image)
    strings_off = _u16(image, metadata_at + 32, "L65M string pool")
    strings_bytes = _u16(image, metadata_at + 34, "L65M string pool length")
    strings_at = metadata_at + strings_off
    strings_end = strings_at + strings_bytes
    if strings_at < metadata_at or strings_end > len(image):
        raise ArtifactError("L65M string pool is out of bounds")
    found: tuple[int, int] | None = None
    for index in range(entry_count):
        record = metadata_at + entries_off + index * ENTRY_BYTES
        name_off = _u16(image, record, "L65M entry name")
        if name_off >= strings_bytes:
            raise ArtifactError("L65M entry name offset is out of bounds")
        end = image.find(b"\x00", strings_at + name_off, strings_end)
        if end < 0:
            raise ArtifactError("L65M entry name is unterminated")
        try:
            name = image[strings_at + name_off : end].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ArtifactError("L65M entry name is not UTF-8") from exc
        if name != entry_name:
            continue
        flags = image[record + 3]
        if flags & 1:
            raise ArtifactError("runtime entry is a macro, not a function: %s" % entry_name)
        code_off = _u16(image, record + 4, "L65M entry code offset")
        code_len = _u16(image, record + 6, "L65M entry code length")
        if code_len < 2 or 4 + code_off + 2 > metadata_at:
            raise ArtifactError("runtime entry code object is truncated: %s" % entry_name)
        if image[4 + code_off] != CODE_MAGIC:
            raise ArtifactError("runtime entry has no P0 code header: %s" % entry_name)
        found = (image[4 + code_off + 1], flags)
    if found is None:
        raise ArtifactError("runtime entry is missing from L65M: %s" % entry_name)
    return found


def validate_entry(image: bytes, entry_name: str, expected_arity: int) -> None:
    if not 0 <= expected_arity <= 255:
        raise ArtifactError("entry arity must be in 0..255")
    actual, _flags = entry_arity(image, entry_name)
    if actual != expected_arity:
        raise ArtifactError(
            "runtime entry arity differs: %s has %d, expected %d"
            % (entry_name, actual, expected_arity)
        )


def bank5_preload(image: bytes) -> bytes:
    try:
        L65M.validate_image(image)
    except L65M.ContractError as exc:
        raise ArtifactError("cannot rebase invalid L65M: %s" % exc) from exc
    metadata_at, entry_count, entries_off = _metadata_layout(image)
    preload = bytearray(image[4:])
    preload_metadata_at = metadata_at - 4
    if _u32(preload, preload_metadata_at + 8, "L65M code base") != 0:
        raise ArtifactError("disk L65M code base must be zero before rebasing")
    _put_u32(preload, preload_metadata_at + 8, PRELOAD_ADDRESS, "L65M code base")
    for index in range(entry_count):
        bank_at = preload_metadata_at + entries_off + index * ENTRY_BYTES + 2
        if preload[bank_at] != 0:
            raise ArtifactError("disk L65M entry bank must be zero before rebasing")
        preload[bank_at] = PRELOAD_ADDRESS >> 16

    inverse = bytearray(preload)
    _put_u32(inverse, preload_metadata_at + 8, 0, "inverse L65M code base")
    for index in range(entry_count):
        inverse[preload_metadata_at + entries_off + index * ENTRY_BYTES + 2] = 0
    if bytes(inverse) != image[4:]:
        raise ArtifactError("Bank-5 rebase changed bytes outside base/bank fields")
    try:
        L65M.validate_image(image[:4] + bytes(inverse))
    except L65M.ContractError as exc:
        raise ArtifactError("inverse Bank-5 rebase failed L65M validation: %s" % exc) from exc
    return bytes(preload)


def byte_diff(left: bytes, right: bytes) -> dict[str, Any]:
    common = min(len(left), len(right))
    positions = [index for index in range(common) if left[index] != right[index]]
    differing = len(positions) + abs(len(left) - len(right))
    first = positions[0] if positions else (common if len(left) != len(right) else None)
    return {
        "equal": differing == 0,
        "left_bytes": len(left),
        "right_bytes": len(right),
        "differing_bytes": differing,
        "first_difference": first,
        "left_sha256": _sha(left),
        "right_sha256": _sha(right),
    }


def _file_record(path: Path, label: str) -> tuple[bytes, dict[str, Any]]:
    data = _read(path, label)
    return data, {"path": str(path), "bytes": len(data), "sha256": _sha(data)}


def _derivation(
    *, capture_id: str, source_sha256: str, ship_sha256: str, before_sha256: str,
    after_sha256: str, slot: str, slot_sha256: str, l65m_sha256: str,
    preload_sha256: str, lcc_records: list[dict[str, Any]],
) -> dict[str, Any]:
    inputs = {
        "capture_id": validate_capture_id(capture_id),
        "emitter": EMITTER,
        "workbench_ship_manifest_sha256": ship_sha256,
        "source_sha256": source_sha256,
        "before_d81_sha256": before_sha256,
        "after_d81_sha256": after_sha256,
        "slot": _canonical_name(slot).decode("ascii"),
        "slot_payload_sha256": slot_sha256,
        "l65m_sha256": l65m_sha256,
        "preload_sha256": preload_sha256,
        "lcc_inputs": [
            {"path": record["path"], "sha256": record["sha256"]}
            for record in lcc_records
        ],
    }
    encoded = json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "format": "lisp65-runtime-export-workbench-derivation-v1",
        "inputs": inputs,
        "sha256": _sha(encoded),
    }


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=path.name + ".", dir=path.parent, delete=False) as handle:
        tmp = Path(handle.name)
        handle.write(data)
    try:
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def capture(args: argparse.Namespace) -> dict[str, Any]:
    capture_id = validate_capture_id(args.capture_id)
    _source, source_record = _file_record(args.source, "application source")
    ship, ship_record = _file_record(args.ship_manifest, "Workbench ship manifest")
    before, before_record = _file_record(args.before_d81, "before D81")
    after, after_record = _file_record(args.after_d81, "after D81")
    ship_json = parse_workbench_ship(ship)

    slot_payload, slot_record = read_d81_slot(after, args.slot)
    image, summary, padding_bytes = canonical_l65m(slot_payload)
    validate_entry(image, args.entry, args.arity)
    preload = bank5_preload(image)

    comparisons: dict[str, Any] = {}
    comparison_equal = True
    if args.host_l65m is not None:
        host_l65m = _read(args.host_l65m, "host L65M")
        try:
            L65M.validate_image(host_l65m)
        except L65M.ContractError as exc:
            raise ArtifactError("host L65M failed v1 validation: %s" % exc) from exc
        comparisons["host_l65m"] = byte_diff(image, host_l65m)
        comparison_equal &= comparisons["host_l65m"]["equal"]
    if args.host_preload is not None:
        host_preload = _read(args.host_preload, "host preload")
        comparisons["host_preload"] = byte_diff(preload, host_preload)
        comparison_equal &= comparisons["host_preload"]["equal"]
    if args.require_host_equal and not comparisons:
        raise ArtifactError("--require-host-equal needs --host-l65m or --host-preload")
    if args.require_host_equal and not comparison_equal:
        raise ArtifactError("Workbench artifact differs from a required host comparison")
    if args.require_d81_change and before == after:
        raise ArtifactError("before and after D81 images are byte-identical")

    lcc_records = []
    lcc_paths: set[str] = set()
    if not args.lcc_input:
        raise ArtifactError("at least one lcc input is required")
    for path in args.lcc_input:
        _data, record = _file_record(path, "lcc input")
        identity = str(path.resolve())
        if identity in lcc_paths:
            raise ArtifactError("duplicate lcc input: %s" % identity)
        lcc_paths.add(identity)
        lcc_records.append(record)

    derivation = _derivation(
        capture_id=capture_id,
        source_sha256=source_record["sha256"],
        ship_sha256=ship_record["sha256"],
        before_sha256=before_record["sha256"],
        after_sha256=after_record["sha256"],
        slot=args.slot,
        slot_sha256=_sha(slot_payload),
        l65m_sha256=_sha(image),
        preload_sha256=_sha(preload),
        lcc_records=lcc_records,
    )

    report = {
        "format": FORMAT,
        "status": "passed",
        "emitter": EMITTER,
        "application": {
            "entry": {"name": args.entry, "arity": args.arity},
            "slot": args.slot,
            "l65m": {
                "bytes": len(image),
                "sha256": _sha(image),
                "blob_bytes": summary.blob_bytes,
                "metadata_bytes": summary.metadata_bytes,
                "entry_names": summary.entry_names,
            },
            "preload": {
                "address": PRELOAD_ADDRESS,
                "bytes": len(preload),
                "sha256": _sha(preload),
            },
        },
        "capture": {
            "capture_id": capture_id,
            **slot_record,
            "slot_payload_bytes": len(slot_payload),
            "slot_payload_sha256": _sha(slot_payload),
            "padding_byte": 0x20,
            "padding_bytes": padding_bytes,
            "d81_changed": before != after,
        },
        "provenance": {
            "source": source_record,
            "workbench_ship": {
                **ship_record,
                "manifest_format": ship_json.get("manifest_format"),
                "status": ship_json.get("status"),
                "product": ship_json.get("product"),
                "profile": ship_json.get("profile"),
                "source": ship_json["source"],
                "gates": ship_json["gates"],
            },
            "before_d81": before_record,
            "after_d81": after_record,
            "lcc_inputs": lcc_records,
        },
        "derivation": derivation,
        "comparisons": comparisons,
    }
    encoded = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _atomic_write(args.l65m_out, image)
    _atomic_write(args.preload_out, preload)
    _atomic_write(args.report_out, encoded)
    return report


def _expect_failure(label: str, needle: str, operation: Any) -> None:
    try:
        operation()
    except ArtifactError as exc:
        if needle not in str(exc):
            raise ArtifactError("selftest %s failed for wrong reason: %s" % (label, exc)) from exc
    else:
        raise ArtifactError("selftest mutation passed: %s" % label)


def _selftest_ship_manifest() -> dict[str, Any]:
    return {
        "manifest_format": WORKBENCH_FORMAT,
        "status": WORKBENCH_STATUS,
        "product": WORKBENCH_PRODUCT,
        "profile": WORKBENCH_PROFILE,
        "source": {
            "commit": "1" * 40,
            "tree": "2" * 40,
            "dirty": False,
            "worktree_sha256": "3" * 64,
        },
        "gates": dict(WORKBENCH_GATES),
        "artifacts": [
            {"id": artifact_id, "path": path, "size": index + 1, "sha256": "%x" % (index + 1) * 64}
            for index, (artifact_id, path) in enumerate(WORKBENCH_ARTIFACTS.items())
        ],
        "overlay": {},
        "runtime_overlays": {},
        "runtime_overlay_slots": {},
        "preloads": [{}],
        "stdlib_trust": {},
        "error_texts": {},
    }


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True) + "\n").encode("utf-8")


def selftest() -> int:
    fixture = json.loads((ROOT / "tests/bytecode/formats/p0-disk-lib-v1.json").read_text())
    minimal = next(item for item in fixture["goldens"] if item["id"] == "minimal")
    image = bytes.fromhex(minimal["image_hex"])
    L65M.validate_image(image)
    payload = image + b" " * (8192 - len(image))
    d81 = D81.seed_file(bytes(D81.blank_image()), "fasl0", payload)

    extracted, slot_record = read_d81_slot(d81, "FASL0")
    canonical, summary, padding = canonical_l65m(extracted)
    if canonical != image or summary.entry_names != ["id"] or padding != 8192 - len(image):
        raise ArtifactError("selftest did not recover the canonical L65M")
    if slot_record["blocks"] != 33:
        raise ArtifactError("selftest D81 chain did not cross multiple sectors")
    validate_entry(canonical, "id", 0)
    preload = bank5_preload(canonical)
    metadata_at = _u16(canonical, 0, "selftest")
    if _u32(preload, metadata_at + 8, "selftest preload base") != PRELOAD_ADDRESS:
        raise ArtifactError("selftest preload base was not rebased")
    entries_off = _u16(preload, metadata_at + 24, "selftest preload entries")
    if preload[metadata_at + entries_off + 2] != 5:
        raise ArtifactError("selftest preload entry bank was not rebased")

    bad_padding = bytearray(payload)
    bad_padding[len(image) + 7] = 0
    _expect_failure("padding", "non-space", lambda: canonical_l65m(bytes(bad_padding)))
    short = bytearray(payload)
    short[0:2] = (0xFFFF).to_bytes(2, "little")
    _expect_failure("declared-length", "exceeds", lambda: canonical_l65m(bytes(short)))
    _expect_failure("arity", "arity differs", lambda: validate_entry(image, "id", 1))
    _expect_failure("entry", "missing", lambda: validate_entry(image, "missing", 0))
    _expect_failure("slot", "not found", lambda: read_d81_slot(d81, "missing"))

    equal = byte_diff(image, image)
    changed = byte_diff(image, image[:-1] + bytes((image[-1] ^ 1,)))
    if not equal["equal"] or changed["equal"] or changed["differing_bytes"] != 1:
        raise ArtifactError("selftest byte-diff accounting failed")

    valid_ship = _selftest_ship_manifest()
    parse_workbench_ship(_json_bytes(valid_ship))
    _expect_failure(
        "ship-duplicate-key",
        "duplicate JSON key",
        lambda: parse_workbench_ship(b'{"manifest_format":"a","manifest_format":"b"}'),
    )
    ship_mutations = (
        ("format", "manifest_format", "lisp65-workbench-ship-v4", "manifest_format"),
        ("status", "status", "unverified-candidate", "status"),
        ("product", "product", "not-workbench", "product"),
        ("profile", "profile", "wrong-profile", "profile"),
    )
    for label, key, value, needle in ship_mutations:
        mutated = json.loads(json.dumps(valid_ship))
        mutated[key] = value
        _expect_failure(
            "ship-" + label,
            needle,
            lambda changed=mutated: parse_workbench_ship(_json_bytes(changed)),
        )
    bad_gates = json.loads(json.dumps(valid_ship))
    bad_gates["gates"]["G2"] = "not-run"
    _expect_failure(
        "ship-gates", "verified G0-G2", lambda: parse_workbench_ship(_json_bytes(bad_gates))
    )
    bad_artifacts = json.loads(json.dumps(valid_ship))
    bad_artifacts["artifacts"][0]["sha256"] = "x" * 64
    _expect_failure(
        "ship-artifact-hash",
        "artifact hash",
        lambda: parse_workbench_ship(_json_bytes(bad_artifacts)),
    )

    with tempfile.TemporaryDirectory(prefix="runtime-export-workbench-selftest-") as raw:
        base = Path(raw)
        source = base / "source.lisp"
        ship = base / "manifest.json"
        before = base / "before.d81"
        after = base / "after.d81"
        lcc = base / "lcc.lisp"
        source.write_text("(defun id () 0)\n", encoding="ascii")
        ship.write_bytes(_json_bytes(valid_ship))
        before.write_bytes(bytes(D81.blank_image()))
        after.write_bytes(d81)
        lcc.write_text("; selftest lcc\n", encoding="ascii")
        args = argparse.Namespace(
            capture_id="selftest-capture-01",
            source=source,
            ship_manifest=ship,
            before_d81=before,
            after_d81=after,
            slot="fasl0",
            entry="id",
            arity=0,
            lcc_input=[lcc],
            l65m_out=base / "runtime-app.l65m",
            preload_out=base / "runtime-preload.bin",
            report_out=base / "report.json",
            host_l65m=None,
            host_preload=None,
            require_host_equal=False,
            require_d81_change=True,
        )
        report = capture(args)
        if (base / "runtime-app.l65m").read_bytes() != image:
            raise ArtifactError("selftest capture wrote the wrong L65M")
        if (base / "runtime-preload.bin").read_bytes() != preload:
            raise ArtifactError("selftest capture wrote the wrong preload")
        if report["provenance"]["source"]["sha256"] != _sha(source.read_bytes()):
            raise ArtifactError("selftest report did not bind the source")
        if report["provenance"]["workbench_ship"]["sha256"] != _sha(ship.read_bytes()):
            raise ArtifactError("selftest report did not bind the Workbench ship")
        if report["provenance"]["before_d81"]["sha256"] != _sha(before.read_bytes()):
            raise ArtifactError("selftest report did not bind the before D81")
        if report["provenance"]["after_d81"]["sha256"] != _sha(after.read_bytes()):
            raise ArtifactError("selftest report did not bind the after D81")
        if report["capture"]["slot_payload_sha256"] != _sha(payload):
            raise ArtifactError("selftest report did not bind the padded D81 slot")
        if report["application"]["l65m"]["sha256"] != _sha(image):
            raise ArtifactError("selftest report did not bind the canonical L65M")
        if report["provenance"]["lcc_inputs"][0]["sha256"] != _sha(lcc.read_bytes()):
            raise ArtifactError("selftest report did not bind the lcc input")
        expected_derivation = _derivation(
            capture_id=args.capture_id,
            source_sha256=_sha(source.read_bytes()),
            ship_sha256=_sha(ship.read_bytes()),
            before_sha256=_sha(before.read_bytes()),
            after_sha256=_sha(after.read_bytes()),
            slot="fasl0",
            slot_sha256=_sha(payload),
            l65m_sha256=_sha(image),
            preload_sha256=_sha(preload),
            lcc_records=report["provenance"]["lcc_inputs"],
        )
        if report["derivation"] != expected_derivation:
            raise ArtifactError("selftest report derivation chain is incomplete")
        derivation_base = {
            "capture_id": args.capture_id,
            "source_sha256": _sha(source.read_bytes()),
            "ship_sha256": _sha(ship.read_bytes()),
            "before_sha256": _sha(before.read_bytes()),
            "after_sha256": _sha(after.read_bytes()),
            "slot": "fasl0",
            "slot_sha256": _sha(payload),
            "l65m_sha256": _sha(image),
            "preload_sha256": _sha(preload),
            "lcc_records": report["provenance"]["lcc_inputs"],
        }
        derivation_mutations = (
            ("capture_id", "selftest-capture-02"),
            ("ship_sha256", "4" * 64),
            ("source_sha256", "5" * 64),
            ("slot", "fasl1"),
        )
        for key, value in derivation_mutations:
            changed = dict(derivation_base)
            changed[key] = value
            if _derivation(**changed)["sha256"] == expected_derivation["sha256"]:
                raise ArtifactError("selftest derivation does not bind %s" % key)
        changed_lcc = dict(derivation_base)
        changed_lcc["lcc_records"] = [dict(report["provenance"]["lcc_inputs"][0])]
        changed_lcc["lcc_records"][0]["sha256"] = "6" * 64
        if _derivation(**changed_lcc)["sha256"] == expected_derivation["sha256"]:
            raise ArtifactError("selftest derivation does not bind the lcc input")
        invalid_capture_id = args.capture_id
        args.capture_id = "unsafe/capture"
        _expect_failure("capture-id", "capture id", lambda: capture(args))
        args.capture_id = invalid_capture_id
        parsed = json.loads((base / "report.json").read_text())
        if parsed != report:
            raise ArtifactError("selftest report is not canonical JSON")
        shutil.copyfile(base / "runtime-app.l65m", base / "host.l65m")
        args.host_l65m = base / "host.l65m"
        args.host_preload = base / "runtime-preload.bin"
        args.require_host_equal = True
        capture(args)
        args.lcc_input = [lcc, lcc]
        _expect_failure("duplicate-lcc", "duplicate lcc input", lambda: capture(args))
        args.lcc_input = [lcc]
        mismatched_preload = base / "mismatched-preload.bin"
        mismatch = bytearray(preload)
        mismatch[0] ^= 1
        mismatched_preload.write_bytes(mismatch)
        args.host_preload = mismatched_preload
        _expect_failure(
            "required-host-diff",
            "differs from a required host comparison",
            lambda: capture(args),
        )

    print(
        "runtime-export-workbench-artifact selftest: PASS "
        "d81_blocks=33 padding=%d rebase_bytes=%d" % (padding, len(preload))
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    capture_parser = sub.add_parser("capture", help="extract and seal one Workbench FASL slot")
    capture_parser.add_argument("--capture-id", required=True)
    capture_parser.add_argument("--source", type=Path, required=True)
    capture_parser.add_argument("--ship-manifest", type=Path, required=True)
    capture_parser.add_argument("--before-d81", type=Path, required=True)
    capture_parser.add_argument("--after-d81", type=Path, required=True)
    capture_parser.add_argument("--slot", required=True)
    capture_parser.add_argument("--entry", required=True)
    capture_parser.add_argument("--arity", type=int, default=0)
    capture_parser.add_argument("--lcc-input", type=Path, action="append", required=True)
    capture_parser.add_argument("--l65m-out", type=Path, required=True)
    capture_parser.add_argument("--preload-out", type=Path, required=True)
    capture_parser.add_argument("--report-out", type=Path, required=True)
    capture_parser.add_argument("--host-l65m", type=Path)
    capture_parser.add_argument("--host-preload", type=Path)
    capture_parser.add_argument("--require-host-equal", action="store_true")
    capture_parser.add_argument("--require-d81-change", action="store_true")
    rebase_parser = sub.add_parser("rebase", help="derive the canonical Bank-5 payload")
    rebase_parser.add_argument("--l65m", type=Path, required=True)
    rebase_parser.add_argument("--out", type=Path, required=True)
    sub.add_parser("selftest", help="run synthetic D81/L65M mutation tests")
    args = parser.parse_args(argv)
    try:
        if args.command == "selftest":
            return selftest()
        if args.command == "rebase":
            image = _read(args.l65m, "Workbench L65M")
            preload = bank5_preload(image)
            _atomic_write(args.out, preload)
            print(
                "runtime-export-workbench-artifact rebase: PASS l65m=%d preload=%d sha256=%s"
                % (len(image), len(preload), _sha(preload))
            )
            return 0
        report = capture(args)
    except (ArtifactError, L65M.ContractError, ValueError, OSError, KeyError) as exc:
        print("runtime-export-workbench-artifact: FAIL: %s" % exc, file=sys.stderr)
        return 1
    print(
        "runtime-export-workbench-artifact: PASS slot=%s entries=%d l65m=%d preload=%d"
        % (
            report["application"]["slot"],
            len(report["application"]["l65m"]["entry_names"]),
            report["application"]["l65m"]["bytes"],
            report["application"]["preload"]["bytes"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
