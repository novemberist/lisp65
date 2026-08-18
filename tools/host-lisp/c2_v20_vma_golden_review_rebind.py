#!/usr/bin/env python3
"""Loudly rebind the VMA-golden review to the current closer authority."""

from __future__ import annotations

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


PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
REBIND = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.0-vma-invariant-golden-review-rebind-2026-08-13.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION_COMMIT = "6c5d0cb1"
AUTHORIZATION_BYTES = 60364
AUTHORIZATION_SHA256 = (
    "1c1bf837ff61a38d63e9b35a1f3bf53f6d295738b1fe6f0267648963e5d4d7f8")
OLD_RECEIPT_SHA256 = (
    "edd2649efc865adfdc0c6f65ba5065f933c34e66ee0d797fef2872f81de2834e")


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
    raw = subprocess.run(
        ["git", "show", f"{AUTHORIZATION_COMMIT}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION_COMMIT}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    require(len(raw) == AUTHORIZATION_BYTES and digest(raw) == AUTHORIZATION_SHA256,
            "VMA-golden rebind authorization drift")
    require(b"VMA-golden review receipt drift" in raw
            and b"standard loud, dated rebind" in raw,
            "VMA-golden rebind authorization language absent")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": digest(raw)}


def without_live_authorities(value: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(value)
    result["authority"].pop("closer_gate")
    result["authority"].pop("invariant_gate")
    return result


def rebind_value(old: dict[str, Any], new: dict[str, Any],
                 old_raw: bytes, new_raw: bytes) -> dict[str, Any]:
    require(without_live_authorities(old) == without_live_authorities(new),
            "VMA-golden rebind moves more than live tool authorities")
    before_closer = old["authority"]["closer_gate"]
    after_closer = new["authority"]["closer_gate"]
    before_gate = old["authority"]["invariant_gate"]
    after_gate = new["authority"]["invariant_gate"]
    require(before_closer == {
        "path": "tools/host-lisp/c2_product_substitution_link.py",
        "bytes": 330871,
        "sha256": "2df283182551d70a0acaf6e7a98af595034ab33b29b870bc40420b0ed7930231"}
        and after_closer == {
            "path": "tools/host-lisp/c2_product_substitution_link.py",
            "bytes": 331908,
            "sha256": "77194a61522f0cf800985382dc12c33fcc0ec2eb2962d1d0fae1cd886f256015"},
            "VMA-golden closer authority transition drift")
    require(before_gate["path"] == after_gate["path"]
            == "tools/host-lisp/c2_v20_vma_invariant_golden.py"
            and before_gate != after_gate,
            "VMA-golden gate authority transition drift")
    require(digest(old_raw) == OLD_RECEIPT_SHA256,
            "VMA-golden historical review receipt ancestry drift")
    return {
        "format": "lisp65-c2.3-v20-vma-golden-review-rebind-v1",
        "recorded_on": "2026-08-13",
        "status": "PASS: loud semantic-preserving live-authority rebind",
        "authority": {
            "owner_authorization": authorization(),
            "historical_review_receipt": bind_raw(V.RECEIPT, old_raw),
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
            "product_artifacts_changed": False,
            "device_contacts": 0,
        },
        "claim_limit": (
            "This rebind updates only the live closer-gate authority of the "
            "already reviewed VMA golden. It authorizes no card, build, "
            "completion, media, device, D2-D5, release or parity action."),
    }


def validate(value: dict[str, Any]) -> None:
    require(value["format"] == "lisp65-c2.3-v20-vma-golden-review-rebind-v1"
            and value["recorded_on"] == "2026-08-13"
            and value["status"] ==
                "PASS: loud semantic-preserving live-authority rebind"
            and value["change"]["fields"]
                == ["authority.closer_gate", "authority.invariant_gate"]
            and value["semantic_preservation"] == {
                "all_other_fields_equal": True,
                "golden_sha256": V.GOLDEN_SHA256,
                "world_probe_equal": True,
                "closer_crc_proof_equal": True,
                "cards_consumed": 0, "wplto_runs": 0,
                "product_artifacts_changed": False,
                "device_contacts": 0},
            "VMA-golden rebind validation drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "erase-loud-status": lambda x: x.update(status="PASS"),
        "move-golden": lambda x: x["semantic_preservation"].update(
            golden_sha256="0" * 64),
        "move-world-probe": lambda x: x["semantic_preservation"].update(
            world_probe_equal=False),
        "move-closer-proof": lambda x: x["semantic_preservation"].update(
            closer_crc_proof_equal=False),
        "claim-product-change": lambda x: x["semantic_preservation"].update(
            product_artifacts_changed=True),
        "hide-gate-rebind": lambda x: x["change"].update(
            fields=["authority.closer_gate"]),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate)
        except RebindError:
            rejected.append(name)
    require(rejected == list(cases), "VMA-golden rebind mutation survived")
    return rejected


def record() -> None:
    require(not REBIND.exists(), "VMA-golden rebind receipt already exists")
    old_raw = V.RECEIPT.read_bytes()
    require(digest(old_raw) == OLD_RECEIPT_SHA256,
            "pre-rebind VMA review receipt drift")
    old = json.loads(old_raw)
    new = V.build_receipt()
    new_raw = V.canonical(new)
    value = rebind_value(old, new, old_raw, new_raw)
    validate(value)
    value["mutations_rejected"] = mutations(value)
    REBIND.write_bytes(canonical(value))
    print("VMA-golden review rebind: PASS fields=two-live-authorities mutations=6")


def check() -> None:
    value = load(REBIND)
    rejected = value.pop("mutations_rejected", None)
    validate(value)
    require(rejected == mutations(value), "VMA-golden rebind mutation drift")
    require(digest(V.RECEIPT.read_bytes()) == OLD_RECEIPT_SHA256,
            "historical VMA-golden review receipt was rewritten")
    reconstructed = load(V.RECEIPT)
    reconstructed["authority"]["closer_gate"] = value["change"]["closer_gate"]["after"]
    reconstructed["authority"]["invariant_gate"] = value["change"]["invariant_gate"]["after"]
    expected_raw = V.canonical(reconstructed)
    require(value["authority"]["live_reconstructed_review"]
            == bind_raw(V.RECEIPT, expected_raw),
            "historical 2026-08-13 VMA-golden reconstruction drift")
    print("VMA-golden review rebind: CHECK PASS historical=unchanged live=bound")


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in {"record", "check", "selftest"},
            "usage: c2_v20_vma_golden_review_rebind.py record|check|selftest")
    if sys.argv[1] == "record":
        record()
    elif sys.argv[1] == "check":
        check()
    else:
        value = load(REBIND); value.pop("mutations_rejected", None)
        validate(value)
        reconstructed = load(V.RECEIPT)
        reconstructed["authority"]["closer_gate"] = value["change"]["closer_gate"]["after"]
        reconstructed["authority"]["invariant_gate"] = value["change"]["invariant_gate"]["after"]
        require(value["authority"]["live_reconstructed_review"]
                == bind_raw(V.RECEIPT, V.canonical(reconstructed)),
                "historical VMA-golden rebind reconstruction drift")
        print(f"VMA-golden review rebind: SELFTEST PASS "
              f"mutations={len(mutations(value))}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RebindError, V.VmaInvariantGoldenError, OSError, ValueError,
            KeyError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"VMA-GOLDEN REVIEW REBIND: {error}", file=sys.stderr)
        raise SystemExit(1)
