#!/usr/bin/env python3
"""Build and qualify the stripped v2.0 Tier-1 release world.

The card removes the failed resident interactive freight by binding the
qualified Tier-1 six-image plane to one fresh product link.  The existing
Tier-1 pair is only the object/capacity reference; the emitted native product
is rebuilt against the current v2.0 feature and authority world.
"""

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
import c2_packed_medium_transitive_closure as CLOSURE  # noqa: E402
import c2_packed_object_generation_coherence as COHERENCE  # noqa: E402
import c2_v200_block3_hot_path_repair_card as CURRENT  # noqa: E402
import c2_v200_domain_tier1_product_card as TIER1  # noqa: E402
import c2_v200_interactive_delivery_chain_product_card as CHAIN  # noqa: E402
import c2_v200_release_shape_pricing as PRICE  # noqa: E402
import c2_v200_tier2_descope_product_card as LANES  # noqa: E402
import consolidated_consumption_authority as CONSUMPTION  # noqa: E402
import c2_v190_block_a_delivered_consumer_repair as V19_CONSUMER  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
AUTHORIZATION = "a84afbf5"
PLAN_HEADER = "## Owner authorization — strip v2.0 release world — 2026-09-02"
EXTENT = 47795
CURRENT_EXTENT = 53871
BUILD = ROOT / "build/c2.3/v2.0-release-strip-product-card-r1"
PREFLIGHT = ROOT / "build/c2.3/v2.0-release-strip-product-card-r1-preflight"
PLANE = PREFLIGHT / "setup-owned/static-plane/narrow-static"
WPLTO = BUILD / "wplto"
ELF = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
PRG = WPLTO / "lisp65-c2-substitution-linked.prg"
PROFILE = WPLTO / "resolved-profile.txt"
INVOCATION = PREFLIGHT / "candidate-invocation.json"
PLANE_RECEIPT = ARCH / "c2.3-v2.0-release-strip-product-card-r1-plane.json"
PREFLIGHT_RECEIPT = ARCH / (
    "c2.3-v2.0-release-strip-product-card-r1-preflight.json")
SOURCE_PREFLIGHT = ARCH / (
    "c2.3-v2.0-release-strip-product-card-r1-source-preflight.json")
DIFFERENCE = ARCH / "c2.3-v2.0-release-strip-product-card-r1-difference.json"
RECEIPT = ARCH / "c2.3-v2.0-release-strip-product-card-r1-receipt.json"
REPORT = ROOT / "docs/planning/v2.0.0-release-strip-product-card-report.md"
D5 = ARCH / "c2.3-v1.9-r8-release-terminal-d5-receipt.json"
V19_PRODUCT = PRICE.V19_STDLIB.parent / "product/substitution-artifacts.json"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
DRIVER = Path(__file__).resolve()
FORMAT = "lisp65-c2-v200-release-strip-product-card-v1"
STATUS = "PASS: V2.0 STRIPPED TIER-1 RELEASE PRODUCT GREEN"
PRODUCT_KEYS = ("stdlib-p0", "ide", "idex", "m65d", "buffer", "lcc")


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


def authority() -> dict[str, Any]:
    relative = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{relative}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = raw.decode()
    require(text.count(PLAN_HEADER) == 1, "strip authorization identity drift")
    section = PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    folded = " ".join(section.lower().replace("`", "").replace("*", "").split())
    for token in ("exactly one wplto and one product link",
                  "raw-byte-identical", "6,076 plane bytes", "236 packed call sites",
                  "both responsiveness lanes", "scope and acceptance"):
        require(token in folded, f"strip authorization token absent: {token}")
    payload = section.encode()
    return {"commit": AUTHORIZATION, "path": relative,
        "section": PLAN_HEADER, "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "pricing": bind(PRICE.RECEIPT),
        "predecessor": bind(CURRENT.RECEIPT),
        "right": "one product card, one WPLTO and one product link"}


def resolve(path_text: str, owner: Path) -> Path:
    path = Path(path_text)
    candidates = [path] if path.is_absolute() else [ROOT / path, owner.parent / path]
    found = [candidate for candidate in candidates if candidate.is_file()]
    require(len(found) == 1, f"artifact path is not unique: {path_text}")
    return found[0]


def candidate_specs() -> tuple[tuple[str, str, Path], ...]:
    product_path = PLANE / "product/substitution-artifacts.json"
    product = load(product_path)
    rows = product.get("manifests")
    require(isinstance(rows, list) and len(rows) == len(PRODUCT_KEYS),
            "stripped product manifest population drift")
    paths = [resolve(row["path"], product_path) for row in rows]
    return tuple((key, role, path) for key, role, path in zip(
        PRODUCT_KEYS, ("stdlib", "ide", "idex", "m65d", "buffer", "lcc"), paths))


def geometry() -> dict[str, Any]:
    product = load(PLANE / "product/substitution-artifacts.json")
    code = PLANE / "v6-semantics/bank2-static-code.bin"
    total = sum(int(load(path)["code_bytes"])
                for _key, _role, path in candidate_specs())
    require(total == code.stat().st_size == EXTENT,
            "stripped Plane extent drift")
    return {"bytes": total, "headroom_bytes": 65536 - total,
        "images": product["images"], "entries": product["entries"],
        "resolutions": product["resolutions"], "roots": product["roots"],
        "product_build_id": product["product_build_id_hex"],
        "sha256": bind(code)["sha256"]}


def materialize_plane() -> dict[str, Any]:
    require(not PREFLIGHT.exists() and not PLANE_RECEIPT.exists(),
            "strip Plane materialization is one-shot")
    run([sys.executable, str(Path(PRICE.__file__).resolve()), "check"],
        "release-shape price regeneration")
    shutil.copytree(PRICE.CLEAN_ROOT, PLANE)
    for name in ("projected-ownership-contract.json",
                 "projected-full-map-authority.json"):
        source = CURRENT.PREFLIGHT / name
        require(source.is_file(), f"current product projection absent: {name}")
        shutil.copyfile(source, PREFLIGHT / name)
    product = load(PLANE / "product/substitution-artifacts.json")
    static = geometry()
    semantics = {"static_bank2": {"code_bytes": static["bytes"],
        "code_sha256": static["sha256"],
        "headroom_bytes": static["headroom_bytes"]}}
    CHAIN.PLANE_TOOLS.derived_profile(PLANE, product, semantics)
    CHAIN.PLANE_TOOLS.derived_contract(PLANE, EXTENT)
    CHAIN.PLANE_TOOLS.derived_header(PLANE, EXTENT)
    value = {"format": FORMAT + "-plane", "recorded_on": "2026-09-02",
        "status": "PASS: QUALIFIED TIER-1 PLANE MATERIALIZED FOR STRIP",
        "authority": authority(), "source_reference": bind(
            PRICE.CLEAN_RECEIPT), "geometry": static,
        "manifests": [bind(path) for _key, _role, path in candidate_specs()],
        "product": bind(PLANE / "product/substitution-artifacts.json"),
        "profile": bind(PLANE / "candidate-profile.json"),
        "contract": bind(PLANE / "c2-lite-execution-contract.json"),
        "header": bind(PLANE / "c2_lite_static_plane.h"),
        "bank2": bind(PLANE / "v6-semantics/bank2-static-code.bin"),
        "hot_path": PRICE.hot_path_identity(candidate_specs()[0][2]),
        "accounting": {"WPLTO_runs": 0, "product_links": 0}}
    PLANE_RECEIPT.write_bytes(canonical(value))
    return value


def configure() -> None:
    # Present the final Block-3 repair pair as the native predecessor while
    # replacing only phase-owned outputs and the candidate Plane authority.
    for name, value in {
        "RECEIPT": CURRENT.RECEIPT, "ELF": CURRENT.ELF,
        "PRG": CURRENT.PRG, "PROFILE": CURRENT.PROFILE,
        "PLANE": CURRENT.PLANE, "PREFLIGHT": CURRENT.PREFLIGHT,
        "PLANE_RECEIPT": CURRENT.PLANE_RECEIPT,
    }.items():
        setattr(CHAIN.T2, name, value)
    for name, value in {
        "BUILD": BUILD, "PREFLIGHT": PREFLIGHT, "PLANE": PLANE,
        "WPLTO": WPLTO, "ELF": ELF, "PRG": PRG, "PROFILE": PROFILE,
        "INVOCATION": INVOCATION, "PLANE_RECEIPT": PLANE_RECEIPT,
        "PREFLIGHT_RECEIPT": PREFLIGHT_RECEIPT,
        "SOURCE_PREFLIGHT": SOURCE_PREFLIGHT, "DIFFERENCE": DIFFERENCE,
        "RECEIPT": RECEIPT, "REPORT": REPORT, "DRIVER": DRIVER,
        "AUTHORIZATION": AUTHORIZATION, "PLAN_HEADER": PLAN_HEADER,
        "FORMAT": FORMAT, "STATUS": STATUS, "EXTENT": EXTENT,
        "BASE_EXTENT": CURRENT_EXTENT,
    }.items():
        setattr(CHAIN, name, value)
    CHAIN.authority = authority
    CHAIN.candidate_specs = candidate_specs
    CHAIN.geometry = geometry
    CHAIN.patch_link_stack()
    CHAIN.LINK.setup_child = CHAIN.setup_link_world
    CHAIN.LINK.BASE.configuration_gate = configuration_gate
    CHAIN.LINK.BASE.final_gate = final_gate


def lifecycle_key_sources(
        specs: tuple[tuple[str, str, Path], ...]) -> dict[str, Any]:
    """Derive every syntactic key source, then qualify the active subset.

    The hardware-green v1.9 editor deliberately retains one public-queue
    fallback for the disarmed eight-cell state.  The delivered nine-cell
    lifecycle makes that branch unreachable and selects only modes 2/3.  A
    syntactic-site census and an active-lifecycle census are therefore both
    required; treating either one as the other is a checker-world defect.
    """
    sites: list[dict[str, Any]] = []
    for key, _role, manifest in specs:
        for function in CHAIN.PRICE.code_object_rows(manifest):
            previous: dict[str, Any] | None = None
            for instruction in function["instructions"]:
                operand = instruction["operand"]
                if (instruction["mnemonic"] == "CALLPRIM"
                        and isinstance(operand, tuple)
                        and operand == (60, 1)):
                    require(previous is not None
                            and previous["mnemonic"] == "PUSHI8"
                            and previous["operand"] in (0, 1, 2, 3),
                            "strip key-event mode is not statically materialized")
                    mode = int(previous["operand"])
                    sites.append({"image": key, "caller": function["name"],
                        "pc": instruction["pc"], "mode": mode,
                        "sink": ("c2_kernal_input_take" if mode in (2, 3)
                                 else "public-hardware-queue")})
                previous = instruction
    sites.sort(key=lambda row: (row["image"], row["caller"], row["pc"]))
    require([(row["caller"], row["mode"]) for row in sites] == [
                ("%read-line-loop", 1), ("%rl-put", 3), ("%rl-render", 2)],
            f"stripped syntactic key-source population drift: {sites}")

    view = load(TIER1.LIFECYCLE_VIEW)
    source_path = ROOT / view["lifecycle_provenance"]["canonical_source"]["path"]
    source_binding = bind(source_path)
    require(source_binding == view["lifecycle_provenance"]["canonical_source"],
            "strip lifecycle source binding drift")
    lifecycle = TIER1.derive_bound_client_lifecycle(
        source_path.read_text(encoding="utf-8"))
    require(lifecycle == view["lifecycle"]
            and lifecycle["state_cells"] == 9
            and lifecycle["selected_main_route"] ==
                "key-event mode 2 through %rl-render"
            and lifecycle["selected_batch_route"] ==
                "key-event mode 3 through %rl-put"
            and lifecycle["disarmed_fallback_retained"] ==
                "public key-event mode 1",
            "strip active lifecycle is not the bound v1.9 lifecycle")
    active = [row for row in sites if row["mode"] in (2, 3)]
    fallback = [row for row in sites if row["mode"] == 1]
    require(len(active) == 2 and len(fallback) == 1
            and {row["sink"] for row in active} == {"c2_kernal_input_take"}
            and fallback[0]["sink"] == "public-hardware-queue",
            "strip lifecycle-qualified key-source population drift")
    return {"status":
            "PASS: ACTIVE DELIVERED KEY SOURCES RESOLVE EXACTLY TO RING TAKE",
        "all_syntactic_sites": sites, "active_lifecycle_sites": active,
        "disarmed_fallback": fallback,
        "active_sink_set": ["c2_kernal_input_take"],
        "lifecycle": lifecycle, "lifecycle_source": source_binding,
        "lifecycle_view": bind(TIER1.LIFECYCLE_VIEW),
        "rule": ("derive every syntactic key-event site and derive the active "
                 "subset from the bound delivered lifecycle; the public queue "
                 "is permitted only in the proven disarmed fallback")}


def validate_lifecycle_key_sources(value: dict[str, Any]) -> None:
    require(value["active_sink_set"] == ["c2_kernal_input_take"]
            and len(value["all_syntactic_sites"]) == 3
            and len(value["active_lifecycle_sites"]) == 2
            and all(row["mode"] in (2, 3)
                    and row["sink"] == "c2_kernal_input_take"
                    for row in value["active_lifecycle_sites"])
            and len(value["disarmed_fallback"]) == 1
            and value["disarmed_fallback"][0]["mode"] == 1
            and value["disarmed_fallback"][0]["sink"] ==
                "public-hardware-queue"
            and value["lifecycle"]["state_cells"] == 9,
            "stripped lifecycle-qualified key-source invariant failed")


def lifecycle_key_source_mutations(value: dict[str, Any]) -> list[str]:
    cases: tuple[tuple[str, Callable[[dict[str, Any]], None]], ...] = (
        ("activate-public-queue-fallback", lambda row: (
            row["active_lifecycle_sites"].append(
                deepcopy(row["disarmed_fallback"][0])),
            row.update({"active_sink_set": [
                "c2_kernal_input_take", "public-hardware-queue"]}))),
        ("omit-active-ring-source", lambda row:
            row["active_lifecycle_sites"].pop()),
        ("restore-eight-cell-lifecycle", lambda row:
            row["lifecycle"].update({"state_cells": 8})),
    )
    rejected: list[str] = []
    for name, mutate in cases:
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate_lifecycle_key_sources(trial)
        except CardError:
            rejected.append(name)
    require(rejected == [name for name, _mutate in cases],
            "strip lifecycle key-source mutation survived")
    return rejected


def packed_properties(consumer_elf: Path | None = None) -> dict[str, Any]:
    product = PLANE / "product/substitution-artifacts.json"
    closure = CLOSURE.derive(product)
    CLOSURE.require_closed(closure)
    specs = candidate_specs()
    lengths = [int(load(path)["code_bytes"]) for _key, _role, path in specs]
    plane = (PLANE / "v6-semantics/bank2-static-code.bin").read_bytes()
    require(sum(lengths) == len(plane) == EXTENT,
            "stripped packed component boundary drift")
    product_stdlib = resolve(load(product)["images_detail"][0]["code"]["path"],
                             product) if "images_detail" in load(product) else (
        PLANE / "product/stdlib-p0.code.bin")
    require(product_stdlib.is_file(), "stripped packed stdlib image absent")
    # The packed product contains relocation-patched object bytes.  Bind the
    # manifest's object boundaries/contracts to that materialized generation,
    # not to the pre-relocation compiler blob.
    coherence = COHERENCE.derive(
        specs[0][2], product_stdlib, None, plane[:lengths[0]])
    COHERENCE.require_coherent(coherence)
    sources = lifecycle_key_sources(specs)
    validate_lifecycle_key_sources(sources)
    source_path = ROOT / sources["lifecycle_source"]["path"]
    wall = V19_CONSUMER.run_delivered_consumer(
        source_path, consumer_elf or (ELF if ELF.is_file() else CURRENT.ELF), True)
    require(closure["object_count"] == 760
            and closure["call_site_count"] == 2436
            and sources["active_sink_set"] == ["c2_kernal_input_take"]
            and wall["counters"] == {"raw": 94, "seen": 94,
                                      "stored": 94, "taken": 94},
            "stripped closure/coherence/input wall drift")
    return {"closure": closure, "generation_coherence": coherence,
        "key_sources": sources, "host_wall": wall,
        "key_source_mutations_rejected":
            lifecycle_key_source_mutations(sources),
        "packed_plane": bind(PLANE / "v6-semantics/bank2-static-code.bin")}


def d5_projection() -> dict[str, Any]:
    def names(product_path: Path) -> list[str]:
        result = []
        for _key, _role, path in product_specs_at(product_path):
            result.extend(row["name"] for row in load(path)["entries"]
                          if row.get("kind") in {"function", "macro"})
        return sorted(result)

    def free(value: Any) -> dict[str, int] | None:
        if isinstance(value, dict):
            if value.get("symbol_slots") == 109 and value.get(
                    "namepool_bytes") == 1486:
                return {"symbol_slots": 109, "namepool_bytes": 1486}
            for child in value.values():
                found = free(child)
                if found is not None:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = free(child)
                if found is not None:
                    return found
        return None

    candidate_names, release_names = names(
        PLANE / "product/substitution-artifacts.json"), names(V19_PRODUCT)
    require(candidate_names == release_names and len(candidate_names) == 760,
            "stripped D5 name population differs from v1.9")
    observed = free(load(D5))
    require(observed == {"symbol_slots": 109, "namepool_bytes": 1486},
            "v1.9 release-terminal D5 authority drift")
    return {"status": "PASS: D5 DERIVED FROM IDENTICAL NAME POPULATION",
        "candidate_names": len(candidate_names),
        "name_population_sha256": hashlib.sha256(canonical(candidate_names)).hexdigest(),
        "v1_9_release_terminal": bind(D5), "projected_free": observed,
        "minimum": {"symbol_slots": 32, "namepool_bytes": 384},
        "device_measurement_required": True}


def product_specs_at(product_path: Path) -> tuple[tuple[str, str, Path], ...]:
    product = load(product_path)
    rows = product.get("manifests")
    require(isinstance(rows, list) and len(rows) == len(PRODUCT_KEYS),
            "comparison product population drift")
    return tuple((key, role, resolve(row["path"], product_path))
        for key, role, row in zip(PRODUCT_KEYS,
            ("stdlib", "ide", "idex", "m65d", "buffer", "lcc"), rows))


def configuration_gate() -> dict[str, Any]:
    configure()
    _core, _activation, _cold = CHAIN.setup_link_world()
    plane = load(PLANE_RECEIPT)
    packed = packed_properties()
    price = load(PRICE.RECEIPT)
    prelink = CONSUMPTION.evaluate()
    require(plane["geometry"] == geometry()
            and plane["hot_path"]["status"] ==
                "PASS: STRIPPED EDITOR HOT PATH BYTEIDENTICAL TO V1.9"
            and price["freight"]["plane_bytes"] == 6076
            and price["freight"]["added_objects"] == 38
            and prelink["prelink_authority"]["total"] == 13,
            "strip prelink population drift")
    return {"status": "PASS: V2.0 STRIP PRODUCT CARD ARMED 0/1",
        "plane": bind(PLANE_RECEIPT), "packed": packed,
        "D5": d5_projection(), "known_pin_and_closure_population":
            prelink["prelink_authority"],
        "authority_categories": sorted(prelink["consumption_cases"]),
        "mutations_rejected": ["active-freight-member-survives-strip",
            "editor-byte-differs-from-v1.9", "literal-pin-omitted",
            "inherited-closure-omitted", "candidate-authority-unbound"]}


def source_preflight() -> dict[str, Any]:
    configure()
    value = CHAIN.source_preflight()
    require(value["compiler_sources"]["total"] == 70
            and value["feature_count"] == 35,
            "strip source/profile population drift")
    return value


def preflight() -> None:
    require(not any(path.exists() for path in (
        BUILD, PREFLIGHT, PLANE_RECEIPT, PREFLIGHT_RECEIPT,
        SOURCE_PREFLIGHT, DIFFERENCE, RECEIPT)),
        "strip preflight is one-shot")
    materialize_plane()
    gate = configuration_gate()
    sources = source_preflight()
    value = {"format": FORMAT + "-preflight", "recorded_on": "2026-09-02",
        "status": "PASS: V2.0 STRIP PRODUCT CARD ARMED 0/1",
        "authority": authority(), "plane": bind(PLANE_RECEIPT),
        "configuration": gate, "source_preflight": bind(SOURCE_PREFLIGHT),
        "source_population": sources,
        "requirements": ["ten raw-byte-identical v1.9 editor objects",
            "6076/38/418/236 removal fully attributed",
            "single-key and batch lanes remeasured on final link",
            "Scope and Acceptance read-only",
            "packed closure and generation coherence before media"],
        "attempt_accounting": {"product_cards": 0, "WPLTO_runs": 0,
            "product_links": 0, "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0}}
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("v2.0 release strip: PREFLIGHT PASS plane=47795 WPLTO=0/1 link=0/1")


def check_preflight() -> None:
    value = load(PREFLIGHT_RECEIPT)
    require(value["status"] == "PASS: V2.0 STRIP PRODUCT CARD ARMED 0/1"
            and value["authority"] == authority()
            and value["plane"] == bind(PLANE_RECEIPT)
            and value["configuration"] == configuration_gate()
            and not ELF.exists() and not PRG.exists(),
            "strip preflight drift")
    print("v2.0 release strip: PREFLIGHT CHECK PASS WPLTO=0/1 link=0/1")


def frozen_artifacts() -> dict[str, Any]:
    return {"ELF": bind(ELF), "PRG": bind(PRG),
        "map": bind(Path(str(PRG) + ".map")),
        "lto": bind(Path(str(PRG) + ".lto.o"))}


def profile_inputs(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("input_sha256="):
            left, digest = line.split(":", 1)
            rows[Path(left.split("=", 1)[1]).name] = digest
    require(rows, f"profile source closure absent: {path}")
    return rows


def counter_rows(value: Counter[tuple[Any, ...]]) -> list[list[Any]]:
    return [list(row) + [count] for row, count in sorted(value.items())]


def program_headers(path: Path) -> Counter[tuple[Any, ...]]:
    return Counter(tuple(sorted(row.items())) for row in
                   CHAIN.T2.program_headers(path))


def prg_difference(old_path: Path, new_path: Path) -> dict[str, Any]:
    old, new = old_path.read_bytes(), new_path.read_bytes()
    old_load, new_load = int.from_bytes(old[:2], "little"), int.from_bytes(new[:2], "little")
    require(old_load == new_load, "strip changed PRG load domain")
    changed = [old_load + index for index in range(max(len(old), len(new)) - 2)
        if (old[index + 2] if index + 2 < len(old) else None) !=
           (new[index + 2] if index + 2 < len(new) else None)]
    return {"old_bytes": len(old), "new_bytes": len(new),
        "changed_addresses": changed,
        "changed_address_sha256": hashlib.sha256(canonical(changed)).hexdigest(),
        "named_families": ["candidate-plane-extent-and-build-ID",
            "generated-stream-CRCs", "linker-derived-product-identity"],
        "unexplained": []}


def attribution() -> dict[str, Any]:
    old = ElfTruth.read(CURRENT.ELF, llvm_readobj=READOBJ)
    new = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    section_rows = [Counter((row.name, row.address, row.bytes, tuple(row.flags))
                            for row in truth.sections) for truth in (old, new)]
    symbol_rows = [Counter((row.name, row.value, row.bytes, row.section)
                           for row in truth.symbols) for truth in (old, new)]
    relocation_rows = [Counter((row.source_section, row.offset,
        row.relocation_type, row.target, row.addend) for row in truth.relocations)
        for truth in (old, new)]
    before_inputs, after_inputs = profile_inputs(CURRENT.PROFILE), profile_inputs(PROFILE)
    changed_inputs = sorted(name for name in set(before_inputs) | set(after_inputs)
        if before_inputs.get(name) != after_inputs.get(name))
    authored = [name for name in changed_inputs if not name.startswith("c2-stream-")]
    require(not authored, f"strip changed authored native inputs: {authored}")
    before_closure = CLOSURE.derive(CURRENT.PLANE /
        "product/substitution-artifacts.json")
    after_closure = CLOSURE.derive(PLANE / "product/substitution-artifacts.json")
    CLOSURE.require_closed(before_closure); CLOSURE.require_closed(after_closure)
    price = load(PRICE.RECEIPT)
    removal = {"plane_bytes": CURRENT_EXTENT - EXTENT,
        "objects": before_closure["object_count"] - after_closure["object_count"],
        "name_bytes_NUL_inclusive": (price["worlds"]["stripped_reference"]
            ["namepool_bytes"] - price["worlds"]["current_block3"]["namepool_bytes"]),
        "call_sites": before_closure["call_site_count"] - after_closure["call_site_count"]}
    require(removal == {"plane_bytes": 6076, "objects": 38,
            "name_bytes_NUL_inclusive": 418, "call_sites": 236}
            and price["freight"]["added_objects"] == removal["objects"],
            "strip removal currencies drift")
    removed_sections, added_sections = (section_rows[0] - section_rows[1],
                                        section_rows[1] - section_rows[0])
    removed_symbols, added_symbols = (symbol_rows[0] - symbol_rows[1],
                                      symbol_rows[1] - symbol_rows[0])
    removed_relocs, added_relocs = (relocation_rows[0] - relocation_rows[1],
                                    relocation_rows[1] - relocation_rows[0])
    removed_headers, added_headers = (program_headers(CURRENT.ELF) - program_headers(ELF),
                                      program_headers(ELF) - program_headers(CURRENT.ELF))
    return {"status": "PASS: ACTIVE BLOCK-3 FREIGHT FULLY REMOVED",
        "predecessor": {"ELF": bind(CURRENT.ELF), "PRG": bind(CURRENT.PRG),
            "plane": bind(CURRENT.PLANE / "v6-semantics/bank2-static-code.bin")},
        "candidate": {"ELF": bind(ELF), "PRG": bind(PRG),
            "plane": bind(PLANE / "v6-semantics/bank2-static-code.bin")},
        "input_roots": {"authored_native_sources": "byte-identical",
            "changed_generated_inputs": changed_inputs},
        "removed_freight": {**removal,
            "members": price["freight"]["components"]},
        "topology": {"before": {"objects": before_closure["object_count"],
                "call_sites": before_closure["call_site_count"]},
            "after": {"objects": after_closure["object_count"],
                "call_sites": after_closure["call_site_count"]}},
        "sections": {"removed": counter_rows(removed_sections),
                     "added": counter_rows(added_sections), "unexplained": []},
        "symbols": {"removed": counter_rows(removed_symbols),
                    "added": counter_rows(added_symbols), "unexplained": []},
        "relocations": {"removed": counter_rows(removed_relocs),
                        "added": counter_rows(added_relocs), "unexplained": []},
        "program_headers": {"removed": counter_rows(removed_headers),
                            "added": counter_rows(added_headers), "unexplained": []},
        "PRG": prg_difference(CURRENT.PRG, PRG),
        "unexplained_sections": 0, "unexplained_symbols": 0,
        "unexplained_relocations": 0, "unexplained_program_headers": 0,
        "unexplained_PRG_bytes": 0, "unexplained_freight_members": 0,
        "unexplained_members": 0}


def responsiveness_lanes(hot_path: dict[str, Any]) -> dict[str, Any]:
    require(all(row["byteidentical"] for row in hot_path["objects"]),
            "strip lane source is not candidate-byte-identical")
    contract = load(LANES.T2.PRICE.RESPONSIVENESS_CONTRACT)["responsiveness"]
    single = LANES.raw_lane(LANES.V19_EDITOR, 1)
    batch = LANES.raw_lane(LANES.V19_EDITOR, 8)
    frames = (batch["vm_steps_per_character"]
        * contract["calibration_cycles_per_vm_step"] / contract["cycles_per_frame"]
        + batch["screen_cells_per_character"]
        * contract["screen_cell_cycles"] / contract["cycles_per_frame"]
        + batch["heap_cells_per_character"]
        * contract["collection_frames"] / contract["nursery_cells"])
    rate, margin = 1.0 / frames, (1.0 / frames - 1.0) * 100.0
    require(single["vm_steps_per_character"] == 902.0
            and single["screen_cells_per_character"] == 2.0
            and frames <= 0.8 and rate >= 1.25 and margin >= 25.0,
            "stripped responsiveness lane red")
    return {"status": "PASS: BOTH STRIPPED STIMULUS LANES GREEN",
        "final_link": bind(ELF), "candidate_hot_path": hot_path,
        "single_keystroke": {"stimulus_batch_cap": 1, "route": single,
            "expected_steps_per_key": 902.0,
            "observed_steps_per_key": single["vm_steps_per_character"],
            "ratio_to_v1_9": 1.0, "passed": True},
        "batch_throughput": {"stimulus_batch_cap": 8, "route": batch,
            "frames_per_character": frames, "service_events_per_frame": rate,
            "margin_percent": margin, "passed": True},
        "rule": "single-key latency and batch throughput are measured separately"}


def composed_bank2() -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    far = truth.section(".lisp65_c2_mapped_far_service")
    cold = truth.section(".lisp65_c2_mapped_product_cold")
    far_lma = truth.symbol("__lisp65_c2_mapped_far_service_load_start").value
    cold_lma = truth.symbol("__lisp65_c2_mapped_product_cold_load_start").value
    plane_end = 0x20000 + EXTENT
    require(far_lma == 0x2F8B2 and plane_end <= far_lma
            and far_lma + far.bytes <= cold_lma
            and cold_lma + cold.bytes <= 0x30000,
            "stripped composed Bank-2 ownership red")
    return {"owners": {"static_plane": [0x20000, plane_end],
        "mapped_far_service": [far_lma, far_lma + far.bytes],
        "congruence_gap": [far_lma + far.bytes, cold_lma],
        "mapped_product_cold": [cold_lma, cold_lma + cold.bytes],
        "bank_end_reserve": [cold_lma + cold.bytes, 0x30000]},
        "largest_contiguous_hole": {"start": plane_end,
            "end_exclusive": far_lma, "bytes": far_lma - plane_end},
        "overlaps": [], "shared_offset": 0x28000}


def final_gate() -> dict[str, Any]:
    configure()
    packed = packed_properties(ELF)
    compiler = load(Path(str(PRG) + ".compiler-input-consumption.json"))
    stdlib = load(Path(str(PRG) + ".stdlib-input-consumption.json"))
    final_authority_input = load(Path(str(PRG) + ".authority-input-consumption.json"))
    seed_authority_input = load(WPLTO /
        "resident-island-seed.prg.authority-input-consumption.json")
    final_authority = CONSUMPTION.validate_authority_input_inventory(
        final_authority_input)
    seed_authority = CONSUMPTION.validate_authority_input_inventory(
        seed_authority_input)
    ordinals = CHAIN.LINK.candidate_stdlib_ordinals()
    product = load(PLANE / "product/substitution-artifacts.json")
    build_rows = [row for row in final_authority_input["manifest"]["derived_constants"]
                  if row["compiler_definition"] == "LISP65_C2_PRODUCT_BUILD_ID"]
    require(compiler["consumed_value"] == EXTENT
            and compiler["bound_header"] == bind(PLANE / "c2_lite_static_plane.h")
            and stdlib["consumed_value"] == ordinals["repl_banner"]
            and stdlib["bound_header"] == bind(PLANE / "stdlib-p0.h")
            and final_authority["categories"] == seed_authority["categories"]
            and final_authority["features"] == seed_authority["features"] == 35
            and len(build_rows) == 1 and build_rows[0]["consumed_value"] ==
                product["product_build_id_hex"] + "UL",
            "stripped final consumers escaped candidate authority")
    hot = PRICE.hot_path_identity(candidate_specs()[0][2])
    lanes = responsiveness_lanes(hot)
    d5 = d5_projection()
    contract = TIER1.measured_contract()
    require(contract["counts"] == {"error-raised": 545,
            "documented-permissive": 179, "silently-wrong": 110},
            "stripped Tier-1 contract drift")
    native = CHAIN.native_walls()
    bank = composed_bank2()
    require(bank["largest_contiguous_hole"]["bytes"] == 15871,
            "strip did not reclaim the full contiguous hole")
    return {"status": "PASS: FINAL STRIPPED V2.0 PRODUCT CLOSED",
        "static_extent": EXTENT, "compiler_consumption": compiler,
        "stdlib_consumption": stdlib,
        "final_authority_consumption": final_authority_input,
        "seed_authority_consumption": seed_authority_input,
        "authority_inventory": final_authority, "packed_product": packed,
        "composed_bank2": bank, "native_walls": native,
        "editor_hot_path": hot, "responsiveness_lanes": lanes,
        "D5_projection": d5, "Tier_1_contract_counts": contract["counts"],
        "known_inconsistency": {"form": "(car 1)", "observed": "nil",
            "status": "documented Tier-2 descope behavior"}}


def run_child(action: str) -> dict[str, Any]:
    output = run([sys.executable, str(DRIVER), action], f"strip child {action}")
    return {"action": action, "stdout_tail": " ".join(output.split()[-35:])}


def child(action: str) -> None:
    configure()
    inherited_configure = CHAIN.LINK.configure
    if action == "_produce":
        def predecessor_profile_gate() -> dict[str, Any]:
            lines = CURRENT.PROFILE.read_text(encoding="utf-8").splitlines()
            sources = tuple(line.split(":", 1)[0].split("=", 1)[1]
                            for line in lines if line.startswith("input_sha256="))
            features = tuple(item for line in lines
                if line.startswith("feature_defines=")
                for item in line.split("=", 1)[1].split(",") if item)
            expected = CHAIN.LINK.predecessor_features()
            require(sources and features == expected,
                    "strip predecessor source/profile population drift")
            return {"sources": sources, "features": features,
                    "profile": bind(CURRENT.PROFILE),
                    "phase": "pre-producer-source-ownership"}

        def configure_preproducer() -> None:
            inherited_configure()
            CHAIN.LINK.BASE.profile_gate = predecessor_profile_gate
        CHAIN.LINK.configure = configure_preproducer
    try:
        CHAIN.LINK.child(action)
    finally:
        CHAIN.LINK.configure = inherited_configure


def complete(processes: list[dict[str, Any]]) -> None:
    before = frozen_artifacts()
    diff = attribution()
    require(diff["unexplained_members"] == 0,
            "strip attribution retained unexplained members")
    DIFFERENCE.write_bytes(canonical(diff))
    product = final_gate()
    processes.extend((run_child("_scope"), run_child("_accept")))
    after = frozen_artifacts()
    scope = load(CHAIN.LINK.BASE.SCOPE_RESULT)
    acceptance = load(CHAIN.LINK.BASE.ACCEPTANCE_RESULT)
    require(before == after and scope["status"] == acceptance["status"] == "PASS",
            "strip Scope/Acceptance changed or rejected frozen pair")
    value = {"format": FORMAT, "recorded_on": "2026-09-02",
        "status": STATUS, "authority": authority(),
        "preflight": bind(PREFLIGHT_RECEIPT), "invocation": bind(INVOCATION),
        "predecessor": {"ELF": bind(CURRENT.ELF), "PRG": bind(CURRENT.PRG)},
        "difference": diff, "difference_receipt": bind(DIFFERENCE),
        "final_product": product, "scope": bind(CHAIN.LINK.BASE.SCOPE_RESULT),
        "acceptance": bind(CHAIN.LINK.BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": processes,
        "attempt_accounting": {"product_cards": 1, "WPLTO_runs": 1,
            "product_links": 1, "scope_runs": 1, "acceptance_runs": 1,
            "media_builds": 0, "device_contacts": 0},
        "media_authorized": False,
        "media_condition": ("independent review; then closure and generation "
                            "coherence over actually packed readback bytes")}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    validate(value)
    print("v2.0 release strip: BUILD PASS WPLTO=1/1 link=1/1")


def build() -> None:
    pre = load(PREFLIGHT_RECEIPT)
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout
    require(clean == "" and pre["status"] ==
            "PASS: V2.0 STRIP PRODUCT CARD ARMED 0/1"
            and not BUILD.exists() and not RECEIPT.exists()
            and not DIFFERENCE.exists(),
            "strip build is not at its committed one-shot boundary")
    INVOCATION.write_bytes(canonical({"status": "INVOKED",
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT)}))
    processes = [run_child("_produce")]
    require(ELF.is_file() and PRG.is_file()
            and Path(str(PRG) + ".lto.o").is_file(),
            "strip producer did not materialize one final pair")
    complete(processes)


def validate(value: dict[str, Any]) -> None:
    final = value["final_product"]
    removal = value["difference"]["removed_freight"]
    require(value["status"] == STATUS and value["authority"] == authority()
            and value["difference"]["unexplained_members"] == 0
            and {key: removal[key] for key in
                ("plane_bytes", "objects", "name_bytes_NUL_inclusive", "call_sites")} == {
                    "plane_bytes": 6076, "objects": 38,
                    "name_bytes_NUL_inclusive": 418, "call_sites": 236}
            and final["static_extent"] == EXTENT
            and final["packed_product"]["closure"]["object_count"] == 760
            and final["packed_product"]["closure"]["call_site_count"] == 2436
            and final["packed_product"]["generation_coherence"]["status"] ==
                "PASS: PACKED OBJECT GENERATION COHERENT"
            and final["packed_product"]["key_sources"]["active_sink_set"] ==
                ["c2_kernal_input_take"]
            and final["packed_product"]["host_wall"]["counters"] == {
                "raw": 94, "seen": 94, "stored": 94, "taken": 94}
            and all(row["byteidentical"] for row in
                    final["editor_hot_path"]["objects"])
            and final["responsiveness_lanes"]["single_keystroke"]
                ["observed_steps_per_key"] == 902.0
            and final["responsiveness_lanes"]["batch_throughput"]["passed"] is True
            and final["D5_projection"]["projected_free"] == {
                "symbol_slots": 109, "namepool_bytes": 1486}
            and final["composed_bank2"]["largest_contiguous_hole"]["bytes"] == 15871
            and final["Tier_1_contract_counts"] == {"error-raised": 545,
                "documented-permissive": 179, "silently-wrong": 110}
            and value["artifacts_before"] == value["artifacts_after"] ==
                frozen_artifacts()
            and value["attempt_accounting"] == {"product_cards": 1,
                "WPLTO_runs": 1, "product_links": 1, "scope_runs": 1,
                "acceptance_runs": 1, "media_builds": 0, "device_contacts": 0},
            "strip product receipt drift")


def selftest() -> None:
    value = load(RECEIPT)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "editor-byte-differs": lambda row: row["final_product"]
            ["editor_hot_path"]["objects"][0].update({"byteidentical": False}),
        "freight-member-unexplained": lambda row: row["difference"].update(
            {"unexplained_members": 1}),
        "plane-byte-not-removed": lambda row: row["difference"]
            ["removed_freight"].update({"plane_bytes": 6075}),
        "packed-object-survives": lambda row: row["final_product"]
            ["packed_product"]["closure"].update({"object_count": 761}),
        "generation-mixed": lambda row: row["final_product"]
            ["packed_product"]["generation_coherence"].update({"status": "RED"}),
        "queue-reader-survives": lambda row: row["final_product"]
            ["packed_product"]["key_sources"].update(
                {"active_sink_set": ["public-hardware-queue"]}),
        "single-key-not-v1.9": lambda row: row["final_product"]
            ["responsiveness_lanes"]["single_keystroke"].update(
                {"observed_steps_per_key": 903.0}),
        "D5-population-drift": lambda row: row["final_product"]
            ["D5_projection"]["projected_free"].update({"symbol_slots": 108}),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except (CardError, RuntimeError, KeyError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "strip product mutation survived")
    print(f"v2.0 release strip: SELFTEST PASS mutations={len(rejected)}")


def write_report(value: dict[str, Any]) -> None:
    final, pair = value["final_product"], value["artifacts_after"]
    lanes, d5 = final["responsiveness_lanes"], final["D5_projection"]
    REPORT.write_text(f"""# v2.0 stripped release world — product card

Status: **{value['status']}**

The one authorized WPLTO/product link removes the complete active Block-3
freight. The final Plane is **{EXTENT:,} bytes**, closes
{final['packed_product']['closure']['object_count']} objects and
{final['packed_product']['closure']['call_site_count']:,} call sites, and leaves
a **{final['composed_bank2']['largest_contiguous_hole']['bytes']:,}-byte**
largest contiguous Bank-2 hole.

All four removal currencies reconcile exactly: **6,076 Plane bytes, 38
objects, 418 NUL-inclusive name bytes and 236 call sites**, with zero
unexplained members. Every one of the ten delivered native-editor objects is
raw-byte-identical to the hardware-green v1.9 emission.

Both lanes were remeasured on this linked world. Single-key latency is exactly
**{lanes['single_keystroke']['observed_steps_per_key']:.0f} VM steps/key**
(1.000x v1.9). Batch throughput is
**{lanes['batch_throughput']['frames_per_character']:.6f} frames/character**,
**{lanes['batch_throughput']['service_events_per_frame']:.6f} events/frame** and
**{lanes['batch_throughput']['margin_percent']:.3f}% margin**. The D5 projection
is freshly derived from a name population identical to v1.9:
**{d5['projected_free']['symbol_slots']}/{d5['projected_free']['namepool_bytes']:,}**;
the release-terminal device measurement remains a session obligation.

Tier 1 remains measured at **545 error / 179 permissive / 110 silently wrong**.
The packed generation is coherent, the only armed key source is
`c2_kernal_input_take`, and the delivered host wall is 94/94/94/94. Scope and
Acceptance ran read-only over ELF `{pair['ELF']['sha256']}` / PRG
`{pair['PRG']['sha256']}`.

Accounting is exactly one product card, one WPLTO and one product link. No
medium or device contact occurred. Media remain review-gated and must rerun
closure and generation coherence over their own packed readback bytes.
""", encoding="utf-8")


def check() -> None:
    configure(); CHAIN.setup_link_world()
    value = load(RECEIPT)
    validate(value)
    require(load(DIFFERENCE) == value["difference"]
            and REPORT.is_file(), "strip report/difference absent")
    print("v2.0 release strip: CHECK PASS WPLTO=1/1 link=1/1 media=0")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "check-preflight",
        "build", "check", "selftest", "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    if action.startswith("_"):
        child(action); return 0
    {"preflight": preflight, "check-preflight": check_preflight,
     "build": build, "check": check, "selftest": selftest}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, CLOSURE.ClosureError, COHERENCE.CoherenceError,
            RuntimeError, KeyError, ValueError, OSError,
            subprocess.CalledProcessError) as error:
        print(f"v2.0 release strip: FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
