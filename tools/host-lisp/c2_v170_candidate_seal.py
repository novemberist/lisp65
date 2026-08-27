#!/usr/bin/env python3
"""Seal the hardware-green v1.7.0 product as the public build target."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
MEDIA_RECEIPT = ARCH / "c2.3-v1.7.0-release-media-receipt.json"
DEVICE_RECEIPT = ARCH / "c2.3-v1.7.0-release-d-session-result-receipt.json"
D5_DELTA = ARCH / "c2.3-v1.7.0-release-d5-delta-attribution-receipt.json"
SOURCE_MANIFEST = ROOT / (
    "build/c2.3/v1.7.0-release-media-r5/shared-system/candidate-manifest.json")
AUTHORITY = ROOT / "config/c2-v170-public-build-authority.json"
RECEIPT = ARCH / "c2.3-v1.7.0-candidate-seal-receipt.json"
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
SHIP_COMMIT = "0fff2765"
STATUS = "PASS: V1.7.0 CANDIDATE SEALED FOR PUBLIC CLEAN BUILD"


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


def ship_authority() -> dict[str, Any]:
    relative = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{SHIP_COMMIT}:{relative}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace(
        "*", "").split())
    require("the owner said ship" in text and
            "publish remains a separate, closed owner halt" in text,
            "owner Ship authority absent")
    return {"authority": "git-blob", "commit": SHIP_COMMIT,
            "path": relative, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def selected_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    media = load(MEDIA_RECEIPT)
    source = load(SOURCE_MANIFEST)
    require(media["status"] == "PASS: V1.7.0 RELEASE MEDIA AND D-SESSION READY"
            and media["library_closure"]["row_names"] == ["v16core"]
            and media["library_closure"]["Comfort_absent"] is True
            and source["format"] == "lisp65-c2-lite-canonical-media-product-v1"
            and source["status"] == "passed-complete-C2-lite-two-media-product"
            and source["artifact_count"] == len(source["artifacts"]) == 19,
            "v1.7 selected product/media closure drift")
    rows: list[dict[str, Any]] = []
    for item in source["artifacts"]:
        path = ROOT / item["path"]
        require(bind(path) == {key: item[key]
                              for key in ("path", "bytes", "sha256")},
                f"selected shared artifact drift: {item['role']}")
        rows.append(dict(item))
    library = media["library_closure"]
    for role, name, identity in (
            ("optional-library-d81", "lisp65-library.d81", library["D81"]),
            ("optional-library-index", "l65index", library["index"]),
            ("library-v16core", "v16core.l65s",
             library["artifacts"]["v16core"])):
        require(bind(ROOT / identity["path"]) == identity,
                f"selected library artifact drift: {role}")
        rows.append({"role": role, "name": name, **identity})
    require(len(rows) == len({row["role"] for row in rows}) ==
            len({row["path"] for row in rows}) == 22,
            "v1.7 sealed role/path inventory is not unique")
    return rows, {"media": media, "source": source}


def acceptance_gate() -> dict[str, Any]:
    device = load(DEVICE_RECEIPT)
    delta = load(D5_DELTA)
    free = device["D5"]["free"]
    require(device["status"] ==
                "PASS: V1.7.0 RELEASE D-SESSION HARDWARE GREEN; OWNER-SHIP-PENDING"
            and all(row["result"] == "PASS" for row in device["rows"])
            and free["symbol_slots"] >= 32
            and free["namepool_bytes"] >= 384
            and delta["status"] ==
                "PASS: V1.7.0 RELEASE D5 DELTA FULLY ATTRIBUTED"
            and delta["attribution"]["unexplained_symbol_slots"] == 0
            and delta["attribution"]["unexplained_name_bytes"] == 0,
            "v1.7 hardware/D5 Ship authority is not green")
    return {"D_session": bind(DEVICE_RECEIPT),
            "D5_delta": bind(D5_DELTA), "D5_free": free,
            "loaded_library_roles": [],
            "delivered_optional_library_roles": ["v16core"]}


def derive_authority() -> dict[str, Any]:
    rows, facts = selected_rows()
    role_map = {row["role"]: {"bytes": row["bytes"],
                              "sha256": row["sha256"]} for row in rows}
    return {
        "format": "lisp65-c2-public-build-authority-v5",
        "release": "v1.7.0",
        "selected_variant": "v1.7-native-init-a0",
        "build_model": "fresh-source-single-emitter-plus-one-WPLTO",
        "entry_point": "make workbench-product-v170",
        "candidate_manifest_path":
            "build/c2.3/v1.7.0-public-selected/candidate-manifest.json",
        "product_manifest_path":
            "build/c2.3/v1.7.0-public-selected/product-link/static-plane/"
            "narrow-static/product/substitution-artifacts.json",
        "artifact_count": 22,
        "sealed_product_artifact_set_sha256": artifact_set(rows),
        "selected_media_sha256": facts["media"]["media"]["product"]["sha256"],
        "sealed_roles": role_map,
        "delivered_library_roles": ["v16core"],
        "loaded_D5_library_roles": [],
        "excluded_library_roles": ["repl-comfort", "Block-3"],
        "private_evidence_is_build_input": False,
        "acceptance_evidence_rule": (
            "The D-session, D5 attribution and owner Ship select the byte "
            "target but are not compilation, link, media or clean-build inputs."),
        "nondeterminism_policy": (
            "Any role mismatch is a clean-build First Red; no selected product, "
            "library or media role is exempt."),
    }


def validate_authority(value: dict[str, Any]) -> None:
    roles = value.get("sealed_roles", {})
    require(value.get("format") == "lisp65-c2-public-build-authority-v5"
            and value.get("release") == "v1.7.0"
            and value.get("selected_variant") == "v1.7-native-init-a0"
            and value.get("entry_point") == "make workbench-product-v170"
            and value.get("artifact_count") == 22
            and isinstance(roles, dict) and len(roles) == 22
            and value.get("delivered_library_roles") == ["v16core"]
            and value.get("loaded_D5_library_roles") == []
            and value.get("excluded_library_roles") ==
                ["repl-comfort", "Block-3"]
            and value.get("private_evidence_is_build_input") is False,
            "v1.7 public build authority envelope drift")
    require(value == derive_authority(),
            "v1.7 public build authority differs from seal")


def derive_receipt() -> dict[str, Any]:
    authority = load(AUTHORITY)
    validate_authority(authority)
    rows, facts = selected_rows()
    return {
        "format": "lisp65-c2-v170-candidate-seal-v1",
        "recorded_on": "2026-08-27",
        "status": STATUS,
        "authority": {"owner_Ship": ship_authority(),
                      "public_build": bind(AUTHORITY),
                      "source_manifest": bind(SOURCE_MANIFEST),
                      "media_receipt": bind(MEDIA_RECEIPT),
                      **acceptance_gate()},
        "selection": {
            "release": "v1.7.0", "variant": "v1.7-native-init-a0",
            "artifact_count": len(rows),
            "artifact_set_sha256": artifact_set(rows),
            "product_build_id": facts["source"]["product_build_id"],
            "profile_build_id": facts["source"]["profile_build_id"],
            "roles": [{key: row[key] for key in
                       ("role", "name", "path", "bytes", "sha256")}
                      for row in sorted(rows, key=lambda item: item["role"])],
        },
        "build_boundary": {"private_evidence_inputs": 0,
            "candidate_bytes_reused_by_clean_build": 0,
            "required_fresh_builds": 2,
            "entry_point": "make workbench-product-v170"},
        "execution_accounting": {"WPLTO_runs": 0, "product_links": 0,
                                 "media_builds": 0, "device_contacts": 0},
        "next": "two-varied-fresh-public-clean-build-qualification",
        "claim_limit": (
            "This seal selects the 22-role byte target. It does not claim a "
            "fresh public rebuild, release package, publication or tag."),
    }


def mutations() -> list[str]:
    base = derive_authority()
    cases = {
        "admit-Comfort": lambda x: x["excluded_library_roles"].remove(
            "repl-comfort"),
        "load-v16core-in-D5": lambda x: x[
            "loaded_D5_library_roles"].append("v16core"),
        "admit-evidence": lambda x: x.update(
            private_evidence_is_build_input=True),
        "drop-role": lambda x: x["sealed_roles"].pop("library-v16core"),
        "change-media": lambda x: x.update(selected_media_sha256="0" * 64),
        "change-release": lambda x: x.update(release="v1.6.0"),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = json.loads(json.dumps(base))
        mutate(trial)
        try:
            validate_authority(trial)
        except SealError:
            rejected.append(name)
    require(rejected == list(cases), "v1.7 candidate-seal mutation survived")
    return rejected


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    require(action in ("seal", "check"), "usage: seal|check")
    if action == "seal":
        require(not AUTHORITY.exists() and not RECEIPT.exists(),
                "v1.7 candidate-seal outputs already exist")
        AUTHORITY.write_bytes(canonical(derive_authority()))
        value = derive_receipt()
        value["mutations_rejected"] = mutations()
        RECEIPT.write_bytes(canonical(value))
    else:
        validate_authority(load(AUTHORITY))
        value = load(RECEIPT)
        rejected = value.pop("mutations_rejected", None)
        require(value == derive_receipt(), "v1.7 candidate-seal receipt stale")
        require(rejected == mutations(), "v1.7 candidate-seal mutation drift")
    print("v1.7 candidate seal: PASS roles=22 clean-build=open")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SealError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"v1.7 candidate seal: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
