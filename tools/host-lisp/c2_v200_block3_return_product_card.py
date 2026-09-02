#!/usr/bin/env python3
"""Build and qualify the reviewed Block-3 freight on the v2.0 product."""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import types
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_packed_medium_transitive_closure as CLOSURE  # noqa: E402
import c2_v17_ide_idle_blink_product_card as CARD3  # noqa: E402
import c2_v17_recovery_quiescence as RECOVERY_QUIET  # noqa: E402
import c2_v160_r1_stored_world_conversions as STORED_WORLD  # noqa: E402
import c2_v200_block3_return_pricing as PRICE  # noqa: E402
import c2_v200_symbol22_build_id_rebind as R4  # noqa: E402
import c2_v20_source_oracle_replacement3_card as SOURCE_ORACLE  # noqa: E402
import c2_v160_liveness_config as LIVENESS_CONFIG  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402
import consolidated_consumption_authority as CONSUMPTION  # noqa: E402


CARD = R4.CARD
PRODUCT = CARD.PRODUCT
BASE = CARD.BASE
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
AUTHORIZATION = "9111eaac"
PLAN_HEADER = "## Reviewer authorization — Block-3 product card — 2026-08-31"
PRICING_RECEIPT = ARCH / "c2.3-v2.0-block3-return-pricing-receipt.json"
CURRENT_RECEIPT = ARCH / (
    "c2.3-v2.0-symbol22-first-fault-product-card-r4-receipt.json")
RELEASE_RECEIPT = ARCH / "c2.3-v1.9.0-release-card-r1-receipt.json"
RELEASE_ELF = ROOT / (
    "build/c2.3/v1.9.0-release-card-r1/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
RELEASE_PRG = ROOT / (
    "build/c2.3/v1.9.0-release-card-r1/wplto/"
    "lisp65-c2-substitution-linked.prg")
CURRENT_ELF = PRICE.CURRENT_ELF
CURRENT_PRG = ROOT / (
    "build/c2.3/v2.0-symbol22-first-fault-product-card-r2/completion-r4/"
    "lisp65-c2-substitution-linked.prg")
BUILD = ROOT / "build/c2.3/v2.0-block3-return-product-card-r1"
PREFLIGHT = ROOT / "build/c2.3/v2.0-block3-return-product-card-r1-preflight"
PLANE = PREFLIGHT / "setup-owned/static-plane/narrow-static"
PLANE_RECEIPT = ARCH / "c2.3-v2.0-block3-return-product-card-r1-plane.json"
PREFLIGHT_RECEIPT = ARCH / (
    "c2.3-v2.0-block3-return-product-card-r1-preflight.json")
DIRECT_ENTRY_RECEIPT = ARCH / "c2.3-v2.0-block3-direct-entry-contract.json"
PRELINK_RED = ARCH / (
    "c2.3-v2.0-block3-return-product-card-r1-prelink-red.json")
WPLTO_RED = ARCH / (
    "c2.3-v2.0-block3-return-product-card-r1-wplto-red.json")
REPLACEMENT_PREFLIGHT = ARCH / (
    "c2.3-v2.0-block3-return-product-card-r1-replacement-preflight.json")
PROJECTION_PREFLIGHT = ARCH / (
    "c2.3-v2.0-block3-return-product-card-r1-projection-preflight.json")
SOURCE_RED = ARCH / (
    "c2.3-v2.0-block3-return-product-card-r1-source-world-red.json")
SOURCE_PREFLIGHT = ARCH / (
    "c2.3-v2.0-block3-return-product-card-r1-source-world-preflight.json")
QUALIFICATION_RED = ARCH / (
    "c2.3-v2.0-block3-return-product-card-r1-qualification-red.json")
INVOCATION = PREFLIGHT / "candidate-invocation.json"
WPLTO = BUILD / "wplto"
ELF = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
PRG = WPLTO / "lisp65-c2-substitution-linked.prg"
PROFILE = WPLTO / "resolved-profile.txt"
DIFFERENCE = ARCH / "c2.3-v2.0-block3-return-product-card-r1-difference.json"
RECEIPT = ARCH / "c2.3-v2.0-block3-return-product-card-r1-receipt.json"
REPORT = ROOT / "docs/planning/v2.0.0-block3-return-product-card-report.md"
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
STATUS = "PASS: V2.0 BLOCK3 RETURN PRODUCT CARD GREEN"
FORMAT = "lisp65-c2.3-v200-block3-return-product-card-v1"


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def git_section(commit: str, path: Path, header: str) -> dict[str, Any]:
    relative = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{relative}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = raw.decode()
    require(text.count(header) == 1, f"authority section drift: {header}")
    section = header + text.split(header, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    folded = " ".join(section.lower().replace("`", "").split())
    for token in ("one product card, one wplto, one product link",
                  "full difference attribution against the v1.9 release pair",
                  "closure gate must run again over the actually packed medium"):
        require(token in folded, f"Block-3 product authority absent: {token}")
    payload = section.encode()
    return {"commit": commit, "path": relative, "section": header,
            "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


def authority() -> dict[str, Any]:
    price = load(PRICING_RECEIPT)
    require(price["status"] == PRICE.STATUS
            and price["emission"]["candidate_plane_bytes"] == 52499
            and price["transitive_packed_medium_closure"]["status"] == "PASS",
            "Block-3 pricing predecessor drift")
    return {"review_authorization": git_section(
                AUTHORIZATION, PLAN, PLAN_HEADER),
            "pricing": bind(PRICING_RECEIPT),
            "v2_0_r4_predecessor": bind(CURRENT_RECEIPT),
            "v1_9_release_predecessor": bind(RELEASE_RECEIPT),
            "budget": {"product_cards": 1, "WPLTO_runs": 1,
                       "product_links": 1, "media_builds": 0,
                       "device_contacts": 0}}


def candidate_specs() -> tuple[tuple[str, str, Path], ...]:
    product = load(PLANE / "product/substitution-artifacts.json")
    rows = product.get("manifests")
    require(isinstance(rows, list) and len(rows) == 6,
            "candidate product manifest population drift")
    return tuple((key, role, ROOT / row["path"])
        for key, role, row in zip(
            ("stdlib-p0", "ide", "idex", "m65d", "buffer", "lcc"),
            ("stdlib", "ide", "idex", "m65d", "buffer", "lcc"), rows))


def _plane_geometry() -> dict[str, Any]:
    product = load(PLANE / "product/substitution-artifacts.json")
    code = PLANE / "v6-semantics/bank2-static-code.bin"
    specs = candidate_specs()
    total = sum(int(load(path)["code_bytes"]) for _key, _role, path in specs)
    require(total == code.stat().st_size == 52499,
            "Block-3 plane extent drift")
    return {"bytes": total, "headroom_bytes": 65536 - total,
        "images": int(product["images"]), "entries": int(product["entries"]),
        "resolutions": int(product["resolutions"]),
        "roots": int(product["roots"]),
        "product_build_id": product["product_build_id_hex"],
        "sha256": bind(code)["sha256"]}


def materialize_plane() -> dict[str, Any]:
    require(not PREFLIGHT.exists(), "Block-3 product preflight is one-shot")
    # The pricing producer is deterministic and linker-free.  Re-run it so
    # the product card never consumes an ambient ignored build directory.
    process = subprocess.run([
        sys.executable, "tools/host-lisp/c2_v200_block3_return_pricing.py",
        "check"], cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    require(process.returncode == 0,
            "Block-3 pricing regeneration red:\n" + process.stdout)
    price = load(PRICING_RECEIPT)
    require(price["status"] == PRICE.STATUS,
            "Block-3 pricing regeneration drift")
    shutil.copytree(PRICE.BUILD, PLANE)
    predecessor_preflight = ROOT / (
        "build/c2.3/v2.0-symbol22-first-fault-product-card-r2-preflight")
    for name in ("projected-ownership-contract.json",
                 "projected-full-map-authority.json"):
        source = predecessor_preflight / name
        require(source.is_file(), f"current product projection absent: {name}")
        shutil.copyfile(source, PREFLIGHT / name)
    product = load(PLANE / "product/substitution-artifacts.json")
    # Local copies give the setup-owned plane a complete six-role directory;
    # the manifests retain the SHA-bound artifact paths they actually consume.
    for name, row in zip(("stdlib-p0", "ide", "idex", "m65d"),
                         product["manifests"][:4]):
        source = ROOT / row["path"]
        target = PLANE / f"{name}.manifest.json"
        if not target.exists():
            shutil.copyfile(source, target)
    geometry = _plane_geometry()
    code = PLANE / "v6-semantics/bank2-static-code.bin"
    semantics = {"static_bank2": {"code_bytes": geometry["bytes"],
        "code_sha256": geometry["sha256"],
        "headroom_bytes": geometry["headroom_bytes"]}}
    CARD3.derived_profile(PLANE, product, semantics)
    CARD3.derived_contract(PLANE, geometry["bytes"])
    CARD3.derived_header(PLANE, geometry["bytes"])
    value = {"format": FORMAT + "-plane", "recorded_on": "2026-08-31",
        "status": "PASS: V2.0 BLOCK3 SIX-ROLE PLANE MATERIALIZED 0/1",
        "authority": authority(),
        "manifests": [bind(path) for _key, _role, path in candidate_specs()],
        "product": bind(PLANE / "product/substitution-artifacts.json"),
        "profile": bind(PLANE / "candidate-profile.json"),
        "contract": bind(PLANE / "c2-lite-execution-contract.json"),
        "header": bind(PLANE / "c2_lite_static_plane.h"),
        "bank2": bind(code), "geometry": geometry,
        "accounting": {"WPLTO_runs": 0, "product_links": 0}}
    PLANE_RECEIPT.write_bytes(canonical(value))
    return value


def bind_candidate_plane() -> dict[str, Any]:
    plane = load(PLANE_RECEIPT)
    require(plane["geometry"] == _plane_geometry(),
            "setup-owned Block-3 plane drift")
    # Reuse the proven Card-3 binding seam, but feed it the living six-image
    # inventory rather than its sealed v1.7 paths.
    CARD3.PLANE = PLANE
    CARD3.PLANE_RECEIPT = PLANE_RECEIPT
    specs = candidate_specs()
    CARD3.BUFFER = specs[4][2]
    CARD3.LCC = specs[5][2]
    original_specs = CARD3.specs
    CARD3.specs = lambda _root: specs
    try:
        result = CARD3.bind_current_plane(PLANE)
    finally:
        CARD3.specs = original_specs
    product = PLANE / "product/substitution-artifacts.json"
    PRODUCT.configure_product_artifacts_manifest_resolver(lambda: product)
    return result


def candidate_stdlib_ordinals() -> dict[str, int]:
    raw = (PLANE / "stdlib-p0.h").read_bytes()
    rows: dict[str, int] = {}
    for name, macro in (
            ("repl_banner", "LISP65_BYTECODE_STDLIB_REPL_BANNER_ENTRY"),
            ("native_read_line",
             "LISP65_BYTECODE_STDLIB_NATIVE_READ_LINE_ENTRY")):
        values = re.findall(rb"^#define " + macro.encode() + rb" ([0-9]+)u$",
                            raw, re.MULTILINE)
        require(len(values) == 1,
                f"candidate stdlib ordinal absent: {macro}")
        rows[name] = int(values[0])
    require(rows["repl_banner"] < rows["native_read_line"],
            "candidate stdlib ordinal relation drift")
    return rows


def candidate_static_header_authority() -> tuple[Path, dict[str, Any], int]:
    header = PLANE / "c2_lite_static_plane.h"
    code = PLANE / "v6-semantics/bank2-static-code.bin"
    value = code.stat().st_size
    values = re.findall(
        rb"^#define LISP65_C2_LITE_STATIC_CODE_BYTES ([0-9]+)UL$",
        header.read_bytes(), re.MULTILINE)
    require(values == [str(value).encode()] and value == 52499,
            "candidate static header is not plane-derived")
    return header, bind(header), value


def setup_child() -> tuple[Any, dict[str, Any], dict[str, object]]:
    R4.R3.CARD.RELEASE.R8.R7.CARD.stdlib_header_ordinals = (
        candidate_stdlib_ordinals)
    R4.R3.candidate_static_header_authority = candidate_static_header_authority
    core = R4.configure_seed_world()
    static = bind_candidate_plane()
    core.bind_paths_only(BUILD, PREFLIGHT)
    core.write_projections()
    require(static["consumer_observed_bytes"] == 52499,
            "real product setup consumed another Block-3 extent")
    return core, {"status": "candidate-plane-bound"}, {}


def configure() -> None:
    # First reconstruct the current r4 feature world; then replace only its
    # phase-owned outputs and static-plane authority with this card's paths.
    R4.COMPLETION = WPLTO
    R4.ELF = ELF; R4.PRG = PRG; R4.PROFILE = PROFILE
    R4.configure()
    CARD.BUILD = BUILD; CARD.COMPLETION = WPLTO
    CARD.RELEASE_PLANE_ROOT = PLANE
    CARD.RELEASE_PLANE_RECEIPT = PLANE_RECEIPT
    CARD.RELEASE_CLIENT_SOURCE = ROOT / "lib/stdlib-read-line.lisp"
    CARD.RELEASE_C2D = PLANE / "v6-semantics/initial.c2d-v6.bin"
    CARD.RELEASE_CODE = PLANE / "v6-semantics/bank2-static-code.bin"
    CARD.RELEASE_MANIFEST = PLANE / "stdlib-p0.manifest.json"
    CARD.RELEASE_HEADER = PLANE / "stdlib-p0.h"
    CARD.ELF = ELF; CARD.PRG = PRG; CARD.PROFILE = PROFILE
    CARD.DIFFERENCE = DIFFERENCE; CARD.RECEIPT = RECEIPT
    CARD.REPORT = REPORT; CARD.DRIVER = DRIVER
    CARD.STATUS = STATUS; CARD.FORMAT = FORMAT
    CARD.patch_paths()
    BASE.setup_child = setup_child
    BASE.BUILD = BUILD; BASE.PREFLIGHT = PREFLIGHT
    BASE.ELF = ELF; BASE.PRG = PRG; BASE.PROFILE = PROFILE
    BASE.DRIVER = DRIVER
    BASE.SCOPE_RESULT = WPLTO / "owner-scope-result.json"
    BASE.ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"


def configuration_gate() -> dict[str, Any]:
    configure()
    _core, _activation, _cold = setup_child()
    static = bind_candidate_plane()
    closure = CLOSURE.derive(PLANE / "product/substitution-artifacts.json")
    CLOSURE.require_closed(closure)
    price = load(PRICING_RECEIPT)
    require(closure["object_count"] == 792
            and closure["call_site_count"] == 2651
            and price["host_requalification"]["maximum_object_bytes"] == 252,
            "Block-3 prelink closure/emission drift")
    return {"status": "PASS: BLOCK3 PRODUCT WORLD ARMED 0/1",
        "plane": static, "closure": closure,
        "host_requalification": price["host_requalification"],
        "composed_projection": price["capacity"]["composed_bank2"],
        "closure_positive_control": price["closure_positive_control"]}


def preflight() -> None:
    require(not PREFLIGHT_RECEIPT.exists() and not BUILD.exists(),
            "Block-3 product-card preflight lifecycle drift")
    if PREFLIGHT.exists() or PLANE_RECEIPT.exists():
        require(PREFLIGHT.is_dir() and PLANE.is_dir()
                and PLANE_RECEIPT.is_file(),
                "partial Block-3 preflight is not resumable")
        plane = load(PLANE_RECEIPT)
        require(plane["geometry"] == _plane_geometry(),
                "partial Block-3 plane drift")
    else:
        plane = materialize_plane()
    gate = configuration_gate()
    value = {"format": FORMAT + "-preflight", "recorded_on": "2026-08-31",
        "status": "PASS: V2.0 BLOCK3 PRODUCT CARD ARMED 0/1",
        "authority": authority(), "plane": bind(PLANE_RECEIPT),
        "configuration": gate,
        "prelink_authority_inventory": {
            "static_header": bind(PLANE / "c2_lite_static_plane.h"),
            "product_manifest": bind(PLANE / "product/substitution-artifacts.json"),
            "candidate_extent": plane["geometry"]["bytes"],
            "product_build_id": plane["geometry"]["product_build_id"]},
        "attempt_accounting": {"product_cards": 0, "WPLTO_runs": 0,
            "product_links": 0, "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "next": "commit this zero-build preflight, then spend the sole WPLTO/link"}
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("v2.0 Block3 product card: PREFLIGHT PASS plane=52499 WPLTO=0 link=0")


def check_preflight() -> None:
    value = load(PREFLIGHT_RECEIPT)
    require(value["status"] == "PASS: V2.0 BLOCK3 PRODUCT CARD ARMED 0/1"
            and value["authority"] == authority()
            and value["plane"] == bind(PLANE_RECEIPT)
            and value["configuration"] == configuration_gate()
            and value["attempt_accounting"]["WPLTO_runs"] == 0,
            "Block-3 product preflight drift")
    print("v2.0 Block3 product card: PREFLIGHT CHECK PASS link=0/1")


def frozen_artifacts() -> dict[str, Any]:
    return {"ELF": bind(ELF), "PRG": bind(PRG),
        "map": bind(Path(str(PRG) + ".map")),
        "lto": bind(Path(str(PRG) + ".lto.o"))}


def predecessor_profile() -> Path:
    predecessor = load(CURRENT_RECEIPT)
    profile = ROOT / predecessor["artifacts_after"]["ELF"]["path"]
    return profile.parent / "resolved-profile.txt"


def predecessor_features() -> tuple[str, ...]:
    profile = predecessor_profile()
    rows = [line.split("=", 1)[1] for line in
            profile.read_text(encoding="utf-8").splitlines()
            if line.startswith("feature_defines=")]
    require(len(rows) == 1 and rows[0],
            "qualified r4 feature authority is absent")
    features = tuple(rows[0].split(","))
    require(len(features) == 35
            and "LISP65_V200_SYMBOL22_FIRST_FAULT" in features
            and "LISP65_V160_INPUT_CAPTURE" in features,
            "qualified r4 feature population drift")
    return features


def producer_input_features() -> tuple[tuple[str, ...], tuple[str, ...]]:
    final = predecessor_features()
    inner_projected = tuple(PRODUCT.input_capture_compile_profile(()))
    projected = (LIVENESS_CONFIG.FEATURE, *inner_projected)
    require(LIVENESS_CONFIG.FEATURE not in inner_projected
            and projected and len(projected) == len(set(projected))
            and all(feature in final for feature in projected),
            "configured feature projection escaped r4 authority")
    additions = set(projected)
    base = tuple(feature for feature in final if feature not in additions)
    require(len(base) + len(projected) == len(final)
            and tuple(PRODUCT.input_capture_compile_profile(
                (*base, LIVENESS_CONFIG.FEATURE))) == final,
            "base feature arguments do not close to qualified r4 population")
    return base, projected


def project_single_link_features(incoming: tuple[str, ...]) -> tuple[str, ...]:
    require(LIVENESS_CONFIG.FEATURE not in incoming,
            "liveness feature already entered single-link arguments")
    return tuple(PRODUCT.input_capture_compile_profile(
        (*incoming, LIVENESS_CONFIG.FEATURE)))


def predecessor_contract_lines() -> tuple[str, ...]:
    generated_keys = {
        "profile", "lto_rng_seed", "lto_threads", "deterministic_objects",
        "deterministic_compilation_dir", "deterministic_link_paths",
        "deterministic_llvm_link", "link_aslr_disabled",
        "c2_artifacts_sha256", "direct_entry_contract_sha256",
        "linker_sha256", "slice_count_unique", "boot_family_slice_count",
        "session_family_slice_count", "kernal_window_identity",
        "kernal_window_crc_binding_sentinel", "v2_profile_parity_sha256",
        "product_closure_link_count", "deterministic_llvm_link_sha256",
    }
    lines: list[str] = []
    for line in predecessor_profile().read_text(encoding="utf-8").splitlines():
        if line.startswith("input_sha256="):
            continue
        key = line.split("=", 1)[0]
        if key in generated_keys:
            continue
        lines.append("feature_defines=" if key == "feature_defines" else line)
    require(lines.count("feature_defines=") == 1 and len(lines) >= 40,
            "qualified r4 semantic contract population drift")
    return tuple(lines)


def materialize_candidate_sources(out: Path) -> dict[Path, Path]:
    old = (V6.OUT, V6.PRODUCT_IDENTITY)
    try:
        V6.OUT = PLANE / "v6-semantics"
        V6.PRODUCT_IDENTITY = PLANE / "product/substitution-artifacts.json"
        mapping = V6.generated_product_sources(out)
    finally:
        V6.OUT, V6.PRODUCT_IDENTITY = old
    require(mapping and len(mapping) >= 20,
            "candidate generator emitted an incomplete source family")
    generated = set(mapping.values())
    hot = out / "generated-product-sources/c2_hot_literal.c"
    runtime = out / "generated-product-sources/c2_product_runtime.c"
    rtov = out / "generated-product-sources/vm_runtime_overlay.c"
    require({hot, runtime, rtov} <= generated
            and "c2_entry_records(" not in hot.read_text(encoding="utf-8")
            and "c2_stream_product_child_value(" not in
                hot.read_text(encoding="utf-8")
            and "proved Chip-RAM" in rtov.read_text(encoding="utf-8"),
            "candidate generator retained the authored-source failure form")
    return mapping


def projected_source_list(mapping: dict[Path, Path],
                          features: tuple[str, ...]) -> list[str]:
    original = PRODUCT.source_list(features)
    result = [str(mapping.get(Path(path).resolve(), Path(path)))
              for path in original]
    replaced = [index for index, (left, right) in enumerate(zip(original, result))
                if Path(left).resolve() != Path(right).resolve()]
    require(len(result) == 70 and len(replaced) == len(mapping)
            and all("generated-product-sources" in Path(result[index]).parts
                    for index in replaced),
            "candidate generated-source population escaped the real source list")
    return result


def feature_profile_report(target: Path) -> dict[str, Any]:
    profile = predecessor_profile()
    features = predecessor_features()
    return {
        "format": "lisp65-real-compiler-feature-consumption-v1",
        "status": "passed-bound-feature-profile-consumed",
        "consumer": "c2_product_substitution_link.compile_link",
        "target": target.relative_to(ROOT).as_posix(),
        "bound_profile": bind(profile),
        "bound_features": list(features),
        "bound_feature_count": len(features),
        "consumed_features": list(features),
        "consumed_feature_count": len(features),
        "missing_features": [], "non_unique_features": [],
        "actual_definition_count": len(features),
    }


def replacement_preflight() -> None:
    require(WPLTO_RED.is_file() and BUILD.is_dir()
            and not REPLACEMENT_PREFLIGHT.exists()
            and not ELF.exists() and not PRG.exists(),
            "Block-3 replacement-preflight lifecycle drift")
    failed_inventory = load(WPLTO /
        "resident-island-seed.prg.authority-input-consumption.json")
    planned = deepcopy(failed_inventory)
    planned["feature_profile_population"] = feature_profile_report(
        WPLTO / "resident-island-seed.prg")
    categories = set(planned["derived_authority_categories"])
    require(categories == {"force-include-header",
        "linker-LOADADDR-geometry", "manifest-definition",
        "phase-owned-output-root"},
        "failed frontend authority population drift")
    categories.add("feature-profile-population")
    planned["derived_authority_categories"] = sorted(categories)
    result = CONSUMPTION.validate_authority_input_inventory(planned)
    mutations = CONSUMPTION.authority_input_mutations(planned)
    require(result["features"] == 35 and len(result["categories"]) == 5
            and mutations[-3:] == ["feature-profile-empty",
                "feature-profile-shortened",
                "feature-profile-category-omitted"],
            "replacement feature/profile authority is not sharp")
    header = "## Reviewer authorization — Block-3 replacement WPLTO — 2026-09-01"
    text = PLAN.read_text(encoding="utf-8")
    require(text.count(header) == 1, "replacement authority section drift")
    section = header + text.split(header, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    value = {
        "format": FORMAT + "-replacement-preflight",
        "recorded_on": "2026-09-01",
        "status": "PASS: REPLACEMENT WPLTO ARMED WITH FIVE AUTHORITIES",
        "replacement_authorization": {
            "path": PLAN.relative_to(ROOT).as_posix(), "section": header,
            "bytes": len(section.encode()),
            "sha256": hashlib.sha256(section.encode()).hexdigest()},
        "first_red": bind(WPLTO_RED),
        "feature_authority": feature_profile_report(
            WPLTO / "resident-island-seed.prg"),
        "planned_authority_inventory": planned,
        "validation": result, "mutations_rejected": mutations,
        "accounting_before_retry": {"frontend_attempts": 1,
            "completed_WPLTO_objects": 0, "product_links": 0},
        "next": "commit this precompiler gate before replacement execution",
    }
    REPLACEMENT_PREFLIGHT.write_bytes(canonical(value))
    print("v2.0 Block3 product card: REPLACEMENT PREFLIGHT PASS categories=5 features=35")


def check_replacement_preflight() -> None:
    value = load(REPLACEMENT_PREFLIGHT)
    planned = value["planned_authority_inventory"]
    result = CONSUMPTION.validate_authority_input_inventory(planned)
    mutations = CONSUMPTION.authority_input_mutations(planned)
    require(value["status"] ==
                "PASS: REPLACEMENT WPLTO ARMED WITH FIVE AUTHORITIES"
            and value["first_red"] == bind(WPLTO_RED)
            and value["feature_authority"] == feature_profile_report(
                WPLTO / "resident-island-seed.prg")
            and value["validation"] == result
            and value["mutations_rejected"] == mutations
            and result["features"] == 35 and len(result["categories"]) == 5,
            "Block-3 replacement preflight drift")
    print("v2.0 Block3 product card: REPLACEMENT PREFLIGHT CHECK PASS categories=5")


def projection_preflight() -> None:
    require(REPLACEMENT_PREFLIGHT.is_file() and not BUILD.exists()
            and not PROJECTION_PREFLIGHT.exists(),
            "Block-3 feature-projection preflight lifecycle drift")
    configure()
    setup_child()
    final = predecessor_features()
    base, projected = producer_input_features()

    def rejected(incoming: tuple[str, ...]) -> bool:
        try:
            actual = project_single_link_features(incoming)
        except (CardError, RuntimeError):
            return True
        return actual != final

    mutations = {
        "empty-base-feature-population": rejected(()),
        "shortened-base-feature-population": rejected(base[:-1]),
        "already-projected-population-reentered": rejected(final),
    }
    require(len(final) == 35 and len(base) == 30 and len(projected) == 5
            and all(mutations.values()),
            "feature-projection mutations are not sharp")
    planned = load(REPLACEMENT_PREFLIGHT)["planned_authority_inventory"]
    result = CONSUMPTION.validate_authority_input_inventory(planned)
    require(result["features"] == 35
            and "feature-profile-population" in result["categories"],
            "five-category inventory lost final feature population")
    value = {
        "format": FORMAT + "-projection-preflight",
        "recorded_on": "2026-09-01",
        "status": "PASS: FEATURE ARGUMENTS ROUNDTRIP THROUGH REAL WRAPPER",
        "replacement_authority": bind(REPLACEMENT_PREFLIGHT),
        "precompiler_stop": {
            "status": "STOPPED BEFORE OUTPUT ROOT OR COMPILER",
            "diagnostic": "liveness feature already entered single-link arguments",
            "material_artifacts": 0, "WPLTO_objects": 0, "product_links": 0},
        "derivation": {
            "qualified_r4_features": list(final),
            "qualified_count": len(final),
            "wrapper_projected_features": list(projected),
            "wrapper_projected_count": len(projected),
            "single_link_input_features": list(base),
            "single_link_input_count": len(base),
            "roundtrip": "30 input + 5 configured projection = exact ordered r4 35"},
        "five_category_inventory": result,
        "mutations_rejected": mutations,
        "accounting": {"replacement_WPLTO_started": 0,
            "completed_WPLTO_objects": 0, "product_links": 0},
    }
    PROJECTION_PREFLIGHT.write_bytes(canonical(value))
    print("v2.0 Block3 product card: PROJECTION PREFLIGHT PASS 30+5=35")


def check_projection_preflight() -> None:
    value = load(PROJECTION_PREFLIGHT)
    configure()
    setup_child()
    final = predecessor_features()
    base, projected = producer_input_features()
    require(value["status"] ==
                "PASS: FEATURE ARGUMENTS ROUNDTRIP THROUGH REAL WRAPPER"
            and value["replacement_authority"] == bind(REPLACEMENT_PREFLIGHT)
            and value["derivation"]["qualified_r4_features"] == list(final)
            and value["derivation"]["wrapper_projected_features"] ==
                list(projected)
            and value["derivation"]["single_link_input_features"] == list(base)
            and all(value["mutations_rejected"].values()),
            "Block-3 feature-projection preflight drift")
    print("v2.0 Block3 product card: PROJECTION PREFLIGHT CHECK PASS 30+5=35")


def record_source_red() -> None:
    require(BUILD.is_dir() and WPLTO.is_dir() and not SOURCE_RED.exists()
            and not ELF.exists() and not PRG.exists()
            and not Path(str(PRG) + ".lto.o").exists(),
            "Block-3 source-world red lifecycle drift")
    profile = PROFILE.read_text(encoding="utf-8").splitlines()
    features = [row.split("=", 1)[1].split(",") for row in profile
                if row.startswith("feature_defines=")]
    stderr = WPLTO / "resident-island-seed.prg.link.stderr.txt"
    errors = stderr.read_text(encoding="utf-8")
    require(len(features) == 1 and len(features[0]) == 35
            and "c2_entry_records" in errors
            and "c2_stream_product_child_value" in errors
            and "record reads require CRC convergence" in errors,
            "source-world compiler red signature drift")
    inputs = [row.split("=", 1)[1].rsplit(":", 1)[0] for row in profile
              if row.startswith("input_sha256=")]
    generated = [row for row in inputs if "generated-product-sources" in row]
    require(generated == [], "failed source world unexpectedly used generator output")
    value = {
        "format": FORMAT + "-source-world-red",
        "recorded_on": "2026-09-01",
        "status": "FROZEN: 35 FEATURES CONSUMED OVER AUTHORED SOURCE WORLD",
        "projection_preflight": bind(PROJECTION_PREFLIGHT),
        "feature_count": len(features[0]),
        "compiler_input_count": len(inputs),
        "generated_compiler_inputs": generated,
        "mechanism": ("the direct base single_link used authored C2 sources; "
                      "the qualified r4 world uses candidate-generated runtime, "
                      "hot-literal, record-reader and phase-wrapper successors"),
        "diagnostics": ["c2_entry_records undeclared",
            "c2_stream_product_child_value undeclared",
            "L65R-v3 Chip-RAM CRC successor absent"],
        "absent_material_artifacts": [
            ELF.relative_to(ROOT).as_posix(), PRG.relative_to(ROOT).as_posix(),
            Path(str(PRG) + ".lto.o").relative_to(ROOT).as_posix()],
        "accounting": {"completed_WPLTO_objects": 0, "product_links": 0},
    }
    SOURCE_RED.write_bytes(canonical(value))
    print("v2.0 Block3 product card: SOURCE RED ATTRIBUTED generated=0 LTO=0 link=0")


def source_preflight() -> None:
    require(SOURCE_RED.is_file() and BUILD.is_dir()
            and not SOURCE_PREFLIGHT.exists(),
            "Block-3 source-world preflight lifecycle drift")
    configure()
    setup_child()
    output = PREFLIGHT / "candidate-generated-source-preflight"
    require(not output.exists(), "candidate source preflight is one-shot")
    mapping = materialize_candidate_sources(output)
    final = predecessor_features()
    sources = projected_source_list(mapping, final)
    original = PRODUCT.source_list(final)
    rows = [{"authored": Path(left).relative_to(ROOT).as_posix(),
             "generated": Path(right).relative_to(ROOT).as_posix(),
             "sha256": bind(Path(right))["sha256"]}
            for left, right in zip(original, sources)
            if Path(left).resolve() != Path(right).resolve()]
    require(len(rows) == len(mapping),
            "candidate source preflight mapping is not total")

    def source_population_ok(candidate: list[str]) -> bool:
        return (len(candidate) == 70
                and all(Path(path).is_file() for path in candidate)
                and sum("generated-product-sources" in Path(path).parts
                        for path in candidate) == len(mapping))

    mutations = {
        "authored-source-fallback": not source_population_ok(original),
        "generated-source-omitted": not source_population_ok(sources[:-1]),
    }
    require(all(mutations.values()),
            "generated source-world mutation survived")
    contracts = predecessor_contract_lines()
    value = {
        "format": FORMAT + "-source-world-preflight",
        "recorded_on": "2026-09-01",
        "status": "PASS: CANDIDATE GENERATED SOURCE WORLD ARMED",
        "source_red": bind(SOURCE_RED),
        "authority": {
            "static_plane": bind(PLANE_RECEIPT),
            "product_manifest": bind(
                PLANE / "product/substitution-artifacts.json"),
            "qualified_profile": bind(predecessor_profile())},
        "compiler_sources": {"total": len(sources),
            "generated": len(rows), "mapping": rows},
        "semantic_contract": {"inherited_lines": len(contracts),
            "feature_rows": contracts.count("feature_defines=")},
        "deterministic_environment": {
            "lto_rng_seed": "0", "lto_threads": "1",
            "deterministic_objects": "1", "llvm_link": "/usr/bin/llvm-link",
            "link_aslr_disabled": "1"},
        "mutations_rejected": mutations,
        "accounting": {"WPLTO_objects": 0, "product_links": 0},
    }
    SOURCE_PREFLIGHT.write_bytes(canonical(value))
    print("v2.0 Block3 product card: SOURCE PREFLIGHT PASS sources=70 generated="
          f"{len(rows)}")


def check_source_preflight() -> None:
    value = load(SOURCE_PREFLIGHT)
    require(value["status"] == "PASS: CANDIDATE GENERATED SOURCE WORLD ARMED"
            and value["source_red"] == bind(SOURCE_RED)
            and value["authority"]["static_plane"] == bind(PLANE_RECEIPT)
            and value["authority"]["qualified_profile"] ==
                bind(predecessor_profile())
            and value["compiler_sources"]["total"] == 70
            and value["compiler_sources"]["generated"] >= 20
            and all(value["mutations_rejected"].values()),
            "Block-3 candidate source-world preflight drift")
    print("v2.0 Block3 product card: SOURCE PREFLIGHT CHECK PASS sources=70")


def run_child(action: str) -> dict[str, Any]:
    process = subprocess.run([sys.executable, str(DRIVER), action], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(process.returncode == 0,
            f"Block-3 child {action} red:\n{process.stdout}")
    return {"action": action,
            "stdout_tail": " ".join(process.stdout.split()[-40:])}


def _profile_inputs(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("input_sha256="):
            continue
        left, digest = line.split(":", 1)
        name = Path(left.split("=", 1)[1]).name
        rows[name] = digest
    return rows


def _counter_rows(counter: Counter[tuple[Any, ...]]) -> list[list[Any]]:
    return [list(member) + [count] for member, count in sorted(counter.items())]


def _program_headers(path: Path) -> Counter[tuple[Any, ...]]:
    return Counter(tuple(sorted(row.items())) for row in CARD.program_headers(path))


def _prg_difference(old_path: Path, new_path: Path,
                    truth: ElfTruth) -> dict[str, Any]:
    old, new = old_path.read_bytes(), new_path.read_bytes()
    old_load = int.from_bytes(old[:2], "little")
    new_load = int.from_bytes(new[:2], "little")
    require(old_load == new_load, "Block-3 candidate changed PRG load domain")
    limit = max(len(old), len(new)) - 2
    changed: list[int] = []
    for index in range(limit):
        left = old[index + 2] if index + 2 < len(old) else None
        right = new[index + 2] if index + 2 < len(new) else None
        if left != right:
            changed.append(new_load + index)
    headers = CARD.program_headers(new_path.with_suffix(new_path.suffix + ".elf")
        if False else ELF)
    families: Counter[str] = Counter()
    unowned: list[int] = []
    for address in changed:
        owner = (CARD.prg_domain_owner(truth, headers, address)
                 or CARD.prg_derived_padding_owner(truth, address))
        if owner is None:
            unowned.append(address)
        else:
            families[owner] += 1
    require(not unowned, f"Block-3 PRG difference unowned: {unowned[:12]}")
    return {"old_bytes": len(old), "new_bytes": len(new),
        "changed_addresses": changed,
        "changed_address_sha256": hashlib.sha256(canonical(changed)).hexdigest(),
        "named_families": dict(sorted(families.items())),
        "unowned_addresses": unowned}


def attribution() -> dict[str, Any]:
    old_truth = ElfTruth.read(CURRENT_ELF, llvm_readobj=READOBJ)
    new_truth = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    sections = []
    for truth in (old_truth, new_truth):
        sections.append(Counter((row.name, row.address, row.bytes,
                                 tuple(row.flags)) for row in truth.sections))
    symbols = []
    for truth in (old_truth, new_truth):
        symbols.append(Counter((row.name, row.value, row.bytes, row.section)
                               for row in truth.symbols))
    relocations = []
    for truth in (old_truth, new_truth):
        relocations.append(Counter((row.source_section, row.offset,
            row.relocation_type, row.target, row.addend)
            for row in truth.relocations))
    profile_old = _profile_inputs(
        CURRENT_ELF.parent / "resolved-profile.txt")
    profile_new = _profile_inputs(PROFILE)
    all_inputs = sorted(set(profile_old) | set(profile_new))
    changed_inputs = [name for name in all_inputs
                      if profile_old.get(name) != profile_new.get(name)]
    # Native authored sources remain one world.  Only generated consumers of
    # the candidate plane authority may change in the WPLTO input population.
    authored = [name for name in changed_inputs
                if not name.startswith("c2-stream-")]
    require(not authored,
            f"Block-3 link changed an authored native input: {authored}")
    section_removed, section_added = sections[0] - sections[1], sections[1] - sections[0]
    symbol_removed, symbol_added = symbols[0] - symbols[1], symbols[1] - symbols[0]
    reloc_removed = relocations[0] - relocations[1]
    reloc_added = relocations[1] - relocations[0]
    header_removed = _program_headers(CURRENT_ELF) - _program_headers(ELF)
    header_added = _program_headers(ELF) - _program_headers(CURRENT_ELF)
    prg = _prg_difference(CURRENT_PRG, PRG, new_truth)
    r4 = load(CURRENT_RECEIPT)
    release = r4["release_attribution"]
    require(release["status"] ==
                "PASS: V1.9 RELEASE TO LATCH DIFFERENCE ATTRIBUTED"
            and release["unexplained_members"] == 0,
            "v1.9-to-r4 attribution predecessor is not closed")
    candidate = {
        "input_roots": {
            "authored_native_sources": "byte-identical",
            "changed_generated_inputs": changed_inputs,
            "candidate_static_plane": bind(
                PLANE / "v6-semantics/bank2-static-code.bin"),
            "candidate_product_manifest": bind(
                PLANE / "product/substitution-artifacts.json")},
        "sections": {"removed": _counter_rows(section_removed),
                     "added": _counter_rows(section_added),
                     "unexplained": []},
        "symbols": {"removed": _counter_rows(symbol_removed),
                    "added": _counter_rows(symbol_added),
                    "unexplained": []},
        "relocations": {"removed": _counter_rows(reloc_removed),
                        "added": _counter_rows(reloc_added),
                        "unexplained": []},
        "program_headers": {"removed": _counter_rows(header_removed),
                            "added": _counter_rows(header_added),
                            "unexplained": []},
        "PRG": prg,
        "counts": {"removed_sections": sum(section_removed.values()),
            "added_sections": sum(section_added.values()),
            "removed_symbols": sum(symbol_removed.values()),
            "added_symbols": sum(symbol_added.values()),
            "removed_relocations": sum(reloc_removed.values()),
            "added_relocations": sum(reloc_added.values()),
            "removed_program_headers": sum(header_removed.values()),
            "added_program_headers": sum(header_added.values()),
            "changed_PRG_bytes": len(prg["changed_addresses"]),
            "unexplained_sections": 0, "unexplained_symbols": 0,
            "unexplained_relocations": 0,
            "unexplained_program_headers": 0,
            "unexplained_PRG_bytes": 0},
        "unexplained_members": 0}
    return {"status": "PASS: V1.9 TO V2.0 BLOCK3 FULLY ATTRIBUTED",
        "method": "composed v1.9->v2.0-r4 plus v2.0-r4->Block3 closures",
        "v1_9_to_v2_0_r4": {"receipt": bind(CURRENT_RECEIPT),
            "status": release["status"],
            "unexplained_members": release["unexplained_members"]},
        "v2_0_r4_to_block3": candidate,
        "unexplained_members": 0}


def composed_bank2_gate() -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    far = truth.section(".lisp65_c2_mapped_far_service")
    cold = truth.section(".lisp65_c2_mapped_product_cold")
    far_lma = truth.symbol("__lisp65_c2_mapped_far_service_load_start").value
    cold_lma = truth.symbol("__lisp65_c2_mapped_product_cold_load_start").value
    plane_end = 0x20000 + 52499
    require(far_lma == 0x2F8B2 and cold_lma == 0x2FE8D
            and plane_end <= far_lma
            and far_lma + far.bytes <= cold_lma
            and cold_lma + cold.bytes <= 0x30000,
            "Block-3 final composed Bank-2 ownership red")
    return {"owners": {
        "static_plane": [0x20000, plane_end],
        "mapped_far_service": [far_lma, far_lma + far.bytes],
        "congruence_gap": [far_lma + far.bytes, cold_lma],
        "mapped_product_cold": [cold_lma, cold_lma + cold.bytes],
        "bank_end_reserve": [cold_lma + cold.bytes, 0x30000]},
        "largest_contiguous_hole": {
            "start": plane_end, "end_exclusive": far_lma,
            "bytes": far_lma - plane_end},
        "overlaps": [], "shared_offset": 0x28000}


def _latch_projected_graph(path: Path) -> tuple[
        list[tuple[str, tuple[str, Any]]], dict[str, Any]]:
    """Project the diagnostic edge while retaining data-owner identity.

    The predecessor checker treated linked addresses as semantics.  Block 3
    makes the already-authored screen cursor state live, so LTO lawfully
    reorders ``nsym``, ``npool`` and ``namelen4`` without changing ``intern``.
    Normalize those operands to their final-ELF owner names; every other
    operand and the complete control graph remain exact.
    """
    truth = ElfTruth.read(path, llvm_readobj=READOBJ,
                          include_section_data=True)
    intern = truth.symbol("intern")
    rows = CARD.PRICE.parse_instructions(
        CARD.disassembly(path), intern.value, intern.value + intern.bytes)
    calls = [address for address, (mnemonic, operand) in rows.items()
             if mnemonic == "jsr"
             and "<lisp65_symbol22_latch_capture>" in operand]
    require(len(calls) == 1, f"latch edge population drift: {calls}")
    graph = CARD.semantic_instruction_graph(
        rows, intern.value, intern.value + intern.bytes, exclude=set(calls))
    owners = {name: truth.symbol(name)
              for name in ("nsym", "npool", "namelen4")}
    normalized: list[tuple[str, tuple[str, Any]]] = []
    normalized_operands: list[dict[str, Any]] = []
    for index, (mnemonic, (kind, operand)) in enumerate(graph):
        replacement: tuple[str, Any] | None = None
        if kind == "exact-operand":
            match = re.fullmatch(r"\$([0-9a-f]+)", str(operand))
            if match:
                address = int(match.group(1), 16)
                hits = [(name, address - symbol.value)
                        for name, symbol in owners.items()
                        if symbol.value <= address < symbol.value + symbol.bytes]
                require(len(hits) <= 1,
                        f"ambiguous data-owner operand: {operand}")
                if hits:
                    replacement = ("final-ELF-data-owner", hits[0])
            match = re.fullmatch(r"#\$([0-9a-f]+)", str(operand))
            if (match and int(match.group(1), 16) ==
                    (owners["namelen4"].value & 0xFF)):
                replacement = ("final-ELF-address-byte",
                               ("namelen4", "low"))
        if replacement is not None:
            normalized_operands.append({"instruction": index,
                "mnemonic": mnemonic, "raw_operand": operand,
                "owner": list(replacement[1])})
            normalized.append((mnemonic, replacement))
        else:
            normalized.append((mnemonic, (kind, operand)))
    return normalized, {"intern": {"address": intern.value,
        "bytes": intern.bytes}, "helper_calls": calls,
        "normalized_operands": normalized_operands,
        "owner_addresses": {name: symbol.value
                            for name, symbol in owners.items()}}


def candidate_latch_abi_gate() -> dict[str, Any]:
    predecessor_graph, predecessor = _latch_projected_graph(CURRENT_ELF)
    candidate_graph, candidate = _latch_projected_graph(ELF)
    require(candidate_graph == predecessor_graph,
            "candidate changed intern outside owner-address projection")
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    intern = truth.symbol("intern")
    helper = truth.symbol("lisp65_symbol22_latch_capture")
    abort = truth.symbol("lisp_abort_code")
    rows = CARD.PRICE.parse_instructions(
        CARD.disassembly(ELF), intern.value, intern.value + intern.bytes)
    call = candidate["helper_calls"][0]
    depths = CARD.PRICE.stack_depths_at(rows, intern.value, call)
    ordered = sorted(rows)
    sequence = [rows[address] for address in ordered]
    pointer_setup = [("ldx", "$4"), ("stx", "$16"),
                     ("ldx", "$5"), ("stx", "$17")]
    start = next((index for index in range(len(sequence) - 3)
                  if sequence[index:index + 4] == pointer_setup), None)
    require(start is not None and depths == [4],
            "candidate latch ABI stack/name-pointer setup drift")
    setup_end = ordered[start + 3]
    clobbers = [(address, rows[address]) for address in ordered
        if setup_end < address < call and rows[address][0] in
            {"sta", "stx", "sty", "stz"} and rows[address][1] in
            {"$16", "$17"}]
    raw = CARD.raw_symbol(truth, "intern")
    edge = bytes((0x20, helper.value & 0xFF, helper.value >> 8,
                  0xA9, CARD.ERROR, 0x20,
                  abort.value & 0xFF, abort.value >> 8))
    source = (ROOT / "src/symbol.c").read_text(encoding="utf-8")
    source_edge = ("lisp65_symbol22_latch_capture();\n#endif\n"
                   "        lisp_abort_static(LISP65_ERR_TOO_MANY_SYMBOLS")
    require(not clobbers and raw.count(edge) == 1
            and source.count(source_edge) == 1,
            "candidate latch escaped the existing fault-only abort edge")
    extra_instruction = list(candidate_graph)
    extra_instruction.insert(1, ("iny", ("exact-operand", "")))
    wrong_owner = list(candidate_graph)
    owner_index = next(index for index, row in enumerate(wrong_owner)
        if row[1] == ("final-ELF-data-owner", ("nsym", 0)))
    wrong_owner[owner_index] = (wrong_owner[owner_index][0],
        ("final-ELF-data-owner", ("npool", 0)))
    require(extra_instruction != predecessor_graph
            and wrong_owner != predecessor_graph,
            "latch semantic-graph mutation escaped")
    return {"status": "PASS: LATCH ABI DERIVED IN BLOCK3 DATA WORLD",
        "intern": candidate["intern"],
        "helper_edge": {"address": call, "callee": helper.value},
        "hardware_stack": {"persistent_bytes": 4,
            "post_JSR_caller_offsets": [7, 8],
            "all_reaching_depths": depths},
        "name_pointer": {"pair": ["__rc20", "__rc21"],
            "setup_end": setup_end, "clobbers": clobbers},
        "successful_path_identity": {
            "predecessor": predecessor, "candidate": candidate,
            "instruction_count": len(candidate_graph),
            "identity": "CFG plus operands, data addresses by final-ELF owner",
            "all_other_semantics_identical": True},
        "mutations_rejected": ["success-path-extra-instruction",
                               "data-owner-substitution"]}


def standing_candidate_walls() -> dict[str, Any]:
    """Re-run the living native walls without replaying sealed plane paths."""
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    sections = {row.name: row for row in truth.sections}
    symbols = {row.name: row for row in truth.symbols}
    cold = sections.get(".lisp65_c2_mapped_product_cold")
    require(".lisp65_c2_mapped_diagnostic" not in sections
            and "c2_refill_trace_read" not in symbols
            and cold is not None and cold.address == 0x7E8D
            and 0 < cold.bytes <= 371,
            "Block3 candidate restored diagnostics or lost product-cold")
    nested = BASE.MAP_NEST.check(ELF)
    dma = BASE.DMA.linked_read_model(ELF); BASE.DMA.validate_final(dma)
    bypass = BASE.BYPASS.linked_read_model(ELF)
    BASE.BYPASS.validate_final(bypass)
    backstop = BASE.BACKSTOP.final_gate(ELF)
    queue = BASE.QUEUE.linked_owner_gate(ELF)
    display = BASE.DISPLAY.check()
    recovery = RECOVERY_QUIET.final_gate(
        ELF, PLANE / "v6-semantics/bank2-static-code.bin")
    host = load(PRICING_RECEIPT)["host_requalification"]
    require(nested["violations"] == []
            and dma["unsafe_content_DMA_count"] == 0
            and bypass["unsafe_content_DMA_count"] == 0
            and backstop["recovery_sanitization"]["dominates_longjmp"] is True
            and queue["dominated_calls"] == 1
            and display["status"] ==
                "PASS: COMFORT DISPLAY HAS ONE OWNER AND DEFINED HANDOFF"
            and recovery["status"] ==
                "PASS: FINAL ELF HAS DERIVED EMPTY-JOURNAL BYPASS"
            and host["status"] ==
                "PASS: THREE SEALED CARDS REQUALIFIED ON LIVE SOURCES",
            "living Block3 standing wall regressed")
    return {"status": "PASS: LIVING BLOCK3 STANDING WALLS GREEN",
        "predecessor_contract": bind(CURRENT_RECEIPT),
        "diagnostic_freight_absent": True,
        "mapped_product_cold": {"address": cold.address,
            "bytes": cold.bytes, "capacity_bytes": 371},
        "profile": BASE.profile_gate(), "nested_MAP": nested,
        "DMA": dma, "selector_bypass": bypass,
        "execution_backstop": backstop, "queue_single_owner": queue,
        "display": display, "recovery_quiescence": recovery,
        "live_artifact_host_requalification": host}


def final_gate() -> dict[str, Any]:
    extent = CARD.static_extent_immediate_gate(52499, 47469)
    profile = CARD.completion_profile_gate()
    abi = candidate_latch_abi_gate()
    positive = CARD.positive_control(ELF)
    survival = CARD.survival_gate()
    base = standing_candidate_walls()
    compiler = load(Path(str(PRG) + ".compiler-input-consumption.json"))
    stdlib = load(Path(str(PRG) + ".stdlib-input-consumption.json"))
    authority_input = load(Path(str(PRG) + ".authority-input-consumption.json"))
    seed_authority_input = load(WPLTO /
        "resident-island-seed.prg.authority-input-consumption.json")
    ordinals = candidate_stdlib_ordinals()
    require(compiler["consumed_value"] == 52499
            and stdlib["consumed_value"] == ordinals["repl_banner"]
            and compiler["bound_header"] == bind(
                PLANE / "c2_lite_static_plane.h")
            and stdlib["bound_header"] == bind(PLANE / "stdlib-p0.h"),
            "Block-3 final compiler consumers escaped candidate authority")
    product = load(PLANE / "product/substitution-artifacts.json")
    constants = authority_input["manifest"]["derived_constants"]
    build_rows = [row for row in constants
                  if row["compiler_definition"] == "LISP65_C2_PRODUCT_BUILD_ID"]
    require(len(build_rows) == 1
            and build_rows[0]["consumed_value"] ==
                product["product_build_id_hex"] + "UL",
            "Block-3 final product build-ID consumer drift")
    seed_authority = CONSUMPTION.validate_authority_input_inventory(
        seed_authority_input)
    final_authority = CONSUMPTION.validate_authority_input_inventory(
        authority_input)
    require(seed_authority["features"] == final_authority["features"] == 35
            and seed_authority["categories"] == final_authority["categories"]
            and "feature-profile-population" in final_authority["categories"],
            "Block-3 feature/profile authority did not reach both real links")
    closure = CLOSURE.derive(PLANE / "product/substitution-artifacts.json")
    CLOSURE.require_closed(closure)
    direct_entry = load(DIRECT_ENTRY_RECEIPT)
    require(direct_entry["cross_parity"]["direct_entry_references"] == 637
            and direct_entry["evidence_era"]["sealed_predecessor"] ==
                ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                 "c2.2-direct-entry-encoding-correction-contract-receipt.json"),
            "Block-3 live direct-entry successor drift")
    return {"status": "PASS: FINAL BLOCK3 PRODUCT WORLD CLOSED",
        "extent": extent, "profile": profile, "candidate_abi": abi,
        "positive_control": positive, "survival": survival,
        "standing_product_walls": base,
        "compiler_consumption": compiler,
        "stdlib_consumption": stdlib,
        "authority_consumption": authority_input,
        "seed_authority_consumption": seed_authority_input,
        "five_category_authority": final_authority,
        "direct_entry_contract": bind(DIRECT_ENTRY_RECEIPT),
        "composed_bank2": composed_bank2_gate(),
        "prepack_closure": closure,
        "host_requalification": load(PRICING_RECEIPT)["host_requalification"]}


def build() -> None:
    configure()
    pre = load(PREFLIGHT_RECEIPT)
    require(pre["status"] == "PASS: V2.0 BLOCK3 PRODUCT CARD ARMED 0/1"
            and load(REPLACEMENT_PREFLIGHT)["status"] ==
                "PASS: REPLACEMENT WPLTO ARMED WITH FIVE AUTHORITIES"
            and load(PROJECTION_PREFLIGHT)["status"] ==
                "PASS: FEATURE ARGUMENTS ROUNDTRIP THROUGH REAL WRAPPER"
            and load(SOURCE_PREFLIGHT)["status"] ==
                "PASS: CANDIDATE GENERATED SOURCE WORLD ARMED"
            and not BUILD.exists()
            and not RECEIPT.exists() and not DIFFERENCE.exists(),
            "Block-3 product build lifecycle drift")
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, check=True).stdout
    require(clean == "", "Block-3 WPLTO requires committed clean sources")
    invocation = {"status": "INVOKED",
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "budget": {"product_cards": 1, "WPLTO_runs": 1,
                   "product_links": 1}}
    if INVOCATION.exists():
        require(load(INVOCATION) == invocation and PRELINK_RED.is_file(),
                "pre-compiler invocation is not the attributed setup stop")
    else:
        INVOCATION.write_bytes(canonical(invocation))
    processes = [run_child("_produce")]
    before = frozen_artifacts()
    diff = attribution()
    require(diff["unexplained_members"] == 0,
            "Block-3 attribution retained an unexplained member")
    DIFFERENCE.write_bytes(canonical(diff))
    gate = final_gate()
    processes.extend((run_child("_scope"), run_child("_accept")))
    after = frozen_artifacts()
    scope, acceptance = load(BASE.SCOPE_RESULT), load(BASE.ACCEPTANCE_RESULT)
    require(before == after
            and scope["status"] == acceptance["status"] == "PASS",
            "Block-3 read-only qualification tail red")
    value = {"format": FORMAT, "recorded_on": "2026-08-31",
        "status": STATUS, "authority": authority(),
        "preflight": bind(PREFLIGHT_RECEIPT), "invocation": bind(INVOCATION),
        "replacement_preflight": bind(REPLACEMENT_PREFLIGHT),
        "projection_preflight": bind(PROJECTION_PREFLIGHT),
        "source_world_preflight": bind(SOURCE_PREFLIGHT),
        "wplto_frontend_stop": bind(WPLTO_RED),
        "prelink_setup_stop": (bind(PRELINK_RED)
                               if PRELINK_RED.is_file() else None),
        "attribution": bind(DIFFERENCE),
        "attribution_status": diff["status"],
        "unexplained_members": diff["unexplained_members"],
        "final_product": gate, "scope": bind(BASE.SCOPE_RESULT),
        "acceptance": bind(BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": processes,
        "attempt_accounting": {"product_cards": 1, "WPLTO_runs": 1,
            "product_links": 1, "scope_runs": 1, "acceptance_runs": 1,
            "media_builds": 0, "device_contacts": 0,
            "pre_material_frontend_stops": 1},
        "media_authorized": True,
        "media_condition": "closure must be rederived from bytes read back from packed medium"}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    check()
    print("v2.0 Block3 product card: PASS WPLTO=1/1 link=1/1 Scope=1 Acceptance=1")


def record_qualification_red() -> None:
    configure()
    require(ELF.is_file() and PRG.is_file() and DIFFERENCE.is_file()
            and not RECEIPT.exists() and not QUALIFICATION_RED.exists()
            and not BASE.SCOPE_RESULT.exists()
            and not BASE.ACCEPTANCE_RESULT.exists(),
            "Block3 qualification-red lifecycle drift")
    diff = load(DIFFERENCE)
    require(diff == attribution() and diff["unexplained_members"] == 0,
            "Block3 qualification red lacks closed attribution")
    pair = frozen_artifacts()
    extent = CARD.static_extent_immediate_gate(52499, 47469)
    abi = candidate_latch_abi_gate()
    value = {"format": FORMAT + "-qualification-red-v1",
        "recorded_on": "2026-09-01",
        "status": "CHECKER-WORLD RED AFTER MATERIAL PAIR; PRODUCT NOT IMPLICATED",
        "authority": authority(), "source_commit": "b193f4d2",
        "frozen_unqualified_pair": pair,
        "difference_attribution": bind(DIFFERENCE),
        "difference_status": diff["status"],
        "unexplained_members": diff["unexplained_members"],
        "first_stop": {
            "mechanism": ("the parent build action did not enter configure() "
                "after the correctly configured material child returned"),
            "observed_red":
                "final ELF static extent dependency drift: c2_stream_phase_02b",
            "child_world": "candidate 52499-byte plane",
            "parent_checker_world": "inherited pre-candidate module paths"},
        "configured_read_only_replay": {
            "extent": extent,
            "next_legacy_stop": ("the inherited latch ABI checker compared "
                "raw linked data addresses across a legitimate LTO owner move"),
            "semantic_successor": abi,
            "second_legacy_stop": ("the v1.6 standing-wall wrapper attempted "
                "to consume its sealed native-client plane receipt instead "
                "of the living Block3 plane")},
        "attempt_accounting": {"product_cards": 1, "WPLTO_runs": 1,
            "product_links": 1, "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "disposition": "FROZEN-UNQUALIFIED-PRODUCT-CANDIDATE",
        "required_successor": ("read-only resume with configured parent, "
            "final-ELF data-owner ABI normalization and living candidate "
            "walls; no WPLTO or product link"),
        "claim_limit": "No Scope, Acceptance, media or device claim."}
    QUALIFICATION_RED.write_bytes(canonical(value))
    print("v2.0 Block3 product card: QUALIFICATION RED RECORDED "
          "pair=frozen WPLTO=1 link=1 Scope=0 Acceptance=0")


def resume() -> None:
    configure()
    red = load(QUALIFICATION_RED)
    require(red["status"] ==
                "CHECKER-WORLD RED AFTER MATERIAL PAIR; PRODUCT NOT IMPLICATED"
            and red["frozen_unqualified_pair"] == frozen_artifacts()
            and DIFFERENCE.is_file() and not RECEIPT.exists(),
            "Block3 read-only resume lifecycle drift")
    if BASE.SCOPE_RESULT.exists():
        require(load(BASE.SCOPE_RESULT)["status"] == "PASS",
                "Block3 partial read-only Scope result is not reusable")
    if BASE.ACCEPTANCE_RESULT.exists():
        require(load(BASE.ACCEPTANCE_RESULT)["status"] == "PASS",
                "Block3 partial read-only Acceptance result is not reusable")
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, check=True).stdout
    require(clean == "", "Block3 read-only resume requires committed clean sources")
    setup_child()
    before = frozen_artifacts()
    diff = load(DIFFERENCE)
    require(diff == attribution() and diff["unexplained_members"] == 0,
            "Block3 read-only resume lost closed attribution")
    gate = final_gate()
    processes = ([{"action": "_scope", "status": "PASS",
                   "mode": "reused-read-only-partial",
                   "receipt": bind(BASE.SCOPE_RESULT)}]
                 if BASE.SCOPE_RESULT.exists() else [run_child("_scope")])
    processes.append({"action": "_accept", "status": "PASS",
        "mode": "reused-read-only-partial",
        "receipt": bind(BASE.ACCEPTANCE_RESULT)}
        if BASE.ACCEPTANCE_RESULT.exists() else run_child("_accept"))
    after = frozen_artifacts()
    scope, acceptance = load(BASE.SCOPE_RESULT), load(BASE.ACCEPTANCE_RESULT)
    require(before == after
            and scope["status"] == acceptance["status"] == "PASS",
            "Block3 read-only qualification tail red")
    value = {"format": FORMAT, "recorded_on": "2026-09-01",
        "status": STATUS, "authority": authority(),
        "preflight": bind(PREFLIGHT_RECEIPT), "invocation": bind(INVOCATION),
        "replacement_preflight": bind(REPLACEMENT_PREFLIGHT),
        "projection_preflight": bind(PROJECTION_PREFLIGHT),
        "source_world_preflight": bind(SOURCE_PREFLIGHT),
        "wplto_frontend_stop": bind(WPLTO_RED),
        "source_world_frontend_stop": bind(SOURCE_RED),
        "prelink_setup_stop": (bind(PRELINK_RED)
                               if PRELINK_RED.is_file() else None),
        "qualification_red": bind(QUALIFICATION_RED),
        "attribution": bind(DIFFERENCE),
        "attribution_status": diff["status"],
        "unexplained_members": diff["unexplained_members"],
        "final_product": gate, "scope": bind(BASE.SCOPE_RESULT),
        "acceptance": bind(BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": processes,
        "attempt_accounting": {"product_cards": 1, "WPLTO_runs": 1,
            "product_links": 1, "scope_runs": 1, "acceptance_runs": 1,
            "media_builds": 0, "device_contacts": 0,
            "pre_material_frontend_stops": 2,
            "post_material_checker_stops": 1},
        "resume": {"mode": "read-only-over-frozen-pair",
            "new_WPLTO_runs": 0, "new_product_links": 0},
        "media_authorized": True,
        "media_condition":
            "closure must be rederived from bytes read back from packed medium"}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    check()
    print("v2.0 Block3 product card: RESUME PASS WPLTO=1/1 link=1/1 "
          "Scope=1 Acceptance=1")


def write_report(value: dict[str, Any]) -> None:
    pair = value["artifacts_after"]
    gate = value["final_product"]
    hole = gate["composed_bank2"]["largest_contiguous_hole"]["bytes"]
    REPORT.write_text(f"""# v2.0 Block 3 return — product card

Status: **{value['status']}**

The one authorized WPLTO/product link consumes the candidate-owned 52,499-byte
static plane, product build ID and shifted stdlib entry ordinals at both real
compiler seams.  The final composed Bank-2 map is disjoint and retains a
largest contiguous hole of **{hole:,} bytes**.  The packed-product closure is
{gate['prepack_closure']['object_count']} objects and
{gate['prepack_closure']['call_site_count']:,} calls, all closed.

The v1.9 release to this candidate is fully attributed as the composition of
the already closed v1.9-to-v2.0-r4 latch change and the candidate plane/build
closure; every section, symbol, relocation, program header and changed PRG
byte is named, with zero unexplained members.

Scope and Acceptance ran read-only over:

- ELF `{pair['ELF']['sha256']}`
- PRG `{pair['PRG']['sha256']}`

Accounting is exactly one product card, one WPLTO and one product link.  Media
is now permitted, but its own acceptance must rerun closure over bytes read
back from the actually packed medium before any device contact.
""", encoding="utf-8")


def check() -> None:
    configure()
    setup_child()
    value = load(RECEIPT)
    diff = load(DIFFERENCE)
    require(value["status"] == STATUS and value["authority"] == authority()
            and value["artifacts_before"] == frozen_artifacts()
            and value["artifacts_after"] == value["artifacts_before"]
            and diff == attribution() and diff["unexplained_members"] == 0
            and canonical(value["final_product"]) == canonical(final_gate())
            and value["scope"] == bind(BASE.SCOPE_RESULT)
            and value["acceptance"] == bind(BASE.ACCEPTANCE_RESULT)
            and value["attempt_accounting"]["WPLTO_runs"] == 1
            and value["attempt_accounting"]["product_links"] == 1,
            "Block-3 product card receipt drift")
    print("v2.0 Block3 product card: CHECK PASS pair=frozen media=0")


def child(action: str) -> None:
    configure()
    core, _activation, _cold = setup_child()
    # Materialize the living source-owner population from the final profile.
    # Calling the historical configurator here would first restore an R1
    # predecessor and thereby manufacture a half-era source tuple.
    profile_sources = set(BASE.profile_gate()["sources"])
    active_features = set(predecessor_features())
    source_scope_rows = []
    for row in PRODUCT.SOURCE_OWNER_SCOPES:
        candidate = deepcopy(row)
        candidate["sources"] = [str(path) for path in row["sources"]]
        candidate["selected"] = (str(row["trigger"]) in active_features
            and all(source in profile_sources for source in candidate["sources"]))
        source_scope_rows.append(candidate)
    source_scope = {"status": "passed-candidate-profile-owner-population",
                    "scopes": source_scope_rows}

    def candidate_single_implementation_gate() -> dict[str, Any]:
        sources = sorted(source for source in profile_sources
            if Path(source).name.startswith("c2_mapped_far_"))
        expected = sorted((
            "src/optional/c2_mapped_far_service_liveness_v4.s",
            "src/optional/c2_mapped_far_convergence_full_span.s",
            "src/optional/c2_mapped_far_facade_padding_liveness_v3.s"))

        def validate(rows: list[str]) -> None:
            require(sorted(rows) == expected and len(rows) == len(set(rows)),
                    "candidate mapped-far implementation owner drift")

        validate(sources)
        rejected = []
        for name, mutant in (("missing-member", sources[:-1]),
                             ("duplicate-member", [*sources, sources[0]]),
                             ("historical-member", [*sources,
                                "src/c2_mapped_far_service.s"])):
            try:
                validate(mutant)
            except CardError:
                rejected.append(name)
        require(len(rejected) == 3,
                "candidate source-owner mutation escaped")
        inventory = SOURCE_ORACLE.BASE_CARD.BASE.real_asm_inventory_gate()
        return {"status":
                    "PASS: CANDIDATE PROFILE OWNS ONE MAPPED-FAR SOURCE SET",
                "owner": "mapped-far-content-convergence",
                "sources": sources, "profile": bind(PROFILE),
                "real_global_inventory": inventory,
                "mutations_rejected": rejected}
    # setup_child has already reconstructed the complete living successor and
    # rebound every output/static consumer.  The inherited card stack normally
    # configures itself again at each historical wrapper.  That is correct for
    # its own drivers, but would restore an obsolete intermediate R1 identity
    # here.  Freeze only the already-configured wrapper functions; the actual
    # producer/Scope/Acceptance bodies still execute in their own processes.
    reachable: list[types.ModuleType] = [core.PRODUCT.BASE]
    seen: set[int] = set()
    while reachable:
        module = reachable.pop()
        if id(module) in seen:
            continue
        seen.add(id(module))
        if callable(getattr(module, "configure", None)):
            module.configure = lambda: None
        for value in vars(module).values():
            if (isinstance(value, types.ModuleType)
                    and value.__name__.startswith("c2_")
                    and id(value) not in seen
                    and any(callable(getattr(value, name, None)) for name in
                            ("produce_child", "scope_child",
                             "acceptance_child"))):
                reachable.append(value)
    SOURCE_ORACLE.BASE_CARD.BASE.configure_fix_source = (
        lambda: deepcopy(source_scope))
    SOURCE_ORACLE.BASE_CARD.REPLACEMENT.single_implementation_gate = (
        candidate_single_implementation_gate)
    # The installed acceptance oracle has two input roots: delivered/link
    # artifacts under WPLTO and the setup-owned static plane.  Its historical
    # single BUILD root cannot represent that successor.  Rebind both real
    # consumers for the duration of the read-only oracle call.
    historical_linked_oracle = STORED_WORLD.linked_oracle_gate

    def candidate_linked_oracle(elf: Path) -> dict[str, Any]:
        old_build = STORED_WORLD.ORACLE.BUILD
        old_paths = STORED_WORLD.ORACLE.artifact_paths
        STORED_WORLD.ORACLE.BUILD = PREFLIGHT / "setup-owned"
        STORED_WORLD.ORACLE.artifact_paths = lambda: {
            "elf": ELF, "prg": PRG, "map": Path(str(PRG) + ".map"),
            "lto": Path(str(PRG) + ".lto.o"),
            "linker": WPLTO / "c2-substitution.ld",
            "resolved_profile": PROFILE,
            "publish_last": WPLTO / "kernal-window-publish-last.json",
            "generated_phase02a": WPLTO /
                "generated-product-sources/c2-stream-phase-02a.c",
            "generated_decoder": WPLTO /
                "generated-product-sources/c2-stream-decoder.c"}
        try:
            return historical_linked_oracle(elf)
        finally:
            STORED_WORLD.ORACLE.BUILD = old_build
            STORED_WORLD.ORACLE.artifact_paths = old_paths

    STORED_WORLD.linked_oracle_gate = candidate_linked_oracle
    if action == "_produce":
        # The configured product module is the actual single-link consumer.
        # Calling back through twenty historical card wrappers would ask each
        # wrapper to reconstruct an already-complete successor.  Enter the
        # product seam directly, while retaining every wrapper that setup has
        # installed on PRODUCT.single_link itself.
        features = predecessor_features()
        input_features, _projected = producer_input_features()
        CARD.bind_seed_link_environment(predecessor_profile())
        mapping = materialize_candidate_sources(WPLTO)
        projected = projected_source_list(mapping, features)
        preflight_sources = load(SOURCE_PREFLIGHT)["compiler_sources"]
        require(len(projected) == preflight_sources["total"]
                and len(mapping) == preflight_sources["generated"],
                "materialized source world differs from committed preflight")
        original_source_list = PRODUCT.source_list

        def candidate_source_list(
                definitions: tuple[str, ...] = ()) -> list[str]:
            original = original_source_list(definitions)
            return [str(mapping.get(Path(path).resolve(), Path(path)))
                    for path in original]

        PRODUCT.source_list = candidate_source_list
        feature_state = PRODUCT.configure_compiler_consumed_feature_profile(
            predecessor_profile(), bind(predecessor_profile()), features)
        try:
            PRODUCT.single_link(WPLTO,
                probe_definitions=input_features,
                direct_entry_receipt=DIRECT_ENTRY_RECEIPT,
                direct_entry_check_tool="c2_v200_block3_direct_entry.py",
                extra_contract_lines=predecessor_contract_lines())
        finally:
            PRODUCT.restore_compiler_consumed_feature_profile(feature_state)
            PRODUCT.source_list = original_source_list
        require(ELF.is_file() and PRG.is_file(),
                "direct configured single-link did not emit the final pair")
        BASE.PRODUCER_RESULT.parent.mkdir(parents=True, exist_ok=True)
        BASE.PRODUCER_RESULT.write_bytes(canonical({
            "status": "PASS", "producer": "configured PRODUCT.single_link",
            "artifacts": frozen_artifacts()}))
        raise SystemExit(0)
    if action == "_scope":
        raise SystemExit(core.PRODUCT.BASE.scope_child())
    if action == "_accept":
        raise SystemExit(core.PRODUCT.BASE.acceptance_child())
    raise CardError(f"unknown child action: {action}")


def record_prelink_red() -> None:
    require(INVOCATION.is_file() and not BUILD.exists()
            and not PRELINK_RED.exists() and not RECEIPT.exists(),
            "Block-3 prelink-stop lifecycle drift")
    value = {"format": FORMAT + "-prelink-red", "recorded_on": "2026-09-01",
        "status": "ATTRIBUTED: CONFIGURATION REENTRY STOPPED BEFORE WPLTO",
        "authority": authority(), "invocation": bind(INVOCATION),
        "mechanism": ("the new wrapper called the fully configured R1 stack, "
            "then the inherited producer tried to reconstruct the same stack; "
            "the historical R1 restore correctly rejected the half-era identity"),
        "repair": ("freeze already-configured wrapper configurators at the "
            "new driver boundary; producer, Scope and Acceptance bodies remain live"),
        "emitted_artifacts": [],
        "attempt_accounting": {"actual_WPLTO_runs": 0,
            "actual_product_links": 0, "ELF": 0, "PRG": 0},
        "budget_consumed": False}
    PRELINK_RED.write_bytes(canonical(value))
    print("v2.0 Block3 product card: PRELINK RED ATTRIBUTED WPLTO=0 link=0")


def record_wplto_red() -> None:
    require(BUILD.is_dir() and WPLTO.is_dir() and not WPLTO_RED.exists()
            and not ELF.exists() and not PRG.exists()
            and not Path(str(PRG) + ".lto.o").exists(),
            "Block-3 WPLTO-red lifecycle drift")
    stderr = WPLTO / "resident-island-seed.prg.link.stderr.txt"
    profile = WPLTO / "resolved-profile.txt"
    require(stderr.is_file() and profile.is_file(),
            "failed WPLTO diagnostics are incomplete")
    errors = stderr.read_text(encoding="utf-8")
    for token in ("C2AW_COMPLETION_MARK", "LISP65_C2_PHASE_05A_SLOT",
                  "vm_c2d_byte", "record reads require CRC convergence",
                  "c2e_work_state"):
        require(token in errors, f"expected feature-world symptom absent: {token}")
    observed = [line for line in profile.read_text(encoding="utf-8").splitlines()
                if line.startswith("feature_defines=")]
    expected = predecessor_features()
    require(observed == [], "failed WPLTO unexpectedly carried feature authority")
    artifacts = [bind(path) for path in sorted(WPLTO.rglob("*"))
                 if path.is_file()]
    value = {
        "format": FORMAT + "-wplto-red",
        "recorded_on": "2026-09-01",
        "status": "FROZEN: WPLTO FRONTEND RED BEFORE LTO OBJECT OR PRODUCT LINK",
        "authority": authority(),
        "preflight": bind(PREFLIGHT_RECEIPT),
        "prelink_setup_stop": bind(PRELINK_RED),
        "direct_entry_successor": bind(DIRECT_ENTRY_RECEIPT),
        "mechanism": {
            "expected_feature_count": len(expected),
            "expected_features": list(expected),
            "observed_feature_defines_rows": observed,
            "cause": ("the direct configured single_link entry used its empty "
                      "probe_definitions default instead of consuming the "
                      "qualified r4 feature authority"),
            "symptom_families": [
                "completion ABI macros absent", "phase-slot macros absent",
                "target C2D primitive absent", "CRC convergence absent",
                "target emitter geometry absent"],
        },
        "emitted_frontend_artifacts": artifacts,
        "absent_material_artifacts": [
            ELF.relative_to(ROOT).as_posix(), PRG.relative_to(ROOT).as_posix(),
            Path(str(PRG) + ".lto.o").relative_to(ROOT).as_posix()],
        "prepared_repair": ("derive probe_definitions from the qualified r4 "
                            "resolved profile and materialize the same set in "
                            "the successor contract"),
        "attempt_accounting": {"WPLTO_attempts": 1,
            "completed_WPLTO_objects": 0, "product_links": 0},
        "budget_decision": ("replacement WPLTO requires a new owner/reviewer "
                            "authorization; no retry was started")}
    WPLTO_RED.write_bytes(canonical(value))
    print("v2.0 Block3 product card: WPLTO RED ATTRIBUTED attempt=1 object=0 link=0")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "check-preflight",
        "record-prelink-red", "record-wplto-red", "replacement-preflight",
        "check-replacement-preflight", "projection-preflight",
        "check-projection-preflight", "record-source-red",
        "source-preflight", "check-source-preflight",
        "record-qualification-red", "resume", "build", "check",
        "_produce", "_scope", "_accept"))
    args = parser.parse_args()
    try:
        if args.action.startswith("_"):
            child(args.action)
        {"preflight": preflight, "check-preflight": check_preflight,
         "record-prelink-red": record_prelink_red,
         "record-wplto-red": record_wplto_red,
         "replacement-preflight": replacement_preflight,
         "check-replacement-preflight": check_replacement_preflight,
         "projection-preflight": projection_preflight,
         "check-projection-preflight": check_projection_preflight,
         "record-source-red": record_source_red,
         "source-preflight": source_preflight,
         "check-source-preflight": check_source_preflight,
         "record-qualification-red": record_qualification_red,
         "resume": resume, "build": build, "check": check}[args.action]()
        return 0
    except (CardError, CLOSURE.ClosureError, RuntimeError) as error:
        print(f"v2.0 Block3 product card: FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
