#!/usr/bin/env python3
"""Project the 139-name host metadata population onto the v2.0 medium."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-v200-public-surface-medium-projection.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.0.0-public-surface-medium-projection.json")


class ProjectionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProjectionError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def parse_defmacros(path: Path) -> set[str]:
    return set(re.findall(
        r"^\(defmacro\s+([^\s()]+)", path.read_text(encoding="utf-8"), re.M))


def evaluator_macro_names(path: Path) -> set[str]:
    return set(re.findall(
        r'WORKBENCH_BOOTNAME\([^,]+,\s*"([^"]+)"\)',
        path.read_text(encoding="utf-8")))


def runtime_entry(path: Path) -> str:
    match = re.search(r"^RUNTIME_CORE_ENTRY\s*:?=\s*(\S+)",
                      path.read_text(encoding="utf-8"), re.M)
    require(match is not None, "runtime entry is not derivable")
    return match.group(1)


def derive() -> dict[str, Any]:
    spec = load(CONTRACT)
    require(spec.get("format") ==
            "lisp65-c2-v200-public-surface-medium-projection-contract-v1"
            and spec.get("release") == "v2.0.0",
            "medium projection contract drift")
    metadata_path = ROOT / spec["metadata_index"]
    authority_path = ROOT / spec["public_build_authority"]
    resident_path = ROOT / spec["resident_manifest"]
    snapshot_root = ROOT / spec["source_snapshot_root"]
    external_root = ROOT / spec["external_manifest_root"]
    image_root = ROOT / spec["external_image_root"]
    registry_path = ROOT / spec["native_registry"]
    profile_path = ROOT / spec["product_profile"]
    evaluator_path = ROOT / spec["evaluator_source"]
    runtime_path = ROOT / spec["runtime_entry_authority"]

    metadata = load(metadata_path)
    build = load(authority_path)
    resident = load(resident_path)
    registry = load(registry_path)
    profile = load(profile_path)["product_profile"]
    records = metadata.get("records", [])
    names = {row.get("name") for row in records}
    require(metadata.get("delivery") ==
                "host-only; device delivery deferred with ide-help to C2"
            and len(records) == len(names) == 139 and None not in names,
            "metadata host population drift")
    delivered_roles = build.get("delivered_library_roles")
    require(delivered_roles == ["ide", "idex", "m65d"]
            and build.get("loaded_D5_library_roles") == [],
            "v2.0 delivered-library authority drift")

    claims: dict[str, list[dict[str, str]]] = {str(name): [] for name in names}
    authorities: list[dict[str, Any]] = [
        bind(CONTRACT), bind(metadata_path), bind(authority_path),
        bind(resident_path), bind(registry_path), bind(profile_path),
        bind(evaluator_path), bind(runtime_path),
    ]

    def add(name: str, category: str, source: str) -> None:
        if name in claims:
            claims[name].append({"category": category, "source": source})

    resident_rel = resident_path.relative_to(ROOT).as_posix()
    for name in resident.get("functions", []):
        add(name, "resident-bytecode", resident_rel)

    source_basenames = [Path(value).name for value in resident.get("sources", [])]
    snapshot_paths = sorted(snapshot_root.glob("*.lisp"))
    require(len(source_basenames) == len(snapshot_paths)
            and source_basenames == [path.name.split("-", 1)[1]
                                     for path in snapshot_paths],
            "resident source snapshot population drift")
    for path in snapshot_paths:
        authorities.append(bind(path))
        for name in parse_defmacros(path):
            add(name, "resident-compile-form", path.relative_to(ROOT).as_posix())

    for role in delivered_roles:
        manifest_path = external_root / f"libs-{role}.manifest.json"
        image_path = image_root / f"{role}.ext.bin"
        manifest = load(manifest_path)
        sealed = build["sealed_roles"][f"library-{role}"]
        require(image_path.stat().st_size == sealed["bytes"]
                and sha(image_path) == sealed["sha256"],
                f"packed library role differs from seal: {role}")
        authorities.extend((bind(manifest_path), bind(image_path)))
        for name in manifest.get("functions", []):
            add(name, "delivered-library", role)

    delivered_ids = set(profile.get("delivered_ids", []))
    tombstoned_ids = set(profile.get("tombstoned_ids", []))
    require(delivered_ids.isdisjoint(tombstoned_ids)
            and delivered_ids | tombstoned_ids == set(range(84)),
            "product primitive profile is not total")
    for row in registry.get("entries", []):
        name, kind, value = row.get("name"), row.get("kind"), row.get("value")
        if kind == "callprim" and isinstance(value, int) and value in tombstoned_ids:
            add(name, "stable-native-identity-without-wrapper", "native-registry")
        else:
            add(name, "resident-native", "native-registry")

    macro_names = {row["name"] for row in records if row.get("kind") == "macro"}
    for name in evaluator_macro_names(evaluator_path) & macro_names:
        add(name, "resident-evaluator-form", evaluator_path.relative_to(ROOT).as_posix())
    add(runtime_entry(runtime_path), "delivered-runtime-entry",
        runtime_path.relative_to(ROOT).as_posix())

    projected = []
    for row in sorted(records, key=lambda item: item["name"]):
        found = claims[row["name"]]
        projected.append({
            "name": row["name"], "kind": row["kind"],
            "medium_status": "delivered-identity" if found else "outside-medium",
            "authorities": found,
        })
    outside = [row["name"] for row in projected
               if row["medium_status"] == "outside-medium"]
    require(len(projected) == 139 and len(outside) == 12,
            f"medium projection population drift: outside={outside}")
    return {
        "format": "lisp65-c2-v200-public-surface-medium-projection-v1",
        "status": "PASS: HOST POPULATION PROJECTED THROUGH V2.0.0 MEDIUM",
        "release": "v2.0.0",
        "counts": {"metadata_records": 139, "delivered_identities": 127,
                   "outside_medium": 12},
        "outside_medium": outside,
        "records": projected,
        "authorities": authorities,
        "rule": spec["rule"],
    }


def validate(value: dict[str, Any]) -> None:
    require(value == derive(), "v2.0 public-surface medium projection drift")


def selftest() -> list[str]:
    base = derive()
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "host-population-called-delivered": lambda value: value["records"][0].update(
            medium_status="host-population"),
        "outside-name-omitted": lambda value: value["outside_medium"].pop(),
        "delivered-role-dropped": lambda value: value["records"].pop(),
        "unbound-delivery-claim": lambda value: value["records"][0].update(
            authorities=[]),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(base); mutate(trial)
        try:
            validate(trial)
        except ProjectionError:
            rejected.append(name)
    require(rejected == list(cases), "medium projection mutation survived")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "write":
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_bytes(canonical(derive()))
    value = derive() if args.action == "selftest" else load(RECEIPT)
    validate(value)
    mutations = selftest() if args.action == "selftest" else []
    print("v2.0 public-surface medium projection: PASS "
          f"delivered={value['counts']['delivered_identities']} "
          f"outside={value['counts']['outside_medium']} "
          f"mutations={len(mutations)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ProjectionError, OSError, KeyError, ValueError,
            json.JSONDecodeError) as error:
        print(f"v2.0 public-surface medium projection: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
