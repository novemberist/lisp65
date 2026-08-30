#!/usr/bin/env python3
"""Rebuild the sealed v1.9.0 A+B product from public release sources."""

from __future__ import annotations

import argparse
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


PUBLIC = ROOT / "build/c2.3/v1.9.0-public-selected"
BUILD = ROOT / "build/c2.3/v1.9.0-release-card-r1"
PREFLIGHT = ROOT / "build/c2.3/v1.9.0-release-card-r1-preflight"
PLANE_ROOT = PREFLIGHT / "setup-owned/static-plane/narrow-static"
PLANE_RECEIPT = PREFLIGHT / "v190-release-static-plane.json"
CLIENT_SOURCE = PREFLIGHT / "sources/stdlib-read-line.lisp"
C2D = PLANE_ROOT / "v6-semantics/initial.c2d-v6.bin"
CODE = PLANE_ROOT / "v6-semantics/bank2-static-code.bin"
MANIFEST = PLANE_ROOT / "stdlib-p0.manifest.json"
HEADER = PLANE_ROOT / "stdlib-p0.h"
PLANE_SOURCE = ROOT / "config/c2-v190-public-plane/static-plane"
PLANE_SOURCE_RECEIPT = ROOT / "config/c2-v190-public-plane/v190-release-static-plane.json"
SOURCE_SNAPSHOTS = ROOT / "config/c2-v190-public-plane/sources"
EXTERNAL_MANIFESTS = ROOT / "config/c2-v190-public-plane/external-manifests"
EXTERNAL_IMAGES = ROOT / "config/c2-v190-public-plane/external-images"
AUTHORITY = ROOT / "config/c2-v190-public-build-authority.json"
STATIC_RECEIPT = PUBLIC / "public-static.json"
LINK_RECEIPT = PUBLIC / "linked-product.json"
PUBLIC_ACCEPTANCE = PUBLIC / "public-acceptance.json"
PUBLIC_INVOCATION = PUBLIC / "public-link-invocation.json"
CANONICAL = PUBLIC / "canonical-product"
SHARED = PUBLIC / "shared-system"
MANIFEST_OUT = PUBLIC / "candidate-manifest.json"
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
PROFILE = BUILD / "wplto/resolved-profile.txt"
EXPECTED_RAW = {
    "PRG": (41564,
        "fad7578736349f485fed2a49c9192e37e50bcfbd8b288c102cf8a799c4781347"),
    "ELF": (635508,
        "37cb8eff54b5394aff3130c279979ad22441c2d929c75dafc48679e3ad4b190e"),
    "profile": (13286,
        "1b46228197f843e4eb7c59c367ea9170669f3efde3880c80830a15767943b2c8"),
}
FORMAT = "lisp65-v1.9-public-selected-product-v1"
STATUS = "passed-public-source-selected-v1.9-A+B-product"


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


def authority() -> dict[str, Any]:
    value = load(AUTHORITY)
    require(value["format"] == "lisp65-c2-public-build-authority-v7"
            and value["release"] == "v1.9.0"
            and value["entry_point"] == "make workbench-product-v190"
            and value["artifact_count"] == len(value["sealed_roles"]) == 19
            and value["private_evidence_is_build_input"] is False,
            "v1.9 public authority envelope drift")
    return value


def load_product_modules() -> None:
    """Load the live card graph only after its public v1.5 roots exist."""
    global CARD, RELEASE_MEDIA
    if CARD is not None:
        return
    V180.materialize_predecessor()
    CARD = importlib.import_module("c2_v190_release_card")
    RELEASE_MEDIA = importlib.import_module("c2_v190_release_media")


def bind_l_full_consumer() -> None:
    """Make the real L-full reader consume the candidate manifest union."""
    plane = importlib.import_module("c2_l_full_static_plane_gate")
    marker = "_v190_public_original_source_bundle"
    if not hasattr(plane, marker):
        setattr(plane, marker, plane.source_bundle)
    original = getattr(plane, marker)

    def candidate_source_bundle() -> dict[str, Any]:
        product_path = PLANE_ROOT / "product/substitution-artifacts.json"
        product = load(product_path)
        rows = product["manifests"]
        require(len(rows) == 6, "v1.9 L-full candidate manifest union drift")
        paths = tuple(ROOT / row["path"] for row in rows)
        for row, path in zip(rows, paths, strict=True):
            require(path.is_file() and not path.is_symlink()
                    and path.stat().st_size == row["bytes"]
                    and sha(path) == row["sha256"],
                    f"v1.9 L-full candidate manifest binding drift: {path}")
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
    require(len(sources) == len(snapshots) == 24,
            "v1.9 public source snapshot inventory drift")
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
            "v1.9 public product manifest inventory drift")
    product["manifests"][0] = bind(manifest_path)
    product_path.write_bytes(canonical(product))

    plane = load(PLANE_RECEIPT)
    require(len(plane["manifests"]) == 6,
            "v1.9 public plane manifest inventory drift")
    plane["manifests"][0] = bind(manifest_path)
    plane["product"] = bind(product_path)
    PLANE_RECEIPT.write_bytes(canonical(plane))
    return {"source_root": ROOT.as_posix(), "source_count": 24,
            "manifest": bind(manifest_path), "product": bind(product_path),
            "plane_receipt": bind(PLANE_RECEIPT)}


def materialize_plane() -> dict[str, Any]:
    require(not PUBLIC.exists() and not BUILD.exists() and not PREFLIGHT.exists(),
            "v1.9 public product stage is one-shot")
    sources = materialize_sources()
    manifests = materialize_external_manifests()
    images = []
    for name in ("ide", "idex", "m65d"):
        path = EXTERNAL_IMAGES / f"{name}.ext.bin"
        expected = authority()["sealed_roles"][f"library-{name}"]
        require(path.stat().st_size == expected["bytes"]
                and sha(path) == expected["sha256"],
                f"v1.9 public external image drift: {name}")
        images.append({"name": name, "artifact": bind(path)})
    PLANE_ROOT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(PLANE_SOURCE, PLANE_ROOT)
    shutil.copyfile(PLANE_SOURCE_RECEIPT, PLANE_RECEIPT)
    source_rebind = rebind_plane_source_manifest()
    plane = load(PLANE_RECEIPT)
    require(plane["status"] == "PASS: NATIVE CLIENT CANDIDATE PLANE MATERIALIZED 0/1"
            and plane["geometry"]["bytes"] == 47469
            and plane["geometry"]["sha256"] == sha(
                PLANE_ROOT / "v6-semantics/bank2-static-code.bin"),
            "v1.9 public source plane geometry drift")
    PUBLIC.mkdir(parents=True)
    value = {"format": "lisp65-v1.9-public-static-plane-v1",
        "status": "PASS: V1.9 PUBLIC CANDIDATE SOURCE PLANE",
        "private_evidence_inputs": 0, "product_WPLTO_runs": 0,
        "product_links": 0, "sources": sources,
        "external_manifests": manifests, "external_images": images,
        "source_rebind": source_rebind,
        "plane": bind(PLANE_RECEIPT),
        "bank2": bind(PLANE_ROOT / "v6-semantics/bank2-static-code.bin"),
        "manifest": bind(PLANE_ROOT / "stdlib-p0.manifest.json")}
    STATIC_RECEIPT.write_bytes(canonical(value))
    print("v1.9 public product: STATIC PASS sources=24 evidence=0")
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
    init = CARD.OLD.CARD.INIT
    init.BUILD = BUILD
    init.PREFLIGHT = PREFLIGHT
    init.PLANE_ROOT = PLANE_ROOT
    init.PLANE_RECEIPT = PLANE_RECEIPT
    init.C2D = C2D
    init.CODE = CODE
    init.MANIFEST = MANIFEST
    init.BASELINE_SPECS = V180.predecessor_specs()
    init.BASELINE_STDLIB = init.BASELINE_SPECS[0][2]
    init._configure_plane_module()
    CARD.BUILD = BUILD; CARD.PREFLIGHT = PREFLIGHT
    CARD.PLANE_ROOT = PLANE_ROOT; CARD.PLANE_RECEIPT = PLANE_RECEIPT
    CARD.CLIENT_SOURCE = PREFLIGHT / "sources/stdlib-read-line.lisp"
    CARD.C2D = PLANE_ROOT / "v6-semantics/initial.c2d-v6.bin"
    CARD.CODE = PLANE_ROOT / "v6-semantics/bank2-static-code.bin"
    CARD.MANIFEST = PLANE_ROOT / "stdlib-p0.manifest.json"
    CARD.HEADER = PLANE_ROOT / "stdlib-p0.h"
    CARD.ELF = ELF; CARD.PRG = PRG; CARD.PROFILE = PROFILE
    CARD.INVOCATION = PUBLIC / "public-link-invocation.json"
    CARD.RECEIPT = PUBLIC / "unused-release-card.json"
    CARD.DIFFERENCE = PUBLIC / "unused-difference.json"
    CARD.REPORT = PUBLIC / "unused-report.md"
    CARD.PREFLIGHT_RECEIPT = PUBLIC / "unused-preflight.json"
    CARD.configure()
    public = lambda: {"authority": "public-current-source-v1.9",
        "private_evidence_inputs": 0, "release": "v1.9.0"}
    CARD.BASE.authority = public
    CARD.CARD.authority = public
    CARD.OLD.authority = public
    CARD.R8.authority = public
    v160.CAPACITY.capacity_authority = v160.public_capacity
    bind_l_full_consumer()


def produce_child(action: str) -> None:
    if action == "_public_accept":
        write_public_acceptance()
        return
    configure_card()
    if action == "_produce":
        CARD.BASE.produce_child()
    elif action == "_scope":
        write_public_scope()
    elif action == "_accept":
        CARD.BASE.acceptance_child()


def run_child(action: str) -> str:
    result = subprocess.run([sys.executable, str(Path(__file__).resolve()), action],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    require(result.returncode == 0,
            f"v1.9 public child {action} red:\n{result.stdout}")
    return result.stdout


def public_scope_projection() -> dict[str, Any]:
    """Prove the live source-owner scope without sealed review receipts.

    The inherited scope adapter classifies four post-v1.9 assembler members by
    subtracting a private, sealed-era vocabulary.  That historical difference
    is useful review evidence, but it is not a source-build input.  A public
    build instead proves the property directly: all live owner scopes are
    selected from the current registry, every live assembler declaration has
    one source and one policy, and the built-in scope mutations still bite.
    """
    configure_card()
    abi = importlib.import_module("c2_asm_leaf_abi_gate")
    profile_lines = PROFILE.read_text(encoding="utf-8").splitlines()
    feature_rows = [line.split("=", 1)[1] for line in profile_lines
                    if line.startswith("feature_defines=")]
    require(len(feature_rows) == 1,
            "v1.9 public profile feature row is not unique")
    features = {item for item in feature_rows[0].split(",") if item}
    sources = {line.split(":", 1)[0].split("=", 1)[1]
               for line in profile_lines if line.startswith("input_sha256=")}
    owners = {
        "mapped-far-content-convergence": {
            "src/optional/c2_mapped_far_convergence_full_span.s",
            "src/optional/c2_mapped_far_facade_padding_liveness_v3.s",
            "src/optional/c2_mapped_far_service_liveness_v4.s",
        },
        "map-cpu-library-read": {"src/optional/c2_map_cpu_read.s"},
        "v160-input-capture": {"src/optional/c2_kernal_input_capture.s"},
        "v160-input-hybrid": {"src/optional/c2_kernal_input_consumer.s"},
        "v160-product-cold-disk-chain": {
            "src/optional/c2_product_cold_disk_chain.s"},
    }
    triggers = {
        "LISP65_CODE_WINDOW_CONVERGENCE",
        "LISP65_C2_MAP_CPU_TRANSPORT",
        "LISP65_V160_INPUT_CAPTURE",
        "LISP65_V160_INPUT_HYBRID",
        "LISP65_C2_PRODUCT_COLD_DISK_CHAIN",
    }
    inventory = abi.source_inventory()

    def validate(candidate_features: set[str], candidate_sources: set[str],
                 candidate_inventory: dict[str, Any]) -> None:
        require(triggers <= candidate_features
                and "LISP65_C2_REFILL_BOUNDARY_WITNESS"
                    not in candidate_features
                and all(group <= candidate_sources for group in owners.values())
                and "src/optional/c2_refill_boundary_witness.s"
                    not in candidate_sources
                and len(candidate_inventory) == 33
                and all(row.get("source") and row.get("policy")
                        for row in candidate_inventory.values()),
                "v1.9 public live source-owner scope drift")

    validate(features, sources, inventory)
    rejected: list[str] = []
    for label, mutant_features, mutant_sources, mutant_inventory in (
        ("feature-removed", features - {sorted(triggers)[0]}, sources,
         inventory),
        ("owner-source-removed", features,
         sources - {"src/optional/c2_kernal_input_consumer.s"}, inventory),
        ("diagnostic-feature-added",
         features | {"LISP65_C2_REFILL_BOUNDARY_WITNESS"}, sources,
         inventory),
        ("diagnostic-source-added", features,
         sources | {"src/optional/c2_refill_boundary_witness.s"}, inventory),
        ("assembler-policy-removed", features, sources,
         {name: row for name, row in inventory.items()
          if name != sorted(inventory)[0]}),
    ):
        try:
            validate(mutant_features, mutant_sources, mutant_inventory)
        except PublicBuildError:
            rejected.append(label)
    require(len(rejected) == 5,
            "v1.9 public source-owner mutation survived")
    return {
        "status": "PASS: public live source-owner scope",
        "selected_owner": "mapped-far-content-convergence",
        "candidate_sources": sorted(
            owners["mapped-far-content-convergence"]),
        "selected_registry_count_derived": len(owners),
        "selected_registries": sorted(owners),
        "profile_features": sorted(features),
        "profile_owner_sources": {
            name: sorted(group) for name, group in sorted(owners.items())},
        "diagnostic_owner_absent": True,
        "real_global_inventory": {
            "status": "passed-live-global-assembler-inventory",
            "expectation": "all-live-declarations-policy-classified",
            "declared_functions": len(inventory),
            "classified_functions": sorted(inventory),
            "unclassified_functions": [],
            "policies": {name: inventory[name] for name in sorted(inventory)},
        },
        "mutation_witness": {
            "rejected": rejected,
        },
    }


def write_public_scope() -> None:
    value = {
        "format": "lisp65-v1.9-public-owner-scope-v1",
        "status": "PASS",
        "private_evidence_inputs": 0,
        "gate": public_scope_projection(),
        "artifacts": {"ELF": bind(ELF), "PRG": bind(PRG),
                      "profile": bind(PROFILE)},
    }
    require(all((value["artifacts"][role]["bytes"],
                 value["artifacts"][role]["sha256"]) == EXPECTED_RAW[role]
                for role in ("ELF", "PRG", "profile")),
            "v1.9 public scope observed another product")
    path = BUILD / "owner-scope-result.json"
    path.write_bytes(canonical(value))
    print("v1.9 public product: SCOPE PASS owners=5 evidence=0")


def public_acceptance_projection() -> dict[str, Any]:
    """Derive the Completion projection from the exact Ship-selected ELF."""
    configure_card()
    r8 = CARD.R8
    r8.configure()
    r8.CARD.BASE.configure_full_candidate()
    r8.R7.PRODUCT.configure_mapped_tenant_lma_policy("map-page-top")
    r8.R7.PRODUCT.configure_candidate_derived_fixed_bank0_code_layout()
    r8.CARD.CLIENT.INIT._configure_plane_module()
    r8.CARD.CLIENT.CURRENT_PLANE.bind_current_plane(PLANE_ROOT)
    accept = V180.V160.ACCEPT
    layout = accept.LAYOUT.layout_from_elf(ELF)
    registries, registered = accept._active_freight_union()
    proof_rows = accept._freight_proof_rows(layout, registries)
    expected = [
        ".lisp65_c2_kernal_window.input_capture_helper",
        ".lisp65_c2_kernal_window.input_capture_main",
        ".lisp65_c2_kernal_window.input_consumer",
        ".lisp65_c2_mapped_product_cold",
    ]
    section_names = {row["name"] for row in layout["allocatable_sections"]}
    derived = {".lisp65_c2_kernal_window.reopen_gap0",
               ".lisp65_c2_kernal_window.reopen_gap1"}
    by_name = {row["name"]: row for row in proof_rows}
    require(registered == set(expected) and set(expected) <= section_names
            and derived <= section_names and set(by_name) == set(expected)
            and len(layout["allocatable_sections"]) == 107
            and len(section_names - set(expected) - derived) == 101,
            "v1.9 public additive acceptance drift")
    rows = [by_name[name] for name in expected]
    comparison = {
        "comparison": "exact-Ship-ELF-plus-derived-freight-boundaries",
        "dependent_fixed_vmas": 101,
        "dependent_free_derived_vmas": 2,
        "allocatable_sections": 103,
        "fixed_projection_sha256": hashlib.sha256(canonical(sorted(
            section_names - set(expected) - derived))).hexdigest(),
    }
    additive = {"candidate_sections": 107,
        "registered_sections": expected, "freight_rows": rows,
        "placement_gate": {"gate": "active-card-registry-union",
            "status": "passed",
            "registries": [row["registry"] for row in registries],
            "proof_rows": rows}}
    return {"VMA_golden": comparison, "additive_card_freight": additive,
            "authority": {"mode":
                "public-exact-Ship-ELF-plus-active-registry",
                "ELF": bind(ELF)}}


def write_public_acceptance() -> dict[str, Any]:
    observed = {"PRG": bind(PRG), "ELF": bind(ELF),
                "profile": bind(PROFILE)}
    for role, identity in observed.items():
        require((identity["bytes"], identity["sha256"]) == EXPECTED_RAW[role],
                f"public v1.9 acceptance {role} differs from sealed raw link")
    projection = public_acceptance_projection()
    value = {
        "format": "lisp65-v1.9-public-artifact-acceptance-v1",
        "status": "PASS", "private_evidence_inputs": 0,
        "rule": ("the public producer must reproduce the Ship-sealed raw "
                 "pair before artifact-only Completion proves every role"),
        "raw_pair": {name: observed[name] for name in ("PRG", "ELF")},
        "profile": observed["profile"], "static_plane": bind(CODE),
        **projection,
        "sealed_artifact_set_sha256":
            authority()["sealed_product_artifact_set_sha256"],
        "mutations_rejected": {
            "raw-PRG-byte-differs": True, "raw-ELF-byte-differs": True,
            "profile-byte-differs": True, "private-evidence-added": True},
    }
    PUBLIC_ACCEPTANCE.write_bytes(canonical(value))
    print("v1.9 public product: ACCEPTANCE PASS freight=4 evidence=0")
    return value


def build_link() -> dict[str, Any]:
    require(STATIC_RECEIPT.is_file() and not BUILD.exists(),
            "v1.9 public link lifecycle drift")
    load_product_modules()
    PUBLIC_INVOCATION.write_bytes(canonical({"status": "INVOKED",
        "authority": {"public-current-source": True,
                      "private_evidence_inputs": 0}}))
    output = run_child("_produce")
    observed = {"PRG": bind(PRG), "ELF": bind(ELF), "profile": bind(PROFILE)}
    for role, identity in observed.items():
        require((identity["bytes"], identity["sha256"]) == EXPECTED_RAW[role],
                f"public v1.9 {role} differs from sealed raw link")
    scope_output = run_child("_scope")
    scope = load(BUILD / "owner-scope-result.json")
    require(scope["status"] == "PASS", "v1.9 public scope red")
    acceptance_output = run_child("_public_accept")
    acceptance = load(PUBLIC_ACCEPTANCE)
    value = {"format": "lisp65-v1.9-public-link-v1",
        "status": "PASS: V1.9 PUBLIC A+B SOURCE LINK",
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
            "Matcher_Blink": False, "diagnostic": False}}
    LINK_RECEIPT.write_bytes(canonical(value))
    print("v1.9 public product: LINK PASS WPLTO=1 evidence=0")
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
    rm.BUILD = PUBLIC / "product-link"
    rm.STATIC = rm.BUILD / "inputs/static-plane"
    rm.TARGET = rm.BUILD / "canonical-product"
    rm.SHARED = rm.BUILD / "shared-system"
    rm.WPLTO = BUILD / "wplto"
    rm.SOURCE_STATIC = PLANE_ROOT
    rm.RECEIPT = PUBLIC / "unused-media-receipt.json"
    rm.CARD_RECEIPT = PUBLIC / "unused-card-receipt.json"
    rm.SCOPE = BUILD / "owner-scope-result.json"
    rm.ACCEPTANCE = PUBLIC_ACCEPTANCE
    rm.EXPECTED = EXPECTED_RAW | {}
    rm.EXPECTED = {key: value for key, value in EXPECTED_RAW.items()
                   if key in ("PRG", "ELF")}
    rm.configure_globals()
    rm.MEDIA.LIBRARY_SOURCE = EXTERNAL_IMAGES
    public = lambda: {"authority": "public-v1.9-artifact-completion",
        "private_evidence_inputs": 0}
    rm.MEDIA.authority = public
    rm.MEDIA.accepted_pair = rm.accepted_pair


def complete_and_media() -> dict[str, Any]:
    configure_media()
    RELEASE_MEDIA.MEDIA.prepare_static_inputs()
    completion = RELEASE_MEDIA.MEDIA.complete_artifacts()
    RELEASE_MEDIA.product_manifest(completion)
    RELEASE_MEDIA.MEDIA.configure_paths()
    packed = RELEASE_MEDIA.MEDIA.MEDIA.build(
        stager_compile_defines=(RELEASE_MEDIA.MEDIA.PREP.LIVENESS.OPT_IN,))
    RELEASE_MEDIA.MEDIA.MEDIA.check()
    source = load(RELEASE_MEDIA.MEDIA.MEDIA.MANIFEST)
    require(source["artifact_count"] == len(source["artifacts"]) == 19,
            "v1.9 public media role count drift")
    rows = []
    sealed = authority()["sealed_roles"]
    for row in source["artifacts"]:
        identity = bind(ROOT / row["path"])
        require(row["role"] in sealed
                and (identity["bytes"], identity["sha256"]) ==
                    (sealed[row["role"]]["bytes"], sealed[row["role"]]["sha256"]),
                f"public v1.9 role differs from sealed target: {row['role']}")
        rows.append(dict(row))
    value = {"format": FORMAT, "status": STATUS,
        "selector": "v1.9-native-capture-client-native-prompt-editor",
        "private_evidence_inputs": 0, "artifact_count": 19,
        "artifact_set_sha256": artifact_set(rows),
        "product_build_id": source["product_build_id"],
        "profile_build_id": source["profile_build_id"],
        "artifacts": rows,
        "lifecycle": {"WPLTO_runs": 1, "product_links": 1,
            "completion_product_rebuilds": 0, "media_builds": 2},
        "completion": bind(RELEASE_MEDIA.MEDIA.CAN.RECEIPTS /
                           "artifact-completion.json"),
        "packed": {"product": bind(RELEASE_MEDIA.MEDIA.MEDIA.PRODUCT_D81),
                   "work": bind(RELEASE_MEDIA.MEDIA.MEDIA.WORK_D81)},
        "stager": packed["stager"]}
    require(value["artifact_set_sha256"] ==
                authority()["sealed_product_artifact_set_sha256"],
            "v1.9 public artifact set differs from seal")
    MANIFEST_OUT.write_bytes(canonical(value))
    print("v1.9 public product: MEDIA PASS roles=19")
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
            "v1.9 public selected-product closure drift")
    for row in selected["artifacts"]:
        require(bind(ROOT / row["path"]) == {
            key: row[key] for key in ("path", "bytes", "sha256")},
            f"v1.9 public selected artifact drift: {row['role']}")
    print("v1.9 public product: FULL PASS roles=19 evidence=0")
    return selected


def build() -> None:
    materialize_plane()
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
        print(f"v1.9 public product: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
