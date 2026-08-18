#!/usr/bin/env python3
"""Attribute the Link-105 phase-02b 104-byte C2D extent mismatch.

This is a host-only attribution gate.  It binds the six current C2D code
rows to their Shelf payloads and candidate code-plane manifest, proves the
Link-96 -> Link-97 delta per slice, reproduces the header selected by the
real compiler include order, and separates that delta from the later mapped
far-service delivery.  It neither repairs nor rebuilds the product.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
PREDECESSOR = EVIDENCE / (
    "c2.3-v2.0-source-oracle-link105-phase02a-dynamic-rescue-receipt.json")
FAR_RECEIPT = EVIDENCE / "c2.3-v2.0-far-payload-delivery-closure-receipt.json"
RECEIPT = EVIDENCE / (
    "c2.3-v2.0-link105-phase02b-extent-attribution-receipt.json")

CURRENT_ROOT = ROOT / (
    "build/c2.3/v2.0-source-oracle-replacement3-card/static-plane/"
    "narrow-static/product")
CURRENT_V6 = ROOT / (
    "build/c2.3/v2.0-source-oracle-replacement3-card/static-plane/"
    "narrow-static/v6-semantics/initial.c2d-v6.bin")
CURRENT_PLANE = ROOT / (
    "build/c2.3/v2.0-source-oracle-replacement3-card/final/"
    "fresh-c2-lite-prelink-gates/v6-semantics/bank2-static-code.bin")
CURRENT_MANIFEST = ROOT / (
    "build/c2.3/v2.0-source-oracle-replacement3-card/"
    "canonical-product-manifest.json")
PREVIOUS_ROOT = ROOT / (
    "build/c2.3/terminal-return-guard-link96/static-plane/"
    "narrow-static/product")
PREVIOUS_PLANE = ROOT / (
    "build/c2.3/terminal-return-guard-link96/final/"
    "fresh-c2-lite-prelink-gates/v6-semantics/bank2-static-code.bin")
CANDIDATE_HEADER = ROOT / (
    "build/c2.3/v2.0-ownership-recharter-inputs/c2_lite_static_plane.h")
HISTORICAL_HEADER = ROOT / "src/c2_lite_static_plane.h"
LINK_DRIVER = ROOT / "tools/host-lisp/c2_product_substitution_link.py"
PHASE02B = ROOT / (
    "build/c2.3/v2.0-source-oracle-replacement3-card/final/"
    "generated-product-sources/c2-stream-phase-02b.c")
COMPILER = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
COMPILER_BINARY = ROOT / "tools/llvm-mos/bin/clang-23"
FAR_PLANE = ROOT / (
    "build/c2.3/v2.0-far-payload-delivery/product-inputs/"
    "bank2-static-code.bin")
DRIVER = Path(__file__).resolve()
ATTRIBUTION_COMMIT = "d4fab946"

FORMAT = "lisp65-c2.3-v20-link105-phase02b-extent-attribution-v1"
STATUS = (
    "PHASE02B-CONTRACT-SHORT-BY-104; "
    "AUTHORITATIVE-CODE-PLANE=46043")
AUTHORIZATION_COMMIT = "0888143d"
AUTHORIZATION_BYTES = 61975
AUTHORIZATION_SHA256 = (
    "2e48422f5d1c04bd28f1697ebd80e6024f0b9f585c89c035a8536b0bdf7446c4")

NAMES = ("stdlib-p0", "ide", "idex", "m65d", "buffer", "lcc")
EXPECTED = {
    "predecessor": "22962cbd4bc5c158a61569a878ba34cb8150144dc0aa347cb903632676b8279b",
    "far_receipt": "db111b95ca62bb22185a4b3831591a9fe968d62f74ec83e4223b15af2e05f254",
    "current_c2d": "d576a0ffbff91737f32c29f8cd69f6ee4af1696adeb01741bcab27d8b6043c19",
    "current_plane": "a241a8c23a5cc8d7f7525ed2f1f522ca41f103c28928a2636a58c1972ba7e7de",
    "previous_plane": "dc02b18be46f96f2b4e72d6502d4c193ee0dcbee4ee0abf4ca1ebd27f1b7a16d",
    "candidate_header": "f58bc7a13282e468489945363306918e84d7fcc17c8fa064bd300fa223fb0e37",
    "historical_header": "3c97cc22b1a53ac781614ae8c9ab8c56998ac44c6ca824fa41f857e8495bdf59",
    "manifest": "7a065f2a8089eb7362a5d6f757f061d334a8777f112776cf0da158157cf2bc8d",
    "far_plane": "94479944eb6f8ece405be2902a424961b72e1936534ecd6acb0e8a2287a9c4ec",
    "link_driver": "77194a61522f0cf800985382dc12c33fcc0ec2eb2962d1d0fae1cd886f256015",
    "phase02b": "d5f499dd7a66a84406a8e479d94e47dd0879e87b19ebd9721fd5e104fb4e6ef9",
    "compiler": "2a831e2abeabb9c6e0605a197ff39903c1326b528f82a7f787bc353ef652309c",
}


class ExtentError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ExtentError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path, expected: str | None = None) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"file absent: {path}")
    raw = path.read_bytes()
    value = {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
             "sha256": digest(raw)}
    if expected is not None:
        require(value["sha256"] == expected, f"identity drift: {path}")
    return value


def historical_bind(path: Path, expected: str) -> dict[str, Any]:
    """Bind the exact source that produced this historical attribution."""
    name = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{ATTRIBUTION_COMMIT}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    value = {"path": name, "bytes": len(raw), "sha256": digest(raw)}
    require(value["sha256"] == expected,
            f"historical attribution source drift: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(canonical(value))
    temporary.replace(path)


def authorization() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{AUTHORIZATION_COMMIT}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION_COMMIT}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    require(len(raw) == AUTHORIZATION_BYTES and digest(raw) == AUTHORIZATION_SHA256,
            "phase02b attribution authorization drift")
    for token in (
            b"Phase 02b: the 104-byte extent mismatch",
            b"six C2D",
            b"code rows deliver 46,043 bytes",
            b"48,156 \xe2\x88\x92 46,043 = 2,113",
            b"single owner",
            b"No fix, card or media change before the number is attributed"):
        require(token in raw, f"authorization token absent: {token!r}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": digest(raw)}


def header_value(path: Path) -> int:
    values = re.findall(
        r"^#define LISP65_C2_LITE_STATIC_CODE_BYTES ([0-9]+)UL$",
        path.read_text(encoding="utf-8"), re.MULTILINE)
    require(len(values) == 1, f"static extent macro drift: {path}")
    return int(values[0])


def c2d_rows(raw: bytes) -> list[dict[str, Any]]:
    require(len(raw) == 33840 and raw[:4] == b"C2D\0",
            "candidate initial C2D shape drift")
    offset = struct.unpack_from("<H", raw, 28)[0]
    require(offset == 48, "C2D image table offset drift")
    rows: list[dict[str, Any]] = []
    for index, name in enumerate(NAMES):
        row = raw[offset + index * 32:offset + (index + 1) * 32]
        require(len(row) == 32 and row[2] == index,
                f"C2D row identity drift: {name}")
        rows.append({
            "name": name,
            "row": index,
            "source_offset": int.from_bytes(row[18:21], "little"),
            "code_bytes": int.from_bytes(row[21:23], "little"),
            "raw_hex": row.hex(),
        })
    return rows


def code_files(root: Path) -> list[tuple[str, bytes]]:
    return [(name, (root / f"{name}.code.bin").read_bytes()) for name in NAMES]


def extent_gate(rows: list[dict[str, Any]], source: bytes,
                files: list[tuple[str, bytes]], contract_bytes: int,
                plane: bytes) -> dict[str, Any]:
    """Single owner: the rows and contract both derive from the same slices."""
    require([row["name"] for row in rows] == list(NAMES),
            "C2D code-row vocabulary drift")
    require([name for name, _ in files] == list(NAMES),
            "code-plane slice vocabulary drift")
    require(len(rows) == len(files) == 6, "six code slices required")
    cursor = rows[0]["source_offset"]
    for row, (name, raw) in zip(rows, files):
        require(row["name"] == name, f"slice owner drift: {name}")
        require(row["source_offset"] == cursor, f"C2D source extent gap: {name}")
        require(row["code_bytes"] == len(raw), f"row length drift: {name}")
        require(source[cursor:cursor + len(raw)] == raw,
                f"C2D source payload differs: {name}")
        cursor += len(raw)
    derived = b"".join(raw for _, raw in files)
    require(derived == plane, "candidate plane differs from six owned slices")
    require(contract_bytes == len(derived),
            "linked extent is not derived from the owned code-plane slices")
    return {
        "single_owner": "six candidate code-plane slices",
        "code_bytes": len(derived),
        "sha256": digest(derived),
        "source_start": rows[0]["source_offset"],
        "source_end_exclusive": cursor,
    }


def mutation_gate(rows: list[dict[str, Any]], source: bytes,
                  files: list[tuple[str, bytes]], plane: bytes) -> list[str]:
    cases: dict[str, Callable[[], None]] = {}
    cases["historical-contract-45939"] = lambda: extent_gate(
        rows, source, files, 45939, plane)
    cases["full-delivery-contract-48156"] = lambda: extent_gate(
        rows, source, files, 48156, plane)
    cases["gap-counted-as-code"] = lambda: extent_gate(
        rows, source, files, 47282, plane)
    cases["service-counted-as-code"] = lambda: extent_gate(
        rows, source, files, 46917, plane)

    def omit_last() -> None:
        extent_gate(rows[:-1], source, files[:-1], 46043, plane)
    cases["omitted-code-row"] = omit_last

    def old_stdlib() -> None:
        trial = deepcopy(files)
        trial[0] = (trial[0][0], (PREVIOUS_ROOT / "stdlib-p0.code.bin").read_bytes())
        extent_gate(rows, source, trial, 46043, plane)
    cases["old-stdlib-under-current-world"] = old_stdlib

    def inflate_row() -> None:
        trial = deepcopy(rows); trial[0]["code_bytes"] += 104
        extent_gate(trial, source, files, 46043, plane)
    cases["medium-row-inflated-by-104"] = inflate_row

    def swap_rows() -> None:
        trial = deepcopy(rows); trial[3], trial[4] = trial[4], trial[3]
        extent_gate(trial, source, files, 46043, plane)
    cases["slice-order-owner-drift"] = swap_rows

    rejected: list[str] = []
    for name, run in cases.items():
        try:
            run()
        except ExtentError:
            rejected.append(name)
    require(rejected == list(cases), "single-owner extent mutation survived")
    return rejected


def preprocess_value(extra_first: Path | None = None) -> int:
    command = [
        str(COMPILER), "-E", "-dM",
        "-DLISP65_C2_LITE_BANK2_STAGING",
        "-DLISP65_C2_PRODUCT_CUT", "-DC2_STREAM_PRODUCT_V3=1",
        "-DLISP65_C2_PRODUCT_BUILD_ID=0x0401e53eUL",
    ]
    if extra_first is not None:
        command.extend(["-I", extra_first.relative_to(ROOT).as_posix()])
    command.extend([
        "-I", "src", "-I", "scripts", "-I", "build/c2.2/substitution",
        "-I", "build/c2.3/v2.0-source-oracle-replacement3-card/final",
        "-I", "build/bytecode", PHASE02B.relative_to(ROOT).as_posix(),
    ])
    output = subprocess.run(command, cwd=ROOT, check=True, text=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE).stdout
    matches = re.findall(
        r"^#define LISP65_C2_LITE_STATIC_CODE_BYTES ([0-9]+)UL$",
        output, re.MULTILINE)
    require(len(matches) == 1, "preprocessor extent macro absent/ambiguous")
    return int(matches[0])


def compiler_consumption() -> dict[str, Any]:
    source = LINK_DRIVER.read_text(encoding="utf-8")
    tokens = [
        '"-I", checkout_arg(ROOT / "src")',
        '"-I", checkout_arg(ROOT / "scripts")',
        '"-I", checkout_arg(ROOT / "build/c2.2/substitution")',
        '"-I", checkout_arg(out)',
        '"-I", checkout_arg(ROOT / "build/bytecode")',
        "for directory in EXTRA_INCLUDE_DIRS:",
    ]
    positions = [source.find(token) for token in tokens]
    require(all(value >= 0 for value in positions)
            and positions == sorted(positions), "real compiler include order drift")
    require("EXTRA_INCLUDE_DIRS: tuple[Path, ...] = ()" in source,
            "default extra include authority drift")
    production = preprocess_value()
    owner_first = preprocess_value(CANDIDATE_HEADER.parent)
    require(production == 45939 and owner_first == 46043,
            "compiler consumption reproduction drift")
    return {
        "actual_production_include_order_macro": production,
        "candidate_owner_first_counterfactual_macro": owner_first,
        "bound_candidate_header_was_force_included": False,
        "mechanism": (
            "the card bound a correct build-local candidate header, but the real "
            "consumer searched src first and compiled the historical tracked header"),
        "classification": "BOUND-NOT-CONSUMED; REAL-CONSUMER-INPUT-DRIFT",
    }


def result() -> dict[str, Any]:
    authority = authorization()
    predecessor = bind(PREDECESSOR, EXPECTED["predecessor"])
    far_receipt_binding = bind(FAR_RECEIPT, EXPECTED["far_receipt"])
    current_c2d_binding = bind(CURRENT_V6, EXPECTED["current_c2d"])
    current_plane_binding = bind(CURRENT_PLANE, EXPECTED["current_plane"])
    previous_plane_binding = bind(PREVIOUS_PLANE, EXPECTED["previous_plane"])
    candidate_header_binding = bind(CANDIDATE_HEADER, EXPECTED["candidate_header"])
    historical_header_binding = bind(HISTORICAL_HEADER, EXPECTED["historical_header"])
    manifest_binding = bind(CURRENT_MANIFEST, EXPECTED["manifest"])
    far_plane_binding = bind(FAR_PLANE, EXPECTED["far_plane"])
    link_driver_binding = historical_bind(
        LINK_DRIVER, EXPECTED["link_driver"])
    phase02b_binding = bind(PHASE02B, EXPECTED["phase02b"])
    compiler_binding = bind(COMPILER_BINARY, EXPECTED["compiler"])
    compiler_binding["invoked_as"] = COMPILER.relative_to(ROOT).as_posix()

    c2d = CURRENT_V6.read_bytes()
    rows = c2d_rows(c2d)
    current_files = code_files(CURRENT_ROOT)
    previous_files = code_files(PREVIOUS_ROOT)
    plane = CURRENT_PLANE.read_bytes()
    candidate_value = header_value(CANDIDATE_HEADER)
    historical_value = header_value(HISTORICAL_HEADER)
    require(candidate_value == 46043 and historical_value == 45939,
            "header value attribution drift")
    owned = extent_gate(rows, plane, current_files, candidate_value, plane)
    mutations = mutation_gate(rows, plane, current_files, plane)

    manifest = load(CURRENT_MANIFEST)
    roles = [row for row in manifest["artifacts"]
             if row.get("role") == "c2-bank2-static-code-plane"]
    require(roles == [{**current_plane_binding,
                       "role": "c2-bank2-static-code-plane"}],
            "candidate manifest code-plane authority drift")

    slice_delta: list[dict[str, Any]] = []
    for (name, old), (_, new) in zip(previous_files, current_files):
        slice_delta.append({
            "name": name, "link96_bytes": len(old), "link97_bytes": len(new),
            "delta_bytes": len(new) - len(old),
            "link96_sha256": digest(old), "link97_sha256": digest(new),
            "byteidentical": old == new,
        })
    require(sum(row["delta_bytes"] for row in slice_delta) == 104,
            "Link96-to-Link97 plane delta drift")
    require(slice_delta[0]["delta_bytes"] == 104
            and all(row["delta_bytes"] == 0 and row["byteidentical"]
                    for row in slice_delta[1:]),
            "104-byte delta is no longer isolated to stdlib-p0")
    require(len(PREVIOUS_PLANE.read_bytes()) == 45939
            and len(plane) == 46043,
            "world plane extent drift")

    far = load(FAR_RECEIPT)["materialization"]
    delivered = FAR_PLANE.read_bytes()
    require(far["source_bytes_preserved"] == len(plane) == 46043
            and far["zero_padding_bytes"] == 1239
            and far["payload_bytes"] == 874
            and far["delivered_bytes"] == len(delivered) == 48156,
            "far-delivery arithmetic drift")
    require(delivered[:len(plane)] == plane,
            "far delivery did not preserve candidate code plane")
    require(delivered[len(plane):len(plane) + 1239] == bytes(1239),
            "far-delivery gap is not the recorded zero padding")
    require(48156 - 46043 == 2113 == 1239 + 874,
            "far-delivery correlation arithmetic drift")

    consumption = compiler_consumption()
    row_summary = [{
        **row,
        "code_sha256": digest(current_files[index][1]),
        "source_plane_identity": True,
    } for index, row in enumerate(rows)]
    return {
        "format": FORMAT,
        "status": STATUS,
        "recorded_on": "2026-08-13",
        "authority": authority,
        "inputs": {
            "predecessor": predecessor,
            "current_c2d": current_c2d_binding,
            "current_plane": current_plane_binding,
            "previous_plane": previous_plane_binding,
            "candidate_header": candidate_header_binding,
            "historical_header": historical_header_binding,
            "candidate_manifest": manifest_binding,
            "far_delivery_receipt": far_receipt_binding,
            "far_delivery_plane": far_plane_binding,
            "real_link_driver": link_driver_binding,
            "phase02b_real_consumer": phase02b_binding,
            "compiler": compiler_binding,
            "attribution_driver": historical_bind(
                DRIVER, "bbe353bd53e0623b324aee459e9183acb4ba33f2d44cf324e3e6902490cb108a"),
        },
        "authoritative_extent": {
            "value_bytes": 46043,
            "owner": "the six current candidate code-plane slices",
            "derivation": "17238 + 13544 + 2940 + 4083 + 104 + 8134",
            "c2d_rows": row_summary,
            "single_owner_gate": owned,
            "candidate_manifest_agrees": True,
            "candidate_build_local_header_agrees": True,
            "medium_has_104_excess_bytes": False,
        },
        "historical_world_delta": {
            "link96_code_plane_bytes": 45939,
            "link97_code_plane_bytes": 46043,
            "delta_bytes": 104,
            "per_slice": slice_delta,
            "finding": (
                "all 104 bytes are stdlib-p0 growth before far-payload delivery; "
                "the other five slices are byteidentical"),
        },
        "linked_contract_attribution": {
            "observed_target_contract_bytes": 45939,
            "short_by_bytes": 104,
            "correct_candidate_header_bytes": 46043,
            "real_consumer": consumption,
            "finding": (
                "the linked contract is short: a correct build-local projection "
                "was bound but not consumed by the real compile"),
        },
        "far_payload_correlation": {
            "correlated": False,
            "code_plane_bytes_before_far_delivery": 46043,
            "zero_gap_bytes": 1239,
            "mapped_far_service_bytes": 874,
            "full_delivered_extent_bytes": 48156,
            "arithmetic": "48156 - 46043 = 2113 = 1239 + 874",
            "finding": (
                "far delivery preserves the already-grown 46043-byte plane "
                "byte-for-byte, then adds only its 1239-byte gap and 874-byte "
                "service; it neither creates nor explains the 104-byte delta"),
        },
        "mutations_rejected": mutations,
        "decision": {
            "which_side_is_right": "media/C2D: 46043 bytes",
            "which_side_is_wrong": "linked phase02b contract: 45939 bytes",
            "mechanism": (
                "historical workspace header selected by real compiler include "
                "order despite correct candidate-local header being bound"),
            "permanent_rule": (
                "extent metadata and every real consumer derive from one bound "
                "candidate code-plane owner; binding an input without proving "
                "real-consumer selection is red"),
        },
        "claim_limit": (
            "Host/ELF attribution only. Phase 02a remains exonerated. This "
            "receipt performs no fix, card, product build, media change or "
            "device access; D2-D5 remain closed and the CPU remains stopped."),
    }


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in {"selftest", "record", "check"},
            "usage: c2_v20_phase02b_extent_attribution.py selftest|record|check")
    value = result()
    if sys.argv[1] == "selftest":
        print(f"Link-105 phase02b extent attribution: SELFTEST PASS "
              f"mutations={len(value['mutations_rejected'])}")
    elif sys.argv[1] == "record":
        write_json(RECEIPT, value)
        print("Link-105 phase02b extent attribution: RECORD PASS "
              "authoritative=46043 stale-contract=45939 delta=104")
    else:
        require(load(RECEIPT) == value, "phase02b extent receipt replay drift")
        print("Link-105 phase02b extent attribution: CHECK PASS "
              "medium=correct contract=short-by-104")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ExtentError, OSError, ValueError, KeyError, IndexError,
            json.JSONDecodeError, struct.error,
            subprocess.CalledProcessError) as error:
        print(f"LINK-105 PHASE02B EXTENT ATTRIBUTION: {error}", file=sys.stderr)
        raise SystemExit(1)
