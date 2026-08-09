#!/usr/bin/env python3
"""The sole host-only product card for the v1.9 ownership recharter."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import c2_v18_full_map_repair_wplto as V18  # noqa: E402


BASE = V18.BASE
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/post-promotion/v19/full-map-recharter-wplto"
PREFLIGHT = ROOT / "build/post-promotion/v19/full-map-recharter-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
RECEIPT = EVIDENCE / "c2.3-v1.9-full-map-recharter-product-card-receipt.json"
FIRST_RED = EVIDENCE / "c2.3-v1.9-full-map-recharter-product-card-first-red.json"
VOCABULARY = EVIDENCE / "c2.3-v1.9-acceptance-vocabulary-receipt.json"
REPLAY = EVIDENCE / "c2.3-v1.9-full-map-replay-closure-receipt.json"
PLAN = ROOT / "docs/planning/1.9-full-map-recharter-work-plan.md"
DRIVER = Path(__file__).resolve()


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"regular JSON authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    return V18.bind(path)


def configure() -> None:
    V18.BUILD = BUILD
    V18.PREFLIGHT = PREFLIGHT
    V18.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT
    V18.RECEIPT = RECEIPT
    V18.FIRST_RED = FIRST_RED
    V18.DRIVER = DRIVER
    V18.configure_base()
    BASE.host_gates = host_gates
    BASE.configure()


def host_gates() -> dict[str, str]:
    gates = V18.host_gates()
    gates["v19_acceptance_vocabulary"] = V18.run(
        [sys.executable,
         "tools/host-lisp/c2_v19_acceptance_vocabulary.py", "check"],
        "v1.9 acceptance vocabulary")
    gates["v19_replay_closure"] = V18.run(
        [sys.executable,
         "tools/host-lisp/c2_v19_full_map_replay.py", "check"],
        "v1.9 full-map replay closure")
    return gates


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FIRST_RED.exists(),
            "v1.9 card/preflight is one-shot")
    vocabulary = load(VOCABULARY)
    replay = load(REPLAY)
    require(vocabulary["status"] == "PASS"
            and vocabulary["execution_witness"]["mutations"] == 378,
            "v1.9 vocabulary closure is not green")
    require(replay["status"] == "PASS"
            and replay["card_gate"]["authorized"] is True,
            "v1.9 replay closure has not authorized the sole card")
    configure()
    historical = V18.historical_seed_authority()
    PREFLIGHT.parent.mkdir(parents=True, exist_ok=True)
    fresh_ship = BASE.create_ship_witness()
    value = {
        "format": "lisp65-c2.3-v1.9-full-map-recharter-preflight-v1",
        "recorded_on": date.today().isoformat(),
        "status": "PASS",
        "card_directory_absent_before_preflight": True,
        "wplto_started": False,
        "compiler_invocations": 0,
        "device_contacts": 0,
        "vocabulary": bind(VOCABULARY),
        "replay_closure": bind(REPLAY),
        "historical_first_red_replay": historical,
        "fresh_ship": fresh_ship,
        "authority": {"plan": bind(PLAN), "driver": bind(DRIVER)},
        "next": "the sole v1.9 product-shaped WPLTO card",
    }
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("c2-v19-full-map-recharter: PREFLIGHT PASS "
          "vocabulary=378 replay=green compiles=0 wplto=0 device=0")


def record_first_red(error: BaseException) -> None:
    diagnostic: dict[str, Any] = {
        "type": type(error).__name__, "message": str(error)}
    internal = BUILD / "receipts/wplto-internal.json"
    if internal.is_file():
        candidate = load(internal).get("diagnostic")
        if isinstance(candidate, dict) \
                and {"type", "message"} <= set(candidate):
            diagnostic = candidate
    artifacts = []
    for relative in (
        "wplto/resident-island-seed.prg.lto.o",
        "wplto/resident-island-seed.prg.elf",
        "wplto/resident-island-seed.prg.map",
        "wplto/lisp65-c2-substitution-linked.prg.lto.o",
        "wplto/lisp65-c2-substitution-linked.prg.elf",
        "wplto/lisp65-c2-substitution-linked.prg.map",
        "wplto/c2-substitution.ld",
    ):
        path = BUILD / relative
        if path.is_file():
            artifacts.append(bind(path))
    value = {
        "format": "lisp65-c2.3-v1.9-full-map-recharter-first-red-v1",
        "recorded_on": date.today().isoformat(),
        "status": "FIRST RED: final park required",
        "diagnostic": diagnostic,
        "card_started": BUILD.exists(),
        "wplto_probes_consumed": int(BUILD.exists()),
        "product_links": 0,
        "device_contacts": 0,
        "retry_authorized": False,
        "final_park_required": True,
        "successful_receipt_consumption_attempted": False,
        "artifacts": artifacts,
        "authority": {
            "vocabulary": bind(VOCABULARY),
            "replay_closure": bind(REPLAY),
            "plan": bind(PLAN),
            "driver": bind(DRIVER),
        },
        "claim_limit": (
            "Every red from the sole v1.9 card is terminal. No retry, third "
            "recommission, Link 91, hardware or release claim."),
    }
    FIRST_RED.write_bytes(canonical(value))


def annotate() -> None:
    V18.annotate()
    value = load(RECEIPT)
    vocabulary = load(VOCABULARY)
    replay = load(REPLAY)
    require(value["status"] ==
            "passed-owner-reauthorized-final-full-map-WPLTO",
            "inherited full-map annotation did not close")
    value.update({
        "format": "lisp65-c2.3-v1.9-full-map-recharter-WPLTO-v1",
        "recorded_on": date.today().isoformat(),
        "status": "passed-sole-v1.9-full-map-recharter-WPLTO",
        "vocabulary_closure": {
            "status": vocabulary["status"],
            "mutations": vocabulary["execution_witness"]["mutations"],
            "output_sections": vocabulary["execution_witness"][
                "output_sections"],
            "driver_receipt_tokens": vocabulary["execution_witness"][
                "driver_receipt_tokens"],
        },
        "replay_closure": {
            "status": replay["status"],
            "product_replay_links": replay["execution_witness"][
                "product_replay_links"],
            "fresh_wplto": replay["execution_witness"]["fresh_wplto"],
        },
        "authority": {
            **value["authority"],
            "v19_vocabulary": bind(VOCABULARY),
            "v19_replay_closure": bind(REPLAY),
            "v19_preflight": bind(PREFLIGHT_RECEIPT),
            "v19_plan": bind(PLAN),
            "v19_driver": bind(DRIVER),
        },
        "next_gate": (
            "The single owner Halt decides whether this green card reopens "
            "1.5 Halt 2, the preserved parity pilot and Link 91."),
        "claim_limit": (
            "One host-only non-promotable product-shaped v1.9 ownership "
            "WPLTO; no Link 91, device, parity-surface, product promotion or "
            "release claim."),
    })
    RECEIPT.write_bytes(canonical(value))


def card() -> None:
    require(PREFLIGHT_RECEIPT.is_file()
            and load(PREFLIGHT_RECEIPT)["status"] == "PASS",
            "green v1.9 preflight required")
    require(not BUILD.exists() and not RECEIPT.exists()
            and not FIRST_RED.exists(), "v1.9 WPLTO card is one-shot")
    configure()
    result = BASE.JOINT.wplto()
    require(result == 0, f"canonical WPLTO returned {result}")
    annotate()
    value = load(RECEIPT)
    layout = value["full_map_layout"]
    print("c2-v19-full-map-recharter: PASS "
          f"ordinary=0xb61d-0xbffb margin={layout['five_byte_margin']} "
          "inventory=190 facade=98/243 far=874 stack=6/12 wplto=1 device=0")


def selftest() -> None:
    vocabulary = load(VOCABULARY)
    replay = load(REPLAY) if REPLAY.is_file() else None
    require(vocabulary["status"] == "PASS"
            and vocabulary["execution_witness"]["mutations"] == 378,
            "v1.9 vocabulary authority drift")
    if replay is not None:
        require(replay["status"] == "PASS",
                "v1.9 replay authority is red")
    require(not BUILD.exists() and not RECEIPT.exists()
            and not FIRST_RED.exists(), "v1.9 card already consumed")
    print("c2-v19-full-map-recharter: SELFTEST PASS "
          f"vocabulary=378 replay={'green' if replay else 'pending'} "
          "card=one retry=none device=0")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("selftest", "preflight", "card"))
    args = parser.parse_args()
    if args.mode == "selftest":
        selftest()
    elif args.mode == "preflight":
        preflight()
    else:
        card()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, V18.RepairCardError, BASE.CardError,
            BASE.JOINT.WPLTOError, OSError, KeyError, ValueError) as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_first_red(error)
            except Exception as receipt_error:  # never mask the primary red
                print("c2-v19-full-map-recharter: receipt failure: "
                      f"{receipt_error}", file=sys.stderr)
        print(f"c2-v19-full-map-recharter: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
