#!/usr/bin/env python3
"""Build the exact static artifacts consumed by the first C2 product link."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_full_emission as F  # noqa: E402
import c2_session_extension_probe as S  # noqa: E402


BUILD = ROOT / "build/c2.2/substitution"
SPECS = (
    ("stdlib-p0", "stdlib", BUILD / "stdlib-p0.manifest.json"),
    ("ide", "ide", ROOT / "build/bytecode/dialect-v2/libs/ide.manifest.json"),
    ("idex", "idex", ROOT / "build/bytecode/dialect-v2/libs/idex.manifest.json"),
    ("m65d", "m65d", ROOT / "build/bytecode/dialect-v2/libs/m65d.manifest.json"),
    ("buffer", "buffer", ROOT / "build/bytecode/dialect-v2/libs/buffer.manifest.json"),
    ("lcc", "lcc", BUILD / "lcc.manifest.json"),
)


class SubstitutionArtifactError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SubstitutionArtifactError(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bind(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(data),
            "sha256": sha(data)}


def build() -> dict[str, object]:
    F.contract_check()
    images = [F.emit_image(*row) for row in SPECS]
    require(len(images) == 6, "C2 product image count drift")
    entries = sum(len(image.manifest["entries"]) for image in images)
    resolutions = sum(len(image.descriptors) for image in images)
    roots = sum(desc.kind in S.ROOT_KINDS for image in images
                for desc in image.descriptors)
    require(entries <= S.C2D_ENTRY_CAPACITY, "C2 entry capacity exhausted")
    require(resolutions <= S.C2D_RESOLUTION_CAPACITY,
            "C2 resolution capacity exhausted")
    require(roots <= S.C2D_ROOT_CAPACITY, "C2 root capacity exhausted")

    shelf, rows, catalog_crc = F.build_shelf(images)
    F.verify_shelf(shelf, images, F.declared_exports(images))
    build_id = struct.unpack_from("<I", shelf, 22)[0]
    require(build_id != 0, "C2 product build identity is zero")

    plane = bytearray(S.C2D_TOTAL_BYTES)
    entry_base = resolution_base = root_base = 0
    for slot, (image, row) in enumerate(zip(images, rows)):
        image_roots = sum(desc.kind in S.ROOT_KINDS for desc in image.descriptors)
        record = S.image_record(
            source_kind=0, source_slot=slot, generation=S.SESSION_GENERATION,
            directory_base=entry_base, entries=len(image.manifest["entries"]),
            resolution_base=resolution_base, resolutions=len(image.descriptors),
            root_base=root_base, roots=image_roots,
            code_offset=row["code_offset"], code_length=row["code_length"],
            metadata_offset=row["metadata_offset"],
            metadata_length=row["metadata_length"],
            combined_crc=zlib.crc32(image.code + image.metadata) & 0xffffffff,
        )
        at = S.C2D_IMAGES_OFFSET + slot * S.C2D_IMAGE_BYTES
        plane[at:at + S.C2D_IMAGE_BYTES] = record
        for ordinal, entry in enumerate(image.manifest["entries"]):
            item = S.entry_record(
                image_slot=slot, ordinal=ordinal,
                code_length=int(entry["length"]),
                resolution_base=resolution_base + image.entry_first[ordinal],
                generation=S.SESSION_GENERATION,
            )
            pos = S.C2D_ENTRIES_OFFSET + (entry_base + ordinal) * S.C2D_ENTRY_BYTES
            plane[pos:pos + S.C2D_ENTRY_BYTES] = item
        entry_base += len(image.manifest["entries"])
        resolution_base += len(image.descriptors)
        root_base += image_roots
    require((entry_base, resolution_base, root_base) ==
            (entries, resolutions, roots), "C2 static range closure")
    S.encode_header(
        plane, generation=S.SESSION_GENERATION, image_count=len(images),
        entry_count=entries, resolution_count=resolutions, root_count=roots,
        immutable_images=len(images), catalog_crc=catalog_crc, build_id=build_id,
    )
    require(all(byte == 0 for byte in plane[S.C2D_RESOLUTIONS_OFFSET:]),
            "initial C2 mutable values must be decoder-owned zeros")

    BUILD.mkdir(parents=True, exist_ok=True)
    shelf_path = BUILD / "product-shelf-v4-direct.bin"
    c2d_path = BUILD / "initial.c2d-v3.bin"
    shelf_path.write_bytes(shelf); c2d_path.write_bytes(plane)
    for image in images:
        (BUILD / f"{image.key}.code.bin").write_bytes(image.code)
        (BUILD / f"{image.key}.c2i.bin").write_bytes(image.metadata)
    report: dict[str, object] = {
        "format": "lisp65-c2-product-substitution-artifacts-v1",
        "status": "static-c2-artifacts-emitted-product-link-not-run",
        "product_build_id_u32": build_id,
        "product_build_id_hex": f"0x{build_id:08x}",
        "images": len(images), "entries": entries,
        "resolutions": resolutions, "roots": roots,
        "capacity_headroom": {
            "images": S.C2D_IMAGE_CAPACITY - len(images),
            "entries": S.C2D_ENTRY_CAPACITY - entries,
            "resolutions": S.C2D_RESOLUTION_CAPACITY - resolutions,
            "roots": S.C2D_ROOT_CAPACITY - roots,
            "bank5_plane_bytes": S.C2D_REGION_BYTES - S.C2D_TOTAL_BYTES,
        },
        "artifacts": {"shelf": bind(shelf_path), "initial_c2d": bind(c2d_path)},
        "manifests": [bind(path) for _key, _name, path in SPECS],
        "one_truth": {
            "static_format": "C2I-v2/L65S-v4-direct",
            "session_format": "C2I-v2/L65S-v4-direct",
            "legacy_emitter_artifacts": [],
        },
    }
    receipt = BUILD / "substitution-artifacts.json"
    receipt.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    try:
        value = build()
        data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
        receipt = BUILD / "substitution-artifacts.json"
        if args.action == "check":
            require(receipt.read_bytes() == data, "substitution artifact receipt drift")
        if args.action == "selftest":
            again = build()
            require(value == again, "substitution artifact emission is not deterministic")
        print("c2-substitution-artifacts: PASS images=%d entries=%d resolutions=%d roots=%d build-id=%s" % (
            value["images"], value["entries"], value["resolutions"], value["roots"],
            value["product_build_id_hex"]))
        return 0
    except (OSError, ValueError, F.FullError, S.ProbeError,
            SubstitutionArtifactError) as exc:
        print(f"c2-substitution-artifacts: FAIL: {exc}", file=sys.stderr); return 1


if __name__ == "__main__":
    raise SystemExit(main())
