#!/usr/bin/env python3
"""Calibrate and price the v1.7 synchronous recovery-service-time seam.

This is deliberately a host-only study.  It consumes the sealed stopped-state
capture and the exact Session overlay package from that world, then compiles
stand-alone target micro-prototypes.  It never changes a product source or
invokes a product link.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import evidence_era as ERA  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
RUNTIME = ROOT / "src/c2_product_runtime.c"
OVERLAY = ROOT / "src/vm_runtime_overlay.c"
CRC_SOURCE = ROOT / "src/rtov_crc_mem.s"
SEALED = ROOT / (
    "build/c2.3/v1.7-comfort-abort-reentry-media-r1/canonical-product/final")
ELF = SEALED / "lisp65-c2-substitution-linked.prg.elf"
MANIFEST = SEALED / "runtime-overlays-session-final.json"
PACKAGE = SEALED / "runtime-overlays-session-final.bin"
PACKAGE_REGION1 = SEALED / "runtime-overlays-session-final-region1.bin"
CAPTURE = ROOT / (
    "build/c2.3/v1.7-comfort-abort-reentry-media-r1/device-session/"
    "contact-r1/abort-recovery-stall/capture.json")
STALL = ARCH / (
    "c2.3-v1.7-comfort-abort-reentry-repair-stall-attribution.json")
OUT = ARCH / "c2.3-v1.7-recovery-service-time-pricing-receipt.json"
CLANG = ROOT / "tools/llvm-mos/bin/mos-clang"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"

FORMAT = "lisp65-c2-v17-recovery-service-time-pricing-v1"
RECORDED_ON = "2026-08-27"
SEALING_COMMIT = "c61649f7"
RTOV_VMA = 0xC356
C2D_UNWIND_BASE = 50752
C2D_UNWIND_BYTES = 64
C2D_IMAGE_CAP = 64
C2D_ENTRY_CAP = 2048


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": len(raw), "sha256": sha(raw)}


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def u16(raw: bytes, offset: int) -> int:
    return int.from_bytes(raw[offset:offset + 2], "little")


def capture_rows() -> tuple[dict[str, Any], dict[str, bytes]]:
    value = json.loads(CAPTURE.read_text(encoding="utf-8"))
    rows = {row["name"]: bytes.fromhex(row["observed_hex"])
            for row in value["reads"]}
    required = {"bank0-zp-stack", "runtime-overlay-lifecycle",
                "c2-runtime-and-phase-scratch", "c2j"}
    require(required <= rows.keys(), "sealed capture range set drift")
    return value, rows


def slices() -> tuple[dict[int, dict[str, Any]], dict[int, bytes]]:
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows = {int(row["id"]): row for row in value["slices"]}
    packages = {0: PACKAGE.read_bytes(), 1: PACKAGE_REGION1.read_bytes()}
    for row in rows.values():
        package = packages[int(row["region_id"])]
        start, length = int(row["file_offset"]), int(row["file_size"])
        payload = package[start:start + length]
        require(len(payload) == length and sha(payload) == row["sha256"],
                f"Session slice payload drift: {row['name']}")
    return rows, packages


def payload(row: dict[str, Any], packages: dict[int, bytes]) -> bytes:
    package = packages[int(row["region_id"])]
    start, length = int(row["file_offset"]), int(row["file_size"])
    return package[start:start + length]


def crc16_and_instructions(raw: bytes) -> tuple[int, int, int]:
    """Model the emitted ``rtov_crc_mem`` instruction stream exactly.

    The count is dynamic 45GS02 instructions, not a wall-clock conversion.
    Transport, verifier execution and phase-body work are deliberately absent,
    so this is a strict lower bound on synchronous service.
    """
    crc = 0xFFFF
    instructions = 9  # argument/pointer setup and CRC initialization
    carry_bits = 0
    for index, value in enumerate(raw):
        remaining = len(raw) - index
        instructions += 3  # remaining test
        instructions += 3 + (1 if (remaining & 0xFF) == 0 else 0)
        instructions += 5  # byte fetch/xor and LDY #8
        crc ^= value << 8
        for _ in range(8):
            carry = bool(crc & 0x8000)
            crc = (crc << 1) & 0xFFFF
            instructions += 5  # ASL, ROL, BCC, DEY, BNE
            if carry:
                carry_bits += 1
                crc ^= 0x1021
                instructions += 6
        instructions += 2  # INW pointer; BRA outer
    instructions += 7  # final zero test and four-instruction return
    return crc, instructions, carry_bits


def point_trace(raw: bytes, byte_index: int, bit_index: int) -> dict[str, int]:
    """Return machine state at $22c5, after BCC and before DEY."""
    crc = 0xFFFF
    instructions = 9
    for index, value in enumerate(raw):
        remaining = len(raw) - index
        instructions += 3 + 3 + (1 if (remaining & 0xFF) == 0 else 0) + 5
        accumulator = value ^ (crc >> 8)
        low, high = crc & 0xFF, accumulator
        for bit in range(8):
            carry = bool(high & 0x80)
            word = (((high << 8) | low) << 1) & 0xFFFF
            low, high = word & 0xFF, word >> 8
            instructions += 3  # ASL, ROL, BCC reaches $22c5
            if carry:
                low ^= 0x21
                high ^= 0x10
                accumulator = high
                instructions += 6
            if index == byte_index and bit == bit_index:
                return {
                    "A": accumulator, "Y": 8 - bit,
                    "crc_low": low, "crc_high": high,
                    "pointer": RTOV_VMA + index,
                    "remaining": len(raw) - index - 1,
                    "instructions_to_pc": instructions,
                }
            instructions += 2  # DEY, BNE
        crc = (high << 8) | low
        instructions += 2
    raise PricingError("requested CRC point lies outside payload")


def baseline_model_route(rows: dict[int, dict[str, Any]],
                         packages: dict[int, bytes],
                         route: list[int]) -> dict[str, Any]:
    verifier = payload(rows[1], packages)
    total_bytes = 0
    total_instructions = 0
    calls = []
    for index in route:
        target = payload(rows[index], packages)
        verifier_crc, verifier_ins, _ = crc16_and_instructions(verifier)
        target_crc, target_ins, _ = crc16_and_instructions(target)
        require(verifier_crc == rows[1]["crc16"],
                "record-verifier CRC model drift")
        require(target_crc == rows[index]["crc16"],
                f"target CRC model drift: {rows[index]['name']}")
        total_bytes += len(verifier) + len(target)
        total_instructions += verifier_ins + target_ins
        calls.append({
            "slot": index, "name": rows[index]["name"],
            "record_verifier_crc_bytes": len(verifier),
            "target_crc_bytes": len(target),
            "crc_instruction_lower_bound": verifier_ins + target_ins,
        })
    return {
        "overlay_calls": len(route), "route": calls,
        "synchronous_crc_bytes": total_bytes,
        "crc_instruction_lower_bound": total_instructions,
        "excluded_from_lower_bound": [
            "physical MAP/CPU reads", "record-verifier execution",
            "phase-body execution", "wipes and call/return glue",
        ],
    }


def baseline_model(rows: dict[int, dict[str, Any]],
                   packages: dict[int, bytes]) -> dict[str, Any]:
    # The serial driver alternates the abort-control overlay with its selected
    # range.  For the empty stopped world the exact route is fixed by source:
    # validate/reconstruct, fronts, prepare, done.
    route = [46, 31, 32, 46, 25, 46, 30, 46]
    expected = [
        "c2-append-abort-control", "c2-append-journal-validate",
        "c2-append-journal-reconstruct", "c2-append-abort-control",
        "c2-append-roots-fronts", "c2-append-abort-control",
        "c2-append-journal-prepare", "c2-append-abort-control",
    ]
    require([rows[index]["name"] for index in route] == expected,
            "empty recovery route no longer names the sealed slot sequence")
    return baseline_model_route(rows, packages, route)


PROTOTYPES = r'''
typedef unsigned char u8;
typedef unsigned short u16;

struct price_runtime { u16 generation; u16 images_offset; };
extern u8 c2_stream_c2d_read(u16, void *, u16);
extern u8 c2_abort_driver_slow(void);

__attribute__((noinline, used, section(".text.price_a0")))
u8 price_empty_journal_derived(u8 *scratch) {
    u8 i;
    if (!c2_stream_c2d_read(50752u, scratch, 64u)) return 0u;
    for (i = 0u; i < 64u; ++i) if (scratch[i]) return 0u;
    return 1u;
}

/* Candidate A uses only bytes already owned by the exclusive phase scratch.
 * A zero C2J plus a valid no-transient front is a derived absence proof. */
__attribute__((noinline, used, section(".text.price_a")))
u8 price_quiescent_derived(const struct price_runtime *runtime, u8 *scratch) {
    u8 i;
    if (!c2_stream_c2d_read(50752u, scratch, 64u)) return 0u;
    for (i = 0u; i < 64u; ++i) if (scratch[i]) return 0u;
    if (!c2_stream_c2d_read(0u, scratch, 48u)) return 0u;
    if (scratch[0] != 'C' || scratch[1] != '2' || scratch[2] != 'D' ||
        scratch[3] || scratch[4] != 6u ||
        (u16)(scratch[8] | (u16)scratch[9] << 8) != 4096u ||
        (u16)(scratch[10] | (u16)scratch[11] << 8) != runtime->generation)
        return 0u;
    if (!c2_stream_c2d_read((u16)(runtime->images_offset + 63u * 32u),
                            scratch, 32u)) return 0u;
    return scratch[0] != 2u;
}

static u8 price_recovery_pending;
__attribute__((noinline, used, section(".text.price_b")))
void price_defer_recovery(void) { price_recovery_pending = 1u; }
__attribute__((noinline, used, section(".text.price_b")))
u8 price_service_deferred(void) {
    if (!price_recovery_pending) return 1u;
    price_recovery_pending = 0u;
    return c2_abort_driver_slow();
}

static u8 price_journal_active;
static u8 price_transient_depth;
__attribute__((noinline, used, section(".text.price_c")))
void price_mark_journal(u8 active) { price_journal_active = active; }
__attribute__((noinline, used, section(".text.price_c")))
void price_mark_transient_depth(u8 depth) { price_transient_depth = depth; }
__attribute__((noinline, used, section(".text.price_c")))
u8 price_ledger_quiescent(void) {
    return (u8)((price_journal_active | price_transient_depth) == 0u);
}
'''


def prototype_prices() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="c2-v17-recovery-price-") as raw:
        root = Path(raw)
        source, obj = root / "price.c", root / "price.o"
        source.write_text(PROTOTYPES, encoding="utf-8")
        result = subprocess.run(
            [str(CLANG), "-Os", "-mcpu=mos45gs02", "-c", str(source),
             "-o", str(obj)], cwd=ROOT, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        require(result.returncode == 0,
                "recovery pricing micro-compile red:\n" + result.stdout)
        truth = ElfTruth.read(obj, llvm_readobj=READOBJ)
        sizes = {name: truth.symbol(name).bytes for name in (
            "price_empty_journal_derived",
            "price_quiescent_derived", "price_defer_recovery",
            "price_service_deferred", "price_mark_journal",
            "price_mark_transient_depth", "price_ledger_quiescent")}
        state_sizes = {name: truth.symbol(name).bytes for name in (
            "price_recovery_pending", "price_journal_active",
            "price_transient_depth")}
    return {
        "compiler": bind(CLANG.resolve()), "compiler_entrypoint":
            CLANG.relative_to(ROOT).as_posix(),
        "exact_function_bytes": sizes,
        "candidate_a0_code_bytes": sizes["price_empty_journal_derived"],
        "candidate_a_code_bytes": sizes["price_quiescent_derived"],
        "candidate_a_state_bytes": 0,
        "candidate_b_code_bytes": (sizes["price_defer_recovery"]
                                   + sizes["price_service_deferred"]),
        "candidate_b_state_bytes": 1,
        "candidate_c_code_bytes": (sizes["price_mark_journal"]
                                   + sizes["price_mark_transient_depth"]
                                   + sizes["price_ledger_quiescent"]),
        "candidate_c_state_bytes": 2,
        "exact_state_bytes": state_sizes,
        "object_state_bytes": sum(state_sizes.values()),
        "scope": ("stand-alone target micro-prototypes; call-site, placement "
                  "and lifecycle integration remain implementation-card prices"),
    }


def quiescent_model(c2j: bytes, header: bytes, top_row: bytes,
                    generation: int) -> bool:
    if len(c2j) != 64 or len(header) != 48 or len(top_row) != 32:
        return False
    if any(c2j):
        return False
    if (header[0:4] != b"C2D\0" or header[4] != 6
            or u16(header, 8) != C2D_ENTRY_CAP * 2
            or u16(header, 10) != generation):
        return False
    return top_row[0] != 2


def mutation_gate(header: bytes, generation: int) -> list[dict[str, Any]]:
    zero_journal = bytes(64)
    empty_top = bytes(32)
    require(quiescent_model(zero_journal, header, empty_top, generation),
            "derived quiescent positive model red")
    cases = {
        "nonzero-final-C2J-byte":
            (zero_journal[:-1] + b"\x01", header, empty_top, generation),
        "transient-top-image-row":
            (zero_journal, header, b"\x02" + empty_top[1:], generation),
        "foreign-header-generation":
            (zero_journal, header, empty_top, generation + 1),
        "incomplete-C2J-population":
            (zero_journal[:-1], header, empty_top, generation),
    }
    rows = []
    for name, args in cases.items():
        require(not quiescent_model(*args), f"quiescence mutation survived: {name}")
        rows.append({"name": name, "result": "slow-path-required"})
    return rows


def derive() -> dict[str, Any]:
    stall = json.loads(STALL.read_text(encoding="utf-8"))
    require(stall["decoded_state"]["crc"] == {
        "current_pointer": "0xc650", "loaded_length": 1434,
        "remaining_length": 671}, "sealed stall statement drift")
    capture, observed = capture_rows()
    zp = observed["bank0-zp-stack"]
    phase = observed["c2-runtime-and-phase-scratch"]
    phase_base = 0xC084
    scratch_base = 0xC0C6 - phase_base
    record = phase[scratch_base + 182:scratch_base + 214]
    meta = phase[scratch_base + 214:scratch_base + 238]
    tail = phase[scratch_base + 238:scratch_base + 241]
    require(len(record) == 32 and len(meta) == 24 and len(tail) == 3,
            "phase scratch layout drift")
    require((record[0], record[31], meta[0:4], tail[0:2])
            == (0, 0, bytes((0, 31, 32, 0)), bytes((1, 1))),
            "sealed empty recovery state drift")
    require(observed["c2j"] == bytes(64), "sealed C2J is not empty")
    header = observed.get("c2d-header")
    require(header is not None and len(header) == 48,
            "sealed C2D header range absent")
    generation = u16(header, 10)

    manifest_rows, packages = slices()
    verifier = payload(manifest_rows[1], packages)
    require(len(verifier) == 1434, "record-verifier length drift")
    point = point_trace(verifier, 762, 1)
    cpu = {name: int(capture["tuple"][name], 16)
           for name in ("A", "PC", "Y")}
    machine = {
        "A": cpu["A"], "Y": cpu["Y"],
        "crc_low": zp[8], "crc_high": zp[9],
        "pointer": u16(zp, 6), "remaining": u16(zp, 4),
    }
    require(cpu["PC"] == 0x22C5, "sealed CRC PC drift")
    require(all(point[name] == machine[name] for name in machine),
            f"CRC model does not reproduce capture: {point} != {machine}")
    crc, full_instructions, carry_bits = crc16_and_instructions(verifier)
    require(crc == manifest_rows[1]["crc16"] == 0x00EF,
            "record-verifier full CRC drift")

    baseline = baseline_model(manifest_rows, packages)
    reduced = baseline_model_route(manifest_rows, packages, [25, 30])
    prototypes = prototype_prices()
    a_bytes = 144
    return {
        "format": FORMAT, "recorded_on": RECORDED_ON,
        "status": "GRADUATED: SEALED STALL REPRODUCED; THREE REPAIR SHAPES PRICED",
        "authority": {
            "commission": ERA.era_bind(SEALING_COMMIT, PLAN),
            "sealed_attribution": bind(STALL),
            "capture": bind(CAPTURE), "final_elf": bind(ELF),
            "session_manifest": bind(MANIFEST),
            "session_package": bind(PACKAGE),
            "session_region1_package": bind(PACKAGE_REGION1),
            "runtime_source": ERA.era_bind(SEALING_COMMIT, RUNTIME),
            "overlay_source": ERA.era_bind(SEALING_COMMIT, OVERLAY),
            "crc_source": ERA.era_bind(SEALING_COMMIT, CRC_SOURCE),
            "pricing_tool": ERA.era_bind(SEALING_COMMIT, Path(__file__)),
        },
        "graduation": {
            "journal": {"C2J_all_zero": True, "journal_result": record[31]},
            "transient_front_depth": record[0],
            "abort_plan": {"state": meta[0], "start": meta[1],
                           "end": meta[2], "done": meta[3]},
            "crc_machine_observed": machine,
            "crc_machine_model": point,
            "loaded_slice": {"id": 1, "name": manifest_rows[1]["name"],
                             "bytes": len(verifier), "crc16": crc,
                             "full_crc_instructions": full_instructions,
                             "carry_poly_iterations": carry_bits},
            "explanation": (
                "The remaining count is decremented before the byte is folded; "
                "the pointer advances only after all eight bits. At $22c5 the "
                "763rd byte is in bit two, so remaining=671 while pointer is "
                "$c356+762=$c650. A/Y and the live CRC pair also match exactly."),
        },
        "sealed_empty_path_cost": baseline,
        "emitted_micro_prices": prototypes,
        "quiescence_mutations": mutation_gate(header, generation),
        "candidates": {
            "A0_empty_journal_bypass": {
                "mechanism": (
                    "Derive all-zero C2J in exclusive phase scratch, bypass "
                    "validate/reconstruct and its control choreography, then "
                    "run the unchanged fronts and rollback-prepare phases."),
                "physical_bytes_read_before_branch": 64,
                "new_state_bytes": 0,
                "emitted_probe_bytes": prototypes["candidate_a0_code_bytes"],
                "remaining_overlay_calls": reduced["overlay_calls"],
                "remaining_crc_bytes": reduced["synchronous_crc_bytes"],
                "remaining_crc_instruction_lower_bound":
                    reduced["crc_instruction_lower_bound"],
                "reduction_percent": round(
                    100.0 * (1.0 - reduced["crc_instruction_lower_bound"] /
                             baseline["crc_instruction_lower_bound"]), 1),
                "verdict": (
                    "SMALL FALLBACK PRICE: safe and cheap, but still leaves "
                    "two indivisible overlay verifications on the prompt path"),
            },
            "A_empty_obligation_fast_path": {
                "mechanism": (
                    "Before the overlay serial driver, derive quiescence from "
                    "the complete zero C2J, the generation-bound header/front "
                    "watermark and the top transient image row. Reuse exclusive "
                    "phase scratch; uncertainty falls through to the slow path."),
                "physical_bytes_read_on_quiescent_abort": a_bytes,
                "physical_read_breakdown": {"C2J": 64, "header": 48,
                                            "top_image_row": 32},
                "new_state_bytes": 0,
                "emitted_probe_bytes": prototypes["candidate_a_code_bytes"],
                "quiescent_overlay_calls": 0,
                "quiescent_crc_bytes": 0,
                "authority_model": "born-derived; no shadow depth or dirty latch",
                "fallback": "unchanged serial driver on any nonzero/invalid read",
                "verdict": "WINNER: smallest service and no second state authority",
            },
            "B_deferred_existing_driver": {
                "mechanism": (
                    "Render the native prompt first and mark recovery pending; "
                    "an idle seam later invokes the unchanged serial driver."),
                "new_state_bytes": prototypes["candidate_b_state_bytes"],
                "emitted_scheduler_bytes": prototypes["candidate_b_code_bytes"],
                "synchronous_crc_bytes_after_prompt": baseline["synchronous_crc_bytes"],
                "crc_instruction_lower_bound_after_prompt":
                    baseline["crc_instruction_lower_bound"],
                "atomicity_problem": (
                    "one overlay call still contains an indivisible verifier "
                    "and payload CRC; deferral changes when the stall occurs, "
                    "not its service cost"),
                "verdict": "DOMINATED unless the overlay transport itself becomes resumable",
            },
            "C_resident_obligation_ledger": {
                "mechanism": (
                    "Maintain journal-active and transient-depth cells at every "
                    "publication/clear edge, allowing an O(1) quiescent return."),
                "new_state_bytes": prototypes["candidate_c_state_bytes"],
                "emitted_core_bytes": prototypes["candidate_c_code_bytes"],
                "quiescent_overlay_calls": 0,
                "quiescent_crc_bytes": 0,
                "integration_not_in_micro_price": (
                    "all writer edges, crash/failure stickiness, boot initialization "
                    "and a reconciliation proof against C2D"),
                "authority_problem": (
                    "duplicates the record-derived fronts that the v5 contract "
                    "deliberately made the sole authority"),
                "verdict": "FASTER-EQUAL BUT STRUCTURALLY DOMINATED BY A",
            },
        },
        "recommendation": {
            "candidate": "A_empty_obligation_fast_path",
            "implementation_card_required": True,
            "required_gates": [
                "quiescent proof consumes all 64 C2J bytes plus generation-bound header/front facts",
                "a nonzero C2J or a transient top row reaches the unchanged slow driver",
                "a read/identity failure reaches the slow driver, never the fast return",
                "final ELF proves the probe before the first overlay call",
            ],
            "not_authorized_here": "no product edit, WPLTO, link, medium or device contact",
        },
        "claim_limit": (
            "Reproduces the sealed machine state and prices three repair shapes. "
            "Micro-prices are exact emitted target bytes for the named cores; "
            "only an implementation card may price placement and integration."),
    }


def main() -> int:
    require(len(sys.argv) in {1, 2} and
            (len(sys.argv) == 1 or sys.argv[1] == "--check"),
            "usage: c2_v17_recovery_service_time_pricing.py [--check]")
    raw = canonical(derive())
    if len(sys.argv) == 2:
        require(OUT.is_file() and OUT.read_bytes() == raw,
                "recovery-service-time pricing receipt drift")
    else:
        OUT.write_bytes(raw)
    value = json.loads(raw)
    print("v1.7 recovery service time: GRADUATED "
          f"crc-bytes={value['sealed_empty_path_cost']['synchronous_crc_bytes']} "
          f"winner-bytes={value['candidates']['A_empty_obligation_fast_path']['emitted_probe_bytes']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PricingError, OSError, ValueError, KeyError,
            subprocess.CalledProcessError) as error:
        print(f"v1.7-recovery-service-time-pricing: FAIL: {error}",
              file=sys.stderr)
        raise SystemExit(1)
