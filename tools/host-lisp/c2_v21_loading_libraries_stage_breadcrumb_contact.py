#!/usr/bin/env python3
"""Run and bind the autonomous Link-107 cold-stager breadcrumb contact."""

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
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_defstruct_link71_slot39_failure_hold as SERIAL  # noqa: E402
import c2_media_builder_closure_enumeration as ENUM  # noqa: E402
import c2_v16_corrected_view_contact as VIEW  # noqa: E402
import c2_v20_loading_libraries_progress_map_contact as RAW  # noqa: E402
import c2_v21_loading_libraries_progress_media_recontact as RING  # noqa: E402
import c2_v21_loading_libraries_progress_rebind as PRODUCT  # noqa: E402
import c2_v21_loading_libraries_stage_breadcrumb_media as BREAD  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
SESSION = ROOT / "config/c2-v21-loading-libraries-stage-breadcrumb-contact.json"
RUNNER = ROOT / "scripts/c2-v21-loading-libraries-stage-breadcrumb-contact.sh"
OUT = ROOT / "build/c2.3/v2.1-loading-libraries-stage-breadcrumb-contact/contact"
CAPTURE = OUT / "raw-capture.json"
RESULT = OUT / "result.json"
RECEIPT = ARCH / (
    "c2.3-v2.1-loading-libraries-stage-breadcrumb-contact-receipt.json")
AUTHORIZATION = "e90e6291"
FORMAT = "lisp65-c2.3-v2.1-loading-libraries-stage-breadcrumb-contact-v1"
DEVICE = os.environ.get("DEVICE", "/dev/ttyUSB1")
TRACE_ADDRESS = 0x3B9C
TRACE_BYTES = 32

REASONS = {
    0x01: "media-identity", 0x02: "descriptor-load",
    0x03: "descriptor-validate", 0x04: "role-domain",
    0x05: "role-stage-flag", 0x10: "length-range",
    0x11: "stage-domain", 0x12: "find-file",
    0x13: "f011-read", 0x14: "chain-terminator",
    0x15: "length-overflow", 0x16: "convergence-timeout",
    0x17: "chain-pointer", 0x18: "chain-fuel",
    0x19: "final-length", 0x1A: "final-crc",
    0x20: "nonstage-scan", 0x21: "product-record",
    0x22: "product-scan", 0x23: "chain-return",
}


class ContactError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ContactError(message)


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


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name); handle.write(canonical(value))
    temporary.replace(path)


def authority() -> dict[str, Any]:
    full = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{full}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().split()).lower()
    for token in ("breadcrumb contact authorized", "one breadcrumb contact",
                  "fallback named now", "product itself"):
        require(token in text, f"breadcrumb authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def session_contract() -> dict[str, Any]:
    value = load(SESSION)
    require(value.get("accepted_by") == AUTHORIZATION
            and value.get("status") ==
                "owner-authorized-autonomous-stage-breadcrumb-contact"
            and value.get("inputs", {}).get("product_medium") ==
                BREAD.PRODUCT_D81.relative_to(ROOT).as_posix()
            and value.get("active_interval", {}).get("quiet_seconds") == 180
            and value.get("authorization", {}).get("fallback") ==
                "product-owned LOADING LIBRARIES progress if breadcrumb remains unreachable",
            "stage breadcrumb session drift")
    return value


def preflight() -> dict[str, Any]:
    bread = BREAD.check(); enumeration = ENUM.check(); session_contract()
    record = bread.get("trace", {}).get("record", {})
    require(bread.get("status").endswith("CONTACT-NOT-AUTHORIZED")
            and record.get("address") == f"0x{TRACE_ADDRESS:04x}"
            and record.get("bytes") == TRACE_BYTES
            and record.get("commit") == "0xa5"
            and bread.get("media", {}).get("product_D81") ==
                bind(BREAD.PRODUCT_D81)
            and enumeration.get("builders", {}).get("total") == 65,
            "stage breadcrumb preflight drift")
    return {"authorization": authority(), "breadcrumb": bind(BREAD.RECEIPT),
            "enumeration": bind(ENUM.RECEIPT), "session": bind(SESSION),
            "runner": bind(RUNNER), "product_D81": bind(BREAD.PRODUCT_D81),
            "library_D81": BREAD.check()["media"]["library_D81"]}


def capture() -> dict[str, Any]:
    bound = preflight()
    require(Path(DEVICE).is_char_device(), f"serial device absent: {DEVICE}")
    OUT.mkdir(parents=True, exist_ok=True)
    raw_log = OUT / "monitor-raw.ndjson"; raw_log.write_bytes(b"")
    fd = os.open(DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        SERIAL.configure_serial(fd)
        stop_raw = VIEW.command(fd, b"t1", 0.08)
        RAW.append_raw(raw_log, "sole-final-stop", "t1", stop_raw)
        register_raw = VIEW.command(fd, b"r", 0.05)
        RAW.append_raw(raw_log, "register-tuple", "r", register_raw)
        registers = VIEW.parse_registers(register_raw)
        trace = RAW.read_range(fd, TRACE_ADDRESS, TRACE_BYTES, raw_log)
        ring = RAW.read_range(fd, 0x0000B582, 66, raw_log)
        frames = RAW.read_range(fd, 0x0000FF83, 2, raw_log)
    finally:
        os.close(fd)
    (OUT / "stage-breadcrumb.bin").write_bytes(trace)
    (OUT / "progress-ring.bin").write_bytes(ring)
    (OUT / "frame-counter.bin").write_bytes(frames)
    value = {"format": FORMAT + "-raw", "captured_on": "2026-08-15",
        "authority": bound, "device": DEVICE,
        "discipline": {"active_observations": 0, "stops": 1,
            "resumes": 0, "tuple_before_data": True,
            "raw_persisted_before_interpretation": True,
            "same_stopped_session": True, "CPU_left_stopped": True,
            "D1_D5_executed": False},
        "tuple": registers, "trace_hex": trace.hex(),
        "ring_hex": ring.hex(), "frame_counter_hex": frames.hex(),
        "raw_log": bind(raw_log),
        "claim_limit": "Raw-first capture only; result binder owns interpretation."}
    write_json(CAPTURE, value); return value


def u32(raw: bytes, offset: int) -> int:
    return int.from_bytes(raw[offset:offset + 4], "little")


def classify(captured: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any]]:
    raw = bytes.fromhex(captured["trace_hex"])
    require(len(raw) == TRACE_BYTES, "stage breadcrumb extent drift")
    if raw[31] == 0xA5:
        require(raw[:2] == b"ST" and raw[3] in REASONS,
                "committed stage breadcrumb schema drift")
        breadcrumb = {"decision": "COMMITTED", "phase": f"0x{raw[2]:02x}",
            "reason": {"value": f"0x{raw[3]:02x}",
                       "meaning": REASONS[raw[3]]},
            "attempt": raw[4], "role": raw[5], "stage": raw[6],
            "domain": raw[7], "sector_ordinal": int.from_bytes(raw[8:10], "little"),
            "track": raw[10], "sector": raw[11],
            "destination": f"0x{u32(raw, 12):08x}",
            "completed_length": u32(raw, 16),
            "expected_length": u32(raw, 20),
            "running_crc": f"0x{u32(raw, 24):08x}",
            "next_track": raw[28], "next_sector": raw[29],
            "wraps": raw[30], "commit": "0xa5"}
        return "BREADCRUMB-COMMITTED", breadcrumb, {"decision": "NOT-USED"}
    ring_capture = {"state_hex": captured["ring_hex"],
                    "frame_counter_hex": captured["frame_counter_hex"]}
    ring = RING.classify(ring_capture)
    if ring["decision"] != "INSTRUMENT-RED":
        return "PRODUCT-RING-REACHED", {"decision": "NOT-COMMITTED"}, ring
    return "PRE-TRACE-DIAGNOSTIC-RED; PRODUCT-FALLBACK-TRIGGERED", {
        "decision": "NOT-COMMITTED", "commit": f"0x{raw[31]:02x}",
        "raw_magic": raw[:2].hex()}, ring


def stopped_identity(tuple_value: dict[str, Any], status: str) -> dict[str, Any]:
    pc = int(tuple_value["PC"], 0)
    if status != "PRODUCT-RING-REACHED":
        truth = ElfTruth.read(Path(str(BREAD.STAGER) + ".elf"),
            llvm_readobj=PRODUCT.READOBJ, include_section_data=True)
        symbol = truth.symbol("show_disk_error")
        require(symbol.value <= pc < symbol.value + symbol.bytes,
                "breadcrumb red PC is not traced stager error hold")
        owner = "breadcrumb-stager"
    else:
        truth = ElfTruth.read(PRODUCT.DIAG_ELF, llvm_readobj=PRODUCT.READOBJ,
                              include_section_data=True)
        symbols = [row for row in truth.symbols
                   if row.value <= pc < row.value + max(row.bytes, 1)]
        symbols.sort(key=lambda row: (row.bytes or 0x10000, -row.value))
        symbol = symbols[0] if symbols else None; owner = "diagnostic-product"
    return {"PC": f"0x{pc:04x}", "owner": owner,
            "symbol": symbol.name if symbol else None,
            "symbol_offset": pc - symbol.value if symbol else None}


def derive() -> dict[str, Any]:
    captured = load(CAPTURE)
    require((OUT / "product-readback.d81").read_bytes() ==
            BREAD.PRODUCT_D81.read_bytes(), "breadcrumb product readback drift")
    status, breadcrumb, ring = classify(captured)
    value = {"format": FORMAT, "recorded_on": "2026-08-15",
        "status": status, "inputs": {"authorization": authority(),
            "breadcrumb": bind(BREAD.RECEIPT),
            "enumeration": captured["authority"]["enumeration"],
            "session": bind(SESSION), "raw_capture": bind(CAPTURE),
            "product_readback": bind(OUT / "product-readback.d81"),
            "library_readback": bind(OUT / "library-readback.d81")},
        "discipline": {"active_observations": 0, "stops": 1,
            "resumes": 0, "same_stopped_session": True,
            "CPU_left_stopped": True, "D1_D5_executed": False},
        "tuple": captured["tuple"], "breadcrumb": breadcrumb,
        "progress_ring": ring,
        "stopped_code_identity": stopped_identity(captured["tuple"], status),
        "fallback": {"triggered": status.startswith("PRE-TRACE"),
            "next_instrument": "ordinary-product LOADING LIBRARIES phase/item liveness"},
        "claim_limit": "One autonomous contact; CPU stopped; D1-D5 closed."}
    value["mutations"] = mutations(value); audit(value); return value


def audit(value: dict[str, Any]) -> None:
    status = value.get("status", "")
    require(status in {"BREADCRUMB-COMMITTED", "PRODUCT-RING-REACHED",
                       "PRE-TRACE-DIAGNOSTIC-RED; PRODUCT-FALLBACK-TRIGGERED"}
            and value.get("discipline") == {"active_observations": 0,
                "stops": 1, "resumes": 0, "same_stopped_session": True,
                "CPU_left_stopped": True, "D1_D5_executed": False}
            and value.get("fallback", {}).get("triggered") ==
                status.startswith("PRE-TRACE")
            and ((status == "BREADCRUMB-COMMITTED"
                  and value.get("breadcrumb", {}).get("commit") == "0xa5")
                 or status != "BREADCRUMB-COMMITTED"),
            "stage breadcrumb contact result drift")


def mutations(base: dict[str, Any]) -> list[str]:
    cases = {
        "add-stop": lambda x: x["discipline"].update(stops=2),
        "add-resume": lambda x: x["discipline"].update(resumes=1),
        "open-D1-D5": lambda x: x["discipline"].update(D1_D5_executed=True),
        "invent-observation": lambda x: x["discipline"].update(active_observations=1),
        "invert-fallback": lambda x: x["fallback"].update(
            triggered=not x["fallback"]["triggered"]),
        "invent-status": lambda x: x.update(status="UNKNOWN"),
    }
    if base["status"] == "BREADCRUMB-COMMITTED":
        cases["drop-commit"] = lambda x: x["breadcrumb"].update(commit="0x00")
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(base); mutate(trial)
        try: audit(trial)
        except ContactError: rejected.append(name)
    require(len(rejected) == len(cases), "breadcrumb contact mutation survived")
    return sorted(rejected)


def record() -> dict[str, Any]:
    require(not RECEIPT.exists(), "stage breadcrumb contact receipt exists")
    value = derive(); write_json(RESULT, value); write_json(RECEIPT, value)
    return value


def check() -> dict[str, Any]:
    value = load(RECEIPT); audit(value)
    require(value.get("inputs", {}).get("authorization") == authority()
            and value.get("inputs", {}).get("breadcrumb") == bind(BREAD.RECEIPT)
            and value.get("inputs", {}).get("session") == bind(SESSION),
            "stage breadcrumb tracked authority drift")
    base = {key: deepcopy(item) for key, item in value.items()
            if key != "mutations"}
    require(value.get("mutations") == mutations(base),
            "stage breadcrumb contact mutation drift")
    # Device raw data and readbacks are intentionally kept out of the source
    # tree.  Reconstruct the full receipt while they remain in the contact
    # workspace; a clean checkout still audits the committed result and all
    # of its tracked authorities without pretending to possess device bytes.
    if CAPTURE.is_file() and RESULT.is_file():
        require(value == derive() and value == load(RESULT),
                "stage breadcrumb contact reconstruction drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("preflight", "capture", "record", "check"))
    args = parser.parse_args()
    value = (preflight() if args.action == "preflight" else
             capture() if args.action == "capture" else
             record() if args.action == "record" else check())
    print(json.dumps(value, indent=2, sort_keys=True)); return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ContactError, BREAD.BreadcrumbError, OSError, KeyError, ValueError,
            subprocess.CalledProcessError) as error:
        print(f"LINK 107 STAGE BREADCRUMB CONTACT: {error}", file=sys.stderr)
        raise SystemExit(1)
