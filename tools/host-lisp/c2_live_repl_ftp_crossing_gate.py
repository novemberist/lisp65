#!/usr/bin/env python3
"""Forbid every FTP helper takeover after a Lisp65 product starts."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config/c2-live-repl-ftp-crossing.json"
GATES = ROOT / "mk/gates.mk"
PLAN = ROOT / "docs/planning/post-v1.4.0-direction-plan.md"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-live-repl-ftp-crossing-gate-receipt.json"
)
FORMAT = "lisp65-c2.3-live-repl-ftp-crossing-gate-v1"
RECORDED_ON = "2026-08-09"


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"file absent: {path}")
    data = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(data),
        "sha256": sha_bytes(data),
    }


def git_blob(commit: str, path: Path) -> dict[str, Any]:
    relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
    data = subprocess.run(
        ["git", "show", f"{commit}:{relative}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout
    return {
        "authority": "git-blob",
        "commit": commit,
        "path": relative,
        "bytes": len(data),
        "sha256": sha_bytes(data),
    }


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def ordered(text: str, tokens: list[str], message: str) -> None:
    cursor = -1
    for token in tokens:
        cursor = text.find(token, cursor + 1)
        require(cursor >= 0, f"{message}: {token}")


def audit_runner(path: Path, source: str | None = None) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8") if source is None else source
    begin = "# FTP-BASIC-ONLY-BEGIN"
    end = "# FTP-BASIC-ONLY-END"
    live_begin = "# PRODUCT-LIVE-BEGIN"
    live_end = "# PRODUCT-LIVE-END"
    require(text.count(begin) == text.count(end) == 1,
            f"{path.name}: FTP ownership markers drift")
    require(text.count(live_begin) == text.count(live_end) == 1,
            f"{path.name}: product-live markers drift")
    basic = text.split(begin, 1)[1].split(end, 1)[0]
    live = text.split(live_begin, 1)[1].split(live_end, 1)[0]
    require(basic.count('"$FTP"') == 1 and " -F " in basic,
            f"{path.name}: exactly one pre-boot FTP helper required")
    ftp_calls = [line for line in text.splitlines()
                 if '"$FTP"' in line and '[ -x "$FTP" ]' not in line]
    require(len(ftp_calls) == 1 and ftp_calls[0] in basic,
            f"{path.name}: a second FTP invocation exists outside pre-boot")
    require(text.count("mega65_ftp") == 1,
            f"{path.name}: a raw FTP helper invocation bypasses ownership")
    require('"$FTP"' not in live and "mega65_ftp" not in live,
            f"{path.name}: FTP access survived in live-product region")
    ordered(basic, [
        '-c "put $product $product_remote"',
        '-c "get $product_remote $OUT/product-readback.d81"',
        '-c "put $library $library_remote"',
        '-c "get $library_remote $OUT/library-readback.d81"',
        '-c "mount $product_remote"',
        "-c exit",
    ], f"{path.name}: two-media FTP order drift")
    require('cmp "$product" "$OUT/product-readback.d81"' in text
            and 'cmp "$library" "$OUT/library-readback.d81"' in text,
            f"{path.name}: media readback proof absent")
    require("# OWNER-FREEZER-MOUNT" in text
            and "physical idle-REPL media change" in text
            and "deliberately no FTP" in text,
            f"{path.name}: physical Freezer handoff absent")
    stage = text.split('if [ "$ACTION" = stage ]; then', 1)[1]
    ordered(stage, [
        "run_m65 -F",
        "ftp_bundle_under_basic",
        live_begin,
        "sleep",
        "freezer-mount-required",
        live_end,
    ], f"{path.name}: reset/upload/boot/Freezer order drift")
    confirm = text.split('if [ "$ACTION" = confirm-library ]; then', 1)[1]
    confirm = confirm.split("\nfi\n", 1)[0]
    require('"$FTP"' not in confirm and "mega65_ftp" not in confirm,
            f"{path.name}: Freezer confirmation invokes FTP")
    require("library-owner-confirmed" in confirm,
            f"{path.name}: owner library confirmation absent")
    return {
        "runner": path.relative_to(ROOT).as_posix(),
        "ftp_helper_lifetimes": 1,
        "post_boot_ftp_invocations": 0,
        "product_mounted_last": True,
        "product_readback": True,
        "library_readback": True,
        "library_mount_after_boot": "physical-Freezer-drive-8",
    }


def validate_contract(value: dict[str, Any]) -> None:
    require(value.get("format")
            == "lisp65-c2.3-live-repl-ftp-crossing-contract-v1",
            "FTP-crossing contract format drift")
    require(value.get("status") == "owner-approved-corrected-choreography",
            "FTP-crossing contract status drift")
    require(value.get("authorization_commit")
            == "bf346d413092dcd6909413d02b2935769c2aacd0",
            "FTP-crossing authorization drift")
    require(value.get("runners") == [
        "scripts/c2-trace-core-abi-link93-hw.sh",
        "scripts/c2-defstruct-terminal-ingress-hw.sh",
    ], "FTP-crossing runner set drift")
    require(value.get("contract") == {
        "fresh_basic_before_helper": True,
        "ftp_helper_lifetimes_before_product_boot": 1,
        "both_media_uploaded_and_read_back_in_that_lifetime": True,
        "product_medium_mounted_last": True,
        "post_boot_ftp_invocations": 0,
        "library_mount_after_boot": "physical-Freezer-drive-8",
        "freezer_return": "F3",
        "live_repl_ftp_policy": "forbidden",
    }, "FTP-crossing semantic contract drift")
    claim = value.get("claim_limit", "")
    require("ran no Link-93 form" in claim and "no product" in claim
            and "R/A/I/G" in claim and "v1.5 claim" in claim,
            "FTP-crossing claim limit broadened")


def derive() -> dict[str, Any]:
    contract = load(CONFIG)
    validate_contract(contract)
    runners = [ROOT / row for row in contract["runners"]]
    audits = [audit_runner(path) for path in runners]
    authorization = git_blob(contract["authorization_commit"], PLAN)
    require(b"Mount choreography approved" in subprocess.run(
        ["git", "show", f"{contract['authorization_commit']}:"
         f"{PLAN.relative_to(ROOT).as_posix()}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout,
        "owner authorization text absent")
    return {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "HARNESS-FIRST-RED-ATTRIBUTED; CORRECTED-CHOREOGRAPHY-GREEN",
        "first_red": {
            "forms_run": 0,
            "product_medium_readback": "byteidentical-before-crossing",
            "library_transfer": "not-completed",
            "mechanism": (
                "second mega65_ftp -F attempted fastloader takeover of the "
                "live Workbench and injected GO64/Y ten times"
            ),
            "classification": "harness-only; no Link-93 claim",
        },
        "contract": contract["contract"],
        "runner_audits": audits,
        "bindings": {
            "contract": bind(CONFIG),
            "authorization": authorization,
            "driver": bind(Path(__file__).resolve()),
            "runners": [bind(path) for path in runners],
        },
        "accounting": {
            "product_bytes_changed": 0,
            "product_links": 0,
            "Link93_forms_run": 0,
            "defstruct_forms_run": 0,
            "hardware_result_claims": 0,
        },
        "claim_limit": contract["claim_limit"],
    }


def validate(value: dict[str, Any], *, verify_sources: bool) -> None:
    require(value.get("format") == FORMAT,
            "FTP-crossing gate format drift")
    require(value.get("status")
            == "HARNESS-FIRST-RED-ATTRIBUTED; CORRECTED-CHOREOGRAPHY-GREEN",
            "FTP-crossing gate status drift")
    require(value.get("first_red") == {
        "forms_run": 0,
        "product_medium_readback": "byteidentical-before-crossing",
        "library_transfer": "not-completed",
        "mechanism": (
            "second mega65_ftp -F attempted fastloader takeover of the "
            "live Workbench and injected GO64/Y ten times"
        ),
        "classification": "harness-only; no Link-93 claim",
    }, "FTP-crossing first-red attribution drift")
    require(value.get("contract", {}).get("ftp_helper_lifetimes_before_product_boot") == 1
            and value.get("contract", {}).get("post_boot_ftp_invocations") == 0
            and value.get("contract", {}).get("live_repl_ftp_policy") == "forbidden",
            "FTP-crossing core rule dimmed")
    audits = value.get("runner_audits", [])
    require(len(audits) == 2
            and all(row.get("ftp_helper_lifetimes") == 1
                    and row.get("post_boot_ftp_invocations") == 0
                    and row.get("product_mounted_last") is True
                    and row.get("library_mount_after_boot")
                    == "physical-Freezer-drive-8" for row in audits),
            "FTP-crossing runner audit drift")
    require(value.get("accounting") == {
        "product_bytes_changed": 0,
        "product_links": 0,
        "Link93_forms_run": 0,
        "defstruct_forms_run": 0,
        "hardware_result_claims": 0,
    }, "FTP-crossing accounting broadened")
    if verify_sources:
        require(value == derive(), "FTP-crossing receipt is stale")


def mutation_sources() -> dict[str, tuple[int, Callable[[str], str]]]:
    return {
        "post-boot-F-helper": (0, lambda s: s.replace(
            "# PRODUCT-LIVE-END", '"$FTP" -F -c exit\n  # PRODUCT-LIVE-END', 1)),
        "post-boot-raw-helper": (1, lambda s: s.replace(
            "# PRODUCT-LIVE-END", "mega65_ftp -F -c exit\n  # PRODUCT-LIVE-END", 1)),
        "second-preboot-helper": (0, lambda s: s.replace(
            "# FTP-BASIC-ONLY-END", '"$FTP" -F -c exit\n  # FTP-BASIC-ONLY-END', 1)),
        "mount-library-last": (1, lambda s: s.replace(
            '-c "mount $product_remote"', '-c "mount $library_remote"', 1)),
        "drop-library-put": (0, lambda s: s.replace(
            '-c "put $library $library_remote" \\\n', "", 1)),
        "drop-library-get": (1, lambda s: s.replace(
            '-c "get $library_remote $OUT/library-readback.d81" \\\n', "", 1)),
        "drop-product-readback-proof": (0, lambda s: s.replace(
            '  cmp "$product" "$OUT/product-readback.d81"\n', "", 1)),
        "drop-library-readback-proof": (1, lambda s: s.replace(
            '  cmp "$library" "$OUT/library-readback.d81"\n', "", 1)),
        "drop-Freezer-handoff": (0, lambda s: s.replace(
            "# OWNER-FREEZER-MOUNT", "# OWNER-MOUNT", 1)),
        "drop-live-boundary": (1, lambda s: s.replace(
            "# PRODUCT-LIVE-END", "# PRODUCT-RUN-END", 1)),
        "FTP-in-Freezer-confirmation": (0, lambda s: s.replace(
            "# OWNER-FREEZER-MOUNT", '"$FTP" -F -c exit\n  # OWNER-FREEZER-MOUNT', 1)),
        "skip-cold-reset": (1, lambda s: s.replace("  run_m65 -F\n", "", 1)),
    }


def rejected_mutations() -> list[str]:
    contract = load(CONFIG)
    paths = [ROOT / row for row in contract["runners"]]
    sources = [path.read_text(encoding="utf-8") for path in paths]
    rejected: list[str] = []
    for name, (index, mutate) in mutation_sources().items():
        candidate = mutate(sources[index])
        require(candidate != sources[index], f"mutation did not alter source: {name}")
        try:
            audit_runner(paths[index], candidate)
        except GateError:
            rejected.append(name)
    require(len(rejected) == len(mutation_sources()),
            "FTP-crossing mutation survived: "
            + ", ".join(sorted(set(mutation_sources()) - set(rejected))))
    return rejected


def gate_wiring() -> None:
    text = GATES.read_text(encoding="utf-8")
    require(all(token in text for token in (
        "c2-live-repl-ftp-crossing-selftest:",
        "python3 tools/host-lisp/c2_live_repl_ftp_crossing_gate.py selftest",
        "c2-live-repl-ftp-crossing-check:",
        "python3 tools/host-lisp/c2_live_repl_ftp_crossing_gate.py check",
        "check-source: c2-live-repl-ftp-crossing-selftest",
    )), "FTP-crossing permanent gate wiring absent")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check", "selftest"))
    action = parser.parse_args().action
    if action == "record":
        value = derive()
        validate(value, verify_sources=False)
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_bytes(canonical(value))
        print(f"live-REPL FTP crossing: WROTE {RECEIPT.relative_to(ROOT)}")
        return 0
    value = load(RECEIPT)
    gate_wiring()
    validate(value, verify_sources=(action == "check"))
    rejected = rejected_mutations()
    if action == "check":
        print("live-REPL FTP crossing: PASS runners=2 post-boot-FTP=0")
    else:
        print(f"live-REPL FTP crossing: SELFTEST PASS mutations={len(rejected)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GateError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"live-REPL FTP crossing: FAIL: {error}", file=sys.stderr)
        raise SystemExit(2)
