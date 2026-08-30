#!/usr/bin/env python3
"""Seal hardware-green v1.9.0 A+B as the public-build target."""

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
MEDIA = ARCH / "c2.3-v1.9.0-release-media-receipt.json"
DEVICE_A = ARCH / "c2.3-v1.9-block-a-delivered-consumer-r8-device-result.json"
DEVICE_B = ARCH / "c2.3-v1.9-blocks-ab-display-r7-device-result-receipt.json"
D5 = ARCH / "c2.3-v1.9-r8-release-terminal-d5-receipt.json"
SOURCE = ROOT / "build/c2.3/v1.9.0-release-media-r3/shared-system/candidate-manifest.json"
AUTHORITY = ROOT / "config/c2-v190-public-build-authority.json"
RECEIPT = ARCH / "c2.3-v1.9.0-candidate-seal-receipt.json"
PLAN = ROOT / "docs/planning/v1.9.0-pre-plan.md"
SHIP = "bd6b7c7d"
STATUS = "PASS: V1.9.0 CANDIDATE SEALED FOR PUBLIC CLEAN BUILD"


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
    require(media["status"] == "PASS: V1.9.0 RELEASE MEDIA READY"
            and media["banner"] == "WORKBENCH 1.9.0"
            and media["library_closure"]["delivered_rows"] == []
            and media["library_closure"]["Comfort_absent"] is True
            and source["format"] == "lisp65-c2-lite-canonical-media-product-v1"
            and source["status"] == "passed-complete-C2-lite-two-media-product"
            and source["artifact_count"] == len(source["artifacts"]) == 19,
            "v1.9 selected product/media closure drift")
    rows = []
    for item in source["artifacts"]:
        identity = bind(ROOT / item["path"])
        require(identity == {key: item[key] for key in ("path", "bytes", "sha256")},
                f"selected shared artifact drift: {item['role']}")
        rows.append(dict(item))
    require(len(rows) == len({row["role"] for row in rows}) ==
            len({row["path"] for row in rows}) == 19,
            "v1.9 sealed role/path inventory is not unique")
    return rows, {"media": media, "source": source}


def acceptance() -> dict[str, Any]:
    a, b, d5 = load(DEVICE_A), load(DEVICE_B), load(D5)
    b_rows = {row["id"]: row for row in b["rows"]}
    require(a["status"] == "PASS: V1.9 BLOCK A HARDWARE ACCEPTED"
            and a["stopped_state"]["counters"] == {
                "raw": 136, "seen": 136, "stored": 136, "taken": 136}
            and b_rows["ABR7-1-composed-native-prompt-display"]["result"] == "PASS"
            and b_rows["ABR7-2-native-prompt-editor"]["result"] == "PASS"
            and d5["status"] ==
                "PASS: V1.9 R8 RELEASE-TERMINAL D5 GREEN AND DELTA ATTRIBUTED"
            and d5["D5"]["free"] == {
                "symbol_slots": 109, "namepool_bytes": 1486},
            "v1.9 hardware/D5 Ship authority is not green")
    return {"Block_A": bind(DEVICE_A), "Block_B": bind(DEVICE_B),
            "D5": bind(D5), "D5_free": d5["D5"]["free"],
            "forced_collection_counters": a["stopped_state"]["counters"],
            "loaded_library_roles": [], "delivered_library_roles": []}


def derive_authority() -> dict[str, Any]:
    rows, facts = selected_rows()
    return {
        "format": "lisp65-c2-public-build-authority-v7",
        "release": "v1.9.0",
        "selected_variant": "v1.9-native-capture-client-native-prompt-editor",
        "build_model": "candidate-source-plane-plus-one-WPLTO",
        "entry_point": "make workbench-product-v190",
        "candidate_manifest_path":
            "build/c2.3/v1.9.0-public-selected/candidate-manifest.json",
        "product_manifest_path":
            "build/c2.3/v1.9.0-public-selected/product-link/static-plane/"
            "narrow-static/product/substitution-artifacts.json",
        "artifact_count": 19,
        "sealed_product_artifact_set_sha256": artifact_set(rows),
        "selected_media_sha256": facts["media"]["media"]["product"]["sha256"],
        "sealed_roles": {row["role"]: {"bytes": row["bytes"],
                                        "sha256": row["sha256"]} for row in rows},
        "delivered_library_roles": [], "loaded_D5_library_roles": [],
        "excluded_library_roles": ["v16core-duplicate", "repl-comfort",
                                     "Matcher/Blink", "Block-3"],
        "editor_ownership": "resident-product-single-owner",
        "capture_lifecycle": "armed-at-native-read-line-disarmed-on-return",
        "private_evidence_is_build_input": False,
        "acceptance_evidence_rule": (
            "Hardware and Ship select the 19-role byte target but are not public "
            "compilation, link, media or clean-build inputs."),
        "nondeterminism_policy": "Every role mismatch is a clean-build First Red.",
    }


def validate_authority(value: dict[str, Any]) -> None:
    roles = value.get("sealed_roles", {})
    require(value.get("format") == "lisp65-c2-public-build-authority-v7"
            and value.get("release") == "v1.9.0"
            and value.get("selected_variant") ==
                "v1.9-native-capture-client-native-prompt-editor"
            and value.get("entry_point") == "make workbench-product-v190"
            and value.get("artifact_count") == len(roles) == 19
            and value.get("private_evidence_is_build_input") is False,
            "v1.9 public build authority envelope drift")
    require(value == derive_authority(),
            "v1.9 public build authority differs from seal")


def derive_receipt() -> dict[str, Any]:
    authority = load(AUTHORITY)
    validate_authority(authority)
    rows, facts = selected_rows()
    return {
        "format": "lisp65-c2-v190-candidate-seal-v1",
        "recorded_on": "2026-08-30", "status": STATUS,
        "authority": {"owner_Ship": ship_authority(),
            "public_build": bind(AUTHORITY), "source_manifest": bind(SOURCE),
            "media_receipt": bind(MEDIA), **acceptance()},
        "selection": {"release": "v1.9.0",
            "variant": "v1.9-native-capture-client-native-prompt-editor",
            "artifact_count": len(rows), "artifact_set_sha256": artifact_set(rows),
            "product_build_id": facts["source"]["product_build_id"],
            "profile_build_id": facts["source"]["profile_build_id"],
            "roles": [{key: row[key] for key in
                       ("role", "name", "path", "bytes", "sha256")}
                      for row in sorted(rows, key=lambda row: row["role"])]},
        "build_boundary": {"private_evidence_inputs": 0,
            "candidate_bytes_reused_by_clean_build": 0,
            "required_fresh_builds": 2,
            "entry_point": "make workbench-product-v190"},
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
        "admit-comfort": lambda x: x["excluded_library_roles"].remove(
            "repl-comfort"),
        "admit-evidence": lambda x: x.update(private_evidence_is_build_input=True),
        "change-release": lambda x: x.update(release="v1.8.0"),
    }
    base = derive_authority()
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(base); mutate(trial)
        try:
            validate_authority(trial)
        except SealError:
            rejected.append(name)
    require(rejected == list(cases), "v1.9 candidate-seal mutation survived")
    return rejected


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    require(action in ("seal", "check"), "usage: seal|check")
    if action == "seal":
        require(not AUTHORITY.exists() and not RECEIPT.exists(),
                "v1.9 candidate-seal outputs already exist")
        AUTHORITY.write_bytes(canonical(derive_authority()))
        value = derive_receipt(); value["mutations_rejected"] = mutation_proof()
        RECEIPT.write_bytes(canonical(value))
    else:
        validate_authority(load(AUTHORITY))
        value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
        require(value == derive_receipt(), "v1.9 candidate-seal receipt stale")
        require(rejected == mutation_proof(), "v1.9 mutation proof drift")
    print("v1.9 candidate seal: PASS roles=19 clean-build=open")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SealError, OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        print(f"v1.9 candidate seal: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
