#!/usr/bin/env python3
"""Attribute the recovery card's post-link v16core size-pin Red."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_primary_vm_type_fix as PRIMARY  # noqa: E402

ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RED = ARCH / "c2.3-v1.6-recovery-sanitization-component-replacement-card-final-red.json"
MANIFEST = ROOT / ("build/c2.3/v1.6-recovery-sanitization-component-"
                   "replacement-card/candidate-library/v16core.manifest.json")
BLOB = MANIFEST.with_name("v16core.blob.bin")
ELF = ROOT / ("build/c2.3/v1.6-recovery-sanitization-component-replacement-"
              "card/wplto/lisp65-c2-substitution-linked.prg.elf")
PRG = ELF.with_suffix("")
GATE = ROOT / "tools/host-lisp/c2_v160_active_frame_liveness_card.py"
OUT = ARCH / "c2.3-v1.6-recovery-sanitization-library-pin-attribution.json"


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def derive() -> dict[str, Any]:
    red = load(RED); manifest = load(MANIFEST)
    rows = [row for row in manifest["entries"] if row["name"] == "%read-line-loop"]
    require(red["error"]["message"] == "candidate v16core lost the empty-phase fix"
            and red["attempt_accounting"]["WPLTO_runs"] == 1
            and red["attempt_accounting"]["product_link_attempts"] == 1
            and len(rows) == 1 and rows[0]["length"] == 250,
            "library-pin Red identity drift")
    source = GATE.read_text()
    require('int(rows[0]["length"]) == 248' in source,
            "stored 248-byte expectation absent from attributed consumer")
    semantic = PRIMARY.derive()
    require(semantic["status"] == "PASS: PRIMARY VM_TYPE EMPTY-PHASE FIX"
            and semantic["regression"]["fixed_boundary"]["status"] ==
                "PASS: EMPTY PHASE WAITS AND CONTINUES"
            and semantic["regression"]["unfixed_mutation"]["status"] == "TypeError"
            and semantic["fixture_contract"]["preload_only_rejected"] is True,
            "empty-phase semantic proof is not green")
    return {"format": "lisp65-c2.3-v1.6-recovery-sanitization-library-pin-attribution-v1",
        "recorded_on": "2026-08-24",
        "status": "ATTRIBUTED: V16CORE EMPTY-PHASE CHECKER PINS CODE SIZE",
        "inputs": {"Final_Red": bind(RED), "candidate_manifest": bind(MANIFEST),
            "candidate_blob": bind(BLOB), "candidate_ELF": bind(ELF),
            "candidate_PRG": bind(PRG), "live_checker": bind(GATE),
            "live_source": semantic["inputs"]["source"]},
        "drift": {"expected_by_checker": {"%read-line-loop_bytes": 248,
                    "claim_proxy": "exact code-object length"},
            "observed_candidate": {"%read-line-loop_bytes": rows[0]["length"],
                "blob_offset": rows[0]["blob_offset"],
                "manifest_blob_sha256": manifest["blob_sha256"]},
            "semantic_truth": {"fixture": semantic["fixture_contract"],
                "fixed": semantic["regression"]["fixed_boundary"],
                "unfixed_mutation": semantic["regression"]["unfixed_mutation"]}},
        "decision": {"class": "stored-world code-object size pin",
            "known_family": True, "product_defect": False,
            "reason": ("the later display-owner successor legitimately emits a "
                       "250-byte loop; the real empty-boundary fixture passes and "
                       "the unfixed semantic mutation still fails with TypeError"),
            "conversion": ("derive the emitted length from the candidate and gate "
                           "the claim through the empty-boundary semantic fixture "
                           "plus byte-identical emitted-vs-compiled code")},
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "successor_scope": ("One known-family replacement card under the 8fc42756 "
                            "self-disposition clause; no media or device contact.")}


def main() -> int:
    value = derive()
    OUT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    print(f"recovery sanitization library Red: {value['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
