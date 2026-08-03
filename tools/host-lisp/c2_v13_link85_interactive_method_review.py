#!/usr/bin/env python3
"""Bind the host-side method review for Link-85 interactive input."""

from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
from subprocess import CalledProcessError
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent))
from elf_truth import ElfTruth, ElfTruthError  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
REVIEW = ROOT / "docs/planning/1.3-link84-closing-first-red-review.md"
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-link85-interactive-retry-first-red-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-link85-interactive-method-host-reading-receipt.json"
)
READ_LINE = ROOT / "lib/stdlib-read-line.lisp"
VM = ROOT / "src/vm.c"
SHIP_IO = ROOT / "products/runtime-core/ship_io.c"
WINDOW = ROOT / "src/c2_kernal_window.s"
RETRY_SESSION = ROOT / "scripts/c2-v13-link85-interactive-retry-hw.sh"
HUMAN_CONFIG = ROOT / "config/c2-ship-builder-v1-link85-interactive-human-test.json"
HUMAN_SESSION = ROOT / "scripts/c2-v13-link85-interactive-human-test-hw.sh"
CAPTURE = ROOT / "build/ship-builder/v13/link85-interactive-retry/run/ack-1.txt"
SHIP_ELF = ROOT / "build/ship-builder/v13/final-fleet-bank2/interactive.runtime.elf"
WORKBENCH_ELF = ROOT / (
    "build/c2.3/v1.3.0-candidate-product-link85-r1/final/"
    "lisp65-c2-substitution-linked.prg.elf"
)
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
DRIVER = Path(__file__).resolve()


class ReviewError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReviewError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, object]:
    require(path.is_file(), f"authority absent: {path}")
    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def text(path: Path) -> str:
    require(path.is_file(), f"authority absent: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def symbol_body(truth: ElfTruth, name: str) -> bytes:
    symbol = truth.symbol(name)
    require(symbol.bytes > 0, f"sized ELF symbol required: {name}")
    section = truth.section(symbol.section)
    data = truth.section_bytes(symbol.section)
    offset = symbol.value - section.address
    require(0 <= offset and offset + symbol.bytes <= len(data),
            f"ELF symbol outside section: {name}")
    return data[offset:offset + symbol.bytes]


def main() -> int:
    review = text(REVIEW)
    read_line = text(READ_LINE)
    vm = text(VM)
    ship_io = text(SHIP_IO)
    window = text(WINDOW)
    session = text(RETRY_SESSION)
    capture = text(CAPTURE)
    first_red = json.loads(text(FIRST_RED))

    require(
        "Interactive-row method review" in review
        and "one-minute" in review
        and "human test" in review,
        "owner method-review commission absent",
    )
    require(
        first_red["status"]
        == "FIRST-RED-Link85-single-character-ack-absent-owner-review",
        "interactive First Red authority drift",
    )
    require(
        "(row (- (car (cdr size)) 1))" in read_line
        and "(screen-put-char length row code 1)" in read_line,
        "read-line last-row viewport contract drift",
    )
    require(
        'grep -Fq "$expected" "$OUT/ack-$index.txt"' in session,
        "screen acknowledgement no longer scans the full text capture",
    )
    lines = capture.splitlines()
    require(len(lines) == 27, f"captured screen height drift: {len(lines)}")
    require(all(not line.strip() for line in lines),
            "captured screen is no longer wholly blank")

    require(
        "lisp65_ship_io_getin((uint8_t)mode)" in vm
        and "lisp_input_event(1u, 0u, &event)" in vm
        and "value = cbm_k_getin();" in ship_io
        and "$d60a" in window.lower()
        and "$d619" in window.lower(),
        "input-source contract drift",
    )

    ship_truth = ElfTruth.read(
        SHIP_ELF, llvm_readobj=READOBJ, include_section_data=True)
    workbench_truth = ElfTruth.read(
        WORKBENCH_ELF, llvm_readobj=READOBJ, include_section_data=True)
    ship_getin = ship_truth.symbol("__GETIN")
    ship_callprim = symbol_body(ship_truth, "vm_callprim")
    workbench_poll = workbench_truth.symbol("c2_kernal_event_poll")
    workbench_input = symbol_body(workbench_truth, "lisp_input_event")
    require(
        ship_getin.section == "Absolute"
        and ship_getin.value == 0xFFE4
        and "c2_kernal_event_poll" not in ship_truth.symbols_by_name
        and bytes((0x20, 0xE4, 0xFF)) in ship_callprim,
        "Ship GETIN composition proof drift",
    )
    require(
        workbench_poll.value == 0xE000
        and bytes((0x20, 0x00, 0xE0)) in workbench_input,
        "Workbench product-queue composition proof drift",
    )

    value = {
        "format": "lisp65-c2.3-v1.3-link85-interactive-method-host-reading-v1",
        "recorded_on": date.today().isoformat(),
        "status": "host-reading-complete-physical-keyboard-discriminator-required",
        "candidate_link": 85,
        "product_bytes_changed": 0,
        "product_links_created": 0,
        "visibility": {
            "read_line_echo_row": "screen-height-minus-one",
            "assert_scope": "all-captured-screen-lines",
            "captured_lines": len(lines),
            "last_row_in_scope": True,
            "visible_A_anywhere": False,
            "wrong-row_hypothesis": "refuted",
        },
        "input_compositions": {
            "ship": {
                "path": "CALLPRIM-60 -> lisp65_ship_io_getin -> KERNAL GETIN",
                "linked_jsr": "0xffe4",
                "product_queue_driver_linked": False,
            },
            "workbench": {
                "path": "CALLPRIM-60 -> lisp_input_event -> c2_kernal_event_poll",
                "queue": ["0xd60a", "0xd619"],
                "linked_driver": "0xe000",
            },
            "conclusion": (
                "Workbench virtual-key success does not prove that m65 -t "
                "feeds the standalone Ship KERNAL-GETIN path."
            ),
        },
        "disposition": {
            "next": "physical-keyboard-Ada-RETURN-human-test",
            "virtual_input_before_human_test": "forbidden",
            "green": "product-end-to-end-proved-virtual-transport-tooling-only",
            "silent": "product-read-line-failure",
        },
        "bindings": {
            "method_review": bind(REVIEW),
            "first_red": bind(FIRST_RED),
            "read_line": bind(READ_LINE),
            "vm": bind(VM),
            "ship_io": bind(SHIP_IO),
            "workbench_queue": bind(WINDOW),
            "retry_session": bind(RETRY_SESSION),
            "human_test_config": bind(HUMAN_CONFIG),
            "human_test_session": bind(HUMAN_SESSION),
            "host_reading_driver": bind(DRIVER),
            "captured_screen_text": {
                **bind(CAPTURE),
                "content_sha_is_bound_in_first_red": True,
            },
            "ship_elf": bind(SHIP_ELF),
            "workbench_elf": bind(WORKBENCH_ELF),
        },
        "claim_limit": (
            "This host reading refutes only the wrong-screen-region theory "
            "and proves that Ship and Workbench consume different physical "
            "input seams. It makes no interactive target or release claim."
        ),
    }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    print(
        "c2-v13-link85-interactive-method-review: PASS "
        "screen=all-27-lines-blank ship=GETIN workbench=D60A/D619 "
        "next=physical-keyboard"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReviewError, ElfTruthError, OSError, ValueError, KeyError,
            TypeError, json.JSONDecodeError, CalledProcessError) as error:
        print(f"c2-v13-link85-interactive-method-review: FIRST RED: {error}")
        raise SystemExit(2)
