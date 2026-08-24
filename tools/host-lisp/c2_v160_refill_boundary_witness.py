#!/usr/bin/env python3
"""Gate the temporary v1.6 refill-boundary witness in source and final ELF."""

from __future__ import annotations

from copy import deepcopy
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

import c2_v160_display_ownership as DISPLAY  # noqa: E402
import c2_crc_codegen_gate as DISASM  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PRICING = ARCH / "c2.3-v1.6-refill-boundary-witness-pricing.json"
ASM = ROOT / "src/optional/c2_refill_boundary_witness.s"
VM = ROOT / "src/vm.c"
RUNTIME = ROOT / "src/vm_runtime_overlay.c"
EDITOR = ROOT / "lib/stdlib-read-line.lisp"
EDITOR_EVIDENCE_COMMIT = "af920418"
CLANG = ROOT / "tools/llvm-mos/bin/mos-clang"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
STATUS = "PASS: REFILL WITNESS OBSERVES EXACT PAYLOAD WITH BOUND ORIGIN"


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def sealed_editor() -> tuple[str, dict[str, Any]]:
    """Read the temporary trace origin from its sealed diagnostic world."""
    name = EDITOR.relative_to(ROOT).as_posix()
    commit = subprocess.run(
        ["git", "rev-parse", f"{EDITOR_EVIDENCE_COMMIT}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE
    ).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return raw.decode("utf-8"), {
        "authority": "sealed-diagnostic-world",
        "commit": commit, "path": name, "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _assembled_sizes() -> dict[str, int]:
    with tempfile.TemporaryDirectory(prefix="c2-refill-witness-") as raw:
        obj = Path(raw) / "witness.o"
        run = subprocess.run(
            [str(CLANG), "-c", "-mcpu=mos45gs02", str(ASM), "-o", str(obj)],
            cwd=ROOT, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)
        require(run.returncode == 0, "witness assembly red:\n" + run.stdout)
        truth = ElfTruth.read(obj, llvm_readobj=READOBJ)
        names = ("disk_chain_to_scratch", "c2_refill_trace_read") \
            if any(row.name == "disk_chain_to_scratch"
                   for row in truth.symbols) else \
            ("vm_runtime_overlay_install_island", "c2_refill_trace_read")
        return {name: truth.symbol(name).bytes for name in names}


def source_gate(editor: str | None = None, asm: str | None = None,
                vm: str | None = None, runtime: str | None = None
                ) -> dict[str, Any]:
    sealed_text, sealed_binding = sealed_editor()
    editor_text = sealed_text if editor is None else editor
    asm_text = ASM.read_text(encoding="utf-8") if asm is None else asm
    vm_text = VM.read_text(encoding="utf-8") if vm is None else vm
    runtime_text = (RUNTIME.read_text(encoding="utf-8")
                    if runtime is None else runtime)
    reset = editor_text.split("(if (= row -2)", 1)[1].split(
        "(write-char 19)", 1)[0]
    for token in ("(poke 188 138 255)", "(poke 188 135 0)",
                  "(poke 188 136 0)", "(poke 188 137 0)",
                  "(poke 188 139 165)"):
        require(reset.count(token) == 1, f"trace-origin step absent: {token}")
    require(reset.index("(poke 188 138 255)")
            < reset.index("(poke 188 135 0)")
            < reset.index("(poke 188 139 165)"),
            "trace origin is not close/reset/publish ordered")
    for token in ("stz $bd00,x", "inc $bc88", "inc $bc89",
                  "jsr c2_product_entry_read", "cpy #$15",
                  "sta $bd00,x"):
        require(token in asm_text, f"trace assembly contract absent: {token}")
    require(asm_text.index("stz $bd00,x") < asm_text.index("sta $bd00,x")
            and asm_text.count("jsr c2_product_entry_read") == 1
            and asm_text.count("jmp c2_product_entry_read") == 1,
            "trace commit/call shape drift")
    require("return c2_refill_trace_read(object, relative, destination, length);"
            in vm_text and
            ("vm_runtime_overlay_install_island_far(void)" in runtime_text or
             "vm_runtime_overlay_status vm_runtime_overlay_install_island(void)"
             in runtime_text), "witness source routing/relocation drift")
    sizes = _assembled_sizes() if asm is None else {
        "disk_chain_to_scratch": 12,
        "c2_refill_trace_read": 205}
    require(sizes in ({"vm_runtime_overlay_install_island": 9,
                       "c2_refill_trace_read": 205},
                      {"disk_chain_to_scratch": 12,
                       "c2_refill_trace_read": 205}),
            f"emitted witness source price drift: {sizes}")
    return {"status": STATUS, "emitted": sizes,
        "origin": {"close": "$BC8A=$FF", "next": "$BC87=0",
            "sequence": "$BC88=0", "wrap": "$BC89=0",
            "publish_last": "$BC8B=$A5"},
        "slots": {"starts": ["$BD00", "$BD22"], "bytes_each": 34,
            "commit_last": "$A5", "payload_bytes": 21},
        "inputs": {"pricing": bind(PRICING), "assembly": bind(ASM),
            "vm": bind(VM), "runtime": bind(RUNTIME),
            "editor": sealed_binding}}


def source_mutations() -> list[str]:
    editor, _binding = sealed_editor()
    asm = ASM.read_text(encoding="utf-8")
    cases = {
        "origin-not-published": (editor.replace(
            "(poke 188 139 165)", "(poke 188 139 0)", 1), asm),
        "slot-not-invalidated": (editor, asm.replace(
            "\tstz $bd00,x", "\tnop", 1)),
        "commit-before-payload": (editor, asm.replace(
            "\tsta $bd00,x\n\tpla", "\tpla", 1)),
    }
    rejected = []
    for name, (editor_mutant, asm_mutant) in cases.items():
        try:
            source_gate(editor_mutant, asm_mutant)
        except GateError:
            rejected.append(name)
    require(rejected == list(cases), "witness source mutation survived")
    return rejected


def _function(disassembly: str, name: str) -> str:
    match = re.search(rf"^[0-9a-f]+ <{re.escape(name)}>:\n(.*?)(?=^[0-9a-f]+ <|\Z)",
                      disassembly, re.MULTILINE | re.DOTALL)
    require(match is not None, f"linked function absent: {name}")
    return match.group(1)


def _linked_callers(truth: ElfTruth, rows: list[dict[str, Any]],
                    target: int) -> list[dict[str, Any]]:
    functions = [symbol for symbol in truth.symbols
        if symbol.symbol_type == "Function" and symbol.bytes > 0]
    callers = []
    for row in rows:
        if row["opcode"] not in ("jsr", "jmp"):
            continue
        match = re.match(r"^\$([0-9a-f]+)\b", str(row["operand"]))
        if match is None or int(match.group(1), 16) != target:
            continue
        owners = [symbol for symbol in functions
            if symbol.section == row["section"]
            and symbol.value <= int(row["address"])
            < symbol.value + symbol.bytes]
        require(bool(owners), f"linked call has no function owner: {row}")
        owner = min(owners, key=lambda symbol: symbol.bytes)
        callers.append({"address": f"0x{int(row['address']):04x}",
                        "owner": owner.name, "edge": row["opcode"]})
    return callers


def _validate_witness_callers(callers: list[dict[str, Any]]) -> None:
    require(bool(callers), "linked witness has no callers")
    owners = {str(row["owner"]) for row in callers}
    require(owners == {"vm_run_inner"},
            f"linked witness has foreign caller owners: {sorted(owners)}")


def final_gate(elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    text = truth.section(".text")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    service = truth.section(".lisp65_c2_mapped_far_service")
    diagnostic = truth.section(".lisp65_c2_mapped_diagnostic")
    stub = truth.symbol("vm_runtime_overlay_install_island")
    body = truth.symbol("vm_runtime_overlay_install_island_far")
    witness = truth.symbol("c2_refill_trace_read")
    original = truth.symbol("c2_product_entry_read")
    require(stub.section == ".text" and stub.bytes == 9
            and witness.section == ".text" and witness.bytes == 205,
            "ordinary witness/stub linked price drift")
    require(body.section == diagnostic.name and body.bytes == diagnostic.bytes == 211
            and diagnostic.address == 0x7E8D,
            "cold installer escaped diagnostic arena")
    lma_start = truth.symbol("__lisp65_c2_mapped_diagnostic_load_start").value
    lma_end = truth.symbol("__lisp65_c2_mapped_diagnostic_load_end").value
    require(lma_start == 0x2BE8D and lma_end == lma_start + diagnostic.bytes,
            "diagnostic Static-Plane delivery identity drift")
    ordinary_free = facade.address - (text.address + text.bytes)
    require(ordinary_free == 3 and service.bytes == 1484
            and 1499 - service.bytes == 15
            and 371 - diagnostic.bytes == 160,
            "final linked capacity price drift")

    raw_disassembly = subprocess.run(
        [str(OBJDUMP), "-d", "--no-show-raw-insn", str(elf)], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout
    disassembly = raw_disassembly.lower()
    stub_lines = _function(disassembly, stub.name)
    witness_lines = _function(disassembly, witness.name)
    body_lines = _function(disassembly, body.name)
    enter = truth.symbol("c2_mapped_far_enter").value
    leave = truth.symbol("c2_mapped_far_leave").value
    require(re.search(rf"jsr\s+\${enter:x}\b", stub_lines)
            and re.search(rf"jsr\s+\${body.value:x}\b", stub_lines)
            and re.search(rf"jmp\s+\${leave:x}\b", stub_lines),
            "cold installer stub lost enter/body/leave")
    require(len(re.findall(rf"(?:jsr|jmp)\s+\${original.value:x}\b",
                           witness_lines)) == 2
            and "cpy\t#$15" in witness_lines,
            "linked witness lost original-reader or full-payload edges")
    external_calls = {int(value, 16) for value in re.findall(
        r"\bjsr\s+\$([0-9a-f]+)\b", body_lines)}
    expected_callees = {truth.symbol(name).value for name in (
        "vm_runtime_overlay_exec_family", "__memset", "rtov_fail")}
    require(expected_callees <= external_calls
            and all(not 0x6000 <= value < 0x8000 for value in expected_callees),
            "mapped installer acquired hidden or missing callee")

    rows = DISASM.disassembly_rows(raw_disassembly)
    incoming_stub = _linked_callers(truth, rows, stub.value)
    incoming_witness = _linked_callers(truth, rows, witness.value)
    require(len(incoming_stub) == 1
            and {row["owner"] for row in incoming_stub} == {"main"},
            "linked installer has a foreign or missing owner")
    _validate_witness_callers(incoming_witness)

    display = DISPLAY.derive()
    screen_tail = display["artifacts"]["code_object_bytes"]["%rl-screen-tail"]
    require(display["status"] ==
                "PASS: COMFORT DISPLAY HAS ONE OWNER AND DEFINED HANDOFF"
            and display["composed_framebuffer"]["result_tail_blank"] is True
            and screen_tail == 251,
            "composed-image/origin final library gate red")
    return {"status": STATUS,
        "artifact": bind(elf),
        "ordinary": {"stub_bytes": stub.bytes, "witness_bytes": witness.bytes,
            "free_bytes": ordinary_free},
        "mapped_diagnostic": {"address": f"0x{diagnostic.address:04x}",
            "load_address": f"0x{lma_start:08x}", "body_bytes": body.bytes,
            "capacity_bytes": 371, "free_bytes": 371 - diagnostic.bytes},
        "existing_far_service": {"bytes": service.bytes,
            "capacity_bytes": 1499, "free_bytes": 1499 - service.bytes},
        "edges": {"installer_callers": incoming_stub,
            "witness_callers": incoming_witness,
            "witness_owner_set": sorted(
                {str(row["owner"]) for row in incoming_witness}),
            "mapped_callees": [f"0x{value:04x}" for value in sorted(expected_callees)]},
        "trace": {"alias_bytes": 73, "new_resident_bytes": 0,
            "slots": 2, "payload_bytes": 21,
            "decision": ["no committed result", "payload differs",
                         "payload matches with bounded frames"]},
        "composed_image": {"status": display["status"],
            "screen_tail_bytes": screen_tail,
            "result_tail_blank": True},
        "removal_default": True}


def final_mutations(value: dict[str, Any]) -> list[str]:
    cases = {
        "ordinary-overstated": lambda x: x["ordinary"].update(free_bytes=4),
        "diagnostic-overstated": lambda x: x["mapped_diagnostic"].update(free_bytes=161),
        "retain-by-default": lambda x: x.update(removal_default=False),
        "foreign-witness-caller": lambda x: x["edges"]["witness_callers"].append(
            {"address": "0xffff", "owner": "foreign_owner", "edge": "jsr"}),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            _validate_witness_callers(trial["edges"]["witness_callers"])
            require(trial["ordinary"]["free_bytes"] == 3
                    and trial["mapped_diagnostic"]["free_bytes"] == 160
                    and trial["removal_default"] is True,
                    "final claim mutation")
        except GateError:
            rejected.append(name)
    require(rejected == list(cases), "final witness mutation survived")
    # A valid extra call in the same semantic owner must be accepted by the
    # classifier and rejected by the predecessor's exact-one projection.
    candidate = deepcopy(value["edges"]["witness_callers"])
    candidate.append({"address": "0xfffe", "owner": "vm_run_inner",
                      "edge": "jsr"})
    _validate_witness_callers(candidate)
    if len(candidate) != 1:
        rejected.append("single-witness-caller-pin")
    require(rejected[-1] == "single-witness-caller-pin",
            "single witness caller pin survived")
    return rejected


def main(argv: list[str]) -> int:
    require(len(argv) in (2, 3) and argv[1] in ("source", "selftest", "final"),
            "usage: source|selftest|final ELF")
    if argv[1] == "source":
        print(json.dumps(source_gate(), sort_keys=True))
    elif argv[1] == "selftest":
        source_gate(); rejected = source_mutations()
        print(f"v1.6 refill witness: SELFTEST PASS mutations={len(rejected)}")
    else:
        require(len(argv) == 3, "final requires ELF")
        value = final_gate(Path(argv[2])); value["mutations_rejected"] = final_mutations(value)
        print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except (GateError, OSError, ValueError, KeyError,
            subprocess.CalledProcessError) as error:
        print(f"v1.6 refill witness: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
