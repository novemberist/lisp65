#!/usr/bin/env python3
"""Attribute the execution-boundary scope mutation-count stop by name."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_comfort_input_fidelity as FIDELITY  # noqa: E402
import c2_v160_execution_boundary_backstop_uint8_irq_return_replacement_card as TOP  # noqa: E402
import c2_v160_input_fidelity_reopen_card as CORE  # noqa: E402
import c2_v160_input_fidelity_reopen_replacement_card as LEAF  # noqa: E402
import c2_v21_root_padding_configurator_projection_replacement as PROJECTION  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
RED = ARCH / (
    "c2.3-v1.6-execution-boundary-backstop-uint8-irq-return-"
    "replacement-card-final-red.json")
OUT = ARCH / "c2.3-v1.6-projection-mutation-population-attribution.json"
AUTHORIZATION = "1624ef03"
FORMAT = "lisp65-c2-v160-projection-mutation-population-attribution-v1"


class AttributionError(RuntimeError):
    pass


class PopulationCaptured(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("*", "").split())
    for token in ("mutation-count attribution commissioned",
                  "expected set, the actual set and the difference",
                  "by name, not by count", "gate-integrity finding",
                  "no run, no card, no media, no device before the report"):
        require(token in text, f"mutation attribution authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def frozen_world() -> dict[str, Any]:
    red = load(RED)
    require(red["status"] == "FINAL RED: V1.6 EXECUTION BOUNDARY CARD STOPS"
            and red["error"]["message"] ==
                "feature-without-configurator-output mutation survived"
            and red["attempt_accounting"]["WPLTO_runs"] == 1
            and red["attempt_accounting"]["product_link_attempts"] == 1,
            "execution-boundary Scope red drift")
    elf = (ROOT / "build/c2.3/v1.6-execution-boundary-backstop-uint8-irq-"
           "return-replacement-card/wplto/"
           "lisp65-c2-substitution-linked.prg.elf")
    prg = elf.with_suffix("")
    require(elf.is_file() and prg.is_file(), "frozen final pair absent")
    return {"Final_Red": bind(RED), "ELF": bind(elf), "PRG": bind(prg)}


def derive_population() -> tuple[dict[str, Any], list[str]]:
    captured: dict[str, Any] = {}
    active_features: list[str] = []
    original_child = LEAF.child
    original_mutations = PROJECTION.projection_mutations

    def intercept(action: str) -> None:
        require(action == "_scope", f"unexpected attribution action: {action}")

        def observe(value: dict[str, Any]) -> list[str]:
            observed = original_mutations(value)
            captured.update(PROJECTION.projection_mutation_population(
                value, observed))
            active_features.extend(value["combined_compiler_features"])
            raise PopulationCaptured

        PROJECTION.projection_mutations = observe
        try:
            FIDELITY.derive(
                CORE.PRODUCT_ELF, output_rebind=CORE.bind_paths_only,
                expected_output_roots=CORE.roots())
        finally:
            PROJECTION.projection_mutations = original_mutations

    LEAF.child = intercept
    previous_argv = sys.argv
    sys.argv = [str(Path(__file__)), "_scope"]
    try:
        TOP.main()
    except PopulationCaptured:
        pass
    finally:
        sys.argv = previous_argv
        LEAF.child = original_child
    require(captured and active_features,
            "real Scope consumer did not expose mutation population")
    return captured, active_features


def mutation_selftest(
        population: dict[str, Any], active_features: list[str]) -> list[str]:
    rejected: list[str] = []
    expected = population["expected"]
    observed = population["observed"]
    cases = {
        "stored-feature-count-33": len(active_features) != 33,
        "stored-total-count-47": len(expected) != 47,
        "missing-named-member": bool(
            set(expected) - set(observed[:-1])),
        "unexpected-named-member": bool(
            set([*observed, "unexpected:synthetic"]) - set(expected)),
        "one-sided-report": all(name in population for name in
            ("expected", "observed", "missing", "unexpected", "survivors")),
    }
    for name, fell in cases.items():
        if fell:
            rejected.append(name)
    require(rejected == list(cases),
            "named mutation-population reporting mutation survived")
    return rejected


def derive() -> dict[str, Any]:
    before = frozen_world()
    population, active_features = derive_population()
    after = frozen_world()
    historic = load(PROJECTION.PREFLIGHT)["configurator_projection"]
    previous_features = historic["combined_compiler_features"]
    added = sorted(set(active_features) - set(previous_features))
    removed = sorted(set(previous_features) - set(active_features))
    require(population["expected_count"] == population["observed_count"] == 48
            and population["missing"] == []
            and population["unexpected"] == []
            and added == ["LISP65_C2_REFILL_BOUNDARY_WITNESS"]
            and removed == [],
            "mutation population is not the authorized-freight branch")
    require(before == after, "host-only attribution changed frozen final pair")
    return {
        "format": FORMAT, "recorded_on": "2026-08-23",
        "status": "ATTRIBUTED: LEGITIMATELY GROWN NAMED MUTATION POPULATION",
        "authority": authority(), "frozen_world": before,
        "stored_world": {
            "source": bind(PROJECTION.PREFLIGHT),
            "feature_names": previous_features,
            "feature_count_summary": len(previous_features),
            "mutation_count_pin": 47,
        },
        "candidate_world": {
            "feature_names": active_features,
            "feature_count_summary": len(active_features),
            "added_features": added, "removed_features": removed,
            "mutation_population": population,
        },
        "decision": {
            "branch": "legitimately-grown-population",
            "gate_integrity_defect": False,
            "exact_new_member": "LISP65_C2_REFILL_BOUNDARY_WITNESS",
            "successor": (
                "candidate-derived named population; no stored count"),
            "scope_resume_authorized": False,
        },
        "permanent_reporting_contract": {
            "expected": "persisted by name", "observed": "persisted by name",
            "missing": "persisted by name", "unexpected": "persisted by name",
            "counts": "summaries only; never predicates",
        },
        "mutations_rejected": mutation_selftest(population, active_features),
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "scope_resumes": 0, "media_builds": 0,
            "device_contacts": 0},
        "claim_limit": (
            "Host-only attribution and checker conversion. No Scope resume, "
            "card, WPLTO, link, media or device action."),
    }


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    require(action in {"write", "check"},
            "usage: c2_v160_projection_mutation_population_attribution.py "
            "write|check")
    value = derive()
    if action == "write":
        require(not OUT.exists(), "mutation population attribution is one-shot")
        OUT.write_bytes(canonical(value))
    else:
        require(load(OUT) == value, "mutation population attribution drift")
    print("v1.6 projection mutations: ATTRIBUTED expected=48 observed=48 "
          "missing=0 unexpected=0 branch=legitimate-growth")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"v1.6 projection mutations: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
