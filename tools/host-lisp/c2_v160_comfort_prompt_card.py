#!/usr/bin/env python3
"""Build and qualify the authorized v1.6 Comfort prompt library card."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
SOURCE = ROOT / "lib/repl-comfort.lisp"
EDITOR = ROOT / "lib/stdlib-read-line.lisp"
SUITE = ROOT / "tests/bytecode/libs/p0-repl-comfort.json"
LIVENESS = ARCH / (
    "c2.3-v1.6-active-frame-liveness-acceptance-resume-receipt.json")
PRODUCT_ELF = (ROOT / ("build/c2.3/v1.6-active-frame-liveness-third-"
               "replacement-card/wplto/") /
               "lisp65-c2-substitution-linked.prg.elf")
CAPACITY = ARCH / (
    "c2.3-v1.6-input-service-hybrid-phase-output-consumption-card-receipt.json")
HISTORICAL_PROMPT = ARCH / "c2.3-v1.6-comfort-prompt-current-card-receipt.json"
PREDECESSOR_MANIFEST = (ROOT / "build/c2.3/v1.6-comfort-prompt-current-card/"
                        "repl-comfort.manifest.json")
BUILD = ROOT / "build/c2.3/v1.6-comfort-prompt-l65-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-comfort-prompt-l65-preflight"
INVOCATION = PREFLIGHT / "card-invocation.json"
RECEIPT = ARCH / "c2.3-v1.6-comfort-prompt-l65-card-receipt.json"
CARD_RED = ARCH / "c2.3-v1.6-comfort-prompt-l65-card-final-red.json"
AUTHORIZATION = "8debd7b9"
PROMPT = "l65>"
PREDECESSOR_PROMPT = "comfort>"
PROMPT_CODES = [ord(char) for char in PROMPT] + [10]


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    commit = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("one small successor card", "prompt string only",
                  "now (v1.6): l65>", "distinct from the native lisp65>",
                  "bank-2 only", "no new names", "margin stays 33/601",
                  "per-key path untouched"):
        require(token in text, f"Comfort prompt authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    live = load(LIVENESS); capacity = load(CAPACITY)
    historical = load(HISTORICAL_PROMPT)
    claims = live["final_world_claims"]
    cap = capacity["corrected_capacity_world"]["capacity"]
    require(live["status"] ==
                "PASS: V1.6 ACTIVE-FRAME LIVENESS CLOSED READ-ONLY"
            and live["liveness_contract_closed"] is True
            and live["execution_witness"] == {"scope_acceptance_resumes": 1,
                "WPLTO_runs": 0, "product_links": 0, "cards_consumed": 0,
                "media_builds": 0, "device_contacts": 0}
            and claims["responsiveness"]["margin_percent"] > 29
            and claims["loss"]["linked_dropped"] == 0
            and cap["with_optional_reclaim"] == {
                "symbol_slots": 33, "namepool_bytes": 601}
            and cap["release_minimum"] == {
                "symbol_slots": 32, "namepool_bytes": 384}
            and historical["status"] == "PASS: V1.6 COMFORT PROMPT GREEN"
            and historical["source_gate"]["prompt"] == PREDECESSOR_PROMPT
            and historical["library"]["price"]["new_symbol_names"] == [],
            "prompt predecessor/liveness closure drift")
    return {"liveness": live, "claims": claims, "capacity": cap,
            "historical_prompt": historical}


def source_gate() -> dict[str, Any]:
    source = SOURCE.read_text(encoding="utf-8")
    editor = EDITOR.read_text(encoding="utf-8")
    prompt_form = f'(if (= depth 0) (write-line "{PROMPT}") nil)'
    require(source.count(prompt_form) == 1
            and source.index(prompt_form) < source.index("(%repl-read indent history 0)")
            and PROMPT not in source[source.index("(defun %repl-read"):source.index(
                "(defun %repl-step")]
            and PROMPT not in editor
            and PREDECESSOR_PROMPT not in source
            and "(< (car (nthcdr 4 state)) 250)" in editor,
            "Comfort prompt crossed the rendering/input boundary")
    suite = load(SUITE)
    cases = {row["name"]: row for row in suite["cases"]}
    top_level = ("comfort-balanced-expression", "comfort-multiline-balanced",
        "comfort-overclose-runs-nothing", "comfort-history-up",
        "comfort-cursor-down-empty-boundary", "comfort-string-parens-do-not-continue",
        "comfort-comment-parens-do-not-close")
    require(all(cases[name]["expect_output_codes"][:len(PROMPT_CODES)] == PROMPT_CODES
                for name in top_level)
            and cases["comfort-auto-indent-prefix"]["expect_output_codes"] == [10],
            "prompt/continuation output fixture boundary drift")
    return {"prompt": PROMPT, "prompt_codes": PROMPT_CODES,
        "top_level_only": True, "before_editor_entry": True,
        "input_buffer_bytes_added": 0, "history_bytes_added": 0,
        "parser_bytes_added": 0, "logical_line_limit": 250,
        "editor_source": bind(EDITOR), "cases_with_prompt": list(top_level),
        "continuation_prompt_absent": True}


def compile_library(root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=False)
    artifact = root / "repl-comfort"
    observation = root / "observations.json"
    command = [sys.executable, "tools/host-lisp/bytecode_p0_stdlib.py", "--check",
        "--artifact-role", "disk-lib", "--emit-artifacts",
        str(artifact.relative_to(ROOT)), "--observation-report",
        str(observation.relative_to(ROOT)), str(SUITE.relative_to(ROOT))]
    run = subprocess.run(command, cwd=ROOT, text=True,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(run.returncode == 0 and "bytecode-p0-stdlib-check: PASS" in run.stdout,
            "Comfort prompt executable suite red:\n" + run.stdout)
    manifest_path = artifact.with_suffix(".manifest.json")
    manifest = load(manifest_path); old = load(PREDECESSOR_MANIFEST)
    rows = {row["name"]: row["length"] for row in manifest["entries"]}
    old_rows = {row["name"]: row["length"] for row in old["entries"]}
    require(rows == {"%repl-read": 249, "%repl-step": 179, "repl": 189}
            and old_rows == rows
            and manifest["code_bytes"] == old["code_bytes"] == 617
            and manifest["cost"]["symbol_names"] == old["cost"]["symbol_names"]
            and manifest["cost"]["largest_code_object_bytes"] == 249 <= 255,
            "Comfort prompt price/symbol/object wall drift")
    return {"artifacts": {name: bind(path) for name, path in (
            ("manifest", manifest_path), ("blob", artifact.with_suffix(".blob.bin")),
            ("directory", artifact.with_suffix(".dir.bin")),
            ("observations", observation))},
        "price": {"bank5_code_before": 617, "bank5_code_after": 617,
            "bank5_delta_bytes": 0, "largest_object_bytes": 249,
            "object_limit_bytes": 255, "new_symbol_names": [],
            "changed_objects": ["%repl-step"],
            "unchanged_objects": {"%repl-read": 249, "repl": 189},
            "bias_adjusted_free_before": {"symbol_slots": 33,
                "namepool_bytes": 601},
            "bias_adjusted_free_after": {"symbol_slots": 33,
                "namepool_bytes": 601},
            "release_minimum": {"symbol_slots": 32,
                "namepool_bytes": 384},
            "remaining_margin": {"symbol_slots": 1,
                "namepool_bytes": 217},
            "margin_slot_spent": False,
            "public_prompt_before": PREDECESSOR_PROMPT,
            "public_prompt_after": PROMPT,
            "prompt_characters_saved": 4,
            "per_key_code_changed": False, "line_boundary_only": True},
        "suite": {"cases": len(load(SUITE)["cases"]), "status": "PASS"},
        "stdout_tail": " ".join(run.stdout.split()[-24:])}


def preflight() -> None:
    require(not any(path.exists() for path in (PREFLIGHT, BUILD, INVOCATION,
                                                RECEIPT, CARD_RED)),
            "Comfort prompt card is one-shot")
    pred = predecessor(); auth = authority(); source = source_gate()
    result = compile_library(PREFLIGHT)
    value = {"format": "lisp65-c2-v160-comfort-prompt-preflight-v1",
        "recorded_on": "2026-08-21", "status": "PASS: L65 PROMPT ARMED 0/1",
        "authority": auth, "liveness_closure": bind(LIVENESS),
        "capacity_authority": bind(CAPACITY),
        "historical_prompt_evidence": bind(HISTORICAL_PROMPT),
        "source_gate": source, "preflight_artifact": result,
        "product_world": bind(PRODUCT_ELF),
        "inherited_walls": {"responsiveness_margin_percent": pred["claims"]
            ["responsiveness"]["margin_percent"],
            "loss_dropped": 0, "normalization_parity": "256/256",
            "far_service_free_bytes": 37, "E000_surplus_over_floor": 6,
            "touched_resident_arenas": [],
            "reason": "prompt changes only the Bank-2 line-boundary object"},
        "execution": {"cards_consumed": 0, "WPLTO_runs": 0,
                      "product_links": 0, "media_builds": 0, "device_contacts": 0}}
    (PREFLIGHT / "preflight.json").write_bytes(canonical(value))
    print("v1.6 l65 prompt: PREFLIGHT PASS card=0/1 delta=0 names=0 "
          "slots=33 margin=1")


def card() -> None:
    require((PREFLIGHT / "preflight.json").is_file() and not BUILD.exists()
            and not INVOCATION.exists() and not RECEIPT.exists() and not CARD_RED.exists(),
            "Comfort prompt card lifecycle drift")
    pre = load(PREFLIGHT / "preflight.json")
    price = pre["preflight_artifact"]["price"]
    require(pre["status"] == "PASS: L65 PROMPT ARMED 0/1"
            and price["new_symbol_names"] == []
            and price["changed_objects"] == ["%repl-step"]
            and price["bias_adjusted_free_after"] == {
                "symbol_slots": 33, "namepool_bytes": 601}
            and price["remaining_margin"] == {
                "symbol_slots": 1, "namepool_bytes": 217}
            and price["margin_slot_spent"] is False,
            "Comfort prompt preflight drift")
    INVOCATION.write_bytes(canonical({"status": "INVOKED", "card": "prompt 1/1",
        "authority": authority(), "preflight": bind(PREFLIGHT / "preflight.json")}))
    before = {"product_ELF": bind(PRODUCT_ELF), "editor": bind(EDITOR)}
    result = compile_library(BUILD)
    require(result["price"] == price,
            "Comfort prompt real library consumer differs from preflight")
    after = {"product_ELF": bind(PRODUCT_ELF), "editor": bind(EDITOR)}
    require(before == after, "prompt library card changed product/editor world")
    value = {"format": "lisp65-c2-v160-comfort-prompt-card-v1",
        "recorded_on": "2026-08-21", "status": "PASS: V1.6 L65 PROMPT GREEN",
        "authority": authority(), "preflight": bind(PREFLIGHT / "preflight.json"),
        "liveness_closure": bind(LIVENESS), "capacity_authority": bind(CAPACITY),
        "source_gate": source_gate(),
        "library": result, "unchanged_world_before": before,
        "unchanged_world_after": after,
        "execution": {"cards_consumed": 1, "library_builds": 1,
            "WPLTO_runs": 0, "product_links": 0, "media_builds": 0,
            "device_contacts": 0},
        "next": "fresh same-world media and fourth owner acceptance contact"}
    RECEIPT.write_bytes(canonical(value))
    print("v1.6 l65 prompt: CARD PASS card=1/1 delta=0 names=0 "
          "slots=33 margin=1")


def record_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or CARD_RED.exists():
        return
    CARD_RED.write_bytes(canonical({"format": "lisp65-c2-v160-comfort-prompt-final-red-v1",
        "recorded_on": "2026-08-21", "status": "FINAL RED: COMFORT PROMPT STOPS",
        "error": {"type": type(error).__name__, "message": str(error)},
        "authority": authority(), "invocation": bind(INVOCATION),
        "execution": {"cards_consumed": 1, "WPLTO_runs": 0,
            "product_links": 0, "media_builds": 0, "device_contacts": 0},
        "retry_authorized": False}))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "card", "check"))
    action = parser.parse_args().action
    if action == "preflight": preflight()
    elif action == "card": card()
    else:
        print("v1.6 Comfort prompt:", "CHECK PASS" if RECEIPT.exists() else
              "CHECK FINAL RED" if CARD_RED.exists() else
              "CHECK ARMED" if (PREFLIGHT / "preflight.json").exists() else "CHECK LOCKED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_red(error)
            except Exception as receipt_error:
                print(f"Comfort prompt Final Red failure: {receipt_error}", file=sys.stderr)
        print(f"v1.6 Comfort prompt: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
