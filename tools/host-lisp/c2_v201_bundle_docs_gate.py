#!/usr/bin/env python3
"""Validate the user documents actually packed in the v2.0.1 bundle."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v200_public_surface_medium_projection as MEDIUM  # noqa: E402


VERSION = "2.0.1"
TOP = f"lisp65-{VERSION}"
METADATA = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-function-metadata-index.json")
MEDIUM_RECEIPT = MEDIUM.RECEIPT
ERRORS = ROOT / "config/error-code-contract.json"
KEYMAP = ROOT / "config/v11-l-lite-keymap.json"
TIER1 = ROOT / "lib/domain-tier1.lisp"
DEVICE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.0-release-strip-device-result-receipt.json")
DOC_PATHS = {
    "release": "docs/release-notes.md",
    "guide": "docs/user-guide.md",
    "reference": "docs/language-reference.md",
    "issues": "docs/known-issues.md",
    "keymap": "docs/generated/ide-keymap.md",
}
SOURCE_DOCS = {
    "release": ROOT / "docs/releases/2.0.1.md",
    "guide": ROOT / "docs/user-guide.md",
    "reference": ROOT / "docs/language-reference.md",
    "issues": ROOT / "docs/known-issues.md",
    "keymap": ROOT / "docs/generated/ide-keymap.md",
}


class DocsGateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise DocsGateError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def inline_names(text: str) -> set[str]:
    result: set[str] = set()
    token = re.compile(
        r"(?:[+*/<=>-]+|[%!?$&A-Za-z][%*+/<=>!?$&A-Za-z0-9._:-]*)")
    for span in re.findall(r"`([^`\n]+)`", text):
        result.update(value.lower() for value in token.findall(span))
    return result


def tier1_names() -> list[str]:
    names = re.findall(r"^\(defun\s+([^\s()]+)",
                       TIER1.read_text(encoding="utf-8"), re.M)
    return [name for name in names if not name.startswith("%")]


def derive_facts() -> dict[str, Any]:
    metadata = load(METADATA)
    projection = load(MEDIUM_RECEIPT)
    MEDIUM.validate(projection)
    errors = load(ERRORS)["codes"]
    arities = [row["arity"]["status"] for row in metadata["records"]]
    device = load(DEVICE)
    d5 = device["rows"][3]["D5"]["free"]
    counters = device["rows"][1]["captures"]["counter_values"]
    examples = sorted((ROOT / "examples/ship").glob("*/project.l65p"))
    keymap = load(KEYMAP)
    tier1 = tier1_names()
    require(len(errors) == 63
            and sum(row["presentation"] == "active-text" for row in errors) == 44
            and arities.count("exact-code-object") == 103
            and arities.count("unresolved") == 36
            and len(metadata["records"]) == 139
            and len(examples) == 5 and len(keymap["bindings"]) == 41
            and d5 == {"symbol_slots": 107, "namepool_bytes": 1467}
            and counters == {"raw": 138, "seen": 138,
                             "stored": 138, "taken": 138}
            and len(tier1) == 21,
            "derived bundled-document number authority drift")
    return {
        "error_codes": {"stable": 63, "active_text": 44},
        "arity": {"exact": 103, "unresolved": 36, "records": 139},
        "ship_examples": {"count": 5,
            "projects": [path.parent.name for path in examples]},
        "keymap_bindings": 41,
        "D5_free": d5,
        "capture_counters": counters,
        "tier1_changed_public_functions": tier1,
        "medium_projection": projection["counts"],
    }


def historical_version_context(texts: dict[str, str]) -> list[dict[str, str]]:
    markers = (
        "histor", "since", "reuses", "unchanged", "remains", "acceptance",
        "published", "previous", "banner", "product bytes", "artifact",
        "supersedes", "older release", "no product behavior",
    )
    result = []
    for role, text in texts.items():
        for paragraph in re.split(r"\n\s*\n", text):
            if "2.0.0" not in paragraph:
                continue
            require(any(marker in paragraph.lower() for marker in markers),
                    f"unclassified 2.0.0 version context in bundled {role}")
            result.append({"document": role,
                           "context_sha256": hashlib.sha256(
                               paragraph.encode()).hexdigest()})
    return result


def named_absence_subjects(text: str) -> set[str]:
    result: set[str] = set()
    pattern = re.compile(
        r"`([^`]+)`(?:\s+(?:and|or)\s+`([^`]+)`)?\s+"
        r"(?:is|are)\s+(?:deliberately\s+)?not\s+"
        r"(?:available|part of|present|delivered|on\b)", re.I)
    for match in pattern.finditer(text):
        for group in match.groups():
            if group:
                result.update(inline_names(f"`{group}`"))
    return result


def absence_section_names(texts: dict[str, str], metadata_names: set[str]
                          ) -> set[str]:
    reference = texts["reference"]
    start = reference.index("### Names outside the 2.0.1 medium")
    end = reference.index("\n## List-domain errors", start)
    reference_bullets = "\n".join(
        line for line in reference[start:end].splitlines()
        if line.startswith("- ") or line.startswith("  `"))
    issues = texts["issues"]
    start = issues.index("| Package | Names it would publish |")
    end = issues.index("\n\n", start)
    return (inline_names(reference_bullets) | inline_names(issues[start:end])) \
        & metadata_names


def validate_texts(texts: dict[str, str], root_name: str,
                   facts: dict[str, Any]) -> dict[str, Any]:
    require(set(texts) == set(DOC_PATHS), "bundled document role drift")
    require(root_name == TOP, "bundle archive root/version drift")
    headings = {
        "release": "# lisp65 2.0.1 Release Notes",
        "guide": "# lisp65 2.0.1 User Guide",
        "reference": "**lisp65 2.0.1**",
        "issues": "lisp65 2.0.1",
        "keymap": "bundled with lisp65 2.0.1",
    }
    for role, marker in headings.items():
        require(marker in texts[role], f"bundled {role} version drift")
    require(f"`{TOP}`" in texts["guide"],
            "guide extraction directory differs from archive root")
    contexts = historical_version_context(texts)

    metadata = load(METADATA)
    metadata_names = {row["name"] for row in metadata["records"]}
    documented = inline_names(texts["guide"] + "\n" + texts["reference"])
    missing = sorted(metadata_names - documented)
    require(not missing, f"public metadata names undocumented: {missing}")
    projection = load(MEDIUM_RECEIPT)
    outside = set(projection["outside_medium"])
    section_names = absence_section_names(texts, metadata_names)
    require(section_names == outside,
            f"medium absence list differs from projection: "
            f"missing={sorted(outside-section_names)} "
            f"extra={sorted(section_names-outside)}")
    direct_absence = set().union(*(
        named_absence_subjects(text) for text in texts.values())) & metadata_names
    require(not (direct_absence - outside),
            f"delivered metadata name described as absent: "
            f"{sorted(direct_absence-outside)}")

    guide, release = texts["guide"], texts["release"]
    checks = {
        "error_codes": "maps 63 stable error codes" in guide
            and "44 codes reachable" in guide,
        "arity": "exact arity for 103 of its 139 entries; 36" in guide,
        "examples": "The five supplied examples" in guide,
        "keymap": "It contains 41 bindings" in guide,
        "D5": "107 free symbol slots and 1,467 free name bytes" in guide
            and "107 free\nsymbol slots and 1,467 free name bytes" in release,
        "capture": "raw = seen = stored = taken = 138" in guide
            and "raw = seen = stored = taken = 138" in release,
        "tier1": "actual twenty-one public functions" in release,
    }
    require(all(checks.values()),
            f"derived bundled-document number pin drift: "
            f"{[name for name, ok in checks.items() if not ok]}")
    return {
        "version": VERSION, "archive_root": TOP,
        "documents": len(texts), "metadata_names": len(metadata_names),
        "documented_names": len(metadata_names & documented),
        "outside_medium_names": sorted(outside),
        "historical_version_contexts": contexts,
        "number_pins": facts, "checks": checks,
    }


def source_texts() -> dict[str, str]:
    return {role: path.read_text(encoding="utf-8")
            for role, path in SOURCE_DOCS.items()}


def validate_bundle(root: Path) -> dict[str, Any]:
    require(root.is_dir() and not root.is_symlink(), f"bundle root absent: {root}")
    texts = {}
    bindings = {}
    for role, relative in DOC_PATHS.items():
        path = root / relative
        require(path.is_file() and not path.is_symlink(),
                f"bundled document absent: {relative}")
        texts[role] = path.read_text(encoding="utf-8")
        raw = path.read_bytes()
        bindings[role] = {"path": relative, "bytes": len(raw),
                          "sha256": hashlib.sha256(raw).hexdigest()}
    result = validate_texts(texts, root.name, derive_facts())
    result["bindings"] = bindings
    result["authorities"] = [bind(path) for path in
        (METADATA, MEDIUM_RECEIPT, ERRORS, KEYMAP, TIER1, DEVICE)]
    return result


def selftest() -> list[str]:
    facts = derive_facts()
    base = source_texts()
    require(validate_texts(base, TOP, facts)["documented_names"] == 139,
            "source document fixture is not green")
    cases: dict[str, Callable[[dict[str, str]], None]] = {
        "stale-release-version": lambda value: value.update(
            guide=value["guide"].replace("# lisp65 2.0.1 User Guide",
                                          "# lisp65 2.0.0 User Guide")),
        "wrong-extraction-root": lambda value: value.update(
            guide=value["guide"].replace("`lisp65-2.0.1`", "`lisp65-2.0.0`")),
        "metadata-name-undocumented": lambda value: value.update(
            reference=value["reference"].replace("`runtime-main`", "runtime-main")),
        "delivered-name-called-absent": lambda value: value.update(
            issues=value["issues"].replace(
                "| `buffer` |", "| `car` | `car` |\n| `buffer` |", 1)),
        "error-count-drift": lambda value: value.update(
            guide=value["guide"].replace("maps 63 stable", "maps 62 stable")),
        "arity-count-drift": lambda value: value.update(
            guide=value["guide"].replace("exact arity for 103", "exact arity for 102")),
        "keymap-count-drift": lambda value: value.update(
            guide=value["guide"].replace("contains 41 bindings", "contains 40 bindings")),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(base); mutate(trial)
        try:
            validate_texts(trial, TOP, facts)
        except DocsGateError:
            rejected.append(name)
    wrong_root = deepcopy(base)
    try:
        validate_texts(wrong_root, "lisp65-2.0.0", facts)
    except DocsGateError:
        rejected.append("bundle-root-drift")
    require(rejected == [*cases, "bundle-root-drift"],
            f"bundle docs mutation survived: {rejected}")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("source-check", "check", "selftest"))
    parser.add_argument("--bundle-root", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    if args.action == "selftest":
        result = validate_texts(source_texts(), TOP, derive_facts())
        mutations = selftest()
    elif args.action == "source-check":
        result = validate_texts(source_texts(), TOP, derive_facts())
        mutations = []
    else:
        require(args.bundle_root is not None, "--bundle-root is required")
        result = validate_bundle(args.bundle_root.resolve())
        mutations = []
    if args.receipt:
        receipt = {"format": "lisp65-v201-bundled-docs-halt-b-v1",
            "status": "PASS: BUNDLED DOCUMENTS MATCH RELEASE AND AUTHORITIES",
            "result": result, "mutations_rejected": len(selftest())}
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_bytes(canonical(receipt))
    print("v2.0.1 bundled docs: PASS "
          f"documents={result['documents']} names={result['documented_names']} "
          f"outside={len(result['outside_medium_names'])} "
          f"mutations={len(mutations)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (DocsGateError, OSError, KeyError, ValueError,
            json.JSONDecodeError) as error:
        print(f"v2.0.1 bundled docs: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
