#!/usr/bin/env python3
"""Keep the v2.0 CPU-transport witness in its sealing era.

The historical reconciliation receipt recorded the complete working-tree
identity of ``c2_product_runtime.h`` even though its claim consumes only five
address constants. Recomputing that sealed receipt after every unrelated
header edit is the evidence-era treadmill. This companion leaves the old
bytes untouched, reconstructs their header input at the sealing commit, and
derives the relevant constants from the live header at check time without
persisting a live file hash.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v20_cpu_transport_reconciliation as BASE  # noqa: E402
import evidence_era as ERA  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = ARCH / (
    "c2.3-v2.0-cpu-transport-reconciliation-rebind-2026-08-25.json")
SEAL_ERA_COMMIT = "7a4f05b583d966d7f7e132a96aa3c4cddfea4481"
FORMAT = "lisp65-c2.3-v2.0-cpu-transport-reconciliation-rebind-v1"
MUTATION_NAMES = [
    "collapse-sealed-era-to-live",
    "restore-working-tree-binding",
    "change-live-semantic-address",
    "rewrite-historical-witness",
    "drop-historical-mutation",
]


class RebindError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RebindError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def live_semantics() -> dict[str, int]:
    text = BASE.HEADER.read_text(encoding="utf-8")
    return {
        "shelf_physical": BASE.macro(text, "LISP65_C2_SHELF_PHYSICAL"),
        "session_physical": BASE.macro(text, "LISP65_C2_SESSION_PHYSICAL"),
        "c2d_bank": BASE.macro(text, "LISP65_C2D_BANK"),
        "c2d_base": BASE.macro(text, "LISP65_C2D_BASE"),
        "c2d_region_bytes": BASE.macro(text, "LISP65_C2D_REGION_BYTES"),
    }


def expected_semantics(historical: dict[str, Any]) -> dict[str, int]:
    sources = historical["library_load_sources"]
    c2d_start = int(sources["initial_c2d"]["physical_start"], 16)
    c2d_end = int(sources["initial_c2d"]["owned_region_end_exclusive"], 16)
    return {
        "shelf_physical": int(sources["shelf"]["physical_start"], 16),
        "session_physical": int(
            sources["session_successor"]["physical_start"], 16),
        "c2d_bank": c2d_start // 0x10000,
        "c2d_base": c2d_start % 0x10000,
        "c2d_region_bytes": c2d_end - c2d_start,
    }


def derive() -> dict[str, Any]:
    historical = load(BASE.RECEIPT)
    BASE.audit(historical)
    old_mutations = historical.get("mutations")
    require(isinstance(old_mutations, dict)
            and old_mutations.get("count") == 14
            and len(old_mutations.get("rejected", {})) == 14,
            "historical reconciliation mutation witness drift")
    sealed_header = ERA.era_bind(SEAL_ERA_COMMIT, BASE.HEADER)
    require(historical["inputs"]["runtime_header"] == sealed_header,
            "historical header input escaped its sealing era")
    semantics = live_semantics()
    require(semantics == expected_semantics(historical),
            "live CPU-transport address semantics changed")
    require(bind(BASE.HEADER) != sealed_header,
            "evidence-era fixture no longer demonstrates the live drift")
    return {
        "format": FORMAT,
        "recorded_on": "2026-08-25",
        "status": "PASS: sealed CPU reconciliation; live semantics derived",
        "authority": {
            "historical_receipt": bind(BASE.RECEIPT),
            "sealing_commit": SEAL_ERA_COMMIT,
            "sealed_runtime_header": sealed_header,
        },
        "split": {
            "historical_receipt_rewritten": False,
            "live_header_identity_persisted": False,
            "sealed_witness": "runtime-header identity at sealing commit",
            "live_check": "five CPU-transport address constants derived at check time",
        },
        "live_semantics": semantics,
        "historical_claim": {
            "status": historical["status"],
            "reads_in_proven_CPU_domain": historical[
                "library_load_sources"]["reads_in_proven_CPU_domain"],
            "reads_outside_proven_CPU_domain": historical[
                "library_load_sources"]["reads_outside_proven_CPU_domain"],
            "mutation_count": old_mutations["count"],
        },
        "claim_limit": (
            "Evidence-era conversion only. The v2.0 receipt remains byte-exact; "
            "the live gate derives its five relevant address constants without "
            "persisting the working-tree header identity. No product, medium, "
            "card, or device action."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(value.get("format") == FORMAT
            and value.get("status") ==
                "PASS: sealed CPU reconciliation; live semantics derived",
            "CPU reconciliation rebind status drift")
    require(value["split"] == {
        "historical_receipt_rewritten": False,
        "live_header_identity_persisted": False,
        "sealed_witness": "runtime-header identity at sealing commit",
        "live_check": "five CPU-transport address constants derived at check time",
    }, "sealed/live evidence split drift")
    require(value["historical_claim"] == {
        "status": "DESK-GREEN; NO-CPU-TRANSPORT-FOR-LINK106; RING-STILL-REQUIRED",
        "reads_in_proven_CPU_domain": 0,
        "reads_outside_proven_CPU_domain": 346298,
        "mutation_count": 14,
    }, "historical CPU reconciliation claim drift")
    require(value["authority"]["sealing_commit"] == SEAL_ERA_COMMIT
            and value["authority"]["sealed_runtime_header"] ==
                ERA.era_bind(SEAL_ERA_COMMIT, BASE.HEADER),
            "CPU reconciliation sealing-era authority drift")
    if verify:
        require(value == derive(), "CPU reconciliation rebind drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "collapse-sealed-era-to-live": lambda x: x["authority"].update(
            sealed_runtime_header=bind(BASE.HEADER)),
        "restore-working-tree-binding": lambda x: x["split"].update(
            live_header_identity_persisted=True),
        "change-live-semantic-address": lambda x: x["live_semantics"].update(
            shelf_physical=0x08100001),
        "rewrite-historical-witness": lambda x: x["split"].update(
            historical_receipt_rewritten=True),
        "drop-historical-mutation": lambda x: x["historical_claim"].update(
            mutation_count=13),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate(trial, verify=True)
        except (RebindError, BASE.ReconciliationError):
            rejected.append(name)
    require(rejected == MUTATION_NAMES,
            "CPU reconciliation rebind mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "CPU reconciliation rebind receipt exists")
    value = derive()
    validate(value, verify=True)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("CPU reconciliation evidence-era rebind: RECORD PASS mutations=5")


def check() -> None:
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == MUTATION_NAMES and mutations(value) == MUTATION_NAMES,
            "CPU reconciliation rebind mutation inventory drift")
    print("CPU reconciliation evidence-era rebind: CHECK PASS "
          "sealed=unchanged live-hash=not-persisted mutations=5")


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in ("record", "check"),
            "usage: c2_v20_cpu_transport_reconciliation_rebind_20260825.py record|check")
    {"record": record, "check": check}[sys.argv[1]]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RebindError, BASE.ReconciliationError, ERA.EraError, OSError,
            ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"CPU reconciliation evidence-era rebind: FAIL {error}",
              file=sys.stderr)
        raise SystemExit(2)
