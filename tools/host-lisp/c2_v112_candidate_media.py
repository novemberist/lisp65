#!/usr/bin/env python3
"""Close the two v1.4.0 Link-92 media variants over one r5 core."""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_defstruct_foundations_gate as FOUNDATION  # noqa: E402
import c2_lite_canonical_product as CAN  # noqa: E402
import c2_lite_media_product as MEDIA  # noqa: E402
import c2_require_resolver_gate as L65I  # noqa: E402
import c2_v112_candidate_product as PRODUCT  # noqa: E402


BUILD = ROOT / "build/c2.3/v1.4.0-candidate-media-link92-r5"
SHARED = BUILD / "shared-system"
BASE = BUILD / "base"
D2 = BUILD / "defstruct-acceptance"
MANIFEST = BUILD / "candidate-manifest.json"
BASE_MANIFEST = BUILD / "base-candidate-manifest.json"
D2_MANIFEST = BUILD / "defstruct-acceptance-manifest.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-link92-r5-two-variant-media-receipt.json"
)
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-link92-r5-base-index-mutation-cardinality-first-red.json"
)
SECOND_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-link92-r5-sibling-resolver-order-first-red.json"
)
PRODUCT_MANIFEST = PRODUCT.MANIFEST
COMFORT_MANIFEST = ROOT / "build/post-promotion/v112/comfort/comfort.manifest.json"
DEFSTRUCT_MANIFEST = ROOT / (
    "build/post-promotion/v110-performance/defstruct-candidate.manifest.json"
)
VARIANTS = {
    "base": (("comfort", "comfort", "comfort", COMFORT_MANIFEST, ()),),
    "defstruct": (
        ("comfort", "comfort", "comfort", COMFORT_MANIFEST, ()),
        ("defstruct", "defstruct", "dfstrct", DEFSTRUCT_MANIFEST, ()),
    ),
}
_CONFIGURE_SHARED_CALLS = 0
_HARNESS_DOUBLE_CONFIG_ERROR = "candidate media harness double configuration"


class MediaClosureError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise MediaClosureError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(raw),
        "sha256": sha(raw),
    }


def configure_shared() -> None:
    global _CONFIGURE_SHARED_CALLS
    require(_CONFIGURE_SHARED_CALLS == 0, _HARNESS_DOUBLE_CONFIG_ERROR)
    _CONFIGURE_SHARED_CALLS += 1
    PRODUCT.configure()
    CAN.MANIFEST = PRODUCT_MANIFEST
    MEDIA.CANONICAL = CAN
    MEDIA.BUILD = SHARED
    MEDIA.PRODUCT_MANIFEST = PRODUCT_MANIFEST
    MEDIA.MANIFEST = SHARED / "candidate-manifest.json"
    MEDIA.DESCRIPTOR = SHARED / "boot.id"
    MEDIA.STAGER = SHARED / "autoboot.c65"
    MEDIA.STAGER_MAP = SHARED / "autoboot.c65.map"
    MEDIA.PRODUCT_D81 = SHARED / "lisp65-product.d81"
    MEDIA.WORK_D81 = SHARED / "lisp65-work.d81"
    MEDIA.MOUNT = SHARED / "lisp65-product.mount.json"


def configuration_lifecycle_gate(
    source_override: str | None = None,
) -> dict[str, Any]:
    source = source_override or Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    configure = functions.get("configure_shared")
    fresh = functions.get("fresh_readback")
    check_function = functions.get("check")
    main = functions.get("main")
    require(configure is not None and fresh is not None
            and check_function is not None and main is not None,
            "media configuration/readback lifecycle entrypoint absent")
    configure_text = ast.unparse(configure)
    fresh_text = ast.unparse(fresh)
    check_calls = [
        ast.unparse(node.func) for node in ast.walk(check_function)
        if isinstance(node, ast.Call)
    ]
    main_text = ast.unparse(main)
    guard = "require(_CONFIGURE_SHARED_CALLS == 0, _HARNESS_DOUBLE_CONFIG_ERROR)"
    increment = "_CONFIGURE_SHARED_CALLS += 1"
    product = "PRODUCT.configure()"
    require(
        guard in configure_text
        and increment in configure_text
        and product in configure_text
        and configure_text.index(guard) < configure_text.index(increment)
        < configure_text.index(product)
        and "subprocess.run" in fresh_text
        and "'check'" in fresh_text
        and "check()" not in fresh_text
        and not any(call.endswith(("write_bytes", "write_text", "unlink", "mkdir"))
                    or call in {"build", "resume", "close_variants"}
                    for call in check_calls)
        and "value = resume()" in main_text
        and "fresh_readback()" in main_text,
        "media readback can double-configure or bypass its fresh process",
    )
    return {
        "status": "passed-one-configuration-per-process-fresh-readback",
        "harness_guard_precedes_product_selector": True,
        "readback_processes": 1,
        "in_process_readback_calls": 0,
        "readback_writes": 0,
    }


def resume_source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = source_override or Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    resume = functions.get("resume")
    require(resume is not None, "media resume entrypoint absent")
    calls = [
        ast.unparse(node) for node in ast.walk(resume)
        if isinstance(node, ast.Call)
    ]
    require(
        not any(call.startswith("MEDIA.build(") for call in calls)
        and not any(call.startswith("build_library_variant(") for call in calls)
        and sum(call.startswith("existing_media_preflight(") for call in calls) == 2
        and sum(call.startswith("existing_library_variant('base'")
                or call.startswith('existing_library_variant("base"')
                for call in calls) == 1
        and sum(call.startswith("existing_library_variant('defstruct'")
                or call.startswith('existing_library_variant("defstruct"')
                for call in calls) == 1,
        "resume path can rebuild a SHA-fixed medium or omit its identity checks",
    )
    return {
        "status": "passed-resume-only-defstruct-sibling-and-aggregates",
        "shared_system_rebuilds": 0,
        "base_library_rebuilds": 0,
        "defstruct_sibling_builds": 0,
        "existing_identity_checks": 2,
    }


def existing_media_preflight() -> dict[str, Any]:
    first_red = load(FIRST_RED)
    second_red = load(SECOND_RED)
    require(
        first_red.get("status")
            == "FIRST RED-attributed-one-row-base-index-versus-two-row-mutation-assumption"
        and first_red.get("disposition", {}).get("state")
            == "owner-disposition-required",
        "media resume lacks its cardinality First-Red authority",
    )
    require(
        second_red.get("status")
            == "FIRST RED-attributed-independent-library-rows-versus-prefix-resolver-assumption"
        and second_red.get("disposition", {}).get("state")
            == "owner-disposition-required",
        "media resume lacks its resolver-order First-Red authority",
    )
    expected = first_red["completed_before_red"]
    second_expected = second_red["completed_before_red"]
    shared = expected["shared_system_media"]
    base = expected["base_library_before_gate"]
    actual = {
        "shared_manifest": bind(MEDIA.MANIFEST),
        "shared_product_D81": bind(MEDIA.PRODUCT_D81),
        "shared_work_D81": bind(MEDIA.WORK_D81),
        "base_D81": bind(BASE / "lisp65-library.d81"),
        "base_index": bind(BASE / "l65index"),
        "base_comfort": bind(BASE / "comfort.l65s"),
        "defstruct_D81": bind(D2 / "lisp65-library.d81"),
        "defstruct_index": bind(D2 / "l65index"),
        "defstruct_comfort": bind(D2 / "comfort.l65s"),
        "defstruct_artifact": bind(D2 / "defstruct.l65s"),
    }
    require(
        actual["shared_manifest"] == shared["manifest"]
        and actual["shared_product_D81"] == shared["product_D81"]
        and actual["shared_work_D81"] == shared["work_D81"]
        and actual["base_D81"] == base["D81"]
        and actual["base_index"] == base["index"]
        and actual["base_comfort"] == base["comfort"],
        "SHA-fixed shared-system/base media drift",
    )
    sibling = second_expected["defstruct_sibling_before_gate"]
    require(
        actual["defstruct_D81"] == sibling["D81"]
        and actual["defstruct_index"] == sibling["index"]
        and actual["defstruct_comfort"] == sibling["comfort"]
        and actual["defstruct_artifact"] == sibling["defstruct"],
        "SHA-fixed defstruct sibling media drift",
    )
    return actual


def product_build_id() -> int:
    product = load(PRODUCT_MANIFEST)
    value = int(product["static_plane"]["product_build_id"], 0)
    roles = {row["role"]: row for row in product["artifacts"]}
    c2d = (ROOT / roles["c2d-v6-code-plane"]["path"]).read_bytes()
    require(
        len(c2d) == MEDIA.C2D_PREFIX_BYTES
        and int.from_bytes(c2d[44:48], "little") == value,
        "Link-92 manifest/C2D product identity drift",
    )
    return value


def measured(
    spec: tuple[str, str, str, Path, tuple[int, ...]],
    locator: tuple[int, int], build_id: int,
) -> tuple[dict[str, Any], bytes]:
    name, image, shelf, manifest, dependencies = spec
    row, artifact = FOUNDATION.measured_row(
        name, image, shelf, manifest, dependencies, *locator,
        product_build_id=build_id,
    )
    L65I.S.decode_extension(artifact, expected_build_id=build_id)
    require(artifact[32:40] == L65I.S.SESSION_RECORD_ID,
            f"{name} lacks the product-bound SESS identity")
    return row, artifact


def build_library_d81(
    output: Path, index: Path, artifacts: list[tuple[Path, str]],
) -> None:
    c1541 = shutil.which("c1541")
    require(c1541 is not None, "c1541 is unavailable")
    # Comfort precedes the index in both variants.  Its locator and index row
    # therefore stay byteidentical when the conditional defstruct row is added.
    command = [c1541, "-format", "L65LIB,65", "d81", str(output)]
    command += ["-write", str(artifacts[0][0]), artifacts[0][1]]
    command += ["-write", str(index), "l65index"]
    for artifact, name in artifacts[1:]:
        command += ["-write", str(artifact), name]
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False,
    )
    require(result.returncode == 0, f"c1541 failed: {result.stdout}")


def declared_dependency_closure(
    rows: list[dict[str, Any]], name: str,
) -> list[int]:
    matches = [ordinal for ordinal, row in enumerate(rows)
               if row["name"] == name]
    require(len(matches) == 1, "resolver-contract requested identity drift")
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
    return order


def resolver_contract(
    rows: list[dict[str, Any]], name: str, *,
    expected_override: list[int] | None = None,
    actual_override: list[int] | None = None,
) -> dict[str, Any]:
    declared = declared_dependency_closure(rows, name)
    expected = declared if expected_override is None else expected_override
    actual = (L65I.resolve(rows, name, 7, [], L65I.CAPACITY)
              if actual_override is None else actual_override)
    require(
        expected == declared,
        "resolver expectation contains undeclared or misses declared rows",
    )
    require(actual == expected, "resolver returned less or more than closure")
    return {
        "requested": name,
        "declared_dependency_closure": declared,
        "actual_resolver_order": actual,
    }


def resolver_contract_mutation_gate(
    rows: list[dict[str, Any]], name: str,
) -> dict[str, str]:
    require(len(rows) >= 2, "resolver contract mutations need two rows")
    declared = declared_dependency_closure(rows, name)
    undeclared = next(
        (ordinal for ordinal in range(len(rows)) if ordinal not in declared),
        None,
    )
    require(undeclared is not None, "resolver over-closure mutation unavailable")
    rejected_mutations: dict[str, str] = {}

    def reject(label: str, action: Callable[[], Any]) -> None:
        try:
            action()
        except MediaClosureError as error:
            rejected_mutations[label] = str(error)
        else:
            raise MediaClosureError(
                f"resolver-contract mutation survived: {label}")

    reject(
        "undeclared-prefix-row-required",
        lambda: resolver_contract(
            rows, name, expected_override=[undeclared, *declared]),
    )
    target = next(ordinal for ordinal, row in enumerate(rows)
                  if row["name"] == name)
    dependency_rows = deepcopy(rows)
    dependency_rows[target]["dependencies"] = [undeclared]
    reject(
        "declared-dependency-omitted-by-resolver",
        lambda: resolver_contract(
            dependency_rows, name, actual_override=[target]),
    )
    require(len(rejected_mutations) == 2,
            "resolver-contract mutation count drift")
    return rejected_mutations


def build_library_variant(
    name: str, output: Path, build_id: int,
) -> dict[str, Any]:
    specs = VARIANTS[name]
    output.mkdir(parents=True)
    placeholder: list[dict[str, Any]] = []
    artifacts: dict[str, bytes] = {}
    paths: list[tuple[Path, str]] = []
    for ordinal, spec in enumerate(specs):
        row, artifact = measured(spec, (1, ordinal + 1), build_id)
        public_name = spec[0]
        placeholder.append(row)
        artifacts[public_name] = artifact
        path = output / f"{public_name}.l65s"
        path.write_bytes(artifact)
        paths.append((path, public_name))
    seed_index = output / "l65index.seed"
    seed_index.write_bytes(L65I.encode_index(placeholder))
    seed = output / "library.seed.d81"
    build_library_d81(seed, seed_index, paths)
    locators = L65I.d81_locators(seed)
    rows = []
    for spec in specs:
        public_name = spec[0]
        require(public_name in locators, f"seed locator absent: {public_name}")
        row, artifact = measured(spec, locators[public_name], build_id)
        require(artifact == artifacts[public_name],
                f"library artifact changed with locator: {public_name}")
        rows.append(row)
    index = L65I.encode_index(rows)
    index_path = output / "l65index"
    index_path.write_bytes(index)
    decoded = L65I.decode_index(
        index, artifacts, artifact_build_id=build_id)
    final = output / "lisp65-library.d81"
    build_library_d81(final, index_path, paths)
    require(L65I.d81_locators(final) == locators,
            f"{name} library locator drift after final index")
    visible = L65I.D81.visible_files(final.read_bytes())
    expected_visible = {b"L65INDEX": index}
    expected_visible.update({key.upper().encode(): value
                             for key, value in artifacts.items()})
    require(visible == expected_visible,
            f"{name} library visible-file truth drift")
    resolver_contracts = {
        spec[0]: resolver_contract(decoded, spec[0]) for spec in specs
    }
    resolver_mutations = (
        resolver_contract_mutation_gate(decoded, specs[-1][0])
        if len(decoded) >= 2 else {}
    )
    mutations = L65I.mutation_gate(
        index, artifacts, artifact_build_id=build_id)
    seed.unlink()
    seed_index.unlink()
    return {
        "variant": name,
        "product_build_id": f"0x{build_id:08x}",
        "D81": bind(final),
        "index": bind(index_path),
        "artifacts": {key: bind(output / f"{key}.l65s")
                      for key in artifacts},
        "index_rows": decoded,
        "index_mutations_rejected": len(mutations),
        "resolver_contracts": resolver_contracts,
        "resolver_mutations_rejected": resolver_mutations,
        "visible_files": sorted(key.decode() for key in visible),
    }


def existing_library_variant(
    name: str, output: Path, build_id: int,
) -> dict[str, Any]:
    specs = VARIANTS[name]
    paths = {spec[0]: output / f"{spec[0]}.l65s" for spec in specs}
    artifacts = {key: path.read_bytes() for key, path in paths.items()}
    index_path = output / "l65index"
    final = output / "lisp65-library.d81"
    index = index_path.read_bytes()
    decoded = L65I.decode_index(
        index, artifacts, artifact_build_id=build_id)
    visible = L65I.D81.visible_files(final.read_bytes())
    expected_visible = {b"L65INDEX": index}
    expected_visible.update({key.upper().encode(): value
                             for key, value in artifacts.items()})
    require(
        [row["name"] for row in decoded] == [spec[0] for spec in specs]
        and [row["dependencies"] for row in decoded]
            == [list(spec[4]) for spec in specs]
        and visible == expected_visible,
        f"SHA-fixed {name} library semantic closure drift",
    )
    resolver_contracts = {
        spec[0]: resolver_contract(decoded, spec[0]) for spec in specs
    }
    resolver_mutations = (
        resolver_contract_mutation_gate(decoded, specs[-1][0])
        if len(decoded) >= 2 else {}
    )
    mutations = L65I.mutation_gate(
        index, artifacts, artifact_build_id=build_id)
    require(
        (len(decoded) == 1 and len(mutations) == 29
         and "one-row-unconditional-second-row-access" in mutations)
        or (len(decoded) >= 2 and len(mutations) == 32),
        f"{name} index mutation closure drift",
    )
    value = {
        "variant": name,
        "product_build_id": f"0x{build_id:08x}",
        "D81": bind(final),
        "index": bind(index_path),
        "artifacts": {key: bind(path) for key, path in paths.items()},
        "index_rows": decoded,
        "index_mutations_rejected": len(mutations),
        "resolver_contracts": resolver_contracts,
        "resolver_mutations_rejected": resolver_mutations,
        "visible_files": sorted(key.decode() for key in visible),
    }
    if len(decoded) == 1:
        value["index_cardinality_witness"] = (
            "one-row-unconditional-second-row-access")
    return value


def variant_gate(base: dict[str, Any], sibling: dict[str, Any]) -> dict[str, Any]:
    require(
        base.get("variant") == "base"
        and sibling.get("variant") == "defstruct"
        and base.get("shared_media") == sibling.get("shared_media")
        and base.get("shared_artifacts") == sibling.get("shared_artifacts")
        and set(base.get("library", {}).get("artifacts", {})) == {"comfort"}
        and set(sibling.get("library", {}).get("artifacts", {}))
            == {"comfort", "defstruct"}
        and base["library"]["artifacts"]["comfort"]["sha256"]
            == sibling["library"]["artifacts"]["comfort"]["sha256"]
        and base["library"]["index_rows"]
            == sibling["library"]["index_rows"][:1]
        and base.get("selection") == {
            "conditional_defstruct_public": False,
            "eligible_for_release_before_D2": True,
        }
        and sibling.get("selection") == {
            "conditional_defstruct_public": True,
            "eligible_for_release_before_D2": False,
        },
        "two-variant closure escaped its enumerated defstruct delta",
    )
    return {
        "status": "passed-one-core-two-media-variants-exact-defstruct-delta",
        "shared_roles": len(base["shared_artifacts"]),
        "allowed_variant_delta": [
            "defstruct library artifact",
            "defstruct index row",
            "conditional surface selection metadata",
        ],
        "third_differences": 0,
    }


def rejected(label: str, action: Callable[[], None], out: dict[str, str]) -> None:
    try:
        action()
    except MediaClosureError as error:
        out[label] = str(error)
    else:
        raise MediaClosureError(f"media-variant mutation survived: {label}")


def selftest(
    base_override: dict[str, Any] | None = None,
    sibling_override: dict[str, Any] | None = None,
) -> dict[str, str]:
    base = deepcopy(base_override) if base_override is not None else load(BASE_MANIFEST)
    sibling = (deepcopy(sibling_override) if sibling_override is not None
               else load(D2_MANIFEST))
    mutations: dict[str, str] = {}

    def mutate(label: str, side: str, path: tuple[str, ...], value: Any) -> None:
        left, right = deepcopy(base), deepcopy(sibling)
        target = left if side == "base" else right
        cursor: Any = target
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = value
        rejected(label, lambda: variant_gate(left, right), mutations)

    mutate("shared-product-role-divergence", "defstruct",
           ("shared_artifacts", 0, "sha256"), "0" * 64)
    mutate("shared-comfort-divergence", "defstruct",
           ("library", "artifacts", "comfort", "sha256"), "1" * 64)
    mutate("shared-index-row-divergence", "defstruct",
           ("library", "index_rows", 0, "name"), "not-comfort")
    changed = deepcopy(base["library"]["artifacts"])
    changed["defstruct"] = sibling["library"]["artifacts"]["defstruct"]
    mutate("defstruct-leaked-into-base", "base",
           ("library", "artifacts"), changed)
    changed = deepcopy(sibling["library"]["artifacts"])
    del changed["defstruct"]
    mutate("defstruct-absent-from-sibling", "defstruct",
           ("library", "artifacts"), changed)
    mutate("conditional-selection-dimmed", "defstruct",
           ("selection", "conditional_defstruct_public"), False)
    require(len(mutations) == 6, "two-variant selftest count drift")
    return mutations


def shared_projection(shared: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {key: row[key] for key in ("role", "bytes", "sha256")}
        for row in shared["artifacts"]
    ]


def close_variants(
    shared: dict[str, Any], base_library: dict[str, Any],
    d2_library: dict[str, Any], *,
    execution_accounting: dict[str, int],
    resume_proof: dict[str, Any] | None = None,
) -> dict[str, Any]:
    shared_binding = bind(MEDIA.MANIFEST)
    shared_artifacts = shared_projection(shared)
    base = {
        "format": "lisp65-c2.3-v1.12-link92-media-variant-v1",
        "status": "passed-closed-base-media-candidate",
        "variant": "base",
        "shared_media": shared_binding,
        "shared_artifacts": shared_artifacts,
        "library": base_library,
        "selection": {
            "conditional_defstruct_public": False,
            "eligible_for_release_before_D2": True,
        },
    }
    sibling = {
        "format": "lisp65-c2.3-v1.12-link92-media-variant-v1",
        "status": "passed-closed-defstruct-acceptance-sibling",
        "variant": "defstruct",
        "shared_media": shared_binding,
        "shared_artifacts": shared_artifacts,
        "library": d2_library,
        "selection": {
            "conditional_defstruct_public": True,
            "eligible_for_release_before_D2": False,
        },
    }
    BASE_MANIFEST.write_bytes(canonical(base))
    D2_MANIFEST.write_bytes(canonical(sibling))
    pair = variant_gate(base, sibling)
    mutations = selftest(base, sibling)
    value = {
        "format": "lisp65-c2.3-v1.12-link92-r5-two-variant-media-v1",
        "recorded_on": "2026-08-07",
        "status": "passed-one-r5-core-two-closed-media-variants",
        "product_manifest": bind(PRODUCT_MANIFEST),
        "shared_media_manifest": shared_binding,
        "base_manifest": bind(BASE_MANIFEST),
        "defstruct_acceptance_manifest": bind(D2_MANIFEST),
        "variant_gate": pair,
        "mutations_rejected": mutations,
        "execution_accounting": execution_accounting,
        "next_gate": "Phase D bundled device acceptance and Halt #1",
        "claim_limit": (
            "Host-closed base and defstruct-acceptance media over the one "
            "immutable Link-92 r5 core. No device, selector, Halt or release claim."
        ),
    }
    if resume_proof is not None:
        value["resume_proof"] = resume_proof
    MANIFEST.write_bytes(canonical(value))
    RECEIPT.write_bytes(canonical(value))
    return value


def build() -> dict[str, Any]:
    require(not BUILD.exists(), "Link-92 two-variant media build is one-shot")
    configure_shared()
    shared = MEDIA.build()
    MEDIA.check()
    build_id = product_build_id()
    base_library = build_library_variant("base", BASE, build_id)
    d2_library = build_library_variant("defstruct", D2, build_id)
    return close_variants(
        shared, base_library, d2_library,
        execution_accounting={
            "product_compiler_runs": 0,
            "product_linker_runs": 0,
            "additional_product_cards": 0,
            "cold_stager_compiler_runs": 1,
            "shared_system_rebuilds": 1,
            "base_library_rebuilds": 1,
            "defstruct_sibling_builds": 1,
            "media_variants": 2,
            "hardware_runs": 0,
        },
    )


def resume() -> dict[str, Any]:
    require(
        not any(path.exists() for path in (
            BASE_MANIFEST, D2_MANIFEST, MANIFEST, RECEIPT,
        )),
        "resume output already exists; refusing a second completion",
    )
    require(D2.is_dir(), "SHA-fixed defstruct sibling is absent")
    configure_shared()
    source = Path(__file__).read_text(encoding="utf-8")
    gate = resume_source_gate(source)
    resume_mutations: dict[str, str] = {}

    def reject_resume_source(label: str, candidate: str) -> None:
        rejected(
            label, lambda: resume_source_gate(candidate), resume_mutations)

    changed = source.replace(
        "    before = existing_media_preflight()\n",
        "    before = MEDIA.build()\n", 1,
    )
    require(changed != source, "shared-system resume mutation did not apply")
    reject_resume_source("shared-system-rebuild-reintroduced", changed)
    changed = source.replace(
        '    base_library = existing_library_variant("base", BASE, build_id)\n',
        '    base_library = build_library_variant("base", BASE, build_id)\n', 1,
    )
    require(changed != source, "base-library resume mutation did not apply")
    reject_resume_source("base-library-rebuild-reintroduced", changed)
    changed = source.replace(
        '    d2_library = existing_library_variant("defstruct", D2, build_id)\n',
        '    d2_library = build_library_variant("defstruct", D2, build_id)\n', 1,
    )
    require(changed != source, "defstruct resume mutation did not apply")
    reject_resume_source("defstruct-sibling-rebuild-reintroduced", changed)
    require(len(resume_mutations) == 3, "resume mutation count drift")

    before = existing_media_preflight()
    shared = MEDIA.check()
    build_id = product_build_id()
    base_library = existing_library_variant("base", BASE, build_id)
    d2_library = existing_library_variant("defstruct", D2, build_id)
    after = existing_media_preflight()
    require(before == after, "SHA-fixed media changed during resume")
    return close_variants(
        shared, base_library, d2_library,
        execution_accounting={
            "product_compiler_runs": 0,
            "product_linker_runs": 0,
            "additional_product_cards": 0,
            "cold_stager_compiler_runs": 0,
            "shared_system_rebuilds": 0,
            "base_library_rebuilds": 0,
            "defstruct_sibling_builds": 0,
            "media_variants": 2,
            "hardware_runs": 0,
        },
        resume_proof={
            "owner_authorization_commit": "35e0a6f1",
            "source_gate": gate,
            "mutations_rejected": resume_mutations,
            "before": before,
            "after": after,
            "base_index_mutations_rejected": 29,
            "defstruct_index_mutations_rejected": 32,
            "resolver_contract_mutations_rejected": 2,
        },
    )


def check_variant(value: dict[str, Any]) -> None:
    library = value["library"]
    for row in [library["D81"], library["index"],
                *library["artifacts"].values()]:
        path = ROOT / row["path"]
        require(bind(path) == row, f"variant artifact drift: {path}")
    visible = L65I.D81.visible_files((ROOT / library["D81"]["path"]).read_bytes())
    require(sorted(key.decode() for key in visible) == library["visible_files"],
            "variant D81 visible inventory drift")
    artifacts = {
        name: (ROOT / row["path"]).read_bytes()
        for name, row in library["artifacts"].items()
    }
    decoded = L65I.decode_index(
        (ROOT / library["index"]["path"]).read_bytes(), artifacts,
        artifact_build_id=int(library["product_build_id"], 0),
    )
    require(decoded == library["index_rows"], "variant index decode drift")
    contracts = {
        row["name"]: resolver_contract(decoded, row["name"])
        for row in decoded
    }
    require(contracts == library.get("resolver_contracts"),
            "variant resolver contract drift")
    resolver_mutations = (
        resolver_contract_mutation_gate(decoded, decoded[-1]["name"])
        if len(decoded) >= 2 else {}
    )
    require(
        resolver_mutations == library.get("resolver_mutations_rejected"),
        "variant resolver mutation closure drift",
    )
    mutations = L65I.mutation_gate(
        (ROOT / library["index"]["path"]).read_bytes(), artifacts,
        artifact_build_id=int(library["product_build_id"], 0),
    )
    require(
        len(mutations) == library["index_mutations_rejected"],
        "variant index mutation closure drift",
    )
    if len(decoded) == 1:
        require(
            library.get("index_cardinality_witness")
                == "one-row-unconditional-second-row-access"
            and "one-row-unconditional-second-row-access" in mutations,
            "one-row index cardinality witness drift",
        )
    else:
        require(len(decoded) >= 2 and len(mutations) == 32,
                "multi-row index mutation closure drift")


def readback_identity() -> dict[str, Any]:
    return {
        "product_manifest": bind(PRODUCT_MANIFEST),
        "shared_manifest": bind(MEDIA.MANIFEST),
        "shared_product_D81": bind(MEDIA.PRODUCT_D81),
        "shared_work_D81": bind(MEDIA.WORK_D81),
        "base_D81": bind(BASE / "lisp65-library.d81"),
        "base_index": bind(BASE / "l65index"),
        "base_comfort": bind(BASE / "comfort.l65s"),
        "defstruct_D81": bind(D2 / "lisp65-library.d81"),
        "defstruct_index": bind(D2 / "l65index"),
        "defstruct_comfort": bind(D2 / "comfort.l65s"),
        "defstruct_artifact": bind(D2 / "defstruct.l65s"),
        "base_manifest": bind(BASE_MANIFEST),
        "defstruct_acceptance_manifest": bind(D2_MANIFEST),
        "aggregate_manifest": bind(MANIFEST),
        "persisted_receipt": bind(RECEIPT),
    }


def check() -> dict[str, Any]:
    configure_shared()
    before = readback_identity()
    shared = MEDIA.check()
    base = load(BASE_MANIFEST)
    sibling = load(D2_MANIFEST)
    check_variant(base)
    check_variant(sibling)
    pair = variant_gate(base, sibling)
    mutations = selftest(base, sibling)
    value = load(MANIFEST)
    require(
        value.get("status") == "passed-one-r5-core-two-closed-media-variants"
        and value.get("product_manifest") == bind(PRODUCT_MANIFEST)
        and value.get("shared_media_manifest") == bind(MEDIA.MANIFEST)
        and value.get("base_manifest") == bind(BASE_MANIFEST)
        and value.get("defstruct_acceptance_manifest") == bind(D2_MANIFEST)
        and value.get("variant_gate") == pair
        and value.get("mutations_rejected") == mutations
        and value.get("shared_media_manifest", {}).get("sha256")
            == bind(MEDIA.MANIFEST)["sha256"]
        and shared.get("artifact_count") == 19
        and load(RECEIPT) == value,
        "Link-92 two-variant media receipt drift",
    )
    after = readback_identity()
    require(after == before, "aggregate readback changed a SHA-fixed artifact")
    return value


def fresh_readback() -> dict[str, Any]:
    lifecycle = configuration_lifecycle_gate()
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "check"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False,
    )
    require(result.returncode == 0,
            f"fresh aggregate readback failed: {result.stdout}")
    return {
        "status": "passed-fresh-process-readback",
        "lifecycle": lifecycle,
        "output": result.stdout.strip(),
    }


def startup_selftest() -> dict[str, str]:
    source = Path(__file__).read_text(encoding="utf-8")
    configuration_lifecycle_gate(source)
    mutations: dict[str, str] = {}
    changed = source.replace(
        "_CONFIGURE_SHARED_CALLS == 0",
        "_CONFIGURE_SHARED_CALLS >= 0", 1,
    )
    require(changed != source, "double-configuration source mutation absent")
    rejected(
        "double-configuration-guard-dimmed",
        lambda: configuration_lifecycle_gate(changed), mutations,
    )
    configure_shared()
    try:
        configure_shared()
    except MediaClosureError as error:
        require(str(error) == _HARNESS_DOUBLE_CONFIG_ERROR,
                "second configuration escaped the harness guard")
        mutations["second-in-process-configuration"] = str(error)
    else:
        raise MediaClosureError(
            "second in-process configuration reached the product selector")
    require(len(mutations) == 2,
            "configuration lifecycle mutation count drift")
    return mutations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=(
            "build", "resume", "check", "selftest", "startup-selftest"))
    action = parser.parse_args().action
    try:
        if action == "build":
            value = build()
            fresh_readback()
        elif action == "resume":
            value = resume()
            fresh_readback()
        elif action == "check":
            value = check()
        elif action == "startup-selftest":
            mutations = startup_selftest()
            print(
                "c2-v112-candidate-media: STARTUP SELFTEST PASS "
                f"mutations={len(mutations)}"
            )
            return 0
        else:
            mutations = selftest()
            print(f"c2-v112-candidate-media: SELFTEST PASS mutations={len(mutations)}")
            return 0
        print(
            "c2-v112-candidate-media: PASS "
            f"variants=2 shared={value['variant_gate']['shared_roles']} "
            f"mutations={len(value['mutations_rejected'])}"
        )
        return 0
    except (
        MediaClosureError, MEDIA.MediaError, CAN.CanonicalError,
        L65I.GateError, L65I.S.ProbeError, RuntimeError, OSError,
        ValueError, KeyError, json.JSONDecodeError,
    ) as error:
        print(f"c2-v112-candidate-media: FIRST RED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
