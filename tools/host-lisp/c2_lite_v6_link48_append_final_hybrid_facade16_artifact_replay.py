#!/usr/bin/env python3
"""Pure completion replay of the facade-16 WPLTO artifacts.

The only product-shaped WPLTO completed and then stopped in an inherited
co-resident semantic gate.  That gate expected the pre-consolidation
publish_exports section and the historical 115-byte floor.  This replay asks
the immutable ELF about the authorized publish_clear section and 54-byte
floor, then runs the remaining read-only structural gates.  Compiler, linker,
product-link and hardware execution are forbidden here.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_append_phase_plan_gate as APPEND  # noqa: E402
import c2_asm_leaf_abi_gate as ABI  # noqa: E402
import c2_lite_root_surrogate as ROOT_GATE  # noqa: E402
import c2_lite_v6_link48_append_final_hybrid_wplto as HYBRID  # noqa: E402
import c2_numeric_early_errors_gate as NUMERIC  # noqa: E402
import c2_zero_literal_execution_gate as ZERO  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


P = HYBRID.P
CONS = HYBRID.BASE
FINAL = CONS.FINAL
BASE_LINK = FINAL.BASE_LINK
STAGE = BASE_LINK.STAGE
ART = BASE_LINK.ART
LINK44 = CONS.PROBE.BASE.LINK44
TRANSIENT = CONS.PROBE.BASE.TRANSIENT
ORDINAL = CONS.PROBE.BASE.ORDINAL
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SOURCE = ROOT / (
    "build/c2.2/substitution/link48-append-final-hybrid-facade16-wplto2")
PRODUCT = SOURCE / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
FIRST_RED = EVIDENCE / (
    "c2.2-link48-append-final-hybrid-facade16-wplto2-internal.json")
FIRST_RED_SHA = (
    "018b21e3340fb1ad91d4f6b5932c5ed80edc69f9bd7b7bebe017527d54dbae59")
PROVENANCE_FIRST_RED = EVIDENCE / (
    "c2.2-link48-append-final-hybrid-facade16-"
    "artifact-replay-provenance-first-red.json")
COMPILER_FIRST_RED = EVIDENCE / (
    "c2.2-link48-append-final-hybrid-facade16-"
    "artifact-replay2-host-compiler-first-red.json")
ROOT_SURROGATE_AUTHORITY = EVIDENCE / (
    "c2.2-product-link48-c2-lite-v6-zero-literal-execution-"
    "structural-receipt.json")
ROOT_SURROGATE_AUTHORITY_SHA = (
    "867bd59ff9c669e98b4969062eeb0dfd39b0fb633f21dd3e19f067fedb3c7f25")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link48-append-final-hybrid-facade16-artifact-replay")
RECEIPT = EVIDENCE / (
    "c2.2-link48-append-final-hybrid-facade16-"
    "artifact-replay-receipt.json")
VERIFIER_BASE = 0xB949


class ReplayError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplayError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"replay evidence absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def snapshot(root: Path) -> dict[str, dict[str, Any]]:
    return {path.relative_to(root).as_posix(): {
                "bytes": path.stat().st_size,
                "mode": oct(path.stat().st_mode & 0o777),
                "sha256": sha(path)}
            for path in sorted(root.rglob("*")) if path.is_file()}


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def configure_profile() -> None:
    for module in (BASE_LINK, STAGE, ART):
        module.VERIFIER_BASE = VERIFIER_BASE
    BASE_LINK.configure_profile()
    CONS.RF.configure_roots_fronts()
    CONS.CONS.configure_publish_clear()
    P.configure_c2_lite_hybrid_e000_geometry()
    P.configure_append_plan_facade()
    require(P.E000_FINAL_FLOOR_BYTES == 54
            and P.host_facade_bytes() == 48
            and P.host_facade_vector_addresses()[
                "c2_facade_append_plan_walk"] == 0xB5F1
            and P.VERIFIER_BINDING_BASE == VERIFIER_BASE,
            "pure replay profile differs from the linked facade-16 profile")


def generic_gate_evidence() -> dict[str, Any]:
    structure = json.loads((SOURCE / "product-substitution-link.json").read_text())
    names = (
        "identity_gate", "capacity_gate", "one_truth_gate",
        "kernal_freedom_gate", "fixed_host_facade_gate",
        "pre_ownership_gate", "handoff_z_abi_gate",
        "direct_entry_encoding_gate", "assembler_leaf_abi_gate")
    require(structure["status"] == "passed"
            and structure["product_closure_link_count"] == 1
            and all("pass" in str(structure[name]) for name in names),
            "frozen generic facade-16 WPLTO gate set is not green")
    leaves = {
        "facade": "fixed-host-facade-final.json",
        "pre_ownership": "pre-ownership-closure-final.json",
        "profile_data": "profile-data-reference-final.json",
        "kernal_freedom": "kernal-freedom-link.json",
        "handoff": "handoff-z-abi-final.json",
        "inventory": "final-section-inventory-lisp65-c2-substitution-linked.prg.json",
        "family_identity": "runtime-family-total-identity.json",
        "publish_last": "total-publish-last-domain.json",
    }
    bound: dict[str, Any] = {}
    for name, leaf in leaves.items():
        path = SOURCE / leaf
        value = json.loads(path.read_text())
        require(value["status"] == "passed", f"frozen gate red: {name}")
        bound[name] = bind(path)
    facade = json.loads((SOURCE / leaves["facade"]).read_text())
    vectors = facade["vector_contract"]
    publish = json.loads((SOURCE / leaves["publish_last"]).read_text())
    require(vectors["base"] == 0xB5C4 and vectors["bytes"] == 48
            and len(vectors["symbols"]) == 16
            and vectors["symbols"]["c2_facade_append_plan_walk"] == 0xB5F1
            and facade["window_direct_low_edges_outside_facade"] == []
            and publish["declared_domain_bytes"] == 42,
            "frozen facade or publish-last truth drift")
    return {"status": "passed-frozen-generic-gate-set",
            "structure": {name: structure[name] for name in names},
            "gate_artifacts": bound,
            "facade_vector_count": len(vectors["symbols"]),
            "publish_last_bytes": publish["declared_domain_bytes"]}


def bound_root_surrogate_gate() -> dict[str, Any]:
    """Consume the immutable complete-domain proof without recompiling it.

    The permanent gate's host helper depends only on its exact helper source
    and ``src/obj.h``.  A pure artifact replay must not invoke that compiler
    again, so bind a prior complete-domain result and reject it unless both
    inputs remain byte-identical.
    """
    require(ROOT_SURROGATE_AUTHORITY.is_file()
            and sha(ROOT_SURROGATE_AUTHORITY) == ROOT_SURROGATE_AUTHORITY_SHA,
            "root-surrogate authority receipt drift")
    authority = json.loads(ROOT_SURROGATE_AUTHORITY.read_text())
    root = authority["fresh_prelink_gates"][
        "root_surrogate_complete_domain"]
    source = root["source_truth"]
    helper_sha = hashlib.sha256(
        ROOT_GATE.helper_source().encode()).hexdigest()
    require(root["format"] == "lisp65-c2d-v6-root-surrogate-gate-v1"
            and root["status"] == "pass"
            and source["obj_h_sha256"] == sha(ROOT_GATE.OBJ_H)
            and source["helper_source_sha256"] == helper_sha
            and source["emitted_rows"] == 57344
            and root["root_surrogates"]["count"] == 1536
            and all(value == 0 for value in
                    root["collision_intersections"].values()),
            "bound root-surrogate proof no longer matches its source truth")
    return {
        "status": "passed-bound-complete-domain-proof-with-identical-inputs",
        "proof": root,
        "authority_receipt": bind(ROOT_SURROGATE_AUTHORITY),
        "current_inputs": {
            "obj_h_sha256": source["obj_h_sha256"],
            "helper_source_sha256": helper_sha},
        "compiler_runs_in_replay": 0,
    }


def workbench_crc_gate() -> dict[str, Any]:
    payload = BASE_LINK.ABI_WPLTO.payload(PRODUCT, ELF)
    expected = BASE_LINK.CRC.crc_reference(payload)
    truth = ElfTruth.read(ELF, llvm_readobj=P.TOOLCHAIN / "llvm-readobj")
    descriptor = BASE_LINK.HW.boot_overlay_descriptor(
        build_id=int(sha(SOURCE / "resolved-profile.txt")[:8], 16),
        start=truth.symbol("__lisp65_workbench_overlay_start").value,
        entry=truth.symbol("vm_workbench_boot_overlay_entry").value,
        payload=payload)
    require(struct.unpack_from("<H", descriptor, 16)[0] == expected,
            "frozen Workbench descriptor CRC drift")
    prior = dict(BASE_LINK.CRC.VECTORS)
    BASE_LINK.CRC.VECTORS["actual-workbench-overlay"] = payload
    try:
        report = BASE_LINK.CRC.audit_elf(
            ELF, out=OUT / "c2-crc-asm-leaf-workbench-gate.json")
    finally:
        BASE_LINK.CRC.VECTORS.clear()
        BASE_LINK.CRC.VECTORS.update(prior)
    witness = report["vectors"]["actual-workbench-overlay"]
    require(witness["bytes"] == len(payload)
            and witness["crc16"] == expected,
            "frozen Workbench/CRC-Leaf parity drift")
    return {"status": "passed-linked-leaf-current-workbench",
            "payload_bytes": len(payload), "payload_crc16": expected,
            "gate": bind(OUT / "c2-crc-asm-leaf-workbench-gate.json")}


def read_only_replay() -> dict[str, Any]:
    walls, family = BASE_LINK.walls_and_family(ELF)
    shape = {"walls": walls,
             "runtime_slices": family["runtime_slices"],
             "successor_bank3_pack": family["successor_bank3_pack"]}
    capacity = CONS.capacity_gate(shape, ELF)
    semantics = BASE_LINK.DIET.semantic_product_gate(shape, PRODUCT, ELF)
    roots_fronts = CONS.roots_fronts_gate(ELF)
    no_attic = BASE_LINK.LINK.no_runtime_attic_gate(
        ELF, SOURCE / "generated-product-sources")
    stage = ART.stage_product_gate(ELF)
    overlay = BASE_LINK.LINK.BASE.LINK33_BASE.final_overlay_closure(ELF)
    preinstall = BASE_LINK.LINK.BASE.ISLAND.static_elf_gate(ELF)
    root = bound_root_surrogate_gate()
    family_seam = FINAL.FAMILY.closure_gate(PRODUCT, ELF)
    identity = FINAL.IDENTITY.audit(
        ELF, SOURCE / "runtime-overlays-boot-final.bin",
        SOURCE / "runtime-overlays-boot-final.json",
        SOURCE / "generated-product-sources/vm_runtime_overlay.c",
        OUT / "final-island-single-runtime-identity.json")
    ordinal = ORDINAL.linked_gate(ELF)
    abi_mutations = ABI.selftest()
    abi = ABI.audit_elf(ELF, out=OUT / "assembler-leaf-abi.json")
    generated = SOURCE / "generated-product-sources"
    transient = {
        "source": TRANSIENT.source_gate(
            generated_runtime=generated / "c2_product_runtime.c",
            generated_hot=generated / "c2_hot_literal.c"),
        "linked": TRANSIENT.linked_gate(ELF),
    }
    c2d = SOURCE / "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin"
    zero = {"source": ZERO.source_gate(
                generated_runtime=generated / "c2_product_runtime.c"),
            "linked": ZERO.linked_gate(ELF, c2d)}
    append = {"source": APPEND.source_gate(),
              "linked": APPEND.linked_gate(ELF)}
    numeric = NUMERIC.linked_gate(ELF)
    bank2 = LINK44.B.elf_gate(
        {"artifacts": {"measurement_elf": bind(ELF)}})
    workbench_scratch = LINK44.B.target_fixture(
        LINK44.REPLAY.fixture_product())
    require(walls == {
                "bank0_text_headroom_bytes": 37,
                "ordinary_bank0_bss_headroom_bytes": 218,
                "fixed_hot_block_headroom_bytes": 33,
                "resident_island_headroom_bytes": 5,
                "e000_headroom_bytes": 54}
            and capacity["session_family_bytes"] == 65438
            and capacity["session_family_headroom_bytes"] == 98
            and semantics["status"] == "passed"
            and roots_fronts["status"].startswith("passed")
            and no_attic["status"].startswith("passed")
            and stage["status"] == "passed"
            and overlay["status"] == "passed-final-elf-overlay-closure"
            and preinstall["status"] ==
                "passed-static-preinstallation-Island-gate"
            and root["status"].startswith("passed-bound")
            and family_seam["status"] ==
                "passed-derived-family-seam-closure"
            and identity["status"].startswith("passed")
            and transient["linked"]["status"] ==
                "passed-linked-one-normalizer-common-record-path"
            and append["linked"]["walker"]["facade_routed_C_call_edges"] == 2
            and abi["c2_append_plan_walk_callers"]["status"] ==
                "passed-complete-C-facade-ASM-C-plan-walker-ABI"
            and bank2["phase"]["bytes"] <= LINK44.B.CAP
            and workbench_scratch["workbench_scratch_passing_records"] == 0,
            "one or more read-only facade-16 replacement gates are red")
    return {
        "status": "passed-read-only-completion-of-facade16-WPLTO",
        "walls": walls,
        "capacity": capacity,
        "product_semantics": semantics,
        "roots_fronts": roots_fronts,
        "no_runtime_attic": no_attic,
        "bank3_stage_before_publish": stage,
        "overlay_closure": overlay,
        "preinstallation_island": preinstall,
        "root_surrogate": root,
        "derived_family_seam": family_seam,
        "final_island_identity": identity,
        "bcode_ordinal_renderer": ordinal,
        "assembler_leaf_abi": abi,
        "assembler_leaf_mutations": abi_mutations,
        "transient_execution": transient,
        "zero_literal_execution": zero,
        "append_phase_plan": append,
        "numeric_early_errors": numeric,
        "bank2_target_stage": bank2,
        "bank2_workbench_scratch_negative": workbench_scratch,
        "workbench_crc": workbench_crc_gate(),
    }


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "facade-16 artifact replay is one-shot")
    require(FIRST_RED.is_file() and sha(FIRST_RED) == FIRST_RED_SHA,
            "facade-16 semantic-gate First Red authority drift")
    require(COMPILER_FIRST_RED.is_file(),
            "pure-replay host-compiler First Red authority absent")
    first = json.loads(FIRST_RED.read_text())
    require(first["diagnostic"] == {
                "type": "ProbeError",
                "message": "co-resident product semantic gate red: "
                           "['only_fused_publication_emitted', "
                           "'restored_e000_floor']"}
            and first["execution_accounting"]["product_closure_links"] == 1,
            "artifact replay is not bound to the two-field checker-model Red")
    require(all(path.is_file() for path in (PRODUCT, ELF, MAP)),
            "frozen facade-16 WPLTO artifacts absent")
    before = snapshot(SOURCE)
    require(before and all((int(row["mode"], 8) & 0o222) == 0
                           for row in before.values()),
            "frozen facade-16 WPLTO tree is not read-only")
    OUT.mkdir(parents=True)
    configure_profile()
    original_run = subprocess.run
    commands: list[str] = []

    def guarded_run(command: Any, *args: Any, **kwargs: Any) -> Any:
        executable = Path(str(command[0] if isinstance(command, (list, tuple))
                              else command)).name
        lowered = executable.lower()
        require("clang" not in lowered and lowered not in {
                    "cc", "gcc", "ld", "ld.lld", "lld",
                    "mos-mega65-clang"},
                f"pure replay attempted compiler/linker: {executable}")
        commands.append(executable)
        return original_run(command, *args, **kwargs)

    old_out = BASE_LINK.OUT
    try:
        BASE_LINK.OUT = SOURCE
        subprocess.run = guarded_run
        generic = generic_gate_evidence()
        replay = read_only_replay()
    finally:
        subprocess.run = original_run
        BASE_LINK.OUT = old_out
    after = snapshot(SOURCE)
    require(before == after, "pure replay modified the frozen WPLTO tree")
    value = {
        "format": "lisp65-c2-lite-v6-facade16-artifact-replay-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-complete-facade16-WPLTO-artifact-replay",
        "promotable": False,
        "authority": {
            "semantic_checker_first_red": bind(FIRST_RED),
            "facade_provenance_checker_first_red": bind(
                PROVENANCE_FIRST_RED),
            "host_compiler_interception_first_red": bind(
                COMPILER_FIRST_RED),
            "replay_driver": bind(Path(__file__))},
        "class_a_correction": {
            "old_publication_section": ".lisp65_rt_c2append_publish_exports",
            "current_publication_section": ".lisp65_rt_c2append_publish_clear",
            "old_e000_floor_bytes": 115,
            "current_e000_floor_bytes": 54,
            "product_bytes_changed": 0,
            "capacity_effect_bytes": 0},
        "frozen_generic_gates": generic,
        "fresh_read_only_replay": replay,
        "frozen_identity": {"product": bind(PRODUCT), "elf": bind(ELF),
                            "map": bind(MAP)},
        "immutable_tree": {"files": len(before),
                           "byte_and_mode_identity": "unchanged"},
        "execution_accounting": {
            "compiler_runs": 0, "linker_runs": 0,
            "new_product_links": 0, "hardware_runs": 0,
            "source_wplto_product_closure_links": 1,
            "read_only_tool_invocations": commands},
        "counters": {"line1_product_first_reds": "2/3",
                     "completed_latency_measurements": "0/2"},
        "claim_limit": (
            "Artifact-only completion of one immutable product-shaped WPLTO. "
            "No new compilation, link, product candidate, hardware, latency, "
            "promotion or acceptance claim."),
        "next_gate": "the owner-authorized successor product link",
    }
    report = OUT / "artifact-replay-report.json"
    write(report, value)
    value["replay_report"] = bind(report)
    write(RECEIPT, value)
    for path in OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    os.chmod(RECEIPT, 0o444)
    return value


def main() -> int:
    try:
        value = build()
    except Exception as error:
        print("c2-lite-v6-facade16-artifact-replay: FIRST RED " + str(error),
              file=sys.stderr)
        return 2
    walls = value["fresh_read_only_replay"]["walls"]
    capacity = value["fresh_read_only_replay"]["capacity"]
    print("c2-lite-v6-facade16-artifact-replay: PASS "
          f"text={walls['bank0_text_headroom_bytes']} "
          f"e000={walls['e000_headroom_bytes']} "
          f"island={walls['resident_island_headroom_bytes']} "
          f"session={capacity['session_family_bytes']} "
          "compiler=0 linker=0 hardware=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
