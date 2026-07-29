#!/usr/bin/env python3
"""Run the sole owner-authorized fail-closed-blackbox WPLTO."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_v122_dirmiss_renderer_wplto as D1  # noqa: E402
import c2_fail_closed_blackbox_gate as BLACKBOX  # noqa: E402
import c2_c1_freezer_irq_episode_gate as EPISODE  # noqa: E402


V = D1.V
BASE = D1.BASE
BUILD = ROOT / "build/post-release/v1.2.2/fail-closed-blackbox/wplto-v2"
PRELINK_BUILD = (
    ROOT / "build/post-release/v1.2.2/fail-closed-blackbox/wplto")
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / "c2.2-v1.2.2-fail-closed-blackbox-wplto-receipt.json"
FIRST_RED = EVIDENCE / (
    "c2.2-v1.2.2-fail-closed-blackbox-wplto-first-red.json")
PREDECESSOR = EVIDENCE / (
    "c2.2-product-link78-dirmiss-renderer-structural-receipt.json")
DRIVER = Path(__file__).resolve()


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
        stderr=subprocess.STDOUT, check=False,
    )
    require(
        result.returncode == 0,
        f"{label} red ({result.returncode}):\n{result.stdout[-6000:]}",
    )
    return result.stdout


def configure() -> dict[str, Path]:
    V.configure_candidate()
    BASE.LINK = 79
    BASE.EXPECTED_STATIC = V.EXPECTED_STATIC
    BASE.EXPECTED_RESOLUTIONS = V.EXPECTED_RESOLUTIONS
    BASE.ROOT_BUILD = BUILD
    BASE.PROBE_BUILD = BUILD
    BASE.LINK_BUILD = BUILD
    BASE.WPLTO_RECEIPT = RECEIPT
    BASE.LINK_RECEIPT = RECEIPT
    BASE.LINK69 = PREDECESSOR
    BASE.EVIDENCE = EVIDENCE
    BASE.DRIVER = DRIVER
    paths = BASE.configure(BUILD)
    V.bind_candidate_specs()
    os.environ.update(BASE.CAN.canonical_build_environment())
    return paths


def probe() -> int:
    require(not BUILD.exists() and not RECEIPT.exists(),
            "blackbox WPLTO requires a fresh one-shot build")
    prelink = load(FIRST_RED)
    require(
        prelink.get("status") == "FIRST RED: blackbox WPLTO stopped"
        and prelink.get("error")
            == "Link-74 resolver, Z-boundary, IRQ or service gate red"
        and prelink.get("product_links") == 0
        and prelink.get("hardware_runs") == 0
        and not list(PRELINK_BUILD.rglob(
            "lisp65-c2-substitution-linked.prg.elf")),
        "typed prelink checker stop is not the unconsumed WPLTO authority",
    )
    predecessor = load(PREDECESSOR)
    require(
        predecessor.get("status")
            == "passed-Link78-D1-renderer-hardware-not-run"
        and predecessor.get("execution_accounting", {}).get(
            "whole_program_product_links") == 1,
        "Link-78 predecessor authority drift",
    )
    source = BLACKBOX.SOURCE.read_text(encoding="ascii")
    source_gate = BLACKBOX.source_gate(source)
    contract_gate = BLACKBOX.contract_gate()
    mutations = BLACKBOX.mutation_gate(source)
    episode = EPISODE.source_gate(source)
    D1.dirmiss_host_gate()
    equivalence = run(
        ["make", "equivalence-check"],
        "blackbox equivalence and execution canary",
    )
    require(
        "equivalence-completion-canary: COMPLETE lanes=11 executed=447"
            in equivalence,
        "equivalence chain lacks its positive execution witness",
    )

    paths = configure()
    static = BASE.PROBE.REQ.build_static_plane()
    plane = BASE.PROBE.REQ.F1W.static_gate()
    product_path = paths["static_product"] / "substitution-artifacts.json"
    product = load(product_path)
    require(
        static["semantics"]["code_bytes"] == V.EXPECTED_STATIC
        and plane["static_code_bytes"] == V.EXPECTED_STATIC
        and product["product_build_id_hex"] == V.EXPECTED_PRODUCT_ID
        and product["entries"] == V.EXPECTED_ENTRIES
        and product["resolutions"] == V.EXPECTED_RESOLUTIONS
        and product["roots"] == V.EXPECTED_ROOTS,
        "blackbox changed the static plane",
    )
    inherited = V.inherited_gates()

    # The only target linker invocation allowed for this capacity question.
    wplto = BASE.CAN.run_wplto()
    replacement = wplto["historical_checker_boundary"][
        "current_replacement_gates"]
    walls = replacement["walls"]
    capacity = replacement["capacity"]
    require(
        wplto["status"].startswith("passed-one-current-WPLTO")
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] >= 54
        and walls["fixed_hot_block_headroom_bytes"] >= 0
        and walls["ordinary_bank0_bss_headroom_bytes"] >= 0
        and walls["resident_island_headroom_bytes"] >= 0
        and capacity["session_family_headroom_bytes"] >= 0,
        "blackbox crossed a product wall",
    )
    elf = paths["wplto"] / "lisp65-c2-substitution-linked.prg.elf"
    linked = BLACKBOX.linked_gate(elf, BLACKBOX.PREDECESSOR)
    irq = V.LINK76.IRQ.audit(elf=elf)
    renderer = D1.linked_renderer_gate(elf)
    require(
        linked["IRQ_nonterminal_delta_bytes"] == 0
        and linked["window_state_growth_bytes"] == 0
        and linked["generic_fail_closed_delta_bytes"] == 0
        and irq["mutations"]["rejected"] == irq["mutations"]["total"] == 16,
        "linked blackbox or IRQ ownership replay red",
    )

    value = {
        "format": "lisp65-c2.2-v1.2.2-fail-closed-blackbox-WPLTO-v1",
        "recorded_on": "2026-07-29",
        "status": "passed-one-fail-closed-blackbox-WPLTO",
        "promotable": False,
        "wplto_probes_consumed": 1,
        "product_links": 0,
        "hardware_runs": 0,
        "prelink_checker_replay": {
            "receipt": bind(FIRST_RED),
            "classification":
                "stale exact ASM-entry inventory before target link",
            "old_expected_entries": 59,
            "current_entries": 60,
            "new_entry":
                "c2_kernal_sourceless_fail_blackbox (nonreturning)",
            "linked_ELFs_before_replay": 0,
            "WPLTO_consumed_before_replay": 0
        },
        "predecessor": bind(PREDECESSOR),
        "blackbox": {
            "source": source_gate,
            "contract": contract_gate,
            "mutations": mutations,
            "linked": linked,
            "linked_gate_mutation_count": mutations["total"],
            "reason_code": "0xb2",
            "visible_code": "F2",
        },
        "normal_path": {
            "IRQ_nonterminal_delta_bytes": 0,
            "generic_fail_closed_delta_bytes": 0,
            "window_state_growth_bytes": 0,
            "episode_gate": episode,
        },
        "static_geometry": {
            "bank2_static_code_bytes": V.EXPECTED_STATIC,
            "entries": V.EXPECTED_ENTRIES,
            "resolutions": V.EXPECTED_RESOLUTIONS,
            "roots": V.EXPECTED_ROOTS,
            "product_build_id": V.EXPECTED_PRODUCT_ID,
            "bank2_sha256": V.EXPECTED_BANK2_SHA,
        },
        "walls": walls,
        "capacity": capacity,
        "interrupt_ownership": irq,
        "DIRMISS": renderer,
        "inherited_gates": {
            "count": len(inherited),
            "names": sorted(inherited),
            "equivalence_lanes": 11,
            "equivalence_cases_executed": 447,
        },
        "wplto": wplto,
        "authority": {
            "contract": bind(BLACKBOX.CONTRACT),
            "kernal_contract": bind(BLACKBOX.KERNAL_CONTRACT),
            "source": bind(BLACKBOX.SOURCE),
            "gate": bind(ROOT / (
                "tools/host-lisp/c2_fail_closed_blackbox_gate.py")),
            "linked_ELF": bind(elf),
            "driver": bind(DRIVER),
        },
        "next_gate": (
            "Exactly one successor product Link 79, then exactly one "
            "three-row defstruct hardware run. No instrument revision."
        ),
        "claim_limit": (
            "One product-shaped WPLTO only; no product-link or hardware "
            "blackbox/defstruct claim."
        ),
    }
    write(RECEIPT, value)
    print(
        "c2-v1.2.2-blackbox: WPLTO PASS "
        f"body={linked['blackbox_bytes']} "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        f"session={capacity['session_family_headroom_bytes']} "
        "links=0 hardware=0"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(probe())
    except Exception as error:
        if not RECEIPT.exists() and not FIRST_RED.exists():
            write(FIRST_RED, {
                "format":
                    "lisp65-c2.2-v1.2.2-fail-closed-blackbox-first-red-v1",
                "recorded_on": "2026-07-29",
                "status": "FIRST RED: blackbox WPLTO stopped",
                "error": str(error),
                "product_links": 0,
                "hardware_runs": 0,
                "retry_authorized": False,
            })
        print(f"c2-v1.2.2-blackbox: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
