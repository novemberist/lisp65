#!/usr/bin/env python3
"""Bind the v2.0 D1 BUILDING-HEAP red and specify its one capture row."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_f018b_content_safe_reads as SAFE  # noqa: E402
import c2_phase_v_gc_ext_dma_lane as LANE  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
CAPTURE = ROOT / "config/c2-v20-building-heap-capture-row.json"
CURRENT_ELF = ROOT / (
    "build/c2.3/v2.0-crc-carveout-card/final/"
    "lisp65-c2-substitution-linked.prg.elf")
CURRENT_PRG = CURRENT_ELF.with_suffix("")
CURRENT_PROFILE = CURRENT_ELF.parent / "resolved-profile.txt"
CARD_RECEIPT = EVIDENCE / "c2.3-v2.0-crc-carveout-card-receipt.json"
LINK96_ELF = ROOT / (
    "build/c2.3/terminal-return-guard-link96/final/"
    "lisp65-c2-substitution-linked.prg.elf")
LINK96_PROFILE = LINK96_ELF.parent / "resolved-profile.txt"
LINK96_DEVICE = EVIDENCE / "c2.3-link96-terminal-return-guard-device-receipt.json"
MEM = ROOT / "src/mem.c"
MAIN = ROOT / "src/main.c"
EVAL = ROOT / "src/eval.c"
OVERLAY = ROOT / "src/vm_boot_overlay.c"
RUNTIME = ROOT / "src/c2_product_runtime.c"
DECODER = CURRENT_ELF.parent / "generated-product-sources/c2-stream-decoder.c"
BOOT_PROGRESS = ROOT / "src/boot_progress.h"
BUILD = ROOT / "build/c2.3/v2.0-building-heap-attribution"
MODEL_BINARY = BUILD / "current-dma-convergence"
RECEIPT = EVIDENCE / "c2.3-v2.0-building-heap-attribution-receipt.json"
REBIND = EVIDENCE / (
    "c2.3-v2.0-building-heap-attribution-rebind-2026-08-14.json")
LATEST_REBIND = EVIDENCE / (
    "c2.3-v2.0-building-heap-attribution-rebind-2026-08-14-"
    "pinned-constant-sweep.json")
MEM_SOURCE_UNBIND = EVIDENCE / (
    "c2.3-v2.0-building-heap-mem-source-unbind-20260816-receipt.json")
DRIVER = Path(__file__).resolve()
FORMAT = "lisp65-c2.3-v20-building-heap-attribution-v1"
STATUS = "HOST-GREEN-NO-MECHANISM; ONE-STOPPED-STATE-ROW-SPECIFIED"
RECORDED_ON = "2026-08-12"
LINK96_COMMIT = "1ede62b3"
HISTORICAL_RECEIPT_SHA256 = (
    "79fbdaccd5f7519efab685222101354c8c32473265c532aa85a98928bd50e68b")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"


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


def bind_raw(path: Path, raw: bytes) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def git_bytes(commit: str, path: Path) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path.relative_to(ROOT).as_posix()}"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    require(result.returncode == 0,
            f"git authority absent: {commit}:{path.relative_to(ROOT)}")
    return result.stdout


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    raw = git_bytes(commit, path)
    return {"authority": "git-blob", "commit": commit,
            "path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def function(source: str, signature: str) -> str:
    start = source.find(signature)
    require(start >= 0, f"function absent: {signature}")
    brace = source.find("{", start)
    require(brace >= 0, f"function body absent: {signature}")
    depth = 0
    for at in range(brace, len(source)):
        if source[at] == "{":
            depth += 1
        elif source[at] == "}":
            depth -= 1
            if depth == 0:
                return source[start:at + 1]
    raise AttributionError(f"unterminated function: {signature}")


def ordered(body: str, tokens: list[str], label: str) -> None:
    positions = [body.find(token) for token in tokens]
    require(all(at >= 0 for at in positions)
            and positions == sorted(positions), f"{label} order drift")


def profile_inputs(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("input_sha256="):
            continue
        name, digest = line[len("input_sha256="):].rsplit(":", 1)
        rows[name] = digest
    require(rows, f"profile input closure absent: {path}")
    return rows


def symbol_row(truth: ElfTruth, name: str) -> dict[str, Any]:
    symbol = truth.symbol(name)
    return {"address": f"0x{symbol.value:04x}", "bytes": symbol.bytes,
            "section": symbol.section}


def section_row(truth: ElfTruth, name: str) -> dict[str, Any]:
    section = truth.section(name)
    return {"address": f"0x{section.address:04x}", "bytes": section.bytes,
            "end_exclusive": f"0x{section.address + section.bytes:04x}"}


def phase_binding() -> dict[str, Any]:
    main = MAIN.read_text(encoding="utf-8")
    mem = MEM.read_text(encoding="utf-8")
    evaluator = EVAL.read_text(encoding="utf-8")
    overlay = OVERLAY.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    decoder = DECODER.read_text(encoding="utf-8")
    progress = BOOT_PROGRESS.read_text(encoding="utf-8")
    main_fn = function(main, "int main(void)")
    mem_init = function(mem, "void mem_init(void)")
    eval_init = function(evaluator, "WORKBENCH_BOOTFN void eval_init(void)")
    overlay_entry = function(
        overlay, "void vm_workbench_boot_overlay_entry(void)")
    prepare = function(runtime, "uint8_t c2_product_prepare_boot(void)")
    boot = function(runtime, "uint8_t c2_product_boot(void)")
    phase00 = function(decoder, "C2_SLICE(00) uint8_t c2_stream_phase_00")

    ordered(main_fn, ["if (!c2_kernal_take_ownership())",
                      "boot_overlay_result = vm_install_staged_boot_overlay()",
                      "if (!c2_product_prepare_boot())",
                      "boot_overlay_result = (uint8_t)vm_runtime_overlay_install_island()",
                      "if (!c2_product_boot())", "BT(5); repl()"],
            "current main boot")
    ordered(mem_init, ["LISP65_BOOT_PROGRESS_HEAP()", "freelist = NIL",
                       "for (i = MAX_CELLS - 1", "cell_set_a",
                       "freelist = (obj)(i << 1)"], "current mem_init")
    ordered(boot, ["c2_stream_init", "c2_decode_from",
                   "c2_pending_roots = c2_runtime.c2_root_count",
                   "c2_committed_roots = c2_runtime.c2_root_count",
                   "c2_publish_exports_from", "c2_ready = 1"],
            "current C2 boot")
    require("mem_init();" in eval_init and "eval_init();" in overlay_entry,
            "overlay/eval/mem boot edge drift")
    require("LISP65_BOOT_PROGRESS_LIBRARIES();" in phase00
            and "LISP65_BOOT_PROGRESS_HEAP()" in progress
            and "LISP65_BOOT_PROGRESS_LIBRARIES()" in progress,
            "boot progress cutpoints drift")
    require("c2_facade_select_family" in prepare,
            "prepare-family edge drift")

    truth = ElfTruth.read(CURRENT_ELF, llvm_readobj=READOBJ)
    old = ElfTruth.read(LINK96_ELF, llvm_readobj=READOBJ)
    current_eval = truth.symbol("eval_init")
    old_eval = old.symbol("eval_init")
    require((current_eval.value, current_eval.bytes) == (0xC3FD, 0x4D4)
            and (old_eval.value, old_eval.bytes) == (0xC3FD, 0x45D),
            "liveness-instrumented eval_init geometry drift")
    return {
        "visible_interval": {
            "opens": "mem_init entry before freelist=NIL",
            "closes": "first instruction-level action of c2_stream_phase_00",
            "screen_lines": ["LISP65: BUILDING HEAP",
                             "LISP65: LOADING LIBRARIES"],
            "classification": "BROAD-PRE-PHASE00-BOOT-INTERVAL",
            "heap_loop_only_claim_valid": False,
        },
        "ordered_reachable_stages": [
            "mem_init progress store", "hot-BSS clear", "freelist reset",
            "root-stack canaries/reset", "1024 EXT cell-a DMA writes",
            "remaining eval_init primitive/symbol installation", "vm_init",
            "boot-overlay chain completion and wipe", "C2 prepare/family select",
            "runtime-island installation", "c2_product_boot setup",
            "c2_decode_from dispatch up to phase 00 entry",
        ],
        "fail_closed_families": [
            "mem/eval lisp_error_msg or mem_oom",
            "boot-overlay chain status/CRC/entry/wipe",
            "C2 prepare family selection and C2D header write",
            "runtime-island family/stage/CRC/convergence/stack/wipe",
            "pre-phase00 overlay dispatch",
        ],
        "ELF_cutpoints": {
            name: symbol_row(truth, name) for name in (
                "main", "eval_init", "cell_set_a", "ext_set_a", "ext_dma",
                "vm_install_staged_boot_overlay",
                "vm_runtime_overlay_install_island", "c2_decode_from",
                "c2_stream_phase_00", "c2_kernal_fail_closed")
        },
        "mem_init_EXT_writes": 1024,
        "bytes_per_EXT_write": 2,
        "logical_first_freelist_head": "0x0060",
        "source_bindings": {name: bind(path) for name, path in {
            "main": MAIN, "mem": MEM, "eval": EVAL,
            "boot_overlay": OVERLAY, "runtime": RUNTIME,
            "decoder": DECODER, "progress": BOOT_PROGRESS}.items()},
    }


def world_diff() -> dict[str, Any]:
    current = profile_inputs(CURRENT_PROFILE)
    old = profile_inputs(LINK96_PROFILE)
    current_src = {key: value for key, value in current.items()
                   if key.startswith("src/")}
    old_src = {key: value for key, value in old.items()
               if key.startswith("src/")}
    changed = sorted(key for key in set(current_src) | set(old_src)
                     if current_src.get(key) != old_src.get(key))
    require(changed == ["src/c2_mapped_far_convergence.s",
                        "src/c2_mapped_far_service.s", "src/mem.c"],
            f"Link96/current source input delta drift: {changed}")

    historical_mem = git_bytes(LINK96_COMMIT, MEM).decode()
    current_mem = MEM.read_text(encoding="utf-8")
    progress_block = (
        "#ifdef LISP65_C2_PRODUCT_CUT\n"
        "    /* mem_init is boot-overlay code in the C2 product.  This store therefore\n"
        "     * dies with the overlay and adds no resident byte or mutable state. */\n"
        "    LISP65_BOOT_PROGRESS_HEAP();\n"
        "#endif\n")
    normalized = current_mem.replace('#include "boot_progress.h"\n', "", 1)
    normalized = normalized.replace(progress_block, "", 1)
    require(normalized == historical_mem,
            "canonical mem delta exceeds the progress-only instrumentation")

    truth = ElfTruth.read(CURRENT_ELF, llvm_readobj=READOBJ)
    old_truth = ElfTruth.read(LINK96_ELF, llvm_readobj=READOBJ)
    current_sections = {name: section_row(truth, name) for name in (
        ".rodata", ".data", ".bss", ".noinit",
        ".lisp65_c2_fixed_bank0_hot_bss",
        ".lisp65_c2_convergence_state", ".lisp65_c2_mapped_far_service")}
    old_sections = {name: section_row(old_truth, name) for name in (
        ".rodata", ".data", ".bss", ".noinit",
        ".lisp65_c2_fixed_bank0_hot_bss")}
    current_symbols = {name: symbol_row(truth, name) for name in (
        "freelist", "gc_rootsp", "mem_oom", "c2_phase_owner",
        "c2_ready", "c2_committed_roots", "c2_pending_roots")}
    old_symbols = {name: symbol_row(old_truth, name) for name in (
        "freelist", "gc_rootsp", "mem_oom", "c2_phase_owner",
        "c2_ready", "c2_committed_roots", "c2_pending_roots")}
    device = load(LINK96_DEVICE)
    require(device["status"] == "LINK96-POINT-HARDWARE-GREEN; GUARD-CLEAN"
            and device["point_postcondition"] == {
                "defstruct_hardware_green": True,
                "form": "(make-point 3 4)", "result": "(point 3 4)"},
            "Link96 physical prompt/point authority drift")
    return {
        "healthy_world": {
            "identity": "Link96", "physical_boot_and_REPL": True,
            "point_result": "(point 3 4)", "ELF": bind(LINK96_ELF),
            "device_authority": bind(LINK96_DEVICE)},
        "candidate_world": {"identity": "v2.0-current", "ELF": bind(CURRENT_ELF),
                            "PRG": bind(CURRENT_PRG)},
        "canonical_source_delta": {
            "changed_profile_inputs": changed,
            "mem_change": "progress-only after normalization",
            "new_inputs": ["mapped convergence service facade/body"],
            "all_other_shared_src_inputs_byteidentical": True,
        },
        "owned_state_layout": {
            "Link96_sections": old_sections, "current_sections": current_sections,
            "Link96_symbols": old_symbols, "current_symbols": current_symbols,
            "VMA_contract_changed": True,
            "mem_init_semantics_changed": False,
        },
    }


def host_model() -> dict[str, Any]:
    BUILD.mkdir(parents=True, exist_ok=True)
    old_build = LANE.BUILD
    try:
        LANE.BUILD = BUILD
        binary = LANE.compile_lane(
            MODEL_BINARY.name,
            ["LISP65_EXT_HEAP_HOST_DMA_MODEL",
             "LISP65_DMA_CONTENT_CONVERGENCE"])
        run = LANE.run_lane(binary)
        LANE.accepted("current convergence-armed EXT model", run, 1)
    finally:
        LANE.BUILD = old_build
    safe = SAFE.source_facts()
    postlink = SAFE.postlink(CURRENT_ELF)
    require(safe["content_consumers"] == 11
            and all(safe["source_routes"].values())
            and postlink["content_consuming_raw_sites"] == 3,
            "current convergence consumer closure red")
    stats = run["stats"]
    require(stats["dma_faults"] == 0 and stats["mem_oom"] == 0
            and stats["dma_reads"] > 0 and stats["dma_writes"] > 0,
            "current heap host model red")
    return {
        "result": "PASS-NO-HOST-REPRODUCTION",
        "model": (
            "exact current mem/eval/vm sources; HEAP=48, EXT=1024; checked "
            "staged EXT transport; content convergence compile define armed"),
        "completion": "while target fixture => 600",
        "stats": stats,
        "F018B": {
            "content_consumers": safe["content_consumers"],
            "source_routes": safe["source_routes"],
            "postlink": postlink,
        },
        "limits": (
            "Host staged-copy semantics do not model MEGA65 DMA completion "
            "timing, mapping or the target overlay machine."),
    }


def capture_row() -> dict[str, Any]:
    value = load(CAPTURE)
    require(value.get("format")
            == "lisp65-c2-v20-building-heap-stopped-state-row-v1"
            and value.get("status") == "host-specified-not-run"
            and value["observation"]["stop_count"] == 1
            and value["observation"]["resume_count"] == 0
            and value["claim_limit"].startswith("One future stopped-state row"),
            "BUILDING-HEAP capture row contract drift")
    truth = ElfTruth.read(CURRENT_ELF, llvm_readobj=READOBJ)
    for name, (address, size) in value["symbol_bindings"].items():
        row = symbol_row(truth, name)
        require(row["address"] == address and row["bytes"] == size,
                f"capture symbol drift: {name}")
    required_rows = {
        "early-eval-or-ext-dma", "boot-overlay-chain",
        "runtime-family-or-convergence", "c2-prepare-or-decode",
        "wild-control-flow", "ambiguous"}
    require(set(value["decision_rows"]) == required_rows
            and len(value["physical_bank0_ranges"]) == 10
            and value["tuple_first"][:2] == ["PC", "SP"]
            and "captured CPU view" in value["code_rule"]
            and "physical RAM" in value["data_rule"],
            "capture row is incomplete")
    return value


def derive() -> dict[str, Any]:
    plan = PLAN.read_text(encoding="utf-8")
    require("D1 red at BUILDING HEAP" in plan
            and "Addendum accepted — two separate D1 reds" in plan,
            "owner commission/addendum absent")
    phase = phase_binding()
    diff = world_diff()
    model = host_model()
    row = capture_row()
    return {
        "format": FORMAT, "recorded_on": RECORDED_ON,
        "status": STATUS,
        "authority": {
            "owner_commission": bind(PLAN), "capture_contract": bind(CAPTURE),
            "current_card": bind(CARD_RECEIPT),
            "Link96_device_control": bind(LINK96_DEVICE),
            "F018B_contract": bind(SAFE.CONTRACT), "driver": bind(DRIVER),
        },
        "observed_first_red": {
            "owner_observation": "BUILDING HEAP then red frame; no REPL",
            "missing_STAGING_MEDIA_is_separate": True,
            "device_reads": 0, "stopped_state": "not captured",
            "mechanism_claim": None,
        },
        "phase_binding": phase,
        "world_diff": diff,
        "host_model": model,
        "disposition": {
            "host_mechanism_named": False,
            "target_only_residue": [
                "MEGA65 DMA completion/timing", "runtime mapping visibility",
                "boot-overlay/family target execution", "wild control transfer"],
            "next_evidence": "one stopped-state row after the natural red frame",
            "capture_row": row,
            "capture_row_specified": True,
            "recontact_authorized": False,
            "D2_D5_open": False,
        },
        "execution_accounting": {
            "host_compiles": 1, "host_runs": 1, "product_links": 0,
            "WPLTO_runs": 0, "media_builds": 0, "hardware_contacts": 0},
        "claim_limit": (
            "Host/source/ELF attribution only. BUILDING HEAP names a broad "
            "pre-phase00 interval, not a heap-loop mechanism. The host model "
            "is green; one row is specified but no contact is authorized."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and value["phase_binding"]["visible_interval"]["classification"]
            == "BROAD-PRE-PHASE00-BOOT-INTERVAL"
        and value["phase_binding"]["visible_interval"]
            ["heap_loop_only_claim_valid"] is False
        and value["phase_binding"]["mem_init_EXT_writes"] == 1024
        and value["world_diff"]["owned_state_layout"]
            ["mem_init_semantics_changed"] is False
        and value["host_model"]["result"] == "PASS-NO-HOST-REPRODUCTION"
        and value["host_model"]["stats"]["dma_faults"] == 0
        and value["host_model"]["stats"]["mem_oom"] == 0
        and value["disposition"]["host_mechanism_named"] is False
        and value["disposition"]["capture_row_specified"] is True
        and value["disposition"]["recontact_authorized"] is False
        and value["disposition"]["D2_D5_open"] is False
        and value["execution_accounting"] == {
            "host_compiles": 1, "host_runs": 1, "product_links": 0,
            "WPLTO_runs": 0, "media_builds": 0, "hardware_contacts": 0},
        "BUILDING-HEAP attribution claim drift")
    if verify:
        require(value == derive(), "BUILDING-HEAP attribution receipt stale")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "narrow-line-to-heap-loop": lambda x:
            x["phase_binding"]["visible_interval"].update(
                classification="EXT-FREELIST-LOOP",
                heap_loop_only_claim_valid=True),
        "change-write-count": lambda x:
            x["phase_binding"].update(mem_init_EXT_writes=4096),
        "claim-mem-semantics-drift": lambda x:
            x["world_diff"]["owned_state_layout"].update(
                mem_init_semantics_changed=True),
        "hide-host-red": lambda x: x["host_model"].update(result="PASS"),
        "accept-dma-fault": lambda x:
            x["host_model"]["stats"].update(dma_faults=1),
        "drop-capture-row": lambda x:
            x["disposition"].update(capture_row_specified=False),
        "claim-mechanism": lambda x:
            x["disposition"].update(host_mechanism_named=True),
        "authorize-contact": lambda x:
            x["disposition"].update(recontact_authorized=True),
        "open-D2-D5": lambda x: x["disposition"].update(D2_D5_open=True),
        "claim-device": lambda x:
            x["execution_accounting"].update(hardware_contacts=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate, verify=False)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases), "BUILDING-HEAP attribution mutation survived")
    return rejected


def build_action() -> int:
    require(not RECEIPT.exists(), "BUILDING-HEAP attribution receipt exists")
    value = derive(); validate(value, verify=False)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("BUILDING-HEAP attribution: PASS host-green capture-row-specified")
    return 0


def rebind_action() -> int:
    raise AttributionError(
        "historical BUILDING-HEAP receipt is immutable; use the dated rebind")


def check() -> int:
    value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
    validate(value, verify=False)
    require(rejected == mutations(value),
            "BUILDING-HEAP attribution mutation set drift")
    if MEM_SOURCE_UNBIND.is_file():
        unbind = load(MEM_SOURCE_UNBIND)
        require(
            unbind.get("format") ==
                "lisp65-c2.3-v20-building-heap-mem-source-unbind-v1"
            and unbind.get("status") ==
                "PASS: HISTORICAL-BUILDING-HEAP-MEM-DETACHED-FROM-LIVE-SOURCE"
            and unbind["authority"]["historical_receipt"] == bind(RECEIPT)
            and unbind["historical_observation"]["receipt_rewritten"] is False
            and unbind["historical_observation"]["claim_changed"] is False
            and unbind["living_successor"]
                ["historical_mem_is_live_predicate"] is False,
            "BUILDING-HEAP mem-source unbind drift")
        print("BUILDING-HEAP attribution check: PASS "
              "historical=unchanged live-mem=detached")
        return 0
    current = derive()
    if value == current:
        print("BUILDING-HEAP attribution check: PASS host-green row-specified")
        return 0
    require(hashlib.sha256(RECEIPT.read_bytes()).hexdigest()
                == HISTORICAL_RECEIPT_SHA256,
            "historical BUILDING-HEAP attribution receipt was rewritten")
    latest = LATEST_REBIND.is_file()
    rebind = load(LATEST_REBIND if latest else REBIND)
    require(
        rebind.get("format") == (
            "lisp65-c2.3-v20-building-heap-attribution-rebind-v2"
            if latest else
            "lisp65-c2.3-v20-building-heap-attribution-rebind-v1")
        and rebind.get("status") == (
            "PASS: second loud semantic-preserving current-source rebind"
            if latest else
            "PASS: loud semantic-preserving current-source rebind")
        and rebind["authority"]["historical_receipt"] == bind(RECEIPT)
        and rebind["authority"]["current_projection"]
            == bind_raw(RECEIPT, canonical(current))
        and rebind["change"]["semantic_claims_changed"] is False,
        "BUILDING-HEAP dated rebind drift")
    print("BUILDING-HEAP attribution check: PASS historical=unchanged live=bound")
    return 0


def selftest() -> int:
    if MEM_SOURCE_UNBIND.is_file():
        value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
        validate(value, verify=False)
        require(rejected == mutations(value),
                "historical BUILDING-HEAP mutation set drift")
        print("BUILDING-HEAP attribution selftest: PASS "
              "mutations=10 historical-live-unbound")
        return 0
    value = derive(); validate(value, verify=False)
    require(len(mutations(value)) == 10,
            "BUILDING-HEAP attribution mutation count drift")
    print("BUILDING-HEAP attribution selftest: PASS mutations=10")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "check", "selftest", "rebind"))
    action = parser.parse_args().action
    return {"build": build_action, "check": check,
            "selftest": selftest, "rebind": rebind_action}[action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, SAFE.FixError, LANE.LaneError, RuntimeError,
            OSError, ValueError, KeyError, json.JSONDecodeError,
            subprocess.SubprocessError) as error:
        print(f"BUILDING-HEAP attribution: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
