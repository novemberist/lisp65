#!/usr/bin/env python3
"""Keep the C2-deferred color-scroll rider binding fail-closed."""

from __future__ import annotations

import copy
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]


class BindingError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BindingError(message)


def validate(values: dict[str, str]) -> None:
    screen = values["screen"]
    overlay = values["overlay"]
    linker = values["linker"]
    profile = values["profile"]
    require("defined(LISP65_SCREEN_EDMA_SCROLL_REQUIRED)" in screen
            and "!defined(LISP65_SCREEN_EDMA_SCROLL)" in screen
            and "#error \"Workbench color-safe scroll is required" in screen,
            "mandatory rider-define guard missing")
    require("section(\".lisp65_rt_screen_scroll\")" in overlay
            and "section(\".lisp65_rt_screen_scroll_data\")" in overlay,
            "rider code/data sections missing")
    require("__lisp65_screen_scroll_required_param" in linker
            and "SIZEOF(.lisp65_rt_screen_scroll) > 0" in linker
            and "required runtime overlay color-safe screen scroll section is empty or unsafe"
                in linker,
            "empty/unsafe rider-section linker gate missing")
    require("-DLISP65_SCREEN_EDMA_SCROLL" not in profile,
            "C2-deferred canonical profile unexpectedly activates the rider")


def inputs() -> dict[str, str]:
    return {
        "screen": (ROOT / "src/screen.c").read_text(encoding="utf-8"),
        "overlay": (ROOT / "src/screen_scroll_overlay.c").read_text(encoding="utf-8"),
        "linker": (ROOT / "scripts/lisp65-screen-scroll-rider-gate.ld").read_text(
            encoding="utf-8"),
        "profile": (ROOT / "config/workbench.mk").read_text(encoding="utf-8"),
    }


def check() -> None:
    validate(inputs())
    print("v11-color-scroll-binding: PASS product=deferred required-define=fail-closed "
          "empty-section=fail-closed")


def selftest() -> None:
    base = inputs()
    validate(base)
    for key, needle in (
        ("screen", "!defined(LISP65_SCREEN_EDMA_SCROLL)"),
        ("linker", "SIZEOF(.lisp65_rt_screen_scroll) > 0"),
    ):
        mutated = copy.deepcopy(base)
        mutated[key] = mutated[key].replace(needle, "MUTATED", 1)
        try:
            validate(mutated)
        except BindingError:
            pass
        else:
            raise BindingError(f"binding mutation was accepted: {key}")
    print("v11-color-scroll-binding: SELFTEST PASS mutations=2")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else "check"
    try:
        if action == "check":
            check()
        elif action == "selftest":
            selftest()
        else:
            raise BindingError(f"unknown action: {action}")
    except (BindingError, OSError, UnicodeError) as exc:
        print(f"v11-color-scroll-binding: FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
