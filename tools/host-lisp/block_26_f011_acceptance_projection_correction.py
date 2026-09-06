#!/usr/bin/env python3
"""Correct r3 Annex normalization and close the qualification resolver set."""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import block_26_f011_acceptance_normalization_red as RED  # noqa: E402
import block_26_f011_acceptance_successor_conversion as PREVIOUS  # noqa: E402
import block_26_f011_map_abort_repair_product_card as CARD  # noqa: E402
import c2_v160_r1_stored_world_conversions as ACCEPT  # noqa: E402
import evidence_era as ERA


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.6-correctness-and-build-integrity-work-plan.md"
AUTHORIZATION = "111421f8"
PLAN_HEADER = (
    "## Reviewer disposition — card 2 r3 annex projection correction — 2026-09-03"
)
RECEIPT = ARCH / "block-2.6-card2-f011-r3-acceptance-projection-correction.json"
REPORT = ROOT / "docs/planning/2.6-card2-f011-r3-acceptance-projection-correction.md"
FORMAT = "lisp65-block-2.6-card2-f011-r3-acceptance-projection-correction-v1"
STATUS = "PASS: ANNEX NORMALIZATION PROJECTION-ONLY; QUALIFICATION POPULATION DERIVED"
INVENTORY_SEAL = '9cdd829a'


class ProjectionCorrectionError(RuntimeError):
    pass


class ComparisonCompleted(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProjectionCorrectionError(message)


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


def authority() -> dict[str, Any]:
    relative = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{relative}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = raw.decode()
    require(text.count(PLAN_HEADER) == 1, "projection authority drift")
    payload = (PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]).split(
        "\n## ", 1)[0].rstrip().encode() + b"\n"
    folded = " ".join(payload.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("only in the fixed-projection comparison", "untouched",
                  "read-only", "no wplto", "qualification/acceptance chain"):
        require(token in folded, f"projection authority token absent: {token}")
    return {"commit": AUTHORIZATION, "path": relative,
        "section": PLAN_HEADER, "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "normalization_red": bind(RED.RECEIPT),
        "predecessor_conversion": bind(PREVIOUS.RECEIPT)}


def _call_name(node: ast.expr) -> str:
    return ast.unparse(node)


def qualification_chain_population(
        source_overrides: dict[str, str] | None = None) -> dict[str, Any]:
    """Derive all local stages and qualified consumers from both live chains."""
    overrides = source_overrides or {}
    specs = ((ACCEPT.DRIVER, "acceptance_child"), (CARD.DRIVER, "resume"))
    chains = []
    for path, root in specs:
        relative = path.relative_to(ROOT).as_posix()
        source = overrides.get(relative, path.read_text(encoding="utf-8"))
        tree = ast.parse(source)
        functions = {node.name: node for node in tree.body
                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        require(root in functions, f"qualification root absent: {relative}:{root}")
        reachable: set[str] = set()
        pending = [root]
        while pending:
            name = pending.pop()
            if name in reachable:
                continue
            reachable.add(name)
            local = {call.func.id for call in ast.walk(functions[name])
                     if isinstance(call, ast.Call)
                     and isinstance(call.func, ast.Name)
                     and call.func.id in functions}
            pending.extend(sorted(local - reachable))
        qualified = sorted({(caller, _call_name(call.func))
            for caller in reachable for call in ast.walk(functions[caller])
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)})
        chains.append({"module": relative, "root": root,
            "reachable_functions": sorted(reachable),
            "qualified_consumers": [
                {"caller": caller, "callee": callee}
                for caller, callee in qualified]})
    require(any(row == {"caller": "acceptance_golden_gate",
                        "callee": "golden.compare_layout"}
                for chain in chains for row in chain["qualified_consumers"])
            and any(row == {"caller": "resume", "callee": "R2.CARD.run_child"}
                for chain in chains for row in chain["qualified_consumers"]),
            "qualification chain omits comparison or resume consumer")
    return {"derivation": "transitive local call graph plus qualified call sites",
        "chains": chains,
        "reachable_functions": sum(len(row["reachable_functions"])
                                   for row in chains),
        "qualified_consumers": sum(len(row["qualified_consumers"])
                                   for row in chains)}


def validate_population(value: dict[str, Any],
        source_overrides: dict[str, str] | None = None) -> dict[str, Any]:
    require(value == qualification_chain_population(source_overrides),
            "qualification/Acceptance resolver population is stale")
    return value


def population_mutations() -> list[str]:
    current = qualification_chain_population()
    accept_relative = ACCEPT.DRIVER.relative_to(ROOT).as_posix()
    accept_source = ACCEPT.DRIVER.read_text(encoding="utf-8")
    cases: dict[str, tuple[dict[str, Any], dict[str, str]]] = {}
    omitted = deepcopy(current)
    target = next(row for row in omitted["chains"]
                  if row["root"] == "acceptance_child")
    target["qualified_consumers"].pop()
    omitted["qualified_consumers"] -= 1
    cases["reachable-qualification-consumer-omitted"] = (omitted, {})
    injected = accept_source.replace(
        "    result_path = acceptance_result_path()\n",
        "    _mutation.resolve_candidate(paths if 'paths' in locals() else elf)\n"
        "    result_path = acceptance_result_path()\n", 1)
    cases["new-qualification-consumer-uninventoried"] = (
        current, {accept_relative: injected})
    missing_root = accept_source.replace("def acceptance_child() -> int:",
        "def mutation_acceptance_child() -> int:", 1)
    cases["qualification-root-removed"] = (
        current, {accept_relative: missing_root})
    rejected = []
    for label, (value, overrides) in cases.items():
        try:
            validate_population(value, overrides)
        except (ProjectionCorrectionError, SyntaxError, KeyError, ValueError):
            rejected.append(label)
    require(rejected == list(cases), "qualification population mutation survived")
    return rejected


def full_comparison_probe() -> dict[str, Any]:
    """Run the real v5 comparison through geometry, then stop before writes."""
    captured: dict[str, Any] = {}
    successor: dict[str, Any] = {}
    original_compare = ACCEPT.V5_GOLDEN.compare_layout
    original_successor = ACCEPT.candidate_fixed_successors

    def prove(layout: dict[str, Any], authority_value: dict[str, Any]
              ) -> dict[str, Any]:
        value = original_successor(layout, authority_value)
        successor.update(value)
        return value

    def compare(layout: dict[str, Any], golden: dict[str, Any] | None = None,
                **kwargs: Any) -> dict[str, Any]:
        value = original_compare(layout, golden, **kwargs)
        captured.update(value)
        raise ComparisonCompleted("full projection and geometry completed")

    ACCEPT.candidate_fixed_successors = prove
    ACCEPT.V5_GOLDEN.compare_layout = compare
    try:
        CARD.patch_card()
        CARD.R2.CARD.child("_accept")
    except ComparisonCompleted:
        pass
    finally:
        ACCEPT.candidate_fixed_successors = original_successor
        ACCEPT.V5_GOLDEN.compare_layout = original_compare
    island = successor.get("resident_island", {})
    require(captured.get("comparison") ==
                "dependent-address-plus-freight-boundaries-exact"
            and captured.get("normalized_fixed_members") == [
                ".lisp65_resident_island_annex.vma"]
            and len(captured.get("capacity_measurements", [])) == 11
            and island.get("annex_vma") == island.get("derived_annex_vma")
            and island.get("combined_margin_bytes") == 28,
            "projection correction did not complete full downstream geometry")
    return {"comparison": captured, "candidate_successors": successor,
        "downstream_geometry_executed": True,
        "candidate_layout_mutated": False}


def derive() -> dict[str, Any]:
    probe = full_comparison_probe()
    population = qualification_chain_population()
    return {"format": FORMAT, "recorded_on": "2026-09-03",
        "status": STATUS, "authority": authority(),
        "frozen_pair": {"ELF": bind(CARD.ELF), "PRG": bind(CARD.PRG)},
        "projection_correction": probe,
        "qualification_chain_population": population,
        "population_mutations_rejected": population_mutations(),
        "normalization_policy": {
            "semantic_proof_precedes_projection": True,
            "projection_only": [".lisp65_resident_island_annex.vma"],
            "geometry_consumes_unmodified_candidate_layout": True,
            "sealed_v5_modified": False},
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "scope_runs": 0, "acceptance_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "next": "commit correction, then resume Acceptance read-only over r3"}


def report(value: dict[str, Any]) -> str:
    comparison = value["projection_correction"]["comparison"]
    island = value["projection_correction"]["candidate_successors"][
        "resident_island"]
    population = value["qualification_chain_population"]
    return f"""# Block 2.6 Card 2 — r3 Annex projection correction

Status: **{value['status']}**

The final-ELF proof derives Annex VMA `{island['annex_vma']:#x}` from the
Island end and emitted alignment before comparison. Only that fixed-projection
member is normalized; the full downstream capacity/load geometry executed on
the untouched candidate layout (**{len(comparison['capacity_measurements'])}**
capacity measurements, 28 bytes combined Island/Annex margin). This closes the
21-byte false overlap in the preceding conversion fixture without touching the
sealed v5 artifact or the frozen product pair.

The pre-resume inventory now derives both live chains: Acceptance and its
read-only Resume. It found **{population['reachable_functions']}** reachable
local functions and **{population['qualified_consumers']}** qualified consumers,
including `golden.compare_layout` and `R2.CARD.run_child`. Missing, new and
rootless chain mutations all fall.

The correction used zero WPLTOs, links, media builds or device contacts. The
next operation is the authorized read-only Acceptance resume over r3.
"""


def validate(value: dict[str, Any]) -> None:
    probe = value["projection_correction"]
    comparison = probe["comparison"]
    island = probe["candidate_successors"]["resident_island"]
    require(value["format"] == FORMAT and value["status"] == STATUS
            and value["authority"] == authority()
            and value["frozen_pair"] == {
                "ELF": bind(CARD.ELF), "PRG": bind(CARD.PRG)}
            and comparison["normalized_fixed_members"] == [
                ".lisp65_resident_island_annex.vma"]
            and len(comparison["capacity_measurements"]) == 11
            and probe["downstream_geometry_executed"] is True
            and probe["candidate_layout_mutated"] is False
            and island["annex_vma"] == island["derived_annex_vma"]
            and island["combined_margin_bytes"] == 28
            and value["normalization_policy"] == {
                "semantic_proof_precedes_projection": True,
                "projection_only": [
                    ".lisp65_resident_island_annex.vma"],
                "geometry_consumes_unmodified_candidate_layout": True,
                "sealed_v5_modified": False}
            and validate_population(value["qualification_chain_population"],
                {p.relative_to(ROOT).as_posix(): ERA.era_blob(INVENTORY_SEAL,
                    p.relative_to(ROOT).as_posix()).decode()
                 for p in (ACCEPT.DRIVER, CARD.DRIVER)}) ==
                value["qualification_chain_population"]
            and value["population_mutations_rejected"] == [
                "reachable-qualification-consumer-omitted",
                "new-qualification-consumer-uninventoried",
                "qualification-root-removed"]
            and value["attempt_accounting"]["WPLTO_runs"] == 0
            and value["attempt_accounting"]["product_links"] == 0,
            "Annex projection correction drift")


def write() -> None:
    require(not RECEIPT.exists() and not REPORT.exists(),
            "projection correction is one-shot")
    value = derive()
    RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(report(value), encoding="utf-8")
    validate(value)
    validate_population(qualification_chain_population())
    population_mutations()
    print("Block 2.6 Card 2: ANNEX PROJECTION CORRECTION PASS")


def check() -> None:
    value = load(RECEIPT)
    validate(value)
    validate_population(qualification_chain_population())
    population_mutations()
    require(REPORT.read_text(encoding="utf-8") == report(value),
            "projection correction report drift")
    print("Block 2.6 Card 2: ANNEX PROJECTION CORRECTION CHECK PASS")


def selftest() -> None:
    value = load(RECEIPT)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "projection-broadened": lambda row: row["normalization_policy"][
            "projection_only"].append(".text.vma"),
        "geometry-not-executed": lambda row: row["projection_correction"].update(
            downstream_geometry_executed=False),
        "qualification-consumer-omitted": lambda row: row[
            "qualification_chain_population"]["chains"][0][
                "qualified_consumers"].pop(),
        "live-population-in-sealed-receipt": lambda row: row.update(
            qualification_chain_population=qualification_chain_population()),
        "link-hidden": lambda row: row["attempt_accounting"].update(
            product_links=1),
    }
    rejected = []
    for label, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate(trial)
        except (ProjectionCorrectionError, RuntimeError, KeyError, ValueError):
            rejected.append(label)
    require(rejected == list(cases), "projection correction mutation survived")
    print(f"Block 2.6 Card 2: PROJECTION CORRECTION SELFTEST mutations={len(rejected)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    action = parser.parse_args().action
    {"write": write, "check": check, "selftest": selftest}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ProjectionCorrectionError, RuntimeError, KeyError, ValueError,
            OSError, subprocess.CalledProcessError) as error:
        print(f"Block 2.6 Card 2 projection correction: FAIL {error}",
              file=sys.stderr)
        raise SystemExit(1)
