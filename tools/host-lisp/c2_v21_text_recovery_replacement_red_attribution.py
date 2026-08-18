#!/usr/bin/env python3
"""Bind the final red of the sole 2.1 text-recovery replacement card."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v2.1-text-recovery-replacement-card/wplto"
ELF = BUILD / "lisp65-c2-substitution-linked.prg.elf"
MANIFEST = BUILD / "runtime-overlays-session-final.json"
FINAL_RED = ARCH / "c2.3-v2.1-text-recovery-replacement-card-final-red.json"
PREDECESSOR = ARCH / "c2.3-v2.1-text-recovery-card-red-attribution-receipt.json"
RECEIPT = ARCH / (
    "c2.3-v2.1-text-recovery-replacement-card-red-attribution-receipt.json")
CARD_DRIVER = ROOT / "tools/host-lisp/c2_v21_text_recovery_replacement_card.py"
PRODUCT_DRIVER = ROOT / "tools/host-lisp/c2_product_substitution_link.py"
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
FORMAT = "lisp65-c2.3-v2.1-text-recovery-replacement-red-attribution-v1"
STATUS = "ATTRIBUTED FINAL RED: exported intra-function labels split ownership"
RECORDED_ON = "2026-08-14"
HISTORICAL_CARD_COMMIT = "b9fd173e"


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


def historical_bind(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"path": name, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def disassembly(section: str) -> str:
    return subprocess.run(
        [str(OBJDUMP), "-d", f"--section={section}", str(ELF)],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.lower()


def actual_call(truth: ElfTruth, label_name: str, tail: bytes) -> dict[str, Any]:
    label = truth.symbol(label_name)
    vector = truth.symbol("c2_facade_runtime_overlay_exec")
    section = truth.section(label.section)
    raw = truth.section_bytes(label.section)
    pattern = bytes((0x20, vector.value & 0xFF, vector.value >> 8)) + tail
    start = label.value - section.address - len(pattern)
    require(raw[start:start + len(pattern)] == pattern,
            f"linked real-caller bytes drift: {label_name}")
    call = label.value - len(pattern)
    pushed = call + 2
    return {"label": f"0x{label.value:04x}", "call": f"0x{call:04x}",
            "emitted_bytes": pattern.hex(), "gap_bytes": len(tail),
            "hardware_pushed_return": f"0x{pushed:04x}",
            "label_minus": label.value - pushed}


def derive() -> dict[str, Any]:
    red = load(FINAL_RED)
    predecessor = load(PREDECESSOR)
    require(
        red.get("status") == "FINAL RED: text-recovery replacement returns to owner"
        and red.get("retry_authorized") is False
        and red.get("owner_disposition_required") is True
        and red["attempt_accounting"] == {
            "replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1, "WPLTO_runs": 1,
            "product_link_attempts": 1, "media_builds": 0,
            "device_contacts": 0}
        and predecessor.get("status")
            == "ATTRIBUTED FINAL RED: completion pin plus real-consumer selector mismatch",
        "replacement card/predecessor disposition drift")

    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    binding = truth.section(".lisp65_runtime_overlay_verifier_bindings")
    publish = load(BUILD / "runtime-verifier-publish-last.json")
    total = load(BUILD / "total-publish-last-domain.json")
    require((binding.address, binding.bytes) == (0xB98C, 40)
            and publish["status"] == total["status"] == "passed"
            and publish["address"] == publish["expected_address"] == binding.address
            and (BUILD / "runtime-overlays-boot-final.bin").is_file()
            and (BUILD / "runtime-overlays-session-final.bin").is_file(),
            "candidate-derived completion did not finish")

    c2d = actual_call(truth, "c2_stream_c2d_read_return", bytes.fromhex("aa"))
    shelf = actual_call(
        truth, "c2_stream_shelf_read_return", bytes.fromhex("8510"))
    selector = truth.symbol("c2_map_cpu_selector")
    selector_section = truth.section(selector.section)
    selector_raw = truth.section_bytes(selector.section)[
        selector.value - selector_section.address:
        selector.value - selector_section.address + selector.bytes]
    c2d_stack = int(c2d["hardware_pushed_return"], 16)
    shelf_stack = int(shelf["hardware_pushed_return"], 16)
    selector_match = (
        selector_raw[7] == c2d_stack >> 8
        and selector_raw[14] == (c2d_stack & 0xFF)
        and selector_raw[20] == shelf_stack >> 8
        and selector_raw[27] == (shelf_stack & 0xFF))
    require(c2d["gap_bytes"] == 1 and c2d["label_minus"] == 2
            and shelf["gap_bytes"] == 2 and shelf["label_minus"] == 3
            and selector_match,
            "real-emitted selector correction is not green")

    text = truth.section(".text")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    cold = truth.section(".lisp65_rt_c2emit_final_crc")
    helper = truth.symbol("c2e_w32")
    manifest = load(MANIFEST)
    rows = sorted(manifest["slices"], key=lambda row: row["file_offset"])
    row = next(item for item in rows if item["section"] == cold.name)
    following = rows[rows.index(row) + 1]
    allocation = following["file_offset"] - row["file_offset"]
    require(facade.address - (text.address + text.bytes) == 24
            and helper.bytes == 63 and cold.bytes == 1246
            and allocation == 1280 and manifest["storage"]["size"] == 65423,
            "green placement changed in replacement")

    c2d_fn = truth.symbol("c2_stream_c2d_read")
    shelf_fn = truth.symbol("c2_stream_shelf_read")
    c2d_label = truth.symbol("c2_stream_c2d_read_return")
    shelf_label = truth.symbol("c2_stream_shelf_read_return")
    require(c2d_label.binding == shelf_label.binding == "Global"
            and c2d_label.symbol_type == shelf_label.symbol_type == "None"
            and c2d_fn.value < c2d_label.value < c2d_fn.value + c2d_fn.bytes
            and shelf_fn.value < shelf_label.value < shelf_fn.value + shelf_fn.bytes,
            "exported intra-function label identity drift")
    e000 = disassembly(".lisp65_c2_kernal_window.c2_resident")
    offending = re.findall(
        r"^\s*([0-9a-f]+):.*\bjmp\s+\$(e32a|e850|e853|e859)\b",
        e000, re.M)
    require(len(offending) == 7
            and "KERNAL freedom red: qualified edge violations" in
                red["error"]["message"]
            and red["error"]["message"].count(
                "inter-function-jmp-not-entry") == 7,
            "owned-control-flow Final Red attribution drift")

    return {
        "format": FORMAT, "recorded_on": RECORDED_ON, "status": STATUS,
        "authority": {"final_red": bind(FINAL_RED),
            "predecessor_attribution": bind(PREDECESSOR), "ELF": bind(ELF),
            "card_driver": historical_bind(HISTORICAL_CARD_COMMIT, CARD_DRIVER),
            # Historical receipts witness the source world that emitted
            # them; they never gate a living successor source tree.
            "product_gate": historical_bind(
                HISTORICAL_CARD_COMMIT, PRODUCT_DRIVER),
            "driver": historical_bind(HISTORICAL_CARD_COMMIT, DRIVER)},
        "authorized_fixes": {
            "candidate_completion": {"status": "GREEN",
                "section": binding.name, "address": "0xb98c",
                "bytes": binding.bytes, "historical_0xb98a_consumed": False,
                "final_overlay_families_built": 2},
            "real_emitted_selector": {"status": "GREEN", "c2d": c2d,
                "shelf": shelf, "selector_operands_match": selector_match}},
        "green_placement": {"resident_reserve_bytes": 24,
            "cold_helper_bytes": helper.bytes, "cold_slice_bytes": cold.bytes,
            "packed_page_bytes": allocation,
            "aggregate_bytes": manifest["storage"]["size"],
            "aggregate_growth_bytes": 0},
        "new_final_red": {
            "class": "EXPORTED-INTRA-FUNCTION-LABEL-SPLITS-CONTROL-FLOW-OWNERSHIP",
            "labels": {
                c2d_label.name: {"address": f"0x{c2d_label.value:04x}",
                    "binding": c2d_label.binding, "type": c2d_label.symbol_type,
                    "inside_function": c2d_fn.name},
                shelf_label.name: {"address": f"0x{shelf_label.value:04x}",
                    "binding": shelf_label.binding, "type": shelf_label.symbol_type,
                    "inside_function": shelf_fn.name}},
            "qualified_edge_violations": len(offending),
            "reason": "inter-function-jmp-not-entry",
            "mechanism": (
                "llvm-objdump starts named nodes at the exported labels; the "
                "ownership gate consequently assigns later basic blocks to a "
                "different node and rejects seven legal intra-function JMPs."),
            "product_geometry_implicated": False,
            "completion_identity_implicated": False,
            "selector_runtime_identity_implicated": False},
        "card_disposition": {"replacement_card_consumed": True,
            "retry_authorized": False, "owner_disposition_required": True,
            "completion_allowed": False, "media_allowed": False,
            "device_allowed": False},
        "attempt_accounting": red["attempt_accounting"],
        "claim_limit": (
            "Read-only attribution of the consumed replacement card. Both "
            "authorized identity fixes and placement are green; no retry, "
            "media, device, D1-D5 or release claim is authorized."),
    }


def validate(value: dict[str, Any]) -> None:
    require(value == derive(), "replacement Final Red attribution drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "resurrect-b98a": lambda x: x["authorized_fixes"][
            "candidate_completion"].update(historical_0xb98a_consumed=True),
        "hide-selector-match": lambda x: x["authorized_fixes"][
            "real_emitted_selector"].update(selector_operands_match=False),
        "erase-reserve": lambda x: x["green_placement"].update(
            resident_reserve_bytes=0),
        "blame-geometry": lambda x: x["new_final_red"].update(
            product_geometry_implicated=True),
        "blame-completion": lambda x: x["new_final_red"].update(
            completion_identity_implicated=True),
        "blame-selector-runtime": lambda x: x["new_final_red"].update(
            selector_runtime_identity_implicated=True),
        "erase-edge": lambda x: x["new_final_red"].update(
            qualified_edge_violations=6),
        "authorize-retry": lambda x: x["card_disposition"].update(
            retry_authorized=True),
        "allow-media": lambda x: x["card_disposition"].update(
            media_allowed=True),
        "claim-device": lambda x: x["attempt_accounting"].update(
            device_contacts=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases), "replacement attribution mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "replacement attribution receipt exists")
    value = derive(); validate(value)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("2.1 replacement red attribution: PASS fixes=2 reserve=24 "
          "edges=7 mutations=10 retry=none")


def check() -> None:
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate(value)
    require(rejected == mutations(value),
            "replacement attribution mutation set drift")
    print("2.1 replacement red attribution: PASS fixes=2 reserve=24 "
          "edges=7 mutations=10 retry=none")


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in ("record", "check"),
            "usage: c2_v21_text_recovery_replacement_red_attribution.py record|check")
    {"record": record, "check": check}[sys.argv[1]]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"2.1 replacement red attribution: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
