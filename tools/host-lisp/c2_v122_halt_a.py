#!/usr/bin/env python3
"""Prepare and verify the v1.2.2 Class-C Halt-A review receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BASE = ROOT / "build/c2.2/v1.2.2-acceptance"
R4_ASSERTIONS = BASE / "r4/r4-product-candidate-assertions.json"
R4_ARCHIVE = BASE / "r4/c2-lite-v1.2.2-r4-product.tar.gz"
G5 = BASE / "r5/hardware-session-01/g5-hardware-receipt.json"
G2 = BASE / (
    "r5/hardware-session-01/g2-symbol-value-cost-hardware-receipt.json"
)
R6 = BASE / "r6/r6-packaging-receipt.json"
G6 = BASE / "g6/session-01/g6-hardware-receipt.json"
SEAL = ROOT / (
    "build/c2.2/v1.2.2-seals/"
    "c2-lite-v1.2.2-r6-g6-hardware-acceptance-8cbc652.tar.gz"
)
A1 = EVIDENCE / "c2.2-v1.2.2-a1-prechain-hygiene-receipt.json"
A2 = EVIDENCE / "c2.2-v1.2.2-link78-cross-invariant-delta-receipt.json"
REGISTER = ROOT / "config/promotion-register.json"
PLAN = ROOT / "docs/planning/v1.2.2-release-plan.md"
RECEIPT = EVIDENCE / "c2.2-v1.2.2-halt-a-review-receipt.json"
SEAL_TOOL = ROOT / "tools/host-lisp/c2_v122_r6_g6_seal.py"
FORMAT = "lisp65-v1.2.2-halt-a-review-v1"
PRODUCT_SET = (
    "359809d4a6b3bde95b9624f375ae38c32446ea54024a58691e07eb4673bcf7de"
)
PACKAGE_SET = (
    "129cbf443beb4433bcf87388c2131a8f084df3b2e812b21fb5893f008932d651"
)
SEAL_SHA256 = (
    "e317bc0525e27c8eb604e70e1018bc8276677959e9b1e455a4687032568e13bc"
)
SEAL_BYTES = 43_354_237
SEAL_SOURCE = "8cbc652e2769de131f6cac703112e2b635e375ed"
PRIVATE_REF = "refs/heads/codex/post-1.0-docs-cleanup"
HARNESS_FIRST_REDS = (
    BASE / (
        "r5/hardware-session-01/g2-symbol-value-cost/"
        "input-transport-first-red.json"
    ),
    BASE / "g6/session-01/case-02-harness-first-red-upload-timeout/receipt.json",
    BASE / (
        "g6/session-01/case-02-cold-boot/"
        "harness-first-red-relative-tools-path/receipt.json"
    ),
    BASE / (
        "g6/session-01/case-04-work-media/"
        "harness-first-red-remount-deadline.json"
    ),
    BASE / (
        "g6/session-01/case-04-work-media/"
        "harness-first-red-freezer-mount-persistence.json"
    ),
    BASE / (
        "g6/session-01/case-04-work-media/"
        "harness-first-red-work-remount-after-cycle-deadline.json"
    ),
)


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
        stderr=subprocess.STDOUT, check=False,
    )
    require(
        result.returncode == 0,
        f"command failed: {' '.join(args)}\n{result.stdout[-5000:]}",
    )
    return result.stdout


def validate_chain(
    r4: dict[str, Any], g5: dict[str, Any],
    r6: dict[str, Any], g6: dict[str, Any],
) -> None:
    require(
        r4.get("status") == "seal-authorized"
        and r4.get("candidate", {}).get("artifact_count") == 19
        and r4.get("candidate", {}).get("artifact_set_sha256") == PRODUCT_SET
        and r4.get("claims", {}).get("hardware_evidence_inherited") is False,
        "R4 fresh candidate drift",
    )
    cases = g5.get("cases")
    require(
        g5.get("status") == "passed-fresh-nine-case-G5"
        and g5.get("result") == "passed"
        and isinstance(cases, list) and len(cases) == 9
        and all(
            row.get("status") == (
                "passed" if row.get("claim") == "required"
                else "recorded-no-claim"
            )
            for row in cases
        ),
        "fresh G5 inventory drift",
    )
    require(
        r6.get("status") == "passed-R6-package"
        and r6.get("result") == "passed"
        and r6.get("artifact_count") == 19
        and r6.get("double_pack") == "passed-byteidentical"
        and r6.get("product_artifact_set_sha256") == PRODUCT_SET
        and r6.get("package_set_sha256") == PACKAGE_SET,
        "R6 packaging drift",
    )
    g6_cases = g6.get("cases")
    require(
        g6.get("status") == "passed-five-of-five"
        and g6.get("result") == "passed"
        and g6.get("product_artifact_set_sha256") == PRODUCT_SET
        and isinstance(g6_cases, list) and len(g6_cases) == 5
        and [row.get("id") for row in g6_cases] == [
            "offline-package-verification",
            "cold-boot-from-exact-R6-product-media",
            "always-restage-and-target-readback",
            "work-media-write-read-power-cycle",
            "product-media-remains-byteidentical",
        ],
        "G6 closure drift",
    )


def validate_matrix(a2: dict[str, Any]) -> None:
    require(
        a2.get("status")
        == "passed-Link78-L65E-delta-review-no-new-open-row"
        and a2.get("method", {}).get("baseline_rows") == 25
        and a2.get("method", {}).get("rederived_count") == 1
        and a2.get("method", {}).get("rederived_rows") == ["E5"]
        and a2.get("method", {}).get("explicit_not_rederived_count") == 24
        and a2.get("summary", {}).get("PROVEN") == 17
        and a2.get("summary", {}).get("EXCLUDED") == 5
        and a2.get("summary", {}).get("DOCUMENTED_C2_3_DEFERRED") == 3
        and a2.get("summary", {}).get("new_OPEN_rows") == 0,
        "Cross-Invariant delta disposition drift",
    )


def validate_g2(g2: dict[str, Any]) -> None:
    observations = g2.get("observations", {})
    require(
        g2.get("status") == "passed-informational-measurement"
        and g2.get("disposition") == "threshold-not-met-no-GC-cut-authorized"
        and g2.get("acceptance_independence", {}).get(
            "can_make_acceptance_chain_red") is False
        and observations.get("delta_frames_per_1000") == 0
        and observations.get("microseconds_per_read") == 0
        and observations.get("projected_480_frames") == 0.0
        and observations.get("dominance_threshold_frames") == 44.5
        and observations.get("dominant_GC_lever") is False,
        "G2 informational measurement drift",
    )


def validate_not_promoted(register: dict[str, Any]) -> None:
    promotions = register.get("promotions")
    require(isinstance(promotions, list), "promotion register malformed")
    require(
        not any(
            "v1.2.2" in json.dumps(row, sort_keys=True)
            for row in promotions
        ),
        "v1.2.2 is already present in the promotion register",
    )


def validate_private_remote() -> str:
    output = run(["git", "ls-remote", "github", PRIVATE_REF]).strip()
    fields = output.split()
    require(
        len(fields) == 2 and fields[1] == PRIVATE_REF
        and re.fullmatch(r"[0-9a-f]{40}", fields[0]) is not None,
        "private remote ref missing",
    )
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", SEAL_SOURCE, fields[0]],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    require(
        result.returncode == 0,
        "private remote does not contain the sealed source commit",
    )
    return fields[0]


def mutation_checks(
    r4: dict[str, Any], g5: dict[str, Any], r6: dict[str, Any],
    g6: dict[str, Any], g2: dict[str, Any], a2: dict[str, Any],
    register: dict[str, Any],
) -> dict[str, Any]:
    checks: list[tuple[str, Callable[[], None]]] = [
        ("G5-row-red", lambda: validate_chain(
            r4,
            {**g5, "cases": [
                ({**row, "status": "failed"} if index == 0 else row)
                for index, row in enumerate(g5["cases"])
            ]},
            r6, g6,
        )),
        ("G6-case-dropped", lambda: validate_chain(
            r4, g5, r6, {**g6, "cases": g6["cases"][:-1]},
        )),
        ("R6-product-set-drift", lambda: validate_chain(
            r4, g5, {**r6, "product_artifact_set_sha256": "0" * 64}, g6,
        )),
        ("matrix-open-row", lambda: validate_matrix({
            **a2,
            "summary": {**a2["summary"], "new_OPEN_rows": 1},
        })),
        ("G2-threshold-forged", lambda: validate_g2({
            **g2,
            "observations": {
                **g2["observations"],
                "delta_frames_per_1000": 45,
                "dominant_GC_lever": True,
            },
        })),
        ("premature-promotion", lambda: validate_not_promoted({
            **register,
            "promotions": [
                *register["promotions"], {"id": "v1.2.2-premature"},
            ],
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
        + ", ".join(name for name, _ in checks if name not in rejected),
    )
    return {
        "attempted": len(checks),
        "rejected": len(rejected),
        "names": rejected,
    }


def expected() -> dict[str, Any]:
    r4 = load(R4_ASSERTIONS)
    g5 = load(G5)
    g2 = load(G2)
    r6 = load(R6)
    g6 = load(G6)
    a1 = load(A1)
    a2 = load(A2)
    register = load(REGISTER)
    validate_chain(r4, g5, r6, g6)
    validate_matrix(a2)
    validate_g2(g2)
    validate_not_promoted(register)
    validate_private_remote()
    require(
        a1.get("status") == "passed-prechain-hygiene"
        and a1.get("equivalence", {}).get("lanes_executed") == 11
        and a1.get("equivalence", {}).get("cases_executed") == 447
        and a1.get("document_index", {}).get("tracked_documents") == 230,
        "A1 execution witness drift",
    )
    require(
        sha256(SEAL) == SEAL_SHA256 and SEAL.stat().st_size == SEAL_BYTES,
        "acceptance seal identity drift",
    )
    seal_output = run(
        [sys.executable, str(SEAL_TOOL), "verify", str(SEAL)]
    )
    require(
        "C2-LITE R6/G6 SEAL OFFLINE PASS files=540 "
        f"source={SEAL_SOURCE} release=v1.2.2-acceptance" in seal_output,
        "isolated acceptance seal verification witness absent",
    )
    harness_rows = []
    for path in HARNESS_FIRST_REDS:
        value = load(path)
        harness_rows.append({
            "id": value.get("id", value.get("classification", path.stem)),
            "classification": value.get(
                "classification", "harness-only",
            ),
            "disposition": value.get(
                "result", value.get("status", "bound"),
            ),
            "receipt": bind(path),
        })
    mutations = mutation_checks(
        r4, g5, r6, g6, g2, a2, register,
    )
    return {
        "format": FORMAT,
        "version": 1,
        "status": "halt-A-ready-owner-review-required",
        "decision_requested": (
            "accept the fresh v1.2.2 chain and authorize Phase B release "
            "preparation; no promotion occurs before this decision"
        ),
        "candidate": {
            "release": "v1.2.2",
            "product_artifact_set_sha256": PRODUCT_SET,
            "package_set_sha256": PACKAGE_SET,
            "promotion_state": "not-promoted",
        },
        "chain": {
            "A1": {
                "status": "passed",
                "lanes": 11,
                "executed_cases": 447,
                "documents": 230,
                "receipt": bind(A1),
            },
            "A2": {
                "status": "passed-no-new-open-row",
                "rows": 25,
                "rederived": ["E5"],
                "explicit_not_rederived": 24,
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
                    {
                        "id": row["id"],
                        "claim": row["claim"],
                        "status": row["status"],
                        "value_string": row["value_string"],
                    }
                    for row in g5["cases"]
                ],
                "receipt": bind(G5),
            },
            "G2_informational_measurement": {
                "status": "passed-not-an-acceptance-criterion",
                "value_string": g2["observations"]["value_string"],
                "threshold_frames": 44.5,
                "threshold_met": False,
                "disposition": "no-GC-cut-authorized",
                "receipt": bind(G2),
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
                "remote_head_at_seal": SEAL_SOURCE,
                "current_remote_contains_source": True,
                "archive": bind(SEAL),
                "files": 540,
                "bindings": 129,
                "claim": "acceptance-sealed-v1.2.2-not-promoted",
            },
        },
        "harness_only_first_reds": harness_rows,
        "known_nonblocking_positions": [
            "cartridge interrupt storms remain unsupported",
            "intermittent post-GC OOM remains unreproduced and documented",
            "defstruct/dynamic library freight remains parked",
            "fail-closed red-frame guard remains intentionally terse",
            "C1, E3 and E4 remain explicit C2.3 deferrals",
        ],
        "mutations": mutations,
        "authority": {
            "release_plan": bind(PLAN),
            "promotion_register": bind(REGISTER),
            "verifier": bind(Path(__file__)),
        },
        "claim_limit": (
            "Halt-A review package only. It does not prepare release notes, "
            "promote, create a tag, push public main or publish v1.2.2. "
            "The G2 measurement is informational and cannot make G5 red."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "verify"))
    args = parser.parse_args()
    try:
        value = expected()
        encoded = json.dumps(
            value, indent=2, sort_keys=True, ensure_ascii=True,
        ) + "\n"
        if args.action == "write":
            RECEIPT.write_text(encoded, encoding="utf-8")
            print(
                "c2-v1.2.2-halt-a: READY A1=447 A2=25 "
                "G5=9/9 G2=0f/1000 G6=5/5 seal=verified mutations=6/6"
            )
        else:
            require(RECEIPT.is_file(), f"missing receipt: {RECEIPT}")
            require(
                RECEIPT.read_text(encoding="utf-8") == encoded,
                "tracked Halt-A receipt drift",
            )
            print(
                "c2-v1.2.2-halt-a: VERIFY PASS "
                "promotion=not-promoted owner-review=required"
            )
        return 0
    except (
        HaltError, OSError, UnicodeError, json.JSONDecodeError,
        KeyError, TypeError, ValueError,
    ) as error:
        print(f"c2-v1.2.2-halt-a: FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
