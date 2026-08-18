#!/usr/bin/env python3
"""Run and bind the authorized read-only Link-107 media rescue row."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_defstruct_link71_slot39_failure_hold as SERIAL  # noqa: E402
import c2_v16_corrected_view_contact as VIEW  # noqa: E402
import c2_v20_loading_libraries_progress_map_contact as MONITOR  # noqa: E402
import c2_v21_loading_libraries_progress_contact as CONTACT  # noqa: E402
import c2_v21_loading_libraries_progress_rebind as RING  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
ROW = ROOT / "config/c2-v21-loading-libraries-progress-media-rescue.json"
FIRST_RED = ARCH / (
    "c2.3-v2.1-loading-libraries-progress-media-first-red-receipt.json")
OUT = CONTACT.OUT / "media-rescue"
RAW = OUT / "raw-checkpoint.json"
RESULT = OUT / "result.json"
RECEIPT = ARCH / (
    "c2.3-v2.1-loading-libraries-progress-media-rescue-receipt.json")
DEVICE = os.environ.get("DEVICE", "/dev/ttyUSB1")
FORMAT = "lisp65-c2.3-v2.1-loading-progress-media-rescue-v1"
AUTHORIZATION_COMMIT = "0c99d88aa8e5ac9085074e8ff95924476b6edebf"
AUTHORIZATION_BYTES = 60450
AUTHORIZATION_SHA256 = (
    "a5642b2263c4c7acb5c60d6d71a154703d3e1fa5de6b3446893e8c89db58acf5")
EXPECTED_TUPLE = {
    "PC": "0x2a72", "A": "0x41", "X": "0x1f", "Y": "0x00",
    "Z": "0x00", "B": "0x00", "SP": "0x01eb",
    "MAPH": "0x8300", "MAPL": "0xe000",
}
EXPECTED_SHA256 = {
    "first_red": "34db16d9785c44a21fe5503d5fa12d655ff74f93752cf89c424167ee6f246815",
    "row": "0ffae09baca73b6a3e8b3f5953a408230df84f3cb4b554e1966049aeb731f1a5",
    "diagnostic_prg": "eef3494fa72de8632bbc694835026c1aca656c853aae2baa403b2477ecc9550a",
    "diagnostic_window": "57bb612a0e6dd93a2024af095c992ec01113c6c9b1d05cf8c7dd56e419e4f490",
    "descriptor": "8fb78ec00471580948a59e1696a28faf9fd2646be65c46ec68da3a7870a3042c",
    "product_readback": "7524d3e116f47c96faf75329033613bf19e2c66e91c258361a3de77d580a58f9",
    "library_readback": "15e4405929be0686d12c8079509fbd9e12f9314041218ed773fd57b895692060",
    "prior_capture": "655738093661611f3c4a35a087ea9c210f5bbcbfb2e4ab57b189c99ab2b8dc8b",
}
RANGES = (
    ("stager-stack-tail", 0x000001EC, 20),
    ("loaded-boot-descriptor", 0x000037E4, 432),
    ("role8-diagnostic-head", 0x087FE053, 16),
    ("role8-diagnostic-middle", 0x087FFEF5, 16),
    ("role8-diagnostic-tail", 0x087FFF57, 16),
    ("bank4-diagnostic-ring", 0x00049583, 66),
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


def write_raw(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(raw); handle.flush(); os.fsync(handle.fileno())
    temporary.replace(path)


def write_json(path: Path, value: dict[str, Any]) -> None:
    write_raw(path, canonical(value))


def git_authorization() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{AUTHORIZATION_COMMIT}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    require(len(raw) == AUTHORIZATION_BYTES and digest(raw) ==
            AUTHORIZATION_SHA256, "rescue authorization identity drift")
    for token in (b"Rescue read authorized", b"stack return",
                  b"loaded descriptor", b"role-8", b"stage probes",
                  b"Bank-4 PRG probe", b"no new stop", b"no resume"):
        require(token in raw, f"rescue authority token absent: {token!r}")
    return {"authority": "git-blob", "commit": AUTHORIZATION_COMMIT,
            "path": name, "bytes": len(raw), "sha256": digest(raw)}


def input_paths() -> dict[str, Path]:
    return {
        "first_red": FIRST_RED, "row": ROW,
        "diagnostic_prg": RING.DIAG_PRG,
        "diagnostic_window": RING.DIAG_WINDOW,
        "descriptor": RING.DIAG_DESCRIPTOR,
        "product_readback": CONTACT.OUT / "product-readback.d81",
        "library_readback": CONTACT.OUT / "library-readback.d81",
        "prior_capture": CONTACT.CAPTURE,
    }


def preflight() -> dict[str, Any]:
    authority = git_authorization()
    paths = input_paths()
    actual = {name: digest(path.read_bytes()) for name, path in paths.items()}
    require(actual == EXPECTED_SHA256, "rescue SHA-first input drift")
    row = load(ROW)
    ranges = tuple((item["name"], int(item["address"], 0), item["bytes"])
                   for item in row.get("reads", []))
    source = Path(__file__).read_text(encoding="utf-8")
    require(
        row.get("format") ==
            "lisp65-c2-v21-loading-progress-media-rescue-row-v1"
        and row.get("status") == "owner-authorized-0c99d88a"
        and row.get("precondition") == {
            "additional_stops": 0,
            "device_state": "unchanged stopped Link-107 progress-media First Red",
            "resumes": 0, "tuple_and_media_SHA_first": True}
        and ranges == RANGES
        and 'VIEW.command(fd, b"' + 't1' not in source
        and 'VIEW.command(fd, b"' + 't0' not in source,
        "rescue row or no-stop/no-resume structure drift")
    return {"authorization": authority,
            "inputs": {name: bind(path) for name, path in paths.items()},
            "row": bind(ROW)}


def expected_bytes() -> dict[str, bytes]:
    descriptor = RING.DIAG_DESCRIPTOR.read_bytes()
    window = RING.DIAG_WINDOW.read_bytes()
    prg = RING.DIAG_PRG.read_bytes()
    state = RING.DIAG_STATE.read_bytes()
    require(prg[0:2] == b"\x01\x20" and prg[0x9583:0x9583 + 66] == state,
            "Bank-4 diagnostic-stage translation drift")
    return {
        "loaded-boot-descriptor": descriptor,
        "role8-diagnostic-head": window[0x53:0x63],
        "role8-diagnostic-middle": window[0x1EF5:0x1F05],
        "role8-diagnostic-tail": window[0x1F57:0x1F67],
        "bank4-diagnostic-ring": state,
    }


def capture() -> dict[str, Any]:
    require(not RAW.exists(), "rescue raw checkpoint already exists")
    authority = preflight()
    require(Path(DEVICE).is_char_device(), f"serial device absent: {DEVICE}")
    OUT.mkdir(parents=True, exist_ok=True)
    raw_log = OUT / "monitor-raw.ndjson"
    write_raw(raw_log, b"")
    fd = os.open(DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        SERIAL.configure_serial(fd)
        register_raw = VIEW.command(fd, b"r", 0.05)
        MONITOR.append_raw(raw_log, "tuple-reconfirmation", "r", register_raw)
        registers = VIEW.parse_registers(register_raw)
        stable = {name: registers[name] for name in EXPECTED_TUPLE}
        require(stable == EXPECTED_TUPLE,
                f"preserved tuple mismatch; no memory read: {stable}")
        rows = []
        for name, address, count in RANGES:
            observed = MONITOR.read_range(fd, address, count, raw_log)
            output = OUT / f"{name}.bin"
            write_raw(output, observed)
            rows.append({"name": name, "address": f"0x{address:08x}",
                         "bytes": count, "raw": bind(output)})
    finally:
        os.close(fd)
    value = {"format": FORMAT + "-raw", "captured_on": "2026-08-15",
             "authority": authority, "tuple": registers, "reads": rows,
             "raw_log": bind(raw_log),
             "discipline": {"additional_stops": 0, "resumes": 0,
                 "tuple_and_media_SHA_first": True,
                 "raw_persisted_before_interpretation": True,
                 "CPU_left_stopped": True, "D1_D5_open": False},
             "claim_limit": "Raw-first rescue only; no interpretation here."}
    write_json(RAW, value)
    return value


def identity(observed: bytes, diagnostic: bytes, control: bytes) -> str:
    return "diagnostic" if observed == diagnostic else (
        "control" if observed == control else "other")


def interpret(raw: dict[str, Any]) -> dict[str, Any]:
    by_name = {row["name"]: (ROOT / row["raw"]["path"]).read_bytes()
               for row in raw["reads"]}
    expected = expected_bytes()
    control_window = (
        RING.OUT / "readback-control/window-bin").read_bytes()
    control_prg = (RING.OUT / "readback-control/lisp65-prg").read_bytes()
    control_state = control_prg[0x9583:0x9583 + 66]
    stack = by_name["stager-stack-tail"]
    caller_words = {
        "descriptor-load-direct-error": bytes.fromhex("6422"),
        "generic-validation-stage-or-handoff-error": bytes.fromhex("7327"),
    }
    callers = [name for name, word in caller_words.items() if word in stack]
    descriptor_exact = by_name["loaded-boot-descriptor"] == expected[
        "loaded-boot-descriptor"]
    window_names = ("role8-diagnostic-head", "role8-diagnostic-middle",
                    "role8-diagnostic-tail")
    window_identity = []
    offsets = (0x53, 0x1EF5, 0x1F57)
    for name, offset in zip(window_names, offsets):
        window_identity.append(identity(
            by_name[name], expected[name], control_window[offset:offset + 16]))
    bank4_identity = identity(by_name["bank4-diagnostic-ring"],
                              expected["bank4-diagnostic-ring"], control_state)
    if not descriptor_exact:
        outcome = "PRE-STAGE-DESCRIPTOR-REJECTION"
    elif window_identity != ["diagnostic"] * 3:
        outcome = "STAGE-ROLE-REJECTION-BEFORE-OR-AT-ROLE8"
    elif bank4_identity != "diagnostic":
        outcome = "PRODUCT-ROLE-SCAN-OR-STAGE-REJECTION"
    else:
        outcome = "CHAIN-COPY-OR-HANDOFF-REJECTION"
    return {"caller_candidates": callers,
            "descriptor": "diagnostic" if descriptor_exact else "other",
            "role8_samples": window_identity,
            "bank4_PRG_ring": bank4_identity, "outcome": outcome}


def derive() -> dict[str, Any]:
    raw = load(RAW)
    result = interpret(raw)
    value = {"format": FORMAT, "recorded_on": "2026-08-15",
             "status": result["outcome"],
             "authority": {"raw_checkpoint": bind(RAW),
                 "authorization": raw["authority"]["authorization"],
                 "first_red": bind(FIRST_RED)},
             "tuple": raw["tuple"], "result": result,
             "discipline": raw["discipline"],
             "claim_limit": (
                 "Names the cold-stager rejection stage only. CPU transport "
                 "rate remains unmeasured; no product finding; CPU stopped.")}
    value["mutations"] = mutation_gate(value)
    audit(value)
    return value


def audit(value: dict[str, Any]) -> None:
    require(
        value.get("status") in {
            "PRE-STAGE-DESCRIPTOR-REJECTION",
            "STAGE-ROLE-REJECTION-BEFORE-OR-AT-ROLE8",
            "PRODUCT-ROLE-SCAN-OR-STAGE-REJECTION",
            "CHAIN-COPY-OR-HANDOFF-REJECTION"}
        and value.get("result", {}).get("outcome") == value.get("status")
        and value.get("discipline") == {"additional_stops": 0,
            "resumes": 0, "tuple_and_media_SHA_first": True,
            "raw_persisted_before_interpretation": True,
            "CPU_left_stopped": True, "D1_D5_open": False},
        "rescue result claim boundary drift")


def mutation_gate(base: dict[str, Any]) -> dict[str, Any]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "add-stop": lambda x: x["discipline"].update(additional_stops=1),
        "add-resume": lambda x: x["discipline"].update(resumes=1),
        "skip-SHA-first": lambda x: x["discipline"].update(
            tuple_and_media_SHA_first=False),
        "interpret-before-persist": lambda x: x["discipline"].update(
            raw_persisted_before_interpretation=False),
        "open-D1-D5": lambda x: x["discipline"].update(D1_D5_open=True),
        "invent-outcome": lambda x: x.update(status="CPU-RATE-MEASURED"),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(base); mutate(trial)
        try:
            audit(trial)
        except RescueError:
            rejected.append(name)
    require(len(rejected) == len(cases), "rescue mutation survived")
    return {"count": len(rejected), "rejected": sorted(rejected)}


def record() -> dict[str, Any]:
    require(not RECEIPT.exists(), "rescue receipt already exists")
    value = derive(); write_json(RESULT, value); write_json(RECEIPT, value)
    return value


def check() -> dict[str, Any]:
    value = load(RECEIPT); audit(value)
    require(value == derive() and value == load(RESULT),
            "rescue receipt/result reconstruction drift")
    return value


def selftest() -> dict[str, Any]:
    authority = preflight(); expected = expected_bytes()
    require(len(expected["loaded-boot-descriptor"]) == 432
            and len(expected["bank4-diagnostic-ring"]) == 66,
            "rescue expected-byte geometry drift")
    return {"status": "SELFTEST PASS", "authority": authority,
            "reads": len(RANGES)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("preflight", "selftest", "capture",
                                           "record", "check"))
    args = parser.parse_args()
    value = preflight() if args.action == "preflight" else (
        selftest() if args.action == "selftest" else
        capture() if args.action == "capture" else
        record() if args.action == "record" else check())
    print(json.dumps(value, indent=2, sort_keys=True)); return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RescueError, OSError, KeyError, ValueError,
            subprocess.CalledProcessError) as error:
        print(f"LINK 107 MEDIA RESCUE: {error}", file=sys.stderr)
        raise SystemExit(1)
