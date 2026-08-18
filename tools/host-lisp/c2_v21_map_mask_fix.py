#!/usr/bin/env python3
"""Prove the emitted MAP tuple, not the intended window, for the CPU reader."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
SOURCE = ROOT / "src/optional/c2_map_cpu_read.s"
FIRST_RED = ARCH / (
    "c2.3-v2.1-product-liveness-phase1-rescue-result-receipt.json")
RECEIPT = ARCH / (
    "c2.3-v2.1-map-mask-fix-phase9-abi-rebind-receipt.json")
DRIVER = Path(__file__).resolve()
CC = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"

AUTHORIZATION = "e63e6240"
FORMAT = "lisp65-c2.3-v2.1-map-mask-fix-v1"
WINDOW_BASE = 0x4000
WINDOW_BYTES = 0x2000
MAX_READ = 64
READER_START = 0x2277
SOURCE_DOMAINS = {
    "c2d-bank5": (0x00050000, 50816),
    "product-shelf-attic": (0x08100000, 93681),
    "session-attic": (0x08400000, 0x00100000),
}


class MaskFixError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise MaskFixError(message)


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


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().split()).lower()
    for token in ("mask construction is corrected", "$ffc0",
                  "decodes the constructed tuple itself", "$4fc0",
                  "any self-covering mapping", "one card"):
        require(token in text, f"MAP-mask authorization token absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": digest(raw)}


def first_red() -> dict[str, Any]:
    value = load(FIRST_RED)
    require(
        value.get("classification", {}).get("name") ==
            "CPU-reader MAP mask borrow contamination/self-occlusion"
        and value.get("contact", {}).get("tuple_first", {}).get("MAPL") ==
            "0xffc0"
        and value.get("mechanism", {}).get("required_tuple", {}).get(
            "MAPL") == "0x4fc0"
        and value.get("mechanism", {}).get("reader", {}).get("start") ==
            "0x2277",
        "phase-1 First Red authority drift")
    return value


def assemble(source: str) -> tuple[bytes, int]:
    with tempfile.TemporaryDirectory(prefix="c2-v21-map-mask-") as raw:
        root = Path(raw); assembly = root / "reader.s"; obj = root / "reader.o"
        assembly.write_text(source, encoding="utf-8")
        result = subprocess.run(
            [str(CC), "-c", "-mcpu=mos45gs02", str(assembly), "-o", str(obj)],
            cwd=ROOT, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, check=False)
        require(result.returncode == 0, f"reader assembly red:\n{result.stdout}")
        truth = ElfTruth.read(obj, llvm_readobj=READOBJ,
                              include_section_data=True)
        symbol = truth.symbol("c2_map_cpu_read")
        section = truth.section(symbol.section)
        body = truth.section_bytes(symbol.section)[
            symbol.value - section.address:
            symbol.value - section.address + symbol.bytes]
        return body, symbol.bytes


def intended_tuple(physical: int) -> tuple[int, int]:
    in_mb = physical & 0xFFFFF
    window = in_mb & ~(WINDOW_BYTES - 1)
    offset = (window - WINDOW_BASE) & 0xFFFFF
    return (offset >> 8) & 0xFF, 0x40 | ((offset >> 16) & 0x0F)


def constructed_initial(physical: int) -> tuple[int, int]:
    byte1 = (physical >> 8) & 0xFF
    byte2 = (physical >> 16) & 0xFF
    a = ((byte1 & 0xE0) - 0x40) & 0xFF
    borrow = 1 if (byte1 & 0xE0) < 0x40 else 0
    x = ((byte2 - borrow) & 0x0F) | 0x40
    return a, x


def constructed_next(a: int, x: int) -> tuple[int, int]:
    total = a + 0x20
    a = total & 0xFF
    if total > 0xFF:
        x = ((x + 1) & 0xFF) & ~0x10
    return a, x


def selected_blocks(x: int) -> list[int]:
    return [block for block in range(4) if (x >> 4) & (1 << block)]


def tuple_row(a: int, x: int) -> dict[str, Any]:
    return {"MAPL": f"0x{x:02x}{a:02x}", "A": f"0x{a:02x}",
            "X": f"0x{x:02x}", "selected_blocks": selected_blocks(x)}


def actual_byte_gate(body: bytes, reader_bytes: int) -> dict[str, Any]:
    fixed = re.findall(rb"\xa5.\xe9\x00\x29\x0f\x09\x40\x85.", body)
    old = re.findall(rb"\xa5.\x29\x0f\xe9\x00\x09\x40\x85.", body)
    crossing = re.findall(
        rb"\xa5.\x69\x1f\x85.\x90\x04\xe6(.)\x47\1", body)
    require(len(fixed) == 1 and not old and len(crossing) == 1,
            "emitted reader does not carry fixed borrow/crossing construction")
    return {"reader_object_bytes": reader_bytes,
            "borrow_then_mask_opcode": fixed[0].hex(),
            "mask_then_borrow_opcode_count": len(old),
            "crossing_inc_rmb4_same_zp": True,
            "crossing_add_uses_cmp_carry": "691f" in body.hex()}


def model_gate() -> dict[str, Any]:
    rows: dict[str, Any] = {}
    initial_windows = boundary_crossings = 0
    for name, (base, length) in SOURCE_DOMAINS.items():
        starts = {base, base + length - 1}
        first = (base + WINDOW_BYTES - 1) & ~(WINDOW_BYTES - 1)
        for boundary in range(first, base + length, WINDOW_BYTES):
            starts.update(range(max(base, boundary - MAX_READ + 1), boundary + 1))
        domain_crossings = 0
        for start in sorted(starts):
            actual = constructed_initial(start)
            require(actual == intended_tuple(start),
                    f"{name} initial tuple drift at {start:#x}")
            require(selected_blocks(actual[1]) == [2],
                    f"{name} actual tuple covers a non-window block")
            initial_windows += 1
            for count in range(1, MAX_READ + 1):
                if start + count > base + length:
                    break
                if (start & ~(WINDOW_BYTES - 1)) != (
                        (start + count - 1) & ~(WINDOW_BYTES - 1)):
                    actual = constructed_next(*actual)
                    expected = intended_tuple(start + count - 1)
                    require(actual == expected and selected_blocks(actual[1]) == [2],
                            f"{name} crossing tuple drift at {start:#x}+{count}")
                    domain_crossings += 1; boundary_crossings += 1
                    break
        rows[name] = {"base": f"0x{base:08x}", "bytes": length,
                      "starts_checked": len(starts),
                      "crossings_checked": domain_crossings}
    positive = tuple_row(0xC0, 0x4F)
    negatives = [tuple_row(0xC0, 0xFF), tuple_row(0xC0, 0x2F)]
    require(positive["selected_blocks"] == [2]
            and all(1 in row["selected_blocks"] for row in negatives),
            "positive/negative MAP decode controls drift")
    return {"status": "PASS: every constructed tuple selects block 2 only",
            "reader": {"start": "0x2277", "block": READER_START >> 13},
            "positive": positive, "negative_self_covering": negatives,
            "initial_windows_checked": initial_windows,
            "boundary_crossings_checked": boundary_crossings,
            "domains": rows}


def linked_gate(elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    reader = truth.symbol("c2_map_cpu_read")
    section = truth.section(reader.section)
    body = truth.section_bytes(reader.section)[
        reader.value - section.address:reader.value - section.address + reader.bytes]
    emitted = actual_byte_gate(body, reader.bytes)
    model = model_gate()
    require(reader.value >> 13 == 1 and reader.value + reader.bytes <= 0x4000,
            "linked reader no longer occupies exactly CPU block 1")
    return {"status": "PASS: linked runtime tuple cannot cover reader block",
            "reader": {"address": f"0x{reader.value:04x}",
                       "bytes": reader.bytes,
                       "end_exclusive": f"0x{reader.value + reader.bytes:04x}",
                       "block": reader.value >> 13},
            "emitted_construction": emitted,
            "positive": model["positive"],
            "negative_self_covering": model["negative_self_covering"]}


def derive() -> dict[str, Any]:
    source = SOURCE.read_text(encoding="utf-8")
    body, reader_bytes = assemble(source)
    emitted = actual_byte_gate(body, reader_bytes)
    require(reader_bytes == 189, "fixed standalone reader price drift")
    return {"format": FORMAT, "recorded_on": "2026-08-15",
        "status": "HOST-GREEN: actual MAP tuple decode closes self-occlusion",
        "rule": "Decode the constructed runtime tuple, never design intent.",
        "authority": {"owner": authority(), "first_red": bind(FIRST_RED),
                      "source": bind(SOURCE), "driver": bind(DRIVER)},
        "first_red": {"actual": "0xffc0", "required": "0x4fc0",
                      "reader_start": "0x2277",
                      "mechanism": first_red()["classification"]["name"]},
        "emitted_construction": emitted, "model": model_gate(),
        "placement_price": {"pre_fix_linked_bytes": 188,
            "fixed_object_bytes": 189, "expected_linked_bytes": 189,
            "pre_fix_reserve_bytes": 2, "expected_reserve_bytes": 1,
            "checks_removed": 0},
        "execution_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "claim_limit": "Host-only fix proof; the authorized card has not run."}


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("status") ==
            "HOST-GREEN: actual MAP tuple decode closes self-occlusion"
        and value.get("model", {}).get("positive", {}).get("MAPL") == "0x4fc0"
        and [row["MAPL"] for row in value.get("model", {}).get(
            "negative_self_covering", [])] == ["0xffc0", "0x2fc0"]
        and value.get("emitted_construction", {}).get(
            "mask_then_borrow_opcode_count") == 0
        and value.get("emitted_construction", {}).get(
            "crossing_inc_rmb4_same_zp") is True
        and value.get("placement_price", {}).get("checks_removed") == 0
        and value.get("execution_accounting", {}).get("cards_consumed") == 0,
        "MAP-mask fix receipt weakened")
    if verify:
        require(value == derive(), "MAP-mask fix authority drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "accept-ffc0": lambda x: x["model"].update(
            negative_self_covering=x["model"]["negative_self_covering"][1:]),
        "reject-4fc0": lambda x: x["model"].update(positive={"MAPL": "0xffc0"}),
        "accept-arbitrary-self-cover": lambda x: x["model"][
            "negative_self_covering"].pop(),
        "hide-old-opcode": lambda x: x["emitted_construction"].update(
            mask_then_borrow_opcode_count=1),
        "drop-crossing-mask": lambda x: x["emitted_construction"].update(
            crossing_inc_rmb4_same_zp=False),
        "remove-check": lambda x: x["placement_price"].update(checks_removed=1),
        "spend-card": lambda x: x["execution_accounting"].update(cards_consumed=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial, verify=True)
        except MaskFixError:
            rejected.append(name)
    source = SOURCE.read_text(encoding="utf-8")
    old = source.replace(
        "\tlda __rc10\n\tsbc #0\n", "\tlda __rc10\n\tand #$0f\n\tsbc #0\n", 1
    ).replace("\tand #$0f\n\tora #$40\n", "\tora #$40\n", 1)
    crossing_register = re.search(r"\trmb4 (__rc(?:1[0-5]))\n", source)
    require(crossing_register is not None,
            "current reader crossing-mask register absent")
    no_cross = source.replace(crossing_register.group(0), "", 1)
    for name, candidate in (("restore-ffc0-borrow-order", old),
                            ("drop-8k-crossing-mask", no_cross)):
        try:
            body, size = assemble(candidate); actual_byte_gate(body, size)
        except MaskFixError:
            rejected.append(name)
    expected = list(cases) + ["restore-ffc0-borrow-order",
                              "drop-8k-crossing-mask"]
    require(rejected == expected, "MAP-mask mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "MAP-mask fix receipt exists")
    value = derive(); validate(value, verify=True)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("2.1 MAP mask: PASS tuple=4fc0 negatives=ffc0/2fc0 reader=189")


def check() -> None:
    value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == mutations(value), "MAP-mask mutation receipt drift")
    print("2.1 MAP mask: CHECK PASS actual-tuple=yes crossings=yes")


def selftest() -> None:
    value = derive(); validate(value, verify=False)
    require(len(mutations(value)) == 9, "MAP-mask selftest mutation drift")
    print("2.1 MAP mask: SELFTEST PASS mutations=9")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check", "selftest"))
    {"record": record, "check": check,
     "selftest": selftest}[parser.parse_args().action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"2.1 MAP mask: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
