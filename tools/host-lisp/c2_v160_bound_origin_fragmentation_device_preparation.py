#!/usr/bin/env python3
"""Prepare fresh same-world media for the bound-origin input measurement."""

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

import c2_v160_bound_origin_fragmentation_second_replacement_card as FINAL  # noqa: E402
import c2_v160_liveness_prompt_device_preparation as PREP  # noqa: E402


BASE = PREP.BASE
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-bound-origin-fragmentation-device-preparation"
CARD = FINAL.BUILD
WPLTO = CARD / "wplto"
STATIC = CARD / "static-plane/narrow-static"
RECEIPT = ARCH / (
    "c2.3-v1.6-bound-origin-fragmentation-device-preparation-receipt.json")
SESSION = ROOT / "config/c2-v160-bound-origin-fragmentation-device-session.json"
CLOSURE = ARCH / (
    "c2.3-v1.6-bound-origin-fragmentation-acceptance-resume-receipt.json")
PROMPT = PREP.L65_PROMPT
EXPECTED = {
    "PRG": (41566, "f43bf592ba6f245e4032f0860aa9c4ce100e6e933767d0a4cf0c355ad6770a3b"),
    "ELF": (632832, "8bb00fd560ddfef9b4f1da5d6269e134de8dc6548a33e3659eb79fc580fecd45"),
}
MEDIA_AUTHORIZATION = "80baec42"
FRAGMENTATION_AUTHORIZATION = "76ff3147"
PRODUCT_REMOTE = "V16P5.D81"
LIBRARY_REMOTE = "V16L5.D81"
ORIGINAL_SESSION = PREP.session_config


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    rows: dict[str, Any] = {}
    for label, ref, tokens in (
        ("media", MEDIA_AUTHORIZATION, ("final product link and fresh same-world media",
            "stay under 256 events", "physical keystroke count")),
        ("fragmentation", FRAGMENTATION_AUTHORIZATION,
            ("aggregate free space is not placement capacity",
             "capacity watches report", "floor is untouched"))):
        commit = subprocess.run(["git", "rev-parse", f"{ref}^{{commit}}"],
            cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
        raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
            check=True, stdout=subprocess.PIPE).stdout
        text = " ".join(raw.decode().lower().replace("`", "").replace(
            "*", "").split())
        for token in tokens:
            require(token in text, f"bound-origin media authority absent: {token}")
        rows[label] = {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    return rows


def configure_candidate() -> None:
    """Reconstruct the configuration consumed by the accepted final link."""
    FINAL.install()
    FINAL.configure_module()
    core, _activation = BASE.REOPEN.configure_stack(FINAL.BUILD, FINAL.PREFLIGHT)
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
    section = PREP.ElfTruth.read(elf,
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj").section(
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
            "accepted fragmentation-safe pair drift")
    configure_candidate()
    closure = load(CLOSURE)
    historical = load(BASE.HISTORICAL_ACCEPTANCE)
    projection = historical["acceptance"]["VMA_golden"]
    placement = closure["placement"]
    require(closure["status"] ==
                "PASS: V1.6 BOUND-ORIGIN FINAL WORLD CLOSED READ-ONLY"
            and closure["frozen_pair_before"] == closure["frozen_pair_after"]
            and placement["final_reserve_bytes"] == 57
            and placement["largest_contiguous_hole_bytes"] == 49
            and closure["active_frame_liveness"]["input_counters"]
                ["ring_usable_events"] == 107,
            "accepted fragmentation closure drift")

    class AcceptedProjection:
        @staticmethod
        def compare_elf(candidate: Path) -> dict[str, Any]:
            require((candidate.stat().st_size, BASE.sha(candidate)) == EXPECTED["ELF"],
                    "Completion adapter received a different final ELF")
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
            "Completion changed accepted final identity")
    return value


def session_config(product: Path, library: Path) -> dict[str, Any]:
    value = ORIGINAL_SESSION(product, library)
    value["format"] = "lisp65-c2-v160-bound-origin-fragmentation-device-session-v1"
    value["recorded_on"] = "2026-08-21"
    value["media"]["product"]["remote_name"] = PRODUCT_REMOTE
    value["media"]["library"]["remote_name"] = LIBRARY_REMOTE
    value["claim_scope"] = {
        "accepts": ["v1.6-bound-origin-input-loss-attribution"],
        "excludes": ["v1.6-items-1-2-final-acceptance", "D5-headroom",
                     "release-acceptance", "v1.6-items-3-4"]}
    value["rows"] = [
        {"id": "D1", "action": "cold boot, mount library, require v16core and repl-comfort",
         "expect": "both requires return t; native lisp65> remains live"},
        {"id": "D2-enter", "action": "submit (repl)",
         "expect": "l65> appears; all four counters atomically start at zero"},
        {"id": "D2-bound-origin", "action": (
            "At l65>, slowly produce exactly the visible target a(a(a(a(. Repeat a "
            "physical key whenever it is not shown, count every physical key actuation "
            "including Shift+8 and every repeat, do not press Return, and stay below 256."),
         "expect": "target is visible; physical actuation count is recorded"},
        {"id": "D2-read-only-stop", "action": (
            "stop once without resume; read raw/seen/stored/taken at $BCFC..$BCFF"),
         "expect": "four raw bytes and the physical actuation count determine one arc"}]
    value["counter_witness"] = {
        "origin": "atomic zero at Comfort entry while capture tail remains $FF",
        "addresses": {"raw": "0xBCFC", "seen": "0xBCFD",
                      "stored": "0xBCFE", "taken": "0xBCFF"},
        "width_bits": 8, "maximum_physical_events": 255,
        "target_visible_text": "a(a(a(a(", "submit_after_target": False,
        "decision_table": {
            "physical>raw": "keyboard/core before queue-present observation",
            "raw>seen": "IRQ queue read or filtering",
            "seen>stored": "ring write or full-ring admission",
            "stored>taken": "consumer/take path",
            "physical=raw=seen=stored=taken": "no loss; display/timing path"}}
    return value


def configure() -> None:
    PREP.BUILD = BUILD; PREP.CARD = CARD; PREP.WPLTO = WPLTO; PREP.STATIC = STATIC
    PREP.RECEIPT = RECEIPT; PREP.SESSION = SESSION; PREP.EXPECTED = EXPECTED
    PREP.PRODUCT_REMOTE = PRODUCT_REMOTE; PREP.LIBRARY_REMOTE = LIBRARY_REMOTE
    PREP.configure_candidate = configure_candidate
    PREP.complete = complete
    PREP.session_config = session_config
    PREP.configure()


def preflight() -> None:
    configure()
    auth = authority(); closure = load(CLOSURE); prompt = load(PROMPT)
    require(not BUILD.exists() and not RECEIPT.exists() and not SESSION.exists(),
            "bound-origin media preparation is one-shot")
    require(closure["status"] ==
                "PASS: V1.6 BOUND-ORIGIN FINAL WORLD CLOSED READ-ONLY"
            and prompt["status"] == "PASS: V1.6 L65 PROMPT GREEN",
            "bound-origin media predecessor drift")
    product = WPLTO / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    require((product.stat().st_size, BASE.sha(product)) == EXPECTED["PRG"]
            and (elf.stat().st_size, BASE.sha(elf)) == EXPECTED["ELF"],
            "bound-origin candidate pair drift")
    print("v1.6 bound-origin media: PREFLIGHT PASS "
          f"media={auth['media']['commit'][:8]} fragmentation={auth['fragmentation']['commit'][:8]}")


def build() -> None:
    configure()
    value = BASE.build()
    value["format"] = (
        "lisp65-c2-v160-bound-origin-fragmentation-device-preparation-v1")
    value["recorded_on"] = "2026-08-21"
    value["execution_accounting"] = {
        "successful_run": {"WPLTO_runs": 0, "product_links": 0,
            "artifact_completions": 1, "media_builds": 2,
            "device_contacts": 0},
        "preparation_history": {"invocations": 2, "pre_output_stops": 1,
            "artifact_completions": 1, "product_media_builds": 1,
            "library_media_builds": 1, "WPLTO_runs": 0,
            "product_links": 0, "device_contacts": 0}}
    value["successor_authority"] = authority()
    value["final_world_closure"] = bind(CLOSURE)
    value["prompt_card"] = bind(PROMPT)
    value["status"] = "PASS: V1.6 BOUND-ORIGIN DEVICE CONTACT READY"
    RECEIPT.write_bytes(canonical(value))
    print("v1.6 bound-origin media: PASS media=2 contact=ready")


def check() -> dict[str, Any]:
    configure()
    value = load(RECEIPT)
    require(value["format"] ==
                "lisp65-c2-v160-bound-origin-fragmentation-device-preparation-v1"
            and value["recorded_on"] == "2026-08-21"
            and value["status"] == "PASS: V1.6 BOUND-ORIGIN DEVICE CONTACT READY"
            and value["execution_accounting"]["preparation_history"] == {
                "WPLTO_runs": 0, "artifact_completions": 1,
                "device_contacts": 0, "invocations": 2,
                "library_media_builds": 1, "pre_output_stops": 1,
                "product_links": 0, "product_media_builds": 1},
            "bound-origin media status drift")
    for row in [*value["accepted_pair"].values(), value["completion"],
                value["media_closure"], *value["media"].values(), value["session"],
                value["final_world_closure"], value["prompt_card"]]:
        require(bind(ROOT / row["path"]) == row,
                f"bound-origin artifact identity drift: {row['path']}")
    pair = BASE.PAIR.pair_identity(ROOT / value["media"]["product"]["path"],
                                   ROOT / value["media"]["library"]["path"])
    require(pair == value["same_world_pair"], "bound-origin pair identity drift")
    session = load(SESSION)
    witness = session["counter_witness"]
    require(session["media"]["product"]["remote_name"] == PRODUCT_REMOTE
            and session["media"]["library"]["remote_name"] == LIBRARY_REMOTE
            and session["recorded_on"] == "2026-08-21"
            and [row["id"] for row in session["rows"]] == [
                "D1", "D2-enter", "D2-bound-origin", "D2-read-only-stop"]
            and witness["target_visible_text"] == "a(a(a(a("
            and witness["maximum_physical_events"] == 255
            and witness["submit_after_target"] is False,
            "bound-origin session drift")
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
        check(); print("v1.6 bound-origin media: CHECK PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
