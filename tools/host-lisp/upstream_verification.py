#!/usr/bin/env python3
"""Reproduce the 2026-07-19 upstream source/toolchain verification round."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build/upstream-verification/receipt-20260719"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/post-release/"
    "upstream-verification-receipt-2026-07-19.json"
)
PINNED_CLANG = ROOT / "tools/llvm-mos/bin/mos-clang"
SIM = ROOT / "tools/llvm-mos/bin/mos-sim"
SIM_CFG = ROOT / "tools/llvm-mos/bin/mos-sim.cfg"
MEGA65_CFG = ROOT / "tools/llvm-mos/bin/mos-mega65.cfg"
SHIFT = ROOT / "tools/upstream-repros/variable_shift_mask.c"
SCROLL = ROOT / "tools/upstream-repros/mega65_kernal_scroll.c"
CLONES = {
    "llvm_mos": ROOT / "build/upstream-verification/llvm-mos-head",
    "llvm_mos_sdk": ROOT / "build/upstream-verification/llvm-mos-sdk",
    "mega65_core": ROOT / "build/upstream-verification/mega65-core",
    "mega65_user_guide": ROOT / "build/upstream-verification/mega65-user-guide",
    "xemu": ROOT / "build/upstream-verification/xemu",
}
EXPECTED_HEADS = {
    "llvm_mos": "8be0546128a55e78c63ca571d466aa72a782cd36",
    "llvm_mos_sdk": "d0b137e5fd443fda1f70bf98ecd739cc131e18f9",
    "mega65_core": "a9158930665763c592d004c895d52eff4a9eefc3",
    "mega65_user_guide": "2d0c444a7f086fcc6c4aed9bbaf5ccc17a19ef60",
    "xemu": "40dfef0d1d5f56be2469492715c12bdb32c75b67",
}


class VerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def run(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args, cwd=cwd, text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )


def checked(*args: str, cwd: Path = ROOT) -> str:
    result = run(*args, cwd=cwd)
    require(result.returncode == 0,
            f"command failed ({result.returncode}): {' '.join(args)}\n{result.stderr}")
    return result.stdout


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def binding(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"regular file required: {path}")
    data = path.read_bytes()
    return {"path": rel(path), "bytes": len(data), "sha256": sha(data)}


def git(clone: Path, *args: str) -> str:
    return checked("git", "-C", str(clone), *args).strip()


def require_needles(text: str, needles: list[str], label: str) -> None:
    missing = [needle for needle in needles if needle not in text]
    require(not missing, f"{label} source facts missing: {missing}")


def distrobox_clang(*args: str) -> subprocess.CompletedProcess[str]:
    return run(
        "distrobox", "enter", "arch", "--",
        "/opt/llvm-mos/bin/mos-clang", *args,
    )


def compile_current(config: Path, source: Path, output: Path) -> None:
    result = distrobox_clang(
        "--config", str(config), "-Os", str(source), "-o", str(output)
    )
    require(result.returncode == 0, f"current compiler failed: {result.stderr}")


def sim_result(image: Path) -> dict[str, Any]:
    result = run(str(SIM), "--cycles", str(image))
    combined = result.stdout + result.stderr
    match = re.search(r"(\d+) cycles", combined)
    require(match is not None, f"simulator cycle result missing: {combined!r}")
    return {"exit": result.returncode, "cycles": int(match.group(1))}


def collect() -> dict[str, Any]:
    BUILD.mkdir(parents=True, exist_ok=True)
    heads = {name: git(path, "rev-parse", "HEAD") for name, path in CLONES.items()}
    require(heads == EXPECTED_HEADS, f"upstream checkout drift: {heads}")

    current_version = distrobox_clang("--version")
    require(current_version.returncode == 0, current_version.stderr)
    require(EXPECTED_HEADS["llvm_mos"] in current_version.stdout,
            "current compiler does not match checked llvm-mos HEAD")
    pinned_version = checked(str(PINNED_CLANG), "--version")
    require("c798c31416f72b395c658b5502d281a162387ab1" in pinned_version,
            "pinned compiler identity drift")

    current_shift = BUILD / "variable-shift-current.bin"
    pinned_shift = BUILD / "variable-shift-pinned.bin"
    current_scroll = BUILD / "mega65-kernal-scroll-current.prg"
    compile_current(SIM_CFG, SHIFT, current_shift)
    pinned = run(
        str(PINNED_CLANG), "--config", str(SIM_CFG), "-Os", str(SHIFT),
        "-o", str(pinned_shift),
    )
    require(pinned.returncode == 0, f"pinned compiler failed: {pinned.stderr}")
    compile_current(MEGA65_CFG, SCROLL, current_scroll)
    shift_runs = {
        "pinned": sim_result(pinned_shift),
        "current": sim_result(current_shift),
    }
    require(all(row == {"exit": 0, "cycles": 3162} for row in shift_runs.values()),
            f"variable-shift result drift: {shift_runs}")
    scroll_binding = binding(current_scroll)
    require(scroll_binding["bytes"] == 294, "current scroll PRG size drift")

    core = CLONES["mega65_core"]
    freeze = (core / "src/hyppo/freeze.asm").read_text(encoding="utf-8")
    dos = (core / "src/hyppo/dos.asm").read_text(encoding="utf-8")
    sdcardio = (core / "src/vhdl/sdcardio.vhdl").read_text(encoding="utf-8")
    require_needles(
        freeze,
        ["Copy $D680 - $D70F", "lda $d680,x", "sta $d680,x"],
        "mega65-core Freezer",
    )
    require_needles(dos, ["tsb $d689"], "mega65-core HYPPO DOS")
    require_needles(
        sdcardio,
        ["$D689.7 - Memory mapped sector buffer select: 1=SD-Card, 0=F011/FDC"],
        "mega65-core BUFSEL",
    )

    xemu = CLONES["xemu"] / "targets/mega65"
    inputs = (xemu / "input_devices.c").read_text(encoding="utf-8")
    hypervisor = (xemu / "hypervisor.c").read_text(encoding="utf-8")
    configdb = (xemu / "configdb.c").read_text(encoding="utf-8")
    sdcard = (xemu / "sdcard.c").read_text(encoding="utf-8")
    require_needles(
        inputs,
        ["read $D619", "read $D60A", "hwa_kbd_move_next", "hwa_kbd_flush_queue"],
        "Xemu typed event queue",
    )
    require_needles(
        hypervisor, ["FREEZER is not enabled in Xemu currently."], "Xemu Freezer"
    )
    require_needles(configdb, ["Allow triggering freezer [NOT YET WORKING]"],
                    "Xemu Freezer configuration")
    require_needles(
        sdcard,
        [
            "F011 buffer should be (FIXME: that is not implemented yet right now!!)",
            'fixed "SD-only" solution for now',
        ],
        "Xemu buffer model",
    )

    return {
        "format": "lisp65-upstream-verification-receipt-v1",
        "version": 1,
        "recorded_on": "2026-07-19",
        "status": "passed-with-explicit-hardware-holds",
        "claim_limit": (
            "This receipt proves source/toolchain re-verification only. It does not "
            "claim a current-core hardware result, file an issue, or change product bytes."
        ),
        "bindings": {
            "verifier": binding(ROOT / "tools/host-lisp/upstream_verification.py"),
            "report": binding(ROOT / "docs/upstream-verification-2026-07-19.md"),
            "findings": binding(ROOT / "docs/upstream-findings.md"),
            "drafts": binding(ROOT / "docs/upstream-issue-drafts.md"),
            "shift_repro": binding(SHIFT),
            "scroll_repro": binding(SCROLL),
        },
        "upstream_heads": heads,
        "upstream_blobs": {
            "mega65_core_freeze": git(core, "rev-parse", "HEAD:src/hyppo/freeze.asm"),
            "mega65_core_dos": git(core, "rev-parse", "HEAD:src/hyppo/dos.asm"),
            "mega65_core_sdcardio": git(core, "rev-parse", "HEAD:src/vhdl/sdcardio.vhdl"),
            "xemu_input_devices": git(CLONES["xemu"], "rev-parse", "HEAD:targets/mega65/input_devices.c"),
            "xemu_hypervisor": git(CLONES["xemu"], "rev-parse", "HEAD:targets/mega65/hypervisor.c"),
            "xemu_sdcard": git(CLONES["xemu"], "rev-parse", "HEAD:targets/mega65/sdcard.c"),
            "xemu_configdb": git(CLONES["xemu"], "rev-parse", "HEAD:targets/mega65/configdb.c"),
        },
        "toolchains": {
            "pinned_compiler": "c798c31416f72b395c658b5502d281a162387ab1",
            "current_compiler": EXPECTED_HEADS["llvm_mos"],
            "current_compiler_link_closure": "repository-pinned-sdk",
        },
        "l1": {
            "result": "reduced-claim-not-reproduced-do-not-file",
            "runs": shift_runs,
        },
        "l3": {
            "result": "current-binary-built-hardware-not-run",
            "prg": scroll_binding,
        },
        "core": {
            "result": "current-source-consistent-current-core-hardware-not-run",
            "historical_hardware_core": "03b24c6b9d0e456f762fdca0d2dd66ec3c3e1fc6",
            "existing_issue_674": "open-checked-2026-07-19",
            "existing_issue_729": "open-checked-2026-07-19",
        },
        "xemu": {
            "typed_event_queue": "implemented",
            "freezer": "not-enabled",
            "f011_sd_buffer_model": "explicitly-incomplete-sd-only-workaround",
        },
        "hardware_holds": ["L3 current-toolchain scroll smoke", "C3 current-core flat-access smoke"],
        "issues_filed": 0,
    }


def selftest() -> None:
    rejected = 0
    for text, needles in (
        ("alpha beta", ["alpha", "missing"]),
        ("", ["required"]),
        ("FREEZER disabled", ["FREEZER enabled"]),
    ):
        try:
            require_needles(text, needles, "mutation")
        except VerificationError:
            rejected += 1
    require(rejected == 3, f"source-fact mutations accepted: {rejected}")


def write() -> dict[str, Any]:
    result = collect()
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def check() -> dict[str, Any]:
    result = collect()
    require(RECEIPT.is_file(), "upstream verification receipt missing")
    recorded = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(recorded == result, "upstream verification receipt drift; regenerate with --write")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
        print("upstream-verification: SELFTEST PASS mutations=3")
        return 0
    result = write() if args.write else check()
    print(
        "upstream-verification: PASS L1=not-reproduced L3=hardware-pending "
        f"Xemu-queue={result['xemu']['typed_event_queue']} issues-filed=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
