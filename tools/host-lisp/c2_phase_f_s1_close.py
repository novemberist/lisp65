#!/usr/bin/env python3
"""Bind the complete Link-67 S1 attempt sequence without rewriting history."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
ATTEMPT1 = EVIDENCE / "c2.2-link67-f1-f2-s1-attempt1-harness-first-red.json"
ATTEMPT2 = EVIDENCE / "c2.2-link67-f1-f2-s1-hardware-receipt.json"
CONTRACT = ROOT / "config/c2.2-s1-freight-session.json"
PLAN = ROOT / "docs/planning/c2.2-f4-s1-freight-session.md"
LINK = EVIDENCE / "c2.2-product-link67-f1-f2-structural-receipt.json"
OUT = EVIDENCE / "c2.2-link67-f1-f2-s1-completion-receipt.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def binding(path: Path) -> dict:
    payload = path.read_bytes()
    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FIRST RED: {message}")


a1 = load(ATTEMPT1)
a2 = load(ATTEMPT2)
contract = load(CONTRACT)
link = load(LINK)

require(
    a1["status"] == "harness-first-red-invalid-fixed-delay-zero-product-rows",
    "attempt 1 lost its harness-only disposition",
)
require(a1["execution_accounting"]["accepted_product_rows"] == 0, "attempt 1 claims product rows")
require(a1["execution_accounting"]["hardware_attempts"] == 1, "attempt 1 count changed")
require(a2["status"] == "passed-Link67-F1-F2-S1-one-session-hardware", "attempt 2 is not green")
require(a2["summary"]["rows_passed"] == 12, "attempt 2 is not 12/12")
require(all(row["status"] == "passed" for row in a2["rows"]), "an S1 row is not green")
require(contract["status"] == "passed-link67-f1-f2-s1-hardware", "contract is not closed")
require(contract["session_policy"]["hardware_attempts_total"] == 2, "total attempt count is not two")
require(contract["session_policy"]["accepted_product_rows"] == 12, "accepted row count is not twelve")
require(link["product"]["sha256"] == contract["candidate"]["product_sha256"], "product identity diverged")
require(link["ELF"]["sha256"] == contract["candidate"]["elf_sha256"], "ELF identity diverged")

rows = {row["id"]: row for row in a2["rows"]}
expected_frames = {
    "boot-watch": (939, 1500),
    "f1-nary-cold": (1, 16),
    "f1-nary-warm": (0, 10),
    "nullary-cold-regression": (0, 16),
    "nullary-warm-regression": (0, 10),
}
for row_id, (frames, limit) in expected_frames.items():
    timing = rows[row_id]["timing"]
    require(timing["frames"] == frames, f"{row_id} frame count changed")
    require(timing["limit_frames"] == limit, f"{row_id} limit changed")

freezer = rows["idle-freezer-roundtrip"]
for bank in ("bank2", "bank3", "bank5"):
    require(
        freezer["identity_before"][bank]["sha256"] == freezer["identity_after"][bank]["sha256"],
        f"{bank} changed over Freezer",
    )
require(freezer["E000"]["preserved_bytes"] == 8190, "E000 preservation is not 8190/8192")
require(
    {item["address"] for item in freezer["E000"]["observed_differences"]} <= {"0xff83", "0xff84", "0xff86"},
    "E000 changed outside contract-listed live cells",
)

receipt = {
    "format": "lisp65-c2.2-link67-f1-f2-s1-completion-v1",
    "recorded_on": "2026-07-27",
    "status": "passed-Link67-F1-F2-S1-complete",
    "authority": {
        "contract": binding(CONTRACT),
        "session_note": binding(PLAN),
        "link_receipt": binding(LINK),
        "attempt_1_first_red": binding(ATTEMPT1),
        "attempt_2_hardware": binding(ATTEMPT2),
        "closure_driver": binding(Path(__file__).resolve()),
    },
    "execution_accounting": {
        "product_links": 1,
        "hardware_attempts_total": 2,
        "harness_invalid_attempts": 1,
        "valid_successful_device_sessions": 1,
        "accepted_product_rows": 12,
        "automatic_retries": 0,
    },
    "candidate": {
        "link": 67,
        "product_sha256": link["product"]["sha256"],
        "elf_sha256": link["ELF"]["sha256"],
        "core_identity": a2["device"]["core_identity"]["hex"],
    },
    "measurements": {
        row_id: rows[row_id]["timing"]["value_string"] for row_id in expected_frames
    },
    "claims": {
        "F1": "passed-on-metal",
        "F2": "passed-on-metal",
        "idle_Freezer": "passed-with-byteidentical-Bank2-Bank3-Bank5",
        "post_Freezer_REPL": rows["post-freezer-repl"]["visible_result"][0],
        "F3": contract["f3_disposition"]["status"],
    },
    "claim_limit": (
        "Closes only Link 67 S1 F1/F2 and listed regressions. "
        "No F3, while, C2.3, promotion, release or later freight claim."
    ),
}
OUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(
    "S1 PASS attempts=2 valid_sessions=1 rows=12/12 "
    f"product={receipt['candidate']['product_sha256']}"
)
