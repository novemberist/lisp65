#!/usr/bin/env python3
"""Run the one authorized v1.6 Comfort input-fidelity product card."""

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
import c2_v21_wysiwyg_text_recovery_replacement_card as PRODUCT  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v1.6-comfort-input-fidelity-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-comfort-input-fidelity-card-preflight"
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
RECEIPT = ARCH / "c2.3-v1.6-comfort-input-fidelity-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-comfort-input-fidelity-card-final-red.json"
DRIVER = Path(__file__).resolve()
FORMAT = "lisp65-c2-v160-comfort-input-fidelity-product-card-v1"


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def configure() -> None:
    PRODUCT.BUILD = BUILD
    PRODUCT.PREFLIGHT = PREFLIGHT
    PRODUCT.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT
    PRODUCT.SEMANTIC_RECEIPT = PREFLIGHT / "semantic-repl-compile.json"
    PRODUCT.INVOCATION = INVOCATION
    PRODUCT.PROJECTED_OWNERSHIP = PROJECTED_OWNERSHIP
    PRODUCT.PROJECTED_FULL_MAP = PROJECTED_FULL_MAP
    PRODUCT.PRODUCER_RESULT = PRODUCER_RESULT
    PRODUCT.SCOPE_RESULT = SCOPE_RESULT
    PRODUCT.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    PRODUCT.ABI_REPORT = ABI_REPORT
    PRODUCT.RECEIPT = BUILD / "unused-predecessor-card-receipt.json"
    PRODUCT.FINAL_RED = BUILD / "unused-predecessor-card-final-red.json"
    PRODUCT.DRIVER = DRIVER
    PRODUCT.LINK = 117
    PRODUCT.set_paths()
    PRODUCT.install()
    product_link = PRODUCT.BASE.PRODUCT.BASE.PRODUCT
    activation = product_link.configure_input_capture()
    require(activation["feature"] == "LISP65_V160_INPUT_CAPTURE"
            and activation["source"] ==
                "src/optional/c2_kernal_input_capture.s"
            and len(activation["sections"]) == 2,
            "input-fidelity capture activation drift")


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "v1.6 input-fidelity card is one-shot")
    value = GATE.derive()
    PREFLIGHT.mkdir(parents=True)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    require(value["status"] == "PREFLIGHT-GREEN: FINAL PRODUCT LINK REQUIRED"
            and value["attempt_accounting"]["product_links"] == 0,
            "input-fidelity preflight drift")
    print("v1.6 input fidelity card: PREFLIGHT PASS card=0/1")


def produce_child() -> None:
    configure()
    # This is the same real projection/producer boundary used by Link 116.
    # Only its owned output roots differ.
    PRODUCT.BASE.PRODUCT.BASE.write_projections()
    raise SystemExit(PRODUCT.BASE.produce_child())


def run_child(action: str) -> str:
    completed = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(completed.returncode == 0,
            f"input-fidelity child {action} red:\n{completed.stdout}")
    return completed.stdout


def card() -> None:
    require(PREFLIGHT_RECEIPT.is_file() and not BUILD.exists()
            and not INVOCATION.exists() and not RECEIPT.exists()
            and not FINAL_RED.exists(),
            "v1.6 input-fidelity card lifecycle drift")
    persisted = load(PREFLIGHT_RECEIPT)
    GATE.validate(persisted, final=False)
    INVOCATION.write_bytes(canonical({
        "status": "INVOKED", "card": "1/1", "product_links": 1,
        "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER),
        "media_builds": 0, "device_contacts": 0,
    }))
    output = run_child("_produce")
    require(PRODUCT_ELF.is_file() and PRODUCT_PRG.is_file(),
            "producer returned without final linked product")
    host = GATE.derive(PRODUCT_ELF)
    HOST_RECEIPT.write_bytes(canonical(host))
    producer = load(PRODUCER_RESULT)
    value = {
        "format": FORMAT, "recorded_on": "2026-08-18",
        "status": "PASS: V1.6 COMFORT INPUT-FIDELITY PRODUCT CARD GREEN",
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "WPLTO_runs": 1, "product_links": 1, "media_builds": 0,
            "device_contacts": 0},
        "authority": {"contract": bind(GATE.CONTRACT),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "artifacts": {"PRG": bind(PRODUCT_PRG), "ELF": bind(PRODUCT_ELF)},
        "host_acceptance": bind(HOST_RECEIPT),
        "placement": host["placement"], "loss": host["loss"],
        "producer": {"status": producer.get("status"),
            "pid": producer.get("pid"),
            "stdout_tail": " ".join(output.split()[-24:])},
        "next": "independent review; device contacts remain closed",
        "claim_limit": "One product link and host acceptance only; no Completion, media, review or device acceptance.",
    }
    RECEIPT.write_bytes(canonical(value))
    print("v1.6 input fidelity card: CARD PASS card=1/1 "
          "events=94/94 C2-reserve=2 ordinary-reserve>=6")


def record_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in
                 (("PRG", PRODUCT_PRG), ("ELF", PRODUCT_ELF))
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2-v160-comfort-input-fidelity-card-final-red-v1",
        "recorded_on": "2026-08-18",
        "status": "FINAL RED: INPUT-FIDELITY CARD RETURNS TO OWNER",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "WPLTO_runs": 1 if artifacts else 0,
            "producer_runs": 1, "product_link_attempts": 1 if artifacts else 0,
            "product_links": 0,
            "media_builds": 0,
            "device_contacts": 0},
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
        value = load(RECEIPT)
        require(value["status"].endswith("PRODUCT CARD GREEN")
                and value["attempt_accounting"]["cards_consumed"] == 1,
                "input-fidelity green receipt drift")
        print("v1.6 input fidelity card: CHECK PASS card=1/1")
    elif FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value["retry_authorized"] is False,
                "input-fidelity Final Red drift")
        print("v1.6 input fidelity card: CHECK FINAL RED")
    else:
        print("v1.6 input fidelity card: CHECK LOCKED/ARMED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_red(error)
            except Exception as receipt_error:
                print(f"input-fidelity Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 input fidelity card: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
