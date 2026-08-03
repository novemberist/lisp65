#!/usr/bin/env python3
"""Close the authorized Link-85 Ship jiffy split from read-only dumps."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REVIEW = ROOT / "docs/planning/1.3-link84-closing-first-red-review.md"
ATTRIBUTION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-link85-ship-input-boot-host-elf-attribution-receipt.json"
)
CAPTURE = ROOT / "build/ship-builder/v13/link85-jiffy-split-capture/run"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-link85-jiffy-split-readonly-capture-receipt.json"
)
M65 = ROOT / "tools/m65tools/m65"
DRIVER = Path(__file__).resolve()


class CaptureError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CaptureError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    resolved = path.resolve()
    try:
        label = resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        label = str(resolved)
    return {
        "path": label,
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def read_exact(name: str, size: int) -> bytes:
    path = CAPTURE / name
    require(path.is_file(), f"capture absent: {path}")
    value = path.read_bytes()
    require(len(value) == size, f"capture length drift: {name}={len(value)}")
    return value


def u16le(value: bytes) -> int:
    require(len(value) == 2, "u16 capture must be two bytes")
    return value[0] | value[1] << 8


def audit(value: dict[str, Any]) -> None:
    samples = value["samples"]
    require(samples["first"]["jiffy_bytes"] == [0x64, 0x00],
            "first jiffy witness drift")
    require(samples["second"]["jiffy_bytes"] == [0x64, 0x00],
            "second jiffy witness drift")
    require(samples["first"]["jiffy_word"] == 0x6400
            and samples["second"]["jiffy_word"] == 0x6400,
            "jiffy changed across the authorized interval")
    require(samples["first"]["d01a"] == 0
            and samples["second"]["d01a"] == 0,
            "VIC interrupt-enable witness is not frozen/off")
    require(samples["first"]["irq_vector"] == 0xF974
            and samples["second"]["irq_vector"] == 0xF974,
            "IRQ vector changed across capture")
    require(samples["first"]["getin_vector"] == 0xF319
            and samples["second"]["getin_vector"] == 0xF319,
            "GETIN vector changed across capture")
    require(value["binary_split"]["outcome"] == "jiffy-frozen",
            "pre-registered split outcome drift")
    require(value["binary_split"]["live_boundary"] == "wait-before-read-line",
            "live boundary drift")
    require(value["binary_split"]["input_layer"] == "not-reached-not-tested",
            "capture overclaims input")
    require(value["scope"]["product_bytes_changed"] == 0
            and value["scope"]["product_links_created"] == 0
            and value["scope"]["reset_before_capture"] is False,
            "read-only scope drift")


def mutations(value: dict[str, Any]) -> dict[str, str]:
    changes = {
        "advancing-jiffy": (["samples", "second", "jiffy_word"], 0x6401),
        "armed-vic": (["samples", "second", "d01a"], 1),
        "irq-vector-drift": (["samples", "second", "irq_vector"], 0xF9EC),
        "input-overclaim": (["binary_split", "input_layer"], "working"),
        "product-byte-claim": (["scope", "product_bytes_changed"], 1),
    }
    result: dict[str, str] = {}
    for name, (path, replacement) in changes.items():
        candidate = deepcopy(value)
        target: Any = candidate
        for component in path[:-1]:
            target = target[component]
        target[path[-1]] = replacement
        try:
            audit(candidate)
        except CaptureError:
            result[name] = "rejected"
        else:
            raise CaptureError(f"verification mutation survived: {name}")
    return result


def main() -> int:
    review = REVIEW.read_text(encoding="utf-8")
    require("Jiffy split capture — authorized 2026-08-02" in review
            and "`$A1/$A2` read twice" in review
            and "Class-A cleanup, alongside" in review,
            "owner capture authorization drift")

    first = {
        "jiffy_bytes": list(read_exact("jiffy-1.bin", 2)),
        "d01a": read_exact("d01a-1.bin", 1)[0],
        "irq_vector": u16le(read_exact("irqvec-1.bin", 2)),
        "getin_vector": u16le(read_exact("getinvec-1.bin", 2)),
    }
    second = {
        "jiffy_bytes": list(read_exact("jiffy-2.bin", 2)),
        "d01a": read_exact("d01a-2.bin", 1)[0],
        "irq_vector": u16le(read_exact("irqvec-2.bin", 2)),
        "getin_vector": u16le(read_exact("getinvec-2.bin", 2)),
    }
    first["jiffy_word"] = first["jiffy_bytes"][0] << 8 | first["jiffy_bytes"][1]
    second["jiffy_word"] = second["jiffy_bytes"][0] << 8 | second["jiffy_bytes"][1]

    value: dict[str, Any] = {
        "format": "lisp65-c2.3-v1.3-link85-jiffy-split-readonly-capture-v1",
        "recorded_on": date.today().isoformat(),
        "status": "hardware-readonly-capture-jiffy-frozen-wait-boundary-attributed",
        "candidate_link": 85,
        "scope": {
            "access": "read-only-memory-dumps",
            "device": "/dev/ttyUSB1",
            "reset_before_capture": False,
            "keyboard_or_screenshot_before_capture": False,
            "product_bytes_changed": 0,
            "product_links_created": 0,
        },
        "capture_timing": {
            "first_tool_timestamp": "2026-08-02T17:22:54.637Z",
            "second_tool_timestamp": "2026-08-02T17:22:56.306Z",
            "nominal_explicit_delay_seconds": 1,
            "tool_timestamp_separation_seconds": 1.669,
        },
        "samples": {"first": first, "second": second},
        "binary_split": {
            "outcome": "jiffy-frozen",
            "live_boundary": "wait-before-read-line",
            "input_layer": "not-reached-not-tested",
            "mechanism": (
                "Ship released interrupts without arming the inherited KERNAL "
                "time base; D01A remained zero and A1/A2 did not advance, so "
                "the sample blocked in its leading (wait 1)."
            ),
            "fix_target": (
                "Ship boot initialization must establish and verify the time "
                "base rather than inherit it; the host lane must assert the "
                "same boot precondition."
            ),
        },
        "separate_latent_finding": {
            "address": "0x0091",
            "class": "Ship-RUNSTOP-assumption",
            "disposition": "separate-not-exercised-by-this-capture",
        },
        "bindings": {
            "owner_review": bind(REVIEW),
            "host_elf_attribution": bind(ATTRIBUTION),
            "capture_driver": bind(DRIVER),
            "m65_tool": bind(M65),
            "raw": {
                name: bind(CAPTURE / name)
                for name in (
                    "jiffy-1.bin", "d01a-1.bin", "irqvec-1.bin",
                    "getinvec-1.bin", "jiffy-2.bin", "d01a-2.bin",
                    "irqvec-2.bin", "getinvec-2.bin",
                )
            },
        },
        "verification": {
            "executions": 1,
            "mutations_rejected": 5,
        },
        "claim_limit": (
            "One owner-authorized read-only capture of the still-live Link-85 "
            "interactive wait state. It attributes this silence to the frozen "
            "pre-input jiffy and does not test GETIN, key-event, read-line, a "
            "product fix, a successor link, acceptance or release readiness."
        ),
    }
    audit(value)
    rejected = mutations(value)
    require(len(rejected) == 5 and set(rejected.values()) == {"rejected"},
            "mutation witness drift")
    value["verification"]["mutation_results"] = rejected
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    print(
        "c2-v13-link85-jiffy-split-capture: PASS "
        "jiffy=0x6400->0x6400 d01a=0 irq=0xf974 getin=0xf319 "
        "boundary=wait-before-read-line mutations=5"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CaptureError, OSError, ValueError, KeyError, TypeError,
            json.JSONDecodeError) as error:
        print(f"c2-v13-link85-jiffy-split-capture: FIRST RED: {error}")
        raise SystemExit(2)
