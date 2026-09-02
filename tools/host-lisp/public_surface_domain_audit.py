#!/usr/bin/env python3
"""Lock the public Lisp surface's target-profile domain behaviour.

The audit intentionally executes the product's materialized bytecode objects,
not a separately implemented host library.  Every cell uses one representative
object kind for the complete required argument vector; heterogeneous calls may
therefore reject every representative.  That is useful here: this is a stable
out-of-domain contract, not a positive conformance suite.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
import bytecode_p0_stdlib as STD  # noqa: E402


METADATA = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-function-metadata-index.json")
PLANE = ROOT / "config/c2-v190-public-plane"
STDLIB_MANIFEST = PLANE / "static-plane/stdlib-p0.manifest.json"
STDLIB_BLOB = PLANE / "static-plane/stdlib-p0.blob.bin"
EXTERNAL_MANIFESTS = (
    "libs-ide.manifest.json",
    "libs-idex.manifest.json",
    "libs-m65d.manifest.json",
    "libs-buffer.manifest.json",
    "compiler-lcc.manifest.json",
)
RELEASE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.0.0-release-card-r3-receipt.json")
CONTRACT = ROOT / "config/public-surface-domain-contract.json"
TIER2_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.0-domain-tier2-product-card-r1-receipt.json")
VM_SOURCE = ROOT / "src/vm.c"

DOMAINS: dict[str, Any] = {
    "number": 7,
    "string": {"string": "abc"},
    "symbol": {"symbol": "alpha"},
    "nil": None,
    "list": [1, 2],
    "function": {"symbol": "car"},
}

# These are domains in which a successful *uniform argument vector* has a
# documented meaning.  Success outside the declared set is classified as
# silently-wrong.  VM rejection is always recorded as error-raised.
POLICY_GROUPS: dict[str, tuple[set[str], set[str]]] = {
    "any-object": ({
        "atom", "bufferp", "consp", "cons", "eq", "equal", "eval", "list",
        "list*", "null", "numberp", "prin1", "princ", "print", "stringp",
        "symbolp", "write",
    }, set(DOMAINS)),
    "number": ({
        "*", "+", "-", "/", "/=", "<", "<=", "=", ">", ">=", "abs",
        "char->string", "char-downcase", "char-upcase", "make-buffer", "max",
        "min", "mod", "number->string", "random", "random-seed",
        "screen-put-char", "write-char", "zerop",
    }, {"number"}),
    "string": ({
        "compile-buffer-to-lib", "compile-file-to-lib", "eval-buffer", "intern", "load",
        "load-file-to-buffer", "load-lib", "m65d-save", "m65d-save-new",
        "read-from-string", "save-buffer-to", "string->buffer", "string-append",
        "string-downcase", "string-length", "string-upcase", "write-line",
        "write-string",
    }, {"string"}),
    "uniform-strings": ({
        "search", "string-equal", "string-prefix-p", "string-suffix-p",
        "string-trim", "string<", "string=",
    }, {"string"}),
    "proper-list": ({
        "append", "butlast", "copy-list", "last", "nreverse", "reverse",
    }, {"nil", "list"}),
    "list-derived": ({
        "count", "find", "getf", "length", "member", "position", "remf",
    }, {"nil", "list"}),
    "symbol": ({
        "boundp", "set", "symbol-value",
    }, {"symbol", "function"}),
    "syntax-transformer": ({
        "and", "case", "cond", "decf", "defparameter", "defun", "defvar",
        "dolist", "dotimes", "incf", "let", "let*", "or", "pop", "push",
        "setf", "unless", "when", "while",
    }, set(DOMAINS)),
    "heterogeneous-or-no-representative": ({
        "apply", "assoc", "buffer->string", "buffer-length", "buffer-ref", "buffer-set!",
        "car", "cdr", "char", "dir", "edit", "every", "filter", "funcall",
        "gensym", "ide", "ide-buffers",
        "key-event", "m65d-remount", "m65d-status", "mapc", "mapcan", "mapcar",
        "nth", "nthcdr", "peek", "poke", "reduce", "rplaca", "rplacd",
        "runtime-main", "screen-clear", "screen-size", "screen-write-string",
        "some", "string-ref", "substring", "terpri",
    }, set()),
}

# car/cdr deliberately keep NIL permissive; their non-list success is exactly
# the domain-discipline family that this audit is intended to expose.
SPECIAL_ALLOWED = {"car": {"nil", "list"}, "cdr": {"nil", "list"}}

DELIVERED_CALLPRIMS = [
    0, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 18, 19, 20,
    21, 22, 23, 24, 25, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39,
    41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57,
    58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74,
    75, 76, 77, 78, 79, 80, 81, 82, 83,
]
TOMBSTONED_CALLPRIMS = [1, 2, 12, 26, 27, 40]
RELEASE_ELF_SHA256 = "96ba670981172fab72383d40cf6da24d3318749d03a916014b716d4b881ecd05"


class AuditError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AuditError(message)


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tier2_contract_p(recorded: dict[str, Any]) -> bool:
    rows = {row["name"]: row for row in recorded.get("rows", [])}
    expected = {"error-raised": 553, "documented-permissive": 179,
                "silently-wrong": 102}
    return (recorded.get("counts") == expected
            and all(rows.get(name, {}).get("cells", {}).get(domain, {}).get(
                    "error") == "TypeError"
                for name in ("car", "cdr")
                for domain in ("number", "string", "symbol", "function")))


def validate_tier2_native_authority(recorded: dict[str, Any]) -> None:
    require(TIER2_RECEIPT.is_file(), "Tier-2 native authority absent")
    receipt = load(TIER2_RECEIPT)
    tier = receipt.get("final_product", {}).get("domain_Tier_2", {})
    durable = receipt.get("durable_contract", {})
    artifacts = receipt.get("artifacts_after", {})
    elf = artifacts.get("ELF", {})
    source = tier.get("source", {}).get("source", {})
    elf_path = ROOT / str(elf.get("path", ""))
    require(receipt.get("status") ==
                "PASS: V2.0 DOMAIN TIER 2 FINAL PRODUCT GREEN"
            and tier.get("contract_counts") == recorded["counts"]
            and durable.get("path") == CONTRACT.relative_to(ROOT).as_posix()
            and durable.get("sha256") == sha(CONTRACT)
            and source.get("path") == VM_SOURCE.relative_to(ROOT).as_posix()
            and source.get("sha256") == sha(VM_SOURCE)
            and elf_path.is_file() and elf.get("sha256") == sha(elf_path),
            "Tier-2 native semantics are not bound to the living contract")


@contextmanager
def recorded_native_semantics(recorded: dict[str, Any]) -> Iterator[None]:
    """Make the host executor consume the final product's opcode contract."""
    if not tier2_contract_p(recorded):
        yield
        return
    validate_tier2_native_authority(recorded)
    old_car, old_cdr = B.Heap.car, B.Heap.cdr

    def require_cons(heap: B.Heap, value: int, name: str) -> Any:
        if value == B.NIL:
            return None
        if not heap.consp(value):
            raise B.VMError("TypeError", f"{name} expects cons or nil")
        return heap.cell(value)

    def strict_car(heap: B.Heap, value: int) -> int:
        cell = require_cons(heap, value, "car")
        return B.NIL if cell is None else cell.a

    def strict_cdr(heap: B.Heap, value: int) -> int:
        cell = require_cons(heap, value, "cdr")
        return B.NIL if cell is None else cell.b

    B.Heap.car, B.Heap.cdr = strict_car, strict_cdr
    try:
        yield
    finally:
        B.Heap.car, B.Heap.cdr = old_car, old_cdr


def policy_map(names: set[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for policy, (members, allowed) in POLICY_GROUPS.items():
        for name in members:
            require(name not in out, f"duplicate domain policy for {name}")
            out[name] = {"policy": policy, "successful_domains": sorted(allowed)}
    for name, allowed in SPECIAL_ALLOWED.items():
        out[name] = {"policy": "proper-list", "successful_domains": sorted(allowed)}
    missing = sorted(names - set(out))
    extra = sorted(set(out) - names)
    require(not missing and not extra,
            f"domain policy population drift missing={missing} extra={extra}")
    return out


def manifest_inputs() -> list[tuple[Path, Path]]:
    rows = [(STDLIB_MANIFEST, STDLIB_BLOB)]
    for name in EXTERNAL_MANIFESTS:
        manifest_path = PLANE / "external-manifests" / name
        manifest = load(manifest_path)
        rows.append((manifest_path, ROOT / manifest["blob"]))
    return rows


def load_product() -> tuple[B.Heap, dict[int, B.CodeObject], set[int], dict[int, str], list[dict[str, Any]]]:
    heap = B.Heap()
    directory: dict[int, B.CodeObject] = {}
    macros: set[int] = set()
    code_names: dict[int, str] = {}
    authorities = []
    for manifest_path, blob_path in manifest_inputs():
        manifest = load(manifest_path)
        blob = blob_path.read_bytes()
        require(hashlib.sha256(blob).hexdigest() == manifest["blob_sha256"],
                f"blob drift: {blob_path}")
        patches = {int(row["blob_offset"]): int(row["node"])
                   for row in manifest["literal_patches"]}
        for entry in manifest["entries"]:
            code = STD._patched_code_from_manifest_entry(
                heap, manifest, blob, entry, patches)
            symbol = heap.intern(entry["name"].lower())
            directory[symbol] = code
            code_names[id(code)] = entry["name"].lower()
            if entry.get("kind") == "macro" or int(entry.get("flags", 0)) == 1:
                macros.add(symbol)
        authorities.append({
            "manifest": manifest_path.relative_to(ROOT).as_posix(),
            "manifest_sha256": sha(manifest_path),
            "blob": blob_path.relative_to(ROOT).as_posix(),
            "blob_sha256": hashlib.sha256(blob).hexdigest(),
            "entries": len(manifest["entries"]),
        })
    return heap, directory, macros, code_names, authorities


def minimum_args(record: dict[str, Any], code: B.CodeObject | None) -> int:
    arity = record["arity"]
    if arity.get("status") == "exact-code-object":
        required = int(arity["required"])
        if required == 0:
            return 1
        return required
    if code is None:
        return 1
    optional = code.flags >> B.CO_FLAG_OPTIONAL_SHIFT
    required = code.nargs - optional
    return max(1, required)


def execute_cell(
    base_heap: B.Heap,
    directory: dict[int, B.CodeObject],
    macros: set[int],
    code_names: dict[int, str],
    ledger: dict[str, Any],
    record: dict[str, Any],
    domain: str,
    allowed: set[str],
) -> dict[str, Any]:
    heap = base_heap.clone()
    target = heap.intern(record["name"].lower())
    code = directory.get(target)
    argc = minimum_args(record, code)
    value = B.obj_from_json(heap, DOMAINS[domain])
    vm = B.P0VM(
        heap=heap,
        directory=directory,
        macro_symbols=macros,
        code_names=code_names,
        max_steps=200_000,
        max_call_args=32,
        key_events=[],
        memory_read_sequences={0xFF83: [0] * 64},
        abi_profile="dialect-v2",
        abi_ledger=ledger,
        delivered_callprims=DELIVERED_CALLPRIMS,
    )
    try:
        result = vm._invoke_function(target, [value] * argc)
    except B.VMError as error:
        return {
            "classification": "error-raised",
            "argc": argc,
            "error": error.status,
            "detail": str(error),
            "steps": vm.steps,
        }
    classification = (
        "documented-permissive" if domain in allowed else "silently-wrong")
    return {
        "classification": classification,
        "argc": argc,
        "result": heap.obj_to_text(result),
        "steps": vm.steps,
    }


def release_authority() -> dict[str, Any]:
    receipt = load(RELEASE_RECEIPT)
    found: list[dict[str, Any]] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            if (str(value.get("path", "")).endswith(
                    "lisp65-c2-substitution-linked.prg.elf")
                    and value.get("sha256") == RELEASE_ELF_SHA256):
                found.append(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(receipt)
    require(found, "v2.0 release receipt does not bind the product ELF")
    return {
        "receipt": RELEASE_RECEIPT.relative_to(ROOT).as_posix(),
        "receipt_sha256": sha(RELEASE_RECEIPT),
        "elf_sha256": RELEASE_ELF_SHA256,
        "table_entries": 84,
        "delivered_ids": DELIVERED_CALLPRIMS,
        "tombstoned_ids": TOMBSTONED_CALLPRIMS,
    }


def derive() -> dict[str, Any]:
    metadata = load(METADATA)
    records = metadata["records"]
    require(len(records) == 139, f"public population drift: {len(records)}")
    names = [record["name"] for record in records]
    require(len(set(names)) == len(names), "duplicate public metadata name")
    policies = policy_map(set(names))
    heap, directory, macros, code_names, authorities = load_product()
    ledger = C._abi_ledger("dialect-v2", None)
    rows = []
    counts = {key: 0 for key in (
        "error-raised", "documented-permissive", "silently-wrong")}
    for record in records:
        policy = policies[record["name"]]
        allowed = set(policy["successful_domains"])
        cells = {}
        for domain in DOMAINS:
            cell = execute_cell(
                heap, directory, macros, code_names, ledger,
                record, domain, allowed)
            cells[domain] = cell
            counts[cell["classification"]] += 1
        rows.append({
            "name": record["name"],
            "kind": record["kind"],
            "library": record.get("authority", {}).get("library"),
            "policy": policy,
            "cells": cells,
        })
    return {
        "format": "lisp65-public-surface-domain-contract-v1",
        "status": "PROFILE-FAITHFUL READ-ONLY DOMAIN MATRIX",
        "rule": (
            "Every metadata-public symbol owns six domain cells; a changed "
            "classification or a new symbol without a row fails before repair."),
        "method": (
            "Each cell invokes the materialized product bytecode with the same "
            "representative object in every required argument position."),
        "population": {
            "path": METADATA.relative_to(ROOT).as_posix(),
            "sha256": sha(METADATA),
            "records": len(records),
        },
        "product_profile": release_authority(),
        "materialized_authorities": authorities,
        "domains": DOMAINS,
        "counts": counts,
        "rows": rows,
    }


def semantic_cell(cell: dict[str, Any]) -> dict[str, Any]:
    """Project only target-visible contract semantics.

    Host step counts, argument bookkeeping and diagnostic prose describe the
    executor, not the delivered Lisp contract.
    """
    return {key: cell[key] for key in
            ("classification", "result", "error") if key in cell}


def semantic_rows(contract: dict[str, Any]) -> list[dict[str, Any]]:
    return [{**{key: row[key] for key in
                ("name", "kind", "library", "policy")},
             "cells": {domain: semantic_cell(cell)
                       for domain, cell in row["cells"].items()}}
            for row in contract["rows"]]


def stable_projection(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "format": contract["format"],
        "population": contract["population"],
        "product_profile": contract["product_profile"],
        "domains": contract["domains"],
        "counts": contract["counts"],
        "rows": semantic_rows(contract),
    }


def derive_recorded_world(recorded: dict[str, Any]) -> dict[str, Any]:
    """Execute the materialized stdlib authority named by the living contract."""
    candidates = [row for row in recorded["materialized_authorities"]
                  if Path(row.get("manifest", "")).name ==
                     "stdlib-p0.manifest.json"
                  and Path(row.get("blob", "")).name ==
                     "stdlib-p0.blob.bin"]
    require(len(candidates) == 1,
            "public domain contract must bind exactly one stdlib authority")
    row = candidates[0]
    manifest, blob = ROOT / row["manifest"], ROOT / row["blob"]
    require(manifest.is_file() and blob.is_file()
            and sha(manifest) == row["manifest_sha256"]
            and sha(blob) == row["blob_sha256"],
            "public domain contract materialized authority unavailable or stale")
    global STDLIB_MANIFEST, STDLIB_BLOB
    old_manifest, old_blob = STDLIB_MANIFEST, STDLIB_BLOB
    try:
        STDLIB_MANIFEST, STDLIB_BLOB = manifest, blob
        with recorded_native_semantics(recorded):
            return derive()
    finally:
        STDLIB_MANIFEST, STDLIB_BLOB = old_manifest, old_blob


def check() -> dict[str, Any]:
    recorded = load(CONTRACT)
    observed = derive_recorded_world(recorded)
    require(stable_projection(observed) == stable_projection(recorded),
            "public domain contract drift; inspect the named cell before updating")
    return observed


def selftest() -> dict[str, Any]:
    observed = derive_recorded_world(load(CONTRACT))
    mutated = json.loads(json.dumps(observed))
    mutated["rows"].pop()
    require(stable_projection(mutated) != stable_projection(observed),
            "removed public row mutation survived")
    mutated = json.loads(json.dumps(observed))
    mutated["rows"][0]["cells"]["number"]["classification"] = "silently-wrong"
    require(stable_projection(mutated) != stable_projection(observed),
            "classification flip mutation survived")
    value_cell = next(cell for row in observed["rows"]
                      for cell in row["cells"].values()
                      if "result" in cell)
    mutated = json.loads(json.dumps(observed))
    target = next(cell for row in mutated["rows"]
                  for cell in row["cells"].values()
                  if "result" in cell)
    target["result"] = value_cell["result"] + "-mutation"
    require(stable_projection(mutated) != stable_projection(observed),
            "target result mutation survived")
    error_cell = next(cell for row in observed["rows"]
                      for cell in row["cells"].values()
                      if "error" in cell)
    mutated = json.loads(json.dumps(observed))
    target = next(cell for row in mutated["rows"]
                  for cell in row["cells"].values()
                  if "error" in cell)
    target["error"] = error_cell["error"] + "Mutation"
    require(stable_projection(mutated) != stable_projection(observed),
            "target error mutation survived")
    mutated = json.loads(json.dumps(observed))
    mutated["rows"][0]["cells"]["number"]["steps"] += 1
    mutated["rows"][0]["cells"]["number"]["detail"] = "host-only mutation"
    require(stable_projection(mutated) == stable_projection(observed),
            "host diagnostics remain pinned as product semantics")
    mutated = json.loads(json.dumps(observed))
    mutated["product_profile"]["delivered_ids"].append(12)
    require(stable_projection(mutated) != stable_projection(observed),
            "invented delivered primitive mutation survived")
    require(12 in observed["product_profile"]["tombstoned_ids"],
            "product profile lost tombstone 12")
    return {"mutations_rejected": 5, "diagnostic_mutations_ignored": 2,
            "observed": observed}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("check", "selftest", "derive"))
    args = parser.parse_args()
    if args.mode == "derive":
        print(json.dumps(derive_recorded_world(load(CONTRACT)),
                         indent=2, sort_keys=True))
        return 0
    if args.mode == "selftest":
        result = selftest()
        print("public surface domain selftest: PASS "
              f"rows={len(result['observed']['rows'])} "
              f"mutations={result['mutations_rejected']}")
        return 0
    result = check()
    print("public surface domain audit: PASS "
          f"rows={len(result['rows'])} cells={sum(result['counts'].values())} "
          f"silent={result['counts']['silently-wrong']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
