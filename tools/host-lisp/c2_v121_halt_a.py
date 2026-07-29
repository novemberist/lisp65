#!/usr/bin/env python3
"""Prepare and verify the v1.2.1 Class-C Halt-A review receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BASE = ROOT / "build/c2.2/v1.2.1-acceptance"
R4_ASSERTIONS = BASE / "r4/r4-product-candidate-assertions.json"
R4_ARCHIVE = BASE / "r4/c2-lite-v1.2.1-r4-product.tar.gz"
G5 = BASE / "r5/hardware-session-01/g5-hardware-receipt.json"
G5_HARNESS = BASE / "r5/hardware-session-01/harness-first-red.json"
R6 = BASE / "r6/r6-packaging-receipt.json"
G6 = BASE / "g6/session-01/g6-hardware-receipt.json"
G6_HARNESS_DEADLINE = (
    BASE / "g6/session-01/case-04-work-media/"
    "harness-first-red-remount-deadline.json")
G6_HARNESS_LATE = (
    BASE / "g6/session-01/case-04-work-media/"
    "harness-first-red-remount-late-success.json")
SEAL = ROOT / (
    "build/c2.2/v1.2.1-seals/"
    "c2-lite-v1.2.1-r6-g6-hardware-acceptance-9928b46.tar.gz")
A1 = EVIDENCE / "c2.2-v1.2.1-a1-prechain-hygiene-receipt.json"
A2 = EVIDENCE / (
    "c2.2-v1.2.1-link77-cross-invariant-delta-receipt.json")
PHASE_C = EVIDENCE / "c2.2-v1.2.1-phase-c-closure-receipt.json"
REGISTER = ROOT / "config/promotion-register.json"
PLAN = ROOT / "docs/planning/v1.2.1-release-plan.md"
RECEIPT = EVIDENCE / "c2.2-v1.2.1-halt-a-review-receipt.json"
SEAL_TOOL = ROOT / "tools/host-lisp/c2_v121_r6_g6_seal.py"
PHASE_C_TOOL = ROOT / "tools/host-lisp/c2_v121_phase_c_close.py"

FORMAT = "lisp65-v1.2.1-halt-a-review-v1"
PRODUCT_SET = (
    "2115b955512a3b794f68d5f2a1d160708cb89184735b7a0984a7cfc61c38f63f")
PACKAGE_SET = (
    "04de1bbba86b9fa7adc030b471e6d74af04eb0aa93912693a79b9996e53b511b")
SEAL_SHA256 = (
    "1521f197fe2ea560ce46aab354c63533fc6e352968308401a3d8653595581a8c")
SEAL_SOURCE = "9928b46d68fa338b670aa0a4302d96195d6cdc5b"
PHASE_C_COMMIT = "f411f35fc8494f9b96879e3925282fb74e865233"
PRIVATE_REF = "refs/heads/codex/post-1.0-docs-cleanup"


class HaltError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise HaltError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"missing file: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"missing JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def run(args: list[str]) -> str:
    result = subprocess.run(
        args, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0, f"command failed: {' '.join(args)}\n"
            f"{result.stdout[-5000:]}")
    return result.stdout


def validate_chain(r4: dict[str, Any], g5: dict[str, Any],
                   r6: dict[str, Any], g6: dict[str, Any]) -> None:
    require(
        r4.get("status") == "seal-authorized"
        and r4.get("candidate", {}).get("artifact_count") == 19
        and r4.get("candidate", {}).get("artifact_set_sha256") == PRODUCT_SET
        and r4.get("claims", {}).get("hardware_evidence_inherited") is False,
        "R4 fresh candidate drift")
    cases = g5.get("cases")
    require(
        g5.get("status") == "passed-fresh-nine-case-G5"
        and g5.get("result") == "passed"
        and isinstance(cases, list) and len(cases) == 9,
        "fresh G5 inventory drift")
    require(
        all(
            case.get("status") == "passed"
            if case.get("claim") == "required"
            else case.get("status") == "recorded-no-claim"
            for case in cases),
        "G5 row status drift")
    require(
        r6.get("status") == "passed-R6-package"
        and r6.get("result") == "passed"
        and r6.get("artifact_count") == 19
        and r6.get("double_pack") == "passed-byteidentical"
        and r6.get("product_artifact_set_sha256") == PRODUCT_SET
        and r6.get("package_set_sha256") == PACKAGE_SET,
        "R6 packaging drift")
    g6_cases = g6.get("cases")
    require(
        g6.get("status") == "passed-five-of-five"
        and g6.get("result") == "passed"
        and g6.get("product_artifact_set_sha256") == PRODUCT_SET
        and isinstance(g6_cases, list) and len(g6_cases) == 5,
        "G6 closure drift")


def validate_matrix(a2: dict[str, Any]) -> None:
    require(
        a2.get("status") == "passed-Link77-delta-review-no-new-open-row"
        and a2.get("method", {}).get("baseline_rows") == 25
        and a2.get("method", {}).get("rederived_count") == 9
        and a2.get("method", {}).get("explicit_not_rederived_count") == 16
        and a2.get("summary", {}).get("PROVEN") == 17
        and a2.get("summary", {}).get("EXCLUDED") == 5
        and a2.get("summary", {}).get("DOCUMENTED_C2_3_DEFERRED") == 3
        and a2.get("summary", {}).get("new_OPEN_rows") == 0,
        "Cross-Invariant delta disposition drift")


def validate_not_promoted(register: dict[str, Any]) -> None:
    promotions = register.get("promotions")
    require(isinstance(promotions, list), "promotion register malformed")
    require(
        not any("v1.2.1" in json.dumps(row, sort_keys=True)
                for row in promotions),
        "v1.2.1 is already present in the promotion register")


def validate_private_remote() -> None:
    output = run(["git", "ls-remote", "github", PRIVATE_REF]).strip()
    fields = output.split()
    require(len(fields) == 2 and fields[1] == PRIVATE_REF,
            "private remote ref missing")
    remote_tip = fields[0]
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", PHASE_C_COMMIT, remote_tip],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    require(
        result.returncode == 0,
        "private remote does not contain the Phase-C closure commit")


def mutation_checks(r4: dict[str, Any], g5: dict[str, Any],
                    r6: dict[str, Any], g6: dict[str, Any],
                    a2: dict[str, Any], register: dict[str, Any]) -> dict[str, Any]:
    checks: list[tuple[str, Any]] = [
        ("G5-row-red", lambda: validate_chain(
            r4,
            {**g5, "cases": [
                ({**row, "status": "failed"} if index == 0 else row)
                for index, row in enumerate(g5["cases"])]},
            r6, g6)),
        ("G6-case-dropped", lambda: validate_chain(
            r4, g5, r6, {**g6, "cases": g6["cases"][:-1]})),
        ("R6-product-set-drift", lambda: validate_chain(
            r4, g5, {**r6, "product_artifact_set_sha256": "0" * 64}, g6)),
        ("matrix-open-row", lambda: validate_matrix({
            **a2,
            "summary": {**a2["summary"], "new_OPEN_rows": 1},
        })),
        ("premature-promotion", lambda: validate_not_promoted({
            **register,
            "promotions": [
                *register["promotions"], {"id": "v1.2.1-premature"}],
        })),
    ]
    rejected: list[str] = []
    for name, check in checks:
        try:
            check()
        except HaltError:
            rejected.append(name)
    require(
        len(rejected) == len(checks),
        "Halt-A mutation escaped: "
        + ", ".join(name for name, _ in checks if name not in rejected))
    return {
        "attempted": len(checks),
        "rejected": len(rejected),
        "names": rejected,
    }


def expected() -> dict[str, Any]:
    r4 = load(R4_ASSERTIONS)
    g5 = load(G5)
    r6 = load(R6)
    g6 = load(G6)
    a1 = load(A1)
    a2 = load(A2)
    phase_c = load(PHASE_C)
    register = load(REGISTER)
    g5_harness = load(G5_HARNESS)
    g6_deadline = load(G6_HARNESS_DEADLINE)
    g6_late = load(G6_HARNESS_LATE)

    validate_chain(r4, g5, r6, g6)
    validate_matrix(a2)
    validate_not_promoted(register)
    validate_private_remote()
    require(
        a1.get("status") == "passed-prechain-hygiene"
        and a1.get("equivalence", {}).get("lanes_executed") == 11
        and a1.get("equivalence", {}).get("cases_executed") == 447,
        "A1 execution witness drift")
    require(
        phase_c.get("status") == "passed-autonomous-phase-c-closed"
        and phase_c.get("rows", {}).get(
            "C3_vm_string_arg_p", {}).get("evaluations") == 844,
        "Phase-C closure drift")
    require(
        sha256(SEAL) == SEAL_SHA256 and SEAL.stat().st_size == 507_635_714,
        "acceptance seal identity drift")
    seal_output = run(
        [sys.executable, str(SEAL_TOOL), "verify", str(SEAL)])
    require(
        "C2-LITE R6/G6 SEAL OFFLINE PASS files=492 "
        f"source={SEAL_SOURCE} release=v1.2.1-acceptance" in seal_output,
        "isolated acceptance seal verification witness absent")
    phase_c_output = run(
        [sys.executable, str(PHASE_C_TOOL), "verify"])
    require(
        "c2-v1.2.1-phase-c: VERIFY PASS rows=4 mutations=5/5"
        in phase_c_output,
        "fresh Phase-C execution witness absent")

    mutations = mutation_checks(r4, g5, r6, g6, a2, register)
    return {
        "format": FORMAT,
        "status": "halt-A-ready-owner-review-required",
        "decision_requested": (
            "accept the fresh v1.2.1 chain and authorize Phase B release "
            "preparation; no promotion occurs before this decision"),
        "candidate": {
            "release": "v1.2.1",
            "product_artifact_set_sha256": PRODUCT_SET,
            "package_set_sha256": PACKAGE_SET,
            "promotion_state": "not-promoted",
        },
        "chain": {
            "A1": {
                "status": "passed",
                "lanes": 11,
                "executed_cases": 447,
                "receipt": bind(A1),
            },
            "A2": {
                "status": "passed-no-new-open-row",
                "rows": 25,
                "rederived": 9,
                "explicit_not_rederived": 16,
                "disposition": {
                    "PROVEN": 17,
                    "EXCLUDED": 5,
                    "DOCUMENTED-C2.3-DEFERRED": 3,
                },
                "receipt": bind(A2),
            },
            "R4": {
                "status": "passed-fresh-seal",
                "roles": 19,
                "archive": bind(R4_ARCHIVE),
                "assertions": bind(R4_ASSERTIONS),
            },
            "G5": {
                "status": "passed-fresh-nine-of-nine",
                "device_count": 1,
                "value_strings": [
                    {"id": row["id"], "claim": row["claim"],
                     "status": row["status"],
                     "value_string": row["value_string"]}
                    for row in g5["cases"]
                ],
                "receipt": bind(G5),
            },
            "R6": {
                "status": "passed-exact-package",
                "roles": 19,
                "double_pack": "byteidentical",
                "receipt": bind(R6),
            },
            "G6": {
                "status": "passed-five-of-five",
                "cases": [row["id"] for row in g6["cases"]],
                "receipt": bind(G6),
            },
            "remote_bound_seal": {
                "status": "passed-isolated-offline-verification",
                "source_commit": SEAL_SOURCE,
                "archive": bind(SEAL),
                "files": 492,
                "bindings": 138,
                "claim": "acceptance-sealed-v1.2.1-not-promoted",
            },
        },
        "harness_only_first_reds": [
            {
                "id": g5_harness["classification"],
                "disposition": g5_harness["status"],
                "product_execution": False,
                "receipt": bind(G5_HARNESS),
            },
            {
                "id": g6_deadline["id"],
                "disposition": g6_deadline["result"],
                "product_result": "0-exact",
                "receipt": bind(G6_HARNESS_DEADLINE),
            },
            {
                "id": g6_late["id"],
                "disposition": g6_late["result"],
                "product_result": "0-exact-late-read-only-capture",
                "receipt": bind(G6_HARNESS_LATE),
            },
        ],
        "autonomous_phase_c": {
            "status": "passed-four-rows",
            "dirmiss": "attributed-renderer-pointer-overwrite-parked-v1.2.2",
            "upstream_L11": "owner-paste-ready-no-action-taken",
            "vm_string_arg_p": "844-evaluations",
            "document_index": "226-tracked-documents",
            "receipt": bind(PHASE_C),
            "private_minimum_commit": PHASE_C_COMMIT,
        },
        "known_nonblocking_positions": [
            "DIRMISS detail renderer fix parked for v1.2.2",
            "intermittent post-GC OOM remains unreproduced and documented",
            "defstruct/dynamic library freight remains parked",
            "C1, E3 and E4 remain explicit C2.3 deferrals",
        ],
        "mutations": mutations,
        "authority": {
            "release_plan": bind(PLAN),
            "promotion_register": bind(REGISTER),
            "verifier": bind(Path(__file__)),
        },
        "claim_limit": (
            "Halt-A review package only. It does not promote, prepare release "
            "notes, create a tag, push a public remote or publish v1.2.1."),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "verify"))
    args = parser.parse_args()
    try:
        value = expected()
        encoded = json.dumps(
            value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
        if args.action == "write":
            RECEIPT.write_text(encoded, encoding="utf-8")
            print(
                "c2-v1.2.1-halt-a: READY A1=447 A2=25 "
                "G5=9/9 G6=5/5 PhaseC=4 seal=verified mutations=5/5")
        else:
            require(RECEIPT.is_file(), f"missing receipt: {RECEIPT}")
            require(
                RECEIPT.read_text(encoding="utf-8") == encoded,
                "tracked Halt-A receipt drift")
            print(
                "c2-v1.2.1-halt-a: VERIFY PASS "
                "promotion=not-promoted owner-review=required")
        return 0
    except (HaltError, OSError, UnicodeError, json.JSONDecodeError,
            ValueError) as error:
        print(f"c2-v1.2.1-halt-a: FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
