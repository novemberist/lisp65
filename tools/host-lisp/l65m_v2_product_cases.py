#!/usr/bin/env python3
"""Validate the approved L65M-v2 product inputs and emit a native C fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

import block_bank_delta_policy as BANK_DELTA
import workbench_product_reproducibility as REPRO
import r3_product_reproducibility as R3_REPRO


ROOT = Path(__file__).resolve().parents[2]
IMPLEMENTATION = ROOT / "config/directory-only-l65m-v2-implementation.json"
INTERLIBRARY = ROOT / "config/directory-only-interlibrary-api.json"
LIBDIR = ROOT / "build/bytecode/dialect-v2/libs"
RESIDENT_PREFIX = ROOT / "build/bytecode/dialect-v2/workbench/stdlib-p0"
R3_CONTRACT = ROOT / "config/r3-g3-g6-contract.json"


class ProductCaseError(RuntimeError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ProductCaseError(f"{path} must contain an object")
    return value


def bound_path(value: object, label: str) -> Path:
    if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
        raise ProductCaseError(f"{label}: binding schema drift")
    raw = value["path"]
    if not isinstance(raw, str):
        raise ProductCaseError(f"{label}: path must be a string")
    relative = PurePosixPath(raw)
    path = ROOT / raw
    if (
        relative.is_absolute() or relative.as_posix() != raw or ".." in relative.parts
        or path.is_symlink() or not path.is_file()
        or value["sha256"] != sha(path.read_bytes())
    ):
        raise ProductCaseError(f"{label}: SHA binding drift")
    return path


def generated_path(value: object, label: str) -> Path:
    if (
        not isinstance(value, dict)
        or value != {
            "path": value.get("path"),
            "binding": "generated-output-sealed-by-r4",
        }
    ):
        raise ProductCaseError(f"{label}: generated binding schema drift")
    raw = value["path"]
    if not isinstance(raw, str):
        raise ProductCaseError(f"{label}: path must be a string")
    relative = PurePosixPath(raw)
    if relative.is_absolute() or relative.as_posix() != raw or ".." in relative.parts:
        raise ProductCaseError(f"{label}: path must be canonical")
    path = ROOT / relative
    if path.is_symlink() or not path.is_file():
        raise ProductCaseError(f"{label}: generated output is absent")
    return path


def validate_product_link(policy: dict) -> dict:
    budget = policy.get("budget_projection", {})
    actual = policy.get("actual_product_link", {})
    authorization = budget.get("authorization")
    report_binding = actual.get("report")
    bound_path(authorization, "bank authorization")
    report = load(bound_path(report_binding, "product-link report"))
    bank_delta = {
        "baseline_product_sha256": actual.get("baseline_product_sha256"),
        "candidate_product_sha256": actual.get("candidate_product_sha256"),
        "baseline_banked_headroom_bytes": report.get("baseline", {}).get("banked_headroom_bytes"),
        "candidate_banked_headroom_bytes": actual.get("banked_headroom_bytes"),
        "delta_bytes": -actual.get("measured_bank0_debit_bytes", 0),
        "authorization": authorization,
    }
    try:
        BANK_DELTA.validate_bank_delta(bank_delta)
    except BANK_DELTA.BankDeltaError as exc:
        raise ProductCaseError(f"product-link bank delta drift: {exc}") from exc
    candidate = report.get("candidate", {})
    resident_delta = report.get("resident_delta", {})
    if (
        report.get("format") != "lisp65-directory-only-l65m-v2-product-link-report-v1"
        or report.get("status") != "measured-awaiting-bank-authorization-binding"
        or report.get("baseline", {}).get("product_sha256") != bank_delta["baseline_product_sha256"]
        or candidate.get("product_sha256") != bank_delta["candidate_product_sha256"]
        or candidate.get("banked_headroom_bytes") != 269
        or candidate.get("post_boot_reserve_bytes") != 1805
        or candidate.get("boot_stack_gap_bytes") != 1585
        or resident_delta.get("total_bytes") != 166
        or sum(resident_delta.get(key, -1000) for key in ("text_bytes", "rodata_bytes", "bss_bytes")) != 166
        or report.get("composition") != {
            "free_symbols": 127,
            "free_namepool_bytes": 2279,
            "post_align_directory_slots": 32,
            "ext_post_headroom_bytes": 16384,
            "ext_contract_floor_bytes": 16384,
            "result": "pass",
        }
        or report.get("verification", {}).get("known_opens") != 0
    ):
        raise ProductCaseError("product-link report identity/measurement drift")
    role_ids = {
        "linked-product-elf": "product-elf",
        "resident-prg": "resident-prg",
        "runtime-overlays": "runtime-overlays",
        "stdlib-preload": "stdlib-preload",
    }
    aggregate_rows = []
    observed_roles = []
    for row in candidate.get("artifacts", []):
        if not isinstance(row, dict) or set(row) != {"role", "build_path", "sha256"}:
            raise ProductCaseError("product artifact inventory schema drift")
        raw_path = row["build_path"]
        relative = PurePosixPath(raw_path)
        if (
            relative.is_absolute() or relative.as_posix() != raw_path or ".." in relative.parts
            or not isinstance(row["sha256"], str) or len(row["sha256"]) != 64
        ):
            raise ProductCaseError(f"historical product artifact binding drift: {raw_path}")
        observed_roles.append(row["role"])
        if row["role"] in role_ids:
            aggregate_rows.append(f"{role_ids[row['role']]}:{row['sha256']}\n")
    if (
        observed_roles != [
            "linked-product-elf", "resident-prg", "runtime-overlays",
            "stdlib-preload", "resolved-profile",
        ]
        or hashlib.sha256("".join(aggregate_rows).encode("ascii")).hexdigest()
        != candidate["product_sha256"]
    ):
        raise ProductCaseError("product artifact-set identity drift")
    for index, binding in enumerate(report.get("source_bindings", [])):
        if not isinstance(binding, dict) or set(binding) != {"path", "sha256"}:
            raise ProductCaseError(f"historical product source binding[{index}] schema drift")
        relative = PurePosixPath(binding["path"])
        if (
            relative.is_absolute() or relative.as_posix() != binding["path"]
            or ".." in relative.parts or not isinstance(binding["sha256"], str)
            or len(binding["sha256"]) != 64
        ):
            raise ProductCaseError(f"historical product source binding[{index}] identity drift")

    r3_contract = load(R3_CONTRACT)
    baseline = r3_contract.get("baseline_identity", {})
    transition = load(bound_path(baseline.get("transition"), "R3 identity transition"))
    reproducibility = load(
        bound_path(baseline.get("reproducibility"), "R3 reproducibility receipt")
    )
    try:
        REPRO.validate(reproducibility)
    except REPRO.ReproError as exc:
        raise ProductCaseError(f"R3 reproducibility receipt drift: {exc}") from exc
    if (
        r3_contract.get("format") != "lisp65-r3-g3-g6-contract-v1"
        or baseline.get("historical_r2_product_sha256") != candidate["product_sha256"]
        or baseline.get("r3_product_sha256") != reproducibility["product_sha256"]
        or baseline.get("banked_headroom_bytes") != 313
        or baseline.get("bank_delta_bytes") != 44
        or transition.get("historical_r2_identity", {}).get("product_sha256") != candidate["product_sha256"]
        or transition.get("r3_baseline_identity", {}).get("product_sha256") != reproducibility["product_sha256"]
        or transition.get("bank_delta", {}).get("delta_bytes") != 44
    ):
        raise ProductCaseError("R2-to-R3 live product transition drift")
    # The R3 baseline receipt is historical identity evidence.  Its recorded
    # paths describe the original build, not mutable live-tree bindings.  The
    # current product is checked separately below against its own complete
    # reproducibility receipt; revalidating old bytes through today's build
    # directory would violate the sealed-snapshot boundary.

    product_block = r3_contract.get("product_block", {})
    current_receipt_path = generated_path(product_block.get("receipt"), "R3 product receipt")
    current_receipt = load(current_receipt_path)
    full_reproducibility = load(
        generated_path(product_block.get("reproducibility"), "R3 product-set reproducibility")
    )
    try:
        R3_REPRO.validate(full_reproducibility)
    except R3_REPRO.ReproError as exc:
        raise ProductCaseError(f"R3 product-set reproducibility drift: {exc}") from exc
    if (
        current_receipt.get("format") != "lisp65-r3-product-block-receipt-v1"
        or current_receipt.get("status") != "product-implemented-g3-not-run"
        or current_receipt.get("product_identity", {}).get("artifact_set_sha256")
        != product_block.get("artifact_set_sha256")
        or full_reproducibility.get("artifact_set_sha256")
        != product_block.get("artifact_set_sha256")
        or full_reproducibility.get("product_receipt_sha256")
        != sha(current_receipt_path.read_bytes())
    ):
        raise ProductCaseError("R3 current product receipt/reproducibility parity drift")
    current_rows = [
        row for group in ("core", "libraries")
        for row in current_receipt.get("artifacts", {}).get(group, [])
    ]
    if len(current_rows) != 8:
        raise ProductCaseError("R3 current core/library inventory drift")
    for row in current_rows:
        path = ROOT / row["path"]
        if (
            path.is_symlink() or not path.is_file()
            or path.stat().st_size != row["bytes"]
            or sha(path.read_bytes()) != row["sha256"]
        ):
            raise ProductCaseError(f"R3 current product artifact drift: {row['path']}")
    return report


def bytes_initializer(data: bytes) -> str:
    return "\n".join(
        "    " + ", ".join(f"0x{byte:02x}" for byte in data[pos:pos + 12]) + ","
        for pos in range(0, len(data), 12)
    )


def collect() -> tuple[dict, list[dict]]:
    policy = load(IMPLEMENTATION)
    interlibrary = load(INTERLIBRARY)
    if (
        policy.get("format") != "lisp65-directory-only-l65m-v2-implementation-v1"
        or policy.get("status") != "implemented-product-link-authorized-awaiting-promotion"
        or policy.get("budget_projection", {}).get("projected_bank0_debit_ceiling_bytes") != 96
    ):
        raise ProductCaseError("implementation/budget stop contract drift")
    validate_product_link(policy)
    expected = {
        row["id"]: (row.get("materialized_caller", row["caller"]), row["target"], sorted(row["routes"]))
        for row in policy.get("designator_matrix", [])
    }
    if len(expected) != 4 or any(routes != ["apply", "direct", "funcall"] for _, _, routes in expected.values()):
        raise ProductCaseError("four-site designator matrix drift")
    resident_image = RESIDENT_PREFIX.with_suffix(".ext.bin").read_bytes()
    resident_manifest = load(RESIDENT_PREFIX.with_suffix(".manifest.json"))
    if (
        resident_manifest.get("external_image", {}).get("sha256")
        != sha(resident_image)
        or resident_manifest.get("external_image", {}).get("bytes")
        != len(resident_image)
    ):
        raise ProductCaseError("resident closure container/manifest SHA drift")
    libraries = [{
        "name": "resident",
        "data": resident_image,
        "sha256": sha(resident_image),
        "entries": len(resident_manifest.get("entries", [])),
        "patches": len(resident_manifest.get("literal_patches", [])),
        "anonymous": 0,
        "entry_refs": 0,
    }]
    observed_sites = {}
    manifests = {}
    for library in ("ide", "idex"):
        image_path = LIBDIR / f"{library}.ext.bin"
        manifest_path = LIBDIR / f"{library}.manifest.json"
        map_path = LIBDIR / f"{library}.diagnostic-map.json"
        image, manifest, diagnostic = image_path.read_bytes(), load(manifest_path), load(map_path)
        manifests[library] = manifest
        directory_only = manifest.get("directory_only", {})
        if (
            manifest.get("external_image", {}).get("metadata_format", {}).get("version") != 2
            or directory_only.get("container_sha256") != sha(image)
            or directory_only.get("diagnostic_map_sha256") != sha(map_path.read_bytes())
            or diagnostic.get("artifact_sha256") != sha(image)
        ):
            raise ProductCaseError(f"{library}: container/map SHA binding drift")
        map_entries = diagnostic.get("entries")
        if (
            not isinstance(map_entries, list)
            or len(map_entries) != directory_only.get("anonymous_entries")
            or any(
                not isinstance(entry.get("source_path"), str)
                or not (ROOT / entry["source_path"]).is_file()
                or not isinstance(entry.get("helper_name"), str)
                or not isinstance(entry.get("code_sha256"), str)
                or len(entry["code_sha256"]) != 64
                for entry in map_entries
            )
        ):
            raise ProductCaseError(f"{library}: diagnostic map coverage/source drift")
        ordinals = {entry["name"]: ordinal for ordinal, entry in enumerate(manifest["entries"])}
        for ref in directory_only.get("entry_refs", []):
            pair = (ref["caller"], ref["target"])
            for site_id, (caller, target, _routes) in expected.items():
                if pair == (caller, target):
                    if site_id in observed_sites:
                        raise ProductCaseError(f"{site_id}: duplicate designator site")
                    observed_sites[site_id] = {
                        "id": site_id,
                        "caller_ordinal": ordinals[caller],
                        "target_ordinal": int(ref["target_ordinal"]),
                        "literal_slot": int(ref["literal_slot"]),
                    }
        libraries.append({
            "name": library,
            "data": image,
            "sha256": sha(image),
            "entries": len(manifest["entries"]),
            "patches": len(manifest["literal_patches"]),
            "anonymous": int(directory_only["anonymous_entries"]),
            "entry_refs": int(directory_only["entry_ref_nodes"]),
        })
    if set(observed_sites) != set(expected):
        raise ProductCaseError(f"designator site coverage drift: {sorted(observed_sites)}")
    entry_names = {
        library: {entry["name"] for entry in manifests[library]["entries"]}
        for library in ("ide", "idex")
    }
    anonymous = {
        library: {entry["name"] for entry in manifests[library]["entries"] if entry.get("anonymous")}
        for library in ("ide", "idex")
    }
    contract_api = {entry.get("name") for entry in interlibrary.get("entries", [])}
    late_bound = set(interlibrary.get("late_bound_exports", []))
    cross = {
        node.get("name") for node in manifests["idex"].get("literal_nodes", [])
        if node.get("kind") == 4 and node.get("name") in contract_api
    }
    declared_overrides = set(manifests["idex"].get("override_exports", []))
    observed_api = cross | declared_overrides
    definition_overlap = entry_names["ide"] & entry_names["idex"]
    hook_audit = interlibrary.get("hook_audit", {})
    entry_ref_targets = {
        library: {
            ref.get("target")
            for ref in manifests[library].get("directory_only", {}).get("entry_refs", [])
        }
        for library in ("ide", "idex")
    }
    anonymous_exports = {
        library: anonymous[library] & set(manifests[library].get("exports", []))
        for library in ("ide", "idex")
    }
    if (
        interlibrary.get("format") != "lisp65-directory-only-interlibrary-api-v1"
        or len(contract_api) != 11 or observed_api != contract_api
        or not contract_api <= set(manifests["ide"].get("exports", []))
        or any(anonymous_exports.values())
        or declared_overrides != late_bound
        or set(manifests["ide"].get("late_bound_exports", [])) != late_bound
        or set(manifests["idex"].get("late_bound_exports", [])) != late_bound
        or any(entry_ref_targets[library] & late_bound for library in ("ide", "idex"))
        or definition_overlap != declared_overrides
        or hook_audit.get("definition_overlap") != sorted(definition_overlap)
        or hook_audit.get("declared_override_exports") != sorted(declared_overrides)
        or hook_audit.get("undeclared_hooks") != []
    ):
        raise ProductCaseError("inter-library export/override classification drift")
    return policy, [*libraries, {"sites": [observed_sites[key] for key in sorted(observed_sites)]}]


def emit(path: Path) -> None:
    _policy, records = collect()
    libraries, sites = records[:-1], records[-1]["sites"]
    lines = [
        "/* generated by tools/host-lisp/l65m_v2_product_cases.py; do not edit */",
        "#ifndef LISP65_L65M_V2_PRODUCT_CASES_H",
        "#define LISP65_L65M_V2_PRODUCT_CASES_H",
        "#include <stdint.h>",
        "typedef struct { const char *id; uint16_t caller_ordinal, target_ordinal; uint8_t literal_slot; } l65m_v2_designator_site;",
    ]
    for library in libraries:
        lines.extend([
            f"static const uint8_t l65m_v2_{library['name']}_data[] = {{",
            bytes_initializer(library["data"]),
            "};",
            f"#define L65M_V2_{library['name'].upper()}_SHA256 \"{library['sha256']}\"",
            f"#define L65M_V2_{library['name'].upper()}_ENTRIES {library['entries']}u",
            f"#define L65M_V2_{library['name'].upper()}_PATCHES {library['patches']}u",
            f"#define L65M_V2_{library['name'].upper()}_ANONYMOUS {library['anonymous']}u",
            f"#define L65M_V2_{library['name'].upper()}_ENTRY_REFS {library['entry_refs']}u",
        ])
    lines.append("static const l65m_v2_designator_site l65m_v2_designator_sites[] = {")
    for site in sites:
        lines.append(
            f"    {{ \"{site['id']}\", {site['caller_ordinal']}u, {site['target_ordinal']}u, {site['literal_slot']}u }},"
        )
    lines.extend([
        "};",
        "#define L65M_V2_DESIGNATOR_SITE_COUNT 4u",
        "#endif",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="ascii")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emit-c-header", type=Path)
    args = parser.parse_args()
    try:
        _policy, records = collect()
        if args.emit_c_header:
            emit(args.emit_c_header)
        sites = records[-1]["sites"]
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, ProductCaseError) as exc:
        print(f"l65m-v2-product-cases: FAIL: {exc}")
        return 1
    print(f"l65m-v2-product-cases: PASS libraries={len(records) - 1} designator_sites={len(sites)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
