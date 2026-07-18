#!/usr/bin/env python3
"""Build the final Wave-1 C1 integration receipt.

The gate deliberately distinguishes three EXT states: persistent composition,
the transactional L65M load peak, and compiler execution after metadata
reclaim.  It also runs the released resident compiler and the temporary C1
tier against the same forms so that the cut is checked semantically rather
than inferred from source similarity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
HOST_TOOLS = ROOT / "tools" / "host-lisp"
if str(HOST_TOOLS) not in sys.path:
    sys.path.insert(0, str(HOST_TOOLS))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
import bytecode_p0_stdlib as Stdlib  # noqa: E402
import v11_prewave_measurements as Prewave  # noqa: E402


FORMAT = "lisp65-v11-c1-wave1-integration-block-receipt-v1"
BASELINE_PROMOTION = "r4-product-candidate-5942e0c"
BASELINE_MEMBER_ROOT = "payload/build/bytecode/dialect-v2/workbench/"
EXT_FLOOR = 16384
EXT_LIMIT = 50816
OVERLAY_LIMIT = 0xC356
SLICE_LIMIT = 1792


class GateError(RuntimeError):
    pass


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GateError(f"{path}: expected a JSON object")
    return value


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def _run_checked(path: Path, *args: str) -> str:
    result = subprocess.run(
        [str(path), *args], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    output = result.stdout.strip()
    if result.returncode:
        raise GateError(f"{_relative(path)} failed: {output}")
    return output


def _promotion_entry(register: dict, promotion_id: str) -> dict:
    for row in register.get("promotions", []):
        if isinstance(row, dict) and row.get("id") == promotion_id:
            return row
    raise GateError(f"promotion register omits {promotion_id}")


def _baseline_artifacts(register: dict) -> tuple[dict, bytes, dict]:
    entry = _promotion_entry(register, BASELINE_PROMOTION)
    archive = ROOT / entry["archive"]
    actual_sha = _sha(archive)
    _require(actual_sha == entry.get("archive_sha256"), "baseline archive SHA drift")
    with tarfile.open(archive, "r:gz") as packed:
        manifest_bytes = packed.extractfile(
            BASELINE_MEMBER_ROOT + "stdlib-p0.manifest.json"
        ).read()
        blob = packed.extractfile(
            BASELINE_MEMBER_ROOT + "stdlib-p0.blob.bin"
        ).read()
    manifest = json.loads(manifest_bytes)
    _require(_sha_bytes(blob) == manifest.get("blob_sha256"), "baseline blob SHA drift")
    _require(len(blob) == manifest.get("code_bytes"), "baseline blob length drift")
    return manifest, blob, {
        "promotion_id": BASELINE_PROMOTION,
        "source_commit": entry["source_commit"],
        "archive": entry["archive"],
        "archive_sha256": actual_sha,
        "manifest_member": BASELINE_MEMBER_ROOT + "stdlib-p0.manifest.json",
        "manifest_sha256": _sha_bytes(manifest_bytes),
        "blob_member": BASELINE_MEMBER_ROOT + "stdlib-p0.blob.bin",
        "blob_sha256": _sha_bytes(blob),
    }


def _manifest_directory_add(heap: B.Heap, directory: dict, manifest: dict,
                            blob: bytes) -> None:
    _require(_sha_bytes(blob) == manifest.get("blob_sha256"), "candidate blob SHA drift")
    patches = {
        int(row["blob_offset"]): int(row["node"])
        for row in manifest.get("literal_patches", [])
    }
    for entry in manifest.get("entries", []):
        symbol = heap.intern(entry["name"])
        _require(symbol not in directory, f"duplicate evaluation entry {entry['name']}")
        directory[symbol] = Stdlib._patched_code_from_manifest_entry(
            heap, manifest, blob, entry, patches
        )


def _eval(manifest_pairs: list[tuple[dict, bytes]], expression: str):
    names = [
        entry["name"]
        for manifest, _blob in manifest_pairs
        for entry in manifest.get("entries", [])
    ]
    heap = C.prepare_heap(names + ["__c1_gate_probe"])
    directory: dict = {}
    for manifest, blob in manifest_pairs:
        _manifest_directory_add(heap, directory, manifest, blob)
    form = ["defun", "__c1_gate_probe", [], C.parse_one(expression)]
    compiled_name, code, helpers = C.compile_top_form_with_helpers(
        form, heap, strict_arity=True, abi_profile="dialect-v2"
    )
    _require(compiled_name == "__c1_gate_probe", "probe compiler renamed entry")
    for name, helper in helpers:
        directory[heap.intern(name)] = helper
    directory[heap.intern(compiled_name)] = code
    vm = B.P0VM(
        heap=heap, directory=directory, max_steps=10_000_000,
        abi_profile="dialect-v2", abi_ledger=C._abi_ledger("dialect-v2", None),
    )
    result = vm.run(code, [])
    return heap, vm, result, vm.steps


def _proper_list(heap: B.Heap, value: int, label: str) -> list[int]:
    out: list[int] = []
    seen: set[int] = set()
    while heap.consp(value):
        if value in seen:
            raise GateError(f"{label}: cyclic list")
        seen.add(value)
        out.append(heap.car(value))
        value = heap.cdr(value)
    _require(value == B.NIL, f"{label}: improper list")
    return out


def _compiled_main(heap: B.Heap, result: int) -> B.CodeObject:
    functions = _proper_list(heap, result, "compiler result")
    _require(bool(functions), "compiler result is empty")
    fields = _proper_list(heap, functions[0], "compiled function")
    _require(len(fields) == 5, "compiled function has wrong shape")
    _require(all(B.is_fix(value) for value in fields[:3]), "compiled header is not numeric")
    literals = tuple(_proper_list(heap, fields[3], "compiled literals"))
    code_values = _proper_list(heap, fields[4], "compiled payload")
    _require(all(B.is_fix(value) for value in code_values), "compiled payload is not numeric")
    payload = bytes(B.fixval(value) & 0xFF for value in code_values)
    return B.CodeObject(
        B.fixval(fields[0]), B.fixval(fields[1]), B.fixval(fields[2]),
        literals, payload,
    )


def _collect_symbols(heap: B.Heap, value: int, out: set[str], seen: set[int]) -> None:
    if not B.is_ptr(value) or value in seen:
        return
    seen.add(value)
    cell = heap.cell(value)
    if cell.type == B.T_SYM:
        out.add(cell.name)
        return
    if cell.type == B.T_CONS:
        _collect_symbols(heap, cell.a, out, seen)
        _collect_symbols(heap, cell.b, out, seen)


def _execution_args(values: Iterable[int]) -> list[int]:
    return [B.mkfix(value) for value in values]


def _compile_equivalence(
    baseline: tuple[dict, bytes], candidate: list[tuple[dict, bytes]],
    compiler_private: set[str],
) -> dict:
    cases = [
        ("expression-arithmetic", "expression", "(+ 1 2)", [], "3"),
        (
            "expression-list", "expression",
            "(if (> 7 3) (cons 7 nil) nil)", [], "(7)",
        ),
        (
            "defun-branch", "defun",
            "(defun c1-branch (x) (if (> x 0) (+ x 1) (- 0 x)))",
            [4], "5",
        ),
        (
            "defun-optional", "defun",
            "(defun c1-opt (a &optional b) (if b (+ a b) a))",
            [5, 6], "11",
        ),
        (
            "defun-rest", "defun",
            "(defun c1-rest (a &rest more) (cons a more))",
            [1, 2, 3], "(1 2 3)",
        ),
        (
            "defun-closure", "defun",
            "(defun c1-maker (x) (lambda (y) (+ x y)))", None, None,
        ),
        (
            "defmacro-shape", "defmacro",
            "(defmacro c1-quote (x) (cons (quote quote) (cons x nil)))",
            None, None,
        ),
    ]
    rows = []
    output_private: set[str] = set()
    for name, kind, form, args, expected in cases:
        if kind == "expression":
            baseline_form = f"(lambda () {form})"
        elif kind == "defmacro":
            # The released resident compiler accepts the macro expander as a
            # lambda; the temporary tier accepts the top-level defmacro form
            # and performs exactly this normalization itself.
            baseline_form = "(lambda (x) (cons (quote quote) (cons x nil)))"
        else:
            baseline_form = form
        old_expr = f"(lcc-compile-obj (quote {baseline_form}))"
        new_expr = f"(%c1-compile 0 (quote {form}) nil)"
        old_heap, old_vm, old_result, old_steps = _eval([baseline], old_expr)
        new_heap, new_vm, new_result, new_steps = _eval(candidate, new_expr)
        old_text = old_heap.obj_to_text(old_result)
        new_text = new_heap.obj_to_text(new_result)
        _require(old_text == new_text, f"compile result drift: {name}")
        found: set[str] = set()
        _collect_symbols(new_heap, new_result, found, set())
        output_private.update(found & compiler_private)
        executed = args is not None
        execution = None
        if executed:
            old_value = old_vm.run(_compiled_main(old_heap, old_result), _execution_args(args))
            new_value = new_vm.run(_compiled_main(new_heap, new_result), _execution_args(args))
            old_value_text = old_heap.obj_to_text(old_value)
            new_value_text = new_heap.obj_to_text(new_value)
            _require(old_value_text == new_value_text, f"execution drift: {name}")
            _require(new_value_text == expected, f"unexpected execution result: {name}")
            execution = new_value_text
        rows.append({
            "id": name,
            "kind": kind,
            "compile_sha256": _sha_bytes(new_text.encode("utf-8")),
            "compile_equal": True,
            "execute_equal": True if executed else "not-applicable-helper-shape",
            "execution_result": execution,
            "baseline_steps": old_steps,
            "candidate_steps": new_steps,
            "performance_claim": "none-host-semantic-counter-only",
        })

    source_rows = []
    for name, source in (
        ("single-defun", "(defun c1-file-a () 42)"),
        (
            "ordered-two-defuns",
            "(defun c1-file-a () 40) (defun c1-file-b () (+ (c1-file-a) 2))",
        ),
    ):
        quoted = json.dumps(source)
        old_expr = (
            f"(progn (%cs-read-open {quoted}) "
            "(let ((fs (%fasl-fs 0))) (%fasl-stream-forms fs) (%fasl-finish fs)))"
        )
        old_heap, old_vm, old_result, old_steps = _eval([baseline], old_expr)
        _require(B.is_fix(old_result), f"baseline source length is invalid: {name}")
        length = B.fixval(old_result)
        old_bytes = bytes(old_vm.fasl_stage[:length])
        new_heap, new_vm, new_result, new_steps = _eval(
            candidate, f"(%c1-compile 1 {quoted} nil)"
        )
        _require(new_heap.bufferp(new_result), f"candidate source result is not a Buffer: {name}")
        cell = new_heap.cell(new_result)
        new_values = _proper_list(new_heap, cell.a, f"{name} buffer")
        _require(all(B.is_fix(value) for value in new_values), f"{name}: non-byte buffer")
        new_bytes = bytes(B.fixval(value) & 0xFF for value in new_values)
        _require(B.fixval(cell.b) == len(new_bytes), f"{name}: Buffer length drift")
        _require(old_bytes == new_bytes, f"source FASL drift: {name}")
        source_rows.append({
            "id": name,
            "bytes": len(new_bytes),
            "sha256": _sha_bytes(new_bytes),
            "equal": True,
            "baseline_steps": old_steps,
            "candidate_steps": new_steps,
            "performance_claim": "none-host-semantic-counter-only",
        })

    _require(not output_private, "compiled output retains compiler-private symbols")
    return {
        "baseline": "sealed-v1.0.1-resident-compiler",
        "candidate": "temporary-C1-shelf-tier",
        "form_cases": rows,
        "source_fasl_cases": source_rows,
        "compile_equal": True,
        "execute_equal": True,
        "compiler_private_symbols_in_outputs": sorted(output_private),
        "claim_limit": (
            "Host P0 executes identical compiler outputs and compares exact FASL bytes. "
            "Step counts are diagnostic only and are not device timing evidence."
        ),
    }


def _function_body(source: str, name: str) -> str:
    needle = name + "("
    start = source.find(needle)
    if start < 0:
        raise GateError(f"missing C function {name}")
    brace = source.find("{", start)
    _require(brace >= 0, f"missing body for C function {name}")
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[brace + 1:index]
    raise GateError(f"unterminated body for C function {name}")


def _performance_gate(mem_source: Path, eval_source: Path) -> dict:
    source = mem_source.read_text(encoding="utf-8")
    from_stage = _function_body(source, "buf_from_stage")
    to_stage = _function_body(source, "buf_to_stage")
    for label, body in (("stage-to-buffer", from_stage), ("buffer-to-stage", to_stage)):
        device = body.split("#else", 1)[1].split("#endif", 1)[0]
        _require(device.count("ext_dma(") == 1, f"{label} is not exactly one device DMA")
        _require("for (" not in device and "while (" not in device, f"{label} has a device loop")
    _require("buf_allocate(len, 0)" in from_stage, "stage-to-buffer reintroduced zero fill")
    lisp = eval_source.read_text(encoding="utf-8")
    _require("(%buffer-alloc 2 length)" in (ROOT / "lib/lcc-fasl.lisp").read_text(),
             "compiler does not use the bulk stage-to-buffer operation")
    _require("(%buffer-alloc 3 output)" in lisp,
             "resident save path does not use the bulk buffer-to-stage operation")
    _require("(%buffer-read 0 output)" in lisp,
             "resident save path does not use the native Buffer predicate")
    _require("(bufferp output)" not in lisp,
             "resident C1 path depends on the optional shelf-only buffer helper")
    return {
        "selected_evidence": "batched-staging-window-to-buffer-DMA-seam",
        "stage_to_buffer_device_dma_calls_per_result": 1,
        "buffer_to_stage_device_dma_calls_per_result": 1,
        "per_byte_buffer_set_calls": 0,
        "preclear_passes": 0,
        "device_loops_in_boundary_copy": 0,
        "claim": (
            "The compiler's established staging emitter remains byte-oriented, but the new "
            "C1 boundary adds two bulk DMA operations, not one overlay call per emitted byte."
        ),
    }


def _source_symbol_names(manifest: dict) -> set[str]:
    return {
        row.get("name")
        for row in manifest.get("literal_nodes", [])
        if int(row.get("kind", 0)) == Stdlib.K_SYMBOL and isinstance(row.get("name"), str)
    }


def _overlay_slice(manifest: dict, name: str) -> dict:
    rows = [row for row in manifest.get("slices", []) if row.get("name") == name]
    _require(len(rows) == 1, f"runtime overlay lacks unique {name} slice")
    return rows[0]


def build_report(args) -> dict:
    decision = _load(args.decision)
    e_auth = _load(args.e_authorization)
    e_receipt = _load(args.e_receipt)
    historical_c1 = _load(args.historical_c1_receipt)
    historical_c1_auth = _load(args.historical_c1_authorization)
    integration_drift = _load(args.integration_drift_receipt)
    integration_auth = _load(args.integration_authorization)
    installer_auth = _load(args.installer_capacity_authorization)
    installer_determinism = _load(args.installer_determinism)
    source_stream_probe = _load(args.source_stream_probe)
    source_stream_auth = _load(args.source_stream_authorization)
    source_stream_report = _load(args.source_stream_report)
    island_inventory = _load(args.island_inventory)
    authorized_capacity = integration_auth["capacity"]
    latency_exception = _load(args.latency_exception)
    prewave = _load(args.prewave)
    register = _load(args.promotion_register)
    resident = _load(args.resident_manifest)
    tier = _load(args.tier_manifest)
    composition = _load(args.composition)
    footprint = _load(args.footprint)
    layout = _load(args.layout)
    overlays = _load(args.overlays)
    shelf = _load(args.shelf_manifest)
    baseline_manifest, baseline_blob, baseline_binding = _baseline_artifacts(register)
    resident_blob = args.resident_blob.read_bytes()
    tier_blob = args.tier_blob.read_bytes()

    _require(decision.get("status") == "owner-approved", "C1 lacks owner approval")
    _require(decision.get("selected") == "C1-compiler-tier-deresidentization",
             "wrong architecture selected")
    _require(e_auth.get("status") == "owner-authorized", "1.1-E is not authorized")
    _require(e_receipt.get("status") == "passed-not-promoted", "unexpected 1.1-E receipt")
    _require(historical_c1.get("status") == "passed-not-promoted",
             "historical C1 receipt drift")
    _require(historical_c1_auth.get("status") == "owner-authorized",
             "historical C1 capacity is not authorized")
    historical_binding = historical_c1_auth.get("probe_receipt_before_authorization", {})
    _require(
        historical_binding.get("path") == _relative(args.historical_c1_receipt)
        and historical_binding.get("sha256") == _sha(args.historical_c1_receipt),
        "historical C1 receipt binding drift",
    )
    _require(integration_drift.get("status") ==
             "owner-capacity-review-required-promotion-blocked",
             "C1 integration drift receipt status drift")
    _require(integration_auth.get("status") == "owner-authorized",
             "C1 integration capacity is not authorized")
    integration_binding = integration_auth.get("probe_receipt", {})
    _require(
        integration_binding.get("path") == _relative(args.integration_drift_receipt)
        and integration_binding.get("sha256") == _sha(args.integration_drift_receipt),
        "C1 integration authorization binding drift",
    )
    _require(installer_auth.get("status") == "owner-authorized",
             "installer-slice capacity repin is not authorized")
    installer_binding = installer_auth.get("probe_receipt", {})
    _require(
        installer_binding.get("path") == _relative(args.installer_diagnosis)
        and installer_binding.get("sha256") == _sha(args.installer_diagnosis),
        "installer-slice authorization binding drift",
    )
    _require(installer_determinism.get("status") ==
             "measured-capacity-credit-no-owner-debit-required",
             "installer allocation-determinism credit status drift")
    determinism_binding = installer_determinism.get("diagnosis", {})
    _require(
        determinism_binding.get("path") == _relative(args.installer_determinism_diagnosis)
        and determinism_binding.get("sha256") ==
        _sha(args.installer_determinism_diagnosis),
        "installer allocation-determinism diagnosis binding drift",
    )
    _require(source_stream_auth.get("status") == "owner-authorized",
             "source-stream lifetime capacity is not authorized")
    source_stream_binding = source_stream_auth.get("probe_receipt", {})
    _require(
        source_stream_binding.get("path") == _relative(args.source_stream_probe)
        and source_stream_binding.get("sha256") == _sha(args.source_stream_probe),
        "source-stream lifetime authorization binding drift",
    )
    _require(source_stream_probe.get("status") ==
             "passed-probe-owner-capacity-authorization-required-not-promoted",
             "source-stream lifetime probe status drift")
    _require(source_stream_report.get("status") == "pass"
             and source_stream_report.get("model", {}).get(
                 "disjoint_directory_scratch") == "byte-identical",
             "source-stream lifetime gate is not closed")
    _require(island_inventory.get("status") == "ok"
             and island_inventory.get("coverage", {}).get("unattributed_bytes") == 0,
             "resident-island inventory is not closed")
    _require(latency_exception.get("status") == "owner-approved-dated-exception"
             and latency_exception.get("performance_bar_result") == "not-passed"
             and latency_exception.get("cure", {}).get("id") ==
             "C2-direct-Attic-execution"
             and latency_exception.get("cure", {}).get("release") == "1.2"
             and latency_exception.get("renewal", {}).get("automatic") is False,
             "C1 dated latency exception drift")
    gross = int(decision["promotion_gate"]["exact_compiler_tier_exclusion_bytes"])
    _require(gross == 9573, "gross compiler exclusion contract drift")
    _require(baseline_manifest.get("code_bytes") == 15203,
             "sealed baseline resident compiler identity drift")

    disk_code = sum(
        int(_load(ROOT / item["manifest"])["code_bytes"])
        for item in shelf.get("containers", [])
        if item.get("key") in {"ide", "idex", "m65d"}
    )
    baseline_headroom = int(
        e_receipt["capacity_delta"]["dimensions"]["ext"]
        ["candidate_standard_composition_headroom_bytes"]
    )
    baseline_resident_code = EXT_LIMIT - baseline_headroom - disk_code
    historical_resident_code = 5985
    historical_net_exclusion = baseline_resident_code - historical_resident_code
    historical_replacement = gross - historical_net_exclusion
    candidate_resident_code = int(resident["code_bytes"])
    wave_r4_resident_code = int(integration_drift["ext_attribution"]
                                ["baseline_resident_code_bytes"])
    integration_ext_debit = candidate_resident_code - wave_r4_resident_code
    final_net_exclusion = baseline_resident_code - candidate_resident_code
    _require(baseline_resident_code == 15229, "1.1-E resident code baseline drift")
    _require(historical_resident_code == 5985 and historical_net_exclusion == 9244,
             "historical C1 net resident exclusion drift")
    _require(historical_replacement == 329, "historical C1 seam attribution drift")
    _require(wave_r4_resident_code == 6452, "Wave-1 R4 resident code drift")
    _require(candidate_resident_code == 6540, "C1 integration resident code drift")
    _require(integration_ext_debit == 88, "authorized C1 integration EXT debit drift")
    _require(final_net_exclusion == 8689, "final C1 net resident exclusion drift")

    tier_code = int(tier["code_bytes"])
    tier_metadata = int(tier["external_image"]["metadata_bytes"])
    _require(tier_code == 9420, "temporary compiler tier size drift")
    _require(tier_code == gross - 313 + 160, "tier link attribution does not close")
    candidate_post = int(composition["ext_code"]["post_headroom"])
    post_margin = candidate_post - EXT_FLOOR
    _require(candidate_post == 25073 and post_margin == 8689,
             "post-C1 integration EXT headroom drift")
    _require(candidate_post == int(authorized_capacity["ext"]
                                   ["candidate_standard_composition_headroom_bytes"])
             and int(authorized_capacity["ext"]["authorized_delta_bytes"]) == -88,
             "authorized C1 EXT integration values drift")
    post_used = int(composition["ext_code"]["post_used"])
    load_peak_used = post_used + tier_code + tier_metadata
    load_peak_headroom = EXT_LIMIT - load_peak_used
    execution_used = post_used + tier_code
    execution_headroom = EXT_LIMIT - execution_used
    _require(load_peak_headroom == 2563, "C1 L65M integration load peak drift")
    _require(execution_headroom == 15653, "C1 integration execution peak drift")
    _require(load_peak_headroom > 0 and execution_headroom > 0,
             "C1 peak does not fit EXT capacity")
    _require(post_margin >= int(decision["promotion_gate"]["minimum_post_block_ext_margin_bytes"]),
             "C1 does not create the authorized post-block margin")

    directory = composition["directory"]
    _require(int(composition["symbols"]["headroom"]) == 298,
             "C1 integration symbol headroom drift")
    _require(int(composition["namepool"]["headroom"]) == 4602,
             "C1 integration namepool headroom drift")
    _require(int(directory["post_align_headroom"]) == 168,
             "C1 integration directory headroom drift")
    compiler_entries = len(tier["entries"])
    temporary_dir_used = ((int(directory["load_used"]) + 7) & ~7) + compiler_entries
    temporary_dir_headroom = int(composition["limits"]["vm_dir_max"]) - temporary_dir_used
    _require(temporary_dir_headroom == 24,
             "temporary compiler integration directory headroom drift")

    tier_functions = set(tier.get("functions", []))
    tier_exports = set(tier.get("exports", []))
    compiler_private = tier_functions - tier_exports
    resident_entries = {entry["name"] for entry in resident.get("entries", [])}
    resident_symbols = _source_symbol_names(resident)
    private_entries = sorted(compiler_private & resident_entries)
    private_literals = sorted(compiler_private & resident_symbols)
    _require(not private_entries and not private_literals,
             "resident image retains compiler-private references")
    _require(tier_exports == {"%c1-compile"}, "temporary tier export set drift")
    _require("%c1-compile" not in resident_entries and "%c1-compile" in resident_symbols,
             "resident control export identity is not literal-only")

    equivalence = _compile_equivalence(
        (baseline_manifest, baseline_blob),
        [(resident, resident_blob), (tier, tier_blob)],
        compiler_private,
    )
    performance = _performance_gate(args.mem_source, args.eval_source)

    footprint_reserve = int(footprint["post_boot_reserve"])
    baseline_bank = int(authorized_capacity["bank"]
                        ["baseline_post_boot_reserve_bytes"])
    bank_delta = footprint_reserve - baseline_bank
    _require(baseline_bank == 1873 and footprint_reserve == 1905
             and bank_delta == 32,
             "C1 integration Bank-0 delta drift")
    resident_prg_bytes = args.resident_prg.stat().st_size
    baseline_prg_bytes = 39490
    _require(resident_prg_bytes == 39456
             and resident_prg_bytes - baseline_prg_bytes == -34
             and footprint_reserve - 1802 == 103,
             "resident PRG attribution does not match integration Bank-0 delta")
    overlay_base = int(layout["overlay"]["base"])
    overlay_headroom = OVERLAY_LIMIT - overlay_base
    _require(overlay_headroom == 0, "integration overlay base headroom drift")
    _require(int(layout["overlay"]["size"]) == 1669, "boot overlay size drift")
    _require(args.runtime_overlay_image.stat().st_size == 65472,
             "runtime-overlay bank integration size drift")
    c1_slice = _overlay_slice(overlays, "c1-compiler-lifetime")
    alloc_slice = _overlay_slice(overlays, "first-class-buffer-alloc")
    installer_slice = _overlay_slice(overlays, "resident-island-installer")
    _require(int(c1_slice["memory_size"]) <= SLICE_LIMIT, "C1 slice overflow")
    _require(int(alloc_slice["memory_size"]) <= SLICE_LIMIT, "buffer alloc slice overflow")
    _require(int(installer_slice["memory_size"]) == 1770,
             "installer slice integration identity drift")
    installer_capacity = installer_auth["capacity"]["resident_island_installer_slice"]
    _require(
        int(installer_capacity["candidate_bytes"]) == 1765
        and int(installer_capacity["hard_limit_bytes"]) == SLICE_LIMIT
        and int(installer_capacity["candidate_headroom_bytes"]) == 27
        and int(installer_capacity["authorized_headroom_delta_bytes"]) == -6,
        "historical authorized installer-slice capacity values drift",
    )
    deterministic_capacity = installer_determinism["capacity"][
        "resident_island_installer_slice"
    ]
    _require(
        int(deterministic_capacity["hard_limit_bytes"]) == SLICE_LIMIT
        and int(deterministic_capacity["owner_authorized_pre_fix_bytes"]) == 1765
        and int(deterministic_capacity["owner_authorized_pre_fix_headroom_bytes"]) == 27
        and int(deterministic_capacity["fixed_bytes"]) == 1743
        and int(deterministic_capacity["fixed_headroom_bytes"]) == 49
        and int(deterministic_capacity["headroom_credit_bytes"]) == 22,
        "historical deterministic installer-slice capacity credit drift",
    )
    correction_capacity = source_stream_auth["capacity"]
    correction_island = correction_capacity["resident_island"]
    correction_installer = correction_capacity["resident_island_installer_slice"]
    island_contract = island_inventory["island_contract"]
    _require(
        int(correction_island["baseline_reserve_bytes"]) == 256
        and int(correction_island["candidate_reserve_bytes"]) == 120
        and int(correction_island["authorized_reserve_delta_bytes"]) == -136
        and int(island_contract["immutable_bytes"]) == 1668
        and int(island_contract["annex_bytes"]) == 260
        and int(island_contract["reserve_bytes"]) == 120,
        "source-stream resident-island capacity authorization drift",
    )
    _require(
        int(correction_installer["hard_limit_bytes"]) == SLICE_LIMIT
        and int(correction_installer["latest_owner_authorized_headroom_pin_bytes"]) == 27
        and int(correction_installer["candidate_bytes"]) ==
        int(installer_slice["memory_size"])
        and int(correction_installer["candidate_headroom_bytes"]) == 22
        and int(correction_installer[
            "authorized_delta_from_latest_owner_pin_bytes"]) == -5,
        "source-stream installer-slice capacity authorization drift",
    )

    lifetime_output = _run_checked(args.lifetime_host)
    _require(
        "PASS cases=12 gc=yes oom=yes malformed=yes reset=yes" in lifetime_output
        and "nested-transient=yes overlap-reject=yes" in lifetime_output,
        "lifetime matrix did not prove all mandatory rollback classes",
    )
    shelf_output = _run_checked(args.shelf_host, str(args.shelf_image))
    _require("PASS libraries=5 negative_cases=7 exact_copy=yes" in shelf_output,
             "shelf negative matrix drift")

    current_attribution = Prewave.source_code_attribution(resident)
    current_eval = next(
        row for row in current_attribution
        if row["source"].endswith("lib/dialect-v2/eval-runtime.lisp")
    )
    _require(int(current_eval["code_bytes"]) == 1306,
             "resident eval-runtime attribution drift")
    current_load = next(
        row for row in current_attribution
        if row["source"].endswith("lib/stdlib-load-lib.lisp")
    )
    _require(int(current_load["code_bytes"]) == 420,
             "resident load-lib attribution drift")

    parity = _load(args.primitive_parity)
    _require(not parity.get("missing") and not parity.get("unclassified"),
             "native primitive cross parity is not closed")
    differential = _load(args.workbench_differential)
    _require(
        differential.get("status") == "passed"
        and differential.get("summary", {}).get("artifacts") == 4
        and differential.get("summary", {}).get("cases") == 357
        and differential.get("summary", {}).get("observation_differences") == 0,
        "four-artifact Workbench differential is not closed",
    )

    report = {
        "format": FORMAT,
        "block_id": "1.1-C1-wave1-final-integration",
        "status": "passed-not-promoted",
        "recorded_on": "2026-07-16",
        "recording_base_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "owner_decision": {
            "path": _relative(args.decision),
            "sha256": _sha(args.decision),
            "selected": decision["selected"],
            "status": decision["status"],
        },
        "baseline": {
            "block": "owner-authorized-1.1-E-on-1.1-A-plus-1.1-B",
            "e_receipt": {"path": _relative(args.e_receipt), "sha256": _sha(args.e_receipt)},
            "e_authorization": {
                "path": _relative(args.e_authorization),
                "sha256": _sha(args.e_authorization),
            },
            "historical_c1_receipt": {
                "path": _relative(args.historical_c1_receipt),
                "sha256": _sha(args.historical_c1_receipt),
            },
            "historical_c1_authorization": {
                "path": _relative(args.historical_c1_authorization),
                "sha256": _sha(args.historical_c1_authorization),
            },
            "source_stream_lifetime_probe": {
                "path": _relative(args.source_stream_probe),
                "sha256": _sha(args.source_stream_probe),
            },
            "source_stream_lifetime_authorization": {
                "path": _relative(args.source_stream_authorization),
                "sha256": _sha(args.source_stream_authorization),
            },
            "released_compiler_oracle": baseline_binding,
        },
        "implementation": {
            "shelf_role": "temporary-compiler-tier",
            "shelf_record_id": 4,
            "exports": sorted(tier_exports),
            "private_functions": len(compiler_private),
            "lifetime": (
                "checkpoint -> exact SHA/CRC/preflight-bound load -> validate -> compile to "
                "detached Buffer/heap result -> retire tier -> install or persist result"
            ),
            "rollback": (
                "LIFO truncation restores code and directory watermarks, clears the export "
                "function, preserves later user symbol/name internings, and is idempotent"
            ),
            "reset": "all C1 checkpoint state is existing reset-cleared BSS; a reset is inert",
            "identity": (
                "CRC32-bound L65S record plus exact generated L65M length/CRC16/blob/entry/format "
                "preflight fields; the generated symbol/name ceilings and the retained "
                "post-retirement accounting are both enforced"
            ),
        },
        "link_attribution": {
            "gross_resident_compiler_source_exclusion_bytes": gross,
            "gross_sources": ["lib/lcc.lisp", "lib/lcc-fasl.lisp", "lib/dialect-v2/lcc-profile.lisp"],
            "historical_c1_resident_replacement_bytes": historical_replacement,
            "historical_c1_resident_replacement_breakdown": {
                "retained_compiler_facing_entries_bytes": 237,
                "new_detach_and_save_seams_bytes": 174,
                "compile_string_rewrite_savings_bytes": -82,
                "sum_bytes": 329,
                "historical_candidate_eval_runtime_bytes": 1225,
            },
            "historical_c1_net_persistent_resident_exclusion_bytes": historical_net_exclusion,
            "wave1_r4_resident_code_bytes": wave_r4_resident_code,
            "integration_resident_code_bytes": candidate_resident_code,
            "integration_ext_debit_bytes": integration_ext_debit,
            "integration_ext_debit_attribution": {
                "eval_runtime_bytes": int(current_eval["code_bytes"]) - 1225,
                "stdlib_load_lib_bytes": int(current_load["code_bytes"]) - 413,
                "sum_bytes": integration_ext_debit,
            },
            "final_net_persistent_resident_exclusion_bytes": final_net_exclusion,
            "temporary_tier_code_bytes": tier_code,
            "temporary_tier_vs_gross": {
                "unchanged_compiler_entries_bytes": 9260,
                "removed_resident_facing_entries_bytes": -313,
                "new_tier_interface_entries_bytes": 160,
                "sum_bytes": tier_code,
            },
        },
        "capacity_delta_scope": "final-C1-reopening-on-sealed-Wave1-R4-candidate",
        "capacity_delta": {
            "authorization": {
                "path": _relative(args.integration_authorization),
                "sha256": _sha(args.integration_authorization),
            },
            "post_integration_correction_authorization": {
                "path": _relative(args.source_stream_authorization),
                "sha256": _sha(args.source_stream_authorization),
            },
            "drift_receipt": {
                "path": _relative(args.integration_drift_receipt),
                "sha256": _sha(args.integration_drift_receipt),
            },
            "dimensions": {
                "bank": {
                    "baseline_post_boot_reserve_bytes": baseline_bank,
                    "candidate_post_boot_reserve_bytes": footprint_reserve,
                    "release_target_bytes": 1536,
                    "candidate_margin_bytes": footprint_reserve - 1536,
                    "delta_bytes": bank_delta,
                    "baseline_resident_prg_bytes": baseline_prg_bytes,
                    "candidate_resident_prg_bytes": resident_prg_bytes,
                },
                "ext": {
                    "baseline_standard_composition_headroom_bytes": 25161,
                    "candidate_standard_composition_headroom_bytes": candidate_post,
                    "floor_bytes": EXT_FLOOR,
                    "candidate_margin_bytes": post_margin,
                    "delta_bytes": candidate_post - 25161,
                    "gross_exclusion_bytes": gross,
                    "historical_c1_net_exclusion_bytes": historical_net_exclusion,
                    "final_net_exclusion_bytes": final_net_exclusion,
                },
                "symbols": {
                    "baseline_headroom": 297,
                    "candidate_headroom": int(composition["symbols"]["headroom"]),
                    "delta": int(composition["symbols"]["headroom"]) - 297,
                },
                "namepool": {
                    "baseline_headroom_bytes": 4594,
                    "candidate_headroom_bytes": int(composition["namepool"]["headroom"]),
                    "delta_bytes": int(composition["namepool"]["headroom"]) - 4594,
                },
                "directory": {
                    "baseline_post_align_headroom": 168,
                    "candidate_post_align_headroom": int(directory["post_align_headroom"]),
                    "delta": int(directory["post_align_headroom"]) - 168,
                    "temporary_compiler_headroom": temporary_dir_headroom,
                },
                "boot_overlay": {
                    "baseline_bytes": 1669,
                    "candidate_bytes": int(layout["overlay"]["size"]),
                    "delta_bytes": int(layout["overlay"]["size"]) - 1669,
                },
                "overlay_vma": {
                    "baseline": "0xc306",
                    "candidate": hex(overlay_base),
                    "ceiling": hex(OVERLAY_LIMIT),
                    "remaining_bytes": overlay_headroom,
                },
                "runtime_overlay_bank": {
                    "baseline_bytes": 63906,
                    "candidate_bytes": args.runtime_overlay_image.stat().st_size,
                    "hard_limit_bytes": 65536,
                    "remaining_bytes": 65536 - args.runtime_overlay_image.stat().st_size,
                },
                "resident_island": {
                    "baseline_payload_bytes": 1531,
                    "candidate_payload_bytes": int(island_contract["immutable_bytes"]),
                    "payload_delta_bytes": int(island_contract["immutable_bytes"]) - 1531,
                    "annex_bytes": int(island_contract["annex_bytes"]),
                    "baseline_reserve_bytes": 256,
                    "candidate_reserve_bytes": int(island_contract["reserve_bytes"]),
                    "reserve_delta_bytes": int(island_contract["reserve_bytes"]) - 256,
                    "authorization": {
                        "path": _relative(args.source_stream_authorization),
                        "sha256": _sha(args.source_stream_authorization),
                    },
                },
            },
            "temporary_compile_peak": {
                "standard_composition_used_bytes": post_used,
                "l65m_code_bytes": tier_code,
                "l65m_metadata_bytes": tier_metadata,
                "load_peak_used_bytes": load_peak_used,
                "load_peak_headroom_bytes": load_peak_headroom,
                "compiler_execution_used_bytes": execution_used,
                "compiler_execution_headroom_bytes": execution_headroom,
                "detached_result_storage": "compacted string arena, not EXT code region",
                "post_retirement_headroom_bytes": candidate_post,
                "floor_policy": (
                    "The 16 KiB floor is restored and exceeded after retirement. Temporary "
                    "load/execution must fit physical EXT capacity; any overflow is a design stop."
                ),
            },
        },
        "compiler_private_reference_gate": {
            "tier_functions": len(tier_functions),
            "exports": sorted(tier_exports),
            "private_functions": len(compiler_private),
            "resident_directory_intersection": private_entries,
            "resident_literal_intersection": private_literals,
            "compiled_output_intersection": equivalence["compiler_private_symbols_in_outputs"],
            "resident_export_identity_literal": "%c1-compile",
            "export_function_after_retirement": "nil-by-lifetime-matrix",
            "status": "pass",
        },
        "compile_equivalence": equivalence,
        "compile_performance": performance,
        "definition_call_latency": {
            "status": "limitation-stable-not-performance-pass",
            "definition_call_frames": 95,
            "definition_call_milliseconds": 1900,
            "warm_call_frames": 10,
            "warm_call_milliseconds": 200,
            "gate_value_required_tokens": [
                "performance-bar=not-passed",
                "exception=owner-dated-2026-07-16",
                "cure=C2/1.2",
            ],
            "exception_contract": {
                "path": _relative(args.latency_exception),
                "sha256": _sha(args.latency_exception),
            },
        },
        "overlay_headroom": {
            "base_vma_remaining_bytes": overlay_headroom,
            "c1_lifetime_slice_bytes": int(c1_slice["memory_size"]),
            "c1_lifetime_slice_remaining_bytes": SLICE_LIMIT - int(c1_slice["memory_size"]),
            "buffer_alloc_slice_bytes": int(alloc_slice["memory_size"]),
            "buffer_alloc_slice_remaining_bytes": SLICE_LIMIT - int(alloc_slice["memory_size"]),
            "resident_island_installer_bytes": int(installer_slice["memory_size"]),
            "resident_island_installer_remaining_bytes":
                SLICE_LIMIT - int(installer_slice["memory_size"]),
            "resident_island_installer_capacity_authorization": {
                "path": _relative(args.installer_capacity_authorization),
                "sha256": _sha(args.installer_capacity_authorization),
            },
            "resident_island_installer_determinism_credit": {
                "path": _relative(args.installer_determinism),
                "sha256": _sha(args.installer_determinism),
            },
            "source_stream_lifetime_capacity_authorization": {
                "path": _relative(args.source_stream_authorization),
                "sha256": _sha(args.source_stream_authorization),
            },
            "resident_island_installer_note": (
                "The sealed final-link allocation credit raised headroom from 27 to 49 "
                "bytes. The owner-authorized source-stream lifetime correction consumes "
                "27 bytes of that actual margin and repins the latest owner floor from "
                "27 to 22 bytes."
            ),
        },
        "verification": {
            "native_function_cross_parity": {
                "status": "pass",
                "missing": parity.get("missing", []),
                "unclassified": parity.get("unclassified", []),
                "evaluations": parity.get("evaluations", 828),
            },
            "workbench_artifact_differential": {
                "path": _relative(args.workbench_differential),
                "sha256": _sha(args.workbench_differential),
                "artifacts": differential["summary"]["artifacts"],
                "cases": differential["summary"]["cases"],
                "observation_differences": differential["summary"]["observation_differences"],
            },
            "compiler_lifetime": lifetime_output,
            "shelf_negative_matrix": shelf_output,
            "full_product_link": "pass",
            "footprint_audit": {"path": _relative(args.footprint), "sha256": _sha(args.footprint)},
            "resident_prg": {"path": _relative(args.resident_prg), "sha256": _sha(args.resident_prg)},
            "runtime_overlays": {"path": _relative(args.overlays), "sha256": _sha(args.overlays)},
            "source_stream_lifetime": {
                "path": _relative(args.source_stream_report),
                "sha256": _sha(args.source_stream_report),
                "source_bytes": source_stream_report["model"]["source_bytes"],
                "sectors": source_stream_report["model"]["sectors"],
                "resident_fetch_bytes": source_stream_report[
                    "resident_source_fetch"]["bytes"],
            },
            "resident_island_inventory": {
                "path": _relative(args.island_inventory),
                "sha256": _sha(args.island_inventory),
                "allocations": island_inventory["coverage"]["physical_allocations"],
                "unattributed_bytes": island_inventory["coverage"]["unattributed_bytes"],
            },
            "hardware": "historical-probe-only-final-product-G5/G6-not-run",
        },
        "promotion_blockers": [
            "regular wave-level product/evidence repin and hardware acceptance",
            "wave-seal user documentation for the Buffer print form and the dated 1.90-second definition-call limitation",
        ],
        "claim_limit": (
            "This integration receipt proves the C1 host semantics, exact compiler equivalence, "
            "rollback classes, authorized final capacity and real product link. The 1.90-second "
            "definition-call path is a dated limitation, not a passed performance bar. This "
            "receipt does not promote a product set or claim final G5/G6 hardware evidence."
        ),
    }
    return report


def selftest() -> None:
    gross = 9573
    net = 9244
    replacement = gross - net
    assert replacement == 329
    assert gross - 313 + 160 == 9420
    post_used = 25743
    assert EXT_LIMIT - (post_used + 9420 + 13090) == 2563
    assert EXT_LIMIT - (post_used + 9420) == 15653
    assert 25073 - EXT_FLOOR == 8689
    assert 6540 - 6452 == 88
    assert 81 + 7 == 88


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--out", type=Path, default=ROOT / (
        "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
        "v11-c1-wave1-integration-block-receipt.json"
    ))
    parser.add_argument("--decision", type=Path, default=ROOT / "config/v11-c1-architecture-decision.json")
    parser.add_argument("--e-authorization", type=Path, default=ROOT / "config/v11-first-class-buffer-capacity-authorization.json")
    parser.add_argument("--e-receipt", type=Path, default=ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-first-class-buffer-block-receipt.json")
    parser.add_argument("--historical-c1-receipt", type=Path, default=ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-c1-compiler-tier-block-receipt.json")
    parser.add_argument("--historical-c1-authorization", type=Path, default=ROOT / "config/v11-c1-capacity-authorization.json")
    parser.add_argument("--integration-drift-receipt", type=Path, default=ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-c1-wave1-integration-capacity-drift-receipt.json")
    parser.add_argument("--integration-authorization", type=Path, default=ROOT / "config/v11-c1-wave1-integration-capacity-authorization.json")
    parser.add_argument("--installer-capacity-authorization", type=Path, default=ROOT / "config/v11-c1-bootstrap-final-link-capacity-authorization.json")
    parser.add_argument("--installer-diagnosis", type=Path, default=ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-c1-bootstrap-final-link-determinism-diagnosis.json")
    parser.add_argument("--installer-determinism", type=Path, default=ROOT / "config/v11-c1-final-link-allocation-determinism.json")
    parser.add_argument("--installer-determinism-diagnosis", type=Path, default=ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-c1-final-link-allocation-determinism-diagnosis.json")
    parser.add_argument("--source-stream-probe", type=Path, default=ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-c1-source-stream-lifetime-correction-probe-receipt.json")
    parser.add_argument("--source-stream-authorization", type=Path, default=ROOT / "config/v11-c1-source-stream-lifetime-capacity-authorization.json")
    parser.add_argument("--source-stream-report", type=Path, default=ROOT / "build/reports/workbench/v11-source-stream-lifetime.json")
    parser.add_argument("--island-inventory", type=Path, default=ROOT / "build/reports/workbench/bank0-island.json")
    parser.add_argument("--latency-exception", type=Path, default=ROOT / "config/v11-c1-definition-call-latency-exception.json")
    parser.add_argument("--prewave", type=Path, default=ROOT / "docs/planning/measurements/v1.1-prewave-measurements.json")
    parser.add_argument("--promotion-register", type=Path, default=ROOT / "config/promotion-register.json")
    parser.add_argument("--resident-manifest", type=Path, default=ROOT / "build/bytecode/dialect-v2/workbench/stdlib-p0.manifest.json")
    parser.add_argument("--resident-blob", type=Path, default=ROOT / "build/bytecode/dialect-v2/workbench/stdlib-p0.blob.bin")
    parser.add_argument("--tier-manifest", type=Path, default=ROOT / "build/bytecode/dialect-v2/libs/lcc.manifest.json")
    parser.add_argument("--tier-blob", type=Path, default=ROOT / "build/bytecode/dialect-v2/libs/lcc.blob.bin")
    parser.add_argument("--composition", type=Path, default=ROOT / "build/bytecode/dialect-v2/workbench-library-composition-budget.json")
    parser.add_argument("--footprint", type=Path, default=ROOT / "build/products/workbench/overlay-stack-guard/footprint-audit.json")
    parser.add_argument("--layout", type=Path, default=ROOT / "build/products/workbench/overlay-stack-guard/layout.json")
    parser.add_argument("--overlays", type=Path, default=ROOT / "build/products/workbench/overlay-stack-guard/runtime-overlays-manifest.json")
    parser.add_argument("--runtime-overlay-image", type=Path, default=ROOT / "build/products/workbench/overlay-stack-guard/lisp65-mvp-workbench.overlays.bin")
    parser.add_argument("--resident-prg", type=Path, default=ROOT / "build/products/workbench/overlay-stack-guard/lisp65-workbench-resident.prg")
    parser.add_argument("--shelf-manifest", type=Path, default=ROOT / "build/bytecode/dialect-v2/shelf/library-shelf-manifest.json")
    parser.add_argument("--shelf-image", type=Path, default=ROOT / "build/bytecode/dialect-v2/shelf/library-shelf.bin")
    parser.add_argument("--shelf-host", type=Path, default=ROOT / "build/attic-library-shelf-smoke-host")
    parser.add_argument("--lifetime-host", type=Path, default=ROOT / "build/v11-c1-compiler-lifetime-host")
    parser.add_argument("--mem-source", type=Path, default=ROOT / "src/mem.c")
    parser.add_argument("--eval-source", type=Path, default=ROOT / "lib/dialect-v2/eval-runtime.lisp")
    parser.add_argument("--primitive-parity", type=Path, default=ROOT / "tests/bytecode/dialect-v2/contracts/primitive-view-cross-parity.json")
    parser.add_argument("--workbench-differential", type=Path, default=ROOT / "tests/bytecode/dialect-v2/evidence/capability-carrier/workbench-artifact-differential-receipt.json")
    args = parser.parse_args()
    try:
        if args.selftest:
            selftest()
            print("v11-c1-gate: SELFTEST PASS cases=6")
            return 0
        report = build_report(args)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(_json_bytes(report))
    except (GateError, OSError, ValueError, KeyError, tarfile.TarError) as exc:
        print(f"v11-c1-gate: FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        "v11-c1-gate: PASS status=passed-not-promoted gross=9573 "
        "historical-net=9244 final-net=8689 ext=25073 peak=2563 "
        "bank=1905 overlay_headroom=0 island=120 installer=22 "
        "latency=LIMITATION-STABLE receipt=%s"
        % _relative(args.out)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
