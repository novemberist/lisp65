#!/usr/bin/env python3
"""Reproduce the frozen v2.1.0 renderer world from its public source projection."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v180_public_product as V180  # noqa: E402


CARD: Any = None
RELEASE_MEDIA: Any = None


PUBLIC = ROOT / "build/release-v2.1.0/public-selected"
BUILD = ROOT / "build/v2.1/renderer-branch-product-r1"
PREFLIGHT = ROOT / "build/v2.1/renderer-branch-product-r1-preflight"
PLANE_ROOT = PREFLIGHT / "setup-owned/static-plane/narrow-static"
PLANE_RECEIPT = PREFLIGHT / "v200-release-static-plane.json"
C2D = PLANE_ROOT / "v6-semantics/initial.c2d-v6.bin"
CODE = PLANE_ROOT / "v6-semantics/bank2-static-code.bin"
MANIFEST = PLANE_ROOT / "stdlib-p0.manifest.json"
HEADER = PLANE_ROOT / "stdlib-p0.h"
PLANE_SOURCE = ROOT / "config/c2-v200-public-plane/static-plane"
SOURCE_SNAPSHOTS = ROOT / "config/c2-v200-public-plane/sources"
EXTERNAL_MANIFESTS = ROOT / "config/c2-v200-public-plane/external-manifests"
EXTERNAL_IMAGES = ROOT / "config/c2-v200-public-plane/external-images"
GENERATION_SUITE_SOURCE = (
    ROOT / "config/c2-v200-public-plane/resident-interactive-stdlib-suite.json")
AUTHORITY = ROOT / "config/c2-v210-public-build-authority.json"
STATIC_RECEIPT = PUBLIC / "public-static.json"
LINK_RECEIPT = PUBLIC / "linked-product.json"
PUBLIC_ACCEPTANCE = PUBLIC / "public-acceptance.json"
PUBLIC_INVOCATION = PUBLIC / "public-link-invocation.json"
PUBLIC_DIRECT_ENTRY = PUBLIC / "public-direct-entry-contract.json"
PUBLIC_GENERATION_SUITE = PUBLIC / "resident-interactive-stdlib-suite.json"
CANONICAL = PUBLIC / "canonical-product"
SHARED = PUBLIC / "shared-system"
MANIFEST_OUT = PUBLIC / "candidate-manifest.json"
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
PROFILE = BUILD / "wplto/resolved-profile.txt"
EXPECTED_RAW = {
    "PRG": (41811,
        "e05a242cfd81f2c72e00d695e682e8e5eb2f017baf50ec58f2933ebcfe2e2f23"),
    "ELF": (642492,
        "c09d6e4d37a7e413133fc8541cc351e5cfc8274fefb7d3aaa325638f39391b2c"),
    "profile": (13673,
        "894397ad0753c5b218d7d1e9e641e3775ea688802c5a536d44d2db2db2eb856e"),
}
FORMAT = "lisp65-v2.1-public-selected-product-v1"
STATUS = "passed-public-source-selected-v2.1-renderer-f011-native"


class PublicBuildError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PublicBuildError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def artifact_set(rows: list[dict[str, Any]]) -> str:
    projection = [{key: row[key] for key in ("role", "name", "bytes", "sha256")}
                  for row in sorted(rows, key=lambda row: (row["role"], row["name"]))]
    return hashlib.sha256(json.dumps(
        projection, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def source_preflight_path() -> Path:
    """The producer owns the output root; consumers never select an era receipt."""
    return PUBLIC / "source-preflight.json"


def compiler_projection(sources, mapping) -> dict[str, Any]:
    def identity(path):
        local = Path(path).relative_to(ROOT)
        return (local.name if "generated-product-sources" in local.parts
                else local.as_posix())
    rows = [{"source": identity(Path(p)), "bytes": Path(p).stat().st_size,
             "sha256": sha(Path(p))} for p in sources]
    require(len({r["source"] for r in rows}) == len(rows),
            "ambiguous compiler source population")
    return {"total": len(rows), "generated": len(mapping), "identities": rows}


def consume_source_preflight(path, value, sources, mapping):
    require(Path(path).resolve() == source_preflight_path().resolve(),
            "source preflight consumer diverges from producer output")
    require(value.get("producer_output") == source_preflight_path().relative_to(ROOT).as_posix()
            and value.get("status") == "PASS"
            and value.get("compiler_sources") == compiler_projection(sources, mapping),
            "source preflight value diverges from materialized compiler inputs")
    return value


def authority() -> dict[str, Any]:
    value = load(AUTHORITY)
    require(value["format"] == "lisp65-c2-public-build-authority-v8"
            and value["release"] == "v2.1.0"
            and value["entry_point"] == "make workbench-product-v210"
            and value["artifact_count"] == len(value["sealed_roles"]) == 19
            and value["private_evidence_is_build_input"] is False,
            "v2.0 public authority envelope drift")
    return value


def load_product_modules() -> None:
    """Load the live card graph after binding the public v2.0 source plane."""
    global CARD, RELEASE_MEDIA
    if CARD is not None:
        return
    v160 = V180.V160
    v160.FIDELITY.CANDIDATE_STATIC_ROOT = ROOT
    v160.FIDELITY.CANDIDATE_STATIC_PRODUCT = (
        PLANE_ROOT / "product/substitution-artifacts.json")
    v160.FIDELITY.CANDIDATE_PREFLIGHT_ROOT = PREFLIGHT
    v160.FIDELITY.CANDIDATE_PROFILE = PLANE_ROOT / "candidate-profile.json"
    v160.FIDELITY.CANDIDATE_PLANE = PLANE_ROOT / "product"
    CARD = importlib.import_module("c2_v200_release_card")
    RELEASE_MEDIA = importlib.import_module("c2_v200_release_media")


def bind_l_full_consumer() -> None:
    """Make the real L-full reader consume the candidate manifest union."""
    plane = importlib.import_module("c2_l_full_static_plane_gate")
    marker = "_v200_public_original_source_bundle"
    if not hasattr(plane, marker):
        setattr(plane, marker, plane.source_bundle)
    original = getattr(plane, marker)

    def candidate_source_bundle() -> dict[str, Any]:
        product_path = PLANE_ROOT / "product/substitution-artifacts.json"
        product = load(product_path)
        rows = product["manifests"]
        require(len(rows) == 6, "v2.0 L-full candidate manifest union drift")
        paths = tuple(ROOT / row["path"] for row in rows)
        for row, path in zip(rows, paths, strict=True):
            require(path.is_file() and not path.is_symlink()
                    and path.stat().st_size == row["bytes"]
                    and sha(path) == row["sha256"],
                    f"v2.0 L-full candidate manifest binding drift: {path}")
        plane.FRESH_ROOT = PLANE_ROOT
        plane.FRESH_PRODUCT = product_path
        plane.FRESH_IDE = paths[1]
        plane.FRESH_BANK2 = CODE
        plane.FRESH_MANIFESTS = paths
        return original()

    plane.source_bundle = candidate_source_bundle
    # The WPLTO configurator replaces PLANE.source_bundle at its real caller
    # boundary.  Bind that replacement too; otherwise registration is green
    # while the materialized link still consumes the historical IDE manifest.
    canonical_product = importlib.import_module("c2_lite_canonical_product")
    canonical_product.fresh_static_plane_bundle = candidate_source_bundle


def original_relative(raw: str) -> Path:
    marker = "/lisp65-cp4-safety-20260712/"
    candidate = raw.split(marker, 1)[1] if marker in raw else raw
    result = Path(candidate)
    require(not result.is_absolute() and ".." not in result.parts,
            f"unsafe sealed source path: {raw}")
    return result


def materialize_sources() -> dict[str, Any]:
    manifest = load(PLANE_SOURCE / "stdlib-p0.manifest.json")
    sources = manifest["sources"]
    snapshots = sorted(SOURCE_SNAPSHOTS.iterdir())
    require(len(sources) == len(snapshots) == 25,
            "v2.0 public source snapshot inventory drift")
    projected = []
    for raw, snapshot in zip(sources, snapshots, strict=True):
        relative = original_relative(raw)
        destination = ROOT / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            require(destination.is_file() and sha(destination) == sha(snapshot),
                    f"tracked/current source differs from snapshot: {relative}")
        else:
            shutil.copyfile(snapshot, destination)
        projected.append({"relative": relative.as_posix(),
                          "snapshot": bind(snapshot),
                          "materialized": bind(destination)})
    return {"count": len(projected), "rows": projected}


def materialize_external_manifests() -> list[dict[str, Any]]:
    product = load(PLANE_SOURCE / "product/substitution-artifacts.json")
    rows = product["manifests"][1:]
    snapshots = {
        "ide.manifest.json": EXTERNAL_MANIFESTS / "libs-ide.manifest.json",
        "idex.manifest.json": EXTERNAL_MANIFESTS / "libs-idex.manifest.json",
        "m65d.manifest.json": EXTERNAL_MANIFESTS / "libs-m65d.manifest.json",
        "buffer.manifest.json": EXTERNAL_MANIFESTS / "libs-buffer.manifest.json",
        "lcc.manifest.json": EXTERNAL_MANIFESTS / "compiler-lcc.manifest.json",
    }
    result = []
    for row in rows:
        relative = Path(row["path"])
        require(not relative.is_absolute() and relative.name in snapshots,
                f"external manifest projection drift: {relative}")
        source = snapshots[relative.name]
        require(source.stat().st_size == row["bytes"] and sha(source) == row["sha256"],
                f"external manifest snapshot identity drift: {relative.name}")
        destination = ROOT / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            require(destination.is_file() and sha(destination) == sha(source),
                    f"external manifest differs: {relative}")
        else:
            shutil.copyfile(source, destination)
        result.append({"role": relative.name, "source": bind(source),
                       "materialized": bind(destination)})
    return result


def rebind_plane_source_manifest() -> dict[str, Any]:
    """Bind the copied plane to sources inside this public checkout.

    The sealed plane records the producer checkout's absolute source names.
    They are provenance, not a valid public-build authority: leaving them live
    would let a clean clone consume a different checkout.  Preserve the
    repository-relative suffixes while binding every live source to ROOT, then
    update the two manifests that own that identity.
    """
    manifest_path = PLANE_ROOT / "stdlib-p0.manifest.json"
    manifest = load(manifest_path)
    manifest["sources"] = [str((ROOT / original_relative(raw)).resolve())
                           for raw in manifest["sources"]]
    for raw in manifest["sources"]:
        source = Path(raw)
        require(source.is_file() and not source.is_symlink()
                and source.is_relative_to(ROOT),
                f"public manifest source escaped clean checkout: {raw}")
    manifest_path.write_bytes(canonical(manifest))

    product_path = PLANE_ROOT / "product/substitution-artifacts.json"
    product = load(product_path)
    require(len(product["manifests"]) == 6,
            "v2.0 public product manifest inventory drift")
    product["manifests"][0] = bind(manifest_path)
    product_path.write_bytes(canonical(product))

    return {"source_root": ROOT.as_posix(), "source_count": 25,
            "manifest": bind(manifest_path), "product": bind(product_path)}


def materialize_generation_suite() -> dict[str, Any]:
    """Bind the packed-generation proof to this checkout's live sources."""
    suite = load(GENERATION_SUITE_SOURCE)
    manifest = load(MANIFEST)
    sources = manifest["sources"]
    require(len(sources) == 25 and all(Path(raw).is_relative_to(ROOT)
            for raw in sources),
            "v2.0 public generation-suite source population drift")
    suite["sources"] = sources
    suite["_suite_dir"] = PUBLIC.as_posix()
    suite["_suite_path"] = PUBLIC_GENERATION_SUITE.as_posix()
    PUBLIC_GENERATION_SUITE.write_bytes(canonical(suite))
    return {"template": bind(GENERATION_SUITE_SOURCE),
            "materialized": bind(PUBLIC_GENERATION_SUITE),
            "source_count": len(sources)}


def materialize_plane() -> dict[str, Any]:
    require(not PUBLIC.exists() and not BUILD.exists() and not PREFLIGHT.exists(),
            "v2.0 public product stage is one-shot")
    sources = materialize_sources()
    manifests = materialize_external_manifests()
    images = []
    for name in ("ide", "idex", "m65d"):
        path = EXTERNAL_IMAGES / f"{name}.ext.bin"
        expected = authority()["sealed_roles"][f"library-{name}"]
        require(path.stat().st_size == expected["bytes"]
                and sha(path) == expected["sha256"],
                f"v2.0 public external image drift: {name}")
        images.append({"name": name, "artifact": bind(path)})
    PLANE_ROOT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(PLANE_SOURCE, PLANE_ROOT)
    source_rebind = rebind_plane_source_manifest()
    # One historical wrapper still performs an early fail-closed bind at the
    # original product-authority path before the successor resolver takes
    # ownership.  Supply the candidate-derived manifest there as a compatibility
    # view; it is the same bytes and is recorded below, never a silent default.
    compatibility = ROOT / "build/c2.2/substitution/substitution-artifacts.json"
    compatibility.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PLANE_ROOT / "product/substitution-artifacts.json",
                    compatibility)
    for source, name in (
        (PLANE_ROOT / "product/product-shelf-v4-direct.bin",
         "product-shelf-v4-direct.bin"),
        (PLANE_ROOT / "product/initial.c2d-v3.bin", "initial.c2d-v3.bin"),
        (PLANE_ROOT / "stdlib-p0.h", "stdlib-p0.h"),
    ):
        shutil.copyfile(source, compatibility.parent / name)
    ownership = ROOT / "build/c2.3/v2.0-ownership-recharter-inputs"
    ownership.mkdir(parents=True, exist_ok=True)
    for name in ("c2_lite_static_plane.h", "candidate-profile.json",
                 "c2-lite-execution-contract.json"):
        shutil.copyfile(PLANE_ROOT / name, ownership / name)
    plane = {
        "format": "lisp65-v2.0-public-static-plane-source-v1",
        "status": "PASS: V2.0 PUBLIC SOURCE PLANE MATERIALIZED",
        "private_evidence_inputs": 0,
        "geometry": bind(PLANE_ROOT / "v6-semantics/bank2-static-code.bin"),
        "manifests": [bind(PLANE_ROOT / "stdlib-p0.manifest.json"),
            *[bind(EXTERNAL_MANIFESTS / name) for name in (
                "libs-ide.manifest.json", "libs-idex.manifest.json",
                "libs-m65d.manifest.json", "libs-buffer.manifest.json",
                "compiler-lcc.manifest.json")]],
        "product": bind(PLANE_ROOT / "product/substitution-artifacts.json"),
        "source_rebind": source_rebind,
        "compatibility_product_authority": bind(compatibility),
        "compatibility_ownership_authority": {
            name: bind(ownership / name) for name in (
                "c2_lite_static_plane.h", "candidate-profile.json",
                "c2-lite-execution-contract.json")},
    }
    PLANE_RECEIPT.write_bytes(canonical(plane))
    require(plane["geometry"]["bytes"] == 47795,
            "v2.0 public source plane geometry drift")
    PUBLIC.mkdir(parents=True)
    generation_suite = materialize_generation_suite()
    value = {"format": "lisp65-v2.0-public-static-plane-v1",
        "status": "PASS: V2.0 PUBLIC CANDIDATE SOURCE PLANE",
        "private_evidence_inputs": 0, "product_WPLTO_runs": 0,
        "product_links": 0, "sources": sources,
        "external_manifests": manifests, "external_images": images,
        "generation_suite": generation_suite,
        "source_rebind": source_rebind,
        "plane": bind(PLANE_RECEIPT),
        "bank2": bind(PLANE_ROOT / "v6-semantics/bank2-static-code.bin"),
        "manifest": bind(PLANE_ROOT / "stdlib-p0.manifest.json")}
    STATIC_RECEIPT.write_bytes(canonical(value))
    print("v2.0 public product: STATIC PASS sources=25 evidence=0")
    return value


def configure_card() -> None:
    load_product_modules()
    # The live card graph still contains sealed-era price readers.  Public
    # builds replace those readers with the already-established current-source
    # authorities before any producer path can consume them.
    v160 = V180.V160
    v160.CAPACITY.capacity_authority = v160.public_capacity
    v160.FIDELITY.CANDIDATE_STATIC_ROOT = ROOT
    v160.FIDELITY.CANDIDATE_STATIC_PRODUCT = (
        PLANE_ROOT / "product/substitution-artifacts.json")
    v160.FIDELITY.CANDIDATE_PREFLIGHT_ROOT = PREFLIGHT
    v160.FIDELITY.CANDIDATE_PROFILE = PLANE_ROOT / "candidate-profile.json"
    v160.FIDELITY.CANDIDATE_PLANE = PLANE_ROOT / "product"
    v160.configure_public_source_authorities()
    # The deepest product seam is fail-closed on its two source-owner
    # projections.  Derive them in this checkout before the wrapper graph is
    # configured; importing sealed projections would make review evidence a
    # compilation input.
    root_card = importlib.import_module("c2_v21_probe_oracle_root_card")
    root_card.PREFLIGHT = PREFLIGHT
    root_card.PROJECTED_OWNERSHIP = PREFLIGHT / "candidate-ownership-contract.json"
    root_card.PROJECTED_FULL_MAP = PREFLIGHT / "candidate-full-map-contract.json"
    if not (root_card.PROJECTED_OWNERSHIP.is_file()
            and root_card.PROJECTED_FULL_MAP.is_file()):
        root_card.write_projections()
    # Successor wrappers give the same two projections newer role names.  Both
    # names are producer-owned views of the just-derived bytes, not independent
    # authorities.
    for source, destination in (
        (root_card.PROJECTED_OWNERSHIP,
         PREFLIGHT / "projected-ownership-contract.json"),
        (root_card.PROJECTED_FULL_MAP,
         PREFLIGHT / "projected-full-map-authority.json"),
    ):
        if not destination.exists():
            shutil.copyfile(source, destination)
    # The latch wrapper originally derived its placement by rereading the
    # previous release ELF.  A public source build does not import that binary;
    # derive the same boundary from the terminal-guard source contract.
    latch_card = importlib.import_module(
        "c2_v200_symbol22_first_fault_product_card")
    build_id_card = importlib.import_module(
        "c2_v200_symbol22_build_id_rebind")
    build_id_card.CANDIDATE_MANIFEST = (
        PLANE_ROOT / "product/substitution-artifacts.json")
    def public_build_id_seed_world() -> Any:
        core = build_id_card.R3.configure_seed_world()
        candidate = build_id_card.CANDIDATE_MANIFEST
        build_id_card.CARD.PRODUCT.configure_product_artifacts_manifest_resolver(
            lambda candidate=candidate: candidate)
        resolved = build_id_card.CARD.PRODUCT.resolved_product_artifacts_manifest()
        require(resolved == candidate
                and load(resolved)["product_build_id_hex"] ==
                    load(PLANE_ROOT / "product/substitution-artifacts.json")[
                        "product_build_id_hex"],
                "public candidate product authority did not dominate")
        return core
    build_id_card.configure_seed_world = public_build_id_seed_world
    terminal_guard = importlib.import_module("c2_terminal_return_guard_gate")
    phase02b = importlib.import_module(
        "c2_v20_phase02b_header_consumption_card")
    public_header = ROOT / (
        "build/c2.3/v2.0-ownership-recharter-inputs/"
        "c2_lite_static_plane.h")

    def public_phase02b_header_binding(
            path: Path = public_header) -> dict[str, Any]:
        value = bind(path)
        require(path == public_header
                and value["sha256"] == bind(
                    PLANE_ROOT / "c2_lite_static_plane.h")["sha256"],
                "public phase02b consumer did not bind candidate header")
        return value

    def public_phase02b_consumption() -> dict[str, Any]:
        binding = public_phase02b_header_binding()
        phase02b.PRODUCT.configure_compiler_consumed_static_header(
            public_header, binding, 47795)
        return binding

    phase02b.CANDIDATE_HEADER = public_header
    phase02b.header_binding = public_phase02b_header_binding
    phase02b.configure_consumption = public_phase02b_consumption
    latch_card.release_raw_guard_geometry = lambda: {
        "start": terminal_guard.ARENA_START,
        "end_exclusive": terminal_guard.ARENA_END,
        "data_references": 64,
        "source_sections": [
            ".lisp65_rt_c2append_header",
            ".lisp65_rt_c2append_publish_clear",
            ".lisp65_rt_c2append_publish_plan_resolve",
            ".lisp65_rt_c2append_publish_plan_scan"],
        "authority": "terminal-return-guard-source-contract",
    }
    CARD.BUILD = BUILD; CARD.PREFLIGHT = PREFLIGHT
    CARD.PLANE = PLANE_ROOT; CARD.PLANE_RECEIPT = PLANE_RECEIPT
    CARD.WPLTO = BUILD / "wplto"
    CARD.ELF = ELF; CARD.PRG = PRG; CARD.PROFILE = PROFILE
    CARD.PREDECESSOR_PLANE = PLANE_ROOT
    CARD.PREDECESSOR_MANIFEST = MANIFEST
    CARD.PREDECESSOR_CODE = CODE
    CARD.PREDECESSOR_PROFILE = ROOT / "config/c2-v210-renderer-profile.txt"
    public_predecessor = PUBLIC / "public-profile-authority.json"
    public_predecessor.write_bytes(canonical({
        "status": "PUBLIC SOURCE PROFILE AUTHORITY",
        "private_evidence_inputs": 0,
        "artifacts_after": {"ELF": {"path":
            (PLANE_SOURCE / "profile-anchor.elf").relative_to(ROOT).as_posix()}},
        "profile": bind(PLANE_SOURCE / "resolved-profile.txt"),
    }))
    CARD.PREDECESSOR_RECEIPT = public_predecessor
    CARD.INVOCATION = PUBLIC / "public-link-invocation.json"
    CARD.RECEIPT = PUBLIC / "unused-release-card.json"
    CARD.DIFFERENCE = PUBLIC / "unused-difference.json"
    CARD.REPORT = PUBLIC / "unused-report.md"
    CARD.PREFLIGHT_RECEIPT = PUBLIC / "unused-preflight.json"
    CARD.SOURCE_PREFLIGHT = source_preflight_path()
    plane_receipt = load(PLANE_RECEIPT)
    plane_receipt["geometry"] = CARD.geometry()
    PLANE_RECEIPT.write_bytes(canonical(plane_receipt))
    static_receipt = load(STATIC_RECEIPT)
    static_receipt["plane"] = bind(PLANE_RECEIPT)
    STATIC_RECEIPT.write_bytes(canonical(static_receipt))
    product_link = importlib.import_module("c2_product_substitution_link")
    product_link.configure_f011_cold_product()
    product_link.configure_fixed_raw_bss_owners()
    marker = "_v210_disabled_witness_registration"
    if not hasattr(product_link, marker):
        setattr(product_link, marker, product_link.f011_status_inventory_registration)
    def disabled_witness_registration():
        result = getattr(product_link, marker)()
        require(not result["selected"], "diagnostic F011 record selected")
        result.update(names=[".noinit.lisp65_f011_status"], record_bytes=0,
                      authority="declared empty linker shell; exact renderer reproduction")
        return result
    product_link.f011_status_inventory_registration = disabled_witness_registration
    CARD.configure()
    # The feature population is the consumed renderer profile, not an
    # extension of the older public world's list.
    profile_path = ROOT / "config/c2-v210-renderer-profile.txt"
    feature_lines = [line for line in profile_path.read_text().splitlines()
                     if line.startswith("feature_defines=")]
    require(len(feature_lines) == 1, "renderer feature authority absent")
    renderer_features = tuple(feature_lines[0].split("=", 1)[1].split(","))
    require(len(renderer_features) == len(set(renderer_features)) == 36,
            "renderer feature population drift")
    CARD.CHAIN.LINK.predecessor_profile = lambda: profile_path
    CARD.CHAIN.LINK.predecessor_features = lambda: renderer_features
    consumer_inputs = {}
    def renderer_sources(mapping: dict[Path, Path],
                         features: tuple[str, ...]) -> list[str]:
        require(features == renderer_features, "renderer feature consumer drift")
        originals = product_link.source_list(features)
        result = [str(mapping.get(Path(p).resolve(), Path(p))) for p in originals]
        expected = [line.split("=", 1)[1].rsplit(":", 1)[0]
                    for line in profile_path.read_text().splitlines()
                    if line.startswith("input_sha256=")
                    and Path(line.split("=", 1)[1].rsplit(":", 1)[0]).suffix in (".c", ".s")]
        def identity(path: str) -> str:
            local = Path(path)
            if local.is_absolute():
                local = local.relative_to(ROOT)
            return local.name if "generated-product-sources" in local.parts else local.as_posix()
        require([identity(p) for p in result] == [identity(p) for p in expected],
                "renderer compiled-source population differs from bound profile")
        consumer_inputs.update(sources=result, mapping=mapping)
        return result
    CARD.CHAIN.LINK.projected_source_list = renderer_sources
    link = CARD.CHAIN.LINK
    require(link.SOURCE_PREFLIGHT == source_preflight_path(),
            "configured source preflight path did not reach the compiler consumer")
    if not hasattr(link, "_v210_original_load"):
        link._v210_original_load = link.load
    def consumer_load(path):
        if Path(path) == link.SOURCE_PREFLIGHT:
            require(consumer_inputs, "source preflight consumed before materialization")
            require(Path(path).resolve() == source_preflight_path().resolve(),
                    "source preflight consumer selected a historical output")
            return consume_source_preflight(path, load(path), **consumer_inputs)
        return link._v210_original_load(path)
    link.load = consumer_load
    public = lambda: {"authority": "public-renderer-source-v2.1",
        "private_evidence_inputs": 0, "release": "v2.1.0"}
    def public_configuration_gate() -> dict[str, Any]:
        require(CODE.stat().st_size == 47795
                and MANIFEST.is_file() and HEADER.is_file(),
                "v2.0 public configuration did not bind the source plane")
        return {"status": "PASS: PUBLIC V2.0 SOURCE PLANE BOUND",
                "private_evidence_inputs": 0,
                "plane": bind(CODE), "manifest": bind(MANIFEST)}

    def public_final_gate() -> dict[str, Any]:
        from elf_truth import ElfTruth
        truth = ElfTruth.read(ELF,
            llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
        sections = {row.name: row for row in truth.sections}
        symbols = {row.name: row for row in truth.symbols}
        required = {".lisp65_c2_kernal_window.input_capture_helper",
                    ".lisp65_c2_kernal_window.input_capture_main",
                    ".lisp65_c2_kernal_window.input_consumer",
                    ".lisp65_c2_mapped_product_cold"}
        require(required <= set(sections)
                and "c2_kernal_input_take" in symbols
                and ".lisp65_c2_mapped_diagnostic" not in sections,
                "v2.0 public final product freight drift")
        return {"status": "PASS: PUBLIC V2.0 FINAL ELF",
                "required_sections": sorted(required),
                "diagnostic_freight_absent": True}

    CARD.authority = public
    CARD.configuration_gate = public_configuration_gate
    CARD.final_gate = public_final_gate
    CARD.CHAIN.authority = public
    CARD.CHAIN.LINK.BASE.authority = public
    CARD.CHAIN.LINK.BASE.configuration_gate = public_configuration_gate
    CARD.CHAIN.LINK.BASE.final_gate = public_final_gate
    product_link = importlib.import_module("c2_product_substitution_link")
    stable = authority()["sealed_path_dependent_profile_fields"]
    product_link.SEALED_C2_ARTIFACTS_IDENTITY = stable[
        "c2_artifacts_sha256"]
    product_link.SEALED_V2_PROFILE_PARITY_IDENTITY = stable[
        "v2_profile_parity_sha256"]
    direct = importlib.import_module("c2_direct_entry_contract")
    original_tool = product_link.tool

    def public_direct_entry() -> dict[str, Any]:
        c2d = PLANE_ROOT / "product/initial.c2d-v3.bin"
        raw = c2d.read_bytes()
        u16 = lambda at: int.from_bytes(raw[at:at + 2], "little")
        direct.SHELF = PLANE_ROOT / "product/product-shelf-v4-direct.bin"
        direct.C2D = c2d
        direct.ARTIFACTS = PLANE_ROOT / "product/substitution-artifacts.json"
        direct.BUILD = PUBLIC / "direct-entry-work"
        direct.EXPECTED_GEOMETRY = {"images": u16(12), "entries": u16(16),
            "resolutions": u16(20), "roots": u16(24),
            "images_offset": u16(28)}
        direct.EXPECTED_DIRECT_REFS = 674
        value = direct.collect()
        require(value["cross_parity"]["direct_entry_references"] == 674,
                "v2.0 public direct-entry population drift")
        value["public_source_authority"] = {
            "private_evidence_inputs": 0, "plane": bind(CODE)}
        encoded = canonical(value)
        if PUBLIC_DIRECT_ENTRY.exists():
            require(PUBLIC_DIRECT_ENTRY.read_bytes() == encoded,
                    "v2.0 public direct-entry receipt drift")
        else:
            PUBLIC_DIRECT_ENTRY.write_bytes(encoded)
        return value

    def public_tool(*args: Any, **kwargs: Any) -> Any:
        if (len(args) == 2 and not kwargs
                and args[0] == "c2_v200_block3_direct_entry.py"
                and args[1] == "check"):
            public_direct_entry()
            return
        return original_tool(*args, **kwargs)

    product_link.tool = public_tool
    CARD.CHAIN.LINK.DIRECT_ENTRY_RECEIPT = PUBLIC_DIRECT_ENTRY
    v160.CAPACITY.capacity_authority = v160.public_capacity
    bind_l_full_consumer()


def produce_child(action: str) -> None:
    if action == "_public_accept":
        write_public_acceptance()
        return
    configure_card()
    if action == "_produce":
        # Keep the public bindings installed above; the release wrapper's
        # normal second configure pass would restore sealed-era adapters.
        CARD.configure = lambda: None
        CARD.child("_produce")
    elif action == "_scope":
        write_public_scope()
    elif action == "_accept":
        CARD.child("_accept")


def run_child(action: str) -> str:
    stable = authority()["sealed_path_dependent_profile_fields"]
    result = subprocess.run([sys.executable, str(Path(__file__).resolve()), action],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
             "LISP65_PUBLIC_CLEAN_BUILD": "1",
             "LISP65_DIRECT_ENTRY_IDENTITY_SHA256":
                stable["direct_entry_contract_sha256"]})
    require(result.returncode == 0,
            f"v2.0 public child {action} red:\n{result.stdout}")
    return result.stdout


def public_scope_projection() -> dict[str, Any]:
    """Reproduction scope: exact source/feature population and real ABI policies."""
    configure_card()
    abi = importlib.import_module("c2_asm_leaf_abi_gate")
    expected = (ROOT / "config/c2-v210-renderer-profile.txt").read_text().splitlines()
    observed = PROFILE.read_text().splitlines()
    projection = lambda lines: [line for line in lines if
        line.startswith(("input_sha256=", "feature_defines="))]
    require(projection(observed) == projection(expected),
            "renderer source or feature consumption differs")
    inventory = abi.source_inventory()
    require(inventory and all(row.get("source") and row.get("policy")
                              for row in inventory.values()),
            "unclassified assembler owner")
    # Validate omissions against the population just derived from live sources.
    expected_keys = set(inventory)
    def validate(lines, policies):
        require(projection(lines) == projection(expected)
                and set(policies) == expected_keys
                and all(row.get("source") and row.get("policy")
                        for row in policies.values()), "scope mutation rejected")
    validate(observed, inventory)
    rejected = []
    cases = {
        "source-omitted": ([x for x in observed if not x.startswith("input_sha256=")], inventory),
        "features-omitted": ([x for x in observed if not x.startswith("feature_defines=")], inventory),
        "policy-omitted": (observed, {k:v for k,v in inventory.items() if k != sorted(inventory)[0]}),
    }
    for name, args in cases.items():
        try:
            validate(*args)
        except PublicBuildError:
            rejected.append(name)
    require(set(rejected) == set(cases), "scope negative control survived")
    return {"status": "PASS", "mode": "exact-frozen-source-reproduction",
            "compiled_profile": bind(PROFILE), "assembler_policies": inventory,
            "mutations_rejected": rejected}


def write_public_scope() -> None:
    value = {
        "format": "lisp65-v2.0-public-owner-scope-v1",
        "status": "PASS",
        "private_evidence_inputs": 0,
        "gate": public_scope_projection(),
        "artifacts": {"ELF": bind(ELF), "PRG": bind(PRG),
                      "profile": bind(PROFILE)},
    }
    require(all((value["artifacts"][role]["bytes"],
                 value["artifacts"][role]["sha256"]) == EXPECTED_RAW[role]
                for role in ("ELF", "PRG", "profile")),
            "v2.0 public scope observed another product")
    path = BUILD / "owner-scope-result.json"
    path.write_bytes(canonical(value))
    print("v2.1 public product: exact renderer reproduction scope PASS; private evidence inputs=0")


def public_acceptance_projection() -> dict[str, Any]:
    """Exact qualified ELF identity, with its actual section/owner geometry.

    This is a reproduction check, not a new product qualification. The device
    and renderer-card evidence selects the comparison identity; no private
    receipt is read by compilation or by this check.
    """
    from elf_truth import ElfTruth
    require((ELF.stat().st_size, sha(ELF)) == EXPECTED_RAW["ELF"],
            "acceptance requires the exact frozen renderer ELF")
    truth = ElfTruth.read(ELF, llvm_readobj=ROOT/"tools/llvm-mos/bin/llvm-readobj")
    renderer = truth.section(".lisp65_rt_l65e")
    limit = truth.symbol("__lisp65_error_overlay_max_bytes").value
    require(limit == 1320 and renderer.bytes <= limit, "renderer owner overflow")
    reservations = {
        ".lisp65_c2_terminal_return_raw_owner": (0xB582, 16),
        ".lisp65_c2_input_raw_owner": (0xBC90, 112),
    }
    for name, expected in reservations.items():
        section = truth.section(name)
        require((section.address, section.bytes) == expected,
                "fixed raw owner missing or displaced: " + name)
    return {"authority": {"mode": "exact-qualified-pair-reproduction",
                          "ELF": bind(ELF)},
            "renderer": {"bytes": renderer.bytes, "limit": limit,
                         "remaining": limit-renderer.bytes},
            "raw_reservations": reservations,
            "allocatable_sections": [
                {"name": row.name, "vma": row.address, "bytes": row.bytes}
                for row in truth.sections if "SHF_ALLOC" in row.flags]}


def write_public_acceptance() -> dict[str, Any]:
    observed = {"PRG": bind(PRG), "ELF": bind(ELF),
                "profile": bind(PROFILE)}
    for role, identity in observed.items():
        require((identity["bytes"], identity["sha256"]) == EXPECTED_RAW[role],
                f"public v2.0 acceptance {role} differs from sealed raw link")
    projection = public_acceptance_projection()
    def validate_identity(rows, private_inputs):
        require(private_inputs == 0 and set(rows) == set(EXPECTED_RAW)
                and all((rows[k]['bytes'], rows[k]['sha256']) == target
                        for k, target in EXPECTED_RAW.items()),
                'reproduction identity or input boundary differs')
    validate_identity(observed, 0)
    rejected = []
    for role in EXPECTED_RAW:
        trial = {k: dict(v) for k, v in observed.items()}
        trial[role]['sha256'] = '0' * 64
        try:
            validate_identity(trial, 0)
        except RuntimeError:
            rejected.append(role + '-identity-differs')
        else:
            raise RuntimeError('acceptance identity mutation survived: ' + role)
    try:
        validate_identity(observed, 1)
    except RuntimeError:
        rejected.append('private-evidence-added')
    else:
        raise RuntimeError('acceptance input-boundary mutation survived')
    value = {
        "format": "lisp65-v2.0-public-artifact-acceptance-v1",
        "status": "PASS", "private_evidence_inputs": 0,
        "rule": ("the public producer must reproduce the Ship-sealed raw "
                 "pair before artifact-only Completion proves every role"),
        "raw_pair": {name: observed[name] for name in ("PRG", "ELF")},
        "profile": observed["profile"], "static_plane": bind(CODE),
        **projection,
        "sealed_artifact_set_sha256":
            authority()["sealed_product_artifact_set_sha256"],
        "mutations_rejected": rejected,
    }
    PUBLIC_ACCEPTANCE.write_bytes(canonical(value))
    print("v2.1 public product: exact renderer reproduction acceptance PASS; private evidence inputs=0")
    return value


def public_delivered_input() -> dict[str, Any]:
    """Execute the packed input-consumer wall from live source and final ELF."""
    configure_card()
    strip = CARD.STRIP
    price = strip.CHAIN.PRICE
    ledger = price.COMPILER._abi_ledger("dialect-v2", None)
    client_rows = [Path(raw) for raw in load(MANIFEST)["sources"]
                   if Path(raw).name == "stdlib-read-line.lisp"]
    require(len(client_rows) == 1 and client_rows[0].is_file(),
            "public delivered client source is not unique")
    client_source = client_rows[0]

    def object_rows(key: str, manifest_path: Path) -> list[dict[str, Any]]:
        manifest = load(manifest_path)
        blob = (PLANE_ROOT / "product" / f"{key}.code.bin").read_bytes()
        require(len(blob) == int(manifest["code_bytes"]),
                f"public object blob extent drift: {key}")
        rows: list[dict[str, Any]] = []
        for entry in manifest.get("entries", []):
            if not isinstance(entry, dict) or entry.get("kind") != "function":
                continue
            start, length = int(entry["blob_offset"]), int(entry["length"])
            code = price.BYTECODE.decode_code_object(blob[start:start + length])
            instructions: list[dict[str, Any]] = []
            pc = 0
            while pc < len(code.payload):
                here = pc
                op, operand, pc = price.BYTECODE.decode_instruction(
                    code.payload, pc, profile_id="dialect-v2",
                    abi_ledger=ledger)
                instructions.append({"pc": here, "mnemonic": op.mnemonic,
                                     "operand": operand})
            rows.append({"name": entry["name"], "instructions": instructions})
        return rows

    sites: list[dict[str, Any]] = []
    for key, _role, manifest in strip.candidate_specs():
        for function in object_rows(key, manifest):
            previous: dict[str, Any] | None = None
            for instruction in function["instructions"]:
                operand = instruction["operand"]
                if (instruction["mnemonic"] == "CALLPRIM"
                        and isinstance(operand, tuple)
                        and operand == (60, 1)):
                    require(previous is not None
                            and previous["mnemonic"] == "PUSHI8"
                            and previous["operand"] in (0, 1, 2, 3),
                            "public key-event mode is not statically bound")
                    mode = int(previous["operand"])
                    sites.append({"image": key, "caller": function["name"],
                        "pc": instruction["pc"], "mode": mode,
                        "sink": ("c2_kernal_input_take" if mode in (2, 3)
                                 else "public-hardware-queue")})
                previous = instruction
    sites.sort(key=lambda row: (row["image"], row["caller"], row["pc"]))
    require([(row["caller"], row["mode"]) for row in sites] == [
                ("%read-line-loop", 1), ("%rl-put", 3), ("%rl-render", 2)],
            "public key-source population drift")
    client_text = client_source.read_text(encoding="utf-8")
    state_form = "(state (list head head head 0 0 0 columns row nil))"
    main_route = """(if (nthcdr 8 state)
                    (%rl-render nil 0 0 0 0 -1)
                    (key-event 1))"""
    history_route = (
        "(if (car (nthcdr 8 state)) command (%read-line-loop state))")
    require(client_text.count(state_form) == 1
            and client_text.count(main_route) == 1
            and history_route in client_text,
            "public delivered lifecycle is not source-derivable")
    lifecycle = {"status":
            "PASS: DELIVERED STATE SELECTS RING WITHOUT HISTORY",
        "candidate": {"bytes": len(client_text.encode()),
            "sha256": hashlib.sha256(client_text.encode()).hexdigest()},
        "state_cells": 9, "ring_selector": "(nthcdr 8 state)",
        "ring_selector_value": "one-cell suffix containing NIL",
        "history_selector": "(car (nthcdr 8 state))",
        "history_selector_value": "NIL",
        "selected_main_route": "key-event mode 2 through %rl-render",
        "selected_batch_route": "key-event mode 3 through %rl-put",
        "disarmed_fallback_retained": "public key-event mode 1"}
    require(lifecycle["state_cells"] == 9
            and lifecycle["selected_main_route"] ==
                "key-event mode 2 through %rl-render"
            and lifecycle["selected_batch_route"] ==
                "key-event mode 3 through %rl-put",
            "public delivered lifecycle drift")
    active = [row for row in sites if row["mode"] in (2, 3)]
    fallback = [row for row in sites if row["mode"] == 1]
    key_sources = {"status":
            "PASS: ACTIVE DELIVERED KEY SOURCES RESOLVE EXACTLY TO RING TAKE",
        "all_syntactic_sites": sites, "active_lifecycle_sites": active,
        "disarmed_fallback": fallback,
        "active_sink_set": ["c2_kernal_input_take"],
        "lifecycle": lifecycle, "lifecycle_source": bind(client_source),
        "rule": ("derive every syntactic key-event site and the active "
                 "subset from the public delivered lifecycle")}
    require(len(active) == 2 and len(fallback) == 1
            and {row["sink"] for row in active} == {"c2_kernal_input_take"}
            and fallback[0]["sink"] == "public-hardware-queue",
            "public active key-source set drift")
    printable = "0123456789" * 9 + "abc"
    events = [ord(char) for char in printable] + [13]
    _truth, machine, meta = strip.V19_CONSUMER.FINAL.linked_consumer(ELF)
    symbols = meta["ring_symbols"]
    base = symbols["C2K_INPUT_RING_BASE"]
    memory = {symbols["C2K_INPUT_RING_HEAD"]: len(events),
              symbols["C2K_INPUT_RING_TAIL"]: 0,
              symbols["C2K_INPUT_EVENTS_RAW"]: len(events),
              symbols["C2K_INPUT_EVENTS_SEEN"]: len(events),
              symbols["C2K_INPUT_EVENTS_STORED"]: len(events),
              symbols["C2K_INPUT_EVENTS_TAKEN"]: 0}
    memory.update({base + index: code for index, code in enumerate(events)})
    modes = [2, *([3] * (len(events) - 2)), 2]
    observed: list[int] = []
    cycles = 0
    for mode in modes:
        value, used, _instructions = machine.run(mode, memory)
        observed.append(value); cycles += used
    counters = {name: memory[symbols[f"C2K_INPUT_EVENTS_{name.upper()}"]]
                for name in ("raw", "seen", "stored", "taken")}
    require(observed == events and counters == {name: 94 for name in counters},
            "public delivered input wall drift")
    wall = {"status": "PASS: DELIVERED ROUTE DRAINS FINAL ELF RING",
        "source": bind(client_source), "ELF": bind(ELF),
        "physical_events": 94, "printable_characters": len(printable),
        "result": printable, "key_modes": modes, "counters": counters,
        "linked_consumer": meta, "linked_consumer_cycles": cycles,
        "observed_red": None}
    return {"key_sources": key_sources, "host_wall": wall}


def build_link() -> dict[str, Any]:
    require(STATIC_RECEIPT.is_file() and not BUILD.exists(),
            "v2.0 public link lifecycle drift")
    load_product_modules()
    PUBLIC_INVOCATION.write_bytes(canonical({"status": "INVOKED",
        "authority": {"public-current-source": True,
                      "private_evidence_inputs": 0}}))
    output = run_child("_produce")
    observed = {"PRG": bind(PRG), "ELF": bind(ELF), "profile": bind(PROFILE)}
    for role, identity in observed.items():
        require((identity["bytes"], identity["sha256"]) == EXPECTED_RAW[role],
                f"public v2.0 {role} differs from sealed raw link")
    scope_output = run_child("_scope")
    scope = load(BUILD / "owner-scope-result.json")
    require(scope["status"] == "PASS", "v2.0 public scope red")
    acceptance_output = run_child("_public_accept")
    acceptance = load(PUBLIC_ACCEPTANCE)
    delivered = public_delivered_input()
    value = {"format": "lisp65-v2.0-public-link-v1",
        "status": "PASS: V2.0 PUBLIC A+B SOURCE LINK",
        "private_evidence_inputs": 0, "WPLTO_runs": 1, "product_links": 1,
        "artifacts": observed,
        "qualification": {"scope": bind(BUILD / "owner-scope-result.json"),
            "acceptance": bind(PUBLIC_ACCEPTANCE)},
        "process_witness": {"produce_lines": len(output.splitlines()),
            "scope_lines": len(scope_output.splitlines()),
            "acceptance_lines": len(acceptance_output.splitlines())},
        "configuration": {"Capture": "armed-native-read-line",
            "native_prompt_editor": True, "native_INIT_L65": True,
            "recovery_quiescence_A0": True, "Comfort": False,
            "Matcher_Blink": False, "diagnostic": False},
        "final_product": {"packed_product": delivered}}
    LINK_RECEIPT.write_bytes(canonical(value))
    print("v2.0 public product: LINK PASS WPLTO=1 evidence=0")
    return value


def source_preflight() -> dict[str, Any]:
    """Resolve all real compiler roots before either reproduction spends LTO."""
    configure_card()
    CARD.CHAIN.setup_link_world()
    link = CARD.CHAIN.LINK
    out = PUBLIC / "source-preflight"
    require(not out.exists(), "source preflight is one-shot")
    mapping = link.materialize_candidate_sources(out)
    sources = link.projected_source_list(mapping, link.predecessor_features())
    profile = (ROOT / "config/c2-v210-renderer-profile.txt").read_text().splitlines()
    expected = {line.split("=", 1)[1].rsplit(":", 1)[0]: line.rsplit(":", 1)[1]
                for line in profile if line.startswith("input_sha256=")}
    normalized = lambda p: (Path(p).name if "generated-product-sources" in Path(p).parts
                            else Path(p).relative_to(ROOT).as_posix())
    expected_by_name = {(Path(p).name if "generated-product-sources" in Path(p).parts else p): digest
                        for p, digest in expected.items()}
    require(len(expected_by_name) == len(expected), "ambiguous renderer input identity")
    rows = []
    for raw in sources:
        path = Path(raw)
        key = normalized(path)
        require(key in expected_by_name and sha(path) == expected_by_name[key],
                "compiler source differs from frozen renderer: " + key)
        rows.append(bind(path))
    compiled = {normalized(Path(p)) for p in sources}
    auxiliary = set(expected_by_name) - compiled
    require(auxiliary == {"src/c2_kernal_window_equates.inc"},
            "unclassified non-translation-unit input")
    for name in auxiliary:
        require(sha(ROOT/name) == expected_by_name[name], "auxiliary source drift")
    product = importlib.import_module("c2_product_substitution_link")
    product.write_product_linker_sources(out, link.predecessor_features())
    expected_linker = [line.split("=", 1)[1] for line in profile
                       if line.startswith("linker_sha256=")]
    require(len(expected_linker) == 1 and sha(out/"c2-substitution.ld") == expected_linker[0],
            "public linker source differs from frozen renderer")
    value = {"status": "PASS", "compiler_invocations": 0,
             "producer_output": source_preflight_path().relative_to(ROOT).as_posix(),
             "compiler_sources": compiler_projection(sources, mapping),
             "sources": rows, "auxiliary_inputs": [bind(ROOT/p) for p in sorted(auxiliary)],
             "feature_count": len(link.predecessor_features()),
             "linker": bind(out/"c2-substitution.ld")}
    source_preflight_path().write_bytes(canonical(value))
    # Exercise the actual loader installed at LINK.child's pre-compiler seam.
    require(link.load(link.SOURCE_PREFLIGHT) == value, "consumer did not read producer receipt")
    rejected = []
    cases = {"value-count-divergence": copy.deepcopy(value),
             "source-identity-divergence": copy.deepcopy(value),
             "producer-path-divergence": copy.deepcopy(value),
             "projection-omitted": copy.deepcopy(value)}
    cases["value-count-divergence"]["compiler_sources"]["total"] += 1
    cases["source-identity-divergence"]["compiler_sources"]["identities"][0]["sha256"] = "0" * 64
    cases["producer-path-divergence"]["producer_output"] = "historical/source-preflight.json"
    del cases["projection-omitted"]["compiler_sources"]
    try:
        for name, mutant in cases.items():
            source_preflight_path().write_bytes(canonical(mutant))
            try:
                link.load(link.SOURCE_PREFLIGHT)
            except PublicBuildError:
                rejected.append(name)
            else:
                raise PublicBuildError("source preflight mutation survived: " + name)
        link.SOURCE_PREFLIGHT = PUBLIC / "historical-source-preflight.json"
        try:
            link.load(link.SOURCE_PREFLIGHT)
        except PublicBuildError:
            rejected.append("consumer-path-divergence")
        else:
            raise PublicBuildError("consumer path mutation survived")
    finally:
        link.SOURCE_PREFLIGHT = source_preflight_path()
        source_preflight_path().write_bytes(canonical(value))
    (PUBLIC / "source-preflight-consumption.json").write_bytes(canonical({
        "status": "PASS", "producer": bind(source_preflight_path()),
        "consumer": "c2_v200_block3_return_product_card.child:_produce",
        "compiler_sources": value["compiler_sources"],
        "mutations_rejected": rejected, "compiler_invocations": 0}))
    return value


def configure_media() -> None:
    load_product_modules()
    v160 = V180.V160
    v160.CAPACITY.capacity_authority = v160.public_capacity
    v160.FIDELITY.CANDIDATE_STATIC_ROOT = ROOT
    v160.FIDELITY.CANDIDATE_STATIC_PRODUCT = (
        PLANE_ROOT / "product/substitution-artifacts.json")
    v160.FIDELITY.CANDIDATE_PREFLIGHT_ROOT = PREFLIGHT
    v160.FIDELITY.CANDIDATE_PROFILE = PLANE_ROOT / "candidate-profile.json"
    v160.FIDELITY.CANDIDATE_PLANE = PLANE_ROOT / "product"
    v160.configure_public_source_authorities()
    bind_l_full_consumer()
    rm = RELEASE_MEDIA
    media_price = rm.Adapter.PRICE

    class PublicLinkBase:
        SCOPE_RESULT = BUILD / "owner-scope-result.json"
        ACCEPTANCE_RESULT = PUBLIC_ACCEPTANCE

    class PublicLink:
        BASE = PublicLinkBase

    class PublicReleaseCard:
        BUILD = BUILD
        WPLTO = BUILD / "wplto"
        PLANE = PLANE_ROOT
        PRG = PRG
        ELF = ELF
        RECEIPT = LINK_RECEIPT
        STATUS = "PASS: V2.0 PUBLIC A+B SOURCE LINK"
        LINK = PublicLink
        PRODUCT_KEYS = CARD.STRIP.PRODUCT_KEYS

        @staticmethod
        def configure() -> None:
            configure_card()

        @staticmethod
        def patch_link_stack() -> None:
            configure_card()

        @staticmethod
        def setup_link_world() -> tuple[Any, dict[str, Any], dict[str, object]]:
            configure_card()
            return CARD.CHAIN.setup_link_world()

    class PublicProductCard(PublicReleaseCard):
        pass

    class PublicAdapter(PublicProductCard):
        PRICING_RECEIPT = media_price.RECEIPT
        PRICE = media_price

    def public_pair() -> dict[str, Any]:
        pair = {"PRG": bind(PRG), "ELF": bind(ELF)}
        for role, identity in pair.items():
            require((identity["bytes"], identity["sha256"]) ==
                    EXPECTED_RAW[role],
                    f"public v2.0 media {role} differs from sealed raw link")
        return pair

    def public_media_authority() -> dict[str, Any]:
        link = load(LINK_RECEIPT)
        require(link["status"] == PublicReleaseCard.STATUS
                and link["private_evidence_inputs"] == 0
                and link["artifacts"] == {
                    "PRG": public_pair()["PRG"],
                    "ELF": public_pair()["ELF"],
                    "profile": bind(PROFILE)},
                "public v2.0 media link authority drift")
        return {"authority": "public-v2.0-artifact-completion",
            "private_evidence_inputs": 0,
            "link": bind(LINK_RECEIPT),
            "scope": bind(PublicLinkBase.SCOPE_RESULT),
            "acceptance": bind(PublicLinkBase.ACCEPTANCE_RESULT)}

    rm.CARD = PublicReleaseCard
    rm.ReleaseCardAdapter = PublicReleaseCard
    rm.ProductCard = PublicProductCard
    rm.Adapter = PublicAdapter
    values = {
        "BUILD": PUBLIC / "product-link",
        "WPLTO": BUILD / "wplto",
        "STATIC": PUBLIC / "product-link/inputs/static-plane",
        "TARGET": PUBLIC / "product-link/canonical-product",
        "SHARED": PUBLIC / "product-link/shared-system",
        "RECEIPT": PUBLIC / "unused-media-receipt.json",
        "SESSION": PUBLIC / "unused-release-session.json",
        "PRODUCT_REMOTE": "LISP65.D81",
        "PRODUCT_ID": 0x4A1713AB,
        "PLANE_BYTES": 47795,
        "EXPECTED": {key: value for key, value in EXPECTED_RAW.items()
                     if key in ("PRG", "ELF")},
        "STATUS": "PASS: V2.0.0 PUBLIC RELEASE MEDIA READY",
        "FORMAT": "lisp65-c2-v200-public-release-media-v1",
        "SESSION_FORMAT": "lisp65-c2-v200-public-no-device-session-v1",
    }
    for name, value in values.items():
        setattr(rm, name, value)
    rm.accepted_pair = public_pair
    rm.authority = public_media_authority
    rm.configure()
    # The public package carries the five tracked external library images.
    # Bind that input at the final media producer rather than inheriting a
    # path from the sealed development checkout.
    block3_media = rm.MEDIA.BASE.BASE.M
    block3_media.CARD.PRICE.BUILD = EXTERNAL_IMAGES
    block3_media.R10_MEDIA.LIBRARY_SOURCE = EXTERNAL_IMAGES
    block3_media.MEDIA.LIBRARY_SOURCE = EXTERNAL_IMAGES
    rm.MEDIA.BASE.BASE.PRICE.STDLIB_SUITE = PUBLIC_GENERATION_SUITE


def complete_and_media() -> dict[str, Any]:
    # The input is a fully finalized renderer pair. Re-entering the historical
    # seed Completion pipeline would repeat the already-attributed R2 defect.
    import c2_v210_public_media
    configure_card()
    return c2_v210_public_media.pack(sys.modules[__name__])


def historical_v200_completion_not_selected() -> dict[str, Any]:
    configure_media()
    RELEASE_MEDIA.MEDIA.BASE.build()
    delivery = RELEASE_MEDIA.MEDIA.BASE.BASE
    media = delivery.M.MEDIA
    source = load(media.MANIFEST)
    require(source["artifact_count"] == len(source["artifacts"]) == 19,
            "v2.0 public media role count drift")
    rows = []
    sealed = authority()["sealed_roles"]
    for row in source["artifacts"]:
        identity = bind(ROOT / row["path"])
        require(row["role"] in sealed
                and (identity["bytes"], identity["sha256"]) ==
                    (sealed[row["role"]]["bytes"], sealed[row["role"]]["sha256"]),
                f"public v2.0 role differs from sealed target: {row['role']}")
        rows.append(dict(row))
    value = {"format": FORMAT, "status": STATUS,
        "selector": "v2.1-renderer-f011-native",
        "private_evidence_inputs": 0, "artifact_count": 19,
        "artifact_set_sha256": artifact_set(rows),
        "product_build_id": source["product_build_id"],
        "profile_build_id": source["profile_build_id"],
        "artifacts": rows,
        "lifecycle": {"WPLTO_runs": 1, "product_links": 1,
            "completion_product_rebuilds": 0, "media_builds": 2},
        "completion": bind(delivery.M.BASE.MEDIA.CAN.RECEIPTS /
                           "artifact-completion.json"),
        "packed": {"product": bind(media.PRODUCT_D81),
                   "work": bind(media.WORK_D81)},
        "stager": load(RELEASE_MEDIA.RECEIPT)
            ["packed_artifact_closure"]["stager_gate"]}
    require(value["artifact_set_sha256"] ==
                authority()["sealed_product_artifact_set_sha256"],
            "v2.0 public artifact set differs from seal")
    MANIFEST_OUT.write_bytes(canonical(value))
    print("v2.0 public product: MEDIA PASS roles=19")
    return value


def check() -> dict[str, Any]:
    static, link, selected = load(STATIC_RECEIPT), load(LINK_RECEIPT), load(MANIFEST_OUT)
    require(static["private_evidence_inputs"] == 0
            and link["private_evidence_inputs"] == 0
            and link["WPLTO_runs"] == link["product_links"] == 1
            and selected["status"] == STATUS
            and selected["artifact_count"] == len(selected["artifacts"]) == 19
            and selected["artifact_set_sha256"] ==
                authority()["sealed_product_artifact_set_sha256"],
            "v2.0 public selected-product closure drift")
    for row in selected["artifacts"]:
        require(bind(ROOT / row["path"]) == {
            key: row[key] for key in ("path", "bytes", "sha256")},
            f"v2.0 public selected artifact drift: {row['role']}")
    print("v2.0 public product: FULL PASS roles=19 evidence=0")
    return selected


def build() -> None:
    require(authority().get("producer_preflight_complete") is True,
            "renderer public producer is not armed; no compiler invocation")
    materialize_plane()
    source_preflight()
    build_link()
    complete_and_media()
    check()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "check", "_produce",
                                            "_scope", "_accept",
                                            "_public_accept"))
    action = parser.parse_args().action
    if action == "build":
        build()
    elif action == "check":
        check()
    else:
        produce_child(action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v2.0 public product: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
