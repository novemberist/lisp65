#!/usr/bin/env python3
"""Bind whether reopen_gap0 has a fixed-address dependent.

The v2.1 post-link schema replacement card differs from the reviewed VMA
golden only because ``c2_resident`` shrank by one byte and the linker-defined
successor ``reopen_gap0`` followed it.  This desk gate distinguishes users of
the section's *symbol identity* from users of its numeric start address.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
GOLDEN = ROOT / (
    "tests/bytecode/dialect-v2/golden-layout/"
    "c2-full-map-owned-vma-invariants-v3.json")
FINAL_RED = ARCH / "c2.3-v2.1-postlink-schema-replacement-card-final-red.json"
BUILD = ROOT / "build/c2.3/v2.1-postlink-schema-replacement-card/wplto"
CANDIDATE_ELF = BUILD / "lisp65-c2-substitution-linked.prg.elf"
CANDIDATE_LINKER = BUILD / "c2-substitution.ld"
CANDIDATE_WINDOW = BUILD / "c2-product-kernal-window.bin"
REFERENCE_ELF = ROOT / (
    "build/c2.3/v2.0-source-oracle-replacement3-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
LINKER_SOURCE = ROOT / "tools/host-lisp/c2_product_substitution_link.py"
HISTORICAL_CONTRACT = ROOT / "config/c2-append-final-hybrid-contract.json"
DRIVER = Path(__file__).resolve()
RECEIPT = ARCH / (
    "c2.3-v2.1-reopen-gap-dependency-attribution-receipt.json")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
AUTHORIZATION = "24c83f4b"
RECORDED_ON = "2026-08-14"
FORMAT = "lisp65-c2.3-v2.1-reopen-gap-dependency-attribution-v1"
STATUS = "ATTRIBUTED: reopen_gap0 has no fixed-address dependent"

GAP0 = ".lisp65_c2_kernal_window.reopen_gap0"
GAP1 = ".lisp65_c2_kernal_window.reopen_gap1"
GAP2 = ".lisp65_c2_kernal_window.reopen_gap2"
RESIDENT = ".lisp65_c2_kernal_window.c2_resident"
PROFILE = ".lisp65_c2_kernal_window.profile_rodata"
BEGIN = "vm_runtime_overlay_transaction_begin"


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
            "reopen_gap0: dependency attribution commissioned",
            "who requires `reopen_gap0` at a fixed address",
            "not depended upon",
            "invariants are addresses with dependents",
            "the owner decides on the reclassification"):
        require(token in text, f"dependency authorization absent: {token}")
    return authority


def tracked_text_files() -> list[Path]:
    raw = subprocess.run(
        ["git", "ls-files", "-z", "src", "config", "scripts", "mk",
         "tools/host-lisp"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    suffixes = {".c", ".h", ".s", ".S", ".py", ".json", ".ld", ".mk"}
    files: list[Path] = []
    for item in raw.split(b"\0"):
        if not item:
            continue
        path = ROOT / item.decode()
        if path == DRIVER or path.suffix not in suffixes:
            continue
        files.append(path)
    return sorted(files)


def exact_address_mentions(address: int) -> list[dict[str, Any]]:
    hexdigits = f"{address:x}"
    pattern = re.compile(
        rf"(?i)(?<![0-9a-f])(?:0x|\$){hexdigits}(?![0-9a-f])"
        rf"|(?<![0-9]){address}(?![0-9])")
    hits: list[dict[str, Any]] = []
    for path in tracked_text_files():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, 1):
            if pattern.search(line):
                hits.append({"path": path.relative_to(ROOT).as_posix(),
                             "line": line_number, "text": line.strip()})
    return hits


def section_row(truth: ElfTruth, name: str) -> dict[str, Any]:
    row = truth.section(name)
    return {"name": name, "vma": row.address, "bytes": row.bytes,
            "end_exclusive": row.address + row.bytes}


def caller_for(truth: ElfTruth, section: str, offset: int) -> str:
    matches = [row for row in truth.symbols
               if row.symbol_type == "Function" and row.bytes > 0
               and row.section == section
               and row.value <= offset < row.value + row.bytes]
    require(len(matches) == 1,
            f"relocation caller identity is not unique: {section}/0x{offset:x}")
    return matches[0].name


def symbolic_consumers(truth: ElfTruth, symbol: str) -> list[dict[str, Any]]:
    target = truth.symbol(symbol)
    rows = []
    for relocation in truth.relocations:
        if relocation.target != symbol:
            continue
        identity = truth.relocation_target_identity(relocation)
        require(identity["kind"] == "section-symbol"
                and identity["symbol_value"] == target.value,
                f"non-symbolic dependent found for {symbol}")
        rows.append({
            "caller": caller_for(
                truth, relocation.source_section, relocation.offset),
            "source_section": relocation.source_section,
            "relocation_offset": relocation.offset,
            "relocation_type": relocation.relocation_type,
            "target_kind": identity["kind"],
            "target_symbol": identity["symbol"],
            "resolved_target": identity["resolved_value"],
        })
    return sorted(rows, key=lambda row: row["relocation_offset"])


def linker_contract(text: str) -> dict[str, Any]:
    compact = " ".join(text.split())
    gap0 = (
        f"{GAP0} ADDR({RESIDENT}) + SIZEOF({RESIDENT}) :")
    gap1 = (
        f"{GAP1} ADDR({PROFILE}) + SIZEOF({PROFILE}) :")
    gap2 = f"{GAP2} 0xff90 :"
    require(gap0 in compact and gap1 in compact and gap2 in compact,
            "reopening linker placement relation drift")
    require(
        f"ADDR({GAP0}) - 0xe000" in compact
        and f"ADDR({GAP1}) - 0xe000" in compact
        and "ORIGIN(c2_kernal_window_load) + 0x1f90" in compact,
        "reopening LMA derivation drift")
    return {
        "gap0": {"vma_source": "end-of-c2_resident",
                 "lma_source": "window-origin-plus-candidate-vma-offset",
                 "fixed_numeric_start": False},
        "gap1": {"vma_source": "end-of-profile_rodata",
                 "lma_source": "window-origin-plus-candidate-vma-offset",
                 "fixed_numeric_start": False},
        "gap2": {"vma_source": "explicit-0xff90",
                 "lma_source": "explicit-window-offset-0x1f90",
                 "fixed_numeric_start": True},
    }


def golden_row(name: str) -> dict[str, Any]:
    value = load(GOLDEN)
    matches = [row for row in value["section_invariants"]
               if row["name"] == name]
    require(len(matches) == 1, f"golden section identity drift: {name}")
    return matches[0]


def derive() -> dict[str, Any]:
    red = load(FINAL_RED)
    require(
        red.get("status") ==
            "FINAL RED: post-link schema replacement returns to owner"
        and red.get("retry_authorized") is False
        and red.get("owner_disposition_required") is True
        and red["attempt_accounting"] == {
            "replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1, "WPLTO_runs": 1,
            "product_link_attempts": 1, "media_builds": 0,
            "device_contacts": 0},
        "post-link schema Final Red disposition drift")

    candidate = ElfTruth.read(
        CANDIDATE_ELF, llvm_readobj=READOBJ, include_section_data=True)
    reference = ElfTruth.read(
        REFERENCE_ELF, llvm_readobj=READOBJ, include_section_data=True)
    current = {name: section_row(candidate, name) for name in
               (RESIDENT, GAP0, PROFILE, GAP1, GAP2)}
    prior = {name: section_row(reference, name) for name in
             (RESIDENT, GAP0, PROFILE, GAP1, GAP2)}
    require(
        current[RESIDENT]["vma"] == prior[RESIDENT]["vma"] == 0xE09D
        and current[RESIDENT]["bytes"] == 0x1C12
        and prior[RESIDENT]["bytes"] == 0x1C13
        and current[GAP0]["vma"] == 0xFCAF
        and prior[GAP0]["vma"] == 0xFCB0
        and current[GAP0]["bytes"] == prior[GAP0]["bytes"] == 89
        and current[GAP0]["vma"] == current[RESIDENT]["end_exclusive"]
        and prior[GAP0]["vma"] == prior[RESIDENT]["end_exclusive"],
        "one-byte predecessor/successor relation drift")
    require(
        current[GAP1]["vma"] == current[PROFILE]["end_exclusive"]
        and prior[GAP1]["vma"] == prior[PROFILE]["end_exclusive"]
        and current[GAP2]["vma"] == prior[GAP2]["vma"] == 0xFF90,
        "sibling reopening relation drift")

    current_calls = symbolic_consumers(candidate, BEGIN)
    prior_calls = symbolic_consumers(reference, BEGIN)
    require(
        [row["caller"] for row in current_calls] == [
            "c2_product_append_staged", "c2_product_install",
            "c2_product_install"]
        and len(prior_calls) == 3
        and {row["resolved_target"] for row in current_calls} == {0xFCAF}
        and {row["resolved_target"] for row in prior_calls} == {0xFCB0},
        "gap0 call consumers do not track the linked symbol")

    old_body = reference.section_bytes(GAP0)
    new_body = candidate.section_bytes(GAP0)
    body_diffs = [index for index, pair in enumerate(zip(old_body, new_body))
                  if pair[0] != pair[1]]
    self_reloc_offsets = sorted(
        row.offset - candidate.section(GAP0).address
        for row in candidate.relocations
        if row.source_section == GAP0 and row.target == GAP0)
    require(body_diffs == [14, 21] and self_reloc_offsets == [14, 21],
            "gap0 byte delta is not confined to self-relocated targets")

    linker = linker_contract(CANDIDATE_LINKER.read_text(encoding="utf-8"))
    require(linker == linker_contract(LINKER_SOURCE.read_text(encoding="utf-8")),
            "emitted/source reopening placement relations differ")

    window = CANDIDATE_WINDOW.read_bytes()
    offset = current[GAP0]["vma"] - 0xE000
    require(len(window) == 0x2000
            and window[offset:offset + len(new_body)] == new_body,
            "candidate media window does not consume candidate-derived gap0 VMA")

    old_mentions = exact_address_mentions(0xFCB0)
    current_mentions = exact_address_mentions(0xFCAF)
    require(old_mentions == [] and current_mentions == [],
            "active source/build contract pins gap0 numeric VMA")

    historical = load(HISTORICAL_CONTRACT)["e000_geometry"]["reopen_gap0"]
    require(historical == {
        "address": "0xfca2", "bytes": 128, "end_exclusive": "0xfd22"},
        "historical reopening mobility evidence drift")
    golden = golden_row(GAP0)
    require(golden["vma"] == 0xFCB0,
            "reviewed golden no longer carries the rejected snapshot VMA")

    gap1_mentions = exact_address_mentions(current[GAP1]["vma"])
    gap2_mentions = exact_address_mentions(current[GAP2]["vma"])
    require(gap1_mentions and gap2_mentions,
            "sibling diagnostic/contract mention inventory unexpectedly empty")

    return {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": STATUS,
        "authority": {
            "authorization": authorization(), "final_red": bind(FINAL_RED),
            "candidate_elf": bind(CANDIDATE_ELF),
            "reference_elf": bind(REFERENCE_ELF),
            "reviewed_golden": bind(GOLDEN),
            "emitted_linker": bind(CANDIDATE_LINKER),
            "linker_source": bind(LINKER_SOURCE),
            "candidate_kernal_window": bind(CANDIDATE_WINDOW),
            "historical_contract": bind(HISTORICAL_CONTRACT),
            "driver": bind(DRIVER),
        },
        "card_state": {
            "replacement_card_consumed": True, "retry_authorized": False,
            "completion_allowed": False, "media_allowed": False,
            "device_allowed": False,
        },
        "observed_delta": {
            "reference": {RESIDENT: prior[RESIDENT], GAP0: prior[GAP0]},
            "candidate": {RESIDENT: current[RESIDENT], GAP0: current[GAP0]},
            "resident_size_delta_bytes": -1,
            "gap0_vma_delta_bytes": -1,
            "gap0_size_delta_bytes": 0,
            "gap0_body_different_offsets": body_diffs,
            "gap0_body_differences_are_self_relocations": True,
        },
        "dependency_inventory": {
            "symbolic_runtime_consumers": current_calls,
            "symbolic_runtime_consumer_count": len(current_calls),
            "absolute_runtime_consumers": [],
            "absolute_runtime_consumer_count": 0,
            "old_golden_vma_active_mentions": old_mentions,
            "candidate_vma_active_mentions": current_mentions,
            "active_pin_scan": {
                "roots": ["src", "config", "scripts", "mk",
                          "tools/host-lisp"],
                "tracked_text_files": len(tracked_text_files()),
                "excludes": [DRIVER.relative_to(ROOT).as_posix(), "docs",
                             "evidence", "golden-layout", "build"],
            },
            "media_format": {
                "window_vma": "0xe000..0xffff",
                "window_bytes": len(window),
                "section_offset_source": "candidate-gap0-vma-minus-0xe000",
                "section_offset": offset,
                "section_lma": 0x40000 + offset,
                "section_bytes_match_at_derived_offset": True,
                "fixed_gap0_offset_field": False,
            },
            "hardware_contract": {
                "required_window": "0xe000..0xffff",
                "fixed_gap0_address": None,
                "numeric_gap0_dependency_found": False,
            },
            "historical_placements": [
                {"world": "link48-hybrid-contract", "vma": 0xFCA2},
                {"world": "v2.0-source-oracle-replacement3", "vma": 0xFCB0},
                {"world": "v2.1-postlink-schema-replacement", "vma": 0xFCAF},
            ],
        },
        "linker_classification": linker,
        "sibling_classification": {
            GAP0: {
                "class": "candidate-derived-predecessor-end",
                "fixed_address_dependent": False,
                "recommended_golden_class": "derived-vma",
            },
            GAP1: {
                "class": "candidate-derived-predecessor-end",
                "fixed_address_dependent": False,
                "world_local_diagnostic_mentions": gap1_mentions,
                "recommendation": (
                    "same derived class as gap0; historical diagnostic pins "
                    "remain bound to their own artifact worlds"),
                "recommended_golden_class": "derived-vma",
            },
            GAP2: {
                "class": "explicit-fixed-window-offset",
                "fixed_address_dependent": True,
                "active_exact_mentions": gap2_mentions,
                "recommended_golden_class": "unchanged-fixed-vma",
                "same_situation_as_gap0": False,
            },
        },
        "attribution": {
            "outcome": "NOT-DEPENDED-UPON",
            "fixed_address_dependency_found": False,
            "mechanism": (
                "reopen_gap0 is the linker-derived end of c2_resident. Its "
                "three product callers relocate against the function symbol, "
                "the packed window derives the byte offset from the candidate "
                "VMA, and no active product/build/hardware/format contract "
                "mentions either 0xfcb0 or 0xfcaf as a required address."),
            "golden_mismatch_class": "snapshot-vma-promoted-to-invariant",
            "anchor_or_padding_supported": False,
            "reclassification_supported": True,
        },
        "owner_disposition": {
            "required": True,
            "recommended": (
                "one-time reviewed reclassification of gap0 and gap1 as "
                "candidate-derived predecessor-end VMAs; gap2 remains fixed"),
            "golden_changed": False,
            "card_authorized": False,
        },
        "attempt_accounting": red["attempt_accounting"],
        "claim_limit": (
            "Desk-only dependency attribution. No Golden edit, retry, card, "
            "Completion, media, device, product or release claim is made."),
    }


def validate(value: dict[str, Any]) -> None:
    require(value == derive(), "reopen-gap dependency attribution drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "promote-symbolic-call-to-absolute": lambda x: x[
            "dependency_inventory"].update(absolute_runtime_consumer_count=1),
        "hide-symbol-consumer": lambda x: x["dependency_inventory"].update(
            symbolic_runtime_consumer_count=2),
        "claim-active-fcb0-pin": lambda x: x["dependency_inventory"].update(
            old_golden_vma_active_mentions=[{"path": "src/fake.c"}]),
        "hide-predecessor-derivation": lambda x: x["linker_classification"][
            "gap0"].update(fixed_numeric_start=True),
        "promote-gap1-to-anchor": lambda x: x["sibling_classification"][
            GAP1].update(fixed_address_dependent=True),
        "demote-explicit-gap2": lambda x: x["sibling_classification"][
            GAP2].update(same_situation_as_gap0=True),
        "authorize-padding": lambda x: x["attribution"].update(
            anchor_or_padding_supported=True),
        "edit-golden-without-review": lambda x: x["owner_disposition"].update(
            golden_changed=True),
        "authorize-card": lambda x: x["owner_disposition"].update(
            card_authorized=True),
        "allow-media": lambda x: x["card_state"].update(media_allowed=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate(candidate)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases), "reopen-gap attribution mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "reopen-gap attribution receipt exists")
    value = derive()
    validate(value)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("2.1 reopen-gap dependency attribution: PASS gap0=derived "
          "gap1=derived gap2=fixed mutations=10 card=closed")


def check() -> None:
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate(value)
    require(rejected == mutations(value),
            "reopen-gap attribution mutation set drift")
    print("2.1 reopen-gap dependency attribution: PASS gap0=derived "
          "gap1=derived gap2=fixed mutations=10 card=closed")


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in ("record", "check"),
            "usage: c2_v21_reopen_gap_dependency_attribution.py record|check")
    {"record": record, "check": check}[sys.argv[1]]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"2.1 reopen-gap dependency attribution: FAIL {error}",
              file=sys.stderr)
        raise SystemExit(2)
