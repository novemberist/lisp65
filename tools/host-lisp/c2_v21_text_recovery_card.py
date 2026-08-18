#!/usr/bin/env python3
"""Run the one owner-authorized 2.1 cold-relocation/selector product card."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_v21_cpu_transport_shrink_card as SHRINK  # noqa: E402
import c2_v21_text_recovery_pricing as PRICE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
PRICING = ARCH / "c2.3-v2.1-text-recovery-pricing-receipt.json"
PREDECESSOR = ARCH / "c2.3-v2.1-cpu-transport-shrink-card-final-red.json"
BUILD = ROOT / "build/c2.3/v2.1-text-recovery-card"
PREFLIGHT = ROOT / "build/c2.3/v2.1-text-recovery-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
RECEIPT = ARCH / "c2.3-v2.1-text-recovery-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v2.1-text-recovery-card-final-red.json"
EMITTER = ROOT / "src/c2_session_emitter.c"
RUNTIME = ROOT / "src/c2_product_runtime.c"
READER = ROOT / "src/optional/c2_map_cpu_read.s"
FACADE = ROOT / "src/c2_kernal_facade_reopen.s"
DRIVER = Path(__file__).resolve()
LLVM = ROOT / "tools/llvm-mos/bin"
AUTHORIZATION = "428edb5e"
RECORDED_ON = "2026-08-14"
LINK = 107


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


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


def run(*argv: str) -> str:
    return subprocess.run(argv, cwd=ROOT, check=True, text=True,
                          stdout=subprocess.PIPE).stdout


def git_binding(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    full = run("git", "rev-parse", f"{commit}^{{commit}}").strip()
    raw = subprocess.run(["git", "show", f"{full}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    authority = git_binding(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{authority['commit']}:{authority['path']}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().split()).lower()
    for token in (
            "card go",
            "exactly one card",
            "c2e_w32",
            "selector seam on the runtime-overlay vector",
            "margins stay untouched non-budgets"):
        require(token in text, f"card authorization token absent: {token}")
    return authority


def configure() -> None:
    SHRINK.BUILD = BUILD
    SHRINK.PREFLIGHT = PREFLIGHT
    SHRINK.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT
    SHRINK.INVOCATION = INVOCATION
    SHRINK.PRODUCER_RESULT = PRODUCER_RESULT
    SHRINK.SCOPE_RESULT = SCOPE_RESULT
    SHRINK.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    SHRINK.RECEIPT = BUILD / "unused-shrink-wrapper-receipt.json"
    SHRINK.FINAL_RED = BUILD / "unused-shrink-wrapper-final-red.json"
    SHRINK.LINK = LINK
    SHRINK.configure()


def artifact_paths() -> dict[str, Path]:
    configure()
    return SHRINK.artifact_paths()


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    result = {name: bind(path) for name, path in artifact_paths().items()}
    result["seed_lto"] = bind(BUILD / "wplto/resident-island-seed.prg.lto.o")
    return result


def function_span(source: str, name: str, next_name: str) -> str:
    start = source.index(name)
    end = source.index(next_name, start + len(name))
    return source[start:end]


def source_gate(emitter_override: str | None = None,
                runtime_override: str | None = None,
                reader_override: str | None = None,
                facade_override: str | None = None) -> dict[str, Any]:
    emitter = EMITTER.read_text(encoding="utf-8") if emitter_override is None else emitter_override
    runtime = RUNTIME.read_text(encoding="utf-8") if runtime_override is None else runtime_override
    reader = READER.read_text(encoding="utf-8") if reader_override is None else reader_override
    facade = FACADE.read_text(encoding="utf-8") if facade_override is None else facade_override

    definition = (
        'C2E_SECTION("final_crc") static void c2e_w32(uint16_t at, '
        'uint32_t value)')
    final_phase = function_span(
        emitter, "C2E_SECTION(\"final_crc\") uint8_t "
        "c2_session_emit_final_crc_phase", "C2_KERNAL_RESIDENT c2_emit_status")
    require(emitter.count(definition) == 1
            and emitter.count("c2e_w32(") == 6
            and final_phase.count("c2e_w32(") == 5,
            "c2e_w32 is not one cold owner with five cold-only calls")

    shelf = function_span(runtime, "C2_KERNAL_RESIDENT uint8_t c2_stream_shelf_read",
                          "C2_KERNAL_RESIDENT uint8_t c2_stream_c2d_read")
    c2d = function_span(runtime, "C2_KERNAL_RESIDENT uint8_t c2_stream_c2d_read",
                        "C2_KERNAL_RESIDENT uint8_t c2_stream_c2d_write")
    alias = '__asm__("c2_facade_runtime_overlay_exec")'
    require(
        runtime.count(alias) == 2
        and runtime.count("c2_facade_map_cpu_read(") == 4
        and "return c2_map_cpu_read(" not in shelf + c2d
        and shelf.count("c2_stream_shelf_read_return") == 2
        and c2d.count("c2_stream_c2d_read_return") == 2
        and shelf.index("c2_facade_map_cpu_read(")
            < shelf.index("c2_stream_shelf_read_return")
        and c2d.index("c2_facade_map_cpu_read(")
            < c2d.index("c2_stream_c2d_read_return"),
        "E000 callers do not carry two symbolic post-call identities")

    require(
        "c2_facade_runtime_overlay_exec:\n\tjmp c2_map_cpu_selector" in facade
        and "c2_facade_runtime_overlay_exec:\n\tjmp vm_runtime_overlay_exec" not in facade,
        "fixed runtime-overlay vector does not retain identity through selector")
    selector = reader[reader.index("c2_map_cpu_selector:"):]
    for token in (
            "pha", "phx", "tsx", "c2_stream_c2d_read_return-1",
            "c2_stream_shelf_read_return-1", "plx", "pla",
            "jmp vm_runtime_overlay_exec", "jmp c2_map_cpu_read"):
        require(token in selector, f"selector token absent: {token}")
    require(selector.count("\tplx\n\tpla\n") == 2
            and "cmp #>(c2_stream_c2d_read_return-1)" in selector
            and "cmp #<(c2_stream_c2d_read_return-1)" in selector
            and "cmp #>(c2_stream_shelf_read_return-1)" in selector
            and "cmp #<(c2_stream_shelf_read_return-1)" in selector
            and selector.index("jmp vm_runtime_overlay_exec")
                < selector.index("jmp c2_map_cpu_read")
            and not re.search(r"cmp\s+#?\$[0-9a-fA-F]{4}", selector),
            "selector clobbers registers, loses legacy default or pins a raw PC")
    return {
        "status": "PASS: cold-only helper and preserving symbolic selector source",
        "c2e_w32": {"definitions": 1, "cold_calls": 5,
                     "outside_cold_calls": 0},
        "reader_callers": ["c2_stream_c2d_read_return",
                           "c2_stream_shelf_read_return"],
        "fixed_vector": "c2_facade_runtime_overlay_exec",
        "unknown_caller_tail": "vm_runtime_overlay_exec",
    }


def object_gate() -> dict[str, Any]:
    reader_bytes, truth = PRICE.assemble(
        READER.read_text(encoding="utf-8"),
        ".text.c2_map_cpu_read", "c2_map_cpu_read")
    selector = truth.symbol("c2_map_cpu_selector")
    relocs = [row.target for row in truth.relocations
              if row.source_section == ".text.c2_map_cpu_selector"]
    require(
        reader_bytes == 166 and selector.bytes == 40
        and relocs.count("c2_stream_c2d_read_return") == 2
        and relocs.count("c2_stream_shelf_read_return") == 2
        and relocs.count("vm_runtime_overlay_exec") == 1
        and relocs.count("c2_map_cpu_read") == 1,
        "actual selector object does not match the 40-byte symbolic price")
    return {"status": "PASS: actual reader/selector object matches price",
            "reader_bytes": reader_bytes, "selector_bytes": selector.bytes,
            "symbolic_relocations": relocs}


def source_mutations() -> list[str]:
    emitter = EMITTER.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    reader = READER.read_text(encoding="utf-8")
    facade = FACADE.read_text(encoding="utf-8")
    cases = {
        "return-c2e-w32-to-resident": (emitter.replace(
            'C2E_SECTION("final_crc") static void c2e_w32',
            "static void c2e_w32", 1), runtime, reader, facade),
        "add-warm-c2e-w32-call": (emitter.replace(
            "static uint8_t c2e_symbol(obj value) {",
            "static void c2e_warm_probe(void) { c2e_w32(0, 0); }\n"
            "static uint8_t c2e_symbol(obj value) {", 1), runtime, reader, facade),
        "lose-shelf-return-identity": (emitter, runtime.replace(
            "c2_stream_shelf_read_return", "c2_stream_shelf_return_lost", 2),
            reader, facade),
        "restore-direct-reader-call": (emitter, runtime.replace(
            "c2_facade_map_cpu_read(", "c2_map_cpu_read(", 2), reader, facade),
        "retire-runtime-overlay-default": (emitter, runtime, reader.replace(
            "\tjmp vm_runtime_overlay_exec\n", "\tjmp c2_map_cpu_read\n", 1), facade),
        "lose-selector-register-restore": (emitter, runtime, reader.replace(
            "\tplx\n\tpla\n\tjmp vm_runtime_overlay_exec",
            "\tpla\n\tjmp vm_runtime_overlay_exec", 1), facade),
        "raw-return-PC-pin": (emitter, runtime, reader.replace(
            "#>(c2_stream_c2d_read_return-1)", "#$e3", 1), facade),
        "bypass-selector": (emitter, runtime, reader, facade.replace(
            "\tjmp c2_map_cpu_selector\n", "\tjmp vm_runtime_overlay_exec\n", 1)),
    }
    rejected: list[str] = []
    for name, (e, r, a, f) in cases.items():
        try:
            source_gate(e, r, a, f)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases), "text-recovery source mutation survived")
    return rejected


def preflight_value() -> dict[str, Any]:
    pricing = load(PRICING)
    predecessor = load(PREDECESSOR)
    require(pricing.get("decision", {}).get("winner")
                == "option-b-wholesale-displacement"
            and pricing["decision"]["card_authorized"] is False
            and predecessor.get("status")
                == "FINAL RED: CPU-reader shrink card returns to owner",
            "pricing/predecessor authority drift")
    return {
        "format": "lisp65-c2.3-v2.1-text-recovery-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: one cold-relocation/selector card armed",
        "configuration": {"link": LINK, "cards_authorized": 1},
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
                               "product_links": 0, "media_builds": 0,
                               "device_contacts": 0},
        "source_gate": source_gate(),
        "object_gate": object_gate(),
        "priced_outcome": {
            "helper_recovered_bytes": 63, "selector_bytes": 40,
            "expected_ordinary_reserve_bytes": 24,
            "fixed_delta_bytes": 0, "E000_delta_bytes": 0,
            "aggregate_delta_bytes": 0,
            "contracted_margins_used_as_freight": False,
        },
        "authority": {"authorization": authorization(),
                      "pricing": bind(PRICING), "predecessor": bind(PREDECESSOR),
                      "emitter": bind(EMITTER), "runtime": bind(RUNTIME),
                      "reader": bind(READER), "facade": bind(FACADE),
                      "driver": bind(DRIVER)},
        "claim_limit": "Host preflight only; no WPLTO, product link, media or device.",
    }


def validate_preflight(value: dict[str, Any]) -> None:
    require(value == preflight_value(), "text-recovery preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases = {
        "authorize-two-cards": lambda x: x["configuration"].update(cards_authorized=2),
        "spend-margin": lambda x: x["priced_outcome"].update(
            contracted_margins_used_as_freight=True),
        "lose-reserve": lambda x: x["priced_outcome"].update(
            expected_ordinary_reserve_bytes=0),
        "invent-card-run": lambda x: x["attempt_accounting"].update(cards_consumed=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate_preflight(candidate)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases), "text-recovery preflight mutation survived")
    return rejected


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "text-recovery card/preflight is one-shot")
    value = preflight_value()
    validate_preflight(value)
    value["mutations_rejected"] = {
        "source": source_mutations(),
        "preflight": preflight_mutations(value),
    }
    PREFLIGHT.mkdir(parents=True)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("2.1 text recovery: PREFLIGHT PASS helper=63 selector=40 "
          "reserve=24 mutations=12 card=0/1")


def disassembly(elf: Path, section: str) -> str:
    return run(str(LLVM / "llvm-objdump"), "-d", f"--section={section}", str(elf))


def linked_gate(elf: Path, manifest_path: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=LLVM / "llvm-readobj")
    text = truth.section(".text")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    fixed = truth.section(".lisp65_c2_host_facade")
    cold = truth.section(".lisp65_rt_c2emit_final_crc")
    reader = truth.symbol("c2_map_cpu_read")
    selector = truth.symbol("c2_map_cpu_selector")
    helper = truth.symbol("c2e_w32")
    vector = truth.symbol("c2_facade_runtime_overlay_exec")
    shelf_return = truth.symbol("c2_stream_shelf_read_return")
    c2d_return = truth.symbol("c2_stream_c2d_read_return")
    shelf = truth.symbol("c2_stream_shelf_read")
    c2d = truth.symbol("c2_stream_c2d_read")
    reserve = facade.address - (text.address + text.bytes)
    require(
        reader.section == ".text" and reader.bytes == 166
        and selector.section == ".text" and selector.bytes == 40
        and helper.section == cold.name and helper.bytes == 63
        and cold.bytes == 1246 and reserve == 24
        and fixed.address == 0xB5C4 and fixed.bytes == 48
        and vector.value == 0xB5EB
        and shelf.bytes == 194 and c2d.bytes == 85,
        "linked placement/capacity differs from priced identity")

    e000 = disassembly(elf, ".lisp65_c2_kernal_window.c2_resident").lower()
    for returned in (shelf_return, c2d_return):
        expected = returned.value - 3
        require(re.search(
            rf"^\s*{expected:x}:\s+(?:[0-9a-f]{{2}}\s+){{3}}jsr\s+\$b5eb\b",
            e000, re.M),
            f"symbolic return identity is not immediately after JSR: {returned.name}")
    require(len(re.findall(r"\b(?:jsr|jmp)\s+\$2277\b", e000)) == 0,
            "E000 still bypasses fixed facade for CPU reader")

    fixed_text = disassembly(elf, ".lisp65_c2_host_facade").lower()
    require(re.search(
        rf"^\s*b5eb:.*jmp\s+\${selector.value:x}\b", fixed_text, re.M),
            "runtime-overlay fixed vector no longer has one JMP body")
    selector_text = disassembly(elf, ".text").lower()
    selector_body = "\n".join(
        line for line in selector_text.splitlines()
        if (match := re.match(r"^\s*([0-9a-f]+):", line))
        and selector.value <= int(match.group(1), 16)
        < selector.value + selector.bytes)
    require("pha" in selector_body and "phx" in selector_body
            and selector_body.count("plx") == 2
            and selector_body.count("pla") == 2
            and f"jmp\t${reader.value:x}" in selector_body,
            "linked selector lost register or reader tail identity")

    cold_text = disassembly(elf, cold.name).lower()
    calls = re.findall(rf"^\s*([0-9a-f]+):.*jsr\s+\${helper.value:x}\b",
                       cold_text, re.M)
    all_text = run(str(LLVM / "llvm-objdump"), "-d", str(elf)).lower()
    all_calls = re.findall(rf"^\s*([0-9a-f]+):.*jsr\s+\${helper.value:x}\b",
                           all_text, re.M)
    require(len(calls) == len(all_calls) == 5,
            "c2e_w32 has a non-cold or missing linked caller")

    manifest = load(manifest_path)
    rows = sorted(manifest["slices"], key=lambda row: row["file_offset"])
    row = next(item for item in rows if item["section"] == cold.name)
    following = rows[rows.index(row) + 1]
    allocation = following["file_offset"] - row["file_offset"]
    require(row["file_size"] == 1246 and allocation == 1280
            and manifest["storage"]["size"] == 65423,
            "cold displacement grew a slot or aggregate image")
    return {
        "status": "PASS: cold displacement and preserving selector linked as priced",
        "ordinary": {"text_end_exclusive": f"0x{text.address + text.bytes:04x}",
                     "facade_start": f"0x{facade.address:04x}",
                     "reserve_bytes": reserve, "net_delta_bytes": -23},
        "reader": {"address": f"0x{reader.value:04x}", "bytes": reader.bytes},
        "selector": {"address": f"0x{selector.value:04x}",
                     "bytes": selector.bytes, "fixed_vector": "0xb5eb",
                     "symbolic_returns": {
                         shelf_return.name: f"0x{shelf_return.value:04x}",
                         c2d_return.name: f"0x{c2d_return.value:04x}"}},
        "cold_displacement": {"symbol": helper.name, "bytes": helper.bytes,
                              "section": cold.name, "section_bytes": cold.bytes,
                              "linked_calls": len(all_calls),
                              "packed_page_bytes": allocation,
                              "packed_padding_bytes": allocation - row["file_size"],
                              "aggregate_bytes": manifest["storage"]["size"],
                              "aggregate_growth_bytes": 0},
        "fixed_block_delta_bytes": 0, "E000_delta_bytes": 0,
        "contracted_margins_used_as_freight": False,
    }


def linked_mutations(value: dict[str, Any]) -> list[str]:
    cases = {
        "lose-resident-reserve": lambda x: x["ordinary"].update(reserve_bytes=0),
        "grow-fixed-block": lambda x: x.update(fixed_block_delta_bytes=3),
        "grow-E000": lambda x: x.update(E000_delta_bytes=1),
        "add-warm-helper-call": lambda x: x["cold_displacement"].update(linked_calls=6),
        "grow-aggregate": lambda x: x["cold_displacement"].update(
            aggregate_growth_bytes=256),
        "spend-margin": lambda x: x.update(contracted_margins_used_as_freight=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            require(candidate["ordinary"]["reserve_bytes"] == 24
                    and candidate["fixed_block_delta_bytes"] == 0
                    and candidate["E000_delta_bytes"] == 0
                    and candidate["cold_displacement"]["linked_calls"] == 5
                    and candidate["cold_displacement"]["aggregate_growth_bytes"] == 0
                    and candidate["contracted_margins_used_as_freight"] is False,
                    "linked text-recovery mutation")
        except CardError:
            rejected.append(name)
    require(rejected == list(cases), "linked text-recovery mutation survived")
    return rejected


def postlink_artifacts(paths: Mapping[str, Path]) -> tuple[Path]:
    """Resolve this wrapper's inputs through the typed producer vocabulary."""
    return (paths["elf"],)


def produce_child() -> int:
    configure()
    result = SHRINK.BASE.produce_child()
    paths = artifact_paths()
    (elf,) = postlink_artifacts(paths)
    gate = linked_gate(
        elf, BUILD / "wplto/runtime-overlays-session-final.json")
    value = load(PRODUCER_RESULT)
    value["v21_text_recovery"] = gate
    value["v21_text_recovery_mutations"] = linked_mutations(gate)
    PRODUCER_RESULT.write_bytes(canonical(value))
    return result


def scope_child() -> int:
    configure()
    return SHRINK.BASE.scope_child()


def acceptance_child() -> int:
    configure()
    return SHRINK.BASE.acceptance_child()


def run_child(action: str) -> None:
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"fresh text-recovery child {action} red:\n{result.stdout}")


def card() -> None:
    value = load(PREFLIGHT_RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate_preflight(value)
    require(rejected == {"source": source_mutations(),
                         "preflight": preflight_mutations(value)},
            "text-recovery mutation receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "text-recovery card is one-shot")
    INVOCATION.write_bytes(canonical({
        "status": "INVOKED", "link": LINK, "authorization": authorization(),
        "predecessor": bind(PREDECESSOR), "pricing": bind(PRICING),
        "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)}))
    run_child("_produce")
    before = frozen_artifacts()
    run_child("_scope")
    run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "text-recovery acceptance changed linked artifacts")
    producer = load(PRODUCER_RESULT)
    scope = load(SCOPE_RESULT)
    acceptance = load(ACCEPTANCE_RESULT)
    require(len({os.getpid(), producer["pid"], scope["pid"],
                 acceptance["pid"]}) == 4,
            "text-recovery card process isolation drift")
    gate = producer["v21_text_recovery"]
    require(producer["v21_text_recovery_mutations"] == linked_mutations(gate),
            "linked mutation receipt drift")
    receipt = {
        "format": "lisp65-c2.3-v2.1-text-recovery-card-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: 2.1 cold-relocation/selector product card green",
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "WPLTO_runs": 1, "product_links": 1, "media_builds": 0,
            "device_contacts": 0},
        "authority": {"authorization": authorization(), "pricing": bind(PRICING),
                      "predecessor": bind(PREDECESSOR),
                      "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "linked_result": gate,
        "artifacts_before": before, "artifacts_after": after,
        "process_isolation": {"parent": os.getpid(), "producer": producer["pid"],
            "owner_scope": scope["pid"], "acceptance": acceptance["pid"],
            "all_distinct": True},
        "owner_scope": scope["gate"],
        "acceptance": {key: item for key, item in acceptance.items()
                       if key not in ("status", "pid")},
        "mutations_rejected": {"preflight": rejected,
                               "linked": producer["v21_text_recovery_mutations"]},
        "next": "artifact completion, same-world media closure, then D1",
        "claim_limit": "One product card only; completion, media and device have not run.",
    }
    RECEIPT.write_bytes(canonical(receipt))
    print("2.1 text recovery: CARD PASS card=1/1 reserve=24 "
          "selector=40 cold=63")


def record_final_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in artifact_paths().items()
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v2.1-text-recovery-card-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: 2.1 text-recovery card returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "WPLTO_runs": 1 if artifacts else 0,
            "product_link_attempts": 1 if artifacts else 0,
            "media_builds": 0, "device_contacts": 0},
        "artifacts": artifacts, "retry_authorized": False,
        "owner_disposition_required": True,
        "authority": {"authorization": authorization(), "pricing": bind(PRICING),
                      "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
    }))


def check() -> None:
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value.get("retry_authorized") is False
                and value.get("owner_disposition_required") is True,
                "text-recovery Final Red drift")
        print("2.1 text recovery: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        if PREFLIGHT_RECEIPT.exists():
            value = load(PREFLIGHT_RECEIPT)
            rejected = value.pop("mutations_rejected")
            validate_preflight(value)
            require(rejected == {"source": source_mutations(),
                                 "preflight": preflight_mutations(value)},
                    "text-recovery preflight receipt drift")
        print("2.1 text recovery: CHECK ARMED")
        return
    value = load(RECEIPT)
    require(value.get("status")
                == "PASS: 2.1 cold-relocation/selector product card green"
            and value["attempt_accounting"]["cards_consumed"] == 1
            and value["artifacts_before"] == frozen_artifacts()
            and value["artifacts_after"] == value["artifacts_before"]
            and value["linked_result"]["ordinary"]["reserve_bytes"] == 24,
            "text-recovery green receipt drift")
    print("2.1 text recovery: CHECK PASS card=1/1 reserve=24")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "preflight", "card", "check", "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    {"preflight": preflight, "card": card, "check": check,
     "_produce": produce_child, "_scope": scope_child,
     "_accept": acceptance_child}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_final_red(error)
            except Exception as receipt_error:
                print(f"text-recovery Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"2.1 text recovery: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
