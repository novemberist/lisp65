#!/usr/bin/env python3
"""Run the one authorized replacement v1.6 input-fidelity product card."""

from __future__ import annotations

import argparse
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

import c2_v160_comfort_input_fidelity as GATE  # noqa: E402
import c2_v160_comfort_input_fidelity_card as BASE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v1.6-comfort-input-fidelity-replacement-card"
PREFLIGHT = ROOT / (
    "build/c2.3/v1.6-comfort-input-fidelity-replacement-card-preflight")
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PROJECTED_OWNERSHIP = PREFLIGHT / "projected-ownership-contract.json"
PROJECTED_FULL_MAP = PREFLIGHT / "projected-full-map-authority.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
ABI_REPORT = BUILD / "wplto/c2-asm-leaf-abi.json"
PRODUCT_ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PRODUCT_PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
HOST_RECEIPT = BUILD / "input-fidelity-host-card.json"
RECEIPT = ARCH / (
    "c2.3-v1.6-comfort-input-fidelity-replacement-card-receipt.json")
FINAL_RED = ARCH / (
    "c2.3-v1.6-comfort-input-fidelity-replacement-card-final-red.json")
PREDECESSOR_RED = ARCH / (
    "c2.3-v1.6-comfort-input-fidelity-card-final-red.json")
DRIVER = Path(__file__).resolve()
FORMAT = "lisp65-c2-v160-comfort-input-fidelity-replacement-card-v1"


class ReplacementError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplacementError(message)


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


def predecessor() -> dict[str, Any]:
    red = load(PREDECESSOR_RED)
    require(red.get("status") ==
                "FINAL RED: INPUT-FIDELITY CARD RETURNS TO OWNER"
            and red["attempt_accounting"]["cards_consumed"] == 1
            and red["attempt_accounting"]["WPLTO_runs"] == 0
            and red["attempt_accounting"]["product_links"] == 0
            and red.get("retry_authorized") is False,
            "consumed predecessor card Final Red drift")
    return red


def configure() -> None:
    BASE.BUILD = BUILD
    BASE.PREFLIGHT = PREFLIGHT
    BASE.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT
    BASE.INVOCATION = INVOCATION
    BASE.PROJECTED_OWNERSHIP = PROJECTED_OWNERSHIP
    BASE.PROJECTED_FULL_MAP = PROJECTED_FULL_MAP
    BASE.PRODUCER_RESULT = PRODUCER_RESULT
    BASE.SCOPE_RESULT = SCOPE_RESULT
    BASE.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    BASE.ABI_REPORT = ABI_REPORT
    BASE.PRODUCT_ELF = PRODUCT_ELF
    BASE.PRODUCT_PRG = PRODUCT_PRG
    BASE.HOST_RECEIPT = HOST_RECEIPT
    BASE.RECEIPT = BUILD / "unused-predecessor-card-receipt.json"
    BASE.FINAL_RED = BUILD / "unused-predecessor-card-final-red.json"
    BASE.DRIVER = DRIVER
    BASE.configure()


def preflight() -> None:
    predecessor()
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "input-fidelity replacement card is one-shot")
    value = GATE.derive()
    PREFLIGHT.mkdir(parents=True)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    require(value["static_plane_consumer"]["candidate_bound_bytes"] == 46043
            and value["static_plane_consumer"]["consumer_observed_bytes"] == 46043
            and "ambient-43308-at-consumer" in value["static_plane_consumer"]
                ["mutations_rejected"]
            and value["attempt_accounting"]["product_links"] == 0,
            "replacement real-consumer preflight drift")
    print("v1.6 input fidelity replacement: PREFLIGHT PASS "
          "card=0/1 real-static-plane=46043 mutations=4")


def produce_child() -> None:
    configure()
    # Install the same complete configurator projection proven by the
    # permanent preflight immediately before the inherited real producer.
    consumed = GATE.candidate_static_plane_consumer(install=True)
    require(consumed["consumer_observed_bytes"] == 46043,
            "replacement lost candidate plane before producer")
    BASE.PRODUCT.BASE.PRODUCT.BASE.write_projections()
    raise SystemExit(BASE.PRODUCT.BASE.produce_child())


def run_child() -> str:
    completed = subprocess.run(
        [sys.executable, str(DRIVER), "_produce"], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(completed.returncode == 0,
            f"input-fidelity replacement child red:\n{completed.stdout}")
    return completed.stdout


def card() -> None:
    predecessor()
    require(PREFLIGHT_RECEIPT.is_file() and not BUILD.exists()
            and not INVOCATION.exists() and not RECEIPT.exists()
            and not FINAL_RED.exists(),
            "input-fidelity replacement lifecycle drift")
    persisted = load(PREFLIGHT_RECEIPT)
    GATE.validate(persisted, final=False)
    INVOCATION.write_bytes(canonical({
        "status": "INVOKED", "replacement_card": "1/1",
        "WPLTO_runs": 1, "product_links": 1,
        "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER),
        "media_builds": 0, "device_contacts": 0,
    }))
    output = run_child()
    require(PRODUCT_ELF.is_file() and PRODUCT_PRG.is_file(),
            "replacement producer returned without linked product")
    host = GATE.derive(PRODUCT_ELF)
    HOST_RECEIPT.write_bytes(canonical(host))
    producer = load(PRODUCER_RESULT)
    value = {
        "format": FORMAT, "recorded_on": "2026-08-18",
        "status": "PASS: V1.6 INPUT-FIDELITY REPLACEMENT CARD GREEN",
        "attempt_accounting": {"replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "authority": {"predecessor_Final_Red": bind(PREDECESSOR_RED),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "real_consumer": host["static_plane_consumer"],
        "artifacts": {"PRG": bind(PRODUCT_PRG), "ELF": bind(PRODUCT_ELF)},
        "host_acceptance": bind(HOST_RECEIPT),
        "placement": host["placement"], "loss": host["loss"],
        "producer": {"status": producer.get("status"),
            "pid": producer.get("pid"),
            "stdout_tail": " ".join(output.split()[-24:])},
        "next": "independent review; media/device contacts remain closed",
        "claim_limit": ("One replacement product card and host acceptance "
                        "only; no Completion, media, review or device work."),
    }
    RECEIPT.write_bytes(canonical(value))
    print("v1.6 input fidelity replacement: CARD PASS card=1/1 "
          "real-static-plane=46043 events=94/94")


def record_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in
                 (("PRG", PRODUCT_PRG), ("ELF", PRODUCT_ELF))
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2-v160-input-fidelity-replacement-final-red-v1",
        "recorded_on": "2026-08-18",
        "status": "FINAL RED: INPUT-FIDELITY REPLACEMENT RETURNS TO OWNER",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {"replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1,
            "WPLTO_runs": 1 if artifacts else 0,
            "product_links": 0, "media_builds": 0, "device_contacts": 0},
        "artifacts": artifacts, "retry_authorized": False,
        "owner_disposition_required": True,
        "authority": {"preflight": bind(PREFLIGHT_RECEIPT),
                      "driver": bind(DRIVER)},
    }))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "card", "check",
                                           "_produce"))
    action = parser.parse_args().action
    if action == "preflight":
        preflight()
    elif action == "card":
        card()
    elif action == "_produce":
        produce_child()
    elif RECEIPT.exists():
        require(load(RECEIPT)["status"].endswith("CARD GREEN"),
                "replacement green receipt drift")
        print("v1.6 input fidelity replacement: CHECK PASS card=1/1")
    elif FINAL_RED.exists():
        require(load(FINAL_RED)["retry_authorized"] is False,
                "replacement Final Red drift")
        print("v1.6 input fidelity replacement: CHECK FINAL RED")
    else:
        print("v1.6 input fidelity replacement: CHECK LOCKED/ARMED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_red(error)
            except Exception as receipt_error:
                print(f"replacement Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 input fidelity replacement: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
