#!/usr/bin/env python3
"""Rebind the proven target-side progress ring to the Link-107 world."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_v20_loading_libraries_progress_ring as RING  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
CARD = ARCH / "c2.3-v2.1-dependent-vma-replacement-card-receipt.json"
MEDIA = ARCH / "c2.3-v2.1-dependent-vma-completion-media-receipt.json"
D1_RED = ARCH / "c2.3-v2.1-dependent-vma-d1-first-red-receipt.json"
OLD_RING = ARCH / "c2.3-v2.0-loading-libraries-progress-ring-receipt.json"
OLD_RESULT = ARCH / "c2.3-v2.0-loading-libraries-progress-map-device-receipt.json"
CONTROL_ELF = ROOT / (
    "build/c2.3/v2.1-dependent-vma-replacement-card/final/"
    "lisp65-c2-substitution-linked.prg.elf")
CONTROL_PRG = ROOT / (
    "build/c2.3/v2.1-dependent-vma-replacement-card/final/"
    "lisp65-c2-substitution-linked.prg")
CONTROL_D81 = ROOT / (
    "build/c2.3/v2.1-dependent-vma-media/shared-system/lisp65-product.d81")
LIBRARY_D81 = ROOT / (
    "build/c2.3/v2.1-dependent-vma-media-base/library/lisp65-library.d81")
SESSION = ROOT / "config/c2-v21-loading-libraries-progress-session.json"
RUNNER = ROOT / "scripts/c2-v21-loading-libraries-progress-hw.sh"

OUT = ROOT / "build/c2.3/v2.1-loading-libraries-progress"
ART = OUT / "artifacts"
DIAG_PRG = ART / "diagnostic-loading-libraries-progress.prg"
DIAG_ELF = ART / "diagnostic-loading-libraries-progress.elf"
DIAG_WINDOW = ART / "diagnostic-loading-libraries-progress-window.bin"
DIAG_STATE = ART / "loading-libraries-progress-state-reset.bin"
DIAG_D81 = OUT / "lisp65-loading-libraries-progress.d81"
DIAG_DESCRIPTOR = OUT / "boot.id"
DIAG_STAGER = OUT / "autoboot.c65"
DIAG_STAGER_MAP = OUT / "autoboot.c65.map"
DIAG_STAGER_BUILD = OUT / "stager-build"
DEPLOY = OUT / "deployment.json"
RECEIPT = ARCH / "c2.3-v2.1-loading-libraries-progress-ring-receipt.json"

AUTHORIZATION = "a673ad27"
FORMAT = "lisp65-c2.3-v2.1-loading-libraries-progress-ring-v1"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"

# Emitted Link-107 identities.  The ring bodies and owner-free state geometry
# are unchanged; only these real call/return PCs differ from the Link-106 donor.
C2D_RETURN = 0xE329
SHELF_RETURN = 0xE850
ABORT_CALL = 0x2EAC
VM_C2D_CALL = 0x788E


class RebindError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RebindError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": digest(raw)}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(canonical(value))
    temporary.replace(path)


def git_authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().split()).lower()
    require("one progress- ring contact on the new candidate world" in text
            and "one closing stop" in text and "owner keyboard" in text,
            "Link-107 ring authorization drift")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": digest(raw)}


def configure_ring() -> None:
    RING.CONTROL_ELF = CONTROL_ELF
    RING.CONTROL_PRG = CONTROL_PRG
    RING.CONTROL_D81 = CONTROL_D81
    RING.LIBRARY_D81 = LIBRARY_D81
    RING.SESSION = SESSION
    RING.RUNNER = RUNNER
    RING.OUT = OUT
    RING.ART = ART
    RING.DIAG_PRG = DIAG_PRG
    RING.DIAG_ELF = DIAG_ELF
    RING.DIAG_WINDOW = DIAG_WINDOW
    RING.DIAG_STATE = DIAG_STATE
    RING.DIAG_D81 = DIAG_D81
    RING.DIAG_DESCRIPTOR = DIAG_DESCRIPTOR
    RING.DIAG_STAGER = DIAG_STAGER
    RING.DIAG_STAGER_MAP = DIAG_STAGER_MAP
    RING.DIAG_STAGER_BUILD = DIAG_STAGER_BUILD
    RING.DEPLOY = DEPLOY
    RING.C2D_RETURN = C2D_RETURN
    RING.SHELF_RETURN = SHELF_RETURN
    RING.ABORT_CALL = ABORT_CALL
    RING.VM_C2D_CALL = VM_C2D_CALL
    RING.SECTION_STATE = ".lisp65_v21_loading_libraries_progress_state"


def session_contract() -> dict[str, Any]:
    value = load(SESSION)
    require(
        value.get("accepted_by") == AUTHORIZATION
        and value.get("status")
            == "owner-authorized-autonomous-cpu-transport-ring-contact"
        and value.get("inputs", {}).get("product_medium")
            == DIAG_D81.relative_to(ROOT).as_posix()
        and value.get("inputs", {}).get("library_medium")
            == LIBRARY_D81.relative_to(ROOT).as_posix()
        and value.get("active_interval") == {
            "begins": "FTP exits after byteidentical readback and product mount",
            "quiet_seconds": 180, "host_monitor_entries": 0,
            "host_CPU_stops": 0, "screenshots": 0, "FTP_accesses": 0,
            "owner_keyboard_lines": 0,
            "sampler": "owned target raster IRQ only"}
        and value.get("readback", {}).get("physical_ranges")
            == ["0x0000B582:66", "0x0000FF83:2"]
        and value.get("authorization") == {
            "contact_authorized": True, "class": "B",
            "owner_keyboard_required": False, "D1_D5_open": False},
        "Link-107 progress session drift")
    return value


def input_contract() -> dict[str, Any]:
    card = load(CARD)
    media = load(MEDIA)
    red = load(D1_RED)
    old = load(OLD_RING)
    old_result = load(OLD_RESULT)
    require(
        card.get("status") == "PASS: sole dependent-VMA replacement card green"
        and card.get("transport", {}).get("reader", {}).get("address") == "0x2277"
        and media.get("status")
            == "PASS: Link 107 completed and media closed; D1 ready"
        and media.get("media", {}).get("product_D81") == bind(CONTROL_D81)
        and media.get("media", {}).get("library_D81") == bind(LIBRARY_D81)
        and red.get("status") == (
            "D1-FIRST-RED-LOADING-LIBRARIES-AT-45S; "
            "NO-LIVE-OR-LOOP-CLAIM")
        and old.get("mutations", {}).get("total") == 24
        and old_result.get("progress_ring", {}).get("newest_counter") == 18,
        "Link-107 ring input authority drift")
    return {"card": card, "media": media, "D1_red": red,
            "old_ring": old, "old_result": old_result}


def emitted_identity(truth: ElfTruth) -> dict[str, Any]:
    c2d = truth.symbol("c2_stream_c2d_read")
    shelf = truth.symbol("c2_stream_shelf_read")
    irq = truth.section(".lisp65_c2_kernal_window.irq_handler")
    text = truth.section(".text")
    raw_text = truth.section_bytes(".text")
    require(
        c2d.value <= C2D_RETURN < c2d.value + c2d.bytes
        and shelf.value <= SHELF_RETURN < shelf.value + shelf.bytes
        and truth.section_bytes(c2d.section)[
            C2D_RETURN - truth.section(c2d.section).address:
            C2D_RETURN - truth.section(c2d.section).address + 3]
            == b"\x4c" + RING.u16(RING.PRODUCER_C2D)
        and truth.section_bytes(shelf.section)[
            SHELF_RETURN - truth.section(shelf.section).address:
            SHELF_RETURN - truth.section(shelf.section).address + 3]
            == b"\x4c" + RING.u16(RING.PRODUCER_SHELF)
        and truth.section_bytes(irq.name)[
            RING.IRQ_SAMPLE_CALL - irq.address:
            RING.IRQ_SAMPLE_CALL - irq.address + 3]
            == b"\x20" + RING.u16(RING.SAMPLER)
        and raw_text[ABORT_CALL - text.address:ABORT_CALL - text.address + 3]
            == b"\xea\xea\xea"
        and raw_text[VM_C2D_CALL - text.address:VM_C2D_CALL - text.address + 3]
            == b"\x20" + RING.u16(RING.VM_C2D_SAFE_NIL),
        "Link-107 ring emitted identity drift")
    return {"c2d_return": f"0x{C2D_RETURN:04x}",
            "shelf_return": f"0x{SHELF_RETURN:04x}",
            "IRQ_sample_call": f"0x{RING.IRQ_SAMPLE_CALL:04x}",
            "abort_call_retired": f"0x{ABORT_CALL:04x}",
            "vm_c2d_call_retired": f"0x{VM_C2D_CALL:04x}"}


def derive(*, rebuild: bool) -> dict[str, Any]:
    configure_ring()
    inputs = input_contract()
    session_contract()
    if rebuild:
        if OUT.exists():
            shutil.rmtree(OUT)
        layout = RING.patched_images()
        medium = RING.build_medium(layout)
        write_json(DEPLOY, {
            "status": "HOST-GREEN; CPU-TRANSPORT-RING-CONTACT-AUTHORIZED",
            "product_D81": bind(DIAG_D81), "library_D81": bind(LIBRARY_D81),
            "diagnostic_PRG": bind(DIAG_PRG), "diagnostic_ELF": bind(DIAG_ELF),
            "diagnostic_window": bind(DIAG_WINDOW),
            "state": {"physical_range": "0x0000B582..0x0000B5C3",
                "counter": "0xB582..0xB585", "arm": "0xB58D",
                "slots": "0xB58E..0xB5C1", "slot_bytes": 13,
                "slot_count": 4},
            "contact": {"authorized": True, "quiet_seconds": 180,
                "active_observations": 0, "final_stops": 1,
                "D1_D5_open": False}})
    else:
        require(DEPLOY.is_file(), "Link-107 ring deployment absent")
        # Read the persisted media inventory rather than rebuilding it.
        medium = load(RECEIPT)["media"]
        layout = load(RECEIPT)["layout"]

    truth = ElfTruth.read(DIAG_ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    identity = emitted_identity(truth)
    state = DIAG_STATE.read_bytes()
    require(state == RING.state_reset() and len(state) == 66,
            "Link-107 progress state reset drift")
    control_roles = medium["control_roles"]
    diagnostic_roles = medium["diagnostic_roles"]
    changed = sorted(name for name in control_roles
                     if control_roles[name]["sha256"]
                     != diagnostic_roles[name]["sha256"])
    require(changed == ["autoboot.c65", "boot.id", "lisp65.prg", "window.bin"]
            and len(control_roles) == len(diagnostic_roles) == 15,
            f"Link-107 ring media delta drift: {changed}")
    producer = DIAG_WINDOW.read_bytes()[
        RING.PRODUCER_C2D - RING.WINDOW_BASE:
        RING.PRODUCER_LIMIT - RING.WINDOW_BASE]
    sampler = DIAG_WINDOW.read_bytes()[
        RING.SAMPLER - RING.WINDOW_BASE:RING.SAMPLER_LIMIT - RING.WINDOW_BASE]
    executable = RING.executable_mutations(producer, sampler)
    require(len(executable) == 6, "Link-107 ring executable mutation drift")
    value = {
        "format": FORMAT, "recorded_on": "2026-08-15",
        "status": "HOST-GREEN; LINK107-CPU-TRANSPORT-RING; CONTACT-AUTHORIZED",
        "authority": git_authority(),
        "inputs": {"card": bind(CARD), "media": bind(MEDIA),
            "D1_first_red": bind(D1_RED), "old_ring": bind(OLD_RING),
            "old_device_result": bind(OLD_RESULT),
            "control_ELF": bind(CONTROL_ELF), "control_PRG": bind(CONTROL_PRG),
            "control_D81": bind(CONTROL_D81)},
        "identity": {"promotable": False, "product_candidate_bytes_changed": 0,
            "product_links": 0, "WPLTO_runs": 0, "hardware_contacts": 0,
            "control_roles": len(control_roles),
            "diagnostic_roles": len(diagnostic_roles),
            "enumerated_delta_roles": changed,
            "control_bytes_outside_delta_byteidentical": True},
        "rebind": {"Link106": {"C2D_return": "0xe32a",
                "Shelf_return": "0xe851", "abort_call": "0x2dde",
                "vm_c2d_call": "0x77c0"},
            "Link107": identity,
            "unchanged": {"producer_carrier": "0xfe88..0xfee0",
                "sampler_carrier": "0xfee1..0xff66",
                "state": "0xb582..0xb5c3", "IRQ_call": "0xe053"}},
        "ring": {"counter": {"address": "0xb582", "bits": 32},
            "expected_logical_reads": 346298, "sample_every_frames": 2048,
            "slots": {"start": "0xb58e", "count": 4, "bytes_each": 13},
            "commit_last": True, "owner_free": True,
            "producer_vectors": RING.producer_vectors(producer),
            "sampler_vectors": RING.sampler_vectors(sampler)},
        "layout": {"producer_hex": producer.hex(), "sampler_hex": sampler.hex(),
            "state_hex": state.hex()},
        "media": {**medium, "diagnostic_D81": bind(DIAG_D81),
            "library_D81": bind(LIBRARY_D81), "shared_roles": 11,
            "total_roles": 15, "readback": "byteidentical"},
        "deployment": bind(DEPLOY), "session": bind(SESSION),
        "runner": bind(RUNNER),
        "comparison": {"old_DMA_world": {
                "counter": inputs["old_result"]["progress_ring"]["newest_counter"],
                "observation_seconds": inputs["old_result"]["progress_ring"]
                    ["fixed_observation_seconds"]},
            "new_CPU_world": "pending-one-autonomous-contact"},
        "contact": {"authorized": True, "class": "B",
            "owner_keyboard_required": False, "quiet_seconds": 180,
            "active_observations": 0, "final_stops": 1,
            "CPU_left_stopped": True, "D1_D5_open": False},
        "mutations": {"executable": {"count": 6, "rejected": executable},
            "rebind": 8, "total": 14},
        "decision_table": {"growing": "LIVE; calculate CPU logical reads/second",
            "complete": "BOOT LOAD COMPLETED inside the ring interval",
            "fixed": "NO LOGICAL READ PROGRESS; bind phase/ordinal neighborhood",
            "invalid": "INSTRUMENT RED; no product claim"},
        "claim_limit": (
            "Non-promotable Link-107 diagnostic sibling only. The one contact "
            "measures successful logical CPU-transport reads; it changes no "
            "product bytes and does not open D1-D5."),
    }
    return value


def audit(value: dict[str, Any]) -> None:
    require(
        value.get("status")
            == "HOST-GREEN; LINK107-CPU-TRANSPORT-RING; CONTACT-AUTHORIZED"
        and value.get("identity", {}).get("promotable") is False
        and value.get("identity", {}).get("product_candidate_bytes_changed") == 0
        and value.get("identity", {}).get("enumerated_delta_roles")
            == ["autoboot.c65", "boot.id", "lisp65.prg", "window.bin"]
        and value.get("rebind", {}).get("Link107") == {
            "c2d_return": "0xe329", "shelf_return": "0xe850",
            "IRQ_sample_call": "0xe053", "abort_call_retired": "0x2eac",
            "vm_c2d_call_retired": "0x788e"}
        and value.get("ring", {}).get("sample_every_frames") == 2048
        and value.get("ring", {}).get("commit_last") is True
        and value.get("media", {}).get("total_roles") == 15
        and value.get("media", {}).get("readback") == "byteidentical"
        and value.get("contact") == {"authorized": True, "class": "B",
            "owner_keyboard_required": False, "quiet_seconds": 180,
            "active_observations": 0, "final_stops": 1,
            "CPU_left_stopped": True, "D1_D5_open": False}
        and value.get("mutations", {}).get("total") == 14,
        "Link-107 progress-ring receipt drift")


def mutation_gate(value: dict[str, Any]) -> int:
    cases = {
        "promote": ("identity", "promotable", True),
        "claim-product-byte": ("identity", "product_candidate_bytes_changed", 1),
        "old-c2d-return": ("rebind", "Link107", {}),
        "drop-delta-role": ("identity", "enumerated_delta_roles", ["window.bin"]),
        "poll-active": ("contact", "active_observations", 1),
        "drop-stop": ("contact", "final_stops", 0),
        "open-D2": ("contact", "D1_D5_open", True),
        "drop-commit-last": ("ring", "commit_last", False),
    }
    rejected = 0
    for section, key, replacement in cases.values():
        trial = deepcopy(value)
        trial[section][key] = replacement
        try:
            audit(trial)
        except RebindError:
            rejected += 1
    require(rejected == len(cases), "Link-107 ring rebind mutation survived")
    return rejected


def build() -> dict[str, Any]:
    value = derive(rebuild=True)
    require(mutation_gate(value) == 8, "Link-107 ring mutation count drift")
    write_json(RECEIPT, value)
    return value


def check() -> dict[str, Any]:
    value = load(RECEIPT)
    audit(value)
    require(value == derive(rebuild=False), "Link-107 ring replay drift")
    require(mutation_gate(value) == 8, "Link-107 ring mutation replay drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "build":
        value = build()
    elif args.action == "check":
        value = check()
    else:
        configure_ring()
        donor = bytearray(RING.PRODUCER_LIMIT - RING.PRODUCER_C2D)
        tail = RING.VM_C2D_SAFE_NIL - RING.PRODUCER_C2D
        donor[tail:tail + 7] = bytes.fromhex("a900a200a30060")
        producer = RING.producer_bytes(bytes(donor))[0]
        sampler = RING.sampler_bytes()[0]
        require(len(RING.producer_vectors(producer)) == 14
                and len(RING.sampler_vectors(sampler)) == 6,
                "Link-107 ring model selftest drift")
        print("Link-107 CPU ring: SELFTEST PASS vectors=20")
        return 0
    print("Link-107 CPU ring: PASS "
          f"action={args.action} roles={value['media']['total_roles']} "
          f"mutations={value['mutations']['total']} contact=authorized")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RebindError, RING.RingError, OSError, ValueError, KeyError,
            subprocess.CalledProcessError) as error:
        print(f"LINK 107 CPU RING: {error}", file=sys.stderr)
        raise SystemExit(1)
