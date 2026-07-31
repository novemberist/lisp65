#!/usr/bin/env python3
"""Test the post-v1.2.4 require prior-append discriminant on the host.

The four device observations appeared to split on whether persistent Session
appends preceded ``require``.  This fixture tests that H1 before any linked
seam mapping.  It executes the exact v1.2.4 bound resolver twice with the
released product medium and twice with a product-identity-bound library
medium:

* no prior Session append;
* the exact two soak helper definitions appended through ProductSessionHost.

The released product D81 is also inventoried independently.  This matters
because ``require`` media is not part of the v1.2.4 product D81.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
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
import c2_link75_require_defstruct_host_attribution as CARRIER  # noqa: E402
import c2_link75_library_media_successor as MEDIA  # noqa: E402
import c2_link75_real_require_resolver_host as R  # noqa: E402
import c2_require_resolver_gate as L65I  # noqa: E402


BASE = ROOT / "build/c2.2/v1.2.4-candidate-product-link81"
STATIC = BASE / "static-plane/narrow-static"
STDLIB = STATIC / "stdlib-p0.manifest.json"
STATIC_C2D = ROOT / (
    "build/c2.2/v1.2.4-acceptance/r5/product/09-initial.c2d-v6.bin")
STATIC_CODE = ROOT / (
    "build/c2.2/v1.2.4-acceptance/r5/product/01-bank2-static-code.bin")
PRODUCT_D81 = ROOT / (
    "build/c2.2/v1.2.4-acceptance/r5/product/15-lisp65-product.d81")
PRODUCT_MOUNT = ROOT / (
    "build/c2.2/v1.2.4-acceptance/r5/product/"
    "16-lisp65-product.mount.json")
BASE_LIBRARY_D81 = ROOT / (
    "build/post-promotion/v124/phase-m/library-media/"
    "require-defstruct-link78-bound.d81")
COMPILER_CARRIER = ROOT / (
    "build/post-promotion/phase-v/while/gate/carrier/lcc.manifest.json")
COMPILER_TIER = ROOT / (
    "build/post-promotion/phase-v/while/gate/compiler-tier/"
    "tier-generation.json")
SOAK_CONFIG = ROOT / "config/c2-v124-post-release-soak.json"
REQUIRE_SOURCE = ROOT / "lib/stdlib-require.lisp"
REQUIRE_CONTRACT = ROOT / "config/c2-require-resolver-contract.json"
SOAK_HARDWARE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/post-release/"
    "post-v124-soak-first-anomaly-hardware-receipt-20260730.json")
LINK80_HARDWARE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.3-link80-bundled-hardware-receipt.json")
OUT = ROOT / (
    "build/post-promotion/v124/post-release-soak/"
    "h1-require-prior-appends")
LIBRARY_OUT = OUT / "library-media"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/post-release/"
    "post-v124-require-prior-append-h1-receipt-20260730.json")
FORMAT = "lisp65-c2.2-v1.2.4-require-prior-append-h1-v1"


class H1Error(RuntimeError):
    pass


class ResolverTrace:
    def __init__(self) -> None:
        self.entries: Counter[str] = Counter()

    def enter(self, name: str, _code: B.CodeObject, _args: list[int]) -> None:
        self.entries[name] += 1

    def exit(self, _name: str, _code: B.CodeObject) -> None:
        pass


def require(value: bool, message: str) -> None:
    if not value:
        raise H1Error(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    data = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(data),
        "sha256": sha_bytes(data),
    }


def write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode(
        "ascii")
    if path.exists():
        require(path.read_bytes() == encoded, f"receipt drift: {path}")
    else:
        path.write_bytes(encoded)


def geometry() -> dict[str, int]:
    data = STATIC_C2D.read_bytes()
    code = STATIC_CODE.read_bytes()
    require(
        len(data) == 33840
        and data[:8] == b"C2D\0\x06\x30\x20\x0a"
        and len(code) == 43218,
        "released v1.2.4 static geometry drift",
    )
    u16 = lambda at: struct.unpack_from("<H", data, at)[0]
    u32 = lambda at: struct.unpack_from("<I", data, at)[0]
    result = {
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
    require(
        result["generation"] == 1
        and result["images"] == result["immutable_images"] == 6
        and result["build_id"] == 0x15DA63C2,
        "released v1.2.4 identity/count drift",
    )
    return result


def configure_v124() -> dict[str, int]:
    result = geometry()
    R.BASE = BASE
    R.STATIC = STATIC
    R.STDLIB = STDLIB
    R.STATIC_C2D = STATIC_C2D
    R.STATIC_CODE = STATIC_CODE
    R.OUT = OUT
    R.ATTR.initial_geometry = lambda: dict(result)
    return result


def visible_files(path: Path) -> dict[str, bytes]:
    return {
        key.decode("ascii").lower(): value
        for key, value in L65I.D81.visible_files(path.read_bytes()).items()
    }


def build_library_media(build_id: int) -> tuple[Path, dict[str, Any]]:
    require(BASE_LIBRARY_D81.is_file(), "base library medium absent")
    locators = L65I.d81_locators(BASE_LIBRARY_D81)
    artifacts, rows = MEDIA.expected_artifacts(build_id, locators)
    old = visible_files(BASE_LIBRARY_D81)
    require(
        set(("l65index", "place", "defstruct")) <= set(old),
        "base library medium inventory drift",
    )
    paths: list[tuple[Path, str]] = []
    envelope_deltas: dict[str, list[int]] = {}
    for name, data in artifacts.items():
        delta = [
            offset
            for offset, (before, after) in enumerate(zip(old[name], data))
            if before != after
        ]
        require(
            len(old[name]) == len(data)
            and old[name][64:] == data[64:]
            and set(delta) <= set(range(18, 26))
            and struct.unpack_from("<I", data, 22)[0] == build_id,
            f"{name} changed outside the product-bound envelope",
        )
        path = LIBRARY_OUT / f"{name}.l65s"
        write_bytes(path, data)
        paths.append((path, name))
        envelope_deltas[name] = delta

    index = L65I.encode_index(rows)
    require(index == old["l65index"], "L65I changed during identity rebind")
    index_path = LIBRARY_OUT / "l65index"
    write_bytes(index_path, index)
    decoded = L65I.decode_index(
        index, artifacts, artifact_build_id=build_id)
    require(
        L65I.resolve(decoded, "place", 7, [], L65I.CAPACITY) == [0],
        "product-bound place resolution drift",
    )
    mutations = L65I.mutation_gate(
        index, artifacts, artifact_build_id=build_id)
    d81 = LIBRARY_OUT / "require-place-v124-bound.d81"
    L65I.build_d81(d81, index_path, paths)
    new = visible_files(d81)
    require(
        L65I.d81_locators(d81) == locators
        and new["l65index"] == index
        and new["place"] == artifacts["place"]
        and new["defstruct"] == artifacts["defstruct"],
        "generated v1.2.4 library medium drift",
    )
    return d81, {
        "D81": bind(d81),
        "index": bind(index_path),
        "place": bind(LIBRARY_OUT / "place.l65s"),
        "defstruct": bind(LIBRARY_OUT / "defstruct.l65s"),
        "product_build_id": f"0x{build_id:08x}",
        "locators": {
            name: list(locator)
            for name, locator in sorted(locators.items())
        },
        "envelope_deltas": envelope_deltas,
        "code_and_C2I": "byte-identical-to-base-library-medium",
        "index_mutations_rejected": len(mutations),
    }


def helper_forms() -> list[tuple[str, str]]:
    config = json.loads(SOAK_CONFIG.read_text(encoding="utf-8"))
    rows = {row["id"]: row for row in config["setup"]}
    require(
        rows["cycle-helper"]["expected"] == "%s"
        and rows["status-helper"]["expected"] == "%sr",
        "soak helper authority drift",
    )
    return [
        (rows["cycle-helper"]["form"], "%s"),
        (rows["status-helper"]["form"], "%sr"),
    ]


def append_helpers(plane: R.LivePlane) -> list[dict[str, Any]]:
    """Compile and append the exact soak helpers through the bound carrier."""
    CARRIER.CARRIER = COMPILER_CARRIER
    CARRIER.TIER = COMPILER_TIER
    compiler = CARRIER.BoundCarrierCompiler()
    CARRIER.attach_heap(plane.host, compiler.heap)
    rows = []
    for source, entry in helper_forms():
        compiled = compiler.compile(source)
        require(
            compiled["name"] == entry
            and compiled["kind"] == "defun"
            and compiled["flags"] == 0,
            f"{entry} compiler-carrier identity drift",
        )
        append = plane.host.append_compiled_definition(
            source,
            entry,
            compiled["code"],
            compiler_authority=bind(COMPILER_CARRIER)["sha256"],
        )
        # The generic Session-host append model has no transient high-front
        # owner and no Session source-slot counter.  The product does: each
        # successful persistent append republishes the authenticated 4096
        # high watermark and source_slot=(image_slot-6).  Mirror those two
        # already-bound target fields before require inspects the world.
        row_at = 48 + append["image_slot"] * 32
        plane.host.plane.c2d[row_at + 2] = append["image_slot"] - 6
        struct.pack_into("<H", plane.host.plane.c2d, 8, 4096)
        append["compiler_steps"] = compiled["steps"]
        append["code"] = compiled["summary"]
        rows.append(append)
    return rows


def persistent_rows(plane: R.LivePlane) -> list[dict[str, Any]]:
    data = plane.host.plane.c2d
    rows = []
    for slot in range(6, plane.host.plane.images):
        at = 48 + slot * 32
        rows.append({
            "slot": slot,
            "source_kind": data[at],
            "source_slot": data[at + 2],
            "generation": struct.unpack_from("<H", data, at + 4)[0],
            "entry_base": struct.unpack_from("<H", data, at + 6)[0],
            "entry_count": struct.unpack_from("<H", data, at + 8)[0],
            "resolution_base": struct.unpack_from("<H", data, at + 10)[0],
            "resolution_count": struct.unpack_from("<H", data, at + 12)[0],
            "root_base": struct.unpack_from("<H", data, at + 14)[0],
            "root_count": struct.unpack_from("<H", data, at + 16)[0],
            "code_base": struct.unpack_from("<H", data, at + 18)[0],
            "code_bytes": struct.unpack_from("<H", data, at + 21)[0],
            "combined_crc32": struct.unpack_from("<I", data, at + 28)[0],
        })
    return rows


def run_case(
    *,
    label: str,
    media: Path,
    library_media: bool,
    prior_helpers: bool,
) -> dict[str, Any]:
    bound = R.BoundStdlib()
    plane = R.LivePlane()
    appends = []
    if prior_helpers:
        appends = append_helpers(plane)
        require(
            [row["entry"] for row in appends] == ["%s", "%sr"]
            and [row["image_slot"] for row in appends] == [6, 7]
            and plane.host.plane.images == 8,
            "two-helper persistent append state drift",
        )

    data = media.read_bytes()
    if library_media:
        locators, payloads = R.media_locators(data)
        index_rows = L65I.decode_index(
            payloads["l65index"],
            {
                "place": payloads["place"],
                "defstruct": payloads["defstruct"],
            },
            artifact_build_id=geometry()["build_id"],
        )
    else:
        locators = {}
        index_rows = []
    before_rows = persistent_rows(plane)
    index_identities = {
        row["combined_crc32"]: row["name"]
        for row in index_rows
    }
    vm = R.ResolverVM(bound, plane, data, locators)
    trace = ResolverTrace()
    vm.trace = trace
    result = vm.run(
        bound.directory[bound.require_symbol],
        [bound.heap.intern("place")],
    )
    return {
        "label": label,
        "prior_persistent_appends": len(appends),
        "prior_append_entries": [row["entry"] for row in appends],
        "prior_append_details": [
            {
                "entry": row["entry"],
                "image_slot": row["image_slot"],
                "code_bytes": row["compiler_code"]["bytes"],
                "compiler_steps": row["compiler_steps"],
                "code_sha256": row["code"]["encoded_sha256"],
            }
            for row in appends
        ],
        "pre_require_active_rows": [
            {
                **row,
                "index_match": index_identities.get(row["combined_crc32"]),
            }
            for row in before_rows
        ],
        "index_rows": [
            {
                "name": row["name"],
                "combined_crc32": row["combined_crc32"],
                "track": row["track"],
                "sector": row["sector"],
            }
            for row in index_rows
        ],
        "result": bound.heap.obj_to_text(result),
        "steps": vm.steps,
        "disk_sector_reads": vm.io_counters["disk_read"],
        "prim67_reads": len(vm.prim67_reads),
        "resolver_trace": {
            name: trace.entries[name]
            for name in (
                "%require-world",
                "%require-active-prefix",
                "%require-index-row-for-image",
                "%disk-load-lib",
                "%require-load-plan",
            )
            if trace.entries[name]
        },
        "loader_attempts": list(vm.loader_attempts),
        "published_appends": list(plane.appends),
        "final_counts": {
            "images": plane.host.plane.images,
            "entries": plane.host.plane.entries,
            "resolutions": plane.host.plane.resolutions,
            "roots": plane.host.plane.roots,
            "code_bytes": plane.host.plane.code_low,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    args = parser.parse_args()
    try:
        geom = configure_v124()
        product_inventory = sorted(visible_files(PRODUCT_D81))
        require(
            not set(("l65index", "place", "defstruct"))
                & set(product_inventory),
            "released product D81 unexpectedly contains require media",
        )
        library_d81, library = build_library_media(geom["build_id"])
        cases = [
            run_case(
                label="product-media-no-prior-appends",
                media=PRODUCT_D81,
                library_media=False,
                prior_helpers=False,
            ),
            run_case(
                label="product-media-two-prior-appends",
                media=PRODUCT_D81,
                library_media=False,
                prior_helpers=True,
            ),
            run_case(
                label="library-media-no-prior-appends",
                media=library_d81,
                library_media=True,
                prior_helpers=False,
            ),
            run_case(
                label="library-media-two-prior-appends",
                media=library_d81,
                library_media=True,
                prior_helpers=True,
            ),
        ]
        results = {row["label"]: row["result"] for row in cases}
        require(
            results == {
                "product-media-no-prior-appends": "nil",
                "product-media-two-prior-appends": "nil",
                "library-media-no-prior-appends": "t",
                "library-media-two-prior-appends": "nil",
            },
            f"H1 result matrix drift: {results}",
        )
        require(
            len(cases[2]["published_appends"]) == 1
            and cases[2]["published_appends"][0]["image_slot"] == 6
            and not cases[3]["loader_attempts"]
            and not cases[3]["published_appends"]
            and len(cases[3]["pre_require_active_rows"]) == 2
            and all(
                row["index_match"] is None
                for row in cases[3]["pre_require_active_rows"]
            ),
            "H1 did not fail at the foreign persistent active universe",
        )
        value = {
            "format": FORMAT,
            "recorded_on": date.today().isoformat(),
            "status": "H1-confirmed-mechanism-attributed-host-only",
            "promotable": False,
            "product_delta_bytes": 0,
            "product_links": 0,
            "hardware_runs": 0,
            "H1_matrix": cases,
            "attribution": {
                "prior_persistent_appends_discriminant": "confirmed-on-host",
                "mechanism": (
                    "%require-world calls %require-active-prefix over every "
                    "persistent C2D image row. %require-active-prefix requires "
                    "each row identity to occur in L65INDEX. The ordinary "
                    "%s/%sr Session appends occupy slots 6/7 but are not "
                    "library-index rows, so %require-index-row-for-image "
                    "returns NIL at slot 6, the world proof returns NIL, and "
                    "the disk loader is never invoked."
                ),
                "contract_defect": (
                    "The active-universe rule treats all source-kind-1 "
                    "persistent Session rows as package identities. C2D-v6 "
                    "does not distinguish an ordinary user definition from "
                    "a dynamically loaded package row, so the strict "
                    "foreign-identity rejection makes require order-dependent."
                ),
                "failed_seam": "resolver-selection/world-proof-before-media-stage",
                "media_stage_attempted": False,
                "stage_authentication_attempted": False,
                "append_entry_attempted": False,
                "four_seam_mapping_required": False,
                "soak_harness_independent_defect": (
                    "The soak mounted only the released product D81, whose "
                    "directory has no L65INDEX, PLACE or DEFSTRUCT. Its NIL "
                    "therefore cannot count as a product second sighting."
                ),
                "second_product_sighting": False,
                "Link80_original_sighting": (
                    "attributed: Link80 used product-bound library media after "
                    "prior persistent definitions, matching the confirmed H1"
                ),
            },
            "released_product_media": {
                "binding": bind(PRODUCT_D81),
                "mount_descriptor": bind(PRODUCT_MOUNT),
                "visible_files": product_inventory,
                "required_library_files_absent": [
                    "l65index", "place", "defstruct"
                ],
            },
            "generated_library_media": library,
            "authority": {
                "stdlib": bind(STDLIB),
                "static_c2d": bind(STATIC_C2D),
                "static_bank2": bind(STATIC_CODE),
                "soak_config": bind(SOAK_CONFIG),
                "base_library_media": bind(BASE_LIBRARY_D81),
                "compiler_carrier": bind(COMPILER_CARRIER),
                "compiler_tier": bind(COMPILER_TIER),
                "require_source": bind(REQUIRE_SOURCE),
                "require_contract": bind(REQUIRE_CONTRACT),
                "soak_hardware_receipt": bind(SOAK_HARDWARE_RECEIPT),
                "Link80_hardware_receipt": bind(LINK80_HARDWARE_RECEIPT),
                "driver": bind(Path(__file__).resolve()),
            },
            "target_model_corrections": {
                "transient_high_watermark": (
                    "The generic Session host resets header bytes 8..9; "
                    "the target republishes 4096 after every persistent "
                    "append. The fixture restores 4096 before require."
                ),
                "source_slot": (
                    "The generic Session host has no source-slot counter; "
                    "the target publishes source_slot=image_slot-6. The "
                    "fixture restores 0 and 1 for slots 6 and 7."
                ),
            },
            "harness_correction": {
                "soak_media_binding": (
                    "config/c2-v124-post-release-soak.json bound and mounted "
                    "15-lisp65-product.d81 only"
                ),
                "missing_precondition": (
                    "The harness never proved that the mounted medium "
                    "contained L65INDEX and the requested package before "
                    "calling require."
                ),
                "required_permanent_gate": (
                    "Any require hardware fixture must inventory the mounted "
                    "D81 and bind L65INDEX plus each requested L65S artifact "
                    "before a product result is claimed."
                ),
            },
            "claim_limit": (
                "The exact v1.2.4 bound Lisp resolver and canonical "
                "persistent-append model run on the host. Physical DMA, "
                "45GS02 ABI and hardware are not executed. The matrix "
                "attributes the resolver's deterministic rejection after "
                "ordinary persistent appends and explains the original "
                "Link80 library-media NIL. It separately disqualifies the "
                "post-release soak NIL because that harness lacked require "
                "media."
            ),
        }
        write_json(args.receipt, value)
        print(
            "c2-v124-require-prior-append-h1: PASS "
            "product-media=nil/nil library-media=t/nil "
            "H1=confirmed seam=resolver-world-proof"
        )
        return 0
    except (H1Error, R.ResolverError, L65I.GateError, B.VMError,
            KeyError, ValueError) as error:
        print(
            "c2-v124-require-prior-append-h1: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
