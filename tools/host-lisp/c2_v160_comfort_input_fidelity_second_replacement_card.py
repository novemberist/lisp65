#!/usr/bin/env python3
"""Run the one authorized second v1.6 input-fidelity replacement card."""

from __future__ import annotations

import argparse
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
import c2_v160_comfort_input_fidelity_replacement_card as FIRST  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v1.6-comfort-input-fidelity-second-replacement-card"
PREFLIGHT = ROOT / (
    "build/c2.3/v1.6-comfort-input-fidelity-second-replacement-card-preflight")
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
    "c2.3-v1.6-comfort-input-fidelity-second-replacement-card-receipt.json")
FINAL_RED = ARCH / (
    "c2.3-v1.6-comfort-input-fidelity-second-replacement-card-final-red.json")
PREDECESSOR_RED = ARCH / (
    "c2.3-v1.6-comfort-input-fidelity-replacement-card-final-red.json")
DRIVER = Path(__file__).resolve()
FORMAT = "lisp65-c2-v160-comfort-input-fidelity-second-replacement-card-v1"


class SecondReplacementError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SecondReplacementError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    return FIRST.bind(path)


def predecessor() -> dict[str, Any]:
    red = load(PREDECESSOR_RED)
    require(red.get("status") ==
                "FINAL RED: INPUT-FIDELITY REPLACEMENT RETURNS TO OWNER"
            and red["attempt_accounting"]["replacement_cards_consumed"] == 1
            and red["attempt_accounting"]["WPLTO_runs"] == 0
            and red["attempt_accounting"]["product_links"] == 0
            and red.get("retry_authorized") is False,
            "first replacement Final Red drift")
    return red


def expected_output_roots() -> dict[str, str]:
    return {"build": BUILD.relative_to(ROOT).as_posix(),
            "preflight": PREFLIGHT.relative_to(ROOT).as_posix(),
            "projected_ownership": PROJECTED_OWNERSHIP.relative_to(
                ROOT).as_posix(),
            "projected_full_map": PROJECTED_FULL_MAP.relative_to(
                ROOT).as_posix()}


def configure() -> dict[str, str]:
    FIRST.BUILD = BUILD
    FIRST.PREFLIGHT = PREFLIGHT
    FIRST.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT
    FIRST.INVOCATION = INVOCATION
    FIRST.PROJECTED_OWNERSHIP = PROJECTED_OWNERSHIP
    FIRST.PROJECTED_FULL_MAP = PROJECTED_FULL_MAP
    FIRST.PRODUCER_RESULT = PRODUCER_RESULT
    FIRST.SCOPE_RESULT = SCOPE_RESULT
    FIRST.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    FIRST.ABI_REPORT = ABI_REPORT
    FIRST.PRODUCT_ELF = PRODUCT_ELF
    FIRST.PRODUCT_PRG = PRODUCT_PRG
    FIRST.HOST_RECEIPT = HOST_RECEIPT
    FIRST.RECEIPT = BUILD / "unused-first-replacement-receipt.json"
    FIRST.FINAL_RED = BUILD / "unused-first-replacement-final-red.json"
    FIRST.DRIVER = DRIVER
    FIRST.configure()
    current = GATE.output_root_snapshot()
    require(current == expected_output_roots(),
            "card output-root rebind did not reach real root producer")
    return current


def ordered_gate(elf: Path | None = None) -> dict[str, Any]:
    return GATE.derive(elf, output_rebind=configure,
                       expected_output_roots=expected_output_roots())


def preflight() -> None:
    predecessor()
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "second input-fidelity replacement is one-shot")
    value = ordered_gate()
    PREFLIGHT.mkdir(parents=True)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    consumer = value["static_plane_consumer"]
    require(consumer["configuration_order"] == [
                "candidate-configurator-closure", "card-output-root-rebind",
                "real-static-plane-consumer"]
            and consumer["output_roots_after_rebind"] ==
                expected_output_roots()
            and consumer["consumer_observed_bytes"] == 46043
            and "closure-displaces-card-root" in
                consumer["mutations_rejected"]
            and value["attempt_accounting"]["product_links"] == 0,
            "second replacement combined preflight drift")
    print("v1.6 input fidelity second replacement: PREFLIGHT PASS "
          "card=0/1 order=closure,rebind,consumer static-plane=46043")


def produce_child() -> None:
    consumed = GATE.candidate_static_plane_consumer(
        install=True, output_rebind=configure,
        expected_output_roots=expected_output_roots())
    require(consumed["consumer_observed_bytes"] == 46043
            and consumed["output_roots_after_rebind"] ==
                expected_output_roots(),
            "ordered producer setup drift")
    # The rebind now owns these paths; materialize its two projections only
    # after the closure has completed, then enter the inherited producer.
    FIRST.BASE.PRODUCT.BASE.PRODUCT.BASE.write_projections()
    raise SystemExit(FIRST.BASE.PRODUCT.BASE.produce_child())


def run_child() -> str:
    completed = subprocess.run(
        [sys.executable, str(DRIVER), "_produce"], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(completed.returncode == 0,
            f"second input-fidelity replacement child red:\n{completed.stdout}")
    return completed.stdout


def card() -> None:
    predecessor()
    require(PREFLIGHT_RECEIPT.is_file() and not BUILD.exists()
            and not INVOCATION.exists() and not RECEIPT.exists()
            and not FINAL_RED.exists(),
            "second input-fidelity replacement lifecycle drift")
    persisted = load(PREFLIGHT_RECEIPT)
    GATE.validate(persisted, final=False)
    INVOCATION.write_bytes(canonical({
        "status": "INVOKED", "second_replacement_card": "1/1",
        "WPLTO_runs": 1, "product_links": 1,
        "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER),
        "media_builds": 0, "device_contacts": 0,
    }))
    output = run_child()
    require(PRODUCT_ELF.is_file() and PRODUCT_PRG.is_file(),
            "second replacement returned without linked product")
    host = ordered_gate(PRODUCT_ELF)
    HOST_RECEIPT.write_bytes(canonical(host))
    producer = load(PRODUCER_RESULT)
    value = {
        "format": FORMAT, "recorded_on": "2026-08-18",
        "status": "PASS: V1.6 INPUT-FIDELITY SECOND REPLACEMENT GREEN",
        "attempt_accounting": {"second_replacement_cards_authorized": 1,
            "second_replacement_cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "authority": {"predecessor_Final_Red": bind(PREDECESSOR_RED),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "configuration_order": host["static_plane_consumer"],
        "artifacts": {"PRG": bind(PRODUCT_PRG), "ELF": bind(PRODUCT_ELF)},
        "host_acceptance": bind(HOST_RECEIPT),
        "placement": host["placement"], "loss": host["loss"],
        "producer": {"status": producer.get("status"),
            "pid": producer.get("pid"),
            "stdout_tail": " ".join(output.split()[-24:])},
        "next": "independent review; media/device contacts remain closed",
        "claim_limit": ("One second replacement product card and host "
                        "acceptance only; no Completion, media or device."),
    }
    RECEIPT.write_bytes(canonical(value))
    print("v1.6 input fidelity second replacement: CARD PASS card=1/1 "
          "order=proved static-plane=46043 events=94/94")


def record_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in
                 (("PRG", PRODUCT_PRG), ("ELF", PRODUCT_ELF))
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2-v160-input-fidelity-second-replacement-red-v1",
        "recorded_on": "2026-08-18",
        "status": "FINAL RED: SECOND INPUT-FIDELITY REPLACEMENT TO OWNER",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {"second_replacement_cards_authorized": 1,
            "second_replacement_cards_consumed": 1,
            "WPLTO_runs": 1 if artifacts else 0, "product_links": 0,
            "media_builds": 0, "device_contacts": 0},
        "artifacts": artifacts, "retry_authorized": False,
        "owner_disposition_required": True,
        "authority": {"preflight": bind(PREFLIGHT_RECEIPT),
                      "driver": bind(DRIVER)},
    }))


def main() -> int:
    action = argparse.ArgumentParser(description=__doc__)
    action.add_argument("action", choices=("preflight", "card", "check",
                                           "_produce"))
    selected = action.parse_args().action
    if selected == "preflight": preflight()
    elif selected == "card": card()
    elif selected == "_produce": produce_child()
    elif RECEIPT.exists():
        require(load(RECEIPT)["status"].endswith("GREEN"),
                "second replacement green receipt drift")
        print("v1.6 input fidelity second replacement: CHECK PASS card=1/1")
    elif FINAL_RED.exists():
        require(load(FINAL_RED)["retry_authorized"] is False,
                "second replacement Final Red drift")
        print("v1.6 input fidelity second replacement: CHECK FINAL RED")
    else:
        print("v1.6 input fidelity second replacement: CHECK LOCKED/ARMED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: record_red(error)
            except Exception as receipt_error:
                print(f"second replacement receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 input fidelity second replacement: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
