#!/usr/bin/env python3
"""Audit and close the physical control row of the v1.6 launch appointment."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "build/c2.3/v1.6-defstruct-phase-c/deployment.json"
STOPPED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-launch-boundary-stopped-state-receipt.json")
RUNNER = ROOT / "scripts/c2-v16-defstruct-launch-boundary-control.sh"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-launch-boundary-control-device-receipt.json")
OUT = ROOT / (
    "build/c2.3/v1.6-defstruct-closing-session/"
    "d2-launch-boundary-appointment/control")


class ControlError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ControlError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object expected: {path}")
    return value


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def inspect_screen(text: str) -> dict[str, Any]:
    folded = text.casefold()
    return {
        "visible_REPL": "lisp65>" in folded,
        "BASIC_seen": "basic 65" in folded or "ready." in folded,
        "terminal_markers": [name for name, pattern in (
            ("BREAK", r"(?m)^\s*break\s*$"),
            ("MONITOR", r"monitor commands"),
        ) if re.search(pattern, folded)],
    }


def audit_runner() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    require('run_m65 -H "$product"' in source
            and 'run_m65 -H -1 "$product"' not in source,
            "control PRG is not installed as a BASIC program")
    require(".control.preloads[]" in source,
            "runner does not stage the control preload set")
    require("type RUN and press RETURN" in source
            and "hw-jtag-repl" not in source,
            "control launch is not physical-only")
    stage = source.index('if [ "$ACTION" = stage ]')
    reset = source.index("run_m65 -F", stage)
    load = source.index('run_m65 -H "$product"', reset)
    ready = source.index("screen control-launch-ready", load)
    require(stage < reset < load < ready,
            "control stage ordering drift")


def check() -> dict[str, Any]:
    deployment = load(DEPLOY)
    stopped = load(STOPPED)
    audit_runner()
    require(stopped["summary"]["CPU_left_stopped"] is True
            and stopped["control_row"] is None,
            "stopped-state row is not open for control")
    control = deployment["control"]
    require(bind(ROOT / control["prg"]["path"]) == control["prg"],
            "control PRG binding drift")
    require(all(bind(ROOT / row["path"])["bytes"] == row["bytes"]
                and bind(ROOT / row["path"])["sha256"] == row["sha256"]
                for row in control["preloads"]),
            "control preload binding drift")
    return {
        "status": "PASS",
        "control_prg_sha256": control["prg"]["sha256"],
        "control_preloads": len(control["preloads"]),
        "stopped_PC": stopped["summary"]["PC"],
        "stopped_C2J_nonzero_bytes": stopped["summary"]["C2J_nonzero_bytes"],
    }


def classify(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            "control screen must be a regular file")
    view = inspect_screen(path.read_text(encoding="utf-8", errors="replace"))
    require(view["visible_REPL"], "control physical boot has no visible lisp65> prompt")
    require(not view["terminal_markers"],
            "control physical boot entered BREAK/monitor")
    return {**view, "status": "CONTROL-PHYSICAL-BOOT-PROMPT-PASS"}


def selftest() -> dict[str, Any]:
    require(classify_fixture("BASIC 65\nREADY.\nRUN\nlisp65>\n")["visible_REPL"],
            "healthy prompt fixture rejected")
    rejected: dict[str, str] = {}
    for name, text in {
        "BASIC-only": "BASIC 65\nREADY.\nRUN\n",
        "BREAK": "RUN\nBREAK\nBS MONITOR COMMANDS\nlisp65>\n",
        "empty-result": "",
    }.items():
        try:
            fixture_require(text)
        except ControlError as error:
            rejected[name] = str(error)
        else:
            raise ControlError(f"control classifier mutation survived: {name}")
    require(len(rejected) == 3, "control classifier mutation count drift")
    return {"status": "PASS", "mutations_rejected": rejected}


def classify_fixture(text: str) -> dict[str, Any]:
    view = inspect_screen(text)
    require(view["visible_REPL"] and not view["terminal_markers"],
            "fixture is not healthy control prompt")
    return view


def fixture_require(text: str) -> None:
    view = inspect_screen(text)
    require(view["visible_REPL"], "control physical boot has no visible lisp65> prompt")
    require(not view["terminal_markers"],
            "control physical boot entered BREAK/monitor")


def finish(screen: Path) -> dict[str, Any]:
    check_row = check()
    tests = selftest()
    stopped = load(STOPPED)
    screen_binding = bind(screen)
    try:
        view = classify(screen)
        status = "CONTROL-PHYSICAL-BOOT-PASS"
        exit_green = True
    except ControlError as error:
        view = {**inspect_screen(screen.read_text(
            encoding="utf-8", errors="replace")), "error": str(error)}
        status = "FIRST RED: control physical boot did not reach visible REPL"
        exit_green = False
    decision = (
        "diagnostic-identity/delta boundary"
        if exit_green else
        "environment/staging class; diagnostic and control identities entangled"
    )
    receipt = {
        "format": "lisp65-c2.3-v1.6-D2-launch-boundary-control-v1",
        "recorded_on": date.today().isoformat(),
        "status": status,
        "authorities": {
            "deployment": bind(DEPLOY),
            "stopped_state": bind(STOPPED),
            "runner": bind(RUNNER),
            "driver": bind(Path(__file__).resolve()),
        },
        "control_identity": {
            "prg_sha256": check_row["control_prg_sha256"],
            "preloads": check_row["control_preloads"],
            "physical_RUN": True,
            "screen": screen_binding,
            "screen_result": view,
        },
        "stopped_diagnostic_row": stopped["summary"],
        "decision": decision,
        "mutations_rejected": tests["mutations_rejected"],
        "measured_forms_run": 0,
        "R_A_I_G_claimed": False,
        "claim_limit": (
            "Two-row physical-launch boundary only. The hook-free diagnostic "
            "record is not a boot witness; no require, defstruct, product fix "
            "or R/A/I/G result is claimed."),
    }
    write(RECEIPT, receipt)
    if not exit_green:
        raise ControlError(view["error"])
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("selftest", "check", "classify", "finish"))
    parser.add_argument("--screen", type=Path)
    args = parser.parse_args()
    if args.action == "selftest":
        value = selftest()
    elif args.action == "check":
        value = check()
    else:
        require(args.screen is not None, f"{args.action} requires --screen")
        path = args.screen if args.screen.is_absolute() else ROOT / args.screen
        value = classify(path) if args.action == "classify" else finish(path)
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ControlError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-v1.6-launch-boundary-control: FIRST RED: " + str(error),
              file=sys.stderr)
        raise SystemExit(2)
