#!/usr/bin/env python3
"""Pack and verify profile-bound lisp65 Bank-0 overlay artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile
from typing import Any, Callable, Sequence


SCHEMA = "lisp65-profile-overlay-v1"
MANIFEST_NAME = "manifest.json"
OVERLAY_NAME = "overlay.bin"
BANK0_LIMIT = 0x10000
MEGA65_ADDRESS_LIMIT = 0x10000000
SHA256_HEX_LENGTH = 64
TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
MANIFEST_FIELDS = {
    "schema",
    "profile",
    "overlay",
    "base",
    "end",
    "size",
    "entry",
    "entry_symbol",
    "sha256",
    "load",
    "lifetime",
    "resident",
    "abi",
}
ABI_FIELDS = {"contract_id", "contract_sha256", "resident_sha256"}
LOAD_FIELDS = {"base", "mode", "staging"}
LIFETIME_FIELDS = {"class", "reclaim_point"}
RESIDENT_FIELDS = {"load_base", "file_end"}


class OverlayPackageError(RuntimeError):
    """A user-facing package or binding error."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _valid_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == SHA256_HEX_LENGTH
        and value == value.lower()
        and all(character in "0123456789abcdef" for character in value)
    )


def _valid_token(value: Any) -> bool:
    return isinstance(value, str) and TOKEN_RE.fullmatch(value) is not None


def _regular_file(path: Path, label: str) -> os.stat_result:
    try:
        info = path.lstat()
    except OSError as exc:
        raise OverlayPackageError(f"{label} is missing or unreadable: {path}: {exc}") from exc
    if stat.S_ISLNK(info.st_mode):
        raise OverlayPackageError(f"{label} must not be a symlink: {path}")
    if not stat.S_ISREG(info.st_mode):
        raise OverlayPackageError(f"{label} must be a regular file: {path}")
    return info


def _package_dir(path: Path) -> Path:
    try:
        info = path.lstat()
    except OSError as exc:
        raise OverlayPackageError(
            f"package directory is missing or unreadable: {path}: {exc}"
        ) from exc
    if stat.S_ISLNK(info.st_mode):
        raise OverlayPackageError(f"package directory must not be a symlink: {path}")
    if not stat.S_ISDIR(info.st_mode):
        raise OverlayPackageError(f"package path is not a directory: {path}")
    return path


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise OverlayPackageError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except OverlayPackageError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OverlayPackageError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise OverlayPackageError("overlay manifest root must be an object")
    return value


def _write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    with path.open("w", encoding="ascii", newline="\n") as output:
        json.dump(manifest, output, indent=2, sort_keys=True)
        output.write("\n")


def _address_errors(
    base: Any,
    end: Any,
    size: Any,
    entry: Any,
    load_base: Any,
) -> list[str]:
    errors: list[str] = []
    if type(base) is not int or not 0 <= base < BANK0_LIMIT:
        errors.append("base must be a Bank-0 integer in the range 0..65535")
    if type(size) is not int or size <= 0:
        errors.append("size must be a positive integer")
    if type(end) is not int or not 0 < end <= BANK0_LIMIT:
        errors.append("end must be a Bank-0 integer in the range 1..65536")
    if type(entry) is not int or not 0 <= entry < BANK0_LIMIT:
        errors.append("entry must be a Bank-0 integer in the range 0..65535")
    if type(base) is int and type(size) is int and size > 0:
        calculated_end = base + size
        if calculated_end > BANK0_LIMIT:
            errors.append("overlay span exceeds Bank 0")
        if type(end) is int and end != calculated_end:
            errors.append("end must equal base plus size")
        if type(entry) is int and not base <= entry < calculated_end:
            errors.append("entry must lie inside the overlay span")
    if type(load_base) is not int or not 0 <= load_base < MEGA65_ADDRESS_LIMIT:
        errors.append("load.base must be a MEGA65 integer address")
    elif type(size) is int and size > 0 and load_base + size > MEGA65_ADDRESS_LIMIT:
        errors.append("load span exceeds the MEGA65 address space")
    return errors


def _resident_errors(resident: Any) -> list[str]:
    if not isinstance(resident, dict):
        return ["resident must be an object"]
    errors: list[str] = []
    if set(resident) != RESIDENT_FIELDS:
        missing = sorted(RESIDENT_FIELDS - resident.keys())
        extra = sorted(resident.keys() - RESIDENT_FIELDS)
        if missing:
            errors.append(f"resident fields missing: {','.join(missing)}")
        if extra:
            errors.append(f"unexpected resident fields: {','.join(extra)}")
    load_base = resident.get("load_base")
    file_end = resident.get("file_end")
    if type(load_base) is not int or not 0 <= load_base < BANK0_LIMIT:
        errors.append("resident.load_base must be a Bank-0 integer in the range 0..65535")
    if type(file_end) is not int or not 0 < file_end <= BANK0_LIMIT:
        errors.append("resident.file_end must be a Bank-0 integer in the range 1..65536")
    if type(load_base) is int and type(file_end) is int and file_end <= load_base:
        errors.append("resident.file_end must be above resident.load_base")
    return errors


def _manifest_errors(package_dir: Path, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if set(manifest) != MANIFEST_FIELDS:
        missing = sorted(MANIFEST_FIELDS - manifest.keys())
        extra = sorted(manifest.keys() - MANIFEST_FIELDS)
        if missing:
            errors.append(f"manifest fields missing: {','.join(missing)}")
        if extra:
            errors.append(f"unexpected manifest fields: {','.join(extra)}")
    if manifest.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    if not _valid_token(manifest.get("profile")):
        errors.append("profile must be a non-empty ASCII identifier")
    if manifest.get("overlay") != OVERLAY_NAME:
        errors.append(f"overlay must be {OVERLAY_NAME}")
    load = manifest.get("load")
    load_base = load.get("base") if isinstance(load, dict) else None
    errors.extend(
        _address_errors(
            manifest.get("base"),
            manifest.get("end"),
            manifest.get("size"),
            manifest.get("entry"),
            load_base,
        )
    )
    if not _valid_sha256(manifest.get("sha256")):
        errors.append("sha256 must be a lowercase SHA-256")
    if not _valid_token(manifest.get("entry_symbol")):
        errors.append("entry_symbol must be a non-empty ASCII identifier")

    if not isinstance(load, dict):
        errors.append("load must be an object")
    else:
        if set(load) != LOAD_FIELDS:
            missing = sorted(LOAD_FIELDS - load.keys())
            extra = sorted(load.keys() - LOAD_FIELDS)
            if missing:
                errors.append(f"load fields missing: {','.join(missing)}")
            if extra:
                errors.append(f"unexpected load fields: {','.join(extra)}")
        if not _valid_token(load.get("mode")):
            errors.append("load.mode must be a non-empty ASCII identifier")
        if not _valid_token(load.get("staging")):
            errors.append("load.staging must be a non-empty ASCII identifier")

    lifetime = manifest.get("lifetime")
    if not isinstance(lifetime, dict):
        errors.append("lifetime must be an object")
    else:
        if set(lifetime) != LIFETIME_FIELDS:
            missing = sorted(LIFETIME_FIELDS - lifetime.keys())
            extra = sorted(lifetime.keys() - LIFETIME_FIELDS)
            if missing:
                errors.append(f"lifetime fields missing: {','.join(missing)}")
            if extra:
                errors.append(f"unexpected lifetime fields: {','.join(extra)}")
        if not _valid_token(lifetime.get("class")):
            errors.append("lifetime.class must be a non-empty ASCII identifier")
        if not _valid_token(lifetime.get("reclaim_point")):
            errors.append("lifetime.reclaim_point must be a non-empty ASCII identifier")

    errors.extend(_resident_errors(manifest.get("resident")))

    abi = manifest.get("abi")
    if not isinstance(abi, dict):
        errors.append("abi must be an object")
    else:
        if set(abi) != ABI_FIELDS:
            missing = sorted(ABI_FIELDS - abi.keys())
            extra = sorted(abi.keys() - ABI_FIELDS)
            if missing:
                errors.append(f"abi fields missing: {','.join(missing)}")
            if extra:
                errors.append(f"unexpected abi fields: {','.join(extra)}")
        if not _valid_token(abi.get("contract_id")):
            errors.append("abi.contract_id must be a non-empty ASCII identifier")
        if not _valid_sha256(abi.get("contract_sha256")):
            errors.append("abi.contract_sha256 must be a lowercase SHA-256")
        if not _valid_sha256(abi.get("resident_sha256")):
            errors.append("abi.resident_sha256 must be a lowercase SHA-256")

    try:
        entries = {entry.name for entry in package_dir.iterdir()}
    except OSError as exc:
        errors.append(f"cannot list package directory: {exc}")
        return errors
    expected_entries = {MANIFEST_NAME, OVERLAY_NAME}
    extra_entries = sorted(entries - expected_entries)
    missing_entries = sorted(expected_entries - entries)
    if extra_entries:
        errors.append(f"unexpected package entries: {','.join(extra_entries)}")
    if missing_entries:
        errors.append(f"package entries missing: {','.join(missing_entries)}")

    overlay_path = package_dir / OVERLAY_NAME
    try:
        info = _regular_file(overlay_path, "overlay artifact")
    except OverlayPackageError as exc:
        errors.append(str(exc))
    else:
        size = manifest.get("size")
        if type(size) is int and info.st_size != size:
            errors.append(f"overlay size mismatch: manifest={size} actual={info.st_size}")
        expected_hash = manifest.get("sha256")
        if _valid_sha256(expected_hash):
            actual_hash = _sha256(overlay_path)
            if actual_hash != expected_hash:
                errors.append(
                    f"overlay SHA-256 mismatch: manifest={expected_hash} actual={actual_hash}"
                )
    return errors


def verify_package(
    package_dir: Path,
    *,
    profile: str | None = None,
    base: int | None = None,
    end: int | None = None,
    entry: int | None = None,
    entry_symbol: str | None = None,
    load_base: int | None = None,
    load_mode: str | None = None,
    staging_mode: str | None = None,
    lifetime: str | None = None,
    reclaim_point: str | None = None,
    abi_id: str | None = None,
    resident: Path | None = None,
    resident_load_base: int | None = None,
    resident_file_end: int | None = None,
    abi_contract: Path | None = None,
    strict: bool = False,
) -> list[str]:
    expected = (
        profile,
        base,
        end,
        entry,
        entry_symbol,
        load_base,
        load_mode,
        staging_mode,
        lifetime,
        reclaim_point,
        abi_id,
        resident,
        resident_load_base,
        resident_file_end,
        abi_contract,
    )
    supplied = [value is not None for value in expected]
    if strict and not all(supplied):
        return ["strict verification requires all profile, address, and ABI binding inputs"]
    if any(supplied) and not all(supplied):
        return ["binding inputs must be supplied together"]

    try:
        package_dir = _package_dir(package_dir)
        manifest_path = package_dir / MANIFEST_NAME
        _regular_file(manifest_path, "overlay manifest")
        manifest = _read_manifest(manifest_path)
    except OverlayPackageError as exc:
        return [str(exc)]

    errors = _manifest_errors(package_dir, manifest)
    if all(supplied):
        assert profile is not None
        assert base is not None
        assert end is not None
        assert entry is not None
        assert entry_symbol is not None
        assert load_base is not None
        assert load_mode is not None
        assert staging_mode is not None
        assert lifetime is not None
        assert reclaim_point is not None
        assert abi_id is not None
        assert resident is not None
        assert resident_load_base is not None
        assert resident_file_end is not None
        assert abi_contract is not None
        if manifest.get("profile") != profile:
            errors.append(
                f"profile binding mismatch: manifest={manifest.get('profile')!r} expected={profile!r}"
            )
        if manifest.get("base") != base:
            errors.append(
                f"base binding mismatch: manifest={manifest.get('base')!r} expected={base!r}"
            )
        if manifest.get("end") != end:
            errors.append(
                f"end binding mismatch: manifest={manifest.get('end')!r} expected={end!r}"
            )
        if manifest.get("entry") != entry:
            errors.append(
                f"entry binding mismatch: manifest={manifest.get('entry')!r} expected={entry!r}"
            )
        if manifest.get("entry_symbol") != entry_symbol:
            errors.append(
                "entry symbol binding mismatch: "
                f"manifest={manifest.get('entry_symbol')!r} expected={entry_symbol!r}"
            )
        load = manifest.get("load")
        if isinstance(load, dict):
            if load.get("base") != load_base:
                errors.append(
                    f"load base binding mismatch: manifest={load.get('base')!r} "
                    f"expected={load_base!r}"
                )
            if load.get("mode") != load_mode:
                errors.append(
                    f"load mode binding mismatch: manifest={load.get('mode')!r} "
                    f"expected={load_mode!r}"
                )
            if load.get("staging") != staging_mode:
                errors.append(
                    f"staging mode binding mismatch: manifest={load.get('staging')!r} "
                    f"expected={staging_mode!r}"
                )
        lifetime_record = manifest.get("lifetime")
        if isinstance(lifetime_record, dict):
            if lifetime_record.get("class") != lifetime:
                errors.append(
                    f"lifetime binding mismatch: manifest={lifetime_record.get('class')!r} "
                    f"expected={lifetime!r}"
                )
            if lifetime_record.get("reclaim_point") != reclaim_point:
                errors.append(
                    "reclaim-point binding mismatch: "
                    f"manifest={lifetime_record.get('reclaim_point')!r} "
                    f"expected={reclaim_point!r}"
                )
        resident_record = manifest.get("resident")
        if isinstance(resident_record, dict):
            if resident_record.get("load_base") != resident_load_base:
                errors.append(
                    "resident load-base binding mismatch: "
                    f"manifest={resident_record.get('load_base')!r} "
                    f"expected={resident_load_base!r}"
                )
            if resident_record.get("file_end") != resident_file_end:
                errors.append(
                    "resident file-end binding mismatch: "
                    f"manifest={resident_record.get('file_end')!r} "
                    f"expected={resident_file_end!r}"
                )
        abi = manifest.get("abi")
        if isinstance(abi, dict):
            if abi.get("contract_id") != abi_id:
                errors.append(
                    "ABI contract binding mismatch: "
                    f"manifest={abi.get('contract_id')!r} expected={abi_id!r}"
                )
            try:
                resident_path = _regular_path(resident, "resident artifact")
                resident_hash = _sha256(resident_path)
            except OverlayPackageError as exc:
                errors.append(str(exc))
            else:
                if abi.get("resident_sha256") != resident_hash:
                    errors.append("resident artifact binding mismatch")
                expected_resident_size = resident_file_end - resident_load_base + 2
                if resident_path.stat().st_size != expected_resident_size:
                    errors.append(
                        "resident PRG span mismatch: "
                        f"addresses imply {expected_resident_size} bytes, "
                        f"actual={resident_path.stat().st_size}"
                    )
            try:
                contract_hash = _sha256(_regular_path(abi_contract, "ABI contract"))
            except OverlayPackageError as exc:
                errors.append(str(exc))
            else:
                if abi.get("contract_sha256") != contract_hash:
                    errors.append("ABI contract content binding mismatch")
    return errors


def _regular_path(path: Path, label: str) -> Path:
    _regular_file(path, label)
    return path


def _replace_package(staged: Path, output_dir: Path) -> None:
    if output_dir.is_symlink():
        raise OverlayPackageError(f"output directory must not be a symlink: {output_dir}")
    if not output_dir.exists():
        staged.rename(output_dir)
        return
    _package_dir(output_dir)
    backup = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.old.", dir=output_dir.parent))
    backup.rmdir()
    output_dir.rename(backup)
    try:
        staged.rename(output_dir)
    except BaseException:
        backup.rename(output_dir)
        raise
    shutil.rmtree(backup)


def pack_package(
    overlay: Path,
    output_dir: Path,
    *,
    profile: str,
    base: int,
    end: int,
    entry: int,
    entry_symbol: str,
    load_base: int,
    load_mode: str,
    staging_mode: str,
    lifetime: str,
    reclaim_point: str,
    abi_id: str,
    resident: Path,
    resident_load_base: int,
    resident_file_end: int,
    abi_contract: Path,
) -> None:
    overlay_info = _regular_file(overlay, "overlay input")
    _regular_file(resident, "resident artifact")
    _regular_file(abi_contract, "ABI contract")
    if not _valid_token(profile):
        raise OverlayPackageError("profile must be a non-empty ASCII identifier")
    token_values = {
        "entry symbol": entry_symbol,
        "load mode": load_mode,
        "staging mode": staging_mode,
        "lifetime": lifetime,
        "reclaim point": reclaim_point,
        "ABI contract ID": abi_id,
    }
    invalid_tokens = [label for label, value in token_values.items() if not _valid_token(value)]
    if invalid_tokens:
        raise OverlayPackageError(
            ", ".join(invalid_tokens) + " must be non-empty ASCII identifiers"
        )
    address_errors = _address_errors(base, end, overlay_info.st_size, entry, load_base)
    if address_errors:
        raise OverlayPackageError("; ".join(address_errors))
    resident_errors = _resident_errors(
        {"load_base": resident_load_base, "file_end": resident_file_end}
    )
    if resident_errors:
        raise OverlayPackageError("; ".join(resident_errors))
    expected_resident_size = resident_file_end - resident_load_base + 2
    if resident.stat().st_size != expected_resident_size:
        raise OverlayPackageError(
            "resident PRG span mismatch: "
            f"addresses imply {expected_resident_size} bytes, actual={resident.stat().st_size}"
        )

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.new.", dir=output_dir.parent))
    try:
        shutil.copyfile(overlay, staged / OVERLAY_NAME)
        manifest = {
            "schema": SCHEMA,
            "profile": profile,
            "overlay": OVERLAY_NAME,
            "base": base,
            "end": end,
            "size": overlay_info.st_size,
            "entry": entry,
            "entry_symbol": entry_symbol,
            "sha256": _sha256(staged / OVERLAY_NAME),
            "load": {
                "base": load_base,
                "mode": load_mode,
                "staging": staging_mode,
            },
            "lifetime": {
                "class": lifetime,
                "reclaim_point": reclaim_point,
            },
            "resident": {
                "load_base": resident_load_base,
                "file_end": resident_file_end,
            },
            "abi": {
                "contract_id": abi_id,
                "contract_sha256": _sha256(abi_contract),
                "resident_sha256": _sha256(resident),
            },
        }
        _write_manifest(staged / MANIFEST_NAME, manifest)
        errors = verify_package(
            staged,
            profile=profile,
            base=base,
            end=end,
            entry=entry,
            entry_symbol=entry_symbol,
            load_base=load_base,
            load_mode=load_mode,
            staging_mode=staging_mode,
            lifetime=lifetime,
            reclaim_point=reclaim_point,
            abi_id=abi_id,
            resident=resident,
            resident_load_base=resident_load_base,
            resident_file_end=resident_file_end,
            abi_contract=abi_contract,
            strict=True,
        )
        if errors:
            raise OverlayPackageError("generated package did not verify: " + "; ".join(errors))
        _replace_package(staged, output_dir)
    except BaseException:
        shutil.rmtree(staged, ignore_errors=True)
        raise


def _copy_case(base: Path, root: Path, name: str) -> Path:
    target = root / name
    shutil.copytree(base, target)
    return target


def _expect_verify_failure(
    failures: list[str],
    name: str,
    package_dir: Path,
    verify: Callable[[Path], list[str]],
) -> None:
    errors = verify(package_dir)
    if not errors:
        failures.append(f"{name}: expected verification failure")


def selftest() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="lisp65-overlay-package-") as temporary_name:
        root = Path(temporary_name)
        overlay = root / "input.bin"
        resident = root / "resident.prg"
        contract = root / "abi.txt"
        overlay.write_bytes(bytes(range(1, 65)))
        resident.write_bytes(b"resident-build\n")
        contract.write_bytes(b"lisp65-bank0-overlay-abi-v1\ncall=fastcall\n")
        profile = "runtime-core"
        base = 0x8000
        end = 0x8040
        entry = 0x8010
        entry_symbol = "vm_load_embedded_stdlib"
        load_base = 0x8000
        load_mode = "fixed-vma-raw"
        staging_mode = "separate-image"
        lifetime = "boot-only"
        reclaim_point = "before-deep-stack"
        abi_id = "lisp65-bank0-overlay-abi-v1"
        resident_load_base = 0x2001
        resident_file_end = resident_load_base + resident.stat().st_size - 2

        package_a = root / "package-a"
        package_b = root / "package-b"
        for package in (package_a, package_b):
            try:
                pack_package(
                    overlay,
                    package,
                    profile=profile,
                    base=base,
                    end=end,
                    entry=entry,
                    entry_symbol=entry_symbol,
                    load_base=load_base,
                    load_mode=load_mode,
                    staging_mode=staging_mode,
                    lifetime=lifetime,
                    reclaim_point=reclaim_point,
                    abi_id=abi_id,
                    resident=resident,
                    resident_load_base=resident_load_base,
                    resident_file_end=resident_file_end,
                    abi_contract=contract,
                )
            except OverlayPackageError as exc:
                failures.append(f"valid-pack-{package.name}: {exc}")

        def strict_verify(package: Path) -> list[str]:
            return verify_package(
                package,
                profile=profile,
                base=base,
                end=end,
                entry=entry,
                entry_symbol=entry_symbol,
                load_base=load_base,
                load_mode=load_mode,
                staging_mode=staging_mode,
                lifetime=lifetime,
                reclaim_point=reclaim_point,
                abi_id=abi_id,
                resident=resident,
                resident_load_base=resident_load_base,
                resident_file_end=resident_file_end,
                abi_contract=contract,
                strict=True,
            )

        if package_a.exists():
            errors = strict_verify(package_a)
            if errors:
                failures.append("valid-strict: " + "; ".join(errors))
        if package_a.exists() and package_b.exists():
            if (package_a / MANIFEST_NAME).read_bytes() != (package_b / MANIFEST_NAME).read_bytes():
                failures.append("deterministic-manifest: generated manifests differ")

        cases = root / "cases"
        cases.mkdir()
        if package_a.exists():
            target = _copy_case(package_a, cases, "byte-mutation")
            content = bytearray((target / OVERLAY_NAME).read_bytes())
            content[0] ^= 0x01
            (target / OVERLAY_NAME).write_bytes(content)
            _expect_verify_failure(failures, "byte-mutation", target, strict_verify)

            target = _copy_case(package_a, cases, "truncated")
            (target / OVERLAY_NAME).write_bytes((target / OVERLAY_NAME).read_bytes()[:-1])
            _expect_verify_failure(failures, "truncated", target, strict_verify)

            target = _copy_case(package_a, cases, "extra-file")
            (target / "undeclared.bin").write_bytes(b"extra\n")
            _expect_verify_failure(failures, "extra-file", target, strict_verify)

            target = _copy_case(package_a, cases, "symlink-overlay")
            (target / OVERLAY_NAME).unlink()
            (target / OVERLAY_NAME).symlink_to(overlay)
            _expect_verify_failure(failures, "symlink-overlay", target, strict_verify)

            for name, mutate in (
                ("schema", lambda value: value.__setitem__("schema", "wrong-v1")),
                ("profile", lambda value: value.__setitem__("profile", "other-profile")),
                ("base", lambda value: value.__setitem__("base", base + 1)),
                ("end", lambda value: value.__setitem__("end", end + 1)),
                ("entry-outside", lambda value: value.__setitem__("entry", base - 1)),
                (
                    "entry-symbol",
                    lambda value: value.__setitem__("entry_symbol", "other_entry"),
                ),
                ("size-overflow", lambda value: value.__setitem__("size", BANK0_LIMIT)),
                ("hash", lambda value: value.__setitem__("sha256", "0" * 64)),
                ("unexpected-field", lambda value: value.__setitem__("extra", True)),
                (
                    "load-base",
                    lambda value: value["load"].__setitem__("base", load_base + 1),
                ),
                (
                    "load-mode",
                    lambda value: value["load"].__setitem__("mode", "other-load-mode"),
                ),
                (
                    "staging-mode",
                    lambda value: value["load"].__setitem__("staging", "other-staging"),
                ),
                (
                    "lifetime",
                    lambda value: value["lifetime"].__setitem__("class", "runtime-hot"),
                ),
                (
                    "reclaim-point",
                    lambda value: value["lifetime"].__setitem__(
                        "reclaim_point", "never"
                    ),
                ),
                (
                    "resident-file-end",
                    lambda value: value["resident"].__setitem__(
                        "file_end", resident_file_end + 1
                    ),
                ),
                (
                    "abi-id",
                    lambda value: value["abi"].__setitem__("contract_id", "other-abi-v1"),
                ),
                (
                    "abi-contract-hash",
                    lambda value: value["abi"].__setitem__("contract_sha256", "0" * 64),
                ),
                (
                    "resident-hash",
                    lambda value: value["abi"].__setitem__("resident_sha256", "0" * 64),
                ),
            ):
                target = _copy_case(package_a, cases, name)
                manifest = _read_manifest(target / MANIFEST_NAME)
                mutate(manifest)
                _write_manifest(target / MANIFEST_NAME, manifest)
                _expect_verify_failure(failures, name, target, strict_verify)

            target = _copy_case(package_a, cases, "duplicate-key")
            manifest_text = (target / MANIFEST_NAME).read_text(encoding="ascii")
            manifest_text = manifest_text.replace(
                '  "schema": "lisp65-profile-overlay-v1",',
                '  "schema": "lisp65-profile-overlay-v1",\n  "schema": "duplicate",',
            )
            (target / MANIFEST_NAME).write_text(manifest_text, encoding="ascii")
            _expect_verify_failure(failures, "duplicate-key", target, strict_verify)

            changed_resident = root / "changed-resident.prg"
            changed_resident.write_bytes(b"different resident\n")
            errors = verify_package(
                package_a,
                profile=profile,
                base=base,
                end=end,
                entry=entry,
                entry_symbol=entry_symbol,
                load_base=load_base,
                load_mode=load_mode,
                staging_mode=staging_mode,
                lifetime=lifetime,
                reclaim_point=reclaim_point,
                abi_id=abi_id,
                resident=changed_resident,
                resident_load_base=resident_load_base,
                resident_file_end=resident_file_end,
                abi_contract=contract,
                strict=True,
            )
            if not errors:
                failures.append("changed-resident-binding: expected verification failure")

            changed_contract = root / "changed-abi.txt"
            changed_contract.write_bytes(b"different contract\n")
            errors = verify_package(
                package_a,
                profile=profile,
                base=base,
                end=end,
                entry=entry,
                entry_symbol=entry_symbol,
                load_base=load_base,
                load_mode=load_mode,
                staging_mode=staging_mode,
                lifetime=lifetime,
                reclaim_point=reclaim_point,
                abi_id=abi_id,
                resident=resident,
                resident_load_base=resident_load_base,
                resident_file_end=resident_file_end,
                abi_contract=changed_contract,
                strict=True,
            )
            if not errors:
                failures.append("changed-contract-binding: expected verification failure")

            errors = verify_package(package_a, strict=True)
            if not errors:
                failures.append("strict-without-bindings: expected verification failure")

    for failure in failures:
        print(f"overlay-package selftest: FAIL {failure}")
    if failures:
        print(f"overlay-package selftest: FAIL failures={len(failures)}", file=sys.stderr)
        return 1
    print("overlay-package selftest: PASS cases=30 failures=0")
    return 0


def _parse_int(value: str) -> int:
    try:
        return int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"not an integer: {value}") from exc


def _binding_arguments(parser: argparse.ArgumentParser, *, expected: bool) -> None:
    prefix = "expect-" if expected else ""
    parser.add_argument(f"--{prefix}profile", required=not expected)
    parser.add_argument(f"--{prefix}base", type=_parse_int, required=not expected)
    parser.add_argument(f"--{prefix}end", type=_parse_int, required=not expected)
    parser.add_argument(f"--{prefix}entry", type=_parse_int, required=not expected)
    parser.add_argument(f"--{prefix}entry-symbol", required=not expected)
    parser.add_argument(f"--{prefix}load-base", type=_parse_int, required=not expected)
    parser.add_argument(f"--{prefix}load-mode", required=not expected)
    parser.add_argument(f"--{prefix}staging-mode", required=not expected)
    parser.add_argument(f"--{prefix}lifetime", required=not expected)
    parser.add_argument(f"--{prefix}reclaim-point", required=not expected)
    parser.add_argument(f"--{prefix}abi-id", required=not expected)
    parser.add_argument("--resident", type=Path, required=not expected)
    parser.add_argument(
        f"--{prefix}resident-load-base", type=_parse_int, required=not expected
    )
    parser.add_argument(
        f"--{prefix}resident-file-end", type=_parse_int, required=not expected
    )
    parser.add_argument("--abi-contract", type=Path, required=not expected)


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    pack = subparsers.add_parser("pack", help="create a deterministic overlay package")
    pack.add_argument("--overlay", type=Path, required=True)
    pack.add_argument("--out-dir", type=Path, required=True)
    _binding_arguments(pack, expected=False)

    verify = subparsers.add_parser("verify", help="verify an overlay package")
    verify.add_argument("--dir", type=Path, required=True)
    verify.add_argument("--strict", action="store_true")
    _binding_arguments(verify, expected=True)

    subparsers.add_parser("selftest", help="run positive and mutation cases")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "selftest":
            return selftest()
        if args.command == "pack":
            pack_package(
                args.overlay,
                args.out_dir,
                profile=args.profile,
                base=args.base,
                end=args.end,
                entry=args.entry,
                entry_symbol=args.entry_symbol,
                load_base=args.load_base,
                load_mode=args.load_mode,
                staging_mode=args.staging_mode,
                lifetime=args.lifetime,
                reclaim_point=args.reclaim_point,
                abi_id=args.abi_id,
                resident=args.resident,
                resident_load_base=args.resident_load_base,
                resident_file_end=args.resident_file_end,
                abi_contract=args.abi_contract,
            )
            print(
                "overlay-package: PACK "
                f"profile={args.profile} base=0x{args.base:04x} end=0x{args.end:04x} "
                f"entry={args.entry_symbol}@0x{args.entry:04x} "
                f"dir={args.out_dir}"
            )
            return 0

        errors = verify_package(
            args.dir,
            profile=args.expect_profile,
            base=args.expect_base,
            end=args.expect_end,
            entry=args.expect_entry,
            entry_symbol=args.expect_entry_symbol,
            load_base=args.expect_load_base,
            load_mode=args.expect_load_mode,
            staging_mode=args.expect_staging_mode,
            lifetime=args.expect_lifetime,
            reclaim_point=args.expect_reclaim_point,
            abi_id=args.expect_abi_id,
            resident=args.resident,
            resident_load_base=args.expect_resident_load_base,
            resident_file_end=args.expect_resident_file_end,
            abi_contract=args.abi_contract,
            strict=args.strict,
        )
        if errors:
            for error in errors:
                print(f"overlay-package: FAIL {error}", file=sys.stderr)
            return 1
        manifest = _read_manifest(args.dir / MANIFEST_NAME)
        print(
            "overlay-package: PASS "
            f"profile={manifest['profile']} base=0x{manifest['base']:04x} "
            f"entry={manifest['entry_symbol']}@0x{manifest['entry']:04x} "
            f"size={manifest['size']}"
        )
        return 0
    except OverlayPackageError as exc:
        print(f"overlay-package: ERROR {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
