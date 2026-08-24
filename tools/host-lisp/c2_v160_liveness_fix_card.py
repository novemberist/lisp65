#!/usr/bin/env python3
"""Run the one authorized v1.6 retirement-liveness product card."""

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

import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v160_hybrid_live_stack_card as BASE  # noqa: E402
import c2_v160_input_fidelity_reopen_card as REOPEN  # noqa: E402
import c2_v160_input_service_hybrid_final_world as FINAL_WORLD  # noqa: E402
import c2_v160_liveness_config as CONFIG  # noqa: E402
import c2_v160_liveness_fix as FIX  # noqa: E402
import c2_v160_primary_vm_type_fix_replacement_card as PRIMARY  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-liveness-fix-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-liveness-fix-preflight"
PROCESS = ROOT / "build/c2.3/v1.6-liveness-fix-process"
NORMAL_BUILD = PROCESS / "normal-build"
NORMAL_PREFLIGHT = PROCESS / "normal-preflight"
MUTANT_BUILD = PROCESS / "mutant-build"
MUTANT_PREFLIGHT = PROCESS / "mutant-preflight"
PRODUCT_ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
RECEIPT = ARCH / "c2.3-v1.6-liveness-fix-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-liveness-fix-card-final-red.json"
PRIMARY_RECEIPT = ARCH / "c2.3-v1.6-primary-vm-type-fix-replacement-card-receipt.json"
HOLDER = ARCH / "c2.3-v1.6-stale-holder-broadened-result-receipt.json"
PREDECESSOR_ELF = ROOT / ("build/c2.3/v1.6-primary-vm-type-fix-replacement-card/"
                          "wplto/lisp65-c2-substitution-linked.prg.elf")
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
AUTHORIZATION = "514b3957"
FORMAT = "lisp65-c2-v160-retirement-liveness-fix-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 RETIREMENT LIVENESS FIX ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 RETIREMENT LIVENESS FIX FINAL WORLD GREEN"


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


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


def authority() -> dict[str, Any]:
    commit = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("exactly one liveness fix card", "enforcement lives at retirement",
                  "byte price is named", "abort row", "no extra contact"):
        require(token in text, f"liveness card authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    primary = load(PRIMARY_RECEIPT); holder = load(HOLDER)
    require(primary["status"] == PRIMARY.FINAL_STATUS
            and primary["attempt_accounting"]["WPLTO_runs"] == 1
            and holder["status"] ==
                "ATTRIBUTED: LISP_TOPLEVEL SAVED CSR HOLDS RETIRED RTOV ENTRY"
            and holder["claim_limit"].startswith("Names the holder"),
            "primary-fix/holder predecessor drift")
    return {"primary_fix": primary, "holder": holder}


def set_paths(build: Path, preflight: Path, *, tag: str) -> None:
    BASE.BUILD = build; BASE.PRODUCT_ELF = build / "wplto/lisp65-c2-substitution-linked.prg.elf"
    BASE.PREFLIGHT = preflight
    BASE.NORMAL_BUILD = NORMAL_BUILD; BASE.NORMAL_PREFLIGHT = NORMAL_PREFLIGHT
    BASE.MUTANT_BUILD = MUTANT_BUILD; BASE.MUTANT_PREFLIGHT = MUTANT_PREFLIGHT
    BASE.RECEIPT = RECEIPT if build == BUILD else preflight / "forbidden-receipt.json"
    BASE.FINAL_RED = FINAL_RED if build == BUILD else preflight / "forbidden-final-red.json"
    BASE.PREDECESSOR_RED = HOLDER
    BASE.DRIVER = DRIVER; BASE.AUTHORIZATION = AUTHORIZATION; BASE.FORMAT = FORMAT
    BASE.PREFLIGHT_STATUS = PREFLIGHT_STATUS; BASE.FINAL_STATUS = FINAL_STATUS
    BASE.set_paths(build, preflight, tag=tag)


def configure_module() -> None:
    set_paths(BUILD, PREFLIGHT, tag="retirement-liveness-fix")
    BASE.PREV.configure_module()

    def configure_stack(build: Path = BUILD, preflight: Path = PREFLIGHT,
                        *, activate_capture: bool = True
                        ) -> tuple[Any, dict[str, Any]]:
        CONFIG.restore_predecessor(PRODUCT)
        REOPEN.R1_TOP.configure_module()
        core = REOPEN.set_core_paths(build, preflight)
        activation: dict[str, Any] = {"capture": None, "hybrid": None,
                                      "liveness": None}
        if activate_capture:
            activation["capture"] = PRODUCT.configure_input_capture()
            activation["hybrid"] = PRODUCT.configure_input_hybrid()
        activation["liveness"] = CONFIG.configure(PRODUCT)
        core.install(build, preflight)
        return core, activation

    configure_stack._v160_input_hybrid = True  # type: ignore[attr-defined]
    configure_stack._v160_hybrid_before_install = True  # type: ignore[attr-defined]
    configure_stack._v160_retirement_liveness = True  # type: ignore[attr-defined]
    REOPEN.configure_stack = configure_stack


def emitted_function(truth: ElfTruth, name: str, *, unsized_bytes: int = 0) -> bytes:
    symbol = truth.symbol(name); section = truth.section(symbol.section)
    raw = truth.section_bytes(symbol.section)
    start = symbol.value - section.address
    count = symbol.bytes or unsized_bytes
    require(count > 0, f"unsized symbol cannot stand in for emitted identity: {name}")
    return raw[start:start + count]


def expected_walker(truth: ElfTruth) -> bytes:
    top = truth.symbol("lisp_toplevel").value
    start = truth.symbol("__lisp65_workbench_overlay_start").value
    length = truth.symbol("__lisp65_workbench_overlay_len").value
    stub = truth.symbol("c2_retired_continuation_stub").value
    return bytes((0xA0, 0x00, 0xB9, (top + 5) & 0xFF, (top + 5) >> 8,
        0x38, 0xE9, start & 0xFF, 0xAA,
        0xB9, (top + 6) & 0xFF, (top + 6) >> 8, 0xE9, start >> 8,
        0x90, 0x14, 0xC9, length >> 8, 0x90, 0x06, 0xD0, 0x0E,
        0xE0, length & 0xFF, 0xB0, 0x0A,
        0xA9, stub & 0xFF, 0x99, (top + 5) & 0xFF, (top + 5) >> 8,
        0xA9, stub >> 8, 0x99, (top + 6) & 0xFF, (top + 6) >> 8,
        0xC8, 0xC8, 0xC0, 0x0E, 0xD0, 0xD8, 0x60))


def final_liveness() -> dict[str, Any]:
    truth = ElfTruth.read(PRODUCT_ELF, llvm_readobj=READOBJ, include_section_data=True)
    sections = {row.name: row for row in truth.sections}
    facade = sections[".lisp65_c2_mapped_far_facade"]
    service = sections[".lisp65_c2_mapped_far_service"]
    text = sections[".text"]
    walker = truth.symbol("c2_rtov_retire_continuations")
    entry = truth.symbol("c2_rtov_retire_continuations_facade")
    stub = truth.symbol("c2_retired_continuation_stub")
    padding = truth.symbol("__lisp65_c2_mapped_far_facade_padding")
    require(service.bytes == 1425 and walker.bytes == 43
            and facade.bytes == 98 and entry.bytes == 9
            and stub.bytes == 1 and padding.bytes == 0
            and emitted_function(truth, walker.name) == expected_walker(truth)
            and emitted_function(truth, stub.name) == b"\x60",
            "final linked liveness identities/price drift")
    enter = truth.symbol("c2_mapped_far_enter").value
    leave = truth.symbol("c2_mapped_far_leave").value
    expected_entry = bytes((0x20, enter & 0xFF, enter >> 8,
                            0x20, walker.value & 0xFF, walker.value >> 8,
                            0x4C, leave & 0xFF, leave >> 8))
    require(emitted_function(truth, entry.name) == expected_entry,
            "final retirement facade does not pair enter/walker/leave")
    ordinary_free = facade.address - (text.address + text.bytes)
    allocated_rows = sorted((max(0xE000, row.address), min(0xFF80, row.address + row.bytes))
        for row in truth.sections if row.bytes > 0 and "SHF_ALLOC" in set(row.flags)
        and row.address < 0xFF80 and row.address + row.bytes > 0xE000)
    allocated: list[tuple[int, int]] = []
    for first, last in allocated_rows:
        if not allocated or first > allocated[-1][1]:
            allocated.append((first, last))
        else:
            allocated[-1] = (allocated[-1][0], max(allocated[-1][1], last))
    e000_free = 0x1F80 - sum(last - first for first, last in allocated)
    require(ordinary_free >= 3 and e000_free == 69 and e000_free - 54 == 15,
            "final born-derived thin-wall price drift")
    old = ElfTruth.read(PREDECESSOR_ELF, llvm_readobj=READOBJ,
                        include_section_data=True)
    require(emitted_function(truth, "__call_indir", unsized_bytes=3) ==
            emitted_function(old, "__call_indir", unsized_bytes=3) ==
            bytes.fromhex("6c1400"),
            "hot indirect-call path changed")
    cleanup = emitted_function(truth, "c2_product_abort_cleanup")
    call = bytes((0x20, entry.value & 0xFF, entry.value >> 8))
    require(cleanup.count(call) == 1, "retirement call absent from final cleanup")
    return {"status": "PASS: FINAL ELF ENFORCES RETIREMENT LIVENESS",
        "claim_source": "final linked ELF only",
        "symbols": {"walker": {"address": f"0x{walker.value:04x}", "bytes": walker.bytes},
            "facade": {"address": f"0x{entry.value:04x}", "bytes": entry.bytes},
            "stub": {"address": f"0x{stub.value:04x}", "bytes": stub.bytes}},
        "capacity": {"ordinary_text_free_bytes": ordinary_free,
            "ordinary_text_forecast_floor_bytes": 3,
            "ordinary_text_forecast_equality_pin_rejected": ordinary_free != 3,
            "e000_free_bytes": e000_free, "e000_floor_bytes": 54,
            "e000_surplus_bytes": e000_free - 54,
            "far_service_bytes": service.bytes, "far_service_capacity": 1499,
            "far_service_free_bytes": 1499 - service.bytes,
            "fixed_facade_bytes": facade.bytes, "facade_padding_bytes": padding.bytes},
        "contract": {"walker_matches_all_seven_pair_loop": True,
            "retirement_call_count": 1, "mapped_enter_leave_paired": True,
            "neutral_stub_is_RTS": True, "hot_call_indir_byteidentical": True}}


def install() -> None:
    BASE.BUILD = BUILD; BASE.PRODUCT_ELF = PRODUCT_ELF; BASE.PREFLIGHT = PREFLIGHT
    BASE.NORMAL_BUILD = NORMAL_BUILD; BASE.NORMAL_PREFLIGHT = NORMAL_PREFLIGHT
    BASE.MUTANT_BUILD = MUTANT_BUILD; BASE.MUTANT_PREFLIGHT = MUTANT_PREFLIGHT
    BASE.RECEIPT = RECEIPT; BASE.FINAL_RED = FINAL_RED; BASE.PREDECESSOR_RED = HOLDER
    BASE.DRIVER = DRIVER; BASE.AUTHORIZATION = AUTHORIZATION; BASE.FORMAT = FORMAT
    BASE.PREFLIGHT_STATUS = PREFLIGHT_STATUS; BASE.FINAL_STATUS = FINAL_STATUS
    BASE.authority = authority; BASE.predecessor = predecessor
    BASE.configure_module = configure_module
    PRIMARY.BUILD = BUILD


def preflight() -> None:
    install(); model = FIX.derive()
    require(not any(path.exists() for path in (BUILD, PREFLIGHT, NORMAL_BUILD,
        NORMAL_PREFLIGHT, MUTANT_BUILD, MUTANT_PREFLIGHT, RECEIPT, FINAL_RED)),
        "retirement liveness card is one-shot")
    BASE.preflight()
    path = PREFLIGHT / "preflight.json"; value = load(path)
    value.update({"format": FORMAT + "-preflight", "status": PREFLIGHT_STATUS,
        "liveness_authority": authority(), "predecessor": {
            "primary_fix": bind(PRIMARY_RECEIPT), "holder": bind(HOLDER)},
        "liveness_host_model": model,
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "media_builds": 0, "device_contacts": 0}})
    path.write_bytes(canonical(value))
    print("v1.6 liveness fix: PREFLIGHT PASS card=0/1 pairs=7")


def card() -> None:
    install(); configure_module(); armed = load(PREFLIGHT / "preflight.json")
    require(armed["status"] == PREFLIGHT_STATUS
            and armed["liveness_host_model"]["continuation_model"]
                ["all_seven_pairs_checked"] is True,
            "persisted liveness preflight drift")
    BASE.card(); receipt = load(RECEIPT)
    final = final_liveness()
    receipt.update({"format": FORMAT, "status": FINAL_STATUS,
        "liveness_authority": authority(), "predecessor": {
            "primary_fix": bind(PRIMARY_RECEIPT), "holder": bind(HOLDER)},
        "liveness_host_model": FIX.derive(), "final_liveness": final,
        "primary_vm_type_fix":
            load(ARCH / "c2.3-v1.6-primary-vm-type-fix-receipt.json"),
        "candidate_v16core": PRIMARY.final_library_world(receipt["final_world_claims"]),
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "media_authorized": False, "device_contacts": 0,
        "next": "independent review; then same-world media and one owner acceptance contact with abort row"})
    RECEIPT.write_bytes(canonical(receipt))
    print("v1.6 liveness fix: CARD PASS card=1/1 final-world=green")


def record_red(error: Exception) -> None:
    install(); configure_module(); BASE.record_red(error)
    if FINAL_RED.exists():
        value = load(FINAL_RED); value.update({"format": FORMAT + "-final-red",
            "status": "FINAL RED: V1.6 RETIREMENT LIVENESS FIX STOPS",
            "liveness_authority": authority(), "host_model": FIX.derive(),
            "retry_authorized": False, "media_authorized": False,
            "device_contacts": 0})
        FINAL_RED.write_bytes(canonical(value))


def main() -> int:
    choices = ("preflight", "card", "check", "_process_probe", "_process_probe_mutant",
        "_contract_probe", "_contract_probe_mutant", "_fold_probe", "_fold_probe_mutant",
        "_order_probe", "_order_probe_mutant", "_real_consumer_probe", "_membership_probe",
        "_hybrid_profile_probe", "_finalize_red", "_dry", "_produce", "_scope", "_accept",
        "_r1_arm", "_owner_graph", "_default_probe", "_full_probe", "_full_probe_mutant")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=choices); action = parser.parse_args().action
    install()
    if action == "preflight": preflight()
    elif action == "card": card()
    elif action == "check":
        require(RECEIPT.is_file(), "liveness card receipt absent")
        value = load(RECEIPT); require(value["status"] == FINAL_STATUS,
            "liveness card receipt drift")
        print("v1.6 liveness fix: CHECK PASS final-world=green")
    elif action == "_process_probe": BASE.process_probe_child(mutant=False)
    elif action == "_process_probe_mutant": BASE.process_probe_child(mutant=True)
    else:
        configure_module(); BASE.PREV.main()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_red(error)
            except Exception as receipt_error:
                print(f"liveness Final Red receipt failure: {receipt_error}", file=sys.stderr)
        print(f"v1.6 liveness fix card: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
