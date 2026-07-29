#!/usr/bin/env python3
"""Permanent contract and linked-closure gate for Session service records."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth, ElfTruthError  # noqa: E402


CONTRACT = ROOT / "config/c2-session-service-contract.json"
SERVICE = ROOT / "src/intern_service_overlay.c"
HEADER = ROOT / "src/intern_service_overlay.h"
VM = ROOT / "src/vm.c"
RUNTIME = ROOT / "src/vm_runtime_overlay.c"
FIXTURE = ROOT / "scripts/c2-intern-session-service-main.c"
BUSY_FIXTURE = ROOT / "scripts/c2-intern-session-service-busy-main.c"
TOOLCHAIN = ROOT / "tools/llvm-mos/bin"


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def source_gate(texts: dict[Path, str] | None = None) -> dict[str, Any]:
    rows = texts or {
        path: path.read_text(encoding="utf-8")
        for path in (SERVICE, HEADER, VM, RUNTIME)
    }
    service = rows[SERVICE]
    header = rows[HEADER]
    vm = rows[VM]
    runtime = rows[RUNTIME]
    contract = load(CONTRACT)
    require(
        contract["status"] == "authorized-product-probe-pending"
        and contract["pattern_class"] == "Session-Service-Record"
        and contract["closure"]["overlay_to_service"].startswith("no ")
        and "VM_RUNTIME_OVERLAY_ERR_BUSY"
            in contract["closure"]["service_while_overlay"],
        "Session-service contract drift")
    require(
        service.count(".lisp65_rt_intern_service") == 1
        and "noinline, used" in service
        and service.count("lisp65_intern_service_entry") == 1
        and "static " not in service
        and "str_copy_out(context->args[0]" in service
        and "context->result = intern(sym_name_scratch);" in service,
        "service body lost named, stateless single-entry form")
    require(
        "LISP65_INTERN_SERVICE_ABI_VERSION 1u" in header
        and '#include "buffer_overlay.h"' in header
        and "lisp65_intern_service_context" not in header,
        "service context ABI drift")
    case = vm[vm.index("case 68:"):vm.index("#endif", vm.index("case 68:"))]
    service_case = case[:case.index("#else")]
    require(
        service_case.count("return vm_buffer_call(pid, a, n);") == 1
        and "vm_runtime_overlay_exec(" not in service_case
        and ("if (pid == 68u) slot = LISP65_INTERN_SERVICE_SLOT;")
            in vm
        and "if (n != 1)" in service_case
        and "if (!vm_string_arg_p(a[0]))" in service_case
        and "if (length > LISP65_SYMBOL_NAME_MAX)" in service_case,
        "resident intern stub lost shared-service-facade form")
    require(
        vm.count("static __attribute__((noinline)) uint8_t "
                 "vm_string_arg_p(obj value)") == 1
        and vm.count("vm_string_arg_p(a[0])") == 3,
        "stringp and intern lost their one-copy resident domain predicate")
    facade = vm[
        vm.index("static LISP65_RESIDENT_ISLAND_FN obj vm_buffer_call("):
        vm.index("\n}\n\n#endif", vm.index(
            "static LISP65_RESIDENT_ISLAND_FN obj vm_buffer_call(")) + 2]
    owner_bank = facade.index("vm_buf_bank = 0xFFu;")
    owner_off = facade.index("vm_buf_off = 0xFFFFu;")
    first_context_write = facade.index("context->args = a;")
    require(
        owner_bank < first_context_write
        and owner_off < first_context_write
        and vm.count("BUF_ENSURE_MINE(pcur);") == 2,
        "shared service context can masquerade as the live VM code buffer")
    require(
        "if (length > LISP65_SYMBOL_NAME_MAX)" in service,
        "cold service lost its defensive length recheck")
    family = runtime[
        runtime.index("vm_runtime_overlay_status vm_runtime_overlay_exec_family"):
        runtime.index("vm_runtime_overlay_status vm_runtime_overlay_exec(")]
    busy = family.index("if (rtov_busy) return VM_RUNTIME_OVERLAY_ERR_BUSY;")
    require(
        busy < family.index("rtov_busy = 1;")
        and busy < family.index("if (!rtov_wipe())")
        and busy < family.index("rtov_run_verifier(")
        and busy < family.index("rtov_read_source("),
        "busy rejection no longer dominates every window mutation/read")
    return {
        "status": "passed-contract-stub-stateless-and-busy-dominance",
        "service_entry_count": 1,
        "service_static_state_bytes": 0,
        "resident_validation": ["arity", "T_STR", "name-length"],
        "resident_stub": "existing vm_buffer_call plus one slot selection",
        "busy_precedes": ["wipe", "verifier", "payload-read", "entry"],
    }


def mutation_gate() -> list[str]:
    source = {
        path: path.read_text(encoding="utf-8")
        for path in (SERVICE, HEADER, VM, RUNTIME)
    }
    mutations = {
        "busy-check-removed": (RUNTIME,
            "if (rtov_busy) return VM_RUNTIME_OVERLAY_ERR_BUSY;",
            "if (0) return VM_RUNTIME_OVERLAY_ERR_BUSY;"),
        "busy-check-after-write": (RUNTIME,
            "if (rtov_busy) return VM_RUNTIME_OVERLAY_ERR_BUSY;",
            "rtov_busy = 1; /* mutated ordering */"),
        "service-section-renamed": (SERVICE,
            ".lisp65_rt_intern_service", ".lisp65_rt_intern_private"),
        "service-inline": (SERVICE, "noinline, used", "always_inline, used"),
        "service-static-state": (SERVICE,
            "#ifdef LISP65_INTERN_SESSION_SERVICE",
            "#ifdef LISP65_INTERN_SESSION_SERVICE\nstatic uint8_t shadow;"),
        "service-second-entry": (SERVICE,
            "lisp65_intern_service_entry(void *opaque)",
            "lisp65_intern_service_entry(void *opaque) /* "
            "lisp65_intern_service_entry */"),
        "direct-entry-call": (VM,
            "return vm_buffer_call(pid, a, n);",
            "return lisp65_intern_service_entry(a);"),
        "slot-unbound": (VM, "LISP65_INTERN_SERVICE_SLOT",
            "LISP65_BUFFER_OVERLAY_ALLOC_SLOT"),
        "arity-validation-removed": (VM,
            "case 68: { /* intern -- canonical public "
            "string-to-symbol operation */\n"
            "#ifdef LISP65_INTERN_SESSION_SERVICE\n"
            "        uint16_t length;\n"
            "        if (n != 1)",
            "case 68: { /* intern -- canonical public "
            "string-to-symbol operation */\n"
            "#ifdef LISP65_INTERN_SESSION_SERVICE\n"
            "        uint16_t length;\n"
            "        if (0 && n != 1)"),
        "type-validation-removed": (VM,
            "case 68: { /* intern -- canonical public "
            "string-to-symbol operation */\n"
            "#ifdef LISP65_INTERN_SESSION_SERVICE\n"
            "        uint16_t length;\n"
            "        if (n != 1) { vm_status = VM_ARITY; return NIL; }\n"
            "        if (!vm_string_arg_p(a[0]))",
            "case 68: { /* intern -- canonical public "
            "string-to-symbol operation */\n"
            "#ifdef LISP65_INTERN_SESSION_SERVICE\n"
            "        uint16_t length;\n"
            "        if (n != 1) { vm_status = VM_ARITY; return NIL; }\n"
            "        if (0 && !vm_string_arg_p(a[0]))"),
        "string-predicate-duplicated": (VM,
            "return (n >= 1 && vm_string_arg_p(a[0])) ? vm_t : NIL;",
            "return (n >= 1 && IS_PTR(a[0]) && "
            "cell_type(a[0]) == T_STR) ? vm_t : NIL;"),
        "vm-codebuf-bank-owner-not-invalidated": (VM,
            "vm_buf_bank = 0xFFu;",
            "vm_buf_bank = vm_buf_bank;"),
        "vm-codebuf-object-owner-not-invalidated": (VM,
            "vm_buf_off = 0xFFFFu;",
            "vm_buf_off = vm_buf_off;"),
        "vm-codebuf-owner-invalidated-too-late": (VM,
            "vm_buf_off = 0xFFFFu;\n"
            "    context->args = a;",
            "context->args = a;\n"
            "    vm_buf_off = 0xFFFFu;"),
        "length-validation-removed": (SERVICE,
            "if (length > LISP65_SYMBOL_NAME_MAX)",
            "if (0 && length > LISP65_SYMBOL_NAME_MAX)"),
    }
    rejected: list[str] = []
    for name, (path, old, new) in mutations.items():
        require(old in source[path], f"mutation anchor absent: {name}")
        changed = dict(source)
        changed[path] = source[path].replace(old, new, 1)
        try:
            source_gate(changed)
        except (GateError, ValueError):
            rejected.append(name)
    require(len(rejected) == len(mutations),
            f"Session-service source mutation survived: "
            f"{sorted(set(mutations) - set(rejected))}")
    return rejected


def _compile(out: Path, name: str, sources: list[Path],
             definitions: list[str]) -> str:
    binary = out / name
    command = [
        "cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", *definitions, "-Isrc",
        *(str(path) for path in sources), "-o", str(binary),
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    run = subprocess.run(
        [str(binary)], cwd=ROOT, check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return run.stdout.strip()


def host_fixtures(out: Path) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    service = _compile(
        out, "intern-service",
        [FIXTURE, SERVICE],
        ["-DLISP65_VM", "-DLISP65_STRING_ARENA",
         "-DLISP65_INTERN_SESSION_SERVICE"])
    busy = _compile(
        out, "intern-service-busy",
        [BUSY_FIXTURE, ROOT / "src/vm_runtime_overlay.c"],
        [
            "-DLISP65_VM", "-DLISP65_RUNTIME_OVERLAY_HOST_TEST",
            "-DLISP65_RUNTIME_OVERLAY_CATALOG_VERSION=4",
            "-DLISP65_RTOV_CRC_CONVERGENCE",
            "-DLISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES",
            "-DLISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_FILE_OFF=0x0500u",
            "-DLISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_FILE_SIZE=8u",
            "-DLISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_ENTRY_OFFSET=0u",
            "-DLISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_CRC16=0x37e8u",
            "-DLISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_FILE_OFF=0x0600u",
            "-DLISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_FILE_SIZE=8u",
            "-DLISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_ENTRY_OFFSET=0u",
            "-DLISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_CRC16=0x5afbu",
        ])
    require(
        service == ("c2-intern-session-service: PASS cases=5 "
                    "exact-name=33 state-bytes=0")
        and busy == ("c2-intern-session-service-busy: PASS bytes=1792 "
                     "transport=ERR_BUSY entry=NOT_RUN "
                     "window=byte-identical family-negatives=4"),
        "Session-service host fixture output drift")
    return {
        "service": service,
        "busy_window": busy,
        "asan": "passed",
        "ubsan": "passed",
    }


def linked_gate(elf: Path, session_manifest: Path,
                boot_manifest: Path) -> dict[str, Any]:
    truth = ElfTruth.read(
        elf, llvm_readobj=TOOLCHAIN / "llvm-readobj")
    section = truth.section(".lisp65_rt_intern_service")
    entry = truth.symbol("lisp65_intern_service_entry")
    require(
        0 < section.bytes <= 1792
        and entry.section == section.name
        and section.address <= entry.value < section.address + section.bytes,
        "linked Session service escaped its named bounded slice")
    session = load(session_manifest)
    boot = load(boot_manifest)
    session_rows = [
        row for row in session["slices"]
        if row["name"] == "intern-session-service"]
    boot_rows = [
        row for row in boot["slices"]
        if row["name"] == "intern-session-service"]
    require(
        len(session_rows) == 1 and not boot_rows
        and session_rows[0]["section"] == section.name
        and session_rows[0]["memory_size"] == section.bytes,
        "service catalog family/section identity drift")

    exec_edges = [
        row for row in truth.relocations
        if row.target == "vm_runtime_overlay_exec"
    ]
    overlay_edges = [
        row for row in exec_edges
        if row.source_section.startswith(".lisp65_rt_")
    ]
    require(not overlay_edges,
            "runtime overlay acquired an outbound service-loader edge")
    facade = truth.symbol("vm_buffer_call")
    service_edges = [
        row for row in exec_edges
        if row.source_section_index == facade.section_index
        and facade.value <= row.offset < facade.value + facade.bytes
    ]
    require(len(service_edges) == 1,
            "resident intern service stub lacks one canonical loader edge")

    def local_refs(name: str) -> list[Any]:
        symbol = truth.symbol(name)
        section = truth.section(symbol.section)
        first = symbol.value - section.address
        last = first + max(symbol.bytes, 1)
        return [
            row for row in truth.relocations
            if row.source_section_index == facade.section_index
            and facade.value <= row.offset < facade.value + facade.bytes
            and (
                row.target == name
                or (
                    row.target == symbol.section
                    and first <= row.addend < last
                )
            )
        ]

    bank_owner = local_refs("vm_buf_bank")
    object_owner = local_refs("vm_buf_off")
    context_buffer = local_refs("vm_codebuf")
    require(
        bank_owner and object_owner and context_buffer
        and max(row.offset for row in bank_owner + object_owner)
            < min(row.offset for row in context_buffer),
        "linked service facade writes vm_codebuf before retiring its owner")
    return {
        "status":
            "passed-one-Session-record-no-overlay-recursion-generation-bound",
        "slot": session_rows[0]["id"],
        "slice_bytes": section.bytes,
        "session_records": len(session["slices"]),
        "boot_records": len(boot["slices"]),
        "overlay_to_loader_edges": 0,
        "shared_facade_to_loader_edges": 1,
        "vm_codebuf_owner_invalidation": {
            "bank_edges": len(bank_owner),
            "object_edges": len(object_owner),
            "first_context_edge": min(row.offset for row in context_buffer),
            "ordering": "both-owner-tags-before-first-context-write",
        },
        "generation_binding":
            "canonical selected Session-family catalog and generation",
    }


def main() -> int:
    try:
        require(len(sys.argv) in (2, 5),
                "usage: gate OUT [ELF SESSION_MANIFEST BOOT_MANIFEST]")
        out = Path(sys.argv[1])
        result = {
            "source": source_gate(),
            "source_mutations_rejected": mutation_gate(),
            "host": host_fixtures(out),
        }
        if len(sys.argv) == 5:
            result["linked"] = linked_gate(
                Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
        print(json.dumps(result, indent=2, sort_keys=True))
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            subprocess.CalledProcessError, GateError,
            ElfTruthError) as error:
        print(f"c2-intern-session-service-gate: FIRST RED: {error}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
