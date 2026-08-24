#!/usr/bin/env python3
"""Prove the bound-origin raw/seen/stored/taken input witness pre-link."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from copy import deepcopy
from typing import Any

from elf_truth import ElfTruth
import c2_product_substitution_link as PRODUCT


ROOT = Path(__file__).resolve().parents[2]
CAPTURE = ROOT / "src/optional/c2_kernal_input_capture.s"
CONSUMER = ROOT / "src/optional/c2_kernal_input_consumer.s"
EQUATES = ROOT / "src/c2_kernal_window_equates.inc"
COMFORT = ROOT / "lib/repl-comfort.lisp"
RECEIPT = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                  "c2.3-v1.6-input-bound-origin-instrument-receipt.json")
RAW_SUCCESSOR = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-recovery-sanitization-adapter-qualification-resume.json")
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
CLANG = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
LD = ROOT / "tools/llvm-mos/bin/ld.lld"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
AUTHORITY = "726ed55b"


class CounterGateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CounterGateError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORITY}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    for token in (b"bound origin", b"atomically at activation",
                  b"raw-arrival counter", b"physical queue"):
        require(token in raw, f"counter authority token absent: {token!r}")
    return {"commit": AUTHORITY, "path": name, "sha256": sha(raw)}


def assemble() -> ElfTruth:
    with tempfile.TemporaryDirectory(prefix="c2-v160-input-counters-") as name:
        root = Path(name)
        capture = root / "capture.o"
        consumer = root / "consumer.o"
        owner_source = root / "equate-owner.s"
        owner = root / "equate-owner.o"
        linked = root / "linked.o"
        owner_source.write_text(
            '.set C2K_EQUATE_OWNER, 1\n'
            '.include "c2_kernal_window_equates.inc"\n', encoding="utf-8")
        subprocess.run([str(CLANG), "-Isrc", "-c", str(CAPTURE), "-o",
                        str(capture)], cwd=ROOT, check=True)
        subprocess.run([str(CLANG), "-Isrc", "-c", str(CONSUMER), "-o",
                        str(consumer)], cwd=ROOT, check=True)
        subprocess.run([str(CLANG), "-Isrc", "-c", str(owner_source), "-o",
                        str(owner)], cwd=ROOT, check=True)
        subprocess.run([str(LD), "-r", "-o", str(linked), str(capture),
                        str(consumer), str(owner)], cwd=ROOT, check=True)
        return ElfTruth.read(linked, llvm_readobj=READOBJ,
                             include_section_data=True)


def relocation_opcode(truth: ElfTruth, symbol: str) -> tuple[str, int, int]:
    rows = [row for row in truth.relocations if row.target == symbol]
    require(len(rows) == 1, f"counter relocation multiplicity: {symbol}")
    row = rows[0]
    section = truth.section(row.source_section)
    raw = truth.section_bytes(row.source_section)
    offset = row.offset - section.address
    require(offset >= 1, f"counter relocation has no owning opcode: {symbol}")
    return row.source_section, row.offset - 1, raw[offset - 1]


def linked_shape() -> dict[str, Any]:
    truth = assemble()
    sizes = {name: truth.section(name).bytes for name in (
        ".lisp65_c2_kernal_window.irq_handler",
        ".lisp65_c2_kernal_window.input_capture_main",
        ".lisp65_c2_kernal_window.input_capture_helper",
        ".lisp65_c2_kernal_window.input_consumer")}
    require(list(sizes.values()) == [74, 28, 40, 70],
            f"instrumented section shape drift: {sizes}")
    base = truth.symbol("C2K_INPUT_RING_BASE").value
    slots = truth.symbol("C2K_INPUT_RING_SLOTS").value
    counters = {name: truth.symbol(name).value for name in (
        "C2K_INPUT_EVENTS_RAW", "C2K_INPUT_EVENTS_SEEN", "C2K_INPUT_EVENTS_STORED",
        "C2K_INPUT_EVENTS_TAKEN")}
    require(base == 0xBC90 and slots == 108
            and list(counters.values()) == [base + 108, base + 109,
                                             base + 110, base + 111],
            "ring/counter allocation is not 108+4 inside 112 bytes")
    sites = {name: relocation_opcode(truth, name) for name in counters}
    require(all(opcode == 0xEE for _section, _site, opcode in sites.values()),
            "counter update is not one INC abs per health signal")
    require(sites["C2K_INPUT_EVENTS_RAW"][0].endswith("input_capture_main")
            and sites["C2K_INPUT_EVENTS_SEEN"][0].endswith("input_capture_main")
            and sites["C2K_INPUT_EVENTS_STORED"][0].endswith("input_capture_helper")
            and sites["C2K_INPUT_EVENTS_TAKEN"][0].endswith("input_consumer"),
            "counter ownership drift")
    return {"sections": sizes, "ring_base": base, "ring_index_values": slots,
            "physical_allocation_bytes": 112, "usable_events": slots - 1,
            "counter_addresses": counters,
            "counter_sites": {name: {"section": row[0], "opcode_address": row[1],
                                     "opcode": "INC abs"}
                              for name, row in sites.items()},
            "E000_delta_bytes": 12, "E000_surplus_over_floor_bytes": 3}


def origin_gate() -> dict[str, Any]:
    source = COMFORT.read_text(encoding="utf-8")
    reset = ["(poke 255 140 0)", "(dotimes (counter 4 nil)",
             "(poke 188 (+ 252 counter) 0))", "(poke 255 141 0)"]
    pattern = r"\s+".join(re.escape(row) for row in reset)
    require(len(re.findall(pattern, source)) == 1,
            "Comfort session must have exactly one bound counter origin")
    require(source.count("(poke 255 141 255)") == 3,
            "capture-close lifecycle multiplicity drift")
    return {"phase": "Comfort activation", "closed_tail": "0xff",
            "activation_sites": 1, "reset_order": reset[:-1],
            "commit": reset[-1],
            "atomicity": "IRQ capture remains disabled until final tail=0"}


def model(events: list[int], *, take: int, slots: int = 108) -> dict[str, int]:
    ring = [0] * slots
    head = tail = raw = seen = stored = taken = 0
    for value in events:
        raw = (raw + 1) & 0xff
        seen = (seen + 1) & 0xff
        if value == 3:
            continue
        following = 0 if head == slots - 1 else head + 1
        if following == tail:
            continue
        ring[head] = value
        head = following
        stored = (stored + 1) & 0xff
    for _ in range(take):
        if tail == head:
            break
        _value = ring[tail]
        tail = 0 if tail == slots - 1 else tail + 1
        taken = (taken + 1) & 0xff
    return {"raw": raw, "seen": seen, "stored": stored, "taken": taken,
            "backlog": (head - tail) % slots}


def behavioral_gate() -> dict[str, Any]:
    normal = model([32 + index % 64 for index in range(94)], take=94)
    require(normal == {"raw": 94, "seen": 94, "stored": 94, "taken": 94, "backlog": 0},
            "94-event counter wall drift")
    full = model(list(range(108)), take=0)
    require(full == {"raw": 108, "seen": 108, "stored": 107, "taken": 0,
                     "backlog": 107},
            "full-ring counter discriminator drift")
    stopped = model([ord("a"), 3, ord("b")], take=2)
    require(stopped == {"raw": 3, "seen": 3, "stored": 2, "taken": 2, "backlog": 0},
            "RUN/STOP seen/stored domain drift")
    return {"loss_wall": normal, "full_ring": full, "run_stop": stopped,
            "measurement_bound": "bound-zero activation; fewer than 256 events",
            "decision_table": {
                "raw_below_physical": "before queue-present observation",
                "raw_above_seen": "queue drain between presence and code read",
                "seen_above_stored": "ring full or capture commit loss",
                "stored_above_taken": "consumer backlog or take failure",
                "all_equal_visible_differs": "edit/render semantic path"}}


def linker_contract() -> dict[str, Any]:
    PRODUCT.configure_e000_reopening()
    PRODUCT.configure_input_capture()
    PRODUCT.configure_input_hybrid()
    script = PRODUCT.linker_script()
    require("SIZEOF(.lisp65_c2_kernal_window.input_capture_helper) == 40"
            in script, "instrumented capture-helper size absent from linker")
    require("SIZEOF(.lisp65_c2_kernal_window.input_consumer) <= 70" in script,
            "instrumented consumer ceiling absent from linker")
    require("SIZEOF(.lisp65_c2_kernal_window.input_consumer))) >= 57" in script
            and "54-byte floor plus 3-byte watch" in script
            and ">= 60" not in script,
            "post-instrument E000 floor/watch contract drift")
    return {"capture_helper_bytes": 40, "consumer_maximum_bytes": 70,
            "free_bytes_minimum": 57, "fixed_floor_bytes": 54,
            "surplus_watch_bytes": 3, "source": "generated live linker script"}


def derive() -> dict[str, Any]:
    return {"format": "lisp65-c2.3-v1.6-input-bound-origin-instrument-v1",
            "status": "HOST-GREEN: PRODUCT COUNTERS BOUNDED AND OWNED",
            "authority": authority(),
            "sources": {path.relative_to(ROOT).as_posix(): sha(path.read_bytes())
            for path in (CAPTURE, CONSUMER, EQUATES, COMFORT)},
            "origin": origin_gate(), "linked_shape": linked_shape(), "behavior": behavioral_gate(),
            "linker_contract": linker_contract(),
            "claim_limit": "pre-link product-source gate; no WPLTO, media or device claim"}


def validate(value: dict[str, Any]) -> None:
    shape = value["linked_shape"]
    behavior = value["behavior"]
    require(value["origin"] == {
        "phase": "Comfort activation", "closed_tail": "0xff",
        "activation_sites": 1,
        "reset_order": ["(poke 255 140 0)", "(dotimes (counter 4 nil)",
                        "(poke 188 (+ 252 counter) 0))"],
        "commit": "(poke 255 141 0)",
        "atomicity": "IRQ capture remains disabled until final tail=0"},
        "bound counter origin validation failed")
    require(shape["ring_index_values"] == 108
            and shape["physical_allocation_bytes"] == 112
            and shape["usable_events"] == 107,
            "ring/counter split validation failed")
    require(list(shape["counter_addresses"].values()) ==
            [shape["ring_base"] + 108, shape["ring_base"] + 109,
             shape["ring_base"] + 110, shape["ring_base"] + 111],
            "counter address validation failed")
    require(all(row["opcode"] == "INC abs"
                for row in shape["counter_sites"].values()),
            "counter update validation failed")
    require(behavior["loss_wall"] ==
            {"raw": 94, "seen": 94, "stored": 94, "taken": 94, "backlog": 0},
            "94-event counter wall validation failed")
    require(behavior["full_ring"] ==
            {"raw": 108, "seen": 108, "stored": 107, "taken": 0, "backlog": 107},
            "full-ring discriminator validation failed")
    require(behavior["run_stop"] ==
            {"raw": 3, "seen": 3, "stored": 2, "taken": 2, "backlog": 0},
            "RUN/STOP counter-domain validation failed")
    require(value["linker_contract"] == {
        "capture_helper_bytes": 40, "consumer_maximum_bytes": 70,
        "free_bytes_minimum": 57, "fixed_floor_bytes": 54,
        "surplus_watch_bytes": 3, "source": "generated live linker script"},
        "live linker floor/watch validation failed")


def raw_successor_gate(value: dict[str, Any], successor: dict[str, Any]) -> None:
    shape = value["linked_shape"]
    names = list(shape["counter_addresses"])
    require(
        successor == {
            "contract": "ring_usable_events >= loss_wall_events",
            "counter_count": 4,
            "counter_names": [
                "C2K_INPUT_EVENTS_RAW", "C2K_INPUT_EVENTS_SEEN",
                "C2K_INPUT_EVENTS_STORED", "C2K_INPUT_EVENTS_TAKEN"],
            "loss_wall_events": 94,
            "mutations_rejected": [
                "restore-pre-RAW-108-14-pin",
                "loss-wall-exceeds-derived-capacity"],
            "physical_allocation_bytes": 112,
            "reserve_events": 13,
            "ring_index_values": 108,
            "ring_usable_events": 107,
            "source": "candidate counter population",
        }
        and names == successor["counter_names"]
        and shape["physical_allocation_bytes"] ==
            successor["physical_allocation_bytes"]
        and shape["ring_index_values"] == successor["ring_index_values"]
        and shape["usable_events"] == successor["ring_usable_events"],
        "authorized RAW-counter successor drift")


def selftest() -> None:
    value = derive()
    validate(value)
    mutations = 0
    for mutate in (
            lambda row: row["linked_shape"].__setitem__("ring_index_values", 112),
            lambda row: row["origin"].__setitem__("commit", "missing"),
            lambda row: row["linked_shape"]["counter_sites"]
            ["C2K_INPUT_EVENTS_STORED"].__setitem__("opcode", "STA abs"),
            lambda row: row["behavior"]["full_ring"].__setitem__("stored", 109),
            lambda row: row["linker_contract"].__setitem__(
                "free_bytes_minimum", 66)):
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate(trial)
        except CounterGateError:
            mutations += 1
    require(mutations == 5, "counter mutation suite drift")
    print("v1.6 input counters: SELFTEST PASS mutations=5")


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in {"check", "selftest"},
            "usage: c2_v160_input_drop_counters.py check|selftest")
    if sys.argv[1] == "selftest":
        selftest()
    else:
        value = derive()
        validate(value)
        sealed = json.loads(RECEIPT.read_text(encoding="utf-8"))
        validate(sealed)
        require(set(value["sources"]) == set(sealed["sources"]),
                "counter source-owner population drift")
        successor_receipt = json.loads(RAW_SUCCESSOR.read_text(encoding="utf-8"))
        successor = successor_receipt["receipt_adapter"]
        raw_successor_gate(value, successor)
        rejected = 0
        for mutate in (
                lambda row: row["counter_names"].remove(
                    "C2K_INPUT_EVENTS_RAW"),
                lambda row: row.__setitem__("ring_index_values", 109),
                lambda row: row.__setitem__("reserve_events", 14)):
            trial = deepcopy(successor); mutate(trial)
            try:
                raw_successor_gate(value, trial)
            except CounterGateError:
                rejected += 1
        require(rejected == 3, "RAW-successor mutation survived")
        changed = sorted(name for name in value["sources"]
                         if value["sources"][name] != sealed["sources"][name])
        print("v1.6 input counters: CHECK PASS ring=107 margin=13 "
              f"E000={value['linked_shape']['E000_delta_bytes']}B/3-over-floor "
              f"sealed=historical live=RAW-successor changed={changed}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CounterGateError, OSError, subprocess.CalledProcessError) as error:
        print(f"v1.6 input counters: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
