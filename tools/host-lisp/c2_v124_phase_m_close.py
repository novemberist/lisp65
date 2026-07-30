#!/usr/bin/env python3
"""Close the v1.2.4 Phase-M session, including its M1 harness First Red."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_v124_phase_m as PM  # noqa: E402
import repl_screen_check as SCREEN  # noqa: E402


OUT = PM.OUT
RECEIPT = PM.HARDWARE
FX_CONTRACT = ROOT / "config/c2-fx-contract.json"


class CloseError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CloseError(message)


def checked_screen(
        name: str, form: str, expected: str) -> dict[str, Any]:
    text = OUT / f"{name}.txt"
    png = OUT / f"{name}.png"
    SCREEN.check_latest_result(text, form, expected)
    SCREEN.check_fail_closed_frame(png)
    return {
        "form": form,
        "expected": expected,
        "screen_text": PM.bind(text),
        "screen_png": PM.bind(png),
    }


def collect() -> dict[str, Any]:
    PM.verify()
    config = PM.session_config()
    deployment = PM.load(PM.DEPLOYMENT)
    fx_contract = PM.load(FX_CONTRACT)
    require(
        "from that poke through the last result peek"
            in fx_contract["math_unit"]["transaction_rule"],
        "fx shared-math-unit transaction rule drift",
    )

    first_red_dir = OUT / "m1-first-red-trigger-order"
    first_red_text = first_red_dir / "row-m1-mul-low.txt"
    first_red_png = first_red_dir / "row-m1-mul-low.png"
    SCREEN.check_latest_result(
        first_red_text,
        "(list(peek 215 120)(peek 215 121)(peek 215 122)(peek 215 123))",
        "(0 0 0 0)",
    )
    SCREEN.check_fail_closed_frame(first_red_png)

    product = checked_screen(
        "m1-product-atomic",
        "(progn(%i)(%o 0))",
        "(0 0 0 64 0 0 0 0)",
    )
    division = checked_screen(
        "m1-division-atomic",
        "(progn(%d)(%e 0))",
        "(0 0 0 128 0 0 0 0)",
    )

    rows = {row["id"]: row for row in config["rows"]}
    m3 = [
        {
            "id": name,
            **checked_screen(
                f"row-{name}", rows[name]["form"], rows[name]["expected"]),
        }
        for name in ("m3-multiply", "m3-divide", "m3-half-away")
    ]
    m5_row = rows["m5-require-place"]
    m5 = checked_screen(
        "row-m5-require-place", m5_row["form"], m5_row["expected"])

    for row in deployment["candidate"]["preloads"]:
        source = ROOT / row["path"]
        readback = OUT / f"m3-{row['role']}.bin"
        require(
            source.read_bytes() == readback.read_bytes(),
            f"M3 preload readback drift: {row['role']}",
        )
    media = ROOT / deployment["candidate"]["media"]["path"]
    media_readback = OUT / "uploaded-media-second.d81"
    require(
        media.read_bytes() == media_readback.read_bytes(),
        "Phase-M candidate media readback drift",
    )

    l10 = PM.l10_result()
    timing = PM.time_result()
    require(
        l10["status"] == "reproduced-delayed-convergence"
        and timing["status"] == "passed-50Hz-calibration",
        "Phase-M measured disposition drift",
    )

    trace = (OUT / "m5-trace.bin").read_bytes()
    header = (OUT / "m5-c2d-header.bin").read_bytes()
    place = (OUT / "m5-place-row.bin").read_bytes()
    core = (OUT / "device-core-id.bin").read_bytes()
    require(
        len(trace) == 2 and len(header) == 48
        and len(place) == 32 and len(core) == 4,
        "Phase-M readback span drift",
    )

    receipt = {
        "format": "lisp65-c2.2-v1.2.4-phase-m-hardware-v2",
        "recorded_on": date.today().isoformat(),
        "status":
            "passed-one-bundled-session-with-M1-harness-correction",
        "device": {
            "core_register_bytes": core.hex(),
            "core_register_artifact": PM.bind(
                OUT / "device-core-id.bin", PM.CORE_ID_ADDRESS),
        },
        "M1_math_register_semantics": {
            "status": "passed-after-atomic-harness-correction",
            "product_u64_le": "0000004000000000",
            "division_fraction_u32_le": "00000080",
            "division_quotient_u32_le": "00000000",
            "rounding_bit": "$D76B bit 7 set on exact half",
            "product": product,
            "division": division,
            "harness_first_red": {
                "status": "closed-measurement-transaction-split",
                "observed": "(0 0 0 0)",
                "mechanism": (
                    "The original script returned to the REPL between input "
                    "writes and result reads. Screen/result work may reuse the "
                    "shared math unit, so the later read was not the measured "
                    "transaction. The corrected row writes all eight inputs "
                    "and reads all eight outputs in one Lisp evaluation."
                ),
                "product_bytes_changed": 0,
                "physical_session_restarted": False,
                "first_red_text": PM.bind(first_red_text),
                "first_red_png": PM.bind(first_red_png),
                "contract": PM.bind(FX_CONTRACT),
            },
        },
        "M2_L10": l10,
        "M3_fx": {
            "status": "passed-target-multiply-divide-rounding-smoke",
            "rows": m3,
        },
        "M4_time": timing,
        "M5_peek_map": {
            "status": "captured-after-green-require",
            "require": m5,
            "trace_hex": trace.hex(),
            "c2d_image_count": struct.unpack_from("<H", header, 12)[0],
            "place_generation": struct.unpack_from("<H", place, 4)[0],
            "place_crc32":
                f"0x{struct.unpack_from('<I', place, 28)[0]:08x}",
            "artifacts": {
                "trace": PM.bind(OUT / "m5-trace.bin", 0x0000C1F4),
                "c2d_header":
                    PM.bind(OUT / "m5-c2d-header.bin", 0x00050000),
                "place_row":
                    PM.bind(OUT / "m5-place-row.bin", 0x000500F0),
            },
        },
        "transport": {
            "cold_start_BASIC_gates": 3,
            "candidate_media_byteidentical": PM.bind(media_readback),
            "candidate_preload_roles_byteidentical":
                len(deployment["candidate"]["preloads"]),
            "ftp_progress_guard_seconds": 120,
        },
        "execution_accounting": {
            "physical_device_sessions": 1,
            "controlled_deployments": 3,
            "product_links": 0,
            "product_bytes_changed": 0,
            "promotable_candidates": 0,
        },
        "authority": {
            "preparation": PM.bind(PM.PREPARATION),
            "deployment": PM.bind(PM.DEPLOYMENT),
            "session_config": PM.bind(PM.CONFIG),
            "prepared_driver": PM.bind(
                ROOT / deployment["authority"]["driver"]["path"]),
            "closure_driver": PM.bind(Path(__file__)),
        },
        "claim_limit": (
            "One non-promotable Phase-M hardware session. M1/M3/M4 are "
            "target measurements; M2 reuses the isolated Link-35 diagnostic "
            "identity on the recorded current core; M5 is a read-only "
            "snapshot. No successor product link or release claim is made."
        ),
    }
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check", action="store_true",
        help="verify the tracked closure receipt instead of writing it")
    args = parser.parse_args()
    try:
        value = collect()
        encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
        if args.check:
            require(
                RECEIPT.is_file()
                and RECEIPT.read_text(encoding="utf-8") == encoded,
                "Phase-M hardware closure receipt drift",
            )
        else:
            require(
                not RECEIPT.exists(),
                "Phase-M hardware receipt already exists")
            PM.write_json(RECEIPT, value)
        print(
            "c2-v124-phase-m-close: "
            f"{'VERIFY ' if args.check else ''}PASS "
            f"L10={value['M2_L10']['status']} "
            f"time={value['M4_time']['frames_per_second']:.3f}Hz "
            "fx=3/3")
        return 0
    except (
        CloseError, PM.PhaseMError, OSError, ValueError, KeyError, TypeError,
        json.JSONDecodeError, SCREEN.CheckError,
    ) as error:
        print(f"c2-v124-phase-m-close: FIRST RED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
