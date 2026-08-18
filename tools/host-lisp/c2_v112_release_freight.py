#!/usr/bin/env python3
"""Promote and permanently gate the host-integrated v1.4 release freight."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0_stdlib as STD  # noqa: E402
import c2_v110_persistent_performance as V110  # noqa: E402
import c2_v111_compiler_locality as V111  # noqa: E402
import c2_v112_product_compiler_tier as TIER  # noqa: E402
import comfort_track_gate as COMFORT  # noqa: E402
import v11_surface_delivery_parity as PARITY  # noqa: E402


CONTRACT = ROOT / "config/c2-v112-release-closure.json"
PARITY_CONTRACT = ROOT / "config/v11-surface-delivery-parity.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-release-freight-receipt.json"
)
DRIVER = Path(__file__).resolve()
GATES = ROOT / "mk/gates.mk"
COMBINED_PREFIX = ROOT / "build/post-promotion/v112/comfort/comfort"
STRING_EXTRA_SUITE = ROOT / "tests/bytecode/libs/p0-string-extra.json"
INSPECT_SUITE = ROOT / "tests/bytecode/libs/p0-inspect.json"
STRING_EXTRA_PREFIX = ROOT / "build/post-promotion/v112/string-extra/string-extra"
INSPECT_PREFIX = ROOT / "build/post-promotion/v112/inspect/inspect"
COMPILER_SUITE = ROOT / "build/post-promotion/v112/compiler-tier/suite.json"
COMPILER_PREFIX = ROOT / "build/post-promotion/v112/compiler/lcc"
RELEASE_NAMES = ("capitalize", "string-split", "who-calls")
STRING_EXTRA_NAMES = ("capitalize", "%comfort-string-split-from", "string-split")
INSPECT_NAMES = ("%comfort-callers-index", "who-calls")
TRACE_NAMES = {
    "%comfort-trace-remove", "%comfort-trace-wrapper-form",
    "%comfort-trace-install-form", "trace", "untrace",
}
TRACE_SCOPE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-link92-r5-trace-fix-library-scope.json"
)
FORMAT = "lisp65-c2.3-v1.12-release-freight-v2"
RECORDED_ON = "2026-08-09"
HISTORICAL_TRACE_AUTHORITY = "f426f7c71b5e85bcbec0a181fa3d1e4838e6388f"


class FreightError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise FreightError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(raw),
        "sha256": sha(raw),
    }


def git_bytes(path: Path) -> bytes:
    relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
    result = subprocess.run(
        ["git", "show", f"{HISTORICAL_TRACE_AUTHORITY}:{relative}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return result.stdout


def git_json(path: Path) -> dict[str, Any]:
    value = json.loads(git_bytes(path).decode("utf-8"))
    require(isinstance(value, dict), f"historical JSON object required: {path}")
    return value


def bind_git(path: Path) -> dict[str, Any]:
    raw = git_bytes(path)
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "git_commit": HISTORICAL_TRACE_AUTHORITY,
        "bytes": len(raw),
        "sha256": sha(raw),
    }


def canonical(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def gate_wiring_projection() -> dict[str, Any]:
    text = GATES.read_text(encoding="utf-8")
    required = [
        "c2-v112-release-freight-selftest:",
        "python3 tools/host-lisp/c2_v112_release_freight.py selftest",
        "c2-v112-release-freight-check: c2-v112-release-freight-selftest",
        "python3 tools/host-lisp/c2_v112_release_freight.py check",
        "check-source: c2-v112-release-freight-check",
    ]
    require(all(row in text for row in required),
            "release-freight permanent gate wiring absent")
    return {"path": "mk/gates.mk", "semantic_projection": required}


def manifest_path(prefix: Path) -> Path:
    return prefix.with_suffix(".manifest.json")


def emit(suite_path: Path, prefix: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    suite = STD._read_suite(str(suite_path))
    checked = STD.check_suite(str(suite_path), suite)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    info = STD.emit_artifacts(
        str(suite_path), suite, str(prefix), base_addr=0, artifact_role="disk-lib",
    )
    return checked, load(manifest_path(prefix))


def entry_code(prefix: Path, manifest: dict[str, Any], name: str) -> bytes:
    matches = [row for row in manifest["entries"] if row["name"] == name]
    require(len(matches) == 1, f"artifact function identity drift: {name}")
    row = matches[0]
    blob = prefix.with_suffix(".blob.bin").read_bytes()
    start = int(row["blob_offset"])
    return blob[start:start + int(row["length"])]


def entry_payload(prefix: Path, name: str) -> list[str]:
    lines = prefix.with_suffix(".disasm.txt").read_text(encoding="utf-8").splitlines()
    marker = next(index for index, line in enumerate(lines)
                  if line.startswith("[") and line.endswith("] " + name))
    end = next((index for index in range(marker + 1, len(lines))
                if lines[index].startswith("[")), len(lines))
    section = lines[marker:end]
    payload = section.index("  payload:")
    return [line.strip() for line in section[payload + 1:] if line.strip()]


def split_identity_gate(
    string_manifest: dict[str, Any], inspect_manifest: dict[str, Any],
) -> dict[str, Any]:
    combined = load(manifest_path(COMBINED_PREFIX))
    split = {
        **{name: (STRING_EXTRA_PREFIX, string_manifest) for name in STRING_EXTRA_NAMES},
        **{name: (INSPECT_PREFIX, inspect_manifest) for name in INSPECT_NAMES},
    }
    combined_rows = {row["name"]: row for row in combined["entries"]}
    require(set(split).issubset(combined_rows)
            and set(split) == set(STRING_EXTRA_NAMES) | set(INSPECT_NAMES),
            "released split library function closure drift")
    require(not TRACE_NAMES.intersection(split),
            "descoped trace object survived released split freight")
    exact = []
    relocated = []
    semantic_keys = ("name", "kind", "length", "flags", "code_flags",
                     "lit_count", "literals")
    for name, (prefix, manifest) in split.items():
        row = next(item for item in manifest["entries"] if item["name"] == name)
        old = combined_rows[name]
        require({key: row[key] for key in semantic_keys}
                    == {key: old[key] for key in semantic_keys}
                and entry_payload(prefix, name) == entry_payload(COMBINED_PREFIX, name),
                f"split changed function instruction semantics: {name}")
        if entry_code(prefix, manifest, name) == entry_code(COMBINED_PREFIX, combined, name):
            exact.append(name)
        else:
            require(name in INSPECT_NAMES,
                    f"non-inspect function acquired a relocation delta: {name}")
            relocated.append(name)
    return {
        "status": "passed-three-byteidentical-two-literal-relocation-equivalent",
        "functions": sorted(exact + relocated),
        "function_count": len(exact + relocated),
        "byteidentical_functions": sorted(exact),
        "literal_relocated_functions": sorted(relocated),
        "instruction_payloads_identical": True,
        "resident_delta_bytes": 0,
    }


def parity_check() -> list[str]:
    contract = load(PARITY_CONTRACT)
    return PARITY.verify_values(
        contract,
        load(ROOT / contract["surface"]),
        load(ROOT / contract["dialect_contract"]),
        load(ROOT / contract["resident_manifest"]),
        [load(ROOT / path) for path in contract["library_manifests"]],
        (ROOT / contract["language_reference"]).read_text(encoding="utf-8"),
        load(ROOT / contract["native_registry"]),
        load(ROOT / contract["artifact_closure"]),
        (ROOT / contract["workbench_profile"]).read_text(encoding="utf-8"),
    )


def derive() -> dict[str, Any]:
    contract = load(CONTRACT)
    selector = contract.get("selector", {})
    require(contract.get("integration_state") in ("host-integrated", "media-closed", "selected")
            and selector.get("state") in ("pending", "base"),
            "host integration/media-closed/selected state or selector drift")

    # Rerun each accepted authority; do not treat its old receipt as execution.
    v110 = V110.derive()
    V110.audit_result(v110)
    v111 = V111.derive()
    V111.audit_result(v111)
    comfort_contract = load(COMFORT.CONTRACT)
    COMFORT.audit_contract(comfort_contract)
    graph, graph_info = COMFORT.shelf_graph(comfort_contract)
    generated = (ROOT / comfort_contract["who_calls"]["generated_source"])
    COMFORT.audit_generated(graph, generated.read_text(encoding="utf-8"))
    comfort = load(COMFORT.RECEIPT)
    require(
        comfort.get("who_calls", {}).get("unique_edges")
        == graph_info["unique_edges"] == 109,
        "who-calls graph authority drift",
    )
    # v1.4 freight is sealed history.  Its trace-descope premise must be read
    # from the owner decision that made it true, never from a successor ABI's
    # live reconstruction of that premise.
    trace_scope = git_json(TRACE_SCOPE)
    require(
        trace_scope.get("status")
        == "descope-required-missing-function-cell-capability",
        "trace descope authority drift",
    )

    generation = TIER.generate(COMPILER_SUITE)
    compiler_checked, compiler = emit(COMPILER_SUITE, COMPILER_PREFIX)
    string_checked, string_manifest = emit(STRING_EXTRA_SUITE, STRING_EXTRA_PREFIX)
    inspect_checked, inspect_manifest = emit(INSPECT_SUITE, INSPECT_PREFIX)
    split_identity = split_identity_gate(string_manifest, inspect_manifest)
    defstruct_built = V110.build_candidate(load(ROOT / "config/c2-v110-persistent-performance.json"))
    defstruct = defstruct_built["manifest"]

    accepted_compiler = v111["authorities"]["candidate_manifest"]
    accepted_path = ROOT / accepted_compiler["path"]
    accepted = load(accepted_path)
    for suffix in ("blob.bin", "dir.bin", "ext.bin"):
        old = accepted_path.with_name("lcc." + suffix)
        new = COMPILER_PREFIX.with_suffix("." + suffix)
        require(old.read_bytes() == new.read_bytes(),
                f"promoted compiler {suffix} differs from accepted v1.11 freight")
    require(accepted["entries"] == compiler["entries"],
            "promoted compiler directory semantics drift")
    require(compiler.get("private_inline_functions") == list(TIER.V111.PRIVATE_INLINE)
            and compiler.get("cost", {}).get("private_inline_gate", {}).get("functions") == 10,
            "promoted private-inline closure drift")

    names = parity_check()
    claims = load(PARITY_CONTRACT)["claims"]
    claim_names = {row["name"] for row in claims}
    require(all(name in claim_names and name in names for name in RELEASE_NAMES),
            "released library surface parity incomplete")
    require(not {"trace", "untrace"}.intersection(claim_names)
            and not {"trace", "untrace"}.intersection(names),
            "descoped trace surface survived parity")
    require("defstruct" not in claim_names, "defstruct escaped pending D2 selector")
    require(
        len(names) == 93
        and not any(name.startswith("m65-") for name in names)
        and not any(name.startswith("m65-") for name in claim_names),
        "parked parity primitives escaped the v1.4 scope freeze",
    )

    price = v111["pricing"]
    require(price["full_sequence"]["candidate"]["operational_floor_seconds"] <= 677
            and price["post_require_definition"]["candidate"]["operational_floor_seconds"] <= 179,
            "promoted locality price regressed")
    projection = v110["host_execution"]["behavior_projection"]
    require(projection["C2J"] == "CLEAR"
            and projection["form_kinds"].count("persistent-definition") == 9
            and len(projection["generated_entries"]) == 9,
            "defstruct publish-last/rollback semantics drift")

    headroom = int(comfort["artifact"]["bank2_headroom_before_bytes"])
    compiler_delta = int(v111["freight"]["delta"]["external_image_bytes"])
    split_external = (int(string_manifest["external_image"]["bytes"])
                      + int(inspect_manifest["external_image"]["bytes"]))
    base_remaining = headroom - split_external - compiler_delta
    sibling_remaining = base_remaining - int(defstruct["external_image"]["bytes"])
    floor = int(comfort["artifact"]["minimum_preserved_headroom_bytes"])
    require(base_remaining >= floor and sibling_remaining >= floor,
            "integrated Bank-2 freight crosses preserved headroom floor")

    return {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "passed-host-integrated-release-freight",
        "historical_trace_authority_commit": HISTORICAL_TRACE_AUTHORITY,
        "execution": {
            "v110_reconstructed": True,
            "v111_reconstructed": True,
            "library_split_reconstructed": True,
            "compiler_cases": compiler_checked["cases"],
            "string_extra_cases": string_checked["cases"],
            "inspect_cases": inspect_checked["cases"],
            "defstruct_cases": defstruct_built["standalone"]["cases"],
        },
        "compiler_promotion": {
            "one_complete_product_carrier": True,
            "accepted_overlay_forms_equal": True,
            "blob_byteidentical_to_v111": True,
            "directory_byteidentical_to_v111": True,
            "external_image_byteidentical_to_v111": True,
            "private_inline_functions": list(TIER.V111.PRIVATE_INLINE),
            "generation": generation,
        },
        "defstruct": {
            "forms": 11,
            "persistent_appends": 9,
            "publish_last": True,
            "rollback_correct": True,
            "constructor_result": "(point 3 4)",
            "final_c2j": "CLEAR",
            "public_before_D2": False,
        },
        "pricing": {
            "full_sequence_seconds": price["full_sequence"]["candidate"]["operational_floor_seconds"],
            "post_require_seconds": price["post_require_definition"]["candidate"]["operational_floor_seconds"],
            "structural_price_is_completion_upper_bound": False,
        },
        "libraries": {
            "public_names": list(RELEASE_NAMES),
            "string-extra": {
                "public_names": ["capitalize", "string-split"],
                "artifact_objects": len(string_manifest["entries"]),
            },
            "inspect": {
                "public_names": ["who-calls"],
                "artifact_objects": len(inspect_manifest["entries"]),
            },
            "artifact_objects": (len(string_manifest["entries"])
                                 + len(inspect_manifest["entries"])),
            "who_calls_exact_edges": comfort["who_calls"]["unique_edges"],
            "trace_descope": {
                "status": "not-delivered",
                "forbidden_names": ["trace", "untrace"],
                "inspect_trace_objects": sorted(
                    TRACE_NAMES.intersection(
                        row["name"] for row in inspect_manifest["entries"])),
                "authority": bind_git(TRACE_SCOPE),
            },
            "split_identity": split_identity,
        },
        "bank2": {
            "headroom_before_bytes": headroom,
            "split_library_external_bytes": split_external,
            "compiler_external_delta_bytes": compiler_delta,
            "defstruct_external_bytes": int(defstruct["external_image"]["bytes"]),
            "base_remaining_bytes": base_remaining,
            "defstruct_sibling_remaining_bytes": sibling_remaining,
            "minimum_preserved_bytes": floor,
            "resident_delta_bytes": 0,
        },
        "surface": {
            "parity_bound_names": len(names),
            "parity_primitives_public": False,
            "split_library_one_truth": True,
            "selector_state": selector["state"],
            "defstruct_public": False,
        },
        "authorities": {
            "contract": bind(CONTRACT),
            "parity_contract": bind(PARITY_CONTRACT),
            "driver": bind(DRIVER),
            "gate_wiring": gate_wiring_projection(),
            "promoted_overlay": bind(ROOT / TIER.PROMOTED_SOURCE),
            "accepted_overlay": bind(ROOT / TIER.V111.CANDIDATE_SOURCE),
            "compiler_suite": bind(COMPILER_SUITE),
            "compiler_manifest": bind(manifest_path(COMPILER_PREFIX)),
            "string_extra_suite": bind(STRING_EXTRA_SUITE),
            "string_extra_manifest": bind(manifest_path(STRING_EXTRA_PREFIX)),
            "inspect_suite": bind(INSPECT_SUITE),
            "inspect_manifest": bind(manifest_path(INSPECT_PREFIX)),
            "combined_development_manifest": bind(manifest_path(COMBINED_PREFIX)),
            "defstruct_manifest": bind(defstruct_built["manifest_path"]),
            "v110_receipt": bind(V110.RECEIPT),
            "v111_receipt": bind(V111.RECEIPT),
            "comfort_receipt": bind(COMFORT.RECEIPT),
            "trace_descope_receipt": bind_git(TRACE_SCOPE),
            "language_reference": bind(ROOT / "docs/language-reference.md"),
        },
        "claim_limit": (
            "Host-integrated release freight and public split-library parity only. "
            "No product core, media, device, link, D2, Halt-1 or release claim."
        ),
    }


def audit(value: dict[str, Any]) -> None:
    require(value.get("format") == FORMAT
            and value.get("recorded_on") == RECORDED_ON,
            "freight receipt authority format drift")
    require(value.get("status") == "passed-host-integrated-release-freight",
            "freight status drift")
    require(value.get("historical_trace_authority_commit")
            == HISTORICAL_TRACE_AUTHORITY,
            "sealed trace-descope authority drift")
    require(value.get("defstruct") == {
        "forms": 11, "persistent_appends": 9, "publish_last": True,
        "rollback_correct": True, "constructor_result": "(point 3 4)",
        "final_c2j": "CLEAR", "public_before_D2": False,
    }, "defstruct semantic closure drift")
    require(value.get("pricing") == {
        "full_sequence_seconds": 677,
        "post_require_seconds": 179,
        "structural_price_is_completion_upper_bound": False,
    }, "release pricing closure drift")
    libraries = value.get("libraries", {})
    require(libraries.get("public_names") == list(RELEASE_NAMES)
            and libraries.get("artifact_objects") == 5
            and libraries.get("who_calls_exact_edges") == 109
            and libraries.get("string-extra") == {
                "public_names": ["capitalize", "string-split"],
                "artifact_objects": 3,
            }
            and libraries.get("inspect") == {
                "public_names": ["who-calls"],
                "artifact_objects": 2,
            }
            and libraries.get("split_identity", {}).get("function_count") == 5
            and len(libraries.get("split_identity", {}).get("byteidentical_functions", [])) == 3
            and len(libraries.get("split_identity", {}).get("literal_relocated_functions", [])) == 2
            and libraries.get("split_identity", {}).get("instruction_payloads_identical") is True
            and libraries.get("split_identity", {}).get("resident_delta_bytes") == 0,
            "split library delivery closure drift")
    require(libraries.get("trace_descope", {}).get("status") == "not-delivered"
            and libraries.get("trace_descope", {}).get("forbidden_names")
            == ["trace", "untrace"]
            and libraries.get("trace_descope", {}).get("inspect_trace_objects") == [],
            "trace/untrace descope closure drift")
    bank = value.get("bank2", {})
    require(bank.get("resident_delta_bytes") == 0
            and bank.get("base_remaining_bytes", 0) >= bank.get("minimum_preserved_bytes", 1)
            and bank.get("defstruct_sibling_remaining_bytes", 0)
            >= bank.get("minimum_preserved_bytes", 1),
            "Bank-2/resident capacity closure drift")
    require(value.get("surface", {}).get("parity_bound_names") == 93
            and value.get("surface", {}).get("parity_primitives_public") is False
            and value.get("surface", {}).get("split_library_one_truth") is True
            and value.get("surface", {}).get("selector_state") == "base"
            and value.get("surface", {}).get("defstruct_public") is False,
            "conditional surface closure drift")


def rejected(label: str, value: dict[str, Any], mutate: Callable[[dict[str, Any]], None],
             results: dict[str, str]) -> None:
    changed = deepcopy(value)
    mutate(changed)
    try:
        audit(changed)
    except FreightError as error:
        results[label] = str(error)
    else:
        raise FreightError(f"release-freight mutation survived: {label}")


def mutations(value: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    tests: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("defstruct:form-lost", lambda x: x["defstruct"].__setitem__("forms", 10)),
        ("defstruct:append-lost", lambda x: x["defstruct"].__setitem__("persistent_appends", 8)),
        ("defstruct:publish-before-commit", lambda x: x["defstruct"].__setitem__("publish_last", False)),
        ("defstruct:rollback-broken", lambda x: x["defstruct"].__setitem__("rollback_correct", False)),
        ("defstruct:journal-dirty", lambda x: x["defstruct"].__setitem__("final_c2j", "DIRTY")),
        ("selector:bypass", lambda x: x["defstruct"].__setitem__("public_before_D2", True)),
        ("price:full-regression", lambda x: x["pricing"].__setitem__("full_sequence_seconds", 678)),
        ("price:post-regression", lambda x: x["pricing"].__setitem__("post_require_seconds", 180)),
        ("price:upper-bound-overclaim", lambda x: x["pricing"].__setitem__("structural_price_is_completion_upper_bound", True)),
        ("libraries:name-lost", lambda x: x["libraries"]["public_names"].pop()),
        ("libraries:edge-invented", lambda x: x["libraries"].__setitem__("who_calls_exact_edges", 110)),
        ("libraries:string-extra-name-dimmed", lambda x: x["libraries"]["string-extra"]["public_names"].pop()),
        ("libraries:inspect-name-dimmed", lambda x: x["libraries"]["inspect"]["public_names"].pop()),
        ("libraries:split-byte-identity-dimmed", lambda x: x["libraries"]["split_identity"].__setitem__("function_count", 4)),
        ("libraries:split-payload-equivalence-dimmed", lambda x: x["libraries"]["split_identity"].__setitem__("instruction_payloads_identical", False)),
        ("descope:trace-name-survives", lambda x: x["libraries"]["trace_descope"]["forbidden_names"].pop()),
        ("descope:trace-object-survives", lambda x: x["libraries"]["trace_descope"]["inspect_trace_objects"].append("trace")),
        ("descope:status-dimmed", lambda x: x["libraries"]["trace_descope"].__setitem__("status", "delivered")),
        ("descope:historical-authority-dimmed", lambda x: x.__setitem__("historical_trace_authority_commit", "0" * 40)),
        ("capacity:base-over", lambda x: x["bank2"].__setitem__("base_remaining_bytes", 8191)),
        ("capacity:sibling-over", lambda x: x["bank2"].__setitem__("defstruct_sibling_remaining_bytes", 8191)),
        ("resident:growth", lambda x: x["bank2"].__setitem__("resident_delta_bytes", 1)),
        ("scope:parked-parity-public", lambda x: x["surface"].__setitem__("parity_primitives_public", True)),
        ("surface:second-truth", lambda x: x["surface"].__setitem__("split_library_one_truth", False)),
        ("selector:defstruct-selected", lambda x: x["surface"].__setitem__("selector_state", "defstruct")),
        ("selector:defstruct-public", lambda x: x["surface"].__setitem__("defstruct_public", True)),
    ]
    for label, mutate in tests:
        rejected(label, value, mutate, result)
    require(len(result) == 26, "release-freight mutation count drift")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("selftest", "write", "check"))
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            value = load(RECEIPT)
            audit(value)
            result = mutations(value)
            print(f"c2-v112-release-freight: SELFTEST PASS mutations={len(result)}")
            return 0
        value = derive()
        audit(value)
        value["mutations_rejected"] = mutations(value)
        value["mutation_count"] = len(value["mutations_rejected"])
        if args.action == "write":
            RECEIPT.parent.mkdir(parents=True, exist_ok=True)
            RECEIPT.write_text(canonical(value), encoding="utf-8")
        else:
            require(load(RECEIPT) == value, "release-freight receipt drift")
        print(
            "c2-v112-release-freight: PASS "
            f"full={value['pricing']['full_sequence_seconds']}s "
            f"post={value['pricing']['post_require_seconds']}s "
            f"split-libraries={len(value['libraries']['public_names'])} "
            f"base-headroom={value['bank2']['base_remaining_bytes']} "
            f"sibling-headroom={value['bank2']['defstruct_sibling_remaining_bytes']} "
            f"mutations={value['mutation_count']}"
        )
        return 0
    except (
        FreightError, V110.PerformanceError, V111.LocalityError,
        COMFORT.ComfortError, PARITY.ParityError, TIER.ProductTierError,
        OSError, ValueError, KeyError, TypeError,
    ) as error:
        print(f"c2-v112-release-freight: FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
