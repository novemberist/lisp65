#!/usr/bin/env python3
"""Prove the Option-A require contract after ordinary Session appends.

This successor gate preserves the v1.2.4 H1 receipt as the historical First
Red, compiles the current resolver, appends the exact two soak helpers through
the real compiler/emitter/Session-host path, and then executes ``require``
against product-identity-bound package media.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import struct
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import c2_link75_real_require_resolver_host as R  # noqa: E402
import c2_defstruct_foundations_gate as FOUNDATION  # noqa: E402
import c2_require_resolver_gate as RESOLVER  # noqa: E402
import c2_v124_require_prior_append_h1 as H1  # noqa: E402


SOURCE_GATE = ROOT / "tools/host-lisp/c2_require_resolver_gate.py"
FRESH_STDLIB = ROOT / (
    "build/post-promotion/require-resolver/l65i-v1/stdlib-p0.manifest.json")
H1_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/post-release/"
    "post-v124-require-prior-append-h1-receipt-20260730.json")
CONTRACT = ROOT / "config/c2-require-resolver-contract.json"
ACCEPTANCE = ROOT / "config/c2-require-prior-append-acceptance.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-require-prior-append-option-A-host-gate-receipt.json")
FORMAT = "lisp65-c2-require-prior-append-option-A-host-gate-v1"
PROFILE = ROOT / "config/c2-l-full-product-profile.json"
FIXTURE = ROOT / "build/post-promotion/require-option-A-fresh-fixtures"
PLACE_MANIFEST = FIXTURE / "place.manifest.json"
DEFSTRUCT_MANIFEST = FIXTURE / "defstruct.manifest.json"
CURRENT_COMPILER_CARRIER = (
    FIXTURE / "compiler/lcc.manifest.json")
CURRENT_COMPILER_TIER = (
    FIXTURE / "compiler/tier-generation.json")
CURRENT_COMPILER_SUITE = FIXTURE / "compiler/p0-c2-compiler-tier.json"


class OptionAError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise OptionAError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_source_gate() -> str:
    result = subprocess.run(
        [sys.executable, str(SOURCE_GATE.relative_to(ROOT))],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    require(
        result.returncode == 0
        and "c2-require-resolver-gate: PASS" in result.stdout,
        f"resolver source gate red:\n{result.stdout}",
    )
    require(FRESH_STDLIB.is_file(), "fresh resolver manifest absent")
    return result.stdout.strip().splitlines()[-1]


def run_fixture(command: list[str], label: str) -> str:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout.strip().splitlines()[-1]


def prepare_source_fixtures() -> dict[str, str]:
    FIXTURE.mkdir(parents=True, exist_ok=True)
    compiler = run_fixture(
        [
            sys.executable,
            "tools/host-lisp/c2_product_compiler_tier.py",
            "--out",
            CURRENT_COMPILER_SUITE.relative_to(ROOT).as_posix(),
            "--receipt",
            CURRENT_COMPILER_TIER.relative_to(ROOT).as_posix(),
        ],
        "current C2 compiler tier",
    )
    carrier = run_fixture(
        [
            sys.executable,
            "tools/host-lisp/bytecode_p0_stdlib.py",
            "--check",
            "--emit-artifacts",
            (FIXTURE / "compiler/lcc").relative_to(ROOT).as_posix(),
            "--artifact-role",
            "disk-lib",
            "--base-addr",
            "0x000000",
            CURRENT_COMPILER_SUITE.relative_to(ROOT).as_posix(),
        ],
        "current C2 compiler carrier",
    )
    libraries = {}
    for name, suite in (
        ("place", ROOT / "tests/bytecode/libs/p0-place-lib.json"),
        ("defstruct", ROOT / "tests/bytecode/libs/p0-defstruct-v1-lib.json"),
    ):
        libraries[name] = run_fixture(
            [
                sys.executable,
                "tools/host-lisp/bytecode_p0_stdlib.py",
                "--check",
                "--emit-artifacts",
                (FIXTURE / name).relative_to(ROOT).as_posix(),
                "--artifact-role",
                "disk-lib",
                "--base-addr",
                "0x000000",
                suite.relative_to(ROOT).as_posix(),
            ],
            f"current {name} library",
        )
    return {
        "compiler_tier": compiler,
        "compiler_carrier": carrier,
        **libraries,
    }


def current_geometry() -> dict[str, int]:
    profile = load(PROFILE)
    code = profile["bank2_static_code"]
    geometry = {
        "generation": 1,
        "images": int(profile["images"]),
        "entries": int(profile["entries"]),
        "resolutions": int(profile["resolutions"]),
        "roots": int(profile["roots"]),
        "code_bytes": int(code["bytes"]),
        "immutable_images": int(profile["images"]),
        # The Option-A host lane never consumes catalog identity.  Keep this
        # model-only field inert instead of importing an ignored linked C2D.
        "catalog_crc32": 0,
        "build_id": int(profile["product_build_id"], 0),
    }
    require(
        geometry == {
            "generation": 1,
            "images": 6,
            "entries": 753,
            "resolutions": 2920,
            "roots": 350,
            "code_bytes": 45939,
            "immutable_images": 6,
            "catalog_crc32": 0,
            "build_id": 0x14D980C3,
        },
        "current profile geometry drift",
    )
    return geometry


def seed_static_rows(plane: Any, geometry: dict[str, int]) -> None:
    """Materialize the resolver-visible immutable prefix without old builds.

    The Option-A class closer executes the real resolver over rows 6 onward.
    The immutable prefix contributes only its authenticated contiguous Bank-2
    edge.  Six deterministic non-empty rows therefore model exactly that
    consumed contract while leaving product identity to WPLTO and hardware.
    """
    sizes = [1, 1, 1, 1, 1, geometry["code_bytes"] - 5]
    code_base = 0
    for slot, size in enumerate(sizes):
        at = R.V6.C2D_IMAGES_OFFSET + 32 * slot
        plane.c2d[at] = 0
        plane.c2d[at + 2] = slot
        struct.pack_into("<H", plane.c2d, at + 4, geometry["generation"])
        struct.pack_into("<H", plane.c2d, at + 18, code_base)
        plane.c2d[at + 20] = 0
        struct.pack_into("<H", plane.c2d, at + 21, size)
        code_base += size
    require(code_base == geometry["code_bytes"], "static row edge drift")


class CurrentLivePlane(R.LivePlane):
    """Source-reproducible target-shaped plane for the Option-A host lane."""

    def __init__(self, *, mutation: str = "none") -> None:
        geometry = current_geometry()
        self.host = R.SESSION.ProductSessionHost(geometry, FIXTURE / "session")
        seed_static_rows(self.host.plane, geometry)
        struct.pack_into("<H", self.host.plane.c2d, 8, R.HANDLE_CAP)
        self.images = {
            name: R.F.emit_image(
                name,
                "dfstrct" if name == "defstruct" else name,
                manifest,
            )
            for name, manifest in (
                ("place", PLACE_MANIFEST),
                ("defstruct", DEFSTRUCT_MANIFEST),
            )
        }
        self.mutation = mutation
        self.appends: list[dict[str, Any]] = []


def helper_forms() -> list[tuple[str, str]]:
    acceptance = load(ACCEPTANCE)
    rows = {row["id"]: row for row in acceptance["rows"]}
    return [
        (rows["ordinary-append-0"]["form"], "%ra"),
        (rows["ordinary-append-1"]["form"], "%rb"),
    ]


def append_helpers(plane: CurrentLivePlane) -> list[dict[str, Any]]:
    H1.CARRIER.CARRIER = CURRENT_COMPILER_CARRIER
    H1.CARRIER.TIER = CURRENT_COMPILER_TIER
    compiler = H1.CARRIER.BoundCarrierCompiler()
    H1.CARRIER.attach_heap(plane.host, compiler.heap)
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
            compiler_authority=H1.bind(CURRENT_COMPILER_CARRIER)["sha256"],
        )
        row_at = 48 + append["image_slot"] * 32
        plane.host.plane.c2d[row_at + 2] = append["image_slot"] - 6
        struct.pack_into("<H", plane.host.plane.c2d, 8, R.HANDLE_CAP)
        append["compiler_steps"] = compiled["steps"]
        append["code"] = compiled["summary"]
        rows.append(append)
    return rows


def run_case(
    *,
    label: str,
    media: Path,
    prior_helpers: bool,
) -> dict[str, Any]:
    bound = R.BoundStdlib()
    plane = CurrentLivePlane()
    appends = append_helpers(plane) if prior_helpers else []
    require(
        not prior_helpers
        or (
            [row["entry"] for row in appends] == ["%ra", "%rb"]
            and [row["image_slot"] for row in appends] == [6, 7]
            and plane.host.plane.images == 8
        ),
        "two-helper persistent append state drift",
    )
    data = media.read_bytes()
    locators, payloads = R.media_locators(data)
    index_rows = RESOLVER.decode_index(
        payloads["l65index"],
        {"place": payloads["place"], "defstruct": payloads["defstruct"]},
        artifact_build_id=current_geometry()["build_id"],
    )
    before_rows = H1.persistent_rows(plane)
    identities = {
        row["combined_crc32"]: row["name"] for row in index_rows
    }
    vm = R.ResolverVM(bound, plane, data, locators)
    trace = H1.ResolverTrace()
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
            {**row, "index_match": identities.get(row["combined_crc32"])}
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


def build_library_media(
    build_id: int,
) -> tuple[Path, dict[str, Any]]:
    manifests = (
        ("place", "place", "place", PLACE_MANIFEST, ()),
        ("defstruct", "defstruct", "dfstrct", DEFSTRUCT_MANIFEST, (0,)),
    )
    placeholder: list[dict[str, Any]] = []
    artifacts: dict[str, bytes] = {}
    paths: list[tuple[Path, str]] = []
    for number, (name, image, shelf, manifest, dependencies) in enumerate(
        manifests
    ):
        row, artifact = FOUNDATION.measured_row(
            name,
            image,
            shelf,
            manifest,
            dependencies,
            1,
            number + 1,
            product_build_id=build_id,
        )
        placeholder.append(row)
        artifacts[name] = artifact
        path = FIXTURE / f"{name}.l65s"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(artifact)
        paths.append((path, name))
    seed_index = FIXTURE / "l65index.seed"
    seed_index.write_bytes(RESOLVER.encode_index(placeholder))
    seed = FIXTURE / "require-place.seed.d81"
    RESOLVER.build_d81(seed, seed_index, paths)
    locators = RESOLVER.d81_locators(seed)
    rows: list[dict[str, Any]] = []
    for name, image, shelf, manifest, dependencies in manifests:
        row, artifact = FOUNDATION.measured_row(
            name,
            image,
            shelf,
            manifest,
            dependencies,
            *locators[name],
            product_build_id=build_id,
        )
        require(artifact == artifacts[name], f"artifact drift: {name}")
        rows.append(row)
    index = RESOLVER.encode_index(rows)
    index_path = FIXTURE / "l65index"
    index_path.write_bytes(index)
    medium = FIXTURE / "require-place-current-bound.d81"
    RESOLVER.build_d81(medium, index_path, paths)
    require(
        RESOLVER.d81_locators(medium) == locators,
        "library-media locator drift",
    )
    decoded = RESOLVER.decode_index(
        index, artifacts, artifact_build_id=build_id)
    require(
        RESOLVER.resolve(decoded, "place", 7, [], RESOLVER.CAPACITY) == [0],
        "source-built place resolution drift",
    )
    mutations = RESOLVER.mutation_gate(
        index, artifacts, artifact_build_id=build_id)
    return medium, {
        "D81": H1.bind(medium),
        "index": H1.bind(index_path),
        "place": H1.bind(FIXTURE / "place.l65s"),
        "defstruct": H1.bind(FIXTURE / "defstruct.l65s"),
        "product_build_id": f"0x{build_id:08x}",
        "locators": {
            name: list(locator)
            for name, locator in sorted(locators.items())
        },
        "source_rebuilt": True,
        "index_mutations_rejected": len(mutations),
    }


def configure_current() -> tuple[dict[str, int], Path, dict[str, Any]]:
    geometry = current_geometry()
    R.STDLIB = FRESH_STDLIB
    medium, media_receipt = build_library_media(geometry["build_id"])
    return geometry, medium, media_receipt


def execute_mutation(
    medium: Path,
    mutation: str,
    place_identity: int,
) -> dict[str, Any]:
    bound = R.BoundStdlib()
    plane = CurrentLivePlane()
    appends = append_helpers(plane)
    require(len(appends) == 2, "mutation lane lacks two helper appends")
    row_at = 48 + 6 * 32
    if mutation == "source-slot":
        plane.data[row_at + 2] ^= 1
    elif mutation == "generation":
        plane.data[row_at + 4] ^= 1
    elif mutation == "code-base":
        plane.data[row_at + 18] ^= 1
    elif mutation == "zero-code-size":
        plane.data[row_at + 21:row_at + 23] = bytes(2)
    elif mutation == "indexed-identity-wrong-size":
        struct.pack_into("<I", plane.data, row_at + 28, place_identity)
    else:
        raise OptionAError(f"unknown mutation: {mutation}")

    media = medium.read_bytes()
    locators, _payloads = R.media_locators(media)
    vm = R.ResolverVM(bound, plane, media, locators)
    result = vm.run(
        bound.directory[bound.require_symbol],
        [bound.heap.intern("place")],
    )
    return {
        "result": bound.heap.obj_to_text(result),
        "steps": vm.steps,
        "loader_attempts": list(vm.loader_attempts),
        "published_appends": list(plane.appends),
    }


def main() -> int:
    try:
        source_summary = run_source_gate()
        fixture_summaries = prepare_source_fixtures()
        geometry, medium, media_receipt = configure_current()
        baseline = run_case(
            label="library-media-no-prior-appends",
            media=medium,
            prior_helpers=False,
        )
        successor = run_case(
            label="library-media-two-prior-appends",
            media=medium,
            prior_helpers=True,
        )
        require(
            baseline["result"] == successor["result"] == "t",
            "Option-A successor did not remove append-order dependence",
        )
        require(
            len(baseline["loader_attempts"]) == 1
            and len(successor["loader_attempts"]) == 1
            and baseline["loader_attempts"][0]["library"] == "place"
            and successor["loader_attempts"][0]["library"] == "place",
            "successor did not reach the exact package loader once",
        )
        require(
            len(successor["pre_require_active_rows"]) == 2
            and all(
                row["index_match"] is None
                for row in successor["pre_require_active_rows"]
            ),
            "successor lane does not contain two ordinary non-index rows",
        )

        payloads = H1.visible_files(medium)
        index = RESOLVER.decode_index(
            payloads["l65index"],
            {"place": payloads["place"], "defstruct": payloads["defstruct"]},
            artifact_build_id=geometry["build_id"],
        )
        place_identity = next(
            row["combined_crc32"] for row in index if row["name"] == "place")
        mutations: dict[str, Any] = {}
        for mutation in (
            "source-slot",
            "generation",
            "code-base",
            "zero-code-size",
            "indexed-identity-wrong-size",
        ):
            row = execute_mutation(medium, mutation, place_identity)
            require(
                row["result"] == "nil"
                and not row["loader_attempts"]
                and not row["published_appends"],
                f"Option-A geometry mutation survived: {mutation}",
            )
            mutations[mutation] = row

        public_build = (
            os.environ.get("LISP65_PUBLIC_CURRENT_SOURCE_BUILD") == "1"
        )
        historical_binding: dict[str, Any] | None = None
        if public_build:
            historical_result = "not-claimed-by-public-build"
        else:
            historical = load(H1_RECEIPT)
            historical_cases = {
                row["label"]: row for row in historical["H1_matrix"]
            }
            require(
                historical_cases[
                    "library-media-two-prior-appends"]["result"] == "nil",
                "historical H1 First Red no longer binds the rejected state",
            )
            historical_result = "nil"
            historical_binding = H1.bind(H1_RECEIPT)
        acceptance = load(ACCEPTANCE)
        require(
            acceptance["status"]
                == "required-in-next-v1.2.5-acceptance-session"
            and len(acceptance["rows"]) == 4,
            "acceptance class-closer drift",
        )
        value = {
            "format": FORMAT,
            "recorded_on": acceptance["recorded_on"],
            "status":
                "passed-option-A-require-after-two-ordinary-appends-host-lane",
            "execution_witness": {
                "cases_executed": 2,
                "mutations_executed": len(mutations),
                "baseline": baseline,
                "two_prior_appends": successor,
                "mutations_rejected": mutations,
            },
            "semantic_delta": {
                "historical_result_after_two_appends": historical_result,
                "successor_result_after_two_appends": "t",
                "ordinary_rows": "geometry-checked-but-not-package-classified",
                "indexed_rows":
                    "geometry-plus-indexed-size-identity-and-duplicate-checked",
                "format_change": False,
                "resident_delta_claim": "none-host-gate-only",
            },
            "library_media": media_receipt,
            "source_reproducible_fixture": {
                "profile_geometry": H1.bind(PROFILE),
                "static_prefix":
                    "six deterministic contiguous rows; resolver-consumed "
                    "shape only; linked identity remains a WPLTO/hardware claim",
                "place_manifest": H1.bind(PLACE_MANIFEST),
                "defstruct_manifest": H1.bind(DEFSTRUCT_MANIFEST),
                "compiler_carrier": H1.bind(CURRENT_COMPILER_CARRIER),
                "compiler_tier": H1.bind(CURRENT_COMPILER_TIER),
                "ignored_predecessor_build_inputs": 0,
            },
            "source_gate": source_summary,
            "source_fixture_builds": fixture_summaries,
            "authority": {
                "fresh_stdlib": H1.bind(FRESH_STDLIB),
                "contract": H1.bind(CONTRACT),
                "acceptance": H1.bind(ACCEPTANCE),
                "driver": H1.bind(Path(__file__).resolve()),
                "private_evidence_inputs": (
                    0 if public_build else 1
                ),
            },
            "claim_limit": (
                "The current compiled Lisp resolver executes against the exact "
                "current profile geometry, real compiler-carrier helper "
                "appends and source-built package media in the target-shaped "
                "host VM. Physical DMA, 45GS02 ABI and hardware are not "
                "claimed; the separate acceptance row remains mandatory."
            ),
        }
        if historical_binding is not None:
            value["authority"]["historical_H1"] = historical_binding
        write_json(RECEIPT, value)
        print(
            "c2-require-prior-append-option-A-gate: PASS "
            "baseline=t two-appends=t mutations=5 executions=7"
        )
        return 0
    except (
        OSError,
        KeyError,
        ValueError,
        OptionAError,
        H1.H1Error,
        R.ResolverError,
        RESOLVER.GateError,
        B.VMError,
    ) as error:
        print(
            "c2-require-prior-append-option-A-gate: FIRST RED: "
            + str(error),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
