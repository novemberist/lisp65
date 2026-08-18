#!/usr/bin/env python3
"""Preflight the commissioned 2.1 MAP-based CPU library reader.

This file deliberately stops before WPLTO.  It binds the two hardware facts,
models every admitted physical source domain independently of the target
implementation, assembles the real reader, proves its source-owner/route
closure, and prices the removed DMA amplification.  A later one-shot card is
the first product-shaped consumer of this preflight.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import re
import subprocess
import sys
import tempfile
from typing import Any
import zlib


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_lite_media_product as MEDIA  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
CONTRACT = ROOT / "config/c2-v21-cpu-transport-release-contract.json"
DEVICE = ARCH / "c2.3-v2.0-loading-libraries-progress-map-device-receipt.json"
GRANULARITY = ARCH / "c2.3-v2.0-convergence-granularity-review-receipt.json"
RECONCILIATION = ARCH / "c2.3-v2.0-cpu-transport-reconciliation-receipt.json"
RUNTIME = ROOT / "src/c2_product_runtime.c"
RUNTIME_H = ROOT / "src/c2_product_runtime.h"
DECODER = ROOT / "scripts/c2-stream-decoder.c"
READER = ROOT / "src/optional/c2_map_cpu_read.s"
PRODUCER = ROOT / "tools/host-lisp/c2_product_substitution_link.py"
MEDIA_BASE = ROOT / "tools/host-lisp/c2_lite_media_product.py"
RECEIPT = ARCH / "c2.3-v2.1-cpu-transport-preflight-receipt.json"
DRIVER = Path(__file__).resolve()

AUTHORIZATION = "149839fe"
RECORDED_ON = "2026-08-14"
FORMAT = "lisp65-c2.3-v2.1-cpu-transport-preflight-v1"
FEATURE = "LISP65_C2_MAP_CPU_TRANSPORT"
WINDOW_BASE = 0x4000
WINDOW_LIMIT = 0x6000
MAX_CALL_BYTES = 64
CPU_CLOCK_HZ = 40_000_000
FRAME_SECONDS = 0.02

SOURCE_DOMAINS = {
    "c2d-bank5": (0x00050000, 50816),
    "product-shelf-attic": (0x08100000, 93681),
    "session-attic": (0x08400000, 0x00100000),
}


class PreflightError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PreflightError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": digest(raw)}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().split()).lower()
    for token in (
            "cpu transport for the library load path",
            "all 346,298",
            "map-based cpu reader",
            "crc32_update",
            "every medium builder",
            "one card"):
        require(token in text, f"2.1 commission token absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": digest(raw)}


def hardware_gate(device_override: dict[str, Any] | None = None) -> dict[str, Any]:
    value = load(DEVICE) if device_override is None else device_override
    probe = value.get("probe", {})
    ring = value.get("progress_ring", {})
    require(
        value.get("status") == "TARGET-RESULT-BOUND"
        and probe.get("decision") == "MAP-CPU-BANK5-AND-ATTIC-TARGET-GREEN"
        and probe.get("bank5") == probe.get("attic") == "PASS"
        and probe.get("bank5_status") == probe.get("attic_status") == "0xa5"
        and ring.get("decision") == "FIXED"
        and ring.get("newest_counter") == 18
        and ring.get("expected_reads") == 346298
        and len(ring.get("slots_newest_first", [])) == 4
        and len({row["counter"] for row in ring["slots_newest_first"]}) == 1,
        "hardware MAP/ring authority drift")
    return {
        "status": "PASS: Bank-5 and Attic MAP CPU reads target-proven",
        "probe_reads": {"bank5": 256, "attic": 256},
        "probe_status": "0xa5/0xa5",
        "ring": {"counter": 18, "samples": 4,
                 "fixed_seconds": ring["fixed_observation_seconds"],
                 "final_pc": value["tuple"]["PC"],
                 "pc_interpretation": value["stopped_code_identity"]["interpretation"]},
        "claim_limit": value["claim_limit"],
    }


def map_tuple(physical: int) -> tuple[int, int, int, int]:
    """Return MB, MAP A/X and CPU pointer for an 8-KiB source window."""
    require(0 <= physical < 1 << 28, "physical source exceeds 28 bits")
    megabyte = physical >> 20
    in_mb = physical & 0xFFFFF
    window = in_mb & ~0x1FFF
    offset = (window - WINDOW_BASE) & 0xFFFFF
    map_a = (offset >> 8) & 0xFF
    map_x = 0x40 | ((offset >> 16) & 0x0F)
    pointer = WINDOW_BASE | (in_mb & 0x1FFF)
    return megabyte, map_a, map_x, pointer


def resolve(pointer: int, megabyte: int, map_a: int, map_x: int) -> int:
    mask = map_x >> 4
    block = pointer >> 13
    if pointer < 0x8000 and mask & (1 << block):
        offset = ((map_x & 0x0F) << 16) | (map_a << 8)
        return (megabyte << 20) | (((offset + pointer) & 0xFFFFF))
    return pointer


def range_model(domains_override: dict[str, tuple[int, int]] | None = None,
                *, maximum: int = MAX_CALL_BYTES) -> dict[str, Any]:
    domains = SOURCE_DOMAINS if domains_override is None else domains_override
    require(maximum == 64, "linked caller maximum is not the admitted 64 bytes")
    rows: dict[str, Any] = {}
    total_bytes = 0
    for name, (base, length) in domains.items():
        require(length > 0 and (base >> 20) == ((base + length - 1) >> 20),
                f"{name} crosses an unhandled megabyte selector")
        # Exhaustively prove every physical byte in the admitted domain maps
        # to itself through its independently derived tuple.
        for physical in range(base, base + length):
            mb, a, x, pointer = map_tuple(physical)
            require(resolve(pointer, mb, a, x) == physical,
                    f"{name} MAP resolution drift at {physical:#x}")
        starts = {base, base + length - 1}
        first_boundary = (base + 0x1FFF) & ~0x1FFF
        for boundary in range(first_boundary, base + length, 0x2000):
            starts.update({max(base, boundary - 64), max(base, boundary - 1), boundary})
        checked_reads = 0
        for start in sorted(starts):
            for size in (1, 2, 4, 8, 10, 16, 20, 24, 32, 48, 64):
                if start + size > base + length:
                    continue
                for delta in range(size):
                    physical = start + delta
                    mb, a, x, pointer = map_tuple(physical)
                    require(resolve(pointer, mb, a, x) == physical,
                            f"{name} boundary copy drift")
                checked_reads += 1
        rows[name] = {
            "base": f"0x{base:08x}", "bytes": length,
            "last": f"0x{base + length - 1:08x}",
            "megabyte": f"0x{base >> 20:02x}",
            "exhaustive_bytes_checked": length,
            "boundary_reads_checked": checked_reads,
        }
        total_bytes += length
    return {"status": "PASS: full source domains resolve through block-2 MAP",
            "mapped_cpu_block": 2, "mapped_window": "0x4000..0x5fff",
            "preserved_high_mask": "block-7 only", "maximum_call_bytes": maximum,
            "total_exhaustive_bytes_checked": total_bytes, "domains": rows}


def assemble_reader(source_override: str | None = None) -> dict[str, Any]:
    source = READER.read_text(encoding="utf-8") if source_override is None else source_override
    required_order = (
        "php", "sei", "map", "eom", "jsr .Lc2_cpu_map_window",
        "lda (__rc16),y", "sta (__rc4),y", ".Lc2_cpu_restore:",
        "plp", "lda #1", "rts")
    cursor = -1
    for token in required_order:
        position = source.find(token, cursor + 1)
        require(position >= 0, f"CPU-reader seam absent/out of order: {token}")
        cursor = position
    require(
        source.count("\tmap\n") == 5 and source.count("\teom\n") == 5
        and "\tldz #$80" in source and source.count("\tldz #0") >= 2
        and "\tldx #$0f" in source
        and "\tlda __rc7\n\tbne .Lc2_cpu_fail" in source
        and "cmp #$60" in source
        and all(token not in source.lower() for token in ("$d700", "$d701", "$d702", "$d703", "$d704", "$d705")),
        "CPU reader does not structurally close MAP/length/no-DMA rules")
    with tempfile.TemporaryDirectory(prefix="c2-v21-reader-") as raw:
        temporary = Path(raw)
        assembly = temporary / "reader.s"
        obj = temporary / "reader.o"
        assembly.write_text(source, encoding="utf-8")
        result = subprocess.run([
            str(ROOT / "tools/llvm-mos/bin/mos-mega65-clang"),
            "-c", "-mcpu=mos45gs02", str(assembly), "-o", str(obj),
        ], cwd=ROOT, text=True, stdout=subprocess.PIPE,
           stderr=subprocess.STDOUT, check=False)
        require(result.returncode == 0, f"real CPU reader did not assemble:\n{result.stdout}")
        truth = ElfTruth.read(
            obj, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
        used = truth.section(".text.c2_map_cpu_read").bytes
        require(0 < used <= 192, "CPU reader exceeds pre-card price ceiling")
    return {"status": "PASS: real reader assembles and closes synchronous MAP path",
            "section": ".text.c2_map_cpu_read", "object_bytes": used,
            "pre_card_ceiling_bytes": 192, "dma_register_references": 0,
            "interrupt_window": "PHP/SEI through full MAP restore/PLP"}


def route_gate(runtime_override: str | None = None,
               producer_override: str | None = None) -> dict[str, Any]:
    runtime = RUNTIME.read_text(encoding="utf-8") if runtime_override is None else runtime_override
    producer = PRODUCER.read_text(encoding="utf-8") if producer_override is None else producer_override
    feature_branch = "#ifdef LISP65_C2_MAP_CPU_TRANSPORT"
    call = "return c2_map_cpu_read("
    require(runtime.count(feature_branch) == 2 and runtime.count(call) == 2,
            "both library reader families must select the CPU transport")
    shelf = runtime[runtime.index("c2_stream_shelf_read"):runtime.index("c2_stream_c2d_read")]
    c2d = runtime[runtime.index("c2_stream_c2d_read"):runtime.index("c2_stream_c2d_write")]
    write_start = runtime.index("c2_stream_c2d_write")
    write = runtime[write_start:runtime.index(
        "#ifdef LISP65_C2_LITE_COLD_EVICTION", write_start)]
    require(
        shelf.index(feature_branch) < shelf.index("LISP65_CODE_WINDOW_CONVERGENCE")
        and c2d.index(feature_branch) < c2d.index("LISP65_CODE_WINDOW_CONVERGENCE")
        and "c2_map_cpu_read" not in write and "c2_facade_c2_dma" in write,
        "CPU read route leaked into DMA fallback or mutable C2D writes")
    require(
        '"name": "map-cpu-library-read"' in producer
        and f'"trigger": "{FEATURE}"' in producer
        and 'ROOT / "src/optional/c2_map_cpu_read.s"' in producer,
        "CPU feature/source owner scope is not explicit")
    base = PRODUCT.definitions({
        "product_build_id_hex": "0x00000000",
        "artifacts": {"shelf": {"bytes": 0}},
    })
    ordinary = PRODUCT.source_list()
    selected = PRODUCT.source_list((FEATURE,))
    ordinary_paths = {Path(row).resolve() for row in ordinary}
    selected_paths = {Path(row).resolve() for row in selected}
    require(
        FEATURE not in base and READER.resolve() not in ordinary_paths
        and READER.resolve() in selected_paths
        and len(selected_paths - ordinary_paths) == 1,
        "historical world or selected source-owner closure drift")
    scope = PRODUCT.source_owner_scope_gate(base, (FEATURE,), selected)
    return {"status": "PASS: exactly both immutable library readers use CPU MAP",
            "read_families": ["Shelf/Session", "C2D/Bank-5"],
            "write_families_changed": 0, "historical_worlds_changed": 0,
            "source_owner_scope": scope}


def crc32_branch(crc: int, raw: bytes) -> int:
    for byte in raw:
        crc ^= byte
        for _ in range(8):
            crc = ((crc >> 1) ^ 0xEDB88320) if crc & 1 else crc >> 1
    return crc & 0xFFFFFFFF


def crc32_mask(crc: int, raw: bytes) -> int:
    for byte in raw:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0xEDB88320 if crc & 1 else 0)
    return crc & 0xFFFFFFFF


def crc_gate(decoder_override: str | None = None) -> dict[str, Any]:
    source = DECODER.read_text(encoding="utf-8") if decoder_override is None else decoder_override
    require(
        source.count("#ifdef LISP65_C2_MAP_CPU_TRANSPORT") == 1
        and source.count("if (crc & 1u)") == 1
        and source.count("0xedb88320UL &") == 1,
        "feature-only CRC equivalent/historical expression closure drift")
    rng = random.Random(0xC221)
    vectors = [b"", b"123456789", bytes(range(32))]
    vectors.extend(bytes(rng.randrange(256) for _ in range(rng.randrange(65)))
                   for _ in range(64))
    for raw in vectors:
        initial = rng.randrange(1 << 32)
        require(crc32_branch(initial, raw) == crc32_mask(initial, raw),
                "branch CRC differs from the historical mask semantics")
        require((crc32_branch(0xFFFFFFFF, raw) ^ 0xFFFFFFFF)
                == (zlib.crc32(raw) & 0xFFFFFFFF),
                "both target CRC forms differ from authoritative zlib semantics")
    # The hot reader's largest admitted object is 64 bytes.  Even charging a
    # deliberately pessimistic 32 target instructions per bit plus setup is
    # less than one 20-ms frame at 40 MHz; the fixed 118-s ring therefore is
    # correlation with a sampled PC, not a defensible per-read CRC price.
    instructions = MAX_CALL_BYTES * 8 * 32 + 512
    seconds = instructions / CPU_CLOCK_HZ
    require(seconds < FRAME_SECONDS, "static CRC instruction ceiling exceeds one frame")
    return {
        "status": "PASS: CRC semantics identical; sampled PC is not a wall-cost proof",
        "vectors": len(vectors), "maximum_admitted_bytes": MAX_CALL_BYTES,
        "pessimistic_instruction_ceiling": instructions,
        "pessimistic_seconds_at_40MHz": seconds,
        "ring_attribution": "fixed state with final PC in crc32_update; no 6.5-s/read claim",
        "feature_shape": "branch form selected only in 2.1; historical expression retained",
    }


def workload_gate(granularity_override: dict[str, Any] | None = None) -> dict[str, Any]:
    value = load(GRANULARITY) if granularity_override is None else granularity_override
    unit = value.get("delivered_unit", {})
    require(
        unit.get("logical_reads") == 346298
        and unit.get("payload_bytes") == 1180781
        and unit.get("source_probe_dma_jobs") == 2361562
        and unit.get("possible_primary_dma_jobs") == 346298,
        "bound library workload/amplification drift")
    # Count target operations, not wall time: the probe proved correctness,
    # not a transferable cycle calibration.  The D1/ring repeat remains the
    # authority for the honest device duration.
    setup_instructions_per_call = 96
    copy_instructions_per_byte = 11
    crossing_instructions = 22
    crossings_upper = unit["logical_reads"]
    instruction_upper = (
        unit["logical_reads"] * setup_instructions_per_call
        + unit["payload_bytes"] * copy_instructions_per_byte
        + crossings_upper * crossing_instructions)
    return {
        "status": "PASS: all bound library reads move to synchronous CPU transport",
        "logical_reads_rerouted": unit["logical_reads"],
        "payload_bytes": unit["payload_bytes"],
        "probe_dma_jobs_removed": unit["source_probe_dma_jobs"],
        "possible_primary_dma_jobs_removed": unit["possible_primary_dma_jobs"],
        "remaining_DMA_write_calls": 4773,
        "structural_instruction_upper_bound": instruction_upper,
        "expected_device_seconds": None,
        "duration_authority": "fresh D1/progress-ring confirmation; MAP probe carried no timing",
    }


def media_closure_gate() -> dict[str, Any]:
    source = MEDIA_BASE.read_text(encoding="utf-8")
    require(
        "def close_packed_artifacts(" in source
        and "set(artifacts) == set(gates)" in source
        and "gates[name](artifacts[name])" in source,
        "common packed-artifact closure API is incomplete")
    device = load(DEVICE)
    missing = device.get("packed_stager_liveness", {})
    require(
        missing.get("result") == "ABSENT-IN-ACTUAL-PACKED-ELF"
        and "lacks the unique liveness-prefix" in missing.get("error", ""),
        "diagnostic-media closure First Red is not bound")
    with tempfile.TemporaryDirectory(prefix="c2-v21-packed-") as raw:
        path = Path(raw) / "artifact.bin"
        path.write_bytes(b"packed")
        result = MEDIA.close_packed_artifacts(
            {"artifact.bin": path},
            {"artifact.bin": lambda item: {
                "status": "PASS", "sha256": digest(item.read_bytes())}})
        rejected: list[str] = []
        for name, artifacts, gates in (
                ("omit-registered-gate", {"artifact.bin": path}, {}),
                ("gate-undelivered-artifact", {}, {"artifact.bin": lambda _p: {}})):
            try:
                MEDIA.close_packed_artifacts(artifacts, gates)
            except MEDIA.MediaError:
                rejected.append(name)
    require(result["complete"] is True
            and result["registered"] == result["executed"] == ["artifact.bin"]
            and rejected == ["omit-registered-gate", "gate-undelivered-artifact"],
            "packed-artifact closure completeness mutation survived")
    return {
        "status": "PASS: packed artifact gates are closure-owned for every successor builder",
        "historical_diagnostic_defect": "actual packed stager ELF omitted STAGING MEDIA",
        "successor_requirement": (
            "2.1 media builder passes the liveness opt-in and closes its actual packed ELF "
            "through MEDIA.close_packed_artifacts"),
        "common_API": result, "mutations_rejected": rejected,
    }


def validate(value: dict[str, Any]) -> None:
    require(value["hardware"]["probe_status"] == "0xa5/0xa5",
            "target transport proof weakened")
    require(value["range_model"]["mapped_cpu_block"] == 2
            and value["range_model"]["maximum_call_bytes"] == 64,
            "MAP range/destination contract weakened")
    require(value["reader"]["dma_register_references"] == 0,
            "CPU reader acquired a DMA completion seam")
    require(value["routing"]["write_families_changed"] == 0
            and value["routing"]["historical_worlds_changed"] == 0,
            "CPU route escaped immutable read-only candidate scope")
    require(value["workload"]["logical_reads_rerouted"] == 346298
            and value["workload"]["probe_dma_jobs_removed"] == 2361562,
            "2.1 workload no longer matches commissioned path")
    require(value["crc"]["ring_attribution"].endswith("no 6.5-s/read claim"),
            "single sampled PC promoted to a wall-cost claim")
    require(value["media_closure"]["common_API"]["complete"] is True
            and len(value["media_closure"]["mutations_rejected"]) == 2,
            "media closure completeness rule weakened")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Any] = {}
    for name, path, replacement in (
            ("lose-bank5-proof", ("hardware", "probe_status"), "0x00/0xa5"),
            ("map-wrong-cpu-block", ("range_model", "mapped_cpu_block"), 3),
            ("accept-wide-call", ("range_model", "maximum_call_bytes"), 255),
            ("add-DMA-to-cpu-reader", ("reader", "dma_register_references"), 1),
            ("change-write-family", ("routing", "write_families_changed"), 1),
            ("change-historical-world", ("routing", "historical_worlds_changed"), 1),
            ("drop-library-read", ("workload", "logical_reads_rerouted"), 346297),
            ("retain-probe-job", ("workload", "probe_dma_jobs_removed"), 2361561),
            ("promote-sampled-PC-to-price", ("crc", "ring_attribution"), "6.5 s/read")):
        candidate = deepcopy(value)
        parent = candidate
        for item in path[:-1]:
            parent = parent[item]
        parent[path[-1]] = replacement
        cases[name] = candidate
    candidate = deepcopy(value)
    candidate["media_closure"]["common_API"]["complete"] = False
    cases["omit-packed-artifact-closure"] = candidate
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            validate(candidate)
        except PreflightError:
            rejected.append(name)
    require(rejected == list(cases), "semantic preflight mutation survived")

    source_cases: dict[str, tuple[str | None, str | None]] = {
        "drop-shelf-cpu-route": (RUNTIME.read_text().replace(
            "#ifdef LISP65_C2_MAP_CPU_TRANSPORT", "#if 0", 1), None),
        "drop-c2d-cpu-route": (RUNTIME.read_text().replace(
            "#ifdef LISP65_C2_MAP_CPU_TRANSPORT", "#if 0", 2), None),
        "cpu-route-C2D-write": (RUNTIME.read_text().replace(
            "c2_facade_c2_dma((uint16_t)(uintptr_t)src, 0u,",
            "c2_map_cpu_read((uint32_t)(uintptr_t)src, (uint8_t *)dst,", 1), None),
        "drop-source-owner": (None, PRODUCER.read_text().replace(
            '    "sources": (ROOT / "src/optional/c2_map_cpu_read.s",),\n',
            '    "sources": (),\n', 1)),
    }
    for name, (runtime, producer) in source_cases.items():
        try:
            route_gate(runtime, producer)
        except (PreflightError, RuntimeError):
            rejected.append(name)
    assembly = READER.read_text(encoding="utf-8")
    for name, candidate in {
            "drop-SEI": assembly.replace("\tsei\n", "", 1),
            "drop-MAP-restore": assembly.replace(".Lc2_cpu_restore:\n", "", 1),
            "accept-high-length": assembly.replace(
                "\tlda __rc7\n\tbne .Lc2_cpu_fail\n", "", 1),
    }.items():
        try:
            assemble_reader(candidate)
        except PreflightError:
            rejected.append(name)
    expected = [*cases, *source_cases, "drop-SEI", "drop-MAP-restore",
                "accept-high-length"]
    require(rejected == expected, "2.1 mutation accounting drift")
    return rejected


def derive() -> dict[str, Any]:
    value = {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "HOST-GREEN; ONE-PRODUCT-CARD-NOT-YET-RUN",
        "authority": {
            "commission": authority(), "contract": bind(CONTRACT),
            "device": bind(DEVICE), "granularity": bind(GRANULARITY),
            "reconciliation": bind(RECONCILIATION), "runtime": bind(RUNTIME),
            "runtime_header": bind(RUNTIME_H), "decoder": bind(DECODER),
            "reader": bind(READER), "producer": bind(PRODUCER), "driver": bind(DRIVER),
            "media_base": bind(MEDIA_BASE),
        },
        "hardware": hardware_gate(),
        "range_model": range_model(),
        "reader": assemble_reader(),
        "routing": route_gate(),
        "workload": workload_gate(),
        "crc": crc_gate(),
        "media_closure": media_closure_gate(),
        "execution_accounting": {"WPLTO_runs": 0, "product_links": 0,
                                 "device_contacts": 0},
        "next": "run exactly one Link-107 product card under producer discipline",
        "claim_limit": (
            "Host preflight proves routing, MAP arithmetic, full admitted source domains, "
            "no-DMA transport shape and workload removal. The MAP hardware receipt proves "
            "the tested Bank-5/Attic transport form, not a wall-time. No product, media, "
            "boot or release claim exists before the one card and D1."),
    }
    validate(value)
    value["mutations_rejected"] = mutations(value)
    return value


def main() -> int:
    value = derive()
    RECEIPT.write_bytes(canonical(value))
    print("2.1 CPU transport: PREFLIGHT PASS "
          f"reads={value['workload']['logical_reads_rerouted']} "
          f"probe-jobs-removed={value['workload']['probe_dma_jobs_removed']} "
          f"reader={value['reader']['object_bytes']}B "
          f"mutations={len(value['mutations_rejected'])} card=0/1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
