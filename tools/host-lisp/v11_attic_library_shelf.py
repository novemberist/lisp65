#!/usr/bin/env python3
"""Build and verify the compact 1.1 Attic library shelf."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import struct
import tarfile
import tempfile
import zlib
import re


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/v11-attic-library-shelf.json"
HEADER = struct.Struct("<4sBBBBHHIIIII")
RECORD = struct.Struct("<8sHHI16s")
MAGIC = b"L65S"
VERSION = 3
HEADER_BYTES = 32
RECORD_BYTES = 32
PAYLOAD_OFF = 192


class ShelfError(RuntimeError):
    pass


SHELF_ERA = "ca8666ab2ce4696efe7463583e47daddc7bb7cec"  # v1.1.0


def shelf_era_archive(commit: str = SHELF_ERA) -> bytes:
    if commit != SHELF_ERA:
        raise ShelfError("retired shelf era drift")
    return subprocess.check_output(["git", "archive", commit], cwd=ROOT)


def validate_shelf_archive(raw: bytes) -> None:
    expected = {}
    for row in subprocess.check_output(["git", "ls-tree", "-rz", SHELF_ERA], cwd=ROOT).split(b"\0"):
        if not row:
            continue
        meta, name = row.split(b"\t", 1)
        mode, kind, oid = meta.split()
        if kind != b"blob" or mode not in (b"100644", b"100755"):
            raise ShelfError("non-file shelf-era input")
        expected[name.decode()] = oid.decode()
    actual = {}
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        for member in archive:
            if member.isdir():
                continue
            if not member.isfile() or member.name in actual:
                raise ShelfError("invalid shelf-era member")
            data = archive.extractfile(member).read()
            actual[member.name] = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    if actual != expected:
        raise ShelfError("shelf-era source population/bytes drift")


def require_era_path(path: Path, folder: Path) -> None:
    if not path.resolve().is_relative_to(folder.resolve()):
        raise ShelfError("old live path outside shelf-era owner")


def era_check(out: Path, manifest_out: Path) -> None:
    raw = shelf_era_archive()
    validate_shelf_archive(raw)
    try:
        shelf_era_archive("HEAD")
    except ShelfError:
        pass
    else:
        raise ShelfError("live-era mutation survived")
    # The contract itself is byte-identical across eras. Do not claim its
    # substitution is a falling mutation; test changed/missing bytes here,
    # and the actual old live path against the archive owner after the build.
    for replacement in ((ROOT / "config/v11-attic-library-shelf.json").read_bytes() + b"\n", None):
        changed = io.BytesIO()
        with tarfile.open(fileobj=io.BytesIO(raw)) as source, tarfile.open(fileobj=changed, mode="w") as target:
            for member in source:
                data = source.extractfile(member).read() if member.isfile() else None
                if member.name == "config/v11-attic-library-shelf.json":
                    if replacement is None:
                        continue
                    data = replacement
                    member.size = len(data)
                target.addfile(member, io.BytesIO(data) if data is not None else None)
        try:
            validate_shelf_archive(changed.getvalue())
        except ShelfError:
            pass
        else:
            raise ShelfError("old-path/missing source mutation survived")
    with tempfile.TemporaryDirectory(prefix="lisp65-attic-shelf-v110-") as directory:
        folder = Path(directory)
        with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
            archive.extractall(folder, filter="data")
        env = {k: v for k, v in os.environ.items() if k not in ("MAKEFLAGS", "MFLAGS", "MAKEOVERRIDES")}
        subprocess.run(["make", "attic-library-shelf-check"], cwd=folder, env=env, check=True)
        image = folder / "build/bytecode/dialect-v2/shelf/library-shelf.bin"
        historical_manifest = folder / "build/bytecode/dialect-v2/shelf/library-shelf-manifest.json"
        data = image.read_bytes()
        manifest = json.loads(historical_manifest.read_text())
        for item in load_json(folder / "config/v11-attic-library-shelf.json")["containers"]:
            artifact_path = item["manifest"]
            require_era_path(folder / artifact_path, folder)
            container = load_json(folder / artifact_path)["external_image"]["path"]
            require_era_path(folder / container, folder)
            try:
                require_era_path(ROOT / artifact_path, folder)
            except ShelfError:
                pass
            else:
                raise ShelfError("live old-path artifact owner mutation survived")
        manifest["era_binding"] = {"commit": SHELF_ERA, "source_archive_sha256": sha_bytes(raw),
                                   "historical_manifest_sha256": sha_file(historical_manifest),
                                   "live_product_claim": False, "mutations": 8}
        out.parent.mkdir(parents=True, exist_ok=True)
        manifest_out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        manifest_out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"attic-shelf-era: PASS bytes={len(data)} host-only mutations=8")


def verify_scratch_binding() -> None:
    source = (ROOT / "src/attic_library_shelf.c").read_text(encoding="utf-8")
    header = (ROOT / "src/mem.h").read_text(encoding="utf-8")
    legacy = "L65S_DISK_SCRATCH_PHYSICAL"
    if legacy in source or legacy in (ROOT / "src/attic_library_shelf.h").read_text(encoding="utf-8"):
        raise ShelfError("Attic shelf retains a private disk-scratch address")
    if "LISP65_EXT_DISK_FILE_PHYSICAL" not in source:
        raise ShelfError("Attic shelf does not consume the shared disk-scratch layout")
    required = ("EXT_BANK", "DISK_EXT_BASE", "LISP65_EXT_DISK_FILE_OFFSET")
    if "#define LISP65_EXT_DISK_FILE_PHYSICAL" not in header or any(
        name not in header for name in required
    ):
        raise ShelfError("shared disk-scratch physical-address derivation is incomplete")
    if re.search(r"0x0*4[0-9a-fA-F]{4}", source):
        raise ShelfError("Attic shelf contains a mirrored Bank-4 physical literal")


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ShelfError(f"JSON object required: {path}")
    return value


def _container(contract_row: dict) -> dict:
    manifest_path = ROOT / contract_row["manifest"]
    manifest = load_json(manifest_path)
    image = manifest.get("external_image", {})
    container_path = ROOT / image.get("path", "")
    data = container_path.read_bytes()
    expected = image.get("sha256")
    actual = sha_bytes(data)
    if actual != expected:
        raise ShelfError(f"container SHA drift: {contract_row['key']}")
    key = contract_row["key"]
    encoded = key.encode("ascii")
    if not encoded or len(encoded) > 7:
        raise ShelfError(f"invalid device key: {key!r}")
    if len(data) > 0xFFFF:
        raise ShelfError(f"container exceeds u16 source contract: {key}")
    return {
        "key": key,
        "role": contract_row["role"],
        "manifest": relative(manifest_path),
        "manifest_sha256": sha_file(manifest_path),
        "container": relative(container_path),
        "container_sha256": actual,
        "bytes": len(data),
        "data": data,
    }


def build(out: Path, manifest_out: Path) -> dict:
    contract = load_json(CONTRACT)
    rows = [_container(row) for row in contract["containers"]]
    keys = ["ide", "idex", "m65d", "buffer", "lcc"]
    if len(rows) != 5 or [row["key"] for row in rows] != keys:
        raise ShelfError("device catalog must be the exact ordered five-library set")
    offset = PAYLOAD_OFF
    records = bytearray()
    payload = bytearray()
    public_rows = []
    for row in rows:
        pad = (-offset) & 1
        payload.extend(b"\0" * pad)
        offset += pad
        record_offset = offset
        key = row["key"].encode("ascii") + b"\0"
        records.extend(RECORD.pack(
            key.ljust(8, b"\0"), record_offset, row["bytes"],
            zlib.crc32(row["data"]) & 0xFFFFFFFF,
            bytes.fromhex(row["container_sha256"])[:16],
        ))
        payload.extend(row["data"])
        offset += row["bytes"]
        public_rows.append({
            key: value for key, value in row.items() if key != "data"
        } | {
            "attic_offset": record_offset,
            "attic_address": contract["attic_address"] + record_offset,
            "crc32": f"{zlib.crc32(row['data']) & 0xFFFFFFFF:08x}",
        })
    if offset > 0xFFFF:
        raise ShelfError("complete shelf exceeds u16 catalog address space")
    catalog_crc = zlib.crc32(records) & 0xFFFFFFFF
    identity = json.dumps(public_rows, sort_keys=True, separators=(",", ":")).encode()
    build_id = int.from_bytes(hashlib.sha256(identity).digest()[:4], "little")
    header = HEADER.pack(
        MAGIC, VERSION, HEADER_BYTES, RECORD_BYTES, len(rows), HEADER_BYTES,
        PAYLOAD_OFF, offset, len(payload), catalog_crc, build_id, 0,
    )
    shelf = header + bytes(records) + bytes(payload)
    if len(shelf) != offset:
        raise ShelfError("shelf layout did not close")
    out.parent.mkdir(parents=True, exist_ok=True)
    manifest_out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(shelf)
    report = {
        "format": "lisp65-v11-attic-library-shelf-manifest-v1",
        "contract": relative(CONTRACT),
        "contract_sha256": sha_file(CONTRACT),
        "product_baseline_sha256": contract["product_baseline_sha256"],
        "attic_address": contract["attic_address"],
        "shelf": relative(out),
        "shelf_bytes": len(shelf),
        "shelf_sha256": sha_bytes(shelf),
        "catalog_crc32": f"{catalog_crc:08x}",
        "build_id": f"{build_id:08x}",
        "containers": public_rows,
        "integrity_claim": {
            "device": contract["device_integrity"],
            "host": contract["host_integrity"],
        },
        "fallback": contract["fallback"],
    }
    manifest_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verify(out, manifest_out)
    return report


def verify(shelf_path: Path, manifest_path: Path) -> dict:
    data = shelf_path.read_bytes()
    report = load_json(manifest_path)
    if len(data) < PAYLOAD_OFF or sha_bytes(data) != report.get("shelf_sha256"):
        raise ShelfError("shelf SHA mismatch")
    fields = HEADER.unpack_from(data)
    magic, version, hbytes, rbytes, count, roff, poff, total, payload_bytes, crc, build_id, reserved = fields
    if (magic, version, hbytes, rbytes, count, roff, poff, total, reserved) != (
        MAGIC, VERSION, HEADER_BYTES, RECORD_BYTES, 5, HEADER_BYTES,
        PAYLOAD_OFF, len(data), 0,
    ):
        raise ShelfError("shelf header contract mismatch")
    if payload_bytes != len(data) - PAYLOAD_OFF:
        raise ShelfError("payload length mismatch")
    catalog = data[roff:roff + count * rbytes]
    if zlib.crc32(catalog) & 0xFFFFFFFF != crc:
        raise ShelfError("catalog CRC mismatch")
    if report.get("catalog_crc32") != f"{crc:08x}" or report.get("build_id") != f"{build_id:08x}":
        raise ShelfError("manifest catalog binding mismatch")
    seen = []
    for index, expected in enumerate(report.get("containers", [])):
        raw_name, off, length, item_crc, sha_prefix = RECORD.unpack_from(catalog, index * rbytes)
        name = raw_name.split(b"\0", 1)[0].decode("ascii")
        payload = data[off:off + length]
        if off < poff or len(payload) != length:
            raise ShelfError("container range mismatch")
        if name != expected["key"] or zlib.crc32(payload) & 0xFFFFFFFF != item_crc:
            raise ShelfError("container catalog mismatch")
        full_sha = sha_bytes(payload)
        if full_sha != expected["container_sha256"] or bytes.fromhex(full_sha)[:16] != sha_prefix:
            raise ShelfError("container SHA binding mismatch")
        seen.append(name)
    if seen != ["ide", "idex", "m65d", "buffer", "lcc"]:
        raise ShelfError("container order mismatch")
    return report


def selftest() -> None:
    verify_scratch_binding()
    (ROOT / "build").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="l65s-", dir=ROOT / "build") as raw:
        root = Path(raw)
        shelf = root / "shelf.bin"
        manifest = root / "manifest.json"
        first = build(shelf, manifest)
        first_bytes = shelf.read_bytes()
        second = build(shelf, manifest)
        if first["shelf_sha256"] != second["shelf_sha256"] or shelf.read_bytes() != first_bytes:
            raise ShelfError("shelf generation is not deterministic")
        for offset in (0, HEADER_BYTES, PAYLOAD_OFF):
            damaged = bytearray(first_bytes)
            damaged[offset] ^= 1
            bad = root / f"bad-{offset}.bin"
            bad.write_bytes(damaged)
            try:
                verify(bad, manifest)
            except ShelfError:
                pass
            else:
                raise ShelfError(f"mutation accepted at offset {offset}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "build/bytecode/dialect-v2/shelf/library-shelf.bin")
    parser.add_argument("--manifest-out", type=Path, default=ROOT / "build/bytecode/dialect-v2/shelf/library-shelf-manifest.json")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--era-check", action="store_true")
    args = parser.parse_args()
    if args.era_check:
        if args.selftest or args.verify:
            raise ShelfError("era check runs the archived selftest and verifier; no live override")
        era_check(args.out, args.manifest_out)
        return 0
    if args.selftest:
        selftest()
        print("v11-attic-library-shelf: SELFTEST PASS mutations=3 scratch-binding=shared")
    if args.verify:
        report = verify(args.out, args.manifest_out)
    else:
        report = build(args.out, args.manifest_out)
    print(f"v11-attic-library-shelf: PASS bytes={report['shelf_bytes']} sha256={report['shelf_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
