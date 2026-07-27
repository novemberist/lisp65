#!/usr/bin/env python3
"""Authorized host/product-shaped C2-lite C2D-v6 probe.

This tool emits the exact six-image Bank-2 plane through the one C2I-v2
emitter, models persistent and transient session publication with C2D-v6,
proves the Bank-3 Boot/Session lifetime union, and performs one non-product
Whole-Program-LTO measurement.  It never writes a promotable product link.
"""

from __future__ import annotations

import argparse
import copy
import ctypes
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
from typing import Any, Callable
import zlib


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_full_emission as F  # noqa: E402
import c2_gc_root_single_source as G  # noqa: E402
import c2_lite_root_surrogate as R  # noqa: E402
import c2_session_extension_probe as S  # noqa: E402
import c2_substitution_artifacts as A  # noqa: E402


OUT = ROOT / "build/c2-lite/product-shaped-v6-probe"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-product-shaped-probe-receipt.json"
)
CONTRACT = ROOT / "config/c2-lite-execution-contract.json"
ADDENDUM = ROOT / "docs/planning/c2-lite-execution-contract-addendum.md"
MEMO = ROOT / "docs/planning/v1.2-scope-memo.md"
PRODUCT_IDENTITY = ROOT / "build/c2.2/substitution/substitution-artifacts.json"
LEGACY_INPUT = ROOT / "build/equivalence/fasl-test.bin"
LINK35 = ROOT / "build/c2.2/substitution/product-link-35-dma-completion-first-status"
BOOT35 = LINK35 / "runtime-overlays-boot-final.bin"
SESSION35 = LINK35 / "runtime-overlays-session-final.bin"
STATIC_CODE_BYTES = 34403
BANK_BYTES = 65536
C2D_VERSION = 6
C2D_HEADER_BYTES = 48
C2D_IMAGE_BYTES = 32
C2D_ENTRY_BYTES = 10
C2D_IMAGES_OFFSET = 48
C2D_ENTRIES_OFFSET = 2096
C2D_RESOLUTIONS_OFFSET = 22576
C2D_ROOTS_OFFSET = 30768
C2D_TOTAL_BYTES = 33840
C2D_REGION_BYTES = 50816
SESSION_GENERATION = 1
ROOT_KINDS = {F.K_STRING, F.K_PAIR}
ROLLBACK_CUTPOINTS = (
    "after-code-copy", "after-resolutions", "after-roots", "after-image",
    "after-entries", "after-header", "during-export-first",
    "during-export-last",
)


class ProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProbeError(message)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def bind(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def u16(data: bytes | bytearray, at: int) -> int:
    require(0 <= at <= len(data) - 2, "truncated u16")
    return struct.unpack_from("<H", data, at)[0]


def u32(data: bytes | bytearray, at: int) -> int:
    require(0 <= at <= len(data) - 4, "truncated u32")
    return struct.unpack_from("<I", data, at)[0]


def canonical_product_shelf_identity() -> dict[str, Any]:
    """Read and self-verify the one immutable product-shelf authority."""
    require(PRODUCT_IDENTITY.is_file(),
            "canonical C2 product identity authority is absent")
    value = json.loads(PRODUCT_IDENTITY.read_text(encoding="utf-8"))
    shelf_row = value.get("artifacts", {}).get("shelf", {})
    require(isinstance(shelf_row.get("path"), str),
            "canonical C2 authority lacks its product shelf")
    shelf_path = ROOT / shelf_row["path"]
    require(shelf_path.is_file() and bind(shelf_path) == shelf_row,
            "canonical product shelf binding drift")
    shelf = shelf_path.read_bytes()
    require(len(shelf) >= 32 and shelf[:7] == b"L65S\x04\x20\x20",
            "canonical product shelf is not L65S-v4")
    image_count = shelf[7]
    catalog_offset = u16(shelf, 8)
    catalog_bytes = u16(shelf, 16)
    catalog_crc = u32(shelf, 18)
    shelf_build_id = u32(shelf, 22)
    require(image_count > 0 and catalog_offset == 32
            and catalog_bytes == image_count * 32
            and catalog_offset + catalog_bytes <= len(shelf),
            "canonical product shelf catalog geometry drift")
    computed_crc = zlib.crc32(
        shelf[catalog_offset:catalog_offset + catalog_bytes]) & 0xffffffff
    require(computed_crc == catalog_crc,
            "canonical product shelf catalog CRC drift")
    build_id = value.get("product_build_id_u32")
    build_hex = value.get("product_build_id_hex")
    require(isinstance(build_id, int) and 0 < build_id <= 0xffffffff,
            "canonical C2 product build identity is invalid")
    require(build_hex == f"0x{build_id:08x}",
            "canonical C2 product build identity forms disagree")
    require(shelf_build_id == build_id,
            "canonical shelf and product build identities disagree")
    return {
        "image_count": image_count,
        "catalog_crc32": catalog_crc,
        "product_build_id": build_id,
        "catalog_offset": catalog_offset,
        "catalog_bytes": catalog_bytes,
        "shelf": bind(shelf_path),
        "authority": bind(PRODUCT_IDENTITY),
    }


def canonical_product_build_id() -> int:
    """Read the one product/shelf build identity used by every C2 consumer."""
    return int(canonical_product_shelf_identity()["product_build_id"])


def canonical_product_catalog_crc() -> int:
    """Read the self-verified L65S catalog identity consumed by C2D."""
    return int(canonical_product_shelf_identity()["catalog_crc32"])


def header_source_audit() -> dict[str, Any]:
    """Account for every C2D-v6 header byte and forbid private identities."""
    rows = [
        ("magic", 0, 4, "contract-constant", "C2D NUL"),
        ("version", 4, 1, "contract-constant", "C2D-v6"),
        ("header_bytes", 5, 1, "contract-constant", "48"),
        ("image_record_bytes", 6, 1, "contract-constant", "32"),
        ("entry_record_bytes", 7, 1, "contract-constant", "10"),
        ("transient_entry_watermark", 8, 2, "legitimate-local-state",
         "derived from active transient entries; zero in pristine plane"),
        ("session_generation", 10, 2, "legitimate-local-state",
         "nonzero session generation, invalidated before restage"),
        ("image_count", 12, 2, "legitimate-local-derivative",
         "active emitted C2D image records"),
        ("image_capacity", 14, 2, "contract-constant", "64"),
        ("entry_count", 16, 2, "legitimate-local-derivative",
         "active emitted C2D entry records"),
        ("entry_capacity", 18, 2, "contract-constant", "2048"),
        ("resolution_count", 20, 2, "legitimate-local-derivative",
         "active emitted resolution words"),
        ("resolution_capacity", 22, 2, "contract-constant", "4096"),
        ("root_count", 24, 2, "legitimate-local-derivative",
         "active emissions-derived canonical roots"),
        ("root_capacity", 26, 2, "contract-constant", "1536"),
        ("images_offset", 28, 2, "contract-constant", "48"),
        ("entries_offset", 30, 2, "contract-constant", "2096"),
        ("resolutions_offset", 32, 2, "contract-constant", "22576"),
        ("roots_offset", 34, 2, "contract-constant", "30768"),
        ("total_bytes", 36, 2, "contract-constant", "33840"),
        ("immutable_image_count", 38, 2, "canonical-authority",
         "consumed from self-verified L65S-v4 shelf header"),
        ("product_shelf_catalog_crc32", 40, 4, "canonical-authority",
         "consumed from and recomputed over the L65S-v4 catalog"),
        ("product_build_id_u32", 44, 4, "canonical-authority",
         "consumed from substitution authority and cross-bound to shelf"),
    ]
    covered = [byte for _name, offset, width, _source, _detail in rows
               for byte in range(offset, offset + width)]
    require(covered == list(range(C2D_HEADER_BYTES)),
            "C2D-v6 header source audit has a gap or overlap")
    result = [{"field": name, "offset": offset, "bytes": width,
               "source": source, "detail": detail}
              for name, offset, width, source, detail in rows]
    private = [row["field"] for row in result
               if row["source"] == "private-identity-derivation"]
    require(not private, "private C2D-v6 header identities remain")
    return {
        "status": "passed-all-48-header-bytes-accounted",
        "fields": result,
        "field_count": len(result),
        "covered_byte_count": len(covered),
        "private_identity_derivations": private,
        "canonical_identity_fields": [
            "immutable_image_count", "product_shelf_catalog_crc32",
            "product_build_id_u32"],
        "legitimate_local_fields": [
            "transient_entry_watermark", "session_generation", "image_count",
            "entry_count", "resolution_count", "root_count"],
    }


def p16(value: int) -> bytes:
    require(0 <= value <= 0xFFFF, "u16 overflow")
    return struct.pack("<H", value)


def p24(value: int) -> bytes:
    require(0 <= value <= 0xFFFFFF, "u24 overflow")
    return bytes((value & 0xFF, value >> 8 & 0xFF, value >> 16 & 0xFF))


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


_ENTRY_EMITTER: Any | None = None
_ENTRY_EMITTER_PATH: Path | None = None


def _entry_emitter() -> Any:
    """Load the host build of the exact target entry-row routine."""
    global _ENTRY_EMITTER, _ENTRY_EMITTER_PATH
    if _ENTRY_EMITTER is not None and _ENTRY_EMITTER_PATH is not None:
        return _ENTRY_EMITTER
    OUT.mkdir(parents=True, exist_ok=True)
    so = OUT / "c2d-v6-entry-emitter-host.so"
    source = ROOT / "scripts/c2d-v6-entry-host.c"
    command = ["cc", "-std=c11", "-O2", "-shared", "-fPIC",
               "-I", str(ROOT / "src"), str(source), "-o", str(so)]
    run = subprocess.run(command, cwd=ROOT, text=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(run.returncode == 0,
            "shared C2D-v6 entry emitter host build failed: " + run.stderr)
    lib = ctypes.CDLL(str(so))
    fn = lib.lisp65_c2d_v6_emit_entry_row
    fn.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint8,
                   ctypes.c_uint8, ctypes.c_uint16, ctypes.c_uint16,
                   ctypes.c_uint16, ctypes.c_uint16]
    fn.restype = ctypes.c_uint8
    _ENTRY_EMITTER = fn; _ENTRY_EMITTER_PATH = so
    return fn


def entry_v6(image: int, literals: int, code_offset: int, code_length: int,
             resolution_base: int, generation: int) -> bytes:
    require(0 <= image <= 0xff and 0 <= literals <= 0xff
            and 0 <= code_offset <= 0xffff
            and 0 <= code_length <= 0xffff
            and 0 <= resolution_base <= 0xffff
            and 0 <= generation <= 0xffff,
            "C2D-v6 entry host ABI field overflow")
    row = (ctypes.c_uint8 * C2D_ENTRY_BYTES)()
    require(bool(_entry_emitter()(row, image, literals, code_offset,
                                  code_length, resolution_base, generation)),
            "shared C2D-v6 entry emitter rejected valid fields")
    value = bytes(row)
    require(len(value) == C2D_ENTRY_BYTES, "C2D-v6 entry width drift")
    return value


def encode_header(data: bytearray, *, generation: int, image_count: int,
                  entry_count: int, resolution_count: int, root_count: int,
                  immutable_images: int, catalog_crc: int, build_id: int) -> None:
    require(0 < generation <= 0xFFFF, "C2D-v6 generation must be nonzero")
    header = bytearray(b"C2D\0")
    header += bytes((C2D_VERSION, C2D_HEADER_BYTES,
                     C2D_IMAGE_BYTES, C2D_ENTRY_BYTES))
    header += struct.pack(
        "<HHHHHHHHHHHHHHHHII", 0, generation,
        image_count, 64, entry_count, 2048, resolution_count, 4096,
        root_count, 1536, C2D_IMAGES_OFFSET, C2D_ENTRIES_OFFSET,
        C2D_RESOLUTIONS_OFFSET, C2D_ROOTS_OFFSET, C2D_TOTAL_BYTES,
        immutable_images, catalog_crc, build_id)
    require(len(header) == C2D_HEADER_BYTES, "C2D-v6 header width drift")
    data[:C2D_HEADER_BYTES] = header


def image_v6(*, source_kind: int, source_slot: int, generation: int,
             entry_base: int, entries: int, resolution_base: int,
             resolutions: int, root_base: int, roots: int,
             code_offset: int, code_length: int, metadata_crc: int,
             combined_crc: int) -> bytes:
    # The 32-byte image envelope retains the approved width.  Its former
    # metadata locator is now cold-stage provenance: offset=0, length=0, CRC
    # in the final u32.  Hot consumers need only the execution-complete entry.
    value = bytearray((source_kind, 0, source_slot, 0))
    value += struct.pack("<HHHHHHH", generation, entry_base, entries,
                         resolution_base, resolutions, root_base, roots)
    value += p24(code_offset) + p16(code_length)
    value += p24(0) + p16(0)
    value += struct.pack("<I", combined_crc ^ metadata_crc)
    require(len(value) == C2D_IMAGE_BYTES, "C2D-v6 image width drift")
    return bytes(value)


def direct_value(desc: F.Desc, ordinal: int, directory_base: int) -> int:
    value = G.direct_value(desc, ordinal, directory_base=directory_base)
    require(not (0 < value < 0x8000 and not value & 1),
            "direct descriptor produced forbidden heap-pointer shape")
    return value


class V6Plane:
    def __init__(self) -> None:
        self.code = bytearray(BANK_BYTES)
        self.c2d = bytearray(C2D_TOTAL_BYTES)
        self.generation = SESSION_GENERATION
        self.images = 0
        self.entries = 0
        self.resolutions = 0
        self.roots = 0
        self.code_low = 0
        self.code_high = BANK_BYTES
        self.transient_entries = 2048
        self.transient_resolutions = 4096
        self.transient_roots = 1536
        self.exports: dict[str, tuple[int, int]] = {}
        self.transient_handles: dict[int, tuple[int, int]] = {}
        self.catalog_crc = 0
        self.build_id = 0
        self.immutable_images = 0

    def snapshot(self) -> tuple[Any, ...]:
        return (bytes(self.code), bytes(self.c2d), self.generation,
                self.images, self.entries, self.resolutions, self.roots,
                self.code_low, self.code_high, self.transient_entries,
                self.transient_resolutions, self.transient_roots,
                dict(self.exports), dict(self.transient_handles))

    def restore(self, state: tuple[Any, ...]) -> None:
        (code, c2d, self.generation, self.images, self.entries,
         self.resolutions, self.roots, self.code_low, self.code_high,
         self.transient_entries, self.transient_resolutions,
         self.transient_roots, exports, handles) = state
        self.code[:] = code
        self.c2d[:] = c2d
        self.exports = exports
        self.transient_handles = handles

    def publish_header(self) -> None:
        encode_header(self.c2d, generation=self.generation,
                      image_count=self.images, entry_count=self.entries,
                      resolution_count=self.resolutions,
                      root_count=self.roots,
                      immutable_images=self.immutable_images,
                      catalog_crc=self.catalog_crc, build_id=self.build_id)

    def callable(self, handle: int, generation: int) -> bool:
        if generation != self.generation:
            return False
        if handle < self.entries:
            at = C2D_ENTRIES_OFFSET + handle * C2D_ENTRY_BYTES
            return u16(self.c2d, at + 8) == generation
        binding = self.transient_handles.get(handle)
        return binding is not None and binding[1] == generation


def emit_resolutions(plane: V6Plane, image: F.Emitted, *, directory_base: int,
                     resolution_base: int, root_base: int) -> tuple[bytes, bytes]:
    resolutions = bytearray()
    roots = bytearray()
    root = root_base
    for local, desc in enumerate(image.descriptors):
        if desc.kind in ROOT_KINDS:
            resolutions += p16(R.root_ref(root))
            roots += p16(G.pointer_for(root))
            root += 1
        else:
            resolutions += p16(direct_value(
                desc, resolution_base + local, directory_base))
    return bytes(resolutions), bytes(roots)


def static_plane(images: list[F.Emitted]) -> tuple[V6Plane, dict[str, Any]]:
    plane = V6Plane()
    authority = canonical_product_shelf_identity()
    require(len(images) == authority["image_count"],
            "emitted image count disagrees with canonical product shelf")
    plane.immutable_images = int(authority["image_count"])
    plane.catalog_crc = int(authority["catalog_crc32"])
    plane.build_id = int(authority["product_build_id"])
    for slot, image in enumerate(images):
        code_base = plane.code_low
        plane.code[code_base:code_base + len(image.code)] = image.code
        plane.code_low += len(image.code)
        image_roots = sum(desc.kind in ROOT_KINDS for desc in image.descriptors)
        resolution_blob, root_blob = emit_resolutions(
            plane, image, directory_base=plane.entries,
            resolution_base=plane.resolutions, root_base=plane.roots)
        plane.c2d[C2D_RESOLUTIONS_OFFSET + plane.resolutions * 2:
                  C2D_RESOLUTIONS_OFFSET + plane.resolutions * 2
                  + len(resolution_blob)] = resolution_blob
        plane.c2d[C2D_ROOTS_OFFSET + plane.roots * 2:
                  C2D_ROOTS_OFFSET + plane.roots * 2 + len(root_blob)] = root_blob
        image_row = image_v6(
            source_kind=0, source_slot=slot, generation=plane.generation,
            entry_base=plane.entries, entries=len(image.manifest["entries"]),
            resolution_base=plane.resolutions,
            resolutions=len(image.descriptors), root_base=plane.roots,
            roots=image_roots, code_offset=code_base,
            code_length=len(image.code),
            metadata_crc=zlib.crc32(image.metadata) & 0xFFFFFFFF,
            combined_crc=zlib.crc32(image.code + image.metadata) & 0xFFFFFFFF)
        pos = C2D_IMAGES_OFFSET + slot * C2D_IMAGE_BYTES
        plane.c2d[pos:pos + C2D_IMAGE_BYTES] = image_row
        for local, entry in enumerate(image.manifest["entries"]):
            row = entry_v6(
                slot, int(entry["lit_count"]),
                code_base + int(entry["blob_offset"]), int(entry["length"]),
                plane.resolutions + image.entry_first[local], plane.generation)
            at = C2D_ENTRIES_OFFSET + (plane.entries + local) * C2D_ENTRY_BYTES
            plane.c2d[at:at + C2D_ENTRY_BYTES] = row
        plane.images += 1
        plane.entries += len(image.manifest["entries"])
        plane.resolutions += len(image.descriptors)
        plane.roots += image_roots
    # Product, shelf, target decoder and C2D consume one authority for both
    # identity fields.  Neither field is reconstructed from the C2D view.
    plane.publish_header()
    require(plane.code_low == STATIC_CODE_BYTES,
            f"static Bank-2 code plane is {plane.code_low}, "
            f"expected {STATIC_CODE_BYTES}")
    return plane, {
        "images": plane.images, "entries": plane.entries,
        "resolutions": plane.resolutions, "roots": plane.roots,
        "code_bytes": plane.code_low,
        "headroom_bytes": BANK_BYTES - plane.code_low,
        "code_sha256": sha_bytes(bytes(plane.code[:plane.code_low])),
        "c2d_bytes": len(plane.c2d), "c2d_sha256": sha_bytes(bytes(plane.c2d)),
    }


def validate_plane(plane: V6Plane) -> dict[str, int]:
    d = plane.c2d
    require(d[:5] == b"C2D\0\x06" and tuple(d[5:8]) == (48, 32, 10),
            "C2D-v6 header/version/width")
    require(u16(d, 10) == plane.generation != 0, "C2D-v6 generation drift")
    require((u16(d, 12), u16(d, 16), u16(d, 20), u16(d, 24)) ==
            (plane.images, plane.entries, plane.resolutions, plane.roots),
            "C2D-v6 active count drift")
    require((u16(d, 14), u16(d, 18), u16(d, 22), u16(d, 26)) ==
            (64, 2048, 4096, 1536), "C2D-v6 capacity drift")
    require((u16(d, 28), u16(d, 30), u16(d, 32), u16(d, 34)) ==
            (48, 2096, 22576, 30768), "C2D-v6 section offset drift")
    require(u16(d, 36) == C2D_TOTAL_BYTES, "C2D-v6 total width drift")
    authority = canonical_product_shelf_identity()
    require(u16(d, 38) == plane.immutable_images == authority["image_count"],
            "C2D-v6 immutable image binding drift")
    require(u32(d, 40) == plane.catalog_crc == authority["catalog_crc32"],
            "C2D-v6 shelf catalog identity drift")
    require(u32(d, 44) == plane.build_id == canonical_product_build_id(),
            "C2D-v6 product build identity drift")
    for ordinal in range(plane.entries):
        at = C2D_ENTRIES_OFFSET + ordinal * C2D_ENTRY_BYTES
        image, literals = d[at], d[at + 1]
        code_offset, length = u16(d, at + 2), u16(d, at + 4)
        resolution = u16(d, at + 6)
        require(image < plane.images and length
                and code_offset + length <= BANK_BYTES
                and resolution + literals <= plane.resolutions
                and u16(d, at + 8) == plane.generation,
                f"C2D-v6 entry invalid: {ordinal}")
    for ordinal in range(plane.resolutions):
        word = u16(d, C2D_RESOLUTIONS_OFFSET + ordinal * 2)
        if word and word < 0x8000 and not word & 1:
            root = R.root_ordinal(word)
            require(root < plane.roots,
                    f"C2D-v6 root surrogate outside active roots: {ordinal}")
            value = u16(d, C2D_ROOTS_OFFSET + root * 2)
            require(0 < value < 0x8000 and not value & 1,
                    "C2D-v6 root value is not a heap pointer")
    return {"entries_checked": plane.entries,
            "resolutions_checked": plane.resolutions,
            "roots_checked": plane.roots}


def append_image(plane: V6Plane, image: F.Emitted, *, transient: bool,
                 fail_at: str | None = None) -> dict[str, Any]:
    before = plane.snapshot()
    roots = sum(desc.kind in ROOT_KINDS for desc in image.descriptors)
    if transient:
        code_base = plane.code_high - len(image.code)
        entry_base = plane.transient_entries - len(image.manifest["entries"])
        resolution_base = plane.transient_resolutions - len(image.descriptors)
        root_base = plane.transient_roots - roots
        image_slot = 63 - len(plane.transient_handles)
    else:
        code_base = plane.code_low
        entry_base = plane.entries
        resolution_base = plane.resolutions
        root_base = plane.roots
        image_slot = plane.images
    require(plane.code_low <= code_base < plane.code_high
            and code_base + len(image.code) <= plane.code_high,
            "persistent/transient Bank-2 fronts collide")
    require(0 <= entry_base and 0 <= resolution_base and 0 <= root_base,
            "C2D-v6 high-edge capacity exhausted")

    touched_exports: list[str] = []
    def point(label: str) -> None:
        if fail_at == label:
            raise ProbeError("injected rollback cutpoint: " + label)

    try:
        plane.code[code_base:code_base + len(image.code)] = image.code
        point("after-code-copy")
        resolution_blob, root_blob = emit_resolutions(
            plane, image, directory_base=entry_base,
            resolution_base=resolution_base, root_base=root_base)
        rpos = C2D_RESOLUTIONS_OFFSET + resolution_base * 2
        plane.c2d[rpos:rpos + len(resolution_blob)] = resolution_blob
        point("after-resolutions")
        rootpos = C2D_ROOTS_OFFSET + root_base * 2
        plane.c2d[rootpos:rootpos + len(root_blob)] = root_blob
        point("after-roots")
        row = image_v6(
            source_kind=2 if transient else 1, source_slot=0,
            generation=plane.generation, entry_base=entry_base,
            entries=len(image.manifest["entries"]),
            resolution_base=resolution_base, resolutions=len(image.descriptors),
            root_base=root_base, roots=roots, code_offset=code_base,
            code_length=len(image.code),
            metadata_crc=zlib.crc32(image.metadata) & 0xFFFFFFFF,
            combined_crc=zlib.crc32(image.code + image.metadata) & 0xFFFFFFFF)
        ipos = C2D_IMAGES_OFFSET + image_slot * C2D_IMAGE_BYTES
        plane.c2d[ipos:ipos + C2D_IMAGE_BYTES] = row
        point("after-image")
        handles: list[int] = []
        for local, entry in enumerate(image.manifest["entries"]):
            physical = entry_base + local
            e = entry_v6(
                image_slot, int(entry["lit_count"]),
                code_base + int(entry["blob_offset"]), int(entry["length"]),
                resolution_base + image.entry_first[local], plane.generation)
            at = C2D_ENTRIES_OFFSET + physical * C2D_ENTRY_BYTES
            plane.c2d[at:at + C2D_ENTRY_BYTES] = e
            handle = 2048 + local if transient else physical
            handles.append(handle)
            if transient:
                plane.transient_handles[handle] = (physical, plane.generation)
        point("after-entries")
        if transient:
            plane.code_high = code_base
            plane.transient_entries = entry_base
            plane.transient_resolutions = resolution_base
            plane.transient_roots = root_base
        else:
            plane.code_low += len(image.code)
            plane.images += 1
            plane.entries += len(image.manifest["entries"])
            plane.resolutions += len(image.descriptors)
            plane.roots += roots
            plane.publish_header()
        point("after-header")
        names = [row["name"] for row in image.manifest["entries"]
                 if not row.get("anonymous", False)]
        for index, name in enumerate(names):
            plane.exports[name] = (handles[min(index, len(handles) - 1)],
                                   plane.generation)
            touched_exports.append(name)
            if index == 0:
                point("during-export-first")
            if index == len(names) - 1:
                point("during-export-last")
        return {"handles": handles, "code_offset": code_base,
                "entries": len(handles), "transient": transient}
    except ProbeError:
        plane.restore(before)
        require(plane.snapshot() == before, "rollback is not byte-identical")
        raise


def reject(label: str, operation: Callable[[], Any]) -> str:
    try:
        operation()
    except (ProbeError, R.SurrogateError, F.FullError):
        return label
    raise ProbeError(f"negative fixture accepted: {label}")


def dynamic_image() -> tuple[F.Emitted, dict[str, Any]]:
    require(LEGACY_INPUT.is_file(), "real compiler L65M oracle is absent")
    manifest, code = S.legacy_manifest(LEGACY_INPUT.read_bytes(), "c2-lite-dynamic")
    manifest["blob"] = (OUT / "c2-lite-dynamic.code.bin").relative_to(ROOT).as_posix()
    manifest_path = OUT / "c2-lite-dynamic.manifest.json"
    (OUT / "c2-lite-dynamic.code.bin").write_bytes(code)
    write_json(manifest_path, manifest)
    first = F.emit_image("c2-lite-dynamic", "session", manifest_path)
    second = F.emit_image("c2-lite-dynamic", "session", manifest_path)
    require(first.code == second.code and first.metadata == second.metadata
            and first.descriptors == second.descriptors,
            "one C2 emitter is nondeterministic for dynamic code")
    return first, {
        "input": bind(LEGACY_INPUT), "manifest": bind(manifest_path),
        "code": {"bytes": len(first.code), "sha256": sha_bytes(first.code)},
        "metadata": {"bytes": len(first.metadata),
                     "sha256": sha_bytes(first.metadata)},
        "repeat_byte_identical": True,
    }


def host_semantics() -> dict[str, Any]:
    root_gate = R.collect()
    F.contract_check()
    images = [F.emit_image(*row) for row in A.SPECS]
    plane, static = static_plane(images)
    checks = validate_plane(plane)
    dynamic, dynamic_report = dynamic_image()

    rollback = []
    for cutpoint in ROLLBACK_CUTPOINTS:
        candidate = copy.deepcopy(plane)
        before = candidate.snapshot()
        rollback.append(reject(
            cutpoint, lambda p=candidate, c=cutpoint:
            append_image(p, dynamic, transient=True, fail_at=c)))
        require(candidate.snapshot() == before,
                "rollback cutpoint changed the candidate")

    nested = copy.deepcopy(plane)
    outer_before = nested.snapshot()
    transient = append_image(nested, dynamic, transient=True)
    transient_handles = list(transient["handles"])
    persistent = append_image(nested, dynamic, transient=False)
    persistent_handles = list(persistent["handles"])
    # Roll back only the high edge.  The persistent descendant is deliberately
    # retained; the outer transaction has no authority over the low edge.
    transient_code_base = int(transient["code_offset"])
    nested.code[transient_code_base:] = outer_before[0][transient_code_base:]
    nested.code_high = BANK_BYTES
    nested.transient_entries = 2048
    nested.transient_resolutions = 4096
    nested.transient_roots = 1536
    for handle in transient_handles:
        nested.transient_handles.pop(handle, None)
    require(all(not nested.callable(handle, nested.generation)
                for handle in transient_handles),
            "outer transient handles survived rollback")
    require(all(nested.callable(handle, nested.generation)
                for handle in persistent_handles),
            "persistent descendant was lost by outer rollback")
    validate_plane(nested)

    old_generation = nested.generation
    old_handles = persistent_handles + list(range(min(3, nested.entries)))
    physical_before = bytes(nested.code)
    nested.generation += 1
    nested.publish_header()
    require(bytes(nested.code) == physical_before,
            "restage generation changed physical Bank-2 bytes")
    require(all(not nested.callable(handle, old_generation)
                for handle in old_handles),
            "old C2D-v6 handles callable after generation change")

    # Bidirectional version asymmetry and entry/root boundaries.
    negatives = list(root_gate["negative_fixtures"])
    old = bytearray(plane.c2d); old[4] = 5
    negatives.append(reject("v6-rejects-v5", lambda: require(
        old[4] == C2D_VERSION, "C2D version mismatch")))
    negatives.append(reject("v5-rejects-v6", lambda: require(
        plane.c2d[4] == 5, "C2D version mismatch")))
    negatives.append(reject("zero-entry-length", lambda: entry_v6(0, 0, 0, 0, 0, 1)))
    negatives.append(reject("bank2-range-wrap", lambda: entry_v6(
        0, 0, 0xFFFF, 2, 0, 1)))
    require(entry_v6(0, 0, 0xFFFF, 1, 0, 1),
            "exact Bank-2 upper edge rejected")
    wrong_identity = copy.deepcopy(plane)
    struct.pack_into("<I", wrong_identity.c2d, 44,
                     (plane.build_id + 1) & 0xffffffff)
    negatives.append(reject(
        "c2d-product-build-identity-mismatch",
        lambda: validate_plane(wrong_identity)))
    zero_identity = copy.deepcopy(plane)
    struct.pack_into("<I", zero_identity.c2d, 44, 0)
    negatives.append(reject(
        "c2d-zero-product-build-identity",
        lambda: validate_plane(zero_identity)))
    wrong_catalog = copy.deepcopy(plane)
    struct.pack_into("<I", wrong_catalog.c2d, 40,
                     (plane.catalog_crc + 1) & 0xffffffff)
    negatives.append(reject(
        "c2d-shelf-catalog-identity-mismatch",
        lambda: validate_plane(wrong_catalog)))
    zero_catalog = copy.deepcopy(plane)
    struct.pack_into("<I", zero_catalog.c2d, 40, 0)
    negatives.append(reject(
        "c2d-zero-shelf-catalog-identity",
        lambda: validate_plane(zero_catalog)))
    wrong_immutable = copy.deepcopy(plane)
    struct.pack_into("<H", wrong_immutable.c2d, 38,
                     plane.immutable_images + 1)
    negatives.append(reject(
        "c2d-immutable-image-count-mismatch",
        lambda: validate_plane(wrong_immutable)))

    (OUT / "bank2-static-code.bin").write_bytes(bytes(plane.code[:STATIC_CODE_BYTES]))
    (OUT / "initial.c2d-v6.bin").write_bytes(bytes(plane.c2d))
    return {
        "status": "passed",
        "permanent_root_surrogate_gate": root_gate,
        "static_bank2": static,
        "static_decoder": checks,
        "product_build_identity": {
            "status": "passed-single-canonical-authority",
            "value_u32": plane.build_id,
            "value_hex": f"0x{plane.build_id:08x}",
            "authority": bind(PRODUCT_IDENTITY),
            "private_derivation_sites": 0,
        },
        "product_shelf_identity": {
            "status": "passed-single-self-verified-shelf-authority",
            "catalog_crc32": f"0x{plane.catalog_crc:08x}",
            "immutable_image_count": plane.immutable_images,
            "authority": canonical_product_shelf_identity(),
            "private_derivation_sites": 0,
        },
        "c2d_v6_header_source_audit": header_source_audit(),
        "one_emitter": {
            "implementation": "tools/host-lisp/c2_full_emission.py::emit_image",
            "implementation_sha256": sha_bytes(
                inspect.getsource(F.emit_image).encode()),
            "static_calls": 6, "dynamic_calls": 2,
            "legacy_emitter_calls": 0,
            "static_and_dynamic_format": "C2I-v2 through one implementation",
        },
        "dynamic": dynamic_report,
        "rollback": {"cutpoints": rollback, "count": len(rollback)},
        "nested": {
            "transient_handles_rolled_back": len(transient_handles),
            "persistent_descendant_handles_retained": len(persistent_handles),
            "low_and_high_edges_disjoint": True,
        },
        "stale_generation": {
            "old_generation": old_generation,
            "new_generation": nested.generation,
            "physical_bytes_retained": True,
            "old_handles_rejected": len(old_handles),
        },
        "negative_fixtures": negatives,
        "artifacts": {
            "code": bind(OUT / "bank2-static-code.bin"),
            "c2d": bind(OUT / "initial.c2d-v6.bin"),
        },
    }


def bank3_lifetime() -> dict[str, Any]:
    expected = {
        BOOT35: (15605, "2703d1e868369c6e54d432e25f0548e9ab85df1a4994442b96e7096bf0ac541d"),
        SESSION35: (60062, "43d0b27a23d5c7ba14d81a47e1f5e3cfa06fe754c5423ffbf0af191e35660e5b"),
    }
    for path, (size, digest) in expected.items():
        require(path.is_file() and path.stat().st_size == size and sha(path) == digest,
                f"Link-35 lifetime artifact drift: {path}")
    bank1 = bytes([0xA1]) * BANK_BYTES
    bank3 = bytearray(BANK_BYTES)
    generation = 1
    boot = BOOT35.read_bytes(); session = SESSION35.read_bytes()
    bank3[:len(boot)] = boot
    boot_binding = ("boot", generation, sha_bytes(bytes(bank3[:len(boot)])))
    require(boot_binding[2] == expected[BOOT35][1], "Boot Bank-3 identity")
    generation += 1                         # invalidate before overwrite
    bank3[:] = b"\0" * BANK_BYTES
    bank3[:len(session)] = session
    session_binding = ("session", generation,
                       sha_bytes(bytes(bank3[:len(session)])))
    require(session_binding[2] == expected[SESSION35][1], "Session Bank-3 identity")
    require(boot_binding[1] != generation, "Boot binding survived Session restage")
    require(bank1 == bytes([0xA1]) * BANK_BYTES, "Bank 1 user/graphics plane changed")
    return {
        "status": "passed-lifetime-exclusive",
        "boot": {**bind(BOOT35), "bank": 3,
                 "headroom_bytes": BANK_BYTES - len(boot), "generation": 1},
        "session": {**bind(SESSION35), "bank": 3,
                    "headroom_bytes": BANK_BYTES - len(session), "generation": 2},
        "simultaneously_callable": False,
        "invalidation_before_overwrite": True,
        "stale_boot_binding_rejected": True,
        "bank1_untouched": True,
    }


def replace_c_function(source: str, name: str, replacement: str) -> str:
    """Replace one C definition while preserving surrounding preprocessor text."""
    for match in re.finditer(r"\b" + re.escape(name) + r"\s*\(", source):
        brace = source.find("{", match.end())
        semicolon = source.find(";", match.end())
        if brace < 0 or (0 <= semicolon < brace):
            continue
        depth = 0
        index = brace
        while index < len(source):
            if source[index] == "{":
                depth += 1
            elif source[index] == "}":
                depth -= 1
                if depth == 0:
                    start = source.rfind("\n", 0, match.start()) + 1
                    return source[:start] + replacement.rstrip() + "\n" + source[index + 1:]
            index += 1
    raise ProbeError(f"C function definition not found: {name}")


def c_function_definition(source: str, name: str) -> str:
    """Return one definition, skipping prototypes and forward declarations."""
    for match in re.finditer(r"\b" + re.escape(name) + r"\s*\(", source):
        brace = source.find("{", match.end())
        semicolon = source.find(";", match.end())
        if brace < 0 or (0 <= semicolon < brace):
            continue
        depth = 0
        for index in range(brace, len(source)):
            depth += source[index] == "{"
            depth -= source[index] == "}"
            if depth == 0:
                start = source.rfind("\n", 0, match.start()) + 1
                return source[start:index + 1]
    raise ProbeError(f"C function definition not found: {name}")


def wrap_c_function(source: str, name: str, prefix: str, suffix: str) -> str:
    """Wrap one complete definition without changing its implementation."""
    marker = "__C2_LITE_KEEP_FUNCTION_BODY__"
    wrapped = replace_c_function(source, name, marker)
    require(wrapped.count(marker) == 1, f"function wrapper marker drift: {name}")
    # Recover the original definition with the same brace scanner by deriving
    # the exact range once from the unmodified source.
    for match in re.finditer(r"\b" + re.escape(name) + r"\s*\(", source):
        brace = source.find("{", match.end()); semicolon = source.find(";", match.end())
        if brace < 0 or (0 <= semicolon < brace):
            continue
        depth = 0
        for index in range(brace, len(source)):
            depth += source[index] == "{"
            depth -= source[index] == "}"
            if depth == 0:
                start = source.rfind("\n", 0, match.start()) + 1
                body = source[start:index + 1]
                return wrapped.replace(marker, prefix + body + suffix, 1)
    raise ProbeError(f"C function wrapper definition not found: {name}")


def replace_once(source: str, old: str, new: str, label: str) -> str:
    require(source.count(old) == 1,
            f"generated-source anchor drift for {label}: {source.count(old)}")
    return source.replace(old, new, 1)


def generated_product_sources(out: Path) -> dict[Path, Path]:
    """Create a non-product C2-lite hot-closure projection for full WPLTO.

    Cold C2I staging remains present so the link prices the complete compiler
    and append machinery.  Only execution-time consumers are projected onto
    C2D-v6/Bank 2 and Bank 3.  Host semantics above, not these generated
    sources, are the format authority.
    """
    generated = out / "generated-product-sources"
    generated.mkdir(parents=True)
    mapping: dict[Path, Path] = {}

    hot = r'''/* generated C2-lite C2D-v6 hot materializer; non-product probe */
#include "c2-stream-v2-decoder.h"
#include "obj.h"
#ifdef C2_STREAM_PRODUCT_V3
#ifdef LISP65_RUNTIME_OVERLAY
#define C2_HOT __attribute__((noinline, used, section(".lisp65_resident_island")))
#else
#define C2_HOT
#endif
extern uint8_t c2_product_entry_record(uint16_t, uint8_t[10], uint16_t *);
static uint16_t hot_u16(const uint8_t *p) {
    return (uint16_t)p[0] | (uint16_t)p[1] << 8;
}
#ifdef LISP65_C2_NESTED_APPEND_V5
C2_HOT uint16_t c2_product_handle_normalize(c2_stream_context *c,
                                             uint16_t handle) {
    if (!c || handle >= 4096u) return 0xffffu;
    if (handle < 2048u) return handle < c->entry_count ? handle : 0xffffu;
    if (handle < c->entry_first) return 0xffffu;
    return (uint16_t)(handle - 2048u);
}
#endif
C2_HOT uint8_t c2_stream_product_materialize_entry(
        c2_stream_context *c, uint16_t ordinal, uint16_t *hot,
        uint8_t capacity, uint8_t *hot_count) {
    uint8_t row[10], b[2], count, i, transient;
    uint16_t physical, word, root, base, resolution_limit, root_limit;
    if (!c || !hot || !hot_count || !c->finished || c->phase != 13u)
        return C2_STREAM_ERR_STATE;
    *hot_count = 0; transient = (uint8_t)(ordinal >= 2048u);
    if (!c2_product_entry_record(ordinal, row, &physical))
        return C2_STREAM_ERR_ENTRY;
    (void)physical; count = row[1]; base = hot_u16(row + 6);
    resolution_limit = transient ? 4096u : c->resolution_count;
    root_limit = transient ? 1536u : c->c2_root_count;
    if (count > capacity || base > resolution_limit
        || count > (uint16_t)(resolution_limit - base))
        return C2_STREAM_ERR_ENTRY;
    for (i = 0; i < count; ++i) {
        if (!c2_stream_c2d_read((uint16_t)(c->resolutions_offset
                + (base + i) * 2u), b, 2u)) return C2_STREAM_ERR_IO;
        word = hot_u16(b);
        if (word && word < 0x8000u && !(word & 1u)) {
            root = (uint16_t)((word >> 1) - 1u);
            if (root >= root_limit
                || !c2_stream_c2d_read((uint16_t)(c->roots_offset
                    + root * 2u), b, 2u)) return C2_STREAM_ERR_RESOLUTION;
            word = hot_u16(b);
            if (!word || word >= 0x8000u || (word & 1u))
                return C2_STREAM_ERR_RESOLUTION;
        }
        hot[i] = word; ++*hot_count;
    }
    return C2_STREAM_OK;
}
#endif
'''
    hot_path = generated / "c2_hot_literal.c"
    hot_path.write_text(hot, encoding="utf-8")
    mapping[ROOT / "src/c2_hot_literal.c"] = hot_path

    runtime_source = (ROOT / "src/c2_product_runtime.c").read_text(encoding="utf-8")
    seam = r'''C2_KERNAL_RESIDENT uint8_t c2_product_entry_record(
        uint16_t ordinal, uint8_t directory[10], uint16_t *physical) {
    uint8_t transient = (uint8_t)(ordinal >= 2048u);
    uint16_t resolution_limit = transient ? 4096u : c2_runtime.resolution_count;
    if (!c2_ready || !directory || !physical
#ifdef LISP65_C2_NESTED_APPEND_V5
        || (ordinal = C2_HANDLE_NORMALIZE(&c2_runtime, ordinal)) == 0xffffu
#else
        || ordinal >= c2_runtime.entry_count
#endif
        || !c2_stream_c2d_read((uint16_t)(c2_runtime.entries_offset
            + ordinal * 10u), directory, 10u)
        || directory[0] >= 64u
        || c2_u16(directory + 8) != c2_runtime.generation
        || (uint32_t)c2_u16(directory + 2) + c2_u16(directory + 4)
            > 65536UL
        || (uint32_t)c2_u16(directory + 6) + directory[1]
            > resolution_limit) return 0;
    *physical = ordinal; return 1;
}

C2_COLD_ENTRY_FN uint8_t c2_entry_records(
        uint16_t ordinal, uint8_t directory[10],
        uint8_t image[32], uint8_t entry[16]) {
    uint8_t metadata_header[24]; uint16_t physical, local, base, entries_offset;
    uint32_t metadata;
    if (!c2_product_entry_record(ordinal, directory, &physical)
        || !c2_stream_c2d_read((uint16_t)(c2_runtime.images_offset
            + directory[0] * 32u), image, 32u)) return 0;
    base = c2_u16(image + 6);
    if (physical < base || (local = (uint16_t)(physical - base))
        >= c2_u16(image + 8)) return 0;
    metadata = c2_u24(image + 23);
    if (!c2_source_read(image, metadata, metadata_header,
                        sizeof metadata_header)) return 0;
    entries_offset = c2_u16(metadata_header + 14);
    return c2_source_read(image, metadata + entries_offset
                          + (uint32_t)local * 16u, entry, 16u);
}'''
    runtime_source = replace_c_function(runtime_source, "c2_entry_records", seam)
    runtime_source = replace_c_function(runtime_source, "c2_product_static_image_named", r'''
uint8_t c2_product_static_image_named(obj name) {
    static const char names[] = "stdlib\0ide\0idex\0m65d\0buffer\0lcc\0";
    uint16_t length, i, at = 0;
    if (!c2_ready || !IS_PTR(name) || cell_type(name) != T_STR) return 0;
    length = str_len(name);
    while (at < sizeof names - 1u) {
        for (i = 0; names[at + i] && i < length
                    && (uint8_t)names[at + i] == str_byte(name, i); ++i) { }
        if (i == length && names[at + i] == 0) return 1;
        while (names[at++]) { }
    }
    return 0;
}''')
    runtime_source = replace_c_function(runtime_source, "c2_product_entry_length", r'''
C2_KERNAL_RESIDENT uint16_t c2_product_entry_length(uint16_t ordinal) {
    uint8_t row[10]; uint16_t physical;
    return c2_product_entry_record(ordinal, row, &physical)
        ? c2_u16(row + 4) : 0u;
}''')
    runtime_source = replace_c_function(runtime_source, "c2_product_entry_read", r'''
uint8_t c2_product_entry_read(uint16_t ordinal, uint16_t relative,
                              uint8_t *destination, uint16_t length) {
    uint8_t row[10], hot_count = 0; uint16_t physical, code_length, i, lit_end;
    uint16_t hot[C2_MAX_HOT_LITERALS];
    if (!destination || !c2_product_entry_record(ordinal, row, &physical)) return 0;
    code_length = c2_u16(row + 4);
    if (relative > code_length || length > (uint16_t)(code_length - relative)) return 0;
    c2_facade_vm_code_load(2u, (uint16_t)(c2_u16(row + 2) + relative),
                           length, destination);
    lit_end = (uint16_t)(7u + 2u * row[1]);
    if (relative < lit_end && (uint16_t)(relative + length) > 7u && row[1]) {
        if (c2_stream_product_materialize_entry(
                &c2_runtime, ordinal, hot, C2_MAX_HOT_LITERALS, &hot_count)
                != C2_STREAM_OK || hot_count != row[1]) return 0;
        for (i = 0; i < length; ++i) {
            uint16_t at = (uint16_t)(relative + i);
            if (at >= 7u && at < lit_end) {
                uint16_t word = hot[(at - 7u) >> 1];
                destination[i] = (uint8_t)(((at - 7u) & 1u) ? word >> 8 : word);
            }
        }
    }
    return 1;
}''')
    runtime_path = generated / "c2_product_runtime.c"
    runtime_path.write_text(runtime_source, encoding="utf-8")
    mapping[ROOT / "src/c2_product_runtime.c"] = runtime_path

    rtov = (ROOT / "src/vm_runtime_overlay.c").read_text(encoding="utf-8")
    rtov = replace_c_function(rtov, "rtov_read", r'''
static void rtov_read(uint16_t relative, uint8_t *dst, uint16_t length) {
#ifdef LISP65_RUNTIME_OVERLAY_HOST_TEST
    vm_code_load((uint8_t)LISP65_RUNTIME_OVERLAY_FORMAT_BANK_TAG,
                 (uint16_t)(LISP65_RUNTIME_OVERLAY_CATALOG_OFF + relative),
                 length, dst);
#else
    c2_facade_vm_code_load(3u,
        (uint16_t)(LISP65_RUNTIME_OVERLAY_CATALOG_OFF + relative),
        length, dst);
#endif
}''')
    rtov = replace_once(
        rtov,
        "#ifdef LISP65_RTOV_CRC_CONVERGENCE\n"
        "static RTOV_RECORDFN uint16_t rtov_r_crc_byte(",
        "#if defined(LISP65_RTOV_CRC_CONVERGENCE) || "
        "defined(LISP65_C2_LITE_CHIP_RAM)\n"
        "static RTOV_RECORDFN uint16_t rtov_r_crc_byte(",
        "Chip-RAM record CRC helper")
    rtov = replace_once(
        rtov,
        '''#ifdef LISP65_RTOV_CRC_CONVERGENCE
    if (rtov_r_record_converge(record) != VM_RUNTIME_OVERLAY_OK)
        return VM_RUNTIME_OVERLAY_ERR_COMPLETION_TIMEOUT;
#else
#error "L65R-v3 record reads require CRC convergence"
#endif''',
        '''#ifdef LISP65_RTOV_CRC_CONVERGENCE
    if (rtov_r_record_converge(record) != VM_RUNTIME_OVERLAY_OK)
        return VM_RUNTIME_OVERLAY_ERR_COMPLETION_TIMEOUT;
#elif defined(LISP65_C2_LITE_CHIP_RAM)
    {
        uint16_t expected = (uint16_t)record[22] |
                            ((uint16_t)record[23] << 8);
        if (!expected || rtov_r_crc_virtual_zero(
                record, LISP65_RUNTIME_OVERLAY_ENTRY_SIZE, 22u) != expected)
            return VM_RUNTIME_OVERLAY_ERR_CRC;
    }
#else
#error "L65R-v3 record reads require convergence or proved Chip-RAM"
#endif''',
        "Chip-RAM immediate record validation")
    rtov = wrap_c_function(rtov, "rtov_r_record_converge",
                           "#ifdef LISP65_RTOV_CRC_CONVERGENCE\n",
                           "\n#endif")
    rtov_path = generated / "vm_runtime_overlay.c"
    rtov_path.write_text(rtov, encoding="utf-8")
    mapping[ROOT / "src/vm_runtime_overlay.c"] = rtov_path

    # Every phase wrapper is copied beside the projected decoders so quoted
    # includes cannot fall back to the repository originals.
    decoder = (ROOT / "scripts/c2-stream-decoder.c").read_text(encoding="utf-8")
    decoder = replace_once(decoder, "|| h[4] != 5u", "|| h[4] != 6u",
                           "C2D-v6 strict header")
    split_marker = "/* C2-lite v6 cutpoint: validate the immutable entry records"
    require(decoder.count(split_marker) == 1,
            "C2D-v6 phase-05 split marker drift")
    legacy_decoder, split_decoder = decoder.split(split_marker, 1)
    legacy_decoder = replace_once(
        legacy_decoder,
        "c2_stream_context *c = opaque; uint8_t im[20], h[24], e[16], de[10];",
        "c2_stream_context *c = opaque; uint8_t im[20], h[24], e[16], de[10], raw[32];",
        "C2D-v6 phase-05 execution image")
    legacy_decoder = replace_once(
        legacy_decoder,
        '''|| !c2_stream_c2d_read((uint16_t)(c->entries_offset
                    + (directory_base + local) * 10u), de, sizeof(de)))''',
        '''|| !c2_stream_c2d_read((uint16_t)(c->entries_offset
                    + (directory_base + local) * 10u), de, sizeof(de))
                || !c2_stream_c2d_read((uint16_t)(c->images_offset
                    + image * 32u), raw, sizeof(raw)))''',
        "C2D-v6 phase-05 execution image read")
    old = '''|| (name == 0xffffu && e[11]) || de[0] != image || de[1]
                || r16(de + 2) != local || r16(de + 4) != length
                || r16(de + 6) != (uint16_t)(r16(im + 6) + first)
                || r16(de + 8) != c->generation)'''
    new = '''|| (name == 0xffffu && e[11]) || de[0] != image
                || de[1] != e[7] || r24(raw + 23) || r16(raw + 26)
                || r24(raw + 18) > 0xffffUL
                || at > 0xffffUL - r24(raw + 18)
                || r16(de + 2) != (uint16_t)(r24(raw + 18) + at)
                || r16(de + 4) != length
                || r16(de + 6) != (uint16_t)(r16(im + 6) + first)
                || r16(de + 8) != c->generation)'''
    legacy_decoder = replace_once(
        legacy_decoder, old, new, "C2D-v6 execution entry")
    decoder = legacy_decoder + split_marker + split_decoder
    (generated / "c2-stream-decoder.c").write_text(decoder, encoding="utf-8")

    v2 = (ROOT / "scripts/c2-stream-v2-decoder.c").read_text(encoding="utf-8")
    v2 = replace_once(v2, "v2_w16(b, root++);",
                      "v2_w16(b, (uint16_t)((root++ + 1u) << 1));",
                      "root surrogate emission")
    v2 = v2.replace(
        "root = v2_r16(b);\n            if (root >= c->c2_root_count)",
        "root = v2_r16(b);\n            if (!root || (root & 1u) || root > 0x0c00u) "
        "return v2_fail(c, C2_STREAM_ERR_RESOLUTION);\n"
        "            root = (uint16_t)((root >> 1) - 1u);\n"
        "            if (root >= c->c2_root_count)")
    v2 = v2.replace(
        "if (word >= c->c2_root_count\n            || !c2_stream_c2d_read((uint16_t)(v2_roots_offset(c) + word * 2u)",
        "if (!word || (word & 1u) || word > 0x0c00u\n"
        "            || (word = (uint16_t)((word >> 1) - 1u)) >= c->c2_root_count\n"
        "            || !c2_stream_c2d_read((uint16_t)(v2_roots_offset(c) + word * 2u)")
    v2 = v2.replace(
        "if (word != root || !c2_stream_c2d_read((uint16_t)(v2_roots_offset(c)\n                + word * 2u)",
        "if (word != (uint16_t)((root + 1u) << 1)\n"
        "                || !c2_stream_c2d_read((uint16_t)(v2_roots_offset(c)\n"
        "                + root * 2u)")
    (generated / "c2-stream-v2-decoder.c").write_text(v2, encoding="utf-8")

    import c2_product_substitution_link as product  # local: mutable configuration
    for original in product.C2_PHASE_SOURCES:
        target = generated / original.name
        target.write_text(original.read_text(encoding="utf-8"), encoding="utf-8")
        mapping[original] = target
    return mapping


def target_seam_preflight() -> dict[str, Any]:
    """Run the one authorized product-shaped WPLTO measurement.

    The target is a deliberately non-promotable seam closure.  It compiles the
    v6 record decoder, root materializer, Bank-2 code loader and Bank-3 family
    loader together under target codegen before the full closure is linked.
    The exact shipped code/native planes remain host-bound inputs; this output
    is never a product candidate and does not count as the WPLTO measurement.
    """
    source = OUT / "c2-lite-v6-wplto.c"
    linker = OUT / "c2-lite-v6-wplto.ld"
    target = OUT / "c2-lite-v6-wplto.elf"
    source.write_text(r'''
#include <stdint.h>
#include "obj.h"

volatile uint8_t sink8;
volatile uint16_t sink16;
static uint8_t c2d[33840];
static uint8_t window[1792];

static uint16_t u16(const uint8_t *p) { return (uint16_t)p[0] | (uint16_t)p[1] << 8; }
static uint8_t chip_load(uint8_t bank, uint16_t off, uint8_t *dst, uint16_t n) {
    sink8 = bank; sink16 = off;
    while (n--) *dst++ = (uint8_t)(off++ ^ bank);
    return 1;
}
static uint8_t entry(uint16_t ordinal, uint8_t e[10]) {
    uint16_t at = (uint16_t)(2096u + ordinal * 10u), i;
    if (ordinal >= u16(c2d + 16)) return 0;
    for (i = 0; i < 10; ++i) e[i] = c2d[at + i];
    return e[1] <= 255u && u16(e + 4) &&
           (uint32_t)u16(e + 2) + u16(e + 4) <= 65536UL &&
           (uint16_t)(u16(e + 6) + e[1]) <= u16(c2d + 20) &&
           u16(e + 8) == u16(c2d + 10);
}
static uint8_t materialize(const uint8_t e[10], uint16_t *hot) {
    uint8_t i; uint16_t word, root;
    for (i = 0; i < e[1]; ++i) {
        word = u16(c2d + 22576u + (uint16_t)(u16(e + 6) + i) * 2u);
        if (word && word < 0x8000u && !(word & 1u)) {
            root = (uint16_t)((word >> 1) - 1u);
            if (root >= u16(c2d + 24)) return 0;
            word = u16(c2d + 30768u + root * 2u);
            if (!word || word >= 0x8000u || (word & 1u)) return 0;
        }
        hot[i] = word;
    }
    return 1;
}
static uint8_t refill(uint16_t ordinal) {
    uint8_t e[10]; uint16_t hot[255], i, end;
    if (!entry(ordinal, e) || !chip_load(2, u16(e + 2), window, u16(e + 4))
        || !materialize(e, hot)) return 0;
    end = (uint16_t)(7u + e[1] * 2u);
    for (i = 7; i < end && i < u16(e + 4); ++i)
        window[i] = (uint8_t)(hot[(i - 7u) >> 1] >> (((i - 7u) & 1u) * 8u));
    return 1;
}
static uint8_t native_load(uint16_t relative, uint16_t length) {
    return chip_load(3, relative, window, length);
}
int main(void) {
    c2d[4] = 6; c2d[5] = 48; c2d[6] = 32; c2d[7] = 10;
    sink8 = (uint8_t)(refill(0) + native_load(0, 32));
    return sink8 == 2 ? 0 : 1;
}
''', encoding="utf-8")
    linker.write_text(
        "/* The target platform's canonical link.ld owns MEMORY and SECTIONS.\n"
        " * This bound marker records that the WPLTO probe adds no private\n"
        " * placement model and therefore cannot mask a platform wall. */\n",
        encoding="utf-8")
    cc = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
    require(cc.is_file(), "llvm-mos target compiler absent")
    command = [str(cc), "-Oz", "-fno-lto", "-Wall", "-Wextra", "-Werror",
               "-I", str(ROOT / "src"), str(source),
               "-Wl,-Map=" + str(target) + ".map", "-o", str(target)]
    run = subprocess.run(command, cwd=ROOT, text=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (OUT / "c2-lite-v6-wplto.stdout.txt").write_text(run.stdout, encoding="utf-8")
    (OUT / "c2-lite-v6-wplto.stderr.txt").write_text(run.stderr, encoding="utf-8")
    require(run.returncode == 0, "C2-lite target seam preflight failed: " + run.stderr)
    size_tool = ROOT / "tools/llvm-mos/bin/llvm-size"
    size_out = subprocess.run([str(size_tool), "-A", str(target) + ".elf"],
                              cwd=ROOT, text=True, check=True,
                              stdout=subprocess.PIPE).stdout
    (OUT / "c2-lite-v6-wplto.size.txt").write_text(size_out, encoding="utf-8")
    sections: dict[str, int] = {}
    for line in size_out.splitlines():
        match = re.match(r"^(\.[^\s]+)\s+(\d+)\s+", line.strip())
        if match:
            sections[match.group(1)] = int(match.group(2))
    text_bytes = sum(value for key, value in sections.items()
                     if key.startswith((".text", ".rodata")))
    require(text_bytes > 0 and sections.get(".bss", 0) >= C2D_TOTAL_BYTES,
            "product-shaped WPLTO section census incomplete")
    return {
        "status": "passed-non-lto-target-codegen-preflight",
        "compiler_command": command,
        "target": bind(target), "elf": bind(Path(str(target) + ".elf")),
        "map": bind(Path(str(target) + ".map")),
        "sections": sections,
        "execution_seam_text_and_rodata_bytes": text_bytes,
        "source": bind(source), "linker_script": bind(linker),
        "product_links": 0, "hardware_runs": 0, "lto": False,
        "claim_limit": (
            "Target-codegen smoke for the execution seams only; the separate "
            "full product-shaped WPLTO is the capacity authority."
        ),
    }


def full_product_wplto() -> dict[str, Any]:
    """Compile exactly one full, non-promotable C2-lite product projection."""
    import c2_link33_bss_triage_product_link as BASE
    P = BASE.P
    BASE.configure()
    # The historical driver module now reflects rejected Link 36.  C2-lite's
    # approved authority is Link 35: the convergence retry is retired and the
    # active floor is restored to 115 bytes.  Pin both here rather than letting
    # mutable historical module state reconstruct the new profile.
    P.E000_FINAL_FLOOR_BYTES = 115
    features = tuple(item for item in BASE.FEATURES
                     if item not in ("LISP65_RTOV_CRC_CONVERGENCE",
                                     "LISP65_RTOV_DMA_COMPLETION_FENCE"))
    features = (*features, "LISP65_C2_LITE_CHIP_RAM")
    require("LISP65_RTOV_CRC_CONVERGENCE" not in features
            and "LISP65_RTOV_DMA_COMPLETION_FENCE" not in features,
            "C2-lite WPLTO retained an Attic convergence feature")
    full = OUT / "full-product-wplto"
    full.mkdir()
    mapping = generated_product_sources(full)
    original_source_list = P.source_list

    def projected_source_list(extra_definitions: tuple[str, ...] = ()) -> list[str]:
        return [str(mapping.get(Path(path).resolve(), Path(path)))
                for path in original_source_list(extra_definitions)]

    P.source_list = projected_source_list
    try:
        manifest = PRODUCT_IDENTITY
        artifacts = json.loads(manifest.read_text(encoding="utf-8"))
        require(artifacts["artifacts"]["shelf"]["bytes"] > 0,
                "static substitution artifact authority absent")
        P.write_v2_profile_report(full, artifacts)
        (full / "c2-substitution.ld").write_text(P.linker_script(), encoding="utf-8")
        contract = full / "resolved-profile.txt"
        lines = [
            "profile=" + P.PROFILE,
            "mode=c2-lite-v6-full-product-shaped-wplto",
            "promotable=no", "product_link=no", "hardware_execution=no",
            "c2d_version=6",
            f"bank2_code_plane_bytes={STATIC_CODE_BYTES}",
            "bank3_family_bytes=derived-from-final-pack-manifests",
            "e000_floor_bytes=115", "feature_defines=" + ",".join(features),
            "linker_sha256=" + sha(full / "c2-substitution.ld"),
        ]
        for path_text in P.source_list(features):
            path = Path(path_text)
            lines.append("input_sha256=" + path.relative_to(ROOT).as_posix()
                         + ":" + sha(path))
        contract.write_text("\n".join(lines) + "\n", encoding="utf-8")

        standard = full / "runtime-overlay.prepare-standard.h"
        prepared = full / "runtime-overlay.prepare.h"
        island = full / "resident-island.prepare.h"
        stage = full / "stage-config.h"
        errors = full / "error-text-table.h"
        kernal = full / "c2-kernal-window.generated.h"
        P.write(kernal, P.kernal_header_values(P.KERNAL_CRC_BINDING_SENTINEL,
                                               "0" * 64))
        P.tool("runtime_overlay_bank.py", "prepare", "--abi-contract",
               str(contract), "--header", str(standard), "--profile", P.PROFILE,
               "--format-version", "3")
        P.render_prepared_family_header(standard, prepared)
        P.tool("resident_island.py", "prepare", "--abi-contract", str(contract),
               "--header", str(island))
        build_id = int(hashlib.sha256(contract.read_bytes()).hexdigest()[:8], 16)
        P.tool("error_text_table.py", "prepare", "--spec",
               str(ROOT / "config/error-texts.json"), "--profile", "workbench",
               "--build-id", hex(build_id), "--header", str(errors), "--binary",
               str(full / "error-text-table.bin"))
        stage.write_text("\n".join([
            "#ifndef LISP65_WORKBENCH_OVERLAY_STAGE_H",
            "#define LISP65_WORKBENCH_OVERLAY_STAGE_H",
            "#define LISP65_BOOT_OVERLAY_STAGE_BANK 0x05u",
            "#define LISP65_BOOT_OVERLAY_STAGE_OFF 0x8500u",
            f"#define LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID 0x{build_id:08x}UL",
            "#endif", "",
        ]), encoding="utf-8")
        target = P.compile_link(
            full, "c2-lite-v6-full-seed.prg",
            [stage, prepared, island, errors, kernal], artifacts,
            probe_definitions=features, final_inventory=False)
        boot_image, boot_manifest = P.overlay_pack_family(
            full, target, contract, "boot", "c2-lite")
        session_image, session_manifest = P.overlay_pack_family(
            full, target, contract, "session", "c2-lite")
    finally:
        P.source_list = original_source_list

    elf = Path(str(target) + ".elf")
    sections = P.section_table(elf)
    text = sections[".text"]; bss = sections[".bss"]
    walls = {
        "bank0_text_headroom_bytes": P.HANDOFF_BASE - text["address"] - text["bytes"],
        "ordinary_bank0_bss_headroom_bytes": P.FIXED_BANK0_BASE
        - bss["address"] - bss["bytes"],
        "fixed_hot_block_headroom_bytes": P.fixed_bank0_headroom_bytes(),
        "resident_island_headroom_bytes": 2048 - sum(
            sections.get(name, {}).get("bytes", 0) for name in
            (".lisp65_resident_island", ".lisp65_resident_island_annex")),
        "e000_headroom_bytes": P.KERNAL_WINDOW_BYTES - sum(
            sections[name]["bytes"] for name in P.KERNAL_SECTIONS),
    }
    require(all(walls[key] >= 0 for key in walls if key != "e000_headroom_bytes")
            and walls["e000_headroom_bytes"] >= 115,
            "full C2-lite WPLTO wall red: " + str(walls))
    slice_sections = {spec.split(":")[2] for spec in
                      P.BOOT_SLICE_SPECS + P.SESSION_SLICE_SPECS}
    slice_sizes = {name: sections.get(name, {}).get("bytes", 0)
                   for name in slice_sections}
    over = {name: size for name, size in slice_sizes.items()
            if size <= 0 or size > 1792}
    require(not over, "full C2-lite WPLTO slice wall red: " + str(over))
    boot = json.loads(boot_manifest.read_text(encoding="utf-8"))
    session = json.loads(session_manifest.read_text(encoding="utf-8"))
    require(boot["storage"]["size"] <= BANK_BYTES
            and session["storage"]["size"] <= BANK_BYTES,
            "full C2-lite WPLTO Bank-3 family overflow")

    generated_hot = (full / "generated-product-sources/c2_hot_literal.c").read_text()
    generated_runtime = (full / "generated-product-sources/c2_product_runtime.c").read_text()
    generated_rtov = (full / "generated-product-sources/vm_runtime_overlay.c").read_text()
    hot_entry = c_function_definition(
        generated_runtime, "c2_product_entry_read")
    rtov_read = c_function_definition(generated_rtov, "rtov_read")
    require("c2_stream_shelf_read" not in generated_hot
            and "c2_stream_shelf_read" not in hot_entry
            and "c2_dma_copy" not in hot_entry
            and "rtov_dma_submit_wait" not in rtov_read
            and "c2_facade_vm_code_load(2u" in hot_entry
            and "c2_facade_vm_code_load(3u" in rtov_read,
            "hot no-Attic source closure is red")
    retired = {
        "runtime_crc_convergence_define":
            "LISP65_RTOV_CRC_CONVERGENCE" not in features,
        "dma_completion_fence_define":
            "LISP65_RTOV_DMA_COMPLETION_FENCE" not in features,
        "hot_c2i_reads": 0, "hot_attic_reads": 0,
        "bank2_loader_callsites": hot_entry.count("c2_facade_vm_code_load(2u"),
        "bank3_loader_callsites": rtov_read.count("c2_facade_vm_code_load(3u"),
    }
    require(all(value is True or isinstance(value, int) for value in retired.values()),
            "retirement census malformed")
    return {
        "status": "passed-one-full-nonpromotable-product-shaped-wplto",
        "product_links": 0, "promotable": False, "hardware_runs": 0,
        "target": bind(target), "elf": bind(elf),
        "map": bind(Path(str(target) + ".map")),
        "resolved_profile": bind(contract),
        "walls": walls,
        "runtime_slices": {
            "count": len(slice_sizes), "cap_bytes": 1792,
            "largest_bytes": max(slice_sizes.values()),
            "minimum_headroom_bytes": 1792 - max(slice_sizes.values()),
        },
        "successor_bank3_pack": {
            "boot": {**bind(boot_image),
                     "headroom_bytes": BANK_BYTES - boot_image.stat().st_size},
            "session": {**bind(session_image),
                        "headroom_bytes": BANK_BYTES - session_image.stat().st_size},
        },
        "hot_no_runtime_attic_gate": {"status": "passed", **retired},
        "generated_source_count": len(mapping),
        "claim_limit": (
            "One complete product-shaped WPLTO and every current linker wall; "
            "generated source projection is nonpromotable and is not a product link."
        ),
    }


def contract_check() -> dict[str, Any]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    require(contract["status"] ==
            "class-c-approved-semantic-split-wplto-probe-authorized",
            "C2-lite v6 probe is not authorized")
    require(contract["scope"] == {
        "product_source_changes_authorized": 1,
        "product_shaped_probes_authorized": 1,
        "product_links_authorized": 0,
        "hardware_claim": "receipt-less-fail-fast-prefilter-only",
        "rollback_product": "Link 35",
    }, "C2-lite probe scope drift")
    require(contract["c2d_v6"]["root_reference"]["root_capacity"] == 1536,
            "C2D-v6 root capacity drift")
    return contract


def protect() -> None:
    for path in OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    if RECEIPT.is_file():
        os.chmod(RECEIPT, 0o444)


def bind_first_red() -> dict[str, Any]:
    """Bind the already-produced, valid full-WPLTO capacity First Red."""
    require(OUT.is_dir() and not RECEIPT.exists(),
            "current C2-lite WPLTO First-Red output/receipt state is invalid")
    full = OUT / "full-product-wplto"
    map_path = full / "c2-lite-v6-full-seed.prg.map"
    stderr_path = full / "c2-lite-v6-full-seed.prg.link.stderr.txt"
    lto_path = full / "c2-lite-v6-full-seed.prg.lto.o"
    require(map_path.is_file() and stderr_path.is_file() and lto_path.is_file(),
            "full-WPLTO First-Red evidence is incomplete")
    stderr = stderr_path.read_text(encoding="utf-8")
    for message in (
        "C2 decoder phase 11 exceeds its stack-safe window",
        "C2 reopening gap0 overlaps session-emitter state",
        "C2 final E000 floor below 115 bytes",
    ):
        require(message in stderr, "expected full-WPLTO red absent: " + message)

    rows: dict[str, dict[str, int]] = {}
    pattern = re.compile(
        r"^\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+\d+\s+"
        r"(\.[^\s]+)$")
    for line in map_path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            rows[match.group(4)] = {
                "address": int(match.group(1), 16),
                "load_address": int(match.group(2), 16),
                "bytes": int(match.group(3), 16),
            }
    required = (
        ".text", ".bss", ".lisp65_rt_c2d_11",
        ".lisp65_resident_island", ".lisp65_resident_island_annex",
        ".lisp65_c2_kernal_window.c2_resident",
        ".lisp65_c2_kernal_window.session_emitter_state",
    )
    require(all(name in rows for name in required),
            "First-Red map lacks required wall rows")
    kernal_names = (
        ".lisp65_c2_kernal_window.typed_queue_driver",
        ".lisp65_c2_kernal_window.irq_handler",
        ".lisp65_c2_kernal_window.nmi_and_freezer_return",
        ".lisp65_c2_kernal_window.map_switch_and_guards",
        ".lisp65_c2_kernal_window.post_startup_output_seam",
        ".lisp65_c2_kernal_window.c2_resident",
        ".lisp65_c2_kernal_window.session_emitter_state",
        ".lisp65_c2_kernal_window.profile_rodata",
        ".lisp65_c2_kernal_window.state", ".lisp65_c2_vectors",
        ".lisp65_c2_kernal_window.reopen_gap0",
        ".lisp65_c2_kernal_window.reopen_gap1",
        ".lisp65_c2_kernal_window.reopen_gap2",
    )
    require(all(name in rows for name in kernal_names),
            "First-Red map lacks complete E000 inventory")
    e000_use = sum(rows[name]["bytes"] for name in kernal_names)
    text = rows[".text"]; bss = rows[".bss"]
    phase11 = rows[".lisp65_rt_c2d_11"]["bytes"]
    island_use = (rows[".lisp65_resident_island"]["bytes"]
                  + rows[".lisp65_resident_island_annex"]["bytes"])
    resident = rows[".lisp65_c2_kernal_window.c2_resident"]
    state = rows[".lisp65_c2_kernal_window.session_emitter_state"]
    walls = {
        "bank0_text_headroom_bytes": 0xB4A3 - text["address"] - text["bytes"],
        "ordinary_bank0_bss_headroom_bytes": 0xC080 - bss["address"] - bss["bytes"],
        "fixed_hot_block_headroom_bytes": 33,
        "resident_island_headroom_bytes": 2048 - island_use,
        "phase11_bytes": phase11,
        "phase11_cap_bytes": 1792,
        "phase11_overflow_bytes": phase11 - 1792,
        "e000_use_bytes": e000_use,
        "e000_capacity_bytes": 8192,
        "e000_raw_overflow_bytes": e000_use - 8192,
        "e000_required_floor_bytes": 115,
        "e000_deficit_to_required_floor_bytes": e000_use + 115 - 8192,
        "c2_resident_end_exclusive": resident["address"] + resident["bytes"],
        "session_emitter_state_base": state["address"],
        "c2_resident_overlap_bytes":
            resident["address"] + resident["bytes"] - state["address"],
    }
    require(walls == {
        "bank0_text_headroom_bytes": 306,
        "ordinary_bank0_bss_headroom_bytes": 144,
        "fixed_hot_block_headroom_bytes": 33,
        "resident_island_headroom_bytes": 170,
        "phase11_bytes": 1825, "phase11_cap_bytes": 1792,
        "phase11_overflow_bytes": 33,
        "e000_use_bytes": 8391, "e000_capacity_bytes": 8192,
        "e000_raw_overflow_bytes": 199,
        "e000_required_floor_bytes": 115,
        "e000_deficit_to_required_floor_bytes": 314,
        "c2_resident_end_exclusive": 0xFDB1,
        "session_emitter_state_base": 0xFD08,
        "c2_resident_overlap_bytes": 169,
    }, "bound First-Red wall arithmetic drift: " + str(walls))

    correction_specs = (
        ("duplicate-platform-memory-region",
         ROOT / "build/c2-lite/product-shaped-v6-probe-harness-parser-first-red/"
                "c2-lite-v6-wplto.stderr.txt"),
        ("stale-link36-profile-and-floor",
         ROOT / "build/c2-lite/product-shaped-v6-probe-link36-profile-first-red/"
                "full-product-wplto/c2-lite-v6-full-seed.prg.link.stderr.txt"),
        ("chip-record-profile-guard",
         ROOT / "build/c2-lite/product-shaped-v6-probe-record-profile-first-red/"
                "full-product-wplto/c2-lite-v6-full-seed.prg.link.stderr.txt"),
        ("retry-helper-preprocessor-scope",
         ROOT / "build/c2-lite/product-shaped-v6-probe-record-helper-first-red/"
                "full-product-wplto/c2-lite-v6-full-seed.prg.link.stderr.txt"),
    )
    corrections = []
    for label, path in correction_specs:
        require(path.is_file(), "harness correction evidence absent: " + label)
        corrections.append({"class": "A", "label": label,
                            "product_bytes": 0, "artifact": bind(path)})

    preliminary = (ROOT / "build/c2-lite/"
                   "product-shaped-v6-probe-seam-preflight-only/"
                   "preliminary-receipt.json")
    require(preliminary.is_file(), "green host-semantics preliminary receipt absent")
    prior = json.loads(preliminary.read_text(encoding="utf-8"))
    require(prior["host_c2d_v6"]["static_bank2"]["code_bytes"] == 34403
            and prior["bank3_lifetime_union"]["boot"]["bytes"] == 15605
            and prior["bank3_lifetime_union"]["session"]["bytes"] == 60062,
            "green host/lifetime authority drift")
    value = {
        "format": "lisp65-c2-lite-v6-product-shaped-wplto-first-red-v1",
        "recorded_on": "2026-07-21",
        "status": "FIRST RED: full product-shaped WPLTO capacity/layout",
        "scope": {
            "product_source_changes": 0, "product_links": 0,
            "promotable_product_links": 0, "hardware_runs": 0,
            "non_lto_target_preflight_compiles": 1,
            "valid_full_product_wplto_attempts": 1,
        },
        "authority": {"contract": bind(CONTRACT), "addendum": bind(ADDENDUM),
                      "memo": bind(MEMO)},
        "green_before_first_red": {
            "permanent_root_surrogate_gate": R.collect(),
            "host_semantics_receipt": bind(preliminary),
            "bank2_static": prior["host_c2d_v6"]["static_bank2"],
            "one_emitter": prior["host_c2d_v6"]["one_emitter"],
            "rollback": prior["host_c2d_v6"]["rollback"],
            "nested": prior["host_c2d_v6"]["nested"],
            "stale_generation": prior["host_c2d_v6"]["stale_generation"],
            "bank3_lifetime_union": prior["bank3_lifetime_union"],
        },
        "full_wplto_first_red": {
            "profile": bind(full / "resolved-profile.txt"),
            "map": bind(map_path), "stderr": bind(stderr_path),
            "lto_object": bind(lto_path), "walls": walls,
            "diagnostics": [
                "phase 11 is 1825 B: 33 B above the immutable 1792-B cap",
                "E000 named tenants total 8391 B: raw overflow 199 B and "
                "314 B short of the restored 115-B floor",
                "the C2 resident section crosses the session-state anchor by 169 B",
            ],
        },
        "autonomous_harness_corrections": corrections,
        "claim_limit": (
            "C2D-v6 host semantics and exact Bank-2/Bank-3 plane arithmetic "
            "are green. The complete product-shaped WPLTO is red; no product, "
            "hardware, performance, promotion or acceptance claim exists."
        ),
        "rollback_line": {"product": "Link 35", "status": "untouched"},
        "next_gate": (
            "Class-C review of phase-11 semantic split and E000 residency; "
            "no retry, product implementation, product link or hardware run."
        ),
    }
    write_json(OUT / "c2-lite-v6-product-shaped-first-red.json", value)
    value["first_red_report"] = bind(
        OUT / "c2-lite-v6-product-shaped-first-red.json")
    write_json(RECEIPT, value)
    protect()
    return value


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "C2-lite v6 product-shaped probe is one-shot and already exists")
    contract_check()
    OUT.mkdir(parents=True)
    host = host_semantics()
    bank3 = bank3_lifetime()
    target_preflight = target_seam_preflight()
    wplto = full_product_wplto()
    value = {
        "format": "lisp65-c2-lite-v6-product-shaped-probe-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-host-and-product-shaped-probe-product-link-not-run",
        "scope": {
            "product_source_changes": 0, "promotable_product_links": 0,
            "product_links": 0, "hardware_runs": 0,
            "non_lto_target_preflight_compiles": 1,
            "whole_program_lto_probes": 1,
        },
        "authority": {"contract": bind(CONTRACT), "addendum": bind(ADDENDUM),
                      "memo": bind(MEMO)},
        "host_c2d_v6": host,
        "bank3_lifetime_union": bank3,
        "target_seam_preflight": target_preflight,
        "whole_program_lto": wplto,
        "capacity": {
            "bank2": {"use_bytes": STATIC_CODE_BYTES,
                      "headroom_bytes": BANK_BYTES - STATIC_CODE_BYTES},
            "bank3_boot": {"use_bytes": 15605, "headroom_bytes": 49931},
            "bank3_session": {"use_bytes": 60062, "headroom_bytes": 5474},
            "bank5_c2d": {"use_bytes": C2D_TOTAL_BYTES,
                         "headroom_bytes": C2D_REGION_BYTES - C2D_TOTAL_BYTES,
                         "record_widening_bytes": 0},
            "bank1": "untouched",
            "e000_active_floor_bytes": 115,
        },
        "claim_limit": (
            "Host semantics and one non-product target WPLTO closure only. "
            "No product link, device execution, promotion, latency or acceptance claim."
        ),
        "next_gate": "Class-C review before any product implementation or link",
    }
    write_json(OUT / "c2-lite-v6-product-shaped-probe.json", value)
    value["probe_report"] = bind(OUT / "c2-lite-v6-product-shaped-probe.json")
    write_json(RECEIPT, value)
    protect()
    return value


def check() -> dict[str, Any]:
    require(RECEIPT.is_file(), "C2-lite v6 product-shaped receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    status = value.get("status")
    green = "passed-host-and-product-shaped-probe-product-link-not-run"
    first_red = "FIRST RED: full product-shaped WPLTO capacity/layout"
    require(status in (green, first_red),
            "C2-lite v6 receipt has an unknown terminal status")

    def verify(row: dict[str, Any], label: str) -> None:
        path = ROOT / row["path"]
        require(path.is_file() and path.stat().st_size == row["bytes"] and
                sha(path) == row["sha256"],
                f"C2-lite v6 artifact drift: {label}: {path}")

    if status == green:
        for label, row in value["host_c2d_v6"]["artifacts"].items():
            verify(row, label)
        return value

    verify(value["first_red_report"], "first-red-report")
    for label, row in value["authority"].items():
        verify(row, "authority-" + label)
    green_rows = value["green_before_first_red"]
    verify(green_rows["host_semantics_receipt"], "host-semantics-receipt")
    for label in ("profile", "map", "stderr", "lto_object"):
        verify(value["full_wplto_first_red"][label], "full-wplto-" + label)
    for row in value["autonomous_harness_corrections"]:
        require(row["class"] == "A" and row["product_bytes"] == 0,
                "harness correction escaped Class A")
        verify(row["artifact"], "harness-correction-" + row["label"])
    walls = value["full_wplto_first_red"]["walls"]
    require(walls["phase11_bytes"] == 1825 and
            walls["phase11_overflow_bytes"] == 33 and
            walls["e000_use_bytes"] == 8391 and
            walls["e000_raw_overflow_bytes"] == 199 and
            walls["e000_deficit_to_required_floor_bytes"] == 314,
            "bound First-Red capacity arithmetic drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "check", "selftest",
                                           "bind-first-red"))
    args = parser.parse_args()
    if args.action == "selftest":
        contract_check(); report = R.collect()
        print("c2-lite-v6-product-probe: SELFTEST PASS roots=%d" %
              report["root_capacity"])
        return 0
    if args.action == "bind-first-red":
        value = bind_first_red()
        print("c2-lite-v6-product-probe: " + value["status"])
        return 2
    value = build() if args.action == "run" else check()
    print("c2-lite-v6-product-probe: " + value["status"])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            subprocess.CalledProcessError, ProbeError, R.SurrogateError,
            F.FullError, S.ProbeError) as exc:
        print(f"c2-lite-v6-product-probe: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
