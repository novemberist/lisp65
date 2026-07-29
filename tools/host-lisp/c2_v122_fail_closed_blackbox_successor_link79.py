#!/usr/bin/env python3
"""Build the sole owner-authorized fail-closed-blackbox product Link 79."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_v122_fail_closed_blackbox_wplto as BB  # noqa: E402


D1 = BB.D1
V = BB.V
BASE = BB.BASE
BOUND = V.BOUND
LINK = 79
BUILD = ROOT / "build/post-release/link79-fail-closed-blackbox"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
AUTHORITY = EVIDENCE / (
    "c2.2-v1.2.2-fail-closed-blackbox-wplto-receipt.json")
PREDECESSOR = EVIDENCE / (
    "c2.2-product-link78-dirmiss-renderer-structural-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.2-product-link79-fail-closed-blackbox-structural-receipt.json")
FIRST_RED = EVIDENCE / (
    "c2.2-product-link79-fail-closed-blackbox-first-red.json")
DRIVER = Path(__file__).resolve()


class LinkError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise LinkError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def bind(path: Path) -> dict[str, Any]:
    return BASE.bind(path)


def configure() -> dict[str, Path]:
    V.configure_candidate()
    BASE.LINK = LINK
    BASE.EXPECTED_STATIC = V.EXPECTED_STATIC
    BASE.EXPECTED_RESOLUTIONS = V.EXPECTED_RESOLUTIONS
    BASE.ROOT_BUILD = BUILD
    BASE.PROBE_BUILD = BUILD
    BASE.LINK_BUILD = BUILD
    BASE.WPLTO_RECEIPT = AUTHORITY
    BASE.LINK_RECEIPT = RECEIPT
    BASE.LINK69 = PREDECESSOR
    BASE.EVIDENCE = EVIDENCE
    BASE.DRIVER = DRIVER
    paths = BASE.configure(BUILD)
    V.bind_candidate_specs()
    os.environ.update(BASE.CAN.canonical_build_environment())
    return paths


def current_completion() -> int:
    paths = configure()
    replay = BASE.CAN.REPLAY
    original = replay.configure

    def current_geometry() -> None:
        replay.PROFILE.configure()
        replay.BANK2.configure_bank2_stage()
        replay.TWO.configure_two_region()
        replay.LINK60.configure_current_pin_adapters()
        replay.P.configure_intern_session_service()
        replay.P.PRODUCT_ARTIFACTS_MANIFEST = (
            paths["static_product"] / "substitution-artifacts.json")
        require(
            replay.P.RUNTIME_OVERLAY_FORMAT_VERSION == 4
            and replay.P.VERIFIER_BINDING_BASE
                == replay.P.LINK60_VERIFIER_BINDING_BASE == 0xB98A
            and replay.P.PROFILE_RODATA_BYTES == 348
            and replay.P.runtime_binding_bytes() == 40
            and replay.P.total_publish_last_bytes() == 42
            and replay.P.INTERN_SESSION_SERVICE,
            "Link-79 artifact-completion geometry drift",
        )

    replay.configure = current_geometry
    try:
        completion = BASE.CAN.complete_artifacts()
    finally:
        replay.configure = original
    require(
        completion["status"]
            == "passed-no-relink-publish-last-artifact-completion"
        and completion["compiler_runs"] == completion["linker_runs"] == 0,
        "Link-79 artifact completion red",
    )
    print(
        "c2-v1.2.2-link79: ARTIFACT COMPLETION PASS "
        f"product={completion['product']['sha256']} compiler=0 linker=0"
    )
    return 0


def complete_in_fresh_process() -> None:
    result = subprocess.run(
        [sys.executable, str(DRIVER), "_complete"],
        cwd=ROOT,
        env=os.environ.copy() | BASE.CAN.canonical_build_environment(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    require(
        result.returncode == 0,
        "Link-79 fresh-process artifact completion red:\n" + result.stdout,
    )
    paths = BASE.paths(BUILD)
    paths["receipts"].mkdir(parents=True, exist_ok=True)
    (paths["receipts"] / "artifact-completion.log").write_text(
        result.stdout, encoding="utf-8")


def build_manifest(
    wplto: dict[str, Any],
    completion: dict[str, Any],
) -> dict[str, Any]:
    value = BASE.L69.BASE.build_manifest(wplto, completion)
    value["static_plane"].update({
        "status":
            "passed-v1.2.1-random-while-static-plane-with-D1-and-blackbox",
        "bank2_static_code_bytes": V.EXPECTED_STATIC,
        "entries": V.EXPECTED_ENTRIES,
        "resolutions": V.EXPECTED_RESOLUTIONS,
        "roots": V.EXPECTED_ROOTS,
        "direct_entry_refs": V.EXPECTED_DIRECT_REFS,
        "product_build_id": V.EXPECTED_PRODUCT_ID,
        "bank2_sha256": V.EXPECTED_BANK2_SHA,
        "compiler_carrier": bind(V.WHILE_MANIFEST),
        "random_manifest": bind(V.RANDOM_MANIFEST),
        "while_manifest": bind(V.WHILE_MANIFEST),
    })
    value["session_service"] = {
        "name": "intern-session-service",
        "slot": 51,
        "bytes": 399,
        "catalog_records": 52,
    }
    value["v1.2.2_D1"] = {
        "feature": "full DIRMISS symbol rendering",
        "error_renderer_bytes": D1.EXPECTED_L65E_BYTES,
        "resident_delta_bytes": 0,
        "bank2_delta_bytes": 0,
    }
    value["fail_closed_blackbox"] = {
        "reason_code": "0xb2",
        "visible_code": "F2",
        "window_state_growth_bytes": 0,
        "terminal_only": True,
        "authority": bind(AUTHORITY),
    }
    write(BASE.paths(BUILD)["manifest"], value)
    return value


def link_action() -> int:
    require(
        not BUILD.exists() and not RECEIPT.exists()
        and not FIRST_RED.exists(),
        "Link-79 is a one-shot successor product link",
    )
    authority = load(AUTHORITY)
    predecessor = load(PREDECESSOR)
    require(
        authority.get("status")
            == "passed-one-fail-closed-blackbox-WPLTO"
        and authority.get("wplto_probes_consumed") == 1
        and authority.get("product_links") == 0
        and authority.get("hardware_runs") == 0
        and predecessor.get("status")
            == "passed-Link78-D1-renderer-hardware-not-run",
        "blackbox WPLTO or Link-78 predecessor authority drift",
    )
    source = BB.BLACKBOX.SOURCE.read_text(encoding="ascii")
    source_gate = BB.BLACKBOX.source_gate(source)
    mutations = BB.BLACKBOX.mutation_gate(source)
    D1.dirmiss_host_gate()
    V.feature_gates()
    paths = configure()
    static = BASE.PROBE.REQ.build_static_plane()
    plane = BASE.PROBE.REQ.F1W.static_gate()
    product_path = paths["static_product"] / "substitution-artifacts.json"
    product_identity = load(product_path)
    inherited = V.inherited_gates()
    product_binding = BOUND.product_manifest_gate(
        product_path, V.WHILE_MANIFEST)
    require(
        static["semantics"]["code_bytes"] == V.EXPECTED_STATIC
        and plane["static_code_bytes"] == V.EXPECTED_STATIC
        and product_identity["product_build_id_hex"] == V.EXPECTED_PRODUCT_ID
        and product_identity["entries"] == V.EXPECTED_ENTRIES
        and product_identity["resolutions"] == V.EXPECTED_RESOLUTIONS
        and product_identity["roots"] == V.EXPECTED_ROOTS,
        "Link-79 prelink static-plane identity drift",
    )

    # The sole successor product-link invocation authorized by the owner.
    wplto = BASE.CAN.run_wplto()
    replacement = wplto["historical_checker_boundary"][
        "current_replacement_gates"]
    walls = replacement["walls"]
    capacity = replacement["capacity"]
    require(
        walls == authority["walls"]
        and capacity == authority["capacity"]
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] >= 54
        and capacity["session_family_headroom_bytes"] >= 0,
        "Link-79 differs from the accepted blackbox card",
    )
    wplto_elf = (
        paths["wplto"] / "lisp65-c2-substitution-linked.prg.elf")
    wplto_blackbox = BB.BLACKBOX.linked_gate(
        wplto_elf, BB.BLACKBOX.PREDECESSOR)
    wplto_renderer = D1.linked_renderer_gate(wplto_elf)

    complete_in_fresh_process()
    paths = BASE.paths(BUILD)
    completion = load(paths["receipts"] / "artifact-completion.json")
    manifest = build_manifest(wplto, completion)
    checked = BASE.CAN.check()
    product = paths["final"] / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    profile = paths["final"] / "resolved-profile.txt"
    product_link = load(
        paths["final"] / "product-substitution-link.json")
    final_blackbox = BB.BLACKBOX.linked_gate(
        elf, BB.BLACKBOX.PREDECESSOR)
    final_renderer = D1.linked_renderer_gate(elf)
    service = BASE.SERVICE.linked_gate(
        elf,
        paths["final"] / "runtime-overlays-session-final.json",
        paths["final"] / "runtime-overlays-boot-final.json",
    )
    irq_path = paths["receipts"] / "interrupt-ownership-final-replay.json"
    irq = V.LINK76.IRQ.audit(elf=elf)
    write(irq_path, irq)
    final_binding_path = (
        paths["receipts"] / "bound-artifact-source-parity-final.json")
    final_binding = V.LINK76.PREV.bound_gate(
        product_path, final_binding_path)
    carrier, suite, source = BOUND.source_binding_gate(
        V.WHILE_MANIFEST, V.WHILE_TIER)
    bound_execution = BOUND.execute_bound_cases(
        V.WHILE_MANIFEST, carrier, suite, require_while=True)
    final_bank2 = (
        paths["final"] / "fresh-c2-lite-prelink-gates/v6-semantics/"
        "bank2-static-code.bin")
    require(
        checked["identity"] == manifest["identity"]
        and product_link["status"] == "passed"
        and product_link["product_closure_link_count"] == 1
        and completion["product"]["sha256"] == BASE.sha(product)
        and completion["elf"]["sha256"] == BASE.sha(elf)
        and BASE.sha(final_bank2) == V.EXPECTED_BANK2_SHA
        and service["slot"] == 51
        and irq["mutations"]["rejected"]
            == irq["mutations"]["total"] == 16
        and final_binding["bound_execution"]["while_lowering_case"]
            == "passed"
        and bound_execution["while_lowering_case"] == "passed"
        and bound_execution["is_prim68_case"] == "passed"
        and wplto_blackbox == final_blackbox
        and wplto_renderer["entry_bytes"]
            == final_renderer["entry_bytes"] == D1.EXPECTED_ENTRY_BYTES,
        "Link-79 full post-link replay red",
    )

    value = {
        "format": "lisp65-c2.2-product-link79-fail-closed-blackbox-v1",
        "recorded_on": "2026-07-29",
        "status": "passed-Link79-blackbox-hardware-not-run",
        "promotable": False,
        "link_number": LINK,
        "predecessor": bind(PREDECESSOR),
        "qualified_WPLTO": bind(AUTHORITY),
        "product": bind(product),
        "ELF": bind(elf),
        "profile": bind(profile),
        "manifest": bind(paths["manifest"]),
        "static_geometry": authority["static_geometry"],
        "walls": walls | {
            "session_family_headroom_bytes":
                capacity["session_family_headroom_bytes"],
        },
        "blackbox": {
            "source": source_gate,
            "mutations": mutations,
            "WPLTO_linked": wplto_blackbox,
            "final_linked": final_blackbox,
        },
        "gates": {
            "inherited_count": len(inherited),
            "inherited_names": sorted(inherited),
            "bound_product_manifests": product_binding,
            "bound_artifact_source_parity": bind(final_binding_path),
            "bound_while_execution": bound_execution,
            "compiler_tier": source,
            "interrupt_ownership": bind(irq_path),
            "session_service": service,
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
            "contract": bind(BB.BLACKBOX.CONTRACT),
            "driver": bind(DRIVER),
            "WPLTO_internal":
                bind(paths["receipts"] / "wplto-internal.json"),
            "artifact_completion":
                bind(paths["receipts"] / "artifact-completion.json"),
        },
        "next_gate": (
            "Exactly one hardware run with require, defstruct and "
            "make-point. Attribute from FF80..FF8F or park defstruct "
            "permanently for this era; no instrument revision."
        ),
        "claim_limit": (
            "Link-79 structural completion only; blackbox and defstruct "
            "hardware outcome remain unclaimed."
        ),
    }
    write(RECEIPT, value)
    print(
        "c2-v1.2.2-link79: LINK PASS "
        f"product={value['product']['sha256']} "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        f"session={capacity['session_family_headroom_bytes']} "
        "hardware=not-run"
    )
    return 0


def main() -> int:
    require(
        sys.argv[1:] in ([], ["link"], ["_complete"]),
        "usage: c2_v122_fail_closed_blackbox_successor_link79.py "
        "[link|_complete]",
    )
    if sys.argv[1:] == ["_complete"]:
        return current_completion()
    return link_action()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if (
            sys.argv[1:] != ["_complete"]
            and not RECEIPT.exists()
            and not FIRST_RED.exists()
        ):
            product = (
                BUILD / "wplto/lisp65-c2-substitution-linked.prg")
            write(FIRST_RED, {
                "format":
                    "lisp65-c2.2-product-link79-blackbox-first-red-v1",
                "recorded_on": "2026-07-29",
                "status": "FIRST RED: Link-79 did not close",
                "error": str(error),
                "product_link_invocation_may_have_completed":
                    product.is_file(),
                "linked_product":
                    bind(product) if product.is_file() else None,
                "retry_authorized": False,
            })
        print(f"c2-v1.2.2-link79: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
