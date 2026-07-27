#!/usr/bin/env python3
"""Permanent gate for retired BADOPCODE detail and preserved DIRMISS detail."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from elf_truth import ElfTruth


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-vm-badopcode-detail-contract.json"
VM = ROOT / "src/vm.c"
VM_H = ROOT / "src/vm.h"
RUNTIME = ROOT / "src/c2_product_runtime.c"
EVAL = ROOT / "src/eval.c"
EVAL_H = ROOT / "src/eval.h"
OVERLAY_C = ROOT / "src/error_overlay.c"
OVERLAY_H = ROOT / "src/error_overlay.h"
OVERLAY_S = ROOT / "src/l65e_bcode_ordinal.s"


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def function_body(text: str, signature: str) -> str:
    start = -1
    search = 0
    while True:
        start = text.find(signature, search)
        require(start >= 0, f"function absent: {signature}")
        brace = text.find("{", start)
        require(brace >= 0, f"function body absent: {signature}")
        semicolon = text.find(";", start, brace)
        if semicolon < 0:
            break
        search = semicolon + 1
    depth = 0
    for index in range(brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise GateError(f"unterminated function: {signature}")


def _sources() -> dict[str, str]:
    return {
        "vm": VM.read_text(encoding="utf-8"),
        "vm_h": VM_H.read_text(encoding="utf-8"),
        "runtime": RUNTIME.read_text(encoding="utf-8"),
        "eval": EVAL.read_text(encoding="utf-8"),
        "eval_h": EVAL_H.read_text(encoding="utf-8"),
        "overlay_c": OVERLAY_C.read_text(encoding="utf-8"),
        "overlay_h": OVERLAY_H.read_text(encoding="utf-8"),
        "overlay_s": OVERLAY_S.read_text(encoding="utf-8"),
    }


RETIRED = (
    "vm_badopcode_detail", "VM_BADDETAIL_", "BADOPCODE_DETAIL",
    "l65e_emit_fixnum_coordinate",
    "code == LISP65_ERR_VM_BAD_BYTECODE && IS_FIX(detail)",
)


def source_gate(parts: dict[str, str] | None = None,
                *, mutations: bool = False) -> dict[str, Any]:
    text = parts or _sources()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    require(contract["schema"] ==
            "lisp65.c2.vm-badopcode-detail-retirement-contract.v1"
            and contract["product_contract"]["badopcode_detail"] == "NIL-only"
            and contract["product_contract"]["dirmiss_detail"] ==
                ["NIL", "SYMI", "BCODE"],
            "BADOPCODE retirement contract drift")
    combined = "\n".join(text.values())
    for token in RETIRED:
        require(token not in combined, f"retired BADOPCODE surface survived: {token}")

    install = function_body(text["runtime"], "obj c2_product_install(")
    eval_init = function_body(text["eval"], "void eval_init(void)")
    run = function_body(text["vm"], "obj vm_run_inner(")
    terminal = function_body(text["eval"], "void vm_check_status(")
    require("c2_install_phase_mark(" not in install
            and "install_failed:" not in install
            and install.count("C2_INSTALL_TRACE_ENTER_INNER();") == 1
            and install.count("if (vm_status != VM_OK) return NIL;") == 3
            and install.count("vm_status = VM_BADOPCODE; return NIL;") == 7
            and "if (vm_status != VM_OK) return result;" not in install
            and install.count("return result;") == 1,
            "install status-only failures or inner-status precedence drift")
    vm_init = function_body(text["vm"], "void vm_init(void)")
    require(text["eval"].count("obj lisp_t;") == 1
            and "static obj lisp_t;" not in text["eval"]
            and text["eval_h"].count("extern obj lisp_t;") == 1
            and "#ifdef LISP65_C2_PRODUCT_CUT\n#define vm_t lisp_t\n#else"
                in text["vm"]
            and vm_init.count('vm_t = intern("t");') == 1
            and eval_init.count("t = lisp_t;") == 1
            and eval_init.count("t = intern(BOOTNAME(t));") == 1
            and "never derive \"t\" twice" in eval_init,
            "canonical lisp_t declaration or initialization drift")
    require(install.count("definition_name == lisp_t") == 1
            and "c2_facade_intern(\"t\")" not in install
            and "definition_name == NIL" not in install
            and "definition_name == vm_t" not in install,
            "C2 installer does not consume the sole canonical t identity")
    require("#define BADOPCODE_DETAIL" not in run
            and "badopcode_detail:" not in run
            and "detail_complete:" not in run
            and run.count("vm_status = VM_BADOPCODE; goto done;") >= 8,
            "VM hot path retained typed BADOPCODE materialisation")
    flags = text["vm_h"][text["vm_h"].index(
        "#define LISP65_V2_CODE_FLAGS_CHECK"):]
    require("vm_status = VM_BADOPCODE; goto done;" in flags,
            "v2 flag failure is not status-only")
    require(terminal.count(
                "code == LISP65_ERR_VM_UNDEFINED_FUNCTION") == 2
            and "IS_SYMI(detail)" in terminal
            and "IS_BCODE(detail)" in terminal
            and terminal.count("lisp_abort_detail(code, detail);") == 1
            and "code == LISP65_ERR_C2_NESTING_DEPTH" not in terminal,
            "DIRMISS user-facing detail seam drift")
    require(text["vm"].count("obj vm_dirmiss_detail(obj detail) {") == 1,
            "one DIRMISS detail constructor absent")
    require("BCODE for VM_DIRMISS" in text["overlay_h"]
            and "FIXNUM for VM_BADOPCODE" not in text["overlay_h"]
            and "l65e_emit_bcode_ordinal(context->detail);" in
                text["overlay_c"],
            "closed L65E detail union drift")
    require(".globl\tl65e_emit_bcode_ordinal" in text["overlay_s"]
            and ".size\tl65e_emit_bcode_ordinal," in text["overlay_s"]
            and "ldy\t#$23" in text["overlay_s"]
            and "cpx\t#43" not in text["overlay_s"],
            "target renderer retained BADOPCODE Fixnum domain")

    rejected: dict[str, str] = {}
    if mutations:
        trials: dict[str, dict[str, str]] = {}

        def inject(name: str, owner: str, needle: str, addition: str) -> None:
            require(needle in text[owner], f"mutation anchor absent: {name}")
            trial = dict(text)
            trial[owner] = trial[owner].replace(needle, needle + addition, 1)
            trials[name] = trial

        inject("restore-constructor", "vm", "obj vm_dirmiss_detail(obj detail) {",
               "\nobj vm_badopcode_detail(int coordinate);\n")
        inject("restore-terminal-fixnum", "eval", "else\n            lisp_abort_code(code);",
               "\n/* code == LISP65_ERR_VM_BAD_BYTECODE && IS_FIX(detail) */")
        inject("restore-renderer-leaf", "overlay_s",
               ".globl\tl65e_emit_bcode_ordinal",
               "\n.globl\tl65e_emit_fixnum_coordinate")
        inject("restore-install-stage", "runtime", "obj c2_product_install(",
               "\n/* VM_BADDETAIL_INSTALL_TX_BEGIN */")
        trial = dict(text)
        trial["runtime"] = trial["runtime"].replace(
            "if (vm_status != VM_OK) return NIL;",
            "if (vm_status != VM_OK) return result;", 1)
        trials["restore-nonauthoritative-error-result"] = trial
        trial = dict(text)
        trial["runtime"] = trial["runtime"].replace(
            "if (vm_status != VM_OK) return NIL;",
            "vm_status = VM_BADOPCODE;", 1)
        trials["overwrite-inner-status"] = trial
        trial = dict(text)
        trial["runtime"] = trial["runtime"].replace(
            "definition_name == lisp_t",
            "definition_name == c2_facade_intern(\"t\")", 1)
        trials["restore-private-t-interning"] = trial
        trial = dict(text)
        trial["runtime"] = trial["runtime"].replace(
            "definition_name == lisp_t", "definition_name == NIL", 1)
        trials["replace-canonical-t-with-NIL"] = trial
        trial = dict(text)
        trial["eval"] = trial["eval"].replace(
            "\n    t = lisp_t;\n#else",
            "\n    t = NIL;\n#else",
            1)
        trials["remove-canonical-t-consumption"] = trial
        trial = dict(text)
        trial["eval"] = trial["eval"].replace(
            "obj lisp_t;", "static obj lisp_t;", 1)
        trials["restore-private-static-t-cache"] = trial
        trial = dict(text)
        trial["vm"] = trial["vm"].replace(
            "#define vm_t lisp_t", "static obj vm_t = NIL;", 1)
        trials["restore-product-private-vm-t-cache"] = trial
        trial = dict(text)
        trial["eval"] = trial["eval"].replace(
            "&& IS_BCODE(detail)", "&& 0", 1)
        trials["drop-dirmiss-bcode"] = trial
        trial = dict(text)
        trial["eval"] = trial["eval"].replace(
            "&& IS_SYMI(detail)", "&& 0", 1)
        trials["drop-dirmiss-symi"] = trial
        for name, variant in trials.items():
            try:
                source_gate(variant, mutations=False)
            except (GateError, KeyError, ValueError):
                rejected[name] = "rejected"
            else:
                raise GateError(f"retirement mutation accepted: {name}")
    return {
        "status": "passed-BADOPCODE-detail-retired-DIRMISS-preserved",
        "badopcode": {"status": "VM_BADOPCODE", "detail": "NIL-only"},
        "dirmiss": {"status": "VM_DIRMISS",
                    "detail_domains": ["NIL", "SYMI", "BCODE"]},
        "E5": {"status": "LISP65_ERR_C2_NESTING_DEPTH",
               "detail_domain": "exact Fixnum 5",
               "authority": "cold terminal detail seam; separate approved matrix addendum"},
        "inner_status_precedence_edges": 3,
        "error_result_policy": "NIL; non-OK status is sole authority",
        "cold_install_provenance": "slot-plus-inner scratch only; not renderer detail",
        "canonical_t": {
            "authority": "vm_init publishes eval_init:lisp_t",
            "installer_consumers": 1,
            "private_intern_edges": 0,
            "new_storage_bytes": 0},
        "mutations_rejected": rejected,
    }


def semantic_fixture() -> dict[str, Any]:
    return {
        "status": "passed-status-only-BADOPCODE-model",
        "badopcode": {"detail": 0, "suffix": "none"},
        "dirmiss_examples": {"symbol": "missing", "ordinal": "#fff"},
        "resident_diagnostic_bytes": 0,
    }


def linked_gate(elf: Path, llvm_readobj: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=llvm_readobj)
    symbols = {row.name: row for row in truth.symbols}
    for name in ("vm_badopcode_detail", "l65e_emit_fixnum_coordinate"):
        require(name not in symbols, f"retired linked symbol survived: {name}")
    for name in ("vm_dirmiss_detail", "vm_check_status",
                 "lisp65_error_overlay_entry", "l65e_emit_bcode_ordinal",
                 "c2_product_install"):
        require(name in symbols and symbols[name].symbol_type == "Function",
                f"required linked DIRMISS citizen absent: {name}")
    entry = symbols["lisp65_error_overlay_entry"]
    ordinal = symbols["l65e_emit_bcode_ordinal"]
    table = symbols["l65e_table"]
    section = truth.section(".lisp65_rt_l65e")
    expected = json.loads(CONTRACT.read_text(encoding="utf-8"))[
        "renderer"]["l65e_expected_shape"]
    require((entry.bytes, ordinal.bytes, table.bytes, section.bytes) ==
                (expected["entry_bytes"],
                 expected["bcode_ordinal_leaf_bytes"],
                 expected["table_bytes"], expected["slice_bytes"]),
            "retired L65E shape/capacity drift")
    retired_targets = sorted({row.target for row in truth.relocations
                              if row.target in RETIRED})
    require(not retired_targets, "relocation targets retired BADOPCODE surface")
    canonical = truth.symbol("lisp_t")
    installer = truth.symbol("c2_product_install")
    installer_relocs = [
        row for row in truth.relocations
        if row.source_section_index == installer.section_index
        and installer.value <= row.offset < installer.value + installer.bytes]
    # WPLTO may internalize lisp_t and emit the canonical section-symbol plus
    # addend rather than a relocation that retains the source-level name.
    # Resolve the structured target identity; rendered symbol spelling is not
    # an invariant (the same section/addend rule used by the other ELF gates).
    canonical_refs = []
    for row in installer_relocs:
        identity = truth.relocation_target_identity(row)
        if (identity["section"] == canonical.section
                and canonical.value <= identity["resolved_value"]
                < canonical.value + canonical.bytes):
            canonical_refs.append(row)
    private_refs = [row for row in installer_relocs
                    if row.target == "c2_facade_intern"]
    require(canonical.bytes == 2 and canonical.symbol_type == "Object"
            and canonical.section not in ("Absolute", "Undefined")
            and {truth.relocation_target_identity(row)["resolved_value"]
                 for row in canonical_refs} ==
                {canonical.value, canonical.value + 1}
            and not private_refs,
            "linked installer retained private t derivation or lost lisp_t")
    return {
        "status": "passed-linked-BADOPCODE-retirement-DIRMISS-preserved",
        "l65e": {"entry_bytes": entry.bytes,
                 "ordinal_leaf_bytes": ordinal.bytes,
                 "table_bytes": table.bytes,
                 "slice_bytes": section.bytes,
                 "slice_headroom_bytes":
                     expected["slice_cap_bytes"] - section.bytes},
        "retired_symbols": ["vm_badopcode_detail",
                            "l65e_emit_fixnum_coordinate"],
        "dirmiss_constructor": {
            "address": symbols["vm_dirmiss_detail"].value,
            "bytes": symbols["vm_dirmiss_detail"].bytes},
        "canonical_t": {
            "symbol": "lisp_t", "address": canonical.value,
            "bytes": canonical.bytes, "section": canonical.section,
            "installer_relocations": len(canonical_refs),
            "installer_resolved_bytes": sorted(
                truth.relocation_target_identity(row)["resolved_value"]
                - canonical.value for row in canonical_refs),
            "private_facade_intern_relocations": len(private_refs)},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check-source", "check-elf"))
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--llvm-readobj", type=Path,
                        default=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    args = parser.parse_args()
    try:
        if args.command == "check-source":
            value = {"source": source_gate(mutations=True),
                     "semantics": semantic_fixture()}
        else:
            require(args.elf is not None, "--elf is required")
            value = linked_gate(args.elf, args.llvm_readobj)
    except (GateError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"c2-vm-badopcode-detail-retirement: FAIL: {error}",
              file=sys.stderr)
        return 1
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
