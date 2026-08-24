#!/usr/bin/env python3
"""Run the final delegated v1.6 input-fidelity replacement card."""

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

import c2_product_substitution_link as PRODUCT_LINK  # noqa: E402
import c2_v160_comfort_input_fidelity as GATE  # noqa: E402
import c2_v160_comfort_input_fidelity_second_replacement_card as SECOND  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v1.6-comfort-input-fidelity-third-replacement-card"
PREFLIGHT = ROOT / (
    "build/c2.3/v1.6-comfort-input-fidelity-third-replacement-card-preflight")
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
    "c2.3-v1.6-comfort-input-fidelity-third-replacement-card-receipt.json")
FINAL_RED = ARCH / (
    "c2.3-v1.6-comfort-input-fidelity-third-replacement-card-final-red.json")
PREDECESSOR_RED = ARCH / (
    "c2.3-v1.6-comfort-input-fidelity-second-replacement-card-final-red.json")
DRIVER = Path(__file__).resolve()
FORMAT = "lisp65-c2-v160-comfort-input-fidelity-third-replacement-card-v1"
PARKING_CONSEQUENCE = (
    "Any Red parks the complete v1.6 input-fidelity placement seam; no further "
    "card, retry, WPLTO, link, media, or device action is delegated.")


class ThirdReplacementError(RuntimeError): pass
class DryConsumerReached(RuntimeError): pass


def require(value: bool, message: str) -> None:
    if not value: raise ThirdReplacementError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]: return SECOND.bind(path)


def predecessor() -> dict[str, Any]:
    red = load(PREDECESSOR_RED)
    require(red.get("status") ==
                "FINAL RED: SECOND INPUT-FIDELITY REPLACEMENT TO OWNER"
            and red["attempt_accounting"]["second_replacement_cards_consumed"] == 1
            and red["attempt_accounting"]["WPLTO_runs"] == 0
            and red["attempt_accounting"]["product_links"] == 0
            and red.get("retry_authorized") is False,
            "second replacement Final Red drift")
    return red


def roots(build: Path = BUILD, preflight: Path = PREFLIGHT) -> dict[str, str]:
    return {"build": build.relative_to(ROOT).as_posix(),
            "preflight": preflight.relative_to(ROOT).as_posix(),
            "projected_ownership": (preflight /
                "projected-ownership-contract.json").relative_to(ROOT).as_posix(),
            "projected_full_map": (preflight /
                "projected-full-map-authority.json").relative_to(ROOT).as_posix()}


def set_outer_freight(build: Path, preflight: Path) -> None:
    SECOND.BUILD = build; SECOND.PREFLIGHT = preflight
    SECOND.PREFLIGHT_RECEIPT = preflight / "preflight.json"
    SECOND.INVOCATION = preflight / "card-invocation.json"
    SECOND.PROJECTED_OWNERSHIP = preflight / "projected-ownership-contract.json"
    SECOND.PROJECTED_FULL_MAP = preflight / "projected-full-map-authority.json"
    SECOND.PRODUCER_RESULT = build / "producer-result.json"
    SECOND.SCOPE_RESULT = build / "owner-scope-result.json"
    SECOND.ACCEPTANCE_RESULT = build / "artifact-acceptance.json"
    SECOND.ABI_REPORT = build / "wplto/c2-asm-leaf-abi.json"
    SECOND.PRODUCT_ELF = build / "wplto/lisp65-c2-substitution-linked.prg.elf"
    SECOND.PRODUCT_PRG = build / "wplto/lisp65-c2-substitution-linked.prg"
    SECOND.HOST_RECEIPT = build / "input-fidelity-host-card.json"
    SECOND.RECEIPT = build / "unused-second-replacement-receipt.json"
    SECOND.FINAL_RED = build / "unused-second-replacement-final-red.json"
    SECOND.DRIVER = DRIVER


def install_outer_freight(build: Path = BUILD,
                          preflight: Path = PREFLIGHT) -> None:
    """Install source hooks once; this does not select product geometry."""
    set_outer_freight(build, preflight)
    SECOND.configure()


def bind_paths_only(build: Path = BUILD,
                    preflight: Path = PREFLIGHT) -> dict[str, str]:
    """Bind output ownership without invoking configure() or install()."""
    top = SECOND.FIRST.BASE.PRODUCT
    top.BUILD = build; top.PREFLIGHT = preflight
    top.PREFLIGHT_RECEIPT = preflight / "preflight.json"
    top.SEMANTIC_RECEIPT = preflight / "semantic-repl-compile.json"
    top.INVOCATION = preflight / "card-invocation.json"
    top.PROJECTED_OWNERSHIP = preflight / "projected-ownership-contract.json"
    top.PROJECTED_FULL_MAP = preflight / "projected-full-map-authority.json"
    top.PRODUCER_RESULT = build / "producer-result.json"
    top.SCOPE_RESULT = build / "owner-scope-result.json"
    top.ACCEPTANCE_RESULT = build / "artifact-acceptance.json"
    top.ABI_REPORT = build / "wplto/c2-asm-leaf-abi.json"
    top.RECEIPT = build / "unused-path-only-receipt.json"
    top.FINAL_RED = build / "unused-path-only-final-red.json"
    top.DRIVER = DRIVER; top.LINK = 117
    top.set_paths()
    current = GATE.output_root_snapshot()
    require(current == roots(build, preflight),
            "path-only output ownership did not reach root producer")
    return current


def ordered_gate(elf: Path | None = None) -> dict[str, Any]:
    return GATE.derive(elf, output_rebind=bind_paths_only,
                       expected_output_roots=roots())


def write_projections() -> None:
    SECOND.FIRST.BASE.PRODUCT.BASE.PRODUCT.BASE.write_projections()


def producer_dry_child() -> None:
    dry_build = PREFLIGHT / "real-producer-dry-build"
    dry_preflight = PREFLIGHT / "real-producer-dry-preflight"
    install_outer_freight(dry_build, dry_preflight)
    static = GATE.install_candidate_static_plane_only(
        dry_build / "static-plane/narrow-static")
    bind_paths_only(dry_build, dry_preflight)
    write_projections()
    require(static["semantic_configurators_run"] == 0,
            "candidate path binding configured semantics")

    reached = False

    def stop_at_real_link(*_args: Any, **_kwargs: Any) -> None:
        nonlocal reached
        reached = True
        raise DryConsumerReached("real single_link consumer reached")

    PRODUCT_LINK.single_link = stop_at_real_link
    try:
        SECOND.FIRST.BASE.PRODUCT.BASE.produce_child()
    except DryConsumerReached:
        print("third replacement: REAL PRODUCER PREFLIGHT PASS "
              "single-link-reached WPLTO=0 link=0")
        return
    except Exception as error:
        # The historical ownership producer catches link-boundary exceptions
        # inside its WPLTO driver, records the traceback, and subsequently
        # reports absent final artifacts.  Accept only our exact sentinel in
        # that log, with no ELF/PRG present; any other exception remains red.
        dry_elf = dry_build / "wplto/lisp65-c2-substitution-linked.prg.elf"
        dry_prg = dry_build / "wplto/lisp65-c2-substitution-linked.prg"
        if (str(error) == "producer did not emit the linked candidate artifacts"
                and reached
                and not dry_elf.exists() and not dry_prg.exists()):
            print("third replacement: REAL PRODUCER PREFLIGHT PASS "
                  "single-link-sentinel-recorded WPLTO=0 link=0")
            return
        raise
    raise ThirdReplacementError("real producer dry-run missed single_link")


def run_dry() -> str:
    completed = subprocess.run([sys.executable, str(DRIVER), "_dry"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(completed.returncode == 0 and
            "REAL PRODUCER PREFLIGHT PASS" in completed.stdout,
            f"real producer lifecycle preflight red:\n{completed.stdout}")
    return " ".join(completed.stdout.split())


def preflight() -> None:
    predecessor()
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "third replacement is one-shot")
    value = ordered_gate()
    PREFLIGHT.mkdir(parents=True)
    dry = run_dry()
    value["real_producer_lifecycle"] = {"status": "passed-to-single-link",
        "WPLTO_runs": 0, "product_links": 0, "witness": dry}
    value["red_consequence"] = PARKING_CONSEQUENCE
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    consumer = value["static_plane_consumer"]
    require(consumer["path_rebind"]["semantic_state_unchanged"]
            and value["require_resolver_one_shot"]["second_call_rejected"]
            and consumer["consumer_observed_bytes"] == 46043
            and value["real_producer_lifecycle"]["status"] ==
                "passed-to-single-link",
            "third replacement preflight drift")
    print("v1.6 input fidelity third replacement: PREFLIGHT PASS card=0/1 "
          "path-only one-shot real-producer=single_link")


def produce_child() -> None:
    install_outer_freight()
    static = GATE.install_candidate_static_plane_only(
        BUILD / "static-plane/narrow-static")
    bind_paths_only()
    write_projections()
    require(static["semantic_configurators_run"] == 0,
            "card candidate binding performed semantic configuration")
    raise SystemExit(SECOND.FIRST.BASE.PRODUCT.BASE.produce_child())


def run_child() -> str:
    completed = subprocess.run([sys.executable, str(DRIVER), "_produce"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(completed.returncode == 0,
            f"third replacement child red:\n{completed.stdout}")
    return completed.stdout


def card() -> None:
    predecessor()
    require(PREFLIGHT_RECEIPT.is_file() and not BUILD.exists()
            and not INVOCATION.exists() and not RECEIPT.exists()
            and not FINAL_RED.exists(), "third replacement lifecycle drift")
    persisted = load(PREFLIGHT_RECEIPT)
    require(persisted["red_consequence"] == PARKING_CONSEQUENCE,
            "parking consequence absent before card")
    GATE.validate(persisted, final=False)
    INVOCATION.write_bytes(canonical({"status": "INVOKED",
        "third_replacement_card": "1/1", "WPLTO_runs": 1,
        "product_links": 1, "red_consequence": PARKING_CONSEQUENCE,
        "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER),
        "media_builds": 0, "device_contacts": 0}))
    output = run_child()
    require(PRODUCT_ELF.is_file() and PRODUCT_PRG.is_file(),
            "third replacement returned without linked product")
    host = ordered_gate(PRODUCT_ELF)
    HOST_RECEIPT.write_bytes(canonical(host))
    value = {"format": FORMAT, "recorded_on": "2026-08-18",
        "status": "PASS: V1.6 INPUT-FIDELITY THIRD REPLACEMENT GREEN",
        "attempt_accounting": {"third_replacement_cards_authorized": 1,
            "third_replacement_cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "authority": {"predecessor_Final_Red": bind(PREDECESSOR_RED),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "artifacts": {"PRG": bind(PRODUCT_PRG), "ELF": bind(PRODUCT_ELF)},
        "host_acceptance": bind(HOST_RECEIPT),
        "configuration_order": host["static_plane_consumer"],
        "placement": host["placement"], "loss": host["loss"],
        "stdout_tail": " ".join(output.split()[-24:]),
        "next": "independent review; media/device contacts remain closed",
        "claim_limit": "One final delegated card; no Completion/media/device."}
    RECEIPT.write_bytes(canonical(value))
    print("v1.6 input fidelity third replacement: CARD PASS card=1/1")


def record_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists(): return
    artifacts = {name: bind(path) for name, path in
        (("PRG", PRODUCT_PRG), ("ELF", PRODUCT_ELF))
        if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({"format":
        "lisp65-c2-v160-input-fidelity-third-replacement-red-v1",
        "recorded_on": "2026-08-18",
        "status": "FINAL RED: INPUT-FIDELITY PLACEMENT SEAM PARKED",
        "error": {"type": type(error).__name__, "message": str(error)},
        "red_consequence": PARKING_CONSEQUENCE,
        "attempt_accounting": {"third_replacement_cards_authorized": 1,
            "third_replacement_cards_consumed": 1,
            "WPLTO_runs": 1 if artifacts else 0, "product_links": 0,
            "media_builds": 0, "device_contacts": 0},
        "artifacts": artifacts, "retry_authorized": False,
        "placement_seam_parked": True, "owner_disposition_required": True,
        "authority": {"preflight": bind(PREFLIGHT_RECEIPT),
                      "driver": bind(DRIVER)}}))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "card", "check",
                                           "_dry", "_produce"))
    action = parser.parse_args().action
    if action == "preflight": preflight()
    elif action == "card": card()
    elif action == "_dry": producer_dry_child()
    elif action == "_produce": produce_child()
    elif RECEIPT.exists(): print("third replacement: CHECK PASS")
    elif FINAL_RED.exists(): print("third replacement: CHECK PARKED")
    else: print("third replacement: CHECK LOCKED/ARMED")
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: record_red(error)
            except Exception as receipt_error:
                print(f"third replacement receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 input fidelity third replacement: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
