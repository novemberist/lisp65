#!/usr/bin/env python3
"""Build the owner-approved Link-68 require-resolver successor product."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_canonical_product as CAN  # noqa: E402
import c2_require_resolver_gate as GATE  # noqa: E402
import c2_require_resolver_wplto as REQ  # noqa: E402


LINK = 68
BUILD = ROOT / "build/post-promotion/link68-require-resolver"
WPLTO = BUILD / "wplto"
FINAL = BUILD / "final"
ARTIFACTS = BUILD / "artifacts"
RECEIPTS = BUILD / "receipts"
MANIFEST = BUILD / "canonical-product-manifest.json"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
AUTHORITY = EVIDENCE / "c2.2-require-resolver-wplto-receipt.json"
RECEIPT = EVIDENCE / (
    "c2.2-product-link68-require-resolver-structural-receipt.json")


class LinkError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise LinkError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path, role: str | None = None) -> dict[str, Any]:
    require(path.is_file(), f"Link-68 artifact absent: {path}")
    row: dict[str, Any] = {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }
    if role is not None:
        row["role"] = role
    return row


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")


def emitted_library(path: Path) -> Path:
    suffix = ".manifest.json"
    require(path.as_posix().endswith(suffix),
            f"unexpected static manifest name: {path}")
    return Path(path.as_posix()[:-len(suffix)] + ".ext.bin")


def configure() -> None:
    REQ.BUILD = BUILD
    REQ.WPLTO = WPLTO
    REQ.RECEIPTS = RECEIPTS
    REQ.STATIC_RECEIPT = RECEIPTS / "require-static-plane-authority.json"
    REQ.configure()
    CAN.BUILD = BUILD
    CAN.WPLTO = WPLTO
    CAN.FINAL = FINAL
    CAN.ARTIFACTS = ARTIFACTS
    CAN.RECEIPTS = RECEIPTS
    CAN.MANIFEST = MANIFEST
    os.environ.update(CAN.canonical_build_environment())


def accepted_authority() -> dict[str, Any]:
    authority = load(AUTHORITY)
    require(
        authority["status"]
            == "passed-bank2-orchestrated-require-product-shaped-WPLTO"
        and authority["resident_text_criterion"]["passed"] is True
        and authority["resident_text_criterion"]["delta_bytes"] == 49
        and authority["resident_text_criterion"]["noise_reserve_bytes"] == 41
        and authority["freight"]["bank2_candidate_bytes"] == 40241
        and authority["freight"]["new_session_records"] == 0
        and authority["walls"] == {
            "bank0_text_headroom_bytes": 41,
            "e000_headroom_bytes": 60,
            "fixed_hot_block_headroom_bytes": 2,
            "ordinary_bank0_bss_headroom_bytes": 137,
            "resident_island_headroom_bytes": 69,
        }
        and authority["capacity"]["session_family_headroom_bytes"] == 610
        and authority["ELF_gate"]["leaf_bytes"] == 89,
        "Link-68 WPLTO authority is not the owner-approved green map")
    return authority


def fresh_source_gates() -> dict[str, Any]:
    abi = subprocess.run(
        [sys.executable, "tools/host-lisp/bytecode_abi_ledger.py",
         "--selftest"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    registry = subprocess.run(
        [sys.executable, "tools/host-lisp/v2_native_function_registry.py",
         "check"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    resolver = subprocess.run(
        [sys.executable, "tools/host-lisp/c2_require_resolver_gate.py"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    source = load(GATE.RECEIPT)
    require(
        abi.returncode == registry.returncode == resolver.returncode == 0
        and "SELFTEST PASS" in abi.stdout
        and "registry: PASS" in registry.stdout
        and source["status"]
            == "passed-bank2-orchestrated-require-and-private-c2d-byte-gates"
        and source["host_first_prerequisite"]["cutpoints"] == 12
        and source["host_first_prerequisite"]["mutations"] == 38
        and len(source["source_mutations"]) == 22
        and len(source["binary_index"]["mutations_rejected"]) == 29,
        "Link-68 fresh source/ABI/index gates are red")
    return {
        "resolver": source,
        "ABI_ledger": abi.stdout.strip(),
        "native_registry": registry.stdout.strip(),
    }


def complete_action() -> int:
    configure()
    replay = CAN.REPLAY
    original = replay.configure

    def current_geometry() -> None:
        replay.PROFILE.configure()
        replay.BANK2.configure_bank2_stage()
        replay.TWO.configure_two_region()
        replay.LINK60.configure_current_pin_adapters()
        replay.P.PRODUCT_ARTIFACTS_MANIFEST = (
            REQ.STATIC_PRODUCT / "substitution-artifacts.json")
        require(
            replay.P.RUNTIME_OVERLAY_FORMAT_VERSION == 4
            and replay.P.VERIFIER_BINDING_BASE
                == replay.P.LINK60_VERIFIER_BINDING_BASE == 0xB98A
            and replay.P.runtime_binding_bytes() == 40
            and replay.P.total_publish_last_bytes() == 42
            and replay.P.FIXED_BANK0_HOT_BSS_BASE == 0xC25D,
            "Link-68 artifact completion geometry drift")

    replay.configure = current_geometry
    try:
        completion = CAN.complete_artifacts()
    finally:
        replay.configure = original
    require(
        completion["status"]
            == "passed-no-relink-publish-last-artifact-completion"
        and completion["compiler_runs"] == completion["linker_runs"] == 0,
        "Link-68 artifact-side completion red")
    print(
        "c2-require-link68: ARTIFACT COMPLETION PASS "
        f"product={completion['product']['sha256']} compiler=0 linker=0")
    return 0


def complete_in_fresh_process() -> None:
    environment = os.environ.copy()
    environment.update(CAN.canonical_build_environment())
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "_complete"],
        cwd=ROOT, env=environment, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(
        result.returncode == 0,
        "Link-68 fresh-process artifact completion red:\n" + result.stdout)
    (RECEIPTS / "artifact-completion.log").write_text(
        result.stdout, encoding="utf-8")


def build_manifest(wplto: dict[str, Any],
                   completion: dict[str, Any]) -> dict[str, Any]:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    product = FINAL / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    profile = FINAL / "resolved-profile.txt"
    bootstage, bootstage_geometry = CAN.build_boot_stage(elf, profile)
    libraries = [
        emitted_library(REQ.SPECS[index][2]) for index in (1, 2, 3)]
    rows = [
        bind(elf, "linked-product-elf"),
        bind(product, "c2-resident-prg"),
        bind(FINAL / (
            "fresh-c2-lite-prelink-gates/v6-semantics/"
            "bank2-static-code.bin"), "c2-bank2-static-code-plane"),
        bind(FINAL / (
            "fresh-c2-lite-prelink-gates/v6-semantics/"
            "initial.c2d-v6.bin"), "c2d-v6-code-plane"),
        bind(bootstage, "c2-two-record-boot-stage"),
        bind(FINAL / "runtime-overlays-session-final.bin",
             "c2-session-family-region-0"),
        bind(REQ.STATIC_PRODUCT / "product-shelf-v4-direct.bin",
             "c2-product-shelf"),
        bind(FINAL / "runtime-overlays-boot-final.bin", "c2-boot-family"),
        bind(FINAL / "runtime-overlays-session-final-region1.bin",
             "c2-session-family-region-1"),
        bind(FINAL / "c2-product-kernal-window.bin", "c2-kernal-window"),
        bind(profile, "resolved-profile"),
        bind(libraries[0], "library-ide"),
        bind(libraries[1], "library-idex"),
        bind(libraries[2], "library-m65d"),
    ]
    value = {
        "format": "lisp65-c2-lite-canonical-product-manifest-v1",
        "status": "passed-fresh-source-product-and-post-link-completion",
        "contract": bind(CAN.CONTRACT),
        "static_plane": {
            "status": "passed-require-resolver-single-emitter-static-plane",
            "bank2_static_code_bytes": 40241,
            "entries": 676,
            "resolutions": 2676,
            "roots": 340,
        },
        "WPLTO": wplto,
        "artifact_completion": completion,
        "bootstage_geometry": bootstage_geometry,
        "artifact_count_before_media": len(rows),
        "artifacts": rows,
        "identity": {
            "resident_prg_sha256": sha(product),
            "linked_elf_sha256": sha(elf),
            "resolved_profile_sha256": sha(profile),
        },
        "execution_accounting": {
            "whole_program_LTO_closure_links": 1,
            "post_link_compiler_runs": 0,
            "post_link_linker_runs": 0,
            "hardware_runs": 0,
        },
        "canonical_build_environment": CAN.canonical_build_environment(),
    }
    write(MANIFEST, value)
    return value


def link_action() -> int:
    require(not BUILD.exists() and not RECEIPT.exists(),
            "Link-68 is one-shot and already has output")
    authority = accepted_authority()
    gates = fresh_source_gates()
    configure()
    BUILD.mkdir(parents=True)
    static = REQ.build_static_plane()
    plane = REQ.F1W.static_gate()
    wplto = CAN.run_wplto()
    replacement = wplto["historical_checker_boundary"][
        "current_replacement_gates"]
    walls = replacement["walls"]
    capacity = replacement["capacity"]
    require(
        static["semantics"]["code_bytes"] == 40241
        and plane["static_code_bytes"] == 40241
        and walls == authority["walls"]
        and capacity["session_family_headroom_bytes"] == 610
        and REQ.runtime_manifest_gate()["new_records"] == 0
        and REQ.elf_symbol_gate()["leaf_bytes"] == 89,
        "Link-68 fresh WPLTO differs from its approved map")
    complete_in_fresh_process()
    return record_final(authority, gates, wplto)


def record_final(authority: dict[str, Any], gates: dict[str, Any],
                 wplto: dict[str, Any]) -> int:
    replacement = wplto["historical_checker_boundary"][
        "current_replacement_gates"]
    walls = replacement["walls"]
    capacity = replacement["capacity"]
    completion = load(RECEIPTS / "artifact-completion.json")
    manifest = build_manifest(wplto, completion)
    checked = CAN.check()
    product = FINAL / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    product_link = load(FINAL / "product-substitution-link.json")
    require(
        checked["identity"] == manifest["identity"]
        and product_link["status"] == "passed"
        and product_link["product_closure_link_count"] == 1
        and completion["product"]["sha256"] == sha(product),
        "Link-68 completed product closure red")
    value = {
        "format": "lisp65-c2.2-product-link68-require-resolver-v1",
        "recorded_on": "2026-07-27",
        "status":
            "passed-Link68-require-resolver-product-identity-hardware-not-run",
        "promotable": False,
        "link_number": LINK,
        "product": bind(product),
        "ELF": bind(elf),
        "profile": bind(FINAL / "resolved-profile.txt"),
        "manifest": bind(MANIFEST),
        "static_geometry": {
            "bank2_static_code_bytes": 40241,
            "entries": 676,
            "resolutions": 2676,
            "roots": 340,
            "direct_entry_refs": 642,
        },
        "walls": walls | {
            "session_family_headroom_bytes":
                capacity["session_family_headroom_bytes"]},
        "gates": {
            "source_index": gates["resolver"]["status"],
            "WPLTO": wplto["status"],
            "artifact_completion": completion["status"],
            "product_substitution_link": product_link["status"],
            "canonical_manifest": checked["status"],
            "all_green": True,
        },
        "execution_accounting": {
            "whole_program_product_links": 1,
            "artifact_completion_compiler_runs": 0,
            "artifact_completion_linker_runs": 0,
            "hardware_runs": 0,
        },
        "authority": {
            "approved_WPLTO": bind(AUTHORITY),
            "resolver_contract": bind(GATE.CONTRACT),
            "source_index_receipt": bind(GATE.RECEIPT),
            "WPLTO_internal": bind(RECEIPTS / "wplto-internal.json"),
            "artifact_completion": bind(
                RECEIPTS / "artifact-completion.json"),
            "driver": bind(Path(__file__).resolve()),
        },
        "next_gate": (
            "Build the host-first defstruct library probe, then bind this "
            "exact Link-68 identity and the real defstruct L65P artifact "
            "into one bundled hardware session."),
        "claim_limit": (
            "Structurally complete Link 68 only. Require execution, "
            "defstruct behavior, hardware acceptance and promotion remain "
            "unclaimed."),
    }
    write(RECEIPT, value)
    print(
        "c2-require-link68: PASS "
        f"product={sha(product)} bank2=40241 text=41 e000=60 "
        "session=610 hardware=not-run")
    return 0


def resume_action() -> int:
    require(BUILD.is_dir() and not RECEIPT.exists(),
            "Link-68 artifact resume requires one unfinished link")
    authority = accepted_authority()
    gates = fresh_source_gates()
    configure()
    internal = load(RECEIPTS / "wplto-internal.json")
    replacement = internal["fresh_replacement_gates"]
    require(
        internal["status"]
            == "passed-new-c2-lite-real-abi-identity-hardware-not-run"
        and replacement["status"] == "passed"
        and replacement["walls"] == authority["walls"]
        and (WPLTO / "lisp65-c2-substitution-linked.prg").is_file()
        and (WPLTO / "lisp65-c2-substitution-linked.prg.elf").is_file(),
        "Link-68 artifact resume lacks the completed green WPLTO")
    if FINAL.exists():
        CAN.make_writable(FINAL)
        shutil.rmtree(FINAL)
    completion = RECEIPTS / "artifact-completion.json"
    if completion.exists():
        completion.unlink()
    complete_in_fresh_process()
    wplto = {
        "status":
            "passed-one-current-WPLTO-closure-at-typed-historical-"
            "qualification-boundary",
        "publish_last_authority": "0xb98a",
        "historical_checker_boundary": {
            "classification":
                "qualification-model-only-not-a-product-or-link-red",
            "current_replacement_gates": replacement,
        },
        "resume_source": bind(RECEIPTS / "wplto-internal.json"),
    }
    return record_final(authority, gates, wplto)


def main() -> int:
    action = sys.argv[1:] or ["link"]
    require(action in (["link"], ["resume"], ["_complete"]),
            "usage: c2_require_resolver_successor_link68.py "
            "[link|resume|_complete]")
    if action == ["_complete"]:
        return complete_action()
    if action == ["resume"]:
        return resume_action()
    return link_action()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        LinkError, REQ.ProbeError, CAN.CanonicalError, OSError, ValueError,
        KeyError, json.JSONDecodeError, subprocess.SubprocessError,
    ) as error:
        print("c2-require-link68: FIRST RED: " + str(error),
              file=sys.stderr)
        raise SystemExit(2)
