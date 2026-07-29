#!/usr/bin/env python3
"""Prepare and verify the one-run Link-58 C1 Freezer hardware fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402
import c2_product_hw_presmoke as HW  # noqa: E402
import runtime_overlay_bank as R  # noqa: E402


LINK = ROOT / (
    "build/c2.2/substitution/product-link-58-matrix-addenda-fixed-block")
CARRIER = ROOT / (
    "build/c2.2/substitution/"
    "link58-c1-freezer-link58-rebound-stage-bound-NONPROMOTABLE")
CARRIER_BASENAME = (
    "runtime-overlays-session-c1-freezer-"
    "link58-rebound-stage-bound.bin")
OUT = ROOT / (
    "build/c2.2/c1-freezer-hardware-link58-attempt4-NONPROMOTABLE")
LINK_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link58-matrix-addenda-fixed-block-structural-receipt.json")
CARRIER_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link58-c1-freezer-link58-relocation-rebind-"
    "nonpromotable-receipt.json")
CARRIER_RECEIPT_STATUS = (
    "passed-class-a-Link58-relocation-rebind-stage-replay-"
    "awaiting-hardware-authorization")
DEPLOYMENT_STATUS = "ready-nonpromotable-hardware-fixture"
FIRST_RED_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link58-c1-freezer-hybrid-stage-binding-hardware-first-red.json")
ZERO_JOURNAL_FIRST_RED_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link58-c1-freezer-zero-journal-hardware-first-red.json")
CROSS_IDENTITY_FIRST_RED_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link58-c1-freezer-cross-identity-relocation-"
    "hardware-first-red.json")
CONTRACT = ROOT / "config/c2-c1-freezer-cutpoint-contract.json"
ARTIFACTS = ROOT / (
    "build/c2.2/substitution/published-nullary-call-bytecode-artifacts/"
    "product/substitution-artifacts.json")
PRODUCT_SHA = (
    "4bab8371aa54060bef4ab9493e12dd6afd230baeb83a11f07daccdaa05000e6f")
RTOV_FAULT = 0x0077
RTOV_FAMILY = 0x0079
C2_READY = 0x008C
C2J_BYTES = 64
HARDWARE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link58-C1-Freezer-four-cutpoint-hardware-receipt.json")
CUTPOINT2_FIRST_RED_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link58-C1-Freezer-cutpoint2-continuation-"
    "hardware-first-red.json")


class FixtureError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise FixtureError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(path.relative_to(ROOT)),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }
    if address is not None:
        result["address"] = f"0x{address:08x}"
    return result


def paths() -> dict[str, Path]:
    artifacts = read_json(ARTIFACTS)
    shelf = ROOT / artifacts["artifacts"]["shelf"]["path"]
    return {
        "product": LINK / "lisp65-c2-substitution-linked.prg",
        "elf": LINK / "lisp65-c2-substitution-linked.prg.elf",
        "window": LINK / "c2-product-kernal-window.bin",
        "boot_family": LINK / "runtime-overlays-boot-final.bin",
        "session_family":
            CARRIER / CARRIER_BASENAME,
        "shelf": shelf,
        "c2d": (
            LINK / "fresh-c2-lite-prelink-gates/v6-semantics/"
            "initial.c2d-v6.bin"),
        "bank2_static": (
            LINK / "fresh-c2-lite-prelink-gates/v6-semantics/"
            "bank2-static-code.bin"),
        "contract": LINK / "resolved-profile.txt",
        "stage_header": LINK / "stage-config.h",
    }


def validate_authority() -> dict[str, Path]:
    p = paths()
    for name, path in p.items():
        require(path.is_file(), f"missing {name}: {path}")
    link = read_json(LINK_RECEIPT)
    carrier = read_json(CARRIER_RECEIPT)
    contract = read_json(CONTRACT)
    artifacts = read_json(ARTIFACTS)
    require(
        sha(p["product"]) == PRODUCT_SHA
        and link["status"] ==
            "passed-link58-matrix-addenda-product-identity-hardware-not-run"
        and link["product_identity"]["product"]["sha256"] == PRODUCT_SHA
        and carrier["status"] == CARRIER_RECEIPT_STATUS
        and carrier["construction"]["product_bytes_changed"] == 0
        and carrier["construction"]["session_family_size_delta"] == 0
        and carrier["construction"]["external_relocation_sites_rebound"] == 7
        and carrier["construction"]["whole_family_crc16"] == "0xd387"
        and contract["status"] == "owner-reviewed-fixture-contract"
        and contract["hardware_protocol"]["freezer_roundtrips"] == 4
        and FIRST_RED_RECEIPT.is_file()
        and ZERO_JOURNAL_FIRST_RED_RECEIPT.is_file()
        and CROSS_IDENTITY_FIRST_RED_RECEIPT.is_file()
        and artifacts["artifacts"]["shelf"]["sha256"] == sha(p["shelf"]),
        "Link-58 C1 fixture authority is incomplete")
    host = link["fresh_prelink_gates"]["c2d_v6_host_semantics"]["artifacts"]
    require(
        host["c2d"]["sha256"] == sha(p["c2d"])
        and host["code"]["sha256"] == sha(p["bank2_static"]),
        "C2-lite C2D/Bank-2 plane binding drift")
    HW.verify_c2d_product_identity(p, ARTIFACTS)
    return p


def boot_stage(p: dict[str, Path], out: Path) -> tuple[Path, dict[str, Any]]:
    elf_symbols = HW.symbols(p["elf"], bank3_bootstrap=True)
    start = elf_symbols["__lisp65_workbench_overlay_start"]
    end = elf_symbols["__lisp65_workbench_overlay_end"]
    entry = elf_symbols["vm_workbench_boot_overlay_entry"]
    first_start = elf_symbols["__lisp65_boot_bank3_stage_start"]
    first_end = elf_symbols["__lisp65_boot_bank3_stage_end"]
    first_entry = elf_symbols["vm_bank3_boot_stage_entry"]
    require(
        0 < start <= entry < end <= 0x10000
        and 0 < first_start <= first_entry < first_end <= 0x10000,
        "two-record boot stage ELF geometry is invalid")

    def section(name: str, output: Path) -> bytes:
        scratch = out / ("source-" + name.strip(".") + ".elf")
        normalized = out / ("normalized-" + name.strip(".") + ".discard")
        shutil.copyfile(p["elf"], scratch)
        HW.run([
            str(HW.OBJCOPY), "--dump-section", f"{name}={output}",
            str(scratch), str(normalized)])
        scratch.unlink()
        normalized.unlink()
        return output.read_bytes()

    first_path = out / "boot-bank3-stage.raw.bin"
    workbench_path = out / "boot-overlay.raw.bin"
    first = section(".lisp65_boot_bank3_stage", first_path)
    workbench = section(".lisp65_workbench_overlay", workbench_path)
    require(len(first) == first_end - first_start
            and len(workbench) == end - start,
            "two-record boot stage extraction length drift")
    build_id = int(sha(p["contract"])[:8], 16)
    header = p["stage_header"].read_text(encoding="ascii")
    expected = re.search(
        r"LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID 0x([0-9a-fA-F]+)UL",
        header)
    require(expected is not None and int(expected.group(1), 16) == build_id,
            "boot-stage build ID differs from Link-58 contract")
    first_record = HW.boot_overlay_descriptor(
        build_id=build_id, start=first_start, entry=first_entry,
        payload=first) + first
    second_offset = (
        (HW.BOOT_OVERLAY_STAGE + len(first_record) + 0xff) & ~0xff
    ) - HW.BOOT_OVERLAY_STAGE
    require(second_offset >= len(first_record),
            "two-record boot-stage alignment underflow")
    second_record = HW.boot_overlay_descriptor(
        build_id=build_id, start=start, entry=entry, payload=workbench,
    ) + workbench
    result = first_record + bytes(second_offset - len(first_record)) + second_record
    stage = out / "boot-overlay.stage.bin"
    stage.write_bytes(result)
    return stage, {
        "build_id": f"0x{build_id:08x}",
        "first": {
            "vma": f"0x{first_start:04x}",
            "entry": f"0x{first_entry:04x}",
            "bytes": len(first),
            "crc16": f"0x{HW.crc16(first):04x}",
        },
        "second": {
            "vma": f"0x{start:04x}",
            "entry": f"0x{entry:04x}",
            "bytes": len(workbench),
            "crc16": f"0x{HW.crc16(workbench):04x}",
            "record_offset": second_offset,
        },
        "bytes": len(result),
    }


def prepare(out: Path) -> None:
    require(not out.exists(), f"fixture output already exists: {out}")
    p = validate_authority()
    observer_mutations = boot_observer_selftest()
    out.mkdir(parents=True)
    stage, chain = boot_stage(p, out)
    commands: dict[str, Any] = {}
    for value in range(5):
        path = out / f"command-{value}.bin"
        path.write_bytes(bytes([value]))
        commands[str(value)] = bind(path)
    zero_journal = out / "zero-c2j.bin"
    zero_journal.write_bytes(bytes(64))

    preloads = [
        bind(p["c2d"], HW.C2D_STAGE),
        bind(stage, HW.BOOT_OVERLAY_STAGE),
        bind(p["session_family"], HW.SESSION_FAMILY_STAGE),
    ]
    if "session_region1" in p:
        preloads.append(bind(
            p["session_region1"], R.REGION1_SOURCE_BASE))
    preloads.extend([
        bind(p["shelf"], HW.SHELF_STAGE),
        bind(p["boot_family"], HW.BOOT_FAMILY_STAGE),
        bind(p["window"], HW.KERNAL_WINDOW_STAGE),
        bind(zero_journal, 0x0005C640),
    ])
    deployment = {
        "format": "lisp65-c2.2-C1-Freezer-hardware-fixture-v1",
        "status": DEPLOYMENT_STATUS,
        "promotable": False,
        "claim_limit": (
            "Matrix-row C1 hardware fixture only; not a product link, "
            "promotion, acceptance-chain result or release claim."),
        "authority": {
            "link58_receipt": bind(LINK_RECEIPT),
            "carrier_receipt": bind(CARRIER_RECEIPT),
            "excluded_harness_first_red": bind(FIRST_RED_RECEIPT),
            "excluded_zero_C2J_first_red":
                bind(ZERO_JOURNAL_FIRST_RED_RECEIPT),
            "excluded_cross_identity_relocation_first_red":
                bind(CROSS_IDENTITY_FIRST_RED_RECEIPT),
            "contract": bind(CONTRACT),
            "canonical_artifacts": bind(ARTIFACTS),
        },
        "product": bind(p["product"], 0x00002001),
        "preloads": preloads,
        "bank2_static_authority": bind(p["bank2_static"]),
        "boot_chain": chain,
        "control": {
            "command_address": "0x000017e0",
            "reached_address": "0x000017e1",
            "command_artifacts": commands,
        },
        "boot_observer": {
            "required_screen_claims": [
                "visible-lisp65-prompt", "no-visible-VM-error"],
            "allowed_vm_status": [0, 1],
            "mutations_rejected": observer_mutations,
        },
        "capture_domains": {
            "bank2": {"start": "0x00020000", "bytes": 65536},
            "bank3": {"start": "0x00030000", "bytes": 65536},
            "bank5_C2D": {"start": "0x00050000", "bytes": 50816},
            "E000": {
                "start": "0x0000e000",
                "bytes": 8192,
                "thaw_volatile_addresses": [
                    "0x0000ff83", "0x0000ff84", "0x0000ff86"],
            },
            "C2J": {"start": "0x0005c640", "bytes": 64},
        },
        "cutpoints": [
            {"id": 1, "name": "journal-written",
             "form": "(defun %c1j () 't)", "call": "(%c1j)",
             "expected": "t", "continuation": "normal"},
            {"id": 2, "name": "staged-before-header",
             "form": "(defun %c1h () 't)", "call": "(%c1h)",
             "expected": "t", "continuation": "normal"},
            {"id": 3, "name": "header-before-exports",
             "form": "(defun %c1e () 't)", "call": "(%c1e)",
             "expected": "t", "continuation": "normal"},
            {"id": 4, "name": "abort-unpublish",
             "form": "(defun %c1a () 't)", "call": "(%c1a)",
             "expected": "*** vm: undefined function", "continuation": "abort"},
        ],
        "span_checks": {
            "c2d_before_boot_stage":
                HW.C2D_STAGE + p["c2d"].stat().st_size
                    <= HW.BOOT_OVERLAY_STAGE,
            "session_before_shelf":
                HW.SESSION_FAMILY_STAGE + p["session_family"].stat().st_size
                    <= HW.SHELF_STAGE,
            "region1_durable_source_disjoint_from_shelf_and_boot": (
                "session_region1" not in p
                or (
                    HW.BOOT_FAMILY_STAGE
                        + p["boot_family"].stat().st_size
                        <= R.REGION1_SOURCE_BASE
                    and R.REGION1_SOURCE_BASE
                        + p["session_region1"].stat().st_size
                        <= HW.KERNAL_WINDOW_STAGE
                )
            ),
            "shelf_before_boot_family":
                HW.SHELF_STAGE + p["shelf"].stat().st_size
                    <= HW.BOOT_FAMILY_STAGE,
            "window_at_attic_limit":
                HW.KERNAL_WINDOW_STAGE + p["window"].stat().st_size
                    == 0x08800000,
            "zero_journal_exact":
                preloads[-1]["address"] == "0x0005c640"
                    and preloads[-1]["bytes"] == 64
                    and zero_journal.read_bytes() == bytes(64),
        },
        "execution_accounting": {
            "compiler_runs": 0,
            "linker_runs": 0,
            "product_bytes_changed": 0,
            "hardware_runs": 0,
            "preceding_harness_first_red_boots": 3,
            "latency_attempts_consumed": 0,
        },
    }
    require(all(deployment["span_checks"].values()),
            "fixture preload spans overlap or drift")
    deployment_path = out / "deployment.json"
    deployment_path.write_text(
        json.dumps(deployment, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    for path in (*[out / f"command-{n}.bin" for n in range(5)],
                 zero_journal, stage, deployment_path):
        os.chmod(path, 0o444)
    print(
        "c2-c1-freezer-hw-fixture: PREPARE PASS "
        f"product={PRODUCT_SHA} session={p['session_family'].stat().st_size} "
        "roundtrips=4 hardware=not-run")


def verify(out: Path) -> None:
    validate_authority()
    deployment = read_json(out / "deployment.json")
    require(
        deployment["status"] == DEPLOYMENT_STATUS
        and deployment["product"]["sha256"] == PRODUCT_SHA
        and deployment["execution_accounting"]["hardware_runs"] == 0
        and deployment["boot_observer"]["mutations_rejected"] ==
            boot_observer_selftest()
        and len(deployment["cutpoints"]) == 4
        and all(deployment["span_checks"].values()),
        "saved C1 hardware fixture shape drift")
    for row in [deployment["product"], *deployment["preloads"]]:
        path = ROOT / row["path"]
        require(path.is_file() and path.stat().st_size == row["bytes"]
                and sha(path) == row["sha256"],
                f"saved fixture binding drift: {path}")
    carrier_artifacts = read_json(CARRIER_RECEIPT)["artifacts"]
    carrier_session = carrier_artifacts.get(
        "session_family", carrier_artifacts.get("session_main"))
    require(
        isinstance(carrier_session, dict)
        and deployment["preloads"][2]["sha256"]
            == carrier_session["sha256"],
        "saved fixture no longer carries the C1 hybrid Session family")
    print(
        "c2-c1-freezer-hw-fixture: VERIFY PASS "
        f"out={out} product={PRODUCT_SHA} hardware=not-run")


def capture_paths(out: Path, cutpoint: int, prefix: str) -> dict[str, Path]:
    root = out / f"cutpoint-{cutpoint}"
    return {
        name: root / f"{prefix}-{name}.bin"
        for name in ("bank2", "bank3", "bank5", "e000")
    }


def bound_captures(captures: dict[str, Path]) -> dict[str, Any]:
    return {name: bind(path) for name, path in captures.items()}


def load_state(out: Path) -> dict[str, Any]:
    path = out / "hardware-state.json"
    require(path.is_file(), "hardware state is absent")
    return read_json(path)


def save_state(out: Path, value: dict[str, Any]) -> None:
    path = out / "hardware-state.json"
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")


def require_captures(captures: dict[str, Path]) -> None:
    expected = {"bank2": 65536, "bank3": 65536,
                "bank5": 50816, "e000": 8192}
    for name, path in captures.items():
        require(path.is_file() and path.stat().st_size == expected[name],
                f"missing or truncated {name} capture: {path}")


def validate_boot_screen(text: str) -> None:
    normalized = text.lower()
    require("lisp65>" in normalized,
            "fixture boot did not render a usable REPL prompt")
    require("*** vm:" not in normalized,
            "fixture boot rendered a VM error instead of a REPL")


def boot_observer_selftest() -> list[str]:
    validate_boot_screen("lisp65 C2-lite\nlisp65> ")
    rejected: list[str] = []
    for name, value in (
            ("missing-prompt", "lisp65 C2-lite\n"),
            ("VM-error-before-prompt",
             "*** vm: undefined function\nlisp65> ")):
        try:
            validate_boot_screen(value)
        except FixtureError:
            rejected.append(name)
        else:
            raise FixtureError(
                f"boot-observer mutation survived: {name}")
    return rejected


def linked_byte_address(name: str) -> int:
    truth = ElfTruth.read(
        paths()["elf"],
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    symbol = truth.symbol(name)
    require(
        symbol.bytes == 1 and 0 <= symbol.value < 0x10000,
        f"linked byte symbol lacks a unique Bank-0 identity: {name}")
    return symbol.value


def observe_boot(out: Path) -> None:
    verify(out)
    require(not (out / "hardware-state.json").exists(),
            "boot observation is one-shot")
    bank0 = out / "boot-bank0.bin"
    bank2 = out / "boot-bank2.bin"
    bank3 = out / "boot-bank3.bin"
    bank5 = out / "boot-bank5.bin"
    screen_png = out / "boot-screen.png"
    screen_ansi = out / "boot-screen.ansi.txt"
    screen_text = out / "boot-screen.txt"
    for path, size in ((bank0, 65536), (bank2, 65536), (bank3, 65536),
                       (bank5, 50816)):
        require(path.is_file() and path.stat().st_size == size,
                f"boot capture absent or truncated: {path}")
    for path in (screen_png, screen_ansi, screen_text):
        require(path.is_file() and path.stat().st_size > 0,
                f"boot screen evidence absent: {path}")
    low = bank0.read_bytes()
    vm_status_address = linked_byte_address("vm_status")
    validate_boot_screen(screen_text.read_text(
        encoding="utf-8", errors="replace"))
    require(low[vm_status_address] in (0, 1),
            "fixture boot retained a non-success VM status")
    require(low[0x8c] == 1,
            "Link-58 C2 READY is not published after fixture boot")
    require(bank5.read_bytes()[50752:50816] == bytes(64),
            "C2J is not empty after fixture boot")
    static = paths()["bank2_static"].read_bytes()
    require(bank2.read_bytes()[:len(static)] == static,
            "Bank-2 target does not contain the canonical static code plane")
    state = {
        "format": "lisp65-c2.2-C1-Freezer-hardware-state-v1",
        "status": "passed-boot-ready-for-cutpoint-1",
        "product_sha256": PRODUCT_SHA,
        "device_runs": 1,
        "next_cutpoint": 1,
        "boot": {
            "ready": 1,
            "vm_status": low[vm_status_address],
            "vm_status_address": f"0x{vm_status_address:04x}",
            "screen": {
                "png": bind(screen_png),
                "ansi": bind(screen_ansi),
                "text": bind(screen_text),
                "verdict": "banner-and-usable-REPL-no-VM-error",
            },
            "C2J": "all-zero",
            "captures": {
                "bank0": bind(bank0), "bank2": bind(bank2),
                "bank3": bind(bank3), "bank5": bind(bank5),
            },
        },
        "cutpoints": [],
    }
    save_state(out, state)
    print("c2-c1-freezer-hw-fixture: BOOT PASS ready=1 next=cutpoint-1")


def observe_hold(out: Path, cutpoint: int) -> None:
    state = load_state(out)
    expected_status = (
        "passed-boot-ready-for-cutpoint-1" if cutpoint == 1 else
        f"passed-cutpoint-{cutpoint - 1}-ready-for-cutpoint-{cutpoint}")
    require(state["next_cutpoint"] == cutpoint
            and state["status"] == expected_status,
            f"cutpoint {cutpoint} was not the next fixture")
    baseline = capture_paths(out, cutpoint, "baseline")
    hold = capture_paths(out, cutpoint, "hold-before")
    require_captures(baseline)
    require_captures(hold)
    control = out / f"cutpoint-{cutpoint}/hold-before-control.bin"
    require(control.is_file() and control.stat().st_size == 2,
            "cutpoint control capture is absent")
    expected_control = bytes([cutpoint, 0 if cutpoint == 4 else cutpoint])
    require(control.read_bytes() == expected_control,
            f"cutpoint {cutpoint} did not reach its unique hold state")
    journal = hold["bank5"].read_bytes()[50752:50816]
    require(journal[:4] == b"C2J\0" and journal != bytes(64),
            f"cutpoint {cutpoint} lacks an ACTIVE C2J witness")
    if cutpoint == 4:
        require(
            hold["bank5"].read_bytes()[:48]
                == baseline["bank5"].read_bytes()[:48],
            "abort-unpublish hold did not restore the old C2D header")
    state["status"] = f"passed-cutpoint-{cutpoint}-hold-awaiting-Freezer"
    state["cutpoints"].append({
        "id": cutpoint,
        "name": read_json(out / "deployment.json")["cutpoints"][
            cutpoint - 1]["name"],
        "status": "hold-reached-awaiting-Freezer",
        "control": bind(control),
        "C2J": {
            "magic": "C2J",
            "sha256": hashlib.sha256(journal).hexdigest(),
            "bytes": len(journal),
        },
        "baseline": bound_captures(baseline),
        "hold_before_Freezer": bound_captures(hold),
    })
    save_state(out, state)
    print(
        "c2-c1-freezer-hw-fixture: HOLD PASS "
        f"cutpoint={cutpoint} C2J=ACTIVE next=physical-Freezer")


def e000_equal_except_contract(before: bytes, after: bytes) -> list[str]:
    ignored = {0xff83 - 0xe000, 0xff84 - 0xe000, 0xff86 - 0xe000}
    return [
        f"0x{0xe000 + index:04x}"
        for index, (left, right) in enumerate(zip(before, after))
        if left != right and index not in ignored
    ]


def observe_thaw(out: Path, cutpoint: int, freezer_output: str) -> None:
    state = load_state(out)
    require(
        state["next_cutpoint"] == cutpoint
        and state["status"] ==
            f"passed-cutpoint-{cutpoint}-hold-awaiting-Freezer"
        and state["cutpoints"][-1]["id"] == cutpoint,
        f"cutpoint {cutpoint} is not awaiting its Freezer observation")
    before = capture_paths(out, cutpoint, "hold-before")
    after = capture_paths(out, cutpoint, "hold-after")
    post = capture_paths(out, cutpoint, "post")
    require_captures(before)
    require_captures(after)
    require_captures(post)
    for name in ("bank2", "bank3", "bank5"):
        require(before[name].read_bytes() == after[name].read_bytes(),
                f"cutpoint {cutpoint} Freezer changed {name}")
    e000_drift = e000_equal_except_contract(
        before["e000"].read_bytes(), after["e000"].read_bytes())
    require(not e000_drift,
            f"cutpoint {cutpoint} Freezer changed bound E000 bytes: {e000_drift}")
    control = out / f"cutpoint-{cutpoint}/hold-after-control.bin"
    expected_control = bytes([cutpoint, 0 if cutpoint == 4 else cutpoint])
    require(control.is_file() and control.read_bytes() == expected_control,
            f"cutpoint {cutpoint} did not resume at the same hold")
    require(post["bank5"].read_bytes()[50752:50816] == bytes(64),
            f"cutpoint {cutpoint} continuation did not clear C2J")
    if cutpoint == 4:
        baseline = capture_paths(out, cutpoint, "baseline")
        for name in ("bank2", "bank3", "bank5"):
            require(post[name].read_bytes() == baseline[name].read_bytes(),
                    f"abort cutpoint failed exact rollback in {name}")
    row = state["cutpoints"][-1]
    row["status"] = "passed-state-awaiting-operator-call-output"
    row["Freezer_operator_observation"] = freezer_output
    row["hold_after_thaw"] = bound_captures(after)
    row["post_continuation"] = bound_captures(post)
    row["checks"] = {
        "Bank2_thaw_identity": "byteidentical",
        "Bank3_thaw_identity": "byteidentical",
        "Bank5_C2D_export_C2J_thaw_identity": "byteidentical",
        "E000_thaw_identity": "byteidentical-except-FF83-FF84-FF86-FF89",
        "same_hold_after_thaw": True,
        "C2J_cleared_last": True,
        "abort_exact_rollback": (
            "Bank2-Bank3-Bank5-byteidentical-preappend"
            if cutpoint == 4 else "not-applicable-normal-completion"),
    }
    state["status"] = f"passed-cutpoint-{cutpoint}-state-awaiting-output"
    save_state(out, state)
    print(
        "c2-c1-freezer-hw-fixture: THAW PASS "
        f"cutpoint={cutpoint} identities=4 C2J=zero "
        "next=operator-call-output")


def confirm_output(out: Path, cutpoint: int, output: str) -> None:
    state = load_state(out)
    require(
        state["next_cutpoint"] == cutpoint
        and state["status"] ==
            f"passed-cutpoint-{cutpoint}-state-awaiting-output"
        and state["cutpoints"][-1]["id"] == cutpoint,
        f"cutpoint {cutpoint} is not awaiting output")
    normalized = " ".join(output.strip().split()).lower()
    expected = (
        "t" if cutpoint < 4 else "*** vm: undefined function: %c1a")
    require(
        normalized == expected,
        f"cutpoint {cutpoint} operator output differs: "
        f"expected {expected!r}, got {normalized!r}")
    row = state["cutpoints"][-1]
    row["operator_call_output"] = output
    row["status"] = "passed"
    if cutpoint < 4:
        state["next_cutpoint"] = cutpoint + 1
        state["status"] = (
            f"passed-cutpoint-{cutpoint}-ready-for-cutpoint-{cutpoint + 1}")
        save_state(out, state)
        print(
            "c2-c1-freezer-hw-fixture: CUTPOINT PASS "
            f"cutpoint={cutpoint} next={cutpoint + 1}")
        return

    require(not HARDWARE_RECEIPT.exists(),
            "C1 hardware receipt already exists")
    state["next_cutpoint"] = None
    state["status"] = "passed-all-four-C1-Freezer-cutpoints"
    save_state(out, state)
    receipt = {
        "format": "lisp65-c2.2-link58-C1-Freezer-hardware-receipt-v1",
        "status": "passed-C1-open-transaction-Freezer-four-cutpoint-fixture",
        "matrix_row": "C1",
        "product_identity": bind(paths()["product"]),
        "diagnostic_identity": {
            "promotable": False,
            "carrier": bind(
                CARRIER / CARRIER_BASENAME),
            "resident_product_bytes_changed": 0,
        },
        "authority": {
            "contract": bind(CONTRACT),
            "link58": bind(LINK_RECEIPT),
            "carrier": bind(CARRIER_RECEIPT),
            "excluded_harness_first_red": bind(FIRST_RED_RECEIPT),
            "excluded_zero_C2J_first_red":
                bind(ZERO_JOURNAL_FIRST_RED_RECEIPT),
            "excluded_cross_identity_relocation_first_red":
                bind(CROSS_IDENTITY_FIRST_RED_RECEIPT),
            "deployment": bind(out / "deployment.json"),
        },
        "hardware": {
            "device_runs": 1,
            "preceding_excluded_harness_first_red_boots": 3,
            "Freezer_roundtrips": 4,
            "cutpoints": state["cutpoints"],
            "boot": state["boot"],
        },
        "verdict": {
            "normal_completion_definitions_callable": 3,
            "abort_definition_callable": 0,
            "C2J_zero_after_each_continuation": 4,
            "Bank2_Bank3_Bank5_thaw_identities": 12,
            "E000_identity_roundtrips": 4,
            "abort_exact_preappend_restoration": True,
        },
        "claim_limit": (
            "Closes cross-invariant matrix row C1 for the exact Link-58 "
            "identity. It is not promotion, an acceptance-chain result or "
            "a release claim."),
        "execution_accounting": {
            "hardware_runs": 1,
            "hardware_boots_total_including_excluded_first_red": 4,
            "product_links": 0,
            "diagnostic_links": 0,
            "latency_attempts_consumed": 0,
        },
        "next_gate": (
            "matrix gate may fall after document index binding; only then "
            "may the fresh R4/R5/R6/G5/G6 acceptance chain start"),
    }
    HARDWARE_RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(HARDWARE_RECEIPT, 0o444)
    print(
        "c2-c1-freezer-hw-fixture: COMPLETE "
        "cutpoints=4 roundtrips=4 matrix=C1-pass promotion=not-claimed")


def record_cutpoint2_first_red(out: Path, operator_observation: str) -> None:
    require(not CUTPOINT2_FIRST_RED_RECEIPT.exists(),
            "C1 cutpoint-2 First Red receipt already exists")
    state = load_state(out)
    resumable_after_receipt_assembly_stop = (
        state["status"] ==
            "first-red-cutpoint-2-continuation-stalled-after-thaw"
        and state["next_cutpoint"] is None
        and len(state["cutpoints"]) == 2
        and state["cutpoints"][1]["status"] ==
            "first-red-continuation-stalled-after-thaw")
    require(
        (resumable_after_receipt_assembly_stop or (
            state["status"] == "passed-cutpoint-2-hold-awaiting-Freezer"
            and state["next_cutpoint"] == 2
            and len(state["cutpoints"]) == 2))
        and state["cutpoints"][0]["status"] == "passed"
        and state["cutpoints"][0]["operator_call_output"] == "t"
        and state["cutpoints"][1]["id"] == 2,
        "hardware state is not the cutpoint-2 continuation First Red")
    root = out / "cutpoint-2"
    before = capture_paths(out, 2, "hold-before")
    after = capture_paths(out, 2, "hold-after")
    post = capture_paths(out, 2, "post")
    for captures in (before, after, post):
        require_captures(captures)
    for name in ("bank2", "bank3", "bank5"):
        require(before[name].read_bytes() == after[name].read_bytes(),
                f"cutpoint-2 thaw identity drifted in {name}")
    require(
        not e000_equal_except_contract(
            before["e000"].read_bytes(), after["e000"].read_bytes()),
        "cutpoint-2 thaw changed bound E000 bytes")
    before_journal = before["bank5"].read_bytes()[50752:50816]
    after_journal = after["bank5"].read_bytes()[50752:50816]
    post_journal = post["bank5"].read_bytes()[50752:50816]
    require(
        before_journal[:4] == b"C2J\0"
        and before_journal == after_journal == post_journal
        and post_journal != bytes(64),
        "cutpoint-2 First Red lacks an unchanged ACTIVE C2J witness")
    hold_control = root / "hold-after-control.bin"
    post_control = root / "post-first-red-control.bin"
    post_bank0 = root / "post-first-red-bank0.bin"
    screen_png = root / "post-first-red.png"
    screen_ansi = root / "post-first-red.ansi.txt"
    screen_text = root / "post-first-red.txt"
    red_png = root / "hold-after-operator-red-frame.png"
    red_ansi = root / "hold-after-operator-red-frame.ansi.txt"
    red_text = root / "hold-after-operator-red-frame.txt"
    for path in (
            hold_control, post_control, post_bank0, screen_png, screen_ansi,
            screen_text, red_png, red_ansi, red_text):
        require(path.is_file() and path.stat().st_size > 0,
                f"cutpoint-2 First Red evidence absent: {path}")
    low = post_bank0.read_bytes()
    require(
        hold_control.read_bytes() == bytes((2, 2))
        and post_control.read_bytes() == bytes((0, 2))
        and low[0x005B] == 0
        and low[RTOV_FAULT] == 0
        and low[RTOV_FAMILY] == 2
        and low[C2_READY] == 1
        and "(defun %c1h () t)" in screen_text.read_text(
            encoding="utf-8", errors="replace"),
        "cutpoint-2 post-release state is not the observed stalled continuation")
    frame_paths = [root / f"post-first-red-frame-{index}.bin"
                   for index in (1, 2, 3)]
    frame_values: list[int] = []
    for path in frame_paths:
        require(path.is_file() and path.stat().st_size == 2,
                f"frame witness absent: {path}")
        frame_values.append(int.from_bytes(path.read_bytes(), "little"))
    require(len(set(frame_values)) == 1,
            "post-release frame witness is not stable")

    carrier_path = paths()["session_family"]
    carrier_manifest_path = CARRIER / (
        "runtime-overlays-session-c1-freezer-"
        "link58-rebound-stage-bound.json")
    manifest = read_json(carrier_manifest_path)
    carrier = carrier_path.read_bytes()
    parsed = R.validate_image(
        carrier, expected_build_id=int(manifest["profile_build_id"]),
        expected_vma=0xC356, max_slice_bytes=1792, format_version=3)
    header = parsed.slices[39]
    header_payload = carrier[
        header.file_offset:header.file_offset + header.file_size]
    live_header = low[header.vma:header.vma + header.file_size]
    require(header_payload == live_header,
            "resident cutpoint-2 overlay differs from its bound carrier")

    row = state["cutpoints"][1]
    row["status"] = "first-red-continuation-stalled-after-thaw"
    row["Freezer_operator_observation"] = operator_observation
    row["hold_after_thaw"] = bound_captures(after)
    row["post_release"] = bound_captures(post)
    row["checks"] = {
        "Bank2_thaw_identity": "byteidentical",
        "Bank3_thaw_identity": "byteidentical",
        "Bank5_C2D_export_C2J_thaw_identity": "byteidentical",
        "E000_thaw_identity": "byteidentical-except-FF83-FF84-FF86-FF89",
        "same_hold_after_thaw": True,
        "release_control": "command=0 reached=2",
        "C2J_after_release": "unchanged-ACTIVE",
        "resident_header_overlay": "byteidentical-bound-slot-39",
        "frame_witness": f"stable-0x{frame_values[0]:04x}",
        "continuation": "failed-to-return-to-REPL",
    }
    state["status"] = "first-red-cutpoint-2-continuation-stalled-after-thaw"
    state["next_cutpoint"] = None
    state["first_red_receipt"] = str(
        CUTPOINT2_FIRST_RED_RECEIPT.relative_to(ROOT))
    save_state(out, state)

    receipt = {
        "format": (
            "lisp65-c2.2-link58-C1-Freezer-cutpoint2-"
            "continuation-hardware-first-red-v1"),
        "status": (
            "first-red-C1-staged-before-header-"
            "continuation-stalled-after-thaw"),
        "matrix_row": "C1",
        "promotable": False,
        "authority": {
            "contract": bind(CONTRACT),
            "link58": bind(LINK_RECEIPT),
            "carrier": bind(CARRIER_RECEIPT),
            "deployment": bind(out / "deployment.json"),
            "hardware_state": bind(out / "hardware-state.json"),
        },
        "identity": {
            "product": bind(paths()["product"]),
            "diagnostic_carrier": bind(carrier_path),
            "product_bytes_changed": 0,
        },
        "hardware": {
            "device_runs": 1,
            "cutpoint_1": "passed-t",
            "cutpoint_2": {
                "state": "staged-before-header",
                "operator_observation": operator_observation,
                "thaw_identity": "passed-four-domains",
                "release_control_before": [2, 2],
                "release_control_after": [0, 2],
                "vm_status": low[0x005B],
                "rtov_fault": low[RTOV_FAULT],
                "rtov_family": low[RTOV_FAMILY],
                "c2_ready": low[C2_READY],
                "C2J": {
                    "state": "unchanged-ACTIVE-before-after-post-release",
                    "bytes": C2J_BYTES,
                    "sha256": hashlib.sha256(post_journal).hexdigest(),
                },
                "resident_overlay": {
                    "slot": 39,
                    "vma": f"0x{header.vma:04x}",
                    "bytes": header.file_size,
                    "identity": "byteidentical-bound-carrier-payload",
                    "sha256": hashlib.sha256(live_header).hexdigest(),
                },
                "frame_witnesses": frame_values,
                "screen": {
                    "hold_after_operator": {
                        "png": bind(red_png), "ansi": bind(red_ansi),
                        "text": bind(red_text),
                    },
                    "post_release": {
                        "png": bind(screen_png), "ansi": bind(screen_ansi),
                        "text": bind(screen_text),
                    },
                },
            },
        },
        "captures": {
            "hold_before": bound_captures(before),
            "hold_after_thaw": bound_captures(after),
            "post_release": bound_captures(post),
            "post_release_bank0": bind(post_bank0),
            "hold_control": bind(hold_control),
            "post_release_control": bind(post_control),
            "frame_witnesses": [bind(path) for path in frame_paths],
        },
        "verdict": {
            "freeze_thaw_storage_identity": "passed",
            "continuation_liveness": "failed",
            "journal_cleanup": "not-reached-C2J-remained-ACTIVE",
            "matrix_C1": "OPEN-first-red",
            "cutpoints_3_and_4": "not-run",
            "latency_attempts_consumed": 0,
        },
        "diagnosis_boundary": (
            "The evidence proves a state-specific continuation/liveness "
            "failure after a byte-identical thaw at staged-before-header. "
            "It does not yet distinguish a Freezer resume-state defect from "
            "a violated assumption in the non-promotable hold carrier."),
        "operator_protocol_correction": {
            "actual_return_key": "F3",
            "old_instruction": "F",
            "harness_instruction": "corrected-to-F3",
            "product_bytes_changed": 0,
        },
        "claim_limit": (
            "C1 First Red only. No matrix closure, promotion, fresh "
            "acceptance-chain result or release claim."),
        "next_gate": (
            "Class-C review of the cutpoint-2 continuation state before any "
            "new diagnostic build or hardware run"),
    }
    CUTPOINT2_FIRST_RED_RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(CUTPOINT2_FIRST_RED_RECEIPT, 0o444)
    print(
        "c2-c1-freezer-hw-fixture: FIRST RED RECORDED "
        "cutpoint=2 thaw-identities=4 continuation=stalled "
        "C2J=ACTIVE matrix-C1=OPEN")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=("prepare", "verify", "observe-boot", "observe-hold",
                 "observe-thaw", "confirm-output",
                 "record-cutpoint2-first-red"))
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--cutpoint", type=int, choices=(1, 2, 3, 4))
    parser.add_argument("--freezer-output")
    parser.add_argument("--output")
    parser.add_argument("--operator-observation")
    args = parser.parse_args()
    try:
        if args.mode == "prepare":
            prepare(args.out.resolve())
        elif args.mode == "verify":
            verify(args.out.resolve())
        elif args.mode == "observe-boot":
            observe_boot(args.out.resolve())
        elif args.mode == "observe-hold":
            require(args.cutpoint is not None, "--cutpoint is required")
            observe_hold(args.out.resolve(), args.cutpoint)
        elif args.mode == "observe-thaw":
            require(args.cutpoint is not None, "--cutpoint is required")
            require(args.freezer_output is not None,
                    "--freezer-output is required")
            observe_thaw(
                args.out.resolve(), args.cutpoint, args.freezer_output)
        elif args.mode == "record-cutpoint2-first-red":
            require(args.operator_observation is not None,
                    "--operator-observation is required")
            record_cutpoint2_first_red(
                args.out.resolve(), args.operator_observation)
        else:
            require(args.cutpoint is not None, "--cutpoint is required")
            require(args.output is not None, "--output is required")
            confirm_output(args.out.resolve(), args.cutpoint, args.output)
    except (
        FixtureError, HW.PreSmokeError, OSError, ValueError, KeyError,
        json.JSONDecodeError,
    ) as error:
        print("c2-c1-freezer-hw-fixture: FIRST RED: " + str(error))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
