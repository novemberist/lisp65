#!/usr/bin/env python3
"""Build/check the non-promotable G5 I/O-trigger attribution carrier.

The first normal-F018B submission is the v7 path.  Only after its bounded
timeout does the carrier repeat the complete $D02F $47/$53 knock and submit
the same immutable job again.  It then holds before product handoff so JTAG
can bind the two I/O snapshots and the unmodified MAP state.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_media_product as MEDIA  # noqa: E402
import c2_lite_canonical_product as CANONICAL  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


SOURCE = ROOT / "scripts/r3-cold-stager-main.c"
CHAIN = ROOT / "scripts/c2-lite-cold-stager-chain.s"
V7 = ROOT / "build/c2.2/acceptance/g5/normal-dma-repack-v7"
OUTPUT = ROOT / "build/c2.2/acceptance/g5/io-trigger-attribution-v1"
STAGER = OUTPUT / "autoboot-io-trigger-attribution.c65"
ELF = Path(str(STAGER) + ".elf")
MAP = Path(str(STAGER) + ".map")
D81 = OUTPUT / "lisp65-product-io-trigger-attribution.d81"
EXTRACTED = OUTPUT / "autoboot-readback.c65"
RECEIPT = OUTPUT / "build-receipt.json"
ATTRIBUTION = OUTPUT / "host-attribution.json"
HARDWARE = OUTPUT / "hardware-run-01"
HARDWARE_RECEIPT = HARDWARE / "hardware-receipt.json"

V7_D81 = V7 / "lisp65-product.d81"
V7_MANIFEST = V7 / "candidate-manifest.json"
V7_HARDWARE = (
    ROOT / "build/c2.2/acceptance/g5/replay-v7/"
    "hardware-first-red-receipt.json"
)
LINK20 = (
    ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link20-hardware-presmoke-first-red-receipt.json"
)
PRODUCT_SOURCE = ROOT / "src/c2_kernal_runtime.c"
PRODUCT_IO = ROOT / "src/c2_kernal_map.s"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"


class AttributionError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AttributionError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"attribution input absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def run(argv: list[str], label: str) -> str:
    result = subprocess.run(
        argv, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        raise AttributionError(
            f"{label} failed ({result.returncode}):\n{result.stdout}")
    return result.stdout


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def source_gate(source: str) -> dict[str, Any]:
    required = (
        "#ifdef LISP65_G5_IO_TRIGGER_PROBE",
        "section(\".bss.g5_trigger_probe\")",
        "static volatile uint8_t g5_trigger_probe[32];",
        "static volatile uint8_t g5_map_snapshot[256];",
        "if (!match && g5_trigger_attempts == 1u)",
        "g5_trigger_probe[16] = wraps;",
        "io_enable();",
        "c2_stage_copy_readback(",
        "g5_probe_hold(match);",
        "ldy #mos16hi(g5_map_snapshot)",
        "lda #$74",
        "sta $d640",
        "\"sta $d700\\n\\t\"",
    )

    def valid(candidate: str) -> bool:
        try:
            failure = candidate.index(
                "if (!match && g5_trigger_attempts == 1u)")
            knock = candidate.index("io_enable();", failure)
            poison = candidate.index(
                "c2_target_readback[poll] = 0xa5u;", knock)
            retry = candidate.index("c2_stage_copy_readback(", poison)
            hold = candidate.index("g5_probe_hold(match);", retry)
            hold_body = candidate.index(
                "static void g5_probe_hold("
            )
            mapping = candidate.index("g5_capture_map();", hold_body)
            border = candidate.index("R3_BORDER =", mapping)
        except ValueError:
            return False
        return (
            all(token in candidate for token in required)
            and failure < knock < poison < retry < hold
            and hold_body < mapping < border
            and "g5_capture_map();" not in candidate[failure:knock]
            and "(uint32_t)(uintptr_t)sector_payload,"
                in candidate[retry:hold]
            and "c2_target_readback[poll] = 0xa5u;"
                in candidate[knock:retry]
            and candidate.count(
                "#ifdef LISP65_G5_IO_TRIGGER_PROBE") >= 3
        )

    def replace_last(candidate: str, old: str, new: str) -> str:
        offset = candidate.rfind(old)
        require(offset >= 0, f"attribution mutation token absent: {old}")
        return candidate[:offset] + new + candidate[offset + len(old):]

    mutations = (
        source.replace("                io_enable();\n", "", 1),
        source.replace(
            "                io_enable();\n",
            "                g5_capture_map();\n                io_enable();\n",
            1),
        replace_last(
            source,
            "                    (uint32_t)(uintptr_t)sector_payload,",
            "                    (uint32_t)(uintptr_t)verify_buffer,"),
        replace_last(
            source,
            "c2_target_readback[poll] = 0xa5u;",
            "c2_target_readback[poll] = sector_payload[poll];"),
        source.replace(
            "\"sta $d700\\n\\t\"", "\"sta $d705\\n\\t\"", 1),
        source.replace(
            "static volatile uint8_t g5_trigger_probe[32];",
            "static volatile uint8_t g5_trigger_probe[31];", 1),
        source.replace("                g5_probe_hold(match);\n", "", 1),
    )
    require(valid(source) and all(not valid(value) for value in mutations),
            "G5 trigger-attribution source/mutation gate red")
    return {
        "status": "passed-first-timeout-then-knock-single-variable-AB",
        "mutations_rejected": len(mutations),
        "ordering": [
            "unaltered-v7-normal-submit",
            "bounded-192-wrap-timeout",
            "immediate-D02F-47-53-knock",
            "same-normal-submit",
            "bounded-result",
            "MAP-capture-after-AB",
            "hold-before-product-handoff",
        ],
    }


def build() -> dict[str, Any]:
    require(not OUTPUT.exists(), "G5 I/O-trigger attribution is one-shot")
    require(V7_HARDWARE.is_file(), "v7 hardware first-red must precede probe")
    manifest = json.loads(V7_MANIFEST.read_text(encoding="utf-8"))
    hardware = json.loads(V7_HARDWARE.read_text(encoding="utf-8"))
    link20 = json.loads(LINK20.read_text(encoding="utf-8"))
    require(
        hardware["status"] == "first-red-normal-dma-write-not-visible"
        and link20["root_cause"]["class"]
        == "firmware-to-product-io-personality-boundary-not-normalized",
        "G5/Link-20 attribution authority drift")
    source = SOURCE.read_text(encoding="utf-8")
    source_result = source_gate(source)
    OUTPUT.mkdir(parents=True)

    c_object = OUTPUT / "autoboot-main.o"
    s_object = OUTPUT / "autoboot-chain.o"
    build_id = int(manifest["product_build_id"], 16)
    run([
        str(CANONICAL.COMPILER), "-std=c99", "-Oz", "-Wall", "-Wextra",
        "-Werror", "-DLISP65_C2_LITE_MEDIA_STAGER",
        "-DLISP65_G5_IO_TRIGGER_PROBE",
        f"-DR3_EXPECTED_PRODUCT_BUILD_ID=0x{build_id:08x}UL",
        "-c", relative(SOURCE), "-o", relative(c_object),
    ], "G5 trigger-attribution C build")
    run([
        str(CANONICAL.COMPILER), "-Qunused-arguments",
        "-c", relative(CHAIN), "-o", relative(s_object),
    ], "G5 trigger-attribution assembler build")
    run([
        "/usr/bin/setarch", os.uname().machine, "-R",
        str(CANONICAL.COMPILER), "-Oz",
        f"-Wl,-Map,{relative(MAP)}",
        relative(c_object), relative(s_object),
        "-o", relative(STAGER),
    ], "G5 trigger-attribution link")

    truth = ElfTruth.read(
        ELF, llvm_readobj=CANONICAL.COMPILER.parent / "llvm-readobj",
        include_section_data=True)
    probe = truth.symbol("g5_trigger_probe")
    mapping = truth.symbol("g5_map_snapshot")
    jobs = truth.symbol("c2_stage_jobs")
    require(
        probe.section == mapping.section == jobs.section == ".bss"
        and probe.bytes == 32 and mapping.bytes == 256 and jobs.bytes == 24
        and mapping.value % 256 == 0,
        "G5 trigger-attribution linked witness geometry drift")
    disassembly = run(
        [str(OBJDUMP), "-d", "--no-show-raw-insn", relative(ELF)],
        "G5 trigger-attribution disassembly")
    linked = disassembly.lower()
    require(
        sum(
            "sta\t$d02f" in line or "stx\t$d02f" in line
            for line in linked.splitlines()) >= 6
        and linked.count("sta\t$d700") >= 2
        and "sta\t$d640" in linked,
        "G5 trigger-attribution linked control-flow evidence drift")

    c1541 = shutil.which("c1541")
    require(c1541 is not None, "c1541 is unavailable")
    shutil.copyfile(V7_D81, D81)
    run([
        c1541, str(D81),
        "-delete", "autoboot.c65",
        "-write", str(STAGER), "autoboot.c65",
        "-read", "autoboot.c65", str(EXTRACTED),
    ], "G5 trigger-attribution D81 replacement")
    require(EXTRACTED.read_bytes() == STAGER.read_bytes(),
            "diagnostic D81 stager readback drift")

    v7_disassembly = run(
        [str(OBJDUMP), "-d", "--no-show-raw-insn",
         relative(V7 / "autoboot.c65.elf")],
        "v7 cold-stager disassembly")
    lower = v7_disassembly.lower()
    last_knock = lower.rfind("sta\t$d02f", 0, lower.find("sta\t$d700"))
    unmap = lower.rfind("sta\t$d680", 0, lower.find("sta\t$d700"))
    trigger = lower.find("sta\t$d700")
    require(0 <= last_knock < unmap < trigger,
            "v7 trigger-boundary ordering attribution drift")
    product = PRODUCT_SOURCE.read_text(encoding="utf-8")
    product_io = PRODUCT_IO.read_text(encoding="utf-8")
    ownership = product.index("C2K_SECTION uint8_t c2_kernal_take_ownership")
    require(
        product.index("c2_kernal_reveal_io();", ownership)
        < product.index("c2k_copy(", ownership)
        and "lda #$47" in product_io and "lda #$53" in product_io,
        "hardware-proven product I/O-boundary source drift")

    replay = ROOT / "build/c2.2/acceptance/g5/replay-v7/first-red-readback"
    payload = (replay / "sector-payload-live.bin").read_bytes()
    old = (replay / "bank2-prefix-live.bin").read_bytes()
    equal_offsets = [
        {"offset": index, "value": f"0x{before:02x}"}
        for index, (before, after) in enumerate(zip(payload, old))
        if before == after
    ]
    require(equal_offsets == [
        {"offset": 140, "value": "0x01"},
        {"offset": 168, "value": "0x01"},
        {"offset": 189, "value": "0x0c"},
    ], "251/254 equality explanation drift")

    attribution = {
        "format": "lisp65-c2-lite-g5-io-trigger-host-attribution-v1",
        "status": "ready-for-single-variable-hardware-AB",
        "v7_boundary": {
            "last_io_knock": "inside f011_read",
            "after_knock_before_trigger": [
                "F011 command and wait",
                "F011 buffer map",
                "CPU copy and CRC",
                "F011 buffer unmap via $D680=$82",
                "normal-F018B descriptor construction",
            ],
            "immediate_knock_before_D700": False,
            "MAP_instructions_in_stager": 0,
        },
        "product_reference": {
            "link20": bind(LINK20),
            "normalization": (
                "c2_kernal_reveal_io immediately at the ownership boundary "
                "before the first CIA/VIC/DMA access"
            ),
        },
        "diff_251_of_254": {
            "meaning": (
                "No three bytes moved. The old Bank-2 target happens to "
                "equal the new payload at exactly three positions."
            ),
            "equal_offsets": equal_offsets,
            "different_offsets": 251,
        },
        "probe_design": {
            "first_submission": "byte-identical v7 path",
            "only_AB_variable": "immediate complete $D02F $47/$53 knock",
            "map_capture_timing": (
                "after both submissions, because the stager executes no MAP "
                "instruction and an earlier HYPPO trap would perturb the AB"
            ),
            "io_witnesses_each_side": [
                "$D012-before-delay", "$D031", "$D054", "$D02F",
                "$D700", "$D703", "$D012-after-delay",
                "$D031-after-delay",
            ],
        },
        "claim_limit": (
            "Host/ELF attribution and non-promotable hardware protocol only. "
            "It does not yet prove the I/O-personality hypothesis or change "
            "the acceptance tool or product."
        ),
    }
    ATTRIBUTION.write_text(
        json.dumps(attribution, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")

    receipt = {
        "format": "lisp65-c2-lite-g5-io-trigger-attribution-carrier-v1",
        "recorded_on": "2026-07-26",
        "status": "built-not-run-non-promotable",
        "authority": {
            "v7_manifest": bind(V7_MANIFEST),
            "v7_hardware_first_red": bind(V7_HARDWARE),
            "link20_io_personality_precedent": bind(LINK20),
            "host_attribution": bind(ATTRIBUTION),
        },
        "candidate": {
            "stager": bind(STAGER),
            "stager_elf": bind(ELF),
            "stager_map": bind(MAP),
            "product_d81": bind(D81),
            "d81_stager_readback": bind(EXTRACTED),
            "product_bytes_changed": 0,
            "diagnostic_identity_promotable": False,
        },
        "linked_witnesses": {
            "probe": {
                "vma": f"0x{probe.value:04x}",
                "bytes": probe.bytes,
            },
            "map_snapshot": {
                "vma": f"0x{mapping.value:04x}",
                "bytes": mapping.bytes,
                "page_aligned": True,
            },
            "stage_jobs": {
                "vma": f"0x{jobs.value:04x}",
                "bytes": jobs.bytes,
            },
        },
        "gates": {
            "source": source_result,
            "linked_io_knock_store_minimum": 6,
            "linked_D700_store_minimum": 2,
            "hyppo_MAP_capture_present": True,
        },
        "hardware_protocol": {
            "expected_baseline": "first submission times out with old target",
            "outcomes": {
                "green-G5-IO-KNOCK-A/B-PASS": (
                    "same job becomes visible only after the immediate knock; "
                    "I/O-personality boundary hypothesis is proven"
                ),
                "red-G5-IO-KNOCK-A/B-FAIL": (
                    "immediate knock is insufficient; bind I/O/MAP witnesses "
                    "and reject the hypothesis before another fix"
                ),
            },
            "readback": {
                "probe_vma": f"0x{probe.value:04x}",
                "probe_bytes": probe.bytes,
                "map_vma": f"0x{mapping.value:04x}",
                "map_bytes": 6,
                "jobs_vma": f"0x{jobs.value:04x}",
                "jobs_bytes": jobs.bytes,
                "bank2_vma": "0x00020000",
                "bank2_bytes": 254,
            },
        },
        "execution_accounting": {
            "cold_stager_compiler_runs": 1,
            "product_compiler_runs": 0,
            "product_linker_runs": 0,
            "hardware_runs": 0,
        },
        "claim_limit": (
            "One non-promotable, single-variable hardware attribution. No "
            "G5/G6, promotion, release, or product claim is authorized."
        ),
    }
    RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return receipt


def check() -> dict[str, Any]:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(
        receipt["status"] == "built-not-run-non-promotable"
        and receipt["authority"]["v7_manifest"] == bind(V7_MANIFEST)
        and receipt["authority"]["v7_hardware_first_red"]
        == bind(V7_HARDWARE)
        and receipt["authority"]["host_attribution"] == bind(ATTRIBUTION)
        and receipt["candidate"]["stager"] == bind(STAGER)
        and receipt["candidate"]["stager_elf"] == bind(ELF)
        and receipt["candidate"]["product_d81"] == bind(D81)
        and receipt["candidate"]["d81_stager_readback"] == bind(EXTRACTED),
        "G5 I/O-trigger attribution carrier drift")
    return receipt


def utc_mtime(path: Path) -> str:
    return datetime.fromtimestamp(
        path.stat().st_mtime, tz=timezone.utc
    ).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def record_hardware() -> dict[str, Any]:
    host = check()
    paths = {
        name: HARDWARE / filename for name, filename in {
            "deployment": "deploy.log",
            "screen_log": "screen.log",
            "screen": "screen.png",
            "probe": "trigger-probe.bin",
            "map": "map-snapshot.bin",
            "jobs": "stage-jobs.bin",
            "payload": "sector-payload.bin",
            "bank2": "bank2-prefix.bin",
            "target": "target-readback.bin",
            "verify": "verify-buffer.bin",
        }.items()
    }
    for path in paths.values():
        require(path.is_file(), f"hardware witness absent: {path}")
    deploy = paths["deployment"].read_text(encoding="utf-8")
    screen = paths["screen_log"].read_text(
        encoding="utf-8", errors="replace")
    plain_screen = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", screen)
    reset = re.search(
        r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d\d\dZ) NOTE reseting "
        r"MEGA65 and exiting",
        deploy,
    )
    require(
        "Uploaded 819200 bytes in " in deploy
        and reset is not None
        and "G5" in plain_screen and "KNOCK" in plain_screen
        and "FAIL" in plain_screen,
        "G5 I/O-trigger hardware execution envelope drift")

    probe = paths["probe"].read_bytes()
    mapping = paths["map"].read_bytes()
    jobs = paths["jobs"].read_bytes()
    payload = paths["payload"].read_bytes()
    bank2 = paths["bank2"].read_bytes()
    target = paths["target"].read_bytes()
    verify = paths["verify"].read_bytes()
    truth = ElfTruth.read(
        ELF, llvm_readobj=CANONICAL.COMPILER.parent / "llvm-readobj",
        include_section_data=True)
    source = truth.symbol("sector_payload").value
    readback = truth.symbol("c2_target_readback").value
    expected_jobs = bytes((
        0x04, 0xfe, 0x00,
        source & 0xff, (source >> 8) & 0xff, 0x00,
        0x00, 0x00, 0x02, 0x00, 0x00, 0x00,
        0x00, 0xfe, 0x00,
        0x00, 0x00, 0x02,
        readback & 0xff, (readback >> 8) & 0xff, 0x00,
        0x00, 0x00, 0x00,
    ))
    require(
        len(probe) == 32 and len(mapping) == 6 and len(jobs) == 24
        and len(payload) == len(bank2) == len(target) == 254
        and jobs == expected_jobs
        and payload == (ROOT / (
            "build/c2.2/acceptance/r5/product/"
            "01-bank2-static-code.bin")).read_bytes()[:254]
        and bank2 == target
        and sum(a != b for a, b in zip(payload, bank2)) == 251
        and probe[:8] == bytes.fromhex("c5e04000c70127e0")
        and probe[8:16] == bytes.fromhex("04e04000e80165e0")
        and probe[16:20] == bytes((192, 192, 0, 2))
        and mapping == bytes.fromhex("e00083000000"),
        "G5 I/O-trigger hardware witness classification drift")
    equal_offsets = [
        {"offset": index, "value": f"0x{before:02x}"}
        for index, (before, after) in enumerate(zip(payload, bank2))
        if before == after
    ]
    require(equal_offsets == [
        {"offset": 140, "value": "0x01"},
        {"offset": 168, "value": "0x01"},
        {"offset": 189, "value": "0x0c"},
    ], "G5 I/O-trigger 251/254 explanation drift")

    receipt = {
        "format": "lisp65-c2-lite-g5-io-trigger-hardware-attribution-v1",
        "recorded_on": "2026-07-26",
        "status": "hardware-rejected-io-visibility-and-personality-hypothesis",
        "authority": {
            "carrier": bind(RECEIPT),
            "host_attribution": bind(ATTRIBUTION),
            "candidate": host["candidate"]["product_d81"],
        },
        "deployment": {
            **bind(paths["deployment"]),
            "device": "/dev/ttyUSB1",
            "machine_serial": "03636093",
            "remote_name": "L65G5IO.D81",
            "uploaded_bytes_reported": 819200,
            "reset_at_utc": reset.group(1),
        },
        "first_red": {
            "frame": "red",
            "message": "G5 IO KNOCK A/B FAIL",
            "stable_capture_at_utc": utc_mtime(paths["screen"]),
            "screen": bind(paths["screen"]),
            "screen_log": bind(paths["screen_log"]),
        },
        "witnesses": {
            key: bind(paths[key]) for key in (
                "probe", "map", "jobs", "payload", "bank2", "target",
                "verify")
        },
        "classification": {
            "baseline": {
                "raster_before_after": ["0xc5", "0x27"],
                "D031": "0xe0",
                "D054": "0x40",
                "timeout_low_raster_wraps": 192,
            },
            "immediate_knock": {
                "raster_before_after": ["0x04", "0x65"],
                "D031": "0xe0",
                "D054": "0x40",
                "timeout_low_raster_wraps": 192,
            },
            "map": "e0 00 83 00 00 00 (expected inherited C65/BOOT map)",
            "same_job_after_knock_matched": False,
            "io_registers_live_both_sides": True,
            "D700_observation_changed": ["0xc7", "0xe8"],
            "target_unchanged": True,
            "hypothesis": (
                "Rejected: neither hidden I/O, stale MEGA65 personality nor "
                "the inherited MAP state explains the absent Bank-2 write."
            ),
        },
        "diff_251_of_254": {
            "meaning": (
                "No three bytes moved; old target and new payload merely "
                "coincide at three offsets."
            ),
            "equal_offsets": equal_offsets,
            "different_offsets": 251,
        },
        "execution_accounting": {
            "cold_stager_compiler_runs": 0,
            "product_compiler_runs": 0,
            "product_linker_runs": 0,
            "hardware_runs": 1,
        },
        "claim_limit": (
            "Non-promotable acceptance-tool attribution only. It rejects one "
            "hypothesis; it does not establish G5 or alter product bytes."
        ),
    }
    HARDWARE_RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("build", "check", "record-hardware"))
    args = parser.parse_args()
    value = (
        build() if args.action == "build"
        else record_hardware() if args.action == "record-hardware"
        else check()
    )
    if args.action == "record-hardware":
        print(json.dumps({
            "status": value["status"],
            "receipt": relative(HARDWARE_RECEIPT),
            "classification": value["classification"],
        }, indent=2, sort_keys=True))
        return 0
    print(json.dumps({
        "status": value["status"],
        "receipt": relative(RECEIPT),
        "candidate": value["candidate"]["product_d81"],
        "linked_witnesses": value["linked_witnesses"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        AttributionError, MEDIA.MediaError, OSError, ValueError, KeyError,
        json.JSONDecodeError,
    ) as error:
        print(f"c2-lite-media-g5-io-trigger-attribution: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
