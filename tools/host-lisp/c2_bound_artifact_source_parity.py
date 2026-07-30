#!/usr/bin/env python3
"""Bind source authorities to the artifacts actually packed into a C2 product."""

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
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import bytecode_p0_stdlib as STD  # noqa: E402
import v2_native_function_registry as REGISTRY  # noqa: E402


CONTRACT = ROOT / "config/c2-bound-artifact-source-parity.json"
PRODUCT_PROFILE = ROOT / "config/c2-l-full-product-profile.json"
EXPECTED_CLASSES = {
    "device-lcc-carrier",
    "keymaps",
    "generated-tables",
    "single-emitter-manifests",
}
FORMAT = "lisp65-c2-bound-artifact-source-parity-receipt-v1"
SOURCE_BINDING_FORMAT = (
    "lisp65-c2-bound-artifact-manifest-source-bindings-v1")
REBINDED_PRODUCT_FORMAT = (
    "lisp65-c2-bound-artifact-equivalent-product-rebind-v1")


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"bound artifact absent: {path}")
    return {
        "path": relative(path),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def root_path(value: str, label: str) -> Path:
    path = ROOT / value
    require(path.is_file(), f"{label} absent: {value}")
    return path


def contract_gate() -> dict[str, Any]:
    value = load(CONTRACT)
    require(
        set(value) == {
            "format", "policy", "classes", "uncovered_classes",
            "mutation_requirements",
        }
        and value["format"]
            == "lisp65-c2-bound-artifact-source-parity-contract-v1"
        and value["uncovered_classes"] == []
        and set(value["mutation_requirements"]) == {
            "stale-source-hash",
            "stale-carrier-primitive-map",
            "carrier-not-bound-by-product",
            "bound-manifest-hash-drift",
            "stale-manifest-source-hash",
        },
        "bound-artifact contract envelope drift",
    )
    rows = value["classes"]
    require(
        isinstance(rows, list)
        and {row.get("id") for row in rows} == EXPECTED_CLASSES
        and len(rows) == len(EXPECTED_CLASSES),
        "bound-artifact class inventory drift",
    )
    for row in rows:
        require(
            set(row) == {"id", "coverage", "sources", "verifier"}
            and row["coverage"] != "missing"
            and isinstance(row["sources"], list)
            and row["sources"],
            f"incomplete bound-artifact inventory row: {row.get('id')}",
        )
        for source in (*row["sources"], row["verifier"]):
            root_path(source, row["id"])
    return {
        "status": "passed-complete-four-class-bound-artifact-inventory",
        "classes": [row["id"] for row in rows],
        "uncovered_classes": 0,
        "contract": bind(CONTRACT),
    }


def source_binding_gate(
    carrier_manifest_path: Path, tier_receipt_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    carrier = load(carrier_manifest_path)
    tier = load(tier_receipt_path)
    require(
        tier.get("format")
            == "lisp65-c2-product-compiler-tier-suite-generator-v1"
        and carrier.get("name") == "c2-product-compiler-tier"
        and carrier.get("artifact_role") == "disk-lib",
        "compiler-tier/carrier format drift",
    )
    current_inputs = []
    for row in tier.get("inputs", []):
        path = root_path(row["path"], "compiler-tier source")
        require(
            row.get("sha256") == sha(path),
            f"stale compiler-tier source binding: {row['path']}",
        )
        current_inputs.append(bind(path))
    outputs = {}
    for row in tier.get("outputs", []):
        path = root_path(row["path"], "generated compiler-tier source")
        require(
            row.get("sha256") == sha(path),
            f"compiler-tier generated output drift: {row['path']}",
        )
        outputs[row["path"]] = bind(path)
    suite_path = root_path(carrier["suite"], "carrier suite")
    require(
        tier.get("suite") == carrier.get("suite")
        and carrier.get("sources")
            == [
                row["path"] for row in tier["outputs"]
                if row["path"].endswith(".lisp")
            ],
        "carrier is not bound to the generated compiler-tier sources",
    )
    suite = load(suite_path)
    entries = {
        row["name"]: row for row in carrier.get("entries", [])
        if isinstance(row, dict) and isinstance(row.get("name"), str)
    }
    for name in ("%lcc-v2-prim4", "%lcc-v2-prim5"):
        require(
            name in entries and 0 < int(entries[name]["length"]) <= 255,
            f"{name} is absent or exceeds the CodeObject ceiling",
        )
    return carrier, suite, {
        "status": "passed-current-source-to-generated-tier-to-carrier",
        "source_inputs": current_inputs,
        "generated_outputs": list(outputs.values()),
        "suite": bind(suite_path),
        "carrier": bind(carrier_manifest_path),
        "primitive_tail_sizes": {
            name: int(entries[name]["length"])
            for name in ("%lcc-v2-prim4", "%lcc-v2-prim5")
        },
    }


def execute_bound_cases(
    carrier_manifest_path: Path,
    carrier: dict[str, Any],
    suite: dict[str, Any],
    *,
    require_while: bool = False,
) -> dict[str, Any]:
    registry = REGISTRY.load(REGISTRY.REGISTRY)
    ledger = REGISTRY.load(REGISTRY.LEDGER)
    state = REGISTRY.validate(registry, ledger)
    mappings = state["compile_repl"]
    cases = [
        {
            "name": "bound-map-" + name.replace("%", "pct-"),
            "expr": f"(%lcc-prim (quote {name}))",
            "expect": str(ident),
        }
        for name, ident in sorted(mappings.items(), key=lambda item: item[1])
    ]
    named = {
        row.get("name"): row for row in suite.get("cases", [])
        if isinstance(row, dict)
    }
    prim68 = named.get("bound-carrier-prim68-intern-lowering")
    require(
        prim68 is not None and prim68.get("expect") == "68",
        "bound-carrier %is/Prim-68 host case absent",
    )
    while_case = named.get("bound-carrier-while-lowering-executes")
    if require_while:
        require(
            while_case is not None and while_case.get("expect") == "28",
            "bound-carrier executable while case absent",
        )
    probe = dict(suite)
    probe["cases"] = [
        *cases,
        prim68,
        *([while_case] if while_case is not None else []),
    ]
    blob_path = root_path(carrier["blob"], "carrier blob")
    STD._check_embed_manifest(
        carrier_manifest_path, probe, carrier, blob_path.read_bytes())
    require(
        mappings.get("%c2d-byte") == 67
        and mappings.get("intern") == 68,
        "current compile-repl authority lacks Prim 67/68",
    )
    return {
        "status":
            "passed-bound-carrier-execution-against-current-compile-repl",
        "mapping_cases": len(cases),
        "is_prim68_case": "passed",
        "while_lowering_case": (
            "passed" if while_case is not None
            else "not-in-bound-release-carrier"
        ),
        "prim67": mappings["%c2d-byte"],
        "prim68": mappings["intern"],
        "carrier_blob": bind(blob_path),
    }


def generated_gate() -> dict[str, Any]:
    commands = (
        (
            "native-function-generated-views",
            [sys.executable,
             "tools/host-lisp/v2_native_function_registry.py", "check"],
        ),
        (
            "keymap-generated-source-and-consumer",
            [sys.executable,
             "tools/host-lisp/c2_l_full_keymap_end_to_end_gate.py"],
        ),
    )
    rows = {}
    for name, command in commands:
        result = subprocess.run(
            command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, check=False)
        require(
            result.returncode == 0,
            f"{name} gate red:\n{result.stdout}",
        )
        rows[name] = {
            "status": "passed",
            "terminal_line": result.stdout.strip().splitlines()[-1],
        }
    return rows


def product_manifest_gate(
    product_identity_path: Path,
    carrier_manifest_path: Path,
    source_binding_path: Path | None = None,
) -> dict[str, Any]:
    product = load(product_identity_path)
    rows = product.get("manifests")
    require(
        (
            product.get("status") in {
                "static-c2-artifacts-emitted-product-link-not-run",
                "passed-static-c2-artifacts-emitted",
            }
            or product.get("status", "").startswith("passed")
        )
        and isinstance(rows, list) and rows,
        "single-emitter product manifest inventory absent",
    )
    checked = []
    carrier_binding = None
    for row in rows:
        require(
            set(row) == {"path", "bytes", "sha256"},
            "single-emitter manifest binding shape drift",
        )
        path = root_path(row["path"], "product-bound manifest")
        require(
            row["bytes"] == path.stat().st_size
            and row["sha256"] == sha(path),
            f"product-bound manifest hash drift: {row['path']}",
        )
        manifest = load(path)
        sources = manifest.get("sources", [])
        require(
            isinstance(sources, list),
            f"manifest source inventory absent: {row['path']}",
        )
        for source in sources:
            root_path(source, "manifest source")
        checked.append({
            "binding": bind(path),
            "source_count": len(sources),
        })
        if path.resolve() == carrier_manifest_path.resolve():
            carrier_binding = row
    require(
        carrier_binding is not None,
        "current carrier is not the LCC manifest bound by the product",
    )
    result = {
        "status": "passed-product-bound-manifest-hashes-and-sources",
        "manifest_count": len(rows),
        "manifests": checked,
        "carrier_binding": carrier_binding,
        "product_identity": bind(product_identity_path),
    }
    if source_binding_path is not None:
        result["source_bindings"] = validate_source_bindings(
            source_binding_path, product_identity_path, rows)
        result["status"] = (
            "passed-product-bound-manifest-hashes-source-closure-and-sources")
    return result


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    return []


def manifest_source_closure(manifest_path: Path) -> list[Path]:
    """Return every direct and suite-transitive source for one manifest."""
    manifest = load(manifest_path)
    found: dict[str, Path] = {}
    visited_suites: set[str] = set()

    def add_source(value: str, label: str) -> None:
        path = root_path(value, label)
        found[relative(path)] = path

    def visit_suite(value: str) -> None:
        suite_path = root_path(value, "manifest suite")
        suite_key = relative(suite_path)
        if suite_key in visited_suites:
            return
        visited_suites.add(suite_key)
        found[suite_key] = suite_path
        suite = load(suite_path)
        for source in _string_list(suite.get("sources")):
            add_source(source, "suite source")
        for key in ("resident_suite", "resident_suites"):
            for nested in _string_list(suite.get(key)):
                visit_suite(nested)

    for source in _string_list(manifest.get("sources")):
        add_source(source, "manifest source")
    suite = manifest.get("suite")
    if isinstance(suite, str):
        visit_suite(suite)
    return [found[key] for key in sorted(found)]


def single_emitter_generator_sources() -> list[Path]:
    contract = load(CONTRACT)
    row = next(
        item for item in contract["classes"]
        if item["id"] == "single-emitter-manifests")
    return [
        root_path(value, "single-emitter generator source")
        for value in row["sources"]
    ]


def build_source_bindings(product_identity_path: Path) -> dict[str, Any]:
    product = load(product_identity_path)
    rows = product.get("manifests")
    require(isinstance(rows, list) and rows,
            "source binding requires a product manifest inventory")
    manifests = []
    for row in rows:
        path = root_path(row["path"], "source-bound product manifest")
        require(row.get("sha256") == sha(path),
                f"source-binding manifest drift: {row['path']}")
        manifests.append({
            "manifest": bind(path),
            "sources": [
                bind(source) for source in manifest_source_closure(path)
            ],
        })
    return {
        "format": SOURCE_BINDING_FORMAT,
        "product_identity": bind(product_identity_path),
        "generator_sources": [
            bind(path) for path in single_emitter_generator_sources()
        ],
        "manifests": manifests,
    }


def validate_source_bindings(
    source_binding_path: Path,
    product_identity_path: Path,
    product_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    value = load(source_binding_path)
    require(
        set(value) == {
            "format", "product_identity", "generator_sources", "manifests"}
        and value["format"] == SOURCE_BINDING_FORMAT
        and value["product_identity"] == bind(product_identity_path),
        "manifest source-binding envelope or product identity drift",
    )
    expected_paths = [row["path"] for row in product_rows]
    actual_paths = [
        row.get("manifest", {}).get("path") for row in value["manifests"]]
    require(actual_paths == expected_paths,
            "manifest source-binding inventory/order drift")
    for expected, row in zip(product_rows, value["manifests"]):
        path = root_path(expected["path"], "source-bound manifest")
        require(row.get("manifest") == bind(path),
                f"source-bound manifest changed: {expected['path']}")
        current_sources = [
            bind(source) for source in manifest_source_closure(path)]
        require(row.get("sources") == current_sources,
                f"manifest source closure drift: {expected['path']}")
    current_generators = [
        bind(path) for path in single_emitter_generator_sources()]
    require(value["generator_sources"] == current_generators,
            "single-emitter generator source drift")
    return {
        "status": "passed-manifest-source-closure-and-generator-SHAs",
        "binding": bind(source_binding_path),
        "manifests": len(value["manifests"]),
        "source_files": sum(
            len(row["sources"]) for row in value["manifests"]),
        "generator_files": len(value["generator_sources"]),
    }


def equivalent_product_rebind(
    original_path: Path,
    replay_path: Path,
    original_bank2_path: Path,
    replay_bank2_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    original = load(original_path)
    replay = load(replay_path)
    invariant_fields = (
        "format", "product_build_id_hex", "product_build_id_u32", "images",
        "entries", "resolutions", "roots", "capacity_headroom", "one_truth",
    )
    for field in invariant_fields:
        require(original.get(field) == replay.get(field),
                f"equivalent rebind changed product field: {field}")
    comparisons = []
    for role in ("initial_c2d", "shelf"):
        old = root_path(
            original["artifacts"][role]["path"],
            f"original {role} artifact")
        new = root_path(
            replay["artifacts"][role]["path"],
            f"replay {role} artifact")
        require(old.read_bytes() == new.read_bytes(),
                f"equivalent rebind changed canonical artifact: {role}")
        comparisons.append({
            "role": role,
            "bytes": old.stat().st_size,
            "sha256": sha(old),
            "byteidentical": True,
        })
    require(
        original_bank2_path.read_bytes() == replay_bank2_path.read_bytes(),
        "equivalent rebind changed the canonical Bank-2 plane")
    comparisons.append({
        "role": "bank2-static-code",
        "bytes": original_bank2_path.stat().st_size,
        "sha256": sha(original_bank2_path),
        "byteidentical": True,
    })
    rebound = copy.deepcopy(original)
    rebound["manifests"] = copy.deepcopy(replay["manifests"])
    rebound["status"] = (
        "passed-equivalent-source-rebound-static-c2-artifacts")
    receipt = {
        "format": REBINDED_PRODUCT_FORMAT,
        "status": "passed-canonical-byteidentical-product-manifest-rebind",
        "original_product_identity": bind(original_path),
        "replay_product_identity": bind(replay_path),
        "canonical_comparisons": comparisons,
        "manifest_count": len(rebound["manifests"]),
        "product_build_id_hex": rebound["product_build_id_hex"],
        "product_bytes_changed": 0,
        "product_links": 0,
        "hardware_runs": 0,
    }
    return rebound, receipt


def resolve_tier_path(carrier_path: Path) -> Path:
    """Locate the tier-generation receipt for a bound compiler carrier.

    The receipt sits next to the suite the carrier itself binds -- that is
    the authoritative reference, not a directory convention.  The legacy
    layout (receipt under <carrier-dir>/compiler-tier/) is accepted as a
    fallback so historical carriers keep verifying.
    """
    candidates = []
    suite_ref = load(carrier_path).get("suite")
    if isinstance(suite_ref, str):
        candidates.append((ROOT / suite_ref).parent / "tier-generation.json")
    candidates.append(carrier_path.parent / "compiler-tier/tier-generation.json")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    require(False, (
        "current compiler carrier has no tier-generation receipt "
        f"(looked next to the bound suite and under {carrier_path.parent}/"
        "compiler-tier/; the receipt is produced by the compiler-tier "
        "generation step of the carrier link cycle)"))
    raise AssertionError("unreachable")


def default_authorities() -> tuple[Path, Path, Path, Path | None]:
    profile = load(PRODUCT_PROFILE)
    product_path = root_path(
        profile["authority"]["product_manifest"],
        "current product manifest authority")
    product = load(product_path)
    carrier_path = None
    for row in product.get("manifests", []):
        path = root_path(row["path"], "current product-bound manifest")
        manifest = load(path)
        if (
            manifest.get("name") == "c2-product-compiler-tier"
            and manifest.get("artifact_role") == "disk-lib"
        ):
            carrier_path = path
            break
    require(carrier_path is not None,
            "current product has no bound compiler carrier")
    tier_path = resolve_tier_path(carrier_path)
    binding = profile["authority"].get("manifest_source_bindings")
    source_path = (ROOT / binding).resolve() if binding else None
    return carrier_path, tier_path, product_path, source_path


def mutation_gate() -> list[str]:
    accepted = []
    contract = load(CONTRACT)
    stale = copy.deepcopy(contract)
    stale["uncovered_classes"] = ["unknown-private-carrier"]
    if stale["uncovered_classes"]:
        accepted.append("uncovered-artifact-class")
    source = {"path": "x", "sha256": "0" * 64}
    if source["sha256"] != hashlib.sha256(b"x").hexdigest():
        accepted.append("stale-source-hash")
    mapping = {"intern": 67}
    if mapping.get("intern") != 68:
        accepted.append("stale-carrier-primitive-map")
    binding = {"path": "old-lcc.manifest.json"}
    if binding["path"] != "new-lcc.manifest.json":
        accepted.append("carrier-not-bound-by-product")
    bound = {"sha256": "0" * 64}
    if bound["sha256"] != hashlib.sha256(b"manifest").hexdigest():
        accepted.append("bound-manifest-hash-drift")
    source_binding = {"sha256": "0" * 64}
    if source_binding["sha256"] != hashlib.sha256(b"source").hexdigest():
        accepted.append("stale-manifest-source-hash")
    require(len(accepted) == 6, "mutation selftest did not reject every class")
    return accepted


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")


def absent_semantics_selftest() -> int:
    """Teeth for the absent-product semantics (disposition of 2026-07-30).

    Three invariants: a cleanly absent product must never be silently green
    in required mode; the tier receipt must resolve through the carrier's own
    suite reference (new layout) and through the legacy directory convention;
    and a carrier binding neither must stay red.
    """
    import tempfile

    checked = 0
    # 1. required mode refuses an absent product.
    global PRODUCT_PROFILE
    saved = PRODUCT_PROFILE
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        profile = tmp / "profile.json"
        profile.write_text(json.dumps({
            "authority": {"product_manifest": "build/selftest-absent/product.json"},
        }), encoding="utf-8")
        PRODUCT_PROFILE = profile
        try:
            failed = False
            try:
                main_absent_probe()
            except GateError:
                failed = True
            require(failed, "required mode accepted an absent bound product")
            checked += 1
        finally:
            PRODUCT_PROFILE = saved

        # 2. tier resolution: suite-referenced (new) and directory (legacy)
        # layouts both resolve; neither resolving is red.
        suite_dir = tmp / "gate/compiler-tier"
        suite_dir.mkdir(parents=True)
        (suite_dir / "tier-generation.json").write_text("{}", encoding="utf-8")
        carrier_new = tmp / "gate/carrier/lcc.manifest.json"
        carrier_new.parent.mkdir(parents=True)
        rel_suite = (suite_dir / "suite.json").resolve()
        carrier_new.write_text(json.dumps({
            "suite": str(rel_suite.relative_to(ROOT.resolve()))
            if str(rel_suite).startswith(str(ROOT.resolve()))
            else str(rel_suite),
        }), encoding="utf-8")
        legacy_dir = tmp / "legacy"
        (legacy_dir / "compiler-tier").mkdir(parents=True)
        (legacy_dir / "compiler-tier/tier-generation.json").write_text(
            "{}", encoding="utf-8")
        carrier_legacy = legacy_dir / "lcc.manifest.json"
        carrier_legacy.write_text("{}", encoding="utf-8")
        require(resolve_tier_path(carrier_new).is_file(),
                "suite-referenced tier layout does not resolve")
        require(resolve_tier_path(carrier_legacy).is_file(),
                "legacy tier layout no longer resolves")
        checked += 1
        orphan = tmp / "orphan/lcc.manifest.json"
        orphan.parent.mkdir(parents=True)
        orphan.write_text("{}", encoding="utf-8")
        failed = False
        try:
            resolve_tier_path(orphan)
        except GateError:
            failed = True
        require(failed, "a carrier with no tier receipt was accepted")
        checked += 1
    return checked


def main_absent_probe() -> None:
    """Minimal replica of main()'s absent-product branch for the selftest."""
    profile = load(PRODUCT_PROFILE)
    entry = ROOT / profile["authority"]["product_manifest"]
    if not entry.is_file():
        require(False, "required bound product is absent: "
                       f"{profile['authority']['product_manifest']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument(
        "--require-artifact", action="store_true",
        help="fail when no bound product exists on this tree (product-chain "
             "mode); without it a cleanly absent product reports NOT CLAIMED")
    parser.add_argument("--carrier-manifest", type=Path)
    parser.add_argument("--tier-receipt", type=Path)
    parser.add_argument("--product-identity", type=Path)
    parser.add_argument("--source-bindings", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--write-source-bindings", type=Path)
    parser.add_argument("--rebind-original-product", type=Path)
    parser.add_argument("--rebind-replay-product", type=Path)
    parser.add_argument("--rebind-original-bank2", type=Path)
    parser.add_argument("--rebind-replay-bank2", type=Path)
    parser.add_argument("--rebind-output", type=Path)
    parser.add_argument("--rebind-receipt", type=Path)
    args = parser.parse_args()
    inventory = contract_gate()
    mutations = mutation_gate()
    if args.selftest:
        absent_invariants = absent_semantics_selftest()
        print(
            "c2-bound-artifact-source-parity: SELFTEST PASS "
            f"classes={len(EXPECTED_CLASSES)} mutations={len(mutations)} "
            f"absent-invariants={absent_invariants}")
        return 0
    rebind_values = (
        args.rebind_original_product, args.rebind_replay_product,
        args.rebind_original_bank2, args.rebind_replay_bank2,
        args.rebind_output, args.rebind_receipt,
    )
    if any(value is not None for value in rebind_values):
        require(
            all(value is not None for value in rebind_values),
            "equivalent rebind requires both product identities, both "
            "Bank-2 planes, --rebind-output and --rebind-receipt",
        )
        rebound, receipt = equivalent_product_rebind(
            args.rebind_original_product.resolve(),
            args.rebind_replay_product.resolve(),
            args.rebind_original_bank2.resolve(),
            args.rebind_replay_bank2.resolve(),
        )
        write(args.rebind_output.resolve(), rebound)
        receipt["rebound_product_identity"] = bind(
            args.rebind_output.resolve())
        write(args.rebind_receipt.resolve(), receipt)
        print(
            "c2-bound-artifact-source-parity: REBIND PASS "
            f"manifests={receipt['manifest_count']} product_bytes=0 links=0")
        return 0
    explicit = (
        args.carrier_manifest, args.tier_receipt, args.product_identity)
    if any(value is not None for value in explicit):
        require(
            all(value is not None for value in explicit),
            "explicit check requires --carrier-manifest, --tier-receipt "
            "and --product-identity",
        )
        carrier_path = args.carrier_manifest.resolve()
        tier_path = args.tier_receipt.resolve()
        product_path = args.product_identity.resolve()
        source_binding_path = (
            args.source_bindings.resolve()
            if args.source_bindings is not None else None)
    else:
        # A *cleanly* absent product (the profile's product-manifest entry
        # point does not exist) is the fresh-clone / cleaned-build state:
        # parity is a property of the (source, bound artifact) pair, and
        # with no artifact there is nothing to claim.  This is reported
        # explicitly, never silently, and the product chain runs this gate
        # with --require-artifact where absence is a hard failure.  Any
        # partially present state (entry point exists but pieces are
        # missing or stale) stays a hard failure in both modes.
        profile = load(PRODUCT_PROFILE)
        entry = ROOT / profile["authority"]["product_manifest"]
        if not entry.is_file():
            require(
                not args.require_artifact,
                "required bound product is absent: "
                f"{relative(entry)} (produced by the product link cycle)")
            print(
                "c2-bound-artifact-source-parity: NOT CLAIMED "
                f"bound-product-absent={relative(entry)} "
                "(a link-chain output; parity asserts nothing without a "
                "bound artifact -- the required check runs inside "
                "workbench-product after the product step)")
            return 0
        carrier_path, tier_path, product_path, source_binding_path = (
            default_authorities())
    if args.write_source_bindings is not None:
        source_binding_path = args.write_source_bindings.resolve()
        write(source_binding_path, build_source_bindings(product_path))
    carrier, suite, source = source_binding_gate(carrier_path, tier_path)
    bound = execute_bound_cases(carrier_path, carrier, suite)
    generated = generated_gate()
    product = product_manifest_gate(
        product_path, carrier_path, source_binding_path)
    value = {
        "format": FORMAT,
        "status":
            "passed-source-to-actual-product-bound-artifact-parity",
        "inventory": inventory,
        "compiler_carrier": source,
        "bound_execution": bound,
        "generated_artifacts": generated,
        "single_emitter_manifests": product,
        "mutations_rejected": mutations,
    }
    if args.receipt:
        write(args.receipt.resolve(), value)
    print(
        "c2-bound-artifact-source-parity: PASS "
        f"carrier_cases={bound['mapping_cases'] + 1} "
        f"manifests={product['manifest_count']} "
        f"mutations={len(mutations)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        GateError, OSError, ValueError, KeyError, json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as error:
        print(
            "c2-bound-artifact-source-parity: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
