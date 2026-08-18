#!/usr/bin/env python3
"""Attribute the sole root-card Red from its emitted WPLTO map."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v2.1-probe-oracle-root-card/wplto"
PREDECESSOR_BUILD = ROOT / "build/c2.3/v2.1-full-span-convergence-card/wplto"
MAP = BUILD / "resident-island-seed.prg.map"
PREDECESSOR_MAP = PREDECESSOR_BUILD / "resident-island-seed.prg.map"
LTO = BUILD / "resident-island-seed.prg.lto.o"
LINKER = BUILD / "c2-substitution.ld"
FINAL_RED = ARCH / "c2.3-v2.1-probe-oracle-root-card-final-red.json"
PREFLIGHT = ROOT / "build/c2.3/v2.1-probe-oracle-root-preflight/preflight.json"
RECEIPT = ARCH / "c2.3-v2.1-probe-oracle-root-card-red-attribution-receipt.json"

FORMAT = "lisp65-c2.3-v2.1-probe-oracle-root-card-red-attribution-v1"
STATUS = "FINAL-RED-ATTRIBUTED: WPLTO-WRAPPER-SHRINK-NEEDS-19-BYTE-FACADE-PAD"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


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


def map_rows(path: Path) -> list[dict[str, Any]]:
    pattern = re.compile(
        r"^\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+\d+\s+(.+?)\s*$")
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            rows.append({"vma": int(match.group(1), 16),
                         "lma": int(match.group(2), 16),
                         "bytes": int(match.group(3), 16),
                         "label": match.group(4)})
    return rows


def one(rows: list[dict[str, Any]], suffix: str) -> dict[str, Any]:
    exact = [row for row in rows if row["label"] == suffix]
    found = exact or [row for row in rows if row["label"].endswith(suffix)]
    require(len(found) == 1, f"map identity is not unique: {suffix}")
    return found[0]


def derive() -> dict[str, Any]:
    red = load(FINAL_RED)
    require(red.get("status") ==
            "FINAL RED: probe-oracle root card returns to owner"
            and red.get("retry_authorized") is False
            and red["attempt_accounting"] == {
                "WPLTO_runs": 1, "cards_authorized": 1,
                "cards_consumed": 1, "completion_runs": 0,
                "device_contacts": 0, "media_builds": 0,
                "product_link_attempts": 1},
            "root-card Final Red boundary drift")
    current = map_rows(MAP)
    old = map_rows(PREDECESSOR_MAP)
    current_facade = one(current, ".lisp65_c2_mapped_far_facade")
    old_facade = one(old, ".lisp65_c2_mapped_far_facade")
    current_entries = one(current, "(.lisp65_c2_mapped_far_facade.entries)")
    old_entries = one(old, "(.lisp65_c2_mapped_far_facade.entries)")
    current_ext = one(current, "ext_dma_read_or_abort")
    old_ext = one(old, "ext_dma_read_or_abort")
    current_c2 = one(current, "c2_dma_read_or_abort")
    old_c2 = one(old, "c2_dma_read_or_abort")
    current_text = one(current, ".text")
    old_text = one(old, ".text")
    linker = LINKER.read_text(encoding="utf-8")
    require(
        (current_facade["vma"], current_facade["bytes"]) == (0xB3B0, 79)
        and (old_facade["vma"], old_facade["bytes"]) == (0xB3B0, 98)
        and current_entries["bytes"] == old_entries["bytes"] == 52
        and (current_ext["bytes"], old_ext["bytes"]) == (35, 38)
        and (current_c2["bytes"], old_c2["bytes"]) == (27, 46)
        and current_text["vma"] + current_text["bytes"] == 0xB3AC
        and old_text["vma"] + old_text["bytes"] == 0xB3AF
        and "SIZEOF(.lisp65_c2_mapped_far_facade) == 98" in linker
        and "mapped far facade escaped its resident wall" in linker,
        "root-card emitted-map mechanism drift")
    require(not (BUILD / "resident-island-seed.prg").exists()
            and not (BUILD / "resident-island-seed.prg.elf").exists(),
            "failed seed link unexpectedly produced a product artifact")
    value = {
        "format": FORMAT, "recorded_on": "2026-08-16", "status": STATUS,
        "mechanism": {
            "class": "TARGET-SHAPED-PRICE-DIFFERS-FROM-REAL-WPLTO-EMISSION",
            "linker_assertion": "mapped far facade escaped its resident wall",
            "facade": {"address": "0xb3b0", "contract_bytes": 98,
                "Link112_bytes": old_facade["bytes"],
                "Link113_emitted_bytes": current_facade["bytes"],
                "missing_contract_padding_bytes": 98 - current_facade["bytes"]},
            "entry_trampolines": {"Link112_bytes": old_entries["bytes"],
                "Link113_bytes": current_entries["bytes"], "changed": False},
            "wrappers": {
                "ordinary": {"priced_bytes": 37,
                    "Link112_bytes": old_ext["bytes"],
                    "actual_WPLTO_bytes": current_ext["bytes"]},
                "mapped_facade": {"priced_bytes": 29,
                    "Link112_bytes": old_c2["bytes"],
                    "actual_WPLTO_bytes": current_c2["bytes"]},
                "actual_execution_delta_bytes":
                    (current_ext["bytes"] - old_ext["bytes"]) +
                    (current_c2["bytes"] - old_c2["bytes"]),
            },
            "ordinary_text": {"Link112_end_exclusive": "0xb3af",
                "Link113_end_exclusive": "0xb3ac",
                "additional_free_bytes": 3},
        },
        "narrow_repair": {
            "form": "explicit non-executed mapped-facade contract padding",
            "padding_bytes": 19,
            "semantic_bytes_changed": 0,
            "reader_or_vector_growth_bytes": 0,
            "expected_execution_delta_bytes": -22,
            "authorized": False,
            "replacement_card_authorized": False,
        },
        "preflight_lesson": {
            "target_shaped_micro_assembly_is_pricing_not_emission_truth": True,
            "actual_WPLTO_map_is_emission_truth": True,
            "product_card_correctly_rejected_underfilled_fixed_contract": True,
        },
        "execution_accounting": {"cards_authorized": 1,
            "cards_consumed": 1, "WPLTO_runs": 1,
            "product_link_attempts": 1, "product_artifacts": 0,
            "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "authority": {"Final_Red": bind(FINAL_RED), "preflight": bind(PREFLIGHT),
            "candidate_map": bind(MAP), "predecessor_map": bind(PREDECESSOR_MAP),
            "candidate_LTO": bind(LTO), "linker": bind(LINKER),
            "checker": bind(Path(__file__))},
        "next": "owner disposition; no retry or replacement card is implied",
        "claim_limit": "Desk attribution only; the sole card remains consumed.",
    }
    validate(value)
    return value


def validate(value: dict[str, Any]) -> None:
    mechanism = value["mechanism"]
    repair = value["narrow_repair"]
    require(value.get("format") == FORMAT and value.get("status") == STATUS,
            "root-card attribution identity drift")
    require(mechanism["facade"]["missing_contract_padding_bytes"] == 19
            and mechanism["wrappers"]["actual_execution_delta_bytes"] == -22
            and mechanism["ordinary_text"]["additional_free_bytes"] == 3,
            "emitted size attribution drift")
    require(repair == {"form":
                "explicit non-executed mapped-facade contract padding",
            "padding_bytes": 19, "semantic_bytes_changed": 0,
            "reader_or_vector_growth_bytes": 0,
            "expected_execution_delta_bytes": -22,
            "authorized": False, "replacement_card_authorized": False},
            "unauthorized repair drift")
    require(value["execution_accounting"]["product_artifacts"] == 0
            and value["execution_accounting"]["cards_consumed"] == 1
            and value["execution_accounting"]["device_contacts"] == 0,
            "card/accounting boundary drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "hide-padding": lambda x: x["mechanism"]["facade"].update(
            missing_contract_padding_bytes=0),
        "inherit-price": lambda x: x["mechanism"]["wrappers"].update(
            actual_execution_delta_bytes=-18),
        "hide-text-space": lambda x: x["mechanism"]["ordinary_text"].update(
            additional_free_bytes=0),
        "change-pad": lambda x: x["narrow_repair"].update(padding_bytes=17),
        "invent-semantics": lambda x: x["narrow_repair"].update(
            semantic_bytes_changed=1),
        "authorize-repair": lambda x: x["narrow_repair"].update(authorized=True),
        "authorize-card": lambda x: x["narrow_repair"].update(
            replacement_card_authorized=True),
        "invent-product": lambda x: x["execution_accounting"].update(
            product_artifacts=1),
        "refund-card": lambda x: x["execution_accounting"].update(
            cards_consumed=0),
        "touch-device": lambda x: x["execution_accounting"].update(
            device_contacts=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate(candidate)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases), "root-card attribution mutation survived")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check", "selftest"))
    action = parser.parse_args().action
    value = derive()
    value["mutations_rejected"] = mutations(value)
    if action == "record":
        RECEIPT.write_bytes(canonical(value))
    elif action == "check":
        require(load(RECEIPT) == value, "root-card attribution receipt stale")
    else:
        require(len(value["mutations_rejected"]) == 10,
                "root-card attribution mutation count drift")
    print(f"probe-oracle root card attribution: PASS action={action} "
          f"pad=19 delta=-22 mutations=10")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"probe-oracle root card attribution: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
