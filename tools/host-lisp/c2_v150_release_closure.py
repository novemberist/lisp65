#!/usr/bin/env python3
"""Close v1.5 freight, surface, performance and card prerequisites."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v150_release_preflight as PRE  # noqa: E402


CONTRACT = PRE.CONTRACT
INSPECT = ROOT / "build/c2.3/trace-core-abi/inspect.manifest.json"
STRING_EXTRA = ROOT / "build/post-promotion/v112/string-extra/string-extra.manifest.json"
PLACE = ROOT / "build/post-promotion/defstruct-v1/foundations/place.manifest.json"
DEFSTRUCT = ROOT / "build/post-promotion/v110-performance/defstruct-candidate.manifest.json"
TRACE_DEVICE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link95-trace-hardware-result-receipt.json"
)
POINT_DEVICE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link96-terminal-return-guard-device-receipt.json"
)
PIPELINE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link96-repl-pipeline-cost-attribution-receipt.json"
)
DIRECT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-repl-direct-expression-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-release-freight-closure-receipt.json"
)
DRIVER = Path(__file__).resolve()
FORMAT = "lisp65-c2.3-v150-release-freight-closure-v1"
STATUS = "V150-FREIGHT-CLOSURE-GREEN; ONE-PRODUCT-CARD-AUTHORIZED"


class ClosureError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ClosureError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def public_entries(manifest: dict[str, Any]) -> list[str]:
    return sorted(str(row["name"]) for row in manifest["entries"]
                  if not str(row["name"]).startswith("%"))


def package_gate() -> dict[str, Any]:
    contract = load(CONTRACT)
    packages = {
        "inspect": load(INSPECT), "string-extra": load(STRING_EXTRA),
        "place": load(PLACE), "defstruct": load(DEFSTRUCT),
    }
    actual = {name: public_entries(value) for name, value in packages.items()}
    require(
        actual["inspect"] == sorted(contract["freight"]["inspect"])
        and actual["string-extra"] == sorted(
            contract["freight"]["string-extra"])
        and "defstruct" in actual["defstruct"]
        and packages["defstruct"].get("requires") == ["place"]
        and packages["inspect"].get("provides") == ["inspect"]
        and packages["string-extra"].get("provides") == ["string-extra"]
        and all(value.get("artifact_role") == "disk-lib"
                for value in packages.values()),
        f"v1.5 package surface/dependency drift: {actual}",
    )
    return {
        "public_entries": actual,
        "dependencies": {name: value.get("requires", [])
                         for name, value in packages.items()},
        "manifests": {name: bind(path) for name, path in {
            "inspect": INSPECT, "string-extra": STRING_EXTRA,
            "place": PLACE, "defstruct": DEFSTRUCT}.items()},
    }


def performance_gate() -> dict[str, Any]:
    contract = load(CONTRACT)
    pipeline = load(PIPELINE)
    direct = load(DIRECT)
    prices = pipeline["stage_prices"]["transient_install_execute_rollback"]
    cold_warm = prices["derived_whole_envelope_frames_cold_warm"]
    device = contract["device"]
    require(
        cold_warm == [60, 62]
        and device["ceremony_frames"] == {
            "documented_cold": 60, "documented_warm": 62,
            "release_max": 72}
        and direct["effect"]["common_nested_calls"]
            == "60/62-frame ceremony removed"
        and direct["effect"]["bound_accessor_calls"]
            == "60/62-frame ceremony removed"
        and len(device["performance_smokes"]) == 4
        and [row["id"] for row in device["performance_smokes"]] == [
            "list-read", "list-write", "string-op", "published-call"]
        and all(0 <= int(row["max_frames"]) <= 2
                for row in device["performance_smokes"]),
        "v1.5 performance authority or release bounds drift",
    )
    return {
        "direct_path_removed_frames": [60, 62],
        "ceremony_release_max_frames": 72,
        "operation_smoke_max_frames": 2,
        "release_terminal_on_violation": True,
        "smokes": device["performance_smokes"],
    }


def predecessor_hardware() -> dict[str, Any]:
    trace = load(TRACE_DEVICE)
    point = load(POINT_DEVICE)
    require(
        trace.get("status") == "LINK95-TRACE-HARDWARE-GREEN; DEFSTRUCT-SISTER-PENDING"
        and point.get("status") == "LINK96-POINT-HARDWARE-GREEN; GUARD-CLEAN",
        "accepted trace/point hardware predecessor drift",
    )
    return {"trace": bind(TRACE_DEVICE), "defstruct_guard": bind(POINT_DEVICE)}


def derive() -> dict[str, Any]:
    preflight = load(PRE.RECEIPT)
    rejected = preflight.pop("mutations_rejected", None)
    PRE.validate(preflight, verify=False)
    require(rejected == PRE.mutations(preflight), "preflight mutation set drift")
    PRE.validate_public_projection(preflight, rejected)
    return {
        "format": FORMAT, "recorded_on": "2026-08-11", "status": STATUS,
        "attempt_accounting": {
            "product_cards_authorized": 1, "product_cards_consumed": 0,
            "product_links": 0, "device_contacts": 0,
        },
        "scope": {"frozen": True, "resident_delta_bytes": 0,
                  "release": "v1.5.0"},
        "packages": package_gate(),
        "performance": performance_gate(),
        "predecessor_hardware": predecessor_hardware(),
        "authorities": {"contract": bind(CONTRACT),
                        "preflight": bind(PRE.RECEIPT), "driver": bind(DRIVER)},
        "claim_limit": (
            "Complete linker-free v1.5 freight closure. The authorized product "
            "card is still unused; media, hardware and release are unclaimed."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and value.get("attempt_accounting") == {
            "product_cards_authorized": 1, "product_cards_consumed": 0,
            "product_links": 0, "device_contacts": 0}
        and value.get("scope") == {
            "frozen": True, "resident_delta_bytes": 0, "release": "v1.5.0"}
        and value.get("performance", {}).get(
            "release_terminal_on_violation") is True,
        "v1.5 freight closure claim drift",
    )
    if verify:
        require(value == derive(), "v1.5 freight closure receipt is stale")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "consume-card": lambda x: x["attempt_accounting"].update(
            product_cards_consumed=1),
        "claim-link": lambda x: x["attempt_accounting"].update(product_links=1),
        "claim-device": lambda x: x["attempt_accounting"].update(
            device_contacts=1),
        "unfreeze-scope": lambda x: x["scope"].update(frozen=False),
        "grow-resident": lambda x: x["scope"].update(resident_delta_bytes=1),
        "soften-performance": lambda x: x["performance"].update(
            release_terminal_on_violation=False),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate, verify=False)
        except ClosureError:
            rejected.append(name)
    require(len(rejected) == len(cases), "v1.5 freight mutation survived")
    return rejected


def write() -> int:
    require(not RECEIPT.exists(), "v1.5 freight closure already exists")
    value = derive(); value["mutations_rejected"] = mutations(value)
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_bytes(canonical(value))
    print("v1.5 freight closure: PASS packages=4 performance-smokes=4 card=0/1")
    return 0


def check() -> int:
    value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
    # This receipt closes the commissioned pre-link freight world.  Its
    # current successor is checked independently through the public product
    # projection; mutable historical package paths are not living predicates.
    validate(value, verify=False)
    require(rejected == mutations(value), "v1.5 freight mutations drift")
    preflight = load(PRE.RECEIPT)
    preflight_rejected = preflight.pop("mutations_rejected", None)
    PRE.validate(preflight, verify=False)
    require(preflight_rejected == PRE.mutations(preflight),
            "preflight mutation set drift")
    PRE.validate_public_projection(preflight, preflight_rejected)
    print("v1.5 freight closure check: PASS")
    return 0


def rebind() -> int:
    value = derive(); value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("v1.5 freight closure authority rebind: PASS card=0/1")
    return 0


def selftest() -> int:
    package_gate(); performance_gate(); predecessor_hardware()
    print("v1.5 freight closure selftest: PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "rebind", "check", "selftest"))
    return {"write": write, "rebind": rebind, "check": check,
            "selftest": selftest}[parser.parse_args().action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ClosureError, PRE.PreflightError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"v1.5 freight closure: FAIL: {error}", file=sys.stderr)
        raise SystemExit(2)
