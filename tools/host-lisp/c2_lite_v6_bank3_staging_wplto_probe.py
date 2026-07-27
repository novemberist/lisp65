#!/usr/bin/env python3
"""Product-shaped C2-lite Bank-3 stage-before-publish WPLTO probe.

This is not a product link.  It prices the complete cold Boot/Session staging
implementation, binds the two final family manifests into the extended non-LTO
publish-last table, and proves that no family becomes callable before its full
Bank-3 destination CRC matches.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link33_bss_triage_product_link as BASE  # noqa: E402
import c2_lite_v6_coresident_diet_probe as DIET  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


P = BASE.P
OUT = ROOT / "build/c2-lite/v6-bank3-stage-asm-fallback-wplto-replay2"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-bank3-stage-asm-fallback-wplto-replay2-receipt.json")
CONTRACT = ROOT / "config/c2-lite-execution-contract.json"
ADDENDUM = ROOT / "docs/planning/c2-lite-execution-contract-addendum.md"
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link37-c2-lite-v6-hardware-first-red-diagnosis.json")
CAP = 1792
BANK_BYTES = 65536
E000_FLOOR = 115
VERIFIER_BASE = 0xB9CD


class ProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"artifact absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def feature_set() -> tuple[str, ...]:
    """Describe the final C2-lite feature set without mutating the profile."""
    base = tuple(item for item in BASE.FEATURES if item not in (
        "LISP65_RTOV_CRC_CONVERGENCE",
        "LISP65_RTOV_DMA_COMPLETION_FENCE",
        "LISP65_C2_PHASE11_SPLIT",
        "LISP65_C2_LITE_COLD_EVICTION",
        "LISP65_C2_LITE_V6_SEMANTIC_SPLITS",
        "LISP65_C2_LITE_V6_CORESIDENT_DIET",
        "LISP65_C2_LITE_CHIP_RAM",
        "LISP65_C2_LITE_BANK3_STAGING",
    ))
    features = (*base,
        "LISP65_C2_PHASE11_SPLIT",
        "LISP65_C2_LITE_COLD_EVICTION",
        "LISP65_C2_LITE_V6_SEMANTIC_SPLITS",
        "LISP65_C2_LITE_V6_CORESIDENT_DIET",
        "LISP65_C2_LITE_CHIP_RAM",
        "LISP65_C2_LITE_BANK3_STAGING")
    require(len(features) == len(set(features)), "feature duplication")
    return features


def apply_profile(base_configure: Any) -> None:
    """Apply the product profile exactly once inside the WPLTO driver."""
    base_configure()
    DIET.configure_coresident_diet()
    P.configure_bank3_staging_slices()
    P.E000_FINAL_FLOOR_BYTES = E000_FLOOR
    P.FAMILY_STAGE_BINDINGS = True
    P.VERIFIER_BINDING_BASE = VERIFIER_BASE


def state_machine_gate() -> dict[str, Any]:
    INACTIVE, BOOT, SESSION, STAGING, VERIFIED = 0, 1, 2, 0x40, 0x80

    class Model:
        def __init__(self) -> None:
            self.family = INACTIVE
            self.generation = 0
            self.published: list[tuple[int, int]] = []

        def begin(self, family: int, generation: int, busy: bool) -> bool:
            if family == BOOT:
                good = not busy and generation == 0 and self.family == INACTIVE
            else:
                good = (family == SESSION and busy and generation != 0
                        and self.family == BOOT)
            if not good:
                return False
            self.family = family | STAGING
            self.generation = generation
            return True

        def verify(self, family: int, generation: int,
                   destination: bytes, expected_crc: int) -> bool:
            good = (self.family == (family | STAGING)
                    and self.generation == generation
                    and P.crc16(destination) == expected_crc)
            if good:
                self.family = family | VERIFIED
            return good

        def publish(self, family: int, generation: int) -> bool:
            if (self.family != (family | VERIFIED)
                    or self.generation != generation):
                return False
            self.family = family
            self.published.append((family, generation))
            return True

    boot = bytes((i * 17 + 3) & 0xff for i in range(997))
    session = bytes((i * 29 + 11) & 0xff for i in range(4093))
    model = Model()
    require(not model.publish(BOOT, 0), "unstaged Boot published")
    require(model.begin(BOOT, 0, False), "Boot stage did not begin")
    corrupt = bytearray(boot); corrupt[-1] ^= 1
    require(not model.verify(BOOT, 0, bytes(corrupt), P.crc16(boot))
            and not model.publish(BOOT, 0), "corrupt Boot published")
    model = Model()
    require(model.begin(BOOT, 0, False)
            and model.verify(BOOT, 0, boot, P.crc16(boot))
            and model.publish(BOOT, 0), "verified Boot did not publish")
    require(not model.publish(SESSION, 7), "unstaged Session published")
    require(model.begin(SESSION, 7, True), "Session stage did not invalidate Boot")
    require(model.family == (SESSION | STAGING)
            and (BOOT, 0) == model.published[-1],
            "Boot was not invalidated before Session write")
    require(not model.verify(SESSION, 7, session, P.crc16(session) ^ 1)
            and not model.publish(SESSION, 7), "bad Session CRC published")
    model = Model(); model.begin(BOOT, 0, False)
    model.verify(BOOT, 0, boot, P.crc16(boot)); model.publish(BOOT, 0)
    require(model.begin(SESSION, 7, True)
            and model.verify(SESSION, 7, session, P.crc16(session))
            and model.publish(SESSION, 7), "verified Session did not publish")
    require(model.published == [(BOOT, 0), (SESSION, 7)],
            "publication order drift")
    return {
        "status": "passed",
        "cases": 8,
        "negative_fixtures": [
            "unstaged-boot", "corrupt-boot", "unstaged-session",
            "wrong-session-crc", "session-stage-without-busy-boot-slice"],
        "positive_fixtures": [
            "boot-destination-crc-before-publish",
            "boot-invalidated-before-session-copy",
            "session-destination-crc-before-publish"],
    }


def source_contract_gate() -> dict[str, Any]:
    boot = (ROOT / "src/vm_boot_overlay.c").read_text(encoding="utf-8")
    decoder = (ROOT / "scripts/c2-stream-decoder.c").read_text(encoding="utf-8")
    product = (ROOT / "src/c2_product_runtime.c").read_text(encoding="utf-8")
    rtov = (ROOT / "src/vm_runtime_overlay.c").read_text(encoding="utf-8")
    chain_asm = (ROOT / "src/c2_lite_bank3_stage_entry.s").read_text(
        encoding="utf-8")
    commit_asm = (ROOT / "src/c2_boot_chain_commit.s").read_text(
        encoding="utf-8")
    main = (ROOT / "src/main.c").read_text(encoding="utf-8")
    asm = (ROOT / "src/runtime_overlay_verifier_bindings.s").read_text(
        encoding="utf-8")
    def ordered(text: str, first: str, second: str) -> bool:
        left = text.find(first); right = text.find(second)
        return left >= 0 and right >= 0 and left < right

    def evaluate(boot_text: str, decoder_text: str, product_text: str,
                 rtov_text: str, chain_text: str,
                 commit_text: str) -> dict[str, bool]:
        select = V6.c_function_definition(
            rtov_text, "vm_runtime_overlay_select_family")
        decode = V6.c_function_definition(product_text, "c2_decode_from")
        stage_body_start = rtov_text.index("#define C2_LITE_STAGE_BODY")
        stage_body_end = rtov_text.index(
            "C2_LITE_STAGE_BODY(c2_lite_stage_boot_family_impl",
            stage_body_start)
        stage_body = rtov_text[stage_body_start:stage_body_end]
        overflow_stage = (
            V6.c_function_definition(
                rtov_text, "c2_lite_stage_session_overflow")
            if "c2_lite_stage_session_overflow(" in rtov_text else "")
        return {
            "boot_stage_is_cold_bounded_chain":
                'section(".lisp65_boot_bank3_stage")' in boot_text
                and "vm_boot_overlay_chain_prepare" in boot_text
                and "B3_CHAIN_BANK" in boot_text
                and "ov_load_record" not in boot_text
                and "jmp vm_boot_overlay_chain_commit" in chain_text
                and "void vm_boot_overlay_chain_commit" not in boot_text
                and ".type vm_boot_overlay_chain_commit,@function"
                    in commit_text
                and ".type vm_boot_overlay_chain_expected,@object"
                    in commit_text
                and "jsr c2_facade_c2_dma" in commit_text
                and "jsr ov_crc16" in commit_text,
            "workbench_no_longer_owns_boot_staging":
                "void vm_workbench_boot_overlay_entry(void) {\n    eval_init();\n}"
                    in boot_text,
            "session_stage_is_final_boot_family_slice":
                'section(".lisp65_rt_bank3_stage_session")' in rtov_text
                and "LISP65_C2_BANK3_STAGE_SESSION_SLOT" in decode
                and decode.index("LISP65_C2_PHASE_03_SLOT")
                    < decode.index("LISP65_C2_BANK3_STAGE_SESSION_SLOT")
                    < decode.index("c2_facade_select_family"),
            "phase03_is_validation_only":
                "c2_lite_stage_session_family" not in decoder_text,
            "attic_sources_are_family_specific":
                "LISP65_RUNTIME_OVERLAY_BOOT_STORAGE_BASE" in rtov_text
                and "LISP65_RUNTIME_OVERLAY_STORAGE_BASE" in rtov_text,
            "target_is_chip_bank3":
                "C2_LITE_BANK3_PHYSICAL 0x00030000UL" in rtov_text
                and "c2_facade_vm_code_load(3u" in rtov_text,
            "whole_destination_crc_precedes_verified_state":
                ordered(rtov_text, "crc == expected",
                        "rtov_family = (uint8_t)((family_value) | RTOV_FAMILY_VERIFIED)"),
            "select_requires_verified_state":
                "family | RTOV_FAMILY_VERIFIED" in select
                and "VM_RUNTIME_OVERLAY_ERR_FAMILY_STAGE" in select,
            "invalidation_precedes_copy":
                ordered(stage_body,
                        "rtov_family = (uint8_t)((family_value) | RTOV_FAMILY_STAGING)",
                        "c2_product_physical_copy"),
            "region1_target_proof_precedes_family_verified":
                (not overflow_stage or (
                    "c2_product_physical_copy(" in overflow_stage
                    and "crc == expected" in overflow_stage
                    and ordered(
                        stage_body, "crc == expected",
                        "C2_LITE_STAGE_SESSION_OVERFLOW")
                    and ordered(
                        stage_body, "C2_LITE_STAGE_SESSION_OVERFLOW",
                        "RTOV_FAMILY_VERIFIED"))),
            "resident_transition_api_is_absent":
                all(name not in rtov_text for name in (
                    "vm_runtime_overlay_stage_begin(",
                    "vm_runtime_overlay_stage_verified(",
                    "vm_runtime_overlay_stage_fail(")),
            "ready_remains_after_cold_session_stage":
                ordered(decode, "LISP65_C2_BANK3_STAGE_SESSION_SLOT",
                        "c2_facade_select_family")
                and ordered(main, "c2_product_prepare_boot",
                            "c2_product_boot"),
            "specific_status_is_user_visible":
                "LISP65_ERR_RUNTIME_FAMILY_STAGE" in main
                and "runtime family staging failed" in main,
            "publish_last_table_is_extended_not_renumbered":
                asm.index("__lisp65_rtov_verifier_bindings_end")
                    < asm.index("__lisp65_rtov_family_stage_bindings_start")
                and asm.count("rtov_family_stage_bindings:") == 1,
        }

    checks = evaluate(boot, decoder, product, rtov, chain_asm, commit_asm)
    require(all(checks.values()), "source contract red: " + str(
        [name for name, value in checks.items() if not value]))
    # Pinned source mutations exercise both directions of the linked gate.
    mutations = {
        "boot-stage-call-removed": chain_asm.replace(
            "jmp vm_boot_overlay_chain_commit", "rts", 1),
        "session-stage-call-removed": product.replace(
            "LISP65_C2_BANK3_STAGE_SESSION_SLOT",
            "LISP65_C2_PHASE_03_SLOT", 1),
        "verified-state-bypassed": rtov.replace(
            "family | RTOV_FAMILY_VERIFIED", "family | RTOV_FAMILY_STAGING", 1),
        "copy-before-invalidation": rtov.replace(
            "rtov_family = (uint8_t)((family_value) | RTOV_FAMILY_STAGING);",
            "rtov_family = (uint8_t)(family_value);", 1),
        "region1-target-proof-removed": rtov.replace(
            "if (!C2_LITE_STAGE_SESSION_OVERFLOW(family_value))",
            "if (!1u)", 1),
    }
    mutated_inputs = {
        "boot-stage-call-removed":
            (boot, decoder, product, rtov,
             mutations["boot-stage-call-removed"], commit_asm),
        "session-stage-call-removed":
            (boot, decoder, mutations["session-stage-call-removed"], rtov,
             chain_asm, commit_asm),
        "verified-state-bypassed":
            (boot, decoder, product, mutations["verified-state-bypassed"],
             chain_asm, commit_asm),
        "copy-before-invalidation":
            (boot, decoder, product, mutations["copy-before-invalidation"],
             chain_asm, commit_asm),
        "region1-target-proof-removed":
            (boot, decoder, product,
             mutations["region1-target-proof-removed"],
             chain_asm, commit_asm),
    }
    rejected = {}
    for name, inputs in mutated_inputs.items():
        result = evaluate(*inputs)
        require(not all(result.values()), f"source mutation escaped: {name}")
        rejected[name] = hashlib.sha256("\0".join(inputs).encode()).hexdigest()
    require(len(rejected) == 5, "source mutation did not alter its fixture")
    return {"status": "passed", "checks": checks,
            "mutations_rejected": list(rejected),
            "mutation_sha256": rejected}


def run_wplto(features: tuple[str, ...]) -> tuple[dict[str, Any], Path, Path]:
    original_configure = BASE.configure
    original_features = BASE.FEATURES
    original_out = V6.OUT

    def configured() -> None:
        apply_profile(original_configure)

    BASE.configure = configured
    # V6 adds the Chip-RAM define itself.  Feed it the exact pre-addition set
    # so the compile profile contains every dialect switch exactly once.
    BASE.FEATURES = tuple(
        item for item in features if item != "LISP65_C2_LITE_CHIP_RAM")
    V6.OUT = OUT
    try:
        result = V6.full_product_wplto()
    finally:
        BASE.configure = original_configure
        BASE.FEATURES = original_features
        V6.OUT = original_out
    target = OUT / "full-product-wplto/c2-lite-v6-full-seed.prg"
    elf = Path(str(target) + ".elf")
    require(target.is_file() and elf.is_file(), "WPLTO artifacts absent")
    return result, target, elf


def product_gate(wplto: dict[str, Any], target: Path,
                 elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=P.TOOLCHAIN / "llvm-readobj")
    symbols = {
        name: truth.symbol(name) for name in (
            "c2_lite_stage_boot_family_impl", "c2_lite_stage_boot_family",
            "vm_bank3_boot_stage_entry",
            "vm_boot_overlay_chain_prepare", "ov_bank_crc16",
            "vm_bank3_boot_stage_fail", "vm_boot_overlay_chain_commit",
            "c2_lite_stage_session_family_impl",
            "c2_lite_stage_session_family", "rtov_family_stage_bindings",
            "__lisp65_rtov_family_stage_bindings_start",
            "__lisp65_rtov_family_stage_bindings_end")}
    require(symbols["c2_lite_stage_boot_family_impl"].section
            == ".lisp65_boot_bank3_stage"
            and symbols["c2_lite_stage_boot_family"].section
            == ".lisp65_boot_bank3_stage"
            and symbols["vm_bank3_boot_stage_entry"].section
            == ".lisp65_boot_bank3_stage"
            and symbols["vm_boot_overlay_chain_prepare"].section
            == ".lisp65_boot_bank3_stage"
            and symbols["ov_bank_crc16"].section
            == ".lisp65_boot_bank3_stage"
            and symbols["vm_bank3_boot_stage_fail"].section
            == ".lisp65_boot_bank3_stage"
            and symbols["vm_boot_overlay_chain_commit"].section == ".text"
            and symbols["c2_lite_stage_session_family_impl"].section
            == ".lisp65_rt_bank3_stage_session"
            and symbols["c2_lite_stage_session_family"].section
            == ".lisp65_rt_bank3_stage_session",
            "staging code escaped its cold homes")
    for name in ("c2_lite_stage_boot_family_impl",
                 "c2_lite_stage_boot_family",
                 "vm_bank3_boot_stage_entry",
                 "vm_boot_overlay_chain_prepare", "ov_bank_crc16",
                 "vm_bank3_boot_stage_fail", "vm_boot_overlay_chain_commit",
                 "c2_lite_stage_session_family_impl",
                 "c2_lite_stage_session_family"):
        require(symbols[name].bytes > 0, f"unsized staging symbol: {name}")
    section = truth.section(P.VERIFIER_BINDING_SECTION)
    require(section.address == VERIFIER_BASE and section.bytes == 40,
            f"40-byte publish-last geometry red: {section}")
    require(symbols["rtov_family_stage_bindings"].value
            == VERIFIER_BASE + 32
            and symbols["__lisp65_rtov_family_stage_bindings_end"].value
            == VERIFIER_BASE + 40,
            "stage binding suffix geometry drift")

    full = target.parent
    boot_manifest = full / "runtime-overlays-boot-c2-lite.json"
    session_manifest = full / "runtime-overlays-session-c2-lite.json"
    binding = P.patch_verifier_binding_table(
        full, target, boot_manifest, session_manifest,
        expected_base=VERIFIER_BASE)
    table = (full / "runtime-overlay-verifier-bindings.bin").read_bytes()
    boot = json.loads(boot_manifest.read_text(encoding="utf-8"))
    session = json.loads(session_manifest.read_text(encoding="utf-8"))
    stage_words = struct.unpack_from("<4H", table, 32)
    expected_words = (
        boot["storage"]["size"], boot["storage"]["crc16"],
        session["storage"]["size"], session["storage"]["crc16"])
    require(stage_words == expected_words,
            "published stage tuples differ from final manifests")
    require(binding["bytes"] == 40
            and binding["tuple_order"][-2:] == [
                "boot-stage-size-crc", "session-stage-size-crc"],
            "stage tuple publication report red")
    phase03 = truth.section(".lisp65_rt_c2d_03")
    boot_record = truth.section(".lisp65_boot_bank3_stage")
    session_stage = truth.section(".lisp65_rt_bank3_stage_session")
    workbench = truth.section(".lisp65_workbench_overlay")
    require(all(0 < section.bytes <= CAP for section in
                (boot_record, session_stage, workbench, phase03)),
            "cold Bank-3 cut overgrew a 1792-byte record")
    symbol_names = truth.symbol_values()
    require(not any(truth.symbol(name).bytes for name in (
                "vm_runtime_overlay_stage_begin",
                "vm_runtime_overlay_stage_verified",
                "vm_runtime_overlay_stage_fail")
                if name in symbol_names),
            "resident staging transition API survived")
    require(wplto["walls"]["e000_headroom_bytes"] >= E000_FLOOR
            and all(value >= 0 for key, value in wplto["walls"].items()
                    if key != "e000_headroom_bytes"),
            "WPLTO wall red")
    require(boot["storage"]["size"] <= BANK_BYTES
            and session["storage"]["size"] <= BANK_BYTES,
            "Bank-3 family capacity red")
    return {
        "status": "passed",
        "cold_symbol_sections": {
            name: {"section": symbol.section, "address": symbol.value,
                   "bytes": symbol.bytes}
            for name, symbol in symbols.items()},
        "cold_cut_capacity": {
            "prefamily_boot_record_bytes": boot_record.bytes,
            "prefamily_boot_record_headroom_bytes": CAP - boot_record.bytes,
            "workbench_record_bytes": workbench.bytes,
            "workbench_record_headroom_bytes": CAP - workbench.bytes,
            "phase03_bytes": phase03.bytes,
            "phase03_headroom_bytes": CAP - phase03.bytes,
            "session_stage_slice_bytes": session_stage.bytes,
            "session_stage_slice_headroom_bytes": CAP - session_stage.bytes,
        },
        "publish_last": binding,
        "stage_binding_words": {
            "boot_size": stage_words[0], "boot_crc16": stage_words[1],
            "session_size": stage_words[2], "session_crc16": stage_words[3]},
        "family_capacity": {
            "boot_bytes": boot["storage"]["size"],
            "boot_headroom_bytes": BANK_BYTES - boot["storage"]["size"],
            "session_bytes": session["storage"]["size"],
            "session_headroom_bytes": BANK_BYTES - session["storage"]["size"]},
        "walls": wplto["walls"],
    }


def protect() -> None:
    for root in (OUT,):
        if root.exists():
            for path in root.rglob("*"):
                if path.is_file():
                    os.chmod(path, 0o444)
    if RECEIPT.is_file():
        os.chmod(RECEIPT, 0o444)


def first_red(error: BaseException) -> dict[str, Any]:
    evidence = [bind(path) for path in sorted(OUT.rglob("*")) if path.is_file()]
    value = {
        "format": "lisp65-c2-lite-bank3-staging-wplto-first-red-v1",
        "recorded_on": "2026-07-21",
        "status": "FIRST RED: Bank-3 staging product-shaped WPLTO stopped",
        "failure": {"type": type(error).__name__, "message": str(error)},
        "scope": {"whole_program_lto_probes": int(OUT.exists()),
                  "product_links": 0, "hardware_runs": 0,
                  "promotable": False},
        "evidence": evidence,
        "rollback_line": {"product": "Link 35", "status": "untouched"},
        "next_gate": "Class-C review; no product link or hardware",
    }
    write_json(RECEIPT, value); protect(); return value


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(), "probe already exists")
    for path in (CONTRACT, ADDENDUM, FIRST_RED):
        require(path.is_file(), f"authority absent: {path}")
    OUT.mkdir(parents=True)
    features = feature_set()
    states = state_machine_gate()
    source = source_contract_gate()
    write_json(OUT / "stage-state-machine-gate.json", states)
    write_json(OUT / "stage-source-contract-gate.json", source)
    wplto, target, elf = run_wplto(features)
    product = product_gate(wplto, target, elf)
    value = {
        "format": "lisp65-c2-lite-bank3-stage-before-publish-wplto-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-one-product-shaped-bank3-staging-wplto",
        "scope": {"whole_program_lto_probes": 1, "product_links": 0,
                  "hardware_runs": 0, "promotable": False},
        "authority": {"contract": bind(CONTRACT), "addendum": bind(ADDENDUM),
                      "link37_hardware_first_red": bind(FIRST_RED)},
        "feature_defines": list(features),
        "state_machine_gate": states,
        "source_contract_gate": source,
        "whole_program_lto": wplto,
        "product_gate": product,
        "artifacts": {"measurement_prg": bind(target),
                      "measurement_elf": bind(elf),
                      "measurement_map": bind(Path(str(target) + ".map"))},
        "claim_limit": (
            "One nonpromotable product-shaped WPLTO and artifact-only binding. "
            "No product link, hardware, latency, promotion or acceptance claim."),
        "rollback_line": {"product": "Link 35", "status": "untouched"},
        "next_gate": "Class-C approval before the successor product link",
    }
    write_json(OUT / "bank3-staging-wplto-report.json", value)
    value["probe_report"] = bind(OUT / "bank3-staging-wplto-report.json")
    write_json(RECEIPT, value); protect(); return value


def main() -> int:
    try:
        value = build()
    except Exception as error:
        if OUT.exists() and not RECEIPT.exists():
            first_red(error)
        print("c2-lite-bank3-staging: FIRST RED " + str(error))
        return 2
    gate = value["product_gate"]
    print("c2-lite-bank3-staging: PASS "
          f"boot={gate['family_capacity']['boot_bytes']} "
          f"session={gate['family_capacity']['session_bytes']} "
          f"phase03={gate['cold_cut_capacity']['phase03_bytes']} "
          f"stage={gate['cold_cut_capacity']['session_stage_slice_bytes']} "
          f"e000={gate['walls']['e000_headroom_bytes']} "
          "product-link=0 hardware=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
