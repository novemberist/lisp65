#!/usr/bin/env python3
"""Build the one-round two-stage Comfort abort-reentry repair."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v17_comfort_abort_reentry_fix as FIX  # noqa: E402
import c2_v17_comfort_phase1b_adapter_replacement_card as PHASE  # noqa: E402


CARD = PHASE.CARD
BASE = CARD.BASE
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
BUILD = ROOT / "build/c2.3/v1.7-comfort-abort-reentry-fix-r2"
PREFLIGHT = ROOT / "build/c2.3/v1.7-comfort-abort-reentry-fix-r2-preflight"
RECEIPT = ARCH / "c2.3-v1.7-comfort-abort-reentry-fix-card-r2-receipt.json"
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
LIBRARY = BUILD / "library/repl-comfort"
LIBRARY_SUITE = BUILD / "library/product-profile-suite.json"
LIBRARY_OBSERVATIONS = BUILD / "library/observations.json"
AUTHORIZATION = "f48a12a8"
FORMAT = "lisp65-c2-v17-comfort-abort-reentry-fix-card-r2-v1"
STATUS = "PASS: V1.7 COMFORT ABORT REENTRY TWO-STAGE FINAL GREEN"
DRIVER = Path(__file__).resolve()


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{AUTHORIZATION}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in (
        "consumes the session's one-repair-round path",
        "the one repair round is bound to a two-stage landing",
        "retirement remain before longjmp",
        "transported c2j recovery runs after the top-level stack",
        "re-arming ready is explicitly not a repair",
    ):
        require(token in text, f"abort-reentry authority absent: {token}")
    return {"authority": "git-blob", "commit": AUTHORIZATION, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def configuration_gate() -> dict[str, Any]:
    product = PHASE.configuration_gate()
    proof = FIX.derive(None)
    require(proof["source_gate"]["status"]
                == "PASS: ABORT LANDING IS TWO STAGE"
            and len(proof["mutations"]) == 3
            and proof["models"]["historical_order"]["status"] == "ERR_STACK"
            and proof["models"]["zero_depth"]["status"] == "OK"
            and proof["models"]["nested_depth_three"]["status"] == "OK",
            "two-stage source/model preflight red")
    return {**product, "abort_reentry_fix": {
        "status": proof["source_gate"]["status"],
        "models": proof["models"], "mutations": proof["mutations"],
        "device_contacts": 0, "media_builds": 0,
    }}


def final_gate() -> dict[str, Any]:
    product = CARD.final_gate()
    proof = FIX.final_gate(ELF)
    require(proof["status"]
                == "PASS: FINAL ELF CONSUMES TWO-STAGE LANDING",
            "two-stage final ELF gate red")
    return {**product, "abort_reentry_fix": {
        "status": "PASS: TWO-STAGE ABORT REENTRY PROVED IN FINAL ELF",
        "source": FIX.source_gate(
            FIX.RUNTIME.read_text(encoding="utf-8"),
            FIX.INTERRUPT.read_text(encoding="utf-8"),
            FIX.REPL.read_text(encoding="utf-8")),
        "final_elf": proof,
        "models": {
            "zero_depth": FIX.model(soft_sp=0xC900, journal_depth=0,
                                      two_stage=True),
            "nested_depth_three": FIX.model(
                soft_sp=0xC700, journal_depth=3, two_stage=True),
        },
        "device_contacts": 0, "media_builds": 0,
    }}


def read_existing_product_profile_library(
        profile: dict[str, Any]) -> dict[str, Any]:
    """Validate the product-profile library without regenerating one byte."""
    manifest_path = LIBRARY.with_suffix(".manifest.json")
    manifest = CARD.load(manifest_path)
    suite = CARD.load(LIBRARY_SUITE)
    resident = str(PHASE.RESIDENT.resolve())
    require(suite.get("delivered_callprims") == profile["delivered_ids"]
            and suite.get("resident_suites") == [resident]
            and manifest.get("functions")
                == ["%repl-read", "%repl-prompt", "%repl-step", "repl"]
            and manifest.get("objects") == 4
            and manifest.get("code_bytes") > 0
            and manifest["cost"]["largest_code_object_bytes"] <= 255,
            "existing product-profile Comfort library drift")
    return {
        "adapter_closure": {
            "status": "PASS: REAL CONSUMER RESOLVES DECLARING-SUITE PATH",
            "declaring_suite": CARD.bind(CARD.COMFORT.COMFORT_SUITE),
            "resident_suite": CARD.bind(PHASE.RESIDENT),
            "resolved_path": resident, "cases": 9, "functions": 4,
            "resume": "read-only-existing-product-profile-artifact",
        },
        "suite": CARD.bind(LIBRARY_SUITE),
        "manifest": CARD.bind(manifest_path),
        "blob": CARD.bind(LIBRARY.with_suffix(".blob.bin")),
        "directory": CARD.bind(LIBRARY.with_suffix(".dir.bin")),
        "observations": CARD.bind(LIBRARY_OBSERVATIONS),
        "objects": manifest["objects"], "code_bytes": manifest["code_bytes"],
        "largest_code_object_bytes":
            manifest["cost"]["largest_code_object_bytes"],
        "delivered_callprims": profile["delivered_ids"],
    }


def configure() -> None:
    PHASE.BUILD = BUILD
    PHASE.PREFLIGHT = PREFLIGHT
    PHASE.RECEIPT = RECEIPT
    PHASE.ELF = ELF
    PHASE.LIBRARY = LIBRARY
    PHASE.LIBRARY_SUITE = LIBRARY_SUITE
    PHASE.LIBRARY_OBSERVATIONS = LIBRARY_OBSERVATIONS
    PHASE.AUTHORIZATION = AUTHORIZATION
    PHASE.FORMAT = FORMAT
    PHASE.STATUS = STATUS
    PHASE.DRIVER = DRIVER
    PHASE.configure()
    BASE.authority = authority
    BASE.configuration_gate = configuration_gate
    BASE.final_gate = final_gate


def preflight() -> None:
    configure()
    BASE.preflight()
    print("v1.7 Comfort abort reentry: PREFLIGHT PASS card=0/1")


def build() -> None:
    configure()
    BASE.build()
    FIX.OUT.write_bytes(FIX.canonical(FIX.derive(ELF)))
    print("v1.7 Comfort abort reentry: BUILD PASS WPLTO=1 link=1")


def resume() -> None:
    configure()
    require(not RECEIPT.exists(), "abort-reentry resume already consumed")
    invocation = CARD.load(BASE.INVOCATION)
    producer = CARD.load(BASE.PRODUCER_RESULT)
    scope = CARD.load(BASE.SCOPE_RESULT)
    acceptance = CARD.load(BASE.ACCEPTANCE_RESULT)
    require(invocation["status"] == "INVOKED"
            and producer["status"] == scope["status"]
                == acceptance["status"] == "PASS",
            "frozen repair pair is not resume-eligible")
    before = BASE.artifacts()
    library_before = {path.name: CARD.bind(path) for path in sorted(
        LIBRARY.parent.glob("repl-comfort*")) if path.is_file()}
    CARD.compile_product_profile_library = read_existing_product_profile_library
    gate = final_gate()
    after = BASE.artifacts()
    library_after = {path.name: CARD.bind(path) for path in sorted(
        LIBRARY.parent.glob("repl-comfort*")) if path.is_file()}
    require(before == after and library_before == library_after,
            "read-only repair resume changed a candidate artifact")
    pre = CARD.load(BASE.PREFLIGHT_RECEIPT)
    value = {
        "format": FORMAT, "recorded_on": "2026-08-25", "status": STATUS,
        "authority": authority(), "preflight": CARD.bind(BASE.PREFLIGHT_RECEIPT),
        "invocation": CARD.bind(BASE.INVOCATION),
        "configuration": pre["configuration"], "final_product": gate,
        "producer": CARD.bind(BASE.PRODUCER_RESULT),
        "scope": CARD.bind(BASE.SCOPE_RESULT),
        "acceptance": CARD.bind(BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": [{"action": "read-only-final-gate-resume",
                       "status": "PASS", "WPLTO_runs": 0,
                       "product_links": 0}],
        "attempt_accounting": {"WPLTO_runs": 1, "product_links": 1,
            "scope_runs": 1, "acceptance_runs": 1, "media_builds": 0,
            "device_contacts": 0},
        "media_authorized": False,
        "resume": {"read_only": True, "same_ELF_PRG_pair": True,
                   "reason": "private final-gate symbol was inlined by LTO"},
        "next": "full check-source self-certification, then fresh same-world media",
    }
    RECEIPT.write_bytes(CARD.canonical(value))
    FIX.OUT.write_bytes(FIX.canonical(FIX.derive(ELF)))
    check()
    print("v1.7 Comfort abort reentry: RESUME PASS WPLTO=0 link=0")


def check() -> None:
    configure()
    BASE.check()
    raw = FIX.canonical(FIX.derive(ELF))
    require(FIX.OUT.is_file() and FIX.OUT.read_bytes() == raw,
            "two-stage standalone fix receipt drift")
    value = CARD.load(RECEIPT)
    fix = value["final_product"]["abort_reentry_fix"]
    require(value["status"] == STATUS
            and fix["status"]
                == "PASS: TWO-STAGE ABORT REENTRY PROVED IN FINAL ELF"
            and value["attempt_accounting"] == {
                "WPLTO_runs": 1, "product_links": 1, "scope_runs": 1,
                "acceptance_runs": 1, "media_builds": 0,
                "device_contacts": 0},
            "two-stage repair receipt drift")
    print("v1.7 Comfort abort reentry: CHECK PASS final-world=green")


def run(action: str) -> None:
    {
        "preflight": preflight,
        "build": build,
        "resume": resume,
        "check": check,
        "_produce": lambda: (configure(), BASE.produce_child()),
        "_scope": lambda: (configure(), BASE.scope_child()),
        "_accept": lambda: (configure(), BASE.acceptance_child()),
    }[action]()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "preflight", "build", "resume", "check",
        "_produce", "_scope", "_accept"))
    run(parser.parse_args().action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.7 Comfort abort reentry card: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
