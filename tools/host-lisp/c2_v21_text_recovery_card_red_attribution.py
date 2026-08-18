#!/usr/bin/env python3
"""Attribute the final-red 2.1 cold-relocation/selector product card."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RED = ARCH / "c2.3-v2.1-text-recovery-card-final-red.json"
RECEIPT = ARCH / "c2.3-v2.1-text-recovery-card-red-attribution-receipt.json"
BUILD = ROOT / "build/c2.3/v2.1-text-recovery-card/wplto"
ELF = BUILD / "lisp65-c2-substitution-linked.prg.elf"
MAP = BUILD / "lisp65-c2-substitution-linked.prg.map"
MANIFEST = BUILD / "runtime-overlays-session-unbound.json"
PRODUCT = ROOT / "tools/host-lisp/c2_product_substitution_link.py"
OWNERSHIP = ROOT / "config/c2-full-map-ownership-contract.json"
CARD = ROOT / "tools/host-lisp/c2_v21_text_recovery_card.py"
DRIVER = Path(__file__).resolve()
LLVM = ROOT / "tools/llvm-mos/bin"
RECORDED_ON = "2026-08-14"
HISTORICAL_CARD_COMMIT = "681e56e0"


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


def historical_bind(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"path": name, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def historical_text(commit: str, path: Path) -> str:
    """Read evidence from the world that emitted the historical receipt."""
    name = path.relative_to(ROOT).as_posix()
    return subprocess.run(
        ["git", "show", f"{commit}:{name}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def run(*argv: str) -> str:
    return subprocess.run(argv, cwd=ROOT, check=True, text=True,
                          stdout=subprocess.PIPE).stdout


def call_identity(disassembly: str, function: Any, returned: Any) -> dict[str, Any]:
    body = "\n".join(
        line for line in disassembly.splitlines()
        if (match := re.match(r"^\s*([0-9a-fA-F]+):", line))
        and function.value <= int(match.group(1), 16)
        < function.value + function.bytes)
    calls = [int(item, 16) for item in re.findall(
        r"^\s*([0-9a-fA-F]+):.*jsr\s+\$b5eb\b", body, re.M)]
    require(len(calls) == 1, f"fixed-vector call identity drift: {function.name}")
    call = calls[0]
    pushed = call + 2
    next_pc = call + 3
    expected = returned.value - 1
    between = "\n".join(
        line for line in body.splitlines()
        if (match := re.match(r"^\s*([0-9a-fA-F]+):", line))
        and next_pc <= int(match.group(1), 16) < returned.value)
    return {
        "function": function.name,
        "JSR": f"0x{call:04x}",
        "hardware_pushed_return": f"0x{pushed:04x}",
        "symbolic_post_call_label": f"0x{returned.value:04x}",
        "selector_expected_return": f"0x{expected:04x}",
        "mismatch_bytes": expected - pushed,
        "compiler_instructions_before_label": between.strip(),
        "selector_match": pushed == expected,
    }


def derive() -> dict[str, Any]:
    red = load(RED)
    require(red.get("status") == "FINAL RED: 2.1 text-recovery card returns to owner"
            and red.get("retry_authorized") is False
            and red.get("owner_disposition_required") is True
            and red.get("attempt_accounting", {}).get("cards_consumed") == 1
            and "verifier binding address drift 0xb98c != 0xb98a"
                in red.get("error", {}).get("message", ""),
            "text-recovery Final Red authority drift")
    truth = ElfTruth.read(ELF, llvm_readobj=LLVM / "llvm-readobj")
    text = truth.section(".text")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    fixed = truth.section(".lisp65_c2_host_facade")
    cold = truth.section(".lisp65_rt_c2emit_final_crc")
    reader = truth.symbol("c2_map_cpu_read")
    selector = truth.symbol("c2_map_cpu_selector")
    helper = truth.symbol("c2e_w32")
    vector = truth.symbol("c2_facade_runtime_overlay_exec")
    e000 = run(str(LLVM / "llvm-objdump"), "-d",
                "--section=.lisp65_c2_kernal_window.c2_resident", str(ELF)).lower()
    calls = [
        call_identity(e000, truth.symbol("c2_stream_c2d_read"),
                      truth.symbol("c2_stream_c2d_read_return")),
        call_identity(e000, truth.symbol("c2_stream_shelf_read"),
                      truth.symbol("c2_stream_shelf_read_return")),
    ]
    require([row["mismatch_bytes"] for row in calls] == [1, 2]
            and all(row["selector_match"] is False for row in calls),
            "real-consumer return-label mismatch changed")

    manifest = load(MANIFEST)
    rows = sorted(manifest["slices"], key=lambda row: row["file_offset"])
    row = next(item for item in rows if item["section"] == cold.name)
    allocation = rows[rows.index(row) + 1]["file_offset"] - row["file_offset"]
    all_disassembly = run(str(LLVM / "llvm-objdump"), "-d", str(ELF)).lower()
    helper_calls = re.findall(
        rf"^\s*([0-9a-f]+):.*jsr\s+\${helper.value:x}\b",
        all_disassembly, re.M)
    require(
        text.address + text.bytes == 0xB398 and facade.address == 0xB3B0
        and reader.bytes == 166 and selector.bytes == 40
        and helper.section == cold.name and helper.bytes == 63
        and cold.bytes == row["file_size"] == 1246
        and allocation == 1280 and manifest["storage"]["size"] == 65423
        and len(helper_calls) == 5 and fixed.bytes == 48 and vector.value == 0xB5EB,
        "linked placement proof drift")

    sections = {item.name: item for item in truth.sections}
    binding = sections[".lisp65_runtime_overlay_verifier_bindings"]
    # Historical receipts witness their own source world.  Re-deriving this
    # attribution from the living product linker turns an evidentiary record
    # into a predicate over unrelated successor work.
    product_source = historical_text(HISTORICAL_CARD_COMMIT, PRODUCT)
    ownership = load(OWNERSHIP)
    ownership_row = next(item for item in ownership["selected_layout"]
                         ["ordinary_outputs"]
                         if item.get("output")
                         == ".lisp65_runtime_overlay_verifier_bindings")
    require(binding.address == 0xB98C and binding.bytes == 40
            and "LINK60_VERIFIER_BINDING_BASE = 0xB98A" in product_source
            and ownership_row["start"] == "0xb98c",
            "completion-pin attribution drift")
    value = {
        "format": "lisp65-c2.3-v2.1-text-recovery-card-red-attribution-v1",
        "recorded_on": RECORDED_ON,
        "status": "ATTRIBUTED FINAL RED: completion pin plus real-consumer selector mismatch",
        "card_disposition": {"card_consumed": True, "retry_authorized": False,
                             "owner_disposition_required": True,
                             "completion_allowed": False,
                             "media_allowed": False, "device_allowed": False},
        "green_subresult": {
            "cold_displacement": {"symbol": helper.name, "bytes": helper.bytes,
                "linked_calls": len(helper_calls), "outside_cold_calls": 0,
                "slice_bytes": cold.bytes, "packed_page_bytes": allocation,
                "packed_padding_bytes": allocation - row["file_size"],
                "aggregate_bytes": manifest["storage"]["size"],
                "aggregate_growth_bytes": 0},
            "ordinary_text": {"end_exclusive": "0xb398",
                              "facade_start": "0xb3b0", "reserve_bytes": 24,
                              "net_resident_delta_bytes": -23},
            "reader_bytes": reader.bytes, "selector_bytes": selector.bytes,
            "fixed_block_bytes": fixed.bytes, "fixed_block_delta_bytes": 0,
            "E000_call_instruction_delta_bytes": 0,
            "contracted_margins_used_as_freight": False,
        },
        "first_stopper": {
            "class": "HISTORICAL-COMPLETION-PIN-CROSSES-CURRENT-FULL-MAP-CONTRACT",
            "linked_binding": {"address": "0xb98c", "bytes": binding.bytes},
            "current_ownership_contract": "0xb98c",
            "completion_expected_base": "0xb98a",
            "delta_bytes": 2,
            "effect": "publish-last verifier binding refused before final family pack",
            "product_geometry_implicated": False,
        },
        "independent_linked_red": {
            "class": "ISOLATED-FIXTURE-MASKED-REAL-CONSUMER-RETURN-LABEL-GAP",
            "fixed_vector": "0xb5eb",
            "selector": f"0x{selector.value:04x}",
            "calls": calls,
            "effect": (
                "Neither actual JSR return matches its selector identity; both "
                "would take the legacy runtime-overlay tail with reader arguments."),
            "preflight_gap": (
                "The isolated alias-call fixture placed its label immediately, but "
                "the real WPLTO consumer inserted result-preservation instructions. "
                "The actual linked consumer ran only after the card was consumed."),
            "card_acceptable_after_completion_pin_only": False,
        },
        "decision": {
            "result": "FINAL-RED-RETURN-TO-OWNER",
            "why": (
                "The placement thesis is proved, but fixing or replaying only the "
                "completion pin cannot make this card green: the linked selector "
                "identities are independently false."),
            "minimum_future_questions": [
                "derive publish-last base from the current full-map contract",
                "make return identity intrinsic to the real call instruction rather than a later C label",
                "run the actual generated consumer before any future card",
            ],
        },
        "attempt_accounting": red["attempt_accounting"],
        "authority": {"final_red": bind(RED), "ELF": bind(ELF), "map": bind(MAP),
                      "unbound_session_manifest": bind(MANIFEST),
                      "product_linker": historical_bind(
                          HISTORICAL_CARD_COMMIT, PRODUCT),
                      "ownership": bind(OWNERSHIP),
                      "card_driver": historical_bind(HISTORICAL_CARD_COMMIT, CARD),
                      "driver": historical_bind(HISTORICAL_CARD_COMMIT, DRIVER)},
        "claim_limit": (
            "Read-only attribution of the consumed card. It proves placement and "
            "two linked red mechanisms; it authorizes no repair, replay, completion, "
            "media, device, D1-D5 or release claim."),
    }
    validate(value)
    value["mutations_rejected"] = mutations(value)
    return value


def validate(value: dict[str, Any]) -> None:
    require(
        value["status"].startswith("ATTRIBUTED FINAL RED")
        and value["card_disposition"] == {
            "card_consumed": True, "retry_authorized": False,
            "owner_disposition_required": True, "completion_allowed": False,
            "media_allowed": False, "device_allowed": False}
        and value["green_subresult"]["ordinary_text"]["reserve_bytes"] == 24
        and value["green_subresult"]["cold_displacement"]["linked_calls"] == 5
        and value["green_subresult"]["cold_displacement"]["aggregate_growth_bytes"] == 0
        and value["green_subresult"]["contracted_margins_used_as_freight"] is False
        and value["first_stopper"]["delta_bytes"] == 2
        and value["first_stopper"]["product_geometry_implicated"] is False
        and [row["mismatch_bytes"] for row in
             value["independent_linked_red"]["calls"]] == [1, 2]
        and all(row["selector_match"] is False for row in
                value["independent_linked_red"]["calls"])
        and value["independent_linked_red"]
            ["card_acceptable_after_completion_pin_only"] is False
        and value["decision"]["result"] == "FINAL-RED-RETURN-TO-OWNER",
        "Final-Red attribution widened or weakened")


def mutations(value: dict[str, Any]) -> list[str]:
    cases = {
        "authorize-retry": lambda x: x["card_disposition"].update(retry_authorized=True),
        "allow-completion": lambda x: x["card_disposition"].update(completion_allowed=True),
        "erase-reserve": lambda x: x["green_subresult"]["ordinary_text"].update(
            reserve_bytes=0),
        "invent-warm-helper-call": lambda x: x["green_subresult"]
            ["cold_displacement"].update(linked_calls=6),
        "spend-margin": lambda x: x["green_subresult"].update(
            contracted_margins_used_as_freight=True),
        "blame-product-geometry": lambda x: x["first_stopper"].update(
            product_geometry_implicated=True),
        "erase-completion-delta": lambda x: x["first_stopper"].update(delta_bytes=0),
        "accept-c2d-return": lambda x: x["independent_linked_red"]["calls"][0].update(
            selector_match=True),
        "erase-shelf-gap": lambda x: x["independent_linked_red"]["calls"][1].update(
            mismatch_bytes=0),
        "accept-after-pin-only": lambda x: x["independent_linked_red"].update(
            card_acceptable_after_completion_pin_only=True),
        "claim-green": lambda x: x["decision"].update(result="PASS"),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate(candidate)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases), "Final-Red attribution mutation survived")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check"))
    action = parser.parse_args().action
    value = derive()
    if action == "record":
        RECEIPT.write_bytes(canonical(value))
    else:
        require(RECEIPT.read_bytes() == canonical(value),
                "Final-Red attribution receipt drift")
    print("2.1 text recovery red attribution: PASS placement=green reserve=24 "
          "completion-delta=2 selector-gaps=1/2 retry=none mutations=11")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"2.1 text recovery red attribution: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
