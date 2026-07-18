#!/usr/bin/env python3
"""Fail-closed audit for the shared F011 transaction-context contract."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/f011-transaction-context.json"
HEADER = ROOT / "src/f011_context.h"
SOURCES = {
    "workbench": ROOT / "src/io.c",
    "stager": ROOT / "scripts/r3-cold-stager-main.c",
    "bam-carrier": ROOT / "scripts/hw-workbench-bam-alloc-main.c",
    "chain-carrier": ROOT / "scripts/hw-workbench-chain-write-main.c",
    "directory-carrier": ROOT / "scripts/hw-workbench-dir-write-main.c",
}


class AuditError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def load_contract() -> dict[str, object]:
    value = json.loads(CONTRACT.read_text(encoding="utf-8"))
    require(value.get("format") == "lisp65-f011-transaction-context-v1", "contract format drift")
    require(value.get("version") == 1, "contract version drift")
    require(value.get("status") == "permanent-product-contract", "contract status drift")
    require(
        value.get("rule")
        == "every F011 or direct-SD transaction establishes its complete register context and inherits no mutable hardware state",
        "transaction ownership rule drift",
    )
    audit = value.get("register_audit")
    require(isinstance(audit, dict), "register audit missing")
    require(
        set(audit) == {"D02F", "D080", "D081", "D082", "D084-D086", "D680", "D681-D684", "D689", "D68B", "D68C-D68F", "SD-slot"},
        "register audit coverage drift",
    )
    case = value.get("permanent_hardware_case")
    require(isinstance(case, dict), "permanent hardware case missing")
    require(case.get("id") == "work-media-save-remount-read", "permanent hardware case drift")
    require(case.get("precondition") == "write-0x80-to-D689-immediately-before-save", "D689 precondition drift")
    require(case.get("postcondition") == "one-byte-0x00-readback-after-transaction", "D689 postcondition drift")
    require(
        case.get("medium") == "disposable-valid-non-product-1581-derived-from-L65WORK.D81",
        "permanent case media-policy drift",
    )
    guard = value.get("mount_token_guard")
    require(isinstance(guard, dict), "mount-token guard missing")
    require(guard.get("token") == "exact-D68B-plus-D68C-D68F", "mount-token identity drift")
    require(guard.get("mismatch_status") == 12, "mount-token mismatch status drift")
    require(
        guard.get("capture")
        == "after-valid-media-classification-before-transaction-bound-planning-or-first-write",
        "mount-token capture boundary drift",
    )
    require(
        guard.get("planning_read_failure")
        == "status-6-with-token-mismatch-reclassified-to-terminal-status-12-before-any-retry-or-write",
        "post-capture planning-read mismatch classification drift",
    )
    require(
        guard.get("stable_planning_read_failure")
        == "status-6-preserved-when-token-still-matches",
        "stable-token planning-read classification drift",
    )
    require(
        guard.get("planning_status_state")
        == "classified-return-is-published-through-m65d-status-from-the-same-value-planning-precedes-all-writes-so-partial-write-latch-remains-clear",
        "planning-read return and persistent status are not a single truth",
    )
    require(
        guard.get("mismatch_semantics")
        == "terminal-no-automatic-remount-or-retry-explicit-user-restart-only",
        "mount-token terminal semantics drift",
    )
    require(
        guard.get("residual_window_gate") == {
            "report": "build/products/workbench/overlay-stack-guard/f011-mount-window-audit.json",
            "source": "final-linked-product-disassembly",
            "cycles_including_last_D68F_read_and_D081_store": 30,
            "cycles_after_last_read_completion": 26,
            "nominal_nanoseconds_at_40_5_mhz": 740.741,
        },
        "mount-token residual-window measurement drift",
    )
    require(
        guard.get("window_classification")
        == "non-atomic-and-therefore-principally-Freezer-reachable",
        "mount-token window atomicity was overstated",
    )
    decision = guard.get("owner_residual_risk_decision")
    require(isinstance(decision, dict), "mount-token owner residual-risk decision missing")
    require(
        decision == {
            "accepted": True,
            "date": "2026-07-14",
            "stock_core_required": True,
            "atomicity_claim": False,
            "damage_bound": "one-sector-maximum-on-newly-mounted-medium-then-terminal-status-12",
            "user_message": "medium changed during write; check both disks",
            "upstream_candidate": "official-mega65-core-drive0-mount-lock-no-project-fork",
            "promotion_effect": "not-blocking-after-three-boundary-characterizations-and-normal-phase-oracles-pass",
        },
        "mount-token owner residual-risk decision drift",
    )
    phase_cases = value.get("permanent_media_change_cases")
    require(isinstance(phase_cases, dict), "media-change phase cases missing")
    require(
        phase_cases.get("automated") == [
            "token-change-during-post-capture-planning-read-status-12-zero-writes",
            "stable-token-planning-read-invalid-status-6-zero-writes",
            "token-change-before-data-write",
            "token-change-before-BAM-write",
            "token-change-before-directory-write",
        ],
        "media-change phase inventory drift",
    )
    require(
        phase_cases.get("residual_window_characterization") == [
            "one-foreign-data-sector-source-unchanged-status-12-stop",
            "one-foreign-BAM-sector-source-unchanged-status-12-stop",
            "one-foreign-directory-sector-source-unchanged-status-12-stop",
        ],
        "residual-window characterization inventory drift",
    )
    require(
        phase_cases.get("residual_window_claim")
        == "known-contract-boundary-characterized-not-a-safety-pass",
        "residual-window characterization was mislabeled as safety",
    )
    require(
        phase_cases.get("manual")
        == "one-real-Freezer-confirmation-after-normal-and-boundary-phase-cases-pass",
        "real-Freezer confirmation policy drift",
    )
    return value


def audit_sources() -> None:
    header = HEADER.read_text(encoding="utf-8")
    for token in (
        "LISP65_SD_REG_BUFFER_SELECT",
        "LISP65_F011_BUFFER_SELECTED",
        "lisp65_f011_take_context",
        "lisp65_f011_map_buffer",
        "lisp65_f011_unmap_buffer",
        "LISP65_SD_REG_MOUNT_CONTROL",
        "LISP65_SD_REG_MOUNT_BASE3",
        "lisp65_f011_mount_token_matches",
    ):
        require(token in header, f"shared context header missing {token}")
    require("0x80u" not in re.sub(r"/\*.*?\*/|//.*", "", header, flags=re.S), "shared header must never select direct-SD buffer")

    for label, path in SOURCES.items():
        text = path.read_text(encoding="utf-8")
        require(re.search(r'#include\s+"(?:\.\./src/)?f011_context\.h"', text) is not None, f"{label} does not consume shared context")
        require("lisp65_f011_take_context();" in text, f"{label} does not claim F011 context")
        require("lisp65_f011_map_buffer();" in text, f"{label} does not map through shared context")
        require("lisp65_f011_unmap_buffer();" in text, f"{label} does not close the buffer window")
        require(not re.search(r"0xD680\s*\)\s*=\s*2\b", text, re.I), f"{label} still issues a raw-SD read")
        require(not re.search(r"0xD689\s*\)\s*=", text, re.I), f"{label} bypasses shared BUFSEL ownership")
    workbench = SOURCES["workbench"].read_text(encoding="utf-8")
    require("disk_io_ready" not in workbench and "disk_ensure" not in workbench, "workbench still caches I/O context")
    require("m65_io_enable();\n    lisp65_f011_take_context();" in workbench, "workbench does not re-establish I/O mode per operation")
    for token in (
        "io_disk_write_sector_guarded",
        "LISP65_DISK_STATUS_MEDIA_CHANGED = 12",
        "final predicate before the trigger",
        "disk_transaction_mount_token_op",
        "disk_transaction_mount_token_op(2)",
        "io_disk_transaction_classify_status",
    ):
        require(token in workbench, f"workbench mount guard missing {token}")
    require(
        workbench.count("disk_transaction_mount_token_op(0)") >= 5,
        "workbench does not guard all RMW/write/readback boundaries",
    )
    guard_asm = (ROOT / "src/f011_guarded_write.s").read_text(encoding="utf-8").lower()
    for token in (
        "lisp65_f011_mount_token_op",
        "lda\t$d68b,x",
        "sta\t$d081",
        ".lf011_mount_token_valid",
    ):
        require(token in guard_asm, f"product assembler guard missing {token}")
    workbench_mk = (ROOT / "config/workbench.mk").read_text(encoding="utf-8")
    require("src/f011_guarded_write.s" in workbench_mk, "product does not link the F011 assembler guard")
    m65d = (ROOT / "lib/m65-disk.lisp").read_text(encoding="utf-8")
    require("(%m65d-set 12 t)" in m65d, "M65D does not expose terminal media-change status")
    require("(%disk-write-sector)" in m65d, "M65D does not capture the native D68B-D68F token")
    require(
        "(%m65d-set\n             (%disk-write-sector (%m65d-run-authorized name src new-only))\n             nil)" in m65d,
        "M65D does not publish the classified planning-read status through its single status state",
    )
    require("%disk-byte 256" not in m65d, "M65D duplicates the private native mount token")
    ide = (ROOT / "lib/ide-disk.lisp").read_text(encoding="utf-8")
    require("(if (= status 8)" in ide, "IDE pretransaction remount path missing")
    retry_tail = ide[ide.index("(if (= status 8)"):ide.index("(m65d-save file source)))") + len("(m65d-save file source)))")]
    require("status 12" not in retry_tail and "(= status 12)" not in retry_tail, "IDE retries terminal status 12")
    stager = SOURCES["stager"].read_text(encoding="utf-8")
    require("io_enable();\n    lisp65_f011_take_context();" in stager, "stager does not re-establish I/O mode per operation")


def audit_matrix() -> None:
    cases = json.loads((ROOT / "tests/bytecode/dialect-v2/r3-boot/cases.json").read_text(encoding="utf-8"))["cases"]
    case = next((item for item in cases if item.get("id") == "work-media-save-remount-read"), None)
    require(isinstance(case, dict), "work persistence matrix case missing")
    combined = " ".join(str(case.get(key, "")) for key in ("setup", "action", "expected", "oracle"))
    require("D689" in combined and "0x80" in combined and "0x00" in combined, "matrix does not pin forced BUFSEL pre/post state")
    swap = next((item for item in cases if item.get("id") == "mid-write-media-swap-abort"), None)
    require(isinstance(swap, dict), "media-change matrix case missing")
    swap_text = " ".join(str(swap.get(key, "")) for key in ("setup", "action", "expected", "oracle"))
    for token in (
        "D68B-D68F", "planning read", "stable-token", "zero writes",
        "status 12", "persistent status", "byteidentical", "Freezer", "one sector",
        "not a safety PASS",
    ):
        require(token in swap_text, f"media-change matrix case does not pin {token}")
    harness = json.loads((ROOT / "config/r6-g6-harness.json").read_text(encoding="utf-8"))
    row = next((item for item in harness["cases"] if item.get("id") == "work-media-save-remount-read"), None)
    require(isinstance(row, dict), "R6/G6 work persistence case missing")
    evidence = row.get("required_evidence")
    require(isinstance(evidence, list), "R6/G6 work persistence evidence malformed")
    require("bufsel-precondition" in evidence and "bufsel-postcondition" in evidence, "R6/G6 BUFSEL evidence missing")
    swap_row = next((item for item in harness["cases"] if item.get("id") == "mid-write-media-swap-abort"), None)
    require(isinstance(swap_row, dict), "R6/G6 media-change case missing")
    require(
        swap_row.get("procedure") == "phase-injection-plus-freezer-boundary",
        "R6/G6 media-change procedure does not characterize the accepted boundary",
    )
    swap_evidence = swap_row.get("required_evidence")
    require(isinstance(swap_evidence, list), "R6/G6 media-change evidence malformed")
    for evidence_id in (
        "phase-injection-report", "clean-media-b-baseline", "manual-pre-media-a",
        "manual-pre-media-b", "manual-expected-content", "freezer-boundary-transcript", "manual-post-media-a",
        "manual-post-media-b", "two-media-oracle",
    ):
        require(evidence_id in swap_evidence, f"R6/G6 media-change evidence missing {evidence_id}")
    trigger = swap_row.get("manual_trigger")
    require(isinstance(trigger, dict), "R6/G6 public Freezer trigger missing")
    require(
        trigger == {
            "entrypoint": "m65d-save",
            "form": '(m65d-save "g6swap" (progn (poke 208 32 2) g6src))',
            "signal": "red-border-immediately-before-public-entry",
            "operator_action": "on-red-open-freezer-and-mount-media-b",
            "acceptance": "terminal-return-12-and-persistent-status-12-plus-two-media-oracle",
            "nonacceptance": "any-other-result-or-private-helper-use-is-receiptless",
            "forbidden_symbol_prefixes": ["%m65d-"],
        },
        "R6/G6 public Freezer trigger contract drift",
    )
    require("%m65d-" not in trigger["form"], "R6/G6 Freezer trigger names a private M65D helper")


def main() -> int:
    try:
        load_contract()
        audit_sources()
        audit_matrix()
    except (AuditError, OSError, UnicodeError, json.JSONDecodeError, StopIteration) as exc:
        print(f"f011-transaction-context: FAIL: {exc}", file=sys.stderr)
        return 1
    print("f011-transaction-context: PASS full register audit + permanent forced-BUFSEL case")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
