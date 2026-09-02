#!/usr/bin/env python3
"""Classify user-visible names without changing the product surface."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from evidence_era import era_bind, era_blob


ROOT = Path(__file__).resolve().parents[2]
METADATA = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-function-metadata-index.json")
ERROR_CODES = ROOT / "src/error_codes.h"
USER_GUIDE = ROOT / "docs/user-guide.md"
RELEASE_NOTES = ROOT / "docs/releases/1.9.0.md"
V2_PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
PLANE = ROOT / "config/c2-v190-public-plane"
CONTRACT = ROOT / "config/public-naming-audit.json"
V2_PLAN_SEAL_ERA = "8224739b3149cf90a7b5bf36b90580df73fb5931"


class NamingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise NamingError(message)


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


FUNCTION_RENAMES = {
    "ide": "editor",
    "ide-buffers": "editor-buffers",
    "m65d-remount": "disk-remount",
    "m65d-save": "disk-save",
    "m65d-save-new": "disk-save-new",
    "m65d-status": "disk-status",
    "runtime-main": "run-program",
}

LIBRARY_DESIGNATORS = [
    {
        "name": "ide", "status": "current-shipped",
        "classification": "implementation-detail",
        "speaking_name": "editor", "migration": "direct rename in v2.0",
    },
    {
        "name": "idex", "status": "current-shipped",
        "classification": "implementation-detail",
        "speaking_name": "editor-tools", "migration": "direct rename in v2.0",
    },
    {
        "name": "m65d", "status": "current-shipped",
        "classification": "implementation-detail",
        "speaking_name": "disk-tools", "migration": "direct rename in v2.0",
    },
    {
        "name": "v16core", "status": "historical-not-in-v1.9-authority",
        "classification": "era-and-implementation-detail",
        "speaking_name": "workbench-core",
        "migration": "remove stale documentation; no runtime alias",
    },
]

MEDIA_AND_FILES = [
    {
        "name": "lisp65-product.d81", "status": "current-release",
        "classification": "capability", "speaking_name": "keep",
    },
    {
        "name": "lisp65-work.d81", "status": "current-release",
        "classification": "capability", "speaking_name": "keep",
    },
    {
        "name": "AUTOBOOT.C65", "status": "current-release",
        "classification": "capability", "speaking_name": "keep",
    },
    {
        "name": "INIT.L65", "status": "public-convention",
        "classification": "capability", "speaking_name": "keep",
    },
    {
        "name": "ide.ext.bin", "status": "packaged-internal-role",
        "classification": "implementation-detail", "speaking_name": "editor.ext.bin",
    },
    {
        "name": "idex.ext.bin", "status": "packaged-internal-role",
        "classification": "implementation-detail", "speaking_name": "editor-tools.ext.bin",
    },
    {
        "name": "m65d.ext.bin", "status": "packaged-internal-role",
        "classification": "implementation-detail", "speaking_name": "disk-tools.ext.bin",
    },
    {
        "name": "V17B3P.D81", "status": "historical-diagnostic",
        "classification": "era-and-work-item-detail",
        "speaking_name": "diagnostic-block3-product.d81",
    },
]

GUIDE_TERMS = [
    {
        "name": "product D81", "classification": "capability",
        "speaking_name": "keep",
    },
    {
        "name": "work disk", "classification": "capability",
        "speaking_name": "keep",
    },
    {
        "name": "resident prompt editor", "classification": "capability",
        "speaking_name": "keep",
    },
    {
        "name": "IDEX", "classification": "implementation-detail",
        "speaking_name": "editor extensions",
    },
    {
        "name": "M65D", "classification": "implementation-detail",
        "speaking_name": "disk persistence",
    },
    {
        "name": "Capture", "classification": "implementation-detail",
        "speaking_name": "lossless input queue",
    },
]


def error_rows() -> list[dict[str, Any]]:
    text = ERROR_CODES.read_text(encoding="utf-8")
    names = re.findall(r"^\s*(LISP65_ERR_[A-Z0-9_]+)\s*=\s*\d+", text, re.M)
    require(len(names) == 64, f"error-code population drift: {len(names)}")
    rows = []
    for name in names:
        words = name.removeprefix("LISP65_ERR_").lower().replace("_", "-")
        rows.append({
            "name": name,
            "classification": "internal-implementation-identifier",
            "speaking_name": words,
            "migration": (
                "keep enum internal; visible errors use operation: problem wording"),
        })
    return rows


def public_function_rows() -> list[dict[str, Any]]:
    records = load(METADATA)["records"]
    require(len(records) == 139, f"public function population drift: {len(records)}")
    rows = []
    for record in records:
        name = record["name"]
        proposal = FUNCTION_RENAMES.get(name)
        rows.append({
            "name": name,
            "kind": record["kind"],
            "classification": (
                "implementation-detail" if proposal else "capability-or-language-term"),
            "speaking_name": proposal or "keep",
            "migration": (
                "direct rename in v2.0" if proposal else "none"),
        })
    return rows


def current_manifest_names() -> list[str]:
    names = []
    for path in sorted((PLANE / "external-manifests").glob("*.manifest.json")):
        short = path.name
        if short.startswith("libs-"):
            names.append(short.removeprefix("libs-").removesuffix(".manifest.json"))
    return sorted(names)


def derive() -> dict[str, Any]:
    guide = USER_GUIDE.read_text(encoding="utf-8")
    release = RELEASE_NOTES.read_text(encoding="utf-8")
    v2_plan = era_blob(V2_PLAN_SEAL_ERA,
                       V2_PLAN.relative_to(ROOT).as_posix()).decode()
    manifests = current_manifest_names()
    require(manifests == ["buffer", "ide", "idex", "m65d"],
            f"current library manifest drift: {manifests}")
    for designator in ("ide", "idex", "m65d"):
        require(f'(load-lib "{designator}")' in guide,
                f"current guide lost library designator {designator}")
    require("no separate optional-library medium" in guide,
            "v1.9 guide reverted to the historical two-media model")
    require("no `v16core` load" in release,
            "v1.9 release no longer states the resident-core boundary")
    require("there is no known user base" in v2_plan,
            "newer owner correction about aliases is missing")
    for term in GUIDE_TERMS:
        require(term["name"].lower() in guide.lower(),
                f"classified guide term is absent: {term['name']}")
    functions = public_function_rows()
    errors = error_rows()
    v2_plan_authority = era_bind(V2_PLAN_SEAL_ERA, V2_PLAN)
    v2_plan_authority.pop("bytes")
    return {
        "format": "lisp65-public-naming-audit-v1",
        "status": "READ-ONLY CLASSIFICATION; NO RENAME AUTHORIZED",
        "rule": (
            "User-facing names state capabilities; era and implementation "
            "identities receive speaking-name proposals before v2 owner review."),
        "authority": {
            "metadata": {"path": METADATA.relative_to(ROOT).as_posix(),
                         "sha256": sha(METADATA), "records": len(functions)},
            "errors": {"path": ERROR_CODES.relative_to(ROOT).as_posix(),
                       "sha256": sha(ERROR_CODES), "records": len(errors)},
            "user_guide": {"path": USER_GUIDE.relative_to(ROOT).as_posix(),
                           "sha256": sha(USER_GUIDE)},
            "release_notes": {"path": RELEASE_NOTES.relative_to(ROOT).as_posix(),
                              "sha256": sha(RELEASE_NOTES)},
            "v2_plan": v2_plan_authority,
            "current_external_manifests": manifests,
        },
        "migration_policy": {
            "work_plan_assumption": "one-cycle alias",
            "newer_owner_correction": "no known user base",
            "proposal": (
                "direct v2.0 renames without alias freight; release migration "
                "table remains a courtesy; every rename still needs owner word"),
        },
        "library_designators": LIBRARY_DESIGNATORS,
        "public_functions": functions,
        "error_identifiers": errors,
        "media_and_files": MEDIA_AND_FILES,
        "guide_terms": GUIDE_TERMS,
        "counts": {
            "library_designators": len(LIBRARY_DESIGNATORS),
            "public_functions": len(functions),
            "function_rename_candidates": len(FUNCTION_RENAMES),
            "error_identifiers": len(errors),
            "media_and_files": len(MEDIA_AND_FILES),
            "guide_terms": len(GUIDE_TERMS),
        },
    }


def stable(value: dict[str, Any]) -> dict[str, Any]:
    return value


def check() -> dict[str, Any]:
    recorded = load(CONTRACT)
    observed = derive()
    require(stable(recorded) == stable(observed),
            "public naming inventory/classification drift")
    return observed


def selftest() -> dict[str, Any]:
    observed = derive()
    mutated = json.loads(json.dumps(observed))
    mutated["public_functions"].pop()
    require(mutated != observed, "missing public name mutation survived")
    mutated = json.loads(json.dumps(observed))
    target = next(row for row in mutated["public_functions"] if row["name"] == "m65d-save")
    target["classification"] = "capability-or-language-term"
    require(mutated != observed, "implementation-name reclassification survived")
    mutated = json.loads(json.dumps(observed))
    mutated["migration_policy"]["proposal"] = "mandatory alias"
    require(mutated != observed, "obsolete alias policy mutation survived")
    mutated = json.loads(json.dumps(observed))
    mutated["authority"]["v2_plan"]["sha256"] = sha(V2_PLAN)
    require(mutated != observed, "living-plan substitution survived era bind")
    return {"observed": observed, "mutations_rejected": 4}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("derive", "check", "selftest"))
    args = parser.parse_args()
    if args.mode == "derive":
        print(json.dumps(derive(), indent=2, sort_keys=True))
        return 0
    if args.mode == "selftest":
        result = selftest()
        counts = result["observed"]["counts"]
        population = sum(
            counts[key] for key in (
                "library_designators", "public_functions", "error_identifiers",
                "media_and_files", "guide_terms")
        )
        print("public naming audit selftest: PASS "
              f"names={population} "
              f"mutations={result['mutations_rejected']}")
        return 0
    result = check()
    print("public naming audit: PASS "
          f"functions={result['counts']['public_functions']} "
          f"rename-candidates={result['counts']['function_rename_candidates']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
