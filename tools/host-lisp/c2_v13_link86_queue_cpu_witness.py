#!/usr/bin/env python3
"""Build and bind the non-promotable Link-86 CPU-side queue witness."""

from __future__ import annotations

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
from elf_truth import ElfTruth  # noqa: E402


CONFIG = ROOT / "config/c2-ship-builder-v1-link86-queue-cpu-witness.json"
OWNER = ROOT / "docs/planning/1.3-link84-closing-first-red-review.md"
SOURCE = ROOT / "products/runtime-core/ship_io.c"
WRAPPER = ROOT / "scripts/c2-v13-link86-queue-cpu-witness-cc.sh"
BUILDER = ROOT / "tools/host-lisp/ship_builder.py"
CORRECTION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-link86-queue-capture-view-host-elf-attribution-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-link86-queue-cpu-witness-preparation-receipt.json"
)
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
C1541 = "c1541"


class WitnessError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise WitnessError(message)


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
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def run(args: list[str], label: str) -> str:
    process = subprocess.run(args, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
    require(process.returncode == 0, f"{label} failed:\n{process.stdout}")
    return process.stdout


def embedded_source_commit(image: Path) -> str:
    c1541 = shutil.which(C1541)
    require(c1541 is not None, "c1541 unavailable")
    with tempfile.TemporaryDirectory(prefix="lisp65-queue-witness-") as raw:
        manifest_path = Path(raw) / "ship.json"
        run([
            c1541, "-attach", str(image), "-read", "ship.json",
            str(manifest_path),
        ], "extract diagnostic Ship manifest")
        manifest = load(manifest_path)
    commit = manifest.get("source_commit")
    require(isinstance(commit, str) and len(commit) == 40
            and all(char in "0123456789abcdef" for char in commit),
            "embedded diagnostic source commit drift")
    return commit


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
            if opcode in opcodes and address in addresses:
                direction, instruction = opcodes[opcode]
                rows.append({
                    "section": section.name,
                    "pc": f"0x{section.address + offset:04x}",
                    "direction": direction,
                    "instruction": instruction,
                    "address": f"0x{address:04x}",
                })
    return rows


def symbol_row(truth: ElfTruth, name: str, *, diagnostic_ram: bool = True) -> dict[str, Any]:
    symbol = truth.symbol(name)
    require(symbol.section not in ("Absolute", "Undefined"),
            f"witness symbol not linked: {name}")
    low = 0x0200 if diagnostic_ram else 0x0080
    require(low <= symbol.value < 0xD000,
            f"witness is not in ordinary monitor-visible RAM: {name}=0x{symbol.value:04x}")
    if diagnostic_ram:
        require(symbol.section in (".bss", ".bss.lisp65_ship_queue_diag"),
                f"witness section drift: {name}={symbol.section}")
    return {
        "name": name,
        "address": f"0x{symbol.value:04x}",
        "bytes": symbol.bytes or 1,
        "section": symbol.section,
    }


def audit(facts: dict[str, Any]) -> None:
    require(facts["identity"] == {
        "promotable": False,
        "product_candidate_bytes_changed": 0,
        "diagnostic_images": 1,
    }, "diagnostic identity boundary drift")
    require(facts["sampler"] == {
        "cpu_reads": ["0xd60a", "0xd619"],
        "io_writes": [],
        "latches_first_present_event": True,
        "ordinary_ram_witnesses": 6,
        "call_sites": ["frame-peek", "getin"],
    }, "CPU sampler semantics drift")
    require(facts["contact"] == {
        "physical_keys": 1,
        "virtual_keys": 0,
        "post_key_screen_captures": 0,
    }, "contact budget drift")


def mutations(facts: dict[str, Any]) -> dict[str, str]:
    changes: dict[str, tuple[list[str], Any]] = {
        "make-promotable": (["identity", "promotable"], True),
        "claim-product-delta": (["identity", "product_candidate_bytes_changed"], 1),
        "drop-d60a-read": (["sampler", "cpu_reads"], ["0xd619"]),
        "drop-d619-read": (["sampler", "cpu_reads"], ["0xd60a"]),
        "add-dequeue-write": (["sampler", "io_writes"], ["0xd619"]),
        "remove-first-event-latch": (["sampler", "latches_first_present_event"], False),
        "drop-frame-peek-site": (["sampler", "call_sites"], ["getin"]),
        "add-virtual-key": (["contact", "virtual_keys"], 1),
        "add-screen-capture": (["contact", "post_key_screen_captures"], 1),
    }
    result: dict[str, str] = {}
    for label, (path, replacement) in changes.items():
        candidate = deepcopy(facts)
        target: Any = candidate
        for component in path[:-1]:
            target = target[component]
        target[path[-1]] = replacement
        try:
            audit(candidate)
        except WitnessError as error:
            result[label] = str(error)
        else:
            raise WitnessError(f"witness mutation survived: {label}")
    return result


def write(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def main() -> int:
    source_commit = run(["git", "rev-parse", "HEAD"], "resolve source commit").strip()
    require(run([
        "git", "status", "--porcelain", "--untracked-files=all",
    ], "verify clean source tree").strip() == "",
            "diagnostic build requires a clean source tree")
    config = load(CONFIG)
    correction = load(CORRECTION)
    owner = OWNER.read_text(encoding="utf-8")
    source = SOURCE.read_text(encoding="utf-8")
    require(config["status"] == "owner-authorized-non-promotable-diagnostic-identity",
            "owner authorization drift")
    require("CPU-side discriminator authorized" in owner
            and "zero bytes on the product candidate" in owner,
            "owner commission absent")
    require(correction["owner_boundary"]["broaden_once_disposition"]
            == "not-triggered-capture-premise-invalid",
            "capture-view correction drift")
    for token in (
        "LISP65_SHIP_QUEUE_DIAGNOSTIC",
        "*(volatile uint8_t *)0xd60a",
        "*(volatile uint8_t *)0xd619",
        "if (!lisp65_ship_queue_diag_latched && (state & 0x80u))",
        "ship_queue_diag_sample();",
    ):
        require(token in source, f"diagnostic sampler source drift: {token}")
    require(source.count("ship_queue_diag_sample();") == 2,
            "diagnostic sampler must cover frame-peek and GETIN")

    reference_image = ROOT / config["reference_image"]
    reference_elf = ROOT / config["reference_runtime_elf"]
    require(sha(reference_image) == config["reference_image_sha256"],
            "Link-86 reference image drift")
    require(sha(reference_elf) == config["reference_runtime_elf_sha256"],
            "Link-86 reference Runtime ELF drift")
    before = {str(reference_image): sha(reference_image), str(reference_elf): sha(reference_elf)}

    output = ROOT / config["output"]
    require(not output.exists(), f"diagnostic output already exists: {output}")
    toolchain = output.parent / "diagnostic-toolchain"
    toolchain.mkdir(parents=True, exist_ok=False)
    cc = toolchain / "mos-mega65-clang"
    readobj = toolchain / "llvm-readobj"
    cc.symlink_to(WRAPPER)
    readobj.symlink_to(READOBJ)
    build_output = run([
        sys.executable, str(BUILDER), "build",
        "--form", config["form"],
        "--project", config["project"],
        "--out", str(output),
        "--cc", str(cc),
    ], "diagnostic Ship build")
    verify_output = run([
        sys.executable, str(BUILDER), "verify", "--image", str(output),
    ], "diagnostic media verify")
    require(embedded_source_commit(output) == source_commit,
            "diagnostic Ship manifest does not bind the source commit")

    elf = output.with_suffix(".runtime.elf")
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    witness_rows = [symbol_row(truth, name) for name in config["witness_symbols"]]
    runtime_state = symbol_row(
        truth, config["runtime_state_symbol"], diagnostic_ram=False)
    io_accesses = accesses(truth, {0xD60A, 0xD619})
    require(any(row["address"] == "0xd60a" and row["direction"] == "read"
                for row in io_accesses), "diagnostic ELF lacks CPU D60A read")
    require(any(row["address"] == "0xd619" and row["direction"] == "read"
                for row in io_accesses), "diagnostic ELF lacks CPU D619 read")
    require(not any(row["direction"] == "write" for row in io_accesses),
            "diagnostic ELF writes a queue register")
    require(all(before[path] == sha(Path(path)) for path in before),
            "Link-86 product candidate changed during diagnostic build")
    require(sha(elf) != config["reference_runtime_elf_sha256"],
            "diagnostic Runtime is byteidentical to uninstrumented Link 86")

    facts = {
        "identity": {
            "promotable": False,
            "product_candidate_bytes_changed": 0,
            "diagnostic_images": 1,
        },
        "sampler": {
            "cpu_reads": ["0xd60a", "0xd619"],
            "io_writes": [],
            "latches_first_present_event": True,
            "ordinary_ram_witnesses": len(witness_rows),
            "call_sites": ["frame-peek", "getin"],
        },
        "contact": {
            "physical_keys": config["limits"]["physical_key_contacts"],
            "virtual_keys": config["limits"]["virtual_keys"],
            "post_key_screen_captures": config["limits"]["post_key_screen_captures"],
        },
    }
    audit(facts)
    rejected = mutations(facts)
    receipt = {
        "format": "lisp65-c2.3-v1.3-link86-queue-cpu-witness-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status": "PREPARED-NON-PROMOTABLE-CPU-IO-WITNESS",
        "candidate_link": 86,
        "facts": facts,
        "diagnostic": {
            "source_commit": source_commit,
            "image": bind(output),
            "runtime_elf": bind(elf),
            "runtime_state": runtime_state,
            "witnesses": witness_rows,
            "io_accesses": io_accesses,
            "build_output": build_output.strip(),
            "verify_output": verify_output.strip(),
        },
        "reference_candidate": {
            "image": bind(reference_image),
            "runtime_elf": bind(reference_elf),
            "unchanged_after_build": True,
        },
        "interpretation": config["interpretation"],
        "verification": {
            "executions": 1,
            "mutations_rejected": rejected,
            "mutation_count": len(rejected),
        },
        "bindings": {
            "config": bind(CONFIG),
            "owner_review": bind(OWNER),
            "capture_correction": bind(CORRECTION),
            "source": bind(SOURCE),
            "compiler_wrapper": bind(WRAPPER),
            "builder": bind(BUILDER),
            "driver": bind(DRIVER),
        },
        "claim_limit": (
            "Non-promotable diagnostic identity only. One CPU-side D60A/D619 "
            "sampler, no queue write, zero changed bytes in the Link-86 product "
            "candidate, zero product links and no hardware result yet."
        ),
    }
    write(RECEIPT, receipt)
    print(
        "c2-v13-link86-queue-cpu-witness: PREPARED "
        f"witnesses={len(witness_rows)} mutations={len(rejected)} "
        f"image={output.relative_to(ROOT)}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (WitnessError, KeyError, OSError, ValueError,
            json.JSONDecodeError) as error:
        print(f"c2-v13-link86-queue-cpu-witness: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
