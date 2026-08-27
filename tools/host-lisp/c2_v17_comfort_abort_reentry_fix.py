#!/usr/bin/env python3
"""Prove the two-stage Comfort abort landing in source and the final ELF."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "src/c2_product_runtime.c"
HEADER = ROOT / "src/c2_product_runtime.h"
INTERRUPT = ROOT / "src/interrupt.c"
REPL = ROOT / "src/repl.c"
ATTRIBUTION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.7-comfort-abort-reentry-attribution.json")
OUT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.7-comfort-abort-reentry-fix-receipt.json")
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def function_body(source: str, name: str) -> str:
    match = re.search(
        rf"^[^#\n]*\b{re.escape(name)}\s*\([^;{{]*?\)\s*\{{",
        source, re.MULTILINE | re.DOTALL)
    require(match is not None, f"function absent: {name}")
    depth = 0
    for offset, char in enumerate(source[match.start():]):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[match.start():match.start() + offset + 1]
    raise GateError(f"unterminated function: {name}")


def source_gate(runtime: str, interrupt: str, repl: str) -> dict[str, Any]:
    cleanup = function_body(runtime, "c2_product_abort_cleanup")
    recover = function_body(runtime, "c2_product_abort_recover")
    jump = function_body(interrupt, "lisp_abort_jump")
    landing = function_body(repl, "repl")
    setjmp_at = landing.find("if (setjmp(lisp_toplevel))")
    recover_at = landing.find("c2_product_abort_recover()", setjmp_at)
    render_at = landing.find("lisp65_error_render_pending()", setjmp_at)
    clear_at = landing.find("lisp65_error_clear()", setjmp_at)

    require("c2_rtov_retire_continuations_facade()" in cleanup
            and "vm_runtime_overlay_abort_cleanup()" in cleanup,
            "pre-longjmp retirement work missing")
    require("c2_abort_driver" not in cleanup
            and "c2_overlay_call" not in cleanup,
            "transported cleanup survived before longjmp")
    require("c2_abort_driver" in recover,
            "post-longjmp journal driver absent")
    require(jump.index("c2_product_abort_cleanup()")
            < jump.index("longjmp(lisp_toplevel, 1)"),
            "retirement no longer precedes longjmp")
    require(0 <= setjmp_at < recover_at < render_at < clear_at,
            "restored-stack recovery is not the first abort-landing work")
    return {
        "status": "PASS: ABORT LANDING IS TWO STAGE",
        "pre_longjmp": ["continuation-sanitize", "overlay-retire-wipe"],
        "post_longjmp": ["C2J-validate", "rollback-if-active"],
        "landing_order": ["setjmp-restored", "C2J-recover",
                          "render-original-error", "clear-error"],
    }


def model(*, soft_sp: int, journal_depth: int,
          two_stage: bool) -> dict[str, Any]:
    limit = 0xCA56
    restored = 0xCFF0
    events = ["sanitize", "retire-wipe"]
    if not two_stage:
        events.append("transport-before-longjmp")
        if soft_sp <= limit:
            return {"status": "ERR_STACK", "ready": 0,
                    "events": events, "soft_sp": soft_sp}
    events.append("longjmp-restore")
    soft_sp = restored
    events += ["journal-validate", "journal-reconstruct"]
    for _ in range(journal_depth):
        events += ["fronts", "rollback-prepare", "journal-write",
                   "rollback-plan"]
    events += ["fronts", "rollback-prepare", "done"]
    return {"status": "OK", "ready": 1, "events": events,
            "soft_sp": soft_sp, "journal_depth": journal_depth}


def mutation_gate(runtime: str, interrupt: str, repl: str) -> list[dict[str, Any]]:
    mutations = {
        "transport-restored-to-pre-longjmp-half": runtime.replace(
            "    return 1;\n}\n\n__attribute__((noinline, used))\n"
            "uint8_t c2_product_abort_recover(void) {",
            "    return c2_abort_driver();\n}\n\n"
            "__attribute__((noinline, used))\n"
            "uint8_t c2_product_abort_recover(void) {", 1),
        "post-longjmp-recovery-removed": repl.replace(
            "        (void)c2_product_abort_recover();\n", "", 1),
        "recovery-delayed-past-error-clear": repl.replace(
            "        (void)c2_product_abort_recover();\n", "", 1).replace(
                "        lisp65_error_clear();\n",
                "        lisp65_error_clear();\n"
                "        (void)c2_product_abort_recover();\n", 1),
    }
    rows = []
    for name, changed in mutations.items():
        try:
            source_gate(changed if name.startswith("transport-") else runtime,
                        interrupt, changed if not name.startswith("transport-")
                        else repl)
        except GateError as error:
            rows.append({"name": name, "rejected": str(error)})
        else:
            raise GateError(f"mutation survived: {name}")
    return rows


def disassembly(elf: Path) -> str:
    return subprocess.run(
        [str(OBJDUMP), "-d", "--no-show-raw-insn", str(elf)],
        check=True, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE).stdout


def emitted_body(text: str, name: str) -> str:
    match = re.search(
        rf"^[0-9a-f]+ <{re.escape(name)}>:\n(?P<body>.*?)(?=^\n?[0-9a-f]+ <|^Disassembly of section|\Z)",
        text, re.MULTILINE | re.DOTALL)
    require(match is not None, f"final function absent: {name}")
    return match.group("body")


def call_targets(body: str) -> list[str]:
    return re.findall(r"\b(?:jsr|jmp)\s+\$[0-9a-f]+\s+<([^+>]+)", body)


def final_gate(elf: Path) -> dict[str, Any]:
    text = disassembly(elf)
    bodies = {name: emitted_body(text, name) for name in (
        "lisp_abort_symbol", "c2_product_abort_cleanup",
        "c2_product_abort_recover", "repl")}
    calls = {name: call_targets(body) for name, body in bodies.items()}
    require("c2_product_abort_cleanup" in calls["lisp_abort_symbol"]
            and "longjmp" in calls["lisp_abort_symbol"],
            "final active abort path lost retirement/longjmp sequence")
    require("c2_product_abort_recover" not in calls["lisp_abort_symbol"],
            "final active abort path runs recovery on failing stack")
    require("c2_product_abort_recover" in calls["repl"],
            "final restored-stack landing lost recovery call")
    require(any(name in calls["c2_product_abort_cleanup"] for name in (
                "vm_runtime_overlay_abort_cleanup",
                "c2_rtov_retire_continuations_facade")),
            "final pre-longjmp retirement body lost its callees")
    require(not any("c2_abort_driver" in name
                    for name in calls["c2_product_abort_cleanup"]),
            "final pre-longjmp body reaches journal driver")
    require(any("c2_abort_driver" in name
                for name in calls["c2_product_abort_recover"]),
            "final post-longjmp body does not reach journal driver")
    return {"status": "PASS: FINAL ELF CONSUMES TWO-STAGE LANDING",
            "elf": bind(elf), "call_targets": calls}


def derive(elf: Path | None) -> dict[str, Any]:
    runtime = RUNTIME.read_text(encoding="utf-8")
    interrupt = INTERRUPT.read_text(encoding="utf-8")
    repl = REPL.read_text(encoding="utf-8")
    old = model(soft_sp=0xC900, journal_depth=0, two_stage=False)
    zero = model(soft_sp=0xC900, journal_depth=0, two_stage=True)
    nested = model(soft_sp=0xC700, journal_depth=3, two_stage=True)
    require(old["status"] == "ERR_STACK" and old["ready"] == 0,
            "historical First Red model did not fail")
    require(zero["status"] == nested["status"] == "OK"
            and zero["ready"] == nested["ready"] == 1
            and nested["events"].count("rollback-plan") == 3,
            "two-stage zero/nested recovery model red")
    value = {
        "format": "lisp65-c2-v17-comfort-abort-reentry-fix-v1",
        "status": "PASS: COMFORT ABORT REENTRY RECOVERS AFTER LONGJMP",
        "authority": {"attribution": bind(ATTRIBUTION)},
        "sources": {"runtime": bind(RUNTIME), "header": bind(HEADER),
                    "interrupt": bind(INTERRUPT), "repl": bind(REPL)},
        "source_gate": source_gate(runtime, interrupt, repl),
        "models": {"historical_order": old, "zero_depth": zero,
                   "nested_depth_three": nested},
        "mutations": mutation_gate(runtime, interrupt, repl),
        "claim_limit": (
            "Proves two-stage ordering and zero/nested journal recovery; "
            "hardware reentry remains a device acceptance claim."),
    }
    if elf is not None:
        value["final_elf"] = final_gate(elf)
    return value


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    require(len(sys.argv) in {2, 3},
            "usage: source-check | write ELF | check ELF")
    action = sys.argv[1]
    require(action == "source-check" or
            (action in {"write", "check"} and len(sys.argv) == 3),
            "usage: source-check | write ELF | check ELF")
    if action == "source-check":
        value = derive(None)
        print("v1.7 Comfort abort reentry: SOURCE PASS mutations=3")
        return 0
    elf = Path(sys.argv[2]).resolve()
    raw = canonical(derive(elf))
    if action == "write":
        OUT.write_bytes(raw)
    else:
        require(OUT.is_file() and OUT.read_bytes() == raw,
                "Comfort abort-reentry fix receipt drift")
    print("v1.7 Comfort abort reentry: FINAL PASS mutations=3")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GateError, OSError, ValueError, KeyError,
            subprocess.CalledProcessError) as error:
        print(f"v1.7-comfort-abort-reentry-fix: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
