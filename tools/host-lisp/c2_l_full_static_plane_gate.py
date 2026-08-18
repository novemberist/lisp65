#!/usr/bin/env python3
"""Bind the target Bank-2 closure to the current L-full product emission."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "config/c2-l-full-product-profile.json"
CONTRACT = ROOT / "config/c2-lite-execution-contract.json"
HEADER = ROOT / "src/c2_lite_static_plane.h"
DECODER = ROOT / "scripts/c2-stream-decoder.c"
FRESH_ROOT = ROOT / (
    "build/c2.2/substitution/published-nullary-call-bytecode-artifacts")
FRESH_PRODUCT = FRESH_ROOT / "product/substitution-artifacts.json"
FRESH_IDE = FRESH_ROOT / "libs/ide.manifest.json"
FRESH_BANK2 = FRESH_ROOT / "v6-semantics/bank2-static-code.bin"
FRESH_MANIFESTS = (
    FRESH_ROOT / "workbench/stdlib-p0.manifest.json",
    FRESH_IDE,
    FRESH_ROOT / "libs/idex.manifest.json",
    FRESH_ROOT / "libs/m65d.manifest.json",
    ROOT / "build/bytecode/dialect-v2/libs/buffer.manifest.json",
    ROOT / "build/c2.2/substitution/lcc.manifest.json",
)
_HISTORICAL_DEFAULT_PRODUCT = FRESH_PRODUCT
_HISTORICAL_DEFAULT_IDE = FRESH_IDE
_HISTORICAL_DEFAULT_BANK2 = FRESH_BANK2
_HISTORICAL_DEFAULT_MANIFESTS = FRESH_MANIFESTS


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bound(row: dict[str, Any], label: str) -> Path:
    path = ROOT / str(row["path"])
    require(path.is_file() and sha(path) == row["sha256"],
            f"{label} binding drift")
    return path


def header_value(text: str) -> int:
    match = re.search(
        r"^#define LISP65_C2_LITE_STATIC_CODE_BYTES ([0-9]+)UL$",
        text, re.MULTILINE)
    require(match is not None, "unique static-plane header pin absent")
    return int(match.group(1))


def validate(bundle: dict[str, Any]) -> dict[str, Any]:
    profile = bundle["profile"]
    contract = bundle["contract"]
    header = bundle["header"]
    decoder = bundle["decoder"]
    expected = int(profile["bank2_static_code"]["bytes"])
    receipt = bundle["receipt"]
    substitution = bundle["substitution"]
    ide = bundle["ide"]
    ide_file = bundle["ide_file"]

    require(profile["format"] == "lisp65-c2-l-full-product-profile-v1",
            "L-full product profile version drift")
    require(
        int(profile["bank2_static_code"]["headroom_bytes"]) ==
            65536 - expected
        and int(contract["physical_planes"]["code"]["static_use_bytes"]) ==
            expected
        and int(contract["physical_planes"]["code"]["gross_headroom_bytes"]) ==
            65536 - expected,
        "contract and L-full static-plane profile disagree",
    )
    require(header_value(header) == expected,
            "target static-plane header differs from canonical emission")
    require(
        decoder.count("LISP65_C2_LITE_STATIC_CODE_BYTES") == 2
        and '#include "c2_lite_static_plane.h"' in decoder
        and "34403UL" not in decoder
        and f"{expected}UL" not in decoder,
        "decoder rebuilt or bypassed the canonical static-plane pin",
    )
    static = receipt["c2d_v6"]["static_bank2"]
    require(
        receipt["status"] ==
            "passed-L-full-plus-published-nullary-six-image-product-and-C2D-v6-plane"
        and static["code_bytes"] == expected
        and static["headroom_bytes"] == 65536 - expected
        and static["code_sha256"] ==
            profile["bank2_static_code"]["sha256"]
        and receipt["six_image_product"]["entries"] ==
            profile["entries"]
        and receipt["six_image_product"]["images"] ==
            profile["images"],
        "canonical L-full product receipt and profile disagree",
    )
    ide_rows = [
        row for row in substitution["manifests"]
        if row["bytes"] == ide_file["bytes"]
        and row["sha256"] == ide_file["sha256"]
    ]
    require(
        substitution["product_build_id_hex"] ==
            profile["product_build_id"]
        and substitution["entries"] == profile["entries"]
        and len(ide_rows) == 1
        and ide_rows[0]["bytes"] == ide_file["bytes"]
        and ide_rows[0]["sha256"] == ide_file["sha256"]
        and int(ide["code_bytes"]) > 0
        and len(ide["entries"]) > 0,
        "L-full manifest/product identity drift",
    )
    return {
        "status": "passed-canonical-L-full-static-plane-to-target-dataflow",
        "static_code_bytes": expected,
        "bank2_headroom_bytes": 65536 - expected,
        "decoder_consumers": 2,
        "private_decoder_lengths": 0,
        "images": profile["images"],
        "entries": profile["entries"],
        "IDE_code_bytes": ide["code_bytes"],
        "IDE_entries": len(ide["entries"]),
    }


def source_bundle() -> dict[str, Any]:
    profile = load(PROFILE)
    require(
        profile["authority"]["kind"] ==
            "fresh-single-emitter-static-plane-dataflow",
        "static-plane profile does not name the public build authority")
    authority = profile["authority"]
    default_mode = (
        FRESH_PRODUCT == _HISTORICAL_DEFAULT_PRODUCT
        and FRESH_IDE == _HISTORICAL_DEFAULT_IDE
        and FRESH_BANK2 == _HISTORICAL_DEFAULT_BANK2
        and FRESH_MANIFESTS == _HISTORICAL_DEFAULT_MANIFESTS
    )
    if default_mode:
        product_path = ROOT / authority["product_manifest"]
        ide_path = ROOT / authority["compiled_ide_manifest"]
        bank2_path = ROOT / authority["bank2_static_plane"]
        substitution = load(product_path)
        manifest_paths = tuple(
            ROOT / row["path"] for row in substitution["manifests"])
    else:
        product_path = FRESH_PRODUCT
        ide_path = FRESH_IDE
        bank2_path = FRESH_BANK2
        manifest_paths = FRESH_MANIFESTS
        substitution = load(product_path)
    ide = load(ide_path)
    require(bank2_path.is_file(), "fresh Bank-2 static plane absent")
    code = bank2_path.read_bytes()
    receipt = {
        "status":
            "passed-L-full-plus-published-nullary-six-image-product-and-C2D-v6-plane",
        "authority": {
            "kind": "fresh-single-emitter-artifact-inventory",
            "current_manifests": [
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha(path),
                }
                for path in manifest_paths
            ],
        },
        "c2d_v6": {
            "static_bank2": {
                "code_bytes": len(code),
                "headroom_bytes": 65536 - len(code),
                "code_sha256": hashlib.sha256(code).hexdigest(),
            },
        },
        "six_image_product": {
            "entries": int(substitution["entries"]),
            "images": int(substitution["images"]),
        },
    }
    return {
        "profile": profile,
        "contract": load(CONTRACT),
        "header": HEADER.read_text(encoding="utf-8"),
        "decoder": DECODER.read_text(encoding="utf-8"),
        "receipt": receipt,
        "substitution": substitution,
        "ide": ide,
        "ide_file": {
            "path": ide_path.relative_to(ROOT).as_posix(),
            "bytes": ide_path.stat().st_size,
            "sha256": sha(ide_path),
        },
    }


def mutations(bundle: dict[str, Any]) -> list[str]:
    rejected: list[str] = []
    expected = int(bundle["profile"]["bank2_static_code"]["bytes"])

    def reject(label: str, mutate: Any) -> None:
        candidate = copy.deepcopy(bundle)
        mutate(candidate)
        try:
            validate(candidate)
        except GateError:
            rejected.append(label)
        else:
            raise GateError("mutation survived: " + label)

    reject("wrong-profile-length", lambda b:
           b["profile"]["bank2_static_code"].update(bytes=expected - 1))
    reject("wrong-contract-length", lambda b:
           b["contract"]["physical_planes"]["code"].update(
               static_use_bytes=expected - 1))
    reject("wrong-header-length", lambda b:
           b.update(header=b["header"].replace(
               f"{expected}UL", f"{expected - 1}UL")))
    reject("decoder-private-literal", lambda b:
           b.update(decoder=b["decoder"].replace(
               "LISP65_C2_LITE_STATIC_CODE_BYTES", f"{expected}UL", 1)))
    reject("wrong-emitted-length", lambda b:
           b["receipt"]["c2d_v6"]["static_bank2"].update(
               code_bytes=expected - 1))
    reject("wrong-code-identity", lambda b:
           b["receipt"]["c2d_v6"]["static_bank2"].update(
               code_sha256="0" * 64))
    reject("wrong-IDE-identity", lambda b:
           b["ide_file"].update(sha256="0" * 64))
    return rejected


def main() -> int:
    try:
        bundle = source_bundle()
        report = validate(bundle)
        rejected = mutations(bundle)
        require(len(rejected) == 7, "static-plane mutation count drift")
    except (GateError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-l-full-static-plane-gate: FAIL: " + str(error),
              file=sys.stderr)
        return 2
    print(
        "c2-l-full-static-plane-gate: PASS "
        f"bytes={report['static_code_bytes']} "
        f"headroom={report['bank2_headroom_bytes']} "
        f"mutations={len(rejected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
