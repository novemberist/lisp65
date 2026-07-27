#!/usr/bin/env python3
"""Bind Link 52's self-stamp hardware First Red without another run."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CANDIDATE = ROOT / (
    "build/c2.2/substitution/product-link-52-c2-lite-v6-phase-self-stamp")
PRODUCT = CANDIDATE / "lisp65-c2-substitution-linked.prg"
STRUCTURAL = EVIDENCE / (
    "c2.2-product-link52-c2-lite-v6-phase-self-stamp-structural-receipt.json")
HW = ROOT / "build/c2.2/hardware-presmoke-link52-phase-self-stamp"
DEPLOYMENT = HW / "deployment.json"
OBS = HW / "observations"
OUTPUT = EVIDENCE / (
    "c2.2-product-link52-phase-self-stamp-hardware-first-red.json")


class EvidenceError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise EvidenceError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"hardware evidence absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def main() -> int:
    require(not OUTPUT.exists(), "Link-52 hardware First Red is one-shot")
    structural = json.loads(STRUCTURAL.read_text(encoding="utf-8"))
    deployment = json.loads(DEPLOYMENT.read_text(encoding="utf-8"))
    setup = (OBS / "definition-setup.txt").read_text(
        encoding="utf-8", errors="replace")
    first = (OBS / "definition-first-call.txt").read_text(
        encoding="utf-8", errors="replace")
    require(structural["status"] ==
                "passed-new-phase-self-stamp-product-identity-hardware-not-run"
            and structural["link_number"] == 52
            and structural["product_identity"]["product"]["sha256"] ==
                sha(PRODUCT)
            and deployment["status"] == "ready-receipt-less"
            and deployment["product"]["sha256"] == sha(PRODUCT)
            and "%c2h" in setup and "*** vm: bad bytecode" in first,
            "Link-52 candidate, deployment, or transcript drift")
    captures = [OBS / f"witness-{index}.bin" for index in (1, 2, 3)]
    witness = [path.read_bytes() for path in captures]
    require(witness == [bytes((44, 0))] * 3,
            "phase-self-stamp captures are not stable [44,0]")
    manifest_path = CANDIDATE / "runtime-overlays-session-final.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    slots = [row for row in manifest["slices"] if row["id"] == 44]
    require(len(slots) == 1 and slots[0]["name"] ==
                "c2-append-abort-control",
            "session slot 44 is not the bound abort-control phase")
    readbacks = sorted(HW.glob("readback-*"))
    require(len(readbacks) == len(deployment["preloads"]),
            "hardware deployment readback inventory incomplete")
    for preload in deployment["preloads"]:
        readback = HW / ("readback-" + Path(preload["path"]).name)
        require(readback.is_file() and sha(readback) == preload["sha256"],
                f"hardware preload readback drift: {preload['path']}")

    value = {
        "format": "lisp65-c2-lite-v6-link52-phase-self-stamp-hardware-first-red-v1",
        "recorded_on": "2026-07-22",
        "status": "first-red-before-inner-vm-after-successful-definition",
        "promotable": False,
        "authority": {
            "structural_receipt": bind(STRUCTURAL),
            "deployment": bind(DEPLOYMENT),
            "product": bind(PRODUCT),
            "session_manifest": bind(manifest_path),
        },
        "hardware": {
            "core_tool_identity": "m65 20260722.00-develo-c5bf0cc",
            "preloads": "6/6 byte-identical readbacks",
            "boot": "passed-banner-and-usable-REPL",
            "definition": {
                "form": "(defun %c2h () 't)",
                "result": "%c2h",
                "transcript": bind(OBS / "definition-setup.txt"),
            },
            "cold_first_call": {
                "form": "%c2h wrapped by the bound frame-counter form",
                "result": "*** vm: bad bytecode",
                "transcript": bind(OBS / "definition-first-call.txt"),
                "completed_latency_measurement": False,
            },
            "phase_witness": {
                "addresses": {"last_session_slot": "0xc1f4",
                              "inner_vm_entered": "0xc1f5"},
                "captures": [bind(path) for path in captures],
                "values": [44, 0],
                "slot_44": slots[0]["name"],
                "stable_captures": 3,
            },
        },
        "finding": {
            "inner_vm_entered": False,
            "vm_run_dir_reached": False,
            "last_observed_phase": "c2-append-abort-control",
            "bounded_origin": (
                "emission/append/install failed before the transition into "
                "inner VM execution; abort cleanup then stamped slot 44"),
            "important_limit": (
                "because rollback and abort phases also self-stamp, slot 44 "
                "is the cleanup terminus, not proof of the primary failing slot"),
            "transport_or_refill_claim": "not implicated by this witness",
        },
        "readback_evidence": [bind(path) for path in readbacks],
        "execution_accounting": {
            "hardware_runs": 1, "additional_product_links": 0,
            "additional_compiler_runs": 0,
        },
        "counters": {
            "line1_product_first_reds": "2/3 unchanged; boot passed",
            "completed_latency_measurements": "0/2",
            "phase_diagnostic_hardware_runs": "1",
        },
        "next_gate": (
            "Class-C review: the witness answers pre-inner versus inner, but "
            "the primary append slot is overwritten by cleanup provenance."),
    }
    OUTPUT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    os.chmod(OUTPUT, 0o444)
    print("c2-lite-v6-link52-phase-self-stamp-hw-first-red: BOUND "
          "definition=passed first-call=BADOPCODE witness=44,0 latency=0/2")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-lite-v6-link52-phase-self-stamp-hw-first-red: FAIL: "
              + str(error), file=sys.stderr)
        raise SystemExit(2)
