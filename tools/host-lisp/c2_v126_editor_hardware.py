#!/usr/bin/env python3
"""Prepare, run and verify the v1.2.6 editor usability session."""

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
from elf_truth import ElfTruth  # noqa: E402
import c2_v124_require_prior_append_h1 as H1  # noqa: E402
import c2_v125_post_release_soak as BASE  # noqa: E402
import repl_screen_check as SCREEN  # noqa: E402


CONFIG = ROOT / "config/c2-v126-editor-hardware-session.json"
CONTRACT = ROOT / "docs/planning/c2.2-v1.2.6-editor-allocation-contract.md"
PLAN = ROOT / "docs/planning/1.2.6-work-plan.md"
DRIVER = Path(__file__).resolve()
PREPARATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-hardware-preparation-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-hardware-receipt.json")
SESSION_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-hardware-first-red-receipt.json")
ALLOCATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2-v126-editor-allocation-gate-receipt.json")
WPLTO = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-wplto-receipt.json")
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-hardware-preload-first-red.json")
BOOT_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-hardware-zero-c2j-first-red.json")
MONITOR_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-hardware-memsave-exit-first-red.json")
START_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-hardware-virtual-run-first-red.json")
RESUME_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-hardware-monitor-resume-first-red.json")
OUT = ROOT / "build/c2.2/v1.2.6-editor-hardware/session-01"
DEPLOYMENT = OUT.parent / "deployment.json"
ZERO_C2J = OUT.parent / "zero-c2j.bin"
DIRECT_TRIGGER = OUT.parent / "direct-entry-trigger.prg"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
HARNESS = ROOT / "scripts/hw-jtag-repl.sh"
ETHERLOAD = ROOT / "tools/m65tools/etherload"


class SessionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SessionError(message)


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
        path.stat().st_size == row["bytes"] and sha(path) == row["sha256"],
        f"binding drift: {path}",
    )
    return path


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def artifact_by_role(
    manifest: dict[str, Any], role: str,
) -> dict[str, Any]:
    rows = [row for row in manifest["artifacts"] if row["role"] == role]
    require(len(rows) == 1, f"candidate role count drift: {role}")
    row = dict(rows[0])
    check_binding(row)
    return row


def candidate_deployment(
    config: dict[str, Any], manifest: dict[str, Any],
) -> dict[str, Any]:
    product = artifact_by_role(manifest, "c2-resident-prg")
    product["address"] = "0x00002001"
    elf = artifact_by_role(manifest, "linked-product-elf")
    package = artifact_by_role(manifest, "product-d81")
    preloads: list[dict[str, Any]] = []
    for role, address_text in config["preload_addresses"].items():
        row = artifact_by_role(manifest, role)
        row["address"] = address_text
        preloads.append(row)
    preloads.append({
        **bind(ZERO_C2J, 0x0005C640),
        "name": "zero-c2j.bin",
        "role": "harness-zero-C2J-baseline",
    })
    return {
        "format": "lisp65-c2.2-v1.2.6-editor-deployment-v1",
        "recorded_on": date.today().isoformat(),
        "candidate": {
            "release": config["candidate"]["release"],
            "link": config["candidate"]["link"],
            "manifest": bind(
                ROOT / config["candidate"]["manifest"]),
            "artifact_set_sha256": manifest["artifact_set_sha256"],
            "product": product,
            "ELF": elf,
            "package_medium": package,
            "remote_media": config["candidate"]["remote_media"],
            "preloads": preloads,
            "promotable": False,
        },
    }


def form_rows(config: dict[str, Any]) -> list[tuple[str, str | None]]:
    rows: list[tuple[str, str | None]] = []
    for key in ("wrap_setup_forms", "scroll_setup_forms"):
        rows += [
            (row["form"], row["expected"])
            for row in config["D2"][key]
        ]
    rows += [
        (config["D2"]["wrap_form"], "t"),
        (config["D2"]["scroll_form"], "t"),
    ]
    rows += [
        (row["form"], row["expected"])
        for row in config["D3"]["smoke_rows"]
    ]
    rows += [
        ("(edit)", None),
        ("(ide\"scroll\")", None),
        ("(defun %ib(n a)(if a(if(string= n(caar a))(cdar a)(%ib n(cdr a)))nil))",
         "%ib"),
        ("(progn(setq b(%ib\"scratch\"(symbol-value(quote ide-buffers))))t)",
         "t"),
        ("(list(ide-line-count b)(string-length(ide-line-at b 0)))",
         "(2 79)"),
        ("(string-length(ide-line-at b 1))", "1"),
        ("(progn(setq b(%ib\"scroll\"(symbol-value(quote ide-buffers))))t)",
         "t"),
        ("(ide-line-count b)", "50"),
    ]
    return rows


def prepare() -> dict[str, Any]:
    config = load(CONFIG)
    manifest_path = ROOT / config["candidate"]["manifest"]
    manifest = load(manifest_path)
    require(
        manifest["artifact_count"] == 19
        and len(manifest["artifacts"]) == 19,
        "candidate-media inventory drift",
    )
    for row in manifest["artifacts"]:
        check_binding(row)
    canonical = check_binding(manifest["canonical_product"])
    ZERO_C2J.parent.mkdir(parents=True, exist_ok=True)
    ZERO_C2J.write_bytes(bytes(64))
    direct = config["direct_entry"]
    trigger_address = int(direct["trigger_load_address"], 16)
    trigger_payload = bytes(direct["trigger_payload_bytes"])
    DIRECT_TRIGGER.write_bytes(
        struct.pack("<H", trigger_address) + trigger_payload)
    require(
        trigger_address + len(trigger_payload) < 0xC000,
        "direct-entry trigger crossed the etherload ceiling",
    )
    deployment = candidate_deployment(config, manifest)
    write_json(DEPLOYMENT, deployment)

    package = check_binding(deployment["candidate"]["package_medium"])
    visible = sorted(H1.visible_files(package))
    require(
        visible == sorted(config["candidate"]["required_visible_files"]),
        "product D81 visible inventory drift",
    )

    elf = check_binding(deployment["candidate"]["ELF"])
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ)
    symbols = {
        name: truth.symbol(name).value
        for name in (
            "lisp65_c2_phase_scratch",
            "c2_phase_owner",
            "gc_runs",
            "mem_oom",
            "gc_badobj",
        )
    }
    require(
        symbols["lisp65_c2_phase_scratch"] + 302 <= 0xFFFF,
        "trace address escaped CPU space",
    )

    allocation = load(ALLOCATION)
    wplto = load(WPLTO)
    require(
        allocation["status"] == "passed"
        and allocation["execution_witness"]["keys"] == 165,
        "allocation-gate authority drift",
    )
    require(
        wplto["status"] == "passed-editor-one-product-shaped-WPLTO"
        and wplto["static_geometry"]["delta"]["resident_bytes"] == 0,
        "editor WPLTO authority drift",
    )
    for form, _expected in form_rows(config):
        require(
            len(form) <= 76,
            f"hardware form exceeds verified-input ceiling ({len(form)}): "
            f"{form}",
        )
        result = BASE.run(
            [
                str(HARNESS), "--dry-run", "--verified-input",
                "--form", form,
            ],
            timeout=30,
        )
        require("DRY-RUN:" in result.stdout, "verified-input dry-run absent")

    d1 = config["D1"]
    require(
        d1["plain_burst_keys"] + d1["plain_fill_keys"] + 2 == 80
        and d1["scroll_prep_returns"] + 1 == 49
        and d1["maximum_average_frames_per_key"] == 88
        and d1["maximum_single_key_frames"] == 177,
        "D1 schedule or preregistered frame ceiling drift",
    )

    value = {
        "format":
            "lisp65-c2.2-v1.2.6-editor-hardware-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status":
            "prepared-host-green-link83-bound-one-device-session",
        "candidate": {
            "release": config["candidate"]["release"],
            "link": config["candidate"]["link"],
            "artifact_set_sha256": manifest["artifact_set_sha256"],
            "manifest": bind(manifest_path),
            "canonical_product": bind(canonical),
            "deployment": bind(DEPLOYMENT),
            "product": deployment["candidate"]["product"],
            "ELF": deployment["candidate"]["ELF"],
            "package_medium": deployment["candidate"]["package_medium"],
            "package_visible_files": visible,
            "preloads": deployment["candidate"]["preloads"],
        },
        "target_ELF_witnesses": {
            name: f"0x{address:08x}"
            for name, address in symbols.items()
        },
        "host_proofs": {
            "allocation_gate": bind(ALLOCATION),
            "WPLTO": bind(WPLTO),
            "preload_harness_first_red": bind(FIRST_RED),
            "zero_C2J_harness_first_red": bind(BOOT_FIRST_RED),
            "memsave_exit_harness_first_red": bind(MONITOR_FIRST_RED),
            "virtual_RUN_harness_first_red": bind(START_FIRST_RED),
            "monitor_resume_harness_first_red": bind(RESUME_FIRST_RED),
            "verified_input_forms": len(form_rows(config)),
        },
        "measurement_contract": {
            "plain_burst_keys": d1["plain_burst_keys"],
            "total_printable_keys": 80,
            "total_return_keys": 49,
            "frame_ceiling_average": 88,
            "frame_ceiling_single": 177,
            "dropped_characters": 0,
            "dropped_returns": 0,
            "D2_time_spot_checks": ["wrap", "scroll"],
        },
        "safety": {
            "cold_reset_and_fresh_BASIC_gate": True,
            "ftp_progress_guard_seconds":
                config["policy"]["ftp_no_progress_timeout_seconds"],
            "package_upload_readback_required": True,
            "preload_target_readback_required": True,
            "C2J_CLEAR_preload_required": bind(
                ZERO_C2J, 0x0005C640),
            "direct_entry_trigger": bind(
                DIRECT_TRIGGER, trigger_address),
            "direct_entry": direct["entry"],
            "direct_entry_product_load":
                direct["product_loaded_by"],
            "direct_entry_control_transfer":
                direct["control_transferred_by"],
            "fail_closed_red_frame_is_terminal": True,
            "product_bytes_changed_by_session": 0,
            "promotable_candidates": 0,
        },
        "authority": {
            "config": bind(CONFIG),
            "allocation_contract": bind(CONTRACT),
            "work_plan": bind(PLAN),
            "driver": bind(DRIVER),
        },
        "claim_limit": config["policy"]["claim_limit"],
    }
    write_json(PREPARATION, value)
    return value


class EditorSession(BASE.DeviceSession):
    def __init__(
        self, config: dict[str, Any], preparation: dict[str, Any],
    ):
        self.config = {
            **config,
            "candidate": {
                **config["candidate"],
                "deployment": bind(DEPLOYMENT),
            },
        }
        self.preparation = preparation
        self.deployment = load(DEPLOYMENT)
        self.out = OUT
        self.out.mkdir(parents=True, exist_ok=True)
        self.exitless_readbacks: list[dict[str, Any]] = []

    def readback(self, address: int, count: int, path: Path) -> None:
        """Accept an exitless m65 only after a fresh, exact-width transfer."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.unlink(missing_ok=True)
        end = address + count
        try:
            self.m65(
                "--memsave",
                f"0x{address:08x}:0x{end:08x}={path}",
                timeout=15,
            )
        except subprocess.TimeoutExpired:
            require(
                path.is_file() and path.stat().st_size == count,
                f"exitless readback has no fresh exact-width result: {path}",
            )
            self.exitless_readbacks.append({
                "address": f"0x{address:08x}",
                "bytes": count,
                "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
                "classification":
                    "transfer-complete-m65-process-exit-timeout",
            })
        require(
            path.is_file() and path.stat().st_size == count,
            f"readback width drift: {path}",
        )

    def validate_resident_product(
        self, product: Path, resident: Path,
    ) -> dict[str, Any]:
        """Require identity outside ELF NOBITS; report allowed BSS dirt."""
        expected = product.read_bytes()[2:]
        observed = resident.read_bytes()
        require(
            len(observed) == len(expected),
            "direct-entry resident product width drift",
        )
        truth = ElfTruth.read(
            check_binding(self.deployment["candidate"]["ELF"]),
            llvm_readobj=READOBJ,
        )
        bss_start = truth.symbol("__bss_start").value
        bss_end = truth.symbol("__bss_end").value
        differences = [
            {
                "address": f"0x{0x2001 + offset:08x}",
                "expected": before,
                "observed": after,
            }
            for offset, (before, after)
            in enumerate(zip(expected, observed))
            if before != after
        ]
        require(
            all(
                bss_start <= int(row["address"], 16) < bss_end
                for row in differences
            ),
            "direct-entry loaded ELF content drift outside NOBITS BSS",
        )
        value = {
            "status": "loaded-ELF-content-byteidentical",
            "BSS": {
                "start": f"0x{bss_start:08x}",
                "end_exclusive": f"0x{bss_end:08x}",
                "pre_start_differences_allowed": len(differences),
            },
            "differences": differences,
        }
        write_json(self.out / "direct-entry-resident-compare.json", value)
        return value

    def transfer_direct_entry(self, product: Path) -> None:
        config = load(CONFIG)
        direct = config["direct_entry"]
        result = BASE.run(
            [
                str(ETHERLOAD), "-i", direct["etherload_ip"],
                "--jump", direct["entry"][2:], str(DIRECT_TRIGGER),
            ],
            timeout=60,
            merge_stderr=False,
        )
        (self.out / "direct-entry-etherload.log").write_text(
            result.stdout + result.stderr, encoding="utf-8")
        time.sleep(3)
        boot = self.poll_text(
            "direct-entry-boot", "lisp65>", 75)
        require(
            self.config["candidate"]["expected_banner"]
            in boot.read_text(errors="replace"),
            "direct entry reached an unbound REPL",
        )
        write_json(self.out / "direct-entry.json", {
            "format": "lisp65-c2.2-v1.2.6-direct-entry-v1",
            "recorded_on": date.today().isoformat(),
            "status": "passed-bound-product-direct-entry",
            "entry": direct["entry"],
            "trigger": bind(
                DIRECT_TRIGGER,
                int(direct["trigger_load_address"], 16)),
            "resident_product": bind(
                self.out / "direct-entry-resident.bin", 0x2001),
            "resident_compare": bind(
                self.out / "direct-entry-resident-compare.json"),
            "product_authority": bind(product),
            "screen": bind(boot),
            "product_bytes_changed": 0,
        })

    def frame(self, prefix: str) -> int:
        path = self.out / f"{prefix}-frame.bin"
        self.readback(0xFF83, 2, path)
        return struct.unpack("<H", path.read_bytes())[0]

    def deploy(self) -> None:
        """Deploy with a bounded USB settle gap between monitor commands."""
        candidate = self.deployment["candidate"]
        product = ROOT / candidate["product"]["path"]
        self.m65("-H", "-1", str(product))
        time.sleep(0.75)
        for row in candidate["preloads"]:
            path = ROOT / row["path"]
            address = int(row["address"], 16)
            self.m65("-H", "-@", f"{path}@{row['address']}")
            time.sleep(0.75)
            captured = self.out / f"preload-{row['role']}.bin"
            self.readback(address, row["bytes"], captured)
            require(
                path.read_bytes() == captured.read_bytes(),
                f"preload readback drift: {row['role']}",
            )
            time.sleep(0.75)
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
            "bound v1.2.6 banner absent",
        )

    def arm_physical_sys(self) -> None:
        """Load the bound candidate, but leave BASIC to a physical SYS."""
        self.fresh_start()
        self.readback(
            0x0FFD3632, 4, self.out / "device-core-id.bin")
        self.ftp_package()
        candidate = self.deployment["candidate"]
        product = ROOT / candidate["product"]["path"]
        self.m65("-H", "-1", str(product))
        time.sleep(0.75)
        for row in candidate["preloads"]:
            path = ROOT / row["path"]
            address = int(row["address"], 16)
            self.m65("-H", "-@", f"{path}@{row['address']}")
            time.sleep(0.75)
            captured = self.out / f"preload-{row['role']}.bin"
            self.readback(address, row["bytes"], captured)
            require(
                path.read_bytes() == captured.read_bytes(),
                f"preload readback drift: {row['role']}",
            )
            time.sleep(0.75)
        self.m65("-1", str(product))
        time.sleep(3)
        _png, text = self.capture_screen("physical-sys-armed")
        content = text.read_text(errors="replace")
        require(
            "READY." in content.upper()
            and "lisp65>" not in content
            and "run:" not in content.lower(),
            "physical-SYS arm did not leave a clean BASIC prompt",
        )
        stub = self.out / "physical-sys-armed-stub.bin"
        self.readback(0x2001, 32, stub)
        require(
            stub.read_bytes() == product.read_bytes()[2:34],
            "physical-SYS arm resident entry stub drift",
        )
        write_json(self.out / "physical-sys-armed.json", {
            "format": "lisp65-c2.2-v1.2.6-physical-sys-arm-v1",
            "recorded_on": date.today().isoformat(),
            "status": "armed-clean-BASIC-for-physical-SYS-8227",
            "screen": bind(text),
            "resident_stub": bind(stub, 0x2001),
            "entry": "0x00002023",
            "typed_command": "SYS 8227",
            "product_bytes_changed": 0,
        })

    def direct_deploy(self) -> None:
        """Load over proven USB paths, then transfer control via etherload."""
        config = load(CONFIG)
        direct = config["direct_entry"]
        _png, text = self.capture_screen("direct-entry-fresh")
        content = text.read_text(errors="replace")
        require(
            "READY." in content.upper()
            and "lisp65>" not in content,
            "direct-entry precondition is not fresh BASIC",
        )
        self.readback(
            0x0FFD3632, 4, self.out / "device-core-id.bin")
        self.ftp_package()
        candidate = self.deployment["candidate"]
        product = ROOT / candidate["product"]["path"]
        self.m65("-H", "-1", str(product))
        time.sleep(0.75)
        for row in candidate["preloads"]:
            path = ROOT / row["path"]
            address = int(row["address"], 16)
            self.m65("-H", "-@", f"{path}@{row['address']}")
            time.sleep(0.75)
            captured = self.out / f"preload-{row['role']}.bin"
            self.readback(address, row["bytes"], captured)
            require(
                path.read_bytes() == captured.read_bytes(),
                f"preload readback drift: {row['role']}",
            )
            time.sleep(0.75)
        resident = self.out / "direct-entry-resident.bin"
        self.readback(0x2001, product.stat().st_size - 2, resident)
        self.validate_resident_product(product, resident)
        self.transfer_direct_entry(product)

    def continue_loaded_direct(self) -> None:
        """Continue an already readback-proven, CPU-held direct deploy."""
        candidate = self.deployment["candidate"]
        product = ROOT / candidate["product"]["path"]
        require(
            (self.out / "package-readback.d81").read_bytes()
            == (ROOT / candidate["package_medium"]["path"]).read_bytes(),
            "continued direct-entry package readback drift",
        )
        for row in candidate["preloads"]:
            require(
                (self.out / f"preload-{row['role']}.bin").read_bytes()
                == (ROOT / row["path"]).read_bytes(),
                f"continued direct-entry preload drift: {row['role']}",
            )
        resident = self.out / "direct-entry-resident.bin"
        self.validate_resident_product(product, resident)
        self.transfer_direct_entry(product)

    def media_deploy(self) -> None:
        """Boot exactly once through the mounted product-medium AUTOBOOT."""
        config = load(CONFIG)
        self.fresh_start()
        self.readback(
            0x0FFD3632, 4, self.out / "device-core-id.bin")
        self.m65("-@", f"{ZERO_C2J}@0x0005c640")
        time.sleep(0.75)
        zero_readback = self.out / "media-preboot-zero-c2j.bin"
        self.readback(0x5C640, 64, zero_readback)
        require(
            zero_readback.read_bytes() == bytes(64),
            "media preboot zero-C2J readback drift",
        )
        _png, basic = self.capture_screen(
            "media-preboot-zero-c2j-basic")
        require(
            "READY." in basic.read_text(errors="replace").upper()
            and "lisp65>" not in basic.read_text(errors="replace"),
            "zero-C2J preload disturbed fresh BASIC",
        )
        self.ftp_package()
        wait = config["canonical_entry"]["startup_wait_seconds"]
        boot = self.poll_text(
            "media-autoboot", "lisp65>", wait)
        require(
            self.config["candidate"]["expected_banner"]
            in boot.read_text(errors="replace"),
            "product-medium autoboot reached an unbound REPL",
        )
        target_readbacks = self.media_target_readbacks()
        write_json(self.out / "media-entry.json", {
            "format": "lisp65-c2.2-v1.2.6-media-entry-v1",
            "recorded_on": date.today().isoformat(),
            "status": "passed-bound-product-medium-autoboot",
            "entry": config["canonical_entry"],
            "package_medium":
                self.deployment["candidate"]["package_medium"],
            "package_readback": bind(
                self.out / "package-readback.d81"),
            "preboot_C2J": bind(
                zero_readback, 0x5C640),
            "screen": bind(boot),
            "target_readbacks": target_readbacks,
            "product_bytes_changed": 0,
        })

    def media_target_readbacks(self) -> list[dict[str, Any]]:
        """Use the exact post-boot target set proven by fresh G6."""
        manifest = load(
            ROOT / self.config["candidate"]["manifest"])
        targets = (
            ("c2-bank2-static-code-plane", "bank2-code", 0x00020000),
            ("c2-session-family-region-0", "bank3-session", 0x00030000),
            ("c2-session-family-region-0", "attic-session", 0x08000000),
            ("c2-product-shelf", "attic-shelf", 0x08100000),
            ("c2-boot-family", "attic-boot", 0x08200000),
            ("c2-session-family-region-1", "attic-region1", 0x08300000),
            ("c2-kernal-window", "attic-window", 0x087FE000),
        )
        evidence: list[dict[str, Any]] = []
        for role, name, address in targets:
            row = artifact_by_role(manifest, role)
            source = ROOT / row["path"]
            captured = self.out / f"media-readback-{name}.bin"
            self.readback(address, row["bytes"], captured)
            require(
                source.read_bytes() == captured.read_bytes(),
                f"product-medium target drift: {name}",
            )
            evidence.append({
                "role": role,
                "target": name,
                "address": f"0x{address:08x}",
                "source": bind(source),
                "readback": bind(captured, address),
                "comparison": "byteidentical",
            })
        c2j = self.out / "media-readback-c2j.bin"
        self.readback(0x5C640, 64, c2j)
        require(c2j.read_bytes() == bytes(64), "media boot C2J is not CLEAR")
        evidence.append({
            "role": "C2J",
            "target": "journal",
            "address": "0x0005c640",
            "readback": bind(c2j, 0x5C640),
            "comparison": "CLEAR",
        })
        return evidence

    def continue_media(self) -> None:
        """Continue the canonical-media boot after a harness-only target stop."""
        boot = self.poll_text(
            "media-autoboot-resume", "lisp65>", 30)
        require(
            self.config["candidate"]["expected_banner"]
            in boot.read_text(errors="replace"),
            "continued media boot reached an unbound REPL",
        )
        target_readbacks = self.media_target_readbacks()
        write_json(self.out / "media-entry.json", {
            "format": "lisp65-c2.2-v1.2.6-media-entry-v1",
            "recorded_on": date.today().isoformat(),
            "status": "passed-bound-product-medium-autoboot",
            "entry": load(CONFIG)["canonical_entry"],
            "package_medium":
                self.deployment["candidate"]["package_medium"],
            "package_readback": bind(
                self.out / "package-readback.d81"),
            "screen": bind(boot),
            "target_readbacks": target_readbacks,
            "product_bytes_changed": 0,
        })

    @staticmethod
    def delta(before: int, after: int) -> int:
        return (after - before) & 0xFFFF

    def send_keys(self, payload: str) -> None:
        self.m65("-t", payload)

    def send_chunks(self, payload: str, width: int) -> None:
        for offset in range(0, len(payload), width):
            self.send_keys(payload[offset:offset + width])
            time.sleep(0.15)

    def abort_editor(self, prefix: str) -> None:
        self.send_keys("~C")
        self.poll_text(prefix, "*** stopped (run/stop)", 30)
        self.poll_text(f"{prefix}-prompt", "lisp65>", 30)

    def launch_editor(self, prefix: str, form: str) -> None:
        result = BASE.run(
            [
                str(HARNESS), "--verified-input",
                "--allow-editor-status-tail", "--no-readback",
                "--form", form,
            ],
            timeout=BASE.TIMEOUT,
            env={
                **os.environ,
                "OUT_DIR": str(self.out),
                "PREFIX": f"{prefix}-input",
                "TIMEOUT_SEC": str(BASE.TIMEOUT),
            },
        )
        (self.out / f"{prefix}-input.log").write_text(
            result.stdout, encoding="utf-8")
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            image, text = self.capture_screen(prefix)
            SCREEN.check_fail_closed_frame(image)
            content = text.read_text(errors="replace")
            if "lisp65>" not in content and "*** " not in content:
                return
            time.sleep(1)
        raise SessionError(f"{prefix}: editor did not own the screen")

    def run_form(
        self, prefix: str, form: str, expected: str | None,
        *, poll: int = BASE.EXPECT_POLL,
    ) -> Path:
        """Run after editor exit while accepting only its strict status row."""
        result = BASE.run(
            [
                str(HARNESS), "--verified-input",
                "--allow-editor-status-tail", "--no-readback",
                "--form", form,
            ],
            timeout=BASE.TIMEOUT,
            env={
                **os.environ,
                "OUT_DIR": str(self.out),
                "PREFIX": f"{prefix}-input",
                "TIMEOUT_SEC": str(BASE.TIMEOUT),
            },
        )
        (self.out / f"{prefix}-input.log").write_text(
            result.stdout, encoding="utf-8")
        for _ in range(poll):
            _png, text = self.capture_screen(prefix)
            try:
                SCREEN.check_latest_result(
                    text,
                    form,
                    expected,
                    allow_editor_status_tail=True,
                )
                return text
            except SCREEN.CheckError:
                time.sleep(1)
        raise BASE.SoakError(
            f"no exact result for {prefix}: {form}")

    def timed_keys(
        self, prefix: str, payload: str, keys: int,
    ) -> dict[str, Any]:
        before = self.frame(f"{prefix}-before")
        start_ns = time.time_ns()
        self.send_keys(payload)
        end_ns = time.time_ns()
        after = self.frame(f"{prefix}-after")
        frames = self.delta(before, after)
        return {
            "keys": keys,
            "frames": frames,
            "frames_per_key": frames / keys,
            "host_transport_milliseconds": (end_ns - start_ns) / 1_000_000,
            "before": before,
            "after": after,
        }

    def wait_editor_lines(
        self, prefix: str, expected: list[str], timeout: int = 120,
    ) -> Path:
        """Wait until the editor has visibly consumed the submitted keys."""
        deadline = time.monotonic() + timeout
        attempt = 0
        last: Path | None = None
        while time.monotonic() < deadline:
            attempt += 1
            image, text = self.capture_screen(
                f"{prefix}-completion-{attempt}")
            SCREEN.check_fail_closed_frame(image)
            rows = [
                SCREEN._screen_content(line)  # type: ignore[attr-defined]
                for line in text.read_text(errors="replace").splitlines()
            ]
            body = rows[1:-1] if len(rows) >= 2 else rows
            if (
                len(body) >= len(expected)
                and all(
                    body[index].startswith(value)
                    for index, value in enumerate(expected)
                )
            ):
                return text
            last = text
            time.sleep(1)
        raise BASE.SoakError(
            f"{prefix}: editor did not visibly consume expected input; "
            f"last={last}")

    def wait_editor_line_number(
        self, prefix: str, buffer_name: str, line_number: int,
        timeout: int = 120,
    ) -> Path:
        """Wait for the editor status row to acknowledge one RETURN."""
        deadline = time.monotonic() + timeout
        attempt = 0
        last: Path | None = None
        pattern = re.compile(
            rf"(?m)^\s*-- {re.escape(buffer_name)} \* "
            rf"L{line_number} -- [0-9]+/[0-9]+\s*$"
        )
        while time.monotonic() < deadline:
            attempt += 1
            image, text = self.capture_screen(
                f"{prefix}-completion-{attempt}")
            SCREEN.check_fail_closed_frame(image)
            if pattern.search(text.read_text(errors="replace")):
                return text
            last = text
            time.sleep(1)
        raise BASE.SoakError(
            f"{prefix}: editor did not reach line {line_number}; last={last}")

    def send_returns_until(
        self, prefix: str, buffer_name: str, count: int,
        initial_line: int = 1,
    ) -> Path:
        """Submit RETURN only after the previous one is visibly complete."""
        completion: Path | None = None
        for offset in range(count):
            target = initial_line + offset + 1
            self.send_keys("~M")
            completion = self.wait_editor_line_number(
                f"{prefix}-return-{offset + 1}",
                buffer_name,
                target,
            )
        require(completion is not None, f"{prefix}: no RETURN submitted")
        return completion

    def timed_return_until(
        self, prefix: str, buffer_name: str, target_line: int,
    ) -> dict[str, Any]:
        before = self.frame(f"{prefix}-before")
        start_ns = time.time_ns()
        self.send_keys("~M")
        completion = self.wait_editor_line_number(
            prefix, buffer_name, target_line)
        end_ns = time.time_ns()
        after = self.frame(f"{prefix}-after")
        frames = self.delta(before, after)
        return {
            "keys": 1,
            "frames": frames,
            "frames_per_key": frames,
            "host_transport_milliseconds": (end_ns - start_ns) / 1_000_000,
            "before": before,
            "after": after,
            "completion_screen": bind(completion),
            "completion_boundary":
                "target editor line visible before frame-after capture",
        }

    def timed_keys_until(
        self, prefix: str, payload: str, keys: int,
        expected_lines: list[str],
    ) -> dict[str, Any]:
        before = self.frame(f"{prefix}-before")
        start_ns = time.time_ns()
        self.send_keys(payload)
        completion = self.wait_editor_lines(prefix, expected_lines)
        end_ns = time.time_ns()
        after = self.frame(f"{prefix}-after")
        frames = self.delta(before, after)
        return {
            "keys": keys,
            "frames": frames,
            "frames_per_key": frames / keys,
            "host_transport_milliseconds": (end_ns - start_ns) / 1_000_000,
            "before": before,
            "after": after,
            "completion_screen": bind(completion),
            "completion_boundary":
                "expected editor rows visible before frame-after capture",
        }

    def send_linear_batches_until(
        self, prefix: str, payload: str, initial: str,
        width: int,
    ) -> Path:
        """Never submit more than the contracted typed-queue batch."""
        cumulative = initial
        completion: Path | None = None
        for offset in range(0, len(payload), width):
            chunk = payload[offset:offset + width]
            self.send_keys(chunk)
            cumulative += chunk
            completion = self.wait_editor_lines(
                f"{prefix}-batch-{offset // width + 1}",
                [cumulative],
            )
        require(completion is not None, f"{prefix}: empty batched payload")
        return completion

    def timed_linear_batches_until(
        self, prefix: str, payload: str, keys: int, width: int,
    ) -> dict[str, Any]:
        before = self.frame(f"{prefix}-before")
        start_ns = time.time_ns()
        completion = self.send_linear_batches_until(
            prefix, payload, "", width)
        end_ns = time.time_ns()
        after = self.frame(f"{prefix}-after")
        frames = self.delta(before, after)
        return {
            "keys": keys,
            "batches": (keys + width - 1) // width,
            "maximum_batch_keys": width,
            "frames": frames,
            "frames_per_key": frames / keys,
            "host_transport_milliseconds": (end_ns - start_ns) / 1_000_000,
            "before": before,
            "after": after,
            "completion_screen": bind(completion),
            "completion_boundary":
                "each contracted queue batch visibly consumed before next",
        }

    def run_timed_form(self, prefix: str, form: str) -> dict[str, Any]:
        result = BASE.run(
            [
                str(HARNESS), "--verified-input",
                "--allow-editor-status-tail", "--no-readback",
                "--form", form,
            ],
            timeout=BASE.TIMEOUT,
            env={
                **os.environ,
                "OUT_DIR": str(self.out),
                "PREFIX": f"{prefix}-input",
                "TIMEOUT_SEC": str(BASE.TIMEOUT),
            },
        )
        (self.out / f"{prefix}-input.log").write_text(
            result.stdout, encoding="utf-8")
        text: Path | None = None
        frames: int | None = None
        for _ in range(BASE.EXPECT_POLL):
            image, candidate = self.capture_screen(prefix)
            SCREEN.check_fail_closed_frame(image)
            content = candidate.read_text(errors="replace")
            form_at = content.rfind(form)
            tail = content[form_at + len(form):] if form_at >= 0 else ""
            matches = re.findall(
                r"(?m)^\s*(\d+)(?:\s+t)?\s*$", tail)
            if matches and "lisp65>" in tail:
                text = candidate
                frames = int(matches[-1])
                break
            time.sleep(1)
        require(
            text is not None and frames is not None,
            f"{prefix}: (time) frame/result pair absent",
        )
        return {
            "form": form,
            "frames": frames,
            "screen_text": bind(text),
        }

    def continued_timed_form(self, prefix: str, form: str) -> dict[str, Any]:
        """Bind a completed `(time ...)` row after a checker-only stop."""
        text = self.out / f"{prefix}.txt"
        require(text.is_file(), f"{prefix}: completed screen absent")
        content = text.read_text(errors="replace")
        form_at = content.rfind(form)
        command_screen: Path | None = None
        if form_at >= 0:
            tail = content[form_at + len(form):]
        else:
            command_screens = [
                path
                for path in sorted(
                    self.out.glob(f"{prefix}-input-input-attempt-*.txt")
                )
                if form in path.read_text(errors="replace")
            ]
            require(
                command_screens,
                f"{prefix}: completed timed form echo absent",
            )
            command_screen = command_screens[-1]
            tail = content
        matches = re.findall(
            r"(?m)^\s*(\d+)(?:\s+t)?\s*$", tail)
        require(
            matches and "lisp65>" in tail,
            f"{prefix}: completed frame/result pair absent",
        )
        result = {
            "form": form,
            "frames": int(matches[-1]),
            "screen_text": bind(text),
            "continuation":
                "bound after checker rejected combined frame/result row",
        }
        if command_screen is not None:
            result["command_screen"] = bind(command_screen)
        return result

    def continued_timed_form_in_followup(
        self, prefix: str, form: str, followup_prefix: str,
    ) -> dict[str, Any]:
        """Bind a result first visible in the immediately following screen."""
        command = self.out / f"{prefix}.txt"
        followup = self.out / f"{followup_prefix}.txt"
        require(
            command.is_file() and followup.is_file(),
            f"{prefix}: command/followup evidence absent",
        )
        require(
            form in command.read_text(errors="replace"),
            f"{prefix}: timed form echo absent",
        )
        content = followup.read_text(errors="replace")
        matches = re.findall(
            r"(?m)^\s*(\d+)\s+t\s*$", content)
        require(matches, f"{prefix}: followup frame/result pair absent")
        return {
            "form": form,
            "frames": int(matches[-1]),
            "screen_text": bind(followup),
            "command_screen": bind(command),
            "continuation":
                "result first visible in immediately following bound screen",
        }

    def state_capture(self, prefix: str) -> dict[str, Any]:
        truth = ElfTruth.read(
            check_binding(self.deployment["candidate"]["ELF"]),
            llvm_readobj=READOBJ,
        )
        addresses = {
            "trace":
                truth.symbol("lisp65_c2_phase_scratch").value + 302,
            "c2d-header": 0x50000,
            "c2j": 0x5C640,
            "phase-owner": truth.symbol("c2_phase_owner").value,
            "gc-runs": truth.symbol("gc_runs").value,
            "mem-oom": truth.symbol("mem_oom").value,
            "gc-badobj": truth.symbol("gc_badobj").value,
        }
        widths = {
            "trace": 2, "c2d-header": 48, "c2j": 64,
            "phase-owner": 1, "gc-runs": 2, "mem-oom": 1,
            "gc-badobj": 2,
        }
        result: dict[str, Any] = {}
        for name, address in addresses.items():
            path = self.out / f"{prefix}-{name}.bin"
            self.readback(address, widths[name], path)
            result[name] = bind(path, address)
        c2d = (
            self.out / f"{prefix}-c2d-header.bin").read_bytes()
        c2j = (self.out / f"{prefix}-c2j.bin").read_bytes()
        owner = (
            self.out / f"{prefix}-phase-owner.bin").read_bytes()
        oom = (self.out / f"{prefix}-mem-oom.bin").read_bytes()
        require(c2d[:4] == b"C2D\0", f"{prefix}: C2D header drift")
        require(c2j == bytes(64), f"{prefix}: C2J is not CLEAR")
        require(owner == b"\0", f"{prefix}: phase owner is not NONE")
        require(oom == b"\0", f"{prefix}: mem_oom is set")
        result["C2J"] = "CLEAR"
        result["phase_owner"] = "NONE"
        result["mem_oom"] = 0
        return result

    def execute(self, *, resume_at_bound_REPL: bool = False) -> None:
        config = load(CONFIG)
        d1 = config["D1"]
        try:
            if resume_at_bound_REPL:
                boot = self.poll_text(
                    "physical-run-resume", "lisp65>", 30)
                require(
                    self.config["candidate"]["expected_banner"]
                    in boot.read_text(errors="replace"),
                    "physical RUN reached an unbound REPL",
                )
            else:
                self.fresh_start()
                self.readback(
                    0x0FFD3632, 4, self.out / "device-core-id.bin")
                self.ftp_package()
                self.deploy()
            baseline = self.state_capture("baseline")

            self.launch_editor("d1-scratch-editor", "(edit)")
            plain_burst = self.timed_keys(
                "d1-plain-burst",
                d1["plain_burst_character"] * d1["plain_burst_keys"],
                d1["plain_burst_keys"],
            )
            self.send_chunks(
                d1["plain_burst_character"] * d1["plain_fill_keys"],
                d1["transport_chunk_keys"],
            )
            plain = self.timed_keys(
                "d1-plain-key", d1["plain_measured_character"], 1)
            wrap = self.timed_keys(
                "d1-wrap-key", d1["wrap_measured_character"], 1)
            self.capture_screen("d1-scratch-after")
            self.abort_editor("d1-scratch-abort")

            self.run_form(
                "d1-query-helper",
                "(defun %ib(n a)(if a(if(string= n(caar a))(cdar a)(%ib n(cdr a)))nil))",
                "%ib",
            )
            self.run_form(
                "d1-query-scratch",
                "(progn(setq b(%ib\"scratch\"(symbol-value(quote ide-buffers))))t)",
                "t")
            self.run_form(
                "d1-query-scratch-head",
                "(list(ide-line-count b)(string-length(ide-line-at b 0)))",
                "(2 79)",
            )
            self.run_form(
                "d1-query-scratch-tail",
                "(string-length(ide-line-at b 1))", "1")

            self.launch_editor(
                "d1-scroll-editor", "(ide\"scroll\")")
            self.send_chunks(
                "~M" * d1["scroll_prep_returns"],
                d1["transport_chunk_keys"] * 2,
            )
            scroll = self.timed_keys("d1-scroll-key", "~M", 1)
            self.capture_screen("d1-scroll-after")
            self.abort_editor("d1-scroll-abort")
            self.run_form(
                "d1-query-scroll",
                "(progn(setq b(%ib\"scroll\"(symbol-value(quote ide-buffers))))t)",
                "t")
            self.run_form(
                "d1-query-scroll-lines", "(ide-line-count b)", "50")

            for index, row in enumerate(
                config["D2"]["wrap_setup_forms"], 1
            ):
                self.run_form(
                    f"d2-wrap-setup-{index}",
                    row["form"], row["expected"])
            time_wrap = self.run_timed_form(
                "d2-time-wrap", config["D2"]["wrap_form"])
            for index, row in enumerate(
                config["D2"]["scroll_setup_forms"], 1
            ):
                self.run_form(
                    f"d2-scroll-setup-{index}",
                    row["form"], row["expected"])
            time_scroll = self.run_timed_form(
                "d2-time-scroll", config["D2"]["scroll_form"])

            smokes: list[dict[str, Any]] = []
            for row in config["D3"]["smoke_rows"]:
                text = self.run_form(
                    f"d3-{row['id']}", row["form"], row["expected"])
                smokes.append({
                    **row,
                    "screen_text": bind(text),
                    "status": "passed-exact-target-result",
                })
            final = self.state_capture("final")
            self.capture_screen("final-screen")

            gc_before = struct.unpack(
                "<H",
                (self.out / "baseline-gc-runs.bin").read_bytes(),
            )[0]
            gc_after = struct.unpack(
                "<H",
                (self.out / "final-gc-runs.bin").read_bytes(),
            )[0]
            bad_before = (
                self.out / "baseline-gc-badobj.bin").read_bytes()
            bad_after = (
                self.out / "final-gc-badobj.bin").read_bytes()
            require(
                bad_before == bad_after,
                "gc_badobj changed during editor session",
            )

            require(
                plain_burst["frames_per_key"]
                    <= d1["maximum_average_frames_per_key"],
                "plain burst reached one collection envelope per key",
            )
            for name, row in (
                ("plain", plain), ("wrap", wrap), ("scroll", scroll)
            ):
                require(
                    row["frames"] <= d1["maximum_single_key_frames"],
                    f"{name} key contained a multi-collection burst",
                )
            require(
                time_wrap["frames"]
                    <= config["D2"]["maximum_frames_per_spot_check"]
                and time_scroll["frames"]
                    <= config["D2"]["maximum_frames_per_spot_check"],
                "(time) wrap/scroll spot check exceeded frame ceiling",
            )

            dropped_characters = (
                80 - (
                    d1["expected_scratch_first_line_characters"]
                    + d1["expected_scratch_second_line_characters"]))
            dropped_returns = (
                49 - (d1["expected_scroll_lines"] - 1))
            require(
                dropped_characters
                    == d1["expected_dropped_characters"]
                and dropped_returns == d1["expected_dropped_returns"],
                "input accounting contract drift",
            )

            value = {
                "format":
                    "lisp65-c2.2-v1.2.6-editor-hardware-v1",
                "recorded_on": date.today().isoformat(),
                "status":
                    "passed-editor-usable-zero-dropped-input-Link83",
                "candidate": {
                    "release": "v1.2.6",
                    "link": 83,
                    "product": self.deployment["candidate"]["product"],
                    "ELF": self.deployment["candidate"]["ELF"],
                    "package_medium":
                        self.deployment["candidate"]["package_medium"],
                    "package_readback": bind(
                        self.out / "package-readback.d81"),
                    "artifact_set_sha256":
                        self.preparation["candidate"][
                            "artifact_set_sha256"],
                },
                "D1_typing_queue_measurement": {
                    "plain_burst": plain_burst,
                    "plain_single": plain,
                    "wrap_single": wrap,
                    "scroll_single": scroll,
                    "printable_keys_sent": 80,
                    "printable_keys_observed": 80,
                    "return_keys_sent": 49,
                    "return_keys_observed": 49,
                    "dropped_characters": dropped_characters,
                    "dropped_returns": dropped_returns,
                    "exit": "RUN/STOP-to-live-REPL-after-persist",
                    "screen_scratch": bind(
                        self.out / "d1-scratch-after.txt"),
                    "screen_scroll": bind(
                        self.out / "d1-scroll-after.txt"),
                },
                "D2_time_spot_checks": {
                    "wrap": time_wrap,
                    "scroll": time_scroll,
                },
                "D3_trailing_lines": {
                    "smokes": smokes,
                    "baseline": baseline,
                    "final": final,
                    "gc_runs_before": gc_before,
                    "gc_runs_after": gc_after,
                    "gc_runs_delta": (gc_after - gc_before) & 0xFFFF,
                    "gc_badobj_unchanged": True,
                    "C2J": "CLEAR",
                    "phase_owner": "NONE",
                    "mem_oom": 0,
                },
                "decision_table": {
                    "host_old_serial_cells_per_key": 169.2625,
                    "host_new_serial_cells_per_key": 38.275,
                    "host_old_derived_collections_per_key": 0.882,
                    "host_new_derived_collections_per_key": 0.199,
                    "target_plain_burst_frames_per_key":
                        plain_burst["frames_per_key"],
                    "target_plain_single_frames": plain["frames"],
                    "target_wrap_single_frames": wrap["frames"],
                    "target_scroll_single_frames": scroll["frames"],
                    "target_time_wrap_frames": time_wrap["frames"],
                    "target_time_scroll_frames": time_scroll["frames"],
                    "dropped_input_total":
                        dropped_characters + dropped_returns,
                    "owner_report_not_usable":
                        "closed-by-zero-loss-and-bounded-key-latency",
                },
                "execution_accounting": {
                    "physical_device_sessions": 1,
                    "cold_resets": 1,
                    "product_links": 1,
                    "product_bytes_changed_by_session": 0,
                    "promotable_candidates": 0,
                },
                "authority": {
                    "config": bind(CONFIG),
                    "preparation": bind(PREPARATION),
                    "allocation_gate": bind(ALLOCATION),
                    "WPLTO": bind(WPLTO),
                    "preload_harness_first_red": bind(FIRST_RED),
                    "zero_C2J_harness_first_red": bind(BOOT_FIRST_RED),
                    "memsave_exit_harness_first_red":
                        bind(MONITOR_FIRST_RED),
                    "virtual_RUN_harness_first_red":
                        bind(START_FIRST_RED),
                    "monitor_resume_harness_first_red":
                        bind(RESUME_FIRST_RED),
                    "driver": bind(DRIVER),
                },
                "harness": {
                    "exitless_readbacks": self.exitless_readbacks,
                    "exitless_readback_count":
                        len(self.exitless_readbacks),
                    "acceptance_rule":
                        "fresh exact-width file plus caller authority compare",
                    "start_transport":
                        "canonical product-D81 AUTOBOOT only; no concurrent "
                        "USB product load or direct entry",
                },
                "claim_limit": config["policy"]["claim_limit"],
            }
            write_json(RECEIPT, value)
        except Exception as error:
            try:
                self.capture_screen("session-anomaly")
            except Exception:
                pass
            if not isinstance(error, subprocess.TimeoutExpired):
                try:
                    self.state_capture("session-anomaly")
                except Exception:
                    pass
            write_json(self.out / "first-anomaly.json", {
                "format":
                    "lisp65-c2.2-v1.2.6-editor-hardware-anomaly-v1",
                "recorded_on": date.today().isoformat(),
                "status": "stopped-on-first-terminal-anomaly",
                "detail": str(error),
                "preparation": bind(PREPARATION),
                "claim_limit": config["policy"]["claim_limit"],
            })
            raise

    def continued_metric(self, prefix: str, keys: int) -> dict[str, Any]:
        """Recover a completed timed row after a harness-only screen stop."""
        before_path = self.out / f"{prefix}-before-frame.bin"
        after_path = self.out / f"{prefix}-after-frame.bin"
        require(
            before_path.is_file() and after_path.is_file(),
            f"continued metric capture absent: {prefix}",
        )
        before = struct.unpack("<H", before_path.read_bytes())[0]
        after = struct.unpack("<H", after_path.read_bytes())[0]
        frames = self.delta(before, after)
        return {
            "keys": keys,
            "frames": frames,
            "frames_per_key": frames / keys,
            "host_transport_milliseconds": None,
            "before": before,
            "after": after,
            "continuation": {
                "classification":
                    "recovered-from-pre/post-frame-captures-after-"
                    "harness-only-screen-tail-stop",
                "before_capture": bind(before_path, 0xFF83),
                "after_capture": bind(after_path, 0xFF83),
            },
        }

    def continued_state(self, prefix: str) -> dict[str, Any]:
        """Bind and re-check a state capture made before a harness-only stop."""
        truth = ElfTruth.read(
            check_binding(self.deployment["candidate"]["ELF"]),
            llvm_readobj=READOBJ,
        )
        rows = {
            "trace": (truth.symbol("lisp65_c2_phase_scratch").value + 302, 2),
            "c2d-header": (0x50000, 48),
            "c2j": (0x5C640, 64),
            "phase-owner": (truth.symbol("c2_phase_owner").value, 1),
            "gc-runs": (truth.symbol("gc_runs").value, 2),
            "mem-oom": (truth.symbol("mem_oom").value, 1),
            "gc-badobj": (truth.symbol("gc_badobj").value, 2),
        }
        result: dict[str, Any] = {}
        for name, (address, count) in rows.items():
            path = self.out / f"{prefix}-{name}.bin"
            require(
                path.is_file() and path.stat().st_size == count,
                f"continued state capture absent or truncated: {path}",
            )
            result[name] = bind(path, address)
        require(
            (self.out / f"{prefix}-c2d-header.bin").read_bytes()[:4]
                == b"C2D\0",
            f"{prefix}: continued C2D header drift",
        )
        require(
            (self.out / f"{prefix}-c2j.bin").read_bytes() == bytes(64),
            f"{prefix}: continued C2J is not CLEAR",
        )
        require(
            (self.out / f"{prefix}-phase-owner.bin").read_bytes() == b"\0",
            f"{prefix}: continued phase owner is not NONE",
        )
        require(
            (self.out / f"{prefix}-mem-oom.bin").read_bytes() == b"\0",
            f"{prefix}: continued mem_oom is set",
        )
        result["C2J"] = "CLEAR"
        result["phase_owner"] = "NONE"
        result["mem_oom"] = 0
        return result

    def continue_after_scratch(self) -> None:
        """Resume after D1 scratch completed and the strict screen check stopped."""
        config = load(CONFIG)
        d1 = config["D1"]
        require(not RECEIPT.exists(), "hardware receipt already exists")
        _entry_image, entry_screen = self.capture_screen(
            "d1-continuation-entry")
        entry_text = entry_screen.read_text(errors="replace")
        in_editor = bool(re.search(
            r"(?m)^\s*-- [A-Za-z0-9._-]+(?: \*?)? L[0-9]+ --",
            entry_text,
        ))
        if not in_editor:
            self.poll_text("d1-continuation-start", "lisp65>", 30)
        helper = self.out / "d1-query-helper-resume.txt"
        require(helper.is_file(), "continued %ib result evidence absent")
        SCREEN.check_latest_result(
            helper,
            "(defun %ib(n)(%ide-buffers-find n(symbol-value(quote ide-buffers))))",
            "%ib",
            allow_editor_status_tail=True,
        )
        corrected_helper = self.out / "d1-query-helper-corrected.txt"
        if corrected_helper.is_file():
            SCREEN.check_latest_result(
                corrected_helper,
                "(defun %ib(n a)(if a(if(string= n(caar a))(cdar a)(%ib n(cdr a)))nil))",
                "%ib",
                allow_editor_status_tail=True,
            )
        else:
            self.run_form(
                "d1-query-helper-corrected",
                "(defun %ib(n a)(if a(if(string= n(caar a))(cdar a)(%ib n(cdr a)))nil))",
                "%ib",
            )

        baseline = self.continued_state("baseline")
        if in_editor and not re.search(
            r"(?m)^\s*-- measure3(?: \*?)? L[0-9]+ --", entry_text,
        ):
            self.abort_editor("d1-overqueue-abort")
            in_editor = False
        if not in_editor:
            self.launch_editor("d1-measure3-editor", "(ide\"measure3\")")
        a40 = d1["plain_burst_character"] * d1["plain_burst_keys"]
        a78 = a40 + (
            d1["plain_burst_character"] * d1["plain_fill_keys"])
        plain_burst = self.timed_linear_batches_until(
            "d1-measure3-plain-burst",
            a40,
            d1["plain_burst_keys"],
            1,
        )
        self.send_linear_batches_until(
            "d1-measure3-fill",
            d1["plain_burst_character"] * d1["plain_fill_keys"],
            a40,
            1,
        )
        plain_line = a78 + d1["plain_measured_character"]
        plain = self.timed_keys_until(
            "d1-measure3-plain-key",
            d1["plain_measured_character"],
            1,
            [plain_line],
        )
        wrap = self.timed_keys_until(
            "d1-measure3-wrap-key",
            d1["wrap_measured_character"],
            1,
            [plain_line, d1["wrap_measured_character"]],
        )
        self.capture_screen("d1-measure3-after")
        self.abort_editor("d1-measure3-abort")

        self.run_form(
            "d1-query-measure3",
            "(progn(setq b(%ib\"measure3\"(symbol-value(quote ide-buffers))))t)",
            "t")
        self.run_form(
            "d1-query-measure3-head",
            "(list(ide-line-count b)(string-length(ide-line-at b 0)))",
            "(2 79)",
        )
        self.run_form(
            "d1-query-measure3-tail",
            "(string-length(ide-line-at b 1))", "1")

        self.launch_editor("d1-scroll-editor", "(ide\"scroll\")")
        self.send_returns_until(
            "d1-scroll-prep",
            "scroll",
            d1["scroll_prep_returns"],
        )
        scroll = self.timed_return_until(
            "d1-scroll-key",
            "scroll",
            d1["scroll_prep_returns"] + 2,
        )
        self.capture_screen("d1-scroll-after")
        self.abort_editor("d1-scroll-abort")
        self.run_form(
            "d1-query-scroll",
            "(progn(setq b(%ib\"scroll\"(symbol-value(quote ide-buffers))))t)",
            "t")
        self.run_form(
            "d1-query-scroll-lines", "(ide-line-count b)", "50")

        for index, row in enumerate(config["D2"]["wrap_setup_forms"], 1):
            self.run_form(
                f"d2-wrap-setup-{index}",
                row["form"], row["expected"])
        time_wrap = self.run_timed_form(
            "d2-time-wrap", config["D2"]["wrap_form"])
        for index, row in enumerate(config["D2"]["scroll_setup_forms"], 1):
            self.run_form(
                f"d2-scroll-setup-{index}",
                row["form"], row["expected"])
        time_scroll = self.run_timed_form(
            "d2-time-scroll", config["D2"]["scroll_form"])

        smokes: list[dict[str, Any]] = []
        for row in config["D3"]["smoke_rows"]:
            text = self.run_form(
                f"d3-{row['id']}", row["form"], row["expected"])
            smokes.append({
                **row,
                "screen_text": bind(text),
                "status": "passed-exact-target-result",
            })
        final = self.state_capture("final")
        self.capture_screen("final-screen")

        gc_before = struct.unpack(
            "<H", (self.out / "baseline-gc-runs.bin").read_bytes())[0]
        gc_after = struct.unpack(
            "<H", (self.out / "final-gc-runs.bin").read_bytes())[0]
        bad_before = (self.out / "baseline-gc-badobj.bin").read_bytes()
        bad_after = (self.out / "final-gc-badobj.bin").read_bytes()
        require(
            bad_before == bad_after,
            "gc_badobj changed during continued editor session",
        )

        require(
            plain_burst["frames_per_key"]
                <= d1["maximum_average_frames_per_key"],
            "plain burst reached one collection envelope per key",
        )
        for name, row in (
            ("plain", plain), ("wrap", wrap), ("scroll", scroll)
        ):
            require(
                row["frames"] <= d1["maximum_single_key_frames"],
                f"{name} key contained a multi-collection burst",
            )
        require(
            time_wrap["frames"]
                <= config["D2"]["maximum_frames_per_spot_check"]
            and time_scroll["frames"]
                <= config["D2"]["maximum_frames_per_spot_check"],
            "(time) wrap/scroll spot check exceeded frame ceiling",
        )

        dropped_characters = (
            80 - (
                d1["expected_scratch_first_line_characters"]
                + d1["expected_scratch_second_line_characters"]))
        dropped_returns = 49 - (d1["expected_scroll_lines"] - 1)
        require(
            dropped_characters == d1["expected_dropped_characters"]
            and dropped_returns == d1["expected_dropped_returns"],
            "input accounting contract drift",
        )

        value = {
            "format": "lisp65-c2.2-v1.2.6-editor-hardware-v1",
            "recorded_on": date.today().isoformat(),
            "status": "passed-editor-usable-zero-dropped-input-Link83",
            "candidate": {
                "release": "v1.2.6",
                "link": 83,
                "product": self.deployment["candidate"]["product"],
                "ELF": self.deployment["candidate"]["ELF"],
                "package_medium":
                    self.deployment["candidate"]["package_medium"],
                "package_readback": bind(self.out / "package-readback.d81"),
                "artifact_set_sha256":
                    self.preparation["candidate"]["artifact_set_sha256"],
            },
            "D1_typing_queue_measurement": {
                "plain_burst": plain_burst,
                "plain_single": plain,
                "wrap_single": wrap,
                "scroll_single": scroll,
                "printable_keys_sent": 80,
                "printable_keys_observed": 80,
                "return_keys_sent": 49,
                "return_keys_observed": 49,
                "dropped_characters": dropped_characters,
                "dropped_returns": dropped_returns,
                "exit": "RUN/STOP-to-live-REPL-after-persist",
                "screen_scratch": bind(self.out / "d1-measure3-after.txt"),
                "screen_scroll": bind(self.out / "d1-scroll-after.txt"),
                "superseded_harness_row": {
                    "classification":
                        "two harness errors: abort-before-visible-completion "
                        "preserved 34 characters; 40-key single submission "
                        "exceeded the contracted ten-key queue batch and "
                        "delivered exactly 15 keys; a nominal ten-key JTAG "
                        "submission delivered only four and proved that "
                        "product queue capacity is not transport capacity",
                    "screen": bind(self.out / "d1-scratch-after.txt"),
                    "result": bind(self.out / "d1-query-scratch-head.txt"),
                    "overqueue_screen": bind(
                        self.out
                        / "d1-measure-plain-burst-completion-93.txt"),
                    "ten_key_transport_screen": bind(
                        self.out
                        / "d1-measure2-plain-burst-batch-1-completion-93.txt"),
                    "product_claim": "none",
                },
            },
            "D2_time_spot_checks": {
                "wrap": time_wrap,
                "scroll": time_scroll,
            },
            "D3_trailing_lines": {
                "smokes": smokes,
                "baseline": baseline,
                "final": final,
                "gc_runs_before": gc_before,
                "gc_runs_after": gc_after,
                "gc_runs_delta": (gc_after - gc_before) & 0xFFFF,
                "gc_badobj_unchanged": True,
                "C2J": "CLEAR",
                "phase_owner": "NONE",
                "mem_oom": 0,
            },
            "decision_table": {
                "host_old_serial_cells_per_key": 169.2625,
                "host_new_serial_cells_per_key": 38.275,
                "host_old_derived_collections_per_key": 0.882,
                "host_new_derived_collections_per_key": 0.199,
                "target_plain_burst_frames_per_key":
                    plain_burst["frames_per_key"],
                "target_plain_single_frames": plain["frames"],
                "target_wrap_single_frames": wrap["frames"],
                "target_scroll_single_frames": scroll["frames"],
                "target_time_wrap_frames": time_wrap["frames"],
                "target_time_scroll_frames": time_scroll["frames"],
                "dropped_input_total":
                    dropped_characters + dropped_returns,
                "owner_report_not_usable":
                    "closed-by-zero-loss-and-bounded-key-latency",
            },
            "execution_accounting": {
                "physical_device_sessions": 1,
                "cold_resets": 1,
                "product_links": 1,
                "product_bytes_changed_by_session": 0,
                "promotable_candidates": 0,
                "continued_after_harness_only_screen_tail_stop": True,
            },
            "authority": {
                "config": bind(CONFIG),
                "preparation": bind(PREPARATION),
                "allocation_gate": bind(ALLOCATION),
                "WPLTO": bind(WPLTO),
                "preload_harness_first_red": bind(FIRST_RED),
                "zero_C2J_harness_first_red": bind(BOOT_FIRST_RED),
                "memsave_exit_harness_first_red": bind(MONITOR_FIRST_RED),
                "virtual_RUN_harness_first_red": bind(START_FIRST_RED),
                "monitor_resume_harness_first_red": bind(RESUME_FIRST_RED),
                "driver": bind(DRIVER),
            },
            "harness": {
                "exitless_readbacks": self.exitless_readbacks,
                "exitless_readback_count": len(self.exitless_readbacks),
                "acceptance_rule":
                    "fresh exact-width file plus caller authority compare",
                "start_transport":
                    "canonical product-D81 AUTOBOOT only; no concurrent "
                    "USB product load or direct entry",
                "screen_tail_rule":
                    "strict opt-in editor status row only; arbitrary tail "
                    "remains malformed",
            },
            "claim_limit": config["policy"]["claim_limit"],
        }
        write_json(RECEIPT, value)

    def continue_independent_after_d1_red(self) -> None:
        """Run D2/D3 after D1 stalled and RUN/STOP returned to a live REPL."""
        config = load(CONFIG)
        require(not RECEIPT.exists(), "passing hardware receipt already exists")
        prompt = self.poll_text(
            "d1-first-red-independent-entry", "lisp65>", 30)
        require(
            "*** stopped (run/stop)" in prompt.read_text(errors="replace"),
            "D1 RUN/STOP recovery evidence absent",
        )

        self.run_form(
            "d1-first-red-query-measure3",
            "(progn(setq b(%ib\"measure3\"(symbol-value(quote ide-buffers))))t)",
            "t",
        )
        measured = self.run_form(
            "d1-first-red-query-measure3-shape",
            "(list(ide-line-count b)(string-length(ide-line-at b 0)))",
            "(1 55)",
        )
        plain_burst = self.continued_metric(
            "d1-measure3-plain-burst",
            config["D1"]["plain_burst_keys"],
        )

        for index, row in enumerate(config["D2"]["wrap_setup_forms"], 1):
            self.run_form(
                f"d2-first-red-wrap-setup-{index}",
                row["form"], row["expected"])
        time_wrap = self.run_timed_form(
            "d2-first-red-time-wrap", config["D2"]["wrap_form"])
        for index, row in enumerate(config["D2"]["scroll_setup_forms"], 1):
            self.run_form(
                f"d2-first-red-scroll-setup-{index}",
                row["form"], row["expected"])
        time_scroll = self.run_timed_form(
            "d2-first-red-time-scroll", config["D2"]["scroll_form"])

        smokes: list[dict[str, Any]] = []
        for row in config["D3"]["smoke_rows"]:
            text = self.run_form(
                f"d3-first-red-{row['id']}",
                row["form"], row["expected"])
            smokes.append({
                **row,
                "screen_text": bind(text),
                "status": "passed-exact-target-result",
            })
        final = self.state_capture("d1-first-red-final")
        final_screen = self.capture_screen("d1-first-red-final-screen")[1]

        gc_before = struct.unpack(
            "<H", (self.out / "baseline-gc-runs.bin").read_bytes())[0]
        gc_after = struct.unpack(
            "<H", (self.out / "d1-first-red-final-gc-runs.bin")
            .read_bytes())[0]
        bad_before = (self.out / "baseline-gc-badobj.bin").read_bytes()
        bad_after = (
            self.out / "d1-first-red-final-gc-badobj.bin").read_bytes()
        require(
            bad_before == bad_after,
            "gc_badobj changed after D1 First Red",
        )

        value = {
            "format":
                "lisp65-c2.2-v1.2.6-editor-hardware-first-red-v1",
            "recorded_on": date.today().isoformat(),
            "status":
                "FIRST-RED-editor-stalled-on-56th-serially-acknowledged-key",
            "candidate": {
                "release": "v1.2.6",
                "link": 83,
                "product": self.deployment["candidate"]["product"],
                "ELF": self.deployment["candidate"]["ELF"],
                "artifact_set_sha256":
                    self.preparation["candidate"]["artifact_set_sha256"],
            },
            "D1": {
                "result": "failed-usability-contract",
                "transport_protocol":
                    "one virtual key only after prior key was visible",
                "plain_burst": plain_burst,
                "accepted_before_stall": 55,
                "stalled_key_ordinal": 56,
                "unchanged_seconds": 120,
                "screen_before_abort": bind(
                    self.out
                    / "d1-measure3-fill-batch-16-completion-93.txt"),
                "screen_after_abort": bind(
                    self.out / "d1-measure3-first-red-abort.png"),
                "persisted_shape": bind(measured),
                "RUN_STOP_returned_live_REPL": True,
                "classification":
                    "product editor stall; transport-overqueue excluded",
            },
            "independent_rows": {
                "D2": {
                    "wrap": time_wrap,
                    "scroll": time_scroll,
                },
                "D3": {
                    "smokes": smokes,
                    "baseline": self.continued_state("baseline"),
                    "final": final,
                    "final_screen": bind(final_screen),
                    "gc_runs_before": gc_before,
                    "gc_runs_after": gc_after,
                    "gc_runs_delta": (gc_after - gc_before) & 0xFFFF,
                    "gc_badobj_unchanged": True,
                    "C2J": "CLEAR",
                    "phase_owner": "NONE",
                    "mem_oom": 0,
                },
            },
            "decision": {
                "release_phase_E": "closed",
                "Halt_1_required": True,
                "product_fix_authorized": False,
                "next_step":
                    "owner review of attributed D1 First Red; no retry",
            },
            "authority": {
                "config": bind(CONFIG),
                "preparation": bind(PREPARATION),
                "allocation_gate": bind(ALLOCATION),
                "WPLTO": bind(WPLTO),
                "driver": bind(DRIVER),
            },
            "claim_limit": config["policy"]["claim_limit"],
        }
        write_json(SESSION_FIRST_RED, value)

    def continue_independent_after_d2_harness_red(self) -> None:
        """Replace the unexported D2 fixture helper, then finish D2/D3."""
        config = load(CONFIG)
        require(not RECEIPT.exists(), "passing hardware receipt already exists")
        prompt = self.poll_text(
            "d2-harness-red-independent-entry", "lisp65>", 30)
        completed_wrap = (
            self.out / "d2-time-wrap-public-fixture.txt")
        if completed_wrap.is_file():
            time_wrap = self.continued_timed_form(
                "d2-time-wrap-public-fixture",
                config["D2"]["wrap_form"],
            )
        else:
            require(
                "*** undefined function: list->string"
                in prompt.read_text(errors="replace"),
                "D2 list->string harness First Red evidence absent",
            )
            replacement = (
                ("d2-wrap-public-string-1",
                 "(progn(setq s\"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\")t)",
                 "t"),
                ("d2-wrap-public-string-2",
                 "(progn(setq s(string-append s s))t)", "t"),
                ("d2-wrap-public-string-3",
                 "(progn(setq s(substring s 0 79))t)", "t"),
                ("d2-wrap-public-string-check", "(string-length s)", "79"),
                ("d2-wrap-public-buffer",
                 "(progn(setq x(ide-make-buffer\"w\"(list s)))t)", "t"),
                ("d2-wrap-public-state",
                 "(progn(setq x(ide-make-state(ide-set-point x 0 79)))t)",
                 "t"),
            )
            for prefix, form, expected in replacement:
                self.run_form(prefix, form, expected)
            time_wrap = self.run_timed_form(
                "d2-time-wrap-public-fixture",
                config["D2"]["wrap_form"])

        completed_scroll = (
            self.out / "d2-time-scroll-public-fixture.txt")
        if completed_scroll.is_file():
            try:
                time_scroll = self.continued_timed_form(
                    "d2-time-scroll-public-fixture",
                    config["D2"]["scroll_form"],
                )
            except SessionError:
                time_scroll = self.continued_timed_form_in_followup(
                    "d2-time-scroll-public-fixture",
                    config["D2"]["scroll_form"],
                    "d3-after-d1-red-fx-multiply",
                )
        else:
            for index, row in enumerate(
                config["D2"]["scroll_setup_forms"], 1
            ):
                self.run_form(
                    f"d2-scroll-setup-public-{index}",
                    row["form"], row["expected"])
            time_scroll = self.run_timed_form(
                "d2-time-scroll-public-fixture",
                config["D2"]["scroll_form"])

        smokes: list[dict[str, Any]] = []
        for row in config["D3"]["smoke_rows"]:
            prefix = f"d3-after-d1-red-{row['id']}"
            completed = self.out / f"{prefix}.txt"
            if completed.is_file():
                content = completed.read_text(errors="replace")
                if row["id"] == "time":
                    require(
                        re.search(
                            rf"(?m)^\s*\d+\s+{re.escape(row['expected'])}"
                            r"\s*$",
                            content,
                        ) is not None
                        and "lisp65>" in content,
                        "completed D3 time result drift",
                    )
                else:
                    SCREEN.check_latest_result(
                        completed,
                        row["form"],
                        row["expected"],
                        allow_editor_status_tail=True,
                    )
                text = completed
            else:
                text = self.run_form(
                    prefix, row["form"], row["expected"])
            smokes.append({
                **row,
                "screen_text": bind(text),
                "status": "passed-exact-target-result",
            })
        final = self.state_capture("d1-first-red-final")
        final_screen = self.capture_screen("d1-first-red-final-screen")[1]

        gc_before = struct.unpack(
            "<H", (self.out / "baseline-gc-runs.bin").read_bytes())[0]
        gc_after = struct.unpack(
            "<H", (self.out / "d1-first-red-final-gc-runs.bin")
            .read_bytes())[0]
        bad_before = (self.out / "baseline-gc-badobj.bin").read_bytes()
        bad_after = (
            self.out / "d1-first-red-final-gc-badobj.bin").read_bytes()
        require(
            bad_before == bad_after,
            "gc_badobj changed after D1 First Red",
        )

        plain_burst = self.continued_metric(
            "d1-measure3-plain-burst",
            config["D1"]["plain_burst_keys"],
        )
        value = {
            "format":
                "lisp65-c2.2-v1.2.6-editor-hardware-first-red-v1",
            "recorded_on": date.today().isoformat(),
            "status":
                "FIRST-RED-editor-stalled-on-56th-serially-acknowledged-key",
            "candidate": {
                "release": "v1.2.6",
                "link": 83,
                "product": self.deployment["candidate"]["product"],
                "ELF": self.deployment["candidate"]["ELF"],
                "artifact_set_sha256":
                    self.preparation["candidate"]["artifact_set_sha256"],
            },
            "D1": {
                "result": "failed-usability-contract",
                "transport_protocol":
                    "one virtual key only after prior key was visible",
                "plain_burst": plain_burst,
                "accepted_before_stall": 55,
                "stalled_key_ordinal": 56,
                "unchanged_seconds": 120,
                "screen_before_abort": bind(
                    self.out
                    / "d1-measure3-fill-batch-16-completion-93.txt"),
                "screen_after_abort": bind(
                    self.out / "d1-measure3-first-red-abort.png"),
                "persisted_shape": bind(
                    self.out / "d1-first-red-query-measure3-shape.txt"),
                "RUN_STOP_returned_live_REPL": True,
                "classification":
                    "product editor stall; transport-overqueue excluded",
            },
            "independent_rows": {
                "D2": {
                    "wrap": time_wrap,
                    "scroll": time_scroll,
                    "harness_first_red": {
                        "detail":
                            "original fixture called unexported "
                            "list->string from the REPL",
                        "screen": bind(
                            self.out
                            / "d2-first-red-wrap-setup-2.txt"),
                        "correction":
                            "public string-append/substring fixture; "
                            "zero product bytes",
                    },
                },
                "D3": {
                    "smokes": smokes,
                    "baseline": self.continued_state("baseline"),
                    "final": final,
                    "final_screen": bind(final_screen),
                    "gc_runs_before": gc_before,
                    "gc_runs_after": gc_after,
                    "gc_runs_delta": (gc_after - gc_before) & 0xFFFF,
                    "gc_badobj_unchanged": True,
                    "C2J": "CLEAR",
                    "phase_owner": "NONE",
                    "mem_oom": 0,
                },
            },
            "decision": {
                "release_phase_E": "closed",
                "Halt_1_required": True,
                "product_fix_authorized": False,
                "next_step":
                    "owner review of attributed D1 First Red; no retry",
            },
            "authority": {
                "config": bind(CONFIG),
                "preparation": bind(PREPARATION),
                "allocation_gate": bind(ALLOCATION),
                "WPLTO": bind(WPLTO),
                "driver": bind(DRIVER),
            },
            "claim_limit": config["policy"]["claim_limit"],
        }
        write_json(SESSION_FIRST_RED, value)


def verify() -> dict[str, Any]:
    value = load(RECEIPT)
    require(
        value["status"]
            == "passed-editor-usable-zero-dropped-input-Link83",
        "hardware receipt status drift",
    )
    d1 = value["D1_typing_queue_measurement"]
    table = value["decision_table"]
    require(
        d1["dropped_characters"] == 0
        and d1["dropped_returns"] == 0
        and table["dropped_input_total"] == 0,
        "hardware receipt records dropped input",
    )
    require(
        table["target_plain_burst_frames_per_key"] <= 88
        and max(
            table["target_plain_single_frames"],
            table["target_wrap_single_frames"],
            table["target_scroll_single_frames"],
            table["target_time_wrap_frames"],
            table["target_time_scroll_frames"],
        ) <= 177,
        "hardware receipt frame ceiling drift",
    )
    trailing = value["D3_trailing_lines"]
    require(
        trailing["C2J"] == "CLEAR"
        and trailing["phase_owner"] == "NONE"
        and trailing["mem_oom"] == 0
        and trailing["gc_badobj_unchanged"],
        "hardware quiescent witness drift",
    )
    for row in value["authority"].values():
        check_binding(row)
    return value


def verify_first_red() -> dict[str, Any]:
    value = load(SESSION_FIRST_RED)
    require(
        value["status"]
        == "FIRST-RED-editor-stalled-on-56th-serially-acknowledged-key",
        "hardware First Red status drift",
    )
    d1 = value["D1"]
    require(
        d1["accepted_before_stall"] == 55
        and d1["stalled_key_ordinal"] == 56
        and d1["unchanged_seconds"] >= 120
        and d1["plain_burst"]["keys"] == 40
        and d1["plain_burst"]["frames_per_key"] == 24.025,
        "D1 First Red witness drift",
    )
    independent = value["independent_rows"]
    require(
        independent["D2"]["wrap"]["frames"] == 74
        and independent["D2"]["scroll"]["frames"] == 80,
        "D2 independent measurement drift",
    )
    require(
        len(independent["D3"]["smokes"]) == 4
        and all(
            row["status"] == "passed-exact-target-result"
            for row in independent["D3"]["smokes"]
        )
        and independent["D3"]["C2J"] == "CLEAR"
        and independent["D3"]["phase_owner"] == "NONE"
        and independent["D3"]["mem_oom"] == 0
        and independent["D3"]["gc_badobj_unchanged"],
        "D3 independent/quiescent witness drift",
    )
    require(
        value["decision"]["release_phase_E"] == "closed"
        and value["decision"]["product_fix_authorized"] is False,
        "Halt #1 decision boundary drift",
    )
    for row in value["authority"].values():
        check_binding(row)
    return value


def selftest() -> None:
    config = load(CONFIG)
    d1 = config["D1"]
    require(
        EditorSession.delta(0xFFFE, 0x0002) == 4,
        "frame wrap arithmetic failed",
    )
    require(
        d1["plain_burst_keys"] + d1["plain_fill_keys"] + 2 == 80,
        "printable schedule mutation accepted",
    )
    require(
        d1["scroll_prep_returns"] + 1 == 49,
        "return schedule mutation accepted",
    )
    require(
        all(len(form) <= 76 for form, _expected in form_rows(config)),
        "oversized verified-input form accepted",
    )
    mutated = dict(d1)
    mutated["maximum_single_key_frames"] = 178
    require(
        mutated["maximum_single_key_frames"]
            != d1["maximum_single_key_frames"],
        "frame-ceiling mutation did not change the contract",
    )


def dry_run() -> dict[str, Any]:
    value = prepare()
    config = load(CONFIG)
    for form, _expected in form_rows(config):
        result = BASE.run(
            [
                str(HARNESS), "--dry-run", "--verified-input",
                "--form", form,
            ],
            timeout=30,
        )
        require("DRY-RUN:" in result.stdout, "dry-run command absent")
    return value


def start() -> None:
    require(not RECEIPT.exists(), "hardware receipt already exists")
    preparation = prepare()
    session = EditorSession(load(CONFIG), preparation)
    session.execute()
    verify()


def resume() -> None:
    require(not RECEIPT.exists(), "hardware receipt already exists")
    preparation = prepare()
    session = EditorSession(load(CONFIG), preparation)
    session.execute(resume_at_bound_REPL=True)
    verify()


def arm() -> None:
    require(not RECEIPT.exists(), "hardware receipt already exists")
    preparation = prepare()
    session = EditorSession(load(CONFIG), preparation)
    session.arm_physical_sys()


def direct() -> None:
    require(not RECEIPT.exists(), "hardware receipt already exists")
    preparation = prepare()
    session = EditorSession(load(CONFIG), preparation)
    session.direct_deploy()
    session.execute(resume_at_bound_REPL=True)
    verify()


def continue_direct() -> None:
    require(not RECEIPT.exists(), "hardware receipt already exists")
    preparation = prepare()
    session = EditorSession(load(CONFIG), preparation)
    session.continue_loaded_direct()
    session.execute(resume_at_bound_REPL=True)
    verify()


def media() -> None:
    require(not RECEIPT.exists(), "hardware receipt already exists")
    preparation = prepare()
    session = EditorSession(load(CONFIG), preparation)
    session.media_deploy()
    session.execute(resume_at_bound_REPL=True)
    verify()


def continue_media() -> None:
    require(not RECEIPT.exists(), "hardware receipt already exists")
    preparation = prepare()
    session = EditorSession(load(CONFIG), preparation)
    session.continue_media()
    session.execute(resume_at_bound_REPL=True)
    verify()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=(
            "selftest", "prepare", "dry-run", "start", "arm", "resume",
            "direct", "continue-direct", "media", "continue-media", "verify",
            "verify-first-red",
            "continue-after-scratch",
            "continue-independent-after-d1-red",
            "continue-independent-after-d2-harness-red",
        ),
    )
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            selftest()
            print("c2-v126-editor-hardware: SELFTEST PASS mutations=4")
        elif args.action == "prepare":
            value = prepare()
            print(
                "c2-v126-editor-hardware: PREPARE PASS "
                f"forms={value['host_proofs']['verified_input_forms']} "
                f"roles={len(value['candidate']['preloads'])}")
        elif args.action == "dry-run":
            value = dry_run()
            print(
                "c2-v126-editor-hardware: DRY-RUN PASS "
                f"forms={value['host_proofs']['verified_input_forms']}")
        elif args.action == "start":
            start()
            value = verify()
            table = value["decision_table"]
            print(
                "c2-v126-editor-hardware: PASS "
                f"plain={table['target_plain_single_frames']} "
                f"wrap={table['target_wrap_single_frames']} "
                f"scroll={table['target_scroll_single_frames']} "
                f"dropped={table['dropped_input_total']}")
        elif args.action == "resume":
            resume()
            value = verify()
            table = value["decision_table"]
            print(
                "c2-v126-editor-hardware: RESUME PASS "
                f"plain={table['target_plain_single_frames']} "
                f"wrap={table['target_wrap_single_frames']} "
                f"scroll={table['target_scroll_single_frames']} "
                f"dropped={table['dropped_input_total']}")
        elif args.action == "arm":
            arm()
            print(
                "c2-v126-editor-hardware: ARM PASS "
                "type physical SYS 8227 plus RETURN")
        elif args.action == "direct":
            direct()
            value = verify()
            table = value["decision_table"]
            print(
                "c2-v126-editor-hardware: DIRECT PASS "
                f"plain={table['target_plain_single_frames']} "
                f"wrap={table['target_wrap_single_frames']} "
                f"scroll={table['target_scroll_single_frames']} "
                f"dropped={table['dropped_input_total']}")
        elif args.action == "continue-direct":
            continue_direct()
            value = verify()
            table = value["decision_table"]
            print(
                "c2-v126-editor-hardware: CONTINUE-DIRECT PASS "
                f"plain={table['target_plain_single_frames']} "
                f"wrap={table['target_wrap_single_frames']} "
                f"scroll={table['target_scroll_single_frames']} "
                f"dropped={table['dropped_input_total']}")
        elif args.action == "media":
            media()
            value = verify()
            table = value["decision_table"]
            print(
                "c2-v126-editor-hardware: MEDIA PASS "
                f"plain={table['target_plain_single_frames']} "
                f"wrap={table['target_wrap_single_frames']} "
                f"scroll={table['target_scroll_single_frames']} "
                f"dropped={table['dropped_input_total']}")
        elif args.action == "continue-media":
            continue_media()
            value = verify()
            table = value["decision_table"]
            print(
                "c2-v126-editor-hardware: CONTINUE-MEDIA PASS "
                f"plain={table['target_plain_single_frames']} "
                f"wrap={table['target_wrap_single_frames']} "
                f"scroll={table['target_scroll_single_frames']} "
                f"dropped={table['dropped_input_total']}")
        elif args.action == "continue-after-scratch":
            preparation = prepare()
            session = EditorSession(load(CONFIG), preparation)
            session.continue_after_scratch()
            value = verify()
            table = value["decision_table"]
            print(
                "c2-v126-editor-hardware: CONTINUE-AFTER-SCRATCH PASS "
                f"plain={table['target_plain_single_frames']} "
                f"wrap={table['target_wrap_single_frames']} "
                f"scroll={table['target_scroll_single_frames']} "
                f"dropped={table['dropped_input_total']}")
        elif args.action == "continue-independent-after-d1-red":
            preparation = prepare()
            session = EditorSession(load(CONFIG), preparation)
            session.continue_independent_after_d1_red()
            value = load(SESSION_FIRST_RED)
            print(
                "c2-v126-editor-hardware: FIRST RED RECORDED "
                f"accepted={value['D1']['accepted_before_stall']} "
                f"stalled={value['D1']['stalled_key_ordinal']} "
                f"independent-smokes="
                f"{len(value['independent_rows']['D3']['smokes'])}")
        elif args.action == "continue-independent-after-d2-harness-red":
            preparation = prepare()
            session = EditorSession(load(CONFIG), preparation)
            session.continue_independent_after_d2_harness_red()
            value = load(SESSION_FIRST_RED)
            print(
                "c2-v126-editor-hardware: FIRST RED RECORDED "
                f"accepted={value['D1']['accepted_before_stall']} "
                f"stalled={value['D1']['stalled_key_ordinal']} "
                f"independent-smokes="
                f"{len(value['independent_rows']['D3']['smokes'])}")
        elif args.action == "verify-first-red":
            value = verify_first_red()
            print(
                "c2-v126-editor-hardware: FIRST RED VERIFY PASS "
                f"accepted={value['D1']['accepted_before_stall']} "
                f"stalled={value['D1']['stalled_key_ordinal']} "
                f"wrap={value['independent_rows']['D2']['wrap']['frames']} "
                f"scroll="
                f"{value['independent_rows']['D2']['scroll']['frames']}")
        else:
            value = verify()
            table = value["decision_table"]
            print(
                "c2-v126-editor-hardware: VERIFY PASS "
                f"dropped={table['dropped_input_total']}")
        return 0
    except (
        BASE.SoakError, SCREEN.CheckError, SessionError,
        OSError, ValueError, subprocess.TimeoutExpired,
    ) as error:
        print(f"c2-v126-editor-hardware: FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
