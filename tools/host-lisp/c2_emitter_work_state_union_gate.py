#!/usr/bin/env python3
"""Prove the C2 emitter's 10-byte scratch union and phase handoffs."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/c2_session_emitter.c"
HARNESS = ROOT / "scripts/c2-emitter-work-state-union-main.c"
OUT = ROOT / "build/c2.2/emitter-work-state-union"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-emitter-work-state-lifetime-union-receipt.json"
)


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def bind(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def run() -> dict[str, object]:
    source = SOURCE.read_text(encoding="utf-8")
    require(
        "static c2e_state C2_SESSION_WINDOW_STATE c2e;" not in source
        and "#define c2e (c2ew.session)" in source,
        "emitter state did not move wholly into phase scratch")
    require(
        re.search(
            r"union\s*\{\s*uint16_t function_count;\s*"
            r"uint16_t final_length;\s*\};",
            source)
        and re.search(
            r"union\s*\{\s*uint16_t literal_index;\s*"
            r"uint16_t code_start;\s*\};",
            source),
        "phase-disjoint u16 pairs are not represented as unions")
    require(
        "sizeof(c2e_work_state) == LISP65_C2_INSTALL_TRACE_OFFSET" in source
        and "sizeof(c2e_state) == 10u" in source,
        "scratch/trace geometry is not compile-time pinned")

    # Exclude the explanatory comment and macro definition themselves.
    accesses = [
        line for line in source.splitlines()
        if "c2e." in line
        and "every c2e.* access" not in line
        and not line.startswith("#define c2e ")
    ]
    require(len(accesses) == 52, f"c2e source-access inventory drift: {len(accesses)}")

    OUT.mkdir(parents=True, exist_ok=True)
    binary = OUT / "c2-emitter-work-state-union-host"
    cc = os.environ.get("CC", "cc")
    subprocess.run([
        cc, "-std=c11", "-O1", "-g",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
        str(HARNESS), "-o", str(binary),
    ], check=True, cwd=ROOT)
    env = {
        **os.environ,
        "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1",
        "UBSAN_OPTIONS": "halt_on_error=1",
    }
    positive = subprocess.run(
        [str(binary)], check=True, cwd=ROOT, env=env,
        text=True, capture_output=True)
    require("PASS" in positive.stdout, "sanitized positive handoff did not pass")

    mutations: dict[str, str] = {}
    for mutation in (
        "final-before-add-end",
        "code-before-literal-end",
        "function-after-final",
        "literal-after-code",
    ):
        result = subprocess.run(
            [str(binary), mutation], cwd=ROOT, env=env,
            text=True, capture_output=True)
        require(
            result.returncode != 0 and "rejected:" in result.stderr,
            f"lifetime mutation accepted: {mutation}")
        mutations[mutation] = "rejected"

    return {
        "format": "lisp65-c2-emitter-work-state-lifetime-union-receipt-v1",
        "recorded_on": "2026-07-24",
        "status": "passed-sanitized-lifetime-union-and-mutations",
        "geometry": {
            "phase_scratch_bytes": 304,
            "installer_trace_offset": 302,
            "work_state_bytes": 302,
            "session_state_bytes": 10,
            "removed_E000_bytes": 10,
            "new_gc_roots": 0,
        },
        "handoffs": {
            "function_count_to_final_length": "disjoint",
            "literal_index_to_code_start": "disjoint",
            "session_state_preserved_across_both": True,
            "installer_trace_tail_preserved": True,
        },
        "source_access_inventory": {
            "c2e_dot_lines": len(accesses),
            "access_spelling": "unchanged-via-c2ew.session-macro",
        },
        "sanitizers": {"ASAN": "passed", "UBSAN": "passed"},
        "mutations": mutations,
        "authority": {
            "product_source": bind(SOURCE),
            "host_harness": bind(HARNESS),
            "gate": bind(Path(__file__)),
        },
    }


def main() -> int:
    value = run()
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(
        "c2-emitter-work-state-union-gate: PASS "
        f"mutations={len(value['mutations'])} "
        f"bytes={value['geometry']['work_state_bytes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
