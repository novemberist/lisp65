#!/usr/bin/env python3
"""Prepare, record and close the bundled Link-69 defstruct hardware session."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import repl_screen_check as SCREEN  # noqa: E402
CONFIG = ROOT / "config/c2.2-defstruct-link69-hardware-session.json"
LINK = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link69-defstruct-foundations-structural-receipt.json")
WPLTO = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-defstruct-foundations-wplto-receipt.json")
FOUNDATIONS = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-defstruct-foundations-gate-receipt.json")
MANIFEST = ROOT / (
    "build/post-promotion/link69-defstruct-foundations/"
    "canonical-product-manifest.json")
OUT = ROOT / "build/post-promotion/link69-defstruct-foundations/hardware-session"
DEPLOYMENT = OUT / "deployment.json"
OBSERVATIONS = OUT / "observed-rows.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link69-require-defstruct-hardware-receipt.json")
HARNESS_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link69-defstruct-hardware-harness-first-red.json")
HARNESS_OUTPUT_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link69-defstruct-hardware-oracle-first-red.json")
ROLE_ADDRESS = {
    "c2d-v6-code-plane": 0x00050000,
    "c2-two-record-boot-stage": 0x00058500,
    "c2-session-family-region-0": 0x08000000,
    "c2-product-shelf": 0x08100000,
    "c2-boot-family": 0x08200000,
    "c2-session-family-region-1": 0x08300000,
    "c2-kernal-window": 0x087FE000,
}
WORKBENCH_BANK5_LAYOUT = {
    "namepool_start": 0xC680,
    "symval_start": 0xEE60,
    "nameoff_start": 0xF440,
    "symfn_start": 0xFA20,
    "symbol_capacity": 752,
}
REQUIRE_TRANSIENT_VALUE_CELLS = (
    "*require-visited*",
    "*require-visiting*",
    "*require-order*",
)


class HardwareError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise HardwareError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"evidence absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def write(path: Path, value: dict[str, Any]) -> None:
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
    temporary.replace(path)


def authority() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    config = load(CONFIG)
    link = load(LINK)
    wplto = load(WPLTO)
    foundations = load(FOUNDATIONS)
    manifest = load(MANIFEST)
    candidate = config["candidate"]
    require(
        config["status"] == "owner-authorized-bundled-hardware-not-run"
        and link["status"].endswith("hardware-not-run")
        and link["product"]["sha256"] == candidate["product_sha256"]
        and link["ELF"]["sha256"] == candidate["elf_sha256"]
        and manifest["identity"]["resident_prg_sha256"]
            == candidate["product_sha256"]
        and manifest["identity"]["linked_elf_sha256"]
            == candidate["elf_sha256"]
        and foundations["media"]["D81"]["sha256"]
            == candidate["d81_sha256"]
        and wplto["session_service_gate"]["host"]["busy_window"]
            == ("c2-intern-session-service-busy: PASS bytes=1792 "
                "transport=ERR_BUSY entry=NOT_RUN "
                "window=byte-identical family-negatives=4"),
        "Link-69 hardware authority drift")
    rows = manifest["artifacts"]
    roles = {row["role"]: row for row in rows}
    require(len(rows) == len(roles) == 14, "Link-69 role inventory drift")
    for role, row in roles.items():
        path = ROOT / row["path"]
        require(
            path.is_file() and path.stat().st_size == row["bytes"]
            and sha(path) == row["sha256"],
            f"Link-69 role byte drift: {role}")
    return config, roles


def prepare() -> None:
    require(not OUT.exists() and not RECEIPT.exists(),
            "Link-69 hardware session is one-shot")
    config, roles = authority()
    preloads = [
        {**roles[role], "address": f"0x{address:08x}"}
        for role, address in ROLE_ADDRESS.items()
    ]
    spans = {
        "c2d_before_boot_stage":
            ROLE_ADDRESS["c2d-v6-code-plane"]
            + roles["c2d-v6-code-plane"]["bytes"]
            <= ROLE_ADDRESS["c2-two-record-boot-stage"],
        "session_before_shelf":
            ROLE_ADDRESS["c2-session-family-region-0"]
            + roles["c2-session-family-region-0"]["bytes"]
            <= ROLE_ADDRESS["c2-product-shelf"],
        "shelf_before_boot":
            ROLE_ADDRESS["c2-product-shelf"]
            + roles["c2-product-shelf"]["bytes"]
            <= ROLE_ADDRESS["c2-boot-family"],
        "boot_before_region1":
            ROLE_ADDRESS["c2-boot-family"]
            + roles["c2-boot-family"]["bytes"]
            <= ROLE_ADDRESS["c2-session-family-region-1"],
        "region1_before_window":
            ROLE_ADDRESS["c2-session-family-region-1"]
            + roles["c2-session-family-region-1"]["bytes"]
            <= ROLE_ADDRESS["c2-kernal-window"],
        "window_ends_at_attic_limit":
            ROLE_ADDRESS["c2-kernal-window"]
            + roles["c2-kernal-window"]["bytes"] == 0x08800000,
    }
    require(all(spans.values()), "Link-69 preload span overlap")
    media = load(FOUNDATIONS)["media"]["D81"]
    value = {
        "format": "lisp65-c2.2-link69-defstruct-deployment-v1",
        "status": "ready-one-bundled-hardware-session",
        "product": {**roles["c2-resident-prg"], "address": "0x00002001"},
        "elf": roles["linked-product-elf"],
        "media": media,
        "remote_media": "L69DEF.D81",
        "preloads": preloads,
        "span_checks": spans,
        "rows": config["rows"],
        "structural_busy_fixture":
            load(WPLTO)["session_service_gate"]["host"]["busy_window"],
        "authority": {
            "config": bind(CONFIG),
            "link": bind(LINK),
            "WPLTO": bind(WPLTO),
            "foundations": bind(FOUNDATIONS),
            "manifest": bind(MANIFEST),
            "driver": bind(Path(__file__).resolve()),
        },
        "execution_accounting": {"new_product_links": 0, "hardware_runs": 0},
    }
    OUT.mkdir(parents=True)
    write(DEPLOYMENT, value)
    write(OBSERVATIONS, {
        "format": "lisp65-c2.2-link69-defstruct-observations-v1",
        "status": "hardware-not-started",
        "rows": [],
    })
    print(
        "c2-defstruct-link69-hw: PREPARE PASS "
        f"rows={len(config['rows'])} product={config['candidate']['product_sha256']} "
        "hardware=not-run")


def record(row_id: str, screen: Path) -> None:
    if not screen.is_absolute():
        screen = ROOT / screen
    config, _ = authority()
    rows = config["rows"]
    observations = load(OBSERVATIONS)
    position = len(observations["rows"])
    require(position < len(rows), "all hardware rows are already recorded")
    expected = rows[position]
    require(row_id == expected["id"], "hardware row order drift")
    try:
        SCREEN.check_latest_result(
            screen, expected["form"], expected["expect"])
    except SCREEN.CheckError as error:
        raise HardwareError(
            f"row screen is not a clean expected result: "
            f"{row_id}: {error.message}") from error
    observations["rows"].append({
        **expected,
        "screen": bind(screen),
        "status": "passed-exact-screen-result",
    })
    observations["status"] = (
        "hardware-complete-pending-finalize"
        if len(observations["rows"]) == len(rows)
        else "hardware-in-progress")
    write(OBSERVATIONS, observations)
    print(
        f"c2-defstruct-link69-hw: ROW PASS "
        f"{len(observations['rows'])}/{len(rows)} id={row_id}")


def require_transient_cells(bank5: bytes) -> dict[str, tuple[int, int]]:
    layout = WORKBENCH_BANK5_LAYOUT
    require(len(bank5) == 65536, "complete Bank-5 capture required")
    cells: dict[str, tuple[int, int]] = {}
    for index in range(layout["symbol_capacity"]):
        at = layout["nameoff_start"] + index * 2
        name_offset = int.from_bytes(bank5[at:at + 2], "little")
        start = layout["namepool_start"] + name_offset
        if not layout["namepool_start"] <= start < layout["symval_start"]:
            continue
        end = bank5.find(b"\0", start, layout["symval_start"])
        if end < 0:
            continue
        try:
            name = bank5[start:end].decode("ascii")
        except UnicodeDecodeError:
            continue
        if name in REQUIRE_TRANSIENT_VALUE_CELLS:
            require(name not in cells, f"duplicate resolver symbol: {name}")
            cells[name] = (index, layout["symval_start"] + index * 2)
    require(
        set(cells) == set(REQUIRE_TRANSIENT_VALUE_CELLS),
        "resolver transient-cell inventory drift")
    return cells


def compare_repeat(name: str) -> dict[str, Any]:
    require(name in ("first-repeat", "post-use-repeat"),
            "unknown require-repeat pair")
    before = OUT / f"{name}-before-bank5.bin"
    after = OUT / f"{name}-after-bank5.bin"
    require(before.is_file() and after.is_file(),
            f"require-repeat capture absent: {name}")
    old = before.read_bytes()
    new = after.read_bytes()
    require(len(old) == len(new) == 65536,
            f"require-repeat capture width drift: {name}")
    old_cells = require_transient_cells(old)
    new_cells = require_transient_cells(new)
    require(old_cells == new_cells,
            f"resolver transient-cell coordinates drift: {name}")
    allowed = {
        offset + byte
        for _, offset in old_cells.values()
        for byte in range(2)
    }
    changed = [offset for offset, pair in enumerate(zip(old, new))
               if pair[0] != pair[1]]
    forbidden = [offset for offset in changed if offset not in allowed]
    if forbidden:
        raise HardwareError(
            f"require idempotence changed contracted Bank-5 byte "
            f"0x{forbidden[0]:04x}: {name}")
    result = {
        "id": name,
        "before": bind(before),
        "after": bind(after),
        "comparison":
            "byte-identical-complete-Bank5-except-three-named-"
            "resolver-transient-value-cells",
        "changed_offsets": [f"0x{offset:04x}" for offset in changed],
        "allowed_transient_cells": {
            cell_name: {
                "symbol_index": index,
                "Bank5_offset": f"0x{offset:04x}",
                "before_obj": f"0x{int.from_bytes(old[offset:offset + 2], 'little'):04x}",
                "after_obj": f"0x{int.from_bytes(new[offset:offset + 2], 'little'):04x}",
            }
            for cell_name, (index, offset) in old_cells.items()
        },
        "contracted_immutable_bytes": len(old) - len(allowed),
        "status": "passed-generation-idempotence-no-product-state-drift",
    }
    if changed:
        write(HARNESS_FIRST_RED, {
            "format":
                "lisp65-c2.2-require-idempotence-oracle-first-red-v1",
            "recorded_on": "2026-07-27",
            "status":
                "resolved-harness-overreach-product-state-byte-identical",
            "first_red": {
                "oracle":
                    "byte-identical-complete-Bank5",
                "reason":
                    "Bank 5 also owns Lisp symbol-value cells; the resolver "
                    "rebuilds three explicitly temporary plan values while "
                    "deriving loaded identity from unchanged C2D rows.",
            },
            "adjudication": result,
            "product_bytes_changed": 0,
            "new_product_links": 0,
        })
    print(
        "c2-defstruct-link69-hw: IDEMPOTENCE PASS "
        f"id={name} immutable={result['contracted_immutable_bytes']} "
        f"transient-drift={len(changed)}")
    return result


def finalize() -> None:
    config, roles = authority()
    deployment = load(DEPLOYMENT)
    observations = load(OBSERVATIONS)
    require(
        [row["id"] for row in observations["rows"]]
            == [row["id"] for row in config["rows"]],
        "hardware row closure incomplete")
    media = ROOT / deployment["media"]["path"]
    uploaded = OUT / "uploaded-media-readback.d81"
    core = OUT / "device-core-id.bin"
    require(
        uploaded.is_file() and uploaded.read_bytes() == media.read_bytes()
        and core.is_file() and core.stat().st_size == 4,
        "hardware media/core evidence drift")
    for item in deployment["preloads"]:
        source = ROOT / item["path"]
        readback = OUT / f"readback-{source.name}"
        require(
            readback.is_file() and readback.read_bytes() == source.read_bytes(),
            f"hardware preload readback differs: {item['role']}")
    repeat_pairs = []
    for name in ("first-repeat", "post-use-repeat"):
        repeat_pairs.append(compare_repeat(name))
    wplto = load(WPLTO)
    receipt = {
        "format": "lisp65-c2.2-link69-require-defstruct-hardware-v1",
        "recorded_on": "2026-07-27",
        "status": "passed-Link69-require-defstruct-on-hardware",
        "candidate": {
            "link": 69,
            "product": roles["c2-resident-prg"],
            "ELF": roles["linked-product-elf"],
            "media": bind(media),
        },
        "device": {
            "core_identity": {**bind(core), "hex": core.read_bytes().hex()},
            "physical_devices": 1,
        },
        "results": {
            "rows": observations["rows"],
            "require_dependency_order": ["place", "defstruct"],
            "require_same_generation_idempotence": repeat_pairs,
            "defstruct": {
                "constructor": "(point 3 4)",
                "accessors": [3, 4],
                "predicate": "t",
                "copy": "(point 3 4)",
                "functional_update": "(point 3 8)",
                "canonical_place_mutation": "(point 9 4)",
            },
            "service_busy_closure":
                wplto["session_service_gate"]["host"]["busy_window"],
            "service_busy_source_mutations":
                wplto["session_service_gate"][
                    "source_mutations_rejected"],
        },
        "evidence": {
            "deployment": bind(DEPLOYMENT),
            "observations": bind(OBSERVATIONS),
            "uploaded_media": bind(uploaded),
            "link_receipt": bind(LINK),
            "WPLTO_receipt": bind(WPLTO),
            "session_config": bind(CONFIG),
            "driver": bind(Path(__file__).resolve()),
            **({"harness_first_red": bind(HARNESS_FIRST_RED)}
               if HARNESS_FIRST_RED.exists() else {}),
            **({"harness_oracle_first_red": bind(HARNESS_OUTPUT_RED)}
               if HARNESS_OUTPUT_RED.exists() else {}),
        },
        "execution_accounting": {
            "hardware_sessions": 1,
            "new_product_links": 0,
            "product_byte_changes": 0,
        },
        "claim_limit": (
            "Link 69 require/defstruct freight qualification only; no "
            "promotion, release or unrelated library claim."),
    }
    write(RECEIPT, receipt)
    print(
        "c2-defstruct-link69-hw: PASS "
        f"rows={len(config['rows'])}/{len(config['rows'])} "
        "require=idempotent defstruct=hardware-green busy=structural-green")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("prepare")
    record_parser = sub.add_parser("record")
    record_parser.add_argument("--id", required=True)
    record_parser.add_argument("--screen", type=Path, required=True)
    compare_parser = sub.add_parser("compare-repeat")
    compare_parser.add_argument("--name", required=True)
    sub.add_parser("finalize")
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
    elif args.action == "record":
        record(args.id, args.screen)
    elif args.action == "compare-repeat":
        compare_repeat(args.name)
    else:
        finalize()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (HardwareError, KeyError, OSError, json.JSONDecodeError) as error:
        print(f"c2-defstruct-link69-hw: FIRST RED: {error}")
        raise SystemExit(1)
