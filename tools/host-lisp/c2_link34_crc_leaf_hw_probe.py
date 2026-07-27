#!/usr/bin/env python3
"""Build, verify and evaluate the exact Link-34 CRC-leaf hardware probe."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "build/c2.2/link34-crc-leaf-hardware-probe"
PRODUCT_DIR = ROOT / "build/c2.2/substitution/product-link-34-crc-asm-leaf"
PRODUCT = PRODUCT_DIR / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
BOOT = PRODUCT_DIR / "runtime-overlays-boot-final.bin"
MANIFEST = PRODUCT_DIR / "runtime-overlays-boot-final.json"
DIAGNOSIS = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link34-runtime-island-hardware-first-red-diagnosis.json")
SOURCE = ROOT / "scripts/c2-link34-crc-leaf-hw-probe.s"
LINKER = ROOT / "config/c2-link34-crc-leaf-hw-probe.ld"
CC = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
LD = ROOT / "tools/llvm-mos/bin/ld.lld"
OBJCOPY = ROOT / "tools/llvm-mos/bin/llvm-objcopy"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
NM = ROOT / "tools/llvm-mos/bin/llvm-nm"
OBJECT = OUT / "c2-link34-crc-leaf-hw-probe.o"
PROBE_ELF = OUT / "c2-link34-crc-leaf-hw-probe.elf"
PROBE_RAW = OUT / "c2-link34-crc-leaf-hw-probe.raw.bin"
PROBE_PRG = OUT / "c2-link34-crc-leaf-hw-probe.prg"
PROBE_MAP = OUT / "c2-link34-crc-leaf-hw-probe.map"
PROBE_DIS = OUT / "c2-link34-crc-leaf-hw-probe.dis"
BUNDLE = OUT / "c2-link34-crc-inputs.bin"
LEAF = OUT / "link34-rtov-crc-mem.bin"
PLAN = OUT / "deployment.json"
RESULT_BIN = OUT / "hardware-mailbox.bin"
RESULT_JSON = OUT / "hardware-result.json"

PRODUCT_SHA = "bef7708baa12b8e23094c2150a53f5bee529be25b9b9e11d0d68a3191ee6a485"
ELF_SHA = "cfbd1f7420c5b0a5bbf80408e7ec39c2b6237d35d3e930a1eb2b219ebb9dadf4"
BOOT_SHA = "cb9f47b8f1c8a924aee4852ee8ba544f1d316211cbd8b2855ee3cf49f778ef19"
DIAGNOSIS_SHA = "803c5b1e5d474e7a02f8ac1afe435f444d9169b7e2aeaa5f301ce0a7c91d68fe"
LEAF_ADDRESS = 0x222D
LEAF_BYTES = 66
BUNDLE_ADDRESS = 0x8000
MAILBOX_ADDRESS = 0x1F00
MAILBOX_BYTES = 32


class ProbeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"probe artifact absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def run(command: list[str]) -> str:
    completed = subprocess.run(command, cwd=ROOT, text=True,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, check=False)
    if completed.returncode:
        raise ProbeError(
            f"command failed ({completed.returncode}): {' '.join(command)}: "
            f"{(completed.stderr or completed.stdout).strip()}")
    require(not completed.stderr.strip(),
            f"unexpected tool diagnostic: {completed.stderr.strip()}")
    return completed.stdout


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF \
                if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def operational_cases() -> list[dict[str, Any]]:
    bank = BOOT.read_bytes()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    header = bytearray(bank[:32])
    header_crc = int.from_bytes(header[26:28], "little")
    header[26:28] = b"\0\0"
    rows: list[dict[str, Any]] = [
        {"id": 0, "name": "ccitt-check", "address": 0x8000,
         "data": b"123456789", "crc16": 0x29B1},
        {"id": 1, "name": "catalog-header", "address": 0x8100,
         "data": bytes(header), "crc16": header_crc},
    ]
    addresses = {0: 0x8200, 1: 0x8700, 8: 0x8D00, 9: 0x9300}
    for case_id, slot in enumerate((0, 1, 8, 9), start=2):
        item = manifest["slices"][slot]
        begin = int(item["file_offset"])
        end = begin + int(item["file_size"])
        rows.append({"id": case_id, "name": item["name"],
                     "address": addresses[slot], "data": bank[begin:end],
                     "crc16": int(item["crc16"])})
    for row in rows:
        require(crc16(row["data"]) == row["crc16"],
                f"operational CRC source drift: {row['name']}")
    return rows


def build_bundle(cases: list[dict[str, Any]]) -> None:
    end = max(row["address"] + len(row["data"]) for row in cases)
    image = bytearray(end - BUNDLE_ADDRESS)
    occupied: set[int] = set()
    for row in cases:
        start = row["address"] - BUNDLE_ADDRESS
        for address in range(start, start + len(row["data"])):
            require(address not in occupied,
                    f"input bundle overlap at 0x{address + BUNDLE_ADDRESS:04x}")
            occupied.add(address)
        image[start:start + len(row["data"])] = row["data"]
    BUNDLE.write_bytes(image)


def extract_leaf() -> None:
    prg = PRODUCT.read_bytes()
    load = int.from_bytes(prg[:2], "little")
    start = 2 + LEAF_ADDRESS - load
    require(load == 0x2001 and start >= 2,
            "Link-34 product load address cannot expose the pinned leaf")
    leaf = prg[start:start + LEAF_BYTES]
    require(len(leaf) == LEAF_BYTES, "Link-34 leaf extraction truncated")
    LEAF.write_bytes(leaf)


def build_probe() -> None:
    run([str(CC), "-c", str(SOURCE), "-o", str(OBJECT)])
    run([str(LD), "--gc-sections", "--entry=c2_link34_crc_probe_entry",
         str(OBJECT), "-T", str(LINKER),
         "-Map=" + str(PROBE_MAP), "-o", str(PROBE_ELF)])
    run([str(OBJCOPY), "-O", "binary", str(PROBE_ELF), str(PROBE_RAW)])
    raw = PROBE_RAW.read_bytes()
    require(len(raw) <= LEAF_ADDRESS - 0x2001,
            "diagnostic probe overlaps the exact Link-34 leaf")
    PROBE_PRG.write_bytes((0x2001).to_bytes(2, "little") + raw)
    disassembly = run([str(OBJDUMP), "-d", "--no-show-raw-insn",
                       str(PROBE_ELF)])
    PROBE_DIS.write_text(disassembly, encoding="utf-8")
    calls = [target for address, target in re.findall(
        r"^\s*([0-9a-f]+):.*\bjsr\s+\$([0-9a-f]+)",
        disassembly, re.MULTILINE) if int(address, 16) >= 0x200D]
    require(calls == ["222d"] * 6,
            f"diagnostic call surface is not six exact leaf calls: {calls}")
    require("\tbne\t" not in disassembly,
            "diagnostic retained a range-sensitive failing BNE")
    fail_jumps = re.findall(r"\bjmp\s+\$([0-9a-f]+)", disassembly)
    require(len(fail_jumps) == 12 and len(set(fail_jumps)) == 1,
            f"diagnostic fail-jump surface drift: {fail_jumps}")
    symbols = run([str(NM), "--defined-only", "--numeric-sort", str(PROBE_ELF)])
    entry = [line for line in symbols.splitlines()
             if line.endswith(" c2_link34_crc_probe_entry")]
    require(len(entry) == 1 and int(entry[0].split()[0], 16) == 0x200D,
            "diagnostic SYS entry does not resolve to 0x200d")


def prepare() -> dict[str, Any]:
    require(not PLAN.exists(), "exact Link-34 CRC hardware probe already prepared")
    require(sha(PRODUCT) == PRODUCT_SHA and sha(ELF) == ELF_SHA
            and sha(BOOT) == BOOT_SHA and sha(DIAGNOSIS) == DIAGNOSIS_SHA,
            "authorized Link-34 diagnosis inputs drifted")
    diagnosis = json.loads(DIAGNOSIS.read_text(encoding="utf-8"))
    require(diagnosis["bounded_next_probe"]["authorization"] ==
            "not granted by this diagnosis",
            "First-Red diagnosis no longer has the expected claim boundary")
    OUT.mkdir(parents=True, exist_ok=True)
    cases = operational_cases()
    build_bundle(cases)
    extract_leaf()
    build_probe()
    value = {
        "format": "lisp65-c2-link34-exact-crc-leaf-hardware-probe-deployment-v1",
        "status": "ready-receipt-less-no-hardware-run",
        "authorization": "owner-authorized-after-Link-34-E2f-First-Red",
        "source_identity": {
            "first_red_diagnosis": bind(DIAGNOSIS),
            "immutable_product": bind(PRODUCT),
            "immutable_product_elf": bind(ELF),
            "immutable_boot_family": bind(BOOT),
        },
        "probe": {
            "prg": bind(PROBE_PRG), "raw": bind(PROBE_RAW),
            "elf": bind(PROBE_ELF), "map": bind(PROBE_MAP),
            "disassembly": bind(PROBE_DIS), "source": bind(SOURCE),
            "linker": bind(LINKER), "load_address": "0x2001",
            "entry": "0x200d", "end_exclusive": hex(0x2001 + PROBE_RAW.stat().st_size),
            "leaf_address": hex(LEAF_ADDRESS), "leaf_overlap": False,
        },
        "injected_inputs": {"address": hex(BUNDLE_ADDRESS),
                            "artifact": bind(BUNDLE)},
        "exact_leaf": {"address": hex(LEAF_ADDRESS), "artifact": bind(LEAF)},
        "mailbox": {"address": hex(MAILBOX_ADDRESS), "bytes": MAILBOX_BYTES,
                    "magic": "C2CR"},
        "cases": [{"id": row["id"], "name": row["name"],
                   "address": hex(row["address"]), "bytes": len(row["data"]),
                   "expected_crc16": f"0x{row['crc16']:04x}"}
                  for row in cases],
        "execution_accounting": {"product_links": 0, "product_entries": 0,
                                 "diagnostic_hardware_runs_authorized": 1,
                                 "presmoke_retries": 0},
        "claim_limit": (
            "One receipt-less exact-byte hardware conformance probe against the "
            "immutable Link-34 leaf. It is not a product run, presmoke retry, "
            "promotion, acceptance or authorization for a source fix."),
    }
    PLAN.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    return value


def verify() -> dict[str, Any]:
    require(PLAN.is_file(), "exact CRC hardware probe deployment absent")
    value = json.loads(PLAN.read_text(encoding="utf-8"))
    require(value.get("status") == "ready-receipt-less-no-hardware-run",
            "exact CRC hardware probe deployment is not ready")
    for group in (value["source_identity"], value["probe"]):
        for item in group.values():
            if isinstance(item, dict) and "path" in item:
                path = ROOT / item["path"]
                require(bind(path) == item, f"prepared artifact drift: {path}")
    require(bind(BUNDLE) == value["injected_inputs"]["artifact"],
            "prepared CRC input bundle drift")
    require(bind(LEAF) == value["exact_leaf"]["artifact"],
            "prepared exact leaf drift")
    require(sha(PRODUCT) == PRODUCT_SHA and sha(DIAGNOSIS) == DIAGNOSIS_SHA,
            "Link-34 authority drift after probe preparation")
    return value


def evaluate() -> dict[str, Any]:
    deployment = verify()
    require(RESULT_BIN.is_file() and RESULT_BIN.stat().st_size == MAILBOX_BYTES,
            "hardware mailbox capture absent or wrong size")
    data = RESULT_BIN.read_bytes()
    require(data[:4] == b"C2CR", "hardware probe mailbox magic absent")
    cases = deployment["cases"]
    observed = [int.from_bytes(data[8 + 2 * index:10 + 2 * index], "little")
                for index in range(len(cases))]
    rows = [{**row, "observed_crc16": f"0x{observed[index]:04x}",
             "status": ("passed" if observed[index] ==
                         int(row["expected_crc16"], 16) else "FIRST RED")}
            for index, row in enumerate(cases)]
    passed = (data[4] == ord("P") and data[5] == 0xFF and data[6] == 6
              and all(row["status"] == "passed" for row in rows))
    failed = data[4] == ord("F") and data[5] < 6
    require(passed or failed, f"invalid terminal mailbox state: {data[:20].hex()}")
    value = {
        "format": "lisp65-c2-link34-exact-crc-leaf-hardware-result-v1",
        "status": ("passed-receipt-less-exact-linked-leaf-on-hardware"
                   if passed else "FIRST RED: exact linked leaf CRC mismatch"),
        "deployment": bind(PLAN), "mailbox_capture": bind(RESULT_BIN),
        "terminal": {"marker": chr(data[4]), "first_failing_case": data[5],
                     "completed_cases": data[6]},
        "cases": rows,
        "execution_accounting": {"product_links": 0, "product_entries": 0,
                                 "diagnostic_hardware_runs": 1,
                                 "presmoke_retries": 0},
        "decision": (
            "Leaf exonerated on metal; return for authorization of one "
            "diagnostic-only inner-status latch before any product link."
            if passed else
            "Leaf/target execution is the First Red; return the exact failing "
            "case before any source change or product link."),
        "claim_limit": (
            "Receipt-less exact-byte diagnostic evidence only. It is not "
            "product hardware acceptance, promotion or latency evidence."),
    }
    RESULT_JSON.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    return value


def selftest() -> None:
    require(crc16(b"123456789") == 0x29B1, "CRC selftest failed")
    sample = bytearray(32)
    sample[:4] = b"C2CR"; sample[4] = ord("P"); sample[5] = 0xFF; sample[6] = 6
    for index, expected in enumerate((0x29B1, 0xF0DE, 0x291D,
                                      0x3D7C, 0xBF4B, 0x8009)):
        sample[8 + 2 * index:10 + 2 * index] = expected.to_bytes(2, "little")
    require(sample[:4] == b"C2CR" and sample[6] == 6,
            "mailbox selftest failed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "verify", "evaluate", "selftest"))
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            selftest(); print("c2-link34-crc-leaf-hw-probe: SELFTEST PASS")
        elif args.action == "prepare":
            value = prepare(); print("c2-link34-crc-leaf-hw-probe: " + value["status"])
        elif args.action == "verify":
            value = verify(); print("c2-link34-crc-leaf-hw-probe: " + value["status"])
        else:
            value = evaluate(); print("c2-link34-crc-leaf-hw-probe: " + value["status"])
        return 0
    except (ProbeError, OSError, ValueError, subprocess.SubprocessError) as error:
        print("c2-link34-crc-leaf-hw-probe: FAIL: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
