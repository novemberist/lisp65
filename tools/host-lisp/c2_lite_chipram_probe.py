#!/usr/bin/env python3
"""Build, statically verify and record the non-product C2-lite Chip-RAM proof."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build/c2-lite/chipram-proof"
CC = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
LD = ROOT / "tools/llvm-mos/bin/ld.lld"
NM = ROOT / "tools/llvm-mos/bin/llvm-nm"
SIZE = ROOT / "tools/llvm-mos/bin/llvm-size"
OBJCOPY = ROOT / "tools/llvm-mos/bin/llvm-objcopy"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"

SHARED_H = ROOT / "scripts/c2-lite-chipram-proof-shared.h"
WINDOW_S = ROOT / "scripts/c2-lite-chipram-proof-window.s"
CONTROL_S = ROOT / "scripts/c2-lite-chipram-proof-control.s"
MAIN_C = ROOT / "scripts/c2-lite-chipram-proof-main.c"
SCREEN_C = ROOT / "src/screen.c"
WINDOW_LD = ROOT / "config/c2-lite-chipram-window-link.ld"
CONTROL_LD = ROOT / "config/c2-lite-chipram-controller-link.ld"
AUDIT = ROOT / "docs/planning/c2-lite-bank-ownership-audit.md"
MEMO = ROOT / "docs/planning/c2-lite-rebuild-memo.md"
REFERENCE = ROOT / "docs/reference/mega65-chipset-reference.pdf"
CORE = ROOT / "build/upstream-verification/mega65-core"

WINDOW_INC = BUILD / "c2-lite-chipram-proof-shared.inc"
WINDOW_O = BUILD / "c2-lite-chipram-window.o"
WINDOW_ELF = BUILD / "c2-lite-chipram-window.elf"
WINDOW_BIN = BUILD / "c2-lite-chipram-window.bin"
WINDOW_MAP = BUILD / "c2-lite-chipram-window.map"
WINDOW_DIS = BUILD / "c2-lite-chipram-window.dis"
WINDOW_H = BUILD / "c2-lite-chipram-window.generated.h"
PATTERN_H = BUILD / "c2-lite-chipram-patterns.generated.h"
PRG = BUILD / "c2-lite-chipram-proof.prg"
PRG_ELF = Path(str(PRG) + ".elf")
PRG_MAP = BUILD / "c2-lite-chipram-proof.map"
PRG_DIS = BUILD / "c2-lite-chipram-proof.dis"
REPORT = BUILD / "c2-lite-chipram-static-report.json"
OBSERVATION = BUILD / "c2-lite-chipram-hardware-observation.json"

REFERENCE_SHA = "107610ae3ea9f7e3f1e78915dcbe2cae1a6f404ca2e538762524a7e58cced220"
CORE_COMMIT = "a9158930665763c592d004c895d52eff4a9eefc3"
SEEDS = {"bank2": 0x42, "bank3_boot": 0x31, "bank3_session": 0x73}
CASES = [
    (2, 0x00FF, 0x9000, 1), (2, 0x01FD, 0x9000, 7),
    (2, 0x0FF8, 0x9000, 16), (2, 0x7FC1, 0x9000, 127),
    (2, 0xFF80, 0x9000, 128),
    (3, 0x00FF, 0x9000, 1), (3, 0x01FD, 0x9000, 7),
    (3, 0x0FF8, 0x9000, 16), (3, 0x7FC1, 0x9000, 127),
    (3, 0xFF80, 0x9000, 128),
    (3, 0x2000, 0xC356, 1761), (3, 0x9000, 0x1800, 1781),
]


class ProbeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeError(message)


def run(command: list[str], *, timeout: int = 180) -> str:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True,
                            timeout=timeout, check=False)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise ProbeError(f"command failed ({result.returncode}): {' '.join(command)}: {detail}")
    require(not result.stderr, f"unexpected diagnostics: {result.stderr.strip()}")
    return result.stdout


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def crc16(data: bytes) -> int:
    value = 0xFFFF
    for byte in data:
        value ^= byte << 8
        for _ in range(8):
            value = (((value << 1) ^ 0x1021) if value & 0x8000 else value << 1) & 0xFFFF
    return value


def pattern_byte(seed: int, offset: int) -> int:
    lo = offset & 0xFF
    hi = (offset >> 8) & 0xFF
    return (seed ^ lo ^ ((hi * 17) & 0xFF) ^ (((lo << 3) | (lo >> 5)) & 0xFF)) & 0xFF


def pattern(seed: int) -> bytes:
    return bytes(pattern_byte(seed, offset) for offset in range(65536))


def c_array(name: str, data: bytes) -> str:
    rows = []
    for start in range(0, len(data), 16):
        rows.append("    " + ", ".join(f"0x{x:02x}u" for x in data[start:start + 16]))
    return f"static const uint8_t {name}[{len(data)}] = {{\n" + ",\n".join(rows) + "\n};\n"


def constants() -> dict[str, int]:
    values: dict[str, int] = {}
    text = SHARED_H.read_text(encoding="utf-8")
    for name, token in re.findall(
            r"^#define\s+(C2LT_[A-Z0-9_]+)\s+(0x[0-9a-fA-F]+|[0-9]+)u?\s*$",
            text, re.MULTILINE):
        values[name] = int(token, 0)
    required = {
        "C2LT_FRAME_LO", "C2LT_FRAME_HI", "C2LT_NMI_COUNT",
        "C2LT_EVENT_CODE", "C2LT_EVENT_MODIFIERS", "C2LT_DEQUEUE_COUNT",
        "C2LT_COMMAND", "C2LT_RESPONSE", "C2LT_UNEXPECTED_IRQ",
        "C2LT_STATE", "C2LT_NATIVE_GENERATION", "C2LT_NATIVE_FAMILY",
        "C2LT_FREEZER_RETURNED", "C2LT_CASE_COUNT_DONE",
        "C2LT_FREEZER_BANKS_OK", "C2LT_WRITEBACK_OK", "C2LT_LATENCY_BASE",
        "C2LT_CMD_POLL_EVENT", "C2LT_STATE_PASS", "C2LT_FAMILY_SESSION",
    }
    require(required <= values.keys(), "shared mailbox constants incomplete")
    return values


def generate_inc(values: dict[str, int]) -> None:
    lines = ["; generated from scripts/c2-lite-chipram-proof-shared.h"]
    for name in sorted(values):
        lines.append(f"\t.equ {name}, 0x{values[name]:x}")
    WINDOW_INC.write_text("\n".join(lines) + "\n", encoding="utf-8")


def symbols(elf: Path) -> dict[str, int]:
    result: dict[str, int] = {}
    for line in run([str(NM), "--defined-only", "--numeric-sort", str(elf)]).splitlines():
        parts = line.split()
        if len(parts) >= 3:
            result[parts[-1]] = int(parts[0], 16)
    return result


def build_window() -> None:
    run([str(CC), "-c", "-I", str(BUILD), "-I", str(ROOT / "scripts"),
         str(WINDOW_S), "-o", str(WINDOW_O)])
    run([str(LD), "--gc-sections", str(WINDOW_O), "-T", str(WINDOW_LD),
         "-Map=" + str(WINDOW_MAP), "-o", str(WINDOW_ELF)])
    run([str(OBJCOPY), "-O", "binary", str(WINDOW_ELF), str(WINDOW_BIN)])
    data = WINDOW_BIN.read_bytes()
    require(len(data) == 8192, f"owned window is {len(data)} bytes, expected 8192")
    syms = symbols(WINDOW_ELF)
    require(syms.get("c2lt_window_dispatch") == 0xE000, "window dispatch VMA drift")
    require(syms.get("c2lt_nmi_handler") == int.from_bytes(data[-6:-4], "little"),
            "NMI vector drift")
    require(syms.get("c2lt_fail_closed") == int.from_bytes(data[-4:-2], "little"),
            "reset vector drift")
    require(syms.get("c2lt_irq_handler") == int.from_bytes(data[-2:], "little"),
            "IRQ vector drift")
    prefix_end = max(index for index, byte in enumerate(data[:0x1FFA]) if byte) + 1
    WINDOW_H.write_text(
        "/* generated from the separately linked non-product owned window */\n"
        "#include <stdint.h>\n"
        f"#define C2LT_WINDOW_PREFIX_BYTES {prefix_end}u\n"
        f"#define C2LT_WINDOW_CRC16 0x{crc16(data):04x}u\n"
        f"#define C2LT_WINDOW_SHA256 \"{hashlib.sha256(data).hexdigest()}\"\n"
        + c_array("c2lt_window_prefix", data[:prefix_end])
        + c_array("c2lt_window_vectors", data[-6:]),
        encoding="utf-8")
    WINDOW_DIS.write_text(run([str(OBJDUMP), "-d", str(WINDOW_ELF)]), encoding="utf-8")


def generate_patterns() -> dict[str, int]:
    crcs = {name: crc16(pattern(seed)) for name, seed in SEEDS.items()}
    PATTERN_H.write_text(
        "/* generated identity bindings for complete 64-KiB proof images */\n"
        f"#define C2LT_BANK2_SEED 0x{SEEDS['bank2']:02x}u\n"
        f"#define C2LT_BANK3_BOOT_SEED 0x{SEEDS['bank3_boot']:02x}u\n"
        f"#define C2LT_BANK3_SESSION_SEED 0x{SEEDS['bank3_session']:02x}u\n"
        f"#define C2LT_BANK2_CRC16 0x{crcs['bank2']:04x}u\n"
        f"#define C2LT_BANK3_BOOT_CRC16 0x{crcs['bank3_boot']:04x}u\n"
        f"#define C2LT_BANK3_SESSION_CRC16 0x{crcs['bank3_session']:04x}u\n",
        encoding="utf-8")
    return crcs


def build_controller() -> None:
    run([
        str(CC), "-mllvm", "-rng-seed=0", "-std=c99", "-Os", "-Wall",
        "-DLISP65_SCREEN_DRIVER", "-I", str(BUILD), "-I", str(ROOT / "scripts"),
        "-I", str(ROOT / "src"), str(MAIN_C), str(CONTROL_S), str(SCREEN_C),
        "-Wl,--icf=none", "-Wl,-T," + str(CONTROL_LD),
        "-Wl,-Map," + str(PRG_MAP), "-o", str(PRG),
    ])
    require(PRG.is_file() and PRG_ELF.is_file(), "controller artifacts absent")
    syms = symbols(PRG_ELF)
    require(syms.get("__c2lt_mailbox_start") == 0x7000
            and syms.get("__c2lt_mailbox_end") == 0x7100,
            "controller mailbox geometry drift")
    loaded_end = 0x2001 + PRG.stat().st_size - 2
    require(loaded_end < 0x7000, f"controller crosses mailbox: ${loaded_end:04x}")
    require(syms.get("c2lt_map_window") is not None
            and syms.get("c2lt_rom_write_enable") is not None,
            "map/write-enable seam absent")
    PRG_DIS.write_text(run([str(OBJDUMP), "-d", str(PRG_ELF)]), encoding="utf-8")


def static_verify(values: dict[str, int], crcs: dict[str, int]) -> dict:
    require(sha(REFERENCE) == REFERENCE_SHA, "pinned chipset reference drift")
    require(run(["git", "-C", str(CORE), "rev-parse", "HEAD"]).strip() == CORE_COMMIT,
            "audited mega65-core checkout drift")
    require(AUDIT.is_file() and MEMO.is_file(), "approved memo/audit input absent")
    main = MAIN_C.read_text(encoding="utf-8")
    control = CONTROL_S.read_text(encoding="utf-8").lower()
    dis = PRG_DIS.read_text(encoding="utf-8").lower()
    require("sta $d641" in control and "lda #$02" in control,
            "idempotent ROM-write-enable trap absent")
    require(re.search(r"\bsta\s+\$d700\b", dis) is not None
            and re.search(r"\bsta\s+\$d705\b", dis) is None,
            "proof does not use production F018A D700 trigger shape")
    require("there is deliberately no\n     * retry" in main.lower(),
            "first-observation/no-retry assertion absent")
    require("0x08000000" not in main.lower() and "attic" not in dis,
            "Attic premise leaked into Chip-RAM proof")
    require("native_handle_valid" in main and "C2LT_FAMILY_INVALID" in main,
            "Boot-to-Session stale-generation proof absent")
    require(len(CASES) == 12 and {row[3] for row in CASES} >= {1, 7, 16, 127, 128, 1761, 1781},
            "seven-point transfer matrix drift")
    core_files = {
        relative: sha(CORE / relative) for relative in (
            "src/hyppo/freeze.asm", "src/hyppo/main.asm", "src/hyppo/mem.asm",
            "src/hyppo/dos.asm", "src/vhdl/gs4510.vhdl")
    }
    report = {
        "format": "lisp65-c2-lite-chipram-static-report-v1",
        "status": "host-green-hardware-pending",
        "classification": "standalone-non-product-receipt-less-prefilter",
        "selected_banks": {
            "bank2": "normalized-bytecode-code-plane",
            "bank3": "lifetime-exclusive-boot-session-native-plane",
            "bank1": "untouched-user-graphics-promise",
        },
        "identity": {
            "audit": {"path": str(AUDIT.relative_to(ROOT)), "sha256": sha(AUDIT)},
            "memo": {"path": str(MEMO.relative_to(ROOT)), "sha256": sha(MEMO)},
            "hardware_reference": {"path": str(REFERENCE.relative_to(ROOT)), "sha256": sha(REFERENCE)},
            "audited_core_source_commit": CORE_COMMIT,
            "audited_core_source_files": core_files,
            "device_core_identity": "pending-hardware-capture",
        },
        "pattern_bindings": {
            name: {"seed": seed, "bytes": 65536, "crc16": crcs[name],
                   "sha256": hashlib.sha256(pattern(seed)).hexdigest()}
            for name, seed in SEEDS.items()
        },
        "window": {"bytes": 8192, "crc16": crc16(WINDOW_BIN.read_bytes()),
                   "sha256": sha(WINDOW_BIN)},
        "cases": [
            {"index": index, "source_bank": bank, "source_offset": offset,
             "target_bank": 0, "target_offset": target, "bytes": length,
             "completion": "first-post-return-observation-only"}
            for index, (bank, offset, target, length) in enumerate(CASES)
        ],
        "hardware_protocol": {
            "owned_irq_frame_source": "required",
            "freezer_roundtrip": "required",
            "post_freezer_full_bank_identity": "required-both",
            "post_freezer_writeability": "required-both",
            "xemu": "not-run-non-authoritative",
            "delayed_convergence_or_retry": "forbidden",
        },
        "artifacts": {
            "prg": {"path": str(PRG.relative_to(ROOT)), "bytes": PRG.stat().st_size, "sha256": sha(PRG)},
            "elf": {"path": str(PRG_ELF.relative_to(ROOT)), "bytes": PRG_ELF.stat().st_size, "sha256": sha(PRG_ELF)},
            "map": {"path": str(PRG_MAP.relative_to(ROOT)), "sha256": sha(PRG_MAP)},
            "window": {"path": str(WINDOW_BIN.relative_to(ROOT)), "sha256": sha(WINDOW_BIN)},
        },
        "claims": {"product_bytes": 0, "product_link": "not-run",
                   "hardware": "not-run",
                   "option_a_contract": "class-c-approved-2026-07-21"},
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def build() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    values = constants()
    generate_inc(values)
    build_window()
    crcs = generate_patterns()
    build_controller()
    report = static_verify(values, crcs)
    print("c2-lite-chipram: HOST GREEN hardware=pending "
          f"cases={len(report['cases'])} banks=2/3 bank1=untouched "
          f"prg={report['artifacts']['prg']['sha256'][:16]}")


def record(core_path: Path, mailbox_path: Path, bank2_path: Path,
           bank3_path: Path) -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    values = constants()
    core = core_path.read_bytes()
    mailbox = mailbox_path.read_bytes()
    bank2 = bank2_path.read_bytes()
    bank3 = bank3_path.read_bytes()
    require(len(core) == 4, "core register capture must be four bytes")
    require(len(mailbox) == 0x100, "mailbox capture must be 256 bytes")
    require(len(bank2) == 65536 and len(bank3) == 65536, "bank captures must be 64 KiB")
    base = values["C2LT_CTL_BASE"]
    at = lambda name: mailbox[values[name] - base]
    require(at("C2LT_STATE") == values["C2LT_STATE_PASS"], "target did not publish PASS")
    require(at("C2LT_NATIVE_GENERATION") == 2
            and at("C2LT_NATIVE_FAMILY") == values["C2LT_FAMILY_SESSION"],
            "native Session generation not published")
    require(at("C2LT_FREEZER_RETURNED") == 1, "Freezer return not observed")
    require(at("C2LT_CASE_COUNT_DONE") == len(CASES), "immediate case count incomplete")
    require(at("C2LT_FREEZER_BANKS_OK") == 2, "Freezer bank identity incomplete")
    require(at("C2LT_WRITEBACK_OK") == 2, "post-Freezer writeability incomplete")
    require(bank2 == pattern(SEEDS["bank2"]), "Bank 2 host readback differs")
    require(bank3 == pattern(SEEDS["bank3_session"]), "Bank 3 host readback differs")
    latency_start = values["C2LT_LATENCY_BASE"] - base
    latencies = list(mailbox[latency_start:latency_start + len(CASES)])
    core_version = f"git-{int.from_bytes(core, 'little'):08x}"
    observation = {
        "format": "lisp65-c2-lite-chipram-hardware-prefilter-observation-v1",
        "status": "passed-receipt-less-non-product",
        "static_report": {"path": str(REPORT.relative_to(ROOT)), "sha256": sha(REPORT)},
        "device": {"core_registers": core.hex(), "core_version": core_version,
                   "machine_serial": "TE0000B18447"},
        "result": {
            "immediate_cases": len(CASES), "delayed_successes": 0,
            "raster_tick_deltas": latencies,
            "freezer_bank_identities": 2, "post_freezer_writeable_banks": 2,
            "native_generation": 2, "stale_boot_generation_rejected": True,
        },
        "captures": {
            "mailbox": {"path": str(mailbox_path.relative_to(ROOT)), "sha256": sha(mailbox_path)},
            "bank2": {"path": str(bank2_path.relative_to(ROOT)), "sha256": sha(bank2_path)},
            "bank3": {"path": str(bank3_path.relative_to(ROOT)), "sha256": sha(bank3_path)},
            "core": {"path": str(core_path.relative_to(ROOT)), "sha256": sha(core_path)},
        },
        "claim_limit": "fail-fast hardware prefilter only; no product link or promotion claim",
    }
    OBSERVATION.write_text(json.dumps(observation, indent=2) + "\n", encoding="utf-8")
    print(f"c2-lite-chipram: HARDWARE PREFILTER PASS core={core_version} cases=12/12 freezer=2/2")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build")
    rec = sub.add_parser("record")
    rec.add_argument("--core", type=Path, required=True)
    rec.add_argument("--mailbox", type=Path, required=True)
    rec.add_argument("--bank2", type=Path, required=True)
    rec.add_argument("--bank3", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "build":
            build()
        else:
            record(*(ROOT / getattr(args, name) for name in ("core", "mailbox", "bank2", "bank3")))
    except (ProbeError, OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        print(f"c2-lite-chipram: FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
