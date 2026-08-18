#!/usr/bin/env python3
"""Bind the preserved-state far-LMA installation discriminator."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v20_far_payload_installation_capture as CAP  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PRIOR = EVIDENCE / "c2.3-v2.0-far-payload-device-receipt.json"
CAPTURE = CAP.CAPTURE
CAPTURE_DRIVER = CAP.__file__
DRIVER = Path(__file__).resolve()
RECEIPT = EVIDENCE / "c2.3-v2.0-far-payload-installation-receipt.json"

FORMAT = "lisp65-c2.3-v20-far-payload-installation-result-v1"
STATUS = "FAR-LMA-PRESENT; SERVICE-ENTRY-UNPROVEN"
RECORDED_ON = "2026-08-13"
CAPTURE_SHA256 = "dd9dfbc97e6ffb4f4636daf078b8aca481c7b4b05a59ce296139220a2459dcb1"
REGISTER_SHA256 = "300b4b0d4e1049c76b4f8ed2fc28bcf58108195230eeb45bc83c2a3b6ae811bc"
OBSERVED_TUPLE = {
    "PC": "0xe099", "A": "0x02", "X": "0x00", "Y": "0xb4",
    "Z": "0x00", "B": "0x00", "SP": "0x01c9", "MAPH": "0x8000",
    "MAPL": "0x2480",
}
CLAIM_LIMIT = (
    "The three ELF-bound target-RAM probes prove the sampled far-service LMA "
    "bytes are installed.  They do not prove all 874 target bytes, service "
    "entry, descriptor initialization, product fault, fix, D2-D5, resume, or "
    "release readiness.")
NEXT = (
    "Host/ELF attribution of the caller dispatch into the mapped far-service "
    "window, starting from captured MAPL=0x2480; no further device contact.")


class ResultError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResultError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def probe_rows() -> list[dict[str, Any]]:
    expected, _ = CAP.expected_rows()
    rows = []
    for name, address, count in CAP.PROBES:
        raw = expected[name]
        rows.append({
            "name": name, "physical_address": f"0x{address:08x}",
            "bytes": count, "expected_hex": raw.hex(),
            "observed_hex": raw.hex(), "byteidentical": True,
            "observed_sha256": sha(raw),
        })
    return rows


def derive() -> dict[str, Any]:
    _, host_authority = CAP.expected_rows()
    service = [row for row in probe_rows()
               if row["name"].startswith("far-service-")]
    return {
        "format": FORMAT, "recorded_on": RECORDED_ON, "status": STATUS,
        "authority": host_authority | {
            "capture": {"path": CAPTURE.relative_to(ROOT).as_posix(),
                        "bytes": 5501, "sha256": CAPTURE_SHA256},
            "capture_driver": bind(Path(CAPTURE_DRIVER)),
            "result_driver": bind(DRIVER),
        },
        "discipline": {
            "tuple_and_SHA_first": True, "memory_rows": 5,
            "stops": 0, "runs": 0, "resets": 0, "resumes": 0,
            "CPU_left_stopped": True, "D2_D5_executed": False,
        },
        "tuple": OBSERVED_TUPLE,
        "tuple_identity": {
            "instruction": "JMP $E096", "pipeline_PC": "0xe099",
            "stable_fields": CAP.EXPECTED_STABLE_TUPLE,
            "accepted_pipeline_PC": sorted(CAP.FAIL_LOOP_PC),
            "pre_read_first_reds": [
                {"PC": "0xe098", "memory_reads": 0,
                 "cause": "single-byte PC pin"},
                {"PC": "0xe099", "memory_reads": 0,
                 "cause": "post-operand pipeline PC omitted"},
            ],
        },
        "physical_reads": probe_rows(),
        "decision": {
            "selected_row": "PRESENT",
            "service_probe_rows": len(service),
            "service_probe_matches": sum(row["byteidentical"] for row in service),
            "old_extent_tail_matches": True,
            "old_extent_successor_is_bound_zero_padding": True,
            "staging_length_mechanism": "REFUTED",
            "result": (
                "head, midpoint-containing row, and tail of the far-service LMA "
                "are byteidentical to the frozen linked ELF on target RAM"),
        },
        "exonerations": [
            "the medium-to-target stager did not stop at the old 46043-byte extent",
            "the sampled far-service target-RAM extent is not absent",
        ],
        "open_boundary": (
            "The descriptor remains all-zero and no service-entry witness exists. "
            "Presence in target RAM does not prove that caller dispatch entered "
            "the service or that every unsampled target byte is identical."),
        "next": NEXT, "claim_limit": CLAIM_LIMIT,
    }


def validate(value: dict[str, Any]) -> None:
    require(value.get("format") == FORMAT and value.get("status") == STATUS,
            "installation result status drift")
    require(value.get("authority") == derive()["authority"],
            "installation authority drift")
    require(value.get("discipline") == {
        "tuple_and_SHA_first": True, "memory_rows": 5,
        "stops": 0, "runs": 0, "resets": 0, "resumes": 0,
        "CPU_left_stopped": True, "D2_D5_executed": False},
        "read-only discipline drift")
    require(value.get("tuple") == OBSERVED_TUPLE,
            "preserved tuple drift")
    identity = value["tuple_identity"]
    require(identity["instruction"] == "JMP $E096"
            and identity["accepted_pipeline_PC"] == sorted(CAP.FAIL_LOOP_PC)
            and all(row["memory_reads"] == 0
                    for row in identity["pre_read_first_reds"]),
            "tuple instruction-identity drift")
    rows = value["physical_reads"]
    require(rows == probe_rows(), "physical installation probes drift")
    decision = value["decision"]
    require(decision == {
        "selected_row": "PRESENT", "service_probe_rows": 3,
        "service_probe_matches": 3, "old_extent_tail_matches": True,
        "old_extent_successor_is_bound_zero_padding": True,
        "staging_length_mechanism": "REFUTED",
        "result": (
            "head, midpoint-containing row, and tail of the far-service LMA "
            "are byteidentical to the frozen linked ELF on target RAM")},
        "installation decision drift")
    require(value.get("claim_limit") == CLAIM_LIMIT
            and value.get("next") == NEXT
            and "does not prove" in value.get("open_boundary", ""),
            "installation claim boundary widened")


def verify_capture() -> None:
    raw = CAPTURE.read_bytes()
    require(len(raw) == 5501 and sha(raw) == CAPTURE_SHA256,
            "live installation capture identity drift")
    captured = load(CAPTURE)
    require(captured["tuple"] == OBSERVED_TUPLE,
            "live captured tuple drift")
    require(captured["decision"] == {
        "outcome": "PRESENT", "service_probe_matches": 3,
        "service_probe_rows": 3}, "live decision drift")
    expected = {row["name"]: row for row in probe_rows()}
    observed = {row["name"]: row for row in captured["reads"]}
    require(set(observed) == set(expected), "live probe set drift")
    for name, row in expected.items():
        require(observed[name]["observed_hex"] == row["observed_hex"]
                and observed[name]["expected_hex"] == row["expected_hex"]
                and observed[name]["byteidentical"] is True,
                f"live probe drift: {name}")
    require(sha((CAP.OUT / "registers.raw").read_bytes()) == REGISTER_SHA256,
            "live register row identity drift")


def mutations() -> dict[str, Callable[[dict[str, Any]], None]]:
    return {
        "classify-absent": lambda x: x["decision"].update(selected_row="ABSENT"),
        "drop-head-match": lambda x: x["physical_reads"][2].update(byteidentical=False),
        "mutate-middle": lambda x: x["physical_reads"][3].update(observed_hex="00" * 16),
        "claim-full-extent": lambda x: x.update(
            claim_limit="all 874 target bytes proven"),
        "claim-service-entry": lambda x: x.update(
            open_boundary="service entry proven"),
        "blame-stager-length": lambda x: x["decision"].update(
            staging_length_mechanism="PROVEN"),
        "resume": lambda x: x["discipline"].update(resumes=1),
        "open-D2-D5": lambda x: x["discipline"].update(D2_D5_executed=True),
        "pin-one-PC": lambda x: x["tuple_identity"].update(
            accepted_pipeline_PC=["0xe097"]),
        "authorize-fix": lambda x: x.update(next="implement a product fix"),
    }


def selftest(base: dict[str, Any]) -> None:
    rejected = []
    for name, mutate in mutations().items():
        changed = deepcopy(base)
        mutate(changed)
        try:
            validate(changed)
        except (ResultError, KeyError, TypeError):
            rejected.append(name)
    require(rejected == list(mutations()), f"mutation survived: {rejected}")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else "check"
    require(action in {"record", "check", "selftest"},
            "usage: c2_v20_far_payload_installation_result.py record|check|selftest")
    value = derive()
    validate(value)
    selftest(value)
    if action == "record":
        verify_capture()
        RECEIPT.write_bytes(canonical(value))
    elif action == "check":
        require(load(RECEIPT) == value, "installation result receipt stale")
    print("v2.0 far-LMA installation result: "
          f"PASS outcome=PRESENT mutations={len(mutations())}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ResultError, OSError, ValueError, KeyError, TypeError) as error:
        print(f"v2.0 far-LMA installation result: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
