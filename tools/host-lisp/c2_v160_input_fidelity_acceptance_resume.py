#!/usr/bin/env python3
"""Resume frozen input-fidelity Acceptance with additive card freight."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v160_r1_stored_world_conversions as CONVERSIONS  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
FINAL_RED = ARCH / (
    "c2.3-v1.6-input-fidelity-membership-real-consumer-card-final-red.json")
ATTRIBUTION = ARCH / (
    "c2.3-v1.6-input-fidelity-acceptance-closure-attribution.json")
TOP_DRIVER = HOST / (
    "c2_v160_input_fidelity_membership_real_consumer_replacement_card.py")
CARD_BUILD = ROOT / (
    "build/c2.3/v1.6-input-fidelity-membership-real-consumer-card")
RESULT = CARD_BUILD / "artifact-acceptance.json"
BUILD = ROOT / "build/c2.3/v1.6-input-fidelity-acceptance-resume"
PREFLIGHT = BUILD / "preflight.json"
RECEIPT = ARCH / (
    "c2.3-v1.6-input-fidelity-acceptance-resume-receipt.json")
FINAL_RED_RECEIPT = ARCH / (
    "c2.3-v1.6-input-fidelity-acceptance-resume-final-red.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "61f77bce"
FORMAT = "lisp65-c2-v160-input-fidelity-additive-acceptance-resume-v1"
STATUS = "PASS: INPUT-FIDELITY SEAM CLOSED; DEVICE PATH OPEN"


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


def authorization() -> dict[str, Any]:
    full = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{full}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("v5 remains the unchanged geometry authority",
                  "no silent third category", "no double authority",
                  "derived placement proof, not addresses", "acceptance resume",
                  "no new wplto", "no link", "green closes"):
        require(token in text, f"additive Acceptance authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def frozen_pair() -> dict[str, dict[str, Any]]:
    red = load(FINAL_RED)
    pair = red["artifacts"]
    require(set(pair) == {"ELF", "PRG"}
            and red["attempt_accounting"]["WPLTO_runs"] == 1
            and red["attempt_accounting"]["product_link_attempts"] == 1,
            "consumed-card frozen pair/accounting drift")
    for row in pair.values():
        require(bind(ROOT / row["path"]) == row,
                f"frozen card artifact identity drift: {row['path']}")
    return pair


def preflight_value() -> dict[str, Any]:
    attribution = load(ATTRIBUTION)
    require(attribution["status"] ==
                "ATTRIBUTED: ACCEPTED V5 REJECTS TWO AUTHORIZED ADDITIVE SECTIONS"
            and attribution["decision_boundary"]["successors_authorized"] == 0,
            "additive Acceptance attribution drift")
    PRODUCT.configure_input_capture()
    pair = frozen_pair()
    elf = ROOT / pair["ELF"]["path"]
    mutations = CONVERSIONS.additive_freight_mutations(elf)
    gate = CONVERSIONS.acceptance_golden_gate(elf)
    freight = gate["additive_card_freight"]
    require(mutations == ["unregistered-third-category",
                "double-golden-and-card-authority",
                "address-snapshot-in-freight-row"]
            and gate["comparison"]["comparison"] ==
                "dependent-address-plus-freight-boundaries-exact"
            and freight["candidate_sections"] == 105
            and freight["golden_sections"] == 103
            and len(freight["registered_sections"]) == 2,
            "additive Acceptance preflight drift")
    return {"format": FORMAT + "-preflight", "recorded_on": "2026-08-19",
        "status": "PASS: ADDITIVE ACCEPTANCE RESUME ARMED 0/1",
        "frozen_pair": pair, "additive_gate": gate,
        "mutations_rejected": mutations,
        "authority": {"review": authorization(),
            "Final_Red": bind(FINAL_RED), "attribution": bind(ATTRIBUTION),
            "driver": bind(DRIVER)},
        "attempt_accounting": {"acceptance_resumes": 0, "WPLTO_runs": 0,
            "product_links": 0, "cards_consumed": 0, "media_builds": 0,
            "device_contacts": 0}}


def preflight() -> None:
    require(not BUILD.exists() and not RECEIPT.exists()
            and not FINAL_RED_RECEIPT.exists() and not RESULT.exists(),
            "additive Acceptance resume is one-shot")
    value = preflight_value()
    BUILD.mkdir(parents=True)
    PREFLIGHT.write_bytes(canonical(value))
    print("v1.6 input fidelity Acceptance: PREFLIGHT PASS resume=0/1 "
          "mutations=3")


def run_acceptance() -> str:
    result = subprocess.run([sys.executable, str(TOP_DRIVER), "_accept"],
        cwd=ROOT, env=dict(os.environ), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0,
            f"frozen input-fidelity Acceptance red:\n{result.stdout}")
    return " ".join(result.stdout.split())


def replay_value(output: str, before: dict[str, dict[str, Any]]) -> dict[str, Any]:
    after = frozen_pair()
    require(before == after, "read-only Acceptance changed frozen pair")
    result = load(RESULT)
    freight = result.get("additive_card_freight")
    require(result["status"] == "PASS"
            and result["VMA_golden"]["comparison"] ==
                "dependent-address-plus-freight-boundaries-exact"
            and result["VMA_golden_authority"]["mode"] ==
                "read-only-additive-successor-authority"
            and freight["golden_sections"] == 103
            and freight["candidate_sections"] == 105
            and len(freight["freight_rows"]) == 2
            and all("address" not in row and "vma" not in row
                    and "lma" not in row for row in freight["freight_rows"]),
            "Acceptance result did not preserve v5 plus proof-only freight")
    return {"format": FORMAT, "recorded_on": "2026-08-19",
        "status": STATUS, "input_fidelity_seam_closed": True,
        "device_path_open": True, "acceptance": result,
        "frozen_pair_before": before, "frozen_pair_after": after,
        "execution_witness": {"output": output, "acceptance_resumes": 1,
            "WPLTO_runs": 0, "product_links": 0, "cards_consumed": 0,
            "media_builds": 0, "device_contacts": 0},
        "authority": {"review": authorization(), "preflight": bind(PREFLIGHT),
            "acceptance_result": bind(RESULT), "driver": bind(DRIVER)},
        "next": "owner device acceptance of v1.6 items 1 and 2"}


def record_red(error: Exception, before: dict[str, dict[str, Any]]) -> None:
    FINAL_RED_RECEIPT.write_bytes(canonical({
        "format": FORMAT + "-final-red", "recorded_on": "2026-08-19",
        "status": "FINAL RED: ADDITIVE ACCEPTANCE RESUME RETURNS TO REVIEW",
        "error": {"type": type(error).__name__, "message": str(error)},
        "frozen_pair_before": before, "frozen_pair_after": frozen_pair(),
        "attempt_accounting": {"acceptance_resumes": 1, "WPLTO_runs": 0,
            "product_links": 0, "cards_consumed": 0, "media_builds": 0,
            "device_contacts": 0}, "retry_authorized": False,
        "authority": {"review": authorization(), "preflight": bind(PREFLIGHT),
            "driver": bind(DRIVER)}}))


def replay() -> None:
    require(PREFLIGHT.read_bytes() == canonical(preflight_value())
            and not RECEIPT.exists() and not FINAL_RED_RECEIPT.exists()
            and not RESULT.exists(), "additive Acceptance lifecycle drift")
    before = frozen_pair()
    try:
        output = run_acceptance()
        RECEIPT.write_bytes(canonical(replay_value(output, before)))
    except Exception as error:
        record_red(error, before)
        raise
    print("v1.6 input fidelity Acceptance: RESUME PASS seam=CLOSED device=OPEN")


def check() -> None:
    if RECEIPT.exists():
        value = load(RECEIPT)
        require(value["status"] == STATUS
                and value["input_fidelity_seam_closed"] is True,
                "additive Acceptance closure receipt drift")
        print("v1.6 input fidelity Acceptance: CHECK PASS seam=CLOSED")
    elif FINAL_RED_RECEIPT.exists():
        print("v1.6 input fidelity Acceptance: CHECK FINAL RED")
    elif PREFLIGHT.exists():
        print("v1.6 input fidelity Acceptance: CHECK ARMED")
    else:
        print("v1.6 input fidelity Acceptance: CHECK LOCKED")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "replay", "check"))
    {"preflight": preflight, "replay": replay, "check": check}[
        parser.parse_args().action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.6 input fidelity Acceptance: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
