#!/usr/bin/env python3
"""Capture and classify the owner-authorized Link-105 phase-02a row."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))
import c2_v16_corrected_view_contact as VIEW  # noqa: E402
import c2_v20_phase02a_site_capture as OLD  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


DEVICE = os.environ.get("DEVICE", "/dev/ttyUSB1")
PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
ROW = ROOT / "config/c2-v20-link105-phase02a-capture-row.json"
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.0-source-oracle-d1-first-red-receipt.json")
MEDIA = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.0-source-oracle-media-closure-receipt.json")
ELF = ROOT / (
    "build/c2.3/v2.0-source-oracle-replacement3-card/final/"
    "lisp65-c2-substitution-linked.prg.elf")
PRODUCT = ROOT / "build/c2.3/v2.0-source-oracle-d1/product-readback.d81"
LIBRARY = ROOT / "build/c2.3/v2.0-source-oracle-d1/library-readback.d81"
SCREEN = ROOT / "build/c2.3/v2.0-source-oracle-d1/product-boot.png"
ORACLE_CONTRACT = ROOT / "config/c2-v20-source-authoritative-oracle-contract.json"
SHELF = ROOT / (
    "build/c2.3/v2.0-source-oracle-replacement3-card/static-plane/"
    "narrow-static/product/product-shelf-v4-direct.bin")
C2D = ROOT / (
    "build/c2.3/v2.0-source-oracle-replacement3-card/static-plane/"
    "narrow-static/v6-semantics/initial.c2d-v6.bin")
OUT = ROOT / "build/c2.3/v2.0-source-oracle-d1/phase02a-link105-row"
CHECKPOINT = OUT / "static-checkpoint.json"
CAPTURE = OUT / "capture.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.0-source-oracle-link105-phase02a-device-receipt.json")
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"

AUTHORIZATION_COMMIT = "9d8ea782"
AUTHORIZATION_BYTES = 59345
AUTHORIZATION_SHA256 = "8ec9eca3dba86200522fef21ca030c024a1f88b0c67f198f41c13ebbdc791132"
EXPECTED_SHA = {
    "first_red": "b1df6c678bd1c423539fb0f67e02102fba8ea1bc6d38e067b302b631608a61a9",
    "media": "9c2d7df63e94850462b7084e2ccb3066f08c3bae81b75520199e1a435d273992",
    "candidate_elf": "bfdad683c3fd0f4aa158770cab30c357d6bacdafa35a92f97fadcaaafd194b6a",
    "product_readback": "c7e3e5bcd9a252bceb0f38f277901776840c29ff60e6e537c9cd0018f8e18b2e",
    "library_readback": "15e4405929be0686d12c8079509fbd9e12f9314041218ed773fd57b895692060",
    "screen": "27225182cc1222b075900be7dbb69099ddb20d89e0c13d839bbc683889d09a7a",
    "oracle_contract": "8d5aeb1976e646d561246cb93c92fa8b08a0303083f79efb6e54c24f64270dc8",
    "shelf": "0924fff5a35d2c72e830e90a949ba5f70a9937e17378db1f39a49844f31a795c",
    "c2d": "d576a0ffbff91737f32c29f8cd69f6ee4af1696adeb01741bcab27d8b6043c19",
}


class CaptureError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CaptureError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"file absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": digest(raw)}


def git_authorization() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{AUTHORIZATION_COMMIT}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION_COMMIT}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    require(len(raw) == AUTHORIZATION_BYTES and digest(raw) == AUTHORIZATION_SHA256,
            "Link-105 row authorization identity drift")
    for token in (b"Link-105 identity", b"raw-first driver", b"one stop",
                  b"no resume", b"actual", b"expected value",
                  b"timeout counters"):
        require(token in raw, f"Link-105 authorization token absent: {token!r}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": digest(raw)}


def contract(row: dict[str, Any], source: str) -> None:
    names = {item["name"]: item for item in row.get("static_reads", [])}
    require(
        row.get("format") == "lisp65-c2-v20-link105-phase02a-capture-row-v1"
        and row.get("status") == "owner-authorized-9d8ea782"
        and row.get("precondition") == {
            "device_state": (
                "the fresh Link-105 D1 E25 state remains running in the "
                "fail-closed loop"),
            "stop_count": 1, "resume_count": 0, "D2_D5_executed": False}
        and names.get("linked-verifier-oracle-tables", {}).get("bytes") == 24
        and names.get("linked-verifier-oracle-tables", {}).get("view")
            == "cpu-resolved-0x0777xxxx"
        and names.get("phase02a-preserved-frame-domain", {}).get("bytes") == 256
        and names.get("frame-counter", {}).get("bytes") == 2
        and row.get("oracle", {}).get("record_bytes") == 32
        and row.get("oracle", {}).get("timeout_frames") == 64
        and row.get("oracle", {}).get("shelf_crc16") ==
            ["0xce26", "0x46f5", "0xfccb", "0xbc88", "0xf871", "0xe3f7"]
        and row.get("oracle", {}).get("c2d_crc16") ==
            ["0xe27e", "0x8cc6", "0x74d8", "0x277a", "0x9866", "0xe9dc"],
        "Link-105 capture-row contract drift")
    stop_token = 'OLD.' + 'command(fd, b"t1"'
    resume_token = 'OLD.' + 'command(fd, b"t0"'
    require(source.count(stop_token) == 1 and resume_token not in source,
            "Link-105 capture stop/resume choreography drift")
    checkpoint = source.find("CHECKPOINT.write_text")
    select = source.find("select_site(static)")
    require(0 <= checkpoint < select, "raw checkpoint does not precede interpretation")


def mutations(row: dict[str, Any], source: str) -> list[str]:
    cases: dict[str, Callable[[], None]] = {}
    for name, path, replacement in (
        ("drop-stop", ("precondition", "stop_count"), 0),
        ("add-resume", ("precondition", "resume_count"), 1),
        ("open-D2-D5", ("precondition", "D2_D5_executed"), True),
        ("short-record", ("oracle", "record_bytes"), 16),
        ("short-timeout", ("oracle", "timeout_frames"), 63),
        ("wrong-shelf-oracle", ("oracle", "shelf_crc16"), ["0x0000"] * 6),
    ):
        def run(path=path, replacement=replacement) -> None:
            trial = deepcopy(row); trial[path[0]][path[1]] = replacement
            contract(trial, source)
        cases[name] = run
    cases["omit-target-oracle"] = lambda: contract(
        {**row, "static_reads": [item for item in row["static_reads"]
          if item["name"] != "linked-verifier-oracle-tables"]}, source)
    cases["interpret-before-raw"] = lambda: contract(
        row, source.replace("CHECKPOINT.write_text", "persist_static", 1))
    cases["resume-command"] = lambda: contract(
        row, source + '\nOLD.' + 'command(fd, b"t0")\n')
    rejected: list[str] = []
    for name, run in cases.items():
        try:
            run()
        except CaptureError:
            rejected.append(name)
    require(rejected == list(cases), "Link-105 capture mutation survived")
    return rejected


def preflight() -> dict[str, Any]:
    row = load(ROW); source = DRIVER.read_text(encoding="utf-8")
    contract(row, source)
    bindings = {
        "first_red": bind(FIRST_RED), "media": bind(MEDIA),
        "candidate_elf": bind(ELF), "product_readback": bind(PRODUCT),
        "library_readback": bind(LIBRARY), "screen": bind(SCREEN),
        "oracle_contract": bind(ORACLE_CONTRACT), "shelf": bind(SHELF),
        "c2d": bind(C2D),
    }
    require({name: item["sha256"] for name, item in bindings.items()} == EXPECTED_SHA,
            "Link-105 capture input identity drift")
    require(load(FIRST_RED)["unlock"] == {"D1": False, "D2_D5": False},
            "Link-105 first-red closure drift")
    require(not CHECKPOINT.exists() and not CAPTURE.exists() and not RECEIPT.exists(),
            "Link-105 phase-02a row is one-shot")
    return {"authorization": git_authorization(), "row": bind(ROW),
            "driver": bind(DRIVER), **bindings,
            "mutations_rejected": mutations(row, source)}


def read_cpu_range(fd: int, logical: int, count: int) -> tuple[bytes, list[dict[str, Any]]]:
    result = bytearray(); rows: list[dict[str, Any]] = []
    while len(result) < count:
        take = min(16, count - len(result))
        raw, evidence = VIEW.read_cpu(fd, logical + len(result), take)
        result.extend(raw); rows.append(evidence)
    return bytes(result), rows


def crc16(raw: bytes) -> int:
    value = 0xFFFF
    for byte in raw:
        value ^= byte << 8
        for _ in range(8):
            value = ((value << 1) ^ 0x1021) & 0xFFFF \
                if value & 0x8000 else (value << 1) & 0xFFFF
    return value


def select_site(static: dict[str, bytes]) -> dict[str, Any]:
    pseudo = static["compiler-static-stack-and-pseudo-registers"]
    initial = pseudo[0] | pseudo[1] << 8
    phase_frame = (initial - 48 - 1 - 66 - 110) & 0xFFFF
    geometry = {"initial_static_stack": initial, "phase02a_frame": phase_frame,
                "outer_shelf_target": phase_frame + 0x4E,
                "c2d_target": phase_frame + 0x0E,
                "inner_shelf_target": phase_frame + 0x2E}
    d700 = OLD.d700_job(static["D700-primary-descriptor"])
    d705 = OLD.edma_job(static["D705-primary-descriptor"])
    if d705["target"] == geometry["inner_shelf_target"]:
        family, site, descriptor = "D705", "inner-Shelf-cross-read", d705
    elif d700["target"] == geometry["c2d_target"]:
        family, site, descriptor = "D700", "C2D-image-row", d700
    elif d705["target"] == geometry["outer_shelf_target"]:
        family, site, descriptor = "D705", "outer-Shelf-record", d705
    else:
        raise CaptureError("retained descriptors name no Link-105 phase-02a site")
    if family == "D705":
        require(descriptor["source"] >= 0x08100020
                and (descriptor["source"] - 0x08100020) % 32 == 0,
                "D705 source is outside delivery-bound Shelf records")
        row = (descriptor["source"] - 0x08100020) // 32
        table = "shelf"
    else:
        require(descriptor["source"] >= 0x00050000,
                "D700 source is outside the C2D plane")
        images_offset = struct.unpack_from("<H", C2D.read_bytes(), 28)[0]
        require(descriptor["source"] >= 0x00050000 + images_offset
                and (descriptor["source"] - 0x00050000 - images_offset) % 32 == 0,
                "D700 source is outside delivery-bound C2D records")
        row = (descriptor["source"] - 0x00050000 - images_offset) // 32
        table = "c2d"
    require(0 <= row < 6 and descriptor["length"] == 32
            and descriptor["target"] < 0x10000,
            "selected phase-02a descriptor geometry drift")
    return {"family": family, "site": site, "row": row, "table": table,
            "source": descriptor["source"], "target": descriptor["target"],
            "descriptor": descriptor, "geometry": geometry}


def capture() -> dict[str, Any]:
    authority = preflight()
    require(Path(DEVICE).is_char_device(), f"serial device absent: {DEVICE}")
    row = load(ROW)
    fd = os.open(DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        OLD.configure_serial(fd)
        stop_raw = OLD.command(fd, b"t1", 0.08)
        registers_raw = OLD.command(fd, b"r", 0.05)
        registers = OLD.parse_registers(registers_raw)
        require(registers["PC"] in {"0xe096", "0xe097"}
                and registers["MAPH"] == "0x8000"
                and registers["MAPL"] == "0x0000",
                f"Link-105 fail-loop tuple mismatch; no memory read: {registers}")
        fail_bytes, fail_rows = read_cpu_range(fd, 0xE096, 3)
        require(fail_bytes == bytes.fromhex("4c96e0"),
                "Link-105 fail-loop CPU identity mismatch")
        reads: list[dict[str, Any]] = []
        static: dict[str, bytes] = {}
        for item in row["static_reads"]:
            address = int(item["address"], 0); count = item["bytes"]
            if item["view"] == "physical-bank0":
                observed, commands = OLD.read_range(fd, address, count)
            else:
                observed, commands = read_cpu_range(fd, address, count)
            static[item["name"]] = observed
            reads.append({"name": item["name"], "view": item["view"],
                          "address": f"0x{address:08x}", "bytes": count,
                          "observed_hex": observed.hex(),
                          "monitor_rows": commands})
        checkpoint = {
            "format": "lisp65-c2.3-v20-link105-phase02a-static-v1",
            "authority": authority, "tuple": registers,
            "stop_raw_hex": stop_raw.hex(),
            "register_raw_hex": registers_raw.hex(),
            "fail_loop": {"bytes": fail_bytes.hex(), "rows": fail_rows},
            "reads": reads,
            "discipline": {"stops": 1, "resumes": 0, "runs": 0,
                           "resets": 0, "raw_before_interpretation": True,
                           "CPU_left_stopped": True, "D2_D5_executed": False},
        }
        OUT.mkdir(parents=True, exist_ok=True)
        CHECKPOINT.write_text(json.dumps(checkpoint, indent=2, sort_keys=True) + "\n",
                              encoding="utf-8")
        selected = select_site(static)
        target, target_rows = OLD.read_range(fd, selected["target"], 32)
        source, source_rows = OLD.read_range(fd, selected["source"], 32)
    finally:
        os.close(fd)

    tables = static["linked-verifier-oracle-tables"]
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    linked = truth.section_bytes(".lisp65_rt_c2d_02a")[:24]
    require(tables == linked, "target verifier tables differ from linked ELF")
    shelf_values = list(struct.unpack("<6H", tables[:12]))
    c2d_values = list(struct.unpack("<6H", tables[12:]))
    expected = (shelf_values if selected["table"] == "shelf" else c2d_values)[selected["row"]]
    source_crc = crc16(source); target_crc = crc16(target)
    if expected != source_crc:
        classification = "WRONG-TARGET-EXPECTED-VALUE"
    elif target_crc != expected:
        classification = "CORRECT-EXPECTATION; CONTENT-NOT-CONVERGED-AFTER-STOP"
    else:
        classification = "CORRECT-EXPECTATION; CONTENT-CONVERGED-AFTER-TIMEOUT"
    timeout_code = static["linked-timeout-compare"]
    require(bytes.fromhex("e040") in timeout_code,
            "linked 64-frame timeout compare absent from target CPU view")
    result = {
        "format": "lisp65-c2.3-v20-link105-phase02a-device-v1",
        "captured_on": "2026-08-13", "status": classification,
        "authority": authority, "tuple": registers,
        "discipline": {"stops": 1, "resumes": 0, "runs": 0,
                       "resets": 0, "raw_before_interpretation": True,
                       "CPU_left_stopped": True, "D2_D5_executed": False},
        "static_checkpoint": bind(CHECKPOINT), "site": selected,
        "verifier": {
            "target_table_bytes": tables.hex(),
            "target_tables_match_linked_ELF": True,
            "actual_expected_crc16": f"0x{expected:04x}",
            "delivery_source_crc16": f"0x{source_crc:04x}",
            "observed_target_crc16": f"0x{target_crc:04x}",
            "expected_matches_delivery_truth": expected == source_crc,
            "observed_content_matches_expected_at_stopped_read": target_crc == expected,
        },
        "content": {
            "source_address": f"0x{selected['source']:08x}",
            "source_hex": source.hex(), "source_rows": source_rows,
            "target_address": f"0x{selected['target']:08x}",
            "target_hex": target.hex(), "target_rows": target_rows,
        },
        "timeout": {
            "configured_frames": 64,
            "linked_compare_present": True,
            "stopped_frame_counter_hex": static["frame-counter"].hex(),
            "exact_start_frame_survives_return": False,
            "interpretation": (
                "the verifier returned only after its linked 64-frame bound; "
                "the helper restores its start registers, so exact elapsed "
                "frames do not survive the fail-closed return"),
        },
        "decision": {
            "classification": classification,
            "wrong_oracle_sourcing": expected != source_crc,
            "late_or_nonconverging_transport": expected == source_crc,
            "different_site": selected["site"],
        },
        "claim_limit": (
            "This closes only the owner-authorized Link-105 phase-02a row. "
            "It authorizes no resume, reset, repeat boot, D2-D5, fix, card, "
            "media or release action."),
    }
    CAPTURE.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    RECEIPT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    return result


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in {"selftest", "preflight", "capture"},
            "usage: c2_v20_link105_phase02a_capture.py selftest|preflight|capture")
    if sys.argv[1] == "selftest":
        row = load(ROW); source = DRIVER.read_text(encoding="utf-8")
        contract(row, source)
        print(f"Link-105 phase-02a selftest: PASS mutations={len(mutations(row, source))}")
    elif sys.argv[1] == "preflight":
        value = preflight()
        print(json.dumps({"status": "PREFLIGHT PASS", "device": DEVICE,
                          "mutations": value["mutations_rejected"]},
                         indent=2, sort_keys=True))
    else:
        value = capture()
        print(json.dumps({"status": value["status"], "site": value["site"],
                          "verifier": value["verifier"],
                          "timeout": value["timeout"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CaptureError, OLD.CaptureError, VIEW.CorrectedViewError, OSError,
            ValueError, KeyError, json.JSONDecodeError,
            subprocess.CalledProcessError) as error:
        print(f"LINK-105 PHASE02A CAPTURE: {error}", file=sys.stderr)
        raise SystemExit(1)
