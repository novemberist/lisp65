#!/usr/bin/env python3
"""Bind the Link-111 D2 BADOPCODE and the partial-span verifier defect.

The target row itself remains mechanism-unattributed until the preserved live
state is read.  Independently, this desk proof shows that the delivered
convergence primitive can report success after only the retained first
difference has landed while later bytes remain stale.  Existing equivalence
fixtures hide the defect by applying the primary copy atomically.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SCREEN = ROOT / (
    "build/c2.3/v2.1-terminal-screen-d2-d5/"
    "d2-define-probe-first-red.png")
ELF = ROOT / (
    "build/c2.3/v2.1-terminal-screen-lease-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
PRODUCT = ROOT / (
    "build/c2.3/v2.1-terminal-screen-media/shared-system/"
    "lisp65-product.d81")
LIBRARY = ROOT / (
    "build/c2.3/v2.1-terminal-screen-media-base/library/"
    "lisp65-library.d81")
MEDIA = ARCH / "c2.3-v2.1-terminal-screen-completion-media-receipt.json"
ASM = ROOT / "src/c2_mapped_far_convergence.s"
C_REF = ROOT / "src/c2_platform_dma.c"
GATE = ROOT / "tools/host-lisp/c2_code_window_convergence_gate.py"
EQUIV = ROOT / "tools/host-lisp/c2_mapped_far_asm_equivalence.py"
OLD_CAPTURE = ARCH / (
    "c2.3-v1.5.0-name-freight-d2-defun-badopcode-capture-receipt.json")
RECEIPT = ARCH / "c2.3-v2.1-link111-d2-partial-span-desk-receipt.json"

FORMAT = "lisp65-c2.3-v2.1-link111-D2-partial-span-desk-v1"
STATUS = "PARTIAL-SPAN-VERIFIER-DEFECT-PROVEN; TARGET-MEMBERSHIP-PENDING"
FORM = "(defun trace-probe (x) (+ x 1))"


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
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def delivered_identity() -> dict[str, Any]:
    media = load(MEDIA)
    product = bind(PRODUCT)
    library = bind(LIBRARY)
    require(
        media.get("status") ==
            "PASS: Link 111 completed and same-world clean-screen media closed"
        and media.get("media", {}).get("product_D81") == product
        and media.get("media", {}).get("library_D81") == library
        and media.get("media", {}).get("same_world") is True
        and product["sha256"] ==
            "4576a99baef4d9ed2fc1397371dc81d0a38aee26279c2fb0ad825ffca73e5e83"
        and library["sha256"] ==
            "15e4405929be0686d12c8079509fbd9e12f9314041218ed773fd57b895692060",
        "Link-111 delivered D2 identity drift")
    return {"product": product, "library": library, "same_world": True}


def partial_primary_model() -> dict[str, Any]:
    source = bytes((0x3B, 0x06, 0x01, 0x01))
    destination = bytearray((0x0B, 0x00, 0x01, 0x01))
    first = next(i for i in range(len(source)) if destination[i] != source[i])
    before = bytes(destination)
    # Legal non-atomic observation: only the first destination byte is visible
    # when the verifier next polls its retained discriminator.
    destination[first] = source[first]
    accepted = destination[first] == source[first]
    require(accepted and bytes(destination) != source,
            "partial primary no longer demonstrates false acceptance")
    return {
        "source_hex": source.hex(), "destination_before_hex": before.hex(),
        "first_difference": first,
        "destination_at_return_hex": bytes(destination).hex(),
        "primitive_returns_success": accepted,
        "full_span_converged": bytes(destination) == source,
    }


def source_and_linked_facts() -> dict[str, Any]:
    asm = ASM.read_text(encoding="utf-8")
    c_ref = C_REF.read_text(encoding="utf-8")
    gate = GATE.read_text(encoding="utf-8")
    equiv = EQUIV.read_text(encoding="utf-8")
    primary = asm.index(".Lc2_d700_primary:")
    success = asm.index("lda #1\n\trts", primary)
    body_end = asm.index("\n\t.globl c2_mapped_far_vm_code_load_converged", success)
    post_primary = asm[primary:body_end]
    require(
        "lda (__rc20),y\n\tcmp __rc27" in post_primary
        and "bne .Lc2_d700_primary_not_yet" in post_primary
        and post_primary.count("lda #1\n\trts") == 1
        and ".Lc2_d700_scan" not in post_primary,
        "assembly no longer returns on the retained byte alone")
    require(
        "while (observed[i] != expected)" in c_ref
        and "return 1u;" in c_ref[c_ref.index(
            "while (observed[i] != expected)"):]
        and "destination[:] = source" in gate
        and "memcpy(active_destination, reference_source, active_length)" in equiv,
        "reference or atomic-fixture seam drift")

    truth = ElfTruth.read(
        ELF, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=False)
    service = truth.symbol("c2_mapped_far_vm_code_load_converged")
    result = subprocess.run(
        [str(ROOT / "tools/llvm-mos/bin/llvm-objdump"), "-d",
         "--symbolize-operands", str(ELF)], cwd=ROOT, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    linked = result.stdout
    require(
        "79c9: a0 00" in linked and "79cb: b1 16" in linked
        and "79cd: c5 1d" in linked and "79d1: a9 01" in linked
        and "79d3: 60" in linked,
        "delivered ELF does not carry the one-byte success edge")
    return {
        "delivered_function": {"address": f"0x{service.value:04x}",
                               "bytes": service.bytes},
        "post_primary_full_span_rescan": False,
        "success_condition": "retained first-difference byte only",
        "fixture_primary_visibility": "atomic whole-span memcpy",
        "fixture_gap": "no prefix-only or torn primary visibility case",
    }


def capture_spec() -> dict[str, Any]:
    truth = ElfTruth.read(
        ELF, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=False)
    scratch = truth.symbol("lisp65_c2_phase_scratch")
    require(scratch.value == 0xC0C6 and scratch.bytes == 304
            and truth.symbol("c2_phase_owner").value == 0x89,
            "Link-111 stopped-state addresses drift")
    return {
        "precondition": (
            "same usable Link-111 REPL immediately after the exact D2 First "
            "Red; no intervening form, reboot, resume, mount or monitor read"),
        "operation": "one t1/register tuple, then three physical reads",
        "resume": False,
        "ranges": [
            {"start": "0x00000000", "bytes": 65536, "role": "Bank-0 state"},
            {"start": "0x00040000", "bytes": 27648, "role": "EXT/string state"},
            {"start": "0x00050000", "bytes": 50816, "role": "C2D/C2J state"},
        ],
        "installer_trace": "0xc1f4",
        "decision": {
            "torn_or_stale_staged_object":
                "this Link-111 row is a member of the proven partial-span defect",
            "byteexact_staged_object":
                "partial-span defect remains real, but this row needs a different mechanism",
        },
    }


def projection() -> dict[str, Any]:
    old = load(OLD_CAPTURE)
    require(old.get("status") == "F018B-READ-CONTENT-COMPLETION-PROVEN",
            "historical D2 control evidence drift")
    value = {
        "format": FORMAT, "recorded_on": "2026-08-16", "status": STATUS,
        "first_red": {
            "form": FORM, "result": "*** vm: bad bytecode",
            "usable_REPL_returned": True, "red_frame": False,
            "green_prefix": ["require inspect -> t", "require string-extra -> t"],
            "screen": bind(SCREEN),
        },
        "delivered_identity": delivered_identity(),
        "host_proof": {
            "partial_primary_model": partial_primary_model(),
            "source_and_linked_facts": source_and_linked_facts(),
            "defect": (
                "the convergence primitive can report success when only the "
                "retained first-difference byte has landed"),
        },
        "historical_control": {
            "receipt": bind(OLD_CAPTURE),
            "same_surface_error": "D2 defun -> VM_BADOPCODE",
            "claim_limit": "historical mechanism is not inherited by this run",
        },
        "capture": capture_spec(),
        "conclusion": {
            "product_defect_proven": True,
            "this_target_row_membership_proven": False,
            "fix_authorized": False,
            "D3_D5_open": False,
            "next": "owner authorization for the one read-only preserved-state capture",
        },
        "authority": {
            "ELF": bind(ELF), "media": bind(MEDIA), "assembly": bind(ASM),
            "C_reference": bind(C_REF), "class_gate": bind(GATE),
            "equivalence_gate": bind(EQUIV), "checker": bind(Path(__file__)),
        },
        "execution_accounting": {"device_stops": 0, "device_resumes": 0,
                                 "links": 0, "WPLTO": 0,
                                 "product_bytes_changed": 0},
    }
    validate(value)
    return value


def validate(value: dict[str, Any]) -> None:
    model = value["host_proof"]["partial_primary_model"]
    facts = value["host_proof"]["source_and_linked_facts"]
    require(value.get("format") == FORMAT and value.get("status") == STATUS,
            "attribution identity drift")
    require(model["primitive_returns_success"] is True
            and model["full_span_converged"] is False,
            "false-success proof lost")
    require(facts["post_primary_full_span_rescan"] is False
            and facts["fixture_primary_visibility"] == "atomic whole-span memcpy",
            "linked defect or fixture gap lost")
    require(value["conclusion"] == {
        "product_defect_proven": True,
        "this_target_row_membership_proven": False,
        "fix_authorized": False, "D3_D5_open": False,
        "next": "owner authorization for the one read-only preserved-state capture"},
        "claim boundary drift")
    require(value["capture"]["resume"] is False
            and len(value["capture"]["ranges"]) == 3,
            "capture scope drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-full-span": lambda x: x["host_proof"]["partial_primary_model"].__setitem__(
            "full_span_converged", True),
        "deny-false-success": lambda x: x["host_proof"]["partial_primary_model"].__setitem__(
            "primitive_returns_success", False),
        "invent-rescan": lambda x: x["host_proof"]["source_and_linked_facts"].__setitem__(
            "post_primary_full_span_rescan", True),
        "deny-atomic-fixture": lambda x: x["host_proof"]["source_and_linked_facts"].__setitem__(
            "fixture_primary_visibility", "torn"),
        "inherit-old-membership": lambda x: x["conclusion"].__setitem__(
            "this_target_row_membership_proven", True),
        "silently-authorize-fix": lambda x: x["conclusion"].__setitem__(
            "fix_authorized", True),
        "open-D3": lambda x: x["conclusion"].__setitem__("D3_D5_open", True),
        "resume": lambda x: x["capture"].__setitem__("resume", True),
        "drop-bank4": lambda x: x["capture"]["ranges"].pop(1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases), "attribution mutation survived")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("record", "check", "selftest"))
    action = parser.parse_args().action
    value = projection(); value["mutations_rejected"] = mutations(value)
    if action == "record":
        RECEIPT.write_bytes(canonical(value))
    elif action == "check":
        require(load(RECEIPT) == value, "partial-span desk receipt stale")
    else:
        require(len(value["mutations_rejected"]) == 9, "mutation count drift")
    print(f"Link-111 D2 partial-span attribution: PASS action={action} mutations=9")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"Link-111 D2 partial-span attribution: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
