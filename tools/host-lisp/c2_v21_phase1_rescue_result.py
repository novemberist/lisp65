#!/usr/bin/env python3
"""Bind the crossing-free phase-1 First Red to the MAP-mask mechanism."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any
import zlib


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CAPTURE = ROOT / "build/c2.3/v2.1-product-liveness-phase1-rescue/capture.json"
ELF = ROOT / (
    "build/c2.3/v2.1-product-loading-liveness-card/final/"
    "lisp65-c2-substitution-linked.prg.elf")
WPLTO = ROOT / "build/c2.3/v2.1-product-loading-liveness-card/receipts/wplto-raw.json"
SOURCE = ROOT / "src/optional/c2_map_cpu_read.s"
DEVICE_RECEIPT = ARCH / (
    "c2.3-v2.1-product-liveness-phase1-rescue-device-receipt.json")
RESULT_RECEIPT = ARCH / (
    "c2.3-v2.1-product-liveness-phase1-rescue-result-receipt.json")
FORMAT = "lisp65-c2.3-v2.1-phase1-rescue-result-v1"


class ResultError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResultError(message)


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


def u16(raw: bytes, at: int) -> int:
    return int.from_bytes(raw[at:at + 2], "little")


def u24(raw: bytes, at: int) -> int:
    return int.from_bytes(raw[at:at + 3], "little")


def u32(raw: bytes, at: int) -> int:
    return int.from_bytes(raw[at:at + 4], "little")


def decode_mapl(word: int) -> dict[str, Any]:
    a = word & 0xff
    x = word >> 8
    units = ((x & 0x0f) << 8) | a
    mask = x >> 4
    blocks = [index for index in range(4) if mask & (1 << index)]
    return {
        "MAPL": f"0x{word:04x}", "A": f"0x{a:02x}", "X": f"0x{x:02x}",
        "offset_units_256": f"0x{units:03x}",
        "physical_offset_low20": f"0x{units << 8:05x}",
        "block_mask": f"0x{mask:x}", "selected_blocks": blocks,
        "selected_CPU_ranges": [
            f"0x{block * 0x2000:04x}..0x{(block + 1) * 0x2000 - 1:04x}"
            for block in blocks],
    }


def ranges(capture: dict[str, Any]) -> dict[str, bytes]:
    result = {row["name"]: bytes.fromhex(row["observed_hex"])
              for row in capture["reads"]}
    require(set(result) == {"bank0-zp-stack",
            "pending-error-and-overlay-status", "c2-boot-runtime",
            "shelf-header-and-max-catalog"}, "authorized range set drift")
    require(tuple(map(len, result.values())) == (512, 9, 50, 2080),
            "authorized range length drift")
    return result


def shelf_facts(raw: bytes, runtime: bytes, wplto: dict[str, Any]) -> dict[str, Any]:
    catalog_bytes = u16(raw, 16)
    catalog = raw[32:32 + catalog_bytes]
    observed_crc = zlib.crc32(catalog) & 0xffffffff
    profile = wplto["canonical_artifact_profile_gate"]
    expected_build = int(profile["c2d_product_build_id"], 16)
    expected_crc = int(profile["c2d_catalog_crc32"], 16)
    require(
        raw[:4] == b"L65S" and raw[4:8] == bytes((4, 32, 32, 6))
        and u16(raw, 8) == 32 and u24(raw, 10) == 224
        and u24(raw, 13) == u32(runtime, 0)
        and catalog_bytes == 192
        and u32(raw, 18) == u32(runtime, 4) == observed_crc == expected_crc
        and u32(raw, 22) == expected_build and u16(raw, 26) == 1
        and raw[28:32] == bytes(4),
        "stopped Shelf header/catalog identity drift")
    return {
        "magic": "L65S", "version": raw[4], "image_count": raw[7],
        "payload_offset": u24(raw, 10), "total_bytes": u24(raw, 13),
        "catalog_bytes": catalog_bytes,
        "catalog_crc32_header": f"0x{u32(raw, 18):08x}",
        "catalog_crc32_recomputed": f"0x{observed_crc:08x}",
        "catalog_crc32_candidate": f"0x{expected_crc:08x}",
        "product_build_id": f"0x{u32(raw, 22):08x}",
        "post_stop_content_identity": "header-and-complete-catalog-exact",
        "claim_limit": (
            "Post-stop exactness excludes a persistent bad Shelf image; it "
            "does not by itself reconstruct every transient instruction fetch."),
    }


def reader_facts(truth: ElfTruth, source: str, mapl: int) -> dict[str, Any]:
    reader = truth.symbol("c2_map_cpu_read")
    shelf = truth.symbol("c2_stream_shelf_read")
    require((reader.value, reader.bytes, reader.section) ==
            (0x2277, 188, ".text") and shelf.value == 0xe79d,
            "candidate reader identity drift")
    require(
        "and #$0f\n\tsbc #0\n\tora #$40\n\tsta __rc18" in source
        and ".Lc2_cpu_map_window:\n\tlda __rc15\n\tldx __rc18" in source
        and "jsr .Lc2_cpu_map_window" in source,
        "reader MAP construction source drift")
    actual = decode_mapl(mapl)
    source_physical = 0x08100000
    cpu_window = 0x4000
    offset = ((source_physical & 0xfffff) - cpu_window) & 0xfffff
    require(offset == 0xfc000, "Shelf-to-window offset derivation drift")
    desired_a = (offset >> 8) & 0xff
    desired_x = 0x40 | ((offset >> 16) & 0x0f)
    desired_word = desired_a | desired_x << 8
    desired = decode_mapl(desired_word)
    require(
        mapl == 0xffc0 and actual["selected_blocks"] == [0, 1, 2, 3]
        and desired_word == 0x4fc0 and desired["selected_blocks"] == [2]
        and reader.value // 0x2000 == 1
        and reader.value + reader.bytes <= 0x4000,
        "captured MAP-mask mechanism drift")
    return {
        "reader": {"symbol": reader.name, "start": f"0x{reader.value:04x}",
            "end_exclusive": f"0x{reader.value + reader.bytes:04x}",
            "bytes": reader.bytes, "CPU_block": 1},
        "first_Shelf_source": f"0x{source_physical:08x}",
        "CPU_destination_window": "0x4000..0x5fff",
        "required_low20_offset": f"0x{offset:05x}",
        "captured_tuple": actual, "required_tuple": desired,
        "construction_defect": (
            "The borrow-producing SBC leaves __rc18=$ff; OR #$40 cannot "
            "clear the borrowed high mask bits. X must retain only the low "
            "offset nibble before block-2 mask bit $40 is added."),
        "control_effect": (
            "The actual mask selects block 1, so the reader at $2277 maps "
            "away while its own MAP helper returns. The subsequent fetch is "
            "from mapped Shelf address space, not the linked reader body."),
        "old_guard_gap": (
            "The linked guard compared the reader only with the intended "
            "$4000..$5fff window; it never decoded the emitted runtime tuple."),
    }


def audit(value: dict[str, Any]) -> None:
    runtime = value["runtime"]
    mechanism = value["mechanism"]
    require(
        value.get("status") == "PRODUCT-FIRST-RED: MAP-MASK-SELF-OCCLUSION"
        and value.get("decision_table") ==
            "error=0: overlay/control-transfer fault outside decoder"
        and runtime == {"phase": 1, "finished": 0, "error": 0,
                        "reserved": 0}
        and value["ordinary_state"]["c2_ready"] == 0
        and value["ordinary_state"]["mem_oom"] == 0
        and value["ordinary_state"]["lisp_error_msg"] == "0x0000"
        and mechanism["captured_tuple"]["block_mask"] == "0xf"
        and mechanism["captured_tuple"]["selected_blocks"] == [0, 1, 2, 3]
        and mechanism["required_tuple"]["MAPL"] == "0x4fc0"
        and mechanism["required_tuple"]["selected_blocks"] == [2]
        and mechanism["reader"]["CPU_block"] == 1
        and value["stack_claim"] == "forbidden-under-selected-block-0"
        and value["discipline"] == {"stops": 1, "resumes": 0,
            "runs": 0, "CPU_left_stopped": True, "D2_D5_open": False},
        "phase-1 rescue claim boundary drift")


def mutations(base: dict[str, Any]) -> dict[str, Any]:
    cases = {
        "call-transport-error": ("runtime", "error", 1),
        "call-shelf-error": ("runtime", "error", 2),
        "advance-phase": ("runtime", "phase", 2),
        "hide-actual-block1": ("mechanism.captured_tuple", "selected_blocks", [0, 2, 3]),
        "claim-safe-actual-mask": ("mechanism.captured_tuple", "block_mask", "0x4"),
        "pin-wrong-required-mapl": ("mechanism.required_tuple", "MAPL", "0xffc0"),
        "move-reader-out-of-block1": ("mechanism.reader", "CPU_block", 2),
        "interpret-underlay-stack": ("stack_claim", None, "current-frame"),
        "resume-CPU": ("discipline", "resumes", 1),
        "open-D2-D5": ("discipline", "D2_D5_open", True),
    }
    rejected: list[str] = []
    for name, (path, key, replacement) in cases.items():
        trial = deepcopy(base)
        target: Any = trial
        for part in path.split("."):
            target = target[part]
        if key is None:
            parent: Any = trial
            parts = path.split(".")
            for part in parts[:-1]:
                parent = parent[part]
            parent[parts[-1]] = replacement
        else:
            target[key] = replacement
        try:
            audit(trial)
        except ResultError:
            rejected.append(name)
    require(rejected == list(cases), "phase-1 result mutation survived")
    return {"count": len(rejected), "rejected": rejected}


def derive() -> tuple[dict[str, Any], dict[str, Any]]:
    capture = load(CAPTURE)
    raw = ranges(capture)
    bank0 = raw["bank0-zp-stack"]
    status = raw["pending-error-and-overlay-status"]
    fixed = raw["c2-boot-runtime"]
    shelf = raw["shelf-header-and-max-catalog"]
    runtime = fixed[4:]
    wplto = load(WPLTO)
    truth = ElfTruth.read(ELF, llvm_readobj="llvm-readobj",
                          include_section_data=True)
    source = SOURCE.read_text(encoding="utf-8")
    tuple_row = capture["tuple"]
    require(tuple_row["PC"] == "0xe096" and tuple_row["MAPH"] == "0x8000"
            and tuple_row["MAPL"] == "0xffc0",
            "phase-1 stopped tuple drift")
    require(len(runtime) == 46 and fixed[2:4] == bytes((0x84, 0xc0)),
            "fixed runtime binding drift")
    runtime_state = {"phase": runtime[42], "finished": runtime[43],
                     "error": runtime[44], "reserved": runtime[45]}
    value: dict[str, Any] = {
        "format": FORMAT, "recorded_on": "2026-08-15",
        "status": "PRODUCT-FIRST-RED: MAP-MASK-SELF-OCCLUSION",
        "authority": {"capture": bind(CAPTURE), "candidate_ELF": bind(ELF),
                      "candidate_WPLTO": bind(WPLTO), "reader_source": bind(SOURCE)},
        "contact": {"kind": "crossing-free-owner-observed-product-first-red",
            "visible": "LISP65: LOADING LIBRARIES 1; red frame",
            "post_mount_automated_access_before_red": 0,
            "tuple_first": tuple_row},
        "runtime": runtime_state,
        "decision_table": "error=0: overlay/control-transfer fault outside decoder",
        "ordinary_state": {"pending_code": bank0[0x36],
            "c2_pending_roots": u16(bank0, 0x8a), "c2_ready": bank0[0x8c],
            "mem_oom": bank0[0x8f], "lisp_error_msg": f"0x{u16(status, 0):04x}",
            "rtov_fault": status[8]},
        "Shelf": shelf_facts(shelf, runtime, wplto),
        "mechanism": reader_facts(truth, source, int(tuple_row["MAPL"], 16)),
        "stack_claim": "forbidden-under-selected-block-0",
        "stack_reason": (
            "The captured MAP mask selects block 0, so physical Bank-0 page 1 "
            "is the underlay, not a proven view of the active mapped stack."),
        "classification": {
            "product_fault": True, "instrument_fault": False,
            "decoder_fault": False, "transport_content_fault": False,
            "mechanism_named": True,
            "name": "CPU-reader MAP mask borrow contamination/self-occlusion"},
        "fix_boundary": {
            "implementation": (
                "Construct X as block-mask $40 plus only the four offset-high "
                "bits after subtraction; prove $08100000 -> MAPL $4FC0."),
            "gate": (
                "Decode every emitted MAP tuple and prove the actual selected "
                "window is disjoint from reader code, ZP/stack and destination; "
                "source-level intended-window checks are insufficient."),
            "authorization": "not granted by this read-only rescue row"},
        "discipline": {"stops": 1, "resumes": 0, "runs": 0,
                       "CPU_left_stopped": True, "D2_D5_open": False},
        "claim_limit": (
            "Names the phase-1 product mechanism from the captured tuple, "
            "linked reader placement and primary MAP decode. It does not use "
            "the hidden Bank-0 stack underlay as an active-frame claim and "
            "does not authorize a fix or another device contact."),
    }
    audit(value)
    value["mutations"] = mutations(value)
    audit(value)
    device = {
        "format": "lisp65-c2.3-v2.1-phase1-rescue-device-v1",
        "captured_on": capture["captured_on"], "authority": capture["authority"],
        "discipline": capture["discipline"], "device": capture["device"],
        "stop_raw_hex": capture["stop_raw_hex"],
        "register_raw_hex": capture["register_raw_hex"], "tuple": tuple_row,
        "reads": capture["reads"], "CPU_left_stopped": True,
    }
    return device, value


def check() -> None:
    device = load(DEVICE_RECEIPT)
    result = load(RESULT_RECEIPT)
    audit(result)
    require(result.get("mutations") == mutations(result),
            "persisted phase-1 mutations drift")
    require(result["authority"]["device_receipt"] == bind(DEVICE_RECEIPT)
            and result["authority"]["candidate_ELF"] == bind(ELF)
            and result["authority"]["candidate_WPLTO"] == bind(WPLTO)
            and result["authority"]["reader_source"] == bind(SOURCE),
            "persisted phase-1 authority drift")
    require(device["tuple"] == result["contact"]["tuple_first"]
            and device["discipline"]["stops"] == 1
            and device["discipline"]["resumes"] == 0
            and device["CPU_left_stopped"] is True,
            "persisted raw device discipline drift")
    raw = ranges(device)
    fixed = raw["c2-boot-runtime"]
    runtime = fixed[4:]
    require({"phase": runtime[42], "finished": runtime[43],
             "error": runtime[44], "reserved": runtime[45]}
            == result["runtime"], "persisted runtime/raw mismatch")
    shelf_facts(raw["shelf-header-and-max-catalog"], runtime, load(WPLTO))
    truth = ElfTruth.read(ELF, llvm_readobj="llvm-readobj",
                          include_section_data=True)
    require(reader_facts(truth, SOURCE.read_text(encoding="utf-8"),
                         int(device["tuple"]["MAPL"], 16))
            == result["mechanism"], "persisted MAP mechanism drift")


def main() -> int:
    try:
        require(len(sys.argv) <= 2 and (len(sys.argv) == 1
                or sys.argv[1] in {"bind", "check"}),
                "usage: c2_v21_phase1_rescue_result.py [bind|check]")
        if len(sys.argv) == 2 and sys.argv[1] == "check":
            check()
            print("c2-v21-phase1-rescue: PASS: persisted product mechanism bound")
            return 0
        device, result = derive()
        DEVICE_RECEIPT.write_bytes(canonical(device))
        result["authority"]["device_receipt"] = bind(DEVICE_RECEIPT)
        RESULT_RECEIPT.write_bytes(canonical(result))
        print("c2-v21-phase1-rescue: PASS: error=0; MAPL=$FFC0 maps reader away")
        print(json.dumps({"device_receipt": bind(DEVICE_RECEIPT),
                          "result_receipt": bind(RESULT_RECEIPT),
                          "mutations": result["mutations"]},
                         indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, ResultError) as error:
        print(f"c2-v21-phase1-rescue: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
