#!/usr/bin/env python3
"""Bind the Link-92 Phase-D conditional defstruct device row."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import repl_screen_check as SCREEN  # noqa: E402

CONFIG = ROOT / "config/c2-v112-link92-phase-d-d2.json"
SCRIPT = ROOT / "scripts/c2-v112-link92-phase-d-d2-hw.sh"
GATES = ROOT / "mk/gates.mk"
PREP = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-link92-r5-phase-d-d2-preparation-receipt.json")
RESULT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-link92-r5-phase-d-d2-device-receipt.json")
OUT = Path(os.environ.get(
    "OUT", ROOT / "build/c2.3/v1.4.0-release/phase-d-split/d2"))
if not OUT.is_absolute():
    OUT = ROOT / OUT


class D2Error(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise D2Error(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"artifact absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def validate_contract(value: dict[str, Any]) -> None:
    require(value.get("format") == "lisp65-c2-v112-link92-phase-d-d2-v1",
            "D2 format drift")
    d3 = value.get("D3_authority", {})
    require(d3.get("status") ==
            "passed-D3-three-split-library-names-and-physical-editor-64-of-64",
            "D2 D3 authority drift")
    identity = value.get("identity", {})
    medium = ROOT / identity.get("library_medium", {}).get("path", "")
    require(medium.is_file()
            and identity["library_medium"].get("bytes") == medium.stat().st_size
            and identity["library_medium"].get("sha256") == sha(medium)
            and "defstruct-acceptance" in medium.as_posix(),
            "D2 sibling-medium identity drift")
    product = ROOT / identity.get("product", {}).get("path", "")
    require(product.is_file()
            and identity["product"].get("sha256") == sha(product)
            and identity["product"].get("sha256") ==
            "fcc785365d2a6d7a3269367a4234cb372783d46b9debdee6ad37e758f6e20a52",
            "D2 immutable product identity drift")
    preloads = identity.get("preloads", [])
    require(len(preloads) == 7 and preloads[0].get("bytes") == 50816
            and preloads[0].get("address") == "0x00050000",
            "D2 reset-domain/preload closure drift")
    require(identity.get("boot_quiet_seconds") == 45
            and identity.get("banner") == "WORKBENCH 1.4.0"
            and identity.get("prompt") == "lisp65>",
            "D2 boot observation contract drift")
    row = value.get("row", {})
    require(row == {
        "require_form": "(require 'defstruct)",
        "require_expect": "t",
        "definition_form": "(defstruct point x y)",
        "quiet_floor_seconds": 180,
        "observations_during_quiet_window": 0,
        "make_form": "(make-point 3 4)",
        "make_expect": "(point 3 4)",
        "owner_physical_input_only": True,
        "structural_price_seconds": 179,
        "structural_price_is_completion_upper_bound": False,
    }, "D2 conditional row drift")


def validate_authorities(value: dict[str, Any]) -> None:
    d3 = load(ROOT / value["D3_authority"]["path"])
    require(d3.get("status") == value["D3_authority"]["status"],
            "D2 D3 receipt authority drift")
    identity = value["identity"]
    for item in [identity["library_medium"], identity["product"],
                 *identity["preloads"]]:
        path = ROOT / item["path"]
        require(path.stat().st_size == item["bytes"] and sha(path) == item["sha256"],
                f"D2 artifact binding drift: {item['path']}")
    c2j = identity["c2j_clear"]
    c2j_path = ROOT / c2j["authority"]
    require(c2j_path.read_bytes() == bytes(c2j["bytes"])
            and sha(c2j_path) == c2j["sha256"], "D2 C2J CLEAR authority drift")
    reset = (ROOT / identity["preloads"][0]["path"]).read_bytes()
    require(reset[33840:] == bytes(16976)
            and reset[0xC640:0xC680] == bytes(64),
            "D2 reset domain lacks the complete CLEAR suffix")


def action_block(source: str, action: str) -> str:
    begin, end = f"# {action}-BEGIN", f"# {action}-END"
    require(source.count(begin) == source.count(end) == 1,
            f"D2 {action} ownership markers drift")
    return source.split(begin, 1)[1].split(end, 1)[0]


def validate_script(source: str) -> None:
    start = action_block(source, "START-D2")
    wait = action_block(source, "WAIT-D2")
    capture = action_block(source, "CAPTURE-GREEN")
    ordered = ["fresh_start", "ftp_library", "load_identity"]
    require(all(token in start for token in ordered)
            and [start.index(token) for token in ordered]
            == sorted(start.index(token) for token in ordered),
            "D2 start order drift")
    for token in ('cmp "$media" "$readback_path"',
                  'cmp "$path" "$OUT/D2-preload-$role.bin"',
                  'cmp "$c2j_authority" "$OUT/D2-c2j-before-run.bin"'):
        require(token in source, f"D2 staging proof absent: {token}")
    require("sleep \"$quiet\"" in wait
            and "run_m65" not in wait and "capture_screen" not in wait
            and "readback" not in wait and "mega65_ftp" not in wait,
            "D2 quiet wait contains device observation")
    require("capture_screen D2-final" in capture
            and 'python3 "$PY" result-green' in capture,
            "D2 green postcondition capture drift")
    require("hw-jtag-repl" not in start and "typing text" not in start,
            "D2 start acquired virtual owner input")


def rejected_mutations(value: dict[str, Any], source: str) -> list[str]:
    result: list[str] = []

    def mutate(name: str, change: Callable[[dict[str, Any]], None]) -> None:
        candidate = deepcopy(value); change(candidate)
        try: validate_contract(candidate)
        except D2Error: result.append(name)
        else: raise D2Error(f"D2 contract mutation survived: {name}")

    mutate("base-medium-substituted", lambda x: x["identity"]["library_medium"].update(
        path="build/c2.3/v1.4.0-candidate-media-link92-r5-split/base/lisp65-library.d81"))
    mutate("product-drift", lambda x: x["identity"]["product"].update(sha256="00" * 32))
    mutate("prefix-reset-domain", lambda x: x["identity"]["preloads"][0].update(bytes=33840))
    mutate("early-boot-look", lambda x: x["identity"].update(boot_quiet_seconds=20))
    mutate("require-form-drift", lambda x: x["row"].update(require_form="(require defstruct)"))
    mutate("definition-drift", lambda x: x["row"].update(definition_form="(defstruct p x)"))
    mutate("quiet-floor-dimmed", lambda x: x["row"].update(quiet_floor_seconds=179))
    mutate("quiet-observation", lambda x: x["row"].update(observations_during_quiet_window=1))
    mutate("virtual-input-enabled", lambda x: x["row"].update(owner_physical_input_only=False))
    mutate("price-promoted-to-upper-bound", lambda x: x["row"].update(
        structural_price_is_completion_upper_bound=True))
    mutate("make-oracle-dimmed", lambda x: x["row"].update(make_expect="point"))
    mutations = {
        "early-device-read": source.replace(
            'sleep "$quiet"', 'capture_screen bad\nsleep "$quiet"', 1),
        "library-readback-removed": source.replace(
            'cmp "$media" "$readback_path"', ': # compare removed', 1),
        "C2J-proof-removed": source.replace(
            'cmp "$c2j_authority" "$OUT/D2-c2j-before-run.bin"',
            ': # compare removed', 1),
        "virtual-input-added": source.replace(
            "# START-D2-BEGIN\nfresh_start",
            "# START-D2-BEGIN\nscripts/hw-jtag-repl.sh --form bad\nfresh_start",
            1),
    }
    for name, candidate in mutations.items():
        try: validate_script(candidate)
        except D2Error: result.append(name)
        else: raise D2Error(f"D2 script mutation survived: {name}")
    require(len(result) == 15, "D2 mutation count drift")
    return result


def evaluate(*, write: bool) -> dict[str, Any]:
    value = load(CONFIG); validate_contract(value); validate_authorities(value)
    source = SCRIPT.read_text(encoding="utf-8"); validate_script(source)
    gates = GATES.read_text(encoding="utf-8")
    require("c2-v112-phase-d-d2-selftest:" in gates
            and "c2_v112_phase_d_d2.py selftest" in gates
            and "check-source: c2-v112-phase-d-d2-selftest" in gates,
            "D2 permanent gate registration drift")
    rejected = rejected_mutations(value, source)
    result = {
        "format": "lisp65-c2.3-v1.12-link92-r5-phase-d-d2-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status": "passed-D2-conditional-defstruct-device-row-ready",
        "bindings": {"config": bind(CONFIG), "runner": bind(SCRIPT),
                     "D3_authority": bind(ROOT / value["D3_authority"]["path"]),
                     "C2J_CLEAR_authority": bind(
                         ROOT / value["identity"]["c2j_clear"]["authority"])},
        "identity": value["identity"], "row": value["row"],
        "mutations_rejected": rejected, "mutation_count": len(rejected),
        "execution_accounting": {"hardware_contacts": 0, "D2_rows": 0},
        "claim_limit": value["claim_limit"],
    }
    if write:
        PREP.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    return result


def result_green() -> dict[str, Any]:
    prep = load(PREP)
    require(prep.get("status") == "passed-D2-conditional-defstruct-device-row-ready",
            "D2 preparation authority drift")
    value = load(CONFIG); validate_contract(value)
    started = int((OUT / "quiet-start-epoch").read_text().strip())
    completed = int((OUT / "quiet-complete-epoch").read_text().strip())
    require(completed - started >= value["row"]["quiet_floor_seconds"],
            "D2 final observation preceded quiet floor")
    SCREEN.check_latest_result(OUT / "D2-final.txt", value["row"]["make_form"],
                               value["row"]["make_expect"])
    SCREEN.check_fail_closed_frame(OUT / "D2-final.png")
    result = {
        "format": "lisp65-c2.3-v1.12-link92-r5-phase-d-d2-device-v1",
        "recorded_on": date.today().isoformat(),
        "status": "passed-D2-defstruct-and-make-point-target",
        "quiet": {"start_epoch": started, "complete_epoch": completed,
                  "elapsed_seconds": completed - started,
                  "automated_observations": 0},
        "forms": value["row"],
        "bindings": {"preparation": bind(PREP),
                     "library_readback": bind(OUT / "D2-library-readback.d81"),
                     "boot_screen": bind(OUT / "D2-boot.png"),
                     "final_screen": bind(OUT / "D2-final.png"),
                     "final_text": bind(OUT / "D2-final.txt")},
        "selector": "D2-green",
        "execution_accounting": {"hardware_contacts": 1, "D2_rows": 1,
                                 "product_rebuilds": 0, "additional_links": 0},
        "claim_limit": value["claim_limit"],
    }
    RESULT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    return result


def result_red() -> dict[str, Any]:
    prep = load(PREP)
    require(prep.get("status") == "passed-D2-conditional-defstruct-device-row-ready",
            "D2 preparation authority drift")
    require(not RESULT.exists(), "D2 device result already exists")
    value = load(CONFIG); validate_contract(value)
    started = int((OUT / "quiet-start-epoch").read_text().strip())
    completed = int((OUT / "quiet-complete-epoch").read_text().strip())
    require(completed - started >= value["row"]["quiet_floor_seconds"],
            "D2 owner observation preceded quiet floor")
    require((OUT / "require-owner-confirmed").is_file()
            and (OUT / "definition-owner-confirmed").is_file(),
            "D2 physical-input owner confirmations incomplete")
    result = {
        "format": "lisp65-c2.3-v1.12-link92-r5-phase-d-d2-device-v1",
        "recorded_on": date.today().isoformat(),
        "status": "D2-red-defstruct-not-selected-after-quiet-floor",
        "quiet": {"start_epoch": started, "complete_epoch": completed,
                  "elapsed_seconds": completed - started,
                  "automated_observations": 0},
        "physical_owner_observation": {
            "require_result": "t",
            "definition_form_submitted": True,
            "first_look_after_floor": True,
            "visible_prompt": False,
            "visible_red_frame": True,
            "make_point_run": False,
        },
        "forms": value["row"],
        "bindings": {"preparation": bind(PREP),
                     "library_readback": bind(OUT / "D2-library-readback.d81"),
                     "boot_screen": bind(OUT / "D2-boot.png"),
                     "require_confirmation": bind(OUT / "require-owner-confirmed"),
                     "definition_confirmation": bind(
                         OUT / "definition-owner-confirmed")},
        "selector": "base",
        "defstruct_public": False,
        "execution_accounting": {"hardware_contacts": 1, "D2_rows": 1,
                                 "post_definition_monitor_accesses": 0,
                                 "product_rebuilds": 0, "additional_links": 0},
        "claim_limit": (
            "D2 delivery red only: after the valid quiet floor the owner saw "
            "no prompt and a red frame. defstruct remains undelivered. This is "
            "not an infinite-hang, new correctness, or failure-mechanism claim."
        ),
    }
    RESULT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "prepare", "selftest",
                                           "dry-run", "result-green", "result-red"))
    args = parser.parse_args()
    try:
        if args.action == "result-green":
            value = result_green()
            print("c2-v112-phase-d-d2: PASS " + value["status"])
        elif args.action == "result-red":
            value = result_red()
            print("c2-v112-phase-d-d2: PASS " + value["status"])
        else:
            value = evaluate(write=args.action == "prepare")
            print("c2-v112-phase-d-d2: PASS "
                  f"mutations={value['mutation_count']} quiet=180s physical=3")
        return 0
    except (D2Error, SCREEN.CheckError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"c2-v112-phase-d-d2: FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
