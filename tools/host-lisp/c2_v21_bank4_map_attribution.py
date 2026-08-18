#!/usr/bin/env python3
"""Decode Link-113's Bank-4 MAP case and specify the closing target row.

This is deliberately a desk-only attribution.  It binds the exact emitted
reader, the exact stopped product world and the pinned GS4510 RTL, then
decodes the ``$00046a00`` case independently.  A target probe is specified
only when the static decode cannot distinguish silicon behaviour from the
delivered reader path; this tool never performs that contact.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
RESCUE = ARCH / (
    "c2.3-v2.1-link113-d2-bank4-root-reader-rescue-receipt.json"
)
MAP_DEVICE = ARCH / (
    "c2.3-v2.0-loading-libraries-progress-map-device-receipt.json"
)
MEDIA = ARCH / "c2.3-v2.1-configurator-parity-completion-media-receipt.json"
ELF = ROOT / (
    "build/c2.3/v2.1-root-padding-configurator-parity-continuation/final/"
    "lisp65-c2-substitution-linked.prg.elf"
)
PRG = ELF.with_suffix("")
PRODUCT_MANIFEST = ROOT / (
    "build/c2.3/v2.1-configurator-parity-media/shared-system/"
    "candidate-manifest.json"
)
READER = ROOT / "src/optional/c2_map_cpu_read.s"
CORE_REPO = ROOT / "build/upstream-verification/mega65-core"
CORE = CORE_REPO / "src/vhdl/gs4510.vhdl"
MAP_CONTRACT = ROOT / "config/c2-mapped-far-map-contract-v2.json"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
DRIVER = Path(__file__).resolve()
RECEIPT = ARCH / "c2.3-v2.1-bank4-map-attribution-receipt.json"

AUTHORIZATION = "bfba29a3"
CORE_COMMIT = "a9158930665763c592d004c895d52eff4a9eefc3"
FORMAT = "lisp65-c2.3-v2.1-bank4-map-attribution-v1"
STATUS = "DESK-DECODE-CORRECT; BANK4-TARGET-PROBE-REQUIRED"
SOURCE = 0x00046A00
CONTROL_BANK5_SAME_OFFSET = 0x00056A00
CONTROL_BANK5_PROVED_BASE = 0x00050000
CPU_WINDOW = 0x4000
WINDOW_BYTES = 0x2000
SIGNATURE_BYTES = 4
REPEATS = 64


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": digest(raw)}


def git_authority() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE,
    ).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE,
    ).stdout
    text = " ".join(raw.decode().replace("*", "").split()).lower()
    for token in (
        "bank-4 attribution commissioned",
        "decode the reader's bank-4 mapping math",
        "$00046a00",
        "if the desk cannot decide",
        "one bank-4 probe row",
        "never another silent generalization",
    ):
        require(token in text, f"Bank-4 commission token absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": digest(raw)}


def map_tuple(physical: int) -> dict[str, Any]:
    """Model the exact emitted initial-window construction."""
    byte0 = physical & 0xFF
    byte1 = (physical >> 8) & 0xFF
    byte2 = (physical >> 16) & 0xFF
    byte3 = (physical >> 24) & 0xFF
    mb = ((byte3 << 4) | (byte2 >> 4)) & 0xFF
    pointer = byte0 | (((byte1 & 0x1F) | 0x40) << 8)
    a = ((byte1 & 0xE0) - 0x40) & 0xFF
    borrow = int((byte1 & 0xE0) < 0x40)
    x = ((byte2 - borrow) & 0x0F) | 0x40
    offset = ((x & 0x0F) << 16) | (a << 8)
    selected = [block for block in range(4)
                if ((x >> 4) & (1 << block))]
    resolved = (mb << 20) | (((offset + pointer) >> 8) << 8) \
        | (pointer & 0xFF)
    window_start = resolved - (pointer - CPU_WINDOW)
    return {
        "source": f"0x{physical:08x}",
        "source_bytes_little_endian": bytes((byte0, byte1, byte2, byte3)).hex(),
        "low_megabyte": f"0x{mb:02x}",
        "cpu_pointer": f"0x{pointer:04x}",
        "A": f"0x{a:02x}", "X": f"0x{x:02x}",
        "MAPL": f"0x{x:02x}{a:02x}",
        "offset20": f"0x{offset:05x}",
        "selected_cpu_blocks": selected,
        "resolved_source": f"0x{resolved:08x}",
        "mapped_window": (
            f"0x{window_start:08x}..0x{window_start + WINDOW_BYTES:08x}"
        ),
    }


def emitted_reader() -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    symbol = truth.symbol("c2_map_cpu_read")
    section = truth.section(symbol.section)
    body = truth.section_bytes(symbol.section)[
        symbol.value - section.address:
        symbol.value - section.address + symbol.bytes
    ]
    # Physical high-byte split, pointer construction, borrow-before-mask and
    # the single-block MAP helper must all be in the delivered body.
    patterns = {
        "pointer_high": rb"\xa5.\x29\x1f\x09\x40\x85.",
        "offset_low": rb"\xa5.\x29\xe0\x38\xe9\x40\x85.",
        "borrow_then_mask": rb"\xa5.\xe9\x00\x29\x0f\x09\x40\x85.",
        "map_helper": rb"\xa5.\xa6.\xa0\x00\xa3\x80\x5c\xea\xa3\x00\x60",
    }
    counts = {name: len(re.findall(pattern, body))
              for name, pattern in patterns.items()}
    require(all(value == 1 for value in counts.values()),
            f"emitted reader construction drift: {counts}")
    require(symbol.value == 0x2277 and symbol.value + symbol.bytes < 0x4000,
            "Link-113 reader placement drift")
    return {
        "symbol": symbol.name,
        "address": f"0x{symbol.value:04x}",
        "bytes": symbol.bytes,
        "end_exclusive": f"0x{symbol.value + symbol.bytes:04x}",
        "execution_cpu_block": symbol.value >> 13,
        "body_sha256": digest(body),
        "construction_patterns": counts,
        "DMA_opcodes_or_registers": 0,
    }


def rtl_decode() -> dict[str, Any]:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=CORE_REPO, check=True,
        text=True, stdout=subprocess.PIPE,
    ).stdout.strip()
    require(head == CORE_COMMIT, "primary GS4510 checkout commit drift")
    source = CORE.read_text(encoding="utf-8")
    anchors = (
        "reg_offset_low <= reg_x(3 downto 0) & reg_a;",
        "reg_map_low <= std_logic_vector(reg_x(7 downto 4));",
        "temp_address(19 downto 8) := reg_offset_low+to_integer(short_address(15 downto 8));",
        "-- @IO:M65 $0040000-$005FFFF - 128KB RAM (in place of C65 cartridge support)",
    )
    require(all(source.count(anchor) == 1 for anchor in anchors),
            "primary RTL MAP/chip-RAM anchors drift")
    mapped_return = source.index(
        "temp_address(19 downto 8) := reg_offset_low+to_integer(short_address(15 downto 8));"
    )
    mapped_return = source.index("return temp_address;", mapped_return)
    c64_io = source.index("-- C64-style $01 mapping", mapped_return)
    require(mapped_return < c64_io,
            "MAP no longer precedes the C64 I/O/ROM overlay decode")

    rows = {}
    for name, physical in (
        ("bank4_exact", SOURCE),
        ("bank5_same_offset", CONTROL_BANK5_SAME_OFFSET),
        ("bank5_proved_base", CONTROL_BANK5_PROVED_BASE),
    ):
        row = map_tuple(physical)
        bit19 = (physical >> 19) & 1
        row["RTL_physical_branch"] = (
            "shadow/chip-RAM $0040000-$005ffff" if
            physical >> 20 == 0 and bit19 == 0 else "other"
        )
        row["C64_IO_overlay_applied_after_MAP"] = False
        rows[name] = row
    require(
        rows["bank4_exact"]["resolved_source"] == "0x00046a00"
        and rows["bank4_exact"]["MAPL"] == "0x4420"
        and rows["bank4_exact"]["cpu_pointer"] == "0x4a00"
        and rows["bank4_exact"]["selected_cpu_blocks"] == [2]
        and rows["bank4_exact"]["mapped_window"]
            == "0x00046000..0x00048000"
        and len({row["RTL_physical_branch"] for row in rows.values()}) == 1,
        "Bank-4/Bank-5 RTL decode distinction appeared",
    )
    return {
        "core_commit": head,
        "core": bind(CORE),
        "MAP_register_semantics": {
            "A": "low offset bits 15..8",
            "X_low_nibble": "low offset bits 19..16",
            "X_high_nibble": "low-half CPU block mask",
        },
        "mapped_access_precedes_C64_IO_decode": True,
        "physical_branch_equivalence": (
            "$00046a00, $00056a00 and the proved $00050000 control all use "
            "the same RTL shadow/chip-RAM branch"
        ),
        "rows": rows,
    }


def delivery_known_probe() -> dict[str, Any]:
    manifest = load(PRODUCT_MANIFEST)
    records = manifest["descriptor"]["records"]
    product = [row for row in records if row["role_id"] == 9]
    require(len(product) == 1, "product staging role is not unique")
    role = product[0]
    raw = PRG.read_bytes()
    offset = SOURCE - role["destination"]
    signature = raw[offset:offset + SIGNATURE_BYTES]
    require(
        role == {
            "role_id": 9, "flags": 2, "destination": 0x00040000,
            "bytes": len(raw), "crc32": "3bc91624", "name": "lisp65.prg",
        }
        and 0 <= offset <= len(raw) - SIGNATURE_BYTES
        and signature == bytes.fromhex("188505a4"),
        "delivery-known Bank-4 product-stage signature drift",
    )
    return {
        "authorization_state": "SPECIFIED-NOT-AUTHORIZED-NOT-RUN",
        "purpose": (
            "distinguish target Bank-4 MAP behaviour from the delivered "
            "reader/caller path after the desk decode found no construction error"
        ),
        "carrier": (
            "non-promotable pre-main sibling; the normal stager has already "
            "loaded the exact product PRG at physical Bank 4"
        ),
        "source_truth": {
            "product_PRG": bind(PRG),
            "product_manifest": bind(PRODUCT_MANIFEST),
            "descriptor_role": role,
            "physical_source": f"0x{SOURCE:08x}",
            "PRG_byte_offset": f"0x{offset:04x}",
            "signature_hex": signature.hex(),
        },
        "exact_row": {
            "low_MB": "0x00", "A": "0x20", "X": "0x44",
            "Y": "0x00", "Z": "0x80", "MAPL": "0x4420",
            "CPU_reads": "LDA $4a00,X for X=0..3",
            "repetitions": REPEATS,
            "raw_reads": REPEATS * SIGNATURE_BYTES,
            "expected": signature.hex(),
            "commit_last_status": {"PASS": "0xa5", "MISMATCH": "0xe1"},
            "restore": "MAPL=0, low MB=0, Z=0 on every exit",
        },
        "decision_table": {
            "0xe1": (
                "intrinsic target Bank-4 MAP form refuted at the exact $4420/$4a00 case"
            ),
            "0xa5": (
                "intrinsic Bank-4 MAP difference refuted; fault remains in the "
                "delivered reader/caller path"
            ),
            "other": "probe/setup red; no mechanism claim",
        },
        "contact": {
            "device_contacts": 0, "owner_keyboard": False,
            "product_bytes_promotable": False, "D3_D5_open": False,
        },
        "filename_note": (
            "SD cleanup acknowledged; a future sibling may use compact fresh "
            "names such as b4map.d81/b4sig without legacy-name constraints"
        ),
    }


def derive() -> dict[str, Any]:
    rescue = load(RESCUE)
    require(
        rescue.get("status") == "BANK4-MAP-CPU-PRODUCT-PATH-REFUTED"
        and rescue.get("conclusion", {}).get(
            "intrinsic_Bank4_MAP_unreadability_proven") is False
        and rescue.get("three_way_comparison", {}).get(
            "staged_equals_historical_poison_object") is True,
        "Link-113 Bank-4 rescue authority drift",
    )
    device = load(MAP_DEVICE)
    require(
        device.get("probe", {}).get("decision")
            == "MAP-CPU-BANK5-AND-ATTIC-TARGET-GREEN"
        and "Bank-4" not in device.get("claim_limit", ""),
        "historical MAP target-proof scope drift",
    )
    decode = rtl_decode()
    exact = decode["rows"]["bank4_exact"]
    value = {
        "format": FORMAT,
        "recorded_on": "2026-08-17",
        "status": STATUS,
        "authority": {
            "owner": git_authority(), "rescue": bind(RESCUE),
            "historical_MAP_device": bind(MAP_DEVICE),
            "media": bind(MEDIA), "ELF": bind(ELF), "PRG": bind(PRG),
            "product_manifest": bind(PRODUCT_MANIFEST),
            "reader_source": bind(READER), "MAP_contract": bind(MAP_CONTRACT),
            "driver": bind(DRIVER),
        },
        "emitted_reader": emitted_reader(),
        "primary_RTL_decode": decode,
        "desk_verdict": {
            "constructed_tuple": exact["MAPL"],
            "cpu_pointer": exact["cpu_pointer"],
            "resolved_source": exact["resolved_source"],
            "mapped_window": exact["mapped_window"],
            "reader_self_covered": False,
            "Bank4_specific_block_mask_or_IO_semantics_found": False,
            "decodable_reader_construction_error_found": False,
            "intrinsic_target_behaviour_decided": False,
            "reason_probe_is_required": (
                "The emitted arithmetic and pinned RTL are exact and Bank 4/5 "
                "share one physical branch, but the only target proof covers "
                "Bank 5 and Attic. Static equivalence cannot promote an "
                "untested target bank."
            ),
        },
        "closing_probe": delivery_known_probe(),
        "execution_accounting": {
            "WPLTO_runs": 0, "product_links": 0, "media_builds": 0,
            "device_contacts": 0, "device_stops": 0, "device_resumes": 0,
        },
        "decision": {
            "fix_authorized": False,
            "probe_contact_authorized": False,
            "D3_D5_open": False,
            "next": "owner review/authorization of the specified Bank-4 probe row",
        },
        "claim_limit": (
            "Desk decode proves the exact Link-113 tuple, pointer and RTL path "
            "contain no Bank-4-specific construction or overlay distinction. "
            "It does not convert static equivalence into target evidence, run "
            "the specified probe, authorize a fix, resume the preserved CPU, "
            "or open D3-D5."
        ),
    }
    validate(value)
    value["mutations_rejected"] = mutations(value)
    return value


def validate(value: dict[str, Any]) -> None:
    desk = value.get("desk_verdict", {})
    probe = value.get("closing_probe", {})
    row = probe.get("exact_row", {})
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and desk.get("constructed_tuple") == "0x4420"
        and desk.get("cpu_pointer") == "0x4a00"
        and desk.get("resolved_source") == "0x00046a00"
        and desk.get("mapped_window") == "0x00046000..0x00048000"
        and desk.get("reader_self_covered") is False
        and desk.get("Bank4_specific_block_mask_or_IO_semantics_found") is False
        and desk.get("decodable_reader_construction_error_found") is False
        and desk.get("intrinsic_target_behaviour_decided") is False
        and row.get("MAPL") == "0x4420"
        and row.get("CPU_reads") == "LDA $4a00,X for X=0..3"
        and row.get("raw_reads") == 256
        and probe.get("authorization_state") == "SPECIFIED-NOT-AUTHORIZED-NOT-RUN"
        and probe.get("source_truth", {}).get("signature_hex") == "188505a4"
        and probe.get("contact", {}).get("device_contacts") == 0
        and value.get("decision") == {
            "fix_authorized": False,
            "probe_contact_authorized": False,
            "D3_D5_open": False,
            "next": "owner review/authorization of the specified Bank-4 probe row",
        }
        and not any(value.get("execution_accounting", {}).values()),
        "Bank-4 desk attribution/probe boundary drift",
    )


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "transpose-Bank4-tuple": lambda x: x["desk_verdict"].update(
            constructed_tuple="0x4424"),
        "move-CPU-pointer": lambda x: x["desk_verdict"].update(
            cpu_pointer="0x4000"),
        "invent-Bank4-RTL-branch": lambda x: x["desk_verdict"].update(
            Bank4_specific_block_mask_or_IO_semantics_found=True),
        "invent-static-reader-fault": lambda x: x["desk_verdict"].update(
            decodable_reader_construction_error_found=True),
        "promote-static-to-target-proof": lambda x: x["desk_verdict"].update(
            intrinsic_target_behaviour_decided=True),
        "probe-wrong-pointer": lambda x: x["closing_probe"]["exact_row"].update(
            CPU_reads="LDA $4000,X for X=0..3"),
        "probe-wrong-tuple": lambda x: x["closing_probe"]["exact_row"].update(
            MAPL="0x44c0"),
        "probe-not-delivery-bound": lambda x: x["closing_probe"][
            "source_truth"].update(signature_hex="00000000"),
        "under-sample-probe": lambda x: x["closing_probe"]["exact_row"].update(
            raw_reads=4),
        "silently-authorize-contact": lambda x: x["decision"].update(
            probe_contact_authorized=True),
        "silently-authorize-fix": lambda x: x["decision"].update(
            fix_authorized=True),
        "open-D3": lambda x: x["decision"].update(D3_D5_open=True),
        "invent-device-contact": lambda x: x["execution_accounting"].update(
            device_contacts=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        trial.pop("mutations_rejected", None)
        mutate(trial)
        try:
            validate(trial)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases), "Bank-4 attribution mutation survived")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("emit", "check", "selftest"))
    action = parser.parse_args().action
    value = derive()
    if action == "emit":
        sys.stdout.buffer.write(canonical(value))
    elif action == "check":
        require(load(RECEIPT) == value, "Bank-4 attribution receipt stale")
        print("Bank-4 MAP attribution: CHECK PASS tuple=4420 probe=pending mutations=13")
    else:
        require(len(value["mutations_rejected"]) == 13,
                "Bank-4 attribution mutation count drift")
        print("Bank-4 MAP attribution: SELFTEST PASS tuple=4420 probe=specified")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"Bank-4 MAP attribution: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
