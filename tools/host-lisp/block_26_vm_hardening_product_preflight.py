#!/usr/bin/env python3
"""Arm Block 2.6 Card 3 A3-A6 with executed source-bound mutations."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import block_26_f011_map_abort_repair_product_card as CARD2  # noqa: E402
import consolidated_consumption_authority as CONSUMPTION  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.6-correctness-and-build-integrity-work-plan.md"
AUTHORIZATION = "552dd3ad"
PLAN_HEADER = "## Reviewer authorization — card 3 A3–A6 product card — 2026-09-03"
PREAMBLE = ARCH / "block-2.6-card3-vm-hardening-preamble.json"
RECEIPT = ARCH / "block-2.6-card3-vm-hardening-product-preflight.json"
BUILD = ROOT / "build/2.6/card3-vm-hardening-product-preflight"
GC_MAIN = ROOT / "scripts/block-26-card3-gc-root-main.c"
VM_MAIN = ROOT / "scripts/block-26-card3-vm-hardening-main.c"
MEM = ROOT / "src/mem.c"
VM = ROOT / "src/vm.c"
PUBLIC_PLANE = ROOT / "config/c2-v200-public-plane/static-plane"
V201_PACKAGE = ROOT / "build/release-v2.0.1/v2.0.1-package-preparation-receipt.json"
FORMAT = "lisp65-block-2.6-card3-vm-hardening-product-preflight-v1"


class PreflightError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PreflightError(message)


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


def git_section() -> dict[str, Any]:
    relative = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{relative}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = raw.decode()
    require(text.count(PLAN_HEADER) == 1, "Card-3 authorization section drift")
    section = PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    folded = " ".join(section.lower().replace("`", "").replace("*", "").split())
    for token in ("one wplto and one product link", "gc-time wall",
                  "mark completeness", "slot operand", "pop underflow",
                  "%disk-poke", "zero contacts"):
        require(token in folded, f"Card-3 authorization token absent: {token}")
    payload = section.encode()
    return {"commit": AUTHORIZATION, "path": relative, "section": PLAN_HEADER,
            "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


def product_world() -> dict[str, Any]:
    return CONSUMPTION.derive_product_world_identity(
        selected_plane=CARD2.PLANE, published_plane=PUBLIC_PLANE,
        build_authority_path=CONSUMPTION.PUBLIC_BUILD_AUTHORITY,
        docs_only_receipt_path=V201_PACKAGE)


def run(command: list[str], *, expect_success: bool) -> dict[str, Any]:
    result = subprocess.run(command, cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env={**os.environ, "ASAN_OPTIONS": "detect_leaks=0:halt_on_error=1",
             "UBSAN_OPTIONS": "halt_on_error=1", "PYTHONDONTWRITEBYTECODE": "1"})
    if expect_success:
        require(result.returncode == 0, "command red:\n" + result.stdout)
    else:
        require(result.returncode != 0, "sharp mutation survived execution")
    return {"returncode": result.returncode,
            "stdout_tail": " ".join(result.stdout.split()[-24:])}


def gc_compile(source: Path, output: Path, extra: tuple[str, ...] = ()) -> None:
    command = [os.environ.get("HOSTCC", "cc"), "-std=c99", "-Wall", "-Wextra",
        "-Werror", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
        "-DLISP65_C2_PRODUCT_CUT", "-DHEAP_CELLS=1024", "-DGC_ROOTS=128",
        "-DMAX_SYM=32", "-DNAMEPOOL=256", *extra, "-Isrc", str(GC_MAIN),
        str(source), "src/symbol.c", "src/interrupt.c", "-o", str(output)]
    run(command, expect_success=True)


VM_DEFS = (
    "-DLISP65_VM", "-DLISP65_DIALECT_V2", "-DLISP65_V2_WORKBENCH_SERVICES",
    "-DLISP65_V2_SERVICE_REGISTRY_CLOSED", "-DLISP65_V2_CARRIER_CUT",
    "-DLISP65_VM_NATIVE_APPLY", "-DLISP65_V2_NATIVE_CAPABILITIES",
    "-DLISP65_V2_NATIVE_STRING_CODECS", "-DLISP65_STRING_ARENA",
    "-DLISP65_EXT_HEAP", "-DEXT_CELLS=1024", "-DHEAP_CELLS=4096",
    "-DGC_ROOTS=128", "-DSTR_ARENA_SIZE=4096", "-DMAX_SYM=512",
    "-DNAMEPOOL=8192", "-DVM_DIR_MAX=128", "-DVM_CODEBUF=64",
    "-DLISP65_COMPILE_STRING", "-DLISP65_LCC_INSTALL",
    "-DLISP65_MACROEXPAND_PRIM", "-DLISP65_TREEWALK_STRIP",
    "-DMEGA65_F011_LOAD", "-DMEGA65_F011_WRITE", "-DLISP65_NUMERIC_ERRORS",
)


def vm_compile(source: Path, output: Path) -> None:
    command = [os.environ.get("HOSTCC", "cc"), "-std=gnu99", "-Wall", "-Wextra",
        "-Werror", "-Wno-unused-function", "-fsanitize=address,undefined",
        "-fno-omit-frame-pointer", *VM_DEFS, "-Isrc", str(VM_MAIN),
        "src/eval.c", "src/lcc_install_overlay.c", str(source), "src/mem.c",
        "src/symbol.c", "src/reader.c", "src/printer.c", "src/interrupt.c",
        "src/screen.c", "-o", str(output)]
    run(command, expect_success=True)


def replace_once(source: str, old: str, new: str, label: str) -> str:
    require(source.count(old) == 1, f"{label} mutation target drift")
    return source.replace(old, new, 1)


def vm_mutants(source: str) -> dict[str, str]:
    slot = source
    for line in (
        "        case OP_PUSHARGN: { uint8_t n = RD8(); if (!SLOT_OK(n)) { vm_status = VM_BADOPCODE; goto done; } PUSH(SLOT(n)); break; }",
        "        case OP_LOADL:    { uint8_t n = RD8(); if (!SLOT_OK(n)) { vm_status = VM_BADOPCODE; goto done; } PUSH(SLOT(n)); break; }",
        "        case OP_STOREL:   { uint8_t n = RD8(); if (!SLOT_OK(n)) { vm_status = VM_BADOPCODE; goto done; } a = POP(); SLOT(n) = a; break; }",
    ):
        slot = replace_once(slot, line, line.replace(
            "if (!SLOT_OK(n)) { vm_status = VM_BADOPCODE; goto done; } ", ""),
            "slot guard removal")

    new_entry = "if ((uint16_t)(base + vm_frame_slots(nargs_actual, nargs, nlocals, flags)) > GC_ROOTS) { vm_status = VM_STACKOVER; goto done; }"
    new_tail = "if ((uint16_t)(base + vm_frame_slots(n, nargs, nlocals, flags)) > GC_ROOTS) { vm_status = VM_STACKOVER; goto done; }"
    old = "if ((uint16_t)(base + nargs + nlocals + 1) >= GC_ROOTS) { vm_status = VM_STACKOVER; goto done; }"
    rest = replace_once(source, new_entry, old, "entry REST guard removal")
    rest = replace_once(rest, new_tail, old, "tail REST guard removal")

    pop = replace_once(source,
        "#define POP()    ({ obj pop__; if (gc_rootsp <= vb) { vm_status = VM_BADOPCODE; goto done; } pop__ = gc_rootstack[--gc_rootsp]; pop__; })",
        "#define POP()    (gc_rootsp > vb ? gc_rootstack[--gc_rootsp] : (vm_status = VM_BADOPCODE, NIL))",
        "POP fail-stop removal")
    disk_block = (
        "    case 21:  /* %disk-poke */\n"
        "        if (n != 2 || !IS_FIX(a[0]) || !IS_FIX(a[1])) { vm_status = VM_TYPEERROR; return NIL; }\n"
        "        io_disk_scratch_poke")
    old_disk_block = "    case 21:  /* %disk-poke */\n        io_disk_scratch_poke"
    pop = replace_once(pop, disk_block, old_disk_block,
                       "historical disk-poke domain removal")
    disk = replace_once(source, disk_block, old_disk_block,
                        "disk-poke domain removal")
    return {"slot-bound-removed": slot, "rest-transient-bound-removed": rest,
            "pop-fail-stop-and-disk-domain-removed": pop,
            "disk-poke-domain-removed": disk}


def executed_fixtures(root: Path) -> dict[str, Any]:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    gc_binary = root / "gc-root"
    gc_compile(MEM, gc_binary)
    gc_result = run([str(gc_binary)], expect_success=True)

    omitted = root / "gc-root-omitted"
    gc_compile(MEM, omitted, ("-DLISP65_CARD3_OMIT_PRODUCT_ROOT",))
    omitted_result = run([str(omitted)], expect_success=False)

    vm_binary = root / "vm-hardening"
    vm_compile(VM, vm_binary)
    vm_result = run([str(vm_binary)], expect_success=True)
    source = VM.read_text(encoding="utf-8")
    mutations: dict[str, Any] = {}
    for name, mutant in vm_mutants(source).items():
        mutant_source = root / f"vm-{name}.c"
        mutant_source.write_text(mutant, encoding="utf-8")
        binary = root / f"vm-{name}"
        vm_compile(mutant_source, binary)
        mutations[name] = run([str(binary)], expect_success=False)

    return {
        "gc": {"status": "PASS: REAL FIXPOINT PRESERVES 600-CELL PRODUCT GRAPH",
            "control": gc_result, "root_omission_mutation": omitted_result,
            "mutations_rejected": ["product-root-omitted"]},
        "vm": {"status": "PASS: REAL VM REJECTS ALL FOUR MALFORMED FORMS",
            "control": vm_result, "mutations": mutations,
            "mutations_rejected": list(mutations)},
        "generated_binaries": {"gc": bind(gc_binary), "vm": bind(vm_binary)},
    }


def source_contract() -> dict[str, Any]:
    mem = MEM.read_text(encoding="utf-8")
    vm = VM.read_text(encoding="utf-8")
    checks = {
        "bounded-mark-worklist-absent": "MARKSTACK" not in mem and "markstack[" not in mem,
        "product-root-enters-flat-mark": "void gc_mark(obj o) { (void)gc_mark1(o); }" in mem,
        "slot-predicate-bound": vm.count("if (!SLOT_OK(n))") == 3,
        "both-frame-guards-use-transient-bound": vm.count("base + vm_frame_slots(") == 2,
        "pop-is-fail-stop": "if (gc_rootsp <= vb) { vm_status = VM_BADOPCODE; goto done; }" in vm,
        "disk-poke-has-exact-domain": (
            "case 21:  /* %disk-poke */\n        if (n != 2 || !IS_FIX(a[0]) || !IS_FIX(a[1]))" in vm),
    }
    require(all(checks.values()), "A3-A6 source contract incomplete")
    return {"status": "PASS: A3-A6 SOURCE CONTRACT BOUND", "checks": checks,
            "mem": bind(MEM), "vm": bind(VM), "gc_fixture": bind(GC_MAIN),
            "vm_fixture": bind(VM_MAIN)}


def derive(root: Path) -> dict[str, Any]:
    preamble = load(PREAMBLE)
    world = product_world()
    require(preamble["cold_hardening"]["decision"] == "open-a3-a6-product-card"
            and preamble["dispatch"]["decision"] == "separate-decision-after-cold-final-link",
            "Card-3 split authority drift")
    require(world["selected_plane_world"]["product_build_id"] == "0x4a1713ab"
            and world["selected_plane_world"]["banner"] == "WORKBENCH 2.0.0",
            "Card-3 predecessor world drift")
    fixtures = executed_fixtures(root)
    return {"format": FORMAT, "recorded_on": "2026-09-03",
        "status": "PASS: BLOCK 2.6 CARD 3 A3-A6 ARMED 0/1",
        "authority": {"commission": git_section(), "preamble": bind(PREAMBLE),
            "card2_r3": bind(CARD2.RECEIPT),
            "right": "one product card, one WPLTO and one product link"},
        "product_world_identity": world, "source_contract": source_contract(),
        "executed_fixtures": fixtures,
        "final_obligations": ["all bounded owners clear their final-link floors",
            "full Card-2-r3 difference attribution has zero unexplained members",
            "Scope and Acceptance run read-only over one frozen pair",
            "packed DWX rows pass", "same-choreography GC cycles do not rise",
            "zero physical device contacts"],
        "attempt_accounting": {"product_cards": 0, "WPLTO_runs": 0,
            "product_links": 0, "device_contacts": 0}}


def validate(value: dict[str, Any]) -> None:
    require(value["status"] == "PASS: BLOCK 2.6 CARD 3 A3-A6 ARMED 0/1"
            and value["authority"]["commission"] == git_section()
            and value["source_contract"]["status"] ==
                "PASS: A3-A6 SOURCE CONTRACT BOUND"
            and all(value["source_contract"]["checks"].values())
            and value["executed_fixtures"]["gc"]["mutations_rejected"] == [
                "product-root-omitted"]
            and value["executed_fixtures"]["vm"]["mutations_rejected"] == [
                "slot-bound-removed", "rest-transient-bound-removed",
                "pop-fail-stop-and-disk-domain-removed", "disk-poke-domain-removed"]
            and value["attempt_accounting"] == {"product_cards": 0,
                "WPLTO_runs": 0, "product_links": 0, "device_contacts": 0},
            "Card-3 product preflight receipt drift")


def selftest(value: dict[str, Any]) -> None:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "root-omission-accepted": lambda row: row["executed_fixtures"]["gc"].update(
            {"mutations_rejected": []}),
        "rest-overflow-accepted": lambda row: row["executed_fixtures"]["vm"].update(
            {"mutations_rejected": ["slot-bound-removed"]}),
        "build-spent": lambda row: row["attempt_accounting"].update({"WPLTO_runs": 1}),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except (PreflightError, KeyError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "Card-3 preflight mutation survived")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "write":
        require(not RECEIPT.exists(), "Card-3 product preflight is one-shot")
        value = derive(BUILD)
        RECEIPT.write_bytes(canonical(value)); verb = "WROTE"
    else:
        value = load(RECEIPT); validate(value)
        if args.action == "check":
            rerun = derive(BUILD / "recheck")
            # Generated host binaries are compiler/path artifacts; semantic rows
            # and source bindings, not their identities, are the durable claim.
            require(rerun["source_contract"]["checks"] ==
                        value["source_contract"]["checks"]
                    and rerun["product_world_identity"] == value["product_world_identity"]
                    and rerun["executed_fixtures"]["gc"]["mutations_rejected"] ==
                        value["executed_fixtures"]["gc"]["mutations_rejected"]
                    and rerun["executed_fixtures"]["vm"]["mutations_rejected"] ==
                        value["executed_fixtures"]["vm"]["mutations_rejected"],
                    "Card-3 executed preflight changed")
        else:
            selftest(value)
        verb = "PASS"
    print(f"Block 2.6 Card 3 A3-A6 preflight: {verb} WPLTO=0/1 link=0/1")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PreflightError, RuntimeError, KeyError, ValueError, OSError,
            subprocess.CalledProcessError) as error:
        print(f"Block 2.6 Card 3 A3-A6 preflight: FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
