#!/usr/bin/env python3
"""Seal the D5-green v1.6 Item-1 product as the public clean-build target."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
MEDIA_RECEIPT = ARCH / "c2.3-v1.6-item1-only-media-r1-public2-receipt.json"
DEVICE_RECEIPT = ARCH / "c2.3-v1.6-item1-only-r1-public2-device-result-receipt.json"
D5_RECEIPT = ARCH / "c2.3-v1.6-item1-d5-result-receipt.json"
SOURCE_MANIFEST = ROOT / (
    "build/c2.3/v1.6-item1-only-media-r1-public2/shared-system/"
    "candidate-manifest.json")
AUTHORITY = ROOT / "config/c2-v160-public-build-authority.json"
RECEIPT = ARCH / "c2.3-v1.6-candidate-seal-receipt.json"
STATUS = "PASS: V1.6 ITEM-1 CANDIDATE SEALED FOR PUBLIC CLEAN BUILD"


class SealError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SealError(message)


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
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def artifact_set(rows: list[dict[str, Any]]) -> str:
    projection = [
        {key: row[key] for key in ("role", "name", "bytes", "sha256")}
        for row in sorted(rows, key=lambda row: (row["role"], row["name"]))]
    return hashlib.sha256(json.dumps(
        projection, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def selected_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    media = load(MEDIA_RECEIPT)
    source = load(SOURCE_MANIFEST)
    require(
        media.get("status") ==
            "PASS: V1.6 ITEM 1 ONLY R1 PUBLIC2 ACCEPTANCE MEDIA READY"
        and media.get("library_closure", {}).get("row_names") == ["v16core"]
        and media.get("library_closure", {}).get("Comfort_absent") is True
        and source.get("format") == "lisp65-c2-lite-canonical-media-product-v1"
        and source.get("status") == "passed-complete-C2-lite-two-media-product"
        and source.get("artifact_count") == 19
        and len(source.get("artifacts", [])) == 19,
        "v1.6 selected product/media closure drift")
    rows: list[dict[str, Any]] = []
    for item in source["artifacts"]:
        path = ROOT / item["path"]
        require(bind(path) == {key: item[key]
                              for key in ("path", "bytes", "sha256")},
                f"selected shared artifact drift: {item['role']}")
        rows.append(dict(item))
    library = media["library_closure"]
    additions = (
        ("optional-library-d81", "lisp65-library.d81", library["D81"]),
        ("optional-library-index", "l65index", library["index"]),
        ("library-v16core", "v16core.l65s", library["artifacts"]["v16core"]),
    )
    for role, name, identity in additions:
        require(bind(ROOT / identity["path"]) == identity,
                f"selected library artifact drift: {role}")
        rows.append({"role": role, "name": name, **identity})
    roles = [row["role"] for row in rows]
    paths = [row["path"] for row in rows]
    require(len(rows) == len(set(roles)) == len(set(paths)) == 22,
            "v1.6 sealed role/path inventory is not unique")
    return rows, {"media": media, "source": source}


def acceptance_gate() -> dict[str, Any]:
    device = load(DEVICE_RECEIPT)
    d5 = load(D5_RECEIPT)
    free = d5.get("D5_user_headroom", {}).get("free", {})
    require(
        device.get("status") ==
            "PASS: V1.6 ITEM 1 HARDWARE ACCEPTED; HALT A REACHED"
        and device.get("acceptance", {}).get("item_1") == "ACCEPTED"
        and d5.get("status") ==
            "PASS: V1.6 ITEM-1 D5 GREEN; CANDIDATE SEAL OPEN"
        and d5.get("measurement_configuration", {}).get(
            "loaded_library_roles") == ["v16core"]
        and d5.get("measurement_configuration", {}).get(
            "absent_library_roles") == ["repl-comfort"]
        and free.get("symbol_slots", -1) >= 32
        and free.get("namepool_bytes", -1) >= 384,
        "v1.6 Halt-A/D5 authority is not green")
    return {"Halt_A": bind(DEVICE_RECEIPT), "D5": bind(D5_RECEIPT),
            "D5_free": free, "measured_roles": ["v16core"],
            "excluded_roles": ["repl-comfort"]}


def derive_authority() -> dict[str, Any]:
    rows, facts = selected_rows()
    role_map = {row["role"]: {"bytes": row["bytes"],
                              "sha256": row["sha256"]} for row in rows}
    return {
        "format": "lisp65-c2-public-build-authority-v4",
        "release": "v1.6.0",
        "selected_variant": "v1.6-item-1-only",
        "build_model": "fresh-source-single-emitter-plus-one-WPLTO",
        "entry_point": "make workbench-product-v160",
        "candidate_manifest_path":
            "build/c2.3/v1.6.0-public-selected/candidate-manifest.json",
        "product_manifest_path":
            "build/c2.3/v1.6.0-public-selected/product-link/static-plane/"
            "narrow-static/product/substitution-artifacts.json",
        "artifact_count": 22,
        "sealed_product_artifact_set_sha256": artifact_set(rows),
        "selected_media_sha256": facts["media"]["media"]["product"]["sha256"],
        "sealed_roles": role_map,
        "delivered_library_roles": ["v16core"],
        "excluded_library_roles": ["repl-comfort"],
        "private_evidence_is_build_input": False,
        "acceptance_evidence_rule": (
            "Halt-A and D5 receipts select the byte target but are not inputs "
            "to compilation, linking, media construction or clean-build "
            "qualification."),
        "nondeterminism_policy": (
            "Any role mismatch is a clean-build First Red; no selected product, "
            "library or media role is exempt."),
    }


def validate_authority(value: dict[str, Any]) -> None:
    roles = value.get("sealed_roles", {})
    require(
        value.get("format") == "lisp65-c2-public-build-authority-v4"
        and value.get("release") == "v1.6.0"
        and value.get("selected_variant") == "v1.6-item-1-only"
        and value.get("entry_point") == "make workbench-product-v160"
        and value.get("artifact_count") == 22
        and isinstance(roles, dict) and len(roles) == 22
        and value.get("delivered_library_roles") == ["v16core"]
        and value.get("excluded_library_roles") == ["repl-comfort"]
        and value.get("private_evidence_is_build_input") is False,
        "v1.6 public build authority envelope drift")
    expected = derive_authority()
    require(value == expected, "v1.6 public build authority differs from seal")


def derive_receipt() -> dict[str, Any]:
    authority = load(AUTHORITY)
    validate_authority(authority)
    rows, facts = selected_rows()
    acceptance = acceptance_gate()
    return {
        "format": "lisp65-c2-v160-candidate-seal-v1",
        "recorded_on": "2026-08-25",
        "status": STATUS,
        "authority": {"public_build": bind(AUTHORITY),
                      "source_manifest": bind(SOURCE_MANIFEST),
                      "media_receipt": bind(MEDIA_RECEIPT), **acceptance},
        "selection": {
            "release": "v1.6.0", "variant": "v1.6-item-1-only",
            "artifact_count": len(rows),
            "artifact_set_sha256": artifact_set(rows),
            "product_build_id": facts["source"]["product_build_id"],
            "profile_build_id": facts["source"]["profile_build_id"],
            "roles": [{key: row[key] for key in
                       ("role", "name", "path", "bytes", "sha256")}
                      for row in sorted(rows, key=lambda item: item["role"])],
        },
        "build_boundary": {
            "private_evidence_inputs": 0,
            "candidate_bytes_reused_by_clean_build": 0,
            "required_fresh_builds": 2,
            "entry_point": "make workbench-product-v160",
        },
        "execution_accounting": {"WPLTO_runs": 0, "product_links": 0,
                                 "media_builds": 0, "device_contacts": 0},
        "next": "two-varied-fresh-public-clean-build-qualification",
        "claim_limit": (
            "This seal selects the 22-role byte target. It does not claim a "
            "fresh public rebuild, release package, publication or tag."),
    }


def validate_receipt(value: dict[str, Any], *, verify: bool) -> None:
    selection = value.get("selection", {})
    require(
        value.get("status") == STATUS
        and selection.get("release") == "v1.6.0"
        and selection.get("variant") == "v1.6-item-1-only"
        and selection.get("artifact_count") == 22
        and len(selection.get("roles", [])) == 22
        and value.get("build_boundary", {}).get("private_evidence_inputs") == 0
        and value.get("build_boundary", {}).get("required_fresh_builds") == 2
        and value.get("next") ==
            "two-varied-fresh-public-clean-build-qualification",
        "v1.6 candidate seal claim drift")
    if verify:
        require(value == derive_receipt(), "v1.6 candidate seal stale")


def mutations() -> list[str]:
    base = derive_authority()
    cases = {
        "admit-Comfort": lambda x: x["excluded_library_roles"].clear(),
        "drop-v16core": lambda x: x["delivered_library_roles"].clear(),
        "admit-evidence": lambda x: x.update(private_evidence_is_build_input=True),
        "drop-role": lambda x: x["sealed_roles"].pop("library-v16core"),
        "change-media": lambda x: x.update(selected_media_sha256="0" * 64),
        "change-release": lambda x: x.update(release="v1.5.0"),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = json.loads(json.dumps(base))
        mutate(trial)
        try:
            validate_authority(trial)
        except SealError:
            rejected.append(name)
    require(rejected == list(cases), "v1.6 candidate seal mutation survived")
    return rejected


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    require(action in ("seal", "check"), "usage: seal|check")
    if action == "seal":
        require(not AUTHORITY.exists() and not RECEIPT.exists(),
                "v1.6 candidate seal outputs already exist")
        AUTHORITY.write_bytes(canonical(derive_authority()))
        value = derive_receipt()
        value["mutations_rejected"] = mutations()
        RECEIPT.write_bytes(canonical(value))
        print("v1.6 candidate seal: PASS roles=22 clean-build=open")
    else:
        validate_authority(load(AUTHORITY))
        value = load(RECEIPT)
        rejected = value.pop("mutations_rejected", None)
        validate_receipt(value, verify=True)
        require(rejected == mutations(), "v1.6 candidate seal mutation drift")
        print("v1.6 candidate seal: CHECK PASS roles=22 clean-build=open")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SealError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"v1.6 candidate seal: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
