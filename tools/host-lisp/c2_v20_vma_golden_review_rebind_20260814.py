#!/usr/bin/env python3
"""Loudly rebind the historical VMA-golden review to current live gates."""

from __future__ import annotations

import argparse
from copy import deepcopy
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

import c2_v20_vma_invariant_golden as V  # noqa: E402


PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
PREDECESSOR_REBIND = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.0-vma-invariant-golden-review-rebind-2026-08-13.json")
# This dated receipt belongs to the 2026-08-14 text-recovery world.  The live
# V.REBIND intentionally advances as later Golden reviews are authorized; a
# historical check must not silently follow that living alias.
REBIND = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.0-vma-invariant-golden-review-rebind-2026-08-14.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "428edb5e"
OLD_RECEIPT_SHA256 = (
    "edd2649efc865adfdc0c6f65ba5065f933c34e66ee0d797fef2872f81de2834e")
RECORDED_ON = "2026-08-14"


class RebindError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RebindError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind_raw(path: Path, raw: bytes) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": digest(raw)}


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"file absent: {path}")
    return bind_raw(path, path.read_bytes())


def authorization() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().split()).lower()
    require("known vma-golden receipt drift" in text
            and "loud, dated rebind" in text,
            "dated VMA-golden rebind authorization absent")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": digest(raw)}


def strip_live(value: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(value)
    result["authority"].pop("closer_gate")
    result["authority"].pop("invariant_gate")
    return result


def derive() -> dict[str, Any]:
    old_raw = V.RECEIPT.read_bytes()
    require(digest(old_raw) == OLD_RECEIPT_SHA256,
            "historical VMA review receipt was rewritten")
    old = json.loads(old_raw)
    new = V.build_receipt()
    new_raw = V.canonical(new)
    require(strip_live(old) == strip_live(new),
            "VMA rebind moves more than live gate authorities")
    before_closer = old["authority"]["closer_gate"]
    after_closer = new["authority"]["closer_gate"]
    before_gate = old["authority"]["invariant_gate"]
    after_gate = new["authority"]["invariant_gate"]
    require(before_closer != after_closer and before_gate != after_gate,
            "VMA live-gate authority did not move")
    value = {
        "format": "lisp65-c2.3-v20-vma-golden-review-rebind-v2",
        "recorded_on": RECORDED_ON,
        "status": "PASS: loud semantic-preserving live-authority rebind",
        "authority": {
            "owner_authorization": authorization(),
            "historical_review_receipt": bind_raw(V.RECEIPT, old_raw),
            "predecessor_rebind": bind(PREDECESSOR_REBIND),
            "live_reconstructed_review": bind_raw(V.RECEIPT, new_raw),
            "rebind_driver": bind(DRIVER),
        },
        "change": {
            "fields": ["authority.closer_gate", "authority.invariant_gate"],
            "closer_gate": {"before": before_closer, "after": after_closer},
            "invariant_gate": {"before": before_gate, "after": after_gate},
        },
        "semantic_preservation": {
            "all_other_fields_equal": True,
            "golden_sha256": new["vma_invariant_golden"]["sha256"],
            "world_probe_equal": old["world_probe"] == new["world_probe"],
            "closer_crc_proof_equal":
                old["closer_crc_repair"] == new["closer_crc_repair"],
            "cards_consumed": 0, "wplto_runs": 0,
            "product_artifacts_changed": False, "device_contacts": 0,
        },
        "claim_limit": (
            "This dated rebind changes only live tool-authority bindings of the "
            "unchanged VMA golden review. It authorizes no card, replay, "
            "completion, media, device, D1-D5, release or parity action."),
    }
    validate(value)
    value["mutations_rejected"] = mutations(value)
    return value


def validate(value: dict[str, Any]) -> None:
    require(
        value["format"] == "lisp65-c2.3-v20-vma-golden-review-rebind-v2"
        and value["recorded_on"] == RECORDED_ON
        and value["status"] == "PASS: loud semantic-preserving live-authority rebind"
        and value["change"]["fields"]
            == ["authority.closer_gate", "authority.invariant_gate"]
        and value["semantic_preservation"] == {
            "all_other_fields_equal": True,
            "golden_sha256": V.GOLDEN_SHA256,
            "world_probe_equal": True, "closer_crc_proof_equal": True,
            "cards_consumed": 0, "wplto_runs": 0,
            "product_artifacts_changed": False, "device_contacts": 0},
        "dated VMA-golden rebind validation drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases = {
        "erase-loud-status": lambda x: x.update(status="PASS"),
        "move-golden": lambda x: x["semantic_preservation"].update(
            golden_sha256="0" * 64),
        "move-world-probe": lambda x: x["semantic_preservation"].update(
            world_probe_equal=False),
        "move-closer-proof": lambda x: x["semantic_preservation"].update(
            closer_crc_proof_equal=False),
        "claim-product-change": lambda x: x["semantic_preservation"].update(
            product_artifacts_changed=True),
        "claim-card": lambda x: x["semantic_preservation"].update(cards_consumed=1),
        "hide-gate-rebind": lambda x: x["change"].update(
            fields=["authority.closer_gate"]),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate(candidate)
        except RebindError:
            rejected.append(name)
    require(rejected == list(cases), "dated VMA rebind mutation survived")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check"))
    action = parser.parse_args().action
    if action == "record":
        value = derive()
        REBIND.write_bytes(canonical(value))
    else:
        # Historical receipts witness their own world; checking one reads and
        # validates the recorded dated value rather than reconstructing it
        # from the current linker/Golden aliases.
        value = load(REBIND)
        rejected = value.pop("mutations_rejected", None)
        validate(value)
        require(rejected == mutations(value),
                "dated VMA-golden rebind mutation receipt drift")
    print("VMA-golden review rebind 2026-08-14: PASS fields=2 mutations=7")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RebindError, V.VmaInvariantGoldenError, OSError, ValueError,
            KeyError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"VMA-golden rebind 2026-08-14: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
