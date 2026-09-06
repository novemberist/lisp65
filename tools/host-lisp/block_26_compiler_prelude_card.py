#!/usr/bin/env python3
"""Build and qualify Block 2.6 Card 4 without a native product link."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
import bytecode_p0_stdlib as STDLIB  # noqa: E402
import c2_bound_artifact_source_parity as BOUND  # noqa: E402
import c2_link75_require_defstruct_host_attribution as CARRIER_HOST  # noqa: E402
import c2_v200_domain_tier1_pricing as PRICE  # noqa: E402
import dialect_v2_lcc_surface as LCC_SURFACE  # noqa: E402
import public_surface_domain_audit as AUDIT  # noqa: E402
import v2_workbench_codemod as CODEMOD_TOOL  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.6-correctness-and-build-integrity-work-plan.md"
AUTHORIZATION = "1f233541"
AUTH_HEADER = (
    "## Reviewer acceptance — card 3 A3–A6 closed; A7 pricing and card 4 open"
)
BUILD = ROOT / "build/2.6/card4-compiler-prelude"
CODEMOD = BUILD / "codemod"
SUITE = BUILD / "successor-suite.json"
PREFIX = BUILD / "stdlib-p0"
MANIFEST = PREFIX.with_suffix(".manifest.json")
BLOB = PREFIX.with_suffix(".blob.bin")
COMPILER_SUITE = BUILD / "compiler-tier/suite.json"
COMPILER_TIER = BUILD / "compiler-tier/generation.json"
COMPILER_PREFIX = BUILD / "compiler/lcc"
COMPILER_MANIFEST = COMPILER_PREFIX.with_suffix(".manifest.json")
COMPILER_BLOB = COMPILER_PREFIX.with_suffix(".blob.bin")
PREDECESSOR_COMPILER_MANIFEST = (
    ROOT / "build/post-promotion/v112/compiler/lcc.manifest.json")
PREDECESSOR_COMPILER_BLOB = (
    ROOT / "build/post-promotion/v112/compiler/lcc.blob.bin")
SOURCE_PARITY = ROOT / "tools/host-lisp/c2_bound_artifact_source_parity.py"
SOURCE_PARITY_CONTRACT = ROOT / "config/c2-bound-artifact-source-parity.json"
LOCALITY_REPLAY = ROOT / "tools/host-lisp/c2_v111_locality_replay_closure.py"
OPTION_A = ROOT / "tools/host-lisp/c2_require_prior_append_option_a_gate.py"
TOP_LEVEL_REDISPATCH = ROOT / "tools/host-lisp/c2_top_level_macro_redispatch.py"
DIRECT_EXPRESSION = ROOT / "tools/host-lisp/c2_repl_direct_expression_gate.py"
TIER1_PRICE = ROOT / "tools/host-lisp/c2_v200_domain_tier1_pricing.py"
V201_DOCS = ROOT / "tools/host-lisp/c2_v201_bundle_docs_gate.py"
PRELUDE_INVENTORY = ROOT / (
    "tests/bytecode/dialect-v2/evidence/prelude-control/"
    "dialect-v2-inventory.json")
MIGRATION_CONTRACT = ROOT / "config/dialect-migration-contract.json"
BUDGET_COMPARISON = ROOT / (
    "tests/bytecode/dialect-v2/evidence/dialect-v2-budget-comparison.json")
METADATA_INDEX = ARCH / "v11-function-metadata-index.json"
METADATA_RECEIPT = ARCH / "v11-function-metadata-contract-receipt.json"
MEASURED = ARCH / "block-2.6-card4-compiler-prelude-domain-contract.json"
RECEIPT = ARCH / "block-2.6-card4-compiler-prelude-receipt.json"
REPORT = ROOT / "docs/planning/block-2.6-card4-compiler-prelude-report.md"
BASE_SUITE = ROOT / "config/c2-v200-public-plane/resident-interactive-stdlib-suite.json"
DURABLE_CONTRACT = ROOT / "config/public-surface-domain-contract.json"
PROMOTION_AUTHORIZATION = "441ca870"
PROMOTION_RECEIPT = ARCH / "block-2.6-card4-domain-contract-promotion-receipt.json"
LCC = ROOT / "lib/lcc.lisp"
PRELUDE = ROOT / "lib/prelude-m1.lisp"
PRELUDE_MACROS = ROOT / "lib/prelude-macros.lisp"
LISTS = ROOT / "lib/dialect-v2/lists-core.lisp"
TIER1 = ROOT / "lib/domain-tier1.lisp"
BINARY = ROOT / "build/equivalence/dialect-v2-equivalence-check"
FORMAT = "lisp65-block-2.6-card4-compiler-prelude-v1"
LIST_OWNER_FUNCTIONS = (
    "%v2-reverse-into", "%v2-filter-into", "filter",
    "member", "assoc", "find",
)


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def load_git_json(revision: str, path: Path) -> dict[str, Any]:
    raw = subprocess.run(
        ["git", "show", f"{revision}:{path.relative_to(ROOT).as_posix()}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    value = json.loads(raw)
    require(isinstance(value, dict), f"JSON object required at {revision}:{path}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
            "sha256": sha(path)}


def run(command: list[str], label: str) -> str:
    result = subprocess.run(command, cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout


def authority() -> dict[str, Any]:
    raw = subprocess.run(
        ["git", "show", f"{AUTHORIZATION}:{PLAN.relative_to(ROOT).as_posix()}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout.decode()
    require(AUTH_HEADER in raw, "Card 4 review authority absent")
    tail = raw.split(AUTH_HEADER, 1)[1]
    for token in ("%lcc-tail-if", "cons-but-not-", "%case-key-test",
                  "domain contract table is re-measured"):
        require(token in tail, f"Card 4 authority token absent: {token}")
    section = tail.split("\n## ", 1)[0].encode()
    return {"commit": AUTHORIZATION,
            "plan": PLAN.relative_to(ROOT).as_posix(),
            "section_sha256": hashlib.sha256(section).hexdigest(),
            "right": "Bank-2 compiler/prelude Card 4; host-only qualification"}


def source_gate(texts: dict[str, str]) -> dict[str, Any]:
    lcc, prelude, macros, lists, tier1 = (
        texts[name] for name in ("lcc", "prelude", "macros", "lists", "tier1"))
    require("(rplaca hole1 (%lcc-rel8 (- (cdr (%lcc-st cs3)) len1)))" in lcc,
            "%lcc-tail-if does not use the shared rel8 oracle")
    require(lcc.count("(%lcc-error-invalid-parameter-list)))") >= 3,
            "cons operator paths do not fail through an LCC error")
    require("(if (consp key-spec)" in prelude
            and "(if (consp key)" in macros,
            "case key classification does not use consp")
    for name in ("find", "member", "assoc"):
        require(lists.count(f"(defun {name} ") == 1,
                f"lists-core must own exactly one {name}")
        require(tier1.count(f"(defun {name} ") == 0,
                f"domain-tier1 still shadows {name}")
    return {"status": "PASS", "owners": {
        name: "lib/dialect-v2/lists-core.lisp"
        for name in ("find", "member", "assoc")}}


def mutation_gate(texts: dict[str, str]) -> list[str]:
    trials: list[tuple[str, dict[str, str]]] = []
    def add(name: str, key: str, old: str, new: str) -> None:
        trial = dict(texts)
        require(old in trial[key], f"mutation anchor absent: {name}")
        trial[key] = trial[key].replace(old, new, 1)
        trials.append((name, trial))

    add("tail-if-raw-offset", "lcc",
        "(rplaca hole1 (%lcc-rel8 (- (cdr (%lcc-st cs3)) len1)))",
        "(rplaca hole1 (- (cdr (%lcc-st cs3)) len1))")
    add("expression-cons-operator-silently-nil", "lcc",
        "(%lcc-error-invalid-parameter-list)))\n        ((eq op 'lambda)",
        "(%lcc-push-value cs nil)))\n        ((eq op 'lambda)")
    add("tail-cons-operator-reenters-expression", "lcc",
        "(%lcc-error-invalid-parameter-list)))\n               ((eq op 'if)",
        "(%lcc-emit-op (%lcc-expr cs lvls form) 'ret)))\n               ((eq op 'if)")
    add("prelude-case-uses-permissive-car", "prelude",
        "(if (consp key-spec)", "(if (car key-spec)")
    add("macro-prelude-case-uses-permissive-car", "macros",
        "(if (consp key)", "(if (car key)")
    for name in ("find", "member", "assoc"):
        trial = dict(texts)
        trial["tier1"] += f"\n(defun {name} (a b) nil)\n"
        trials.append((f"tier1-shadows-{name}", trial))
    rejected = []
    for name, trial in trials:
        try:
            source_gate(trial)
        except CardError:
            rejected.append(name)
    require(len(rejected) == len(trials), "a Card 4 source mutation survived")
    return rejected


def successor_suite() -> dict[str, Any]:
    suite = deepcopy(load(BASE_SUITE))
    replacements = {
        "prelude-m1.lisp": (CODEMOD / "sources/lib/prelude-m1.lisp")
            .relative_to(ROOT).as_posix(),
        "lists-core.lisp": (CODEMOD / "sources/lib/dialect-v2/lists-core.lisp")
            .relative_to(ROOT).as_posix(),
        "domain-tier1.lisp": TIER1.relative_to(ROOT).as_posix(),
    }
    seen = {key: 0 for key in replacements}
    sources = []
    for source in suite["sources"]:
        name = Path(source).name
        if name in replacements:
            source = replacements[name]
            seen[name] += 1
        sources.append(source)
    require(seen == {name: 1 for name in replacements},
            f"successor source population drift: {seen}")
    suite["name"] = "block-2.6-card4-compiler-prelude"
    suite["sources"] = sources
    omitted = list(suite.get("allow_omitted_defuns", []))
    if not any(row.get("name") == "%rl-wait" for row in omitted):
        omitted.append({"name": "%rl-wait", "reason":
            "owned by the delivered read-line successor, not this static-plane slice"})
    suite["allow_omitted_defuns"] = omitted
    return suite


def materialize_list_owner() -> dict[str, Any]:
    """Materialize exactly the six list objects owned by lists-core in Card 4."""
    text = LISTS.read_text(encoding="utf-8")
    selected: list[str] = []
    counts = {name: 0 for name in LIST_OWNER_FUNCTIONS}
    for start, end in CODEMOD_TOOL._top_level_forms(text):
        form = text[start:end]
        atoms = CODEMOD_TOOL._form_atoms(form)
        if len(atoms) >= 2 and atoms[0] == "defun" and atoms[1] in counts:
            counts[atoms[1]] += 1
            selected.append(form)
    require(all(count == 1 for count in counts.values()),
            f"Card 4 lists-core owner population drift: {counts}")
    target = CODEMOD / "sources/lib/dialect-v2/lists-core.lisp"
    target.write_text(
        "; Generated for Block 2.6 Card 4 from "
        "lib/dialect-v2/lists-core.lisp; do not edit.\n\n"
        + "\n\n".join(selected) + "\n",
        encoding="utf-8",
    )
    generated = target.read_text(encoding="utf-8")
    for name in LIST_OWNER_FUNCTIONS:
        require(generated.count(f"(defun {name} ") == 1,
                f"generated list owner missing or duplicates {name}")
    return bind(target)


def normalized_code_objects(
    manifest_path: Path, blob_path: Path,
) -> dict[str, dict[str, Any]]:
    """Remove only literal-object relocation from carrier CodeObjects."""
    manifest = load(manifest_path)
    blob = blob_path.read_bytes()
    result = {}
    for row in manifest["entries"]:
        start = int(row["blob_offset"])
        raw = blob[start:start + int(row["length"])]
        require(len(raw) >= 7 and raw[0] == 0xB5,
                f"carrier CodeObject envelope drift: {row['name']}")
        literal_count = raw[6]
        payload_at = 7 + 2 * literal_count
        require(literal_count == len(row["literals"])
                and payload_at <= len(raw),
                f"carrier literal table drift: {row['name']}")
        literals = [
            item.get("symbol", item) if isinstance(item, dict) else item
            for item in row["literals"]
        ]
        result[row["name"]] = {
            "header_hex": raw[:7].hex(),
            "literals": literals,
            "payload_sha256": hashlib.sha256(raw[payload_at:]).hexdigest(),
            "encoded_bytes": len(raw),
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
        }
    return result


def carrier_executions() -> dict[str, Any]:
    old_carrier, old_tier = CARRIER_HOST.CARRIER, CARRIER_HOST.TIER
    CARRIER_HOST.CARRIER, CARRIER_HOST.TIER = COMPILER_MANIFEST, COMPILER_TIER
    try:
        valid = CARRIER_HOST.BoundCarrierCompiler().compile(
            "(defun %card4-ok (x) (if x 1 2))")
        errors = {}
        cases = {
            "cons-operator": "(defun %card4-bad () ((foo) 1))",
            "tail-if-rel8": (
                "(defun %card4-wide (x) (if x (progn "
                + " ".join("1" for _ in range(48)) + ") nil))"
            ),
        }
        for name, source in cases.items():
            try:
                CARRIER_HOST.BoundCarrierCompiler().compile(source)
            except B.VMError as error:
                errors[name] = str(error)
            else:
                raise CardError(f"live compiler carrier accepted {name}")
    finally:
        CARRIER_HOST.CARRIER, CARRIER_HOST.TIER = old_carrier, old_tier
    require(errors == {
        "cons-operator": "%lcc-error-invalid-parameter-list",
        "tail-if-rel8": "%lcc-error-do-body-too-big",
    }, f"live compiler carrier error semantics drift: {errors}")
    return {
        "valid_form": {
            "encoded_bytes": valid["summary"]["encoded_bytes"],
            "compiler_steps": valid["steps"],
        },
        "errors": errors,
    }


def materialize_compiler_carrier() -> dict[str, Any]:
    run([
        sys.executable, "tools/host-lisp/c2_v112_product_compiler_tier.py",
        "--out", COMPILER_SUITE.relative_to(ROOT).as_posix(),
        "--receipt", COMPILER_TIER.relative_to(ROOT).as_posix(),
    ], "Card 4 live compiler-tier generation")
    run([
        sys.executable, "tools/host-lisp/bytecode_p0_stdlib.py", "--check",
        "--emit-artifacts", COMPILER_PREFIX.relative_to(ROOT).as_posix(),
        "--artifact-role", "disk-lib", "--base-addr", "0x000000",
        COMPILER_SUITE.relative_to(ROOT).as_posix(),
    ], "Card 4 live compiler-carrier emission")
    carrier, suite, source = BOUND.source_binding_gate(
        COMPILER_MANIFEST, COMPILER_TIER)
    bound = BOUND.execute_bound_cases(
        COMPILER_MANIFEST, carrier, suite, require_while=True)

    before = normalized_code_objects(
        PREDECESSOR_COMPILER_MANIFEST, PREDECESSOR_COMPILER_BLOB)
    after = normalized_code_objects(COMPILER_MANIFEST, COMPILER_BLOB)
    require(before.keys() == after.keys(), "compiler carrier object population drift")
    semantic_changed = sorted(name for name in before if {
        key: before[name][key]
        for key in ("header_hex", "literals", "payload_sha256", "encoded_bytes")
    } != {
        key: after[name][key]
        for key in ("header_hex", "literals", "payload_sha256", "encoded_bytes")
    })
    raw_changed = sorted(
        name for name in before
        if before[name]["raw_sha256"] != after[name]["raw_sha256"])
    require(semantic_changed == [
        "%lcc-expr-form", "%lcc-tail", "%lcc-tail-if"],
        f"unattributed compiler carrier objects: {semantic_changed}")
    predecessor = load(PREDECESSOR_COMPILER_MANIFEST)
    successor = load(COMPILER_MANIFEST)
    require(
        len(successor["entries"]) == len(predecessor["entries"]) == 102
        and int(successor["code_bytes"]) - int(predecessor["code_bytes"]) == -3
        and len(successor["literal_nodes"]) - len(predecessor["literal_nodes"]) == 1
        and len(successor["literal_patches"])
            - len(predecessor["literal_patches"]) == 1
        and int(successor["external_image"]["bytes"])
            - int(predecessor["external_image"]["bytes"]) == 13,
        "compiler carrier freight attribution drift",
    )
    return {
        "tier": bind(COMPILER_TIER),
        "suite": bind(COMPILER_SUITE),
        "manifest": bind(COMPILER_MANIFEST),
        "blob": bind(COMPILER_BLOB),
        "source_binding": source,
        "bound_execution": bound,
        "card4_execution": carrier_executions(),
        "attribution": {
            "predecessor_manifest": bind(PREDECESSOR_COMPILER_MANIFEST),
            "objects_before": len(before),
            "objects_after": len(after),
            "code_bytes_before": int(predecessor["code_bytes"]),
            "code_bytes_after": int(successor["code_bytes"]),
            "code_bytes_delta": -3,
            "literal_nodes_delta": 1,
            "literal_patches_delta": 1,
            "external_image_bytes_delta": 13,
            "semantic_changed_objects": semantic_changed,
            "literal_relocation_only_objects": sorted(
                set(raw_changed) - set(semantic_changed)),
            "raw_identical_objects": sorted(set(before) - set(raw_changed)),
            "unexplained_objects": [],
        },
    }


def materialize(*, comfort_source_ref: str | None = None) -> dict[str, Any]:
    """Replay Card 4's external Comfort input in its own evidence era.

    The five Card-4-owned sources remain live and are checked separately.
    A later Comfort feature repair must not overwrite the durable domain
    authority with an unreviewed, mixed-generation re-emission.
    """
    from evidence_era import era_blob
    read_source = STDLIB._read_source
    consumed = []

    def source(path):
        if Path(STDLIB._suite_path(path)).resolve() == ROOT / "lib/repl-comfort.lisp":
            consumed.append(str(path))
            return era_blob(comfort_source_ref, "lib/repl-comfort.lisp").decode("utf-8")
        return read_source(path)

    try:
        if comfort_source_ref is not None:
            STDLIB._read_source = source
        result = _materialize()
        require(comfort_source_ref is None or consumed,
                "Card 4 sealed Comfort source was bound but not consumed")
        return result
    finally:
        STDLIB._read_source = read_source


def _materialize() -> dict[str, Any]:
    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True)
    run([sys.executable, "tools/host-lisp/v2_workbench_codemod.py",
         "--out", CODEMOD.relative_to(ROOT).as_posix()],
        "Card 4 canonical source codemod")
    list_owner = materialize_list_owner()
    SUITE.write_bytes(canonical(successor_suite()))
    resolved = STDLIB._read_suite(SUITE)
    forms, _macros = STDLIB._collect_top_defs(resolved["sources"])
    require(forms["member"][2] == ["item", "xs", "&optional", "test"]
            and forms["assoc"][2] == ["key", "alist", "&optional", "test"]
            and forms["find"][2] == ["predicate", "xs"],
            "the emitted successor did not select the lists-core ABI")
    require(STDLIB.main(["--check", "--emit-artifacts",
                        PREFIX.relative_to(ROOT).as_posix(),
                        SUITE.relative_to(ROOT).as_posix()]) == 0,
            "Card 4 successor emission failed")
    manifest = load(MANIFEST)
    entries = {row["name"]: row for row in manifest["entries"]}
    for name in ("find", "member", "assoc", "%case-key-test"):
        require(name in entries and int(entries[name]["length"]) < 255,
                f"Card 4 object absent or over ceiling: {name}")
    compiler_carrier = materialize_compiler_carrier()
    return {"suite": bind(SUITE), "list_owner": list_owner,
            "manifest": bind(MANIFEST), "blob": bind(BLOB),
            "entries": len(manifest["entries"]),
            "code_bytes": int(manifest["code_bytes"]),
            "objects": {name: int(entries[name]["length"])
                        for name in ("find", "member", "assoc", "%case-key-test")},
            "compiler_carrier": compiler_carrier}


def derive_contract(write: bool = True) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    # Card 4's predecessor is sealed at the parent of the review promotion.
    # Once the measured successor becomes the durable contract, comparing to
    # the live file would erase the one-cell attribution on every replay.
    before = load_git_json(f"{PROMOTION_AUTHORIZATION}^", DURABLE_CONTRACT)
    old_manifest, old_blob = AUDIT.STDLIB_MANIFEST, AUDIT.STDLIB_BLOB
    try:
        AUDIT.STDLIB_MANIFEST, AUDIT.STDLIB_BLOB = MANIFEST, BLOB
        after = AUDIT.derive()
    finally:
        AUDIT.STDLIB_MANIFEST, AUDIT.STDLIB_BLOB = old_manifest, old_blob
    old_rows = {row["name"]: row for row in before["rows"]}
    new_rows = {row["name"]: row for row in after["rows"]}
    require(old_rows.keys() == new_rows.keys(), "domain population changed")
    changed = []
    for name in old_rows:
        for domain in AUDIT.DOMAINS:
            old = AUDIT.semantic_cell(old_rows[name]["cells"][domain])
            new = AUDIT.semantic_cell(new_rows[name]["cells"][domain])
            if old != new:
                changed.append({"name": name, "domain": domain,
                                "before": old, "after": new})
    require({row["name"] for row in changed} <= {"find", "member", "assoc"},
            "Card 4 changed an unrelated domain cell")
    if write:
        MEASURED.write_bytes(canonical(after))
    else:
        require(MEASURED.read_bytes() == canonical(after),
                "Card 4 domain measurement is not derived from the successor")
    return after, changed


def rel8_oracles() -> dict[str, Any]:
    body = " ".join("1" for _ in range(48))
    source = f"(lambda (x) (if x (progn {body}) nil))"
    try:
        C.compile_source(source, B.Heap(), strict_arity=True,
                         abi_profile="dialect-v2")
    except C.CompileError as error:
        python = str(error)
    else:
        raise CardError("Python rel8 oracle accepted a wide tail branch")
    require("branch offset out of rel8 range" in python,
            "Python rel8 oracle rejected for the wrong reason")
    cases = [
        {"id": "cons-operator-expression",
         "source": "(lcc-compile-obj '(lambda () (progn ((foo) 1) 0)))"},
        {"id": "cons-operator-tail",
         "source": "(lcc-compile-obj '(lambda () ((foo) 1)))"},
        {"id": "tail-if-rel8", "source": f"(lcc-compile-obj '{source})"},
    ]
    with tempfile.TemporaryDirectory(prefix="lisp65-card4-lcc-") as raw:
        observed = LCC_SURFACE._run_profile(
            "dialect-v2", BINARY, cases, Path(raw), ROOT)
    expected = [
        "!error:code=59:symbol=%lcc-error-invalid-parameter-list",
        "!error:code=59:symbol=%lcc-error-invalid-parameter-list",
        # The equivalence host deliberately lacks the product-only error
        # primitive.  Reaching it is observed as an undefined public name;
        # source closure above binds that edge to %lcc-error-do-body-too-big.
        "!error:undefined-public-name",
    ]
    require(observed == expected,
            f"executed LCC Card 4 cases red: {observed}")
    return {"python_reference": python,
            "lisp_lcc": [{"id": case["id"], "observed": result}
                         for case, result in zip(cases, observed)]}


def list_semantics() -> dict[str, Any]:
    cases = {
        "member-optional-predicate": ("member", [3, [1, 4], {"symbol": "<"}], "(4)"),
        "assoc-optional-predicate": ("assoc", [3, [[1, 11], [4, 22]],
                                                   {"symbol": "<"}], "(4 22)"),
        "find-predicate": ("find", [{"symbol": "numberp"},
                                     [{"symbol": "a"}, 2, 3]], "2"),
    }
    rows = {}
    for case, (name, args, expected) in cases.items():
        result = PRICE.execute(MANIFEST, BLOB, name, args)
        require(result["result"] == "value" and result["value"] == expected,
                f"Card 4 list semantics red: {case}: {result}")
        rows[case] = result
    return rows


def record() -> None:
    texts = {"lcc": LCC.read_text(), "prelude": PRELUDE.read_text(),
             "macros": PRELUDE_MACROS.read_text(), "lists": LISTS.read_text(),
             "tier1": TIER1.read_text()}
    source = source_gate(texts)
    mutations = mutation_gate(texts)
    artifacts = materialize()
    contract, delta = derive_contract()
    oracles = rel8_oracles()
    semantics = list_semantics()
    receipt = {
        "format": FORMAT, "recorded_on": "2026-09-04",
        "status": "PASS: BLOCK 2.6 CARD 4 COMPILER/PRELUDE GREEN",
        "authority": authority(),
        "sources": {name: bind(path) for name, path in {
            "lcc": LCC, "prelude": PRELUDE, "prelude_macros": PRELUDE_MACROS,
            "lists_core": LISTS, "domain_tier1": TIER1}.items()},
        "source_gate": source, "mutations_rejected": mutations,
        "oracles": oracles, "successor_artifacts": artifacts,
        "list_semantics": semantics,
        "domain_contract": {"measurement": bind(MEASURED),
                            "counts": contract["counts"],
                            "changed_cells": delta},
        "integration_closure": {
            "current_compiler_carrier":
                "source-to-generated-tier-to-emitted-carrier",
            "sealed_public_carrier":
                "derived-committed-source-era-not-live-worktree",
            "historical_lcc_checks":
                "sealed-era-replay-and-live-successor-kept-separate",
            "gates": {
                "source_parity": bind(SOURCE_PARITY),
                "source_parity_contract": bind(SOURCE_PARITY_CONTRACT),
                "locality_replay": bind(LOCALITY_REPLAY),
                "option_a": bind(OPTION_A),
                "top_level_redispatch": bind(TOP_LEVEL_REDISPATCH),
                "direct_expression": bind(DIRECT_EXPRESSION),
            },
            "anti_mixing_mutations": [
                "sealed-source-era-live-mixing",
                "sealed-v111-source-content-drift",
                "live-option-A-content-in-sealed-receipt",
                "sealed-Link95-compiler-live-mixing",
            ],
        },
        "full_check_closure": {
            "historical_follow_on_checks": {
                "tier1_price": bind(TIER1_PRICE),
                "v201_bundled_docs": bind(V201_DOCS),
            },
            "derived_successor_indexes": {
                "prelude_inventory": bind(PRELUDE_INVENTORY),
                "dialect_migration_contract": bind(MIGRATION_CONTRACT),
                "dialect_budget_comparison": bind(BUDGET_COMPARISON),
                "function_metadata_index": bind(METADATA_INDEX),
                "function_metadata_receipt": bind(METADATA_RECEIPT),
            },
            "rule": (
                "sealed evidence is replayed in its source era; living indexes "
                "are regenerated from the executed Card-4 successor"
            ),
        },
        "budget": {"WPLTO_runs": 0, "product_links": 0,
                   "media_builds": 0, "device_contacts": 0},
    }
    RECEIPT.write_bytes(canonical(receipt))
    REPORT.write_text(
        "# Block 2.6 Card 4 — compiler and prelude\n\n"
        f"Status: **{receipt['status']}**\n\n"
        "`%lcc-tail-if` now shares `%lcc-rel8` with ordinary `if`; both "
        "non-lambda cons-operator paths stop through the existing LCC compile "
        "error. Both `case` implementations classify compound keys with "
        "`consp`. `find`, `member`, and `assoc` have one v2 owner, "
        "`lib/dialect-v2/lists-core.lisp`; Tier 1 no longer shadows their "
        "predicate/optional-argument semantics.\n\n"
        f"The successor Bank-2 artifact contains **{artifacts['code_bytes']} "
        f"code bytes / {artifacts['entries']} entries**. Executed list cases "
        "return `(4)`, `(4 22)`, and `2`. The Python compiler and executed "
        "Lisp LCC both reject the over-wide tail branch; expression and tail "
        "cons-operators both raise the named LCC error.\n\n"
        f"The public domain matrix was freshly re-executed: **"
        f"{contract['counts']['error-raised']} error-raised / "
        f"{contract['counts']['documented-permissive']} documented-permissive / "
        f"{contract['counts']['silently-wrong']} silently-wrong**; "
        f"{len(delta)} semantic cell changed (the `find` list-domain cell). "
        "The durable table is not hand-edited; the "
        "measurement remains a review input until promotion.\n\n"
        "The live compiler edge is closed separately: current source → "
        "generated v1.12 tier → emitted carrier. The carrier contains **8131 "
        "code bytes / 102 objects** (−3 bytes); exactly `%lcc-expr-form`, "
        "`%lcc-tail`, and `%lcc-tail-if` change semantically. Of the other "
        "objects, 89 differ only by relocated literal-object addresses and "
        "10 are raw-byte identical; the unexplained set is empty. One new "
        "literal node/patch adds 16 metadata bytes, hence the external image "
        "moves by +13 bytes net. Executing that carrier raises the named "
        "invalid-parameter and rel8 errors.\n\n"
        "The five compiler-carrier integration reds were checker-world "
        "crossings. The public "
        "sealed carrier now resolves its matching committed source era while "
        "explicit candidate carriers remain live-source strict; the v1.11 "
        "locality replay rebuilds solely from its sealed closure; the Option-A "
        "gate executes today's carrier but never rewrites or semantically "
        "compares it with the historical receipt; the Link-95 redispatch and "
        "direct-expression gates likewise consume their own source-era shape. "
        "The old Tier-1 price and v2.0.1 docs gates remain sealed while the "
        "Prelude, migration-budget, and function-metadata indexes are "
        "regenerated from the living successor. Anti-mixing mutations cover "
        "the historical boundaries.\n\n"
        f"Eight sharp mutations are rejected. Budget: **0 WPLTO / 0 product "
        "links / 0 media / 0 device contacts**.\n",
        encoding="utf-8")
    print("block-2.6-card4: RECORD PASS "
          f"code={artifacts['code_bytes']} domain={contract['counts']} "
          f"changed={len(delta)} mutations={len(mutations)}")


def validate(value: dict[str, Any]) -> None:
    require(value.get("format") == FORMAT
            and value.get("status") ==
            "PASS: BLOCK 2.6 CARD 4 COMPILER/PRELUDE GREEN",
            "Card 4 receipt identity drift")
    require(value.get("authority") == authority(),
            "Card 4 review authority drift")
    for name, path in {"lcc": LCC, "prelude": PRELUDE,
                       "prelude_macros": PRELUDE_MACROS,
                       "lists_core": LISTS, "domain_tier1": TIER1}.items():
        require(value["sources"][name] == bind(path),
                f"Card 4 source binding drift: {name}")
    artifacts = materialize(comfort_source_ref=PROMOTION_AUTHORIZATION)
    require(value["successor_artifacts"] == artifacts,
            "Card 4 successor artifact derivation drift")
    require(value["successor_artifacts"]["manifest"] == bind(MANIFEST)
            and value["successor_artifacts"]["blob"] == bind(BLOB)
            and value["domain_contract"]["measurement"] == bind(MEASURED),
            "Card 4 successor artifact binding drift")
    require(len(value["mutations_rejected"]) == 8
            and value["budget"] == {"WPLTO_runs": 0, "product_links": 0,
                                    "media_builds": 0, "device_contacts": 0},
            "Card 4 mutation or budget drift")
    require(value.get("integration_closure", {}).get("gates") == {
        "source_parity": bind(SOURCE_PARITY),
        "source_parity_contract": bind(SOURCE_PARITY_CONTRACT),
        "locality_replay": bind(LOCALITY_REPLAY),
        "option_a": bind(OPTION_A),
        "top_level_redispatch": bind(TOP_LEVEL_REDISPATCH),
        "direct_expression": bind(DIRECT_EXPRESSION),
    } and len(value["integration_closure"]["anti_mixing_mutations"]) == 4,
            "Card 4 integration closure drift")
    require(value.get("full_check_closure") == {
        "historical_follow_on_checks": {
            "tier1_price": bind(TIER1_PRICE),
            "v201_bundled_docs": bind(V201_DOCS),
        },
        "derived_successor_indexes": {
            "prelude_inventory": bind(PRELUDE_INVENTORY),
            "dialect_migration_contract": bind(MIGRATION_CONTRACT),
            "dialect_budget_comparison": bind(BUDGET_COMPARISON),
            "function_metadata_index": bind(METADATA_INDEX),
            "function_metadata_receipt": bind(METADATA_RECEIPT),
        },
        "rule": (
            "sealed evidence is replayed in its source era; living indexes "
            "are regenerated from the executed Card-4 successor"
        ),
    }, "Card 4 full-check closure drift")
    texts = {"lcc": LCC.read_text(), "prelude": PRELUDE.read_text(),
             "macros": PRELUDE_MACROS.read_text(), "lists": LISTS.read_text(),
             "tier1": TIER1.read_text()}
    source_gate(texts)
    require(mutation_gate(texts) == value["mutations_rejected"],
            "Card 4 mutation population drift")
    contract, delta = derive_contract(write=False)
    require(value["domain_contract"]["counts"] == contract["counts"]
            and value["domain_contract"]["changed_cells"] == delta,
            "Card 4 executed domain measurement drift")
    require(value["oracles"] == rel8_oracles(),
            "Card 4 compiler oracle drift")
    require(value["list_semantics"] == list_semantics(),
            "Card 4 list semantics drift")


def check() -> None:
    validate(load(RECEIPT))
    require(REPORT.is_file(), "Card 4 report absent")
    print("block-2.6-card4: CHECK PASS mutations=8 WPLTO=0 links=0 contacts=0")


def promote() -> None:
    review = subprocess.run(
        ["git", "show", f"{PROMOTION_AUTHORIZATION}:{PLAN.relative_to(ROOT).as_posix()}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout.decode()
    require("The re-measured domain matrix is promoted to the durable contract" in review,
            "Card 4 promotion authority absent")
    measured, changed = derive_contract(write=False)
    require(measured["counts"] == {
        "documented-permissive": 178,
        "error-raised": 546,
        "silently-wrong": 110,
    }, "reviewed Card 4 count tuple drift")
    require(len(changed) == 1 and changed[0]["name"] == "find"
            and changed[0]["domain"] == "list",
            "reviewed Card 4 attribution drift")
    DURABLE_CONTRACT.write_bytes(canonical(measured))
    receipt = {
        "format": "lisp65-block-2.6-card4-domain-promotion-v1",
        "status": "PASS: REVIEWED MEASUREMENT PROMOTED",
        "authority": {"commit": PROMOTION_AUTHORIZATION,
                      "plan": PLAN.relative_to(ROOT).as_posix()},
        "predecessor": bind_git_contract(f"{PROMOTION_AUTHORIZATION}^"),
        "measurement": bind(MEASURED),
        "durable_contract": bind(DURABLE_CONTRACT),
        "counts": measured["counts"],
        "changed_cells": changed,
    }
    PROMOTION_RECEIPT.write_bytes(canonical(receipt))
    print("block-2.6-card4: PROMOTE PASS domain=546/178/110 changed=find:list")


def bind_git_contract(revision: str) -> dict[str, Any]:
    raw = subprocess.run(
        ["git", "show", f"{revision}:{DURABLE_CONTRACT.relative_to(ROOT).as_posix()}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    return {"revision": revision,
            "path": DURABLE_CONTRACT.relative_to(ROOT).as_posix(),
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def selftest() -> None:
    texts = {"lcc": LCC.read_text(), "prelude": PRELUDE.read_text(),
             "macros": PRELUDE_MACROS.read_text(), "lists": LISTS.read_text(),
             "tier1": TIER1.read_text()}
    source_gate(texts)
    rejected = mutation_gate(texts)
    require(len(rejected) == 8, "Card 4 selftest mutation count drift")
    print("block-2.6-card4: SELFTEST PASS mutations=8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("record", "check", "selftest", "promote"))
    args = parser.parse_args()
    try:
        {"record": record, "check": check, "selftest": selftest,
         "promote": promote}[args.mode]()
        return 0
    except (CardError, OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"block-2.6-card4: FAIL {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
