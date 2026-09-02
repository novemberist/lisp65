#!/usr/bin/env python3
"""Seal the Ship-selected WORKBENCH 2.0.0 product for public clean builds."""

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
MEDIA = ARCH / "c2.3-v2.0.0-release-media-receipt.json"
DEVICE = ARCH / "c2.3-v2.0-release-strip-device-result-receipt.json"
ATTRIBUTIONS = ARCH / "c2.3-v2.0-release-device-attributions-receipt.json"
CARD = ARCH / "c2.3-v2.0.0-release-card-r3-receipt.json"
SOURCE = ROOT / "build/c2.3/v2.0.0-release-media-r1/shared-system/candidate-manifest.json"
AUTHORITY = ROOT / "config/c2-v200-public-build-authority.json"
RECEIPT = ARCH / "c2.3-v2.0.0-candidate-seal-receipt.json"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
SHIP = "00cc347a"
STATUS = "PASS: V2.0.0 CANDIDATE SEALED FOR PUBLIC CLEAN BUILD"
VARIANT = "v2.0-tier1-lossless-native-editor-stripped"


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
    text = " ".join(raw.decode().lower().replace("`", "").replace(
        "*", "").split())
    require("the owner said ship" in text and "publish remains closed" in text,
            "owner Ship authority absent")
    return {"authority": "git-blob", "commit": SHIP, "path": relative,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def selected_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    media, source = load(MEDIA), load(SOURCE)
    require(media["status"] == "PASS: V2.0.0 RELEASE MEDIA READY"
            and media["banner"] == "WORKBENCH 2.0.0"
            and source["format"] == "lisp65-c2-lite-canonical-media-product-v1"
            and source["status"] == "passed-complete-C2-lite-two-media-product"
            and source["artifact_count"] == len(source["artifacts"]) == 19,
            "v2.0 selected product/media closure drift")
    rows = []
    for item in source["artifacts"]:
        identity = bind(ROOT / item["path"])
        require(identity == {key: item[key] for key in ("path", "bytes", "sha256")},
                f"selected shared artifact drift: {item['role']}")
        rows.append(dict(item))
    require(len(rows) == len({row["role"] for row in rows}) ==
            len({row["path"] for row in rows}) == 19,
            "v2.0 sealed role/path inventory is not unique")
    require(artifact_set(rows) == source["artifact_set_sha256"],
            "v2.0 selected artifact-set identity drift")
    return rows, {"media": media, "source": source}


def acceptance() -> dict[str, Any]:
    device, deltas, card = map(load, (DEVICE, ATTRIBUTIONS, CARD))
    counters = device["rows"][1]["captures"]["counter_values"]
    d5 = device["rows"][3]["D5"]["free"]
    require(device["decision"]["all_four_claim_groups_hardware_green"] is True
            and counters == {"raw": 138, "seen": 138,
                             "stored": 138, "taken": 138}
            and d5 == {"symbol_slots": 107, "namepool_bytes": 1467}
            and deltas["status"] ==
                "PASS: V2.0 DEVICE DELTAS ATTRIBUTED AND COLD-BOOT RULE ARMED"
            and deltas["decision"]["release_card"] == "AUTHORIZED"
            and card["status"] ==
                "PASS: WORKBENCH 2.0.0 RELEASE PRODUCT CARD GREEN",
            "v2.0 hardware/D5 Ship authority is not green")
    return {"device": bind(DEVICE), "device_attributions": bind(ATTRIBUTIONS),
            "release_card": bind(CARD), "D5_free": d5,
            "forced_collection_counters": counters,
            "loaded_library_roles": [], "delivered_library_roles": []}


def derive_authority() -> dict[str, Any]:
    rows, facts = selected_rows()
    profile_path = ROOT / next(
        row["path"] for row in rows if row["role"] == "resolved-profile")
    profile = dict(line.split("=", 1)
        for line in profile_path.read_text(encoding="utf-8").splitlines()
        if "=" in line)
    stable_profile = {key: profile[key] for key in (
        "c2_artifacts_sha256", "direct_entry_contract_sha256",
        "v2_profile_parity_sha256")}
    return {
        "format": "lisp65-c2-public-build-authority-v8",
        "release": "v2.0.0", "selected_variant": VARIANT,
        "build_model": "candidate-source-plane-plus-one-WPLTO",
        "entry_point": "make workbench-product-v200",
        "candidate_manifest_path":
            "build/c2.3/v2.0.0-public-selected/candidate-manifest.json",
        "product_manifest_path":
            "build/c2.3/v2.0.0-public-selected/product-link/static-plane/"
            "narrow-static/product/substitution-artifacts.json",
        "artifact_count": 19,
        "sealed_product_artifact_set_sha256": artifact_set(rows),
        "sealed_path_dependent_profile_fields": stable_profile,
        "selected_media_sha256": facts["media"]["media"]["product"]["sha256"],
        "sealed_roles": {row["role"]: {"bytes": row["bytes"],
                                         "sha256": row["sha256"]} for row in rows},
        "delivered_library_roles": [], "loaded_D5_library_roles": [],
        "excluded_library_roles": ["v16core-duplicate", "repl-comfort",
                                     "Matcher/Blink", "Tier-2"],
        "Tier_1_contract_counts": {"error-raised": 545,
            "documented-permissive": 179, "silently-wrong": 110},
        "editor_ownership": "resident-product-single-owner",
        "capture_lifecycle": "armed-at-native-read-line-disarmed-on-return",
        "packed_gates": ["transitive-closure", "generation-coherence"],
        "private_evidence_is_build_input": False,
        "acceptance_evidence_rule": (
            "Hardware and Ship select the 19-role byte target but are not public "
            "compilation, link, media or clean-build inputs."),
        "nondeterminism_policy": "Every role mismatch is a clean-build First Red.",
    }


def validate_authority(value: dict[str, Any]) -> None:
    roles = value.get("sealed_roles", {})
    require(value.get("format") == "lisp65-c2-public-build-authority-v8"
            and value.get("release") == "v2.0.0"
            and value.get("selected_variant") == VARIANT
            and value.get("entry_point") == "make workbench-product-v200"
            and value.get("artifact_count") == len(roles) == 19
            and value.get("private_evidence_is_build_input") is False,
            "v2.0 public build authority envelope drift")
    require(value == derive_authority(),
            "v2.0 public build authority differs from seal")


def derive_receipt() -> dict[str, Any]:
    authority = load(AUTHORITY)
    validate_authority(authority)
    rows, facts = selected_rows()
    return {
        "format": "lisp65-c2-v200-candidate-seal-v1",
        "recorded_on": "2026-09-02", "status": STATUS,
        "authority": {"owner_Ship": ship_authority(),
            "public_build": bind(AUTHORITY), "source_manifest": bind(SOURCE),
            "media_receipt": bind(MEDIA), **acceptance()},
        "selection": {"release": "v2.0.0", "variant": VARIANT,
            "artifact_count": len(rows), "artifact_set_sha256": artifact_set(rows),
            "product_build_id": facts["source"]["product_build_id"],
            "profile_build_id": facts["source"]["profile_build_id"],
            "roles": [{key: row[key] for key in
                       ("role", "name", "path", "bytes", "sha256")}
                      for row in sorted(rows, key=lambda row: row["role"])]},
        "build_boundary": {"private_evidence_inputs": 0,
            "candidate_bytes_reused_by_clean_build": 0,
            "required_fresh_builds": 2,
            "entry_point": "make workbench-product-v200"},
        "execution_accounting": {"WPLTO_runs": 0, "product_links": 0,
                                 "media_builds": 0, "device_contacts": 0},
        "next": "two-varied-fresh-public-clean-build-qualification",
        "claim_limit": "Selects bytes; does not publish, tag or extend claims.",
    }


def mutation_proof() -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "close-capture": lambda x: x.update(capture_lifecycle="closed"),
        "lose-editor": lambda x: x.update(editor_ownership="fallback-C-reader"),
        "drop-role": lambda x: x["sealed_roles"].pop("product-d81"),
        "lose-tier1": lambda x: x["Tier_1_contract_counts"].update(
            **{"silently-wrong": 172}),
        "admit-comfort": lambda x: x["excluded_library_roles"].remove(
            "repl-comfort"),
        "admit-evidence": lambda x: x.update(private_evidence_is_build_input=True),
        "change-release": lambda x: x.update(release="v1.9.0"),
    }
    base = derive_authority()
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(base); mutate(trial)
        try:
            validate_authority(trial)
        except SealError:
            rejected.append(name)
    require(rejected == list(cases), "v2.0 candidate-seal mutation survived")
    return rejected


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    require(action in ("seal", "refresh-profile-authority", "check"),
            "usage: seal|refresh-profile-authority|check")
    if action == "seal":
        require(not AUTHORITY.exists() and not RECEIPT.exists(),
                "v2.0 candidate-seal outputs already exist")
        AUTHORITY.write_bytes(canonical(derive_authority()))
        value = derive_receipt(); value["mutations_rejected"] = mutation_proof()
        RECEIPT.write_bytes(canonical(value))
    elif action == "refresh-profile-authority":
        old_authority, old_receipt = load(AUTHORITY), load(RECEIPT)
        successor = derive_authority()
        require("sealed_path_dependent_profile_fields" not in old_authority
                and old_authority == {key: value for key, value in
                    successor.items()
                    if key != "sealed_path_dependent_profile_fields"}
                and old_receipt.get("status") == STATUS
                and old_receipt.get("selection", {}).get(
                    "artifact_set_sha256") ==
                    successor["sealed_product_artifact_set_sha256"],
                "v2.0 public profile-authority refresh is not additive")
        AUTHORITY.write_bytes(canonical(successor))
        value = derive_receipt(); value["mutations_rejected"] = mutation_proof()
        RECEIPT.write_bytes(canonical(value))
    else:
        validate_authority(load(AUTHORITY))
        value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
        require(value == derive_receipt(), "v2.0 candidate-seal receipt stale")
        require(rejected == mutation_proof(), "v2.0 mutation proof drift")
    print("v2.0 candidate seal: PASS roles=19 clean-build=open")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SealError, OSError, KeyError, ValueError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"v2.0 candidate seal: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
