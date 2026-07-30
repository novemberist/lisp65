#!/usr/bin/env python3
"""Build, verify and adjudicate the v1.2.4 Chip-RAM visibility curve."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any

from elf_truth import ElfTruth, ElfTruthError


ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build/post-promotion/v124/chipram-visibility"
ARTIFACTS = BUILD / "preparation"
SOURCE = ROOT / "tools/host-lisp/fixtures/c2_v124_chipram_visibility_curve.c"
LINKER = ROOT / "config/c2-v124-chipram-visibility-link.ld"
CONTRACT = ROOT / "docs/planning/c2d-append-visibility-measurement-contract.md"
PLAN = ROOT / "docs/planning/1.2.4-work-plan.md"
PRODUCT_DMA = ROOT / "src/c2_platform_dma.c"
CANDIDATE = ROOT / (
    "build/c2.2/v1.2.4-candidate-product-link81/"
    "canonical-product-manifest.json")
G5_DEPLOYMENT = ROOT / (
    "build/c2.2/v1.2.4-acceptance/r5/hardware-session-01/deployment.json")
G5_RECEIPT = ROOT / (
    "build/c2.2/v1.2.4-acceptance/r5/hardware-session-01/"
    "g5-hardware-receipt.json")
PREPARATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.4-chipram-visibility-curve-preparation-receipt.json")
HARDWARE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.4-chipram-visibility-curve-hardware-receipt.json")
PRG = ARTIFACTS / "curve.prg"
ELF = Path(str(PRG) + ".elf")
MAP = ARTIFACTS / "curve.map"
DEPLOYMENT = ARTIFACTS / "deployment.json"
ZERO_C2J = ARTIFACTS / "zero-c2j.bin"

CC = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"

FORMAT = "lisp65-c2.2-v1.2.4-chipram-visibility-curve-v1"
MAILBOX_ADDRESS = 0x7000
MAILBOX_BYTES = 256
PHASE_OWNER_ADDRESS = 0x89
C2J_ADDRESS = 0x5C640
C2J_BYTES = 64
BANK5_ADDRESS = 0x50000
BANK5_BYTES = 65536
TARGET_OFFSET = 0x8430
TARGET_ADDRESS = BANK5_ADDRESS + TARGET_OFFSET
TARGET_BYTES = 256
REPETITIONS = 20
CURVE_BYTES = 4 * TARGET_BYTES
TRACE_ADDRESS = 0xC1F4
C2D_HEADER_ADDRESS = 0x50000
PLACE_ROW_ADDRESS = 0x500F0


class CurveError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CurveError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"missing file: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def load(path: Path, label: str) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"{label} missing")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CurveError(f"cannot read {label}: {error}") from error
    require(isinstance(value, dict), f"{label} must be a JSON object")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )


def run(command: list[str], label: str, *, timeout: int = 180) -> str:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, timeout=timeout, check=False)
    require(
        result.returncode == 0,
        f"{label} failed ({result.returncode}):\n{result.stdout[-6000:]}")
    return result.stdout


def pattern(seed: int) -> bytes:
    return bytes(
        (seed ^ offset ^ (((offset << 3) | (offset >> 5)) & 0xFF)) & 0xFF
        for offset in range(256))


def crc16(data: bytes) -> int:
    value = 0xFFFF
    for byte in data:
        value ^= byte << 8
        for _ in range(8):
            value = (
                ((value << 1) ^ 0x1021)
                if value & 0x8000 else value << 1) & 0xFFFF
    return value


def u16(data: bytes, offset: int) -> int:
    return data[offset] | (data[offset + 1] << 8)


def artifact(manifest: dict[str, Any], role: str) -> dict[str, Any]:
    rows = [
        row for row in manifest.get("artifacts", [])
        if isinstance(row, dict) and row.get("role") == role]
    require(len(rows) == 1, f"candidate role is not unique: {role}")
    row = rows[0]
    path = ROOT / row["path"]
    require(
        path.is_file() and path.stat().st_size == row["bytes"]
        and sha256(path) == row["sha256"],
        f"candidate role binding drift: {role}")
    return row


def source_invariants(text: str) -> None:
    required = [
        "#define PROBE_TARGET 0x8430u",
        "#define PROBE_BANK 5u",
        "#define PROBE_BYTES 256u",
        "#define PROBE_REPETITIONS 20u",
        "#define PROBE_DELAY_2MS_LINES 31u",
        "#define PROBE_DELAY_100MS_AFTER_2MS_LINES 1532u",
        "#define PROBE_DELAY_714MS_AFTER_100MS_LINES 9593u",
        "DMA_MODE = 1u;",
        "sta $d702",
        "sta $d701",
        "sta $d700",
        "product_dma_copy(",
        "__asm__ volatile(\"sei\"",
        "PROBE_MAILBOX[5] = PROBE_STATE_COMPLETE;",
    ]
    for token in required:
        require(token in text, f"curve source invariant absent: {token}")
    forbidden = ["sta $d705", "0x08000000", "PROBE_BANK 4u"]
    for token in forbidden:
        require(token not in text, f"curve source forbidden token: {token}")
    for index in range(12):
        require(
            f"c2_dma_list[{index}]" in text,
            f"F018B descriptor field absent: {index}")
    require(
        "C2J=CLEAR before entry" in text
        and "unpublished C2D append-scratch" in text,
        "safety preconditions absent from source")


def build() -> tuple[ElfTruth, dict[str, Any]]:
    manifest = load(CANDIDATE, "Link-81 candidate manifest")
    g5 = load(G5_RECEIPT, "v1.2.4 G5 receipt")
    deployment = load(G5_DEPLOYMENT, "v1.2.4 G5 deployment")
    require(
        g5.get("status") == "passed-fresh-nine-case-G5"
        and len(g5.get("cases", [])) == 9,
        "fresh v1.2.4 G5 authority is not green")
    c2d = artifact(manifest, "c2d-v6-code-plane")
    require(
        c2d["bytes"] == TARGET_OFFSET,
        "probe target is not the live Link-81 published C2D end")
    stage = deployment.get("stage_authorities", {}).get("c2d", {})
    require(
        stage.get("address") == BANK5_ADDRESS
        and stage.get("bytes") == c2d["bytes"]
        and stage.get("sha256") == c2d["sha256"],
        "G5 C2D stage authority differs from Link-81 candidate")

    text = SOURCE.read_text(encoding="utf-8")
    source_invariants(text)
    product = PRODUCT_DMA.read_text(encoding="utf-8")
    for token in (
        "c2_dma_list[0] = 0u;",
        "c2_dma_list[1] = (uint8_t)length;",
        "c2_dma_list[2] = (uint8_t)(length >> 8);",
        "c2_dma_list[11] = 0u;",
        "sta $d702", "sta $d701", "sta $d700",
    ):
        require(token in product and token in text,
                f"product-shape token diverged: {token}")

    if ARTIFACTS.exists():
        shutil.rmtree(ARTIFACTS)
    ARTIFACTS.mkdir(parents=True)
    run([
        str(CC), "-mllvm", "-rng-seed=0", "-std=c99", "-Oz",
        "-Wall", "-Werror", "-ffunction-sections", "-I", "src",
        str(SOURCE), "-Wl,--gc-sections", f"-Wl,-T,{LINKER}",
        f"-Wl,-Map,{MAP}", "-o", str(PRG),
    ], "compile visibility curve")
    require(PRG.is_file() and ELF.is_file(), "curve artifacts missing")

    truth = ElfTruth.read(
        ELF, llvm_readobj=READOBJ, include_section_data=True)
    symbols = {
        name: truth.symbol(name) for name in (
            "c2_dma_list", "probe_source", "probe_readback", "probe_curve",
            "__bss_end", "__c2_v124_curve_mailbox_start",
            "__c2_v124_curve_mailbox_end", "product_dma_copy", "main")}
    require(
        symbols["c2_dma_list"].bytes == 12
        and symbols["probe_source"].bytes == TARGET_BYTES
        and symbols["probe_readback"].bytes == TARGET_BYTES
        and symbols["probe_curve"].bytes == CURVE_BYTES,
        "curve ELF witness sizes drift")
    require(
        symbols["__bss_end"].value <= MAILBOX_ADDRESS
        and symbols["__c2_v124_curve_mailbox_start"].value == MAILBOX_ADDRESS
        and symbols["__c2_v124_curve_mailbox_end"].value
            == MAILBOX_ADDRESS + MAILBOX_BYTES,
        "curve ELF/mailbox geometry drift")

    loaded = b"".join(
        truth.section_bytes(row.name)
        for row in truth.sections
        if row.bytes and row.section_type == "SHT_PROGBITS"
        and "SHF_ALLOC" in row.flags)
    opcode_counts = {
        "sta_D700": loaded.count(b"\x8d\x00\xd7"),
        "sta_D701": loaded.count(b"\x8d\x01\xd7"),
        "sta_D702": loaded.count(b"\x8d\x02\xd7"),
        "sta_D703": loaded.count(b"\x8d\x03\xd7"),
        "sta_D705": loaded.count(b"\x8d\x05\xd7"),
    }
    require(
        opcode_counts == {
            "sta_D700": 1, "sta_D701": 1, "sta_D702": 1,
            "sta_D703": 1, "sta_D705": 0},
        f"bound DMA trigger shape drift: {opcode_counts}")

    ZERO_C2J.write_bytes(bytes(C2J_BYTES))
    geometry = {
        name: {"address": row.value, "bytes": row.bytes,
               "section": row.section}
        for name, row in symbols.items()
    }
    deployment_value = {
        "format": FORMAT,
        "status": "prepared-nonpromotable-hardware-measurement",
        "prg": bind(PRG),
        "elf": bind(ELF),
        "map": bind(MAP),
        "zero_c2j": bind(ZERO_C2J),
        "geometry": geometry,
        "addresses": {
            "mailbox": MAILBOX_ADDRESS,
            "mailbox_bytes": MAILBOX_BYTES,
            "phase_owner": PHASE_OWNER_ADDRESS,
            "C2J": C2J_ADDRESS,
            "C2J_bytes": C2J_BYTES,
            "Bank5": BANK5_ADDRESS,
            "Bank5_bytes": BANK5_BYTES,
            "target": TARGET_ADDRESS,
            "target_offset": TARGET_OFFSET,
            "target_bytes": TARGET_BYTES,
            "trace": TRACE_ADDRESS,
            "C2D_header": C2D_HEADER_ADDRESS,
            "place_row": PLACE_ROW_ADDRESS,
        },
        "accepted_G5_C2D_stage": stage,
        "opcode_counts": opcode_counts,
    }
    write_json(DEPLOYMENT, deployment_value)
    return truth, deployment_value


def mutation_selftest() -> int:
    source = SOURCE.read_text(encoding="utf-8")
    mutations = [
        ("repetitions", "#define PROBE_REPETITIONS 20u",
         "#define PROBE_REPETITIONS 19u"),
        ("bytes", "#define PROBE_BYTES 256u",
         "#define PROBE_BYTES 255u"),
        ("target", "#define PROBE_TARGET 0x8430u",
         "#define PROBE_TARGET 0x842fu"),
        ("bank", "#define PROBE_BANK 5u", "#define PROBE_BANK 4u"),
        ("trigger", "sta $d700", "sta $d705"),
        ("delay-2ms", "PROBE_DELAY_2MS_LINES 31u",
         "PROBE_DELAY_2MS_LINES 30u"),
        ("delay-100ms", "PROBE_DELAY_100MS_AFTER_2MS_LINES 1532u",
         "PROBE_DELAY_100MS_AFTER_2MS_LINES 1531u"),
        ("clear-contract", "C2J=CLEAR before entry",
         "C2J is unchecked before entry"),
    ]
    for name, old, new in mutations:
        require(old in source, f"mutation anchor absent: {name}")
        try:
            source_invariants(source.replace(old, new, 1))
        except CurveError:
            continue
        raise CurveError(f"source mutation survived: {name}")
    return len(mutations)


def prepare() -> dict[str, Any]:
    _, deployment = build()
    mutations = mutation_selftest()
    value = {
        "format": FORMAT,
        "version": 1,
        "recorded_on": date.today().isoformat(),
        "status": "passed-host-prepared-awaiting-device-curve",
        "classification":
            "nonpromotable-measurement-rider-not-acceptance",
        "authority": {
            "contract": bind(CONTRACT),
            "plan": bind(PLAN),
            "source": bind(SOURCE),
            "linker": bind(LINKER),
            "product_DMA_source": bind(PRODUCT_DMA),
            "candidate_manifest": bind(CANDIDATE),
            "G5_deployment": bind(G5_DEPLOYMENT),
            "G5_receipt": bind(G5_RECEIPT),
            "deployment": bind(DEPLOYMENT),
        },
        "geometry": deployment["geometry"],
        "safety": {
            "only_Bank5_write":
                "0x58430..0x5852f, unpublished Link-81 append scratch",
            "published_C2D_end_derived_from_candidate_bytes": TARGET_OFFSET,
            "C2J_must_be_CLEAR": True,
            "phase_owner_must_be_NONE": True,
            "product_bytes": 0,
            "product_links": 0,
            "promotable": False,
        },
        "curve": {
            "bytes": TARGET_BYTES,
            "points": [
                {"id": "immediate", "cumulative_lines": 0},
                {"id": "2ms", "cumulative_lines": 31},
                {"id": "100ms", "cumulative_lines": 1563},
                {"id": "714ms", "cumulative_lines": 11156},
            ],
            "immediate_repetitions": REPETITIONS,
            "timing_authority": "device-raster-lines-not-host-time",
        },
        "host_execution_witness": {
            "compiled_artifacts": 3,
            "source_mutations_rejected": mutations,
            "bound_trigger_shape": deployment["opcode_counts"],
        },
        "policy": {
            "can_make_acceptance_chain_red": False,
            "red_acceptance_row_invalidates_measurement": False,
            "mismatch_disposition":
                "prepared-Class-C-review-at-halt-2",
            "all_exact_disposition":
                "bounded-exoneration-not-family-closure",
        },
    }
    write_json(PREPARATION, value)
    return value


def exact_file(out: Path, name: str, size: int) -> bytes:
    path = out / name
    require(path.is_file() and not path.is_symlink(), f"capture absent: {name}")
    data = path.read_bytes()
    require(len(data) == size, f"capture width drift: {name}")
    return data


def evaluate(out: Path, *, write: bool = True) -> dict[str, Any]:
    preparation = load(PREPARATION, "curve preparation receipt")
    deployment = load(DEPLOYMENT, "curve deployment")
    accepted_c2d_path = (
        ROOT / deployment["accepted_G5_C2D_stage"]["path"])
    accepted_c2d = accepted_c2d_path.read_bytes()
    mailbox = exact_file(out, "mailbox.bin", MAILBOX_BYTES)
    curve = exact_file(out, "curve.bin", CURVE_BYTES)
    before = exact_file(out, "bank5-before.bin", BANK5_BYTES)
    after = exact_file(out, "bank5-after.bin", BANK5_BYTES)
    phase_before = exact_file(out, "phase-owner-before.bin", 1)
    phase_after = exact_file(out, "phase-owner-after.bin", 1)
    c2j_before = exact_file(out, "c2j-before.bin", C2J_BYTES)
    c2j_after = exact_file(out, "c2j-after.bin", C2J_BYTES)
    trace = exact_file(out, "require-trace.bin", 2)
    header = exact_file(out, "c2d-header.bin", 48)
    place = exact_file(out, "place-row.bin", 32)

    require(
        mailbox[:6] == b"CVC1\x01\xa5"
        and mailbox[6] == REPETITIONS
        and u16(mailbox, 24) == TARGET_OFFSET,
        "curve mailbox identity/state drift")
    require(phase_before == phase_after == b"\0",
            "phase owner was not NONE across curve")
    require(c2j_before == c2j_after == bytes(C2J_BYTES),
            "C2J was not CLEAR across curve")
    require(
        header == accepted_c2d[:48]
        and place == accepted_c2d[
            PLACE_ROW_ADDRESS - BANK5_ADDRESS:
            PLACE_ROW_ADDRESS - BANK5_ADDRESS + 32],
        "require C2D header/place peek differs from accepted G5 authority")
    require(before[:TARGET_OFFSET] == after[:TARGET_OFFSET],
            "published C2D changed during curve")
    allowed = set(range(TARGET_OFFSET, TARGET_OFFSET + TARGET_BYTES))
    changed = {
        index for index, pair in enumerate(zip(before, after))
        if pair[0] != pair[1]}
    require(changed <= allowed, "Bank-5 write escaped probe scratch")
    expected_final = pattern(0x80 + REPETITIONS - 1)
    require(
        after[TARGET_OFFSET:TARGET_OFFSET + TARGET_BYTES] == expected_final,
        "final probe target does not contain repetition-19 pattern")

    expected_curve = pattern(0x6D)
    expected_crc = crc16(expected_curve)
    observed_crcs = [u16(mailbox, 10 + 2 * index) for index in range(4)]
    curve_exact = [
        curve[index * TARGET_BYTES:(index + 1) * TARGET_BYTES]
            == expected_curve
        for index in range(4)]
    require(u16(mailbox, 18) == expected_crc,
            "device expected CRC differs from host oracle")
    mismatch = (
        mailbox[7] != 0 or u16(mailbox, 8) != 0
        or not all(curve_exact)
        or any(value != expected_crc for value in observed_crcs))
    classification = (
        "measured-chipram-immediate-visibility-mismatch-class-c-review"
        if mismatch else
        "bounded-exoneration-chipram-L10-variant-curve20")

    value = {
        "format": FORMAT,
        "version": 1,
        "recorded_on": date.today().isoformat(),
        "status": "completed-measurement-valid",
        "classification": classification,
        "authority": {
            "preparation": bind(PREPARATION),
            "deployment": bind(DEPLOYMENT),
            "G5_receipt": bind(G5_RECEIPT),
        },
        "measurement": {
            "curve_expected_crc16": expected_crc,
            "curve_observed_crc16": observed_crcs,
            "curve_snapshots_exact": curve_exact,
            "curve_mismatch_points": mailbox[7],
            "immediate_repetitions": mailbox[6],
            "immediate_mismatch_cycles": u16(mailbox, 8),
            "first_failure_iteration": mailbox[22],
            "first_failure_byte": mailbox[23],
            "repeat_observation_hash": u16(mailbox, 20),
            "changed_Bank5_bytes": len(changed),
            "changed_offsets_min":
                None if not changed else min(changed),
            "changed_offsets_max":
                None if not changed else max(changed),
        },
        "safety": {
            "published_C2D_byteidentical": True,
            "C2J_CLEAR_before_after": True,
            "phase_owner_NONE_before_after": True,
            "Bank5_changes_confined_to_unpublished_scratch": True,
        },
        "require_peek_map": {
            "trace": {
                "address": TRACE_ADDRESS,
                "hex": trace.hex(),
                "claim": "observational-after-standalone-measurement",
            },
            "header": {
                "address": C2D_HEADER_ADDRESS, "sha256":
                    hashlib.sha256(header).hexdigest(),
                "matches_accepted_G5_C2D": True,
            },
            "place_row": {
                "address": PLACE_ROW_ADDRESS, "sha256":
                    hashlib.sha256(place).hexdigest(),
                "matches_accepted_G5_C2D": True,
            },
        },
        "evidence": {
            name: bind(out / name) for name in (
                "mailbox.bin", "curve.bin", "bank5-before.bin",
                "bank5-after.bin", "phase-owner-before.bin",
                "phase-owner-after.bin", "c2j-before.bin", "c2j-after.bin",
                "require-trace.bin", "c2d-header.bin", "place-row.bin")
        },
        "policy": {
            "acceptance_criterion": False,
            "can_make_chain_red": False,
            "halt_2_review_required": True,
            "post_release_soak_still_required": True,
            "same_Link81_candidate_as_G5": True,
            "supplemental_cold_reset_contacts_after_G5": 1,
            "G5_acceptance_rows_repeated": False,
        },
        "claim_limit": (
            "One cold-reset target session, four raster-timed snapshots and "
            "20 immediate cycles over the unpublished Link-81 Bank-5 append "
            "scratch. All-exact is bounded exoneration only; mismatch is a "
            "prepared Class-C item, never an acceptance failure."),
    }
    if write:
        write_json(HARDWARE, value)
    return value


def selftest() -> dict[str, int]:
    mutations = mutation_selftest()
    BUILD.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
            prefix="selftest-", dir=BUILD) as tmp:
        out = Path(tmp)
        expected_curve = pattern(0x6D)
        expected_crc = crc16(expected_curve)
        mailbox = bytearray(MAILBOX_BYTES)
        mailbox[:6] = b"CVC1\x01\xa5"
        mailbox[6] = REPETITIONS
        for index in range(4):
            mailbox[10 + 2 * index:12 + 2 * index] = (
                expected_crc.to_bytes(2, "little"))
        mailbox[18:20] = expected_crc.to_bytes(2, "little")
        mailbox[22:24] = b"\xff\xff"
        mailbox[24:26] = TARGET_OFFSET.to_bytes(2, "little")
        before = bytearray(BANK5_BYTES)
        after = bytearray(before)
        after[TARGET_OFFSET:TARGET_OFFSET + TARGET_BYTES] = pattern(0x93)
        deployment = load(DEPLOYMENT, "curve deployment")
        accepted_c2d = (
            ROOT / deployment["accepted_G5_C2D_stage"]["path"]).read_bytes()
        files = {
            "mailbox.bin": bytes(mailbox),
            "curve.bin": expected_curve * 4,
            "bank5-before.bin": bytes(before),
            "bank5-after.bin": bytes(after),
            "phase-owner-before.bin": b"\0",
            "phase-owner-after.bin": b"\0",
            "c2j-before.bin": bytes(C2J_BYTES),
            "c2j-after.bin": bytes(C2J_BYTES),
            "require-trace.bin": b"\0\0",
            "c2d-header.bin": accepted_c2d[:48],
            "place-row.bin": accepted_c2d[0xF0:0x110],
        }
        for name, data in files.items():
            (out / name).write_bytes(data)
        clean = evaluate(out, write=False)
        require(clean["classification"].startswith("bounded-exoneration"),
                "clean evaluator selftest did not exonerate")
        mailbox[8:10] = b"\x01\0"
        (out / "mailbox.bin").write_bytes(mailbox)
        red = evaluate(out, write=False)
        require("mismatch" in red["classification"],
                "mismatch evaluator selftest did not classify")
    return {"source_mutations": mutations, "evaluator_cases": 2}


def verify() -> dict[str, Any]:
    value = load(PREPARATION, "curve preparation receipt")
    require(
        value.get("format") == FORMAT
        and value.get("status")
            == "passed-host-prepared-awaiting-device-curve"
        and value.get("policy", {}).get("can_make_acceptance_chain_red")
            is False,
        "curve preparation receipt drift")
    build()
    require(
        bind(DEPLOYMENT) == value["authority"]["deployment"],
        "reproduced curve deployment differs from preparation receipt")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("prepare")
    sub.add_parser("verify")
    sub.add_parser("selftest")
    evaluate_parser = sub.add_parser("evaluate")
    evaluate_parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            value = prepare()
            print(
                "c2-v1.2.4-chipram-curve: PREPARED "
                f"mutations={value['host_execution_witness']['source_mutations_rejected']} "
                "acceptance-criterion=no")
        elif args.action == "verify":
            verify()
            print("c2-v1.2.4-chipram-curve: VERIFY PASS")
        elif args.action == "selftest":
            value = selftest()
            print(
                "c2-v1.2.4-chipram-curve: SELFTEST PASS "
                f"mutations={value['source_mutations']} "
                f"evaluator={value['evaluator_cases']}/2")
        else:
            value = evaluate(args.out.resolve())
            print(
                "c2-v1.2.4-chipram-curve: HARDWARE "
                f"{value['classification']} "
                f"curve-mismatch={value['measurement']['curve_mismatch_points']} "
                f"repeat-mismatch={value['measurement']['immediate_mismatch_cycles']}")
        return 0
    except (
            CurveError, ElfTruthError, OSError, UnicodeError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"c2-v1.2.4-chipram-curve: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
