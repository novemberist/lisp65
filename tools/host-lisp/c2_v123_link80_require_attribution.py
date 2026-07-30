#!/usr/bin/env python3
"""Attribute Link-80 ``(require 'place)`` against its exact rebound medium.

This is a host-only Halt-1 discriminator.  It executes the compiled Link-80
Lisp require/index/resolver objects, serves Prim 67 from a mutable copy of the
exact Link-80 C2D image, and serves disk sectors from the D81 that was uploaded
and read back during the bundled hardware session.  Prim 18 remains modeled by
the existing target-shaped persistent-append lane; no product is rebuilt.
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import c2_link75_real_require_resolver_host as R  # noqa: E402
import c2_require_resolver_gate as L65I  # noqa: E402
from elf_truth import ElfTruth, ElfTruthError  # noqa: E402


BASE = ROOT / "build/c2.2/v1.2.3-candidate-product-link80"
STATIC = BASE / "static-plane/narrow-static"
STDLIB = STATIC / "stdlib-p0.manifest.json"
STATIC_C2D = STATIC / "v6-semantics/initial.c2d-v6.bin"
STATIC_CODE = STATIC / "v6-semantics/bank2-static-code.bin"
SESSION = ROOT / "build/post-promotion/v1.2.3/link80-bundled-session"
MEDIA_DIR = SESSION / "library-media"
MEDIA = MEDIA_DIR / "require-defstruct-link78-bound.d81"
MEDIA_READBACK = SESSION / "uploaded-media-readback.d81"
OUT = SESSION / "require-host-attribution"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.3-link80-require-host-attribution-receipt.json"
)
PRODUCT_MANIFEST = BASE / "canonical-product-manifest.json"
ELF = BASE / "final/lisp65-c2-substitution-linked.prg.elf"
LLVM_READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
VM_SOURCE = ROOT / "src/vm.c"
RUNTIME_SOURCE = ROOT / "src/c2_product_runtime.c"
REQUIRE_SOURCE = ROOT / "lib/stdlib-require.lisp"
FORMAT = "lisp65-c2-v1.2.3-link80-require-host-attribution-v1"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


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


def configure_exact_link80() -> None:
    """Point the proven real-resolver runner at Link 80 without copying it."""
    R.BASE = BASE
    R.STATIC = STATIC
    R.STDLIB = STDLIB
    R.STATIC_C2D = STATIC_C2D
    R.STATIC_CODE = STATIC_CODE
    R.MEDIA = MEDIA
    R.OUT = OUT
    # The inherited Link-75 append lane otherwise seeds its in-memory
    # counters from Link 75 while copying Link-80 C2D bytes over them.  Bind
    # both representations to the exact Link-80 header.
    data = STATIC_C2D.read_bytes()
    code = STATIC_CODE.read_bytes()
    u16 = lambda at: struct.unpack_from("<H", data, at)[0]
    u32 = lambda at: struct.unpack_from("<I", data, at)[0]
    geometry = {
        "generation": u16(10),
        "images": u16(12),
        "entries": u16(16),
        "resolutions": u16(20),
        "roots": u16(24),
        "code_bytes": len(code),
        "immutable_images": u16(38),
        "catalog_crc32": u32(40),
        "build_id": u32(44),
    }
    R.ATTR.initial_geometry = lambda: dict(geometry)


def artifact_binding() -> dict[str, Any]:
    media = MEDIA.read_bytes()
    readback = MEDIA_READBACK.read_bytes()
    require(media == readback, "uploaded D81 readback differs from source D81")
    locators, payloads = R.media_locators(media)
    exact = {
        "place": (MEDIA_DIR / "place.l65s").read_bytes(),
        "defstruct": (MEDIA_DIR / "defstruct.l65s").read_bytes(),
    }
    require(
        payloads["l65index"] == (MEDIA_DIR / "l65index").read_bytes()
        and payloads["place"] == exact["place"]
        and payloads["defstruct"] == exact["defstruct"],
        "D81 visible files differ from Link-80 library-media authority",
    )
    manifest = json.loads(PRODUCT_MANIFEST.read_text(encoding="utf-8"))
    build_id = int(manifest["static_plane"]["product_build_id"], 0)
    rows = L65I.decode_index(
        payloads["l65index"], exact, artifact_build_id=build_id
    )
    require(
        L65I.resolve(rows, "place", 7, [], L65I.CAPACITY) == [0],
        "Link-80 place resolution order drift",
    )
    require(
        L65I.resolve(rows, "defstruct", 7, [], L65I.CAPACITY) == [0, 1],
        "Link-80 defstruct resolution order drift",
    )
    place = rows[0]
    raw_row = payloads["l65index"][
        L65I.HEADER_BYTES:L65I.HEADER_BYTES + L65I.ROW_BYTES
    ]
    return {
        "status": "H0-disproved-no-media-or-index-lock-mismatch",
        "product_build_id": f"0x{build_id:08x}",
        "D81_source_and_uploaded_readback_byteidentical": True,
        "D81_sha256": sha_bytes(media),
        "visible_locators": {
            name: list(locator) for name, locator in sorted(locators.items())
        },
        "index": {
            "records_crc16": (
                f"0x{struct.unpack_from('<H', payloads['l65index'], 11)[0]:04x}"
            ),
            "header_crc16": (
                f"0x{struct.unpack_from('<H', payloads['l65index'], 17)[0]:04x}"
            ),
            "identity_crc32": (
                f"0x{struct.unpack_from('<I', payloads['l65index'], 13)[0]:08x}"
            ),
            "place_row_crc16": (
                f"0x{struct.unpack_from('<H', raw_row, 45)[0]:04x}"
            ),
        },
        "place": {
            "locator": [place["track"], place["sector"]],
            "combined_crc32": f"0x{place['combined_crc32']:08x}",
            "artifact_bytes": place["artifact_bytes"],
            "dependencies": place["dependencies"],
            "resolve_order": [0],
        },
        "defstruct_resolve_order": [0, 1],
    }


def run_exact_place() -> dict[str, Any]:
    configure_exact_link80()
    bound = R.BoundStdlib()
    media = MEDIA.read_bytes()
    locators, payloads = R.media_locators(media)

    # Product rebinds change only the L65S envelope.  The target-shaped append
    # model consumes the code/C2I body, which must remain the proven foundation.
    for name in ("place", "defstruct"):
        current = payloads[name]
        foundation = (R.FOUNDATIONS / f"{name}.l65s").read_bytes()
        require(
            len(current) == len(foundation) and current[64:] == foundation[64:],
            f"{name} code/C2I differs from proven append-model authority",
        )

    plane = R.LivePlane()
    vm = R.ResolverVM(bound, plane, media, locators)
    place_symbol = bound.heap.intern("place")
    result = vm.run(
        bound.directory[bound.require_symbol],
        [place_symbol],
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
    require(first["result"] == "t", "exact Link-80 require place returned nil")
    require(
        [row["library"] for row in vm.loader_attempts] == ["place"],
        "exact Link-80 resolver did not load only place",
    )
    require(
        len(plane.appends) == 1
        and plane.appends[0]["combined_crc32"] == 0x485A1CE2,
        "published place identity differs from exact L65I row",
    )
    require(
        first["prim67_reads"] > 0 and first["disk_sector_reads"] > 0,
        "exact resolver did not cross Prim-67 and D81 boundaries",
    )

    snapshot = bytes(plane.data), bytes(plane.host.plane.code)
    reads_before = len(vm.prim67_reads)
    loads_before = len(vm.loader_attempts)
    repeat = vm.run(
        bound.directory[bound.require_symbol],
        [place_symbol],
    )
    second = {
        "result": bound.heap.obj_to_text(repeat),
        "steps": vm.steps,
        "additional_prim67_reads": len(vm.prim67_reads) - reads_before,
        "additional_loader_attempts": len(vm.loader_attempts) - loads_before,
        "c2d_and_code_byteidentical": snapshot
            == (bytes(plane.data), bytes(plane.host.plane.code)),
    }
    require(
        second["result"] == "t"
        and second["additional_loader_attempts"] == 0
        and second["c2d_and_code_byteidentical"],
        "Link-80 place idempotence failed in exact host route",
    )
    first["second_require"] = second
    return first


def target_boundary() -> dict[str, Any]:
    """Bind the third and final Class-B cycle to the linked target seam."""
    truth = ElfTruth.read(ELF, llvm_readobj=LLVM_READOBJ)
    names = (
        "vm_callprim",
        "disk_chain_to_scratch",
        "c2_product_append_staged",
        "c2_append_begin",
        "vm_runtime_overlay_transaction_begin",
        "vm_runtime_overlay_transaction_end",
        "c2_stream_c2d_read",
    )
    symbols = {}
    for name in names:
        row = truth.symbol(name)
        require(row.bytes > 0, f"linked target seam has empty symbol: {name}")
        symbols[name] = {
            "address": f"0x{row.value:04x}",
            "bytes": row.bytes,
            "section": row.section,
        }

    vm_source = VM_SOURCE.read_text(encoding="utf-8")
    runtime_source = RUNTIME_SOURCE.read_text(encoding="utf-8")
    require_source = REQUIRE_SOURCE.read_text(encoding="utf-8")
    checks = {
        "Prim18_stages_then_appends":
            "staged = io_disk_stage_chain" in vm_source
            and "staged && c2_product_append_staged(staged) ? vm_t : NIL"
                in vm_source,
        "append_result_saved_across_transaction_end":
            "ok = c2_append_begin(length, &before, &main" in runtime_source
            and "if (vm_runtime_overlay_transaction_end()"
                " != VM_RUNTIME_OVERLAY_OK) return 0;" in runtime_source
            and "return ok;" in runtime_source,
        "published_identity_from_authenticated_L65S":
            "combined = c2_stage_u32(58u);" in runtime_source
            and "row[28] = (uint8_t)combined;" in runtime_source
            and "row[31] = (uint8_t)(combined >> 24);" in runtime_source,
        "require_checks_loader_then_published_identity":
            "(if (%disk-load-lib (nth 2 row) (nth 3 row))"
                in require_source
            and "(if (%require-identity-loaded-p row)" in require_source,
        "require_success_rechecks_requested_identity":
            "(%require-fast-note" in require_source
            and "%require-identity-loaded-at-value" in require_source,
    }
    require(all(checks.values()), "linked target seam source contract drift")
    return {
        "status": "bounded-target-runtime-seam-no-static-discriminator-left",
        "commission_cycle": 3,
        "linked_symbols": symbols,
        "source_dataflow_checks": checks,
        "false_result_boundaries": [
            {
                "boundary": "Prim18 stage/append",
                "outcome": (
                    "io_disk_stage_chain or c2_product_append_staged returns "
                    "zero; %disk-load-lib returns nil before the Lisp "
                    "post-publication identity check"
                ),
            },
            {
                "boundary": "transaction terminator",
                "outcome": (
                    "c2_append_begin may have completed, but a non-OK "
                    "vm_runtime_overlay_transaction_end forces the native "
                    "wrapper result to zero"
                ),
            },
            {
                "boundary": "post-publication identity read",
                "outcome": (
                    "Prim18 returns t, but the target C2D readback does not "
                    "show the requested combined identity to "
                    "%require-identity-loaded-p/%require-fast-note"
                ),
            },
        ],
        "available_hardware_evidence": (
            "The screen proves only the final Lisp nil and 272 elapsed "
            "frames; no post-row C2D header/image readback or Prim18 return "
            "witness was captured."
        ),
        "disposition": (
            "The Class-B three-cycle budget is exhausted without an "
            "attributed product mechanism. No fix, link or hardware retry "
            "is authorized; Phase E remains closed and the residual target "
            "runtime boundary returns for owner disposition."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    args = parser.parse_args()
    try:
        h0 = artifact_binding()
        h1 = run_exact_place()
        h2 = target_boundary()
        value = {
            "format": FORMAT,
            "recorded_on": "2026-07-30",
            "status": "passed-H0-binding-and-H1-exact-Link80-host-success",
            "promotable": False,
            "product_delta_bytes": 0,
            "product_links": 0,
            "hardware_runs": 0,
            "commission": {
                "class": "B",
                "cycles_completed": 3,
                "limit": "at most three attribution cycles",
                "product_fix_authorized": False,
            },
            "H0_artifact_binding": h0,
            "H1_exact_success_path": h1,
            "H2_linked_target_boundary": h2,
            "fixture_hygiene": {
                "first_execution_rejected": (
                    "The inherited Link-75 runner initially mixed Link-80 "
                    "C2D bytes with Link-75 in-memory geometry counters."
                ),
                "correction": (
                    "Seed images/entries/resolutions/roots/code/build ID "
                    "from the exact Link-80 C2D header and Bank-2 image "
                    "before making any H1 claim."
                ),
                "corrected_first_counts": h1["appends"][0]["before"],
            },
            "attribution": {
                "H0_index_lock_or_media_mismatch": "disproved",
                "H1_real_Link80_Lisp_resolver_result": "t",
                "H1_repeat_result": "t",
                "logical_parser_resolver_and_publication_model":
                    "entlastet-hostseitig",
                "hardware_observation": "nil after 272 frames",
                "remaining_boundary": (
                    "target Prim-18 loader/publication return or the "
                    "post-publication C2D identity scan on real 45GS02"
                ),
                "class_B_disposition": (
                    "budget exhausted; no mechanism-attributed product fix"
                ),
            },
            "authority": {
                "stdlib": bind(STDLIB),
                "static_c2d": bind(STATIC_C2D),
                "static_bank2": bind(STATIC_CODE),
                "D81": bind(MEDIA),
                "uploaded_D81_readback": bind(MEDIA_READBACK),
                "index": bind(MEDIA_DIR / "l65index"),
                "place_L65S": bind(MEDIA_DIR / "place.l65s"),
                "defstruct_L65S": bind(MEDIA_DIR / "defstruct.l65s"),
                "product_manifest": bind(PRODUCT_MANIFEST),
                "linked_ELF": bind(ELF),
                "vm_source": bind(VM_SOURCE),
                "runtime_source": bind(RUNTIME_SOURCE),
                "require_source": bind(REQUIRE_SOURCE),
                "driver": bind(Path(__file__).resolve()),
            },
            "claim_limit": (
                "The exact compiled Link-80 Lisp parser/resolver and every "
                "Prim-67 decision execute in the host VM against exact C2D "
                "and hardware-uploaded D81 bytes. Prim 18 publishes through "
                "the existing target-shaped C2D-v6 model; this does not "
                "execute physical DMA, the linked 45GS02 loader, IRQ or "
                "target ABI behavior."
            ),
        }
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            "c2-v123-link80-require-attribution: PASS "
            f"H0=disproved H1={h1['result']} "
            f"prim67={h1['prim67_reads']} "
            f"loads={len(h1['loader_attempts'])} repeat="
            f"{h1['second_require']['result']}"
        )
        return 0
    except (AttributionError, R.ResolverError, L65I.GateError,
            ElfTruthError, B.VMError, KeyError, ValueError) as error:
        print(
            "c2-v123-link80-require-attribution: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
