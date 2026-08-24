#!/usr/bin/env python3
"""Prove the resident Island cannot be consumed before installation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_hot_refill_capacity_probe as H  # noqa: E402
import c2_product_substitution_link as P  # noqa: E402


CONTRACT = ROOT / "config/c2-preinstall-island-guard-contract.json"
DOCUMENT = ROOT / "docs/planning/c2.2-preinstall-island-guard-addendum.md"
RUNTIME = ROOT / "src/vm_runtime_overlay.c"
HEADER = ROOT / "src/vm_runtime_overlay.h"
FIXTURE = ROOT / "scripts/runtime-overlay-transaction-main.c"
MAKEFILE = ROOT / "mk/workbench.mk"
BINARY = ROOT / "build/runtime-overlay-transaction-host"
LINK30_FIXTURE = ROOT / (
    "tests/bytecode/dialect-v2/fixtures/"
    "c2-link30-resident-island-stale.hex")
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link31-transaction-auth-hardware-first-red-diagnosis.json")
STRUCTURAL = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link31-transaction-auth-structural-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-preinstall-island-guard-contract-probe-receipt.json")
HOST_OUT = ROOT / "build/c2.2/preinstall-island-guard-host"
STALE_BIN = HOST_OUT / "link30-resident-island.bin"
LINK30_LENGTH = 1291
LINK30_PAYLOAD_SHA256 = (
    "5d0141d0c78cfd29bacc993b0050c2ba5770938b36236f6c4e12bf740600b40a")
EXPECTED_OUTPUT = (
    "runtime-overlay-transaction: PASS catalog=once-per-transaction "
    "record+payload=per-slice same-generation-mutation=crc-red "
    "generation-change=reauthenticated batch-state=lifetime-exclusive "
    "batch-S1=full-single-record-repeat "
    "stale-predecessor=exact-link30 preinstall-island-calls=0")
FACADE_HANDLE_SYMBOL = "c2_facade_handle_normalize"
FACADE_HANDLE_SECTION = ".lisp65_c2_host_facade"
FACADE_HANDLE_ADDRESS = 0xB5EE
FACADE_HANDLE_BYTES = 3
FACADE_APPEND_SYMBOL = "c2_facade_append_plan_walk"
FACADE_APPEND_ADDRESS = 0xB5F1
FACADE_APPEND_BYTES = 3
ISLAND_BASE = 0x1800
ISLAND_CAPACITY = 0x0800
INSTALLER_ROOT = "vm_runtime_overlay_install_island"
INSTALLER_WIPE_TARGET = "__lisp65_resident_island_start"
INSTALLER_WIPE_COUNT = 3
INSTALLER_NONLOCAL_EXIT_CLASSES = (
    "poll",
    "abort",
    "longjmp",
    "c2j-abort-cleanup",
)


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def parse_island_header(path: Path) -> bytes:
    text = path.read_text(encoding="ascii")
    length = re.search(r"LISP65_RESIDENT_ISLAND_LENGTH\s+(\d+)u", text)
    require(length is not None and int(length.group(1)) == LINK30_LENGTH,
            "Link-30 Island length drift")
    require("LISP65_RESIDENT_ISLAND_BYTES" in text,
            "Link-30 Island initializer absent")
    values = re.findall(
        r"0x([0-9a-fA-F]{2})(?:,|\s*})",
        text.split("LISP65_RESIDENT_ISLAND_BYTES", 1)[1])
    payload = bytes.fromhex("".join(values))
    require(len(payload) == LINK30_LENGTH,
            f"Link-30 Island initializer length {len(payload)}")
    require(hashlib.sha256(payload).hexdigest() == LINK30_PAYLOAD_SHA256,
            "Link-30 Island payload identity drift")
    return payload


def parse_stale_island_fixture(path: Path) -> bytes:
    try:
        payload = bytes.fromhex(path.read_text(encoding="ascii"))
    except ValueError as error:
        raise GateError("Link-30 stale-Island fixture is not hex") from error
    require(len(payload) == LINK30_LENGTH,
            f"Link-30 stale-Island fixture length {len(payload)}")
    require(hashlib.sha256(payload).hexdigest() == LINK30_PAYLOAD_SHA256,
            "Link-30 stale-Island fixture identity drift")
    return payload


def write_bound(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.read_bytes() == data,
                f"refusing to overwrite divergent artifact {path}")
        return
    path.write_bytes(data)
    os.chmod(path, 0o444)


def _guard_body(source: str) -> str:
    match = re.search(
        r"(?:static RTOV_NOINLINE|LISP65_C2_MAPPED_FAR_FN) uint8_t "
        r"rtov_transaction_context_if_ready(?:_far)?\s*"
        r"\([^)]*\)\s*\{(.*?)\n\}", source, re.DOTALL)
    require(match is not None, "resident transaction guard absent")
    return match.group(1)


def guard_source_errors(source: str) -> list[str]:
    errors: list[str] = []
    try:
        body = _guard_body(source)
    except GateError as exc:
        return [str(exc)]
    tokens = (
        "if (!RTOV_TRANSACTION_ACTIVE()) return 0;",
        "if (rtov_island_state != RTOV_ISLAND_READY) return 0xfeu;",
        "return rtov_transaction_context(verify, publish);",
    )
    positions = [body.find(token) for token in tokens]
    if any(position < 0 for position in positions):
        errors.append("guard-clause-absent")
    elif positions != sorted(positions):
        errors.append("guard-order-drift")
    if body.count("rtov_transaction_context(") != 1:
        errors.append("guard-has-nonunique-Island-call")
    return errors


def model_selftest() -> dict[str, str]:
    def model(active: bool, ready: bool) -> tuple[int, int]:
        if not active:
            return 0, 0
        if not ready:
            return 0xfe, 0
        return 1, 1

    require(model(False, False) == (0, 0),
            "inactive/stale model entered Island")
    require(model(True, False) == (0xfe, 0),
            "active/not-ready model did not fail closed")
    require(model(True, True) == (1, 1),
            "active/ready model did not enter Island")
    source = RUNTIME.read_text(encoding="utf-8")
    require(not guard_source_errors(source), "valid guard source rejected")
    body = _guard_body(source)
    mutations = {
        "inactive-check-removed": source.replace(body, body.replace(
            "if (!RTOV_TRANSACTION_ACTIVE()) return 0;", "", 1), 1),
        "ready-check-removed": source.replace(body, body.replace(
            "if (rtov_island_state != RTOV_ISLAND_READY) return 0xfeu;",
            "", 1), 1),
        "guard-order-reversed": source.replace(body, body.replace(
            "if (!RTOV_TRANSACTION_ACTIVE()) return 0;\n"
            "    if (rtov_island_state != RTOV_ISLAND_READY) return 0xfeu;",
            "if (rtov_island_state != RTOV_ISLAND_READY) return 0xfeu;\n"
            "    if (!RTOV_TRANSACTION_ACTIVE()) return 0;", 1), 1),
    }
    for name, mutated in mutations.items():
        require(guard_source_errors(mutated),
                f"source mutation accepted: {name}")
    return {
        "inactive-stale": "zero-Island-calls",
        "active-not-ready": "fail-closed-zero-Island-calls",
        "active-ready": "single-Island-call",
        "missing-active-guard": "rejected",
        "missing-ready-guard": "rejected",
        "reversed-guard-order": "rejected",
    }


def source_gate() -> dict[str, Any]:
    runtime = RUNTIME.read_text(encoding="utf-8")
    fixture = FIXTURE.read_text(encoding="utf-8")
    installer_source = runtime.split(
        "vm_runtime_overlay_status vm_runtime_overlay_install_island(void)",
        1)[1].split("uint8_t vm_runtime_overlay_island_ready(void)", 1)[0]
    complete_wipes = re.findall(
        r"memset\(\(uint8_t \*\)RTOV_ISLAND_TARGET,\s*0,\s*"
        r"LISP65_RUNTIME_ISLAND_CAPACITY\);", installer_source)
    rows = {
        "installer_is_named_noinline_boundary": (
            "RTOV_NOINLINE\nvm_runtime_overlay_status "
            "vm_runtime_overlay_install_island(void)" in runtime),
        "resident_guard_exact": not guard_source_errors(runtime),
        "lookup_and_publish_share_guard": (
            runtime.count("rtov_transaction_context_if_ready(&verify") == 2),
        "not_ready_is_fail_closed": (
            runtime.count("VM_RUNTIME_OVERLAY_ERR_ISLAND_NOT_READY") >= 3),
        "host_context_counter": all(token in runtime for token in (
            "rtov_transaction_context_calls",
            "vm_runtime_overlay_host_transaction_context_calls")),
        "exact_stale_fixture_case": all(token in fixture for token in (
            "stale_predecessor_island_is_never_entered",
            "exact Link-30 predecessor length",
            "installer never enters stale transaction context")),
        "active_not_ready_case": (
            "active_transaction_before_install_fails_closed" in fixture),
        "asan_ubsan_host_target": (
            "-fsanitize=address,undefined" in MAKEFILE.read_text(
                encoding="utf-8")),
        "installer_source_has_exact_two_complete_zero_wipes": (
            len(complete_wipes) == 2),
        "installer_source_has_no_other_target_use": (
            installer_source.count("RTOV_ISLAND_TARGET") == 2),
        "E000_S1_full_single_record_repeat": (
            not e000_s1_source_errors(runtime)),
    }
    failed = sorted(name for name, passed in rows.items() if not passed)
    require(not failed, f"source gate red: {failed}")
    return {"status": "passed", "checks": rows,
            "mutation_matrix": {
                **model_selftest(),
                **installer_wipe_model_selftest(),
                **e000_s1_source_selftest(runtime)}}


def host_gate() -> dict[str, Any]:
    payload = parse_stale_island_fixture(LINK30_FIXTURE)
    write_bound(STALE_BIN, payload)
    built = subprocess.run(
        ["make", "-B", "build/runtime-overlay-transaction-host"], cwd=ROOT,
        capture_output=True, text=True, check=False, timeout=120)
    require(built.returncode == 0,
            "host build red: " + (built.stdout + built.stderr).strip())
    env = os.environ.copy()
    env["ASAN_OPTIONS"] = "detect_leaks=1"
    env["UBSAN_OPTIONS"] = "halt_on_error=1"
    ran = subprocess.run(
        [str(BINARY), str(STALE_BIN)], cwd=ROOT, env=env,
        capture_output=True, text=True, check=False, timeout=120)
    detail = (ran.stdout + "\n" + ran.stderr).strip()
    require(ran.returncode == 0, "host lifecycle red: " + detail)
    require(EXPECTED_OUTPUT in detail, "host lifecycle output drift: " + detail)
    return {
        "status": "passed-asan-ubsan",
        "exact_predecessor": bind(STALE_BIN),
        "preinstall_transaction_context_calls": 0,
        "active_not_ready": "failed-closed-with-zero-Island-calls",
        "postinstall_image": "matches-current-generated-Island",
        "value_string": EXPECTED_OUTPUT,
        "binary": bind(BINARY),
    }


def _closure_model_violations(
        edges: list[tuple[str, str]], data_refs: list[tuple[str, str]]) -> list[str]:
    violations: list[str] = []
    for source, target in edges:
        permitted = (source in ("rtov_transaction_context_if_ready",
                                "rtov_transaction_context_if_ready_far")
                     and target == "rtov_transaction_context")
        if not permitted:
            violations.append("unguarded-Island-control-edge")
    if data_refs:
        violations.extend("installer-Island-data-reference" for _ in data_refs)
    return violations


def closure_model_selftest() -> dict[str, str]:
    require(not _closure_model_violations(
        [("rtov_transaction_context_if_ready", "rtov_transaction_context")],
        []), "valid guarded edge rejected")
    require(not _closure_model_violations(
        [("rtov_transaction_context_if_ready_far", "rtov_transaction_context")],
        []), "valid relocated guarded edge rejected")
    require("unguarded-Island-control-edge" in _closure_model_violations(
        [("vm_runtime_overlay_exec_family", "rtov_run_batch")], []),
        "retired Island batch edge mutation accepted")
    require("unguarded-Island-control-edge" in _closure_model_violations(
        [("vm_runtime_overlay_exec_family", "rtov_transaction_context")], []),
        "unguarded edge mutation accepted")
    require("installer-Island-data-reference" in _closure_model_violations(
        [], [("vm_runtime_overlay_exec_family", "island-table")]),
        "Island data mutation accepted")
    return {
        "transaction-ready-guarded-control-edge": "passed",
        "retired-batch-control-edge": "rejected",
        "unguarded-control-edge": "rejected",
        "installer-Island-data-reference": "rejected",
    }


def e000_s1_source_errors(runtime: str) -> list[str]:
    errors: list[str] = []
    begin = runtime.find(
        "vm_runtime_overlay_status vm_runtime_overlay_exec_batch(")
    end = runtime.find("#ifdef LISP65_RTOV_FLOOR_BREAK_RETRY_PROBE", begin)
    if begin < 0 or end < 0:
        return ["batch-wrapper-boundary-missing"]
    body = runtime[begin:end]
    if "rtov_run_batch" in runtime:
        errors.append("retired-same-payload-runner-present")
    if "vm_runtime_overlay_exec_batch_island" in runtime:
        errors.append("retired-Island-batch-wrapper-present")
    required = (
        "if (!repeat || !whitelisted)",
        "if (rtov_island_state != RTOV_ISLAND_READY)",
        "do {",
        "status = vm_runtime_overlay_exec(slot, context, entry_result);",
        "if (status != VM_RUNTIME_OVERLAY_OK) return status;",
        "if (!repeat(context, slot, *entry_result))",
        "} while (--remaining);",
        "return rtov_fail(VM_RUNTIME_OVERLAY_ERR_BATCH_LIMIT);",
    )
    for marker in required:
        if marker not in body:
            errors.append("missing-" + marker.split("(")[0].strip())
    single = body.find(
        "status = vm_runtime_overlay_exec(slot, context, entry_result);")
    predicate = body.find("if (!repeat(context, slot, *entry_result))")
    if single < 0 or predicate < 0 or single >= predicate:
        errors.append("predicate-precedes-single-record-proof")
    if "rtov_repeat = repeat" in body or "RTOV_CALL(" in body:
        errors.append("batch-bypasses-single-record-loader")
    return errors


def e000_s1_source_selftest(runtime: str) -> dict[str, str]:
    require(not e000_s1_source_errors(runtime),
            f"E000-S1 source contract red: {e000_s1_source_errors(runtime)}")
    begin = runtime.find(
        "vm_runtime_overlay_status vm_runtime_overlay_exec_batch(")
    end = runtime.find("#ifdef LISP65_RTOV_FLOOR_BREAK_RETRY_PROBE", begin)
    body = runtime[begin:end]

    def mutate_body(old: str, new: str) -> str:
        require(old in body, f"E000-S1 mutation anchor absent: {old}")
        return runtime[:begin] + body.replace(old, new, 1) + runtime[end:]

    mutations = {
        "same-payload-runner": runtime + "\nvoid rtov_run_batch(void);\n",
        "Island-batch-wrapper":
            runtime + "\nvoid vm_runtime_overlay_exec_batch_island(void);\n",
        "direct-entry-bypass": mutate_body(
            "status = vm_runtime_overlay_exec(slot, context, entry_result);",
            "*entry_result = RTOV_CALL(0, context);",
        ),
        "predicate-before-proof": mutate_body(
            "status = vm_runtime_overlay_exec(slot, context, entry_result);",
            "if (!repeat(context, slot, *entry_result)) "
            "return VM_RUNTIME_OVERLAY_OK;",
        ),
        "batch-limit-success": mutate_body(
            "return rtov_fail(VM_RUNTIME_OVERLAY_ERR_BATCH_LIMIT);",
            "return VM_RUNTIME_OVERLAY_OK;",
        ),
    }
    for name, mutated in mutations.items():
        require(e000_s1_source_errors(mutated),
                f"E000-S1 mutation accepted: {name}")
    return {name: "rejected" for name in mutations}


def _installer_nonlocal_exit_class(target_names: list[str]) -> str | None:
    """Classify a direct installer-closure edge that can escape non-locally.

    The names come from the linked ELF.  In particular, this deliberately does
    not infer safety from the C source or from the current implementation of a
    status-returning helper.
    """
    for name in target_names:
        if name == "lisp_poll":
            return "poll"
        if name.startswith("lisp_abort"):
            return "abort"
        if name == "longjmp":
            return "longjmp"
        if name == "c2_product_abort_cleanup":
            return "c2j-abort-cleanup"
    return None


def _installer_nonlocal_exit_errors(
        edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    for edge in edges:
        target_names = [str(name) for name in edge.get("target_names", [])]
        exit_class = _installer_nonlocal_exit_class(target_names)
        if exit_class is not None:
            violations.append({
                "class": exit_class,
                "source": str(edge.get("source", "")),
                "target_address": int(edge.get("target_address", 0)),
                "target_names": sorted(target_names),
            })
    return violations


def installer_nonlocal_exit_model_selftest() -> dict[str, str]:
    baseline = {
        "source": INSTALLER_ROOT,
        "target_address": 0,
    }
    mutations = {
        "poll-edge": "lisp_poll",
        "abort-edge": "lisp_abort_static",
        "longjmp-edge": "longjmp",
        "c2j-abort-cleanup-edge": "c2_product_abort_cleanup",
    }
    require(not _installer_nonlocal_exit_errors([{
        **baseline, "target_names": ["rtov_fail"],
    }]), "status-returning installer failure was rejected")
    for label, target in mutations.items():
        violations = _installer_nonlocal_exit_errors([{
            **baseline, "target_names": [target],
        }])
        require(len(violations) == 1,
                f"installer non-local-exit mutation accepted: {label}")
    require(
        {row["class"] for row in _installer_nonlocal_exit_errors([
            {**baseline, "target_names": [target]}
            for target in mutations.values()
        ])} == set(INSTALLER_NONLOCAL_EXIT_CLASSES),
        "installer non-local-exit mutation classes incomplete")
    return {
        "clean-status-returning-failure": "passed",
        **{label: "rejected" for label in mutations},
    }


def _installer_wipe_model_errors(
        wipes: list[dict[str, object]], unmatched_refs: int = 0) -> list[str]:
    """Validate the sole pre-READY data-reference exception.

    This is deliberately a complete tuple rather than an allowlist by source
    function alone.  Every field describes the one operation the written
    contract permits while the installer manufactures the Island.
    """
    errors: list[str] = []
    if len(wipes) != INSTALLER_WIPE_COUNT:
        errors.append("installer-wipe-count")
    if unmatched_refs:
        errors.append("unmatched-Island-reference")
    expected = {
        "source": INSTALLER_ROOT,
        "target_symbol": INSTALLER_WIPE_TARGET,
        "target_address": ISLAND_BASE,
        "addend": 0,
        "pair_complete": True,
        "fill": 0,
        "length": ISLAND_CAPACITY,
        "call_target": "__memset",
    }
    for index, wipe in enumerate(wipes):
        for field, value in expected.items():
            if wipe.get(field) != value:
                errors.append(f"wipe-{index}-{field}")
    return errors


def installer_wipe_model_selftest() -> dict[str, str]:
    baseline = {
        "source": INSTALLER_ROOT,
        "target_symbol": INSTALLER_WIPE_TARGET,
        "target_address": ISLAND_BASE,
        "addend": 0,
        "pair_complete": True,
        "fill": 0,
        "length": ISLAND_CAPACITY,
        "call_target": "__memset",
    }
    valid = [dict(baseline) for _ in range(INSTALLER_WIPE_COUNT)]
    require(not _installer_wipe_model_errors(valid),
            "valid complete-Island zero wipes rejected")
    mutations: dict[str, tuple[list[dict[str, object]], int]] = {
        "wrong-target": ([dict(valid[0], target_address=ISLAND_BASE + 1),
                           *valid[1:]], 0),
        "wrong-length": ([dict(valid[0], length=ISLAND_CAPACITY - 1),
                           *valid[1:]], 0),
        "nonzero-fill": ([dict(valid[0], fill=1), *valid[1:]], 0),
        "wrong-call-target": ([dict(valid[0], call_target="memcmp"),
                                *valid[1:]], 0),
        "half-address-pair": ([dict(valid[0], pair_complete=False),
                               *valid[1:]], 0),
        "extra-reference": (valid, 1),
        "missing-wipe": (valid[:-1], 0),
    }
    for name, (candidate, unmatched) in mutations.items():
        require(_installer_wipe_model_errors(candidate, unmatched),
                f"installer wipe mutation accepted: {name}")
    return {name: "rejected" for name in mutations}


def _instruction_rows(lines: list[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in lines:
        match = re.match(
            r"^\s*([0-9a-f]+):\s+(?:[0-9a-f]{2}\s+)+"
            r"([a-z][a-z0-9]*)\s*(.*?)\s*$", line)
        if not match:
            continue
        rows.append({
            "address": int(match.group(1), 16),
            "mnemonic": match.group(2),
            "operand": match.group(3).split(";", 1)[0].strip(),
        })
    return rows


def _zero_fill_backward_slice(
        rows: list[dict[str, object]], call_index: int) -> tuple[
            dict[str, object] | None, list[str]]:
    """Prove A=0 at memset from a bounded straight-line X->A slice.

    The contract cares about register value, not adjacency.  Stores preserve X
    and may therefore sit between the dominating LDX #0 and TXA.  Every other
    intervening instruction is rejected rather than guessed about; the slice
    is intentionally smaller than a general-purpose MOS data-flow engine.
    """
    errors: list[str] = []
    if call_index <= 0:
        return None, ["fill-call-has-no-predecessor"]
    allowed_stores = {"sta", "stx", "sty", "stz"}
    proof_rows: list[dict[str, object]] = []
    index = call_index - 1
    lower = max(-1, call_index - 9)

    # The nearest A-defining operation must be TXA.  Stores after it would
    # preserve A and are accepted; arithmetic, loads and control flow are not.
    while index > lower:
        row = rows[index]
        mnemonic = str(row["mnemonic"])
        if mnemonic == "txa":
            txa_index = index
            proof_rows.append(row)
            break
        if mnemonic not in allowed_stores:
            errors.append("fill-a-not-derived-from-txa")
            return None, errors
        proof_rows.append(row)
        index -= 1
    else:
        errors.append("fill-txa-absent")
        return None, errors

    # Walk backwards to the unique X definition.  Only stores are transparent;
    # any X-changing or otherwise unmodelled instruction closes the gate.
    index = txa_index - 1
    while index > lower:
        row = rows[index]
        mnemonic = str(row["mnemonic"])
        operand = str(row["operand"])
        proof_rows.append(row)
        if mnemonic == "ldx":
            immediate = re.fullmatch(r"#\$([0-9a-f]+)", operand)
            if immediate is None or int(immediate.group(1), 16) != 0:
                errors.append("fill-x-definition-is-not-zero")
                return None, errors
            proof_rows.reverse()
            return {
                "value": 0,
                "dominator": row,
                "transfer": rows[txa_index],
                "transparent_instructions": [
                    item for item in proof_rows
                    if str(item["mnemonic"]) in allowed_stores],
                "bounded_instruction_count": len(proof_rows),
            }, []
        if mnemonic not in allowed_stores:
            errors.append("fill-x-clobbered-or-unproved")
            return None, errors
        index -= 1
    errors.append("fill-x-zero-dominator-absent")
    return None, errors


def installer_wipe_dataflow_selftest() -> dict[str, str]:
    def row(mnemonic: str, operand: str = "") -> dict[str, object]:
        return {"address": 0, "mnemonic": mnemonic, "operand": operand}

    direct = [row("ldx", "#$0"), row("txa"), row("jsr", "$1234")]
    spilled = [row("ldx", "#$0"), row("sta", "$16"),
               row("txa"), row("jsr", "$1234")]
    require(_zero_fill_backward_slice(direct, 2)[1] == [],
            "direct zero-fill dataflow rejected")
    proof, errors = _zero_fill_backward_slice(spilled, 3)
    require(not errors and proof is not None
            and len(proof["transparent_instructions"]) == 1,
            "X-preserving status spill rejected")
    mutations = {
        "nonzero-x": [row("ldx", "#$1"), row("txa"), row("jsr")],
        "missing-txa": [row("ldx", "#$0"), row("sta", "$16"), row("jsr")],
        "x-clobber": [row("ldx", "#$0"), row("inx"),
                      row("txa"), row("jsr")],
    }
    rejected: dict[str, str] = {}
    for name, candidate in mutations.items():
        _proof, candidate_errors = _zero_fill_backward_slice(
            candidate, len(candidate) - 1)
        require(candidate_errors, f"zero-fill dataflow mutation accepted: {name}")
        rejected[name] = "rejected"
    return {
        "direct-ldx-zero-txa": "passed",
        "x-preserving-store": "passed",
        **rejected,
    }


def _linked_installer_wipes(
        references: list[dict[str, object]], lines: list[str],
        symbols: dict[str, dict[str, Any]]) -> tuple[
            list[dict[str, object]], list[dict[str, object]], list[str]]:
    """Bind each retained Island address pair to an exact memset machine form."""
    errors: list[str] = []
    matched: list[dict[str, object]] = []
    rows = _instruction_rows(lines)
    row_by_operand = {int(row["address"]) + 1: index
                      for index, row in enumerate(rows)}
    ordered = sorted(references, key=lambda row: int(row["offset"]))
    if len(ordered) % 2:
        errors.append("half-address-pair")
    memset_address = symbols.get("__memset", {}).get("address")
    if memset_address is None:
        errors.append("memset-symbol-absent")
    for pair_index in range(0, len(ordered) - 1, 2):
        lo, hi = ordered[pair_index:pair_index + 2]
        pair_errors: list[str] = []
        if (lo.get("type") != "R_MOS_ADDR16_LO"
                or hi.get("type") != "R_MOS_ADDR16_HI"
                or int(hi["offset"]) != int(lo["offset"]) + 4):
            pair_errors.append("incomplete-or-nonadjacent-address-pair")
        if not all(row.get("target") == INSTALLER_WIPE_TARGET
                   and int(row.get("addend", -1)) == 0
                   for row in (lo, hi)):
            pair_errors.append("wrong-target-or-addend")
        lo_index = row_by_operand.get(int(lo["offset"]))
        hi_index = row_by_operand.get(int(hi["offset"]))
        if lo_index is None or hi_index is None or hi_index != lo_index + 2:
            pair_errors.append("address-pair-does-not-bind-immediates")
            lo_index = -1
            hi_index = -1
        call_index = -1
        if lo_index >= 0:
            prefix = rows[lo_index:lo_index + 6]
            expected_prefix = [
                ("ldx", "#$0"), ("stx", "$4"),
                ("ldx", "#$18"), ("stx", "$5"),
                ("ldx", "#$8"), ("stx", "$6"),
            ]
            if [(row["mnemonic"], row["operand"]) for row in prefix] \
                    != expected_prefix:
                pair_errors.append("wrong-target-or-length-machine-form")
            for index in range(lo_index + 6, min(len(rows), lo_index + 11)):
                if rows[index]["mnemonic"] == "jsr":
                    call_index = index
                    break
            if call_index < 1:
                pair_errors.append("memset-call-absent")
            else:
                call_row = rows[call_index]
                call_operand = str(call_row["operand"])
                call_match = re.match(r"\$([0-9a-f]+)", call_operand)
                fill_proof, fill_errors = _zero_fill_backward_slice(
                    rows, call_index)
                if fill_errors:
                    pair_errors.append("nonzero-fill-machine-form")
                    pair_errors.extend(fill_errors)
                if (call_row["mnemonic"] != "jsr" or call_match is None
                        or int(call_match.group(1), 16) != memset_address):
                    pair_errors.append("wrong-call-target")
        wipe = {
            "source": INSTALLER_ROOT,
            "target_symbol": INSTALLER_WIPE_TARGET,
            "target_address": ISLAND_BASE,
            "addend": 0,
            "pair_complete": not pair_errors,
            "fill": 0 if "nonzero-fill-machine-form" not in pair_errors else -1,
            "length": (ISLAND_CAPACITY if
                       "wrong-target-or-length-machine-form" not in pair_errors
                       else -1),
            "call_target": ("__memset" if "wrong-call-target" not in pair_errors
                            and "memset-call-absent" not in pair_errors else ""),
            "relocations": [lo, hi],
            "call_address": (int(rows[call_index]["address"])
                             if call_index >= 0 else None),
            "fill_dataflow": (fill_proof if call_index >= 1 else None),
        }
        matched.extend((lo, hi))
        errors.extend(pair_errors)
        # Keep the complete tuple even on failure so the abstract validator
        # supplies the second, independent fail-closed decision.
        wipe["pair_complete"] = not pair_errors
        if not pair_errors:
            wipe["pair_complete"] = True
        matched_wipe = wipe
        # Store through a local list below without changing retained records.
        lo["_classified_wipe"] = matched_wipe
    wipes = [row["_classified_wipe"] for row in ordered
             if "_classified_wipe" in row]
    for row in ordered:
        row.pop("_classified_wipe", None)
    errors.extend(_installer_wipe_model_errors(
        wipes, len(ordered) - len(matched)))
    return wipes, matched, errors


def _facade_interval_errors(interval: dict[str, object]) -> list[str]:
    expected = {
        "section": FACADE_HANDLE_SECTION,
        "name": FACADE_HANDLE_SYMBOL,
        "address": FACADE_HANDLE_ADDRESS,
        "bytes": FACADE_HANDLE_BYTES,
        "end_exclusive": FACADE_HANDLE_ADDRESS + FACADE_HANDLE_BYTES,
        "provenance": "fixed-facade-contract",
    }
    return [name for name, value in expected.items()
            if interval.get(name) != value]


def _append_facade_interval_errors(
        interval: dict[str, object]) -> list[str]:
    expected = {
        "section": FACADE_HANDLE_SECTION,
        "name": FACADE_APPEND_SYMBOL,
        "address": FACADE_APPEND_ADDRESS,
        "bytes": FACADE_APPEND_BYTES,
        "end_exclusive": FACADE_APPEND_ADDRESS + FACADE_APPEND_BYTES,
        "provenance": "fixed-facade-contract",
    }
    return [name for name, value in expected.items()
            if interval.get(name) != value]


def _elf_symbol_section_view(elf: Path) -> dict[str, dict[str, object]]:
    """Read st_shndx through llvm-readobj without classifying symbol types."""
    text = P.run([
        str(P.TOOLCHAIN / "llvm-readobj"), "--symbols", str(elf)
    ], capture=True)
    result: dict[str, dict[str, object]] = {}
    current: dict[str, object] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if line == "Symbol {":
            current = {}
            continue
        if current is None:
            continue
        if line == "}":
            name = current.get("name")
            if isinstance(name, str):
                require(name not in result,
                        f"duplicate ELF symbol in st_shndx view: {name}")
                result[name] = current
            current = None
            continue
        name = re.match(r"Name: (\S+)(?: \(\d+\))?$", line)
        value = re.match(r"Value: 0x([0-9A-Fa-f]+)$", line)
        size = re.match(r"Size: (\d+)$", line)
        symbol_type = re.match(r"Type: (\S+)", line)
        section = re.match(r"Section: (\S+) \(0x([0-9A-Fa-f]+)\)$", line)
        if name:
            current["name"] = name.group(1)
        elif value:
            current["address"] = int(value.group(1), 16)
        elif size:
            current["bytes"] = int(size.group(1))
        elif symbol_type:
            current["type"] = symbol_type.group(1)
        elif section:
            current["section"] = section.group(1)
            current["st_shndx"] = int(section.group(2), 16)
    return result


def facade_interval_model_selftest() -> dict[str, str]:
    interval = {
        "section": FACADE_HANDLE_SECTION,
        "name": FACADE_HANDLE_SYMBOL,
        "address": FACADE_HANDLE_ADDRESS,
        "bytes": FACADE_HANDLE_BYTES,
        "end_exclusive": FACADE_HANDLE_ADDRESS + FACADE_HANDLE_BYTES,
        "provenance": "fixed-facade-contract",
    }
    require(not _facade_interval_errors(interval),
            "valid fixed-facade interval rejected")
    wrong_address = dict(interval, address=FACADE_HANDLE_ADDRESS - 1,
                         end_exclusive=FACADE_HANDLE_ADDRESS - 1
                         + FACADE_HANDLE_BYTES)
    wrong_size = dict(interval, bytes=FACADE_HANDLE_BYTES + 1,
                      end_exclusive=FACADE_HANDLE_ADDRESS
                      + FACADE_HANDLE_BYTES + 1)
    wrong_section = dict(interval, section=".text")
    require(_facade_interval_errors(wrong_address),
            "wrong-address facade interval accepted")
    require(_facade_interval_errors(wrong_size),
            "wrong-size facade interval accepted")
    require(_facade_interval_errors(wrong_section),
            "wrong st_shndx facade ownership accepted")
    record = {
        "relocation_section": ".rela" + FACADE_HANDLE_SECTION,
        "source_section": FACADE_HANDLE_SECTION,
        "offset": FACADE_HANDLE_ADDRESS + 1,
        "type": "R_MOS_ADDR16",
        "target": "c2_product_handle_normalize",
        "addend": 0,
    }
    violations, bound = P._bind_relocation_function_provenance(
        [record], function_intervals=[interval], pre_handoff_intervals=[])
    require(not violations and len(bound) == 1,
            "valid fixed-facade relocation did not bind")
    outside = dict(record, offset=FACADE_HANDLE_ADDRESS - 1)
    violations, _bound = P._bind_relocation_function_provenance(
        [outside], function_intervals=[interval], pre_handoff_intervals=[])
    require(any(row["reason"] == "source-function-unresolved"
                for row in violations),
            "unlisted facade address gained provenance")
    return {
        "exact-b5ee-three-byte-vector": "accepted",
        "wrong-address-contract-object": "rejected",
        "wrong-size-contract-object": "rejected",
        "wrong-elf-section-index": "rejected",
        "unlisted-facade-relocation-address": "rejected",
    }


def append_facade_interval_model_selftest() -> dict[str, str]:
    interval = {
        "section": FACADE_HANDLE_SECTION,
        "name": FACADE_APPEND_SYMBOL,
        "address": FACADE_APPEND_ADDRESS,
        "bytes": FACADE_APPEND_BYTES,
        "end_exclusive": FACADE_APPEND_ADDRESS + FACADE_APPEND_BYTES,
        "provenance": "fixed-facade-contract",
    }
    require(not _append_facade_interval_errors(interval),
            "valid append-plan facade interval rejected")
    wrong_address = dict(interval, address=FACADE_APPEND_ADDRESS - 1,
                         end_exclusive=FACADE_APPEND_ADDRESS - 1
                         + FACADE_APPEND_BYTES)
    wrong_size = dict(interval, bytes=FACADE_APPEND_BYTES + 1,
                      end_exclusive=FACADE_APPEND_ADDRESS
                      + FACADE_APPEND_BYTES + 1)
    wrong_section = dict(interval, section=".text")
    require(_append_facade_interval_errors(wrong_address),
            "wrong-address append facade interval accepted")
    require(_append_facade_interval_errors(wrong_size),
            "wrong-size append facade interval accepted")
    require(_append_facade_interval_errors(wrong_section),
            "wrong-section append facade interval accepted")
    record = {
        "relocation_section": ".rela" + FACADE_HANDLE_SECTION,
        "source_section": FACADE_HANDLE_SECTION,
        "offset": FACADE_APPEND_ADDRESS + 1,
        "type": "R_MOS_ADDR16",
        "target": "c2_append_plan_walk",
        "addend": 0,
    }
    violations, bound = P._bind_relocation_function_provenance(
        [record], function_intervals=[interval], pre_handoff_intervals=[])
    require(not violations and len(bound) == 1,
            "valid append-plan facade relocation did not bind")
    outside = dict(record, offset=FACADE_APPEND_ADDRESS + FACADE_APPEND_BYTES)
    violations, _bound = P._bind_relocation_function_provenance(
        [outside], function_intervals=[interval], pre_handoff_intervals=[])
    require(any(row["reason"] == "source-function-unresolved"
                for row in violations),
            "unlisted append facade address gained provenance")
    return {
        "exact-b5f1-three-byte-vector": "accepted",
        "append-wrong-address-contract-object": "rejected",
        "append-wrong-size-contract-object": "rejected",
        "append-wrong-elf-section-index": "rejected",
        "append-unlisted-facade-address": "rejected",
    }


def contractual_facade_interval(
        elf: Path, symbols: dict[str, dict[str, Any]]) -> tuple[
            dict[str, object] | None, dict[str, object] | None]:
    if FACADE_HANDLE_SYMBOL not in symbols:
        return None, None
    section_view = _elf_symbol_section_view(elf)
    evidence = section_view.get(FACADE_HANDLE_SYMBOL)
    require(evidence is not None,
            "fixed-facade vector absent from ELF st_shndx view")
    sections = P.section_table(elf)
    owner = sections.get(str(evidence.get("section")))
    require(owner is not None,
            f"fixed-facade st_shndx names absent section: {evidence}")
    address = int(evidence.get("address", -1))
    require(owner["address"] <= address
            and address + FACADE_HANDLE_BYTES
            <= owner["address"] + owner["bytes"],
            f"fixed-facade symbol is outside its st_shndx range: {evidence}")
    interval = {
        "section": evidence.get("section"),
        "name": FACADE_HANDLE_SYMBOL,
        "address": address,
        "bytes": FACADE_HANDLE_BYTES,
        "end_exclusive": address + FACADE_HANDLE_BYTES,
        "provenance": "fixed-facade-contract",
    }
    errors = _facade_interval_errors(interval)
    require(not errors,
            f"fixed-facade provenance contract drift: {errors}: {interval}")
    require(symbols[FACADE_HANDLE_SYMBOL]["address"] == address
            and symbols[FACADE_HANDLE_SYMBOL]["bytes"] == 0,
            "fixed-facade st_shndx view disagrees with linked symbol identity")
    return interval, {
        **evidence,
        "owner_address": owner["address"],
        "owner_bytes": owner["bytes"],
        "range_crosscheck": "passed",
    }


def contractual_append_facade_interval(
        elf: Path, symbols: dict[str, dict[str, Any]]) -> tuple[
            dict[str, object] | None, dict[str, object] | None]:
    if FACADE_APPEND_SYMBOL not in symbols:
        return None, None
    section_view = _elf_symbol_section_view(elf)
    evidence = section_view.get(FACADE_APPEND_SYMBOL)
    require(evidence is not None,
            "append-plan facade vector absent from ELF st_shndx view")
    sections = P.section_table(elf)
    owner = sections.get(str(evidence.get("section")))
    require(owner is not None,
            f"append facade st_shndx names absent section: {evidence}")
    address = int(evidence.get("address", -1))
    require(owner["address"] <= address
            and address + FACADE_APPEND_BYTES
            <= owner["address"] + owner["bytes"],
            f"append facade symbol is outside its st_shndx range: {evidence}")
    interval = {
        "section": evidence.get("section"),
        "name": FACADE_APPEND_SYMBOL,
        "address": address,
        "bytes": FACADE_APPEND_BYTES,
        "end_exclusive": address + FACADE_APPEND_BYTES,
        "provenance": "fixed-facade-contract",
    }
    errors = _append_facade_interval_errors(interval)
    require(not errors,
            f"append facade provenance contract drift: {errors}: {interval}")
    require(symbols[FACADE_APPEND_SYMBOL]["address"] == address
            and symbols[FACADE_APPEND_SYMBOL]["bytes"] == 0,
            "append facade st_shndx view disagrees with linked identity")
    return interval, {
        **evidence,
        "owner_address": owner["address"],
        "owner_bytes": owner["bytes"],
        "range_crosscheck": "passed",
    }


def static_elf_gate(elf: Path) -> dict[str, Any]:
    symbols = H.symbol_table(elf)
    symbol_sections = H.symbol_sections(elf)
    required = (
        "vm_runtime_overlay_install_island",
        "vm_runtime_overlay_exec_family",
        "rtov_transaction_context_if_ready",
        "rtov_transaction_context",
    )
    require(all(name in symbols for name in required),
            "pre-install Island symbol inventory incomplete")
    require(symbol_sections["rtov_transaction_context"]
            == ".lisp65_resident_island",
            "transaction context escaped resident Island")
    require(symbol_sections["rtov_transaction_context_if_ready"]
            != ".lisp65_resident_island",
            "resident guard was placed inside the uninstalled Island")
    guard_name = ("rtov_transaction_context_if_ready_far"
                  if "rtov_transaction_context_if_ready_far" in symbols
                  else "rtov_transaction_context_if_ready")
    if guard_name.endswith("_far"):
        require(symbol_sections[guard_name]
                == ".lisp65_c2_mapped_far_service",
                "relocated transaction guard escaped mapped Far service")
    retired_batch_symbols = (
        "rtov_run_batch", "vm_runtime_overlay_exec_batch_island")
    require(not any(name in symbols for name in retired_batch_symbols),
            "E000-S1 retired batch symbol survived in final ELF")

    disassembly = P.run([
        str(P.TOOLCHAIN / "llvm-objdump"), "-d", str(elf)
    ], capture=True)
    nodes, _section_lines = P._sectioned_disassembly(disassembly)
    island_start, island_end = 0x1800, 0x2000
    ordinary = {
        key: row for key, row in nodes.items()
        if key[0] != ".lisp65_resident_island"
        and not key[0].startswith(".lisp65_rt_")
    }
    by_address: dict[int, list[tuple[str, int]]] = {}
    for key in ordinary:
        by_address.setdefault(key[1], []).append(key)
    root_matches = [key for key, row in ordinary.items()
                    if "vm_runtime_overlay_install_island" in row["names"]]
    require(len(root_matches) == 1, "installer root is not unique")
    pending = root_matches.copy()
    closure: set[tuple[str, int]] = set()
    edges: list[dict[str, Any]] = []
    call_edges: list[dict[str, Any]] = []
    while pending:
        key = pending.pop()
        if key in closure:
            continue
        closure.add(key)
        source_name = str(ordinary[key]["names"][0])
        for target in P._direct_call_targets(ordinary[key]["lines"]):
            target_names = {
                name for name, row in symbols.items()
                if row["address"] == target
            }
            for candidate in by_address.get(target, []):
                target_names.update(str(name)
                                    for name in ordinary[candidate]["names"])
            call_edges.append({
                "source": source_name,
                "target_address": target,
                "target_names": sorted(target_names),
            })
            if island_start <= target < island_end:
                edges.append({"source": source_name, "target_address": target,
                              "target_names": sorted(target_names)})
                continue
            pending.extend(candidate for candidate in by_address.get(target, [])
                           if candidate not in closure)

    nonlocal_exit_violations = _installer_nonlocal_exit_errors(call_edges)
    require(not nonlocal_exit_violations,
            "installer closure reaches non-local exit: "
            f"{nonlocal_exit_violations}")
    context_address = symbols["rtov_transaction_context"]["address"]
    allowed_edges = [row for row in edges
                     if (row["source"]
                         == guard_name
                         and row["target_address"] == context_address)]
    require(len(edges) == 1 and len(allowed_edges) == 1,
            f"unguarded or nonunique Island control edge: {edges}")
    runtime = RUNTIME.read_text(encoding="utf-8")
    s1_mutations = e000_s1_source_selftest(runtime)

    relocation_text = P.run([
        str(P.TOOLCHAIN / "llvm-readobj"), "--relocations", str(elf)
    ], capture=True)
    records = P._relocation_records(relocation_text)
    island_symbols = {
        name for name, row in symbols.items()
        if island_start <= row["address"] < island_end
    }
    island_records = []
    for row in records:
        target = str(row["target"])
        target_address = symbols.get(target, {}).get("address")
        if (target in island_symbols or
                target_address is not None
                and island_start <= target_address + int(row["addend"])
                < island_end):
            island_records.append(row)
    intervals = P._sized_function_intervals(elf)
    facade_interval, facade_section_evidence = contractual_facade_interval(
        elf, symbols)
    if facade_interval is not None:
        intervals.append(facade_interval)
    append_facade_interval, append_facade_section_evidence = (
        contractual_append_facade_interval(elf, symbols))
    if append_facade_interval is not None:
        intervals.append(append_facade_interval)
    violations, bound = P._bind_relocation_function_provenance(
        island_records, function_intervals=intervals, pre_handoff_intervals=[])
    require(not violations, f"relocation provenance red: {violations}")
    closure_names = {str(name) for key in closure
                     for name in ordinary[key]["names"]}
    island_refs: list[dict[str, Any]] = []
    for row in bound:
        source = str(row["source_function"]["name"])
        target = str(row["target"])
        target_address = symbols.get(target, {}).get("address")
        if (source in closure_names and
                (target in island_symbols or
                 target_address is not None
                 and island_start <= target_address + int(row["addend"])
                 < island_end)):
            island_refs.append(row)
    non_guard_refs = [row for row in island_refs
                      if not (row["source_function"]["name"]
                              == guard_name
                              and (row["target"]
                                   == "rtov_transaction_context"
                                   or (row["target"]
                                       == ".lisp65_resident_island"
                                       and int(row["addend"])
                                       == context_address - island_start)))]
    installer_refs = [row for row in non_guard_refs
                      if (row["source_function"]["name"] == INSTALLER_ROOT
                          and row["target"] == INSTALLER_WIPE_TARGET)]
    unexpected_refs = [row for row in non_guard_refs
                       if row not in installer_refs]
    installer_key = next(
        key for key, row in ordinary.items()
        if INSTALLER_ROOT in row["names"])
    wipes, matched_wipe_refs, wipe_errors = _linked_installer_wipes(
        installer_refs, ordinary[installer_key]["lines"], symbols)
    require(not unexpected_refs and not wipe_errors
            and len(matched_wipe_refs) == len(installer_refs),
            "installer closure has non-manufacturing Island reference: "
            f"unexpected={unexpected_refs} wipe_errors={wipe_errors} "
            f"installer_refs={installer_refs}")
    facade_refs = [row for row in bound
                   if row["source_function"]["name"]
                   == FACADE_HANDLE_SYMBOL]
    if facade_interval is not None:
        require(len(facade_refs) == 1
                and facade_refs[0]["target"]
                == "c2_product_handle_normalize",
                f"fixed-facade Island provenance drift: {facade_refs}")
    append_facade_refs = [row for row in bound
                          if row["source_function"]["name"]
                          == FACADE_APPEND_SYMBOL]
    if append_facade_interval is not None:
        require(len(append_facade_refs) == 1
                and append_facade_refs[0]["target"]
                == "c2_append_plan_walk",
                "append-plan facade Island provenance drift: "
                f"{append_facade_refs}")

    helper_key = next(
        key for key, row in ordinary.items()
        if guard_name in row["names"])
    helper_instructions = P._machine_instructions(ordinary[helper_key]["lines"])
    branch_count = sum(1 for mnemonic, _operand in helper_instructions
                       if mnemonic.startswith("b"))
    require(branch_count >= 2,
            "linked resident guard lacks the two fail-closed branches")
    require(not guard_source_errors(RUNTIME.read_text(encoding="utf-8")),
            "linked guard no longer matches source contract")
    return {
        "status": "passed-static-preinstallation-Island-gate",
        "installer_root": {
            "section": root_matches[0][0], "address": root_matches[0][1]},
        "reachable_function_count": len(closure),
        "reachable_functions": sorted(closure_names),
        "installer_direct_call_edges": call_edges,
        "installer_non_local_exit_gate": {
            "status": "passed-zero-linked-non-local-exit-edges",
            "forbidden_classes": list(INSTALLER_NONLOCAL_EXIT_CLASSES),
            "linked_violations": nonlocal_exit_violations,
            "mutations": installer_nonlocal_exit_model_selftest(),
        },
        "Island_control_edges": edges,
        "Island_relocation_references": island_refs,
        "permitted_pre_READY_manufacturing_writes": wipes,
        "fixed_facade_Island_references": facade_refs + append_facade_refs,
        "fixed_facade_contract_interval": facade_interval,
        "fixed_facade_section_evidence": facade_section_evidence,
        "append_facade_contract_interval": append_facade_interval,
        "append_facade_section_evidence": append_facade_section_evidence,
        "unguarded_or_consuming_data_references": [],
        "guard_machine_branch_count": branch_count,
        "E000_S1": {
            "status": "passed-full-single-record-repeat",
            "retired_symbols": list(retired_batch_symbols),
            "final_ELF_occurrences": 0,
            "replacement":
                "vm_runtime_overlay_exec once per requested repetition",
            "deliberate_cost": "cold batch operations repeat verification",
            "mutations": s1_mutations,
        },
        "negative_matrix": {
            **closure_model_selftest(),
            **installer_nonlocal_exit_model_selftest(),
            **facade_interval_model_selftest(),
            **append_facade_interval_model_selftest(),
            **installer_wipe_model_selftest(),
            **installer_wipe_dataflow_selftest(),
        },
        "claim_limit": (
            "Static direct-control and retained-relocation proof. Before READY, "
            "the sole Bank-0 data-reference exception is the machine-proven "
            "complete-Island zero wipe used to erase or fail-close the destination; "
            "no Island-owned value is consumed and no unguarded code is entered."),
    }


def build_receipt() -> dict[str, Any]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    require(contract.get("status")
            == "owner-authorized-one-host-and-capacity-probe",
            "authorization contract status drift")
    require(sha(FIRST_RED)
            == contract["historical_identity"][
                "link31_first_red_diagnosis_sha256"],
            "Link-31 first-red diagnosis drift")
    return {
        "format": "lisp65-c2-preinstall-island-guard-contract-probe-v1",
        "recorded_on": "2026-07-20",
        "status": "passed-host-source-mutations-capacity-not-run",
        "authorization": {
            "contract": bind(CONTRACT),
            "document": bind(DOCUMENT),
            "first_red_diagnosis": bind(FIRST_RED),
            "link31_structural_receipt": bind(STRUCTURAL),
            "product_links": 0,
            "hardware_runs": 0,
        },
        "implementation": {
            "runtime": bind(RUNTIME),
            "header": bind(HEADER),
            "fixture": bind(FIXTURE),
            "makefile": bind(MAKEFILE),
        },
        "source_gate": source_gate(),
        "host_lifecycle_gate": host_gate(),
        "claim_limit": (
            "Host/source/ASAN/UBSAN and exact stale-Link-30 lifecycle proof only. "
            "Capacity, linked static closure, product SHA, hardware, latency, "
            "promotion and release are not claimed."),
        "next_gate": (
            "Exactly one product-shaped seed may measure capacity/placement and "
            "run the static pre-installation Island gate; any red stops before "
            "a successor product link."),
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("selftest", "write", "check"))
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            source_gate()
            closure_model_selftest()
            installer_nonlocal_exit_model_selftest()
            installer_wipe_dataflow_selftest()
            print("c2-preinstall-island-guard: SELFTEST PASS source+mutations")
            return 0
        value = build_receipt()
        data = canonical(value)
        if args.action == "write":
            if RECEIPT.exists():
                require(RECEIPT.read_bytes() == data,
                        "refusing to overwrite divergent receipt")
            else:
                RECEIPT.write_bytes(data)
            os.chmod(RECEIPT, 0o444)
            verb = "WROTE"
        else:
            require(RECEIPT.is_file() and RECEIPT.read_bytes() == data,
                    "contract receipt absent or drifted")
            verb = "CHECK PASS"
        print("c2-preinstall-island-guard: " + verb
              + " host=green stale-link30=green preinstall-calls=0 product-links=0")
        return 0
    except (GateError, OSError, KeyError, ValueError,
            json.JSONDecodeError, subprocess.SubprocessError) as exc:
        print(f"c2-preinstall-island-guard: FAIL {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
