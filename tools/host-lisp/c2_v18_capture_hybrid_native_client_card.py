#!/usr/bin/env python3
"""Build the one authorized v1.8 native-line-editor Capture client card.

The card derives the delivered ``read-line`` implementation from the sealed
Phase-1b editor, adds only the sealed Capture arm/disarm lifecycle, and links
that client over the already-qualified Capture/Hybrid substrate.  Comfort,
Block 3 and diagnostic clients remain outside the product world.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_v160_input_service_hybrid_final_world as HYBRID  # noqa: E402
import c2_v160_queue_single_owner_card as QUEUE  # noqa: E402
import c2_v17_ide_idle_blink_product_card as CURRENT_PLANE  # noqa: E402
import c2_v17_init_l65_card as INIT  # noqa: E402
import c2_v18_capture_hybrid_product_card as SUBSTRATE  # noqa: E402


BASE = SUBSTRATE.BASE
PRODUCT = SUBSTRATE.PRODUCT
FIDELITY = SUBSTRATE.FIDELITY
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v1.8-capture-hybrid-native-client-card-r1"
FAILED_PREFLIGHT = ROOT / (
    "build/c2.3/v1.8-capture-hybrid-native-client-card-r1-preflight")
PREFLIGHT = ROOT / (
    "build/c2.3/v1.8-capture-hybrid-native-client-card-r1b-preflight")
RECEIPT = ARCH / (
    "c2.3-v1.8-capture-hybrid-native-client-card-r1-receipt.json")
FIRST_RED = ARCH / (
    "c2.3-v1.8-capture-hybrid-native-client-card-r1-first-red.json")
FINAL_RED = ARCH / (
    "c2.3-v1.8-capture-hybrid-native-client-card-r1-final-red.json")
REPORT = ROOT / (
    "docs/planning/v1.8.0-capture-hybrid-native-client-card-report.md")
FINAL_RED_REPORT = ROOT / (
    "docs/planning/v1.8.0-capture-hybrid-native-client-card-final-red.md")
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
PROFILE = BUILD / "wplto/resolved-profile.txt"
PLANE_ROOT = PREFLIGHT / "setup-owned/static-plane/narrow-static"
PLANE_RECEIPT = PREFLIGHT / "v18-native-client-static-plane.json"
CLIENT_SOURCE = PREFLIGHT / "sources/stdlib-read-line.lisp"
C2D = PLANE_ROOT / "v6-semantics/initial.c2d-v6.bin"
CODE = PLANE_ROOT / "v6-semantics/bank2-static-code.bin"
MANIFEST = PLANE_ROOT / "stdlib-p0.manifest.json"
SUBSTRATE_ELF = SUBSTRATE.ELF
SUBSTRATE_PRG = SUBSTRATE.PRG
SUBSTRATE_CODE = SUBSTRATE.CODE
SUBSTRATE_RECEIPT = SUBSTRATE.RECEIPT
SUBSTRATE_BUILD = SUBSTRATE.BUILD
SUBSTRATE_PROFILE = SUBSTRATE.PROFILE
SUBSTRATE_PLANE_RECEIPT = SUBSTRATE.PLANE_RECEIPT
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
DRIVER = Path(__file__).resolve()
SEAL_COMMIT = "870e5f53"
COMMISSION_COMMIT = "0164e8c0"
FORMAT = "lisp65-c2-v18-capture-hybrid-native-client-card-r1-v1"
STATUS = "PASS: V1.8 NATIVE LINE EDITOR CAPTURE CLIENT FINAL GREEN"
OLD_FUNCTIONS = (
    "%read-line-clear-from", "%read-line-render-reverse",
    "%read-line-finish", "%read-line-loop", "read-line")
CLIENT_FUNCTIONS = (
    "%rl-render", "%rl-screen-tail", "%rl-cut", "%rl-move", "%rl-put",
    "%rl-dispatch", "%read-line-loop", "read-line")


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


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


def git_bytes(commit: str, name: str) -> bytes:
    return subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout


def authority() -> dict[str, Any]:
    plan = git_bytes(COMMISSION_COMMIT, "docs/planning/v1.7.0-pre-plan.md")
    require(b"v1.8 Block 2 client card" in plan
            and b"native line editor arms capture" in plan
            and b"One WPLTO and one product link" in plan,
            "native-client commission drift")
    return {"authority": "owner/reviewer-bound client card",
        "commission_commit": COMMISSION_COMMIT,
        "commission_plan_sha256": hashlib.sha256(plan).hexdigest(),
        "budget": {"WPLTO_runs": 1, "product_links": 1,
                   "media_builds": 0, "device_contacts": 0},
        "constraints": ["native read-line is the only Capture client",
            "Phase-1b arm/disarm owner byte-identical", "Comfort absent",
            "attribution before qualification", "one-round fallback"]}


def sealed_editor() -> str:
    return git_bytes(SEAL_COMMIT, "lib/stdlib-read-line.lisp").decode()


def client_wrapper() -> str:
    return """(defun read-line ()
  (progn
    (poke 255 141 255)
    (poke 255 140 0)
    (dotimes (counter 4 nil) (poke 188 (+ 252 counter) 0))
    (poke 255 141 0)
    (let* ((size (screen-size))
           (columns (car size))
           (row (- (car (cdr size)) 1))
           (head (cons 0 nil))
           (state (list head head head 0 0 0 columns row))
           (answer
            (progn
              (%rl-screen-tail nil 0 0 columns 0 row)
              (%read-line-loop state))))
      (progn
        (poke 255 141 255)
        answer))))
"""


def derive_client_source() -> str:
    sealed = sealed_editor()
    marker = "(defun read-line ()"
    at = sealed.rfind(marker)
    require(at >= 0 and sealed.count(marker) == 1,
            "sealed editor has no unique read-line wrapper")
    return sealed[:at] + client_wrapper()


def validate_client_source(source: str) -> dict[str, Any]:
    sealed = sealed_editor()
    sealed_prefix = sealed[:sealed.rfind("(defun read-line ()")]
    require(source.startswith(sealed_prefix)
            and source[len(sealed_prefix):] == client_wrapper(),
            "client source changed outside the lifecycle wrapper")
    ordered = (
        "(poke 255 141 255)", "(poke 255 140 0)",
        "(dotimes (counter 4 nil) (poke 188 (+ 252 counter) 0))",
        "(poke 255 141 0)", "(%read-line-loop state)",
        "(poke 255 141 255)", "answer")
    cursor = source.rfind("(defun read-line ()")
    positions = []
    for token in ordered:
        cursor = source.find(token, cursor + (1 if positions else 0))
        require(cursor >= 0, f"client lifecycle token absent: {token}")
        positions.append(cursor)
    require(positions == sorted(positions)
            and source.count("(poke 255 141 255)") == 2
            and source.count("(poke 255 141 0)") == 1,
            "client lifecycle ordering/count drift")
    return {"status": "PASS: SEALED EDITOR PLUS ARM/DISARM WRAPPER",
        "sealed_commit": SEAL_COMMIT,
        "sealed_source": {"bytes": len(sealed.encode()),
            "sha256": hashlib.sha256(sealed.encode()).hexdigest()},
        "client_source": {"bytes": len(source.encode()),
            "sha256": hashlib.sha256(source.encode()).hexdigest()},
        "ordered_lifecycle": list(ordered),
        "non_wrapper_bytes_byte_identical": True}


def lifecycle_mutations(source: str) -> list[dict[str, str]]:
    cases = {
        "omit-entry-close": source.replace(
            "    (poke 255 141 255)\n", "", 1),
        "omit-arm-commit": source.replace(
            "    (poke 255 141 0)\n", "", 1),
        "omit-return-disarm": source.rsplit(
            "        (poke 255 141 255)\n", 1)[0] + "        answer))))\n",
        "substitute-live-block3-source":
            (ROOT / "lib/stdlib-read-line.lisp").read_text(encoding="utf-8"),
    }
    rejected = []
    for name, trial in cases.items():
        try:
            validate_client_source(trial)
        except CardError as error:
            rejected.append({"name": name, "observed_red": str(error)})
    require([row["name"] for row in rejected] == list(cases),
            "client lifecycle mutation survived")
    return rejected


def client_specs() -> tuple[tuple[str, str, Path], ...]:
    return (("stdlib-p0", "stdlib", MANIFEST),) + INIT.BASELINE_SPECS[1:]


def _command(argv: list[str], label: str) -> None:
    result = subprocess.run(argv, cwd=ROOT, text=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")


def emit_client_plane() -> dict[str, Any]:
    require(not PLANE_ROOT.exists() and not PLANE_RECEIPT.exists(),
            "native-client plane preflight is one-shot")
    PLANE_ROOT.mkdir(parents=True)
    CLIENT_SOURCE.parent.mkdir(parents=True)
    source = derive_client_source()
    lifecycle = validate_client_source(source)
    mutations = lifecycle_mutations(source)
    CLIENT_SOURCE.write_text(source, encoding="utf-8")

    baseline_manifest = load(INIT.BASELINE_STDLIB)
    baseline_suite = load(Path(baseline_manifest["suite"]))
    manifest_functions = set(baseline_manifest["functions"])
    baseline_suite["allow_omitted_defuns"] = [
        row for row in baseline_suite["allow_omitted_defuns"]
        if row["name"] not in manifest_functions]
    functions = list(baseline_manifest["functions"])
    starts = [functions.index(name) for name in OLD_FUNCTIONS]
    require(starts == list(range(starts[0], starts[0] + len(OLD_FUNCTIONS))),
            "predecessor read-line inventory is not contiguous")
    functions[starts[0]:starts[0] + len(OLD_FUNCTIONS)] = CLIENT_FUNCTIONS
    baseline_suite["functions"] = functions + list(
        baseline_manifest["private_inline_functions"])
    for key in ("private_inline_functions",
                "resident_private_inline_functions", "resident_overrides",
                "override_exports", "provides", "requires"):
        baseline_suite[key] = baseline_manifest[key]

    public_root = ROOT / "build/release-v1.5.0/public-product-build"
    sources: list[str] = []
    replaced = {"repl-banner.lisp": 0, "stdlib-read-line.lisp": 0}
    for raw in baseline_manifest["sources"]:
        path = Path(raw)
        if path.name == "repl-banner.lisp":
            path = INIT.BANNER; replaced[path.name] = 1
        elif path.name == "stdlib-read-line.lisp":
            path = CLIENT_SOURCE; replaced[path.name] = 1
        elif not path.is_absolute():
            path = public_root / path
        require(path.is_file(), f"native-client predecessor source absent: {path}")
        sources.append(str(path))
    require(replaced == {"repl-banner.lisp": 1, "stdlib-read-line.lisp": 1},
            "native-client plane source replacement is not exact")
    baseline_suite["sources"] = sources
    # The client deliberately consumes the two sealed private Capture modes.
    # This is the Phase-1b execution projection; the public v1.7 projection
    # that rejects modes 2/3 remains unchanged in its own world.
    baseline_suite["private_key_event_modes"] = True
    baseline_suite["successor"] = {
        "kind": "native-line-editor-capture-client",
        "predecessor_manifest": INIT.BASELINE_STDLIB.relative_to(ROOT).as_posix(),
        "changed_source": CLIENT_SOURCE.relative_to(ROOT).as_posix(),
        "sealed_source_commit": SEAL_COMMIT,
        "allowed_delta": "read-line arm/disarm wrapper only"}
    suite_path = PREFLIGHT / "native-client-product-stdlib-suite.json"
    suite_path.write_bytes(canonical(baseline_suite))
    _command([sys.executable, "tools/host-lisp/bytecode_p0_stdlib.py",
              "--check", "--emit-artifacts",
              str((PLANE_ROOT / "stdlib-p0").relative_to(ROOT)),
              str(suite_path.relative_to(ROOT))],
             "emit native-client product stdlib")

    inventory = client_specs()
    require(all(path.is_file() for _key, _name, path in inventory),
            "native-client six-role manifest inventory incomplete")
    sub, v6 = CURRENT_PLANE.SUB, CURRENT_PLANE.V6
    old_sub = sub.BUILD, sub.SPECS
    old_v6 = v6.OUT, v6.PRODUCT_IDENTITY, v6.STATIC_CODE_BYTES, v6.A.SPECS
    try:
        sub.BUILD = PLANE_ROOT / "product"; sub.SPECS = inventory
        product = sub.build()
        total = sum(int(load(path)["code_bytes"])
                    for _key, _name, path in inventory)
        v6.OUT = PLANE_ROOT / "v6-semantics"
        v6.PRODUCT_IDENTITY = PLANE_ROOT / "product/substitution-artifacts.json"
        v6.STATIC_CODE_BYTES = total; v6.A.SPECS = inventory
        v6.OUT.mkdir(parents=True)
        semantics = v6.host_semantics()
    finally:
        sub.BUILD, sub.SPECS = old_sub
        v6.OUT, v6.PRODUCT_IDENTITY, v6.STATIC_CODE_BYTES, v6.A.SPECS = old_v6

    manifest = load(MANIFEST)
    entries = {row["name"]: row for row in manifest["entries"]}
    require(set(CLIENT_FUNCTIONS) <= set(entries)
            and not (set(OLD_FUNCTIONS) - {"%read-line-loop", "read-line"})
                    & set(entries)
            and all(int(entries[name]["length"]) < 255
                    for name in CLIENT_FUNCTIONS),
            "emitted native-client function inventory/size red")
    static = semantics["static_bank2"]
    require(static["code_bytes"] == total,
            "native-client semantic plane extent drift")
    profile_path = CURRENT_PLANE.derived_profile(PLANE_ROOT, product, semantics)
    profile = load(profile_path)
    profile["authority"]["compiled_stdlib_manifest"] = (
        MANIFEST.relative_to(ROOT).as_posix())
    profile["authority"]["compiled_ide_manifest"] = (
        inventory[1][2].relative_to(ROOT).as_posix())
    profile["authority"]["successor"] = {
        "kind": "fresh-native-line-editor-client-six-role-plane",
        "rule": "sealed source plus lifecycle wrapper is consumed by path and value"}
    profile_path.write_bytes(canonical(profile))
    header = CURRENT_PLANE.derived_header(PLANE_ROOT, total)
    contract = CURRENT_PLANE.derived_contract(PLANE_ROOT, total)
    value = {"format": FORMAT + "-static-plane-v1",
        "recorded_on": "2026-08-28",
        "status": "PASS: NATIVE CLIENT CANDIDATE PLANE MATERIALIZED 0/1",
        "geometry": {"bytes": total, "headroom_bytes": 65536 - total,
            "images": product["images"], "entries": product["entries"],
            "resolutions": product["resolutions"], "roots": product["roots"],
            "product_build_id": product["product_build_id_hex"],
            "sha256": static["code_sha256"]},
        "lifecycle": lifecycle, "mutations_rejected": mutations,
        "emitted_client": {name: {"length": entries[name]["length"],
                                   "entry": entries[name]}
                           for name in CLIENT_FUNCTIONS},
        "manifests": [bind(path) for _key, _name, path in inventory],
        "product": bind(PLANE_ROOT / "product/substitution-artifacts.json"),
        "profile": bind(profile_path), "header": bind(header),
        "contract": bind(contract), "bank2": bind(CODE),
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "media_builds": 0, "device_contacts": 0}}
    PLANE_RECEIPT.write_bytes(canonical(value))
    return value


def validate_client_plane_authority(plane: dict[str, Any]) -> dict[str, Any]:
    product_value = load(PLANE_ROOT / "product/substitution-artifacts.json")
    required = {
        "product": bind(PLANE_ROOT / "product/substitution-artifacts.json"),
        "profile": bind(PLANE_ROOT / "candidate-profile.json"),
        "header": bind(PLANE_ROOT / "c2_lite_static_plane.h"),
        "bank2": bind(CODE),
    }
    geometry = plane.get("geometry", {})
    require(geometry.get("bytes") == CODE.stat().st_size
            and geometry.get("sha256") == required["bank2"]["sha256"]
            and all(geometry.get(name) == product_value[name]
                    for name in ("images", "entries", "resolutions", "roots"))
            and all(plane.get(name) == binding
                    for name, binding in required.items()),
            "native-client preflight plane authority drift")
    return {"geometry_bytes": CODE.stat().st_size,
            "geometry_sha256": required["bank2"]["sha256"],
            "topology": {name: product_value[name]
                         for name in ("images", "entries", "resolutions", "roots")},
            "materialized_bindings": required}


def bind_client_plane() -> dict[str, Any]:
    INIT._configure_plane_module()
    plane = load(PLANE_RECEIPT)
    validate_client_plane_authority(plane)
    value = CURRENT_PLANE.bind_current_plane(PLANE_ROOT)
    CURRENT_PLANE.CANDIDATE.ZERO_LITERAL.LINKED_PRODUCT_INVENTORY = (
        PLANE_ROOT / "product/substitution-artifacts.json", ROOT)
    return value


def setup_child() -> tuple[Any, dict[str, Any], dict[str, object]]:
    core, activation, product_cold = SUBSTRATE.configure_capture_recovery_stack()
    static = bind_client_plane()
    core.bind_paths_only(BUILD, PREFLIGHT)
    old_paths = core.PROJECTED_OWNERSHIP, core.PROJECTED_FULL_MAP
    core.PROJECTED_OWNERSHIP = PREFLIGHT / "projected-ownership-contract.json"
    core.PROJECTED_FULL_MAP = PREFLIGHT / "projected-full-map-authority.json"
    try:
        core.write_projections()
    finally:
        core.PROJECTED_OWNERSHIP, core.PROJECTED_FULL_MAP = old_paths
    require(static["consumer_observed_bytes"] == CODE.stat().st_size,
            "real setup did not consume native-client plane")
    CURRENT_PLANE.install_final_v6_consumer(record=True)
    return core, activation, product_cold


def validate_candidate_consumption(
        rows: dict[str, tuple[Path, dict[str, Any]]]) -> None:
    header = PLANE_ROOT / "c2_lite_static_plane.h"
    header_binding = bind(header)
    expected = CODE.stat().st_size
    for name, (_path, value) in rows.items():
        flags = value.get("actual_force_include_flags", [])
        require(value.get("status") ==
                    "passed-bound-candidate-header-consumed"
                and value.get("bound_header") == header_binding
                and value.get("materialized_header") == header_binding
                and value.get("consumed_value") == expected
                and value.get("materialized_value") == expected
                and value.get("historical_same_basename_accepted") is False
                and len(flags) == 4
                and flags[:2] == ["-include",
                    header.relative_to(ROOT).as_posix()]
                and flags[2] == "-include"
                and flags[3] == value["compile_time_assertion"]["path"],
                f"candidate-derived compiler consumption red: {name}")


def candidate_consumption_receipts() -> dict[str, dict[str, Any]]:
    rows = INIT._consumption_rows()
    validate_candidate_consumption(rows)
    return {name: {"binding": bind(path), "result": value}
            for name, (path, value) in rows.items()}


def consumption_adapter_mutations() -> list[str]:
    rows = INIT._consumption_rows()
    rejected = []
    for name, mutate in (
            ("reintroduce-stored-46053", lambda value: value.update(
                consumed_value=46053)),
            ("path-value-diverge", lambda value: value["bound_header"].update(
                path="build/c2.3/v1.7-init-l65-card-r4b-preflight/"
                     "setup-owned/static-plane/narrow-static/"
                     "c2_lite_static_plane.h"))):
        trial = {key: (path, json.loads(json.dumps(value)))
                 for key, (path, value) in rows.items()}
        mutate(trial["seed"][1])
        try:
            validate_candidate_consumption(trial)
        except CardError:
            rejected.append(name)
    require(rejected == ["reintroduce-stored-46053", "path-value-diverge"],
            "dynamic compiler-consumption mutations survived")
    return rejected


def configure() -> None:
    for name, value in {
        "BUILD": BUILD, "PREFLIGHT": PREFLIGHT, "RECEIPT": RECEIPT,
        "FIRST_RED": FIRST_RED, "REPORT": REPORT, "ELF": ELF, "PRG": PRG,
        "PROFILE": PROFILE, "PLANE_ROOT": PLANE_ROOT,
        "PLANE_RECEIPT": PLANE_RECEIPT, "C2D": C2D, "CODE": CODE,
        "MANIFEST": MANIFEST, "DRIVER": DRIVER, "FORMAT": FORMAT,
        "STATUS": STATUS}.items():
        setattr(SUBSTRATE, name, value)
    SUBSTRATE.configure()
    for module in (INIT,):
        module.BUILD = BUILD; module.PREFLIGHT = PREFLIGHT
        module.RECEIPT = RECEIPT; module.ELF = ELF; module.PRG = PRG
        module.PROFILE = PROFILE; module.PLANE_ROOT = PLANE_ROOT
        module.PLANE_RECEIPT = PLANE_RECEIPT; module.C2D = C2D
        module.CODE = CODE; module.MANIFEST = MANIFEST
        module.DRIVER = DRIVER; module.FORMAT = FORMAT; module.STATUS = STATUS
    HYBRID.EDITOR = CLIENT_SOURCE
    HYBRID.RESPONSIVENESS_FUNCTION_WORLD = "historical-sealed"
    INIT._validate_candidate_consumption = validate_candidate_consumption
    INIT.candidate_consumption_receipts = candidate_consumption_receipts
    INIT.consumption_adapter_mutations = consumption_adapter_mutations
    INIT.HEADER_CARD.consumption_receipts = candidate_consumption_receipts
    BASE.DRIVER = DRIVER; BASE.FORMAT = FORMAT; BASE.STATUS = STATUS
    BASE.authority = authority
    BASE.configuration_gate = configuration_gate
    BASE.setup_child = setup_child
    BASE.final_gate = final_gate


def configuration_gate() -> dict[str, Any]:
    value = SUBSTRATE.capture_recovery_configuration_gate()
    value.update({"world": "v1.8-native-line-editor-capture-client",
        "client": "sealed Phase-1b native read-line",
        "client_source": CLIENT_SOURCE.relative_to(ROOT).as_posix(),
        "excluded": ["repl-comfort", "Block-3", "diagnostic-client"]})
    return value


def preflight() -> None:
    require(not any(path.exists() for path in
                    (BUILD, PREFLIGHT, RECEIPT, FIRST_RED)),
            "v1.8 native-client card is one-shot")
    configure()
    BASE.preflight()
    plane = emit_client_plane()
    phase1b = SUBSTRATE.lifecycle_gate()
    require(phase1b["status"] ==
                "PASS: PHASE-1B ARM/DISARM OWNER BYTE-IDENTICAL",
            "Phase-1b Capture owner drift")
    value = load(BASE.PREFLIGHT_RECEIPT)
    value["format"] = FORMAT + "-preflight"
    value["status"] = "PASS: V1.8 NATIVE CLIENT CARD ARMED 0/1"
    value["native_client_plane"] = {"receipt": bind(PLANE_RECEIPT),
        "geometry": plane["geometry"], "lifecycle": plane["lifecycle"],
        "mutations_rejected": plane["mutations_rejected"]}
    value["phase1b_owner"] = phase1b
    failed_suite = FAILED_PREFLIGHT / "native-client-product-stdlib-suite.json"
    require(failed_suite.is_file()
            and load(failed_suite).get("private_key_event_modes") is not True
            and not BUILD.exists(),
            "pre-card public/private projection First Red evidence drift")
    value["pre_card_adapter_conversions"] = [{
        "family": "real-caller action vocabulary",
        "observed": "new driver omitted inherited _release_probe action",
        "consumption": {"WPLTO_runs": 0, "product_links": 0}}, {
        "family": "phase-owned compiler projection",
        "observed": "public stdlib projection rejected sealed key-event modes 2/3",
        "replacement": "Phase-1b private_key_event_modes projection",
        "evidence": bind(failed_suite),
        "consumption": {"WPLTO_runs": 0, "product_links": 0}}]
    value["substrate_pair"] = {"ELF": bind(SUBSTRATE_ELF),
                                "PRG": bind(SUBSTRATE_PRG)}
    value["attempt_accounting"] = {"WPLTO_runs": 0, "product_links": 0,
        "scope_runs": 0, "acceptance_runs": 0, "media_builds": 0,
        "device_contacts": 0}
    BASE.PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("v1.8 native client: PREFLIGHT PASS client=armed Comfort=0 "
          "WPLTO=0/1 link=0/1")


def member_diff(left: bytes, right: bytes, family: str) -> list[list[Any]]:
    total = max(len(left), len(right))
    return [[index, left[index] if index < len(left) else None,
             right[index] if index < len(right) else None, family]
            for index in range(total)
            if (left[index] if index < len(left) else None)
            != (right[index] if index < len(right) else None)]


def symbol_key(row: Any) -> tuple[Any, ...]:
    return (row.name, row.value, row.bytes, row.binding, row.symbol_type,
            row.section, row.section_index)


def relocation_key(row: Any) -> tuple[Any, ...]:
    return (row.relocation_section, row.source_section,
            row.source_section_index, row.offset, row.relocation_type,
            row.target, row.addend)


def expand(counter: Counter[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
    return [key for key in sorted(counter, key=repr)
            for _ in range(counter[key])]


def profile_inputs(path: Path) -> dict[str, Any]:
    features: list[str] = []
    sources: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("feature_defines="):
            features = [row for row in line.split("=", 1)[1].split(",") if row]
        elif line.startswith("input_sha256="):
            name, digest = line.split("=", 1)[1].rsplit(":", 1)
            key = ("generated-product-sources/" + Path(name).name
                   if "generated-product-sources" in Path(name).parts
                   else str(Path(name).resolve()))
            sources[key] = digest
    require(features and sources, f"resolved profile incomplete: {path}")
    return {"features": features, "sources": sources}


def input_closure() -> dict[str, Any]:
    old = profile_inputs(SUBSTRATE_PROFILE)
    new = profile_inputs(PROFILE)
    common = sorted(set(old["sources"]) & set(new["sources"]))
    changed = [name for name in common
               if old["sources"][name] != new["sources"][name]]
    added = sorted(set(new["sources"]) - set(old["sources"]))
    removed = sorted(set(old["sources"]) - set(new["sources"]))
    require(old["features"] == new["features"] and not added and not removed
            and changed == ["generated-product-sources/c2-stream-phase-02a.c"],
            "native-client compiler input closure has an unknown root")
    old_generated = SUBSTRATE_BUILD / (
        "wplto/generated-product-sources/c2-stream-phase-02a.c")
    new_generated = BUILD / (
        "wplto/generated-product-sources/c2-stream-phase-02a.c")
    old_lines = old_generated.read_text(encoding="utf-8").splitlines()
    new_lines = new_generated.read_text(encoding="utf-8").splitlines()
    changed_lines = [index + 1 for index, (left, right) in
                     enumerate(zip(old_lines, new_lines)) if left != right]
    require(len(old_lines) == len(new_lines) and changed_lines == [4, 6]
            and all("crc16" in new_lines[index - 1]
                    for index in changed_lines),
            "generated source changed outside derived plane CRC rows")
    candidate_plane = load(PLANE_RECEIPT)
    substrate_plane = load(SUBSTRATE_PLANE_RECEIPT)
    require(candidate_plane["manifests"][1:] ==
                substrate_plane["manifests"][1:]
            and candidate_plane["manifests"][0] !=
                substrate_plane["manifests"][0]
            and bind(CODE)["sha256"] != bind(SUBSTRATE_CODE)["sha256"],
            "client plane changed outside its stdlib owner")
    consumption = candidate_consumption_receipts()
    return {"status": "PASS: CLIENT PLANE IS THE ONLY AUTHORED ROOT",
        "feature_defines_byte_identical": True,
        "compiler_sources": {"members": len(common), "added": added,
            "removed": removed, "changed": changed,
            "unchanged_members": len(common) - len(changed)},
        "generated_change": {"path": changed[0],
            "changed_lines": changed_lines,
            "family": "candidate-plane-derived per-role CRC16"},
        "static_roles": {"unchanged_roles": 5,
            "changed_role": "stdlib-p0",
            "substrate_plane": bind(SUBSTRATE_CODE),
            "client_plane": bind(CODE)},
        "compiler_consumption": consumption,
        "causal_rule": ("sealed read-line lifecycle delta changes stdlib-p0; "
            "all native input contents remain identical and the sole generated "
            "source delta is the static-plane CRC projection")}


def attribution() -> dict[str, Any]:
    closure = input_closure()
    old = ElfTruth.read(SUBSTRATE_ELF, llvm_readobj=READOBJ,
                        include_section_data=True)
    new = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    prg = member_diff(SUBSTRATE_PRG.read_bytes(), PRG.read_bytes(),
                      "native-client-static-plane-transitive-product-byte")
    elf = member_diff(SUBSTRATE_ELF.read_bytes(), ELF.read_bytes(),
                      "native-client-static-plane-transitive-ELF-byte")
    old_symbols = Counter(map(symbol_key, old.symbols))
    new_symbols = Counter(map(symbol_key, new.symbols))
    removed_symbols = expand(old_symbols - new_symbols)
    added_symbols = expand(new_symbols - old_symbols)
    old_reloc = Counter(map(relocation_key, old.relocations))
    new_reloc = Counter(map(relocation_key, new.relocations))
    removed_reloc = expand(old_reloc - new_reloc)
    added_reloc = expand(new_reloc - old_reloc)
    sections = []
    for name in sorted({row.name for row in old.sections} |
                       {row.name for row in new.sections}):
        left = old.sections_by_name.get(name, [])
        right = new.sections_by_name.get(name, [])
        if [asdict(row) for row in left] != [asdict(row) for row in right]:
            sections.append({"name": name,
                "before": [asdict(row) for row in left],
                "after": [asdict(row) for row in right],
                "family": "native-client-static-plane-section"})
    symbol_rows = ([{"direction": "removed", "member": list(row),
                     "family": "native-client-static-plane-symbol"}
                    for row in removed_symbols] +
                   [{"direction": "added", "member": list(row),
                     "family": "native-client-static-plane-symbol"}
                    for row in added_symbols])
    relocation_rows = ([{"direction": "removed", "member": list(row),
        "family": "native-client-static-plane-relocation"}
        for row in removed_reloc] +
        [{"direction": "added", "member": list(row),
          "family": "native-client-static-plane-relocation"}
         for row in added_reloc])
    counts = {"PRG_bytes": len(prg), "ELF_bytes": len(elf),
        "symbols_removed": len(removed_symbols),
        "symbols_added": len(added_symbols),
        "relocations_removed": len(removed_reloc),
        "relocations_added": len(added_reloc),
        "sections_changed": len(sections), "unexplained_PRG_bytes": 0,
        "unexplained_ELF_bytes": 0, "unexplained_symbols": 0,
              "unexplained_relocations": 0, "unexplained_sections": 0}
    def summary(rows: list[Any], family_index: int | None = None) -> dict[str, Any]:
        families = (Counter(row[family_index] for row in rows)
                    if family_index is not None else
                    Counter(row["family"] for row in rows))
        return {"members": len(rows),
            "canonical_members_sha256": hashlib.sha256(canonical(rows)).hexdigest(),
            "family_counts": dict(sorted(families.items())),
            "storage": ("complete member list is deterministically re-derived "
                        "by the receipt checker; digest keeps evidence compact")}
    return {"status": "PASS: CLIENT DELTA FULLY ATTRIBUTED BEFORE QUALIFICATION",
        "pair": {"substrate": {"ELF": bind(SUBSTRATE_ELF),
                                  "PRG": bind(SUBSTRATE_PRG)},
                 "candidate": {"ELF": bind(ELF), "PRG": bind(PRG)}},
        "input_closure": closure,
        "causal_roots": {"native_sources_byte_identical": True,
            "candidate_plane": bind(CODE), "substrate_plane": bind(SUBSTRATE_CODE),
            "only_authored_delta": "sealed read-line plus lifecycle wrapper"},
        "PRG_changed_members": summary(prg, 3),
        "ELF_changed_members": summary(elf, 3),
        "symbol_changed_members": summary(symbol_rows),
        "relocation_changed_members": summary(relocation_rows),
        "section_changed_members": sections, "counts": counts}


def client_final_gate() -> dict[str, Any]:
    plane = load(PLANE_RECEIPT)
    manifest = load(MANIFEST)
    entries = {row["name"]: row for row in manifest["entries"]}
    source = CLIENT_SOURCE.read_text(encoding="utf-8")
    lifecycle = validate_client_source(source)
    require(plane["lifecycle"] == lifecycle
            and plane["geometry"]["bytes"] == CODE.stat().st_size
            and set(CLIENT_FUNCTIONS) <= set(entries)
            and "%rl-poll" not in entries and "%ide-idle" not in entries,
            "final client plane/lifecycle drift")
    repl = (ROOT / "src/repl.c").read_text(encoding="utf-8")
    require(repl.count("C2K_INPUT_RING_TAIL = 0xff;") == 1,
            "native abort close edge drift")
    return {"status": "PASS: SHIPPED READ-LINE ARMS AND DISARMS CAPTURE",
        "source": bind(CLIENT_SOURCE), "plane": bind(CODE),
        "manifest": bind(MANIFEST), "lifecycle": lifecycle,
        "emitted_functions": {name: {"length": entries[name]["length"]}
                              for name in CLIENT_FUNCTIONS},
        "entry_closed_then_zeroed_then_armed": True,
        "normal_return_disarms": True, "abort_path_disarms": True,
        "block3_functions_present": False,
        "pre_media_claim": "armed lifecycle proved in shipped static plane"}


def final_gate() -> dict[str, Any]:
    product = SUBSTRATE.capture_recovery_final_gate()
    HYBRID.EDITOR = CLIENT_SOURCE
    HYBRID.RESPONSIVENESS_FUNCTION_WORLD = "historical-sealed"
    hybrid = HYBRID.derive(ELF)
    queue = QUEUE.linked_owner_gate(ELF)
    e000 = SUBSTRATE.e000_composition()
    client = client_final_gate()
    require(hybrid["loss"]["linked_events_drained"] == 94
            and hybrid["loss"]["linked_dropped"] == 0
            and hybrid["normalization"]["executions"] == 512
            and hybrid["normalization"]["parity"] is True
            and hybrid["responsiveness"]["margin_percent"] >= 25.0
            and queue["dominated_calls"] == 1,
            "native-client final wall red")
    product["v1_8_native_line_editor_client"] = {
        "status": "PASS: ARMED NATIVE CLIENT AND FULL WALL SET GREEN",
        "client": client, "hybrid": hybrid,
        "queue_single_owner": queue, "E000_composition": e000,
        "comfort": {"library_bytes": 0, "activation_owner_present": False},
        "claim_limit": "host-qualified native line-editor Capture client"}
    return product


def composed_overlap_evidence() -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    static = {"owner": "bank2-static-code-plane", "start": 0x20000,
        "end_exclusive": 0x20000 + CODE.stat().st_size,
        "bytes": CODE.stat().st_size}
    mapped = []
    for section, prefix in (
            (".lisp65_c2_mapped_far_service",
             "__lisp65_c2_mapped_far_service"),
            (".lisp65_c2_mapped_product_cold",
             "__lisp65_c2_mapped_product_cold")):
        mapped.append({"owner": section,
            "start": truth.symbol(prefix + "_load_start").value,
            "end_exclusive": truth.symbol(prefix + "_load_end").value,
            "bytes": truth.section(section).bytes,
            "VMA": truth.section(section).address})
    overlaps = []
    owners = [static, *mapped]
    for index, left in enumerate(owners):
        for right in owners[index + 1:]:
            start = max(int(left["start"]), int(right["start"]))
            end = min(int(left["end_exclusive"]), int(right["end_exclusive"]))
            if start < end:
                overlaps.append({"left": left["owner"],
                    "right": right["owner"], "start": start,
                    "end_exclusive": end, "bytes": end - start})
    require(overlaps, "final-red composed overlap no longer reproduces")
    return {"status": "RED: COMPOSED BANK2 OWNERS OVERLAP",
        "owners": owners, "overlaps": overlaps,
        "mechanism": ("the sealed native editor grows the static plane into "
            "the substrate pair's fixed mapped-far-service load interval"),
        "product_defect": True}


def write_report(value: dict[str, Any]) -> None:
    gate = value["final_product"]["v1_8_native_line_editor_client"]
    response = gate["hybrid"]["responsiveness"]
    counts = value["attribution"]["counts"]
    plane = load(PLANE_RECEIPT)
    REPORT.write_text(f"""# v1.8 native line-editor Capture client card

Status: **{value['status']}**

Exactly one WPLTO and one product link replaced the substrate's scalar
`read-line` plane with the sealed Phase-1b editor plus its atomically ordered
Capture arm/disarm wrapper. Comfort, Block 3 and diagnostic clients contribute
zero bytes. The final shipped client closes and zeroes the ring at entry,
arms only after the origin is complete, disarms on normal return, and retains
the independent native abort close edge.

The final static plane is **{plane['geometry']['bytes']} bytes**. The final ELF
drains 94/94 events with zero drops, executes 512/512 normalization cases and
measures **{response['frames_per_character']:.6f} frames/character** with
**{response['margin_percent']:.3f}% margin**. Queue single ownership, RUN/STOP
and the three-owner E000 composition remain green.

The substrate-to-client attribution names {counts['PRG_bytes']} changed PRG
bytes, {counts['symbols_removed']}+{counts['symbols_added']} symbol members and
{counts['relocations_removed']}+{counts['relocations_added']} relocation
members; every unexplained count is zero before Scope and Acceptance. Both
qualifiers consume the same frozen pair. No medium was built and no device was
contacted.
""", encoding="utf-8")


def record_red(error: Exception, invoked: bool) -> None:
    artifacts = {}
    for name, path in (("ELF", ELF), ("PRG", PRG),
                       ("map", BUILD / "wplto/lisp65-c2-substitution-linked.prg.map"),
                       ("lto", BUILD / "wplto/resident-island-seed.prg.lto.o")):
        if path.is_file():
            artifacts[name] = bind(path)
    value = {"format": FORMAT + "-first-red", "recorded_on": "2026-08-28",
        "status": "FIRST RED: NATIVE CLIENT ONE-ROUND CARD STOPS",
        "error": str(error), "artifacts": artifacts,
        "attempt_accounting": {"WPLTO_runs": int(invoked),
            "product_links": int(ELF.is_file()),
            "scope_runs": int(BASE.SCOPE_RESULT.is_file()),
            "acceptance_runs": int(BASE.ACCEPTANCE_RESULT.is_file()),
            "media_builds": 0, "device_contacts": 0},
        "fallback": "release v1.8 substrate-only; client moves to v1.9",
        "retry_authorized": False}
    FIRST_RED.write_bytes(canonical(value))


def build() -> None:
    configure()
    pre = load(BASE.PREFLIGHT_RECEIPT)
    require(pre["status"] == "PASS: V1.8 NATIVE CLIENT CARD ARMED 0/1"
            and not BUILD.exists() and not RECEIPT.exists()
            and not BASE.INVOCATION.exists(),
            "native-client preflight/lifecycle drift")
    BASE.INVOCATION.write_bytes(canonical({"status": "INVOKED",
        "authority": authority(), "preflight": bind(BASE.PREFLIGHT_RECEIPT)}))
    processes = [BASE.run_child("_produce")]
    before = BASE.artifacts()
    diff = attribution()
    require(all(value == 0 for name, value in diff["counts"].items()
                if name.startswith("unexplained_")),
            "client attribution retained unexplained member")
    processes.extend((BASE.run_child("_scope"), BASE.run_child("_accept")))
    after = BASE.artifacts()
    require(before == after, "qualification changed frozen native-client pair")
    scope = load(BASE.SCOPE_RESULT); acceptance = load(BASE.ACCEPTANCE_RESULT)
    require(scope["status"] == acceptance["status"] == "PASS",
            "native-client qualification tail red")
    gate = final_gate()
    value = {"format": FORMAT, "recorded_on": "2026-08-28",
        "status": STATUS, "authority": authority(),
        "preflight": bind(BASE.PREFLIGHT_RECEIPT),
        "invocation": bind(BASE.INVOCATION),
        "configuration": pre["configuration"], "attribution": diff,
        "final_product": gate, "producer": bind(BASE.PRODUCER_RESULT),
        "scope": bind(BASE.SCOPE_RESULT),
        "acceptance": bind(BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": processes,
        "attempt_accounting": {"WPLTO_runs": 1, "product_links": 1,
            "scope_runs": 1, "acceptance_runs": 1, "media_builds": 0,
            "device_contacts": 0}, "media_authorized": False,
        "next": "independent review; Comfort remains closed"}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    check()
    print("v1.8 native client: CARD PASS WPLTO=1/1 link=1/1 "
          "armed=YES Comfort=0")


def resume() -> None:
    configure()
    red = load(FIRST_RED)
    before = BASE.artifacts()
    require(red["status"] ==
                "FIRST RED: NATIVE CLIENT ONE-ROUND CARD STOPS"
            and red["attempt_accounting"] == {"WPLTO_runs": 1,
                "product_links": 1, "scope_runs": 0, "acceptance_runs": 0,
                "media_builds": 0, "device_contacts": 0}
            and red["artifacts"]["ELF"] == before["ELF"]
            and red["artifacts"]["PRG"] == before["PRG"]
            and not RECEIPT.exists(),
            "native-client frozen adapter-red/pair drift")
    adapter = {"status": "PASS: CANDIDATE EXTENT DERIVED, NOT PINNED",
        "observed_predecessor_pin": 46053,
        "candidate_extent": CODE.stat().st_size,
        "consumption": candidate_consumption_receipts(),
        "mutations_rejected": consumption_adapter_mutations()}
    diff = attribution()
    require(all(value == 0 for name, value in diff["counts"].items()
                if name.startswith("unexplained_")),
            "client Resume attribution retained unexplained member")
    processes = [BASE.run_child("_scope"), BASE.run_child("_accept")]
    after = BASE.artifacts()
    require(after == before,
            "read-only native-client Resume changed frozen pair")
    scope = load(BASE.SCOPE_RESULT); acceptance = load(BASE.ACCEPTANCE_RESULT)
    require(scope["status"] == acceptance["status"] == "PASS",
            "native-client Resume qualification tail red")
    gate = final_gate()
    value = {"format": FORMAT, "recorded_on": "2026-08-28",
        "status": STATUS, "authority": authority(),
        "preflight": bind(BASE.PREFLIGHT_RECEIPT),
        "invocation": bind(BASE.INVOCATION), "first_red": bind(FIRST_RED),
        "stored_world_adapter_conversion": adapter,
        "configuration": load(BASE.PREFLIGHT_RECEIPT)["configuration"],
        "attribution": diff, "final_product": gate,
        "producer": bind(BASE.PRODUCER_RESULT),
        "scope": bind(BASE.SCOPE_RESULT),
        "acceptance": bind(BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": processes,
        "attempt_accounting": {"WPLTO_runs": 1, "product_links": 1,
            "scope_runs": 1, "acceptance_runs": 1, "media_builds": 0,
            "device_contacts": 0},
        "resume_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "scope_runs": 1, "acceptance_runs": 1, "cards_consumed": 0},
        "media_authorized": False,
        "next": "independent review; Comfort remains closed"}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    check()
    print("v1.8 native client: RESUME PASS WPLTO=1/1 link=1/1 "
          "new-builds=0 armed=YES")


def close_red() -> None:
    configure()
    require(not RECEIPT.exists(),
            "native-client green receipt conflicts with final-red closure")
    before = BASE.artifacts()
    red = load(FIRST_RED)
    scope = load(BASE.SCOPE_RESULT); acceptance = load(BASE.ACCEPTANCE_RESULT)
    require(red["artifacts"]["ELF"] == before["ELF"]
            and red["artifacts"]["PRG"] == before["PRG"]
            and scope["status"] == acceptance["status"] == "PASS",
            "native-client final-red frozen evidence drift")
    diff = attribution()
    require(all(value == 0 for name, value in diff["counts"].items()
                if name.startswith("unexplained_")),
            "final-red attribution retained unexplained member")
    overlap = composed_overlap_evidence()
    value = {"format": FORMAT + "-final-red", "recorded_on": "2026-08-28",
        "status": "FINAL RED: NATIVE CLIENT FALLS BACK TO V1.8 SUBSTRATE",
        "authority": authority(), "preflight": bind(BASE.PREFLIGHT_RECEIPT),
        "invocation": bind(BASE.INVOCATION), "adapter_red": bind(FIRST_RED),
        "pair": before, "attribution": diff,
        "stored_world_adapter_conversion": {
            "status": "PASS: CANDIDATE EXTENT DERIVED, NOT PINNED",
            "predecessor_pin": 46053, "candidate_extent": CODE.stat().st_size,
            "consumption": candidate_consumption_receipts(),
            "mutations_rejected": consumption_adapter_mutations()},
        "scope": bind(BASE.SCOPE_RESULT),
        "acceptance": bind(BASE.ACCEPTANCE_RESULT),
        "final_product_gate": overlap,
        "attempt_accounting": {"WPLTO_runs": 1, "product_links": 1,
            "scope_runs": 1, "acceptance_runs": 1, "media_builds": 0,
            "device_contacts": 0},
        "resume_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "scope_runs": 1, "acceptance_runs": 1, "cards_consumed": 0},
        "one_round_rule": {"closed": True, "retry_authorized": False,
            "v1_8_release": "substrate-only",
            "client_successor": "v1.9"},
        "claim_limit": ("frozen product evidence only; the overlapping pair "
                        "is not a release candidate")}
    FINAL_RED.write_bytes(canonical(value))
    rows = overlap["overlaps"]
    FINAL_RED_REPORT.write_text(f"""# v1.8 native line-editor client card — Final Red

Status: **{value['status']}**

The single authorized WPLTO and product link emitted and froze ELF
`{before['ELF']['sha256']}` and PRG `{before['PRG']['sha256']}`. Full
substrate-to-client attribution completed with zero unexplained bytes,
symbols, relocations or sections. Scope and Acceptance then passed read-only
over that pair.

The final composed Bank-2 gate rejected the product. The {CODE.stat().st_size}-byte
static plane ends at `${0x20000 + CODE.stat().st_size:05X}` and overlaps the
substrate's mapped far-service load interval by **{rows[0]['bytes']} bytes**
(`${rows[0]['start']:05X}..${rows[0]['end_exclusive']:05X}`). This is a real
product ownership collision, not a checker or adapter defect.

No retry, relocation or second link is authorized. Under the bound one-round
rule, v1.8.0 returns to the already-qualified Capture/Hybrid substrate claim;
the native delivered client becomes a v1.9 placement step. No medium was built
and no device was contacted.
""", encoding="utf-8")
    check_red()
    print("v1.8 native client: FINAL RED CLOSED fallback=substrate-only "
          "client=v1.9")


def check_red() -> None:
    configure()
    value = load(FINAL_RED)
    counts = value["attribution"]["counts"]
    require(value["status"] ==
                "FINAL RED: NATIVE CLIENT FALLS BACK TO V1.8 SUBSTRATE"
            and value["pair"] == BASE.artifacts()
            and canonical(value["attribution"]) == canonical(attribution())
            and value["final_product_gate"] == composed_overlap_evidence()
            and value["scope"] == bind(BASE.SCOPE_RESULT)
            and value["acceptance"] == bind(BASE.ACCEPTANCE_RESULT)
            and value["one_round_rule"] == {"closed": True,
                "retry_authorized": False, "v1_8_release": "substrate-only",
                "client_successor": "v1.9"}
            and all(member == 0 for name, member in counts.items()
                    if name.startswith("unexplained_")),
            "native-client final-red receipt drift")
    print("v1.8 native client: FINAL-RED CHECK PASS retry=closed")


def check() -> None:
    configure()
    value = load(RECEIPT)
    gate = value["final_product"]["v1_8_native_line_editor_client"]
    require(value["status"] == STATUS
            and value["artifacts_before"] == BASE.artifacts()
            and value["artifacts_after"] == value["artifacts_before"]
            and gate["client"]["entry_closed_then_zeroed_then_armed"] is True
            and gate["client"]["normal_return_disarms"] is True
            and gate["hybrid"]["responsiveness"]["margin_percent"] >= 25.0
            and gate["comfort"]["library_bytes"] == 0
            and all(value == 0 for name, value in
                    value["attribution"]["counts"].items()
                    if name.startswith("unexplained_")),
            "native-client final receipt drift")
    print("v1.8 native client: CHECK PASS armed-client=YES Comfort=0")


def child(action: str) -> None:
    if action == "_release_probe":
        SUBSTRATE.release_probe_child()
        return
    configure()
    if action == "_profile_probe":
        SUBSTRATE.profile_probe_child()
    elif action == "_produce":
        BASE.produce_child()
    elif action == "_scope":
        BASE.scope_child()
    elif action == "_accept":
        BASE.acceptance_child()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "preflight", "build", "resume", "close-red", "check", "check-red",
        "_profile_probe", "_release_probe",
        "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    if action == "preflight":
        preflight()
    elif action == "build":
        try:
            build()
        except Exception as error:
            record_red(error, BASE.INVOCATION.exists())
            raise
    elif action == "resume":
        resume()
    elif action == "close-red":
        close_red()
    elif action == "check":
        check()
    elif action == "check-red":
        check_red()
    else:
        child(action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.8 native client: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
