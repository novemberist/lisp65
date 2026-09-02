#!/usr/bin/env python3
"""Seal the one-shot final v2.0 Comfort composition device result."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SESSION = ROOT / "config/c2-v200-comfort-return-device-session-r2.json"
COMPOSITION = ARCH / (
    "c2.3-v2.0-comfort-return-final-composition-receipt.json")
RECEIPT = ARCH / (
    "c2.3-v2.0-comfort-return-final-device-result-receipt.json")
REPORT = ROOT / (
    "docs/planning/v2.0.0-comfort-return-final-device-result.md")
DEVICE = ROOT / "build/c2.3/v2.0-comfort-return-final-composition/device"
STATUS = "FINAL RED: COMFORT DESCOPED; BLOCK 3 INDEPENDENTLY OPEN"


class ResultError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResultError(message)


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
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(canonical(value))
    temporary.replace(path)


def readback(name: str, session_row: dict[str, Any]) -> dict[str, Any]:
    path = DEVICE / f"{name}-readback.d81"
    identity = bind(path)
    require(identity["bytes"] == session_row["bytes"]
            and identity["sha256"] == session_row["sha256"],
            f"{name} readback differs from the bound medium")
    return identity


def result_value() -> dict[str, Any]:
    session, composition = load(SESSION), load(COMPOSITION)
    require(session["status"] ==
            "READY: OWNER V2.0 FINAL COMFORT COMPOSITION CONTACT"
            and composition["status"] ==
            "PASS: FINAL COMFORT COMPOSITION READY",
            "final composition/session authority drift")
    require(session["media"]["product"]["sha256"] ==
            "e20c161509f790aeecd1f6fa008e84bd2020f303a26500a41df49b9c980b0d0c"
            and session["media"]["library"]["sha256"] ==
            "22f1e73c7e2903bc4a9ba813e0988ffea248a68616a40eb507961418a2ab37e2",
            "final media identities drift")
    return {
        "format": "lisp65-c2-v200-comfort-return-final-device-result-v1",
        "recorded_on": "2026-08-31",
        "status": STATUS,
        "authority": {
            "composition": bind(COMPOSITION),
            "session": bind(SESSION),
            "decision_table": session["decision_table"],
        },
        "media": {
            "product": {
                "source": session["media"]["product"],
                "readback": readback("product", session["media"]["product"]),
                "byteidentical": True,
            },
            "library": {
                "source": session["media"]["library"],
                "readback": readback("library", session["media"]["library"]),
                "byteidentical": True,
                "index_rows": ["repl-comfort"],
                "v16core_present": False,
            },
        },
        "contact": {
            "count": 1,
            "retries": 0,
            "automated_device_access_after_boot": False,
            "CPU_stopped": False,
            "reset_after_result": False,
            "owner_observation": {
                "native_prompt_before_library": "lisp65>",
                "library_mounted_physically": True,
                "submitted_forms": [
                    "(require 'repl-comfort)",
                    "(repl)",
                    "<empty Comfort line>",
                ],
                "require_result": "t",
                "comfort_prompt": "l65>",
                "empty_line_result":
                    "*** undefined function: %ide-line-net-depth",
                "recovery_prompt": "lisp65>",
                "wrong_argument_count_loop": False,
            },
        },
        "session_progress": {
            "started_groups": ["C1"],
            "failed_group": "C1",
            "unstarted_groups": ["C2", "C3", "C5", "C4", "C6", "C7"],
            "latch_read": False,
            "input_counters_read": False,
            "D5_read": False,
        },
        "interpretation": {
            "classification": "daily-use-blocker",
            "decision_table_branch":
                "final composition contact red: Comfort descopes; no further medium",
            "comfort_v2_0": "descoped-and-sealed",
            "further_comfort_media": "forbidden",
            "remaining_composition_media_budget": 0,
            "block3": "independently-open",
            "v16core": "absent-from-active-session-and-medium",
            "mechanism_claim":
                "not-attributed; device runtime could not resolve one host-closed resident reference",
        },
        "claim_limit": {
            "accepts": [
                "the final no-v16core medium reached Comfort",
                "C1 failed on undefined %ide-line-net-depth",
                "the pre-bound descope branch fired",
                "Block 3 remains independently open",
            ],
            "excludes": [
                "C2-C7 acceptance",
                "Comfort freight mechanism attribution",
                "latch result",
                "input fidelity result",
                "D5",
                "Block-3 acceptance",
                "release",
            ],
        },
        "next": "seal Comfort evidence; proceed independently to Block 3",
    }


def validate(value: dict[str, Any]) -> None:
    session = load(SESSION)
    require(value["status"] == STATUS
            and value["authority"]["composition"] == bind(COMPOSITION)
            and value["authority"]["session"] == bind(SESSION)
            and value["authority"]["decision_table"] ==
                session["decision_table"],
            "result authority drift")
    for name in ("product", "library"):
        medium = value["media"][name]
        require(medium["source"]["sha256"] ==
                medium["readback"]["sha256"]
                and medium["source"]["bytes"] ==
                medium["readback"]["bytes"]
                and medium["byteidentical"] is True,
                f"{name} same-world readback claim drift")
    observation = value["contact"]["owner_observation"]
    require(value["contact"]["count"] == 1
            and value["contact"]["retries"] == 0
            and value["contact"]["automated_device_access_after_boot"] is False
            and observation["submitted_forms"] == [
                "(require 'repl-comfort)", "(repl)",
                "<empty Comfort line>"]
            and observation["require_result"] == "t"
            and observation["comfort_prompt"] == "l65>"
            and observation["empty_line_result"] ==
                "*** undefined function: %ide-line-net-depth"
            and observation["recovery_prompt"] == "lisp65>",
            "raw owner observation drift")
    progress = value["session_progress"]
    require(progress == {
        "started_groups": ["C1"],
        "failed_group": "C1",
        "unstarted_groups": ["C2", "C3", "C5", "C4", "C6", "C7"],
        "latch_read": False,
        "input_counters_read": False,
        "D5_read": False,
    }, "session progress or claim boundary drift")
    decision = value["interpretation"]
    require(decision["classification"] == "daily-use-blocker"
            and decision["decision_table_branch"] ==
                session["decision_table"]["daily-use-blocker"]
            and decision["comfort_v2_0"] == "descoped-and-sealed"
            and decision["further_comfort_media"] == "forbidden"
            and decision["remaining_composition_media_budget"] == 0
            and decision["block3"] == "independently-open"
            and decision["v16core"] ==
                "absent-from-active-session-and-medium",
            "pre-bound decision-table result drift")
    require(value["media"]["library"]["index_rows"] == ["repl-comfort"]
            and value["media"]["library"]["v16core_present"] is False,
            "active v16core removal drift")


REPORT_TEXT = """# v2.0 final Comfort device result

Status: **FINAL RED — Comfort descoped; Block 3 independently open**

The one remaining composition contact used the byte-read-back product
`e20c1615…` and the final one-row library `22f1e73c…`.  The library contained
only `repl-comfort`; `v16core` was absent.

C1 reached farther than either predecessor: `(require 'repl-comfort)` returned
`t`, `(repl)` displayed `l65>`, and no `wrong argument count` loop appeared.
The first empty Comfort line then produced exactly
`*** undefined function: %ide-line-net-depth` and recovered to `lisp65>`.
That violates C1 and is a daily-use blocker.

The pre-bound decision table therefore fires without a new repair decision:
Comfort is descoped from v2.0, its evidence is sealed, the remaining media
budget is zero, and no further Comfort medium is permitted.  Active v2.0
session/media population has no `v16core`; historical sealed evidence is not
rewritten.

Only C1 began.  C2 through C7 did not run, so this contact makes no latch,
input-counter, D5, Block-3 or release claim.  The missing-function mechanism
is not attributed in this cycle; the narrow observation is preserved for a
future return.

Block 3 remains independently open.  Its `$22` gate was resolved separately
and its scanner/blink freight does not consume Comfort code.
"""


def build() -> dict[str, Any]:
    require(not RECEIPT.exists(), "final device result is one-shot")
    value = result_value()
    validate(value)
    write(RECEIPT, value)
    REPORT.write_text(REPORT_TEXT, encoding="utf-8")
    return value


def check() -> dict[str, Any]:
    value = load(RECEIPT)
    validate(value)
    require(REPORT.read_text(encoding="utf-8") == REPORT_TEXT,
            "final device-result report drift")
    print("v2.0 final Comfort device result: CHECK PASS "
          "Comfort=descoped Block3=open media=0")
    return value


def selftest() -> None:
    value = load(RECEIPT)
    mutations = [
        ("accept-Comfort", lambda v: v["interpretation"].__setitem__(
            "comfort_v2_0", "accepted")),
        ("permit-another-medium", lambda v: v["interpretation"].__setitem__(
            "further_comfort_media", "permitted")),
        ("reopen-budget", lambda v: v["interpretation"].__setitem__(
            "remaining_composition_media_budget", 1)),
        ("close-Block3", lambda v: v["interpretation"].__setitem__(
            "block3", "closed")),
        ("reintroduce-v16core", lambda v: v["media"]["library"].__setitem__(
            "v16core_present", True)),
        ("erase-error", lambda v: v["contact"]["owner_observation"].__setitem__(
            "empty_line_result", "lisp65>")),
        ("claim-latch", lambda v: v["session_progress"].__setitem__(
            "latch_read", True)),
        ("claim-C2", lambda v: v["session_progress"]["started_groups"].append(
            "C2")),
        ("allow-retry", lambda v: v["contact"].__setitem__("retries", 1)),
    ]
    rejected = 0
    for name, mutate in mutations:
        candidate = copy.deepcopy(value)
        mutate(candidate)
        try:
            validate(candidate)
        except ResultError:
            rejected += 1
        else:
            raise ResultError(f"mutation survived: {name}")
    require(rejected == len(mutations), "mutation rejection count drift")
    print(f"v2.0 final Comfort device result: SELFTEST PASS mutations={rejected}")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "build":
        build()
        check()
    elif action in ("check", "source-check"):
        check()
    elif action == "selftest":
        selftest()
    else:
        raise ResultError("usage: build|check|source-check|selftest")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v2.0 final Comfort device result: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
