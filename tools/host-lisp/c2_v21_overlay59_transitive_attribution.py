#!/usr/bin/env python3
"""Attribute the Workbench-overlay 1,792/1,851 Final Red without a card."""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable
import zlib


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_v20_vma_invariant_golden as VMA  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
GOLDEN = ROOT / (
    "tests/bytecode/dialect-v2/golden-layout/"
    "c2-full-map-owned-vma-invariants-v3.json")
LINKER = ROOT / "scripts/lisp65-mega65-workbench-overlay.ld"
BUILD = ROOT / "build/c2.3/v2.1-pinned-constant-card/wplto"
CURRENT_ELF = BUILD / "lisp65-c2-substitution-linked.prg.elf"
SCRATCH = BUILD / (
    "fresh-c2-lite-prelink-gates/bank2-target-stage/"
    "current-workbench-overlay.bin")
SESSION = BUILD / "runtime-overlays-session-final.json"
F1_ELF = ROOT / (
    "build/post-promotion/f1/product-shaped/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
LINK97_ELF = ROOT / (
    "build/c2.3/v1.5.0-candidate-product-link97/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
FINAL_RED = ARCH / "c2.3-v2.1-pinned-constant-card-final-red.json"
RED_ATTRIBUTION = ARCH / (
    "c2.3-v2.1-pinned-constant-card-red-attribution-receipt.json")
DIRECT_SWEEP = ARCH / "c2.3-v2.1-pinned-constant-sweep-receipt.json"
F1 = HOST / "c2_f1_published_value_call_wplto.py"
CANONICAL = HOST / "c2_lite_canonical_product.py"
BANK2 = HOST / "c2_lite_v6_bank2_target_stage_successor_link.py"
EXPORT = HOST / "c2_lite_v6_export_symbol_domain_successor_link.py"
FINAL_ISLAND = HOST / "c2_lite_v6_final_island_identity_successor_link.py"
RTOV = HOST / "c2_lite_v6_rtov_crc_real_abi_successor_link.py"
DRIVER = Path(__file__).resolve()
RECEIPT = ARCH / (
    "c2.3-v2.1-overlay59-transitive-attribution-receipt.json")
AUTHORIZATION = "e6bf8f17"
RECORDED_ON = "2026-08-14"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
FORMAT = "lisp65-c2.3-v2.1-overlay59-transitive-attribution-v1"
STATUS = (
    "ATTRIBUTED: 1792 is a real runtime-slice cap misapplied to the "
    "independent Workbench arena")


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


def git_binding(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    authority = git_binding(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{authority['commit']}:{authority['path']}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().split()).lower()
    for token in (
            "overlay-59 attribution commissioned", "is 1,792 a contracted",
            "what exactly grew", "sweep completes transitively",
            "card question returns to the owner"):
        require(token in text, f"overlay-59 authorization absent: {token}")
    return authority


def function(text: str, name: str) -> ast.FunctionDef:
    nodes = [node for node in ast.walk(ast.parse(text))
             if isinstance(node, ast.FunctionDef) and node.name == name]
    require(len(nodes) == 1, f"unique function absent: {name}")
    return nodes[0]


def source_gate(overrides: dict[str, str] | None = None) -> dict[str, Any]:
    paths = {"f1": F1, "canonical": CANONICAL, "bank2": BANK2,
             "export": EXPORT, "final_island": FINAL_ISLAND, "rtov": RTOV}
    text = {name: path.read_text(encoding="utf-8")
            for name, path in paths.items()}
    if overrides:
        text.update(overrides)
    fixture = ast.unparse(function(text["f1"], "bank2_fixture_product"))
    target = ast.unparse(function(text["f1"], "bank2_target_fixture"))
    bank2_replacement = ast.unparse(function(text["bank2"], "replacement"))
    export_replacement = ast.unparse(function(text["export"], "replacement"))
    island_replacement = ast.unparse(
        function(text["final_island"], "replacement"))
    rtov_build = ast.unparse(function(text["rtov"], "build"))
    require(
        "BASE_LINK.replacement_gates(product, elf, prelink)" in rtov_build
        and "value = old['replacement'](product, elf, host)"
            in island_replacement
        and "value = old['replacement'](product, elf, host)"
            in export_replacement
        and "value = old['replacement'](product, elf, host)"
            in bank2_replacement
        and "B.target_fixture(REPLAY.fixture_product())"
            in bank2_replacement,
        "observed replacement wrapper chain no longer closes transitively")
    require(
        "CAN.fresh_bank2_fixture_product = bank2_fixture_product"
            in text["f1"]
        and "CAN.fresh_bank2_target_fixture = bank2_target_fixture"
            in text["f1"]
        and "BANK2_REPLAY.fixture_product = fresh_bank2_fixture_product"
            in text["canonical"]
        and "BANK2_REPLAY.B.target_fixture = fresh_bank2_target_fixture"
            in text["canonical"],
        "configured F1 helper identity chain drift")
    require(
        "artifacts['code']['bytes'] == EXPECTED_STATIC" in fixture
        and "bind(expected_path) == artifacts['code']" in target
        and "0 < len(scratch) <= min(1792, static_bytes)" in target
        and "cursor == static_bytes" in target
        and "scratch_matches == 0" in target,
        "terminal F1 helper expectation closure drift")
    return {
        "status": "PASS: configured replacement path closed through F1 helper",
        "observed_wrappers": [
            "c2_lite_v6_rtov_crc_real_abi_successor_link.build",
            "c2_lite_v6_final_island_identity_successor_link.replacement",
            "c2_lite_v6_export_symbol_domain_successor_link.replacement",
            "c2_lite_v6_bank2_target_stage_successor_link.replacement",
            "c2_f1_published_value_call_wplto.bank2_fixture_product",
            "c2_f1_published_value_call_wplto.bank2_target_fixture",
        ],
        "configured_helper_substitutions": 4,
        "terminal_expectation_classes": [
            {"id": "sealed-F1-fixture-artifact-sizes",
             "classification": "sealed-fixture-identity"},
            {"id": "six-record-layout-and-CRC",
             "classification": "format-and-content-contract"},
            {"id": "Bank2-target-phase-cap",
             "classification": "runtime-slice-contract"},
            {"id": "Workbench-scratch-nonempty",
             "classification": "negative-fixture-shape"},
            {"id": "Workbench-scratch-1792-ceiling",
             "classification": "improper-cross-domain-pin"},
            {"id": "Workbench-scratch-zero-passing-records",
             "classification": "content-derived-negative"},
        ],
        "terminal_expectation_class_count": 6,
        "improper_pin_count": 1,
    }


def source_mutations() -> list[str]:
    base = {name: path.read_text(encoding="utf-8") for name, path in {
        "f1": F1, "canonical": CANONICAL, "bank2": BANK2,
        "export": EXPORT, "final_island": FINAL_ISLAND, "rtov": RTOV}.items()}
    cases = [
        ("drop-helper-of-helper-fixture", "f1",
         "CAN.fresh_bank2_fixture_product = bank2_fixture_product",
         "CAN.fresh_bank2_fixture_product = lambda: {}"),
        ("drop-configured-target-helper", "canonical",
         "BANK2_REPLAY.B.target_fixture = fresh_bank2_target_fixture",
         "BANK2_REPLAY.B.target_fixture = lambda product: {}"),
        ("truncate-wrapper-chain", "bank2",
         "B.target_fixture(REPLAY.fixture_product())",
         "{}"),
        ("hide-cross-domain-pin", "f1",
         "min(1792, static_bytes)", "min(2730, static_bytes)"),
        ("drop-fixture-content-binding", "f1",
         "bind(expected_path) == artifacts[\"code\"]",
         "expected_path.is_file()"),
        ("drop-record-closure", "f1", "cursor == static_bytes",
         "cursor > 0"),
    ]
    rejected: list[str] = []
    for name, role, old, new in cases:
        require(old in base[role], f"source mutation anchor absent: {name}")
        mutant = dict(base); mutant[role] = mutant[role].replace(old, new, 1)
        try:
            source_gate(mutant)
        except (AttributionError, SyntaxError):
            rejected.append(name)
    require(rejected == [name for name, *_rest in cases],
            "transitive source mutation survived")
    return rejected


def section_members(truth: ElfTruth) -> dict[str, Any]:
    section = truth.section(".lisp65_workbench_overlay")
    members = [row for row in truth.symbols
               if row.section == section.name and row.bytes > 0]
    require(sum(row.bytes for row in members) == section.bytes,
            "Workbench member symbols do not close the section")
    objects = [row for row in members if row.symbol_type == "Object"]
    functions = [row for row in members if row.symbol_type == "Function"]
    return {
        "section": {"vma": section.address, "bytes": section.bytes,
                    "end_exclusive": section.address + section.bytes},
        "functions": {row.name: row.bytes for row in functions},
        "objects": {row.name: row.bytes for row in objects},
        "function_bytes": sum(row.bytes for row in functions),
        "object_bytes": sum(row.bytes for row in objects),
    }


def member_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_members = {**before["functions"], **before["objects"]}
    after_members = {**after["functions"], **after["objects"]}
    names = sorted(set(before_members) | set(after_members))
    changed = [{"name": name, "before_bytes": before_members.get(name, 0),
                "after_bytes": after_members.get(name, 0),
                "delta_bytes": after_members.get(name, 0)
                    - before_members.get(name, 0)}
               for name in names
               if before_members.get(name, 0) != after_members.get(name, 0)]
    total = (after["section"]["bytes"] - before["section"]["bytes"])
    require(sum(row["delta_bytes"] for row in changed) == total,
            "Workbench member deltas do not close the section delta")
    return {"before_bytes": before["section"]["bytes"],
            "after_bytes": after["section"]["bytes"],
            "delta_bytes": total, "changed_members": changed,
            "unchanged_member_count": len(names) - len(changed)}


def terminal_consumer_replay() -> dict[str, Any]:
    """Evaluate every F1 target-fixture predicate on the frozen bytes."""
    f1_root = ROOT / "build/post-promotion/f1"
    artifacts = {
        "c2d": bind(f1_root / "v6-semantics/initial.c2d-v6.bin"),
        "code": bind(f1_root / "v6-semantics/bank2-static-code.bin"),
        "shelf": bind(f1_root / "product/product-shelf-v4-direct.bin"),
    }
    require((artifacts["c2d"]["bytes"], artifacts["code"]["bytes"],
             artifacts["shelf"]["bytes"]) == (33840, 34748, 71710),
            "sealed F1 fixture identity drift")
    shelf = (ROOT / artifacts["shelf"]["path"]).read_bytes()
    c2d = (ROOT / artifacts["c2d"]["path"]).read_bytes()
    expected = (ROOT / artifacts["code"]["path"]).read_bytes()
    scratch = SCRATCH.read_bytes()
    cursor = 0; rows: list[dict[str, Any]] = []
    for image in range(6):
        shelf_record = shelf[32 + image * 32:64 + image * 32]
        c2d_record = c2d[48 + image * 32:80 + image * 32]
        source = int.from_bytes(shelf_record[8:11], "little")
        length = int.from_bytes(shelf_record[11:13], "little")
        crc = int.from_bytes(shelf_record[18:22], "little")
        target = int.from_bytes(c2d_record[18:21], "little")
        require(
            target == cursor
            and int.from_bytes(c2d_record[21:23], "little") == length
            and zlib.crc32(shelf[source:source + length]) & 0xffffffff == crc
            and zlib.crc32(expected[target:target + length])
                & 0xffffffff == crc,
            f"terminal F1 record {image} replay red")
        rows.append({"image": image, "source": source, "target": target,
                     "bytes": length, "crc32": f"0x{crc:08x}"})
        cursor += length
    require(cursor == len(expected) == 34748,
            "terminal F1 record replay does not close the plane")
    scratch_plane = scratch + bytes(len(expected) - len(scratch))
    scratch_matches = sum(
        (zlib.crc32(scratch_plane[row["target"]:
                                  row["target"] + row["bytes"]])
         & 0xffffffff) == int(row["crc32"], 16) for row in rows)
    predicates = {
        "artifact_binding": bind(ROOT / artifacts["code"]["path"])
            == artifacts["code"],
        "plane_length": len(expected) == artifacts["code"]["bytes"],
        "scratch_nonempty": len(scratch) > 0,
        "scratch_under_misapplied_1792": len(scratch) <= 1792,
        "six_records_close_plane": cursor == len(expected),
        "scratch_passing_records_zero": scratch_matches == 0,
    }
    require(predicates == {
        "artifact_binding": True, "plane_length": True,
        "scratch_nonempty": True, "scratch_under_misapplied_1792": False,
        "six_records_close_plane": True,
        "scratch_passing_records_zero": True},
        "terminal F1 predicate replay drift")
    return {"status": "PASS: only cross-domain 1792 predicate is red",
            "records": rows, "predicates": predicates,
            "downstream_hidden_reds": 0,
            "actual_workbench_bytes": len(scratch)}


def derive() -> dict[str, Any]:
    red = load(FINAL_RED); attribution = load(RED_ATTRIBUTION)
    direct = load(DIRECT_SWEEP); golden = load(GOLDEN)
    require(red.get("retry_authorized") is False
            and attribution.get("status", "").startswith("ATTRIBUTED FINAL RED")
            and direct["sweep"]["expectation_count"] == 14
            and direct["sweep"]["pinned_count"] == 0,
            "Final Red/direct-sweep authority drift")
    error = red["error"]["message"]
    for token in (
            "c2_lite_v6_rtov_crc_real_abi_successor_link.py",
            "c2_lite_v6_final_island_identity_successor_link.py",
            "c2_lite_v6_export_symbol_domain_successor_link.py",
            "c2_lite_v6_bank2_target_stage_successor_link.py",
            "c2_f1_published_value_call_wplto.py"):
        require(token in error, f"actual configured stack omits {token}")

    # This question is capacity-domain-specific.  The full VMA projection has
    # a separately booked one-byte reopen-gap receipt drift; do not broaden
    # this attribution into that unrelated authority rebind.
    layout = VMA.LEGACY.layout_from_elf(CURRENT_ELF)
    VMA.V2.validate_capacities(layout, golden)
    capacity_measurements = VMA.V2.capacity_measurements(layout, golden)
    arenas = {row["id"]: row for row in golden["capacity_arenas"]}
    workbench_arena = arenas["workbench-boot-overlay"]
    runtime_arena = arenas["runtime-overlay-slices"]
    require(len(arenas) == 11
            and workbench_arena == {
                "end_exclusive": 52736, "id": "workbench-boot-overlay",
                "members": [".lisp65_workbench_overlay"],
                "policy": "independent-alternate-overlay",
                "space": "boot-overlay", "start": 50006}
            and runtime_arena["start"] == 50006
            and runtime_arena["end_exclusive"] == 51798,
            "Golden capacity-domain partition drift")
    linker = LINKER.read_text(encoding="utf-8")
    require("__lisp65_workbench_runtime_transport_max_bytes = 1792;"
            in linker, "runtime transport cap source drift")
    session = load(SESSION)
    entries = [row for row in session["slices"]
               if row["section"] == ".lisp65_rt_c2append_entries"]
    largest_runtime = max(session["slices"], key=lambda row: row["file_size"])
    require(session["policy"]["max_slice_bytes"] == 1792
            and len(entries) == 1 and entries[0]["file_size"] == 1771
            and largest_runtime["section"]
                == ".lisp65_rt_c2append_publish_plan_scan"
            and largest_runtime["file_size"] == 1786,
            "runtime-slice 1,792/1,771 evidence drift")

    current_truth = ElfTruth.read(CURRENT_ELF, llvm_readobj=READOBJ)
    f1_truth = ElfTruth.read(F1_ELF, llvm_readobj=READOBJ)
    link97_truth = ElfTruth.read(LINK97_ELF, llvm_readobj=READOBJ)
    current = section_members(current_truth)
    f1 = section_members(f1_truth)
    link97 = section_members(link97_truth)
    origin_delta = member_delta(f1, current)
    predecessor_delta = member_delta(link97, current)
    require(origin_delta["delta_bytes"] == 141
            and origin_delta["changed_members"] == [
                {"name": "eval_init", "before_bytes": 1102,
                 "after_bytes": 1236, "delta_bytes": 134},
                {"name": "workbench_boot_name_intern", "before_bytes": 0,
                 "after_bytes": 7, "delta_bytes": 7}]
            and predecessor_delta["delta_bytes"] == 2
            and predecessor_delta["changed_members"] == [
                {"name": "eval_init", "before_bytes": 1234,
                 "after_bytes": 1236, "delta_bytes": 2}],
            "Workbench member attribution drift")
    workbench_capacity = (workbench_arena["end_exclusive"]
                          - workbench_arena["start"])
    runtime_capacity = runtime_arena["end_exclusive"] - runtime_arena["start"]
    require(current["section"] == {
        "vma": 50006, "bytes": 1851, "end_exclusive": 51857}
        and workbench_capacity == 2730 and runtime_capacity == 1792,
        "candidate/arena capacity arithmetic drift")

    transitive = source_gate()
    terminal = terminal_consumer_replay()
    return {
        "format": FORMAT, "recorded_on": RECORDED_ON, "status": STATUS,
        "authority": {"authorization": authorization(),
            "final_red": bind(FINAL_RED),
            "red_attribution": bind(RED_ATTRIBUTION),
            "direct_sweep": bind(DIRECT_SWEEP), "golden": bind(GOLDEN),
            "linker_contract": bind(LINKER), "candidate_ELF": bind(CURRENT_ELF),
            "F1_origin_ELF": bind(F1_ELF), "Link97_ELF": bind(LINK97_ELF),
            "session_manifest": bind(SESSION), "scratch": bind(SCRATCH),
            "driver": bind(DRIVER),
            "transitive_sources": {name: bind(path) for name, path in {
                "rtov": RTOV, "final_island": FINAL_ISLAND,
                "export": EXPORT, "bank2": BANK2,
                "canonical": CANONICAL, "F1": F1}.items()}},
        "capacity_answer": {
            "classification": "REAL-CONTRACT-IN-WRONG-DOMAIN",
            "golden_capacity_arena_count": len(arenas),
            "runtime_slice_domain": {"capacity_bytes": runtime_capacity,
                "historical_pricing_witness": {
                    "section": ".lisp65_rt_c2append_entries",
                    "bytes": entries[0]["file_size"],
                    "headroom_bytes": runtime_capacity
                        - entries[0]["file_size"]},
                "current_largest_tenant": {
                    "section": largest_runtime["section"],
                    "bytes": largest_runtime["file_size"],
                    "headroom_bytes": runtime_capacity
                        - largest_runtime["file_size"]}},
            "workbench_boot_domain": {"capacity_bytes": workbench_capacity,
                "candidate_bytes": current["section"]["bytes"],
                "headroom_bytes": workbench_capacity
                    - current["section"]["bytes"],
                "policy": workbench_arena["policy"]},
            "VMA_golden_capacity_validation": {
                "status": "passed-all-eleven-capacity-arenas",
                "measurements": capacity_measurements,
                "full_projection_claimed": False,
                "excluded_known_drift":
                    ".lisp65_c2_kernal_window.reopen_gap0 one-byte rebind"},
            "decision": (
                "1,792 is a contracted runtime-slice capacity, but the F1 "
                "helper applies it to the independent Workbench boot overlay. "
                "The candidate has 879 bytes of its actual arena free; this "
                "is a checker-domain defect, not a freight-capacity finding."),
        },
        "growth_answer": {
            "claimed_59_is_world_delta": False,
            "arithmetic_only": {"candidate_bytes": 1851,
                "misapplied_ceiling_bytes": 1792, "difference_bytes": 59},
            "immediate_predecessor_Link97": predecessor_delta,
            "F1_checker_origin_world": origin_delta,
            "decision": (
                "No world-to-world 59-byte growth exists. Link97 to the "
                "candidate is +2 bytes, solely eval_init. The F1 helper's "
                "own origin world to the candidate is +141 bytes: eval_init "
                "+134 and the new 7-byte intern name object."),
        },
        "transitive_sweep": {
            **transitive,
            "prior_direct_expectations_revalidated": 14,
            "actual_consumer_evidence": "consumed card traceback",
            "terminal_semantic_replay": terminal,
            "complete_for": (
                "configured replacement-stage execution path through the "
                "terminal F1 consumer, including all of that consumer's "
                "post-predicate record and CRC checks"),
            "not_claimed": [
                "post-red real-ABI consumer",
                "completion, acceptance, media or device paths",
                "a future card preflight run"],
            "result": "exactly one improper terminal pin; no hidden F1 red",
        },
        "disposition_boundary": {
            "capacity_freight_disposition_supported": False,
            "checker_conversion_supported": True,
            "card_authorized": False, "completion_allowed": False,
            "media_allowed": False, "device_allowed": False,
            "owner_disposition_required": True,
        },
        "claim_limit": (
            "Host-only attribution and transitive terminal-consumer closure. "
            "No source fix, card, WPLTO, link, completion, media or device."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(value.get("format") == FORMAT and value.get("status") == STATUS
            and value["capacity_answer"]["classification"]
                == "REAL-CONTRACT-IN-WRONG-DOMAIN"
            and value["capacity_answer"]["workbench_boot_domain"]
                ["headroom_bytes"] == 879
            and value["growth_answer"]["claimed_59_is_world_delta"] is False
            and value["transitive_sweep"]["improper_pin_count"] == 1
            and value["transitive_sweep"]["terminal_semantic_replay"]
                ["downstream_hidden_reds"] == 0
            and value["disposition_boundary"]["card_authorized"] is False,
            "overlay-59 attribution receipt red")
    if verify:
        require(value == derive(), "overlay-59 attribution authority drift")


def receipt_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "call-1792-workbench-capacity": lambda x: x["capacity_answer"].update(
            classification="WORKBENCH-CAPACITY"),
        "erase-real-workbench-headroom": lambda x: x["capacity_answer"]
            ["workbench_boot_domain"].update(headroom_bytes=0),
        "call-59-world-growth": lambda x: x["growth_answer"].update(
            claimed_59_is_world_delta=True),
        "hide-eval-growth": lambda x: x["growth_answer"]
            ["F1_checker_origin_world"]["changed_members"].pop(0),
        "hide-intern-growth": lambda x: x["growth_answer"]
            ["F1_checker_origin_world"]["changed_members"].pop(),
        "hide-improper-pin": lambda x: x["transitive_sweep"].update(
            improper_pin_count=0),
        "invent-hidden-F1-red": lambda x: x["transitive_sweep"]
            ["terminal_semantic_replay"].update(downstream_hidden_reds=1),
        "broaden-beyond-proof": lambda x: x["transitive_sweep"].update(
            not_claimed=[]),
        "authorize-card": lambda x: x["disposition_boundary"].update(
            card_authorized=True),
        "allow-device": lambda x: x["disposition_boundary"].update(
            device_allowed=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate, verify=True)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases), "overlay-59 receipt mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "overlay-59 attribution receipt exists")
    value = derive(); validate(value, verify=True)
    value["source_mutations_rejected"] = source_mutations()
    value["receipt_mutations_rejected"] = receipt_mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("2.1 overlay-59 attribution: PASS runtime-cap=1792 "
          "workbench-cap=2730 headroom=879 world-delta=not-59 "
          "transitive-pin=1")


def check() -> None:
    value = load(RECEIPT)
    source_rejected = value.pop("source_mutations_rejected", None)
    receipt_rejected = value.pop("receipt_mutations_rejected", None)
    validate(value, verify=True)
    require(source_rejected == source_mutations()
            and receipt_rejected == receipt_mutations(value),
            "overlay-59 mutation inventory drift")
    print("2.1 overlay-59 attribution: CHECK PASS runtime-cap=1792 "
          "workbench-cap=2730 headroom=879 transitive-pin=1")


def selftest() -> None:
    value = derive(); validate(value, verify=True)
    source_mutations(); receipt_mutations(value)
    print("2.1 overlay-59 attribution: SELFTEST PASS mutations=16")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check", "selftest"))
    {"record": record, "check": check, "selftest": selftest}[
        parser.parse_args().action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"2.1 overlay-59 attribution: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
