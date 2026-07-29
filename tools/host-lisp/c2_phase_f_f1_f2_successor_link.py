#!/usr/bin/env python3
"""Build the one owner-approved Phase-F F1+F2 successor product link."""

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
import c2_bitops_gate as F2_GATE  # noqa: E402
import c2_f2_bitops_wplto as F2_WPLTO  # noqa: E402
import c2_lite_canonical_product as CAN  # noqa: E402
import c2_top_level_published_value_call_gate as F1_GATE  # noqa: E402


LINK_NUMBER = 67
BUILD = ROOT / "build/post-promotion/link67-f1-f2"
WPLTO = BUILD / "wplto"
FINAL = BUILD / "final"
ARTIFACTS = BUILD / "artifacts"
RECEIPTS = BUILD / "receipts"
MANIFEST = BUILD / "canonical-product-manifest.json"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
HALT2 = EVIDENCE / "c2.2-phase-f-halt2-review-receipt.json"
F1_RECEIPT = EVIDENCE / "c2.2-f1-published-value-call-wplto-receipt.json"
F2_RECEIPT = EVIDENCE / "c2.2-f2-bitops-wplto-receipt.json"
RECEIPT = EVIDENCE / "c2.2-product-link67-f1-f2-structural-receipt.json"
FIRST_RED = EVIDENCE / (
    "c2.2-product-link67-f1-f2-artifact-completion-first-red.json")


class LinkError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise LinkError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"Link-67 authority absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def configure() -> None:
    """Bind the accepted F2 static plane to a fresh product-link directory."""
    F2_WPLTO.configure()
    CAN.BUILD = BUILD
    CAN.WPLTO = WPLTO
    CAN.FINAL = FINAL
    CAN.ARTIFACTS = ARTIFACTS
    CAN.RECEIPTS = RECEIPTS
    CAN.MANIFEST = MANIFEST
    F2_WPLTO.F1W.BUILD = BUILD
    F2_WPLTO.F1W.WPLTO = WPLTO
    F2_WPLTO.F1W.RECEIPTS = RECEIPTS
    F2_WPLTO.F1W.STATIC_RECEIPT = (
        RECEIPTS / "f2-static-plane-authority.json")
    os.environ.update(CAN.canonical_build_environment())


def source_gates() -> dict[str, Any]:
    f1_bundle = F1_GATE.bundle()
    f1 = F1_GATE.validate_source(f1_bundle)
    f1["mutations_rejected"] = F1_GATE.mutation_tests(f1_bundle)
    f1_execution = F1_GATE.executable_fixtures()
    f2_bundle = F2_GATE.bundle()
    f2 = F2_GATE.validate(f2_bundle)
    f2["mutations_rejected"] = F2_GATE.mutation_tests(f2_bundle)
    f2_execution = F2_GATE.executable_fixtures()
    emission = F2_WPLTO.emission_gate()
    require(
        f1["status"] == "passed-exact-published-value-call-source-contract"
        and f1["mutations_rejected"] == 10
        and f1_execution["fixture_count"] == 18
        and f2["status"] == "passed-all-eight-ABI-and-source-views"
        and f2["mutations_rejected"] == 16
        and f2_execution["positive_count"] == 28
        and f2_execution["negative_count"] == 8
        and emission["bank2_static_code_bytes"] == 34990
        and emission["entries"] == 602
        and emission["resolutions"] == 2299
        and emission["roots"] == 283,
        "Link-67 F1/F2 source, execution or emission gate red",
    )
    return {
        "F1": {"source": f1, "execution": f1_execution},
        "F2": {
            "source": f2,
            "execution": f2_execution,
            "emission": emission,
        },
    }


def halt2_gate() -> dict[str, Any]:
    halt = load(HALT2)
    require(
        halt["status"] == "Class-C-halt-2-owner-approved"
        and halt["result"]["recommended_link"] == ["F1", "F2"]
        and halt["result"]["parked"] == ["F3"]
        and halt["result"]["paper_only"] == ["F5"]
        and halt["result"]["product_links_so_far"] == 0
        and halt["result"]["hardware_runs_so_far"] == 0,
        "Link-67 lacks the exact Halt-2 owner approval",
    )
    return halt


def complete_in_fresh_process() -> None:
    environment = os.environ.copy()
    environment.update(CAN.canonical_build_environment())
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "_complete"],
        cwd=ROOT, env=environment, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(
        result.returncode == 0,
        "Link-67 artifact-side completion failed:\n" + result.stdout)
    (RECEIPTS / "artifact-completion.log").write_text(
        result.stdout, encoding="utf-8")


def complete_action() -> int:
    configure()
    replay = CAN.REPLAY
    original_configure = replay.configure

    def configure_link67_geometry() -> None:
        # The historical Link-64 replay pins $B972.  F1+F2 deterministically
        # moved the current verifier table to $B98A, already proven by the
        # approved WPLTO.  Reuse every current v4/two-region selector while
        # checking the post-promotion pin instead of resurrecting Link 64.
        replay.PROFILE.configure()
        replay.BANK2.configure_bank2_stage()
        replay.TWO.configure_two_region()
        replay.LINK60.configure_current_pin_adapters()
        replay.P.PRODUCT_ARTIFACTS_MANIFEST = (
            CAN.STATIC_PRODUCT / "substitution-artifacts.json")
        require(
            replay.P.RUNTIME_OVERLAY_FORMAT_VERSION == 4
            and replay.P.VERIFIER_BINDING_BASE
                == replay.P.LINK60_VERIFIER_BINDING_BASE == 0xB98A
            and replay.P.runtime_binding_bytes() == 40
            and replay.P.total_publish_last_bytes() == 42
            and replay.P.FIXED_BANK0_HOT_BSS_BASE == 0xC25D
            and replay.P.fixed_bank0_contract_end() == 0xC354,
            "Link-67 artifact replay current geometry drift")

    replay.configure = configure_link67_geometry
    try:
        completion = CAN.complete_artifacts()
    finally:
        replay.configure = original_configure
    require(
        completion["status"]
        == "passed-no-relink-publish-last-artifact-completion"
        and completion["compiler_runs"] == 0
        and completion["linker_runs"] == 0,
        "Link-67 post-link completion was not artifact-only",
    )
    print(
        "c2-phase-f-link67: ARTIFACT COMPLETION PASS "
        f"product={completion['product']['sha256']} "
        "compiler=0 linker=0")
    return 0


def existing_wplto() -> dict[str, Any]:
    internal = load(RECEIPTS / "wplto-internal.json")
    replacement = internal["fresh_replacement_gates"]
    require(
        internal["status"]
            == "passed-new-c2-lite-real-abi-identity-hardware-not-run"
        and (WPLTO / "lisp65-c2-substitution-linked.prg").is_file()
        and (WPLTO / "lisp65-c2-substitution-linked.prg.elf").is_file()
        and replacement["status"] == "passed",
        "Link-67 resume lacks its complete green WPLTO closure")
    return {
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


def emitted_library(path: Path) -> Path:
    suffix = ".manifest.json"
    require(path.as_posix().endswith(suffix),
            f"unexpected static manifest name: {path}")
    return Path(path.as_posix()[:-len(suffix)] + ".ext.bin")


def build_manifest(static: dict[str, Any], wplto: dict[str, Any],
                   completion: dict[str, Any]) -> dict[str, Any]:
    """Write the canonical role set from the accepted F2 emitter paths."""
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    product = FINAL / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    profile = FINAL / "resolved-profile.txt"
    bootstage, bootstage_geometry = CAN.build_boot_stage(elf, profile)
    libraries = [
        emitted_library(F2_WPLTO.SPECS[index][2])
        for index in (1, 2, 3)
    ]
    rows = [
        bind(elf) | {"role": "linked-product-elf"},
        bind(product) | {"role": "c2-resident-prg"},
        bind(FINAL / (
            "fresh-c2-lite-prelink-gates/v6-semantics/"
            "bank2-static-code.bin")) | {
                "role": "c2-bank2-static-code-plane"},
        bind(FINAL / (
            "fresh-c2-lite-prelink-gates/v6-semantics/"
            "initial.c2d-v6.bin")) | {"role": "c2d-v6-code-plane"},
        bind(bootstage) | {"role": "c2-two-record-boot-stage"},
        bind(FINAL / "runtime-overlays-session-final.bin") | {
            "role": "c2-session-family-region-0"},
        bind(F2_WPLTO.PRODUCT / "product-shelf-v4-direct.bin") | {
            "role": "c2-product-shelf"},
        bind(FINAL / "runtime-overlays-boot-final.bin") | {
            "role": "c2-boot-family"},
        bind(FINAL / "runtime-overlays-session-final-region1.bin") | {
            "role": "c2-session-family-region-1"},
        bind(FINAL / "c2-product-kernal-window.bin") | {
            "role": "c2-kernal-window"},
        bind(profile) | {"role": "resolved-profile"},
        bind(libraries[0]) | {"role": "library-ide"},
        bind(libraries[1]) | {"role": "library-idex"},
        bind(libraries[2]) | {"role": "library-m65d"},
    ]
    value = {
        "format": "lisp65-c2-lite-canonical-product-manifest-v1",
        "status": "passed-fresh-source-product-and-post-link-completion",
        "contract": bind(CAN.CONTRACT),
        "static_plane": static,
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
        "post_promotion_static_paths": {
            "classification": (
                "same six F2 single-emitter specs; no private or second "
                "library build truth"),
            "manifests": [bind(row[2]) for row in F2_WPLTO.SPECS],
        },
    }
    MANIFEST.write_bytes(json_bytes(value))
    return value


def record_final(gates: dict[str, Any], wplto: dict[str, Any],
                 *, artifact_resume: bool) -> int:
    replacement = wplto["historical_checker_boundary"][
        "current_replacement_gates"]
    walls = replacement["walls"]
    capacity = replacement["capacity"]
    completion = load(RECEIPTS / "artifact-completion.json")
    static = {
        "status": "passed-owner-reviewed-F2-single-emitter-static-plane",
        "authority": bind(F2_RECEIPT),
        "bank2_static_code_bytes": 34990,
        "entries": 602,
        "resolutions": 2299,
        "roots": 283,
    }
    manifest = build_manifest(static, wplto, completion)
    checked = CAN.check()
    product = FINAL / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    profile = FINAL / "resolved-profile.txt"
    internal = load(RECEIPTS / "wplto-internal.json")
    product_link = load(FINAL / "product-substitution-link.json")
    require(
        manifest["status"]
            == "passed-fresh-source-product-and-post-link-completion"
        and checked["identity"] == manifest["identity"]
        and internal["status"]
            == "passed-new-c2-lite-real-abi-identity-hardware-not-run"
        and product_link["status"] == "passed"
        and product_link["product_closure_link_count"] == 1
        and completion["product"]["sha256"] == sha(product)
        and completion["elf"]["sha256"] == sha(elf),
        "Link-67 final product or manifest closure red",
    )
    value = {
        "format": "lisp65-c2.2-product-link67-f1-f2-v1",
        "recorded_on": "2026-07-27",
        "status": "passed-Link67-F1-F2-product-identity-hardware-not-run",
        "promotable": False,
        "link_number": LINK_NUMBER,
        "freight": ["F1", "F2"],
        "parked": ["F3"],
        "paper_only": ["F5"],
        "product": bind(product),
        "ELF": bind(elf),
        "profile": bind(profile),
        "manifest": bind(MANIFEST),
        "static_geometry": {
            "bank2_static_code_bytes": 34990,
            "entries": 602,
            "resolutions": 2299,
            "roots": 283,
        },
        "walls": walls | {
            "session_family_headroom_bytes":
                capacity["session_family_headroom_bytes"]
        },
        "gates": {
            "F1": gates["F1"],
            "F2": gates["F2"],
            "WPLTO": wplto["status"],
            "artifact_completion": completion["status"],
            "product_substitution_link": product_link["status"],
            "canonical_manifest": checked["status"],
            "all_green": True,
        },
        "execution_accounting": {
            "whole_program_product_links": 1,
            "resident_island_seed_materializer_links": 1,
            "artifact_completion_resume": artifact_resume,
            "artifact_resume_compiler_runs": 0,
            "artifact_resume_linker_runs": 0,
            "hardware_runs": 0,
        },
        "authority": {
            "Halt_2": bind(HALT2),
            "F1_probe": bind(F1_RECEIPT),
            "F2_probe": bind(F2_RECEIPT),
            "driver": bind(Path(__file__)),
            "WPLTO_internal": bind(RECEIPTS / "wplto-internal.json"),
            "artifact_completion": bind(
                RECEIPTS / "artifact-completion.json"),
        },
        "next_gate": (
            "Bind this exact product/ELF/profile and the device core/tool "
            "identities into the approved 12-row F4 S1 session, then request "
            "the single hardware start."
        ),
        "claim_limit": (
            "Structurally complete F1+F2 Link 67 only. S1 hardware behavior, "
            "latency, bitops-on-metal, promotion and release remain unclaimed."
        ),
    }
    if FIRST_RED.is_file():
        value["authority"]["artifact_completion_first_red"] = bind(FIRST_RED)
    RECEIPT.write_bytes(json_bytes(value))
    print(
        "c2-phase-f-link67: PASS "
        f"product={sha(product)} bank2=34990 text=90 e000=151 "
        "island=69 session=610 hardware=not-run")
    return 0


def link_action() -> int:
    require(not BUILD.exists() and not RECEIPT.exists(),
            "Link-67 is one-shot and already has output")
    halt2_gate()
    gates = source_gates()
    configure()
    BUILD.mkdir(parents=True)
    wplto = CAN.run_wplto()
    replacement = wplto["historical_checker_boundary"][
        "current_replacement_gates"]
    walls = replacement["walls"]
    capacity = replacement["capacity"]
    require(
        wplto["status"].startswith("passed-one-current-WPLTO-closure")
        and walls == {
            "bank0_text_headroom_bytes": 90,
            "e000_headroom_bytes": 151,
            "fixed_hot_block_headroom_bytes": 2,
            "ordinary_bank0_bss_headroom_bytes": 137,
            "resident_island_headroom_bytes": 69,
        }
        and capacity["session_family_headroom_bytes"] == 610,
        "Link-67 WPLTO walls differ from the approved F2 map",
    )
    complete_in_fresh_process()
    return record_final(gates, wplto, artifact_resume=False)


def resume_action() -> int:
    require(BUILD.is_dir() and not RECEIPT.exists(),
            "Link-67 artifact resume requires one unfinished link")
    halt2_gate()
    gates = source_gates()
    configure()
    wplto = existing_wplto()
    product = WPLTO / "lisp65-c2-substitution-linked.prg"
    first_red = {
        "format": "lisp65-c2.2-link67-artifact-completion-first-red-v1",
        "recorded_on": "2026-07-27",
        "status": "FIRST RED: post-link artifact completion used Link-64 pin",
        "classification": "Class-A replay-configuration-only",
        "product_bytes_changed": 0,
        "new_compiler_runs": 0,
        "new_linker_runs": 0,
        "linked_product": bind(product),
        "diagnosis": (
            "The fresh-process completion restored v4/two-region geometry "
            "but its historical assertion required verifier pin $B972. "
            "The approved F1+F2 link deterministically uses current pin "
            "$B98A. The product link and publish-last bytes were already "
            "complete; only the read-only completion model stopped. After "
            "that correction, the generic manifest writer still addressed "
            "IDE/IDEX/M65D through the promoted canonical static root rather "
            "than the already bound F2 emitter specs."
        ),
        "repair": (
            "Reuse the current v4/two-region selectors and assert $B98A "
            "before artifact-only completion; construct the canonical role "
            "manifest from the exact F2 spec paths; do not compile or relink."
        ),
        "tool_first_red_count": 2,
    }
    FIRST_RED.write_bytes(json_bytes(first_red))
    if FINAL.exists():
        CAN.make_writable(FINAL)
        shutil.rmtree(FINAL)
    if ARTIFACTS.exists():
        CAN.make_writable(ARTIFACTS)
        shutil.rmtree(ARTIFACTS)
    if MANIFEST.exists():
        MANIFEST.unlink()
    completion_receipt = RECEIPTS / "artifact-completion.json"
    if completion_receipt.exists():
        completion_receipt.unlink()
    complete_in_fresh_process()
    return record_final(gates, wplto, artifact_resume=True)


def main() -> int:
    action = sys.argv[1:] or ["link"]
    require(action in (["link"], ["resume"], ["_complete"]),
            "usage: c2_phase_f_f1_f2_successor_link.py "
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
        LinkError, CAN.CanonicalError, F1_GATE.GateError,
        F2_GATE.GateError, OSError, ValueError, KeyError,
        json.JSONDecodeError, subprocess.SubprocessError,
    ) as error:
        print("c2-phase-f-link67: FIRST RED: " + str(error), file=sys.stderr)
        raise SystemExit(2)
