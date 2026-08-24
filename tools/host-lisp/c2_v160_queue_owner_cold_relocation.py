#!/usr/bin/env python3
"""Gate the cold transaction-guard relocation used by queue ownership."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path: sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402

RUNTIME = ROOT / "src/vm_runtime_overlay.c"
FACADE = ROOT / "src/optional/c2_mapped_far_service_liveness_v4.s"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
FAR_CAPACITY = 1499
FACADE_BYTES = 98
STATUS = "PASS: COLD TRANSACTION GUARD RELOCATED WITH DERIVED CAPACITY"


class GateError(RuntimeError): pass


def require(value: bool, message: str) -> None:
    if not value: raise GateError(message)


def source_gate(runtime: str | None = None,
                facade: str | None = None) -> dict[str, Any]:
    c = RUNTIME.read_text(encoding="utf-8") if runtime is None else runtime
    asm = FACADE.read_text(encoding="utf-8") if facade is None else facade
    require("LISP65_C2_MAPPED_FAR_FN uint8_t "
            "rtov_transaction_context_if_ready_far(" in c,
            "transaction guard body is not mapped-Far-owned")
    require(c.count("rtov_transaction_context_if_ready(&verify") == 2,
            "transaction guard does not retain exactly two source callers")
    body = c.split("rtov_transaction_context_if_ready_far(", 1)[1].split(
        "\n}", 1)[0]
    require(body.count("rtov_transaction_context(verify, publish)") == 1
            and "RTOV_TRANSACTION_ACTIVE()" in body
            and "RTOV_ISLAND_READY" in body,
            "relocated body changed transaction-guard semantics")
    stub = asm.split("rtov_transaction_context_if_ready:", 1)[1].split(
        ".size rtov_transaction_context_if_ready", 1)[0]
    expected = ("jsr c2_mapped_far_enter", "jsr rtov_transaction_context_if_ready_far",
                "jmp c2_mapped_far_leave")
    require(all(stub.count(token) == 1 for token in expected),
            "ordinary stub is not exact enter/body/leave")
    require(".section .text.rtov_transaction_context_if_ready" in asm,
            "transaction stub escaped ordinary text ownership")
    return {"status": STATUS, "source_callers": 2,
            "body_owner": ".lisp65_c2_mapped_far_service",
            "stub_owner": ".text.rtov_transaction_context_if_ready",
            "stub_shape": list(expected)}


def _function_lines(disassembly: str, name: str) -> str:
    match = re.search(rf"^[0-9a-f]+ <{re.escape(name)}>:\n(.*?)(?=^[0-9a-f]+ <|\Z)",
                      disassembly, re.MULTILINE | re.DOTALL)
    require(match is not None, f"linked function absent from disassembly: {name}")
    return match.group(1)


def linked_gate(elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ)
    text = truth.section(".text")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    far = truth.section(".lisp65_c2_mapped_far_service")
    stub = truth.symbol("rtov_transaction_context_if_ready")
    body = truth.symbol("rtov_transaction_context_if_ready_far")
    island = truth.symbol("rtov_transaction_context")
    require(stub.section == ".text" and stub.bytes == 9,
            "linked transaction stub is not exact 9-byte ordinary entry")
    require(body.section == ".lisp65_c2_mapped_far_service",
            "linked transaction body escaped mapped Far service")
    require(island.value == 0x1DCE and not (0x6000 <= island.value < 0x8000),
            "transaction callee is not disjoint from mapped CPU block 3")
    ordinary_free = facade.address - (text.address + text.bytes)
    far_free = FAR_CAPACITY - far.bytes
    require(facade.bytes == FACADE_BYTES and ordinary_free >= 6
            and far.bytes <= FAR_CAPACITY and far_free >= 15,
            "linked relocation violates facade or priced capacity floors")

    disassembly = subprocess.run([str(OBJDUMP), "-d", str(elf)], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.lower()
    calls = re.findall(rf"^\s*([0-9a-f]+):\s+(?:[0-9a-f]{{2}}\s+)+"
                       rf"jsr\s+\${stub.value:x}\b", disassembly, re.MULTILINE)
    require(len(calls) == 2, "linked transaction stub caller count drift")
    stub_lines = _function_lines(disassembly, "rtov_transaction_context_if_ready")
    body_lines = _function_lines(disassembly, "rtov_transaction_context_if_ready_far")
    require(re.search(rf"jsr\s+\${truth.symbol('c2_mapped_far_enter').value:x}\b", stub_lines)
            and re.search(rf"jsr\s+\${body.value:x}\b", stub_lines)
            and re.search(rf"jmp\s+\${truth.symbol('c2_mapped_far_leave').value:x}\b", stub_lines),
            "linked stub lost enter/body/leave edges")
    direct_body_calls = re.findall(r"\bjsr\s+\$([0-9a-f]+)\b", body_lines)
    require(direct_body_calls == [f"{island.value:x}"],
            "mapped body acquired an unpriced or hidden callee")
    return {"status": STATUS,
            "ordinary": {"text_end_exclusive": f"0x{text.address + text.bytes:04x}",
                         "facade_start": f"0x{facade.address:04x}",
                         "free_bytes": ordinary_free,
                         "stub_address": f"0x{stub.value:04x}",
                         "stub_bytes": stub.bytes},
            "far": {"body_address": f"0x{body.value:04x}",
                    "body_bytes": body.bytes, "service_bytes": far.bytes,
                    "capacity_bytes": FAR_CAPACITY, "free_bytes": far_free},
            "facade_bytes": facade.bytes,
            "linked_callers": [f"0x{int(value, 16):04x}" for value in calls],
            "callee": {"name": island.name, "address": f"0x{island.value:04x}",
                       "outside_mapped_block3": True}}


def selftest() -> None:
    source = RUNTIME.read_text(encoding="utf-8")
    facade = FACADE.read_text(encoding="utf-8")
    source_gate(source, facade)
    mutations = {
        "body-owner-removed": (source.replace("LISP65_C2_MAPPED_FAR_FN uint8_t", "uint8_t", 1), facade),
        "caller-removed": (source.replace("rtov_transaction_context_if_ready(&verify, 0u)", "0", 1), facade),
        "stub-enter-removed": (source, facade.replace(
            "rtov_transaction_context_if_ready:\n\tjsr c2_mapped_far_enter",
            "rtov_transaction_context_if_ready:\n\tnop", 1)),
        "stub-body-removed": (source, facade.replace(
            "\tjsr rtov_transaction_context_if_ready_far", "\tnop", 1)),
        "stub-leave-removed": (source, facade.replace(
            "\tjsr rtov_transaction_context_if_ready_far\n\tjmp c2_mapped_far_leave",
            "\tjsr rtov_transaction_context_if_ready_far\n\trts", 1)),
    }
    for name, (c, asm) in mutations.items():
        try: source_gate(c, asm)
        except GateError: pass
        else: raise GateError(f"source mutation survived: {name}")
    print("v1.6 queue-owner cold relocation: SELFTEST PASS mutations=5")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else "source"
    if action == "selftest": selftest(); return 0
    if action == "source":
        print(json.dumps(source_gate(), sort_keys=True)); return 0
    if action == "linked":
        require(len(sys.argv) == 3, "linked requires ELF")
        print(json.dumps(linked_gate(Path(sys.argv[2])), sort_keys=True)); return 0
    raise GateError("usage: [selftest|source|linked ELF]")


if __name__ == "__main__":
    try: raise SystemExit(main())
    except (GateError, subprocess.CalledProcessError) as error:
        print(f"v1.6 queue-owner cold relocation: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
