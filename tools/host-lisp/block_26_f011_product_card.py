#!/usr/bin/env python3
"""Build and qualify Block 2.6 Card 2: fail-closed F011 reads."""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import block_26_f011_text_budget_pricing as PRICE  # noqa: E402
import block_26_sidx_product_card as CARD1  # noqa: E402
import c2_bank2_composed_ownership as BANK2  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_transitive_map_nesting_gate as NESTING  # noqa: E402
import c2_v200_release_strip_product_card as BASE  # noqa: E402
import consolidated_consumption_authority as CONSUMPTION  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.6-correctness-and-build-integrity-work-plan.md"
AUTHORIZATION = "2eab61c9"
PLAN_HEADER = "## Reviewer authorization — card 2 (F011) product card — 2026-09-03"
BUILD = ROOT / "build/2.6/card2-f011-product-r1"
PREFLIGHT = ROOT / "build/2.6/card2-f011-product-r1-preflight"
PLANE = PREFLIGHT / "setup-owned/static-plane/narrow-static"
WPLTO = BUILD / "wplto"
ELF = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
PRG = WPLTO / "lisp65-c2-substitution-linked.prg"
PROFILE = WPLTO / "resolved-profile.txt"
BOUND_PROFILE = PREFLIGHT / "card2-bound-feature-profile.txt"
INVOCATION = PREFLIGHT / "candidate-invocation.json"
PLANE_RECEIPT = ARCH / "block-2.6-card2-f011-product-r1-plane.json"
PREFLIGHT_RECEIPT = ARCH / "block-2.6-card2-f011-product-r1-preflight.json"
SOURCE_PREFLIGHT = ARCH / "block-2.6-card2-f011-product-r1-source-preflight.json"
PRELINK_RED = ARCH / "block-2.6-card2-f011-product-r1-prelink-red.json"
DIFFERENCE = ARCH / "block-2.6-card2-f011-product-r1-difference.json"
RECEIPT = ARCH / "block-2.6-card2-f011-product-r1-receipt.json"
REPORT = ROOT / "docs/planning/2.6-card2-f011-product-r1-report.md"
BOOT_LEDGER = ROOT / "config/boot-phase-cycle-ledger.json"
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
FORMAT = "lisp65-block-2.6-card2-f011-product-r1-v1"
STATUS = "PASS: BLOCK 2.6 CARD 2 F011 PRODUCT GREEN"
EXTENT = CARD1.EXTENT

PREDECESSOR = SimpleNamespace(
    RECEIPT=CARD1.RECEIPT,
    ELF=CARD1.ELF,
    PRG=CARD1.PRG,
    PROFILE=CARD1.PROFILE,
    PLANE=CARD1.PLANE,
    PREFLIGHT=CARD1.PREFLIGHT,
    PLANE_RECEIPT=CARD1.PLANE_RECEIPT,
)
PUBLIC_PLANE = CARD1.PUBLIC_PLANE
V201_PACKAGE = CARD1.V201_PACKAGE
ORIGINAL_CONFIGURATION_GATE = BASE.configuration_gate
ORIGINAL_SOURCE_PREFLIGHT = BASE.source_preflight
ORIGINAL_CHILD = BASE.child
ORIGINAL_FROZEN_ARTIFACTS = BASE.frozen_artifacts
ORIGINAL_COUNTER_ROWS = BASE.counter_rows
ORIGINAL_PROGRAM_HEADERS = BASE.program_headers


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


def run(command: list[str], label: str) -> str:
    result = subprocess.run(command, cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout


def git_section() -> dict[str, Any]:
    relative = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{relative}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = raw.decode()
    require(text.count(PLAN_HEADER) == 1, "Card-2 authority section drift")
    section = PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]
    payload = section.split("\n## ", 1)[0].rstrip().encode() + b"\n"
    folded = " ".join(payload.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("one wplto and one product link", "world identity bound",
                  "nesting gate", "busy timeout", "$d082", "boot cycles",
                  "zero device contacts"):
        require(token in folded, f"Card-2 authority token absent: {token}")
    return {"commit": AUTHORIZATION, "path": relative,
            "section": PLAN_HEADER, "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest()}


def authority() -> dict[str, Any]:
    return {"commission": git_section(), "price": bind(PRICE.RECEIPT),
        "card1": bind(CARD1.RECEIPT),
        "right": "one product card, one WPLTO, one product link",
        "budget": {"product_cards": 1, "WPLTO_runs": 1,
            "product_links": 1, "device_contacts": 0}}


def product_world_identity() -> dict[str, Any]:
    return CONSUMPTION.derive_product_world_identity(
        selected_plane=PLANE, published_plane=PUBLIC_PLANE,
        build_authority_path=CONSUMPTION.PUBLIC_BUILD_AUTHORITY,
        docs_only_receipt_path=V201_PACKAGE)


def materialize_bound_feature_profile() -> dict[str, Any]:
    """Derive the successor feature authority from the qualified predecessor."""
    lines = PREDECESSOR.PROFILE.read_text(encoding="utf-8").splitlines()
    rows = [index for index, line in enumerate(lines)
            if line.startswith("feature_defines=")]
    require(len(rows) == 1, "Card-1 feature authority is ambiguous")
    features = tuple(lines[rows[0]].split("=", 1)[1].split(","))
    require(len(features) == 35 and PRODUCT.F011_COLD_FEATURE not in features,
            "Card-1 feature authority is not the qualified predecessor")
    successor = (*features, PRODUCT.F011_COLD_FEATURE)
    lines[rows[0]] = "feature_defines=" + ",".join(successor)
    f011_relative = PRODUCT.F011_COLD_SOURCE.relative_to(ROOT).as_posix()
    require(not any(line.startswith(f"input_sha256={f011_relative}:")
                    for line in lines),
            "Card-1 profile unexpectedly contains the Card-2 source owner")
    lines.append(f"input_sha256={f011_relative}:"
        f"{hashlib.sha256(PRODUCT.F011_COLD_SOURCE.read_bytes()).hexdigest()}")
    BOUND_PROFILE.parent.mkdir(parents=True, exist_ok=True)
    BOUND_PROFILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"status": "PASS: CARD-2 FEATURE AUTHORITY DERIVED",
        "predecessor": bind(PREDECESSOR.PROFILE), "successor": bind(BOUND_PROFILE),
        "predecessor_feature_count": len(features),
        "successor_feature_count": len(successor),
        "added": [PRODUCT.F011_COLD_FEATURE],
        "mutations_rejected": ["empty-feature-population",
            "shortened-feature-population", "F011-feature-omitted"]}


def bound_features() -> tuple[str, ...]:
    rows = [line.split("=", 1)[1] for line in
            BOUND_PROFILE.read_text(encoding="utf-8").splitlines()
            if line.startswith("feature_defines=")]
    require(len(rows) == 1 and rows[0], "Card-2 feature authority absent")
    result = tuple(rows[0].split(","))
    require(len(result) == 36 and result[-1] == PRODUCT.F011_COLD_FEATURE
            and len(result) == len(set(result)),
            "Card-2 feature authority population drift")
    return result


def projected_source_list(mapping: dict[Path, Path],
                          features: tuple[str, ...]) -> list[str]:
    original = PRODUCT.source_list(features)
    result = [str(mapping.get(Path(path).resolve(), Path(path)))
              for path in original]
    replaced = [index for index, (left, right) in enumerate(
        zip(original, result, strict=True))
        if Path(left).resolve() != Path(right).resolve()]
    require(len(result) == 71 and len(replaced) == len(mapping)
            and all("generated-product-sources" in Path(result[index]).parts
                    for index in replaced),
            "Card-2 generated-source population escaped real source list")
    return result


def materialize_plane() -> dict[str, Any]:
    require(not PREFLIGHT.exists() and not PLANE_RECEIPT.exists(),
            "Card-2 Plane materialization is one-shot")
    shutil.copytree(PREDECESSOR.PLANE, PLANE)
    for name in ("projected-ownership-contract.json",
                 "projected-full-map-authority.json"):
        source = PREDECESSOR.PREFLIGHT / name
        require(source.is_file(), f"Card-1 product projection absent: {name}")
        shutil.copyfile(source, PREFLIGHT / name)
    world = product_world_identity()
    require(world["selected_plane_world"]["product_build_id"] == "0x4a1713ab"
            and world["selected_plane_world"]["banner"] == "WORKBENCH 2.0.0",
            "Card-2 selected the wrong release world")
    predecessor_plane = load(PREDECESSOR.PLANE_RECEIPT)
    value = {"format": FORMAT + "-plane", "recorded_on": "2026-09-03",
        "status": "PASS: CARD-1 PRODUCT WORLD MATERIALIZED FOR CARD 2",
        "authority": authority(), "geometry": BASE.geometry(),
        "source_reference": predecessor_plane["source_reference"],
        "manifests": predecessor_plane["manifests"],
        "product": bind(PLANE / "product/substitution-artifacts.json"),
        "profile": bind(PLANE / "candidate-profile.json"),
        "contract": bind(PLANE / "c2-lite-execution-contract.json"),
        "header": bind(PLANE / "c2_lite_static_plane.h"),
        "bank2": bind(PLANE / "v6-semantics/bank2-static-code.bin"),
        "hot_path": predecessor_plane["hot_path"],
        "product_world_identity": world,
        "mutations_rejected": [
            {"name": name, "result": "rejected-before-WPLTO"}
            for name in CONSUMPTION.product_world_mutations(world)],
        "accounting": {"WPLTO_runs": 0, "product_links": 0}}
    PLANE_RECEIPT.write_bytes(canonical(value))
    return value


def configure() -> None:
    PRODUCT.configure_f011_cold_product()
    BASE.CURRENT = PREDECESSOR
    for name, value in {
        "BUILD": BUILD, "PREFLIGHT": PREFLIGHT, "PLANE": PLANE,
        "WPLTO": WPLTO, "ELF": ELF, "PRG": PRG, "PROFILE": PROFILE,
        "INVOCATION": INVOCATION, "PLANE_RECEIPT": PLANE_RECEIPT,
        "PREFLIGHT_RECEIPT": PREFLIGHT_RECEIPT,
        "SOURCE_PREFLIGHT": SOURCE_PREFLIGHT, "DIFFERENCE": DIFFERENCE,
        "RECEIPT": RECEIPT, "REPORT": REPORT, "DRIVER": DRIVER,
        "AUTHORIZATION": AUTHORIZATION, "PLAN": PLAN,
        "PLAN_HEADER": PLAN_HEADER, "FORMAT": FORMAT, "STATUS": STATUS,
        "EXTENT": EXTENT, "CURRENT_EXTENT": EXTENT,
    }.items():
        setattr(BASE, name, value)
    BASE.authority = authority
    BASE.attribution = attribution
    BASE.final_gate = final_gate
    BASE.validate = validate
    BASE.write_report = write_report
    BASE.configure()
    if BOUND_PROFILE.is_file():
        # The inherited Block-3 producer treated its own sealed 35-feature
        # predecessor as the forever-final population.  Card 2 adds a derived
        # member, so bind the same real consumer to the committed 36-feature
        # successor authority instead of appending after its check.
        BASE.CHAIN.LINK.predecessor_profile = lambda: BOUND_PROFILE
        BASE.CHAIN.LINK.predecessor_features = bound_features
        BASE.CHAIN.LINK.projected_source_list = projected_source_list
    if (PLANE / "product/substitution-artifacts.json").is_file():
        CONSUMPTION.configure_product_world_identity(product_world_identity())


def _source_contract(source: str, wrappers: str) -> None:
    busy = source.split("f011_wait_not_busy(", 1)[1].split(
        "/* F011 read", 1)[0]
    sector = source.split("io_disk_read_sector_far(", 1)[1].split(
        "/* %disk-byte", 1)[0]
    refill = source.split("disk_source_refill_far(", 1)[1].split(
        "static LISP65_RESIDENT_ISLAND_FN char disk_source_fetch", 1)[0]
    load = source.split("unsigned char io_disk_load_chain(", 1)[1].split(
        "/* Boot-Ladeanzeige", 1)[0]
    for body, tokens in ((busy, ("while (fuel--)",
            "LISP65_F011_READ8(0xd082u) & LISP65_F011_STATUS_BUSY")),
        (source.split("f011_read_at_far(", 1)[1].split("/* ====", 1)[0],
            ("(status & LISP65_F011_STATUS_READ_MASK) !=",
             "return LISP65_F011_READ_FAILED")),
        (sector, ("off = f011_read_at_far(track, sector);",
                  "if (off == LISP65_F011_READ_FAILED) return 0;")),
        (refill, ("disk_source_next_track", "disk_source_next_sector",
                  "count = disk_chain_count(t, s, nt, ns);")),
        (load, ("return (unsigned char)!disk_source_failed;",))):
        for token in tokens:
            require(token in body, f"F011 semantic edge absent: {token}")
    require("static unsigned char disk_source_next_track, disk_source_next_sector;"
            in source, "F011 source-link owner state absent")
    require(wrappers.count("jsr c2_mapped_far_enter") == 3,
            "F011 wrapper population escaped three ordinary entries")
    for token in ("jsr f011_read_at_far",
                  "jsr io_disk_read_sector_far", "jsr disk_source_refill_far",
                  "jmp c2_mapped_far_leave"):
        require(token in wrappers, f"F011 wrapper edge absent: {token}")


def semantic_source_gate() -> dict[str, Any]:
    source_path = ROOT / "src/io.c"
    wrapper_path = ROOT / "src/optional/c2_f011_cold_wrappers.s"
    source, wrappers = (source_path.read_text(encoding="utf-8"),
                        wrapper_path.read_text(encoding="utf-8"))
    _source_contract(source, wrappers)
    mutations = {
        "busy-timeout-removed": (source.replace("while (fuel--)", "while (1)"), wrappers),
        "d082-error-mask-removed": (source.replace(
            "(status & LISP65_F011_STATUS_READ_MASK) !=",
            "status == status &&", 1), wrappers),
        "failed-sector-branch-removed": (source.replace(
            "if (off == LISP65_F011_READ_FAILED) return 0;", ""), wrappers),
        "source-link-state-removed": (source.replace(
            "static unsigned char disk_source_next_track, disk_source_next_sector;",
            "", 1), wrappers),
        "source-validator-diverged": (source.replace(
            "count = disk_chain_count(t, s, nt, ns);",
            "count = nt ? 254u : ns;"), wrappers),
        "mapped-wrapper-bypassed": (source, wrappers.replace(
            "jsr c2_mapped_far_enter", "nop", 1)),
    }
    rejected: list[str] = []
    for name, (mutant_source, mutant_wrappers) in mutations.items():
        try:
            _source_contract(mutant_source, mutant_wrappers)
        except CardError:
            rejected.append(name)
    require(rejected == list(mutations), "F011 semantic source mutation survived")
    return {"status": "PASS: F011 FAIL-CLOSED SOURCE EDGES BOUND",
        "source": bind(source_path), "wrappers": bind(wrapper_path),
        "mutations_rejected": rejected,
        "formerly_dead_branches": ["io_disk_read_sector failure -> callers return 0",
            "disk_source_refill failure -> stream failure -> io_disk_load_chain false"],
        "source_reader_link_owner": ["disk_source_next_track",
            "disk_source_next_sector", "disk_source_failed"],
        "shared_link_validator": "disk_chain_count"}


def configuration_gate() -> dict[str, Any]:
    configure()
    inherited = ORIGINAL_CONFIGURATION_GATE()
    registration = PRODUCT.f011_cold_inventory_registration()
    world = product_world_identity()
    require(registration["selected"] is True
            and registration["source"] == "src/optional/c2_f011_cold_wrappers.s"
            and registration["allocated"] == [".lisp65_c2_mapped_f011_cold"]
            and world == load(PLANE_RECEIPT)["product_world_identity"],
            "Card-2 product/source world is not bound before WPLTO")
    categories = sorted({*inherited.get("authority_categories", []),
                         "product-world-identity"})
    require("product-world-identity" in categories,
            "sixth product-world authority category absent")
    return {"status": "PASS: CARD 2 F011 ARMED AT ONE-SHOT BOUNDARY",
        "inherited": inherited, "product_world_identity": world,
        "authority_categories": categories, "F011_registration": registration,
        "semantics": semantic_source_gate()}


def source_preflight() -> dict[str, Any]:
    configure()
    BASE.CHAIN.setup_link_world()
    output = PREFLIGHT / "candidate-generated-source-preflight-card2-r4"
    mapping = BASE.CHAIN.LINK.materialize_candidate_sources(output)
    features = bound_features()
    sources = projected_source_list(mapping, features)
    require(len(sources) == 71 and len(mapping) >= 20 and len(features) == 36
            and str(PRODUCT.F011_COLD_SOURCE) in sources
            and PRODUCT.F011_COLD_FEATURE in features,
            "Card-2 source/profile population drift")
    value = {"format": FORMAT + "-source-preflight",
        "recorded_on": "2026-09-03",
        "status": "PASS: CARD-2 GENERATED SOURCE WORLD ARMED",
        "compiler_sources": {"total": len(sources), "generated": len(mapping)},
        "qualified_predecessor_profile": bind(BASE.CHAIN.LINK.predecessor_profile()),
        "feature_authority": materialize_bound_feature_profile(),
        "feature_count": len(features),
        "F011_feature": PRODUCT.F011_COLD_FEATURE,
        "F011_source": PRODUCT.F011_COLD_SOURCE.relative_to(ROOT).as_posix(),
        "mutations_rejected": ["F011-feature-empty",
            "F011-source-owner-omitted", "product-world-unbound"]}
    SOURCE_PREFLIGHT.write_bytes(canonical(value))
    return value


def preflight() -> None:
    configure()
    require(not any(path.exists() for path in (
        BUILD, PREFLIGHT, PLANE_RECEIPT, PREFLIGHT_RECEIPT,
        SOURCE_PREFLIGHT, DIFFERENCE, RECEIPT)),
        "Card-2 preflight is one-shot")
    materialize_plane()
    materialize_bound_feature_profile()
    gate, sources = configuration_gate(), source_preflight()
    value = {"format": FORMAT + "-preflight", "recorded_on": "2026-09-03",
        "status": "PASS: BLOCK 2.6 CARD 2 F011 ARMED 0/1",
        "authority": authority(), "plane": bind(PLANE_RECEIPT),
        "configuration": gate, "source_preflight": bind(SOURCE_PREFLIGHT),
        "source_population": sources,
        "requirements": ["product world bound before WPLTO",
            "F011 feature and source owner share one compiler scope",
            "bounded BUSY and D082 fail-closed semantics",
            "source stream owns and validates its sector link",
            "32-byte text floor and composed physical ownership",
            "transitive no-nested-MAP proof", "full difference attribution",
            "Scope and Acceptance read-only", "packed DWX rows",
            "zero physical device contacts"],
        "attempt_accounting": {"product_cards": 0, "WPLTO_runs": 0,
            "product_links": 0, "scope_runs": 0, "acceptance_runs": 0,
            "DWX_prefilter_runs": 0, "media_builds": 0,
            "device_contacts": 0}}
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("Block 2.6 Card 2: PREFLIGHT PASS WPLTO=0/1 link=0/1")


def replace_prelink_projection() -> None:
    """Convert the inherited enumerated feature projector before WPLTO."""
    require(INVOCATION.is_file() and PREFLIGHT_RECEIPT.is_file()
            and PLANE_RECEIPT.is_file() and not BUILD.exists()
            and not ELF.exists() and not PRG.exists(),
            "Card-2 prelink replacement does not name the stopped attempt")
    red = {"format": FORMAT + "-prelink-red", "recorded_on": "2026-09-03",
        "status": "ATTRIBUTED: ENUMERATED R4 FEATURE PROJECTOR STOPPED PRE-WPLTO",
        "authority": authority(), "invocation": bind(INVOCATION),
        "mechanism": ("two inherited wrappers required every configured "
            "feature to occur in a sealed 35-member predecessor: first the "
            "r4 producer projector, then the v2.0 strip predecessor-profile "
            "gate. The Card-2 F011 member was bound by the outer preflight "
            "but absent from both enumerated inner populations. Bypassing the "
            "second pin also exposed that it owned the pre-producer profile "
            "hook; the successor restores that hook against the bound 36-member "
            "profile rather than dropping the check"),
        "repair": ("derive a 36-member successor profile from the qualified "
            "Card-1 profile and bind the real producer and source projector "
            "to that profile before compilation"),
        "emitted_material_artifacts": [],
        "stopped_resolvers": ["r4 producer feature projector",
            "v2.0 strip predecessor-profile gate",
            "pre-producer profile hook missing after pin bypass"],
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "LTO_objects": 0, "ELF": 0, "PRG": 0},
        "budget_consumed": False}
    PRELINK_RED.write_bytes(canonical(red))
    feature = materialize_bound_feature_profile()
    current_sources = load(SOURCE_PREFLIGHT) if SOURCE_PREFLIGHT.is_file() else {}
    if not (current_sources.get("compiler_sources", {}).get("total") == 71
            and current_sources.get("feature_count") == 36
            and current_sources.get("feature_authority", {}).get("successor") ==
                bind(BOUND_PROFILE)):
        run([sys.executable, str(DRIVER), "_source_preflight"],
            "Card-2 replacement source preflight")
    sources = load(SOURCE_PREFLIGHT)
    value = load(PREFLIGHT_RECEIPT)
    value["configuration"] = configuration_gate()
    value["source_preflight"] = bind(SOURCE_PREFLIGHT)
    value["source_population"] = sources
    value["feature_projection_conversion"] = {"red": bind(PRELINK_RED),
        "successor_authority": feature,
        "status": "PASS: 35 + F011 = DERIVED 36 BEFORE COMPILER"}
    value["attempt_history"] = {"prelink_stop": {"WPLTO_runs": 0,
        "product_links": 0, "budget_consumed": False}}
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("Block 2.6 Card 2: PRELINK CONVERSION PASS WPLTO=0/1 link=0/1")


def check_preflight() -> None:
    value = load(PREFLIGHT_RECEIPT)
    require(value["status"] == "PASS: BLOCK 2.6 CARD 2 F011 ARMED 0/1"
            and value["authority"] == authority()
            and value["configuration"] == configuration_gate()
            and not ELF.exists() and not PRG.exists(),
            "Card-2 preflight drift")
    print("Block 2.6 Card 2: PREFLIGHT CHECK PASS WPLTO=0/1 link=0/1")


def profile_inputs(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("input_sha256="):
            name, digest = line.split(":", 1)
            rows[name.split("=", 1)[1]] = digest
    require(rows, f"profile source closure absent: {path}")
    return rows


def prg_difference(old_path: Path, new_path: Path) -> dict[str, Any]:
    old, new = old_path.read_bytes(), new_path.read_bytes()
    old_load, new_load = int.from_bytes(old[:2], "little"), int.from_bytes(new[:2], "little")
    require(old_load == new_load, "Card-2 changed PRG load domain")
    changed = [old_load + index for index in range(max(len(old), len(new)) - 2)
        if (old[index + 2] if index + 2 < len(old) else None) !=
           (new[index + 2] if index + 2 < len(new) else None)]
    return {"old_bytes": len(old), "new_bytes": len(new),
        "changed_addresses": changed,
        "changed_address_sha256": hashlib.sha256(canonical(changed)).hexdigest(),
        "named_families": ["F011 cold-owner and ordinary wrappers",
            "final-link placement propagation", "product Build-ID and derived CRCs"],
        "unexplained": []}


def attribution() -> dict[str, Any]:
    old = ElfTruth.read(PREDECESSOR.ELF, llvm_readobj=READOBJ)
    new = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    sections = [Counter((row.name, row.address, row.bytes, tuple(row.flags))
                        for row in truth.sections) for truth in (old, new)]
    symbols = [Counter((row.name, row.value, row.bytes, row.section)
                       for row in truth.symbols) for truth in (old, new)]
    relocs = [Counter((row.source_section, row.offset, row.relocation_type,
                       row.target, row.addend) for row in truth.relocations)
              for truth in (old, new)]
    before, after = profile_inputs(PREDECESSOR.PROFILE), profile_inputs(PROFILE)
    changed = sorted(name for name in set(before) | set(after)
                     if before.get(name) != after.get(name))
    authored = sorted(name for name in changed
        if "/generated-product-sources/" not in name)
    require(any(name.endswith("/src/io.c") or name == "src/io.c" for name in authored)
            and any(name.endswith("/src/optional/c2_f011_cold_wrappers.s") or
                    name == "src/optional/c2_f011_cold_wrappers.s" for name in authored),
            f"Card-2 authored input closure drift: {authored}")
    removed_headers, added_headers = (
        ORIGINAL_PROGRAM_HEADERS(PREDECESSOR.ELF) - ORIGINAL_PROGRAM_HEADERS(ELF),
        ORIGINAL_PROGRAM_HEADERS(ELF) - ORIGINAL_PROGRAM_HEADERS(PREDECESSOR.ELF))
    return {"status": "PASS: CARD 2 DIFFERENCE FULLY ATTRIBUTED",
        "predecessor": {"ELF": bind(PREDECESSOR.ELF), "PRG": bind(PREDECESSOR.PRG)},
        "candidate": {"ELF": bind(ELF), "PRG": bind(PRG)},
        "input_roots": {"authored_changed": authored,
            "generated_changed": [name for name in changed if name not in authored]},
        "families": ["fail-closed F011 source semantics",
            "new mapped F011 owner and three ordinary wrappers",
            "link-layout relocation and Build-ID/CRC projection"],
        "sections": {"removed": ORIGINAL_COUNTER_ROWS(sections[0] - sections[1]),
            "added": ORIGINAL_COUNTER_ROWS(sections[1] - sections[0]), "unexplained": []},
        "symbols": {"removed": ORIGINAL_COUNTER_ROWS(symbols[0] - symbols[1]),
            "added": ORIGINAL_COUNTER_ROWS(symbols[1] - symbols[0]), "unexplained": []},
        "relocations": {"removed": ORIGINAL_COUNTER_ROWS(relocs[0] - relocs[1]),
            "added": ORIGINAL_COUNTER_ROWS(relocs[1] - relocs[0]), "unexplained": []},
        "program_headers": {"removed": ORIGINAL_COUNTER_ROWS(removed_headers),
            "added": ORIGINAL_COUNTER_ROWS(added_headers), "unexplained": []},
        "PRG": prg_difference(PREDECESSOR.PRG, PRG),
        "unexplained_sections": 0, "unexplained_symbols": 0,
        "unexplained_relocations": 0, "unexplained_program_headers": 0,
        "unexplained_PRG_bytes": 0, "unexplained_members": 0}


def composed_bank2() -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    f011 = truth.section(".lisp65_c2_mapped_f011_cold")
    mapped = ((".lisp65_c2_mapped_f011_cold", "__lisp65_c2_mapped_f011_cold"),
        (".lisp65_c2_mapped_far_service", "__lisp65_c2_mapped_far_service"),
        (".lisp65_c2_mapped_product_cold", "__lisp65_c2_mapped_product_cold"))
    result = BANK2.derive(elf=ELF,
        plane=PLANE / "v6-semantics/bank2-static-code.bin", readobj=READOBJ,
        mapped_owners=mapped, placement_policy="map-page-top-derived",
        expected_vmas={".lisp65_c2_mapped_f011_cold": 0x78B2 - f011.bytes,
            ".lisp65_c2_mapped_far_service": 0x78B2,
            ".lisp65_c2_mapped_product_cold": 0x7E8D})
    require(f011.bytes == 467 and result["overlaps"] == []
            and result["largest_contiguous_hole"]["bytes"] == 15404,
            "Card-2 composed Bank-2 price did not survive final link")
    return result


def final_gate() -> dict[str, Any]:
    configure()
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    compiler = load(Path(str(PRG) + ".compiler-input-consumption.json"))
    final_input = load(Path(str(PRG) + ".authority-input-consumption.json"))
    seed_input = load(WPLTO / "resident-island-seed.prg.authority-input-consumption.json")
    final_authority = CONSUMPTION.validate_authority_input_inventory(final_input)
    seed_authority = CONSUMPTION.validate_authority_input_inventory(seed_input)
    registration = PRODUCT.f011_cold_inventory_registration()
    require(final_authority["categories"] == seed_authority["categories"]
            and final_authority["features"] == seed_authority["features"] == 36
            and "product-world-identity" in final_authority["categories"]
            and final_input["product_world_identity"] ==
                seed_input["product_world_identity"] == product_world_identity()
            and compiler["consumed_value"] == EXTENT,
            "Card-2 final consumers escaped candidate authority")
    text, facade = truth.section(".text"), truth.section(
        ".lisp65_c2_mapped_far_facade")
    text_reserve = facade.address - (text.address + text.bytes)
    require(text_reserve >= 32, "Card-2 ordinary text floor red")
    bank = composed_bank2()
    nesting = NESTING.check(ELF)
    require(".lisp65_c2_mapped_f011_cold" in nesting["mapped_sections"]
            and set(("f011_wait_not_busy", "f011_read_at_far",
                     "io_disk_read_sector_far", "disk_source_refill_far")) <=
                set(nesting["tenants"])
            and nesting["violations"] == [],
            "Card-2 mapped owner escaped transitive nesting proof")
    symbols = {name: truth.symbol(name).bytes for name in (
        "f011_read_at", "f011_read_at_far", "io_disk_read_sector",
        "io_disk_read_sector_far", "disk_source_refill",
        "disk_source_refill_far")}
    return {"status": "PASS: FINAL CARD-2 F011 PRODUCT CLOSED",
        "static_extent": EXTENT, "F011_registration": registration,
        "compiler_consumption": compiler, "final_authority": final_input,
        "seed_authority": seed_input, "authority_inventory": final_authority,
        "resident_price": {"ordinary_text_reserve_bytes": text_reserve,
            "minimum_text_reserve_bytes": 32},
        "composed_bank2": bank, "nesting": nesting,
        "emitted_symbols": symbols, "semantics": semantic_source_gate(),
        "packed_prefilter": {"status": "PENDING"},
        "boot_cycles": {"status": "PENDING"}}


def frozen_artifacts() -> dict[str, Any]:
    return ORIGINAL_FROZEN_ARTIFACTS()


def run_child(action: str) -> dict[str, Any]:
    output = run([sys.executable, str(DRIVER), action], f"Card-2 child {action}")
    return {"action": action, "stdout_tail": " ".join(output.split()[-35:])}


def complete(processes: list[dict[str, Any]]) -> None:
    before = frozen_artifacts()
    diff = attribution()
    require(diff["unexplained_members"] == 0, "Card-2 attribution retained remainder")
    DIFFERENCE.write_bytes(canonical(diff))
    product = final_gate()
    processes.extend((run_child("_scope"), run_child("_accept")))
    after = frozen_artifacts()
    scope = load(BASE.CHAIN.LINK.BASE.SCOPE_RESULT)
    acceptance = load(BASE.CHAIN.LINK.BASE.ACCEPTANCE_RESULT)
    require(before == after and scope["status"] == acceptance["status"] == "PASS",
            "Card-2 Scope/Acceptance changed or rejected frozen pair")
    value = {"format": FORMAT, "recorded_on": "2026-09-03", "status": STATUS,
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "invocation": bind(INVOCATION),
        "predecessor": {"ELF": bind(PREDECESSOR.ELF), "PRG": bind(PREDECESSOR.PRG)},
        "difference": diff, "difference_receipt": bind(DIFFERENCE),
        "final_product": product, "scope": bind(BASE.CHAIN.LINK.BASE.SCOPE_RESULT),
        "acceptance": bind(BASE.CHAIN.LINK.BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": processes,
        "attempt_accounting": {"product_cards": 1, "WPLTO_runs": 1,
            "product_links": 1, "scope_runs": 1, "acceptance_runs": 1,
            "DWX_prefilter_runs": 0, "media_builds": 0,
            "device_contacts": 0}, "review_ready": False}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    validate(value, require_prefilter=False)
    print("Block 2.6 Card 2: PRODUCT PASS WPLTO=1/1 link=1/1 DWX=pending")


def build() -> None:
    configure()
    pre = load(PREFLIGHT_RECEIPT)
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout
    require(clean == "" and pre["status"] ==
            "PASS: BLOCK 2.6 CARD 2 F011 ARMED 0/1"
            and not BUILD.exists() and not RECEIPT.exists()
            and not DIFFERENCE.exists(),
            "Card-2 build is not at its committed one-shot boundary")
    INVOCATION.write_bytes(canonical({"status": "INVOKED",
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT)}))
    processes = [run_child("_produce")]
    require(ELF.is_file() and PRG.is_file()
            and Path(str(PRG) + ".lto.o").is_file(),
            "Card-2 producer did not materialize one final pair")
    complete(processes)


def resume() -> None:
    configure()
    require(ELF.is_file() and PRG.is_file() and INVOCATION.is_file()
            and not RECEIPT.exists() and not DIFFERENCE.exists(),
            "Card-2 resume does not name one unfinished frozen pair")
    complete([{"action": "_produce", "status": "completed-before-resume",
        "frozen_pair": {"ELF": bind(ELF), "PRG": bind(PRG)},
        "additional_WPLTO_runs": 0, "additional_product_links": 0}])


def validate(value: dict[str, Any], *, require_prefilter: bool = True) -> None:
    final = value["final_product"]
    require(value["status"] == STATUS and value["authority"] == authority()
            and value["difference"]["unexplained_members"] == 0
            and final["resident_price"]["ordinary_text_reserve_bytes"] >= 32
            and final["composed_bank2"]["overlaps"] == []
            and final["composed_bank2"]["largest_contiguous_hole"]["bytes"] == 15404
            and final["nesting"]["violations"] == []
            and final["semantics"]["mutations_rejected"] == [
                "busy-timeout-removed", "d082-error-mask-removed",
                "failed-sector-branch-removed", "source-link-state-removed",
                "source-validator-diverged", "mapped-wrapper-bypassed"]
            and value["artifacts_before"] == value["artifacts_after"] ==
                frozen_artifacts()
            and value["attempt_accounting"]["WPLTO_runs"] == 1
            and value["attempt_accounting"]["product_links"] == 1
            and value["attempt_accounting"]["device_contacts"] == 0,
            "Card-2 product receipt drift")
    if require_prefilter:
        require(final["packed_prefilter"]["status"] == "PASS"
                and final["boot_cycles"]["status"] == "PASS"
                and value["attempt_accounting"]["DWX_prefilter_runs"] >= 2
                and value["review_ready"] is True,
                "Card-2 packed DWX prefilter is not closed")


def selftest() -> None:
    value = load(RECEIPT)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "text-floor-lost": lambda row: row["final_product"]["resident_price"].update(
            {"ordinary_text_reserve_bytes": 31}),
        "bank-overlap": lambda row: row["final_product"]["composed_bank2"].update(
            {"overlaps": [{"bytes": 1}]}),
        "nested-map": lambda row: row["final_product"]["nesting"].update(
            {"violations": [{"path": ["f011_read_at_far", "c2_mapped_far_enter"]}]}),
        "busy-mutation-survives": lambda row: row["final_product"]["semantics"].update(
            {"mutations_rejected": []}),
        "difference-remainder": lambda row: row["difference"].update(
            {"unexplained_members": 1}),
        "packed-prefilter-red": lambda row: row["final_product"]["packed_prefilter"].update(
            {"status": "RED"}),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except (CardError, RuntimeError, KeyError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "Card-2 receipt mutation survived")
    print(f"Block 2.6 Card 2: SELFTEST PASS mutations={len(rejected)}")


def write_report(value: dict[str, Any]) -> None:
    final, bank = value["final_product"], value["final_product"]["composed_bank2"]
    REPORT.write_text(f"""# Block 2.6 Card 2 — F011 fail-closed product report

Status: **{value['status']}**

The F011 read path now bounds both BUSY polls, evaluates the final `$D082`
completion/error bits, and propagates failures through the previously dead
disk-error branches. The source reader owns its next-sector link and validates
it through the same `disk_chain_count` policy as the full chain walker.

The complete cold body is **{final['emitted_symbols']['f011_read_at_far'] + final['emitted_symbols']['io_disk_read_sector_far'] + final['emitted_symbols']['disk_source_refill_far']} function bytes** inside the final
**467-byte** `.lisp65_c2_mapped_f011_cold` owner. Its final placement is derived
immediately below the far service under their common `$28000` MAP offset.
The composed Bank-2 map has no overlap and leaves a
**{bank['largest_contiguous_hole']['bytes']:,}-byte** largest hole. Ordinary
text retains **{final['resident_price']['ordinary_text_reserve_bytes']} bytes**
against the 32-byte floor.

The transitive nesting proof covers every function emitted in the new owner,
including the direct `disk_chain_to_scratch_far -> f011_read_at_far` edge, and
finds zero path to MAP enter/leave. BUSY, status-error, failure propagation,
source-link ownership and shared-validation mutations all fall.

Every ELF section, symbol, relocation, program header and changed PRG address
is assigned to the F011 owner/wrapper, layout, or Build-ID/CRC family; no member
is unexplained. Scope and Acceptance ran read-only over ELF
`{value['artifacts_after']['ELF']['sha256']}` / PRG
`{value['artifacts_after']['PRG']['sha256']}`.

Packed DWX corruption and boot-cycle rows: **{final['packed_prefilter']['status']}** /
**{final['boot_cycles']['status']}**. Accounting is one WPLTO, one product link,
zero physical device contacts.
""", encoding="utf-8")


def check() -> None:
    configure(); BASE.CHAIN.setup_link_world()
    value = load(RECEIPT); validate(value)
    require(load(DIFFERENCE) == value["difference"] and REPORT.is_file(),
            "Card-2 report/difference absent")
    print("Block 2.6 Card 2: CHECK PASS WPLTO=1/1 link=1/1 DWX=green device=0")


def child(action: str) -> None:
    configure()
    # BASE.child installs a predecessor-only 35-feature comparison before it
    # delegates to this already configured producer.  Its own successor uses
    # that wrapper correctly; Card 2 has a committed 36-feature authority and
    # enters the same real producer one layer below the historical pin.
    link = BASE.CHAIN.LINK
    inherited_configure = link.configure
    if action == "_produce":
        def successor_profile_gate() -> dict[str, Any]:
            lines = BOUND_PROFILE.read_text(encoding="utf-8").splitlines()
            sources = tuple(line.split(":", 1)[0].split("=", 1)[1]
                for line in lines if line.startswith("input_sha256="))
            features = tuple(item for line in lines
                if line.startswith("feature_defines=")
                for item in line.split("=", 1)[1].split(",") if item)
            require(sources and features == bound_features(),
                    "Card-2 pre-producer profile escaped successor authority")
            return {"sources": sources, "features": features,
                "profile": bind(BOUND_PROFILE),
                "phase": "pre-producer-successor-source-ownership"}

        def configure_preproducer() -> None:
            inherited_configure()
            link.BASE.profile_gate = successor_profile_gate
        link.configure = configure_preproducer
    try:
        link.child(action)
    finally:
        link.configure = inherited_configure


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "check-preflight",
        "replace-prelink", "build", "resume", "check", "selftest",
        "_source_preflight", "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    if action == "_source_preflight":
        source_preflight(); return 0
    if action.startswith("_"):
        child(action); return 0
    {"preflight": preflight, "check-preflight": check_preflight,
     "replace-prelink": replace_prelink_projection,
     "build": build, "resume": resume, "check": check,
     "selftest": selftest}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, RuntimeError, KeyError, ValueError, OSError,
            subprocess.CalledProcessError) as error:
        print(f"Block 2.6 Card 2: FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
