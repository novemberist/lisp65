#!/usr/bin/env python3
"""Resume card-3 qualification read-only over its frozen linked pair."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_lite_v6_first_product_link as ATTIC  # noqa: E402
import c2_v17_ide_idle_blink_product_card as CARD  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
FINAL_RED = CARD.FINAL_RED
BUILD = CARD.BUILD
SCOPE = BUILD / "owner-scope-result.json"
ACCEPTANCE = BUILD / "artifact-acceptance.json"
RECEIPT = ARCH / (
    "c2.3-v1.7-ide-idle-blink-qualification-resume-receipt.json")
FINAL_RED_2 = ARCH / (
    "c2.3-v1.7-ide-idle-blink-qualification-resume-final-red.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "f4e3a854"
EXPECTED = {
    "ELF": "c5aaccf702a655223b540e18ccb58176aa500baa37554a0d610c07c2381b6c52",
    "PRG": "7345e84de9e30eae3428ff2444de1c626b873109abb0f2c9dc4c6a35f03ce5d0",
}
STATUS = "PASS: IDE IDLE/BLINK QUALIFICATION RESUMED READ-ONLY"


class ResumeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResumeError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def git_binding(commit: str, path: Path) -> dict[str, Any]:
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    name = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    value = git_binding(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{value['commit']}:{value['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout.decode().lower()
    text = " ".join(raw.replace("*", "").replace("`", "").split())
    for token in ("semantic conversion", "read-only qualification resume",
                  "no new wplto, product link or card run",
                  EXPECTED["ELF"], EXPECTED["PRG"],
                  "loses the bank-2 term", "shelf, dma or attic edge"):
        require(token in text, f"card-3 resume authority absent: {token}")
    return value


def frozen_pair() -> dict[str, dict[str, Any]]:
    paths = {"ELF": CARD.ELF, "PRG": CARD.PRG}
    value = {name: bind(path) for name, path in paths.items()}
    require({name: row["sha256"] for name, row in value.items()} == EXPECTED,
            "IDE idle/blink frozen pair drift")
    return value


def validate_execution(value: dict[str, int]) -> None:
    require(value == {"qualification_resumes": 1, "WPLTO_runs": 0,
        "product_links": 0, "cards_consumed": 0, "scope_runs": 1,
        "acceptance_runs": 1, "media_builds": 0, "device_contacts": 0},
        "read-only IDE idle/blink resume attempted product work")


def execution_mutations(value: dict[str, int]) -> list[str]:
    cases: dict[str, Callable[[dict[str, int]], None]] = {
        "rebuild-WPLTO": lambda x: x.update(WPLTO_runs=1),
        "relink-product": lambda x: x.update(product_links=1),
        "consume-card": lambda x: x.update(cards_consumed=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate_execution(trial)
        except ResumeError:
            rejected.append(name)
    require(rejected == list(cases), "qualification rebuild mutation survived")
    return rejected


def run_child(action: str) -> dict[str, Any]:
    run = subprocess.run([sys.executable, str(CARD.DRIVER), action], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(run.returncode == 0,
            f"IDE idle/blink read-only {action} red:\n{run.stdout}")
    return {"action": action, "status": "PASS",
            "witness": " ".join(run.stdout.split())}


def validate(value: dict[str, Any]) -> None:
    require(value["status"] == STATUS
            and value["frozen_pair_before"] == value["frozen_pair_after"]
            and value["semantic_no_runtime_attic"]["checks"][
                "hot_entry_uses_bank2"] is True
            and value["semantic_no_runtime_attic"][
                "bank2_linked_reader_targets"] == ["c2_map_cpu_read"]
            and value["semantic_no_runtime_attic"]["mutations_rejected"] == [
                "lost-bank2-expression", "reintroduced-Shelf-edge",
                "reintroduced-DMA-edge",
                "reintroduced-Attic-completion-edge"]
            and value["scope"]["status"] == "PASS"
            and value["acceptance"]["status"] == "PASS",
            "IDE idle/blink qualification-resume receipt drift")
    validate_execution(value["execution_accounting"])


def resume() -> None:
    require(not RECEIPT.exists() and not FINAL_RED_2.exists()
            and not CARD.RECEIPT.exists()
            and not SCOPE.exists() and not ACCEPTANCE.exists(),
            "IDE idle/blink qualification resume is one-shot")
    red = load(FINAL_RED)
    require(red["status"] ==
                "FINAL RED: IDE IDLE/BLINK CARD RETURNS FOR REVIEW"
            and red["attempt_accounting"] == {
                "cards_consumed": 1, "WPLTO_runs": 1, "product_links": 1,
                "scope_runs": 0, "acceptance_runs": 0, "media_builds": 0,
                "device_contacts": 0},
            "IDE idle/blink Final Red authority drift")
    auth = authority()
    before = frozen_pair()
    semantic = ATTIC.no_runtime_attic_gate(
        CARD.ELF, CARD.ELF.parent / "generated-product-sources")
    # The inherited v1.6 final gate contains a Comfort-service benchmark.
    # Card 3 changes only the current Bank-2 IDE plane; its read-only resume
    # therefore qualifies that freight and leaves unrelated Comfort history
    # to its sealed predecessor evidence.
    final_product = {"card3": CARD.card3_final_gate()}
    processes = [run_child("_scope"), run_child("_accept")]
    scope = load(SCOPE); acceptance = load(ACCEPTANCE)
    after = frozen_pair()
    require(before == after and scope.get("status") == "PASS"
            and acceptance.get("status") == "PASS",
            "IDE idle/blink Scope/Acceptance resume red")
    execution = {"qualification_resumes": 1, "WPLTO_runs": 0,
        "product_links": 0, "cards_consumed": 0, "scope_runs": 1,
        "acceptance_runs": 1, "media_builds": 0, "device_contacts": 0}
    validate_execution(execution)
    value = {
        "format": "lisp65-c2-v17-ide-idle-blink-qualification-resume-v1",
        "recorded_on": "2026-08-26", "status": STATUS,
        "authority": {"review": auth, "Final_Red": bind(FINAL_RED),
            "semantic_guard": bind(Path(ATTIC.__file__)),
            "driver": bind(DRIVER)},
        "frozen_pair_before": before, "frozen_pair_after": after,
        "semantic_no_runtime_attic": semantic,
        "final_product": final_product,
        "scope": {"status": scope["status"], "receipt": bind(SCOPE),
                  "value": scope},
        "acceptance": {"status": acceptance["status"],
                       "receipt": bind(ACCEPTANCE), "value": acceptance},
        "processes": processes, "execution_accounting": execution,
        "rebuild_mutations_rejected": execution_mutations(execution),
        "claim_limit": "Post-link qualification only; no WPLTO, link, card, media or device.",
        "next": "card-3 report and review; hardware remains closed",
    }
    validate(value)
    RECEIPT.write_bytes(canonical(value))
    print("v1.7 IDE idle/blink: RESUME PASS scope=PASS acceptance=PASS "
          "WPLTO=0 link=0 card=0")


def record_red() -> None:
    require(not RECEIPT.exists() and not FINAL_RED_2.exists()
            and not CARD.RECEIPT.exists() and not SCOPE.exists()
            and not ACCEPTANCE.exists(),
            "IDE idle/blink qualification-red lifecycle drift")
    before = frozen_pair()
    semantic = ATTIC.no_runtime_attic_gate(
        CARD.ELF, CARD.ELF.parent / "generated-product-sources")
    consumption = CARD.card3_compiler_consumption()
    values = [row["consumed_value"] for row in consumption["consumers"]]
    headers = {row["bound_header"]["path"]
               for row in consumption["consumers"]}
    require(semantic["checks"]["hot_entry_uses_bank2"] is True
            and semantic["bank2_linked_reader_targets"] == ["c2_map_cpu_read"]
            and consumption["candidate_bytes"] == 52230
            and values == [46043, 46043]
            and headers == {
                "build/c2.3/v2.0-ownership-recharter-inputs/c2_lite_static_plane.h"}
            and consumption["all_consumers_current"] is False,
            "IDE idle/blink compiler-consumption attribution drift")
    after = frozen_pair()
    require(before == after, "qualification attribution changed frozen pair")
    value = {
        "format": "lisp65-c2-v17-ide-idle-blink-qualification-resume-red-v1",
        "recorded_on": "2026-08-26",
        "status": "QUALIFICATION RED: CARD3 BANK2 PLANE BOUND BUT NOT COMPILED",
        "authority": {"review": authority(), "Final_Red": bind(FINAL_RED),
            "driver": bind(DRIVER)},
        "frozen_pair_before": before, "frozen_pair_after": after,
        "completed_conversion": {"semantic_no_runtime_attic": semantic,
            "status": "PASS"},
        "stopper": {
            "classification": "bound-not-consumed at real compile_link consumer",
            "candidate_plane": {"bytes": consumption["candidate_bytes"],
                "sha256": consumption["candidate_sha256"],
                "path": consumption["candidate_plane"]["path"]},
            "real_compiler_consumption": consumption["consumers"],
            "observed_values": values,
            "difference_bytes": consumption["candidate_bytes"] - values[0],
            "product_defect_not_exonerated": True,
        },
        "attempt_accounting": {"qualification_resumes_completed": 0,
            "scope_runs": 0, "acceptance_runs": 0, "WPLTO_runs": 0,
            "product_links": 0, "cards_consumed": 0,
            "media_builds": 0, "device_contacts": 0},
        "retry_authorized": False, "review_disposition_required": True,
        "recommended_successor": (
            "bind the candidate-owned 52,230-byte static-plane header at both "
            "real compile_link consumers, prove the force-include path and "
            "consumed value together, then authorize a new read-only resume"),
        "claim_limit": "Attribution only; Scope and Acceptance did not run.",
    }
    FINAL_RED_2.write_bytes(canonical(value))
    print("v1.7 IDE idle/blink: QUALIFICATION RED RECORD 52230!=46043 "
          "scope=0 acceptance=0 WPLTO=0 link=0 card=0")


def check() -> None:
    value = load(RECEIPT); validate(value)
    require(value["frozen_pair_before"] == frozen_pair()
            and value["frozen_pair_after"] == frozen_pair(),
            "IDE idle/blink resumed pair changed after qualification")
    print("v1.7 IDE idle/blink: RESUME CHECK PASS frozen-pair=exact")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("resume", "record-red", "check"))
    {"resume": resume, "record-red": record_red,
     "check": check}[parser.parse_args().action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ResumeError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"v1.7 IDE idle/blink resume: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
