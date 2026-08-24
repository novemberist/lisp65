#!/usr/bin/env python3
"""Born-derived E000 tenant inventory and relocation price study.

This is deliberately a desk gate, not a product card.  It reads one bound
candidate ELF, prices a relocation, and emits a receipt.  It never compiles,
links, or writes product sources.
"""

from __future__ import annotations

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

from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
PLACEMENT_RED = ARCH / (
    "c2.3-v1.6-comfort-input-fidelity-placement-first-red-receipt.json")
FINAL_RED = ARCH / (
    "c2.3-v1.6-comfort-input-fidelity-third-replacement-card-final-red.json")
PREFLIGHT = ROOT / (
    "build/c2.3/v1.6-comfort-input-fidelity-third-replacement-card-preflight/"
    "preflight.json")
FLOOR_CONTRACT = ROOT / "config/c2-append-final-hybrid-contract.json"
FAR_CONTRACT = ROOT / "config/c2-mapped-far-full-span-contract-v3.json"
MAP_CONTRACT = ROOT / "config/c2-mapped-far-map-contract-v2.json"
RUNTIME_SOURCE = ROOT / "src/c2_product_runtime.c"
INTERRUPT_SOURCE = ROOT / "src/interrupt.c"
FACADE_SOURCE = ROOT / "src/optional/c2_mapped_far_service_v2.s"
DRIVER = Path(__file__).resolve()
RECEIPT = ARCH / "c2.3-v1.6-e000-relocation-study-receipt.json"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"

AUTHORIZATION = "3772232b"
RECORDED_ON = "2026-08-18"
FORMAT = "lisp65-c2-v160-e000-relocation-study-v1"

ARENA_START = 0xE000
ARENA_END = 0xFF80
ACTIVE_FLOOR = 54
PARKED_CAPTURE_BYTES = 59
REQUIRED_NEW_FREE = 52
FAR_CAPACITY = 1499

FACADE = ".lisp65_c2_mapped_far_facade"
FAR_SERVICE = ".lisp65_c2_mapped_far_service"
GAP1 = ".lisp65_c2_kernal_window.reopen_gap1"
RESIDENT = ".lisp65_c2_kernal_window.c2_resident"


class StudyError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise StudyError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def git_binding(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {
        "authority": "git-blob", "commit": full, "path": name,
        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
    }


def authorization() -> dict[str, Any]:
    row = git_binding(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{row['commit']}:{row['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout.decode()
    compact = " ".join(raw.split()).lower()
    for token in (
            "e000 relocation study commissioned",
            "host-only e000 relocation study",
            "every tenant, size and address comes from elftruth",
            "can at least 52 bytes",
            "no floor change is proposed"):
        require(token in compact, f"study authorization absent: {token}")
    return row


def section_row(section: Any) -> dict[str, Any]:
    return {
        "name": section.name, "vma": section.address,
        "end_exclusive": section.address + section.bytes,
        "bytes": section.bytes,
    }


def function_for_offset(truth: ElfTruth, section: str, offset: int) -> str:
    rows = [s for s in truth.symbols
            if s.section == section and s.symbol_type == "Function"
            and s.bytes > 0 and s.value <= offset < s.value + s.bytes]
    return rows[0].name if len(rows) == 1 else f"{section}+0x{offset:x}"


def edges_for(truth: ElfTruth, symbol: Any) -> tuple[list[dict[str, Any]],
                                                     list[dict[str, Any]]]:
    incoming: list[dict[str, Any]] = []
    outgoing: list[dict[str, Any]] = []
    for relocation in truth.relocations:
        identity = truth.relocation_target_identity(relocation)
        if identity.get("resolved_value") == symbol.value:
            incoming.append({
                "caller": function_for_offset(
                    truth, relocation.source_section, relocation.offset),
                "source_section": relocation.source_section,
                "offset": relocation.offset,
                "type": relocation.relocation_type,
            })
        if (relocation.source_section == symbol.section
                and symbol.value <= relocation.offset
                < symbol.value + symbol.bytes):
            outgoing.append({
                "target": relocation.target,
                "resolved_target": identity.get("resolved_value"),
                "type": relocation.relocation_type,
            })
    return incoming, outgoing


def complement(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    free: list[dict[str, Any]] = []
    cursor = ARENA_START
    for row in rows:
        if cursor < row["vma"]:
            free.append({"start": cursor, "end_exclusive": row["vma"],
                         "bytes": row["vma"] - cursor})
        cursor = max(cursor, row["end_exclusive"])
    if cursor < ARENA_END:
        free.append({"start": cursor, "end_exclusive": ARENA_END,
                     "bytes": ARENA_END - cursor})
    return free


def function_row(truth: ElfTruth, symbol: Any, verdict: str,
                 reason: str, destination: str | None,
                 price: dict[str, Any]) -> dict[str, Any]:
    incoming, outgoing = edges_for(truth, symbol)
    return {
        "name": symbol.name, "kind": "function", "section": symbol.section,
        "vma": symbol.value, "end_exclusive": symbol.value + symbol.bytes,
        "bytes": symbol.bytes, "incoming_edges": len(incoming),
        "outgoing_relocations": len(outgoing), "verdict": verdict,
        "mapped_reason": reason, "destination": destination,
        "move_price": price,
    }


def derive() -> dict[str, Any]:
    placement = load(PLACEMENT_RED)
    candidate_binding = placement["authority"]["candidate_elf"]
    candidate = ROOT / candidate_binding["path"]
    require(bind(candidate) == candidate_binding,
            "bound candidate ELF identity drift")
    truth = ElfTruth.read(candidate, llvm_readobj=READOBJ,
                          include_section_data=True)

    allocated = sorted([
        section_row(s) for s in truth.sections
        if s.bytes > 0 and ARENA_START <= s.address < ARENA_END
    ], key=lambda row: row["vma"])
    expected_names = [
        ".lisp65_c2_kernal_window.typed_queue_driver",
        ".lisp65_c2_kernal_window.irq_handler",
        ".lisp65_c2_kernal_window.nmi_and_freezer_return",
        ".lisp65_c2_kernal_window.map_switch_and_guards",
        ".lisp65_c2_kernal_window.post_startup_output_seam",
        RESIDENT,
        ".lisp65_c2_kernal_window.reopen_gap0",
        ".lisp65_c2_kernal_window.profile_rodata",
        GAP1,
    ]
    require([row["name"] for row in allocated] == expected_names,
            "E000 tenant section inventory drift")
    for left, right in zip(allocated, allocated[1:]):
        require(left["end_exclusive"] <= right["vma"],
                "overlapping E000 tenants")
    free = complement(allocated)
    allocated_bytes = sum(row["bytes"] for row in allocated)
    free_bytes = sum(row["bytes"] for row in free)
    require(allocated_bytes == 8003 and free_bytes == 61
            and [row["bytes"] for row in free] == [36, 25],
            "bound candidate E000 geometry drift")

    functions = sorted([
        s for s in truth.symbols if s.symbol_type == "Function" and s.bytes > 0
        and ARENA_START <= s.value < ARENA_END
    ], key=lambda s: s.value)
    require(len(functions) == 29, "named E000 sized-function inventory drift")

    abort = truth.symbol("c2_abort_driver")
    abort_in, abort_out = edges_for(truth, abort)
    require(abort.section == GAP1 and abort.bytes == 134
            and [row["caller"] for row in abort_in]
                == ["c2_product_abort_cleanup"],
            "abort-driver identity/cold-call edge drift")
    allowed_abort_targets = {
        "__rc20", "__rc21", "__rc22", "c2_phase_owner",
        GAP1, "__rc2", "__rc3", "lisp65_c2_phase_scratch",
        "c2_overlay_call", RESIDENT, ".lisp65_c2_fixed_zp",
    }
    require({row["target"] for row in abort_out} <= allowed_abort_targets,
            "abort driver acquired an unpriced dependency")

    service = truth.section(FAR_SERVICE)
    facade = truth.section(FACADE)
    padding = truth.symbol("__lisp65_c2_mapped_far_facade_padding")
    wrappers = [truth.symbol("vm_code_load_converged"),
                truth.symbol("c2_physical_read_converged")]
    require(service.bytes == 1248 and FAR_CAPACITY - service.bytes == 251,
            "mapped far-service price drift")
    require(facade.bytes == 98 and padding.bytes == 19
            and all(row.bytes == 9 for row in wrappers),
            "mapped facade/padding price drift")

    map_contract = load(MAP_CONTRACT)
    # The corrected tuple maps only CPU block 3.  The planned body may call
    # E000 (block 7), C000 state (block 6) and lower fixed facades safely.
    map_text = json.dumps(map_contract, sort_keys=True).lower()
    require("0x40" in map_text and "0x82" in map_text
            and "block 3" in map_text, "corrected MAP contract drift")
    mapped_blocks = [3]
    require(7 not in mapped_blocks and 6 not in mapped_blocks,
            "far mapping hides abort-driver dependencies")

    preflight = load(PREFLIGHT)
    capture = preflight["target_object"]["sizes"]
    require(capture == {"helper": 25, "irq": 74, "main": 34, "state": 16},
            "parked capture emitted-size evidence drift")
    require(capture["main"] + capture["helper"] == PARKED_CAPTURE_BYTES,
            "parked split-capture code price drift")

    floor = load(FLOOR_CONTRACT)
    floor_geometry = floor["e000_geometry"]
    require(floor_geometry["active_floor_bytes"] == ACTIVE_FLOOR
            and "scope triage" in floor_geometry["self_defense"],
            "active E000 floor contract drift")

    # Per-function inventory.  Small residents are technically candidates for
    # a separately proved far wrapper; large ones do not fit the current
    # service reserve.  The abort driver is the one cold, single-edge winner.
    units: list[dict[str, Any]] = []
    fixed_reasons = {
        "c2_kernal_event_poll": (
            "hardware queue drain at the evaluator/KERNAL boundary; moving it "
            "would add a map transition to every key poll"),
        "c2_kernal_irq_handler": (
            "asynchronous hardware-vector target; must remain visible under "
            "every interrupted lower-map state"),
        "c2_kernal_nmi_handler": (
            "asynchronous NMI/freezer vector target; cannot depend on a "
            "foreground mapping trampoline"),
        "c2_kernal_fail_closed": (
            "reset-vector and corrupt-map terminal guard; its purpose requires "
            "visibility when lower mapping state is untrustworthy"),
        "c2_kernal_output_cell": (
            "four-byte post-startup screen seam; a nine-byte far entry would "
            "increase resident cost by five bytes"),
        "vm_runtime_overlay_transaction_begin": (
            "transaction boundary must execute outside the runtime overlay it "
            "authorizes and before overlay replacement"),
        "vm_c2d_byte": (
            "per-byte C2D primitive; a map/unmap pair on every byte is a "
            "timing regression and nests its resident stream dependency"),
    }
    for symbol in functions:
        if symbol.name == "c2_abort_driver":
            units.append(function_row(
                truth, symbol, "MOVE", "cold abort/RUN-STOP cleanup body with "
                "one ordinary-text caller; block-3 mapping leaves every linked "
                "state and E000 callee visible", FAR_SERVICE,
                {"far_service_bytes": symbol.bytes,
                 "facade_entry_bytes": wrappers[0].bytes,
                 "new_state_bytes": 0, "new_e000_bytes": 0}))
        elif symbol.name in fixed_reasons:
            units.append(function_row(
                truth, symbol, "STAY", fixed_reasons[symbol.name], None,
                {"rejected_far_service_bytes": symbol.bytes,
                 "rejected_facade_entry_bytes": wrappers[0].bytes}))
        elif symbol.section == RESIDENT:
            fits = symbol.bytes <= FAR_CAPACITY - service.bytes
            units.append(function_row(
                truth, symbol,
                ("CONDITIONALLY MOVABLE; NOT SELECTED"
                 if fits else "STAY: DOES NOT FIT CURRENT FAR RESERVE"),
                "member of the always-visible C2 resident call/overlay closure; "
                "no single cold caller establishes a lower-risk move than the "
                "abort driver",
                FAR_SERVICE if fits else None,
                {"body_bytes": symbol.bytes,
                 "facade_entry_min_bytes": wrappers[0].bytes,
                 "fits_current_service_reserve": fits}))
        else:
            raise StudyError(f"unclassified E000 function: {symbol.name}")

    # Four hand-written vector/seam bodies intentionally have zero-sized ELF
    # symbols.  Their section extents, not guessed symbol ends, are the truth.
    unsized = [
        ("c2_kernal_irq_handler",
         ".lisp65_c2_kernal_window.irq_handler",
         "asynchronous hardware-vector target; must remain visible under every "
         "interrupted lower-map state"),
        ("c2_kernal_nmi_handler",
         ".lisp65_c2_kernal_window.nmi_and_freezer_return",
         "asynchronous NMI/freezer vector target; cannot depend on a foreground "
         "mapping trampoline"),
        ("c2_kernal_fail_closed",
         ".lisp65_c2_kernal_window.map_switch_and_guards",
         "reset-vector and corrupt-map terminal guard; it must remain visible "
         "when lower mapping state is untrustworthy"),
        ("c2_kernal_output_cell",
         ".lisp65_c2_kernal_window.post_startup_output_seam",
         "four-byte screen seam; a nine-byte far entry would increase resident "
         "cost by five bytes"),
    ]
    for name, section_name, reason in unsized:
        symbol = truth.symbol(name)
        section = truth.section(section_name)
        require(symbol.value == section.address and symbol.bytes == 0,
                f"unsized assembler tenant identity drift: {name}")
        incoming, _ = edges_for(truth, symbol)
        units.append({
            "name": name, "kind": "section-sized-function",
            "section": section.name, "vma": section.address,
            "end_exclusive": section.address + section.bytes,
            "bytes": section.bytes, "incoming_edges": len(incoming),
            "verdict": "STAY", "mapped_reason": reason,
            "destination": None,
            "move_price": {"rejected_far_service_bytes": section.bytes,
                           "rejected_facade_entry_bytes": wrappers[0].bytes},
        })

    profile = truth.section(
        ".lisp65_c2_kernal_window.profile_rodata")
    profile_inputs = [r for r in truth.relocations
                      if truth.relocation_target_identity(r).get(
                          "resolved_value") == profile.address]
    units.append({
        "name": "profile_rodata", "kind": "data",
        "section": profile.name, "vma": profile.address,
        "end_exclusive": profile.address + profile.bytes,
        "bytes": profile.bytes, "incoming_edges": len(profile_inputs),
        "verdict": "STAY",
        "mapped_reason": "function/dispatch profile tables are synchronously "
                         "consumed by ordinary text, including code inside the "
                         "same block-3 CPU window; mapped Bank-2 data would hide "
                         "such consumers during access",
        "destination": None,
        "move_price": {"required_new_reader_or_copy": True,
                       "ordinary_bank0_known_free_bytes": 6},
    })

    post_relocation_free = free_bytes + abort.bytes
    post_capture_free = post_relocation_free - PARKED_CAPTURE_BYTES
    surplus_over_floor = post_capture_free - ACTIVE_FLOOR
    service_after = service.bytes + abort.bytes
    padding_after = padding.bytes - wrappers[0].bytes
    require(post_relocation_free == 195 and post_capture_free == 136
            and surplus_over_floor == 82, "E000 plan arithmetic drift")
    require(service_after == 1382 and FAR_CAPACITY - service_after == 117,
            "far-service plan arithmetic drift")
    require(padding_after == 10, "facade plan arithmetic drift")

    result = {
        "format": FORMAT, "recorded_on": RECORDED_ON,
        "status": "PRICED: ONE RELOCATION FREES 134 E000 BYTES",
        "authority": {
            "commission": authorization(), "placement_first_red": bind(PLACEMENT_RED),
            "parked_seam_final_red": bind(FINAL_RED), "parked_preflight": bind(PREFLIGHT),
            "candidate_elf": bind(candidate), "floor_contract": bind(FLOOR_CONTRACT),
            "far_contract": bind(FAR_CONTRACT), "map_contract": bind(MAP_CONTRACT),
            "runtime_source": bind(RUNTIME_SOURCE),
            "interrupt_source": bind(INTERRUPT_SOURCE),
            "facade_source": bind(FACADE_SOURCE), "driver": bind(DRIVER),
        },
        "execution": {"host_only": True, "product_sources_changed": False,
                      "compiles": 0, "links": 0, "device_contacts": 0},
        "candidate_geometry": {
            "arena": {"start": ARENA_START, "end_exclusive": ARENA_END,
                      "bytes": ARENA_END - ARENA_START},
            "allocated_union_bytes": allocated_bytes,
            "allocated_sections": allocated, "free_intervals": free,
            "free_bytes": free_bytes,
        },
        "tenant_inventory": {
            "allocated_section_count": len(allocated),
            "sized_function_count": len(functions),
            "section_sized_function_count": len(unsized),
            "units": units,
        },
        "selected_move": {
            "symbol": abort.name, "source_section": abort.section,
            "body_bytes": abort.bytes, "incoming": abort_in,
            "outgoing": abort_out, "destination_section": FAR_SERVICE,
            "mapped_cpu_blocks": mapped_blocks,
            "visible_dependency_blocks": [6, 7],
            "new_facade_entry": {
                "bytes": wrappers[0].bytes,
                "derivation": "two emitted predecessor entries are each 9 bytes",
                "shape": "enter -> relocated body -> leave",
            },
            "state_bytes": 0,
        },
        "price": {
            "e000": {"before_free": free_bytes,
                     "freed_by_relocation": abort.bytes,
                     "after_relocation_free": post_relocation_free,
                     "parked_capture_bytes": PARKED_CAPTURE_BYTES,
                     "after_capture_free": post_capture_free,
                     "active_floor": ACTIVE_FLOOR,
                     "surplus_over_floor": surplus_over_floor,
                     "required_freed_bytes": REQUIRED_NEW_FREE},
            "far_service": {"before_bytes": service.bytes,
                            "relocated_body_bytes": abort.bytes,
                            "after_bytes": service_after,
                            "capacity_bytes": FAR_CAPACITY,
                            "after_headroom_bytes": FAR_CAPACITY - service_after},
            "facade": {"fixed_section_bytes": facade.bytes,
                       "padding_before": padding.bytes,
                       "new_entry_bytes": wrappers[0].bytes,
                       "padding_after": padding_after,
                       "section_growth_bytes": 0},
            "other": {"ordinary_text_bytes": 0, "fixed_state_bytes": 0,
                      "image_growth_bytes": abort.bytes,
                      "new_public_symbols": 0},
        },
        "floor_finding": {
            "kind": "owner-bound capacity reserve, not a runtime tenant",
            "measurable_protection": "prevents any successor card from "
                "silently spending the last 54 bytes of always-visible E000",
            "historical_origin": "bound after append-final consolidation "
                "measured 54 bytes remaining; the contract requires scope "
                "triage rather than a fourth floor erosion",
            "used_as_relocation_credit": False,
            "change_evidence_required": [
                "new explicit owner decision",
                "born-derived final-ELF tenant and free-space inventory",
                "named workload or failure model protected by the replacement floor",
                "full linked qualification and capacity mutations",
            ],
        },
        "ordered_cards": [
            {
                "order": 1, "name": "abort-driver far relocation",
                "product_delta": "move one 134-byte body and replace 9 of 19 "
                                 "explicit facade-padding bytes with one entry",
                "acceptance_gates": [
                    "final-ElfTruth body identity and single-owner placement",
                    "emitted facade edges enter/body/leave and fixed 98-byte facade",
                    "decoded block-3 map leaves blocks 6 and 7 visible",
                    "transitive C/ASM ABI and every-exit unmap preservation",
                    "far-service 1382 <= 1499 and facade padding 10 >= 0",
                    "E000 free 195 with the 54-byte floor unchanged",
                ],
            },
            {
                "order": 2, "name": "reopen parked input-fidelity seam",
                "precondition": "card 1 final artifacts and all gates green",
                "product_delta": "place the already priced 34+25 byte capture "
                                 "fragments; no new architecture",
                "acceptance_gates": [
                    "the parked three permanent placement/ordering/consumer gates",
                    "94-event forced-89-frame-collection loss model",
                    "capture disabled before evaluation and on every exit",
                    "final-ElfTruth E000 free 136 and floor surplus 82",
                ],
            },
        ],
        "claim_limit": "Study only. No relocation, capture, compile, link, "
                       "media, device or product-success claim is made.",
    }
    return result


def validate(value: dict[str, Any]) -> None:
    require(value["execution"] == {
        "host_only": True, "product_sources_changed": False,
        "compiles": 0, "links": 0, "device_contacts": 0},
        "study crossed its execution boundary")
    require(value["candidate_geometry"]["free_bytes"] == 61,
            "candidate free-space truth drift")
    price = value["price"]
    require(price["e000"]["freed_by_relocation"] >= REQUIRED_NEW_FREE,
            "relocation does not free the commissioned minimum")
    require(price["e000"]["active_floor"] == ACTIVE_FLOOR
            and price["e000"]["after_capture_free"] >= ACTIVE_FLOOR,
            "plan spends or changes the E000 floor")
    require(price["far_service"]["after_bytes"]
            <= price["far_service"]["capacity_bytes"],
            "relocated body exceeds the far-service contract")
    require(price["facade"]["fixed_section_bytes"] == 98
            and price["facade"]["padding_after"] >= 0
            and price["facade"]["section_growth_bytes"] == 0,
            "facade price breaks its fixed contract")
    selected = value["selected_move"]
    require(selected["symbol"] == "c2_abort_driver"
            and selected["body_bytes"] == 134
            and len(selected["incoming"]) == 1
            and selected["incoming"][0]["caller"]
                == "c2_product_abort_cleanup",
            "selected cold single-edge tenant drift")
    require(selected["mapped_cpu_blocks"] == [3]
            and not ({6, 7} & set(selected["mapped_cpu_blocks"])),
            "selected mapping hides required resident dependencies")
    require(value["floor_finding"]["used_as_relocation_credit"] is False,
            "historical floor was used as freight")
    require(len(value["ordered_cards"]) == 2,
            "relocation and parked seam are not separately gated")


def mutation_results(value: dict[str, Any]) -> dict[str, bool]:
    mutations = {
        "free-space-range-arithmetic": lambda x: x["candidate_geometry"].update(
            free_bytes=606),
        "relocation-under-52": lambda x: x["price"]["e000"].update(
            freed_by_relocation=51),
        "floor-eroded": lambda x: x["price"]["e000"].update(active_floor=53),
        "capture-spends-floor": lambda x: x["price"]["e000"].update(
            after_capture_free=53),
        "far-service-over-capacity": lambda x: x["price"]["far_service"].update(
            after_bytes=1500),
        "facade-growth": lambda x: x["price"]["facade"].update(
            section_growth_bytes=9),
        "facade-padding-negative": lambda x: x["price"]["facade"].update(
            padding_after=-1),
        "second-abort-caller": lambda x: x["selected_move"]["incoming"].append(
            {"caller": "mutation"}),
        "map-hides-e000": lambda x: x["selected_move"].update(
            mapped_cpu_blocks=[3, 7]),
        "floor-used-as-credit": lambda x: x["floor_finding"].update(
            used_as_relocation_credit=True),
        "merge-relocation-and-capture-card": lambda x: x.update(
            ordered_cards=x["ordered_cards"][:1]),
    }
    results: dict[str, bool] = {}
    for name, mutate in mutations.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate(trial)
        except StudyError:
            results[name] = True
        else:
            results[name] = False
    require(all(results.values()), "study mutation did not fail closed")
    return results


def main() -> int:
    try:
        value = derive()
        validate(value)
        value["mutations"] = mutation_results(value)
        value["mutation_count"] = len(value["mutations"])
        RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
        print("v1.6 E000 relocation study: PASS "
              "move=c2_abort_driver freed=134 post-capture=136 floor=54 "
              "far=1382/1499 facade-pad=10")
        return 0
    except (StudyError, KeyError, OSError, ValueError,
            subprocess.CalledProcessError) as error:
        print(f"v1.6 E000 relocation study: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
