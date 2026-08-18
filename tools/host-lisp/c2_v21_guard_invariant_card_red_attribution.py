#!/usr/bin/env python3
"""Attribute the guard-invariant card Final Red without replay."""

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

import c2_v21_guard_invariant_card as CARD  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = CARD.BUILD
FINAL_RED = CARD.FINAL_RED
PRODUCER = CARD.PRODUCER_RESULT
INTERNAL = BUILD / "receipts/wplto-internal.json"
BASE_RESULT = BUILD / "receipts/wplto-base-result.json"
ABI = CARD.ABI_REPORT
KERNAL = BUILD / "wplto/kernal-freedom-link.json"
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
MAP = BUILD / "wplto/lisp65-c2-substitution-linked.prg.map"
LOCAL_WRAPPER = ROOT / "tools/host-lisp/c2_v21_local_return_identity_card.py"
PRODUCT = ROOT / "tools/host-lisp/c2_product_substitution_link.py"
DRIVER = Path(__file__).resolve()
RECEIPT = ARCH / "c2.3-v2.1-guard-invariant-card-red-attribution-receipt.json"
HISTORICAL_COMMIT = "da7dae0a"
RECORDED_ON = "2026-08-14"
STATUS = "ATTRIBUTED FINAL RED: post-link consumer requests retired control-flow field"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


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


def git_source(path: Path) -> str:
    name = path.relative_to(ROOT).as_posix()
    return subprocess.run(
        ["git", "show", f"{HISTORICAL_COMMIT}:{name}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout


def git_bind(path: Path) -> dict[str, Any]:
    raw = git_source(path).encode()
    return {"authority": "git-blob", "commit": subprocess.run(
        ["git", "rev-parse", f"{HISTORICAL_COMMIT}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip(),
        "path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest()}


def derive() -> dict[str, Any]:
    red = load(FINAL_RED)
    producer = load(PRODUCER)
    internal = load(INTERNAL)
    base = load(BASE_RESULT)
    abi = load(ABI)
    kernal = load(KERNAL)
    require(
        red.get("status") == "FINAL RED: guard-invariant card returns to owner"
        and red.get("retry_authorized") is False
        and red.get("owner_disposition_required") is True
        and red.get("attempt_accounting") == {"cards_authorized": 1,
            "cards_consumed": 1, "WPLTO_runs": 1,
            "product_link_attempts": 1, "media_builds": 0,
            "device_contacts": 0}
        and red.get("error", {}).get("message", "").rstrip().endswith(
            "2.1 guard card: FINAL RED: 'control_flow'")
        and producer.get("status") == "PASS"
        and internal.get("status") ==
            "passed-new-c2-lite-real-abi-identity-hardware-not-run"
        and base.get("WPLTO", {}).get("product_completed") is True
        and abi.get("status") == "passed-all-assembler-leaf-abi-contracts",
        "guard card Final Red evidence drift")

    transport = producer["v21_linked_transport"]
    flow = kernal["control_flow_ownership"]
    require(
        transport["reader"]["address"] == "0x2277"
        and transport["reader"]["end_exclusive"] == "0x231d"
        and transport["mapped_window"] == "0x4000..0x5fff"
        and producer["v21_linked_mutations"] == [
            "reader-inside-window", "reader-straddles-window",
            "reader-empty", "historical-world-changed"]
        and kernal.get("status") == "passed"
        and "control_flow" not in kernal
        and flow["violations"] == []
        and flow["direct_window_edges"] == 390
        and flow["same_function_basic_block_jumps"] == 181
        and abi["rtov_crc_mem_callers"]["callsite_count"] == 10
        and abi["ELF_derived_C_called_inventory"]
            ["unclassified_C_called_functions"] == [],
        "green linked product/guard evidence drift")

    wrapper_source = git_source(LOCAL_WRAPPER)
    product_source = git_source(PRODUCT)
    require(
        'ownership = kernal["control_flow"]' in wrapper_source
        and '"control_flow_ownership": control_flow' in product_source,
        "post-link schema mismatch source evidence drift")
    return {
        "format": "lisp65-c2.3-v21-guard-invariant-card-red-attribution-v1",
        "recorded_on": RECORDED_ON, "status": STATUS,
        "card_result": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "green_subresults": {
            "product_completed_by_WPLTO": True,
            "real_ABI_status": abi["status"],
            "rtov_crc_callers": 10,
            "guard": {"reader": transport["reader"],
                "mapped_window": transport["mapped_window"],
                "mutations_rejected": producer["v21_linked_mutations"]},
            "ownership_producer": {"status": kernal["status"],
                "field": "control_flow_ownership", "violations": [],
                "direct_window_edges": flow["direct_window_edges"],
                "same_function_basic_block_jumps":
                    flow["same_function_basic_block_jumps"]}},
        "root_cause": {
            "class": "POSTLINK-CONSUMER-SCHEMA-VOCABULARY-DRIFT",
            "consumer": "c2_v21_local_return_identity_card.linked_gate",
            "requested_field": "control_flow",
            "producer_field": "control_flow_ownership",
            "requested_field_present": False,
            "producer_field_present": True,
            "mechanism": (
                "The local-return post-link wrapper indexes the retired "
                "kernal-freedom field 'control_flow'. The actual candidate "
                "producer emits 'control_flow_ownership', whose violations "
                "list is empty. Python raises KeyError after the corrected "
                "reader guard and product link are green."),
            "preflight_gap": (
                "The wrapper preflight exercised typed artifact-path roles, "
                "but not the linked_gate consumer against the producer's "
                "actual kernal-freedom schema."),
            "product_failure": False, "guard_failure": False,
            "post_link_consumer_failure": True},
        "card_disposition": {"retry_authorized": False,
            "owner_disposition_required": True, "completion_allowed": False,
            "media_allowed": False, "device_allowed": False},
        "authority": {"final_red": bind(FINAL_RED), "producer": bind(PRODUCER),
            "WPLTO_internal": bind(INTERNAL), "WPLTO_base_result": bind(BASE_RESULT),
            "real_ABI": bind(ABI), "kernal_freedom": bind(KERNAL),
            "ELF": bind(ELF), "map": bind(MAP),
            "local_wrapper_at_card": git_bind(LOCAL_WRAPPER),
            "product_producer_at_card": git_bind(PRODUCT),
            "driver": bind(DRIVER)},
        "claim_limit": (
            "Read-only attribution of the consumed card. It proves a post-link "
            "schema-vocabulary failure after green WPLTO, product link, guard, "
            "ownership producer and ABI; it authorizes no repair or retry."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    root = value.get("root_cause", {})
    require(
        value.get("status") == STATUS
        and value.get("card_result") == {"cards_consumed": 1,
            "WPLTO_runs": 1, "product_links": 1, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0}
        and value.get("green_subresults", {}).get("guard", {}).get(
            "reader", {}).get("address") == "0x2277"
        and value.get("green_subresults", {}).get(
            "ownership_producer", {}).get("violations") == []
        and root.get("class") ==
            "POSTLINK-CONSUMER-SCHEMA-VOCABULARY-DRIFT"
        and root.get("requested_field") == "control_flow"
        and root.get("producer_field") == "control_flow_ownership"
        and root.get("product_failure") is False
        and root.get("guard_failure") is False
        and root.get("post_link_consumer_failure") is True
        and value.get("card_disposition", {}).get("retry_authorized") is False,
        "guard card attribution widened or weakened")
    if verify:
        require(value == derive(), "guard card attribution authority drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "hide-consumed-card": lambda x: x["card_result"].update(cards_consumed=0),
        "blame-product": lambda x: x["root_cause"].update(product_failure=True),
        "blame-guard": lambda x: x["root_cause"].update(guard_failure=True),
        "rename-requested-field": lambda x: x["root_cause"].update(
            requested_field="control_flow_ownership"),
        "rename-producer-field": lambda x: x["root_cause"].update(
            producer_field="control_flow"),
        "invent-ownership-violation": lambda x: x["green_subresults"]
            ["ownership_producer"].update(violations=["invented"]),
        "authorize-retry": lambda x: x["card_disposition"].update(
            retry_authorized=True),
        "allow-completion": lambda x: x["card_disposition"].update(
            completion_allowed=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate, verify=True)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases), "guard card attribution mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "guard card attribution receipt exists")
    value = derive(); validate(value, verify=True)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("2.1 guard card attribution: PASS guard=green product=green "
          "postlink-schema=red retry=none")


def check() -> None:
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == mutations(value), "guard card attribution mutation drift")
    print("2.1 guard card attribution: CHECK PASS field=control_flow_ownership")


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in ("record", "check"),
            "usage: c2_v21_guard_invariant_card_red_attribution.py record|check")
    {"record": record, "check": check}[sys.argv[1]]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"2.1 guard card attribution: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
