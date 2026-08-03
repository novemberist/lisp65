#!/usr/bin/env python3
"""Audit the Link-86 queue discriminator's monitor read semantics.

The physical-key row used ``m65 --memsave`` at $D60A/$D619 and interpreted
the two returned zero bytes as live I/O.  This host/ELF-only attribution binds
the actual tool path, the project's earlier G6 precedent, both Link-86 product
ELFs, and the pinned core queue producer.  It deliberately does not repair the
product or replace the invalid target observation with another assumption.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / (
    "c2.3-v1.3-link86-queue-capture-view-host-elf-attribution-receipt.json"
)
PRIOR = EVIDENCE / (
    "c2.3-v1.3-link86-physical-key-queue-discriminator-receipt.json"
)
SESSION = ROOT / "scripts/c2-v13-link86-queue-discriminator-hw.sh"
CLOSER = ROOT / "tools/host-lisp/c2_v13_link86_queue_discriminator_close.py"
G6 = ROOT / "tools/host-lisp/c2_lite_g6.py"
SHIP_MAIN = ROOT / "products/runtime-core/main.c"
WORKBENCH_MAIN = ROOT / "src/main.c"
WORKBENCH_OWNER = ROOT / "src/c2_kernal_runtime.c"
WORKBENCH_QUEUE = ROOT / "src/c2_kernal_window.s"
SHIP_ELF = ROOT / "build/ship-builder/v13/link86-final-5a7c0d18/interactive.runtime.elf"
WORKBENCH_ELF = ROOT / (
    "build/c2.3/v1.3.0-candidate-product-link86-r1/final/"
    "lisp65-c2-substitution-linked.prg.elf"
)
CORE = ROOT / "build/post-v1.2.4/upstream-recheck/mega65-core"
CORE_UART = CORE / "src/vhdl/c65uart.vhdl"
CORE_IOMAPPER = CORE / "src/vhdl/iomapper.vhdl"
M65 = ROOT / "tools/m65tools/m65"
M65_REPO = Path(os.environ.get(
    "LISP65_MEGA65_TOOLS_REPOSITORY",
    str(ROOT / "build/post-v1.2.4/upstream-recheck/mega65-tools"),
))
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
DRIVER = Path(__file__).resolve()

SHIP_ELF_SHA = "6a256512378142ece82ca6405cbf01a60f7c01f2312a84b9eb4f37969d26a0b4"
WORKBENCH_ELF_SHA = "cf8d4c9bb6404f9df3a47241628793206a90a60946202647e9a631d2ef6e5245"
M65_SHA = "158c932c07a82771704c86e8ee79700c992e150fe0cd64b2ba99b10071233bc4"
M65_COMMIT = "c5bf0ccd7ec6398290176f8af928d0780482577f"
CORE_COMMIT = "a9158930665763c592d004c895d52eff4a9eefc3"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return digest(path.read_bytes())


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    resolved = path.resolve()
    try:
        label = resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        label = str(resolved)
    return {"path": label, "bytes": path.stat().st_size, "sha256": sha(path)}


def bind_blob(label: str, data: bytes) -> dict[str, Any]:
    return {"path": label, "bytes": len(data), "sha256": digest(data)}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def run(args: list[str], *, cwd: Path = ROOT) -> str:
    process = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
    require(process.returncode == 0,
            f"command failed ({' '.join(args)}):\n{process.stdout}")
    return process.stdout


def git_blob(path: str) -> bytes:
    process = subprocess.run(["git", "show", f"{M65_COMMIT}:{path}"],
                             cwd=M65_REPO, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    require(process.returncode == 0,
            f"mega65-tools authority absent: {path}: {process.stderr.decode(errors='replace')}")
    return process.stdout


def absolute_accesses(truth: ElfTruth, addresses: set[int]) -> list[dict[str, Any]]:
    opcodes = {
        0xAD: ("read", "lda"), 0xAE: ("read", "ldx"),
        0xAC: ("read", "ldy"), 0x8D: ("write", "sta"),
        0x8E: ("write", "stx"), 0x8C: ("write", "sty"),
        0x9C: ("write", "stz"),
    }
    result: list[dict[str, Any]] = []
    for section in truth.sections:
        if "SHF_EXECINSTR" not in section.flags or section.bytes < 3:
            continue
        data = truth.section_bytes(section.name)
        for offset in range(len(data) - 2):
            opcode = data[offset]
            address = data[offset + 1] | (data[offset + 2] << 8)
            if opcode in opcodes and address in addresses:
                direction, instruction = opcodes[opcode]
                result.append({
                    "section": section.name,
                    "pc": f"0x{section.address + offset:04x}",
                    "direction": direction,
                    "instruction": instruction,
                    "address": f"0x{address:04x}",
                })
    return result


def audit(facts: dict[str, Any]) -> None:
    require(facts["capture"] == {
        "api": "m65 --memsave",
        "implementation": "memory_save->fetch_ram->monitor-m/M",
        "view": "RAM-under-mapped-I/O-not-live-I/O",
        "live_queue_observed": False,
    }, "capture-view classification drift")
    require(facts["prior_interpretation"] == {
        "bytes": [0, 0],
        "queue_empty_claim": "invalidated",
        "getin_refuted": False,
        "queue_production_dead": False,
    }, "prior interpretation was not withdrawn completely")
    require(facts["static_diff"] == {
        "both_unlock-mega65-io": True,
        "workbench-private-queue-arm-registers": [],
        "ship-private-queue-arm-registers": [],
        "workbench-queue-consumer": ["0xd60a-read", "0xd619-read-write"],
    }, "Workbench/Ship below-queue diff drift")
    require(facts["core"] == {
        "producer": "hardware-key-valid-edge",
        "cpu-irq-service-required": False,
        "physical-source-reset-enabled": True,
        "scan-rate-reset": "0xff",
        "queue-state-register": "0xd60a",
    }, "pinned core queue producer drift")
    require(facts["broaden_once_activated"] is False,
            "broaden-once activated from an invalid I/O observation")


def mutations(facts: dict[str, Any]) -> dict[str, str]:
    changes: dict[str, tuple[list[str], Any]] = {
        "pretend-native-io-view": (["capture", "view"], "live-I/O"),
        "pretend-live-queue-observed": (["capture", "live_queue_observed"], True),
        "keep-empty-claim": (["prior_interpretation", "queue_empty_claim"], "proven"),
        "keep-getin-refutation": (["prior_interpretation", "getin_refuted"], True),
        "keep-dead-producer": (["prior_interpretation", "queue_production_dead"], True),
        "invent-workbench-arm-register": (
            ["static_diff", "workbench-private-queue-arm-registers"], ["0xd612"]),
        "invent-ship-arm-register": (
            ["static_diff", "ship-private-queue-arm-registers"], ["0xd618"]),
        "make-producer-irq-owned": (["core", "cpu-irq-service-required"], True),
        "disable-physical-source-default": (["core", "physical-source-reset-enabled"], False),
        "activate-broaden-once": (["broaden_once_activated"], True),
    }
    rejected: dict[str, str] = {}
    for label, (path, replacement) in changes.items():
        candidate = deepcopy(facts)
        target: Any = candidate
        for component in path[:-1]:
            target = target[component]
        target[path[-1]] = replacement
        try:
            audit(candidate)
        except AttributionError as error:
            rejected[label] = str(error)
        else:
            raise AttributionError(f"verification mutation survived: {label}")
    return rejected


def write_receipt(value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=RECEIPT.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(RECEIPT)


def main() -> int:
    require(sha(SHIP_ELF) == SHIP_ELF_SHA, "Link-86 Ship ELF drift")
    require(sha(WORKBENCH_ELF) == WORKBENCH_ELF_SHA, "Link-86 Workbench ELF drift")
    require(sha(M65) == M65_SHA, "m65 capture binary drift")
    require(run(["git", "rev-parse", "HEAD"], cwd=CORE).strip() == CORE_COMMIT,
            "pinned mega65-core checkout drift")
    require(run(["git", "rev-parse", "HEAD"], cwd=M65_REPO).strip() == M65_COMMIT,
            "mega65-tools source authority drift")

    prior = load(PRIOR)
    session = SESSION.read_text(encoding="utf-8")
    closer = CLOSER.read_text(encoding="utf-8")
    g6 = G6.read_text(encoding="utf-8")
    ship_main = SHIP_MAIN.read_text(encoding="utf-8")
    wb_main = WORKBENCH_MAIN.read_text(encoding="utf-8")
    owner = WORKBENCH_OWNER.read_text(encoding="utf-8")
    queue = WORKBENCH_QUEUE.read_text(encoding="utf-8")
    uart = CORE_UART.read_text(encoding="utf-8")
    iomapper = CORE_IOMAPPER.read_text(encoding="utf-8")
    m65_source = git_blob("src/tools/m65.c")
    common_source = git_blob("src/tools/m65common.c")
    m65_text = m65_source.decode("utf-8")
    common_text = common_source.decode("utf-8")

    require('run_m65 --memsave' in session
            and 'readback "$queue_state"' in session
            and 'readback "$queue_code"' in session,
            "queue row no longer uses m65 --memsave")
    require("fetch_ram(cur_addr, count, membuf);" in m65_text,
            "memory_save no longer delegates to fetch_ram")
    require('snprintf(cmd, 79, "m%X\\r"' in common_text
            and 'snprintf(cmd, 79, "M%X\\r"' in common_text,
            "fetch_ram no longer uses monitor m/M reads")
    disassembly = run(["objdump", "-d", "--disassemble=memory_save", str(M65)])
    require("<fetch_ram>" in disassembly,
            "installed m65 memory_save/fetch_ram call edge drift")
    require("m65 --memsave observes the RAM under the mapped I/O page" in g6
            and "native I/O reader" in g6,
            "bound G6 RAM-under-I/O precedent drift")
    require(prior["readback"] == {
        "D60A": "0x00", "D619": "0x00", "dequeue_writes": 0,
        "queue_present": False,
    } and prior["preregistered_interpretation"]["selected"] == "queue-empty",
            "prior queue interpretation drift")
    require("require(d60a == 0 and d619 == 0" in closer,
            "prior closer no longer interprets the RAM bytes as queue state")

    ship_truth = ElfTruth.read(SHIP_ELF, llvm_readobj=READOBJ,
                               include_section_data=True)
    wb_truth = ElfTruth.read(WORKBENCH_ELF, llvm_readobj=READOBJ,
                             include_section_data=True)
    keyboard_registers = {0xD60A, 0xD612, 0xD618, 0xD619}
    ship_accesses = absolute_accesses(ship_truth, keyboard_registers)
    wb_accesses = absolute_accesses(wb_truth, keyboard_registers)
    ship_arm_writes = [row for row in ship_accesses
                       if row["direction"] == "write"
                       and row["address"] in {"0xd612", "0xd618"}]
    wb_arm_writes = [row for row in wb_accesses
                     if row["direction"] == "write"
                     and row["address"] in {"0xd612", "0xd618"}]
    require(ship_arm_writes == [] and wb_arm_writes == [],
            "linked product gained a keyboard-source arm write")
    require(any(row["address"] == "0xd60a" and row["direction"] == "read"
                for row in wb_accesses)
            and any(row["address"] == "0xd619" and row["direction"] == "read"
                    for row in wb_accesses)
            and any(row["address"] == "0xd619" and row["direction"] == "write"
                    for row in wb_accesses),
            "Workbench linked queue consumer drift")

    io_unlock = (
        "*(volatile unsigned char *)0xD02F = 0x47;",
        "*(volatile unsigned char *)0xD02F = 0x53;",
        "*(volatile unsigned char *)0xD054 |= 0x40;",
    )
    require(all(token in ship_main and token in wb_main for token in io_unlock),
            "Ship/Workbench MEGA65-I/O unlock equivalence drift")
    require("$d60a" in queue.lower() and "$d619" in queue.lower()
            and "c2_kernal_reveal_io();" in owner,
            "Workbench queue/I/O source binding drift")

    require("signal physkey_enable_internal : std_logic := '1';" in uart
            and 'signal portn_internal : std_logic_vector(7 downto 0) := x"FF";' in uart,
            "core physical keyboard reset defaults drift")
    require("if key_valid='1' and last_key_valid='0' then" in iomapper
            and "key_presenting <= '1';" in iomapper
            and "fastio_rdata(7) <= key_presenting;" in uart,
            "core hardware queue producer drift")

    facts = {
        "capture": {
            "api": "m65 --memsave",
            "implementation": "memory_save->fetch_ram->monitor-m/M",
            "view": "RAM-under-mapped-I/O-not-live-I/O",
            "live_queue_observed": False,
        },
        "prior_interpretation": {
            "bytes": [0, 0],
            "queue_empty_claim": "invalidated",
            "getin_refuted": False,
            "queue_production_dead": False,
        },
        "static_diff": {
            "both_unlock-mega65-io": True,
            "workbench-private-queue-arm-registers": [],
            "ship-private-queue-arm-registers": [],
            "workbench-queue-consumer": ["0xd60a-read", "0xd619-read-write"],
        },
        "core": {
            "producer": "hardware-key-valid-edge",
            "cpu-irq-service-required": False,
            "physical-source-reset-enabled": True,
            "scan-rate-reset": "0xff",
            "queue-state-register": "0xd60a",
        },
        "broaden_once_activated": False,
    }
    audit(facts)
    rejected = mutations(facts)

    value = {
        "format": "lisp65-c2.3-v1.3-link86-queue-capture-view-attribution-v1",
        "recorded_on": date.today().isoformat(),
        "status": "FIRST-RED-PRIOR-QUEUE-DISCRIMINATOR-READ-RAM-NOT-LIVE-IO",
        "candidate_link": 86,
        "product_bytes_changed": 0,
        "product_links_created": 0,
        "hardware_contacts": 0,
        "facts": facts,
        "correction": {
            "superseded_claim": (
                "The two zero bytes prove that the live D60A/D619 queue was empty, "
                "therefore GETIN was refuted and queue production was dead."
            ),
            "correct_claim": (
                "The two files contain zero bytes from the monitor's RAM view under "
                "the mapped I/O page. They make no claim about live D60A/D619. The "
                "GETIN-consumer branch and the hardware-queue branch are both open."
            ),
            "historical_receipt": PRIOR.relative_to(ROOT).as_posix(),
            "history_policy": "preserved and explicitly superseded; not rewritten",
        },
        "below_queue_diff": {
            "result": "no-workbench-only-keyboard-source-arm-sequence-found",
            "ship_elf_accesses": ship_accesses,
            "workbench_elf_accesses": wb_accesses,
            "core_interpretation": (
                "The pinned core enqueues a physical key on a hardware key_valid "
                "edge. Physical input and the default scan-rate are enabled by reset; "
                "the producer is not a KERNAL or product IRQ service."
            ),
            "arm_readback_list": [],
            "reason_no_list": (
                "No second inherited subsystem has been established. Inventing D612 "
                "or D618 writes would be a speculative product change, not a diff."
            ),
        },
        "owner_boundary": {
            "mechanism_named": False,
            "fix_authorized": False,
            "broaden_once_disposition": "not-triggered-capture-premise-invalid",
            "smallest_valid_discriminator": (
                "Read D60A/D619 through a target-CPU/native-I/O witness and copy the "
                "result into ordinary RAM before using monitor memsave. This requires "
                "a new non-promotable diagnostic identity or equivalent owner-authorized "
                "target witness; no hardware retry is claimed here."
            ),
        },
        "verification": {
            "executions": 1,
            "mutations_rejected": rejected,
            "mutation_count": len(rejected),
        },
        "external_authority": {
            "mega65_tools_commit": M65_COMMIT,
            "m65_source": bind_blob(
                f"mega65-tools@{M65_COMMIT}:src/tools/m65.c", m65_source),
            "m65common_source": bind_blob(
                f"mega65-tools@{M65_COMMIT}:src/tools/m65common.c", common_source),
            "mega65_core_commit": CORE_COMMIT,
        },
        "bindings": {
            "driver": bind(DRIVER),
            "prior_queue_receipt": bind(PRIOR),
            "session": bind(SESSION),
            "prior_closer": bind(CLOSER),
            "g6_precedent": bind(G6),
            "m65_binary": bind(M65),
            "ship_elf": bind(SHIP_ELF),
            "workbench_elf": bind(WORKBENCH_ELF),
            "ship_main": bind(SHIP_MAIN),
            "workbench_main": bind(WORKBENCH_MAIN),
            "workbench_owner": bind(WORKBENCH_OWNER),
            "workbench_queue": bind(WORKBENCH_QUEUE),
            "core_uart": bind(CORE_UART),
            "core_iomapper": bind(CORE_IOMAPPER),
        },
        "claim_limit": (
            "Host/source/ELF attribution only. It invalidates the interpretation "
            "of the prior two RAM bytes; it does not infer live queue state, name "
            "an input mechanism, authorize a product fix, create a link or consume "
            "a hardware contact."
        ),
    }
    write_receipt(value)
    print(
        "c2-v13-link86-queue-capture-view-attribution: FIRST RED "
        f"view=RAM-under-I/O mutations={len(rejected)} broaden=not-triggered"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, KeyError, OSError, ValueError,
            json.JSONDecodeError) as error:
        print(f"c2-v13-link86-queue-capture-view-attribution: ERROR: {error}",
              file=sys.stderr)
        raise SystemExit(2)
