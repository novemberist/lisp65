#!/usr/bin/env python3
"""Permanent host-first gate for the Phase-V1 base-composition PRNG."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-random-contract.json"
SOURCE = ROOT / "lib/stdlib-random.lisp"
SUITE = ROOT / "tests/bytecode/libs/p0-stdlib-random-base.json"
BASE_SUITE = ROOT / "tests/bytecode/libs/p0-stdlib-require-resolver.json"
PROFILE = ROOT / "config/c2-l-full-product-profile.json"
BUILD = ROOT / "build/post-promotion/phase-v/random-base/gate"
BASE_PREFIX = BUILD / "base/stdlib-p0"
CANDIDATE_PREFIX = BUILD / "candidate/stdlib-p0"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1-random-base-host-first-receipt.json"
)
POST_TIME_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1-random-base-post-time-revalidation-receipt.json"
)
FINAL_COMPOSITION_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1-random-base-final-composition-revalidation-receipt.json"
)
CURRENT_COMPOSITION_RECEIPT = BUILD / "v1.2.5-current-composition.json"
PUBLIC_BUILD_RECEIPT = BUILD / "public-build-current-source-receipt.json"
RANDOM_NAMES = [
    "%random-add14",
    "%random-seed-step",
    "%random-normalize-seed",
    "%random-fill",
    "random-seed",
    "%random-hardware-seed",
    "%random-ensure-state",
    "%random-next",
    "%random-16384-remainder",
    "%random-draw-below",
    "random",
]


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"bound input absent: {path}")
    data = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def validate(contract: dict[str, Any], source: str, suite: dict[str, Any]) -> dict[str, Any]:
    public = contract["public_surface"]
    generator = contract["generator"]
    placement = contract["placement"]
    require(
        contract["format"] == "lisp65-c2-random-base-composition-v1"
        and public["random"]["syntax"] == "(random n)"
        and public["random-seed"]["syntax"] == "(random-seed seed)"
        and generator["kind"] == "additive lagged Fibonacci"
        and generator["recurrence"]
        == "X(n) = (X(n-24) + X(n-55)) mod 16384"
        and "rejection sampling" in generator["range_mapping"]
        and generator["plain_modulo_bias"] == "forbidden",
        "random semantic contract drift",
    )
    require(
        placement == {
            "code": "Bank-2 base composition",
            "resident_code_bytes": 0,
            "resident_state_bytes": 0,
            "new_resident_gc_roots": 0,
            "static_plane_root_records": 0,
            "runtime_overlay_records": 0,
            "require_dependency": False,
        },
        "random placement contract drift",
    )
    required_source = (
        "(defun %random-add14 (a b)",
        "(let ((room (- 16383 a)))",
        "(if (> b room)",
        "(defun %random-seed-step (value)",
        "(if (>= value 6411) (- value 6411) (+ value 9973))",
        "(defun %random-normalize-seed (seed)",
        "(%random-fill 55 normalized nil)",
        "(set-symbol-value '%random-index 0)",
        "(peek 208 18)",
        "(peek 220 4)",
        "(peek 221 4)",
        "(peek 212 27)",
        "(nthcdr (mod (+ index 31) 55) state)",
        "(rplaca oldest value)",
        "(set-symbol-value '%random-index (mod (+ index 1) 55))",
        "(defun %random-16384-remainder (n)",
        "(if (<= value last-accepted)",
        "(%random-draw-below n last-accepted)",
        "(- 16383 (%random-16384-remainder n))",
    )
    require(all(token in source for token in required_source),
            "random source seam drift")
    require(
        "(require " not in source
        and "poll-key" not in source
        and "read-key" not in source
        and "*loaded-libs*" not in source,
        "random introduced require/input-consuming/shadow-registry dependency",
    )
    require(
        suite["extends"] == "p0-stdlib-require-resolver.json"
        and suite["sources"] == ["lib/stdlib-random.lisp"]
        and suite["functions"] == RANDOM_NAMES
        and suite["tailcall_self"] == [
            "%random-fill", "%random-draw-below"]
        and any(row["name"] == "random-rejection-path"
                and row["expect"] == "179"
                for row in suite["cases"]),
        "random suite/composition drift",
    )
    return {
        "status": "passed-source-contract-and-base-composition",
        "public_functions": ["random", "random-seed"],
        "private_functions": len(RANDOM_NAMES) - 2,
        "state_slots": 55,
        "lags": [24, 55],
        "range_size": 16384,
        "resident_delta_bytes": 0,
        "runtime_overlay_records": 0,
        "require_dependency": False,
    }


def mutation_tests(
    contract: dict[str, Any], source: str, suite: dict[str, Any]
) -> dict[str, str]:
    mutants: list[tuple[str, dict[str, Any], str, dict[str, Any]]] = []

    def source_mutation(label: str, old: str, new: str) -> None:
        require(old in source, f"mutation anchor absent: {label}")
        mutants.append((label, contract, source.replace(old, new, 1), suite))

    source_mutation(
        "plain-modulo-bias",
        "(if (<= value last-accepted)\n        (mod value n)\n        (%random-draw-below n last-accepted))",
        "(mod value n)",
    )
    source_mutation(
        "state-width-54",
        "(%random-fill 55 normalized nil)",
        "(%random-fill 54 normalized nil)",
    )
    source_mutation(
        "lag-24-index-30",
        "(nthcdr (mod (+ index 31) 55) state)",
        "(nthcdr (mod (+ index 30) 55) state)",
    )
    source_mutation(
        "overflow-safe-add-removed",
        "(if (> b room)\n        (- b (+ room 1))\n        (+ a b))",
        "(+ a b)",
    )
    source_mutation(
        "consuming-key-seed",
        "(peek 212 27)",
        "(poll-key)",
    )
    source_mutation(
        "require-dependency",
        "(defun %random-add14 (a b)",
        "(require 'random-support)\n\n(defun %random-add14 (a b)",
    )
    source_mutation(
        "cursor-not-advanced",
        "(set-symbol-value '%random-index (mod (+ index 1) 55))",
        "(set-symbol-value '%random-index index)",
    )
    bad_contract = copy.deepcopy(contract)
    bad_contract["placement"]["resident_state_bytes"] = 2
    mutants.append(("native-state", bad_contract, source, suite))

    bad_suite = copy.deepcopy(suite)
    bad_suite["extends"] = "p0-defstruct-v1-lib.json"
    mutants.append(("parked-defstruct-dependency", contract, source, bad_suite))

    rejected: dict[str, str] = {}
    for label, candidate_contract, candidate_source, candidate_suite in mutants:
        try:
            validate(candidate_contract, candidate_source, candidate_suite)
        except GateError as error:
            rejected[label] = str(error)
        else:
            raise GateError(f"random mutation survived: {label}")
    return rejected


def compile_suite(suite: Path, prefix: Path) -> dict[str, Any]:
    prefix.parent.mkdir(parents=True, exist_ok=True)
    observation = prefix.with_suffix(".observations.json")
    run = subprocess.run(
        [
            sys.executable,
            "tools/host-lisp/bytecode_p0_stdlib.py",
            "--check",
            "--emit-artifacts",
            str(prefix.relative_to(ROOT)),
            "--observation-report",
            str(observation.relative_to(ROOT)),
            str(suite.relative_to(ROOT)),
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    require(run.returncode == 0, f"random suite compile red:\n{run.stdout}")
    manifest = load(prefix.with_suffix(".manifest.json"))
    return {
        "manifest": manifest,
        "stdout": run.stdout.strip().splitlines(),
        "observation": bind(observation),
    }


def artifact_gate() -> dict[str, Any]:
    baseline = compile_suite(BASE_SUITE, BASE_PREFIX)
    candidate = compile_suite(SUITE, CANDIDATE_PREFIX)
    old = baseline["manifest"]
    new = candidate["manifest"]
    code_delta = int(new["code_bytes"]) - int(old["code_bytes"])
    dir_delta = int(new["directory_bytes"]) - int(old["directory_bytes"])
    object_delta = int(new["objects"]) - int(old["objects"])
    literal_delta = (
        sum(int(row["lit_count"]) for row in new["entries"])
        - sum(int(row["lit_count"]) for row in old["entries"])
    )
    new_names = [row["name"] for row in new["entries"][-len(RANDOM_NAMES):]]
    require(
        code_delta == 489
        and dir_delta == 77
        and object_delta == len(RANDOM_NAMES)
        and literal_delta == 31
        and new_names == RANDOM_NAMES,
        "random artifact delta or suffix inventory drift",
    )

    profile = load(PROFILE)
    bank2 = profile["bank2_static_code"]
    random_delta = profile["random_base_delta"]
    while_delta = profile["while_delta"]
    fx_delta = profile["fx_base_delta"]
    time_delta = profile.get("time_base_delta")
    option_a = profile.get("require_prior_append_option_A_delta")
    time_code = 0 if time_delta is None else int(
        time_delta["stdlib_code_bytes"])
    time_entries = 0 if time_delta is None else int(
        time_delta["new_entries"])
    time_resolutions = 0 if time_delta is None else int(
        time_delta["new_resolutions"])
    geometry = {
        "bank2_static_code_bytes": (
            int(bank2["bytes"])
            - int(random_delta["stdlib_code_bytes"])
            - int(while_delta["lcc_code_bytes"])
            - int(fx_delta["stdlib_code_bytes"])
            - time_code
            - (0 if option_a is None
               else int(option_a["stdlib_code_bytes"]))
        ),
        "entries": (
            int(profile["entries"])
            - int(random_delta["new_entries"])
            - int(while_delta["new_entries"])
            - int(fx_delta["new_entries"])
            - time_entries
            - (0 if option_a is None else int(option_a["new_entries"]))
        ),
        "resolutions": (
            int(profile["resolutions"])
            - int(random_delta["new_resolutions"])
            - int(while_delta["new_resolutions"])
            - int(fx_delta["new_resolutions"])
            - time_resolutions
            - (0 if option_a is None
               else int(option_a["new_resolutions"]))
        ),
        "roots": int(profile["roots"]),
    }
    require(
        profile["format"] == "lisp65-c2-l-full-product-profile-v1"
        and fx_delta["resident_bytes"] == 0
        and fx_delta["new_roots"] == 0
        and fx_delta["new_direct_entry_refs"] == 0
        and geometry["bank2_static_code_bytes"] == 40746
        and geometry["entries"] == 682
        and geometry["resolutions"] == 2711
        and geometry["roots"] == 340,
        "tracked Link-76-relative capacity reconstruction drift",
    )
    projected = {
        "bank2_static_code_bytes": geometry["bank2_static_code_bytes"] + code_delta,
        "bank2_headroom_bytes": 65536
        - (geometry["bank2_static_code_bytes"] + code_delta),
        "entries": geometry["entries"] + object_delta,
        "entry_headroom": 2048 - (geometry["entries"] + object_delta),
        "resolutions": geometry["resolutions"] + literal_delta,
        "resolution_headroom": 4096
        - (geometry["resolutions"] + literal_delta),
        "roots": geometry["roots"],
        "root_headroom": 1536 - geometry["roots"],
    }
    require(all(value >= 0 for key, value in projected.items()
                if key.endswith("headroom") or key.endswith("headroom_bytes")),
            "random projected static-plane capacity red")
    return {
        "baseline": {
            "code_bytes": int(old["code_bytes"]),
            "directory_bytes": int(old["directory_bytes"]),
            "objects": int(old["objects"]),
            "manifest": bind(BASE_PREFIX.with_suffix(".manifest.json")),
        },
        "candidate": {
            "code_bytes": int(new["code_bytes"]),
            "directory_bytes": int(new["directory_bytes"]),
            "objects": int(new["objects"]),
            "manifest": bind(CANDIDATE_PREFIX.with_suffix(".manifest.json")),
        },
        "delta": {
            "bank2_code_bytes": code_delta,
            "directory_bytes": dir_delta,
            "objects": object_delta,
            "resolution_words": literal_delta,
            "resident_bytes": 0,
        },
        "projected_post_Link76": projected,
        "candidate_stdout": candidate["stdout"],
        "candidate_observation": candidate["observation"],
    }


def main(*, public_build: bool = False) -> int:
    try:
        contract = load(CONTRACT)
        source = SOURCE.read_text(encoding="utf-8")
        suite = load(SUITE)
        source_proof = validate(contract, source, suite)
        mutations = mutation_tests(contract, source, suite)
        artifacts = artifact_gate()
        receipt = {
            "format": "lisp65-c2.2-v1-random-base-host-first-receipt-v1",
            "recorded_on": "2026-07-28",
            "status": "passed-random-base-host-first-and-capacity-projection",
            "promotable": False,
            "product_links": 0,
            "hardware_runs": 0,
            "source_contract": source_proof,
            "mutations_rejected": mutations,
            "artifacts": artifacts,
            "authority": {
                "contract": bind(CONTRACT),
                "source": bind(SOURCE),
                "suite": bind(SUITE),
                "baseline_suite": bind(BASE_SUITE),
                "product_profile": bind(PROFILE),
                "gate": bind(Path(__file__)),
            },
            "next_gate": (
                "Owner review of the V2 while contract at Halt #3; one later "
                "product-shaped link and the final bundled hardware session."
            ),
            "claim_limit": (
                "Host compiler/VM execution and a Link-76-relative Bank-2/"
                "C2D capacity projection only. No product link, target timing, "
                "hardware entropy-quality or on-metal random claim."
            ),
        }
        profile = load(PROFILE)
        current_successor = (
            profile.get("require_prior_append_option_A_delta") is not None)
        target = (
            PUBLIC_BUILD_RECEIPT
            if public_build
            else CURRENT_COMPOSITION_RECEIPT
            if current_successor
            else FINAL_COMPOSITION_RECEIPT
            if profile.get("product_build_id") == "0x15da63c2"
            else POST_TIME_RECEIPT
            if profile.get("time_base_delta") is not None
            else RECEIPT
        )
        if public_build:
            receipt["status"] = (
                "passed-random-base-current-source-public-build"
            )
            receipt["composition"] = {
                "successors": ["fx", "time"],
                "release_banner": "WORKBENCH 1.2.4",
                "product_build_id": "0x15da63c2",
                "private_evidence_inputs": 0,
            }
            receipt["claim_limit"] = (
                "Current public source/artifact semantics and capacity only; "
                "historical proof receipts and hardware claims are not inputs."
            )
        elif current_successor:
            receipt["status"] = (
                "passed-random-base-in-current-successor-composition")
            receipt["composition"] = {
                "successors": ["fx", "time", "require-option-A"],
                "product_build_id": profile["product_build_id"],
                "final_v1.2.4_authority": bind(FINAL_COMPOSITION_RECEIPT),
            }
        elif target == FINAL_COMPOSITION_RECEIPT:
            receipt["status"] = (
                "passed-random-base-in-final-v1.2.4-composition"
            )
            receipt["composition"] = {
                "successors": ["fx", "time"],
                "release_banner": "WORKBENCH 1.2.4",
                "product_build_id": "0x15da63c2",
                "original_receipt": bind(RECEIPT),
                "post_time_receipt": bind(POST_TIME_RECEIPT),
            }
        if not public_build and target == POST_TIME_RECEIPT:
            receipt["status"] = (
                "passed-random-base-revalidated-in-fx-time-composition"
            )
            receipt["composition"] = {
                "successors": ["fx", "time"],
                "original_receipt": bind(RECEIPT),
            }
        atomic_json(target, receipt)
        delta = artifacts["delta"]
        projected = artifacts["projected_post_Link76"]
        print(
            "c2-random-base-gate: PASS "
            f"bank2=+{delta['bank2_code_bytes']} "
            f"dir=+{delta['directory_bytes']} "
            f"objects=+{delta['objects']} "
            f"headroom={projected['bank2_headroom_bytes']} "
            f"mutations={len(mutations)} resident=+0 hardware=0"
        )
        return 0
    except (GateError, KeyError, OSError, ValueError) as error:
        print(f"c2-random-base-gate: FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
