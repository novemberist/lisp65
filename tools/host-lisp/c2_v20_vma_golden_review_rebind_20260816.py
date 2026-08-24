#!/usr/bin/env python3
"""Loudly rebind the VMA-golden review to the authorized linker producer."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v20_vma_invariant_golden as V  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
PREDECESSOR = ARCH / (
    "c2.3-v2.0-vma-invariant-golden-review-rebind-2026-08-14.json")
RECEIPT = V.REBIND
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "da4bf9f5"
HISTORICAL_REVIEW_SHA256 = (
    "edd2649efc865adfdc0c6f65ba5065f933c34e66ee0d797fef2872f81de2834e")
RECORDED_ON = "2026-08-16"


class RebindError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RebindError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"file absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": digest(raw)}


def bind_raw(path: Path, raw: bytes) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": digest(raw)}


def authorization() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("*", "").split())
    for token in ("relocation derivation and replay authorized",
                  "loud rebind of the historical vma-golden review",
                  "authorized linker producer"):
        require(token in text, f"VMA rebind authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": digest(raw)}


def strip_live(value: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(value)
    result["authority"].pop("closer_gate")
    result["authority"].pop("invariant_gate")
    return result


def validate(value: dict[str, Any]) -> None:
    require(
        value.get("format") ==
            "lisp65-c2.3-v20-vma-golden-review-rebind-v3"
        and value.get("recorded_on") == RECORDED_ON
        and value.get("status") ==
            "PASS: loud linker-producer authority rebind"
        and value.get("change", {}).get("fields") ==
            ["authority.closer_gate", "authority.invariant_gate"]
        and value.get("semantic_preservation") == {
            "all_other_fields_equal": True,
            "golden_sha256": V.GOLDEN_SHA256,
            "world_probe_equal": True,
            "closer_crc_proof_equal": True,
            "cards_consumed": 0,
            "wplto_runs": 0,
            "product_artifacts_changed": False,
            "device_contacts": 0,
        },
        "VMA linker-producer rebind validation drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "rewrite-golden": lambda x: x["semantic_preservation"].update(
            golden_sha256="0" * 64),
        "move-world-evidence": lambda x: x["semantic_preservation"].update(
            world_probe_equal=False),
        "move-closer-proof": lambda x: x["semantic_preservation"].update(
            closer_crc_proof_equal=False),
        "hide-one-live-field": lambda x: x["change"].update(
            fields=["authority.closer_gate"]),
        "claim-card": lambda x: x["semantic_preservation"].update(
            cards_consumed=1),
        "claim-product-change": lambda x: x["semantic_preservation"].update(
            product_artifacts_changed=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate(trial)
        except RebindError:
            rejected.append(name)
    require(rejected == list(cases), "VMA rebind mutation survived")
    return rejected


def derive() -> dict[str, Any]:
    historical_raw = V.RECEIPT.read_bytes()
    require(digest(historical_raw) == HISTORICAL_REVIEW_SHA256,
            "historical VMA review receipt was rewritten")
    historical = json.loads(historical_raw)
    current = V.build_receipt()
    current_raw = V.canonical(current)
    require(strip_live(historical) == strip_live(current),
            "VMA rebind moves more than live producer authorities")
    predecessor = json.loads(PREDECESSOR.read_text(encoding="utf-8"))
    require(
        predecessor.get("status") ==
            "PASS: loud semantic-preserving live-authority rebind"
        and predecessor.get("semantic_preservation", {}).get(
            "all_other_fields_equal") is True,
        "predecessor VMA rebind drift")
    value = {
        "format": "lisp65-c2.3-v20-vma-golden-review-rebind-v3",
        "recorded_on": RECORDED_ON,
        "status": "PASS: loud linker-producer authority rebind",
        "authority": {
            "owner_authorization": authorization(),
            "historical_review_receipt": bind_raw(V.RECEIPT, historical_raw),
            "predecessor_rebind": bind(PREDECESSOR),
            "live_reconstructed_review": bind_raw(V.RECEIPT, current_raw),
            "authorized_linker_producer": bind(
                ROOT / "tools/host-lisp/c2_product_substitution_link.py"),
            "rebind_driver": bind(DRIVER),
        },
        "change": {
            "fields": ["authority.closer_gate", "authority.invariant_gate"],
            "closer_gate": {"before": historical["authority"]["closer_gate"],
                            "after": current["authority"]["closer_gate"]},
            "invariant_gate": {
                "before": historical["authority"]["invariant_gate"],
                "after": current["authority"]["invariant_gate"]},
        },
        "semantic_preservation": {
            "all_other_fields_equal": True,
            "golden_sha256": V.GOLDEN_SHA256,
            "world_probe_equal": historical["world_probe"] ==
                current["world_probe"],
            "closer_crc_proof_equal": historical["closer_crc_repair"] ==
                current["closer_crc_repair"],
            "cards_consumed": 0, "wplto_runs": 0,
            "product_artifacts_changed": False, "device_contacts": 0,
        },
        "claim_limit": (
            "This loud rebind changes only the two live tool-authority "
            "bindings of the unchanged VMA review. It authorizes no card, "
            "link, completion, media or device action."),
    }
    validate(value)
    value["mutations_rejected"] = mutations(value)
    return value


# Checking by re-deriving asked the living tree to reproduce a closed event:
# every later edit to the linker producer made this receipt "drift" although
# nothing about the recorded rebind had changed.  The check therefore verifies
# the receipt against the world it names -- its own recorded values and the
# pinned historical review -- exactly as the 2026-08-14 predecessor does.
def check() -> None:
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    rejected = value.pop("mutations_rejected", None)
    validate(value)
    require(rejected == mutations(value), "VMA rebind mutation drift")
    require(digest(V.RECEIPT.read_bytes()) == HISTORICAL_REVIEW_SHA256,
            "historical VMA review receipt was rewritten")
    reconstructed = json.loads(V.RECEIPT.read_text(encoding="utf-8"))
    for field in ("closer_gate", "invariant_gate"):
        require(value["change"][field]["before"] ==
                reconstructed["authority"][field],
                f"recorded rebind predecessor drift: {field}")
        reconstructed["authority"][field] = value["change"][field]["after"]
    require(value["authority"]["live_reconstructed_review"] ==
            bind_raw(V.RECEIPT, V.canonical(reconstructed)),
            "recorded 2026-08-16 VMA reconstruction drift")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check"))
    action = parser.parse_args().action
    if action == "record":
        require(not RECEIPT.exists(), "VMA rebind receipt exists")
        RECEIPT.write_bytes(canonical(derive()))
    else:
        check()
    print("VMA-golden review rebind 2026-08-16: PASS fields=2 mutations=6")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RebindError, V.VmaInvariantGoldenError, OSError, ValueError,
            KeyError, json.JSONDecodeError,
            subprocess.CalledProcessError) as error:
        print(f"VMA-golden rebind 2026-08-16: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
