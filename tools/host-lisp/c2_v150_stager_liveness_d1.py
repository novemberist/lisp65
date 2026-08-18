#!/usr/bin/env python3
"""Prepare/check the fresh physical D1 for the delivered stager liveness fix."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))
import repl_screen_check as SCREEN  # noqa: E402


CONFIG = ROOT / "config/c2-v150-link97-stager-liveness-d1.json"
RUNNER = ROOT / "scripts/c2-v150-link97-stager-liveness-d1-hw.sh"
MEDIA = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-link97-stager-liveness-media-receipt.json")
PREDECESSOR_PREP = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-link97-device-session-preparation-receipt.json")
PREP = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-link97-stager-liveness-d1-preparation-receipt.json")
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-link97-stager-liveness-d1-first-red-receipt.json")
RESULT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-link97-stager-liveness-d1-receipt.json")
OUT = ROOT / "build/c2.3/v1.5.0-link97-stager-liveness-d1"
FORMAT = "lisp65-c2.3-v150-link97-stager-liveness-d1-preparation-v1"
STATUS = "V150-LINK97-STAGER-LIVENESS-D1-PREPARED-NOT-RUN"
SIGNS = ["LISP65: STAGING MEDIA", "LISP65: BUILDING HEAP",
         "LISP65: LOADING LIBRARIES"]


class D1Error(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise D1Error(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    path = path if path.is_absolute() else ROOT / path
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def contract(value: dict[str, Any] | None = None) -> dict[str, Any]:
    value = value or load(CONFIG)
    media = load(MEDIA)
    require(
        value.get("format") == "lisp65-c2-v150-link97-stager-liveness-d1-v1"
        and value.get("status") == "prepared-not-run"
        and value.get("access_free_seconds") == 45
        and value.get("required_visible_liveness") == SIGNS
        and value.get("required_terminal_state")
            == ["WORKBENCH 1.5.0", "lisp65>"]
        and value.get("unlock") == {
            "D1_repeat": True, "D2_D5": False,
            "condition": (
                "owner confirms all three physical liveness lines and "
                "terminal banner/prompt")}
        and value.get("successor_media_authority")
            == MEDIA.relative_to(ROOT).as_posix()
        and value.get("identity", {}).get("product_medium")
            == media["regenerated_contract_members"]["product_D81"]["path"]
        and value.get("identity", {}).get("library_medium")
            == media["library"]["D81"]["path"]
        and media.get("status")
            == "V150-LINK97-STAGER-LIVENESS-MEDIA-GREEN; FRESH-D1-PENDING"
        and media["actual_packed_ELF_gate"]["result"]
            == "passed-actual-linked-stager-prefix"
        and media["actual_packed_ELF_gate"]["screen_bytes_hex"]
            == (SIGNS[0] + " " * 7).encode().hex(),
        "fresh D1 contract/media authority drift")
    return value


def runner_gate(source_override: str | None = None) -> dict[str, Any]:
    source = source_override or RUNNER.read_text(encoding="utf-8")
    require(
        "dry-run|stage|recover-terminal|confirm-liveness" in source
        and "wait-row" not in source and "capture-final" not in source
        and 'sleep "$(jq -r \'.access_free_seconds\' "$CONFIG")"' in source
        and source.count("ftp_bundle_under_basic") == 2
        and 'cmp "$product" "$OUT/product-readback.d81"' in source
        and 'cmp "$library" "$OUT/library-readback.d81"' in source
        and "# PRODUCT-LIVE-BEGIN" in source
        and "# PRODUCT-LIVE-END" in source
        and "owner-visible-signs-confirmed" in source
        and "python3 \"$PY\" record" in source,
        "fresh D1 runner lifecycle token absent")
    live = source.split("# PRODUCT-LIVE-BEGIN", 1)[1].split(
        "# PRODUCT-LIVE-END", 1)[0]
    require(
        "mega65_ftp" not in live and "$FTP" not in live
        and "run_m65" not in live and "capture_screen" not in live
        and live.count("sleep") == 1,
        "fresh D1 liveness window admits device observation or FTP")
    confirm = source.split('if [ "$ACTION" = confirm-liveness ]; then', 1)[1]
    require(
        all(f"grep -Fqx '{sign}'" in confirm for sign in SIGNS)
        and "owner-visible-signs-confirmed" in confirm
        and "terminal-banner-and-prompt-proven" in confirm,
        "fresh D1 confirmation can omit a visible sign or terminal state")
    recover = source.split('if [ "$ACTION" = recover-terminal ]; then', 1)[1]
    recover = recover.split("\nfi\n", 1)[0]
    require(
        "verify-terminal" in recover and "capture_screen" not in recover
        and "run_m65" not in recover and "$FTP" not in recover,
        "fresh D1 terminal rescue can touch the device")
    return {"result": "passed", "access_free_seconds": 45,
            "pre_terminal_device_accesses": 0, "post_boot_FTP": 0,
            "D2_D5_actions": 0, "owner_visible_signs": len(SIGNS)}


def rejected_mutations(config: dict[str, Any], source: str) -> list[str]:
    cases: dict[str, Callable[[], None]] = {}

    def config_case(name: str, mutate: Callable[[dict[str, Any]], None]) -> None:
        def run() -> None:
            value = deepcopy(config); mutate(value); contract(value)
        cases[name] = run

    config_case("drop-staging-sign", lambda x: x[
        "required_visible_liveness"].pop(0))
    config_case("shorten-access-free-window", lambda x: x.update(
        access_free_seconds=20))
    config_case("reuse-predecessor-medium", lambda x: x["identity"].update(
        product_medium=(
            "build/c2.3/v1.5.0-candidate-media-link97/shared-system/"
            "lisp65-product.d81")))
    config_case("open-D2-before-D1", lambda x: x["unlock"].update(D2_D5=True))

    source_cases = {
        "observe-liveness-window": source.replace(
            '# PRODUCT-LIVE-BEGIN: no access while all three physical signs pass.\n'
            '  sleep',
            '# PRODUCT-LIVE-BEGIN: no access while all three physical signs pass.\n'
            '  capture_screen forbidden\n  sleep', 1),
        "skip-product-readback": source.replace(
            '  cmp "$product" "$OUT/product-readback.d81"\n', "", 1),
        "skip-library-readback": source.replace(
            '  cmp "$library" "$OUT/library-readback.d81"\n', "", 1),
        "omit-staging-owner-confirmation": source.replace(
            "  grep -Fqx 'LISP65: STAGING MEDIA' \"$OUT/owner-visible-signs.txt\"\n",
            "", 1),
    }
    for name, candidate in source_cases.items():
        cases[name] = lambda candidate=candidate: runner_gate(candidate)

    rejected: list[str] = []
    for name, run in cases.items():
        try:
            run()
        except D1Error:
            rejected.append(name)
    require(rejected == list(cases), "fresh D1 mutation survived")
    return rejected


def derive_preparation() -> dict[str, Any]:
    config = contract()
    source = RUNNER.read_text(encoding="utf-8")
    runner = runner_gate(source)
    rejected = rejected_mutations(config, source)
    relative_capture_binding = bind(CONFIG.relative_to(ROOT))
    require(relative_capture_binding == bind(CONFIG),
            "relative stopped-artifact binding is not workspace-normalized")
    authority = {
        "approval": {"commit": "739c5436"},
        "successor_media": bind(MEDIA), "config": bind(CONFIG),
        "runner": bind(RUNNER), "checker": bind(Path(__file__)),
        "predecessor_session_preparation": bind(PREDECESSOR_PREP),
    }
    if FIRST_RED.exists():
        authority["first_red"] = bind(FIRST_RED)
    return {
        "format": FORMAT, "recorded_on": "2026-08-11", "status": STATUS,
        "authority": authority,
        "runner_gate": runner,
        "path_binding_gate": {
            "result": "passed-relative-and-absolute-same-artifact",
            "relative_fixture": CONFIG.relative_to(ROOT).as_posix(),
            "binding": relative_capture_binding,
        },
        "required_visible_liveness": SIGNS,
        "required_terminal_state": config["required_terminal_state"],
        "mutations_rejected": rejected,
        "execution_accounting": {"hardware_contacts": 0, "forms": 0,
                                 "product_links": 0, "WPLTO_runs": 0},
        "unlock": {"D1_repeat": True, "D2_D5": False},
        "claim_limit": (
            "Fresh physical D1 preparation only. D2-D5 remain closed until "
            "the owner confirms all three visible signs and terminal state."),
    }


def validate_preparation(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and value.get("required_visible_liveness") == SIGNS
        and value.get("runner_gate", {}).get("pre_terminal_device_accesses") == 0
        and value.get("runner_gate", {}).get("D2_D5_actions") == 0
        and value.get("path_binding_gate", {}).get("result")
            == "passed-relative-and-absolute-same-artifact"
        and len(value.get("mutations_rejected", [])) == 8
        and value.get("execution_accounting") == {
            "hardware_contacts": 0, "forms": 0,
            "product_links": 0, "WPLTO_runs": 0}
        and value.get("unlock") == {"D1_repeat": True, "D2_D5": False},
        "fresh D1 preparation claim drift")
    if verify:
        require(value == derive_preparation(), "fresh D1 preparation stale")


def verify_terminal(text: Path, image: Path) -> dict[str, Any]:
    SCREEN.check_fail_closed_frame(image)
    raw = text.read_text(encoding="utf-8", errors="replace")
    require("WORKBENCH 1.5.0" in raw and "lisp65>" in raw,
            "fresh D1 terminal banner/prompt absent")
    return {"result": "passed", "text": bind(text), "image": bind(image)}


def derive_result() -> dict[str, Any]:
    prep = load(PREP); validate_preparation(prep, verify=True)
    require((OUT / "owner-visible-signs-confirmed").is_file(),
            "owner liveness confirmation absent")
    signs = (OUT / "owner-visible-signs.txt").read_text(
        encoding="utf-8").splitlines()
    require(signs == SIGNS, "owner liveness confirmation vocabulary drift")
    terminal = verify_terminal(OUT / "product-boot.txt", OUT / "product-boot.png")
    return {
        "format": "lisp65-c2.3-v150-link97-stager-liveness-d1-v1",
        "recorded_on": "2026-08-11",
        "status": "V150-LINK97-STAGER-LIVENESS-D1-GREEN",
        "authority": {"preparation": bind(PREP), "media": bind(MEDIA)},
        "physical_observation": {"visible_liveness": signs,
                                 "terminal": terminal},
        "execution_accounting": {"hardware_contacts": 1, "forms": 0,
                                 "product_links": 0, "WPLTO_runs": 0},
        "unlock": {"D2_D5": True, "requires_successor_session_rebind": True},
        "claim_limit": (
            "Fresh D1 boot-liveness acceptance only. D2-D5 have not run."),
    }


def rebind_after_first_red() -> None:
    require(PREP.is_file() and not FIRST_RED.exists(),
            "fresh D1 First Red/rebind state invalid")
    old = load(PREP)
    capture_text = OUT / "product-boot.txt"
    capture_image = OUT / "product-boot.png"
    require(capture_text.is_file() and capture_image.is_file(),
            "fresh D1 terminal capture absent for First Red")
    first_red = {
        "format": "lisp65-c2.3-v150-link97-stager-liveness-d1-first-red-v1",
        "recorded_on": "2026-08-11",
        "status": "FIRST-RED-HOST-PATH-NORMALIZATION-AFTER-VALID-D1-CAPTURE",
        "authority": {
            "approval": {"commit": "739c5436"},
            "old_preparation_sha256": hashlib.sha256(
                PREP.read_bytes()).hexdigest(),
            "old_checker": old["authority"]["checker"],
            "media": bind(MEDIA),
        },
        "evidence": {
            "terminal_text": bind(capture_text),
            "terminal_image": bind(capture_image),
            "terminal_contains": ["WORKBENCH 1.5.0", "lisp65>"],
            "owner_reported_visible_liveness": SIGNS,
            "failure": (
                "relative product-boot.txt was passed to bind(), whose "
                "relative_to(ROOT) assumed an absolute path"),
        },
        "execution_accounting": {"hardware_contacts": 1, "forms": 0,
                                 "product_links": 0, "WPLTO_runs": 0},
        "claim_limit": (
            "Host checker First Red after the sole allowed terminal capture. "
            "D1 is not green until read-only rescue and owner confirmation."),
    }
    FIRST_RED.write_bytes(canonical(first_red))
    value = derive_preparation(); validate_preparation(value, verify=False)
    PREP.write_bytes(canonical(value))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "rebind", "check",
                                           "selftest", "verify-terminal",
                                           "record"))
    parser.add_argument("--text", type=Path)
    parser.add_argument("--image", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        require(not PREP.exists(), "fresh D1 preparation already exists")
        value = derive_preparation(); validate_preparation(value, verify=False)
        PREP.parent.mkdir(parents=True, exist_ok=True)
        PREP.write_bytes(canonical(value))
        print("v1.5 stager-liveness D1 preparation: PASS mutations=8")
    elif args.action == "rebind":
        rebind_after_first_red()
        print("v1.5 stager-liveness D1 First Red bound; preparation rebound")
    elif args.action == "check":
        value = load(PREP); validate_preparation(value, verify=True)
        print("v1.5 stager-liveness D1 check: PASS mutations=8")
    elif args.action == "selftest":
        value = derive_preparation(); validate_preparation(value, verify=False)
        print("v1.5 stager-liveness D1 selftest: PASS mutations=8")
    elif args.action == "verify-terminal":
        require(args.text is not None and args.image is not None,
                "verify-terminal requires --text and --image")
        verify_terminal(args.text, args.image)
        print("v1.5 stager-liveness D1 terminal: PASS")
    else:
        require(not RESULT.exists(), "fresh D1 result already exists")
        result = derive_result(); RESULT.write_bytes(canonical(result))
        print("v1.5 stager-liveness D1: PASS D2-D5 successor rebind pending")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (D1Error, SCREEN.CheckError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        message = error.message if isinstance(error, SCREEN.CheckError) else str(error)
        print(f"v1.5 stager-liveness D1: FIRST RED: {message}", file=sys.stderr)
        raise SystemExit(2)
