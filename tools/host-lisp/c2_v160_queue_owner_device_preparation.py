#!/usr/bin/env python3
"""Prepare fresh same-world media for the fifth v1.6 input contact."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_bound_origin_fragmentation_device_preparation as PREV  # noqa: E402
import c2_v160_queue_owner_cold_relocation_card as QUEUE  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


BASE = PREV.BASE
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-queue-owner-device-preparation"
CARD = QUEUE.BUILD
WPLTO = CARD / "wplto"
STATIC = CARD / "static-plane/narrow-static"
RECEIPT = ARCH / "c2.3-v1.6-queue-owner-device-preparation-receipt.json"
SESSION = ROOT / "config/c2-v160-queue-owner-device-session.json"
CLOSURE = ARCH / "c2.3-v1.6-queue-owner-cold-relocation-resume-receipt.json"
PROMPT = PREV.PROMPT
ACCEPTANCE = CARD / "artifact-acceptance.json"
EXPECTED = {
    "PRG": (41566, "7c3b8936e7c732e31c9b2196caeb9672638d09460600c0950c14decf5bc44e8d"),
    "ELF": (632960, "347a2e6b4070a9f9e02c21216d59c5c18f66015373bbe93df14027eba0107c42"),
}
AUTHORIZATION = "c2b8b6a4"
PRODUCT_REMOTE = "V16Q5.D81"
LIBRARY_REMOTE = "V16C5.D81"


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


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


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    commit = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("queue ownership closed", "counter row, first",
                  "pressed = raw = seen = stored = taken", "prompt rows",
                  "abort row", "input rows"):
        require(token in text, f"queue-owner device authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def configure_candidate() -> None:
    """Reconstruct the configuration consumed by the frozen final link."""
    QUEUE.install()
    QUEUE.configure_module()
    core, _activation = BASE.REOPEN.configure_stack(QUEUE.BUILD, QUEUE.PREFLIGHT)
    core.PRODUCT.BASE.configure()
    BASE.CAN.REPLAY.PROFILE.configure()
    if BASE.PRODUCT.PROFILE_RODATA_BYTES == 342:
        BASE.PRODUCT.configure_require_resolver_profile_geometry()
        BASE.PRODUCT.configure_defstruct_foundation_profile_geometry()
    BASE.CAN.REPLAY.BANK2.configure_bank2_stage()
    BASE.CAN.REPLAY.TWO.configure_two_region()
    BASE.CAN.REPLAY.LINK60.configure_current_pin_adapters()
    BASE.PRODUCT.configure_intern_session_service()
    BASE.PRODUCT.configure_full_map_ownership()
    BASE.PRODUCT.configure_low_resident_lma_reset()
    BASE.HEADER.configure_consumption()
    BASE.PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = (
        STATIC / "product/substitution-artifacts.json")
    BASE.PRODUCT.INITIAL_C2D = STATIC / "product/initial.c2d-v3.bin"
    BASE.PRODUCT.PRODUCT_SHELF = STATIC / "product/product-shelf-v4-direct.bin"
    elf = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
    section = ElfTruth.read(
        elf, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj").section(
            BASE.PRODUCT.VERIFIER_BINDING_SECTION)
    BASE.PRODUCT.VERIFIER_BINDING_BASE = section.address
    BASE.PRODUCT.LINK60_VERIFIER_BINDING_BASE = section.address
    require(section.bytes == 40, "candidate verifier-binding size drift")


def complete() -> dict[str, Any]:
    BASE.configure_paths()
    product = WPLTO / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    require((product.stat().st_size, BASE.sha(product)) == EXPECTED["PRG"]
            and (elf.stat().st_size, BASE.sha(elf)) == EXPECTED["ELF"],
            "accepted queue-owner pair drift")
    configure_candidate()
    closure = load(CLOSURE)
    acceptance = load(ACCEPTANCE)
    projection = acceptance["VMA_golden"]
    require(
        closure["status"] ==
            "PASS: V1.6 QUEUE-OWNER COLD RELOCATION CLOSED READ-ONLY"
        and closure["frozen_pair_before"] == closure["frozen_pair_after"]
        and closure["linked_single_owner"]["queue_poll_calls"] == 2
        and closure["linked_single_owner"]["dominated_calls"] == 1
        and closure["cold_relocation"]["ordinary"]["free_bytes"] == 6
        and closure["cold_relocation"]["far"]["free_bytes"] == 15
        and acceptance["status"] == "PASS",
        "accepted queue-owner closure drift")

    class AcceptedProjection:
        @staticmethod
        def compare_elf(candidate: Path) -> dict[str, Any]:
            require((candidate.stat().st_size, BASE.sha(candidate)) == EXPECTED["ELF"],
                    "Completion adapter received a different queue-owner ELF")
            return projection

    accepted = AcceptedProjection()
    BASE.SOURCE_MEDIA.FLOW.BASE.INV = accepted
    BASE.CRC_MEDIA.INV = accepted
    BASE.SOURCE_MEDIA.card_projection = lambda: {
        "acceptance": {"VMA_golden": projection}}
    original_configure = BASE.CAN.REPLAY.configure
    original_fixed = BASE.PRODUCT.FIXED_BLOCK_LEAF.audit_elf
    original_facade = BASE.PRODUCT.fixed_facade_gate

    def fixed(candidate: Path, **kwargs: Any) -> dict[str, Any]:
        return BASE.SOURCE_MEDIA._link105_fixed_audit(
            original_fixed, candidate, **kwargs)

    def facade(out: Path, target: Path, suffix: str) -> dict[str, Any]:
        return BASE.CRC_MEDIA._current_facade_gate(
            original_facade, out, target, suffix)

    BASE.CAN.REPLAY.configure = lambda: None
    BASE.PRODUCT.FIXED_BLOCK_LEAF.audit_elf = fixed
    BASE.PRODUCT.fixed_facade_gate = facade
    try:
        value = BASE.CAN.complete_artifacts()
    finally:
        BASE.CAN.REPLAY.configure = original_configure
        BASE.PRODUCT.FIXED_BLOCK_LEAF.audit_elf = original_fixed
        BASE.PRODUCT.fixed_facade_gate = original_facade
    final_product = BASE.CAN.FINAL / product.name
    final_elf = Path(str(final_product) + ".elf")
    require((final_product.stat().st_size, BASE.sha(final_product)) == EXPECTED["PRG"]
            and (final_elf.stat().st_size, BASE.sha(final_elf)) == EXPECTED["ELF"]
            and value["compiler_runs"] == value["linker_runs"] == 0,
            "Completion changed queue-owner final identity")
    return value


def session_config(product: Path, library: Path) -> dict[str, Any]:
    value = PREV.ORIGINAL_SESSION(product, library)
    value["format"] = "lisp65-c2-v160-queue-owner-device-session-v1"
    value["recorded_on"] = "2026-08-21"
    value["media"]["product"]["remote_name"] = PRODUCT_REMOTE
    value["media"]["library"]["remote_name"] = LIBRARY_REMOTE
    value["claim_scope"] = {
        "accepts_on_green": ["v1.6-item-1-cursor-navigation",
                              "v1.6-item-2-comfort-repl", "Halt-A-decidable"],
        "excludes": ["D5-headroom", "v1.6-items-3-4", "release-acceptance",
                     "v1.7-retired-window-backstop"]}
    value["rows"] = [
        {"id": "D1", "action": (
            "cold boot product, mount library physically, require v16core and "
            "repl-comfort, then submit (repl)"),
         "expect": "both requires return t and the distinct l65> prompt appears"},
        {"id": "D2-counter-first", "action": (
            "At l65>, slowly enter exactly a(a(a(a( without Return. Count every "
            "character attempt; each Shift+8 chord counts as one queue event; "
            "repeat only if a character is not visible; remain below 256."),
         "expect": "all eight intended characters are visible and the attempt count is recorded"},
        {"id": "D2-counter-read", "action": (
            "stop once and read raw/seen/stored/taken at $BCFC..$BCFF; if equal, "
            "cold reboot the same media before continuing"),
         "expect": "attempts = raw = seen = stored = taken; any inequality stops the contact"},
        {"id": "D2-prompts", "action": (
            "re-enter Comfort, observe l65>, provoke TOKEN_TOO_LONG, then observe recovery"),
         "expect": (
            "l65> marks Comfort entry; clean recovery shows native lisp65>. The documented "
            "retired-window red frame is pre-existing v1.7 freight, not a v1.6 blocker; "
            "cold reboot after it. Any different failure stops.")},
        {"id": "D2-left-insert", "action": (
            "type (list 1 3), move left twice, insert 2 followed by a space"),
         "expect": "(1 2 3)"},
        {"id": "D2-navigation", "action": (
            "exercise Left/Right, C-b/C-f, C-a/C-e, Delete and C-d including boundaries"),
         "expect": "cursor editing preserves order, inserts rather than overwrites, and boundary no-ops are safe"},
        {"id": "D2-balanced", "action": (
            "submit (+ 10 on line one and 32) on line two"),
         "expect": "42 with continuation indentation"},
        {"id": "D2-history", "action": "evaluate (list 7 8), then Up and Return",
         "expect": "(7 8) twice"},
        {"id": "D2-input-fidelity", "action": (
            "rapidly enter (+ 1, then five continuation comment lines each with a "
            "visually checked 40-digit 0123456789 pattern, then 2), without observation pauses"),
         "expect": "every digit remains ordered and the result is 3",
         "forced_collection_basis": (
            "more than 192 accepted printable cells forces at least one collection")},
        {"id": "D2-lowercase", "action": (
            "with Shift-Lock off, type and inspect a lowercase alphabetic form"),
         "expect": "lowercase remains lowercase on screen and in the result"},
        {"id": "D2-felt-latency", "action": (
            "type a rapid sentence-length burst, pause once, then edit its middle"),
         "expect": "no swallowed keys and no progressive multi-second backlog"},
    ]
    value["counter_witness"] = {
        "origin": "atomic zero at Comfort entry while capture tail is closed",
        "addresses": {"raw": "0xBCFC", "seen": "0xBCFD",
                      "stored": "0xBCFE", "taken": "0xBCFF"},
        "width_bits": 8, "maximum_events": 255,
        "decision_table": {
            "attempts>raw": "keyboard/core before queue-present observation",
            "raw>seen": "IRQ queue read or filtering",
            "seen>stored": "ring admission",
            "stored>taken": "consumer",
            "attempts=raw=seen=stored=taken": "single-owner input path green"}}
    return value


def configure() -> None:
    BASE.BUILD = BUILD; BASE.CARD = CARD; BASE.WPLTO = WPLTO; BASE.STATIC = STATIC
    BASE.TARGET = BUILD / "canonical-product"
    BASE.SHARED = BUILD / "shared-system"; BASE.LIBRARY = BUILD / "library"
    BASE.RECEIPT = RECEIPT; BASE.SESSION = SESSION; BASE.EXPECTED = EXPECTED
    BASE.configure_candidate = configure_candidate
    BASE.complete = complete
    BASE.session_config = session_config


def preflight() -> None:
    configure()
    closure = load(CLOSURE)
    require(not BUILD.exists() and not RECEIPT.exists() and not SESSION.exists(),
            "queue-owner device preparation is one-shot")
    require(closure["status"] ==
                "PASS: V1.6 QUEUE-OWNER COLD RELOCATION CLOSED READ-ONLY"
            and load(PROMPT)["status"] == "PASS: V1.6 L65 PROMPT GREEN",
            "queue-owner media predecessor drift")
    product = WPLTO / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    require((product.stat().st_size, BASE.sha(product)) == EXPECTED["PRG"]
            and (elf.stat().st_size, BASE.sha(elf)) == EXPECTED["ELF"],
            "queue-owner candidate pair drift")
    print("v1.6 queue-owner media: PREFLIGHT PASS "
          f"authority={authority()['commit'][:8]} media=0 device=0")


def build() -> None:
    configure()
    value = BASE.build()
    value["format"] = "lisp65-c2-v160-queue-owner-device-preparation-v1"
    value["recorded_on"] = "2026-08-21"
    value["successor_authority"] = authority()
    value["final_world_closure"] = bind(CLOSURE)
    value["prompt_card"] = bind(PROMPT)
    value["status"] = "PASS: V1.6 QUEUE-OWNER FIFTH CONTACT READY"
    RECEIPT.write_bytes(canonical(value))
    print("v1.6 queue-owner media: PASS media=2 contact=ready")


def check() -> dict[str, Any]:
    configure()
    value = load(RECEIPT)
    require(value["format"] ==
                "lisp65-c2-v160-queue-owner-device-preparation-v1"
            and value["status"] == "PASS: V1.6 QUEUE-OWNER FIFTH CONTACT READY",
            "queue-owner preparation receipt drift")
    for row in [*value["accepted_pair"].values(), value["completion"],
                value["media_closure"], *value["media"].values(),
                value["session"], value["final_world_closure"],
                value["prompt_card"]]:
        require(bind(ROOT / row["path"]) == row,
                f"queue-owner artifact identity drift: {row['path']}")
    pair = BASE.PAIR.pair_identity(ROOT / value["media"]["product"]["path"],
                                   ROOT / value["media"]["library"]["path"])
    require(pair == value["same_world_pair"], "queue-owner pair identity drift")
    session = load(SESSION)
    require(session["media"]["product"]["remote_name"] == PRODUCT_REMOTE
            and session["media"]["library"]["remote_name"] == LIBRARY_REMOTE
            and [row["id"] for row in session["rows"][:4]] == [
                "D1", "D2-counter-first", "D2-counter-read", "D2-prompts"]
            and session["counter_witness"]["maximum_events"] == 255,
            "queue-owner session drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "build", "check"))
    action = parser.parse_args().action
    if action == "preflight":
        preflight()
    elif action == "build":
        build()
    else:
        check(); print("v1.6 queue-owner media: CHECK PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
