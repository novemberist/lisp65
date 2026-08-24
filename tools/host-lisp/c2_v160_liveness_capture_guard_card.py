#!/usr/bin/env python3
"""Run the released active-candidate Capture-guard liveness card."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_v160_abort_driver_relocation as R1_GATE  # noqa: E402
import c2_v160_input_fidelity_reopen_card as REOPEN  # noqa: E402
import c2_v160_liveness_fix_scope_floor_card as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-liveness-capture-guard-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-liveness-capture-guard-preflight"
PROCESS = ROOT / "build/c2.3/v1.6-liveness-capture-guard-process"
NORMAL_BUILD = PROCESS / "normal-build"; NORMAL_PREFLIGHT = PROCESS / "normal-preflight"
MUTANT_BUILD = PROCESS / "mutant-build"; MUTANT_PREFLIGHT = PROCESS / "mutant-preflight"
PRODUCT_ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
RECEIPT = ARCH / "c2.3-v1.6-liveness-capture-guard-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-liveness-capture-guard-card-final-red.json"
IMMEDIATE_RED = ARCH / "c2.3-v1.6-liveness-fix-scope-floor-card-final-red.json"
ATTRIBUTION = ARCH / "c2.3-v1.6-liveness-capture-successor-pin-attribution.json"
FROZEN_ELF = (ROOT / "build/c2.3/v1.6-liveness-fix-scope-floor-card/wplto/"
              "lisp65-c2-substitution-linked.prg.elf")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "2fe067ab"
FORMAT = "lisp65-c2-v160-liveness-capture-guard-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 LIVENESS CAPTURE GUARD ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 RETIREMENT LIVENESS FIX FINAL WORLD GREEN"
TAG = "retirement-liveness-capture-guard"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    commit = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("exactly one card", "active final candidate", "abort body 134",
                  "facade exactly 98", "abort entry 9", "1,499-byte arena",
                  "never an equality"):
        require(token in text, f"capture-guard authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    red = load(IMMEDIATE_RED); attribution = load(ATTRIBUTION)
    require(red["error"]["message"] ==
                "post-R1 capture changed abort/facade contracts"
            and red["attempt_accounting"]["cards_consumed"] == 1
            and red["attempt_accounting"]["WPLTO_runs"] == 1
            and red["retry_authorized"] is False
            and attribution["status"] ==
                "ATTRIBUTED: CAPTURE GUARD STORED R1 WORLD REJECTED LIVENESS SUCCESSOR"
            and attribution["candidate_world"]["service_bytes"] == 1425
            and attribution["candidate_world"]["padding_bytes"] == 0,
            "capture-guard predecessor drift")
    return {"Final_Red": red, "attribution": attribution}


def _facade_members(truth: ElfTruth) -> tuple[dict[str, Any], ...]:
    facade = truth.section(R1_GATE.FACADE_SECTION)
    members = sorted((row for row in truth.symbols
        if row.section == facade.name and row.symbol_type == "Function"
        and row.bytes > 0), key=lambda row: (row.value, row.name))
    require(members and members[0].value == facade.address
            and members[-1].value + members[-1].bytes == facade.address + facade.bytes,
            "active facade membership does not span the fixed facade")
    cursor = facade.address
    result: list[dict[str, Any]] = []
    for row in members:
        require(row.value == cursor, "active facade membership has overlap or a hole")
        result.append({"name": row.name, "address": row.value, "bytes": row.bytes})
        cursor += row.bytes
    require(cursor == facade.address + facade.bytes,
            "active facade membership does not own every facade byte")
    return tuple(result)


def active_capture_successor_gate(elf: Path, *, arena: int = 1499,
        claimed_members: Iterable[str] | None = None,
        legacy_equalities: tuple[int, int] | None = None) -> dict[str, Any]:
    """Validate fixed contracts while deriving freight from the final ELF."""
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    service = truth.section(R1_GATE.FAR)
    facade = truth.section(R1_GATE.FACADE_SECTION)
    abort = truth.symbol("c2_abort_driver")
    abort_entry = truth.symbol("c2_abort_driver_facade")
    padding = truth.symbol("__lisp65_c2_mapped_far_facade_padding")
    members = _facade_members(truth)
    member_names = tuple(row["name"] for row in members)
    claims = tuple(member_names if claimed_members is None else claimed_members)

    require(abort.section == R1_GATE.FAR and abort.bytes == 134
            and facade.bytes == 98 and abort_entry.bytes == 9,
            "active candidate changed a fixed abort/facade contract")
    require(set(claims) == set(member_names) and len(claims) == len(member_names),
            "facade claim contains a member outside active candidate membership")
    require(service.bytes <= arena,
            "active candidate exceeds the mapped Far Service arena")
    if legacy_equalities is not None:
        require((service.bytes, padding.bytes) == legacy_equalities,
                "stored R1 service/padding equality rejected active successor")

    sections = {row.name: row for row in truth.sections}
    require(all(name in sections for name in R1_GATE.CAPTURE_SECTIONS),
            "capture successor omitted a capture section")
    capture_bytes = sum(sections[name].bytes for name in R1_GATE.CAPTURE_SECTIONS)
    allocated_rows = sorted((max(R1_GATE.E000_START, row.address),
        min(R1_GATE.E000_END, row.address + row.bytes))
        for row in truth.sections if row.bytes > 0
        and "SHF_ALLOC" in set(row.flags)
        and row.address < R1_GATE.E000_END
        and row.address + row.bytes > R1_GATE.E000_START)
    allocated: list[tuple[int, int]] = []
    for start, end in allocated_rows:
        if not allocated or start > allocated[-1][1]:
            allocated.append((start, end))
        else:
            allocated[-1] = (allocated[-1][0], max(allocated[-1][1], end))
    free = R1_GATE.E000_END - R1_GATE.E000_START - sum(
        end - start for start, end in allocated)
    require(capture_bytes > 0 and free >= 54,
            "active capture successor exceeds the fixed E000 reserve floor")

    edges = R1_GATE.graph(truth)
    reached = R1_GATE.closure(edges, ["c2_mapped_far_vm_code_load_converged",
                                      "c2_mapped_far_physical_read_converged"])
    forbidden = reached & {"c2_abort_driver", "c2_abort_driver_facade",
        "c2_product_abort_cleanup", "lisp_abort", "lisp_abort_code",
        "lisp_abort_symbol", "lisp_abort_static", "c2_mapped_far_leave"}
    require(not forbidden, "active capture successor invalidated abort closure")
    equates = {}
    for name, expected in R1_GATE.SPLIT_EQUATES.items():
        rows = [row for row in truth.symbols if row.name == name]
        if name == "C2K_INPUT_RING_SLOTS" and \
                "C2K_INPUT_EVENTS_SEEN" in truth.symbols_by_name:
            first_counter = ("C2K_INPUT_EVENTS_RAW"
                if "C2K_INPUT_EVENTS_RAW" in truth.symbols_by_name
                else "C2K_INPUT_EVENTS_SEEN")
            expected = (truth.symbol(first_counter).value
                        - truth.symbol("C2K_INPUT_RING_BASE").value)
        require(len(rows) == 1 and rows[0].value == expected
                and rows[0].section == "Absolute",
                f"active capture equate ownership drift: {name}")
        equates[name] = {"count": 1, "value": expected,
            "authority": ("candidate first-counter boundary minus ring base"
                if name == "C2K_INPUT_RING_SLOTS"
                and "C2K_INPUT_EVENTS_SEEN" in truth.symbols_by_name
                else "fixed split-equate contract")}
    return {"status": "PASS: ACTIVE-CANDIDATE CAPTURE SUCCESSOR CONTRACTS",
        "fixed_contracts": {"abort_body_bytes": abort.bytes,
            "facade_bytes": facade.bytes, "abort_entry_bytes": abort_entry.bytes},
        "derived_freight": {"service_bytes": service.bytes,
            "facade_members": list(members), "padding_bytes": padding.bytes},
        "service_arena": {"capacity_bytes": arena, "used_bytes": service.bytes,
            "free_bytes": arena - service.bytes, "relation": "used <= capacity"},
        "capture_bytes": capture_bytes, "post_capture_free_bytes": free,
        "reserve_floor_bytes": 54, "surplus_over_floor_bytes": free - 54,
        "worst_state_forbidden_reached": sorted(forbidden), "equates": equates}


def mutation_gate(elf: Path) -> dict[str, Any]:
    good = active_capture_successor_gate(elf)
    members = [row["name"] for row in good["derived_freight"]["facade_members"]]
    rejected: list[str] = []
    for name, call in (
        ("stored-1382-10-equality", lambda: active_capture_successor_gate(
            elf, legacy_equalities=(1382, 10))),
        ("facade-outsider", lambda: active_capture_successor_gate(
            elf, claimed_members=(*members, "c2_unowned_facade_member"))),
        ("arena-overflow", lambda: active_capture_successor_gate(
            elf, arena=good["derived_freight"]["service_bytes"] - 1))):
        try:
            call()
        except RuntimeError:
            rejected.append(name)
    equality_boundary = active_capture_successor_gate(
        elf, arena=good["derived_freight"]["service_bytes"])
    require(rejected == ["stored-1382-10-equality", "facade-outsider",
                         "arena-overflow"]
            and equality_boundary["service_arena"]["free_bytes"] == 0,
            "active-candidate capture mutations did not enforce all three walls")
    return {"status": "PASS: ACTIVE-CANDIDATE CAPTURE GUARD MUTATIONS",
        "candidate": good, "mutations_rejected": rejected,
        "arena_equality_boundary_accepted": True,
        "capacity_semantics": "used <= fixed capacity, not used == capacity"}


def configure_module() -> None:
    PREV.BUILD = BUILD; PREV.PREFLIGHT = PREFLIGHT; PREV.PROCESS = PROCESS
    PREV.NORMAL_BUILD = NORMAL_BUILD; PREV.NORMAL_PREFLIGHT = NORMAL_PREFLIGHT
    PREV.MUTANT_BUILD = MUTANT_BUILD; PREV.MUTANT_PREFLIGHT = MUTANT_PREFLIGHT
    PREV.PRODUCT_ELF = PRODUCT_ELF; PREV.RECEIPT = RECEIPT
    PREV.FINAL_RED = FINAL_RED; PREV.DRIVER = DRIVER; PREV.TAG = TAG
    # Preserve the inherited scope/floor layer's own sealed authority and
    # predecessor.  This outer successor validates and binds its immediate
    # predecessor separately; substituting it into the historical layer would
    # make that layer interpret a newer Final Red as its own old witness.
    REOPEN.capture_successor_gate = active_capture_successor_gate


def append(path: Path, gate: dict[str, Any]) -> None:
    value = load(path)
    value.update({"format": FORMAT + ("-preflight" if path.parent == PREFLIGHT else ""),
        "capture_guard_authority": authority(),
        "immediate_Final_Red": bind(IMMEDIATE_RED),
        "capture_guard_attribution": bind(ATTRIBUTION),
        "active_candidate_capture_guard": gate})
    path.write_bytes(canonical(value))


def preflight() -> None:
    predecessor(); authority(); gate = mutation_gate(FROZEN_ELF)
    configure_module(); PREV.preflight(); append(PREFLIGHT / "preflight.json", gate)
    print("v1.6 liveness capture guard: PREFLIGHT PASS card=0/1 mutations=3")


def card() -> None:
    predecessor(); authority(); configure_module(); PREV.card()
    append(RECEIPT, mutation_gate(PRODUCT_ELF))
    print("v1.6 liveness capture guard: CARD PASS card=1/1 final-world=green")


def record_red(error: Exception) -> None:
    configure_module(); PREV.record_red(error)
    if FINAL_RED.exists():
        value = load(FINAL_RED); value.update({"format": FORMAT + "-final-red",
            "status": "FINAL RED: V1.6 LIVENESS CAPTURE GUARD STOPS",
            "capture_guard_authority": authority(),
            "immediate_Final_Red": bind(IMMEDIATE_RED),
            "capture_guard_attribution": bind(ATTRIBUTION),
            "retry_authorized": False, "media_authorized": False,
            "device_contacts": 0})
        FINAL_RED.write_bytes(canonical(value))


def main() -> int:
    choices = ("preflight", "card", "check", "_process_probe",
        "_process_probe_mutant", "_contract_probe", "_contract_probe_mutant",
        "_fold_probe", "_fold_probe_mutant", "_order_probe", "_order_probe_mutant",
        "_real_consumer_probe", "_membership_probe", "_hybrid_profile_probe",
        "_finalize_red", "_dry", "_produce", "_scope", "_accept", "_r1_arm",
        "_owner_graph", "_default_probe", "_full_probe", "_full_probe_mutant")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=choices); action = parser.parse_args().action
    configure_module()
    if action == "preflight": preflight()
    elif action == "card": card()
    elif action == "check":
        value = load(RECEIPT); require(value["status"] == FINAL_STATUS,
            "capture-guard receipt drift")
        print("v1.6 liveness capture guard: CHECK PASS")
    else:
        PREV.main()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_red(error)
            except Exception as receipt_error:
                print(f"capture-guard Final Red failure: {receipt_error}", file=sys.stderr)
        print(f"v1.6 liveness capture guard: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
