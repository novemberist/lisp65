#!/usr/bin/env python3
"""Prove the private function-cell ABI and restorable trace transaction."""

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

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_stdlib as STDLIB  # noqa: E402
import evidence_era as ERA  # noqa: E402


CONTRACT = ROOT / "config/c2-trace-core-abi.json"
LEDGER = ROOT / "config/bytecode-abi-ledger.json"
REGISTRY = ROOT / "config/v2-native-function-registry.json"
DISPATCH = ROOT / "src/v2_native_function_dispatch.h"
VIEWS = ROOT / "tools/host-lisp/v2_native_function_views_generated.py"
VM_SOURCE = ROOT / "src/vm.c"
SESSION_SERVICE = ROOT / "src/intern_service_overlay.c"
P0_SOURCE = ROOT / "tools/host-lisp/bytecode_p0.py"
C2_RUNTIME = ROOT / "src/c2_product_runtime.c"
TRACE_SOURCE = ROOT / "lib/inspect-trace.lisp"
TRACE_SUITE = ROOT / "tests/bytecode/libs/p0-inspect-trace.json"
HISTORICAL_SCOPE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-link92-r5-trace-fix-library-scope.json"
)
BUILD = ROOT / "build/c2.3/trace-core-abi"
PREFIX = BUILD / "inspect"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-trace-core-abi-host-receipt.json"
)
GATES = ROOT / "mk/gates.mk"
PLAN = ROOT / "docs/planning/trace-core-abi-work-plan.md"
FORMAT = "lisp65-c2.3-trace-core-abi-host-v1"
SEALED_COMMIT = "3a0aba8e1b980a855eb0edde05c5862c430da968"
TRACE_REPLAY_WORLD_COMMIT = "48164d54ac1da418d84377a2a067a12170c0782e"
TRACE_REPLAY_EVAL_SHA256 = (
    "f5aa454d38c66a64363f58323104db04db929055e6ff9cfeeec8134bf9e011e3"
)
TRACE_REPLAY_EVAL_SUFFIX = (
    "build/bytecode/dialect-v2/sources/lib/dialect-v2/eval-runtime.lisp"
)
TRACE_REPLAY_READ_LINE_SUFFIX = "lib/stdlib-read-line.lisp"
TRACE_REPLAY_READ_LINE_SHA256 = (
    "c074cc7ec2c96cd716d7b670c287704e62d583f7f22fccc022a1b19ee5bd8cac"
)
TRACE_REPLAY_RESIDENT_SUITE_SUFFIX = (
    "tests/bytecode/libs/p0-stdlib-ship-input-wait-base.json"
)
TRACE_REPLAY_RESIDENT_SUITE_SHA256 = (
    "46ec56eca12e89196c11013d36a7c55c6ea14248bdeeb20bd40207541ed593ff"
)
TRACE_REPLAY_SUCCESSOR_FUNCTIONS = {
    "%c2-direct-expression-p",
    "%c2-direct-expression",
}


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(raw),
        "sha256": sha(raw),
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def build_library() -> dict[str, Any]:
    BUILD.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(HOST / "bytecode_p0_stdlib.py"),
        "--check", "--emit-artifacts", str(PREFIX),
        "--artifact-role", "disk-lib", "--base-addr", "0x000000",
        str(TRACE_SUITE),
    ]
    # This receipt seals the Link-93 resident world.  Recompiling its inspect
    # library against whatever generated resident suite happens to be live
    # would make a historical replay depend on a mutable symbol space.  Keep
    # the original CLI identity and output, but invert the producer onto its
    # content-bound eval-runtime source and function inventory.  The override
    # is scoped to this call and never rewrites the generated worktree files.
    def historical_blob(path: str, expected_sha256: str) -> bytes:
        result = subprocess.run(
            ["git", "show", f"{TRACE_REPLAY_WORLD_COMMIT}:{path}"],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        require(result.returncode == 0,
                f"trace replay historical input is unavailable: {path}")
        require(sha(result.stdout) == expected_sha256,
                f"trace replay historical input content drift: {path}")
        return result.stdout

    historical_eval = historical_blob(
        "lib/dialect-v2/eval-runtime.lisp", TRACE_REPLAY_EVAL_SHA256)
    historical_read_line = historical_blob(
        TRACE_REPLAY_READ_LINE_SUFFIX, TRACE_REPLAY_READ_LINE_SHA256)
    historical_resident = historical_blob(
        TRACE_REPLAY_RESIDENT_SUITE_SUFFIX,
        TRACE_REPLAY_RESIDENT_SUITE_SHA256,
    )

    original_read_source = STDLIB._read_source
    original_read_suite = STDLIB._read_suite

    def replay_read_source(path: str) -> str:
        key = str(path).replace("\\", "/")
        if key.endswith(TRACE_REPLAY_EVAL_SUFFIX):
            return historical_eval.decode("utf-8")
        if key.endswith(TRACE_REPLAY_READ_LINE_SUFFIX):
            return historical_read_line.decode("utf-8")
        return original_read_source(path)

    def replay_read_suite(path: str, seen: set[str] | None = None) -> dict[str, Any]:
        key = str(path).replace("\\", "/")
        if key.endswith(TRACE_REPLAY_RESIDENT_SUITE_SUFFIX):
            child = json.loads(historical_resident.decode("utf-8"))
            base = original_read_suite(str(
                ROOT / "tests/bytecode/libs/p0-stdlib-time-base.json"))
            suite = STDLIB._apply_suite_transforms(
                STDLIB._merge_suite(base, child))
            suite["_suite_path"] = str(path)
            suite["_suite_dir"] = str(
                ROOT / "tests/bytecode/libs")
        else:
            suite = original_read_suite(path, seen=seen)
        suite["functions"] = [
            name for name in suite.get("functions", [])
            if name not in TRACE_REPLAY_SUCCESSOR_FUNCTIONS
        ]
        return suite

    STDLIB._read_source = replay_read_source
    STDLIB._read_suite = replay_read_suite
    try:
        info = STDLIB.check_paths([str(TRACE_SUITE)], base_addr=0)
        artifact = STDLIB.emit_artifacts(
            str(TRACE_SUITE), STDLIB._read_suite(str(TRACE_SUITE)), str(PREFIX),
            base_addr=0, artifact_role="disk-lib",
        )
    finally:
        STDLIB._read_source = original_read_source
        STDLIB._read_suite = original_read_suite

    stdout = (
        "bytecode-p0-stdlib-check: PASS "
        f"suites={info['suites']} functions={info['functions']} "
        f"cases={info['cases']} objects={info['objects']} "
        f"code_bytes={info['code_bytes']} dir_bytes={info['directory_bytes']} "
        f"steps={info['steps']}\n"
        "bytecode-p0-disk-lib-artifacts: WROTE "
        f"{artifact['prefix']} objects={artifact['objects']} "
        f"code_bytes={artifact['code_bytes']} ext_bytes={artifact['external_bytes']} "
        f"dir_bytes={artifact['directory_bytes']} manifest={artifact['manifest']} "
        f"disasm={artifact['disasm']}\n"
        "bytecode-p0-stdlib-embed-check: PASS "
        f"cases={artifact['embed_cases']} objects={artifact['objects']} "
        f"literal_nodes={artifact['literal_nodes']} "
        f"literal_patches={artifact['literal_patches']} "
        f"steps={artifact['embed_steps']}\n"
    )
    manifest = load(PREFIX.with_suffix(".manifest.json"))
    disassembly = PREFIX.with_suffix(".disasm.txt").read_text(encoding="utf-8")
    require(disassembly.count("CALLPRIM prim=20:set-symbol-value") >= 2
            and "[002] %function-cell" in disassembly,
            "inspect artifact does not carry the private carrier wrapper")
    require(manifest.get("code_bytes") == 558,
            "inspect trace candidate code size drift")
    return {
        "command": command,
        "stdout_sha256": sha(stdout.encode("utf-8")),
        "manifest": bind(PREFIX.with_suffix(".manifest.json")),
        "extended_image": bind(PREFIX.with_suffix(".ext.bin")),
        "disassembly": bind(PREFIX.with_suffix(".disasm.txt")),
        "code_bytes": manifest["code_bytes"],
        "private_carrier_call_count": 2,
    }


def abi_contract() -> dict[str, Any]:
    contract = load(CONTRACT)
    ledger = load(LEDGER)
    registry = load(REGISTRY)
    dispatch = DISPATCH.read_text(encoding="utf-8")
    views = VIEWS.read_text(encoding="utf-8")
    vm = VM_SOURCE.read_text(encoding="utf-8")
    service = SESSION_SERVICE.read_text(encoding="utf-8")
    p0 = P0_SOURCE.read_text(encoding="utf-8")
    require(contract.get("format") == "lisp65-c2.3-trace-core-abi-contract-v1",
            "trace ABI contract format drift")
    require(contract.get("status")
            == "link93-host-media-green-hardware-pending"
            and contract.get("next_link", {}).get("number") == 93
            and contract.get("next_link", {}).get("state")
            == "host-media-green-hardware-pending",
            "trace ABI lifecycle contract drift")
    identities = {row["id"]: row["canonical_name"]
                  for row in ledger["prim_identities"]}
    profile = next(row for row in ledger["profiles"]
                   if row["id"] == "dialect-v2")
    require(identities.get(20) == "set-symbol-value"
            and 20 in profile["prim_ids"]["active"]
            and 69 not in identities
            and profile["prim_ids"]["reserved_ranges"] == [[69, 255]],
            "private carrier preserved-ID ABI classification drift")
    restricted = next((row for row in registry["restricted_primitives"]
                       if row["name"] == "set-symbol-value"), None)
    require(restricted is not None and restricted["value"] == 20
            and restricted["restricted_views"] == ["apply", "function-kind"],
            "Prim 20 carrier restriction contract drift")
    require('X("%function-cell", 69)' not in dispatch
            and "%function-cell" not in views,
            "private wrapper escaped into a native ABI view")
    namespace: dict[str, Any] = {}
    exec(compile(views, str(VIEWS), "exec"), namespace)
    require(namespace["ACTIVE_CALLPRIMS"].get("set-symbol-value") == 20
            and 20 not in namespace["FUNCTION_DESIGNATOR_IDS"],
            "restricted Prim 20 carrier escaped into a forbidden view")
    required_vm = (
        "case 20:  /* set-symbol-value */",
        "static __attribute__((noinline)) uint8_t vm_symbol_arg_p(obj value)",
        "if (n != 1 || !vm_symbol_arg_p(a[0]))",
        "if (n != 2 || !vm_symbol_arg_p(a[0]))",
        "old = sym_function(a[0]);",
        "if (n == 3) set_sym_function(a[0], a[1]);",
        "FIXVAL(a[2]) != 69",
        "return old;",
    )
    require(all(token in vm for token in required_vm),
            "target exact getter/swap implementation drift")
    require(vm.count("vm_symbol_arg_p(a[0])") == 6,
            "resident symbol-domain predicate stopped owning all six arms")
    require("sym_function(" not in service
            and "set_sym_function(" not in service,
            "unrelated intern Session service absorbed function-cell semantics")
    require("if prim_id == 20:" in p0
            and "if argc in (1, 3):" in p0
            and "old = self.function_cells.get(key, NIL)" in p0
            and "self.function_cells[key] = to_i16(args[1])" in p0,
            "host exact getter/swap implementation drift")
    return {
        "carrier_primitive_id": 20,
        "carrier_canonical_name": "set-symbol-value",
        "capability_name": "%function-cell",
        "private_mode_marker": 69,
        "active_prebuilt": True,
        "public_function_designator": False,
        "native_capability_name_visible": False,
        "apply_visible": False,
        "function_kind_visible": False,
        "target_semantics": "exact-get-or-atomic-swap-returning-prior",
        "target_placement": "existing-resident-prim20-dispatch-seam",
    }


def execute_primitive() -> dict[str, Any]:
    ledger = load(LEDGER)
    heap = B.Heap()
    symbol = heap.intern("sample")
    old_a = B.to_i16(0xC100)
    old_b = B.to_i16(0xC102)
    wrapper = B.to_i16(0xC104)
    vm = B.P0VM(heap=heap, abi_profile="dialect-v2", abi_ledger=ledger)
    vm.function_cells[B.to_i16(symbol)] = old_a

    def call(args: list[int]) -> int:
        stack = list(args)
        return vm._callprim(20, len(args), stack)

    first = call([symbol])
    displaced = call([symbol, wrapper, B.mkfix(69)])
    installed = call([symbol])
    restored_displaced = call([symbol, old_a, B.mkfix(69)])
    restored = call([symbol])
    require((first, displaced, installed, restored_displaced, restored)
            == (old_a, old_a, wrapper, wrapper, old_a),
            "host primitive exact getter/swap sequence failed")
    vm.function_cells[B.to_i16(symbol)] = old_b
    require(call([symbol]) == old_b and old_a != old_b,
            "exact getter cannot distinguish adjacent BCODE cells")
    rejected = []
    for name, args in (
        ("arity-zero", []),
        ("arity-four", [symbol, wrapper, B.mkfix(69), old_a]),
        ("wrong-marker", [symbol, wrapper, B.mkfix(68)]),
        ("non-symbol", [B.mkfix(1)]),
    ):
        try:
            call(args)
        except B.VMError:
            rejected.append(name)
        else:
            raise GateError(f"Prim 69 negative case survived: {name}")
    return {
        "old_a": B.obj_hex(old_a),
        "old_b": B.obj_hex(old_b),
        "wrapper": B.obj_hex(wrapper),
        "getter_distinguishes_cells": True,
        "swap_returns_prior": True,
        "restoration_exact": True,
        "negative_cases": rejected,
    }


class TraceModel:
    def __init__(self, old: str = "BCODE:748") -> None:
        self.cell = old
        self.binding: dict[str, str | None] | None = None
        self.output: list[str] = []

    def prepare(self) -> bool:
        if self.binding is None:
            self.binding = {"old": self.cell, "wrapper": None}
            return True
        return self.cell == self.binding["old"]

    def publish(self, *, fail: bool = False) -> bool:
        require(self.binding is not None, "model publish without prepare")
        if fail:
            return False  # the C2 journal restores the old cell
        self.cell = "BCODE:wrapper"
        self.binding["wrapper"] = self.cell
        return True

    def call(self, value: int) -> int:
        require(self.binding is not None and self.cell == "BCODE:wrapper",
                "model traced call without persistent wrapper")
        self.output.extend(["trace-enter", "original", "trace-exit"])
        return value + 1

    def untrace(self, *, stop_after_swap: bool = False) -> bool:
        if self.binding is None:
            return False
        old = str(self.binding["old"])
        if self.cell != old:
            self.cell = old
            if stop_after_swap:
                return False
        self.binding = None
        return True


def transaction_cases() -> dict[str, Any]:
    normal = TraceModel()
    require(normal.prepare() and normal.publish(), "normal trace publication failed")
    require(normal.call(3) == 4
            and normal.output == ["trace-enter", "original", "trace-exit"],
            "traced call did not reach exact original")
    require(not normal.prepare(), "double trace was not idempotent")
    require(normal.untrace() and normal.cell == "BCODE:748",
            "untrace did not restore exact original")
    require(not normal.untrace() and normal.cell == "BCODE:748",
            "double untrace changed restored state")

    before = TraceModel()
    require(before.prepare(), "prepare-before-publication failed")
    require(before.cell == "BCODE:748" and before.binding is not None,
            "prepare mutated the function cell")
    require(before.prepare() and before.publish(),
            "retry after pre-publication stop failed")

    inside = TraceModel()
    require(inside.prepare() and not inside.publish(fail=True),
            "injected publication rollback did not fire")
    require(inside.cell == "BCODE:748" and inside.binding is not None,
            "publication rollback leaked a wrapper cell")
    require(inside.prepare() and inside.publish(),
            "retry after journal rollback failed")

    restore = TraceModel()
    require(restore.prepare() and restore.publish(), "restore setup failed")
    require(not restore.untrace(stop_after_swap=True)
            and restore.cell == "BCODE:748" and restore.binding is not None,
            "post-swap interruption model failed")
    require(restore.untrace() and restore.binding is None,
            "untrace recovery did not finish cleanup")
    return {
        "cases": {
            "traced_call_reaches_original": True,
            "untrace_restores_exact_original": True,
            "rollback_before_publication_retryable": True,
            "rollback_inside_publication_restores_old_cell": True,
            "double_trace_idempotent": True,
            "double_untrace_idempotent": True,
            "post_restore_cleanup_recoverable": True,
        },
        "publication_model": "prepare-old; C2-journaled-defun-publish; finish-wrapper",
        "restoration_model": "exact-swap; verify-displaced; remove-binding-last",
    }


def publication_contract() -> dict[str, Any]:
    source = C2_RUNTIME.read_text(encoding="utf-8")
    trace = TRACE_SOURCE.read_text(encoding="utf-8")
    required = (
        "old = sym_function(symbol);",
        "journal[2] = row[2]; journal[3] = row[3];",
        "++c2_journal_count;",
        "set_sym_function(symbol, published);",
        "c2_restore_exports();",
    )
    require(all(item in source for item in required),
            "C2 journaled publication/rollback contract drift")
    shape = (
        "(list 'progn",
        "(list 'defun name '(&rest %inspect-trace-arguments)",
        "(list '%inspect-trace-finish (list 'quote name))",
        "(%function-cell name old)",
    )
    require(all(item in trace for item in shape),
            "trace persistent-wrapper/restoration source shape drift")
    require("lambda (&rest" not in trace,
            "trace reintroduced a transient wrapper closure")
    return {
        "wrapper_owner": "persistent named C2 definition",
        "cell_publication": "same journaled C2 definition transaction",
        "rollback_restores_old_cell": True,
        "transient_helper_escape": False,
        "binding_prepared_before_publication": True,
        "binding_removed_after_restoration": True,
    }


def historical_boundary() -> dict[str, Any]:
    value = load(HISTORICAL_SCOPE)
    require(value.get("status")
            == "descope-required-missing-function-cell-capability",
            "sealed v1.4 trace descope conclusion drift")
    require(value.get("historical_authority_commit")
            == "f426f7c71b5e85bcbec0a181fa3d1e4838e6388f",
            "v1.4 trace descope is not sealed to its owner authority")
    require(value["delivered_surface"]["function_cell_getter_delivered"] is False,
            "v1.4 history was rewritten by the successor ABI")
    return {
        "v1_4_getter_delivered": False,
        "successor_getter_delivered": True,
        "history_rewritten": False,
        "sealed_authority_commit": value["historical_authority_commit"],
    }


def gate_wiring() -> dict[str, Any]:
    gates = GATES.read_text(encoding="utf-8")
    expected = (
        "c2-trace-core-abi-selftest:",
        "python3 tools/host-lisp/c2_trace_core_abi.py selftest",
        "c2-trace-core-abi-check:",
        "python3 tools/host-lisp/c2_trace_core_abi.py check",
        "check-source: c2-trace-core-abi-check",
    )
    require(all(item in gates for item in expected),
            "trace core-ABI permanent gate wiring absent")
    return {"selftest": True, "check": True, "check_source": True}


def validate(value: dict[str, Any]) -> None:
    require(value.get("format") == FORMAT, "trace core-ABI receipt format drift")
    require(value.get("status") == "host-green-link-pending",
            "trace core-ABI host status dimmed")
    require(value["abi"]["carrier_primitive_id"] == 20
            and value["abi"]["public_function_designator"] is False,
            "private ABI identity/surface dimmed")
    require(value["primitive_execution"]["getter_distinguishes_cells"] is True
            and value["primitive_execution"]["swap_returns_prior"] is True
            and value["primitive_execution"]["restoration_exact"] is True,
            "exact getter/swap proof dimmed")
    require(all(value["transactions"]["cases"].values()),
            "trace transaction case dimmed")
    require(value["publication"]["cell_publication"]
            == "same journaled C2 definition transaction"
            and value["publication"]["transient_helper_escape"] is False,
            "persistent publication ownership dimmed")
    require(value["history"]["history_rewritten"] is False,
            "sealed v1.4 history was rewritten")
    require(value["scope"] == {
        "compiler_changed": False,
        "public_surface_changed": False,
        "sealed_v1_4_artifacts_changed": False,
        "device_contact": False,
        "release_claim": False,
        "next_action": "one-new-product-link-and-inspect-medium",
        "hardware_row": "bundled-session-core-ABI-trace-acceptance",
    }, "trace core-ABI scope broadened")


def derive() -> dict[str, Any]:
    result = {
        "format": FORMAT,
        "recorded_on": "2026-08-09",
        "status": "host-green-link-pending",
        "bindings": {
            name: ERA.era_bind(SEALED_COMMIT, path) for name, path in {
                "contract": CONTRACT,
                "plan": PLAN,
                "ABI_ledger": LEDGER,
                "native_registry": REGISTRY,
                "generated_dispatch": DISPATCH,
                "generated_host_views": VIEWS,
                "target_VM": VM_SOURCE,
                "shared_Session_service": SESSION_SERVICE,
                "host_VM": P0_SOURCE,
                "C2_runtime": C2_RUNTIME,
                "inspect_trace_source": TRACE_SOURCE,
                "inspect_trace_suite": TRACE_SUITE,
                "historical_v1_4_descope": HISTORICAL_SCOPE,
            }.items()
        },
        "abi": abi_contract(),
        "primitive_execution": execute_primitive(),
        "transactions": transaction_cases(),
        "publication": publication_contract(),
        "library_artifact": build_library(),
        "history": historical_boundary(),
        "gate_wiring": gate_wiring(),
        "scope": {
            "compiler_changed": False,
            "public_surface_changed": False,
            "sealed_v1_4_artifacts_changed": False,
            "device_contact": False,
            "release_claim": False,
            "next_action": "one-new-product-link-and-inspect-medium",
            "hardware_row": "bundled-session-core-ABI-trace-acceptance",
        },
    }
    validate(result)
    return result


def rejected_mutations(base: dict[str, Any]) -> list[str]:
    mutations: dict[str, Callable[[dict[str, Any]], None]] = {
        "make-primitive-public": lambda x: x["abi"].update(
            public_function_designator=True),
        "hide-getter-distinction": lambda x: x["primitive_execution"].update(
            getter_distinguishes_cells=False),
        "return-replacement-from-swap": lambda x: x["primitive_execution"].update(
            swap_returns_prior=False),
        "restore-symbol-not-cell": lambda x: x["primitive_execution"].update(
            restoration_exact=False),
        "skip-traced-call": lambda x: x["transactions"]["cases"].update(
            traced_call_reaches_original=False),
        "skip-restore": lambda x: x["transactions"]["cases"].update(
            untrace_restores_exact_original=False),
        "leak-pre-publication-stop": lambda x: x["transactions"]["cases"].update(
            rollback_before_publication_retryable=False),
        "leak-publication-rollback": lambda x: x["transactions"]["cases"].update(
            rollback_inside_publication_restores_old_cell=False),
        "double-trace-redefines": lambda x: x["transactions"]["cases"].update(
            double_trace_idempotent=False),
        "double-untrace-swaps": lambda x: x["transactions"]["cases"].update(
            double_untrace_idempotent=False),
        "transient-wrapper": lambda x: x["publication"].update(
            transient_helper_escape=True),
        "split-cell-publication": lambda x: x["publication"].update(
            cell_publication="separate-unowned-write"),
        "rewrite-v1.4-history": lambda x: x["history"].update(
            history_rewritten=True),
        "claim-release": lambda x: x["scope"].update(release_claim=True),
        "authorize-device-early": lambda x: x["scope"].update(device_contact=True),
    }
    rejected: list[str] = []
    for name, mutate in mutations.items():
        candidate = deepcopy(base)
        mutate(candidate)
        try:
            validate(candidate)
        except (GateError, KeyError):
            rejected.append(name)
        else:
            raise GateError(f"trace core-ABI mutation survived: {name}")
    require(len(rejected) == len(mutations), "mutation count drift")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("selftest", "record", "check"))
    args = parser.parse_args()
    try:
        if args.action == "record":
            value = derive()
        else:
            raw = RECEIPT.read_bytes()
            require(raw == ERA.era_blob(
                SEALED_COMMIT, RECEIPT.relative_to(ROOT).as_posix()),
                "sealed trace core-ABI receipt was rewritten")
            value = json.loads(raw)
            validate(value)
        mutations = rejected_mutations(value)
        if args.action == "selftest":
            print(f"trace core-ABI selftest: PASS mutations={len(mutations)}")
            return 0
        if args.action == "record":
            value["mutations_rejected"] = mutations
            value["mutation_count"] = len(mutations)
            write_json(RECEIPT, value)
            print(f"trace core-ABI: WROTE {RECEIPT.relative_to(ROOT)}")
            return 0
        live_claim = {
            "abi": abi_contract(),
            "primitive_execution": execute_primitive(),
            "transactions": transaction_cases(),
            "publication": publication_contract(),
            "history": historical_boundary(),
            "gate_wiring": gate_wiring(),
        }
        require(all(value[key] == observed for key, observed in live_claim.items()),
                "trace core-ABI live semantic claim drift")
        print("trace core-ABI check: PASS host-green-link-pending "
              "runtime-source=semantically-revalidated artifact=sealed")
        return 0
    except (GateError, B.VMError, KeyError, TypeError, ValueError,
            OSError, subprocess.SubprocessError) as error:
        print(f"trace core-ABI: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
