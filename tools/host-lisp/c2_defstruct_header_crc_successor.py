#!/usr/bin/env python3
"""Qualify and link the Link-69 L65I header-CRC hardware First Red."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_defstruct_foundations_wplto as PROBE  # noqa: E402
import c2_defstruct_successor_link69 as L69  # noqa: E402
import c2_intern_session_service_gate as SERVICE  # noqa: E402
import c2_lite_canonical_product as CAN  # noqa: E402
import c2_require_resolver_gate as RESOLVER  # noqa: E402


LINK = 70
EXPECTED_STATIC = 40243
EXPECTED_RESOLUTIONS = 2677
ROOT_BUILD = ROOT / "build/post-promotion/link70-defstruct-header-crc"
PROBE_BUILD = ROOT_BUILD / "product-shaped-probe"
LINK_BUILD = ROOT_BUILD
WPLTO_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link70-defstruct-header-crc-wplto-receipt.json")
LINK_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link70-defstruct-header-crc-structural-receipt.json")
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link69-require-header-crc-hardware-first-red.json")
LINK69 = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link69-defstruct-foundations-structural-receipt.json")
EVIDENCE = WPLTO_RECEIPT.parent
DRIVER = Path(__file__).resolve()


class SuccessorError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SuccessorError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")


def paths(build: Path) -> dict[str, Path]:
    return {
        "base": build / "static-plane",
        "static": build / "static-plane/narrow-static",
        "static_product": build / "static-plane/narrow-static/product",
        "v6": build / "static-plane/narrow-static/v6-semantics",
        "build": build,
        "wplto": build / "wplto",
        "final": build / "final",
        "artifacts": build / "artifacts",
        "receipts": build / "receipts",
        "manifest": build / "canonical-product-manifest.json",
    }


def configure(build: Path) -> dict[str, Path]:
    p = paths(build)
    PROBE.BASE = p["base"]
    PROBE.STATIC = p["static"]
    PROBE.STATIC_PRODUCT = p["static_product"]
    PROBE.V6 = p["v6"]
    PROBE.BUILD = p["build"]
    PROBE.WPLTO = p["wplto"]
    PROBE.RECEIPTS = p["receipts"]
    PROBE.STATIC_RECEIPT = (
        p["receipts"] / "defstruct-static-plane-authority.json")
    PROBE.configure()
    # The canonical-domain correction remains Bank-2-only and changes no
    # resident geometry.  Successor wrappers bind the measured static size.
    PROBE.REQ.EXPECTED_STATIC = EXPECTED_STATIC
    PROBE.REQ.F1W.EXPECTED_STATIC = EXPECTED_STATIC
    PROBE.REQ.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    PROBE.REQ.F1W.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    CAN.BUILD = p["build"]
    CAN.WPLTO = p["wplto"]
    CAN.FINAL = p["final"]
    CAN.ARTIFACTS = p["artifacts"]
    CAN.RECEIPTS = p["receipts"]
    CAN.MANIFEST = p["manifest"]
    base = L69.BASE
    for name, value in {
        "LINK": LINK,
        "BUILD": p["build"],
        "WPLTO": p["wplto"],
        "FINAL": p["final"],
        "ARTIFACTS": p["artifacts"],
        "RECEIPTS": p["receipts"],
        "MANIFEST": p["manifest"],
        "RECEIPT": LINK_RECEIPT,
    }.items():
        setattr(base, name, value)
    os.environ.update(CAN.canonical_build_environment())
    return p


def fix_gates() -> dict[str, Any]:
    source = RESOLVER.source_gate()
    source_mutations = RESOLVER.source_mutations()
    rows: list[dict[str, Any]] = []
    artifacts: dict[str, bytes] = {}
    for ordinal, (name, manifest, dependencies) in enumerate(
            RESOLVER.LIBRARIES):
        row, artifact = RESOLVER.measured_row(
            name, manifest, dependencies, 1, ordinal + 1)
        rows.append(row)
        artifacts[name] = artifact
    media_mutations = RESOLVER.mutation_gate(
        RESOLVER.encode_index(rows), artifacts)
    require(
        source["status"].startswith("passed-")
        # The require idempotence fastpath added four permanent source
        # directions to the original 30 header/reader mutations.  Option A
        # adds the persistent-row size proof and the non-index acceptance
        # direction.  This inherited gate must count the current suite rather
        # than silently excluding either contract correction.
        and len(source_mutations) == 36
        and {
            "header-record-crc-low-omitted",
            "header-record-crc-high-omitted",
            "header-version-omitted",
            "header-width-omitted",
            "row-width-omitted",
            "dependency-width-omitted",
            "row-count-omitted",
            "persistent-row-size-removed",
            "ordinary-persistent-row-rejected",
            "leaf-length-high-Z-nonzero",
        }.issubset(source_mutations)
        and len(media_mutations) == 32
        and {
            "header-seal-omits-record-crc-fields",
            "header-seal-magic-record-crc-identity-only",
            "header-seal-magic-identity-only",
        }.issubset(media_mutations),
        "header-CRC fix or permanent negative fixtures red")
    compile_result = subprocess.run(
        [
            sys.executable, "tools/host-lisp/bytecode_p0_stdlib.py",
            "--check",
            "tests/bytecode/libs/p0-stdlib-require-resolver.json",
        ],
        cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    require(
        compile_result.returncode == 0
        and "bytecode-p0-stdlib-check: PASS" in compile_result.stdout,
        "target resolver compile red:\n" + compile_result.stdout)
    return {
        "source": source,
        "source_mutations_rejected": source_mutations,
        "media_mutations_rejected": media_mutations,
        "target_compile": compile_result.stdout.strip(),
        "fix": {
            "field": "L65I-v1 canonical header CRC16 over bytes 0..16",
            "old_reader": "%l65i-next-byte",
            "new_reader": "%l65i-next-crc",
            "changed_calls_from_link_69": 7,
            "changed_calls_from_predecessor": 5,
            "format_delta_bytes": 0,
            "media_delta_bytes": 0,
        },
    }


def run_wplto(build: Path) -> tuple[dict[str, Path], dict[str, Any]]:
    p = configure(build)
    static = PROBE.REQ.build_static_plane()
    build.mkdir(parents=True, exist_ok=True)
    plane = PROBE.REQ.F1W.static_gate()
    wplto = CAN.run_wplto()
    replacement = wplto["historical_checker_boundary"][
        "current_replacement_gates"]
    walls = replacement["walls"]
    capacity = replacement["capacity"]
    session = PROBE.service_manifest_gate()
    linked = SERVICE.linked_gate(
        p["wplto"] / "lisp65-c2-substitution-linked.prg.elf",
        p["wplto"] / "runtime-overlays-session-final.json",
        p["wplto"] / "runtime-overlays-boot-final.json")
    require(
        static["semantics"]["code_bytes"] == EXPECTED_STATIC
        and plane["static_code_bytes"] == EXPECTED_STATIC
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] >= 54
        and capacity["session_family_headroom_bytes"] >= 0
        and session["new_records"] == 1
        and linked["slot"] == 51,
        "header-CRC successor crossed a product wall")
    return p, {
        "static": static,
        "plane": plane,
        "wplto": wplto,
        "walls": walls,
        "capacity": capacity,
        "session": session,
        "linked_service": linked,
    }


def probe_action() -> int:
    require(
        not PROBE_BUILD.exists() and not WPLTO_RECEIPT.exists(),
        "header-CRC WPLTO is one-shot")
    first_red = load(FIRST_RED)
    require(
        first_red["status"].startswith("FIRST RED")
        and first_red["hardware"]["require_defstruct_result"] == "nil",
        "Link-69 hardware First Red authority drift")
    gates = fix_gates()
    p, result = run_wplto(PROBE_BUILD)
    value = {
        "format": f"lisp65-c2.2-link{LINK}-header-crc-WPLTO-v1",
        "recorded_on": "2026-07-27",
        "status": (
            f"passed-Link{LINK}-header-CRC-fix-product-shaped-WPLTO"),
        "promotable": False,
        "product_links": 0,
        "hardware_runs": 0,
        "first_red": bind(FIRST_RED),
        "fix_gates": gates,
        "static_code_bytes": result["plane"]["static_code_bytes"],
        "walls": result["walls"],
        "capacity": result["capacity"],
        "session_service": result["linked_service"],
        "wplto": result["wplto"],
        "authority": {
            "target_source": bind(ROOT / "lib/stdlib-require.lisp"),
            "resolver_gate": bind(
                ROOT / "tools/host-lisp/c2_require_resolver_gate.py"),
            "linked_ELF": bind(
                p["wplto"] / "lisp65-c2-substitution-linked.prg.elf"),
            "driver": bind(DRIVER),
        },
        "next_gate": "one successor product link, then bundled hardware replay",
        "claim_limit": "Product-shaped capacity only; no Link 70 or hardware claim.",
    }
    write(WPLTO_RECEIPT, value)
    print(
        "c2-defstruct-header-crc: WPLTO PASS "
        f"bank2={value['static_code_bytes']} "
        f"text={value['walls']['bank0_text_headroom_bytes']} "
        f"e000={value['walls']['e000_headroom_bytes']} "
        f"session={value['capacity']['session_family_headroom_bytes']}")
    return 0


def complete_action() -> int:
    p = configure(LINK_BUILD)
    replay = CAN.REPLAY
    original = replay.configure

    def current_geometry() -> None:
        replay.PROFILE.configure()
        replay.BANK2.configure_bank2_stage()
        replay.TWO.configure_two_region()
        replay.LINK60.configure_current_pin_adapters()
        replay.P.configure_intern_session_service()
        replay.P.PRODUCT_ARTIFACTS_MANIFEST = (
            p["static_product"] / "substitution-artifacts.json")
        require(
            replay.P.RUNTIME_OVERLAY_FORMAT_VERSION == 4
            and replay.P.VERIFIER_BINDING_BASE
                == replay.P.LINK60_VERIFIER_BINDING_BASE == 0xB98A
            and replay.P.PROFILE_RODATA_BYTES == 348
            and replay.P.runtime_binding_bytes() == 40
            and replay.P.total_publish_last_bytes() == 42
            and replay.P.INTERN_SESSION_SERVICE,
            "Link-70 artifact completion geometry drift")

    replay.configure = current_geometry
    try:
        completion = CAN.complete_artifacts()
    finally:
        replay.configure = original
    require(
        completion["status"]
            == "passed-no-relink-publish-last-artifact-completion"
        and completion["compiler_runs"] == completion["linker_runs"] == 0,
        "Link-70 artifact completion red")
    return 0


def fresh_completion() -> None:
    result = subprocess.run(
        [sys.executable, str(DRIVER), "_complete"],
        cwd=ROOT, env=os.environ.copy(), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(
        result.returncode == 0,
        "Link-70 fresh-process completion red:\n" + result.stdout)
    paths(LINK_BUILD)["receipts"].mkdir(parents=True, exist_ok=True)
    (paths(LINK_BUILD)["receipts"] / "artifact-completion.log").write_text(
        result.stdout, encoding="utf-8")


def link_action() -> int:
    require(
        WPLTO_RECEIPT.is_file()
        and not LINK_RECEIPT.exists(),
        "Link-70 prerequisites or one-shot boundary red")
    authority = load(WPLTO_RECEIPT)
    p = paths(LINK_BUILD)
    if not p["wplto"].exists():
        gates = fix_gates()
        p, result = run_wplto(LINK_BUILD)
        require(
            result["walls"] == authority["walls"]
            and result["capacity"] == authority["capacity"]
            and result["plane"]["static_code_bytes"]
                == authority["static_code_bytes"],
            "Link-70 fresh WPLTO differs from accepted probe")
        fresh_completion()
    else:
        # The first receipt pass used the wrong descriptive key after the
        # one and only link had completed.  Resume only from the bound WPLTO
        # and artifact-completion receipts; never call the linker again.
        require(
            p["final"].is_dir()
            and (p["receipts"] / "artifact-completion.json").is_file()
            and (p["receipts"] / "wplto-internal.json").is_file(),
            "Link-70 artifact-side resume lacks bound truth")
        configure(LINK_BUILD)
        gates = fix_gates()
        internal = load(p["receipts"] / "wplto-internal.json")
        replacement = internal["fresh_replacement_gates"]
        wplto = {
            "status":
                "passed-one-current-WPLTO-closure-at-typed-historical-"
                "qualification-boundary",
            "publish_last_authority":
                f"0x{CAN.PRODUCT.LINK60_VERIFIER_BINDING_BASE:04x}",
            "historical_profile_label":
                "0xb94e retained only inside the sealed legacy profile text",
            "historical_checker_boundary": {
                "classification":
                    "qualification-model-only-not-a-product-or-link-red",
                "raw_status": load(
                    p["receipts"] / "wplto-raw.json")["status"],
                "raw_error": load(
                    p["receipts"] / "wplto-raw.json")["error"],
                "captured_driver_log": bind(
                    p["receipts"] / "wplto-historical-driver.log"),
                "current_replacement_gates": replacement,
            },
            "qualification": bind(
                p["receipts"] / "wplto-qualification.json"),
            "linked_gate": bind(
                p["receipts"] / "single-submit-linked-gates.json"),
        }
        result = {
            "wplto": wplto,
            "walls": replacement["walls"],
            "capacity": replacement["capacity"],
            "linked_service": SERVICE.linked_gate(
                p["wplto"] / "lisp65-c2-substitution-linked.prg.elf",
                p["wplto"] / "runtime-overlays-session-final.json",
                p["wplto"] / "runtime-overlays-boot-final.json"),
        }
        require(
            result["walls"] == authority["walls"]
            and result["capacity"] == authority["capacity"],
            "Link-70 artifact-side resume differs from accepted probe")
    completion = load(p["receipts"] / "artifact-completion.json")
    manifest = L69.BASE.build_manifest(result["wplto"], completion)
    manifest["static_plane"]["status"] = (
        "passed-defstruct-header-CRC-successor-single-emitter-static-plane")
    manifest["static_plane"]["intern_prim_id"] = 68
    manifest["session_service"] = {
        "name": "intern-session-service",
        "slot": 51,
        "bytes": result["linked_service"]["slice_bytes"],
        "catalog_records": 52,
    }
    write(p["manifest"], manifest)
    checked = CAN.check()
    product = p["final"] / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    product_link = load(p["final"] / "product-substitution-link.json")
    session = load(p["final"] / "runtime-overlays-session-final.json")
    service = SERVICE.linked_gate(
        elf,
        p["final"] / "runtime-overlays-session-final.json",
        p["final"] / "runtime-overlays-boot-final.json")
    require(
        checked["identity"] == manifest["identity"]
        and product_link["status"] == "passed"
        and completion["product"]["sha256"] == sha(product)
        and session["storage"]["size"] == 65423
        and service["slot"] == 51,
        "Link-70 completed product closure red")
    value = {
        "format": (
            f"lisp65-c2.2-product-link{LINK}-header-crc-successor-v1"),
        "recorded_on": "2026-07-27",
        "status": (
            f"passed-Link{LINK}-header-CRC-successor-hardware-not-run"),
        "promotable": False,
        "link_number": LINK,
        "predecessor": bind(LINK69),
        "qualified_WPLTO": bind(WPLTO_RECEIPT),
        "product": bind(product),
        "ELF": bind(elf),
        "manifest": bind(p["manifest"]),
        "walls": result["walls"] | {
            "session_family_headroom_bytes":
                result["capacity"]["session_family_headroom_bytes"]},
        "session_service": service,
        "fix_gates": gates,
        "execution_accounting": {
            "whole_program_product_links": 1,
            "artifact_completion_compiler_runs": 0,
            "artifact_completion_linker_runs": 0,
            "hardware_runs": 0,
        },
        "authority": {
            "WPLTO_internal": bind(p["receipts"] / "wplto-internal.json"),
            "artifact_completion": bind(
                p["receipts"] / "artifact-completion.json"),
            "driver": bind(DRIVER),
        },
        "next_gate": (
            "Bundled hardware replay: require defstruct, construct/access/"
            "mutate a point, same-generation require idempotence, and busy "
            "Session-service fail-closed window identity."),
        "claim_limit": (
            f"Link {LINK} structural completion only; hardware unclaimed."),
    }
    write(LINK_RECEIPT, value)
    print(
        f"c2-defstruct-header-crc: LINK {LINK} PASS "
        f"product={sha(product)} bank2={authority['static_code_bytes']} "
        f"text={result['walls']['bank0_text_headroom_bytes']} "
        f"e000={result['walls']['e000_headroom_bytes']} "
        f"session={result['capacity']['session_family_headroom_bytes']}")
    return 0


def main() -> int:
    action = sys.argv[1:] or ["probe"]
    require(
        action in (["probe"], ["link"], ["_complete"]),
        "usage: c2_defstruct_header_crc_successor.py [probe|link|_complete]")
    if action == ["probe"]:
        return probe_action()
    if action == ["link"]:
        return link_action()
    return complete_action()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        SuccessorError, PROBE.ProbeError, CAN.CanonicalError,
        SERVICE.GateError, SERVICE.ElfTruthError, OSError, ValueError,
        KeyError, json.JSONDecodeError, subprocess.SubprocessError,
    ) as error:
        print("c2-defstruct-header-crc: FIRST RED: " + str(error),
              file=sys.stderr)
        raise SystemExit(2)
