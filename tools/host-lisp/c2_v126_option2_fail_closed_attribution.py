#!/usr/bin/env python3
"""Attribute the Option-2 red frame without another device contact."""

from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth, ElfTruthError  # noqa: E402


TOOLCHAIN = ROOT / "tools/llvm-mos/bin"
ELF = ROOT / (
    "build/c2.2/v1.2.6-candidate-product-link83/final/"
    "resident-island-seed.prg.elf")
FIXTURE = ROOT / "tests/bytecode/dialect-v2/fixtures/v126-editor-option2.lisp"
OPTION2_DRIVER = ROOT / "tools/host-lisp/c2_v126_editor_option2_device.py"
DEVICE_BASE = ROOT / "tools/host-lisp/c2_v125_post_release_soak.py"
HOST_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-option2-equivalence-receipt.json")
DEVICE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-option2-device-receipt.json")
PRECEDENT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link72-defstruct-active-definition-poll-harness-first-red.json")
QUIET_CONTRACT = ROOT / "config/c2.2-defstruct-link72-stz-hardware-session.json"
COMMISSION = ROOT / "docs/planning/c2.2-v1.2.6-editor-option1-contact-review.md"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-option2-fail-closed-load-attribution-receipt.json")


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def elf_gate() -> dict[str, Any]:
    truth = ElfTruth.read(
        ELF, llvm_readobj=TOOLCHAIN / "llvm-readobj",
        include_section_data=True)
    irq = truth.section(".lisp65_c2_kernal_window.irq_handler")
    fail = truth.section(".lisp65_c2_kernal_window.map_switch_and_guards")
    vectors = truth.section(".lisp65_c2_vectors")
    irq_bytes = truth.section_bytes(irq.name)
    fail_bytes = truth.section_bytes(fail.name)
    vector_bytes = truth.section_bytes(vectors.name)

    require(irq.address == 0xE038 and irq.bytes == 74,
            "Link-83 IRQ handler geometry drift")
    require(fail.address == 0xE08B and fail_bytes == bytes.fromhex(
        "78 a9 00 8d 1a d0 a9 02 8d 20 d0 4c 96 e0"),
        "Link-83 fail-closed body drift")
    require(vector_bytes == bytes.fromhex("82 e0 8b e0 38 e0"),
            "Link-83 NMI/RESET/IRQ vector identity drift")
    require(irq_bytes[0x42:0x48] == bytes.fromhex("4c 8b e0 ee 86 ff"),
            "second-source-less fail-closed edge drift")

    targets = [row for row in truth.relocations
               if row.target == "c2_kernal_fail_closed"]
    require(
        [(row.source_section, row.offset, row.relocation_type)
         for row in targets] == [
            (irq.name, 0xE07B, "R_MOS_ADDR16"),
            (vectors.name, 0xFFFC, "R_MOS_ADDR16"),
        ],
        "fail-closed ingress set is not exactly IRQ-storm plus RESET",
    )

    red_store = bytes.fromhex("8d 20 d0")
    red_sites: list[dict[str, Any]] = []
    for section in truth.sections:
        if ("SHF_ALLOC" not in section.flags or section.bytes == 0
                or "NOBITS" in section.section_type):
            continue
        data = truth.section_bytes(section.name)
        offset = data.find(red_store)
        while offset >= 0:
            red_sites.append({
                "section": section.name,
                "address": f"0x{section.address + offset:04x}",
            })
            offset = data.find(red_store, offset + 1)
    require(red_sites == [{
        "section": fail.name,
        "address": "0xe093",
    }], "red-frame store is not unique in the bound product ELF")
    return {
        "IRQ_handler": "0xe038",
        "source_less_path": "0xe06d",
        "second_source_less_jump": "0xe07a -> 0xe08b",
        "fail_closed": "0xe08b",
        "fail_closed_self_loop": "0xe096",
        "red_store": red_sites[0],
        "ingresses": [
            "second consecutive source-less IRQ without owned-raster progress",
            "RESET vector deliberately names fail-closed",
        ],
        "semantic_C2D_or_loader_ingresses": 0,
    }


def validate_harness(
    fixture: str, option2: str, base: str,
    host: dict[str, Any], device: dict[str, Any],
    precedent: dict[str, Any], quiet: dict[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    forms = [line.strip() for line in fixture.splitlines() if line.strip()]
    require(len(forms) == 5 and sum(row.startswith("(defun ") for row in forms) == 2,
            "Option-2 fixture is not five forms with two persistent appends")
    run_begin = option2.index("\ndef run_contact(")
    run_end = option2.index("\ndef finalize(", run_begin)
    run_body = option2[run_begin:run_end]
    require(
        'load_screen = session.run_form(' in run_body
        and '"option2-source-load", SOURCE_LOAD, "t", poll=180)' in run_body,
        "Option-2 source load no longer uses exact-result screenshot polling",
    )
    base_begin = base.index("    def run_form(")
    base_end = base.index("    def capture_state(", base_begin)
    base_run = base[base_begin:base_end]
    require(
        "for _ in range(poll):" in base_run
        and "self.capture_screen(prefix)" in base_run
        and "time.sleep(1)" in base_run,
        "device run_form no longer polls through JTAG screenshots",
    )
    require(
        host["execution_witness"]["separate_session_appends_per_route"] == 2
        and "Physical C2J" in host["claim_limit"]
        and "target" in host["transaction_handoff"]["authority_boundary"],
        "host proof no longer exposes its target-state boundary",
    )
    require(
        device["contact"]["CPU_halts"] == 0
        and device["contact"]["measurement_claimed"] is False
        and device["contact"]["stage"].startswith("source load"),
        "Option-2 device First Red evidence boundary drift",
    )
    require(
        precedent["status"]
            == "resolved-harness-crossed-documented-C2.3-boundary"
        and precedent["first_red"]["stable_PC"] == "0xe096"
        and precedent["first_red"]["C2K_SOURCELESS_IRQS"] == 1
        and "JTAG screenshot per second"
            in precedent["first_red"]["harness_behavior"],
        "Link-72 active-definition monitor precedent drift",
    )
    define_row = [row for row in quiet["rows"] if row["id"] == "define-point"]
    require(
        len(define_row) == 1
        and define_row[0]["quiet_wait_seconds"] == 90
        and "no screenshot" in define_row[0]["reason"],
        "quiet active-definition harness contract drift",
    )
    return forms, {
        "source_forms": len(forms),
        "persistent_appends_during_load": 2,
        "device_protocol": "exact-result poll requests a JTAG screenshot every second until a result",
        "known_forbidden_crossing": (
            "monitor/Freezer intervention while a persistent definition or append is active"),
        "precedent": {
            "link": 72,
            "PC": "0xe096",
            "C2K_SOURCELESS_IRQS": 1,
            "classification": precedent["status"],
        },
        "current_contact_PC_measured": False,
        "current_contact_red_frame": True,
        "host_model_interrupt_or_monitor_semantics": False,
    }


def harness_gate() -> tuple[dict[str, Any], dict[str, str]]:
    values: dict[str, Any] = {
        "fixture": FIXTURE.read_text(encoding="utf-8"),
        "option2": OPTION2_DRIVER.read_text(encoding="utf-8"),
        "base": DEVICE_BASE.read_text(encoding="utf-8"),
        "host": load(HOST_RECEIPT),
        "device": load(DEVICE_RECEIPT),
        "precedent": load(PRECEDENT),
        "quiet": load(QUIET_CONTRACT),
    }
    _forms, witness = validate_harness(**values)

    def clone() -> dict[str, Any]:
        return json.loads(json.dumps(values))

    def rejected(mutated: dict[str, Any]) -> bool:
        try:
            validate_harness(**mutated)
        except AttributionError:
            return True
        return False

    mutations: dict[str, str] = {}
    row = clone()
    row["fixture"] = row["fixture"].replace("(defun %ib(n)", "(progn %ib(n)", 1)
    require(rejected(row), "missing persistent append mutation survived")
    mutations["remove-one-persistent-append"] = "rejected"
    row = clone()
    row["option2"] = row["option2"].replace("poll=180", "poll=0", 1)
    require(rejected(row), "poll removal mutation survived")
    mutations["remove-screenshot-poll"] = "rejected"
    row = clone()
    row["base"] = row["base"].replace(
        "for _ in range(poll):\n            _png, text = self.capture_screen(prefix)",
        "for _ in range(poll):\n            _png, text = (None, None)",
        1)
    require(rejected(row), "screen-capture removal mutation survived")
    mutations["remove-base-screen-capture"] = "rejected"
    row = clone()
    row["precedent"]["first_red"]["stable_PC"] = "0xe095"
    require(rejected(row), "precedent PC mutation survived")
    mutations["move-defstruct-precedent-PC"] = "rejected"
    row = clone()
    row["device"]["contact"]["CPU_halts"] = 1
    require(rejected(row), "current-contact halt mutation survived")
    mutations["invent-current-contact-PC-capture"] = "rejected"
    row = clone()
    define_row = next(item for item in row["quiet"]["rows"]
                      if item["id"] == "define-point")
    define_row["reason"] = define_row["reason"].replace(
        "no screenshot", "screenshot allowed")
    require(rejected(row), "quiet-contract screenshot mutation survived")
    mutations["allow-active-definition-screenshot"] = "rejected"
    return witness, mutations


def main() -> int:
    linked = elf_gate()
    harness, mutations = harness_gate()
    value = {
        "format": "lisp65-c2.2-v1.2.6-option2-fail-closed-load-attribution-v1",
        "recorded_on": date.today().isoformat(),
        "status": "attributed-known-active-definition-monitor-crossing",
        "decision": {
            "guard": "correct under the existing C2.2 episode contract",
            "product_load_or_C2D_invariant_failure": False,
            "target_only_pre_stage_divergence": False,
            "mechanism": (
                "the harness polled the screen through JTAG while the five-form "
                "source load could be executing either of its two persistent "
                "appends; the bound product maps the resulting second source-less "
                "IRQ of one raster episode to c2_kernal_fail_closed"),
            "host_proof_gap": (
                "the equivalence proof models persistent bytes and logical "
                "handoff state after append; it does not execute target IRQ, "
                "Freezer/monitor, raster-episode or load-time scheduling semantics"),
        },
        "linked_ELF": linked,
        "harness_and_precedent": harness,
        "mutations_rejected": mutations,
        "execution_witness": {
            "ELF_ingresses": 2,
            "semantic_loader_ingresses": 0,
            "red_store_sites": 1,
            "fixture_forms": 5,
            "persistent_appends": 2,
            "mutations": len(mutations),
        },
        "disposition": {
            "editor_stall": "remains parked; Option-2 never reached its measurement",
            "defstruct": (
                "Class-C owner review: the formal red-frame reopening condition is met, "
                "but this attribution removes a harness-induced fail-closed claim; it "
                "does not prove defstruct completion or authorize freight"),
            "harness": (
                "Class-C/process item: exact-result screenshot polling must not be used "
                "around forms that may append persistently; use the already contracted "
                "quiet/no-monitor protocol or an independently commissioned witness"),
            "product_bytes_changed": 0,
            "new_product_links": 0,
            "hardware_runs": 0,
        },
        "claim_limit": (
            "This host/ELF attribution names the Option-2 fail-closed mechanism from "
            "the bound Link-83 control-flow closure and the Link-72 target precedent. "
            "The current contact captured no PC or latch byte, so it does not claim a "
            "new target measurement, editor-stall classification or defstruct result."),
        "authority": {
            "ELF": bind(ELF),
            "fixture": bind(FIXTURE),
            "option2_driver": bind(OPTION2_DRIVER),
            "device_base": bind(DEVICE_BASE),
            "host_equivalence": bind(HOST_RECEIPT),
            "device_First_Red": bind(DEVICE_RECEIPT),
            "active_definition_precedent": bind(PRECEDENT),
            "quiet_contract": bind(QUIET_CONTRACT),
            "commission": bind(COMMISSION),
            "driver": bind(Path(__file__).resolve()),
        },
    }
    write_json(RECEIPT, value)
    print(
        "c2-v126-option2-fail-closed-attribution: PASS "
        "ingress=irq/reset semantic-loader=0 red-stores=1 "
        f"mutations={len(mutations)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, ElfTruthError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"c2-v126-option2-fail-closed-attribution: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
