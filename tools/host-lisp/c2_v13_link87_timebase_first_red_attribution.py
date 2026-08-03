#!/usr/bin/env python3
"""Attribute Link 87's pre-input RUNTIME_IO_ERROR without another contact."""

from __future__ import annotations

from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / "c2.3-v1.3-link87-timebase-device-first-red-attribution.json"
CONFIG = ROOT / "config/c2-ship-builder-v1-link87-interactive-human-test.json"
CONTRACT = ROOT / "config/c2-ship-boot-inheritance-contract.json"
BOOT = EVIDENCE / "c2.3-v1.3-ship-boot-inheritance-gate-receipt.json"
CARD = EVIDENCE / "c2.3-v1.3-link87-repeated-timebase-wplto-receipt.json"
REVIEW = ROOT / "docs/planning/1.3-link84-closing-first-red-review.md"
SHIP_IO = ROOT / "products/runtime-core/ship_io.c"
SESSION = ROOT / "scripts/c2-v13-link87-interactive-human-test-hw.sh"
DRIVER = Path(__file__).resolve()
RUN = ROOT / "build/ship-builder/v13/link87-interactive-human-test/run"
ELF = ROOT / "build/ship-builder/v13/link87-final-3bcb488d/interactive.runtime.elf"
IMAGE = ROOT / "build/ship-builder/v13/link87-final-3bcb488d/interactive.d81"
REPRO = ROOT / (
    "build/ship-builder/v13/link87-interactive-repro-3bcb488d/"
    "reproducibility.json"
)
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"evidence absent: {path}")
    data = path.read_bytes()
    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def symbol_bytes(truth: ElfTruth, name: str) -> bytes:
    symbol = truth.symbol(name)
    section = truth.section(symbol.section)
    data = truth.section_bytes(symbol.section)
    offset = symbol.value - section.address
    require(symbol.bytes > 0 and 0 <= offset <= len(data) - symbol.bytes,
            f"symbol bytes unavailable: {name}")
    return data[offset:offset + symbol.bytes]


def simulate(start: int, reference: Callable[[int, int], bool],
             lines: int = 312, deltas: int = 3) -> tuple[bool, int | None]:
    """Run the target ordering: IRQ on entering line 255, then observe line."""
    position = start
    previous_line = position
    counter = 0
    synchronized = False
    previous_counter = 0
    remaining = deltas
    for _ in range(lines * 8):
        position = (position + 1) % lines
        if position == 255:
            counter += 1
        if reference(previous_line, position):
            if not synchronized:
                synchronized = True
                previous_counter = counter
            else:
                delta = counter - previous_counter
                if delta != 1:
                    return False, delta
                previous_counter = counter
                remaining -= 1
                if remaining == 0:
                    return True, None
        previous_line = position
    raise AttributionError("bounded raster simulation did not terminate")


def low_byte_decrease(previous: int, current: int) -> bool:
    return (current & 0xFF) < (previous & 0xFF)


def full_raster_wrap(previous: int, current: int) -> bool:
    return bool(previous & 0x100) and not bool(current & 0x100)


def main() -> int:
    config = load(CONFIG)
    contract = load(CONTRACT)
    boot = load(BOOT)
    card = load(CARD)
    repro = load(REPRO)
    source = SHIP_IO.read_text(encoding="utf-8")
    require(config["candidate_link"] == 87
            and config["image_sha256"] == bind(IMAGE)["sha256"],
            "Link-87 image commission drift")
    require((RUN / "state.bin").read_bytes() == b"\xe5",
            "device First Red is not RUNTIME_IO_ERROR")
    require(IMAGE.read_bytes() == (RUN / "package-readback.d81").read_bytes(),
            "mounted package differs from committed Link-87 image")
    require(contract["target"]["independent_progress_oracle"]
            == "$D012 wrap, never the counter under test"
            and "current < previous" in source,
            "low-byte reference implementation drift")
    require(boot["status"] == "passed-ship-owned-repeated-frame-clock"
            and boot["host_execution"]["executions"] == 3
            and card["status"]
            == "passed-Link87-repeated-timebase-one-product-shaped-WPLTO"
            and repro["comparison_sha256"] == config["image_sha256"],
            "Link-87 host/card authority drift")

    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    reference_body = symbol_bytes(truth, "ship_reference_wrap")
    irq_body = symbol_bytes(truth, "lisp65_ship_timebase_irq")
    require(reference_body.count(bytes.fromhex("ad 12 d0")) == 1
            and reference_body.startswith(bytes.fromhex("ae 12 d0"))
            and bytes.fromhex("90 27") in reference_body,
            "linked target does not compare successive D012 low bytes")
    require(len(irq_body) == 23
            and bytes.fromhex("8d 19 d0") in irq_body,
            "linked IRQ owner/acknowledgement drift")

    low_results = [simulate(start, low_byte_decrease) for start in range(312)]
    full_results = [simulate(start, full_raster_wrap) for start in range(312)]
    require(all(not passed for passed, _ in low_results),
            "D012-low oracle unexpectedly survives a target phase")
    require(all(passed for passed, _ in full_results),
            "full 9-bit raster oracle fails a target phase")
    failures = Counter(delta for _, delta in low_results)
    require(failures == Counter({0: 312}),
            "D012-low failure signature drift")

    value = {
        "format": "lisp65-c2.3-v1.3-link87-timebase-device-first-red-attribution-v1",
        "recorded_on": date.today().isoformat(),
        "status": "ATTRIBUTED-D012-LOW-BYTE-HAS-TWO-DECREASES-PER-FRAME",
        "candidate_link": 87,
        "release_ready": False,
        "device_first_red": {
            "runtime_state": "0xe5",
            "meaning": "RUNTIME_IO_ERROR before physical input",
            "virtual_keys_sent": 0,
            "physical_keys_requested": 0,
            "package_readback_byteidentical": True,
        },
        "mechanism": {
            "raster_domain": "9-bit raster with 312 modeled lines",
            "implementation_oracle": "successive $D012 low-byte decrease",
            "decreases_per_frame": [
                "line 255 -> 256: D012 ff -> 00, owned IRQ just advanced",
                "last line -> line 0: D012 37 -> 00, no owned IRQ advanced",
            ],
            "effect": (
                "the verifier samples one zero counter delta within at most "
                "two verification edges and returns RUNTIME_IO_ERROR"
            ),
            "correct_reference_shape": (
                "$D011 bit-8 high-to-low transition, i.e. one full 9-bit "
                "raster frame wrap"
            ),
        },
        "executed_phase_matrix": {
            "start_phases": 312,
            "required_deltas": 3,
            "d012_low_decrease_passes": sum(p for p, _ in low_results),
            "d012_low_decrease_rejections": sum(not p for p, _ in low_results),
            "first_bad_delta_histogram": {str(k): v for k, v in failures.items()},
            "full_9bit_wrap_passes": sum(p for p, _ in full_results),
        },
        "gate_lesson": {
            "old_host_oracle": "one synthetic callback per assumed frame",
            "missing_world_fact": "$D012 alone is the low byte of a 9-bit raster",
            "why_green": (
                "the host supplied one event per logical frame and never "
                "executed the target register transition sequence"
            ),
            "required_closure": (
                "the gate oracle must execute the 9-bit target raster model "
                "and reject the low-byte-only implementation"
            ),
        },
        "scope": {
            "product_bytes_changed_after_link": 0,
            "additional_product_links": 0,
            "additional_hardware_contacts": 0,
            "v1.3_status": "closed-pending-owner-review",
            "next": "owner decision required before a corrected successor link",
        },
        "bindings": {
            "config": bind(CONFIG), "contract": bind(CONTRACT),
            "boot_gate": bind(BOOT), "wplto": bind(CARD),
            "owner_review": bind(REVIEW), "ship_io": bind(SHIP_IO),
            "runtime_elf": bind(ELF), "image": bind(IMAGE),
            "fresh_repro": bind(REPRO), "session": bind(SESSION),
            "device_state": bind(RUN / "state.bin"),
            "package_readback": bind(RUN / "package-readback.d81"),
            "fresh_basic_screen": bind(RUN / "fresh-basic.png"),
            "upload_log": bind(RUN / "upload.log"),
            "elf_truth": bind(ROOT / "tools/host-lisp/elf_truth.py"),
            "driver": bind(DRIVER),
        },
        "claim_limit": (
            "The exact Link-87 image failed before input. The linked low-byte "
            "oracle is rejected for every one of 312 starting raster phases; "
            "no corrected product, successor link or physical pass is claimed."
        ),
    }
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    print("c2-v13-link87-timebase-attribution: PASS phases=312 "
          "d012-low=0/312 full-9bit=312/312 state=0xe5 contacts=0 links=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"c2-v13-link87-timebase-attribution: FIRST RED: {error}")
        raise SystemExit(2)
