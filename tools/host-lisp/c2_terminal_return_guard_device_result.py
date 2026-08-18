#!/usr/bin/env python3
"""Close the Link-96 physical point row and decode its shadow-guard record."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import repl_screen_check as SCREEN  # noqa: E402


CONFIG = ROOT / "config/c2-terminal-return-guard-link96-device-session.json"
MEDIA_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link96-terminal-return-guard-media-receipt.json"
)
OUT = ROOT / "build/c2.3/terminal-return-guard-link96-device-session-r2"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link96-terminal-return-guard-device-receipt.json"
)
FORMAT = "lisp65-c2.3-link96-terminal-return-guard-device-result-v1"
STATUS_CLEAN = "LINK96-POINT-HARDWARE-GREEN; GUARD-CLEAN"
STATUS_RESTORED = "LINK96-POINT-HARDWARE-GREEN; GUARD-RESTORED"
ROW_IDS = ("require-defstruct", "define-point", "make-point")
TRANSFER_NAMES = (
    "append-header", "publish-plan-scan", "publish-plan-resolve",
    "publish-clear",
)
TAG_NAMES = {1: "return-low", 2: "return-high", 3: "phase-owner"}
MUTATIONS = (
    "drop-row", "wrong-point", "allow-virtual-input", "allow-polling",
    "replace-product-readback", "replace-library-readback",
    "leave-guard-armed", "drop-guard-record", "wrong-restoration-count",
    "wrong-status", "claim-product-link", "claim-writer-attribution",
    "wrong-record-base",
)


class ResultError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResultError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"evidence absent: {path}")
    raw = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
    }


def decode_guard(raw: bytes) -> dict[str, Any]:
    require(len(raw) == 16, f"guard readback length drift: {len(raw)}")
    require(raw[0] == 0, f"guard remained armed: 0x{raw[0]:02x}")
    working_shadow = {
        "return_low": raw[1], "return_high": raw[2],
        "phase_owner": raw[3],
    }
    records = []
    for index, transfer in enumerate(TRANSFER_NAMES):
        tag, live, shadow = raw[4 + index * 3:7 + index * 3]
        require(tag in (0, 1, 2, 3), f"guard tag invalid: 0x{tag:02x}")
        if tag == 0:
            require(live == shadow == 0,
                    "untagged guard record carries values")
            records.append({
                "transfer": transfer, "tag": 0, "field": None,
                "live": 0, "shadow": 0, "restored": False,
            })
        else:
            require(live != shadow,
                    "tagged guard record does not describe a mismatch")
            records.append({
                "transfer": transfer, "tag": tag,
                "field": TAG_NAMES[tag], "live": live, "shadow": shadow,
                "restored": True,
            })
    restored = sum(row["restored"] for row in records)
    return {
        "raw_hex": raw.hex(), "arm": raw[0],
        "working_shadow": working_shadow, "records": records,
        "restoration_count": restored,
        "classification": "restored" if restored else "clean",
    }


def row_evidence(row: dict[str, Any]) -> dict[str, Any]:
    row_id = row["id"]
    text = OUT / f"row-{row_id}.txt"
    image = OUT / f"row-{row_id}.png"
    SCREEN.check_fail_closed_frame(image)
    SCREEN.check_latest_result(text, row["form"], row["expect"][0])
    visible = SCREEN._latest_visible_results(text, row["form"])
    return {
        "id": row_id, "form": row["form"],
        "quiet_floor_seconds": row["quiet_floor_seconds"],
        "latest_visible_results": visible,
        "screen_text": bind(text), "screen_image": bind(image),
        "result": "passed",
    }


def derive(recorded_on: str) -> dict[str, Any]:
    config = load(CONFIG)
    media = load(MEDIA_RECEIPT)
    require(
        config.get("status") == "prepared-not-run"
        and [row["id"] for row in config["rows"]] == list(ROW_IDS),
        "Link-96 device-session contract drift",
    )
    require(
        media.get("status")
            == "LINK96-GUARDED-MEDIA-R2-GREEN; POINT-HARDWARE-ROW-READY",
        "Link-96 guarded media authority is not green",
    )
    require((OUT / "rows-complete").is_file()
            and (OUT / "next-row").read_text(encoding="ascii").strip()
            == "COMPLETE", "Link-96 physical rows are incomplete")
    rows = [row_evidence(row) for row in config["rows"]]

    product_source = ROOT / config["identity"]["product_medium"]
    library_source = ROOT / config["identity"]["library_medium"]
    product_readback = OUT / "product-readback.d81"
    library_readback = OUT / "library-readback.d81"
    require(product_source.read_bytes() == product_readback.read_bytes(),
            "product D81 readback mismatch")
    require(library_source.read_bytes() == library_readback.read_bytes(),
            "library D81 readback mismatch")

    guard_path = OUT / "terminal-return-guard.bin"
    guard = decode_guard(guard_path.read_bytes())
    status = STATUS_RESTORED if guard["restoration_count"] else STATUS_CLEAN
    require(rows[-1]["latest_visible_results"] == ["(point 3 4)"],
            "make-point postcondition drift")
    return {
        "format": FORMAT, "recorded_on": recorded_on, "status": status,
        "authority": {
            "guarded_media": bind(MEDIA_RECEIPT),
            "session_contract": bind(CONFIG),
            "result_recorder": bind(Path(__file__).resolve()),
            "screen_checker": bind(ROOT / "tools/host-lisp/repl_screen_check.py"),
        },
        "media_readback": {
            "product_source": bind(product_source),
            "product_readback": bind(product_readback),
            "library_source": bind(library_source),
            "library_readback": bind(library_readback),
            "result": "byteidentical",
        },
        "rows": rows,
        "point_postcondition": {
            "form": "(make-point 3 4)", "result": "(point 3 4)",
            "defstruct_hardware_green": True,
        },
        "terminal_return_guard": {
            **guard, "capture": bind(guard_path),
            "arena": "physical Bank-0 0x0000b582..0x0000b591",
            "writer_attributed": False,
        },
        "readback_decoder": {
            "arm": "0xB582",
            "working_shadow": "0xB583..0xB585",
            "records": "0xB586..0xB591",
            "initial_first_red": (
                "parser treated working shadow byte 0xE4 as record tag"),
            "device_reads_after_first_red": 0,
            "rescued_from_same_capture": True,
            "layout_mutations_rejected": 1,
        },
        "execution_accounting": {
            "product_links": 0, "hardware_contacts": 1,
            "physical_forms": 3, "virtual_forms": 0,
            "observations_during_active_forms": 0, "final_stops": 1,
        },
        "release_claim": False,
        "mutation_contract": list(MUTATIONS),
        "next": "owner-halt-before-experience-block",
        "claim_limit": (
            "Link-96 point hardware acceptance and terminal-return-guard "
            "readback only. A restored record names the mismatching tuple "
            "field and values, not its writer. No release or Experience-block "
            "claim is made here."
        ),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    guard = value.get("terminal_return_guard", {})
    decoded = decode_guard(bytes.fromhex(guard.get("raw_hex", "")))
    expected_status = (STATUS_RESTORED if decoded["restoration_count"]
                       else STATUS_CLEAN)
    media = value.get("media_readback", {})
    require(
        value.get("format") == FORMAT and value.get("status") == expected_status
        and [row.get("id") for row in value.get("rows", [])] == list(ROW_IDS)
        and all(row.get("result") == "passed" for row in value["rows"])
        and value["rows"][-1].get("latest_visible_results") == ["(point 3 4)"]
        and value.get("point_postcondition") == {
            "form": "(make-point 3 4)", "result": "(point 3 4)",
            "defstruct_hardware_green": True}
        and value.get("readback_decoder") == {
            "arm": "0xB582",
            "working_shadow": "0xB583..0xB585",
            "records": "0xB586..0xB591",
            "initial_first_red": (
                "parser treated working shadow byte 0xE4 as record tag"),
            "device_reads_after_first_red": 0,
            "rescued_from_same_capture": True,
            "layout_mutations_rejected": 1}
        and guard.get("arm") == 0
        and guard.get("working_shadow") == decoded["working_shadow"]
        and guard.get("records") == decoded["records"]
        and guard.get("restoration_count") == decoded["restoration_count"]
        and guard.get("classification") == decoded["classification"]
        and guard.get("writer_attributed") is False
        and media.get("result") == "byteidentical"
        and media.get("product_source", {}).get("sha256")
            == media.get("product_readback", {}).get("sha256")
        and media.get("library_source", {}).get("sha256")
            == media.get("library_readback", {}).get("sha256")
        and value.get("execution_accounting") == {
            "product_links": 0, "hardware_contacts": 1,
            "physical_forms": 3, "virtual_forms": 0,
            "observations_during_active_forms": 0, "final_stops": 1}
        and value.get("release_claim") is False
        and value.get("mutation_contract") == list(MUTATIONS)
        and value.get("next") == "owner-halt-before-experience-block",
        "Link-96 device-result claim drift",
    )
    if verify:
        require(value == derive(value["recorded_on"]),
                "Link-96 device-result receipt is stale")


def rejected_mutations(base: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "drop-row": lambda x: x["rows"].pop(),
        "wrong-point": lambda x: x["point_postcondition"].update(result="nil"),
        "allow-virtual-input": lambda x: x["execution_accounting"].update(virtual_forms=1),
        "allow-polling": lambda x: x["execution_accounting"].update(observations_during_active_forms=1),
        "replace-product-readback": lambda x: x["media_readback"]["product_readback"].update(sha256="00" * 32),
        "replace-library-readback": lambda x: x["media_readback"]["library_readback"].update(sha256="00" * 32),
        "leave-guard-armed": lambda x: x["terminal_return_guard"].update(arm=1),
        "drop-guard-record": lambda x: x["terminal_return_guard"]["records"].pop(),
        "wrong-restoration-count": lambda x: x["terminal_return_guard"].update(restoration_count=99),
        "wrong-status": lambda x: x.update(status="UNKNOWN"),
        "claim-product-link": lambda x: x["execution_accounting"].update(product_links=1),
        "claim-writer-attribution": lambda x: x["terminal_return_guard"].update(writer_attributed=True),
        "wrong-record-base": lambda x: x["readback_decoder"].update(
            records="0xB583..0xB58E"),
    }
    rejected = []
    for name, mutate in cases.items():
        candidate = deepcopy(base)
        mutate(candidate)
        try:
            validate(candidate, verify=False)
        except (ResultError, ValueError):
            rejected.append(name)
    require(rejected == list(MUTATIONS), "Link-96 device-result mutation survived")
    return rejected


def selftest() -> None:
    clean = decode_guard(bytes(16))
    require(clean["classification"] == "clean", "clean fixture drift")
    target_clean_raw = bytes((0, 0xE4, 0x2C, 2)) + bytes(12)
    target_clean = decode_guard(target_clean_raw)
    require(
        target_clean["classification"] == "clean"
        and target_clean["working_shadow"] == {
            "return_low": 0xE4, "return_high": 0x2C, "phase_owner": 2},
        "working-shadow/record layout drift",
    )
    healed_raw = bytearray(16)
    healed_raw[1:4] = bytes((0xE4, 0x2C, 2))
    healed_raw[4:7] = bytes((1, 0x71, 0x35))
    healed_raw[10:13] = bytes((3, 0, 2))
    healed = decode_guard(bytes(healed_raw))
    require(healed["restoration_count"] == 2, "restored fixture drift")
    rejected = 0
    for raw in (
        bytes(15), bytes((1,)) + bytes(15),
        bytes((0, 0, 0, 0, 4, 1, 2)) + bytes(9),
        bytes((0, 0, 0, 0, 0, 1, 0)) + bytes(9),
        bytes((0, 0, 0, 0, 1, 7, 7)) + bytes(9),
    ):
        try:
            decode_guard(raw)
        except ResultError:
            rejected += 1
    require(rejected == 5, "guard decoder mutation survived")
    print("Link-96 device-result selftest: PASS decoder-mutations=5")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check", "selftest"))
    action = parser.parse_args().action
    if action == "selftest":
        selftest()
        return 0
    if action == "record":
        require(not RECEIPT.exists(), "Link-96 device result is one-shot")
        value = derive(date.today().isoformat())
        validate(value, verify=False)
        rejected = rejected_mutations(value)
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_bytes(canonical(value))
        print(f"Link-96 device result: WROTE {RECEIPT.relative_to(ROOT)} "
              f"mutations={len(rejected)}")
        return 0
    value = load(RECEIPT)
    validate(value, verify=True)
    rejected = rejected_mutations(value)
    print(f"Link-96 device result check: PASS mutations={len(rejected)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ResultError, SCREEN.CheckError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        message = error.message if isinstance(error, SCREEN.CheckError) else str(error)
        print(f"Link-96 device result: FIRST RED: {message}", file=sys.stderr)
        raise SystemExit(2)
