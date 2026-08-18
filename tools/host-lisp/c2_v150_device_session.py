#!/usr/bin/env python3
"""Prepare and close the owner-guided v1.5 Link-97 D1-D5 session."""

from __future__ import annotations

import argparse
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
import c2_live_repl_ftp_crossing_gate as CROSSING  # noqa: E402
import repl_screen_check as SCREEN  # noqa: E402


CONFIG = ROOT / "config/c2-v150-link97-device-session.json"
ROWS = ROOT / "config/c2-v150-link97-device-rows.json"
CONTRACT = ROOT / "config/c2-v150-release-contract.json"
MEDIA = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-link97-media-closure-receipt.json")
TRACE = ROOT / "config/c2-trace-core-abi-device-session.json"
DEFSTRUCT = ROOT / "config/c2-terminal-return-guard-link96-device-session.json"
RUNNER = ROOT / "scripts/c2-v150-link97-hw.sh"
OUT = ROOT / "build/c2.3/v1.5.0-link97-device-session"
PREP = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-link97-device-session-preparation-receipt.json")
RESULT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-link97-device-session-receipt.json")
FORMAT = "lisp65-c2.3-v150-link97-device-session-preparation-v1"
STATUS = "V150-LINK97-D1-D5-PREPARED-NOT-RUN"


class SessionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SessionError(message)


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


def rows_contract(value: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    value = value or load(ROWS)
    rows = value.get("rows", [])
    ids = [row.get("id") for row in rows]
    require(
        value.get("format") == "lisp65-c2-v150-link97-device-rows-v1"
        and value.get("status") == "prepared-not-run"
        and value.get("session_authority") == CONFIG.relative_to(ROOT).as_posix()
        and len(rows) == 19 and len(ids) == len(set(ids))
        and [row["phase"] for row in rows].count("D2") == 7
        and [row["phase"] for row in rows].count("D3") == 3
        and [row["phase"] for row in rows].count("D4") == 4
        and [row["phase"] for row in rows].count("D5") == 5,
        "v1.5 flattened D1-D5 row shape drift")
    session = load(CONFIG)
    contract = load(CONTRACT)
    trace = load(TRACE)
    defstruct = load(DEFSTRUCT)
    require(
        session["order"] == ["D1", "D2", "D3", "D4", "D5"]
        and session["release_terminal_row"] == "D5"
        and session["input"] == {
            "one_form_per_submission": True,
            "owner_physical_keyboard": True,
            "polling_during_persistent_form": False,
            "virtual_transport_forbidden": True,
        }
        and [row["form"] for row in rows[:7]] == session["rows"]["D2"]["forms"]
        and [row["form"] for row in rows[7:10]] == session["rows"]["D3"]["forms"]
        and [row["quiet_floor_seconds"] for row in rows[7:10]]
            == session["rows"]["D3"]["quiet_floor_seconds"]
        and [row["form"] for row in rows[10:14]] == session["rows"]["D4"]["forms"]
        and rows[13]["timing_authority"].startswith("structural 60/62-frame")
        and session["rows"]["D4"]["ceremony_max_frames"]
            == contract["device"]["ceremony_frames"]["release_max"] == 72
        and [row["form"] for row in rows[15:]]
            == [row["form"] for row in contract["device"]["performance_smokes"]]
        and [row["oracle"]["max_frames"] for row in rows[15:]]
            == [row["max_frames"] for row in contract["device"]["performance_smokes"]]
        and [row["oracle"]["value"] for row in rows[15:]]
            == [row["expect"] for row in contract["device"]["performance_smokes"]]
        and rows[14]["form"]
            == contract["device"]["performance_smokes"][-1]["setup"],
        "v1.5 flattened rows do not derive from frozen session/release contract")
    trace_rows = trace["rows"]
    require(
        rows[0]["form"] == trace_rows[0]["form"]
        and [row["form"] for row in rows[2:7]]
            == [row["form"] for row in trace_rows[1:]]
        and [row["form"] for row in rows[7:10]]
            == [row["form"] for row in defstruct["rows"]],
        "v1.5 trace/defstruct predecessor row identity drift")
    return rows


def runner_gate(source: str | None = None) -> dict[str, Any]:
    text = RUNNER.read_text(encoding="utf-8") if source is None else source
    CROSSING.audit_runner(RUNNER, text)
    required = [
        "dry-run|stage|confirm-liveness|confirm-library|wait-row|capture-final",
        "# ACTIVE-FORM-BEGIN", "# ACTIVE-FORM-END",
        'sleep "$quiet"', 'capture_screen "row-$row"',
        'python3 "$PY" verify-row',
        'if [ "$row" = d3-make-point ]; then',
        'python3 "$PY" verify-guard', 'python3 "$PY" record',
    ]
    require(all(token in text for token in required),
            "v1.5 runner ownership/observation token absent")
    require(text.count('python3 "$PY" verify-guard') == 2
            and 'd3-terminal-return-guard.bin' in text
            and 'final-terminal-return-guard.bin' in text,
            "v1.5 D3/final guard readback ownership drift")
    confirm = text.split('if [ "$ACTION" = confirm-library ]; then', 1)[1]
    confirm = confirm.split("\nfi\n", 1)[0]
    require('boot-liveness-owner-confirmed' in confirm,
            "v1.5 library handoff bypasses owner boot-liveness evidence")
    active = text.split("# ACTIVE-FORM-BEGIN", 1)[1].split(
        "# ACTIVE-FORM-END", 1)[0]
    require("$M65" not in active and "capture_screen" not in active
            and "mega65_ftp" not in active and "sleep" in active,
            "v1.5 active form window admits an observer")
    return {"physical_rows": 19, "post_boot_ftp_invocations": 0,
            "active_form_observations": 0, "guard_readbacks": 2}


def rejected_mutations(rows_value: dict[str, Any], source: str) -> list[str]:
    cases: dict[str, Callable[[], None]] = {}

    def row_case(name: str, mutate: Callable[[dict[str, Any]], None]) -> None:
        def run() -> None:
            value = deepcopy(rows_value); mutate(value); rows_contract(value)
        cases[name] = run

    row_case("drop-row", lambda x: x["rows"].pop())
    row_case("duplicate-id", lambda x: x["rows"][-1].update(
        id=x["rows"][0]["id"]))
    row_case("virtual-form", lambda x: x["rows"][0].update(form="(+ 1 2)"))
    row_case("short-defstruct-floor", lambda x: x["rows"][8].update(
        quiet_floor_seconds=30))
    row_case("soften-time-bound", lambda x: x["rows"][15]["oracle"].update(
        max_frames=3))
    row_case("pin-ceremony-as-remeasurement", lambda x: x["rows"][13].update(
        timing_authority="fresh exact hardware measurement"))

    source_cases = {
        "observe-active-form": source.replace(
            '  sleep "$quiet"\n  # ACTIVE-FORM-END',
            '  capture_screen forbidden\n  sleep "$quiet"\n  # ACTIVE-FORM-END', 1),
        "drop-guard-readback": source.replace(
            '    python3 "$PY" verify-guard --path "$OUT/d3-terminal-return-guard.bin"',
            "    : # guard readback removed", 1),
        "drop-row-oracle": source.replace(
            '  python3 "$PY" verify-row --row "$row" \\\n',
            '  : # row oracle removed \\\n', 1),
        "skip-liveness-owner": source.replace(
            '&& [ -e "$OUT/boot-liveness-owner-confirmed" ]',
            '&& [ -e "$OUT/freezer-mount-required" ]', 1),
    }
    for name, candidate in source_cases.items():
        cases[name] = lambda candidate=candidate: runner_gate(candidate)

    rejected: list[str] = []
    for name, run in cases.items():
        try:
            run()
        except (SessionError, CROSSING.GateError):
            rejected.append(name)
    require(rejected == list(cases),
            "v1.5 device-session mutation survived: "
            + ", ".join(name for name in cases if name not in rejected))
    return rejected


def derive_preparation() -> dict[str, Any]:
    rows_value = load(ROWS)
    rows = rows_contract(rows_value)
    media = load(MEDIA)
    require(media.get("status") == "V150-LINK97-HOST-AND-MEDIA-GREEN; D1-D5-PENDING"
            and media["pair_identity"]["result"] == "same-world-pair",
            "v1.5 media authority is not green")
    source = RUNNER.read_text(encoding="utf-8")
    runner = runner_gate(source)
    rejected = rejected_mutations(rows_value, source)
    return {
        "format": FORMAT, "recorded_on": "2026-08-11", "status": STATUS,
        "authority": {"media": bind(MEDIA), "session": bind(CONFIG),
                      "rows": bind(ROWS), "release_contract": bind(CONTRACT),
                      "runner": bind(RUNNER), "checker": bind(Path(__file__))},
        "media": {"product_D81": media["shared_system"]["product_D81"],
                  "library_D81": media["library"]["D81"],
                  "same_world": media["pair_identity"]["product_build_id"]},
        "session": {"order": ["D1", "D2", "D3", "D4", "D5"],
                    "physical_rows": len(rows), **runner},
        "mutations_rejected": rejected,
        "execution_accounting": {"hardware_contacts": 0, "forms": 0,
                                 "media_builds": 0, "product_links": 0},
        "claim_limit": (
            "Host/media-green v1.5 D1-D5 physical-session preparation only; "
            "no hardware, Halt, release or publication claim."),
    }


def validate_preparation(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and value.get("session", {}).get("order") == ["D1", "D2", "D3", "D4", "D5"]
        and value.get("session", {}).get("physical_rows") == 19
        and value.get("session", {}).get("post_boot_ftp_invocations") == 0
        and value.get("session", {}).get("active_form_observations") == 0
        and len(value.get("mutations_rejected", [])) == 10
        and value.get("execution_accounting") == {
            "hardware_contacts": 0, "forms": 0,
            "media_builds": 0, "product_links": 0},
        "v1.5 session preparation claim drift")
    if verify:
        require(value == derive_preparation(), "v1.5 session preparation stale")


def latest_values(text: Path, form: str) -> list[str]:
    SCREEN.check_latest_result(text, form, None)
    return SCREEN._latest_visible_results(text, form)


def verify_row(row_id: str, text: Path, image: Path) -> dict[str, Any]:
    rows = {row["id"]: row for row in rows_contract()}
    require(row_id in rows, f"unknown row: {row_id}")
    row = rows[row_id]; oracle = row["oracle"]
    SCREEN.check_fail_closed_frame(image)
    values = latest_values(text, row["form"])
    kind = oracle["kind"]
    if kind == "exact":
        require(values == [oracle["value"]],
                f"{row_id}: expected {oracle['value']!r}, got {values!r}")
    elif kind == "ordered":
        require(values == oracle["values"],
                f"{row_id}: expected {oracle['values']!r}, got {values!r}")
    elif kind == "time":
        require(len(values) == 1, f"{row_id}: time result cardinality drift")
        tokens = values[0].split(maxsplit=1)
        require(len(tokens) == 2 and tokens[0].isdigit(),
                f"{row_id}: expected FRAME RESULT, got {values!r}")
        require(int(tokens[0]) <= oracle["max_frames"]
                and tokens[1] == oracle["value"],
                f"{row_id}: release-terminal performance red: {values[0]}")
    else:
        raise SessionError(f"unknown row oracle: {kind}")
    for forbidden in oracle.get("forbid", []):
        require(forbidden not in values,
                f"{row_id}: forbidden current-segment token: {forbidden}")
    return {"id": row_id, "values": values, "result": "passed"}


def verify_guard(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    require(len(raw) == 16 and raw[0] == 0,
            "terminal-return guard is armed or readback length drifted")
    records = []
    for index in range(4):
        tag, live, shadow = raw[4 + index * 3:7 + index * 3]
        require(tag in (0, 1, 2, 3), f"guard tag invalid: {tag:02x}")
        if tag == 0:
            require(live == shadow == 0, "untagged guard record carries values")
        else:
            require(live != shadow, "tagged guard mismatch lacks distinct values")
        records.append({"tag": tag, "live": live, "shadow": shadow})
    require(all(row["tag"] == 0 for row in records),
            "v1.5 clean-path guard recorded a mismatch/restoration")
    return {"raw_hex": raw.hex(), "records": records, "result": "clean"}


def derive_result() -> dict[str, Any]:
    prep = load(PREP); validate_preparation(prep, verify=True)
    require((OUT / "final-capture-complete").is_file(),
            "v1.5 final stopped-state capture absent")
    row_results = []
    for row in rows_contract():
        row_id = row["id"]
        row_results.append(verify_row(
            row_id, OUT / f"row-{row_id}.txt", OUT / f"row-{row_id}.png"))
    guard = verify_guard(OUT / "final-terminal-return-guard.bin")
    require((OUT / "boot-liveness-owner-confirmed").is_file(),
            "D1 physical boot-liveness confirmation absent")
    return {
        "format": "lisp65-c2.3-v150-link97-device-session-v1",
        "recorded_on": "2026-08-11",
        "status": "V150-LINK97-D1-D5-HARDWARE-GREEN; OWNER-HALT-1-PENDING",
        "authority": {"preparation": bind(PREP), "media": bind(MEDIA),
                      "session": bind(CONFIG), "rows": bind(ROWS)},
        "D1": {"boot_liveness_owner_confirmed": True,
               "terminal_screen": bind(OUT / "product-boot.png")},
        "rows": row_results,
        "D3_guard": guard,
        "execution_accounting": {"hardware_contacts": 1, "physical_forms": 19,
                                 "post_boot_ftp_invocations": 0,
                                 "observations_during_active_forms": 0,
                                 "final_stops": 1},
        "next": "owner-halt-1",
        "claim_limit": (
            "D1-D5 hardware acceptance only. Release publication remains "
            "behind owner Halt #1 and later Publish-Go."),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "check", "selftest",
                                           "verify-row", "verify-guard", "record"))
    parser.add_argument("--row")
    parser.add_argument("--text", type=Path)
    parser.add_argument("--image", type=Path)
    parser.add_argument("--path", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        require(not PREP.exists(), "v1.5 session preparation already exists")
        value = derive_preparation(); validate_preparation(value, verify=False)
        PREP.parent.mkdir(parents=True, exist_ok=True); PREP.write_bytes(canonical(value))
        print("v1.5 D1-D5 preparation: PASS rows=19 mutations=10")
    elif args.action == "check":
        value = load(PREP); validate_preparation(value, verify=True)
        print("v1.5 D1-D5 preparation check: PASS rows=19 mutations=10")
    elif args.action == "selftest":
        value = derive_preparation(); validate_preparation(value, verify=False)
        print("v1.5 D1-D5 selftest: PASS rows=19 mutations=10")
    elif args.action == "verify-row":
        require(args.row is not None and args.text is not None and args.image is not None,
                "verify-row requires --row/--text/--image")
        result = verify_row(args.row, args.text, args.image)
        print(f"v1.5 row {args.row}: PASS {result['values']}")
    elif args.action == "verify-guard":
        require(args.path is not None, "verify-guard requires --path")
        result = verify_guard(args.path)
        print(f"v1.5 guard: PASS {result['raw_hex']}")
    else:
        require(not RESULT.exists(), "v1.5 device result already exists")
        result = derive_result(); RESULT.write_bytes(canonical(result))
        print("v1.5 D1-D5 result: PASS owner-halt-1-pending")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SessionError, SCREEN.CheckError, CROSSING.GateError,
            OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        message = error.message if isinstance(error, SCREEN.CheckError) else str(error)
        print(f"v1.5 D1-D5: FIRST RED: {message}", file=sys.stderr)
        raise SystemExit(2)
