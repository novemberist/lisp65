#!/usr/bin/env python3
"""Enumerate every medium-producing source and close active packed gates."""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
SCRIPTS = ROOT / "scripts"
MK = ROOT / "mk"
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
REPAIR = ARCH / (
    "c2.3-v2.1-loading-libraries-progress-media-repair-receipt.json")
BREADCRUMB = ARCH / (
    "c2.3-v2.1-loading-libraries-stage-breadcrumb-media-receipt.json")
RECEIPT = ARCH / "c2.3-media-builder-closure-enumeration-receipt.json"
PREDECESSOR_RECEIPT = RECEIPT
RECEIPT = ARCH / "c2.3-media-builder-closure-enumeration-v3-receipt.json"
# The v1.5 public product driver joined the medium builders in phase E.  The
# population moved, so the enumeration mints its successor rather than
# rewriting the record its predecessors left.
PREDECESSOR_RECEIPT = RECEIPT
RECEIPT = ARCH / "c2.3-media-builder-closure-enumeration-v4-receipt.json"
PREDECESSOR_RECEIPT = RECEIPT
RECEIPT = ARCH / "c2.3-media-builder-closure-enumeration-v5-receipt.json"
PREDECESSOR_RECEIPT = RECEIPT
RECEIPT = ARCH / "c2.3-media-builder-closure-enumeration-v6-receipt.json"
PREDECESSOR_RECEIPT = RECEIPT
RECEIPT = ARCH / "c2.3-media-builder-closure-enumeration-v7-receipt.json"
PREDECESSOR_RECEIPT = RECEIPT
RECEIPT = ARCH / "c2.3-media-builder-closure-enumeration-v8-receipt.json"
PREDECESSOR_RECEIPT = RECEIPT
RECEIPT = ARCH / "c2.3-media-builder-closure-enumeration-v9-receipt.json"
PREDECESSOR_RECEIPT = RECEIPT
RECEIPT = ARCH / "c2.3-media-builder-closure-enumeration-v10-receipt.json"
PREDECESSOR_RECEIPT = RECEIPT
RECEIPT = ARCH / "c2.3-media-builder-closure-enumeration-v11-receipt.json"
BANK4 = ARCH / "c2.3-v2.1-bank4-map-probe-receipt.json"
DEVICE_PREPARATION = ARCH / (
    "c2.3-v1.6-item1-only-media-r1-public2-receipt.json")
FORMAT = "lisp65-c2.3-media-builder-closure-enumeration-v11"
SELF = "tools/host-lisp/c2_media_builder_closure_enumeration.py"

# The registry is deliberately explicit.  Discovery below is independent of
# this set and makes either a newly added builder or a stale registry fail
# check-source.  Non-current sources remain usable as historical evidence or
# developer fixtures, but they cannot become a qualified product producer
# without an explicit reclassification and packed-artifact closure.
REGISTERED = {
    "tools/host-lisp/c2_defstruct_foundations_gate.py",
    "tools/host-lisp/c2_defstruct_product_identity_rebind.py",
    "tools/host-lisp/c2_defstruct_session_record_identity_rebind.py",
    "tools/host-lisp/c2_defstruct_terminal_ingress_sister.py",
    "tools/host-lisp/c2_link75_library_media_successor.py",
    "tools/host-lisp/c2_v150_public_product.py",
    "tools/host-lisp/c2_link95_acceptance_media.py",
    "tools/host-lisp/c2_link95_world_bound_media.py",
    "tools/host-lisp/c2_lite_media_g5_entry_repack.py",
    "tools/host-lisp/c2_lite_media_g5_handoff_completion_repack.py",
    "tools/host-lisp/c2_lite_media_g5_hybrid_dma_repack.py",
    "tools/host-lisp/c2_lite_media_g5_io_trigger_attribution.py",
    "tools/host-lisp/c2_lite_media_g5_normal_dma_repack.py",
    "tools/host-lisp/c2_lite_media_g5_rom_write_repack.py",
    "tools/host-lisp/c2_lite_media_g5_write_only_diagnostic.py",
    "tools/host-lisp/c2_lite_media_product.py",
    "tools/host-lisp/c2_require_prior_append_option_a_gate.py",
    "tools/host-lisp/c2_require_resolver_gate.py",
    "tools/host-lisp/c2_terminal_return_guard_media.py",
    "tools/host-lisp/c2_top_level_macro_redispatch_link94_media.py",
    "tools/host-lisp/c2_v112_candidate_media.py",
    "tools/host-lisp/c2_v121_candidate_media.py",
    "tools/host-lisp/c2_v122_candidate_media.py",
    "tools/host-lisp/c2_v122_link78_d1_d2_hw.py",
    "tools/host-lisp/c2_v123_candidate_media.py",
    "tools/host-lisp/c2_v124_candidate_media.py",
    "tools/host-lisp/c2_v124_require_prior_append_h1.py",
    "tools/host-lisp/c2_v125_candidate_media.py",
    "tools/host-lisp/c2_v126_candidate_media.py",
    "tools/host-lisp/c2_v126_editor_option2_medium.py",
    "tools/host-lisp/c2_v13_candidate_media.py",
    "tools/host-lisp/c2_v13_link85_candidate_media.py",
    "tools/host-lisp/c2_v13_link86_candidate_media.py",
    "tools/host-lisp/c2_v13_link87_candidate_media.py",
    "tools/host-lisp/c2_v13_link88_candidate_media.py",
    "tools/host-lisp/c2_v14_link90_candidate_media.py",
    "tools/host-lisp/c2_v14_parity_pilot_candidate_media.py",
    "tools/host-lisp/c2_v150_candidate_media.py",
    "tools/host-lisp/c2_v150_name_freight_media.py",
    "tools/host-lisp/c2_v150_stager_liveness_successor.py",
    "tools/host-lisp/c2_v160_items12_device_preparation.py",
    "tools/host-lisp/c2_v160_boot_refill_selector_bypass_media.py",
    "tools/host-lisp/c2_v160_clean_product_acceptance_media.py",
    "tools/host-lisp/c2_v160_clean_product_operand_root_media.py",
    "tools/host-lisp/c2_v160_item1_only_media.py",
    "tools/host-lisp/c2_v20_crc_carveout_media.py",
    "tools/host-lisp/c2_v20_crc_carveout_media_liveness.py",
    "tools/host-lisp/c2_v20_far_payload_delivery.py",
    "tools/host-lisp/c2_v20_loading_libraries_progress_ring.py",
    "tools/host-lisp/c2_v20_map_cpu_transport_probe.py",
    "tools/host-lisp/c2_v21_loading_libraries_progress_media_repair.py",
    "tools/host-lisp/c2_v21_loading_libraries_stage_breadcrumb_media.py",
    "tools/host-lisp/c2_v21_bank4_map_probe.py",
    "tools/host-lisp/project_doctor.py",
    "tools/host-lisp/r3_product_block.py",
    "tools/host-lisp/r3_stager_probe.py",
    "tools/host-lisp/r5_global_g5.py",
    "tools/host-lisp/r5_workbench_test_media.py",
    "tools/host-lisp/ship_builder.py",
    "scripts/build-bytecode-lib-d81.sh",
    "scripts/build-demo-suite-d81.sh",
    "scripts/build-f011-autoload-image.sh",
    "scripts/build-f011-defd81-image.sh",
    "scripts/build-interim-ship.sh",
    "scripts/build-s5-source-d81.sh",
    "scripts/build-stdlib-d81.sh",
    "scripts/build-workbench-d81.sh",
    "scripts/hw-b4-workflow.sh",
    "scripts/hw-disk-roundtrip.sh",
    "scripts/hw-runtime-export-reemit.sh",
    "scripts/hw-workbench-save-new-smoke.sh",
    "mk/workbench.mk",
}
CURRENT = {
    "tools/host-lisp/c2_v20_far_payload_delivery.py":
        "registered packed-artifact registry in delivered media closure",
    "tools/host-lisp/c2_v21_loading_libraries_progress_media_repair.py":
        "close_packed_artifacts over actual stager ELF and D81",
    "tools/host-lisp/c2_v21_loading_libraries_stage_breadcrumb_media.py":
        "non-promotable trace stager plus closed same-product D81",
    "tools/host-lisp/c2_v21_bank4_map_probe.py":
        "non-promotable Bank-4 MAP probe plus closed same-world D81",
    "tools/host-lisp/c2_v160_item1_only_media.py":
        "one-row item-1 product media with packed-artifact closure",
}


class EnumerationError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise EnumerationError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def _python_reasons(source: str, label: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        raise EnumerationError(f"media-builder AST red: {label}: {error}") from error
    calls = [ast.unparse(call.func) for call in ast.walk(tree)
             if isinstance(call, ast.Call)]
    reasons = []
    if "MEDIA.build" in calls:
        reasons.append("canonical-product-build")
    if "MEDIA.compile_stager" in calls:
        reasons.append("stager-build")
    if any(call == "build_d81" or call.endswith(".build_d81")
           for call in calls):
        reasons.append("d81-builder-call")
    for function in (node for node in tree.body
                     if isinstance(node, (ast.FunctionDef,
                                          ast.AsyncFunctionDef))):
        strings = {node.value for node in ast.walk(function)
                   if isinstance(node, ast.Constant)
                   and isinstance(node.value, str)}
        names = {node.id.lower() for node in ast.walk(function)
                 if isinstance(node, ast.Name)}
        attrs = {node.attr.lower() for node in ast.walk(function)
                 if isinstance(node, ast.Attribute)}
        mentions_c1541 = ("c1541" in names or "c1541" in attrs
                          or any("c1541" in value.lower()
                                 for value in strings))
        if mentions_c1541 and "-write" in strings:
            reasons.append("direct-medium-write")
        if mentions_c1541 and "-format" in strings and "d81" in strings:
            reasons.append("direct-d81-format")
    return sorted(set(reasons))


def _text_reasons(source: str, kind: str) -> list[str]:
    lower = source.lower()
    if "c1541" not in lower:
        return []
    if re.search(r"(?<![A-Za-z0-9_-])-(?:format|write|delete)\b",
                 source) is None:
        return []
    return [kind]


def discover(overrides: dict[str, str] | None = None) -> dict[str, list[str]]:
    overrides = overrides or {}
    candidates = ({path.relative_to(ROOT).as_posix()
                   for path in HOST.glob("*.py")}
                  | {path.relative_to(ROOT).as_posix()
                     for path in SCRIPTS.iterdir()
                     if path.is_file() and path.suffix in (".py", ".sh")}
                  | {path.relative_to(ROOT).as_posix()
                     for path in MK.glob("*.mk")}
                  | set(overrides))
    found: dict[str, list[str]] = {}
    for relative in sorted(candidates):
        if relative == SELF:
            continue
        path = ROOT / relative
        source = overrides.get(relative)
        if source is None:
            require(path.is_file() and not path.is_symlink(),
                    f"media-builder candidate absent: {relative}")
            source = path.read_text(encoding="utf-8")
        if relative.startswith("tools/host-lisp/") and relative.endswith(".py"):
            reasons = _python_reasons(source, relative)
        elif relative.startswith("scripts/"):
            reasons = _text_reasons(source, "script-medium-mutation")
        elif relative.startswith("mk/"):
            reasons = _text_reasons(source, "make-medium-mutation")
        else:
            reasons = []
        if reasons:
            found[relative] = reasons
    return found


def domain(path: str) -> str:
    if path in CURRENT:
        return "current-qualified-product-or-diagnostic"
    if path.startswith("scripts/"):
        return "nonshipping-developer-or-hardware-utility"
    if path.startswith("mk/"):
        return "nonshipping-make-selftest-fixture"
    name = Path(path).name
    if name in {"project_doctor.py", "r3_product_block.py",
                "r3_stager_probe.py", "r5_global_g5.py",
                "r5_workbench_test_media.py", "ship_builder.py"}:
        return "legacy-or-toolchain-fixture"
    if any(token in name for token in
           ("library", "require", "foundations", "identity_rebind")):
        return "sealed-library-or-reconstruction-fixture"
    return "sealed-c2-product-or-diagnostic-evidence"


def active_closure() -> dict[str, Any]:
    repair = load(REPAIR)
    breadcrumb = load(BREADCRUMB)
    repaired = repair.get("packed_artifact_gate_registry", {})
    traced = breadcrumb.get("packed_artifact_gate_registry", {})
    bank4 = load(BANK4).get("media", {}).get(
        "packed_artifact_closure", {})
    device = load(DEVICE_PREPARATION).get("packed_artifact_closure", {})
    far_source = (HOST / "c2_v20_far_payload_delivery.py").read_text(
        encoding="utf-8")
    repair_source = (HOST /
        "c2_v21_loading_libraries_progress_media_repair.py").read_text(
        encoding="utf-8")
    breadcrumb_source = (HOST /
        "c2_v21_loading_libraries_stage_breadcrumb_media.py").read_text(
        encoding="utf-8")
    device_source = (HOST /
        "c2_v160_item1_only_media.py").read_text(encoding="utf-8")
    require(
        "PACKED_ARTIFACT_GATES" in far_source
        and "run_packed_artifact_gates()" in far_source
        and '"complete": True' in far_source
        and "MEDIA.close_packed_artifacts(" in repair_source
        and "compile_defines=(LIVE.OPT_IN,)" in repair_source
        and repaired.get("complete") is True
        and repaired.get("registered") == repaired.get("executed") ==
            ["autoboot.c65.elf", "diagnostic-product.d81"]
        and "MEDIA.close_packed_artifacts(" in breadcrumb_source
        and "LIVE.OPT_IN, TRACE_OPT_IN" in breadcrumb_source
        and traced.get("complete") is True
        and traced.get("registered") == traced.get("executed") ==
            ["autoboot.c65.elf", "diagnostic-product.d81"]
        and bank4.get("complete") is True
        and bank4.get("registered") == bank4.get("executed") ==
            ["autoboot.c65.elf", "b4map.d81"]
        and "MEDIA.build()" in device_source
        and device.get("artifact_count") == 19
        and device.get("stager_gate", {}).get("status") ==
            "passed-strict-build-and-address-qualified-hybrid-f018b-content-defined-target-readback",
        "active medium builder omits registered packed-artifact gates")
    return {"current": dict(sorted(CURRENT.items())),
            "repair_registry": repaired,
            "breadcrumb_registry": traced,
            "bank4_registry": bank4,
            "device_preparation_registry": device}


def derive() -> dict[str, Any]:
    observed = discover()
    require(set(observed) == REGISTERED,
            "medium builder exists outside structural enumeration: "
            + ", ".join(sorted(set(observed) ^ REGISTERED)))
    domains: dict[str, list[str]] = {}
    for path in sorted(observed):
        domains.setdefault(domain(path), []).append(path)
    value = {
        "format": FORMAT,
        "recorded_on": "2026-08-24",
        "status": "PASS: EVERY MEDIUM BUILDER IN TREE ENUMERATED",
        "builders": {
            "total": len(observed),
            "current_gate_closed": sorted(CURRENT),
            "registered_noncurrent": sorted(REGISTERED - set(CURRENT)),
            "observed": observed,
            "domains": dict(sorted(domains.items())),
        },
        "active_closure": active_closure(),
        "rule": (
            "Every Python, shell, and Make medium producer is structurally "
            "enumerated. Current product/diagnostic producers run every "
            "registered packed-artifact gate inside the closure that ships "
            "their output. A noncurrent producer cannot become current "
            "without explicit reclassification and the same closure."),
        "claim_limit": (
            "Static producer inventory covers host Python calls through the "
            "canonical builders or c1541, shell c1541 mutations, and Make "
            "c1541 mutations. Read-only media consumers are not producers."),
    }
    value["mutations"] = mutations(value)
    audit(value)
    return value


def audit(value: dict[str, Any]) -> None:
    builders = value.get("builders", {})
    observed = builders.get("observed", {})
    domain_members = {
        member for members in builders.get("domains", {}).values()
        for member in members
    }
    require(
        value.get("status") == "PASS: EVERY MEDIUM BUILDER IN TREE ENUMERATED"
        and builders.get("total") == len(REGISTERED)
        and set(observed) == REGISTERED
        and set(builders.get("current_gate_closed", [])) == set(CURRENT)
        and set(builders.get("registered_noncurrent", [])) ==
            REGISTERED - set(CURRENT)
        and domain_members == REGISTERED
        and value.get("active_closure", {}).get("repair_registry", {})
            .get("complete") is True
        and value.get("active_closure", {}).get("breadcrumb_registry", {})
            .get("complete") is True
        and value.get("active_closure", {}).get("bank4_registry", {})
            .get("complete") is True
        and value.get("active_closure", {}).get(
            "device_preparation_registry", {}).get("artifact_count") == 19,
        "media-builder structural enumeration drift")


def mutations(base: dict[str, Any]) -> list[str]:
    rejected = []
    synthetic = {"tools/host-lisp/c2_unregistered_media_builder.py":
        "def build():\n    return MEDIA.compile_stager(1, [])\n"}
    try:
        require(set(discover(synthetic)) == REGISTERED,
                "unregistered builder rejected")
    except EnumerationError:
        rejected.append("builder-outside-enumeration")
    for name, mutate in (
        ("drop-enumerated-builder", lambda x: x["builders"]
            ["observed"].pop(next(iter(x["builders"]["observed"])))),
        ("drop-current-builder", lambda x: x["builders"]
            ["current_gate_closed"].pop()),
        ("incomplete-active-registry", lambda x: x["active_closure"]
            ["repair_registry"].update(complete=False)),
        ("incomplete-breadcrumb-registry", lambda x: x["active_closure"]
            ["breadcrumb_registry"].update(complete=False)),
        ("incomplete-bank4-registry", lambda x: x["active_closure"]
            ["bank4_registry"].update(complete=False)),
        ("incomplete-device-preparation-registry", lambda x: x["active_closure"]
            ["device_preparation_registry"].update(artifact_count=0)),
        ("promote-noncurrent-without-gates", lambda x: x["builders"]
            ["current_gate_closed"].append(
                x["builders"]["registered_noncurrent"][0])),
        ("unclassified-builder", lambda x: next(iter(x["builders"]
            ["domains"].values())).pop()),
    ):
        trial = deepcopy(base)
        mutate(trial)
        try:
            audit(trial)
        except EnumerationError:
            rejected.append(name)
    require(len(rejected) == 9,
            "media-builder enumeration mutation survived")
    return sorted(rejected)


def record() -> dict[str, Any]:
    require(not RECEIPT.exists(), "media-builder enumeration receipt exists")
    value = derive()
    RECEIPT.write_bytes(canonical(value))
    return value


def check() -> dict[str, Any]:
    value = load(RECEIPT)
    audit(value)
    require(value == derive() and value["active_closure"]["repair_registry"] ==
            load(REPAIR)["packed_artifact_gate_registry"]
            and value["active_closure"]["breadcrumb_registry"] ==
                load(BREADCRUMB)["packed_artifact_gate_registry"]
            and value["active_closure"]["bank4_registry"] ==
                load(BANK4)["media"]["packed_artifact_closure"]
            and value["active_closure"]["device_preparation_registry"] ==
                load(DEVICE_PREPARATION)["packed_artifact_closure"],
            "media-builder enumeration reconstruction drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("record", "check", "selftest"))
    args = parser.parse_args()
    value = record() if args.action == "record" else (
        check() if args.action == "check" else derive())
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EnumerationError, OSError, KeyError, ValueError) as error:
        print(f"MEDIA BUILDER ENUMERATION: {error}", file=sys.stderr)
        raise SystemExit(1)
