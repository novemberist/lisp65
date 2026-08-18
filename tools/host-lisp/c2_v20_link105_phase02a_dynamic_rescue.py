#!/usr/bin/env python3
"""Run the owner-authorized raw-first Link-105 dynamic rescue read."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))
import c2_v20_link105_phase02a_capture as C  # noqa: E402
import c2_v20_phase02a_site_capture as SERIAL  # noqa: E402


DEVICE = os.environ.get("DEVICE", "/dev/ttyUSB1")
PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
ROW = ROOT / "config/c2-v20-link105-phase02a-dynamic-rescue-row.json"
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.0-source-oracle-link105-phase02a-capture-first-red.json")
DECODER = C.ELF.parent / "generated-product-sources/c2-stream-decoder.c"
STATIC_PLANE = ROOT / "src/c2_lite_static_plane.h"
OUT = C.OUT / "dynamic-rescue"
RAW_CHECKPOINT = OUT / "raw-checkpoint.json"
CAPTURE = OUT / "capture.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.0-source-oracle-link105-phase02a-dynamic-rescue-receipt.json")
DRIVER = Path(__file__).resolve()

AUTHORIZATION_COMMIT = "6c5d0cb1"
AUTHORIZATION_BYTES = 60364
AUTHORIZATION_SHA256 = (
    "1c1bf837ff61a38d63e9b35a1f3bf53f6d295738b1fe6f0267648963e5d4d7f8")
EXPECTED_SHA = {
    "first_red": "9ff6fc39cc9fda80cc9711d2aece29ad472e66e20acbf09fd6a3123cb29c103b",
    "static_checkpoint":
        "ee3226904a09dec32e33d6ddf913d961082167fc761e68249f729a4ae01dfe47",
    "candidate_elf": "bfdad683c3fd0f4aa158770cab30c357d6bacdafa35a92f97fadcaaafd194b6a",
    "product_readback": "c7e3e5bcd9a252bceb0f38f277901776840c29ff60e6e537c9cd0018f8e18b2e",
    "library_readback": "15e4405929be0686d12c8079509fbd9e12f9314041218ed773fd57b895692060",
    "shelf_truth": "0924fff5a35d2c72e830e90a949ba5f70a9937e17378db1f39a49844f31a795c",
    "c2d_truth": "d576a0ffbff91737f32c29f8cd69f6ee4af1696adeb01741bcab27d8b6043c19",
    "candidate_decoder":
        "fb5f0a9c8cccb33cdea5ec04df817647c95dd5d9b7e5db9586f0a83979e7c6fc",
    "static_plane_contract":
        "3c97cc22b1a53ac781614ae8c9ab8c56998ac44c6ca824fa41f857e8495bdf59",
}
EXPECTED_TUPLE = {
    "PC": "0xe096", "A": "0x02", "X": "0x64", "Y": "0x01",
    "Z": "0x00", "B": "0x00", "SP": "0x01e4",
    "MAPH": "0x8000", "MAPL": "0x0000",
    "suffix": "4C96E0  00     04 .....I.. ...P 15 -  00 - ..c..lhc",
}
RANGES = (
    ("c2-runtime-and-cutpoint", 0x0000C080, 50, "physical-bank0"),
    ("selected-shelf-source-row", 0x081000C0, 32, "physical-28-bit"),
)


class RescueError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RescueError(message)


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
    require(path.is_file() and not path.is_symlink(), f"file absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": digest(raw)}


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(canonical(value))
    temporary.replace(path)


def git_authorization() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{AUTHORIZATION_COMMIT}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION_COMMIT}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    require(len(raw) == AUTHORIZATION_BYTES and digest(raw) == AUTHORIZATION_SHA256,
            "dynamic-rescue authorization identity drift")
    for token in (b"Rescue read authorized", b"no further stop",
                  b"$C080..$C0B1", b"$081000C0..$081000DF",
                  b"raw-first persisted", b"CPU stays stopped",
                  "D2–D5 closed".encode()):
        require(token in raw, f"dynamic-rescue authority token absent: {token!r}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": digest(raw)}


def contract(row: dict[str, Any], source: str) -> None:
    ranges = tuple((item["name"], int(item["address"], 0), item["bytes"],
                    item["view"]) for item in row.get("physical_reads", []))
    require(
        row.get("format") ==
            "lisp65-c2-v20-link105-phase02a-dynamic-rescue-row-v1"
        and row.get("status") == "owner-authorized-6c5d0cb1"
        and row.get("precondition") == {
            "device_state": (
                "the Link-105 phase-02a capture state remains stopped and unchanged"),
            "tuple_and_media_identity_first": True,
            "additional_stops": 0, "resumes": 0, "runs": 0, "resets": 0,
            "D2_D5_executed": False}
        and ranges == RANGES
        and row.get("persistence", "").startswith("Both complete dynamic ranges")
        and "No stop, resume, reset, run" in row.get("claim_limit", ""),
        "dynamic-rescue row contract drift")
    require('command(fd, b"' + 't1' not in source
            and 'command(fd, b"' + 't0' not in source,
            "dynamic rescue contains stop/resume command")
    checkpoint = source.find("write_json(RAW_CHECKPOINT, checkpoint)")
    interpret = source.find("result = interpret(checkpoint)")
    require(0 <= checkpoint < interpret,
            "dynamic ranges are not persisted before interpretation")


def mutations(row: dict[str, Any], source: str) -> list[str]:
    cases: dict[str, Callable[[], None]] = {}
    for name, key, replacement in (
        ("add-stop", "additional_stops", 1),
        ("add-resume", "resumes", 1),
        ("add-run", "runs", 1),
        ("open-D2-D5", "D2_D5_executed", True),
    ):
        def run(key=key, replacement=replacement) -> None:
            trial = deepcopy(row); trial["precondition"][key] = replacement
            contract(trial, source)
        cases[name] = run
    cases["omit-runtime"] = lambda: contract(
        {**row, "physical_reads": row["physical_reads"][1:]}, source)
    cases["omit-source"] = lambda: contract(
        {**row, "physical_reads": row["physical_reads"][:1]}, source)
    cases["widen-source"] = lambda: contract(
        {**row, "physical_reads": [row["physical_reads"][0],
          {**row["physical_reads"][1], "bytes": 33}]}, source)
    cases["interpret-before-persist"] = lambda: contract(
        row, source.replace("write_json(RAW_CHECKPOINT, checkpoint)",
                            "persist_dynamic_later(checkpoint)", 1))
    cases["inject-stop-command"] = lambda: contract(
        row, source + '\ncommand(fd, b"' + 't1")\n')
    rejected: list[str] = []
    for name, run in cases.items():
        try:
            run()
        except RescueError:
            rejected.append(name)
    require(rejected == list(cases), "dynamic-rescue mutation survived")
    return rejected


def preflight() -> dict[str, Any]:
    row = load(ROW); source = DRIVER.read_text(encoding="utf-8")
    contract(row, source)
    bindings = {
        "first_red": bind(FIRST_RED),
        "static_checkpoint": bind(C.CHECKPOINT),
        "candidate_elf": bind(C.ELF),
        "product_readback": bind(C.PRODUCT),
        "library_readback": bind(C.LIBRARY),
        "shelf_truth": bind(C.SHELF),
        "c2d_truth": bind(C.C2D),
        "candidate_decoder": bind(DECODER),
        "static_plane_contract": bind(STATIC_PLANE),
    }
    require({name: item["sha256"] for name, item in bindings.items()}
            == EXPECTED_SHA, "dynamic-rescue input identity drift")
    red = load(FIRST_RED)
    require(red["status"] ==
            "CAPTURE-HARNESS-RED; STATIC-RAW-SALVAGED; MECHANISM-UNDECIDED"
            and red["required_rescue_if_authorized"] == {
                "stops": 0, "resumes": 0,
                "physical_ranges": [
                    {"address": "0x0000c080", "bytes": 50,
                     "purpose": "runtime phase/error/cutpoint"},
                    {"address": "0x081000c0", "bytes": 32,
                     "purpose": "selected immutable Shelf source row"}],
                "rule": "persist both raw ranges before any interpretation"},
            "dynamic-rescue predecessor drift")
    require(not RAW_CHECKPOINT.exists() and not CAPTURE.exists()
            and not RECEIPT.exists(), "dynamic rescue is one-shot")
    return {"authorization": git_authorization(), "row": bind(ROW),
            "driver": bind(DRIVER), **bindings,
            "mutations_rejected": mutations(row, source)}


def u16(raw: bytes, offset: int) -> int:
    return struct.unpack_from("<H", raw, offset)[0]


def u32(raw: bytes, offset: int) -> int:
    return struct.unpack_from("<I", raw, offset)[0]


def runtime_fields(whole: bytes) -> dict[str, int]:
    require(len(whole) == 50, "rescued runtime range length drift")
    raw = whole[4:]
    require(len(raw) == 46, "rescued c2_runtime length drift")
    return {
        "committed_roots": u16(whole, 0),
        "decode_active": u16(whole, 2),
        "shelf_bytes": u32(raw, 0),
        "catalog_crc32": u32(raw, 4),
        "c2d_bytes": u16(raw, 8),
        "generation": u16(raw, 10),
        "image_count": u16(raw, 12),
        "entry_count": u16(raw, 14),
        "resolution_count": u16(raw, 16),
        "images_offset": u16(raw, 18),
        "entries_offset": u16(raw, 20),
        "resolutions_offset": u16(raw, 22),
        "roots_offset": u16(raw, 24),
        "root_count": u16(raw, 26),
        "entry_cursor": u16(raw, 28),
        "resolution_cursor": u16(raw, 30),
        "root_cursor": u16(raw, 32),
        "image_first": u16(raw, 34),
        "entry_first": u16(raw, 36),
        "resolution_first": u16(raw, 38),
        "root_first": u16(raw, 40),
        "phase": raw[42], "finished": raw[43],
        "error": raw[44], "reserved": raw[45],
    }


def interpret(checkpoint: dict[str, Any],
              raw_checkpoint_binding: dict[str, Any] | None = None
              ) -> dict[str, Any]:
    observed = {item["name"]: bytes.fromhex(item["observed_hex"])
                for item in checkpoint["reads"]}
    runtime = runtime_fields(observed["c2-runtime-and-cutpoint"])
    source = observed["selected-shelf-source-row"]
    truth = C.SHELF.read_bytes()[0xC0:0xE0]
    source_crc = C.crc16(source)
    truth_crc = C.crc16(truth)
    predecessor = load(FIRST_RED)
    preserved = predecessor["preserved"]
    expected = int(preserved[
        "actual_expected_crc16_from_preserved_phase_frame"], 0)
    target = bytes.fromhex(preserved["target_at_stop"]["hex"])
    target_crc = C.crc16(target)
    c2d = C.C2D.read_bytes()
    images = u16(c2d, 28)
    rows = [c2d[images + i * 32:images + (i + 1) * 32]
            for i in range(6)]
    code_rows = []
    code_target = 0
    for index, row in enumerate(rows):
        target_at = int.from_bytes(row[18:21], "little")
        length = u16(row, 21)
        code_rows.append({"row": index, "target": target_at,
                          "length": length,
                          "expected_target": code_target,
                          "continuous": target_at == code_target})
        code_target += length
    plane_source = STATIC_PLANE.read_text(encoding="utf-8")
    marker = "#define LISP65_C2_LITE_STATIC_CODE_BYTES "
    pins = [line for line in plane_source.splitlines()
            if line.startswith(marker)]
    require(len(pins) == 1 and pins[0].endswith("UL"),
            "static-plane byte contract shape drift")
    pinned_code_bytes = int(pins[0][len(marker):-2])
    decoder = DECODER.read_text(encoding="utf-8")
    require("c->reserved = 0x2au;" in decoder
            and "c->reserved != 0x2au" in decoder
            and "code_target != LISP65_C2_LITE_STATIC_CODE_BYTES" in decoder,
            "candidate phase-02a/02b cutpoint contract drift")
    require(runtime["decode_active"] == 0xC084,
            "rescued decode-active pointer drift")
    require(runtime["phase"] == 2 and runtime["error"] == 3
            and runtime["reserved"] == 0x2A,
            "rescued state is not phase-02b C2_STREAM_ERR_C2D")
    require(source == truth and source_crc == truth_crc == expected == target_crc,
            "rescued source/target/oracle truth mismatch")
    require(runtime["entry_cursor"] == runtime["entry_count"]
            and runtime["resolution_cursor"] == runtime["resolution_count"],
            "phase-02b cursor-total state drift")
    require(all(row["continuous"] for row in code_rows)
            and code_target == 46043 and pinned_code_bytes == 45939
            and code_target - pinned_code_bytes == 104,
            "candidate phase-02b static extent attribution drift")
    return {
        "format": "lisp65-c2.3-v20-link105-phase02a-dynamic-rescue-v1",
        "recorded_on": "2026-08-13",
        "status": "PHASE02A-EXONERATED; PHASE02B-STATIC-EXTENT-CONTRACT-MISMATCH",
        "authority": checkpoint["authority"],
        "host_attribution": {
            "result_binder": bind(DRIVER),
            "candidate_decoder": bind(DECODER),
            "static_plane_contract": bind(STATIC_PLANE),
            "c2d_delivery_truth": bind(C.C2D),
        },
        "tuple": checkpoint["tuple"],
        "raw_checkpoint": (raw_checkpoint_binding
                           if raw_checkpoint_binding is not None
                           else bind(RAW_CHECKPOINT)),
        "raw_reads": checkpoint["reads"],
        "runtime": runtime,
        "verifier": {
            "site": "inner D705 Shelf cross-read",
            "row": 5,
            "configured_timeout_frames": 64,
            "actual_expected_crc16": f"0x{expected:04x}",
            "physical_source_crc16": f"0x{source_crc:04x}",
            "stopped_target_crc16": f"0x{target_crc:04x}",
            "physical_source_matches_delivery_truth": True,
            "expected_matches_physical_source": True,
            "target_converged_by_stopped_read": True,
            "phase02a_completed_within_each_64_frame_bound": True,
        },
        "classification": {
            "wrong_oracle_sourcing": False,
            "wrong_source_row": False,
            "different_site": True,
            "late_convergence_beyond_64_frames": False,
            "runtime_cutpoint": (
                "phase=2,error=C2_STREAM_ERR_C2D,reserved=0x2a; "
                "phase-02a completed and phase-02b failed"),
            "mechanism": (
                "the six candidate C2D code rows form a continuous 46043-byte "
                "plane, but the linked phase-02b contract pins 45939 bytes; "
                "phase-02b therefore cannot complete even with perfect reads"),
            "claim": "candidate-local phase-02b static-plane extent mismatch",
            "exact_first_phase02b_branch": (
                "not retained; the final extent mismatch is independently "
                "guaranteed and sufficient to reject this candidate"),
        },
        "phase02b_extent": {
            "c2d_rows": code_rows,
            "delivery_code_bytes": code_target,
            "linked_contract_code_bytes": pinned_code_bytes,
            "deficit_bytes": code_target - pinned_code_bytes,
            "entry_totals_equal_at_stop": True,
            "resolution_totals_equal_at_stop": True,
        },
        "discipline": {
            "additional_stops": 0, "resumes": 0, "runs": 0, "resets": 0,
            "dynamic_raw_persisted_before_interpretation": True,
            "CPU_left_stopped": True, "D2_D5_executed": False,
        },
        "unlock": {"D1": False, "D2_D5": False},
        "claim_limit": (
            "This closes only the authorized Link-105 dynamic rescue row. It "
            "does not authorize a static-plane correction, "
            "resume, reset, repeat boot, fix, card, media, D2-D5 or release."),
    }


def capture() -> dict[str, Any]:
    authority = preflight()
    require(Path(DEVICE).is_char_device(), f"serial device absent: {DEVICE}")
    fd = os.open(DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        SERIAL.configure_serial(fd)
        register_raw = SERIAL.command(fd, b"r", 0.05)
        registers = SERIAL.parse_registers(register_raw)
        require(registers == EXPECTED_TUPLE,
                f"dynamic-rescue tuple mismatch; no memory read: {registers}")
        reads: list[dict[str, Any]] = []
        for name, address, count, view in RANGES:
            raw, rows = SERIAL.read_range(fd, address, count)
            reads.append({"name": name, "view": view,
                          "address": f"0x{address:08x}", "bytes": count,
                          "observed_hex": raw.hex(), "monitor_rows": rows})
    finally:
        os.close(fd)
    checkpoint = {
        "format": "lisp65-c2.3-v20-link105-phase02a-dynamic-raw-v1",
        "captured_on": "2026-08-13", "authority": authority,
        "tuple": registers, "register_raw_hex": register_raw.hex(),
        "reads": reads,
        "discipline": {
            "additional_stops": 0, "resumes": 0, "runs": 0, "resets": 0,
            "dynamic_raw_persisted_before_interpretation": True,
            "CPU_left_stopped": True, "D2_D5_executed": False,
        },
    }
    write_json(RAW_CHECKPOINT, checkpoint)
    result = interpret(checkpoint)
    write_json(CAPTURE, result)
    write_json(RECEIPT, result)
    return result


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in {
        "selftest", "preflight", "capture", "record", "check"},
        "usage: c2_v20_link105_phase02a_dynamic_rescue.py "
        "selftest|preflight|capture|record|check")
    row = load(ROW); source = DRIVER.read_text(encoding="utf-8")
    if sys.argv[1] == "selftest":
        contract(row, source)
        print(f"Link-105 dynamic rescue: SELFTEST PASS "
              f"mutations={len(mutations(row, source))}")
    elif sys.argv[1] == "preflight":
        value = preflight()
        print(json.dumps({"status": "PREFLIGHT PASS", "device": DEVICE,
                          "mutations": value["mutations_rejected"]},
                         indent=2, sort_keys=True))
    elif sys.argv[1] == "capture":
        value = capture()
        print(json.dumps({"status": value["status"],
                          "runtime": value["runtime"],
                          "verifier": value["verifier"],
                          "classification": value["classification"]},
                         indent=2, sort_keys=True))
    elif sys.argv[1] == "record":
        raw = load(RAW_CHECKPOINT)
        value = interpret(raw)
        write_json(CAPTURE, value)
        write_json(RECEIPT, value)
        print("Link-105 dynamic rescue: RECORD PASS phase02a=exonerated "
              "phase02b=extent-mismatch")
    else:
        receipt = load(RECEIPT)
        persisted = {
            "authority": receipt["authority"],
            "tuple": receipt["tuple"],
            "reads": receipt["raw_reads"],
        }
        require(receipt == interpret(persisted, receipt["raw_checkpoint"]),
                "dynamic rescue receipt replay drift")
        print("Link-105 dynamic rescue: CHECK PASS phase02b=extent-mismatch")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RescueError, C.CaptureError, SERIAL.CaptureError, OSError,
            ValueError, KeyError, json.JSONDecodeError, struct.error,
            subprocess.CalledProcessError) as error:
        print(f"LINK-105 DYNAMIC RESCUE: {error}", file=sys.stderr)
        raise SystemExit(1)
