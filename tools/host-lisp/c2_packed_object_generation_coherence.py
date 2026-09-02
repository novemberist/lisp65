#!/usr/bin/env python3
"""Prove that packed bytecode callers and implementations share one world.

Transitive closure answers whether a callee exists.  This gate answers the
orthogonal question whether the callee that exists satisfies the contract
materialized by its caller.  It also binds every function to one manifest,
one blob and (when supplied) one source-suite generation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


class CoherenceError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CoherenceError(message)


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
    try:
        name = path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        name = path.resolve().as_posix()
    return {"path": name, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def _strings(row: dict[str, Any]) -> list[str]:
    return [item["string"] for item in row.get("literals", [])
            if isinstance(item, dict) and isinstance(item.get("string"), str)]


def _callees(row: dict[str, Any]) -> list[str]:
    return [item["symbol"] for item in row.get("literals", [])
            if isinstance(item, dict) and isinstance(item.get("symbol"), str)]


def _functions(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = [row for row in manifest.get("entries", [])
            if isinstance(row, dict) and row.get("kind") == "function"
            and isinstance(row.get("name"), str)]
    names = [row["name"] for row in rows]
    require(len(rows) == len(set(names)), "function owner is not unique")
    return {row["name"]: row for row in rows}


def source_generation(suite_path: Path | None) -> dict[str, Any] | None:
    if suite_path is None:
        return None
    suite = load(suite_path)
    sources: list[dict[str, Any]] = []
    for raw in suite.get("sources", []):
        path = Path(raw)
        if not path.is_absolute():
            path = ROOT / path
        sources.append(bind(path))
    require(sources, "suite source population is empty")
    identity = [{"path": row["path"], "sha256": row["sha256"]}
                for row in sources]
    return {"suite": bind(suite_path), "source_count": len(sources),
            "sources": sources,
            "generation_sha256": hashlib.sha256(canonical(identity)).hexdigest()}


def _contract(functions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    caller = functions.get("%native-prompt")
    target = functions.get("%rl-screen-tail")
    require(caller is not None and target is not None,
            "native prompt generation pair is incomplete")
    caller_strings = _strings(caller)
    caller_callees = _callees(caller)
    target_strings = _strings(target)
    target_callees = _callees(target)
    delegates = "%rl-screen-tail" in caller_callees
    caller_owns_prompt = "lisp65> " in caller_strings
    target_owns_prompt = "lisp65> " in target_strings
    target_direct_cells = "%rl-render" in target_callees
    requirement = ("callee-provides-native-prompt"
                   if delegates and not caller_owns_prompt
                   else "caller-provides-native-prompt")
    capability = ("direct-cell-native-prompt"
                  if target_owns_prompt and target_direct_cells
                  else "position-only-no-prompt")
    failures: list[str] = []
    if requirement == "callee-provides-native-prompt" and not target_owns_prompt:
        failures.append("delegating-native-prompt-resolves-to-promptless-tail")
    if target_owns_prompt and not target_direct_cells:
        failures.append("prompt-provider-lacks-editor-render-owner")
    return {"caller": "%native-prompt", "implementation": "%rl-screen-tail",
        "caller_requirement": requirement,
        "implementation_capability": capability,
        "caller_strings": caller_strings, "caller_callees": caller_callees,
        "implementation_strings": target_strings,
        "implementation_callees": target_callees,
        "failures": failures}


def derive(manifest_path: Path, blob_path: Path,
           suite_path: Path | None = None,
           packed_blob: bytes | None = None) -> dict[str, Any]:
    manifest = load(manifest_path)
    functions = _functions(manifest)
    blob = blob_path.read_bytes()
    require(len(blob) == int(manifest["code_bytes"]),
            "manifest/blob extent divergence")
    rows: list[dict[str, Any]] = []
    for name, entry in sorted(functions.items()):
        start, size = int(entry["blob_offset"]), int(entry["length"])
        require(0 <= start <= len(blob) and start + size <= len(blob),
                f"object outside manifest blob: {name}")
        payload = blob[start:start + size]
        rows.append({"name": name, "offset": start, "bytes": size,
            "sha256": hashlib.sha256(payload).hexdigest()})
    packed = blob if packed_blob is None else packed_blob
    packed_equal = packed == blob
    contract = _contract(functions)
    failures = list(contract["failures"])
    if not packed_equal:
        failures.append("packed-blob-differs-from-materialized-generation")
    return {"status": ("PASS: PACKED OBJECT GENERATION COHERENT"
                       if not failures else "FIRST RED"),
        "manifest": bind(manifest_path), "blob": bind(blob_path),
        "source_generation": source_generation(suite_path),
        "object_count": len(rows), "objects": rows,
        "packed_blob": {"bytes": len(packed),
            "sha256": hashlib.sha256(packed).hexdigest(),
            "equals_materialized_blob": packed_equal},
        "contract": contract, "failures": failures}


def require_coherent(value: dict[str, Any]) -> None:
    require(value["status"] == "PASS: PACKED OBJECT GENERATION COHERENT"
            and value["failures"] == []
            and value["packed_blob"]["equals_materialized_blob"] is True,
            f"packed object generation incoherent: {value['failures']}")


def sharp_mutation(candidate_manifest: Path, candidate_blob: Path,
                   device_manifest: Path) -> dict[str, Any]:
    candidate = load(candidate_manifest)
    device = load(device_manifest)
    current = _functions(candidate)
    old = _functions(device)
    require("%native-prompt" in current and "%rl-screen-tail" in old,
            "banner-only mutation inputs incomplete")
    mutant = dict(current)
    mutant["%rl-screen-tail"] = old["%rl-screen-tail"]
    contract = _contract(mutant)
    require(contract["failures"] == [
        "delegating-native-prompt-resolves-to-promptless-tail"],
        "banner-only generation mutation did not fail sharply")
    return {"status": "PASS: BANNER-ONLY MIXED GENERATION REJECTED",
        "mutation": "successor native-prompt plus predecessor rl-screen-tail",
        "candidate_manifest": bind(candidate_manifest),
        "device_manifest": bind(device_manifest),
        "contract": contract,
        "mutations_rejected": [
            "successor-caller-with-predecessor-implementation"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("blob", type=Path)
    parser.add_argument("--suite", type=Path)
    parser.add_argument("--packed-blob", type=Path)
    parser.add_argument("--device-red-manifest", type=Path)
    args = parser.parse_args()
    try:
        packed = args.packed_blob.read_bytes() if args.packed_blob else None
        value = derive(args.manifest, args.blob, args.suite, packed)
        require_coherent(value)
        if args.device_red_manifest:
            value["sharp_mutation"] = sharp_mutation(
                args.manifest, args.blob, args.device_red_manifest)
        print(json.dumps(value, indent=2, sort_keys=True))
        return 0
    except (CoherenceError, KeyError, ValueError) as error:
        print(f"generation coherence: FIRST RED: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
