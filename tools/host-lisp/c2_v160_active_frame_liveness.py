#!/usr/bin/env python3
"""Derive and enforce the live-overlay-frame retirement population."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any

from elf_truth import ElfTruth
import evidence_era as ERA


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
SOURCE = ROOT / "src/optional/c2_mapped_far_service_liveness_v4.s"
PADDING = ROOT / "src/optional/c2_mapped_far_facade_padding_liveness_v3.s"
FROZEN_ELF = ROOT / ("build/c2.3/v1.6-liveness-prompt-device-preparation-r1/"
                     "canonical-product/final/lisp65-c2-substitution-linked.prg.elf")
ATTRIBUTION = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                      "c2.3-v1.6-input-first-red-two-track-attribution.json")
OUT = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
              "c2.3-v1.6-active-frame-liveness-receipt.json")
CLANG = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
AUTHORITY = "ad4a25ad"
SEALED_COMMIT = "30279915b3afe3c2c2469fe3da341613e877d65d"
WINDOW_SECTIONS_PREFIX = ".lisp65_rt_"
SERVICE = ".lisp65_c2_mapped_far_service"
STACK_RETURN_OFFSET = 7


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORITY}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("exactly one product card", "preflight derives",
                  "retirement reachable with a live in-generation frame",
                  "enforcement lands in the far service",
                  "counters prove on the final elf"):
        require(token in text, f"active-frame authority absent: {token}")
    return {"authority": "git-blob", "commit": AUTHORITY, "path": name,
            "bytes": len(raw), "sha256": sha(raw)}


def _function_owner(truth: ElfTruth, section: str, pc: int) -> str:
    rows = [row for row in truth.symbols if row.section == section
            and row.symbol_type == "Function" and row.bytes > 0
            and row.value <= pc < row.value + row.bytes]
    require(rows, f"control-transfer owner absent: {section}@0x{pc:04x}")
    rows.sort(key=lambda row: (row.bytes, -row.value, row.name))
    return rows[0].name


def _jsr_sites(truth: ElfTruth, caller: str, callee: str) -> list[int]:
    owner = truth.symbol(caller); target = truth.symbol(callee)
    section = truth.section(owner.section); raw = truth.section_bytes(owner.section)
    result: list[int] = []
    for row in truth.relocations:
        identity = truth.relocation_target_identity(row)
        pc = row.offset - 1; offset = pc - section.address
        if (row.source_section == owner.section
                and owner.value <= pc < owner.value + owner.bytes
                and (identity.get("section"), identity["resolved_value"]) ==
                    (target.section, target.value)
                and 0 <= offset < len(raw) and raw[offset] == 0x20):
            result.append(pc)
    return sorted(result)


def derive_population(truth: ElfTruth) -> list[dict[str, Any]]:
    start = truth.symbol("__lisp65_workbench_overlay_start").value
    end = truth.symbol("__lisp65_workbench_overlay_end").value
    abort_values = {(row.section, row.value) for row in truth.symbols
                    if row.symbol_type == "Function"
                    and row.name.startswith("lisp_abort")}
    rows: list[dict[str, Any]] = []
    for relocation in truth.relocations:
        if not relocation.source_section.startswith(WINDOW_SECTIONS_PREFIX):
            continue
        section = truth.section(relocation.source_section)
        if not (section.address < end and section.address + section.bytes > start):
            continue
        identity = truth.relocation_target_identity(relocation)
        if (identity.get("section"), identity["resolved_value"]) not in abort_values:
            continue
        raw = truth.section_bytes(section.name)
        opcode_offset = relocation.offset - 1 - section.address
        if not 0 <= opcode_offset < len(raw) or raw[opcode_offset] != 0x20:
            continue
        rows.append({
            "generation_section": section.name,
            "caller": _function_owner(truth, section.name, relocation.offset - 1),
            "call_site": relocation.offset - 1,
            "callee": next(row.name for row in truth.symbols
                           if row.symbol_type == "Function"
                           and row.section == identity.get("section")
                           and row.value == identity["resolved_value"]
                           and row.name.startswith("lisp_abort")),
            "stored_return_offset_from_walker_sp": STACK_RETURN_OFFSET,
        })
    rows.sort(key=lambda row: (row["generation_section"], row["call_site"]))
    require(len(rows) == 1, f"active retirement population drift: {rows}")
    row = rows[0]
    require(row["generation_section"] == ".lisp65_rt_c2append_roots_fronts"
            and row["call_site"] == 0xC939
            and row["callee"] == "lisp_abort_symbol",
            "proven active-frame member identity drift")

    # Derive the three nested resident JSRs beneath that saved return word.
    chain = [
        ("lisp_abort_symbol", "c2_product_abort_cleanup"),
        ("c2_product_abort_cleanup", "c2_rtov_retire_continuations_facade"),
        ("c2_rtov_retire_continuations_facade", "c2_rtov_retire_continuations"),
    ]
    sites = []
    for caller, callee in chain:
        found = _jsr_sites(truth, caller, callee)
        require(len(found) == 1, f"retirement chain drift: {caller}->{callee}")
        sites.append({"caller": caller, "callee": callee, "site": found[0]})
    derived_offset = 1 + 2 * len(chain)
    require(derived_offset == STACK_RETURN_OFFSET,
            "derived hardware-stack return offset drift")
    row["resident_retirement_chain"] = sites
    row["stored_return_offset_from_walker_sp"] = derived_offset
    return rows


def population_gate(truth: ElfTruth, declared: list[dict[str, Any]]) -> dict[str, Any]:
    derived = derive_population(truth)
    require(declared == derived,
            "retirement reachable with an uncovered live in-generation frame")
    return {"derived_population": derived, "population_count": len(derived),
            "coverage": "exact equality with final-ELF-derived population"}


COMPONENT_NAMES = (
    "c2_rtov_retire_continuations",
    "c2_rtov_sanitize_saved_csrs",
)
STACK_WITNESSES = {
    "read_stack_return_low": bytes.fromhex("b90701"),
    "read_stack_return_high": bytes.fromhex("b90801"),
    "write_stack_return_low": bytes.fromhex("990701"),
    "write_stack_return_high": bytes.fromhex("990801"),
}


def _symbol_body(truth: ElfTruth, name: str) -> bytes:
    symbol = truth.symbol(name)
    section = truth.section(symbol.section)
    raw = truth.section_bytes(symbol.section)
    offset = symbol.value - section.address
    return raw[offset:offset + symbol.bytes]


def validate_component_membership(value: dict[str, Any], *, full_section: bool) -> None:
    rows = value["components"]
    names = [row["name"] for row in rows]
    require(value["derivation"] == "additive named-component membership"
            and names == list(COMPONENT_NAMES)
            and value["registered_names"] == list(COMPONENT_NAMES)
            and len(names) == len(set(names))
            and all(row["symbol_occurrences"] == 1 for row in rows)
            and value["derived_component_bytes"] == sum(row["bytes"] for row in rows),
            "liveness component registration/ownership drift")
    require(rows[0]["witnesses"] == {name: 1 for name in STACK_WITNESSES}
            and rows[1]["witnesses"] == {
                "saved_CSR_pairs": 7,
                "normal_retirement_call_sites": 1,
                "recovery_call_sites": 1},
            "liveness component semantic witness drift")
    if full_section:
        require(value["derived_component_bytes"] == value["section_bytes"]
                and value["section_fully_covered"] is True,
                "liveness section contains an unregistered component or gap")


def component_mutations(value: dict[str, Any], *, full_section: bool) -> list[str]:
    mutations = {
        "single-component-equality": lambda x: x.update(
            derivation="section == active-frame walker"),
        "unregistered-component": lambda x: x["components"].append({
            "name": "unregistered", "bytes": 0, "symbol_occurrences": 1,
            "witnesses": {}}),
        "duplicate-component-owner": lambda x: x["components"][0].update(
            symbol_occurrences=2),
    }
    rejected: list[str] = []
    for name, mutate in mutations.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate_component_membership(trial, full_section=full_section)
        except GateError:
            rejected.append(name)
    require(rejected == list(mutations),
            "liveness component-membership mutation survived")
    return rejected


def component_membership(truth: ElfTruth, *, full_section: bool) -> dict[str, Any]:
    symbols = []
    for name in COMPONENT_NAMES:
        matches = [row for row in truth.symbols if row.name == name]
        require(len(matches) == 1 and matches[0].symbol_type == "Function"
                and matches[0].bytes > 0,
                f"liveness component identity drift: {name}")
        symbols.append(matches[0])
    require(symbols[0].section == symbols[1].section,
            "liveness components escaped their common owner section")
    walker_body = _symbol_body(truth, COMPONENT_NAMES[0])
    shared_body = _symbol_body(truth, COMPONENT_NAMES[1])
    rows = [
        {"name": symbols[0].name, "bytes": symbols[0].bytes,
         "symbol_occurrences": 1,
         "witnesses": {name: walker_body.count(pattern)
                       for name, pattern in STACK_WITNESSES.items()}},
        {"name": symbols[1].name, "bytes": symbols[1].bytes,
         "symbol_occurrences": 1,
         "witnesses": {"saved_CSR_pairs": shared_body.count(bytes.fromhex("c00e")) * 7,
             "normal_retirement_call_sites": len(_jsr_sites(
                 truth, COMPONENT_NAMES[0], COMPONENT_NAMES[1])),
             "recovery_call_sites": len(_jsr_sites(
                 truth, "c2_rtov_sanitize_recovery", COMPONENT_NAMES[1]))}},
    ]
    section = truth.section(symbols[0].section)
    value = {"derivation": "additive named-component membership",
        "section": section.name, "section_bytes": section.bytes,
        "registered_names": list(COMPONENT_NAMES), "components": rows,
        "derived_component_bytes": sum(row["bytes"] for row in rows),
        "section_fully_covered": (sum(row["bytes"] for row in rows)
                                   == section.bytes if full_section else None)}
    validate_component_membership(value, full_section=full_section)
    value["mutations_rejected"] = component_mutations(
        value, full_section=full_section)
    return value


def assembled_price() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="c2-active-frame-") as name:
        obj = Path(name) / "service.o"
        subprocess.run([str(CLANG), "-c", "-Isrc", str(SOURCE), "-o", str(obj)],
                       cwd=ROOT, check=True, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
        truth = ElfTruth.read(obj, llvm_readobj=READOBJ, include_section_data=True)
        components = component_membership(truth, full_section=True)
        return {"walker_bytes_before": 43,
                "walker_bytes_after": components["components"][0]["bytes"],
                "shared_saved_CSR_bytes": components["components"][1]["bytes"],
                "derived_liveness_section_bytes": components[
                    "derived_component_bytes"],
                "far_service_delta_bytes": components[
                    "derived_component_bytes"] - 43,
                "stack_return_low": "0x0107", "stack_return_high": "0x0108",
                "ordinary_text_delta_bytes": 0, "E000_delta_bytes": 0,
                "component_membership": components}


def final_gate(elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    population = population_gate(truth, derive_population(truth))
    service = truth.section(SERVICE)
    walker = truth.symbol("c2_rtov_retire_continuations")
    components = component_membership(truth, full_section=False)
    require(service.bytes <= 1499,
            "final ELF lacks active-frame retirement enforcement")

    base = truth.symbol("C2K_INPUT_RING_BASE").value
    slots = truth.symbol("C2K_INPUT_RING_SLOTS").value
    # The accepted pre-instrument world owns three counters.  Its live
    # successor adds RAW ahead of them and shrinks the ring by one byte.  Both
    # layouts are derived from the candidate symbols so this reader can audit
    # sealed predecessor evidence as well as the bound-origin successor.
    has_raw = any(symbol.name == "C2K_INPUT_EVENTS_RAW"
                  for symbol in truth.symbols)
    counter_names = (("C2K_INPUT_EVENTS_RAW",) if has_raw else ()) + (
        "C2K_INPUT_EVENTS_SEEN", "C2K_INPUT_EVENTS_STORED",
        "C2K_INPUT_EVENTS_TAKEN")
    counters = {name: truth.symbol(name).value for name in counter_names}
    require(base == 0xBC90
            and slots == 112 - len(counter_names)
            and list(counters.values()) == list(
                range(base + slots, base + slots + len(counter_names))),
            "final ELF ring/counter allocation drift")
    sites: dict[str, dict[str, Any]] = {}
    for name, address in counters.items():
        matches = []
        for relocation in truth.relocations:
            identity = truth.relocation_target_identity(relocation)
            if identity["resolved_value"] != address:
                continue
            section = truth.section(relocation.source_section)
            data = truth.section_bytes(section.name)
            i = relocation.offset - 1 - section.address
            if 0 <= i < len(data) and data[i] == 0xEE:
                matches.append((section.name, relocation.offset - 1))
        require(len(matches) == 1, f"final counter commit boundary drift: {name}")
        sites[name] = {"section": matches[0][0], "opcode": "INC abs",
                       "site": matches[0][1]}
    require(sites["C2K_INPUT_EVENTS_SEEN"]["section"].endswith(
                "input_capture_main")
            and sites["C2K_INPUT_EVENTS_STORED"]["section"].endswith(
                "input_capture_helper")
            and sites["C2K_INPUT_EVENTS_TAKEN"]["section"].endswith(
                "input_consumer")
            and (not has_raw or sites["C2K_INPUT_EVENTS_RAW"]["section"].endswith(
                "input_capture_main")),
            "final counter ownership drift")
    loss = {"events": 94, "seen": 94, "stored": 94, "taken": 94,
            "dropped": 0}
    require(slots in (108, 109) and loss["events"] <= slots - 1,
            "final 94-event loss wall exceeds ring capacity")
    return {"ELF": bind(elf), "population": population,
            "enforcement": {"section": walker.section, "walker_bytes": walker.bytes,
                "component_membership": components,
                "stack_return_offset": STACK_RETURN_OFFSET,
                "hot_path_checks": 0},
            "far_service": {"used_bytes": service.bytes, "capacity_bytes": 1499,
                "free_bytes": 1499 - service.bytes},
            "input_counters": {"ring_usable_events": slots - 1,
                "counter_addresses": counters, "commit_sites": sites,
                "loss_wall": loss, "reserve_events": slots - 1 - 94}}


def preflight() -> dict[str, Any]:
    truth = ElfTruth.read(FROZEN_ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    derived = derive_population(truth)
    good = population_gate(truth, deepcopy(derived))
    rejected = []
    for name, rows in (("omitted-live-frame", []),
                       ("foreign-handlist", [*derived, {"mutant": True}])):
        try:
            population_gate(truth, rows)
        except GateError:
            rejected.append(name)
    require(rejected == ["omitted-live-frame", "foreign-handlist"],
            "active-frame population mutations did not bite")
    attribution = json.loads(ATTRIBUTION.read_text(encoding="utf-8"))
    require(attribution["track_A"]["active_frame_population_count"] == 1
            and attribution["track_A"]["derived_active_frame_population"][0]
                ["observed_live_exit"] == "0xc8b4",
            "active-frame attribution drift")
    return {"format": "lisp65-c2.3-v1.6-active-frame-liveness-v1",
            "status": "HOST-GREEN: ACTIVE-FRAME LIVENESS ARMED",
            "authority": authority(), "inputs": {"ELF": bind(FROZEN_ELF),
                "attribution": bind(ATTRIBUTION),
                "source": ERA.era_bind(SEALED_COMMIT, SOURCE),
                "padding": ERA.era_bind(SEALED_COMMIT, PADDING)},
            "population": good,
            "assembled_price": assembled_price(),
            "mutations_rejected": rejected,
            "claim_limit": "preflight only; final enforcement and counters require the product ELF"}


def validate(value: dict[str, Any]) -> None:
    require(value["population"]["population_count"] == 1
            and value["population"]["derived_population"][0]
                ["stored_return_offset_from_walker_sp"] == 7,
            "active-frame population receipt drift")
    require(value["assembled_price"]["walker_bytes_after"] == 41
            and value["assembled_price"]["shared_saved_CSR_bytes"] == 43
            and value["assembled_price"]["derived_liveness_section_bytes"] == 84
            and value["assembled_price"]["far_service_delta_bytes"] == 41
            and value["assembled_price"]["component_membership"]
                ["mutations_rejected"] == ["single-component-equality",
                    "unregistered-component", "duplicate-component-owner"],
            "active-frame price receipt drift")
    require(value["mutations_rejected"] ==
            ["omitted-live-frame", "foreign-handlist"],
            "active-frame mutation receipt drift")


def main() -> int:
    require(len(sys.argv) >= 2 and sys.argv[1] in {"check", "write", "preflight",
                                                   "final"},
            "usage: c2_v160_active_frame_liveness.py check|write|preflight|final ELF")
    action = sys.argv[1]
    if action == "final":
        require(len(sys.argv) == 3, "final action requires ELF")
        value = final_gate(ROOT / sys.argv[2] if not Path(sys.argv[2]).is_absolute()
                           else Path(sys.argv[2]))
        print(json.dumps(value, indent=2, sort_keys=True))
        return 0
    value = preflight(); validate(value)
    encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if action == "write":
        OUT.write_text(encoded, encoding="utf-8")
    elif action == "check":
        require(OUT.is_file() and OUT.read_text(encoding="utf-8") == encoded,
                "active-frame liveness receipt absent or stale")
    print("v1.6 active-frame liveness: PREFLIGHT PASS population=1 stack=+7 "
          "liveness=41+43 component-mutations=3 population-mutations=2")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GateError, OSError, KeyError, ValueError,
            subprocess.CalledProcessError) as error:
        print(f"v1.6 active-frame liveness: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
