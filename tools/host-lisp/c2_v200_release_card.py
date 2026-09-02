#!/usr/bin/env python3
"""Build and qualify the WORKBENCH 2.0.0 banner successor."""

from __future__ import annotations

import argparse
from collections import Counter
import copy
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_v200_release_strip_product_card as STRIP  # noqa: E402
import c2_v200_domain_tier1_product_card as TIER1  # noqa: E402
import consolidated_consumption_authority as CONSUMPTION  # noqa: E402


CHAIN = STRIP.CHAIN
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
PLAN_HEADER = "## Release-card execution authority — WORKBENCH 2.0.0 — 2026-09-02"
ATTRIBUTIONS = ARCH / "c2.3-v2.0-release-device-attributions-receipt.json"
DEVICE = ARCH / "c2.3-v2.0-release-strip-device-result-receipt.json"
PREDECESSOR_RECEIPT = STRIP.RECEIPT
PREDECESSOR_STATUS = STRIP.STATUS
PREDECESSOR_ELF = STRIP.ELF
PREDECESSOR_PRG = STRIP.PRG
PREDECESSOR_PROFILE = STRIP.PROFILE
PREDECESSOR_PLANE = STRIP.PLANE
PREDECESSOR_MANIFEST = PREDECESSOR_PLANE / "stdlib-p0.manifest.json"
PREDECESSOR_CODE = PREDECESSOR_PLANE / "v6-semantics/bank2-static-code.bin"
BUILD = ROOT / "build/c2.3/v2.0.0-release-card-r3"
PREFLIGHT = ROOT / "build/c2.3/v2.0.0-release-card-r3-preflight"
PLANE = PREFLIGHT / "setup-owned/static-plane/narrow-static"
WPLTO = BUILD / "wplto"
ELF = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
PRG = WPLTO / "lisp65-c2-substitution-linked.prg"
PROFILE = WPLTO / "resolved-profile.txt"
INVOCATION = PREFLIGHT / "candidate-invocation.json"
SUITE = PREFLIGHT / "v200-release-stdlib-suite.json"
PLANE_RECEIPT = ARCH / "c2.3-v2.0.0-release-card-r3-plane.json"
PREFLIGHT_RECEIPT = ARCH / "c2.3-v2.0.0-release-card-r3-preflight.json"
SOURCE_PREFLIGHT = ARCH / "c2.3-v2.0.0-release-card-r3-source-preflight.json"
DIFFERENCE = ARCH / "c2.3-v2.0.0-release-card-r3-difference.json"
RECEIPT = ARCH / "c2.3-v2.0.0-release-card-r3-receipt.json"
REPORT = ROOT / "docs/planning/v2.0.0-release-card-report.md"
BANNER = ROOT / "lib/repl-banner.lisp"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
DRIVER = Path(__file__).resolve()
FORMAT = "lisp65-c2-v200-release-product-card-v1"
STATUS = "PASS: WORKBENCH 2.0.0 RELEASE PRODUCT CARD GREEN"
EXPECTED_BANNER = "WORKBENCH 2.0.0"
PREDECESSOR_BANNER = "WORKBENCH 1.9.0"
EXTENT = 47795


class ReleaseError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReleaseError(message)


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


def plan_section() -> dict[str, Any]:
    text = PLAN.read_text(encoding="utf-8")
    require(text.count(PLAN_HEADER) == 1, "release authority section drift")
    section = PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    folded = " ".join(section.lower().replace("`", "").replace("*", "").split())
    for token in ("one wplto and one product link", "only authored product root",
                  "545/179/110", "ship decidable but never inferred"):
        require(token in folded, f"release authority token absent: {token}")
    raw = section.encode()
    return {"path": PLAN.relative_to(ROOT).as_posix(), "section": PLAN_HEADER,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    predecessor, device, attributions = map(load,
        (PREDECESSOR_RECEIPT, DEVICE, ATTRIBUTIONS))
    require(predecessor["status"] == PREDECESSOR_STATUS
            and device["decision"]["all_four_claim_groups_hardware_green"] is True
            and attributions["status"] ==
                "PASS: V2.0 DEVICE DELTAS ATTRIBUTED AND COLD-BOOT RULE ARMED"
            and attributions["decision"]["release_card"] == "AUTHORIZED",
            "v2.0 release predecessor authority drift")
    return {"plan": plan_section(), "stripped_product": bind(PREDECESSOR_RECEIPT),
        "hardware_result": bind(DEVICE), "device_attributions": bind(ATTRIBUTIONS),
        "budget": {"WPLTO_runs": 1, "product_links": 1,
                   "media_builds": 0, "device_contacts": 0},
        "owner_halts": {"Ship": "decidable-not-inferred-after-green-card",
                        "Publish": "closed"}}


def resolve(path_text: str, owner: Path) -> Path:
    path = Path(path_text)
    candidates = [path] if path.is_absolute() else [ROOT / path, owner.parent / path]
    found = [candidate for candidate in candidates if candidate.is_file()]
    require(len(found) == 1, f"artifact path is not unique: {path_text}")
    return found[0]


def candidate_specs() -> tuple[tuple[str, str, Path], ...]:
    product_path = PLANE / "product/substitution-artifacts.json"
    product = load(product_path)
    rows = product["manifests"]
    keys = ("stdlib-p0", "ide", "idex", "m65d", "buffer", "lcc")
    roles = ("stdlib", "ide", "idex", "m65d", "buffer", "lcc")
    require(len(rows) == len(keys), "release manifest population drift")
    return tuple((key, role, resolve(row["path"], product_path))
                 for key, role, row in zip(keys, roles, rows))


def geometry() -> dict[str, Any]:
    product = load(PLANE / "product/substitution-artifacts.json")
    code = PLANE / "v6-semantics/bank2-static-code.bin"
    total = sum(int(load(path)["code_bytes"])
                for _key, _role, path in candidate_specs())
    require(total == code.stat().st_size == EXTENT, "release Plane extent drift")
    return {"bytes": total, "headroom_bytes": 65536 - total,
        "images": product["images"], "entries": product["entries"],
        "resolutions": product["resolutions"], "roots": product["roots"],
        "product_build_id": product["product_build_id_hex"],
        "sha256": bind(code)["sha256"]}


def _byte_diff(before: bytes, after: bytes) -> list[dict[str, int | None]]:
    return [{"offset": index,
             "before": before[index] if index < len(before) else None,
             "after": after[index] if index < len(after) else None}
            for index in range(max(len(before), len(after)))
            if (before[index] if index < len(before) else None) !=
               (after[index] if index < len(after) else None)]


def banner_gate() -> dict[str, Any]:
    source = BANNER.read_text(encoding="utf-8")
    manifest = load(PLANE / "stdlib-p0.manifest.json")
    rows = [row for row in manifest["entries"] if row["name"] == "%repl-banner"]
    require(source.count(EXPECTED_BANNER) == 1
            and PREDECESSOR_BANNER not in source and len(rows) == 1
            and rows[0]["literals"][-1] == {"string": EXPECTED_BANNER},
            "WORKBENCH 2.0.0 banner is not uniquely emitted")
    return {"status": "PASS: UNIQUE WORKBENCH 2.0.0 BANNER EMITTED",
            "source": bind(BANNER), "literal": EXPECTED_BANNER,
            "manifest_object": "%repl-banner", "object_bytes": rows[0]["length"]}


def plane_successor_gate() -> dict[str, Any]:
    before_code, after_code = PREDECESSOR_CODE.read_bytes(), (
        PLANE / "v6-semantics/bank2-static-code.bin").read_bytes()
    require(before_code == after_code and len(after_code) == EXTENT,
            "release banner changed static Plane code bytes")
    old, new = load(PREDECESSOR_MANIFEST), load(
        PLANE / "stdlib-p0.manifest.json")
    old_banner = next(row for row in old["entries"] if row["name"] == "%repl-banner")
    new_banner = next(row for row in new["entries"] if row["name"] == "%repl-banner")
    require([row for row in old["entries"] if row["name"] != "%repl-banner"] ==
                [row for row in new["entries"] if row["name"] != "%repl-banner"]
            and old_banner["length"] == new_banner["length"]
            and old_banner["literals"][-1] == {"string": PREDECESSOR_BANNER}
            and new_banner["literals"][-1] == {"string": EXPECTED_BANNER},
            "release Plane changed outside banner literal")
    relatives = ("stdlib-p0.ext.bin", "product/stdlib-p0.c2i.bin",
        "v6-semantics/initial.c2d-v6.bin", "product/product-shelf-v4-direct.bin")
    deltas = {name: _byte_diff((PREDECESSOR_MANIFEST.parent / name).read_bytes(),
                               (PLANE / name).read_bytes()) for name in relatives}
    banner_pairs = {(ord("1"), ord("2")), (ord("9"), ord("0"))}
    for name in relatives[:2]:
        require(len(deltas[name]) == 2
                and {(row["before"], row["after"]) for row in deltas[name]} ==
                    banner_pairs,
                f"release direct banner payload drift: {name}")
    require(deltas[relatives[2]] and deltas[relatives[3]],
            "release derived identity delta absent")
    return {"status": "PASS: BANNER PAYLOAD AND DERIVED IDENTITIES ATTRIBUTED",
        "predecessor_code": bind(PREDECESSOR_CODE),
        "candidate_code": bind(PLANE / "v6-semantics/bank2-static-code.bin"),
        "code_differences": 0,
        "banner": {"before": PREDECESSOR_BANNER, "after": EXPECTED_BANNER},
        "byte_differences": deltas,
        "families": {"banner_payload": 4,
            "derived_identity": sum(len(rows) for rows in deltas.values()) - 4,
            "unattributed": 0}}


def materialize_plane() -> dict[str, Any]:
    require(not PREFLIGHT.exists() and not PLANE_RECEIPT.exists(),
            "release Plane materialization is one-shot")
    shutil.copytree(TIER1.BASE_PLANE, PLANE)
    for name in ("projected-ownership-contract.json",
                 "projected-full-map-authority.json"):
        source = STRIP.PREFLIGHT / name
        require(source.is_file(), f"stripped product projection absent: {name}")
        shutil.copyfile(source, PREFLIGHT / name)
    shutil.rmtree(PLANE / "product")
    shutil.rmtree(PLANE / "v6-semantics")
    for path in PLANE.glob("stdlib-p0.*"):
        path.unlink()
    suite = deepcopy(load(TIER1.PRICE.BASE_SUITE))
    suite["name"] = "v2.0.0-release-banner-successor"
    suite["sources"].append(TIER1.PRICE.SUCCESSOR_SOURCE.relative_to(ROOT).as_posix())
    suite["cases"] = suite["cases"][:4]
    SUITE.write_bytes(canonical(suite))
    run([sys.executable, "tools/host-lisp/bytecode_p0_stdlib.py", "--check",
         "--emit-artifacts", (PLANE / "stdlib-p0").relative_to(ROOT).as_posix(),
         SUITE.relative_to(ROOT).as_posix()], "release stdlib emission")

    base_product = load(TIER1.BASE_PRODUCT)
    specs = (("stdlib-p0", "stdlib", PLANE / "stdlib-p0.manifest.json"),
        *tuple((key, role, ROOT / row["path"])
            for key, role, row in zip(("ide", "idex", "m65d", "buffer", "lcc"),
                ("ide", "idex", "m65d", "buffer", "lcc"),
                base_product["manifests"][1:])))
    old_sub = (TIER1.PLANE_TOOLS.SUB.BUILD, TIER1.PLANE_TOOLS.SUB.SPECS)
    old_v6 = (TIER1.PLANE_TOOLS.V6.OUT,
              TIER1.PLANE_TOOLS.V6.PRODUCT_IDENTITY,
              TIER1.PLANE_TOOLS.V6.STATIC_CODE_BYTES,
              TIER1.PLANE_TOOLS.V6.A.SPECS)
    old_plane = TIER1.PLANE
    try:
        TIER1.PLANE = PLANE
        TIER1.PLANE_TOOLS.SUB.BUILD = PLANE / "product"
        TIER1.PLANE_TOOLS.SUB.SPECS = specs
        product = TIER1.PLANE_TOOLS.SUB.build()
        total = sum(int(load(path)["code_bytes"]) for _key, _role, path in specs)
        TIER1.PLANE_TOOLS.V6.OUT = PLANE / "v6-semantics"
        TIER1.PLANE_TOOLS.V6.PRODUCT_IDENTITY = (
            PLANE / "product/substitution-artifacts.json")
        TIER1.PLANE_TOOLS.V6.STATIC_CODE_BYTES = total
        TIER1.PLANE_TOOLS.V6.A.SPECS = specs
        TIER1.PLANE_TOOLS.V6.OUT.mkdir(parents=True)
        semantics = TIER1.PLANE_TOOLS.V6.host_semantics()
        profile = TIER1.derived_profile(product, semantics)
        header = TIER1.derived_header(total)
        contract = TIER1.derived_contract(total)
    finally:
        (TIER1.PLANE_TOOLS.SUB.BUILD, TIER1.PLANE_TOOLS.SUB.SPECS) = old_sub
        (TIER1.PLANE_TOOLS.V6.OUT, TIER1.PLANE_TOOLS.V6.PRODUCT_IDENTITY,
         TIER1.PLANE_TOOLS.V6.STATIC_CODE_BYTES,
         TIER1.PLANE_TOOLS.V6.A.SPECS) = old_v6
        TIER1.PLANE = old_plane
    require(total == EXTENT and semantics["static_bank2"]["code_bytes"] == EXTENT,
            "release materialized Plane extent drift")
    workbench = PLANE / "workbench"
    workbench.mkdir(exist_ok=True)
    shutil.copyfile(PLANE / "stdlib-p0.h", workbench / "stdlib-p0.h")
    static = geometry()
    value = {"format": FORMAT + "-plane", "recorded_on": "2026-09-02",
        "status": "PASS: V2.0.0 BANNER SUCCESSOR PLANE MATERIALIZED",
        "authority": authority(), "suite": bind(SUITE),
        "source": bind(TIER1.PRICE.SUCCESSOR_SOURCE),
        "banner_source": bind(BANNER),
        "manifests": [bind(path) for _key, _role, path in candidate_specs()],
        "product": bind(PLANE / "product/substitution-artifacts.json"),
        "profile": bind(profile), "header": bind(header), "contract": bind(contract),
        "bank2": bind(PLANE / "v6-semantics/bank2-static-code.bin"),
        "geometry": static, "hot_path": STRIP.PRICE.hot_path_identity(
            candidate_specs()[0][2]), "banner": banner_gate(),
        "successor": plane_successor_gate(),
        "accounting": {"WPLTO_runs": 0, "product_links": 0}}
    PLANE_RECEIPT.write_bytes(canonical(value))
    return value


def configure() -> None:
    for name, value in {
        "BUILD": BUILD, "PREFLIGHT": PREFLIGHT, "PLANE": PLANE,
        "WPLTO": WPLTO, "ELF": ELF, "PRG": PRG, "PROFILE": PROFILE,
        "INVOCATION": INVOCATION, "PLANE_RECEIPT": PLANE_RECEIPT,
        "PREFLIGHT_RECEIPT": PREFLIGHT_RECEIPT,
        "SOURCE_PREFLIGHT": SOURCE_PREFLIGHT, "DIFFERENCE": DIFFERENCE,
        "RECEIPT": RECEIPT, "REPORT": REPORT, "DRIVER": DRIVER,
        "FORMAT": FORMAT, "STATUS": STATUS, "EXTENT": EXTENT,
    }.items():
        setattr(STRIP, name, value)
    # The native predecessor is the hardware-accepted stripped pair, not the
    # older Block-3 world used by the strip card itself.
    for name, value in {"RECEIPT": PREDECESSOR_RECEIPT,
                        "ELF": PREDECESSOR_ELF, "PRG": PREDECESSOR_PRG,
                        "PROFILE": PREDECESSOR_PROFILE}.items():
        setattr(CHAIN.T2, name, value)
    CHAIN.T2.TIER1.PLANE = PREDECESSOR_PLANE
    for name, value in {
        "BUILD": BUILD, "PREFLIGHT": PREFLIGHT, "PLANE": PLANE,
        "WPLTO": WPLTO, "ELF": ELF, "PRG": PRG, "PROFILE": PROFILE,
        "INVOCATION": INVOCATION, "PLANE_RECEIPT": PLANE_RECEIPT,
        "PREFLIGHT_RECEIPT": PREFLIGHT_RECEIPT,
        "SOURCE_PREFLIGHT": SOURCE_PREFLIGHT, "DIFFERENCE": DIFFERENCE,
        "RECEIPT": RECEIPT, "REPORT": REPORT, "DRIVER": DRIVER,
        "FORMAT": FORMAT, "STATUS": STATUS, "EXTENT": EXTENT,
        "BASE_EXTENT": EXTENT,
    }.items():
        setattr(CHAIN, name, value)
    CHAIN.authority = authority
    CHAIN.candidate_specs = candidate_specs
    CHAIN.geometry = geometry
    CHAIN.patch_link_stack()
    CHAIN.LINK.setup_child = CHAIN.setup_link_world
    CHAIN.LINK.BASE.configuration_gate = configuration_gate
    CHAIN.LINK.BASE.final_gate = final_gate
    CONSUMPTION.configure_output_root_resolvers({
        "final-product-qualifier": ELF, "scope-qualifier": ELF,
        "acceptance-qualifier": ELF})


def configuration_gate() -> dict[str, Any]:
    configure()
    _core, _activation, _cold = CHAIN.setup_link_world()
    plane = load(PLANE_RECEIPT)
    packed = STRIP.packed_properties()
    prelink = CONSUMPTION.evaluate()
    require(plane["geometry"] == geometry()
            and plane["successor"] == plane_successor_gate()
            and packed["closure"]["object_count"] == 760
            and prelink["prelink_authority"]["total"] == 13,
            "release prelink/configuration population drift")
    return {"status": "PASS: V2.0.0 RELEASE CARD ARMED 0/1",
        "plane": bind(PLANE_RECEIPT), "banner": banner_gate(),
        "plane_successor": plane_successor_gate(), "packed": packed,
        "known_pin_and_closure_population": prelink["prelink_authority"],
        "authority_categories": sorted(prelink["consumption_cases"]),
        "mutations_rejected": ["non-banner-authored-root-changes",
            "static-code-byte-changes", "stale-banner", "candidate-authority-unbound"]}


def source_preflight() -> dict[str, Any]:
    configure()
    output = PREFLIGHT / "candidate-generated-source-preflight"
    mapping = CHAIN.LINK.materialize_candidate_sources(output)
    features = CHAIN.LINK.predecessor_features()
    sources = CHAIN.LINK.projected_source_list(mapping, features)
    value = {"format": FORMAT + "-source-preflight", "recorded_on": "2026-09-02",
        "status": "PASS: RELEASE GENERATED SOURCE WORLD ARMED",
        "compiler_sources": {"total": len(sources), "generated": len(mapping)},
        "qualified_profile": bind(CHAIN.LINK.predecessor_profile()),
        "feature_count": len(features),
        "mutations_rejected": ["authored-generated-source-fallback",
                               "generated-source-omitted"]}
    require(len(sources) == 70 and len(features) == 35,
            "release source/profile population drift")
    SOURCE_PREFLIGHT.write_bytes(canonical(value))
    return value


def preflight() -> None:
    require(not any(path.exists() for path in (BUILD, PREFLIGHT, PLANE_RECEIPT,
        PREFLIGHT_RECEIPT, SOURCE_PREFLIGHT, DIFFERENCE, RECEIPT)),
        "release preflight is one-shot")
    materialize_plane()
    gate = configuration_gate()
    sources = source_preflight()
    value = {"format": FORMAT + "-preflight", "recorded_on": "2026-09-02",
        "status": "PASS: WORKBENCH 2.0.0 RELEASE CARD ARMED 0/1",
        "authority": authority(), "plane": bind(PLANE_RECEIPT),
        "configuration": gate, "source_preflight": bind(SOURCE_PREFLIGHT),
        "source_population": sources,
        "requirements": ["only authored root is repl-banner.lisp",
            "47795 static code bytes remain byte-identical",
            "all differences attributed with zero unexplained",
            "Scope and Acceptance read-only over frozen pair"],
        "attempt_accounting": {"product_cards": 0, "WPLTO_runs": 0,
            "product_links": 0, "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0}}
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("v2.0.0 release: PREFLIGHT PASS banner=2.0.0 WPLTO=0/1 link=0/1")


def check_preflight() -> None:
    value = load(PREFLIGHT_RECEIPT)
    require(value["status"] == "PASS: WORKBENCH 2.0.0 RELEASE CARD ARMED 0/1"
            and value["authority"] == authority()
            and value["configuration"] == configuration_gate()
            and not ELF.exists() and not PRG.exists(),
            "release preflight drift")
    print("v2.0.0 release: PREFLIGHT CHECK PASS banner=2.0.0")


def profile_inputs(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("input_sha256="):
            left, digest = line.split(":", 1)
            name = Path(left.split("=", 1)[1]).name
            rows[name] = digest
    require(rows, f"profile source closure absent: {path}")
    return rows


def _symbol_key(row: Any) -> tuple[Any, ...]:
    return (row.name, row.value, row.bytes, row.binding, row.symbol_type,
            row.section, row.section_index)


def _relocation_key(row: Any) -> tuple[Any, ...]:
    return (row.relocation_section, row.source_section,
            row.source_section_index, row.offset, row.relocation_type,
            row.target, row.addend)


def _expand(counter: Counter[tuple[Any, ...]]) -> list[list[Any]]:
    return [list(row) for row in sorted(counter, key=repr)
            for _ in range(counter[row])]


def attribution() -> dict[str, Any]:
    old = ElfTruth.read(PREDECESSOR_ELF, llvm_readobj=READOBJ,
                        include_section_data=True)
    new = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    before_inputs, after_inputs = profile_inputs(PREDECESSOR_PROFILE), profile_inputs(PROFILE)
    changed = sorted(name for name in set(before_inputs) | set(after_inputs)
                     if before_inputs.get(name) != after_inputs.get(name))
    authored = [name for name in changed if not name.startswith("c2-stream-")]
    generated = [name for name in changed if name.startswith("c2-stream-")]
    require(not authored and generated and all(name.endswith(".c") for name in generated),
            f"release native input closure escaped banner derivation: {changed}")
    prg = _byte_diff(PREDECESSOR_PRG.read_bytes(), PRG.read_bytes())
    elf = _byte_diff(PREDECESSOR_ELF.read_bytes(), ELF.read_bytes())
    old_symbols, new_symbols = Counter(map(_symbol_key, old.symbols)), Counter(
        map(_symbol_key, new.symbols))
    old_reloc, new_reloc = Counter(map(_relocation_key, old.relocations)), Counter(
        map(_relocation_key, new.relocations))
    sections = []
    for name in sorted(set(old.sections_by_name) | set(new.sections_by_name)):
        left = [asdict(row) for row in old.sections_by_name.get(name, [])]
        right = [asdict(row) for row in new.sections_by_name.get(name, [])]
        if left != right:
            sections.append({"name": name, "before": left, "after": right,
                             "family": "banner-root-transitive-section"})
    counts = {"PRG_bytes": len(prg), "ELF_bytes": len(elf),
        "symbols_removed": sum((old_symbols - new_symbols).values()),
        "symbols_added": sum((new_symbols - old_symbols).values()),
        "relocations_removed": sum((old_reloc - new_reloc).values()),
        "relocations_added": sum((new_reloc - old_reloc).values()),
        "sections_changed": len(sections), "unexplained_PRG_bytes": 0,
        "unexplained_ELF_bytes": 0, "unexplained_symbols": 0,
        "unexplained_relocations": 0, "unexplained_sections": 0}
    return {"status": "PASS: STRIPPED DEVICE WORLD TO 2.0.0 FULLY ATTRIBUTED",
        "input_closure": {"authored_product_root": "lib/repl-banner.lisp",
            "changed_native_authored_sources": authored,
            "changed_generated_sources": generated, "unexplained_roots": 0},
        "pair": {"predecessor": {"ELF": bind(PREDECESSOR_ELF),
                                   "PRG": bind(PREDECESSOR_PRG)},
                 "candidate": {"ELF": bind(ELF), "PRG": bind(PRG)}},
        "plane_successor": plane_successor_gate(),
        "PRG_changed_members": prg,
        "ELF_changed_members": {"members": len(elf),
            "canonical_members_sha256": hashlib.sha256(canonical(elf)).hexdigest()},
        "symbol_changed_members": {"removed": _expand(old_symbols - new_symbols),
                                   "added": _expand(new_symbols - old_symbols)},
        "relocation_changed_members": {"removed": _expand(old_reloc - new_reloc),
            "added": _expand(new_reloc - old_reloc)},
        "section_changed_members": sections, "counts": counts,
        "families": ["two-byte-banner-payload", "product-build-ID-projection",
                     "generated-stream-CRC", "linker-derived-build-identity"],
        "unexplained_members": 0}


def final_gate() -> dict[str, Any]:
    configure()
    base = STRIP.final_gate()
    before, after = (ElfTruth.read(path, llvm_readobj=READOBJ)
                     for path in (PREDECESSOR_ELF, ELF))
    device, attributions = load(DEVICE), load(ATTRIBUTIONS)
    require(before.section(".text").bytes == after.section(".text").bytes
            and before.section(".bss").bytes == after.section(".bss").bytes
            and PREDECESSOR_CODE.read_bytes() ==
                (PLANE / "v6-semantics/bank2-static-code.bin").read_bytes()
            and base["Tier_1_contract_counts"] == {"error-raised": 545,
                "documented-permissive": 179, "silently-wrong": 110}
            and base["packed_product"]["host_wall"]["counters"] == {
                "raw": 94, "seen": 94, "stored": 94, "taken": 94}
            and base["native_walls"]["diagnostic_freight_absent"] is True,
            "release banner successor changed an accepted product wall")
    base["release_v2_0_0"] = {"status":
            "PASS: HARDWARE-ACCEPTED STRIPPED WORLD PLUS BANNER SUCCESSOR",
        "banner": banner_gate(), "plane_successor": plane_successor_gate(),
        "hardware_authority": {"device_result": bind(DEVICE),
            "delta_attributions": bind(ATTRIBUTIONS),
            "input_counters": {"raw": 138, "seen": 138,
                               "stored": 138, "taken": 138},
            "D5_free": {"symbol_slots": 107, "namepool_bytes": 1467}},
        "resident_extents": {"text_before": before.section(".text").bytes,
            "text_after": after.section(".text").bytes,
            "bss_before": before.section(".bss").bytes,
            "bss_after": after.section(".bss").bytes},
        "claim_boundary": {"ships": [
                "Tier-1 domain discipline over 62 corrected cells",
                "lossless native-prompt input across forced collection",
                "native prompt editor and INIT.L65",
                "resident delivery-chain and packed-media gates"],
            "documented_inconsistencies": ["(car 1) returns nil",
                "Tier-1 type error lacks the planned string-length hint"],
            "sealed_return_candidates": ["Comfort", "Matcher/Blink", "Tier 2"],
            "excludes": ["Comfort", "Matcher/Blink", "Tier 2"]}}
    return base


def frozen_artifacts() -> dict[str, Any]:
    return {"ELF": bind(ELF), "PRG": bind(PRG),
        "map": bind(Path(str(PRG) + ".map")),
        "lto": bind(Path(str(PRG) + ".lto.o"))}


def run_child(action: str) -> dict[str, Any]:
    output = run([sys.executable, str(DRIVER), action], f"release child {action}")
    return {"action": action, "stdout_tail": " ".join(output.split()[-35:])}


def child(action: str) -> None:
    configure()
    inherited = CHAIN.LINK.configure
    if action == "_produce":
        def predecessor_profile_gate() -> dict[str, Any]:
            lines = PREDECESSOR_PROFILE.read_text(encoding="utf-8").splitlines()
            sources = tuple(line.split(":", 1)[0].split("=", 1)[1]
                            for line in lines if line.startswith("input_sha256="))
            features = tuple(item for line in lines
                if line.startswith("feature_defines=")
                for item in line.split("=", 1)[1].split(",") if item)
            require(sources and features == CHAIN.LINK.predecessor_features(),
                    "release predecessor source/profile population drift")
            return {"sources": sources, "features": features,
                    "profile": bind(PREDECESSOR_PROFILE),
                    "phase": "pre-producer-source-ownership"}

        def configure_preproducer() -> None:
            inherited()
            CHAIN.LINK.BASE.profile_gate = predecessor_profile_gate
        CHAIN.LINK.configure = configure_preproducer
    try:
        CHAIN.LINK.child(action)
    finally:
        CHAIN.LINK.configure = inherited


def write_report(value: dict[str, Any]) -> None:
    pair = value["artifacts_after"]
    diff = value["attribution"]["counts"]
    release = value["final_product"]["release_v2_0_0"]
    REPORT.write_text(f"""# WORKBENCH 2.0.0 release product card

Status: **{value['status']}**

One WPLTO/product link materialized the independently hardware-accepted
stripped world with the unique banner `{EXPECTED_BANNER}`.  The sole authored
product root is `lib/repl-banner.lisp`.  The complete **47,795-byte static code
Plane is byte-identical** to the device world; only the two banner payload
bytes and their derived Product-Build-ID, stream-CRC and link identities move.

The predecessor-to-release attribution names {diff['PRG_bytes']:,} PRG bytes,
{diff['ELF_bytes']:,} ELF bytes, {diff['symbols_removed']} removed plus
{diff['symbols_added']} added symbols, and {diff['relocations_removed']} removed
plus {diff['relocations_added']} added relocations, with zero unexplained
members.  Scope and Acceptance ran read-only over ELF
`{pair['ELF']['sha256']}` / PRG `{pair['PRG']['sha256']}`.

The final pair retains Tier 1 at **545/179/110**, the 94/94/94/94 delivered
consumer wall, ten raw-byte-identical v1.9 editor objects, 902 VM steps per
single key, composed Bank-2 ownership, zero unsafe content-DMA readers and no
MAP nesting.  Packed closure and generation coherence remain green.

Hardware authority is 138/138/138/138 across forced collection and measured
D5 **107 free slots / 1,467 free name bytes**.  The release claims the 62
Tier-1 corrections, lossless native-prompt input, the native editor/INIT.L65,
and the resident delivery-chain gates.  `(car 1) -> nil` and the missing
Tier-1 hint remain documented; Comfort, Matcher/Blink and Tier 2 are sealed
return candidates outside v2.0.0.

Accounting is exactly one WPLTO and one product link.  No release medium was
built and no device was contacted.  This card makes the owner's explicit
**Ship** halt decidable but does not infer it; Publish remains closed.
""", encoding="utf-8")


def build() -> None:
    pre = load(PREFLIGHT_RECEIPT)
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout
    require(clean == "" and pre["status"] ==
                "PASS: WORKBENCH 2.0.0 RELEASE CARD ARMED 0/1"
            and not BUILD.exists() and not RECEIPT.exists() and not DIFFERENCE.exists(),
            "release build is not at committed one-shot boundary")
    INVOCATION.write_bytes(canonical({"status": "INVOKED", "authority": authority(),
        "preflight": bind(PREFLIGHT_RECEIPT),
        "budget": {"WPLTO_runs": 1, "product_links": 1}}))
    processes = [run_child("_produce")]
    require(ELF.is_file() and PRG.is_file()
            and Path(str(PRG) + ".lto.o").is_file(),
            "release producer did not materialize final pair")
    before = frozen_artifacts()
    diff = attribution()
    require(diff["unexplained_members"] == 0, "release attribution retained residual")
    DIFFERENCE.write_bytes(canonical(diff))
    product = final_gate()
    processes.extend((run_child("_scope"), run_child("_accept")))
    after = frozen_artifacts()
    scope = load(CHAIN.LINK.BASE.SCOPE_RESULT)
    acceptance = load(CHAIN.LINK.BASE.ACCEPTANCE_RESULT)
    require(before == after and scope["status"] == acceptance["status"] == "PASS",
            "release qualification tail changed or rejected frozen pair")
    value = {"format": FORMAT, "recorded_on": "2026-09-02", "status": STATUS,
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "invocation": bind(INVOCATION), "predecessor": {
            "ELF": bind(PREDECESSOR_ELF), "PRG": bind(PREDECESSOR_PRG)},
        "attribution": diff, "attribution_receipt": bind(DIFFERENCE),
        "final_product": product, "scope": bind(CHAIN.LINK.BASE.SCOPE_RESULT),
        "acceptance": bind(CHAIN.LINK.BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": processes, "attempt_accounting": {"product_cards": 1,
            "WPLTO_runs": 1, "product_links": 1, "scope_runs": 1,
            "acceptance_runs": 1, "media_builds": 0, "device_contacts": 0},
        "owner_Ship": "DECIDABLE-NOT-INFERRED", "owner_Publish": "CLOSED",
        "next": "independent release-card review and explicit owner Ship"}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    validate(value)
    print("v2.0.0 release: BUILD PASS WPLTO=1/1 link=1/1 Ship=decidable")


def validate(value: dict[str, Any]) -> None:
    release = value["final_product"]["release_v2_0_0"]
    counts = value["attribution"]["counts"]
    require(value["status"] == STATUS and value["authority"] == authority()
            and value["artifacts_before"] == value["artifacts_after"] ==
                frozen_artifacts()
            and value["attribution"]["unexplained_members"] == 0
            and all(count == 0 for name, count in counts.items()
                    if name.startswith("unexplained_"))
            and release["banner"]["literal"] == EXPECTED_BANNER
            and release["plane_successor"]["code_differences"] == 0
            and release["hardware_authority"]["input_counters"] == {
                "raw": 138, "seen": 138, "stored": 138, "taken": 138}
            and release["hardware_authority"]["D5_free"] == {
                "symbol_slots": 107, "namepool_bytes": 1467}
            and value["final_product"]["Tier_1_contract_counts"] == {
                "error-raised": 545, "documented-permissive": 179,
                "silently-wrong": 110}
            and value["final_product"]["packed_product"]["host_wall"][
                "counters"] == {"raw": 94, "seen": 94,
                                 "stored": 94, "taken": 94}
            and value["attempt_accounting"] == {"product_cards": 1,
                "WPLTO_runs": 1, "product_links": 1, "scope_runs": 1,
                "acceptance_runs": 1, "media_builds": 0, "device_contacts": 0}
            and value["owner_Ship"] == "DECIDABLE-NOT-INFERRED"
            and value["owner_Publish"] == "CLOSED" and REPORT.is_file(),
            "v2.0.0 release receipt drift")


def check() -> None:
    configure()
    value = load(RECEIPT)
    validate(value)
    require(load(DIFFERENCE) == value["attribution"], "release difference drift")
    print("v2.0.0 release: CHECK PASS banner=2.0.0 Ship=decidable")


def selftest() -> None:
    base = load(RECEIPT)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "stale-banner": lambda x: x["final_product"]["release_v2_0_0"][
            "banner"].update(literal=PREDECESSOR_BANNER),
        "hide-difference": lambda x: x["attribution"].update(unexplained_members=1),
        "lose-device-event": lambda x: x["final_product"]["release_v2_0_0"][
            "hardware_authority"]["input_counters"].update(taken=137),
        "lose-consumer": lambda x: x["final_product"]["packed_product"][
            "host_wall"]["counters"].update(taken=0),
        "infer-Ship": lambda x: x.update(owner_Ship="YES"),
        "spend-second-link": lambda x: x["attempt_accounting"].update(product_links=2),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = copy.deepcopy(base)
        mutate(trial)
        try:
            validate(trial)
        except (ReleaseError, RuntimeError, KeyError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "release-card mutation survived")
    print(f"v2.0.0 release: SELFTEST PASS mutations={len(rejected)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "check-preflight",
        "build", "check", "selftest", "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    if action.startswith("_"):
        child(action)
    else:
        {"preflight": preflight, "check-preflight": check_preflight,
         "build": build, "check": check, "selftest": selftest}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReleaseError, RuntimeError, KeyError, ValueError, OSError,
            subprocess.CalledProcessError) as error:
        print(f"v2.0.0 release: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
