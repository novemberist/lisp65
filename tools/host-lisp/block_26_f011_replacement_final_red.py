#!/usr/bin/env python3
"""Freeze Card 2's replacement final pair at its transitive MAP red."""

from __future__ import annotations

import argparse
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

from elf_truth import ElfTruth  # noqa: E402
import block_26_f011_replacement_product_card as CARD  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = ARCH / "block-2.6-card2-f011-product-r2-final-red.json"
REPORT = ROOT / "docs/planning/2.6-card2-f011-product-r2-final-red.md"
FORMAT = "lisp65-block-2.6-card2-f011-product-r2-final-red-v1"
STATUS = "FROZEN: CARD 2 REPLACEMENT STOPPED ON TRANSITIVE MAP NESTING"


class RedError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RedError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def derive() -> dict[str, Any]:
    CARD.patch_card()
    CARD.CARD.configure()
    truth = ElfTruth.read(CARD.ELF, llvm_readobj=CARD.READOBJ,
                          include_section_data=True)
    owners = CARD.bounded_owners(truth)
    bank = CARD.composed_bank2()
    nesting = CARD.NESTING.analyze(CARD.ELF)
    expected_path = ["disk_source_refill_far", "ext_disk_get",
        "ext_dma_read_or_abort", "lisp_abort_code", "lisp_abort_symbol",
        "c2_product_abort_cleanup", "c2_rtov_retire_continuations_facade"]
    require(len(nesting["violations"]) == 2
            and {row["terminal"] for row in nesting["violations"]} == {
                "c2_mapped_far_enter", "c2_mapped_far_leave"}
            and all(row["path"][:-1] == expected_path
                    for row in nesting["violations"]),
            "replacement nesting red changed identity")
    difference = load(CARD.DIFFERENCE)
    require(difference["unexplained_members"] == 0,
            "replacement attribution retained a remainder")
    return {"format": FORMAT, "recorded_on": "2026-09-03", "status": STATUS,
        "authority": CARD.authority(),
        "artifact_boundary": {"ELF": bind(CARD.ELF), "PRG": bind(CARD.PRG),
            "LTO_object": bind(Path(str(CARD.PRG) + ".lto.o")),
            "link_map": bind(Path(str(CARD.PRG) + ".map")),
            "disposition": "FROZEN-UNQUALIFIED-PRODUCT-EVIDENCE"},
        "difference": bind(CARD.DIFFERENCE),
        "attribution": {"classification": "real-product-nesting-defect",
            "mechanism": ("mapped disk_source_refill_far reads the copied DIR "
                "link through ext_disk_get; its fail-closed DMA path may abort "
                "through cleanup, whose continuation retirement enters and "
                "leaves the MAP arena a second time"),
            "direct_edge": ["disk_source_refill_far", "ext_disk_get"],
            "violations": nesting["violations"],
            "unexplained_members": 0},
        "final_link_facts": {"bounded_owners": owners,
            "composed_bank2": {"overlaps": bank["overlaps"],
                "largest_contiguous_hole": bank["largest_contiguous_hole"]},
            "mapped_F011_bytes": truth.section(
                ".lisp65_c2_mapped_f011_cold").bytes,
            "emitted_function_bytes": {name: truth.symbol(name).bytes for name in (
                "disk_source_fetch", "disk_source_refill_far", "disk_source_refill")},
            "packed_link": {"symbol": "disk_source_link",
                "bytes": truth.symbol("disk_source_link").bytes},
            "all_capacity_floors_green": owners["all_floors_green"]},
        "projection_to_final": {"ordinary_text_delta_projected": 11,
            "ordinary_text_delta_r1_to_r2": 6,
            "resident_island_delta_projected": 82,
            "resident_island_delta_r1_to_r2": 85,
            "mapped_F011_delta_projected": 86,
            "mapped_F011_delta_r1_to_r2": 84,
            "BSS_margin_r1_to_r2": [3, 6]},
        "qualification": {"scope_runs": 0, "acceptance_runs": 0,
            "DWX_prefilter_runs": 0, "reason": "stopped before Scope"},
        "attempt_accounting": {"card_total": {"WPLTO_runs": 2,
                "product_link_attempts": 2, "completed_product_links": 1},
            "replacement": {"WPLTO_runs": 1, "product_link_attempts": 1,
                "completed_product_links": 1},
            "media_builds": 0, "device_contacts": 0},
        "next": "reviewer/owner decision; no third link is authorized"}


def report(value: dict[str, Any]) -> str:
    owners = value["final_link_facts"]["bounded_owners"]
    violations = value["attribution"]["violations"]
    return f"""# Block 2.6 Card 2 — replacement final red

Status: **{value['status']}**

The packed state itself lands exactly as priced: `disk_source_link` is two
bytes, ordinary BSS recovers from the r1 margin of 3 to **{owners['ordinary_BSS']['margin_bytes']} bytes**
against the five-byte floor. Ordinary text leaves
**{owners['ordinary_text']['margin_bytes']} bytes** against 32; resident Island
plus annex leaves **{owners['resident_island']['margin_bytes']} bytes** against
its named five-byte floor (including a {owners['resident_island']['alignment_gap_bytes']}-byte alignment gap).
ZP and NOLOAD remain in bounds, the composed Bank-2 map is disjoint, and the
packed link validity model rejects every stale word.

The replacement nevertheless stops before Scope on a real product defect.
`disk_source_refill_far` is a mapped tenant but calls `ext_disk_get` after the
sector copy. The fail-closed read reaches abort cleanup and then
`c2_rtov_retire_continuations_facade`, which can reach both MAP terminals:

- `{ ' -> '.join(violations[0]['path']) }`
- `{ ' -> '.join(violations[1]['path']) }`

Capacity therefore is not the blocker; transitive mapping lifetime is. The
final ELF/PRG pair is frozen unqualified evidence. Across Card 2 the run count
is two WPLTOs, two link attempts and one completed but unqualified pair; Scope,
Acceptance, DWX, media and device counts remain zero. No third link is
authorized.
"""


def validate(value: dict[str, Any]) -> None:
    current = derive()
    require(value == current and value["status"] == STATUS
            and value["final_link_facts"]["all_capacity_floors_green"] is True
            and value["final_link_facts"]["bounded_owners"][
                "ordinary_BSS"]["margin_bytes"] == 6
            and value["final_link_facts"]["bounded_owners"][
                "resident_island"]["margin_bytes"] >= 5
            and len(value["attribution"]["violations"]) == 2
            and value["attribution"]["unexplained_members"] == 0
            and value["qualification"]["scope_runs"] == 0
            and value["attempt_accounting"]["device_contacts"] == 0,
            "Card-2 replacement final-red receipt drift")


def write() -> None:
    require(not RECEIPT.exists() and not REPORT.exists(),
            "Card-2 replacement final red is one-shot")
    value = derive()
    RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(report(value), encoding="utf-8")
    validate(value)
    print("Block 2.6 Card 2 replacement: FINAL RED nesting=2 floors=green scope=0")


def check() -> None:
    value = load(RECEIPT)
    validate(value)
    require(REPORT.is_file() and REPORT.read_text(encoding="utf-8") == report(value),
            "Card-2 replacement final-red report drift")
    print("Block 2.6 Card 2 replacement: FINAL RED CHECK nesting=2 scope=0")


def selftest() -> None:
    value = load(RECEIPT)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "nesting-hidden": lambda row: row["attribution"].update({"violations": []}),
        "capacity-misreported": lambda row: row["final_link_facts"].update(
            {"all_capacity_floors_green": False}),
        "remainder-hidden": lambda row: row["attribution"].update(
            {"unexplained_members": 1}),
        "scope-overclaimed": lambda row: row["qualification"].update(
            {"scope_runs": 1}),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except (RedError, RuntimeError, KeyError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "Card-2 final-red mutation survived")
    print(f"Block 2.6 Card 2 replacement: FINAL RED SELFTEST mutations={len(rejected)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    action = parser.parse_args().action
    {"write": write, "check": check, "selftest": selftest}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RedError, RuntimeError, OSError, ValueError, KeyError) as error:
        print(f"Block 2.6 Card 2 replacement red: FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
