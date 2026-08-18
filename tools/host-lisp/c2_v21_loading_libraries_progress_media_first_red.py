#!/usr/bin/env python3
"""Bind the Link-107 progress contact as a pre-install media First Red."""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_defstruct_terminal_ingress_sister as SISTER  # noqa: E402
import c2_v150_stager_liveness_successor as LIVE  # noqa: E402
import c2_v21_loading_libraries_progress_contact as CONTACT  # noqa: E402
import c2_v21_loading_libraries_progress_rebind as RING  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = ARCH / (
    "c2.3-v2.1-loading-libraries-progress-media-first-red-receipt.json")
FORMAT = "lisp65-c2.3-v2.1-loading-progress-media-first-red-v1"
DIAG_STAGER_ELF = RING.OUT / "autoboot.c65.elf"
CONTROL_STAGER_ELF = (
    ROOT / "build/c2.3/v2.1-dependent-vma-media/shared-system/"
    "autoboot.c65.elf")
PRODUCT_READBACK = CONTACT.OUT / "product-readback.d81"
LIBRARY_READBACK = CONTACT.OUT / "library-readback.d81"
STATE_BYTES = 66


class FirstRedError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise FirstRedError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def packed_stager_closure() -> dict[str, Any]:
    control = LIVE.delivered_liveness_gate(CONTROL_STAGER_ELF.resolve())
    diagnostic_rejection = None
    try:
        LIVE.delivered_liveness_gate(DIAG_STAGER_ELF.resolve())
    except LIVE.SuccessorError as error:
        diagnostic_rejection = str(error)
    source = Path(RING.RING.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    build = next(node for node in tree.body
                 if isinstance(node, ast.FunctionDef)
                 and node.name == "build_medium")
    calls = [node for node in ast.walk(build) if isinstance(node, ast.Call)
             and ast.unparse(node.func) == "MEDIA.compile_stager"]
    require(
        control["result"] == "passed-actual-linked-stager-prefix"
        and diagnostic_rejection ==
            "actual stager ELF lacks the unique liveness-prefix entry"
        and len(calls) == 1
        and not any(keyword.arg == "compile_defines"
                    for keyword in calls[0].keywords),
        "diagnostic packed-stager closure is not the named defect")
    return {
        "classification": "PACKED-STAGER-CLOSURE-INCOMPLETE",
        "control_actual_ELF_gate": control["result"],
        "diagnostic_actual_ELF_gate": "rejected",
        "diagnostic_rejection": diagnostic_rejection,
        "producer_omission": (
            "diagnostic MEDIA.compile_stager call omits the v1.5 opt-in"),
        "scope": (
            "Proves a diagnostic-media closure defect and the missing "
            "STAGING MEDIA line; it does not by itself name which cold-"
            "stager failure branch produced DISK ERROR."),
    }


def descriptor_closure() -> dict[str, Any]:
    roles = SISTER.medium_roles(RING.DIAG_D81, RING.OUT / "first-red-roles")
    paths = SISTER.role_paths(roles)
    descriptor = paths["boot.id"].read_bytes()
    rows, build_id, profile_id = SISTER.descriptor_rows(descriptor, paths)
    SISTER.target_descriptor_check(
        descriptor, rows, descriptor_build_id=build_id,
        stager_build_id=build_id)
    return {"result": "passed-13-of-13-host-descriptor-and-payload-identity",
            "roles": len(roles), "descriptor_rows": len(rows),
            "build_id": f"0x{build_id:08x}",
            "profile_id": f"0x{profile_id:08x}"}


def stopped_identity(raw: dict[str, Any]) -> dict[str, Any]:
    pc = int(raw["tuple"]["PC"], 0)
    truth = ElfTruth.read(DIAG_STAGER_ELF, llvm_readobj=RING.READOBJ,
                          include_section_data=True)
    symbol = truth.symbol("show_disk_error")
    require(symbol.value <= pc < symbol.value + symbol.bytes,
            "stopped PC is not the diagnostic stager error hold")
    return {"PC": f"0x{pc:04x}", "symbol": symbol.name,
            "offset": pc - symbol.value,
            "SP": raw["tuple"]["SP"], "MAPH": raw["tuple"]["MAPH"],
            "MAPL": raw["tuple"]["MAPL"]}


def derive() -> dict[str, Any]:
    raw = load(CONTACT.CAPTURE)
    state = bytes.fromhex(raw["state_hex"])
    frames = bytes.fromhex(raw["frame_counter_hex"])
    require(len(state) == STATE_BYTES and state == bytes(STATE_BYTES),
            "diagnostic ring was not wholly reset/absent")
    require(len(frames) == 2 and int.from_bytes(frames, "little") == 23,
            "closing frame sample drift")
    require(PRODUCT_READBACK.read_bytes() == RING.DIAG_D81.read_bytes()
            and LIBRARY_READBACK.read_bytes() == RING.LIBRARY_D81.read_bytes(),
            "uploaded media readback drift")
    value = {
        "format": FORMAT, "recorded_on": "2026-08-15",
        "status": "INSTRUMENT-MEDIA-FIRST-RED; CPU-RATE-UNMEASURED",
        "authority": {"ring": bind(RING.RECEIPT),
            "raw_capture": bind(CONTACT.CAPTURE),
            "product_readback": bind(PRODUCT_READBACK),
            "library_readback": bind(LIBRARY_READBACK)},
        "observation": {"owner_visible":
            "red frame; L65SYS DISK ERROR - CHECK MEDIA",
            "stopped_identity": stopped_identity(raw),
            "ring_state": "66-of-66-zero",
            "ring_arm": "absent", "ring_reset_tail": "absent",
            "closing_frame_counter": 23},
        "classification": {
            "kind": "setup/instrument-media-red",
            "product_rate_claim": False,
            "reason": (
                "The diagnostic PRG identity never reached Bank-0; no ring "
                "slot can describe Link-107 CPU transport."),
            "descriptor_closure": descriptor_closure(),
            "packed_stager_closure": packed_stager_closure()},
        "rescue_read": {
            "authorization": "required-before-device-access",
            "same_stopped_state": True, "read_only": True,
            "tuple_and_media_SHA_first": True, "stops": 0, "resumes": 0,
            "ranges": [
                {"physical": "0x000001ec..0x000001ff",
                 "purpose": "bind the surviving show_disk_error caller"},
                {"physical": "0x000037e4..0x00003993",
                 "purpose": "bind the descriptor actually loaded by stager"},
                {"physical": "0x087fe000..0x087fffff",
                 "sampling": "diagnostic-delta head/middle/tail only",
                 "purpose": "prove whether role-8 diagnostic WINDOW staged"},
                {"physical": "0x00049583..0x000495c4",
                 "derivation": (
                     "stage $040000 + PRG file offset $9583; the PRG load "
                     "address maps that offset to CPU $B582"),
                 "purpose": "prove whether diagnostic PRG reached Bank 4"}],
            "decision": {
                "descriptor_mismatch": "pre-stage media/descriptor rejection",
                "descriptor_exact_window_absent": "stage-role rejection",
                "window_exact_bank4_absent": "product-role scan/stage rejection",
                "bank4_exact_bank0_absent": "chain/copy/handoff rejection"}},
        "discipline": {"additional_device_access": 0,
            "CPU_left_stopped": True, "D1_D5_open": False},
        "claim_limit": (
            "The contact proves an instrument-media First Red and one packed-"
            "stager closure defect. It does not measure CPU transport and "
            "does not yet attribute the cold-stager failure branch."),
    }
    value["mutations"] = mutation_gate(value)
    audit(value)
    return value


def audit(value: dict[str, Any]) -> None:
    require(
        value.get("status") ==
            "INSTRUMENT-MEDIA-FIRST-RED; CPU-RATE-UNMEASURED"
        and value.get("classification", {}).get("kind") ==
            "setup/instrument-media-red"
        and value.get("classification", {}).get("product_rate_claim") is False
        and value.get("observation", {}).get("ring_state") == "66-of-66-zero"
        and value.get("classification", {}).get("packed_stager_closure", {})
            .get("diagnostic_actual_ELF_gate") == "rejected"
        and value.get("rescue_read", {}).get("authorization") ==
            "required-before-device-access"
        and value.get("discipline") == {"additional_device_access": 0,
            "CPU_left_stopped": True, "D1_D5_open": False},
        "Link-107 media First Red claim boundary drift")


def mutation_gate(base: dict[str, Any]) -> dict[str, Any]:
    cases = {
        "claim-CPU-rate": ("classification", "product_rate_claim", True),
        "call-product-red": ("classification", "kind", "product-red"),
        "invent-armed-ring": ("observation", "ring_state", "armed"),
        "accept-packed-stager": (
            "classification.packed_stager_closure",
            "diagnostic_actual_ELF_gate", "passed"),
        "preauthorize-rescue": ("rescue_read", "authorization", "authorized"),
        "add-device-access": ("discipline", "additional_device_access", 1),
        "open-D1-D5": ("discipline", "D1_D5_open", True),
    }
    rejected: list[str] = []
    for name, (section, key, replacement) in cases.items():
        trial = deepcopy(base)
        target = trial
        for part in section.split("."):
            target = target[part]
        target[key] = replacement
        try:
            audit(trial)
        except FirstRedError:
            rejected.append(name)
    require(len(rejected) == len(cases), "media First Red mutation survived")
    return {"count": len(rejected), "rejected": sorted(rejected)}


def record() -> dict[str, Any]:
    require(not RECEIPT.exists(), "media First Red receipt already exists")
    value = derive()
    RECEIPT.write_bytes(canonical(value))
    return value


def check() -> dict[str, Any]:
    value = load(RECEIPT)
    audit(value)
    require(value == derive(), "media First Red receipt drift")
    return value


def selftest() -> dict[str, Any]:
    value = derive()
    audit(value)
    require(value["mutations"]["count"] == 7,
            "media First Red mutation count drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("record", "check", "selftest"))
    args = parser.parse_args()
    value = record() if args.action == "record" else (
        check() if args.action == "check" else selftest())
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FirstRedError, LIVE.SuccessorError, OSError, KeyError,
            ValueError) as error:
        print(f"LINK 107 PROGRESS MEDIA FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
