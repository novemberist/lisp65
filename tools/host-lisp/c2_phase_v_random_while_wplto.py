#!/usr/bin/env python3
"""Run the one owner-authorized Phase-V random/while product-shaped WPLTO.

This is deliberately a probe-only driver.  It emits the current six-image
static plane, binds the actual random stdlib and while-capable compiler
carrier, runs one target WPLTO, and writes a non-promotable capacity receipt.
It has no product-link or hardware action.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_bound_artifact_source_parity as BOUND  # noqa: E402
import c2_random_base_gate as RANDOM  # noqa: E402
import c2_require_fastpath_irq_successor_link76 as LINK76  # noqa: E402


BASE = LINK76.BASE
BUILD = (
    ROOT /
    "build/post-promotion/phase-v/random-while/product-shaped-wplto-v2")
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / "c2.2-phase-v-random-while-wplto-receipt.json"
FIRST_RED = EVIDENCE / (
    "c2.2-phase-v-random-while-wplto-first-red.json")
PREDECESSOR = EVIDENCE / (
    "c2.2-product-link76-require-fastpath-irq-ownership-"
    "structural-receipt.json")
RANDOM_RECEIPT = EVIDENCE / "c2.2-v1-random-base-host-first-receipt.json"
WHILE_RECEIPT = EVIDENCE / "c2.2-v2-while-four-view-receipt.json"
RANDOM_MANIFEST = (
    ROOT / "build/post-promotion/phase-v/random-base/gate/"
    "candidate/stdlib-p0.manifest.json")
WHILE_MANIFEST = (
    ROOT / "build/post-promotion/phase-v/while/gate/carrier/"
    "lcc.manifest.json")
WHILE_TIER = (
    ROOT / "build/post-promotion/phase-v/while/gate/"
    "compiler-tier/tier-generation.json")
WHILE_GATE = ROOT / "tools/host-lisp/c2_while_gate.py"
DRIVER = Path(__file__).resolve()

EXPECTED_STATIC = 41485
EXPECTED_ENTRIES = 696
EXPECTED_RESOLUTIONS = 2760
EXPECTED_ROOTS = 340
EXPECTED_DIRECT_REFS = 656
EXPECTED_PRODUCT_ID = "0x0957c9d5"
EXPECTED_BANK2_SHA = (
    "cac8e6392de04b9086f37d77b38db7a2f2fd99e904b7b985c50af93db4b16c09"
)


class ProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProbeError(message)


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


def run(command: list[str], label: str) -> str:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    require(
        result.returncode == 0,
        f"{label} red ({result.returncode}):\n{result.stdout}",
    )
    return result.stdout


def bind_candidate_specs() -> None:
    """Bind both changed manifest roles at the active producer boundary."""
    for module in (LINK76, LINK76.PREV):
        module.EXPECTED_STATIC = EXPECTED_STATIC
        module.EXPECTED_ENTRIES = EXPECTED_ENTRIES
        module.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
        module.EXPECTED_ROOTS = EXPECTED_ROOTS
        module.EXPECTED_DIRECT_REFS = EXPECTED_DIRECT_REFS

    req = BASE.PROBE.REQ
    req.SPECS = tuple(
        (
            key,
            name,
            RANDOM_MANIFEST if key == "stdlib-p0"
            else WHILE_MANIFEST if key == "lcc"
            else path,
        )
        for key, name, path in req.SPECS
    )
    req.EXPECTED_STATIC = EXPECTED_STATIC
    req.EXPECTED_ENTRIES = EXPECTED_ENTRIES
    req.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    req.EXPECTED_ROOTS = EXPECTED_ROOTS
    req.EXPECTED_DIRECT_REFS = EXPECTED_DIRECT_REFS
    req.F1W.EXPECTED_STATIC = EXPECTED_STATIC
    req.F1W.EXPECTED_ENTRIES = EXPECTED_ENTRIES
    req.F1W.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    req.F1W.EXPECTED_ROOTS = EXPECTED_ROOTS
    req.F1W.SPECS = req.SPECS
    # F1W.configure has already copied its manifest tuple into the canonical
    # product module by the time the final producer boundary is selected.
    # Keep that runtime copy aligned as well: current linked gates (notably
    # the zero-literal witness) derive ordinals from CAN.SPECS.
    BASE.CAN.SPECS = req.SPECS
    BASE.CAN.PREFIXES = tuple(
        (
            path.with_suffix(""),
            "stdlib" if index == 0 else "disk-lib",
            None if index == 0 else "0x000000",
        )
        for index, (_key, _name, path) in enumerate(req.SPECS)
    )


def configure_candidate() -> None:
    """Rebind every producer and checker to the two Phase-V artifacts."""
    LINK76.configure()
    LINK76.PREV.CARRIER = WHILE_MANIFEST
    LINK76.PREV.TIER_RECEIPT = WHILE_TIER
    bind_candidate_specs()

    BASE.LINK = 77
    BASE.EXPECTED_STATIC = EXPECTED_STATIC
    BASE.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    BASE.ROOT_BUILD = BUILD
    BASE.PROBE_BUILD = BUILD
    BASE.LINK_BUILD = BUILD
    BASE.WPLTO_RECEIPT = RECEIPT
    BASE.LINK_RECEIPT = RECEIPT
    BASE.LINK69 = PREDECESSOR
    BASE.EVIDENCE = EVIDENCE
    BASE.DRIVER = DRIVER
    os.environ.update(BASE.CAN.canonical_build_environment())


def feature_gates() -> dict[str, Any]:
    public_build = (
        os.environ.get("LISP65_PUBLIC_CURRENT_SOURCE_BUILD") == "1"
    )
    random_result = RANDOM.main(public_build=public_build)
    require(random_result == 0, "random host-first gate red")
    while_output = run(
        [sys.executable, str(WHILE_GATE)],
        "while four-view gate",
    )
    random_receipt_path = (
        RANDOM.PUBLIC_BUILD_RECEIPT if public_build else RANDOM_RECEIPT
    )
    random_receipt = load(random_receipt_path)
    while_receipt = load(WHILE_RECEIPT)
    require(
        random_receipt["status"]
            == (
                "passed-random-base-current-source-public-build"
                if public_build
                else "passed-random-base-host-first-and-capacity-projection"
            )
        and random_receipt["artifacts"]["delta"] == {
            "bank2_code_bytes": 489,
            "directory_bytes": 77,
            "objects": 11,
            "resolution_words": 31,
            "resident_bytes": 0,
        }
        and while_receipt["status"]
            == (
                "passed-four-view-while-successor-link-"
                "authorized-not-run"
            )
        and len(while_receipt["mutations_rejected"]) == 14
        and while_receipt["bound_device_carrier"]["result"] == 3,
        "Phase-V random/while host authorities drift",
    )
    carrier, suite, source = BOUND.source_binding_gate(
        WHILE_MANIFEST, WHILE_TIER)
    execution = BOUND.execute_bound_cases(
        WHILE_MANIFEST, carrier, suite, require_while=True)
    require(
        execution["while_lowering_case"] == "passed"
        and execution["is_prim68_case"] == "passed",
        "packed candidate carrier did not execute while",
    )
    return {
        "random": {
            "receipt": bind(random_receipt_path),
            "candidate_manifest": bind(RANDOM_MANIFEST),
            "delta": random_receipt["artifacts"]["delta"],
        },
        "while": {
            "receipt": bind(WHILE_RECEIPT),
            "gate_output": while_output.strip().splitlines()[-1],
            "candidate_manifest": bind(WHILE_MANIFEST),
            "compiler_tier": source,
            "bound_execution": execution,
            "streamed_backedge":
                while_receipt["host_compiler_VM"]["streamed_backedge"],
        },
    }


def inherited_gates() -> dict[str, Any]:
    gates = LINK76.fix_gates()
    bound = gates["bound_artifact_source_parity_preplane"][
        "bound_execution"]
    require(
        bound["while_lowering_case"] == "passed"
        and bound["prim67"] == 67 and bound["prim68"] == 68,
        "inherited bound-artifact gate omitted candidate while execution",
    )
    return gates


def probe() -> int:
    require(
        not BUILD.exists() and not RECEIPT.exists()
        and not FIRST_RED.exists(),
        "Phase-V random/while WPLTO is a one-shot probe",
    )
    predecessor = load(PREDECESSOR)
    require(
        predecessor["status"]
            == (
                "passed-Link76-require-fastpath-and-strict-"
                "IRQ-ownership-hardware-not-run"
            )
        and predecessor["static_geometry"] == {
            "bank2_delta_bytes": 462,
            "bank2_static_code_bytes": 40746,
            "entries": 682,
            "resident_fastpath_delta_bytes": 0,
            "resolutions": 2711,
            "roots": 340,
            "direct_entry_refs": 643,
        },
        "Link-76 predecessor authority drift",
    )

    features = feature_gates()
    configure_candidate()
    paths = BASE.configure(BUILD)
    # BASE.configure regenerates its ordinary stdlib manifest and restores
    # that local path.  Candidate selection belongs after that setup: the
    # single-emitter must consume the already qualified random manifest, not
    # the resolver-only intermediate it just emitted.
    bind_candidate_specs()
    static = BASE.PROBE.REQ.build_static_plane()
    plane = BASE.PROBE.REQ.F1W.static_gate()
    product_path = paths["static_product"] / "substitution-artifacts.json"
    product = load(product_path)
    profile = load(ROOT / "config/c2-l-full-product-profile.json")
    require(
        static["semantics"]["code_bytes"] == EXPECTED_STATIC
        and plane["static_code_bytes"] == EXPECTED_STATIC
        and product["product_build_id_hex"] == EXPECTED_PRODUCT_ID
        and product["entries"] == EXPECTED_ENTRIES
        and product["resolutions"] == EXPECTED_RESOLUTIONS
        and product["roots"] == EXPECTED_ROOTS
        and profile["direct_entry_refs"] == EXPECTED_DIRECT_REFS
        and profile["bank2_static_code"]["sha256"] == EXPECTED_BANK2_SHA,
        "candidate static plane differs from its bound geometry",
    )
    gates = inherited_gates()
    product_binding = BOUND.product_manifest_gate(
        product_path, WHILE_MANIFEST)

    # This is the sole target linker invocation authorized for this probe.
    wplto = BASE.CAN.run_wplto()
    replacement = wplto["historical_checker_boundary"][
        "current_replacement_gates"]
    walls = replacement["walls"]
    capacity = replacement["capacity"]
    session = BASE.PROBE.service_manifest_gate()
    elf = paths["wplto"] / "lisp65-c2-substitution-linked.prg.elf"
    linked_service = BASE.SERVICE.linked_gate(
        elf,
        paths["wplto"] / "runtime-overlays-session-final.json",
        paths["wplto"] / "runtime-overlays-boot-final.json",
    )
    linked_irq = LINK76.IRQ.audit(elf=elf)
    resident_keys = (
        "bank0_text_headroom_bytes",
        "e000_headroom_bytes",
        "fixed_hot_block_headroom_bytes",
        "ordinary_bank0_bss_headroom_bytes",
        "resident_island_headroom_bytes",
    )
    require(
        wplto["status"].startswith("passed-one-current-WPLTO")
        and all(walls[key] >= 0 for key in resident_keys)
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] >= 54
        and capacity["session_family_headroom_bytes"] >= 0
        and session["new_records"] == 1
        and linked_service["slot"] == 51
        and linked_irq["final_ELF"][
            "readbacks_before_window_publish"] is True,
        "Phase-V candidate crossed a product wall or linked gate",
    )

    value = {
        "format": "lisp65-c2.2-phase-v-random-while-WPLTO-v1",
        "recorded_on": "2026-07-29",
        "status": "passed-random-and-while-one-product-shaped-WPLTO",
        "promotable": False,
        "product_links": 0,
        "hardware_runs": 0,
        "wplto_probes_consumed": 1,
        "predecessor": bind(PREDECESSOR),
        "features": features,
        "static_geometry": {
            "bank2_static_code_bytes": EXPECTED_STATIC,
            "bank2_delta_from_Link76_bytes":
                EXPECTED_STATIC - 40746,
            "bank2_headroom_bytes": 65536 - EXPECTED_STATIC,
            "entries": EXPECTED_ENTRIES,
            "resolutions": EXPECTED_RESOLUTIONS,
            "roots": EXPECTED_ROOTS,
            "direct_entry_refs": EXPECTED_DIRECT_REFS,
            "product_build_id": EXPECTED_PRODUCT_ID,
            "bank2_sha256": EXPECTED_BANK2_SHA,
        },
        "bound_product_manifests": product_binding,
        "inherited_gates": {
            "count": len(gates),
            "names": sorted(gates),
            "bound_candidate_while_execution": "passed",
        },
        "walls": walls,
        "capacity": capacity,
        "session_service": linked_service,
        "interrupt_ownership": linked_irq,
        "wplto": wplto,
        "authority": {
            "profile": bind(
                ROOT / "config/c2-l-full-product-profile.json"),
            "execution_contract": bind(
                ROOT / "config/c2-lite-execution-contract.json"),
            "static_plane_header": bind(
                ROOT / "src/c2_lite_static_plane.h"),
            "static_product": bind(product_path),
            "linked_ELF": bind(elf),
            "driver": bind(DRIVER),
        },
        "next_gate": (
            "Owner review of this capacity card. A successor product link "
            "requires separate authorization."
        ),
        "claim_limit": (
            "One product-shaped target WPLTO and host/ELF gates only; no "
            "successor product link, hardware timing, on-metal random or "
            "on-metal while claim."
        ),
    }
    write(RECEIPT, value)
    print(
        "c2-phase-v-random-while: WPLTO PASS "
        f"bank2={EXPECTED_STATIC} "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        f"session={capacity['session_family_headroom_bytes']} "
        "links=0 hardware=0"
    )
    return 0


def resume() -> int:
    """Close the one completed WPLTO from its unchanged linked artifacts.

    The target linker completed once.  Its historical zero-literal adapter
    derived the witness ordinal from the pre-random stdlib tuple because
    F1W.configure had copied SPECS before the final candidate selection.
    The permanent binding now updates CAN.SPECS at that same boundary.  This
    action consumes only host/ELF gates over the already linked identity.
    """
    require(
        BUILD.is_dir() and not RECEIPT.exists() and FIRST_RED.is_file(),
        "Phase-V artifact-side resume boundary red",
    )
    configure_candidate()
    paths = BASE.configure(BUILD)
    bind_candidate_specs()
    product = paths["wplto"] / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    map_path = Path(str(product) + ".map")
    qualification_path = (
        paths["receipts"] /
        "phase-v-artifact-side-current-qualification.json")
    qualification = load(qualification_path)
    base_result_path = paths["receipts"] / "wplto-base-result.json"
    base_result = load(base_result_path)
    static_product = (
        paths["static_product"] / "substitution-artifacts.json")
    product_identity = load(static_product)
    random_receipt = load(RANDOM_RECEIPT)
    while_receipt = load(WHILE_RECEIPT)
    gates = inherited_gates()
    product_binding = BOUND.product_manifest_gate(
        static_product, WHILE_MANIFEST)
    walls = qualification["walls"]
    capacity = qualification["capacity"]
    zero = qualification["zero_literal"]["c2d_witness"]
    resident_keys = (
        "bank0_text_headroom_bytes",
        "e000_headroom_bytes",
        "fixed_hot_block_headroom_bytes",
        "ordinary_bank0_bss_headroom_bytes",
        "resident_island_headroom_bytes",
    )
    require(
        base_result["WPLTO"]["product_completed"] is True
        and base_result["WPLTO"]["return_code"] == 2
        and qualification["status"]
            == "passed-same-ELF-current-artifact-side-qualification"
        and qualification["generic_product_closure"] == "passed"
        and qualification["pre_ownership"] == "passed"
        and qualification["product_identity"] == {
            "product": bind(product),
            "elf": bind(elf),
            "map": bind(map_path),
        }
        and all(walls[key] >= 0 for key in resident_keys)
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] >= 54
        and capacity["session_family_headroom_bytes"] >= 0
        and zero == {
            "ordinal": 591,
            "row_hex": "05000c862600b2080100",
            "literal_count": 0,
            "code_length": 38,
        }
        and qualification["real_abi"]["status"]
            == "passed-all-assembler-leaf-abi-contracts"
        and qualification["real_abi"]["callsite_count"] == 9
        and qualification["session_service"]["slot"] == 51
        and qualification["interrupt_ownership"]["final_ELF"][
            "readbacks_before_window_publish"] is True
        and product_identity["product_build_id_hex"] == EXPECTED_PRODUCT_ID
        and product_identity["entries"] == EXPECTED_ENTRIES
        and product_identity["resolutions"] == EXPECTED_RESOLUTIONS
        and product_identity["roots"] == EXPECTED_ROOTS,
        "same-ELF Phase-V artifact-side qualification red",
    )
    value = {
        "format": "lisp65-c2.2-phase-v-random-while-WPLTO-v1",
        "recorded_on": "2026-07-29",
        "status":
            "passed-random-and-while-one-WPLTO-with-same-ELF-checker-replay",
        "promotable": False,
        "product_links": 0,
        "hardware_runs": 0,
        "wplto_probes_consumed": 1,
        "whole_program_LTO_closure_links": 1,
        "predecessor": bind(PREDECESSOR),
        "first_red": {
            "receipt": bind(FIRST_RED),
            "classification":
                "checker-configuration-only-after-link-completion",
            "mechanism": (
                "The static producer was rebound to random after F1W setup, "
                "but CAN.SPECS retained the earlier stdlib tuple; the "
                "zero-literal checker therefore derived a stale ordinal."
            ),
            "product_bytes_changed_by_correction": 0,
            "compiler_runs_added": 0,
            "linker_runs_added": 0,
        },
        "features": {
            "random": {
                "receipt": bind(RANDOM_RECEIPT),
                "candidate_manifest": bind(RANDOM_MANIFEST),
                "delta": random_receipt["artifacts"]["delta"],
            },
            "while": {
                "receipt": bind(WHILE_RECEIPT),
                "candidate_manifest": bind(WHILE_MANIFEST),
                "compiler_tier": bind(WHILE_TIER),
                "bound_execution": {
                    "result":
                        while_receipt["bound_device_carrier"]["result"],
                    "byteidentical_to_host_compiler":
                        while_receipt["bound_device_carrier"][
                            "byteidentical_to_host_compiler"],
                },
                "streamed_backedge":
                    while_receipt["host_compiler_VM"][
                        "streamed_backedge"],
            },
        },
        "static_geometry": {
            "bank2_static_code_bytes": EXPECTED_STATIC,
            "bank2_delta_from_Link76_bytes":
                EXPECTED_STATIC - 40746,
            "bank2_headroom_bytes": 65536 - EXPECTED_STATIC,
            "entries": EXPECTED_ENTRIES,
            "resolutions": EXPECTED_RESOLUTIONS,
            "roots": EXPECTED_ROOTS,
            "direct_entry_refs": EXPECTED_DIRECT_REFS,
            "product_build_id": EXPECTED_PRODUCT_ID,
            "bank2_sha256": EXPECTED_BANK2_SHA,
        },
        "bound_product_manifests": product_binding,
        "inherited_gates": {
            "count": len(gates),
            "names": sorted(gates),
            "bound_candidate_while_execution": "passed",
        },
        "walls": walls,
        "capacity": capacity,
        "zero_literal_current_witness": zero,
        "artifact_side_completion": bind(qualification_path),
        "linked_identity": qualification["product_identity"],
        "wplto": {
            "status":
                "passed-current-artifact-side-closure-after-typed-first-red",
            "base_result": bind(base_result_path),
            "compiler_runs_added": 0,
            "linker_runs_added": 0,
            "product_links_added": 0,
        },
        "authority": {
            "profile": bind(
                ROOT / "config/c2-l-full-product-profile.json"),
            "execution_contract": bind(
                ROOT / "config/c2-lite-execution-contract.json"),
            "static_plane_header": bind(
                ROOT / "src/c2_lite_static_plane.h"),
            "static_product": bind(static_product),
            "linked_ELF": bind(elf),
            "driver": bind(DRIVER),
        },
        "next_gate": (
            "Owner review of this capacity card. A successor product link "
            "requires separate authorization."
        ),
        "claim_limit": (
            "One product-shaped target WPLTO plus same-ELF host/ELF checker "
            "completion only; no successor product link, hardware timing, "
            "on-metal random or on-metal while claim."
        ),
    }
    write(RECEIPT, value)
    print(
        "c2-phase-v-random-while: WPLTO RESUME PASS "
        f"bank2={EXPECTED_STATIC} "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        f"session={capacity['session_family_headroom_bytes']} "
        "links=0 hardware=0"
    )
    return 0


def finalize_receipt() -> int:
    """Refresh mutable evidence bindings without rebuilding any artifact."""
    require(
        RECEIPT.is_file() and BUILD.is_dir(),
        "Phase-V final receipt is absent",
    )
    value = load(RECEIPT)
    paths = BASE.paths(BUILD)
    product = paths["wplto"] / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    map_path = Path(str(product) + ".map")
    source_parity = (
        paths["receipts"] /
        "final-bound-artifact-source-parity-replay.json")
    random_receipt = load(RANDOM_RECEIPT)
    while_receipt = load(WHILE_RECEIPT)
    require(
        value["status"]
            == (
                "passed-random-and-while-one-WPLTO-with-"
                "same-ELF-checker-replay"
            )
        and value["linked_identity"] == {
            "product": bind(product),
            "elf": bind(elf),
            "map": bind(map_path),
        }
        and load(source_parity)["bound_execution"][
            "while_lowering_case"] == "passed"
        and random_receipt["artifacts"]["projected_post_Link76"]["roots"]
            == EXPECTED_ROOTS
        and while_receipt["source_contract"]["new_opcodes"] == 0,
        "Phase-V evidence-only finalization red",
    )
    value["features"]["random"]["receipt"] = bind(RANDOM_RECEIPT)
    value["features"]["random"]["delta"] = (
        random_receipt["artifacts"]["delta"])
    value["features"]["while"]["receipt"] = bind(WHILE_RECEIPT)
    value["features"]["while"]["compiler_tier"] = bind(WHILE_TIER)
    value["features"]["while"]["streamed_backedge"] = (
        while_receipt["host_compiler_VM"]["streamed_backedge"])
    value["first_red"]["receipt"] = bind(FIRST_RED)
    value["bound_source_closure"] = bind(source_parity)
    value["authority"].update({
        "profile": bind(ROOT / "config/c2-l-full-product-profile.json"),
        "execution_contract":
            bind(ROOT / "config/c2-lite-execution-contract.json"),
        "static_plane_header": bind(ROOT / "src/c2_lite_static_plane.h"),
        "static_product":
            bind(paths["static_product"] / "substitution-artifacts.json"),
        "linked_ELF": bind(elf),
        "driver": bind(DRIVER),
    })
    value["evidence_finalization"] = {
        "status": "passed-bindings-refreshed-without-build",
        "compiler_runs": 0,
        "linker_runs": 0,
        "product_links": 0,
        "hardware_runs": 0,
    }
    write(RECEIPT, value)
    print(
        "c2-phase-v-random-while: RECEIPT FINAL PASS "
        "compiler=0 linker=0 links=0 hardware=0"
    )
    return 0


def main() -> int:
    require(
        sys.argv[1:] in ([], ["probe"], ["resume"], ["finalize-receipt"]),
        "usage: c2_phase_v_random_while_wplto.py "
        "[probe|resume|finalize-receipt]",
    )
    if sys.argv[1:] == ["resume"]:
        return resume()
    if sys.argv[1:] == ["finalize-receipt"]:
        return finalize_receipt()
    return probe()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if not RECEIPT.exists():
            write(FIRST_RED, {
                "format": "lisp65-c2.2-phase-v-random-while-WPLTO-first-red-v1",
                "recorded_on": "2026-07-29",
                "status": "FIRST RED: one authorized WPLTO did not close",
                "promotable": False,
                "product_links": 0,
                "hardware_runs": 0,
                "wplto_retry_authorized": False,
                "error": str(error),
                "driver": (
                    bind(DRIVER) if DRIVER.is_file()
                    else {"path": str(DRIVER)}
                ),
            })
        print(
            "c2-phase-v-random-while: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
