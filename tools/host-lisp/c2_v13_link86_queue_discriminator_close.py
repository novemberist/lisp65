#!/usr/bin/env python3
"""Close the authorized Link-86 physical-key queue discriminator."""

from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CONFIG = ROOT / "config/c2-ship-builder-v1-link86-queue-discriminator.json"
SESSION = ROOT / "scripts/c2-v13-link86-queue-discriminator-hw.sh"
ATTRIBUTION = EVIDENCE / (
    "c2.3-v1.3-link86-ship-output-input-host-elf-attribution-receipt.json"
)
OUT = ROOT / "build/ship-builder/v13/link86-queue-discriminator/run"
RECEIPT = EVIDENCE / (
    "c2.3-v1.3-link86-physical-key-queue-discriminator-receipt.json"
)
CORRECTION = EVIDENCE / (
    "c2.3-v1.3-link86-queue-capture-view-host-elf-attribution-receipt.json"
)
DRIVER = Path(__file__).resolve()


class CloseError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CloseError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path, *, address: str | None = None) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    resolved = path.resolve()
    try:
        label = resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        label = str(resolved)
    result: dict[str, Any] = {
        "path": label,
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }
    if address is not None:
        result["address"] = address
    return result


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def one(path: Path) -> int:
    data = path.read_bytes()
    require(len(data) == 1, f"one-byte readback required: {path}")
    return data[0]


def main() -> int:
    require(not CORRECTION.is_file(),
            "superseded: m65 --memsave reads RAM under mapped I/O; "
            "the historical zero bytes are not live D60A/D619")
    config = load(CONFIG)
    prior = load(ATTRIBUTION)
    queue = load(OUT / "queue.json")
    d60a = one(OUT / "d60a.bin")
    d619 = one(OUT / "d619.bin")
    state = one(OUT / "state-before-human.bin")

    require(config["status"] == "owner-authorized-one-read-only-contact",
            "owner authorization drift")
    require(config["candidate_link"] == 86
            and config["limits"] == {
                "product_bytes": 0,
                "product_links": 0,
                "physical_keys": 1,
                "post_key_memory_reads": 2,
                "virtual_keys": 0,
                "screen_captures_after_key": 0,
            }, "contact limits drift")
    require(prior["owner_decision_boundary"]["smallest_discriminator"].startswith(
        "On unchanged Link 86, type one physical printable key"),
        "prior attribution boundary drift")
    image = ROOT / config["image"]
    require(sha(image) == config["image_sha256"], "Link-86 image drift")
    require((OUT / "package-readback.d81").read_bytes() == image.read_bytes(),
            "mounted package readback drift")
    require(state == config["runtime_waiting_value"] == 2,
            "Runtime was not waiting before physical input")
    require(queue == {"d60a": f"0x{d60a:02x}", "d619": f"0x{d619:02x}"},
            "queue summary does not match byte readbacks")
    require(d60a == 0 and d619 == 0,
            f"pre-registered queue-empty outcome not observed: {d60a:02x}/{d619:02x}")

    result = {
        "format": "lisp65-c2.3-v1.3-link86-physical-key-queue-discriminator-v1",
        "recorded_on": date.today().isoformat(),
        "status": "DEVICE-DISCRIMINATOR-QUEUE-EMPTY",
        "candidate_link": 86,
        "contact": {
            "count": 1,
            "cold_reset": True,
            "exact_unchanged_image": True,
            "runtime_state_before_key": state,
            "physical_key": config["physical_key"],
            "operator_visible_effect": "none; screen remained blank blue",
            "virtual_keys": 0,
            "post_key_reads": 2,
            "post_key_screen_captures": 0,
        },
        "readback": {
            "D60A": f"0x{d60a:02x}",
            "D619": f"0x{d619:02x}",
            "queue_present": bool(d60a & 0x80),
            "dequeue_writes": 0,
        },
        "preregistered_interpretation": {
            "selected": "queue-empty",
            "result": (
                "The physical key was not pending in the hardware queue at "
                "capture time. The proposed mechanism 'queue contains the key "
                "but inherited KERNAL GETIN never consumes it' is refuted. The "
                "divergence is below the queue observation and returns to owner "
                "review with these two bytes as ground truth."
            ),
            "not_claimed": [
                "a Ship direct-queue fix",
                "a KERNAL GETIN consumer defect",
                "a keyboard-scan mechanism below the empty queue",
                "read-line correctness or failure",
            ],
        },
        "decision": {
            "product_fix_authorized": False,
            "additional_hardware_authorized": False,
            "product_bytes_changed": 0,
            "product_links_created": 0,
            "v1.3_status": "closed-pending-owner-review",
        },
        "bindings": {
            "config": bind(CONFIG),
            "session": bind(SESSION),
            "prior_attribution": bind(ATTRIBUTION),
            "driver": bind(DRIVER),
            "image": bind(image),
            "package_readback": bind(OUT / "package-readback.d81"),
            "state_before_key": bind(
                OUT / "state-before-human.bin", address="0x00000085"),
            "queue_state": bind(OUT / "d60a.bin", address="0x0000d60a"),
            "queue_code": bind(OUT / "d619.bin", address="0x0000d619"),
            "queue_summary": bind(OUT / "queue.json"),
        },
        "claim_limit": (
            "One unchanged-image physical-key contact and two non-consuming "
            "one-byte reads. The receipt applies the pre-registered empty-queue "
            "outcome; it does not infer a new mechanism, authorize a fix, alter "
            "product bytes or create a link."
        ),
    }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    print(
        "c2-v13-link86-queue-discriminator: PASS "
        f"D60A=0x{d60a:02x} D619=0x{d619:02x} outcome=queue-empty"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CloseError, OSError, ValueError, KeyError, TypeError,
            json.JSONDecodeError) as error:
        print(f"c2-v13-link86-queue-discriminator: FIRST RED: {error}")
        raise SystemExit(2)
