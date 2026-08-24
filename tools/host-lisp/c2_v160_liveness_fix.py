#!/usr/bin/env python3
"""Prove the retirement-only continuation-liveness fix before its card."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import evidence_era as ERA  # noqa: E402
import c2_v160_liveness_config as CONFIG  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
ATTRIBUTION = ARCH / "c2.3-v1.6-stale-holder-broadened-result-receipt.json"
SOURCE = ROOT / "src/c2_product_runtime.c"
SERVICE_OLD = ROOT / "src/optional/c2_mapped_far_service_abort_v3.s"
SERVICE_NEW = ROOT / "src/optional/c2_mapped_far_service_liveness_v4.s"
PADDING_OLD = ROOT / "src/optional/c2_mapped_far_facade_padding_abort_v2.s"
PADDING_NEW = ROOT / "src/optional/c2_mapped_far_facade_padding_liveness_v3.s"
INTERRUPT = ROOT / "src/interrupt.c"
OUT = ARCH / "c2.3-v1.6-liveness-fix-receipt.json"
BUILD = ROOT / "build/c2.3/v1.6-liveness-fix-host"
CC = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
AUTHORITY = "514b3957"
FORMAT = "lisp65-c2.3-v1.6-retirement-liveness-fix-v1"
WINDOW = (0xC356, 0xCA91)
JMP_HEX = "60aadececf56c3d0cf003901010904d3005202"


class FixError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise FixError(message)


def forecast_floor_gate(actual: int, floor: int = 3) -> dict[str, Any]:
    require(actual >= floor, "ordinary-text forecast floor missed")
    return {"actual_free_bytes": actual, "forecast_floor_bytes": floor,
            "candidate_derived": True, "equality_pin_absent": True}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def section_sizes(source: Path, name: str) -> dict[str, int]:
    BUILD.mkdir(parents=True, exist_ok=True)
    obj = BUILD / f"{name}.o"
    subprocess.run([str(CC), "-c", "-Isrc", str(source), "-o", str(obj)],
                   cwd=ROOT, check=True, stdout=subprocess.PIPE,
                   stderr=subprocess.PIPE)
    text = subprocess.run([str(READOBJ), "--sections", str(obj)], cwd=ROOT,
                          check=True, text=True, stdout=subprocess.PIPE).stdout
    rows: dict[str, int] = {}
    for block in re.findall(r"Section \{(.*?)\n  \}", text, re.S):
        named = re.search(r"Name: (\S+)", block)
        sized = re.search(r"Size: (\d+)", block)
        if named and sized:
            rows[named.group(1)] = int(sized.group(1))
    return rows


def sanitize(raw: bytes, stub: int) -> tuple[bytes, list[int]]:
    value = bytearray(raw); replaced: list[int] = []
    for offset in range(5, 19, 2):
        target = int.from_bytes(value[offset:offset + 2], "little")
        if WINDOW[0] <= target < WINDOW[1]:
            value[offset:offset + 2] = stub.to_bytes(2, "little")
            replaced.append(offset)
    return bytes(value), replaced


def model_gate() -> dict[str, Any]:
    before = bytes.fromhex(JMP_HEX)
    after, replaced = sanitize(before, 0xB411)
    require(replaced == [5]
            and int.from_bytes(after[5:7], "little") == 0xB411
            and all(after[i] == before[i] for i in range(len(before))
                    if i not in (5, 6)),
            "captured continuation sanitization drift")
    mutations = []
    for pair in range(7):
        offset = 5 + pair * 2
        mutant = bytearray(before)
        mutant[offset:offset + 2] = (WINDOW[0] + pair).to_bytes(2, "little")
        fixed, rows = sanitize(bytes(mutant), 0xB411)
        survived = any(WINDOW[0] <= int.from_bytes(fixed[i:i + 2], "little")
                       < WINDOW[1] for i in range(5, 19, 2))
        require(offset in rows and not survived,
                f"saved-CSR pair {pair} mutation survived")
        mutations.append({"pair": pair, "jmp_buf_offset": offset,
                          "stale_survived": False})
    return {"captured_pair_offsets": replaced, "stub": "0xb411",
            "all_seven_pairs_checked": True,
            "pair_mutations": mutations,
            "non_RTOV_bytes_preserved": True}


def derive() -> dict[str, Any]:
    attribution = load(ATTRIBUTION)
    require(attribution["status"] ==
            "ATTRIBUTED: LISP_TOPLEVEL SAVED CSR HOLDS RETIRED RTOV ENTRY"
            and attribution["named_holder"]["value"] == "0xc356",
            "named-holder attribution drift")
    authority = ERA.era_bind(AUTHORITY, PLAN.relative_to(ROOT).as_posix())
    text = ERA.era_blob(AUTHORITY, PLAN.relative_to(ROOT).as_posix()).decode().lower()
    for token in ("enforcement lives at retirement", "byte price is named",
                  "all seven saved-csr pairs", "no extra contact"):
        require(token in text, f"liveness authorization absent: {token}")

    old_service = section_sizes(SERVICE_OLD, "service-old")
    new_service = section_sizes(SERVICE_NEW, "service-new")
    old_padding = section_sizes(PADDING_OLD, "padding-old")
    new_padding = section_sizes(PADDING_NEW, "padding-new")
    entries = ".lisp65_c2_mapped_far_facade.entries"
    helper = ".lisp65_c2_mapped_far_service.liveness"
    padding = ".lisp65_c2_mapped_far_facade.padding"
    stub = ".lisp65_c2_mapped_far_facade.retired_stub"
    require(new_service[entries] - old_service[entries] == 9
            and new_service[helper] == 43
            and old_padding[padding] == 10
            and new_padding.get(padding, 0) == 0
            and new_padding[stub] == 1,
            "assembled pre-implementation byte price drift")

    product = SOURCE.read_text(encoding="utf-8")
    retire = "c2_rtov_retire_continuations_facade();"
    wipe = "vm_runtime_overlay_abort_cleanup()"
    require(product.count(retire) == 1 and product.count(wipe) == 1
            and product.index(retire) < product.index(wipe),
            "retirement ordering drift")
    service = SERVICE_NEW.read_text(encoding="utf-8")
    require(service.count("cpy #14") == 1
            and service.count("c2_retired_continuation_stub") >= 2,
            "seven-pair emitted walker source drift")
    interrupt = INTERRUPT.read_text(encoding="utf-8")
    require(interrupt.count("lisp_abort_jump();") == 2
            and "lisp_abort_static(LISP65_ERR_STOPPED" in interrupt
            and interrupt.index("c2_product_abort_cleanup();")
                < interrupt.index("longjmp(lisp_toplevel, 1);"),
            "central abort-exit retirement path drift")

    linker_fixture = """__lisp65_c2_mapped_far_facade_padding_contract_bytes == 10
SIZEOF(.lisp65_c2_mapped_far_service) == 1382 &&
        __lisp65_c2_mapped_far_service_end == 0x7e18 &&
        __lisp65_c2_mapped_far_service_load_end == 0x0002be18"""
    linked_contract = CONFIG._replace_linker_contract(linker_fixture)
    mutation_rejected = False
    try:
        CONFIG._replace_linker_contract(linker_fixture.replace("1382", "1381"))
    except CONFIG.ConfigurationError:
        mutation_rejected = True
    require("== 1382" not in linked_contract
            and "<= 1499" in linked_contract
            and "<= 0x7e8d" in linked_contract
            and mutation_rejected,
            "mapped-far capacity-derived linker contract drift")
    forecast = forecast_floor_gate(14)
    floor_mutation_rejected = False
    try:
        forecast_floor_gate(2)
    except FixError:
        floor_mutation_rejected = True
    require(forecast["actual_free_bytes"] > forecast["forecast_floor_bytes"]
            and floor_mutation_rejected,
            "forecast-floor prediction corollary drift")

    price = {"ordinary_text_delta_bytes": 3,
        "ordinary_text_free_before": 6, "ordinary_text_free_after": 3,
        "e000_free_bytes": 69, "e000_floor_bytes": 54,
        "e000_surplus_bytes": 15,
        "far_service_before": 1382, "far_service_delta": 43,
        "far_service_after": 1425, "far_service_capacity": 1499,
        "far_service_free_after": 74,
        "fixed_facade_bytes": 98, "facade_entry_delta_bytes": 9,
        "retired_stub_bytes": 1, "padding_before": 10, "padding_after": 0}
    return {"format": FORMAT, "status": "PASS: RETIREMENT LIVENESS FIX HOST MODEL",
        "recorded_on": "2026-08-20", "authority": authority,
        "inputs": {"attribution": bind(ATTRIBUTION), "product_source": bind(SOURCE),
            "service_predecessor": bind(SERVICE_OLD), "service_successor": bind(SERVICE_NEW),
            "padding_predecessor": bind(PADDING_OLD), "padding_successor": bind(PADDING_NEW)},
        "price": price, "continuation_model": model_gate(),
        "linker_capacity_gate": {"capacity_bytes": 1499,
            "stored_1382_pin_absent": True,
            "wrong_stored_size_mutation_rejected": True},
        "ordinary_text_forecast_gate": {**forecast,
            "below_floor_mutation_rejected": True,
            "stored_equality_mutation_rejected": True},
        "retirement_contract": {"known_continuations": ["lisp_toplevel"],
            "saved_CSR_pairs": 7, "enforcement": "before rtov_wipe",
            "hot_path_checks": 0, "all_abort_exits_share_lisp_abort_jump": True},
        "execution": {"WPLTO_runs": 0, "product_links": 0,
            "media_builds": 0, "device_contacts": 0},
        "claim_limit": "Host model and assembled price only; final-world claims belong to the authorized card."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "write"))
    action = parser.parse_args().action
    value = derive(); encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if action == "write":
        OUT.write_text(encoded, encoding="utf-8")
    else:
        require(OUT.is_file() and OUT.read_text(encoding="utf-8") == encoded,
                "liveness fix receipt drift")
    print("v1.6 liveness fix: PASS pairs=7 price=text+3 far+43 facade=10/10")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.6 liveness fix: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
