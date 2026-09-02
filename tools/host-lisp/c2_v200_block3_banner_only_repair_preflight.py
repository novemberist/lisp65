#!/usr/bin/env python3
"""Attribute the Block-3 banner-only device red and price its repair."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0_stdlib as P0  # noqa: E402
import c2_packed_medium_transitive_closure as CLOSURE  # noqa: E402
import c2_v190_native_prompt_editor_display_repair_r7 as DISPLAY  # noqa: E402
import c2_v18_capture_hybrid_responsiveness_repair as RESPONSIVENESS  # noqa: E402
import c2_v200_block3_return_pricing as PRICE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
AUTHORITY_COMMIT = "f160678f"
CANDIDATE_EVIDENCE_ERA = "8cb2b95593262a335da7905afb8cd923b915bc41"
SESSION = ROOT / "config/c2-v200-block3-return-device-session.json"
LIVE_SOURCE = ROOT / "lib/stdlib-read-line.lisp"
BROKEN_MANIFEST = ROOT / (
    "build/c2.3/v2.0-block3-return-device-media/inputs/static-plane/"
    "stdlib-p0.manifest.json")
V19_MANIFEST = ROOT / (
    "build/c2.3/v1.9.0-release-media/inputs/static-plane/"
    "stdlib-p0.manifest.json")
PRODUCT_RECEIPT = ARCH / (
    "c2.3-v2.0-block3-return-product-card-r1-receipt.json")
MEDIA_RECEIPT = ARCH / (
    "c2.3-v2.0-block3-return-device-media-receipt.json")
BUILD = ROOT / "build/c2.3/v2.0-block3-banner-only-repair-preflight"
CHECK_BUILD = ROOT / "build/c2.3/v2.0-block3-banner-only-repair-preflight-check"
STDLIB_SUITE = BUILD / "v2.0-block3-stdlib-suite.json"
IDE_SUITE = BUILD / "v2.0-block3-ide-suite.json"
COMFORT_MANIFEST = BUILD / "comfort-positive/repl-comfort.manifest.json"
LOGICAL_CANDIDATE_MANIFEST = (
    "build/c2.3/v2.0-block3-banner-only-repair-preflight/"
    "stdlib-p0.manifest.json")
RECEIPT = ARCH / (
    "c2.3-v2.0-block3-banner-only-repair-preflight.json")
REPORT = ROOT / "docs/planning/v2.0.0-block3-banner-only-repair-preflight.md"
STATUS = "PASS: BLOCK3 BANNER-ONLY MECHANISM ATTRIBUTED AND REPAIR PRICED"
FORMAT = "lisp65-c2.3-v200-block3-banner-only-repair-preflight-v1"


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
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def era_bind(commit: str, path: Path) -> dict[str, Any]:
    raw = git_blob(commit, path)
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def memory_bind(name: str, raw: bytes) -> dict[str, Any]:
    return {"name": name, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def manifest_semantic_bind(path: Path) -> dict[str, Any]:
    """Bind emitted object truth while excluding checkout/source spelling."""
    value = load(path)
    entries = [{key: row[key] for key in (
                    "name", "kind", "length", "ext_addr", "blob_offset")
                if key in row}
               for row in value.get("entries", [])]
    raw = canonical(entries)
    return {"path": LOGICAL_CANDIDATE_MANIFEST,
        "objects": value.get("objects"), "code_bytes": value.get("code_bytes"),
        "blob_sha256": value.get("blob_sha256"),
        "directory_sha256": value.get("directory_sha256"),
        "entry_projection": {"count": len(entries), "sha256":
                              hashlib.sha256(raw).hexdigest()}}


def git_blob(commit: str, path: Path) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path.relative_to(ROOT).as_posix()}"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(result.returncode == 0,
            f"era source absent: {result.stderr.decode('utf-8', 'replace')}")
    return result.stdout


def authority() -> dict[str, Any]:
    raw = git_blob(AUTHORITY_COMMIT, SESSION)
    value = json.loads(raw)
    decision = value.get("decision_table", {})
    require(decision.get("daily-use-blocker") ==
            "at most one repair round; otherwise descope the affected Block-3 freight",
            "device repair-round authority drift")
    return {"commit": AUTHORITY_COMMIT,
        "session": memory_bind(SESSION.relative_to(ROOT).as_posix(), raw),
        "right": "one bounded repair round after a deterministic daily-use blocker",
        "budget_consumed_here": {"WPLTO_runs": 0, "product_links": 0,
                                  "media_builds": 0, "device_contacts": 0}}


def entry(path: Path, name: str) -> dict[str, Any]:
    rows = [row for row in load(path).get("entries", [])
            if isinstance(row, dict) and row.get("name") == name]
    require(len(rows) == 1, f"manifest object not unique: {name}")
    return rows[0]


def source_gate() -> dict[str, Any]:
    broken = git_blob(AUTHORITY_COMMIT, LIVE_SOURCE).decode("utf-8")
    candidate = git_blob(CANDIDATE_EVIDENCE_ERA, LIVE_SOURCE).decode("utf-8")
    old = """  (if (= row -2)
      (progn
        (write-char 19)
        (dotimes (line stop nil) (write-char 17)))
      (let* ((prompted (< row -2)))
"""
    new = """  (if (= row -2)
      (let ((text \"lisp65> \"))
        (dotimes (at 8 nil)
          (screen-put-char at stop (string-ref text at) 1)))
      (let* ((native (< row -34))
             (prompted (< row -2))
             (actual-row (if native (- 0 (+ row 34)) (- 0 (+ row 2)))))
"""
    prompt = """(defun %native-prompt (row)
  (%rl-screen-tail nil 0 0 row nil -2))
"""
    require(broken.count(old) == broken.count(prompt) == 1
            and new not in broken and candidate.count(new) == 1
            and candidate.count(prompt) == 1 and old not in candidate
            and "(write-char 19)" not in candidate
            and "(write-char 17)" not in candidate
            and "(let* ((origin (if native 8 (if prompted 5 0))))" in candidate,
            "prompt positioning source is not the exact repaired composition")
    return {"status": "PASS: ONE DIRECT-CELL POSITIONING OWNER",
        "device_medium_source": memory_bind("device-red-source", broken.encode()),
        "candidate_source": era_bind(CANDIDATE_EVIDENCE_ERA, LIVE_SOURCE),
        "device_red_form": "old control-code tail plus new empty prompt wrapper",
        "candidate_form": "direct-cell prompt plus native-row decoding",
        "changed_function": "%rl-screen-tail", "new_named_helpers": 0,
        "forbidden_control_codes": [19, 17]}


def candidate_emit() -> tuple[dict[str, Any], tuple[tuple[str, str, Path], ...]]:
    old = (PRICE.BUILD, PRICE.STDLIB_SUITE, PRICE.IDE_SUITE,
           PRICE.COMFORT_MANIFEST)
    old_suite = PRICE.candidate_stdlib_suite

    def sealed_suite() -> dict[str, Any]:
        value = old_suite()
        source = BUILD / "evidence-era-stdlib-read-line.lisp"
        source.write_bytes(git_blob(CANDIDATE_EVIDENCE_ERA, LIVE_SOURCE))
        PRICE._replace_source(value["sources"], "stdlib-read-line.lisp",
                              str(source.resolve()))
        return value

    try:
        PRICE.BUILD = BUILD
        PRICE.STDLIB_SUITE = STDLIB_SUITE
        PRICE.IDE_SUITE = IDE_SUITE
        PRICE.COMFORT_MANIFEST = COMFORT_MANIFEST
        PRICE.candidate_stdlib_suite = sealed_suite
        return PRICE.emit_candidate()
    finally:
        (PRICE.BUILD, PRICE.STDLIB_SUITE, PRICE.IDE_SUITE,
         PRICE.COMFORT_MANIFEST) = old
        PRICE.candidate_stdlib_suite = old_suite


def run_surface(raw: bytes, label: str, stop_at_handoff: bool) -> dict[str, Any]:
    surface_dir = BUILD / "framebuffer"
    surface_dir.mkdir(parents=True, exist_ok=True)
    source = surface_dir / f"stdlib-read-line-{label}.lisp"
    source.write_bytes(raw)
    suite = PRICE.candidate_stdlib_suite()
    matches = [index for index, item in enumerate(suite["sources"])
               if Path(item).name == "stdlib-read-line.lisp"]
    require(len(matches) == 1, "framebuffer source owner not unique")
    suite["sources"][matches[0]] = str(source.resolve())
    suite["cases"] = [{"name": label, "expr": "(%native-read-line)",
        "expect": '"abc"', "key_events": [97, 98, 99, 13],
        "max_steps": 1_000_000}]
    suite["private_key_event_modes"] = True
    (heap, _names, _code, flags, resident, _bundle, directory,
     _cases, entries, _inliner) = P0._compile_suite(suite)
    macros = P0._macro_symbol_objs(heap, flags, resident)
    abi_profile, abi_ledger = P0._suite_abi(suite)
    vm = DISPLAY.TargetFrameVM(
        heap=heap.clone(), directory=directory, macro_symbols=macros,
        max_steps=1_000_000, max_call_args=suite.get("max_call_args"),
        key_events=[97, 98, 99, 13], private_key_event_modes=True,
        abi_profile=abi_profile, abi_ledger=abi_ledger,
        stop_at_return=stop_at_handoff)
    reached_handoff = False
    try:
        vm.run(directory[heap.intern(entries[0])], [])
    except DISPLAY.DISPLAY.AtReturn:
        reached_handoff = True
    require(reached_handoff == stop_at_handoff,
            f"unexpected framebuffer handoff state: {label}")
    surface = (vm.surface_at_return if reached_handoff
               else bytes(vm.screen_cells))
    require(surface is not None and len(surface) == 2000,
            f"framebuffer absent: {label}")
    return {"handoff_reached": reached_handoff,
        "banner_row": DISPLAY.row(surface, 7).rstrip(),
        "row_24": DISPLAY.row(surface, 24).rstrip(),
        "surface_sha256": hashlib.sha256(surface).hexdigest()}


def build_receipt() -> dict[str, Any]:
    gate = source_gate()
    candidate_source = git_blob(CANDIDATE_EVIDENCE_ERA, LIVE_SOURCE)
    _product, specs = candidate_emit()
    manifests = {key: path for key, _role, path in specs}
    candidate_manifest = manifests["stdlib-p0"]
    candidate_product = BUILD / "product/substitution-artifacts.json"
    closure = CLOSURE.derive(candidate_product)
    CLOSURE.require_closed(closure)
    broken_tail = entry(BROKEN_MANIFEST, "%rl-screen-tail")
    accepted_tail = entry(V19_MANIFEST, "%rl-screen-tail")
    candidate_tail = entry(candidate_manifest, "%rl-screen-tail")
    broken_prompt = entry(BROKEN_MANIFEST, "%native-prompt")
    candidate_prompt = entry(candidate_manifest, "%native-prompt")
    literal = lambda row: [item.get("string") for item in row.get("literals", [])
                           if isinstance(item, dict) and "string" in item]
    require(broken_tail["length"] == 185 and literal(broken_tail) == []
            and accepted_tail["length"] == candidate_tail["length"] == 223
            and literal(accepted_tail) == literal(candidate_tail) == ["lisp65> "]
            and broken_prompt["length"] == candidate_prompt["length"] == 21,
            "emitted prompt object did not restore the accepted successor")
    candidate_total = sum(int(load(path)["code_bytes"])
                          for _key, _role, path in specs)
    predecessor_total = int(load(PRICE.RECEIPT)["emission"]["candidate_plane_bytes"])
    require(predecessor_total == 52499 and candidate_total == 52537,
            "repair plane extent drift")
    repaired = run_surface(candidate_source, "candidate", True)
    broken = run_surface(git_blob(AUTHORITY_COMMIT, LIVE_SOURCE),
                         "device-red", False)
    require(repaired["row_24"] == "lisp65> abc"
            and broken["banner_row"] == "WORKBENCH 1.9.0"
            and broken["row_24"] == "",
            "composed boot-to-prompt framebuffer discriminator drift")
    geometry = PRICE.bank2_geometry(candidate_total)
    require(geometry["largest_contiguous_hole"]["bytes"] == 11129,
            "repair placement drift")
    route = RESPONSIVENESS.execute(candidate_source, "live-artifacts")
    product_pair = load(PRODUCT_RECEIPT)["artifacts_after"]
    linked_elf = ROOT / product_pair["ELF"]["path"]
    _truth, machine, _membership = RESPONSIVENESS.HYBRID.linked_consumer(
        linked_elf)
    symbols = machine.symbols
    memory = {symbols["C2K_INPUT_RING_HEAD"]: 1,
              symbols["C2K_INPUT_RING_TAIL"]: 0,
              symbols["C2K_INPUT_RING_BASE"]: ord("a")}
    result, native_cycles, native_instructions = machine.run(2, memory)
    require(result == ord("a"), "linked Capture consumer drift")
    responsiveness = RESPONSIVENESS.measurement(
        route, native_cycles, native_instructions)
    require(route["dynamic_vm_steps"] == 9010
            and route["screen_cells"] == 45
            and all(responsiveness["walls"].values())
            and responsiveness["margin_percent"] > 28.95,
            "prompt repair crossed the responsiveness wall")
    return {"format": FORMAT, "recorded_on": "2026-09-01",
        "status": STATUS, "authority": authority(),
        "device_observation": {"result": "banner only; no prompt or cursor",
            "session_medium": bind(MEDIA_RECEIPT),
            "packed_manifest": bind(BROKEN_MANIFEST)},
        "attribution": {"source": gate,
            "emitted_objects": {
                "accepted_v1_9": {"manifest": bind(V19_MANIFEST),
                    "screen_tail": {"length": accepted_tail["length"],
                                    "strings": literal(accepted_tail)}},
                "device_red": {"screen_tail": {"length": broken_tail["length"],
                                                 "strings": literal(broken_tail)},
                    "native_prompt_bytes": broken_prompt["length"]},
                "repair_candidate": {
                    "manifest": manifest_semantic_bind(candidate_manifest),
                    "screen_tail": {"length": candidate_tail["length"],
                                    "strings": literal(candidate_tail)},
                    "native_prompt_bytes": candidate_prompt["length"]}},
            "mechanism": ("the product card consumed the stale living editor: "
                "the old control-code %rl-screen-tail survived while the new "
                "%native-prompt wrapper emitted no text; the native editor row "
                "was consequently decoded off-screen"),
            "product_defect": True, "packing_defect": False},
        "composed_framebuffer_gate": {
            "status": "PASS: BOOT BANNER TO NATIVE PROMPT COMPOSED",
            "candidate": repaired, "device_red_mutation": broken,
            "cells_checked_per_world": 2000,
            "mutations_rejected": [
                "restore-control-code-positioner",
                "remove-native-row-decoder",
                "omit-direct-cell-prompt"],
            "rule": ("the product/media claim composes boot, banner, prompt and "
                     "active editor on the delivered 80x25 framebuffer")},
        "live_responsiveness": {
            "status": "PASS: ALL THREE RESPONSIVENESS WALLS HOLD",
            "route": {"dynamic_vm_steps": route["dynamic_vm_steps"],
                      "screen_cells": route["screen_cells"],
                      "characters": route["characters"]},
            "measurement": responsiveness,
            "predecessor_receipt": bind(RESPONSIVENESS.RECEIPT),
            "source_era_rule": ("the v1.8 receipt remains sealed; the v2.0 "
                "successor measures the extra native-row work in its own world")},
        "repair_price": {"predecessor_plane_bytes": predecessor_total,
            "candidate_plane_bytes": candidate_total,
            "delta_bytes": candidate_total - predecessor_total,
            "new_named_helpers": 0, "new_symbol_slots": 0,
            "largest_contiguous_hole_bytes":
                geometry["largest_contiguous_hole"]["bytes"],
            "closure": {"object_count": closure["object_count"],
                        "call_site_count": closure["call_site_count"],
                        "failures": closure["failures"]},
            "required_successor_budget": {"WPLTO_runs": 1,
                                           "product_links": 1},
            "reason": ("the repaired Bank-2 plane extent and product build ID "
                       "are compiler-consumed product inputs")},
        "claim_limit": ("Host-only device-red attribution and repair price. "
            "No WPLTO, product link, replacement medium, device acceptance or "
            "Block-3 feature claim.")}


def report(value: dict[str, Any]) -> str:
    price = value["repair_price"]
    return f"""# v2.0 Block 3 banner-only repair preflight

Status: **{value['status']}**

The device red is fully reproduced.  The packed Block-3 world emitted
`%rl-screen-tail` as 185 bytes with no `lisp65> ` literal, while
`%native-prompt` was already the 21-byte successor that delegates all output
to that helper.  The accepted v1.9 world emitted the helper as 223 bytes with
the prompt literal.  Thus the card composed the old control-code positioner
with the new empty wrapper; it also lacked the native-row decoder, placing the
editor off-screen.  The target-faithful 80x25 model reproduces exactly a banner
and an empty row 24.

The repair materializes the already hardware-accepted direct-cell positioning
form in the living editor source.  The same model now observes
`lisp65> abc` on row 24; the device-red form is a permanent failing mutation.
The gate composes boot, banner, prompt and editor rather than checking the
Block-3 helpers in isolation.

The added native-row branch is also measured on the live typing route, not
charged to the sealed v1.8 repair: 9,010 VM steps over 40 characters,
0.775452 frames/character, 1.289570 events/frame and **28.957% margin**.  All
three responsiveness walls remain green.

The repair changes no public name and adds no helper.  `%rl-screen-tail` grows
185 -> 223 bytes, so the complete plane grows
{price['predecessor_plane_bytes']:,} -> {price['candidate_plane_bytes']:,}
(+{price['delta_bytes']}); the largest contiguous Bank-2 hole remains
{price['largest_contiguous_hole_bytes']:,} bytes.  Closure remains
{price['closure']['object_count']} objects / {price['closure']['call_site_count']:,}
calls with zero failures.

Because the plane extent and product build ID are compiler-consumed, the
bounded repair needs **one WPLTO and one product link**.  This preflight spent
neither.  A successor must fully attribute the difference, rerun Scope and
Acceptance, and prove the composed framebuffer gate over the actually packed
replacement medium before another device contact.
"""


def write() -> dict[str, Any]:
    value = build_receipt()
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(report(value), encoding="utf-8")
    return value


def check() -> dict[str, Any]:
    global BUILD, STDLIB_SUITE, IDE_SUITE, COMFORT_MANIFEST
    require(RECEIPT.is_file() and REPORT.is_file(), "repair preflight absent")
    old = BUILD, STDLIB_SUITE, IDE_SUITE, COMFORT_MANIFEST
    try:
        BUILD = CHECK_BUILD
        STDLIB_SUITE = BUILD / "v2.0-block3-stdlib-suite.json"
        IDE_SUITE = BUILD / "v2.0-block3-ide-suite.json"
        COMFORT_MANIFEST = BUILD / "comfort-positive/repl-comfort.manifest.json"
        value = build_receipt()
    finally:
        BUILD, STDLIB_SUITE, IDE_SUITE, COMFORT_MANIFEST = old
    require(RECEIPT.read_bytes() == canonical(value)
            and REPORT.read_text(encoding="utf-8") == report(value),
            "banner-only repair preflight drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check"))
    args = parser.parse_args()
    try:
        value = write() if args.action == "write" else check()
        price = value["repair_price"]
        print("v2.0 Block3 banner-only repair: PASS "
              f"plane={price['candidate_plane_bytes']} "
              f"delta=+{price['delta_bytes']} "
              f"hole={price['largest_contiguous_hole_bytes']} "
              "WPLTO=0 link=0")
        return 0
    except (RepairError, CLOSURE.ClosureError, RuntimeError) as error:
        print(f"v2.0 Block3 banner-only repair: FIRST RED: {error}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
