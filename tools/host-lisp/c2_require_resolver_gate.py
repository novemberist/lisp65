#!/usr/bin/env python3
"""Qualify the target-shaped cold require resolver and its L65I-v1 index."""

from __future__ import annotations

import binascii
import copy
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from typing import Any, Callable
import zlib


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_full_emission as F  # noqa: E402
import c2_session_extension_probe as S  # noqa: E402
import d81_persistence_fault as D81  # noqa: E402


CONTRACT = ROOT / "config/c2-require-resolver-contract.json"
NOTE = ROOT / "docs/planning/c2.2-require-resolver-product-probe.md"
RAMP = ROOT / "config/c2.2-workbench-era-ramp.json"
HOST_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-require-manifest-v1-host-probe-receipt.json")
LISP = ROOT / "lib/stdlib-require.lisp"
RUNTIME = ROOT / "src/c2_product_runtime.c"
VM = ROOT / "src/vm.c"
LEAF = ROOT / "src/vm_c2d_byte.s"
SUITE = ROOT / "tests/bytecode/libs/p0-stdlib-require-resolver.json"
BUILD = ROOT / "build/post-promotion/require-resolver/l65i-v1"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-require-resolver-source-index-gate-receipt.json")
HOST_PROBE = ROOT / "tools/host-lisp/c2_require_manifest_v1_probe.py"

HEADER_BYTES = 32
ROW_BYTES = 48
MAX_ROWS = 32
MAX_DEPS = 8
SOURCE_BANK2 = 2
CAPACITY = (65536, 64, 2048, 4096, 1536, 14544)
BASELINE = (34990, 6, 602, 2299, 283, 0)
LIBRARIES = (
    ("room", ROOT / "build/bytecode/dialect-v2/libs/room.manifest.json", ()),
    ("buffer", ROOT / "build/bytecode/dialect-v2/libs/buffer.manifest.json", (0,)),
)


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"artifact absent: {path}")
    data = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": sha_bytes(data),
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def crc16(data: bytes) -> int:
    return binascii.crc_hqx(data, 0xFFFF)


def measured_row(name: str, manifest: Path, dependencies: tuple[int, ...],
                 track: int, sector: int, *,
                 artifact_build_id: int = S.PROBE_BUILD_ID
                 ) -> tuple[dict[str, Any], bytes]:
    image = F.emit_image(name, name, manifest)
    artifact = S.build_extension(image, build_id=artifact_build_id)
    decoded = S.decode_extension(
        artifact, image, expected_build_id=artifact_build_id)
    exports = sum(not bool(row.get("anonymous", False))
                  for row in image.manifest["entries"])
    roots = sum(desc.kind in S.ROOT_KINDS for desc in image.descriptors)
    values = {
        "name": name,
        "track": track,
        "sector": sector,
        "combined_crc32": decoded.combined_crc,
        "dependencies": list(dependencies),
        "execution_source": SOURCE_BANK2,
        "artifact_bytes": len(artifact),
        "bank2": len(image.code),
        "images": 1,
        "entries": len(image.manifest["entries"]),
        "resolutions": len(image.descriptors),
        "roots": roots,
        "scratch": exports * 8,
    }
    return values, artifact


def encode_row(row: dict[str, Any]) -> bytes:
    name = row["name"].encode("ascii")
    require(1 <= len(name) <= 16 and name.decode() == row["name"].lower(),
            "noncanonical L65I name")
    dependencies = row["dependencies"]
    require(len(dependencies) <= MAX_DEPS, "dependency width")
    data = bytearray(ROW_BYTES)
    data[:16] = name + bytes(16 - len(name))
    data[16] = row["track"]
    data[17] = row["sector"]
    struct.pack_into("<I", data, 18, row["combined_crc32"])
    data[22] = len(dependencies)
    data[23:31] = bytes(dependencies) + bytes(
        [0xFF] * (MAX_DEPS - len(dependencies)))
    data[31] = row["execution_source"]
    struct.pack_into("<H", data, 32, row["artifact_bytes"])
    struct.pack_into("<H", data, 34, row["bank2"])
    data[36] = row["images"]
    struct.pack_into("<H", data, 37, row["entries"])
    struct.pack_into("<H", data, 39, row["resolutions"])
    struct.pack_into("<H", data, 41, row["roots"])
    struct.pack_into("<H", data, 43, row["scratch"])
    struct.pack_into("<H", data, 45, crc16(data[:45]))
    return bytes(data)


def encode_index(rows: list[dict[str, Any]]) -> bytes:
    records = b"".join(encode_row(row) for row in rows)
    header = bytearray(HEADER_BYTES)
    header[:4] = b"L65I"
    header[4:9] = bytes((1, HEADER_BYTES, ROW_BYTES, MAX_DEPS, len(rows)))
    struct.pack_into("<H", header, 9, len(records))
    struct.pack_into("<H", header, 11, crc16(records))
    struct.pack_into("<I", header, 13, zlib.crc32(records) & 0xFFFFFFFF)
    struct.pack_into("<H", header, 17, crc16(header[:17]))
    return bytes(header) + records


def decode_index(data: bytes, artifacts: dict[str, bytes] | None = None, *,
                 artifact_build_id: int = S.PROBE_BUILD_ID
                 ) -> list[dict[str, Any]]:
    require(len(data) >= HEADER_BYTES, "index-truncated")
    header = data[:HEADER_BYTES]
    require(header[:4] == b"L65I", "index-magic")
    require(header[4] == 1, "index-version")
    require(header[5:8] == bytes((HEADER_BYTES, ROW_BYTES, MAX_DEPS)),
            "index-widths")
    count = header[8]
    require(1 <= count <= MAX_ROWS, "index-count")
    records_bytes = struct.unpack_from("<H", header, 9)[0]
    require(records_bytes == count * ROW_BYTES, "index-record-bytes")
    require(len(data) == HEADER_BYTES + records_bytes, "index-length")
    records = data[HEADER_BYTES:]
    require(crc16(records) == struct.unpack_from("<H", header, 11)[0],
            "index-record-crc")
    require((zlib.crc32(records) & 0xFFFFFFFF)
            == struct.unpack_from("<I", header, 13)[0],
            "index-identity")
    require(crc16(header[:17]) == struct.unpack_from("<H", header, 17)[0],
            "index-header-crc")
    require(header[19:] == bytes(13), "index-header-reserved")
    rows: list[dict[str, Any]] = []
    for ordinal in range(count):
        raw = records[ordinal * ROW_BYTES:(ordinal + 1) * ROW_BYTES]
        require(crc16(raw[:45]) == struct.unpack_from("<H", raw, 45)[0],
                "index-row-crc")
        require(raw[47] == 0, "index-row-reserved")
        zero = raw[:16].find(b"\0")
        if zero < 0:
            zero = 16
        name_raw = raw[:zero]
        require(name_raw and raw[zero:16] == bytes(16 - zero)
                and all(0x21 <= byte <= 0x7E for byte in name_raw),
                "index-row-name")
        name = name_raw.decode("ascii")
        require(name == name.lower(), "index-row-name-case")
        track, sector = raw[16], raw[17]
        require(1 <= track <= 80 and sector < 40, "index-row-locator")
        dependency_count = raw[22]
        require(dependency_count <= MAX_DEPS, "index-row-dependency-count")
        dependencies = list(raw[23:23 + dependency_count])
        require(all(item < count and item != ordinal for item in dependencies),
                "index-row-dependency")
        require(raw[23 + dependency_count:31]
                == bytes([0xFF] * (MAX_DEPS - dependency_count)),
                "index-row-dependency-padding")
        require(raw[31] == SOURCE_BANK2, "index-row-source")
        row = {
            "name": name,
            "track": track,
            "sector": sector,
            "combined_crc32": struct.unpack_from("<I", raw, 18)[0],
            "dependencies": dependencies,
            "execution_source": raw[31],
            "artifact_bytes": struct.unpack_from("<H", raw, 32)[0],
            "bank2": struct.unpack_from("<H", raw, 34)[0],
            "images": raw[36],
            "entries": struct.unpack_from("<H", raw, 37)[0],
            "resolutions": struct.unpack_from("<H", raw, 39)[0],
            "roots": struct.unpack_from("<H", raw, 41)[0],
            "scratch": struct.unpack_from("<H", raw, 43)[0],
        }
        require(row["combined_crc32"] != 0 and row["artifact_bytes"] > 0
                and row["bank2"] > 0 and row["images"] > 0,
                "index-row-zero-authority")
        if artifacts is not None:
            artifact = artifacts.get(name)
            require(artifact is not None and len(artifact) == row["artifact_bytes"],
                    "index-artifact-length")
            decoded = S.decode_extension(
                artifact, expected_build_id=artifact_build_id)
            require(decoded.combined_crc == row["combined_crc32"],
                    "index-artifact-identity")
        rows.append(row)
    require(len({row["name"] for row in rows}) == len(rows),
            "index-duplicate-name")
    require(len({row["combined_crc32"] for row in rows}) == len(rows),
            "index-duplicate-identity")
    visiting: set[int] = set()
    visited: set[int] = set()

    def visit(ordinal: int) -> None:
        require(ordinal not in visiting, "index-cycle")
        if ordinal in visited:
            return
        visiting.add(ordinal)
        for dependency in rows[ordinal]["dependencies"]:
            visit(dependency)
        visiting.remove(ordinal)
        visited.add(ordinal)

    for ordinal in range(len(rows)):
        visit(ordinal)
    return rows


def resolve(rows: list[dict[str, Any]], name: str, generation: int,
            loaded: list[tuple[int, int]], capacity: tuple[int, ...]
            ) -> list[int]:
    require(generation != 0, "resolve-generation")
    matches = [index for index, row in enumerate(rows) if row["name"] == name]
    require(len(matches) == 1, "resolve-name")
    current = [identity for gen, identity in loaded if gen == generation]
    index_identities = {row["combined_crc32"] for row in rows}
    require(len(current) == len(set(current))
            and all(identity in index_identities for identity in current),
            "resolve-active-universe")
    order: list[int] = []
    seen: set[int] = set()

    def visit(ordinal: int) -> None:
        if ordinal in seen:
            return
        for dependency in rows[ordinal]["dependencies"]:
            visit(dependency)
        seen.add(ordinal)
        order.append(ordinal)

    visit(matches[0])
    pending = [ordinal for ordinal in order
               if rows[ordinal]["combined_crc32"] not in current]
    totals = [0] * 6
    for ordinal in pending:
        row = rows[ordinal]
        for index, key in enumerate(
                ("bank2", "images", "entries", "resolutions", "roots", "scratch")):
            totals[index] += row[key]
    require(all(BASELINE[index] + totals[index] <= capacity[index]
                for index in range(6)), "resolve-capacity")
    return pending


def build_d81(path: Path, index: Path, artifacts: list[tuple[Path, str]]) -> None:
    c1541 = shutil.which("c1541")
    require(c1541 is not None, "c1541-unavailable")
    command = [c1541, "-format", "L65REQ,65", "d81", str(path),
               "-write", str(index), "l65index"]
    for artifact, name in artifacts:
        command += ["-write", str(artifact), name]
    result = subprocess.run(command, cwd=ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0, f"c1541 failed: {result.stdout}")


def d81_locators(path: Path) -> dict[str, tuple[int, int]]:
    data = path.read_bytes()
    D81.validate_bam(data)
    out: dict[str, tuple[int, int]] = {}
    for slot in D81.directory_slots(data):
        if not slot.record[2]:
            continue
        name = D81.entry_name(slot.record).decode("ascii").lower()
        chain = D81.file_chain(data, slot.record)
        require(chain, f"empty D81 chain: {name}")
        out[name] = chain[0]
    return out


def expect(label: str, action: Callable[[], Any],
           rejected: dict[str, str]) -> None:
    try:
        action()
    except (GateError, S.ProbeError) as error:
        rejected[label] = str(error)
        return
    raise GateError(f"mutation survived: {label}")


def reseal_index(candidate: bytearray, *,
                 rows: bool = True, identity: bool = True,
                 header: bool = True) -> None:
    if rows:
        count = candidate[8]
        records = bytes(candidate[HEADER_BYTES:HEADER_BYTES + count * ROW_BYTES])
        struct.pack_into("<H", candidate, 11, crc16(records))
        if identity:
            struct.pack_into("<I", candidate, 13,
                             zlib.crc32(records) & 0xFFFFFFFF)
    if header:
        struct.pack_into("<H", candidate, 17, crc16(candidate[:17]))


def mutation_gate(
        index: bytes, artifacts: dict[str, bytes], *,
        artifact_build_id: int = S.PROBE_BUILD_ID) -> dict[str, str]:
    rejected: dict[str, str] = {}

    def seal_without_record_crc_fields(candidate: bytearray) -> None:
        # Hardware First Red on Link 69: the target parser accidentally used
        # non-CRC reads for header bytes 11/12.  Pin that exact private seal so
        # a reader can never again accept a header which omits the record CRC
        # field from the canonical header-CRC domain.
        legacy_domain = bytes(candidate[:11]) + bytes(candidate[13:17])
        struct.pack_into("<H", candidate, 17, crc16(legacy_domain))

    def seal_magic_record_crc_identity_only(candidate: bytearray) -> None:
        # Link 70's first correction included bytes 11/12 but still omitted
        # the five fixed fields at 4..8 and the record length at 9/10.
        private_domain = bytes(candidate[:4]) + bytes(candidate[11:17])
        struct.pack_into("<H", candidate, 17, crc16(private_domain))

    def seal_magic_identity_only(candidate: bytearray) -> None:
        # Exact Link-69 target domain before the first hardware correction.
        private_domain = bytes(candidate[:4]) + bytes(candidate[13:17])
        struct.pack_into("<H", candidate, 17, crc16(private_domain))

    def mutation(label: str, change: Callable[[bytearray], None],
                 *, row_crc: int | None = None,
                 reseal: bool = False) -> None:
        candidate = bytearray(index)
        change(candidate)
        if row_crc is not None:
            at = HEADER_BYTES + row_crc * ROW_BYTES
            struct.pack_into("<H", candidate, at + 45,
                             crc16(candidate[at:at + 45]))
        if reseal:
            reseal_index(candidate)
        expect(
            label,
            lambda: decode_index(
                bytes(candidate), artifacts,
                artifact_build_id=artifact_build_id),
            rejected)

    mutation("magic", lambda b: b.__setitem__(0, ord("X")))
    mutation("version", lambda b: b.__setitem__(4, 2))
    mutation("header-width", lambda b: b.__setitem__(5, 31))
    mutation("row-width", lambda b: b.__setitem__(6, 47))
    mutation("dependency-width", lambda b: b.__setitem__(7, 7))
    mutation("zero-rows", lambda b: b.__setitem__(8, 0))
    mutation("record-bytes", lambda b: b.__setitem__(9, b[9] ^ 1))
    mutation("record-crc", lambda b: b.__setitem__(11, b[11] ^ 1))
    mutation("identity", lambda b: b.__setitem__(13, b[13] ^ 1))
    mutation("header-crc", lambda b: b.__setitem__(17, b[17] ^ 1))
    mutation("header-seal-omits-record-crc-fields",
             seal_without_record_crc_fields)
    mutation("header-seal-magic-record-crc-identity-only",
             seal_magic_record_crc_identity_only)
    mutation("header-seal-magic-identity-only",
             seal_magic_identity_only)
    mutation("header-reserved", lambda b: b.__setitem__(31, 1))
    mutation("empty-name", lambda b: b.__setitem__(HEADER_BYTES, 0),
             row_crc=0, reseal=True)
    mutation("name-padding", lambda b: b.__setitem__(HEADER_BYTES + 15, 65),
             row_crc=0, reseal=True)
    mutation("track-zero", lambda b: b.__setitem__(HEADER_BYTES + 16, 0),
             row_crc=0, reseal=True)
    mutation("sector-range", lambda b: b.__setitem__(HEADER_BYTES + 17, 40),
             row_crc=0, reseal=True)
    mutation("zero-identity",
             lambda b: b.__setitem__(
                 slice(HEADER_BYTES + 18, HEADER_BYTES + 22), bytes(4)),
             row_crc=0, reseal=True)
    mutation("dependency-count", lambda b: b.__setitem__(
        HEADER_BYTES + ROW_BYTES + 22, 9), row_crc=1, reseal=True)
    mutation("dependency-self", lambda b: b.__setitem__(
        HEADER_BYTES + ROW_BYTES + 23, 1), row_crc=1, reseal=True)
    mutation("dependency-padding", lambda b: b.__setitem__(
        HEADER_BYTES + 23, 0), row_crc=0, reseal=True)
    mutation("execution-source", lambda b: b.__setitem__(
        HEADER_BYTES + 31, 1), row_crc=0, reseal=True)
    mutation("artifact-zero", lambda b: b.__setitem__(
        slice(HEADER_BYTES + 32, HEADER_BYTES + 34), bytes(2)),
        row_crc=0, reseal=True)
    mutation("bank2-zero", lambda b: b.__setitem__(
        slice(HEADER_BYTES + 34, HEADER_BYTES + 36), bytes(2)),
        row_crc=0, reseal=True)
    mutation("images-zero", lambda b: b.__setitem__(
        HEADER_BYTES + 36, 0), row_crc=0, reseal=True)
    mutation("row-crc", lambda b: b.__setitem__(
        HEADER_BYTES + 45, b[HEADER_BYTES + 45] ^ 1))
    mutation("row-reserved", lambda b: b.__setitem__(
        HEADER_BYTES + 47, 1), row_crc=0, reseal=True)
    mutation("duplicate-name", lambda b: b.__setitem__(
        slice(HEADER_BYTES + ROW_BYTES, HEADER_BYTES + ROW_BYTES + 16),
        b[HEADER_BYTES:HEADER_BYTES + 16]), row_crc=1, reseal=True)
    mutation("duplicate-identity", lambda b: b.__setitem__(
        slice(HEADER_BYTES + ROW_BYTES + 18,
              HEADER_BYTES + ROW_BYTES + 22),
        b[HEADER_BYTES + 18:HEADER_BYTES + 22]),
        row_crc=1, reseal=True)
    mutation("artifact-length", lambda b: b.__setitem__(
        HEADER_BYTES + 32, b[HEADER_BYTES + 32] ^ 1),
        row_crc=0, reseal=True)
    mutation("artifact-identity", lambda b: b.__setitem__(
        HEADER_BYTES + 18, b[HEADER_BYTES + 18] ^ 1),
        row_crc=0, reseal=True)
    require(len(rejected) == 32, "L65I mutation count drift")
    return rejected


def source_gate() -> dict[str, Any]:
    lisp = LISP.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    vm = VM.read_text(encoding="utf-8")
    leaf = LEAF.read_text(encoding="utf-8")
    required_lisp = (
        "(defun require (library)",
        "(%c2d-byte (car address) (cdr address))",
        "(defun %require-static-prefix",
        "(defun %require-active-prefix",
        "(defun %require-transient-fronts-at",
        "(defun %require-capacities-p",
        "(defun %require-fast-loaded-p (library)",
        "(defun %require-active-identities-at",
        "(if (equal state (nth 3 cache))",
        "(if (%require-fast-loaded-p library)",
        "(cons 0 256)",
        "(%disk-load-lib (nth 2 row) (nth 3 row))",
        "(crc-lo (%l65i-next-crc))",
        "(crc-hi (%l65i-next-crc))",
        "(version (%l65i-next-crc))",
        "(header-bytes (%l65i-next-crc))",
        "(row-bytes (%l65i-next-crc))",
        "(max-dependencies (%l65i-next-crc))",
        "(rows (%l65i-next-crc))",
    )
    required_vm = (
        "case 67: /* %c2d-byte -- private read-only published-C2D seam */",
        "if (!vm_byte_args(a, n, 2u)) return NIL;",
        "return vm_c2d_byte(a);",
    )
    required_leaf = (
        ".section\t.lisp65_c2_kernal_window.reopen_gap1",
        ".globl\tvm_c2d_byte",
        ".type\tvm_c2d_byte,@function",
        "vm_byte_args already proved both operands are byte Fixnums",
        "cpx\t#$84",
        "cmp\t#$30",
        "ldz\t#0\n\tstz\t__rc5\n\tlda\t__rc6\n"
        "\tjsr\tc2_stream_c2d_read",
        ".size\tvm_c2d_byte,",
    )
    require(all(token in lisp for token in required_lisp),
            "target resolver source seam drift")
    primitive_start = vm.index("case 67:")
    primitive_end = vm.index("\n#else", primitive_start)
    primitive_body = vm[primitive_start:primitive_end]
    require(all(token in primitive_body for token in required_vm),
            "private C2D-byte primitive source drift")
    require(all(token in leaf for token in required_leaf),
            "private C2D-byte assembler leaf source drift")
    require("if (n == 1)" in vm
            and "c2_product_static_image_named(a[0]) ? vm_t : NIL" in vm,
            "ordinary one-argument static-image seam drift")
    require("(set-symbol-value '*loaded-libs*" not in lisp,
            "require introduced a loaded registry")
    require(
        all(token not in runtime for token in (
            "C2_REQUIRE_QUERY_", "c2_require_query_context",
            "c2_require_query_phase")),
        "retired string/query/overlay protocol remains")
    require(
        all(token not in primitive_body for token in (
            "c2_transient_fronts(",
            "c2_lite_bank2_fronts(",
            "c2_product_append_staged(",
            "vm_runtime_overlay_exec(",
        )),
        "private byte seam owns resolver policy")
    return {
        "status": "passed-private-C2D-byte-primitive-bank2-orchestration",
        "lisp_tokens": len(required_lisp),
        "primitive_tokens": len(required_vm),
        "assembler_leaf_tokens": len(required_leaf),
        "assembler_leaf": "vm_c2d_byte",
        "prim_id": 67,
        "arguments": ["offset-low-byte", "offset-high-byte"],
        "published_c2d_bytes": 33840,
        "read_bytes": 1,
        "retired_string_query_protocol": True,
        "overlay_roundtrips": 0,
        "new_session_records": 0,
        "claimed_resident_state_bytes": 0,
        "native_policy_decisions": 0,
        "bank2_decisions": [
            "active persistent identity universe",
            "canonical static Bank-2 edge from C2D slots 0..5",
            "persistent Bank-2 low edge",
            "transient C2D and Bank-2 high edges",
            "six-currency aggregate preflight",
            "dependency order and idempotence",
        ],
    }


def source_mutations() -> dict[str, str]:
    lisp = LISP.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    vm = VM.read_text(encoding="utf-8")
    leaf = LEAF.read_text(encoding="utf-8")
    rejected: dict[str, str] = {}

    def validate(lisp_source: str, runtime_source: str,
                 vm_source: str, leaf_source: str) -> None:
        require("(set-symbol-value '*loaded-libs*" not in lisp_source,
                "loaded-registry")
        for token in (
            "(%c2d-byte (car address) (cdr address))",
            "(defun %require-static-prefix",
            "(defun %require-active-prefix",
            "(defun %require-transient-fronts-at",
            "(defun %require-capacities-p",
            "(defun %require-fast-loaded-p (library)",
            "(defun %require-active-identities-at",
            "(if (equal state (nth 3 cache))",
            "(if (%require-fast-loaded-p library)",
            "(%disk-load-lib (nth 2 row) (nth 3 row))",
            "(crc-lo (%l65i-next-crc))",
            "(crc-hi (%l65i-next-crc))",
            "(version (%l65i-next-crc))",
            "(header-bytes (%l65i-next-crc))",
            "(row-bytes (%l65i-next-crc))",
            "(max-dependencies (%l65i-next-crc))",
            "(rows (%l65i-next-crc))",
        ):
            require(token in lisp_source, "lisp-seam")
        require("case 67:" in vm_source, "primitive-seam")
        start = vm_source.index("case 67:")
        end = vm_source.index("\n#else", start)
        body = vm_source[start:end]
        for token in (
            "case 67: /* %c2d-byte -- private read-only published-C2D seam */",
            "if (!vm_byte_args(a, n, 2u)) return NIL;",
            "return vm_c2d_byte(a);",
        ):
            require(token in body, "primitive-seam")
        for token in (
            ".section\t.lisp65_c2_kernal_window.reopen_gap1",
            ".globl\tvm_c2d_byte",
            ".type\tvm_c2d_byte,@function",
            "vm_byte_args already proved both operands are byte Fixnums",
            "cpx\t#$84",
            "cmp\t#$30",
            "ldz\t#0\n\tstz\t__rc5\n\tlda\t__rc6\n"
            "\tjsr\tc2_stream_c2d_read",
            ".size\tvm_c2d_byte,",
        ):
            require(token in leaf_source, "assembler-leaf-seam")
        require(
            "C2_REQUIRE_QUERY_" not in runtime_source
            and "c2_require_query_context" not in runtime_source
            and "c2_require_query_phase" not in runtime_source,
            "retired-query-protocol")
        require(
            "c2_transient_fronts(" not in body
            and "c2_lite_bank2_fronts(" not in body
            and "vm_runtime_overlay_exec(" not in body,
            "native-policy")

    variants = {
        "registry-introduced": (
            lisp + "\n(set-symbol-value '*loaded-libs* nil)\n", runtime, vm),
        "raw-c2d-read-removed": (lisp.replace(
            "(%c2d-byte (car address) (cdr address))", "nil", 1), runtime, vm),
        "static-prefix-removed": (lisp.replace(
            "(defun %require-static-prefix", "(defun %missing-static-prefix", 1),
            runtime, vm),
        "active-prefix-removed": (lisp.replace(
            "(defun %require-active-prefix", "(defun %missing-active-prefix", 1),
            runtime, vm),
        "transient-fronts-removed": (lisp.replace(
            "(defun %require-transient-fronts-at",
            "(defun %missing-transient-fronts-at", 1), runtime, vm),
        "capacity-orchestration-removed": (lisp.replace(
            "(defun %require-capacities-p",
            "(defun %missing-capacities-p", 1), runtime, vm),
        "idempotence-fastpath-removed": (lisp.replace(
            "(defun %require-fast-loaded-p (library)",
            "(defun %missing-fast-loaded-p (library)", 1), runtime, vm),
        "idempotence-state-check-removed": (lisp.replace(
            "(if (equal state (nth 3 cache))",
            "(if t", 1), runtime, vm),
        "idempotence-active-identities-removed": (lisp.replace(
            "(defun %require-active-identities-at",
            "(defun %missing-active-identities-at", 1), runtime, vm),
        "idempotence-parser-order-reversed": (lisp.replace(
            "(if (%require-fast-loaded-p library)",
            "(if nil", 1), runtime, vm),
        "append-seam-removed": (lisp.replace(
            "(%disk-load-lib (nth 2 row) (nth 3 row))", "t", 1), runtime, vm),
        "header-record-crc-low-omitted": (lisp.replace(
            "(crc-lo (%l65i-next-crc))",
            "(crc-lo (%l65i-next-byte))", 1), runtime, vm),
        "header-record-crc-high-omitted": (lisp.replace(
            "(crc-hi (%l65i-next-crc))",
            "(crc-hi (%l65i-next-byte))", 1), runtime, vm),
        "header-version-omitted": (lisp.replace(
            "(version (%l65i-next-crc))",
            "(version (%l65i-next-byte))", 1), runtime, vm),
        "header-width-omitted": (lisp.replace(
            "(header-bytes (%l65i-next-crc))",
            "(header-bytes (%l65i-next-byte))", 1), runtime, vm),
        "row-width-omitted": (lisp.replace(
            "(row-bytes (%l65i-next-crc))",
            "(row-bytes (%l65i-next-byte))", 1), runtime, vm),
        "dependency-width-omitted": (lisp.replace(
            "(max-dependencies (%l65i-next-crc))",
            "(max-dependencies (%l65i-next-byte))", 1), runtime, vm),
        "row-count-omitted": (lisp.replace(
            "(rows (%l65i-next-crc))",
            "(rows (%l65i-next-byte))", 1), runtime, vm),
        "prim-id": (lisp, runtime, vm.replace(
            "case 67: /* %c2d-byte", "case 68: /* %c2d-byte", 1)),
        "assembler-leaf-edge": (lisp, runtime, vm.replace(
            "return vm_c2d_byte(a);", "return NIL;", 1)),
        "byte-args-helper-removed": (lisp, runtime, vm.replace(
            "if (!vm_byte_args(a, n, 2u)) return NIL;",
            "if (0) return NIL;", 1)),
        "byte-args-arity": (lisp, runtime, vm.replace(
            "vm_byte_args(a, n, 2u)", "vm_byte_args(a, n, 1u)", 1)),
        "c2d-read-address": (lisp, runtime, vm.replace(
            "return vm_c2d_byte(a);",
            "return vm_c2d_byte(a + 1);", 1)),
        "c2d-read-width": (lisp, runtime, vm.replace(
            "return vm_c2d_byte(a);",
            "return vm_c2d_byte((obj *)0);", 1)),
        "typed-result": (lisp, runtime, vm.replace(
            "return vm_c2d_byte(a);", "return vm_t;", 1)),
        "old-query-protocol": (lisp, runtime
            + "\n#define C2_REQUIRE_QUERY_PREFIX 0xffu\n", vm),
        "native-policy-reintroduced": (lisp, runtime, vm.replace(
            "return vm_c2d_byte(a);",
            "c2_transient_fronts(0, 0, 0, 0, 0);\n"
            "        return vm_c2d_byte(a);", 1)),
        "leaf-proof-precondition": (lisp, runtime, vm, leaf.replace(
            "vm_byte_args already proved both operands are byte Fixnums",
            "operands are assumed without a caller proof", 1)),
        "leaf-published-high-bound": (lisp, runtime, vm, leaf.replace(
            "cpx\t#$84", "cpx\t#$85", 1)),
        "leaf-published-low-bound": (lisp, runtime, vm, leaf.replace(
            "cmp\t#$30", "cmp\t#$31", 1)),
        "leaf-reader-edge": (lisp, runtime, vm, leaf.replace(
            "jsr\tc2_stream_c2d_read", "jsr\tc2_stream_c2d_write", 1)),
        "leaf-length-high-Z-nonzero": (
            lisp, runtime, vm, leaf.replace(
                "ldz\t#0\n\tstz\t__rc5",
                "ldz\t#1\n\tstz\t__rc5", 1)),
        "leaf-reader-Z": (lisp, runtime, vm, leaf.replace(
            "lda\t__rc6\n\tjsr\tc2_stream_c2d_read",
            "lda\t__rc6\n\tldz\t#$d5\n\tjsr\tc2_stream_c2d_read", 1)),
        "leaf-size": (lisp, runtime, vm, leaf.replace(
            ".size\tvm_c2d_byte,", ".nosize\tvm_c2d_byte,", 1)),
    }
    for label, sources in variants.items():
        if len(sources) == 3:
            lisp_source, runtime_source, vm_source = sources
            leaf_source = leaf
        else:
            lisp_source, runtime_source, vm_source, leaf_source = sources
        expect(label, lambda ls=lisp_source, rs=runtime_source, vs=vm_source,
               lfs=leaf_source: validate(ls, rs, vs, lfs), rejected)
    require(len(rejected) == len(variants), "source mutation count")
    return rejected


def main() -> int:
    try:
        contract = load(CONTRACT)
        require(contract["status"]
                == "class-C-product-shaped-WPLTO-probe-authorized",
                "resolver probe is not authorized")
        host = load(HOST_RECEIPT)
        require(host["status"] == "passed-host-first-require-index-L65P-v1"
                and host["negative"]["mutation_count"] >= 38
                and host["rollback"]["cutpoint_count"] == 12,
                "host-first prerequisite drift")
        host_replay = subprocess.run(
            [sys.executable, str(HOST_PROBE.relative_to(ROOT))],
            cwd=ROOT, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, check=False)
        require(
            host_replay.returncode == 0
            and "cutpoints=12" in host_replay.stdout
            and "mutations=38" in host_replay.stdout,
            f"fresh host orchestration replay red:\n{host_replay.stdout}")
        host = load(HOST_RECEIPT)
        target_compile = subprocess.run(
            [
                sys.executable,
                "tools/host-lisp/bytecode_p0_stdlib.py",
                "--check",
                "--emit-artifacts",
                str((BUILD / "stdlib-p0").relative_to(ROOT)),
                str(SUITE.relative_to(ROOT)),
            ],
            cwd=ROOT, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, check=False)
        require(
            target_compile.returncode == 0
            and "bytecode-p0-stdlib-check: PASS" in target_compile.stdout,
            f"Bank-2 resolver compile red:\n{target_compile.stdout}")
        BUILD.mkdir(parents=True, exist_ok=True)
        placeholder: list[dict[str, Any]] = []
        artifact_data: dict[str, bytes] = {}
        artifact_paths: list[tuple[Path, str]] = []
        for number, (name, manifest, dependencies) in enumerate(LIBRARIES):
            row, artifact = measured_row(
                name, manifest, dependencies, 1, number + 1)
            placeholder.append(row)
            artifact_data[name] = artifact
            path = BUILD / f"{name}.l65s"
            path.write_bytes(artifact)
            artifact_paths.append((path, name))
        seed_index = BUILD / "l65index.seed"
        seed_index.write_bytes(encode_index(placeholder))
        seed_d81 = BUILD / "require-resolver-seed.d81"
        build_d81(seed_d81, seed_index, artifact_paths)
        locators = d81_locators(seed_d81)
        rows: list[dict[str, Any]] = []
        for name, manifest, dependencies in LIBRARIES:
            require(name in locators, f"D81 locator absent: {name}")
            row, artifact = measured_row(
                name, manifest, dependencies, *locators[name])
            require(artifact == artifact_data[name], f"artifact drift: {name}")
            rows.append(row)
        index = encode_index(rows)
        index_path = BUILD / "l65index"
        index_path.write_bytes(index)
        decoded = decode_index(index, artifact_data)
        final_d81 = BUILD / "require-resolver-fixture.d81"
        build_d81(final_d81, index_path, artifact_paths)
        final_locators = d81_locators(final_d81)
        require(final_locators == locators, "D81 locator drift after final index")
        visible = D81.visible_files(final_d81.read_bytes())
        require(visible[b"L65INDEX"] == index
                and visible[b"ROOM"] == artifact_data["room"]
                and visible[b"BUFFER"] == artifact_data["buffer"],
                "D81 visible file truth drift")
        require(resolve(decoded, "buffer", 7, [], CAPACITY) == [0, 1],
                "dependency order")
        room_id = decoded[0]["combined_crc32"]
        buffer_id = decoded[1]["combined_crc32"]
        require(resolve(decoded, "buffer", 7, [(7, room_id)], CAPACITY) == [1],
                "partial idempotence")
        require(resolve(
            decoded, "buffer", 7, [(7, room_id), (7, buffer_id)], CAPACITY) == [],
            "complete idempotence")
        expect("foreign-loaded-identity", lambda: resolve(
            decoded, "buffer", 7, [(7, 0xDEADBEEF)], CAPACITY), {})
        capacity_mutations: dict[str, str] = {}
        totals = [sum(row[key] for row in decoded) for key in
                  ("bank2", "images", "entries", "resolutions", "roots", "scratch")]
        for index_no, label in enumerate(
                ("bank2", "images", "entries", "resolutions", "roots", "scratch")):
            exact = list(CAPACITY)
            exact[index_no] = BASELINE[index_no] + totals[index_no]
            require(resolve(decoded, "buffer", 7, [], tuple(exact)) == [0, 1],
                    f"{label} exact meet")
            overflow = list(exact)
            overflow[index_no] -= 1
            expect(f"{label}-one-byte-overflow", lambda c=tuple(overflow):
                   resolve(decoded, "buffer", 7, [], c), capacity_mutations)
        source = source_gate()
        source_rejected = source_mutations()
        binary_rejected = mutation_gate(index, artifact_data)
        value = {
            "format": "lisp65-c2-require-resolver-source-index-gate-v2",
            "recorded_on": "2026-07-27",
            "status":
                "passed-bank2-orchestrated-require-and-private-c2d-byte-gates",
            "promotable": False,
            "product_links": 0,
            "hardware_runs": 0,
            "host_first_prerequisite": {
                "cutpoints": host["rollback"]["cutpoint_count"],
                "mutations": host["negative"]["mutation_count"],
                "fresh_replay": host_replay.stdout.strip().splitlines()[-1],
                "binding":
                    "same dependency/rollback/preflight semantics are "
                    "implemented by the gated Bank-2 Lisp functions",
            },
            "target_bank2_compile": {
                "status": "passed",
                "summary": target_compile.stdout.strip().splitlines()[-3:],
                "manifest": bind(BUILD / "stdlib-p0.manifest.json"),
            },
            "source_gate": source,
            "source_mutations": source_rejected,
            "binary_index": {
                "format": "L65I-v1",
                "rows": rows,
                "dependency_order": ["room", "buffer"],
                "generation_idempotence": "passed-empty-partial-complete",
                "capacity_exact_meets": 6,
                "capacity_one_byte_overflows": capacity_mutations,
                "mutations_rejected": binary_rejected,
                "index_crc16": f"0x{struct.unpack_from('<H', index, 11)[0]:04x}",
                "index_identity_crc32":
                    f"0x{struct.unpack_from('<I', index, 13)[0]:08x}",
            },
            "artifacts": {
                "index": bind(index_path),
                "D81": bind(final_d81),
                "libraries": [bind(path) for path, _name in artifact_paths],
            },
            "authority": {
                "contract": bind(CONTRACT),
                "note": bind(NOTE),
                "ramp": bind(RAMP),
                "host_receipt": bind(HOST_RECEIPT),
                "lisp": bind(LISP),
                "runtime": bind(RUNTIME),
                "vm": bind(VM),
                "assembler_leaf": bind(LEAF),
                "suite": bind(SUITE),
                "gate": bind(Path(__file__).resolve()),
            },
            "claim_limit":
                "Source, real-artifact L65I and host semantics only; WPLTO, "
                "product link, hardware and defstruct are not claimed.",
        }
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        print(
            "c2-require-resolver-gate: PASS "
            f"rows={len(rows)} source-mutations={len(source_rejected)} "
            f"index-mutations={len(binary_rejected)} capacity=6/6")
    except (OSError, ValueError, KeyError, GateError, F.FullError,
            S.ProbeError) as error:
        print(f"c2-require-resolver-gate: FIRST RED: {error}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
