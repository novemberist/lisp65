#!/usr/bin/env python3
"""Seal the v1.6-v1.9 planning roots without rewriting their evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
INDEX = Path("config/document-index.json")
V16 = Path("docs/planning/v1.6.0-freight-work-plan.md")
V17 = Path("docs/planning/v1.7.0-pre-plan.md")
V18 = Path("docs/planning/v1.8.0-cycle-decisions.md")
V19 = Path("docs/planning/v1.9.0-pre-plan.md")
BLOCK25 = Path("docs/planning/2.5-post-v1.9-housekeeping-work-plan.md")
BLOCK25_REPORT = Path("docs/planning/2.5-post-v1.9-housekeeping-report.md")
RUNTIME_REPORT = Path("docs/planning/2.5-check-source-runtime-report.md")
HYGIENE_REPORT = Path("docs/planning/2.5-plan-document-hygiene-report.md")

SOURCE_COMMIT = "bb30c709f7f710f8f665c1828fa424d6dfb48c64"
TAIL_MARKER = b"## v1.8 opening shape agreed \xe2\x80\x94 2026-08-28\n"
TAIL_SHA256 = "9788e175bb91d96364a7a6d0504ef89418bf72e3d488718fe29eaaa18b0544d3"
BEGIN = b"<!-- BEGIN VERBATIM V1.7 TAIL -->\n"
END = b"<!-- END VERBATIM V1.7 TAIL -->\n"

V17_OLD_STATUS = b"Status: **inventory only \xe2\x80\x94 not commissioned**"
V17_NEW_STATUS = b"Status: **historical \xe2\x80\x94 sealed after v1.7.0 publication**"
V19_STATUS = b"Status: **historical \xe2\x80\x94 v1.9.0 published and post-release verified**\n\n"


class HygieneError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_tail(root: Path = ROOT) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{SOURCE_COMMIT}:{V17.as_posix()}"],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
    )
    try:
        offset = result.stdout.index(TAIL_MARKER)
    except ValueError as exc:
        raise HygieneError("source-era v1.8 marker is absent") from exc
    tail = result.stdout[offset:]
    if sha256(tail) != TAIL_SHA256:
        raise HygieneError("source-era v1.8 tail hash drift")
    return tail


def extract_verbatim(document: bytes) -> bytes:
    if document.count(BEGIN) != 1 or document.count(END) != 1:
        raise HygieneError("v1.8 verbatim boundary count drift")
    start = document.index(BEGIN) + len(BEGIN)
    stop = document.index(END, start)
    return document[start:stop]


def index_rows(document: dict[str, object]) -> dict[str, dict[str, object]]:
    rows = document.get("documents")
    if not isinstance(rows, list):
        raise HygieneError("document index has no document rows")
    result: dict[str, dict[str, object]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise HygieneError("malformed document-index row")
        path = str(row["path"])
        if path in result:
            raise HygieneError(f"duplicate document-index row: {path}")
        result[path] = row
    return result


def tracked_planning(root: Path = ROOT) -> list[str]:
    output = subprocess.check_output(
        ["git", "ls-files", "docs/planning/*.md"], cwd=root, text=True
    )
    return sorted(line for line in output.splitlines() if line)


def validate_state(
    *, v16: bytes, v17: bytes, v18: bytes, v19: bytes,
    index: dict[str, object], planning_paths: list[str], expected_tail: bytes,
) -> list[str]:
    errors: list[str] = []
    if b"## SEALED \xe2\x80\x94 2026-08-25" not in v16:
        errors.append("v1.6 terminal seal absent")
    if V17_NEW_STATUS not in v17:
        errors.append("v1.7 historical seal absent")
    if TAIL_MARKER in v17:
        errors.append("v1.8 tail remains duplicated in v1.7")
    if V18.as_posix().encode() not in v17:
        errors.append("v1.7 relocation does not name v1.8 document")
    try:
        moved = extract_verbatim(v18)
    except HygieneError as exc:
        errors.append(str(exc))
    else:
        if moved != expected_tail:
            errors.append("relocated v1.8 bytes differ from source era")
    if V19_STATUS not in v19:
        errors.append("v1.9 historical seal absent")
    if V18.as_posix().encode() not in v19:
        errors.append("v1.9 does not link its v1.8 provenance")

    try:
        rows = index_rows(index)
    except HygieneError as exc:
        return errors + [str(exc)]
    required = {
        V16.as_posix(): ("historical", V17.as_posix()),
        V17.as_posix(): ("historical", V18.as_posix()),
        V18.as_posix(): ("historical", V19.as_posix()),
        V19.as_posix(): ("historical", BLOCK25.as_posix()),
        BLOCK25.as_posix(): ("historical", BLOCK25_REPORT.as_posix()),
        BLOCK25_REPORT.as_posix(): ("current", None),
        RUNTIME_REPORT.as_posix(): ("current", None),
        HYGIENE_REPORT.as_posix(): ("current", None),
    }
    for path, (classification, successor) in required.items():
        row = rows.get(path)
        if row is None:
            errors.append(f"missing document-index row: {path}")
            continue
        if row.get("class") != classification:
            errors.append(f"wrong document class: {path}")
        if successor is not None and row.get("superseded_by") != successor:
            errors.append(f"wrong successor: {path}")
        if successor is None and "superseded_by" in row:
            errors.append(f"unexpected successor: {path}")
    missing = sorted(set(planning_paths) - set(rows))
    extra = sorted(set(rows).intersection({p for p in rows if p.startswith("docs/planning/")}) - set(planning_paths))
    if missing:
        errors.append("unclassified planning documents: " + ", ".join(missing))
    if extra:
        errors.append("indexed planning documents absent from tracked tree: " + ", ".join(extra))
    return errors


def add_or_replace_row(index: dict[str, object], row: dict[str, object]) -> None:
    rows = index.get("documents")
    if not isinstance(rows, list):
        raise HygieneError("document index has no document rows")
    path = row["path"]
    rows[:] = [item for item in rows if item.get("path") != path]
    rows.append(row)
    rows.sort(key=lambda item: str(item["path"]))


def apply(root: Path = ROOT) -> None:
    tail = source_tail(root)
    v17_path = root / V17
    v18_path = root / V18
    v19_path = root / V19
    if v18_path.exists():
        raise HygieneError("v1.8 cycle document already exists")
    v17 = v17_path.read_bytes()
    if v17.count(TAIL_MARKER) != 1 or V17_OLD_STATUS not in v17:
        raise HygieneError("live v1.7 source is not the expected pre-move world")
    prefix = v17[:v17.index(TAIL_MARKER)].rstrip() + b"\n\n"
    prefix = prefix.replace(V17_OLD_STATUS, V17_NEW_STATUS, 1)
    relocation = (
        b"## Post-v1.7 cycle decisions relocated \xe2\x80\x94 2026-08-30\n\n"
        b"The exact v1.8 cycle tail formerly appended here is preserved in `"
        + V18.as_posix().encode()
        + b"`. Its source authority is commit `" + SOURCE_COMMIT.encode()
        + b"`; the moved bytes have SHA-256 `" + TAIL_SHA256.encode()
        + b"`. The live v1.9 cycle record is `" + V19.as_posix().encode()
        + b"`. No historical decision text was rewritten by this relocation.\n"
    )
    v17_path.write_bytes(prefix + relocation)

    wrapper = (
        b"# v1.8.0 cycle decisions\n\n"
        b"Status: **historical \xe2\x80\x94 sealed after v1.8.0 publication**\n\n"
        b"This file preserves byte-for-byte the v1.8 cycle tail that had been\n"
        b"appended to the v1.7 pre-plan. Source commit: `" + SOURCE_COMMIT.encode()
        + b"`; verbatim payload SHA-256: `" + TAIL_SHA256.encode() + b"`.\n\n"
        + BEGIN + tail + END
    )
    v18_path.write_bytes(wrapper)

    v19 = v19_path.read_bytes()
    if V19_STATUS not in v19:
        heading = b"# v1.9.0 pre-plan\n\n"
        if not v19.startswith(heading):
            raise HygieneError("unexpected v1.9 heading")
        provenance = (
            V19_STATUS
            + b"The predecessor-cycle decisions and the v1.9 register that opened this\n"
            + b"cycle are preserved in `" + V18.as_posix().encode() + b"`.\n\n"
        )
        v19_path.write_bytes(heading + provenance + v19[len(heading):])

    index_path = root / INDEX
    index = json.loads(index_path.read_text(encoding="utf-8"))
    for row in (
        {"path": V16.as_posix(), "class": "historical", "superseded_by": V17.as_posix()},
        {"path": V17.as_posix(), "class": "historical", "superseded_by": V18.as_posix()},
        {"path": V18.as_posix(), "class": "historical", "superseded_by": V19.as_posix()},
        {"path": V19.as_posix(), "class": "historical", "superseded_by": BLOCK25.as_posix()},
        {"path": BLOCK25.as_posix(), "class": "historical", "superseded_by": BLOCK25_REPORT.as_posix()},
        {"path": BLOCK25_REPORT.as_posix(), "class": "current"},
        {"path": RUNTIME_REPORT.as_posix(), "class": "current"},
        {"path": HYGIENE_REPORT.as_posix(), "class": "current"},
    ):
        add_or_replace_row(index, row)
    index_path.write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
    print(f"plan hygiene: APPLIED tail_bytes={len(tail)} tail_sha256={sha256(tail)}")


def check(root: Path = ROOT) -> None:
    expected = source_tail(root)
    index = json.loads((root / INDEX).read_text(encoding="utf-8"))
    paths = tracked_planning(root)
    # During a pre-commit check, newly created planning documents are not yet
    # in git ls-files. Include existing index-owned files in the live census.
    rows = index_rows(index)
    paths = sorted(set(paths) | {
        path for path in rows
        if path.startswith("docs/planning/") and (root / path).is_file()
    })
    errors = validate_state(
        v16=(root / V16).read_bytes(),
        v17=(root / V17).read_bytes(),
        v18=(root / V18).read_bytes(),
        v19=(root / V19).read_bytes(),
        index=index,
        planning_paths=paths,
        expected_tail=expected,
    )
    if errors:
        raise HygieneError("; ".join(errors))
    print(
        f"plan hygiene: CHECK PASS planning_documents={len(paths)} "
        f"verbatim_bytes={len(expected)} sha256={sha256(expected)}"
    )


def selftest() -> None:
    tail = TAIL_MARKER + b"sealed body\n"
    v16 = b"# v1.6\n## SEALED \xe2\x80\x94 2026-08-25\n"
    v17 = V17_NEW_STATUS + b"\n" + V18.as_posix().encode()
    v18 = BEGIN + tail + END
    v19 = V19_STATUS + V18.as_posix().encode()
    paths = [
        V16.as_posix(), V17.as_posix(), V18.as_posix(), V19.as_posix(),
        BLOCK25.as_posix(), BLOCK25_REPORT.as_posix(), RUNTIME_REPORT.as_posix(),
        HYGIENE_REPORT.as_posix(),
    ]
    rows = [
        {"path": V16.as_posix(), "class": "historical", "superseded_by": V17.as_posix()},
        {"path": V17.as_posix(), "class": "historical", "superseded_by": V18.as_posix()},
        {"path": V18.as_posix(), "class": "historical", "superseded_by": V19.as_posix()},
        {"path": V19.as_posix(), "class": "historical", "superseded_by": BLOCK25.as_posix()},
        {"path": BLOCK25.as_posix(), "class": "historical", "superseded_by": BLOCK25_REPORT.as_posix()},
        {"path": BLOCK25_REPORT.as_posix(), "class": "current"},
        {"path": RUNTIME_REPORT.as_posix(), "class": "current"},
        {"path": HYGIENE_REPORT.as_posix(), "class": "current"},
    ]
    base = {"documents": rows}
    arguments = dict(v16=v16, v17=v17, v18=v18, v19=v19,
                     index=base, planning_paths=paths, expected_tail=tail)
    if validate_state(**arguments):
        raise HygieneError("valid synthetic hygiene world was rejected")
    mutations = [
        {"v18": BEGIN + tail + b"drift\n" + END},
        {"v17": v17 + b"\n" + TAIL_MARKER},
        {"v19": V19_STATUS},
        {"v16": b"# unsealed\n"},
        {"planning_paths": paths + ["docs/planning/unclassified.md"]},
    ]
    wrong = json.loads(json.dumps(base))
    for row in wrong["documents"]:
        if row["path"] == V17.as_posix():
            row["superseded_by"] = V19.as_posix()
    mutations.append({"index": wrong})
    for mutation in mutations:
        changed = dict(arguments)
        changed.update(mutation)
        if not validate_state(**changed):
            raise HygieneError(f"mutation survived: {sorted(mutation)}")
    print(f"plan hygiene: SELFTEST PASS mutations={len(mutations)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("apply", "check", "selftest"))
    args = parser.parse_args()
    try:
        if args.command == "apply":
            apply()
        elif args.command == "check":
            check()
        else:
            selftest()
    except (HygieneError, OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"plan hygiene: FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
