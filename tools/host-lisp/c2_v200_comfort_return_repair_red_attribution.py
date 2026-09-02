#!/usr/bin/env python3
"""Attribute the red v2.0 Comfort replacement contact without new media."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v17_comfort_phase1b_acceptance_media as V17  # noqa: E402
import c2_v200_comfort_return_materialization_repair as REPAIR  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
AUTHORITY = ROOT / "config/c2-v190-public-build-authority.json"
NAMING_AUDIT = ROOT / "docs/planning/2.5-public-naming-audit-report.md"
HALT_B = ROOT / "docs/planning/v1.9.0-halt-b-review.md"
RECEIPT = ARCH / (
    "c2.3-v2.0-comfort-return-repair-red-attribution-receipt.json")
REPORT = ROOT / (
    "docs/planning/v2.0.0-comfort-return-repair-red-attribution-report.md")
FORMAT = "lisp65-c2-v200-comfort-return-repair-red-attribution-v1"
STATUS = "PASS: REPLACEMENT RED ATTRIBUTED; COMFORT DESCOPED"
EVIDENCE_SEAL_COMMIT = "6b5760e06f9016a3da38b281f19390fbabd67a60"


class AttributionError(RuntimeError):
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
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def sealed_file(path: Path) -> bytes:
    return subprocess.run(
        ["git", "show", f"{EVIDENCE_SEAL_COMMIT}:"
         f"{path.relative_to(ROOT).as_posix()}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout


def write(path: Path, value: dict[str, Any] | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical(value) if isinstance(value, dict) else value
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(raw)
    temporary.replace(path)


def symbol_literals(entry: dict[str, Any]) -> list[str]:
    return [item["symbol"] for item in entry.get("literals", [])
            if isinstance(item, dict) and isinstance(item.get("symbol"), str)]


def product_entries() -> tuple[dict[str, dict[str, Any]], int]:
    index = load(REPAIR.STATIC_MANIFEST)
    entries: dict[str, dict[str, Any]] = {}
    count = 0
    for row in index["manifests"]:
        manifest = load(ROOT / row["path"])
        for entry in manifest["entries"]:
            # Later images lawfully replace an earlier directory binding.  The
            # final owner is therefore the last entry in product append order.
            entries[entry["name"]] = entry
            count += 1
    require(count == REPAIR.geometry()["entries"] == 760,
            "candidate static population drift")
    return entries, count


def ownership_world() -> dict[str, Any]:
    authority = load(AUTHORITY)
    support = load(REPAIR.SUPPORT.with_suffix(".manifest.json"))
    comfort = load(REPAIR.COMFORT_MANIFEST)
    entries, emitted_count = product_entries()
    resident_names = set(entries)
    support_names = set(support["functions"])
    overlap = sorted(resident_names & support_names)
    additions = sorted(support_names - resident_names)
    external = comfort["cost"]["dependency_gate"]["allowed_external_calls"]
    missing_external = sorted(set(external) - resident_names)
    resident_loop = entries["%read-line-loop"]
    support_loop = next(entry for entry in support["entries"]
                        if entry["name"] == "%read-line-loop")
    require(authority["editor_ownership"] == "resident-product-single-owner"
            and "v16core-duplicate" in authority["excluded_library_roles"]
            and authority["delivered_library_roles"] == []
            and overlap == ["%ide-line-net-depth", "%read-line-loop",
                "%rl-cut", "%rl-dispatch", "%rl-move", "%rl-put",
                "%rl-render", "%rl-screen-tail", "read-line"]
            and len(additions) == 19 and not missing_external
            and "%rl-poll" not in symbol_literals(resident_loop)
            and "%rl-poll" in symbol_literals(support_loop),
            "resident/external editor ownership derivation drift")
    return {
        "authority": bind(AUTHORITY),
        "editor_ownership": authority["editor_ownership"],
        "excluded_library_role": "v16core-duplicate",
        "static_entry_count": emitted_count,
        "final_static_directory_names": len(entries),
        "external_support_function_count": len(support_names),
        "overwritten_resident_owners": overlap,
        "overwritten_resident_owner_count": len(overlap),
        "new_external_objects": additions,
        "new_external_object_count": len(additions),
        "comfort_external_calls": external,
        "comfort_external_calls_missing_from_product": missing_external,
        "resident_read_line_loop": {
            "bytes": resident_loop["length"],
            "symbol_literals": symbol_literals(resident_loop),
            "consumes_rl_poll": False,
        },
        "external_read_line_loop": {
            "bytes": support_loop["length"],
            "symbol_literals": symbol_literals(support_loop),
            "consumes_rl_poll": True,
        },
        "historical_documents": {
            "naming_audit": bind(NAMING_AUDIT),
            "v1_9_halt_b": bind(HALT_B),
        },
    }


def comfort_only_world() -> dict[str, Any]:
    cases = load(REPAIR.COMFORT_SUITE)["cases"]
    with tempfile.TemporaryDirectory(
            prefix="c2-v200-comfort-only-", dir=ROOT / "build") as raw:
        host, static_entries = REPAIR.product_host(Path(raw))
        append = REPAIR.append_manifest(
            host, REPAIR.COMFORT_MANIFEST, "repl-comfort")
        observations = [REPAIR.execute_case(host, case, ordinal)
                        for ordinal, case in enumerate(cases)]
    require(static_entries == 760 and len(observations) == 9
            and append["before"] == {"images": 6, "entries": 760,
                "resolutions": 3020, "roots": 378, "code_bytes": 47469}
            and append["after"] == {"images": 7, "entries": 764,
                "resolutions": 3062, "roots": 386, "code_bytes": 48284},
            "product plus Comfort-only execution drift")

    spec = ("repl-comfort", "repl", "repl",
            REPAIR.COMFORT_MANIFEST, ())
    row, artifact = V17.LIBMEDIA.measured(
        spec, (1, 1), REPAIR.BASE.PRODUCT_ID)
    prior = load(REPAIR.RECEIPT)["library"]["artifacts"]["repl-comfort"]
    artifact_sha256 = hashlib.sha256(artifact).hexdigest()
    encoded = V17.LIBMEDIA.L65I.encode_index([row])
    decoded = V17.LIBMEDIA.L65I.decode_index(
        encoded, {"repl-comfort": artifact},
        artifact_build_id=REPAIR.BASE.PRODUCT_ID)
    contract = V17.LIBMEDIA.resolver_contract(decoded, "repl-comfort")
    require(row["dependencies"] == []
            and contract["actual_resolver_order"] == [0]
            and len(artifact) == prior["bytes"] == 1625
            and artifact_sha256 == prior["sha256"],
            "one-row Comfort projection drift")
    return {
        "status": "PASS: PRODUCT PLUS SEALED COMFORT, NO V16CORE",
        "static_entries": static_entries,
        "comfort_append": append,
        "cases": observations,
        "case_count": len(observations),
        "one_row_projection": {
            "artifact_bytes": len(artifact),
            "artifact_sha256": artifact_sha256,
            "prior_packed_artifact": prior,
            "index_bytes": len(encoded),
            "index_sha256": hashlib.sha256(encoded).hexdigest(),
            "dependencies": row["dependencies"],
            "resolver_order": contract["actual_resolver_order"],
            "claim": "host-only price; no medium was built or authorized",
        },
    }


def device_red() -> dict[str, Any]:
    repair = load(REPAIR.RECEIPT)
    session = load(REPAIR.SESSION_CONFIG)
    require(repair["status"] == REPAIR.STATUS
            and session["decision_table"]["daily-use-blocker"]
                == "repair contact red: bounded round exhausted; Comfort descopes",
            "replacement-contact authority drift")
    return {
        "contact": 2,
        "product_medium": repair["product"]["projected"],
        "library_medium": repair["library"]["D81"],
        "stimulus": "(require 'v16core) at the native prompt",
        "owner_observation": "*** wrong argument count repeated in a loop",
        "accepted_groups": [],
        "classification": "daily-use blocker in the bounded repair contact",
        "decision_table_result": "bounded round exhausted; Comfort descopes",
    }


def correction() -> dict[str, Any]:
    return {
        "superseded_receipt": bind(REPAIR.RECEIPT),
        "superseded_report": bind(REPAIR.REPORT),
        "preservation": "prior bytes remain sealed evidence of the failed repair",
        "false_claims": [
            {
                "old": "the first contact failed while requiring repl-comfort",
                "correct": ("the first required form was v16core; the loop began "
                            "before Comfort was loaded"),
            },
            {
                "old": "the r4 product contains none of those owners",
                "correct": "the r4 product contains nine resident editor owners",
            },
            {
                "old": "missing %rl-poll is a product materialization omission",
                "correct": ("the resident %read-line-loop does not consume %rl-poll; "
                            "the external replacement introduced that dependency"),
            },
            {
                "old": "product plus 28-object support plus Comfort is the actual world",
                "correct": ("that composition has duplicate editor ownership; its nine "
                            "overwrites violate the v1.9 product authority"),
            },
        ],
        "blind_spot": ("the repair gate executed post-append Comfort cases but did not "
                       "model the require transaction or reject duplicate owners"),
        "rule": ("library closure is derived against product plus media ownership; an "
                 "excluded resident duplicate may not be materialized as a dependency"),
    }


def validate(value: dict[str, Any]) -> None:
    require(value["format"] == FORMAT and value["status"] == STATUS
            and value["accounting"] == {"WPLTO_runs": 0, "product_links": 0,
                "new_media_builds": 0, "new_device_contacts": 0,
                "bounded_repair_rounds_consumed": 1}
            and value["ownership_world"]["editor_ownership"]
                == "resident-product-single-owner"
            and value["ownership_world"]["excluded_library_role"]
                == "v16core-duplicate"
            and value["ownership_world"]["overwritten_resident_owner_count"] == 9
            and value["ownership_world"]["new_external_object_count"] == 19
            and not value["ownership_world"]
                ["comfort_external_calls_missing_from_product"]
            and not value["ownership_world"]
                ["resident_read_line_loop"]["consumes_rl_poll"]
            and value["ownership_world"]
                ["external_read_line_loop"]["consumes_rl_poll"]
            and value["comfort_only_world"]["case_count"] == 9
            and value["comfort_only_world"]["one_row_projection"]
                ["dependencies"] == []
            and value["device_red"]["decision_table_result"]
                == "bounded round exhausted; Comfort descopes"
            and value["decision"]["comfort_v2_0"] == "DESCOPED"
            and value["decision"]["block_3_v2_0"] == "CLOSED"
            and not value["decision"]["third_medium_authorized"],
            "replacement-red attribution semantic wall red")


def report(value: dict[str, Any]) -> str:
    ownership = value["ownership_world"]
    return f"""# v2.0 Comfort replacement-red attribution

Status: **{value['status']}**

## Device result

The replacement contact failed on its first form, `(require 'v16core)`, with
repeating `*** wrong argument count`.  Comfort was never loaded and no
acceptance row passed.  This is the red branch of the pre-bound replacement
session; the single repair round is exhausted.

## Corrected mechanism

The replacement repaired the wrong world.  The v1.9 product authority names
the editor **resident-product-single-owner** and explicitly excludes
`v16core-duplicate`.  The final r4 static plane already contains
{ownership['overwritten_resident_owner_count']} of the 28 externally emitted objects.
Loading the replacement overwrites those nine resident owners and adds 19
objects from a different editor generation.

The sharp distinction is `%read-line-loop`: the resident 250-byte object does
not consume `%rl-poll`; the external 225-byte replacement does.  `%rl-poll`
was therefore not missing from the product.  The replacement introduced the
dependency while replacing the resident owner.

This corrects three claims in the prior repair report without rewriting its
sealed bytes.  That report and receipt remain evidence of the failed repair;
this successor owns their interpretation.

## Counterfactual host result

The exact 760-entry product plus sealed Comfort alone resolves every Comfort
external call from the resident product and passes all
{value['comfort_only_world']['case_count']} registered cases.  A one-row Comfort
index with no external-library dependency is representable and keeps the
Comfort artifact byte-identical.  This is host-only price evidence, not a third
medium or hardware authorization.

The former validator was green because it started after both append operations
and executed Comfort cases.  It neither modeled the failing `require`
transaction nor rejected duplicate product/library ownership.  Thus it proved
post-append behavior in an unauthorized world.

## Disposition

The bound table is applied literally: **Comfort is descoped from v2.0 and
Block 3 remains closed.**  No third medium, WPLTO, product link or device
contact is authorized.  The Comfort-only projection is preserved as the
starting evidence for a later explicitly opened cycle.

Permanent rule: *library closure is derived against product plus media
ownership; an excluded resident duplicate may not be materialized as a
dependency.*
"""


def derive() -> dict[str, Any]:
    value = {
        "format": FORMAT,
        "recorded_on": "2026-08-31",
        "status": STATUS,
        "device_red": device_red(),
        "ownership_world": ownership_world(),
        "comfort_only_world": comfort_only_world(),
        "correction": correction(),
        "decision": {
            "comfort_v2_0": "DESCOPED",
            "block_3_v2_0": "CLOSED",
            "third_medium_authorized": False,
            "later_starting_point": (
                "product plus sealed Comfort only; owner must reopen explicitly"),
        },
        "accounting": {"WPLTO_runs": 0, "product_links": 0,
            "new_media_builds": 0, "new_device_contacts": 0,
            "bounded_repair_rounds_consumed": 1},
    }
    validate(value)
    return value


def build() -> None:
    require(not RECEIPT.exists() and not REPORT.exists(),
            "replacement-red attribution is one-shot")
    value = derive()
    write(RECEIPT, value)
    write(REPORT, report(value).encode())
    check()
    print("v2.0 Comfort replacement red: ATTRIBUTION PASS; Comfort descoped")


def check() -> None:
    require(RECEIPT.is_file() and REPORT.is_file(),
            "replacement-red attribution outputs absent")
    value = load(RECEIPT)
    validate(value)
    require(value == derive()
            and REPORT.read_text(encoding="utf-8") == report(value),
            "replacement-red attribution persisted-world drift")
    print("v2.0 Comfort replacement red: CHECK PASS; device=0")


def source_check() -> None:
    value = load(RECEIPT)
    validate(value)
    require(RECEIPT.read_bytes() == sealed_file(RECEIPT)
            and REPORT.read_bytes() == sealed_file(REPORT),
            "sealed Comfort replacement-red evidence drift")
    print("v2.0 Comfort replacement red: SOURCE CHECK PASS "
          "sealed-evidence-era; device=0")


def selftest() -> None:
    value = load(RECEIPT)
    mutations: dict[str, Any] = {
        "resident-owner-hidden": lambda row: row["ownership_world"].update(
            editor_ownership="external-library-owner"),
        "duplicate-role-not-excluded": lambda row: row["ownership_world"].update(
            excluded_library_role="v16core"),
        "overlap-underreported": lambda row: row["ownership_world"].update(
            overwritten_resident_owner_count=0),
        "comfort-only-case-missing": lambda row: row["comfort_only_world"].update(
            case_count=8),
        "one-row-requires-duplicate": lambda row: row["comfort_only_world"]
            ["one_row_projection"].update(dependencies=[0]),
        "third-medium-silently-opened": lambda row: row["decision"].update(
            third_medium_authorized=True),
        "descope-not-applied": lambda row: row["decision"].update(
            comfort_v2_0="OPEN"),
    }
    rejected = []
    for name, mutate in mutations.items():
        mutant = deepcopy(value)
        mutate(mutant)
        try:
            validate(mutant)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(mutations),
            "replacement-red attribution mutation gate weakened")
    print(f"v2.0 Comfort replacement red: SELFTEST PASS mutations={len(rejected)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("build", "check", "source-check",
                                             "selftest"))
    args = parser.parse_args()
    globals()[args.command.replace("-", "_")]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
