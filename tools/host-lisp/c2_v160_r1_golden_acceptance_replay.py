#!/usr/bin/env python3
"""Seal the R1 no-successor review and replay frozen acceptance read-only."""

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

import c2_v160_r1_golden_review as REVIEW  # noqa: E402
import c2_v160_r1_stored_world_conversions as CONVERSIONS  # noqa: E402
import c2_v21_phase9_freight_boundary_golden as V5  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
FINAL_RED = REVIEW.FINAL_RED
REVIEW_ACCEPTANCE = ARCH / "c2.3-v1.6-r1-golden-review-acceptance.json"
RECEIPT = ARCH / "c2.3-v1.6-r1-golden-acceptance-replay-receipt.json"
FINAL_RED_RECEIPT = ARCH / (
    "c2.3-v1.6-r1-golden-acceptance-replay-final-red.json")
BUILD = ROOT / "build/c2.3/v1.6-r1-golden-acceptance-replay"
PREFLIGHT = BUILD / "preflight.json"
RESULT = BUILD / "artifact-acceptance.json"
TOP_DRIVER = HOST / "c2_v160_r1_scope_projection_replacement.py"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "74802ec9"
FORMAT = "lisp65-c2-v160-r1-golden-acceptance-replay-v1"
STATUS = "PASS: R1 CLOSED UNDER ACCEPTED V5 GOLDEN"


class ReplayError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplayError(message)


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
    for token in ("no successor golden", "rebinds loudly from v4",
                  "read-only", "additive provenance",
                  "reintroduced v4 binding", "no new wplto",
                  "no new link", "green under these terms closes r1"):
        require(token in text, f"R1 acceptance-replay authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def frozen_pair() -> dict[str, dict[str, Any]]:
    red = load(FINAL_RED)
    pair = red["artifacts"]
    require(set(pair) == {"ELF", "PRG"}, "twelfth-run pair closure drift")
    for row in pair.values():
        path = ROOT / row["path"]
        require(bind(path) == row, f"frozen artifact identity drift: {path}")
    return pair


def seal_value() -> dict[str, Any]:
    pending = load(REVIEW.RECEIPT)
    require(pending["status"] == REVIEW.STATUS
            and pending["decision"]["classification"] ==
                "NO-SUCCESSOR-GOLDEN-REQUIRED"
            and pending["review"]["review_accepted"] is False
            and pending["two_world_evidence"]["differing_invariants"] == [],
            "pending no-successor review drift")
    return {"format": "lisp65-c2-v160-r1-golden-review-acceptance-v1",
        "recorded_on": "2026-08-19",
        "status": "ACCEPTED: R1 REQUIRES NO SUCCESSOR GOLDEN",
        "decision": {"review_accepted": True, "golden_v6_emitted": False,
            "accepted_authority": bind(V5.GOLDEN),
            "acceptance_consumer_rebind_authorized": True,
            "acceptance_replay_authorized": True,
            "new_card_authorized": False},
        "authority": {"owner_veto": authorization(),
            "pending_review": bind(REVIEW.RECEIPT),
            "accepted_v5_review": bind(V5.RECEIPT)},
        "claim_limit": (
            "Accepts the host review and one read-only acceptance replay. "
            "No WPLTO, product link, card, media or device action.")}


def seal() -> None:
    require(not REVIEW_ACCEPTANCE.exists(), "R1 Golden review already sealed")
    REVIEW_ACCEPTANCE.write_bytes(canonical(seal_value()))
    print("v1.6 R1 Golden review: SEALED successor=none v5=accepted")


def preflight_value() -> dict[str, Any]:
    require(REVIEW_ACCEPTANCE.read_bytes() == canonical(seal_value()),
            "R1 Golden-review acceptance seal drift")
    pair = frozen_pair()
    elf = ROOT / pair["ELF"]["path"]
    gate = CONVERSIONS.acceptance_golden_gate(elf)
    mutation = CONVERSIONS.acceptance_golden_mutation(elf)
    require(gate["provenance"]["mode"] ==
                "read-only-additive-successor-authority"
            and mutation == "reintroduce-reviewed-v4-binding",
            "v5 consumer rebind gate drift")
    return {"format": FORMAT + "-preflight", "recorded_on": "2026-08-19",
        "status": "PASS: R1 FROZEN ACCEPTANCE REPLAY ARMED 0/1",
        "frozen_pair": pair, "v5_consumer_rebind": gate["provenance"],
        "mutations_rejected": [mutation],
        "attempt_accounting": {"acceptance_replays": 0, "WPLTO_runs": 0,
            "product_links": 0, "cards_consumed": 0, "media_builds": 0,
            "device_contacts": 0},
        "authority": {"owner": authorization(),
            "review_acceptance": bind(REVIEW_ACCEPTANCE),
            "driver": bind(DRIVER)}}


def preflight() -> None:
    require(not BUILD.exists() and not RECEIPT.exists()
            and not FINAL_RED_RECEIPT.exists(), "acceptance replay is one-shot")
    BUILD.mkdir(parents=True)
    PREFLIGHT.write_bytes(canonical(preflight_value()))
    print("v1.6 R1 Golden acceptance: PREFLIGHT PASS replay=0/1 links=0")


def run_acceptance() -> str:
    environment = dict(os.environ)
    environment["LISP65_R1_ACCEPTANCE_RESULT"] = str(RESULT)
    result = subprocess.run([sys.executable, str(TOP_DRIVER), "_accept"],
        cwd=ROOT, env=environment, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    require(result.returncode == 0,
            f"frozen R1 acceptance red:\n{result.stdout}")
    return " ".join(result.stdout.split())


def replay_value(output: str, before: dict[str, dict[str, Any]]
                 ) -> dict[str, Any]:
    after = frozen_pair()
    require(before == after, "read-only acceptance changed frozen pair")
    result = load(RESULT)
    comparison = result["VMA_golden"]
    require(result["status"] == "PASS"
            and comparison["comparison"] ==
                "dependent-address-plus-freight-boundaries-exact"
            and comparison["dependent_fixed_vmas"] == 101
            and comparison["fixed_boundary_symbols"] == 25
            and result["VMA_golden_authority"]["mode"] ==
                "read-only-additive-successor-authority"
            and "dependent_vma_authority" in result
            and "freight_boundary_v5_authority" in result,
            "frozen acceptance did not consume v5 with additive provenance")
    return {"format": FORMAT, "recorded_on": "2026-08-19",
        "status": STATUS, "R1_closed": True,
        "acceptance": result, "frozen_pair_before": before,
        "frozen_pair_after": after,
        "execution_witness": {"output": output, "acceptance_replays": 1,
            "WPLTO_runs": 0, "product_links": 0, "cards_consumed": 0,
            "media_builds": 0, "device_contacts": 0},
        "authority": {"owner": authorization(),
            "review_acceptance": bind(REVIEW_ACCEPTANCE),
            "preflight": bind(PREFLIGHT), "acceptance_result": bind(RESULT),
            "driver": bind(DRIVER)},
        "next": "reopen input-fidelity card on derived 82-byte reserve"}


def record_red(error: Exception, before: dict[str, dict[str, Any]]) -> None:
    value = {"format": FORMAT + "-final-red", "recorded_on": "2026-08-19",
        "status": "FINAL RED: R1 GOLDEN ACCEPTANCE REPLAY RETURNS TO OWNER",
        "error": {"type": type(error).__name__, "message": str(error)},
        "frozen_pair_before": before, "frozen_pair_after": frozen_pair(),
        "attempt_accounting": {"acceptance_replays": 1, "WPLTO_runs": 0,
            "product_links": 0, "cards_consumed": 0, "media_builds": 0,
            "device_contacts": 0}, "retry_authorized": False,
        "owner_disposition_required": True,
        "authority": {"owner": authorization(),
            "review_acceptance": bind(REVIEW_ACCEPTANCE),
            "preflight": bind(PREFLIGHT), "driver": bind(DRIVER)}}
    FINAL_RED_RECEIPT.write_bytes(canonical(value))


def replay() -> None:
    require(PREFLIGHT.read_bytes() == canonical(preflight_value())
            and not RECEIPT.exists() and not FINAL_RED_RECEIPT.exists()
            and not RESULT.exists(), "acceptance replay lifecycle drift")
    before = frozen_pair()
    try:
        output = run_acceptance()
        RECEIPT.write_bytes(canonical(replay_value(output, before)))
    except Exception as error:
        record_red(error, before)
        raise
    print("v1.6 R1 Golden acceptance: REPLAY PASS v5=consumed R1=CLOSED")


def check() -> None:
    if RECEIPT.exists():
        value = load(RECEIPT)
        require(value["status"] == STATUS and value["R1_closed"] is True,
                "R1 closure receipt drift")
        print("v1.6 R1 Golden acceptance: CHECK PASS R1=CLOSED")
    elif FINAL_RED_RECEIPT.exists():
        print("v1.6 R1 Golden acceptance: CHECK FINAL RED")
    elif PREFLIGHT.exists():
        print("v1.6 R1 Golden acceptance: CHECK ARMED")
    else:
        print("v1.6 R1 Golden acceptance: CHECK LOCKED")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("seal", "preflight", "replay", "check"))
    action = parser.parse_args().action
    {"seal": seal, "preflight": preflight, "replay": replay,
     "check": check}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.6 R1 Golden acceptance: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
