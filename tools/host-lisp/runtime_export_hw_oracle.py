#!/usr/bin/env python3
"""Standalone AP8.2.3 Runtime Export G4/G5 hardware contract.

The shipped Runtime Export package deliberately contains no ELF.  ``oracle``
therefore binds the three hardware-observable symbols to the exact PRG payload at
build-review time.  ``deploy`` verifies the sealed package and that oracle
before it can touch a device.

G4 is a pure planner: it performs no mkdir, tempfile, tool lookup, or hardware
command.  G5 is one power-cycle-scoped phase per invocation.  It records the
pre-stage Bank-5 digest, stages only Bank 5 and the PRG, reads the effective
    Bank-5 image back, and then evaluates the symbol-sized
    state/result/preload-detail readbacks.
No D81, SD-card, or Attic operation exists in this module.
"""

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
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "host-lisp"))

import runtime_export_ship as SHIP  # noqa: E402


ORACLE_FORMAT = "lisp65-runtime-export-hw-oracle-v2"
RECEIPT_FORMAT = "lisp65-runtime-export-hw-receipt-v2"
PLAN_FORMAT = "lisp65-runtime-export-g4-plan-v2"
PACKAGE_FORMAT = "lisp65-runtime-export-ship-v2"
INTERNAL_V2_PACKAGE_FORMAT = "lisp65-v2-runtime-core-g5-package-v1"
PACKAGE_FORMATS = {PACKAGE_FORMAT, INTERNAL_V2_PACKAGE_FORMAT}
PHASES = ("clean", "truncated", "bitflip", "build-id-mismatch")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
CYCLE_ID_RE = re.compile(r"^[A-Za-z0-9._-]{8,}$")
SYMBOL_RE = re.compile(
    r"^([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+\S\s+(\S+)$"
)
ORACLE_KEYS = {
    "format", "manifest_sha256", "package_format", "profile", "runtime",
    "hardware_oracle", "elf",
}
RECEIPT_KEYS = {
    "schema", "scope", "gate", "phase", "status", "manifest_sha256",
    "oracle_sha256", "profile_build_id", "foreign_profile_build_id",
    "foreign_manifest_sha256", "operator", "addresses", "expected",
    "observed", "evidence", "error",
}
PLAN_KEYS = {
    "format", "gate", "offline", "side_effects", "phase",
    "manifest_sha256", "oracle_sha256", "profile_build_id",
    "foreign_profile_build_id", "foreign_manifest_sha256", "mutation",
    "stage_payload", "effective_bank5", "state_address", "result_address",
    "preload_detail_address", "expected_preload_detail", "commands",
}


class HardwareContractError(RuntimeError):
    pass


def _valid_cycle_id(value: Any) -> bool:
    return isinstance(value, str) and CYCLE_ID_RE.fullmatch(value) is not None


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise HardwareContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object
        )
    except HardwareContractError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HardwareContractError(f"cannot read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise HardwareContractError(f"{label} must be an object")
    return value


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise HardwareContractError(
            f"{label} keys differ: expected={sorted(keys)} actual={actual}"
        )
    return value


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_file(path: Path) -> str:
    try:
        return _sha(path.read_bytes())
    except OSError as exc:
        raise HardwareContractError(f"cannot hash {path}: {exc}") from exc


def _regular_file(path: Path, label: str) -> Path:
    if path.is_symlink() or not path.is_file():
        raise HardwareContractError(f"{label} must be a regular non-symlink file: {path}")
    return path


def _artifact_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records = manifest.get("artifacts")
    if not isinstance(records, list):
        raise HardwareContractError("manifest artifacts must be a list")
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            raise HardwareContractError("manifest has a malformed artifact record")
        path = record["path"]
        if path in result:
            raise HardwareContractError(f"duplicate manifest artifact: {path}")
        result[path] = record
    return result


def _verify_internal_v2_package(package: Path, manifest: dict[str, Any]) -> None:
    """Verify the non-shippable dialect-v2 Runtime-Core G5 package.

    This format deliberately carries the same runtime/oracle vocabulary as the
    Runtime Export harness, but it is sealed from the v2 proof candidate and is
    never accepted by the Runtime Export ship verifier.
    """
    _exact(
        manifest,
        {
            "format", "version", "profile", "source_candidate", "artifacts",
            "runtime", "hardware_oracle", "phases",
        },
        "internal v2 runtime package",
    )
    if manifest["format"] != INTERNAL_V2_PACKAGE_FORMAT or manifest["version"] != 1:
        raise HardwareContractError("internal v2 runtime package identity drift")
    profile = _exact(
        manifest["profile"],
        {"id", "abi_profile", "build_id", "sha256", "shippable"},
        "internal v2 runtime profile",
    )
    if (
        profile["id"] != "dialect-v2-runtime-core-proof"
        or profile["abi_profile"] != "dialect-v2"
        or type(profile["build_id"]) is not int
        or not 0 <= profile["build_id"] <= 0xFFFFFFFF
        or profile["shippable"] is not False
        or not isinstance(profile["sha256"], str)
        or not SHA_RE.fullmatch(profile["sha256"])
    ):
        raise HardwareContractError("internal v2 runtime profile drift")
    source = _exact(
        manifest["source_candidate"], {"path", "sha256", "format", "source_commit"},
        "internal v2 runtime source candidate",
    )
    if (
        source["format"] != "lisp65-v2-runtime-core-proof-candidate-v1"
        or not isinstance(source["source_commit"], str)
        or not re.fullmatch(r"[0-9a-f]{40}", source["source_commit"])
    ):
        raise HardwareContractError("internal v2 runtime source candidate drift")

    records = manifest["artifacts"]
    if not isinstance(records, list):
        raise HardwareContractError("internal v2 runtime artifacts must be a list")
    by_role: dict[str, tuple[dict[str, Any], bytes]] = {}
    seen_paths: set[str] = set()
    for index, raw in enumerate(records):
        record = _exact(raw, {"role", "path", "size", "sha256"}, f"artifact[{index}]")
        role, name = record["role"], record["path"]
        if (
            not isinstance(role, str) or not role or role in by_role
            or not isinstance(name, str) or name != Path(name).name or name in seen_paths
            or type(record["size"]) is not int or record["size"] < 0
            or not isinstance(record["sha256"], str) or not SHA_RE.fullmatch(record["sha256"])
        ):
            raise HardwareContractError("internal v2 runtime artifact record is invalid")
        path = _regular_file(package / name, f"internal v2 runtime artifact {role}")
        data = path.read_bytes()
        if len(data) != record["size"] or _sha(data) != record["sha256"]:
            raise HardwareContractError(f"internal v2 runtime artifact binding drift: {role}")
        by_role[role] = (record, data)
        seen_paths.add(name)
    required_roles = {
        "proof-manifest", "resolved-profile", "runtime-prg", "runtime-preload",
        "runtime-elf", "stage-clean", "stage-truncated", "effective-truncated",
        "clear-truncated", "stage-bitflip", "stage-build-id-mismatch",
        "foreign-profile",
    }
    if set(by_role) != required_roles:
        raise HardwareContractError(
            "internal v2 runtime artifact role mismatch: "
            f"expected={sorted(required_roles)} actual={sorted(by_role)}"
        )
    source_path = source["path"]
    if (
        source_path != by_role["proof-manifest"][0]["path"]
        or source["sha256"] != by_role["proof-manifest"][0]["sha256"]
    ):
        raise HardwareContractError("internal v2 runtime source manifest binding drift")
    try:
        proof = json.loads(by_role["proof-manifest"][1].decode("utf-8"), object_pairs_hook=_strict_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HardwareContractError("internal v2 proof manifest is invalid") from exc
    if (
        not isinstance(proof, dict)
        or proof.get("format") != source["format"]
        or proof.get("source_commit") != source["source_commit"]
    ):
        raise HardwareContractError("internal v2 proof manifest identity drift")

    profile_bytes = by_role["resolved-profile"][1]
    if _sha(profile_bytes) != profile["sha256"] or int(profile["sha256"][:8], 16) != profile["build_id"]:
        raise HardwareContractError("internal v2 resolved profile/build-id drift")
    runtime = _exact(
        manifest["runtime"], {"prg", "preload", "expected_result"},
        "internal v2 runtime",
    )
    prg_record = _exact(runtime["prg"], {"path", "format", "load_address"}, "runtime.prg")
    if (
        prg_record != {
            "path": by_role["runtime-prg"][0]["path"],
            "format": "mega65-prg",
            "load_address": 0x2001,
        }
        or runtime["expected_result"] != "42"
    ):
        raise HardwareContractError("internal v2 runtime PRG/result drift")
    preload = _exact(
        runtime["preload"],
        {
            "path", "address", "length", "sha256", "payload_length",
            "code_blob_bytes", "binding",
        },
        "runtime.preload",
    )
    binding = _exact(
        preload["binding"], {"format", "trailer_offset", "trailer_length", "build_id"},
        "runtime.preload.binding",
    )
    canonical = by_role["runtime-preload"][1]
    try:
        payload, bound_build_id = SHIP.PRELOAD.parse(canonical)
    except SHIP.PRELOAD.PreloadError as exc:
        raise HardwareContractError(f"internal v2 bound preload is invalid: {exc}") from exc
    if (
        preload["path"] != by_role["runtime-preload"][0]["path"]
        or preload["address"] != 0x050000
        or preload["length"] != len(canonical)
        or preload["sha256"] != _sha(canonical)
        or preload["payload_length"] != len(payload)
        or type(preload["code_blob_bytes"]) is not int
        or not 0 <= preload["code_blob_bytes"] < len(payload)
        or binding != {
            "format": "lisp65-runtime-preload-binding-v1",
            "trailer_offset": len(payload),
            "trailer_length": SHIP.PRELOAD.TRAILER_BYTES,
            "build_id": profile["build_id"],
        }
        or bound_build_id != profile["build_id"]
    ):
        raise HardwareContractError("internal v2 preload metadata drift")
    try:
        SHIP.verify_prg_binding(
            by_role["runtime-prg"][1], len(payload),
            SHIP.PRELOAD.crc16_ccitt_false(canonical), profile["build_id"],
        )
    except SHIP.ShipError as exc:
        raise HardwareContractError(f"internal v2 PRG/preload binding failed: {exc}") from exc

    phases = _exact(
        manifest["phases"], {"clean", "truncated", "bitflip", "build-id-mismatch"},
        "internal v2 phases",
    )
    clean = _exact(phases["clean"], {"stage", "effective", "expected_detail"}, "phase.clean")
    truncated = _exact(
        phases["truncated"], {"stage", "effective", "clear", "expected_detail"},
        "phase.truncated",
    )
    bitflip = _exact(phases["bitflip"], {"stage", "effective", "offset", "expected_detail"}, "phase.bitflip")
    mismatch = _exact(
        phases["build-id-mismatch"],
        {"stage", "effective", "foreign_profile", "foreign_build_id", "expected_detail"},
        "phase.build-id-mismatch",
    )
    hardware = manifest["hardware_oracle"]
    details = hardware.get("preload_details") if isinstance(hardware, dict) else None
    if not isinstance(details, dict):
        raise HardwareContractError("internal v2 hardware detail oracle is missing")

    def role_data(role: str, record: Any, label: str) -> bytes:
        item = _exact(record, {"role", "sha256"}, label)
        if item["role"] != role or item["sha256"] != by_role[role][0]["sha256"]:
            raise HardwareContractError(f"{label} artifact binding drift")
        return by_role[role][1]

    if (
        role_data("stage-clean", clean["stage"], "phase.clean.stage") != canonical
        or clean["effective"] != clean["stage"]
        or clean["expected_detail"] != details.get("ok")
    ):
        raise HardwareContractError("internal v2 clean phase drift")
    truncated_stage = role_data("stage-truncated", truncated["stage"], "phase.truncated.stage")
    truncated_effective = role_data("effective-truncated", truncated["effective"], "phase.truncated.effective")
    truncated_clear = role_data("clear-truncated", truncated["clear"], "phase.truncated.clear")
    if (
        truncated_stage != payload or truncated_clear != bytes(len(canonical))
        or truncated_effective != payload + bytes(SHIP.PRELOAD.TRAILER_BYTES)
        or truncated["expected_detail"] != details.get("length")
    ):
        raise HardwareContractError("internal v2 truncated phase drift")
    bitflip_stage = role_data("stage-bitflip", bitflip["stage"], "phase.bitflip.stage")
    if (
        bitflip["effective"] != bitflip["stage"]
        or bitflip["offset"] != preload["code_blob_bytes"]
        or len(bitflip_stage) != len(canonical)
        or bitflip_stage[:bitflip["offset"]] != canonical[:bitflip["offset"]]
        or bitflip_stage[bitflip["offset"]] != (canonical[bitflip["offset"]] ^ 1)
        or bitflip_stage[bitflip["offset"] + 1:] != canonical[bitflip["offset"] + 1:]
        or bitflip["expected_detail"] != details.get("crc")
    ):
        raise HardwareContractError("internal v2 bitflip phase drift")
    mismatch_stage = role_data(
        "stage-build-id-mismatch", mismatch["stage"], "phase.build-id-mismatch.stage"
    )
    foreign_profile = role_data(
        "foreign-profile", mismatch["foreign_profile"], "phase.build-id-mismatch.foreign_profile"
    )
    try:
        foreign_payload, foreign_build_id = SHIP.PRELOAD.parse(mismatch_stage)
    except SHIP.PRELOAD.PreloadError as exc:
        raise HardwareContractError(f"internal v2 mismatch preload is invalid: {exc}") from exc
    if (
        mismatch["effective"] != mismatch["stage"]
        or foreign_payload != payload
        or foreign_build_id == profile["build_id"]
        or foreign_build_id != mismatch["foreign_build_id"]
        or int(_sha(foreign_profile)[:8], 16) != foreign_build_id
        or mismatch["expected_detail"] != details.get("build_id")
    ):
        raise HardwareContractError("internal v2 build-id mismatch phase drift")


def _json_diff_paths(left: Any, right: Any, prefix: tuple[Any, ...] = ()) -> set[tuple[Any, ...]]:
    if type(left) is not type(right):
        return {prefix}
    if isinstance(left, dict):
        if set(left) != set(right):
            return {prefix}
        result: set[tuple[Any, ...]] = set()
        for key in left:
            result.update(_json_diff_paths(left[key], right[key], prefix + (key,)))
        return result
    if isinstance(left, list):
        if len(left) != len(right):
            return {prefix}
        result = set()
        for index, (left_item, right_item) in enumerate(zip(left, right)):
            result.update(_json_diff_paths(left_item, right_item, prefix + (index,)))
        return result
    return set() if left == right else {prefix}


def _verified_package(package: Path) -> tuple[dict[str, Any], str]:
    package = package.resolve()
    manifest_path = _regular_file(package / "manifest.json", "package manifest")
    manifest = _load_json(manifest_path, "package manifest")
    if manifest.get("format") == INTERNAL_V2_PACKAGE_FORMAT:
        _verify_internal_v2_package(package, manifest)
    else:
        try:
            SHIP.verify(package)
        except (SHIP.ShipError, OSError, ValueError, KeyError) as exc:
            raise HardwareContractError(f"Runtime Export package verification failed: {exc}") from exc
    return manifest, _sha_file(manifest_path)


def _profile_with_id(data: bytes, profile_id: str | None) -> tuple[bytes, str, str, int]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HardwareContractError("resolved profile is not UTF-8") from exc
    lines = text.splitlines(keepends=True)
    matches = [index for index, line in enumerate(lines) if line.startswith("profile=")]
    if len(matches) != 1:
        raise HardwareContractError("resolved profile must contain exactly one profile field")
    index = matches[0]
    old_id = lines[index][len("profile="):].rstrip("\r\n")
    newline = lines[index][len(lines[index].rstrip("\r\n")):]
    if not old_id:
        raise HardwareContractError("resolved profile id is empty")
    if profile_id is not None:
        candidates = (profile_id,)
    else:
        candidates = tuple(
            old_id + "-g5-mismatch" + ("" if suffix == 1 else f"-{suffix}")
            for suffix in range(1, 257)
        )
    for candidate in candidates:
        if (candidate == old_id or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", candidate)):
            if profile_id is not None:
                raise HardwareContractError("mismatch profile id is invalid or unchanged")
            continue
        changed = list(lines)
        changed[index] = f"profile={candidate}{newline}"
        encoded = "".join(changed).encode("utf-8")
        build_id = int(_sha(encoded)[:8], 16)
        if build_id != int(_sha(data)[:8], 16):
            return encoded, old_id, candidate, build_id
    raise HardwareContractError("could not derive a distinct mismatch profile build-id")


def create_mismatch_package(package: Path, out: Path, profile_id: str | None = None) -> int:
    package = package.resolve()
    out = out.resolve()
    manifest, _manifest_sha = _verified_package(package)
    try:
        out.relative_to(package)
    except ValueError:
        pass
    else:
        raise HardwareContractError("mismatch output must not be inside the canonical package")
    if out.exists() or out.is_symlink():
        raise HardwareContractError(f"mismatch output must not exist: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        out.mkdir(exist_ok=False)
        created = True
        for name in SHIP.PACKAGE_FILES:
            shutil.copyfile(package / name, out / name)

        profile_path = out / "resolved-profile.txt"
        old_profile = profile_path.read_bytes()
        new_profile, old_id, new_id, new_build_id = _profile_with_id(old_profile, profile_id)
        old_build_id = manifest["profile"]["build_id"]
        if old_build_id != int(_sha(old_profile)[:8], 16) or new_build_id == old_build_id:
            raise HardwareContractError("canonical/mismatch profile build-id relation is invalid")
        profile_path.write_bytes(new_profile)

        preload_path = out / "runtime-preload.bin"
        old_preload = preload_path.read_bytes()
        try:
            payload, bound_build_id = SHIP.PRELOAD.parse(old_preload)
            new_preload = SHIP.PRELOAD.bind(payload, new_build_id)
        except SHIP.PRELOAD.PreloadError as exc:
            raise HardwareContractError(f"canonical preload binding is invalid: {exc}") from exc
        if bound_build_id != old_build_id:
            raise HardwareContractError("canonical preload/profile build-id differs")
        if new_preload[:-4] != old_preload[:-4] or new_preload[:len(payload)] != payload:
            raise HardwareContractError("mismatch preload changed outside the binding build-id")
        preload_path.write_bytes(new_preload)

        prg_path = out / "runtime.prg"
        old_prg = prg_path.read_bytes()
        new_prg = SHIP.rebind_prg(
            old_prg, len(payload), SHIP.crc16_ccitt_false(new_preload), new_build_id
        )
        prg_path.write_bytes(new_prg)

        changed = _load_json(out / "manifest.json", "copied package manifest")
        changed["profile"].update({
            "id": new_id,
            "sha256": _sha(new_profile),
            "build_id": new_build_id,
        })
        artifacts = _artifact_map(changed)
        for name, data in (
            ("resolved-profile.txt", new_profile),
            ("runtime-preload.bin", new_preload),
            ("runtime.prg", new_prg),
        ):
            artifacts[name]["size"] = len(data)
            artifacts[name]["sha256"] = _sha(data)
        preload_record = changed["runtime"]["preload"]
        preload_record.update({
            "length": len(new_preload),
            "crc16": SHIP.crc16_ccitt_false(new_preload),
            "sha256": _sha(new_preload),
        })
        preload_record["binding"]["build_id"] = new_build_id
        artifact_indices = {
            record["path"]: index for index, record in enumerate(changed["artifacts"])
        }
        profile_index = artifact_indices["resolved-profile.txt"]
        preload_index = artifact_indices["runtime-preload.bin"]
        prg_index = artifact_indices["runtime.prg"]
        allowed_diffs = {
            ("profile", "id"),
            ("profile", "sha256"),
            ("profile", "build_id"),
            ("artifacts", profile_index, "size"),
            ("artifacts", profile_index, "sha256"),
            ("artifacts", preload_index, "size"),
            ("artifacts", preload_index, "sha256"),
            ("artifacts", prg_index, "size"),
            ("artifacts", prg_index, "sha256"),
            ("runtime", "preload", "length"),
            ("runtime", "preload", "crc16"),
            ("runtime", "preload", "sha256"),
            ("runtime", "preload", "binding", "build_id"),
        }
        required_diffs = {
            ("profile", "id"),
            ("profile", "sha256"),
            ("profile", "build_id"),
            ("artifacts", profile_index, "sha256"),
            ("artifacts", preload_index, "sha256"),
            ("artifacts", prg_index, "sha256"),
            ("runtime", "preload", "sha256"),
            ("runtime", "preload", "binding", "build_id"),
        }
        actual_diffs = _json_diff_paths(manifest, changed)
        if actual_diffs - allowed_diffs or not required_diffs.issubset(actual_diffs):
            raise HardwareContractError(
                "mismatch manifest changed outside the approved binding fields: %s"
                % sorted(actual_diffs - allowed_diffs)
            )
        (out / "manifest.json").write_text(
            json.dumps(changed, indent=2, sort_keys=True) + "\n", encoding="ascii"
        )
        _verified_package(out)

        if (package / "runtime-preload.bin").read_bytes() != old_preload:
            raise HardwareContractError("canonical package changed while creating mismatch package")
    except BaseException:
        if created:
            shutil.rmtree(out, ignore_errors=True)
        raise
    print(
        "runtime-export-hw mismatch package: PASS "
        f"out={out} profile={old_id}->{new_id} build_id=0x{old_build_id:08x}->0x{new_build_id:08x}"
    )
    return 0


def _fixnum_raw(text: str) -> int:
    try:
        value = int(text, 10)
    except (TypeError, ValueError) as exc:
        raise HardwareContractError(
            "Runtime Export HW v2 requires an integer expected_result"
        ) from exc
    if value < -16384 or value > 16383:
        raise HardwareContractError("expected_result is outside the 15-bit fixnum range")
    return ((value & 0xFFFF) << 1 | 1) & 0xFFFF


def _run_checked(command: list[str], *, timeout: int = 30,
                 env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command, check=True, text=True, capture_output=True, timeout=timeout, env=env
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        detail = ""
        if isinstance(exc, subprocess.CalledProcessError):
            detail = (exc.stderr or exc.stdout or "").strip()
        raise HardwareContractError(
            f"command failed: {' '.join(command)}{': ' + detail if detail else ''}"
        ) from exc


def _nm_symbols(nm: Path, elf: Path) -> dict[str, dict[str, Any]]:
    output = _run_checked(
        [str(nm), "--defined-only", "--print-size", str(elf)]
    ).stdout
    wanted = {
        "lisp65_runtime_state": (1, "u8"),
        "lisp65_runtime_result": (2, "obj16-le"),
        "lisp65_runtime_preload_detail": (1, "u8"),
    }
    found: dict[str, dict[str, Any]] = {}
    for raw in output.splitlines():
        match = SYMBOL_RE.match(raw.strip())
        if not match:
            continue
        address_hex, size_hex, name = match.groups()
        if name not in wanted:
            continue
        if name in found:
            raise HardwareContractError(f"duplicate ELF symbol: {name}")
        expected_size, encoding = wanted[name]
        address = int(address_hex, 16)
        size = int(size_hex, 16)
        if size != expected_size or address + size > 0x10000:
            raise HardwareContractError(
                f"ELF symbol {name} has invalid address/size: 0x{address:04x}/{size}"
            )
        found[name] = {
            "name": name,
            "address": address,
            "size": size,
            "encoding": encoding,
        }
    if set(found) != set(wanted):
        raise HardwareContractError(
            f"ELF lacks Runtime Export HW symbols: {sorted(set(wanted) - set(found))}"
        )
    records = list(found.values())
    for index, left in enumerate(records):
        for right in records[index + 1:]:
            if max(left["address"], right["address"]) < min(
                left["address"] + left["size"], right["address"] + right["size"]
            ):
                raise HardwareContractError("Runtime Export HW symbols overlap")
    return {
        "state": found["lisp65_runtime_state"],
        "result": found["lisp65_runtime_result"],
        "preload_detail": found["lisp65_runtime_preload_detail"],
    }


def create_oracle(package: Path, elf: Path, nm: Path, objcopy: Path, out: Path) -> int:
    manifest, manifest_sha = _verified_package(package)
    _regular_file(elf, "Runtime Export ELF")
    _regular_file(nm, "llvm-nm")
    _regular_file(objcopy, "llvm-objcopy")
    symbols = _nm_symbols(nm, elf)
    hardware_oracle = manifest["hardware_oracle"]
    if symbols != hardware_oracle["symbols"]:
        raise HardwareContractError(
            "ELF hardware symbols differ from the manifest-v2 hardware oracle"
        )
    prg = _regular_file(package / manifest["runtime"]["prg"]["path"], "runtime PRG").read_bytes()
    if len(prg) < 3:
        raise HardwareContractError("runtime PRG is truncated")
    with tempfile.TemporaryDirectory(prefix="runtime-export-oracle-") as raw:
        raw_payload = Path(raw) / "elf.bin"
        _run_checked([str(objcopy), "-O", "binary", str(elf), str(raw_payload)])
        elf_payload = _regular_file(raw_payload, "objcopy payload").read_bytes()
    if elf_payload != prg[2:]:
        raise HardwareContractError("ELF payload differs from the manifest-bound runtime PRG")
    runtime = manifest["runtime"]
    preload = runtime["preload"]
    expected_text = runtime["expected_result"]
    oracle = {
        "format": ORACLE_FORMAT,
        "manifest_sha256": manifest_sha,
        "package_format": manifest["format"],
        "profile": {
            "id": manifest["profile"]["id"],
            "build_id": manifest["profile"]["build_id"],
        },
        "runtime": {
            "prg_sha256": _sha(prg),
            "preload_address": preload["address"],
            "preload_length": preload["length"],
            "preload_sha256": preload["sha256"],
            "code_blob_bytes": preload["code_blob_bytes"],
            "expected_result": expected_text,
            "expected_result_raw": _fixnum_raw(expected_text),
        },
        "hardware_oracle": hardware_oracle,
        "elf": {
            "sha256": _sha_file(elf),
            "payload_sha256": _sha(elf_payload),
        },
    }
    if out.exists() or out.is_symlink():
        raise HardwareContractError(f"refusing to overwrite oracle: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(oracle, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(f"runtime-export-hw-oracle create: PASS out={out} manifest_sha256={manifest_sha}")
    return 0


def verify_oracle(package: Path, oracle_path: Path) -> tuple[dict[str, Any], dict[str, Any], str]:
    manifest, manifest_sha = _verified_package(package)
    _regular_file(oracle_path, "Runtime Export HW oracle")
    oracle_sha = _sha_file(oracle_path)
    oracle = _exact(_load_json(oracle_path, "Runtime Export HW oracle"), ORACLE_KEYS, "oracle")
    if (
        oracle["format"] != ORACLE_FORMAT
        or oracle["package_format"] != manifest["format"]
        or oracle["package_format"] not in PACKAGE_FORMATS
    ):
        raise HardwareContractError("oracle format/package format mismatch")
    if oracle["manifest_sha256"] != manifest_sha:
        raise HardwareContractError("oracle is bound to another package manifest")
    profile = _exact(oracle["profile"], {"id", "build_id"}, "oracle.profile")
    if profile != {"id": manifest["profile"]["id"], "build_id": manifest["profile"]["build_id"]}:
        raise HardwareContractError("oracle profile/build-id mismatch")
    runtime = _exact(
        oracle["runtime"],
        {"prg_sha256", "preload_address", "preload_length", "preload_sha256",
         "code_blob_bytes", "expected_result", "expected_result_raw"},
        "oracle.runtime",
    )
    manifest_runtime = manifest["runtime"]
    preload = manifest_runtime["preload"]
    expected_runtime = {
        "prg_sha256": _sha_file(package / manifest_runtime["prg"]["path"]),
        "preload_address": preload["address"],
        "preload_length": preload["length"],
        "preload_sha256": preload["sha256"],
        "code_blob_bytes": preload["code_blob_bytes"],
        "expected_result": manifest_runtime["expected_result"],
        "expected_result_raw": _fixnum_raw(manifest_runtime["expected_result"]),
    }
    if runtime != expected_runtime:
        raise HardwareContractError("oracle runtime binding differs from the package")
    if oracle["hardware_oracle"] != manifest["hardware_oracle"]:
        raise HardwareContractError("oracle differs from the manifest-v2 hardware oracle")
    hardware = _exact(
        oracle["hardware_oracle"],
        {"format", "symbols", "states", "results", "preload_details"},
        "oracle.hardware_oracle",
    )
    symbols = _exact(
        hardware["symbols"], {"state", "result", "preload_detail"},
        "oracle.hardware_oracle.symbols",
    )
    for key, name, size, encoding in (
        ("state", "lisp65_runtime_state", 1, "u8"),
        ("result", "lisp65_runtime_result", 2, "obj16-le"),
        ("preload_detail", "lisp65_runtime_preload_detail", 1, "u8"),
    ):
        record = _exact(symbols[key], {"name", "address", "size", "encoding"}, f"oracle.symbols.{key}")
        if (record["name"], record["size"], record["encoding"]) != (name, size, encoding):
            raise HardwareContractError(f"oracle {key} symbol contract mismatch")
        if not isinstance(record["address"], int) or record["address"] < 0 or record["address"] + size > 0x10000:
            raise HardwareContractError(f"oracle {key} address is invalid")
    _exact(oracle["elf"], {"sha256", "payload_sha256"}, "oracle.elf")
    if oracle["elf"]["payload_sha256"] != _sha((package / manifest_runtime["prg"]["path"]).read_bytes()[2:]):
        raise HardwareContractError("oracle ELF payload binding differs from the runtime PRG")
    print(f"runtime-export-hw-oracle verify: PASS oracle={oracle_path} sha256={oracle_sha}")
    return manifest, oracle, oracle_sha


def _phase_payload(
    phase: str, package: Path, manifest: dict[str, Any],
    mismatch_package: Path | None,
) -> tuple[bytes, bytes, bytes | None, int | None, str | None, str, int]:
    canonical = (package / manifest["runtime"]["preload"]["path"]).read_bytes()
    preload = manifest["runtime"]["preload"]
    details = manifest["hardware_oracle"]["preload_details"]
    if manifest["format"] == INTERNAL_V2_PACKAGE_FORMAT:
        phase_record = manifest["phases"][phase]

        def phase_file(binding: dict[str, Any]) -> bytes:
            role = binding["role"]
            records = {
                record["role"]: record for record in manifest["artifacts"]
            }
            if role not in records or binding["sha256"] != records[role]["sha256"]:
                raise HardwareContractError(f"internal v2 phase artifact drift: {role}")
            return _regular_file(package / records[role]["path"], role).read_bytes()

        payload = phase_file(phase_record["stage"])
        effective = payload if phase_record["effective"] == phase_record["stage"] else phase_file(phase_record["effective"])
        clear = phase_file(phase_record["clear"]) if "clear" in phase_record else None
        foreign_id = phase_record.get("foreign_build_id")
        foreign_sha = None
        if phase == "build-id-mismatch":
            foreign_profile = phase_file(phase_record["foreign_profile"])
            foreign_sha = _sha(foreign_profile)
        descriptions = {
            "clean": "canonical manifest-bound v2 preload",
            "truncated": "target span zeroed; v2 payload staged without binding trailer",
            "build-id-mismatch": "manifest-bound foreign v2 preload with a different profile build-id",
        }
        description = (
            f"v2 payload bit 0 flipped at manifest offset {phase_record['offset']}"
            if phase == "bitflip" else descriptions[phase]
        )
        return (
            payload, effective, clear, foreign_id, foreign_sha,
            description, phase_record["expected_detail"],
        )
    foreign_build_id: int | None = None
    foreign_manifest_sha: str | None = None
    detail = "canonical manifest-bound preload"
    clear: bytes | None = None
    if phase == "clean":
        return canonical, canonical, None, None, None, detail, details["ok"]
    if phase == "truncated":
        payload_length = preload["payload_length"]
        binding = preload["binding"]
        if (payload_length <= 0 or binding["trailer_offset"] != payload_length or
                payload_length + binding["trailer_length"] != len(canonical)):
            raise HardwareContractError("manifest-v2 preload span is invalid for truncation")
        clear = bytes(len(canonical))
        payload = canonical[:payload_length]
        effective = payload + clear[payload_length:]
        return (
            payload, effective, clear, None, None,
            "target span zeroed; payload staged without binding trailer",
            details["length"],
        )
    if phase == "bitflip":
        offset = preload["code_blob_bytes"]
        if not isinstance(offset, int) or offset < 0 or offset >= preload["payload_length"]:
            raise HardwareContractError("metadata bitflip offset is outside the preload payload")
        payload = bytearray(canonical)
        payload[offset] ^= 0x01
        return (
            bytes(payload), bytes(payload), None, None, None,
            f"payload bit 0 flipped at manifest offset {offset}", details["crc"],
        )
    if mismatch_package is None:
        raise HardwareContractError("build-id-mismatch requires --mismatch-package")
    foreign_manifest, foreign_manifest_sha = _verified_package(mismatch_package)
    foreign_build_id = foreign_manifest["profile"]["build_id"]
    if foreign_build_id == manifest["profile"]["build_id"]:
        raise HardwareContractError("mismatch package has the same profile build-id")
    foreign = (mismatch_package / foreign_manifest["runtime"]["preload"]["path"]).read_bytes()
    foreign_preload = foreign_manifest["runtime"]["preload"]
    if len(foreign) != len(canonical):
        raise HardwareContractError("mismatch preload length differs from the canonical preload")
    if (foreign_preload["payload_length"] != preload["payload_length"] or
            foreign_preload["binding"]["trailer_offset"] !=
            preload["binding"]["trailer_offset"] or
            foreign_preload["binding"]["trailer_length"] !=
            preload["binding"]["trailer_length"]):
        raise HardwareContractError("mismatch preload binding layout differs from canonical")
    payload_length = preload["payload_length"]
    if foreign[:payload_length] != canonical[:payload_length]:
        raise HardwareContractError("mismatch preload payload differs from canonical")
    return (
        foreign, foreign, None, foreign_build_id, foreign_manifest_sha,
        "verified foreign preload with a different profile build-id",
        details["build_id"],
    )


def _plan(args: argparse.Namespace, manifest: dict[str, Any], oracle: dict[str, Any],
          oracle_sha: str) -> dict[str, Any]:
    package = args.package.resolve()
    payload, effective, clear, foreign_build_id, foreign_manifest_sha, detail, expected_detail = _phase_payload(
        args.phase, package, manifest,
        args.mismatch_package.resolve() if args.mismatch_package else None,
    )
    runtime = oracle["runtime"]
    hardware = oracle["hardware_oracle"]
    state = hardware["symbols"]["state"]
    result = hardware["symbols"]["result"]
    preload_detail = hardware["symbols"]["preload_detail"]
    address = runtime["preload_address"]
    commands = [
        "OPERATOR: power-cycle MEGA65 and acknowledge with a fresh cycle-id",
        f"m65 -H --memsave 0x{address:08x}:0x{address + runtime['preload_length']:08x}=prestage.bin",
    ]
    if clear is not None:
        commands.append(f"m65 -H -@ generated-clear.bin@0x{address:08x}")
    commands.extend((
        f"m65 -H -@ generated-{args.phase}.bin@0x{address:08x}",
        f"m65 -H -1 {package / manifest['runtime']['prg']['path']}",
        f"m65 -H --memsave 0x{address:08x}:0x{address + len(effective):08x}=staged.bin",
        f"m65 -r -1 {package / manifest['runtime']['prg']['path']}",
        f"m65 --memsave 0x{state['address']:08x}:0x{state['address'] + state['size']:08x}=state.bin",
        f"m65 -H --memsave 0x{result['address']:08x}:0x{result['address'] + result['size']:08x}=result.bin",
        f"m65 -H --memsave 0x{preload_detail['address']:08x}:0x{preload_detail['address'] + preload_detail['size']:08x}=preload-detail.bin",
    ))
    return {
        "format": PLAN_FORMAT,
        "gate": "G4",
        "offline": True,
        "side_effects": False,
        "phase": args.phase,
        "manifest_sha256": oracle["manifest_sha256"],
        "oracle_sha256": oracle_sha,
        "profile_build_id": manifest["profile"]["build_id"],
        "foreign_profile_build_id": foreign_build_id,
        "foreign_manifest_sha256": foreign_manifest_sha,
        "mutation": detail,
        "stage_payload": {"length": len(payload), "sha256": _sha(payload)},
        "effective_bank5": {"length": len(effective), "sha256": _sha(effective)},
        "state_address": state["address"],
        "result_address": result["address"],
        "preload_detail_address": preload_detail["address"],
        "expected_preload_detail": expected_detail,
        "commands": commands,
    }


def _load_plan(path: Path) -> dict[str, Any]:
    data = _regular_file(path, "G4 plan").read_bytes()
    try:
        text = data.decode("utf-8")
        start = text.index("{")
        value = json.loads(text[start:], object_pairs_hook=_strict_object)
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise HardwareContractError("G4 plan is not valid strict JSON output") from exc
    return _exact(value, PLAN_KEYS, "G4 plan")


def verify_plan(path: Path, expected_phase: str | None = None) -> dict[str, Any]:
    plan = _load_plan(path)
    phase = plan["phase"]
    if phase not in PHASES or (expected_phase is not None and phase != expected_phase):
        raise HardwareContractError("G4 plan phase differs from the expected phase")
    if (plan["format"] != PLAN_FORMAT or plan["gate"] != "G4" or
            plan["offline"] is not True or plan["side_effects"] is not False):
        raise HardwareContractError("G4 plan is not strict offline/no-side-effect v2")
    for key in ("manifest_sha256", "oracle_sha256"):
        if not isinstance(plan[key], str) or not SHA_RE.fullmatch(plan[key]):
            raise HardwareContractError(f"G4 plan {key} is not a SHA-256")
    if (not isinstance(plan["profile_build_id"], int) or
            isinstance(plan["profile_build_id"], bool)):
        raise HardwareContractError("G4 plan profile build-id is invalid")
    commands = plan["commands"]
    if not isinstance(commands, list) or not commands or any(
        not isinstance(command, str) or not command for command in commands
    ):
        raise HardwareContractError("G4 plan commands are invalid")
    lowered = "\n".join(commands).lower()
    forbidden = ("d81", "attic", "mega65_ftp", "etherload")
    if any(word in lowered for word in forbidden):
        raise HardwareContractError("G4 plan contains a forbidden appliance operation")
    foreign_id = plan["foreign_profile_build_id"]
    foreign_sha = plan["foreign_manifest_sha256"]
    if phase == "build-id-mismatch":
        if (not isinstance(foreign_id, int) or foreign_id == plan["profile_build_id"] or
                not isinstance(foreign_sha, str) or not SHA_RE.fullmatch(foreign_sha)):
            raise HardwareContractError("G4 build-id plan lacks a verified foreign package")
    elif foreign_id is not None or foreign_sha is not None:
        raise HardwareContractError("non-build-id G4 plan carries a foreign package")
    return plan


def verify_plan_suite(paths: list[Path]) -> int:
    if len(paths) != len(PHASES) or len({path.resolve() for path in paths}) != len(PHASES):
        raise HardwareContractError("G4 plan suite requires four distinct paths")
    plans = [verify_plan(path.resolve()) for path in paths]
    if {plan["phase"] for plan in plans} != set(PHASES):
        raise HardwareContractError("G4 plan suite does not cover all four phases")
    identity = (
        plans[0]["manifest_sha256"], plans[0]["oracle_sha256"],
        plans[0]["profile_build_id"],
    )
    if any(
        (plan["manifest_sha256"], plan["oracle_sha256"], plan["profile_build_id"])
        != identity for plan in plans[1:]
    ):
        raise HardwareContractError("G4 plan suite mixes candidate/oracle identities")
    print("runtime-export G5 ready: PASS phases=4 mismatch=verified offline=true")
    return 0


def _tool(tools: Path, name: str) -> Path:
    path = tools / name
    if path.is_symlink() or not path.is_file() or not os.access(path, os.X_OK):
        raise HardwareContractError(f"hardware tool is missing/not executable: {path}")
    return path


def _m65(command: list[str], *, timeout: int, env: dict[str, str]) -> None:
    _run_checked(command, timeout=timeout, env=env)


def _memsave(m65: Path, device: str, address: int, size: int, output: Path,
             *, halted: bool, timeout: int, env: dict[str, str]) -> bytes:
    if output.exists() or output.is_symlink():
        raise HardwareContractError(f"refusing stale readback file: {output}")
    spec = f"0x{address:08x}:0x{address + size:08x}={output}"
    command = [str(m65), "-l", device]
    if halted:
        command.append("-H")
    command.extend(("--memsave", spec))
    _m65(command, timeout=timeout, env=env)
    data = _regular_file(output, "hardware readback").read_bytes()
    if len(data) != size:
        raise HardwareContractError(
            f"hardware readback length mismatch at 0x{address:08x}: expected={size} actual={len(data)}"
        )
    return data


def _evidence(path: Path, role: str) -> dict[str, Any]:
    data = _regular_file(path, role).read_bytes()
    return {"role": role, "file": path.name, "size": len(data), "sha256": _sha(data)}


def _write_json_exclusive(path: Path, value: dict[str, Any]) -> None:
    if path.exists() or path.is_symlink():
        raise HardwareContractError(f"refusing to overwrite {path}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "w", encoding="ascii") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _evaluate(
    phase: str, state: int, result_raw: int, preload_detail: int,
    hardware: dict[str, Any], expected_detail: int,
) -> tuple[bool, str]:
    states = hardware["states"]
    results = hardware["results"]
    details = hardware["preload_details"]
    if phase == "clean":
        if state != states["complete"]:
            return False, f"clean phase state 0x{state:02x} is not COMPLETE"
        if result_raw != results["success_raw"]:
            return False, (
                f"clean phase result 0x{result_raw:04x} != "
                f"0x{results['success_raw']:04x}"
            )
        if preload_detail != details["ok"]:
            return False, f"clean phase preload detail {preload_detail} is not OK"
        return True, "clean runtime completed with the exact result and preload detail"
    if state != states["preload_error"]:
        return False, f"corrupt phase state 0x{state:02x} is not PRELOAD_ERROR"
    if result_raw != results["error_nil_raw"]:
        return False, f"corrupt phase result 0x{result_raw:04x} is not NIL"
    if preload_detail != expected_detail:
        return False, (
            f"corrupt phase detail {preload_detail} differs from expected {expected_detail}"
        )
    return True, "corrupt preload failed closed with exact state, NIL, and detail"


def deploy_g5(args: argparse.Namespace, manifest: dict[str, Any], oracle: dict[str, Any],
              oracle_sha: str) -> int:
    if args.power_cycle_token != "POWER-CYCLED":
        raise HardwareContractError("G5 requires --power-cycle-token POWER-CYCLED")
    if not _valid_cycle_id(args.cycle_id):
        raise HardwareContractError("G5 requires a fresh safe --cycle-id of at least 8 characters")
    payload, effective, clear, foreign_build_id, foreign_manifest_sha, detail, expected_detail = _phase_payload(
        args.phase, args.package.resolve(), manifest,
        args.mismatch_package.resolve() if args.mismatch_package else None,
    )
    m65 = _tool(args.tools, "m65")
    if args.out_dir.exists() or args.out_dir.is_symlink():
        raise HardwareContractError(f"G5 out-dir must be fresh: {args.out_dir}")
    args.out_dir.mkdir(parents=True, exist_ok=False)
    receipt_path = args.out_dir / f"receipt-{args.phase}.json"
    env = os.environ.copy()
    env["RUNTIME_EXPORT_PHASE"] = args.phase
    env["RUNTIME_EXPORT_CYCLE_ID"] = args.cycle_id
    evidence: list[dict[str, Any]] = []
    state_value: int | None = None
    result_raw: int | None = None
    preload_detail_value: int | None = None
    error: str | None = None
    status = "FAIL"
    try:
        runtime = oracle["runtime"]
        address = runtime["preload_address"]
        length = runtime["preload_length"]
        prestage_path = args.out_dir / "prestage-bank5.bin"
        prestage = _memsave(
            m65, args.device, address, length, prestage_path,
            halted=True, timeout=args.timeout, env=env,
        )
        evidence.append(_evidence(prestage_path, "prestage-bank5"))
        if _sha(prestage) == runtime["preload_sha256"]:
            raise HardwareContractError(
                "pre-stage Bank-5 digest equals the manifest-bound target; fresh staging is unproven"
            )

        if clear is not None:
            clear_path = args.out_dir / "clear-bank5.bin"
            clear_path.write_bytes(clear)
            evidence.append(_evidence(clear_path, "clear-bank5"))
            _m65(
                [str(m65), "-l", args.device, "-H", "-@", f"{clear_path}@0x{address:08x}"],
                timeout=args.timeout, env=env,
            )

        payload_path = args.out_dir / f"stage-{args.phase}.bin"
        payload_path.write_bytes(payload)
        evidence.append(_evidence(payload_path, "stage-payload"))
        _m65(
            [str(m65), "-l", args.device, "-H", "-@", f"{payload_path}@0x{address:08x}"],
            timeout=args.timeout, env=env,
        )
        prg = args.package.resolve() / manifest["runtime"]["prg"]["path"]
        _m65(
            [str(m65), "-l", args.device, "-H", "-1", str(prg)],
            timeout=args.timeout, env=env,
        )
        staged_path = args.out_dir / "staged-bank5.bin"
        staged = _memsave(
            m65, args.device, address, length, staged_path,
            halted=True, timeout=args.timeout, env=env,
        )
        evidence.append(_evidence(staged_path, "staged-bank5"))
        if staged != effective:
            raise HardwareContractError("staged Bank-5 readback differs from the planned phase image")

        _m65(
            [str(m65), "-l", args.device, "-r", "-1", str(prg)],
            timeout=args.timeout, env=env,
        )
        hardware = oracle["hardware_oracle"]
        state_record = hardware["symbols"]["state"]
        state_path = args.out_dir / "runtime-state.bin"
        deadline = time.monotonic() + args.runtime_timeout
        while True:
            if state_path.exists():
                state_path.unlink()
            state_bytes = _memsave(
                m65, args.device, state_record["address"], state_record["size"], state_path,
                halted=False, timeout=args.timeout, env=env,
            )
            state_value = state_bytes[0]
            if state_value in (
                hardware["states"]["complete"], hardware["states"]["preload_error"]
            ):
                break
            if time.monotonic() >= deadline:
                raise HardwareContractError(f"runtime did not reach a terminal state: 0x{state_value:02x}")
            time.sleep(args.poll_interval)
        evidence.append(_evidence(state_path, "runtime-state"))
        result_record = hardware["symbols"]["result"]
        result_path = args.out_dir / "runtime-result.bin"
        result_bytes = _memsave(
            m65, args.device, result_record["address"], result_record["size"], result_path,
            halted=True, timeout=args.timeout, env=env,
        )
        evidence.append(_evidence(result_path, "runtime-result"))
        result_raw = int.from_bytes(result_bytes, "little")
        preload_detail_record = hardware["symbols"]["preload_detail"]
        preload_detail_path = args.out_dir / "runtime-preload-detail.bin"
        preload_detail_bytes = _memsave(
            m65, args.device, preload_detail_record["address"],
            preload_detail_record["size"], preload_detail_path,
            halted=True, timeout=args.timeout, env=env,
        )
        evidence.append(_evidence(preload_detail_path, "runtime-preload-detail"))
        preload_detail_value = preload_detail_bytes[0]
        passed, message = _evaluate(
            args.phase, state_value, result_raw, preload_detail_value,
            hardware, expected_detail,
        )
        if not passed:
            raise HardwareContractError(message)
        status = "PASS"
        error = None
    except (HardwareContractError, OSError) as exc:
        error = str(exc)
    operator = {
        "power_cycle_ack": args.power_cycle_token,
        "cycle_id": args.cycle_id,
        "prestage_digest": next(
            (item["sha256"] for item in evidence if item["role"] == "prestage-bank5"), None
        ),
    }
    receipt = {
        "schema": RECEIPT_FORMAT,
        "scope": "runtime-export-g5-single-phase",
        "gate": "G5",
        "phase": args.phase,
        "status": status,
        "manifest_sha256": oracle["manifest_sha256"],
        "oracle_sha256": oracle_sha,
        "profile_build_id": manifest["profile"]["build_id"],
        "foreign_profile_build_id": foreign_build_id,
        "foreign_manifest_sha256": foreign_manifest_sha,
        "operator": operator,
        "addresses": {
            "preload": oracle["runtime"]["preload_address"],
            "state": oracle["hardware_oracle"]["symbols"]["state"]["address"],
            "result": oracle["hardware_oracle"]["symbols"]["result"]["address"],
            "preload_detail": oracle["hardware_oracle"]["symbols"]["preload_detail"]["address"],
        },
        "expected": {
            "state": oracle["hardware_oracle"]["states"][
                "complete" if args.phase == "clean" else "preload_error"
            ],
            "result_raw": oracle["hardware_oracle"]["results"][
                "success_raw" if args.phase == "clean" else "error_nil_raw"
            ],
            "preload_detail": expected_detail,
            "effective_bank5_sha256": _sha(effective),
            "mutation": detail,
        },
        "observed": {
            "state": state_value,
            "result_raw": result_raw,
            "preload_detail": preload_detail_value,
            "result_fixnum": None if result_raw is None or not (result_raw & 1)
            else (result_raw if result_raw < 0x8000 else result_raw - 0x10000) >> 1,
        },
        "evidence": evidence,
        "error": error,
    }
    _write_json_exclusive(receipt_path, receipt)
    if status != "PASS":
        print(f"runtime-export G5 {args.phase}: FAIL: {error}", file=sys.stderr)
        return 1
    verify_receipt(
        args.package.resolve(), args.oracle.resolve(), receipt_path,
        args.mismatch_package.resolve() if args.mismatch_package else None,
    )
    print(
        f"runtime-export G5 {args.phase}: PASS receipt={receipt_path} "
        f"prestage_sha256={operator['prestage_digest']}"
    )
    return 0


def _receipt_evidence(base: Path, entries: Any) -> dict[str, bytes]:
    if not isinstance(entries, list) or not entries:
        raise HardwareContractError("receipt evidence must be a non-empty list")
    result: dict[str, bytes] = {}
    files: set[str] = set()
    for index, record in enumerate(entries):
        record = _exact(record, {"role", "file", "size", "sha256"}, f"receipt.evidence[{index}]")
        role = record["role"]
        filename = record["file"]
        if not isinstance(role, str) or not role or role in result:
            raise HardwareContractError("receipt has an invalid/duplicate evidence role")
        if not isinstance(filename, str) or filename != Path(filename).name or filename in files:
            raise HardwareContractError("receipt has an invalid/duplicate evidence filename")
        path = _regular_file(base / filename, f"receipt evidence {role}")
        data = path.read_bytes()
        if record["size"] != len(data) or record["sha256"] != _sha(data):
            raise HardwareContractError(f"receipt evidence hash/size mismatch: {role}")
        files.add(filename)
        result[role] = data
    return result


def verify_receipt(
    package: Path, oracle_path: Path, receipt_path: Path,
    mismatch_package: Path | None = None,
) -> int:
    manifest, oracle, oracle_sha = verify_oracle(package, oracle_path)
    receipt = _exact(_load_json(receipt_path, "G5 receipt"), RECEIPT_KEYS, "receipt")
    if (receipt["schema"] != RECEIPT_FORMAT or receipt["scope"] != "runtime-export-g5-single-phase" or
            receipt["gate"] != "G5" or receipt["status"] != "PASS"):
        raise HardwareContractError("receipt is not a passing Runtime Export G5 phase")
    phase = receipt["phase"]
    if phase not in PHASES:
        raise HardwareContractError("receipt has an unknown phase")
    if receipt["manifest_sha256"] != oracle["manifest_sha256"] or receipt["oracle_sha256"] != oracle_sha:
        raise HardwareContractError("receipt package/oracle binding mismatch")
    if receipt["profile_build_id"] != manifest["profile"]["build_id"]:
        raise HardwareContractError("receipt profile build-id mismatch")
    foreign = receipt["foreign_profile_build_id"]
    foreign_manifest_sha = receipt["foreign_manifest_sha256"]
    if phase == "build-id-mismatch":
        if not isinstance(foreign, int) or foreign == receipt["profile_build_id"]:
            raise HardwareContractError("build-id mismatch receipt lacks a foreign build-id")
        if mismatch_package is None and manifest["format"] != INTERNAL_V2_PACKAGE_FORMAT:
            raise HardwareContractError("build-id mismatch receipt verification requires --mismatch-package")
    elif foreign is not None or foreign_manifest_sha is not None or mismatch_package is not None:
        raise HardwareContractError("non-build-id phase carries a foreign package binding")
    operator = _exact(receipt["operator"], {"power_cycle_ack", "cycle_id", "prestage_digest"}, "receipt.operator")
    if operator["power_cycle_ack"] != "POWER-CYCLED" or not _valid_cycle_id(operator["cycle_id"]):
        raise HardwareContractError("receipt lacks the explicit operator power-cycle acknowledgement")
    hardware = oracle["hardware_oracle"]
    addresses = _exact(
        receipt["addresses"], {"preload", "state", "result", "preload_detail"},
        "receipt.addresses",
    )
    if addresses != {
        "preload": oracle["runtime"]["preload_address"],
        "state": hardware["symbols"]["state"]["address"],
        "result": hardware["symbols"]["result"]["address"],
        "preload_detail": hardware["symbols"]["preload_detail"]["address"],
    }:
        raise HardwareContractError("receipt address binding mismatch")
    expected = _exact(
        receipt["expected"],
        {"state", "result_raw", "preload_detail", "effective_bank5_sha256", "mutation"},
        "receipt.expected",
    )
    observed = _exact(
        receipt["observed"], {"state", "result_raw", "result_fixnum", "preload_detail"},
        "receipt.observed",
    )
    evidence = _receipt_evidence(receipt_path.parent, receipt["evidence"])
    required_roles = {
        "prestage-bank5", "stage-payload", "staged-bank5", "runtime-state",
        "runtime-result", "runtime-preload-detail",
    }
    if phase == "truncated":
        required_roles.add("clear-bank5")
    if set(evidence) != required_roles:
        raise HardwareContractError(
            f"receipt evidence role mismatch: expected={sorted(required_roles)} actual={sorted(evidence)}"
        )
    payload, effective, clear, planned_foreign_id, planned_foreign_sha, detail, expected_detail = _phase_payload(
        phase, package, manifest, mismatch_package,
    )
    if foreign != planned_foreign_id or foreign_manifest_sha != planned_foreign_sha:
        raise HardwareContractError("receipt foreign package binding mismatch")
    if evidence["stage-payload"] != payload:
        raise HardwareContractError("receipt stage payload differs from the approved phase mutation")
    if phase == "truncated" and evidence["clear-bank5"] != clear:
        raise HardwareContractError("receipt clear image differs from the approved truncation setup")
    if evidence["staged-bank5"] != effective:
        raise HardwareContractError("receipt staged Bank-5 image differs from the approved phase image")
    if expected["effective_bank5_sha256"] != _sha(effective) or expected["mutation"] != detail:
        raise HardwareContractError("receipt mutation description/digest mismatch")
    if operator["prestage_digest"] != _sha(evidence["prestage-bank5"]):
        raise HardwareContractError("receipt pre-stage digest mismatch")
    if operator["prestage_digest"] == oracle["runtime"]["preload_sha256"]:
        raise HardwareContractError("receipt pre-stage digest equals the manifest-bound target")
    if len(evidence["prestage-bank5"]) != oracle["runtime"]["preload_length"]:
        raise HardwareContractError("receipt pre-stage span length mismatch")
    if _sha(evidence["staged-bank5"]) != expected["effective_bank5_sha256"]:
        raise HardwareContractError("receipt staged Bank-5 digest mismatch")
    if (len(evidence["runtime-state"]) != hardware["symbols"]["state"]["size"] or
            len(evidence["runtime-result"]) != hardware["symbols"]["result"]["size"] or
            len(evidence["runtime-preload-detail"]) !=
            hardware["symbols"]["preload_detail"]["size"]):
        raise HardwareContractError("receipt hardware readback sizes are invalid")
    state = int.from_bytes(evidence["runtime-state"], "little")
    result = int.from_bytes(evidence["runtime-result"], "little")
    preload_detail = int.from_bytes(evidence["runtime-preload-detail"], "little")
    if (observed["state"] != state or observed["result_raw"] != result or
            observed["preload_detail"] != preload_detail):
        raise HardwareContractError("receipt observation differs from raw readback")
    decoded_fixnum = None if not (result & 1) else (
        (result if result < 0x8000 else result - 0x10000) >> 1
    )
    if observed["result_fixnum"] != decoded_fixnum:
        raise HardwareContractError("receipt decoded fixnum differs from the raw result")
    expected_values = {
        "state": hardware["states"]["complete" if phase == "clean" else "preload_error"],
        "result_raw": hardware["results"][
            "success_raw" if phase == "clean" else "error_nil_raw"
        ],
        "preload_detail": expected_detail,
    }
    if any(expected[key] != value for key, value in expected_values.items()):
        raise HardwareContractError("receipt expected hardware verdict differs from manifest-v2")
    passed, message = _evaluate(
        phase, state, result, preload_detail, hardware, expected_detail
    )
    if not passed or receipt["error"] is not None:
        raise HardwareContractError(f"receipt verdict is invalid: {message}")
    expected_files = {record["file"] for record in receipt["evidence"]} | {receipt_path.name}
    actual_files = {item.name for item in receipt_path.parent.iterdir() if item.is_file()}
    if actual_files != expected_files:
        raise HardwareContractError(
            f"receipt evidence inventory mismatch: expected={sorted(expected_files)} actual={sorted(actual_files)}"
        )
    print(f"runtime-export-hw receipt verify: PASS phase={phase} receipt={receipt_path}")
    return 0


def verify_suite(
    package: Path, oracle_path: Path, receipt_paths: list[Path], mismatch_package: Path | None,
) -> int:
    manifest, _oracle, _oracle_sha = verify_oracle(package.resolve(), oracle_path.resolve())
    if manifest["format"] != INTERNAL_V2_PACKAGE_FORMAT and mismatch_package is None:
        raise HardwareContractError("Runtime Export G5 suite requires --mismatch-package")
    if len(receipt_paths) != len(PHASES):
        raise HardwareContractError("G5 suite requires exactly four receipt paths")
    resolved = [path.resolve() for path in receipt_paths]
    if len(set(resolved)) != len(resolved):
        raise HardwareContractError("G5 suite receipt paths must be distinct")
    by_phase: dict[str, Path] = {}
    cycle_ids: set[str] = set()
    for path in resolved:
        _regular_file(path, "G5 suite receipt")
        receipt = _exact(_load_json(path, "G5 suite receipt"), RECEIPT_KEYS, "receipt")
        phase = receipt.get("phase")
        if phase not in PHASES or phase in by_phase:
            raise HardwareContractError("G5 suite has an unknown/duplicate phase")
        if receipt.get("status") != "PASS":
            raise HardwareContractError("G5 suite contains a non-passing receipt")
        operator = _exact(
            receipt.get("operator"), {"power_cycle_ack", "cycle_id", "prestage_digest"},
            "receipt.operator",
        )
        cycle_id = operator.get("cycle_id")
        if not _valid_cycle_id(cycle_id) or cycle_id in cycle_ids:
            raise HardwareContractError("G5 suite cycle ids must be valid and distinct")
        cycle_ids.add(cycle_id)
        by_phase[phase] = path
    if set(by_phase) != set(PHASES):
        raise HardwareContractError("G5 suite does not cover each required phase exactly once")
    for phase in PHASES:
        verify_receipt(
            package.resolve(), oracle_path.resolve(), by_phase[phase],
            mismatch_package.resolve() if phase == "build-id-mismatch" and mismatch_package else None,
        )
    print(
        "runtime-export-hw suite verify: PASS phases=4 cycle_ids=4 "
        f"package={package} mismatch_package={mismatch_package or 'embedded-v2-phase'}"
    )
    return 0


def deploy(args: argparse.Namespace) -> int:
    manifest, oracle, oracle_sha = verify_oracle(args.package.resolve(), args.oracle.resolve())
    internal_v2 = manifest["format"] == INTERNAL_V2_PACKAGE_FORMAT
    if args.phase == "build-id-mismatch" and args.mismatch_package is None and not internal_v2:
        raise HardwareContractError("build-id-mismatch requires --mismatch-package")
    if (args.phase != "build-id-mismatch" or internal_v2) and args.mismatch_package is not None:
        raise HardwareContractError("--mismatch-package is only valid for build-id-mismatch")
    if args.gate == "G4":
        plan = _plan(args, manifest, oracle, oracle_sha)
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0
    return deploy_g5(args, manifest, oracle, oracle_sha)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--package", type=Path, required=True)
    create.add_argument("--elf", type=Path, required=True)
    create.add_argument("--nm", type=Path, required=True)
    create.add_argument("--objcopy", type=Path, required=True)
    create.add_argument("--out", type=Path, required=True)
    mismatch = sub.add_parser("create-mismatch-package")
    mismatch.add_argument("--package", type=Path, required=True)
    mismatch.add_argument("--out", type=Path, required=True)
    mismatch.add_argument("--profile-id")
    verify = sub.add_parser("verify")
    verify.add_argument("--package", type=Path, required=True)
    verify.add_argument("--oracle", type=Path, required=True)
    plan = sub.add_parser("verify-plan")
    plan.add_argument("--plan", type=Path, required=True)
    plan.add_argument("--phase", choices=PHASES)
    plan_suite = sub.add_parser("verify-plan-suite")
    plan_suite.add_argument("--plan", type=Path, action="append", required=True)
    receipt = sub.add_parser("verify-receipt")
    receipt.add_argument("--package", type=Path, required=True)
    receipt.add_argument("--oracle", type=Path, required=True)
    receipt.add_argument("--receipt", type=Path, required=True)
    receipt.add_argument("--mismatch-package", type=Path)
    suite = sub.add_parser("verify-suite")
    suite.add_argument("--package", type=Path, required=True)
    suite.add_argument("--oracle", type=Path, required=True)
    suite.add_argument("--receipt", type=Path, action="append", required=True)
    suite.add_argument("--mismatch-package", type=Path)
    deploy_parser = sub.add_parser("deploy")
    deploy_parser.add_argument("--gate", choices=("G4", "G5"), required=True)
    deploy_parser.add_argument("--phase", choices=PHASES, required=True)
    deploy_parser.add_argument("--package", type=Path, required=True)
    deploy_parser.add_argument("--oracle", type=Path, required=True)
    deploy_parser.add_argument("--mismatch-package", type=Path)
    deploy_parser.add_argument("--out-dir", type=Path, required=True)
    deploy_parser.add_argument("--tools", type=Path, default=Path("tools/m65tools"))
    deploy_parser.add_argument("--device", default="/dev/ttyUSB1")
    deploy_parser.add_argument("--power-cycle-token")
    deploy_parser.add_argument("--cycle-id")
    deploy_parser.add_argument("--timeout", type=int, default=30)
    deploy_parser.add_argument("--runtime-timeout", type=int, default=15)
    deploy_parser.add_argument("--poll-interval", type=float, default=0.25)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "create":
            return create_oracle(args.package, args.elf, args.nm, args.objcopy, args.out)
        if args.command == "create-mismatch-package":
            return create_mismatch_package(args.package, args.out, args.profile_id)
        if args.command == "verify":
            verify_oracle(args.package.resolve(), args.oracle.resolve())
            return 0
        if args.command == "verify-plan":
            plan = verify_plan(args.plan.resolve(), args.phase)
            print(f"runtime-export G4 plan verify: PASS phase={plan['phase']} plan={args.plan}")
            return 0
        if args.command == "verify-plan-suite":
            return verify_plan_suite(args.plan)
        if args.command == "verify-receipt":
            return verify_receipt(
                args.package.resolve(), args.oracle.resolve(), args.receipt.resolve(),
                args.mismatch_package.resolve() if args.mismatch_package else None,
            )
        if args.command == "verify-suite":
            return verify_suite(
                args.package, args.oracle, args.receipt, args.mismatch_package,
            )
        if args.timeout <= 0 or args.runtime_timeout <= 0 or args.poll_interval < 0:
            raise HardwareContractError("timeouts must be positive and poll interval nonnegative")
        return deploy(args)
    except (HardwareContractError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"runtime-export-hw: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
