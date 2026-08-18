#!/usr/bin/env python3
"""Attribute the wrapper-contract replacement Final Red without replay."""

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

from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v2.1-wrapper-contract-replacement-card"
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
MAP = BUILD / "wplto/lisp65-c2-substitution-linked.prg.map"
PRODUCER = BUILD / "producer-result.json"
INTERNAL = BUILD / "receipts/wplto-internal.json"
ABI = BUILD / "wplto/c2-asm-leaf-real-abi-callers.json"
FINAL_RED = ARCH / "c2.3-v2.1-wrapper-contract-replacement-card-final-red.json"
PREFLIGHT = BUILD.parent / "v2.1-wrapper-contract-replacement-preflight/preflight.json"
WRAPPER_CONTRACT = ARCH / "c2.3-v2.1-postlink-wrapper-contract-receipt.json"
PRICING = ARCH / "c2.3-v2.1-call-seam-pricing-receipt.json"
CPU_CARD = ROOT / "tools/host-lisp/c2_v21_cpu_transport_card.py"
CARD = ROOT / "tools/host-lisp/c2_v21_wrapper_contract_replacement_card.py"
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
RECEIPT = ARCH / (
    "c2.3-v2.1-wrapper-contract-replacement-card-red-attribution-receipt.json")
HISTORICAL_COMMIT = "bd2bfcf4"
RECORDED_ON = "2026-08-14"
FORMAT = "lisp65-c2.3-v2.1-wrapper-contract-replacement-red-attribution-v1"
STATUS = "ATTRIBUTED FINAL RED: linked guard pins reader to wrong address domain"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


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


def git_source(commit: str, path: Path) -> str:
    name = path.relative_to(ROOT).as_posix()
    return subprocess.run(
        ["git", "show", f"{commit}:{name}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    raw = git_source(commit, path).encode()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def derive() -> dict[str, Any]:
    red = load(FINAL_RED)
    producer = load(PRODUCER)
    internal = load(INTERNAL)
    abi = load(ABI)
    preflight = load(PREFLIGHT)
    contract = load(WRAPPER_CONTRACT)
    pricing = load(PRICING)
    require(
        red.get("status") ==
            "FINAL RED: wrapper-contract replacement returns to owner"
        and red.get("retry_authorized") is False
        and red.get("owner_disposition_required") is True
        and red.get("attempt_accounting") == {
            "replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1, "WPLTO_runs": 1,
            "product_link_attempts": 1, "media_builds": 0,
            "device_contacts": 0}
        and red.get("error", {}).get("message", "").rstrip().endswith(
            "linked CPU reader can hide beneath its own block-2 MAP")
        and producer.get("status") == "PASS"
        and internal.get("status") ==
            "passed-new-c2-lite-real-abi-identity-hardware-not-run"
        and abi.get("status") == "passed-all-assembler-leaf-abi-contracts"
        and preflight.get("status") ==
            "PASS: wrapper plumbing green before replacement card"
        and contract.get("status") ==
            "HOST-GREEN: post-link wrapper contract conformance",
        "wrapper replacement Final Red evidence drift")

    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    reader = truth.symbol("c2_map_cpu_read")
    selector = truth.symbol("c2_map_cpu_selector")
    text = truth.section(".text")
    mapped_start, mapped_end = 0x4000, 0x6000
    reader_end = reader.value + reader.bytes
    outside_window = reader_end <= mapped_start or reader.value >= mapped_end
    require(
        reader.value == 0x2277 and reader.bytes == 166
        and reader_end == 0x231D and reader.section == ".text"
        and selector.value == reader_end and selector.bytes == 40
        and text.address <= reader.value and reader_end <= text.address + text.bytes
        and outside_window
        and pricing["pricing"]["linked_capacity"]["reader_address"] == "0x2277"
        and pricing["pricing"]["linked_capacity"]["reader_bytes"] == 166
        and pricing["pricing"]["candidate_3_reader_in_far_service"]
            ["reader_target_window"] == "CPU block 2 ($4000..$5fff)",
        "linked reader placement/pricing attribution drift")

    source = git_source(HISTORICAL_COMMIT, CPU_CARD)
    require(
        "not (0x4000 <= reader.value < 0x6000)" in source
        and "reader.value >= 0x8000" in source
        and '"mapped_window": "0x4000..0x5fff"' in source,
        "historical linked-guard predicate drift")
    return {
        "format": FORMAT, "recorded_on": RECORDED_ON, "status": STATUS,
        "card_result": {"replacement_cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "green_subresults": {
            "wrapper_contract": {"wrappers_executed": 3,
                "producer_roles": 9, "uppercase_role_references": 0},
            "producer": producer["status"], "WPLTO": internal["status"],
            "real_ABI": abi["status"],
            "rtov_crc_callers": abi["rtov_crc_mem_callers"]["callsite_count"]},
        "root_cause": {
            "class": "LINKED-GUARD-PINS-READER-TO-WRONG-ADDRESS-DOMAIN",
            "reader": {"address": "0x2277", "end_exclusive": "0x231d",
                "bytes": reader.bytes, "section": reader.section},
            "mapped_window": {"start": "0x4000", "end_exclusive": "0x6000",
                "reader_overlaps": not outside_window},
            "priced_placement": {"reader_address": "0x2277",
                "reader_bytes": 166, "known_before_card": True},
            "accepted_safety_fact": "reader executes outside the mapped block",
            "invalid_extra_predicate": "reader.value >= 0x8000",
            "mechanism": (
                "The linked guard combines the real non-overlap property with "
                "an unrelated high-memory floor. The commissioned placement has "
                "always put the reader at 0x2277, below and disjoint from the "
                "0x4000..0x5fff mapped block; the extra floor rejects that priced "
                "placement after a successful product link."),
            "product_failure": False, "wrapper_vocabulary_failure": False,
            "post_link_guard_failure": True},
        "card_disposition": {"retry_authorized": False,
            "owner_disposition_required": True, "completion_allowed": False,
            "media_allowed": False, "device_allowed": False},
        "authority": {"final_red": bind(FINAL_RED), "producer": bind(PRODUCER),
            "WPLTO_internal": bind(INTERNAL), "real_ABI": bind(ABI),
            "ELF": bind(ELF), "map": bind(MAP), "pricing": bind(PRICING),
            "wrapper_contract": bind(WRAPPER_CONTRACT),
            "CPU_wrapper_at_card": git_bind(HISTORICAL_COMMIT, CPU_CARD),
            "card_driver_at_card": git_bind(HISTORICAL_COMMIT, CARD),
            "driver": bind(DRIVER)},
        "claim_limit": (
            "Read-only attribution of the consumed replacement card. It proves "
            "a post-link guard-domain error after green WPLTO/ABI work; it "
            "authorizes no repair, retry, completion, media or device contact."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    root = value.get("root_cause", {})
    require(
        value.get("status") == STATUS
        and value.get("card_result") == {
            "replacement_cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0}
        and value.get("green_subresults", {}).get("wrapper_contract") == {
            "wrappers_executed": 3, "producer_roles": 9,
            "uppercase_role_references": 0}
        and root.get("class") ==
            "LINKED-GUARD-PINS-READER-TO-WRONG-ADDRESS-DOMAIN"
        and root.get("reader", {}).get("address") == "0x2277"
        and root.get("mapped_window", {}).get("reader_overlaps") is False
        and root.get("priced_placement", {}).get("known_before_card") is True
        and root.get("invalid_extra_predicate") == "reader.value >= 0x8000"
        and root.get("product_failure") is False
        and root.get("post_link_guard_failure") is True
        and value.get("card_disposition", {}).get("retry_authorized") is False,
        "wrapper replacement attribution widened or weakened")
    if verify:
        require(value == derive(), "wrapper replacement attribution authority drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "hide-card": lambda x: x["card_result"].update(
            replacement_cards_consumed=0),
        "blame-product": lambda x: x["root_cause"].update(product_failure=True),
        "claim-overlap": lambda x: x["root_cause"]["mapped_window"].update(
            reader_overlaps=True),
        "erase-priced-placement": lambda x: x["root_cause"]
            ["priced_placement"].update(known_before_card=False),
        "accept-high-floor": lambda x: x["root_cause"].update(
            invalid_extra_predicate=None),
        "erase-wrapper-green": lambda x: x["green_subresults"]
            ["wrapper_contract"].update(wrappers_executed=2),
        "authorize-retry": lambda x: x["card_disposition"].update(
            retry_authorized=True),
        "allow-media": lambda x: x["card_disposition"].update(media_allowed=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate, verify=True)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases), "wrapper replacement attribution mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "wrapper replacement attribution receipt exists")
    value = derive(); validate(value, verify=True)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("2.1 wrapper replacement attribution: PASS product=green "
          "reader=2277 window=4000..5fff guard=red retry=none")


def check() -> None:
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == mutations(value), "attribution mutation receipt drift")
    print("2.1 wrapper replacement attribution: CHECK PASS guard-domain=wrong")


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in ("record", "check"),
            "usage: c2_v21_wrapper_contract_replacement_red_attribution.py record|check")
    {"record": record, "check": check}[sys.argv[1]]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"2.1 wrapper replacement attribution: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
