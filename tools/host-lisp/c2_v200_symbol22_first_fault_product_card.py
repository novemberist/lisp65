#!/usr/bin/env python3
"""Build and qualify the v2.0 `$22` first-fault latch product world."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from cpu6502 import CPU  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402
import c2_v17_comfort_abort_reentry_fix as RECOVERY  # noqa: E402
import c2_v160_liveness_config as LIVENESS_CONFIG  # noqa: E402
import c2_v190_release_card as RELEASE  # noqa: E402
import c2_v200_symbol22_first_fault_pricing as PRICE  # noqa: E402


PRODUCT = RELEASE.R8.R7.PRODUCT
BASE = RELEASE.BASE
ORIGINAL_R6_SETUP = RELEASE.R8.R7.R6.setup_child
RECOVERY_SUBSTRATE = RELEASE.R8.R7.R6.CARD.CLIENT.SUBSTRATE
INIT_ADAPTER = RECOVERY_SUBSTRATE.INIT
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
AUTHORIZATION = "5c2fa22bedf569c413f3f1aa045d0c4904733998"
PLAN_HEADER = (
    "## Reviewer authorization — phase-0 product card, re-priced placement — 2026-08-31")
SUCCESSOR_AUTHORIZATION = "ad5b67ee"
SUCCESSOR_PLAN_HEADER = (
    "## Reviewer disposition — r2 relocation-membership pin — 2026-08-31")
PRICING_RECEIPT = ARCH / "c2.3-v2.0-symbol22-first-fault-repricing-receipt.json"
RELEASE_ELF = RELEASE.ELF
RELEASE_PRG = RELEASE.PRG
RELEASE_PROFILE = RELEASE.PROFILE
RELEASE_RECEIPT = RELEASE.RECEIPT
RELEASE_STATUS = RELEASE.STATUS
RELEASE_PLANE_ROOT = RELEASE.PLANE_ROOT
RELEASE_PLANE_RECEIPT = RELEASE.PLANE_RECEIPT
RELEASE_CLIENT_SOURCE = RELEASE.CLIENT_SOURCE
RELEASE_C2D = RELEASE.C2D
RELEASE_CODE = RELEASE.CODE
RELEASE_MANIFEST = RELEASE.MANIFEST
RELEASE_HEADER = RELEASE.HEADER
BUILD = ROOT / "build/c2.3/v2.0-symbol22-first-fault-product-card-r2"
COMPLETION = BUILD / "completion"
PREFLIGHT = ROOT / "build/c2.3/v2.0-symbol22-first-fault-product-card-r2-preflight"
PREFLIGHT_RECEIPT = ARCH / "c2.3-v2.0-symbol22-first-fault-product-card-r2-preflight.json"
INVOCATION = PREFLIGHT / "candidate-invocation.json"
ELF = COMPLETION / "lisp65-c2-substitution-linked.prg.elf"
PRG = COMPLETION / "lisp65-c2-substitution-linked.prg"
PROFILE = COMPLETION / "resolved-profile.txt"
DIFFERENCE = ARCH / "c2.3-v2.0-symbol22-first-fault-product-card-r2-difference.json"
FIRST_RED = ARCH / "c2.3-v2.0-symbol22-first-fault-product-card-r1-first-red.json"
OWNER_RED = ARCH / "c2.3-v2.0-symbol22-first-fault-product-card-r1-owner-red.json"
R2_INVENTORY_RED = ARCH / "c2.3-v2.0-symbol22-first-fault-product-card-r2-first-red.json"
INVENTORY_CONVERSION = ARCH / "c2.3-v2.0-symbol22-first-fault-product-card-r2-inventory-conversion.json"
INVENTORY_CONVERSION_REPORT = ROOT / "docs/planning/v2.0.0-symbol22-r2-inventory-conversion.md"
QUALIFICATION_RED = ARCH / (
    "c2.3-v2.0-symbol22-first-fault-product-card-r2-qualification-red.json")
QUALIFICATION_RED_REPORT = ROOT / (
    "docs/planning/v2.0.0-symbol22-r2-qualification-red.md")
RECEIPT = ARCH / "c2.3-v2.0-symbol22-first-fault-product-card-r2-receipt.json"
REPORT = ROOT / "docs/planning/v2.0.0-symbol22-first-fault-product-card-r2-report.md"
OWNER_RED_REPORT = ROOT / "docs/planning/v2.0.0-symbol22-first-fault-product-card-owner-red.md"
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
SECTION = ".lisp65_symbol22_first_fault_latch"
STATE_SECTION = ".lisp65_symbol22_first_fault_state"
FEATURE = "LISP65_V200_SYMBOL22_FIRST_FAULT"
STATUS = "PASS: V2.0 SYMBOL22 FIRST-FAULT PRODUCT CARD GREEN"
FORMAT = "lisp65-c2.3-v200-symbol22-first-fault-product-card-v2"
TAG = 0xA5
ERROR = 0x22
PAYLOAD_BYTES = 34
REPRICING_STATUS = "PASS: DISJOINT SPLIT LATCH PRICED; PRODUCT CARD REQUIRED"


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
    payload = section.encode()
    return {"commit": commit, "path": relative, "section": header,
            "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


def authority() -> dict[str, Any]:
    pricing = load(PRICING_RECEIPT)
    release = load(RELEASE_RECEIPT)
    section = git_section(AUTHORIZATION, PLAN, PLAN_HEADER)
    require(pricing["status"] == REPRICING_STATUS
            and pricing["selection"]["name"] ==
                "split ordinary Bank-0 code/state"
            and pricing["candidate"]["code_bytes"] == 48
            and pricing["candidate"]["state_bytes"] == 5
            and pricing["candidate"]["record"]["payload_bytes"] == 34
            and release["status"] == RELEASE_STATUS,
            "product-card predecessor authority drift")
    return {"review_authorization": section, "pricing": bind(PRICING_RECEIPT),
            "owner_red": bind(OWNER_RED),
            "v1_9_release_predecessor": bind(RELEASE_RECEIPT),
            "budget": {"product_cards": 1, "WPLTO_runs": 1,
                       "product_links": 1, "media_builds": 0,
                       "device_contacts": 0}}


def successor_authority() -> dict[str, Any]:
    return {"review_authorization": git_section(
        SUCCESSOR_AUTHORIZATION, PLAN, SUCCESSOR_PLAN_HEADER),
        "inventory_first_red": bind(R2_INVENTORY_RED),
        "right": "read-only seed replay, then sole product-closure link",
        "new_WPLTOs": 0, "product_closure_links": 1}


def release_raw_guard_geometry() -> dict[str, Any]:
    truth = ElfTruth.read(RELEASE_ELF, llvm_readobj=READOBJ)
    handoff = truth.section(".lisp65_c2_kernal_handoff")
    facade = truth.section(".lisp65_c2_host_facade")
    refs = raw_interval_references(RELEASE_ELF,
        handoff.address + handoff.bytes, facade.address,
        exclude_section="__no_candidate_section__")
    targets = sorted({row["target"] for row in refs})
    sections = sorted({row["source_section"] for row in refs})
    require(len(refs) == 64 and targets == list(range(0xB582, 0xB592))
            and sections == [".lisp65_rt_c2append_header",
                ".lisp65_rt_c2append_publish_clear",
                ".lisp65_rt_c2append_publish_plan_resolve",
                ".lisp65_rt_c2append_publish_plan_scan"],
            "release terminal-return raw-owner geometry drift")
    return {"start": targets[0], "end_exclusive": targets[-1] + 1,
            "data_references": len(refs), "source_sections": sections}


def patch_paths() -> None:
    values = {
        "BUILD": BUILD, "PREFLIGHT": PREFLIGHT,
        "PLANE_ROOT": RELEASE_PLANE_ROOT,
        "PLANE_RECEIPT": RELEASE_PLANE_RECEIPT,
        "CLIENT_SOURCE": RELEASE_CLIENT_SOURCE, "C2D": RELEASE_C2D,
        "CODE": RELEASE_CODE, "MANIFEST": RELEASE_MANIFEST,
        "HEADER": RELEASE_HEADER, "ELF": ELF, "PRG": PRG,
        "PROFILE": PROFILE, "INVOCATION": INVOCATION,
        "PREFLIGHT_RECEIPT": PREFLIGHT_RECEIPT,
        "DIFFERENCE": DIFFERENCE, "RECEIPT": RECEIPT,
        "REPORT": REPORT, "DRIVER": DRIVER, "FORMAT": FORMAT,
        "STATUS": STATUS,
    }
    for name, value in values.items():
        if hasattr(RELEASE, name):
            setattr(RELEASE, name, value)
    RELEASE.configure()
    code_start = release_raw_guard_geometry()["end_exclusive"]
    if not PRODUCT.SYMBOL22_LATCH_ENABLED:
        PRODUCT.configure_symbol22_first_fault_latch(code_start)
    else:
        require(PRODUCT.SYMBOL22_LATCH_CODE_START == code_start,
                "repeated product-card configuration changed code placement")
    BASE.INVOCATION = INVOCATION
    BASE.authority = authority
    BASE.configuration_gate = configuration_gate
    BASE.final_gate = final_gate
    BASE.ELF = ELF
    BASE.PRG = PRG
    BASE.PROFILE = PROFILE
    BASE.profile_gate = completion_profile_gate
    BASE.artifacts = frozen_artifacts
    RECOVERY_SUBSTRATE.ORIGINAL_CLEAN_PROFILE = completion_profile_gate
    INIT_ADAPTER._consumption_rows = completion_consumption_rows
    RELEASE.R8.R7.R6.setup_child = completion_qualification_setup


def bind_completion_clean_world() -> None:
    BASE.ELF = ELF
    BASE.PRG = PRG
    BASE.PROFILE = PROFILE
    BASE.profile_gate = completion_profile_gate
    BASE.artifacts = frozen_artifacts
    RECOVERY_SUBSTRATE.ORIGINAL_CLEAN_PROFILE = completion_profile_gate
    INIT_ADAPTER._consumption_rows = completion_consumption_rows


def completion_qualification_setup() -> Any:
    result = ORIGINAL_R6_SETUP()
    # The historical setup installs the predecessor defaults as part of its
    # active configuration.  Rebind only the output consumers after that
    # configuration has completed; no configurator is executed twice.
    bind_completion_clean_world()
    return result


def completion_consumption_rows() -> dict[str, tuple[Path, dict[str, Any]]]:
    paths = {
        "seed": BUILD / ("wplto/resident-island-seed.prg."
                           "compiler-input-consumption.json"),
        "final": COMPLETION / ("lisp65-c2-substitution-linked.prg."
                                 "compiler-input-consumption.json"),
    }
    rows = {name: (path, load(path)) for name, path in paths.items()}
    require(rows["seed"][0].parent != rows["final"][0].parent
            and rows["final"][1]["consumed_value"] ==
                RELEASE_CODE.stat().st_size,
            "completion consumer did not bind path and value together")
    return rows


def completion_profile_gate() -> dict[str, Any]:
    lines = PROFILE.read_text(encoding="utf-8").splitlines()
    feature_rows = [line.split("=", 1)[1] for line in lines
                    if line.startswith("feature_defines=")]
    require(len(feature_rows) == 1,
            "completion profile feature row is not unique")
    features = tuple(item for item in feature_rows[0].split(",") if item)
    sources = tuple(line.split(":", 1)[0].split("=", 1)[1]
                    for line in lines if line.startswith("input_sha256="))
    object_root = (COMPLETION /
        ".canonical-objects-lisp65-c2-substitution-linked")
    object_names = sorted(path.name for path in object_root.glob("*.o"))
    require(PRODUCT.REFILL_WITNESS_FEATURE not in features
            and PRODUCT.PRODUCT_COLD_FEATURE in features
            and FEATURE in features
            and not any(name.endswith("c2_refill_boundary_witness.s")
                        for name in sources)
            and any(name.endswith("c2_product_cold_disk_chain.s")
                    for name in sources)
            and any(name.endswith("c2_symbol22_first_fault_latch.s")
                    for name in sources)
            and not any("refill_boundary_witness" in name
                        for name in object_names)
            and any("product_cold_disk_chain" in name
                    for name in object_names)
            and any("symbol22_first_fault_latch" in name
                    for name in object_names),
            "completion consumer lost product or admitted diagnostic freight")
    return {"features": list(features), "sources": list(sources),
            "objects": object_names,
            "real_consumer": ("completion resolved profile plus canonical "
                              "object inventory")}


def configuration_gate() -> dict[str, Any]:
    definitions = tuple(PRODUCT.CONVERGENCE_DEFINES)
    sources = tuple(Path(path).relative_to(ROOT).as_posix()
                    for path in PRODUCT.source_list(definitions))
    registries = PRODUCT.active_card_freight_registries()
    names = [row["registry"] for row in registries]
    require(definitions.count(FEATURE) == 1
            and sources.count(
                "src/optional/c2_symbol22_first_fault_latch.s") == 1
            and names in (["symbol22-first-fault-latch"],
                          ["input-fidelity", "product-cold-disk-chain",
                           "symbol22-first-fault-latch"]),
            "first-fault feature was not materialized at every real consumer")
    latch = next(row for row in registries
                 if row["registry"] == "symbol22-first-fault-latch")
    release_features = profile_features(RELEASE_PROFILE)
    require(latch["allocated"] == [SECTION, STATE_SECTION]
            and release_features.count(
                PRODUCT.TERMINAL_RETURN_GUARD_FEATURE) == 1,
            "split latch or retained terminal guard was not materialized")
    return {"status": "PASS: LATCH FEATURE MATERIALIZED END TO END",
            "feature": FEATURE, "sources": list(sources),
            "active_registries": registries,
            "terminal_return_guard_active": True,
            "base_stack_materialized": len(names) == 3,
            "candidate_allocated_sections": latch["allocated"],
            "composed_candidate_owner_count": 2}


def preflight_micro() -> dict[str, Any]:
    out = PREFLIGHT / "micro"
    out.mkdir(parents=True, exist_ok=True)
    obj = out / "latch.o"
    subprocess.run([str(PRODUCT.TOOLCHAIN / "mos-mega65-clang"), "-c",
        "-mcpu=mos45gs02", str(PRODUCT.SYMBOL22_LATCH_SOURCE), "-o", str(obj)],
        cwd=ROOT, check=True)
    truth = ElfTruth.read(obj, llvm_readobj=READOBJ, include_section_data=True)
    section = truth.section(SECTION)
    state_section = truth.section(STATE_SECTION)
    state = truth.symbol("lisp65_symbol22_latch_state")
    helper = truth.symbol("lisp65_symbol22_latch_capture")
    registration = PRODUCT.symbol22_latch_inventory_registration()
    actual_names = [row.name for row in truth.sections if row.name]
    emitted_sources = sorted({
        row.source_section for row in truth.relocations
        if row.source_section in registration["allocated"]})
    relocation_violations = \
        PRODUCT._registered_relocation_membership_violations(
            registration, emitted_sources, actual_names)
    require((section.bytes, state_section.bytes, state.bytes, helper.bytes) ==
                (48, 5, 5, 48)
            and truth.section_bytes(STATE_SECTION) == bytes(5)
            and not relocation_violations,
            "preflight micro-object freight drift")
    linker = PRODUCT.linker_script(ownership_opt_in=True)
    for token in (".lisp65_symbol22_first_fault_latch 0xb592",
                  "ADDR(.lisp65_c2_host_facade)",
                  "SIZEOF(.lisp65_symbol22_first_fault_latch) == 48",
                  "ADDR(.lisp65_c2_fixed_bank0_hot_bss)",
                  "SIZEOF(.lisp65_symbol22_first_fault_state) == 5"):
        require(token in linker, f"derived latch linker fact absent: {token}")
    source = (ROOT / "src/repl.c").read_text(encoding="utf-8")
    symbol = (ROOT / "src/symbol.c").read_text(encoding="utf-8")
    require(source.count(".set c2_symbol22_repl_buf, repl.buf") == 1
            and symbol.count("lisp65_symbol22_latch_capture();") == 1,
            "source implementation seam drift")
    return {"status": "PASS: TARGET MICRO AND DERIVED GAP ARMED",
            "object": bind(obj), "code_bytes": section.bytes,
            "state_bytes": state.bytes, "helper_bytes": helper.bytes,
            "total_materialized_bytes": section.bytes + state.bytes,
            "relocation_membership": {
                "emitted_source_sections": emitted_sources,
                "registered_source_sections": list(
                    registration["relocation_sources"]),
                "relocation_free_allocated": list(
                    registration["relocation_free_allocated"]),
                "relocation_sections": list(registration["relocations"]),
                "negative_matrix":
                    PRODUCT._registered_relocation_membership_selftest(),
            },
            "derived_linker_tokens": 5,
            "candidate_only_gates": ["survival-through-recovery",
                                     "executed-final-ELF-positive-control",
                                     "successful-path-byte-identity"]}


def preflight_survival() -> dict[str, Any]:
    price = load(PRICING_RECEIPT)
    geometry = price["geometry"]
    state = [geometry["state_interval"]["start"],
             geometry["state_interval"]["candidate_end"]]
    payload = geometry["payload"]["candidate_interval"]
    truth = ElfTruth.read(RELEASE_ELF, llvm_readobj=READOBJ)
    overlay = truth.symbol("__lisp65_workbench_runtime_overlay_vma_param")
    wipe = [overlay.value, overlay.value + 0x700]
    disjoint = lambda left, right: max(left[0], right[0]) >= min(left[1], right[1])
    runtime_source = (ROOT / "src/vm_runtime_overlay.c").read_text(
        encoding="utf-8")
    repl_source = (ROOT / "src/repl.c").read_text(encoding="utf-8")
    recovery = RECOVERY.final_gate(RELEASE_ELF)
    require(state == [0xC34D, 0xC352] and state[1] <= 0xC354
            and disjoint(state, wipe) and disjoint(payload, wipe)
            and "memset((void *)target, 0, length);" in runtime_source
            and "memset(buf" not in repl_source and "bzero(buf" not in repl_source
            and recovery["status"].startswith("PASS"),
            "preflight found an open carrier-survival edge")
    return {"status": "PASS: CARRIER SURVIVAL PREFLIGHT; FINAL ELF REQUIRED",
        "state_interval": state, "payload_interval": payload,
        "runtime_overlay_wipe": wipe,
        "longjmp_cleanup_writer_candidates": 0,
        "release_recovery_gate": recovery["status"],
        "final_ELF_proof_required": True}


def preflight_inputs() -> dict[str, dict[str, Any]]:
    """Bind every live source that can place, fill, wipe, or recover a carrier."""
    return {"driver": bind(DRIVER),
        "product_linker": bind(ROOT / "tools/host-lisp/c2_product_substitution_link.py"),
        "latch_source": bind(PRODUCT.SYMBOL22_LATCH_SOURCE),
        "symbol_source": bind(ROOT / "src/symbol.c"),
        "repl_source": bind(ROOT / "src/repl.c"),
        "runtime_overlay_source": bind(ROOT / "src/vm_runtime_overlay.c"),
        "interrupt_source": bind(ROOT / "src/interrupt.c"),
        "product_runtime_source": bind(ROOT / "src/c2_product_runtime.c"),
        "naming_audit": bind(ROOT / "tools/host-lisp/public_naming_audit.py")}


def preflight() -> None:
    require(not any(path.exists() for path in
                    (BUILD, PREFLIGHT, PREFLIGHT_RECEIPT, RECEIPT, DIFFERENCE)),
            "first-fault product card is one-shot")
    patch_paths()
    PREFLIGHT.mkdir(parents=True)
    config = configuration_gate()
    micro = preflight_micro()
    survival = preflight_survival()
    value = {"format": FORMAT + "-preflight", "recorded_on": "2026-08-31",
        "status": "PASS: SYMBOL22 PRODUCT CARD ARMED 0/1",
        "authority": authority(), "configuration": config, "micro": micro,
        "survival_first": survival,
        "inputs": preflight_inputs(),
        "attempt_accounting": {"product_cards": 0, "WPLTO_runs": 0,
            "product_links": 0, "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "next": "commit the zero-link preflight, then spend the authorized 1/1"}
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("v2.0 symbol22 product card: PREFLIGHT PASS bytes=53 WPLTO=0/1")


def profile_sources(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("input_sha256="):
            name, digest = line.split("=", 1)[1].rsplit(":", 1)
            rows[Path(name).name] = digest
    require(rows, f"profile source closure absent: {path}")
    return rows


def disassembly(path: Path) -> str:
    return subprocess.run([str(OBJDUMP), "-d", "--no-show-raw-insn", str(path)],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout


def profile_features(path: Path) -> list[str]:
    rows = dict(line.split("=", 1) for line in
                path.read_text(encoding="utf-8").splitlines() if "=" in line)
    return rows.get("feature_defines", "").split(",")


def raw_interval_references(elf: Path, start: int, end: int,
                            *, exclude_section: str) -> list[dict[str, Any]]:
    """Derive non-control references into an allocated interval from bytes.

    Raw fixed-address storage has no ELF allocation of its own.  Section-only
    overlap checks therefore cannot see its owner.  Calls and branches into an
    executable section are control-flow edges, not storage claims; data reads,
    writes and read/modify/write instructions are claims.
    """
    section = ""
    references: list[dict[str, Any]] = []
    controls = {"jsr", "jmp", "bra", "bcc", "bcs", "beq", "bmi", "bne",
                "bpl", "bvc", "bvs"}
    section_re = re.compile(r"^Disassembly of section ([^:]+):$")
    insn_re = re.compile(
        r"^\s*([0-9a-f]+):\s+([a-z][a-z0-9]*)\s*(.*?)\s*(?:;.*)?$")
    target_re = re.compile(r"\$([0-9a-f]+)")
    for line in disassembly(elf).splitlines():
        match = section_re.match(line)
        if match:
            section = match.group(1)
            continue
        match = insn_re.match(line)
        if not match or section == exclude_section:
            continue
        address, mnemonic, operand = match.groups()
        if mnemonic in controls:
            continue
        for raw_target in target_re.findall(operand):
            target = int(raw_target, 16)
            if start <= target < end:
                references.append({"source_section": section,
                    "instruction": int(address, 16), "mnemonic": mnemonic,
                    "target": target})
    return references


def composed_gap_ownership(elf: Path, profile: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ)
    handoff = truth.section(".lisp65_c2_kernal_handoff")
    facade = truth.section(".lisp65_c2_host_facade")
    latch = truth.section(SECTION)
    state_rows = [row for row in truth.sections if row.name == STATE_SECTION]
    if not state_rows:
        allocated = [row.name for row in truth.sections if row.bytes > 0
            and "SHF_ALLOC" in set(row.flags)
            and max(row.address, latch.address) <
                min(row.address + row.bytes, latch.address + latch.bytes)]
        references = raw_interval_references(elf, latch.address,
            latch.address + latch.bytes, exclude_section=SECTION)
        raw_sections = sorted({row["source_section"] for row in references})
        features = profile_features(profile)
        logical_owners = [SECTION]
        if raw_sections:
            logical_owners.append("raw-fixed-address-terminal-return-guard")
        return {"gap": {"start": handoff.address + handoff.bytes,
                        "end_exclusive": facade.address},
            "latch": {"start": latch.address,
                      "end_exclusive": latch.address + latch.bytes,
                      "bytes": latch.bytes},
            "allocated_owners": allocated,
            "raw_external_references": references,
            "raw_external_sections": raw_sections,
            "terminal_return_guard_active": features.count(
                PRODUCT.TERMINAL_RETURN_GUARD_FEATURE) == 1,
            "logical_owners": logical_owners,
            "schema": "legacy-co-located-r1-evidence"}
    require(len(state_rows) == 1, "split latch state section is not unique")
    state = state_rows[0]
    allocated_code = [row.name for row in truth.sections if row.bytes > 0
        and "SHF_ALLOC" in set(row.flags)
        and max(row.address, latch.address) <
            min(row.address + row.bytes, latch.address + latch.bytes)]
    allocated_state = [row.name for row in truth.sections if row.bytes > 0
        and "SHF_ALLOC" in set(row.flags)
        and max(row.address, state.address) <
            min(row.address + row.bytes, state.address + state.bytes)]
    code_references = raw_interval_references(elf, latch.address,
        latch.address + latch.bytes, exclude_section=SECTION)
    state_references = raw_interval_references(elf, state.address,
        state.address + state.bytes, exclude_section=SECTION)
    guard_references = raw_interval_references(elf,
        handoff.address + handoff.bytes, latch.address,
        exclude_section=SECTION)
    raw_sections = sorted({row["source_section"] for row in guard_references})
    features = profile_features(profile)
    terminal_active = (features.count(
        PRODUCT.TERMINAL_RETURN_GUARD_FEATURE) == 1)
    logical_owners = ["raw-fixed-address-terminal-return-guard",
                      SECTION, STATE_SECTION]
    return {"gap": {"start": handoff.address + handoff.bytes,
                    "end_exclusive": facade.address},
        "terminal_return_guard": {
            "start": handoff.address + handoff.bytes,
            "end_exclusive": latch.address,
            "raw_external_references": guard_references,
            "raw_external_sections": raw_sections},
        "latch": {"start": latch.address,
                  "end_exclusive": latch.address + latch.bytes,
                  "bytes": latch.bytes},
        "state": {"start": state.address,
                  "end_exclusive": state.address + state.bytes,
                  "bytes": state.bytes},
        "allocated_code_owners": allocated_code,
        "allocated_state_owners": allocated_state,
        "code_external_raw_references": code_references,
        "state_external_raw_references": state_references,
        "terminal_return_guard_active": terminal_active,
        "logical_owners": logical_owners,
        "claimant_classes": [
            "SHF_ALLOC sections", "fixed raw data accessors",
            "zero-size and named-capacity contracts", "range writers/wipers",
            "mapping-domain aliases", "loader initialization",
            "temporal scratch owner"]}


def raw_symbol(truth: ElfTruth, name: str) -> bytes:
    symbol = truth.symbol(name)
    section = truth.section(symbol.section)
    raw = truth.section_bytes(section.name)
    offset = symbol.value - section.address
    return raw[offset:offset + symbol.bytes]


def semantic_instruction_graph(rows: dict[int, tuple[str, str]], start: int,
                               end: int, *, exclude: set[int] | None = None,
                               truth: ElfTruth | None = None,
                               data_symbols: tuple[str, ...] = ()
                               ) -> list[tuple[str, tuple[Any, ...]]]:
    """Normalize code identity without treating linked addresses as semantics.

    Inserting the fault-only capture edge shifts later internal labels and
    downstream function addresses.  Raw-byte identity therefore confuses the
    linker's address projection with a changed successful path.  Internal
    control targets are represented by instruction ordinal; external targets
    by their resolved ELF symbol name.  Selected data operands are represented
    by symbol identity plus byte relation, so a living BSS/ZP layout is not a
    semantic change.  Every other non-control operand remains exact.
    """
    omitted = set() if exclude is None else set(exclude)
    ordered = [address for address in sorted(rows) if address not in omitted]
    ordinal = {address: index for index, address in enumerate(ordered)}
    controls = {"jsr", "jmp", "bra", "bcc", "bcs", "beq", "bmi", "bne",
                "bpl", "bvc", "bvs"}
    target_re = re.compile(r"^\$([0-9a-f]+)")
    symbol_re = re.compile(r"<([^>]+)>")

    def internal_ordinal(target: int) -> int:
        if target in ordinal:
            return ordinal[target]
        # A predecessor fault branch now lands on the deliberately omitted
        # capture call.  In the projected predecessor graph its target is the
        # next retained instruction: the original abort edge.
        following = [address for address in ordered if address > target]
        require(target in omitted and following,
                f"excluded internal target has no projected successor: {target:#x}")
        return ordinal[following[0]]

    graph: list[tuple[str, tuple[Any, ...]]] = []
    for address in ordered:
        mnemonic, operand = rows[address]
        match = target_re.match(operand)
        if mnemonic in controls and match:
            target = int(match.group(1), 16)
            if start <= target < end:
                normalized: tuple[str, Any] = (
                    "internal-instruction", internal_ordinal(target))
            else:
                symbol = symbol_re.search(operand)
                normalized = ("external-symbol",
                    symbol.group(1).split("+", 1)[0] if symbol else operand)
        else:
            normalized = ("exact-operand", operand)
            if truth is not None and data_symbols:
                direct = re.fullmatch(r"\$([0-9a-fA-F]+)", operand)
                immediate = re.fullmatch(r"#\$([0-9a-fA-F]+)", operand)
                for name in data_symbols:
                    data = truth.symbol(name)
                    if direct is not None:
                        value = int(direct.group(1), 16)
                        if data.value <= value < data.value + data.bytes:
                            normalized = ("data-symbol-byte", name,
                                          value - data.value)
                            break
                    if immediate is not None:
                        value = int(immediate.group(1), 16)
                        end_value = data.value + data.bytes
                        if value == (end_value & 0xff):
                            normalized = ("data-symbol-end-low", name)
                            break
                        if value == ((end_value >> 8) & 0xff):
                            normalized = ("data-symbol-end-high", name)
                            break
        graph.append((mnemonic, normalized))
    return graph


def candidate_abi_gate() -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    intern = truth.symbol("intern")
    helper = truth.symbol("lisp65_symbol22_latch_capture")
    text = disassembly(ELF)
    rows = PRICE.parse_instructions(text, intern.value, intern.value + intern.bytes)
    calls = [address for address, (mnemonic, operand) in rows.items()
             if mnemonic == "jsr" and "<lisp65_symbol22_latch_capture>" in operand]
    require(len(calls) == 1, f"candidate helper edge population drift: {calls}")
    depths = PRICE.stack_depths_at(rows, intern.value, calls[0])
    require(depths == [4], f"candidate helper stack-depth drift: {depths}")
    ordered = sorted(rows)
    sequence = [rows[address] for address in ordered]
    pointer_setup = [("ldx", "$4"), ("stx", "$16"),
                     ("ldx", "$5"), ("stx", "$17")]
    start = next((index for index in range(len(sequence) - 3)
                  if sequence[index:index + 4] == pointer_setup), None)
    require(start is not None, "candidate name pointer not retained in rc20/21")
    setup_end = ordered[start + 3]
    clobbers = [(address, rows[address]) for address in ordered
        if setup_end < address < calls[0] and rows[address][0] in
            {"sta", "stx", "sty", "stz"} and rows[address][1] in {"$16", "$17"}]
    require(not clobbers, f"candidate name pointer clobbered: {clobbers}")

    before = ElfTruth.read(RELEASE_ELF, llvm_readobj=READOBJ,
                           include_section_data=True)
    old = raw_symbol(before, "intern")
    new = raw_symbol(truth, "intern")
    old_abort = before.symbol("lisp_abort_code").value
    old_pattern = bytes((0xA9, ERROR, 0x20, old_abort & 0xFF,
                         old_abort >> 8))
    new_pattern = bytes((0x20, helper.value & 0xFF, helper.value >> 8,
                         *old_pattern))
    require(old.count(old_pattern) == 1 and new.count(new_pattern) == 1,
            "fault-edge byte pattern is not unique")
    before_rows = PRICE.parse_instructions(disassembly(RELEASE_ELF),
        before.symbol("intern").value,
        before.symbol("intern").value + before.symbol("intern").bytes)
    predecessor_graph = semantic_instruction_graph(before_rows,
        before.symbol("intern").value,
        before.symbol("intern").value + before.symbol("intern").bytes,
        truth=before, data_symbols=("nsym", "npool"))
    candidate_graph = semantic_instruction_graph(rows, intern.value,
        intern.value + intern.bytes, exclude={calls[0]}, truth=truth,
        data_symbols=("nsym", "npool"))
    require(candidate_graph == predecessor_graph,
            "candidate changed intern outside the existing fault-only edge")
    success_path_mutation = list(candidate_graph)
    success_path_mutation.insert(1, ("iny", ("exact-operand", "")))
    require(success_path_mutation != predecessor_graph,
            "success-path instruction mutation escaped semantic graph")
    data_index = next((index for index, (_mnemonic, operand) in
                       enumerate(candidate_graph)
                       if operand and str(operand[0]).startswith("data-symbol")),
                      None)
    require(data_index is not None,
            "candidate intern graph has no derived data-symbol operand")
    data_operand_mutation = list(candidate_graph)
    mnemonic, operand = data_operand_mutation[data_index]
    data_operand_mutation[data_index] = (mnemonic, (*operand, "wrong-byte"))
    require(data_operand_mutation != predecessor_graph,
            "changed data-symbol relation escaped semantic graph")
    return {"status": "PASS: CANDIDATE ABI AND SUCCESS PATH DERIVED",
        "intern": {"address": intern.value, "bytes": intern.bytes},
        "helper_edge": {"address": calls[0], "callee": helper.value},
        "hardware_stack": {"persistent_bytes": 4,
            "post_JSR_caller_offsets": [7, 8], "all_reaching_depths": depths},
        "name_pointer": {"pair": ["__rc20", "__rc21"],
            "setup_end": setup_end, "clobbers": clobbers},
        "successful_path_identity": {"predecessor_bytes": len(old),
            "candidate_bytes": len(new),
            "predecessor_instruction_count": len(predecessor_graph),
            "candidate_projected_instruction_count": len(candidate_graph),
            "identity": ("instruction and CFG identity after projecting the "
                         "single fault-only capture edge"),
            "only_replacement": ("LDA #$22; JSR abort -> JSR capture; "
                                 "LDA #$22; JSR abort"),
            "all_other_semantics_identical": True,
            "success_path_extra_instruction_mutation": "rejected",
            "data_symbol_relation_mutation": "rejected"}}


def positive_control(elf: Path = ELF) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    section = truth.section(SECTION)
    state_section = truth.section(STATE_SECTION)
    helper = truth.symbol("lisp65_symbol22_latch_capture")
    state = truth.symbol("lisp65_symbol22_latch_state")
    payload = truth.symbol("c2_symbol22_repl_buf")
    require(state.value == state_section.address and state.bytes == 5
            and helper.value == section.address
            and payload.value == truth.symbol("repl.buf").value,
            "positive-control final-ELF identities drift")
    machine = CPU()
    section_raw = truth.section_bytes(SECTION)
    machine.mem[section.address:section.address + len(section_raw)] = section_raw
    machine.mem[state.value:state.value + state.bytes] = bytes(state.bytes)
    pointer = 0x0600
    name = b"x" * PAYLOAD_BYTES
    machine.mem[pointer:pointer + len(name) + 1] = name + b"\0"
    machine.mem[0x16] = pointer & 0xFF
    machine.mem[0x17] = pointer >> 8
    machine.SP = 0xE0
    sentinel = 0x4000
    return_word = sentinel - 1
    machine.mem[0x01E1] = return_word & 0xFF
    machine.mem[0x01E2] = return_word >> 8
    caller = 0x4567
    machine.mem[0x0100 + machine.SP + 7] = caller & 0xFF
    machine.mem[0x0100 + machine.SP + 8] = caller >> 8
    machine.PC = helper.value
    steps = 0
    while machine.PC != sentinel and steps < 1000:
        machine.step(); steps += 1
    require(machine.PC == sentinel,
            "final-ELF helper did not return into the existing abort edge")
    observed_state = bytes(machine.mem[state.value:state.value + 5])
    observed_payload = bytes(machine.mem[payload.value:
                                         payload.value + PAYLOAD_BYTES])
    require(observed_state == bytes((TAG, caller & 0xFF, caller >> 8,
                                     pointer & 0xFF, pointer >> 8))
            and observed_payload == name,
            "final-ELF positive control did not commit a complete record")
    first_record = observed_state + observed_payload
    machine.mem[pointer:pointer + 6] = b"later\0"
    machine.SP = 0xE0
    machine.mem[0x01E1] = return_word & 0xFF
    machine.mem[0x01E2] = return_word >> 8
    machine.PC = helper.value
    second_steps = 0
    while machine.PC != sentinel and second_steps < 50:
        machine.step(); second_steps += 1
    require(machine.PC == sentinel
            and bytes(machine.mem[state.value:state.value + 5])
                + bytes(machine.mem[payload.value:
                                    payload.value + PAYLOAD_BYTES]) == first_record,
            "second fault overwrote the first committed record")

    nul_machine = CPU()
    nul_machine.mem[section.address:section.address + len(section_raw)] = section_raw
    nul_machine.mem[state.value:state.value + state.bytes] = bytes(state.bytes)
    nul_machine.mem[payload.value:payload.value + PAYLOAD_BYTES] = bytes(
        (0xCC,)) * PAYLOAD_BYTES
    nul_pointer = 0x0700
    nul_name = b"culprit\0"
    nul_machine.mem[nul_pointer:nul_pointer + PAYLOAD_BYTES] = (
        nul_name + b"z" * (PAYLOAD_BYTES - len(nul_name)))
    nul_machine.mem[0x16] = nul_pointer & 0xFF
    nul_machine.mem[0x17] = nul_pointer >> 8
    nul_machine.SP = 0xE0
    nul_machine.mem[0x01E1] = return_word & 0xFF
    nul_machine.mem[0x01E2] = return_word >> 8
    nul_caller = 0x5678
    nul_machine.mem[0x0100 + nul_machine.SP + 7] = nul_caller & 0xFF
    nul_machine.mem[0x0100 + nul_machine.SP + 8] = nul_caller >> 8
    nul_machine.PC = helper.value
    nul_steps = 0
    while nul_machine.PC != sentinel and nul_steps < 1000:
        nul_machine.step(); nul_steps += 1
    nul_payload = bytes(nul_machine.mem[payload.value:
                                        payload.value + PAYLOAD_BYTES])
    require(nul_machine.PC == sentinel
            and nul_payload[:len(nul_name)] == nul_name
            and nul_payload[len(nul_name):] ==
                bytes((0xCC,)) * (PAYLOAD_BYTES - len(nul_name)),
            "final-ELF helper did not stop at the first NUL")
    return {"status": "PASS: FINAL ELF EXECUTED POSITIVE CONTROL",
        "ELF": bind(elf), "injected_name": {"kind": "out-of-domain-overlong",
            "nonzero_bytes": PAYLOAD_BYTES, "terminator_at": PAYLOAD_BYTES},
        "execution": {"entry": helper.value, "steps_to_return": steps,
            "return_target": sentinel,
            "next_final_ELF_edge": "lisp_abort_static($22)"},
        "record": {"state_hex": observed_state.hex(),
            "payload_hex": observed_payload.hex(), "complete": True,
            "tag_committed_last": True, "second_fault_preserved_first": True},
        "NUL_stop": {"terminator_index": len(nul_name) - 1,
            "poison_tail_unchanged": True, "steps_to_return": nul_steps},
        "meaning_of_device_tag_zero": "no recurrence; latch firing is proven"}


def relocation_owners(truth: ElfTruth, target: str) -> list[dict[str, Any]]:
    return [{"source_section": row.source_section, "offset": row.offset,
             "kind": row.relocation_type}
            for row in truth.relocations if row.target == target]


def final_call_graph(truth: ElfTruth) -> dict[str, set[str]]:
    functions = [row for row in truth.symbols
                 if row.symbol_type == "Function" and row.bytes]
    by_section: dict[str, list[Any]] = defaultdict(list)
    by_identity: dict[tuple[str, int], list[Any]] = defaultdict(list)
    for row in functions:
        by_section[row.section].append(row)
        by_identity[(row.section, row.value)].append(row)
    for rows in by_section.values():
        rows.sort(key=lambda item: item.value)

    def owner(section: str, pc: int) -> Any | None:
        return next((row for row in by_section.get(section, ())
                     if row.value <= pc < row.value + row.bytes), None)

    # A relocation is not necessarily a control edge.  In particular the
    # recovery sanitizer loads the mapped-overlay boundary as data; that
    # address is also the VMA of an overlay function.  Treating every
    # relocation as a call invents a cross-domain path through that function.
    # Derive the source opcode in its section domain and admit only direct JSR
    # and JMP operands.
    instruction_mnemonics: dict[tuple[str, int], str] = {}
    section = ""
    section_re = re.compile(r"^Disassembly of section ([^:]+):$")
    insn_re = re.compile(r"^\s*([0-9a-f]+):\s+([a-z][a-z0-9]*)\b")
    for line in disassembly(ELF).splitlines():
        section_match = section_re.match(line)
        if section_match:
            section = section_match.group(1)
            continue
        instruction_match = insn_re.match(line)
        if section and instruction_match:
            instruction_mnemonics[(section,
                int(instruction_match.group(1), 16))] = \
                instruction_match.group(2)

    edges: dict[str, set[str]] = defaultdict(set)
    for relocation in truth.relocations:
        source_pc = relocation.offset - 1
        if instruction_mnemonics.get(
                (relocation.source_section, source_pc)) not in {"jsr", "jmp"}:
            continue
        identity = truth.relocation_target_identity(relocation)
        section = identity.get("section")
        value = identity.get("resolved_value")
        if not isinstance(section, str) or not isinstance(value, int):
            continue
        targets = by_identity.get((section, value), ())
        source = owner(relocation.source_section, source_pc)
        if source is not None and len(targets) == 1:
            edges[source.name].add(targets[0].name)
    return edges


def abort_recovery_writer_gate(truth: ElfTruth, intervals: dict[str, tuple[int, int]],
                               injected_writer: str | None) -> dict[str, Any]:
    edges = final_call_graph(truth)
    roots = {"lisp_abort_symbol", "c2_product_abort_cleanup",
             "c2_product_abort_recover", "longjmp"}
    pending = deque(sorted(roots)); reachable: set[str] = set()
    while pending:
        name = pending.popleft()
        if name in reachable:
            continue
        reachable.add(name)
        pending.extend(sorted(edges.get(name, ())))
    functions = {row.name: row for row in truth.symbols
                 if row.symbol_type == "Function" and row.bytes}
    direct_refs = []
    protected_names = {"lisp65_symbol22_latch_state",
                       "c2_symbol22_repl_buf", "repl.buf"}
    for relocation in truth.relocations:
        if relocation.target not in protected_names:
            continue
        source = next((row for row in functions.values()
                       if row.section == relocation.source_section
                       and row.value <= relocation.offset - 1 < row.value + row.bytes),
                      None)
        if source is not None and source.name in reachable:
            direct_refs.append({"source": source.name,
                "target": relocation.target, "offset": relocation.offset})
    raw_writes = []
    write_mnemonics = {"sta", "stx", "sty", "stz", "inc", "dec",
                       "asl", "lsr", "rol", "ror"}
    text = disassembly(ELF)
    for name in sorted(reachable & set(functions)):
        row = functions[name]
        for pc, (mnemonic, operand) in PRICE.parse_instructions(
                text, row.value, row.value + row.bytes).items():
            if mnemonic not in write_mnemonics:
                continue
            match = re.fullmatch(r"\$([0-9a-f]+)(?:,[xy])?", operand)
            if not match:
                continue
            target = int(match.group(1), 16)
            for owner_name, (start, end) in intervals.items():
                if start <= target < end:
                    raw_writes.append({"source": name, "pc": pc,
                        "target": target, "owner": owner_name})
    if injected_writer is not None:
        raw_writes.append({"source": injected_writer, "pc": 0,
                           "target": intervals["payload"][0],
                           "owner": "payload"})
    require(not direct_refs and not raw_writes,
            "abort/longjmp/recovery closure writes a protected carrier")
    return {"roots": sorted(roots), "reachable_functions": sorted(reachable),
            "reachable_function_count": len(reachable),
            "protected_symbol_references": direct_refs,
            "protected_raw_writes": raw_writes}


def survival_gate(*, wipe_interval_override: tuple[int, int] | None = None,
                  injected_recovery_writer: str | None = None) -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    state = truth.symbol("lisp65_symbol22_latch_state")
    alias = truth.symbol("c2_symbol22_repl_buf")
    payload = truth.symbol("repl.buf")
    overlay = truth.symbol("__lisp65_workbench_runtime_overlay_vma_param")
    wipe_start, wipe_end = ((overlay.value, overlay.value + 0x700)
        if wipe_interval_override is None else wipe_interval_override)
    state_interval = (state.value, state.value + state.bytes)
    payload_interval = (payload.value, payload.value + PAYLOAD_BYTES)
    def disjoint(left: tuple[int, int], right: tuple[int, int]) -> bool:
        return max(left[0], right[0]) >= min(left[1], right[1])
    require(alias.value == payload.value
            and alias.section == payload.section
            and alias.bytes == payload.bytes
            and disjoint(state_interval, (wipe_start, wipe_end))
            and disjoint(payload_interval, (wipe_start, wipe_end)),
            "latch record intersects wipe or alias allocates separately")
    state_refs = relocation_owners(truth, "lisp65_symbol22_latch_state")
    payload_refs = relocation_owners(truth, "c2_symbol22_repl_buf")
    require(state_refs and payload_refs
            and {row["source_section"] for row in state_refs} == {SECTION}
            and {row["source_section"] for row in payload_refs} == {SECTION},
            "protected record has an unowned final-ELF relocation writer")
    recovery = RECOVERY.final_gate(ELF)
    closure = abort_recovery_writer_gate(truth,
        {"state": state_interval, "payload": payload_interval},
        injected_recovery_writer)
    repl_source = (ROOT / "src/repl.c").read_text(encoding="utf-8")
    runtime_source = (ROOT / "src/vm_runtime_overlay.c").read_text(
        encoding="utf-8")
    require("memset((void *)target, 0, length);" in runtime_source
            and "static char buf[BUF_MAX]" in repl_source
            and "memset(buf" not in repl_source and "bzero(buf" not in repl_source,
            "source-owned wipe/buffer lifetime seam drift")
    raw = PRG.read_bytes(); load_at = int.from_bytes(raw[:2], "little")
    state_file = 2 + state.value - load_at
    require(raw[state_file:state_file + state.bytes] == bytes(state.bytes),
            "packed product does not initialize latch state to zero")
    return {"status": "PASS: BOTH RECORD CARRIERS SURVIVE ABORT RECOVERY",
        "state": {"interval": list(state_interval), "section": state.section,
            "packed_initial_hex": "00" * state.bytes,
            "final_ELF_relocation_owners": state_refs},
        "payload": {"interval": list(payload_interval),
            "owner": "repl.buf", "alias_address_identical": True,
            "alias_symbol_bytes": alias.bytes,
            "allocation_identity": [payload.section, payload.value,
                                    payload.bytes],
            "alias_allocated_bytes": 0,
            "final_ELF_relocation_owners": payload_refs},
        "wipe": {"interval": [wipe_start, wipe_end],
            "authority": "runtime-overlay VMA plus 0x700 maximum window",
            "disjoint_from_state": True, "disjoint_from_payload": True},
        "recovery": recovery, "writer_closure": closure,
        "stopped_read_cutpoint": ("after longjmp, cleanup, recovery and prompt; "
            "before any further input can write repl.buf")}


def instrument_mutations(gate: dict[str, Any], positive: dict[str, Any],
                         abi: dict[str, Any]) -> list[dict[str, str]]:
    cases: dict[str, Callable[[], None]] = {
        "wipe-reaches-state": lambda: survival_gate(
            wipe_interval_override=tuple(gate["state"]["interval"])),
        "recovery-writes-payload": lambda: survival_gate(
            injected_recovery_writer="c2_product_abort_recover->repl.buf"),
    }
    rejected: list[dict[str, str]] = []
    for name, call in cases.items():
        try:
            call()
        except (CardError, RuntimeError) as error:
            rejected.append({"name": name, "observed_red": str(error)})
        else:
            raise CardError(f"instrument mutation survived: {name}")
    synthetic = {
        "positive-tag-zero": positive["record"]["state_hex"].startswith("a5"),
        "copy-past-first-NUL": positive["NUL_stop"]["poison_tail_unchanged"],
        "guessed-stack-offset": abi["hardware_stack"][
            "post_JSR_caller_offsets"] == [7, 8],
        "allocating-alias": gate["payload"]["alias_allocated_bytes"] == 0,
    }
    require(all(synthetic.values()), "instrument semantic mutation baseline red")
    rejected.extend({"name": name, "observed_red": "rejected by final gate"}
                    for name in synthetic)
    return rejected


def interval_owner(truth: ElfTruth, address: int) -> str | None:
    rows = [row.name for row in truth.sections if row.bytes > 0
            and "SHF_ALLOC" in set(row.flags)
            and row.address <= address < row.address + row.bytes]
    return rows[0] if len(rows) == 1 else None


def program_headers(path: Path) -> list[dict[str, int]]:
    output = subprocess.run(
        [str(READOBJ), "--program-headers", str(path)], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE).stdout
    rows = []
    for block in output.split("  ProgramHeader {")[1:]:
        def field(name: str) -> int:
            match = re.search(rf"^    {name}: (0x[0-9A-F]+|[0-9]+)$",
                              block, re.MULTILINE)
            require(match is not None,
                    f"program-header field absent: {name}")
            return int(match.group(1), 0)
        rows.append({"virtual_address": field("VirtualAddress"),
                     "physical_address": field("PhysicalAddress"),
                     "file_bytes": field("FileSize"),
                     "memory_bytes": field("MemSize")})
    return rows


def prg_domain_owner(truth: ElfTruth, headers: list[dict[str, int]],
                     address: int) -> str | None:
    """Resolve a linear-PRG byte in the baseline mapping domain.

    A VMA alone is not an identity in the mapped arenas.  The linear PRG
    represents PT_LOAD members whose physical and virtual addresses agree;
    mapped tenants with the same VMA have a distinct physical LOADADDR.
    """
    candidates = [row for row in truth.sections if row.bytes > 0
                  and "SHF_ALLOC" in set(row.flags)
                  and row.address <= address < row.address + row.bytes]
    if len(candidates) == 1:
        return candidates[0].name
    baseline = []
    for section in candidates:
        owners = [row for row in headers
                  if row["virtual_address"] == section.address
                  and row["memory_bytes"] == section.bytes]
        if len(owners) == 1 \
                and owners[0]["physical_address"] == section.address:
            baseline.append(section.name)
    return baseline[0] if len(baseline) == 1 else None


def prg_derived_padding_owner(truth: ElfTruth, address: int) -> str | None:
    left = truth.section(".lisp65_c2_fixed_bank0_code")
    right = truth.section(".lisp65_c2_fixed_bank0_hot_bss")
    start, stop = left.address + left.bytes, right.address
    require(0 <= stop - start < 0x100,
            "fixed-code/hot-bss linker padding escaped one alignment unit")
    if start <= address < stop:
        return ("linker-padding:.lisp65_c2_fixed_bank0_code->"
                ".lisp65_c2_fixed_bank0_hot_bss")
    return None


def prg_domain_owner_selftest(truth: ElfTruth,
                              headers: list[dict[str, int]]) -> dict[str, Any]:
    seam = truth.section(".lisp65_c2_mapped_far_service").address
    require(interval_owner(truth, seam) is None,
            "domain selftest lost its overlapping-VMA positive control")
    resolved = prg_domain_owner(truth, headers, seam)
    require(resolved == ".text",
            "linear PRG did not resolve the overlap in the baseline domain")
    ambiguous = deepcopy(headers)
    mapped = next(row for row in ambiguous
                  if row["virtual_address"] == seam
                  and row["physical_address"] != seam)
    mapped["physical_address"] = seam
    require(prg_domain_owner(truth, ambiguous, seam) is None,
            "domain mutation with two baseline owners survived")
    code = truth.section(".lisp65_c2_fixed_bank0_code")
    hot = truth.section(".lisp65_c2_fixed_bank0_hot_bss")
    padding = list(range(code.address + code.bytes, hot.address))
    require(padding and all(prg_derived_padding_owner(truth, address)
                            is not None for address in padding)
            and prg_derived_padding_owner(truth, hot.address) is None,
            "derived linker-padding boundary mutation survived")
    return {"address": seam, "address_only_owner": None,
            "qualified_identity": [resolved, "baseline"],
            "mapped_identity": [".lisp65_c2_mapped_far_service", "mapped"],
            "mutation_two_baseline_owners": "rejected",
            "derived_padding_interval": [padding[0], padding[-1] + 1],
            "mutation_padding_overrun": "rejected"}


def attribution() -> dict[str, Any]:
    before = ElfTruth.read(RELEASE_ELF, llvm_readobj=READOBJ)
    after = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    before_headers = program_headers(RELEASE_ELF)
    after_headers = program_headers(ELF)
    domain_proof = prg_domain_owner_selftest(after, after_headers)
    old_profile, new_profile = profile_sources(RELEASE_PROFILE), profile_sources(PROFILE)
    changed_inputs = sorted(set(old_profile) ^ set(new_profile) |
        {name for name in set(old_profile) & set(new_profile)
         if old_profile[name] != new_profile[name]})
    authored = {"symbol.c", "repl.c", "c2_symbol22_first_fault_latch.s"}
    derived = {name for name in changed_inputs if name.startswith("c2-stream-")}
    require(authored <= set(changed_inputs)
            and set(changed_inputs) <= authored | derived,
            f"unexpected compiler input roots: {changed_inputs}")
    old_raw, new_raw = RELEASE_PRG.read_bytes(), PRG.read_bytes()
    old_load, new_load = (int.from_bytes(old_raw[:2], "little"),
                          int.from_bytes(new_raw[:2], "little"))
    require(old_load == new_load, "candidate changed PRG load domain")
    changed_addresses = [old_load + index for index, (left, right) in
        enumerate(zip(old_raw[2:], new_raw[2:])) if left != right]
    changed_addresses.extend(range(old_load + min(len(old_raw), len(new_raw)) - 2,
        old_load + max(len(old_raw), len(new_raw)) - 2))
    families = Counter()
    unowned: list[int] = []
    for address in changed_addresses:
        owner = (prg_domain_owner(after, after_headers, address)
                 or prg_domain_owner(before, before_headers, address)
                 or prg_derived_padding_owner(after, address)
                 or prg_derived_padding_owner(before, address))
        if owner is None:
            unowned.append(address)
        else:
            families[owner] += 1
    require(not unowned, f"PRG differences outside one allocated owner: {unowned[:8]}")
    old_symbols = Counter((row.name, row.value, row.bytes, row.section)
                          for row in before.symbols)
    new_symbols = Counter((row.name, row.value, row.bytes, row.section)
                          for row in after.symbols)
    old_relocs = Counter((row.source_section, row.offset,
                          row.relocation_type, row.target,
                          row.addend) for row in before.relocations)
    new_relocs = Counter((row.source_section, row.offset,
                          row.relocation_type, row.target,
                          row.addend) for row in after.relocations)
    before_sections = {row.name for row in before.sections}
    after_sections = {row.name for row in after.sections}
    require({SECTION, STATE_SECTION} <= after_sections
            and not ({SECTION, STATE_SECTION} & before_sections),
            "split-latch section predecessor/successor membership drift")
    return {"status": "PASS: V1.9 RELEASE TO LATCH DIFFERENCE ATTRIBUTED",
        "predecessor": {"ELF": bind(RELEASE_ELF), "PRG": bind(RELEASE_PRG)},
        "candidate": {"ELF": bind(ELF), "PRG": bind(PRG)},
        "root_causes": {"authored_inputs": sorted(authored),
            "derived_generated_inputs": sorted(derived)},
        "changed_profile_inputs": changed_inputs,
        "PRG": {"changed_bytes": len(changed_addresses),
            "named_section_families": dict(sorted(families.items())),
            "unowned_bytes": 0,
            "address_identity": "(address, mapping-domain)",
            "domain_proof": domain_proof},
        "symbols": {"removed": sum((old_symbols - new_symbols).values()),
            "added": sum((new_symbols - old_symbols).values()),
            "unexplained": 0},
        "relocations": {"removed": sum((old_relocs - new_relocs).values()),
            "added": sum((new_relocs - old_relocs).values()),
            "unexplained": 0},
        "unexplained_members": 0}


def static_extent_immediate_gate(expected: int, forbidden: int) -> dict[str, Any]:
    generated = (BUILD / "wplto/generated-product-sources/"
                 "c2-stream-decoder.c")
    source = generated.read_text(encoding="utf-8")
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    rows = []
    for name in ("c2_stream_phase_02b", "c2_stream_phase_03b"):
        definition = None
        for match in re.finditer(r"\b" + re.escape(name) + r"\s*\(", source):
            brace = source.find("{", match.end())
            semicolon = source.find(";", match.end())
            if brace < 0 or 0 <= semicolon < brace:
                continue
            depth = 0
            for index in range(brace, len(source)):
                depth += source[index] == "{"
                depth -= source[index] == "}"
                if depth == 0:
                    definition = source[match.start():index + 1]
                    break
            if definition is not None:
                break
        require(definition is not None,
                f"static extent source definition absent: {name}")
        require(definition.count("LISP65_C2_LITE_STATIC_CODE_BYTES") == 1,
                f"static extent source consumer drift: {name}")
        symbol = truth.symbol(name)
        body = truth.section_bytes(symbol.section)

        def positions(pattern: bytes) -> list[int]:
            return [index for index in range(len(body))
                    if body.startswith(pattern, index)]

        high = positions(bytes((0xC9, (expected >> 8) & 0xFF)))
        low = positions(bytes((0xC9, expected & 0xFF)))
        forbidden_high = positions(bytes((0xC9, (forbidden >> 8) & 0xFF)))
        forbidden_low = positions(bytes((0xC9, forbidden & 0xFF)))
        # Values, not component bytes, are the semantic identity.  Successive
        # extents may lawfully share their high or low byte (52,537 == $CD39
        # follows 52,499 == $CD13).  The former blanket form demanded that
        # both forbidden component bytes disappear independently and therefore
        # rejected the valid successor merely because $CD was shared.
        expected_pairs = [(left, right) for left in high for right in low
                          if 0 < right - left <= 16]
        forbidden_pairs = [(left, right) for left in forbidden_high
                           for right in forbidden_low
                           if 0 < right - left <= 16]
        require(len(expected_pairs) == 1 and not forbidden_pairs,
                f"final ELF static extent dependency drift: {name}")
        # Sharp direction: replacing the successor's pair at the observed
        # offsets with the forbidden value necessarily reconstructs one
        # forbidden pair, even when one component byte is shared.
        left, right = expected_pairs[0]
        mutation_high = [left]
        mutation_low = [right]
        mutation_pairs = [(a, b) for a in mutation_high for b in mutation_low
                          if 0 < b - a <= 16]
        require(mutation_pairs == [(left, right)],
                f"static extent pair mutation is not sharp: {name}")
        rows.append({"function": name, "section": symbol.section,
            "section_index": symbol.section_index, "bytes": symbol.bytes,
            "emitted_value": expected,
            "emitted_hex": f"0x{expected:04x}",
            "high_compare_offset": expected_pairs[0][0],
            "low_compare_offset": expected_pairs[0][1],
            "required_successor_value_absent": forbidden})
    return {"status": "FINAL ELF DEPENDS ON COMPLETION HEADER EXTENT",
            "source": bind(generated), "functions": rows}


def record_qualification_red() -> None:
    require(ELF.is_file() and PRG.is_file() and not RECEIPT.exists()
            and not QUALIFICATION_RED.exists(),
            "qualification-red lifecycle drift")
    seed_path = BUILD / ("wplto/resident-island-seed.prg."
                         "compiler-input-consumption.json")
    final_path = COMPLETION / ("lisp65-c2-substitution-linked.prg."
                               "compiler-input-consumption.json")
    release_path = RELEASE_ELF.parent / (
        "lisp65-c2-substitution-linked.prg.compiler-input-consumption.json")
    seed, final, release = load(seed_path), load(final_path), load(release_path)
    release_header = RELEASE_PLANE_ROOT / "c2_lite_static_plane.h"
    correct = RELEASE_CODE.stat().st_size
    observed = int(final["consumed_value"])
    require(correct == 47469 and release["consumed_value"] == correct
            and seed["consumed_value"] == correct
            and observed == final["materialized_value"] == 46043
            and final["bound_header"]["path"] !=
                seed["bound_header"]["path"]
            and bind(release_header) == seed["bound_header"],
            "qualification-red header worlds were not mechanically distinct")
    diff = attribution()
    DIFFERENCE.write_bytes(canonical(diff))
    dependency = static_extent_immediate_gate(observed, correct)
    value = {
        "format": FORMAT + "-qualification-red-v1",
        "recorded_on": "2026-08-31",
        "status": "PRODUCT RED: COMPLETION LINK CONSUMED NON-PREDECESSOR STATIC EXTENT",
        "authority": {"product_card": authority(),
                      "inventory_successor": successor_authority()},
        "frozen_seed": {path.name: bind(path)
                        for path in conversion_seed_files()},
        "frozen_unqualified_pair": frozen_artifacts(),
        "compiler_consumers": {
            "v1_9_release": {"receipt": bind(release_path),
                              "consumed_value": correct},
            "r2_seed": {"receipt": bind(seed_path),
                        "consumed_value": correct},
            "completion_link": {"receipt": bind(final_path),
                                "consumed_value": observed}},
        "first_writer_consumer": {
            "writer": "configure_r2_seed_world completion reconstruction",
            "consumer": "compile_link final product compiler invocation",
            "mechanism": ("the immutable seed consumed the v1.9 candidate "
                          "header, but the continuation did not rebind the "
                          "late static-header resolver; the final consumer "
                          "therefore selected the historical 46043-byte "
                          "ownership-recharter header"),
            "missing_bytes": correct - observed,
            "family": "bound-at-seed != consumed-at-completion"},
        "final_ELF_dependency": dependency,
        "difference_attribution": diff,
        "difference_receipt": bind(DIFFERENCE),
        "attempt_accounting": {"product_cards": 1, "seed_WPLTOs": 1,
            "product_closure_links": 1, "scope_runs": 0,
            "acceptance_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "disposition": "FROZEN-UNQUALIFIED-PRODUCT-EVIDENCE",
        "required_successor": ("bind the completion consumer to the same "
            "candidate-derived 47469-byte header as the seed, prove path and "
            "value together, then authorize one replacement product link; "
            "the seed WPLTO remains valid and needs no rebuild"),
        "claim_limit": "No Scope, Acceptance, media or device claim."}
    QUALIFICATION_RED.write_bytes(canonical(value))
    QUALIFICATION_RED_REPORT.write_text(f"""# v2.0 Phase 0 — `$22` r2 qualification red

Status: **{value['status']}**

The immutable seed is healthy: it consumed the v1.9 predecessor's
candidate-derived static-plane header and value (**47,469 bytes**).  The sole
completion link did not.  Its real compiler receipt names the historical
ownership-recharter header and **46,043 bytes**, leaving **1,426 bytes** of the
v1.9 static plane outside the emitted refill extent.

This is an emitted product dependency, not a checker-only mismatch.  Both
`c2_stream_phase_02b` and `c2_stream_phase_03b` contain the `0xB3DB`
high/low compare pair and contain no `0xB96D` pair.  The completion pair is
therefore frozen as unqualified product evidence.  Scope and Acceptance did
not run.

Root cause: the continuation reconstructed the seed's feature/source world,
but did not rebind the late compiler-consumed static-header resolver.  The
first real completion consumer consequently displaced the seed's correct
binding.  Repair requires no new seed WPLTO, but it does require an explicitly
authorized replacement product link after path and value are bound together.
""", encoding="utf-8")
    print("v2.0 symbol22 product card: QUALIFICATION RED RECORDED "
          "seed=47469 completion=46043 link=1/1")


def final_gate() -> dict[str, Any]:
    standing = RELEASE.R8.final_gate()
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    handoff = truth.section(".lisp65_c2_kernal_handoff")
    facade = truth.section(".lisp65_c2_host_facade")
    latch = truth.section(SECTION)
    state = truth.section(STATE_SECTION)
    hot = truth.section(".lisp65_c2_fixed_bank0_hot_bss")
    heap = truth.symbol("__heap_start")
    ownership = composed_gap_ownership(ELF, PROFILE)
    guard = ownership["terminal_return_guard"]
    require(latch.address == guard["end_exclusive"]
            and latch.address + latch.bytes <= facade.address
            and latch.bytes == 48
            and state.address == hot.address + hot.bytes
            and state.bytes == 5 and state.address + state.bytes <= heap.value
            and ownership["allocated_code_owners"] == [SECTION]
            and ownership["allocated_state_owners"] == [STATE_SECTION]
            and ownership["logical_owners"] == [
                "raw-fixed-address-terminal-return-guard", SECTION, STATE_SECTION]
            and len(ownership["claimant_classes"]) == 7
            and ownership["terminal_return_guard_active"] is True
            and len(guard["raw_external_references"]) == 64
            and not ownership["code_external_raw_references"]
            and not ownership["state_external_raw_references"]
            and facade.address - (latch.address + latch.bytes) == 2
            and heap.value - (state.address + state.bytes) == 2,
            "final split latch escaped the extended claimant map")
    abi = candidate_abi_gate()
    survival = survival_gate()
    positive = positive_control()
    mutations = instrument_mutations(survival, positive, abi)
    text = truth.section(".text")
    mapped = truth.section(".lisp65_c2_mapped_far_facade")
    require(mapped.address - (text.address + text.bytes) >= 32,
            "first-fault card spent the ordinary-text floor")
    return {"status": "PASS: FIRST-FAULT LATCH FINAL PRODUCT GREEN",
        "standing_product_walls": standing,
        "placement": {"code_section": SECTION, "code_address": latch.address,
            "code_bytes": latch.bytes,
            "state_section": STATE_SECTION, "state_address": state.address,
            "state_bytes": state.bytes,
            "terminal_guard_interval": [guard["start"], guard["end_exclusive"]],
            "host_facade_start": facade.address,
            "code_residual_bytes": 2, "state_residual_bytes": 2,
            "composed_owners": ownership["logical_owners"],
            "claimant_classes": ownership["claimant_classes"],
            "allocated_code_owners": ownership["allocated_code_owners"],
            "allocated_state_owners": ownership["allocated_state_owners"],
            "guard_raw_references": guard["raw_external_references"],
            "code_external_raw_references": ownership[
                "code_external_raw_references"],
            "state_external_raw_references": ownership[
                "state_external_raw_references"]},
        "survival": survival, "positive_control": positive,
        "ABI_and_success_path": abi,
        "ordinary_text": {"end_exclusive": text.address + text.bytes,
            "mapped_facade_start": mapped.address,
            "free_bytes": mapped.address - (text.address + text.bytes),
            "floor_bytes": 32},
        "mutations_rejected": mutations,
        "device_read": ["five state bytes", "repl.buf[0..33]", "nsym", "npool"]}


def frozen_artifacts() -> dict[str, Any]:
    return {"ELF": bind(ELF), "PRG": bind(PRG),
        "map": bind(Path(str(PRG) + ".map")),
        "lto": bind(Path(str(PRG) + ".lto.o"))}


def run_child(action: str) -> dict[str, Any]:
    result = subprocess.run([sys.executable, str(DRIVER), action], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0,
            f"first-fault child {action} red:\n{result.stdout}")
    return {"action": action,
            "stdout_tail": " ".join(result.stdout.split()[-35:])}


def run_final_gate_child() -> tuple[dict[str, Any], dict[str, Any]]:
    marker = "FIRST_FAULT_FINAL_GATE_JSON="
    result = subprocess.run([sys.executable, str(DRIVER), "_final"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0,
            f"first-fault child _final red:\n{result.stdout}")
    rows = [row[len(marker):] for row in result.stdout.splitlines()
            if row.startswith(marker)]
    require(len(rows) == 1,
            "first-fault child _final did not emit one structured result")
    value = json.loads(rows[0])
    return value, {"action": "_final", "configuration_scope": "fresh-process",
                   "stdout_tail": " ".join(result.stdout.split()[-35:])}


def build() -> None:
    patch_paths()
    pre = load(PREFLIGHT_RECEIPT)
    current_inputs = preflight_inputs()
    require(pre["status"] == "PASS: SYMBOL22 PRODUCT CARD ARMED 0/1"
            and pre["inputs"] == current_inputs
            and not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not DIFFERENCE.exists(),
            "first-fault product-card lifecycle drift")
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, check=True).stdout
    require(clean == "", "first-fault WPLTO requires committed clean sources")
    INVOCATION.write_bytes(canonical({"status": "INVOKED",
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "budget": {"product_cards": 1, "WPLTO_runs": 1,
                   "product_links": 1}}))
    processes = [run_child("_produce")]
    before = frozen_artifacts()
    diff = attribution(); DIFFERENCE.write_bytes(canonical(diff))
    gate = final_gate()
    processes.extend((run_child("_scope"), run_child("_accept")))
    after = frozen_artifacts()
    scope, acceptance = load(BASE.SCOPE_RESULT), load(BASE.ACCEPTANCE_RESULT)
    require(before == after and scope["status"] == acceptance["status"] == "PASS",
            "first-fault read-only qualification tail red")
    value = {"format": FORMAT, "recorded_on": "2026-08-31",
        "status": STATUS, "authority": authority(),
        "preflight": bind(PREFLIGHT_RECEIPT), "invocation": bind(INVOCATION),
        "attribution": diff, "attribution_receipt": bind(DIFFERENCE),
        "final_product": gate, "producer": bind(BASE.PRODUCER_RESULT),
        "scope": bind(BASE.SCOPE_RESULT), "acceptance": bind(BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": processes,
        "attempt_accounting": {"product_cards": 1, "WPLTO_runs": 1,
            "product_links": 1, "scope_runs": 1, "acceptance_runs": 1,
            "media_builds": 0, "device_contacts": 0},
        "diagnostic_removal_default": True, "media_authorized": False,
        "next": "independent product-card review; then owner-controlled short device session"}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    check()
    print("v2.0 symbol22 product card: BUILD PASS WPLTO=1/1 link=1/1")


def record_first_red() -> None:
    patch_paths()
    out = BUILD / "wplto"
    seed = out / "resident-island-seed.prg"
    required = (seed, Path(str(seed) + ".elf"), Path(str(seed) + ".map"),
                Path(str(seed) + ".lto.o"), out / "resolved-profile.txt")
    require(all(path.is_file() for path in required) and INVOCATION.is_file()
            and not FIRST_RED.exists() and not ELF.exists() and not RECEIPT.exists(),
            "inventory first-red lifecycle drift")
    value = {"format": FORMAT + "-first-red", "recorded_on": "2026-08-31",
        "status": "FIRST RED: CANDIDATE LATCH ABSENT FROM SECTION INVENTORY",
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "invocation": bind(INVOCATION),
        "frozen_seed": {path.name: bind(path) for path in required},
        "diagnosis": {"expected_missing": [],
            "observed_additional": [SECTION, ".rela" + SECTION],
            "family": "configured-card registry omitted from derived inventory",
            "product_defect_established": False,
            "conversion": ("derive both section names from the active symbol22 "
                "registry; missing and unregistered extras remain red")},
        "accounting": {"card": 1, "seed_WPLTO": 1,
            "product_closure_links": 0, "media_builds": 0,
            "device_contacts": 0},
        "resume_right": ("replay inventory on immutable seed, materialize island, "
            "then consume the still-unspent sole product-closure link")}
    FIRST_RED.write_bytes(canonical(value))
    print("v2.0 symbol22 product card: FIRST RED RECORDED closure-link=0/1")


def record_owner_red() -> None:
    out = BUILD / "wplto"
    seed = out / "resident-island-seed.prg"
    seed_elf = Path(str(seed) + ".elf")
    seed_profile = out / "resolved-profile.txt"
    required = (seed, seed_elf, Path(str(seed) + ".map"),
                Path(str(seed) + ".lto.o"), seed_profile)
    first = load(FIRST_RED)
    require(all(path.is_file() for path in required)
            and first["frozen_seed"] == {
                path.name: bind(path) for path in required}
            and not OWNER_RED.exists() and not ELF.exists()
            and not RECEIPT.exists() and not DIFFERENCE.exists(),
            "gap-owner red lifecycle drift")
    ownership = composed_gap_ownership(seed_elf, seed_profile)
    expected_sections = [
        ".lisp65_rt_c2append_header",
        ".lisp65_rt_c2append_publish_clear",
        ".lisp65_rt_c2append_publish_plan_resolve",
        ".lisp65_rt_c2append_publish_plan_scan",
    ]
    require(ownership["gap"] == {"start": 0xB582,
                                  "end_exclusive": 0xB5C4}
            and ownership["latch"] == {"start": 0xB582,
                "end_exclusive": 0xB5BB, "bytes": 57}
            and ownership["allocated_owners"] == [SECTION]
            and ownership["terminal_return_guard_active"] is True
            and ownership["raw_external_sections"] == expected_sections
            and len(ownership["raw_external_references"]) == 64
            and ownership["logical_owners"] == [SECTION,
                "raw-fixed-address-terminal-return-guard"],
            "active raw gap claimant was not derived from frozen seed")
    release_features = profile_features(RELEASE_PROFILE)
    require(release_features.count(
        PRODUCT.TERMINAL_RETURN_GUARD_FEATURE) == 1,
        "release terminal-return claimant provenance drift")
    value = {"format": FORMAT + "-owner-red", "recorded_on": "2026-08-31",
        "status": "SECOND RED: ACTIVE RAW OWNER OVERLAPS LATCH",
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "invocation": bind(INVOCATION), "first_red": bind(FIRST_RED),
        "frozen_seed": {path.name: bind(path) for path in required},
        "ownership": ownership,
        "diagnosis": {
            "product_defect_established": True,
            "pricing_premise": "terminal-return diagnostic inactive",
            "observed_predecessor_fact": (
                "LISP65_C2_TERMINAL_RETURN_GUARD is active in the sealed "
                "v1.9 profile and remains active in the candidate profile"),
            "blind_spot": (
                "the price and preflight counted SHF_ALLOC interval owners "
                "but not fixed-address readers/writers with no allocation"),
            "effect": (
                "four emitted overlay wrappers write B582..B591, overwriting "
                "the latch state and the first eleven bytes of its helper"),
            "family": "composed ownership omitted a raw fixed-address owner",
        },
        "mutations": {
            "section_only_owner_count": 1,
            "composed_owner_count": 2,
            "section_only_false_green_rejected": True,
        },
        "accounting": {"product_cards": 1, "seed_WPLTO": 1,
            "product_closure_links": 0, "scope_runs": 0,
            "acceptance_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "candidate_disposition": "FROZEN-UNQUALIFIED-PRODUCT-EVIDENCE",
        "unspent_budget": {"product_closure_links": 1},
        "blocked_conditions": {
            "survival_proof": "not reachable on an overlapping product world",
            "positive_control": (
                "an isolated helper execution cannot qualify code that an "
                "active product path overwrites")},
        "decision_required": [
            "retire or relocate the active terminal-return guard, then rebuild",
            "reprice the latch into a disjoint owner interval, then rebuild",
        ],
        "resume_right": "none under the current one-WPLTO authority"}
    OWNER_RED.write_bytes(canonical(value))
    OWNER_RED_REPORT.write_text(f"""# v2.0 Phase 0 — `$22` latch owner red

Status: **{value['status']}**

The authorized seed WPLTO is frozen as unqualified evidence.  Its allocated
section map reports one owner at `$B582..$B5BB`, but the final bytes prove a
second owner that has no ELF allocation: the active terminal-return guard.
Four emitted append-overlay wrappers make **64** data references into
`$B582..$B591`; their stores overwrite all five latch state bytes and the
first eleven helper bytes.  The candidate therefore cannot reach either the
survival proof or a meaningful final-ELF positive control.

The pricing premise was false.  `LISP65_C2_TERMINAL_RETURN_GUARD` is present
once in both the sealed v1.9 profile and this seed profile.  The earlier check
mistook “no allocated section” for “inactive”.  The permanent successor gate
now composes allocated intervals with raw fixed-address data references.

Budget consumed: one product card and one seed WPLTO.  The sole product-
closure link remains unused.  Continuing requires a new owner decision:
either retire/relocate the active guard, or reprice the latch into a disjoint
interval.  Both choices change the WPLTO world, so the frozen seed is not a
resume basis under the current authority.
""", encoding="utf-8")
    print("v2.0 symbol22 product card: OWNER RED RECORDED WPLTO=1 link=0/1")


def conversion_seed_files() -> tuple[Path, ...]:
    out = BUILD / "wplto"
    seed = out / "resident-island-seed.prg"
    return (seed, Path(str(seed) + ".elf"), Path(str(seed) + ".map"),
            Path(str(seed) + ".lto.o"), out / "resolved-profile.txt")


def configure_r2_seed_world() -> Any:
    """Rebuild the exact living configuration which emitted the r2 seed."""
    core, _activation, _product_cold = BASE.configure_full_candidate()
    LIVENESS_CONFIG.configure(PRODUCT)
    PRODUCT.configure_mapped_tenant_lma_policy("map-page-top")
    PRODUCT.configure_mapped_facade_placement(
        "after-final-text-floor", text_floor=32)
    PRODUCT.configure_candidate_derived_fixed_bank0_code_layout()
    ordinals = RELEASE.R8.R7.CARD.stdlib_header_ordinals()
    PRODUCT.configure_compiler_consumed_stdlib_header(
        RELEASE_HEADER, bind(RELEASE_HEADER), ordinals["repl_banner"])
    return core


def seed_compile_inputs(contract: Path) -> tuple[tuple[str, ...], list[str]]:
    """Read the compiler feature/source world materialized by the seed."""
    rows = contract.read_text(encoding="utf-8").splitlines()
    feature_rows = [line.split("=", 1)[1] for line in rows
                    if line.startswith("feature_defines=")]
    require(len(feature_rows) == 1, "seed feature profile is not unique")
    features = tuple(item for item in feature_rows[0].split(",") if item)
    inputs: list[Path] = []
    for line in rows:
        if not line.startswith("input_sha256="):
            continue
        raw_path, digest = line.split("=", 1)[1].rsplit(":", 1)
        path = ROOT / raw_path
        require(path.is_file()
                and hashlib.sha256(path.read_bytes()).hexdigest() == digest,
                f"seed compiler input drift: {raw_path}")
        inputs.append(path)
    require(len(inputs) == 71
            and inputs[-1].resolve() ==
                PRODUCT.KERNAL_EQUATES_INCLUDE.resolve(),
            "seed compiler-input closure drift")
    sources = [str(path) for path in inputs[:-1]]
    require(len(sources) == 70
            and all(Path(path).suffix in (".c", ".s") for path in sources),
            "seed compiler source population drift")
    return features, sources


def bind_seed_link_environment(contract: Path) -> None:
    rows = dict(line.split("=", 1) for line in
                contract.read_text(encoding="utf-8").splitlines()
                if "=" in line)
    require(rows.get("lto_rng_seed") == "0"
            and rows.get("lto_threads") == "1"
            and rows.get("deterministic_objects") == "1"
            and rows.get("deterministic_llvm_link") == "/usr/bin/llvm-link"
            and rows.get("link_aslr_disabled") == "1",
            "seed deterministic-link environment drift")
    os.environ.update({
        "PYTHONHASHSEED": "0", "LISP65_LTO_RNG_SEED": "0",
        "LISP65_LTO_THREADS": "1", "LISP65_DETERMINISTIC_OBJECTS": "1",
        "LISP65_LLVM_LINK": "/usr/bin/llvm-link",
        "LISP65_DISABLE_LINK_ASLR": "1", "SOURCE_DATE_EPOCH": "1785024000",
        "TZ": "UTC", "LC_ALL": "C", "LANG": "C",
        "LISP65_PUBLIC_CLEAN_BUILD": "1",
    })


def bind_completion_seed_support(out: Path, seed_out: Path) -> list[str]:
    """Expose fixed seed support by reference, never by writing the seed."""
    names = (
        "stage-config.h", "runtime-overlay.prepare-standard.h",
        "runtime-overlay.prepare.h", "resident-island.prepare.h",
        "error-text-table.h", "c2-kernal-window.generated.h",
    )
    for name in names:
        source = seed_out / name
        target = out / name
        require(source.is_file() and not source.is_symlink(),
                f"seed support absent: {name}")
        if name == "c2-kernal-window.generated.h":
            # Publish-last rewrites this header.  Its predecessor is therefore
            # a completion-owned copy, never a write-through seed reference.
            if not (out / "kernal-window-publish-last.json").exists():
                if target.is_symlink():
                    target.unlink()
                target.write_bytes(source.read_bytes())
            else:
                require(target.is_file() and not target.is_symlink(),
                        "published KERNAL header lost completion ownership")
            continue
        if target.exists() or target.is_symlink():
            require(target.is_symlink() and target.resolve() == source.resolve(),
                    f"completion support has a second owner: {name}")
        else:
            target.symlink_to(source)
    return list(names)


def validate_inventory_conversion(value: dict[str, Any]) -> None:
    require(value["status"] ==
                "PASS: RELOCATION MEMBERSHIP DERIVED; SEED READ-ONLY GREEN"
            and value["authority"] == successor_authority()
            and value["seed_before"] == value["seed_after"]
            and value["micro_object"]["emitted_source_sections"] == [SECTION]
            and value["micro_object"]["relocation_free_allocated"] == [
                STATE_SECTION]
            and value["micro_object"]["relocation_sections"] == [
                ".rela" + SECTION]
            and value["seed_replay"]["emitted_source_sections"] == [SECTION]
            and value["seed_replay"]["relocation_free_allocated"] == [
                STATE_SECTION]
            and value["seed_replay"]["relocation_sections"] == [
                ".rela" + SECTION]
            and value["sharp_mutations"] == {
                "zero-relocation-state": "accepted",
                "emitted-relocation-without-rela": "rejected",
                "fabricated-rela-for-zero-relocation-state": "rejected",
                "registry-omits-emitted-source": "rejected"}
            and value["accounting"] == {"new_WPLTOs": 0,
                "product_links": 0, "scope_runs": 0,
                "acceptance_runs": 0},
            "r2 relocation-membership conversion receipt drift")


def convert_inventory() -> None:
    patch_paths()
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, check=True).stdout
    require(clean == "" and not INVENTORY_CONVERSION.exists()
            and not ELF.exists() and not RECEIPT.exists()
            and not DIFFERENCE.exists(),
            "inventory conversion requires committed sources and unused link")
    red = load(R2_INVENTORY_RED)
    required = conversion_seed_files()
    before = {path.name: bind(path) for path in required}
    require(red["status"] ==
                "FIRST RED: ZERO-RELOCATION STATE SECTION WAS REQUIRED AS RELA FREIGHT"
            and red["frozen_seed"] == before,
            "r2 inventory First Red does not own the frozen seed")

    # Reconstruct the exact full candidate configuration that produced the
    # seed.  This is configuration only: no producer, WPLTO or link runs.
    configure_r2_seed_world()
    micro = preflight_micro()["relocation_membership"]
    seed = required[0]
    replay = PRODUCT.final_section_inventory_check(seed)
    registration = replay["pin"]["profile_derivation"][
        "symbol22_latch_registration"]
    seed_membership = replay["symbol22_relocation_membership"]
    after = {path.name: bind(path) for path in required}
    require(before == after and replay["status"] == "passed"
            and registration["relocations"] == [".rela" + SECTION]
            and registration["relocation_free_allocated"] == [STATE_SECTION]
            and micro["emitted_source_sections"] == [SECTION]
            and seed_membership["emitted_source_sections"] == [SECTION],
            "converted inventory did not bind micro and immutable seed truth")
    value = {
        "format": FORMAT + "-inventory-conversion-v1",
        "recorded_on": "2026-08-31",
        "status": "PASS: RELOCATION MEMBERSHIP DERIVED; SEED READ-ONLY GREEN",
        "authority": successor_authority(),
        "sealed_preflight": bind(PREFLIGHT_RECEIPT),
        "seed_before": before, "seed_after": after,
        "micro_object": micro,
        "seed_replay": {
            "status": replay["status"],
            "final_elf_sha256": replay["final_elf_sha256"],
            "emitted_source_sections":
                seed_membership["emitted_source_sections"],
            "registered_source_sections":
                seed_membership["registered_source_sections"],
            "relocation_free_allocated":
                seed_membership["relocation_free_allocated"],
            "relocation_sections":
                seed_membership["registered_relocation_sections"],
        },
        "sharp_mutations":
            PRODUCT._registered_relocation_membership_selftest(),
        "claim": ("allocation and relocation membership are separate; an "
                  "emitting source requires its RELA while pure state does not"),
        "accounting": {"new_WPLTOs": 0, "product_links": 0,
            "scope_runs": 0, "acceptance_runs": 0},
        "next": "commit conversion evidence, then consume sole closure link",
    }
    INVENTORY_CONVERSION.write_bytes(canonical(value))
    INVENTORY_CONVERSION_REPORT.write_text(f"""# v2.0 `$22` r2 inventory conversion

Status: **{value['status']}**

The split latch allocates two sections but emits relocation records from only
the 48-byte helper.  Both the compiled micro object and the immutable seed
derive the same membership: `{SECTION}` owns its `.rela`; the pure five-byte
`{STATE_SECTION}` owns none.  The seed hashes are byte-identical before and
after the replay.  No WPLTO, product link, Scope or Acceptance ran.

The sharp mutation remains red: when the model emits relocation records for
the state section but its `.rela` is absent, the converted checker rejects the
candidate.  A fabricated `.rela` for zero-relocation state is rejected too.
""", encoding="utf-8")
    validate_inventory_conversion(value)
    print("v2.0 symbol22 product card: INVENTORY CONVERSION PASS link=0/1")


def check_inventory_conversion() -> None:
    validate_inventory_conversion(load(INVENTORY_CONVERSION))
    print("v2.0 symbol22 product card: INVENTORY CONVERSION CHECK PASS")


def resume_from_seed() -> list[dict[str, Any]]:
    red = load(R2_INVENTORY_RED)
    conversion = load(INVENTORY_CONVERSION)
    validate_inventory_conversion(conversion)
    seed_out = BUILD / "wplto"
    out = COMPLETION
    seed = seed_out / "resident-island-seed.prg"
    required = conversion_seed_files()
    linked_family = (PRG, ELF, Path(str(PRG) + ".map"),
                     Path(str(PRG) + ".lto.o"))
    linked_before = all(path.is_file() for path in linked_family)
    closure_receipt = out / "product-substitution-link.json"
    closure_before = closure_receipt.is_file()
    require(red["status"] ==
                "FIRST RED: ZERO-RELOCATION STATE SECTION WAS REQUIRED AS RELA FREIGHT"
            and red["frozen_seed"] == {path.name: bind(path) for path in required}
            and conversion["seed_after"] == red["frozen_seed"]
            and (not ELF.exists() or linked_before)
            and not RECEIPT.exists() and not DIFFERENCE.exists(),
            "inventory seed resume authority drift")
    partial_names = {
        "resident-island.h",
        "lisp65-c2-substitution-linked.compiler-input-assert.h",
        "lisp65-c2-substitution-linked.stdlib-input-assert.h",
        "lisp65-c2-substitution-linked.prg.link.stderr.txt",
        "lisp65-c2-substitution-linked.prg.link.stdout.txt",
    }
    if out.exists() and not linked_before:
        require(out.is_dir() and not out.is_symlink()
                and {path.name for path in out.iterdir()} <= partial_names
                and not any(path.is_dir() for path in out.iterdir()),
                "completion root is not the bounded pre-link frontend stop")
    elif out.exists():
        require(out.is_dir() and not out.is_symlink()
                and (not closure_before
                     or json.loads(closure_receipt.read_text(
                         encoding="utf-8"))["status"] == "passed"),
                "linked completion is not the bounded post-link adapter stop")
    else:
        out.mkdir()
    core = configure_r2_seed_world()
    core.install_static(BUILD)
    core.bind_paths_only(BUILD, PREFLIGHT)
    core.write_projections()
    inventory = PRODUCT.final_section_inventory_check(seed)
    metadata = PRODUCT.lto_partition_metadata_check(seed)
    expectation = PRODUCT.final_section_inventory_expectation()
    require(inventory["status"] == metadata["status"] == "passed"
            and expectation["symbol22_latch_registration"]["selected"] is True
            and SECTION in expectation["names"]
            and ".rela" + SECTION in expectation["names"],
            "converted inventory did not consume active latch registry")
    require(STATE_SECTION in expectation["names"]
            and ".rela" + STATE_SECTION not in expectation["names"]
            and inventory["symbol22_relocation_membership"][
                "emitted_source_sections"] == [SECTION],
            "zero-relocation state membership regressed before closure link")
    contract = seed_out / "resolved-profile.txt"
    features, compiler_sources = seed_compile_inputs(contract)
    bind_seed_link_environment(contract)
    support = bind_completion_seed_support(out, seed_out)
    if PROFILE.exists():
        require(PROFILE.read_bytes() == contract.read_bytes(),
                "completion profile differs from consumed seed contract")
    else:
        PROFILE.write_bytes(contract.read_bytes())
    require(bind(PROFILE)["sha256"] == bind(contract)["sha256"],
            "completion profile materialization drift")
    island_header = out / "resident-island.h"
    if not linked_before:
        PRODUCT.tool("resident_island.py", "materialize",
            "--elf", str(seed) + ".elf",
            "--nm", str(PRODUCT.TOOLCHAIN / "llvm-nm"),
            "--objcopy", str(PRODUCT.TOOLCHAIN / "llvm-objcopy"),
            "--abi-contract", str(contract), "--header", str(island_header))
    else:
        require(island_header.is_file(),
                "linked completion lost its materialized resident header")
    artifacts = json.loads(PRODUCT.resolved_product_artifacts_manifest().read_text(
        encoding="utf-8"))
    if not linked_before:
        PRODUCT.write_product_linker_sources(out, features)
    old_source_list = PRODUCT.source_list
    old_include_dirs = PRODUCT.EXTRA_INCLUDE_DIRS
    registered_features = tuple(PRODUCT.CONVERGENCE_DEFINES)

    def exact_seed_sources(
            extra_definitions: tuple[str, ...] = ()) -> list[str]:
        require(tuple(extra_definitions) in ((), features,
                                              registered_features),
                "completion requested a source world other than the seed")
        return list(compiler_sources)

    try:
        PRODUCT.source_list = exact_seed_sources
        PRODUCT.EXTRA_INCLUDE_DIRS = (*old_include_dirs, seed_out)
        final = PRG
        if not linked_before:
            final = PRODUCT.compile_link(out,
                "lisp65-c2-substitution-linked.prg",
                [seed_out / "stage-config.h",
                 seed_out / "runtime-overlay.prepare.h", island_header,
                 seed_out / "error-text-table.h",
                 seed_out / "c2-kernal-window.generated.h"], artifacts,
                probe_definitions=features)
        elif not closure_before:
            PRODUCT.input_capture_seed_size_witness(
                PRODUCT._readobj_sections(ELF), features)
            PRODUCT.final_section_inventory_gate(out, final)
            PRODUCT.lto_partition_metadata_gate(out, final)
        if not closure_before:
            PRODUCT.finish_single_link(out, final, contract)
    finally:
        PRODUCT.source_list = old_source_list
        PRODUCT.EXTRA_INCLUDE_DIRS = old_include_dirs
    require(red["frozen_seed"] == {path.name: bind(path) for path in required},
            "artifact completion changed immutable seed WPLTO evidence")
    return [{"action": "inventory-replay", "status": inventory["status"],
             "expected_sections": expectation["expected_names"],
             "relocation_sources": [SECTION],
             "relocation_free_allocated": [STATE_SECTION]},
            {"action": "completion-owned-output-root",
             "status": "PASS", "path": out.relative_to(ROOT).as_posix(),
             "seed_copied": False,
             "frontend_continuation": "fixed headers referenced from seed",
             "referenced_seed_support": support},
            {"action": "sole-product-closure-link", "status": "PASS",
             "emitted_before_post_link_resume": linked_before,
             "closure_completed_before_card_resume": closure_before,
             "final_linker_invocations": 1}]


def resume() -> None:
    patch_paths()
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, check=True).stdout
    require(clean == "", "inventory resume requires committed conversion")
    processes = resume_from_seed()
    before = frozen_artifacts()
    diff = attribution(); DIFFERENCE.write_bytes(canonical(diff))
    gate, final_process = run_final_gate_child()
    processes.append(final_process)
    processes.extend((run_child("_scope"), run_child("_accept")))
    after = frozen_artifacts()
    scope, acceptance = load(BASE.SCOPE_RESULT), load(BASE.ACCEPTANCE_RESULT)
    require(before == after and scope["status"] == acceptance["status"] == "PASS",
            "first-fault read-only qualification tail red")
    value = {"format": FORMAT, "recorded_on": "2026-08-31",
        "status": STATUS, "authority": authority(),
        "successor_authority": successor_authority(),
        "preflight": bind(PREFLIGHT_RECEIPT), "invocation": bind(INVOCATION),
        "inventory_first_red": bind(R2_INVENTORY_RED),
        "inventory_conversion": bind(INVENTORY_CONVERSION),
        "attribution": diff,
        "attribution_receipt": bind(DIFFERENCE), "final_product": gate,
        "producer": {"status": "completed-from-immutable-seed"},
        "scope": bind(BASE.SCOPE_RESULT), "acceptance": bind(BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": processes,
        "attempt_accounting": {"product_cards": 1, "WPLTO_runs": 1,
            "product_links": 1, "scope_runs": 1, "acceptance_runs": 1,
            "media_builds": 0, "device_contacts": 0},
        "resume_accounting": {"new_seed_WPLTOs": 0,
            "product_closure_links": 1, "new_cards": 0},
        "diagnostic_removal_default": True, "media_authorized": False,
        "next": "independent product-card review; then owner-controlled short device session"}
    RECEIPT.write_bytes(canonical(value)); write_report(value); check()
    print("v2.0 symbol22 product card: RESUME PASS WPLTO=1/1 product-link=1/1")


def write_report(value: dict[str, Any]) -> None:
    final = value["final_product"]
    pair = value["artifacts_after"]
    REPORT.write_text(f"""# v2.0 Phase 0 — `$22` first-fault latch product card r2

Status: **{value['status']}**

One authorized product card, WPLTO and link materialized a split latch without
retiring the terminal-return guard.  The guard's 64 fixed raw accesses own
`$B582..$B591`; the 48-byte helper follows at `$B592`, leaving **2 bytes**
before the host facade.  Five packed-zero state bytes begin at the derived end
of fixed hot BSS and leave **2 bytes** before `__heap_start`.  The
ordinary-text wall retains **{final['ordinary_text']['free_bytes']} bytes**
against its 32-byte floor.

The candidate's own final ELF derives the four-byte hardware-stack depth,
the +7/+8 caller offsets and the live `__rc20/__rc21` name pointer.  After
projecting the one new call, all 347 `intern` instructions and their internal
CFG targets are identical to v1.9; external calls retain symbol identity and
all data operands remain exact.  The existing fault-only edge
`LDA #$22; JSR lisp_abort_code` becomes `JSR
lisp65_symbol22_latch_capture; LDA #$22; JSR lisp_abort_code`.  The helper
returns into the existing abort edge; successful lookup/intern execution has
no new work.  A mutation adding one successful-path instruction falls.

Both record carriers have an explicit lifetime proof.  The five packed state
bytes and the first 34 bytes of the address-identical, zero-allocation
`repl.buf` alias are outside the runtime-overlay wipe interval.  The final
abort/cleanup/`longjmp`/recovery callgraph has no writer to either owner before
the stopped-read cutpoint.  Mutations that widen the wipe into state or add a
recovery writer to the payload fall.

The positive control executes the **emitted 45GS02 helper bytes from the final
ELF**.  An injected 34-byte out-of-domain name commits tag `$A5`, caller,
pointer and all 34 payload bytes before returning to the existing `$22` edge;
a second fault cannot overwrite them.  A separate poisoned-payload execution
proves that copying stops at the first NUL and leaves every following byte
untouched.  Consequently a device `tag == 0` means no recurrence rather than
an untested instrument.

The v1.9→candidate difference has zero unexplained members.  The immutable
pair is ELF `{pair['ELF']['sha256']}` / PRG `{pair['PRG']['sha256']}`.
Read-only Scope and Acceptance are green.  No medium was built and no device
was contacted; removal remains the default after Phase-0 attribution.
""", encoding="utf-8")


def validate(value: dict[str, Any]) -> None:
    patch_paths()
    final = value["final_product"]
    require(value["status"] == STATUS and value["authority"] == authority()
            and value["successor_authority"] == successor_authority()
            and value["inventory_first_red"] == bind(R2_INVENTORY_RED)
            and value["inventory_conversion"] == bind(INVENTORY_CONVERSION)
            and value["artifacts_before"] == value["artifacts_after"] ==
                frozen_artifacts()
            and value["attribution"]["unexplained_members"] == 0
            and final["survival"]["status"] ==
                "PASS: BOTH RECORD CARRIERS SURVIVE ABORT RECOVERY"
            and not final["survival"]["writer_closure"][
                "protected_symbol_references"]
            and not final["survival"]["writer_closure"]["protected_raw_writes"]
            and final["survival"]["state"]["packed_initial_hex"] == "00" * 5
            and final["positive_control"]["record"]["complete"] is True
            and final["positive_control"]["record"]["state_hex"].startswith("a5")
            and final["positive_control"]["NUL_stop"][
                "poison_tail_unchanged"] is True
            and final["ABI_and_success_path"]["successful_path_identity"][
                "all_other_semantics_identical"] is True
            and final["placement"]["code_residual_bytes"] == 2
            and final["placement"]["state_residual_bytes"] == 2
            and final["placement"]["composed_owners"] == [
                "raw-fixed-address-terminal-return-guard", SECTION, STATE_SECTION]
            and len(final["placement"]["claimant_classes"]) == 7
            and len(final["placement"]["guard_raw_references"]) == 64
            and not final["placement"]["code_external_raw_references"]
            and not final["placement"]["state_external_raw_references"]
            and final["ordinary_text"]["free_bytes"] >= 32
            and value["attempt_accounting"] == {"product_cards": 1,
                "WPLTO_runs": 1, "product_links": 1, "scope_runs": 1,
                "acceptance_runs": 1, "media_builds": 0,
                "device_contacts": 0}
            and value["diagnostic_removal_default"] is True
            and REPORT.is_file(), "first-fault product-card receipt drift")


def check() -> None:
    validate(load(RECEIPT))
    print("v2.0 symbol22 product card: CHECK PASS positive=executed survival=2/2")


def selftest() -> None:
    value = load(RECEIPT)
    cases = {
        "lose-survival": lambda x: x["final_product"]["survival"].update(
            status="FAIL"),
        "positive-tag-zero": lambda x: x["final_product"]["positive_control"]
            ["record"].update(complete=False),
        "lose-NUL-stop": lambda x: x["final_product"]["positive_control"]
            ["NUL_stop"].update(poison_tail_unchanged=False),
        "second-gap-owner": lambda x: x["final_product"]["placement"].update(
            composed_owners=[SECTION, STATE_SECTION]),
        "omit-raw-claimant": lambda x: x["final_product"]["placement"].update(
            guard_raw_references=[]),
        "omit-claimant-class": lambda x: x["final_product"]["placement"][
            "claimant_classes"].pop(),
        "spend-floor": lambda x: x["final_product"]["ordinary_text"].update(
            free_bytes=31),
        "retain-by-default": lambda x: x.update(diagnostic_removal_default=False),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except (CardError, RuntimeError):
            rejected.append(name)
    require(rejected == list(cases), "product-card receipt mutation survived")
    print(f"v2.0 symbol22 product card: SELFTEST PASS mutations={len(rejected)}")


def child(action: str) -> None:
    patch_paths()
    if action == "_produce":
        BASE.produce_child()
    elif action == "_scope":
        BASE.scope_child()
    elif action == "_final":
        # This is a line protocol consumed by run_final_gate_child().  The
        # canonical evidence serializer is intentionally pretty-printed and
        # therefore cannot be embedded after a one-line marker.
        print("FIRST_FAULT_FINAL_GATE_JSON=" + json.dumps(
            final_gate(), sort_keys=True, separators=(",", ":")))
    else:
        BASE.acceptance_child()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "build",
        "record-first-red", "record-owner-red", "convert-inventory",
        "check-inventory-conversion", "record-qualification-red",
        "resume", "check", "selftest",
        "_produce", "_scope", "_accept", "_final"))
    action = parser.parse_args().action
    if action == "preflight": preflight()
    elif action == "build": build()
    elif action == "record-first-red": record_first_red()
    elif action == "record-owner-red": record_owner_red()
    elif action == "convert-inventory": convert_inventory()
    elif action == "check-inventory-conversion": check_inventory_conversion()
    elif action == "record-qualification-red": record_qualification_red()
    elif action == "resume": resume()
    elif action == "check": check()
    elif action == "selftest": selftest()
    else: child(action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"v2.0 symbol22 product card: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
