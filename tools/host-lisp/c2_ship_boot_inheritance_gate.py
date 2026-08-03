#!/usr/bin/env python3
"""Permanent class closer for standalone Ship boot inheritance.

The clock under test and its progress oracle are intentionally different:
Ship owns an IRQ counter, while the complete D011/D012 9-bit raster is the
target reference and the host witness supplies the real 312-line sequence plus
an independent IRQ pulse.  Every starting phase is executed; the former D012
low-byte interpretation must fail all 312 phases.
"""

from __future__ import annotations

from copy import deepcopy
from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))
from elf_truth import ElfTruth  # noqa: E402


CONTRACT = ROOT / "config/c2-ship-boot-inheritance-contract.json"
SHARED = ROOT / "src/mega65_raster_timebase.h"
WORKBENCH = ROOT / "src/c2_kernal_runtime.c"
SHIP_IO = ROOT / "products/runtime-core/ship_io.c"
SHIP_TIMEBASE = ROOT / "products/runtime-core/ship_timebase.s"
SHIP_HEADER = ROOT / "src/ship_runtime_io.h"
RUNTIME = ROOT / "products/runtime-core/main.c"
BUILDER = ROOT / "tools/host-lisp/ship_builder.py"
HOST_RUNNER = ROOT / "scripts/ship-runtime-host-main.c"
HOST_WITNESS = ROOT / "scripts/ship-boot-inheritance-host-main.c"
INTERRUPT = ROOT / "src/interrupt.c"
ELF_TRUTH = ROOT / "tools/host-lisp/elf_truth.py"
COMPILER = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-ship-boot-inheritance-gate-receipt.json"
)


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def bind_tool(path: Path) -> dict[str, Any]:
    """Bind a tool by its checkout mount point and resolved file bytes.

    LLVM-MOS is an external, hash-bound toolchain rather than repository
    source.  Fresh-clone proofs deliberately mount the same tool tree at the
    canonical in-checkout path so full LTO cannot inherit a checkout-specific
    resource-directory identity.  Resolving that mount before making the path
    relative would confuse an external tool with escaped source.
    """
    require(path.is_file(), f"tool absent: {path}")
    data = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def write(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def validate(contract: dict[str, Any], shared: str, workbench: str,
             ship: str, timebase: str, header: str, runtime: str,
             builder: str, host: str, witness: str) -> None:
    target = contract["target"]
    host_contract = contract["host"]
    require(
        contract["format"] == "lisp65-c2-ship-boot-inheritance-v3"
        and contract["status"] == "owner-commissioned-permanent-gate"
        and target["failure_state"] == "RUNTIME_IO_ERROR=$E5"
        and target["independent_progress_oracle"]
        == ("full 9-bit $D011/$D012 high-to-low transition, never "
            "$D012 alone or the counter under test")
        and target["raster_lines"] == 312
        and target["raster_start_phases"] == 312
        and target["synchronization_wraps"] == 1
        and target["required_progress_deltas"] == 3
        and target["required_delta_per_wrap"] == 1
        and host_contract["execution_witnesses"] == 3
        and host_contract["complete_raster_sequence_lines"] == 312
        and host_contract["phase_matrix_passes"] == 312
        and host_contract["low_byte_oracle_phase_matrix_passes"] == 0,
        "Ship boot-inheritance contract identity drift",
    )
    require("must not model the code assumption" in contract["gate_rule"]
            and "real 312-line 9-bit sequence" in contract["gate_rule"],
            "independent-oracle gate rule drift")
    shared_tokens = (
        "*(volatile uint8_t *)0xd012 = 0xffu;",
        "*(volatile uint8_t *)0xd011 &= 0x7fu;",
        "*(volatile uint8_t *)0xd019 = 0xffu;",
        "*(volatile uint8_t *)0xd01a = LISP65_RASTER_IRQ_ENABLE_MASK;",
        "*(volatile uint8_t *)0xd01a\n                     & LISP65_RASTER_IRQ_ENABLE_MASK",
    )
    require(all(token in shared for token in shared_tokens),
            "shared raster arm/readback sequence drift")
    require(workbench.count("lisp65_raster_timebase_arm();") == 1,
            "Workbench no longer consumes the shared raster arm sequence")

    for token in (
        "#define LISP65_SHIP_PROGRESS_DELTAS 3u",
        "if (!ship_reference_wrap()) return 0u;",
        "if (!ship_reference_wrap()) return 0u;\n    previous = ship_frame_read();",
        "for (sample = 0u; sample < LISP65_SHIP_PROGRESS_DELTAS; ++sample)",
        "if ((uint16_t)(current - previous) != 1u) return 0u;",
        "if ((previous & 0x100u) && !(current & 0x100u)) return 1u;",
        "volatile uint8_t *control = (volatile uint8_t *)0xd011;",
        "volatile uint8_t *raster = (volatile uint8_t *)0xd012;",
        "high_before = *control & 0x80u;",
        "high_after = *control & 0x80u;",
        "while (high_before != high_after);",
        "lisp65_ship_old_irq[0] = *(volatile uint8_t *)0x0314;",
        "*(volatile uint8_t *)0x0314 = (uint8_t)handler;",
        "&& *(volatile uint8_t *)0x0314 == (uint8_t)handler",
        "lisp65_raster_timebase_arm();",
        "if (!ship_timebase_armed()) {",
        "if (ship_frame_prove_progress()) return 1u;",
        "*value = lisp65_ship_frame_lo;",
        "*value = lisp65_ship_frame_hi;",
        "lisp65_ship_io_host_raster_step()",
        "event & LISP65_SHIP_HOST_RASTER_IRQ",
        "event & LISP65_SHIP_HOST_RASTER_MASK",
    ):
        require(token in ship, f"Ship repeated-progress seam drift: {token}")
    require("ship_jiffy" not in ship and "0x00a1" not in ship
            and "0x00a2" not in ship,
            "retired A1/A2 clock assumption reintroduced")

    for token in (
        "lda $d019", "and #$01", "sta $d019",
        "inc lisp65_ship_frame_lo",
        "inc lisp65_ship_frame_hi", "jmp (lisp65_ship_old_irq)",
    ):
        require(token in timebase, f"Ship IRQ counter/chain drift: {token}")
    require(timebase.count("pha") == 1 and timebase.count("pla") == 1,
            "Ship IRQ A preservation drift")

    for token in (
        "#define LISP65_SHIP_HOST_RASTER_MASK 0x01ffu",
        "#define LISP65_SHIP_HOST_RASTER_IRQ 0x8000u",
        "uint16_t lisp65_ship_io_host_raster_step(void);",
        "uint16_t lisp65_ship_io_host_frame_count(void);",
        "uint8_t lisp65_ship_io_host_verified_deltas(void);",
    ):
        require(token in header, f"Ship host oracle interface drift: {token}")
    require(builder.count('"products/runtime-core/ship_timebase.s"') == 1,
            "Ship target builder timebase ownership drift")

    init = runtime.index("if (!lisp65_ship_io_init())")
    error = runtime.index("lisp65_runtime_state = RUNTIME_IO_ERROR", init)
    loaded = runtime.index("lisp65_runtime_state = RUNTIME_LOADED")
    require(init < error < loaded and "RUNTIME_IO_ERROR = 0xe5" in runtime,
            "Runtime publishes LOADED before repeated-progress proof")

    for token in (
        "uint16_t lisp65_ship_io_host_raster_step(void)",
        "host_raster_line = (uint16_t)((host_raster_line + 1u) % 312u);",
        "lisp65_ship_io_host_verified_deltas() != 3u",
        "boot-armed=1 boot-verified=1 input-armed=1",
    ):
        require(token in host, f"runtime host oracle assertion drift: {token}")
    for token in (
        "ORACLE_ONE_SHOT", "ORACLE_STALLED", "ORACLE_RECURRING",
        "uint16_t lisp65_ship_io_host_raster_step(void)",
        "oracle_line = (uint16_t)((oracle_line + 1u) % 312u);",
        "if (oracle_line == 255u) event |= LISP65_SHIP_HOST_RASTER_IRQ;",
        "if (lisp65_ship_io_init() || lisp65_ship_io_host_clock_verified())",
        "oracle_reset(ORACLE_ONE_SHOT);\n    if (lisp65_ship_io_init() || "
        "lisp65_ship_io_host_clock_verified()) return 2;",
        "oracle_reset(ORACLE_STALLED);\n    if (lisp65_ship_io_init() || "
        "lisp65_ship_io_host_clock_verified()) return 3;",
        "lisp65_ship_io_host_verified_deltas() != 3u",
        "one-shot=reject stagnant=reject",
        "deltas=3 oracle-wraps=4", "executions=3",
    ):
        require(token in witness, f"independent host witness drift: {token}")
    require("*(volatile unsigned char *)0x91 == 0x7F"
            in INTERRUPT.read_text(encoding="utf-8"),
            "$91 RUN/STOP issue was silently folded into this fix")


def mutations(contract: dict[str, Any], shared: str, workbench: str,
              ship: str, timebase: str, header: str, runtime: str,
              builder: str, host: str, witness: str) -> dict[str, str]:
    rows: list[tuple[str, dict[str, Any], str, str, str, str, str, str, str,
                     str, str]] = []

    def add(label: str, *, c: dict[str, Any] | None = None,
            shared_m: str | None = None, workbench_m: str | None = None,
            ship_m: str | None = None, timebase_m: str | None = None,
            header_m: str | None = None, runtime_m: str | None = None,
            builder_m: str | None = None, host_m: str | None = None,
            witness_m: str | None = None) -> None:
        rows.append((label, c or contract, shared_m or shared,
                     workbench_m or workbench, ship_m or ship,
                     timebase_m or timebase, header_m or header,
                     runtime_m or runtime, builder_m or builder,
                     host_m or host, witness_m or witness))

    def replace(label: str, domain: str, old: str, new: str) -> None:
        value = {
            "shared": shared, "workbench": workbench, "ship": ship,
            "timebase": timebase, "header": header, "runtime": runtime,
            "builder": builder, "host": host, "witness": witness,
        }[domain]
        require(old in value, f"mutation anchor absent: {label}")
        add(label, **{domain + "_m": value.replace(old, new, 1)})

    changed = deepcopy(contract)
    changed["target"]["required_progress_deltas"] = 1
    add("contract-one-delta", c=changed)
    replace("raster-line-drift", "shared", "0xd012 = 0xffu", "0xd012 = 0xfeu")
    replace("workbench-private-arm", "workbench", "lisp65_raster_timebase_arm();", "")
    replace("ship-one-delta", "ship", "LISP65_SHIP_PROGRESS_DELTAS 3u",
            "LISP65_SHIP_PROGRESS_DELTAS 1u")
    replace("ship-accept-any-change", "ship",
            "if ((uint16_t)(current - previous) != 1u) return 0u;",
            "if (current == previous) return 0u;")
    replace("ship-no-sync-wrap", "ship",
            "if (!ship_reference_wrap()) return 0u;\n    previous = ship_frame_read();",
            "previous = ship_frame_read();")
    replace("ship-low-byte-only-oracle", "ship",
            "if ((previous & 0x100u) && !(current & 0x100u)) return 1u;",
            "if ((current & 0xffu) < (previous & 0xffu)) return 1u;")
    replace("ship-no-raster-high-bit", "ship", "0xd011", "0xd012")
    replace("ship-torn-raster-accepted", "ship",
            "while (high_before != high_after);", "while (0);" )
    replace("ship-self-referential-oracle", "ship", "0xd012", "0x00a1")
    replace("ship-no-vector-readback", "ship",
            "&& *(volatile uint8_t *)0x0314 == (uint8_t)handler", "")
    replace("ship-old-a1-low", "ship", "*value = lisp65_ship_frame_lo;",
            "*value = *(volatile uint8_t *)0x00a2;")
    replace("irq-no-low-tick", "timebase", "\tinc lisp65_ship_frame_lo\n", "")
    replace("irq-no-high-tick", "timebase", "\tinc lisp65_ship_frame_hi\n", "")
    replace("irq-no-owned-ack", "timebase", "\tsta $d019\n", "")
    replace("irq-no-kernal-chain", "timebase", "\tjmp (lisp65_ship_old_irq)", "\trts")
    replace("host-oracle-api-removed", "header",
            "uint16_t lisp65_ship_io_host_raster_step(void);", "")
    replace("runtime-loaded-before-proof", "runtime",
            "if (!lisp65_ship_io_init()) {",
            "lisp65_runtime_state = RUNTIME_LOADED;\n    if (!lisp65_ship_io_init()) {")
    replace("builder-omits-target-timebase", "builder",
            '        "products/runtime-core/ship_timebase.s",\n', "")
    replace("runtime-host-no-oracle", "host",
            "uint16_t lisp65_ship_io_host_raster_step(void)",
            "uint16_t removed_raster_step(void)")
    replace("witness-accepts-one-shot", "witness",
            "if (lisp65_ship_io_init() || lisp65_ship_io_host_clock_verified()) return 2;",
            "if (!lisp65_ship_io_init()) return 2;")
    replace("witness-drops-stalled-case", "witness",
            "oracle_reset(ORACLE_STALLED);", "oracle_reset(ORACLE_RECURRING);")

    rejected: dict[str, str] = {}
    for row in rows:
        label, c, shared_m, workbench_m, ship_m, timebase_m, header_m, \
            runtime_m, builder_m, host_m, witness_m = row
        try:
            validate(c, shared_m, workbench_m, ship_m, timebase_m, header_m,
                     runtime_m, builder_m, host_m, witness_m)
        except (GateError, ValueError) as error:
            rejected[label] = str(error)
        else:
            raise GateError(f"Ship boot-inheritance mutation survived: {label}")
    require(len(rejected) == 22, "boot-inheritance mutation count drift")
    return rejected


def execute_phase_matrix() -> dict[str, Any]:
    def run(start: int, low_only: bool) -> tuple[bool, int | None]:
        line = start
        previous_line = line
        counter = 0
        synchronized = False
        previous_counter = 0
        remaining = 3
        for _ in range(312 * 8):
            line = (line + 1) % 312
            if line == 255:
                counter += 1
            if low_only:
                boundary = (line & 0xff) < (previous_line & 0xff)
            else:
                boundary = bool(previous_line & 0x100) and not bool(line & 0x100)
            if boundary:
                if not synchronized:
                    synchronized = True
                    previous_counter = counter
                else:
                    delta = counter - previous_counter
                    if delta != 1:
                        return False, delta
                    previous_counter = counter
                    remaining -= 1
                    if remaining == 0:
                        return True, None
            previous_line = line
        raise GateError("bounded 9-bit raster phase execution did not terminate")

    complete = [run(start, False) for start in range(312)]
    low_only = [run(start, True) for start in range(312)]
    failures = Counter(delta for _, delta in low_only)
    require(all(passed for passed, _ in complete),
            "complete 9-bit raster oracle rejected a starting phase")
    require(all(not passed for passed, _ in low_only)
            and failures == Counter({0: 312}),
            "D012-low mutation did not fail 0/312 with delta zero")
    return {
        "status": "passed",
        "raster_lines": 312,
        "start_phases_executed": 312,
        "required_unit_deltas": 3,
        "full_9bit_high_to_low_passes": 312,
        "d012_low_decrease_passes": 0,
        "d012_low_decrease_rejections": 312,
        "d012_low_first_bad_delta_histogram": {"0": 312},
    }


def execute_host_witness() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="lisp65-ship-boot-") as raw:
        binary = Path(raw) / "ship-boot-host"
        process = subprocess.run([
            "cc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-Isrc",
            "scripts/ship-boot-inheritance-host-main.c",
            "products/runtime-core/ship_io.c", "-o", str(binary),
        ], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        require(process.returncode == 0,
                "host witness build red:\n" + process.stdout)
        process = subprocess.run([str(binary)], cwd=ROOT, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        expected = (
            "ship-boot-inheritance-host: PASS inherited=0 one-shot=reject "
            "stagnant=reject armed=1 verified=1 deltas=3 oracle-wraps=4 "
            "input=1 executions=3"
        )
        require(process.returncode == 0 and process.stdout.strip() == expected,
                "host witness execution red:\n" + process.stdout)
        return {
            "status": "passed", "executions": 3,
            "negative_executions": 2, "positive_executions": 1,
            "output": expected,
        }


def inspect_target_irq() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="lisp65-ship-timebase-") as raw:
        obj = Path(raw) / "ship-timebase.o"
        process = subprocess.run([
            str(COMPILER), "-Qunused-arguments", "-c", str(SHIP_TIMEBASE),
            "-o", str(obj),
        ], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        require(process.returncode == 0,
                "target IRQ object build red:\n" + process.stdout)
        truth = ElfTruth.read(obj, llvm_readobj=READOBJ,
                              include_section_data=True)
        handler = truth.symbol("lisp65_ship_timebase_irq")
        require(handler.section == ".text.lisp65_ship_timebase_irq"
                and handler.bytes == 23,
                "target IRQ handler symbol drift")
        body = truth.section_bytes(handler.section)
        require(body == bytes.fromhex(
            "48 ad 19 d0 29 01 f0 0b 8d 19 d0 ee 00 00 d0 03 ee 00 00 "
            "68 6c 00 00"),
            "target IRQ handler bytes drift")
        relocations = sorted(
            (row.offset, row.relocation_type, row.target)
            for row in truth.relocations
            if row.source_section == handler.section
        )
        require(relocations == [
            (12, "R_MOS_ADDR16", "lisp65_ship_frame_lo"),
            (17, "R_MOS_ADDR16", "lisp65_ship_frame_hi"),
            (21, "R_MOS_ADDR16", "lisp65_ship_old_irq"),
        ], "target IRQ relocation ownership drift")
        return {
            "status": "passed",
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
            "relocations": [
                {"offset": offset, "type": kind, "target": target}
                for offset, kind, target in relocations
            ],
        }


def main() -> int:
    try:
        contract = load(CONTRACT)
        shared = SHARED.read_text(encoding="utf-8")
        workbench = WORKBENCH.read_text(encoding="utf-8")
        ship = SHIP_IO.read_text(encoding="utf-8")
        timebase = SHIP_TIMEBASE.read_text(encoding="utf-8")
        header = SHIP_HEADER.read_text(encoding="utf-8")
        runtime = RUNTIME.read_text(encoding="utf-8")
        builder = BUILDER.read_text(encoding="utf-8")
        host = HOST_RUNNER.read_text(encoding="utf-8")
        witness_source = HOST_WITNESS.read_text(encoding="utf-8")
        validate(contract, shared, workbench, ship, timebase, header, runtime,
                 builder, host, witness_source)
        rejected = mutations(contract, shared, workbench, ship, timebase,
                             header, runtime, builder, host, witness_source)
        witness = execute_host_witness()
        phase_matrix = execute_phase_matrix()
        target_object = inspect_target_irq()
        value = {
            "format": "lisp65-c2.3-v1.3-ship-boot-inheritance-gate-v3",
            "recorded_on": date.today().isoformat(),
            "status": "passed-ship-owned-full-9bit-repeated-frame-clock",
            "promotable": False,
            "product_links": 0,
            "hardware_runs": 0,
            "host_execution": witness,
            "raster_phase_matrix": phase_matrix,
            "target_object_execution": target_object,
            "mutations_rejected": rejected,
            "mutation_count": len(rejected),
            "target_claim": (
                "source plus target IRQ object; complete Link-88 ELF and "
                "physical Ada+RETURN remain pending"
            ),
            "clock_contract": {
                "logical_surface": "$FF83/$FF84",
                "ship_backing": "private chained-raster-IRQ counter",
                "independent_oracle": "$D011/$D012 9-bit high-to-low wraps",
                "synchronization_wraps": 1,
                "verified_unit_deltas": 3,
                "one_shot_false_green": "rejected by executed negative case",
            },
            "out_of_scope": contract["out_of_scope"],
            "authority": {
                "contract": bind(CONTRACT),
                "shared_arm_sequence": bind(SHARED),
                "workbench_owner": bind(WORKBENCH),
                "ship_io": bind(SHIP_IO),
                "ship_timebase": bind(SHIP_TIMEBASE),
                "ship_header": bind(SHIP_HEADER),
                "runtime": bind(RUNTIME),
                "ship_builder": bind(BUILDER),
                "host_runner": bind(HOST_RUNNER),
                "host_witness": bind(HOST_WITNESS),
                "elf_truth": bind(ELF_TRUTH),
                "compiler": bind_tool(COMPILER),
                "llvm_readobj": bind_tool(READOBJ),
                "gate": bind(Path(__file__)),
            },
            "next_gate": "one Link 88 plus one physical Ada+RETURN acceptance row",
        }
        write(RECEIPT, value)
        print(
            "c2-ship-boot-inheritance-gate: PASS executions=3 "
            f"mutations={len(rejected)} target-object={target_object['bytes']} "
            "one-shot=reject stagnant=reject phases=312/312 "
            "low-byte=0/312 deltas=3 input=1"
        )
        return 0
    except (GateError, KeyError, OSError, ValueError,
            json.JSONDecodeError) as error:
        print(f"c2-ship-boot-inheritance-gate: FIRST RED: {error}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
