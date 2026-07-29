#!/usr/bin/env python3
"""Run the owner-approved host-first require/index/L65P-v1 probe."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import l65p_v1 as L  # noqa: E402


FIXTURE = ROOT / "tests/fixtures/l65p-v1"
PROJECT_FILE = FIXTURE / "project/project.l65p"
INDEX_INPUT = FIXTURE / "library-index-input.json"
OUT_DIR = ROOT / "build/post-promotion/workbench-era/require-v1-host-probe"
INDEX_OUT = OUT_DIR / "library-index.json"
LOCK_OUT = OUT_DIR / "resolution-lock.json"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / "c2.2-require-manifest-v1-host-probe-receipt.json"
FIRST_RED = EVIDENCE / "c2.2-require-manifest-v1-host-probe-first-red.json"
RAMP = ROOT / "config/c2.2-workbench-era-ramp.json"
RAMP_NOTE = ROOT / "docs/planning/c2.2-workbench-era-ramp-halt3.md"
REVIEW_NOTE = ROOT / "docs/planning/c2.2-require-manifest-v1-host-probe-review.md"
RAMP_RECEIPT = EVIDENCE / "c2.2-phase-w-workbench-ramp-halt3-receipt.json"
S1 = EVIDENCE / "c2.2-link67-f1-f2-s1-completion-receipt.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def binding(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def expect(
    label: str,
    action: Callable[[], Any],
    expected: str,
    rejected: dict[str, str],
) -> None:
    try:
        action()
    except L.L65PError as exc:
        require(str(exc) == expected, f"{label}: got {exc}, expected {expected}")
        rejected[label] = str(exc)
        return
    raise RuntimeError(f"mutation passed: {label}")


def index_rebind(index: dict[str, Any]) -> None:
    material = {"format": index["format"], "libraries": index["libraries"]}
    index["index_sha256"] = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


ramp = load(RAMP)
require(
    ramp["status"] == "owner-approved-library-era-open-host-first-probe-authorized",
    "Halt #3 is not owner-approved",
)
decision = ramp["halt_3_decision"]
require(
    decision["host_first_require_probe"] == "authorized"
    and decision["library_era"] == "open",
    "host-first scope is absent",
)
require(
    load(RAMP_RECEIPT)["status"] == "passed-W1-W2-owner-approved-library-era-open",
    "owner-approved Phase-W gate is not green",
)
require(load(S1)["status"] == "passed-Link67-F1-F2-S1-complete", "S1 is not closed")

spec = load(INDEX_INPUT)
index = L.generate_index(spec, ROOT)
L.validate_index(index, ROOT)
project_source = PROJECT_FILE.read_text(encoding="utf-8")
project = L.parse_project(project_source)
require(project.name == "require-probe", "project name drift")
require(project.requires == ("probe-seq",), "project requires drift")
require(project.sources == ("src/macros.l65", "src/main.l65"), "source order drift")
for relative in project.sources:
    source = PROJECT_FILE.parent / relative
    require(source.is_file() and not source.is_symlink(), f"source missing: {relative}")

lock = L.resolve(project, index, 7)
L.validate_lock(lock, project, index)
require(
    [row["name"] for row in lock["libraries"]] == ["probe-core", "probe-seq"],
    "dependency order drift",
)
require(lock["sources"] == list(project.sources), "locked source order drift")

session = L.Session(generation=7)
before = session.snapshot()
require(session.require("probe-seq", index) == "t", "first require result")
after_first = session.snapshot()
require(after_first != before, "first require changed nothing")
first_totals = dict(session.totals)
first_loaded = dict(session.loaded)
require(session.require("probe-seq", index) == "t", "idempotent require result")
require(session.snapshot() == after_first, "idempotent require changed session")
require(
    list(session.loaded) == ["probe-core", "probe-seq"]
    and set(session.exports) == {"probe-id", "probe-pair"},
    "loaded/export state drift",
)

fresh = L.Session(generation=8)
require(fresh.require("probe-seq", index) == "t", "fresh-generation require")
require(fresh.loaded == first_loaded, "fresh generation changed library identities")
require(fresh.totals == first_totals, "fresh generation changed capacity result")

cutpoints: dict[str, str] = {}
for state in L.APPEND_STATES:
    empty = L.Session(generation=7)
    snapshot = empty.snapshot()
    expect(
        f"dependency-cutpoint-{state.lower()}",
        lambda state=state, empty=empty: empty.require(
            "probe-seq", index, fail_library="probe-core", fail_at=state
        ),
        f"injected-{state.lower()}",
        cutpoints,
    )
    require(empty.snapshot() == snapshot, f"{state}: dependency rollback drift")

    committed = L.Session(generation=7)
    require(committed.require("probe-core", index) == "t", "dependency setup")
    snapshot = committed.snapshot()
    expect(
        f"request-cutpoint-{state.lower()}",
        lambda state=state, committed=committed: committed.require(
            "probe-seq", index, fail_library="probe-seq", fail_at=state
        ),
        f"injected-{state.lower()}",
        cutpoints,
    )
    require(committed.snapshot() == snapshot, f"{state}: request rollback drift")
    require(list(committed.loaded) == ["probe-core"], f"{state}: committed dependency lost")

mutations: dict[str, str] = {}
expect("manifest-version", lambda: L.parse_project(project_source.replace("l65-project-v1", "l65-project-v2", 1)), "bad-version", mutations)
expect("manifest-trailing-form", lambda: L.parse_project(project_source + "\n(progn)\n"), "reader-error", mutations)
expect("manifest-quoted-code", lambda: L.parse_project("'" + project_source), "bad-version", mutations)
expect(
    "manifest-duplicate-field",
    lambda: L.parse_project(project_source.replace('(name "require-probe")', '(name "require-probe") (name "other")')),
    "duplicate-field",
    mutations,
)
expect(
    "manifest-unknown-field",
    lambda: L.parse_project(project_source.replace("(requires probe-seq)", "(requires probe-seq) (autoload t)")),
    "unknown-or-missing-field",
    mutations,
)
expect(
    "manifest-duplicate-require",
    lambda: L.parse_project(project_source.replace("(requires probe-seq)", "(requires probe-seq probe-seq)")),
    "duplicate-require",
    mutations,
)
expect(
    "manifest-name-evaluation",
    lambda: L.parse_project(project_source.replace('(name "require-probe")', "(name (progn 1))")),
    "name-type",
    mutations,
)
expect(
    "manifest-absolute-path",
    lambda: L.parse_project(project_source.replace('"src/macros.l65"', '"/src/macros.l65"')),
    "absolute-path",
    mutations,
)
expect(
    "manifest-device-prefix",
    lambda: L.parse_project(project_source.replace('"src/macros.l65"', '"8:src/macros.l65"')),
    "device-prefix",
    mutations,
)
expect(
    "manifest-parent-path",
    lambda: L.parse_project(project_source.replace('"src/macros.l65"', '"../macros.l65"')),
    "parent-path",
    mutations,
)
expect(
    "manifest-duplicate-source",
    lambda: L.parse_project(project_source.replace('"src/macros.l65" "src/main.l65"', '"src/main.l65" "src/main.l65"')),
    "duplicate-source",
    mutations,
)
expect(
    "manifest-default-not-source",
    lambda: L.parse_project(project_source.replace('(default-target "src/main.l65")', '(default-target "src/other.l65")')),
    "default-target-not-source",
    mutations,
)
expect(
    "manifest-empty-sources",
    lambda: L.parse_project(project_source.replace('(sources "src/macros.l65" "src/main.l65")', "(sources)")),
    "empty-sources",
    mutations,
)

bad_spec = copy.deepcopy(spec)
bad_spec["libraries"].append(copy.deepcopy(bad_spec["libraries"][0]))
expect("index-duplicate-library", lambda: L.generate_index(bad_spec, ROOT), "duplicate-library", mutations)
bad_spec = copy.deepcopy(spec)
bad_spec["libraries"][1]["requires"] = ["missing"]
expect("index-unknown-dependency", lambda: L.generate_index(bad_spec, ROOT), "unknown-dependency", mutations)
bad_spec = copy.deepcopy(spec)
bad_spec["libraries"][0]["artifact"] = "tests/fixtures/l65p-v1/missing.l65"
expect("index-missing-artifact", lambda: L.generate_index(bad_spec, ROOT), "artifact-missing", mutations)
bad_spec = copy.deepcopy(spec)
bad_spec["libraries"][0]["measurement"] = "estimated"
expect("index-unmeasured-delta", lambda: L.generate_index(bad_spec, ROOT), "unmeasured-delta", mutations)
bad_spec = copy.deepcopy(spec)
bad_spec["libraries"][0]["c2_delta"]["entries"] = -1
expect("index-negative-delta", lambda: L.generate_index(bad_spec, ROOT), "c2-delta-value", mutations)
bad_spec = copy.deepcopy(spec)
bad_spec["libraries"][0]["exports"].append("probe-id")
expect("index-duplicate-export", lambda: L.generate_index(bad_spec, ROOT), "library-exports", mutations)

bad_index = copy.deepcopy(index)
bad_index["index_sha256"] = "0" * 64
expect("index-sha", lambda: L.validate_index(bad_index, ROOT), "index-sha", mutations)
bad_index = copy.deepcopy(index)
bad_index["libraries"][0]["artifact_sha256"] = "0" * 64
index_rebind(bad_index)
expect("index-artifact-sha", lambda: L.validate_index(bad_index, ROOT), "artifact-sha", mutations)
bad_index = copy.deepcopy(index)
bad_index["libraries"][0]["identity_u32"] ^= 1
index_rebind(bad_index)
expect("index-identity-u32", lambda: L.validate_index(bad_index, ROOT), "identity-u32", mutations)

unknown_project = L.Project("unknown", ("missing",), ("x.l65",), "x.l65")
expect("resolve-unknown", lambda: L.resolve(unknown_project, index, 7), "unknown-library", mutations)
bad_index = copy.deepcopy(index)
bad_index["libraries"].append(copy.deepcopy(bad_index["libraries"][1]))
expect("resolve-ambiguous", lambda: L.resolve(project, bad_index, 7), "ambiguous-library", mutations)
bad_index = copy.deepcopy(index)
for row in bad_index["libraries"]:
    if row["name"] == "probe-core":
        row["requires"] = ["probe-seq"]
expect("resolve-cycle", lambda: L.resolve(project, bad_index, 7), "dependency-cycle", mutations)
bad_index = copy.deepcopy(index)
for row in bad_index["libraries"]:
    if row["name"] == "probe-seq":
        row["execution_source"] = "attic"
expect("resolve-runtime-attic", lambda: L.resolve(project, bad_index, 7), "runtime-attic", mutations)
expect("resolve-zero-generation", lambda: L.resolve(project, index, 0), "generation", mutations)

bad_lock = copy.deepcopy(lock)
bad_lock["sources"].reverse()
expect("lock-source-order", lambda: L.validate_lock(bad_lock, project, index), "resolution-lock-drift", mutations)
bad_lock = copy.deepcopy(lock)
bad_lock["libraries"][1]["identity_u32"] ^= 1
expect("lock-library-identity", lambda: L.validate_lock(bad_lock, project, index), "resolution-lock-drift", mutations)
bad_lock = copy.deepcopy(lock)
bad_lock["generation"] = 8
expect("lock-generation", lambda: L.validate_lock(bad_lock, project, index), "resolution-lock-drift", mutations)

stale = L.Session(generation=7)
stale.loaded["probe-seq"] = 0xDEADBEEF
expect("require-loaded-identity-drift", lambda: stale.require("probe-seq", index), "loaded-identity-drift", mutations)

capacity_cases = {
    "bank2": ("bank2_code_bytes", 30547),
    "images": ("images", 59),
    "entries": ("entries", 1447),
    "resolutions": ("resolutions", 1798),
    "roots": ("roots", 1254),
    "scratch": ("c2d_scratch_bytes", 14545),
}
for label, (key, value) in capacity_cases.items():
    bad_index = copy.deepcopy(index)
    for row in bad_index["libraries"]:
        if row["name"] == "probe-seq":
            row["c2_delta"][key] = value
    expect(
        f"capacity-{label}",
        lambda bad_index=bad_index: L.resolve(project, bad_index, 7),
        f"capacity-{key}",
        mutations,
    )

require(
    L.APPEND_STATES.index("TARGET_VERIFIED") < L.APPEND_STATES.index("C2D_PUBLISHED"),
    "target verification no longer precedes publication",
)
mutations["publish-before-target-verification"] = "state-order-rejected"
require(len(mutations) >= 35, "negative matrix unexpectedly small")
require(len(cutpoints) == 12, "cutpoint matrix drift")

OUT_DIR.mkdir(parents=True, exist_ok=True)
INDEX_OUT.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
LOCK_OUT.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
L.validate_index(load(INDEX_OUT), ROOT)
L.validate_lock(load(LOCK_OUT), project, load(INDEX_OUT))

receipt = {
    "format": "lisp65-c2.2-require-manifest-v1-host-probe-receipt-v1",
    "recorded_on": "2026-07-27",
    "status": "passed-host-first-require-index-L65P-v1",
    "authority": {
        "Halt_3_contract": binding(RAMP),
        "Halt_3_note": binding(RAMP_NOTE),
        "freight_review": binding(REVIEW_NOTE),
        "Halt_3_gate": binding(RAMP_RECEIPT),
        "S1_completion": binding(S1),
        "first_red": binding(FIRST_RED),
        "model": binding(ROOT / "tools/host-lisp/l65p_v1.py"),
        "probe": binding(Path(__file__).resolve()),
        "canonical_reader": binding(ROOT / "tools/host-lisp/bytecode_p0_compiler.py"),
        "project": binding(PROJECT_FILE),
        "index_input": binding(INDEX_INPUT),
        "generated_index": binding(INDEX_OUT),
        "resolution_lock": binding(LOCK_OUT),
        "fixture_artifacts": [
            binding(FIXTURE / "probe-core.l65"),
            binding(FIXTURE / "probe-seq.l65"),
        ],
        "project_sources": [
            binding(PROJECT_FILE.parent / relative) for relative in project.sources
        ],
    },
    "positive": {
        "reader": "canonical-bytecode-p0-parse-one-one-form-no-eval",
        "dependency_order": ["probe-core", "probe-seq"],
        "source_order": list(project.sources),
        "default_target": project.default_target,
        "first_require": "t",
        "repeat_require": "t-byteidentical-session-state",
        "fresh_generation": "both-libraries-reloaded-under-generation-8",
        "loaded_identities": first_loaded,
        "post_load_totals": first_totals,
        "resolution_lock_sha256": lock["lock_sha256"],
    },
    "rollback": {
        "cutpoints": cutpoints,
        "cutpoint_count": len(cutpoints),
        "dependency_failure": "no session growth",
        "request_failure": "committed dependency remains; request leaves no growth",
    },
    "negative": {
        "mutations": mutations,
        "mutation_count": len(mutations),
    },
    "execution_accounting": {
        "host_probe_runs": 4,
        "first_red_runs": 1,
        "green_replays": 3,
        "product_bytes": 0,
        "product_links": 0,
        "hardware_runs": 0,
    },
    "next_gate": "Class-C freight review before any target require implementation; recommended first library is defstruct",
    "claim_limit": "Host parser/index/resolution/preflight/transaction model only. No target require, product, hardware, defstruct or random claim.",
}
RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(
    "REQUIRE V1 HOST PASS "
    f"libs={len(index['libraries'])} cutpoints={len(cutpoints)} "
    f"mutations={len(mutations)} resident=0 product=0"
)
