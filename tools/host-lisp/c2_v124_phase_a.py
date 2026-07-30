#!/usr/bin/env python3
"""Close v1.2.4 Phase A without reopening the fixed DIRMISS product path."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_v122_dirmiss_renderer_wplto as D1  # noqa: E402


PLAN = ROOT / "docs/planning/1.2.4-work-plan.md"
HISTORICAL_GATE = (
    ROOT / "tools/host-lisp/c2_v121_dirmiss_renderer_attribution.py")
HISTORICAL_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.1-dirmiss-renderer-attribution-receipt.json")
LINK78_STRUCTURAL = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link78-dirmiss-renderer-structural-receipt.json")
LINK78_HARDWARE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link78-d1-d2-bundled-hardware-receipt.json")
V123_PUBLICATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/post-release/"
    "v123-public-publication-receipt-20260730.json")
LINK80_ELF = ROOT / (
    "build/c2.2/v1.2.3-candidate-product-link80/final/"
    "lisp65-c2-substitution-linked.prg.elf")
SOURCE = ROOT / "src/l65e_bcode_ordinal.s"
SMOKE = ROOT / "tools/host-lisp/error_overlay_smoke.py"
DRIVER = Path(__file__).resolve()
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.4-phase-a-dirmiss-hygiene-receipt.json")

FORMAT = "lisp65-c2.2-v1.2.4-phase-a-dirmiss-hygiene-v1"
EXACT_RENDER = "undefined function: intern-renderer-missing"
ARTIFACT_SET = (
    "e71cc4f46068a1c5ebebf050a76fb14717c03a27e954d0bbaacd95a70970e315")


class PhaseAError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PhaseAError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"missing file: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"missing JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def run(command: list[str], label: str) -> str:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    require(
        result.returncode == 0,
        f"{label} failed ({result.returncode}):\n{result.stdout[-6000:]}")
    return result.stdout


def collect() -> dict[str, Any]:
    historical_output = run(
        [sys.executable, str(HISTORICAL_GATE), "--check"],
        "historical DIRMISS attribution")
    historical = load(HISTORICAL_RECEIPT)
    require(
        historical.get("status")
        == "passed-renderer-pointer-abi-overwrite-attributed"
        and historical.get("mutations", {}).get("attempted") == 5
        and historical.get("mutations", {}).get("rejected") == 5
        and historical.get("disposition", {}).get("next_eligible_release")
        == "v1.2.2",
        "historical DIRMISS attribution drift")

    source = SOURCE.read_text(encoding="ascii")
    D1.L65E.renderer_source_contract(source)
    current_mutations = D1.L65E.renderer_source_mutations(source)
    smoke_output = run(
        [sys.executable, str(SMOKE)], "current DIRMISS execution fixture")
    require(
        "error-overlay smoke: ok "
        "(cases=20 full-symbol=intern-renderer-missing "
        "target-mutations=5 " in smoke_output
        and "error-overlay target pointer contract: "
        "ok (mutations=5 full-symbol=intern-renderer-missing)"
        in smoke_output
        and len(current_mutations) == 5,
        "current DIRMISS fixture lacks its execution/mutation witness")

    structural = load(LINK78_STRUCTURAL)
    d1 = structural.get("D1", {})
    host_gate = d1.get("host_and_object_gate", {})
    require(
        structural.get("status")
        == "passed-Link78-D1-renderer-hardware-not-run"
        and host_gate.get("status")
        == "passed-full-name-and-target-pointer-consumption"
        and host_gate.get("rendered_exactly") == EXACT_RENDER
        and host_gate.get("host_cases_executed") == 20,
        "Link-78 structural DIRMISS authority drift")

    hardware = load(LINK78_HARDWARE)
    rows = {
        row.get("id"): row for row in hardware.get("passed_rows", [])
        if isinstance(row, dict)
    }
    require(
        rows.get("dirmiss-full-name", {}).get("outcome")
        == "*** " + EXACT_RENDER
        and rows.get("post-dirmiss-repl", {}).get("outcome") == "9",
        "Link-78 full-name hardware authority drift")

    publication = load(V123_PUBLICATION)
    require(
        publication.get("status") == "passed"
        and publication.get("result") == "published-and-readback-verified"
        and publication.get("product_authority", {}).get(
            "artifact_set_sha256") == ARTIFACT_SET,
        "released v1.2.3 authority drift")
    linked = D1.linked_renderer_gate(LINK80_ELF)
    require(
        linked.get("status")
        == "passed-linked-symname-result-consumed-directly"
        and linked.get("instructions_after_symname")
        == ["ldz #$0", "lda ($4),z"],
        "Link-80 renderer reintroduced incidental A/X stores")

    return {
        "format": FORMAT,
        "recorded_on": "2026-07-30",
        "status": "passed-phase-A-checker-harness-debt-closed",
        "classification": "checker-harness-fix-no-product-question",
        "disposition": {
            "historical_fault":
                "renderer overwrote symname's __rc2/__rc3 with incidental A/X",
            "product_fix": "landed-in-Link78-and-released-in-v1.2.2",
            "remaining_red":
                "historical checker read corrected current source",
            "checker_fix":
                "read historical source and plan blobs from bound Git commits",
            "open_product_question": False,
        },
        "execution_witnesses": {
            "historical_attribution_mutations": "5/5",
            "historical_gate_output": historical_output.strip(),
            "current_host_cases": 20,
            "current_target_mutations": current_mutations,
            "current_smoke_output": smoke_output.strip().splitlines(),
            "hardware_full_name": "*** " + EXACT_RENDER,
        },
        "released_product": {
            "release": "v1.2.3",
            "artifact_set_sha256": ARTIFACT_SET,
            "link80_renderer": linked,
        },
        "scope_effects": {
            "product_bytes": 0,
            "wplto_runs": 0,
            "product_links": 0,
            "hardware_runs": 0,
        },
        "authorities": {
            "plan": bind(PLAN),
            "historical_gate": bind(HISTORICAL_GATE),
            "historical_receipt": bind(HISTORICAL_RECEIPT),
            "current_source": bind(SOURCE),
            "current_smoke": bind(SMOKE),
            "link78_structural": bind(LINK78_STRUCTURAL),
            "link78_hardware": bind(LINK78_HARDWARE),
            "link80_elf": bind(LINK80_ELF),
            "v1.2.3_publication": bind(V123_PUBLICATION),
            "driver": bind(DRIVER),
        },
        "claim_limit": (
            "Host/static closure plus inherited Link-78 full-name hardware "
            "authority only; no new product, timing, WPLTO, link or hardware "
            "claim."),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check", action="store_true",
        help="verify the tracked receipt instead of rewriting it")
    args = parser.parse_args()
    try:
        value = collect()
        encoded = json.dumps(
            value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
        if args.check:
            require(RECEIPT.is_file(), f"missing receipt: {RECEIPT}")
            require(
                RECEIPT.read_text(encoding="utf-8") == encoded,
                "tracked Phase-A receipt drift")
        else:
            RECEIPT.parent.mkdir(parents=True, exist_ok=True)
            RECEIPT.write_text(encoded, encoding="utf-8")
        print(
            "c2-v1.2.4-phase-a: PASS "
            "historical-mutations=5/5 current-cases=20 "
            "current-mutations=5/5 product-delta=0")
        return 0
    except (PhaseAError, D1.DirmissProbeError, OSError, UnicodeError,
            json.JSONDecodeError, ValueError) as error:
        print(f"c2-v1.2.4-phase-a: FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
