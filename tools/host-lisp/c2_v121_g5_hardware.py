#!/usr/bin/env python3
"""Prepare, bind, and close the fresh v1.2.1 nine-case G5 hardware run."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_g5_hardware_close as CLOSE  # noqa: E402


BASE = ROOT / "build/c2.2/v1.2.1-acceptance/r5"
RUNBOOK = BASE / "g5-runbook.json"
PREFLIGHT = BASE / "r5-preflight-receipt.json"
SESSION = BASE / "hardware-session-01"
EVIDENCE = SESSION / "g5"
DEPLOYMENT = SESSION / "deployment.json"
TRANSPORT = SESSION / "media-transport-hardware-receipt.json"
G5_RECEIPT = SESSION / "g5-hardware-receipt.json"
HARNESS_FIRST_RED = SESSION / "harness-first-red.json"
RESTAGE_ROUTE = SESSION / "restage-route-observation.json"
FORMAT = "lisp65-c2-lite-v1.2.1-G5-hardware-session-v1"
TRANSPORT_FORMAT = "lisp65-c2-lite-v1.2.1-media-transport-hardware-receipt-v1"
REMOTE_MEDIA = "L65V121.D81"


class G5Error(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise G5Error(message)


def load(path: Path, label: str) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"{label} missing")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise G5Error(f"cannot read {label}: {error}") from error
    require(isinstance(value, dict), f"{label} is not an object")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def binding(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"binding missing: {path}")
    return {
        "path": relative(path),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii")


def write_exact(path: Path, value: dict[str, Any]) -> None:
    data = canonical(value)
    if path.exists() or path.is_symlink():
        require(
            path.is_file() and not path.is_symlink() and path.read_bytes() == data,
            f"existing generated file differs: {path}",
        )
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def authorities() -> tuple[dict[str, Any], dict[str, Any]]:
    runbook = load(RUNBOOK, "R5 runbook")
    preflight = load(PREFLIGHT, "R5 preflight")
    require(
        runbook.get("status") == "ready-first-red"
        and preflight.get("status") == "passed-ready-for-fresh-G5-hardware"
        and runbook.get("artifact_set_sha256")
        == preflight.get("artifact_set_sha256")
        and preflight.get("claims", {}).get("hardware_started") is False,
        "R5 authority is not the untouched fresh-G5 handoff",
    )
    return runbook, preflight


def prepare() -> dict[str, Any]:
    runbook, preflight = authorities()
    product = ROOT / runbook["product_d81"]
    work = ROOT / runbook["work_d81"]
    bank2 = BASE / "product/01-bank2-static-code.bin"
    bank3 = BASE / "product/06-runtime-overlays-session-final.bin"
    region1 = BASE / "product/07-runtime-overlays-session-final-region1.bin"
    c2d = BASE / "product/09-initial.c2d-v6.bin"
    elf = BASE / "product/14-lisp65-c2-substitution-linked.prg.elf"
    role_rows = preflight["materialized_artifacts"]
    by_role = {row["role"]: row for row in role_rows}
    for role, path in (
        ("product-d81", product),
        ("work-d81", work),
        ("c2-bank2-static-code-plane", bank2),
        ("c2-session-family-region-0", bank3),
        ("c2-session-family-region-1", region1),
        ("c2d-v6-code-plane", c2d),
        ("linked-product-elf", elf),
    ):
        require(
            path.is_file()
            and path.stat().st_size == by_role[role]["bytes"]
            and sha(path) == by_role[role]["sha256"],
            f"materialized R5 role drift: {role}",
        )

    deployment = {
        "format": FORMAT,
        "version": 1,
        "status": "prepared-hardware-not-run",
        "runbook": binding(RUNBOOK),
        "preflight": binding(PREFLIGHT),
        "artifact_set_sha256": runbook["artifact_set_sha256"],
        "product_build_id": runbook["product_build_id"],
        "profile_build_id": runbook["profile_build_id"],
        "source_commit": runbook["source_commit"],
        "remote_head": runbook["remote_head"],
        "remote_media": REMOTE_MEDIA,
        "product_d81": binding(product),
        "work_d81": binding(work),
        "elf": binding(elf),
        "stage_authorities": {
            "bank2": {**binding(bank2), "address": 0x00020000},
            "bank3": {**binding(bank3), "address": 0x00030000},
            "session_region1": {**binding(region1), "address": 0x0005BD00},
            "c2d": {**binding(c2d), "address": 0x00050000},
        },
        "execution": {
            "hardware_started": False,
            "product_builds": 0,
            "product_links": 0,
            "product_byte_changes": 0,
        },
        "claim_limit": (
            "Preparation only. Hardware, G5, R6, G6, promotion and release are "
            "not claimed."
        ),
    }
    write_exact(DEPLOYMENT, deployment)
    for directory in (
        EVIDENCE,
        EVIDENCE / "counters",
        EVIDENCE / "runstop",
        EVIDENCE / "freezer",
        EVIDENCE / "nested",
        EVIDENCE / "restage",
    ):
        directory.mkdir(parents=True, exist_ok=True)
    poison2 = bytes((0xA5 ^ index) & 0xFF for index in range(256))
    poison3 = bytes((0x5A ^ index) & 0xFF for index in range(256))
    for path, data in (
        (EVIDENCE / "restage/poison-bank2-prefix.bin", poison2),
        (EVIDENCE / "restage/poison-bank3-prefix.bin", poison3),
    ):
        if path.exists():
            require(path.read_bytes() == data, f"poison authority drift: {path}")
        else:
            path.write_bytes(data)
    return deployment


def transport() -> dict[str, Any]:
    deployment = load(DEPLOYMENT, "G5 deployment")
    staged = deployment["stage_authorities"]
    observed = {
        "uploaded_product_d81": SESSION / "uploaded-media-readback.d81",
        "bank2": SESSION / "cold-stage-bank2.bin",
        "bank3": SESSION / "cold-stage-bank3.bin",
        "session_region1": SESSION / "cold-stage-session_region1.bin",
        "c2d": SESSION / "cold-stage-c2d.bin",
        "boot_screen": EVIDENCE / "cold-boot.txt",
        "device_core_id": SESSION / "device-core-id.bin",
        "upload_mount_log": SESSION / "media-upload-mount.log",
    }
    require(
        observed["uploaded_product_d81"].read_bytes()
        == (ROOT / deployment["product_d81"]["path"]).read_bytes(),
        "uploaded product D81 differs from sealed R5 medium",
    )
    for name in ("bank2", "bank3", "session_region1"):
        authority = ROOT / staged[name]["path"]
        require(
            observed[name].read_bytes() == authority.read_bytes(),
            f"cold-stage target differs: {name}",
        )
    c2d_initial = (ROOT / staged["c2d"]["path"]).read_bytes()
    c2d_live = observed["c2d"].read_bytes()
    require(
        len(c2d_live) == len(c2d_initial),
        "live post-boot C2D observation length drift",
    )
    c2d_differences = sum(a != b for a, b in zip(c2d_initial, c2d_live))
    require(
        c2d_differences > 0,
        "post-boot C2D unexpectedly remained the pre-boot initial image",
    )
    boot = observed["boot_screen"].read_text(encoding="utf-8", errors="strict")
    require(
        "WORKBENCH - DIALECT V2" in boot and "lisp65>" in boot,
        "cold media route did not reach the product REPL",
    )
    value = {
        "format": TRANSPORT_FORMAT,
        "version": 1,
        "recorded_on": date.today().isoformat(),
        "status": "passed-sealed-media-upload-mount-and-cold-stage",
        "authority": {
            "runbook": binding(RUNBOOK),
            "product_d81": deployment["product_d81"],
            "stage_authorities": staged,
        },
        "observations": {name: binding(path) for name, path in observed.items()},
        "transport": {
            "remote_media": deployment["remote_media"],
            "mount_route": "mega65_ftp-put-readback-mount",
            "stage_proof": (
                "target-byteidentity for immutable Bank-2, Bank-3 and Session "
                "Region-1; post-boot C2D is bound as live runtime state"
            ),
            "pre_runtime_gate_correction": {
                "classification": "acceptance-harness-model-only",
                "finding": (
                    "The first checker revision incorrectly required the live "
                    "post-boot C2D span to equal initial.c2d-v6.bin. Boot and "
                    "Session publication legitimately mutate that runtime-owned "
                    "span; the false-positive assertion was removed before any "
                    "runtime G5 form."
                ),
                "initial_c2d": staged["c2d"],
                "live_c2d": binding(observed["c2d"]),
                "different_bytes": c2d_differences,
                "product_failure": False,
            },
        },
        "execution_accounting": {
            "physical_devices": 1,
            "product_builds": 0,
            "product_links": 0,
            "product_byte_changes": 0,
        },
        "claim_limit": (
            "Binds the sealed R5 D81 to the observed cold-stage targets. G5 "
            "runtime cases, R6, G6, promotion and release remain unclaimed."
        ),
    }
    write_exact(TRANSPORT, value)
    return value


def close() -> dict[str, Any]:
    deployment = load(DEPLOYMENT, "G5 deployment")
    bank2 = ROOT / deployment["stage_authorities"]["bank2"]["path"]
    bank3 = ROOT / deployment["stage_authorities"]["bank3"]["path"]
    value = CLOSE.collect(RUNBOOK, TRANSPORT, EVIDENCE, bank2, bank3)
    CLOSE.write_exclusive(G5_RECEIPT, value)
    return CLOSE.verify_receipt(G5_RECEIPT)


def record_harness_first_red() -> dict[str, Any]:
    deployment = load(DEPLOYMENT, "G5 deployment")
    screenshot = SESSION / "ftp-timeout-screen.png"
    screen_text = SESSION / "ftp-timeout-screen.ansi.txt"
    error_log = SESSION / "ftp-timeout-screen.err"
    upload_log = SESSION / "ftp-timeout-upload.log"
    require(
        screenshot.is_file()
        and screen_text.is_file()
        and error_log.is_file()
        and upload_log.is_file()
        and upload_log.stat().st_size == 0
        and not (SESSION / "uploaded-media-readback.d81").exists()
        and not TRANSPORT.exists(),
        "harness First Red is not the observed pre-upload timeout",
    )
    value = {
        "format": "lisp65-c2-lite-v1.2.1-G5-harness-first-red-v1",
        "version": 1,
        "recorded_on": date.today().isoformat(),
        "classification": "acceptance-harness-ftp-entry-route-only",
        "status": "excluded-no-media-upload-no-product-execution",
        "finding": (
            "The combined FTP entry route timed out while switching from the "
            "pre-existing machine state. Its upload log remained empty, no "
            "uploaded-media readback existed, and the sealed product had not "
            "started. A physical cold restart to BASIC precedes the fresh retry."
        ),
        "authority": {
            "deployment": binding(DEPLOYMENT),
            "product_d81": deployment["product_d81"],
        },
        "evidence": {
            "screen": binding(screenshot),
            "screen_text": binding(screen_text),
            "tool_log": binding(error_log),
            "empty_upload_log": binding(upload_log),
        },
        "product_execution": False,
        "G5_case_consumed": False,
        "claim_limit": (
            "Harness-only First Red before media upload or product execution. "
            "It carries no G5, product, R6, G6, promotion or release claim."
        ),
    }
    write_exact(HARNESS_FIRST_RED, value)
    return value


def record_restage_route() -> dict[str, Any]:
    deployment = load(DEPLOYMENT, "G5 deployment")
    restage = EVIDENCE / "restage"
    soft_reset_log = restage / "soft-reset-after-poison.log"
    poison2 = restage / "poison-bank2-prefix.bin"
    poison2_readback = restage / "poison-bank2-readback.bin"
    poison3 = restage / "poison-bank3-prefix.bin"
    poison3_readback = restage / "poison-bank3-readback.bin"
    require(
        soft_reset_log.is_file()
        and soft_reset_log.stat().st_size == 0
        and poison2.read_bytes() == poison2_readback.read_bytes()
        and poison3.read_bytes() == poison3_readback.read_bytes()
        and not (restage / "post-media-restage.txt").exists(),
        "restage-route observation does not match the destructive pre-boot state",
    )
    value = {
        "format": "lisp65-c2-lite-v1.2.1-G5-restage-route-observation-v1",
        "version": 1,
        "recorded_on": date.today().isoformat(),
        "classification": "acceptance-harness-soft-reset-after-destruction",
        "status": "excluded-before-required-physical-cold-boot",
        "finding": (
            "After the fixture deliberately replaced the Bank-2 and Bank-3 "
            "prefixes, the FTP soft-reset entry route stalled and the operator "
            "observed the red fail-closed border. The route had not mounted the "
            "medium (empty log) and therefore had not begun the contractual "
            "cold-boot repair. The accepted continuation is a physical cold "
            "restart to BASIC followed by mounting the unchanged sealed D81."
        ),
        "authority": {
            "deployment": binding(DEPLOYMENT),
            "product_d81": deployment["product_d81"],
        },
        "evidence": {
            "poison_bank2": binding(poison2),
            "poison_bank2_readback": binding(poison2_readback),
            "poison_bank3": binding(poison3),
            "poison_bank3_readback": binding(poison3_readback),
            "empty_soft_reset_log": binding(soft_reset_log),
        },
        "operator_observation": "red-border-after-poison-before-cold-boot",
        "G5_case_result": "not-yet-observed",
        "product_byte_changes": 0,
        "claim_limit": (
            "Harness-route observation after intentional volatile destruction "
            "and before the required cold boot. It is not a G5 case result."
        ),
    }
    write_exact(RESTAGE_ROUTE, value)
    return value


def verify() -> None:
    deployment = load(DEPLOYMENT, "G5 deployment")
    require(
        deployment.get("format") == FORMAT
        and deployment.get("status") == "prepared-hardware-not-run",
        "G5 deployment drift",
    )
    if TRANSPORT.exists():
        receipt = load(TRANSPORT, "transport receipt")
        require(
            receipt.get("format") == TRANSPORT_FORMAT
            and receipt.get("status")
            == "passed-sealed-media-upload-mount-and-cold-stage",
            "transport receipt drift",
        )
    if G5_RECEIPT.exists():
        CLOSE.verify_receipt(G5_RECEIPT)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=(
            "prepare",
            "transport",
            "close",
            "verify",
            "record-harness-first-red",
            "record-restage-route",
            "selftest",
        ),
    )
    args = parser.parse_args()
    try:
        if args.action in {"prepare", "selftest"}:
            value = prepare()
            print(
                "c2-v121-g5-hardware: PREPARED "
                f"set={value['artifact_set_sha256']} hardware=not-run"
            )
        elif args.action == "transport":
            value = transport()
            print(
                "c2-v121-g5-hardware: TRANSPORT PASS "
                f"product={value['authority']['product_d81']['sha256']}"
            )
        elif args.action == "close":
            value = close()
            print(
                "c2-v121-g5-hardware: G5 PASS "
                f"cases={len(value['cases'])} set={value['product']['artifact_set_sha256']}"
            )
        elif args.action == "record-harness-first-red":
            value = record_harness_first_red()
            print(
                "c2-v121-g5-hardware: HARNESS FIRST RED BOUND "
                f"class={value['classification']} product-execution=no"
            )
        elif args.action == "record-restage-route":
            value = record_restage_route()
            print(
                "c2-v121-g5-hardware: RESTAGE ROUTE BOUND "
                f"class={value['classification']} G5=not-yet-observed"
            )
        else:
            verify()
            print("c2-v121-g5-hardware: VERIFY PASS")
        return 0
    except (
        G5Error,
        CLOSE.CloseError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        print(f"c2-v121-g5-hardware: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
