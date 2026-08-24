#!/usr/bin/env python3
"""Attribute the post-R1 capture guard red on the frozen liveness final ELF."""

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

from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
FINAL_RED = ARCH / "c2.3-v1.6-liveness-fix-scope-floor-card-final-red.json"
ELF = (ROOT / "build/c2.3/v1.6-liveness-fix-scope-floor-card/wplto/"
       "lisp65-c2-substitution-linked.prg.elf")
GUARD = ROOT / "tools/host-lisp/c2_v160_input_fidelity_reopen_card.py"
OUT = ARCH / "c2.3-v1.6-liveness-capture-successor-pin-attribution.json"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    red = json.loads(FINAL_RED.read_text(encoding="utf-8"))
    require(red["error"]["message"] ==
            "post-R1 capture changed abort/facade contracts"
            and red["attempt_accounting"]["cards_consumed"] == 1
            and red["attempt_accounting"]["WPLTO_runs"] == 1,
            "frozen liveness Final Red drift")
    source = GUARD.read_text(encoding="utf-8")
    require("service.bytes == 1382" in source
            and "padding.bytes == 10" in source
            and "abort.bytes == 134" in source
            and "facade.bytes == 98" in source
            and "entry.bytes == 9" in source,
            "stored capture-successor witness drift")

    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    service = truth.section(".lisp65_c2_mapped_far_service")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    abort = truth.symbol("c2_abort_driver")
    abort_entry = truth.symbol("c2_abort_driver_facade")
    padding = truth.symbol("__lisp65_c2_mapped_far_facade_padding")
    walker = truth.symbol("c2_rtov_retire_continuations")
    retire_entry = truth.symbol("c2_rtov_retire_continuations_facade")
    stub = truth.symbol("c2_retired_continuation_stub")

    observed = {"service_bytes": service.bytes,
        "abort_body_bytes": abort.bytes, "facade_bytes": facade.bytes,
        "abort_entry_bytes": abort_entry.bytes, "padding_bytes": padding.bytes,
        "retirement_walker_bytes": walker.bytes,
        "retirement_entry_bytes": retire_entry.bytes,
        "retired_stub_bytes": stub.bytes}
    stored = {"service_bytes": 1382, "abort_body_bytes": 134,
        "facade_bytes": 98, "abort_entry_bytes": 9, "padding_bytes": 10}
    require(observed == {"service_bytes": 1425, "abort_body_bytes": 134,
            "facade_bytes": 98, "abort_entry_bytes": 9, "padding_bytes": 0,
            "retirement_walker_bytes": 43, "retirement_entry_bytes": 9,
            "retired_stub_bytes": 1},
            "candidate does not match authorized liveness freight")
    unchanged = tuple(name for name in ("abort_body_bytes", "facade_bytes",
                       "abort_entry_bytes") if observed[name] == stored[name])
    changed = tuple(name for name in ("service_bytes", "padding_bytes")
                     if observed[name] != stored[name])
    require(unchanged == ("abort_body_bytes", "facade_bytes",
                          "abort_entry_bytes")
            and changed == ("service_bytes", "padding_bytes"),
            "capture guard delta is not exactly the liveness successor")

    value = {
        "format": "lisp65-c2-v160-liveness-capture-successor-pin-attribution-v1",
        "recorded_on": "2026-08-20",
        "status": "ATTRIBUTED: CAPTURE GUARD STORED R1 WORLD REJECTED LIVENESS SUCCESSOR",
        "evidence": {"Final_Red": bind(FINAL_RED), "final_ELF": bind(ELF),
                     "guard_source": bind(GUARD)},
        "stored_guard_world": stored,
        "candidate_world": observed,
        "delta": {"changed_only": list(changed),
                  "unchanged": list(unchanged),
                  "service_growth_bytes": service.bytes - stored["service_bytes"],
                  "padding_consumed_bytes": stored["padding_bytes"] - padding.bytes},
        "classification": {
            "family": "stored-world exact freight identities in a successor guard",
            "mechanism_fully_attributed": True,
            "product_defect": False,
            "scope_floor_conversions_passed": True,
            "authorized_liveness_freight_present": True},
        "required_successor_form": {
            "fixed_contracts": {"facade_bytes": 98, "abort_body_bytes": 134,
                                "abort_entry_bytes": 9},
            "freight_rule": "service size and facade members derive from the active final candidate",
            "capacity_rule": "mapped Far Service remains <= 1499 bytes",
            "mutation": "reintroduced 1382/10 predecessor equality fails"},
        "execution": {"WPLTO_runs": 0, "product_links": 0,
                      "media_builds": 0, "device_contacts": 0},
        "claim_limit": "Host-only attribution; no successor card is authorized by this receipt."
    }
    OUT.write_bytes(canonical(value))
    print("v1.6 liveness capture successor attribution: PASS "
          "stored=1382/10 candidate=1425/0 unchanged=134/98/9")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
