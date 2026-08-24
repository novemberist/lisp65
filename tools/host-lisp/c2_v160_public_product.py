#!/usr/bin/env python3
"""Rebuild the sealed v1.6 Item-1 product from public source inputs."""

from __future__ import annotations

import argparse
import hashlib
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

import c2_v160_boot_refill_selector_bypass_dual_capacity_replacement_card as CAPACITY  # noqa: E402
import c2_v160_comfort_input_fidelity as FIDELITY  # noqa: E402
import c2_v160_item1_only_candidate as ITEM1  # noqa: E402
import c2_v160_nested_map_swap_media as NESTED_MEDIA  # noqa: E402
import c2_v160_refill_boundary_witness_media_repair as FACADE  # noqa: E402
import c2_v160_r1_stored_world_conversions as ACCEPT  # noqa: E402
import bytecode_p0_stdlib as STD  # noqa: E402
import c2_lite_canonical_product as CAN  # noqa: E402
import c2_lite_media_product as MEDIA  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v112_candidate_media as LIBMEDIA  # noqa: E402
import c2_v150_stager_liveness_successor as LIVENESS  # noqa: E402
import c2_v20_crc_carveout_media as CRC_MEDIA  # noqa: E402
import c2_v20_source_oracle_media as SOURCE_MEDIA  # noqa: E402
import c2_v21_full_span_convergence_card as FULL_SPAN  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


PUBLIC = ROOT / "build/c2.3/v1.6.0-public-selected"
SOURCE = PUBLIC / "source-static"
HISTORICAL = SOURCE / "v1.5.0-public-parent"
HISTORICAL_OUTPUT = HISTORICAL / "build/c2.3/v1.5.0-public-selected"
HISTORICAL_PREFLIGHT = HISTORICAL / "build/c2.3/v1.5.0-release-preflight"
HISTORICAL_OWNERSHIP = HISTORICAL / "build/c2.3/v2.0-ownership-recharter-inputs"
CURRENT_PREFLIGHT = ROOT / "build/c2.3/v1.5.0-release-preflight"
CURRENT_OWNERSHIP = ROOT / "build/c2.3/v2.0-ownership-recharter-inputs"
STATIC_RECEIPT = SOURCE / "public-static.json"
STATIC_HELPER = DRIVER = Path(__file__).resolve().with_name(
    "c2_v160_public_static_from_v150.py")
STATIC_SOURCE_COMMIT = "189fa2e746ecef481db33f24221c41fd35ffbe27"
CANDIDATE = ROOT / "build/c2.3/v1.6-item1-only-candidate-r1"
PREFLIGHT = ROOT / "build/c2.3/v1.6-item1-only-candidate-r1-preflight"
LINK_RECEIPT = PUBLIC / "linked-product.json"
MANIFEST = PUBLIC / "candidate-manifest.json"
AUTHORITY = ROOT / "config/c2-v160-public-build-authority.json"
CANONICAL = PUBLIC / "canonical-product"
SHARED = PUBLIC / "shared-system"
LIBRARY = PUBLIC / "library"
DRIVER = Path(__file__).resolve()
EXPECTED_RAW = {
    "PRG": (41566,
        "4d80051c80473e26f3a8b4582d8e0200ec9d15e5e6faa4e1cd7984e6a97b4f6c"),
    "ELF": (646192,
        "82bc474e61a0ba4691abe52c3f0c8fcf6e26335f533df2d59ddd3ab2f3eba489"),
    "profile": (13207,
        "a873e2158c8107c5a9640656d968af469193a51e02f247c1f582912a4996d737"),
}


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


def run_stage(action: str) -> str:
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0,
            f"v1.6 public {action} stage red:\n{result.stdout}")
    print(result.stdout.strip())
    return result.stdout


def materialize_static_consumer_view() -> dict[str, Any]:
    """Project the fresh historical plane at its manifest-declared paths.

    v1.5 manifests intentionally store checkout-relative ``build/...`` paths.
    Their blobs therefore need a same-path view in the v1.6 checkout; merely
    passing a manifest from another checkout would bind it without letting the
    real consumer read its payload.  Only files named by the plane or its
    transitive JSON closure are copied.
    """
    static = HISTORICAL_PREFLIGHT / "static-plane/narrow-static"
    compiler_sources = HISTORICAL / (
        "build/c2.3/top-level-macro-publication-link95-preflight/"
        "codemod/sources")
    require(static.is_dir() and HISTORICAL_OWNERSHIP.is_dir()
            and compiler_sources.is_dir()
            and not CURRENT_PREFLIGHT.exists()
            and not CURRENT_OWNERSHIP.exists(),
            "public static consumer view is not fresh")
    queue = [path.relative_to(HISTORICAL).as_posix()
             for root in (static, HISTORICAL_OWNERSHIP, compiler_sources)
             for path in sorted(root.rglob("*")) if path.is_file()]
    queue.append("build/equivalence/fasl-test.bin")
    seen: set[str] = set()
    declarations_without_files: set[str] = set()

    def declared_paths(value: Any) -> list[str]:
        if isinstance(value, dict):
            return [path for item in value.values()
                    for path in declared_paths(item)]
        if isinstance(value, list):
            return [path for item in value for path in declared_paths(item)]
        if isinstance(value, str) and value.startswith("build/"):
            return [value]
        return []

    while queue:
        relative = queue.pop()
        if relative in seen:
            continue
        path = Path(relative)
        require(not path.is_absolute() and ".." not in path.parts,
                f"static closure path escapes checkout: {relative}")
        source = HISTORICAL / path
        if not source.exists():
            declarations_without_files.add(relative)
            continue
        require(source.is_file() and not source.is_symlink(),
                f"declared static closure path is not a file: {relative}")
        destination = ROOT / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            require(destination.is_file() and sha(destination) == sha(source),
                    f"static consumer path has a second owner: {relative}")
        else:
            shutil.copyfile(source, destination)
        seen.add(relative)
        if source.suffix == ".json":
            try:
                value = json.loads(source.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                value = None
            if value is not None:
                queue.extend(declared_paths(value))
    require(len(seen) >= 30,
            "public static consumer closure unexpectedly small")
    return {"files": len(seen), "all_content_identical": True,
            "path_authority": "materialized manifest-declared build paths",
            "real_compiler_oracle": bind(
                ROOT / "build/equivalence/fasl-test.bin"),
            "non_materialized_declarations":
                sorted(declarations_without_files)}


def build_source_static() -> dict[str, Any]:
    """Emit the six-image plane from the public v1.5 parent checkout."""
    require(not SOURCE.exists() and not CANDIDATE.exists()
            and not PREFLIGHT.exists(),
            "v1.6 public static stage is one-shot")
    PUBLIC.mkdir(parents=True)
    SOURCE.mkdir()
    clone = subprocess.run(
        ["git", "clone", "--no-local", "--no-checkout", str(ROOT),
         str(HISTORICAL)], cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    require(clone.returncode == 0, f"historical public clone red:\n{clone.stdout}")
    checkout = subprocess.run(
        ["git", "checkout", "--detach", STATIC_SOURCE_COMMIT], cwd=HISTORICAL,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(checkout.returncode == 0,
            f"historical public checkout red:\n{checkout.stdout}")
    resolved = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=HISTORICAL, check=True, text=True,
        stdout=subprocess.PIPE).stdout.strip()
    require(resolved == STATIC_SOURCE_COMMIT,
            "historical public static source identity drift")
    bundled = HISTORICAL / "tools/llvm-mos"
    require(not bundled.exists() and not bundled.is_symlink(),
            "historical public source unexpectedly bundles LLVM-MOS")
    bundled.symlink_to((ROOT / "tools/llvm-mos").resolve(),
                       target_is_directory=True)
    output_relative = HISTORICAL_OUTPUT.relative_to(HISTORICAL)
    run = subprocess.run(
        [sys.executable, str(STATIC_HELPER), "--output", str(output_relative)],
        cwd=HISTORICAL, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(run.returncode == 0,
            f"historical public static emitter red:\n{run.stdout}")
    historical = load(HISTORICAL_OUTPUT / "public-static.json")
    require(historical.get("private_evidence_inputs") == 0
            and historical.get("product_WPLTO_runs") == 0
            and historical.get("product_links") == 0,
            "historical static source boundary drift")
    consumer_view = materialize_static_consumer_view()
    value = {"status": "PASS: V1.6 PUBLIC STATIC SOURCE PLANE",
        "source_commit": STATIC_SOURCE_COMMIT,
        "source_role": "curated-public-v1.5-parent",
        "private_evidence_inputs": 0, "product_WPLTO_runs": 0,
        "product_links": 0, "images": 6,
        "consumer_view": consumer_view,
        "historical_receipt": bind(HISTORICAL_OUTPUT / "public-static.json"),
        "bank2": bind(CURRENT_PREFLIGHT / (
            "static-plane/narrow-static/v6-semantics/"
            "bank2-static-code.bin"))}
    STATIC_RECEIPT.write_bytes(canonical(value))
    print("v1.6 public product: STATIC PASS parent=v1.5 images=6 evidence=0")
    return value


def public_capacity() -> dict[str, Any]:
    """Current source contract, replacing predecessor-world receipts."""
    return {"authority": "public-current-source-capacity-contract",
            "derived_ordinary_floor_bytes": 18,
            "derived_far_floor_bytes": 11}


def configure_public_source_authorities() -> dict[str, Any]:
    """Replace historical forecast receipts with current source contracts."""
    authorities = PUBLIC / "product-inputs/source-authorities"
    authorities.mkdir(parents=True, exist_ok=True)
    full_span = authorities / "full-span-current-source.json"
    full_span.write_bytes(canonical({
        "format": "lisp65-v1.6-public-full-span-authority-v1",
        "status": "passed-current-source-contract-projection",
        "contract": bind(FULL_SPAN.CONTRACT),
        "configuration": bind(FULL_SPAN.CONFIG_DRIVER),
        "private_evidence_inputs": 0,
    }))
    FULL_SPAN.FIX.RECEIPT = full_span
    # The replacement wrapper adds provenance from a historical relocation
    # forecast.  Full-span immediately supersedes every forecast value from
    # its tracked artifact contract, so begin with the source-derived ABI
    # projection and let full-span derive the current freight.
    FULL_SPAN.BASE.projected_contracts = (
        FULL_SPAN.BASE.OLD.projected_contracts)
    return {"full_span": bind(full_span), "private_evidence_inputs": 0}


def configure_item1_link() -> Any:
    static = load(STATIC_RECEIPT)
    require(static.get("private_evidence_inputs") == 0,
            "public static source boundary drift")
    preflight = CURRENT_PREFLIGHT
    static_root = preflight / "static-plane/narrow-static"
    ownership = CURRENT_OWNERSHIP
    CAPACITY.capacity_authority = public_capacity
    FIDELITY.CANDIDATE_STATIC_ROOT = ROOT
    FIDELITY.CANDIDATE_STATIC_PRODUCT = (
        static_root / "product/substitution-artifacts.json")
    FIDELITY.CANDIDATE_PREFLIGHT_ROOT = preflight
    FIDELITY.CANDIDATE_PROFILE = ownership / "candidate-profile.json"
    FIDELITY.CANDIDATE_PLANE = static_root / "product"

    configure_public_source_authorities()
    ITEM1.BUILD = CANDIDATE
    ITEM1.PREFLIGHT = PREFLIGHT
    ITEM1.RECEIPT = PUBLIC / "unused-item1-card-receipt.json"
    ITEM1.DRIVER = DRIVER
    ITEM1.configure()
    core, activation, _cold = ITEM1.configure_item1_stack()
    require(activation == {"capture": None, "hybrid": None},
            "public Item-1 link admitted Comfort activation")
    return core


def expected_role(role: str, path: Path) -> dict[str, Any]:
    roles = load(AUTHORITY).get("sealed_roles", {})
    require(role in roles, f"sealed public role absent: {role}")
    identity = bind(path)
    require((identity["bytes"], identity["sha256"]) ==
            (roles[role]["bytes"], roles[role]["sha256"]),
            f"public role differs from sealed candidate: {role}")
    return identity


def configure_completion_paths() -> None:
    CAN.BUILD = CANONICAL
    CAN.WPLTO = CANDIDATE / "wplto"
    CAN.FINAL = CANONICAL / "final"
    CAN.ARTIFACTS = CANONICAL / "artifacts"
    CAN.RECEIPTS = CANONICAL / "receipts"
    CAN.MANIFEST = CANONICAL / "canonical-product-manifest.json"
    CAN.STATIC = CURRENT_PREFLIGHT / "static-plane/narrow-static"
    CAN.STATIC_PRODUCT = CAN.STATIC / "product"
    CAN.CONTRACT = CURRENT_OWNERSHIP / "c2-lite-execution-contract.json"
    CAN.PROFILE = CURRENT_OWNERSHIP / "candidate-profile.json"


def configure_item1_semantics() -> None:
    core = configure_item1_link()
    core.PRODUCT.BASE.configure()
    base = ITEM1.BASE.CHAIN.ENGINE.BASE.BASE
    base.CAN.REPLAY.PROFILE.configure()
    if PRODUCT.PROFILE_RODATA_BYTES == 342:
        PRODUCT.configure_require_resolver_profile_geometry()
        PRODUCT.configure_defstruct_foundation_profile_geometry()
    base.CAN.REPLAY.BANK2.configure_bank2_stage()
    base.CAN.REPLAY.TWO.configure_two_region()
    base.CAN.REPLAY.LINK60.configure_current_pin_adapters()
    PRODUCT.configure_intern_session_service()
    PRODUCT.configure_full_map_ownership()
    PRODUCT.configure_low_resident_lma_reset()
    base.HEADER.configure_consumption()
    PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = (
        CAN.STATIC_PRODUCT / "substitution-artifacts.json")
    PRODUCT.INITIAL_C2D = CAN.STATIC_PRODUCT / "initial.c2d-v3.bin"
    PRODUCT.PRODUCT_SHELF = (
        CAN.STATIC_PRODUCT / "product-shelf-v4-direct.bin")
    elf = CAN.WPLTO / "lisp65-c2-substitution-linked.prg.elf"
    section = ElfTruth.read(
        elf, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj").section(
            PRODUCT.VERIFIER_BINDING_SECTION)
    require(section.bytes == 40,
            "public candidate verifier-binding geometry drift")
    PRODUCT.VERIFIER_BINDING_BASE = section.address
    PRODUCT.LINK60_VERIFIER_BINDING_BASE = section.address


def public_acceptance_projection(elf: Path) -> dict[str, Any]:
    """Compare the candidate to public v5 plus active registered freight."""
    golden_module = ACCEPT.V5_GOLDEN
    golden = load(golden_module.GOLDEN)
    expected_sha = getattr(golden_module, "GOLDEN_SHA256", sha(golden_module.GOLDEN))
    require(sha(golden_module.GOLDEN) == expected_sha,
            "public v5 Golden identity drift")
    old_audit = golden_module.audit_artifact
    golden_module.audit_artifact = lambda value: require(
        value == golden, "public v5 Golden bytes drift")
    try:
        layout = ACCEPT.LAYOUT.layout_from_elf(elf)
        registries, registered = ACCEPT._active_freight_union()
        rows = ACCEPT._freight_proof_rows(layout, registries)
        additive = ACCEPT._additive_section_closure(
            layout, golden, registered, rows)
        base_layout = additive.pop("base_layout")
        comparison = golden_module.compare_layout(base_layout, golden)
    finally:
        golden_module.audit_artifact = old_audit
    additive["placement_gate"] = {
        "gate": "active-card-registry-union", "status": "passed",
        "registries": [row["registry"] for row in registries],
        "proof_rows": rows,
    }
    require(comparison.get("comparison") ==
                "dependent-address-plus-freight-boundaries-exact"
            and comparison.get("dependent_fixed_vmas") == 101
            and comparison.get("fixed_boundary_symbols") == 25
            and additive["registered_sections"] ==
                [".lisp65_c2_mapped_product_cold"],
            "public Item-1 additive acceptance drift")
    return {"VMA_golden": comparison, "additive_card_freight": additive,
            "authority": {"mode": "public-fixed-golden-plus-active-registry",
                           "golden": bind(golden_module.GOLDEN)}}


def complete_product() -> dict[str, Any]:
    configure_completion_paths()
    product = CAN.WPLTO / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    expected_role("linked-product-elf", elf)
    require((product.stat().st_size, sha(product)) == EXPECTED_RAW["PRG"],
            "sealed raw product absent before Completion")
    configure_item1_semantics()
    acceptance = public_acceptance_projection(elf)

    class AcceptedProjection:
        @staticmethod
        def compare_elf(candidate: Path) -> dict[str, Any]:
            expected_role("linked-product-elf", candidate)
            return acceptance["VMA_golden"]

    accepted = AcceptedProjection()
    SOURCE_MEDIA.FLOW.BASE.INV = accepted
    CRC_MEDIA.INV = accepted
    SOURCE_MEDIA.card_projection = lambda: {
        "acceptance": {"VMA_golden": acceptance["VMA_golden"]}}
    original_configure = CAN.REPLAY.configure
    original_fixed = PRODUCT.FIXED_BLOCK_LEAF.audit_elf
    original_facade = PRODUCT.fixed_facade_gate
    original_kernal = PRODUCT.kernal_freedom_gate
    original_kernal_sections = list(PRODUCT.KERNAL_SECTIONS)

    def fixed(candidate: Path, **kwargs: Any) -> dict[str, Any]:
        return SOURCE_MEDIA._link105_fixed_audit(
            original_fixed, candidate, **kwargs)

    def facade(out: Path, target: Path, suffix: str) -> dict[str, Any]:
        report = out / "packed-prg-facade-predecessor-rebind.json"
        if not report.exists():
            NESTED_MEDIA.materialize_candidate_publish_predecessors(
                out, target, Path(str(target) + ".elf"))
        value = CRC_MEDIA._current_facade_gate(
            original_facade, out, target, suffix)
        value["packed_PRG_facade"] = FACADE.packed_facade_gate(
            target, Path(str(target) + ".elf"))
        return value

    def item1_kernal(out: Path, target: Path) -> dict[str, object]:
        optional = {
            *map(str, PRODUCT.INPUT_CAPTURE_BUILD_CONFIGURATION["allocated"]),
            *map(str, PRODUCT.INPUT_HYBRID_BUILD_CONFIGURATION["allocated"]),
        }
        truth = ElfTruth.read(
            Path(str(target) + ".elf"),
            llvm_readobj=PRODUCT.TOOLCHAIN / "llvm-readobj")
        require(not optional.intersection(row.name for row in truth.sections),
                "public Item-1 ELF contains Comfort KERNAL freight")
        PRODUCT.KERNAL_SECTIONS[:] = [
            name for name in PRODUCT.KERNAL_SECTIONS if name not in optional]
        return original_kernal(out, target)

    CAN.REPLAY.configure = lambda: None
    PRODUCT.FIXED_BLOCK_LEAF.audit_elf = fixed
    PRODUCT.fixed_facade_gate = facade
    PRODUCT.kernal_freedom_gate = item1_kernal
    try:
        value = CAN.complete_artifacts()
    finally:
        CAN.REPLAY.configure = original_configure
        PRODUCT.FIXED_BLOCK_LEAF.audit_elf = original_fixed
        PRODUCT.fixed_facade_gate = original_facade
        PRODUCT.kernal_freedom_gate = original_kernal
        PRODUCT.KERNAL_SECTIONS[:] = original_kernal_sections
    final_product = CAN.FINAL / product.name
    final_elf = Path(str(final_product) + ".elf")
    expected_role("c2-resident-prg", final_product)
    expected_role("linked-product-elf", final_elf)
    require(value["compiler_runs"] == value["linker_runs"] == 0,
            "public Completion rebuilt the final pair")
    FACADE.packed_facade_gate(final_product, final_elf)
    receipt = PUBLIC / "completion.json"
    receipt.write_bytes(canonical({
        "status": "PASS: V1.6 PUBLIC ARTIFACT-ONLY COMPLETION",
        "private_evidence_inputs": 0, "compiler_runs": 0, "linker_runs": 0,
        "acceptance": acceptance, "completion": bind(
            CAN.RECEIPTS / "artifact-completion.json")}))
    print("v1.6 public product: COMPLETION PASS rebuilds=0")
    return value


def build_link() -> dict[str, Any]:
    require(STATIC_RECEIPT.is_file()
            and not CANDIDATE.exists() and not PREFLIGHT.exists(),
            "v1.6 public link lifecycle drift")
    core = configure_item1_link()
    installed = core.install_static(CANDIDATE)
    require(installed["consumer_observed_bytes"] == 46043,
            "public Item-1 static consumer drift")
    core.bind_paths_only(CANDIDATE, PREFLIGHT)
    core.write_projections()
    exit_code: int | None = None
    try:
        core.PRODUCT.BASE.produce_child()
    except SystemExit as error:
        exit_code = error.code if isinstance(error.code, int) else 0
    prg = CANDIDATE / "wplto/lisp65-c2-substitution-linked.prg"
    elf = Path(str(prg) + ".elf")
    profile = CANDIDATE / "wplto/resolved-profile.txt"
    require(all(path.is_file() for path in (prg, elf, profile)),
            f"public Item-1 producer emitted no final pair (exit={exit_code})")
    observed = {"PRG": bind(prg), "ELF": bind(elf), "profile": bind(profile)}
    for role, identity in observed.items():
        require((identity["bytes"], identity["sha256"]) == EXPECTED_RAW[role],
                f"public Item-1 {role} differs from sealed raw link")
    value = {"status": "PASS: V1.6 PUBLIC ITEM-1 SOURCE LINK",
        "private_evidence_inputs": 0, "WPLTO_runs": 1,
        "product_links": 1, "artifacts": observed,
        "configuration": {"Comfort": False, "diagnostic": False,
            "capacity": public_capacity()}}
    LINK_RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    LINK_RECEIPT.write_bytes(canonical(value))
    print("v1.6 public product: LINK PASS WPLTO=1 evidence=0")
    return value


def canonical_manifest() -> dict[str, Any]:
    configure_completion_paths()
    configure_item1_semantics()
    libs = CAN.STATIC / "libs"
    libs.mkdir(parents=True, exist_ok=True)
    sources = {
        "ide": ROOT / "build/bytecode/dialect-v2/libs/ide.ext.bin",
        "idex": ROOT / (
            "build/c2.2/substitution/published-nullary-call-bytecode-artifacts/"
            "libs/idex.ext.bin"),
        "m65d": ROOT / (
            "build/c2.2/substitution/published-nullary-call-bytecode-artifacts/"
            "libs/m65d.ext.bin"),
    }
    for name, source in sources.items():
        shutil.copyfile(source, libs / f"{name}.ext.bin")
    completion = load(CAN.RECEIPTS / "artifact-completion.json")
    static_product = load(CAN.STATIC_PRODUCT / "substitution-artifacts.json")
    static = {"status": "passed-v1.6-public-item1-static-plane",
              "product_build_id": static_product["product_build_id_hex"],
              "bank2_static_code_bytes": 46043}
    wplto = {"status": "passed-one-public-v1.6-source-link",
             "product": bind(CAN.WPLTO /
                             "lisp65-c2-substitution-linked.prg")}
    value = CAN.manifest(static, wplto, completion)
    elf = CAN.FINAL / "lisp65-c2-substitution-linked.prg.elf"
    truth = ElfTruth.read(elf,
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=True)
    registries = PRODUCT.active_card_freight_registries()
    registered = {
        name for registry in registries for name in registry["allocated"]
        if name.startswith(".lisp65_c2_mapped_")}
    names = [".lisp65_c2_mapped_far_service", *sorted(registered)]
    require(registered == {".lisp65_c2_mapped_product_cold"}
            and len(names) == len(set(names)),
            "public Item-1 mapped freight registry drift")
    row = next(item for item in value["artifacts"]
               if item["role"] == "c2-bank2-static-code-plane")
    prefix = (ROOT / row["path"]).read_bytes()
    require(len(prefix) == 46043, "public Item-1 Bank-2 prefix drift")
    sections: list[tuple[int, bytes, str]] = []
    for name in names:
        raw = truth.section_bytes(name)
        symbol = "__" + name.removeprefix(".") + "_load_start"
        sections.append((truth.symbol(symbol).value, raw, name))
    base = 0x20000
    end = max(start + len(raw) for start, raw, _name in sections)
    materialized = bytearray(end - base)
    materialized[:len(prefix)] = prefix
    for start, raw, name in sections:
        offset = start - base
        require(offset >= len(prefix),
                f"mapped section overlaps public prefix: {name}")
        materialized[offset:offset + len(raw)] = raw
    bank2 = PUBLIC / "product-inputs/bank2-static-code.bin"
    bank2.parent.mkdir(parents=True, exist_ok=True)
    bank2.write_bytes(materialized)
    row.clear()
    row.update({**bind(bank2), "role": "c2-bank2-static-code-plane"})
    value["static_plane"].update({
        "bank2_static_code_bytes": len(materialized),
        "bank2_sha256": hashlib.sha256(materialized).hexdigest(),
        "mapped_sections": names,
        "membership_authority": "public Item-1 active registry union",
    })
    CAN.MANIFEST.write_bytes(canonical(value))
    CAN.check()
    expected_role("c2-bank2-static-code-plane", bank2)
    return value


def configure_media_paths() -> None:
    configure_completion_paths()
    MEDIA.CANONICAL = CAN
    MEDIA.BUILD = SHARED
    MEDIA.PRODUCT_MANIFEST = CAN.MANIFEST
    MEDIA.MANIFEST = SHARED / "candidate-manifest.json"
    MEDIA.DESCRIPTOR = SHARED / "boot.id"
    MEDIA.STAGER = SHARED / "autoboot.c65"
    MEDIA.STAGER_MAP = SHARED / "autoboot.c65.map"
    MEDIA.PRODUCT_D81 = SHARED / "lisp65-product.d81"
    MEDIA.WORK_D81 = SHARED / "lisp65-work.d81"
    MEDIA.MOUNT = SHARED / "lisp65-product.mount.json"


def build_shared_media() -> dict[str, Any]:
    canonical_manifest()
    configure_media_paths()
    value = MEDIA.build(stager_compile_defines=(LIVENESS.OPT_IN,))
    MEDIA.check()
    rows = value.get("artifacts", [])
    require(len(rows) == 19, "public Item-1 shared-media role count drift")
    for row in rows:
        expected_role(row["role"], ROOT / row["path"])
    print("v1.6 public product: SHARED MEDIA PASS roles=19")
    return value


def compile_v16core(prefix: Path) -> Path:
    generated = prefix.parent
    generated.mkdir(parents=True, exist_ok=True)
    source = generated / "stdlib-read-line-item1.lisp"
    source.write_text(ITEM1.CURSOR.public_only_source(
        ITEM1.CURSOR.READ_LINE.read_text(encoding="utf-8")), encoding="utf-8")
    suite_path = generated / "v16core-item1-suite.json"
    cursor_suite = ROOT / "tests/bytecode/libs/p0-v160-comfort-device-delta.json"
    suite_path.write_bytes(canonical({
        "extends": str(cursor_suite.resolve()),
        "sources": [source.relative_to(ROOT).as_posix()],
        "remove_sources": [ITEM1.CURSOR.READ_LINE.relative_to(ROOT).as_posix()],
        "resident_suite": str((ROOT /
            "config/c2-v160-comfort-repl-device-resident.json").resolve()),
        "private_key_event_modes": False,
        "description": "Public Item-1 cursor editor; Comfort is excluded.",
    }))
    suite = STD._read_suite(str(suite_path))
    STD.check_suite(str(suite_path), suite)
    STD.emit_artifacts(str(suite_path), suite, str(prefix), base_addr=0,
                       artifact_role="disk-lib")
    return prefix.with_suffix(".manifest.json")


def build_library_media() -> dict[str, Any]:
    generated = PUBLIC / "library-inputs"
    manifest = compile_v16core(generated / "v16core")
    static = load(CAN.STATIC_PRODUCT / "substitution-artifacts.json")
    product_id = int(static["product_build_id_u32"])
    spec = ("v16core", "v16core", "v16core", manifest, ())
    LIBRARY.mkdir(parents=True)
    row, artifact = LIBMEDIA.measured(spec, (1, 1), product_id)
    artifact_path = LIBRARY / "v16core.l65s"
    artifact_path.write_bytes(artifact)
    seed_index = LIBRARY / "l65index.seed"
    seed_index.write_bytes(LIBMEDIA.L65I.encode_index([row]))
    seed = LIBRARY / "library.seed.d81"
    LIBMEDIA.build_library_d81(
        seed, seed_index, [(artifact_path, "v16core")])
    locator = LIBMEDIA.L65I.d81_locators(seed)["v16core"]
    row, located = LIBMEDIA.measured(spec, locator, product_id)
    require(located == artifact, "v16core changed with final locator")
    index = LIBMEDIA.L65I.encode_index([row])
    index_path = LIBRARY / "l65index"
    index_path.write_bytes(index)
    decoded = LIBMEDIA.L65I.decode_index(
        index, {"v16core": artifact}, artifact_build_id=product_id)
    require(len(decoded) == 1 and decoded[0]["name"] == "v16core",
            "public Item-1 library row closure drift")
    final = LIBRARY / "lisp65-library.d81"
    LIBMEDIA.build_library_d81(
        final, index_path, [(artifact_path, "v16core")])
    visible = LIBMEDIA.L65I.D81.visible_files(final.read_bytes())
    require(visible == {b"L65INDEX": index, b"V16CORE": artifact},
            "public Item-1 library visible-file closure drift")
    seed.unlink()
    seed_index.unlink()
    value = {"D81": expected_role("optional-library-d81", final),
        "index": expected_role("optional-library-index", index_path),
        "v16core": expected_role("library-v16core", artifact_path),
        "rows": ["v16core"], "Comfort_absent": True,
        "private_evidence_inputs": 0}
    (PUBLIC / "library.json").write_bytes(canonical(value))
    print("v1.6 public product: LIBRARY MEDIA PASS rows=1")
    return value


def artifact_set(rows: list[dict[str, Any]]) -> str:
    projection = [
        {key: row[key] for key in ("role", "name", "bytes", "sha256")}
        for row in sorted(rows, key=lambda item: (item["role"], item["name"]))]
    return hashlib.sha256(json.dumps(
        projection, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build_selected() -> dict[str, Any]:
    configure_media_paths()
    shared = load(MEDIA.MANIFEST)
    require(shared.get("artifact_count") == 19
            and len(shared.get("artifacts", [])) == 19,
            "public Item-1 shared-media closure absent")
    library = build_library_media()
    rows = [dict(row) for row in shared["artifacts"]]
    for role, name, identity in (
            ("optional-library-d81", "lisp65-library.d81", library["D81"]),
            ("optional-library-index", "l65index", library["index"]),
            ("library-v16core", "v16core.l65s", library["v16core"])):
        rows.append({"role": role, "name": name, **identity})
    require(len(rows) == len({row["role"] for row in rows}) == 22,
            "public v1.6 selected role inventory drift")
    authority = load(AUTHORITY)
    value = {"format": "lisp65-v1.6-public-selected-product-v1",
        "status": "passed-public-source-selected-v1.6-item1-product",
        "artifact_count": 22, "artifact_set_sha256": artifact_set(rows),
        "product_build_id": shared["product_build_id"],
        "profile_build_id": shared["profile_build_id"],
        "private_evidence_inputs": 0, "selector": "v1.6-item-1-only",
        "artifacts": rows}
    require(value["artifact_set_sha256"] ==
                authority["sealed_product_artifact_set_sha256"],
            "public v1.6 artifact set differs from candidate seal")
    MANIFEST.write_bytes(canonical(value))
    print("v1.6 public product: SELECTED PASS roles=22 "+
          value["artifact_set_sha256"])
    return value


def build() -> None:
    require(not PUBLIC.exists() and not CANDIDATE.exists()
            and not PREFLIGHT.exists(), "v1.6 public build is one-shot")
    for action in ("static", "link", "complete", "media", "selected"):
        run_stage(action)
    check()
    print("v1.6 public product: FULL PASS roles=22 evidence=0")


def check_link() -> dict[str, Any]:
    value = load(LINK_RECEIPT)
    require(value.get("status") == "PASS: V1.6 PUBLIC ITEM-1 SOURCE LINK"
            and value.get("private_evidence_inputs") == 0
            and value.get("WPLTO_runs") == value.get("product_links") == 1,
            "v1.6 public link receipt drift")
    for role, identity in value["artifacts"].items():
        require(bind(ROOT / identity["path"]) == identity
                and (identity["bytes"], identity["sha256"]) == EXPECTED_RAW[role],
                f"v1.6 public linked role drift: {role}")
    print("v1.6 public product: LINK CHECK PASS")
    return value


def check() -> dict[str, Any]:
    check_link()
    value = load(MANIFEST)
    rows = value.get("artifacts", [])
    authority = load(AUTHORITY)
    require(value.get("format") == "lisp65-v1.6-public-selected-product-v1"
            and value.get("private_evidence_inputs") == 0
            and value.get("selector") == "v1.6-item-1-only"
            and value.get("artifact_count") == len(rows) == 22
            and artifact_set(rows) == value.get("artifact_set_sha256")
            == authority["sealed_product_artifact_set_sha256"],
            "selected public v1.6 manifest drift")
    for row in rows:
        expected_role(row["role"], ROOT / row["path"])
    print("v1.6 public product: CHECK PASS roles=22 evidence=0")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("static", "link", "complete",
        "media", "selected", "build", "check-link", "check"))
    action = parser.parse_args().action
    if action == "static":
        build_source_static()
    elif action == "link":
        build_link()
    elif action == "complete":
        complete_product()
    elif action == "media":
        build_shared_media()
    elif action == "selected":
        build_selected()
    elif action == "build":
        build()
    elif action == "check-link":
        check_link()
    else:
        check()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PublicBuildError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"c2-v160-public-product: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
