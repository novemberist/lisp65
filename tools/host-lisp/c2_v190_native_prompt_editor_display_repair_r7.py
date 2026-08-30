#!/usr/bin/env python3
"""Repair the v1.9 B-light prompt/editor positioning split in one r7 round."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import inspect
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_v190_native_prompt_editor_r6_card as R6  # noqa: E402


CARD = R6.CARD
BASE = R6.BASE
CLIENT = CARD.CLIENT
PRICE = CARD.PRICE
PRODUCT = R6.PRODUCT
DEVICE = CARD.DEVICE
P0 = PRICE.P0
DISPLAY = PRICE.DISPLAY
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
DECISION = ROOT / "config/c2-v190-native-prompt-editor-display-repair-r7.json"
RESUME_DECISION = ROOT / (
    "config/c2-v190-native-prompt-editor-display-repair-r7-resume.json")
FIRST_RED_ATTRIBUTION = ARCH / (
    "c2.3-v1.9-native-prompt-editor-display-first-red-attribution.json")
R6_BUILD = R6.BUILD
R6_ELF = R6.ELF
R6_PRG = R6.PRG
R6_PROFILE = R6.PROFILE
R6_SOURCE = ROOT / (
    "build/c2.3/v1.9-native-prompt-editor-card-r1-preflight/"
    "sources/stdlib-read-line.lisp")
R6_PLANE = ROOT / (
    "build/c2.3/v1.9-native-prompt-editor-card-r1-preflight/"
    "setup-owned/static-plane/narrow-static")
BUILD = ROOT / "build/c2.3/v1.9-native-prompt-editor-display-repair-r7"
PREFLIGHT = ROOT / (
    "build/c2.3/v1.9-native-prompt-editor-display-repair-r7-preflight")
PLANE_ROOT = PREFLIGHT / "setup-owned/static-plane/narrow-static"
PLANE_RECEIPT = PREFLIGHT / "v19-display-repair-static-plane.json"
CLIENT_SOURCE = PREFLIGHT / "sources/stdlib-read-line.lisp"
C2D = PLANE_ROOT / "v6-semantics/initial.c2d-v6.bin"
CODE = PLANE_ROOT / "v6-semantics/bank2-static-code.bin"
MANIFEST = PLANE_ROOT / "stdlib-p0.manifest.json"
HEADER = PLANE_ROOT / "stdlib-p0.h"
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
PROFILE = BUILD / "wplto/resolved-profile.txt"
INVOCATION = PREFLIGHT / "candidate-invocation-r7.json"
PREFLIGHT_RECEIPT = ARCH / (
    "c2.3-v1.9-native-prompt-editor-display-repair-r7-preflight.json")
DIFFERENCE = ARCH / (
    "c2.3-v1.9-native-prompt-editor-display-repair-r6-r7-difference.json")
RECEIPT = ARCH / (
    "c2.3-v1.9-native-prompt-editor-display-repair-r7-receipt.json")
FINAL_RED = ARCH / (
    "c2.3-v1.9-native-prompt-editor-display-repair-r7-final-red.json")
FINAL_RED_ATTRIBUTION = ARCH / (
    "c2.3-v1.9-native-prompt-editor-display-repair-r7-final-red-attribution.json")
ERA_CONVERSION = ARCH / (
    "c2.3-v1.9-native-prompt-editor-display-repair-r7-era-conversion.json")
REPORT = ROOT / (
    "docs/planning/v1.9.0-native-prompt-editor-display-repair-report.md")
DRIVER = Path(__file__).resolve()
FORMAT = "lisp65-c2-v190-native-prompt-editor-display-repair-r7-v1"
STATUS = "PASS: V1.9 B-LIGHT DISPLAY REPAIR R7 GREEN"


class RepairError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RepairError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def authority() -> dict[str, Any]:
    decision = load(DECISION)
    first_red = load(FIRST_RED_ATTRIBUTION)
    inherited = load(R6.RECEIPT)
    require(decision["status"] == "one-bounded-daily-use-repair-authorized"
            and decision["budget"] == {"WPLTO_runs": 1, "product_links": 1,
                "media_builds": 0, "device_contacts": 0}
            and first_red["status"] ==
                "ATTRIBUTED: TWO POSITIONING MODELS SPLIT PROMPT AND CURSOR"
            and first_red["device_claims_accepted_before_stop"] == []
            and inherited["status"] == R6.STATUS,
            "r7 owner/first-red/r6 authority drift")
    return {"decision": bind(DECISION),
            "device_first_red_attribution": bind(FIRST_RED_ATTRIBUTION),
            "r6_predecessor": bind(R6.RECEIPT),
            "budget": decision["budget"]}


def resume_authority() -> dict[str, Any]:
    decision = load(RESUME_DECISION)
    red = load(FINAL_RED)
    red_attribution = load(FINAL_RED_ATTRIBUTION)
    frozen = frozen_artifacts()
    require(decision["status"] ==
                "zero-build-era-conversion-and-read-only-resume-authorized"
            and decision["budget"] == {"WPLTO_runs": 0, "product_links": 0,
                "media_builds": 0, "device_contacts": 0}
            and decision["frozen_pair"] == {
                "ELF_sha256": frozen["ELF"]["sha256"],
                "PRG_sha256": frozen["PRG"]["sha256"]}
            and red["error"] ==
                "r2/r3 stdlib-header consumption closure drift"
            and red_attribution["status"] ==
                "ATTRIBUTED: HISTORICAL R2/R3 CLOSURE CONSUMED LIVE R7 HEADER WORLD"
            and red_attribution["product_defect_not_established"] is True,
            "r7 resume owner/frozen-pair authority drift")
    return {"repair_authority": authority(),
            "resume_decision": bind(RESUME_DECISION),
            "first_red": bind(FINAL_RED),
            "first_red_attribution": bind(FINAL_RED_ATTRIBUTION),
            "budget": decision["budget"]}


def _consumers_match(rows: dict[str, Any], header: dict[str, Any]) -> bool:
    if set(rows) != {"seed", "final"}:
        return False
    return all(
        row.get("result", {}).get("status") ==
            "passed-bound-candidate-stdlib-header-consumed"
        and row["result"].get("bound_header") == header
        and row["result"].get("materialized_header") == header
        and row["result"].get("consumed_value") == 239
        and row["result"].get("materialized_value") == 239
        and row["result"].get("actual_force_include_flags", [None, None])[1]
            == header["path"]
        for row in rows.values())


def era_separated_header_consumption() -> dict[str, Any]:
    """Keep the sealed predecessor proof and live r7 proof in their worlds."""
    r6_receipt = load(R6.RECEIPT)
    r6_difference = load(R6.DIFFERENCE)
    require(r6_receipt["status"] == R6.STATUS
            and r6_receipt["attribution"]["receipt"] == bind(R6.DIFFERENCE)
            and r6_difference["status"] ==
                "PASS: R5/R6 AND COMPLETE PRODUCT DIFFERENCES ATTRIBUTED",
            "sealed r6 attribution authority drift")
    sealed = r6_difference["r2_to_r6_complete_product_closure"][
        "stdlib_header_consumption"]
    sealed_header = sealed["r4_candidate_header"]
    sealed_consumers = sealed["r4_real_consumers"]
    for row in sealed_consumers.values():
        receipt = ROOT / row["receipt"]["path"]
        require(bind(receipt) == row["receipt"],
                "sealed header-consumption receipt changed after sealing")
    require(sealed["status"] ==
                "PASS: BOTH R4 COMPILERS CONSUME PATH AND VALUE"
            and _consumers_match(sealed_consumers, sealed_header),
            "sealed r2/r6 header world no longer verifies in its era")

    live_header = bind(HEADER)
    live_consumers = CARD.candidate_stdlib_consumption()
    require(_consumers_match(live_consumers, live_header)
            and live_header != sealed_header,
            "live r7 consumers do not verify in the successor header era")

    mutations = {
        "sealed-consumers-compared-to-live-r7-header":
            not _consumers_match(sealed_consumers, live_header),
        "live-r7-consumers-compared-to-sealed-header":
            not _consumers_match(live_consumers, sealed_header),
    }
    require(all(mutations.values()), "era anti-mixing mutation survived")
    return {
        "status": "PASS: SEALED AND LIVE HEADER WORLDS ARE ERA-SEPARATED",
        "sealed_predecessor": {
            "attribution": bind(R6.DIFFERENCE),
            "header": sealed_header,
            "real_consumers": sealed_consumers,
        },
        "live_successor": {
            "header": live_header,
            "real_consumers": live_consumers,
        },
        "mutations_rejected": mutations,
        "rule": ("sealed evidence verifies against its sealing-era inputs; "
                 "the living successor owns and verifies the r7 header world"),
    }


def inherited_closure_inventory() -> dict[str, Any]:
    """Enumerate inherited candidate-dependent closures before future links."""
    policies = {
        "input_closure": "live-successor comparison",
        "r2_r3_profile_closure": "sealed-anchor to live-successor comparison",
        "r2_r3_header_consumption": "era-separated sealed and live proofs",
        "r2_r3_object_closure": "sealed-anchor to live-successor comparison",
        "r3_r4_emitted_closure": "sealed-anchor to live-successor comparison",
        "r2_r3_product_members": "sealed-anchor to live-successor comparison",
    }
    tree = ast.parse(inspect.getsource(CARD.inherited_product_attribution))
    observed = sorted({node.func.id for node in ast.walk(tree)
                       if isinstance(node, ast.Call)
                       and isinstance(node.func, ast.Name)
                       and node.func.id in policies})
    require(set(observed) == set(policies),
            "inherited candidate-dependent closure inventory drift")

    def policy_valid(rows: dict[str, str]) -> bool:
        return (set(rows) == set(observed)
                and rows["r2_r3_header_consumption"] ==
                    "era-separated sealed and live proofs"
                and all(value != "unclassified" for value in rows.values()))

    mixed = dict(policies)
    mixed["r2_r3_header_consumption"] = "live-successor comparison"
    omitted = dict(policies)
    del omitted["r2_r3_header_consumption"]
    require(policy_valid(policies) and not policy_valid(mixed)
            and not policy_valid(omitted),
            "inherited-closure inventory mutation survived")
    pins = load(PREFLIGHT_RECEIPT)["known_pin_inventory"]
    return {
        "status": "PASS: PINS AND INHERITED CLOSURES ENUMERATED",
        "literal_pin_entries": pins["entries"],
        "inherited_candidate_dependent_closures": [
            {"name": name, "world_policy": policies[name]}
            for name in observed],
        "counts": {"literal_pins": len(pins["entries"]),
                   "inherited_closures": len(observed),
                   "total": len(pins["entries"]) + len(observed)},
        "mutations_rejected": {
            "header-closure-live-only-mixing": True,
            "header-closure-omitted": True,
        },
    }


def era_conversion_gate() -> dict[str, Any]:
    return {"status": "PASS: R7 ERA CONVERSION ARMED READ-ONLY RESUME",
            "authority": resume_authority(),
            "header_worlds": era_separated_header_consumption(),
            "prelink_inventory": inherited_closure_inventory()}


OLD_TAIL = """  (if (= row -2)
      (progn
        (write-char 19)
        (dotimes (line stop nil) (write-char 17)))
"""
NEW_TAIL = """  (if (= row -2)
      (let ((text \"lisp65> \"))
        (dotimes (at 8 nil)
          (screen-put-char at stop (string-ref text at) 1)))
"""
OLD_PROMPT = """(defun %native-prompt (row)
  (progn
    (%rl-screen-tail nil 0 0 row 0 -2)
    (write-string \"lisp65> \")))
"""
NEW_PROMPT = """(defun %native-prompt (row)
  (%rl-screen-tail nil 0 0 row nil -2))
"""


def derive_editor_source() -> str:
    source = R6_SOURCE.read_text(encoding="utf-8")
    require(source.count(OLD_TAIL) == source.count(OLD_PROMPT) == 1,
            "r6 positioning source seam drift")
    return source.replace(OLD_TAIL, NEW_TAIL, 1).replace(
        OLD_PROMPT, NEW_PROMPT, 1)


def validate_editor_source(source: str) -> dict[str, Any]:
    predecessor = R6_SOURCE.read_text(encoding="utf-8")
    require(source == derive_editor_source()
            and source.count(NEW_TAIL) == source.count(NEW_PROMPT) == 1
            and OLD_TAIL not in source and OLD_PROMPT not in source
            and "(write-char 19)" not in source
            and "(write-char 17)" not in source,
            "r7 editor is not the exact one-positioning-model transform")
    # The Phase-1b lifecycle owner is the Block-A source.  r6 additionally
    # composed the prompt helpers, so validating the full r6 source as though
    # it were the sealed lifecycle prefix would conflate two successor layers.
    lifecycle = CARD.ORIGINAL_VALIDATE_CLIENT_SOURCE(
        CARD.BLOCK_A.CLIENT_SOURCE.read_text(encoding="utf-8"))
    return {"status": "PASS: ONE DELIVERED POSITIONING MODEL",
        "predecessor": bind(R6_SOURCE),
        "candidate": {"bytes": len(source.encode()),
            "sha256": hashlib.sha256(source.encode()).hexdigest()},
        "ordered_lifecycle": lifecycle["ordered_lifecycle"],
        "changed_forms": ["%rl-screen-tail", "%native-prompt"],
        "unchanged_forms": 396,
        "positioning_owner": "direct screen-put-char cells on editor row",
        "forbidden_positioning_bytes": [19, 17]}


def editor_mutations(source: str) -> list[dict[str, str]]:
    cases = {
        "restore-device-red-HOME-DOWN-model":
            source.replace(NEW_TAIL, OLD_TAIL, 1).replace(
                NEW_PROMPT, OLD_PROMPT, 1),
        "split-prompt-back-to-sequential-writer": source.replace(
            NEW_PROMPT,
            "(defun %native-prompt (row) (write-string \"lisp65> \"))\n", 1),
        "omit-prompt-row-argument": source.replace(
            "(screen-put-char at stop", "(screen-put-char at 0", 1),
    }
    rejected = []
    for name, trial in cases.items():
        try:
            validate_editor_source(trial)
        except RepairError as error:
            rejected.append({"name": name, "observed_red": str(error)})
    require([row["name"] for row in rejected] == list(cases),
            "r7 positioning source mutation survived")
    return rejected


def configure() -> None:
    R6.configure()
    for name, value in {
        "BUILD": BUILD, "PREFLIGHT": PREFLIGHT, "RECEIPT": RECEIPT,
        "DIFFERENCE": DIFFERENCE, "PRODUCT_FIRST_RED": FINAL_RED,
        "REPORT": REPORT, "ELF": ELF, "PRG": PRG, "PROFILE": PROFILE,
        "PLANE_ROOT": PLANE_ROOT, "PLANE_RECEIPT": PLANE_RECEIPT,
        "CLIENT_SOURCE": CLIENT_SOURCE, "C2D": C2D, "CODE": CODE,
        "MANIFEST": MANIFEST, "HEADER": HEADER, "DRIVER": DRIVER,
        "FORMAT": FORMAT, "STATUS": STATUS,
    }.items():
        setattr(CARD, name, value)
    CARD.derive_editor_source = derive_editor_source
    CARD.validate_editor_source = validate_editor_source
    CARD.editor_mutations = editor_mutations
    CARD.authority = authority
    CARD.setup_child = R6.setup_child
    CARD.attribution = attribution
    CARD.write_report = write_report
    CARD.native_prompt_final_elf = native_prompt_final_elf
    CARD.configure()
    # The inherited closure is deliberately rebound only after CARD.configure:
    # its predecessor evidence and the live successor header are two worlds.
    CARD.r2_r3_header_consumption = era_separated_header_consumption
    BASE.INVOCATION = INVOCATION
    BASE.authority = authority
    BASE.setup_child = R6.setup_child
    BASE.final_gate = final_gate


class TargetFrameVM(DISPLAY.FrameVM):
    """Model the delivered screen driver, including unknown control bytes."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.cursor_row = 9
        self.cursor_column = 0
        self.screen_cells[7 * 80:7 * 80 + 15] = list(b"WORKBENCH 1.9.0")
        self.surface_at_return: bytes | None = None

    def sequential(self, code: int) -> None:
        if code in (10, 13):
            return super().sequential(code)
        # src/screen.c:scr_putc has no HOME/DOWN interpretation. Unknown
        # control bytes map to a blank and still advance the cursor.
        super().sequential(32 if code < 32 else code)

    def _callprim(self, prim_id: int, argc: int, stack: list[int],
                  pc: int | None = None, native_base: int = 0,
                  frame_slots: int = 0) -> int:
        try:
            return super()._callprim(prim_id, argc, stack, pc=pc,
                native_base=native_base, frame_slots=frame_slots)
        except DISPLAY.AtReturn:
            self.surface_at_return = bytes(self.screen_cells)
            raise


def run_surface(source: Path, expr: str, expected: str,
                events: list[int]) -> bytes:
    suite = PRICE.live_suite(source, expr, expected, events)
    (heap, _names, _code, flags, resident, _bundle, directory,
     _cases, entries, _inliner) = P0._compile_suite(suite)
    macros = P0._macro_symbol_objs(heap, flags, resident)
    abi_profile, abi_ledger = P0._suite_abi(suite)
    vm = TargetFrameVM(heap=heap.clone(), directory=directory,
        macro_symbols=macros, max_steps=1_000_000,
        max_call_args=suite.get("max_call_args"), key_events=events,
        private_key_event_modes=True, abi_profile=abi_profile,
        abi_ledger=abi_ledger, stop_at_return=True)
    try:
        vm.run(directory[heap.intern(entries[0])], [])
    except DISPLAY.AtReturn:
        pass
    else:
        raise RepairError("25-row framebuffer witness missed return handoff")
    require(vm.surface_at_return is not None, "25-row framebuffer absent")
    return vm.surface_at_return


def row(surface: bytes, index: int) -> str:
    return surface[index * 80:(index + 1) * 80].decode("latin-1")


def full_framebuffer_gate() -> dict[str, Any]:
    events = [ord("a"), ord("c"), 157, ord("b"), 13]
    current = run_surface(CLIENT_SOURCE, "(%native-read-line)", "abc", events)
    predecessor = run_surface(R6_SOURCE, "(%native-read-line)", "abc", events)
    ordinary_current = run_surface(
        CLIENT_SOURCE, "(read-line)", "abc", [97, 98, 99, 13])
    ordinary_predecessor = run_surface(
        R6_SOURCE, "(read-line)", "abc", [97, 98, 99, 13])
    require(len(current) == 2000
            and row(current, 24).startswith("lisp65> abc")
            and "lisp65>" not in row(current, 9)
            and row(predecessor, 9)[25:33] == "lisp65> "
            and row(predecessor, 24)[8:11] == "abc"
            and "lisp65>" not in row(predecessor, 24)
            and ordinary_current == ordinary_predecessor,
            "target-faithful composed 25-row framebuffer gate red")
    return {"status": "PASS: DELIVERED 80X25 FRAMEBUFFER COMPOSED",
        "cells_checked": len(current),
        "banner_row": 7, "sequential_driver_start_row": 9,
        "candidate": {"prompt_row": 24, "prompt_column": 0,
            "editor_origin_column": 8,
            "active_row": row(current, 24).rstrip()},
        "device_red_mutation": {"prompt_row": 9, "prompt_column": 25,
            "prompt_end_column": 33, "editor_row": 24,
            "editor_origin_column": 8,
            "row9": row(predecessor, 9).rstrip(),
            "row24": row(predecessor, 24).rstrip(),
            "rejected": True},
        "explicit_read_line_framebuffer_identical": True,
        "surface_sha256": hashlib.sha256(current).hexdigest(),
        "ordinary_surface_sha256": hashlib.sha256(ordinary_current).hexdigest(),
        "rule": ("one surface has one positioning model; a control byte is "
                 "positioning only when the delivered driver interprets it")}


def emit_plane() -> dict[str, Any]:
    value = CLIENT.emit_client_plane()
    manifest = load(MANIFEST)
    entries = {row["name"]: row for row in manifest["entries"]}
    observed = {name: int(entries[name]["length"]) for name in (
        "%rl-screen-tail", "read-line", "%native-prompt", "%native-read-line")}
    require(value["geometry"]["bytes"] == 47468
            and observed == {"%rl-screen-tail": 223, "read-line": 235,
                "%native-prompt": 21, "%native-read-line": 16}
            and len(manifest["entries"]) == 398,
            "r7 byte-neutral Bank-2 geometry drift")
    old_manifest = load(R6_PLANE / "stdlib-p0.manifest.json")
    old_entries = {row["name"]: row for row in old_manifest["entries"]}
    value["display_repair"] = {
        "objects": observed,
        "predecessor_objects": {name: int(old_entries[name]["length"])
            for name in observed},
        "aggregate_delta_bytes": 0,
        "literal_inventory": {"before": {"index": 971, "node": 971,
                "patch": 879}, "after": {"index": 970, "node": 970,
                "patch": 878}},
        "source_gate": validate_editor_source(CLIENT_SOURCE.read_text(
            encoding="utf-8")),
        "mutations_rejected": editor_mutations(
            CLIENT_SOURCE.read_text(encoding="utf-8"))}
    PLANE_RECEIPT.write_bytes(canonical(value))
    return value


def product_identity_preflight(plane: dict[str, Any]) -> dict[str, Any]:
    old = load(R6_PLANE / "product/substitution-artifacts.json")
    new = load(PLANE_ROOT / "product/substitution-artifacts.json")
    old_header = (R6_PLANE / "stdlib-p0.h").read_text(encoding="utf-8")
    new_header = HEADER.read_text(encoding="utf-8")
    counts = lambda text: {name: int(re.search(  # noqa: E731
        rf"#define LISP65_BYTECODE_STDLIB_LITERAL_{name.upper()}_COUNT (\d+)u",
        text).group(1)) for name in ("index", "node", "patch")}
    require(old["product_build_id_u32"] != new["product_build_id_u32"]
            and old["resolutions"] == new["resolutions"] + 1
            and counts(old_header) == {"index": 971, "node": 971, "patch": 879}
            and counts(new_header) == {"index": 970, "node": 970, "patch": 878}
            and plane["geometry"]["bytes"] == 47468,
            "r7 generated identity/link necessity proof drift")
    consumers = CARD.stdlib_consumer_preflight()
    return {"status": "PASS: NATIVE PRODUCT REBUILD IS REQUIRED",
        "plane_extent_byte_identical": True,
        "bank2_before": bind(R6_PLANE / "v6-semantics/bank2-static-code.bin"),
        "bank2_after": bind(CODE),
        "stdlib_header_before": bind(R6_PLANE / "stdlib-p0.h"),
        "stdlib_header_after": bind(HEADER),
        "literal_counts_before": counts(old_header),
        "literal_counts_after": counts(new_header),
        "product_build_id_before": old["product_build_id_hex"],
        "product_build_id_after": new["product_build_id_hex"],
        "real_force_include_consumers": consumers,
        "conclusion": ("artifact-only replacement is forbidden: both native "
                       "consumers must compile the successor literal counts "
                       "and derived product identity")}


def preflight() -> None:
    configure()
    require(not PREFLIGHT.exists() and not PREFLIGHT_RECEIPT.exists()
            and not BUILD.exists() and not RECEIPT.exists()
            and not FINAL_RED.exists(), "r7 preflight is one-shot")
    plane = emit_plane()
    frame = full_framebuffer_gate()
    R6.setup_child()
    order = R6.configuration_order_gate()
    linker = PRODUCT.linker_script(ownership_opt_in=True)
    pins = R6.known_pin_inventory(linker)
    identity = product_identity_preflight(plane)
    require(pins["status"] ==
                "PASS: ALL KNOWN R4/R5 PIN CHECKERS ENUMERATED",
            "r7 known-pin inventory red")
    value = {"format": FORMAT + "-preflight-v1", "recorded_on": "2026-08-29",
        "status": "PASS: R7 DISPLAY REPAIR ARMED 0/1",
        "authority": authority(), "plane": bind(PLANE_RECEIPT),
        "framebuffer": frame, "native_product_rebuild": identity,
        "configuration_order": order, "known_pin_inventory": pins,
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "next": "commit this zero-link preflight, then spend r7 1/1"}
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("v1.9 B-light display: R7 PREFLIGHT PASS cells=2000 link=0/1")


def check_preflight() -> None:
    configure()
    value = load(PREFLIGHT_RECEIPT)
    require(value["status"] == "PASS: R7 DISPLAY REPAIR ARMED 0/1"
            and value["authority"] == authority()
            and value["framebuffer"] == full_framebuffer_gate()
            and value["framebuffer"]["device_red_mutation"]["rejected"] is True
            and value["native_product_rebuild"]["plane_extent_byte_identical"]
            and value["attempt_accounting"]["WPLTO_runs"] == 0,
            "r7 preflight receipt drift")
    print("v1.9 B-light display: R7 PREFLIGHT CHECK PASS link=0/1")


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
    old_inputs, new_inputs = profile_sources(R6_PROFILE), profile_sources(PROFILE)
    require(set(old_inputs) == set(new_inputs),
            "r6/r7 compiler input population drift")
    changed = sorted(name for name in old_inputs if old_inputs[name] != new_inputs[name])
    allowed = {"c2-stream-phase-02a.c", "vm_embed.c", "repl.c"}
    require(set(changed) <= allowed and "c2-stream-phase-02a.c" in changed,
            f"r6/r7 compiler inputs escaped display/header roots: {changed}")
    old = ElfTruth.read(R6_ELF, llvm_readobj=CARD.READOBJ,
                        include_section_data=True)
    new = ElfTruth.read(ELF, llvm_readobj=CARD.READOBJ,
                        include_section_data=True)
    old_symbols = Counter(CARD.symbol_key(row) for row in old.symbols)
    new_symbols = Counter(CARD.symbol_key(row) for row in new.symbols)
    old_relocs = Counter(CARD.relocation_key(row) for row in old.relocations)
    new_relocs = Counter(CARD.relocation_key(row) for row in new.relocations)
    old_sections = Counter((row.name, row.address, row.bytes,
                            tuple(row.flags)) for row in old.sections)
    new_sections = Counter((row.name, row.address, row.bytes,
                            tuple(row.flags)) for row in new.sections)
    prg_differences = sum(a != b for a, b in zip(
        R6_PRG.read_bytes(), PRG.read_bytes())) + abs(
            R6_PRG.stat().st_size - PRG.stat().st_size)
    elf_left, elf_right = R6_ELF.read_bytes(), ELF.read_bytes()
    elf_differences = sum(a != b for a, b in zip(elf_left, elf_right)) + abs(
        len(elf_left) - len(elf_right))
    inherited = CARD.inherited_product_attribution()
    require(all(value == 0 for name, value in inherited["counts"].items()
                if name.startswith("unexplained_")),
            "complete product attribution retained unexplained members")
    return {"format": FORMAT + "-difference-v1", "recorded_on": "2026-08-29",
        "status": "PASS: EVERY R6/R7 PRODUCT MEMBER HAS A NAMED FAMILY",
        "authored_root": {"source": bind(CLIENT_SOURCE),
            "predecessor": bind(R6_SOURCE),
            "changed_forms": ["%rl-screen-tail", "%native-prompt"],
            "aggregate_Bank2_delta_bytes": 0},
        "compiler_input_closure": {"population": len(old_inputs),
            "changed": changed, "unchanged": len(old_inputs) - len(changed),
            "families": ["editor static-plane image and derived phase CRC",
                         "candidate stdlib literal-count force-include",
                         "derived product build-ID projection"]},
        "product_members": {"PRG_changed_bytes": prg_differences,
            "ELF_changed_bytes": elf_differences,
            "symbols": counter_diff(old_symbols, new_symbols),
            "relocations": counter_diff(old_relocs, new_relocs),
            "sections": counter_diff(old_sections, new_sections),
            "family": "display-source -> header/build-ID/CRC deterministic closure"},
        "complete_product_closure": inherited,
        "era_conversion": era_conversion_gate(),
        "counts": inherited["counts"],
        "unexplained_members": 0,
        "causal_statement": ("the sole authored source transform changes the "
            "stdlib image and its literal counts; both real force-include "
            "consumers and the phase CRC/build-ID projection account for every "
            "native successor member")}


def native_prompt_final_elf() -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=CARD.READOBJ,
                          include_section_data=True)
    manifest = load(MANIFEST)
    entries = {row["name"]: row for row in manifest["entries"]}
    names = [row["name"] for row in manifest["entries"]]
    ordinal = names.index("%native-read-line")
    define = ("#define LISP65_BYTECODE_STDLIB_NATIVE_READ_LINE_ENTRY "
              f"{ordinal}u")
    rows = DEVICE.instruction_records(ELF, "repl")
    targets = {name: truth.symbol(name).value for name in (
        "vm_run_dir", "lisp_input_event")}
    vm_calls = [record for record in rows if record["mnemonic"] == "jsr"
                and DEVICE.absolute_target(record) == targets["vm_run_dir"]]
    event_calls = [record for record in rows if record["mnemonic"] == "jsr"
                   and DEVICE.absolute_target(record) == targets["lisp_input_event"]]
    text = truth.section(".text")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    frame = full_framebuffer_gate()
    sizes = {name: entries[name]["length"] for name in (
        "%rl-screen-tail", "read-line", "%native-prompt", "%native-read-line")}
    require(ordinal == 395 and HEADER.read_text(encoding="utf-8").count(define) == 1
            and len(vm_calls) == 2 and event_calls == []
            and sizes == {"%rl-screen-tail": 223, "read-line": 235,
                "%native-prompt": 21, "%native-read-line": 16}
            and entries["%native-prompt"]["literals"] == [
                {"symbol": "%rl-screen-tail"}]
            and entries["%rl-screen-tail"]["literals"] == [
                {"string": "lisp65> "}, {"symbol": "%rl-render"},
                {"symbol": "%rl-screen-tail"}]
            and facade.address - (text.address + text.bytes) >= 32,
            "r7 final ELF does not execute the repaired prompt route")
    static_consumption = CLIENT.candidate_consumption_receipts()
    stdlib_consumption = CARD.candidate_stdlib_consumption()
    sweep = CARD.force_include_consumption_sweep(
        static_consumption, stdlib_consumption)
    return {"status": "PASS: FINAL ELF USES ONE PROMPT POSITIONING MODEL",
        "manifest": bind(MANIFEST), "header": bind(HEADER),
        "native_entry": {"name": "%native-read-line", "ordinal": ordinal,
            "length": sizes["%native-read-line"]},
        "objects": sizes,
        "resolved_calls": {"vm_run_dir": [f"0x{int(row['address']):04x}"
            for row in vm_calls], "lisp_input_event": []},
        "prompt_owner": {"object": "%rl-screen-tail",
            "writer": "screen-put-char", "row": "read-line screen-row",
            "positioning_control_bytes": []},
        "ordinary_text": {"end_exclusive": text.address + text.bytes,
            "facade_start": facade.address,
            "free_bytes": facade.address - (text.address + text.bytes),
            "permanent_floor_bytes": 32},
        "candidate_extent": CODE.stat().st_size,
        "compiler_consumers": static_consumption,
        "stdlib_header_consumers": stdlib_consumption,
        "force_include_bound_equals_consumed": sweep,
        "composed_framebuffer_effect": frame,
        "mutations": {"restore-device-red-HOME-DOWN-model": "rejected",
            "split-prompt-positioning-owner": "rejected",
            "alter-explicit-read-line-surface": "rejected"}}


def final_gate() -> dict[str, Any]:
    value = R6.final_gate()
    block = value["v1_9_Block_B_light"]
    block["status"] = "PASS: NATIVE PROMPT AND EDITOR COMPOSED ON ONE ROW"
    block["native_prompt_final_ELF"] = native_prompt_final_elf()
    block["device_first_red_closed"] = bind(FIRST_RED_ATTRIBUTION)
    block["session_continuation"] = "all A+B rows remain unaccepted"
    return value


def frozen_artifacts() -> dict[str, Any]:
    return BASE.artifacts()


def run_child(action: str) -> dict[str, Any]:
    result = subprocess.run([sys.executable, str(DRIVER), action], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0, f"r7 child {action} red:\n{result.stdout}")
    return {"action": action, "stdout_tail": " ".join(result.stdout.split()[-30:])}


def write_report(value: dict[str, Any]) -> None:
    frame = value["final_product"]["v1_9_Block_B_light"][
        "native_prompt_final_ELF"]["composed_framebuffer_effect"]
    pair = value["artifacts_after"]
    REPORT.write_text(f"""# v1.9 B-light display repair — r7

Status: **{value['status']}**

The stopped device world placed `lisp65> ` on row 9, column 25 and the active
editor cursor on row 24, column 8.  The exact writer was the `$13`/twenty-four
`$11` sequence in `%rl-screen-tail`; the delivered screen driver renders those
bytes as blanks instead of interpreting KERNAL HOME/DOWN mnemonics.

r7 removes that second positioning model.  `%rl-screen-tail` writes the prompt
through the same direct-cell surface and row owned by the editor.  Its object
grows 212→223 bytes while `%native-prompt` shrinks 32→21, leaving the final
Bank-2 plane byte-neutral at 47,468 bytes.  The target-faithful full-frame gate
checks {frame['cells_checked']} cells, observes `{frame['candidate']['active_row']}`
on row 24 and rejects the exact captured row-9/row-24 split.  Explicit
`(read-line)` is byte-identical across the complete surface.

The link was nevertheless necessary: the stdlib literal counts change
971/971/879→970/970/878, changing the derived product identity consumed by both
native Force-Include clients.  Every r6→r7 difference is attributed to that
source/header/build-ID/CRC closure before read-only Scope and Acceptance.

The first attribution attempt stopped on an era-crossing checker, not on the
product: its inherited r2/r3 header closure compared sealing-era receipts with
the live r7 header.  The zero-build successor verifies those worlds separately
and rejects both directions of mixing.  Its pre-link inventory now covers the
seven literal-pin checks plus all six inherited candidate-dependent closures.

- ELF: `{pair['ELF']['sha256']}`
- PRG: `{pair['PRG']['sha256']}`

Exactly one WPLTO and one product link ran in the original r7 attempt; the
successful resume ran zero of either and proved the complete WPLTO tree
byte-identical before/after.  No medium was built and no device was contacted.
The successor hardware session must repeat every Block-A and Block-B row; the
stopped predecessor contact accepted none.
""", encoding="utf-8")


def build() -> None:
    configure()
    pre = load(PREFLIGHT_RECEIPT)
    require(pre["status"] == "PASS: R7 DISPLAY REPAIR ARMED 0/1"
            and not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not DIFFERENCE.exists(),
            "r7 preflight/build lifecycle drift")
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, check=True).stdout
    require(clean == "", "r7 WPLTO requires committed clean sources")
    INVOCATION.write_bytes(canonical({"status": "INVOKED",
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "budget": {"WPLTO_runs": 1, "product_links": 1}}))
    processes = [run_child("_produce")]
    before = frozen_artifacts()
    diff = attribution()
    require(diff["unexplained_members"] == 0,
            "r7 attribution retained unexplained members")
    DIFFERENCE.write_bytes(canonical(diff))
    gate = final_gate()
    processes.extend((run_child("_scope"), run_child("_accept")))
    after = frozen_artifacts()
    scope, acceptance = load(BASE.SCOPE_RESULT), load(BASE.ACCEPTANCE_RESULT)
    require(before == after and scope["status"] == acceptance["status"] == "PASS",
            "r7 read-only qualification tail red")
    value = {"format": FORMAT, "recorded_on": "2026-08-29", "status": STATUS,
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "invocation": bind(INVOCATION), "attribution": bind(DIFFERENCE),
        "final_product": gate, "producer": bind(BASE.PRODUCER_RESULT),
        "scope": bind(BASE.SCOPE_RESULT), "acceptance": bind(BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": processes,
        "attempt_accounting": {"WPLTO_runs": 1, "product_links": 1,
            "scope_runs": 1, "acceptance_runs": 1,
            "media_builds": 0, "device_contacts": 0},
        "media_authorized": False,
        "next": "independent review; then successor A+B media and full session"}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    check()
    print("v1.9 B-light display: R7 CARD PASS WPLTO=1/1 link=1/1")


def tree_fingerprint(path: Path) -> dict[str, Any]:
    rows = []
    for member in sorted(path.rglob("*")):
        if member.is_file() and not member.is_symlink():
            raw = member.read_bytes()
            rows.append({"path": member.relative_to(ROOT).as_posix(),
                         "bytes": len(raw),
                         "sha256": hashlib.sha256(raw).hexdigest()})
    return {"root": path.relative_to(ROOT).as_posix(), "files": len(rows),
            "sha256": hashlib.sha256(canonical(rows)).hexdigest()}


def resume() -> None:
    configure()
    require(not DIFFERENCE.exists() and not RECEIPT.exists()
            and not ERA_CONVERSION.exists()
            and not BASE.SCOPE_RESULT.exists()
            and not BASE.ACCEPTANCE_RESULT.exists(),
            "r7 resume is one-shot")
    before = frozen_artifacts()
    red = load(FINAL_RED)
    require(red["artifacts"]["ELF"] == before["ELF"]
            and red["artifacts"]["PRG"] == before["PRG"],
            "r7 resume pair is not the frozen first-red pair")
    wplto_before = tree_fingerprint(BUILD / "wplto")

    conversion = era_conversion_gate()
    ERA_CONVERSION.write_bytes(canonical(conversion))
    diff = attribution()
    require(diff["unexplained_members"] == 0,
            "r7 attribution retained unexplained members")
    DIFFERENCE.write_bytes(canonical(diff))
    gate = final_gate()
    processes = [run_child("_scope"), run_child("_accept")]

    after = frozen_artifacts()
    wplto_after = tree_fingerprint(BUILD / "wplto")
    scope, acceptance = load(BASE.SCOPE_RESULT), load(BASE.ACCEPTANCE_RESULT)
    require(before == after and wplto_before == wplto_after
            and scope["status"] == acceptance["status"] == "PASS",
            "r7 read-only qualification tail red")
    value = {"format": FORMAT + "-resume-v1",
        "recorded_on": "2026-08-29", "status": STATUS,
        "authority": resume_authority(),
        "preflight": bind(PREFLIGHT_RECEIPT),
        "first_red": bind(FINAL_RED),
        "first_red_attribution": bind(FINAL_RED_ATTRIBUTION),
        "era_conversion": bind(ERA_CONVERSION),
        "invocation": bind(INVOCATION), "attribution": bind(DIFFERENCE),
        "final_product": gate, "producer": bind(BASE.PRODUCER_RESULT),
        "scope": bind(BASE.SCOPE_RESULT),
        "acceptance": bind(BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "wplto_tree_before": wplto_before, "wplto_tree_after": wplto_after,
        "processes": processes,
        "attempt_accounting": {"WPLTO_runs_total": 1,
            "product_links_total": 1, "resume_WPLTO_runs": 0,
            "resume_product_links": 0, "scope_runs": 1,
            "acceptance_runs": 1, "media_builds": 0,
            "device_contacts": 0},
        "media_authorized": False,
        "next": "independent review; then successor A+B media and full session"}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    check()
    print("v1.9 B-light display: R7 RESUME PASS WPLTO=0 link=0")


def check() -> None:
    configure()
    value = load(RECEIPT)
    diff = load(DIFFERENCE)
    frame = value["final_product"]["v1_9_Block_B_light"][
        "native_prompt_final_ELF"]["composed_framebuffer_effect"]
    require(value["status"] == STATUS
            and value["authority"] == resume_authority()
            and value["artifacts_before"] == value["artifacts_after"] ==
                frozen_artifacts()
            and value["wplto_tree_before"] == value["wplto_tree_after"] ==
                tree_fingerprint(BUILD / "wplto")
            and value["attempt_accounting"]["resume_WPLTO_runs"] == 0
            and value["attempt_accounting"]["resume_product_links"] == 0
            and load(ERA_CONVERSION) == era_conversion_gate()
            and canonical(diff) == canonical(attribution())
            and diff["unexplained_members"] == 0
            and frame == full_framebuffer_gate()
            and frame["device_red_mutation"]["rejected"] is True,
            "r7 receipt drift")
    print("v1.9 B-light display: R7 CHECK PASS one-row=YES")


def record_red(error: Exception) -> None:
    artifacts = {name: bind(path) for name, path in (
        ("ELF", ELF), ("PRG", PRG),
        ("map", BUILD / "wplto/lisp65-c2-substitution-linked.prg.map"),
        ("lto", BUILD / "wplto/lisp65-c2-substitution-linked.prg.lto.o"))
        if path.is_file()}
    FINAL_RED.write_bytes(canonical({"format": FORMAT + "-final-red-v1",
        "recorded_on": "2026-08-29",
        "status": "FINAL RED: B-LIGHT DESCOPES; BLOCK A CARRIES V1.9",
        "error": str(error), "artifacts": artifacts,
        "attempt_accounting": {"WPLTO_runs": int(any(BUILD.rglob("*.lto.o"))),
            "product_links": int(ELF.is_file()), "media_builds": 0,
            "device_contacts": 0},
        "retry_authorized": False,
        "fallback": "Block A only; native prompt cursor Known Issue remains"}))


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
        "build", "resume", "check", "_profile_probe", "_release_probe", "_produce",
        "_scope", "_accept"))
    action = parser.parse_args().action
    if action == "preflight":
        preflight()
    elif action == "check-preflight":
        check_preflight()
    elif action == "build":
        try:
            build()
        except Exception as error:
            record_red(error)
            raise
    elif action == "resume":
        resume()
    elif action == "check":
        check()
    else:
        child(action)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
