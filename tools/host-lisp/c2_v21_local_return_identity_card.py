#!/usr/bin/env python3
"""Run the one approved local-return-identity replacement card."""

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
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v21_text_recovery_pricing as PRICE  # noqa: E402
import c2_v21_text_recovery_replacement_card as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
BUILD = ROOT / "build/c2.3/v2.1-local-return-identity-card"
PREFLIGHT = ROOT / "build/c2.3/v2.1-local-return-identity-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
RECEIPT = ARCH / "c2.3-v2.1-local-return-identity-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v2.1-local-return-identity-card-final-red.json"
PREDECESSOR = ARCH / (
    "c2.3-v2.1-text-recovery-replacement-card-final-red.json")
ATTRIBUTION = ARCH / (
    "c2.3-v2.1-text-recovery-replacement-card-red-attribution-receipt.json")
PRIOR_ELF = ROOT / (
    "build/c2.3/v2.1-text-recovery-replacement-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
RUNTIME = ROOT / "src/c2_product_runtime.c"
READER = ROOT / "src/optional/c2_map_cpu_read.s"
DRIVER = Path(__file__).resolve()
LLVM = ROOT / "tools/llvm-mos/bin"
AUTHORIZATION = "6772b41e"
RECORDED_ON = "2026-08-14"
LINK = 107
SECTION = ".lisp65_c2_kernal_window.c2_resident"
IDENTITIES = {
    "c2d": {"function": "c2_stream_c2d_read", "offset": 0x4B,
              "tail": bytes.fromhex("aa")},
    "shelf": {"function": "c2_stream_shelf_read", "offset": 0xB0,
                "tail": bytes.fromhex("8510")},
}


class LocalIdentityError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise LocalIdentityError(message)


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
            "return labels stop being global",
            "identity computation takes them from the emitted output",
            "one replacement card",
            "historical map-tuple receipt drift"):
        require(token in text, f"local-identity authorization absent: {token}")
    return authority


def predecessor() -> tuple[dict[str, Any], dict[str, Any]]:
    red = load(PREDECESSOR)
    attribution = load(ATTRIBUTION)
    require(
        red.get("status")
            == "FINAL RED: text-recovery replacement returns to owner"
        and red.get("retry_authorized") is False
        and attribution.get("status")
            == "ATTRIBUTED FINAL RED: exported intra-function labels split ownership"
        and attribution["new_final_red"]["qualified_edge_violations"] == 7
        and attribution["card_disposition"]["retry_authorized"] is False,
        "exported-return-label Final Red authority drift")
    return red, attribution


def configure() -> None:
    PREV.BUILD = BUILD
    PREV.PREFLIGHT = PREFLIGHT
    PREV.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT
    PREV.INVOCATION = INVOCATION
    PREV.PRODUCER_RESULT = PRODUCER_RESULT
    PREV.SCOPE_RESULT = SCOPE_RESULT
    PREV.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    PREV.RECEIPT = BUILD / "unused-predecessor-receipt.json"
    PREV.FINAL_RED = BUILD / "unused-predecessor-final-red.json"
    PREV.LINK = LINK
    PREV.linked_gate = linked_gate
    PREV.linked_mutations = linked_mutations
    PREV.configure()


def artifact_paths() -> dict[str, Path]:
    configure()
    return PREV.artifact_paths()


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    result = {name: bind(path) for name, path in artifact_paths().items()}
    result["seed_lto"] = bind(BUILD / "wplto/resident-island-seed.prg.lto.o")
    return result


def selector_source_gate(runtime_override: str | None = None,
                         reader_override: str | None = None) -> dict[str, Any]:
    runtime = (RUNTIME.read_text(encoding="utf-8")
               if runtime_override is None else runtime_override)
    reader = (READER.read_text(encoding="utf-8")
              if reader_override is None else reader_override)
    require("c2_stream_c2d_read_return" not in runtime + reader
            and "c2_stream_shelf_read_return" not in runtime + reader,
            "non-entry return label is still exported or consumed")
    require(reader.count("c2_stream_c2d_read+$4b") == 2
            and reader.count("c2_stream_shelf_read+$b0") == 2
            and "\t.globl c2_stream_c2d_read\n" in reader
            and "\t.globl c2_stream_shelf_read\n" in reader,
            "selector identities are not function-entry plus emitted offset")
    reader_bytes, truth = PRICE.assemble(
        reader, ".text.c2_map_cpu_read", "c2_map_cpu_read")
    rows = [row for row in truth.relocations
            if row.source_section == ".text.c2_map_cpu_selector"
            and row.target.startswith("c2_stream_")]
    addends = {(row.target, row.relocation_type): row.addend
               for row in rows}
    require(reader_bytes == 166
            and truth.symbol("c2_map_cpu_selector").bytes == 40
            and addends == {
                ("c2_stream_c2d_read", "R_MOS_ADDR16_HI"): 0x4B,
                ("c2_stream_c2d_read", "R_MOS_ADDR16_LO"): 0x4B,
                ("c2_stream_shelf_read", "R_MOS_ADDR16_HI"): 0xB0,
                ("c2_stream_shelf_read", "R_MOS_ADDR16_LO"): 0xB0},
            "selector object does not carry the emitted-output offsets")
    return {"status": "PASS: local non-entries; identities use emitted offsets",
            "return_labels_exported": False,
            "identity_depends_on_global_return_label": False,
            "reader_bytes": reader_bytes, "selector_bytes": 40,
            "relocations": {"c2d": "c2_stream_c2d_read+0x4b",
                            "shelf": "c2_stream_shelf_read+0xb0"}}


def source_mutations() -> list[str]:
    runtime = RUNTIME.read_text(encoding="utf-8")
    reader = READER.read_text(encoding="utf-8")
    promoted = reader.replace(
        "\t.globl c2_stream_c2d_read\n",
        "\t.globl c2_stream_c2d_read\n"
        "\t.globl c2_stream_c2d_read_return\n", 1)
    global_identity = reader.replace(
        "c2_stream_c2d_read+$4b", "c2_stream_c2d_read_return-2")
    global_identity = global_identity.replace(
        "\t.globl c2_stream_c2d_read\n",
        "\t.globl c2_stream_c2d_read_return\n", 1)
    cases = {
        "promote-non-entry-to-global": promoted,
        "derive-identity-from-global-label": global_identity,
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            selector_source_gate(runtime, candidate)
        except (LocalIdentityError, PRICE.PricingError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "local-return mutation survived")
    return rejected


def _call_identity(truth: ElfTruth, function: str, vector: int,
                   tail: bytes) -> dict[str, Any]:
    owner = truth.symbol(function)
    section = truth.section(owner.section)
    raw = truth.section_bytes(owner.section)
    body = raw[owner.value - section.address:
               owner.value - section.address + owner.bytes]
    pattern = bytes((0x20, vector & 0xFF, vector >> 8)) + tail
    matches = [at for at in range(len(body) - len(pattern) + 1)
               if body[at:at + len(pattern)] == pattern]
    require(len(matches) == 1, f"actual call/tail identity drift: {function}")
    call = owner.value + matches[0]
    pushed = call + 2
    return {"function": function, "entry": f"0x{owner.value:04x}",
            "call": f"0x{call:04x}", "emitted_bytes": pattern.hex(),
            "tail_bytes": tail.hex(), "hardware_pushed_return": f"0x{pushed:04x}",
            "entry_offset": pushed - owner.value}


def _owned_consumer(elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=LLVM / "llvm-readobj")
    sections = PRODUCT.section_table(elf)
    objdump = run(str(LLVM / "llvm-objdump"), "-d", f"--section={SECTION}",
                  str(elf)).lower()
    objdump += ("\nDisassembly of section .text:\n00002042 <shift>:\n"
                " 2042: a9 0e lda #$e\n 2044: 20 d2 ff jsr $ffd2\n")
    prior = PRODUCT.KERNAL_SECTIONS
    try:
        PRODUCT.KERNAL_SECTIONS = (SECTION,)
        return PRODUCT._owned_control_flow_gate(
            elf, sections, objdump, truth)
    finally:
        PRODUCT.KERNAL_SECTIONS = prior


def real_consumer_preflight() -> dict[str, Any]:
    require(PRIOR_ELF.is_file(), "consumed replacement ELF absent")
    historical_red = ""
    try:
        _owned_consumer(PRIOR_ELF)
    except RuntimeError as error:
        historical_red = str(error)
    require(historical_red.count("inter-function-jmp-not-entry") == 7,
            "historical actual-consumer red is not the seven-label case")
    with tempfile.TemporaryDirectory(prefix="lisp65-local-return-") as temp:
        stripped = Path(temp) / "candidate.elf"
        subprocess.run([
            str(LLVM / "llvm-objcopy"),
            "--strip-symbol=c2_stream_c2d_read_return",
            "--strip-symbol=c2_stream_shelf_read_return",
            str(PRIOR_ELF), str(stripped)], cwd=ROOT, check=True)
        result = _owned_consumer(stripped)
    require(result["violations"] == []
            and result["same_function_basic_block_jumps"] >= 7,
            "actual KERNAL-freedom consumer did not accept local non-entries")
    return {"status": "PASS: actual linked ownership consumer accepts local points",
            "historical_global_case_rejected_edges": 7,
            "local_projection_violations": 0,
            "local_projection_internal_basic_block_jumps":
                result["same_function_basic_block_jumps"],
            "consumer": "c2_product_substitution_link._owned_control_flow_gate"}


def prior_emitted_offsets() -> dict[str, Any]:
    truth = ElfTruth.read(PRIOR_ELF, llvm_readobj=LLVM / "llvm-readobj",
                          include_section_data=True)
    vector = truth.symbol("c2_facade_runtime_overlay_exec").value
    rows = {name: _call_identity(truth, spec["function"], vector, spec["tail"])
            for name, spec in IDENTITIES.items()}
    require(rows["c2d"]["entry_offset"] == 0x4B
            and rows["shelf"]["entry_offset"] == 0xB0,
            "emitted caller offsets do not match selector relocations")
    return rows


def preflight_value() -> dict[str, Any]:
    predecessor()
    return {
        "format": "lisp65-c2.3-v2.1-local-return-identity-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: local non-entries and emitted offsets; card armed",
        "configuration": {"link": LINK, "replacement_cards_authorized": 1},
        "attempt_accounting": {"replacement_cards_consumed": 0,
            "WPLTO_runs": 0, "product_links": 0, "media_builds": 0,
            "device_contacts": 0},
        "host_gates": {"source_and_object": selector_source_gate(),
            "prior_emitted_offsets": prior_emitted_offsets(),
            "actual_ownership_consumer": real_consumer_preflight()},
        "placement_inherited_green": {"resident_reserve_bytes": 24,
            "cold_helper_bytes": 63, "image_growth_bytes": 0},
        "authority": {"authorization": authorization(),
            "predecessor_final_red": bind(PREDECESSOR),
            "attribution": bind(ATTRIBUTION), "prior_ELF": bind(PRIOR_ELF),
            "runtime": bind(RUNTIME), "reader": bind(READER),
            "driver": bind(DRIVER)},
        "claim_limit": "Host preflight only; no WPLTO, link, media or device.",
    }


def validate_preflight(value: dict[str, Any]) -> None:
    require(value == preflight_value(), "local-return preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    candidate = deepcopy(value)
    candidate["configuration"]["replacement_cards_authorized"] = 2
    rejected: list[str] = []
    try:
        validate_preflight(candidate)
    except LocalIdentityError:
        rejected.append("authorize-two-cards")
    require(rejected == ["authorize-two-cards"], "one-card mutation survived")
    return rejected


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "local-return preflight/card is one-shot")
    value = preflight_value()
    validate_preflight(value)
    value["mutations_rejected"] = {
        "local_identity": source_mutations(),
        "card_contract": preflight_mutations(value),
    }
    PREFLIGHT.mkdir(parents=True)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("2.1 local return identity: PREFLIGHT PASS labels=local "
          "offsets=4b/b0 consumer=green mutations=3 card=0/1")


def disassembly(elf: Path, section: str) -> str:
    return run(str(LLVM / "llvm-objdump"), "-d", f"--section={section}",
               str(elf)).lower()


def validate_linked(value: dict[str, Any]) -> None:
    identities = value["selector"]["real_call_identities"]
    require(value["ordinary"]["reserve_bytes"] == 24
            and value["return_labels"]["global_non_entries"] == 0
            and value["selector"]["identity_depends_on_global_return_label"] is False
            and identities["c2d"]["entry_offset"] == 0x4B
            and identities["shelf"]["entry_offset"] == 0xB0
            and identities["selector_operands_match"] is True
            and value["ownership"]["violations"] == [],
            "linked local-return identity drift")


def linked_gate(elf: Path, manifest_path: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=LLVM / "llvm-readobj",
                          include_section_data=True)
    text = truth.section(".text")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    fixed = truth.section(".lisp65_c2_host_facade")
    cold = truth.section(".lisp65_rt_c2emit_final_crc")
    reader = truth.symbol("c2_map_cpu_read")
    selector = truth.symbol("c2_map_cpu_selector")
    helper = truth.symbol("c2e_w32")
    vector = truth.symbol("c2_facade_runtime_overlay_exec")
    shelf = truth.symbol("c2_stream_shelf_read")
    c2d = truth.symbol("c2_stream_c2d_read")
    reserve = facade.address - (text.address + text.bytes)
    require(reader.bytes == 166 and selector.bytes == 40
            and helper.section == cold.name and helper.bytes == 63
            and cold.bytes == 1246 and reserve == 24
            and fixed.address == 0xB5C4 and fixed.bytes == 48
            and vector.value == 0xB5EB and shelf.bytes == 194 and c2d.bytes == 85,
            "local-return card changed green placement identity")
    require(not truth.symbols_by_name.get("c2_stream_c2d_read_return")
            and not truth.symbols_by_name.get("c2_stream_shelf_read_return"),
            "linked ELF promotes an internal return point to a symbol")

    identities = {name: _call_identity(
        truth, spec["function"], vector.value, spec["tail"])
        for name, spec in IDENTITIES.items()}
    selector_section = truth.section(selector.section)
    raw = truth.section_bytes(selector.section)[
        selector.value - selector_section.address:
        selector.value - selector_section.address + selector.bytes]
    c2d_stack = int(identities["c2d"]["hardware_pushed_return"], 16)
    shelf_stack = int(identities["shelf"]["hardware_pushed_return"], 16)
    require(raw[7] == c2d_stack >> 8 and raw[14] == (c2d_stack & 0xFF)
            and raw[20] == shelf_stack >> 8 and raw[27] == (shelf_stack & 0xFF),
            "selector operands differ from actual emitted call identities")
    identities["selector_operands_match"] = True

    e000 = disassembly(elf, SECTION)
    require(len(re.findall(r"\b(?:jsr|jmp)\s+\$2277\b", e000)) == 0,
            "E000 bypasses the fixed selector vector")
    fixed_text = disassembly(elf, ".lisp65_c2_host_facade")
    require(re.search(rf"^\s*b5eb:.*jmp\s+\${selector.value:x}\b",
                      fixed_text, re.M), "fixed vector lost selector")
    cold_text = disassembly(elf, cold.name)
    all_text = run(str(LLVM / "llvm-objdump"), "-d", str(elf)).lower()
    require(len(re.findall(rf"^\s*[0-9a-f]+:.*jsr\s+\${helper.value:x}\b",
                           cold_text, re.M)) == 5
            and len(re.findall(rf"^\s*[0-9a-f]+:.*jsr\s+\${helper.value:x}\b",
                               all_text, re.M)) == 5,
            "cold helper caller identity drift")
    manifest = load(manifest_path)
    rows = sorted(manifest["slices"], key=lambda row: row["file_offset"])
    row = next(item for item in rows if item["section"] == cold.name)
    following = rows[rows.index(row) + 1]
    allocation = following["file_offset"] - row["file_offset"]
    require(row["file_size"] == 1246 and allocation == 1280
            and manifest["storage"]["size"] == 65423,
            "local-return card grew packed image")
    kernal = load(elf.parent / "kernal-freedom-link.json")
    ownership = kernal["control_flow_ownership"]
    require(ownership["violations"] == [],
            "actual linked KERNAL-freedom consumer is not green")
    value = {
        "status": "PASS: local non-entries and emitted identities linked",
        "ordinary": {"reserve_bytes": reserve,
                     "text_end_exclusive": f"0x{text.address + text.bytes:04x}"},
        "reader": {"address": f"0x{reader.value:04x}", "bytes": reader.bytes},
        "selector": {"address": f"0x{selector.value:04x}",
            "bytes": selector.bytes, "fixed_vector": "0xb5eb",
            "identity_depends_on_global_return_label": False,
            "real_call_identities": identities},
        "return_labels": {"global_non_entries": 0,
                          "symbol_names_present": []},
        "ownership": ownership,
        "cold_displacement": {"bytes": helper.bytes,
            "section_bytes": cold.bytes, "packed_page_bytes": allocation,
            "aggregate_bytes": manifest["storage"]["size"],
            "aggregate_growth_bytes": 0},
        "fixed_block_delta_bytes": 0, "E000_delta_bytes": 0,
        "contracted_margins_used_as_freight": False,
    }
    validate_linked(value)
    return value


def linked_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "promote-non-entry-to-global": lambda x: x["return_labels"].update(
            global_non_entries=1),
        "derive-identity-from-global-label": lambda x: x["selector"].update(
            identity_depends_on_global_return_label=True),
        "accept-wrong-selector-operands": lambda x: x["selector"][
            "real_call_identities"].update(selector_operands_match=False),
        "lose-resident-reserve": lambda x: x["ordinary"].update(
            reserve_bytes=0),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate_linked(candidate)
        except LocalIdentityError:
            rejected.append(name)
    require(rejected == list(cases), "linked local-return mutation survived")
    return rejected


def produce_child() -> int:
    configure()
    return PREV.produce_child()


def scope_child() -> int:
    configure()
    return PREV.scope_child()


def acceptance_child() -> int:
    configure()
    return PREV.acceptance_child()


def run_child(action: str) -> None:
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"fresh local-return child {action} red:\n{result.stdout}")


def card() -> None:
    value = load(PREFLIGHT_RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate_preflight(value)
    require(rejected == {"local_identity": source_mutations(),
                         "card_contract": preflight_mutations(value)},
            "local-return preflight mutation receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "local-return replacement card is one-shot")
    INVOCATION.write_bytes(canonical({
        "status": "INVOKED", "link": LINK, "authorization": authorization(),
        "predecessor": bind(PREDECESSOR), "attribution": bind(ATTRIBUTION),
        "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)}))
    run_child("_produce")
    before = frozen_artifacts()
    run_child("_scope")
    run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "local-return acceptance changed artifacts")
    producer = load(PRODUCER_RESULT)
    scope = load(SCOPE_RESULT)
    acceptance = load(ACCEPTANCE_RESULT)
    require(len({os.getpid(), producer["pid"], scope["pid"],
                 acceptance["pid"]}) == 4,
            "local-return process isolation drift")
    linked = producer["v21_text_recovery"]
    require(producer["v21_text_recovery_mutations"] == linked_mutations(linked)
            and producer["candidate_completion_mutations"]
                == ["reject-historical-0xb98a"],
            "local-return linked mutation receipt drift")
    receipt = {
        "format": "lisp65-c2.3-v2.1-local-return-identity-card-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: local-return-identity replacement card green",
        "attempt_accounting": {"replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "authority": {"authorization": authorization(),
            "predecessor_final_red": bind(PREDECESSOR),
            "attribution": bind(ATTRIBUTION), "preflight": bind(PREFLIGHT_RECEIPT),
            "driver": bind(DRIVER)},
        "linked_result": linked,
        "completion_identity": producer["candidate_completion_identity"],
        "artifacts_before": before, "artifacts_after": after,
        "process_isolation": {"parent": os.getpid(), "producer": producer["pid"],
            "owner_scope": scope["pid"], "acceptance": acceptance["pid"],
            "all_distinct": True},
        "owner_scope": scope["gate"],
        "acceptance": {key: item for key, item in acceptance.items()
                       if key not in ("status", "pid")},
        "mutations_rejected": {"preflight": rejected,
            "linked": producer["v21_text_recovery_mutations"],
            "completion": producer["candidate_completion_mutations"]},
        "next": "same-world media closure, then D1",
        "claim_limit": "One replacement card; media and device have not run.",
    }
    RECEIPT.write_bytes(canonical(receipt))
    print("2.1 local return identity: CARD PASS card=1/1 reserve=24 "
          "labels=local ownership=green")


def record_final_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in artifact_paths().items()
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v2.1-local-return-identity-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: local-return-identity card returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {"replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1,
            "WPLTO_runs": 1 if artifacts else 0,
            "product_link_attempts": 1 if artifacts else 0,
            "media_builds": 0, "device_contacts": 0},
        "artifacts": artifacts, "retry_authorized": False,
        "owner_disposition_required": True,
        "authority": {"authorization": authorization(),
            "predecessor_final_red": bind(PREDECESSOR),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
    }))


def check() -> None:
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value.get("retry_authorized") is False
                and value.get("owner_disposition_required") is True,
                "local-return Final Red drift")
        print("2.1 local return identity: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        if PREFLIGHT_RECEIPT.exists():
            value = load(PREFLIGHT_RECEIPT)
            rejected = value.pop("mutations_rejected")
            validate_preflight(value)
            require(rejected == {"local_identity": source_mutations(),
                                 "card_contract": preflight_mutations(value)},
                    "local-return preflight receipt drift")
        print("2.1 local return identity: CHECK ARMED")
        return
    value = load(RECEIPT)
    require(value.get("status")
                == "PASS: local-return-identity replacement card green"
            and value["attempt_accounting"]["replacement_cards_consumed"] == 1
            and value["artifacts_before"] == frozen_artifacts()
            and value["artifacts_after"] == value["artifacts_before"],
            "local-return green receipt drift")
    validate_linked(value["linked_result"])
    print("2.1 local return identity: CHECK PASS card=1/1 reserve=24")


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
                print(f"local-return Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"2.1 local return identity: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
