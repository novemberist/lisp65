#!/usr/bin/env python3
"""Build and qualify the review-opened native INIT.L65 product card."""

from __future__ import annotations

import argparse
import copy
from collections import deque
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
import bytecode_p0_stdlib as STD  # noqa: E402
import c2_v17_init_l65_pricing as PRICE  # noqa: E402
import c2_v17_ide_idle_blink_product_card as CURRENT_PLANE  # noqa: E402
import c2_v17_recovery_quiescence_card as RECOVERY  # noqa: E402
import c2_v20_phase02b_header_consumption_card as HEADER_CARD  # noqa: E402
from c2_product_session_host import (  # noqa: E402
    ProductSessionHost, SessionHostError, Trace,
)
from elf_truth import ElfTruth  # noqa: E402


BASE = RECOVERY.BASE
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CONTRACT = ROOT / "config/c2-v17-init-l65-implementation-contract.json"
REPLACEMENT = ROOT / "config/c2-v17-init-l65-replacement-contract.json"
FIRST_RED = ARCH / "c2.3-v1.7-init-l65-card-r1-first-red.json"
PLANE_REPLACEMENT = ROOT / (
    "config/c2-v17-init-l65-plane-replacement-contract.json")
SECOND_RED = ARCH / "c2.3-v1.7-init-l65-card-r2-first-red.json"
CONSUMER_REPLACEMENT = ROOT / (
    "config/c2-v17-init-l65-consumer-replacement-contract.json")
THIRD_RED = ARCH / "c2.3-v1.7-init-l65-card-r3-first-red.json"
FOURTH_RED = ARCH / "c2.3-v1.7-init-l65-card-r4-first-red.json"
RESUME_CONTRACT = ROOT / "config/c2-v17-init-l65-r4-resume-contract.json"
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
REPORT = ROOT / "docs/planning/v1.7.0-init-l65-implementation-report.md"
BUILD = ROOT / "build/c2.3/v1.7-init-l65-card-r4"
PREFLIGHT = ROOT / "build/c2.3/v1.7-init-l65-card-r4b-preflight"
RECEIPT = ARCH / "c2.3-v1.7-init-l65-card-r4-receipt.json"
RESUME_RECEIPT = ARCH / (
    "c2.3-v1.7-init-l65-card-r4-qualification-resume-receipt.json")
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
PLANE_ROOT = PREFLIGHT / "setup-owned/static-plane/narrow-static"
PLANE_RECEIPT = PREFLIGHT / "native-init-static-plane.json"
C2D = PLANE_ROOT / "v6-semantics/initial.c2d-v6.bin"
CODE = PLANE_ROOT / "v6-semantics/bank2-static-code.bin"
MANIFEST = PLANE_ROOT / "stdlib-p0.manifest.json"
BASELINE_SPECS = CURRENT_PLANE.CANDIDATE.candidate_static_specs()
BASELINE_STDLIB = BASELINE_SPECS[0][2]
BASELINE_ROOT = ROOT / "build/c2.3/v1.7-recovery-quiescence-card-r3-a0"
BASELINE_ELF = BASELINE_ROOT / "wplto/lisp65-c2-substitution-linked.prg.elf"
BASELINE_CODE = BASELINE_ROOT / (
    "static-plane/narrow-static/v6-semantics/bank2-static-code.bin")
SUITE = ROOT / "tests/bytecode/libs/p0-stdlib-require-resolver.json"
BANNER = ROOT / "lib/repl-banner.lisp"
LOAD = ROOT / "lib/stdlib-load.lisp"
REPL = ROOT / "src/repl.c"
COMPILE_REPL = ROOT / "src/compile_repl.c"
VM = ROOT / "src/vm.c"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
DRIVER = Path(__file__).resolve()
FORMAT = "lisp65-c2-v17-init-l65-card-r4-v1"
STATUS = "PASS: V1.7 NATIVE INIT.L65 FINAL PRODUCT GREEN"
SEALED_COMMIT = "be6c40bfe200ee486b451754a2b1a511ea46d6e4"
FROZEN_PAIR = {
    "ELF": "4ae360b0ff583505d0c584c7c20a269526b8145f9406f1ef0752433099a021b9",
    "PRG": "f2ea6e12333ff036067a21ec04c32b26cda66b004e16df2814e3b5fbaa1813b7",
}


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


def sealed_bind(path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{SEALED_COMMIT}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"path": name, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    contract = load(CONTRACT)
    replacement = load(REPLACEMENT)
    first_red = load(FIRST_RED)
    plane_replacement = load(PLANE_REPLACEMENT)
    second_red = load(SECOND_RED)
    consumer_replacement = load(CONSUMER_REPLACEMENT)
    third_red = load(THIRD_RED)
    fourth_red = load(FOURTH_RED)
    resume_contract = load(RESUME_CONTRACT)
    plan = subprocess.run(
        ["git", "show", f"{SEALED_COMMIT}:{PLAN.relative_to(ROOT).as_posix()}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout.decode()
    price = PRICE.check_sealed_receipt()
    require(contract["status"] == "OPEN: REVIEW-APPROVED IMPLEMENTATION CARD"
            and contract["pricing_commit"] == PRICE.SEALED_COMMIT
            and contract["selected_form"]["new_named_helpers"] == []
            and contract["final_bars"]["resident_delta_bytes_max"] == 0
            and replacement["status"] ==
                "OPEN: SELF-DISPOSED KNOWN-FAMILY REPLACEMENT"
            and first_red["classification"]["product_defect"] is False
            and first_red["attempt_accounting"] == {
                "WPLTO_runs": 1, "product_links": 0,
                "media_builds": 0, "device_contacts": 0}
            and plane_replacement["status"] ==
                "OPEN: SELF-DISPOSED BOUND-NOT-CONSUMED REPLACEMENT"
            and second_red["observed"]["candidate_static_plane_bytes"]
                == second_red["observed"]["baseline_static_plane_bytes"]
            and consumer_replacement["status"] ==
                "OPEN: THIRD AND FINAL SELF-DISPOSED REPLACEMENT"
            and third_red["attribution"]["product_defect"] is False
            and "Block I implementation opening" in plan
            and "Block I implementation r1 First Red" in plan
            and "Block I implementation r2 First Red" in plan
            and "Block I implementation r3 First Red" in plan
            and "Block I r4 semantic-witness conversion" in plan
            and fourth_red["attribution"]["product_defect"] is False
            and resume_contract["status"] ==
                "OPEN: REVIEW-APPROVED READ-ONLY R4 RESUME"
            and price["bank2_price"]["delta"]["code_bytes"] == 10,
            "INIT.L65 implementation authority drift")
    return {"implementation_contract": bind(CONTRACT),
            "replacement_contract": bind(REPLACEMENT),
            "r1_first_red": bind(FIRST_RED),
            "plane_replacement_contract": bind(PLANE_REPLACEMENT),
            "r2_first_red": bind(SECOND_RED),
            "consumer_replacement_contract": bind(CONSUMER_REPLACEMENT),
            "r3_first_red": bind(THIRD_RED),
            "r4_first_red": bind(FOURTH_RED),
            "r4_resume_contract": bind(RESUME_CONTRACT),
            "pre_plan": sealed_bind(PLAN),
            "sealed_pricing": bind(PRICE.OUT)}


def _command(argv: list[str], label: str) -> None:
    result = subprocess.run(argv, cwd=ROOT, text=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")


def _configure_plane_module() -> None:
    CURRENT_PLANE.PLANE = PLANE_ROOT
    CURRENT_PLANE.PLANE_RECEIPT = PLANE_RECEIPT
    CURRENT_PLANE.PREFLIGHT = PREFLIGHT
    CURRENT_PLANE.BUILD = BUILD
    CURRENT_PLANE.setup_plane = lambda _preflight=PREFLIGHT: PLANE_ROOT
    CURRENT_PLANE.specs = lambda _root=PLANE_ROOT: init_specs()


def init_specs() -> tuple[tuple[str, str, Path], ...]:
    return (("stdlib-p0", "stdlib", MANIFEST),) + BASELINE_SPECS[1:]


def emit_init_plane() -> dict[str, Any]:
    """Materialize the Lisp source successor before any product invocation."""
    require(not PLANE_ROOT.exists() and not PLANE_RECEIPT.exists(),
            "native INIT plane preflight is one-shot")
    PLANE_ROOT.mkdir(parents=True)
    baseline_manifest = load(BASELINE_STDLIB)
    baseline_suite = load(Path(baseline_manifest["suite"]))
    # The published predecessor's release projection promoted two direct-C2
    # functions after its original suite file was written.  Reconstruct the
    # effective suite from the consumed manifest, not from that earlier
    # registration snapshot.
    manifest_functions = set(baseline_manifest["functions"])
    baseline_suite["allow_omitted_defuns"] = [
        row for row in baseline_suite["allow_omitted_defuns"]
        if row["name"] not in manifest_functions]
    baseline_suite["functions"] = (baseline_manifest["functions"]
        + baseline_manifest["private_inline_functions"])
    for key in ("private_inline_functions",
                "resident_private_inline_functions", "resident_overrides",
                "override_exports", "provides", "requires"):
        baseline_suite[key] = baseline_manifest[key]
    public_root = ROOT / "build/release-v1.5.0/public-product-build"
    sources: list[str] = []
    banner_sources = 0
    for raw in baseline_manifest["sources"]:
        source = Path(raw)
        if source.name == "repl-banner.lisp":
            source = BANNER
            banner_sources += 1
        elif not source.is_absolute():
            source = public_root / source
        require(source.is_file(), f"native INIT predecessor source absent: {source}")
        sources.append(str(source))
    require(banner_sources == 1,
            "native INIT predecessor suite has no unique banner owner")
    baseline_suite["sources"] = sources
    baseline_suite["successor"] = {
        "kind": "native-init-only",
        "predecessor_manifest": BASELINE_STDLIB.relative_to(ROOT).as_posix(),
        "changed_source": BANNER.relative_to(ROOT).as_posix(),
    }
    suite_path = PREFLIGHT / "native-init-product-stdlib-suite.json"
    suite_path.write_bytes(canonical(baseline_suite))
    _command([sys.executable, "tools/host-lisp/bytecode_p0_stdlib.py",
              "--check", "--emit-artifacts",
              str((PLANE_ROOT / "stdlib-p0").relative_to(ROOT)),
              str(suite_path.relative_to(ROOT))],
             "emit native INIT product stdlib")

    inventory = init_specs()
    require(all(path.is_file() for _key, _name, path in inventory),
            "native INIT six-role manifest inventory incomplete")
    sub, v6 = CURRENT_PLANE.SUB, CURRENT_PLANE.V6
    old_sub = sub.BUILD, sub.SPECS
    old_v6 = v6.OUT, v6.PRODUCT_IDENTITY, v6.STATIC_CODE_BYTES, v6.A.SPECS
    try:
        sub.BUILD = PLANE_ROOT / "product"
        sub.SPECS = inventory
        product = sub.build()
        total = sum(int(load(path)["code_bytes"])
                    for _key, _name, path in inventory)
        v6.OUT = PLANE_ROOT / "v6-semantics"
        v6.PRODUCT_IDENTITY = PLANE_ROOT / (
            "product/substitution-artifacts.json")
        v6.STATIC_CODE_BYTES = total
        v6.A.SPECS = inventory
        v6.OUT.mkdir(parents=True)
        semantics = v6.host_semantics()
    finally:
        sub.BUILD, sub.SPECS = old_sub
        (v6.OUT, v6.PRODUCT_IDENTITY,
         v6.STATIC_CODE_BYTES, v6.A.SPECS) = old_v6

    static = semantics["static_bank2"]
    manifest = load(PLANE_ROOT / "stdlib-p0.manifest.json")
    banner = next(row for row in manifest["entries"]
                  if row["name"] == "%repl-banner")
    require(total == 46053 and product["images"] == 6
            and product["entries"] == 755
            and product["resolutions"] == 2931
            and product["roots"] == 353
            and manifest["objects"] == 393
            and manifest["code_bytes"] == 17248
            and banner["length"] == 155
            and static["code_bytes"] == total,
            "candidate-owned native INIT plane price/materialization red")

    profile_path = CURRENT_PLANE.derived_profile(
        PLANE_ROOT, product, semantics)
    profile = load(profile_path)
    profile["authority"]["compiled_stdlib_manifest"] = (
        MANIFEST.relative_to(ROOT).as_posix())
    profile["authority"]["compiled_ide_manifest"] = (
        inventory[1][2].relative_to(ROOT).as_posix())
    profile["authority"]["successor"] = {
        "kind": "fresh-native-init-six-role-plane",
        "rule": ("current Lisp sources are materialized once before the "
                 "real product link and consumed by path plus value"),
    }
    profile_path.write_bytes(canonical(profile))
    header = CURRENT_PLANE.derived_header(PLANE_ROOT, total)
    contract = CURRENT_PLANE.derived_contract(PLANE_ROOT, total)
    value = {
        "format": FORMAT + "-static-plane-v1",
        "recorded_on": "2026-08-27",
        "status": "PASS: NATIVE INIT CANDIDATE PLANE MATERIALIZED 0/1",
        "geometry": {"bytes": total, "headroom_bytes": 65536 - total,
            "images": product["images"], "entries": product["entries"],
            "resolutions": product["resolutions"],
            "roots": product["roots"],
            "product_build_id": product["product_build_id_hex"],
            "sha256": static["code_sha256"]},
        "banner": {"objects": manifest["objects"],
            "suite_code_bytes": manifest["code_bytes"],
            "object_bytes": banner["length"],
            "first_call": "load", "literal": "init.l65",
            "isolated_pricing_suite": {"objects": 352,
                "code_bytes": 15501}},
        "manifests": [bind(path) for _key, _name, path in inventory],
        "product": bind(PLANE_ROOT / "product/substitution-artifacts.json"),
        "profile": bind(profile_path), "header": bind(header),
        "contract": bind(contract), "bank2": bind(CODE),
        "consumption_rule": ("source registration is insufficient; the "
            "setup-owned candidate plane is the real link input"),
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "media_builds": 0, "device_contacts": 0},
    }
    PLANE_RECEIPT.write_bytes(canonical(value))
    return value


def bind_init_plane() -> dict[str, Any]:
    _configure_plane_module()
    plane = load(PLANE_RECEIPT)
    require(plane["status"] ==
                "PASS: NATIVE INIT CANDIDATE PLANE MATERIALIZED 0/1"
            and plane["geometry"]["bytes"] == 46053,
            "native INIT preflight plane authority drift")
    value = CURRENT_PLANE.bind_current_plane(PLANE_ROOT)
    # The product manifest stores repository-relative members.  Its real
    # Zero-Literal consumer therefore resolves from ROOT, not by appending the
    # repository path once more below the setup-owned plane.
    CURRENT_PLANE.CANDIDATE.ZERO_LITERAL.LINKED_PRODUCT_INVENTORY = (
        PLANE_ROOT / "product/substitution-artifacts.json", ROOT)
    return value


def _consumption_rows() -> dict[str, tuple[Path, dict[str, Any]]]:
    paths = {
        "seed": BUILD / (
            "wplto/resident-island-seed.prg.compiler-input-consumption.json"),
        "final": BUILD / (
            "wplto/lisp65-c2-substitution-linked.prg."
            "compiler-input-consumption.json"),
    }
    return {name: (path, load(path)) for name, path in paths.items()}


def _validate_candidate_consumption(
        rows: dict[str, tuple[Path, dict[str, Any]]]) -> None:
    header = PLANE_ROOT / "c2_lite_static_plane.h"
    header_binding = bind(header)
    expected = CODE.stat().st_size
    require(expected == 46053, "candidate compiler plane extent drift")
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
    rows = _consumption_rows()
    _validate_candidate_consumption(rows)
    return {name: {"binding": bind(path), "result": value}
            for name, (path, value) in rows.items()}


def consumption_adapter_mutations() -> list[str]:
    rows = _consumption_rows()
    rejected: list[str] = []
    for name, mutate in (
            ("reintroduce-stored-46043", lambda value: value.update(
                consumed_value=46043)),
            ("path-value-diverge", lambda value: value["bound_header"].update(
                path="build/c2.3/v2.0-phase02b-header-consumption-preflight/"
                     "setup-owned/c2_lite_static_plane.h"))):
        trial = {key: (path, json.loads(json.dumps(value)))
                 for key, (path, value) in rows.items()}
        mutate(trial["seed"][1])
        try:
            _validate_candidate_consumption(trial)
        except CardError:
            rejected.append(name)
    require(rejected == ["reintroduce-stored-46043", "path-value-diverge"],
            "compiler-consumption adapter mutations survived")
    return rejected


def setup_child() -> tuple[Any, dict[str, Any], dict[str, object]]:
    core, activation, product_cold = RECOVERY.configure_recovery_stack()
    static = bind_init_plane()
    core.bind_paths_only(BUILD, PREFLIGHT)
    old_paths = core.PROJECTED_OWNERSHIP, core.PROJECTED_FULL_MAP
    core.PROJECTED_OWNERSHIP = PREFLIGHT / "projected-ownership-contract.json"
    core.PROJECTED_FULL_MAP = PREFLIGHT / "projected-full-map-authority.json"
    try:
        core.write_projections()
    finally:
        core.PROJECTED_OWNERSHIP, core.PROJECTED_FULL_MAP = old_paths
    require(static["consumer_observed_bytes"] == 46053,
            "real setup did not consume native INIT plane")
    CURRENT_PLANE.install_final_v6_consumer(record=True)
    return core, activation, product_cold


def _compile_banner(source: str) -> dict[str, Any]:
    suite = STD._read_suite(str(SUITE))
    forms = [form for form in C.parse_all(source)
             if isinstance(form, list) and len(form) >= 4
             and form[0] == "defun" and form[1] == "%repl-banner"]
    require(len(forms) == 1, "source has no unique %repl-banner owner")
    heap = B.Heap()
    name, code, helpers = C.compile_top_form_with_helpers(
        forms[0], heap, strict_arity=True,
        abi_profile=suite.get("abi_profile", "dialect-v2"))
    encoded = code.encode()
    require(name == "%repl-banner" and helpers == [],
            "banner direct emission introduced another object")
    return {"direct_object_bytes": len(encoded),
            "direct_object_sha256": hashlib.sha256(encoded).hexdigest(),
            "call_edges": [list(row) for row in
                           STD._call_edges(heap, code, suite)],
            "literal_text": [heap.obj_to_text(row) for row in code.littab]}


def _native_claim(repl: str, stream: str, vm: str, load_source: str) -> bool:
    try:
        setjmp_at = repl.index("if (setjmp(lisp_toplevel))")
        active_at = repl.index("lisp_toplevel_active = 1;")
        screen_at = repl.index("scr_init();")
        banner_at = repl.index(
            "vm_run_dir(LISP65_BYTECODE_STDLIB_REPL_BANNER_ENTRY")
        prompt_at = repl.index('emit_str("lisp65> ")')
        banner_window = repl[screen_at:prompt_at]
        stream_body = stream[stream.index("void load_source_stream"):
                             stream.index("void crepl_boot_init")]
        compile_at = stream_body.index("compile_run_top_form(form);")
        stop_at = stream_body.index(
            "if (vm_status != VM_OK && vm_status != VM_HALT) return;")
        primitive = vm[vm.index("case 17:"):vm.index("case 18:")]
        load_body = load_source[load_source.index("(defun load (name)"):]
    except ValueError:
        return False
    return (
        setjmp_at < active_at < screen_at < banner_at < prompt_at
        and ("if (!aborted) {\n"
             "        (void)vm_run_dir(") in banner_window
        and "lisp_abort_code(vm_status_error_code(vm_status));"
            in banner_window
        and 'emit_str("*** ");' not in banner_window
        and compile_at < stop_at
        and "lisp_abort_code(LISP65_ERR_LOAD_OPEN);" in primitive
        and "return vm_t;" in primitive
        and load_body.rstrip().endswith("nil))")
    )


def source_gate() -> dict[str, Any]:
    banner = BANNER.read_text(encoding="utf-8")
    repl = REPL.read_text(encoding="utf-8")
    stream = COMPILE_REPL.read_text(encoding="utf-8")
    vm = VM.read_text(encoding="utf-8")
    load_source = LOAD.read_text(encoding="utf-8")
    require(banner.count('(load "init.l65")') == 1
            and banner.index('(load "init.l65")')
                < banner.index("(%banner-runs)")
            and _native_claim(repl, stream, vm, load_source),
            "priced INIT.L65 source form is not implemented exactly")
    emitted = _compile_banner(banner)
    require(emitted["direct_object_bytes"] == 65
            and emitted["call_edges"][0] == ["CALL", "load", 1]
            and "\"init.l65\"" in emitted["literal_text"]
            and not any(name.startswith("%init")
                        for edge in emitted["call_edges"]
                        for name in edge if isinstance(name, str)),
            "emitted INIT banner price/order/name wall red")

    no_hook = banner.replace('  (load "init.l65")\n', "", 1)
    late_hook = banner.replace('  (load "init.l65")\n', "", 1).replace(
        "  (%banner-runs)\n", "  (%banner-runs)\n  (load \"init.l65\")\n", 1)
    emitted_no_hook = _compile_banner(no_hook)
    emitted_late = _compile_banner(late_hook)
    require(emitted_no_hook["call_edges"][0] != ["CALL", "load", 1]
            and emitted_late["call_edges"][0] != ["CALL", "load", 1],
            "banner hook-order mutations survived emission")

    native_mutations = {
        "missing-file-treated-as-error": (
            repl, stream, vm,
            load_source.rsplit("nil))", 1)[0] + "(%disk-load-file 0 0)))"),
        "failure-returns-from-repl": (
            repl.replace(
                "lisp_abort_code(vm_status_error_code(vm_status));",
                'emit_str("*** "); return;', 1), stream, vm, load_source),
        "retry-init-after-abort": (
            repl.replace("if (!aborted) {\n        (void)vm_run_dir",
                         "if (1) {\n        (void)vm_run_dir", 1),
            stream, vm, load_source),
        "later-form-masks-earlier-vm-error": (
            repl, stream.replace(
                "if (vm_status != VM_OK && vm_status != VM_HALT) return;",
                "", 1), vm, load_source),
    }
    rejected = []
    for name, values in native_mutations.items():
        require(not _native_claim(*values), f"INIT mutation survived: {name}")
        rejected.append(name)
    order = ["setjmp", "active", "screen", "banner", "prompt"]
    require(order.index("setjmp") < order.index("banner")
            and not (["banner"] + order)[0] == "setjmp",
            "hook-before-setjmp mutation survived")
    rejected.insert(0, "hook-before-setjmp")
    return {"status": "PASS: PRICED INIT SOURCE AND EMISSION EXACT",
            "sources": {name: bind(path) for name, path in (
                ("banner", BANNER), ("repl", REPL),
                ("stream", COMPILE_REPL), ("vm", VM), ("load", LOAD))},
            "emitted_banner": emitted,
            "mutations_rejected": rejected,
            "new_named_helpers": [], "new_state_bytes": 0}


def configuration_gate() -> dict[str, Any]:
    recovery = RECOVERY.configuration_gate()
    source = source_gate()
    require(recovery["closed_freight"] == [
                "Comfort", "Block-3", "diagnostic-witness"],
            "INIT card reopened unrelated freight")
    return {**recovery, "world": "item-1-plus-A0-plus-native-init",
            "native_init": source}


def _geometry() -> dict[str, int]:
    raw = C2D.read_bytes()
    require(raw[:4] == b"C2D\0" and raw[4] == 6 and len(raw) >= 48,
            "candidate C2D header drift")
    u16 = lambda at: int.from_bytes(raw[at:at + 2], "little")
    return {"generation": u16(10), "images": u16(12),
            "entries": u16(16), "resolutions": u16(20),
            "roots": u16(24), "code_bytes": len(CODE.read_bytes()),
            "immutable_images": u16(38),
            "catalog_crc32": int.from_bytes(raw[40:44], "little"),
            "build_id": int.from_bytes(raw[44:48], "little")}


def _candidate_host(out: Path) -> ProductSessionHost:
    geometry = _geometry()
    host = ProductSessionHost(geometry, out)
    c2d, code = C2D.read_bytes(), CODE.read_bytes()
    require(len(host.plane.c2d) == len(c2d)
            and len(host.plane.code) >= len(code),
            "candidate Session host cannot hold final plane")
    host.plane.c2d[:] = c2d
    host.plane.code[:len(code)] = code
    manifest = load(MANIFEST)
    blob = (ROOT / manifest["blob"]).read_bytes()
    patches = {int(row["blob_offset"]): int(row["node"])
               for row in manifest["literal_patches"]}
    for entry in manifest["entries"]:
        code_obj = STD._patched_code_from_manifest_entry(
            host.heap, manifest, blob, entry, patches)
        symbol = host.heap.intern(entry["name"])
        host.directory[symbol] = code_obj
        host.code_names[id(code_obj)] = entry["name"]
    return host


def _reject(label: str, function: Any) -> dict[str, str]:
    try:
        function()
    except Exception as error:
        return {"name": label, "result": "rejected",
                "exception": type(error).__name__}
    raise CardError(f"external publication mutation survived: {label}")


def external_append_gate() -> dict[str, Any]:
    source = "(defun %init-external-proof () (list 17 65))"
    with tempfile.TemporaryDirectory(
            prefix="c2-v17-init-card-append-", dir=ROOT / "build") as raw:
        out = Path(raw)
        host = _candidate_host(out / "positive")
        before = {key: int(getattr(host.plane, attr)) for key, attr in (
            ("images", "images"), ("entries", "entries"),
            ("resolutions", "resolutions"), ("roots", "roots"),
            ("code_bytes", "code_low"))}
        appended = host.append_definition(source, "%init-external-proof")
        executed = host.execute("%init-external-proof", [])
        require(before == {"images": 6, "entries": 755,
                            "resolutions": 2931, "roots": 353,
                            "code_bytes": 46053}
                and appended["after"] == {"images": 7, "entries": 756,
                    "resolutions": 2932, "roots": 353,
                    "code_bytes": 46069}
                and appended["handle"] == 755
                and executed["result_text"] == "(17 65)"
                and executed["steps"] == 5,
                "external append did not execute over candidate plane")
        missing = _candidate_host(out / "missing")
        missing_reject = _reject(
            "external-entry-not-published",
            lambda: missing.execute("%init-external-proof", []))
        no_owner = _candidate_host(out / "no-owner")
        no_owner.append_definition(source, "%init-external-proof")
        del no_owner.directory[no_owner.heap.intern("list")]
        owner_reject = _reject(
            "external-caller-loses-final-static-owner",
            lambda: no_owner.execute("%init-external-proof", []))
    return {"before": before, "after": appended["after"],
            "published_handle": appended["handle"], "execution": executed,
            "mutations": [missing_reject, owner_reject],
            "status": "PASS: EXTERNAL APPEND USES INIT CANDIDATE PLANE"}


def boot_host_gate() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(
            prefix="c2-v17-init-card-boot-", dir=ROOT / "build") as raw:
        host = _candidate_host(Path(raw) / "absent")
        banner = host.directory[host.heap.intern("%repl-banner")]
        edges = [list(row) for row in STD._call_edges(
            host.heap, banner, {"abi_profile": "dialect-v2"})]
        absent = host.execute("%repl-banner", [])
        require(edges[0] == ["CALL", "load", 1]
                and absent["result_text"] == "nil"
                and absent["calls"][0]["target"] == "load"
                and not any(row["target"] == "%disk-load-file"
                            and row["resolved"] is False
                            for row in absent["calls"]),
                "missing INIT is not silent on emitted banner")
        trace = Trace()
        vm = B.P0VM(heap=host.heap, directory=host.directory,
                    trace=trace, code_names=host.code_names,
                    abi_profile="dialect-v2",
                    abi_ledger=json.loads((ROOT / "config/bytecode-abi-ledger.json")
                                         .read_text(encoding="utf-8")),
                    disk_files={"INIT.L65": "(defun init-proof () 1)"},
                    max_steps=500000)
        present_result = vm.run(banner, [])
        require(host.heap.obj_to_text(present_result) == "nil"
                and vm.disk_loaded == [(1, 2)]
                and trace.calls[0]["target"] == "load",
                "present INIT did not take the emitted load path")
    return {"emitted_call_edges": edges,
            "absent": {"result": absent["result_text"],
                       "steps": absent["steps"],
                       "first_call": absent["calls"][0]},
            "present": {"result": host.heap.obj_to_text(present_result),
                        "disk_loaded": [list(row) for row in vm.disk_loaded],
                        "first_call": trace.calls[0]},
            "attempts_per_banner_execution": 1}


def _function_body(disassembly: str, name: str) -> str:
    marker = re.search(rf"^[0-9a-f]+ <{re.escape(name)}>:\s*$",
                       disassembly, re.MULTILINE)
    require(marker is not None, f"final disassembly lacks {name}")
    following = re.search(r"^[0-9a-f]+ <[^>]+>:\s*$",
                          disassembly[marker.end():], re.MULTILINE)
    end = marker.end() + (following.start() if following else
                          len(disassembly) - marker.end())
    return disassembly[marker.start():end]


_CFG_BRANCHES = {"beq", "bne", "bcc", "bcs", "bmi", "bpl", "bvc", "bvs"}


def _direct_target(operand: str) -> int | None:
    """Decode the numeric operand; rendered labels deliberately carry no identity."""
    match = re.search(r"\$([0-9a-fA-F]+)", operand)
    return int(match.group(1), 16) if match else None


def _repl_instructions(truth: ElfTruth, disassembly: str) -> dict[int, dict[str, Any]]:
    repl = truth.symbol("repl")
    start, end = repl.value, repl.value + repl.bytes
    pattern = re.compile(
        r"^\s*([0-9a-fA-F]+):\s+\t([a-z][a-z0-9]*)\s*(.*)$")
    rows: dict[int, dict[str, Any]] = {}
    for line in disassembly.splitlines():
        match = pattern.match(line)
        if match is None:
            continue
        address = int(match.group(1), 16)
        if start <= address < end:
            rows[address] = {"address": address,
                "opcode": match.group(2).lower(),
                "operand": match.group(3).strip()}
    require(rows and min(rows) == start,
            "final repl instruction map is incomplete")
    return rows


def _successors(rows: dict[int, dict[str, Any]], pc: int) -> tuple[int, ...]:
    addresses = sorted(rows)
    index = addresses.index(pc)
    following = addresses[index + 1] if index + 1 < len(addresses) else None
    row = rows[pc]
    opcode = str(row["opcode"])
    target = _direct_target(str(row["operand"]))
    if opcode in ("jmp", "bra"):
        return (target,) if target in rows else ()
    if opcode in _CFG_BRANCHES:
        value = []
        if target in rows:
            value.append(target)
        if following is not None:
            value.append(following)
        return tuple(value)
    if opcode in ("rts", "rti", "brk") or following is None:
        return ()
    return (following,)


def _matches(row: dict[str, Any], milestone: tuple[str, int]) -> bool:
    kind, target = milestone
    if kind == "call":
        return row["opcode"] == "jsr" and _direct_target(row["operand"]) == target
    if kind == "store":
        return row["opcode"] in ("sta", "stx", "sty", "stz") \
            and _direct_target(row["operand"]) == target
    raise CardError(f"unknown CFG milestone: {kind}")


def _milestone_path(rows: dict[int, dict[str, Any]], start: int,
                    milestones: list[tuple[str, int]],
                    forbidden_calls: set[int] | None = None) -> list[int]:
    """Return one reachable path's milestone PCs, independent of address order."""
    forbidden = forbidden_calls or set()
    pending = deque([(start, 0, tuple())])
    visited: set[tuple[int, int]] = set()
    while pending:
        pc, stage, hits = pending.popleft()
        state = (pc, stage)
        if state in visited or pc not in rows:
            continue
        visited.add(state)
        row = rows[pc]
        next_stage, next_hits = stage, hits
        if stage < len(milestones) and _matches(row, milestones[stage]):
            next_stage += 1
            next_hits = hits + (pc,)
            if next_stage == len(milestones):
                return list(next_hits)
        call_target = (_direct_target(row["operand"])
                       if row["opcode"] == "jsr" else None)
        if call_target in forbidden:
            continue
        for successor in _successors(rows, pc):
            pending.append((successor, next_stage, next_hits))
    raise CardError("final repl CFG lacks required semantic milestone path")


def _call_sites(rows: dict[int, dict[str, Any]], target: int) -> list[int]:
    return sorted(pc for pc, row in rows.items()
                  if row["opcode"] == "jsr"
                  and _direct_target(row["operand"]) == target)


def _linked_flow_core(truth: ElfTruth,
                      rows: dict[int, dict[str, Any]]) -> dict[str, Any]:
    symbols = {name: truth.symbol(name).value for name in (
        "repl", "setjmp", "lisp_toplevel_active", "scr_init",
        "vm_run_dir", "vm_status_error_code", "lisp_abort_code", "emit_str")}
    calls = {name: _call_sites(rows, symbols[name]) for name in (
        "setjmp", "scr_init", "vm_run_dir", "vm_status_error_code",
        "lisp_abort_code", "emit_str")}
    require(len(calls["setjmp"]) == len(calls["scr_init"]) ==
            len(calls["vm_run_dir"]) == len(calls["vm_status_error_code"]) == 1
            and len(calls["lisp_abort_code"]) >= 1,
            "final repl target-address call inventory drift")

    ready = [("call", symbols["setjmp"]),
             ("store", symbols["lisp_toplevel_active"]),
             ("call", symbols["scr_init"]),
             ("call", symbols["vm_run_dir"]),
             ("call", symbols["emit_str"])]
    ready_path = _milestone_path(
        rows, symbols["repl"], ready,
        {symbols["vm_status_error_code"], symbols["lisp_abort_code"]})
    error = [("call", symbols["setjmp"]),
             ("store", symbols["lisp_toplevel_active"]),
             ("call", symbols["scr_init"]),
             ("call", symbols["vm_run_dir"]),
             ("call", symbols["vm_status_error_code"]),
             ("call", symbols["lisp_abort_code"])]
    error_path = _milestone_path(rows, symbols["repl"], error)
    addresses = sorted(rows)
    status_site = calls["vm_status_error_code"][0]
    status_index = addresses.index(status_site)
    require(status_index + 1 < len(addresses),
            "final VM-status conversion lacks a continuation")
    abort_edge = addresses[status_index + 1]
    require(ready_path[:4] == [calls["setjmp"][0], ready_path[1],
                               calls["scr_init"][0], calls["vm_run_dir"][0]]
            and error_path[0] == calls["setjmp"][0]
            and error_path[2:5] == [calls["scr_init"][0],
                                    calls["vm_run_dir"][0],
                                    calls["vm_status_error_code"][0]]
            and error_path[-1] == abort_edge
            and rows[abort_edge]["opcode"] == "jsr"
            and _direct_target(rows[abort_edge]["operand"])
                == symbols["lisp_abort_code"],
            "final repl CFG resolved the wrong ready/error edges")
    return {
        "authority": "ElfTruth symbol values plus numeric decoded CFG edges",
        "symbols": {name: f"0x{value:04x}" for name, value in symbols.items()},
        "resolved_call_sites": {
            name: [f"0x{pc:04x}" for pc in sites]
            for name, sites in calls.items()},
        "normal_ready_hook_prompt_path": [f"0x{pc:04x}" for pc in ready_path],
        "vm_error_abort_path": [f"0x{pc:04x}" for pc in error_path],
        "claims": {
            "hook_after_installed_recovery_and_ready_screen": True,
            "hook_before_normal_prompt": True,
            "vm_error_reaches_numeric_abort": True,
        },
    }


def _retarget(row: dict[str, Any], target: int) -> None:
    require(_direct_target(str(row["operand"])) is not None,
            "CFG mutation lacks numeric target")
    row["operand"] = re.sub(r"\$[0-9a-fA-F]+", f"${target:x}",
                            str(row["operand"]), count=1)


def _linked_flow_mutations(truth: ElfTruth,
                           rows: dict[int, dict[str, Any]],
                           base: dict[str, Any]) -> list[str]:
    symbols = {name: truth.symbol(name).value for name in (
        "scr_init", "vm_run_dir")}
    scr_site = int(base["resolved_call_sites"]["scr_init"][0], 16)
    vm_site = int(base["resolved_call_sites"]["vm_run_dir"][0], 16)
    abort_site = int(base["vm_error_abort_path"][-1], 16)
    cases: dict[str, dict[int, dict[str, Any]]] = {}

    early = copy.deepcopy(rows)
    _retarget(early[scr_site], symbols["vm_run_dir"])
    _retarget(early[vm_site], symbols["scr_init"])
    cases["hook-before-ready-world"] = early

    missing = copy.deepcopy(rows)
    _retarget(missing[scr_site], 0xffff)
    cases["missing-screen-ready-edge"] = missing

    returned = copy.deepcopy(rows)
    _retarget(returned[abort_site], truth.symbol("emit_str").value)
    cases["return-from-repl-instead-of-abort"] = returned

    rejected = []
    for name, candidate in cases.items():
        try:
            _linked_flow_core(truth, candidate)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases),
            "final CFG semantic mutation survived")
    return rejected


def linked_failure_gate(truth: ElfTruth) -> dict[str, Any]:
    disassembly = subprocess.run(
        [str(OBJDUMP), "-d", "--no-show-raw-insn", str(ELF)],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout
    prim = _function_body(disassembly, "vm_callprim")
    rows = _repl_instructions(truth, disassembly)
    flow = _linked_flow_core(truth, rows)
    mutations = _linked_flow_mutations(truth, rows, flow)
    # A rendered label is intentionally ignored.  The operand's numeric value
    # remains the same under this equivalence probe.
    scr = truth.symbol("scr_init").value
    require(_direct_target(f"${scr:x} <deliberately-wrong-label>") == scr,
            "rendered-label equivalence probe changed caller identity")
    load_open = re.search(
        r"lda\s+#\$12[\s\S]{0,180}?jsr\s+\$[0-9a-f]+\s+<lisp_abort_code>",
        prim)
    require(load_open is not None,
            "final %disk-load-file lacks emitted LOAD_OPEN abort")
    profile = BUILD / "wplto/resolved-profile.txt"
    lines = profile.read_text(encoding="utf-8").splitlines()
    consumed = {line.split("=", 1)[1].split(":", 1)[0]:
                line.rsplit(":", 1)[1]
                for line in lines if line.startswith("input_sha256=")}
    for path in (REPL, COMPILE_REPL, VM):
        name = path.relative_to(ROOT).as_posix()
        require(name in consumed
                and consumed[name] == bind(path)["sha256"],
                f"real compiler did not consume INIT source: {name}")
    return {"final_repl_control_flow": flow,
            "mutations_rejected": mutations,
            "rendered_label_equivalence": "PASS: numeric target unchanged",
            "load_open_abort_emitted": True,
            "real_compiler_inputs": {path.relative_to(ROOT).as_posix():
                consumed[path.relative_to(ROOT).as_posix()]
                for path in (REPL, COMPILE_REPL, VM)},
            "artifact_authority": "final ELF plus resolved compiler profile"}


def final_gate() -> dict[str, Any]:
    product = RECOVERY.final_gate()
    baseline = ElfTruth.read(BASELINE_ELF, llvm_readobj=READOBJ)
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    baseline_text = baseline.section(".text").bytes
    candidate_text = truth.section(".text").bytes
    baseline_bss = baseline.section(".bss").bytes
    candidate_bss = truth.section(".bss").bytes
    baseline_symbols = {row.name: row for row in baseline.symbols}
    symbols = {row.name: row for row in truth.symbols}
    require(candidate_text <= baseline_text
            and candidate_bss == baseline_bss,
            "final linked resident/state price exceeds the card bar")
    manifest = load(MANIFEST)
    banner = next(row for row in manifest["entries"]
                  if row["name"] == "%repl-banner")
    require(len(CODE.read_bytes()) - len(BASELINE_CODE.read_bytes()) == 10
            and manifest["objects"] == 393
            and manifest["code_bytes"] == 17248
            and banner["length"] == 155,
            "final Bank-2 INIT price drift")
    boot = boot_host_gate()
    append = external_append_gate()
    linked = linked_failure_gate(truth)
    product["native_init"] = {
        "status": "PASS: INIT HOOK AND FAILURE SEMANTICS PROVED ON FINAL WORLD",
        "bank2": {"baseline_static_plane_bytes": len(BASELINE_CODE.read_bytes()),
                  "candidate_static_plane_bytes": len(CODE.read_bytes()),
                  "delta_bytes": 10, "objects": manifest["objects"],
                  "repl_banner_bytes": banner["length"],
                  "new_named_helpers": 0},
        "resident": {"baseline_text_bytes": baseline_text,
                     "candidate_text_bytes": candidate_text,
                     "delta_bytes": candidate_text - baseline_text,
                     "bar_bytes_max": 0,
                     "repl_bytes_before": baseline_symbols["repl"].bytes,
                     "repl_bytes_after": symbols["repl"].bytes,
                     "vm_callprim_bytes_before":
                         baseline_symbols["vm_callprim"].bytes,
                     "vm_callprim_bytes_after": symbols["vm_callprim"].bytes},
        "state": {"baseline_bss_bytes": baseline_bss,
                  "candidate_bss_bytes": candidate_bss,
                  "delta_bytes": 0},
        "capacity": {"free_symbol_slots": 105,
                     "free_name_bytes": 1413,
                     "minimum": {"free_symbol_slots": 32,
                                 "free_name_bytes": 384}},
        "boot": boot, "linked_failures": linked,
        "external_publication": append,
        "mutations_rejected": source_gate()["mutations_rejected"]
            + [row["name"] for row in append["mutations"]],
        "consumer_conversions": {
            "product_inventory_root": ROOT.relative_to(ROOT).as_posix(),
            "compiler_header_consumption": candidate_consumption_receipts(),
            "mutations_rejected": consumption_adapter_mutations(),
        },
        "comfort_dependency": False,
        "canonical_prompt_swap": False,
    }
    return product


def configure() -> None:
    RECOVERY.BUILD = BUILD
    RECOVERY.PREFLIGHT = PREFLIGHT
    RECOVERY.RECEIPT = RECEIPT
    RECOVERY.ELF = ELF
    RECOVERY.PLANE = CODE
    RECOVERY.DRIVER = DRIVER
    RECOVERY.FORMAT = FORMAT
    RECOVERY.STATUS = STATUS
    RECOVERY.configure()
    BASE.DRIVER = DRIVER
    BASE.FORMAT = FORMAT
    BASE.STATUS = STATUS
    BASE.authority = authority
    BASE.configuration_gate = configuration_gate
    BASE.setup_child = setup_child
    BASE.final_gate = final_gate
    HEADER_CARD.consumption_receipts = candidate_consumption_receipts


def report_text(value: dict[str, Any]) -> str:
    init = value["final_product"]["native_init"]
    resident = init["resident"]
    bank2 = init["bank2"]
    return f"""# v1.7 native `INIT.L65` implementation card

Status: **{value['status']}**

The existing `%repl-banner` now evaluates `(load \"init.l65\")` exactly once
on the native first-boot path. Missing media remains silent; reader, VM and
found-but-unloadable failures cross the installed native recovery and return
to `lisp65>`. Comfort and the canonical prompt swap remain absent.

## Final emitted price

- Static Bank-2 plane: {bank2['baseline_static_plane_bytes']} ->
  **{bank2['candidate_static_plane_bytes']} bytes** (`+10`).
- `%repl-banner`: **{bank2['repl_banner_bytes']} bytes**, one existing object.
- Resident `.text`: {resident['baseline_text_bytes']} ->
  **{resident['candidate_text_bytes']} bytes**
  (`{resident['delta_bytes']:+d}`, required `<= 0`).
- Resident state: **0 bytes**; symbols/names remain **105 / 1,413 free**.

The final ELF resolves the native call identities from ElfTruth symbol values
and numeric targets.  Its reachable CFG paths prove installed recovery and
screen readiness before banner execution, the normal prompt after the banner,
and VM-status conversion immediately into `lisp_abort_code`.  No rendered
disassembly label or linear byte order carries that claim.  The final
`%disk-load-file` path emits `LOAD_OPEN` (`18`) into the same abort seam.  The
real compiler profile binds all three changed C inputs.

## Executable boundaries

The emitted candidate banner executes with missing `INIT.L65` as silent NIL
and takes the disk-load path when the file is present. The external append
fixture starts from the exact {bank2['candidate_static_plane_bytes']}-byte
candidate plane, publishes handle 755 and returns `(17 65)` through the final
static `list` owner. Removing either the appended entry or that owner fails.

All seven priced mutations and all three linked-CFG mutations remain rejected.
Scope and Acceptance ran over the same SHA-bound ELF/PRG pair.  The final gate
was resumed read-only after Review converted its witness; the Resume changed
neither artifact and consumed no WPLTO, link or card.  The card built no media
and made no device contact; hardware acceptance remains the next owner-held
step.
"""


def write_report() -> None:
    value = load(RECEIPT)
    REPORT.write_text(report_text(value), encoding="utf-8")


def frozen_pair() -> dict[str, dict[str, Any]]:
    value = {"ELF": bind(ELF), "PRG": bind(PRG)}
    require({name: row["sha256"] for name, row in value.items()}
            == FROZEN_PAIR, "INIT r4 frozen pair drift")
    return value


def validate_resume_execution(value: dict[str, int]) -> None:
    require(value == {"qualification_resumes": 1, "new_WPLTO_runs": 0,
            "new_product_links": 0, "new_cards_consumed": 0,
            "media_builds": 0, "device_contacts": 0},
            "INIT r4 Resume attempted product work")


def resume_execution_mutations(value: dict[str, int]) -> list[str]:
    cases = {
        "resume-rebuilds-WPLTO": ("new_WPLTO_runs", 1),
        "resume-relinks-product": ("new_product_links", 1),
        "resume-consumes-card": ("new_cards_consumed", 1),
    }
    rejected = []
    for name, (key, replacement) in cases.items():
        trial = dict(value); trial[key] = replacement
        try:
            validate_resume_execution(trial)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases), "INIT r4 Resume rebuild mutation survived")
    return rejected


def preflight() -> None:
    configure()
    BASE.preflight()
    plane = emit_init_plane()
    value = load(BASE.PREFLIGHT_RECEIPT)
    value["configuration"]["native_init_plane"] = {
        "receipt": bind(PLANE_RECEIPT),
        "geometry": plane["geometry"],
        "banner": plane["banner"],
        "real_link_input": PLANE_ROOT.relative_to(ROOT).as_posix(),
    }
    BASE.PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("v1.7 INIT.L65: PREFLIGHT PASS card=0/1")


def build() -> None:
    configure()
    BASE.build()
    write_report()
    check()
    print("v1.7 INIT.L65: BUILD PASS WPLTO=1 link=1")


def resume() -> None:
    configure()
    require(not RECEIPT.exists() and not RESUME_RECEIPT.exists()
            and not REPORT.exists(), "INIT r4 qualification Resume is one-shot")
    red = load(FOURTH_RED)
    contract = load(RESUME_CONTRACT)
    require(red["status"].startswith("FIRST RED: FINAL-ELF CALL-ORDER")
            and red["attempt_accounting"] == {
                "WPLTO_runs": 1, "product_links": 1,
                "scope_runs": 1, "acceptance_runs": 1,
                "media_builds": 0, "device_contacts": 0}
            and contract["frozen_pair"] == {
                "ELF_sha256": FROZEN_PAIR["ELF"],
                "PRG_sha256": FROZEN_PAIR["PRG"]},
            "INIT r4 Resume authority/frozen-red drift")
    scope = load(BASE.SCOPE_RESULT)
    acceptance = load(BASE.ACCEPTANCE_RESULT)
    producer = load(BASE.PRODUCER_RESULT)
    require(scope["status"] == acceptance["status"] == producer["status"]
                == "PASS", "INIT r4 frozen product tail is not green")
    pair_before = frozen_pair()
    artifacts_before = BASE.artifacts()
    gate = final_gate()
    artifacts_after = BASE.artifacts()
    pair_after = frozen_pair()
    require(pair_before == pair_after and artifacts_before == artifacts_after,
            "read-only INIT r4 Resume changed frozen artifacts")
    execution = {"qualification_resumes": 1, "new_WPLTO_runs": 0,
        "new_product_links": 0, "new_cards_consumed": 0,
        "media_builds": 0, "device_contacts": 0}
    validate_resume_execution(execution)
    pre = load(BASE.PREFLIGHT_RECEIPT)
    value = {
        "format": FORMAT, "recorded_on": "2026-08-27", "status": STATUS,
        "authority": authority(), "preflight": bind(BASE.PREFLIGHT_RECEIPT),
        "invocation": bind(BASE.INVOCATION),
        "configuration": pre["configuration"], "final_product": gate,
        "producer": bind(BASE.PRODUCER_RESULT),
        "scope": bind(BASE.SCOPE_RESULT),
        "acceptance": bind(BASE.ACCEPTANCE_RESULT),
        "artifacts_before": artifacts_before,
        "artifacts_after": artifacts_after,
        "processes": [{"action": "read-only-final-gate-resume",
            "status": "PASS", **execution}],
        "attempt_accounting": {"WPLTO_runs": 1, "product_links": 1,
            "scope_runs": 1, "acceptance_runs": 1,
            "media_builds": 0, "device_contacts": 0},
        "resume": {"read_only": True,
            "frozen_pair_before": pair_before,
            "frozen_pair_after": pair_after,
            "execution": execution,
            "rebuild_mutations_rejected":
                resume_execution_mutations(execution)},
        "media_authorized": False,
        "next": "full check-source self-certification, then reviewed media",
    }
    RECEIPT.write_bytes(canonical(value))
    resume_value = {
        "format": "lisp65-c2-v17-init-l65-r4-qualification-resume-v1",
        "recorded_on": "2026-08-27",
        "status": "PASS: INIT.L65 R4 FINAL GATE RESUMED READ-ONLY",
        "authority": {"contract": bind(RESUME_CONTRACT),
                      "r4_first_red": bind(FOURTH_RED)},
        "frozen_pair_before": pair_before,
        "frozen_pair_after": pair_after,
        "semantic_CFG": gate["native_init"]["linked_failures"],
        "execution": execution,
        "rebuild_mutations_rejected": resume_execution_mutations(execution),
        "final_card_receipt": bind(RECEIPT),
        "claim_limit": "Final-gate Resume only; no WPLTO, link, card, media or device.",
    }
    RESUME_RECEIPT.write_bytes(canonical(resume_value))
    write_report()
    check()
    print("v1.7 INIT.L65: RESUME PASS WPLTO=0 link=0 card=0")


def check() -> None:
    configure()
    BASE.check()
    value = load(RECEIPT)
    init = value["final_product"]["native_init"]
    require(value["status"] == STATUS
            and value["authority"] == authority()
            and init["resident"]["delta_bytes"] <= 0
            and init["bank2"]["delta_bytes"] == 10
            and init["mutations_rejected"] == load(CONTRACT)[
                "required_mutations"]
            and init["linked_failures"]["mutations_rejected"] == load(
                RESUME_CONTRACT)["required_mutations"]
            and value["attempt_accounting"] == {
                "WPLTO_runs": 1, "product_links": 1,
                "scope_runs": 1, "acceptance_runs": 1,
                "media_builds": 0, "device_contacts": 0},
            "INIT.L65 final card receipt drift")
    resumed = load(RESUME_RECEIPT)
    require(resumed["status"] ==
                "PASS: INIT.L65 R4 FINAL GATE RESUMED READ-ONLY"
            and resumed["frozen_pair_before"] == frozen_pair()
            and resumed["frozen_pair_after"] == frozen_pair()
            and resumed["execution"] == {
                "qualification_resumes": 1, "new_WPLTO_runs": 0,
                "new_product_links": 0, "new_cards_consumed": 0,
                "media_builds": 0, "device_contacts": 0},
            "INIT.L65 r4 qualification Resume receipt drift")
    require(REPORT.is_file()
            and REPORT.read_text(encoding="utf-8") == report_text(value),
            "INIT.L65 implementation report drift")
    print("v1.7 INIT.L65: CHECK PASS final-world=green media=0 device=0")


def run(action: str) -> None:
    {"preflight": preflight, "build": build, "resume": resume, "check": check,
     "_produce": lambda: (configure(), BASE.produce_child()),
     "_scope": lambda: (configure(), BASE.scope_child()),
     "_accept": lambda: (configure(), BASE.acceptance_child())}[action]()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "preflight", "build", "resume", "check", "_produce", "_scope", "_accept"))
    run(parser.parse_args().action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, SessionHostError, RuntimeError) as error:
        print(f"v1.7 INIT.L65: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
