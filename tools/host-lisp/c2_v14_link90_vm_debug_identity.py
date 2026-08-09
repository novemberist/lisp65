#!/usr/bin/env python3
"""Build, bind and decode the non-promotable Link-90 VM-debug identity."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth, ElfTruthError  # noqa: E402


CONFIG = ROOT / "config/c2-v14-link90-vm-debug-identity.json"
OWNER = ROOT / "docs/planning/1.4-parity-pilot-work-plan.md"
VM = ROOT / "src/vm.c"
MAIN = ROOT / "products/runtime-core/main.c"
WRAPPER = ROOT / "scripts/c2-v14-link90-vm-debug-cc.sh"
HW = ROOT / "scripts/c2-v14-link90-vm-debug-hw.sh"
BUILDER = ROOT / "tools/host-lisp/ship_builder.py"
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PREPARATION = EVIDENCE / (
    "c2.3-v1.4-link90-vm-debug-identity-preparation-receipt.json")
RESULT = EVIDENCE / (
    "c2.3-v1.4-link90-vm-debug-identity-device-receipt.json")
BASE = ROOT / "build/post-promotion/v14/link90-vm-debug-identity"
DEPLOYMENT = BASE / "deployment.json"
RUN = BASE / "run"


class DiagnosticError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise DiagnosticError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    resolved = path.resolve()
    try:
        label = resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        label = str(resolved)
    return {"path": label, "bytes": path.stat().st_size, "sha256": sha(path)}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def run(args: list[str], label: str) -> str:
    process = subprocess.run(args, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
    require(process.returncode == 0, f"{label} failed:\n{process.stdout}")
    return process.stdout


def clean_head() -> str:
    status = run(["git", "status", "--porcelain", "--untracked-files=all"],
                 "verify diagnostic source tree")
    require(status == "", "diagnostic preparation requires a clean worktree")
    return run(["git", "rev-parse", "HEAD"], "resolve source commit").strip()


def accesses(truth: ElfTruth, addresses: set[int]) -> list[dict[str, Any]]:
    opcodes = {
        0xAD: ("read", "lda"), 0xAE: ("read", "ldx"),
        0xAC: ("read", "ldy"), 0x8D: ("write", "sta"),
        0x8E: ("write", "stx"), 0x8C: ("write", "sty"),
        0x9C: ("write", "stz"),
    }
    rows: list[dict[str, Any]] = []
    for section in truth.sections:
        if "SHF_EXECINSTR" not in section.flags or section.bytes < 3:
            continue
        data = truth.section_bytes(section.name)
        for offset in range(len(data) - 2):
            opcode = data[offset]
            address = data[offset + 1] | (data[offset + 2] << 8)
            if opcode not in opcodes or address not in addresses:
                continue
            direction, instruction = opcodes[opcode]
            rows.append({
                "section": section.name,
                "pc": f"0x{section.address + offset:04x}",
                "direction": direction,
                "instruction": instruction,
                "address": f"0x{address:04x}",
            })
    return rows


def symbol_row(truth: ElfTruth, name: str) -> dict[str, Any]:
    symbol = truth.symbol(name)
    require(symbol.section not in ("Absolute", "Undefined"),
            f"diagnostic symbol not linked: {name}")
    require(0x0020 <= symbol.value < 0xD000,
            f"diagnostic symbol not in ordinary monitor-visible RAM: {name}")
    return {
        "name": name, "address": f"0x{symbol.value:08x}",
        "bytes": symbol.bytes or 1, "section": symbol.section,
    }


def audit(facts: dict[str, Any]) -> None:
    require(facts["identity"] == {
        "promotable": False, "product_candidate_bytes_changed": 0,
        "product_links": 0, "diagnostic_identities": 1,
    }, "diagnostic identity boundary drift")
    require(facts["diagnostic_runtime_contract"]["product_wall_changed"] is False
            and facts["diagnostic_runtime_contract"]["post_boot_reserve_param"] == 8160
            and facts["diagnostic_runtime_contract"]["actual_stack_heap_bytes"] >= 16352,
            "diagnostic-only runtime reserve proof drift")
    require(facts["fault_capture"] == {
        "natural_vm_error": True,
        "fields": ["pc", "op", "bank", "off"],
        "ordinary_ram": True,
    }, "VM fault-capture semantics drift")
    require(facts["vic_sampler"] == {
        "cpu_reads": ["0xd06c", "0xd06d", "0xd06e"],
        "io_writes": [], "after_vm_error": True,
        "sample_latch": True,
    }, "VIC CPU sampler semantics drift")
    require(facts["contact"] == {
        "hardware_contacts": 1, "physical_keys": 0, "virtual_keys": 0,
        "screen_polls_during_execution": 0,
    }, "device contact boundary drift")


def mutation_check(facts: dict[str, Any]) -> dict[str, str]:
    changes: dict[str, tuple[list[str], Any]] = {
        "make-promotable": (["identity", "promotable"], True),
        "claim-product-delta": (["identity", "product_candidate_bytes_changed"], 1),
        "claim-product-link": (["identity", "product_links"], 1),
        "claim-product-wall-change":
            (["diagnostic_runtime_contract", "product_wall_changed"], True),
        "erase-diagnostic-reserve":
            (["diagnostic_runtime_contract", "post_boot_reserve_param"], 0),
        "drop-fault-pc": (["fault_capture", "fields"], ["op", "bank", "off"]),
        "capture-watchdog-only": (["fault_capture", "natural_vm_error"], False),
        "drop-d06c": (["vic_sampler", "cpu_reads"], ["0xd06d", "0xd06e"]),
        "add-vic-write": (["vic_sampler", "io_writes"], ["0xd06c"]),
        "sample-before-error": (["vic_sampler", "after_vm_error"], False),
        "add-virtual-key": (["contact", "virtual_keys"], 1),
        "poll-screen": (["contact", "screen_polls_during_execution"], 1),
    }
    rejected: dict[str, str] = {}
    for label, (path, value) in changes.items():
        candidate = deepcopy(facts)
        target: Any = candidate
        for component in path[:-1]:
            target = target[component]
        target[path[-1]] = value
        try:
            audit(candidate)
        except DiagnosticError as error:
            rejected[label] = str(error)
        else:
            raise DiagnosticError(f"diagnostic mutation survived: {label}")
    return rejected


def build_image(output: Path, config: dict[str, Any], cc: Path | None) -> str:
    require(not output.exists(), f"diagnostic output already exists: {output}")
    args = [
        sys.executable, str(BUILDER), "build", "--form", config["form"],
        "--project", config["project"], "--out", str(output),
    ]
    if cc is not None:
        args += ["--cc", str(cc)]
    output_text = run(args, f"build {output.parent.name} Ship identity")
    run([sys.executable, str(BUILDER), "verify", "--image", str(output)],
        f"verify {output.parent.name} Ship identity")
    return output_text.strip()


def prepare() -> int:
    head = clean_head()
    config = load(CONFIG)
    owner = OWNER.read_text(encoding="utf-8")
    owner_flat = " ".join(owner.split())
    vm_source = VM.read_text(encoding="utf-8")
    main_source = MAIN.read_text(encoding="utf-8")
    require(config["status"] == "owner-authorized-non-promotable-diagnostic-identity",
            "owner authorization status drift")
    require("Authorized: the non-promotable VM-debug identity" in owner_flat
            and "CPU-side witness" in owner_flat
            and "Zero bytes on the product candidate" in owner_flat,
            "owner authorization text absent")
    for token in (
        "defined(LISP65_VM_FAULT_CAPTURE)", "vm_dbg_pc", "vm_dbg_op",
        "vm_dbg_bank", "vm_dbg_off",
    ):
        require(token in vm_source, f"minimal VM fault seam drift: {token}")
    for token in (
        "LISP65_V14_SPRITE_FAULT_DIAGNOSTIC",
        "*(volatile uint8_t *)0xd06c", "*(volatile uint8_t *)0xd06d",
        "*(volatile uint8_t *)0xd06e", "lisp65_v14_sprite_fault_sample();",
    ):
        require(token in main_source, f"CPU VIC witness source drift: {token}")

    reference_image = ROOT / config["reference_image"]
    reference_elf = ROOT / config["reference_runtime_elf"]
    reference_receipt = load(ROOT / config["reference_receipt"])
    require(sha(reference_image) == config["reference_image_sha256"],
            "Link-90 reference image drift")
    require(sha(reference_elf) == config["reference_runtime_elf_sha256"],
            "Link-90 reference Runtime ELF drift")
    before = {reference_image: sha(reference_image), reference_elf: sha(reference_elf)}

    control = ROOT / config["control_output"]
    diagnostic = ROOT / config["diagnostic_output"]
    build_image(control, config, None)
    control_elf = control.with_suffix(".runtime.elf")
    require(sha(control_elf) == config["reference_runtime_elf_sha256"],
            "inactive diagnostic seams changed the ordinary Runtime ELF")

    toolchain = diagnostic.parent / "diagnostic-toolchain"
    toolchain.mkdir(parents=True, exist_ok=False)
    cc = toolchain / "mos-mega65-clang"
    readobj = toolchain / "llvm-readobj"
    cc.symlink_to(WRAPPER)
    readobj.symlink_to(READOBJ)
    diagnostic_build = build_image(diagnostic, config, cc)
    diagnostic_elf = diagnostic.with_suffix(".runtime.elf")
    diagnostic_receipt = load(diagnostic.with_suffix(".receipt.json"))
    require(diagnostic_receipt["build_identity_sha256"]
            == reference_receipt["build_identity_sha256"],
            "diagnostic identity changed the emitted Lisp artifact")
    require(diagnostic_receipt["host_execution"]["status"] == "passed",
            "diagnostic identity host execution is not green")

    truth = ElfTruth.read(diagnostic_elf, llvm_readobj=READOBJ,
                          include_section_data=True)
    control_truth = ElfTruth.read(control_elf, llvm_readobj=READOBJ)
    required_names = (config["debug_symbols"] + config["vic_witness_symbols"]
                      + [config["runtime_state_symbol"], config["vm_status_symbol"]])
    rows = [symbol_row(truth, name) for name in required_names]
    control_names = {row.name for row in control_truth.symbols}
    require(not any(name in control_names for name in
                    config["debug_symbols"] + config["vic_witness_symbols"]),
            "diagnostic witnesses escaped into the ordinary Runtime")
    io_accesses = accesses(truth, {0xD06C, 0xD06D, 0xD06E})
    reads = {row["address"] for row in io_accesses if row["direction"] == "read"}
    require(reads == {"0xd06c", "0xd06d", "0xd06e"},
            "diagnostic ELF lacks an exact CPU VIC read set")
    require(not any(row["direction"] == "write" for row in io_accesses),
            "diagnostic ELF writes a VIC geometry register")
    require(all(sha(path) == digest for path, digest in before.items()),
            "Link-90 product candidate changed during diagnostic build")
    require(sha(diagnostic_elf) != sha(reference_elf),
            "diagnostic Runtime is byteidentical to the uninstrumented candidate")
    stack = truth.symbol("__stack").value
    heap_start = truth.symbol("__heap_start").value
    reserve_param = truth.symbol(
        "__lisp65_runtime_core_inline_required_post_boot_reserve_param").value
    require(reserve_param == config["diagnostic_post_boot_reserve_param"],
            "diagnostic-only post-boot reserve parameter drift")
    actual_stack_heap = stack - heap_start
    require(actual_stack_heap >= 8192 + reserve_param,
            "diagnostic Runtime misses its own stack/heap contract")

    facts = {
        "identity": {
            "promotable": False, "product_candidate_bytes_changed": 0,
            "product_links": 0, "diagnostic_identities": 1,
        },
        "diagnostic_runtime_contract": {
            "product_wall_changed": False,
            "post_boot_reserve_param": reserve_param,
            "actual_stack_heap_bytes": actual_stack_heap,
        },
        "fault_capture": {
            "natural_vm_error": True, "fields": ["pc", "op", "bank", "off"],
            "ordinary_ram": True,
        },
        "vic_sampler": {
            "cpu_reads": ["0xd06c", "0xd06d", "0xd06e"], "io_writes": [],
            "after_vm_error": True, "sample_latch": True,
        },
        "contact": {
            "hardware_contacts": config["limits"]["hardware_contacts"],
            "physical_keys": config["limits"]["physical_keys"],
            "virtual_keys": config["limits"]["virtual_keys"],
            "screen_polls_during_execution":
                config["limits"]["screen_polls_during_execution"],
        },
    }
    audit(facts)
    rejected = mutation_check(facts)
    by_name = {row["name"]: row for row in rows}
    deployment = {
        "format": "lisp65-c2.3-v1.4-link90-vm-debug-deployment-v1",
        "status": "prepared", "source_commit": head, "candidate_link": 90,
        "image": bind(diagnostic), "runtime_elf": bind(diagnostic_elf),
        "remote": config["remote"], "terminal_value": config["terminal_value"],
        "typeerror_value": config["typeerror_value"],
        "symbols": by_name,
    }
    write_json(DEPLOYMENT, deployment)
    receipt = {
        "format": "lisp65-c2.3-v1.4-link90-vm-debug-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status": "PREPARED-NON-PROMOTABLE-VM-DEBUG-IDENTITY",
        "candidate_link": 90, "facts": facts,
        "control": {
            "image": bind(control), "runtime_elf": bind(control_elf),
            "byteidentical_to_link90_runtime_elf": True,
        },
        "diagnostic": {
            "image": bind(diagnostic), "runtime_elf": bind(diagnostic_elf),
            "symbols": rows, "io_accesses": io_accesses,
            "build_output": diagnostic_build,
        },
        "reference_candidate": {
            "image": bind(reference_image), "runtime_elf": bind(reference_elf),
            "unchanged_after_build": True,
        },
        "verification": {
            "executions": 2, "mutation_count": len(rejected),
            "mutations_rejected": rejected,
        },
        "bindings": {
            "config": bind(CONFIG), "owner_review": bind(OWNER),
            "vm": bind(VM), "runtime_main": bind(MAIN),
            "compiler_wrapper": bind(WRAPPER), "hardware_script": bind(HW),
            "ship_builder": bind(BUILDER), "driver": bind(DRIVER),
            "deployment": bind(DEPLOYMENT),
        },
        "claim_limit": (
            "Host/ELF preparation only. The ordinary Runtime ELF is byteidentical "
            "to Link 90 and the product candidate is unchanged. No device result yet."),
    }
    write_json(PREPARATION, receipt)
    print("c2-v14-link90-vm-debug: PREPARED "
          f"symbols={len(rows)} mutations={len(rejected)} control-identical=1")
    return 0


def dry_run() -> int:
    deployment = load(DEPLOYMENT)
    preparation = load(PREPARATION)
    require(deployment["status"] == "prepared"
            and preparation["status"]
                == "PREPARED-NON-PROMOTABLE-VM-DEBUG-IDENTITY",
            "diagnostic deployment status drift")
    for row in preparation["bindings"].values():
        require(bind(ROOT / row["path"])["sha256"] == row["sha256"],
                f"bound preparation input drift: {row['path']}")
    require(bind(ROOT / deployment["image"]["path"])["sha256"]
            == deployment["image"]["sha256"], "diagnostic image drift")
    require(bind(ROOT / deployment["runtime_elf"]["path"])["sha256"]
            == deployment["runtime_elf"]["sha256"], "diagnostic ELF drift")
    print("c2-v14-link90-vm-debug: DRY-RUN PASS "
          "cold-reset=1 BASIC-gate=1 input=0 screen-polls=0 terminal=E3")
    return 0


def captured(name: str, deployment: dict[str, Any]) -> int:
    row = deployment["symbols"][name]
    path = RUN / f"{name}.bin"
    require(path.is_file() and path.stat().st_size == row["bytes"],
            f"captured witness absent/short: {name}")
    return int.from_bytes(path.read_bytes(), "little")


def analyze() -> int:
    deployment = load(DEPLOYMENT)
    preparation = load(PREPARATION)
    config = load(CONFIG)
    manifest = load(ROOT / config["artifact_manifest"])
    values = {name: captured(name, deployment) for name in deployment["symbols"]}
    require(values[config["runtime_state_symbol"]] == config["terminal_value"],
            "capture is not the VM-error terminal state")
    require(values[config["vm_status_symbol"]] == config["typeerror_value"],
            "capture is not VM_TYPEERROR")
    require(values["lisp65_v14_sprite_fault_sampled"] == 1,
            "CPU VIC sampler did not run")
    bank = values["vm_dbg_bank"]
    off = values["vm_dbg_off"]
    pc = values["vm_dbg_pc"]
    op = values["vm_dbg_op"]
    entries = [row for row in manifest["entries"]
               if (int(row["ext_addr"], 16) >> 16) == bank
               and (int(row["ext_addr"], 16) & 0xFFFF) == off]
    require(len(entries) == 1, f"fault object does not map uniquely: bank={bank} off={off}")
    entry = entries[0]
    require(0 <= pc <= entry["length"], "fault pc outside captured object")
    blob = ROOT / manifest["blob"]
    require(blob.is_file(), "bound bytecode blob absent")
    object_bytes = blob.read_bytes()[
        entry["blob_offset"]:entry["blob_offset"] + entry["length"]]
    header_bytes = 7 + 2 * entry["lit_count"]
    payload = object_bytes[header_bytes:]
    instruction_bytes = 3 if op in (60, 61, 62) else 1
    instruction_start = pc - instruction_bytes
    tuple_coherent = (instruction_start >= 0
                      and instruction_start < len(payload)
                      and payload[instruction_start] == op)
    object_byte_at_claimed_start = (
        payload[instruction_start] if 0 <= instruction_start < len(payload)
        else None)
    geometry = {
        "d06c": values["lisp65_v14_sprite_fault_d06c"],
        "d06d": values["lisp65_v14_sprite_fault_d06d"],
        "d06e": values["lisp65_v14_sprite_fault_d06e"],
    }
    pointer_guard_accepts = geometry["d06e"] == 0 and geometry["d06c"] <= 248
    if not tuple_coherent:
        classification = "non-atomic-recursive-vm-debug-tuple"
        mechanism = (
            "The four minimal VM fields do not describe one instruction: OP_CALLPRIM "
            "has length three, so post-PC 0x002a claims an opcode at 0x0027, but "
            "the bound m65-sprite-shape payload contains 0x01 there. Recursive VM "
            "state clobbered the minimal seam; production-order witnesses remain required.")
        fully_attributed = False
    elif entry["name"] == "%m65-error" and op == 17 and not pointer_guard_accepts:
        classification = "pointer-geometry-rejection-after-inline-unlock"
        mechanism = (
            "The target reads a nonzero/high or out-of-range live sprite pointer table "
            "base from D06C-D06E; m65-sprite-shape takes its pointer-geometry error tail.")
        fully_attributed = True
    elif entry["name"] != "%m65-error":
        classification = "target-only-failure-at-captured-consumer"
        mechanism = (
            "The coherent tuple binds the target-only VM_TYPEERROR to the captured "
            "consumer object; its exact instruction determines the next source boundary.")
        fully_attributed = True
    else:
        classification = "fault-pc-and-end-sample-not-disjoint-production-order-fallback-required"
        mechanism = (
            "The fault is the deliberate %m65-error MOD, but the end-state geometry passes "
            "the guard; temporal/order witnesses are required before attribution.")
        fully_attributed = False

    raw_bindings = {name: bind(RUN / f"{name}.bin") for name in deployment["symbols"]}
    receipt = {
        "format": "lisp65-c2.3-v1.4-link90-vm-debug-device-v1",
        "recorded_on": date.today().isoformat(),
        "status": ("ATTRIBUTED" if fully_attributed else "BOUNDED-FIRST-RED"),
        "candidate_link": 90,
        "scope": {
            "promotable": False, "product_candidate_bytes_changed": 0,
            "product_links": 0, "hardware_contacts": 1,
        },
        "fault": {
            "vm_status": values[config["vm_status_symbol"]],
            "pc": f"0x{pc:04x}", "op": f"0x{op:02x}",
            "bank": f"0x{bank:02x}", "off": f"0x{off:04x}",
            "function": entry["name"], "function_ext_addr": entry["ext_addr"],
            "function_length": entry["length"],
            "tuple_coherent": tuple_coherent,
            "instruction_bytes": instruction_bytes,
            "claimed_instruction_start": f"0x{instruction_start:04x}",
            "object_byte_at_claimed_start": (
                f"0x{object_byte_at_claimed_start:02x}"
                if object_byte_at_claimed_start is not None else None),
        },
        "live_vic_geometry": {
            **{key: f"0x{value:02x}" for key, value in geometry.items()},
            "sample_latch": values["lisp65_v14_sprite_fault_sampled"],
            "pointer_guard_accepts": pointer_guard_accepts,
        },
        "decision": {
            "classification": classification,
            "mechanism": mechanism,
            "fully_attributed": fully_attributed,
            "production_order_fallback_required": not fully_attributed,
        },
        "device": {
            "uploaded_image": deployment["image"],
            "device_readback": bind(RUN / "readback.d81"),
            "byteidentical_media": sha(RUN / "readback.d81")
                == deployment["image"]["sha256"],
            "raw_witnesses": raw_bindings,
        },
        "bindings": {
            "config": bind(CONFIG), "preparation": bind(PREPARATION),
            "deployment": bind(DEPLOYMENT), "artifact_manifest":
                bind(ROOT / config["artifact_manifest"]),
            "artifact_disassembly": bind(ROOT / config["artifact_disassembly"]),
            "artifact_blob": bind(blob),
            "hardware_script": bind(HW), "driver": bind(DRIVER),
        },
        "claim_limit": (
            "One non-promotable diagnostic hardware contact. Fault-site and CPU-side "
            "VIC geometry only; no product fix, product link or promotion."),
    }
    require(receipt["device"]["byteidentical_media"],
            "device media readback differs from diagnostic upload")
    write_json(RESULT, receipt)
    print("c2-v14-link90-vm-debug: " + receipt["status"] + " "
          f"function={entry['name']} pc=0x{pc:04x} op=0x{op:02x} "
          f"D06C-E={geometry['d06c']:02x}/{geometry['d06d']:02x}/{geometry['d06e']:02x} "
          f"classification={classification}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "dry-run", "analyze"))
    args = parser.parse_args()
    if args.action == "prepare":
        return prepare()
    if args.action == "dry-run":
        return dry_run()
    return analyze()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (DiagnosticError, ElfTruthError, KeyError, OSError, ValueError,
            json.JSONDecodeError) as error:
        print(f"c2-v14-link90-vm-debug: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
