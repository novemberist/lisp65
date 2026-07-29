#!/usr/bin/env python3
"""Build the accepted defstruct-foundation successor as product Link 69."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_defstruct_foundations_wplto as PROBE  # noqa: E402
import c2_intern_session_service_gate as SERVICE  # noqa: E402
import c2_lite_canonical_product as CAN  # noqa: E402
import c2_require_resolver_successor_link68 as BASE  # noqa: E402


LINK = 69
BUILD = ROOT / "build/post-promotion/link69-defstruct-foundations"
WPLTO = BUILD / "wplto"
FINAL = BUILD / "final"
ARTIFACTS = BUILD / "artifacts"
RECEIPTS = BUILD / "receipts"
MANIFEST = BUILD / "canonical-product-manifest.json"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
AUTHORITY = EVIDENCE / "c2.2-defstruct-foundations-wplto-receipt.json"
FOUNDATIONS = EVIDENCE / "c2.2-defstruct-foundations-gate-receipt.json"
RECEIPT = EVIDENCE / (
    "c2.2-product-link69-defstruct-foundations-structural-receipt.json")


class LinkError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise LinkError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path, role: str | None = None) -> dict[str, Any]:
    require(path.is_file(), f"Link-69 artifact absent: {path}")
    row: dict[str, Any] = {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": BASE.sha(path),
    }
    if role is not None:
        row["role"] = role
    return row


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")


def configure() -> None:
    PROBE.BUILD = BUILD
    PROBE.WPLTO = WPLTO
    PROBE.RECEIPTS = RECEIPTS
    PROBE.STATIC_RECEIPT = (
        RECEIPTS / "defstruct-static-plane-authority.json")
    PROBE.configure()
    CAN.BUILD = BUILD
    CAN.WPLTO = WPLTO
    CAN.FINAL = FINAL
    CAN.ARTIFACTS = ARTIFACTS
    CAN.RECEIPTS = RECEIPTS
    CAN.MANIFEST = MANIFEST
    for name, value in {
        "LINK": LINK,
        "BUILD": BUILD,
        "WPLTO": WPLTO,
        "FINAL": FINAL,
        "ARTIFACTS": ARTIFACTS,
        "RECEIPTS": RECEIPTS,
        "MANIFEST": MANIFEST,
        "AUTHORITY": AUTHORITY,
        "RECEIPT": RECEIPT,
    }.items():
        setattr(BASE, name, value)
    os.environ.update(CAN.canonical_build_environment())


def accepted_authority() -> dict[str, Any]:
    authority = load(AUTHORITY)
    require(
        authority["status"]
            == "passed-defstruct-foundations-product-shaped-WPLTO"
        and authority["freight"]["bank2_bytes"] == 40241
        and authority["freight"]["bank2_delta_from_Link68"] == 0
        and authority["freight"]["new_session_records"] == 1
        and authority["freight"]["session_slice_delta_bytes"] == 399
        and authority["walls"] == {
            "bank0_text_headroom_bytes": 351,
            "e000_headroom_bytes": 56,
            "fixed_hot_block_headroom_bytes": 2,
            "ordinary_bank0_bss_headroom_bytes": 137,
            "resident_island_headroom_bytes": 61,
        }
        and authority["capacity"]["session_catalog_records"] == 52
        and authority["capacity"]["session_family_bytes"] == 65423
        and authority["capacity"]["session_family_headroom_bytes"] == 113
        and authority["session_service_gate"]["linked"]["slot"] == 51,
        "Link-69 WPLTO authority is not the accepted green map")
    return authority


def source_gates() -> dict[str, Any]:
    foundation = load(FOUNDATIONS)
    commands = (
        ("ABI_ledger", [
            sys.executable, "tools/host-lisp/bytecode_abi_ledger.py",
            "--selftest"]),
        ("native_registry", [
            sys.executable,
            "tools/host-lisp/v2_native_function_registry.py", "check"]),
        ("bytecode_native_drift", [
            sys.executable,
            "tools/host-lisp/bytecode_p0_drift_check.py"]),
    )
    outputs: dict[str, str] = {}
    for name, command in commands:
        result = subprocess.run(
            command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, check=False)
        require(result.returncode == 0,
                f"Link-69 fresh {name} gate red:\n{result.stdout}")
        outputs[name] = result.stdout.strip()
    service = {
        "source": SERVICE.source_gate(),
        "source_mutations_rejected": SERVICE.mutation_gate(),
        "host": SERVICE.host_fixtures(
            BUILD / "session-service-host-gates"),
    }
    require(
        foundation["status"]
            == "passed-intern-canonical-places-and-real-defstruct-media"
        and foundation["intern"]["evaluations"] == 844
        and foundation["places"]["failed_library"].startswith(
            "pending registrations invisible")
        and len(service["source_mutations_rejected"]) == 12,
        "Link-69 foundations or Session-service source gate red")
    return {
        "foundation": foundation,
        "session_service": service,
        **outputs,
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
        replay.P.configure_intern_session_service()
        replay.P.PRODUCT_ARTIFACTS_MANIFEST = (
            PROBE.STATIC_PRODUCT / "substitution-artifacts.json")
        require(
            replay.P.RUNTIME_OVERLAY_FORMAT_VERSION == 4
            and replay.P.VERIFIER_BINDING_BASE
                == replay.P.LINK60_VERIFIER_BINDING_BASE == 0xB98A
            and replay.P.PROFILE_RODATA_BYTES == 348
            and replay.P.runtime_binding_bytes() == 40
            and replay.P.total_publish_last_bytes() == 42
            and replay.P.INTERN_SESSION_SERVICE,
            "Link-69 artifact completion geometry drift")

    replay.configure = current_geometry
    try:
        completion = CAN.complete_artifacts()
    finally:
        replay.configure = original
    require(
        completion["status"]
            == "passed-no-relink-publish-last-artifact-completion"
        and completion["compiler_runs"] == completion["linker_runs"] == 0,
        "Link-69 artifact-side completion red")
    print(
        "c2-defstruct-link69: ARTIFACT COMPLETION PASS "
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
        "Link-69 fresh-process artifact completion red:\n" + result.stdout)
    (RECEIPTS / "artifact-completion.log").write_text(
        result.stdout, encoding="utf-8")


def build_manifest(wplto: dict[str, Any],
                   completion: dict[str, Any]) -> dict[str, Any]:
    value = BASE.build_manifest(wplto, completion)
    value["static_plane"]["status"] = (
        "passed-defstruct-foundations-single-emitter-static-plane")
    value["static_plane"]["intern_prim_id"] = 68
    value["session_service"] = {
        "name": "intern-session-service",
        "slot": 51,
        "bytes": 399,
        "catalog_records": 52,
    }
    write(MANIFEST, value)
    return value


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
    session = load(FINAL / "runtime-overlays-session-final.json")
    service = SERVICE.linked_gate(
        elf,
        FINAL / "runtime-overlays-session-final.json",
        FINAL / "runtime-overlays-boot-final.json")
    require(
        checked["identity"] == manifest["identity"]
        and product_link["status"] == "passed"
        and product_link["product_closure_link_count"] == 1
        and completion["product"]["sha256"] == BASE.sha(product)
        and session["storage"]["size"] == 65423
        and session["catalog"]["slice_count"] == 52
        and service["slot"] == 51,
        "Link-69 completed product closure red")
    value = {
        "format": "lisp65-c2.2-product-link69-defstruct-foundations-v1",
        "recorded_on": "2026-07-27",
        "status":
            "passed-Link69-defstruct-foundations-product-identity-"
            "hardware-not-run",
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
        "session_service": service,
        "gates": {
            "foundations": gates["foundation"]["status"],
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
            "foundation_receipt": bind(FOUNDATIONS),
            "session_service_contract": bind(SERVICE.CONTRACT),
            "WPLTO_internal": bind(RECEIPTS / "wplto-internal.json"),
            "artifact_completion": bind(
                RECEIPTS / "artifact-completion.json"),
            "driver": bind(Path(__file__).resolve()),
        },
        "next_gate": (
            "One bundled hardware session: require defstruct, construct and "
            "read point accessors, mutate through canonical Places, repeat "
            "require in the same generation, and reject a busy service "
            "without changing the runtime window."),
        "claim_limit": (
            "Structurally complete Link 69 only. Require/defstruct hardware "
            "behavior and promotion remain unclaimed."),
    }
    write(RECEIPT, value)
    print(
        "c2-defstruct-link69: PASS "
        f"product={BASE.sha(product)} bank2=40241 "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        f"session={capacity['session_family_headroom_bytes']} "
        "hardware=not-run")
    return 0


def link_action() -> int:
    require(
        not WPLTO.exists() and not FINAL.exists() and not RECEIPT.exists(),
        "Link-69 is one-shot and already has product output")
    authority = accepted_authority()
    configure()
    BUILD.mkdir(parents=True, exist_ok=True)
    gates = source_gates()
    static = PROBE.REQ.build_static_plane()
    plane = PROBE.REQ.F1W.static_gate()
    wplto = CAN.run_wplto()
    replacement = wplto["historical_checker_boundary"][
        "current_replacement_gates"]
    walls = replacement["walls"]
    capacity = replacement["capacity"]
    session = PROBE.service_manifest_gate()
    elf = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
    linked = SERVICE.linked_gate(
        elf,
        WPLTO / "runtime-overlays-session-final.json",
        WPLTO / "runtime-overlays-boot-final.json")
    require(
        static["semantics"]["code_bytes"] == 40241
        and plane["static_code_bytes"] == 40241
        and walls == authority["walls"]
        and capacity["session_family_headroom_bytes"] == 113
        and session["new_records"] == 1
        and session["slice_delta_bytes"] == 399
        and linked["slot"] == 51,
        "Link-69 fresh WPLTO differs from its accepted map")
    complete_in_fresh_process()
    return record_final(authority, gates, wplto)


def main() -> int:
    action = sys.argv[1:] or ["link"]
    require(action in (["link"], ["_complete"]),
            "usage: c2_defstruct_successor_link69.py [link|_complete]")
    if action == ["_complete"]:
        return complete_action()
    return link_action()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        LinkError, PROBE.ProbeError, CAN.CanonicalError, SERVICE.GateError,
        SERVICE.ElfTruthError, OSError, ValueError, KeyError,
        json.JSONDecodeError, subprocess.SubprocessError,
    ) as error:
        print("c2-defstruct-link69: FIRST RED: " + str(error),
              file=sys.stderr)
        raise SystemExit(2)
