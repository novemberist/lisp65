#!/usr/bin/env python3
"""Rebuild the sealed v1.7.0 native-INIT/A0 product from public sources."""

from __future__ import annotations

import argparse
from copy import deepcopy
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

import c2_v160_public_product as V160  # noqa: E402


INIT: Any = None
CARD: Any = None
RELEASE_MEDIA: Any = None


PUBLIC = ROOT / "build/c2.3/v1.7.0-public-selected"
# Build identities include repository-relative generated-source paths.  Public
# clones therefore reproduce at the release producer's canonical phase-owned
# roots; only the selected/completed outputs live below PUBLIC.
BUILD = ROOT / "build/c2.3/v1.7.0-release-card-r1"
PREFLIGHT = ROOT / "build/c2.3/v1.7.0-release-card-r1-preflight"
PLANE_ROOT = PREFLIGHT / "setup-owned/static-plane/narrow-static"
PLANE_RECEIPT = PREFLIGHT / "public-v170-static-plane.json"
C2D = PLANE_ROOT / "v6-semantics/initial.c2d-v6.bin"
CODE = PLANE_ROOT / "v6-semantics/bank2-static-code.bin"
MANIFEST = PLANE_ROOT / "stdlib-p0.manifest.json"
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
PROFILE = BUILD / "wplto/resolved-profile.txt"
STATIC_RECEIPT = PUBLIC / "public-static.json"
LINK_RECEIPT = PUBLIC / "linked-product.json"
CANONICAL = PUBLIC / "canonical-product"
SHARED = PUBLIC / "shared-system"
LIBRARY = PUBLIC / "library"
MANIFEST_OUT = PUBLIC / "candidate-manifest.json"
AUTHORITY = ROOT / "config/c2-v170-public-build-authority.json"
DRIVER = Path(__file__).resolve()
EXPECTED_RAW = {
    "PRG": (41566,
        "b6ea4519cd2ec29eec028e65fa0102b9eac89f7d0b1a85458415595f5db0342c"),
    "ELF": (647268,
        "e8ca0734427cbe22c6d60dfbba2cc141b8c98dd031beecdab8c57aa7d499efab"),
    "profile": (13103,
        "560a64601ada7f64a688eaff8a386f1e560f0857ef34a7f49bed972083c9ea14"),
}
PUBLIC_V15_REPOSITORY = "https://github.com/novemberist/lisp65.git"
PUBLIC_V16_SOURCE_COMMIT = "9938c274e34ff7163d0d6e0109df60e0540ae83a"


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


def expected_role(role: str, path: Path) -> dict[str, Any]:
    roles = load(AUTHORITY)["sealed_roles"]
    require(role in roles, f"sealed public role absent: {role}")
    identity = bind(path)
    require((identity["bytes"], identity["sha256"]) ==
            (roles[role]["bytes"], roles[role]["sha256"]),
            f"public role differs from sealed candidate: {role}")
    return identity


def predecessor_specs() -> tuple[tuple[str, str, Path], ...]:
    static = V160.CURRENT_PREFLIGHT / "static-plane/narrow-static"
    V160.FIDELITY.CANDIDATE_STATIC_ROOT = ROOT
    V160.FIDELITY.CANDIDATE_STATIC_PRODUCT = (
        static / "product/substitution-artifacts.json")
    V160.FIDELITY.CANDIDATE_PREFLIGHT_ROOT = V160.CURRENT_PREFLIGHT
    V160.FIDELITY.CANDIDATE_PROFILE = (
        V160.CURRENT_OWNERSHIP / "candidate-profile.json")
    V160.FIDELITY.CANDIDATE_PLANE = static / "product"
    return V160.FIDELITY.candidate_static_specs()


def predecessor_ready() -> bool:
    try:
        return all(path.is_file()
                   for _key, _name, path in predecessor_specs())
    except Exception:
        return False


def materialize_predecessor() -> dict[str, Any]:
    """Build the public v1.5 source plane, or bind an existing exact copy."""
    if not predecessor_ready():
        require(not V160.SOURCE.exists() and not V160.CANDIDATE.exists()
                and not V160.PREFLIGHT.exists(),
                "public predecessor source stage is not fresh")
        V160.PUBLIC.mkdir(parents=True)
        V160.SOURCE.mkdir()
        clone = subprocess.run(
            ["git", "clone", "--no-local", "--no-checkout",
             PUBLIC_V15_REPOSITORY, str(V160.HISTORICAL)], cwd=ROOT,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        require(clone.returncode == 0,
                f"public v1.5 clone red:\n{clone.stdout}")
        checkout = subprocess.run(
            ["git", "checkout", "--detach", V160.STATIC_SOURCE_COMMIT],
            cwd=V160.HISTORICAL, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)
        require(checkout.returncode == 0,
                f"public v1.5 checkout red:\n{checkout.stdout}")
        bundled = V160.HISTORICAL / "tools/llvm-mos"
        require(not bundled.exists() and not bundled.is_symlink(),
                "public v1.5 source unexpectedly bundles LLVM-MOS")
        bundled.symlink_to((ROOT / "tools/llvm-mos").resolve(),
                           target_is_directory=True)
        output = V160.HISTORICAL_OUTPUT.relative_to(V160.HISTORICAL)
        run = subprocess.run(
            [sys.executable, str(V160.STATIC_HELPER), "--output", str(output)],
            cwd=V160.HISTORICAL,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        require(run.returncode == 0,
                f"public v1.5 static emitter red:\n{run.stdout}")
        historical = load(V160.HISTORICAL_OUTPUT / "public-static.json")
        require(historical["private_evidence_inputs"] == 0
                and historical["product_WPLTO_runs"] == 0
                and historical["product_links"] == 0,
                "public v1.5 static source boundary drift")
        consumer_view = V160.materialize_static_consumer_view()
        V160.STATIC_RECEIPT.write_bytes(canonical({
            "status": "PASS: V1.7 PUBLIC PREDECESSOR STATIC PLANE",
            "source_commit": V160.STATIC_SOURCE_COMMIT,
            "source_repository": PUBLIC_V15_REPOSITORY,
            "private_evidence_inputs": 0, "product_WPLTO_runs": 0,
            "product_links": 0, "images": 6,
            "consumer_view": consumer_view,
            "historical_receipt": bind(
                V160.HISTORICAL_OUTPUT / "public-static.json"),
            "bank2": bind(V160.CURRENT_PREFLIGHT / (
                "static-plane/narrow-static/v6-semantics/"
                "bank2-static-code.bin")),
        }))
    require(predecessor_ready(), "public predecessor six-role plane absent")
    # The sealed manifest deliberately retains checkout-relative source names.
    # Project those names into the same public-root view consumed by the INIT
    # successor; absolute source names already point inside the fresh public
    # v1.5 checkout and remain valid for this build.
    manifest = load(predecessor_specs()[0][2])
    public_root = ROOT / "build/release-v1.5.0/public-product-build"
    projected_sources = 0
    for raw in manifest["sources"]:
        relative = Path(raw)
        if relative.is_absolute():
            continue
        source = V160.HISTORICAL / relative
        destination = public_root / relative
        require(source.is_file() and not source.is_symlink(),
                f"public predecessor source absent: {relative}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copyfile(source, destination)
        require(destination.is_file() and sha(destination) == sha(source),
                f"public predecessor source projection drift: {relative}")
        projected_sources += 1
    rows = [bind(path) for _key, _name, path in predecessor_specs()]
    return {"source": "fresh-public-v1.5-parent",
            "private_evidence_inputs": 0, "images": len(rows),
            "projected_relative_sources": projected_sources,
            "manifests": rows}


def load_successor_modules() -> None:
    global INIT, CARD, RELEASE_MEDIA
    if INIT is None:
        # These modules derive their baseline inventory at import time.  They
        # are intentionally imported only after the public predecessor has
        # been materialized in this fresh checkout.
        predecessor_specs()
        INIT = importlib.import_module("c2_v17_init_l65_card")
        CARD = importlib.import_module("c2_v170_release_card")
        RELEASE_MEDIA = importlib.import_module("c2_v170_release_media")


def configure_paths() -> None:
    load_successor_modules()
    INIT.BUILD = BUILD
    INIT.PREFLIGHT = PREFLIGHT
    INIT.RECEIPT = PUBLIC / "unused-card-receipt.json"
    INIT.ELF = ELF
    INIT.PRG = PRG
    INIT.PROFILE = PROFILE
    INIT.PLANE_ROOT = PLANE_ROOT
    INIT.PLANE_RECEIPT = PLANE_RECEIPT
    INIT.C2D = C2D
    INIT.CODE = CODE
    INIT.MANIFEST = MANIFEST
    INIT.DRIVER = DRIVER
    INIT.FORMAT = "lisp65-c2-v170-public-product-v1"
    INIT.STATUS = "PASS: V1.7.0 PUBLIC SOURCE PRODUCT"
    INIT.BASELINE_SPECS = predecessor_specs()
    INIT.BASELINE_STDLIB = INIT.BASELINE_SPECS[0][2]
    INIT._configure_plane_module()


def build_static() -> dict[str, Any]:
    require(not PUBLIC.exists(), "v1.7 public source stage is one-shot")
    predecessor = materialize_predecessor()
    PUBLIC.mkdir(parents=True)
    configure_paths()
    plane = INIT.emit_init_plane()
    require(plane["geometry"]["bytes"] == 46053
            and plane["banner"]["literal"] == "init.l65",
            "public v1.7 source plane geometry drift")
    value = {
        "format": "lisp65-v1.7-public-static-plane-v1",
        "status": "PASS: V1.7 PUBLIC NATIVE-INIT SOURCE PLANE",
        "private_evidence_inputs": 0,
        "product_WPLTO_runs": 0, "product_links": 0,
        "predecessor": predecessor, "successor": bind(PLANE_RECEIPT),
        "bank2": bind(CODE), "manifest": bind(MANIFEST),
    }
    STATIC_RECEIPT.write_bytes(canonical(value))
    print("v1.7 public product: STATIC PASS images=6 evidence=0")
    return value


def configure_link() -> Any:
    configure_paths()
    # Replace historical price receipts with the same current-source
    # authorities used by the already-public v1.6 producer.
    V160.CAPACITY.capacity_authority = V160.public_capacity
    V160.FIDELITY.CANDIDATE_STATIC_ROOT = ROOT
    V160.FIDELITY.CANDIDATE_STATIC_PRODUCT = (
        PLANE_ROOT / "product/substitution-artifacts.json")
    V160.FIDELITY.CANDIDATE_PREFLIGHT_ROOT = PREFLIGHT
    V160.FIDELITY.CANDIDATE_PROFILE = (
        PLANE_ROOT / "derived-profile/resolved-profile.json")
    V160.FIDELITY.CANDIDATE_PLANE = PLANE_ROOT / "product"
    V160.configure_public_source_authorities()
    INIT.configure()
    return INIT.BASE


def build_link() -> dict[str, Any]:
    require(STATIC_RECEIPT.is_file() and not BUILD.exists(),
            "v1.7 public link lifecycle drift")
    configure_link()
    # Use the native-INIT card's real producer seam.  Its setup_child binds
    # the already materialized 46,053-byte plane directly at every consumer;
    # the inherited v1.6 core.install_static() intentionally belongs to the
    # 46,043-byte predecessor and must not be called in this successor world.
    exit_code: int | None = None
    try:
        INIT.BASE.produce_child()
    except SystemExit as error:
        exit_code = error.code if isinstance(error.code, int) else 0
    require(all(path.is_file() for path in (PRG, ELF, PROFILE)),
            f"public v1.7 producer emitted no final pair (exit={exit_code})")
    observed = {"PRG": bind(PRG), "ELF": bind(ELF),
                "profile": bind(PROFILE)}
    for role, identity in observed.items():
        require((identity["bytes"], identity["sha256"]) == EXPECTED_RAW[role],
                f"public v1.7 {role} differs from sealed raw link")
    value = {
        "format": "lisp65-v1.7-public-link-v1",
        "status": "PASS: V1.7 PUBLIC NATIVE-INIT/A0 SOURCE LINK",
        "private_evidence_inputs": 0, "WPLTO_runs": 1,
        "product_links": 1, "artifacts": observed,
        "configuration": {"native_INIT_L65": True,
            "recovery_quiescence_A0": True, "Comfort": False,
            "Block_3": False, "diagnostic": False},
    }
    LINK_RECEIPT.write_bytes(canonical(value))
    print("v1.7 public product: LINK PASS WPLTO=1 evidence=0")
    return value


def check_link() -> dict[str, Any]:
    value = load(LINK_RECEIPT)
    require(value["status"] ==
                "PASS: V1.7 PUBLIC NATIVE-INIT/A0 SOURCE LINK"
            and value["private_evidence_inputs"] == 0
            and value["WPLTO_runs"] == value["product_links"] == 1,
            "v1.7 public link receipt drift")
    for role, identity in value["artifacts"].items():
        require(bind(ROOT / identity["path"]) == identity
                and (identity["bytes"], identity["sha256"]) ==
                    EXPECTED_RAW[role],
                f"v1.7 public linked role drift: {role}")
    print("v1.7 public product: LINK CHECK PASS")
    return value


def configure_completion() -> None:
    load_successor_modules()
    V160.PUBLIC = PUBLIC
    V160.CANDIDATE = BUILD
    V160.PREFLIGHT = PREFLIGHT
    V160.CURRENT_PREFLIGHT = PREFLIGHT / "setup-owned"
    V160.CURRENT_OWNERSHIP = PLANE_ROOT
    V160.CANONICAL = CANONICAL
    V160.SHARED = SHARED
    V160.LIBRARY = LIBRARY
    V160.AUTHORITY = AUTHORITY
    V160.EXPECTED_RAW = EXPECTED_RAW
    V160.MANIFEST = MANIFEST_OUT

    def current_semantics() -> None:
        configure_paths()
        V160.CAPACITY.capacity_authority = V160.public_capacity
        V160.configure_public_source_authorities()
        CARD.configure()
        CARD.BASE.configure_full_candidate()
        V160.PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = (
            PLANE_ROOT / "product/substitution-artifacts.json")
        V160.PRODUCT.INITIAL_C2D = (
            PLANE_ROOT / "product/initial.c2d-v3.bin")
        V160.PRODUCT.PRODUCT_SHELF = (
            PLANE_ROOT / "product/product-shelf-v4-direct.bin")
        truth = V160.ElfTruth.read(
            ELF, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
        section = truth.section(V160.PRODUCT.VERIFIER_BINDING_SECTION)
        require(section.bytes == 40,
                "public v1.7 verifier-binding geometry drift")
        V160.PRODUCT.VERIFIER_BINDING_BASE = section.address
        V160.PRODUCT.LINK60_VERIFIER_BINDING_BASE = section.address

    V160.configure_item1_semantics = current_semantics


def complete_product() -> dict[str, Any]:
    configure_completion()
    value = V160.complete_product()
    receipt = PUBLIC / "completion.json"
    current = load(receipt)
    current["status"] = "PASS: V1.7 PUBLIC ARTIFACT-ONLY COMPLETION"
    receipt.write_bytes(canonical(current))
    print("v1.7 public product: COMPLETION PASS rebuilds=0")
    return value


def canonical_manifest() -> dict[str, Any]:
    configure_completion()
    V160.configure_completion_paths()
    V160.configure_item1_semantics()
    libs = V160.CAN.STATIC / "libs"
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
    completion = load(V160.CAN.RECEIPTS / "artifact-completion.json")
    product = load(V160.CAN.STATIC_PRODUCT / "substitution-artifacts.json")
    static = {"status": "passed-v1.7.0-release-static-plane",
              "product_build_id": product["product_build_id_hex"],
              "bank2_static_code_bytes": 46053}
    wplto = {"status": "passed-one-public-v1.7-source-link",
             "product": bind(PRG)}
    value = V160.CAN.manifest(static, wplto, completion)
    final_elf = V160.CAN.FINAL / "lisp65-c2-substitution-linked.prg.elf"
    truth = V160.ElfTruth.read(
        final_elf, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=True)
    row = next(item for item in value["artifacts"]
               if item["role"] == "c2-bank2-static-code-plane")
    prefix = (ROOT / row["path"]).read_bytes()
    require(len(prefix) == 46053, "public v1.7 Bank-2 prefix drift")
    sections = RELEASE_MEDIA.MEDIA.mapped_section_rows(truth)
    base = 0x20000
    end = max(start + len(raw) for start, raw, _name in sections)
    materialized = bytearray(end - base)
    materialized[:len(prefix)] = prefix
    cursor = base + len(prefix)
    owners: list[dict[str, Any]] = []
    for start, raw, name in sections:
        require(start >= cursor, f"mapped section overlaps predecessor: {name}")
        if start > cursor:
            owners.append({"owner": "static-to-mapped-free-hole",
                "start": cursor, "end_exclusive": start,
                "bytes": start - cursor})
        offset = start - base
        materialized[offset:offset + len(raw)] = raw
        owners.append({"owner": name, "start": start,
                       "end_exclusive": start + len(raw),
                       "bytes": len(raw)})
        cursor = start + len(raw)
    require(cursor == 0x2BFD1 and end - base == 49105,
            "public v1.7 composed Bank-2 geometry drift")
    owners.append({"owner": "mapped-tenant-bank-end-reserve",
                   "start": cursor, "end_exclusive": 0x30000,
                   "bytes": 0x30000 - cursor})
    bank2 = PUBLIC / "product-inputs/bank2-static-code.bin"
    bank2.parent.mkdir(parents=True, exist_ok=True)
    bank2.write_bytes(materialized)
    row.clear()
    row.update({**bind(bank2), "role": "c2-bank2-static-code-plane"})
    value["static_plane"].update({
        "bank2_static_code_bytes": len(materialized),
        "bank2_sha256": hashlib.sha256(materialized).hexdigest(),
        "mapped_sections": [name for _start, _raw, name in sections],
        "composed_owners": owners,
        "membership_authority": "v1.7 final-ELF composed ownership",
    })
    V160.CAN.MANIFEST.write_bytes(canonical(value))
    V160.CAN.check()
    expected_role("c2-bank2-static-code-plane", bank2)
    return value


def configure_media_paths() -> None:
    configure_completion()
    V160.configure_completion_paths()
    V160.MEDIA.CANONICAL = V160.CAN
    V160.MEDIA.BUILD = SHARED
    V160.MEDIA.PRODUCT_MANIFEST = V160.CAN.MANIFEST
    V160.MEDIA.MANIFEST = SHARED / "candidate-manifest.json"
    V160.MEDIA.DESCRIPTOR = SHARED / "boot.id"
    V160.MEDIA.STAGER = SHARED / "autoboot.c65"
    V160.MEDIA.STAGER_MAP = SHARED / "autoboot.c65.map"
    V160.MEDIA.PRODUCT_D81 = SHARED / "lisp65-product.d81"
    V160.MEDIA.WORK_D81 = SHARED / "lisp65-work.d81"
    V160.MEDIA.MOUNT = SHARED / "lisp65-product.mount.json"


def build_shared_media() -> dict[str, Any]:
    canonical_manifest()
    configure_media_paths()
    value = V160.MEDIA.build(stager_compile_defines=(V160.LIVENESS.OPT_IN,))
    V160.MEDIA.check()
    rows = value.get("artifacts", [])
    require(len(rows) == 19, "public v1.7 shared-media role count drift")
    for row in rows:
        expected_role(row["role"], ROOT / row["path"])
    print("v1.7 public product: SHARED MEDIA PASS roles=19")
    return value


def build_library_media() -> dict[str, Any]:
    generated = PUBLIC / "library-inputs"
    generated.mkdir(parents=True, exist_ok=True)
    # v16core is sealed v1.6 freight.  Read it from the public predecessor
    # history already cloned for the source build; a private proof commit is
    # neither present nor authoritative in a public checkout/source archive.
    era = PUBLIC_V16_SOURCE_COMMIT
    historical = subprocess.run(
        ["git", "show", f"{era}:lib/stdlib-read-line.lisp"],
        cwd=V160.HISTORICAL,
        check=True, stdout=subprocess.PIPE).stdout.decode()
    source = generated / "stdlib-read-line-v160-sealed.lisp"
    source.write_text(V160.ITEM1.CURSOR.public_only_source(historical),
                      encoding="utf-8")
    sexp = generated / "sexp-depth-v160-sealed.lisp"
    sexp.write_bytes(subprocess.run(
        ["git", "show", f"{era}:lib/sexp-depth.lisp"],
        cwd=V160.HISTORICAL,
        check=True, stdout=subprocess.PIPE).stdout)
    suite_path = generated / "v16core-v170-suite.json"
    cursor_suite = ROOT / "tests/bytecode/libs/p0-v160-comfort-device-delta.json"
    suite_path.write_bytes(canonical({
        "extends": str(cursor_suite.resolve()),
        "sources": [source.relative_to(ROOT).as_posix(),
                    sexp.relative_to(ROOT).as_posix()],
        "remove_sources": [
            V160.ITEM1.CURSOR.READ_LINE.relative_to(ROOT).as_posix(),
            "lib/sexp-depth.lisp"],
        "resident_suite": str((ROOT /
            "config/c2-v160-comfort-repl-device-resident.json").resolve()),
        "private_key_event_modes": False,
        "allow_omitted_defuns": [],
        "description": "sealed v1.6 cursor editor for v1.7 public build",
    }))
    prefix = generated / "v16core"
    suite = V160.STD._read_suite(str(suite_path))
    V160.STD.check_suite(str(suite_path), suite)
    V160.STD.emit_artifacts(str(suite_path), suite, str(prefix), base_addr=0,
                            artifact_role="disk-lib")
    manifest = prefix.with_suffix(".manifest.json")
    product = load(PLANE_ROOT / "product/substitution-artifacts.json")
    product_id = int(product["product_build_id_u32"])
    spec = ("v16core", "v16core", "v16core", manifest, ())
    LIBRARY.mkdir(parents=True)
    row, artifact = V160.LIBMEDIA.measured(spec, (1, 1), product_id)
    artifact_path = LIBRARY / "v16core.l65s"
    artifact_path.write_bytes(artifact)
    seed_index = LIBRARY / "l65index.seed"
    seed_index.write_bytes(V160.LIBMEDIA.L65I.encode_index([row]))
    seed = LIBRARY / "library.seed.d81"
    V160.LIBMEDIA.build_library_d81(
        seed, seed_index, [(artifact_path, "v16core")])
    locator = V160.LIBMEDIA.L65I.d81_locators(seed)["v16core"]
    row, located = V160.LIBMEDIA.measured(spec, locator, product_id)
    require(located == artifact, "public v1.7 v16core locator drift")
    index = V160.LIBMEDIA.L65I.encode_index([row])
    index_path = LIBRARY / "l65index"
    index_path.write_bytes(index)
    decoded = V160.LIBMEDIA.L65I.decode_index(
        index, {"v16core": artifact}, artifact_build_id=product_id)
    require(len(decoded) == 1 and decoded[0]["name"] == "v16core",
            "public v1.7 library row closure drift")
    final = LIBRARY / "lisp65-library.d81"
    V160.LIBMEDIA.build_library_d81(
        final, index_path, [(artifact_path, "v16core")])
    visible = V160.LIBMEDIA.L65I.D81.visible_files(final.read_bytes())
    require(visible == {b"L65INDEX": index, b"V16CORE": artifact},
            "public v1.7 library visible closure drift")
    seed.unlink(); seed_index.unlink()
    value = {"D81": expected_role("optional-library-d81", final),
        "index": expected_role("optional-library-index", index_path),
        "v16core": expected_role("library-v16core", artifact_path),
        "rows": ["v16core"], "Comfort_absent": True,
        "source_authority": {"kind": "public-v1.6-sealed-era",
            "commit": era,
            "paths": ["lib/stdlib-read-line.lisp", "lib/sexp-depth.lisp"]},
        "private_evidence_inputs": 0}
    (PUBLIC / "library.json").write_bytes(canonical(value))
    print("v1.7 public product: LIBRARY MEDIA PASS rows=1")
    return value


def artifact_set(rows: list[dict[str, Any]]) -> str:
    projection = [
        {key: row[key] for key in ("role", "name", "bytes", "sha256")}
        for row in sorted(rows, key=lambda item: (item["role"], item["name"]))]
    return hashlib.sha256(json.dumps(
        projection, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build_selected() -> dict[str, Any]:
    configure_media_paths()
    shared = load(V160.MEDIA.MANIFEST)
    require(shared["artifact_count"] == len(shared["artifacts"]) == 19,
            "public v1.7 shared-media closure absent")
    library = build_library_media()
    rows = [dict(row) for row in shared["artifacts"]]
    for role, name, identity in (
            ("optional-library-d81", "lisp65-library.d81", library["D81"]),
            ("optional-library-index", "l65index", library["index"]),
            ("library-v16core", "v16core.l65s", library["v16core"])):
        rows.append({"role": role, "name": name, **identity})
    require(len(rows) == len({row["role"] for row in rows}) == 22,
            "public v1.7 selected role inventory drift")
    authority = load(AUTHORITY)
    value = {
        "format": "lisp65-v1.7-public-selected-product-v1",
        "status": "passed-public-source-selected-v1.7-native-init-a0-product",
        "artifact_count": 22, "artifact_set_sha256": artifact_set(rows),
        "product_build_id": shared["product_build_id"],
        "profile_build_id": shared["profile_build_id"],
        "private_evidence_inputs": 0,
        "selector": "v1.7-native-init-a0", "artifacts": rows}
    require(value["artifact_set_sha256"] ==
                authority["sealed_product_artifact_set_sha256"],
            "public v1.7 artifact set differs from candidate seal")
    MANIFEST_OUT.write_bytes(canonical(value))
    print("v1.7 public product: SELECTED PASS roles=22 " +
          value["artifact_set_sha256"])
    return value


def check() -> dict[str, Any]:
    check_link()
    value = load(MANIFEST_OUT)
    rows = value.get("artifacts", [])
    authority = load(AUTHORITY)
    require(value.get("format") == "lisp65-v1.7-public-selected-product-v1"
            and value.get("private_evidence_inputs") == 0
            and value.get("selector") == "v1.7-native-init-a0"
            and value.get("artifact_count") == len(rows) == 22
            and artifact_set(rows) == value.get("artifact_set_sha256")
                == authority["sealed_product_artifact_set_sha256"],
            "selected public v1.7 manifest drift")
    for row in rows:
        expected_role(row["role"], ROOT / row["path"])
    print("v1.7 public product: CHECK PASS roles=22 evidence=0")
    return value


def run_stage(action: str) -> None:
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0,
            f"v1.7 public {action} stage red:\n{result.stdout}")
    print(result.stdout.strip())


def build() -> None:
    require(not PUBLIC.exists(), "v1.7 public build is one-shot")
    for action in ("static", "link", "complete", "media", "selected"):
        run_stage(action)
    check()
    print("v1.7 public product: FULL PASS roles=22 evidence=0")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "static", "link", "complete", "media", "selected", "build",
        "check-link", "check"))
    action = parser.parse_args().action
    if action == "static":
        build_static()
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
    except Exception as error:
        print(f"v1.7 public product: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
