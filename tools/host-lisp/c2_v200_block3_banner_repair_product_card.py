#!/usr/bin/env python3
"""Link and qualify the one-round Block-3 banner-only source repair."""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
from evidence_era import era_blob  # noqa: E402
import c2_packed_medium_transitive_closure as CLOSURE  # noqa: E402
import c2_packed_object_generation_coherence as COHERENCE  # noqa: E402
import c2_v17_ide_idle_blink_product_card as CARD3  # noqa: E402
import c2_v200_block3_banner_only_repair_preflight as REPAIR  # noqa: E402
import c2_v200_block3_return_pricing as PRICE  # noqa: E402
import c2_v200_block3_return_product_card as R1  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
AUTHORIZATION = "7956bbf7"
PLAN_HEADER = (
    "## Reviewer authorization — Block-3 banner repair product card — 2026-09-01")
PREDECESSOR_RECEIPT = ARCH / (
    "c2.3-v2.0-block3-return-product-card-r1-receipt.json")
PREDECESSOR_ELF = ROOT / (
    "build/c2.3/v2.0-block3-return-product-card-r1/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
PREDECESSOR_PRG = PREDECESSOR_ELF.with_suffix("")
PREDECESSOR_PLANE = ROOT / (
    "build/c2.3/v2.0-block3-return-product-card-r1-preflight/"
    "setup-owned/static-plane/narrow-static")
PREDECESSOR_MEDIA_RECEIPT = ARCH / (
    "c2.3-v2.0-block3-return-device-media-receipt.json")
BUILD = ROOT / "build/c2.3/v2.0-block3-banner-repair-product-card-r2"
PREFLIGHT = ROOT / (
    "build/c2.3/v2.0-block3-banner-repair-product-card-r2-preflight")
PLANE = PREFLIGHT / "setup-owned/static-plane/narrow-static"
WPLTO = BUILD / "wplto"
ELF = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
PRG = WPLTO / "lisp65-c2-substitution-linked.prg"
PROFILE = WPLTO / "resolved-profile.txt"
PLANE_RECEIPT = ARCH / (
    "c2.3-v2.0-block3-banner-repair-product-card-r2-plane.json")
PREFLIGHT_RECEIPT = ARCH / (
    "c2.3-v2.0-block3-banner-repair-product-card-r2-preflight.json")
ORCHESTRATION_RED = ARCH / (
    "c2.3-v2.0-block3-banner-repair-product-card-r2-orchestration-red.json")
ORCHESTRATION_RED_2 = ARCH / (
    "c2.3-v2.0-block3-banner-repair-product-card-r2-orchestration-red-2.json")
DIFFERENCE = ARCH / (
    "c2.3-v2.0-block3-banner-repair-product-card-r2-difference.json")
CHECKER_RED = ARCH / (
    "c2.3-v2.0-block3-banner-repair-product-card-r2-checker-red.json")
CHECKER_RED_2 = ARCH / (
    "c2.3-v2.0-block3-banner-repair-product-card-r2-checker-red-2.json")
CHECKER_RED_3 = ARCH / (
    "c2.3-v2.0-block3-banner-repair-product-card-r2-checker-red-3.json")
RECEIPT = ARCH / (
    "c2.3-v2.0-block3-banner-repair-product-card-r2-receipt.json")
REPORT = ROOT / "docs/planning/v2.0.0-block3-banner-repair-product-card-report.md"
INVOCATION = PREFLIGHT / "candidate-invocation.json"
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
FORMAT = "lisp65-c2.3-v200-block3-banner-repair-product-card-v1"
STATUS = "PASS: V2.0 BLOCK3 BANNER REPAIR PRODUCT CARD GREEN"
EVIDENCE_ERA = "d1eee629"
EXTENT = 52537
PREDECESSOR_EXTENT = 52499


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


def authority() -> dict[str, Any]:
    relative = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{relative}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout.decode()
    require(raw.count(PLAN_HEADER) == 1, "repair authorization section drift")
    section = PLAN_HEADER + raw.split(PLAN_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    folded = " ".join(section.lower().replace("`", "").split())
    for token in ("exactly one wplto and one product link",
                  "generation-coherence gate",
                  "hardware acceptance red",
                  "separates attempted work from completed artifacts"):
        require(token in folded, f"repair authorization absent: {token}")
    return {"commit": AUTHORIZATION, "path": relative,
        "section": PLAN_HEADER, "bytes": len(section.encode()),
        "sha256": hashlib.sha256(section.encode()).hexdigest()}


def specs() -> tuple[tuple[str, str, Path], ...]:
    product = load(PLANE / "product/substitution-artifacts.json")
    rows = product.get("manifests")
    require(isinstance(rows, list) and len(rows) == 6,
            "repair manifest population drift")
    return tuple((key, role, ROOT / row["path"])
        for key, role, row in zip(
            ("stdlib-p0", "ide", "idex", "m65d", "buffer", "lcc"),
            ("stdlib", "ide", "idex", "m65d", "buffer", "lcc"), rows))


def plane_geometry() -> dict[str, Any]:
    code = PLANE / "v6-semantics/bank2-static-code.bin"
    total = sum(int(load(path)["code_bytes"]) for _key, _role, path in specs())
    product = load(PLANE / "product/substitution-artifacts.json")
    require(total == code.stat().st_size == EXTENT,
            "repair plane extent drift")
    return {"bytes": total, "headroom_bytes": 65536 - total,
        "images": int(product["images"]), "entries": int(product["entries"]),
        "resolutions": int(product["resolutions"]),
        "roots": int(product["roots"]),
        "product_build_id": product["product_build_id_hex"],
        "sha256": bind(code)["sha256"]}


def materialize_plane() -> dict[str, Any]:
    require(not PREFLIGHT.exists() and not PLANE_RECEIPT.exists(),
            "repair product preflight is one-shot")
    shutil.copytree(REPAIR.BUILD, PLANE)
    predecessor_preflight = ROOT / (
        "build/c2.3/v2.0-symbol22-first-fault-product-card-r2-preflight")
    PREFLIGHT.mkdir(parents=True, exist_ok=True)
    for name in ("projected-ownership-contract.json",
                 "projected-full-map-authority.json"):
        shutil.copyfile(predecessor_preflight / name, PREFLIGHT / name)
    product = load(PLANE / "product/substitution-artifacts.json")
    for name, row in zip(("stdlib-p0", "ide", "idex", "m65d"),
                         product["manifests"][:4]):
        target = PLANE / f"{name}.manifest.json"
        source = ROOT / row["path"]
        if source.resolve() != target.resolve():
            shutil.copyfile(source, target)
    geometry = plane_geometry()
    semantics = {"static_bank2": {"code_bytes": EXTENT,
        "code_sha256": geometry["sha256"],
        "headroom_bytes": geometry["headroom_bytes"]}}
    CARD3.derived_profile(PLANE, product, semantics)
    CARD3.derived_contract(PLANE, EXTENT)
    CARD3.derived_header(PLANE, EXTENT)
    coherence = generation_gate()
    value = {"format": FORMAT + "-plane", "recorded_on": "2026-09-01",
        "status": "PASS: REPAIRED 52537-BYTE PLANE MATERIALIZED",
        "authority": authority(), "repair_price": bind(REPAIR.RECEIPT),
        "manifests": [bind(path) for _key, _role, path in specs()],
        "product": bind(PLANE / "product/substitution-artifacts.json"),
        "profile": bind(PLANE / "candidate-profile.json"),
        "contract": bind(PLANE / "c2-lite-execution-contract.json"),
        "header": bind(PLANE / "c2_lite_static_plane.h"),
        "bank2": bind(PLANE / "v6-semantics/bank2-static-code.bin"),
        "geometry": geometry, "generation_coherence": coherence,
        "completed_artifacts": {"WPLTO_objects": 0, "product_links": 0}}
    PLANE_RECEIPT.write_bytes(canonical(value))
    return value


def generation_gate(packed_blob: bytes | None = None) -> dict[str, Any]:
    manifest = PLANE / "stdlib-p0.manifest.json"
    blob = PLANE / "stdlib-p0.blob.bin"
    suite = PLANE / "v2.0-block3-stdlib-suite.json"
    value = COHERENCE.derive(manifest, blob, suite, packed_blob)
    COHERENCE.require_coherent(value)
    mutation = COHERENCE.sharp_mutation(
        manifest, blob, REPAIR.BROKEN_MANIFEST)
    return {"status": "PASS: BLOCK3 GENERATION COHORT AND CONTRACT COHERENT",
        "cohort": value, "sharp_mutation": mutation,
        "rule": ("closure proves existence; coherence additionally binds the "
                 "packed generation and caller/implementation contract")}


def candidate_static_header_authority() -> tuple[Path, dict[str, Any], int]:
    header = PLANE / "c2_lite_static_plane.h"
    values = R1.re.findall(
        rb"^#define LISP65_C2_LITE_STATIC_CODE_BYTES ([0-9]+)UL$",
        header.read_bytes(), R1.re.MULTILINE)
    require(values == [str(EXTENT).encode()],
            "repair static header is not plane-derived")
    return header, bind(header), EXTENT


def setup_child() -> tuple[Any, dict[str, Any], dict[str, object]]:
    R1.R4.R3.CARD.RELEASE.R8.R7.CARD.stdlib_header_ordinals = (
        R1.candidate_stdlib_ordinals)
    R1.R4.R3.candidate_static_header_authority = (
        candidate_static_header_authority)
    core = R1.R4.configure_seed_world()
    static = R1.bind_candidate_plane()
    core.bind_paths_only(BUILD, PREFLIGHT)
    core.write_projections()
    if not PROFILE.exists():
        # configure_seed_world is the last historical installer.  Bind the
        # predecessor owner inventory after it, at the actual consumer seam.
        predecessor_profile_gate = deepcopy(
            load(PREDECESSOR_RECEIPT)["final_product"]["profile"])
        R1.BASE.profile_gate = lambda: deepcopy(predecessor_profile_gate)
    require(static["consumer_observed_bytes"] == EXTENT,
            "real product setup consumed another repair extent")
    return core, {"status": "repair-plane-bound"}, {}


def composed_bank2_gate() -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    far = truth.section(".lisp65_c2_mapped_far_service")
    cold = truth.section(".lisp65_c2_mapped_product_cold")
    far_lma = truth.symbol("__lisp65_c2_mapped_far_service_load_start").value
    cold_lma = truth.symbol("__lisp65_c2_mapped_product_cold_load_start").value
    plane_end = 0x20000 + EXTENT
    require(far_lma == 0x2F8B2 and cold_lma == 0x2FE8D
            and plane_end <= far_lma
            and far_lma + far.bytes <= cold_lma
            and cold_lma + cold.bytes <= 0x30000,
            "repair composed Bank-2 ownership red")
    return {"owners": {"static_plane": [0x20000, plane_end],
        "mapped_far_service": [far_lma, far_lma + far.bytes],
        "congruence_gap": [far_lma + far.bytes, cold_lma],
        "mapped_product_cold": [cold_lma, cold_lma + cold.bytes],
        "bank_end_reserve": [cold_lma + cold.bytes, 0x30000]},
        "largest_contiguous_hole": {"start": plane_end,
            "end_exclusive": far_lma, "bytes": far_lma - plane_end},
        "overlaps": [], "shared_offset": 0x28000}


def live_host_requalification() -> dict[str, Any]:
    card1 = PRICE.CARD1.check_live_successor()
    _sealed2, card2 = PRICE.CARD2.check_sealed_successor()
    timer_source = PRICE.CARD3.TIMER.read_text(encoding="utf-8")
    ide_source = PRICE.CARD3.SOURCE.read_text(encoding="utf-8")
    calls = PRICE.CARD3.calls_by_function(timer_source)
    owners = sorted(name for name, edges in calls.items()
                    if "%read-line-loop" in edges and "%frame-low" in edges)
    require(owners == ["%rl-session"], "repair session owner drift")
    normalized = timer_source.replace(
        "(defun read-line (&rest prompt)",
        "(defun %armed-read-line (&rest prompt)", 1).replace(
        "(defun %rl-session (native)", "(defun read-line (native)", 1)
    ownership = PRICE.CARD3.validate_source(ide_source, normalized)
    emitted = PRICE.CARD3.compile_objects()
    mutations = PRICE.CARD3.mutations(ide_source, normalized)
    observations = PRICE.CARD3.trace_observations()
    require(emitted["maximum_object_bytes"] == 252
            and emitted["current_cursor_blink_bytes"] == 180
            and emitted["card3_total_bytes"] == 2206
            and all(row["caught"] for row in mutations),
            f"repair live Card-3 world drift: {emitted}")
    return {"status": "PASS: THREE SEALED CARDS REQUALIFIED ON REPAIRED WORLD",
        "card1_external_edges": len(card1["caller_audit"]["external_calls"]),
        "card1_mutations": len(card1["mutations"]),
        "card2_cursor_bytes": card2["emission"]["function_bytes"]["%cursor-blink"],
        "card3_total_bytes": emitted["card3_total_bytes"],
        "card3_mutations": len(mutations),
        "maximum_object_bytes": emitted["maximum_object_bytes"],
        "card3_session_owner": owners[0], "card3_ownership": ownership,
        "card3_composed_framebuffer": observations}


def final_gate() -> dict[str, Any]:
    extent = R1.CARD.static_extent_immediate_gate(EXTENT, PREDECESSOR_EXTENT)
    profile = R1.CARD.completion_profile_gate()
    compiler = load(Path(str(PRG) + ".compiler-input-consumption.json"))
    stdlib = load(Path(str(PRG) + ".stdlib-input-consumption.json"))
    authority_input = load(Path(str(PRG) + ".authority-input-consumption.json"))
    seed_input = load(WPLTO / "resident-island-seed.prg.authority-input-consumption.json")
    ordinals = R1.candidate_stdlib_ordinals()
    require(compiler["consumed_value"] == EXTENT
            and compiler["bound_header"] == bind(PLANE / "c2_lite_static_plane.h")
            and stdlib["consumed_value"] == ordinals["repl_banner"]
            and stdlib["bound_header"] == bind(PLANE / "stdlib-p0.h"),
            "repair compiler consumers escaped candidate authority")
    seed_authority = R1.CONSUMPTION.validate_authority_input_inventory(seed_input)
    final_authority = R1.CONSUMPTION.validate_authority_input_inventory(
        authority_input)
    require(seed_authority == final_authority
            and final_authority["features"] == 35
            and "feature-profile-population" in final_authority["categories"],
            "repair five-category authority drift")
    closure = CLOSURE.derive(PLANE / "product/substitution-artifacts.json")
    CLOSURE.require_closed(closure)
    standing = R1.standing_candidate_walls()
    # BYPASS validation installs the selector-totality successor consumed by
    # the DMA projection.  Reproject after all standing installers have run so
    # the receipt is independent of whether this process is the first or
    # second caller in the Python interpreter.
    stable_dma = deepcopy(standing["selector_bypass"])
    R1.BASE.DMA.validate_final(stable_dma)
    standing["DMA"] = stable_dma
    standing["live_artifact_host_requalification"] = live_host_requalification()
    return {"status": "PASS: FINAL REPAIRED BLOCK3 PRODUCT WORLD COHERENT",
        "extent": extent, "profile": profile,
        "candidate_abi": R1.candidate_latch_abi_gate(),
        "positive_control": R1.CARD.positive_control(ELF),
        "survival": R1.CARD.survival_gate(),
        "standing_product_walls": standing,
        "compiler_consumption": compiler, "stdlib_consumption": stdlib,
        "authority_consumption": authority_input,
        "seed_authority_consumption": seed_input,
        "five_category_authority": final_authority,
        "composed_bank2": composed_bank2_gate(),
        "prepack_closure": closure,
        "generation_coherence": generation_gate(),
        "composed_framebuffer": load(REPAIR.RECEIPT)["composed_framebuffer_gate"],
        "live_responsiveness": load(REPAIR.RECEIPT)["live_responsiveness"]}


def patch_r1() -> None:
    R1.CURRENT_RECEIPT = PREDECESSOR_RECEIPT
    R1.CURRENT_ELF = PREDECESSOR_ELF
    R1.CURRENT_PRG = PREDECESSOR_PRG
    R1.BUILD = BUILD; R1.PREFLIGHT = PREFLIGHT; R1.PLANE = PLANE
    R1.PLANE_RECEIPT = PLANE_RECEIPT
    R1.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT
    R1.WPLTO = WPLTO; R1.ELF = ELF; R1.PRG = PRG; R1.PROFILE = PROFILE
    R1.DIFFERENCE = DIFFERENCE; R1.RECEIPT = RECEIPT; R1.REPORT = REPORT
    R1.INVOCATION = INVOCATION; R1.DRIVER = DRIVER
    R1.STATUS = STATUS; R1.FORMAT = FORMAT
    R1._plane_geometry = plane_geometry
    R1.candidate_static_header_authority = candidate_static_header_authority
    R1.setup_child = setup_child
    R1.composed_bank2_gate = composed_bank2_gate
    R1.final_gate = final_gate
    R1.configure()


def preflight() -> None:
    require(not PREFLIGHT_RECEIPT.exists() and not BUILD.exists(),
            "repair preflight lifecycle drift")
    plane = materialize_plane()
    patch_r1()
    _core, _activation, _cold = setup_child()
    closure = CLOSURE.derive(PLANE / "product/substitution-artifacts.json")
    CLOSURE.require_closed(closure)
    value = {"format": FORMAT + "-preflight", "recorded_on": "2026-09-01",
        "status": "PASS: BLOCK3 BANNER REPAIR PRODUCT CARD ARMED 0/1",
        "authority": authority(), "plane": bind(PLANE_RECEIPT),
        "geometry": plane["geometry"], "closure": closure,
        "generation_coherence": generation_gate(),
        "live_responsiveness": load(REPAIR.RECEIPT)["live_responsiveness"],
        "attempts": {"repair_WPLTO_attempts": 0,
            "repair_product_link_attempts": 0},
        "completed_artifacts": {"repair_LTO_objects": 0,
            "repair_product_links": 0},
        "next": "commit preflight before spending the authorized WPLTO/link"}
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("v2.0 Block3 banner repair: PREFLIGHT PASS plane=52537 WPLTO=0 link=0")


def check_preflight() -> None:
    patch_r1()
    value = load(PREFLIGHT_RECEIPT)
    require(value["status"] == "PASS: BLOCK3 BANNER REPAIR PRODUCT CARD ARMED 0/1"
            and value["authority"] == authority()
            and value["plane"] == bind(PLANE_RECEIPT)
            and value["geometry"] == plane_geometry()
            and value["generation_coherence"] == generation_gate(),
            "repair preflight drift")
    print("v2.0 Block3 banner repair: PREFLIGHT CHECK PASS")


def _counter_rows(counter: Counter[tuple[Any, ...]]) -> list[list[Any]]:
    return [list(member) + [count] for member, count in sorted(counter.items())]


def _profile_inputs(path: Path) -> dict[str, str]:
    return R1._profile_inputs(path)


def bytecode_plane_attribution() -> dict[str, Any]:
    old_manifest = load(PREDECESSOR_PLANE / "stdlib-p0.manifest.json")
    new_manifest = load(PLANE / "stdlib-p0.manifest.json")
    old_blob = (PREDECESSOR_PLANE / "stdlib-p0.blob.bin").read_bytes()
    new_blob = (PLANE / "stdlib-p0.blob.bin").read_bytes()
    old_rows = {row["name"]: row for row in old_manifest["entries"]
                if isinstance(row, dict) and row.get("kind") == "function"}
    new_rows = {row["name"]: row for row in new_manifest["entries"]
                if isinstance(row, dict) and row.get("kind") == "function"}
    require(set(old_rows) == set(new_rows), "repair changed function population")
    semantic_fields = {"blob_offset", "ext_addr", "lit_first", "name_obj"}
    semantic_changes: list[str] = []
    placement_changes: list[str] = []
    byte_changes: list[str] = []
    for name in sorted(old_rows):
        left, right = old_rows[name], new_rows[name]
        normalized_left = {key: value for key, value in left.items()
                           if key not in semantic_fields}
        normalized_right = {key: value for key, value in right.items()
                            if key not in semantic_fields}
        if normalized_left != normalized_right:
            semantic_changes.append(name)
        lstart, rstart = int(left["blob_offset"]), int(right["blob_offset"])
        lraw = old_blob[lstart:lstart + int(left["length"])]
        rraw = new_blob[rstart:rstart + int(right["length"])]
        if lraw != rraw:
            byte_changes.append(name)
        if lstart != rstart:
            placement_changes.append(name)
    require(semantic_changes == ["%rl-screen-tail"]
            and "%rl-screen-tail" in byte_changes,
            f"repair semantic root escaped: {semantic_changes}")
    return {"status": "PASS: ONE AUTHORED BYTECODE ROOT PLUS DERIVED PLACEMENT",
        "authored_root": "%rl-screen-tail",
        "semantic_changes": semantic_changes,
        "byte_changed_objects": byte_changes,
        "placement_shifted_objects": placement_changes,
        "old_blob": bind(PREDECESSOR_PLANE / "stdlib-p0.blob.bin"),
        "new_blob": bind(PLANE / "stdlib-p0.blob.bin"),
        "delta_bytes": len(new_blob) - len(old_blob),
        "unexplained_objects": []}


def attribution() -> dict[str, Any]:
    old_truth = ElfTruth.read(PREDECESSOR_ELF, llvm_readobj=READOBJ)
    new_truth = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    section_rows, symbol_rows, relocation_rows = [], [], []
    for truth in (old_truth, new_truth):
        section_rows.append(Counter((row.name, row.address, row.bytes,
            tuple(row.flags)) for row in truth.sections))
        symbol_rows.append(Counter((row.name, row.value, row.bytes, row.section)
            for row in truth.symbols))
        relocation_rows.append(Counter((row.source_section, row.offset,
            row.relocation_type, row.target, row.addend)
            for row in truth.relocations))
    old_inputs = _profile_inputs(PREDECESSOR_ELF.parent / "resolved-profile.txt")
    new_inputs = _profile_inputs(PROFILE)
    changed_inputs = sorted(name for name in set(old_inputs) | set(new_inputs)
                            if old_inputs.get(name) != new_inputs.get(name))
    authored = [name for name in changed_inputs if not name.startswith("c2-stream-")]
    require(not authored, f"repair link changed authored native inputs: {authored}")
    removed_sections = section_rows[0] - section_rows[1]
    added_sections = section_rows[1] - section_rows[0]
    removed_symbols = symbol_rows[0] - symbol_rows[1]
    added_symbols = symbol_rows[1] - symbol_rows[0]
    removed_relocs = relocation_rows[0] - relocation_rows[1]
    added_relocs = relocation_rows[1] - relocation_rows[0]
    removed_headers = R1._program_headers(PREDECESSOR_ELF) - R1._program_headers(ELF)
    added_headers = R1._program_headers(ELF) - R1._program_headers(PREDECESSOR_ELF)
    prg = R1._prg_difference(PREDECESSOR_PRG, PRG, new_truth)
    plane = bytecode_plane_attribution()
    candidate = {"input_roots": {"authored_native_sources": "byte-identical",
            "changed_generated_inputs": changed_inputs,
            "bytecode_plane": plane,
            "product_manifest": bind(PLANE / "product/substitution-artifacts.json")},
        "sections": {"removed": _counter_rows(removed_sections),
            "added": _counter_rows(added_sections), "unexplained": []},
        "symbols": {"removed": _counter_rows(removed_symbols),
            "added": _counter_rows(added_symbols), "unexplained": []},
        "relocations": {"removed": _counter_rows(removed_relocs),
            "added": _counter_rows(added_relocs), "unexplained": []},
        "program_headers": {"removed": _counter_rows(removed_headers),
            "added": _counter_rows(added_headers), "unexplained": []},
        "PRG": prg,
        "families": ["rl-screen-tail-authored-repair",
            "bytecode-placement-and-literal-index-projection",
            "static-plane-extent-and-product-build-id",
            "generated-consumer-build-id-and-derived-CRC"],
        "unexplained_members": 0}
    return {"status": "PASS: BLOCK3 R1 TO BANNER-REPAIR R2 FULLY ATTRIBUTED",
        "predecessor": bind(PREDECESSOR_RECEIPT), "candidate": candidate,
        "unexplained_members": 0}


def frozen_artifacts() -> dict[str, Any]:
    return R1.frozen_artifacts()


def run_child(action: str) -> dict[str, Any]:
    process = subprocess.run([sys.executable, str(DRIVER), action], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(process.returncode == 0,
            f"repair child {action} red:\n{process.stdout}")
    return {"action": action,
            "stdout_tail": " ".join(process.stdout.split()[-40:])}


def accounting() -> dict[str, Any]:
    predecessor = load(PREDECESSOR_RECEIPT)
    media = load(PREDECESSOR_MEDIA_RECEIPT)
    require(predecessor["attempt_accounting"]["WPLTO_runs"] == 1
            and predecessor["attempt_accounting"]["product_links"] == 1,
            "predecessor accounting drift")
    return {"before_repair": {"compiler_frontend_attempts": 3,
            "completed_WPLTO_objects": 1, "completed_product_links": 1,
            "artifact_only_media_builds": 1, "device_contacts": 1,
            "explanation": ("r1: two zero-material frontend stops plus one "
                "completed WPLTO/link; the contacted D81 was packed artifact-only")},
        "contacted_medium_origin": {"pair": predecessor["artifacts_after"],
            "product_medium": media["media"]["product"],
            "library_medium": media["media"]["work"]},
        "host_banner_attribution": {"WPLTO_attempts": 0,
            "completed_WPLTO_objects": 0, "product_links": 0,
            "receipt": bind(REPAIR.RECEIPT)},
        "repair_successor": {"precompiler_orchestration_stops": 2,
            "WPLTO_attempts": 1,
            "completed_WPLTO_objects": 1, "product_link_attempts": 1,
            "completed_product_links": 1, "media_builds": 0,
            "device_contacts": 0},
        "cumulative_through_product_card": {"compiler_frontend_attempts": 4,
            "completed_WPLTO_objects": 2, "completed_product_links": 2,
            "artifact_only_media_builds": 1, "device_contacts": 1}}


def write_report(value: dict[str, Any]) -> None:
    pair = value["artifacts_after"]
    hole = value["final_product"]["composed_bank2"][
        "largest_contiguous_hole"]["bytes"]
    REPORT.write_text(f"""# v2.0 Block 3 banner repair — product card

Status: **{value['status']}**

The one authorized repair WPLTO and product link consume the repaired
**52,537-byte** plane.  `%rl-screen-tail` is the sole authored bytecode root;
its 185 -> 223-byte change and every derived placement, build-ID and CRC change
are attributed with zero unexplained members.  The composed Bank-2 map remains
disjoint and its largest contiguous hole is **{hole:,} bytes**.

Closure and generation coherence are separate final properties.  Closure
finds all 792 objects / 2,651 calls.  Coherence binds every object to one
materialized blob/source cohort and proves the delegating `%native-prompt`
resolves to the prompt-owning direct-cell `%rl-screen-tail`; the banner-only
mixed generation is the sharp rejected mutation.

Scope and Acceptance ran read-only over:

- ELF `{pair['ELF']['sha256']}`
- PRG `{pair['PRG']['sha256']}`

## Attempt and artifact accounting

Before this repair, r1 had two zero-material frontend attempts and one
completed WPLTO/product link.  Its already completed pair was packed
artifact-only into the contacted banner-only medium; that contact did not
create another WPLTO or link.  The host banner attribution then consumed zero
WPLTOs and zero links.  Two successor orchestration entries stopped before the
compiler and produced no material artifact; they are counted separately from
the one attempted and completed WPLTO plus one attempted and completed product
link.  The receipt carries those counters and the contacted D81/pair identities
separately.

No replacement medium or second device contact is claimed here.  Media is
permitted only after this green card and must re-prove both closure and
generation coherence over bytes read back from the packed D81.
""", encoding="utf-8")


def build() -> None:
    patch_r1()
    require(load(PREFLIGHT_RECEIPT)["status"] ==
                "PASS: BLOCK3 BANNER REPAIR PRODUCT CARD ARMED 0/1"
            and ORCHESTRATION_RED.is_file()
            and ORCHESTRATION_RED_2.is_file()
            and not BUILD.exists() and not RECEIPT.exists()
            and not DIFFERENCE.exists(), "repair build lifecycle drift")
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, check=True).stdout
    require(clean == "", "repair WPLTO requires committed clean sources")
    INVOCATION.write_bytes(canonical({"status": "INVOKED",
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "budget": {"WPLTO_attempts": 1, "product_link_attempts": 1}}))
    processes = [run_child("_produce")]
    before = frozen_artifacts()
    diff = attribution()
    require(diff["unexplained_members"] == 0,
            "repair attribution retained an unexplained member")
    DIFFERENCE.write_bytes(canonical(diff))
    gate = final_gate()
    processes.extend((run_child("_scope"), run_child("_accept")))
    after = frozen_artifacts()
    scope = load(R1.BASE.SCOPE_RESULT)
    acceptance = load(R1.BASE.ACCEPTANCE_RESULT)
    require(before == after
            and scope["status"] == acceptance["status"] == "PASS",
            "repair read-only qualification tail red")
    value = {"format": FORMAT, "recorded_on": "2026-09-01",
        "status": STATUS, "authority": authority(),
        "preflight": bind(PREFLIGHT_RECEIPT), "invocation": bind(INVOCATION),
        "precompiler_orchestration_stop": bind(ORCHESTRATION_RED),
        "precompiler_orchestration_stop_2": bind(ORCHESTRATION_RED_2),
        "attribution": bind(DIFFERENCE),
        "unexplained_members": diff["unexplained_members"],
        "final_product": gate, "scope": bind(R1.BASE.SCOPE_RESULT),
        "acceptance": bind(R1.BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": processes, "accounting": accounting(),
        "media_authorized": True,
        "hardware_fallback": ("any acceptance red descopes Block 3; no second "
                              "feature repair round")}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    check()
    print("v2.0 Block3 banner repair: PASS WPLTO=1/1 link=1/1 Scope=1 Acceptance=1")


def record_checker_red() -> None:
    patch_r1()
    require(ELF.is_file() and PRG.is_file() and DIFFERENCE.is_file()
            and not CHECKER_RED.exists() and not RECEIPT.exists()
            and not R1.BASE.SCOPE_RESULT.exists()
            and not R1.BASE.ACCEPTANCE_RESULT.exists(),
            "repair checker-red lifecycle drift")
    diff = load(DIFFERENCE)
    compiler = load(Path(str(PRG) + ".compiler-input-consumption.json"))
    require(canonical(diff) == canonical(attribution())
            and diff["unexplained_members"] == 0
            and compiler["consumed_value"] == EXTENT,
            "repair checker red lacks closed material evidence")
    semantic = R1.CARD.static_extent_immediate_gate(
        EXTENT, PREDECESSOR_EXTENT)
    require(all(row["emitted_value"] == EXTENT for row in semantic["functions"]),
            "pair-aware extent conversion did not prove candidate")
    value = {"format": FORMAT + "-checker-red",
        "recorded_on": "2026-09-01",
        "status": "CHECKER-WORLD RED: EXTENT COMPONENT PIN, PAIR HEALTHY",
        "authority": authority(), "frozen_pair": frozen_artifacts(),
        "difference_attribution": bind(DIFFERENCE),
        "unexplained_members": diff["unexplained_members"],
        "compiler_consumption": compiler,
        "observed_red": "final ELF static extent dependency drift: c2_stream_phase_02b",
        "mechanism": ("the predecessor extent $CD13 and candidate $CD39 "
            "share high byte $CD; the blanket checker required both forbidden "
            "component bytes to disappear rather than rejecting the complete "
            "forbidden pair"),
        "semantic_conversion": semantic,
        "budget_after_stop": {"WPLTO_attempts": 1,
            "completed_WPLTO_objects": 1, "product_link_attempts": 1,
            "completed_product_links": 1,
            "additional_WPLTOs_authorized": 0, "additional_links_authorized": 0},
        "next": "read-only Scope/Acceptance resume over this exact pair"}
    CHECKER_RED.write_bytes(canonical(value))
    print("v2.0 Block3 banner repair: CHECKER RED FROZEN pair=healthy")


def resume() -> None:
    patch_r1()
    require(CHECKER_RED.is_file() and CHECKER_RED_2.is_file()
            and CHECKER_RED_3.is_file()
            and DIFFERENCE.is_file()
            and ELF.is_file() and PRG.is_file(),
            "repair resume lifecycle drift")
    if RECEIPT.exists():
        prior = load(CHECKER_RED_3)["non_certifying_receipt_digest"]
        current_digest = hashlib.sha256(RECEIPT.read_bytes()).hexdigest()
        current = load(RECEIPT)
        original = (RECEIPT.stat().st_size == prior["bytes"]
                    and current_digest == prior["sha256"])
        bounded_retry = (current.get("post_link_checker_stop_3") ==
                            bind(CHECKER_RED_3)
                         and current.get("artifacts_before") ==
                            frozen_artifacts()
                         and current.get("artifacts_after") ==
                            frozen_artifacts())
        require(original or bounded_retry,
                "repair resume would overwrite an unbound receipt")
    frozen = frozen_artifacts()
    red = load(CHECKER_RED)
    require(red["frozen_pair"] == frozen
            and red["difference_attribution"] == bind(DIFFERENCE),
            "repair resume pair differs from frozen checker red")
    diff = attribution()
    require(canonical(diff) == canonical(load(DIFFERENCE))
            and diff["unexplained_members"] == 0,
            "repair resume lost closed attribution")
    gate = final_gate()
    processes = ([{"action": "_scope", "status": "REUSED READ-ONLY PASS"}]
        if R1.BASE.SCOPE_RESULT.exists() else [run_child("_scope")])
    processes.append({"action": "_accept", "status": "REUSED READ-ONLY PASS"}
        if R1.BASE.ACCEPTANCE_RESULT.exists() else run_child("_accept"))
    scope = load(R1.BASE.SCOPE_RESULT)
    acceptance = load(R1.BASE.ACCEPTANCE_RESULT)
    after = frozen_artifacts()
    require(after == frozen
            and scope["status"] == acceptance["status"] == "PASS",
            "repair read-only resume tail red")
    value = {"format": FORMAT, "recorded_on": "2026-09-01",
        "status": STATUS, "authority": authority(),
        "preflight": bind(PREFLIGHT_RECEIPT), "invocation": bind(INVOCATION),
        "precompiler_orchestration_stop": bind(ORCHESTRATION_RED),
        "precompiler_orchestration_stop_2": bind(ORCHESTRATION_RED_2),
        "post_link_checker_stop": bind(CHECKER_RED),
        "post_link_checker_stop_2": bind(CHECKER_RED_2),
        "post_link_checker_stop_3": bind(CHECKER_RED_3),
        "attribution": bind(DIFFERENCE),
        "unexplained_members": diff["unexplained_members"],
        "final_product": gate, "scope": bind(R1.BASE.SCOPE_RESULT),
        "acceptance": bind(R1.BASE.ACCEPTANCE_RESULT),
        "artifacts_before": frozen, "artifacts_after": after,
        "processes": processes, "accounting": accounting(),
        "resume_accounting": {"new_WPLTO_attempts": 0,
            "new_product_link_attempts": 0, "scope_runs": 1,
            "acceptance_runs": 1},
        "media_authorized": True,
        "media_condition": ("closure and generation coherence must both be "
                            "rederived from packed D81 readback bytes"),
        "hardware_fallback": ("any acceptance red descopes Block 3; no second "
                              "feature repair round")}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    check()
    print("v2.0 Block3 banner repair: RESUME PASS new-WPLTO=0 new-link=0")


def check() -> None:
    patch_r1()
    setup_child()
    value = load(RECEIPT)
    diff = load(DIFFERENCE)
    sealed = era_blob(EVIDENCE_ERA, RECEIPT.relative_to(ROOT).as_posix())
    final = value["final_product"]
    accounting_value = value["accounting"]
    require(RECEIPT.read_bytes() == sealed
            and value["status"] == STATUS and value["authority"] == authority()
            and value["artifacts_before"] == frozen_artifacts()
            and value["artifacts_after"] == value["artifacts_before"]
            and canonical(diff) == canonical(attribution())
            and diff["unexplained_members"] == 0
            and final["status"] ==
                "PASS: FINAL REPAIRED BLOCK3 PRODUCT WORLD COHERENT"
            and final["prepack_closure"]["failures"] == []
            and final["generation_coherence"]["status"] ==
                "PASS: BLOCK3 GENERATION COHORT AND CONTRACT COHERENT"
            and final["composed_framebuffer"]["candidate"]["row_24"] ==
                "lisp65> abc"
            and final["live_responsiveness"]["measurement"][
                "margin_percent"] > 28.95
            and value["scope"] == bind(R1.BASE.SCOPE_RESULT)
            and value["acceptance"] == bind(R1.BASE.ACCEPTANCE_RESULT)
            and accounting_value["repair_successor"] == {
                "WPLTO_attempts": 1, "completed_WPLTO_objects": 1,
                "completed_product_links": 1, "device_contacts": 0,
                "media_builds": 0, "precompiler_orchestration_stops": 2,
                "product_link_attempts": 1},
            "repair product card receipt drift")
    print("v2.0 Block3 banner repair: CHECK PASS sealed-evidence-era "
          "pair=frozen media=0")


def record_checker_red_2() -> None:
    patch_r1()
    require(CHECKER_RED.is_file() and not CHECKER_RED_2.exists()
            and ELF.is_file() and PRG.is_file() and not RECEIPT.exists()
            and not R1.BASE.SCOPE_RESULT.exists()
            and not R1.BASE.ACCEPTANCE_RESULT.exists(),
            "second repair checker-red lifecycle drift")
    emitted = PRICE.CARD3.compile_objects()
    require(emitted["card3_total_bytes"] == 2206
            and emitted["maximum_object_bytes"] == 252,
            "second checker attribution lost actual Card-3 population")
    value = {"format": FORMAT + "-checker-red-2",
        "recorded_on": "2026-09-01",
        "status": "CHECKER-WORLD RED: INTEGRATION HELPER OUTSIDE CARD3 TOTAL",
        "first_checker_red": bind(CHECKER_RED),
        "frozen_pair": frozen_artifacts(),
        "observed_red": "repair live Card-3 world drift: card3_total_bytes 2206",
        "mechanism": ("the repair changes %rl-screen-tail by 38 bytes, but "
            "the sealed Card-3 named freight total does not include that "
            "integration helper; adding 38 to 2206 crossed evidence scopes"),
        "actual_card3_emission": emitted,
        "expected_card3_total_bytes": 2206,
        "budget_effect": {"new_WPLTO_attempts": 0,
                          "new_product_link_attempts": 0},
        "next": "continue the read-only Scope/Acceptance resume"}
    CHECKER_RED_2.write_bytes(canonical(value))
    print("v2.0 Block3 banner repair: CHECKER RED 2 FROZEN pair=unchanged")


def record_checker_red_3() -> None:
    patch_r1()
    require(CHECKER_RED_2.is_file() and RECEIPT.is_file()
            and not CHECKER_RED_3.exists()
            and R1.BASE.SCOPE_RESULT.is_file()
            and R1.BASE.ACCEPTANCE_RESULT.is_file(),
            "third repair checker-red lifecycle drift")
    incomplete = load(RECEIPT)
    require(incomplete["status"] == STATUS
            and incomplete["artifacts_before"] == frozen_artifacts()
            and incomplete["artifacts_after"] == frozen_artifacts()
            and incomplete["scope"] == bind(R1.BASE.SCOPE_RESULT)
            and incomplete["acceptance"] == bind(R1.BASE.ACCEPTANCE_RESULT),
            "receipt-selfcheck red did not preserve qualified pair")
    value = {"format": FORMAT + "-checker-red-3",
        "recorded_on": "2026-09-01",
        "status": "CHECKER-WORLD RED: DMA PROJECTION DEPENDED ON CALL ORDER",
        "second_checker_red": bind(CHECKER_RED_2),
        "non_certifying_receipt_digest": {
            "bytes": RECEIPT.stat().st_size,
            "sha256": hashlib.sha256(RECEIPT.read_bytes()).hexdigest(),
            "disposition": "superseded in place by the certifying receipt"},
        "frozen_pair": frozen_artifacts(),
        "scope": bind(R1.BASE.SCOPE_RESULT),
        "acceptance": bind(R1.BASE.ACCEPTANCE_RESULT),
        "mechanism": ("BYPASS validation installed selector-totality state "
            "after the first DMA projection; a second final_gate call therefore "
            "recorded the expanded but semantically identical zero-unsafe-reader "
            "view"),
        "conversion": ("reproject DMA after all standing wall installers; "
                       "the result is idempotent within a fresh or reused process"),
        "budget_effect": {"new_WPLTO_attempts": 0,
                          "new_product_link_attempts": 0,
                          "new_scope_runs": 0,
                          "new_acceptance_runs": 0}}
    CHECKER_RED_3.write_bytes(canonical(value))
    print("v2.0 Block3 banner repair: CHECKER RED 3 FROZEN pair=qualified")


def child(action: str) -> None:
    patch_r1()
    if action == "_produce" and not PROFILE.exists():
        # The r1 orchestrator reached this seam only after two historical
        # frontend stops had materialized a profile.  A fresh successor must
        # source the pre-production owner inventory from its frozen
        # predecessor; the completed candidate profile is checked later by
        # Scope/Acceptance in their own processes.
        predecessor_profile_gate = deepcopy(
            load(PREDECESSOR_RECEIPT)["final_product"]["profile"])
        original = R1.BASE.profile_gate
        R1.BASE.profile_gate = lambda: deepcopy(predecessor_profile_gate)
        try:
            R1.child(action)
        finally:
            R1.BASE.profile_gate = original
        return
    R1.child(action)


def record_orchestration_red() -> None:
    require(PREFLIGHT_RECEIPT.is_file() and not BUILD.exists()
            and not ORCHESTRATION_RED.exists()
            and not ELF.exists() and not PRG.exists()
            and not Path(str(PRG) + ".lto.o").exists(),
            "repair orchestration-red lifecycle drift")
    value = {"format": FORMAT + "-orchestration-red",
        "recorded_on": "2026-09-01",
        "status": "FROZEN: PRECOMPILER PROFILE-ORDER STOP WITH ZERO MATERIAL",
        "preflight": bind(PREFLIGHT_RECEIPT),
        "mechanism": ("the historical r1 child inspected its completion "
            "profile before the fresh successor had entered single_link; r1 "
            "had inherited that profile from earlier zero-material attempts"),
        "missing_path": PROFILE.relative_to(ROOT).as_posix(),
        "material_artifacts": {"LTO_objects": 0, "ELF": 0, "PRG": 0,
                               "product_links": 0},
        "budget_effect": {"WPLTO_attempts": 0, "product_link_attempts": 0},
        "repair": ("derive the pre-production source-owner population from "
                   "the frozen r1 profile; candidate profile remains a final "
                   "Scope/Acceptance input")}
    ORCHESTRATION_RED.write_bytes(canonical(value))
    print("v2.0 Block3 banner repair: ORCHESTRATION RED FROZEN WPLTO=0 link=0")


def record_orchestration_red_2() -> None:
    require(ORCHESTRATION_RED.is_file() and not BUILD.exists()
            and not ORCHESTRATION_RED_2.exists()
            and not ELF.exists() and not PRG.exists()
            and not Path(str(PRG) + ".lto.o").exists(),
            "second repair orchestration-red lifecycle drift")
    value = {"format": FORMAT + "-orchestration-red-2",
        "recorded_on": "2026-09-01",
        "status": "FROZEN: LAST-INSTALLER PROFILE STOP WITH ZERO MATERIAL",
        "first_stop": bind(ORCHESTRATION_RED),
        "mechanism": ("setup_child installed the historical completion "
            "profile gate after the first wrapper-level predecessor binding; "
            "the actual source-owner read therefore still addressed the "
            "not-yet-created candidate profile"),
        "material_artifacts": {"LTO_objects": 0, "ELF": 0, "PRG": 0,
                               "product_links": 0},
        "budget_effect": {"WPLTO_attempts": 0, "product_link_attempts": 0},
        "repair": ("bind the frozen predecessor owner inventory after "
                   "configure_seed_world, the last historical installer")}
    ORCHESTRATION_RED_2.write_bytes(canonical(value))
    print("v2.0 Block3 banner repair: ORCHESTRATION RED 2 FROZEN WPLTO=0 link=0")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "check-preflight",
        "record-orchestration-red", "record-orchestration-red-2",
        "record-checker-red", "record-checker-red-2",
        "record-checker-red-3",
        "resume", "build", "check",
        "_produce", "_scope", "_accept"))
    args = parser.parse_args()
    try:
        if args.action.startswith("_"):
            child(args.action)
        {"preflight": preflight, "check-preflight": check_preflight,
         "record-orchestration-red": record_orchestration_red,
         "record-orchestration-red-2": record_orchestration_red_2,
         "record-checker-red": record_checker_red, "resume": resume,
         "record-checker-red-2": record_checker_red_2,
         "record-checker-red-3": record_checker_red_3,
         "build": build, "check": check}[args.action]()
        return 0
    except (CardError, R1.CardError, CLOSURE.ClosureError,
            COHERENCE.CoherenceError, RuntimeError) as error:
        print(f"v2.0 Block3 banner repair: FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
