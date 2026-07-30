#!/usr/bin/env python3
"""Prepare, verify and close the one v1.2.4 Phase-M device session."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link35_hold_before_wipe_fixed_patch as L10  # noqa: E402
import c2_v122_link78_d1_d2_hw as MEDIA  # noqa: E402
import c2_v124_fx_wplto as FXW  # noqa: E402
import repl_screen_check as SCREEN  # noqa: E402


CAN = FXW.CAN
CONFIG = ROOT / "config/c2.2-v1.2.4-phase-m-session.json"
WPLTO_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.4-fx-wplto-receipt.json")
PHASE_R = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.4-basic65-parity-revalidation-receipt.json")
OUT = ROOT / "build/post-promotion/v124/phase-m"
ARTIFACTS = OUT / "artifacts"
MEDIA_OUT = OUT / "library-media"
DEPLOYMENT = OUT / "deployment.json"
PREPARATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.4-phase-m-preparation-receipt.json")
HARDWARE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.4-phase-m-hardware-receipt.json")
SCRIPT = ROOT / "scripts/c2-v124-phase-m.sh"
BASE_MEDIA = ROOT / (
    "build/post-promotion/v1.2.3/link80-bundled-session/library-media/"
    "require-defstruct-link78-bound.d81")
ROLE_ADDRESS = {
    "c2d-v6-code-plane": 0x00050000,
    "c2-two-record-boot-stage": 0x00058500,
    "c2-session-family-region-0": 0x08000000,
    "c2-product-shelf": 0x08100000,
    "c2-boot-family": 0x08200000,
    "c2-session-family-region-1": 0x08300000,
    "c2-kernal-window": 0x087FE000,
}
LOAD_ADDRESS = 0x2001
CORE_ID_ADDRESS = 0x0FFD3632


class PhaseMError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PhaseMError(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    data = path.read_bytes()
    value: dict[str, Any] = {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(data),
        "sha256": sha_bytes(data),
    }
    if address is not None:
        value["address"] = f"0x{address:08x}"
    return value


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"JSON authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii")
    if path.exists():
        require(path.read_bytes() == encoded, f"generated JSON drift: {path}")
    else:
        path.write_bytes(encoded)


def replace_json(path: Path, value: dict[str, Any]) -> None:
    require(path.is_file(), f"JSON replay target absent: {path}")
    path.write_bytes(
        (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii"))


def crc16(value: bytes) -> int:
    result = 0xFFFF
    for byte in value:
        result ^= byte << 8
        for _ in range(8):
            result = (
                ((result << 1) ^ 0x1021) & 0xFFFF
                if result & 0x8000 else (result << 1) & 0xFFFF
            )
    return result


def session_config() -> dict[str, Any]:
    value = load(CONFIG)
    rows = value["rows"]
    require(
        value["status"] == "owner-commissioned-one-session-hardware-not-run"
        and value["policy"]["product_links"] == 0
        and value["policy"]["physical_device_sessions"] == 1
        and value["policy"]["cold_reset_and_asserted_basic_before_first_transfer"]
        and value["policy"]["ftp_no_progress_timeout_seconds"] == 120
        and [row["phase"] for row in rows]
            == ["M1"] * 9 + ["M3"] * 3 + ["M5"],
        "Phase-M contract envelope drift",
    )
    maximum = value["input_transport"]["maximum_form_characters"]
    require(
        all(len(row["form"]) <= maximum for row in rows),
        "Phase-M form exceeds verified-input transport limit",
    )
    return value


def candidate_roles() -> dict[str, dict[str, Any]]:
    receipt = load(WPLTO_RECEIPT)
    require(
        receipt["status"] == "passed-fx-one-product-shaped-WPLTO"
        and receipt["product_links"] == 0
        and receipt["hardware_runs"] == 0
        and receipt["wplto_probes_consumed"] == 1,
        "fx WPLTO authority drift",
    )
    paths = FXW.configure()
    wplto = paths["wplto"]
    static = paths["static"]
    static_product = paths["static_product"]
    profile = wplto / "resolved-profile.txt"
    elf = wplto / "lisp65-c2-substitution-linked.prg.elf"
    CAN.ARTIFACTS = ARTIFACTS
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    bootstage, _ = CAN.build_boot_stage(elf, profile)
    result = {
        "linked-product-elf": bind(elf),
        "c2-resident-prg": bind(
            wplto / "lisp65-c2-substitution-linked.prg", LOAD_ADDRESS),
        "c2-bank2-static-code-plane": bind(
            static / "v6-semantics/bank2-static-code.bin"),
        "c2d-v6-code-plane": bind(
            static / "v6-semantics/initial.c2d-v6.bin",
            ROLE_ADDRESS["c2d-v6-code-plane"]),
        "c2-two-record-boot-stage": bind(
            bootstage, ROLE_ADDRESS["c2-two-record-boot-stage"]),
        "c2-session-family-region-0": bind(
            wplto / "runtime-overlays-session-final.bin",
            ROLE_ADDRESS["c2-session-family-region-0"]),
        "c2-product-shelf": bind(
            static_product / "product-shelf-v4-direct.bin",
            ROLE_ADDRESS["c2-product-shelf"]),
        "c2-boot-family": bind(
            wplto / "runtime-overlays-boot-final.bin",
            ROLE_ADDRESS["c2-boot-family"]),
        "c2-session-family-region-1": bind(
            wplto / "runtime-overlays-session-final-region1.bin",
            ROLE_ADDRESS["c2-session-family-region-1"]),
        "c2-kernal-window": bind(
            wplto / "c2-product-kernal-window.bin",
            ROLE_ADDRESS["c2-kernal-window"]),
        "resolved-profile": bind(profile),
    }
    expected = {
        "c2-resident-prg": 41566,
        "c2-bank2-static-code-plane": 42936,
        "c2d-v6-code-plane": 33840,
        "c2-session-family-region-0": 65423,
        "c2-session-family-region-1": 1956,
        "c2-kernal-window": 8192,
    }
    require(
        all(result[name]["bytes"] == size for name, size in expected.items()),
        "fx deployment role size drift",
    )
    return result


def prepare() -> dict[str, Any]:
    require(
        not OUT.exists() and not PREPARATION.exists() and not HARDWARE.exists(),
        "Phase-M preparation is one-shot",
    )
    config = session_config()
    roles = candidate_roles()
    MEDIA.BASE_MEDIA = BASE_MEDIA
    MEDIA.MEDIA_OUT = MEDIA_OUT
    media_path, media_receipt = MEDIA.build_media(roles)
    l10_deployment = L10.verify_hardware()
    preloads = [
        {**roles[name], "role": name}
        for name in ROLE_ADDRESS
    ]
    value = {
        "format": "lisp65-c2.2-v1.2.4-phase-m-deployment-v1",
        "status": "ready-one-session-three-controlled-deployments",
        "candidate": {
            "product": roles["c2-resident-prg"],
            "ELF": roles["linked-product-elf"],
            "preloads": preloads,
            "media": bind(media_path),
            "remote_media": "V124FX.D81",
            "promotable": False,
        },
        "l10": {
            "product": l10_deployment["product"],
            "preloads": l10_deployment["preloads"],
            "expected_source": next(
                row for row in l10_deployment["preloads"]
                if int(row["address"], 16) == 0x08200000
            ),
            "promotable": False,
        },
        "addresses": {
            "core_id": f"0x{CORE_ID_ADDRESS:08x}",
            "frame_counter": "0x0000ff83",
            **config["peek_map"],
        },
        "authority": {
            "config": bind(CONFIG),
            "phase_R": bind(PHASE_R),
            "fx_WPLTO": bind(WPLTO_RECEIPT),
            "driver": bind(Path(__file__)),
            "hardware_script": bind(SCRIPT),
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(DEPLOYMENT, value)
    receipt = {
        "format": "lisp65-c2.2-v1.2.4-phase-m-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status": "passed-host-dry-run-ready-hardware-not-run",
        "deployment": bind(DEPLOYMENT),
        "candidate_media": media_receipt,
        "session": {
            "physical_devices": 1,
            "controlled_deployments": 3,
            "verified_forms": len(config["rows"]),
            "maximum_form_characters": max(
                len(row["form"]) for row in config["rows"]),
            "cold_reset_gate": True,
            "ftp_progress_guard_seconds": 120,
        },
        "execution_accounting": {
            "product_links": 0,
            "hardware_runs": 0,
            "diagnostic_product_bytes_changed": 0,
        },
        "claim_limit": (
            "Host preparation only. The fx and L10 identities are "
            "non-promotable; no target result is claimed."
        ),
    }
    write_json(PREPARATION, receipt)
    verify()
    return receipt


def verify() -> dict[str, Any]:
    config = session_config()
    deployment = load(DEPLOYMENT)
    preparation = load(PREPARATION)
    require(
        deployment["status"] == "ready-one-session-three-controlled-deployments"
        and preparation["status"]
            == "passed-host-dry-run-ready-hardware-not-run"
        and deployment["authority"] == {
            "config": bind(CONFIG),
            "phase_R": bind(PHASE_R),
            "fx_WPLTO": bind(WPLTO_RECEIPT),
            "driver": bind(Path(__file__)),
            "hardware_script": bind(SCRIPT),
        }
        and preparation["deployment"] == bind(DEPLOYMENT)
        and preparation["session"]["verified_forms"] == len(config["rows"]),
        "Phase-M preparation authority drift",
    )
    for phase in ("candidate", "l10"):
        rows = [
            deployment[phase]["product"],
            *deployment[phase]["preloads"],
        ]
        for row in rows:
            path = ROOT / row["path"]
            require(
                bind(path)["bytes"] == row["bytes"]
                and bind(path)["sha256"] == row["sha256"],
                f"Phase-M deployment artifact drift: {path}",
            )
    return preparation


def rebind_preparation() -> dict[str, Any]:
    require(
        DEPLOYMENT.is_file() and PREPARATION.is_file()
        and not HARDWARE.exists(),
        "Phase-M pre-hardware replay envelope absent or already consumed",
    )
    deployment = load(DEPLOYMENT)
    preparation = load(PREPARATION)
    immutable = {
        "candidate": deployment["candidate"],
        "l10": deployment["l10"],
        "addresses": deployment["addresses"],
        "candidate_media": preparation["candidate_media"],
        "session": preparation["session"],
        "execution_accounting": preparation["execution_accounting"],
    }
    deployment["authority"] = {
        "config": bind(CONFIG),
        "phase_R": bind(PHASE_R),
        "fx_WPLTO": bind(WPLTO_RECEIPT),
        "driver": bind(Path(__file__)),
        "hardware_script": bind(SCRIPT),
    }
    replace_json(DEPLOYMENT, deployment)
    preparation["deployment"] = bind(DEPLOYMENT)
    preparation["artifact_replay"] = {
        "status": "passed-authority-only-pre-hardware-rebind",
        "reason": (
            "Phase-M progress was recorded in the bound work plan; the "
            "Phase-R receipt replay changed only that plan authority."
        ),
        "candidate_and_L10_bytes_changed": 0,
        "hardware_runs_before_replay": 0,
    }
    replace_json(PREPARATION, preparation)
    replayed = {
        "candidate": load(DEPLOYMENT)["candidate"],
        "l10": load(DEPLOYMENT)["l10"],
        "addresses": load(DEPLOYMENT)["addresses"],
        "candidate_media": load(PREPARATION)["candidate_media"],
        "session": load(PREPARATION)["session"],
        "execution_accounting": load(PREPARATION)["execution_accounting"],
    }
    require(replayed == immutable, "Phase-M authority replay changed payload")
    return verify()


def screen_result(row: dict[str, Any], path: Path) -> dict[str, Any]:
    SCREEN.check_latest_result(path, row["form"], row["expected"])
    return {"id": row["id"], "phase": row["phase"], "status": "passed",
            "expected": row["expected"], "screen": bind(path)}


def l10_result() -> dict[str, Any]:
    deployment = load(DEPLOYMENT)
    source_row = deployment["l10"]["expected_source"]
    source = (ROOT / source_row["path"]).read_bytes()
    expected = source[0x200:0x200 + 1156]
    require(len(expected) == 1156 and crc16(expected) == 0xE856,
            "L10 expected source drift")
    captures = []
    values = []
    for index in range(1, 4):
        path = OUT / f"l10-capture-{index}.bin"
        value = path.read_bytes()
        require(len(value) == len(expected), "L10 capture length drift")
        values.append(value)
        captures.append({
            "capture": index,
            "elapsed_after_launch_ms": int(
                (OUT / f"l10-capture-{index}-ms.txt").read_text().strip()),
            "crc16": f"0x{crc16(value):04x}",
            "nonmatching_bytes": sum(a != b for a, b in zip(value, expected)),
            "matches_expected": value == expected,
            "artifact": bind(path),
        })
    if values[0] == expected:
        disposition = "not-reproduced-immediate-content-visible"
    elif any(value == expected for value in values[1:]):
        disposition = "reproduced-delayed-convergence"
    elif any(a != b for a, b in zip(values, values[1:])):
        disposition = "reproduced-still-changing"
    else:
        disposition = "stable-wrong-owner-review"
    return {"status": disposition, "expected_crc16": "0xe856",
            "captures": captures}


def time_result() -> dict[str, Any]:
    before_bytes = (OUT / "time-before.bin").read_bytes()
    after_bytes = (OUT / "time-after.bin").read_bytes()
    require(
        len(before_bytes) == 2 and len(after_bytes) == 2,
        "M4 frame-counter readback length drift",
    )
    before = int.from_bytes(before_bytes, "little")
    after = int.from_bytes(after_bytes, "little")
    start = int((OUT / "time-start-ns.txt").read_text().strip())
    end = int((OUT / "time-end-ns.txt").read_text().strip())
    elapsed = (end - start) / 1_000_000_000
    delta = (after - before) & 0xFFFF
    hz = delta / elapsed
    low, high = session_config()["time_calibration"]["accepted_hz"]
    return {
        "status": "passed-50Hz-calibration" if low <= hz <= high
            else "measurement-outside-preregistered-band",
        "counter_before": before,
        "counter_after": after,
        "counter_delta": delta,
        "elapsed_seconds": elapsed,
        "frames_per_second": hz,
        "nominal_hz": 50,
        "accepted_hz": [low, high],
    }


def evaluate() -> dict[str, Any]:
    verify()
    config = session_config()
    rows = [
        screen_result(row, OUT / f"row-{row['id']}.txt")
        for row in config["rows"]
    ]
    peek = {
        name: bind(OUT / f"m5-{name.replace('_', '-')}.bin",
                   int(row["address"], 0))
        for name, row in config["peek_map"].items()
    }
    header = (ROOT / peek["c2d_header"]["path"]).read_bytes()
    place = (ROOT / peek["place_row"]["path"]).read_bytes()
    require(
        len(header) == 48 and len(place) == 32,
        "M5 peek-map span drift",
    )
    value = {
        "format": "lisp65-c2.2-v1.2.4-phase-m-hardware-v1",
        "recorded_on": date.today().isoformat(),
        "status": "passed-one-bundled-Phase-M-session",
        "device": {
            "core_register_bytes": (
                OUT / "device-core-id.bin").read_bytes().hex(),
            "core_register_artifact": bind(OUT / "device-core-id.bin",
                                           CORE_ID_ADDRESS),
        },
        "M1_math_register_semantics": {
            "status": "passed-full-product-and-fraction-layout",
            "rows": [row for row in rows if row["phase"] == "M1"],
            "product_u64_le": "0000004000000000",
            "division_quotient_u32_le": "00000000",
            "division_fraction_u32_le": "00000080",
            "rounding_bit": "$D76B bit 7 set on exact half",
        },
        "M2_L10": l10_result(),
        "M3_fx": {
            "status": "passed-target-smoke",
            "rows": [row for row in rows if row["phase"] == "M3"],
        },
        "M4_time": time_result(),
        "M5_peek_map": {
            "status": "captured-after-green-require",
            "require_row": next(row for row in rows if row["phase"] == "M5"),
            "trace_hex": (ROOT / peek["trace"]["path"]).read_bytes().hex(),
            "c2d_image_count": struct.unpack_from("<H", header, 12)[0],
            "place_generation": struct.unpack_from("<H", place, 4)[0],
            "place_crc32": f"0x{struct.unpack_from('<I', place, 28)[0]:08x}",
            "artifacts": peek,
        },
        "execution_accounting": {
            "physical_device_sessions": 1,
            "controlled_deployments": 3,
            "product_links": 0,
            "promotable_candidates": 0,
        },
        "authority": {
            "preparation": bind(PREPARATION),
            "deployment": bind(DEPLOYMENT),
            "config": bind(CONFIG),
            "driver": bind(Path(__file__)),
            "hardware_script": bind(SCRIPT),
        },
        "claim_limit": (
            "One non-promotable Phase-M measurement session. M1/M3/M4 are "
            "target measurements; M2 reuses the isolated Link-35 diagnostic "
            "identity on the current recorded core; M5 is a read-only snapshot."
        ),
    }
    require(
        value["M4_time"]["status"] == "passed-50Hz-calibration",
        "M4 time-base calibration outside preregistered band",
    )
    write_json(HARDWARE, value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=("prepare", "verify", "rebind", "evaluate"))
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            result = prepare()
            print(
                "c2-v124-phase-m: PREPARE PASS "
                f"forms={result['session']['verified_forms']} hardware=not-run")
        elif args.action == "verify":
            verify()
            print("c2-v124-phase-m: VERIFY PASS")
        elif args.action == "rebind":
            rebind_preparation()
            print(
                "c2-v124-phase-m: REBIND PASS "
                "payload-delta=0 hardware=not-run")
        else:
            result = evaluate()
            print(
                "c2-v124-phase-m: PASS "
                f"L10={result['M2_L10']['status']} "
                f"time={result['M4_time']['frames_per_second']:.3f}Hz")
        return 0
    except (
        PhaseMError, OSError, ValueError, KeyError, TypeError,
        json.JSONDecodeError, SCREEN.CheckError,
    ) as error:
        print(f"c2-v124-phase-m: FIRST RED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
