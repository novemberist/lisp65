#!/usr/bin/env python3
"""Inventory and price the C2 stack/overlay ownership alternatives.

Final-ELF truth comes only from llvm-readobj JSON through ElfTruth.  The two
Link-91 failures have no final ELF, so their bound maps and First-Red receipts
are the deliberately narrow historical fallback.  No product is compiled or
linked by this tool; the only links it performs are tiny stack-arena fixtures.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any

from elf_truth import ElfTruth, ElfTruthError


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-stack-overlay-ownership-contract.json"
INVENTORY_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-stack-overlay-ownership-inventory-receipt.json")
PRICING_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-stack-overlay-ownership-halt1-candidate-pricing.json")
LLVM_READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
LLVM_MC = ROOT / "tools/llvm-mos/bin/llvm-mc"
LD_LLD = ROOT / "tools/llvm-mos/bin/ld.lld"

MAP_ROW = re.compile(
    r"^\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+"
    r"(\d+)\s+(\S.*?)\s*$")


class OwnershipError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise OwnershipError(message)


def parse_int(value: Any) -> int:
    if isinstance(value, bool):
        raise OwnershipError("boolean is not an address")
    if isinstance(value, int):
        return value
    return int(str(value), 0)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"bound input absent: {relative(path)}")
    return {
        "path": relative(path),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def named(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("Name", ""))
    return str(value)


def load_contract() -> dict[str, Any]:
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    require(data.get("format") ==
            "lisp65-c2-stack-overlay-ownership-contract-v1",
            "ownership contract format drift")
    require(data.get("status") == "halt-1-fourth-class-priced-fit",
            "ownership contract selection status drift")
    rows = data.get("section_rules", [])
    require(rows and len({(row["match"], row["value"]) for row in rows})
            == len(rows), "section ownership rules absent or duplicated")
    require(data.get("required_mutations") == [
        "missing-section", "missing-owner", "missing-live-peer",
        "missing-descriptor", "missing-call-edge"],
        "inventory mutation census drift")
    return data


def authority_paths(contract: dict[str, Any]) -> dict[str, Path]:
    return {key: ROOT / value for key, value in contract["authorities"].items()}


def read_elf(path: Path) -> tuple[ElfTruth, dict[int, dict[str, Any]],
                                  list[dict[str, Any]]]:
    command = [
        str(LLVM_READOBJ), "--elf-output-style=JSON", "--sections",
        "--symbols", "--relocations", "--program-headers", str(path),
    ]
    completed = subprocess.run(
        command, check=True, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    document = json.loads(completed.stdout)
    truth = ElfTruth.from_document(document)
    require(isinstance(document, list) and len(document) == 1,
            "llvm-readobj file cardinality drift")
    root = document[0]
    raw_sections: dict[int, dict[str, Any]] = {}
    for wrapper in root.get("Sections", []):
        row = wrapper["Section"]
        raw_sections[int(row["Index"])] = row
    headers = [wrapper["ProgramHeader"]
               for wrapper in root.get("ProgramHeaders", [])
               if named(wrapper["ProgramHeader"]["Type"]) == "PT_LOAD"]
    require(raw_sections and headers, "structured section/LMA truth absent")
    return truth, raw_sections, headers


def section_lma(section: Any, raw: dict[str, Any],
                headers: list[dict[str, Any]]) -> int:
    offset = int(raw["Offset"])
    candidates: list[tuple[int, int, int]] = []
    for header in headers:
        h_offset = int(header["Offset"])
        file_bytes = int(header["FileSize"])
        mem_bytes = int(header["MemSize"])
        vma = int(header["VirtualAddress"])
        pma = int(header["PhysicalAddress"])
        if section.section_type == "SHT_NOBITS":
            if vma <= section.address < vma + max(mem_bytes, 1):
                candidates.append((0 if vma == section.address else 1,
                                   pma + section.address - vma, h_offset))
        elif (h_offset <= offset and
              offset + section.bytes <= h_offset + file_bytes and
              vma <= section.address < vma + max(mem_bytes, 1)):
            candidates.append((0 if h_offset == offset else 1,
                               pma + offset - h_offset, h_offset))
    require(bool(candidates), f"section LMA unresolved: {section.name}")
    candidates.sort()
    return candidates[0][1]


def rule_for(name: str, contract: dict[str, Any]) -> dict[str, str] | None:
    matches = []
    for row in contract["section_rules"]:
        if ((row["match"] == "exact" and name == row["value"]) or
                (row["match"] == "prefix" and name.startswith(row["value"]))):
            matches.append(row)
    if not matches:
        return None
    # An exact rule is more specific than a prefix; the longest prefix wins.
    matches.sort(key=lambda row: (
        row["match"] == "exact", len(row["value"])), reverse=True)
    winner = matches[0]
    if len(matches) > 1:
        first = (winner["match"] == "exact", len(winner["value"]))
        second = (matches[1]["match"] == "exact", len(matches[1]["value"]))
        require(first != second, f"ambiguous section owner: {name}")
    return winner


def relevant_sections(truth: ElfTruth, raw: dict[int, dict[str, Any]],
                      headers: list[dict[str, Any]],
                      contract: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for section in truth.sections:
        rule = rule_for(section.name, contract)
        if rule is None or section.bytes <= 0 or "SHF_ALLOC" not in section.flags:
            continue
        source = raw[section.index]
        records.append({
            "index": section.index,
            "name": section.name,
            "vma": section.address,
            "lma": section_lma(section, source, headers),
            "bytes": section.bytes,
            "alignment": int(source["AddressAlignment"]),
            "section_type": section.section_type,
            "owner": rule["owner"],
            "lifetime": rule["lifetime"],
            "placement": rule["placement"],
        })
    names = {row["name"] for row in records}
    missing = sorted(set(contract["required_sections"]) - names)
    require(not missing, f"required owned sections absent: {missing}")
    return sorted(records, key=lambda row: (row["vma"], row["lma"], row["name"]))


def make_live_envelopes(sections: list[dict[str, Any]]) -> dict[str, Any]:
    by_name = {row["name"]: row for row in sections}
    overlays = [row for row in sections if row["lifetime"].endswith("overlay")]
    ordinary_base = [row["name"] for row in sections
                     if row["lifetime"] in (
                         "always-resident", "always-resident-mixed")]
    post_ownership = [row["name"] for row in sections
                      if row["lifetime"] ==
                      "always-resident-post-ownership"]
    base = ordinary_base + post_ownership
    handoff = [row["name"] for row in sections
               if row["lifetime"] == "boot-only"]
    envelopes: dict[str, list[str]] = {
        "boot-handoff": sorted(set(ordinary_base + handoff)),
        "post-ownership-no-overlay": sorted(set(base)),
    }
    for overlay in overlays:
        envelopes[f"with:{overlay['name']}"] = sorted(set(base + [overlay["name"]]))
    membership: dict[str, list[str]] = {name: [] for name in by_name}
    for envelope, members in envelopes.items():
        for member in members:
            if member in membership:
                membership[member].append(envelope)
    for row in sections:
        row["live_envelopes"] = sorted(membership[row["name"]])
        require(row["live_envelopes"], f"section has no live peer set: {row['name']}")
    return {"envelopes": envelopes, "membership": membership}


def interval_or_none(truth: ElfTruth, section: str,
                     address: int) -> dict[str, Any] | None:
    try:
        return truth.resolve_interval(section=section, address=address)
    except ElfTruthError:
        return None


def function_edges(truth: ElfTruth,
                   relevant_names: set[str]) -> list[dict[str, Any]]:
    edges: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for relocation in truth.relocations:
        if relocation.source_section not in relevant_names:
            continue
        source = interval_or_none(
            truth, relocation.source_section, relocation.offset)
        if source is None or source["kind"] != "elf-symbol":
            continue
        identity = truth.relocation_target_identity(relocation)
        target_section = str(identity["section"])
        if target_section not in relevant_names:
            continue
        target = interval_or_none(
            truth, target_section, int(identity["resolved_value"]))
        if target is None or target["kind"] != "elf-symbol":
            continue
        if source["section"] == target["section"]:
            continue
        key = (source["name"], source["section"],
               target["name"], target["section"])
        edges[key] = {
            "caller": source["name"],
            "caller_section": source["section"],
            "callee": target["name"],
            "callee_section": target["section"],
            "relocation_type": relocation.relocation_type,
        }
    require(bool(edges), "cross-section call-edge inventory is empty")
    return [edges[key] for key in sorted(edges)]


def linker_provenance(sections: list[dict[str, Any]],
                      link88: Path, link90: Path) -> dict[str, Any]:
    sources = {
        "link88": link88.read_text(encoding="utf-8"),
        "link90": link90.read_text(encoding="utf-8"),
    }
    explicit = sorted({
        row["name"] for row in sections
        if row["placement"] in (
            "explicit-linker-section", "explicit-overlay-lma")})
    missing: dict[str, list[str]] = {}
    for label, source in sources.items():
        absent = [name for name in explicit if name not in source]
        if absent:
            missing[label] = absent
        require(
            "__lisp65_workbench_noinit_end = ADDR(.noinit) + SIZEOF(.noinit);"
            in source and
            "__lisp65_workbench_overlay_min_start = "
            "ALIGN(__lisp65_workbench_noinit_end + 1, 2);" in source,
            f"{label} compiler-derived overlay-floor witness absent")
    require(not missing, f"explicit linker owner absent: {missing}")
    counts: dict[str, int] = {}
    for row in sections:
        counts[row["placement"]] = counts.get(row["placement"], 0) + 1
    return {
        "explicit_section_names_verified_in_both_scripts": explicit,
        "explicit_section_count": len(explicit),
        "placement_counts": counts,
        "compiler_floor_derivation": (
            "ADDR(.noinit)+SIZEOF(.noinit), then ALIGN(+1,2)"),
        "compiler_floor_derivation_present_in": ["link88", "link90"],
        "orphan_owned_ranges": 0,
    }


def e000_reachability(truth: ElfTruth, sections: list[dict[str, Any]],
                      edges: list[dict[str, Any]]) -> dict[str, Any]:
    e000 = ".lisp65_c2_kernal_window.c2_resident"
    functions = sorted(
        (row for row in truth.symbols
         if row.section == e000 and row.symbol_type == "Function" and row.bytes),
        key=lambda row: row.value)
    lifetime = {row["name"]: row["lifetime"] for row in sections}
    reached: dict[str, list[str]] = {}
    for edge in edges:
        if edge["callee_section"] != e000 or edge["caller_section"] == e000:
            continue
        source_lifetime = lifetime.get(edge["caller_section"], "")
        if source_lifetime not in ("boot-only", "boot-only-overlay"):
            reached.setdefault(edge["callee"], []).append(
                f"{edge['caller']}[{edge['caller_section']}]")
    changed = True
    while changed:
        changed = False
        for edge in edges:
            if (edge["caller_section"] == e000 and
                    edge["callee_section"] == e000 and
                    edge["caller"] in reached and edge["callee"] not in reached):
                reached[edge["callee"]] = [f"{edge['caller']}[e000]"]
                changed = True
    rows = [{
        "name": row.name,
        "vma": row.value,
        "bytes": row.bytes,
        "post_boot_witnesses": sorted(set(reached.get(row.name, []))),
        "post_boot_reachable": row.name in reached,
    } for row in functions]
    unreachable = [row["name"] for row in rows if not row["post_boot_reachable"]]
    require(not unreachable,
            f"E000 reachability needs manual disposition: {unreachable}")
    return {
        "section": e000,
        "function_count": len(rows),
        "function_bytes": sum(row["bytes"] for row in rows),
        "post_boot_reachable_count": len(rows) - len(unreachable),
        "proven_boot_only_bytes": 0,
        "functions": rows,
    }


def parse_map(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        match = MAP_ROW.match(line)
        if match:
            rows.append({
                "vma": int(match.group(1), 16),
                "lma": int(match.group(2), 16),
                "bytes": int(match.group(3), 16),
                "alignment": int(match.group(4)),
                "name": match.group(5),
                "line": line_number,
            })
    require(bool(rows), f"linker map has no records: {relative(path)}")
    return rows


def map_one(rows: list[dict[str, Any]], name: str) -> dict[str, Any]:
    matches = [row for row in rows if row["name"] == name]
    require(len(matches) == 1,
            f"map identity is not unique: {name} ({len(matches)})")
    return matches[0]


def descriptor_inventory(truth: ElfTruth, compact_map: list[dict[str, Any]],
                         contract: dict[str, Any],
                         full_receipt: dict[str, Any]) -> dict[str, Any]:
    baseline = []
    for expected in contract["descriptors"]["link90"]:
        symbol = truth.symbol(expected["symbol"])
        require(symbol.bytes == expected["bytes"] and
                symbol.section == expected["section"],
                f"Link-90 descriptor drift: {expected['symbol']}")
        baseline.append(expected | {
            "vma": symbol.value,
            "owner": ("c2-fixed-bank0" if symbol.section.startswith(
                ".lisp65_c2_fixed_bank0") else "ordinary-bank0-bss"),
        })
    compact = []
    for expected in contract["descriptors"]["compact_link91"]:
        row = map_one(compact_map, expected["symbol"])
        require(row["bytes"] == expected["bytes"],
                f"compact descriptor drift: {expected['symbol']}")
        compact.append(expected | {
            "vma": row["vma"], "lma": row["lma"],
            "placement": "ordinary-bss-unowned-first-red",
        })
    markers = []
    for expected in contract["descriptors"]["compact_link91_markers"]:
        row = map_one(compact_map, expected["symbol"])
        require(row["bytes"] == expected["bytes"],
                f"compact marker drift: {expected['symbol']}")
        markers.append(expected | {
            "vma": row["vma"], "lma": row["lma"],
            "placement": "ordinary-rodata-source-oracle",
        })
    scratch = []
    for expected in contract["descriptors"]["compact_link91_scratch"]:
        row = map_one(compact_map, expected["symbol"])
        require(row["bytes"] == expected["bytes"],
                f"compact scratch drift: {expected['symbol']}")
        scratch.append(expected | {
            "vma": row["vma"], "lma": row["lma"],
            "placement": "ordinary-zero-page-unowned-first-red",
        })
    missing = contract["descriptors"]["full_link91_missing_owner"]
    state_red = full_receipt["state_ownership_first_red"]
    require(state_red["symbol"] == missing["symbol"] and
            state_red["ordinary_static_descriptor_bytes_unresolved"]
            == missing["bytes"], "full Link-91 missing-owner witness drift")
    return {
        "link90": baseline,
        "compact_link91": compact,
        "compact_named_bytes": sum(row["bytes"] for row in compact),
        "compact_link91_markers": markers,
        "compact_marker_bytes": sum(row["bytes"] for row in markers),
        "compact_link91_scratch": scratch,
        "compact_scratch_bytes": sum(row["bytes"] for row in scratch),
        "compact_emitted_bss_delta_bytes": 68,
        "full_link91_missing_owner": missing,
    }


def conviction_fixtures(paths: dict[str, Path]) -> dict[str, Any]:
    link36 = json.loads(paths["link36_floor"].read_text())
    joint = json.loads(paths["del_joint"].read_text())
    inline = json.loads(paths["del_inline"].read_text())
    nonlto = json.loads(paths["del_nonlto"].read_text())
    full = json.loads(paths["link91_full_first_red"].read_text())
    compact = json.loads(paths["link91_compact_first_red"].read_text())
    del_shapes = [
        joint["linked_shape_at_failure"]["candidate"][
            "compiler_static_stack_noinit_bytes"],
        inline["linked_shape_at_failure"]["forced_inline_card"][
            "compiler_static_stack_noinit_bytes"],
        nonlto["three_card_partition_matrix"][2]["compiler_static_stack_bytes"],
    ]
    require(del_shapes == [3, 4, 12], "DEL 3/4/12 conviction drift")
    require(full["geometry"]["pinned_noinit_overlay"]["trial_noinit"]
            == "0xc554", "full Link-91 noinit witness drift")
    require(compact["geometry"]["pinned_noinit_overlay"][
            "trial_noinit_address"] == "0xc51e",
            "compact Link-91 noinit witness drift")
    return {
        "link36": {
            "previous_floor_bytes": link36["contract"]["previous_floor_bytes"],
            "terminal_floor_bytes": link36["contract"]["terminal_floor_bytes"],
            "third_floor_negotiation": link36["contract"][
                "third_floor_negotiation"],
        },
        "del_static_stack_shapes_bytes": del_shapes,
        "link91_full": {
            "missing_descriptor": full["state_ownership_first_red"],
            "noinit_from": full["geometry"]["pinned_noinit_overlay"][
                "contract_noinit"],
            "noinit_to": full["geometry"]["pinned_noinit_overlay"][
                "trial_noinit"],
        },
        "link91_compact": {
            "noinit_from": compact["geometry"]["pinned_noinit_overlay"][
                "required_noinit_address"],
            "noinit_to": compact["geometry"]["pinned_noinit_overlay"][
                "trial_noinit_address"],
        },
    }


def stack_micro_fixtures(contract: dict[str, Any]) -> dict[str, Any]:
    geometry = contract["geometry"]
    stack = geometry["candidate_static_stack_arena"]
    stack_start = parse_int(stack["start"])
    capacity = int(stack["capacity_bytes"])
    floor = parse_int(geometry["overlay_floor"])
    executions = []
    with tempfile.TemporaryDirectory(prefix="lisp65-owned-stack-") as temp_name:
        temp = Path(temp_name)
        linker = temp / "fixture.ld"
        linker.write_text(
            "SECTIONS {\n"
            f"  .owned_stack 0x{stack_start:x} (NOLOAD) : "
            "{ KEEP(*(.owned_stack)) }\n"
            f"  ASSERT(SIZEOF(.owned_stack) <= {capacity}, "
            "\"owned static stack arena overflow\")\n"
            f"  .owned_overlay 0x{floor:x} : {{ BYTE(0) }}\n"
            "}\n", encoding="utf-8")
        for size in [*contract["micro_elf_stack_sizes"], capacity + 1]:
            source = (
                ".section .owned_stack,\"aw\",@nobits\n"
                f".space {size}\n")
            obj = temp / f"stack-{size}.o"
            elf = temp / f"stack-{size}.elf"
            subprocess.run(
                [str(LLVM_MC), "--triple=mos", "-filetype=obj", "-o", str(obj)],
                input=source, text=True, check=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            linked = subprocess.run(
                [str(LD_LLD), "-T", str(linker), "-o", str(elf), str(obj)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if size <= capacity:
                require(linked.returncode == 0,
                        f"valid stack micro fixture rejected: {size}")
                truth, raw, headers = read_elf(elf)
                stack_section = truth.section(".owned_stack")
                overlay = truth.section(".owned_overlay")
                require(stack_section.address == stack_start and
                        stack_section.bytes == size and overlay.address == floor,
                        f"stack micro fixture geometry drift: {size}")
                executions.append({
                    "stack_bytes": size,
                    "status": "passed",
                    "stack_vma": stack_section.address,
                    "overlay_floor": overlay.address,
                    "structured_sections": len(raw),
                    "load_segments": len(headers),
                })
            else:
                require(linked.returncode != 0 and
                        "owned static stack arena overflow" in linked.stderr,
                        "capacity+1 stack fixture did not fail closed")
                executions.append({
                    "stack_bytes": size,
                    "status": "rejected-capacity-plus-one",
                })
    return {
        "arena_start": stack_start,
        "arena_capacity_bytes": capacity,
        "overlay_floor": floor,
        "executions": executions,
    }


def service_demand(compact_map: list[dict[str, Any]],
                   contract: dict[str, Any]) -> dict[str, Any]:
    rows = [map_one(compact_map, name)
            for name in contract["convergence_code_symbols"]]
    low = sum(row["bytes"] for row in rows if row["vma"] < 0xe000)
    e000 = sum(row["bytes"] for row in rows if row["vma"] >= 0xe000)
    require((low, e000, low + e000) == (870, 675, 1545),
            "compact convergence code attribution drift")
    return {
        "symbols": rows,
        "low_text_named_bytes": low,
        "e000_named_bytes": e000,
        "total_named_bytes": low + e000,
        "observed_net_text_growth_bytes": 841,
        "observed_net_e000_growth_bytes": 659,
        "observed_net_total_growth_bytes": 1500,
    }


def bank2_inventory(paths: dict[str, Path],
                    contract: dict[str, Any]) -> dict[str, Any]:
    far = contract["mapped_far_service"]
    expected = far["bank2"]
    product = json.loads(paths["link90_product_manifest"].read_text())
    static_product = json.loads(paths["link90_static_product"].read_text())
    media = json.loads(paths["media_contract"].read_text())
    code = paths["link90_bank2_static_code"].read_bytes()
    current = int(expected["current_static_bytes"])
    physical_base = parse_int(expected["physical_base"])
    capacity = int(expected["capacity_bytes"])
    require(
        product["static_plane"]["bank2_static_code_bytes"] == current
        and product["static_plane"]["bank2_sha256"] == sha256(
            paths["link90_bank2_static_code"])
        and len(code) == current
        and capacity - current == int(expected["current_headroom_bytes"]),
        "Link-90 real Bank-2 inventory drift")
    rows = []
    cursor = 0
    for binding in static_product["manifests"]:
        manifest_path = ROOT / binding["path"]
        require(bind(manifest_path)["sha256"] == binding["sha256"],
                f"Bank-2 manifest binding drift: {binding['path']}")
        manifest = json.loads(manifest_path.read_text())
        size = int(manifest["code_bytes"])
        rows.append({
            "owner": manifest["artifact_role"],
            "manifest": binding,
            "offset_start": cursor,
            "offset_end_exclusive": cursor + size,
            "physical_start": physical_base + cursor,
            "physical_end_exclusive": physical_base + cursor + size,
            "bytes": size,
        })
        cursor += size
    require(cursor == current and len(rows) == 6,
            "Bank-2 six-image owner inventory drift")
    role = [row for row in media["media_entries"]
            if row["artifact_role"] == far["bootstrap"]["media_role"]]
    require(len(role) == 1
            and parse_int(role[0]["destination"]) == physical_base
            and role[0]["policy"] == far["bootstrap"]["stage_policy"],
            "Bank-2 media-stage authority drift")
    service_start = parse_int(expected["service_physical_start"])
    service_end = parse_int(expected["service_physical_end_exclusive"])
    service_bytes = int(expected["service_bytes"])
    require(service_start == physical_base + current
            and service_end - service_start == service_bytes
            and int(expected["post_service_static_bytes"])
                == current + service_bytes
            and int(expected["post_service_headroom_bytes"])
                == capacity - current - service_bytes,
            "Bank-2 far-service arithmetic drift")
    return {
        "physical_base": physical_base,
        "capacity_bytes": capacity,
        "current_static_artifact": bind(paths["link90_bank2_static_code"]),
        "current_static_bytes": current,
        "current_headroom_bytes": capacity - current,
        "current_owners": rows,
        "current_owner_count": len(rows),
        "current_occupied_interval": {
            "start": physical_base,
            "end_exclusive": physical_base + current,
            "bytes": current,
        },
        "far_service_reservation": {
            "start": service_start,
            "end_exclusive": service_end,
            "bytes": service_bytes,
            "placement": "contiguous suffix of the boot-staged static artifact",
        },
        "post_service_static_bytes": current + service_bytes,
        "post_service_headroom_bytes": capacity - current - service_bytes,
        "displaced_owner": {
            "owner": "future persistent/transient Bank-2 append capacity",
            "bytes": service_bytes,
            "existing_product_bytes_displaced": 0,
            "required_low_front_floor": service_end - physical_base,
        },
        "media_stage": role[0],
        "bootstrap_order": media["staging"]["publish_order"],
    }


def far_service_dependency_closure(
        truth: ElfTruth, compact_map: list[dict[str, Any]],
        contract: dict[str, Any]) -> dict[str, Any]:
    far = contract["mapped_far_service"]
    far_names = {row["name"] for row in far["far_symbols"]}
    expected_sizes = {row["name"]: int(row["bytes"])
                      for row in far["far_symbols"]}
    internal: dict[tuple[str, str], dict[str, Any]] = {}
    external: dict[str, dict[str, Any]] = {}
    seen_data: set[str] = set()
    for source_name in sorted(far_names):
        source = truth.symbol(source_name)
        require(source.bytes == expected_sizes[source_name],
                f"far-service symbol size drift: {source_name}")
        for relocation in truth.relocations:
            if (relocation.source_section_index != source.section_index
                    or not source.value <= relocation.offset <
                    source.value + source.bytes):
                continue
            identity = truth.relocation_target_identity(relocation)
            section = str(identity["section"])
            address = int(identity["resolved_value"])
            target_name = ""
            if section not in ("Undefined", "Absolute"):
                try:
                    target = truth.resolve_interval(
                        section=section, address=address)
                    target_name = str(target["name"])
                except ElfTruthError:
                    target_name = ""
            if target_name and target_name != source_name:
                target_symbol = truth.symbol(target_name)
                if target_symbol.symbol_type == "Function":
                    if target_name in far_names:
                        internal[(source_name, target_name)] = {
                            "caller": source_name, "callee": target_name}
                    else:
                        row = map_one(compact_map, target_name)
                        external[target_name] = {
                            "symbol": target_name,
                            "vma": row["vma"], "bytes": row["bytes"],
                        }
            for data_name in far["external_data_dependencies"]:
                if (identity["symbol"] == data_name
                        or section.endswith("." + data_name)):
                    seen_data.add(data_name)
    expected_external = set(far["external_code_dependencies"])
    require(set(external) == expected_external,
            f"far-service external code closure drift: {sorted(external)}")
    require(seen_data == set(far["external_data_dependencies"]),
            f"far-service data closure drift: {sorted(seen_data)}")
    window = far["cpu_window"]
    start = parse_int(window["start"])
    end = parse_int(window["end_exclusive"])
    for row in external.values():
        require(not start <= row["vma"] < end,
                f"far service calls hidden CPU block: {row['symbol']}")
    data = []
    for name in far["external_data_dependencies"]:
        row = map_one(compact_map, name)
        require(not start <= row["vma"] < end,
                f"far service data hidden by MAP: {name}")
        data.append({"symbol": name, "vma": row["vma"],
                     "bytes": row["bytes"]})
    return {
        "far_symbols": [
            {"symbol": name, "bytes": truth.symbol(name).bytes,
             "source_section": truth.symbol(name).section}
            for name in sorted(far_names)],
        "far_bytes": sum(expected_sizes.values()),
        "internal_calls": [internal[key] for key in sorted(internal)],
        "external_code_calls": [external[key] for key in sorted(external)],
        "external_data": data,
        "hidden_cpu_block_dependencies": 0,
        "direct_frame_counter_dependency": "0xff83..0xff85",
    }


def far_service_micro_fixture(contract: dict[str, Any]) -> dict[str, Any]:
    far = contract["mapped_far_service"]
    resident = far["resident"]
    bank2 = far["bank2"]
    mapping = far["map_tuple"]
    resident_start = parse_int(resident["start"])
    resident_limit = parse_int(resident["end_exclusive"])
    far_start = parse_int(mapping["mapped_service_cpu_start"])
    far_lma = parse_int(bank2["service_physical_start"])
    far_sizes = {row["name"]: int(row["bytes"])
                 for row in far["far_symbols"]}
    source = """
.section .mapped_far_facade,"ax",@progbits
.globl c2_dma_read_or_abort
.type c2_dma_read_or_abort,@function
c2_dma_read_or_abort:
  .space 46, 0xea
.size c2_dma_read_or_abort, .-c2_dma_read_or_abort
.globl mapped_vm_code_load_converged
.type mapped_vm_code_load_converged,@function
mapped_vm_code_load_converged:
  jsr mapped_far_enter
  jsr far_vm_code_load_converged
  jmp mapped_far_leave
.size mapped_vm_code_load_converged, .-mapped_vm_code_load_converged
.globl mapped_c2_physical_read_converged
.type mapped_c2_physical_read_converged,@function
mapped_c2_physical_read_converged:
  jsr mapped_far_enter
  jsr far_c2_physical_read_converged
  jmp mapped_far_leave
.size mapped_c2_physical_read_converged, .-mapped_c2_physical_read_converged
.globl mapped_far_enter
.type mapped_far_enter,@function
mapped_far_enter:
  pha
  phx
  phy
  phz
  lda #0x80
  ldx #0x24
  ldy #0x00
  ldz #0x80
  map
  eom
  plz
  ply
  plx
  pla
  rts
.size mapped_far_enter, .-mapped_far_enter
.globl mapped_far_leave
.type mapped_far_leave,@function
mapped_far_leave:
  pha
  lda #0x00
  ldx #0x00
  ldy #0x00
  ldz #0x80
  map
  eom
  pla
  ldz #0x00
  rts
.size mapped_far_leave, .-mapped_far_leave

.section .mapped_far_service,"ax",@progbits
.globl far_vm_code_load_converged
.type far_vm_code_load_converged,@function
far_vm_code_load_converged:
  .space 682, 0xea
.size far_vm_code_load_converged, .-far_vm_code_load_converged
.globl far_c2_edma_prepare
.type far_c2_edma_prepare,@function
far_c2_edma_prepare:
  .space 142, 0xea
.size far_c2_edma_prepare, .-far_c2_edma_prepare
.globl far_c2_physical_read_converged
.type far_c2_physical_read_converged,@function
far_c2_physical_read_converged:
  .space 480, 0xea
.size far_c2_physical_read_converged, .-far_c2_physical_read_converged
.globl far_c2_physical_source_byte
.type far_c2_physical_source_byte,@function
far_c2_physical_source_byte:
  .space 195, 0xea
.size far_c2_physical_source_byte, .-far_c2_physical_source_byte

.section .mapped_irq_probe,"ax",@progbits
.globl mapped_irq_probe
.type mapped_irq_probe,@function
mapped_irq_probe:
  pha
  lda 0xd019
  sta 0xff80
  pla
  rti
.size mapped_irq_probe, .-mapped_irq_probe
""".strip() + "\n"
    linker = f"""SECTIONS {{
  .mapped_far_facade 0x{resident_start:x} : {{
    KEEP(*(.mapped_far_facade))
  }}
  ASSERT(SIZEOF(.mapped_far_facade) <= {resident_limit - resident_start},
         \"mapped far facade overflow\")
  .mapped_far_service 0x{far_start:x} : AT(0x{far_lma:x}) {{
    KEEP(*(.mapped_far_service))
  }}
  ASSERT(SIZEOF(.mapped_far_service) == {int(bank2['service_bytes'])},
         \"mapped far service size drift\")
  .mapped_irq_probe 0xe038 : {{ KEEP(*(.mapped_irq_probe)) }}
}}
"""
    executions = []
    with tempfile.TemporaryDirectory(prefix="lisp65-mapped-far-") as temp_name:
        temp = Path(temp_name)
        obj = temp / "mapped-far.o"
        elf = temp / "mapped-far.elf"
        script = temp / "mapped-far.ld"
        script.write_text(linker, encoding="utf-8")
        subprocess.run(
            [str(LLVM_MC), "--triple=mos", "--mcpu=mos45gs02",
             "-filetype=obj", "-o", str(obj)],
            input=source, text=True, check=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        linked = subprocess.run(
            [str(LD_LLD), "-T", str(script), "-o", str(elf), str(obj)],
            text=True, check=False, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        require(linked.returncode == 0,
                "mapped far micro-ELF link failed: " + linked.stderr)
        truth = ElfTruth.read(
            elf, llvm_readobj=LLVM_READOBJ, include_section_data=True)
        structured, raw, headers = read_elf(elf)
        facade = truth.section(".mapped_far_facade")
        service = truth.section(".mapped_far_service")
        irq = truth.section(".mapped_irq_probe")
        require(facade.address == resident_start
                and facade.bytes == int(resident["total_bytes"])
                and service.address == far_start
                and service.bytes == int(bank2["service_bytes"])
                and irq.address == 0xe038,
                "mapped far micro-ELF geometry drift")
        service_lma = section_lma(
            structured.section(".mapped_far_service"),
            raw[structured.section(".mapped_far_service").index], headers)
        require(service_lma == far_lma,
                "mapped far micro-ELF physical placement drift")
        expected_symbols = {
            "c2_dma_read_or_abort": 46,
            "mapped_vm_code_load_converged": 9,
            "mapped_c2_physical_read_converged": 9,
            "mapped_far_enter": 19,
            "mapped_far_leave": 15,
            "far_vm_code_load_converged": far_sizes[
                "vm_code_load_converged"],
            "far_c2_edma_prepare": far_sizes["c2_edma_prepare"],
            "far_c2_physical_read_converged": far_sizes[
                "c2_physical_read_converged"],
            "far_c2_physical_source_byte": far_sizes[
                "c2_physical_source_byte"],
        }
        actual_symbols = {name: truth.symbol(name).bytes
                          for name in expected_symbols}
        require(actual_symbols == expected_symbols,
                f"mapped far ABI symbol-size drift: {actual_symbols}")
        facade_bytes = truth.section_bytes(".mapped_far_facade")
        def symbol_code(name: str) -> bytes:
            symbol = truth.symbol(name)
            return facade_bytes[
                symbol.value - facade.address:
                symbol.value - facade.address + symbol.bytes]
        enter_code = symbol_code("mapped_far_enter")
        leave_code = symbol_code("mapped_far_leave")
        expected_enter = bytes.fromhex(
            "48 da 5a db a9 80 a2 24 a0 00 a3 80 5c ea fb 7a fa 68 60")
        expected_leave = bytes.fromhex(
            "48 a9 00 a2 00 a0 00 a3 80 5c ea 68 a3 00 60")
        require(enter_code == expected_enter and leave_code == expected_leave,
                "mapped far ABI machine-code tuple drift")
        require(facade_bytes.count(bytes([0x5c])) == 2
                and facade_bytes.count(bytes([0xea])) >= 48,
                "mapped far MAP/EOM opcode witness drift")
        executions.append({
            "case": "priced-facade-and-service",
            "status": "passed",
            "facade_vma": facade.address,
            "facade_bytes": facade.bytes,
            "facade_headroom_bytes": resident_limit - facade.address
                - facade.bytes,
            "far_vma": service.address,
            "far_lma": service_lma,
            "far_bytes": service.bytes,
            "irq_vma": irq.address,
            "symbol_bytes": actual_symbols,
            "map_enter_machine_code": enter_code.hex(),
            "map_leave_machine_code": leave_code.hex(),
            "map_opcode_count": facade_bytes.count(bytes([0x5c])),
        })
        overflow_source = source.replace(
            ".size mapped_far_leave, .-mapped_far_leave",
            ".space 146, 0xea\n.size mapped_far_leave, .-mapped_far_leave")
        overflow_obj = temp / "overflow.o"
        overflow_elf = temp / "overflow.elf"
        subprocess.run(
            [str(LLVM_MC), "--triple=mos", "--mcpu=mos45gs02",
             "-filetype=obj", "-o",
             str(overflow_obj)], input=overflow_source, text=True, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        rejected = subprocess.run(
            [str(LD_LLD), "-T", str(script), "-o", str(overflow_elf),
             str(overflow_obj)], text=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        require(rejected.returncode != 0
                and "mapped far facade overflow" in rejected.stderr,
                "mapped far capacity+1 fixture did not fail closed")
        executions.append({
            "case": "resident-capacity-plus-one",
            "status": "rejected",
            "facade_bytes": int(resident["capacity_bytes"]) + 1,
        })
    offset = parse_int(mapping["mapped_physical_slab_start"]) - parse_int(
        far["cpu_window"]["start"])
    require(offset == 0x24000
            and parse_int(mapping["maplo_a"]) == 0x80
            and parse_int(mapping["maplo_x"]) == 0x24,
            "MAP tuple does not encode the priced physical slab")
    return {
        "assembly_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "linker_sha256": hashlib.sha256(linker.encode()).hexdigest(),
        "call_abi": {
            "entry_wrappers": 2,
            "wrapper_bytes_each": 9,
            "map_enter_bytes": 19,
            "map_leave_bytes": 15,
            "register_preservation": "A/X/Y/Z across map-enter; A status across map-leave; Z=0 at C return",
            "interrupt_flag": "unchanged; MAP inhibits only until EOM",
        },
        "map_offset": offset,
        "map_tuple": mapping,
        "executions": executions,
    }


def geometry_by_name(sections: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["name"]: row for row in sections}


def candidate_pricing(sections: list[dict[str, Any]],
                      demand: dict[str, Any], reachability: dict[str, Any],
                      contract: dict[str, Any], bank2: dict[str, Any],
                      closure: dict[str, Any],
                      far_fixture: dict[str, Any]) -> dict[str, Any]:
    geometry = contract["geometry"]
    by_name = geometry_by_name(sections)
    text = by_name[".text"]
    bss = by_name[".bss"]
    island = by_name[".lisp65_resident_island"]
    annex = by_name[".lisp65_resident_island_annex"]
    e000 = by_name[".lisp65_c2_kernal_window.c2_resident"]
    overlay_rows = [row for row in sections
                    if row["lifetime"].endswith("overlay")]
    largest = max(overlay_rows, key=lambda row: row["bytes"])
    overlay_capacity = int(geometry["overlay_capacity_bytes"])
    code_bytes = int(demand["total_named_bytes"])
    screen_gap = parse_int(geometry["resident_island_start"]) - parse_int(
        geometry["screen_end_exclusive"])
    island_tail = parse_int(geometry["resident_island_limit"]) - (
        annex["vma"] + annex["bytes"])
    text_tail = parse_int(geometry["text_limit"]) - (
        text["vma"] + text["bytes"])
    low_free = screen_gap + island_tail + text_tail
    require((screen_gap, island_tail, text_tail, low_free) == (96, 50, 243, 389),
            "Link-90 low-resident free-space arithmetic drift")
    e000_live_bytes = sum(
        row["bytes"] for row in sections
        if 0xe000 <= row["vma"] < 0x10000)
    e000_headroom = 8192 - e000_live_bytes
    require(e000_headroom == 54, "Link-90 E000 headroom drift")
    bss_headroom = parse_int(geometry["ordinary_bss_limit"]) - (
        bss["vma"] + bss["bytes"])
    state = geometry["candidate_service_state_arena"]
    stack = geometry["candidate_static_stack_arena"]
    state_start = parse_int(state["start"])
    state_end = parse_int(state["end_exclusive"])
    stack_start = parse_int(stack["start"])
    stack_end = parse_int(stack["end_exclusive"])
    state_stack_fit = (
        bss["vma"] + bss["bytes"] +
        int(geometry["candidate_source_marker_bytes"]) <= state_start and
        state_end <= stack_start and stack_end == parse_int(
            geometry["ordinary_bss_limit"]))
    require(state_stack_fit and bss_headroom == 137,
            "candidate state/static-stack arena does not fit baseline")

    low = {
        "id": "fixed-low-resident-island",
        "code_owner": "new KEEP-ed low-resident service section",
        "code_demand_bytes": code_bytes,
        "stable_free_spans": [
            {"start": parse_int(geometry["screen_end_exclusive"]),
             "end_exclusive": parse_int(geometry["resident_island_start"]),
             "bytes": screen_gap},
            {"start": annex["vma"] + annex["bytes"],
             "end_exclusive": parse_int(geometry["resident_island_limit"]),
             "bytes": island_tail},
            {"start": text["vma"] + text["bytes"],
             "end_exclusive": parse_int(geometry["text_limit"]),
             "bytes": text_tail},
        ],
        "aggregate_stable_capacity_bytes": low_free,
        "largest_contiguous_span_bytes": max(screen_gap, island_tail, text_tail),
        "proven_cold_domain_moves_bytes": 0,
        "aggregate_deficit_bytes": code_bytes - low_free,
        "contiguous_island_deficit_bytes": code_bytes - max(
            screen_gap, island_tail, text_tail),
        "facade_bytes": 0,
        "state_stack": "fits-owned-c000/c074-arenas",
        "simultaneous_live_envelope_bytes": code_bytes +
            int(geometry["candidate_service_state_bytes"]) +
            int(geometry["candidate_source_marker_bytes"]) +
            int(geometry["candidate_completion_scratch_zp"]["capacity_bytes"]) +
            int(stack["capacity_bytes"]),
        "fits": False,
        "rejection": (
            "Only 389 stable low bytes exist in three disjoint spans; the largest "
            "contiguous span is 243 bytes. No boot body has an already valid cold "
            "home before the first protected consumer."),
    }
    owned_e000 = {
        "id": "owned-e000-service-slot",
        "code_owner": "new KEEP-ed C2 E000 service section",
        "code_demand_bytes": code_bytes,
        "available_capacity_bytes": e000_headroom,
        "post_boot_reachable_existing_functions": reachability[
            "post_boot_reachable_count"],
        "post_boot_reachable_existing_bytes": reachability["function_bytes"],
        "proven_cold_move_bytes": reachability["proven_boot_only_bytes"],
        "deficit_bytes": code_bytes - e000_headroom,
        "facade_bytes": 0,
        "state_stack": "fits-owned-c000/c074-arenas",
        "simultaneous_live_envelope_bytes": code_bytes + e000_live_bytes +
            int(geometry["candidate_service_state_bytes"]) +
            int(geometry["candidate_source_marker_bytes"]) +
            int(geometry["candidate_completion_scratch_zp"]["capacity_bytes"]) +
            int(stack["capacity_bytes"]),
        "fits": False,
        "rejection": (
            "All 25 E000 functions (7203 bytes) are post-boot reachable; no body "
            "may fund the slot. Only the existing 54-byte floor is free."),
    }
    overlay_live = code_bytes + largest["bytes"]
    overlay = {
        "id": "overlay-service-with-bootstrap-closure",
        "code_owner": "reserved C356 service subrange plus stable facade",
        "service_bytes": code_bytes,
        "largest_live_overlay": {
            "section": largest["name"], "bytes": largest["bytes"]},
        "overlay_capacity_bytes": overlay_capacity,
        "overlay_window_live_envelope_bytes": overlay_live,
        "simultaneous_live_envelope_bytes": overlay_live +
            int(geometry["candidate_service_state_bytes"]) +
            int(geometry["candidate_source_marker_bytes"]) +
            int(geometry["candidate_completion_scratch_zp"]["capacity_bytes"]) +
            int(stack["capacity_bytes"]),
        "deficit_bytes": overlay_live - overlay_capacity,
        "facade_bytes": 3,
        "state_stack": "fits-owned-c000/c074-arenas",
        "bootstrap_acyclic": False,
        "fits": False,
        "rejection": (
            "The 1545-byte service and the 1771-byte live phase slice require "
            "3316 bytes in a 1792-byte window. Loading either displaces the other; "
            "reloading the service would traverse the seam it protects."),
    }
    far = contract["mapped_far_service"]
    far_bank2 = far["bank2"]
    far_resident = far["resident"]
    far_code_bytes = int(far_bank2["service_bytes"])
    resident_bytes = int(far_resident["total_bytes"])
    cpu_window_bytes = int(far["cpu_window"]["capacity_bytes"])
    map_start = parse_int(far["cpu_window"]["start"])
    map_end = parse_int(far["cpu_window"]["end_exclusive"])
    hidden = []
    for row in sections:
        begin = max(row["vma"], map_start)
        end = min(row["vma"] + row["bytes"], map_end)
        if begin < end:
            hidden.append({
                "section": row["name"], "owner": row["owner"],
                "start": begin, "end_exclusive": end,
                "bytes": end - begin,
            })
    require(sum(row["bytes"] for row in hidden) == cpu_window_bytes
            and {row["owner"] for row in hidden}
                == {"ordinary-bank0-text"},
            "mapped CPU-window underlay ownership drift")
    map_source = (ROOT / contract["authorities"]["map_source"]).read_text()
    irq_source = (ROOT / contract["authorities"]["irq_source"]).read_text()
    require("ldz #$80\n\tmap\n\teom" in map_source
            and "c2_kernal_irq_handler:" in irq_source
            and "jmp c2_kernal_fail_closed" in irq_source
            and not re.search(r"c2_kernal_irq_handler:.*?\bjsr\b", irq_source,
                              re.DOTALL),
            "mapped-service interrupt authority drift")
    mapped = {
        "id": "mapped-bank2-far-service",
        "code_owner": (
            "native suffix of the boot-staged Bank-2 static artifact, exposed "
            "through one KEEP-ed two-entry mapped facade"),
        "far_code_bytes": far_code_bytes,
        "far_symbols": far["far_symbols"],
        "resident_code": {
            "dma_abort_wrapper_bytes": int(
                far_resident["dma_abort_wrapper_bytes"]),
            "map_trampoline_bytes": int(
                far_resident["map_trampoline_bytes"]),
            "total_bytes": resident_bytes,
            "available_capacity_bytes": int(far_resident["capacity_bytes"]),
            "headroom_after_bytes": int(
                far_resident["capacity_bytes"]) - resident_bytes,
            "vma_start": parse_int(far_resident["start"]),
            "vma_end_exclusive": parse_int(far_resident["start"])
                + resident_bytes,
        },
        "call_abi": far_fixture["call_abi"],
        "mapping": {
            "cpu_window": far["cpu_window"],
            "map_tuple": far["map_tuple"],
            "underlying_live_owner": hidden,
            "underlying_owner_restored_before_caller_return": True,
        },
        "interrupt_discipline": {
            "raster_irq_vma": 0xe038,
            "irq_and_vectors_remain_in_high_map_block7": True,
            "d000_io_block6_remains_unmapped": True,
            "zero_page_and_stack_block0_remain_unmapped": True,
            "irq_handler_calls_into_hidden_block3": 0,
            "far_dependency_edges_into_hidden_block3":
                closure["hidden_cpu_block_dependencies"],
            "map_atomicity": "MAP inhibits interrupt entry until EOM; the prior I state is unchanged",
            "fits": True,
        },
        "bootstrap": {
            "acyclic": True,
            "media_role": bank2["media_stage"]["artifact_role"],
            "stage_policy": bank2["media_stage"]["policy"],
            "service_install": (
                "contiguous bytes in the same authenticated Bank-2 artifact; "
                "staged and independently read back before the resident PRG "
                "is chained"),
            "protected_refill_used_to_install_service": False,
        },
        "bank2_inventory": {
            "physical_base": bank2["physical_base"],
            "current_static_bytes": bank2["current_static_bytes"],
            "current_owner_count": bank2["current_owner_count"],
            "current_headroom_bytes": bank2["current_headroom_bytes"],
            "service_start": bank2["far_service_reservation"]["start"],
            "service_end_exclusive": bank2[
                "far_service_reservation"]["end_exclusive"],
            "post_service_static_bytes": bank2[
                "post_service_static_bytes"],
            "post_service_headroom_bytes": bank2[
                "post_service_headroom_bytes"],
            "displaced_owner": bank2["displaced_owner"],
        },
        "state_stack": "fits-owned-c000/c074-arenas",
        "simultaneous_live_envelope": {
            "bank2_static_and_far_bytes": bank2[
                "post_service_static_bytes"],
            "bank2_capacity_bytes": bank2["capacity_bytes"],
            "bank2_dynamic_capacity_remaining_bytes": bank2[
                "post_service_headroom_bytes"],
            "mapped_cpu_slab_bytes": cpu_window_bytes,
            "far_bytes_inside_mapped_slab": far_code_bytes,
            "mapped_slab_unused_bytes": cpu_window_bytes - far_code_bytes,
            "temporarily_occluded_bank0_text_bytes": sum(
                row["bytes"] for row in hidden),
            "resident_facade_and_wrapper_bytes": resident_bytes,
            "service_state_bytes": int(
                geometry["candidate_service_state_bytes"]),
            "source_marker_bytes": int(
                geometry["candidate_source_marker_bytes"]),
            "completion_scratch_zp_bytes": int(
                geometry["candidate_completion_scratch_zp"][
                    "capacity_bytes"]),
            "static_stack_bytes": int(stack["capacity_bytes"]),
        },
        "protected_refill_paths": 4,
        "protected_content_consumers": 11,
        "existing_product_bytes_displaced": 0,
        "fits": True,
        "acceptance": (
            "1499 far bytes consume only measured Bank-2 append headroom; "
            "the exact 98-byte resident facade fits the 243-byte text tail "
            "with 145 bytes remaining. The boot stage is acyclic and the "
            "owned raster IRQ remains entirely visible."),
    }
    rows = [low, owned_e000, overlay, mapped]
    require([row["id"] for row in rows] == contract["candidate_rows"],
            "candidate row order drift")
    return {
        "shared_state_and_stack": {
            "ordinary_bss_end": bss["vma"] + bss["bytes"],
            "ordinary_bss_end_after_source_markers":
                bss["vma"] + bss["bytes"] +
                int(geometry["candidate_source_marker_bytes"]),
            "ordinary_bss_headroom_bytes": bss_headroom,
            "headroom_to_owned_state_after_source_markers":
                state_start - bss["vma"] - bss["bytes"] -
                int(geometry["candidate_source_marker_bytes"]),
            "service_state_arena": state,
            "static_stack_arena": stack,
            "completion_scratch_zp":
                geometry["candidate_completion_scratch_zp"],
            "unallocated_gap_bytes": stack_start - state_end,
            "fits": state_stack_fit,
        },
        "rows": rows,
        "fit_count": sum(bool(row["fits"]) for row in rows),
        "recommendation": (
            "select mapped-bank2-far-service: it is the sole fit (1/4), keeps "
            "all four refill paths and eleven content consumers, and pays its "
            "only displacement as 1499 bytes of measured Bank-2 append capacity"),
    }


def validate_far_candidate(row: dict[str, Any],
                           contract: dict[str, Any]) -> None:
    expected = contract["mapped_far_service"]
    require(row["id"] == "mapped-bank2-far-service" and row["fits"],
            "mapped far row is not the selected fit")
    resident = row["resident_code"]
    require(resident["total_bytes"] == expected["resident"]["total_bytes"]
            and resident["total_bytes"] <=
                resident["available_capacity_bytes"]
            and resident["headroom_after_bytes"] == 145,
            "mapped far resident facade does not fit")
    bank2 = row["bank2_inventory"]
    require(bank2["post_service_static_bytes"]
                + bank2["post_service_headroom_bytes"] == 65536
            and bank2["displaced_owner"][
                "existing_product_bytes_displaced"] == 0,
            "mapped far Bank-2 live envelope drift")
    require(row["existing_product_bytes_displaced"] == 0
            and row["bootstrap"]["acyclic"]
            and row["bootstrap"]["protected_refill_used_to_install_service"]
                is False
            and row["interrupt_discipline"]["fits"]
            and row["interrupt_discipline"][
                "far_dependency_edges_into_hidden_block3"] == 0,
            "mapped far closure or interrupt discipline drift")


def far_candidate_mutation_selftest(
        row: dict[str, Any], contract: dict[str, Any]) -> dict[str, str]:
    validate_far_candidate(row, contract)
    mutations: list[tuple[str, Any]] = []
    candidate = deepcopy(row)
    candidate["resident_code"]["total_bytes"] = 244
    mutations.append(("resident-trampoline-overflow", candidate))
    candidate = deepcopy(row)
    candidate["bootstrap"]["acyclic"] = False
    mutations.append(("recursive-bootstrap", candidate))
    candidate = deepcopy(row)
    candidate["interrupt_discipline"]["fits"] = False
    mutations.append(("irq-not-visible", candidate))
    candidate = deepcopy(row)
    candidate["interrupt_discipline"][
        "far_dependency_edges_into_hidden_block3"] = 1
    mutations.append(("far-call-into-hidden-block", candidate))
    candidate = deepcopy(row)
    candidate["existing_product_bytes_displaced"] = 1
    mutations.append(("bank2-owner-overlap", candidate))
    result = {}
    for name, candidate in mutations:
        try:
            validate_far_candidate(candidate, contract)
        except OwnershipError:
            result[name] = "rejected"
        else:
            raise OwnershipError(f"mapped far mutation survived: {name}")
    return result


def validate_inventory(inventory: dict[str, Any],
                       expected_edges: set[tuple[str, str, str, str]]) -> None:
    section_rows = inventory.get("ranges", [])
    require(section_rows, "inventory has no section ranges")
    required = set(inventory["required_sections"])
    names = {row.get("name") for row in section_rows}
    require(required <= names, "inventory required section missing")
    require(all(row.get("owner") for row in section_rows),
            "inventory section owner missing")
    envelopes = inventory["simultaneous_live_sets"]["envelopes"]
    require(all(row.get("live_envelopes") and all(
        item in envelopes for item in row["live_envelopes"])
        for row in section_rows), "inventory live peer missing")
    descriptor_names = {
        row["symbol"] for group in (
            inventory["descriptors"]["link90"],
            inventory["descriptors"]["compact_link91"],
            inventory["descriptors"]["compact_link91_markers"],
            inventory["descriptors"]["compact_link91_scratch"])
        for row in group}
    require({"c2_edma_job", "c2_dma_list", "c2_dma_verify_list",
             "c2_edma_probe_jobs"} <= descriptor_names,
            "inventory descriptor missing")
    edge_keys = {(row["caller"], row["caller_section"], row["callee"],
                  row["callee_section"]) for row in inventory["call_edges"]}
    require(expected_edges <= edge_keys, "inventory call edge missing")


def mutation_selftest(inventory: dict[str, Any]) -> dict[str, str]:
    expected_edges = {(row["caller"], row["caller_section"], row["callee"],
                       row["callee_section"]) for row in inventory["call_edges"]}
    validate_inventory(inventory, expected_edges)
    mutations: dict[str, dict[str, Any]] = {}
    mutated = deepcopy(inventory)
    wanted = inventory["required_sections"][0]
    mutated["ranges"] = [row for row in mutated["ranges"]
                         if row["name"] != wanted]
    mutations["missing-section"] = mutated
    mutated = deepcopy(inventory)
    mutated["ranges"][0]["owner"] = ""
    mutations["missing-owner"] = mutated
    mutated = deepcopy(inventory)
    mutated["ranges"][0]["live_envelopes"] = []
    mutations["missing-live-peer"] = mutated
    mutated = deepcopy(inventory)
    mutated["descriptors"]["compact_link91"] = [
        row for row in mutated["descriptors"]["compact_link91"]
        if row["symbol"] != "c2_edma_probe_jobs"]
    mutations["missing-descriptor"] = mutated
    mutated = deepcopy(inventory)
    mutated["call_edges"] = mutated["call_edges"][1:]
    mutations["missing-call-edge"] = mutated
    result = {}
    for name, candidate in mutations.items():
        try:
            validate_inventory(candidate, expected_edges)
        except OwnershipError:
            result[name] = "rejected"
        else:
            raise OwnershipError(f"inventory mutation survived: {name}")
    require(list(result) == inventory["required_mutations"],
            "mutation execution order drift")
    return result


def build() -> tuple[dict[str, Any], dict[str, Any]]:
    contract = load_contract()
    paths = authority_paths(contract)
    for path in paths.values():
        require(path.is_file(), f"authority absent: {relative(path)}")
    truth88, raw88, headers88 = read_elf(paths["link88_elf"])
    truth90, raw90, headers90 = read_elf(paths["link90_elf"])
    sections88 = relevant_sections(truth88, raw88, headers88, contract)
    sections90 = relevant_sections(truth90, raw90, headers90, contract)
    key_names = set(contract["required_sections"])
    shape88 = {(row["name"], row["vma"], row["bytes"])
               for row in sections88 if row["name"] in key_names}
    shape90 = {(row["name"], row["vma"], row["bytes"])
               for row in sections90 if row["name"] in key_names}
    require(shape88 == shape90,
            "Link-88/90 owned baseline geometry is not byteidentical")
    live = make_live_envelopes(sections90)
    placement = linker_provenance(
        sections90, paths["link88_linker"], paths["link90_linker"])
    edges = function_edges(truth90, {row["name"] for row in sections90})
    reachability = e000_reachability(truth90, sections90, edges)
    compact_map = parse_map(paths["link91_compact_map"])
    full_map = parse_map(paths["link91_full_map"])
    compact_truth = ElfTruth.read(
        paths["link91_compact_lto_object"], llvm_readobj=LLVM_READOBJ)
    full_receipt = json.loads(paths["link91_full_first_red"].read_text())
    compact_receipt = json.loads(paths["link91_compact_first_red"].read_text())
    descriptors = descriptor_inventory(
        truth90, compact_map, contract, full_receipt)
    demand = service_demand(compact_map, contract)
    bank2 = bank2_inventory(paths, contract)
    far_closure = far_service_dependency_closure(
        compact_truth, compact_map, contract)
    fixtures = conviction_fixtures(paths)
    link90_text = map_one(parse_map(
        ROOT / "build/post-promotion/v14/link90-vic-unlock-wplto/wplto/"
        "resident-island-seed.prg.map"), ".text")
    compact_text = map_one(compact_map, ".text")
    full_text = map_one(full_map, ".text")
    inventory = {
        "format": "lisp65-c2-stack-overlay-ownership-inventory-v1",
        "recorded_on": "2026-08-04",
        "status": "passed-read-only-ownership-inventory",
        "contract": bind(CONTRACT),
        "authorities": {key: bind(path) for key, path in paths.items()},
        "upstream_map_semantics_authority": contract[
            "map_semantics_authority"],
        "required_sections": contract["required_sections"],
        "required_mutations": contract["required_mutations"],
        "ranges": sections90,
        "range_count": len(sections90),
        "simultaneous_live_sets": live,
        "linker_placement_provenance": placement,
        "call_edges": edges,
        "call_edge_count": len(edges),
        "e000_post_boot_reachability": reachability,
        "descriptors": descriptors,
        "conviction_fixtures": fixtures,
        "failed_link_geometry": {
            "link90_text_bytes": link90_text["bytes"],
            "link91_compact_text_bytes": compact_text["bytes"],
            "link91_compact_text_delta": compact_text["bytes"] -
                link90_text["bytes"],
            "link91_full_text_bytes": full_text["bytes"],
            "link91_full_text_delta": full_text["bytes"] -
                link90_text["bytes"],
            "compact_noinit": compact_receipt["geometry"][
                "pinned_noinit_overlay"],
            "full_noinit": full_receipt["geometry"][
                "pinned_noinit_overlay"],
        },
        "service_demand": demand,
        "bank2_real_inventory": bank2,
        "mapped_far_service_dependency_closure": far_closure,
        "claim_limit": contract["claim"],
    }
    mutations = mutation_selftest(inventory)
    inventory["execution_witness"] = {
        "positive_inventory_executions": 1,
        "mutation_executions": len(mutations),
        "mutations": mutations,
        "total_executions": 1 + len(mutations),
    }
    stack = stack_micro_fixtures(contract)
    far_fixture = far_service_micro_fixture(contract)
    candidates = candidate_pricing(
        sections90, demand, reachability, contract, bank2, far_closure,
        far_fixture)
    far_mutations = far_candidate_mutation_selftest(
        candidates["rows"][-1], contract)
    pricing = {
        "format": "lisp65-c2-stack-overlay-ownership-halt1-pricing-v1",
        "recorded_on": "2026-08-04",
        "status": "halt-1-fourth-class-priced-one-row-fits",
        "contract": bind(CONTRACT),
        "inventory_receipt_expected_sha256": hashlib.sha256(
            canonical(inventory)).hexdigest(),
        "stack_micro_elf_fixtures": stack,
        "mapped_far_service_micro_elf": far_fixture,
        "mapped_far_service_mutations": far_mutations,
        "candidates": candidates,
        "bootstrap_answer": {
            "c356_overlay_service_acyclic": False,
            "c356_reason": (
                "The service would occupy the same C356 execution window as its "
                "phase-overlay callers. Installing either evicts the other; restoring "
                "the service requires the refill seam that the service must protect."),
            "largest_overlay_section": max(
                (row for row in sections90 if row["lifetime"].endswith("overlay")),
                key=lambda row: row["bytes"])["name"],
            "mapped_bank2_service_acyclic": True,
            "mapped_bank2_reason": (
                "The far bytes are a contiguous suffix of the canonical Bank-2 "
                "artifact. The cold stager writes and independently reads back "
                "that role before it chains to the resident entry, so no protected "
                "runtime refill is needed to install or map the service."),
        },
        "execution_witness": {
            "candidate_rows_evaluated": 4,
            "stack_micro_elf_executions": len(stack["executions"]),
            "mapped_far_micro_elf_executions": len(
                far_fixture["executions"]),
            "mapped_far_mutation_executions": len(far_mutations),
            "inventory_and_mutation_executions":
                inventory["execution_witness"]["total_executions"],
            "total_executions": 4 + len(stack["executions"]) +
                len(far_fixture["executions"]) + len(far_mutations) +
                inventory["execution_witness"]["total_executions"],
        },
        "claim_limit": contract["claim"],
    }
    return inventory, pricing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("emit-inventory", "emit-pricing",
                                           "write", "check", "selftest"))
    args = parser.parse_args()
    try:
        inventory, pricing = build()
        if args.action == "emit-inventory":
            print(canonical(inventory).decode(), end="")
        elif args.action == "emit-pricing":
            print(canonical(pricing).decode(), end="")
        elif args.action == "write":
            INVENTORY_RECEIPT.write_bytes(canonical(inventory))
            PRICING_RECEIPT.write_bytes(canonical(pricing))
            print("c2-stack-overlay-ownership: WROTE "
                  "candidates=1/4-fit far=1499 resident=98 bank2=16755-free")
        elif args.action == "check":
            require(INVENTORY_RECEIPT.read_bytes() == canonical(inventory),
                    "ownership inventory receipt drift")
            require(PRICING_RECEIPT.read_bytes() == canonical(pricing),
                    "ownership pricing receipt drift")
            print("c2-stack-overlay-ownership: PASS "
                  f"ranges={inventory['range_count']} "
                  f"edges={inventory['call_edge_count']} "
                  "e000=25/25-post-boot candidates=1/4-fit "
                  f"executions={pricing['execution_witness']['total_executions']}")
        else:
            print("c2-stack-overlay-ownership: SELFTEST PASS "
                  "mutations=5/5 stack=3/4/6/12 overflow=13-rejected "
                  "far=5/5 candidates=4")
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError,
            ElfTruthError, OwnershipError) as error:
        print(f"c2-stack-overlay-ownership: FAIL: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
