#!/usr/bin/env python3
"""Explain the v1.6-loaded versus v1.7-shipped D5 headroom delta."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OLD = ARCH / "c2.3-v1.6-item1-d5-result-receipt.json"
NEW = ARCH / "c2.3-v1.7.0-release-d-session-result-receipt.json"
SESSION = ROOT / "config/c2-v170-release-d-session.json"
MEDIA = ARCH / "c2.3-v1.7.0-release-media-receipt.json"
LIBRARY = ROOT / (
    "build/c2.3/v1.7.0-release-media-r5/library-inputs/v16core.manifest.json")
PRODUCT = ROOT / (
    "build/c2.3/v1.7.0-release-card-r1-preflight/setup-owned/static-plane/"
    "narrow-static/stdlib-p0.manifest.json")
RECEIPT = ARCH / "c2.3-v1.7.0-release-d5-delta-attribution-receipt.json"
STATUS = "PASS: V1.7.0 RELEASE D5 DELTA FULLY ATTRIBUTED"


class DeltaError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise DeltaError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def nul_bytes(names: list[str]) -> int:
    return sum(len(name.encode("ascii")) + 1 for name in names)


def derive() -> dict[str, Any]:
    old = load(OLD)
    new = load(NEW)
    session = load(SESSION)
    media = load(MEDIA)
    library = load(LIBRARY)
    product = load(PRODUCT)

    old_free = old["D5_user_headroom"]["free"]
    new_free = new["D5"]["free"]
    old_observed = old["D5_user_headroom"]["observed"]
    new_observed = new["D5"]["observed"]
    require(old["measurement_configuration"]["loaded_library_roles"] ==
            ["v16core"], "v1.6 comparison world did not load v16core")
    require(session["configuration"]["loaded_library_roles"] == [] and
            session["configuration"]["available_optional_roles"] ==
            ["v16core"],
            "v1.7 shipped configuration must leave optional v16core unloaded")
    require(media["same_world_pair"]["row_names"] == ["v16core"],
            "v1.7 optional-library row drift")

    library_names = library["cost"]["symbol_names"]
    product_names = set(product["cost"]["symbol_names"])
    require(isinstance(library_names, list) and
            all(isinstance(name, str) for name in library_names),
            "v16core manifest symbol inventory malformed")
    new_library_names = sorted(set(library_names) - product_names)
    attributed_names = sorted(media["same_world_pair"]["row_names"] +
                              new_library_names)
    require(attributed_names == [
        "%ide-line-net-depth", "%rl-cut", "%rl-dispatch", "%rl-move",
        "%rl-put", "%rl-render", "%rl-screen-tail", "v16core"],
        "v16core D5 successor name population drift")

    slots = len(attributed_names)
    name_bytes = nul_bytes(attributed_names)
    observed_delta = {
        "nsym": old_observed["nsym"] - new_observed["nsym"],
        "npool": old_observed["npool"] - new_observed["npool"],
    }
    free_delta = {
        "symbol_slots": new_free["symbol_slots"] - old_free["symbol_slots"],
        "namepool_bytes": new_free["namepool_bytes"] -
            old_free["namepool_bytes"],
    }
    require(observed_delta == {"nsym": slots, "npool": name_bytes} and
            free_delta == {"symbol_slots": slots,
                           "namepool_bytes": name_bytes},
            "measured D5 delta is not exactly the unloaded v16core freight")

    return {
        "format": "lisp65-c2-v170-release-d5-delta-attribution-v1",
        "recorded_on": "2026-08-27",
        "status": STATUS,
        "authority": {
            "v1_6_loaded_world": bind(OLD),
            "v1_7_shipped_world": bind(NEW),
            "v1_7_session_configuration": bind(SESSION),
            "v1_7_media": bind(MEDIA),
            "v16core_manifest": bind(LIBRARY),
            "product_symbol_manifest": bind(PRODUCT),
        },
        "worlds": {
            "v1_6_loaded_v16core": {
                "loaded_library_roles": ["v16core"],
                "observed": old_observed,
                "free": old_free,
            },
            "v1_7_shipped_configuration": {
                "loaded_library_roles": [],
                "available_optional_roles": ["v16core"],
                "observed": new_observed,
                "free": new_free,
            },
        },
        "attribution": {
            "cause": "optional v16core is delivered but not loaded in the v1.7 release D5 configuration",
            "names": attributed_names,
            "symbol_slots": slots,
            "NUL_inclusive_name_bytes": name_bytes,
            "observed_counter_delta": observed_delta,
            "observed_free_delta": free_delta,
            "unexplained_symbol_slots": 0,
            "unexplained_name_bytes": 0,
        },
        "claim_limit": (
            "This receipt attributes the favorable D5 difference between two "
            "explicitly different loaded-library configurations. It does not "
            "treat optional v16core as absent from the release media."),
        "next": "owner-Ship candidate seal",
    }


def validate(value: dict[str, Any]) -> None:
    require(value == derive(), "v1.7 release D5 delta receipt stale")


def selftest() -> list[str]:
    base = derive()
    cases = {
        "drop-name": lambda x: x["attribution"]["names"].pop(),
        "hide-slot": lambda x: x["attribution"].update(symbol_slots=7),
        "hide-bytes": lambda x: x["attribution"].update(
            NUL_inclusive_name_bytes=92),
        "claim-same-load": lambda x: x["worlds"][
            "v1_7_shipped_configuration"]["loaded_library_roles"].append(
                "v16core"),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = json.loads(json.dumps(base))
        mutate(trial)
        try:
            validate(trial)
        except DeltaError:
            rejected.append(name)
    require(rejected == list(cases), "D5 delta mutation survived")
    return rejected


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    require(action in ("record", "check", "selftest"),
            "usage: record|check|selftest")
    if action == "record":
        require(not RECEIPT.exists(), "D5 delta receipt already exists")
        RECEIPT.write_bytes(canonical(derive()))
    elif action == "check":
        validate(load(RECEIPT))
    rejected = selftest()
    print(f"v1.7 release D5 delta: PASS slots=8 bytes=93 mutations={len(rejected)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (DeltaError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"v1.7 release D5 delta: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
