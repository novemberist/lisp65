#!/usr/bin/env python3
"""Verify the owner-authorized read-only salvage of the retained stop."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_v16_corrected_view_contact as VIEW  # noqa: E402

RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-mem-init-preoverlay-status-salvage-device-receipt.json")
PREPARATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-mem-init-preoverlay-status-partition-preparation.json")
PLAN = "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
OWNER_COMMIT = "f96bb504f9a460c708d58d7130e98e5d6fea7c3f"
PREPARATION_SHA256 = "21c8c7e362bec378a4de0cb7575042f3575dbbbb3aaa606b8947120b232b8ad2"
PLAN_SHA256 = "d90eaa8b7634873b7185d727f557c0561f08382c25256a28587b7235fe235e97"


class SalvageError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SalvageError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def git(args: list[str]) -> bytes:
    result = subprocess.run(["git", *args], cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    require(result.returncode == 0,
            f"git {' '.join(args)} failed: {result.stderr.decode(errors='replace')}")
    return result.stdout


def authorities() -> None:
    require(git(["rev-parse", "f96bb504^{commit}"]).decode().strip() == OWNER_COMMIT,
            "owner authorization commit drift")
    plan = git(["show", f"{OWNER_COMMIT}:{PLAN}"])
    require(sha256(plan) == PLAN_SHA256, "owner authorization plan blob drift")
    text = plan.decode("utf-8")
    require("confirm the register tuple, then read only `$74/$75` and\n"
            "`$8C…$8F`. No RUN, no new monitor entry, no stop, no resume." in text
            and "if the tuple\ndoes not confirm, the reading aborts with no claim."
            in text, "owner authorization wording absent")
    require(sha256(PREPARATION.read_bytes()) == PREPARATION_SHA256,
            "salvage preparation drift")


def audit(value: dict[str, Any]) -> None:
    require(value["status"] == "PRE-INSTALLER-BOUNDARY; SAME-STOP READ COMPLETE",
            "salvage status drift")
    precondition = value["precondition"]
    expected = {"PC": "0xe160", "B": "0x00", "SP": "0x01ee",
                "MAPH": "0xb300", "MAPL": "0xe300"}
    require(precondition["expected_tuple"] == expected
            and precondition["observed_tuple"] == expected
            and precondition["tuple_matches"] is True,
            "retained tuple was not confirmed exactly")
    parsed = VIEW.parse_registers(bytes.fromhex(precondition["raw_hex"]))
    require({key: parsed[key] for key in expected} == expected,
            "raw register row does not confirm retained tuple")

    reads = value["reads"]
    require(reads["status_pair"]["command"] == "m00000074"
            and reads["status_pair"]["physical_address"] == "0x00000074"
            and reads["status_pair"]["bytes"] == "0000",
            "status-pair read drift")
    require(reads["health_row"]["command"] == "m0000008c"
            and reads["health_row"]["physical_address"] == "0x0000008c"
            and reads["health_row"]["bytes"] == "00000000",
            "health-row read drift")
    for key, address, size in (("status_pair", 0x74, 2),
                               ("health_row", 0x8C, 4)):
        row = reads[key]
        parsed_bytes = VIEW.parse_memory(bytes.fromhex(row["raw_hex"]),
                                         address, size)
        require(parsed_bytes.hex() == row["bytes"], f"raw {key} read drift")

    require(value["decoded"] == {
        "vm_boot_overlay_status": 0, "ov_started": 0, "c2_ready": 0,
        "reserved_8d": 0, "reserved_8e": 0, "mem_oom": 0},
        "decoded status drift")
    require(value["classification"] == {
        "decision_row": "started=0", "outcome": "PRE-INSTALLER-BOUNDARY",
        "claim": ("boot reached the prior $44 witness but did not reach the "
                  "overlay-installer arming store before $C85A")},
        "classification drift")
    require(value["contact"] == {
        "additional_RUNs": 0, "additional_monitor_entries": 0,
        "additional_stops": 0, "additional_resumes": 0,
        "CPU_left_stopped": True, "reads_after_tuple_confirmation": 2},
        "same-stop action accounting drift")
    require(value["claim_limit"] == {
        "mem_init_answer": None, "R_A_I_G": None, "product_fault": None,
        "new_launch": False, "new_measured_form": False,
        "boundary_only": "before $C85A"}, "claim limit drift")


def selftest() -> dict[str, Any]:
    base = load(RECEIPT)
    audit(base)
    mutations = [
        (["precondition", "observed_tuple", "PC"], "0xe161"),
        (["precondition", "tuple_matches"], False),
        (["reads", "status_pair", "physical_address"], "0x0000b582"),
        (["reads", "status_pair", "bytes"], "0001"),
        (["reads", "health_row", "bytes"], "00000001"),
        (["decoded", "ov_started"], 1),
        (["classification", "decision_row"], "started=1,status=9"),
        (["classification", "outcome"], "ENTRY-RUN-BOUNDARY"),
        (["contact", "additional_RUNs"], 1),
        (["contact", "additional_monitor_entries"], 1),
        (["contact", "additional_resumes"], 1),
        (["contact", "CPU_left_stopped"], False),
        (["claim_limit", "mem_init_answer"], "never-established"),
        (["claim_limit", "R_A_I_G"], "G"),
    ]
    rejected: dict[str, str] = {}
    for index, (path, replacement) in enumerate(mutations, 1):
        trial = deepcopy(base)
        cursor: Any = trial
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = replacement
        try:
            audit(trial)
        except (SalvageError, ValueError) as error:
            rejected[f"mutation-{index:02d}"] = str(error)
        else:
            raise SalvageError(f"salvage mutation survived: {path}")
    return {"status": "SELFTEST PASS", "mutations": len(rejected),
            "rejected": rejected}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "selftest"))
    args = parser.parse_args()
    authorities()
    if args.action == "selftest":
        value = selftest()
    else:
        value = load(RECEIPT)
        audit(value)
        value = {"status": "PASS", "classification":
                 value["classification"]["outcome"],
                 "mutations": len(selftest()["rejected"])}
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SalvageError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"MEM_INIT PREOVERLAY STATUS SALVAGE FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(1)
