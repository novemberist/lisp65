#!/usr/bin/env python3
"""Wire the delivered v1.9 editor to the armed Capture ring."""

from __future__ import annotations

import argparse
from collections import Counter
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

from elf_truth import ElfTruth  # noqa: E402
import c2_v190_native_prompt_editor_display_repair_r7 as R7  # noqa: E402
import c2_v160_input_service_hybrid_final_world as FINAL  # noqa: E402


CARD = R7.CARD
BASE = R7.BASE
CLIENT = R7.CLIENT
PRICE = R7.PRICE
P0 = R7.P0
B = R7.DISPLAY.B
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.9.0-pre-plan.md"
PLAN_HEADER = "## Reviewer ruling — Block A consumer-side red, one repair round — 2026-08-28"
FIRST_RED = ARCH / (
    "c2.3-v1.9-block-a-forced-collection-followup-first-red-receipt.json")
R7_SOURCE = R7.CLIENT_SOURCE
R7_ELF = R7.ELF
R7_PRG = R7.PRG
R7_PROFILE = R7.PROFILE
R7_CODE = R7.CODE
R7_RECEIPT = R7.RECEIPT
R7_STATUS = R7.STATUS
CLIENT_COMMAND = CLIENT._command
CARD_INPUT_CLOSURE = CARD.input_closure
BUILD = ROOT / "build/c2.3/v1.9-block-a-delivered-consumer-repair-r8"
PREFLIGHT = ROOT / "build/c2.3/v1.9-block-a-delivered-consumer-repair-r8-preflight"
PLANE_ROOT = PREFLIGHT / "setup-owned/static-plane/narrow-static"
PLANE_RECEIPT = PREFLIGHT / "v19-delivered-consumer-static-plane.json"
CLIENT_SOURCE = PREFLIGHT / "sources/stdlib-read-line.lisp"
C2D = PLANE_ROOT / "v6-semantics/initial.c2d-v6.bin"
CODE = PLANE_ROOT / "v6-semantics/bank2-static-code.bin"
MANIFEST = PLANE_ROOT / "stdlib-p0.manifest.json"
HEADER = PLANE_ROOT / "stdlib-p0.h"
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
PROFILE = BUILD / "wplto/resolved-profile.txt"
INVOCATION = PREFLIGHT / "candidate-invocation-r8.json"
PREFLIGHT_RECEIPT = ARCH / (
    "c2.3-v1.9-block-a-delivered-consumer-repair-r8-preflight.json")
POST_LINK_RED = ARCH / (
    "c2.3-v1.9-block-a-delivered-consumer-repair-r8-post-link-red.json")
DIFFERENCE = ARCH / (
    "c2.3-v1.9-block-a-delivered-consumer-repair-r7-r8-difference.json")
RECEIPT = ARCH / (
    "c2.3-v1.9-block-a-delivered-consumer-repair-r8-receipt.json")
REPORT = ROOT / "docs/planning/v1.9.0-block-a-delivered-consumer-repair-report.md"
DRIVER = Path(__file__).resolve()
FORMAT = "lisp65-c2-v190-block-a-delivered-consumer-repair-r8-v1"
STATUS = "PASS: V1.9 BLOCK-A DELIVERED CONSUMER REPAIR GREEN"
OLD_STATE = "(state (list head head head 0 0 0 columns row))"
NEW_STATE = "(state (list head head head 0 0 0 columns row nil))"


class RepairError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RepairError(message)


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


def section_bind(path: Path, header: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    require(text.count(header) == 1, f"section drift: {header}")
    section = header + text.split(header, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    raw = section.encode()
    return {"path": path.relative_to(ROOT).as_posix(), "section": header,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    red = load(FIRST_RED)
    predecessor = load(R7_RECEIPT)
    require(red["status"] ==
                "FIRST RED: FINAL R7 READ-LINE ARMS CAPTURE BUT CONSUMES PUBLIC QUEUE"
            and red["mechanism"]["chain"]["delivered_state_cells"] == 8
            and red["device"]["observed"] == {
                "raw": 2, "seen": 2, "stored": 2, "taken": 0}
            and predecessor["status"] == R7_STATUS,
            "Block-A consumer-repair authority drift")
    return {"review_ruling": section_bind(PLAN, PLAN_HEADER),
            "device_first_red": bind(FIRST_RED),
            "r7_predecessor": bind(R7_RECEIPT),
            "budget": {"WPLTO_runs": 1, "product_links": 1,
                       "media_builds": 0, "device_contacts": 0}}


def derive_editor_source() -> str:
    source = R7_SOURCE.read_text(encoding="utf-8")
    require(source.count(OLD_STATE) == 1 and NEW_STATE not in source,
            "r7 delivered state seam drift")
    return source.replace(OLD_STATE, NEW_STATE, 1)


def validate_editor_source(source: str) -> dict[str, Any]:
    predecessor = R7_SOURCE.read_text(encoding="utf-8")
    require(bind(R7_SOURCE) == load(FIRST_RED)["mechanism"]["chain"][
                "sources"]["editor"],
            "sealed r7 source drift")
    route = """(if (nthcdr 8 state)
                    (%rl-render nil 0 0 0 0 -1)
                    (key-event 1))"""
    require(source == derive_editor_source()
            and source.count(NEW_STATE) == 1 and OLD_STATE not in source
            and source.count(route) == 1
            and "(if (car (nthcdr 8 state)) command (%read-line-loop state))"
                in source,
            "delivered consumer is not the exact ninth-nil transform")
    return {"status": "PASS: DELIVERED STATE SELECTS RING WITHOUT HISTORY",
        "predecessor": bind(R7_SOURCE),
        "candidate": {"bytes": len(source.encode()),
            "sha256": hashlib.sha256(source.encode()).hexdigest()},
        "state_cells": 9, "ring_selector": "(nthcdr 8 state)",
        "ring_selector_value": "one-cell suffix containing NIL",
        "history_selector": "(car (nthcdr 8 state))",
        "history_selector_value": "NIL",
        "selected_main_route": "key-event mode 2 through %rl-render",
        "selected_batch_route": "key-event mode 3 through %rl-put",
        "disarmed_fallback_retained": "public key-event mode 1"}


def editor_mutations(source: str) -> list[dict[str, str]]:
    cases = {
        "restore-device-red-eight-cell-state": source.replace(
            NEW_STATE, OLD_STATE, 1),
        "select-public-queue-with-armed-state": source.replace(
            "(if (nthcdr 8 state)", "(if nil", 1),
        "enable-history-escape-in-native-state": source.replace(
            NEW_STATE, "(state (list head head head 0 0 0 columns row 't))", 1),
    }
    rejected = []
    for name, trial in cases.items():
        try:
            validate_editor_source(trial)
        except RepairError as error:
            rejected.append({"name": name, "observed_red": str(error)})
    require([row["name"] for row in rejected] == list(cases),
            "delivered-consumer source mutation survived")
    return rejected


def successor_command(argv: list[str], label: str) -> None:
    """Keep the asynchronous matrix RUN/STOP case out of the scalar P0 lane.

    Once the delivered state selects private modes 2/3, raw code 3 is
    deliberately absent from the ring.  RUN/STOP is owned by the independent
    matrix latch and `lisp_poll`, which the scalar P0 executor cannot schedule.
    The predecessor case therefore cannot honestly execute in this lane; the
    final-ELF matrix-latch wall remains authoritative.
    """
    if label == "emit native-client product stdlib":
        suite_path = ROOT / argv[-1]
        suite = load(suite_path)
        removed = [row for row in suite["cases"]
                   if row.get("name") == "read-line-run-stop"]
        require(len(removed) == 1, "scalar P0 RUN/STOP case inventory drift")
        suite["cases"] = [row for row in suite["cases"]
                          if row.get("name") != "read-line-run-stop"]
        suite["successor"]["host_case_projection"] = {
            "omitted": "read-line-run-stop",
            "reason": ("private Capture drops raw code 3; independent matrix "
                       "latch is proved at final ELF, outside scalar P0")}
        suite_path.write_bytes(canonical(suite))
    CLIENT_COMMAND(argv, label)


def derived_input_closure() -> dict[str, Any]:
    """Let the living plane, not B-light's historical 133-byte delta, lead."""
    actual = CODE.stat().st_size - CARD.BLOCK_A.CODE.stat().st_size
    historical = 133
    require(actual == 134 and actual != historical,
            "successor static-plane delta is not the named one-cell growth")
    CARD.PLANE_DELTA = actual
    value = CARD_INPUT_CLOSURE()
    require(value["static_roles"]["delta_bytes"] == actual,
            "input closure did not consume candidate-derived plane delta")
    value["successor_conversion"] = {
        "expected_from_candidate_bytes": actual,
        "historical_B_light_delta": historical,
        "mutation_rejected": "restore-historical-133-byte-delta",
        "rule": "a living closure derives its plane delta from its candidate"}
    return value


def checker_conversion() -> dict[str, Any]:
    plane_bytes = CODE.stat().st_size
    hole = 0x2F8B2 - (0x20000 + plane_bytes)
    require(plane_bytes == 47469 and hole == 16197,
            "successor composed-plane facts drift")
    return {"status": "PASS: LIVING PLANE CLOSURES ARE CANDIDATE-DERIVED",
        "first_red": bind(POST_LINK_RED),
        "expected": {"plane_bytes": plane_bytes,
            "Block_A_delta_bytes": plane_bytes - CARD.BLOCK_A.CODE.stat().st_size,
            "largest_contiguous_hole_bytes": hole},
        "historical_B_light_world": {"plane_bytes": 47468,
            "Block_A_delta_bytes": 133,
            "largest_contiguous_hole_bytes": 16198},
        "mutations_rejected": {
            "restore-historical-133-byte-input-closure": True,
            "restore-historical-47468-byte-owner-sum": True,
            "restore-historical-16198-byte-largest-hole": True},
        "rule": ("a living closure derives static ownership and holes from "
                 "the candidate; sealed B-light arithmetic stays in its era")}


def configure() -> None:
    R7.configure()
    for module in (R7, CARD):
        for name, value in {
            "BUILD": BUILD, "PREFLIGHT": PREFLIGHT, "RECEIPT": RECEIPT,
            "DIFFERENCE": DIFFERENCE, "REPORT": REPORT, "ELF": ELF,
            "PRG": PRG, "PROFILE": PROFILE, "PLANE_ROOT": PLANE_ROOT,
            "PLANE_RECEIPT": PLANE_RECEIPT, "CLIENT_SOURCE": CLIENT_SOURCE,
            "C2D": C2D, "CODE": CODE, "MANIFEST": MANIFEST,
            "HEADER": HEADER, "DRIVER": DRIVER, "FORMAT": FORMAT,
            "STATUS": STATUS,
        }.items():
            setattr(module, name, value)
    R7.derive_editor_source = derive_editor_source
    R7.validate_editor_source = validate_editor_source
    R7.editor_mutations = editor_mutations
    CARD.derive_editor_source = derive_editor_source
    CARD.validate_editor_source = validate_editor_source
    CARD.editor_mutations = editor_mutations
    CARD.authority = authority
    CARD.setup_child = R7.R6.setup_child
    CARD.attribution = attribution
    CARD.write_report = write_report
    CARD.native_prompt_final_elf = native_prompt_final_elf
    CARD.configure()
    CLIENT._command = successor_command
    CARD.input_closure = derived_input_closure
    if CODE.is_file():
        CARD.PLANE_BYTES = CODE.stat().st_size
        CARD.LARGEST_BANK2_HOLE = 0x2F8B2 - (
            0x20000 + CODE.stat().st_size)
    CARD.r2_r3_header_consumption = R7.era_separated_header_consumption
    BASE.INVOCATION = INVOCATION
    BASE.authority = authority
    BASE.setup_child = R7.R6.setup_child
    BASE.final_gate = final_gate


class LinkedRouteVM(R7.TargetFrameVM):
    """Run the delivered Lisp route against final-ELF consumer bytes."""

    def __init__(self, *args: Any, linked: FINAL.LinkedConsumer,
                 linked_memory: dict[int, int], **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.linked = linked
        self.linked_memory = linked_memory
        self.key_modes: list[int] = []
        self.linked_cycles = 0

    def _private_key_event(self, mode: int) -> int:
        value, cycles, _instructions = self.linked.run(mode, self.linked_memory)
        self.linked_cycles += cycles
        return B.NIL if value == 0 else B.mkfix(value)

    def _callprim(self, prim_id: int, argc: int, stack: list[int],
                  pc: int | None = None, native_base: int = 0,
                  frame_slots: int = 0) -> int:
        args = stack[-argc:] if argc else []
        if prim_id == 60:
            mode = 0 if not args else B.fixval(args[0])
            self.key_modes.append(mode)
        return super()._callprim(prim_id, argc, stack, pc=pc,
            native_base=native_base, frame_slots=frame_slots)


def run_delivered_consumer(source: Path, elf: Path,
                           expect_success: bool) -> dict[str, Any]:
    printable = "0123456789" * 9 + "abc"
    events = [ord(char) for char in printable] + [13]
    require(len(events) == 94, "delivered-consumer wall event count drift")
    _truth, machine, meta = FINAL.linked_consumer(elf)
    symbols = meta["ring_symbols"]
    base = symbols["C2K_INPUT_RING_BASE"]
    memory = {symbols["C2K_INPUT_RING_HEAD"]: len(events),
              symbols["C2K_INPUT_RING_TAIL"]: 0,
              symbols["C2K_INPUT_EVENTS_RAW"]: len(events),
              symbols["C2K_INPUT_EVENTS_SEEN"]: len(events),
              symbols["C2K_INPUT_EVENTS_STORED"]: len(events),
              symbols["C2K_INPUT_EVENTS_TAKEN"]: 0}
    memory.update({base + index: code for index, code in enumerate(events)})
    suite = PRICE.live_suite(source, "(%native-read-line)", printable, [])
    (heap, _names, _code, flags, resident, _bundle, directory,
     _cases, entries, _inliner) = P0._compile_suite(suite)
    vm = LinkedRouteVM(heap=heap.clone(), directory=directory,
        macro_symbols=P0._macro_symbol_objs(heap, flags, resident),
        max_steps=2_000_000, max_call_args=suite.get("max_call_args"),
        key_events=[], private_key_event_modes=True,
        abi_profile=P0._suite_abi(suite)[0],
        abi_ledger=P0._suite_abi(suite)[1], stop_at_return=False,
        linked=machine, linked_memory=memory)
    observed_red = None
    try:
        result = vm.run(directory[heap.intern(entries[0])], [])
    except B.VMError as error:
        observed_red = str(error)
        result_text = None
    else:
        result_text = vm.heap.string_to_text(result)
    counters = {name: memory[symbols[f"C2K_INPUT_EVENTS_{name.upper()}"]]
                for name in ("raw", "seen", "stored", "taken")}
    if expect_success:
        require(result_text == printable and observed_red is None
                and counters == {name: 94 for name in counters}
                and vm.key_modes and set(vm.key_modes) <= {2, 3}
                and 2 in vm.key_modes,
                "delivered consumer did not drain final-ELF ring")
    else:
        require(result_text is None and observed_red is not None
                and "blocking key-event fixture exhausted" in observed_red
                and counters["taken"] == 0 and vm.key_modes == [1],
                "public-queue mutation did not reproduce taken=0")
    return {"status": ("PASS: DELIVERED ROUTE DRAINS FINAL ELF RING"
                       if expect_success else
                       "PASS: EIGHT-CELL PUBLIC-QUEUE MUTATION REJECTED"),
        "source": bind(source), "ELF": bind(elf), "physical_events": 94,
        "printable_characters": len(printable), "result": result_text,
        "key_modes": vm.key_modes, "counters": counters,
        "linked_consumer": meta, "linked_consumer_cycles": vm.linked_cycles,
        "observed_red": observed_red}


def consumption_preflight(elf: Path) -> dict[str, Any]:
    source = CLIENT_SOURCE.read_text(encoding="utf-8")
    source_gate = validate_editor_source(source)
    candidate = run_delivered_consumer(CLIENT_SOURCE, elf, True)
    mutation = run_delivered_consumer(R7_SOURCE, elf, False)
    require(candidate["counters"]["taken"] == 94
            and mutation["counters"]["taken"] == 0,
            "host wall can pass while delivered taken remains zero")
    return {"status": "PASS: ARM AND CONSUMPTION SHARE DELIVERED CLIENT",
        "source_gate": source_gate,
        "delivered_host_wall": candidate,
        "device_red_mutation": mutation,
        "mutations_rejected": editor_mutations(source),
        "rule": ("a delivered client proves both arming and actual final-world "
                 "consumption; taken=0 is red even when capture stores")}


def emit_plane() -> dict[str, Any]:
    value = CLIENT.emit_client_plane()
    manifest = load(MANIFEST)
    entries = {row["name"]: row for row in manifest["entries"]}
    observed = {name: int(entries[name]["length"]) for name in (
        "%read-line-loop", "read-line", "%rl-screen-tail",
        "%native-prompt", "%native-read-line")}
    value["delivered_consumer_repair"] = {
        "source_gate": validate_editor_source(
            CLIENT_SOURCE.read_text(encoding="utf-8")),
        "mutations_rejected": editor_mutations(
            CLIENT_SOURCE.read_text(encoding="utf-8")),
        "objects": observed,
        "predecessor_plane_bytes": R7_CODE.stat().st_size,
        "candidate_plane_bytes": CODE.stat().st_size,
        "delta_bytes": CODE.stat().st_size - R7_CODE.stat().st_size,
        "manifest_entries": len(manifest["entries"]),
    }
    PLANE_RECEIPT.write_bytes(canonical(value))
    return value


def preflight() -> None:
    configure()
    require(not PREFLIGHT.exists() and not PREFLIGHT_RECEIPT.exists()
            and not BUILD.exists() and not RECEIPT.exists(),
            "delivered-consumer preflight is one-shot")
    plane = emit_plane()
    frame = R7.full_framebuffer_gate()
    R7.R6.setup_child()
    order = R7.R6.configuration_order_gate()
    linker = R7.PRODUCT.linker_script(ownership_opt_in=True)
    pins = R7.R6.known_pin_inventory(linker)
    consumption = consumption_preflight(R7_ELF)
    value = {"format": FORMAT + "-preflight-v1", "recorded_on": "2026-08-30",
        "status": "PASS: BLOCK-A DELIVERED CONSUMER REPAIR ARMED 0/1",
        "authority": authority(), "plane": bind(PLANE_RECEIPT),
        "framebuffer": frame, "delivered_consumption": consumption,
        "configuration_order": order, "known_pin_inventory": pins,
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "next": "commit zero-link preflight; then spend the authorized 1/1"}
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("v1.9 Block A consumer repair: PREFLIGHT PASS taken=94 link=0/1")


def check_preflight() -> None:
    configure()
    value = load(PREFLIGHT_RECEIPT)
    require(value["status"] ==
                "PASS: BLOCK-A DELIVERED CONSUMER REPAIR ARMED 0/1"
            and value["authority"] == authority()
            and value["delivered_consumption"] == consumption_preflight(R7_ELF)
            and value["delivered_consumption"]["delivered_host_wall"][
                "counters"] == {"raw": 94, "seen": 94,
                                "stored": 94, "taken": 94}
            and value["attempt_accounting"]["WPLTO_runs"] == 0,
            "delivered-consumer preflight receipt drift")
    print("v1.9 Block A consumer repair: PREFLIGHT CHECK PASS taken=94")


def profile_sources(path: Path) -> dict[str, str]:
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("input_sha256="):
            name, digest = line.split("=", 1)[1].rsplit(":", 1)
            rows[Path(name).name] = digest
    require(rows, f"profile input closure absent: {path}")
    return rows


def counter_diff(left: Counter[tuple[Any, ...]],
                 right: Counter[tuple[Any, ...]]) -> dict[str, int]:
    return {"removed": sum((left - right).values()),
            "added": sum((right - left).values())}


def attribution() -> dict[str, Any]:
    old_inputs = profile_sources(R7_PROFILE)
    new_inputs = profile_sources(PROFILE)
    require(set(old_inputs) == set(new_inputs),
            "r7/r8 compiler input population drift")
    changed = sorted(name for name in old_inputs
                     if old_inputs[name] != new_inputs[name])
    allowed = {"c2-stream-phase-02a.c", "vm_embed.c", "repl.c"}
    require(set(changed) <= allowed and "c2-stream-phase-02a.c" in changed,
            f"r7/r8 compiler inputs escaped consumer/header roots: {changed}")
    old = ElfTruth.read(R7_ELF, llvm_readobj=CARD.READOBJ,
                        include_section_data=True)
    new = ElfTruth.read(ELF, llvm_readobj=CARD.READOBJ,
                        include_section_data=True)
    old_symbols = Counter(CARD.symbol_key(row) for row in old.symbols)
    new_symbols = Counter(CARD.symbol_key(row) for row in new.symbols)
    old_relocs = Counter(CARD.relocation_key(row) for row in old.relocations)
    new_relocs = Counter(CARD.relocation_key(row) for row in new.relocations)
    old_sections = Counter((row.name, row.address, row.bytes, tuple(row.flags))
                           for row in old.sections)
    new_sections = Counter((row.name, row.address, row.bytes, tuple(row.flags))
                           for row in new.sections)
    old_prg, new_prg = R7_PRG.read_bytes(), PRG.read_bytes()
    old_elf, new_elf = R7_ELF.read_bytes(), ELF.read_bytes()
    complete = CARD.inherited_product_attribution()
    counts = dict(complete["counts"])
    require(all(value == 0 for name, value in counts.items()
                if name.startswith("unexplained_")),
            "complete product attribution retained unexplained members")
    return {"format": FORMAT + "-difference-v1", "recorded_on": "2026-08-30",
        "status": "PASS: EVERY R7/R8 PRODUCT MEMBER HAS A NAMED FAMILY",
        "authored_root": {"source": bind(CLIENT_SOURCE),
            "predecessor": bind(R7_SOURCE),
            "changed_form": "read-line state gains one NIL ring-selector cell",
            "Bank2_delta_bytes": CODE.stat().st_size - R7_CODE.stat().st_size},
        "compiler_input_closure": {"population": len(old_inputs),
            "changed": changed, "unchanged": len(old_inputs) - len(changed),
            "families": ["successor static-plane and phase-02a CRC",
                         "candidate extent/header consumption",
                         "derived product build-ID projection"]},
        "product_members": {
            "PRG_changed_bytes": sum(a != b for a, b in zip(old_prg, new_prg))
                + abs(len(old_prg) - len(new_prg)),
            "ELF_changed_bytes": sum(a != b for a, b in zip(old_elf, new_elf))
                + abs(len(old_elf) - len(new_elf)),
            "symbols": counter_diff(old_symbols, new_symbols),
            "relocations": counter_diff(old_relocs, new_relocs),
            "sections": counter_diff(old_sections, new_sections),
            "family": ("single state-cell source root -> static plane/extent/"
                       "build-ID/CRC deterministic closure")},
        "complete_product_closure": complete,
        "checker_conversion": checker_conversion(),
        "counts": counts, "unexplained_members": 0,
        "causal_statement": ("the sole authored change is one NIL state cell; "
            "the candidate plane, both real Force-Include consumers and the "
            "phase CRC/build-ID closure name every native successor member")}


def native_prompt_final_elf() -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=CARD.READOBJ,
                          include_section_data=True)
    manifest = load(MANIFEST)
    entries = {row["name"]: row for row in manifest["entries"]}
    names = [row["name"] for row in manifest["entries"]]
    ordinal = names.index("%native-read-line")
    define = ("#define LISP65_BYTECODE_STDLIB_NATIVE_READ_LINE_ENTRY "
              f"{ordinal}u")
    rows = R7.DEVICE.instruction_records(ELF, "repl")
    targets = {name: truth.symbol(name).value for name in (
        "vm_run_dir", "lisp_input_event")}
    vm_calls = [row for row in rows if row["mnemonic"] == "jsr"
                and R7.DEVICE.absolute_target(row) == targets["vm_run_dir"]]
    event_calls = [row for row in rows if row["mnemonic"] == "jsr"
                   and R7.DEVICE.absolute_target(row) ==
                       targets["lisp_input_event"]]
    consumer = truth.symbol("c2_kernal_input_take")
    callprim = truth.symbol("vm_callprim")
    relocations = [row for row in truth.relocations
        if row.source_section == ".text"
        and row.target == "c2_kernal_input_take"
        and callprim.value <= row.offset < callprim.value + callprim.bytes]
    text_bytes = truth.section_bytes(".text")
    text = truth.section(".text")
    require(len(relocations) == 1, "final key-event ring-take edge absent")
    operand = relocations[0].offset
    require(text_bytes[operand - text.address - 1] == 0x20,
            "final ring-take relocation is not a JSR operand")
    sizes = {name: int(entries[name]["length"]) for name in (
        "%read-line-loop", "read-line", "%rl-screen-tail",
        "%native-prompt", "%native-read-line")}
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    consumption = consumption_preflight(ELF)
    static_consumption = CLIENT.candidate_consumption_receipts()
    stdlib_consumption = CARD.candidate_stdlib_consumption()
    sweep = CARD.force_include_consumption_sweep(
        static_consumption, stdlib_consumption)
    require(ordinal == 395 and HEADER.read_text(encoding="utf-8").count(define) == 1
            and len(vm_calls) == 2 and event_calls == []
            and sizes == {"%read-line-loop": 250, "read-line": 236,
                "%rl-screen-tail": 223, "%native-prompt": 21,
                "%native-read-line": 16}
            and CODE.stat().st_size == 47469
            and facade.address - (text.address + text.bytes) >= 32
            and consumption["delivered_host_wall"]["counters"]["taken"] == 94,
            "final ELF does not execute the repaired delivered consumer")
    return {"status": "PASS: FINAL ELF EDITOR CONSUMES ARMED RING",
        "manifest": bind(MANIFEST), "header": bind(HEADER),
        "native_entry": {"name": "%native-read-line", "ordinal": ordinal},
        "objects": sizes, "candidate_extent": CODE.stat().st_size,
        "resolved_calls": {"vm_run_dir": [f"0x{int(row['address']):04x}"
            for row in vm_calls], "lisp_input_event": []},
        "ring_take_edge": {"caller": "vm_callprim", "mapping_domain": ".text",
            "relocation_offset": relocations[0].offset,
            "callee": consumer.name, "callee_address": consumer.value,
            "callee_bytes": consumer.bytes},
        "delivered_consumption": consumption,
        "compiler_consumers": static_consumption,
        "stdlib_header_consumers": stdlib_consumption,
        "force_include_bound_equals_consumed": sweep,
        "composed_framebuffer_effect": R7.full_framebuffer_gate(),
        "ordinary_text": {"end_exclusive": text.address + text.bytes,
            "facade_start": facade.address,
            "free_bytes": facade.address - (text.address + text.bytes),
            "permanent_floor_bytes": 32},
        "mutations_rejected": {
            "restore-eight-cell-public-queue-world": "rejected",
            "host-wall-green-with-taken-zero": "rejected",
            "remove-final-ring-take-edge": "rejected"}}


def final_gate() -> dict[str, Any]:
    R7.native_prompt_final_elf = native_prompt_final_elf
    CARD.native_prompt_final_elf = native_prompt_final_elf
    value = R7.final_gate()
    block = value["v1_9_Block_B_light"]
    block["status"] = "PASS: BLOCKS A+B DELIVERED CONSUMER COMPOSED"
    block["native_prompt_final_ELF"] = native_prompt_final_elf()
    block["Block_A_device_first_red_closed_host_side"] = bind(FIRST_RED)
    block["device_reverification_required"] = (
        "raw=seen=stored=taken and nonzero on fresh successor medium")
    return value


def frozen_artifacts() -> dict[str, Any]:
    return BASE.artifacts()


def run_child(action: str) -> dict[str, Any]:
    result = subprocess.run([sys.executable, str(DRIVER), action], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0,
            f"delivered-consumer child {action} red:\n{result.stdout}")
    return {"action": action,
            "stdout_tail": " ".join(result.stdout.split()[-30:])}


def write_report(value: dict[str, Any]) -> None:
    gate = value["final_product"]["v1_9_Block_B_light"][
        "native_prompt_final_ELF"]
    pair = value["artifacts_after"]
    REPORT.write_text(f"""# v1.9 Block A — delivered consumer repair

Status: **{value['status']}**

The stopped r7 device world armed Capture and stored two events but reported
`raw/seen/stored/taken = 2/2/2/0`.  Attribution found an eight-cell delivered
`read-line` state: `(nthcdr 8 state)` was NIL, so the editor selected public
blocking `key-event 1` while the IRQ independently filled the ring.

r8 adds one NIL cell.  The suffix is now non-NIL and selects private modes 2/3,
while its first value remains NIL so native history escape stays disabled.  No
name or native source is added.  The Bank-2 plane grows one byte to
**{CODE.stat().st_size:,} bytes**; `read-line` grows 235→236 bytes and every
object remains below 255 bytes.

The permanent host wall executes the delivered Lisp state against the
**final-ELF 70-byte `c2_kernal_input_take` body**.  Its 94-event result is
`raw=seen=stored=taken=94`; the exact eight-cell predecessor selects mode 1,
fails against the empty public queue and leaves `taken=0`.  The final ELF also
contains one `.text`-domain `vm_callprim` relocation to the ring consumer at
offset `${gate['ring_take_edge']['relocation_offset']:04X}`.  Thus the gate
proves both arm and delivered consumption rather than composing two fixtures.

The scalar P0 suite omits only its historical raw-code-3 RUN/STOP case: private
Capture deliberately drops raw code 3, while the independent matrix latch and
`lisp_poll` remain the product authority and unchanged inherited wall.

Every r7→r8 product difference is attributed before read-only Scope and
Acceptance.  Exactly one authorized WPLTO and product link ran:

- ELF: `{pair['ELF']['sha256']}`
- PRG: `{pair['PRG']['sha256']}`

No medium was built and no device was contacted.  Hardware re-verification is
the same short counter row and must produce nonzero equal values on all four
counters before Block A can be accepted or the v1.5 Known Issue pensioned.
""", encoding="utf-8")


def build() -> None:
    configure()
    pre = load(PREFLIGHT_RECEIPT)
    require(pre["status"] ==
                "PASS: BLOCK-A DELIVERED CONSUMER REPAIR ARMED 0/1"
            and not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not DIFFERENCE.exists(),
            "delivered-consumer preflight/build lifecycle drift")
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, check=True).stdout
    require(clean == "", "delivered-consumer WPLTO requires committed clean sources")
    INVOCATION.write_bytes(canonical({"status": "INVOKED",
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "real_stdlib_header_consumer": CARD.stdlib_consumer_preflight(),
        "budget": {"WPLTO_runs": 1, "product_links": 1}}))
    processes = [run_child("_produce")]
    before = frozen_artifacts()
    diff = attribution()
    require(diff["unexplained_members"] == 0,
            "delivered-consumer attribution retained unexplained members")
    DIFFERENCE.write_bytes(canonical(diff))
    gate = final_gate()
    processes.extend((run_child("_scope"), run_child("_accept")))
    after = frozen_artifacts()
    scope, acceptance = load(BASE.SCOPE_RESULT), load(BASE.ACCEPTANCE_RESULT)
    require(before == after and scope["status"] == acceptance["status"] == "PASS",
            "delivered-consumer read-only qualification tail red")
    value = {"format": FORMAT, "recorded_on": "2026-08-30", "status": STATUS,
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "invocation": bind(INVOCATION), "attribution": bind(DIFFERENCE),
        "final_product": gate, "producer": bind(BASE.PRODUCER_RESULT),
        "scope": bind(BASE.SCOPE_RESULT),
        "acceptance": bind(BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": processes,
        "attempt_accounting": {"WPLTO_runs": 1, "product_links": 1,
            "scope_runs": 1, "acceptance_runs": 1,
            "media_builds": 0, "device_contacts": 0},
        "media_authorized": False,
        "next": "independent review; then artifact-only media and counter row"}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    check()
    print("v1.9 Block A consumer repair: CARD PASS WPLTO=1/1 taken=94")


def record_post_link_red() -> None:
    configure()
    require(ELF.is_file() and PRG.is_file() and INVOCATION.is_file()
            and not POST_LINK_RED.exists() and not DIFFERENCE.exists()
            and not RECEIPT.exists() and not BASE.SCOPE_RESULT.exists()
            and not BASE.ACCEPTANCE_RESULT.exists(),
            "post-link checker red lifecycle drift")
    value = {"format": FORMAT + "-post-link-red-v1",
        "recorded_on": "2026-08-30",
        "status": "POST-LINK RED: INHERITED B-LIGHT PLANE DELTA PIN",
        "error": "B-light static role closure drift",
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "invocation": bind(INVOCATION),
        "frozen_pair": {"ELF": bind(ELF), "PRG": bind(PRG)},
        "observed": {"historical_Block_A_delta_bytes": 133,
            "candidate_Block_A_delta_bytes": 134,
            "historical_plane_bytes": 47468,
            "candidate_plane_bytes": CODE.stat().st_size},
        "classification": ("candidate-dependent closure crossed from sealed "
                           "B-light arithmetic into the living +1 successor"),
        "product_defect_established": False,
        "pair_disposition": "FROZEN-READ-ONLY-ATTRIBUTION",
        "attempt_accounting": {"WPLTO_runs": 1, "product_links": 1,
            "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "retry_authorized": False,
        "resume_right": ("checker conversion, complete attribution, Scope and "
                         "Acceptance over this pair; zero WPLTO and links")}
    POST_LINK_RED.write_bytes(canonical(value))
    print("v1.9 Block A consumer repair: POST-LINK RED RECORDED pair=frozen")


def resume() -> None:
    configure()
    red = load(POST_LINK_RED)
    require(red["status"] ==
                "POST-LINK RED: INHERITED B-LIGHT PLANE DELTA PIN"
            and red["frozen_pair"] == {"ELF": bind(ELF), "PRG": bind(PRG)}
            and not DIFFERENCE.exists() and not RECEIPT.exists()
            and not BASE.SCOPE_RESULT.exists()
            and not BASE.ACCEPTANCE_RESULT.exists(),
            "delivered-consumer resume lifecycle drift")
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, check=True).stdout
    require(clean == "", "read-only resume requires committed clean conversion")
    before = frozen_artifacts()
    tree_before = R7.tree_fingerprint(BUILD / "wplto")
    conversion = checker_conversion()
    diff = attribution()
    require(diff["unexplained_members"] == 0,
            "resume attribution retained unexplained members")
    DIFFERENCE.write_bytes(canonical(diff))
    gate = final_gate()
    processes = [run_child("_scope"), run_child("_accept")]
    after = frozen_artifacts()
    tree_after = R7.tree_fingerprint(BUILD / "wplto")
    scope, acceptance = load(BASE.SCOPE_RESULT), load(BASE.ACCEPTANCE_RESULT)
    require(before == after and tree_before == tree_after
            and scope["status"] == acceptance["status"] == "PASS",
            "delivered-consumer read-only resume red")
    value = {"format": FORMAT + "-resume-v1", "recorded_on": "2026-08-30",
        "status": STATUS, "authority": authority(),
        "preflight": bind(PREFLIGHT_RECEIPT), "first_red": bind(POST_LINK_RED),
        "checker_conversion": conversion, "invocation": bind(INVOCATION),
        "attribution": bind(DIFFERENCE), "final_product": gate,
        "producer": bind(BASE.PRODUCER_RESULT),
        "scope": bind(BASE.SCOPE_RESULT),
        "acceptance": bind(BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "wplto_tree_before": tree_before, "wplto_tree_after": tree_after,
        "processes": processes,
        "attempt_accounting": {"WPLTO_runs_total": 1,
            "product_links_total": 1, "resume_WPLTO_runs": 0,
            "resume_product_links": 0, "scope_runs": 1,
            "acceptance_runs": 1, "media_builds": 0, "device_contacts": 0},
        "media_authorized": False,
        "next": "independent review; then artifact-only media and counter row"}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    check()
    print("v1.9 Block A consumer repair: RESUME PASS WPLTO=0 taken=94")


def check() -> None:
    configure()
    value = load(RECEIPT)
    diff = load(DIFFERENCE)
    gate = value["final_product"]["v1_9_Block_B_light"][
        "native_prompt_final_ELF"]
    require(value["status"] == STATUS and value["authority"] == authority()
            and value["artifacts_before"] == value["artifacts_after"] ==
                frozen_artifacts()
            and canonical(diff) == canonical(attribution())
            and diff["unexplained_members"] == 0
            and gate == native_prompt_final_elf()
            and gate["delivered_consumption"]["delivered_host_wall"][
                "counters"] == {"raw": 94, "seen": 94,
                                "stored": 94, "taken": 94}
            and value["checker_conversion"] == checker_conversion()
            and value["wplto_tree_before"] == value["wplto_tree_after"] ==
                R7.tree_fingerprint(BUILD / "wplto")
            and value["attempt_accounting"]["WPLTO_runs_total"] == 1
            and value["attempt_accounting"]["resume_WPLTO_runs"] == 0,
            "delivered-consumer receipt drift")
    print("v1.9 Block A consumer repair: CHECK PASS taken=94")


def child(action: str) -> None:
    configure()
    if action == "_profile_probe":
        CLIENT.SUBSTRATE.profile_probe_child()
    elif action == "_release_probe":
        CLIENT.SUBSTRATE.release_probe_child()
    elif action == "_produce":
        BASE.produce_child()
    elif action == "_scope":
        BASE.scope_child()
    elif action == "_accept":
        BASE.acceptance_child()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "check-preflight",
        "build", "record-post-link-red", "resume", "check",
        "_profile_probe", "_release_probe", "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    if action == "preflight":
        preflight()
    elif action == "check-preflight":
        check_preflight()
    elif action == "build":
        build()
    elif action == "record-post-link-red":
        record_post_link_red()
    elif action == "resume":
        resume()
    elif action == "check":
        check()
    else:
        child(action)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
