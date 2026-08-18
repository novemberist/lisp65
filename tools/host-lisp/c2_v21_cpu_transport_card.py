#!/usr/bin/env python3
"""Run the one commissioned Link-107 CPU-transport product card."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v150_candidate_product as V150  # noqa: E402
import c2_v20_phase02b_header_consumption_replacement_card as BASE  # noqa: E402
import c2_v21_cpu_transport_preflight as PRE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v2.1-cpu-transport-card"
PREFLIGHT = ROOT / "build/c2.3/v2.1-cpu-transport-card-preflight"
INVOCATION = PREFLIGHT / "card-invocation.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
RECEIPT = ARCH / "c2.3-v2.1-cpu-transport-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v2.1-cpu-transport-card-final-red.json"
CONTRACT = PRE.CONTRACT
DRIVER = Path(__file__).resolve()
LINK = 107
RECORDED_ON = "2026-08-14"
FORMAT = "lisp65-c2.3-v2.1-cpu-transport-card-v1"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
MAP_WINDOW_START = 0x4000
MAP_WINDOW_END = 0x6000


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


def reader_span_is_disjoint(
        address: int, size: int,
        window_start: int = MAP_WINDOW_START,
        window_end: int = MAP_WINDOW_END) -> bool:
    """Assert the actual self-occlusion invariant for the mapped reader."""
    require(0 <= address < 0x10000 and size > 0
            and address + size <= 0x10000,
            "linked CPU reader span is invalid")
    require(0 <= window_start < window_end <= 0x10000,
            "decoded MAP window is invalid")
    return address + size <= window_start or address >= window_end


def configure() -> None:
    BASE.BUILD = BUILD
    BASE.PREFLIGHT = PREFLIGHT
    BASE.PREFLIGHT_RECEIPT = PRE.RECEIPT
    BASE.INVOCATION = INVOCATION
    BASE.PRODUCER_RESULT = PRODUCER_RESULT
    BASE.SCOPE_RESULT = SCOPE_RESULT
    BASE.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    # The nested predecessor receipt is deliberately build-local and never
    # becomes the 2.1 authority.  This wrapper owns the final receipt/red.
    BASE.RECEIPT = BUILD / "unused-link106-wrapper-receipt.json"
    BASE.FINAL_RED = BUILD / "unused-link106-wrapper-final-red.json"
    BASE.LINK = LINK
    V150.CONTRACT = CONTRACT
    BASE.configure_card()


def artifact_paths() -> dict[str, Path]:
    configure()
    return BASE.CARD.artifact_paths()


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    result = {name: bind(path) for name, path in artifact_paths().items()}
    result["seed_lto"] = bind(BUILD / "wplto/resident-island-seed.prg.lto.o")
    return result


def validate_preflight() -> dict[str, Any]:
    value = load(PRE.RECEIPT)
    require(
        value.get("status") == "HOST-GREEN; ONE-PRODUCT-CARD-NOT-YET-RUN"
        and value["execution_accounting"] == {
            "WPLTO_runs": 0, "product_links": 0, "device_contacts": 0}
        and value["workload"]["logical_reads_rerouted"] == 346298
        and value["hardware"]["probe_status"] == "0xa5/0xa5"
        and value["authority"]["contract"] == bind(CONTRACT),
        "2.1 preflight authority drift")
    return value


def linked_transport_gate(elf: Path, map_path: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    reader = truth.symbol("c2_map_cpu_read")
    shelf = truth.symbol("c2_stream_shelf_read")
    c2d = truth.symbol("c2_stream_c2d_read")
    require(reader.bytes > 0 and reader.section == ".text",
            "linked CPU reader is absent from ordinary executable text")
    require(reader_span_is_disjoint(reader.value, reader.bytes),
            "linked CPU reader can hide beneath its own block-2 MAP")
    require(shelf.bytes > 0 and c2d.bytes > 0,
            "linked library read seam absent")
    linked_map = map_path.read_text(encoding="utf-8")
    require(linked_map.count("c2_map_cpu_read") >= 1,
            "link map omits selected CPU source owner")
    contract = load(CONTRACT)
    require(PRE.FEATURE in contract["build"]["activation_defines"],
            "Link-107 release contract omitted CPU feature")
    section = truth.section(reader.section)
    return {
        "status": "PASS: linked reader executes outside its mapped window",
        "reader": {"address": f"0x{reader.value:04x}",
                   "end_exclusive": f"0x{reader.value + reader.bytes:04x}",
                   "bytes": reader.bytes, "section": reader.section,
                   "section_end": f"0x{section.address + section.bytes:04x}"},
        "call_seams": {
            "shelf": f"0x{shelf.value:04x}", "c2d": f"0x{c2d.value:04x}"},
        "mapped_window": "0x4000..0x5fff", "historical_worlds_changed": 0,
    }


def linked_mutations(value: dict[str, Any]) -> list[str]:
    cases = {
        "reader-inside-window": ("address", "0x5000"),
        "reader-straddles-window": ("address", "0x3ff0"),
        "reader-empty": ("bytes", 0),
        "historical-world-changed": ("historical_worlds_changed", 1),
    }
    rejected: list[str] = []
    for name, (field, replacement) in cases.items():
        candidate = deepcopy(value)
        if field in candidate["reader"]:
            candidate["reader"][field] = replacement
        else:
            candidate[field] = replacement
        try:
            address = int(candidate["reader"]["address"], 16)
            require(reader_span_is_disjoint(address, candidate["reader"]["bytes"])
                    and candidate["historical_worlds_changed"] == 0,
                    "linked CPU transport mutation")
        except CardError:
            rejected.append(name)
    require(rejected == list(cases), "linked CPU transport mutation survived")
    require(reader_span_is_disjoint(0x2277, value["reader"]["bytes"]),
            "priced 0x2277 positive control rejected")
    return rejected


def postlink_artifacts(paths: Mapping[str, Path]) -> tuple[Path, Path]:
    """Resolve this wrapper's inputs through the typed producer vocabulary."""
    return paths["elf"], paths["map"]


def produce_child() -> int:
    configure()
    result = BASE.produce_child()
    paths = artifact_paths()
    elf, map_path = postlink_artifacts(paths)
    gate = linked_transport_gate(elf, map_path)
    value = load(PRODUCER_RESULT)
    value["v21_linked_transport"] = gate
    value["v21_linked_mutations"] = linked_mutations(gate)
    PRODUCER_RESULT.write_bytes(canonical(value))
    return result


def scope_child() -> int:
    configure()
    return BASE.scope_child()


def acceptance_child() -> int:
    configure()
    return BASE.acceptance_child()


def run_child(action: str) -> None:
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"fresh Link-107 child {action} red:\n{result.stdout}")


def card() -> None:
    preflight = validate_preflight()
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "Link-107 CPU-transport card is one-shot")
    PREFLIGHT.mkdir(parents=True)
    INVOCATION.write_bytes(canonical({
        "status": "INVOKED", "link": LINK,
        "commission": preflight["authority"]["commission"],
        "preflight": bind(PRE.RECEIPT), "contract": bind(CONTRACT),
        "driver": bind(DRIVER)}))
    run_child("_produce")
    before = frozen_artifacts()
    run_child("_scope")
    run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "Link-107 acceptance changed frozen artifacts")
    producer = load(PRODUCER_RESULT)
    scope = load(SCOPE_RESULT)
    acceptance = load(ACCEPTANCE_RESULT)
    require(len({os.getpid(), producer["pid"], scope["pid"],
                 acceptance["pid"]}) == 4,
            "Link-107 card process isolation drift")
    gate = producer["v21_linked_transport"]
    require(producer["v21_linked_mutations"] == linked_mutations(gate),
            "linked transport mutation receipt drift")
    receipt = {
        "format": FORMAT, "recorded_on": RECORDED_ON,
        "status": "PASS: Link-107 CPU transport product card green",
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "WPLTO_runs": 1, "product_links": 1, "media_builds": 0,
            "device_contacts": 0},
        "authority": {"preflight": bind(PRE.RECEIPT), "contract": bind(CONTRACT),
                      "driver": bind(DRIVER)},
        "transport": gate,
        "workload": preflight["workload"],
        "crc_attribution": preflight["crc"],
        "candidate_oracle_inputs": producer["candidate_oracle_inputs"],
        "artifacts_before": before, "artifacts_after": after,
        "process_isolation": {"parent": os.getpid(), "producer": producer["pid"],
            "owner_scope": scope["pid"], "acceptance": acceptance["pid"],
            "all_distinct": True},
        "acceptance": {key: item for key, item in acceptance.items()
                       if key not in ("status", "pid")},
        "owner_scope": scope["gate"],
        "mutations_rejected": {
            "preflight": len(preflight["mutations_rejected"]),
            "linked": producer["v21_linked_mutations"]},
        "next": "completion and complete same-world media closure, then D1",
        "claim_limit": "One linked product card only; completion, media and device have not run.",
    }
    RECEIPT.write_bytes(canonical(receipt))
    print("2.1 CPU transport: CARD PASS card=1/1 "
          f"reader={gate['reader']['bytes']}B VMA=103")


def record_final_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in artifact_paths().items()
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v2.1-cpu-transport-card-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: Link-107 returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "WPLTO_runs": 1 if artifacts else 0,
            "product_link_attempts": 1 if artifacts else 0,
            "media_builds": 0, "device_contacts": 0},
        "artifacts": artifacts, "retry_authorized": False,
        "owner_disposition_required": True,
        "authority": {"preflight": bind(PRE.RECEIPT), "contract": bind(CONTRACT),
                      "driver": bind(DRIVER)},
    }))


def check() -> None:
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value.get("retry_authorized") is False
                and value.get("owner_disposition_required") is True,
                "Link-107 Final Red drift")
        print("2.1 CPU transport: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        validate_preflight()
        print("2.1 CPU transport: CHECK ARMED card=0/1")
        return
    value = load(RECEIPT)
    require(value.get("status") == "PASS: Link-107 CPU transport product card green"
            and value["attempt_accounting"]["cards_consumed"] == 1
            and value["artifacts_before"] == frozen_artifacts()
            and value["artifacts_after"] == value["artifacts_before"]
            and value["process_isolation"]["all_distinct"] is True,
            "Link-107 green receipt drift")
    print("2.1 CPU transport: CHECK PASS card=1/1")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("card", "check", "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    {"card": card, "check": check, "_produce": produce_child,
     "_scope": scope_child, "_accept": acceptance_child}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_final_red(error)
            except Exception as receipt_error:
                print(f"Link-107 Final Red receipt failure: {receipt_error}", file=sys.stderr)
        print(f"2.1 CPU transport: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
