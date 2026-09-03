#!/usr/bin/env python3
"""Materialize, link and qualify v2.0 domain discipline Tier 1."""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_v17_ide_idle_blink_product_card as PLANE_TOOLS  # noqa: E402
import c2_v18_capture_hybrid_native_client_card as CLIENT_CARD  # noqa: E402
import c2_v200_domain_tier1_pricing as PRICE  # noqa: E402
import c2_v200_symbol22_first_fault_product_card as LATCH  # noqa: E402
import consolidated_consumption_authority as CONSUMPTION  # noqa: E402
import public_surface_domain_audit as AUDIT  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
AUTHORIZATION = "5a4653ae"
PLAN_HEADER = (
    "## Reviewer disposition — B3-1 attribution and Tier-1 authorization — 2026-09-01")
SUCCESSOR_AUTHORIZATION = "7ab194bb"
SUCCESSOR_PLAN_HEADER = (
    "## Reviewer disposition — Tier-1 output-root resume — 2026-09-01")
LIFECYCLE_AUTHORIZATION = "5f723985"
LIFECYCLE_PLAN_HEADER = (
    "## Reviewer disposition — Tier-1 lifecycle projection resume — 2026-09-01")
BUILD = ROOT / "build/c2.3/v2.0-domain-tier1-product-card-r1"
PINNED_COMPLETION = BUILD / "completion"
COMPLETION = PINNED_COMPLETION
PREFLIGHT = ROOT / "build/c2.3/v2.0-domain-tier1-product-card-r1-preflight"
PLANE = PREFLIGHT / "setup-owned/static-plane/narrow-static"
PLANE_RECEIPT = PREFLIGHT / "v200-domain-tier1-static-plane.json"
SUITE = PREFLIGHT / "v200-domain-tier1-stdlib-suite.json"
ELF = COMPLETION / "lisp65-c2-substitution-linked.prg.elf"
PRG = COMPLETION / "lisp65-c2-substitution-linked.prg"
PROFILE = COMPLETION / "resolved-profile.txt"
INVOCATION = PREFLIGHT / "candidate-invocation.json"
PREFLIGHT_RECEIPT = ARCH / (
    "c2.3-v2.0-domain-tier1-product-card-r1-preflight.json")
PRELINK_RED = ARCH / (
    "c2.3-v2.0-domain-tier1-product-card-r1-prelink-red.json")
PRELINK_RED_REPORT = ROOT / (
    "docs/planning/v2.0.0-domain-tier1-product-card-prelink-red.md")
PRELINK_RED_2 = ARCH / (
    "c2.3-v2.0-domain-tier1-product-card-r1-prelink-red-2.json")
PRELINK_RED_2_REPORT = ROOT / (
    "docs/planning/v2.0.0-domain-tier1-product-card-prelink-red-2.md")
POSTLINK_RED = ARCH / (
    "c2.3-v2.0-domain-tier1-product-card-r1-postlink-red.json")
POSTLINK_RED_REPORT = ROOT / (
    "docs/planning/v2.0.0-domain-tier1-product-card-postlink-red.md")
OUTPUT_ROOT_CONVERSION = ARCH / (
    "c2.3-v2.0-domain-tier1-output-root-population-conversion.json")
OUTPUT_ROOT_CONVERSION_REPORT = ROOT / (
    "docs/planning/v2.0.0-domain-tier1-output-root-population-conversion.md")
RESUME_RED = ARCH / (
    "c2.3-v2.0-domain-tier1-product-card-r1-resume-red.json")
RESUME_RED_REPORT = ROOT / (
    "docs/planning/v2.0.0-domain-tier1-product-card-resume-red.md")
LIFECYCLE_VIEW = ARCH / (
    "c2.3-v2.0-domain-tier1-client-lifecycle-qualification-view.json")
LIFECYCLE_VIEW_REPORT = ROOT / (
    "docs/planning/v2.0.0-domain-tier1-client-lifecycle-projection.md")
CHECKER_CONVERSIONS = ARCH / (
    "c2.3-v2.0-domain-tier1-inherited-final-gate-conversions.json")
CHECKER_CONVERSIONS_REPORT = ROOT / (
    "docs/planning/v2.0.0-domain-tier1-inherited-final-gate-conversions.md")
ACCEPTANCE_FREIGHT_CONVERSION = ARCH / (
    "c2.3-v2.0-domain-tier1-acceptance-freight-conversion.json")
ACCEPTANCE_FREIGHT_CONVERSION_REPORT = ROOT / (
    "docs/planning/v2.0.0-domain-tier1-acceptance-freight-conversion.md")
MEASURED_CONTRACT = ARCH / (
    "c2.3-v2.0-domain-tier1-measured-contract-r1.json")
DURABLE_CONTRACT = ROOT / "config/public-surface-domain-contract.json"
CONTRACT_AUTHORITY_RECEIPT = ARCH / (
    "c2.3-v2.0-domain-tier1-contract-authority-closure.json")
CONTRACT_AUTHORITY_REPORT = ROOT / (
    "docs/planning/v2.0.0-domain-tier1-contract-authority-closure.md")
CONTRACT_AUTHORITY_EVIDENCE_ERA = "b1c3890d"
NATIVE_DIFFERENCE = ARCH / (
    "c2.3-v2.0-domain-tier1-v190-native-difference-r1.json")
PLANE_DIFFERENCE = ARCH / (
    "c2.3-v2.0-domain-tier1-v190-plane-difference-r1.json")
RECEIPT = ARCH / "c2.3-v2.0-domain-tier1-product-card-r1-receipt.json"
REPORT = ROOT / "docs/planning/v2.0.0-domain-tier1-product-card-report.md"
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
BASE_PLANE = LATCH.RELEASE_PLANE_ROOT
BASE_MANIFEST = LATCH.RELEASE_MANIFEST
BASE_BLOB = BASE_MANIFEST.with_name("stdlib-p0.blob.bin")
BASE_CODE = LATCH.RELEASE_CODE
BASE_PRODUCT = BASE_PLANE / "product/substitution-artifacts.json"
BASE_ELF = LATCH.RELEASE_ELF
BASE_PRG = LATCH.RELEASE_PRG
BASE_PROFILE = LATCH.RELEASE_PROFILE
CLIENT_SOURCE = LATCH.RELEASE_CLIENT_SOURCE
CANONICAL_CLIENT_SOURCE = (
    ROOT / "config/c2-v190-public-plane/sources/22-stdlib-read-line.lisp")
FORMAT = "lisp65-c2-v200-domain-tier1-product-card-v1"
STATUS = "PASS: V2.0 DOMAIN TIER 1 FINAL PRODUCT GREEN"
EXTENT = 47795
BASE_EXTENT = 47469

LATCH_CONFIGURATION_GATE = LATCH.configuration_gate
LATCH_FINAL_GATE = LATCH.final_gate


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


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str], label: str) -> str:
    result = subprocess.run(command, cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout


def authority() -> dict[str, Any]:
    section = LATCH.git_section(AUTHORIZATION, PLAN, PLAN_HEADER)
    folded = " ".join(subprocess.run(
        ["git", "show", f"{AUTHORIZATION}:{PLAN.relative_to(ROOT).as_posix()}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout.decode().lower()
        .replace("`", "").split())
    for token in ("one wplto and one product link", "172 → 110",
                  "classification, result, error", "largest object reaches 253"):
        require(token in folded, f"Tier-1 product authority absent: {token}")
    return {"review_authorization": section, "pricing": bind(PRICE.RECEIPT),
        "right": "one Tier-1 product card, one WPLTO and one product link",
        "budget": {"product_cards": 1, "WPLTO_runs": 1,
                   "product_links": 1, "media_builds": 0,
                   "device_contacts": 0}}


def successor_authority() -> dict[str, Any]:
    section = LATCH.git_section(
        SUCCESSOR_AUTHORIZATION, PLAN, SUCCESSOR_PLAN_HEADER)
    folded = " ".join(subprocess.run(
        ["git", "show", f"{SUCCESSOR_AUTHORIZATION}:"
         f"{PLAN.relative_to(ROOT).as_posix()}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout.decode().lower().replace("`", "").split())
    for token in ("resume read-only", "no new wplto",
                  "compiler, linker, producer, media builder and qualifier",
                  "110 remainder is measured"):
        require(token in folded, f"Tier-1 resume authority absent: {token}")
    return {"review_authorization": section, "postlink_red": bind(POSTLINK_RED),
        "right": "output-root conversion plus read-only frozen-pair resume",
        "new_WPLTOs": 0, "new_product_links": 0}


def lifecycle_successor_authority() -> dict[str, Any]:
    section = LATCH.git_section(
        LIFECYCLE_AUTHORIZATION, PLAN, LIFECYCLE_PLAN_HEADER)
    folded = " ".join(subprocess.run(
        ["git", "show", f"{LIFECYCLE_AUTHORIZATION}:"
         f"{PLAN.relative_to(ROOT).as_posix()}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout.decode().lower().replace("`", "").split())
    for token in ("bound candidate client source", "missing",
                  "divergent lifecycle", "fails closed", "110 silently-wrong"):
        require(token in folded, f"Tier-1 lifecycle authority absent: {token}")
    return {"review_authorization": section, "resume_red": bind(RESUME_RED),
        "right": "derived lifecycle qualification view plus read-only resume",
        "new_WPLTOs": 0, "new_product_links": 0}


def phase_owned_output_root() -> Path:
    """Derive the live product root from producer evidence when available."""
    producer = BUILD / "producer-result.json"
    if producer.is_file():
        value = load(producer)
        path = ROOT / value["artifacts"]["prg"]["path"]
        require(path.name == "lisp65-c2-substitution-linked.prg",
                "producer result names an unexpected Tier-1 product")
        return path.parent
    # Before producer execution, the inherited phase contract owns its target
    # under BUILD/wplto.  No qualifier may invent a sibling completion root.
    return BUILD / "wplto"


def bind_phase_owned_output_root() -> Path:
    global COMPLETION, ELF, PRG, PROFILE
    root = phase_owned_output_root()
    COMPLETION = root
    PRG = root / "lisp65-c2-substitution-linked.prg"
    ELF = Path(str(PRG) + ".elf")
    PROFILE = root / "resolved-profile.txt"
    return root


def bind_client_lifecycle_view() -> None:
    if LIFECYCLE_VIEW.is_file():
        CLIENT_CARD.PLANE_RECEIPT = LIFECYCLE_VIEW


def tier1_qualification_setup() -> Any:
    result = LATCH.completion_qualification_setup()
    bind_client_lifecycle_view()
    return result


def tier1_symbol22_freight_proof(name: str, row: dict[str, Any],
        layout: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    """Prove the active latch registry against the living Tier-1 world."""
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    owners = LATCH.composed_gap_ownership(ELF, PROFILE)
    by_name = {item["name"]: item for item in layout["allocatable_sections"]}
    hot = by_name[".lisp65_c2_fixed_bank0_hot_bss"]
    heap = truth.symbol("__heap_start").value

    def relation(candidate: dict[str, Any]) -> str:
        if name == LATCH.SECTION:
            require(candidate["vma"] ==
                        owners["terminal_return_guard"]["end_exclusive"]
                    and candidate["bytes"] == 48,
                    "symbol22 code escaped the derived raw-owner end")
            return "code-start-equals-derived-raw-owner-end"
        require(name == LATCH.STATE_SECTION
                and candidate["vma"] == hot["vma"] + hot["bytes"]
                and candidate["lma"] == candidate["vma"]
                and candidate["bytes"] == 5
                and candidate["vma"] + candidate["bytes"] <= heap,
                "symbol22 state escaped the derived pre-heap gap")
        return "state-start-equals-hot-bss-end-before-heap"

    derived = relation(row)
    shifted = dict(row)
    shifted["vma"] += 1
    try:
        relation(shifted)
    except CardError:
        pass
    else:
        raise CardError("shifted symbol22 freight placement mutation survived")
    require(registry["registration"]["source"] ==
                "src/optional/c2_symbol22_first_fault_latch.s",
            "symbol22 freight prover bound another registry")
    return {"gate": "composed-raw-owner/preheap-gap",
        "relation": derived, "status": "passed"}


def inventory() -> tuple[tuple[str, str, Path], ...]:
    product = load(BASE_PRODUCT)
    rows = product["manifests"]
    require(len(rows) == 6, "Tier-1 predecessor manifest population drift")
    return (("stdlib-p0", "stdlib", PLANE / "stdlib-p0.manifest.json"),
            *tuple((key, role, ROOT / row["path"])
                   for key, role, row in zip(
                       ("ide", "idex", "m65d", "buffer", "lcc"),
                       ("ide", "idex", "m65d", "buffer", "lcc"), rows[1:])))


def derived_header(code_bytes: int) -> Path:
    source = (ROOT / "src/c2_lite_static_plane.h").read_text(encoding="utf-8")
    source, count = re.subn(
        r"(#define LISP65_C2_LITE_STATIC_CODE_BYTES )\d+(UL)",
        rf"\g<1>{code_bytes}\2", source)
    require(count == 1, "Tier-1 static extent macro absent")
    path = PLANE / "c2_lite_static_plane.h"
    path.write_text(source, encoding="utf-8")
    return path


def derived_contract(code_bytes: int) -> Path:
    contract = load(ROOT / "config/c2-lite-execution-contract.json")
    code = contract["physical_planes"]["code"]
    code["static_use_bytes"] = code_bytes
    code["gross_headroom_bytes"] = 65536 - code_bytes
    path = PLANE / "c2-lite-execution-contract.json"
    path.write_bytes(canonical(contract))
    return path


def derived_profile(product: dict[str, Any], semantics: dict[str, Any]) -> Path:
    profile = load(ROOT / "config/c2-l-full-product-profile.json")
    authority_row = dict(profile["authority"])
    authority_row.update({
        "product_manifest": (PLANE / "product/substitution-artifacts.json")
            .relative_to(ROOT).as_posix(),
        "bank2_static_plane": (PLANE / "v6-semantics/bank2-static-code.bin")
            .relative_to(ROOT).as_posix(),
        "compiled_ide_manifest": inventory()[1][2].relative_to(ROOT).as_posix(),
        "compiled_stdlib_manifest": inventory()[0][2].relative_to(ROOT).as_posix(),
        "successor": {"kind": "v2.0-domain-tier1-in-place-successor",
            "source": PRICE.SUCCESSOR_SOURCE.relative_to(ROOT).as_posix(),
            "rule": "one executed six-role plane owns the link"},
    })
    static = semantics["static_bank2"]
    profile.update({"recorded_on": "2026-09-01", "authority": authority_row,
        "product_build_id": product["product_build_id_hex"],
        "images": product["images"], "entries": product["entries"],
        "resolutions": product["resolutions"], "roots": product["roots"],
        "direct_entry_refs": PLANE_TOOLS.L94.direct_entry_census(
            PLANE / "product"),
        "bank2_static_code": {"bytes": static["code_bytes"],
            "sha256": static["code_sha256"],
            "headroom_bytes": static["headroom_bytes"]}})
    path = PLANE / "candidate-profile.json"
    path.write_bytes(canonical(profile))
    return path


def materialize_plane() -> dict[str, Any]:
    require(not PREFLIGHT.exists() and not PREFLIGHT_RECEIPT.exists(),
            "Tier-1 product preflight is one-shot")
    shutil.copytree(BASE_PLANE, PLANE)
    shutil.rmtree(PLANE / "product")
    shutil.rmtree(PLANE / "v6-semantics")
    for path in PLANE.glob("stdlib-p0.*"):
        path.unlink()
    suite = deepcopy(load(PRICE.BASE_SUITE))
    suite["name"] = "v2.0-domain-tier1-product"
    suite["sources"].append(PRICE.SUCCESSOR_SOURCE.relative_to(ROOT).as_posix())
    suite["cases"] = suite["cases"][:4]
    SUITE.write_bytes(canonical(suite))
    run([sys.executable, "tools/host-lisp/bytecode_p0_stdlib.py", "--check",
         "--emit-artifacts", (PLANE / "stdlib-p0").relative_to(ROOT).as_posix(),
         SUITE.relative_to(ROOT).as_posix()], "Tier-1 stdlib emission")
    specs = inventory()
    old_sub = (PLANE_TOOLS.SUB.BUILD, PLANE_TOOLS.SUB.SPECS)
    old_v6 = (PLANE_TOOLS.V6.OUT, PLANE_TOOLS.V6.PRODUCT_IDENTITY,
              PLANE_TOOLS.V6.STATIC_CODE_BYTES, PLANE_TOOLS.V6.A.SPECS)
    try:
        PLANE_TOOLS.SUB.BUILD = PLANE / "product"
        PLANE_TOOLS.SUB.SPECS = specs
        product = PLANE_TOOLS.SUB.build()
        total = sum(int(load(path)["code_bytes"]) for _key, _role, path in specs)
        PLANE_TOOLS.V6.OUT = PLANE / "v6-semantics"
        PLANE_TOOLS.V6.PRODUCT_IDENTITY = (
            PLANE / "product/substitution-artifacts.json")
        PLANE_TOOLS.V6.STATIC_CODE_BYTES = total
        PLANE_TOOLS.V6.A.SPECS = specs
        PLANE_TOOLS.V6.OUT.mkdir(parents=True)
        semantics = PLANE_TOOLS.V6.host_semantics()
    finally:
        (PLANE_TOOLS.SUB.BUILD, PLANE_TOOLS.SUB.SPECS) = old_sub
        (PLANE_TOOLS.V6.OUT, PLANE_TOOLS.V6.PRODUCT_IDENTITY,
         PLANE_TOOLS.V6.STATIC_CODE_BYTES, PLANE_TOOLS.V6.A.SPECS) = old_v6
    static = semantics["static_bank2"]
    require(total == EXTENT == static["code_bytes"]
            and (PLANE / "v6-semantics/bank2-static-code.bin").stat().st_size == EXTENT,
            "Tier-1 materialized plane extent drift")
    profile = derived_profile(product, semantics)
    header = derived_header(total)
    contract = derived_contract(total)
    workbench = PLANE / "workbench"
    workbench.mkdir(exist_ok=True)
    shutil.copyfile(PLANE / "stdlib-p0.h", workbench / "stdlib-p0.h")
    measured = measured_contract()
    MEASURED_CONTRACT.write_bytes(canonical(measured))
    signatures = signature_gate()
    ceiling = object_ceiling()
    value = {"format": FORMAT + "-plane", "recorded_on": "2026-09-01",
        "status": "PASS: TIER-1 47795-BYTE PLANE MATERIALIZED 0/1",
        "authority": authority(), "suite": bind(SUITE),
        "source": bind(PRICE.SUCCESSOR_SOURCE),
        "manifests": [bind(path) for _key, _role, path in specs],
        "product": bind(PLANE / "product/substitution-artifacts.json"),
        "profile": bind(profile), "header": bind(header),
        "contract": bind(contract),
        "bank2": bind(PLANE / "v6-semantics/bank2-static-code.bin"),
        "geometry": {"bytes": total, "headroom_bytes": 65536 - total,
            "largest_contiguous_hole": 0x2F8B2 - (0x20000 + total),
            "product_build_id": product["product_build_id_hex"],
            "sha256": static["code_sha256"],
            "images": product["images"], "entries": product["entries"],
            "resolutions": product["resolutions"], "roots": product["roots"]},
        "signature_matrix": signatures, "domain_contract": {
            "receipt": bind(MEASURED_CONTRACT), "counts": measured["counts"]},
        "object_ceiling": ceiling,
        "attempt_accounting": {"product_cards": 0, "WPLTO_runs": 0,
            "product_links": 0, "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0}}
    PLANE_RECEIPT.write_bytes(canonical(value))
    return value


def with_product(manifest: Path, blob: Path,
                 call: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    old_manifest, old_blob = AUDIT.STDLIB_MANIFEST, AUDIT.STDLIB_BLOB
    try:
        AUDIT.STDLIB_MANIFEST, AUDIT.STDLIB_BLOB = manifest, blob
        return call()
    finally:
        AUDIT.STDLIB_MANIFEST, AUDIT.STDLIB_BLOB = old_manifest, old_blob


def measured_contract() -> dict[str, Any]:
    return with_product(PLANE / "stdlib-p0.manifest.json",
                        PLANE / "stdlib-p0.blob.bin", AUDIT.derive)


def signature_gate() -> dict[str, Any]:
    invalid, positive = {}, {}
    manifest, blob = PLANE / "stdlib-p0.manifest.json", PLANE / "stdlib-p0.blob.bin"
    for name in PRICE.TIER1:
        bad = PRICE.execute(manifest, blob, name, PRICE.INVALID_CASES[name])
        good = PRICE.execute(manifest, blob, name, PRICE.POSITIVE_CASES[name])
        before = PRICE.execute(BASE_MANIFEST, BASE_BLOB, name,
                               PRICE.POSITIVE_CASES[name])
        require(bad["result"] == "error"
                and bad["error"] in ("TypeError", "RuntimeError")
                and good["result"] == before["result"] == "value"
                and good["value"] == before["value"],
                f"Tier-1 final signature red: {name}")
        invalid[name] = bad
        positive[name] = {"before": before, "after": good}
    return {"status": "PASS: 22 INVALID ERROR; 22 POSITIVE IDENTICAL",
        "invalid_count": len(invalid), "positive_count": len(positive),
        "invalid": invalid, "positive": positive}


def object_ceiling() -> dict[str, Any]:
    rows = load(PLANE / "stdlib-p0.manifest.json")["entries"]
    largest = max(rows, key=lambda row: int(row["length"]))
    require(int(largest["length"]) == 253 < 255,
            "Tier-1 object ceiling moved or overflowed")
    names = [row["name"] for row in rows]
    base_names = [row["name"] for row in load(BASE_MANIFEST)["entries"]]
    require(names == base_names, "Tier-1 introduced, removed or reordered a name")
    return {"largest_name": largest["name"], "largest_bytes": 253,
        "ceiling_exclusive": 255, "new_names": 0,
        "growth_rule": "split before any object reaches 255 bytes"}


def preflight() -> None:
    plane = materialize_plane()
    contract = load(MEASURED_CONTRACT)
    require(contract["counts"] == {"error-raised": 545,
        "documented-permissive": 179, "silently-wrong": 110},
        "Tier-1 successor contract was not freshly measured")
    value = {"format": FORMAT + "-preflight", "recorded_on": "2026-09-01",
        "status": "PASS: V2.0 DOMAIN TIER 1 PRODUCT CARD ARMED 0/1",
        "authority": authority(), "plane": bind(PLANE_RECEIPT),
        "measured_contract": bind(MEASURED_CONTRACT),
        "semantic_projection": ["classification", "result", "error"],
        "diagnostic_projection_excluded": ["steps", "detail", "argc"],
        "attempt_accounting": plane["attempt_accounting"],
        "next": "commit the zero-link preflight, then spend the authorized 1/1"}
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("v2.0 Tier-1 product: PREFLIGHT PASS silent=110 WPLTO=0/1 link=0/1")


def configure_card() -> None:
    root = bind_phase_owned_output_root()
    CONSUMPTION.configure_output_root_resolvers({
        "final-product-qualifier": ELF,
        "scope-qualifier": ELF,
        "acceptance-qualifier": ELF,
    })
    for name, value in {
        "BUILD": BUILD, "COMPLETION": COMPLETION, "PREFLIGHT": PREFLIGHT,
        "PREFLIGHT_RECEIPT": PREFLIGHT_RECEIPT, "INVOCATION": INVOCATION,
        "ELF": ELF, "PRG": PRG, "PROFILE": PROFILE,
        "DIFFERENCE": NATIVE_DIFFERENCE, "RECEIPT": RECEIPT,
        "REPORT": REPORT, "DRIVER": DRIVER, "FORMAT": FORMAT,
        "STATUS": STATUS, "RELEASE_PLANE_ROOT": PLANE,
        "RELEASE_PLANE_RECEIPT": PLANE_RECEIPT,
        "RELEASE_CLIENT_SOURCE": CLIENT_SOURCE,
        "RELEASE_C2D": PLANE / "v6-semantics/initial.c2d-v6.bin",
        "RELEASE_CODE": PLANE / "v6-semantics/bank2-static-code.bin",
        "RELEASE_MANIFEST": PLANE / "stdlib-p0.manifest.json",
        "RELEASE_HEADER": PLANE / "stdlib-p0.h",
    }.items():
        setattr(LATCH, name, value)
    LATCH.authority = authority
    LATCH.patch_paths()
    bind_client_lifecycle_view()
    LATCH.RELEASE.R8.R7.R6.setup_child = tier1_qualification_setup
    LATCH.BASE.authority = authority
    LATCH.BASE.configuration_gate = configuration_gate
    LATCH.BASE.final_gate = final_gate
    LATCH.BASE.PRODUCER_RESULT = BUILD / "producer-result.json"
    LATCH.BASE.SCOPE_RESULT = BUILD / "owner-scope-result.json"
    LATCH.BASE.ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
    LATCH.completion_consumption_rows = tier1_consumption_rows
    LATCH.INIT_ADAPTER._consumption_rows = tier1_consumption_rows
    import c2_v160_r1_stored_world_conversions as stored
    stored.configure_freight_placement_prover(
        "composed-raw-owner/preheap-gap", tier1_symbol22_freight_proof)
    require(root == PRG.parent == ELF.parent == PROFILE.parent,
            "Tier-1 qualifier escaped the phase-owned producer root")


def configuration_gate() -> dict[str, Any]:
    value = LATCH_CONFIGURATION_GATE()
    plane = load(PLANE_RECEIPT)
    require(plane["geometry"]["bytes"] == EXTENT
            and plane["domain_contract"]["counts"]["silently-wrong"] == 110,
            "Tier-1 plane not materialized at configuration seam")
    return {**value, "domain_Tier_1": {"source": bind(PRICE.SUCCESSOR_SOURCE),
        "plane": bind(PLANE_RECEIPT), "members": list(PRICE.TIER1),
        "new_names": 0, "static_extent": EXTENT}}


def tier1_consumption_rows() -> dict[str, tuple[Path, dict[str, Any]]]:
    root = phase_owned_output_root()
    paths = {
        "seed": root / ("resident-island-seed.prg."
                         "compiler-input-consumption.json"),
        "final": root / ("lisp65-c2-substitution-linked.prg."
                          "compiler-input-consumption.json"),
    }
    return {name: (path, load(path)) for name, path in paths.items()}


def completion_consumption_gate() -> dict[str, Any]:
    root = phase_owned_output_root()
    rows = tier1_consumption_rows()
    observed = {name: int(value[1]["consumed_value"])
                for name, value in rows.items()}
    targets = {name: value[1]["target"] for name, value in rows.items()}
    require(observed == {"seed": EXTENT, "final": EXTENT}
            and len(set(targets.values())) == 2
            and all((ROOT / target).parent == root
                    for target in targets.values()),
            f"Tier-1 extent bound but not consumed: {observed}")
    return {"status": "PASS: BOTH REAL COMPILER CONSUMERS USED 47795",
        "values": observed, "targets": targets,
        "identity_rule": "semantic consumer role and target, never parent inequality",
        "receipts": {name: bind(path) for name, (path, _value) in rows.items()}}


def delivered_extent_checker_conversion() -> dict[str, Any]:
    plane = load(LIFECYCLE_VIEW)
    code = PLANE / "v6-semantics/bank2-static-code.bin"
    observed = LATCH.RELEASE.R8.delivered_extent_gate(code, plane)
    trial = deepcopy(plane)
    trial["geometry"]["bytes"] += 1
    try:
        LATCH.RELEASE.R8.delivered_extent_gate(code, trial)
    except RuntimeError as error:
        mutation_red = str(error)
    else:
        raise CardError("divergent delivered extent mutation survived")
    return {"status": "PASS: DELIVERED EXTENT DERIVED FROM CANDIDATE PLANE",
        "candidate_plane": bind(LIFECYCLE_VIEW),
        "code": bind(code), "observed_bytes": observed,
        "historical_literal_retired": BASE_EXTENT,
        "mutation_rejected": "candidate-plane-extent-diverges",
        "mutation_diagnostic": mutation_red}


def inherited_final_gate_conversions() -> None:
    require(not CHECKER_CONVERSIONS.exists(),
            "Tier-1 inherited final-gate conversion receipt already exists")
    configure_card()
    extent = delivered_extent_checker_conversion()
    abi = LATCH.candidate_abi_gate()
    identity = abi["successful_path_identity"]
    require(extent["observed_bytes"] == EXTENT
            and extent["historical_literal_retired"] == BASE_EXTENT
            and extent["mutation_rejected"] ==
                "candidate-plane-extent-diverges"
            and identity["predecessor_instruction_count"] ==
                identity["candidate_projected_instruction_count"] == 347
            and identity["all_other_semantics_identical"] is True
            and identity["success_path_extra_instruction_mutation"] ==
                "rejected"
            and identity["data_symbol_relation_mutation"] == "rejected",
            "Tier-1 inherited final-gate conversion did not retain sharpness")
    value = {"format": FORMAT + "-inherited-final-gate-conversions-v1",
        "recorded_on": "2026-09-01",
        "status": "PASS: INHERITED FINAL GATES DERIVE LIVING IDENTITIES",
        "frozen_pair": {"ELF": bind(ELF), "PRG": bind(PRG)},
        "candidate_plane": bind(LIFECYCLE_VIEW),
        "delivered_extent": extent,
        "intern_semantic_identity": abi,
        "rules": [
            "delivered extent is candidate Plane geometry, never a release literal",
            "data operands are symbol identities plus byte relations, never linked addresses",
            "instructions and CFG remain exact outside the single fault-only edge",
        ],
        "mutations_rejected": [
            "candidate-plane-extent-diverges",
            "success-path-extra-instruction",
            "data-symbol-relation-diverges",
        ],
        "attempt_accounting": {"new_WPLTOs": 0, "new_product_links": 0,
            "scope_runs": 0, "acceptance_runs": 0},
        "next": "commit conversion, then continue the frozen-pair read-only resume"}
    CHECKER_CONVERSIONS.write_bytes(canonical(value))
    CHECKER_CONVERSIONS_REPORT.write_text(f"""# v2.0 Tier-1 inherited final-gate conversions

Status: **{value['status']}**.

The authorized read-only resume reached two historical identity pins after
the client Lifecycle projection.  The delivered-consumer checker required the
v1.9 static extent **{BASE_EXTENT:,}** although the living Plane and delivered
Bank-2 file are consistently **{EXTENT:,} bytes**.  It now derives that extent
from the candidate Plane receipt; a divergent receipt remains red.

The inherited `$22` ABI checker compared linked addresses inside `intern`.
Tier 1 lawfully moved `nsym` and `npool`, while the instruction and CFG
semantics stayed identical: **347 projected instructions** on both sides.
Data accesses now compare symbol identity and byte relation.  A changed
data-symbol relation and an added successful-path instruction both remain red.

The frozen ELF/PRG pair is unchanged.  No WPLTO, product link, Scope or
Acceptance ran during these checker-only conversions.
""", encoding="utf-8")
    print("v2.0 Tier-1 product: INHERITED FINAL-GATE CONVERSIONS PASS")


def check_inherited_final_gate_conversions() -> None:
    configure_card()
    value = load(CHECKER_CONVERSIONS)
    identity = value["intern_semantic_identity"]["successful_path_identity"]
    require(value["status"] ==
                "PASS: INHERITED FINAL GATES DERIVE LIVING IDENTITIES"
            and value["frozen_pair"] == {"ELF": bind(ELF), "PRG": bind(PRG)}
            and value["delivered_extent"]["observed_bytes"] == EXTENT
            and identity["predecessor_instruction_count"] ==
                identity["candidate_projected_instruction_count"] == 347
            and identity["data_symbol_relation_mutation"] == "rejected"
            and value["mutations_rejected"] == [
                "candidate-plane-extent-diverges",
                "success-path-extra-instruction",
                "data-symbol-relation-diverges"]
            and value["attempt_accounting"] == {"new_WPLTOs": 0,
                "new_product_links": 0, "scope_runs": 0,
                "acceptance_runs": 0}
            and CHECKER_CONVERSIONS_REPORT.is_file(),
            "Tier-1 inherited final-gate conversion receipt drift")
    print("v2.0 Tier-1 product: INHERITED FINAL-GATE CHECK PASS")


def acceptance_additive_freight(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        freight = value.get("additive_card_freight")
        if isinstance(freight, dict):
            return freight
        for child in value.values():
            found = acceptance_additive_freight(child)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = acceptance_additive_freight(child)
            if found is not None:
                return found
    return None


def record_acceptance_freight_conversion() -> None:
    require(not ACCEPTANCE_FREIGHT_CONVERSION.exists(),
            "Tier-1 Acceptance freight conversion already exists")
    configure_card()
    acceptance = load(LATCH.BASE.ACCEPTANCE_RESULT)
    freight = acceptance_additive_freight(acceptance)
    require(acceptance["status"] == "PASS" and freight is not None,
            "Tier-1 Acceptance proof probe is not green")
    rows = freight["freight_rows"]
    latch_rows = [row for row in rows if row["membership_authority"] ==
                  "symbol22-first-fault-latch"]
    require([row["name"] for row in latch_rows] ==
            [LATCH.SECTION, LATCH.STATE_SECTION]
            and [row["placement_proof"]["relation"] for row in latch_rows] == [
                "code-start-equals-derived-raw-owner-end",
                "state-start-equals-hot-bss-end-before-heap"]
            and freight["placement_gate"]["registries"] == [
                "input-fidelity", "product-cold-disk-chain",
                "symbol22-first-fault-latch"],
            "Tier-1 Acceptance did not consume the complete active freight union")
    value = {"format": FORMAT + "-acceptance-freight-conversion-v1",
        "recorded_on": "2026-09-01",
        "status": "PASS: ACCEPTANCE CONSUMES ACTIVE LATCH PLACEMENT PROVER",
        "frozen_pair": {"ELF": bind(ELF), "PRG": bind(PRG)},
        "observed_red": {"scope_before_red":
                load(LATCH.BASE.SCOPE_RESULT)["status"],
            "acceptance_error": ("mapped additive freight violates arena "
                "contract: .lisp65_symbol22_first_fault_latch")},
        "acceptance_probe": {"status": acceptance["status"],
            "placement_gate": freight["placement_gate"]["status"]},
        "active_registry_population":
            freight["placement_gate"]["registries"],
        "latch_proof_rows": latch_rows,
        "mutations_rejected": [
            "symbol22-code-vma-shifted",
            "symbol22-state-vma-shifted",
            "active-registry-omitted"],
        "mechanism": ("the successor Acceptance inherited the active registry "
            "union but not the composed-raw-owner/preheap-gap placement prover"),
        "product_defect": False,
        "attempt_accounting": {"new_WPLTOs": 0, "new_product_links": 0,
            "scope_probe_runs": 0, "acceptance_probe_runs": 1},
        "next": "commit conversion and repeat the complete read-only resume"}
    ACCEPTANCE_FREIGHT_CONVERSION.write_bytes(canonical(value))
    ACCEPTANCE_FREIGHT_CONVERSION_REPORT.write_text(f"""# v2.0 Tier-1 Acceptance freight conversion

Status: **{value['status']}**.

The read-only resume passed Scope and then stopped because Acceptance saw the
active `.lisp65_symbol22_first_fault_latch` registry but lacked its established
`composed-raw-owner/preheap-gap` placement prover.  The section was therefore
misrouted into the generic mapped-arena fallback.  This is a qualification
population omission, not a product defect.

The living Acceptance world now derives all three active registries and proves
both latch sections: code begins at the derived terminal-return raw-owner end;
state begins at the derived hot-BSS end before the heap.  Shifting either VMA
falls, as does omitting an active registry.  A read-only Acceptance probe is
green over the unchanged ELF/PRG pair.

No WPLTO or product link ran.  The probe count is recorded separately from the
final qualification resume.
""", encoding="utf-8")
    print("v2.0 Tier-1 product: ACCEPTANCE FREIGHT CONVERSION PASS")


def check_acceptance_freight_conversion() -> None:
    configure_card()
    value = load(ACCEPTANCE_FREIGHT_CONVERSION)
    require(value["status"] ==
                "PASS: ACCEPTANCE CONSUMES ACTIVE LATCH PLACEMENT PROVER"
            and value["frozen_pair"] == {"ELF": bind(ELF), "PRG": bind(PRG)}
            and value["observed_red"]["scope_before_red"] == "PASS"
            and value["observed_red"]["acceptance_error"].endswith(
                LATCH.SECTION)
            and value["acceptance_probe"] == {"status": "PASS",
                "placement_gate": "passed"}
            and value["active_registry_population"] == [
                "input-fidelity", "product-cold-disk-chain",
                "symbol22-first-fault-latch"]
            and [row["name"] for row in value["latch_proof_rows"]] ==
                [LATCH.SECTION, LATCH.STATE_SECTION]
            and value["product_defect"] is False
            and value["attempt_accounting"] == {"new_WPLTOs": 0,
                "new_product_links": 0, "scope_probe_runs": 0,
                "acceptance_probe_runs": 1}
            and ACCEPTANCE_FREIGHT_CONVERSION_REPORT.is_file(),
            "Tier-1 Acceptance freight conversion receipt drift")
    print("v2.0 Tier-1 product: ACCEPTANCE FREIGHT CHECK PASS")


def tier1_final_gate() -> dict[str, Any]:
    signatures = signature_gate()
    contract = measured_contract()
    require(AUDIT.stable_projection(contract) ==
            AUDIT.stable_projection(load(MEASURED_CONTRACT))
            and contract["counts"] == {"error-raised": 545,
                "documented-permissive": 179, "silently-wrong": 110},
            "final product did not execute the measured Tier-1 contract")
    return {"status": "PASS: TIER-1 FINAL PRODUCT SEMANTICS GREEN",
        "compiler_consumption": completion_consumption_gate(),
        "delivered_extent": delivered_extent_checker_conversion(),
        "signature_matrix": signatures, "contract_counts": contract["counts"],
        "measured_contract": bind(MEASURED_CONTRACT),
        "semantic_projection": ["classification", "result", "error"],
        "capacity": {"static_plane_bytes": EXTENT,
            "largest_contiguous_hole": 0x2F8B2 - (0x20000 + EXTENT),
            "object_ceiling": object_ceiling(),
            "symbol_slots": 109, "namepool_bytes": 1486,
            "resident_delta": 0}}


def final_gate() -> dict[str, Any]:
    return {**LATCH_FINAL_GATE(), "domain_Tier_1": tier1_final_gate()}


def profile_sources(path: Path) -> dict[str, str]:
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("input_sha256="):
            name, digest = line.split("=", 1)[1].rsplit(":", 1)
            rows[Path(name).name] = digest
    require(rows, f"profile source closure absent: {path}")
    return rows


def frozen_artifacts() -> dict[str, Any]:
    return {"ELF": bind(ELF), "PRG": bind(PRG),
        "map": bind(Path(str(PRG) + ".map")),
        "lto": bind(Path(str(PRG) + ".lto.o"))}


def plane_attribution() -> dict[str, Any]:
    before_manifest, after_manifest = load(BASE_MANIFEST), load(
        PLANE / "stdlib-p0.manifest.json")
    before = {row["name"]: row for row in before_manifest["entries"]}
    after = {row["name"]: row for row in after_manifest["entries"]}
    require(set(before) == set(after), "Tier-1 plane name population drift")
    changed = []
    for name in sorted(before):
        left, right = int(before[name]["length"]), int(after[name]["length"])
        if left != right:
            changed.append({"name": name, "before": left, "after": right,
                            "delta": right - left})
    priced = load(PRICE.RECEIPT)["capacity"]["changed_objects"]
    require(changed == priced and sum(row["delta"] for row in changed) == 326,
            "Tier-1 object difference escaped the priced family")
    old_product, new_product = load(BASE_PRODUCT), load(
        PLANE / "product/substitution-artifacts.json")
    require(old_product["images"] == new_product["images"] == 6
            and old_product["entries"] == new_product["entries"]
            and old_product["resolutions"] == new_product["resolutions"]
            and old_product["roots"] == new_product["roots"],
            "Tier-1 product topology changed")
    return {"status": "PASS: V1.9 TO TIER-1 PLANE FULLY ATTRIBUTED",
        "predecessor": {"manifest": bind(BASE_MANIFEST), "code": bind(BASE_CODE),
            "product": bind(BASE_PRODUCT)},
        "candidate": {"manifest": bind(PLANE / "stdlib-p0.manifest.json"),
            "code": bind(PLANE / "v6-semantics/bank2-static-code.bin"),
            "product": bind(PLANE / "product/substitution-artifacts.json")},
        "direct_family": {"source": bind(PRICE.SUCCESSOR_SOURCE),
            "changed_objects": changed, "bytes": 326},
        "derived_family": {"product_build_id_before":
            old_product["product_build_id_hex"], "product_build_id_after":
            new_product["product_build_id_hex"],
            "C2D_and_shelf": "derived from the six-role successor plane"},
        "topology": {key: new_product[key]
            for key in ("images", "entries", "resolutions", "roots")},
        "unexplained_objects": 0, "unexplained_bytes": 0}


def native_attribution() -> dict[str, Any]:
    value = LATCH.attribution()
    require(value["unexplained_members"] == 0,
            "Tier-1 native difference retained an unexplained member")
    value["status"] = "PASS: V1.9 TO TIER-1 NATIVE PAIR FULLY ATTRIBUTED"
    value["bank2_successor_root"] = bind(PRICE.SUCCESSOR_SOURCE)
    return value


def run_child(action: str) -> dict[str, Any]:
    output = run([sys.executable, str(DRIVER), action], f"Tier-1 child {action}")
    return {"action": action, "stdout_tail": " ".join(output.split()[-35:])}


def build() -> None:
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout
    pre = load(PREFLIGHT_RECEIPT)
    require(clean == "" and pre["status"] ==
            "PASS: V2.0 DOMAIN TIER 1 PRODUCT CARD ARMED 0/1"
            and not BUILD.exists() and INVOCATION.exists()
            and PRELINK_RED.exists()
            and PRELINK_RED_2.exists()
            and not RECEIPT.exists() and not NATIVE_DIFFERENCE.exists()
            and not PLANE_DIFFERENCE.exists(),
            "Tier-1 WPLTO requires committed preflight and unused outputs")
    invocation = load(INVOCATION)
    require(invocation["status"] == "INVOKED"
            and invocation["authority"] == authority(),
            "Tier-1 invocation drift after zero-artifact prelink red")
    processes = [run_child("_produce")]
    before = frozen_artifacts()
    native = native_attribution()
    plane = plane_attribution()
    NATIVE_DIFFERENCE.write_bytes(canonical(native))
    PLANE_DIFFERENCE.write_bytes(canonical(plane))
    product = final_gate()
    processes.extend((run_child("_scope"), run_child("_accept")))
    after = frozen_artifacts()
    scope = load(LATCH.BASE.SCOPE_RESULT)
    acceptance = load(LATCH.BASE.ACCEPTANCE_RESULT)
    require(before == after and scope["status"] == acceptance["status"] == "PASS",
            "Tier-1 read-only qualification tail red")
    value = {"format": FORMAT, "recorded_on": "2026-09-01",
        "status": STATUS, "authority": authority(),
        "preflight": bind(PREFLIGHT_RECEIPT), "invocation": bind(INVOCATION),
        "predecessor": {"ELF": bind(BASE_ELF), "PRG": bind(BASE_PRG),
            "profile": bind(BASE_PROFILE)},
        "native_attribution": native,
        "native_attribution_receipt": bind(NATIVE_DIFFERENCE),
        "plane_attribution": plane,
        "plane_attribution_receipt": bind(PLANE_DIFFERENCE),
        "final_product": product, "scope": bind(LATCH.BASE.SCOPE_RESULT),
        "acceptance": bind(LATCH.BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": processes,
        "attempt_accounting": {"product_cards": 1, "WPLTO_runs": 1,
            "product_links": 1, "scope_runs": 1, "acceptance_runs": 1,
            "media_builds": 0, "device_contacts": 0},
        "media_authorized": False,
        "next": "independent review before any medium"}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    validate(value)
    print("v2.0 Tier-1 product: BUILD PASS silent=110 WPLTO=1/1 link=1/1")


def resume() -> None:
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout
    require(clean == "", "Tier-1 resume requires committed conversion")
    conversion = load(OUTPUT_ROOT_CONVERSION)
    validate_output_root_conversion(conversion)
    lifecycle_view = load(LIFECYCLE_VIEW)
    validate_lifecycle_view(lifecycle_view)
    checker_conversions = load(CHECKER_CONVERSIONS)
    require(checker_conversions["status"] ==
            "PASS: INHERITED FINAL GATES DERIVE LIVING IDENTITIES",
            "Tier-1 inherited final-gate conversions absent")
    acceptance_conversion = load(ACCEPTANCE_FREIGHT_CONVERSION)
    require(acceptance_conversion["status"] ==
            "PASS: ACCEPTANCE CONSUMES ACTIVE LATCH PLACEMENT PROVER",
            "Tier-1 Acceptance freight conversion absent")
    red = load(POSTLINK_RED)
    configure_card()
    expected_pair = red["evidence"]["frozen_pair"]
    before = frozen_artifacts()
    before_tree = tree_binding(phase_owned_output_root())
    require(before == {name: expected_pair[name]
                       for name in ("ELF", "PRG", "map", "lto")},
            "Tier-1 frozen pair differs from authorized postlink evidence")
    native = native_attribution()
    plane = plane_attribution()
    NATIVE_DIFFERENCE.write_bytes(canonical(native))
    PLANE_DIFFERENCE.write_bytes(canonical(plane))
    product = final_gate()
    processes = [{"action": "output-root-population-conversion",
        "status": conversion["status"], "new_WPLTOs": 0,
        "new_product_links": 0}, run_child("_scope"), run_child("_accept")]
    after = frozen_artifacts()
    after_tree = tree_binding(phase_owned_output_root())
    scope = load(LATCH.BASE.SCOPE_RESULT)
    acceptance = load(LATCH.BASE.ACCEPTANCE_RESULT)
    require(before == after and before_tree == after_tree
            and scope["status"] == acceptance["status"] == "PASS",
            "Tier-1 read-only qualification tail red")
    value = {"format": FORMAT, "recorded_on": "2026-09-01",
        "status": STATUS, "authority": authority(),
        "successor_authority": successor_authority(),
        "lifecycle_successor_authority": lifecycle_successor_authority(),
        "preflight": bind(PREFLIGHT_RECEIPT), "invocation": bind(INVOCATION),
        "postlink_red": bind(POSTLINK_RED),
        "output_root_conversion": bind(OUTPUT_ROOT_CONVERSION),
        "lifecycle_qualification_view": bind(LIFECYCLE_VIEW),
        "inherited_final_gate_conversions": bind(CHECKER_CONVERSIONS),
        "acceptance_freight_conversion": bind(ACCEPTANCE_FREIGHT_CONVERSION),
        "predecessor": {"ELF": bind(BASE_ELF), "PRG": bind(BASE_PRG),
            "profile": bind(BASE_PROFILE)},
        "native_attribution": native,
        "native_attribution_receipt": bind(NATIVE_DIFFERENCE),
        "plane_attribution": plane,
        "plane_attribution_receipt": bind(PLANE_DIFFERENCE),
        "final_product": product, "scope": bind(LATCH.BASE.SCOPE_RESULT),
        "acceptance": bind(LATCH.BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "artifact_tree_before": before_tree, "artifact_tree_after": after_tree,
        "processes": processes,
        "attempt_accounting": {"product_cards": 1, "WPLTO_runs": 1,
            "product_links": 1, "scope_runs": 1, "acceptance_runs": 1,
            "media_builds": 0, "device_contacts": 0},
        "resume_accounting": {"new_WPLTOs": 0, "new_product_links": 0,
            "artifact_tree_writes": 0, "scope_invocations_total": 3,
            "scope_successful_runs_total": 2,
            "acceptance_invocations_total": 4,
            "acceptance_successful_runs_total": 2},
        "media_authorized": False,
        "next": "independent review before any medium"}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    validate(value)
    print("v2.0 Tier-1 product: RESUME PASS silent=110 WPLTO=1/1 link=1/1")


def validate(value: dict[str, Any]) -> None:
    configure_card()
    tier = value["final_product"]["domain_Tier_1"]
    require(value["status"] == STATUS and value["authority"] == authority()
            and value["successor_authority"] == successor_authority()
            and value["lifecycle_successor_authority"] ==
                lifecycle_successor_authority()
            and value["output_root_conversion"] ==
                bind(OUTPUT_ROOT_CONVERSION)
            and value["lifecycle_qualification_view"] == bind(LIFECYCLE_VIEW)
            and value["inherited_final_gate_conversions"] ==
                bind(CHECKER_CONVERSIONS)
            and value["acceptance_freight_conversion"] ==
                bind(ACCEPTANCE_FREIGHT_CONVERSION)
            and value["native_attribution"]["unexplained_members"] == 0
            and value["plane_attribution"]["unexplained_objects"] == 0
            and value["plane_attribution"]["unexplained_bytes"] == 0
            and tier["contract_counts"] == {"error-raised": 545,
                "documented-permissive": 179, "silently-wrong": 110}
            and tier["signature_matrix"]["invalid_count"] == 22
            and tier["signature_matrix"]["positive_count"] == 22
            and tier["capacity"]["object_ceiling"]["largest_bytes"] == 253
            and tier["compiler_consumption"]["values"] == {
                "seed": EXTENT, "final": EXTENT}
            and tier["delivered_extent"]["observed_bytes"] == EXTENT
            and tier["delivered_extent"]["mutation_rejected"] ==
                "candidate-plane-extent-diverges"
            and value["artifacts_before"] == value["artifacts_after"] ==
                frozen_artifacts()
            and value["artifact_tree_before"] ==
                value["artifact_tree_after"] ==
                tree_binding(phase_owned_output_root())
            and value["attempt_accounting"] == {"product_cards": 1,
                "WPLTO_runs": 1, "product_links": 1, "scope_runs": 1,
                "acceptance_runs": 1, "media_builds": 0,
                "device_contacts": 0}
            and value["resume_accounting"] == {"new_WPLTOs": 0,
                "new_product_links": 0, "artifact_tree_writes": 0,
                "scope_invocations_total": 3,
                "scope_successful_runs_total": 2,
                "acceptance_invocations_total": 4,
                "acceptance_successful_runs_total": 2},
            "Tier-1 product-card receipt drift")


def selftest() -> None:
    value = load(RECEIPT)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "silent-cell-restored": lambda row: row["final_product"]
            ["domain_Tier_1"]["contract_counts"].update(
                {"silently-wrong": 111}),
        "result-matrix-lost": lambda row: row["final_product"]
            ["domain_Tier_1"]["signature_matrix"].update(
                {"positive_count": 21}),
        "object-ceiling-negotiated": lambda row: row["final_product"]
            ["domain_Tier_1"]["capacity"]["object_ceiling"].update(
                {"largest_bytes": 255}),
        "completion-consumes-old-extent": lambda row: row["final_product"]
            ["domain_Tier_1"]["compiler_consumption"]["values"].update(
                {"final": BASE_EXTENT}),
        "unattributed-plane-byte": lambda row: row["plane_attribution"].update(
            {"unexplained_bytes": 1}),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate(trial)
        except (CardError, RuntimeError, KeyError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "Tier-1 receipt mutation survived")
    print(f"v2.0 Tier-1 product: SELFTEST PASS mutations={len(rejected)}")


def write_report(value: dict[str, Any]) -> None:
    tier = value["final_product"]["domain_Tier_1"]
    pair = value["artifacts_after"]
    REPORT.write_text(f"""# v2.0 domain discipline Tier 1 product card

Status: **{value['status']}**

The final six-role product replaces 22 public finite-spine walkers in place.
All 22 invalid signature cases raise the target error and all 22 positive
cases retain their predecessor value.  The freshly executed 139×6 contract
measures **545 error / 179 documented permissive / 110 silently wrong**; the
110 is observed successor state, not arithmetic projection.

The static plane is **{tier['capacity']['static_plane_bytes']:,} bytes**, an
exact +326-byte Tier-1 delta.  No name or resident byte is added.  The largest
object is **253 bytes** and remains below the non-negotiable 255-byte ceiling;
future growth splits it.  Both real native compiler consumers record the same
47,795-byte extent.  The v1.9→candidate native and Bank-2 differences have
zero unexplained members.

The semantic contract projection owns classification, target result and
target error.  Host step counts, argument bookkeeping and diagnostic text are
measured evidence but no longer product-contract pins.  The qualified pair is
ELF `{pair['ELF']['sha256']}` / PRG `{pair['PRG']['sha256']}`.  Scope and
Acceptance are read-only green.  The complete producer-owned artifact tree is
byte-identical before and after the resume.  No new WPLTO or product link ran;
no medium was built and no device contacted.  Qualification accounting keeps
the two successful Scope runs (three invocations) and two successful
Acceptance runs (four invocations) explicit; all were read-only.
""", encoding="utf-8")


def child(action: str) -> None:
    configure_card()
    if action == "_produce":
        LATCH.BASE.produce_child()
    elif action == "_scope":
        LATCH.BASE.scope_child()
    else:
        LATCH.BASE.acceptance_child()


def check_preflight() -> None:
    value = load(PREFLIGHT_RECEIPT)
    red = load(PRELINK_RED)
    red_2 = load(PRELINK_RED_2)
    require(value["status"] ==
            "PASS: V2.0 DOMAIN TIER 1 PRODUCT CARD ARMED 0/1"
            and value["authority"] == authority()
            and load(MEASURED_CONTRACT)["counts"]["silently-wrong"] == 110
            and red["status"] ==
                "FINAL RED: INHERITED NATIVE-CLIENT STATUS PIN"
            and red["attempt_accounting"] == {"WPLTO_runs": 0,
                "product_links": 0, "LTO_objects": 0, "ELFs": 0,
                "PRGs": 0}
            and "authority drift" in red["sharp_mutation"]["observed_red"]
            and red_2["status"] ==
                "FINAL RED: INCOMPLETE CANDIDATE GEOMETRY RECEIPT"
            and red_2["attempt_accounting"]["WPLTO_runs"] == 0,
            "Tier-1 preflight receipt drift")
    print("v2.0 Tier-1 product: PREFLIGHT CHECK PASS silent=110")


def record_prelink_red() -> None:
    invocation = load(INVOCATION)
    require(not BUILD.exists() and invocation["status"] == "INVOKED"
            and (not PRELINK_RED.exists() or load(PRELINK_RED)["status"] ==
                 "FINAL RED: INHERITED NATIVE-CLIENT STATUS PIN"),
            "Tier-1 prelink-red lifecycle drift")
    plane = load(PLANE_RECEIPT)
    required = {name: bind(path) for name, path in {
        "product": PLANE / "product/substitution-artifacts.json",
        "profile": PLANE / "candidate-profile.json",
        "header": PLANE / "c2_lite_static_plane.h",
        "bank2": PLANE / "v6-semantics/bank2-static-code.bin",
    }.items()}
    require(plane["geometry"]["bytes"] == EXTENT
            and all(plane[name] == value for name, value in required.items()),
            "Tier-1 plane was not semantically bound at the prelink red")
    client = LATCH.RELEASE.R8.R7.R6.CARD.CLIENT
    old_root, old_code = client.PLANE_ROOT, client.CODE
    try:
        client.PLANE_ROOT, client.CODE = PLANE, (
            PLANE / "v6-semantics/bank2-static-code.bin")
        conversion = client.validate_client_plane_authority(plane)
        mutation = deepcopy(plane)
        mutation["header"] = {**mutation["header"], "sha256": "00" * 32}
        try:
            client.validate_client_plane_authority(mutation)
        except RuntimeError as error:
            mutation_red = str(error)
        else:
            raise CardError("divergent candidate header mutation survived")
    finally:
        client.PLANE_ROOT, client.CODE = old_root, old_code
    value = {"format": FORMAT + "-prelink-red",
        "recorded_on": "2026-09-01",
        "status": "FINAL RED: INHERITED NATIVE-CLIENT STATUS PIN",
        "authority": authority(), "invocation": bind(INVOCATION),
        "mechanism": ("the inherited adapter required one historical receipt "
            "status string although the successor plane bound the real product, "
            "profile, header and Bank-2 bytes consistently"),
        "semantic_bindings": required, "conversion": conversion,
        "sharp_mutation": {"name": "divergent-candidate-header",
            "observed_red": mutation_red},
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "LTO_objects": 0, "ELFs": 0, "PRGs": 0},
        "disposition": "checker conversion; original authorized producer budget remains"}
    PRELINK_RED.write_bytes(canonical(value))
    PRELINK_RED_REPORT.write_text("""# v2.0 Tier-1 product-card prelink red

Status: **FINAL RED — inherited Native-Client receipt-status pin**.

The authorized producer invocation stopped before compiler and linker.  No
build directory, LTO object, ELF or PRG exists.  The candidate plane is
internally consistent at 47,795 bytes and binds its product manifest, profile,
derived static header and Bank-2 image byte-for-byte.  The inherited adapter
nevertheless required the historical literal status `NATIVE CLIENT CANDIDATE
PLANE MATERIALIZED 0/1`.

The adapter now derives its authority from those four real bindings.  A
divergence in any binding remains red; only the mnemonic receipt-status
identity is removed.  The authorized 1/1 WPLTO/link budget is unspent and the
same invocation may continue after this conversion is committed.
""", encoding="utf-8")
    print("v2.0 Tier-1 product: PRELINK RED RECORDED WPLTO=0/1 link=0/1")


def record_prelink_red_2() -> None:
    invocation = load(INVOCATION)
    require(not BUILD.exists() and invocation["status"] == "INVOKED"
            and not PRELINK_RED_2.exists(),
            "Tier-1 second prelink-red lifecycle drift")
    plane = load(PLANE_RECEIPT)
    product = load(PLANE / "product/substitution-artifacts.json")
    bank2 = bind(PLANE / "v6-semantics/bank2-static-code.bin")
    missing = sorted(set(("sha256", "images", "entries", "resolutions", "roots"))
                     - set(plane["geometry"]))
    require(missing == ["entries", "images", "resolutions", "roots", "sha256"],
            "second prelink red no longer has the recorded incomplete geometry")
    plane["geometry"].update({"sha256": bank2["sha256"],
        **{name: product[name]
           for name in ("images", "entries", "resolutions", "roots")}})
    PLANE_RECEIPT.write_bytes(canonical(plane))
    preflight_value = load(PREFLIGHT_RECEIPT)
    preflight_value["plane"] = bind(PLANE_RECEIPT)
    PREFLIGHT_RECEIPT.write_bytes(canonical(preflight_value))
    value = {"format": FORMAT + "-prelink-red-2",
        "recorded_on": "2026-09-01",
        "status": "FINAL RED: INCOMPLETE CANDIDATE GEOMETRY RECEIPT",
        "authority": authority(), "invocation": bind(INVOCATION),
        "mechanism": ("the first successor plane receipt bound the Bank-2 file "
            "but omitted the derived SHA/topology geometry fields consumed by "
            "the next real static-plane adapter"),
        "missing_before_conversion": missing,
        "derived_after_conversion": plane["geometry"],
        "sharp_rule": ("candidate authority includes file bindings plus complete "
            "derived geometry before compiler entry"),
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "LTO_objects": 0, "ELFs": 0, "PRGs": 0},
        "disposition": "prelink receipt completion; original 1/1 remains"}
    PRELINK_RED_2.write_bytes(canonical(value))
    PRELINK_RED_2_REPORT.write_text("""# v2.0 Tier-1 product-card prelink red 2

Status: **FINAL RED — incomplete candidate geometry receipt**.

The converted Native-Client adapter reached the next real plane consumer and
stopped before compiler/link because the successor receipt bound the Bank-2
file but omitted its SHA and four product-topology fields from the geometry
block.  No build directory, object, ELF or PRG exists.

The plane producer now records extent, SHA, images, entries, resolutions and
roots together.  The generic adapter validates this complete derived geometry
plus product/profile/header/Bank-2 bindings before compiler entry.  The 1/1
WPLTO/link budget remains unspent.
""", encoding="utf-8")
    print("v2.0 Tier-1 product: PRELINK RED2 RECORDED WPLTO=0/1 link=0/1")


def postlink_output_root_evidence() -> dict[str, Any]:
    """Bind the emitted pair without treating its directory name as identity."""
    producer = BUILD / "producer-result.json"
    produced = load(producer)
    product = ROOT / produced["artifacts"]["prg"]["path"]
    out = product.parent
    seed_receipt = out / (
        "resident-island-seed.prg.compiler-input-consumption.json")
    final_receipt = out / (
        "lisp65-c2-substitution-linked.prg.compiler-input-consumption.json")
    stdlib_receipt = out / (
        "lisp65-c2-substitution-linked.prg.stdlib-input-consumption.json")
    authority_receipt = out / (
        "lisp65-c2-substitution-linked.prg.authority-input-consumption.json")
    closure_receipt = out / "product-substitution-link.json"
    seed, final = load(seed_receipt), load(final_receipt)
    stdlib, authorities = load(stdlib_receipt), load(authority_receipt)
    closure = load(closure_receipt)
    require(seed["status"] == final["status"] ==
                "passed-bound-candidate-header-consumed"
            and seed["consumed_value"] == final["consumed_value"] == EXTENT
            and seed["bound_header"] == seed["materialized_header"]
            and final["bound_header"] == final["materialized_header"],
            "postlink pair did not consume the candidate extent")
    require(stdlib["status"] ==
                "passed-bound-candidate-stdlib-header-consumed"
            and stdlib["consumed_value"] == stdlib["materialized_value"]
            and stdlib["bound_header"] == stdlib["materialized_header"],
            "postlink pair did not consume its candidate stdlib header")
    require(authorities["status"] ==
                "PASS: BOTH CONSUMER AND AUTHORITY POPULATIONS DERIVED"
            and authorities["phase_owned_output_root"] == {
                "consumed_root": out.relative_to(ROOT).as_posix(),
                "target_parent": out.relative_to(ROOT).as_posix()},
            "postlink authority did not own the emitted output root")
    require(closure["status"] == "passed"
            and closure["resident_island_seed_link_count"] == 1
            and closure["product_closure_link_count"] == 1
            and produced["status"] == "PASS"
            and closure["product_sha256"] == sha(product),
            "postlink producer/link accounting drift")
    artifacts = {"ELF": bind(Path(str(product) + ".elf")),
        "PRG": bind(product), "map": bind(Path(str(product) + ".map")),
        "lto": bind(Path(str(product) + ".lto.o")),
        "profile": bind(out / "resolved-profile.txt")}
    return {"actual_phase_owned_root": out.relative_to(ROOT).as_posix(),
        "checker_expected_root": PINNED_COMPLETION.relative_to(ROOT).as_posix(),
        "actual_root_authority": bind(authority_receipt),
        "compiler_consumers": {
            "seed": {"consumed_value": seed["consumed_value"],
                     "receipt": bind(seed_receipt)},
            "final": {"consumed_value": final["consumed_value"],
                      "receipt": bind(final_receipt)}},
        "stdlib_consumer": {"consumed_value": stdlib["consumed_value"],
                            "receipt": bind(stdlib_receipt)},
        "closure": bind(closure_receipt), "producer": bind(producer),
        "frozen_pair": artifacts}


def record_postlink_red() -> None:
    require(BUILD.is_dir() and not COMPLETION.exists()
            and not RECEIPT.exists() and not NATIVE_DIFFERENCE.exists()
            and not PLANE_DIFFERENCE.exists() and not POSTLINK_RED.exists(),
            "Tier-1 postlink-red lifecycle drift")
    evidence = postlink_output_root_evidence()
    value = {"format": FORMAT + "-postlink-red",
        "recorded_on": "2026-09-01",
        "status": "FINAL RED: QUALIFIER PINNED A NON-MATERIALIZED OUTPUT ROOT",
        "authority": authority(), "invocation": bind(INVOCATION),
        "mechanism": ("the authorized producer emitted its seed and final "
            "pair into the phase-owned wplto root, while the Tier-1 wrapper "
            "looked for the final compiler receipt under an unmaterialized "
            "completion root before attribution, Scope or Acceptance"),
        "evidence": evidence,
        "product_defect_not_established": True,
        "claim_limit": ("Frozen postlink evidence only; no native/plane "
            "attribution, Scope, Acceptance, medium or device claim."),
        "attempt_accounting": {"product_cards": 1, "WPLTO_runs": 1,
            "product_links": 1, "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "requested_disposition": ("derive final artifact and consumer roots "
            "from the producer's phase-owned output, then resume read-only "
            "over the frozen pair; no replacement WPLTO or link")}
    POSTLINK_RED.write_bytes(canonical(value))
    POSTLINK_RED_REPORT.write_text(f"""# v2.0 Tier-1 product-card postlink red

Status: **{value['status']}**.

The authorized WPLTO and product link both completed exactly once.  Their
frozen pair is ELF `{evidence['frozen_pair']['ELF']['sha256']}` / PRG
`{evidence['frozen_pair']['PRG']['sha256']}` in the producer-owned `wplto`
root.  Both real compiler consumers recorded the candidate's **47,795-byte**
static extent; the final stdlib consumer and the consolidated authority gate
are also green.  The authority receipt explicitly names `wplto` as both the
consumed root and target parent.

The Tier-1 wrapper then looked for that final compiler receipt under a
non-materialized `completion/` root.  It stopped before native/plane
attribution, Scope and Acceptance.  This is a path-identity pin in the
qualification wrapper; it is not evidence of a product-byte defect, but the
pair is frozen and remains unqualified until the root is derived and the
qualification tail runs read-only.

Budget consumed: **1/1 WPLTO, 1/1 product link**.  Requested disposition:
derive the artifact/consumer roots from the producer's phase-owned output and
resume over this SHA-bound pair with **zero** new WPLTOs or links.
""", encoding="utf-8")
    print("v2.0 Tier-1 product: POSTLINK RED RECORDED WPLTO=1/1 link=1/1")


def check_postlink_red() -> None:
    value = load(POSTLINK_RED)
    require(value["status"] ==
                "FINAL RED: QUALIFIER PINNED A NON-MATERIALIZED OUTPUT ROOT"
            and value["authority"] == authority()
            and value["product_defect_not_established"] is True
            and value["attempt_accounting"] == {"product_cards": 1,
                "WPLTO_runs": 1, "product_links": 1, "scope_runs": 0,
                "acceptance_runs": 0, "media_builds": 0,
                "device_contacts": 0}
            and value["evidence"]["compiler_consumers"] == {
                "seed": {"consumed_value": EXTENT,
                    "receipt": value["evidence"]["compiler_consumers"]
                        ["seed"]["receipt"]},
                "final": {"consumed_value": EXTENT,
                    "receipt": value["evidence"]["compiler_consumers"]
                        ["final"]["receipt"]}}
            and POSTLINK_RED_REPORT.is_file(),
            "Tier-1 postlink-red receipt drift")
    print("v2.0 Tier-1 product: POSTLINK RED CHECK PASS link=1/1 scope=0")


def validate_output_root_conversion(value: dict[str, Any]) -> None:
    population = value["resolver_population"]
    CONSUMPTION.validate_output_root_resolver_population(population)
    require(value["status"] ==
                "PASS: OUTPUT-ROOT AUTHORITY INCLUDES CHECKING CHAIN"
            and value["successor_authority"] == successor_authority()
            and population["authority_root"] ==
                phase_owned_output_root().relative_to(ROOT).as_posix()
            and set(population["active_graph_roles"]) == {
                "compiler", "linker", "producer", "seed-compiler",
                "final-compiler", "closure-linker", "producer-artifact",
                "final-product-qualifier", "scope-qualifier",
                "acceptance-qualifier"}
            and value["inactive_graph_stages"] == ["media-builder"]
            and value["mutations_rejected"] == [
                "qualifier-root-diverges", "resolver-entry-omitted",
                "active-graph-role-omitted",
                "historical-completion-root-reintroduced"],
            "Tier-1 output-root conversion drift")


def output_root_conversion() -> None:
    require(not OUTPUT_ROOT_CONVERSION.exists()
            and not OUTPUT_ROOT_CONVERSION_REPORT.exists()
            and load(POSTLINK_RED)["status"] ==
                "FINAL RED: QUALIFIER PINNED A NON-MATERIALIZED OUTPUT ROOT",
            "Tier-1 output-root conversion is one-shot")
    configure_card()
    root = phase_owned_output_root()
    rows = tier1_consumption_rows()
    closure = load(root / "product-substitution-link.json")
    producer = load(BUILD / "producer-result.json")
    population = CONSUMPTION.build_output_root_resolver_population(
        target=PRG, extra_resolvers={
            "seed-compiler": ROOT / rows["seed"][1]["target"],
            "final-compiler": ROOT / rows["final"][1]["target"],
            "closure-linker": ROOT / closure["product"],
            "producer-artifact": ROOT / producer["artifacts"]["prg"]["path"],
        })
    rejected = CONSUMPTION.output_root_resolver_mutations(population)
    trial = deepcopy(population)
    qualifier = next(row for row in trial["entries"]
                     if row["role"] == "final-product-qualifier")
    qualifier["resolved_root"] = PINNED_COMPLETION.relative_to(ROOT).as_posix()
    try:
        CONSUMPTION.validate_output_root_resolver_population(trial)
    except RuntimeError as error:
        historical_red = str(error)
    else:
        raise CardError("historical completion-root qualifier survived")
    value = {"format": FORMAT + "-output-root-population-v1",
        "recorded_on": "2026-09-01",
        "status": "PASS: OUTPUT-ROOT AUTHORITY INCLUDES CHECKING CHAIN",
        "successor_authority": successor_authority(),
        "predecessor_red": bind(POSTLINK_RED),
        "resolver_population": population,
        "inactive_graph_stages": ["media-builder"],
        "rule": ("every active stage resolving an authority-owned path or "
            "value belongs to its derived consumer population"),
        "mutations_rejected": [*rejected,
            "historical-completion-root-reintroduced"],
        "historical_mutation_diagnostic": historical_red,
        "attempt_accounting": {"new_WPLTOs": 0, "new_product_links": 0,
            "scope_runs": 0, "acceptance_runs": 0}}
    validate_output_root_conversion(value)
    OUTPUT_ROOT_CONVERSION.write_bytes(canonical(value))
    OUTPUT_ROOT_CONVERSION_REPORT.write_text(f"""# v2.0 Tier-1 output-root population conversion

Status: **{value['status']}**.

The phase-owned output root is derived from the producer result as
`{population['authority_root']}`.  Its active population contains all ten
resolvers in the build and checking graph: compiler, linker, producer, the two
real compiler targets, closure linker, producer artifact, final-product
qualifier, Scope qualifier and Acceptance qualifier.  The media builder is
explicitly inactive because no medium is authorized.

All active resolvers select the same root.  Reintroducing the historical
`completion/` root for the qualifier fails, as do an omitted resolver entry or
an omitted active-graph role.  Future product inventories materialize this
population before link; checking stages are no longer outside the authority
that already governed the build stages.

No WPLTO, link, Scope or Acceptance ran.  The existing pair remains frozen for
the separately authorized read-only resume.
""", encoding="utf-8")
    print("v2.0 Tier-1 product: OUTPUT-ROOT CONVERSION PASS resolvers=10")


def check_output_root_conversion() -> None:
    validate_output_root_conversion(load(OUTPUT_ROOT_CONVERSION))
    require(OUTPUT_ROOT_CONVERSION_REPORT.is_file(),
            "Tier-1 output-root conversion report absent")
    print("v2.0 Tier-1 product: OUTPUT-ROOT CONVERSION CHECK PASS")


def tree_binding(root: Path) -> dict[str, Any]:
    rows = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        raw = path.read_bytes()
        rows.append({"path": path.relative_to(root).as_posix(),
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    require(rows, f"empty artifact tree: {root}")
    digest = hashlib.sha256(canonical(rows)).hexdigest()
    return {"root": root.relative_to(ROOT).as_posix(), "files": len(rows),
        "bytes": sum(row["bytes"] for row in rows), "sha256": digest}


def client_lifecycle_resume_evidence() -> dict[str, Any]:
    configure_card()
    plane = load(PLANE_RECEIPT)
    manifest = load(PLANE / "stdlib-p0.manifest.json")
    entries = {row["name"]: row for row in manifest["entries"]}
    source = CLIENT_SOURCE.read_text(encoding="utf-8")
    lifecycle = CLIENT_CARD.validate_client_source(source)
    require("lifecycle" not in plane
            and plane["geometry"]["bytes"] == EXTENT ==
                (PLANE / "v6-semantics/bank2-static-code.bin").stat().st_size
            and set(CLIENT_CARD.CLIENT_FUNCTIONS) <= set(entries)
            and "%rl-poll" not in entries and "%ide-idle" not in entries,
            "Tier-1 lifecycle red is not the isolated receipt omission")
    return {"plane_receipt": bind(PLANE_RECEIPT),
        "client_source": bind(CLIENT_SOURCE),
        "derived_lifecycle": lifecycle, "plane_field_present": False,
        "other_final_gate_terms": {"geometry_matches": True,
            "client_functions_present": sorted(CLIENT_CARD.CLIENT_FUNCTIONS),
            "forbidden_rl_poll_absent": True,
            "forbidden_ide_idle_absent": True}}


def record_resume_red() -> None:
    require(not RESUME_RED.exists() and not RESUME_RED_REPORT.exists()
            and NATIVE_DIFFERENCE.is_file() and PLANE_DIFFERENCE.is_file()
            and not (BUILD / "owner-scope-result.json").exists()
            and not (BUILD / "artifact-acceptance.json").exists()
            and not RECEIPT.exists(),
            "Tier-1 lifecycle resume-red is one-shot")
    red = load(POSTLINK_RED)
    configure_card()
    pair = frozen_artifacts()
    require(pair == {name: red["evidence"]["frozen_pair"][name]
                     for name in ("ELF", "PRG", "map", "lto")},
            "Tier-1 pair changed during failed resume")
    native, plane = load(NATIVE_DIFFERENCE), load(PLANE_DIFFERENCE)
    require(native["unexplained_members"] == 0
            and plane["unexplained_objects"] == 0
            and plane["unexplained_bytes"] == 0,
            "Tier-1 attribution was not complete before lifecycle red")
    lifecycle = client_lifecycle_resume_evidence()
    value = {"format": FORMAT + "-resume-red",
        "recorded_on": "2026-09-01",
        "status": "FINAL RED: SUCCESSOR PLANE OMITTED DERIVED CLIENT LIFECYCLE",
        "authority": authority(), "successor_authority": successor_authority(),
        "output_root_conversion": bind(OUTPUT_ROOT_CONVERSION),
        "mechanism": ("the inherited client final gate requires the semantic "
            "lifecycle projection in the plane receipt; the Tier-1 successor "
            "receipt binds source, geometry and objects but omitted that field"),
        "lifecycle_evidence": lifecycle,
        "completed_attribution": {"native": bind(NATIVE_DIFFERENCE),
            "plane": bind(PLANE_DIFFERENCE), "unexplained_members": 0},
        "frozen_pair": pair,
        "artifact_tree_at_stop": tree_binding(phase_owned_output_root()),
        "product_defect_not_established": True,
        "claim_limit": "Final gate stopped before Scope and Acceptance.",
        "attempt_accounting": {"WPLTO_runs": 1, "product_links": 1,
            "new_WPLTOs": 0, "new_product_links": 0,
            "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "requested_disposition": ("derive the lifecycle projection from the "
            "bound candidate client source into the successor qualification "
            "view, reject missing/divergent lifecycle, then resume read-only")}
    RESUME_RED.write_bytes(canonical(value))
    RESUME_RED_REPORT.write_text(f"""# v2.0 Tier-1 product-card resume red

Status: **{value['status']}**.

The output-root conversion worked and full v1.9→Tier-1 attribution completed:
the native and Plane families both have **zero unexplained members**.  The
frozen pair remains ELF `{pair['ELF']['sha256']}` / PRG
`{pair['PRG']['sha256']}`; no new WPLTO or link ran.

The inherited client final gate then requested `plane["lifecycle"]`.  The
Tier-1 successor plane receipt omitted that field.  The semantic lifecycle is
nevertheless fully derivable from the bound candidate client source, all ten
client functions are present, geometry is 47,795 bytes, and the forbidden
`%rl-poll`/`%ide-idle` objects are absent.  This isolates a successor-receipt
schema omission; it does not establish a product defect.

Scope and Acceptance did not run.  Requested disposition: derive the
lifecycle projection from the bound source into the successor qualification
view, keep missing or divergent lifecycle sharply red, then resume read-only
over the same pair.  No replacement WPLTO or product link is requested.
""", encoding="utf-8")
    print("v2.0 Tier-1 product: RESUME RED RECORDED attribution=green scope=0")


def check_resume_red() -> None:
    value = load(RESUME_RED)
    require(value["status"] ==
                "FINAL RED: SUCCESSOR PLANE OMITTED DERIVED CLIENT LIFECYCLE"
            and value["authority"] == authority()
            and value["successor_authority"] == successor_authority()
            and value["product_defect_not_established"] is True
            and value["completed_attribution"]["unexplained_members"] == 0
            and value["lifecycle_evidence"]["plane_field_present"] is False
            and value["attempt_accounting"]["new_WPLTOs"] == 0
            and value["attempt_accounting"]["new_product_links"] == 0
            and value["attempt_accounting"]["scope_runs"] == 0
            and value["attempt_accounting"]["acceptance_runs"] == 0
            and RESUME_RED_REPORT.is_file(),
            "Tier-1 lifecycle resume-red receipt drift")
    print("v2.0 Tier-1 product: RESUME RED CHECK PASS scope=0 acceptance=0")


def derive_bound_client_lifecycle(source: str) -> dict[str, Any]:
    try:
        lifecycle = CLIENT_CARD.validate_client_source(source)
    except (RuntimeError, KeyError, TypeError, ValueError) as error:
        raise CardError(
            f"bound client source yields no lifecycle: {error}") from error
    require(isinstance(lifecycle, dict) and lifecycle.get("status", "").startswith(
                "PASS:"),
            "bound client source yielded an empty lifecycle projection")
    return lifecycle


def validate_lifecycle_view(value: dict[str, Any]) -> None:
    configure_card()
    canonical_source = CANONICAL_CLIENT_SOURCE.read_text(encoding="utf-8")
    derived = derive_bound_client_lifecycle(canonical_source)
    canonical_binding = bind(CANONICAL_CLIENT_SOURCE)
    provenance = value["lifecycle_provenance"]
    require(value["lifecycle_projection_status"] ==
                "PASS: CLIENT LIFECYCLE DERIVED FROM BOUND SOURCE"
            and value["lifecycle_successor_authority"] ==
                lifecycle_successor_authority()
            and provenance["canonical_source"] == canonical_binding
            and provenance["materialized_source"]["bytes"] ==
                canonical_binding["bytes"]
            and provenance["materialized_source"]["sha256"] ==
                canonical_binding["sha256"]
            and value["lifecycle"] == derived
            and value["geometry"]["bytes"] == EXTENT,
            "client lifecycle projection is missing, divergent or unbound")


def lifecycle_projection() -> None:
    require(not LIFECYCLE_VIEW.exists() and not LIFECYCLE_VIEW_REPORT.exists()
            and load(RESUME_RED)["status"] ==
                "FINAL RED: SUCCESSOR PLANE OMITTED DERIVED CLIENT LIFECYCLE",
            "Tier-1 lifecycle projection is one-shot")
    configure_card()
    materialized = bind(CLIENT_SOURCE)
    canonical_binding = bind(CANONICAL_CLIENT_SOURCE)
    require(materialized["bytes"] == canonical_binding["bytes"]
            and materialized["sha256"] == canonical_binding["sha256"],
            "materialized client source differs from canonical bound source")
    source = CANONICAL_CLIENT_SOURCE.read_text(encoding="utf-8")
    lifecycle = derive_bound_client_lifecycle(source)
    value = deepcopy(load(PLANE_RECEIPT))
    value.update({
        "lifecycle_projection_status":
            "PASS: CLIENT LIFECYCLE DERIVED FROM BOUND SOURCE",
        "lifecycle_successor_authority": lifecycle_successor_authority(),
        "lifecycle_predecessor_red": bind(RESUME_RED),
        "lifecycle_provenance": {"canonical_source": canonical_binding,
            "materialized_source": materialized,
            "derivation": "living validate_client_source over exact source bytes"},
        "lifecycle": lifecycle,
    })
    LIFECYCLE_VIEW.write_bytes(canonical(value))
    validate_lifecycle_view(value)
    mutations = []
    for name, mutate in (
        ("lifecycle-missing", lambda row: row.pop("lifecycle")),
        ("lifecycle-divergent", lambda row: row["lifecycle"].update(
            status="PASS: DIFFERENT LIFECYCLE")),
    ):
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate_lifecycle_view(trial)
        except (CardError, RuntimeError, KeyError, TypeError, ValueError):
            mutations.append(name)
    try:
        derive_bound_client_lifecycle("")
    except (CardError, RuntimeError, KeyError, TypeError, ValueError):
        mutations.append("bound-source-has-no-lifecycle")
    require(mutations == ["lifecycle-missing", "lifecycle-divergent",
                          "bound-source-has-no-lifecycle"],
            "client lifecycle projection mutation survived")
    value["lifecycle_mutations_rejected"] = mutations
    LIFECYCLE_VIEW.write_bytes(canonical(value))
    LIFECYCLE_VIEW_REPORT.write_text(f"""# v2.0 Tier-1 client Lifecycle projection

Status: **{value['lifecycle_projection_status']}**.

The successor qualification view derives its Lifecycle by executing the living
client validator over the exact tracked source
`{canonical_binding['path']}`.  The materialized source consumed by the
candidate is byte-identical ({canonical_binding['bytes']} bytes, SHA
`{canonical_binding['sha256']}`).  Provenance for both identities travels in
the view; no Lifecycle value is entered by hand.

Three sharp mutations fall: missing Lifecycle, divergent Lifecycle, and a
bound source from which no Lifecycle can be derived.  The last case fails
closed rather than manufacturing an empty/default projection.  No WPLTO,
product link, Scope or Acceptance ran during this conversion.
""", encoding="utf-8")
    print("v2.0 Tier-1 product: LIFECYCLE PROJECTION PASS mutations=3")


def check_lifecycle_projection() -> None:
    value = load(LIFECYCLE_VIEW)
    validate_lifecycle_view(value)
    require(value["lifecycle_mutations_rejected"] == [
                "lifecycle-missing", "lifecycle-divergent",
                "bound-source-has-no-lifecycle"]
            and LIFECYCLE_VIEW_REPORT.is_file(),
            "Tier-1 lifecycle projection receipt drift")
    print("v2.0 Tier-1 product: LIFECYCLE PROJECTION CHECK PASS mutations=3")


def check() -> None:
    validate(load(RECEIPT))
    print("v2.0 Tier-1 product: CHECK PASS silent=110")


def contract_semantic_delta(before: dict[str, Any],
                            after: dict[str, Any]) -> list[dict[str, Any]]:
    old_rows = {row["name"]: row for row in before["rows"]}
    new_rows = {row["name"]: row for row in after["rows"]}
    require(old_rows.keys() == new_rows.keys(),
            "Tier-1 contract population changed during promotion")
    changed = []
    for name in old_rows:
        for domain in AUDIT.DOMAINS:
            old = AUDIT.semantic_cell(old_rows[name]["cells"][domain])
            new = AUDIT.semantic_cell(new_rows[name]["cells"][domain])
            if old != new:
                changed.append({"name": name, "domain": domain,
                    "before": old, "after": new})
    return changed


def require_promoted_contract(durable: Any,
                              measured: dict[str, Any]) -> None:
    require(isinstance(durable, dict),
            "Tier-1 durable contract authority is missing")
    require(canonical(durable) == canonical(measured),
            "Tier-1 durable contract authority is stale or divergent")
    require(durable["counts"] == {"error-raised": 545,
                "documented-permissive": 179, "silently-wrong": 110},
            "Tier-1 durable contract counts are not the measured successor")


def derive_contract_authority_closure() -> dict[str, Any]:
    predecessor = PRICE.domain_projection(PRICE.BASE_MANIFEST, PRICE.BASE_BLOB)
    measured = load(MEASURED_CONTRACT)
    durable_raw = subprocess.run(["git", "show",
        f"{CONTRACT_AUTHORITY_EVIDENCE_ERA}:"
        "config/public-surface-domain-contract.json"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    durable = json.loads(durable_raw)
    require_promoted_contract(durable, measured)
    # The predecessor is the sealed v1.9 execution world.  The live domain
    # executor now names the v2.0 release receipt, which is correct for new
    # measurements but must not rewrite this historical projection.  Restore
    # the profile identity from the closure's own evidence era before hashing
    # the predecessor; target-visible rows are still freshly re-executed.
    predecessor["product_profile"] = deepcopy(durable["product_profile"])
    changed = contract_semantic_delta(predecessor, measured)
    classification_changes = [row for row in changed
        if row["before"]["classification"] != row["after"]["classification"]]
    error_priority_changes = [row for row in changed
        if row["before"]["classification"] ==
           row["after"]["classification"] == "error-raised"
        and row["before"].get("error") != row["after"].get("error")]
    require(len(changed) == 65 and len(classification_changes) == 62
            and len(error_priority_changes) == 3
            and {row["name"] for row in changed} <= set(PRICE.TIER1)
            and all(row["after"]["classification"] == "error-raised"
                    for row in classification_changes),
            "Tier-1 durable contract semantic delta is not the qualified tier")
    mutations = []
    for name, trial in (
        ("durable-authority-missing", None),
        ("durable-authority-stale", predecessor),
        ("durable-authority-divergent", deepcopy(durable)),
    ):
        if isinstance(trial, dict) and name.endswith("divergent"):
            row = next(item for item in trial["rows"]
                       if item["name"] == changed[0]["name"])
            row["cells"][changed[0]["domain"]] = deepcopy(
                next(item for item in predecessor["rows"]
                     if item["name"] == changed[0]["name"])
                ["cells"][changed[0]["domain"]])
        try:
            require_promoted_contract(trial, measured)
        except (CardError, KeyError, TypeError, ValueError):
            mutations.append(name)
    require(mutations == ["durable-authority-missing",
                          "durable-authority-stale",
                          "durable-authority-divergent"],
            "Tier-1 stale-derived-index mutation survived")
    comfort_driver = ROOT / "tools/host-lisp/c2_v200_comfort_return_media.py"
    comfort_domain = subprocess.run(["git", "show",
        "0e846eb0:config/public-surface-domain-contract.json"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    return {"format": FORMAT + "-contract-authority-closure",
        "recorded_on": "2026-09-01",
        "status": "PASS: TIER-1 MEASUREMENT PROMOTED TO DURABLE CONTRACT",
        "predecessor": {
            "derivation": [bind(PRICE.BASE_MANIFEST), bind(PRICE.BASE_BLOB)],
            "counts": predecessor["counts"],
            "stable_projection_sha256": hashlib.sha256(canonical(
                AUDIT.stable_projection(predecessor))).hexdigest()},
        "successor_measurement": bind(MEASURED_CONTRACT),
        "durable_authority": {
            "path": DURABLE_CONTRACT.relative_to(ROOT).as_posix(),
            "evidence_era": CONTRACT_AUTHORITY_EVIDENCE_ERA,
            "bytes": len(durable_raw),
            "sha256": hashlib.sha256(durable_raw).hexdigest()},
        "product_card": bind(RECEIPT),
        "successor_counts": durable["counts"],
        "semantic_delta": {"changed_cells": len(changed),
            "classification_changes": len(classification_changes),
            "error_priority_changes": len(error_priority_changes),
            "changed_names": sorted({row["name"] for row in changed}),
            "members_outside_Tier_1": sorted(
                {row["name"] for row in changed} - set(PRICE.TIER1))},
        "mutations_rejected": mutations,
        "historical_consumer_conversions": [{
            "consumer": "v2.0 Comfort return media/session",
            "driver": bind(comfort_driver), "evidence_era": "0e846eb0",
            "sealed_contract_sha256": hashlib.sha256(comfort_domain).hexdigest(),
            "living_contract_sha256_at_Tier_1":
                hashlib.sha256(durable_raw).hexdigest(),
            "anti_mixing_mutation": "domain-authority-crosses-evidence-era"}],
        "rule": ("the living public contract equals the freshly measured "
                 "qualified successor; historical pricing derives its "
                 "predecessor from sealed artifacts; this closure itself is "
                 "checked in its Tier-1 evidence era")}


def record_contract_authority_closure() -> None:
    value = derive_contract_authority_closure()
    CONTRACT_AUTHORITY_RECEIPT.write_bytes(canonical(value))
    CONTRACT_AUTHORITY_REPORT.write_text(f"""# v2.0 Tier-1 contract authority closure

Status: **{value['status']}**

The durable public-surface contract now equals the freshly executed Tier-1
successor measurement byte for byte: **545 error-raised / 179 documented
permissive / 110 silently wrong** over the unchanged 139-by-6 population.
Exactly **62 classifications** move from silently wrong to error-raised.  Three
already-red cells additionally sharpen their error identity from `DirMiss` to
`TypeError`; all 65 target-semantic changes stay inside Tier 1.

The historical price no longer reads this living index as its predecessor; it
derives the 483/179/172 world from the sealed v1.9 manifest and blob.  Missing,
stale and divergent durable authorities all fail.  No WPLTO, product link,
Scope, Acceptance, medium or device contact occurs in this closure.

The full-source run exposed one historical consumer: the sealed v2.0 Comfort
media/session used the same path as a live authority.  It now reads the domain
table from its evidence era; substituting the living Tier-1 table falls as an
explicit anti-mixing mutation.
""", encoding="utf-8")
    print("v2.0 Tier-1 contract authority: RECORD PASS silent=110")


def check_contract_authority_closure() -> None:
    require(CONTRACT_AUTHORITY_RECEIPT.is_file()
            and CONTRACT_AUTHORITY_RECEIPT.read_bytes() ==
                canonical(derive_contract_authority_closure())
            and CONTRACT_AUTHORITY_REPORT.is_file(),
            "Tier-1 durable contract authority closure drift")
    print("v2.0 Tier-1 contract authority: CHECK PASS silent=110 mutations=3")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "check-preflight",
        "record-prelink-red",
        "record-prelink-red-2",
        "record-postlink-red", "check-postlink-red",
        "convert-output-root", "check-output-root-conversion",
        "record-resume-red", "check-resume-red",
        "project-lifecycle", "check-lifecycle-projection",
        "record-inherited-final-gate-conversions",
        "check-inherited-final-gate-conversions",
        "record-acceptance-freight-conversion",
        "check-acceptance-freight-conversion",
        "record-contract-authority-closure",
        "check-contract-authority-closure",
        "build", "resume", "check", "selftest",
        "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    if action == "preflight":
        preflight()
    elif action == "check-preflight":
        check_preflight()
    elif action == "record-prelink-red":
        record_prelink_red()
    elif action == "record-prelink-red-2":
        record_prelink_red_2()
    elif action == "record-postlink-red":
        record_postlink_red()
    elif action == "check-postlink-red":
        check_postlink_red()
    elif action == "convert-output-root":
        output_root_conversion()
    elif action == "check-output-root-conversion":
        check_output_root_conversion()
    elif action == "record-resume-red":
        record_resume_red()
    elif action == "check-resume-red":
        check_resume_red()
    elif action == "project-lifecycle":
        lifecycle_projection()
    elif action == "check-lifecycle-projection":
        check_lifecycle_projection()
    elif action == "record-inherited-final-gate-conversions":
        inherited_final_gate_conversions()
    elif action == "check-inherited-final-gate-conversions":
        check_inherited_final_gate_conversions()
    elif action == "record-acceptance-freight-conversion":
        record_acceptance_freight_conversion()
    elif action == "check-acceptance-freight-conversion":
        check_acceptance_freight_conversion()
    elif action == "record-contract-authority-closure":
        record_contract_authority_closure()
    elif action == "check-contract-authority-closure":
        check_contract_authority_closure()
    elif action == "build":
        build()
    elif action == "resume":
        resume()
    elif action == "check":
        check()
    elif action == "selftest":
        selftest()
    else:
        child(action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"v2.0 Tier-1 product: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
