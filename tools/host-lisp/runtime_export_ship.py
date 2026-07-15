#!/usr/bin/env python3
"""Pack and independently verify the sealed Runtime Export v2 candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "host-lisp"))

import l65m_contract as L65M  # noqa: E402
import dialect_ship_guard as DialectShipGuard  # noqa: E402
import runtime_export_contract as REC  # noqa: E402
import runtime_export_preload as PRELOAD  # noqa: E402
import runtime_export_workbench_artifact as WORKBENCH  # noqa: E402
import runtime_export_workbench_golden as GOLDEN  # noqa: E402


FORMAT = "lisp65-runtime-export-ship-v2"
STATUS = "candidate"
CRC_ALGORITHM = "crc-16-ccitt-false"
PRELOAD_ADDRESS = 0x050000
PRG_LOAD_ADDRESS = 0x2001
PRG_BINDING_MAGIC = b"L65P"
PRG_BINDING_VERSION = 1
PRG_BINDING_BYTES = 14
PACKAGE_FILES = [
    "manifest.json",
    "resolved-profile.txt",
    "runtime-app.json",
    "runtime-app.l65m",
    "runtime-preload.bin",
    "runtime.prg",
    "toolchain-report.txt",
]
ARTIFACT_ROLES = {
    "resolved-profile.txt": "resolved-profile",
    "runtime-app.json": "application-descriptor",
    "runtime-app.l65m": "application-l65m",
    "runtime-preload.bin": "bank5-preload",
    "runtime.prg": "runtime-prg",
    "toolchain-report.txt": "toolchain-report",
}
ROOT_KEYS = {
    "format", "status", "claims", "profile", "artifacts", "runtime", "gates",
    "provenance", "hardware_oracle",
}
CLAIM_KEYS = {"interactive_product", "language_semantics", "release", "runtime_export"}
PROFILE_RECORD_KEYS = {"id", "file", "sha256", "build_id"}
ARTIFACT_KEYS = {"path", "role", "size", "sha256"}
RUNTIME_KEYS = {
    "layout", "entry", "expected_result", "prg", "preload", "application",
    "native_capabilities",
}
ENTRY_KEYS = {"name", "arity", "abi"}
PRG_KEYS = {"path", "format", "load_address"}
PRELOAD_KEYS = {
    "path", "address", "length", "crc16", "crc16_algorithm", "sha256",
    "payload_length", "payload_crc16", "payload_sha256", "binding",
    "code_blob_bytes",
}
BINDING_KEYS = {"format", "trailer_offset", "trailer_length", "build_id"}
APPLICATION_KEYS = {
    "descriptor", "image", "format", "l65m_version", "entry_names", "provides",
    "requires", "library_closure",
}
GATE_KEYS = {"G0", "G1", "G2", "G4", "G5"}
G0_KEYS = {"schema", "l65m_preflight", "dependency_closure"}
G1_KEYS = {"python_vm", "native_host_vm"}
G2_KEYS = {
    "elf_surface", "budgets", "inline_overlay_audit", "package_verifier",
    "reproducibility", "prg_preload_binding",
}
G2_ELF_KEYS = {"status", "resident_overlay_control_refs"}
G2_BUDGET_KEYS = {
    "status", "prg_file_end", "boot_stack_gap", "post_boot_reserve",
    "post_boot_reserve_target", "symbol_headroom",
}
PROVENANCE_KEYS = {
    "application_emitter", "emission_receipt_sha256",
    "reemission_receipt_sha256", "python_differential_oracle",
    "contract_sha256", "closed_at_pack", "open_gaps",
}
HARDWARE_ORACLE_KEYS = {"format", "symbols", "states", "results", "preload_details"}
HARDWARE_SYMBOL_KEYS = {"name", "address", "size", "encoding"}
APP_KEYS = {
    "format", "status", "name", "suite", "entry", "exports", "provides",
    "requires", "library_closure", "native_capabilities", "expected_result",
}
APP_ENTRY_KEYS = {"name", "arity"}
PROFILE_KEYS = {
    "format", "profile", "status", "layout", "entry_abi", "runtime_entry",
    "runtime_prg_format", "runtime_prg_load_address", "application_preload",
    "runtime_preload_address", "runtime_disk_loader", "application_descriptor_format",
    "application_artifact_format", "application_bytecode_abi",
    "application_l65m_version", "application_emitter", "min_boot_stack_gap",
    "min_post_boot_reserve", "post_boot_reserve_target", "max_prg_file_end",
    "min_symbol_headroom", "g2_elf_surface", "g2_budgets",
    "g2_inline_overlay_audit", "g2_package_verifier", "g2_reproducibility",
    "contract_sha256", "app_descriptor_sha256", "suite_sha256", "config_sha256",
    "make_sha256", "inline_linker_sha256", "workbench_golden_sha256",
    "workbench_emission_receipt_sha256", "workbench_reemission_receipt_sha256",
    "workbench_ship_manifest_sha256",
}
SHA_KEYS = {
    "contract_sha256", "app_descriptor_sha256", "suite_sha256", "config_sha256",
    "make_sha256", "inline_linker_sha256", "workbench_golden_sha256",
    "workbench_emission_receipt_sha256", "workbench_reemission_receipt_sha256",
    "workbench_ship_manifest_sha256",
}


class ShipError(RuntimeError):
    pass


def preload_binding_record(payload_length: int, image_crc16: int, build_id: int) -> bytes:
    if not 0 < payload_length <= 0xFFFF:
        raise ShipError("PRG preload binding payload length is invalid")
    if not 0 <= image_crc16 <= 0xFFFF or not 0 <= build_id <= 0xFFFFFFFF:
        raise ShipError("PRG preload binding CRC/build-id is invalid")
    return (
        PRG_BINDING_MAGIC
        + bytes((PRG_BINDING_VERSION, PRG_BINDING_BYTES))
        + payload_length.to_bytes(2, "little")
        + image_crc16.to_bytes(2, "little")
        + build_id.to_bytes(4, "little")
    )


def _prg_binding_span(prg: bytes) -> tuple[int, int]:
    offsets: list[int] = []
    start = 0
    while True:
        offset = prg.find(PRG_BINDING_MAGIC, start)
        if offset < 0:
            break
        offsets.append(offset)
        start = offset + 1
    if len(offsets) != 1:
        raise ShipError("runtime PRG must contain exactly one L65P preload binding record")
    begin = offsets[0]
    end = begin + PRG_BINDING_BYTES
    if end > len(prg):
        raise ShipError("runtime PRG preload binding record is truncated")
    record = prg[begin:end]
    if record[4] != PRG_BINDING_VERSION or record[5] != PRG_BINDING_BYTES:
        raise ShipError("runtime PRG preload binding version/size mismatch")
    return begin, end


def rebind_prg(prg: bytes, payload_length: int, image_crc16: int, build_id: int) -> bytes:
    begin, end = _prg_binding_span(prg)
    return prg[:begin] + preload_binding_record(payload_length, image_crc16, build_id) + prg[end:]


def verify_prg_binding(prg: bytes, payload_length: int, image_crc16: int,
                       build_id: int) -> None:
    begin, end = _prg_binding_span(prg)
    expected = preload_binding_record(payload_length, image_crc16, build_id)
    if prg[begin:end] != expected:
        raise ShipError("runtime PRG preload binding differs from the shipped preload/profile")


def audit_prg_binding_references(elf: Path, objdump: Path) -> None:
    try:
        output = subprocess.run(
            [str(objdump), "-d", "--no-show-raw-insn", str(elf)],
            check=True, text=True, capture_output=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ShipError("cannot disassemble Runtime PRG binding references") from exc
    pattern = re.compile(
        r"<lisp65_runtime_preload_binding_record(?:\+0x([0-9a-fA-F]+))?>"
    )
    offsets = {
        0 if match.group(1) is None else int(match.group(1), 16)
        for match in pattern.finditer(output)
    }
    required = set(range(6, PRG_BINDING_BYTES))
    if not required <= offsets:
        raise ShipError(
            "Runtime code does not read every L65P payload/CRC/build-id byte: missing=%s"
            % sorted(required - offsets)
        )


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ShipError("duplicate JSON key: %s" % key)
        out[key] = value
    return out


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
    except ShipError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ShipError("cannot read %s %s: %s" % (label, path, exc)) from exc
    if not isinstance(value, dict):
        raise ShipError("%s must be an object" % label)
    return value


def _read(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ShipError("cannot read %s %s: %s" % (label, path, exc)) from exc


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ShipError("%s must be an object" % label)
    missing = sorted(keys - set(value))
    extra = sorted(set(value) - keys)
    if missing or extra:
        raise ShipError(
            "%s keys differ: missing=%s extra=%s"
            % (label, ",".join(missing) or "-", ",".join(extra) or "-")
        )
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ShipError("%s must be a non-empty string" % label)
    return value


def _integer(value: Any, label: str, low: int = 0, high: int | None = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < low:
        raise ShipError("%s must be an integer >= %d" % (label, low))
    if high is not None and value > high:
        raise ShipError("%s must be an integer <= %d" % (label, high))
    return value


def _fixnum_raw(value: Any) -> int:
    text = _text(value, "expected result")
    try:
        number = int(text, 10)
    except ValueError as exc:
        raise ShipError("Runtime Export v2 expected result must be an integer") from exc
    if number < -16384 or number > 16383:
        raise ShipError("Runtime Export v2 expected result exceeds the 15-bit fixnum range")
    return ((number & 0xffff) << 1 | 1) & 0xffff


def _strings(value: Any, label: str, *, nonempty: bool = True) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        raise ShipError("%s must be %sa list" % (label, "a non-empty " if nonempty else ""))
    out = [_text(item, "%s[%d]" % (label, index)) for index, item in enumerate(value)]
    if len(out) != len(set(out)):
        raise ShipError("%s contains duplicates" % label)
    return out


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha(_read(path, "artifact"))


def _is_sha(value: Any, label: str) -> str:
    text = _text(value, label)
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise ShipError("%s must be a lowercase SHA-256" % label)
    return text


def crc16_ccitt_false(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def _u16(data: bytes, at: int, label: str) -> int:
    if at < 0 or at + 2 > len(data):
        raise ShipError("%s is truncated" % label)
    return data[at] | (data[at + 1] << 8)


def _parse_l65m(image: bytes) -> tuple[L65M.Summary, bytes, dict[str, tuple[int, int, int]]]:
    try:
        summary = L65M.validate_image(image)
    except L65M.ContractError as exc:
        raise ShipError("application L65M failed preflight: %s" % exc) from exc
    blob_len = _u16(image, 0, "L65M prefix")
    metadata = image[4 + blob_len :]
    entry_count = _u16(metadata, 16, "L65M entry count")
    entries_off = _u16(metadata, 24, "L65M entry table")
    strings_off = _u16(metadata, 32, "L65M string pool")
    strings_bytes = _u16(metadata, 34, "L65M string pool length")
    strings = metadata[strings_off : strings_off + strings_bytes]
    entries: dict[str, tuple[int, int, int]] = {}
    for index in range(entry_count):
        at = entries_off + index * 8
        name_off = _u16(metadata, at, "L65M entry")
        flags = metadata[at + 3]
        offset = _u16(metadata, at + 4, "L65M entry offset")
        length = _u16(metadata, at + 6, "L65M entry length")
        end = strings.find(b"\x00", name_off)
        if end < 0:
            raise ShipError("L65M entry string is unterminated after preflight")
        name = strings[name_off:end].decode("utf-8")
        entries[name] = (offset, length, flags)
    return summary, image[4 : 4 + blob_len], entries


def _entry_arity(image: bytes, entries: dict[str, tuple[int, int, int]], name: str) -> int:
    if name not in entries:
        raise ShipError("application L65M is missing runtime entry %s" % name)
    blob_len = _u16(image, 0, "L65M prefix")
    offset, length, _flags = entries[name]
    if offset + 2 > blob_len or length < 2:
        raise ShipError("application runtime entry is truncated")
    return image[4 + offset + 1]


def _parse_profile(path: Path) -> tuple[dict[str, str], bytes]:
    data = _read(path, "resolved profile")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ShipError("resolved profile is not UTF-8") from exc
    fields: dict[str, str] = {}
    for number, line in enumerate(text.splitlines(), 1):
        if not line or "=" not in line:
            raise ShipError("resolved profile line %d is not key=value" % number)
        key, value = line.split("=", 1)
        if not key or not value or key in fields:
            raise ShipError("resolved profile line %d has an empty/duplicate field" % number)
        fields[key] = value
    _exact(fields, PROFILE_KEYS, "resolved profile")
    for key in SHA_KEYS:
        _is_sha(fields[key], "resolved profile.%s" % key)
    expected = {
        "format": "lisp65-runtime-export-resolved-profile-v2",
        "status": STATUS,
        "layout": "inline-boot-overlay",
        "entry_abi": "named-zero-argument-p0",
        "runtime_prg_format": "mega65-prg",
        "runtime_prg_load_address": "0x2001",
        "application_preload": "bank5-build-bound",
        "runtime_preload_address": "0x050000",
        "runtime_disk_loader": "false",
        "application_descriptor_format": "lisp65-runtime-app-v1",
        "application_artifact_format": "lisp65-bytecode-p0-disk-lib-artifacts-v1",
        "application_bytecode_abi": "P0",
        "application_l65m_version": "1",
        "application_emitter": "workbench-lcc-fasl-v1",
        "g2_elf_surface": "passed-by-inline-overlay-audit",
        "g2_budgets": "passed-by-inline-overlay-audit",
        "g2_inline_overlay_audit": "passed",
        "g2_package_verifier": "required-post-pack",
        "g2_reproducibility": "required-post-pack",
    }
    for key, value in expected.items():
        if fields[key] != value:
            raise ShipError("resolved profile %s must be %s" % (key, value))
    for key in (
        "min_boot_stack_gap", "min_post_boot_reserve", "post_boot_reserve_target",
        "max_prg_file_end", "min_symbol_headroom",
    ):
        try:
            number = int(fields[key], 0)
        except ValueError as exc:
            raise ShipError("resolved profile %s is not an integer" % key) from exc
        if number <= 0:
            raise ShipError("resolved profile %s must be positive" % key)
    return fields, data


def _parse_report(path: Path, label: str) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ShipError("cannot read %s: %s" % (label, exc)) from exc
    fields: dict[str, str] = {}
    for line in lines:
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in fields:
            continue
        fields[key] = value
    if fields.get("status") != "ok":
        raise ShipError("%s does not record status=ok" % label)
    return fields


def _audit_elf_surface(elf: Path, nm: Path, forbidden: list[str]) -> None:
    try:
        result = subprocess.run(
            [str(nm), "--defined-only", str(elf)], check=True, capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ShipError("cannot inspect Runtime Export ELF surface: %s" % exc) from exc
    symbols = {
        fields[-1]
        for line in result.stdout.splitlines()
        if len(fields := line.split()) >= 2
    }
    leaked = sorted(symbols & set(forbidden))
    if leaked:
        raise ShipError("Runtime Export ELF contains forbidden symbols: %s" % ", ".join(leaked))
    missing = sorted({"main", "vm_run_dir", "vm_load_embedded_stdlib"} - symbols)
    if missing:
        raise ShipError("Runtime Export ELF is missing required symbols: %s" % ", ".join(missing))


def _hardware_symbols(elf: Path, nm: Path) -> dict[str, dict[str, Any]]:
    wanted = {
        "lisp65_runtime_state": ("state", 1, "u8"),
        "lisp65_runtime_result": ("result", 2, "obj16-le"),
        "lisp65_runtime_preload_detail": ("preload_detail", 1, "u8"),
    }
    try:
        result = subprocess.run(
            [str(nm), "--defined-only", "--print-size", str(elf)], check=True,
            capture_output=True, text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ShipError("cannot resolve Runtime Export hardware oracle: %s" % exc) from exc
    found: dict[str, dict[str, Any]] = {}
    spans: list[tuple[int, int, str]] = []
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) < 4 or fields[-1] not in wanted:
            continue
        name = fields[-1]
        key, expected_size, encoding = wanted[name]
        if key in found:
            raise ShipError("duplicate Runtime Export hardware symbol: %s" % name)
        try:
            address = int(fields[0], 16)
            size = int(fields[1], 16)
        except ValueError as exc:
            raise ShipError("malformed Runtime Export hardware symbol: %s" % name) from exc
        if size != expected_size or address + size > 0x10000:
            raise ShipError("invalid Runtime Export hardware symbol span: %s" % name)
        found[key] = {
            "name": name, "address": address, "size": size, "encoding": encoding,
        }
        spans.append((address, address + size, name))
    if set(found) != {"state", "result", "preload_detail"}:
        raise ShipError("Runtime Export ELF lacks the complete hardware oracle")
    for index, left in enumerate(spans):
        for right in spans[index + 1:]:
            if max(left[0], right[0]) < min(left[1], right[1]):
                raise ShipError("Runtime Export hardware symbols overlap")
    return found


def _strict_app(app: dict[str, Any]) -> dict[str, Any]:
    _exact(app, APP_KEYS, "runtime-app.json")
    if app["format"] != "lisp65-runtime-app-v1" or app["status"] != STATUS:
        raise ShipError("runtime app must be a v1 candidate")
    _text(app["name"], "runtime app name")
    _text(app["suite"], "runtime app suite")
    entry = _exact(app["entry"], APP_ENTRY_KEYS, "runtime app entry")
    name = _text(entry["name"], "runtime app entry.name")
    if _integer(entry["arity"], "runtime app entry.arity") != 0:
        raise ShipError("runtime app entry arity must be zero")
    exports = _strings(app["exports"], "runtime app exports")
    if name not in exports:
        raise ShipError("runtime app entry must be exported")
    provides = _strings(app["provides"], "runtime app provides")
    requires = _strings(app["requires"], "runtime app requires")
    if "core" not in requires or set(provides) & set(requires):
        raise ShipError("runtime app dependency closure is invalid")
    _strings(app["library_closure"], "runtime app library_closure", nonempty=False)
    _strings(app["native_capabilities"], "runtime app native_capabilities")
    _text(app["expected_result"], "runtime app expected_result")
    return app


def _manifest_artifacts(paths: dict[str, Path]) -> list[dict[str, Any]]:
    records = []
    for name in PACKAGE_FILES[1:]:
        data = _read(paths[name], name)
        records.append({
            "path": name,
            "role": ARTIFACT_ROLES[name],
            "size": len(data),
            "sha256": _sha(data),
        })
    return records


def _manifest(
    *, paths: dict[str, Path], profile: dict[str, str], profile_data: bytes,
    app: dict[str, Any], image: bytes, summary: L65M.Summary, blob: bytes,
    audit: dict[str, str], footprint: dict[str, str], contract_sha256: str,
    hardware_symbols: dict[str, dict[str, Any]], emission_receipt_sha256: str,
    reemission_receipt_sha256: str,
) -> dict[str, Any]:
    preload = _read(paths["runtime-preload.bin"], "runtime preload")
    preload_payload, preload_build_id = PRELOAD.parse(preload)
    prg = _read(paths["runtime.prg"], "runtime PRG")
    profile_sha = _sha(profile_data)
    build_id = int(profile_sha[:8], 16)
    if preload_build_id != build_id:
        raise ShipError("runtime preload trailer build id differs from profile")
    verify_prg_binding(
        prg, len(preload_payload), crc16_ccitt_false(preload), build_id
    )
    return {
        "format": FORMAT,
        "status": STATUS,
        "claims": {
            "interactive_product": False,
            "language_semantics": False,
            "release": False,
            "runtime_export": True,
        },
        "profile": {
            "id": profile["profile"],
            "file": "resolved-profile.txt",
            "sha256": profile_sha,
            "build_id": build_id,
        },
        "artifacts": _manifest_artifacts(paths),
        "runtime": {
            "layout": "inline-boot-overlay",
            "entry": {
                "name": app["entry"]["name"],
                "arity": app["entry"]["arity"],
                "abi": "named-zero-argument-p0",
            },
            "expected_result": app["expected_result"],
            "prg": {
                "path": "runtime.prg",
                "format": "mega65-prg",
                "load_address": PRG_LOAD_ADDRESS,
            },
            "preload": {
                "path": "runtime-preload.bin",
                "address": PRELOAD_ADDRESS,
                "length": len(preload),
                "crc16": crc16_ccitt_false(preload),
                "crc16_algorithm": CRC_ALGORITHM,
                "sha256": _sha(preload),
                "payload_length": len(preload_payload),
                "payload_crc16": crc16_ccitt_false(preload_payload),
                "payload_sha256": _sha(preload_payload),
                "binding": {
                    "format": "lisp65-runtime-preload-binding-v1",
                    "trailer_offset": len(preload_payload),
                    "trailer_length": PRELOAD.TRAILER_BYTES,
                    "build_id": preload_build_id,
                },
                "code_blob_bytes": len(blob),
            },
            "application": {
                "descriptor": "runtime-app.json",
                "image": "runtime-app.l65m",
                "format": "lisp65-bytecode-p0-disk-lib-image-v1",
                "l65m_version": 1,
                "entry_names": summary.entry_names,
                "provides": app["provides"],
                "requires": app["requires"],
                "library_closure": app["library_closure"],
            },
            "native_capabilities": app["native_capabilities"],
        },
        "gates": {
            "G0": {
                "schema": "passed-at-pack",
                "l65m_preflight": "passed-at-pack",
                "dependency_closure": "passed-at-pack",
            },
            "G1": {
                "python_vm": "passed-at-artifact-build",
                "native_host_vm": "not-run-by-packer",
            },
            "G2": {
                "elf_surface": {
                    "status": "passed",
                    "resident_overlay_control_refs": int(audit["resident_overlay_control_refs"], 0),
                },
                "budgets": {
                    "status": "passed",
                    "prg_file_end": int(audit["prg_file_end"], 0),
                    "boot_stack_gap": int(audit["boot_stack_gap"], 0),
                    "post_boot_reserve": int(audit["post_boot_reserve"], 0),
                    "post_boot_reserve_target": int(profile["post_boot_reserve_target"], 0),
                    "symbol_headroom": int(footprint["boot_sym_headroom"], 0),
                },
                "inline_overlay_audit": "passed",
                "prg_preload_binding": "passed-at-pack",
                "package_verifier": "required-post-pack",
                "reproducibility": "required-post-pack",
            },
            "G4": {"deploy_dry_run": "required-post-pack"},
            "G5": {"cold_boot_hardware": "not-run", "preload_corruption": "not-run"},
        },
        "hardware_oracle": {
            "format": "lisp65-runtime-export-hardware-oracle-v1",
            "symbols": hardware_symbols,
            "states": {"complete": 3, "preload_error": 0xe4},
            "results": {"success_raw": _fixnum_raw(app["expected_result"]), "error_nil_raw": 0},
            "preload_details": {"ok": 0, "length": 1, "build_id": 2, "crc": 3},
        },
        "provenance": {
            "application_emitter": "workbench-lcc-fasl-v1",
            "emission_receipt_sha256": emission_receipt_sha256,
            "reemission_receipt_sha256": reemission_receipt_sha256,
            "python_differential_oracle": "reported-not-authoritative",
            "contract_sha256": contract_sha256,
            "closed_at_pack": ["workbench-emitter-provenance", "runtime-export-ship-packer"],
            "open_gaps": ["cold-boot-hardware"],
        },
    }


def _validate_source_identity(
    image: bytes, blob: bytes, entries: dict[str, tuple[int, int, int]], preload: bytes,
    app_manifest: dict[str, Any], preload_manifest: dict[str, Any], app: dict[str, Any],
) -> None:
    try:
        expected_preload = WORKBENCH.bank5_preload(image)
    except WORKBENCH.ArtifactError as exc:
        raise ShipError("cannot derive Bank-5 preload from Workbench L65M: %s" % exc) from exc
    if preload != expected_preload:
        raise ShipError("runtime preload is not the reversible Bank-5 rebase of the Workbench L65M")
    app_entries = app_manifest.get("entries")
    preload_entries = preload_manifest.get("entries")
    if not isinstance(app_entries, list) or not isinstance(preload_entries, list):
        raise ShipError("Python differential-oracle manifests need entry lists")

    def identity(items: list[Any], label: str) -> list[tuple[Any, ...]]:
        result = []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise ShipError("%s entry %d is not an object" % (label, index))
            result.append((item.get("name"), item.get("kind")))
        return result

    app_identity = identity(app_entries, "application manifest")
    preload_identity = identity(preload_entries, "preload manifest")
    if app_identity != preload_identity:
        raise ShipError("Python disk/preload differential oracles expose different entries")
    if [item[0] for item in app_identity] != list(entries):
        raise ShipError("Python differential oracle and Workbench L65M entry sets differ")
    if app_manifest.get("artifact_role") != "disk-lib":
        raise ShipError("application manifest role must be disk-lib")
    if preload_manifest.get("artifact_role") != "stdlib":
        raise ShipError("preload manifest role must be stdlib")
    if preload_manifest.get("base_addr") != "0x050000":
        raise ShipError("Python preload oracle base address must be 0x050000")
    if app_manifest.get("name") != app["name"]:
        raise ShipError("application manifest identity differs from descriptor")
    if app_manifest.get("provides") != app["provides"] or app_manifest.get("requires") != app["requires"]:
        raise ShipError("application manifest dependency metadata differs from descriptor")
    if app_manifest.get("code_bytes") != len(blob) or preload_manifest.get("code_bytes") != len(blob):
        raise ShipError("Python differential-oracle code length differs from Workbench L65M")
    if _entry_arity(image, entries, app["entry"]["name"]) != app["entry"]["arity"]:
        raise ShipError("application L65M entry arity differs from descriptor")


def pack(args: argparse.Namespace) -> int:
    contract = _load_json(args.contract, "runtime export contract")
    try:
        contract_app, _suite = REC.validate(contract)
    except REC.ContractError as exc:
        raise ShipError("runtime export contract failed: %s" % exc) from exc
    app = _strict_app(_load_json(args.app, "runtime app descriptor"))
    if app != contract_app:
        raise ShipError("pack application differs from contract application")
    profile, profile_data = _parse_profile(args.profile)
    if profile["profile"] != contract["profile"]["id"] or profile["runtime_entry"] != app["entry"]["name"]:
        raise ShipError("resolved profile identity/entry differs from contract")
    if profile["contract_sha256"] != _sha_file(args.contract):
        raise ShipError("resolved profile contract hash differs from input")
    if profile["app_descriptor_sha256"] != _sha_file(args.app):
        raise ShipError("resolved profile app hash differs from input")
    profile_sources = {
        "suite_sha256": ROOT / app["suite"],
        "config_sha256": ROOT / "config/runtime-core.mk",
        "make_sha256": ROOT / "mk/runtime-core.mk",
        "inline_linker_sha256": ROOT / "scripts/lisp65-mega65-runtime-core-inline-overlay.ld",
    }
    for key, source in profile_sources.items():
        if profile[key] != _sha_file(source):
            raise ShipError("resolved profile %s differs from current input" % key)

    image = _read(args.app_image, "application L65M")
    summary, blob, entries = _parse_l65m(image)
    try:
        same_receipt = os.path.samefile(
            args.workbench_emission_receipt, args.workbench_reemission_receipt
        )
    except OSError:
        same_receipt = (
            args.workbench_emission_receipt.resolve()
            == args.workbench_reemission_receipt.resolve()
        )
    if same_receipt:
        raise ShipError("Workbench emission and re-emission receipts must be distinct files")
    try:
        emission_receipt = GOLDEN.parse_receipt(
            _read(args.workbench_emission_receipt, "Workbench emission receipt"),
            "Workbench emission receipt",
        )
        reemission_receipt = GOLDEN.parse_receipt(
            _read(args.workbench_reemission_receipt, "Workbench re-emission receipt"),
            "Workbench re-emission receipt",
        )
        GOLDEN.reconstruct_derivation(emission_receipt, "Workbench emission receipt")
        GOLDEN.reconstruct_derivation(reemission_receipt, "Workbench re-emission receipt")
    except GOLDEN.GoldenError as exc:
        raise ShipError("Workbench receipt contract failed: %s" % exc) from exc
    if emission_receipt["capture"]["capture_id"] == reemission_receipt["capture"]["capture_id"]:
        raise ShipError("Workbench emission and re-emission capture ids must be distinct")
    expected_workbench_hashes = {
        "workbench_golden_sha256": _sha(image),
        "workbench_emission_receipt_sha256": _sha_file(args.workbench_emission_receipt),
        "workbench_reemission_receipt_sha256": _sha_file(args.workbench_reemission_receipt),
        "workbench_ship_manifest_sha256": _sha_file(args.workbench_ship_manifest),
    }
    for key, value in expected_workbench_hashes.items():
        if profile[key] != value:
            raise ShipError("resolved profile %s differs from Workbench provenance" % key)
    for label, receipt in (("emission", emission_receipt), ("re-emission", reemission_receipt)):
        if (receipt.get("format") != WORKBENCH.FORMAT or receipt.get("status") != "passed"
                or receipt.get("emitter") != WORKBENCH.EMITTER):
            raise ShipError("Workbench %s receipt identity is invalid" % label)
        application = receipt.get("application")
        l65m_record = application.get("l65m") if isinstance(application, dict) else None
        if not isinstance(l65m_record, dict) or l65m_record.get("sha256") != _sha(image):
            raise ShipError("Workbench %s receipt is bound to another L65M" % label)
    comparisons = reemission_receipt.get("comparisons")
    if (not isinstance(comparisons, dict)
            or not isinstance(comparisons.get("host_l65m"), dict)
            or not comparisons["host_l65m"].get("equal")):
        raise ShipError("Workbench re-emission receipt lacks the byte-exact Golden diff")
    preload = _read(args.preload, "runtime preload")
    try:
        preload_payload, preload_build_id = PRELOAD.parse(preload)
    except PRELOAD.PreloadError as exc:
        raise ShipError("runtime preload binding failed: %s" % exc) from exc
    if preload_build_id != int(_sha(profile_data)[:8], 16):
        raise ShipError("runtime preload build id differs from resolved profile")
    _validate_source_identity(
        image, blob, entries, preload_payload,
        _load_json(args.app_manifest, "application artifact manifest"),
        _load_json(args.preload_manifest, "preload artifact manifest"), app,
    )
    prg = _read(args.prg, "runtime PRG")
    if len(prg) < 2 or _u16(prg, 0, "runtime PRG") != PRG_LOAD_ADDRESS:
        raise ShipError("runtime PRG load address must be 0x2001")
    audit = _parse_report(args.audit_report, "inline overlay audit")
    footprint = _parse_report(args.footprint_report, "inline overlay footprint")
    _audit_elf_surface(args.elf, args.nm, contract["capabilities"]["forbidden_native_symbols"])
    hardware_symbols = _hardware_symbols(args.elf, args.nm)
    audit_prg_binding_references(args.elf, args.objdump)
    if int(audit.get("prg_bytes", "-1"), 0) != len(prg):
        raise ShipError("inline overlay audit PRG size differs from payload")
    if int(footprint.get("prg_bytes", "-1"), 0) != len(prg):
        raise ShipError("inline overlay footprint PRG size differs from payload")
    if int(audit["boot_stack_gap"], 0) < int(profile["min_boot_stack_gap"], 0):
        raise ShipError("inline overlay boot stack gap is below profile minimum")
    if int(audit["post_boot_reserve"], 0) < int(profile["post_boot_reserve_target"], 0):
        raise ShipError("inline overlay misses the profile reserve target")
    if int(footprint["boot_sym_headroom"], 0) < int(profile["min_symbol_headroom"], 0):
        raise ShipError("inline overlay symbol headroom is below profile minimum")

    out_dir = args.out_dir.resolve()
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="runtime-export-", dir=out_dir.parent) as raw_tmp:
        tmp = Path(raw_tmp)
        sources = {
            "resolved-profile.txt": args.profile,
            "runtime-app.json": args.app,
            "runtime-app.l65m": args.app_image,
            "runtime-preload.bin": args.preload,
            "runtime.prg": args.prg,
            "toolchain-report.txt": args.toolchain_report,
        }
        for name, source in sources.items():
            shutil.copyfile(source, tmp / name)
        toolchain = _read(tmp / "toolchain-report.txt", "toolchain report")
        if not toolchain.startswith(b"format=lisp65-runtime-export-toolchain-report-v1\n"):
            raise ShipError("toolchain report format mismatch")
        paths = {name: tmp / name for name in PACKAGE_FILES[1:]}
        manifest = _manifest(
            paths=paths, profile=profile, profile_data=profile_data, app=app,
            image=image, summary=summary, blob=blob, audit=audit, footprint=footprint,
            contract_sha256=_sha_file(args.contract),
            hardware_symbols=hardware_symbols,
            emission_receipt_sha256=_sha_file(args.workbench_emission_receipt),
            reemission_receipt_sha256=_sha_file(args.workbench_reemission_receipt),
        )
        (tmp / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        verify(tmp)
        if out_dir.exists():
            if out_dir.is_symlink() or not out_dir.is_dir():
                raise ShipError("output path exists and is not a directory")
            shutil.rmtree(out_dir)
        shutil.copytree(tmp, out_dir)
    print(
        "runtime-export-ship pack: PASS dir=%s files=%d entries=%d build_id=0x%08x"
        % (out_dir, len(PACKAGE_FILES), len(summary.entry_names), int(_sha(profile_data)[:8], 16))
    )
    return 0


def _artifact_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records = manifest["artifacts"]
    if not isinstance(records, list) or len(records) != len(PACKAGE_FILES) - 1:
        raise ShipError("manifest artifacts must cover the six non-manifest files")
    result: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records):
        record = _exact(record, ARTIFACT_KEYS, "artifact[%d]" % index)
        path = _text(record["path"], "artifact.path")
        if path in result:
            raise ShipError("duplicate artifact path: %s" % path)
        if path not in ARTIFACT_ROLES or record["role"] != ARTIFACT_ROLES[path]:
            raise ShipError("artifact path/role differs from the v1 package")
        _integer(record["size"], "artifact.size", 1)
        _is_sha(record["sha256"], "artifact.sha256")
        result[path] = record
    if list(result) != PACKAGE_FILES[1:]:
        raise ShipError("artifact order/file set differs from Runtime Export v1")
    return result


def verify(package_dir: Path) -> int:
    try:
        members = sorted(item.name for item in package_dir.iterdir())
    except OSError as exc:
        raise ShipError("cannot list package directory: %s" % exc) from exc
    if members != sorted(PACKAGE_FILES):
        raise ShipError("package file set differs: expected=%s actual=%s" % (PACKAGE_FILES, members))
    for name in PACKAGE_FILES:
        path = package_dir / name
        if path.is_symlink() or not path.is_file():
            raise ShipError("package member must be a regular non-symlink file: %s" % name)

    manifest = _exact(_load_json(package_dir / "manifest.json", "ship manifest"), ROOT_KEYS, "manifest")
    if manifest["format"] != FORMAT or manifest["status"] != STATUS:
        raise ShipError("manifest format/status must describe the v2 candidate")
    claims = _exact(manifest["claims"], CLAIM_KEYS, "manifest.claims")
    if claims != {
        "interactive_product": False, "language_semantics": False,
        "release": False, "runtime_export": True,
    }:
        raise ShipError("manifest claims exceed the Runtime Export boundary")

    resolved_profile_data = _read(package_dir / "resolved-profile.txt", "resolved profile")
    try:
        DialectShipGuard.enforce(
            resolved_profile=resolved_profile_data,
            metadata=manifest,
        )
    except DialectShipGuard.DialectShipError as exc:
        raise ShipError(str(exc)) from exc

    artifacts = _artifact_map(manifest)
    for name, record in artifacts.items():
        data = _read(package_dir / name, name)
        if len(data) != record["size"] or _sha(data) != record["sha256"]:
            raise ShipError("artifact size/hash mismatch: %s" % name)

    profile_record = _exact(manifest["profile"], PROFILE_RECORD_KEYS, "manifest.profile")
    profile, profile_data = _parse_profile(package_dir / "resolved-profile.txt")
    profile_sha = _sha(profile_data)
    if profile_record != {
        "id": profile["profile"], "file": "resolved-profile.txt", "sha256": profile_sha,
        "build_id": int(profile_sha[:8], 16),
    }:
        raise ShipError("manifest profile/build-id binding is invalid")

    app_data = _read(package_dir / "runtime-app.json", "runtime app descriptor")
    app = _strict_app(_load_json(package_dir / "runtime-app.json", "runtime app descriptor"))
    if profile["app_descriptor_sha256"] != _sha(app_data):
        raise ShipError("resolved profile app descriptor hash is invalid")
    image = _read(package_dir / "runtime-app.l65m", "application L65M")
    summary, blob, entries = _parse_l65m(image)
    entry_name = app["entry"]["name"]
    if _entry_arity(image, entries, entry_name) != 0:
        raise ShipError("shipped runtime entry is not zero-argument P0 bytecode")

    runtime = _exact(manifest["runtime"], RUNTIME_KEYS, "manifest.runtime")
    if runtime["layout"] != "inline-boot-overlay" or runtime["expected_result"] != app["expected_result"]:
        raise ShipError("runtime layout/result differs from shipped app")
    entry = _exact(runtime["entry"], ENTRY_KEYS, "manifest.runtime.entry")
    if entry != {"name": entry_name, "arity": 0, "abi": "named-zero-argument-p0"}:
        raise ShipError("runtime entry binding differs from shipped app")
    prg_record = _exact(runtime["prg"], PRG_KEYS, "manifest.runtime.prg")
    if prg_record != {"path": "runtime.prg", "format": "mega65-prg", "load_address": PRG_LOAD_ADDRESS}:
        raise ShipError("runtime PRG contract mismatch")
    prg = _read(package_dir / "runtime.prg", "runtime PRG")
    if len(prg) < 2 or _u16(prg, 0, "runtime PRG") != PRG_LOAD_ADDRESS:
        raise ShipError("runtime PRG payload has the wrong load address")

    preload_record = _exact(runtime["preload"], PRELOAD_KEYS, "manifest.runtime.preload")
    preload = _read(package_dir / "runtime-preload.bin", "runtime preload")
    try:
        preload_payload, preload_build_id = PRELOAD.parse(preload)
    except PRELOAD.PreloadError as exc:
        raise ShipError("runtime preload binding failed: %s" % exc) from exc
    if preload_build_id != profile_record["build_id"]:
        raise ShipError("runtime preload trailer build id differs from profile")
    expected_preload = {
        "path": "runtime-preload.bin", "address": PRELOAD_ADDRESS, "length": len(preload),
        "crc16": crc16_ccitt_false(preload), "crc16_algorithm": CRC_ALGORITHM,
        "sha256": _sha(preload),
        "payload_length": len(preload_payload),
        "payload_crc16": crc16_ccitt_false(preload_payload),
        "payload_sha256": _sha(preload_payload),
        "binding": {
            "format": "lisp65-runtime-preload-binding-v1",
            "trailer_offset": len(preload_payload),
            "trailer_length": PRELOAD.TRAILER_BYTES,
            "build_id": preload_build_id,
        },
        "code_blob_bytes": len(blob),
    }
    if preload_record != expected_preload:
        raise ShipError("runtime preload length/hash/CRC/address binding is invalid")
    verify_prg_binding(
        prg, len(preload_payload), crc16_ccitt_false(preload), preload_build_id
    )
    try:
        expected_rebase = WORKBENCH.bank5_preload(image)
    except WORKBENCH.ArtifactError as exc:
        raise ShipError("shipped Workbench L65M cannot be rebased: %s" % exc) from exc
    if preload_payload != expected_rebase:
        raise ShipError("shipped preload is not the Workbench L65M Bank-5 rebase")
    application = _exact(runtime["application"], APPLICATION_KEYS, "manifest.runtime.application")
    expected_application = {
        "descriptor": "runtime-app.json", "image": "runtime-app.l65m",
        "format": "lisp65-bytecode-p0-disk-lib-image-v1", "l65m_version": 1,
        "entry_names": summary.entry_names, "provides": app["provides"],
        "requires": app["requires"], "library_closure": app["library_closure"],
    }
    if application != expected_application:
        raise ShipError("runtime application binding differs from descriptor/L65M")
    if runtime["native_capabilities"] != app["native_capabilities"]:
        raise ShipError("runtime capabilities differ from shipped app")

    gates = _exact(manifest["gates"], GATE_KEYS, "manifest.gates")
    g0 = _exact(gates["G0"], G0_KEYS, "manifest.gates.G0")
    if set(g0.values()) != {"passed-at-pack"}:
        raise ShipError("G0 pack results must all be passed-at-pack")
    g1 = _exact(gates["G1"], G1_KEYS, "manifest.gates.G1")
    if g1 != {"python_vm": "passed-at-artifact-build", "native_host_vm": "not-run-by-packer"}:
        raise ShipError("G1 status is not fail-honest")
    g2 = _exact(gates["G2"], G2_KEYS, "manifest.gates.G2")
    elf = _exact(g2["elf_surface"], G2_ELF_KEYS, "manifest.gates.G2.elf_surface")
    budgets = _exact(g2["budgets"], G2_BUDGET_KEYS, "manifest.gates.G2.budgets")
    if elf["status"] != "passed" or _integer(elf["resident_overlay_control_refs"], "refs") < 1:
        raise ShipError("G2 ELF-surface evidence is invalid")
    if budgets["status"] != "passed":
        raise ShipError("G2 budget status is not passed")
    if _integer(budgets["prg_file_end"], "prg_file_end") != PRG_LOAD_ADDRESS + len(prg) - 2:
        raise ShipError("G2 PRG file-end evidence differs from payload")
    numeric_profile = {key: int(profile[key], 0) for key in (
        "min_boot_stack_gap", "post_boot_reserve_target", "max_prg_file_end",
        "min_symbol_headroom",
    )}
    if _integer(budgets["boot_stack_gap"], "boot_stack_gap") < numeric_profile["min_boot_stack_gap"]:
        raise ShipError("G2 boot stack gap misses profile budget")
    if _integer(budgets["post_boot_reserve"], "post_boot_reserve") < numeric_profile["post_boot_reserve_target"]:
        raise ShipError("G2 post-boot reserve misses profile target")
    if budgets["post_boot_reserve_target"] != numeric_profile["post_boot_reserve_target"]:
        raise ShipError("G2 reserve target differs from profile")
    if _integer(budgets["symbol_headroom"], "symbol_headroom") < numeric_profile["min_symbol_headroom"]:
        raise ShipError("G2 symbol headroom misses profile budget")
    if budgets["prg_file_end"] > numeric_profile["max_prg_file_end"]:
        raise ShipError("G2 PRG file end exceeds profile limit")
    if {key: g2[key] for key in (
        "inline_overlay_audit", "prg_preload_binding", "package_verifier", "reproducibility"
    )} != {
        "inline_overlay_audit": "passed", "package_verifier": "required-post-pack",
        "prg_preload_binding": "passed-at-pack", "reproducibility": "required-post-pack",
    }:
        raise ShipError("G2 status is not fail-honest")
    if gates["G4"] != {"deploy_dry_run": "required-post-pack"}:
        raise ShipError("G4 status is not fail-honest")
    if gates["G5"] != {"cold_boot_hardware": "not-run", "preload_corruption": "not-run"}:
        raise ShipError("G5 status is not fail-honest")

    hardware = _exact(manifest["hardware_oracle"], HARDWARE_ORACLE_KEYS, "manifest.hardware_oracle")
    if hardware["format"] != "lisp65-runtime-export-hardware-oracle-v1":
        raise ShipError("hardware oracle format mismatch")
    symbols = _exact(hardware["symbols"], {"state", "result", "preload_detail"}, "hardware symbols")
    for key, name, size, encoding in (
        ("state", "lisp65_runtime_state", 1, "u8"),
        ("result", "lisp65_runtime_result", 2, "obj16-le"),
        ("preload_detail", "lisp65_runtime_preload_detail", 1, "u8"),
    ):
        record = _exact(symbols[key], HARDWARE_SYMBOL_KEYS, "hardware symbol %s" % key)
        if (record["name"], record["size"], record["encoding"]) != (name, size, encoding):
            raise ShipError("hardware symbol contract mismatch: %s" % key)
        _integer(record["address"], "hardware symbol address", 0, 0xffff - size + 1)
    if hardware["states"] != {"complete": 3, "preload_error": 0xe4}:
        raise ShipError("hardware state oracle mismatch")
    if hardware["results"] != {"success_raw": _fixnum_raw(app["expected_result"]), "error_nil_raw": 0}:
        raise ShipError("hardware result oracle mismatch")
    if hardware["preload_details"] != {"ok": 0, "length": 1, "build_id": 2, "crc": 3}:
        raise ShipError("hardware preload-detail oracle mismatch")

    provenance = _exact(manifest["provenance"], PROVENANCE_KEYS, "manifest.provenance")
    _is_sha(provenance["contract_sha256"], "provenance.contract_sha256")
    if profile["contract_sha256"] != provenance["contract_sha256"]:
        raise ShipError("profile/manifest contract hashes differ")
    _is_sha(provenance["emission_receipt_sha256"], "provenance.emission_receipt_sha256")
    _is_sha(provenance["reemission_receipt_sha256"], "provenance.reemission_receipt_sha256")
    if (provenance["emission_receipt_sha256"] != profile["workbench_emission_receipt_sha256"]
            or provenance["reemission_receipt_sha256"] != profile["workbench_reemission_receipt_sha256"]
            or profile["workbench_golden_sha256"] != _sha(image)):
        raise ShipError("manifest/profile Workbench provenance binding differs")
    if provenance != {
        "application_emitter": "workbench-lcc-fasl-v1",
        "emission_receipt_sha256": provenance["emission_receipt_sha256"],
        "reemission_receipt_sha256": provenance["reemission_receipt_sha256"],
        "python_differential_oracle": "reported-not-authoritative",
        "contract_sha256": provenance["contract_sha256"],
        "closed_at_pack": ["workbench-emitter-provenance", "runtime-export-ship-packer"],
        "open_gaps": ["cold-boot-hardware"],
    }:
        raise ShipError("runtime export provenance/gap record differs from candidate contract")
    print(
        "runtime-export-ship verify: PASS dir=%s files=%d entries=%d build_id=0x%08x"
        % (package_dir, len(PACKAGE_FILES), len(summary.entry_names), profile_record["build_id"])
    )
    return 0


def _rewrite_manifest(package: Path, mutate: Any) -> None:
    path = package / "manifest.json"
    manifest = _load_json(path, "selftest manifest")
    mutate(manifest)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _refresh_artifact_record(package: Path, name: str) -> None:
    data = _read(package / name, "selftest artifact")

    def refresh(manifest: dict[str, Any]) -> None:
        matches = [record for record in manifest["artifacts"] if record.get("path") == name]
        if len(matches) != 1:
            raise ShipError("selftest artifact record is missing/duplicated: %s" % name)
        matches[0]["size"] = len(data)
        matches[0]["sha256"] = _sha(data)

    _rewrite_manifest(package, refresh)


def selftest() -> int:
    fixture = _load_json(ROOT / "tests/bytecode/formats/p0-disk-lib-v1.json", "L65M fixture")
    minimal = next(item for item in fixture["goldens"] if item["id"] == "minimal")
    image = bytes.fromhex(minimal["image_hex"])
    summary, blob, _entries = _parse_l65m(image)
    app = {
        "format": "lisp65-runtime-app-v1", "status": STATUS, "name": "selftest",
        "suite": "tests/selftest.json", "entry": {"name": "id", "arity": 0},
        "exports": ["id"], "provides": ["selftest"], "requires": ["core"],
        "library_closure": [], "native_capabilities": ["vm"], "expected_result": "0",
    }
    with tempfile.TemporaryDirectory(prefix="runtime-export-selftest-") as raw:
        base = Path(raw) / "base"
        base.mkdir()
        (base / "runtime-app.json").write_text(json.dumps(app, sort_keys=True) + "\n", encoding="utf-8")
        (base / "runtime-app.l65m").write_bytes(image)
        (base / "toolchain-report.txt").write_text(
            "format=lisp65-runtime-export-toolchain-report-v1\n", encoding="utf-8"
        )
        zero_sha = "0" * 64
        profile_lines = {
            "format": "lisp65-runtime-export-resolved-profile-v2",
            "profile": "runtime-export-v1-candidate", "status": STATUS,
            "layout": "inline-boot-overlay", "entry_abi": "named-zero-argument-p0",
            "runtime_entry": "id", "runtime_prg_format": "mega65-prg",
            "runtime_prg_load_address": "0x2001", "application_preload": "bank5-build-bound",
            "runtime_preload_address": "0x050000", "runtime_disk_loader": "false",
            "application_descriptor_format": "lisp65-runtime-app-v1",
            "application_artifact_format": "lisp65-bytecode-p0-disk-lib-artifacts-v1",
            "application_bytecode_abi": "P0", "application_l65m_version": "1",
            "application_emitter": "workbench-lcc-fasl-v1", "min_boot_stack_gap": "512",
            "min_post_boot_reserve": "8192", "post_boot_reserve_target": "12288",
            "max_prg_file_end": "45056", "min_symbol_headroom": "64",
            "g2_elf_surface": "passed-by-inline-overlay-audit",
            "g2_budgets": "passed-by-inline-overlay-audit", "g2_inline_overlay_audit": "passed",
            "g2_package_verifier": "required-post-pack", "g2_reproducibility": "required-post-pack",
            "contract_sha256": zero_sha, "app_descriptor_sha256": _sha((base / "runtime-app.json").read_bytes()),
            "suite_sha256": zero_sha, "config_sha256": zero_sha, "make_sha256": zero_sha,
            "inline_linker_sha256": zero_sha,
            "workbench_golden_sha256": _sha(image),
            "workbench_emission_receipt_sha256": zero_sha,
            "workbench_reemission_receipt_sha256": zero_sha,
            "workbench_ship_manifest_sha256": zero_sha,
        }
        (base / "resolved-profile.txt").write_text(
            "".join("%s=%s\n" % item for item in profile_lines.items()), encoding="utf-8"
        )
        profile, profile_data = _parse_profile(base / "resolved-profile.txt")
        build_id = int(_sha(profile_data)[:8], 16)
        preload = PRELOAD.bind(WORKBENCH.bank5_preload(image), build_id)
        (base / "runtime-preload.bin").write_bytes(preload)
        prg = b"\x01\x20runtime" + preload_binding_record(
            len(PRELOAD.parse(preload)[0]), crc16_ccitt_false(preload), build_id
        )
        (base / "runtime.prg").write_bytes(prg)
        paths = {name: base / name for name in PACKAGE_FILES[1:]}
        audit = {
            "resident_overlay_control_refs": "1",
            "prg_file_end": hex(PRG_LOAD_ADDRESS + len(prg) - 2),
            "boot_stack_gap": "1024", "post_boot_reserve": "13000",
        }
        footprint = {"boot_sym_headroom": "80"}
        manifest = _manifest(
            paths=paths, profile=profile, profile_data=profile_data, app=app, image=image,
            summary=summary, blob=blob, audit=audit, footprint=footprint,
            contract_sha256=zero_sha,
            hardware_symbols={
                "state": {"name": "lisp65_runtime_state", "address": 0x80, "size": 1, "encoding": "u8"},
                "result": {"name": "lisp65_runtime_result", "address": 0x82, "size": 2, "encoding": "obj16-le"},
                "preload_detail": {"name": "lisp65_runtime_preload_detail", "address": 0x84, "size": 1, "encoding": "u8"},
            },
            emission_receipt_sha256=zero_sha,
            reemission_receipt_sha256=zero_sha,
        )
        (base / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        verify(base)

        def corrupt_l65m(package: Path) -> None:
            path = package / "runtime-app.l65m"
            data = bytearray(path.read_bytes())
            data[4 + _u16(data, 0, "selftest L65M")] ^= 1
            path.write_bytes(data)
            _refresh_artifact_record(package, "runtime-app.l65m")

        def change_l65m_arity(package: Path) -> None:
            path = package / "runtime-app.l65m"
            data = bytearray(path.read_bytes())
            data[5] = 1
            path.write_bytes(data)
            _refresh_artifact_record(package, "runtime-app.l65m")

        def change_prg_binding(package: Path) -> None:
            path = package / "runtime.prg"
            data = bytearray(path.read_bytes())
            begin, _end = _prg_binding_span(data)
            data[begin + 8] ^= 1
            path.write_bytes(data)
            _refresh_artifact_record(package, "runtime.prg")

        def add_profile_marker(package: Path, marker: str) -> None:
            path = package / "resolved-profile.txt"
            path.write_text(
                path.read_text(encoding="utf-8") + marker + "\n",
                encoding="utf-8",
            )

        mutations: list[tuple[str, Any, str]] = [
            (
                "dialect-v2-abi-profile",
                lambda p: add_profile_marker(p, "abi_profile=dialect-v2"),
                "no passed-G5",
            ),
            (
                "dialect-v2-profile-id",
                lambda p: add_profile_marker(p, "profile_id=v2-capability-candidate"),
                "no passed-G5",
            ),
            ("extra-file", lambda p: (p / "extra").write_text("x", encoding="utf-8"), "file set"),
            ("payload-hash", lambda p: (p / "runtime.prg").write_bytes(b"\x01\x20changed"), "hash mismatch"),
            ("build-id", lambda p: _rewrite_manifest(p, lambda m: m["profile"].update({"build_id": 1})), "build-id"),
            ("preload-crc", lambda p: _rewrite_manifest(p, lambda m: m["runtime"]["preload"].update({"crc16": 1})), "preload"),
            ("preload-payload-crc", lambda p: _rewrite_manifest(p, lambda m: m["runtime"]["preload"].update({"payload_crc16": 1})), "preload"),
            ("preload-binding-build-id", lambda p: _rewrite_manifest(p, lambda m: m["runtime"]["preload"]["binding"].update({"build_id": 1})), "preload"),
            ("prg-preload-binding", change_prg_binding, "PRG preload binding"),
            ("l65m-schema", corrupt_l65m, "L65M failed preflight"),
            ("l65m-entry-arity", change_l65m_arity, "not zero-argument"),
            ("entry-arity", lambda p: _rewrite_manifest(p, lambda m: m["runtime"]["entry"].update({"arity": 1})), "entry binding"),
            ("g5-claim", lambda p: _rewrite_manifest(p, lambda m: m["gates"]["G5"].update({"cold_boot_hardware": "passed"})), "G5"),
            ("g4-claim", lambda p: _rewrite_manifest(p, lambda m: m["gates"]["G4"].update({"deploy_dry_run": "passed"})), "G4"),
            ("hardware-detail", lambda p: _rewrite_manifest(p, lambda m: m["hardware_oracle"]["preload_details"].update({"crc": 2})), "preload-detail"),
            ("hardware-symbol", lambda p: _rewrite_manifest(p, lambda m: m["hardware_oracle"]["symbols"]["state"].update({"name": "magic_state"})), "hardware symbol"),
            ("provenance", lambda p: _rewrite_manifest(p, lambda m: m["provenance"].update({"application_emitter": "host-p0-generator"})), "provenance"),
        ]
        for label, mutate, needle in mutations:
            candidate = Path(raw) / label
            shutil.copytree(base, candidate)
            mutate(candidate)
            try:
                verify(candidate)
            except ShipError as exc:
                if needle not in str(exc):
                    raise ShipError("selftest %s failed for wrong reason: %s" % (label, exc)) from exc
            else:
                raise ShipError("selftest mutation passed: %s" % label)
    if crc16_ccitt_false(b"123456789") != 0x29B1:
        raise ShipError("CRC-16/CCITT-FALSE check vector failed")
    print("runtime-export-ship selftest: PASS mutations=16")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    pack_parser = sub.add_parser("pack")
    for flag in (
        "contract", "app", "app-image", "app-manifest", "preload", "preload-manifest",
        "prg", "elf", "nm", "objdump", "profile", "toolchain-report", "audit-report",
        "footprint-report", "workbench-emission-receipt",
        "workbench-reemission-receipt", "workbench-ship-manifest", "out-dir",
    ):
        pack_parser.add_argument("--" + flag, type=Path, required=True)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("--dir", type=Path, required=True)
    sub.add_parser("selftest")
    args = parser.parse_args(argv)
    try:
        if args.command == "pack":
            return pack(args)
        if args.command == "verify":
            return verify(args.dir)
        return selftest()
    except (ShipError, OSError, ValueError, KeyError) as exc:
        print("runtime-export-ship: FAIL: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
