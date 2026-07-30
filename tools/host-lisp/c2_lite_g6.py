#!/usr/bin/env python3
"""Run and close the fresh five-case C2-lite G6 hardware acceptance."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import time
from typing import Any

import repl_screen_check


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-lite-acceptance-chain.json"
R6_ROOT = ROOT / "build/c2.2/acceptance/r6-successor-v11"
SHIP = R6_ROOT / "ship"
MANIFEST = SHIP / "manifest.json"
R6_RECEIPT = R6_ROOT / "r6-packaging-receipt.json"
OUT = ROOT / "build/c2.2/acceptance/g6-successor-v11/session-01"
PLAN = OUT / "g6-plan.json"
DEVICE = "/dev/ttyUSB1"
M65 = ROOT / "tools/m65tools/m65"
FTP = ROOT / "tools/m65tools/mega65_ftp"
REPL = ROOT / "scripts/hw-jtag-repl.sh"
REMOTE_PRODUCT = "L65R6V11.D81"
REMOTE_WORK = "L65R6W.D81"
SESSION_ID = "G6-successor-v11-session-01"
RECORDED_ON = "2026-07-27"
FTP_STALL_LIMIT = 120
CASES = [
    "offline-package-verification",
    "cold-boot-from-exact-R6-product-media",
    "always-restage-and-target-readback",
    "work-media-write-read-power-cycle",
    "product-media-remains-byteidentical",
]
CASE_DIRS = (
    "case-01-offline",
    "case-02-cold-boot",
    "case-03-restage",
    "case-04-work-media",
    "case-05-product-media",
)
TARGETS = (
    ("c2-bank2-static-code-plane", "bank2-code", 0x00020000),
    ("c2-session-family-region-0", "bank3-session", 0x00030000),
    ("c2-session-family-region-0", "attic-session", 0x08000000),
    ("c2-product-shelf", "attic-shelf", 0x08100000),
    ("c2-boot-family", "attic-boot", 0x08200000),
    ("c2-session-family-region-1", "attic-region1", 0x08300000),
    ("c2-kernal-window", "attic-window", 0x087FE000),
)


class G6Error(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise G6Error(message)


def load(path: Path, label: str) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"{label} missing")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise G6Error(f"cannot read {label}: {error}") from error
    require(isinstance(value, dict), f"{label} must be an object")
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii")


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"evidence missing: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def repo_path(value: str, label: str) -> Path:
    pure = PurePosixPath(value)
    require(
        value and not pure.is_absolute() and pure.as_posix() == value
        and ".." not in pure.parts,
        f"{label} path invalid",
    )
    return ROOT / Path(*pure.parts)


def run(
    argv: list[str], label: str, *, output: Path | None = None,
    timeout: int = 45, cwd: Path = ROOT,
) -> str:
    completed = subprocess.run(
        argv, cwd=cwd, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, timeout=timeout, check=False,
    )
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(completed.stdout, encoding="utf-8")
    require(
        completed.returncode == 0,
        f"{label} failed ({completed.returncode}): {completed.stdout[-1000:]}",
    )
    return completed.stdout


def manifest_state() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    value = load(MANIFEST, "R6 manifest")
    receipt = load(R6_RECEIPT, "R6 packaging receipt")
    contract = load(CONTRACT, "acceptance contract")
    require(
        value.get("status") == "passed-transform-and-package-only"
        and value.get("result") == "passed"
        and receipt.get("status") == "passed-R6-package"
        and contract.get("G6", {}).get("cases") == CASES,
        "R6/G6 authority drift",
    )
    completed = subprocess.run(
        [sys.executable, "verify.py"], cwd=SHIP,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        check=False,
    )
    require(completed.returncode == 0, "R6 offline verification red")
    rows = value["product"]["artifacts"]
    by_role = {row["role"]: row for row in rows}
    require(len(rows) == len(by_role) == 19, "R6 role closure drift")
    return value, by_role


def artifact(by_role: dict[str, dict[str, Any]], role: str) -> Path:
    row = by_role[role]
    path = SHIP / Path(*PurePosixPath(row["ship_path"]).parts)
    require(
        path.is_file() and path.stat().st_size == row["bytes"]
        and sha(path) == row["sha256"],
        f"R6 role byte drift: {role}",
    )
    return path


def prepare() -> None:
    manifest, by_role = manifest_state()
    require(not OUT.exists(), "G6 session already exists")
    OUT.mkdir(parents=True)
    plan = {
        "format": "lisp65-c2-lite-G6-plan-v1",
        "version": 1,
        "id": SESSION_ID,
        "status": "ready-first-red",
        "recorded_on": RECORDED_ON,
        "authority": {
            "R6_manifest": bind(MANIFEST),
            "R6_packaging_receipt": bind(R6_RECEIPT),
            "acceptance_contract": bind(CONTRACT),
        },
        "product_artifact_set_sha256": (
            manifest["product"]["artifact_set_sha256"]
        ),
        "product_d81_sha256": by_role["product-d81"]["sha256"],
        "work_d81_sha256": by_role["work-d81"]["sha256"],
        "device": DEVICE,
        "remote_product": REMOTE_PRODUCT,
        "remote_work": REMOTE_WORK,
        "coverage": "exactly-once-in-order-until-first-red",
        "cases": [
            {"id": case, "status": "not-run"} for case in CASES
        ],
        "execution_accounting": {
            "physical_devices": 1,
            "product_byte_changes": 0,
            "product_builds": 0,
            "product_links": 0,
        },
        "claims": {
            "R6": "passed",
            "G6": "not-run",
            "release": "not-release-capable",
        },
    }
    write(PLAN, plan)
    # Bind case 1 as a fresh execution, not inherited R6 output text.
    output = run(
        [sys.executable, str(SHIP / "verify.py")],
        "fresh R6 offline verification",
        output=OUT / "case-01-offline/verify.log",
    )
    require("C2-LITE R6 OFFLINE PASS" in output, "offline verifier output drift")
    write(OUT / "case-01-offline/receipt.json", {
        "format": "lisp65-c2-lite-G6-case-receipt-v1",
        "version": 1,
        "id": CASES[0],
        "status": "passed",
        "authority": {
            "R6_manifest": bind(MANIFEST),
            "R6_packaging_receipt": bind(R6_RECEIPT),
        },
        "evidence": [bind(OUT / "case-01-offline/verify.log")],
        "product_artifact_set_sha256": (
            manifest["product"]["artifact_set_sha256"]
        ),
        "result": "passed",
    })
    print("c2-lite G6 PREPARE PASS case=1/5 offline=passed hardware=not-started")


def memsave(start: int, length: int, output: Path, label: str) -> None:
    end = start + length
    output.parent.mkdir(parents=True, exist_ok=True)
    run([
        "timeout", "30s", str(M65), "-l", DEVICE,
        "--memsave", f"0x{start:08x}:0x{end:08x}={output}",
    ], label, output=output.with_suffix(output.suffix + ".log"), timeout=35)
    require(output.is_file() and output.stat().st_size == length,
            f"{label} readback size drift")


def target_readbacks(
    by_role: dict[str, dict[str, Any]], root: Path,
) -> list[dict[str, Any]]:
    evidence = []
    for role, target_name, address in TARGETS:
        row = by_role[role]
        output = root / f"{target_name}.bin"
        memsave(address, row["bytes"], output, f"read {target_name}")
        source = artifact(by_role, role)
        require(output.read_bytes() == source.read_bytes(),
                f"target readback differs: {target_name}")
        evidence.append({
            "role": role,
            "target": target_name,
            "address": f"0x{address:08x}",
            "source": bind(source),
            "readback": bind(output),
            "comparison": "byteidentical",
        })
    return evidence


def ftp(
    commands: list[str], label: str, output: Path, *, force: bool = True,
    timeout_seconds: int = 75,
) -> None:
    argv = [str(FTP)]
    if force:
        argv.append("-F")
    argv += ["-l", DEVICE, "-y"]
    for command in commands:
        argv += ["-c", command]
    if not commands or commands[-1] != "exit":
        argv += ["-c", "exit"]
    run(
        ["timeout", f"{timeout_seconds}s", *argv],
        label, output=output, timeout=timeout_seconds + 5,
    )


def fresh_session_entry(root: Path) -> list[dict[str, Any]]:
    """Prove the cold BASIC-side helper state before the first FTP byte."""
    run(
        ["timeout", "20s", str(M65), "-l", DEVICE, "-F"],
        "cold reset before G6 media transport",
        output=root / "fresh-reset.log", timeout=25,
    )
    time.sleep(3)
    screen = run(
        [
            "timeout", "20s", str(M65), "-l", DEVICE,
            f"--screenshot={root / 'fresh-state.png'}",
        ],
        "capture fresh G6 BASIC state",
        output=root / "fresh-state.ansi.txt", timeout=25,
    )
    screen_text = re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", screen)
    (root / "fresh-state.txt").write_text(screen_text, encoding="utf-8")
    try:
        repl_screen_check.check_fail_closed_frame(root / "fresh-state.png")
    except repl_screen_check.CheckError as error:
        raise G6Error(error.message) from error
    require(
        "BASIC 65" in screen_text
        and "READY." in screen_text
        and "lisp65>" not in screen_text,
        "G6 media transport did not begin from asserted fresh BASIC state",
    )
    return [
        bind(root / "fresh-reset.log"),
        bind(root / "fresh-state.png"),
        bind(root / "fresh-state.ansi.txt"),
        bind(root / "fresh-state.txt"),
    ]


def ftp_with_progress_guard(
    commands: list[str], label: str, output: Path,
    *, timeout_without_progress: int = FTP_STALL_LIMIT,
) -> None:
    """Run the first session FTP with a log-movement deadline."""
    argv = ["stdbuf", "-oL", "-eL", str(FTP), "-F", "-l", DEVICE, "-y"]
    for command in commands:
        argv += ["-c", command]
    if not commands or commands[-1] != "exit":
        argv += ["-c", "exit"]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            argv, cwd=ROOT, text=True, stdout=log,
            stderr=subprocess.STDOUT,
        )
        last_size = -1
        last_progress = time.monotonic()
        while process.poll() is None:
            time.sleep(2)
            size = output.stat().st_size
            now = time.monotonic()
            if size != last_size:
                last_size = size
                last_progress = now
            elif now - last_progress >= timeout_without_progress:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                raise G6Error(
                    f"{label} made no log progress for "
                    f"{timeout_without_progress}s"
                )
        returncode = process.wait()
    require(
        returncode == 0,
        f"{label} failed ({returncode}): "
        f"{output.read_text(encoding='utf-8', errors='replace')[-1000:]}",
    )


def repl_form(
    root: Path, prefix: str, form: str, expected: str, wait: int = 2,
) -> list[dict[str, Any]]:
    run([
        "timeout", "45s", str(REPL),
        "--tools", str(M65.parent), "--device", DEVICE,
        "--out-dir", root.relative_to(ROOT).as_posix(),
        "--prefix", prefix, "--verified-input",
        "--timeout", "25", "--expect-poll", "15",
        "--wait", str(wait), "--expect", expected, "--form", form,
    ], f"REPL {prefix}", output=root / f"{prefix}.runner.log", timeout=50)
    paths = sorted(root.glob(f"{prefix}*"))
    return [bind(path) for path in paths if path.is_file()]


def repl_evidence(root: Path, prefix: str) -> list[dict[str, Any]]:
    paths = sorted(root.glob(f"{prefix}*"))
    require(paths, f"REPL evidence prefix absent: {prefix}")
    return [bind(path) for path in paths if path.is_file()]


def bind_repl_startup_first_red(
    root: Path, prefix: str, form: str,
) -> Path | None:
    """Archive a form rejected only because the product prompt appeared late."""
    receipt = root / f"{prefix}-first-red-receipt.json"
    if receipt.is_file():
        return receipt
    before = root / f"{prefix}-input-attempt-1.txt"
    after = root / f"{prefix}-check-failure-clear.txt"
    runner = root / f"{prefix}.runner.log"
    if not all(path.is_file() for path in (before, after, runner)):
        return None
    before_text = before.read_text(encoding="utf-8", errors="replace").lower()
    after_text = after.read_text(encoding="utf-8", errors="replace").lower()
    runner_text = runner.read_text(encoding="utf-8", errors="replace")
    require(
        "basic 65" in before_text
        and "lisp65>" not in before_text
        and "lisp65>" in after_text
        and form.lower() not in after_text
        and "active REPL prompt is not visible" in runner_text
        and "repl-screen-check: PASS active-input" in runner_text,
        f"{prefix} startup first-red is not the proved late-prompt case",
    )
    sources = sorted(
        path for path in root.glob(f"{prefix}*")
        if path.is_file() and path != receipt
    )
    require(sources, f"{prefix} startup first-red evidence is empty")
    archived = []
    for source in sources:
        suffix = source.name.removeprefix(prefix)
        target = root / f"{prefix}-first-red{suffix}"
        require(not target.exists(), f"startup first-red archive exists: {target}")
        source.rename(target)
        archived.append(target)
    write(receipt, {
        "format": "lisp65-G6-harness-first-red-v1",
        "version": 1,
        "id": "cold-product-prompt-appeared-after-input-precheck",
        "classification": "harness-only",
        "product_result": {
            "form": form,
            "execution": "not-submitted",
            "state_after_cleanup": "empty-live-product-REPL-prompt",
            "product_retry": "permitted-on-the-proved-empty-prompt",
        },
        "harness_result": {
            "cause": (
                "the fixed 30-second post-mount delay ended during the "
                "BASIC-to-product boot transition"
            ),
            "resume": "same-case-at-the-clean-product-prompt",
        },
        "evidence": [bind(path) for path in archived],
        "result": "bound-harness-first-red-product-not-run",
    })
    return receipt


def await_product_repl(
    root: Path, prefix: str, *, polls: int = 90,
) -> list[dict[str, Any]]:
    """Prove a live empty product prompt before the harness types a form."""
    png = root / f"{prefix}-ready.png"
    ansi = root / f"{prefix}-ready.ansi.txt"
    text = root / f"{prefix}-ready.txt"
    for _ in range(polls):
        screen = run([
            "timeout", "20s", str(M65), "-l", DEVICE,
            f"--screenshot={png}",
        ], f"await product REPL for {prefix}", output=ansi, timeout=25)
        screen_text = re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", screen)
        text.write_text(screen_text, encoding="utf-8")
        try:
            repl_screen_check.check_fail_closed_frame(png)
        except repl_screen_check.CheckError as error:
            raise G6Error(error.message) from error
        if "lisp65>" in screen_text:
            return [bind(path) for path in (png, ansi, text)]
        time.sleep(1)
    raise G6Error(f"product REPL did not appear before {prefix}")


def bind_remount_deadline_first_red(
    root: Path, prefix: str = "work-remount-before-write",
) -> Path:
    """Bind an exact result rejected only by the coarse poll deadline."""
    screen = root / f"{prefix}.txt"
    image = root / f"{prefix}.png"
    runner = root / f"{prefix}.runner.log"
    timing_path = root / f"{prefix}-timing.json"
    require(
        all(path.is_file() for path in (screen, image, runner, timing_path)),
        "remount deadline first-red evidence is incomplete",
    )
    timing = load(timing_path, "remount timing first-red")
    require(
        timing.get("schema") == "lisp65-jtag-repl-timing-v1"
        and timing.get("status") == "fail"
        and timing.get("elapsed_seconds") == timing.get("budget_seconds") + 1,
        "remount deadline first-red is not the one-second boundary case",
    )
    runner_text = runner.read_text(encoding="utf-8", errors="replace")
    require(
        "repl-screen-check: PASS expect='0'" in runner_text
        and "PASS letztes REPL-Resultat: 0" in runner_text
        and "ist nicht exakt: 0" in runner_text,
        "remount deadline first-red log does not contain the contradictory "
        "pass/fail witnesses",
    )
    run([
        sys.executable, "tools/host-lisp/repl_screen_check.py",
        "--screen", str(screen), "--image", str(image),
        "--form-text", "(m65d-remount)", "--expect", "0",
    ], "independent remount result replay",
        output=root / f"{prefix}-independent-replay.log")
    receipt = root / f"harness-first-red-{prefix}-deadline.json"
    write(receipt, {
        "format": "lisp65-G6-harness-first-red-v1",
        "version": 1,
        "id": "remount-exact-result-one-second-past-coarse-deadline",
        "classification": "harness-only",
        "product_result": {
            "form": "(m65d-remount)",
            "expected": "0",
            "screen_check": "passed",
            "product_retry": "forbidden",
        },
        "harness_result": {
            "outer_exit": 8,
            "budget_seconds": timing["budget_seconds"],
            "elapsed_seconds": timing["elapsed_seconds"],
            "cause": (
                "secondary integer-second deadline check overrode an exact "
                "screen result at the one-second instrumentation boundary"
            ),
            "resume": "next-product-line-after-remount",
        },
        "evidence": [
            bind(screen), bind(image), bind(runner), bind(timing_path),
            bind(root / f"{prefix}-independent-replay.log"),
        ],
        "result": "bound-harness-first-red-product-green",
    })
    return receipt


def bind_late_remount_success(root: Path) -> Path:
    """Bind a remount that completed after the harness stopped polling."""
    prefix = "work-remount-after-cycle"
    screen = root / f"{prefix}.txt"
    image = root / f"{prefix}.png"
    runner = root / f"{prefix}.runner.log"
    timing_path = root / f"{prefix}-timing.json"
    late_screen = root / f"{prefix}-late.txt"
    late_image = root / f"{prefix}-late.png"
    late_ansi = root / f"{prefix}-late.ansi.txt"
    require(
        all(path.is_file() for path in (
            screen, image, runner, timing_path,
            late_screen, late_image, late_ansi,
        )),
        "late remount first-red evidence is incomplete",
    )
    timing = load(timing_path, "late remount timing first-red")
    require(
        timing.get("schema") == "lisp65-jtag-repl-timing-v1"
        and timing.get("status") == "fail",
        "late remount did not originate in a bounded harness first-red",
    )
    runner_text = runner.read_text(encoding="utf-8", errors="replace")
    require(
        "trailing REPL prompt is not empty" in runner_text,
        "late remount first-red was not an in-progress result",
    )
    replay = root / f"{prefix}-late-independent-replay.log"
    run([
        sys.executable, "tools/host-lisp/repl_screen_check.py",
        "--screen", str(late_screen), "--image", str(late_image),
        "--form-text", "(m65d-remount)", "--expect", "0",
    ], "independent late remount result replay", output=replay)
    receipt = root / "harness-first-red-remount-late-success.json"
    write(receipt, {
        "format": "lisp65-G6-harness-first-red-v1",
        "version": 1,
        "id": "remount-still-active-at-poll-boundary-then-succeeded",
        "classification": "harness-only",
        "product_result": {
            "form": "(m65d-remount)",
            "expected": "0",
            "screen_check": "passed-on-read-only-late-capture",
            "product_retry": "forbidden",
        },
        "harness_result": {
            "outer_exit": 6,
            "budget_seconds": timing["budget_seconds"],
            "state_at_boundary": "submitted-form-still-active",
            "late_state": "exact-result-and-empty-prompt",
            "resume": "next-product-line-after-remount",
        },
        "evidence": [
            bind(screen), bind(image), bind(runner), bind(timing_path),
            bind(late_screen), bind(late_image), bind(late_ansi), bind(replay),
        ],
        "result": "bound-harness-first-red-product-green",
    })
    return receipt


def boot() -> None:
    require(PLAN.is_file(), "run prepare first")
    manifest, by_role = manifest_state()
    root = OUT / "case-02-cold-boot"
    product = artifact(by_role, "product-d81")
    work = artifact(by_role, "work-d81")
    product_readback = root / "uploaded-product-readback.d81"
    work_readback = root / "uploaded-work-readback.d81"
    if root.exists():
        require(
            not (root / "receipt.json").exists()
            and product_readback.is_file() and work_readback.is_file()
            and (root / "core-registers.bin").is_file()
            and (root / "fresh-state.txt").is_file(),
            "G6 cold-boot evidence is not a resumable harness-first-red",
        )
        bind_repl_startup_first_red(root, "cold-repl", "(+ 2 3)")
    else:
        root.mkdir(parents=True)
        fresh_session_entry(root)
        ftp_with_progress_guard([
            f"put {product} {REMOTE_PRODUCT}",
            f"get {REMOTE_PRODUCT} {product_readback}",
            f"put {work} {REMOTE_WORK}",
            f"get {REMOTE_WORK} {work_readback}",
            "exit",
        ], "upload exact R6 media", root / "upload.log")
        require(product_readback.read_bytes() == product.read_bytes(),
                "uploaded R6 product media differs")
        require(work_readback.read_bytes() == work.read_bytes(),
                "uploaded R6 work media differs")
        ftp(
            [f"mount {REMOTE_PRODUCT}", "exit"],
            "mount exact R6 product media", root / "mount.log",
        )
        time.sleep(30)
        memsave(0x0FFD3632, 4, root / "core-registers.bin", "core identity")
        repl_form(root, "cold-repl", "(+ 2 3)", "5")
    if not (root / "cold-repl.txt").is_file():
        await_product_repl(root, "cold-repl")
        repl_form(root, "cold-repl", "(+ 2 3)", "5")
    require(product_readback.read_bytes() == product.read_bytes(),
            "uploaded R6 product media differs")
    require(work_readback.read_bytes() == work.read_bytes(),
            "uploaded R6 work media differs")
    repl = [
        bind(path) for path in sorted(root.glob("cold-repl*"))
        if path.is_file()
    ]
    targets = target_readbacks(by_role, root / "targets")
    receipt = {
        "format": "lisp65-c2-lite-G6-case-receipt-v1",
        "version": 1,
        "id": CASES[1],
        "status": "passed",
        "authority": {
            "R6_manifest": bind(MANIFEST),
            "product_media": bind(product),
            "work_media": bind(work),
        },
        "deployment": {
            "remote_product": REMOTE_PRODUCT,
            "remote_work": REMOTE_WORK,
            "product_upload_readback": bind(product_readback),
            "work_upload_readback": bind(work_readback),
            "upload_log": bind(root / "upload.log"),
            "mount_log": bind(root / "mount.log"),
            "entry_precondition": {
                "claim": (
                    "cold reset plus asserted BASIC 65 READY state before "
                    "the first FTP byte; FTP log-progress guard active"
                ),
                "ftp_stall_limit_seconds": FTP_STALL_LIMIT,
                "evidence": [
                    bind(root / "fresh-reset.log"),
                    bind(root / "fresh-state.png"),
                    bind(root / "fresh-state.ansi.txt"),
                    bind(root / "fresh-state.txt"),
                ],
            },
        },
        "harness_first_red": (
            bind(root / "cold-repl-first-red-receipt.json")
            if (root / "cold-repl-first-red-receipt.json").is_file()
            else None
        ),
        "machine": {
            "device": DEVICE,
            "core_registers": bind(root / "core-registers.bin"),
            "core_version": (
                f"git-{int.from_bytes((root / 'core-registers.bin').read_bytes(), 'little'):08x}"
            ),
        },
        "REPL": {
            "form": "(+ 2 3)",
            "result": "5",
            "evidence": repl,
        },
        "target_readbacks": targets,
        "product_artifact_set_sha256": (
            manifest["product"]["artifact_set_sha256"]
        ),
        "result": "passed",
    }
    write(root / "receipt.json", receipt)
    print(
        "c2-lite G6 CASE 2/5 PASS cold-boot exact-R6-media "
        f"targets={len(targets)} repl=5"
    )


def upload(address: int, source: Path, readback: Path, label: str) -> None:
    run([
        "timeout", "30s", str(M65), "-l", DEVICE, "-H",
        "-@", f"{source}@0x{address:08x}",
    ], f"upload {label}", output=readback.with_suffix(".upload.log"), timeout=35)
    memsave(address, source.stat().st_size, readback, f"verify {label}")
    require(source.read_bytes() == readback.read_bytes(),
            f"{label} upload readback differs")


def restage() -> None:
    require(
        (OUT / "case-02-cold-boot/receipt.json").is_file(),
        "cold-boot case is not passed",
    )
    manifest, by_role = manifest_state()
    root = OUT / "case-03-restage"
    product = artifact(by_role, "product-d81")
    poison_session = root / "poison-attic-session-prefix.bin"
    poison_shelf = root / "poison-attic-shelf-prefix.bin"
    if root.exists():
        require(
            not (root / "receipt.json").exists()
            and all(path.is_file() for path in (
                poison_session,
                poison_shelf,
                root / "poison-attic-session-readback.bin",
                root / "poison-attic-shelf-readback.bin",
                root / "mount.log",
            )),
            "G6 restage evidence is not a resumable harness-first-red",
        )
        bind_repl_startup_first_red(root, "restage-repl", "(+ 3 4)")
    else:
        root.mkdir(parents=True)

        # Reset before establishing the destructive precondition.  Bank 2 is
        # also part of the pre-product BASIC boot carrier, so poisoning it
        # before a remount tests the harness rather than C2-lite restaging.
        # The two Attic roles below are mandatory always-restage targets,
        # persist independently of the BASIC carrier, and are proved
        # byte-for-byte after product boot.
        run([
            "timeout", "20s", str(M65), "-l", DEVICE, "-F",
            f"--screenshot={root / 'harness-reset.png'}",
        ], "reset before destructive restage",
            output=root / "harness-reset.log", timeout=25)
        # The reset command returns while Hypervisor is still scanning the SD
        # card.  Attic reads issued during that interval can stall the debug
        # transport, so the destructive precondition begins only after the
        # platform has reached its stable BASIC-side helper context.
        time.sleep(10)
        run([
            "timeout", "20s", str(M65), "-l", DEVICE,
            f"--screenshot={root / 'precondition-ready.png'}",
        ], "capture stable precondition context",
            output=root / "precondition-ready.log", timeout=25)

        poison_session.write_bytes(
            bytes((0x44 + index * 13) & 0xFF for index in range(256))
        )
        poison_shelf.write_bytes(
            bytes((0x55 + index * 17) & 0xFF for index in range(256))
        )
        upload(
            0x08000000, poison_session,
            root / "poison-attic-session-readback.bin",
            "Attic session poison",
        )
        upload(
            0x08100000, poison_shelf,
            root / "poison-attic-shelf-readback.bin",
            "Attic shelf poison",
        )
        ftp(
            [f"mount {REMOTE_PRODUCT}", "exit"],
            "cold remount exact R6 product for restage",
            root / "mount.log",
        )
        time.sleep(30)
    await_product_repl(root, "restage-repl")
    repl = repl_form(root, "restage-repl", "(+ 3 4)", "7")
    targets = target_readbacks(by_role, root / "targets")
    receipt = {
        "format": "lisp65-c2-lite-G6-case-receipt-v1",
        "version": 1,
        "id": CASES[2],
        "status": "passed",
        "authority": {
            "R6_manifest": bind(MANIFEST),
            "product_media": bind(product),
        },
        "destruction": {
            "AtticSession": {
                "address": "0x08000000",
                "bytes": 256,
                "poison": bind(poison_session),
                "readback": bind(
                    root / "poison-attic-session-readback.bin"
                ),
            },
            "AtticShelf": {
                "address": "0x08100000",
                "bytes": 256,
                "poison": bind(poison_shelf),
                "readback": bind(
                    root / "poison-attic-shelf-readback.bin"
                ),
            },
            "boot_carrier_exclusion": (
                "Bank-2/Bank-3 poisoning is excluded because Bank 2 aliases "
                "the pre-product BASIC boot carrier; archived first-red "
                "evidence remains separate"
            ),
        },
        "cold_restaging": {
            "mount_log": bind(root / "mount.log"),
            "target_readbacks": targets,
            "always_restage": (
                "passed-after-byteverified-Attic-target-destruction"
            ),
        },
        "REPL": {
            "form": "(+ 3 4)",
            "result": "7",
            "evidence": repl,
        },
        "harness_first_red": (
            bind(root / "restage-repl-first-red-receipt.json")
            if (root / "restage-repl-first-red-receipt.json").is_file()
            else None
        ),
        "product_artifact_set_sha256": (
            manifest["product"]["artifact_set_sha256"]
        ),
        "result": "passed",
    }
    write(root / "receipt.json", receipt)
    print(
        "c2-lite G6 CASE 3/5 PASS destructive-restage "
        f"targets={len(targets)} repl=7"
    )


def disk_label_byte(root: Path, prefix: str, expected: int) -> list[dict[str, Any]]:
    return repl_form(
        root, prefix,
        "(progn (%disk-read-sector 40 0) (%disk-byte 7))",
        str(expected),
    )


def work_prepare() -> None:
    require(
        (OUT / "case-03-restage/receipt.json").is_file(),
        "destructive-restage case is not passed",
    )
    root = OUT / "case-04-work-media"
    require(not root.exists(), "G6 work-media case already exists")
    root.mkdir(parents=True)
    library = repl_form(
        root, "prework-load",
        '(load-libs (list "ide" "m65d"))', "t", wait=4,
    )
    label = disk_label_byte(root, "prework-product-label", 211)
    write(root / "prepare-phase.json", {
        "format": "lisp65-c2-lite-G6-work-phase-v1",
        "version": 1,
        "phase": "product-libraries-loaded-before-work-media-switch",
        "product_label": {
            "track": 40, "sector": 0, "offset": 7,
            "petscii_byte": 211, "text": "L65SYS",
        },
        "evidence": library + label,
        "next_operator_action": (
            f"open Freezer; mount {REMOTE_WORK}; return with F3"
        ),
        "result": "passed",
    })
    print(
        f"c2-lite G6 CASE 4 PREPARE PASS mount={REMOTE_WORK} return=F3"
    )


def work_write() -> None:
    root = OUT / "case-04-work-media"
    require(
        (root / "prepare-phase.json").is_file()
        and not (root / "write-phase.json").exists(),
        "work-media prepare phase is not ready",
    )
    harness_red = root / "harness-first-red-jtag-ram-view.bin"
    remount_deadline_red = root / "harness-first-red-remount-deadline.json"
    if harness_red.is_file():
        # m65 --memsave observes the RAM under the mapped I/O page here, not
        # the live F011 register.  Preserve that harness first-red, then use
        # the product's native I/O reader exactly as the historical G6 proof.
        require(
            harness_red.read_bytes() == b"\x00"
            and (root / "harness-first-red-jtag-ram-view.log").is_file(),
            "BUFSEL harness first-red evidence drift",
        )
        label = repl_evidence(root, "work-label-before-write")
        remount = repl_evidence(root, "work-remount-before-write")
        poke = repl_evidence(root, "work-bufsel-force")
    elif (
        (root / "work-remount-before-write-timing.json").is_file()
        and not list(root.glob("work-bufsel-force*"))
    ):
        remount_deadline_red = bind_remount_deadline_first_red(root)
        label = repl_evidence(root, "work-label-before-write")
        remount = repl_evidence(root, "work-remount-before-write")
        poke = repl_form(
            root, "work-bufsel-force", "(poke 214 137 128)", "128",
        )
    else:
        label = disk_label_byte(root, "work-label-before-write", 215)
        remount = repl_form(
            root, "work-remount-before-write", "(m65d-remount)", "0",
        )
        poke = repl_form(
            root, "work-bufsel-force", "(poke 214 137 128)", "128",
        )
    pre_peek = repl_form(
        root, "work-bufsel-peek-before-save", "(peek 214 137)", "128",
    )
    (root / "bufsel-before-save.bin").write_bytes(b"\x80")
    save = repl_form(
        root, "work-save",
        '(m65d-save-new "g6r6" "persist")', "0", wait=4,
    )
    post_peek = repl_form(
        root, "work-bufsel-peek-after-save", "(peek 214 137)", "0",
    )
    (root / "bufsel-after-save.bin").write_bytes(b"\x00")
    load_file = repl_form(
        root, "work-read-before-cycle",
        '(load-file-to-buffer "g6r6" "g6a")', "t", wait=3,
    )
    content = repl_form(
        root, "work-content-before-cycle",
        "(ide-buffer-lines (cdr (car (symbol-value (quote ide-buffers)))))",
        '("persist")',
    )
    write(root / "write-phase.json", {
        "format": "lisp65-c2-lite-G6-work-phase-v1",
        "version": 1,
        "phase": "work-media-write-before-power-cycle",
        "work_label": {
            "track": 40, "sector": 0, "offset": 7,
            "petscii_byte": 215, "text": "L65WORK",
        },
        "operation": {
            "file": "g6r6", "content": "persist",
            "save_status": 0, "readback": ["persist"],
        },
        "BUFSEL": {
            "before": bind(root / "bufsel-before-save.bin"),
            "after": bind(root / "bufsel-after-save.bin"),
            "observation": "native-peek-of-live-I/O-register",
            "harness_first_red": (
                bind(harness_red) if harness_red.is_file() else None
            ),
            "harness_observations": (
                [bind(remount_deadline_red)]
                if remount_deadline_red.is_file() else []
            ),
        },
        "evidence": (
            label + remount + poke + pre_peek + save + post_peek
            + load_file + content
        ),
        "next_operator_action": (
            f"open Freezer; mount {REMOTE_PRODUCT}; return with F3; "
            "physically power-cycle; wait for the lisp65 REPL"
        ),
        "result": "passed",
    })
    print(
        f"c2-lite G6 CASE 4 WRITE PASS file=g6r6 "
        f"next=mount-{REMOTE_PRODUCT}-and-power-cycle"
    )


def work_resume() -> None:
    _manifest, by_role = manifest_state()
    root = OUT / "case-04-work-media"
    require(
        (root / "write-phase.json").is_file()
        and not (root / "resume-phase.json").exists(),
        "work-media write phase is not ready",
    )
    remount_log = root / "postcycle-product-remount.log"
    if not remount_log.is_file():
        # Freezer-mounted D81 images are not retained across a reboot in the
        # qualified stock-core profile.  The inherited G6 operator text said
        # to wait for the product REPL after the physical cycle, contradicting
        # the public user guide.  Bind the stable BASIC state, then remount
        # the exact byte-verified R6 product image just as case 2 does.
        screen = run([
            "timeout", "20s", str(M65), "-l", DEVICE,
            f"--screenshot={root / 'postcycle-basic.png'}",
        ], "capture post-cycle BASIC context",
            output=root / "postcycle-basic.ansi.txt", timeout=25)
        screen_text = re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", screen)
        (root / "postcycle-basic.txt").write_text(
            screen_text, encoding="utf-8",
        )
        require(
            any(marker in screen_text.upper()
                for marker in ("READY.", "MEGA65", "COMMODORE")),
            "physical power-cycle did not reach stable BASIC",
        )
        product = artifact(by_role, "product-d81")
        upload_readback = (
            OUT / "case-02-cold-boot/uploaded-product-readback.d81"
        )
        require(
            upload_readback.is_file()
            and upload_readback.read_bytes() == product.read_bytes(),
            "post-cycle R6 product medium lacks byte-verified upload",
        )
        ftp(
            [f"mount {REMOTE_PRODUCT}", "exit"],
            "remount exact R6 product media after physical cycle",
            remount_log,
        )
        write(root / "harness-first-red-freezer-mount-persistence.json", {
            "format": "lisp65-G6-harness-first-red-v1",
            "version": 1,
            "id": "freezer-mount-not-retained-across-physical-reboot",
            "classification": "harness-only",
            "contradiction": {
                "inherited_operator_instruction": (
                    f"mount {REMOTE_PRODUCT}; return with F3; physically "
                    "power-cycle; wait for the lisp65 REPL"
                ),
                "qualified_profile": (
                    "Freezer-mounted D81 is not retained across reboot; "
                    "physical power-cycle reaches BASIC"
                ),
            },
            "recovery": {
                "medium": bind(product),
                "prior_upload_readback": bind(upload_readback),
                "action": "host-remount-exact-R6-product-after-cold-BASIC",
                "product_retry": "not-applicable-no-product-line-ran",
            },
            "evidence": [
                bind(root / "postcycle-basic.png"),
                bind(root / "postcycle-basic.ansi.txt"),
                bind(root / "postcycle-basic.txt"),
                bind(remount_log),
            ],
            "result": "bound-harness-first-red-exact-media-remounted",
        })
        time.sleep(30)
    await_product_repl(root, "postcycle-repl")
    cold = repl_form(root, "postcycle-repl", "(+ 4 5)", "9")
    memsave(0x0FFD3632, 4, root / "postcycle-core-registers.bin",
            "post-cycle core identity")
    libraries = repl_form(
        root, "postcycle-load",
        '(load-libs (list "ide" "m65d"))', "t", wait=4,
    )
    label = disk_label_byte(root, "postcycle-product-label", 211)
    write_phase = bind(root / "write-phase.json")
    cycle_id = hashlib.sha256(
        (root / "postcycle-core-registers.bin").read_bytes()
        + bytes.fromhex(write_phase["sha256"])
        + b"G6-work-media-power-cycle"
    ).hexdigest()[:24]
    write(root / "resume-phase.json", {
        "format": "lisp65-c2-lite-G6-work-phase-v1",
        "version": 1,
        "phase": "post-physical-power-cycle-product-repl",
        "cycle_id": cycle_id,
        "operator_confirmation": (
            "physical-power-cycle-to-BASIC-completed; exact-R6-product-"
            "medium-remounted-by-bound-host-path"
        ),
        "product_label": {
            "track": 40, "sector": 0, "offset": 7,
            "petscii_byte": 211, "text": "L65SYS",
        },
        "core_registers": bind(root / "postcycle-core-registers.bin"),
        "evidence": (
            [bind(root / "harness-first-red-freezer-mount-persistence.json")]
            + cold + libraries + label
        ),
        "next_operator_action": (
            f"open Freezer; mount {REMOTE_WORK}; return with F3"
        ),
        "result": "passed",
    })
    print(
        f"c2-lite G6 CASE 4 RESUME PASS cycle={cycle_id} "
        f"mount={REMOTE_WORK} return=F3"
    )


def work_read() -> None:
    manifest, by_role = manifest_state()
    root = OUT / "case-04-work-media"
    require(
        (root / "resume-phase.json").is_file()
        and not (root / "receipt.json").exists(),
        "work-media resume phase is not ready",
    )
    late_remount = root / "work-remount-after-cycle-late.txt"
    if (
        late_remount.is_file()
        and not list(root.glob("work-read-after-cycle*"))
    ):
        first_red = bind_late_remount_success(root)
        label = repl_evidence(root, "work-label-after-cycle")
        remount = (
            repl_evidence(root, "work-remount-after-cycle")
            + [bind(first_red)]
        )
    elif (
        (root / "work-remount-after-cycle-timing.json").is_file()
        and not list(root.glob("work-read-after-cycle*"))
    ):
        first_red = bind_remount_deadline_first_red(
            root, "work-remount-after-cycle",
        )
        label = repl_evidence(root, "work-label-after-cycle")
        remount = (
            repl_evidence(root, "work-remount-after-cycle")
            + [bind(first_red)]
        )
    else:
        label = disk_label_byte(root, "work-label-after-cycle", 215)
        remount = repl_form(
            root, "work-remount-after-cycle", "(m65d-remount)", "0",
        )
    load_file = repl_form(
        root, "work-read-after-cycle",
        '(load-file-to-buffer "g6r6" "g6b")', "t", wait=3,
    )
    content = repl_form(
        root, "work-content-after-cycle",
        "(ide-buffer-lines (cdr (car (symbol-value (quote ide-buffers)))))",
        '("persist")',
    )
    status_evidence = repl_form(
        root, "work-status-after-cycle", "(m65d-status)", "0",
    )
    product = artifact(by_role, "product-d81")
    work = artifact(by_role, "work-d81")
    resume = load(root / "resume-phase.json", "work resume phase")
    receipt = {
        "format": "lisp65-c2-lite-G6-case-receipt-v1",
        "version": 1,
        "id": CASES[3],
        "status": "passed",
        "authority": {
            "R6_manifest": bind(MANIFEST),
            "product_media": bind(product),
            "pristine_work_media": bind(work),
        },
        "cycle_id": resume["cycle_id"],
        "procedure": {
            "write": bind(root / "write-phase.json"),
            "physical_power_cycle": bind(root / "resume-phase.json"),
            "read_after_cycle": {
                "file": "g6r6", "content": ["persist"], "status": 0,
            },
        },
        "evidence": label + remount + load_file + content + status_evidence,
        "product_artifact_set_sha256": (
            manifest["product"]["artifact_set_sha256"]
        ),
        "result": "passed",
    }
    write(root / "receipt.json", receipt)
    print(
        f"c2-lite G6 CASE 4/5 PASS work-media-persisted "
        f"cycle={resume['cycle_id']} content=persist"
    )


def media_finalize(
    root: Path, manifest: dict[str, Any], by_role: dict[str, dict[str, Any]],
) -> None:
    product = artifact(by_role, "product-d81")
    pristine_work = artifact(by_role, "work-d81")
    product_after = root / "product-after-G6.d81"
    work_after = root / "work-after-G6.d81"
    require(
        product_after.read_bytes() == product.read_bytes(),
        "product medium changed during G6",
    )
    require(
        work_after.read_bytes() != pristine_work.read_bytes(),
        "work medium did not retain the G6 write",
    )
    listing = run(
        ["c1541", str(work_after), "-list"],
        "list final G6 work medium", output=root / "work-list.log",
    )
    require('"g6r6"' in listing.lower(), "G6 work file absent after power cycle")
    extract_root = root / "work-extracted"
    extract_root.mkdir(exist_ok=True)
    extracted = extract_root / "g6r6"
    if extracted.exists():
        extracted.unlink()
    run(
        ["c1541", str(work_after), "-extract"],
        "extract final G6 work medium", output=root / "work-extract.log",
        cwd=extract_root,
    )
    require(
        extracted.is_file() and b"persist" in extracted.read_bytes().lower(),
        "G6 work payload differs after power cycle",
    )
    case4 = OUT / "case-04-work-media/receipt.json"
    receipt = {
        "format": "lisp65-c2-lite-G6-case-receipt-v1",
        "version": 1,
        "id": CASES[4],
        "status": "passed",
        "authority": {
            "R6_manifest": bind(MANIFEST),
            "product_media": bind(product),
            "pristine_work_media": bind(pristine_work),
            "work_persistence_case": bind(case4),
        },
        "media_readback": {
            "product": bind(product_after),
            "work": bind(work_after),
            "product_comparison": "byteidentical",
            "work_comparison": "changed-only-by-authorized-G6-work-write",
            "work_listing": bind(root / "work-list.log"),
            "work_payload": bind(extracted),
        },
        "product_artifact_set_sha256": (
            manifest["product"]["artifact_set_sha256"]
        ),
        "result": "passed",
    }
    write(root / "receipt.json", receipt)

    case_receipts = [
        OUT / directory / "receipt.json" for directory in CASE_DIRS
    ]
    require(
        all(path.is_file() for path in case_receipts),
        "one or more canonical G6 case receipts are absent",
    )
    top = {
        "format": "lisp65-c2-lite-G6-hardware-receipt-v2",
        "version": 2,
        "id": SESSION_ID,
        "status": "passed-five-of-five",
        "product_artifact_set_sha256": (
            manifest["product"]["artifact_set_sha256"]
        ),
        "R6_manifest": bind(MANIFEST),
        "cases": [
            {"id": case, "receipt": bind(path)}
            for case, path in zip(CASES, case_receipts, strict=True)
        ],
        "claims": {
            "G5": "passed-nine-of-nine",
            "G6": "passed-five-of-five",
            "release": "not-promoted-until-remote-head-seal",
        },
        "result": "passed",
    }
    write(OUT / "g6-hardware-receipt.json", top)
    print(
        "c2-lite G6 CASE 5/5 PASS product-media=byteidentical "
        "work-media=persistent G6=5/5"
    )


def media_close() -> None:
    require(
        (OUT / "case-04-work-media/receipt.json").is_file(),
        "work-media case is not passed",
    )
    manifest, by_role = manifest_state()
    root = OUT / "case-05-product-media"
    require(not root.exists(), "G6 product-media case already exists")
    root.mkdir(parents=True)

    # Case 5 is entered only after the operator's physical cold start.  A
    # JTAG warm reset from the running product can leave the serial SD helper
    # installed but unable to transfer its first byte; two archived harness
    # first-reds bind that distinction.
    screen = run([
        "timeout", "20s", str(M65), "-l", DEVICE,
        f"--screenshot={root / 'cold-helper-context.png'}",
    ], "capture cold helper context",
        output=root / "cold-helper-context.log",
        timeout=25)
    screen_text = re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", screen)
    (root / "cold-helper-context.txt").write_text(
        screen_text, encoding="utf-8",
    )
    require(
        any(marker in screen_text.upper()
            for marker in ("READY.", "MEGA65", "COMMODORE")),
        "cold helper screen is not a stable BASIC/Hypervisor context",
    )
    product_after = root / "product-after-G6.d81"
    work_after = root / "work-after-G6.d81"
    helper_prime = root / "helper-prime.bin"
    helper_prime.write_bytes(b"G6")
    ftp(
        [
            f"put {helper_prime} G6PRIME.BIN",
            f"get {REMOTE_PRODUCT} {product_after}",
            f"get {REMOTE_WORK} {work_after}",
            "del G6PRIME.BIN",
            "exit",
        ],
        "prime helper and read final G6 media",
        root / "media-readback.log",
        timeout_seconds=180,
    )
    media_finalize(root, manifest, by_role)


def media_finalize_existing() -> None:
    require(
        (OUT / "case-04-work-media/receipt.json").is_file(),
        "work-media case is not passed",
    )
    manifest, by_role = manifest_state()
    root = OUT / "case-05-product-media"
    require(
        root.is_dir()
        and (root / "product-after-G6.d81").is_file()
        and (root / "work-after-G6.d81").is_file()
        and not (root / "receipt.json").exists(),
        "no incomplete final-media readback to close",
    )
    media_finalize(root, manifest, by_role)


def status() -> None:
    manifest, _ = manifest_state()
    print(f"G6 set={manifest['product']['artifact_set_sha256']}")
    for index, (directory, case) in enumerate(
        zip(CASE_DIRS, CASES, strict=True), 1,
    ):
        state = "passed" if (OUT / directory / "receipt.json").is_file() \
            else "not-run"
        print(f"{index}/5 {state} {case}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=(
            "prepare", "boot", "restage", "work-prepare", "work-write",
            "work-resume", "work-read", "media-close", "media-finalize",
            "status",
        ),
    )
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            prepare()
        elif args.command == "boot":
            boot()
        elif args.command == "restage":
            restage()
        elif args.command == "work-prepare":
            work_prepare()
        elif args.command == "work-write":
            work_write()
        elif args.command == "work-resume":
            work_resume()
        elif args.command == "work-read":
            work_read()
        elif args.command == "media-close":
            media_close()
        elif args.command == "media-finalize":
            media_finalize_existing()
        else:
            status()
    except (G6Error, subprocess.TimeoutExpired) as error:
        raise SystemExit(f"c2-lite G6: FAIL: {error}") from error


if __name__ == "__main__":
    main()
