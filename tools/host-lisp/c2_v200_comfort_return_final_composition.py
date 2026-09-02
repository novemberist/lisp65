#!/usr/bin/env python3
"""Build the final, single-owner v2.0 Comfort composition and session."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
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

import c2_v17_comfort_phase1b_acceptance_media as V17  # noqa: E402
import c2_v200_comfort_return_card as CARD  # noqa: E402
import c2_v200_comfort_return_media as BASE  # noqa: E402
import c2_v200_comfort_return_materialization_repair as REPAIR  # noqa: E402
import c2_v200_comfort_return_repair_red_attribution as RED  # noqa: E402
import c2_v200_symbol22_build_id_device_media as R4_MEDIA  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
PLAN_HEADER = (
    "## Reviewer ruling — Comfort descope lifted; media-composition budget — "
    "2026-08-31")
BUILD = ROOT / "build/c2.3/v2.0-comfort-return-final-composition"
PRODUCT = BUILD / "shared-system/lisp65-product.d81"
LIBRARY = BUILD / "library"
LIBRARY_D81 = LIBRARY / "lisp65-library.d81"
INDEX = LIBRARY / "l65index"
COMFORT_ARTIFACT = LIBRARY / "repl-comfort.l65s"
RECEIPT = ARCH / (
    "c2.3-v2.0-comfort-return-final-composition-receipt.json")
REPORT = ROOT / "docs/planning/v2.0.0-comfort-return-final-composition-report.md"
SESSION = ROOT / "config/c2-v200-comfort-return-device-session-r2.json"
PRODUCT_REMOTE = "V20CFR3P.D81"
LIBRARY_REMOTE = "V20CFR3L.D81"
FORMAT = "lisp65-c2-v200-comfort-return-final-composition-v1"
SESSION_FORMAT = "lisp65-c2-v200-comfort-return-device-session-v3"
STATUS = "PASS: FINAL COMFORT COMPOSITION READY"
EVIDENCE_SEAL_COMMIT = "6bc8de21726cf6439ae1036adf3cf791d97eeb4b"


class CompositionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CompositionError(message)


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


def owner_authority() -> dict[str, Any]:
    text = PLAN.read_text(encoding="utf-8")
    require(text.count(PLAN_HEADER) == 1,
            "final Comfort composition owner authority drift")
    section = PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    folded = " ".join(section.lower().replace("`", "").replace(
        "*", "").split())
    for token in ("exactly one further medium", "no v16core",
                  "packed-medium closure gate", "no packed object overwrites",
                  "block 3 is not hostage to comfort"):
        require(token in folded, f"owner authority absent: {token}")
    raw = section.encode()
    return {"path": PLAN.relative_to(ROOT).as_posix(), "section": PLAN_HEADER,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "right": "one final artifact-only Comfort composition medium"}


def final_product_entries() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    count = 0
    for row in load(REPAIR.STATIC_MANIFEST)["manifests"]:
        manifest = load(ROOT / row["path"])
        for entry in manifest["entries"]:
            result[entry["name"]] = entry
            count += 1
    require(count == 760, "final product entry population drift")
    return result


def symbol_literals(entry: dict[str, Any]) -> list[str]:
    result: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if set(value) == {"symbol"} and isinstance(value["symbol"], str):
                result.append(value["symbol"])
            else:
                for nested in value.values():
                    visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)

    visit(entry.get("literals", []))
    return result


def composition_preflight() -> dict[str, Any]:
    product = final_product_entries()
    comfort = load(REPAIR.COMFORT_MANIFEST)
    product_names = set(product)
    library_names = set(comfort["functions"])
    references = sorted({name for entry in comfort["entries"]
                         for name in symbol_literals(entry)})
    own = sorted(set(references) & library_names)
    resident = sorted(set(references) - library_names & product_names)
    missing = sorted(set(references) - library_names - product_names)
    overlap = sorted(library_names & product_names)
    expected_functions = ["%repl-read", "%repl-prompt", "%repl-step", "repl"]
    expected_own = ["%repl-prompt", "%repl-read", "%repl-step", "repl"]
    expected_resident = ["%ide-line-net-depth", "%read-line-loop",
        "%rl-screen-tail", "butlast", "eval", "last", "lcc-run", "length",
        "list", "nthcdr", "read-from-string", "screen-bulk-p",
        "string-append", "substring", "terpri", "write", "write-line"]
    require(comfort["functions"] == expected_functions
            and len(references) == 21 and own == expected_own
            and resident == expected_resident and not missing and not overlap,
            "product plus Comfort composition closure/ownership drift")
    return {
        "status": "PASS: COMBINED PRODUCT/MEDIUM CALLEE CLOSURE",
        "product_static_entries": 760,
        "product_final_directory_names": len(product_names),
        "packed_objects": comfort["functions"],
        "packed_object_count": len(library_names),
        "symbolic_references": references,
        "symbolic_reference_count": len(references),
        "library_owned_references": own,
        "resident_product_references": resident,
        "missing_references": missing,
        "packed_resident_owner_overlap": overlap,
        "single_owner": not overlap,
        "external_duplicate_designators": [],
    }


def project_product() -> dict[str, Any]:
    source = REPAIR.BASE.SOURCE_PRODUCT
    require(bind(source)["sha256"] == REPAIR.BASE.PRODUCT_D81_SHA256,
            "qualified r4 product source drift")
    PRODUCT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, PRODUCT)
    require(PRODUCT.read_bytes() == source.read_bytes(),
            "artifact-only product projection changed a byte")
    return {"source": bind(source), "projected": bind(PRODUCT),
            "operation": "byte-identical artifact copy; no product build/link"}


def build_library() -> dict[str, Any]:
    spec = ("repl-comfort", "repl", "repl", REPAIR.COMFORT_MANIFEST, ())
    LIBRARY.mkdir(parents=True, exist_ok=True)
    placeholder, artifact = V17.LIBMEDIA.measured(
        spec, (1, 1), REPAIR.BASE.PRODUCT_ID)
    seed_index = LIBRARY / "l65index.seed"
    seed_index.write_bytes(V17.LIBMEDIA.L65I.encode_index([placeholder]))
    seed = LIBRARY / "library.seed.d81"
    COMFORT_ARTIFACT.write_bytes(artifact)
    V17.LIBMEDIA.build_library_d81(
        seed, seed_index, [(COMFORT_ARTIFACT, "repl-comfort")])
    locator = V17.LIBMEDIA.L65I.d81_locators(seed)["repl-comfort"]
    row, located_artifact = V17.LIBMEDIA.measured(
        spec, locator, REPAIR.BASE.PRODUCT_ID)
    require(located_artifact == artifact, "Comfort artifact changed with locator")
    encoded = V17.LIBMEDIA.L65I.encode_index([row])
    INDEX.write_bytes(encoded)
    decoded = V17.LIBMEDIA.L65I.decode_index(
        encoded, {"repl-comfort": artifact},
        artifact_build_id=REPAIR.BASE.PRODUCT_ID)
    contract = V17.LIBMEDIA.resolver_contract(decoded, "repl-comfort")
    V17.LIBMEDIA.build_library_d81(
        LIBRARY_D81, INDEX, [(COMFORT_ARTIFACT, "repl-comfort")])
    visible = V17.LIBMEDIA.L65I.D81.visible_files(LIBRARY_D81.read_bytes())
    prior = load(REPAIR.RECEIPT)["library"]["artifacts"]["repl-comfort"]
    require(row["dependencies"] == []
            and contract["actual_resolver_order"] == [0]
            and bind(COMFORT_ARTIFACT)["sha256"] == prior["sha256"]
            and visible == {b"L65INDEX": encoded,
                            b"REPL-COMFORT": artifact},
            "one-row Comfort library materialization drift")
    seed.unlink()
    seed_index.unlink()
    return {
        "status": "PASS: ONE-ROW COMFORT LIBRARY, NO V16CORE",
        "D81": bind(LIBRARY_D81), "index": bind(INDEX),
        "artifact": bind(COMFORT_ARTIFACT),
        "sealed_artifact_predecessor": prior,
        "manifest": bind(REPAIR.COMFORT_MANIFEST),
        "index_rows": decoded, "resolver_contract": contract,
        "visible_files": sorted(name.decode() for name in visible),
        "external_library_dependencies": row["dependencies"],
    }


def read_library() -> dict[str, Any]:
    require(INDEX.is_file() and LIBRARY_D81.is_file()
            and COMFORT_ARTIFACT.is_file(),
            "frozen one-row Comfort library absent")
    artifact = COMFORT_ARTIFACT.read_bytes()
    encoded = INDEX.read_bytes()
    decoded = V17.LIBMEDIA.L65I.decode_index(
        encoded, {"repl-comfort": artifact},
        artifact_build_id=REPAIR.BASE.PRODUCT_ID)
    contract = V17.LIBMEDIA.resolver_contract(decoded, "repl-comfort")
    visible = V17.LIBMEDIA.L65I.D81.visible_files(LIBRARY_D81.read_bytes())
    prior = load(REPAIR.RECEIPT)["library"]["artifacts"]["repl-comfort"]
    require(len(decoded) == 1 and decoded[0]["dependencies"] == []
            and contract["actual_resolver_order"] == [0]
            and bind(COMFORT_ARTIFACT)["sha256"] == prior["sha256"]
            and visible == {b"L65INDEX": encoded,
                            b"REPL-COMFORT": artifact},
            "frozen one-row Comfort library drift")
    return {
        "status": "PASS: ONE-ROW COMFORT LIBRARY, NO V16CORE",
        "D81": bind(LIBRARY_D81), "index": bind(INDEX),
        "artifact": bind(COMFORT_ARTIFACT),
        "sealed_artifact_predecessor": prior,
        "manifest": bind(REPAIR.COMFORT_MANIFEST),
        "index_rows": decoded, "resolver_contract": contract,
        "visible_files": sorted(name.decode() for name in visible),
        "external_library_dependencies": decoded[0]["dependencies"],
    }


def pair_identity() -> dict[str, Any]:
    R4_MEDIA.configure()
    pair = R4_MEDIA.BASE.MEDIA.PREP.PAIR.pair_identity(PRODUCT, LIBRARY_D81)
    require(pair["result"] == "same-world-pair"
            and pair["product_build_id"]
                == f"0x{REPAIR.BASE.PRODUCT_ID:08x}"
            and pair["index_rows"] == 1
            and pair["row_names"] == ["repl-comfort"]
            and set(pair["library_build_ids"].values())
                == {f"0x{REPAIR.BASE.PRODUCT_ID:08x}"},
            "final Comfort product/library identity drift")
    return pair


def session_value() -> dict[str, Any]:
    session = deepcopy(load(BASE.SESSION))
    session["format"] = SESSION_FORMAT
    session["status"] = "READY: OWNER V2.0 FINAL COMFORT COMPOSITION CONTACT"
    session["media"] = {
        "product": {**bind(PRODUCT), "remote_name": PRODUCT_REMOTE},
        "library": {**bind(LIBRARY_D81), "remote_name": LIBRARY_REMOTE},
    }
    session["world"]["same_world_pair"] = pair_identity()
    session["world"]["final_composition"] = {
        "receipt": RECEIPT.relative_to(ROOT).as_posix(),
        "library_rows": ["repl-comfort"],
        "resident_editor_owner": True,
        "external_editor_duplicate": False,
    }
    row = next(item for item in session["rows"] if item["id"] == "C1")
    row["actions"] = [
        "cold boot product and mount the prepared library physically",
        "at lisp65> submit (require 'repl-comfort), then submit (repl)",
        "at l65> submit one empty line; at lisp65> submit (repl) again",
    ]
    row["expect"] = ["require returns t", "Comfort prompt is l65>",
        "empty balanced line returns to one native lisp65>",
        "second entry returns to l65>"]
    session["decision_table"]["daily-use-blocker"] = (
        "final composition contact red: Comfort descopes; no further medium")
    session["claim_scope"]["green_consequence"] = (
        "Comfort accepted; Block 3 remains independently open")
    session["evidence_limit"] = (
        "one final composition contact; no external editor duplicate and no "
        "further media round")
    require("v16core" not in canonical(session).decode().lower(),
            "final session still names v16core")
    return session


def host_execution() -> dict[str, Any]:
    value = RED.comfort_only_world()
    require(value["case_count"] == 9
            and value["status"]
                == "PASS: PRODUCT PLUS SEALED COMFORT, NO V16CORE",
            "final one-row host execution drift")
    return value


def validate(value: dict[str, Any]) -> None:
    session = value["session_value"]
    session_text = canonical(session).decode().lower()
    c1 = next(item for item in session["rows"] if item["id"] == "C1")
    preflight = value["composition_preflight"]
    library = value["library"]
    require(value["format"] == FORMAT and value["status"] == STATUS
            and value["accounting"] == {"WPLTO_runs": 0,
                "product_links": 0, "product_cards": 0,
                "artifact_only_product_copies": 1,
                "library_media_builds": 1, "device_contacts": 0,
                "remaining_composition_media_budget": 0}
            and value["product"]["source"]["sha256"]
                == value["product"]["projected"]["sha256"]
                == REPAIR.BASE.PRODUCT_D81_SHA256
            and value["same_world_pair"]["row_names"] == ["repl-comfort"]
            and library["visible_files"] == ["L65INDEX", "REPL-COMFORT"]
            and library["external_library_dependencies"] == []
            and library["artifact"]["sha256"]
                == library["sealed_artifact_predecessor"]["sha256"]
            and preflight["packed_object_count"] == 4
            and preflight["symbolic_reference_count"] == 21
            and not preflight["missing_references"]
            and not preflight["packed_resident_owner_overlap"]
            and preflight["single_owner"]
            and not preflight["external_duplicate_designators"]
            and value["host_execution"]["case_count"] == 9
            and session["format"] == SESSION_FORMAT
            and session["world"]["final_composition"]["library_rows"]
                == ["repl-comfort"]
            and not session["world"]["final_composition"]
                ["external_editor_duplicate"]
            and c1["actions"][1]
                == "at lisp65> submit (require 'repl-comfort), then submit (repl)"
            and session_text.count("(require '") == 1
            and "v16core" not in session_text
            and session["decision_table"]["daily-use-blocker"]
                == "final composition contact red: Comfort descopes; no further medium",
            "final Comfort composition semantic wall red")


def report(value: dict[str, Any]) -> str:
    return f"""# v2.0 final Comfort media composition

Status: **{value['status']}**

## Composition

The final library medium has one index row and two visible files:
`L65INDEX` and `REPL-COMFORT`.  It contains no `v16core`, no dependency row,
and no external copy of a resident editor object.  The product medium is a
byte-identical projection of the qualified r4 product.

The packed Comfort artifact remains byte-identical to its sealed predecessor
(`{value['library']['artifact']['sha256']}`).  Its four objects carry 21
symbolic references: four resolve within Comfort and seventeen resolve to the
resident product.  Missing references: zero.  Packed/resident owner overlap:
zero.  All nine registered Comfort cases pass in this exact combined function
world.

## Pre-deploy bars

1. The bound session contains exactly one load form: `repl-comfort`; the token
   `v16core` is absent from the complete session document.
2. Product-plus-medium symbolic closure is complete.
3. The packed object set is disjoint from the resident product owner set.

The mutation gate rejects reintroduced `v16core`, an external resident editor
copy, a missing resident callee, a second index row and a changed Comfort
artifact.

## Budget and next step

This consumes the single final media-composition round.  It uses zero WPLTOs,
zero product links and zero product cards.  Product SHA-256:
`{value['product']['projected']['sha256']}`.  Library SHA-256:
`{value['library']['D81']['sha256']}`.

One owner device contact is ready.  A daily-use red descopes Comfort without
another medium.  Block 3 remains independently open in either outcome.
"""


def derive(product: dict[str, Any], library: dict[str, Any]) -> dict[str, Any]:
    session = session_value()
    write(SESSION, session)
    value = {
        "format": FORMAT, "recorded_on": "2026-08-31", "status": STATUS,
        "authority": owner_authority(),
        "predecessors": {"red_attribution": bind(RED.RECEIPT),
                         "sealed_comfort_card": bind(CARD.RECEIPT)},
        "product": product, "library": library,
        "same_world_pair": pair_identity(),
        "composition_preflight": composition_preflight(),
        "host_execution": host_execution(),
        "session": bind(SESSION), "session_value": session,
        "accounting": {"WPLTO_runs": 0, "product_links": 0,
            "product_cards": 0, "artifact_only_product_copies": 1,
            "library_media_builds": 1, "device_contacts": 0,
            "remaining_composition_media_budget": 0},
        "claim_limit": ("final Comfort composition medium and one owner "
                        "contact; no hardware acceptance or release claim"),
    }
    validate(value)
    return value


def build() -> None:
    require(not BUILD.exists() and not RECEIPT.exists()
            and not REPORT.exists() and not SESSION.exists(),
            "final Comfort composition is one-shot")
    owner_authority()
    preflight = composition_preflight()
    require(preflight["single_owner"] and not preflight["missing_references"],
            "pre-media composition gate red")
    product = project_product()
    library = build_library()
    value = derive(product, library)
    write(RECEIPT, value)
    write(REPORT, report(value).encode())
    check()
    print("v2.0 final Comfort composition: BUILD PASS "
          f"product={value['product']['projected']['sha256']} "
          f"library={value['library']['D81']['sha256']} device=0")


def resume() -> None:
    require(BUILD.is_dir() and PRODUCT.is_file() and LIBRARY_D81.is_file()
            and not RECEIPT.exists() and not REPORT.exists()
            and not SESSION.exists(),
            "final Comfort composition resume precondition red")
    owner_authority()
    preflight = composition_preflight()
    require(preflight["single_owner"] and not preflight["missing_references"],
            "pre-media composition gate red")
    source = REPAIR.BASE.SOURCE_PRODUCT
    require(PRODUCT.read_bytes() == source.read_bytes(),
            "frozen product projection changed a byte")
    product = {"source": bind(source), "projected": bind(PRODUCT),
        "operation": "byte-identical artifact copy; no product build/link"}
    library = read_library()
    value = derive(product, library)
    write(RECEIPT, value)
    write(REPORT, report(value).encode())
    check()
    print("v2.0 final Comfort composition: RESUME PASS "
          f"product={value['product']['projected']['sha256']} "
          f"library={value['library']['D81']['sha256']} device=0")


def check() -> None:
    require(RECEIPT.is_file() and REPORT.is_file() and SESSION.is_file(),
            "final Comfort composition outputs absent")
    value = load(RECEIPT)
    validate(value)
    require(value["authority"] == owner_authority()
            and value["composition_preflight"] == composition_preflight()
            and value["host_execution"] == host_execution()
            and value["same_world_pair"] == pair_identity()
            and value["session_value"] == session_value()
            and bind(SESSION) == value["session"]
            and bind(PRODUCT) == value["product"]["projected"]
            and bind(LIBRARY_D81) == value["library"]["D81"]
            and bind(COMFORT_ARTIFACT) == value["library"]["artifact"]
            and REPORT.read_text(encoding="utf-8") == report(value),
            "final Comfort composition persisted-world drift")
    print("v2.0 final Comfort composition: CHECK PASS rows=1 device=0")


def source_check() -> None:
    value = load(RECEIPT)
    validate(value)
    require(RECEIPT.read_bytes() == sealed_file(RECEIPT)
            and REPORT.read_bytes() == sealed_file(REPORT)
            and SESSION.read_bytes() == sealed_file(SESSION),
            "sealed final Comfort composition evidence drift")
    print("v2.0 final Comfort composition: SOURCE CHECK PASS "
          "sealed-evidence-era rows=1 device=0")


def selftest() -> None:
    value = load(RECEIPT)
    mutations: dict[str, Any] = {
        "session-reintroduces-v16core": lambda row: row["session_value"]
            ["world"]["final_composition"].update(
                library_rows=["v16core", "repl-comfort"]),
        "session-loads-another-designator": lambda row: next(item for item in
            row["session_value"]["rows"] if item["id"] == "C1")["actions"].__setitem__(
                1, "at lisp65> submit (require 'other), then submit (repl)"),
        "session-external-editor-copy": lambda row: row["session_value"]
            ["world"]["final_composition"].update(
                external_editor_duplicate=True),
        "packed-resident-owner-overlap": lambda row: row
            ["composition_preflight"].update(
                packed_resident_owner_overlap=["read-line"]),
        "packed-closure-missing-callee": lambda row: row
            ["composition_preflight"].update(missing_references=["%rl-poll"]),
        "second-index-row": lambda row: row["same_world_pair"].update(
            row_names=["v16core", "repl-comfort"]),
        "comfort-artifact-changed": lambda row: row["library"]["artifact"].update(
            sha256="0" * 64),
        "composition-budget-reopened": lambda row: row["accounting"].update(
            remaining_composition_media_budget=1),
    }
    rejected = []
    for name, mutate in mutations.items():
        mutant = deepcopy(value)
        mutate(mutant)
        try:
            validate(mutant)
        except CompositionError:
            rejected.append(name)
    require(rejected == list(mutations),
            "final Comfort composition mutation gate weakened")
    print(f"v2.0 final Comfort composition: SELFTEST PASS mutations={len(rejected)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("build", "resume", "check",
                                             "source-check", "selftest"))
    args = parser.parse_args()
    globals()[args.command.replace("-", "_")]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
