#!/usr/bin/env python3
"""Exercise the C2.1 shelf, identity, reset and negative contract matrix."""

from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any, Callable
import zlib


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "host-lisp"))

import c2_direct_proof as D  # noqa: E402


RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.1-direct-negative-reset-receipt.json"
)
DIRECT_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.1-direct-proof-receipt.json"
)
SHELF_HEADER_BYTES = 32
SHELF_RECORD_BYTES = 32
SPLIT_FLAG = 1
MAX_PHYSICAL = 0x0FFFFFFF


class OracleError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise OracleError(message)


def p24(value: int) -> bytes:
    require(0 <= value <= 0xFFFFFF, "u24 overflow")
    return bytes((value & 0xFF, value >> 8 & 0xFF, value >> 16 & 0xFF))


def u24(data: bytes, offset: int) -> int:
    require(offset + 3 <= len(data), "truncated u24")
    return data[offset] | data[offset + 1] << 8 | data[offset + 2] << 16


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def binding(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": len(data),
        "sha256": sha(data),
    }


@dataclass(frozen=True)
class ShelfRecord:
    code: bytes
    metadata: bytes
    build_id: int
    shelf_sha: str
    code_offset: int
    metadata_offset: int


def target_inputs() -> tuple[dict[str, Any], bytes, bytes]:
    target = json.loads(D.TARGET.read_text(encoding="utf-8"))
    D.validate_target(target)
    code, metadata = D.build_image(target)
    return target, code, metadata


def build_shelf(target: dict[str, Any], code: bytes, metadata: bytes) -> bytes:
    spec = target["shelf"]
    require(spec == {
        "magic": "L65S", "version": 4, "header_bytes": 32,
        "record_bytes": 32, "split_flag": 1, "record_name": "c2proof",
        "proof_build_id": "0xc2210001", "region_id": 1,
        "region_base": "0x08100000", "maximum_relative_offset": 7340031,
    }, "shelf target drift")
    payload_offset = SHELF_HEADER_BYTES + SHELF_RECORD_BYTES
    code_offset = payload_offset
    metadata_offset = code_offset + len(code)
    total = metadata_offset + len(metadata)

    record = bytearray(SHELF_RECORD_BYTES)
    record[:8] = b"c2proof\0"
    record[8:11] = p24(code_offset)
    struct.pack_into("<H", record, 11, len(code))
    record[13:16] = p24(metadata_offset)
    struct.pack_into("<H", record, 16, len(metadata))
    struct.pack_into("<I", record, 18, zlib.crc32(code) & 0xFFFFFFFF)
    struct.pack_into("<I", record, 22, zlib.crc32(metadata) & 0xFFFFFFFF)
    struct.pack_into("<I", record, 26, zlib.crc32(code + metadata) & 0xFFFFFFFF)
    record[30] = SPLIT_FLAG

    header = bytearray(SHELF_HEADER_BYTES)
    header[:8] = b"L65S" + bytes((4, SHELF_HEADER_BYTES, SHELF_RECORD_BYTES, 1))
    struct.pack_into("<H", header, 8, SHELF_HEADER_BYTES)
    header[10:13] = p24(payload_offset)
    header[13:16] = p24(total)
    struct.pack_into("<H", header, 16, len(record))
    struct.pack_into("<I", header, 18, zlib.crc32(record) & 0xFFFFFFFF)
    struct.pack_into("<I", header, 22, int(spec["proof_build_id"], 0))
    struct.pack_into("<H", header, 26, SPLIT_FLAG)
    shelf = bytes(header) + bytes(record) + code + metadata
    require(len(shelf) == total, "shelf encoder length did not close")
    return shelf


def legacy_v11_accepts(shelf: bytes) -> None:
    require(len(shelf) >= 5 and shelf[:4] == b"L65S" and shelf[4] == 3,
            "v1.1 decoder rejects non-v3 shelf")


def decode_shelf(
    shelf: bytes,
    *,
    expected_build_id: int,
    generation: int = 1,
    region_base: int = 0x08100000,
    maximum_offset: int = 0x6FFFFF,
) -> tuple[ShelfRecord, D.DecodedImage]:
    require(len(shelf) >= SHELF_HEADER_BYTES + SHELF_RECORD_BYTES, "short shelf")
    require(shelf[:4] == b"L65S" and shelf[4] == 4, "C2 decoder accepts only L65S-v4")
    require(tuple(shelf[5:7]) == (SHELF_HEADER_BYTES, SHELF_RECORD_BYTES),
            "shelf header or record width mismatch")
    count = shelf[7]
    require(count == 1, "proof shelf record count drift")
    require(struct.unpack_from("<H", shelf, 8)[0] == SHELF_HEADER_BYTES,
            "shelf header duplicate width mismatch")
    payload_offset = u24(shelf, 10)
    total = u24(shelf, 13)
    catalog_bytes = struct.unpack_from("<H", shelf, 16)[0]
    catalog_crc = struct.unpack_from("<I", shelf, 18)[0]
    build_id = struct.unpack_from("<I", shelf, 22)[0]
    flags = struct.unpack_from("<H", shelf, 26)[0]
    require(shelf[28:32] == b"\0\0\0\0", "nonzero shelf header reserved")
    require(flags == SPLIT_FLAG, "unknown or non-direct v4 shelf flag")
    require(build_id == expected_build_id, "product/shelf build-identity mismatch")
    require(catalog_bytes == count * SHELF_RECORD_BYTES,
            "shelf catalog length mismatch")
    require(payload_offset == SHELF_HEADER_BYTES + catalog_bytes,
            "shelf payload offset mismatch")
    require(total == len(shelf), "shelf total length mismatch")
    catalog = shelf[SHELF_HEADER_BYTES:payload_offset]
    require(zlib.crc32(catalog) & 0xFFFFFFFF == catalog_crc, "catalog CRC mismatch")

    record = catalog[:SHELF_RECORD_BYTES]
    require(record[:8] == b"c2proof\0", "proof record name mismatch")
    code_offset = u24(record, 8)
    code_length = struct.unpack_from("<H", record, 11)[0]
    metadata_offset = u24(record, 13)
    metadata_length = struct.unpack_from("<H", record, 16)[0]
    require(record[30] == SPLIT_FLAG and record[31] == 0,
            "unknown record flag or nonzero reserved")
    for label, offset, length in (
        ("code", code_offset, code_length),
        ("metadata", metadata_offset, metadata_length),
    ):
        require(offset <= maximum_offset and offset + length <= maximum_offset + 1,
                "%s region offset outside u24 envelope" % label)
        require(region_base + offset + length - (1 if length else 0) <= MAX_PHYSICAL,
                "28-bit base-plus-offset overflow")
        require(payload_offset <= offset <= len(shelf) and offset + length <= len(shelf),
                "%s region outside shelf" % label)
    require(code_length > 0 and metadata_length > 0, "empty direct region")
    require(metadata_offset == code_offset + code_length,
            "split regions are not contiguous")
    require(metadata_offset + metadata_length == total,
            "split regions do not close the shelf")
    code = shelf[code_offset:code_offset + code_length]
    metadata = shelf[metadata_offset:metadata_offset + metadata_length]
    require(zlib.crc32(code) & 0xFFFFFFFF == struct.unpack_from("<I", record, 18)[0],
            "code region CRC mismatch")
    require(zlib.crc32(metadata) & 0xFFFFFFFF == struct.unpack_from("<I", record, 22)[0],
            "metadata region CRC mismatch")
    require(zlib.crc32(code + metadata) & 0xFFFFFFFF == struct.unpack_from("<I", record, 26)[0],
            "container CRC mismatch")
    image = D.decode_image(code, metadata, generation)
    return ShelfRecord(code, metadata, build_id, sha(shelf), code_offset, metadata_offset), image


class Session:
    def __init__(self, expected_build_id: int):
        self.expected_build_id = expected_build_id
        self.generation = 0
        self.shelf_sha: str | None = None
        self.image: D.DecodedImage | None = None

    def cold_stage(self, shelf: bytes) -> D.DecodedImage:
        require(self.generation != 0xFFFF, "session generation wrap requires cold boot")
        generation = self.generation + 1
        record, image = decode_shelf(
            shelf, expected_build_id=self.expected_build_id, generation=generation
        )
        self.generation = generation
        self.shelf_sha = record.shelf_sha
        self.image = image
        return image

    def hot_restage(self, _shelf: bytes) -> None:
        require(self.image is None, "hot restage forbidden in live session")


def encode_reference(source_container: int, target_container: int, ordinal: int) -> bytes:
    require(source_container == target_container,
            "cross-container ordinal reference forbidden")
    return D.literal_entry_ref(ordinal)


class Publisher:
    def __init__(self):
        self.directory: list[str] = ["old-dir"]
        self.resolutions: list[str] = ["old-lit"]
        self.cells: dict[str, str] = {"a": "old-a", "b": "old-b"}

    def publish(self, *, fail_before_exports: bool = False, fail_after: int | None = None) -> None:
        old_directory = list(self.directory)
        old_resolutions = list(self.resolutions)
        journal: list[tuple[str, bool, str | None]] = []
        try:
            self.directory.append("new-dir")
            self.resolutions.append("new-lit")
            if fail_before_exports:
                raise OracleError("injected failure before export publication")
            for index, name in enumerate(("a", "b"), start=1):
                journal.append((name, name in self.cells, self.cells.get(name)))
                self.cells[name] = "new-" + name
                if fail_after == index:
                    raise OracleError("injected failure during export publication")
        except OracleError:
            for name, bound, old in reversed(journal):
                if bound:
                    require(old is not None, "journal lost bound value")
                    self.cells[name] = old
                else:
                    self.cells.pop(name, None)
            self.directory = old_directory
            self.resolutions = old_resolutions
            raise


def metadata_from_shelf(shelf: bytes) -> tuple[bytearray, int, int]:
    record = SHELF_HEADER_BYTES
    metadata_offset = u24(shelf, record + 13)
    metadata_length = struct.unpack_from("<H", shelf, record + 16)[0]
    return bytearray(shelf[metadata_offset:metadata_offset + metadata_length]), metadata_offset, metadata_length


def replace_metadata(shelf: bytes, metadata: bytes) -> bytes:
    out = bytearray(shelf)
    record_at = SHELF_HEADER_BYTES
    old_offset = u24(out, record_at + 13)
    old_length = struct.unpack_from("<H", out, record_at + 16)[0]
    require(old_offset + old_length == len(out), "proof metadata is not the terminal region")
    del out[old_offset:]
    out.extend(metadata)
    struct.pack_into("<H", out, record_at + 16, len(metadata))
    code_offset = u24(out, record_at + 8)
    code_length = struct.unpack_from("<H", out, record_at + 11)[0]
    code = bytes(out[code_offset:code_offset + code_length])
    struct.pack_into("<I", out, record_at + 22, zlib.crc32(metadata) & 0xFFFFFFFF)
    struct.pack_into("<I", out, record_at + 26, zlib.crc32(code + metadata) & 0xFFFFFFFF)
    out[13:16] = p24(len(out))
    catalog = bytes(out[SHELF_HEADER_BYTES:SHELF_HEADER_BYTES + SHELF_RECORD_BYTES])
    struct.pack_into("<I", out, 18, zlib.crc32(catalog) & 0xFFFFFFFF)
    return bytes(out)


def mutate_shelf(shelf: bytes, action: Callable[[bytearray], None], *, repair_catalog: bool = False) -> bytes:
    out = bytearray(shelf)
    action(out)
    if repair_catalog:
        catalog = bytes(out[SHELF_HEADER_BYTES:SHELF_HEADER_BYTES + SHELF_RECORD_BYTES])
        struct.pack_into("<I", out, 18, zlib.crc32(catalog) & 0xFFFFFFFF)
    return bytes(out)


def expect_failure(label: str, action: Callable[[], Any], contains: str) -> dict[str, str]:
    try:
        action()
    except (D.ProofError, OracleError) as exc:
        require(contains in str(exc), "%s wrong failure: %s" % (label, exc))
        return {"id": label, "result": "rejected", "diagnostic": str(exc)}
    raise OracleError("negative case passed: %s" % label)


def late_bound_metadata(metadata: bytes) -> bytes:
    value = bytearray(metadata)
    entry0 = D.HEADER_BYTES
    value[entry0 + 8:entry0 + 10] = b"\0\0"
    value[entry0 + 11] = 2
    string = b"\x04\x00hook"
    strings_bytes = D.read_u16(value, 20)
    require(strings_bytes == 0 and len(value) % 2 == 0, "late-bound fixture baseline drift")
    struct.pack_into("<H", value, 20, len(string))
    value.extend(string)
    return bytes(value)


def string_metadata(metadata: bytes, *, descriptor_length: int = 4, offset: int = 0,
                    name: bytes = b"name", kind: int = 5) -> bytes:
    value = bytearray(metadata)
    literal_offset = D.read_u16(value, 16)
    value[literal_offset] = kind
    struct.pack_into("<H", value, literal_offset + 2, descriptor_length)
    value[literal_offset + 4:literal_offset + 7] = p24(offset)
    record = struct.pack("<H", len(name)) + name
    struct.pack_into("<H", value, 20, len(record))
    value.extend(record)
    if len(value) & 1:
        value += b"\0"
    return bytes(value)


def render() -> dict[str, Any]:
    target, code, metadata = target_inputs()
    build_id = int(target["shelf"]["proof_build_id"], 0)
    shelf = build_shelf(target, code, metadata)
    record, image = decode_shelf(shelf, expected_build_id=build_id)
    require(image.identity == sha(code + metadata), "shelf/image identity drift")

    negatives: list[dict[str, str]] = []
    negatives.append(expect_failure(
        "c2-rejects-v3",
        lambda: decode_shelf(bytes(shelf[:4] + b"\x03" + shelf[5:]), expected_build_id=build_id),
        "only L65S-v4",
    ))
    negatives.append(expect_failure(
        "v11-rejects-v4", lambda: legacy_v11_accepts(shelf), "rejects non-v3"
    ))
    negatives.append(expect_failure(
        "unknown-v4-flag",
        lambda: decode_shelf(
            mutate_shelf(shelf, lambda out: struct.pack_into("<H", out, 26, 2)),
            expected_build_id=build_id,
        ),
        "unknown or non-direct",
    ))
    negatives.append(expect_failure(
        "u24-region-envelope",
        lambda: decode_shelf(
            mutate_shelf(shelf, lambda out: out.__setitem__(slice(40, 43), p24(0x700000)),
                         repair_catalog=True),
            expected_build_id=build_id,
        ),
        "outside u24 envelope",
    ))
    negatives.append(expect_failure(
        "physical-address-overflow",
        lambda: decode_shelf(
            shelf, expected_build_id=build_id, region_base=0x0FFFFFC0
        ),
        "28-bit",
    ))

    anonymous_flags = bytearray(metadata)
    anonymous_flags[D.HEADER_BYTES + 11] = 1
    negatives.append(expect_failure(
        "ffff-used-as-named-offset",
        lambda: D.decode_image(code, bytes(anonymous_flags)), "anonymous entry"
    ))
    zero_length = bytearray(metadata)
    zero_length[D.HEADER_BYTES + 3:D.HEADER_BYTES + 5] = b"\0\0"
    negatives.append(expect_failure(
        "zero-length-entry", lambda: D.decode_image(code, bytes(zero_length)), "entry code range"
    ))
    bad_fixnum = bytearray(metadata)
    literals_at = D.read_u16(bad_fixnum, 16)
    bad_fixnum[literals_at] = 2
    struct.pack_into("<H", bad_fixnum, literals_at + 2, 0x4000)
    negatives.append(expect_failure(
        "fixnum-outside-dialect-range",
        lambda: D.decode_image(code, bytes(bad_fixnum)), "fixnum descriptor"
    ))
    negatives.append(expect_failure(
        "cross-container-ordinal",
        lambda: encode_reference(0, 1, 0), "cross-container ordinal"
    ))
    negatives.append(expect_failure(
        "late-bound-ordinal-edge",
        lambda: D.decode_image(code, late_bound_metadata(metadata)), "late-bound entry"
    ))
    negatives.append(expect_failure(
        "region-crc-mismatch",
        lambda: decode_shelf(
            mutate_shelf(shelf, lambda out: out.__setitem__(64, out[64] ^ 1)),
            expected_build_id=build_id,
        ),
        "code region CRC",
    ))
    negatives.append(expect_failure(
        "build-identity-mismatch",
        lambda: decode_shelf(shelf, expected_build_id=build_id ^ 1), "build-identity"
    ))

    session = Session(build_id)
    first = session.cold_stage(shelf)
    stale = D.BCode(first.generation, 0)
    second = session.cold_stage(shelf)
    negatives.append(expect_failure(
        "stale-generation-after-restage",
        lambda: D.DirectVM(second, 8)._invoke(stale, [41], 0), "stale session generation"
    ))
    negatives.append(expect_failure(
        "hot-restage-live-session", lambda: session.hot_restage(shelf), "hot restage forbidden"
    ))

    publisher = Publisher()
    baseline = (list(publisher.directory), list(publisher.resolutions), dict(publisher.cells))
    negatives.append(expect_failure(
        "failure-before-export-publication",
        lambda: publisher.publish(fail_before_exports=True), "before export"
    ))
    require((publisher.directory, publisher.resolutions, publisher.cells) == baseline,
            "pre-export rollback leaked state")
    negatives.append(expect_failure(
        "failure-during-export-publication",
        lambda: publisher.publish(fail_after=1), "during export"
    ))
    require((publisher.directory, publisher.resolutions, publisher.cells) == baseline,
            "mid-export rollback leaked state")
    vm = D.DirectVM(second, 8)
    negatives.append(expect_failure(
        "refill-crosses-entry-bound",
        lambda: vm._byte(second.entries[0], second.entries[0].payload_length),
        "refill crosses entry bounds",
    ))

    # Metadata-envelope addendum cases not already covered above.
    bad_magic = bytearray(metadata)
    bad_magic[0] ^= 1
    negatives.append(expect_failure(
        "metadata-bad-magic", lambda: D.decode_image(code, bytes(bad_magic)), "bad C2I"
    ))
    bad_width = bytearray(metadata)
    bad_width[6] = 15
    negatives.append(expect_failure(
        "metadata-record-width", lambda: D.decode_image(code, bytes(bad_width)), "record-size"
    ))
    bad_header_flags = bytearray(metadata)
    bad_header_flags[8] = 1
    negatives.append(expect_failure(
        "metadata-header-flags", lambda: D.decode_image(code, bytes(bad_header_flags)), "header flags"
    ))
    bad_sections = bytearray(metadata)
    struct.pack_into("<H", bad_sections, 16, D.read_u16(metadata, 16) + 1)
    negatives.append(expect_failure(
        "metadata-section-gap", lambda: D.decode_image(code, bytes(bad_sections)), "section arithmetic"
    ))
    negatives.append(expect_failure(
        "metadata-length-vs-shelf-record",
        lambda: decode_shelf(
            mutate_shelf(
                shelf,
                lambda out: struct.pack_into("<H", out, SHELF_HEADER_BYTES + 16, len(metadata) - 2),
                repair_catalog=True,
            ),
            expected_build_id=build_id,
        ),
        "split regions do not close",
    ))
    bad_literal_range = bytearray(metadata)
    struct.pack_into("<H", bad_literal_range, D.HEADER_BYTES + 5, 99)
    negatives.append(expect_failure(
        "entry-literal-range", lambda: D.decode_image(code, bytes(bad_literal_range)), "literal range"
    ))
    bad_entry_flags = bytearray(metadata)
    bad_entry_flags[D.HEADER_BYTES + 11] = 4
    negatives.append(expect_failure(
        "unknown-entry-flag", lambda: D.decode_image(code, bytes(bad_entry_flags)), "entry flags"
    ))
    negatives.append(expect_failure(
        "string-offset-not-boundary",
        lambda: D.decode_image(code, string_metadata(metadata, offset=1)), "record boundary"
    ))
    negatives.append(expect_failure(
        "invalid-symbol-name",
        lambda: D.decode_image(
            code, string_metadata(metadata, descriptor_length=8, name=b"bad name")
        ),
        "canonical ASCII",
    ))
    bad_literal_flags = bytearray(metadata)
    bad_literal_flags[literals_at + 1] = 1
    negatives.append(expect_failure(
        "literal-flags", lambda: D.decode_image(code, bytes(bad_literal_flags)), "literal flags"
    ))
    negatives.append(expect_failure(
        "string-length-mismatch",
        lambda: D.decode_image(code, string_metadata(metadata, descriptor_length=3)),
        "string descriptor length",
    ))

    wrap = Session(build_id)
    wrap.generation = 0xFFFF
    negatives.append(expect_failure(
        "session-generation-wrap", lambda: wrap.cold_stage(shelf), "generation wrap"
    ))

    require(len(negatives) == 29 and len({case["id"] for case in negatives}) == 29,
            "negative matrix count or identity drift")
    current = D.DirectVM(second, target["window_bytes"])
    positive_routes = {
        entry["route"]: current.run(entry["ordinal"])
        for entry in target["entries"] if entry["route"] != "helper"
    }
    require(positive_routes == target["expected_routes"], "post-restage route closure drift")
    require(sha(first.code) == sha(second.code) == sha(code), "restage changed immutable code")
    return {
        "format": "lisp65-c2.1-direct-negative-reset-receipt-v1",
        "version": 1,
        "recorded_on": "2026-07-19",
        "status": "host-negative-and-reset-model-passed-target-not-run",
        "claim_limit": (
            "This receipt proves the host shelf/identity/reset model and 29 fail-closed "
            "cases. It does not prove the target decoder, DMA timing, target reset, capacity "
            "or any product behavior."
        ),
        "bindings": {
            "target": binding(D.TARGET),
            "core_contract": binding(D.CORE),
            "metadata_envelope": binding(D.ENVELOPE),
            "direct_proof_receipt": binding(DIRECT_RECEIPT),
            "direct_proof_verifier": binding(ROOT / "tools/host-lisp/c2_direct_proof.py"),
            "oracle": binding(Path(__file__)),
        },
        "shelf": {
            "bytes": len(shelf),
            "sha256": sha(shelf),
            "catalog_crc32": "%08x" % (zlib.crc32(shelf[32:64]) & 0xFFFFFFFF),
            "code_offset": record.code_offset,
            "metadata_offset": record.metadata_offset,
            "code_crc32": "%08x" % (zlib.crc32(code) & 0xFFFFFFFF),
            "metadata_crc32": "%08x" % (zlib.crc32(metadata) & 0xFFFFFFFF),
            "build_id": "0x%08x" % build_id,
        },
        "negative_matrix": {
            "cases": negatives,
            "count": len(negatives),
            "all_rejected": True,
            "core_contract_classes": 17,
            "metadata_addendum_classes": 12,
            "overlap_is_explicit": True,
        },
        "reset_restage": {
            "generations": [first.generation, second.generation],
            "stale_handle_rejected": True,
            "hot_restage_rejected": True,
            "generation_wrap_rejected": True,
            "immutable_code_sha256": sha(code),
            "post_restage_routes": positive_routes,
        },
        "publication_rollback": {
            "before_exports": "exact-baseline-restored",
            "during_exports": "reverse-journal-exact-baseline-restored",
        },
        "next_authorized_action": (
            "Build the independent target-side C decoder/refill proof and measure the "
            "isolated real link; no product cut or capacity debit is authorized."
        ),
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def selftest() -> None:
    first = canonical(render())
    second = canonical(render())
    require(first == second, "oracle rendering is nondeterministic")
    value = json.loads(first)
    require(value["negative_matrix"]["count"] == 29, "negative matrix selftest drift")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            selftest()
            print("c2-direct-oracles: SELFTEST PASS cases=29 deterministic=2/2")
            return 0
        value = render()
        data = canonical(value)
        if args.action == "write":
            RECEIPT.parent.mkdir(parents=True, exist_ok=True)
            RECEIPT.write_bytes(data)
            action = "WROTE"
        else:
            require(RECEIPT.is_file() and RECEIPT.read_bytes() == data,
                    "pinned negative/reset receipt drift")
            action = "PASS"
        print(
            "c2-direct-oracles: %s shelf=%d negatives=%d generations=1,2"
            % (action, value["shelf"]["bytes"], value["negative_matrix"]["count"])
        )
        return 0
    except (OSError, ValueError, json.JSONDecodeError, D.ProofError, OracleError) as exc:
        print("c2-direct-oracles: FAIL: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
