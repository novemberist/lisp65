#!/usr/bin/env python3
"""Cross-check current product direct-entry resolutions against MK_BCODE."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_bcode_contract as B  # noqa: E402

BUILD = ROOT / "build/c2.2/direct-entry-contract"
SHELF = ROOT / "build/c2.2/substitution/product-shelf-v4-direct.bin"
C2D = ROOT / "build/c2.2/substitution/initial.c2d-v3.bin"
EXPECTED_GEOMETRY = {
    "images": 6, "entries": 588, "resolutions": 2264,
    "roots": 283, "images_offset": 48,
}
EXPECTED_DIRECT_REFS = 637
ARTIFACTS = ROOT / "build/c2.2/substitution/substitution-artifacts.json"
TARGET_CORE = ROOT / "scripts/c2-stream-v2-decoder.c"
TARGET_MAIN = ROOT / "scripts/c2-direct-entry-contract-main.c"
PHASE_08 = ROOT / "scripts/c2-stream-v2-phase-08.c"
PHASE_12 = ROOT / "scripts/c2-stream-v2-phase-12.c"
TARGET_DEFINES: tuple[str, ...] = ()
HOST_MODEL = ROOT / "tools/host-lisp/c2_gc_root_single_source.py"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-direct-entry-encoding-correction-contract-receipt.json")


class DirectEntryError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DirectEntryError(message)


def u16(data: bytes | bytearray, at: int) -> int:
    return struct.unpack_from("<H", data, at)[0]


def u24(data: bytes | bytearray, at: int) -> int:
    return data[at] | data[at + 1] << 8 | data[at + 2] << 16


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": len(data), "sha256": sha(data)}


def current_geometry(c2d: bytes) -> dict[str, int]:
    require(c2d[:8] == b"C2D\0\x03\x30\x20\x0a", "current C2D-v3 identity")
    values = {
        "images": u16(c2d, 12), "entries": u16(c2d, 16),
        "resolutions": u16(c2d, 20), "roots": u16(c2d, 24),
        "images_offset": u16(c2d, 28),
    }
    require(values == EXPECTED_GEOMETRY,
            f"current C2D-v3 census drift: {values}")
    return values


def normalized_c2d(c2d: bytes, geometry: dict[str, int]) -> bytes:
    image_bytes = geometry["images"] * 20
    resolutions_offset = 32 + image_bytes
    total = resolutions_offset + geometry["resolutions"] * 2 + geometry["roots"] * 2
    result = bytearray(total)
    for slot in range(geometry["images"]):
        source = geometry["images_offset"] + slot * 32
        target = 32 + slot * 20
        result[target] = slot
        result[target + 1] = 0
        result[target + 2:target + 10] = c2d[source + 6:source + 14]
        result[target + 10:target + 13] = c2d[source + 18:source + 21]
        result[target + 13:target + 16] = c2d[source + 23:source + 26]
        result[target + 16:target + 18] = c2d[source + 21:source + 23]
        result[target + 18:target + 20] = c2d[source + 26:source + 28]
    return bytes(result)


def descriptor_rows(shelf: bytes, c2d: bytes,
                    geometry: dict[str, int]) -> list[dict[str, int]]:
    rows: list[dict[str, int]] = []
    for slot in range(geometry["images"]):
        at = geometry["images_offset"] + slot * 32
        directory_base, entries = u16(c2d, at + 6), u16(c2d, at + 8)
        resolution_base, resolutions = u16(c2d, at + 10), u16(c2d, at + 12)
        metadata = u24(c2d, at + 23)
        require(metadata + 24 <= len(shelf), "image metadata header range")
        literal_count, literal_offset = u16(shelf, metadata + 12), u16(shelf, metadata + 16)
        require(literal_count == resolutions, "image descriptor count/C2D drift")
        for local_resolution in range(literal_count):
            desc = metadata + literal_offset + local_resolution * 8
            require(desc + 8 <= len(shelf), "descriptor range")
            if shelf[desc] != 4:
                continue
            local_entry = u16(shelf, desc + 2)
            require(local_entry < entries, "entry descriptor local range")
            rows.append({
                "image": slot,
                "directory_base": directory_base,
                "local_entry": local_entry,
                "global_entry": directory_base + local_entry,
                "global_resolution": resolution_base + local_resolution,
            })
    require(len(rows) == EXPECTED_DIRECT_REFS,
            f"direct-entry census drift: {len(rows)}")
    return rows


def source_single_truth_gate() -> dict[str, Any]:
    target = TARGET_CORE.read_text(encoding="utf-8")
    host = HOST_MODEL.read_text(encoding="utf-8")
    phase8 = target[target.index("#if C2_STREAM_V2_PHASE == 8"):
                    target.index("#if C2_STREAM_V2_PHASE == 9")]
    require(phase8.count("MK_BCODE(") == 1,
            "target phase 8 must call MK_BCODE exactly once")
    require("0xc000u +" not in phase8 and "0xC000 +" not in phase8,
            "target phase 8 contains hand-rolled BCODE tag arithmetic")
    direct = host[host.index("def direct_value("):host.index("def build_v2(")]
    require("B.mk_bcode(directory_base + descriptor.arg0)" in direct,
            "host direct-value model does not call the ABI bridge")
    require("0xC000 +" not in direct and "0xc000 +" not in direct,
            "host direct-value model contains hand-rolled BCODE tag arithmetic")
    return {
        "target_phase8_mk_bcode_calls": 1,
        "target_hand_rolled_tag_arithmetic": 0,
        "host_abi_bridge_calls": 1,
        "host_hand_rolled_tag_arithmetic": 0,
    }


def compile_and_run(geometry: dict[str, int], normalized: Path,
                    resolved: Path) -> dict[str, Any]:
    executable = BUILD / "c2-direct-entry-contract-host"
    command = [
        "cc", "-std=c99", "-Os", "-Wall", "-Wextra", "-Werror",
        "-I", str(ROOT / "scripts"), "-I", str(ROOT / "src"),
        f"-DEXPECTED_IMAGES={geometry['images']}",
        f"-DEXPECTED_ENTRIES={geometry['entries']}",
        f"-DEXPECTED_RESOLUTIONS={geometry['resolutions']}",
        f"-DEXPECTED_ROOTS={geometry['roots']}",
        f"-DEXPECTED_DIRECT_REFS={EXPECTED_DIRECT_REFS}",
        *(f"-D{name}=1" for name in TARGET_DEFINES),
        str(PHASE_08), str(PHASE_12), str(TARGET_MAIN), "-o", str(executable),
    ]
    built = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                           check=False)
    require(built.returncode == 0 and not built.stdout and not built.stderr,
            "target contract harness did not compile cleanly: "
            + (built.stderr or built.stdout).strip())
    ran = subprocess.run(
        [str(executable), str(SHELF), str(normalized), str(resolved)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    require(ran.returncode == 0 and not ran.stderr, "target contract harness failed: "
            + (ran.stderr or ran.stdout).strip())
    match = re.fullmatch(
        r"c2-direct-entry-target: PASS refs=(\d+) range=([0-9a-f]{4})\.\."
        r"([0-9a-f]{4}) fixnums=0 negatives=(\d+)\n?", ran.stdout)
    require(match is not None and tuple(map(int, (match.group(1), match.group(4))))
            == (EXPECTED_DIRECT_REFS, 4), "target contract harness output")
    return {"compiler": command[0], "stdout": ran.stdout.strip(),
            "direct_refs": EXPECTED_DIRECT_REFS,
            "target_negative_classes": 4,
            "minimum_value": int(match.group(2), 16),
            "maximum_value": int(match.group(3), 16)}


def collect() -> dict[str, Any]:
    shelf, c2d = SHELF.read_bytes(), C2D.read_bytes()
    geometry = current_geometry(c2d)
    rows = descriptor_rows(shelf, c2d, geometry)
    BUILD.mkdir(parents=True, exist_ok=True)
    normalized = BUILD / "normalized-direct-entry-plane.bin"
    resolved = BUILD / "target-resolved-direct-entry-plane.bin"
    normalized_data = normalized_c2d(c2d, geometry)
    if normalized.exists():
        require(normalized.read_bytes() == normalized_data,
                "pinned normalized direct-entry plane drift")
        with tempfile.TemporaryDirectory(prefix="lisp65-c2-direct-entry-") as raw:
            work_normalized = Path(raw) / normalized.name
            work_resolved = Path(raw) / resolved.name
            work_normalized.write_bytes(normalized_data)
            target = compile_and_run(geometry, work_normalized, work_resolved)
            resolved_data = work_resolved.read_bytes()
        require(resolved.is_file() and resolved.read_bytes() == resolved_data,
                "pinned target-resolved direct-entry plane drift")
    else:
        normalized.write_bytes(normalized_data)
        target = compile_and_run(geometry, normalized, resolved)
        resolved_data = resolved.read_bytes()
    resolution_offset = 32 + geometry["images"] * 20
    per_image: Counter[int] = Counter()
    values: list[int] = []
    for row in rows:
        value = u16(resolved_data, resolution_offset + row["global_resolution"] * 2)
        B.require_published_entry(value, row["global_entry"])
        values.append(value); per_image[row["image"]] += 1
    require(not any(value & 1 for value in values),
            "published direct-entry value decodes as Fixnum")
    require(min(values) >= 0xC000 and max(values) <= 0xDFFE,
            "published direct-entry value outside contract range")
    source_gate = source_single_truth_gate()
    mutation_matrix = B.mutation_selftest()
    require(list(mutation_matrix.values()).count("rejected") == 4,
            "host mutation matrix")
    report = {
        "format": "lisp65-c2-direct-entry-encoding-correction-contract-receipt-v1",
        "recorded_on": "2026-07-20",
        "status": "passed-contract-and-cross-parity-probe-only",
        "bindings": {
            "abi_constructor": B.source_binding(),
            "abi_bridge": bind(ROOT / "tools/host-lisp/c2_bcode_contract.py"),
            "target_decoder": bind(TARGET_CORE),
            "target_contract_harness": bind(TARGET_MAIN),
            "host_model": bind(HOST_MODEL),
            "product_shelf": bind(SHELF),
            "initial_c2d": bind(C2D),
            "substitution_artifacts": bind(ARTIFACTS),
            "normalized_plane": bind(normalized),
            "target_resolved_plane": bind(resolved),
        },
        "single_truth": source_gate,
        "cross_parity": {
            "images": geometry["images"],
            "entries": geometry["entries"],
            "resolutions": geometry["resolutions"],
            "direct_entry_references": len(rows),
            "per_image": {str(key): per_image[key] for key in sorted(per_image)},
            "minimum_published_value": f"0x{min(values):04x}",
            "maximum_published_value": f"0x{max(values):04x}",
            "contract_range": "0xc000..0xdffe",
            "fixnum_decodable_published_values": 0,
            "target_phase12_negative_classes": target["target_negative_classes"],
            "host_constructor_negative_matrix": mutation_matrix,
        },
        "target_execution": target,
        "claim_limit": (
            "Host execution of the current target phase-8 and phase-12 C code plus "
            "an exact direct-reference cross-check against the src/obj.h MK_BCODE ABI. "
            "This is not a product link, device run, capacity authorization, "
            "promotion or release claim. Historical C2.1 receipts remain unchanged."
        ),
        "next_gate": "Owner-authorized product-shaped capacity and placement probe.",
    }
    return report


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument(
        "action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    try:
        value = collect(); data = canonical(value)
        if args.action == "write":
            RECEIPT.parent.mkdir(parents=True, exist_ok=True)
            RECEIPT.write_bytes(data); verb = "WROTE"
        elif args.action == "check":
            require(RECEIPT.is_file() and RECEIPT.read_bytes() == data,
                    "direct-entry correction receipt drift")
            verb = "PASS"
        else:
            verb = "SELFTEST PASS"
        print("c2-direct-entry-contract: " + verb
              + f" refs={EXPECTED_DIRECT_REFS} "
              "fixnums=0 target-negatives=4")
        return 0
    except (OSError, ValueError, subprocess.SubprocessError,
            DirectEntryError, B.BcodeContractError) as error:
        print(f"c2-direct-entry-contract: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
