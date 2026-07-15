#!/usr/bin/env python3
"""Reject internal dialect-v2 staging profiles at normal Ship boundaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SELECTION = ROOT / "config" / "dialect-profile-selection.json"
STAGING_VALUES = {
    ("abi_profile", "dialect-v2"),
    ("profile_id", "v2-capability-candidate"),
    ("profile_id", "dialect-v2-capability-carrier-workbench-staging"),
    # Runtime Export calls its resolved profile key simply "profile".
    ("profile", "v2-capability-candidate"),
    ("profile", "dialect-v2-capability-carrier-workbench-staging"),
}


class DialectShipError(RuntimeError):
    pass


def _json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DialectShipError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise DialectShipError(f"{label} must be a JSON object")
    return value


def _metadata_markers(value: Any) -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, str) and (key, item) in STAGING_VALUES:
                found.add((key, item))
            found.update(_metadata_markers(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_metadata_markers(item))
    return found


def _profile_markers(data: bytes | None) -> set[tuple[str, str]]:
    if data is None:
        return set()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return set()
    found: set[tuple[str, str]] = set()
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if (key, value) in STAGING_VALUES:
            found.add((key, value))
    return found


def _require_g5_authorization(selection_path: Path) -> None:
    selection = _json(selection_path, "dialect profile selection")
    promotion = selection.get("promotion")
    if (
        selection.get("active_profile") != "dialect-v2"
        or not isinstance(promotion, dict)
        or promotion.get("status") != "passed-g5"
        or promotion.get("evidence") is None
    ):
        raise DialectShipError(
            "internal dialect-v2 staging profile is not shippable: "
            "no passed-G5 dialect-v2 switch authorization is bound"
        )

    migration_value = promotion.get("migration_contract")
    if not isinstance(migration_value, str):
        raise DialectShipError(
            "dialect-v2 Ship authorization is invalid: migration contract is not bound"
        )
    migration_path = ROOT / migration_value
    try:
        import dialect_migration_contract as Migration

        Migration.validate(
            _json(migration_path, "dialect migration contract"),
            selection,
            migration_path,
        )
    except Exception as exc:
        if isinstance(exc, DialectShipError):
            raise
        raise DialectShipError(
            f"dialect-v2 Ship authorization failed G5 validation: {exc}"
        ) from exc


def enforce(
    *,
    resolved_profile: bytes | None = None,
    metadata: Any = None,
    selection_path: Path = DEFAULT_SELECTION,
) -> None:
    markers = _profile_markers(resolved_profile) | _metadata_markers(metadata)
    if not markers:
        return
    try:
        _require_g5_authorization(selection_path)
    except DialectShipError as exc:
        rendered = ", ".join(f"{key}={value}" for key, value in sorted(markers))
        raise DialectShipError(f"{exc}; rejected marker(s): {rendered}") from exc


def selftest() -> None:
    enforce(resolved_profile=b"profile=runtime-export-v1-candidate\n")
    enforce(metadata={"profile_id": "v1-candidate"})
    with tempfile.TemporaryDirectory(prefix="dialect-ship-guard-") as raw:
        selection_path = Path(raw) / "selection.json"
        selection_path.write_text(
            json.dumps({
                "active_profile": "dialect-v1",
                "promotion": {"status": "not-requested", "evidence": None},
            }),
            encoding="utf-8",
        )
        mutations = (
            {"resolved_profile": b"abi_profile=dialect-v2\n"},
            {"resolved_profile": b"profile_id=v2-capability-candidate\n"},
            {"resolved_profile": b"profile=v2-capability-candidate\n"},
            {"resolved_profile": b"profile=dialect-v2-capability-carrier-workbench-staging\n"},
            {"metadata": {"nested": {"abi_profile": "dialect-v2"}}},
            {"metadata": {"profile_id": "dialect-v2-capability-carrier-workbench-staging"}},
        )
        for mutation in mutations:
            try:
                enforce(selection_path=selection_path, **mutation)
            except DialectShipError as exc:
                if "no passed-G5" not in str(exc) or "rejected marker" not in str(exc):
                    raise DialectShipError(f"mutation failed unclearly: {exc}") from exc
            else:
                raise DialectShipError("internal dialect-v2 staging mutation was accepted")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if not args.selftest:
        parser.error("--selftest is required")
    try:
        selftest()
    except DialectShipError as exc:
        print(f"dialect-ship-guard: FAIL: {exc}")
        return 1
    print("dialect-ship-guard: SELFTEST PASS mutations=6")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
