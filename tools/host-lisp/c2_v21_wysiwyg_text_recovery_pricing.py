#!/usr/bin/env python3
"""Price and bind the authorized Link-115 ordinary-text recovery.

The selected micro form preserves the complete WYSIWYG boundary while
folding the two PETSCII control ranges through bit 7.  The cold alternative
is priced against a real same-slice caller closure, not a hypothetical move.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
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
import c2_v21_root_padding_configurator_projection_replacement as CONFIG  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
REPL = ROOT / "src/repl.c"
FINAL_RED = ARCH / "c2.3-v2.1-wysiwyg-input-card-final-red.json"
ATTRIBUTION = ARCH / (
    "c2.3-v2.1-wysiwyg-input-card-red-attribution-receipt.json")
WYSIWYG = ARCH / "c2.3-v2.1-wysiwyg-input-receipt.json"
PRIOR_ELF = ROOT / (
    "build/c2.3/v2.1-root-padding-configurator-parity-continuation/final/"
    "lisp65-c2-substitution-linked.prg.elf")
PACKED = ROOT / (
    "build/c2.3/v2.1-root-padding-configurator-parity-continuation/final/"
    "runtime-overlays-session-final.json")
RECEIPT = ARCH / "c2.3-v2.1-wysiwyg-text-recovery-pricing-receipt.json"
LLVM = ROOT / "tools/llvm-mos/bin"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "eb688c60"
BASELINE_COMMIT = "f51712ac"
RECORDED_ON = "2026-08-17"
FORMAT = "lisp65-c2.3-v2.1-wysiwyg-text-recovery-pricing-v1"
STATUS = "PRICED: 42-BYTE SEMANTIC MICRO-RECOVERY WINS"


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": digest(raw)}


def run(*argv: str) -> str:
    return subprocess.run(argv, cwd=ROOT, check=True, text=True,
                          stdout=subprocess.PIPE).stdout


def git_blob(commit: str, path: Path) -> tuple[bytes, dict[str, Any]]:
    full = run("git", "rev-parse", f"{commit}^{{commit}}").strip()
    name = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{full}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    return raw, {"authority": "git-blob", "commit": full, "path": name,
                 "bytes": len(raw), "sha256": digest(raw)}


def authorization() -> dict[str, Any]:
    raw, authority = git_blob(AUTHORIZATION, PLAN)
    text = " ".join(raw.decode().lower().split())
    for token in (
            "text-recovery pricing ii", "at least 13 ordinary-text bytes",
            "contracted cold relocation", "winner by price",
            "margins stay non-budgets", "one replacement card"):
        require(token in text, f"pricing authorization token absent: {token}")
    return authority


def boundary(value: int, room: bool, optimized: bool) -> tuple[str, int | None]:
    """Visible outcome after the already-handled editing-key branches."""
    if optimized:
        if (value & 0x7F) < 0x20:
            return "visible-reader-error", None
        if room:
            return "echo-and-store", 0x20 if value == 0xA0 else value
        return "buffer-full", None
    if value == 0xA0:
        value = 0x20
    elif value < 0x20 or 0x80 <= value < 0xA0:
        return "visible-reader-error", None
    return (("echo-and-store", value) if room else ("buffer-full", None))


def semantic_table() -> dict[str, Any]:
    rows = []
    for room in (False, True):
        for value in range(256):
            before = boundary(value, room, False)
            after = boundary(value, room, True)
            require(before == after,
                    f"input-boundary semantic drift at {value:#04x}/{room}")
            rows.append((room, value, before))
    rejected = [value for value in range(256)
                if boundary(value, True, True)[0] == "visible-reader-error"]
    require(rejected == [*range(0x20), *range(0x80, 0xA0)]
            and boundary(0xA0, True, True) == ("echo-and-store", 0x20),
            "optimized control/A0 truth table drift")
    return {
        "cases": len(rows), "room_states": 2, "byte_values": 256,
        "mismatches": 0, "visible_rejection_bytes": len(rejected),
        "visible_rejection_ranges": ["0x00..0x1f", "0x80..0x9f"],
        "a0_result": "0x20", "buffer_full_external_delta": 0,
    }


def source_gate(source: str) -> dict[str, Any]:
    for token in (
            "if ((c & 0x7F) < 0x20) {",
            "lisp_abort_code(LISP65_ERR_READER_INVALID_TOKEN);",
            "} else if (n < max - 1) {",
            "if (c == 0xA0) c = ' ';",
            "echo_char((char)c);", "buf[n++] = (char)c;"):
        require(token in source, f"selected micro source seam absent: {token}")
    require(source.index("if ((c & 0x7F) < 0x20) {")
            < source.index("lisp_abort_code(LISP65_ERR_READER_INVALID_TOKEN);")
            < source.index("} else if (n < max - 1) {")
            < source.index("if (c == 0xA0) c = ' ';")
            < source.index("echo_char((char)c);")
            < source.index("buf[n++] = (char)c;"),
            "selected micro no longer rejects/normalizes before echo/store")
    return {
        "control_classifier": "(c & 0x7f) < 0x20",
        "visible_error_preserved": True,
        "a0_normalization_preserved": True,
        "facade_changed": False, "placement_contract_changed": False,
        "checks_removed": 0,
    }


def compile_repl(source: bytes, prefix: list[str], directory: Path,
                 name: str) -> dict[str, Any]:
    target = directory / f"{name}.o"
    completed = subprocess.run(
        [*prefix, "-fno-lto", "-c", "-x", "c", "-", "-o", str(target)],
        cwd=ROOT, input=source, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    require(completed.returncode == 0 and target.is_file(),
            f"configured target compile red ({name}):\n"
            + completed.stdout.decode(errors="replace"))
    symbols = run(str(LLVM / "llvm-nm"), "--print-size", "--size-sort",
                  str(target))
    match = re.search(r"^\S+\s+([0-9a-fA-F]+)\s+[Tt]\s+repl$",
                      symbols, re.MULTILINE)
    require(match is not None, f"compiled repl symbol absent: {name}")
    return {"source_bytes": len(source), "source_sha256": digest(source),
            "object_bytes": target.stat().st_size,
            "repl_symbol_bytes": int(match.group(1), 16),
            "compiler_exit_status": 0}


def micro_price() -> dict[str, Any]:
    baseline, baseline_binding = git_blob(BASELINE_COMMIT, REPL)
    candidate = REPL.read_bytes()
    _old, projection = CONFIG.configure_projected_candidate()
    prefix, static = CONFIG.configured_compile_prefix(projection)
    with tempfile.TemporaryDirectory(prefix="c2-v21-wysiwyg-price-") as raw:
        directory = Path(raw)
        before = compile_repl(baseline, prefix, directory, "before")
        after = compile_repl(candidate, prefix, directory, "after")
    recovered = before["repl_symbol_bytes"] - after["repl_symbol_bytes"]
    require(before["repl_symbol_bytes"] == 654
            and after["repl_symbol_bytes"] == 612 and recovered == 42
            and len(projection["final_state"]["compiler_definitions"]) == 73
            and static["consumed_value"] == 46043,
            "configured micro price drift")
    return {
        "status": "WINNER: semantic instruction selection",
        "baseline_source": baseline_binding, "before_compile": before,
        "candidate_source": bind(REPL), "after_compile": after,
        "configured_definition_count": 73,
        "candidate_static_header_bytes_consumed": 46043,
        "resident_bytes_recovered_nolto": recovered,
        "required_final_recovery_bytes": 13,
        "projected_final_headroom_bytes": recovered - 13,
        "new_sections": 0, "new_slots": 0, "image_growth_bytes": 0,
        "placement_contract_changes": 0, "checks_removed": 0,
        "semantic_equivalence": semantic_table(),
        "source_contract": source_gate(candidate.decode()),
        "claim_limit": (
            "Configured per-TU target price; the replacement card alone decides "
            "the final WPLTO size and facade headroom."),
    }


def cold_price() -> dict[str, Any]:
    truth = ElfTruth.read(PRIOR_ELF, llvm_readobj=LLVM / "llvm-readobj")
    helper = truth.symbol("v2_child_value")
    section = truth.section(".lisp65_rt_c2append_rollback_wipe_plane")
    disassembly = run(str(LLVM / "llvm-objdump"), "-d", str(PRIOR_ELF))
    calls = [int(item, 16) for item in re.findall(
        rf"^\s*([0-9a-fA-F]+):.*jsr\s+\${helper.value:x}\b",
        disassembly, re.MULTILINE)]
    packed = load(PACKED)
    rows = sorted(packed["slices"], key=lambda row: row["file_offset"])
    row = next(item for item in rows if item["section"] == section.name)
    index = rows.index(row)
    allocated = rows[index + 1]["file_offset"] - row["file_offset"]
    projected = section.bytes + helper.bytes
    projected_allocated = (projected + 255) & ~255
    require(helper.section == ".text" and helper.bytes == 374
            and calls == [0xC668, 0xC6A8]
            and all(section.address <= site < section.address + section.bytes
                    for site in calls)
            and section.bytes == row["file_size"] == 954
            and allocated == 1024 and projected == 1328
            and projected_allocated == 1536
            and packed["policy"]["max_slice_bytes"] == 1792,
            "cold-relocation price drift")
    return {
        "status": "VALID BUT HIGHER-PRICE: contracted cold relocation",
        "routine": "v2_child_value", "ordinary_bytes_recovered": helper.bytes,
        "callers": [f"0x{site:04x}" for site in calls],
        "all_callers_in_destination": True, "outside_callers": 0,
        "destination": section.name,
        "destination_before_bytes": section.bytes,
        "destination_after_bytes": projected,
        "slice_capacity_bytes": packed["policy"]["max_slice_bytes"],
        "allocated_before_bytes": allocated,
        "allocated_after_bytes": projected_allocated,
        "aggregate_image_growth_bytes": projected_allocated - allocated,
        "new_slots": 0, "placement_contract_changes": 1,
        "risk": (
            "Valid same-slice cold closure, but it changes placement authority "
            "and grows the packed image by one 512-byte page span."),
    }


def derive() -> dict[str, Any]:
    red, attribution, wysiwyg = load(FINAL_RED), load(ATTRIBUTION), load(WYSIWYG)
    require(red["status"] == "FINAL RED: WYSIWYG card returns to owner"
            and red["retry_authorized"] is False
            and attribution["capacity"]["ordinary_text_deficit_bytes"] == 13
            and wysiwyg["status"].startswith("PASS: A0-TO-SPACE"),
            "WYSIWYG Final-Red/preflight authority drift")
    micro, cold = micro_price(), cold_price()
    require(micro["resident_bytes_recovered_nolto"] >= 13
            and micro["image_growth_bytes"] == 0
            and micro["placement_contract_changes"] == 0
            and cold["aggregate_image_growth_bytes"] == 512
            and cold["placement_contract_changes"] == 1,
            "winner comparison drift")
    value = {
        "format": FORMAT, "recorded_on": RECORDED_ON, "status": STATUS,
        "baseline": {
            "failed_card_repl_growth_bytes": 17,
            "prior_ordinary_headroom_bytes": 4,
            "minimum_recovery_bytes": 13,
            "mapped_far_facade_fixed": True,
            "contracted_margins_used_as_freight": False,
        },
        "option_a_micro": micro, "option_b_cold_relocation": cold,
        "decision": {
            "winner": "option-a-semantic-instruction-selection",
            "why": (
                "It clears the 13-byte stop by 29 projected bytes with no new "
                "section, slot, packed bytes, or placement contract. The best "
                "demonstrable cold alternative is valid but grows the packed "
                "image by 512 bytes and changes placement authority."),
            "replacement_cards_authorized": 1,
            "replacement_cards_consumed": 0,
            "completion_allowed_before_card_green": False,
            "media_allowed_before_card_green": False,
            "device_allowed_before_card_green": False,
        },
        "authority": {
            "owner": authorization(), "Final_Red": bind(FINAL_RED),
            "attribution": bind(ATTRIBUTION), "WYSIWYG": bind(WYSIWYG),
            "prior_ELF": bind(PRIOR_ELF), "packed_manifest": bind(PACKED),
            "repl": bind(REPL), "checker": bind(DRIVER),
        },
        "claim_limit": (
            "Host pricing and winner selection only. No WPLTO, product link, "
            "replacement card, Completion, media, device, or D2 claim."),
    }
    validate(value)
    return value


def validate(value: dict[str, Any]) -> None:
    require(value["format"] == FORMAT and value["status"] == STATUS,
            "pricing identity drift")
    baseline = value["baseline"]
    micro, cold, decision = (value["option_a_micro"],
                             value["option_b_cold_relocation"],
                             value["decision"])
    require(baseline["minimum_recovery_bytes"] == 13
            and baseline["mapped_far_facade_fixed"] is True
            and baseline["contracted_margins_used_as_freight"] is False,
            "capacity walls drift")
    require(micro["resident_bytes_recovered_nolto"] == 42
            and micro["projected_final_headroom_bytes"] == 29
            and micro["new_sections"] == micro["new_slots"]
                == micro["image_growth_bytes"]
                == micro["placement_contract_changes"]
                == micro["checks_removed"] == 0
            and micro["semantic_equivalence"]["cases"] == 512
            and micro["semantic_equivalence"]["mismatches"] == 0
            and micro["semantic_equivalence"]["visible_rejection_bytes"] == 64
            and micro["source_contract"]["visible_error_preserved"] is True
            and micro["source_contract"]["a0_normalization_preserved"] is True,
            "micro-recovery contract drift")
    require(cold["routine"] == "v2_child_value"
            and cold["ordinary_bytes_recovered"] == 374
            and cold["all_callers_in_destination"] is True
            and cold["outside_callers"] == 0
            and cold["aggregate_image_growth_bytes"] == 512
            and cold["placement_contract_changes"] == 1,
            "cold-relocation price drift")
    require(decision["winner"] == "option-a-semantic-instruction-selection"
            and decision["replacement_cards_authorized"] == 1
            and decision["replacement_cards_consumed"] == 0
            and decision["completion_allowed_before_card_green"] is False
            and decision["media_allowed_before_card_green"] is False
            and decision["device_allowed_before_card_green"] is False,
            "winner/card boundary drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "recover-twelve": lambda x: x["option_a_micro"].update(
            resident_bytes_recovered_nolto=12),
        "project-headroom-zero": lambda x: x["option_a_micro"].update(
            projected_final_headroom_bytes=0),
        "remove-check": lambda x: x["option_a_micro"].update(checks_removed=1),
        "weaken-visible-error": lambda x: x["option_a_micro"][
            "source_contract"].update(visible_error_preserved=False),
        "drop-a0-normalization": lambda x: x["option_a_micro"][
            "source_contract"].update(a0_normalization_preserved=False),
        "semantic-mismatch": lambda x: x["option_a_micro"][
            "semantic_equivalence"].update(mismatches=1),
        "miss-control": lambda x: x["option_a_micro"][
            "semantic_equivalence"].update(visible_rejection_bytes=63),
        "move-facade": lambda x: x["baseline"].update(
            mapped_far_facade_fixed=False),
        "spend-margin": lambda x: x["baseline"].update(
            contracted_margins_used_as_freight=True),
        "hide-cold-image-growth": lambda x: x[
            "option_b_cold_relocation"].update(aggregate_image_growth_bytes=0),
        "hide-cold-contract": lambda x: x[
            "option_b_cold_relocation"].update(placement_contract_changes=0),
        "choose-cold": lambda x: x["decision"].update(
            winner="option-b-cold-relocation"),
        "authorize-two": lambda x: x["decision"].update(
            replacement_cards_authorized=2),
        "consume-card-in-pricing": lambda x: x["decision"].update(
            replacement_cards_consumed=1),
        "open-completion": lambda x: x["decision"].update(
            completion_allowed_before_card_green=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except PricingError:
            rejected.append(name)
    require(rejected == list(cases), "text-recovery pricing mutation survived")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check", "selftest"))
    action = parser.parse_args().action
    value = derive()
    value["mutations_rejected"] = mutations(value)
    if action == "record":
        RECEIPT.write_bytes(canonical(value))
    elif action == "check":
        require(load(RECEIPT) == value, "text-recovery pricing receipt stale")
    else:
        require(len(value["mutations_rejected"]) == 15,
                "mutation count drift")
    print("WYSIWYG text recovery: PASS "
          f"action={action} micro=42 cold=374 image-delta=512 mutations=15")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PricingError, OSError, ValueError, KeyError,
            UnicodeDecodeError, json.JSONDecodeError,
            subprocess.CalledProcessError) as error:
        print(f"WYSIWYG text recovery: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
