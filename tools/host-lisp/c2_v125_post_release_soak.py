#!/usr/bin/env python3
"""Prepare, run, and verify the corrected v1.2.5 C2D soak."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth, ElfTruthError  # noqa: E402
import c2_v124_require_prior_append_h1 as H1  # noqa: E402
import repl_screen_check as SCREEN  # noqa: E402


CONFIG = ROOT / "config/c2-v125-post-release-soak.json"
CONTRACT = ROOT / (
    "docs/planning/c2d-append-visibility-soak-v125-correction-contract.md")
FIXTURE = ROOT / "tests/equivalence/c2-v124-post-release-soak.lisp"
DRIVER = Path(__file__).resolve()
PREPARATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/post-release/"
    "post-v125-corrected-soak-preparation-receipt-20260731.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/post-release/"
    "post-v125-corrected-soak-hardware-receipt-20260731.json")
OUT = ROOT / "build/post-release/v125/corrected-soak/session-02"
TOOLS = ROOT / os.environ.get("TOOLS", "tools/m65tools")
DEVICE = Path(os.environ.get("DEVICE", "/dev/ttyUSB1"))
M65 = TOOLS / "m65"
FTP = TOOLS / "mega65_ftp"
HARNESS = ROOT / "scripts/hw-jtag-repl.sh"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
TIMEOUT = int(os.environ.get("TIMEOUT", "60"))
EXPECT_POLL = int(os.environ.get("EXPECT_POLL", "120"))
FTP_STALL_LIMIT = int(os.environ.get("FTP_STALL_LIMIT", "120"))


class SoakError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SoakError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    require(path.is_file(), f"bound file absent: {path}")
    value: dict[str, Any] = {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }
    if address is not None:
        value["address"] = f"0x{address:08x}"
    return value


def check_binding(row: dict[str, Any]) -> Path:
    path = ROOT / row["path"]
    require(path.is_file(), f"bound path absent: {path}")
    require(
        ("bytes" not in row or path.stat().st_size == row["bytes"])
        and sha(path) == row["sha256"],
        f"binding drift: {path}",
    )
    return path


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run(
    command: list[str],
    *,
    timeout: int | None = None,
    capture: bool = True,
    check: bool = True,
    env: dict[str, str] | None = None,
    merge_stderr: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=(
            subprocess.STDOUT if capture and merge_stderr
            else subprocess.PIPE if capture else None
        ),
        timeout=timeout,
        check=False,
        env=env,
    )
    if check and result.returncode != 0:
        tail = ((result.stdout or "") + (result.stderr or ""))[-4000:]
        raise SoakError(
            f"command failed ({result.returncode}): {' '.join(command)}\n{tail}")
    return result


def forms(config: dict[str, Any]) -> list[str]:
    result = [row["form"] for row in config["setup"]]
    result += [
        config["batch"]["work_form"],
        config["batch"]["require_form"],
        config["batch"]["status_form"],
    ]
    for row in config["persistent_definitions"]:
        result.extend((row["form"], row["call"]))
    return result


def prepare() -> dict[str, Any]:
    config = load(CONFIG)
    schedule = config["schedule"]
    require(
        schedule["batches"] * schedule["cycles_per_batch"] == 1860
        and schedule["minimum_cycles"] == 1800
        and (schedule["batches"] - 1)
            * schedule["start_interval_seconds"] >= 1800,
        "soak schedule drift",
    )
    require(
        [row["batch"] for row in config["persistent_definitions"]]
        == [5, 10, 15, 20, 25, 30],
        "persistent-definition schedule drift",
    )

    deployment_path = check_binding(config["candidate"]["deployment"])
    hardware_path = check_binding(config["candidate"]["hardware_receipt"])
    deployment = load(deployment_path)
    hardware = load(hardware_path)
    require(
        deployment["candidate"]["release"] == "v1.2.5"
        and deployment["candidate"]["link"] == 82
        and deployment["candidate"]["product_build_id"]
            == config["candidate"]["product_build_id"]
        and hardware["status"]
            == "passed-require-after-two-ordinary-persistent-appends",
        "v1.2.5 deployment or device authority drift",
    )

    product = check_binding(deployment["candidate"]["product"])
    elf = check_binding(deployment["candidate"]["ELF"])
    package = check_binding(deployment["candidate"]["package_medium"])
    for row in deployment["candidate"]["preloads"]:
        check_binding(row)
    visible = H1.visible_files(package)
    required_files = set(config["candidate"]["package_visible_files"])
    require(
        required_files <= set(visible)
        and sorted(visible) == deployment["candidate"]["package_visible_files"],
        "package-medium visible inventory drift",
    )
    package_readback = ROOT / hardware["bindings"]["package_readback"]["path"]
    require(
        check_binding(hardware["bindings"]["package_readback"]) == package_readback
        and package.read_bytes() == package_readback.read_bytes(),
        "hardware-proved package readback drift",
    )

    truth = ElfTruth.read(elf, llvm_readobj=READOBJ)
    expected_symbols = {
        "c2_phase_owner": config["addresses"]["phase_owner"],
        "mem_oom": config["addresses"]["mem_oom"],
        "gc_badobj": config["addresses"]["gc_badobj"],
        "gc_runs": config["addresses"]["gc_runs"],
    }
    for symbol, expected in expected_symbols.items():
        require(
            truth.symbol(symbol).value == expected,
            f"ELF address drift: {symbol}",
        )
    scratch = truth.symbol("lisp65_c2_phase_scratch").value
    require(
        scratch + 302 == config["addresses"]["trace"],
        "ELF trace-address drift",
    )

    binary = ROOT / "build/equivalence/dialect-v2-equivalence-check"
    require(binary.is_file(), "equivalence runner absent")
    host: dict[str, Any] = {}
    for mode in ("vm", "lcc"):
        command = [str(binary), mode, str(FIXTURE)]
        if mode == "lcc":
            command += ["--preload", str(ROOT / "lib/lcc.lisp")]
        result = run(command, timeout=180)
        require(
            "=> %s" in result.stdout and "=> %sr" in result.stdout,
            f"{mode} did not compile both soak helpers",
        )
        host[mode] = {
            "status": "passed-exact-helper-definitions-compiled",
            "stdout_sha256":
                hashlib.sha256(result.stdout.encode()).hexdigest(),
            "lines": len(result.stdout.splitlines()),
        }
    for target, expected in (
        (
            "c2-require-prior-append-option-a-check",
            "baseline=t two-appends=t mutations=5 executions=7",
        ),
        (
            "c2-product-session-host-check",
            "c2-product-session-host: PASS cases=2 appends=3",
        ),
    ):
        result = run(
            ["make", "--no-print-directory", target], timeout=240)
        require(expected in result.stdout, f"{target} execution witness absent")
        host[target] = {
            "status": "passed",
            "stdout_sha256":
                hashlib.sha256(result.stdout.encode()).hexdigest(),
        }

    value = {
        "format":
            "lisp65-c2.2-v1.2.5-corrected-post-release-soak-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status": "prepared-host-green-package-bound-nonpromotable-soak",
        "schedule": {
            **schedule,
            "bound_cycles":
                schedule["batches"] * schedule["cycles_per_batch"],
            "bound_start_span_seconds":
                (schedule["batches"] - 1)
                * schedule["start_interval_seconds"],
        },
        "candidate": {
            "release": "v1.2.5",
            "link": 82,
            "product_build_id": config["candidate"]["product_build_id"],
            "product": bind(product, 0x2001),
            "ELF": bind(elf),
            "package_medium": bind(package),
            "package_visible_files": sorted(visible),
            "preloads": deployment["candidate"]["preloads"],
        },
        "target_ELF_witnesses": {
            **{
                name: f"0x{value:08x}"
                for name, value in expected_symbols.items()
            },
            "trace": f"0x{config['addresses']['trace']:08x}",
        },
        "host_dry_run": host,
        "safety": {
            "product_bytes_changed": 0,
            "product_links": 0,
            "cold_reset_and_fresh_BASIC_gate": True,
            "ftp_progress_guard_seconds": FTP_STALL_LIMIT,
            "package_inventory_bound_before_session": True,
            "first_anomaly_action": "stop feature activity, capture only",
            "readback_map": [
                "trace", "complete_c2d", "C2J", "phase_owner",
                "GC counters",
            ],
        },
        "authority": {
            "config": bind(CONFIG),
            "contract": bind(CONTRACT),
            "host_fixture": bind(FIXTURE),
            "driver": bind(DRIVER),
            "v1.2.5_deployment": bind(deployment_path),
            "v1.2.5_hardware_receipt": bind(hardware_path),
        },
        "claim_limit": config["claim_limit"],
    }
    write_json(PREPARATION, value)
    return value


class DeviceSession:
    def __init__(self, config: dict[str, Any], preparation: dict[str, Any]):
        self.config = config
        self.preparation = preparation
        self.deployment = load(
            ROOT / config["candidate"]["deployment"]["path"])
        self.out = OUT
        self.out.mkdir(parents=True, exist_ok=True)

    def m65(self, *args: str, timeout: int = TIMEOUT) -> str:
        return run(
            [str(M65), "-l", str(DEVICE), *args],
            timeout=timeout,
            merge_stderr=False,
        ).stdout

    def readback(self, address: int, count: int, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        end = address + count
        self.m65(
            "--memsave",
            f"0x{address:08x}:0x{end:08x}={path}",
        )
        require(path.stat().st_size == count, f"readback width drift: {path}")

    def capture_screen(self, prefix: str) -> tuple[Path, Path]:
        png = self.out / f"{prefix}.png"
        ansi = self.out / f"{prefix}.ansi.txt"
        text = self.out / f"{prefix}.txt"
        raw = self.m65(f"--screenshot={png}")
        ansi.write_text(raw, encoding="utf-8")
        text.write_text(
            re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw),
            encoding="utf-8",
        )
        SCREEN.check_fail_closed_frame(png)
        return png, text

    def poll_text(self, prefix: str, pattern: str, limit: int) -> Path:
        for _ in range(limit):
            _png, text = self.capture_screen(prefix)
            if pattern in text.read_text(errors="replace"):
                return text
            time.sleep(1)
        raise SoakError(f"screen pattern absent after {limit}s: {pattern}")

    def fresh_start(self) -> None:
        self.m65("-F")
        time.sleep(3)
        text = self.poll_text("fresh-start", "READY.", 30)
        screen = text.read_text(errors="replace")
        require(
            "BASIC 65" in screen and "lisp65>" not in screen,
            "fresh BASIC startup state not proven",
        )

    def ftp_package(self) -> None:
        package = ROOT / self.deployment["candidate"]["package_medium"]["path"]
        remote = self.config["candidate"]["remote_media"]
        readback = self.out / "package-readback.d81"
        log = self.out / "package-upload.log"
        command = [
            "stdbuf", "-oL", "-eL",
            str(FTP), "-0", "5", "-F", "-l", str(DEVICE),
            "-s", "2000000", "-y",
            "-c", f"put {package} {remote}",
            "-c", f"get {remote} {readback}",
            "-c", f"mount {remote}", "-c", "exit",
        ]
        with log.open("w", encoding="utf-8") as stream:
            process = subprocess.Popen(
                command, cwd=ROOT, text=True,
                stdout=stream, stderr=subprocess.STDOUT)
        last_size = -1
        last_progress = time.monotonic()
        while process.poll() is None:
            time.sleep(2)
            size = log.stat().st_size
            if size != last_size:
                last_size = size
                last_progress = time.monotonic()
            elif time.monotonic() - last_progress >= FTP_STALL_LIMIT:
                process.kill()
                process.wait()
                raise SoakError(
                    f"FTP stalled for {FTP_STALL_LIMIT} seconds")
        require(process.returncode == 0, "package FTP failed")
        require(
            package.read_bytes() == readback.read_bytes(),
            "package upload/readback drift",
        )

    def deploy(self) -> None:
        candidate = self.deployment["candidate"]
        product = ROOT / candidate["product"]["path"]
        self.m65("-H", "-1", str(product))
        for row in candidate["preloads"]:
            path = ROOT / row["path"]
            address = int(row["address"], 16)
            self.m65("-H", "-@", f"{path}@{row['address']}")
            captured = self.out / f"preload-{row['role']}.bin"
            self.readback(address, row["bytes"], captured)
            require(
                path.read_bytes() == captured.read_bytes(),
                f"preload readback drift: {row['role']}",
            )
        self.m65("-r", "-1", str(product))
        time.sleep(3)
        _png, text = self.capture_screen("boot-autorun")
        content = text.read_text(errors="replace")
        if (
            re.search(r"(?m)^\s*run:\s*$", content)
            and "lisp65>" not in content
        ):
            self.m65("-t", "~M")
        boot = self.poll_text("boot", "lisp65>", 75)
        require(
            self.config["candidate"]["expected_banner"]
            in boot.read_text(errors="replace"),
            "bound correction-release banner absent",
        )

    def run_form(
        self, prefix: str, form: str, expected: str | None,
        *, poll: int = EXPECT_POLL,
    ) -> Path:
        result = run(
            [
                str(HARNESS), "--verified-input", "--no-readback",
                "--form", form,
            ],
            timeout=TIMEOUT,
            env={
                **os.environ,
                "OUT_DIR": str(self.out),
                "PREFIX": f"{prefix}-input",
                "TIMEOUT_SEC": str(TIMEOUT),
            },
        )
        (self.out / f"{prefix}-input.log").write_text(
            result.stdout, encoding="utf-8")
        for _ in range(poll):
            _png, text = self.capture_screen(prefix)
            try:
                SCREEN.check_latest_result(text, form, expected)
                return text
            except SCREEN.CheckError:
                time.sleep(1)
        raise SoakError(f"no exact result for {prefix}: {form}")

    def capture_state(self, prefix: str) -> None:
        addresses = self.config["addresses"]
        for name, address, count in (
            ("trace", addresses["trace"], 2),
            ("c2d", addresses["c2d"], addresses["c2d_bytes"]),
            ("c2j", addresses["c2j"], addresses["c2j_bytes"]),
            ("phase-owner", addresses["phase_owner"], 1),
            ("gc-runs", addresses["gc_runs"], 2),
            ("mem-oom", addresses["mem_oom"], 1),
            ("gc-badobj", addresses["gc_badobj"], 2),
        ):
            self.readback(address, count, self.out / f"{prefix}-{name}.bin")

    def quiescent(self, prefix: str) -> None:
        q = self.config["quiescent_invariants"]
        c2d = (self.out / f"{prefix}-c2d.bin").read_bytes()
        c2j = (self.out / f"{prefix}-c2j.bin").read_bytes()
        owner = (self.out / f"{prefix}-phase-owner.bin").read_bytes()
        oom = (self.out / f"{prefix}-mem-oom.bin").read_bytes()
        require(
            c2d[:4] == b"C2D\0"
            and struct.unpack_from("<H", c2d, 8)[0]
                == q["transient_handle_watermark_u16"],
            f"{prefix}: C2D quiescent header drift",
        )
        require(c2j == bytes(len(c2j)), f"{prefix}: C2J is not CLEAR")
        require(
            owner == bytes([q["phase_owner"]]),
            f"{prefix}: phase owner is not NONE",
        )
        require(
            oom == bytes([q["mem_oom"]]),
            f"{prefix}: mem_oom is set",
        )

    def status(self, prefix: str, expected_cycles: int) -> dict[str, int]:
        form = self.config["batch"]["status_form"]
        text = self.run_form(prefix, form, None)
        matches = re.findall(
            r"^\s*\((\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+"
            r"(\d+)\s+(\d+)\s+(\d+)\)\s*$",
            text.read_text(errors="replace"),
            re.M,
        )
        require(bool(matches), f"{prefix}: status tuple absent")
        values = list(map(int, matches[-1]))
        cycles, mismatches, gc_lo, gc_hi, oom, bad_lo, bad_hi = values
        require(cycles == expected_cycles, f"{prefix}: cycle counter drift")
        require(
            mismatches == 0 and oom == 0,
            f"{prefix}: mismatch={mismatches} oom={oom}",
        )
        value = {
            "cycles": cycles,
            "mismatches": mismatches,
            "gc_runs": gc_lo | (gc_hi << 8),
            "mem_oom": oom,
            "gc_badobj": bad_lo | (bad_hi << 8),
        }
        write_json(self.out / f"{prefix}-status.json", value)
        return value

    def anomaly(self, prefix: str, detail: str) -> None:
        try:
            self.capture_screen(f"{prefix}-anomaly-screen")
        except Exception:
            pass
        try:
            self.capture_state(f"{prefix}-anomaly")
        except Exception:
            pass
        write_json(self.out / "first-anomaly.json", {
            "format": "lisp65-c2.2-v1.2.5-corrected-soak-anomaly-v1",
            "recorded_on": date.today().isoformat(),
            "status": "stopped-on-first-anomaly",
            "detail": detail,
            "capture_prefix": prefix,
            "preparation": bind(PREPARATION),
            "claim_limit": self.config["claim_limit"],
        })
        raise SoakError(f"SOAK ANOMALY: {detail}")

    def execute(self) -> None:
        try:
            self.fresh_start()
            self.readback(0x0FFD3632, 4, self.out / "device-core-id.bin")
            self.ftp_package()
            self.deploy()

            for row in self.config["setup"]:
                self.run_form(
                    f"setup-{row['id']}", row["form"], row["expected"])
            self.capture_state("baseline")
            self.quiescent("baseline")
            baseline = (self.out / "baseline-c2d.bin").read_bytes()
            images = struct.unpack_from("<H", baseline, 12)[0]
            place_slot = self.config["candidate"]["place_slot_after_helpers"]
            require(images == place_slot + 1, "baseline image-count drift")
            for slot in (6, 7, place_slot):
                at = 48 + slot * 32
                require(
                    baseline[at:at + 32] != bytes(32),
                    f"baseline persistent row absent: slot {slot}",
                )

            start_ns = time.time_ns()
            (self.out / "session-start-ns.txt").write_text(
                str(start_ns), encoding="ascii")
            start = time.time()
            schedule = self.config["schedule"]
            timeline: list[str] = []
            definitions = {
                row["batch"]: row
                for row in self.config["persistent_definitions"]
            }
            for batch in range(1, schedule["batches"] + 1):
                target = start + (batch - 1) * schedule["start_interval_seconds"]
                if target > time.time():
                    time.sleep(target - time.time())
                elapsed = int(time.time() - start)
                print(
                    f"SOAK batch {batch:02d}/{schedule['batches']:02d} "
                    f"start elapsed={elapsed}s",
                    flush=True,
                )
                if batch in definitions:
                    row = definitions[batch]
                    self.run_form(
                        f"batch-{batch:02d}-definition",
                        row["form"], row["expected"])
                    self.run_form(
                        f"batch-{batch:02d}-definition-call",
                        row["call"], row["call_expected"])

                pre = f"batch-{batch:02d}-pre"
                self.capture_state(pre)
                self.quiescent(pre)
                pre_c2d = (self.out / f"{pre}-c2d.bin").read_bytes()
                self.run_form(
                    f"batch-{batch:02d}-require",
                    self.config["batch"]["require_form"],
                    self.config["batch"]["require_expected"],
                )
                post_require = f"batch-{batch:02d}-post-require"
                self.capture_state(post_require)
                self.quiescent(post_require)
                require(
                    pre_c2d
                    == (self.out / f"{post_require}-c2d.bin").read_bytes(),
                    f"batch {batch}: idempotent require changed C2D",
                )

                self.run_form(
                    f"batch-{batch:02d}-work",
                    self.config["batch"]["work_form"],
                    self.config["batch"]["work_expected"],
                )
                post = f"batch-{batch:02d}-post"
                self.capture_state(post)
                self.quiescent(post)
                require(
                    pre_c2d == (self.out / f"{post}-c2d.bin").read_bytes(),
                    f"batch {batch}: transient work changed persistent C2D",
                )
                expected = batch * schedule["cycles_per_batch"]
                self.status(f"batch-{batch:02d}-status", expected)
                timeline.append(f"{batch} {int(time.time())} {expected}")
                (self.out / "batch-timeline.txt").write_text(
                    "\n".join(timeline) + "\n", encoding="ascii")

            (self.out / "session-end-ns.txt").write_text(
                str(time.time_ns()), encoding="ascii")
            self.capture_state("final")
            self.quiescent("final")
            self.capture_screen("final-screen")
        except Exception as error:
            self.anomaly("session", str(error))


def evaluate() -> dict[str, Any]:
    config = load(CONFIG)
    preparation = load(PREPARATION)
    statuses = [
        load(path)
        for path in sorted(OUT.glob("batch-*-status-status.json"))
    ]
    schedule = config["schedule"]
    require(
        len(statuses) == schedule["batches"],
        "status-row count drift",
    )
    completed = statuses[-1]["cycles"]
    require(completed >= schedule["minimum_cycles"], "too few soak cycles")
    require(
        all(row["mismatches"] == 0 and row["mem_oom"] == 0
            for row in statuses),
        "semantic mismatch or OOM in status rows",
    )
    start_ns = int((OUT / "session-start-ns.txt").read_text())
    end_ns = int((OUT / "session-end-ns.txt").read_text())
    elapsed = (end_ns - start_ns) // 1_000_000_000
    require(
        elapsed >= schedule["minimum_session_seconds"],
        "soak session was shorter than 30 minutes",
    )
    baseline_gc = struct.unpack(
        "<H", (OUT / "baseline-gc-runs.bin").read_bytes())[0]
    final_gc = struct.unpack(
        "<H", (OUT / "final-gc-runs.bin").read_bytes())[0]
    baseline_bad = struct.unpack(
        "<H", (OUT / "baseline-gc-badobj.bin").read_bytes())[0]
    final_bad = struct.unpack(
        "<H", (OUT / "final-gc-badobj.bin").read_bytes())[0]
    final_oom = (OUT / "final-mem-oom.bin").read_bytes()[0]
    require(final_gc > baseline_gc, "soak did not exercise GC")
    require(final_bad == baseline_bad, "gc_badobj changed")
    require(final_oom == 0, "final mem_oom is set")

    deployment = load(
        ROOT / config["candidate"]["deployment"]["path"])
    package = ROOT / deployment["candidate"]["package_medium"]["path"]
    require(
        package.read_bytes() == (OUT / "package-readback.d81").read_bytes(),
        "mounted package readback drift",
    )
    value = {
        "format":
            "lisp65-c2.2-v1.2.5-corrected-post-release-soak-hardware-v1",
        "recorded_on": date.today().isoformat(),
        "status": "passed-clean-1860-cycle-30-minute-corrected-soak",
        "device": {
            "core_register": bind(
                OUT / "device-core-id.bin", 0x0FFD3632),
        },
        "candidate": {
            "release": "v1.2.5",
            "link": 82,
            "product_build_id": config["candidate"]["product_build_id"],
            "package_medium": bind(package),
            "package_readback": bind(OUT / "package-readback.d81"),
        },
        "result": {
            "completed_cycles": completed,
            "elapsed_seconds": elapsed,
            "batches": len(statuses),
            "require_rows": len(statuses) + 1,
            "persistent_definitions":
                2 + len(config["persistent_definitions"]),
            "semantic_mismatches": statuses[-1]["mismatches"],
            "gc_runs_before": baseline_gc,
            "gc_runs_after": final_gc,
            "gc_runs_delta": final_gc - baseline_gc,
            "gc_badobj_before": baseline_bad,
            "gc_badobj_after": final_bad,
            "gc_badobj_delta": final_bad - baseline_bad,
            "mem_oom": final_oom,
            "c2j_clear_after_every_batch": True,
            "phase_owner_none_after_every_batch": True,
            "persistent_C2D_unchanged_by_each_idempotent_require": True,
            "persistent_C2D_unchanged_by_each_transient_batch": True,
            "package_inventory_bound_before_session": True,
        },
        "interpretation": {
            "pre_registered_outcome":
                "bounded-exoneration-at-1860-cycle-30-minute-soak-scale",
            "chip_ram_append_visibility":
                "retired-as-active-post-GC-OOM-suspect-at-soak-scale",
            "intermittent_post_GC_OOM": "remains-open-single-sighting",
        },
        "evidence": {
            "timeline": bind(OUT / "batch-timeline.txt"),
            "final_screen_text": bind(OUT / "final-screen.txt"),
            "final_screen_png": bind(OUT / "final-screen.png"),
            "final_trace": bind(
                OUT / "final-trace.bin", config["addresses"]["trace"]),
            "final_c2d": bind(
                OUT / "final-c2d.bin", config["addresses"]["c2d"]),
            "final_c2j": bind(
                OUT / "final-c2j.bin", config["addresses"]["c2j"]),
            "final_gc_runs": bind(
                OUT / "final-gc-runs.bin", config["addresses"]["gc_runs"]),
        },
        "execution_accounting": {
            "physical_device_sessions": 1,
            "cold_resets": 1,
            "product_links": 0,
            "product_bytes_changed": 0,
            "promotable_candidates": 0,
        },
        "authority": {
            "config": bind(CONFIG),
            "contract": bind(CONTRACT),
            "preparation": bind(PREPARATION),
            "driver": bind(DRIVER),
        },
        "claim_limit": config["claim_limit"],
    }
    write_json(RECEIPT, value)
    return value


def verify() -> dict[str, Any]:
    value = load(RECEIPT)
    config = load(CONFIG)
    require(
        value["status"]
            == "passed-clean-1860-cycle-30-minute-corrected-soak"
        and value["result"]["completed_cycles"]
            >= config["schedule"]["minimum_cycles"]
        and value["result"]["elapsed_seconds"]
            >= config["schedule"]["minimum_session_seconds"]
        and value["result"]["semantic_mismatches"] == 0
        and value["result"]["mem_oom"] == 0
        and value["result"]["gc_badobj_delta"] == 0
        and value["result"]["gc_runs_delta"] > 0,
        "corrected-soak receipt invariant failed",
    )
    return value


def selftest() -> None:
    config = load(CONFIG)
    schedule = config["schedule"]
    require(schedule["batches"] * schedule["cycles_per_batch"] == 1860,
            "schedule mutation accepted")
    sample = bytearray(48 + 9 * 32)
    sample[:4] = b"C2D\0"
    struct.pack_into("<H", sample, 12, 9)
    for slot in (6, 7, 8):
        sample[48 + slot * 32] = 1
    require(
        struct.unpack_from("<H", sample, 12)[0] == 9
        and all(sample[48 + slot * 32] for slot in (6, 7, 8)),
        "live package-row model failed",
    )
    mutated = bytearray(sample)
    mutated[48 + 8 * 32:48 + 9 * 32] = bytes(32)
    rejected = 0
    try:
        require(
            all(mutated[48 + slot * 32] for slot in (6, 7, 8)),
            "mutation",
        )
    except SoakError:
        rejected += 1
    require(rejected == 1, "absent package row mutation accepted")
    streams = run(
        [
            sys.executable, "-c",
            "import sys; print('screen'); print('diagnostic', file=sys.stderr)",
        ],
        merge_stderr=False,
    )
    require(
        streams.stdout.strip() == "screen"
        and streams.stderr.strip() == "diagnostic",
        "screen/diagnostic stream separation failed",
    )


def dry_run() -> None:
    value = prepare()
    for index, form in enumerate(forms(load(CONFIG))):
        run(
            [
                str(HARNESS), "--dry-run", "--verified-input",
                "--form", form,
            ],
            timeout=TIMEOUT,
        )
    print(
        "c2-v125-corrected-soak: DRY-RUN PASS "
        f"forms={len(forms(load(CONFIG)))} "
        f"package={value['candidate']['package_medium']['sha256']} "
        "cycles=1860 span=1800s")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=("selftest", "prepare", "dry-run", "start", "evaluate",
                 "verify"),
    )
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            selftest()
            print("c2-v125-corrected-soak: SELFTEST PASS mutations=1")
        elif args.action == "prepare":
            value = prepare()
            print(
                "c2-v125-corrected-soak: PREPARE PASS "
                f"cycles={value['schedule']['bound_cycles']} "
                f"package-files={len(value['candidate']['package_visible_files'])}")
        elif args.action == "dry-run":
            dry_run()
        elif args.action == "start":
            require(M65.is_file() and FTP.is_file(), "MEGA65 tools absent")
            require(DEVICE.exists(), f"JTAG device absent: {DEVICE}")
            require(not RECEIPT.exists(), "hardware receipt already exists")
            require(
                not (OUT / "session-start-ns.txt").exists()
                and not (OUT / "first-anomaly.json").exists(),
                "prior device-attempt state exists; preserve and disposition it",
            )
            preparation = prepare()
            session = DeviceSession(load(CONFIG), preparation)
            session.execute()
            value = evaluate()
            print(
                "c2-v125-corrected-soak: PASS "
                f"cycles={value['result']['completed_cycles']} "
                f"seconds={value['result']['elapsed_seconds']} "
                f"gc={value['result']['gc_runs_delta']} mismatch=0")
        elif args.action == "evaluate":
            value = evaluate()
            print(
                "c2-v125-corrected-soak: EVALUATE PASS "
                f"cycles={value['result']['completed_cycles']}")
        else:
            value = verify()
            print(
                "c2-v125-corrected-soak: VERIFY PASS "
                f"cycles={value['result']['completed_cycles']} "
                f"seconds={value['result']['elapsed_seconds']}")
        return 0
    except (
        SoakError, H1.H1Error, SCREEN.CheckError, ElfTruthError,
        OSError, ValueError, KeyError, TypeError, json.JSONDecodeError,
        subprocess.TimeoutExpired,
    ) as error:
        print(f"c2-v125-corrected-soak: FIRST RED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
