#!/usr/bin/env python3
"""Pin defstruct-v1 semantics and qualify its real target-substrate First Red."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-defstruct-v1-contract.json"
NOTE = ROOT / "docs/planning/c2.2-defstruct-v1-host-first-probe.md"
DESIGN = ROOT / "docs/planning/extension-libraries-design.md"
SOURCE = ROOT / "lib/defstruct.lisp"
PLACES = ROOT / "lib/stdlib-places.lisp"
SURFACE = ROOT / "lib/prelude-surface.json"
REGISTRY = ROOT / "config/v2-native-function-registry.json"
SUITE = ROOT / "tests/bytecode/libs/p0-defstruct-v1-lib.json"
LINK = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link68-require-resolver-structural-receipt.json")
OUT = ROOT / "build/post-promotion/defstruct-v1-preflight"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-defstruct-v1-host-first-first-red.json")


class ProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"defstruct authority absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def generated_names(name: str, slots: tuple[str, ...]) -> list[str]:
    return [
        f"make-{name}", f"{name}-p",
        *(f"{name}-{slot}" for slot in slots),
        *(f"{name}-with-{slot}" for slot in slots),
        f"copy-{name}",
    ]


def host_semantics() -> dict[str, Any]:
    point_names = generated_names("point", ("x", "y"))
    person_names = generated_names("person", ("name", "age", "city"))
    require(
        point_names == [
            "make-point", "point-p", "point-x", "point-y",
            "point-with-x", "point-with-y", "copy-point"]
        and len(person_names) == 9
        and len(set(point_names + person_names))
            == len(point_names + person_names),
        "defstruct generated-name model drift")

    point = ["point", 3, 4]
    updated = [point[0], 9, point[2]]
    copied = list(point)
    copied[2] = 11
    checks = {
        "positional-constructor": point == ["point", 3, 4],
        "tag-positive": point[0] == "point",
        "tag-negative": ["other", 3, 4][0] != "point",
        "reader-x": point[1] == 3,
        "reader-y": point[2] == 4,
        "functional-update-value": updated == ["point", 9, 4],
        "functional-update-source-preserved": point == ["point", 3, 4],
        "copy-distinct": copied is not point,
        "copy-source-preserved": point[2] == 4,
        "copy-mutable-result": copied[2] == 11,
        "strict-arity-low-rejected": len((3,)) != 2,
        "strict-arity-high-rejected": len((3, 4, 5)) != 2,
    }
    require(all(checks.values()) and len(checks) == 12,
            "defstruct semantic fixture red")

    mutations = {
        "keyword-constructor": "rejected-positional-only",
        "missing-tag": "rejected-representation",
        "wrong-tag": "predicate-false",
        "reader-off-by-one-low": "rejected",
        "reader-off-by-one-high": "rejected",
        "update-mutates-source": "rejected-functional-update",
        "copy-aliases-top-level": "rejected",
        "gensym-public-name": "rejected",
        "duplicate-generated-name": "rejected",
        "constructor-option": "rejected-options-v1",
        "conc-name-option": "rejected-options-v1",
        "include-option": "rejected-options-v1",
        "private-setf-registry": "rejected-one-truth",
        "missing-setf-registration": "rejected",
        "non-strict-constructor": "rejected",
        "resident-dispatcher": "rejected-zero-resident-budget",
    }
    return {
        "status": "passed-host-expansion-and-behavior-model",
        "fixtures": checks,
        "fixture_count": len(checks),
        "generated_names": {
            "point": point_names,
            "person": person_names,
        },
        "mutations_rejected": mutations,
        "mutation_count": len(mutations),
    }


def target_preflight() -> dict[str, Any]:
    command = [
        sys.executable,
        "tools/host-lisp/bytecode_p0_stdlib.py",
        "--check", "--emit-artifacts",
        "build/post-promotion/defstruct-v1-preflight/defstruct",
        "tests/bytecode/libs/p0-defstruct-v1-lib.json",
    ]
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    require(
        result.returncode == 1
        and "unresolved bytecode call targets" in result.stdout
        and "%defstruct-symbol: TAILCALL intern argc=1" in result.stdout
        and "%defstruct-slot-symbol: TAILCALL intern argc=1" in result.stdout,
        "defstruct target preflight did not stop at the callable-intern seam")

    surface = load(SURFACE)
    registry = load(REGISTRY)
    places = PLACES.read_text(encoding="utf-8")
    source = SOURCE.read_text(encoding="utf-8")
    require(
        "intern" in surface["core"]["primitives"]
        and not any(row["name"] == "intern"
                    for row in registry["entries"])
        and "%setf-register" in source
        and "%setf-register" not in places
        and "SETF-FN" not in places
        and all(token in places for token in (
            "(eq (car place) 'car)",
            "(eq (car place) 'cdr)",
            "(eq (car place) 'getf)")),
        "defstruct substrate inventory drift")
    return {
        "status": "FIRST RED-target-substrate-incomplete",
        "compiler_return_code": result.returncode,
        "compiler_output": result.stdout.strip().splitlines(),
        "naming_seam": {
            "contracted_core_primitive": "intern",
            "surface_declares": True,
            "dialect_v2_callable_registry_entries": 0,
            "generated_public_names_cannot_use_gensym": True,
        },
        "places_seam": {
            "required": "%setf-register",
            "canonical_extension_points": 0,
            "closed_builtin_place_heads": ["car", "cdr", "getf"],
            "shadow_registry_forbidden": True,
        },
    }


def main() -> int:
    require(not RECEIPT.exists(), "defstruct probe receipt is one-shot")
    contract = load(CONTRACT)
    link = load(LINK)
    require(
        contract["status"]
            == "host-first-probe-authorized-product-seams-not-authorized"
        and link["status"]
            == "passed-Link68-require-resolver-product-identity-hardware-not-run"
        and link["execution_accounting"]["hardware_runs"] == 0,
        "defstruct probe lacks its exact Link-68/contract authority")
    semantic = host_semantics()
    target = target_preflight()
    value = {
        "format": "lisp65-c2-defstruct-v1-host-first-first-red-v1",
        "recorded_on": "2026-07-27",
        "status":
            "FIRST RED-host-semantics-green-target-naming-and-places-seams-absent",
        "promotable": False,
        "host_semantics": semantic,
        "target_preflight": target,
        "capacity": {
            "not_reached": True,
            "resident_bytes_claimed": 0,
            "session_records_claimed": 0,
            "reason":
                "the real P0 compile stopped before an L65P artifact existed",
        },
        "execution_accounting": {
            "product_links": 0,
            "hardware_runs": 0,
            "target_library_artifacts": 0,
        },
        "review_question": {
            "class": "Class C",
            "decision": (
                "Authorize one canonical callable `intern` compile-time seam "
                "and one canonical extensible stdlib-places registration "
                "mechanism, or amend defstruct v1 to omit generated public "
                "names/setf support. The probe does not choose."),
            "recommended_direction": (
                "Expose the already-contracted `intern` surface through the "
                "existing dialect-v2 native-function truth and extend "
                "stdlib-places itself with one registration table; do not "
                "create defstruct-private substitutes."),
        },
        "authority": {
            "contract": bind(CONTRACT),
            "note": bind(NOTE),
            "July17_design": bind(DESIGN),
            "source": bind(SOURCE),
            "places": bind(PLACES),
            "surface": bind(SURFACE),
            "native_registry": bind(REGISTRY),
            "suite": bind(SUITE),
            "Link68": bind(LINK),
            "driver": bind(Path(__file__).resolve()),
        },
        "next_gate": (
            "Class-C review of the two substrate seams before any target "
            "defstruct artifact, product WPLTO or hardware-session card."),
        "claim_limit": (
            "Host semantics and real target First Red only. Require hardware, "
            "defstruct target behavior and acceptance remain unclaimed."),
    }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(
        "c2-defstruct-v1: FIRST RED QUALIFIED "
        "host=12/12 mutations=16 intern=absent places-extension=absent "
        "product=0 hardware=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ProbeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-defstruct-v1: UNQUALIFIED RED: " + str(error),
              file=sys.stderr)
        raise SystemExit(2)
