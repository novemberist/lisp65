#!/usr/bin/env python3
"""Bind the preserved D1 red after mapped-far payload delivery.

The device row is intentionally narrow.  It records one stopped session
against the successor medium and proves that the old descriptor-uninitialised
state recurred byte-for-byte even though the packed medium now contains the
linked far-service extent.  It does not claim that the payload reached target
RAM; that extent was not part of the authorised read set.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v20_building_heap_device_result as PRIOR_MODEL  # noqa: E402

EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
CAPTURE_CONTRACT = ROOT / "config/c2-v20-building-heap-capture-row.json"
DELIVERY = EVIDENCE / "c2.3-v2.0-far-payload-delivery-closure-receipt.json"
PRIOR = EVIDENCE / "c2.3-v2.0-building-heap-device-receipt.json"
PRIOR_DRIVER = ROOT / "tools/host-lisp/c2_v20_building_heap_device_result.py"
ELF = ROOT / (
    "build/c2.3/v2.0-crc-carveout-card/final/"
    "lisp65-c2-substitution-linked.prg.elf")
CAPTURE = ROOT / "build/c2.3/v2.0-far-payload-d1-hw"
RECEIPT = EVIDENCE / "c2.3-v2.0-far-payload-device-receipt.json"
DRIVER = Path(__file__).resolve()

FORMAT = "lisp65-c2.3-v20-far-payload-device-result-v1"
STATUS = "D1-HEAP-RED-REPRODUCED; FAR-DESCRIPTOR-UNINITIALIZED"
RECORDED_ON = "2026-08-12"
AUTHORIZATION_COMMIT = "11166ae4"
ELF_SHA256 = "34fb0a1173d66c2779ec7778ab0ab208bda7fd9a407989e2bb31660e71af4080"
PRODUCT_D81_SHA256 = "d2ab92b14140caab5f3ca87b51fa8e4ab65183b387d6fe76ee4ae1588fcd1130"
DELIVERED_CODE_SHA256 = "94479944eb6f8ece405be2902a424961b72e1936534ecd6acb0e8a2287a9c4ec"
SCREEN_SHA256 = "7550769c93947242ab482ebc046ab1fa8fad731c9e87ce5d9cc5c68027d79d3d"
REGISTERS_SHA256 = "b3486d04a2fdc9adca3db660a60aa5684e41c1aa744c62986fe3303e00546352"
FAIL_VIEW_SHA256 = "8355160349bfb1542047517ebda3ab99857adb3f341e5983234cea8678e232f2"
NAMEOFF_VIEW_SHA256 = "4b298058e1d5fd3f2fa20ead21773912a5dc38da3c0da0bbc7de1adfb6011f1c"

TUPLE = {
    "PC": "0xE097", "SP": "0x01C9", "A": "0x02", "X": "0x00",
    "Y": "0xB4", "Z": "0x00", "B": "0x00", "MAPH": "0x8000",
    "MAPL": "0x2480",
}

PHYSICAL = {
    "hardware-stack": (0x0100, 256,
        "0000000000000000000000000000000000e300b3a0820083001180b100e00083"
        "0000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000"
        "000000000000000042e400b40000328731b803bb2e2f0060605cc5390105ddc9"
        "2240a818005ca46218004920de276420b103b300e300833dc1ea2d31ea362f20"),
    "allocator-zp": (0x003D, 16, "00000000600000000000000000000000"),
    "vm-and-boot-zp": (0x005F, 21,
        "03000000e000000000000000000000000000000901"),
    "ownership-and-convergence-zp": (0x0087, 9,
        "020000000000000000"),
    "ordinary-dma-list": (0xB9D3, 12, "000200a3cf0022fa05000000"),
    "gc-runs": (0xB9EE, 2, "0000"),
    "pending-error-pointer": (0xBFEF, 2, "0000"),
    "runtime-overlay-state": (0xBFF7, 4, "00810000"),
    "convergence-state": (0xC000, 66, "00" * 66),
    "c2-runtime-state": (0xC080, 50, "00" * 50),
}

FAIL_VIEW_HEX = (
    "80e648ad0dddee85ff684078a9008d1ad0a9028d20d04c96e09d0008608508ae"
    "8ec0ac8fc0a9025aa4048406a40584077a8404a40884054ccab5ac80c0ad81c0")
NAMEOFF_VIEW_HEX = "00" * 99


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


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    completed = subprocess.run(
        ["git", "show", f"{commit}:{name}"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, check=True).stdout.strip()
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(completed.stdout), "sha256": sha(completed.stdout)}


def physical_rows() -> dict[str, Any]:
    return {name: {"physical_address": f"0x{address:08X}", "bytes": count,
                   "raw_hex": raw}
            for name, (address, count, raw) in sorted(PHYSICAL.items())}


def derive() -> dict[str, Any]:
    delivery = load(DELIVERY)
    prior = load(PRIOR)
    require(bind(ELF)["sha256"] == ELF_SHA256, "candidate ELF identity drift")
    require(delivery["shared_system"]["product_D81"]["sha256"]
            == PRODUCT_D81_SHA256, "successor D81 identity drift")
    require(delivery["materialization"]["delivered_sha256"]
            == DELIVERED_CODE_SHA256, "delivered code identity drift")
    nonstack = {name: row for name, row in physical_rows().items()
                if name != "hardware-stack"}
    require(prior["device"]["physical_state"] == nonstack,
            "prior physical-state vocabulary drift")
    require(PRIOR_MODEL.STACK_HEX == PHYSICAL["hardware-stack"][2],
            "prior hardware-stack identity drift")
    return {
        "format": FORMAT, "recorded_on": RECORDED_ON, "status": STATUS,
        "authority": {
            "authorization": git_bind(AUTHORIZATION_COMMIT, PLAN),
            "capture_contract": bind(CAPTURE_CONTRACT),
            "delivery": bind(DELIVERY), "candidate_ELF": bind(ELF),
            "prior_device_result": bind(PRIOR), "driver": bind(DRIVER),
            "prior_device_driver": bind(PRIOR_DRIVER),
        },
        "contact": {
            "owner_observation": {
                "visible": ["LISP65: STAGING MEDIA", "LISP65: BUILDING HEAP"],
                "absent": ["LISP65: LOADING LIBRARIES", "WORKBENCH 1.5.0",
                           "lisp65>"],
                "frame": "red", "screenshot_sha256": SCREEN_SHA256,
            },
            "one_stopped_session": {"stops": 1, "resumes": 0,
                "CPU_left_stopped": True, "D2_D5_executed": False},
            "tuple_first": TUPLE,
            "register_read_sha256": REGISTERS_SHA256,
            "readback_identity": {
                "product_D81_sha256": PRODUCT_D81_SHA256,
                "delivered_CODE_BIN_sha256": DELIVERED_CODE_SHA256,
            },
            "physical_state": physical_rows(),
            "cpu_view": {
                "fail_loop": {"logical": "0xE080", "bytes": 64,
                    "raw_hex": FAIL_VIEW_HEX, "sha256": FAIL_VIEW_SHA256,
                    "PC_within": ["0xE096", "0xE097"]},
                "nameoff_get": {"logical": "0x3143", "bytes": 99,
                    "raw_hex": NAMEOFF_VIEW_HEX,
                    "sha256": NAMEOFF_VIEW_SHA256,
                    "interpretation": ("active MAPL=0x2480 makes the linked "
                                       "nameoff_get body invisible")},
            },
        },
        "comparison_to_pre_delivery_red": {
            "physical_ranges_compared": len(PHYSICAL),
            "physical_ranges_byteidentical": len(PHYSICAL),
            "BRK_frame_byteidentical": True,
            "only_tuple_delta": "PC advanced within the same E096/E097 fail loop",
        },
        "decision": {
            "selected_row": "far-service-descriptor-never-initialized",
            "status_0x87": {"observed": "0x02", "clear": "0x5A",
                            "committed": "0xA5", "legal": False},
            "descriptor": {"physical_address": "0x0000C000", "bytes": 66,
                           "all_zero": True},
            "mapping": {"MAPH": "0x8000", "MAPL": "0x2480",
                        "ordinary_required_MAPL": "0x0000"},
            "BRK": {"stacked_B": 1, "stacked_continuation": "0x3187",
                    "linked_context": "nameoff_get"},
            "result": ("the convergence descriptor was not initialized before "
                       "the recurrent mapped-view BRK"),
        },
        "exonerations": [
            "the packed D81 contains the complete linked far-service extent",
            "the linked service geometry and eight audited exits remain unchanged",
        ],
        "open_boundary": (
            "The authorised row did not read physical target RAM at the far-service "
            "LMA.  It therefore does not prove that the D81 payload was installed "
            "there, nor that service entry executed."),
        "claim_limit": (
            "One preserved D1 stopped-state row only: recurrent uninitialised "
            "descriptor and mapped-view BRK under the delivered-media identity. "
            "No target-RAM payload, service-entry, product-fault, fix, new contact, "
            "D2-D5 or release-readiness claim."),
    }


def validate(value: dict[str, Any]) -> None:
    require(value.get("format") == FORMAT and value.get("status") == STATUS,
            "far-payload device status drift")
    contact = value["contact"]
    require(contact["one_stopped_session"] == {
        "stops": 1, "resumes": 0, "CPU_left_stopped": True,
        "D2_D5_executed": False}, "stopped-session discipline drift")
    require(contact["tuple_first"] == TUPLE, "tuple-first drift")
    require(contact["readback_identity"] == {
        "product_D81_sha256": PRODUCT_D81_SHA256,
        "delivered_CODE_BIN_sha256": DELIVERED_CODE_SHA256},
        "successor media identity drift")
    require(contact["physical_state"] == physical_rows(),
            "physical stopped-state drift")
    decision = value["decision"]
    require(decision["selected_row"] == "far-service-descriptor-never-initialized"
            and decision["status_0x87"]["observed"] == "0x02"
            and decision["status_0x87"]["legal"] is False
            and decision["descriptor"]["all_zero"] is True,
            "descriptor classification drift")
    require(value["comparison_to_pre_delivery_red"]
            ["physical_ranges_byteidentical"] == len(PHYSICAL),
            "pre-delivery comparison drift")
    require("did not read physical target RAM" in value["open_boundary"]
            and "No target-RAM payload" in value["claim_limit"],
            "claim boundary widened")


def verify_capture() -> None:
    value = load(CAPTURE / "stopped-state-capture.json")
    require(value["CPU_left_stopped"] is True and value["resume_count"] == 0,
            "live capture stop discipline drift")
    require(value["tuple_first"] == load(CAPTURE / "stopped-registers.json"),
            "live capture tuple provenance drift")
    observed = {row["name"]: row["hex"]
                for row in value["physical_bank0_reads"]}
    require(observed == {name: raw for name, (_, _, raw) in PHYSICAL.items()},
            "live physical row differs from bound constants")
    cpu = {row["name"]: row["hex"] for row in value["cpu_view_reads"]}
    require(cpu == {"fail-loop-neighborhood": FAIL_VIEW_HEX,
                    "nameoff-get-context": NAMEOFF_VIEW_HEX},
            "live CPU-view row differs from bound constants")
    require(sha((CAPTURE / "product-readback.d81").read_bytes())
            == PRODUCT_D81_SHA256, "live D81 readback identity drift")
    require(sha((CAPTURE / "product-boot.png").read_bytes()) == SCREEN_SHA256,
            "live screen identity drift")


def mutations() -> dict[str, Callable[[dict[str, Any]], None]]:
    return {
        "old-product-world": lambda x: x["contact"]["readback_identity"].update(
            product_D81_sha256="704c60a3979b4a1b5b55f7ccf8de95d99b2ef9fb82c462dfe496952af3ab4dde"),
        "legalize-02": lambda x: x["decision"]["status_0x87"].update(legal=True),
        "invent-descriptor": lambda x: x["decision"]["descriptor"].update(all_zero=False),
        "unmap": lambda x: x["contact"]["tuple_first"].update(MAPL="0x0000"),
        "drop-range": lambda x: x["contact"]["physical_state"].pop("convergence-state"),
        "resume": lambda x: x["contact"]["one_stopped_session"].update(resumes=1),
        "open-D2-D5": lambda x: x["contact"]["one_stopped_session"].update(D2_D5_executed=True),
        "claim-target-install": lambda x: x.update(open_boundary="target RAM proven"),
    }


def selftest(base: dict[str, Any]) -> None:
    rejected = []
    for name, mutate in mutations().items():
        changed = deepcopy(base); mutate(changed)
        try:
            validate(changed)
        except (ResultError, KeyError, TypeError):
            rejected.append(name)
    require(rejected == list(mutations()), f"mutation survived: {rejected}")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else "check"
    require(action in {"record", "check", "selftest"},
            "usage: c2_v20_far_payload_device_result.py record|check|selftest")
    value = derive(); validate(value); selftest(value)
    if action == "record":
        verify_capture(); RECEIPT.write_bytes(canonical(value))
    elif action == "check":
        require(load(RECEIPT) == value, "far-payload device receipt stale")
    print(f"v2.0 far-payload device result: PASS descriptor-uninitialized mutations={len(mutations())}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ResultError, OSError, ValueError, KeyError, TypeError,
            subprocess.CalledProcessError) as error:
        print(f"v2.0 far-payload device result: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
