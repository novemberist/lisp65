#!/usr/bin/env python3
"""Seal the one read-only Acceptance resume for the nested-MAP candidate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v160_r1_stored_world_conversions as ACCEPT  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v1.6-nested-map-swap-replacement-card"
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
PRODUCER = BUILD / "producer-result.json"
RESULT = BUILD / "artifact-acceptance.json"
ATTRIBUTION = ARCH / "c2.3-v1.6-nested-map-swap-acceptance-attribution.json"
RECEIPT = ARCH / "c2.3-v1.6-nested-map-swap-acceptance-union-resume.json"
AUTHORIZATION = "46af5798"
STATUS = "PASS: NESTED MAP ACCEPTANCE ACTIVE-REGISTRY UNION"


class ResumeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResumeError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"object expected: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    name = "docs/planning/v1.6.0-freight-work-plan.md"
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{name}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").split())
    for token in ("union of all active card registries",
                  "no per-registry enumeration in the consumer",
                  "read-only acceptance resume"):
        require(token in text, f"Acceptance-union authority absent: {token}")
    return {"authority": "git-blob", "commit": AUTHORIZATION, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def configure() -> None:
    PRODUCT.configure_input_capture()
    PRODUCT.configure_input_hybrid()
    PRODUCT.configure_refill_boundary_witness()


def seal() -> dict[str, Any]:
    require(not RECEIPT.exists(), "Acceptance-union resume is one-shot")
    attribution = load(ATTRIBUTION)
    producer = load(PRODUCER)
    result = load(RESULT)
    artifacts = producer["artifacts"]
    before = {"ELF": artifacts["elf"], "PRG": artifacts["prg"]}
    after = {"ELF": bind(ELF), "PRG": bind(PRG)}
    require(before == after, "read-only Acceptance changed frozen pair")
    require(after["ELF"] == attribution["inputs"]["frozen_candidate_ELF"],
            "Acceptance pair differs from attributed frozen ELF")

    configure()
    mutations = ACCEPT.additive_freight_mutations(ELF)
    freight = result.get("additive_card_freight")
    expected_names = set(attribution["worlds"]["complete_card_freight_sections"])
    require(result.get("status") == "PASS" and isinstance(freight, dict)
            and freight.get("candidate_sections") == 107
            and freight.get("golden_sections") == 103
            and set(freight.get("registered_sections", [])) == expected_names
            and freight["placement_gate"]["registries"] ==
                ["input-fidelity", "refill-boundary-witness"]
            and mutations == ["unregistered-third-category",
                "double-golden-and-card-authority",
                "address-snapshot-in-freight-row",
                "omitted-active-registry"],
            "active-registry Acceptance result or mutations drift")
    value = {"format": "lisp65-c2-v160-nested-map-acceptance-union-resume-v1",
        "status": STATUS, "authority": authority(),
        "attribution": bind(ATTRIBUTION), "frozen_pair_before": before,
        "frozen_pair_after": after, "acceptance_result": bind(RESULT),
        "active_registry_union": freight["placement_gate"],
        "registered_sections": freight["registered_sections"],
        "mutations_rejected": mutations,
        "attempt_accounting": {"acceptance_resumes": 1, "WPLTO_runs": 0,
            "product_links": 0, "cards_consumed": 0, "media_builds": 0,
            "device_contacts": 0}, "MAP_fix_closed": True,
        "next": "artifact-only replacement media and seam confirmation contact"}
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    return value


def check() -> dict[str, Any]:
    value = load(RECEIPT)
    require(value["status"] == STATUS and value["frozen_pair_before"] ==
            value["frozen_pair_after"] and value["MAP_fix_closed"] is True
            and value["attempt_accounting"] == {"acceptance_resumes": 1,
                "WPLTO_runs": 0, "product_links": 0, "cards_consumed": 0,
                "media_builds": 0, "device_contacts": 0},
            "Acceptance-union resume receipt drift")
    return value


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else "check"
    if action == "seal":
        seal(); print("nested MAP Acceptance union: RESUME PASS 1/1")
    elif action == "check":
        check(); print("nested MAP Acceptance union: CHECK PASS")
    else:
        raise ResumeError(f"unknown action: {action}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"nested MAP Acceptance union: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
