#!/usr/bin/env python3
"""Price the two v2.0 release shapes after the final Block-3 descope.

This is a host-only decision card.  It compares the qualified Tier-1 world
with the final Block-3 repair world, derives every freight member from the
packed manifests, proves whether the latter is actually dormant from the
packed call graph, and checks the stripped editor hot path against the
hardware-green v1.9 release emission.  It never invokes WPLTO or a linker.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_packed_medium_transitive_closure as CLOSURE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CLEAN_ROOT = ROOT / (
    "build/c2.3/v2.0-domain-tier1-product-card-r1-preflight/"
    "setup-owned/static-plane/narrow-static")
CURRENT_ROOT = ROOT / (
    "build/c2.3/v2.0-block3-hot-path-repair-card-r1-preflight/"
    "setup-owned/static-plane/narrow-static")
V19_ROOT = ROOT / (
    "build/c2.3/v1.9.0-release-card-r1-preflight/"
    "setup-owned/static-plane/narrow-static")
CLEAN_PRODUCT = CLEAN_ROOT / "product/substitution-artifacts.json"
CURRENT_PRODUCT = CURRENT_ROOT / "product/substitution-artifacts.json"
V19_STDLIB = V19_ROOT / "stdlib-p0.manifest.json"
CLEAN_RECEIPT = ARCH / (
    "c2.3-v2.0-domain-tier1-product-card-r1-receipt.json")
CURRENT_RECEIPT = ARCH / (
    "c2.3-v2.0-block3-hot-path-repair-card-r1-receipt.json")
DEVICE_RECEIPT = ARCH / (
    "c2.3-v2.0-block3-hot-path-repair-device-result-receipt.json")
RECEIPT = ARCH / "c2.3-v2.0-release-shape-pricing-receipt.json"
REPORT = ROOT / "docs/planning/v2.0.0-release-shape-decision-card.md"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
AUTHORITY_COMMIT = "3c88d046"
AUTHORITY_HEADER = (
    "## Reviewer ratification — Block 3 finally descoped; "
    "two divergences sealed — 2026-09-02")
RESULT_HEADER = "## Release-shape decision card — 2026-09-02"
FORMAT = "lisp65-c2-v200-release-shape-pricing-v1"
STATUS = "PASS: V2.0 RELEASE SHAPES PRICED; OWNER DECISION REQUIRED"
PRODUCT_KEYS = ("stdlib-p0", "ide", "idex", "m65d", "buffer", "lcc")

HOT_PATH = (
    "%native-prompt", "%native-read-line", "%read-line-loop",
    "%rl-render", "%rl-cut", "%rl-move", "%rl-put", "%rl-dispatch",
    "%rl-screen-tail", "read-line")
ACTIVE_BLOCK3_EDGES = (
    ("%read-line-loop", "CALL", "%rl-poll"),
    ("%rl-poll", "TAILCALL", "%rl-clear"),
    ("%rl-clear", "CALL", "%rl-idle"),
    ("%rl-clear", "CALL", "%cursor-blink"),
    ("%rl-idle", "TAILCALL", "%sexp-scan"),
    ("%rl-idle", "TAILCALL", "%sexp-close"),
    ("%rl-idle", "TAILCALL", "%sexp-open"),
    ("%rl-idle", "TAILCALL", "%sexp-paint"),
)


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


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


def resolve(path_text: str, owner: Path) -> Path:
    path = Path(path_text)
    candidates = [path] if path.is_absolute() else [ROOT / path, owner.parent / path]
    found = [candidate for candidate in candidates if candidate.is_file()]
    require(len(found) == 1, f"artifact path is not unique: {path_text}")
    return found[0]


def authority() -> dict[str, Any]:
    relative = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{AUTHORITY_COMMIT}:{relative}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = raw.decode("utf-8")
    require(text.count(AUTHORITY_HEADER) == 1,
            "release-shape commission identity drift")
    section = AUTHORITY_HEADER + text.split(AUTHORITY_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    folded = " ".join(section.lower().replace("`", "").replace("*", "").split())
    for token in ("release-shape decision needed", "strip it (one link",
                  "ship it dormant and documented", "actual strip cost"):
        require(token in folded, f"release-shape commission token absent: {token}")
    payload = section.encode()
    return {"commit": AUTHORITY_COMMIT, "path": relative,
            "section": AUTHORITY_HEADER, "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "right": "host-only two-shape price; no WPLTO, link, media or device"}


def product_manifests(product_path: Path) -> dict[str, Path]:
    product = load(product_path)
    rows = product.get("manifests")
    require(product.get("format") ==
            "lisp65-c2-product-substitution-artifacts-v1"
            and isinstance(rows, list) and len(rows) == len(PRODUCT_KEYS),
            "product manifest population drift")
    result: dict[str, Path] = {}
    for key, row in zip(PRODUCT_KEYS, rows):
        require(isinstance(row, dict) and isinstance(row.get("path"), str),
                f"product manifest binding absent: {key}")
        path = resolve(row["path"], product_path)
        require(bind(path) == row, f"product manifest identity drift: {key}")
        result[key] = path
    return result


def entries(manifest_path: Path) -> tuple[dict[str, dict[str, Any]], bytes]:
    manifest = load(manifest_path)
    rows = manifest.get("entries")
    require(isinstance(rows, list), f"entry inventory absent: {manifest_path}")
    selected = [row for row in rows if isinstance(row, dict)
                and row.get("kind") in {"function", "macro"}]
    by_name = {row["name"]: row for row in selected}
    require(len(by_name) == len(selected), f"duplicate object name: {manifest_path}")
    blob = resolve(manifest["blob"], manifest_path).read_bytes()
    return by_name, blob


def object_bytes(row: dict[str, Any], blob: bytes) -> bytes:
    start, length = row["blob_offset"], row["length"]
    value = blob[start:start + length]
    require(len(value) == length, f"object slice truncated: {row['name']}")
    return value


def component_delta(clean_path: Path, current_path: Path) -> dict[str, Any]:
    clean_value, current_value = load(clean_path), load(current_path)
    clean, _clean_blob = entries(clean_path)
    current, _current_blob = entries(current_path)
    added_names = sorted(current.keys() - clean.keys())
    removed_names = sorted(clean.keys() - current.keys())
    require(not removed_names, f"release-shape comparison removed objects: {removed_names}")
    added = [{"name": name, "object_bytes": current[name]["length"],
              "name_bytes_NUL_inclusive": len(name.encode()) + 1}
             for name in added_names]
    changed = [{"name": name, "before_bytes": clean[name]["length"],
                "after_bytes": current[name]["length"],
                "delta_bytes": current[name]["length"] - clean[name]["length"]}
               for name in sorted(clean.keys() & current.keys())
               if current[name]["length"] != clean[name]["length"]]
    return {"clean_manifest": bind(clean_path),
            "current_manifest": bind(current_path),
            "clean_code_bytes": clean_value["code_bytes"],
            "current_code_bytes": current_value["code_bytes"],
            "code_delta_bytes": (current_value["code_bytes"] -
                                 clean_value["code_bytes"]),
            "added": added, "removed": removed_names,
            "added_object_bytes": sum(row["object_bytes"] for row in added),
            "added_name_bytes_NUL_inclusive": sum(
                row["name_bytes_NUL_inclusive"] for row in added),
            "changed_existing": changed,
            "changed_existing_net_bytes": sum(
                row["delta_bytes"] for row in changed)}


def closure_summary(product: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    value = CLOSURE.derive(product)
    CLOSURE.require_closed(value)
    summary = {"status": value["status"],
               "object_count": value["object_count"],
               "call_site_count": value["call_site_count"],
               "duplicate_public_owners": value["duplicate_public_owners"],
               "failures": value["failures"]}
    return value, summary


def hot_path_identity(clean_manifest: Path) -> dict[str, Any]:
    released, released_blob = entries(V19_STDLIB)
    clean, clean_blob = entries(clean_manifest)
    rows = []
    for name in HOT_PATH:
        require(name in released and name in clean, f"hot-path object absent: {name}")
        before = object_bytes(released[name], released_blob)
        after = object_bytes(clean[name], clean_blob)
        rows.append({"name": name, "v1_9_bytes": len(before),
                     "stripped_bytes": len(after),
                     "byteidentical": before == after,
                     "sha256": hashlib.sha256(after).hexdigest()})
    require(all(row["byteidentical"] for row in rows),
            "stripped editor hot path differs from hardware-green v1.9")
    released_manifest = load(V19_STDLIB)
    clean_value = load(clean_manifest)
    return {"status": "PASS: STRIPPED EDITOR HOT PATH BYTEIDENTICAL TO V1.9",
            "v1_9_manifest": bind(V19_STDLIB),
            "v1_9_blob": bind(resolve(released_manifest["blob"], V19_STDLIB)),
            "stripped_manifest": bind(clean_manifest),
            "stripped_blob": bind(resolve(clean_value["blob"], clean_manifest)),
            "objects": rows}


def metrics() -> dict[str, Any]:
    clean = load(CLEAN_RECEIPT)
    current = load(CURRENT_RECEIPT)
    require(clean["status"] == "PASS: V2.0 DOMAIN TIER 1 FINAL PRODUCT GREEN"
            and current["status"] ==
                "PASS: V2.0 BLOCK-3 HOT-PATH REPAIR PRODUCT GREEN",
            "candidate receipt status drift")
    ccap = clean["final_product"]["domain_Tier_1"]["capacity"]
    d5 = current["final_product"]["D5_projection"]["after"]
    bank = current["final_product"]["composed_bank2"]
    lanes = current["final_product"]["responsiveness_lanes"]
    return {
        "clean": {"plane_bytes": ccap["static_plane_bytes"],
            "symbol_slots": ccap["symbol_slots"],
            "namepool_bytes": ccap["namepool_bytes"],
            "largest_contiguous_hole": ccap["largest_contiguous_hole"],
            "largest_object_bytes": ccap["object_ceiling"]["largest_bytes"],
            "resident_delta": ccap["resident_delta"]},
        "current": {"plane_bytes": current["final_product"]["static_extent"],
            "symbol_slots": d5["symbol_slots"],
            "namepool_bytes": d5["namepool_bytes"],
            "largest_contiguous_hole": bank["largest_contiguous_hole"]["bytes"],
            "single_key_VM_steps":
                lanes["single_keystroke"]["successor"]["vm_steps_per_character"],
            "single_key_step_ratio": lanes["single_keystroke"]["ratio"],
            "batch_margin_percent":
                lanes["batch_throughput"]["margin_percent"]}}


def derive() -> dict[str, Any]:
    clean_manifests = product_manifests(CLEAN_PRODUCT)
    current_manifests = product_manifests(CURRENT_PRODUCT)
    components = {
        key: component_delta(clean_manifests[key], current_manifests[key])
        for key in ("stdlib-p0", "ide")}
    clean_closure, clean_summary = closure_summary(CLEAN_PRODUCT)
    current_closure, current_summary = closure_summary(CURRENT_PRODUCT)
    del clean_closure
    emitted_edges = {(row["caller"], row["opcode"], row["target"])
                     for row in current_closure["call_sites"]}
    missing_edges = sorted(set(ACTIVE_BLOCK3_EDGES) - emitted_edges)
    require(not missing_edges, f"active Block-3 call edge absent: {missing_edges}")
    active_edges = [{"caller": caller, "opcode": opcode, "target": target}
                    for caller, opcode, target in ACTIVE_BLOCK3_EDGES]
    price = metrics()
    total_added = sum(len(row["added"]) for row in components.values())
    total_names = sum(row["added_name_bytes_NUL_inclusive"]
                      for row in components.values())
    total_code = sum(row["code_delta_bytes"] for row in components.values())
    require((total_added, total_names, total_code) == (38, 418, 6076),
            "release-shape freight total drift")
    require((current_summary["object_count"] - clean_summary["object_count"],
             current_summary["call_site_count"] - clean_summary["call_site_count"])
            == (38, 236), "packed topology delta drift")
    require(price["current"]["plane_bytes"] - price["clean"]["plane_bytes"]
            == total_code
            and price["clean"]["largest_contiguous_hole"] -
            price["current"]["largest_contiguous_hole"] == total_code
            and price["clean"]["symbol_slots"] -
            price["current"]["symbol_slots"] == total_added
            and price["clean"]["namepool_bytes"] -
            price["current"]["namepool_bytes"] == total_names,
            "capacity currencies do not reconcile to manifest freight")
    device = load(DEVICE_RECEIPT)
    require(device["decision"]["block3_v2_0"] == "DESCOPED"
            and device["decision"]["matcher_device_claim"] == "not accepted"
            and device["decision"]["latency_device_claim"] == "not accepted",
            "final device-red authority drift")
    return {
        "format": FORMAT, "recorded_on": "2026-09-02", "status": STATUS,
        "authority": {"review": authority(), "clean_receipt": bind(CLEAN_RECEIPT),
            "current_receipt": bind(CURRENT_RECEIPT),
            "device_red": bind(DEVICE_RECEIPT)},
        "process_accounting": {"WPLTO": 0, "product_links": 0,
            "media_builds": 0, "device_contacts": 0},
        "worlds": {"stripped_reference": {**price["clean"],
                         "ELF_sha256": load(CLEAN_RECEIPT)["artifacts_after"]["ELF"]["sha256"],
                         "PRG_sha256": load(CLEAN_RECEIPT)["artifacts_after"]["PRG"]["sha256"],
                         "closure": clean_summary},
                   "current_block3": {**price["current"],
                         "ELF_sha256": load(CURRENT_RECEIPT)["artifacts_after"]["ELF"]["sha256"],
                         "PRG_sha256": load(CURRENT_RECEIPT)["artifacts_after"]["PRG"]["sha256"],
                         "closure": current_summary}},
        "freight": {"components": components, "added_objects": total_added,
            "name_bytes_NUL_inclusive": total_names,
            "plane_bytes": total_code, "added_call_sites": 236,
            "largest_hole_cost_bytes": total_code},
        "stripped_hot_path_identity": hot_path_identity(clean_manifests["stdlib-p0"]),
        "dormancy_test": {"status": "FAIL: CURRENT FREIGHT IS ACTIVE",
            "is_dormant": False, "derived_from": bind(CURRENT_PRODUCT),
            "active_key_path": active_edges,
            "device_effect": {"matcher": "no visible mark",
                              "key_feel": "noticeably worse than v1.9"},
            "conclusion": ("the current packed world executes Block-3 freight "
                           "from the delivered read-line path; calling it dormant "
                           "would be false")},
        "options": {
            "strip": {"new_WPLTOs": 1, "new_product_links": 1,
                "target": "qualified Tier-1 object population and semantics",
                "reclaims": {"plane_bytes": total_code,
                    "symbol_slots": total_added, "namepool_bytes": total_names,
                    "largest_contiguous_hole_bytes": total_code,
                    "packed_objects": total_added, "packed_call_sites": 236},
                "keeps": ["Tier-1 domain discipline", "v1.9 Capture and native editor",
                    "$22 first-fault latch", "resident delivery-chain architecture",
                    "closure and generation-coherence gates"],
                "qualification_debt": ["full difference attribution",
                    "all authority-consumption gates", "Scope and Acceptance",
                    "packed closure and generation coherence"],
                "release_eligibility": "eligible after one green product card"},
            "keep_current_as_documented_dormant": {
                "new_WPLTOs": 0, "new_product_links": 0,
                "keeps_cost": {"plane_bytes": total_code,
                    "symbol_slots": total_added, "namepool_bytes": total_names,
                    "packed_objects": total_added, "packed_call_sites": 236},
                "dormant": False,
                "release_eligibility": ("not eligible under the standing device "
                    "no-regression rule without an explicit owner waiver"),
                "why": ["active on the delivered key path",
                    "matcher has no visible device effect",
                    "typing is noticeably worse than v1.9"],
                "true_dormant_variant": {"requires_product_change": True,
                    "minimum_new_product_links": 1,
                    "price_advantage_over_strip": "none established"}}},
        "recommendation": {"choice": "strip", "basis": [
            "only priced form that removes the device-red active path",
            "restores the ten-object v1.9 editor hot path byte-for-byte",
            "reclaims all 6076 Plane bytes and all 38 names",
            "a truly dormant variant also requires a product change and link"],
            "owner_decision_required": True, "implementation_started": False},
        "mutations_rejected": ["hide-active-read-line-to-block3-edge",
            "label-active-current-world-dormant", "omit-added-freight-member",
            "misstate-plane-or-capacity-delta", "claim-device-latency-green",
            "break-v1.9-hot-path-byteidentity", "claim-true-dormancy-costs-zero-links"],
        "next": "owner/reviewer chooses strip or explicitly waives the active-world reds",
    }


def validate(value: dict[str, Any]) -> None:
    require(value["format"] == FORMAT and value["status"] == STATUS,
            "release-shape receipt identity drift")
    require(value["process_accounting"] == {"WPLTO": 0, "product_links": 0,
            "media_builds": 0, "device_contacts": 0},
            "host-only accounting drift")
    freight = value["freight"]
    require((freight["added_objects"], freight["name_bytes_NUL_inclusive"],
             freight["plane_bytes"], freight["added_call_sites"]) ==
            (38, 418, 6076, 236), "freight currency drift")
    names = [row["name"] for component in freight["components"].values()
             for row in component["added"]]
    require(len(names) == len(set(names)) == 38,
            "freight member inventory is incomplete or non-unique")
    require(value["dormancy_test"]["is_dormant"] is False
            and value["dormancy_test"]["active_key_path"] == [
                {"caller": caller, "opcode": opcode, "target": target}
                for caller, opcode, target in ACTIVE_BLOCK3_EDGES],
            "active-world dormancy classification drift")
    require(value["dormancy_test"]["device_effect"] == {
                "matcher": "no visible mark",
                "key_feel": "noticeably worse than v1.9"},
            "device-red claim drift")
    require(all(row["byteidentical"] for row in
                value["stripped_hot_path_identity"]["objects"])
            and [row["name"] for row in
                 value["stripped_hot_path_identity"]["objects"]] == list(HOT_PATH),
            "v1.9 editor hot-path identity drift")
    options = value["options"]
    require(options["strip"]["new_WPLTOs"] == 1
            and options["strip"]["new_product_links"] == 1
            and options["keep_current_as_documented_dormant"]["dormant"] is False
            and options["keep_current_as_documented_dormant"]
                ["true_dormant_variant"]["minimum_new_product_links"] >= 1,
            "option price or dormancy drift")
    require(value["recommendation"]["choice"] == "strip"
            and value["recommendation"]["owner_decision_required"] is True
            and value["recommendation"]["implementation_started"] is False,
            "recommendation/decision boundary drift")


def report_text(value: dict[str, Any]) -> str:
    clean = value["worlds"]["stripped_reference"]
    current = value["worlds"]["current_block3"]
    freight = value["freight"]
    stdlib = freight["components"]["stdlib-p0"]
    ide = freight["components"]["ide"]
    return f"""# v2.0 release-shape decision card

Status: **PRICED — owner decision required; no implementation started**

This host-only card compares the final Block-3 repair world with the already
qualified Tier-1 successor world. It consumed **0 WPLTOs, 0 product links,
0 media builds and 0 device contacts**.

## Result that changes the decision

The proposed keep-as-is form is not dormant. The packed final call graph has
the active path `%read-line-loop → %rl-poll → %rl-clear`, then both
`%cursor-blink` and `%rl-idle`; `%rl-idle` reaches all four `%sexp-*` passes.
Thus the exact freight rejected at the device executes on the delivered input
path. The device saw no Matcher mark and judged typing noticeably worse than
v1.9. Calling this world dormant would misclassify an active device-red path.

A genuinely dormant form would need a product edit that bypasses those calls
and therefore at least one new product link. Its apparent zero-link advantage
over stripping does not exist.

## Prices

| Currency | Strip to Tier 1 | Keep current active world | Strip reclaim |
|---|---:|---:|---:|
| Static Plane | {clean['plane_bytes']:,} B | {current['plane_bytes']:,} B | {freight['plane_bytes']:,} B |
| Symbol slots | {clean['symbol_slots']} | {current['symbol_slots']} | {freight['added_objects']} |
| Name bytes | {clean['namepool_bytes']:,} | {current['namepool_bytes']:,} | {freight['name_bytes_NUL_inclusive']} |
| Largest contiguous Bank-2 hole | {clean['largest_contiguous_hole']:,} B | {current['largest_contiguous_hole']:,} B | {freight['largest_hole_cost_bytes']:,} B |
| Packed objects | {clean['closure']['object_count']} | {current['closure']['object_count']} | {freight['added_objects']} |
| Packed call sites | {clean['closure']['call_site_count']:,} | {current['closure']['call_site_count']:,} | {freight['added_call_sites']} |
| New WPLTO / product link | 1 / 1 | 0 / 0 as-is | — |

The manifest accounting is exact. Stdlib contributes {stdlib['code_delta_bytes']:,}
Plane bytes and {len(stdlib['added'])} names ({stdlib['added_name_bytes_NUL_inclusive']}
NUL-inclusive bytes); IDE contributes {ide['code_delta_bytes']:,} Plane bytes
and {len(ide['added'])} names ({ide['added_name_bytes_NUL_inclusive']} bytes).
Together these are exactly the 6,076-byte Plane and hole delta and the D5
38-slot/418-byte delta.

## Option A — strip (recommended)

Run one product card with one WPLTO and one product link, targeting the
qualified Tier-1 object population and semantics. The existing Tier-1 pair is
the measured price/reference, not a substitute for the new candidate link.
The ten delivered editor objects from `%native-prompt` through `read-line`
are byte-identical between that reference and the hardware-green v1.9 release.

The strip retains Tier 1, v1.9 Capture/native-editor behavior, the `$22`
first-fault latch, the resident delivery-chain architecture and the permanent
closure/coherence gates. It removes the unaccepted interactive object set.
The product card owes full difference attribution, authority-consumption,
Scope/Acceptance and both packed-world gates before media.

## Option B — keep and call dormant

This spends no new build immediately, but the label is false: the freight is
active, has no visible Matcher effect, and carries the device-observed typing
regression. It is not release-eligible under the standing no-regression rule
without an explicit owner waiver. Making it truly inert needs a product edit
and link, eliminating its only price advantage.

## Recommendation

**Strip.** It is the only priced form that removes the device-red path,
restores the hardware-proven editor emission, and returns all 6,076 Plane
bytes plus 38 names. This card does not exercise the owner decision and has
started neither implementation.
"""


def plan_result_check() -> None:
    text = PLAN.read_text(encoding="utf-8")
    require(text.count(RESULT_HEADER) == 1, "release-shape result section drift")
    section = RESULT_HEADER + text.split(RESULT_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    folded = " ".join(section.lower().replace("`", "").replace("*", "").split())
    for token in ("38 funktionsobjekte", "418 namensbytes", "6.076 plane-bytes",
                  "not dormant", "empfehlung: strippen", "owner-entscheidung"):
        require(token in folded, f"release-shape plan result absent: {token}")


def mutation_tests(value: dict[str, Any]) -> list[str]:
    cases: dict[str, dict[str, Any]] = {}
    candidate = copy.deepcopy(value)
    candidate["dormancy_test"]["active_key_path"].pop()
    cases["hide-active-read-line-to-block3-edge"] = candidate
    candidate = copy.deepcopy(value)
    candidate["dormancy_test"]["is_dormant"] = True
    cases["label-active-current-world-dormant"] = candidate
    candidate = copy.deepcopy(value)
    candidate["freight"]["components"]["ide"]["added"].pop()
    cases["omit-added-freight-member"] = candidate
    candidate = copy.deepcopy(value)
    candidate["freight"]["plane_bytes"] -= 1
    cases["misstate-plane-or-capacity-delta"] = candidate
    candidate = copy.deepcopy(value)
    candidate["dormancy_test"]["device_effect"]["key_feel"] = "green"
    cases["claim-device-latency-green"] = candidate
    candidate = copy.deepcopy(value)
    candidate["stripped_hot_path_identity"]["objects"][0]["byteidentical"] = False
    cases["break-v1.9-hot-path-byteidentity"] = candidate
    candidate = copy.deepcopy(value)
    candidate["options"]["keep_current_as_documented_dormant"][
        "true_dormant_variant"]["minimum_new_product_links"] = 0
    cases["claim-true-dormancy-costs-zero-links"] = candidate
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            validate(candidate)
        except PricingError:
            rejected.append(name)
    require(rejected == list(cases), "release-shape pricing mutation survived")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("emit", "emit-report", "check", "selftest"))
    args = parser.parse_args()
    try:
        value = derive()
        validate(value)
        if args.action == "emit":
            sys.stdout.buffer.write(canonical(value))
        elif args.action == "emit-report":
            print(report_text(value), end="")
        elif args.action == "check":
            require(load(RECEIPT) == value, "release-shape receipt drift")
            require(REPORT.read_text(encoding="utf-8") == report_text(value),
                    "release-shape report drift")
            plan_result_check()
            print("v2.0 release-shape pricing: CHECK PASS "
                  "strip=6076B/38names current_is_dormant=false")
        else:
            rejected = mutation_tests(value)
            print("v2.0 release-shape pricing: SELFTEST PASS "
                  f"mutations={len(rejected)}")
        return 0
    except (PricingError, CLOSURE.ClosureError, KeyError, ValueError,
            subprocess.CalledProcessError) as exc:
        print(f"v2.0 release-shape pricing: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
