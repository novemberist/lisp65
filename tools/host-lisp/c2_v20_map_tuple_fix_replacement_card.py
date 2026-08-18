#!/usr/bin/env python3
"""Run the one owner-authorized replacement card for the corrected MAP tuple."""

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

import c2_v20_map_tuple_fix_card as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
BUILD = ROOT / "build/c2.3/v2.0-map-tuple-fix-replacement-card"
PREFLIGHT = ROOT / "build/c2.3/v2.0-map-tuple-fix-replacement-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
RECEIPT = EVIDENCE / "c2.3-v2.0-map-tuple-fix-replacement-card-receipt.json"
FINAL_RED = EVIDENCE / (
    "c2.3-v2.0-map-tuple-fix-replacement-card-final-red.json")
HISTORICAL_RED = BASE.FINAL_RED
AUTHORIZATION_COMMIT = "7b7dcc11"
RECORDED_ON = "2026-08-13"
LINK = 101
DRIVER = Path(__file__).resolve()


class ReplacementCardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplacementCardError(message)


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


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    text = " ".join(raw.decode().split()).lower()
    require(
        "replacement card authorized" in text
        and "one name, one owner, one body" in text
        and "one replacement card" in text,
        "replacement-card owner authorization text drift")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def owner_authorization() -> dict[str, Any]:
    return git_bind(AUTHORIZATION_COMMIT, PLAN)


def historical_red() -> dict[str, Any]:
    value = load(HISTORICAL_RED)
    require(
        value.get("status")
            == "FINAL RED: corrected-tuple card returns to owner"
        and value.get("root_cause", {}).get("class")
            == "GLOBAL-ASM-INVENTORY-DUPLICATE-SUCCESSOR"
        and value.get("attempt_accounting", {}).get("cards_consumed") == 1
        and value.get("post_red_closure", {}).get("retry_authorized") is False,
        "historical corrected-tuple Final Red drift")
    return value


def single_implementation_gate() -> dict[str, Any]:
    historical_red()
    scope = BASE.source_scope_gate()
    inventory = BASE.real_asm_inventory_gate()
    scopes = scope["selected"]["scopes"]
    selected = [row for row in scopes if row["selected"] is True]
    require(
        len(selected) == 1 and selected[0]["selected"] is True
        and selected[0]["sources"].count(
            "src/optional/c2_mapped_far_service_v2.s") == 1
        and "src/c2_mapped_far_service.s" not in selected[0]["sources"]
        and inventory["duplicate-successor-in-global-asm-domain"] == "rejected",
        "one-name/one-owner/one-body inventory closure drift")
    return {
        "status": "PASS: one name, one owner, one body per inventory",
        "selected_owner": selected[0]["name"],
        "selected_successor_copies": 1,
        "historical_body_selected": False,
        "real_global_inventory": inventory,
        "relapse_mutation": "duplicate successor in global src/*.s domain rejected",
    }


def single_implementation_mutations() -> list[str]:
    """Reject zero/multiple owners without pinning total registry size."""
    scopes = BASE.source_scope_gate()["selected"]["scopes"]

    def validate(rows: list[dict[str, Any]]) -> None:
        selected = [row for row in rows if row["selected"] is True]
        require(
            len(selected) == 1
            and selected[0]["sources"].count(
                "src/optional/c2_mapped_far_service_v2.s") == 1
            and "src/c2_mapped_far_service.s" not in selected[0]["sources"],
            "identity-selected implementation owner drift",
        )

    cases = {
        "select-unrelated-scope": lambda rows: rows[1].update(selected=True),
        "drop-selected-owner": lambda rows: rows[0].update(selected=False),
        "duplicate-selected-body": lambda rows: rows[0]["sources"].append(
            "src/optional/c2_mapped_far_service_v2.s"),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(scopes); mutate(candidate)
        try:
            validate(candidate)
        except ReplacementCardError:
            rejected.append(name)
    require(rejected == list(cases),
            "identity-selected implementation mutation survived")
    return rejected


def preflight_value() -> dict[str, Any]:
    fix = BASE.fix_authority()
    return {
        "format": "lisp65-c2.3-v20-map-tuple-fix-replacement-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: one corrected-tuple replacement card armed",
        "attempt_accounting": {"replacement_cards_consumed": 0,
            "wplto_runs": 0, "product_links": 0, "device_contacts": 0},
        "configuration": {"link": LINK, "tuple": {"A": "0x40", "X": "0x82"},
            "corrected_trampoline": BASE.FIX.SOURCE.relative_to(ROOT).as_posix(),
            "full_map_ownership": True, "low_resident_LMA_reset": True},
        "host_gates": {"MAP_decode_mutations": len(fix["mutations_rejected"]),
                       "single_implementation": single_implementation_gate()},
        "authority": {"owner_authorization": owner_authorization(),
            "historical_final_red": bind(HISTORICAL_RED),
            "fix_receipt": bind(BASE.FIX.RECEIPT),
            "VMA_golden": bind(BASE.INV.GOLDEN), "driver": bind(DRIVER)},
        "claim_limit": (
            "One host-only replacement card. Media, device, D1, D2-D5 and "
            "release remain unclaimed until a green terminal receipt."),
    }


def validate_preflight(value: dict[str, Any]) -> None:
    expected = preflight_value()
    require(value == expected, "replacement-card preflight drift")


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "replacement preflight/card is one-shot")
    value = preflight_value()
    validate_preflight(value)
    PREFLIGHT.mkdir(parents=True)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("2.0 MAP-tuple replacement: PREFLIGHT PASS decode=14 "
          "implementation=one card=0")


def produce_candidate() -> dict[str, Any]:
    BASE.configure_fix_source()
    BASE.PRODUCER.LINK = LINK
    BASE.PRODUCER.BUILD = BUILD
    BASE.PRODUCER.FINAL_RED = BUILD / "producer-internal-first-red.json"
    BASE.PRODUCT.configure_full_map_ownership()
    BASE.PRODUCT.configure_low_resident_lma_reset()
    return BASE.PRODUCER.produce_candidate()


def card() -> None:
    validate_preflight(load(PREFLIGHT_RECEIPT))
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "replacement product card is one-shot")
    INVOCATION.write_bytes(canonical({
        "format": "lisp65-c2.3-v20-map-tuple-replacement-invocation-v1",
        "recorded_on": RECORDED_ON, "status": "INVOKED",
        "owner_authorization": owner_authorization(),
        "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)}))
    artifacts = produce_candidate()
    comparison = BASE.INV.compare_elf(artifacts["elf"])
    linker = BASE.PRODUCT.low_resident_lma_reset_gate(
        artifacts["linker"].read_text(encoding="utf-8"))
    BASE.CRC.BUILD = BUILD
    delivery = BASE.CRC.delivered_bytes_gate(artifacts["elf"], artifacts["prg"])
    BASE.CRC.validate_delivery(delivery, artifacts["elf"], artifacts["prg"])
    delivery_rejected = BASE.CRC.delivery_mutations(
        delivery, artifacts["elf"], artifacts["prg"])
    tuple_gate = BASE.linked_tuple_gate(artifacts["elf"])
    tuple_rejected = BASE.linked_mutations(tuple_gate, artifacts["elf"])
    headroom = {row["id"]: row["candidate_headroom_bytes"]
                for row in comparison["capacity_measurements"]}
    value = {
        "format": "lisp65-c2.3-v20-map-tuple-fix-replacement-card-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: corrected MAP tuple replacement card green",
        "attempt_accounting": {"replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1, "wplto_runs": 1,
            "product_link_attempts": 1, "device_contacts": 0},
        "acceptance": {"VMA_golden": comparison,
            "low_resident_linker_reset": linker, "delivered_bytes": delivery,
            "delivery_mutations_rejected": delivery_rejected,
            "linked_MAP_tuple": tuple_gate,
            "linked_MAP_mutations_rejected": tuple_rejected,
            "single_implementation": single_implementation_gate()},
        "artifacts": {key: bind(artifacts[key])
                      for key in ("elf", "prg", "map", "lto", "linker")},
        "producer": {"mechanical_completion_only": True,
            "historical_return_nonauthoritative": artifacts["producer_return"],
            "log": bind(artifacts["producer_log"]),
            "resolved_profile": bind(artifacts["resolved_profile"])},
        "authority": {"owner_authorization": owner_authorization(),
            "historical_final_red": bind(HISTORICAL_RED),
            "fix_receipt": bind(BASE.FIX.RECEIPT),
            "preflight": bind(PREFLIGHT_RECEIPT),
            "invocation": bind(INVOCATION), "driver": bind(DRIVER),
            "VMA_golden": bind(BASE.INV.GOLDEN)},
        "narrow_margins_are_not_budgets": {
            "ordinary_chain": headroom["low-resident-and-ordinary-chain"],
            "runtime_overlay": headroom["runtime-overlay-slices"],
            "bank0_state": headroom["owned-bank0-state"]},
        "next_gate": "regenerate current-world media, then fresh D1",
        "claim_limit": (
            "One green host-only replacement card. Media and device have not "
            "run; D2-D5 remain behind green D1 liveness."),
    }
    RECEIPT.write_bytes(canonical(value))
    print("2.0 MAP-tuple replacement: PASS A=40 X=82 block=3 "
          f"sections={comparison['allocatable_sections']} wplto=1 device=0")


def record_final_red(error: BaseException) -> None:
    if RECEIPT.exists() or FINAL_RED.exists() or not INVOCATION.exists():
        return
    artifacts = {}
    for name, relative in {
        "elf": "wplto/lisp65-c2-substitution-linked.prg.elf",
        "prg": "wplto/lisp65-c2-substitution-linked.prg",
        "map": "wplto/lisp65-c2-substitution-linked.prg.map",
        "producer_log": "receipts/v20-producer.log"}.items():
        path = BUILD / relative
        if path.is_file():
            artifacts[name] = bind(path)
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v20-map-tuple-replacement-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: replacement card returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {"replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1,
            "wplto_runs": int((BUILD / "receipts/wplto-base-result.json").is_file()),
            "product_artifacts_emitted": any(
                name in artifacts for name in ("elf", "prg", "map")),
            "device_contacts": 0},
        "retry_authorized": False, "owner_disposition_required": True,
        "artifacts": artifacts,
        "authority": {"owner_authorization": owner_authorization(),
            "historical_final_red": bind(HISTORICAL_RED),
            "preflight": bind(PREFLIGHT_RECEIPT),
            "invocation": bind(INVOCATION), "driver": bind(DRIVER)},
        "claim_limit": "The sole replacement card is consumed; no media or device.",
    }))


def selftest() -> None:
    owner_authorization(); historical_red(); BASE.fix_authority()
    gate = single_implementation_gate()
    require(gate["selected_successor_copies"] == 1
            and gate["historical_body_selected"] is False,
            "single-implementation gate drift")
    rejected = single_implementation_mutations()
    print("2.0 MAP-tuple replacement: SELFTEST PASS authority=7b7dcc11 "
          f"implementation=one mutations={len(rejected)}")


def check() -> None:
    selftest()
    require(not (RECEIPT.exists() and FINAL_RED.exists()),
            "replacement card has two terminal outcomes")
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value["retry_authorized"] is False
                and value["owner_disposition_required"] is True,
                "replacement Final Red drift")
        elf = ROOT / value["artifacts"]["elf"]["path"]
        comparison = BASE.INV.compare_elf(elf)
        tuple_gate = BASE.linked_tuple_gate(elf)
        require(
            value["error"] == {
                "type": "RuntimeError",
                "message": "source-owner scope mutation survived: "
                           "companion-define-without-trigger"}
            and value["root_cause"] == {
                "class": "IN-PROCESS-OWNER-SCOPE-SELFTEST-CONTAMINATION",
                "phase": "post-acceptance receipt assembly",
                "fresh_process_gate": "green",
                "producer_configured_process_gate": (
                    "source-owner scope mutation survived: "
                    "companion-define-without-trigger")}
            and value["read_only_post_red"]["VMA_golden"] == {
                "allocatable_sections": comparison["allocatable_sections"],
                "fixed_boundary_symbols": comparison["fixed_boundary_symbols"],
                "comparison": comparison["comparison"],
                "margins": {"ordinary_chain": 5,
                            "runtime_overlay": 6, "bank0_state": 7}}
            and value["read_only_post_red"]["linked_MAP_tuple"] == tuple_gate
            and value["read_only_post_red"]["delivery_gate_control_flow"]
                == "returned before terminal post-acceptance selftest"
            and value["read_only_post_red"]["independent_delivery_replay"]
                == "not claimed"
            and value["historical_producer_diagnostic"]["promotable"] is False,
            "replacement Final Red mechanism/read-only attribution drift")
        print("2.0 MAP-tuple replacement: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        print("2.0 MAP-tuple replacement: CHECK ARMED card=unused")
        return
    value = load(RECEIPT)
    elf = ROOT / value["artifacts"]["elf"]["path"]
    require(
        value["status"] == "PASS: corrected MAP tuple replacement card green"
        and value["attempt_accounting"]["replacement_cards_consumed"] == 1
        and value["acceptance"]["linked_MAP_tuple"] == BASE.linked_tuple_gate(elf)
        and value["acceptance"]["single_implementation"]
            == single_implementation_gate(),
        "green replacement-card receipt drift")
    print("2.0 MAP-tuple replacement: CHECK PASS A40/X82 card=consumed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("selftest", "preflight", "card", "check"))
    selected = parser.parse_args().action
    {"selftest": selftest, "preflight": preflight,
     "card": card, "check": check}[selected]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_final_red(error)
            except Exception as receipt_error:
                print(f"2.0 MAP-tuple replacement receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"2.0 MAP-tuple replacement: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
