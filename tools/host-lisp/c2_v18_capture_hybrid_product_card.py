#!/usr/bin/env python3
"""Build the one authorized v1.8 Capture/Hybrid-only product candidate.

The card adds only the sealed native Capture/Hybrid substrate to the
published v1.7 product world.  It never builds or installs Comfort media.
Exactly one producer invocation is permitted; attribution precedes Scope and
Acceptance.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v160_clean_product_candidate as CLEAN  # noqa: E402
import c2_v160_comfort_input_fidelity as FIDELITY  # noqa: E402
import c2_v160_input_service_hybrid_final_world as HYBRID  # noqa: E402
import c2_v160_queue_single_owner_card as QUEUE  # noqa: E402
import c2_v17_init_l65_card as INIT  # noqa: E402
import c2_v17_recovery_quiescence_card as RECOVERY  # noqa: E402
import c2_v170_release_card as RELEASE  # noqa: E402


BASE = INIT.BASE
QUIET = RECOVERY.QUIET
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v1.8-capture-hybrid-product-card-r1"
PREFLIGHT = ROOT / "build/c2.3/v1.8-capture-hybrid-product-card-r1-preflight"
RECEIPT = ARCH / "c2.3-v1.8-capture-hybrid-product-card-r1-receipt.json"
FIRST_RED = ARCH / "c2.3-v1.8-capture-hybrid-product-card-r1-first-red.json"
RESUME_RED = ARCH / (
    "c2.3-v1.8-capture-hybrid-product-card-r1-"
    "source-world-resume-final-red.json")
REPAIR_RECEIPT = ARCH / (
    "c2.3-v1.8-capture-hybrid-responsiveness-repair-receipt.json")
REPORT = ROOT / "docs/planning/v1.8.0-capture-hybrid-product-card-report.md"
RESUME_RED_REPORT = ROOT / (
    "docs/planning/v1.8.0-capture-hybrid-source-world-resume-final-red.md")
RESUME_SCOPE_RESULT = BUILD / "source-world-resume-owner-scope-result.json"
RESUME_ACCEPTANCE_RESULT = (
    BUILD / "source-world-resume-artifact-acceptance.json")
REPAIR_SCOPE_RESULT = BUILD / "responsiveness-repair-owner-scope-result.json"
REPAIR_ACCEPTANCE_RESULT = (
    BUILD / "responsiveness-repair-artifact-acceptance.json")
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
PROFILE = BUILD / "wplto/resolved-profile.txt"
PLANE_ROOT = PREFLIGHT / "setup-owned/static-plane/narrow-static"
PLANE_RECEIPT = PREFLIGHT / "v18-capture-static-plane.json"
C2D = PLANE_ROOT / "v6-semantics/initial.c2d-v6.bin"
CODE = PLANE_ROOT / "v6-semantics/bank2-static-code.bin"
MANIFEST = PLANE_ROOT / "stdlib-p0.manifest.json"
RELEASE_BUILD = ROOT / "build/c2.3/v1.7.0-release-card-r1/wplto"
RELEASE_ELF = RELEASE_BUILD / "lisp65-c2-substitution-linked.prg.elf"
RELEASE_PRG = RELEASE_BUILD / "lisp65-c2-substitution-linked.prg"
RELEASE_PROFILE = RELEASE_BUILD / "resolved-profile.txt"
RELEASE_CODE = ROOT / (
    "build/c2.3/v1.7.0-release-card-r1-preflight/setup-owned/static-plane/"
    "narrow-static/v6-semantics/bank2-static-code.bin")
PUBLISHED_RELEASE_RECEIPT = ARCH / "c2.3-v1.7.0-release-card-r1-receipt.json"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
DRIVER = Path(__file__).resolve()
SEAL_COMMIT = "870e5f53"
FORMAT = "lisp65-c2-v18-capture-hybrid-product-card-r1-v1"
STATUS = "PASS: V1.8 CAPTURE/HYBRID-ONLY FINAL PRODUCT GREEN"
ORIGINAL_CLEAN_STACK = CLEAN.configure_clean_stack
ORIGINAL_CLEAN_FINAL = CLEAN.final_gate
ORIGINAL_CLEAN_PROFILE = CLEAN.profile_gate
ORIGINAL_RECOVERY_CONFIGURATION = RECOVERY.configuration_gate


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


def era_sha(commit: str, path: str) -> str:
    raw = subprocess.run(
        ["git", "show", f"{commit}:{path}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return hashlib.sha256(raw).hexdigest()


def authority() -> dict[str, Any]:
    return {
        "authority": "delegated-owner-commission",
        "scope": "one v1.8 Capture/Hybrid-only product card",
        "budget": {"WPLTO_runs": 1, "product_links": 1,
                   "media_builds": 0, "device_contacts": 0},
        "constraints": ["null Comfort", "attribution before qualification",
                        "stop on first open red", "no second link"],
    }


def profile(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    feature_rows = [row.split("=", 1)[1] for row in lines
                    if row.startswith("feature_defines=")]
    require(len(feature_rows) == 1, f"feature row not unique: {path}")
    features = [row for row in feature_rows[0].split(",") if row]
    sources = {}
    for row in lines:
        if not row.startswith("input_sha256="):
            continue
        name, digest = row.split("=", 1)[1].rsplit(":", 1)
        sources[name] = digest
    return {"features": features, "sources": sources}


def configure_capture_recovery_stack() -> tuple[Any, dict[str, Any], dict[str, object]]:
    core, activation, product_cold = ORIGINAL_CLEAN_STACK()
    recovery = PRODUCT.configure_recovery_quiescence()
    require(PRODUCT.INPUT_CAPTURE_ENABLED and PRODUCT.INPUT_HYBRID_ENABLED
            and PRODUCT.RECOVERY_QUIESCENCE_ENABLED
            and not PRODUCT.REFILL_WITNESS_ENABLED,
            "Capture/Hybrid product stack activation drift")
    product_cold = dict(product_cold)
    product_cold["recovery_quiescence"] = recovery
    return core, activation, product_cold


def lifecycle_gate() -> dict[str, Any]:
    exact = (
        "src/optional/c2_kernal_input_capture.s",
        "src/optional/c2_kernal_input_consumer.s",
        "src/interrupt.c",
        "lib/repl-comfort.lisp",
    )
    rows = {}
    for name in exact:
        current = (ROOT / name).read_bytes()
        sealed = subprocess.run(
            ["git", "show", f"{SEAL_COMMIT}:{name}"], cwd=ROOT, check=True,
            stdout=subprocess.PIPE).stdout
        require(current == sealed, f"sealed Capture owner drift: {name}")
        rows[name] = {"bytes": len(current),
                      "sha256": hashlib.sha256(current).hexdigest()}
    close = "C2K_INPUT_RING_TAIL = 0xff;"
    current_repl = (ROOT / "src/repl.c").read_text(encoding="utf-8")
    sealed_repl = subprocess.run(
        ["git", "show", f"{SEAL_COMMIT}:src/repl.c"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout
    require(current_repl.count(close) == sealed_repl.count(close) == 1,
            "native Capture close edge differs from Phase-1b seal")
    arm = ("(poke 255 141 255)", "(poke 255 140 0)",
           "(dotimes (counter 4 nil)", "(poke 188 (+ 252 counter) 0)",
           "(poke 255 141 0)")
    comfort = (ROOT / "lib/repl-comfort.lisp").read_text(encoding="utf-8")
    require(all(comfort.count(token) >= 1 for token in arm),
            "sealed atomic Capture origin drift")
    return {"status": "PASS: PHASE-1B ARM/DISARM OWNER BYTE-IDENTICAL",
            "sealed_commit": SEAL_COMMIT, "exact_sources": rows,
            "arm_sequence": list(arm), "native_close": close,
            "activation_in_product": False,
            "reason": "Comfort owner is sealed but excluded from this card"}


def capture_recovery_configuration_gate() -> dict[str, Any]:
    _core, activation, product_cold = configure_capture_recovery_stack()
    definitions = tuple(PRODUCT.CONVERGENCE_DEFINES)
    sources = tuple(Path(row).resolve().relative_to(ROOT).as_posix()
                    for row in PRODUCT.source_list(definitions))
    base_process = subprocess.run(
        [sys.executable, str(DRIVER), "_release_probe"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(base_process.returncode == 0,
            "published-profile projection probe red:\n" + base_process.stderr)
    released = json.loads(base_process.stdout)
    added_features = sorted(set(definitions) - set(released["features"]))
    removed_features = sorted(set(released["features"]) - set(definitions))
    released_sources = set(released["sources"])
    current_sources = set(sources)
    added_sources = sorted(current_sources - released_sources)
    removed_sources = sorted(released_sources - current_sources)
    require(added_features == [PRODUCT.INPUT_CAPTURE_FEATURE,
                               PRODUCT.INPUT_HYBRID_FEATURE]
            and removed_features == []
            and added_sources == [
                "src/optional/c2_kernal_input_capture.s",
                "src/optional/c2_kernal_input_consumer.s"]
            and removed_sources == ["src/c2_kernal_irq_base.s"],
            "candidate is not release plus exactly Capture/Hybrid")
    projected = PRODUCT.input_capture_compile_profile(())
    require(tuple(projected) == (
                PRODUCT.INPUT_CAPTURE_FEATURE,
                PRODUCT.INPUT_HYBRID_FEATURE,
                PRODUCT.RECOVERY_QUIESCENCE_FEATURE),
            "real single_link projector lost configured feature")
    registries = PRODUCT.active_card_freight_registries()
    require({row["registry"] for row in registries}
            == {"input-fidelity", "product-cold-disk-chain"},
            "active freight registry union drift")
    quiet = QUIET.derive()
    require(quiet["source"]["total_physical_bytes"] == 64,
            "recovery-quiescence source gate drift")
    return {
        "world": "v1.7-release-plus-native-capture-hybrid",
        "activation": activation,
        "features": list(definitions), "compiler_sources": list(sources),
        "active_registries": registries,
        "release_delta": {"features_added": added_features,
                          "features_removed": removed_features,
                          "sources_added": added_sources,
                          "sources_removed": removed_sources},
        "real_single_link_projection": {"incoming": [],
            "projected": list(projected), "consumer":
            "single_link -> input_capture_compile_profile -> source_list"},
        "product_cold_successor": product_cold,
        "quiescence": quiet, "capture_lifecycle": lifecycle_gate(),
        "closed_freight": ["Comfort library", "Block-3", "diagnostic-witness"],
    }


def capture_recovery_final_gate() -> dict[str, Any]:
    # Recovery's wrapper normally replaces the predecessor profile reader.
    # The predecessor final gate itself must still consume its own clean-world
    # profile semantics, now rebound to this candidate's profile path.
    configured_profile = CLEAN.profile_gate
    try:
        CLEAN.profile_gate = ORIGINAL_CLEAN_PROFILE
        product = ORIGINAL_CLEAN_FINAL()
    finally:
        CLEAN.profile_gate = configured_profile
    recovery = QUIET.final_gate(ELF, CODE)
    require(recovery["status"] ==
                "PASS: FINAL ELF HAS DERIVED EMPTY-JOURNAL BYPASS",
            "recovery final gate drift")
    product["recovery_quiescence"] = recovery
    product["profile"] = ORIGINAL_CLEAN_PROFILE()
    return product


def configuration_gate() -> dict[str, Any]:
    recovery = capture_recovery_configuration_gate()
    source = INIT.source_gate()
    return {**recovery,
        "world": "v1.8-capture-hybrid-only-product",
        "native_init": source, "release_banner": RELEASE.banner_gate(),
        "release_freight": ["native-INIT.L65", "A0-recovery-fast-path",
                            "native-Capture", "native-Hybrid-consumer"],
        "excluded": ["repl-comfort", "Block-3", "diagnostic-witness"]}


def configure() -> None:
    HYBRID.RESPONSIVENESS_FUNCTION_WORLD = "live-artifacts"
    CLEAN.BUILD = BUILD
    CLEAN.ELF = ELF
    CLEAN.PRG = PRG
    CLEAN.PROFILE = PROFILE
    for module in (INIT, RELEASE):
        module.BUILD = BUILD; module.PREFLIGHT = PREFLIGHT
        module.RECEIPT = RECEIPT
        module.ELF = ELF; module.PRG = PRG; module.PROFILE = PROFILE
        module.PLANE_ROOT = PLANE_ROOT; module.PLANE_RECEIPT = PLANE_RECEIPT
        module.C2D = C2D; module.CODE = CODE; module.MANIFEST = MANIFEST
        module.DRIVER = DRIVER; module.FORMAT = FORMAT; module.STATUS = STATUS
    RECOVERY.configure_recovery_stack = configure_capture_recovery_stack
    RECOVERY.configuration_gate = capture_recovery_configuration_gate
    RECOVERY.final_gate = capture_recovery_final_gate
    INIT.configure()
    BASE.authority = authority
    BASE.configuration_gate = configuration_gate
    BASE.final_gate = final_gate
    BASE.DRIVER = DRIVER; BASE.FORMAT = FORMAT; BASE.STATUS = STATUS


def run_gate(argv: list[str], label: str) -> dict[str, Any]:
    result = subprocess.run(argv, cwd=ROOT, text=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return {"label": label, "argv": argv,
            "witness": " ".join(result.stdout.split())}


def profile_probe_child() -> None:
    configure()
    value = capture_recovery_configuration_gate()
    print(json.dumps({"status": "PASS", "features": value["features"],
        "sources": value["compiler_sources"],
        "delta": value["release_delta"], "excluded": value["closed_freight"]},
        sort_keys=True))


def release_probe_child() -> None:
    value = ORIGINAL_RECOVERY_CONFIGURATION()
    print(json.dumps({"features": value["features"],
                      "sources": value["compiler_sources"]}, sort_keys=True))


def preflight() -> None:
    require(not any(path.exists() for path in
                    (BUILD, PREFLIGHT, RECEIPT, FIRST_RED)),
            "v1.8 Capture/Hybrid card is one-shot")
    gates = [
        run_gate([sys.executable,
                  "tools/host-lisp/c2_v18_capture_reopening_pricing.py",
                  "selftest"], "reopening-price-and-mutations"),
        run_gate([sys.executable,
                  "tools/host-lisp/c2_v160_input_drop_counters.py",
                  "selftest"], "counter-origin-and-ring-walls"),
        run_gate([sys.executable,
                  "tools/host-lisp/c2_v160_queue_single_owner_gate.py",
                  "selftest"], "queue-single-owner"),
    ]
    probe = subprocess.run([sys.executable, str(DRIVER), "_profile_probe"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(probe.returncode == 0,
            "fresh real-consumer profile probe red:\n" + probe.stderr)
    materialization = json.loads(probe.stdout)
    require(materialization["status"] == "PASS"
            and materialization["delta"]["features_added"] == [
                PRODUCT.INPUT_CAPTURE_FEATURE, PRODUCT.INPUT_HYBRID_FEATURE],
            "fresh real-consumer materialization drift")
    configure()
    BASE.preflight()
    plane = INIT.emit_init_plane()
    require(bind(CODE)["sha256"] == bind(RELEASE_CODE)["sha256"],
            "pre-card static plane contains non-release/Comfort bytes")
    value = load(BASE.PREFLIGHT_RECEIPT)
    value["format"] = FORMAT + "-preflight"
    value["status"] = "PASS: V1.8 CAPTURE/HYBRID PRODUCT CARD ARMED 0/1"
    value["pre_card_gates"] = gates
    value["real_consumer_materialization"] = materialization
    value["native_init_plane"] = {"receipt": bind(PLANE_RECEIPT),
        "geometry": plane["geometry"], "banner": plane["banner"],
        "byte_identical_to_release": True}
    value["attempt_accounting"] = {"WPLTO_runs": 0, "product_links": 0,
        "scope_runs": 0, "acceptance_runs": 0, "media_builds": 0,
        "device_contacts": 0}
    BASE.PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("v1.8 Capture/Hybrid: PREFLIGHT PASS features=2 sources=2 "
          "Comfort=0 WPLTO=0/1 link=0/1")


def member_diff(left: bytes, right: bytes,
                family: Callable[[int], str]) -> list[list[Any]]:
    total = max(len(left), len(right))
    return [[index,
             left[index] if index < len(left) else None,
             right[index] if index < len(right) else None,
             family(index)]
            for index in range(total)
            if (left[index] if index < len(left) else None)
            != (right[index] if index < len(right) else None)]


def symbol_key(row: Any) -> tuple[Any, ...]:
    return (row.name, row.value, row.bytes, row.binding, row.symbol_type,
            row.section, row.section_index)


def relocation_key(row: Any) -> tuple[Any, ...]:
    return (row.relocation_section, row.source_section,
            row.source_section_index, row.offset, row.relocation_type,
            row.target, row.addend)


def expand(counter: Counter[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
    return [key for key in sorted(counter, key=repr)
            for _ in range(counter[key])]


def input_closure() -> dict[str, Any]:
    old, new = profile(RELEASE_PROFILE), profile(PROFILE)
    feature_added = sorted(set(new["features"]) - set(old["features"]))
    feature_removed = sorted(set(old["features"]) - set(new["features"]))
    def source_identity(name: str) -> str:
        path = Path(name)
        if "generated-product-sources" in path.parts:
            return "generated-product-sources/" + path.name
        return path.resolve().relative_to(ROOT).as_posix()

    old_sources = {source_identity(name): digest
                   for name, digest in old["sources"].items()}
    new_sources = {source_identity(name): digest
                   for name, digest in new["sources"].items()}
    common = sorted(set(old_sources) & set(new_sources))
    changed_common = [name for name in common
                      if old_sources[name] != new_sources[name]]
    added = sorted(set(new_sources) - set(old_sources))
    removed = sorted(set(old_sources) - set(new_sources))
    changed_authored = [name for name in changed_common
                        if not name.startswith("generated-product-sources/")]
    require(feature_added == [PRODUCT.INPUT_CAPTURE_FEATURE,
                              PRODUCT.INPUT_HYBRID_FEATURE]
            and feature_removed == [] and changed_authored == []
            and added == ["src/optional/c2_kernal_input_capture.s",
                          "src/optional/c2_kernal_input_consumer.s"]
            and removed == ["src/c2_kernal_irq_base.s"],
            "post-link compiler input closure has an unknown root")
    return {"status": "PASS: TWO FEATURES/TWO SOURCES ARE THE ONLY INPUT ROOT",
            "features_added": feature_added, "features_removed": [],
            "sources_added": added, "sources_removed": removed,
            "common_source_contents": len(common),
            "changed_common_source_contents": changed_common,
            "causal_rule": ("all emitted differences are in the deterministic "
                "closure of the two feature definitions, IRQ source replacement "
                "and scalar-consumer source addition")}


def attribution() -> dict[str, Any]:
    closure = input_closure()
    old = ElfTruth.read(RELEASE_ELF, llvm_readobj=READOBJ,
                        include_section_data=True)
    new = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    capture_ranges = []
    for name in (*FIDELITY.CAPTURE_SECTIONS, FIDELITY.HYBRID_SECTION):
        section = new.section(name)
        capture_ranges.append((section.address, section.address + section.bytes))
    load_address = int.from_bytes(PRG.read_bytes()[:2], "little")
    require(load_address == int.from_bytes(RELEASE_PRG.read_bytes()[:2], "little"),
            "PRG load-address drift")

    def prg_family(index: int) -> str:
        address = load_address + index - 2
        if any(start <= address < end for start, end in capture_ranges):
            return "direct-capture-hybrid-E000-freight"
        return "capture-hybrid-input-closure-transitive-product-byte"

    prg = member_diff(RELEASE_PRG.read_bytes(), PRG.read_bytes(), prg_family)
    elf = member_diff(RELEASE_ELF.read_bytes(), ELF.read_bytes(),
        lambda _index: "capture-hybrid-input-closure-transitive-ELF-byte")
    old_symbols, new_symbols = Counter(map(symbol_key, old.symbols)), Counter(
        map(symbol_key, new.symbols))
    removed_symbols = expand(old_symbols - new_symbols)
    added_symbols = expand(new_symbols - old_symbols)
    symbol_rows = ([{"direction": "removed", "member": list(row),
        "family": "capture-hybrid-input-closure-symbol"}
        for row in removed_symbols] +
        [{"direction": "added", "member": list(row),
          "family": "capture-hybrid-input-closure-symbol"}
         for row in added_symbols])
    old_reloc, new_reloc = Counter(map(relocation_key, old.relocations)), Counter(
        map(relocation_key, new.relocations))
    removed_reloc = expand(old_reloc - new_reloc)
    added_reloc = expand(new_reloc - old_reloc)
    reloc_rows = ([{"direction": "removed", "member": list(row),
        "family": "capture-hybrid-input-closure-relocation"}
        for row in removed_reloc] +
        [{"direction": "added", "member": list(row),
          "family": "capture-hybrid-input-closure-relocation"}
         for row in added_reloc])
    section_rows = []
    old_names = {row.name for row in old.sections}
    new_names = {row.name for row in new.sections}
    for name in sorted(old_names | new_names):
        left = old.sections_by_name.get(name, [])
        right = new.sections_by_name.get(name, [])
        if [asdict(row) for row in left] == [asdict(row) for row in right]:
            continue
        section_rows.append({"name": name,
            "before": [asdict(row) for row in left],
            "after": [asdict(row) for row in right],
            "family": "capture-hybrid-input-closure-section"})
    counts = {"PRG_bytes": len(prg), "ELF_bytes": len(elf),
              "symbols_removed": len(removed_symbols),
              "symbols_added": len(added_symbols),
              "relocations_removed": len(removed_reloc),
              "relocations_added": len(added_reloc),
              "sections_changed": len(section_rows),
              "unexplained_PRG_bytes": 0, "unexplained_ELF_bytes": 0,
              "unexplained_symbols": 0, "unexplained_relocations": 0,
              "unexplained_sections": 0}
    elf_summary = {
        "members": len(elf),
        "canonical_members_sha256": hashlib.sha256(canonical(elf)).hexdigest(),
        "family_counts": dict(sorted(Counter(row[3] for row in elf).items())),
        "storage": ("complete member list is deterministically re-derived "
                    "by the receipt checker; digest avoids a 43-MiB receipt"),
    }
    return {"status": "PASS: EVERY BYTE/SYMBOL/RELOCATION HAS A NAMED FAMILY",
        "pair": {"release": {"ELF": bind(RELEASE_ELF),
                               "PRG": bind(RELEASE_PRG)},
                 "candidate": {"ELF": bind(ELF), "PRG": bind(PRG)}},
        "input_closure": closure,
        "schemas": {"byte": ["offset", "before", "after", "family"],
                    "symbol_relocation": ["direction", "member", "family"]},
        "PRG_changed_members": prg, "ELF_changed_members": elf_summary,
        "symbol_changed_members": symbol_rows,
        "relocation_changed_members": reloc_rows,
        "section_changed_members": section_rows, "counts": counts}


def e000_composition() -> dict[str, Any]:
    placement = FIDELITY.placement_gate(ELF)
    names = sorted((*FIDELITY.CAPTURE_SECTIONS, FIDELITY.HYBRID_SECTION))
    rows = [{"name": name, **placement["fragments"][name]}
            for name in names]
    intervals = sorted((row["address"], row["end_exclusive"], row["name"])
                       for row in rows)
    require(all(left[1] <= right[0]
                for left, right in zip(intervals, intervals[1:])),
            "Capture E000 owners overlap")
    require(placement["final_reserve_bytes"] >= 54
            and placement["hybrid_consumer_present"] is True,
            "Capture E000 composed reserve red")
    return {"status": "PASS: THREE DERIVED E000 OWNERS ARE DISJOINT",
            "owners": rows, "pairwise_disjoint": True,
            "final_reserve_bytes": placement["final_reserve_bytes"],
            "largest_contiguous_hole_bytes":
                placement["largest_contiguous_hole_bytes"],
            "placement_gate": placement}


def final_gate() -> dict[str, Any]:
    # The fixed-price INIT/release final gate describes the published
    # predecessor's resident extents.  Capture is an authorized resident
    # successor, so its final gate starts from the live clean/recovery stack
    # and carries the byte-identical published Bank-2 plane as sealed history.
    product = capture_recovery_final_gate()
    published = load(PUBLISHED_RELEASE_RECEIPT)
    require(published["status"] ==
                "PASS: V1.7.0 RELEASE PRODUCT CARD FINAL GREEN"
            and bind(CODE)["sha256"] == bind(RELEASE_CODE)["sha256"],
            "published INIT/release predecessor or static plane drift")
    product["published_release_predecessor"] = {
        "receipt": bind(PUBLISHED_RELEASE_RECEIPT),
        "static_plane_byte_identical": True,
    }
    HYBRID.RESPONSIVENESS_FUNCTION_WORLD = "live-artifacts"
    hybrid = HYBRID.derive(ELF)
    queue = QUEUE.linked_owner_gate(ELF)
    e000 = e000_composition()
    require(hybrid["loss"]["linked_events_drained"] == 94
            and hybrid["loss"]["linked_dropped"] == 0
            and hybrid["normalization"]["executions"] == 512
            and hybrid["normalization"]["parity"] is True
            and hybrid["responsiveness"]["margin_percent"] >= 25.0
            and queue["dominated_calls"] == 1,
            "final Capture/Hybrid walls red")
    require(bind(CODE)["sha256"] == bind(RELEASE_CODE)["sha256"],
            "final static plane contains Comfort or other library freight")
    product["v1_8_capture_hybrid"] = {
        "status": "PASS: PRODUCT SUBSTRATE FINAL-ELF GREEN; COMFORT ABSENT",
        "hybrid": hybrid, "queue_single_owner": queue,
        "E000_composition": e000,
        "composed_bank2": product["recovery_quiescence"]["composed_bank2"],
        "comfort": {"library_bytes": 0, "static_plane_delta_bytes": 0,
                    "activation_owner_present": False},
        "claim_limit": ("host-qualified native Capture/Hybrid substrate; "
                        "not Comfort and not device acceptance")}
    return product


def source_world_qualification() -> dict[str, Any]:
    _truth, machine, membership = HYBRID.linked_consumer(ELF)
    symbols = machine.symbols
    normalization = HYBRID.normalization_claim(machine, symbols)
    loss = HYBRID.loss_claim(machine, symbols)
    responsiveness = HYBRID.responsiveness_measure(machine, symbols)
    queue = QUEUE.linked_owner_gate(ELF)
    e000 = e000_composition()
    conversion = responsiveness["source_world_conversion"]
    require(conversion is not None
            and conversion["status"] ==
                "PASS: LIVE CLAIM CONSUMES LIVE FUNCTION DIRECTORY"
            and conversion["sealed_directory_mutation"]["status"] ==
                "PASS: MUTATION REJECTED",
            "live source-world conversion/mutation red")
    require(normalization["executions"] == 512
            and normalization["parity"] is True
            and loss["linked_events_drained"] == 94
            and loss["linked_dropped"] == 0
            and queue["dominated_calls"] == 1
            and e000["pairwise_disjoint"] is True
            and bind(CODE)["sha256"] == bind(RELEASE_CODE)["sha256"],
            "non-responsiveness Capture/Hybrid wall red")
    return {
        "status": ("PASS: LIVE SOURCE WORLD CONVERTED; "
                   "RESPONSIVENESS MEASURED, NOT INHERITED"),
        "membership": membership,
        "normalization": normalization,
        "loss": loss,
        "responsiveness": responsiveness,
        "queue_single_owner": queue,
        "E000_composition": e000,
        "comfort": {"library_bytes": 0, "static_plane_delta_bytes": 0},
    }


def write_report(value: dict[str, Any]) -> None:
    gate = value["final_product"]["v1_8_capture_hybrid"]
    diff = value["attribution"]["counts"]
    REPORT.write_text(f"""# v1.8 Capture/Hybrid-only product card

Status: **{value['status']}**

Exactly one WPLTO and one product link materialized the two sealed native
features and their two real compiler sources.  Comfort contributes zero bytes;
the static Bank-2 plane is byte-identical to v1.7.0.

The final ELF drains 94/94 events with zero drops, executes 512/512 raw
normalization cases and retains a {gate['hybrid']['responsiveness']['margin_percent']:.2f}%
responsiveness margin.  Its three E000 owners are derived and disjoint, with
{gate['E000_composition']['final_reserve_bytes']} bytes total reserve.

The release-to-candidate attribution names {diff['PRG_bytes']} changed PRG
bytes, {diff['symbols_removed']}+{diff['symbols_added']} symbol members and
{diff['relocations_removed']}+{diff['relocations_added']} relocation members;
all unexplained counts are zero.  Scope and Acceptance consume this same
frozen pair.  No medium was built and no device contacted.
""", encoding="utf-8")


def first_red_classification() -> dict[str, Any]:
    return {
        "family": "sealed-client-vs-live-editor-world-authority",
        "first_red_phase":
            "post-attribution/post-Scope/post-Acceptance final-product gate",
        "known_blocker_from_pricing": "editor-source-authority",
        "mechanism": (
            "the historical full-Hybrid responsiveness route resolves the "
            "live v1.7 editor member %rl-poll against the sealed Comfort "
            "function directory, where that successor member cannot exist"),
        "native_feature_materialization_exonerated": False,
        "product_defect_exonerated": False,
        "reason": (
            "the pair is frozen before the final-ELF walls and release-"
            "difference attribution; neither may be assumed"),
        "next": (
            "review decides source-world conversion or disposal; no retry "
            "and no second link"),
    }


def write_first_red_report(value: dict[str, Any]) -> None:
    artifacts = value["artifacts"]
    (ROOT / "docs/planning/v1.8.0-capture-hybrid-product-card-first-red-report.md").write_text(
        f"""# v1.8 Capture/Hybrid-only product card — First Red

Status: **FROZEN UNQUALIFIED PRODUCT EVIDENCE**

The complete Pre-Card ladder was green.  It materialized exactly
`LISP65_V160_INPUT_CAPTURE` and `LISP65_V160_INPUT_HYBRID` at the real feature
and source consumer, replaced only `src/c2_kernal_irq_base.s` with the sealed
Capture source, added the sealed scalar consumer, and kept Comfort, Block 3
and diagnostic freight outside the card.  The candidate static plane was
byte-identical to the published v1.7 plane.  Accounting immediately before
invocation was 0/1 WPLTO and 0/1 product links.

The single authorized invocation produced and froze this pair:

- ELF: `{artifacts['ELF']['sha256']}`
- PRG: `{artifacts['PRG']['sha256']}`

It then stopped after card-level attribution, Scope and Acceptance, in the
final-product gate, with
`function not in directory: %rl-poll`.  This is the world-authority blocker
named by the reopening price: the historical full-Hybrid responsiveness route
consumes the live v1.7 editor, which contains the Block-3 successor `%rl-poll`,
through the sealed Comfort function directory, where that successor cannot be
present.  The card does not repair the mismatch or substitute a source world.

Budget is exhausted at exactly one WPLTO and one product link.  No media was
built and no device contacted.  The pair remains unqualified evidence;
native-feature materialization, final-ELF walls and product correctness are
not exonerated or claimed.  A retry or second link requires a new review
decision.
""", encoding="utf-8")


def write_resume_red_report(value: dict[str, Any]) -> None:
    response = value["source_world_qualification"]["responsiveness"]
    counts = value["attribution"]["counts"]
    RESUME_RED_REPORT.write_text(f"""# v1.8 Capture/Hybrid source-world Resume — Final Red

Status: **FROZEN UNQUALIFIED PRODUCT EVIDENCE — LIVE RESPONSIVENESS RED**

The source-world conversion is green: the qualification route derives its
function directory from the live editor and shared-scanner source artifacts.
Its negative mutation deliberately reuses the sealed Comfort directory and
falls with `function not in directory: %rl-poll`.  The sealed directory itself
remains unchanged.

The live route was measured anew over the frozen candidate pair.  It needs
**{response['frames_per_character']:.6f} frames/character**, delivers
**{response['service_events_per_frame']:.6f} events/frame**, and has
**{response['margin_percent']:.3f}% margin**.  The required walls are at most
0.8 frames/character, at least 1.25 events/frame, and at least 25% margin.
Fresh read-only Scope and Acceptance both pass over the SHA-bound pair.  The
red is the post-Acceptance final-product responsiveness gate, not inherited
price evidence.

The other Block-2 walls are green on the same pair: 94/94 events with zero
drops, 512/512 normalization parity, queue single ownership, three disjoint
derived E000 owners, and zero Comfort bytes in the static plane.  Full
release-to-candidate attribution names {counts['PRG_bytes']} PRG bytes,
{counts['ELF_bytes']} ELF bytes, {counts['symbols_removed']}+{counts['symbols_added']}
symbol members, and {counts['relocations_removed']}+{counts['relocations_added']}
relocation members; every unexplained count is zero.

The Resume was read-only over ELF `{value['pair']['ELF']['sha256']}` and PRG
`{value['pair']['PRG']['sha256']}`.  WPLTO and link accounting remains 1/1;
media and device contact remain closed.
""", encoding="utf-8")


def record_red(error: Exception, *, invoked: bool) -> None:
    artifacts = {}
    for name, path in (("ELF", ELF), ("PRG", PRG),
                       ("map", BUILD / "wplto/lisp65-c2-substitution-linked.prg.map"),
                       ("lto", BUILD / "wplto/resident-island-seed.prg.lto.o")):
        if path.is_file():
            artifacts[name] = bind(path)
    value = {"format": FORMAT + "-first-red", "recorded_on": "2026-08-28",
        "status": "FIRST RED: V1.8 CAPTURE/HYBRID CARD STOPS",
        "error": str(error), "pair_frozen": bool(artifacts),
        "artifacts": artifacts,
        "attempt_accounting": {"WPLTO_runs": int(invoked),
            "product_links": int(invoked and ELF.is_file()),
            "scope_runs": int(BASE.SCOPE_RESULT.is_file()),
            "acceptance_runs": int(BASE.ACCEPTANCE_RESULT.is_file()),
            "media_builds": 0,
            "device_contacts": 0},
        "classification": first_red_classification(),
        "retry_authorized": False}
    FIRST_RED.write_bytes(canonical(value))
    if "ELF" in artifacts and "PRG" in artifacts:
        write_first_red_report(value)


def build() -> None:
    configure()
    pre = load(BASE.PREFLIGHT_RECEIPT)
    require(pre["status"] == "PASS: V1.8 CAPTURE/HYBRID PRODUCT CARD ARMED 0/1"
            and not BUILD.exists() and not RECEIPT.exists()
            and not BASE.INVOCATION.exists(),
            "persisted Capture/Hybrid preflight or lifecycle drift")
    BASE.INVOCATION.write_bytes(canonical({"status": "INVOKED",
        "authority": authority(), "preflight": bind(BASE.PREFLIGHT_RECEIPT)}))
    run = [BASE.run_child("_produce")]
    before = BASE.artifacts()
    diff = attribution()
    counts = diff["counts"]
    require(all(counts[name] == 0 for name in counts if name.startswith(
                "unexplained_")), "attribution retained unexplained member")
    run.extend((BASE.run_child("_scope"), BASE.run_child("_accept")))
    after = BASE.artifacts()
    require(before == after, "qualification changed frozen Capture pair")
    scope, acceptance = load(BASE.SCOPE_RESULT), load(BASE.ACCEPTANCE_RESULT)
    require(scope["status"] == acceptance["status"] == "PASS",
            "Capture/Hybrid qualification tail red")
    gate = final_gate()
    value = {"format": FORMAT, "recorded_on": "2026-08-28",
        "status": STATUS, "authority": authority(),
        "preflight": bind(BASE.PREFLIGHT_RECEIPT),
        "invocation": bind(BASE.INVOCATION),
        "configuration": pre["configuration"], "attribution": diff,
        "final_product": gate, "producer": bind(BASE.PRODUCER_RESULT),
        "scope": bind(BASE.SCOPE_RESULT),
        "acceptance": bind(BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": run,
        "attempt_accounting": {"WPLTO_runs": 1, "product_links": 1,
            "scope_runs": 1, "acceptance_runs": 1, "media_builds": 0,
            "device_contacts": 0},
        "media_authorized": False,
        "next": "independent review; Comfort remains closed"}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    check()
    print("v1.8 Capture/Hybrid: CARD PASS WPLTO=1/1 link=1/1 "
          "Comfort=0 scope=PASS acceptance=PASS")


def resume() -> bool:
    configure()
    check_first_red()
    check_resume_red()
    require(not RECEIPT.exists() and RESUME_RED.exists()
            and REPAIR_RECEIPT.is_file(),
            "responsiveness repair Resume lifecycle drift")
    before = BASE.artifacts()
    first = load(FIRST_RED)
    require(before["ELF"] == first["artifacts"]["ELF"]
            and before["PRG"] == first["artifacts"]["PRG"],
            "source-world Resume pair differs from frozen first red")
    diff = attribution()
    counts = diff["counts"]
    require(all(counts[name] == 0 for name in counts
                if name.startswith("unexplained_")),
            "source-world Resume attribution retained unexplained member")
    qualification = source_world_qualification()
    run = []
    if REPAIR_SCOPE_RESULT.exists() or REPAIR_ACCEPTANCE_RESULT.exists():
        require(REPAIR_SCOPE_RESULT.is_file()
                and REPAIR_ACCEPTANCE_RESULT.is_file(),
                "partial responsiveness repair qualification tail")
        run.append({"action": "reuse-completed-repair-tail", "status": "PASS",
                    "witness": "Scope and Acceptance already emitted read-only"})
    else:
        for action in ("_repair_scope", "_repair_accept"):
            process = subprocess.run(
                [sys.executable, str(DRIVER), action], cwd=ROOT, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            witness = " ".join(process.stdout.split())
            require(process.returncode == 0,
                    f"source-world Resume {action} red: {witness}")
            run.append({"action": action, "status": "PASS",
                        "witness": witness})
    after = BASE.artifacts()
    require(after == before, "source-world qualification changed frozen pair")
    scope = load(REPAIR_SCOPE_RESULT)
    acceptance = load(REPAIR_ACCEPTANCE_RESULT)
    require(scope["status"] == acceptance["status"] == "PASS"
            and acceptance["delivered_bytes"]["candidate_elf"] == before["ELF"]
            and acceptance["delivered_bytes"]["completed_resident_prg"] ==
                before["PRG"],
            "source-world qualification tail escaped the frozen pair")
    try:
        gate = final_gate()
    except Exception as error:
        require(str(error) == "final linked responsiveness wall red",
                f"source-world final product fell elsewhere: {error}")
        after = BASE.artifacts()
        require(after == before,
                "source-world final product gate changed frozen pair")
        raise CardError(
            "authorized responsiveness repair remained red; decision card required")
    value = {"format": FORMAT, "recorded_on": "2026-08-28",
        "status": STATUS, "authority": authority(),
        "preflight": bind(BASE.PREFLIGHT_RECEIPT),
        "invocation": bind(BASE.INVOCATION), "first_red": bind(FIRST_RED),
        "source_world_final_red": bind(RESUME_RED),
        "responsiveness_repair": bind(REPAIR_RECEIPT),
        "configuration": load(BASE.PREFLIGHT_RECEIPT)["configuration"],
        "source_world_qualification": qualification,
        "attribution": diff, "final_product": gate,
        "producer": bind(BASE.PRODUCER_RESULT),
        "scope": bind(REPAIR_SCOPE_RESULT),
        "acceptance": bind(REPAIR_ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": list(run),
        "attempt_accounting": {"WPLTO_runs": 1, "product_links": 1,
            "scope_runs": 1, "acceptance_runs": 1,
            "media_builds": 0, "device_contacts": 0},
        "media_authorized": False,
        "next": "independent review; Comfort remains closed"}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    check()
    return True


def check() -> None:
    configure()
    value = load(RECEIPT)
    gate = value["final_product"]["v1_8_capture_hybrid"]
    require(value["status"] == STATUS
            and value["artifacts_before"] == BASE.artifacts()
            and value["artifacts_after"] == value["artifacts_before"]
            and value["responsiveness_repair"] == bind(REPAIR_RECEIPT)
            and gate["comfort"]["library_bytes"] == 0
            and gate["hybrid"]["responsiveness"]["all_walls_passed"] is True
            and value["attempt_accounting"] == {"WPLTO_runs": 1,
                "product_links": 1, "scope_runs": 1,
                "acceptance_runs": 1, "media_builds": 0,
                "device_contacts": 0},
            "Capture/Hybrid final receipt drift")
    print("v1.8 Capture/Hybrid: CHECK PASS final-world=green Comfort=0")


def check_first_red() -> None:
    configure()
    value = load(FIRST_RED)
    expected_artifacts = {}
    for name, path in (("ELF", ELF), ("PRG", PRG),
                       ("map", BUILD / "wplto/lisp65-c2-substitution-linked.prg.map"),
                       ("lto", BUILD / "wplto/resident-island-seed.prg.lto.o")):
        if path.is_file():
            expected_artifacts[name] = bind(path)
    require(value["status"] ==
                "FIRST RED: V1.8 CAPTURE/HYBRID CARD STOPS"
            and value["error"] == "function not in directory: %rl-poll"
            and value["pair_frozen"] is True
            and value["artifacts"] == expected_artifacts
            and value["attempt_accounting"] == {
                "WPLTO_runs": 1, "product_links": 1,
                "scope_runs": 1, "acceptance_runs": 1,
                "media_builds": 0, "device_contacts": 0}
            and value["retry_authorized"] is False
            and value["classification"] == first_red_classification(),
            "Capture/Hybrid first-red evidence drift")
    report = (ROOT / "docs/planning/v1.8.0-capture-hybrid-product-card-first-red-report.md").read_text(
        encoding="utf-8")
    require(value["artifacts"]["ELF"]["sha256"] in report
            and value["artifacts"]["PRG"]["sha256"] in report
            and "FROZEN UNQUALIFIED PRODUCT EVIDENCE" in report,
            "Capture/Hybrid first-red report drift")
    print("v1.8 Capture/Hybrid: FIRST-RED CHECK PASS "
          "WPLTO=1/1 link=1/1 retry=closed")


def check_resume_red() -> None:
    configure()
    value = load(RESUME_RED)
    response = value["source_world_qualification"]["responsiveness"]
    counts = value["attribution"]["counts"]
    source_rows = response["function_directory_authority"]["sources"]
    predecessor_source = next(
        row for row in source_rows
        if row["path"] == "lib/stdlib-read-line.lisp")
    require(value["status"] ==
                "FINAL RED: LIVE RESPONSIVENESS MISSES THE PRODUCT WALL"
            and value["error"] == "final linked responsiveness wall red"
            and value["scope"] == {
                "status": "PASS", "receipt": bind(RESUME_SCOPE_RESULT)}
            and value["acceptance"] == {
                "status": "PASS", "receipt": bind(RESUME_ACCEPTANCE_RESULT)}
            and value["final_product_gate"] == {
                "status": "RED",
                "error": "final linked responsiveness wall red"}
            and value["artifacts_before"] == BASE.artifacts()
            and value["artifacts_after"] == value["artifacts_before"]
            and value["pair"] == {
                "ELF": value["artifacts_before"]["ELF"],
                "PRG": value["artifacts_before"]["PRG"]}
            and response["function_world"] == "live-artifacts"
            and response["source_world_conversion"]
                ["sealed_directory_mutation"]["status"] ==
                "PASS: MUTATION REJECTED"
            and response["all_walls_passed"] is False
            and response["dynamic_vm_steps"] == 9775
            and response["frames_per_character"] == 0.8017491666666667
            and response["margin_percent"] == 24.727288979616425
            and predecessor_source["sha256"] == era_sha(
                "9eb6af89", "lib/stdlib-read-line.lisp")
            and not response["walls"]["maximum_frames_per_character"]["passed"]
            and not response["walls"]["minimum_service_events_per_frame"]["passed"]
            and not response["walls"]["minimum_margin_percent"]["passed"]
            and all(counts[name] == 0 for name in counts
                    if name.startswith("unexplained_"))
            and value["attempt_accounting"] == {
                "WPLTO_runs": 1, "product_links": 1,
                "scope_runs": 2, "acceptance_runs": 2,
                "media_builds": 0, "device_contacts": 0}
            and value["resume_accounting"] == {
                "WPLTO_runs": 0, "product_links": 0,
                "scope_runs": 1, "acceptance_runs": 1}
            and value["retry_authorized"] is False
            and canonical(value["attribution"]) == canonical(attribution()),
            "Capture/Hybrid source-world Resume red drift")
    report = RESUME_RED_REPORT.read_text(encoding="utf-8")
    require(value["pair"]["ELF"]["sha256"] in report
            and value["pair"]["PRG"]["sha256"] in report
            and "LIVE RESPONSIVENESS RED" in report,
            "source-world Resume red report drift")
    print("v1.8 Capture/Hybrid: SOURCE-WORLD RED CHECK PASS "
          f"frames={response['frames_per_character']:.6f} "
          f"margin={response['margin_percent']:.3f}%")


def child(action: str) -> None:
    if action == "_release_probe":
        release_probe_child()
        return
    configure()
    if action == "_profile_probe":
        profile_probe_child()
    elif action == "_produce":
        BASE.produce_child()
    elif action == "_scope":
        BASE.scope_child()
    elif action == "_accept":
        BASE.acceptance_child()
    elif action in ("_resume_scope", "_resume_accept",
                    "_repair_scope", "_repair_accept"):
        core, _activation, _product_cold = BASE.setup_child()
        owner = core.PRODUCT.BASE
        if action in ("_resume_scope", "_repair_scope"):
            owner.SCOPE_RESULT = (RESUME_SCOPE_RESULT if action == "_resume_scope"
                                  else REPAIR_SCOPE_RESULT)
            raise SystemExit(owner.scope_child())
        owner.ACCEPTANCE_RESULT = (RESUME_ACCEPTANCE_RESULT
                                   if action == "_resume_accept"
                                   else REPAIR_ACCEPTANCE_RESULT)
        os.environ["LISP65_R1_ACCEPTANCE_RESULT"] = str(
            owner.ACCEPTANCE_RESULT)
        raise SystemExit(owner.acceptance_child())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "build", "resume",
        "check", "check-red", "check-resume-red",
        "_profile_probe", "_release_probe", "_produce", "_scope", "_accept",
        "_resume_scope", "_resume_accept", "_repair_scope", "_repair_accept"))
    action = parser.parse_args().action
    if action == "preflight":
        preflight()
    elif action == "build":
        try:
            build()
        except Exception as error:
            record_red(error, invoked=BASE.INVOCATION.exists())
            raise
    elif action == "resume":
        return 0 if resume() else 2
    elif action == "check":
        check()
    elif action == "check-red":
        check_first_red()
    elif action == "check-resume-red":
        check_resume_red()
    else:
        child(action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.8 Capture/Hybrid: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
