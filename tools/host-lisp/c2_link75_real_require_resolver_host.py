#!/usr/bin/env python3
"""Execute the real Link-75 Lisp require resolver against its exact media.

This fixture closes a deliberately narrow host boundary.  It executes the
compiled ``require``/L65I/C2D resolver objects from Link 75, serves disk sectors
from the exact defstruct D81, and serves Prim 67 from a mutable copy of the
exact Link-75 C2D image.  Prim 18 remains the target seam: on an authenticated
library locator it publishes the corresponding exact library image through
the C2D-v6 persistent-append model using the current target row semantics.

No product source, product link, emulator, or hardware is changed or run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any
import zlib


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
import bytecode_p0_stdlib as STD  # noqa: E402
import c2_full_emission as F  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402
import c2_link75_require_defstruct_host_attribution as ATTR  # noqa: E402
import c2_product_session_host as SESSION  # noqa: E402
import d81_persistence_fault as D81  # noqa: E402


BASE = ROOT / "build/post-promotion/link75-bound-compiler-carrier"
STATIC = BASE / "static-plane/narrow-static"
STDLIB = STATIC / "stdlib-p0.manifest.json"
STATIC_C2D = STATIC / "v6-semantics/initial.c2d-v6.bin"
STATIC_CODE = STATIC / "v6-semantics/bank2-static-code.bin"
FOUNDATIONS = ROOT / "build/post-promotion/defstruct-v1/foundations"
MEDIA = FOUNDATIONS / "require-defstruct.d81"
OUT = BASE / "real-require-resolver-host"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-real-require-resolver-host-receipt.json"
)
TARGET_APPEND = ROOT / "src/c2_product_runtime.c"
FORMAT = "lisp65-c2-link75-real-require-resolver-host-v1"
HANDLE_CAP = 4096

HISTORICAL_STDLIB = {
    "Link72": ROOT / (
        "build/post-promotion/link72-stz-semantics/static-plane/"
        "narrow-static/stdlib-p0.manifest.json"
    ),
    "Link73": ROOT / (
        "build/post-promotion/link73-vm-codebuf-owner/static-plane/"
        "narrow-static/stdlib-p0.manifest.json"
    ),
    "Link75": STDLIB,
}


class ResolverError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResolverError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"bound input absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"bound input absent: {path}")
    data = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(data),
        "sha256": sha_bytes(data),
    }


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def bound_prim67_history() -> dict[str, Any]:
    rows: dict[str, Any] = {}
    code_hashes: set[str] = set()
    for label, manifest_path in HISTORICAL_STDLIB.items():
        manifest = load(manifest_path)
        blob_path = ROOT / manifest["blob"]
        blob = blob_path.read_bytes()
        entry = next(
            (row for row in manifest["entries"]
             if row["name"] == "%require-c2d-byte"),
            None,
        )
        require(entry is not None, f"{label} lacks %require-c2d-byte")
        start, length = int(entry["blob_offset"]), int(entry["length"])
        encoded = blob[start:start + length]
        code = B.decode_code_object(encoded)
        # OP_CALLPRIM=0x3d, Prim 67=0x43, argc=2.
        require(
            b"\x3d\x43\x02" in bytes(code.payload),
            f"{label} resolver does not execute Prim 67",
        )
        digest = sha_bytes(encoded)
        code_hashes.add(digest)
        rows[label] = {
            "manifest": bind(manifest_path),
            "object_offset": start,
            "object_bytes": length,
            "object_sha256": digest,
            "payload_hex": bytes(code.payload).hex(),
            "callprim67_argc2": True,
        }
    require(
        len(code_hashes) == 1,
        "Link 72/73/75 bound %require-c2d-byte objects differ",
    )
    return {
        "status": "passed-static-resolver-already-called-Prim67",
        "byteidentical_links": list(HISTORICAL_STDLIB),
        "objects": rows,
        "conclusion": (
            "The stale runtime compiler carrier did not prevent the already "
            "compiled Link-72/73 stdlib resolver from calling Prim 67."
        ),
    }


class BoundStdlib:
    def __init__(self) -> None:
        self.manifest = load(STDLIB)
        self.blob = (ROOT / self.manifest["blob"]).read_bytes()
        require(
            len(self.blob) == int(self.manifest["code_bytes"])
            and sha_bytes(self.blob) == self.manifest["blob_sha256"],
            "Link-75 stdlib blob identity drift",
        )
        patches = {
            int(row["blob_offset"]): int(row["node"])
            for row in self.manifest["literal_patches"]
        }
        self.heap = C.prepare_heap([])
        self.directory: dict[int, B.CodeObject] = {}
        self.macros: set[int] = set()
        self.code_names: dict[int, str] = {}
        for entry in self.manifest["entries"]:
            code = STD._patched_code_from_manifest_entry(
                self.heap, self.manifest, self.blob, entry, patches
            )
            symbol = self.heap.intern(entry["name"])
            require(symbol not in self.directory,
                    f"duplicate stdlib entry: {entry['name']}")
            self.directory[symbol] = code
            self.code_names[id(code)] = entry["name"]
            if int(entry.get("flags", 0)) & STD.ENTRY_FLAG_MACRO:
                self.macros.add(symbol)
        self.ledger = C._abi_ledger("dialect-v2", None)
        self.require_symbol = self.heap.intern("require")
        require(
            self.require_symbol in self.directory,
            "bound stdlib omits require",
        )


def media_locators(data: bytes) -> tuple[
    dict[str, tuple[int, int]], dict[str, bytes]
]:
    D81.validate_bam(data)
    locators: dict[str, tuple[int, int]] = {}
    payloads: dict[str, bytes] = {}
    for slot in D81.directory_slots(data):
        if not slot.record[2]:
            continue
        name = D81.entry_name(slot.record).decode("ascii").lower()
        chain = D81.file_chain(data, slot.record)
        require(chain, f"empty D81 file chain: {name}")
        locators[name] = chain[0]
        payloads[name] = D81.read_record_payload(data, slot.record)
    require(
        set(("l65index", "place", "defstruct")) <= set(locators),
        "exact D81 omits require media",
    )
    return locators, payloads


class LivePlane:
    """Post-boot C2D plus target-shaped persistent library publication."""

    def __init__(self, *, mutation: str = "none") -> None:
        self.host = SESSION.ProductSessionHost(ATTR.initial_geometry(), OUT)
        static_c2d = STATIC_C2D.read_bytes()
        static_code = STATIC_CODE.read_bytes()
        require(
            struct.unpack_from("<H", static_c2d, 8)[0] == 0,
            "static C2D no longer carries the pre-boot inactive watermark",
        )
        self.host.plane.c2d[:] = static_c2d
        self.host.plane.code[:len(static_code)] = static_code
        # c2_product_prepare_boot publishes the inactive high-handle edge
        # before the Session family becomes live.
        struct.pack_into("<H", self.host.plane.c2d, 8, HANDLE_CAP)
        if mutation == "static-source-slot":
            self.host.plane.c2d[V6.C2D_IMAGES_OFFSET + 2] ^= 1
        self.images = {
            name: F.emit_image(
                name,
                "dfstrct" if name == "defstruct" else name,
                FOUNDATIONS / f"{name}.manifest.json",
            )
            for name in ("place", "defstruct")
        }
        self.mutation = mutation
        self.appends: list[dict[str, Any]] = []

    @property
    def data(self) -> bytearray:
        return self.host.plane.c2d

    def append(self, name: str) -> dict[str, Any]:
        require(name in self.images, f"unknown exact library: {name}")
        image = self.images[name]
        plane = self.host.plane
        old_images = plane.images
        before = (
            plane.images, plane.entries, plane.resolutions,
            plane.roots, plane.code_low,
        )
        result = V6.append_image(
            plane,
            image,
            transient=False,
            direct_resolver=self.host._resolve_direct(image),
        )
        # The generic static-plane v6 model stores code-only provenance in
        # field 28 and has no Session source-slot counter.  The current target
        # append path instead publishes the authenticated L65S combined CRC
        # and source_slot=(old_images-6).  Model that exact target boundary.
        row_at = V6.C2D_IMAGES_OFFSET + old_images * V6.C2D_IMAGE_BYTES
        plane.c2d[row_at + 2] = old_images - plane.immutable_images
        combined = zlib.crc32(image.code + image.metadata) & 0xFFFFFFFF
        struct.pack_into("<I", plane.c2d, row_at + 28, combined)
        struct.pack_into("<H", plane.c2d, 8, HANDLE_CAP)
        if self.mutation == "loaded-identity":
            plane.c2d[row_at + 28] ^= 1
        after = (
            plane.images, plane.entries, plane.resolutions,
            plane.roots, plane.code_low,
        )
        row = {
            "library": name,
            "before": list(before),
            "after": list(after),
            "handles": result["handles"],
            "image_slot": old_images,
            "source_slot": plane.c2d[row_at + 2],
            "combined_crc32": struct.unpack_from(
                "<I", plane.c2d, row_at + 28
            )[0],
        }
        self.appends.append(row)
        return row


class ResolverVM(B.P0VM):
    def __init__(
        self,
        bound: BoundStdlib,
        plane: LivePlane,
        media: bytes,
        locators: dict[str, tuple[int, int]],
        *,
        prim67_zero: bool = False,
        load_without_publish: bool = False,
    ) -> None:
        super().__init__(
            heap=bound.heap,
            directory=bound.directory,
            macro_symbols=bound.macros,
            max_steps=100_000_000,
            code_names=bound.code_names,
            abi_profile="dialect-v2",
            abi_ledger=bound.ledger,
        )
        self.live_plane = plane
        self.exact_media = media
        self.locator_names = {
            value: name
            for name, value in locators.items()
            if name in ("place", "defstruct")
        }
        self.prim67_zero = prim67_zero
        self.load_without_publish = load_without_publish
        self.prim67_reads: list[dict[str, int]] = []
        self.loader_attempts: list[dict[str, Any]] = []

    def _disk_read_sector_impl(self, track: int, sector: int) -> bool:
        self.disk_buf = [0] * 256
        try:
            self.disk_buf = list(
                D81.get_sector(self.exact_media, track, sector)
            )
        except ValueError:
            return False
        return True

    def _custom_args(
        self, prim_id: int, argc: int, stack: list[int], pc: int | None
    ) -> list[int]:
        self._check_argc(argc, "CALLPRIM")
        classification = B.classify_abi_id(
            "prim",
            prim_id,
            profile_id=self.abi_profile,
            abi_ledger=self.abi_ledger,
        )
        if classification["status"] != "active":
            raise B.VMError(
                "BadOpcode",
                f"inactive Prim {prim_id}: {classification['diagnostic']}",
            )
        args = self._pop_args(argc, stack)
        self._trace_call(
            "CALLPRIM",
            B.PRIM_IDS.get(prim_id, f"#{prim_id}"),
            argc,
            pc=pc,
            resolved=True,
        )
        return args

    def _callprim(
        self,
        prim_id: int,
        argc: int,
        stack: list[int],
        pc: int | None = None,
        native_base: int = 0,
        frame_slots: int = 0,
    ) -> int:
        if prim_id not in (18, 67):
            return super()._callprim(
                prim_id, argc, stack, pc, native_base, frame_slots
            )
        args = self._custom_args(prim_id, argc, stack, pc)
        if prim_id == 67:
            if argc != 2 or not all(B.is_fix(arg) for arg in args):
                raise B.VMError(
                    "TypeError", "%c2d-byte expects low and high bytes"
                )
            lo, hi = (B.fixval(arg) for arg in args)
            if not (0 <= lo <= 255 and 0 <= hi <= 255):
                raise B.VMError(
                    "TypeError", "%c2d-byte address byte out of range"
                )
            offset = lo | (hi << 8)
            if not 0 <= offset < len(self.live_plane.data):
                raise B.VMError(
                    "TypeError", "%c2d-byte offset outside published C2D"
                )
            value = 0 if self.prim67_zero else self.live_plane.data[offset]
            self.prim67_reads.append({"offset": offset, "value": value})
            return B.mkfix(value)

        if argc == 1 and self.heap.stringp(args[0]):
            # No reset-persistent shelf is modeled; the real D81 lane follows.
            return B.NIL
        if argc != 2 or not all(B.is_fix(arg) for arg in args):
            raise B.VMError(
                "TypeError",
                "%disk-load-lib expects name or track and sector",
            )
        locator = tuple(B.fixval(arg) for arg in args)
        name = self.locator_names.get(locator)
        event = {
            "track": locator[0],
            "sector": locator[1],
            "library": name,
        }
        self.loader_attempts.append(event)
        if name is None:
            event["result"] = "not-found"
            return B.NIL
        if self.load_without_publish:
            event["result"] = "reported-success-without-publication"
            return self.heap.t_obj
        self.live_plane.append(name)
        self.disk_loaded_libs.append(locator)
        event["result"] = "published"
        return self.heap.t_obj


def candidate_media(mutation: str) -> bytes:
    data = bytearray(MEDIA.read_bytes())
    if mutation == "index-magic":
        # L65INDEX begins at payload byte 2 in its one-sector T39/S0 chain.
        data[D81.sector_offset(39, 0) + 2] ^= 1
    return bytes(data)


def run_case(mutation: str = "none") -> dict[str, Any]:
    bound = BoundStdlib()
    media = candidate_media(mutation)
    locators, payloads = media_locators(media)
    if mutation == "index-magic":
        # Directory and payload extraction remain structurally valid.
        require(payloads["l65index"][:4] != b"L65I", "index mutation missed")
    else:
        require(
            payloads["l65index"] == (FOUNDATIONS / "l65index").read_bytes()
            and payloads["place"] == (FOUNDATIONS / "place.l65s").read_bytes()
            and payloads["defstruct"]
                == (FOUNDATIONS / "defstruct.l65s").read_bytes(),
            "D81 visible files differ from bound foundation artifacts",
        )
    plane = LivePlane(
        mutation=mutation
        if mutation in ("loaded-identity", "static-source-slot")
        else "none"
    )
    if mutation == "inactive-watermark":
        struct.pack_into("<H", plane.data, 8, 0)
    vm = ResolverVM(
        bound,
        plane,
        media,
        locators,
        prim67_zero=mutation == "prim67-zero",
        load_without_publish=mutation == "load-without-publish",
    )
    result = vm.run(
        bound.directory[bound.require_symbol],
        [bound.heap.intern("defstruct")],
    )
    first = {
        "result": bound.heap.obj_to_text(result),
        "steps": vm.steps,
        "disk_sector_reads": vm.io_counters["disk_read"],
        "prim67_reads": len(vm.prim67_reads),
        "prim67_unique_offsets": len({
            row["offset"] for row in vm.prim67_reads
        }),
        "prim67_trace_sha256": sha_bytes(canonical(vm.prim67_reads)),
        "loader_attempts": list(vm.loader_attempts),
        "appends": list(plane.appends),
        "final_counts": {
            "images": plane.host.plane.images,
            "entries": plane.host.plane.entries,
            "resolutions": plane.host.plane.resolutions,
            "roots": plane.host.plane.roots,
            "code_bytes": plane.host.plane.code_low,
        },
    }
    if mutation != "none":
        return first

    require(first["result"] == "t", "real compiled require did not return t")
    require(
        [row["library"] for row in first["loader_attempts"]]
        == ["place", "defstruct"],
        "resolver dependency/load order drift",
    )
    require(
        first["prim67_reads"] > 0
        and first["disk_sector_reads"] == 2,
        "real resolver did not cross exact Prim-67/D81 boundaries",
    )
    snapshot = bytes(plane.data), bytes(plane.host.plane.code)
    reads_before = len(vm.prim67_reads)
    loads_before = len(vm.loader_attempts)
    result = vm.run(
        bound.directory[bound.require_symbol],
        [bound.heap.intern("defstruct")],
    )
    second = {
        "result": bound.heap.obj_to_text(result),
        "steps": vm.steps,
        "additional_prim67_reads": len(vm.prim67_reads) - reads_before,
        "additional_loader_attempts":
            len(vm.loader_attempts) - loads_before,
        "c2d_and_code_byteidentical": snapshot
            == (bytes(plane.data), bytes(plane.host.plane.code)),
    }
    require(
        second == {
            "result": "t",
            "steps": second["steps"],
            "additional_prim67_reads": second["additional_prim67_reads"],
            "additional_loader_attempts": 0,
            "c2d_and_code_byteidentical": True,
        },
        "generation-bound require idempotence drift",
    )
    first["second_require"] = second
    return first


def target_append_model_gate() -> dict[str, Any]:
    source = TARGET_APPEND.read_text(encoding="utf-8")
    checks = {
        "session_source_slot_from_old_image_count":
            "w->old_images - 6u" in source,
        "combined_crc_from_authenticated_L65S":
            "combined = c2_stage_u32(58u);" in source,
        "combined_crc_published_at_image_field_28":
            "row[28] = (uint8_t)combined;" in source
            and "row[31] = (uint8_t)(combined >> 24);" in source,
        "boot_publishes_inactive_transient_watermark":
            "c2_header_watermark(header, C2D_HANDLE_CAP);" in source,
    }
    require(all(checks.values()), "target append semantics drift")
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    args = parser.parse_args()
    try:
        history = bound_prim67_history()
        target_model = target_append_model_gate()
        baseline = run_case()
        expected_counts = {
            "images": 8,
            "entries": 709,
            "resolutions": 2827,
            "roots": 358,
            "code_bytes": 41980,
        }
        require(
            baseline["final_counts"] == expected_counts,
            "real resolver published unexpected final C2D geometry",
        )
        mutations = {}
        for mutation in (
            "prim67-zero",
            "inactive-watermark",
            "index-magic",
            "load-without-publish",
            "loaded-identity",
            "static-source-slot",
        ):
            row = run_case(mutation)
            require(
                row["result"] == "nil",
                f"resolver mutation survived: {mutation}",
            )
            mutations[mutation] = {
                "result": row["result"],
                "prim67_reads": row["prim67_reads"],
                "loader_attempts": row["loader_attempts"],
                "appends": row["appends"],
            }
        value = {
            "format": FORMAT,
            "recorded_on": "2026-07-28",
            "status":
                "passed-real-Link75-Lisp-resolver-exact-C2D-D81-host-run",
            "promotable": False,
            "product_delta_bytes": 0,
            "product_links": 0,
            "hardware_runs": 0,
            "historical_interpretation": history,
            "target_append_model": target_model,
            "baseline": baseline,
            "mutations_rejected": mutations,
            "attribution": {
                "actual_compiled_require_executed": True,
                "actual_compiled_l65i_parser_executed": True,
                "actual_compiled_require_resolver_executed": True,
                "actual_prim67_c2d_reads": baseline["prim67_reads"],
                "exact_D81_sector_reads": baseline["disk_sector_reads"],
                "dependency_order": ["place", "defstruct"],
                "result": "t",
                "logical_resolver_status": "entlastet-hostseitig",
                "next_hardware_order": (
                    "Run the already specified small Bank-5 read completion "
                    "measurement before another require/defstruct retry."
                ),
            },
            "authority": {
                "stdlib": bind(STDLIB),
                "static_c2d": bind(STATIC_C2D),
                "static_bank2": bind(STATIC_CODE),
                "D81": bind(MEDIA),
                "index": bind(FOUNDATIONS / "l65index"),
                "place_L65S": bind(FOUNDATIONS / "place.l65s"),
                "defstruct_L65S": bind(FOUNDATIONS / "defstruct.l65s"),
                "target_append_source": bind(TARGET_APPEND),
                "driver": bind(Path(__file__).resolve()),
            },
            "claim_limit": (
                "The exact compiled Link-75 Lisp parser/resolver and every "
                "Prim-67 decision execute in the host VM against exact C2D "
                "and D81 bytes. Prim 18 publishes exact library artifacts "
                "through a target-shaped C2D-v6 model; it does not execute "
                "the linked 45GS02 loader, physical DMA, IRQ, CPU or target "
                "ABI behavior. No hardware reliability claim is made."
            ),
        }
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            "c2-link75-real-require-resolver-host: PASS "
            f"prim67={baseline['prim67_reads']} "
            "loads=place,defstruct result=t idempotent=t mutations=6"
        )
        return 0
    except (ResolverError, B.VMError, ValueError) as error:
        print(
            "c2-link75-real-require-resolver-host: FIRST RED: "
            + str(error),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
