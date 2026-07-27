#!/usr/bin/env python3
"""Attribute Link-64 C2D-reader bounds and prepare rejection-edge holds."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import runtime_overlay_bank as R  # noqa: E402
import c2_link64_slot39_threshold_hold as H  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PRODUCT_ELF = H.PRODUCT_ELF
DONOR_ELF = ROOT / (
    "build/c2.2/substitution/"
    "link64-c1-freezer-cutpoints-WPLTO-donor-NONPROMOTABLE/"
    "lisp65-c2-substitution-linked.prg.elf")
WINDOW = ROOT / (
    "build/c2.2/substitution/"
    "product-link-64-nonlto-stateless-completion-length/"
    "c2-product-kernal-window.bin")
READER_RETURN_RECEIPT = EVIDENCE / (
    "c2.2-link64-slot39-reader-return-hold-hardware-receipt.json")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link64-c2d-reader-bounds-hold-NONPROMOTABLE")
ORIGINAL_READER = OUT / "c2-stream-c2d-read-original.bin"
PATCHED_READER = OUT / "c2-stream-c2d-read-bounds-holds.bin"
MANIFEST = OUT / "manifest.json"
RECEIPT = EVIDENCE / (
    "c2.2-link64-c2d-reader-operand-bounds-host-ELF-attribution.json")
HW_OUT = ROOT / (
    "build/c2.2/hardware-link64-c2d-reader-bounds-hold-NONPROMOTABLE")
DEPLOYMENT = HW_OUT / "deployment.json"
HARDWARE_RECEIPT = EVIDENCE / (
    "c2.2-link64-c2d-reader-bounds-hold-hardware-receipt.json")
HARDWARE_DRIVER = ROOT / "scripts/c2-link64-c2d-reader-bounds-hold-hw.sh"

READER_VMA = 0xE691
READER_BYTES = 87
REGION_END = 0xC680
EXPECTED_OFFSET = 0xC640
EXPECTED_LENGTH = 64
PATCHES = (
    # Each target byte makes only its own reject edge self-loop.
    (0xE6A3, 0xE0, 0xA2, "offset-low-overflow"),
    (0xE6AC, 0xE0, 0xAB, "offset-high-overflow"),
    (0xE6C2, 0x1D, 0xFE, "length-low-overflow"),
    (0xE6E7, 0xF8, 0xFE, "length-high-overflow"),
)
CALL_ZP_ADDRESS = 0x04
CALL_ZP_BYTES = 8
RECORD_ADDRESS = 0xC17C
C2J_ADDRESS = 0x0005C640
TRACE_ADDRESS = 0xC1F0
FRAME_ADDRESS = 0xFF83


class BoundsHoldError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise BoundsHoldError(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def data(path: Path) -> bytes:
    require(path.is_file() and not path.is_symlink(),
            f"authority absent or not regular: {path}")
    return path.read_bytes()


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    value = data(path)
    row: dict[str, Any] = {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(value),
        "sha256": sha_bytes(value),
    }
    if address is not None:
        row["address"] = f"0x{address:08x}"
    return row


def load(path: Path) -> dict[str, Any]:
    value = json.loads(data(path))
    require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def write(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(data(path) == value, f"generated artifact differs: {path}")
        return
    path.write_bytes(value)
    path.chmod(0o444)


def write_json(path: Path, value: dict[str, Any]) -> None:
    write(
        path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode())


def symbol_body(truth: ElfTruth, name: str) -> tuple[Any, bytes]:
    symbol = truth.symbol(name)
    section = truth.section(symbol.section)
    body = truth.section_bytes(symbol.section)
    offset = symbol.value - section.address
    return symbol, body[offset:offset + symbol.bytes]


def accepted(offset: int, length: int) -> bool:
    return (
        0 <= offset <= REGION_END
        and 0 <= length <= REGION_END - offset)


def boundary_oracle() -> dict[str, Any]:
    checked = 0
    for offset in range(0x10000):
        if offset <= REGION_END:
            remaining = REGION_END - offset
            candidates = {0, remaining}
            if remaining:
                candidates.add(remaining - 1)
            if remaining < 0xFFFF:
                candidates.add(remaining + 1)
        else:
            candidates = {0, 1, 0xFFFF}
        for length in candidates:
            expected = (
                offset <= REGION_END
                and length <= REGION_END - offset)
            require(
                accepted(offset, length) == expected,
                f"bounds oracle mismatch: {offset:04x}/{length:04x}")
            checked += 1
    require(
        accepted(EXPECTED_OFFSET, EXPECTED_LENGTH)
        and not accepted(EXPECTED_OFFSET, EXPECTED_LENGTH + 1)
        and accepted(REGION_END, 0)
        and not accepted(REGION_END, 1)
        and not accepted(REGION_END + 1, 0),
        "exact-meet boundary cases drift")
    return {
        "boundary_cases_checked": checked,
        "exact_meet": {
            "offset": f"0x{EXPECTED_OFFSET:04x}",
            "length": EXPECTED_LENGTH,
            "end": f"0x{EXPECTED_OFFSET + EXPECTED_LENGTH:04x}",
            "accepted": True,
        },
        "one_byte_over": {
            "offset": f"0x{EXPECTED_OFFSET:04x}",
            "length": EXPECTED_LENGTH + 1,
            "accepted": False,
        },
        "zero_at_end": {
            "offset": f"0x{REGION_END:04x}",
            "length": 0,
            "accepted": True,
        },
    }


def elf_attribution() -> tuple[dict[str, Any], bytes, bytes]:
    product = ElfTruth.read(
        PRODUCT_ELF, llvm_readobj=H.LENGTH.READOBJ,
        include_section_data=True)
    donor = ElfTruth.read(
        DONOR_ELF, llvm_readobj=H.LENGTH.READOBJ,
        include_section_data=True)
    reader, reader_body = symbol_body(product, "c2_stream_c2d_read")
    donor_reader, donor_reader_body = symbol_body(
        donor, "c2_stream_c2d_read")
    poll, poll_body = symbol_body(donor, "c2_completion_poll")
    leaf, leaf_body = symbol_body(donor, "c2_completion_mode_length")
    require(
        reader.value == donor_reader.value == READER_VMA
        and reader.bytes == donor_reader.bytes == READER_BYTES
        and reader_body == donor_reader_body
        and data(WINDOW)[READER_VMA - 0xE000:
                         READER_VMA - 0xE000 + READER_BYTES] == reader_body,
        "reader identity differs across product/donor/window")
    require(
        reader_body == bytes.fromhex(
            "850b860aa200a40ac0c6d008a8c081900c4ce0e6"
            "a40ac0c690034ce0e638a980e50b8508a9c6e50a"
            "c507d025a408c406901da905a6048608a6058609"
            "a60a8604a6068605a6078606a60b20c4b5a2018a"
            "60c507b0dd80f8"),
        "linked reader comparison body drift")

    exact_setup = bytes.fromhex(
        "a2c68621a2408620")
    call_setup = bytes.fromhex(
        "a51f2056c38506a61a8604a61b86056407a621a5202091e6")
    require(
        exact_setup in poll_body and call_setup in poll_body
        and leaf.value == 0xC356 and leaf.bytes == 27
        and leaf_body == bytes.fromhex(
            "c9a19012c9a5b00ec9a2f005a940a30060"
            "a930a30060a900a30060"),
        "linked caller or stateless length leaf drift")

    patched = bytearray(reader_body)
    patch_rows: list[dict[str, Any]] = []
    for address, before, after, reason in PATCHES:
        index = address - READER_VMA
        require(patched[index] == before,
                f"reader patch authority drift at {address:04x}")
        patched[index] = after
        patch_rows.append({
            "address": f"0x{address:04x}",
            "reader_offset": index,
            "before": f"0x{before:02x}",
            "after": f"0x{after:02x}",
            "reject_class": reason,
        })
    changed = [
        index for index, (left, right)
        in enumerate(zip(reader_body, patched)) if left != right
    ]
    require(
        changed == [address - READER_VMA for address, *_ in PATCHES],
        "reader hold changed outside four target operands")

    oracle = boundary_oracle()
    return ({
        "reader": {
            "symbol": reader.name,
            "address": f"0x{reader.value:04x}",
            "bytes": reader.bytes,
            "sha256": sha_bytes(reader_body),
            "byteidentical_product_donor_window": True,
        },
        "exact_meet_comparison": {
            "source_rule":
                "offset > $c680 || length > ($c680 - offset) rejects",
            "linked_rule": (
                "subtract $c680-offset; reject high word only when "
                "remaining<length, or equal-high low word via CPY/BCC; "
                "equality is accepted"),
            "linked_low_compare": "CPY $06 at $e6bf; BCC $e6e0 at $e6c1",
            "verdict": "exact-meet rejection hypothesis disproved",
            **oracle,
        },
        "caller_dataflow": {
            "ACTIVE_offset_materialization":
                "$c782..$c788 writes __rc31=$c6, __rc30=$40",
            "ACTIVE_length_materialization":
                "$c813 call to 27-byte stateless leaf returns $40; "
                "$c818 writes __rc4=$40 and $c822 writes __rc5=$00",
            "call_edge":
                "$c824 X=__rc31, $c826 A=__rc30, $c828 JSR $e691",
            "intervening_general_calls": 0,
            "only_intervening_leaf":
                "c2_completion_mode_length; touches A and Z only",
            "linked_expected_tuple":
                "offset=$c640, length=$0040, exact end=$c680",
        },
        "hardware_contradiction": {
            "prior_result":
                "$c82c discriminator proved c2_stream_c2d_read returned 0",
            "consequence": (
                "the linked comparison is not an off-by-one; at least one "
                "runtime operand at the reader differs from its linked last "
                "writer in the failing episode"),
        },
        "next_discriminator": {
            "method": (
                "after clean REPL, patch only the four reject-edge target "
                "operands in live $e000 code; a rejection self-loops while "
                "saved entry offset $0a/$0b and length $06/$07 remain "
                "memory-stable"),
            "patches": patch_rows,
            "live_executable_bytes_changed": len(changed),
            "product_file_bytes_changed": 0,
            "capacity_delta": 0,
            "capture": {
                "address": "0x0004",
                "bytes": 8,
                "fields": {
                    "destination": "$04/$05",
                    "length": "$06/$07",
                    "saved_offset_high": "$0a",
                    "saved_offset_low": "$0b",
                },
            },
            "outcomes": {
                "hang": (
                    "a bounds-reject edge fired; captured operands identify "
                    "offset versus length corruption"),
                "no_hang": (
                    "the intermittent reader rejection did not recur in "
                    "this episode; no product inference"),
            },
        },
    }, reader_body, bytes(patched))


def prepare() -> dict[str, Any]:
    source, base_deployment = H.validate_authority()
    prior = load(READER_RETURN_RECEIPT)
    require(
        prior["hardware_First_Red"]["binary_discriminator"]["answer"]
            == "c2_stream_c2d_read returned zero"
        and prior["hardware_First_Red"]["postmortem"][
            "runtime_slot39_fully_wiped"] is True,
        "reader-return hardware authority drift")
    attribution, original, patched = elf_attribution()
    write(ORIGINAL_READER, original)
    write(PATCHED_READER, patched)
    patch_files: list[dict[str, Any]] = []
    for address, _before, after, reason in PATCHES:
        path = OUT / f"patch-{address:04x}.bin"
        write(path, bytes([after]))
        patch_files.append({
            **bind(path, address),
            "reject_class": reason,
        })
    write_json(MANIFEST, {
        "format": "lisp65-Link64-c2d-reader-bounds-hold-manifest-v1",
        "status": "ready-nonpromotable-live-rejection-holds",
        "promotable": False,
        "original_reader": bind(ORIGINAL_READER, READER_VMA),
        "patched_reader": bind(PATCHED_READER, READER_VMA),
        "live_patch_bytes": patch_files,
    })
    write_json(RECEIPT, {
        "format":
            "lisp65-c2.2-Link64-c2d-reader-operand-bounds-"
            "host-ELF-attribution-v1",
        "recorded_on": "2026-07-26",
        "status":
            "passed-exact-meet-accepted-runtime-operands-remain",
        "promotable": False,
        "authority": {
            "reader_return_hardware_receipt": bind(READER_RETURN_RECEIPT),
            "product_ELF": bind(PRODUCT_ELF),
            "donor_ELF": bind(DONOR_ELF),
            "window": bind(WINDOW, 0x087FE000),
            "source_carrier": bind(H.BASE_CARRIER, 0x08000000),
            "source_deployment": bind(H.BASE_DEPLOYMENT),
            "driver": bind(Path(__file__)),
            "hardware_driver": bind(HARDWARE_DRIVER),
        },
        "attribution": attribution,
        "candidate": {
            "manifest": bind(MANIFEST),
            "original_reader": bind(ORIGINAL_READER, READER_VMA),
            "patched_reader": bind(PATCHED_READER, READER_VMA),
            "patch_files": patch_files,
            "identity_separate_from_Link64": True,
            "lifecycle": "discard after one diagnostic outcome",
        },
        "construction": {
            "product_file_bytes_changed": 0,
            "compiler_runs": 0,
            "linker_runs": 0,
            "hardware_runs": 0,
            "all_capacity_deltas": 0,
        },
        "claim_limit": (
            "Host/ELF bounds attribution and nonpromotable live-patch "
            "feasibility only. C1 remains OPEN."),
    })
    write_json(DEPLOYMENT, {
        "format":
            "lisp65-c2.2-Link64-c2d-reader-bounds-hold-hardware-v1",
        "recorded_on": "2026-07-26",
        "status": "ready-authorized-nonpromotable-hardware",
        "promotable": False,
        "authority": {
            "attribution_receipt": bind(RECEIPT),
            "manifest": bind(MANIFEST),
            "source_deployment": bind(H.BASE_DEPLOYMENT),
        },
        "product": base_deployment["product"],
        "preloads": base_deployment["preloads"],
        "live_patch": {
            "apply_after_clean_REPL": True,
            "original_reader": bind(ORIGINAL_READER, READER_VMA),
            "patched_reader": bind(PATCHED_READER, READER_VMA),
            "patch_files": patch_files,
        },
        "test": {
            "form": "(defun %c1e () (quote t))",
            "capture_intervals_seconds": [0, 1, 5],
        },
        "capture_domains": {
            "reader_arguments": {
                "address": f"0x{CALL_ZP_ADDRESS:08x}",
                "bytes": CALL_ZP_BYTES,
            },
            "reader_code": {
                "address": f"0x{READER_VMA:08x}",
                "bytes": READER_BYTES,
            },
            "completion_record": {
                "address": f"0x{RECORD_ADDRESS:08x}", "bytes": 32},
            "target_C2J": {
                "address": f"0x{C2J_ADDRESS:08x}", "bytes": 64},
            "phase_trace": {
                "address": f"0x{TRACE_ADDRESS:08x}", "bytes": 8},
            "current_frame": {
                "address": f"0x{FRAME_ADDRESS:08x}", "bytes": 5},
        },
        "execution_accounting": {
            "product_links": 0,
            "compiler_runs": 0,
            "hardware_runs": 0,
            "latency_attempts_consumed": 0,
        },
        "claim_limit": (
            "Nonpromotable live bounds-reject holds only; C1 OPEN."),
    })
    return {
        "status": "ready",
        "exact_meet": "accepted",
        "live_patch_bytes": len(PATCHES),
        "product_file_delta": 0,
        "capacity_delta": 0,
    }


def verify() -> dict[str, Any]:
    receipt = load(RECEIPT)
    deployment = load(DEPLOYMENT)
    attribution, original, patched = elf_attribution()
    require(
        receipt["status"]
            == "passed-exact-meet-accepted-runtime-operands-remain"
        and receipt["authority"]["driver"]["sha256"]
            == sha_bytes(data(Path(__file__)))
        and deployment["authority"]["attribution_receipt"]["sha256"]
            == sha_bytes(data(RECEIPT))
        and data(ORIGINAL_READER) == original
        and data(PATCHED_READER) == patched
        and receipt["attribution"] == attribution,
        "reader bounds deployment binding drift")
    for row in deployment["preloads"]:
        path = ROOT / row["path"]
        require(
            len(data(path)) == row["bytes"]
            and sha_bytes(data(path)) == row["sha256"],
            f"reader bounds preload drift: {path}")
    for address, _before, after, _reason in PATCHES:
        require(
            data(OUT / f"patch-{address:04x}.bin") == bytes([after]),
            f"reader bounds patch drift: {address:04x}")
    return {
        "status": "verified",
        "exact_meet": "accepted",
        "live_patch_bytes": len(PATCHES),
    }


def evaluate_hang() -> dict[str, Any]:
    verify()
    timing = load(HW_OUT / "capture-times.json")
    require(timing["interval_seconds"] == [0, 1, 5],
            "reader bounds capture timing drift")
    rows: list[dict[str, Any]] = []
    args_values: list[bytes] = []
    fixed: dict[str, list[bytes]] = {
        name: [] for name in (
            "reader-code", "completion-record", "c2j", "trace")
    }
    frames: list[int] = []
    for index in range(1, 4):
        directory = HW_OUT / f"capture-{index}"
        args = data(directory / "reader-args.bin")
        code = data(directory / "reader-code.bin")
        record = data(directory / "completion-record.bin")
        c2j = data(directory / "c2j.bin")
        trace = data(directory / "trace.bin")
        frame = data(directory / "frame.bin")
        require(
            len(args) == CALL_ZP_BYTES and len(code) == READER_BYTES
            and len(record) == 32 and len(c2j) == 64
            and len(trace) == 8 and len(frame) == 5
            and code == data(PATCHED_READER) and trace[4] == 39,
            f"reader bounds capture {index} drift")
        offset = args[7] | args[6] << 8
        length = args[2] | args[3] << 8
        destination = args[0] | args[1] << 8
        args_values.append(args)
        for name, value in (
                ("reader-code", code), ("completion-record", record),
                ("c2j", c2j), ("trace", trace)):
            fixed[name].append(value)
        current_frame = int.from_bytes(frame[:2], "little")
        frames.append(current_frame)
        rows.append({
            "index": index,
            "captured_at_utc": timing["captures"][index - 1]["utc"],
            "offset": f"0x{offset:04x}",
            "length": length,
            "destination": f"0x{destination:04x}",
            "bounds_accepts": accepted(offset, length),
            "current_frame": f"0x{current_frame:04x}",
        })
    require(
        len({sha_bytes(value) for value in args_values}) == 1
        and all(len({sha_bytes(value) for value in values}) == 1
                for values in fixed.values())
        and frames[0] < frames[1] < frames[2],
        "reader bounds witnesses were not stable with progressing frames")
    args = args_values[0]
    offset = args[7] | args[6] << 8
    length = args[2] | args[3] << 8
    require(not accepted(offset, length),
            "reject-edge hold captured a tuple the linked bounds accept")
    if offset > REGION_END:
        classification = "runtime-offset-out-of-range"
    else:
        classification = "runtime-length-exceeds-remaining-region"
    screen = data(HW_OUT / "reader-bounds-screen.txt").decode("utf-8")
    require(
        "(defun %c1e () (quote t))" in screen
        and "*** vm:" not in screen,
        "reader bounds screen does not establish the rejection hold")
    value = {
        "format":
            "lisp65-c2.2-Link64-c2d-reader-bounds-hold-hardware-v1",
        "recorded_on": "2026-07-26",
        "status": f"completed-{classification}",
        "promotable": False,
        "authority": {
            "attribution_receipt": bind(RECEIPT),
            "deployment": bind(DEPLOYMENT),
            "hardware_driver": bind(HARDWARE_DRIVER),
            "evaluator": bind(Path(__file__)),
        },
        "answer": {
            "classification": classification,
            "captured_offset": f"0x{offset:04x}",
            "captured_length": length,
            "linked_expected_offset": f"0x{EXPECTED_OFFSET:04x}",
            "linked_expected_length": EXPECTED_LENGTH,
            "exact_meet_comparison_exonerated": True,
        },
        "time_separated_captures": rows,
        "stable_witnesses": {
            "reader_arguments_sha256": sha_bytes(args),
            **{
                f"{name}_sha256": sha_bytes(values[0])
                for name, values in fixed.items()
            },
            "byteidentical_across_three": True,
            "frames_progressed": True,
        },
        "execution_accounting": {
            "product_links": 0,
            "compiler_runs": 0,
            "diagnostic_hardware_runs": 1,
            "latency_attempts_consumed": 0,
        },
        "diagnostic_lifecycle": {
            "eligible_for_promotion": False,
            "state": "discarded-after-capture",
        },
        "claim_limit": (
            "Reader operand attribution only. C1 remains OPEN; no "
            "acceptance, promotion or release claim."),
    }
    encoded = (
        json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    if HARDWARE_RECEIPT.exists():
        require(data(HARDWARE_RECEIPT) == encoded,
                "sealed reader bounds hardware receipt drift")
    else:
        HARDWARE_RECEIPT.write_bytes(encoded)
    print(
        "c2-link64-reader-bounds: PASS "
        f"{classification} offset=0x{offset:04x} length={length}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", nargs="?", default="prepare",
        choices=("prepare", "verify", "evaluate-hang"))
    action = parser.parse_args().action
    value = {
        "prepare": prepare,
        "verify": verify,
        "evaluate-hang": evaluate_hang,
    }[action]()
    if action != "evaluate-hang":
        print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (BoundsHoldError, H.HoldError, R.OverlayBankError, OSError,
            ValueError, KeyError, json.JSONDecodeError) as error:
        print("c2-link64-reader-bounds: FIRST RED: " + str(error))
        raise SystemExit(2)
