#!/usr/bin/env python3
"""Prepare and close the v1.2.5 require-after-appends device row."""

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
import c2_v124_require_prior_append_h1 as H1  # noqa: E402
import repl_screen_check as SCREEN  # noqa: E402


BASE = ROOT / "build/c2.2/v1.2.5-candidate-product-link82"
MANIFEST = BASE / "canonical-product-manifest.json"
PRODUCT_IDENTITY = (
    BASE / "static-plane/narrow-static/product/substitution-artifacts.json")
ACCEPTANCE = ROOT / "config/c2-require-prior-append-acceptance.json"
SCRIPT = ROOT / "scripts/c2-v125-require-prior-append-hw.sh"
OUT = ROOT / "build/c2.2/v1.2.5-require-prior-append-hardware"
DEPLOYMENT = OUT / "deployment.json"
PREPARATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.5-require-prior-append-hardware-preparation-receipt.json")
HARDWARE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.5-require-prior-append-hardware-receipt.json")
C2D_ADDRESS = 0x00050000
C2D_BYTES = 50752
C2J_ADDRESS = 0x0005C640
C2J_BYTES = 64
BANK2_ADDRESS = 0x00020000
BANK2_BYTES = 65536


class HardwareError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise HardwareError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    data = path.read_bytes()
    value: dict[str, Any] = {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    if address is not None:
        value["address"] = f"0x{address:08x}"
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def artifact_rows(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = {
        row["role"]: row for row in manifest["artifacts"]
        if isinstance(row, dict)
    }
    require(len(rows) == 14, "Link-82 pre-media artifact inventory drift")
    return rows


def prepare() -> dict[str, Any]:
    manifest = load(MANIFEST)
    identity = load(PRODUCT_IDENTITY)
    acceptance = load(ACCEPTANCE)
    require(
        manifest["candidate"]["release"] == "v1.2.5"
        and identity["product_build_id_hex"] == "0x270030c3"
        and acceptance["status"]
            == "required-in-next-v1.2.5-acceptance-session",
        "v1.2.5 candidate or acceptance authority drift",
    )
    H1.LIBRARY_OUT = OUT / "library-media"
    package, package_receipt = H1.build_library_media(
        int(identity["product_build_id_u32"]))
    package_v125 = package.with_name("require-place-v125-bound.d81")
    package.replace(package_v125)
    package = package_v125
    package_receipt["D81"] = bind(package)
    visible = H1.visible_files(package)
    require(
        set(acceptance["media_precondition"]["required_visible_files"])
            <= set(visible),
        "package medium lacks required visible files",
    )
    rows = artifact_rows(manifest)
    product = ROOT / rows["c2-resident-prg"]["path"]
    preload_map = (
        ("c2d-v6-code-plane", C2D_ADDRESS),
        ("c2-two-record-boot-stage", 0x00058500),
        ("c2-session-family-region-0", 0x08000000),
        ("c2-product-shelf", 0x08100000),
        ("c2-boot-family", 0x08200000),
        ("c2-session-family-region-1", 0x08300000),
        ("c2-kernal-window", 0x087FE000),
    )
    preloads = []
    for role, address in preload_map:
        path = ROOT / rows[role]["path"]
        preloads.append({"role": role, **bind(path, address)})
    deployment = {
        "format": "lisp65-c2.2-v1.2.5-require-prior-append-deployment-v1",
        "recorded_on": date.today().isoformat(),
        "status": "passed-host-dry-run-ready-for-one-device-session",
        "candidate": {
            "release": "v1.2.5",
            "link": 82,
            "product_build_id": identity["product_build_id_hex"],
            "product": bind(product, 0x00002001),
            "ELF": bind(ROOT / rows["linked-product-elf"]["path"]),
            "manifest": bind(MANIFEST),
            "package_medium": bind(package),
            "package_visible_files": sorted(visible),
            "package_receipt": package_receipt,
            "preloads": preloads,
        },
        "rows": acceptance["rows"],
        "addresses": {
            "c2d": f"0x{C2D_ADDRESS:08x}",
            "c2d_bytes": C2D_BYTES,
            "c2j": f"0x{C2J_ADDRESS:08x}",
            "c2j_bytes": C2J_BYTES,
            "bank2": f"0x{BANK2_ADDRESS:08x}",
            "bank2_bytes": BANK2_BYTES,
        },
        "policy": acceptance["policy"],
    }
    write_json(DEPLOYMENT, deployment)
    prep = {
        "format":
            "lisp65-c2.2-v1.2.5-require-prior-append-hardware-prep-v1",
        "recorded_on": date.today().isoformat(),
        "status": "passed-package-bound-device-row-preparation",
        "promotable": False,
        "product_links": 0,
        "hardware_runs": 0,
        "package_visible_files": sorted(visible),
        "deployment": bind(DEPLOYMENT),
        "acceptance": bind(ACCEPTANCE),
        "driver": bind(Path(__file__).resolve()),
        "script": bind(SCRIPT),
        "next_gate": "One cold-reset Link-82 device session.",
        "claim_limit": "Host preparation only; no hardware or release claim.",
    }
    write_json(PREPARATION, prep)
    return deployment


def screen_result(path: Path, form: str, expected: str) -> None:
    SCREEN.check_latest_result(path, form, expected)


def row(path: Path, slot: int) -> bytes:
    data = path.read_bytes()
    require(len(data) == C2D_BYTES, f"C2D capture width drift: {path}")
    start = 48 + slot * 32
    return data[start:start + 32]


def evaluate() -> dict[str, Any]:
    deployment = load(DEPLOYMENT)
    rows = deployment["rows"]
    out = OUT / "run"
    for item in rows:
        screen_result(
            out / f"{item['id']}.txt", item["form"], item["expected"])
    c2d0 = out / "after-first-require-c2d.bin"
    c2d1 = out / "after-repeat-c2d.bin"
    bank0 = out / "after-first-require-bank2.bin"
    bank1 = out / "after-repeat-bank2.bin"
    require(
        c2d0.read_bytes() == c2d1.read_bytes()
        and bank0.read_bytes() == bank1.read_bytes(),
        "repeat require changed C2D or Bank 2",
    )
    data = c2d1.read_bytes()
    require(
        struct.unpack_from("<H", data, 12)[0] == 9,
        "final C2D image count is not nine",
    )
    for slot in (6, 7, 8):
        require(row(c2d1, slot) != bytes(32), f"persistent slot {slot} absent")
    c2j = (out / "final-c2j.bin").read_bytes()
    require(c2j == bytes(C2J_BYTES), "C2J is not CLEAR after repeat")
    package = Path(deployment["candidate"]["package_medium"]["path"])
    package_readback = out / "package-readback.d81"
    require(
        (ROOT / package).read_bytes() == package_readback.read_bytes(),
        "mounted package-medium readback drift",
    )
    value = {
        "format":
            "lisp65-c2.2-v1.2.5-require-prior-append-hardware-v1",
        "recorded_on": date.today().isoformat(),
        "status": "passed-require-after-two-ordinary-persistent-appends",
        "promotable": True,
        "hardware_runs": 1,
        "product_links": 0,
        "results": {
            item["id"]: item["expected"] for item in rows
        },
        "readback": {
            "final_image_count": 9,
            "helper_slots": [6, 7],
            "package_slot": 8,
            "repeat_c2d_byteidentical": True,
            "repeat_bank2_byteidentical": True,
            "c2j": "CLEAR",
        },
        "bindings": {
            "preparation": bind(PREPARATION),
            "deployment": bind(DEPLOYMENT),
            "package_readback": bind(package_readback),
            "first_require_c2d": bind(c2d0, C2D_ADDRESS),
            "repeat_c2d": bind(c2d1, C2D_ADDRESS),
            "first_require_bank2": bind(bank0, BANK2_ADDRESS),
            "repeat_bank2": bind(bank1, BANK2_ADDRESS),
            "final_c2j": bind(out / "final-c2j.bin", C2J_ADDRESS),
        },
        "claim_limit": (
            "One Link-82 hardware row proves require after two ordinary "
            "persistent definitions and repeat idempotence. It makes no "
            "general package, GC, L10 or promotion claim."
        ),
    }
    write_json(HARDWARE, value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=("prepare", "dry-run", "screen", "evaluate"))
    parser.add_argument("--path", type=Path)
    parser.add_argument("--form")
    parser.add_argument("--expected")
    args = parser.parse_args()
    try:
        if args.action in {"prepare", "dry-run"}:
            value = prepare()
            print(
                "c2-v125-require-prior-append-hardware: "
                f"{'DRY-RUN ' if args.action == 'dry-run' else ''}PASS "
                f"rows={len(value['rows'])} "
                f"package={value['candidate']['package_medium']['sha256']}"
            )
        elif args.action == "screen":
            require(
                args.path is not None
                and args.form is not None and args.expected is not None,
                "screen requires --path, --form and --expected",
            )
            screen_result(args.path, args.form, args.expected)
            print("c2-v125-require-prior-append-hardware: SCREEN PASS")
        else:
            value = evaluate()
            print(
                "c2-v125-require-prior-append-hardware: PASS "
                f"status={value['status']} images=9 repeat=byteidentical"
            )
        return 0
    except (
        HardwareError, H1.H1Error, SCREEN.CheckError, OSError, ValueError,
        KeyError, TypeError, json.JSONDecodeError,
    ) as error:
        print(
            "c2-v125-require-prior-append-hardware: FIRST RED: "
            + str(error),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
