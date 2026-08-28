#!/usr/bin/env python3
"""Seal the hardware-green v1.8.0 substrate as the public build target."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
MEDIA = ARCH / "c2.3-v1.8.0-release-media-receipt.json"
DEVICE = ARCH / "c2.3-v1.8.0-substrate-d-session-result-receipt.json"
SOURCE = ROOT / "build/c2.3/v1.8.0-release-media/shared-system/candidate-manifest.json"
AUTHORITY = ROOT / "config/c2-v180-public-build-authority.json"
RECEIPT = ARCH / "c2.3-v1.8.0-candidate-seal-receipt.json"
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
SHIP = "caf640c5"
STATUS = "PASS: V1.8.0 CANDIDATE SEALED FOR PUBLIC CLEAN BUILD"


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


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def artifact_set(rows: list[dict[str, Any]]) -> str:
    projection = [{key: row[key] for key in ("role", "name", "bytes", "sha256")}
                  for row in sorted(rows, key=lambda row: (row["role"], row["name"]))]
    return hashlib.sha256(json.dumps(
        projection, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def ship_authority() -> dict[str, Any]:
    relative = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{SHIP}:{relative}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    require("the owner said ship" in text and "publish remains closed" in text,
            "owner Ship authority absent")
    return {"authority": "git-blob", "commit": SHIP, "path": relative,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def selected_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    media, source = load(MEDIA), load(SOURCE)
    require(media["status"] == "PASS: V1.8.0 RELEASE MEDIA READY"
            and media["banner"] == "WORKBENCH 1.8.0"
            and media["release_lifecycle"]["initial_tail"] == 255
            and media["release_lifecycle"]["losslessness_claim"] is False
            and media["library_closure"]["row_names"] == ["v16core"]
            and media["library_closure"]["Comfort_absent"] is True
            and source["format"] == "lisp65-c2-lite-canonical-media-product-v1"
            and source["status"] == "passed-complete-C2-lite-two-media-product"
            and source["artifact_count"] == len(source["artifacts"]) == 19,
            "v1.8 selected product/media closure drift")
    rows = []
    for item in source["artifacts"]:
        identity = bind(ROOT / item["path"])
        require(identity == {key: item[key] for key in ("path", "bytes", "sha256")},
                f"selected shared artifact drift: {item['role']}")
        rows.append(dict(item))
    library = media["library_closure"]
    for role, name, identity in (
            ("optional-library-d81", "lisp65-library.d81", library["D81"]),
            ("optional-library-index", "l65index", library["index"]),
            ("library-v16core", "v16core.l65s", library["artifacts"]["v16core"])):
        require(bind(ROOT / identity["path"]) == identity,
                f"selected library artifact drift: {role}")
        rows.append({"role": role, "name": name, **identity})
    require(len(rows) == len({row["role"] for row in rows}) ==
            len({row["path"] for row in rows}) == 22,
            "v1.8 sealed role/path inventory is not unique")
    return rows, {"media": media, "source": source}


def acceptance() -> dict[str, Any]:
    value = load(DEVICE)
    rows = {row["id"]: row for row in value["rows"]}
    free = value["D5"]["free"]
    require(value["status"] ==
                "PASS: V1.8.0 SUBSTRATE D-SESSION HARDWARE GREEN; OWNER-SHIP-PENDING"
            and all(row["result"] == "PASS" for key, row in rows.items()
                    if key != "S-withdrawn-native-cursor-row")
            and rows["S-withdrawn-native-cursor-row"]["result"] ==
                "PROTOCOL-FALSE-RED"
            and rows["S-withdrawn-native-cursor-row"]["product_defect"] is False
            and free["symbol_slots"] >= 32 and free["namepool_bytes"] >= 384,
            "v1.8 hardware/D5 Ship authority is not green")
    return {"D_session": bind(DEVICE), "D5_free": free,
            "native_cursor_boundary": "attributed-preexisting-nonclaim",
            "loaded_library_roles": [], "delivered_optional_library_roles": ["v16core"]}


def derive_authority() -> dict[str, Any]:
    rows, facts = selected_rows()
    return {
        "format": "lisp65-c2-public-build-authority-v6",
        "release": "v1.8.0", "selected_variant": "v1.8-closed-capture-substrate",
        "build_model": "fresh-source-single-emitter-plus-one-WPLTO",
        "entry_point": "make workbench-product-v180",
        "candidate_manifest_path":
            "build/c2.3/v1.8.0-public-selected/candidate-manifest.json",
        "product_manifest_path":
            "build/c2.3/v1.8.0-public-selected/product-link/static-plane/"
            "narrow-static/product/substitution-artifacts.json",
        "artifact_count": 22,
        "sealed_product_artifact_set_sha256": artifact_set(rows),
        "selected_media_sha256": facts["media"]["media"]["product"]["sha256"],
        "sealed_roles": {row["role"]: {"bytes": row["bytes"],
                                        "sha256": row["sha256"]} for row in rows},
        "delivered_library_roles": ["v16core"], "loaded_D5_library_roles": [],
        "excluded_library_roles": ["repl-comfort", "Matcher/Blink", "Block-3"],
        "capture_lifecycle": "present-closed-tail-ff-no-lossless-claim",
        "private_evidence_is_build_input": False,
        "acceptance_evidence_rule": (
            "Hardware and Ship select the 22-role byte target but are not public "
            "compilation, link, media or clean-build inputs."),
        "nondeterminism_policy": "Every role mismatch is a clean-build First Red.",
    }


def validate_authority(value: dict[str, Any]) -> None:
    roles = value.get("sealed_roles", {})
    require(value.get("format") == "lisp65-c2-public-build-authority-v6"
            and value.get("release") == "v1.8.0"
            and value.get("selected_variant") == "v1.8-closed-capture-substrate"
            and value.get("entry_point") == "make workbench-product-v180"
            and value.get("artifact_count") == len(roles) == 22
            and value.get("private_evidence_is_build_input") is False,
            "v1.8 public build authority envelope drift")
    require(value == derive_authority(), "v1.8 public build authority differs from seal")


def derive_receipt() -> dict[str, Any]:
    authority = load(AUTHORITY)
    validate_authority(authority)
    rows, facts = selected_rows()
    return {
        "format": "lisp65-c2-v180-candidate-seal-v1", "recorded_on": "2026-08-28",
        "status": STATUS,
        "authority": {"owner_Ship": ship_authority(), "public_build": bind(AUTHORITY),
                      "source_manifest": bind(SOURCE), "media_receipt": bind(MEDIA),
                      **acceptance()},
        "selection": {"release": "v1.8.0",
            "variant": "v1.8-closed-capture-substrate", "artifact_count": len(rows),
            "artifact_set_sha256": artifact_set(rows),
            "product_build_id": facts["source"]["product_build_id"],
            "profile_build_id": facts["source"]["profile_build_id"],
            "roles": [{key: row[key] for key in
                       ("role", "name", "path", "bytes", "sha256")}
                      for row in sorted(rows, key=lambda row: row["role"])]},
        "build_boundary": {"private_evidence_inputs": 0,
            "candidate_bytes_reused_by_clean_build": 0, "required_fresh_builds": 2,
            "entry_point": "make workbench-product-v180"},
        "execution_accounting": {"WPLTO_runs": 0, "product_links": 0,
                                 "media_builds": 0, "device_contacts": 0},
        "next": "two-varied-fresh-public-clean-build-qualification",
        "claim_limit": "Selects bytes; does not publish, tag or extend hardware claims.",
    }


def mutation_proof() -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "activate-capture": lambda x: x.update(capture_lifecycle="active"),
        "claim-lossless": lambda x: x.update(capture_lifecycle="lossless"),
        "drop-role": lambda x: x["sealed_roles"].pop("library-v16core"),
        "admit-comfort": lambda x: x["excluded_library_roles"].remove("repl-comfort"),
        "admit-evidence": lambda x: x.update(private_evidence_is_build_input=True),
        "change-release": lambda x: x.update(release="v1.7.0"),
    }
    base = derive_authority()
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(base); mutate(trial)
        try:
            validate_authority(trial)
        except SealError:
            rejected.append(name)
    require(rejected == list(cases), "v1.8 candidate-seal mutation survived")
    return rejected


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    require(action in ("seal", "check"), "usage: seal|check")
    if action == "seal":
        require(not AUTHORITY.exists() and not RECEIPT.exists(),
                "v1.8 candidate-seal outputs already exist")
        AUTHORITY.write_bytes(canonical(derive_authority()))
        value = derive_receipt(); value["mutations_rejected"] = mutation_proof()
        RECEIPT.write_bytes(canonical(value))
    else:
        validate_authority(load(AUTHORITY))
        value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
        require(value == derive_receipt(), "v1.8 candidate-seal receipt stale")
        require(rejected == mutation_proof(), "v1.8 candidate-seal mutation drift")
    print("v1.8 candidate seal: PASS roles=22 clean-build=open")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SealError, OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        print(f"v1.8 candidate seal: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
