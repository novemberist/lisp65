#!/usr/bin/env python3
"""Classify the v1.6 D2 BASIC launch screen without case assumptions.

Letter case is presentation state on BASIC 65, not launch semantics.  BREAK or
monitor output, however, is a terminal setup state and must never be accepted
merely because a RUN: line is also visible in the scrollback.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re


class LaunchScreenError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise LaunchScreenError(message)


def inspect(text: str) -> dict[str, object]:
    lines = [line.strip().casefold() for line in text.splitlines()]
    terminal = []
    if "break" in lines:
        terminal.append("BREAK")
    if any("monitor commands" in line for line in lines):
        terminal.append("MONITOR-COMMANDS")
    if any(re.search(r"\bpc\s+sr\s+ac\s+xr\s+yr\s+zr\s+bp\s+sp\b", line)
           for line in lines):
        terminal.append("MONITOR-REGISTER-HEADER")
    return {
        "run_seen_casefolded": "run:" in lines,
        "workbench_prompt_seen_casefolded": any("lisp65>" in line for line in lines),
        "terminal_markers": terminal,
    }


def classify(text: str) -> dict[str, object]:
    result = inspect(text)
    require(bool(result["run_seen_casefolded"]),
            "BASIC RUN intermediate absent (case-insensitive)")
    require(not bool(result["workbench_prompt_seen_casefolded"]),
            "Workbench already running at BASIC launch assertion")
    require(not result["terminal_markers"],
            "unhealthy BREAK/monitor state at BASIC launch: "
            + ",".join(result["terminal_markers"]))
    return {**result, "status": "healthy-BASIC-RUN-intermediate"}


def old_case_sensitive_accepts(text: str) -> bool:
    return re.search(r"(?m)^\s*run:\s*$", text) is not None


def selftest() -> dict[str, object]:
    upper_healthy = "READY.\nRUN:\n"
    lower_healthy = "ready.\nrun:\n"
    observed = (
        "READY.\nRUN:\n\nBREAK\n"
        "BS MONITOR COMMANDS:ABCDEFGHJMRTUX@.>;?$+&%'LSV\n"
        "    PC   SR AC XR YR ZR BP  SP  NVEBDIZC\n"
        "; 00C802 34 00 00 00 00 00 01ED --11-1--\n"
    )
    require(classify(upper_healthy)["status"] ==
            "healthy-BASIC-RUN-intermediate", "upper-case RUN was not accepted")
    require(classify(lower_healthy)["status"] ==
            "healthy-BASIC-RUN-intermediate", "lower-case run was not accepted")
    require(not old_case_sensitive_accepts(observed),
            "old case-sensitive classifier unexpectedly accepted observed RUN:")
    observed_view = inspect(observed)
    require(observed_view["run_seen_casefolded"]
            and observed_view["terminal_markers"] == [
                "BREAK", "MONITOR-COMMANDS", "MONITOR-REGISTER-HEADER"],
            "observed RUN:+BREAK fixture classification drift")
    rejected: dict[str, str] = {}
    for name, fixture in {
        "observed-RUN-plus-BREAK": observed,
        "missing-RUN": "READY.\n",
        "already-Workbench": "RUN:\nlisp65>\n",
    }.items():
        try:
            classify(fixture)
        except LaunchScreenError as error:
            rejected[name] = str(error)
        else:
            raise LaunchScreenError(f"launch-screen mutation survived: {name}")
    require(len(rejected) == 3, "launch-screen mutation count drift")
    return {
        "healthy_case_forms": 2,
        "old_case_sensitive_observed_acceptance": False,
        "observed_casefolded_RUN_seen": True,
        "observed_terminal_markers": observed_view["terminal_markers"],
        "mutations_rejected": rejected,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("selftest", "classify"))
    parser.add_argument("--screen", type=Path)
    args = parser.parse_args()
    if args.action == "selftest":
        result = selftest()
        print("D2 LAUNCH SCREEN SELFTEST PASS case-forms=2 mutations=3 "
              "observed-RUN+BREAK=rejected")
        return 0
    require(args.screen is not None and args.screen.is_file()
            and not args.screen.is_symlink(), "classify requires a regular --screen")
    result = classify(args.screen.read_text(encoding="utf-8", errors="replace"))
    print("D2 LAUNCH SCREEN PASS state=" + str(result["status"]))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LaunchScreenError as error:
        print(f"D2 LAUNCH SCREEN FIRST RED: {error}", file=__import__("sys").stderr)
        raise SystemExit(1)
