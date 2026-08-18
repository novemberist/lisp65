#!/usr/bin/env python3
"""Continue the green stager-liveness D1 session through v1.5 D2-D5."""

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
import c2_v150_device_session as BASE  # noqa: E402
import repl_screen_check as SCREEN  # noqa: E402


CONFIG = ROOT / "config/c2-v150-link97-stager-liveness-d2-d5.json"
RUNNER = ROOT / "scripts/c2-v150-link97-stager-liveness-d2-d5-hw.sh"
D1 = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-link97-stager-liveness-d1-receipt.json")
MEDIA = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-link97-stager-liveness-media-receipt.json")
PREP = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-link97-stager-liveness-d2-d5-preparation-receipt.json")
RESULT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-link97-stager-liveness-d2-d5-receipt.json")
OUT = ROOT / "build/c2.3/v1.5.0-link97-stager-liveness-d2-d5"
FORMAT = "lisp65-c2.3-v150-link97-stager-liveness-d2-d5-preparation-v1"
STATUS = "V150-LINK97-D2-D5-CONTINUATION-PREPARED-NOT-RUN"


class ContinuationError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ContinuationError(message)


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


def rows() -> list[dict[str, Any]]:
    return BASE.rows_contract()


def contract(value: dict[str, Any] | None = None) -> dict[str, Any]:
    value = value or load(CONFIG)
    d1 = load(D1); media = load(MEDIA)
    require(
        value.get("format") == "lisp65-c2-v150-link97-stager-liveness-d2-d5-v1"
        and value.get("status") == "prepared-not-run"
        and value.get("order") == ["D2", "D3", "D4", "D5"]
        and value.get("D1_authority") == D1.relative_to(ROOT).as_posix()
        and value.get("rows_authority") == BASE.ROWS.relative_to(ROOT).as_posix()
        and value.get("unlock") == {
            "D1_green_required": True, "post_boot_FTP": False,
            "product_reboot": False}
        and d1.get("status") == "V150-LINK97-STAGER-LIVENESS-D1-GREEN"
        and d1.get("unlock", {}).get("D2_D5") is True
        and len(d1["physical_observation"]["visible_liveness"]) == 3
        and value.get("identity", {}).get("product_medium")
            == media["regenerated_contract_members"]["product_D81"]["path"]
        and value.get("identity", {}).get("library_medium")
            == media["library"]["D81"]["path"]
        and len(rows()) == 19,
        "D2-D5 continuation contract/D1 authority drift")
    return value


def runner_gate(source_override: str | None = None) -> dict[str, Any]:
    source = source_override or RUNNER.read_text(encoding="utf-8")
    require(
        "dry-run|confirm-library|wait-row|capture-final" in source
        and "mega65_ftp" not in source and "ftp_bundle" not in source
        and "stage)" not in source and "run_m65 -F" not in source
        and "# ACTIVE-FORM-BEGIN" in source
        and "# ACTIVE-FORM-END" in source
        and source.count('python3 "$PY" verify-guard') == 2
        and "D1_GREEN" in source and "library-owner-confirmed" in source,
        "D2-D5 continuation runner scope token drift")
    active = source.split("# ACTIVE-FORM-BEGIN", 1)[1].split(
        "# ACTIVE-FORM-END", 1)[0]
    require(
        "$M65" not in active and "capture_screen" not in active
        and "sleep" in active,
        "D2-D5 active form window admits an observer")
    confirm = source.split('if [ "$ACTION" = confirm-library ]; then', 1)[1]
    confirm = confirm.split("\nfi\n", 1)[0]
    require(
        "WORKBENCH 1.5.0" in confirm and "lisp65>" in confirm
        and "D1_GREEN=$(jq -r '.status' \"$D1\")" in confirm
        and "V150-LINK97-STAGER-LIVENESS-D1-GREEN" in confirm,
        "D2-D5 continuation can bypass green D1 or idle REPL")
    return {"result": "passed", "physical_rows": 19,
            "post_boot_FTP": 0, "product_reboots": 0,
            "active_form_observations": 0, "guard_readbacks": 2}


def rejected_mutations(config: dict[str, Any], source: str) -> list[str]:
    cases: dict[str, Callable[[], None]] = {}

    def config_case(name: str, mutate: Callable[[dict[str, Any]], None]) -> None:
        def run() -> None:
            value = deepcopy(config); mutate(value); contract(value)
        cases[name] = run

    config_case("drop-D1-authority", lambda x: x.update(D1_authority="missing"))
    config_case("permit-post-boot-FTP", lambda x: x["unlock"].update(
        post_boot_FTP=True))
    config_case("permit-product-reboot", lambda x: x["unlock"].update(
        product_reboot=True))
    config_case("reuse-predecessor-product", lambda x: x["identity"].update(
        product_medium=(
            "build/c2.3/v1.5.0-candidate-media-link97/shared-system/"
            "lisp65-product.d81")))
    source_cases = {
        "observe-active-form": source.replace(
            '  sleep "$quiet"\n  # ACTIVE-FORM-END',
            '  capture_screen forbidden\n  sleep "$quiet"\n'
            '  # ACTIVE-FORM-END', 1),
        "add-FTP": source.replace(
            "# NO-POST-BOOT-FTP", "mega65_ftp forbidden", 1),
        "drop-guard-readback": source.replace(
            '    python3 "$PY" verify-guard --path '
            '"$OUT/d3-terminal-return-guard.bin"',
            "    : # guard readback removed", 1),
        "drop-D1-marker": source.replace(
            '  D1_GREEN=$(jq -r \'.status\' "$D1")\n',
            "  D1_GREEN=assumed\n", 1),
    }
    for name, candidate in source_cases.items():
        cases[name] = lambda candidate=candidate: runner_gate(candidate)
    rejected: list[str] = []
    for name, run in cases.items():
        try:
            run()
        except ContinuationError:
            rejected.append(name)
    require(
        rejected == list(cases),
        "D2-D5 continuation mutation survived: "
        + ", ".join(name for name in cases if name not in rejected))
    return rejected


def derive_preparation() -> dict[str, Any]:
    config = contract(); source = RUNNER.read_text(encoding="utf-8")
    runner = runner_gate(source)
    rejected = rejected_mutations(config, source)
    return {
        "format": FORMAT, "recorded_on": "2026-08-11", "status": STATUS,
        "authority": {
            "D1": bind(D1), "successor_media": bind(MEDIA),
            "config": bind(CONFIG), "rows": bind(BASE.ROWS),
            "release_contract": bind(BASE.CONTRACT), "runner": bind(RUNNER),
            "checker": bind(Path(__file__)),
        },
        "session": {"order": ["D2", "D3", "D4", "D5"], **runner},
        "mutations_rejected": rejected,
        "execution_accounting": {"new_hardware_contacts": 0, "forms": 0,
                                 "product_links": 0, "WPLTO_runs": 0},
        "claim_limit": (
            "Continuation of the already green D1 session only. No reboot, "
            "FTP, D2-D5 hardware or release claim."),
    }


def validate_preparation(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and value.get("session", {}).get("order") == ["D2", "D3", "D4", "D5"]
        and value.get("session", {}).get("physical_rows") == 19
        and value.get("session", {}).get("post_boot_FTP") == 0
        and value.get("session", {}).get("product_reboots") == 0
        and len(value.get("mutations_rejected", [])) == 8
        and value.get("execution_accounting") == {
            "new_hardware_contacts": 0, "forms": 0,
            "product_links": 0, "WPLTO_runs": 0},
        "D2-D5 continuation preparation claim drift")
    if verify:
        require(value == derive_preparation(),
                "D2-D5 continuation preparation stale")


def verify_row(row_id: str, text: Path, image: Path) -> dict[str, Any]:
    try:
        return BASE.verify_row(row_id, text, image)
    except BASE.SessionError as error:
        raise ContinuationError(str(error)) from error


def verify_guard(path: Path) -> dict[str, Any]:
    try:
        return BASE.verify_guard(path)
    except BASE.SessionError as error:
        raise ContinuationError(str(error)) from error


def derive_result() -> dict[str, Any]:
    prep = load(PREP); validate_preparation(prep, verify=True)
    require((OUT / "final-capture-complete").is_file(),
            "D2-D5 final stopped-state capture absent")
    results = [verify_row(
        row["id"], OUT / f"row-{row['id']}.txt",
        OUT / f"row-{row['id']}.png") for row in rows()]
    guard = verify_guard(OUT / "final-terminal-return-guard.bin")
    return {
        "format": "lisp65-c2.3-v150-link97-stager-liveness-d2-d5-v1",
        "recorded_on": "2026-08-11",
        "status": "V150-LINK97-D1-D5-HARDWARE-GREEN; OWNER-HALT-1-PENDING",
        "authority": {"preparation": bind(PREP), "D1": bind(D1),
                      "media": bind(MEDIA)},
        "rows": results, "D3_guard": guard,
        "execution_accounting": {"hardware_contacts_total": 1,
                                 "physical_forms": 19,
                                 "post_boot_FTP": 0,
                                 "product_reboots_after_D1": 0,
                                 "final_stops": 1},
        "next": "owner-halt-1",
        "claim_limit": (
            "D1-D5 hardware acceptance only. Publication remains behind "
            "owner Halt #1 and Publish-Go."),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "check", "selftest",
                                           "verify-row", "verify-guard",
                                           "record"))
    parser.add_argument("--row")
    parser.add_argument("--text", type=Path)
    parser.add_argument("--image", type=Path)
    parser.add_argument("--path", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        require(not PREP.exists(), "D2-D5 continuation preparation exists")
        value = derive_preparation(); validate_preparation(value, verify=False)
        PREP.parent.mkdir(parents=True, exist_ok=True)
        PREP.write_bytes(canonical(value))
        print("v1.5 D2-D5 continuation preparation: PASS mutations=8")
    elif args.action == "check":
        value = load(PREP); validate_preparation(value, verify=True)
        print("v1.5 D2-D5 continuation check: PASS mutations=8")
    elif args.action == "selftest":
        value = derive_preparation(); validate_preparation(value, verify=False)
        print("v1.5 D2-D5 continuation selftest: PASS mutations=8")
    elif args.action == "verify-row":
        require(args.row is not None and args.text is not None and args.image,
                "verify-row requires --row/--text/--image")
        result = verify_row(args.row, args.text, args.image)
        print(f"v1.5 row {args.row}: PASS {result['values']}")
    elif args.action == "verify-guard":
        require(args.path is not None, "verify-guard requires --path")
        result = verify_guard(args.path)
        print(f"v1.5 guard: PASS {result['raw_hex']}")
    else:
        require(not RESULT.exists(), "D2-D5 continuation result exists")
        result = derive_result(); RESULT.write_bytes(canonical(result))
        print("v1.5 D1-D5 result: PASS owner-halt-1-pending")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ContinuationError, BASE.SessionError, SCREEN.CheckError,
            OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        message = error.message if isinstance(error, SCREEN.CheckError) else str(error)
        print(f"v1.5 D2-D5 continuation: FIRST RED: {message}", file=sys.stderr)
        raise SystemExit(2)
