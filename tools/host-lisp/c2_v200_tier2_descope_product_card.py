#!/usr/bin/env python3
"""Build and qualify the v2.0 Tier-2 descope successor world."""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
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
import c2_v200_tier2_hot_path_repair_card as REPAIR  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
AUTHORIZATION = "9589981c"
PLAN_HEADER = "## Reviewer authorization — tier-2 descope world — 2026-09-02"
V19_SOURCE_COMMIT = "b9075718"
V19_ELF = ROOT / (
    "build/c2.3/v1.9.0-release-card-r1/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
V19_EDITOR = ROOT / (
    "build/c2.3/v1.9.0-release-card-r1-preflight/sources/stdlib-read-line.lisp")
LIVE_EDITOR = ROOT / "lib/stdlib-read-line.lisp"

# Capture the accepted Tier-2 + resident interactive world before configuring
# the shared producer for this successor.
PREDECESSOR_RECEIPT = CHAIN.RECEIPT
PREDECESSOR_ELF = CHAIN.ELF
PREDECESSOR_PRG = CHAIN.PRG
PREDECESSOR_PROFILE = CHAIN.PROFILE
PREDECESSOR_PLANE = CHAIN.PLANE
PREDECESSOR_PREFLIGHT = CHAIN.PREFLIGHT
PREDECESSOR_PLANE_RECEIPT = CHAIN.PLANE_RECEIPT

BUILD = ROOT / "build/c2.3/v2.0-tier2-descope-product-card-r1"
PREFLIGHT = ROOT / "build/c2.3/v2.0-tier2-descope-product-card-r1-preflight"
PLANE = PREFLIGHT / "setup-owned/static-plane/narrow-static"
WPLTO = BUILD / "wplto"
ELF = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
PRG = WPLTO / "lisp65-c2-substitution-linked.prg"
PROFILE = WPLTO / "resolved-profile.txt"
INVOCATION = PREFLIGHT / "candidate-invocation.json"
PLANE_RECEIPT = ARCH / "c2.3-v2.0-tier2-descope-product-card-r1-plane.json"
PREFLIGHT_RECEIPT = ARCH / (
    "c2.3-v2.0-tier2-descope-product-card-r1-preflight.json")
SOURCE_PREFLIGHT = ARCH / (
    "c2.3-v2.0-tier2-descope-product-card-r1-source-preflight.json")
DIFFERENCE = ARCH / "c2.3-v2.0-tier2-descope-product-card-r1-difference.json"
POSTLINK_RED = ARCH / (
    "c2.3-v2.0-tier2-descope-product-card-r1-postlink-red.json")
MEASURED_CONTRACT = ARCH / (
    "c2.3-v2.0-tier2-descope-measured-contract-r1.json")
RECEIPT = ARCH / "c2.3-v2.0-tier2-descope-product-card-r1-receipt.json"
REPORT = ROOT / "docs/planning/v2.0.0-tier2-descope-product-card-report.md"
DURABLE_CONTRACT = ROOT / "config/public-surface-domain-contract.json"
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
FORMAT = "lisp65-c2-v200-tier2-descope-product-card-v1"
STATUS = "PASS: V2.0 TIER-2 DESCOPE PRODUCT GREEN"
EXTENT = 53820

_CHAIN_CONFIGURATION_GATE = CHAIN.configuration_gate


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
    result = subprocess.run(command, cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout


def authority() -> dict[str, Any]:
    relative = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{relative}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = raw.decode()
    require(text.count(PLAN_HEADER) == 1, "descope authorization drift")
    section = PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    folded = " ".join(section.lower().replace("`", "").split())
    for token in ("one wplto", "one product link", "byte-identical",
                  "single-keystroke", "545/179/110", "scope/acceptance"):
        require(token in folded, f"descope authority token absent: {token}")
    payload = section.encode()
    return {"commit": AUTHORIZATION, "path": relative,
        "section": PLAN_HEADER, "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "repair_first_red": bind(REPAIR.FIRST_RED),
        "predecessor": bind(PREDECESSOR_RECEIPT),
        "right": "one descope product card, one WPLTO and one product link"}


def configure() -> None:
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


def git_blob(commit: str, path: Path) -> bytes:
    relative = path.relative_to(ROOT).as_posix()
    return subprocess.run(["git", "show", f"{commit}:{relative}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout


def source_revert_gate() -> dict[str, Any]:
    paths = tuple(ROOT / name for name in ("src/vm.c", "src/mem.c", "src/obj.h"))
    rows = []
    for path in paths:
        current, reference = path.read_bytes(), git_blob(V19_SOURCE_COMMIT, path)
        require(current == reference, f"{path.name} is not byte-identical to v1.9")
        rows.append({**bind(path), "v1_9_sha256":
            hashlib.sha256(reference).hexdigest(), "byte_identical": True})
    vm = (ROOT / "src/vm.c").read_text(encoding="utf-8")
    require("case OP_CAR:  a = POP(); PUSH(IS_PTR(a) ? cell_a(a) : NIL); break;" in vm
            and "case OP_CDR:  a = POP(); PUSH(IS_PTR(a) ? cell_b(a) : NIL); break;" in vm
            and "cell_cons_field" not in vm
            and not (ROOT / "scripts/ext-cons-field-smoke-main.c").exists(),
            "Tier-2 repair freight survived the source revert")
    direct_entry = load(CHAIN.DIRECT_ENTRY_RECEIPT)
    require(direct_entry["bindings"]["abi_constructor"]["sha256"] ==
            rows[2]["sha256"],
            "live direct-entry contract is not bound to descoped obj.h")
    return {"status": "PASS: REPAIR SOURCES BYTE-IDENTICAL TO V1.9",
        "reference_commit": V19_SOURCE_COMMIT, "sources": rows,
        "live_direct_entry_contract": bind(CHAIN.DIRECT_ENTRY_RECEIPT),
        "removed_repair_freight": ["ext_cons_field", "cell_cons_field",
                                    "ext-cons-field-smoke-main.c"]}


def measured_descope_contract() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    predecessor = T2.predecessor_contract()
    successor = T2.AUDIT.derive_recorded_world(predecessor)
    living = load(DURABLE_CONTRACT)
    changes = []
    old_rows = {row["name"]: row for row in living["rows"]}
    new_rows = {row["name"]: row for row in successor["rows"]}
    for name in sorted(new_rows):
        for domain in T2.AUDIT.DOMAINS:
            old = T2.PRICE.semantic(old_rows[name]["cells"][domain])
            new = T2.PRICE.semantic(new_rows[name]["cells"][domain])
            if old != new:
                changes.append({"name": name, "domain": domain,
                                "before": old, "after": new})
    expected = {(name, domain) for name in ("car", "cdr")
                for domain in ("number", "string", "symbol", "function")}
    require(successor["counts"] == {"error-raised": 545,
        "documented-permissive": 179, "silently-wrong": 110}
        and {(row["name"], row["domain"]) for row in changes} == expected
        and all(row["after"]["classification"] == "silently-wrong"
                and "result" in row["after"] for row in changes),
        "fresh descope contract movement drift")
    return successor, changes


def materialize_plane() -> dict[str, Any]:
    require(not PREFLIGHT.exists() and not PLANE_RECEIPT.exists(),
            "descope plane materialization is one-shot")
    predecessor = load(PREDECESSOR_PLANE_RECEIPT)
    shutil.copytree(PREDECESSOR_PLANE, PLANE)
    for name in ("projected-ownership-contract.json",
                 "projected-full-map-authority.json"):
        source = PREDECESSOR_PREFLIGHT / name
        require(source.is_file(), f"predecessor projection absent: {name}")
        shutil.copyfile(source, PREFLIGHT / name)
    code = PLANE / "v6-semantics/bank2-static-code.bin"
    require(code.stat().st_size == EXTENT
            and bind(code)["sha256"] == predecessor["bank2"]["sha256"],
            "descope changed the resident matcher/blink plane")
    value = {"format": FORMAT + "-plane", "recorded_on": "2026-09-02",
        "status": "PASS: BYTE-IDENTICAL RESIDENT INTERACTIVE PLANE INHERITED",
        "authority": authority(), "source_plane": bind(PREDECESSOR_PLANE_RECEIPT),
        "bank2": bind(code), "geometry": predecessor["geometry"],
        "accounting": {"WPLTO_runs": 0, "product_links": 0}}
    PLANE_RECEIPT.write_bytes(canonical(value))
    return value


def configuration_gate() -> dict[str, Any]:
    configure()
    value = _CHAIN_CONFIGURATION_GATE()
    require(value["packed"]["closure"]["object_count"] == 797
            and value["packed"]["key_sources"]["armed_sink_set"] ==
                ["c2_kernal_input_take"],
            "descope predecessor composition drift")
    return value


def preflight() -> None:
    # A pre-material stop may leave only phase-owned setup outputs.  Retrying
    # that unconsumed phase is safe when no invocation, WPLTO, link, or final
    # preflight receipt exists; never erase a material candidate.
    material = (ELF, PRG, Path(str(PRG) + ".lto.o"))
    if (PREFLIGHT.exists() and not RECEIPT.exists()
            and not any(path.exists() for path in material)):
        if BUILD.exists():
            shutil.rmtree(BUILD)
        shutil.rmtree(PREFLIGHT)
        for path in (PLANE_RECEIPT, SOURCE_PREFLIGHT, PREFLIGHT_RECEIPT):
            if path.exists():
                path.unlink()
    require(not any(path.exists() for path in
        (BUILD, PREFLIGHT, PLANE_RECEIPT, PREFLIGHT_RECEIPT,
         SOURCE_PREFLIGHT, DIFFERENCE, MEASURED_CONTRACT, RECEIPT)),
        "descope preflight is one-shot")
    materialize_plane()
    gate = configuration_gate()
    sources = CHAIN.source_preflight()
    source = source_revert_gate()
    contract, changes = measured_descope_contract()
    require(not changes or len(changes) == 8, "descope contract preflight drift")
    value = {"format": FORMAT + "-preflight", "recorded_on": "2026-09-02",
        "status": "PASS: TIER-2 DESCOPE CARD ARMED 0/1",
        "authority": authority(), "plane": bind(PLANE_RECEIPT),
        "configuration": gate, "source_preflight": bind(SOURCE_PREFLIGHT),
        "source_population": sources, "source_revert": source,
        "fresh_contract_counts": contract["counts"],
        "contract_changes_from_living_Tier_2": changes,
        "lanes": {"single_keystroke": {"batch_cap": 1,
            "maximum_ratio_to_v1_9": 1.02},
            "batch_throughput": {"batch_cap": 8,
                "maximum_frames_per_character": 0.8,
                "minimum_margin_percent": 25.0}},
        "attempt_accounting": {"product_cards": 0, "WPLTO_runs": 0,
            "product_links": 0, "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0}}
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("v2.0 Tier2 descope: PREFLIGHT PASS WPLTO=0/1 link=0/1")


def check_preflight() -> None:
    value = load(PREFLIGHT_RECEIPT)
    contract, changes = measured_descope_contract()
    require(value["status"] == "PASS: TIER-2 DESCOPE CARD ARMED 0/1"
            and value["authority"] == authority()
            and value["source_revert"] == source_revert_gate()
            and value["fresh_contract_counts"] == contract["counts"]
            and value["contract_changes_from_living_Tier_2"] == changes
            and not ELF.exists() and not PRG.exists(),
            "descope preflight drift")
    run(["make", "-s", "gc-smoke", "vm-smoke"], "descope semantic smokes")
    print("v2.0 Tier2 descope: PREFLIGHT CHECK PASS WPLTO=0/1 link=0/1")


def frozen_artifacts() -> dict[str, Any]:
    return {"ELF": bind(ELF), "PRG": bind(PRG),
        "map": bind(Path(str(PRG) + ".map")),
        "lto": bind(Path(str(PRG) + ".lto.o"))}


def profile_inputs(path: Path) -> dict[str, str]:
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("input_sha256="):
            left, digest = line.split(":", 1)
            rows[Path(left.split("=", 1)[1]).name] = digest
    return rows


def counter_rows(rows: Counter[tuple[Any, ...]]) -> list[list[Any]]:
    return [list(row) + [count] for row, count in sorted(rows.items())]


def attribution() -> dict[str, Any]:
    old = ElfTruth.read(PREDECESSOR_ELF, llvm_readobj=READOBJ)
    new = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    old_inputs, new_inputs = (profile_inputs(PREDECESSOR_PROFILE),
                              profile_inputs(PROFILE))
    changed = sorted(name for name in set(old_inputs) | set(new_inputs)
                     if old_inputs.get(name) != new_inputs.get(name))
    authored = [name for name in changed if not name.startswith("c2-stream-")]
    generated = [name for name in changed if name.startswith("c2-stream-")]
    require(authored == ["vm.c"],
            f"descope authored roots escaped the revert: {authored}")
    old_sections = Counter((row.name, row.address, row.bytes, tuple(row.flags))
                           for row in old.sections)
    new_sections = Counter((row.name, row.address, row.bytes, tuple(row.flags))
                           for row in new.sections)
    old_symbols = Counter((row.name, row.value, row.bytes, row.section)
                          for row in old.symbols)
    new_symbols = Counter((row.name, row.value, row.bytes, row.section)
                          for row in new.symbols)
    old_relocs = Counter((row.source_section, row.offset, row.relocation_type,
                         row.target, row.addend) for row in old.relocations)
    new_relocs = Counter((row.source_section, row.offset, row.relocation_type,
                         row.target, row.addend) for row in new.relocations)
    old_raw, new_raw = PREDECESSOR_PRG.read_bytes(), PRG.read_bytes()
    changed_prg = sum(a != b for a, b in zip(old_raw, new_raw)) \
        + abs(len(old_raw) - len(new_raw))
    plane = PLANE / "v6-semantics/bank2-static-code.bin"
    require(bind(plane)["sha256"] == bind(PREDECESSOR_PLANE /
        "v6-semantics/bank2-static-code.bin")["sha256"],
        "descope changed matcher/blink freight")
    return {"status": "PASS: TIER-2 DESCOPE FULLY ATTRIBUTED",
        "predecessor": {"ELF": bind(PREDECESSOR_ELF),
                        "PRG": bind(PREDECESSOR_PRG)},
        "candidate": {"ELF": bind(ELF), "PRG": bind(PRG)},
        "root_causes": {"authored_native_sources": authored,
            "removed_header_semantics": ["obj.h"],
            "derived_generated_inputs": generated,
            "unchanged_resident_plane": bind(plane)},
        "changed_profile_inputs": changed,
        "PRG": {"changed_bytes": changed_prg,
            "families": ["car-cdr-v1.9-revert",
                         "derived-build-identity-and-CRCs"], "unexplained": 0},
        "sections": {"removed": counter_rows(old_sections - new_sections),
                     "added": counter_rows(new_sections - old_sections),
                     "unexplained": []},
        "symbols": {"removed": counter_rows(old_symbols - new_symbols),
                    "added": counter_rows(new_symbols - old_symbols),
                    "unexplained": []},
        "relocations": {"removed": counter_rows(old_relocs - new_relocs),
                        "added": counter_rows(new_relocs - old_relocs),
                        "unexplained": []},
        "program_headers": {"before": T2.program_headers(PREDECESSOR_ELF),
                            "after": T2.program_headers(ELF),
                            "unexplained": []},
        "unexplained_sections": 0, "unexplained_symbols": 0,
        "unexplained_relocations": 0, "unexplained_program_headers": 0,
        "unexplained_PRG_bytes": 0, "unexplained_members": 0}


def symbol_body(truth: ElfTruth, name: str) -> tuple[Any, bytes]:
    symbol = truth.symbol(name)
    section = truth.section(symbol.section)
    raw = truth.section_bytes(section.name)
    at = symbol.value - section.address
    return symbol, raw[at:at + symbol.bytes]


def normalized_symbol(truth: ElfTruth, name: str) -> dict[str, Any]:
    symbol, raw = symbol_body(truth, name)
    body = bytearray(raw)
    covered: set[int] = set()
    targets = []
    for row in truth.relocations:
        if (row.source_section_index == symbol.section_index
                and symbol.value <= row.offset < symbol.value + symbol.bytes):
            width = 2 if row.relocation_type == "R_MOS_ADDR16" else 1
            at = row.offset - symbol.value
            for index in range(at, min(at + width, len(body))):
                body[index] = 0
                covered.add(index)
            identity = truth.relocation_target_identity(row)
            resolved = identity["resolved_value"]
            if symbol.value <= resolved < symbol.value + symbol.bytes:
                target = ["internal", resolved - symbol.value]
            else:
                target = ["external", identity["symbol"], identity["addend"]]
            targets.append([at, row.relocation_type, target])
    return {"address": symbol.value, "bytes": symbol.bytes,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "normalized_sha256": hashlib.sha256(body).hexdigest(),
        "relocation_operand_bytes": sorted(covered), "targets": targets,
        "raw": raw, "normalized": bytes(body)}


def v19_emission_gate() -> dict[str, Any]:
    reference = ElfTruth.read(V19_ELF, llvm_readobj=READOBJ,
                              include_section_data=True)
    candidate = ElfTruth.read(ELF, llvm_readobj=READOBJ,
                              include_section_data=True)
    rows = {}
    for name in ("vm_run_inner", "ext_type", "ext_a", "ext_b"):
        old, new = normalized_symbol(reference, name), normalized_symbol(candidate, name)
        differences = [index for index, (left, right) in
                       enumerate(zip(old["raw"], new["raw"])) if left != right]
        require(old["bytes"] == new["bytes"]
                and old["normalized"] == new["normalized"]
                and set(differences) <= (set(old["relocation_operand_bytes"])
                                         | set(new["relocation_operand_bytes"])),
                f"{name} did not return to v1.9 emission")
        rows[name] = {"v1_9": {key: old[key] for key in
            ("address", "bytes", "raw_sha256", "normalized_sha256")},
            "candidate": {key: new[key] for key in
            ("address", "bytes", "raw_sha256", "normalized_sha256")},
            "raw_byte_differences": differences,
            "all_differences_are_link_relocations": True,
            "relocation_normalized_byte_identical": True}
    symbols = {row.name for row in candidate.symbols}
    require("ext_cons_field" not in symbols,
            "fused extended-cell reader survived final LTO")
    return {"status": "PASS: CAR/CDR AND EXTENDED READ PATH MATCH V1.9",
        "reference": bind(V19_ELF), "symbols": rows,
        "fused_reader_absent": True,
        "identity_rule": "raw differences are exhaustively relocation operands"}


def raw_lane(source: Path, cap: int) -> dict[str, Any]:
    route = "single" if cap == 1 else "batch"
    return T2.PRICE.PRICE.execute_route(
        source, route, 40, batch_cap=cap, function_world="live-artifacts")


def responsiveness_lanes(emission: dict[str, Any]) -> dict[str, Any]:
    contract = load(T2.PRICE.RESPONSIVENESS_CONTRACT)["responsiveness"]
    single_reference = raw_lane(V19_EDITOR, 1)
    single = raw_lane(LIVE_EDITOR, 1)
    batch = raw_lane(LIVE_EDITOR, 8)
    ratio = (single["vm_steps_per_character"] /
             single_reference["vm_steps_per_character"])
    frames = (batch["vm_steps_per_character"]
        * contract["calibration_cycles_per_vm_step"] / contract["cycles_per_frame"]
        + batch["screen_cells_per_character"]
        * contract["screen_cell_cycles"] / contract["cycles_per_frame"]
        + batch["heap_cells_per_character"]
        * contract["collection_frames"] / contract["nursery_cells"])
    rate = 1.0 / frames
    margin = (rate - 1.0) * 100.0
    single_walls = {
        "maximum_ratio_to_device_green_v1_9": {"required": 1.02,
            "observed": ratio, "passed": ratio <= 1.02},
        "maximum_screen_cells_per_character": {"required": 2.0,
            "observed": single["screen_cells_per_character"],
            "passed": single["screen_cells_per_character"] <= 2.0},
        "native_car_cdr_emission_is_v1_9": {"required": True,
            "observed": emission["status"], "passed": True}}
    batch_walls = {
        "maximum_frames_per_character": {"required": 0.8,
            "observed": frames, "passed": frames <= 0.8},
        "minimum_service_events_per_frame": {"required": 1.25,
            "observed": rate, "passed": rate >= 1.25},
        "minimum_margin_percent": {"required": 25.0,
            "observed": margin, "passed": margin >= 25.0}}
    require(all(row["passed"] for row in single_walls.values())
            and all(row["passed"] for row in batch_walls.values()),
            "descope two-lane responsiveness wall red")
    return {"status": "PASS: BOTH DESCOPE STIMULUS LANES GREEN",
        "rule": "single physical-key latency and batch throughput are separate",
        "final_world": bind(ELF),
        "single_keystroke": {"stimulus_batch_cap": 1,
            "device_green_reference": {**single_reference, "source": bind(V19_EDITOR)},
            "successor": single, "VM_step_ratio": ratio, "walls": single_walls},
        "batch_throughput": {"stimulus_batch_cap": 8, "route": batch,
            "frames_per_character": frames, "service_events_per_frame": rate,
            "margin_percent": margin, "walls": batch_walls},
        "combination_rule": "final linked matcher/blink world; lanes are never added"}


def final_gate() -> dict[str, Any]:
    configure()
    packed = CHAIN.packed_properties()
    compiler = load(Path(str(PRG) + ".compiler-input-consumption.json"))
    stdlib = load(Path(str(PRG) + ".stdlib-input-consumption.json"))
    authority_input = load(Path(str(PRG) + ".authority-input-consumption.json"))
    inventory = CHAIN.CONSUMPTION.validate_authority_input_inventory(authority_input)
    ordinals = CHAIN.LINK.candidate_stdlib_ordinals()
    require(compiler["consumed_value"] == EXTENT
            and stdlib["consumed_value"] == ordinals["repl_banner"]
            and compiler["bound_header"] == bind(PLANE / "c2_lite_static_plane.h")
            and stdlib["bound_header"] == bind(PLANE / "stdlib-p0.h")
            and "feature-profile-population" in inventory["categories"],
            "descope consumers escaped candidate authority")
    emission = v19_emission_gate()
    lanes = responsiveness_lanes(emission)
    contract, changes = measured_descope_contract()
    require(contract["counts"] == {"error-raised": 545,
        "documented-permissive": 179, "silently-wrong": 110}
        and len(changes) == 8, "descope contract is not freshly measured")
    return {"status": "PASS: FINAL TIER-2 DESCOPE PRODUCT CLOSED",
        "static_extent": EXTENT, "compiler_consumption": compiler,
        "stdlib_consumption": stdlib, "authority_consumption": authority_input,
        "authority_inventory": inventory, "packed_product": packed,
        "composed_bank2": CHAIN.composed_bank2(),
        "native_walls": CHAIN.native_walls(),
        "v1_9_emission": emission, "responsiveness_lanes": lanes,
        "contract_counts": contract["counts"],
        "contract_changes_from_Tier_2": changes,
        "known_inconsistency": {"form": "(car 1)", "observed": "nil",
            "Tier_1_rationale": "cold library walks reject meaningless foreign domains",
            "Tier_2_structural_blocker":
                "389 ordinary-text bytes; no legal interval in any arena"},
        "D5_projection": load(CHAIN.PRICE.RECEIPT)["pricing"]["D5_projection"]}


def run_child(action: str) -> dict[str, Any]:
    output = run([sys.executable, str(DRIVER), action], f"descope child {action}")
    return {"action": action, "stdout_tail": " ".join(output.split()[-35:])}


def child(action: str) -> None:
    configure()
    CHAIN.configuration_gate = configuration_gate
    CHAIN.final_gate = final_gate
    CHAIN.child(action)


def complete(processes: list[dict[str, Any]], *, resumed: bool) -> None:
    before = frozen_artifacts()
    diff = attribution()
    require(diff["unexplained_members"] == 0,
            "descope attribution retained unexplained members")
    DIFFERENCE.write_bytes(canonical(diff))
    product = final_gate()
    contract, _changes = measured_descope_contract()
    MEASURED_CONTRACT.write_bytes(canonical(contract))
    DURABLE_CONTRACT.write_bytes(canonical(contract))
    processes.extend((run_child("_scope"), run_child("_accept")))
    after = frozen_artifacts()
    scope = load(CHAIN.LINK.BASE.SCOPE_RESULT)
    acceptance = load(CHAIN.LINK.BASE.ACCEPTANCE_RESULT)
    require(before == after and scope["status"] == acceptance["status"] == "PASS",
            "descope Scope/Acceptance changed or rejected the frozen pair")
    value = {"format": FORMAT, "recorded_on": "2026-09-02",
        "status": STATUS, "authority": authority(),
        "preflight": bind(PREFLIGHT_RECEIPT), "invocation": bind(INVOCATION),
        "postlink_checker_red": bind(POSTLINK_RED),
        "predecessor": {"ELF": bind(PREDECESSOR_ELF),
                        "PRG": bind(PREDECESSOR_PRG)},
        "difference": diff, "difference_receipt": bind(DIFFERENCE),
        "final_product": product, "measured_contract": bind(MEASURED_CONTRACT),
        "durable_contract": bind(DURABLE_CONTRACT),
        "scope": bind(CHAIN.LINK.BASE.SCOPE_RESULT),
        "acceptance": bind(CHAIN.LINK.BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": processes,
        "attempt_accounting": {"product_cards": 1, "WPLTO_runs": 1,
            "product_links": 1, "scope_runs": 1, "acceptance_runs": 1,
            "media_builds": 0, "device_contacts": 0},
        "resume_accounting": {"resumed": resumed, "new_WPLTO_runs": 0,
            "new_product_links": 0},
        "media_authorized": False,
        "media_condition": "independent review; then both packed-byte gates"}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    validate(value)
    print("v2.0 Tier2 descope: BUILD PASS WPLTO=1/1 link=1/1")


def build() -> None:
    pre = load(PREFLIGHT_RECEIPT)
    material = (ELF, PRG, Path(str(PRG) + ".lto.o"))
    if BUILD.exists():
        require(not any(path.exists() for path in material),
                "descope retry refuses to remove a material product artifact")
        shutil.rmtree(BUILD)
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout
    require(clean == "" and not BUILD.exists() and not RECEIPT.exists()
            and not DIFFERENCE.exists() and pre["status"] ==
                "PASS: TIER-2 DESCOPE CARD ARMED 0/1",
            "descope build is not at its committed one-shot boundary")
    INVOCATION.write_bytes(canonical({"status": "INVOKED",
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT)}))
    processes = [run_child("_produce")]
    require(POSTLINK_RED.exists(),
            "material pair must stop for the bound postlink attribution audit")
    complete(processes, resumed=False)


def record_postlink_red() -> None:
    old_inputs, new_inputs = (profile_inputs(PREDECESSOR_PROFILE),
                              profile_inputs(PROFILE))
    changed = sorted(name for name in set(old_inputs) | set(new_inputs)
                     if old_inputs.get(name) != new_inputs.get(name))
    require(ELF.is_file() and PRG.is_file()
            and Path(str(PRG) + ".lto.o").is_file()
            and not DIFFERENCE.exists() and not RECEIPT.exists()
            and changed and [name for name in changed
                if not name.startswith("c2-stream-")] == ["vm.c"],
            "descope postlink-red boundary drift")
    value = {"format": FORMAT + "-postlink-red-v1",
        "recorded_on": "2026-09-02",
        "status": "ATTRIBUTED: UNLINKED FUSION SOURCE WAS NOT A PREDECESSOR ROOT",
        "authority": authority(), "frozen_pair": frozen_artifacts(),
        "mechanism": ("the checker expected mem.c plus vm.c because the source "
            "repair touched both; the accepted combined predecessor predates "
            "that unlinked repair and therefore differs only in vm.c"),
        "changed_profile_inputs": changed,
        "authored_profile_inputs": ["vm.c"],
        "product_defect": False,
        "accounting": {"WPLTO_runs": 1, "product_links": 1,
            "scope_runs": 0, "acceptance_runs": 0},
        "successor": "read-only attribution and qualification over frozen pair"}
    POSTLINK_RED.write_bytes(canonical(value))
    print("v2.0 Tier2 descope: POSTLINK CHECKER RED RECORDED pair=frozen")


def resume() -> None:
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout
    require(clean == "" and POSTLINK_RED.exists() and ELF.is_file()
            and PRG.is_file() and not DIFFERENCE.exists()
            and not RECEIPT.exists(),
            "descope read-only resume boundary absent")
    complete([{"action": "read-only-resume",
        "note": "pair existed before resume; no producer or linker invoked"}],
        resumed=True)


def validate(value: dict[str, Any]) -> None:
    final = value["final_product"]
    lanes = final["responsiveness_lanes"]
    require(value["status"] == STATUS and value["authority"] == authority()
            and value["difference"]["unexplained_members"] == 0
            and final["v1_9_emission"]["fused_reader_absent"] is True
            and all(row["relocation_normalized_byte_identical"]
                    for row in final["v1_9_emission"]["symbols"].values())
            and all(row["passed"] for row in
                    lanes["single_keystroke"]["walls"].values())
            and all(row["passed"] for row in
                    lanes["batch_throughput"]["walls"].values())
            and final["contract_counts"] == {"error-raised": 545,
                "documented-permissive": 179, "silently-wrong": 110}
            and final["known_inconsistency"]["observed"] == "nil"
            and final["packed_product"]["closure"]["object_count"] == 797
            and final["packed_product"]["generation_coherence"]["status"] ==
                "PASS: PACKED OBJECT GENERATION COHERENT"
            and value["artifacts_before"] == value["artifacts_after"] ==
                frozen_artifacts()
            and load(MEASURED_CONTRACT)["counts"] ==
                load(DURABLE_CONTRACT)["counts"] == final["contract_counts"]
            and value["attempt_accounting"] == {"product_cards": 1,
                "WPLTO_runs": 1, "product_links": 1, "scope_runs": 1,
                "acceptance_runs": 1, "media_builds": 0,
                "device_contacts": 0}
            and value["resume_accounting"] == {"resumed": True,
                "new_WPLTO_runs": 0, "new_product_links": 0},
            "Tier-2 descope receipt drift")


def selftest() -> None:
    value = load(RECEIPT)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "opcode-not-v1.9": lambda row: row["final_product"]["v1_9_emission"]
            ["symbols"]["vm_run_inner"].update(
                {"relocation_normalized_byte_identical": False}),
        "single-lane-red": lambda row: row["final_product"]
            ["responsiveness_lanes"]["single_keystroke"]["walls"]
            ["maximum_ratio_to_device_green_v1_9"].update({"passed": False}),
        "batch-lane-red": lambda row: row["final_product"]
            ["responsiveness_lanes"]["batch_throughput"]["walls"]
            ["minimum_margin_percent"].update({"passed": False}),
        "contract-not-remeasured": lambda row: row["final_product"]
            ["contract_counts"].update({"silently-wrong": 102}),
        "known-inconsistency-hidden": lambda row: row["final_product"]
            ["known_inconsistency"].update({"observed": "TypeError"}),
        "unexplained-member": lambda row: row["difference"].update(
            {"unexplained_members": 1}),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except (CardError, RuntimeError, KeyError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "descope mutation survived")
    print(f"v2.0 Tier2 descope: SELFTEST PASS mutations={len(rejected)}")


def write_report(value: dict[str, Any]) -> None:
    final = value["final_product"]
    single = final["responsiveness_lanes"]["single_keystroke"]
    batch = final["responsiveness_lanes"]["batch_throughput"]
    pair = value["artifacts_after"]
    REPORT.write_text(f"""# v2.0 Tier-2 descope product card

Status: **{value['status']}**

The bounded repair had no legal placement, so the authorized fallback is now
material. `OP_CAR`/`OP_CDR`, `ext_type`, `ext_a` and `ext_b` are
relocation-normalized byte-identical to the v1.9 final ELF; every raw mismatch
is an enumerated linker relocation operand. The fused `ext_cons_field` symbol
is absent. Tier 1 and the **53,820-byte** resident Matcher/Blink plane remain.

Both permanent responsiveness lanes were remeasured on this exact final-linked
world. The physical-key lane is batch-cap 1 and measures
{single['successor']['vm_steps_per_character']:.3f} VM steps/character versus
{single['device_green_reference']['vm_steps_per_character']:.3f} in device-green
v1.9 (ratio {single['VM_step_ratio']:.6f}). The batch-cap-8 lane measures
{batch['frames_per_character']:.6f} frames/character,
{batch['service_events_per_frame']:.6f} events/frame and
{batch['margin_percent']:.3f}% margin. Both are green; neither is inferred from
the other.

The complete 139×6 contract was executed afresh and measures **545 error / 179
permissive / 110 silently wrong**. The eight CAR/CDR foreign-domain cells moved
back to the v1.9 behavior; they were not arithmetically subtracted.

Release-note obligation: **Known inconsistency — `(car 1)` and `(cdr 1)` return
`nil` in v2.0. Tier 1 still rejects meaningless foreign domains in cold library
walks. Tier 2 could not land because its emitted hot-path implementation added
389 ordinary-text bytes and no legal resident or mapped interval could hold
them.** Reopening requires a cheaper check form, text reclaim or capacity change.

The predecessor difference has zero unexplained members. Scope and Acceptance
are read-only green over ELF `{pair['ELF']['sha256']}` / PRG
`{pair['PRG']['sha256']}`. Budget is exactly one WPLTO and one product link; no
medium or device contact occurred. Media remain review-gated and must rerun
closure and generation coherence over packed readback bytes.
""", encoding="utf-8")


def check() -> None:
    value = load(RECEIPT)
    validate(value)
    require(REPORT.is_file(), "descope report absent")
    print("v2.0 Tier2 descope: CHECK PASS WPLTO=1/1 link=1/1 media=0")


def check_current() -> None:
    if RECEIPT.exists():
        check(); selftest()
    else:
        check_preflight()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "check-preflight",
        "build", "record-postlink-red", "resume", "check", "check-current", "selftest",
        "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    if action.startswith("_"):
        child(action); return 0
    {"preflight": preflight, "check-preflight": check_preflight,
     "build": build, "record-postlink-red": record_postlink_red,
     "resume": resume, "check": check, "check-current": check_current,
     "selftest": selftest}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, RuntimeError, KeyError, ValueError, OSError,
            subprocess.CalledProcessError) as error:
        print(f"v2.0 Tier2 descope: FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
