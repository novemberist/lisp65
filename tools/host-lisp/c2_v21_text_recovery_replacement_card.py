#!/usr/bin/env python3
"""Run the one approved replacement for the 2.1 text-recovery card."""

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
from typing import Any, Callable, Mapping


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v21_text_recovery_card as BASE  # noqa: E402
import c2_v21_text_recovery_pricing as PRICE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
BUILD = ROOT / "build/c2.3/v2.1-text-recovery-replacement-card"
PREFLIGHT = ROOT / "build/c2.3/v2.1-text-recovery-replacement-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
RECEIPT = ARCH / "c2.3-v2.1-text-recovery-replacement-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v2.1-text-recovery-replacement-card-final-red.json"
PREDECESSOR = ARCH / "c2.3-v2.1-text-recovery-card-final-red.json"
ATTRIBUTION = ARCH / (
    "c2.3-v2.1-text-recovery-card-red-attribution-receipt.json")
READER = ROOT / "src/optional/c2_map_cpu_read.s"
DRIVER = Path(__file__).resolve()
LLVM = ROOT / "tools/llvm-mos/bin"
AUTHORIZATION = "421468b1"
RECORDED_ON = "2026-08-14"
LINK = 107

_GENERIC_PATCH = PRODUCT.patch_verifier_binding_table
_GENERIC_TOTAL = PRODUCT.total_publish_last_gate


class ReplacementError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplacementError(message)


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
            "completion expectation derives from the candidate",
            "actually emitted",
            "one replacement card",
            "building-heap receipt binding current sources gets its loud"):
        require(token in text, f"replacement authorization token absent: {token}")
    return authority


def predecessor() -> tuple[dict[str, Any], dict[str, Any]]:
    red = load(PREDECESSOR)
    attribution = load(ATTRIBUTION)
    require(
        red.get("status") == "FINAL RED: 2.1 text-recovery card returns to owner"
        and red.get("retry_authorized") is False
        and attribution.get("status")
            == "ATTRIBUTED FINAL RED: completion pin plus real-consumer selector mismatch"
        and attribution["first_stopper"]["current_ownership_contract"] == "0xb98c"
        and attribution["independent_linked_red"]["calls"][0][
            "mismatch_bytes"] == 1
        and attribution["independent_linked_red"]["calls"][1][
            "mismatch_bytes"] == 2,
        "text-recovery Final Red authority drift")
    return red, attribution


def candidate_verifier_binding(target: Path) -> dict[str, Any]:
    """Derive publish-last identity from the candidate being completed."""
    elf = Path(str(target) + ".elf")
    section = PRODUCT.section_table(elf).get(
        PRODUCT.VERIFIER_BINDING_SECTION)
    require(section is not None
            and section["bytes"] == PRODUCT.runtime_binding_bytes(),
            "candidate verifier-binding section geometry red")
    return {"section": PRODUCT.VERIFIER_BINDING_SECTION,
            "address": int(section["address"]),
            "bytes": int(section["bytes"]), "ELF": bind(elf)}


def candidate_patch(*args: Any, **kwargs: Any) -> dict[str, object]:
    target = Path(args[1] if len(args) > 1 else kwargs["target"])
    expected = candidate_verifier_binding(target)
    kwargs["expected_base"] = expected["address"]
    PRODUCT.VERIFIER_BINDING_BASE = expected["address"]
    PRODUCT.LINK60_VERIFIER_BINDING_BASE = expected["address"]
    result = _GENERIC_PATCH(*args, **kwargs)
    require(result["address"] == result["expected_address"]
            == expected["address"],
            "publish-last did not consume candidate-derived identity")
    return result


def candidate_total(*args: Any, **kwargs: Any) -> dict[str, object]:
    target = Path(args[1] if len(args) > 1 else kwargs["target"])
    expected = candidate_verifier_binding(target)
    kwargs["expected_verifier_base"] = expected["address"]
    return _GENERIC_TOTAL(*args, **kwargs)


def configure() -> None:
    BASE.BUILD = BUILD
    BASE.PREFLIGHT = PREFLIGHT
    BASE.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT
    BASE.INVOCATION = INVOCATION
    BASE.PRODUCER_RESULT = PRODUCER_RESULT
    BASE.SCOPE_RESULT = SCOPE_RESULT
    BASE.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    BASE.RECEIPT = BUILD / "unused-text-recovery-receipt.json"
    BASE.FINAL_RED = BUILD / "unused-text-recovery-final-red.json"
    BASE.LINK = LINK
    BASE.configure()
    BASE.linked_gate = linked_gate
    BASE.linked_mutations = linked_mutations
    PRODUCT.patch_verifier_binding_table = candidate_patch
    PRODUCT.total_publish_last_gate = candidate_total


def artifact_paths() -> dict[str, Path]:
    configure()
    return BASE.artifact_paths()


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    result = {name: bind(path) for name, path in artifact_paths().items()}
    result["seed_lto"] = bind(BUILD / "wplto/resident-island-seed.prg.lto.o")
    return result


def completion_source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = DRIVER.read_text(encoding="utf-8") if source_override is None else source_override
    require(
        'expected = candidate_verifier_binding(target)' in source
        and 'kwargs["expected_base"] = expected["address"]' in source
        and 'kwargs["expected_verifier_base"] = expected["address"]' in source
        and 'PRODUCT.section_table(elf)' in source
        and 'PRODUCT.VERIFIER_BINDING_SECTION' in source,
        "completion identity is not derived from the actual candidate ELF")
    bodies = source[source.index("def candidate_patch"):
                    source.index("def configure")]
    require("0xB98A" not in bodies and "0xb98a" not in bodies,
            "completion adapter retains a historical address pin")
    return {"status": "PASS: completion identity derives from candidate ELF",
            "section": PRODUCT.VERIFIER_BINDING_SECTION,
            "historical_pin_consumed": False}


def selector_source_gate(reader_override: str | None = None) -> dict[str, Any]:
    reader = READER.read_text(encoding="utf-8") if reader_override is None else reader_override
    legacy_view = reader.replace(
        "c2_stream_c2d_read_return-2", "c2_stream_c2d_read_return-1").replace(
        "c2_stream_shelf_read_return-3", "c2_stream_shelf_read_return-1")
    BASE.source_gate(reader_override=legacy_view)
    require(reader.count("c2_stream_c2d_read_return-2") == 2
            and reader.count("c2_stream_shelf_read_return-3") == 2
            and "c2_stream_c2d_read_return-1" not in reader
            and "c2_stream_shelf_read_return-1" not in reader,
            "selector still assumes post-JSR label adjacency")
    reader_bytes, truth = PRICE.assemble(
        reader, ".text.c2_map_cpu_read", "c2_map_cpu_read")
    rows = [row for row in truth.relocations
            if row.source_section == ".text.c2_map_cpu_selector"
            and row.target.startswith("c2_stream_")]
    addends = {(row.target, row.relocation_type): row.addend & 0xFFFFFFFF
               for row in rows}
    require(reader_bytes == 166
            and truth.symbol("c2_map_cpu_selector").bytes == 40
            and addends == {
                ("c2_stream_c2d_read_return", "R_MOS_ADDR16_HI"): 0xFFFFFFFE,
                ("c2_stream_c2d_read_return", "R_MOS_ADDR16_LO"): 0xFFFFFFFE,
                ("c2_stream_shelf_read_return", "R_MOS_ADDR16_HI"): 0xFFFFFFFD,
                ("c2_stream_shelf_read_return", "R_MOS_ADDR16_LO"): 0xFFFFFFFD},
            "selector object addends do not encode real caller gaps")
    return {"status": "PASS: selector addends encode emitted caller tails",
            "reader_bytes": reader_bytes, "selector_bytes": 40,
            "callers": {"c2d": {"tail": "aa", "gap_bytes": 1,
                                   "stack_identity": "return-label-2"},
                        "shelf": {"tail": "8510", "gap_bytes": 2,
                                  "stack_identity": "return-label-3"}}}


def preflight_mutations() -> list[str]:
    reader = READER.read_text(encoding="utf-8")
    driver = DRIVER.read_text(encoding="utf-8")
    cases: dict[str, Callable[[], None]] = {
        "restore-c2d-adjacency": lambda: selector_source_gate(reader.replace(
            "c2_stream_c2d_read_return-2", "c2_stream_c2d_read_return-1")),
        "restore-shelf-adjacency": lambda: selector_source_gate(reader.replace(
            "c2_stream_shelf_read_return-3", "c2_stream_shelf_read_return-1")),
        "restore-historical-completion-pin": lambda: completion_source_gate(
            driver.replace("expected = candidate_verifier_binding(target)",
                           "expected = {'address': 0xB98A}", 1)),
    }
    rejected: list[str] = []
    for name, action in cases.items():
        try:
            action()
        except (ReplacementError, BASE.CardError, PRICE.PricingError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "replacement identity mutation survived")
    return rejected


def preflight_value() -> dict[str, Any]:
    predecessor()
    return {
        "format": "lisp65-c2.3-v2.1-text-recovery-replacement-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: candidate completion and real-caller selector; card armed",
        "configuration": {"link": LINK, "replacement_cards_authorized": 1},
        "attempt_accounting": {"replacement_cards_consumed": 0,
            "WPLTO_runs": 0, "product_links": 0, "media_builds": 0,
            "device_contacts": 0},
        "host_gates": {"completion": completion_source_gate(),
                       "selector": selector_source_gate()},
        "placement_inherited_green": {"resident_reserve_bytes": 24,
            "cold_helper_bytes": 63, "image_growth_bytes": 0},
        "authority": {"authorization": authorization(),
            "predecessor_final_red": bind(PREDECESSOR),
            "attribution": bind(ATTRIBUTION), "driver": bind(DRIVER),
            "reader": bind(READER)},
        "claim_limit": "Host preflight only; no WPLTO, product link, media or device.",
    }


def validate_preflight(value: dict[str, Any]) -> None:
    require(value == preflight_value(), "text-recovery replacement preflight drift")


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "text-recovery replacement is one-shot")
    value = preflight_value()
    validate_preflight(value)
    value["mutations_rejected"] = preflight_mutations()
    PREFLIGHT.mkdir(parents=True)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("2.1 text recovery replacement: PREFLIGHT PASS card=0/1 "
          "completion=candidate selector=real-caller mutations=3")


def disassembly(elf: Path, section: str) -> str:
    return run(str(LLVM / "llvm-objdump"), "-d", f"--section={section}", str(elf))


def _actual_call_identity(truth: ElfTruth, label_name: str,
                          vector: int, tail: bytes) -> dict[str, Any]:
    label = truth.symbol(label_name)
    section = truth.section(label.section)
    raw = truth.section_bytes(label.section)
    pattern = bytes((0x20, vector & 0xFF, vector >> 8)) + tail
    start = label.value - section.address - len(pattern)
    require(start >= 0 and raw[start:start + len(pattern)] == pattern,
            f"real WPLTO call/tail bytes drift: {label_name}")
    call = label.value - len(pattern)
    pushed = call + 2
    return {"label": f"0x{label.value:04x}", "call": f"0x{call:04x}",
            "emitted_bytes": pattern.hex(), "tail_bytes": tail.hex(),
            "gap_bytes": len(tail), "stack_identity": f"0x{pushed:04x}",
            "label_minus": label.value - pushed}


def validate_real_identities(value: dict[str, Any]) -> None:
    require(value["c2d"]["emitted_bytes"].endswith("aa")
            and value["c2d"]["gap_bytes"] == 1
            and value["c2d"]["label_minus"] == 2
            and value["shelf"]["emitted_bytes"].endswith("8510")
            and value["shelf"]["gap_bytes"] == 2
            and value["shelf"]["label_minus"] == 3
            and value["selector_operands_match"] is True,
            "real linked selector identities drift")


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
    require(reader.section == ".text" and reader.bytes == 166
            and selector.section == ".text" and selector.bytes == 40
            and helper.section == cold.name and helper.bytes == 63
            and cold.bytes == 1246 and reserve == 24
            and fixed.address == 0xB5C4 and fixed.bytes == 48
            and vector.value == 0xB5EB
            and shelf.bytes == 194 and c2d.bytes == 85,
            "replacement changed the green placement/capacity identity")

    identities = {
        "c2d": _actual_call_identity(
            truth, "c2_stream_c2d_read_return", vector.value, bytes.fromhex("aa")),
        "shelf": _actual_call_identity(
            truth, "c2_stream_shelf_read_return", vector.value, bytes.fromhex("8510")),
    }
    selector_section = truth.section(selector.section)
    selector_raw = truth.section_bytes(selector.section)[
        selector.value - selector_section.address:
        selector.value - selector_section.address + selector.bytes]
    c2d_stack = int(identities["c2d"]["stack_identity"], 16)
    shelf_stack = int(identities["shelf"]["stack_identity"], 16)
    require(selector_raw[7] == c2d_stack >> 8
            and selector_raw[14] == (c2d_stack & 0xFF)
            and selector_raw[20] == shelf_stack >> 8
            and selector_raw[27] == (shelf_stack & 0xFF),
            "linked selector operands do not equal emitted call identities")
    identities["selector_operands_match"] = True
    validate_real_identities(identities)

    e000 = disassembly(elf, ".lisp65_c2_kernal_window.c2_resident").lower()
    require(len(re.findall(r"\b(?:jsr|jmp)\s+\$2277\b", e000)) == 0,
            "E000 still bypasses fixed facade for CPU reader")
    fixed_text = disassembly(elf, ".lisp65_c2_host_facade").lower()
    require(re.search(rf"^\s*b5eb:.*jmp\s+\${selector.value:x}\b",
                      fixed_text, re.M),
            "runtime-overlay fixed vector lost the selector")

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
        "status": "PASS: green placement plus real-emitted selector identities",
        "ordinary": {"text_end_exclusive": f"0x{text.address + text.bytes:04x}",
                     "facade_start": f"0x{facade.address:04x}",
                     "reserve_bytes": reserve, "net_delta_bytes": -23},
        "reader": {"address": f"0x{reader.value:04x}", "bytes": reader.bytes},
        "selector": {"address": f"0x{selector.value:04x}",
                     "bytes": selector.bytes, "fixed_vector": "0xb5eb",
                     "real_call_identities": identities},
        "cold_displacement": {"symbol": helper.name, "bytes": helper.bytes,
            "section": cold.name, "section_bytes": cold.bytes,
            "linked_calls": len(all_calls), "packed_page_bytes": allocation,
            "packed_padding_bytes": allocation - row["file_size"],
            "aggregate_bytes": manifest["storage"]["size"],
            "aggregate_growth_bytes": 0},
        "fixed_block_delta_bytes": 0, "E000_delta_bytes": 0,
        "contracted_margins_used_as_freight": False,
    }


def linked_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "assume-c2d-adjacency": lambda x: x["selector"][
            "real_call_identities"]["c2d"].update(gap_bytes=0, label_minus=1),
        "assume-shelf-adjacency": lambda x: x["selector"][
            "real_call_identities"]["shelf"].update(gap_bytes=0, label_minus=1),
        "accept-wrong-operands": lambda x: x["selector"][
            "real_call_identities"].update(selector_operands_match=False),
        "lose-reserve": lambda x: x["ordinary"].update(reserve_bytes=0),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            require(candidate["ordinary"]["reserve_bytes"] == 24,
                    "resident reserve mutation")
            validate_real_identities(candidate["selector"]["real_call_identities"])
        except ReplacementError:
            rejected.append(name)
    require(rejected == list(cases), "linked replacement mutation survived")
    return rejected


def completion_gate(elf: Path) -> dict[str, Any]:
    candidate = candidate_verifier_binding(Path(str(elf)[:-4]))
    report = load(elf.parent / "runtime-verifier-publish-last.json")
    require(report["status"] == "passed"
            and report["address"] == report["expected_address"]
                == candidate["address"]
            and report["bytes"] == candidate["bytes"],
            "completed candidate did not consume its own binding identity")
    return {"status": "PASS: publish-last consumed candidate identity",
            "section": candidate["section"], "address": candidate["address"],
            "bytes": candidate["bytes"], "historical_0xb98a_consumed": False}


def postlink_artifacts(paths: Mapping[str, Path]) -> tuple[Path]:
    """Resolve this wrapper's inputs through the typed producer vocabulary."""
    return (paths["elf"],)


def produce_child() -> int:
    configure()
    result = BASE.produce_child()
    paths = artifact_paths()
    (elf,) = postlink_artifacts(paths)
    product = load(PRODUCER_RESULT)
    product["candidate_completion_identity"] = completion_gate(elf)
    product["candidate_completion_mutations"] = ["reject-historical-0xb98a"]
    PRODUCER_RESULT.write_bytes(canonical(product))
    return result


def scope_child() -> int:
    configure()
    return BASE.scope_child()


def acceptance_child() -> int:
    configure()
    return BASE.acceptance_child()


def run_child(action: str) -> None:
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"fresh text-recovery replacement child {action} red:\n{result.stdout}")


def card() -> None:
    value = load(PREFLIGHT_RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate_preflight(value)
    require(rejected == preflight_mutations(),
            "replacement preflight mutation receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "text-recovery replacement card is one-shot")
    INVOCATION.write_bytes(canonical({
        "status": "INVOKED", "link": LINK, "authorization": authorization(),
        "predecessor": bind(PREDECESSOR), "attribution": bind(ATTRIBUTION),
        "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)}))
    run_child("_produce")
    before = frozen_artifacts()
    run_child("_scope")
    run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "replacement acceptance changed linked artifacts")
    producer = load(PRODUCER_RESULT)
    scope = load(SCOPE_RESULT)
    acceptance = load(ACCEPTANCE_RESULT)
    require(len({os.getpid(), producer["pid"], scope["pid"],
                 acceptance["pid"]}) == 4,
            "replacement card process isolation drift")
    linked = producer["v21_text_recovery"]
    require(producer["v21_text_recovery_mutations"] == linked_mutations(linked)
            and producer["candidate_completion_mutations"]
                == ["reject-historical-0xb98a"],
            "replacement linked mutation receipt drift")
    receipt = {
        "format": "lisp65-c2.3-v2.1-text-recovery-replacement-card-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: text-recovery replacement card green",
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
        "process_isolation": {"parent": os.getpid(),
            "producer": producer["pid"], "owner_scope": scope["pid"],
            "acceptance": acceptance["pid"], "all_distinct": True},
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
    print("2.1 text recovery replacement: CARD PASS card=1/1 reserve=24 "
          "completion=candidate selector=real-caller")


def record_final_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in artifact_paths().items()
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v2.1-text-recovery-replacement-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: text-recovery replacement returns to owner",
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
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)}}))


def check() -> None:
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value.get("retry_authorized") is False
                and value.get("owner_disposition_required") is True,
                "replacement Final Red drift")
        print("2.1 text recovery replacement: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        if PREFLIGHT_RECEIPT.exists():
            value = load(PREFLIGHT_RECEIPT)
            rejected = value.pop("mutations_rejected")
            validate_preflight(value)
            require(rejected == preflight_mutations(), "preflight receipt drift")
        print("2.1 text recovery replacement: CHECK ARMED")
        return
    value = load(RECEIPT)
    require(value.get("status") == "PASS: text-recovery replacement card green"
            and value["attempt_accounting"]["replacement_cards_consumed"] == 1
            and value["artifacts_before"] == frozen_artifacts()
            and value["artifacts_after"] == value["artifacts_before"]
            and value["linked_result"]["ordinary"]["reserve_bytes"] == 24
            and value["completion_identity"]["historical_0xb98a_consumed"] is False,
            "replacement green receipt drift")
    print("2.1 text recovery replacement: CHECK PASS card=1/1 reserve=24")


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
                print(f"replacement Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"2.1 text recovery replacement: FINAL RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
