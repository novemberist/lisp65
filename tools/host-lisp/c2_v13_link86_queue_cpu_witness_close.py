#!/usr/bin/env python3
"""Close the authorized Link-86 CPU-side physical-key discriminator."""

from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CONFIG = ROOT / "config/c2-ship-builder-v1-link86-queue-cpu-witness.json"
PREP = EVIDENCE / "c2.3-v1.3-link86-queue-cpu-witness-preparation-receipt.json"
SESSION = ROOT / "scripts/c2-v13-link86-queue-cpu-witness-hw.sh"
OUT = ROOT / "build/ship-builder/v13/link86-queue-cpu-witness/device"
RECEIPT = EVIDENCE / "c2.3-v1.3-link86-queue-cpu-witness-device-receipt.json"
DRIVER = Path(__file__).resolve()


class CloseError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CloseError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    resolved = path.resolve()
    try:
        label = resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        label = str(resolved)
    return {"path": label, "bytes": path.stat().st_size, "sha256": sha(path)}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def main() -> int:
    config = load(CONFIG)
    prep = load(PREP)
    require(prep["status"] == "PREPARED-NON-PROMOTABLE-CPU-IO-WITNESS",
            "preparation status drift")
    require(config["limits"] == {
        "promotable": False,
        "product_candidate_bytes_changed": 0,
        "product_links": 0,
        "diagnostic_identities": 1,
        "physical_key_contacts": 1,
        "virtual_keys": 0,
        "post_key_screen_captures": 0,
    }, "owner contact limits drift")
    image = ROOT / prep["diagnostic"]["image"]["path"]
    require(sha(image) == prep["diagnostic"]["image"]["sha256"],
            "diagnostic image drift")
    require((OUT / "package-readback.d81").read_bytes() == image.read_bytes(),
            "mounted diagnostic image readback drift")
    pre = (OUT / "pre-key-witness.bin").read_bytes()
    post = (OUT / "post-key-witness.bin").read_bytes()
    require(len(pre) == 6 and len(post) == 6, "six-byte witness required")
    require(pre[0] > 0 and pre[3] == 0,
            "sampler was not live and empty before physical input")
    require(post[0] > 0, "sampler did not run after physical input")
    if post[3] == 1 and post[4] & 0x80:
        outcome = "queue-present-consumer-path"
        status = "DEVICE-DISCRIMINATOR-CPU-QUEUE-PRESENT"
        interpretation = config["interpretation"]["queue_present"]
    elif post[3] == 0 and not (post[4] & 0x80):
        outcome = "queue-empty-production-or-configuration"
        status = "DEVICE-DISCRIMINATOR-CPU-QUEUE-EMPTY"
        interpretation = config["interpretation"]["queue_empty"]
    else:
        raise CloseError(
            f"inconsistent latch/state: latch={post[3]} state=0x{post[4]:02x}")
    value = {
        "format": "lisp65-c2.3-v1.3-link86-queue-cpu-witness-device-v1",
        "recorded_on": date.today().isoformat(),
        "status": status,
        "candidate_link": 86,
        "contact": {
            "count": 1,
            "cold_reset": True,
            "physical_key": config["physical_key"],
            "virtual_keys": 0,
            "post_key_screen_captures": 0,
        },
        "witness": {
            "pre": list(pre),
            "post": list(post),
            "samples": post[0],
            "last_state": f"0x{post[1]:02x}",
            "last_code": f"0x{post[2]:02x}",
            "latched": post[3],
            "latched_state": f"0x{post[4]:02x}",
            "latched_code": f"0x{post[5]:02x}",
        },
        "preregistered_interpretation": {
            "selected": outcome,
            "result": interpretation,
        },
        "decision": {
            "product_fix_authorized": False,
            "product_candidate_bytes_changed": 0,
            "product_links_created": 0,
            "diagnostic_identity_promotable": False,
            "v1.3_status": "closed-pending-owner-review",
        },
        "bindings": {
            "config": bind(CONFIG),
            "preparation": bind(PREP),
            "session": bind(SESSION),
            "driver": bind(DRIVER),
            "image": bind(image),
            "package_readback": bind(OUT / "package-readback.d81"),
            "pre_key_witness": bind(OUT / "pre-key-witness.bin"),
            "post_key_witness": bind(OUT / "post-key-witness.bin"),
        },
        "claim_limit": (
            "One non-promotable diagnostic identity, one cold-reset physical-key "
            "contact and CPU-side live-I/O samples copied to ordinary RAM. No "
            "product fix, product link, virtual key or post-key screen capture."
        ),
    }
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=RECEIPT.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(RECEIPT)
    print(
        "c2-v13-link86-queue-cpu-witness-close: PASS "
        f"outcome={outcome} samples={post[0]} "
        f"D60A=0x{post[4]:02x} D619=0x{post[5]:02x}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CloseError, KeyError, OSError, ValueError,
            json.JSONDecodeError) as error:
        print(f"c2-v13-link86-queue-cpu-witness-close: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
