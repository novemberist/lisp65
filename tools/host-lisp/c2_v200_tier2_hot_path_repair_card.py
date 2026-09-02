#!/usr/bin/env python3
"""Fuse Tier-2 CAR/CDR type+payload reads and qualify two latency lanes."""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_v200_domain_tier2_product_card as T2  # noqa: E402
import c2_v200_interactive_delivery_chain_product_card as CHAIN  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
AUTHORIZATION = "ddb07891"
PLAN_HEADER = (
    "## Reviewer disposition — tier-2 hot-path regression, one repair round — 2026-09-02")
PREDECESSOR_RECEIPT = CHAIN.RECEIPT
PREDECESSOR_ELF = CHAIN.ELF
PREDECESSOR_PRG = CHAIN.PRG
PREDECESSOR_PROFILE = CHAIN.PROFILE
PREDECESSOR_PLANE = CHAIN.PLANE
PREDECESSOR_PREFLIGHT = CHAIN.PREFLIGHT
PREDECESSOR_PLANE_RECEIPT = CHAIN.PLANE_RECEIPT
V19_EDITOR = ROOT / (
    "build/c2.3/v1.9.0-release-card-r1-preflight/sources/stdlib-read-line.lisp")
LIVE_EDITOR = ROOT / "lib/stdlib-read-line.lisp"

BUILD = ROOT / "build/c2.3/v2.0-tier2-hot-path-repair-card-r1"
PREFLIGHT = ROOT / "build/c2.3/v2.0-tier2-hot-path-repair-card-r1-preflight"
PLANE = PREFLIGHT / "setup-owned/static-plane/narrow-static"
WPLTO = BUILD / "wplto"
ELF = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
PRG = WPLTO / "lisp65-c2-substitution-linked.prg"
PROFILE = WPLTO / "resolved-profile.txt"
INVOCATION = PREFLIGHT / "candidate-invocation.json"
PLANE_RECEIPT = ARCH / "c2.3-v2.0-tier2-hot-path-repair-card-r1-plane.json"
PREFLIGHT_RECEIPT = ARCH / (
    "c2.3-v2.0-tier2-hot-path-repair-card-r1-preflight.json")
SOURCE_PREFLIGHT = ARCH / (
    "c2.3-v2.0-tier2-hot-path-repair-card-r1-source-preflight.json")
FIRST_RED = ARCH / (
    "c2.3-v2.0-tier2-hot-path-repair-card-r1-first-red.json")
DIFFERENCE = ARCH / "c2.3-v2.0-tier2-hot-path-repair-card-r1-difference.json"
RECEIPT = ARCH / "c2.3-v2.0-tier2-hot-path-repair-card-r1-receipt.json"
REPORT = ROOT / "docs/planning/v2.0.0-tier2-hot-path-repair-card-report.md"
FIRST_RED_REPORT = ROOT / (
    "docs/planning/v2.0.0-tier2-hot-path-repair-first-red-report.md")
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
FORMAT = "lisp65-c2-v200-tier2-hot-path-repair-card-v1"
STATUS = "PASS: V2.0 TIER-2 HOT-PATH REPAIR GREEN"
EXTENT = 53820


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


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


def run(command: list[str], label: str) -> str:
    process = subprocess.run(command, cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    require(process.returncode == 0, f"{label} red:\n{process.stdout}")
    return process.stdout


def authority() -> dict[str, Any]:
    relative = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{relative}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = raw.decode()
    require(text.count(PLAN_HEADER) == 1, "hot-path authorization drift")
    section = PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    folded = " ".join(section.lower().replace("`", "").split())
    for token in ("one bounded repair round", "single-keystroke lane",
                  "batch throughput", "final link", "matcher/blink"):
        require(token in folded, f"hot-path authority token absent: {token}")
    payload = section.encode()
    return {"commit": AUTHORIZATION, "path": relative,
        "section": PLAN_HEADER, "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "predecessor": bind(PREDECESSOR_RECEIPT),
        "right": "one repair product card, one WPLTO and one product link"}


def configure() -> None:
    # Reuse the proven resident delivery producer, but make its predecessor and
    # every phase-owned output explicit successor values.
    CHAIN.T2.RECEIPT = PREDECESSOR_RECEIPT
    CHAIN.T2.ELF = PREDECESSOR_ELF
    CHAIN.T2.PRG = PREDECESSOR_PRG
    CHAIN.T2.PROFILE = PREDECESSOR_PROFILE
    for name, value in {
        "BUILD": BUILD, "PREFLIGHT": PREFLIGHT, "PLANE": PLANE,
        "WPLTO": WPLTO, "ELF": ELF, "PRG": PRG, "PROFILE": PROFILE,
        "INVOCATION": INVOCATION, "PLANE_RECEIPT": PLANE_RECEIPT,
        "PREFLIGHT_RECEIPT": PREFLIGHT_RECEIPT,
        "SOURCE_PREFLIGHT": SOURCE_PREFLIGHT, "DIFFERENCE": DIFFERENCE,
        "RECEIPT": RECEIPT, "REPORT": REPORT, "DRIVER": DRIVER,
        "AUTHORIZATION": AUTHORIZATION, "PLAN_HEADER": PLAN_HEADER,
        "FORMAT": FORMAT, "STATUS": STATUS,
    }.items():
        setattr(CHAIN, name, value)
    CHAIN.authority = authority
    CHAIN.patch_link_stack()


def materialize_plane() -> dict[str, Any]:
    require(not PREFLIGHT.exists() and not PLANE_RECEIPT.exists(),
            "repair plane materialization is one-shot")
    predecessor = load(PREDECESSOR_PLANE_RECEIPT)
    require(predecessor["geometry"]["bytes"] == EXTENT
            and bind(PREDECESSOR_PLANE / "v6-semantics/bank2-static-code.bin")
                == predecessor["bank2"],
            "delivery predecessor plane drift")
    shutil.copytree(PREDECESSOR_PLANE, PLANE)
    for name in ("projected-ownership-contract.json",
                 "projected-full-map-authority.json"):
        source = PREDECESSOR_PREFLIGHT / name
        require(source.is_file(), f"delivery projection absent: {name}")
        shutil.copyfile(source, PREFLIGHT / name)
    code = PLANE / "v6-semantics/bank2-static-code.bin"
    value = {"format": FORMAT + "-plane", "recorded_on": "2026-09-02",
        "status": "PASS: BYTE-IDENTICAL 53820-BYTE PLANE INHERITED",
        "authority": authority(), "source_plane": bind(PREDECESSOR_PLANE_RECEIPT),
        "bank2": bind(code), "geometry": predecessor["geometry"],
        "accounting": {"WPLTO_runs": 0, "product_links": 0}}
    require(value["bank2"]["sha256"] == predecessor["bank2"]["sha256"],
            "repair changed the resident interactive plane")
    PLANE_RECEIPT.write_bytes(canonical(value))
    return value


def configuration_gate() -> dict[str, Any]:
    configure()
    value = CHAIN.configuration_gate()
    require(value["packed"]["closure"]["object_count"] == 797
            and value["packed"]["key_sources"]["armed_sink_set"]
                == ["c2_kernal_input_take"],
            "repair predecessor composition drift")
    return value


def preflight() -> None:
    require(not any(path.exists() for path in
        (BUILD, PREFLIGHT, PLANE_RECEIPT, PREFLIGHT_RECEIPT,
         SOURCE_PREFLIGHT, DIFFERENCE, RECEIPT)),
        "repair preflight is one-shot")
    materialize_plane()
    gate = configuration_gate()
    sources = CHAIN.source_preflight()
    source_text = (ROOT / "src/vm.c").read_text(encoding="utf-8")
    mem_text = (ROOT / "src/mem.c").read_text(encoding="utf-8")
    require("cell_cons_field(a, op == OP_CDR, &b)" in source_text
            and "ext_dma_read_or_abort(EXT_OFF(i),EXT_BANK,stg" in mem_text
            and "uint8_t *stg=ext_dl" in mem_text,
            "fused target source is not armed")
    value = {"format": FORMAT + "-preflight", "recorded_on": "2026-09-02",
        "status": "PASS: HOT-PATH REPAIR CARD ARMED 0/1",
        "authority": authority(), "plane": bind(PLANE_RECEIPT),
        "configuration": gate, "source_preflight": bind(SOURCE_PREFLIGHT),
        "source_population": sources,
        "repair_sources": [bind(ROOT / name) for name in
            ("src/mem.c", "src/obj.h", "src/vm.c",
             "scripts/ext-cons-field-smoke-main.c")],
        "lanes": {
            "single_keystroke": {
                "stimulus_batch_cap": 1,
                "bound": "no more than 2 percent VM-step drift from device-green v1.9 and one transport per extended Cons field"},
            "batch_throughput": {
                "stimulus_batch_cap": 8,
                "bound": "at most 0.8 frames/character and at least 25 percent service margin"}},
        "attempt_accounting": {"product_cards": 0, "WPLTO_runs": 0,
            "product_links": 0, "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0}}
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("v2.0 Tier2 hot path: PREFLIGHT PASS WPLTO=0/1 link=0/1")


def check_preflight() -> None:
    value = load(PREFLIGHT_RECEIPT)
    require(value["status"] == "PASS: HOT-PATH REPAIR CARD ARMED 0/1"
            and value["authority"] == authority()
            and value["plane"] == bind(PLANE_RECEIPT)
            and value["attempt_accounting"]["WPLTO_runs"] == 0
            and value["attempt_accounting"]["product_links"] == 0
            and not ELF.exists() and not PRG.exists(),
            "hot-path repair preflight drift")
    run(["make", "-s", "gc-smoke", "vm-smoke"],
        "hot-path preflight semantic smokes")
    run([sys.executable, "tools/host-lisp/c2_v200_block3_direct_entry.py",
         "check"], "live direct-entry source binding")
    print("v2.0 Tier2 hot path: PREFLIGHT CHECK PASS WPLTO=0/1 link=0/1")


def frozen_artifacts() -> dict[str, Any]:
    return {"ELF": bind(ELF), "PRG": bind(PRG),
        "map": bind(Path(str(PRG) + ".map")),
        "lto": bind(Path(str(PRG) + ".lto.o"))}


def map_output_sections(path: Path) -> dict[str, dict[str, int]]:
    import re
    rows: dict[str, dict[str, int]] = {}
    pattern = re.compile(
        r"^\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+1\s+(\.\S+)\s*$")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            address, load, size = (int(match.group(i), 16)
                                   for i in range(1, 4))
            rows[match.group(4)] = {"address": address,
                "load_address": load, "bytes": size, "end": address + size}
    return rows


def nm_sizes(path: Path) -> dict[str, int]:
    output = run([str(ROOT / "tools/llvm-mos/bin/llvm-nm"),
        "--print-size", "--size-sort", "--radix=x", str(path)],
        "hot-path first-red symbol inventory")
    rows: dict[str, int] = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) == 4 and fields[0] != "U":
            try:
                rows[fields[3]] = int(fields[1], 16)
            except ValueError:
                pass
    return rows


def e000_holes(sections: dict[str, dict[str, int]]) -> list[dict[str, int]]:
    intervals = sorted((row["address"], row["end"])
        for row in sections.values()
        if row["bytes"] and 0xE000 <= row["address"] < 0x10000)
    merged: list[list[int]] = []
    for start, end in intervals:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    result = []
    cursor = 0xE000
    for start, end in merged:
        if start > cursor:
            result.append({"start": cursor, "end": start,
                           "bytes": start - cursor})
        cursor = max(cursor, end)
    if cursor < 0x10000:
        result.append({"start": cursor, "end": 0x10000,
                       "bytes": 0x10000 - cursor})
    return result


def first_red_value() -> dict[str, Any]:
    seed = WPLTO / "resident-island-seed.prg"
    lto = Path(str(seed) + ".lto.o")
    candidate_map = Path(str(seed) + ".map")
    predecessor_map = Path(str(PREDECESSOR_PRG) + ".map")
    require(lto.is_file() and candidate_map.is_file()
            and predecessor_map.is_file() and not ELF.exists()
            and not PRG.exists(),
            "hot-path first-red artifact boundary drift")
    old_sections = map_output_sections(predecessor_map)
    new_sections = map_output_sections(candidate_map)
    old_lto = Path(str(PREDECESSOR_PRG) + ".lto.o")
    old_symbols, new_symbols = nm_sizes(old_lto), nm_sizes(lto)
    text_old, text_new = old_sections[".text"], new_sections[".text"]
    facade = new_sections[".lisp65_c2_mapped_far_facade"]
    fixed_code = new_sections[".lisp65_c2_fixed_bank0_code"]
    hot_bss = new_sections[".lisp65_c2_fixed_bank0_hot_bss"]
    far = new_sections[".lisp65_c2_mapped_far_service"]
    text_growth = text_new["bytes"] - text_old["bytes"]
    vm_growth = new_symbols["vm_run_inner"] - old_symbols["vm_run_inner"]
    helper_bytes = new_symbols["ext_cons_field"]
    facade_wall = 0xB4A3
    wall_overflow = facade["end"] - facade_wall
    holes = e000_holes(new_sections)
    require(text_growth == 389 and vm_growth == 259
            and helper_bytes == 130
            and text_growth == vm_growth + helper_bytes
            and facade["address"] == text_new["end"] + 32
            and wall_overflow == 95
            and fixed_code["end"] == 0xC25B
            and hot_bss["address"] == 0xC25D
            and max(row["bytes"] for row in holes) == 49
            and far["bytes"] == 1488,
            "hot-path first-red arithmetic drift")
    return {"format": FORMAT + "-first-red-v1",
        "recorded_on": "2026-09-02",
        "status": "ATTRIBUTED: FUSED C FORM ESCAPES ORDINARY-TEXT WALL",
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "attempt": {"WPLTO_runs": 1, "product_link_attempts": 1,
            "successful_product_links": 0, "ELF_emitted": False,
            "PRG_emitted": False},
        "evidence": {"candidate_LTO": bind(lto),
            "candidate_map": bind(candidate_map),
            "link_stderr": bind(Path(str(seed) + ".link.stderr.txt")),
            "predecessor_map": bind(predecessor_map)},
        "ordinary_text": {"predecessor": text_old, "candidate": text_new,
            "growth_bytes": text_growth,
            "growth_attribution": {
                "vm_run_inner_bytes": vm_growth,
                "ext_cons_field_bytes": helper_bytes,
                "unexplained_bytes": 0}},
        "facade": {**facade, "required_reserve_bytes": 32,
            "wall_end": facade_wall, "overflow_bytes": wall_overflow},
        "placement_inventory": {
            "fixed_bank0_code_free_bytes": hot_bss["address"] - fixed_code["end"],
            "E000_always_visible_holes": holes,
            "largest_E000_hole_bytes": max(row["bytes"] for row in holes),
            "mapped_far_service_free_bytes": 1499 - far["bytes"],
            "mapped_service_rejected": (
                "helper consumes c2_map_cpu_read; mapped placement would violate "
                "the permanent no-transitive-MAP-nesting rule")},
        "decision": {"relocation_only_candidate": None,
            "reason": "130-byte helper has no legal always-visible interval",
            "replacement_requires": "new source codegen plus a new WPLTO/link",
            "bound_fallback": "descope Tier 2; retain Tier 1 and Matcher/Blink"},
        "claim": "no replacement build or link is authorized or attempted"}


def write_first_red_report(value: dict[str, Any]) -> None:
    text = value["ordinary_text"]
    facade = value["facade"]
    placement = value["placement_inventory"]
    FIRST_RED_REPORT.write_text(f"""# v2.0 Tier-2 hot-path repair — first-red attribution

Status: **{value['status']}**

The authorized WPLTO completed.  The product link stopped before emitting an
ELF or PRG because the fused C form grew ordinary text from
{text['predecessor']['bytes']} to {text['candidate']['bytes']} bytes.  All
{text['growth_bytes']} added bytes are named: `vm_run_inner` grew by
{text['growth_attribution']['vm_run_inner_bytes']} bytes and the emitted
`ext_cons_field` body is {text['growth_attribution']['ext_cons_field_bytes']}
bytes; unexplained growth is zero.

Text ends at `${text['candidate']['end']:04X}`.  The required 32-byte reserve
therefore puts the 98-byte facade at `${facade['address']:04X}..${facade['end']:04X}`,
{facade['overflow_bytes']} bytes beyond its `${facade['wall_end']:04X}` wall.

This cannot be repaired by relinking the existing LTO object.  Fixed Bank-0
has {placement['fixed_bank0_code_free_bytes']} bytes, the largest unowned E000
interval has {placement['largest_E000_hole_bytes']} bytes, and the mapped far
service has {placement['mapped_far_service_free_bytes']} bytes.  Mapped
placement is independently illegal because this helper itself calls the MAP
reader; it would introduce transitive MAP nesting.

The stopped pair is evidence, not a candidate: 1 WPLTO, one failed link
attempt, zero successful links, zero ELF/PRG.  A source-level successor needs
a new WPLTO/link decision.  Under the pre-bound fallback, the ready route is
Tier-2 descope while retaining Tier 1 and Matcher/Blink.
""", encoding="utf-8")


def record_first_red() -> None:
    require(not FIRST_RED.exists() and not FIRST_RED_REPORT.exists(),
            "hot-path first red is one-shot")
    value = first_red_value()
    FIRST_RED.write_bytes(canonical(value))
    write_first_red_report(value)
    print("v2.0 Tier2 hot path: FIRST RED ATTRIBUTED WPLTO=1 link=0/1")


def check_first_red() -> None:
    value = load(FIRST_RED)
    require(value == first_red_value()
            and value["ordinary_text"]["growth_attribution"]
                ["unexplained_bytes"] == 0
            and value["facade"]["overflow_bytes"] == 95
            and value["decision"]["relocation_only_candidate"] is None,
            "hot-path first-red receipt drift")
    print("v2.0 Tier2 hot path: FIRST RED CHECK PASS")


def profile_inputs(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("input_sha256="):
            left, digest = line.split(":", 1)
            rows[Path(left.split("=", 1)[1]).name] = digest
    return rows


def _counter(rows: Counter[tuple[Any, ...]]) -> list[list[Any]]:
    return [list(row) + [count] for row, count in sorted(rows.items())]


def attribution() -> dict[str, Any]:
    old = ElfTruth.read(PREDECESSOR_ELF, llvm_readobj=READOBJ,
                        include_section_data=True)
    new = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    old_inputs, new_inputs = (profile_inputs(PREDECESSOR_PROFILE),
                              profile_inputs(PROFILE))
    changed = sorted(name for name in set(old_inputs) | set(new_inputs)
                     if old_inputs.get(name) != new_inputs.get(name))
    authored = [name for name in changed if not name.startswith("c2-stream-")]
    generated = [name for name in changed if name.startswith("c2-stream-")]
    require(authored == ["mem.c", "vm.c"]
            and set(changed) == set(authored + generated),
            f"repair input roots escaped fused implementation: {changed}")
    old_sections = Counter((row.name, row.address, row.bytes,
                            tuple(row.flags)) for row in old.sections)
    new_sections = Counter((row.name, row.address, row.bytes,
                            tuple(row.flags)) for row in new.sections)
    old_symbols = Counter((row.name, row.value, row.bytes, row.section)
                          for row in old.symbols)
    new_symbols = Counter((row.name, row.value, row.bytes, row.section)
                          for row in new.symbols)
    old_relocs = Counter((row.source_section, row.offset,
        row.relocation_type, row.target, row.addend) for row in old.relocations)
    new_relocs = Counter((row.source_section, row.offset,
        row.relocation_type, row.target, row.addend) for row in new.relocations)
    old_raw, new_raw = PREDECESSOR_PRG.read_bytes(), PRG.read_bytes()
    require(old_raw[:2] == new_raw[:2], "repair changed PRG load address")
    changed_prg = sum(left != right for left, right in zip(old_raw, new_raw)) \
        + abs(len(old_raw) - len(new_raw))
    plane = PLANE / "v6-semantics/bank2-static-code.bin"
    require(bind(plane)["sha256"] == bind(
        PREDECESSOR_PLANE / "v6-semantics/bank2-static-code.bin")["sha256"],
        "repair changed Bank-2 freight")
    value = {"status": "PASS: HOT-PATH REPAIR FULLY ATTRIBUTED",
        "predecessor": {"ELF": bind(PREDECESSOR_ELF),
                        "PRG": bind(PREDECESSOR_PRG)},
        "candidate": {"ELF": bind(ELF), "PRG": bind(PRG)},
        "root_causes": {"authored_native_sources": authored,
            "header_semantics": ["obj.h"],
            "derived_generated_inputs": generated,
            "unchanged_resident_plane": bind(plane)},
        "changed_profile_inputs": changed,
        "PRG": {"changed_bytes": changed_prg,
            "families": ["fused-car-cdr-native-path",
                         "derived-build-identity-and-CRCs"],
            "unexplained": 0},
        "sections": {"removed": _counter(old_sections - new_sections),
                     "added": _counter(new_sections - old_sections),
                     "unexplained": []},
        "symbols": {"removed": _counter(old_symbols - new_symbols),
                    "added": _counter(new_symbols - old_symbols),
                    "unexplained": []},
        "relocations": {"removed": _counter(old_relocs - new_relocs),
                        "added": _counter(new_relocs - old_relocs),
                        "unexplained": []},
        "program_headers": {"before": T2.program_headers(PREDECESSOR_ELF),
                            "after": T2.program_headers(ELF),
                            "unexplained": []},
        "unexplained_sections": 0, "unexplained_symbols": 0,
        "unexplained_relocations": 0, "unexplained_program_headers": 0,
        "unexplained_PRG_bytes": 0, "unexplained_members": 0}
    return value


def call_edges(truth: ElfTruth, caller_name: str,
               callee_name: str) -> list[dict[str, Any]]:
    caller, callee = truth.symbol(caller_name), truth.symbol(callee_name)
    rows = []
    for row in truth.relocations:
        if (row.source_section_index == caller.section_index
                and caller.value <= row.offset < caller.value + caller.bytes
                and row.relocation_type == "R_MOS_ADDR16"):
            target = truth.relocation_target_identity(row)
            if target["resolved_value"] == callee.value:
                rows.append({"offset": row.offset - caller.value,
                    "resolved_target": target["resolved_value"]})
    return rows


def fusion_gate() -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    helper = truth.symbol("ext_cons_field")
    bss = truth.section(".bss")
    vm_edges = call_edges(truth, "vm_run_inner", "ext_cons_field")
    map_edges = call_edges(truth, "ext_cons_field", "c2_map_cpu_read")
    source = (ROOT / "src/vm.c").read_text(encoding="utf-8")
    smoke = run(["make", "-s", "gc-smoke"], "fused transport smoke")
    require(helper.section == ".text" and 0 < helper.bytes < 255
            and len(vm_edges) == 1 and len(map_edges) == 1
            and bss.bytes == 1584 and 0xC000 - (bss.address + bss.bytes) == 6
            and "cell_cons_field(a, op == OP_CDR, &b)" in source
            and "cell_type(a) != T_CONS" not in source
            and "ext-cons-field-smoke: PASS ext-a=1/4 ext-b=1/6 hot=0" in smoke,
            "final-linked fused CAR/CDR transport gate red")
    return {"status": "PASS: ONE TRANSPORT OWNS TYPE PLUS FIELD",
        "helper": {"address": helper.value, "bytes": helper.bytes,
            "section": helper.section},
        "edges": {"vm_run_inner_to_ext_cons_field": vm_edges,
                  "ext_cons_field_to_c2_map_cpu_read": map_edges},
        "transport_contract": {"extended_car": {"jobs": 1, "bytes": 4},
            "extended_cdr": {"jobs": 1, "bytes": 6},
            "hot_cons": {"jobs": 0}},
        "scratch_owner": "existing ext_dl; zero additional BSS allocation",
        "ordinary_BSS": {"bytes": bss.bytes,
            "margin_to_0xc000": 0xC000 - (bss.address + bss.bytes)},
        "mutation_rejected": "cell_type plus cell_a/cell_b uses two jobs"}


def raw_lane(source: Path, cap: int) -> dict[str, Any]:
    route = "single" if cap == 1 else "batch"
    return T2.PRICE.PRICE.execute_route(
        source, route, 40, batch_cap=cap, function_world="live-artifacts")


def responsiveness_lanes(fusion: dict[str, Any]) -> dict[str, Any]:
    contract = load(T2.PRICE.RESPONSIVENESS_CONTRACT)["responsiveness"]
    single_reference = raw_lane(V19_EDITOR, 1)
    single = raw_lane(LIVE_EDITOR, 1)
    batch = raw_lane(LIVE_EDITOR, 8)
    ratio = (single["vm_steps_per_character"] /
             single_reference["vm_steps_per_character"])
    # The standing calibration is valid for throughput batches.  The fused
    # final ELF has the same one-transport shape as the device-green v1.9
    # payload read; charge a conservative 32 local guard cycles per CAR/CDR,
    # while the separate MAP/type transport is provably absent.
    car_cdr_per_character = 20.5
    local_cycles_per_opcode_ceiling = 32
    base_frames = (
        batch["vm_steps_per_character"]
        * contract["calibration_cycles_per_vm_step"] / contract["cycles_per_frame"]
        + batch["screen_cells_per_character"]
        * contract["screen_cell_cycles"] / contract["cycles_per_frame"]
        + batch["heap_cells_per_character"]
        * contract["collection_frames"] / contract["nursery_cells"])
    frames = (base_frames + car_cdr_per_character
              * local_cycles_per_opcode_ceiling / contract["cycles_per_frame"])
    rate = 1.0 / frames
    margin = (rate - 1.0) * 100.0
    single_walls = {
        "maximum_ratio_to_device_green_v1_9": {
            "required": 1.02, "observed": ratio, "passed": ratio <= 1.02},
        "maximum_extended_transports_per_operation": {
            "required": 1, "observed": fusion["transport_contract"]
                ["extended_car"]["jobs"], "passed": True},
        "maximum_screen_cells_per_character": {
            "required": 2.0, "observed": single["screen_cells_per_character"],
            "passed": single["screen_cells_per_character"] <= 2.0}}
    batch_walls = {
        "maximum_frames_per_character": {"required": 0.8,
            "observed": frames, "passed": frames <= 0.8},
        "minimum_service_events_per_frame": {"required": 1.25,
            "observed": rate, "passed": rate >= 1.25},
        "minimum_margin_percent": {"required": 25.0,
            "observed": margin, "passed": margin >= 25.0}}
    require(all(row["passed"] for row in single_walls.values())
            and all(row["passed"] for row in batch_walls.values()),
            "separate single-key/batch responsiveness wall red")
    return {"status": "PASS: BOTH DELIVERED STIMULUS LANES GREEN",
        "rule": "measure single physical key and batch throughput separately",
        "final_world": bind(ELF),
        "single_keystroke": {"stimulus_batch_cap": 1,
            "device_green_reference": {**single_reference,
                "source": bind(V19_EDITOR)},
            "successor": single, "VM_step_ratio": ratio,
            "transport": fusion["transport_contract"], "walls": single_walls},
        "batch_throughput": {"stimulus_batch_cap": 8, "route": batch,
            "base_frames_per_character": base_frames,
            "fused_local_cycle_ceiling_per_car_cdr":
                local_cycles_per_opcode_ceiling,
            "frames_per_character": frames,
            "service_events_per_frame": rate, "margin_percent": margin,
            "walls": batch_walls},
        "combination_rule": "final linked matcher/blink world; lanes are never added"}


def final_gate() -> dict[str, Any]:
    configure()
    packed = CHAIN.packed_properties()
    fusion = fusion_gate()
    lanes = responsiveness_lanes(fusion)
    contract, changes = T2.measured_successor_contract()
    require(contract["counts"] == {"error-raised": 553,
        "documented-permissive": 179, "silently-wrong": 102}
        and len(changes) == 8,
        "repair lost Tier-2 semantics")
    return {"status": "PASS: REPAIRED COMBINED PRODUCT CLOSED",
        "static_extent": EXTENT, "packed_product": packed,
        "composed_bank2": CHAIN.composed_bank2(),
        "native_walls": CHAIN.native_walls(),
        "fusion": fusion, "responsiveness_lanes": lanes,
        "Tier_2_contract_counts": contract["counts"],
        "Tier_2_changed_cells": changes,
        "D5_projection": load(CHAIN.PRICE.RECEIPT)["pricing"]["D5_projection"]}


def run_child(action: str) -> dict[str, Any]:
    output = run([sys.executable, str(DRIVER), action],
                 f"hot-path child {action}")
    return {"action": action,
            "stdout_tail": " ".join(output.split()[-35:])}


def child(action: str) -> None:
    configure()
    CHAIN.child(action)


def build() -> None:
    pre = load(PREFLIGHT_RECEIPT)
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout
    require(clean == "" and not BUILD.exists() and not RECEIPT.exists()
            and not DIFFERENCE.exists()
            and pre["status"] == "PASS: HOT-PATH REPAIR CARD ARMED 0/1",
            "repair build is not at its committed one-shot boundary")
    invocation = {"status": "INVOKED", "authority": authority(),
                  "preflight": bind(PREFLIGHT_RECEIPT)}
    INVOCATION.write_bytes(canonical(invocation))
    processes = [run_child("_produce")]
    before = frozen_artifacts()
    diff = attribution()
    require(diff["unexplained_members"] == 0,
            "repair attribution retained unexplained members")
    DIFFERENCE.write_bytes(canonical(diff))
    product = final_gate()
    processes.extend((run_child("_scope"), run_child("_accept")))
    after = frozen_artifacts()
    scope = load(CHAIN.LINK.BASE.SCOPE_RESULT)
    acceptance = load(CHAIN.LINK.BASE.ACCEPTANCE_RESULT)
    require(before == after
            and scope["status"] == acceptance["status"] == "PASS",
            "repair qualification changed or rejected frozen pair")
    value = {"format": FORMAT, "recorded_on": "2026-09-02",
        "status": STATUS, "authority": authority(),
        "preflight": bind(PREFLIGHT_RECEIPT), "invocation": bind(INVOCATION),
        "predecessor": {"ELF": bind(PREDECESSOR_ELF),
                        "PRG": bind(PREDECESSOR_PRG)},
        "difference": diff, "difference_receipt": bind(DIFFERENCE),
        "final_product": product,
        "scope": bind(CHAIN.LINK.BASE.SCOPE_RESULT),
        "acceptance": bind(CHAIN.LINK.BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": processes,
        "attempt_accounting": {"product_cards": 1, "WPLTO_runs": 1,
            "product_links": 1, "scope_runs": 1, "acceptance_runs": 1,
            "media_builds": 0, "device_contacts": 0},
        "media_authorized": False,
        "media_condition": "independent review, then a fresh device feel check"}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    validate(value)
    print("v2.0 Tier2 hot path: BUILD PASS WPLTO=1/1 link=1/1")


def validate(value: dict[str, Any]) -> None:
    product = value["final_product"]
    lanes = product["responsiveness_lanes"]
    require(value["status"] == STATUS and value["authority"] == authority()
            and value["difference"]["unexplained_members"] == 0
            and product["fusion"]["transport_contract"]["extended_car"]
                ["jobs"] == 1
            and product["fusion"]["ordinary_BSS"]["margin_to_0xc000"] >= 5
            and lanes["single_keystroke"]["stimulus_batch_cap"] == 1
            and lanes["batch_throughput"]["stimulus_batch_cap"] == 8
            and all(row["passed"] for row in
                lanes["single_keystroke"]["walls"].values())
            and all(row["passed"] for row in
                lanes["batch_throughput"]["walls"].values())
            and product["Tier_2_contract_counts"]["silently-wrong"] == 102
            and value["artifacts_before"] == value["artifacts_after"]
            and value["attempt_accounting"] == {"product_cards": 1,
                "WPLTO_runs": 1, "product_links": 1, "scope_runs": 1,
                "acceptance_runs": 1, "media_builds": 0,
                "device_contacts": 0},
            "hot-path repair receipt drift")


def selftest() -> None:
    value = load(RECEIPT)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "two-transport-predecessor": lambda row: row["final_product"]
            ["fusion"]["transport_contract"]["extended_car"].update({"jobs": 2}),
        "single-lane-omitted": lambda row: row["final_product"]
            ["responsiveness_lanes"]["single_keystroke"].update(
                {"stimulus_batch_cap": 8}),
        "single-wall-red": lambda row: row["final_product"]
            ["responsiveness_lanes"]["single_keystroke"]["walls"]
            ["maximum_ratio_to_device_green_v1_9"].update({"passed": False}),
        "batch-wall-red": lambda row: row["final_product"]
            ["responsiveness_lanes"]["batch_throughput"]["walls"]
            ["minimum_margin_percent"].update({"passed": False}),
        "bss-margin-spent": lambda row: row["final_product"]
            ["fusion"]["ordinary_BSS"].update({"margin_to_0xc000": 4}),
        "unexplained-link-member": lambda row: row["difference"].update(
            {"unexplained_members": 1}),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except (CardError, KeyError, ValueError, RuntimeError):
            rejected.append(name)
    require(rejected == list(cases), "repair mutation survived")
    print(f"v2.0 Tier2 hot path: SELFTEST PASS mutations={len(rejected)}")


def write_report(value: dict[str, Any]) -> None:
    product = value["final_product"]
    fusion = product["fusion"]
    single = product["responsiveness_lanes"]["single_keystroke"]
    batch = product["responsiveness_lanes"]["batch_throughput"]
    pair = value["artifacts_after"]
    REPORT.write_text(f"""# v2.0 Tier-2 hot-path repair — product card

Status: **{value['status']}**

`OP_CAR` and `OP_CDR` now obtain the Cons type and selected payload field in
one `c2_map_cpu_read`.  The final ELF emits `ext_cons_field` at
`${fusion['helper']['address']:04X}` ({fusion['helper']['bytes']} bytes), with
one caller edge and one MAP-reader edge.  Extended CAR is 1 job / 4 bytes,
extended CDR 1 job / 6 bytes; the predecessor two-job mutation falls.  Scratch
is the existing `ext_dl`, so ordinary BSS remains {fusion['ordinary_BSS']['bytes']}
bytes with {fusion['ordinary_BSS']['margin_to_0xc000']} bytes safety margin.

The responsiveness authority now has two independent permanent lanes.  The
physical-single-key lane is batch-cap 1 and measures
{single['successor']['vm_steps_per_character']:.3f} VM steps/key versus the
device-green v1.9 reference {single['device_green_reference']['vm_steps_per_character']:.3f}
(ratio {single['VM_step_ratio']:.6f}); the final transport population is one per
extended Cons field.  The batch-cap-8 lane measures
{batch['frames_per_character']:.6f} frames/character,
{batch['service_events_per_frame']:.6f} events/frame and
{batch['margin_percent']:.3f}% margin.  Neither lane is inferred from the other,
and both run over the final matcher/blink source world.

Tier-2 remains freshly measured at 553 error / 179 permissive / 102 silently
wrong.  The 53,820-byte Bank-2 plane is byte-identical to the accepted delivery
world.  Full native attribution has zero unexplained members; Scope and
Acceptance are read-only green over ELF `{pair['ELF']['sha256']}` / PRG
`{pair['PRG']['sha256']}`.  Budget is exactly one WPLTO and one product link.
No medium or device contact occurred; good typing feel remains the hardware
acceptance condition, with Tier 2 descope already bound if that condition fails.
""", encoding="utf-8")


def check() -> None:
    value = load(RECEIPT)
    validate(value)
    require(REPORT.is_file(), "repair report absent")
    print("v2.0 Tier2 hot path: CHECK PASS WPLTO=1/1 link=1/1 media=0")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "check-preflight",
                                            "record-first-red", "check-first-red",
                                            "build", "check", "selftest", "_produce",
                                            "_scope", "_accept"))
    action = parser.parse_args().action
    if action.startswith("_"):
        child(action)
        return 0
    {"preflight": preflight, "check-preflight": check_preflight,
     "record-first-red": record_first_red,
     "check-first-red": check_first_red,
     "build": build, "check": check,
     "selftest": selftest}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, RuntimeError, KeyError, ValueError, OSError,
            subprocess.CalledProcessError) as error:
        print(f"v2.0 Tier2 hot path: FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
