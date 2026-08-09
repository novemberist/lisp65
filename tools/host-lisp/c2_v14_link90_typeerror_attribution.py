#!/usr/bin/env python3
"""Bind the honest host/ELF limit of the Link-90 VM_TYPEERROR attribution.

The owner commission expected the existing 16-byte target readback to carry
vm_dbg_pc/op/bank/off.  The shipped Runtime Core does not enable either build
switch that creates those symbols.  This probe therefore binds what the
existing evidence really proves and stops before inventing a fault PC.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth, ElfTruthError  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / (
    "c2.3-v1.4-link90-typeerror-host-elf-attribution-first-red.json"
)
ELF = ROOT / "build/post-promotion/v14/sample-fleet-host-link90/parity-toy.runtime.elf"
SHIP_RECEIPT = ROOT / (
    "build/post-promotion/v14/sample-fleet-host-link90/parity-toy.receipt.json"
)
MANIFEST = ROOT / (
    "build/post-promotion/v14/parity-toy-link90-artifact/stdlib-p0.manifest.json"
)
DISASM = ROOT / (
    "build/post-promotion/v14/parity-toy-link90-artifact/stdlib-p0.disasm.txt"
)
TARGET_RED = EVIDENCE / "c2.3-v1.4-link90-vic-unlock-inline-target-first-red.json"
ARGUMENT_WITNESS = EVIDENCE / (
    "c2.3-v1.4-link89-ship-shape-input-probe-order-first-red.json"
)
PAIR_WITNESS = EVIDENCE / "c2.3-v1.4-link89-vic-unlock-tailcall-attribution.json"
VM = ROOT / "src/vm.c"
VM_EMBED = ROOT / "src/vm_embed.c"
M65 = ROOT / "lib/m65-hw.lisp"
SHIP_MAIN = ROOT / "products/runtime-core/main.c"
SHIP_IO = ROOT / "products/runtime-core/ship_io.c"
SHIP_BUILDER = ROOT / "tools/host-lisp/ship_builder.py"
CONTRACT = ROOT / "config/c2-m65-hw-contract.json"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
DRIVER = Path(__file__).resolve()


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def audit(facts: dict[str, Any]) -> None:
    capture = facts["capture_authority"]
    require(capture["bytes"] == 16, "target readback size drift")
    require(capture["hex"] == "e30000000103000f38015040ff800000",
            "target readback bytes drift")
    require(capture["decoded_prefix"] == {
        "0x85": "runtime-state-E3", "0x86-0x87": "runtime-result-NIL",
        "0x88": "preload-detail-OK", "0x89": "toplevel-active-1",
        "0x8a": "vm-status-TYPEERROR-3",
    }, "target prefix decoding drift")
    require(capture["bytes_0x8b_through_0x8d"] == "unowned-padding-not-debug",
            "non-symbol bytes were promoted to diagnostics")

    debug = facts["debug_capture"]
    require(debug["symbols_present"] == []
            and debug["target_diagnostics_define"] is False
            and debug["target_step_limit_define"] is False
            and debug["target_dma_prof_define"] is False,
            "target VM debug-capture absence drift")
    require(debug["commissioned_site_binding"] == "unavailable",
            "an absent target diagnostic was claimed")

    host = facts["exact_host_replay"]
    require(host["status"] == "passed" and host["vm_status"] == 0
            and host["artifact_objects"] == 36,
            "exact Link-90 host replay drift")

    args = facts["argument_domain"]
    require(args["sprite"] == 0 and args["shape_length"] == 63
            and args["shape_byte_zero"] == 88
            and args["single_string_literal_bytes"] == 63,
            "target shape argument witness drift")
    require(args["outer_argument_rejection"] == "excluded-by-target-witness",
            "outer shape arguments were not excluded")

    boundary = facts["remaining_boundary"]
    require(boundary["first_host_target_semantic_difference"]
            == "live-D06C-D06E-versus-host-zero-fixture",
            "first host/target semantic difference drift")
    require(boundary["ship_initializes_D06C_D06E"] is False
            and boundary["exact_post-unlock_Link90_values_captured"] is False,
            "Ship pointer-table ownership evidence drift")
    require(boundary["mechanism_fully_attributed"] is False,
            "bounded attribution was overclaimed")
    require(boundary["unresolved"] == [
        "pointer-geometry-rejection-after-the-inline-unlock",
        "target-only-failure-between-the-accepted-outer-arguments-and-the-shape-writer",
    ], "remaining target boundary drift")

    require(facts["scope"] == {
        "product_candidate_bytes_changed": 0,
        "product_fixes": 0,
        "product_links": 0,
        "hardware_contacts": 0,
        "v1.4_status": "closed-pending-owner-method-decision",
    }, "attribution scope drift")


def mutation_check(facts: dict[str, Any]) -> dict[str, str]:
    rows: dict[str, tuple[list[str], Any]] = {
        "invent-debug-symbol": (["debug_capture", "symbols_present"], ["vm_dbg_pc"]),
        "claim-site": (["debug_capture", "commissioned_site_binding"], "m65-sprite-shape"),
        "erase-target-argument": (["argument_domain", "shape_length"], 0),
        "claim-boot-ownership": (["remaining_boundary", "ship_initializes_D06C_D06E"], True),
        "claim-attribution": (["remaining_boundary", "mechanism_fully_attributed"], True),
        "claim-product-fix": (["scope", "product_fixes"], 1),
    }
    rejected: dict[str, str] = {}
    for label, (path, value) in rows.items():
        candidate = deepcopy(facts)
        target: Any = candidate
        for component in path[:-1]:
            target = target[component]
        target[path[-1]] = value
        try:
            audit(candidate)
        except AttributionError as error:
            rejected[label] = str(error)
        else:
            raise AttributionError(f"verification mutation survived: {label}")
    return rejected


def main() -> int:
    try:
        truth = ElfTruth.read(ELF, llvm_readobj=READOBJ)
        names = {symbol.name for symbol in truth.symbols}
        debug_names = sorted(name for name in names
                             if name.startswith("vm_dbg") or name.startswith("vm_diag"))
        zp = {}
        for name in (
            "lisp65_runtime_state", "lisp65_runtime_result",
            "lisp65_runtime_preload_detail", "lisp_toplevel_active", "vm_status",
        ):
            symbol = truth.symbol(name)
            zp[name] = {"address": f"0x{symbol.value:02x}", "bytes": symbol.bytes}
        require(zp == {
            "lisp65_runtime_state": {"address": "0x85", "bytes": 1},
            "lisp65_runtime_result": {"address": "0x86", "bytes": 2},
            "lisp65_runtime_preload_detail": {"address": "0x88", "bytes": 1},
            "lisp_toplevel_active": {"address": "0x89", "bytes": 1},
            "vm_status": {"address": "0x8a", "bytes": 1},
        }, "target zero-page runtime layout drift")

        target = load(TARGET_RED)
        host = load(SHIP_RECEIPT)
        manifest = load(MANIFEST)
        argument = load(ARGUMENT_WITNESS)
        pair = load(PAIR_WITNESS)
        disasm = DISASM.read_text(encoding="utf-8")
        vm = VM.read_text(encoding="utf-8")
        vm_embed = VM_EMBED.read_text(encoding="utf-8")
        m65 = M65.read_text(encoding="utf-8")
        ship_main = SHIP_MAIN.read_text(encoding="utf-8").lower()
        ship_io = SHIP_IO.read_text(encoding="utf-8").lower()
        builder = SHIP_BUILDER.read_text(encoding="utf-8")

        runtime_hex = target["observation"]["runtime"]["hex"]
        runtime_bytes = bytes.fromhex(runtime_hex)
        require(len(runtime_bytes) == 16, "target runtime readback is not 16 bytes")
        require("-DLISP65_VM_DIAGNOSTICS" in builder,
                "host diagnostic define anchor absent")
        runtime_defines = builder.split("def runtime_compile", 1)[1]
        require("-DLISP65_VM_DIAGNOSTICS" not in runtime_defines,
                "target Runtime unexpectedly enables VM diagnostics")
        require("-DVM_STEP_LIMIT" not in runtime_defines
                and "-DLISP65_DMA_PROF" not in runtime_defines,
                "target Runtime unexpectedly enables minimal VM capture")
        require("#if defined(VM_STEP_LIMIT) || defined(LISP65_DMA_PROF)" in vm,
                "minimal VM capture build condition drift")

        nodes = manifest["literal_nodes"]
        string_nodes = [node for node in nodes if node["kind"] == 7]
        require(len(string_nodes) == 1 and len(string_nodes[0]["name"]) == 63,
                "parity-toy string literal inventory drift")
        require(any(patch["node"] == 8 and patch["blob_offset"] == 101
                    for patch in manifest["literal_patches"]),
                "main shape literal patch drift")
        require("0030 PUSHI8 0" in disasm and "0032 PUSHLIT 2" in disasm
                and "0034 CALL lit=3 argc=2" in disasm,
                "main sprite-shape call boundary drift")
        require("(= (string-length shape) 63)" in m65
                and "(%m65-sprite-write-shape shape 0)" in m65
                and "(<= table-low 248)" in m65,
                "sprite-shape source boundary drift")
        require("case lisp65_bc_lit_string" in vm_embed.lower()
                and "str_putc" in vm_embed,
                "target string materializer drift")

        decoded = argument["observation"]["decoded_pre_unlock_values"]
        require(decoded["shape_length"] == 63 and decoded["shape_byte_zero"] == 88,
                "bound target shape argument witness drift")
        exact_pair = pair["discriminators"]["exact_pair_fixture"]
        require(exact_pair["target_state"] == "RUNTIME_COMPLETE=3",
                "exact raw VIC pair target witness drift")

        host_output = host["host_execution"]["output"]
        require(host["host_execution"]["status"] == "passed"
                and "status=0" in host_output,
                "exact Link-90 host replay is not green")
        require("if (address == 0xff83u)" in ship_io
                and "if (address == 0xff84u)" in ship_io
                and "return 0u;" in ship_io,
                "Ship host I/O fallback drift")
        require("0xd06c" not in ship_main and "0xd06d" not in ship_main
                and "0xd06e" not in ship_main
                and "0xd06c" not in ship_io and "0xd06d" not in ship_io
                and "0xd06e" not in ship_io,
                "Ship boot now initializes sprite pointer geometry")

        facts = {
            "capture_authority": {
                "bytes": len(runtime_bytes), "hex": runtime_hex,
                "zero_page_symbols": zp,
                "decoded_prefix": {
                    "0x85": "runtime-state-E3", "0x86-0x87": "runtime-result-NIL",
                    "0x88": "preload-detail-OK", "0x89": "toplevel-active-1",
                    "0x8a": "vm-status-TYPEERROR-3",
                },
                "bytes_0x8b_through_0x8d": "unowned-padding-not-debug",
            },
            "debug_capture": {
                "symbols_present": debug_names,
                "target_diagnostics_define": False,
                "target_step_limit_define": False,
                "target_dma_prof_define": False,
                "commissioned_site_binding": "unavailable",
                "correction": "the existing readback cannot name pc/op/bank/off",
            },
            "exact_host_replay": {
                "status": host["host_execution"]["status"],
                "vm_status": 0,
                "output": host_output,
                "artifact_objects": manifest["objects"],
                "same_emitted_manifest": MANIFEST.resolve().relative_to(ROOT).as_posix(),
            },
            "argument_domain": {
                "sprite": 0,
                "shape_length": decoded["shape_length"],
                "shape_byte_zero": decoded["shape_byte_zero"],
                "single_string_literal_bytes": len(string_nodes[0]["name"]),
                "outer_argument_rejection": "excluded-by-target-witness",
                "limit": "the witness precedes the call; it does not prove the nested writer call",
            },
            "remaining_boundary": {
                "first_host_target_semantic_difference":
                    "live-D06C-D06E-versus-host-zero-fixture",
                "host_behavior": "unmodeled non-clock peeks fall through to VM zero",
                "target_behavior": "peek reads live memory-mapped VIC-IV registers",
                "ship_initializes_D06C_D06E": False,
                "exact_raw_D02F_pair_target_green": True,
                "exact_post-unlock_Link90_values_captured": False,
                "mechanism_fully_attributed": False,
                "unresolved": [
                    "pointer-geometry-rejection-after-the-inline-unlock",
                    "target-only-failure-between-the-accepted-outer-arguments-and-the-shape-writer",
                ],
                "why_screen_is_not_a_site_witness":
                    "sprite enable occurs only after shape returns; no sprite is expected at either unresolved point",
            },
            "smallest_honest_next_discriminator": {
                "preferred": "non-promotable target identity with VM_STEP_LIMIT-style pc/op/bank/off capture enabled",
                "alternative": "production-order CPU-side witnesses after argument guard, after D06C-D06E guard and after first shape byte",
                "authorization": "owner Class-C decision required; not executed here",
            },
            "scope": {
                "product_candidate_bytes_changed": 0,
                "product_fixes": 0,
                "product_links": 0,
                "hardware_contacts": 0,
                "v1.4_status": "closed-pending-owner-method-decision",
            },
        }
        audit(facts)
        rejected = mutation_check(facts)
        receipt = {
            "format": "lisp65-c2.3-v1.4-link90-typeerror-host-elf-attribution-first-red-v1",
            "recorded_on": date.today().isoformat(),
            "status": "ATTRIBUTION FIRST RED: commissioned target VM site capture is absent",
            "candidate_link": 90,
            "facts": facts,
            "mutations": {"count": len(rejected), "rejected": rejected},
            "bindings": {
                "driver": bind(DRIVER), "elf": bind(ELF),
                "ship_receipt": bind(SHIP_RECEIPT), "manifest": bind(MANIFEST),
                "disassembly": bind(DISASM), "target_first_red": bind(TARGET_RED),
                "argument_witness": bind(ARGUMENT_WITNESS),
                "exact_pair_witness": bind(PAIR_WITNESS), "vm": bind(VM),
                "vm_embed": bind(VM_EMBED), "m65_hw": bind(M65),
                "ship_main": bind(SHIP_MAIN), "ship_io": bind(SHIP_IO),
                "ship_builder": bind(SHIP_BUILDER), "contract": bind(CONTRACT),
            },
            "disposition": (
                "Stop without fix, Link 91 or hardware. Return the missing diagnostic "
                "premise, green exact host replay, excluded outer argument guard and "
                "remaining two-way target boundary for owner method review."
            ),
            "claim_limit": (
                "A host/source/ELF attribution boundary only. It does not select pointer "
                "geometry or the nested shape-writer edge as the Link-90 target cause."
            ),
        }
        atomic_json(RECEIPT, receipt)
        print(
            "c2-v14-link90-typeerror-attribution: FIRST RED "
            "debug-site=absent host=green args=target-green remaining=2 mutations=%d"
            % len(rejected)
        )
        return 0
    except (AttributionError, ElfTruthError, KeyError, OSError, ValueError) as error:
        print(f"c2-v14-link90-typeerror-attribution: ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
