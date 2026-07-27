#!/usr/bin/env python3
"""Finish Link 37 from its immutable post-link First-Red artifacts.

This continuation performs no compiler or linker invocation.  It copies the
SHA-bound Link-37 artifacts, applies the profile-specific B99B publish-last
table, repacks the two runtime families from the existing ELF, and runs the
remaining structural and C2-lite replacement gates.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_direct_entry_contract as LITE_DIRECT  # noqa: E402
import c2_lite_v6_first_product_link as LINK  # noqa: E402
import c2_lite_v6_publish_last_geometry as GEOMETRY  # noqa: E402


P = LINK.P
V6 = LINK.V6
DIET = LINK.DIET
BASE = LINK.BASE
ROOT_GATE = LINK.ROOT_GATE
SOURCE = ROOT / (
    "build/c2.2/substitution/product-link-37-c2-lite-v6-successor2")
SOURCE_RECEIPT = LINK.EVIDENCE / (
    "c2.2-product-link37-c2-lite-v6-successor2-structural-receipt.json")
OUT = ROOT / (
    "build/c2.2/substitution/product-link-37-c2-lite-v6-artifact-resume")
RECEIPT = LINK.EVIDENCE / (
    "c2.2-product-link37-c2-lite-v6-artifact-resume-structural-receipt.json")
PRODUCT_NAME = "lisp65-c2-substitution-linked.prg"
EXPECTED_SOURCE_PRODUCT = (
    "c2bb7d1fbf5ba5eb7f54326dda88cef0fd4c227f494e2872fc036ef7c5ed35d2")
EXPECTED_SOURCE_ELF = (
    "8a2cdec687024e9b9ef8e492fec04ff983d5b7c72326d3a34a2bed7097453ca9")
EXPECTED_UNBOUND = (
    "03f381d46950feeb0e4028f7417e32bb50817123bb4a520b6b2e522c6f476c0a")
EXPECTED_BOOT_UNBOUND = (
    "1b2a2545c758096b296667e9fc652cbdde66676c7d441a70465c69c21bd9523e")
EXPECTED_SESSION_UNBOUND = (
    "4f4e25bcf72c4329799961d0e3871b3f17f6955caa4908f943f02653a7a9c3a4")
EXTRA_AUTHORITY: dict[str, Any] = {}


class ResumeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ResumeError(message)


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


def tree(path: Path) -> dict[str, dict[str, Any]]:
    return {item.relative_to(path).as_posix(): {
                "bytes": item.stat().st_size, "sha256": sha(item)}
            for item in sorted(path.rglob("*")) if item.is_file()}


def make_writable(path: Path) -> None:
    for item in sorted(path.rglob("*")):
        if item.is_dir():
            os.chmod(item, 0o755)
        elif item.is_file():
            os.chmod(item, 0o644)
    os.chmod(path, 0o755)


def validate_source() -> tuple[dict[str, Any], dict[str, Any]]:
    require(SOURCE.is_dir() and SOURCE_RECEIPT.is_file(),
            "Link-37 First-Red source absent")
    receipt = json.loads(SOURCE_RECEIPT.read_text(encoding="utf-8"))
    require(receipt.get("status")
            == "FIRST RED: first C2-lite product link stopped"
            and receipt["diagnostic"]["message"]
                == "verifier binding address drift 0xb99b != 0xb954"
            and receipt["execution_accounting"] == {
                "hardware_runs": 0, "product_closure_links": 1},
            "Link-37 source First Red drift")
    actual = tree(SOURCE)
    require(actual == receipt["evidence"],
            "Link-37 protected source tree differs from its SHA receipt")
    expected = {
        PRODUCT_NAME: EXPECTED_SOURCE_PRODUCT,
        PRODUCT_NAME + ".elf": EXPECTED_SOURCE_ELF,
        "lisp65-c2-substitution-unbound.prg": EXPECTED_UNBOUND,
        "runtime-overlays-boot-unbound.bin": EXPECTED_BOOT_UNBOUND,
        "runtime-overlays-session-unbound.bin": EXPECTED_SESSION_UNBOUND,
    }
    require(all(actual[name]["sha256"] == digest
                for name, digest in expected.items()),
            "Link-37 named source identity drift")
    require(sha(LINK.LINK35_PRODUCT) == LINK.LINK35_PRODUCT_SHA,
            "Link-35 rollback product drift")
    return receipt, actual


def copy_source() -> None:
    require(not OUT.exists() and not RECEIPT.exists(),
            "Link-37 artifact continuation is one-shot")
    shutil.copytree(SOURCE, OUT, copy_function=shutil.copy2)
    make_writable(OUT)


def cached_host_semantics() -> dict[str, Any]:
    """Re-run model semantics with the already built, SHA-bound emitter SO."""
    cached = SOURCE / (
        "fresh-c2-lite-prelink-gates/v6-semantics/"
        "c2d-v6-entry-emitter-host.so")
    require(sha(cached)
            == "602bd3d7a141e7a686a40d0696056d413fcea9c46acdf53e50f2802ae0a54d58",
            "cached one-emitter host artifact drift")
    lib = ctypes.CDLL(str(cached))
    fn = lib.lisp65_c2d_v6_emit_entry_row
    fn.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint8,
                   ctypes.c_uint8, ctypes.c_uint16, ctypes.c_uint16,
                   ctypes.c_uint16, ctypes.c_uint16]
    fn.restype = ctypes.c_uint8
    old = (V6.OUT, V6._ENTRY_EMITTER, V6._ENTRY_EMITTER_PATH)
    try:
        V6.OUT = OUT / "artifact-only-v6-host-replay"
        V6.OUT.mkdir()
        V6._ENTRY_EMITTER = fn
        V6._ENTRY_EMITTER_PATH = cached
        host = V6.host_semantics()
        lifetime = V6.bank3_lifetime()
    finally:
        V6.OUT, V6._ENTRY_EMITTER, V6._ENTRY_EMITTER_PATH = old
    publication = DIET.PLAN.publication_model_gate()
    source = DIET.source_contract_gate()
    protocol = DIET.COLD.publication_protocol_gate()
    stage = {
        "status": "passed",
        "publication": publication,
        "source_contract": source,
        "maximum_plan_protocol": protocol,
        "one_emitter": host["one_emitter"],
        "evidence_mode": (
            "model replay with the exact SHA-bound host emitter from the "
            "consumed Link-37 prelink; no compiler invocation"),
    }
    require(host["status"] == "passed"
            and host["rollback"]["count"] == 8
            and host["stale_generation"]["old_handles_rejected"] > 0
            and lifetime["status"] == "passed-lifetime-exclusive"
            and publication["status"] == source["status"]
                == protocol["status"] == "passed",
            "artifact-only C2-lite semantic replay red")
    return {
        "status": "passed-artifact-only-model-replay",
        "c2d_v6_host_semantics": host,
        "bank3_lifetime_model": lifetime,
        "stage_before_publish_and_one_emitter": stage,
    }


def direct_entry_gate() -> dict[str, Any]:
    receipt = json.loads(LITE_DIRECT.RECEIPT.read_text(encoding="utf-8"))
    generated = OUT / "generated-product-sources"
    pairs = (
        (generated / "c2-stream-v2-phase-08.c",
         ROOT / "scripts/c2-stream-v2-phase-08.c"),
        (generated / "c2-stream-v2-phase-12.c",
         ROOT / "scripts/c2-stream-v2-phase-12.c"),
    )
    require(all(left.read_bytes() == right.read_bytes()
                for left, right in pairs),
            "generated direct-entry phases differ from current source truth")
    parity = receipt["cross_parity"]
    require(parity["direct_entry_references"] == 637
            and parity["fixnum_decodable_published_values"] == 0
            and parity["target_phase12_negative_classes"] == 4,
            "current C2-lite direct-entry receipt red")
    return {
        "status": "passed-637-of-637-fixnum-values-zero",
        "receipt": bind(LITE_DIRECT.RECEIPT),
        "generated_phase_sources_byte_identical": 2,
        "references": 637, "fixnum_decodable": 0,
        "negative_classes": 4,
    }


def f011_gate(elf: Path) -> dict[str, Any]:
    value = P.F011_WINDOW.audit(P.F011_WINDOW.disassemble(
        P.TOOLCHAIN / "llvm-objdump", elf))
    write_json(OUT / "c2-f011-mount-window-gate.json", value)
    return value


def final_generic_gates(product: Path, elf: Path,
                        boot_unbound: tuple[Path, Path],
                        session_unbound: tuple[Path, Path]) -> dict[str, Any]:
    crc_codegen = P.CRC_CODEGEN.audit_elf(
        elf, out=OUT / "c2-crc-codegen-gate.json")
    crc_leaf = P.CRC_ASM_LEAF.audit_elf(
        elf, out=OUT / "c2-crc-asm-leaf-gate.json")
    f011 = f011_gate(elf)
    inventory = P.final_section_inventory_gate(OUT, product)
    handoff = P.handoff_z_abi_gate(OUT, product, "artifact-resume")
    preownership = P.pre_ownership_gate(
        OUT, product, "artifact-resume")
    data = P.profile_data_reference_gate(
        OUT, product, "artifact-resume", preownership)
    facade = P.fixed_facade_gate(OUT, product, "artifact-resume")

    binding = P.patch_verifier_binding_table(
        OUT, product, boot_unbound[1], session_unbound[1],
        expected_base=GEOMETRY.ADDRESS)
    window = json.loads(
        (OUT / "kernal-window-publish-last.json").read_text(encoding="utf-8"))
    require(window.get("status") == "passed",
            "bound KERNAL publish-last evidence is not green")
    total = P.total_publish_last_gate(
        OUT, product, window, binding,
        expected_verifier_base=GEOMETRY.ADDRESS)
    # The consumed product link packed the unbound references against this
    # exact contract object.  Using the generated C header instead changes the
    # ABI build-id and record CRC fields despite identical slice payloads.
    contract = OUT / "resolved-profile.txt"
    boot_final = P.overlay_pack_family(
        OUT, product, contract, "boot", "final")
    session_final = P.overlay_pack_family(
        OUT, product, contract, "session", "final")
    family = P.runtime_family_identity_gate(
        OUT, boot_unbound, session_unbound, boot_final, session_final)
    (OUT / "runtime-overlays-final.bin").write_bytes(
        session_final[0].read_bytes())
    P.closure_gate(OUT, product)
    closure = json.loads((OUT / "one-truth-closure.json").read_text())
    kernal = P.kernal_freedom_gate(OUT, product)
    balance = P.substitution_balance(OUT, product, kernal)
    overlay = BASE.LINK33_BASE.final_overlay_closure(elf)
    preinstall = BASE.ISLAND.static_elf_gate(elf)
    write_json(OUT / "overlay-closure-artifact-resume.json", overlay)
    write_json(OUT / "preinstallation-island-artifact-resume.json", preinstall)
    required = {
        "crc_codegen": crc_codegen["status"],
        "crc_assembler_leaf": crc_leaf["status"],
        "f011_mount_window": f011["status"],
        "section_inventory": inventory["status"],
        "handoff_z_abi": handoff["status"],
        "pre_ownership": preownership["status"],
        "profile_data_reference": data["status"],
        "fixed_facade": facade["status"],
        "kernal_publish_last": window["status"],
        "verifier_publish_last": binding["status"],
        "total_publish_last": total["status"],
        "runtime_family_identity": family["status"],
        "one_truth_closure": closure["status"],
        "kernal_freedom": kernal["status"],
        "substitution_balance": balance["status"],
        "overlay_closure": overlay["status"],
        "preinstallation_island": preinstall["status"],
    }
    require(all("pass" in str(value) for value in required.values()),
            f"Link-37 final generic gate red: {required}")
    return {
        "status": "passed",
        "gates": required,
        "publish_last": total,
        "verifier_binding": binding,
        "runtime_family_identity": family,
        "kernal_freedom": kernal,
        "substitution_balance": balance,
        "boot_final": bind(boot_final[0]),
        "session_final": bind(session_final[0]),
    }


def product_link_report(product: Path, generic: dict[str, Any],
                        replacement: dict[str, Any],
                        direct: dict[str, Any]) -> dict[str, Any]:
    total = generic["publish_last"]
    report = {
        "format": "lisp65-c2-lite-product-link37-artifact-completion-v1",
        "status": "passed",
        "link_label": OUT.name,
        "product": product.relative_to(ROOT).as_posix(),
        "product_sha256": sha(product),
        "product_closure_link_count": 1,
        "artifact_resume_compiler_runs": 0,
        "artifact_resume_linker_runs": 0,
        "identity_gate": "passed",
        "capacity_gate": "passed",
        "one_truth_gate": "passed",
        "kernal_freedom_gate": "passed",
        "direct_entry_encoding_gate": direct["status"],
        "c2_lite_replacement_gate": replacement["status"],
        "total_post_link_mutable_product_bytes":
            total["declared_domain_bytes"],
        "actual_post_link_changed_bytes": total["actual_changed_bytes"],
        "runtime_family_headroom_bytes": {
            "boot": replacement["runtime_family"]
                ["successor_bank3_pack"]["boot"]["headroom_bytes"],
            "session": replacement["runtime_family"]
                ["successor_bank3_pack"]["session"]["headroom_bytes"],
        },
        "claim_limit": (
            "Artifact-side completion of the already consumed sole Link-37 "
            "product closure. No compiler, linker, hardware, promotion or "
            "acceptance claim."),
    }
    write_json(OUT / "product-substitution-link.json", report)
    return report


def protect() -> None:
    if OUT.is_dir():
        BASE.protect(OUT)
    if RECEIPT.is_file():
        os.chmod(RECEIPT, 0o444)


def build() -> dict[str, Any]:
    source_receipt, source_tree = validate_source()
    features = LINK.configure()
    geometry = GEOMETRY.collect()
    copy_source()
    product = OUT / PRODUCT_NAME
    elf = Path(str(product) + ".elf")
    boot_unbound = (
        OUT / "runtime-overlays-boot-unbound.bin",
        OUT / "runtime-overlays-boot-unbound.json")
    session_unbound = (
        OUT / "runtime-overlays-session-unbound.bin",
        OUT / "runtime-overlays-session-unbound.json")
    before_source = tree(SOURCE)
    try:
        host = cached_host_semantics()
        direct = direct_entry_gate()
        generic = final_generic_gates(
            product, elf, boot_unbound, session_unbound)
        old_out = LINK.OUT
        try:
            LINK.OUT = OUT
            replacement = LINK.c2_lite_product_gates(product, elf, host)
        finally:
            LINK.OUT = old_out
        require(replacement["status"] == "passed",
                "C2-lite replacement gate set red")
        report = product_link_report(product, generic, replacement, direct)
        require(sha(product) not in {
                    EXPECTED_SOURCE_PRODUCT, EXPECTED_UNBOUND,
                    LINK.LINK35_PRODUCT_SHA}
                and sha(elf) == EXPECTED_SOURCE_ELF,
                "Link-37 final identity did not bind the existing ELF uniquely")
        require(tree(SOURCE) == before_source == source_tree,
                "protected Link-37 source artifacts changed during continuation")
        value = {
            "format": "lisp65-c2-lite-product-link37-artifact-resume-v1",
            "recorded_on": "2026-07-21",
            "status": "passed-new-c2-lite-product-identity-hardware-not-run",
            "promotable": False,
            "link_number": 37,
            "completion_mode": (
                "artifact-only continuation after profile-specific verifier "
                "geometry re-pin; no compiler or linker"),
            "execution_accounting": {
                "source_product_closure_links": 1,
                "artifact_resume_product_closure_links": 0,
                "artifact_resume_compiler_runs": 0,
                "artifact_resume_linker_runs": 0,
                "runtime_family_pack_runs": 2,
                "hardware_runs": 0,
            },
            "authority": {
                "source_first_red": bind(SOURCE_RECEIPT),
                "c2_lite_contract": bind(LINK.CONTRACT),
                "c2_lite_addendum": bind(LINK.ADDENDUM),
                "geometry_gate_source": bind(
                    ROOT / "tools/host-lisp/"
                    "c2_lite_v6_publish_last_geometry.py"),
                "artifact_resume_driver": bind(Path(__file__)),
                **EXTRA_AUTHORITY,
            },
            "publish_last_geometry": geometry,
            "product_identity": {
                "product": bind(product), "elf": bind(elf),
                "map": bind(Path(str(product) + ".map")),
                "resolved_profile": bind(OUT / "resolved-profile.txt"),
                "pre_publish_product_sha256": EXPECTED_SOURCE_PRODUCT,
                "unbound_product_sha256": EXPECTED_UNBOUND,
                "new_identity": True,
            },
            "fresh_generic_gates": generic["gates"],
            "fresh_c2_lite_replacement_gates": replacement,
            "artifact_model_replay": host,
            "direct_entry_gate": direct,
            "post_link_identity": {
                "declared_mutable_product_bytes":
                    generic["publish_last"]["declared_domain_bytes"],
                "actual_changed_bytes":
                    generic["publish_last"]["actual_changed_bytes"],
                "status": generic["publish_last"]["status"],
            },
            "product_link_report": report,
            "rollback_line": {
                **bind(LINK.LINK35_PRODUCT),
                "status": "untouched-and-readable"},
            "source_first_red_artifacts": {
                "files": len(source_tree),
                "status": "SHA-bound-and-unchanged"},
            "claim_limit": (
                "First complete C2-lite product candidate and full structural, "
                "capacity, replacement and publish-last closure only. Hardware, "
                "boot, latency, refill timing, GC cost, Freezer identity, nested "
                "eval, promotion and acceptance remain not-run."),
            "next_gate": (
                "owner-authorized seven-line receipt-less hardware presmoke "
                "from line 1"),
        }
        write_json(OUT / "link37-c2-lite-v6-artifact-resume.json", value)
        receipt = {**value,
                   "structural_report": bind(
                       OUT / "link37-c2-lite-v6-artifact-resume.json"),
                   "evidence_file_count": len(tree(OUT))}
        write_json(RECEIPT, receipt)
        protect()
        return receipt
    except Exception as error:
        failure = {
            "format": "lisp65-c2-lite-product-link37-artifact-resume-v1",
            "recorded_on": "2026-07-21",
            "status": "FIRST RED: Link-37 artifact continuation stopped",
            "promotable": False,
            "diagnostic": {"type": type(error).__name__,
                           "message": str(error)},
            "execution_accounting": {
                "source_product_closure_links": 1,
                "artifact_resume_compiler_runs": 0,
                "artifact_resume_linker_runs": 0,
                "hardware_runs": 0,
            },
            "source_first_red": bind(SOURCE_RECEIPT),
            "rollback_line": {**bind(LINK.LINK35_PRODUCT),
                              "status": "untouched"},
            "next_gate": "return to review; no compiler, linker or hardware",
        }
        write_json(RECEIPT, failure)
        protect()
        return failure


def main() -> int:
    value = build()
    print("c2-lite-v6-link37-artifact-resume: " + value["status"])
    return 2 if value["status"].startswith("FIRST RED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
