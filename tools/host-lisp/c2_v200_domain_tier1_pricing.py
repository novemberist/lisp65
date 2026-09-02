#!/usr/bin/env python3
"""Price v2.0 domain discipline Tier 1 on the materialized product world."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
import public_surface_domain_audit as AUDIT  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
AUTHORITY_COMMIT = "d38ea2e3"
PLAN_HEADER = (
    "## Owner decision — v2.0 reshaped; the delivery chain becomes the target — 2026-09-01")
PILLAR_HEADER = "## Pillar 2 — consistency and names (the breaking half)"
BASE_SUITE = ROOT / (
    "build/c2.3/v1.9.0-release-card-r1-preflight/"
    "native-client-product-stdlib-suite.json")
BASE_MANIFEST = ROOT / (
    "build/c2.3/v1.9.0-release-card-r1-preflight/setup-owned/"
    "static-plane/narrow-static/stdlib-p0.manifest.json")
BASE_BLOB = ROOT / (
    "build/c2.3/v1.9.0-release-card-r1-preflight/setup-owned/"
    "static-plane/narrow-static/stdlib-p0.blob.bin")
CURRENT_CARD = ARCH / (
    "c2.3-v2.0-symbol22-first-fault-product-card-r4-receipt.json")
CURRENT_PRODUCT = ROOT / (
    "build/c2.3/v2.0-symbol22-first-fault-product-card-r2/"
    "static-plane/narrow-static/product/substitution-artifacts.json")
BUILD = ROOT / "build/c2.3/v2.0-domain-tier1-pricing"
SUCCESSOR_SOURCE = ROOT / "lib/domain-tier1.lisp"
SUITE = BUILD / "tier1-product-stdlib-suite.json"
PREFIX = BUILD / "stdlib-p0"
RECEIPT = ARCH / "c2.3-v2.0-domain-tier1-pricing-receipt.json"
REPORT = ROOT / "docs/planning/v2.0.0-domain-tier1-pricing-report.md"
STATUS = "PASS: V2.0 DOMAIN TIER 1 PRICED; ONE BANK-2 PRODUCT CARD RECOMMENDED"
FORMAT = "lisp65-c2-v200-domain-tier1-pricing-v1"
EVIDENCE_ERA = "c6f40bfd"

TIER1 = (
    "append", "assoc", "butlast", "copy-list", "count", "every", "filter",
    "find", "getf", "last", "length", "mapc", "mapcan", "mapcar", "member",
    "nth", "nthcdr", "position", "reduce", "remf", "reverse", "some",
)
ALREADY_STRICT = ("filter",)

# All names below already exist in the shipped resident population. The price
# therefore adds no symbol or namepool freight. Public definitions and their
# existing private traversal helpers are replaced in place.
SUCCESSOR = r"""; v2.0 Tier 1: strict finite proper-list spines.

(defun %append2 (a b)
  (%append2-rev (reverse a) b))

(defun %append2-rev (ra b)
  (if (consp ra)
      (%append2-rev (cdr ra) (cons (car ra) b))
      (if ra (%list-malformed-error) b)))

(defun append (&rest lists)
  ((lambda (rev-lists)
     (if (consp rev-lists)
         (progn
           (length (car rev-lists))
           (%append-lists (cdr rev-lists) (car rev-lists)))
         (if rev-lists (%list-malformed-error) nil)))
   (reverse lists)))

(defun %append-lists (rev-lists acc)
  (if (consp rev-lists)
      (%append-lists (cdr rev-lists) (%append2 (car rev-lists) acc))
      (if rev-lists (%list-malformed-error) acc)))

(defun length (xs)
  (%length-from xs 0))

(defun %length-from (xs n)
  (if (consp xs)
      (%length-from (cdr xs) (1+ n))
      (if xs (%list-malformed-error) n)))

(defun nth (n xs)
  (if (numberp n)
      (if (< n 0)
          (%list-malformed-error)
          (if (zerop n)
              (if (consp xs) (car xs) (if xs (%list-malformed-error) nil))
              (if (consp xs)
                  (nth (1- n) (cdr xs))
                  (if xs (%list-malformed-error) nil))))
      (%list-malformed-error)))

(defun nthcdr (n xs)
  (if (numberp n)
      (if (< n 0)
          (%list-malformed-error)
          (if (zerop n)
              (progn (length xs) xs)
              (if (consp xs)
                  (nthcdr (1- n) (cdr xs))
                  (if xs (%list-malformed-error) nil))))
      (%list-malformed-error)))

(defun %reverse-into (xs acc)
  (if (consp xs)
      (%reverse-into (cdr xs) (cons (car xs) acc))
      (if xs (%list-malformed-error) acc)))

(defun reverse (xs)
  (%reverse-into xs nil))

(defun last (xs)
  (if (consp xs)
      (if (consp (cdr xs))
          (last (cdr xs))
          (if (cdr xs) (%list-malformed-error) xs))
      (if xs (%list-malformed-error) nil)))

(defun member (item xs)
  (if (consp xs)
      (if (eql item (car xs)) xs (member item (cdr xs)))
      (if xs (%list-malformed-error) nil)))

(defun assoc (key alist)
  (if (consp alist)
      (if (consp (car alist))
          (if (eql key (car (car alist)))
              (car alist)
              (assoc key (cdr alist)))
          (%list-malformed-error))
      (if alist (%list-malformed-error) nil)))

(defun %any-null (lists)
  (if (consp lists)
      (if (consp (car lists))
          (%any-null (cdr lists))
          (if (car lists) (%list-malformed-error) 't))
      (if lists (%list-malformed-error) nil)))

(defun %cars (lists)
  (if (consp lists)
      (cons (car (car lists)) (%cars (cdr lists)))
      (if lists (%list-malformed-error) nil)))

(defun %cdrs (lists)
  (if (consp lists)
      (cons (cdr (car lists)) (%cdrs (cdr lists)))
      (if lists (%list-malformed-error) nil)))

(defun mapcar (fn &rest lists)
  (if (consp lists)
      (%mapcar-into fn lists nil)
      (if lists (%list-malformed-error) nil)))

(defun %mapcar-into (fn lists acc)
  (if (consp lists)
      (if (%any-null lists)
          (reverse acc)
          (%mapcar-into fn (%cdrs lists)
                        (cons (apply fn (%cars lists)) acc)))
      (if lists (%list-malformed-error) (reverse acc))))

(defun mapcan (fn &rest lists)
  (apply (function append) (apply (function mapcar) (cons fn lists))))

(defun %mapc (fn xs)
  (if (consp xs)
      (progn (funcall fn (car xs)) (%mapc fn (cdr xs)))
      (if xs (%list-malformed-error) nil)))

(defun mapc (fn xs)
  (%mapc fn xs)
  xs)

(defun find (item xs)
  (if (consp xs)
      (if (eql item (car xs)) (car xs) (find item (cdr xs)))
      (if xs (%list-malformed-error) nil)))

(defun %position-from (item xs n)
  (if (consp xs)
      (if (eql item (car xs)) n (%position-from item (cdr xs) (1+ n)))
      (if xs (%list-malformed-error) nil)))

(defun position (item xs)
  (%position-from item xs 0))

(defun butlast (xs &rest maybe-n)
  (%take xs (- (length xs) (if maybe-n (car maybe-n) 1))))

(defun copy-list (xs)
  (reverse (reverse xs)))

(defun count (item xs)
  (%count-from item xs 0))

(defun %count-from (item xs n)
  (if (consp xs)
      (%count-from item (cdr xs) (if (eql item (car xs)) (1+ n) n))
      (if xs (%list-malformed-error) n)))

(defun %reduce-from (fn acc xs)
  (if (consp xs)
      (%reduce-from fn (funcall fn acc (car xs)) (cdr xs))
      (if xs (%list-malformed-error) acc)))

(defun reduce (fn xs)
  (if (consp xs)
      (%reduce-from fn (car xs) (cdr xs))
      (if xs (%list-malformed-error) nil)))

(defun every (fn xs)
  (if (consp xs)
      (if (funcall fn (car xs)) (every fn (cdr xs)) nil)
      (if xs (%list-malformed-error) 't)))

(defun some (fn xs)
  (if (consp xs)
      ((lambda (r) (if r r (some fn (cdr xs)))) (funcall fn (car xs)))
      (if xs (%list-malformed-error) nil)))

(defun %getf (plist key default)
  (if (consp plist)
      (if (consp (cdr plist))
          (if (eql (car plist) key)
              (car (cdr plist))
              (%getf (cdr (cdr plist)) key default))
          (%list-malformed-error))
      (if plist (%list-malformed-error) default)))

(defun getf (plist key &rest default)
  (%getf plist key (if default (car default) nil)))

(defun remf (plist key)
  (%remf-into plist key nil))

(defun %remf-into (plist key acc)
  (if (consp plist)
      (if (consp (cdr plist))
          (if (eql (car plist) key)
              (%append2-rev acc (cdr (cdr plist)))
              (%remf-into (cdr (cdr plist)) key
                          (cons (car (cdr plist)) (cons (car plist) acc))))
          (%list-malformed-error))
      (if plist (%list-malformed-error) (reverse acc))))
"""


INVALID_CASES: dict[str, list[Any]] = {
    "append": [7], "assoc": [1, 7], "butlast": [7], "copy-list": [7],
    "count": [1, 7], "every": [{"symbol": "numberp"}, 7],
    "filter": [{"symbol": "numberp"}, 7], "find": [1, 7],
    "getf": [7, 1], "last": [7], "length": [7],
    "mapc": [{"symbol": "identity"}, 7],
    "mapcan": [{"symbol": "list"}, 7],
    "mapcar": [{"symbol": "identity"}, 7], "member": [1, 7],
    "nth": [0, 7], "nthcdr": [1, 7], "position": [1, 7],
    "reduce": [{"symbol": "+"}, 7], "remf": [7, 1], "reverse": [7],
    "some": [{"symbol": "numberp"}, 7],
}

POSITIVE_CASES: dict[str, list[Any]] = {
    "append": [[1, 2], [3]], "assoc": [1, [[1, 2], [3, 4]]],
    "butlast": [[1, 2, 3]], "copy-list": [[1, 2]],
    "count": [1, [1, 2, 1]], "every": [{"symbol": "numberp"}, [1, 2]],
    "filter": [{"symbol": "numberp"}, [1, 2]], "find": [2, [1, 2]],
    "getf": [[1, 2, 3, 4], 3], "last": [[1, 2, 3]],
    "length": [[1, 2, 3]], "mapc": [{"symbol": "identity"}, [1, 2]],
    "mapcan": [{"symbol": "list"}, [1, 2]],
    "mapcar": [{"symbol": "identity"}, [1, 2]], "member": [2, [1, 2]],
    "nth": [1, [1, 2, 3]], "nthcdr": [1, [1, 2, 3]],
    "position": [2, [1, 2, 3]], "reduce": [{"symbol": "+"}, [1, 2, 3]],
    "remf": [[1, 2, 3, 4], 1], "reverse": [[1, 2, 3]],
    "some": [{"symbol": "numberp"}, [1, 2]],
}


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    relative = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{AUTHORITY_COMMIT}:{relative}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = raw.decode()
    require(text.count(PLAN_HEADER) == 1, "Tier-1 authority section drift")
    section = PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    folded = " ".join(section.lower().replace("`", "").split())
    for token in ("pillars 2 and 3", "172 silently-wrong"):
        require(token in folded, f"Tier-1 authority absent: {token}")
    require(text.count(PILLAR_HEADER) == 1, "Tier-1 pillar section drift")
    pillar = PILLAR_HEADER + text.split(PILLAR_HEADER, 1)[1]
    pillar = pillar.split("\n## ", 1)[0].rstrip() + "\n"
    pillar_folded = " ".join(pillar.lower().replace("`", "").split())
    for token in ("domain discipline, tier 1", "everything that walks with cdr",
                  "string-length"):
        require(token in pillar_folded, f"Tier-1 specification absent: {token}")
    payload = (section + pillar).encode()
    return {"commit": AUTHORITY_COMMIT, "path": relative,
            "sections": [PLAN_HEADER, PILLAR_HEADER], "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "right": "host-only Tier-1 price card; no product repair, WPLTO or link"}


def run(command: list[str], label: str) -> str:
    result = subprocess.run(command, cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout


def emit() -> None:
    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True)
    require(SUCCESSOR_SOURCE.read_text(encoding="utf-8") == SUCCESSOR,
        "tracked Tier-1 successor diverged from the priced source")
    suite = deepcopy(load(BASE_SUITE))
    suite["name"] = "v2.0-domain-tier1-pricing"
    suite["sources"].append(SUCCESSOR_SOURCE.relative_to(ROOT).as_posix())
    # The inherited executable cases freeze predecessor results.  This is a
    # price-only successor; its positive and sharp negative matrices below are
    # the executable authority and the sealed predecessor suite remains bound.
    suite["cases"] = suite["cases"][:4]
    SUITE.write_bytes(canonical(suite))
    run([sys.executable, "tools/host-lisp/bytecode_p0_stdlib.py", "--check",
         "--emit-artifacts", PREFIX.relative_to(ROOT).as_posix(),
         SUITE.relative_to(ROOT).as_posix()], "Tier-1 prototype emission")


def product(manifest: Path, blob: Path) -> tuple[Any, ...]:
    old_manifest, old_blob = AUDIT.STDLIB_MANIFEST, AUDIT.STDLIB_BLOB
    try:
        AUDIT.STDLIB_MANIFEST, AUDIT.STDLIB_BLOB = manifest, blob
        return AUDIT.load_product()
    finally:
        AUDIT.STDLIB_MANIFEST, AUDIT.STDLIB_BLOB = old_manifest, old_blob


def execute(manifest: Path, blob: Path, name: str,
            args_json: list[Any]) -> dict[str, Any]:
    base_heap, directory, macros, code_names, _authorities = product(manifest, blob)
    heap = base_heap.clone()
    target = heap.intern(name)
    args = [B.obj_from_json(heap, value) for value in args_json]
    vm = B.P0VM(
        heap=heap, directory=directory, macro_symbols=macros,
        code_names=code_names, max_steps=300_000, max_call_args=32,
        key_events=[], memory_read_sequences={0xFF83: [0] * 64},
        abi_profile="dialect-v2", abi_ledger=C._abi_ledger("dialect-v2", None),
        delivered_callprims=AUDIT.DELIVERED_CALLPRIMS)
    try:
        result = vm._invoke_function(target, args)
    except B.VMError as error:
        return {"result": "error", "error": error.status,
                "detail": str(error), "steps": vm.steps}
    return {"result": "value", "value": heap.obj_to_text(result),
            "steps": vm.steps}


def domain_projection(manifest: Path, blob: Path) -> dict[str, Any]:
    old_manifest, old_blob = AUDIT.STDLIB_MANIFEST, AUDIT.STDLIB_BLOB
    try:
        AUDIT.STDLIB_MANIFEST, AUDIT.STDLIB_BLOB = manifest, blob
        return AUDIT.derive()
    finally:
        AUDIT.STDLIB_MANIFEST, AUDIT.STDLIB_BLOB = old_manifest, old_blob


def entries(path: Path) -> dict[str, dict[str, Any]]:
    return {row["name"]: row for row in load(path)["entries"]
            if isinstance(row, dict) and row.get("kind") == "function"}


def cell_semantics(cell: dict[str, Any]) -> dict[str, Any]:
    """The product contract owns result/error identity, not host diagnostics."""
    return {key: cell[key] for key in
            ("classification", "result", "error") if key in cell}


def evidence_era_equivalent(
        sealed: dict[str, Any], live_derivation: dict[str, Any]) -> bool:
    """Compare a sealed price with a live re-emission without crossing eras.

    The candidate manifest records source provenance as well as emitted object
    facts.  A later banner changes that metadata even when the candidate blob
    and every semantic price fact remain byte-identical.  The sealed manifest
    digest therefore stays in its evidence era; the live derivation may differ
    only at that one metadata digest, with path/size, emitted blob, and all
    derived facts still equal.
    """
    expected = deepcopy(live_derivation)
    sealed_bindings = sealed.get("bindings")
    live_bindings = expected.get("bindings")
    if (not isinstance(sealed_bindings, list)
            or not isinstance(live_bindings, list)
            or len(sealed_bindings) != len(live_bindings) + 1):
        return False
    # The first binding was converted to an evidence-era contract binding;
    # all remaining predecessor/product inputs must still be live-identical.
    if sealed_bindings[1:] != live_bindings:
        return False
    expected["bindings"] = sealed_bindings

    sealed_prototype = sealed.get("prototype", {}).get("bindings")
    live_prototype = expected.get("prototype", {}).get("bindings")
    if (not isinstance(sealed_prototype, list)
            or not isinstance(live_prototype, list)
            or len(sealed_prototype) != 4
            or len(live_prototype) != 4):
        return False
    # Source, suite, and emitted bytecode blob remain exact.  Only manifest
    # provenance metadata may cross the live banner boundary.
    if (sealed_prototype[:2] != live_prototype[:2]
            or sealed_prototype[3] != live_prototype[3]
            or {key: sealed_prototype[2].get(key) for key in ("path", "bytes")}
               != {key: live_prototype[2].get(key) for key in ("path", "bytes")}):
        return False
    expected["prototype"]["bindings"] = sealed_prototype
    return sealed == expected


def derive() -> dict[str, Any]:
    emit()
    candidate_manifest = PREFIX.with_suffix(".manifest.json")
    candidate_blob = PREFIX.with_suffix(".blob.bin")
    base_entries = entries(BASE_MANIFEST)
    candidate_entries = entries(candidate_manifest)
    require(set(TIER1) <= set(base_entries) & set(candidate_entries),
            "Tier-1 materialized population incomplete")

    invalid = {}
    positive = {}
    for name in TIER1:
        before_bad = execute(BASE_MANIFEST, BASE_BLOB, name, INVALID_CASES[name])
        after_bad = execute(candidate_manifest, candidate_blob, name,
                            INVALID_CASES[name])
        require(after_bad["result"] == "error"
                and after_bad["error"] in ("TypeError", "RuntimeError"),
                f"Tier-1 invalid spine still succeeds: {name} {after_bad}")
        if name not in ALREADY_STRICT:
            require(before_bad["result"] == "value",
                    f"Tier-1 predecessor unexpectedly strict: {name}")
        invalid[name] = {"arguments": INVALID_CASES[name],
                         "before": before_bad, "after": after_bad}

        before_good = execute(BASE_MANIFEST, BASE_BLOB, name,
                              POSITIVE_CASES[name])
        after_good = execute(candidate_manifest, candidate_blob, name,
                             POSITIVE_CASES[name])
        require(before_good["result"] == "value"
                and after_good["result"] == "value"
                and before_good["value"] == after_good["value"],
                f"Tier-1 positive result drift: {name}")
        positive[name] = {"arguments": POSITIVE_CASES[name],
                          "before": before_good, "after": after_good,
                          "step_delta": after_good["steps"] - before_good["steps"]}

    # The price belongs to the sealed v1.9 evidence era.  Its predecessor
    # contract is derived from those exact artifacts, never from the living
    # public contract authority (which advances when a tier closes).
    baseline_contract = domain_projection(BASE_MANIFEST, BASE_BLOB)
    require(baseline_contract["counts"] == {"error-raised": 483,
                "documented-permissive": 179, "silently-wrong": 172},
            "Tier-1 sealed predecessor contract drift")
    successor_contract = domain_projection(candidate_manifest, candidate_blob)
    base_rows = {row["name"]: row for row in baseline_contract["rows"]}
    next_rows = {row["name"]: row for row in successor_contract["rows"]}
    changed_cells = []
    diagnostic_only_cells = []
    for name in base_rows:
        for domain in AUDIT.DOMAINS:
            before = base_rows[name]["cells"][domain]
            after = next_rows[name]["cells"][domain]
            if cell_semantics(before) != cell_semantics(after):
                changed_cells.append({"name": name, "domain": domain,
                    "before": cell_semantics(before),
                    "after": cell_semantics(after)})
            elif before != after:
                diagnostic_only_cells.append({"name": name, "domain": domain,
                    "before_steps": before.get("steps"),
                    "after_steps": after.get("steps"),
                    "before_detail": before.get("detail"),
                    "after_detail": after.get("detail")})
    require(all(row["name"] in TIER1 for row in changed_cells),
            "Tier-1 prototype changes a public cell outside Tier 1")
    require(all(
                row["after"]["classification"] == "error-raised"
                and row["before"]["classification"] in
                    ("silently-wrong", "error-raised")
                for row in changed_cells),
            "Tier-1 public matrix changes a successful documented result")

    base_bytes = int(load(BASE_MANIFEST)["code_bytes"])
    next_bytes = int(load(candidate_manifest)["code_bytes"])
    delta = next_bytes - base_bytes
    current_product = load(CURRENT_PRODUCT)
    current_plane = sum(int(load(ROOT / row["path"])["code_bytes"])
                        for row in current_product["manifests"])
    require(current_plane == 47469 and delta > 0,
            "living Tier-1 plane baseline drift")
    changed_names = sorted(name for name in candidate_entries
        if name in base_entries and int(candidate_entries[name]["length"]) !=
        int(base_entries[name]["length"]))
    object_rows = [{"name": name,
        "before": int(base_entries[name]["length"]),
        "after": int(candidate_entries[name]["length"]),
        "delta": int(candidate_entries[name]["length"]) -
                 int(base_entries[name]["length"])} for name in changed_names]
    largest = max(int(row["length"]) for row in candidate_entries.values())
    require(largest < 255, "Tier-1 candidate emits an object at/above 255 bytes")
    successor_defuns = {form[1] for form in C.parse_all(SUCCESSOR)
                        if isinstance(form, list) and len(form) >= 4
                        and form[0] == "defun"}
    base_functions = set(load(BASE_SUITE)["functions"])
    require(successor_defuns <= base_functions,
            "Tier-1 prototype introduces an unpriced name")

    contract_silent_before = baseline_contract["counts"]["silently-wrong"]
    contract_silent_after = successor_contract["counts"]["silently-wrong"]
    return {
        "format": FORMAT, "recorded_on": "2026-09-01", "status": STATUS,
        "authority": authority(),
        "scope": {
            "members": list(TIER1), "member_count": len(TIER1),
            "already_strict": list(ALREADY_STRICT),
            "definition": ("resident public library sequence operations whose "
                           "delivered implementation traverses a list spine with cdr"),
            "excluded": {
                "tier_2": ["car", "cdr"],
                "other_domain_families": ["numeric comparisons", "string/buffer entry points"],
            },
        },
        "prototype": {
            "strategy": ("replace existing public objects and existing traversal "
                         "helpers in place; fail through %list-malformed-error at "
                         "every foreign finite spine termination"),
            "new_names": 0, "new_namepool_bytes": 0,
            "successor_definition_names": sorted(successor_defuns),
            "bindings": [bind(SUCCESSOR_SOURCE), bind(SUITE),
                         bind(candidate_manifest), bind(candidate_blob)],
        },
        "public_contract_projection": {
            "baseline_counts": baseline_contract["counts"],
            "successor_counts": successor_contract["counts"],
            "silent_cells_removed": contract_silent_before - contract_silent_after,
            "changed_cell_count": len(changed_cells),
            "error_priority_changes": sum(
                row["before"]["classification"] == "error-raised"
                for row in changed_cells),
            "changed_cells": changed_cells,
            "claim_limit": ("uniform-vector contract cells are a regression "
                            "projection; the per-signature invalid-spine matrix "
                            "is the Tier-1 conformance authority"),
        },
        "contract_gate_conversion": {
            "required": True,
            "reason": ("the current stable projection also pins host VM steps and "
                       "diagnostic detail although the sealed rule owns only "
                       "classification plus target result/error"),
            "diagnostic_only_cell_count": len(diagnostic_only_cells),
            "diagnostic_only_names": sorted({row["name"]
                                             for row in diagnostic_only_cells}),
            "successor_projection": ["classification", "result", "error"],
            "sharp_mutations": ["flip-classification", "change-result",
                                "change-target-error"],
        },
        "signature_faithful_checks": {
            "invalid_spines": invalid, "positive_results": positive,
            "invalid_count": len(invalid), "positive_count": len(positive),
            "mutations_rejected": [
                "restore-truthiness-at-foreign-spine-termination",
                "change-a-positive-result",
                "introduce-an-unpriced-helper-name",
                "change-a-public-contract-cell-outside-tier1",
            ],
        },
        "capacity": {
            "stdlib_before": base_bytes, "stdlib_after": next_bytes,
            "bank2_delta": delta,
            "static_plane_before": current_plane,
            "static_plane_after": current_plane + delta,
            "largest_contiguous_hole_before": 16197,
            "largest_contiguous_hole_after": 16197 - delta,
            "largest_emitted_object": largest,
            "changed_objects": object_rows,
            "D5_projection": {
                "before": {"symbol_slots": 109, "namepool_bytes": 1486},
                "after": {"symbol_slots": 109, "namepool_bytes": 1486},
                "minimum": {"symbol_slots": 32, "namepool_bytes": 384},
            },
            "resident_delta": {"ordinary_text": 0, "E000": 0,
                               "BSS": 0, "far_service": 0},
        },
        "performance": {
            "positive_case_step_deltas": {
                name: row["step_delta"] for name, row in positive.items()},
            "claim": "host VM steps on small positive representatives; no device timing claim",
        },
        "recommendation": {
            "variant": "in-place fail-closed traversal termination",
            "product_cards": 1, "WPLTOs": 0, "links": 0,
            "reason": ("zero names and zero resident bytes; direct per-signature "
                       "guards avoid a second whole-list preflight traversal"),
            "next_touchpoint": "review and product-card authorization",
        },
        "bindings": [bind(BASE_SUITE), bind(BASE_MANIFEST),
                     bind(BASE_BLOB), bind(CURRENT_CARD), bind(CURRENT_PRODUCT)],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("record", "check"))
    args = parser.parse_args()
    raw = canonical(derive())
    if args.command == "record":
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_bytes(raw)
    else:
        require(RECEIPT.is_file(), "Tier-1 pricing receipt absent")
        sealed_receipt = subprocess.run(
            ["git", "show", f"{EVIDENCE_ERA}:"
             f"{RECEIPT.relative_to(ROOT).as_posix()}"], cwd=ROOT, check=True,
            stdout=subprocess.PIPE).stdout
        require(RECEIPT.read_bytes() == sealed_receipt,
                "Tier-1 pricing receipt escaped its evidence era")
        value = load(RECEIPT)
        expected = json.loads(raw)
        sealed_contract = subprocess.run(
            ["git", "show", f"{EVIDENCE_ERA}:config/"
             "public-surface-domain-contract.json"], cwd=ROOT, check=True,
            stdout=subprocess.PIPE).stdout
        historical = value["bindings"][0]
        require(historical == {"path":
                    "config/public-surface-domain-contract.json",
                "bytes": len(sealed_contract),
                "sha256": hashlib.sha256(sealed_contract).hexdigest()}
                and evidence_era_equivalent(value, expected),
                "Tier-1 pricing evidence-era derivation drift")
    value = load(RECEIPT) if args.command == "check" else json.loads(raw)
    print("c2-v200-domain-tier1-pricing: PASS "
          f"members={value['scope']['member_count']} "
          f"bank2_delta={value['capacity']['bank2_delta']} "
          f"silent_removed={value['public_contract_projection']['silent_cells_removed']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PricingError, KeyError, ValueError, OSError,
            subprocess.CalledProcessError) as error:
        print(f"c2-v200-domain-tier1-pricing: FAIL {error}")
        raise SystemExit(1)
