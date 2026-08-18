#!/usr/bin/env python3
"""Price the Link-106 LOADING LIBRARIES interval from bound artifacts.

This is a desk-only classifier.  It deliberately distinguishes an exact
workload count from a device-time price: a timeout is a correctness envelope,
not a measured mean, and the historical two-byte vm_dma cost is not portable
to the mapped convergence service without a path-equivalence proof.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
CARD = ARCH / "c2.3-v2.0-phase02b-header-consumption-replacement-card-receipt.json"
D1_RED = ARCH / "c2.3-v2.0-phase02b-header-consumption-d1-first-red-receipt.json"
CONVERGENCE = ROOT / "config/c2-f018b-content-safe-read-contract.json"
ORACLE = ROOT / "config/c2-v20-source-authoritative-oracle-contract.json"
TWO_BYTE = ARCH / "c2.2-v1.2.2-g2-symbol-value-cost-preparation-receipt.json"
RECEIPT = ARCH / "c2.3-v2.0-loading-libraries-duration-pricing-receipt.json"
DRIVER = Path(__file__).resolve()

AUTHORIZATION = "c049bb66"
RECORDED_ON = "2026-08-13"
FORMAT = "lisp65-c2.3-v2.0-loading-libraries-duration-pricing-v1"
BUILD = ROOT / "build/c2.3/v2.0-phase02b-header-consumption-replacement-card"
SHELF = BUILD / "static-plane/narrow-static/product/product-shelf-v4-direct.bin"
C2D = BUILD / "static-plane/narrow-static/v6-semantics/initial.c2d-v6.bin"
DECODER = BUILD / "wplto/generated-product-sources/c2-stream-decoder.c"
V2_DECODER = BUILD / "wplto/generated-product-sources/c2-stream-v2-decoder.c"
RUNTIME = BUILD / "wplto/generated-product-sources/c2_product_runtime.c"
MAPPED = ROOT / "src/c2_mapped_far_convergence.s"


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def git_authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{AUTHORIZATION}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    text = " ".join(raw.decode().split()).lower()
    require("loading libraries phase" in text
            and "desk classification commissioned" in text
            and "implausibly high" in text
            and "progress witness" in text,
            "LOADING LIBRARIES pricing authority drift")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def u16(raw: bytes, offset: int) -> int:
    return int.from_bytes(raw[offset:offset + 2], "little")


def u24(raw: bytes, offset: int) -> int:
    return int.from_bytes(raw[offset:offset + 3], "little")


@dataclass
class Traffic:
    shelf_calls: int = 0
    shelf_bytes: int = 0
    c2d_calls: int = 0
    c2d_bytes: int = 0
    c2d_write_calls: int = 0
    c2d_write_bytes: int = 0
    allocations: int = 0
    other: dict[str, int] = field(default_factory=dict)

    def shelf(self, length: int, calls: int = 1) -> None:
        self.shelf_calls += calls
        self.shelf_bytes += length

    def c2d(self, length: int, calls: int = 1) -> None:
        self.c2d_calls += calls
        self.c2d_bytes += length

    def write(self, length: int, calls: int = 1) -> None:
        self.c2d_write_calls += calls
        self.c2d_write_bytes += length

    def add(self, other: "Traffic") -> None:
        for name in ("shelf_calls", "shelf_bytes", "c2d_calls", "c2d_bytes",
                     "c2d_write_calls", "c2d_write_bytes", "allocations"):
            setattr(self, name, getattr(self, name) + getattr(other, name))
        for name, value in other.other.items():
            self.other[name] = self.other.get(name, 0) + value

    def result(self) -> dict[str, Any]:
        return {
            "shelf": {"converged_calls": self.shelf_calls,
                      "payload_bytes": self.shelf_bytes},
            "c2d": {"converged_calls": self.c2d_calls,
                    "payload_bytes": self.c2d_bytes,
                    "write_calls": self.c2d_write_calls,
                    "write_bytes": self.c2d_write_bytes},
            "heap_allocations": self.allocations,
            "other": dict(sorted(self.other.items())),
        }


@dataclass(frozen=True)
class Image:
    ordinal: int
    code: int
    code_bytes: int
    metadata: int
    metadata_bytes: int
    entries: tuple[bytes, ...]
    descriptors: tuple[bytes, ...]
    pool: bytes
    pool_offset: int
    string_records: tuple[tuple[int, int], ...]


def parse_images() -> tuple[bytes, bytes, tuple[Image, ...]]:
    shelf = SHELF.read_bytes()
    c2d = C2D.read_bytes()
    require(len(shelf) == 93681 and shelf[:7] == b"L65S\x04\x20\x20",
            "Link-106 Shelf identity/shape drift")
    require(len(c2d) == 33840 and c2d[:8] == b"C2D\0\x06\x30\x20\x0a",
            "Link-106 C2D identity/shape drift")
    require(u16(c2d, 12) == 6 and u16(c2d, 16) == 755
            and u16(c2d, 20) == 2929 and u16(c2d, 24) == 352
            and u16(c2d, 28) == 48 and u16(c2d, 30) == 2096
            and u16(c2d, 32) == 22576 and u16(c2d, 34) == 30768,
            "Link-106 C2D geometry drift")
    images: list[Image] = []
    entry_first = resolution_first = 0
    for ordinal in range(6):
        srow = shelf[32 + ordinal * 32:64 + ordinal * 32]
        drow = c2d[48 + ordinal * 32:80 + ordinal * 32]
        code = u24(srow, 8); code_bytes = u16(srow, 11)
        metadata = u24(srow, 13); metadata_bytes = u16(srow, 16)
        header = shelf[metadata:metadata + 24]
        entry_count = u16(header, 10); descriptor_count = u16(header, 12)
        entry_offset = u16(header, 14); descriptor_offset = u16(header, 16)
        pool_offset = u16(header, 18); pool_bytes = u16(header, 20)
        require(drow[2] == ordinal and u16(drow, 6) == entry_first
                and u16(drow, 8) == entry_count
                and u16(drow, 10) == resolution_first
                and u16(drow, 12) == descriptor_count
                and u16(drow, 21) == code_bytes,
                f"image {ordinal} C2D/Shelf cross-binding drift")
        entries = tuple(
            shelf[metadata + entry_offset + i * 16:
                  metadata + entry_offset + (i + 1) * 16]
            for i in range(entry_count))
        descriptors = tuple(
            shelf[metadata + descriptor_offset + i * 8:
                  metadata + descriptor_offset + (i + 1) * 8]
            for i in range(descriptor_count))
        pool = shelf[metadata + pool_offset:metadata + pool_offset + pool_bytes]
        records: list[tuple[int, int]] = []
        cursor = 0
        while cursor < len(pool):
            length = u16(pool, cursor)
            require(cursor + 2 + length <= len(pool),
                    f"image {ordinal} string pool truncated")
            records.append((cursor, length))
            cursor += 2 + length
        require(cursor == len(pool) and all(len(row) in (8, 16) for row in (*entries, *descriptors)),
                f"image {ordinal} metadata domain drift")
        images.append(Image(ordinal, code, code_bytes, metadata, metadata_bytes,
                            entries, descriptors, pool, pool_offset,
                            tuple(records)))
        entry_first += entry_count
        resolution_first += descriptor_count
    require(entry_first == 755 and resolution_first == 2929,
            "parsed cursor totals drift")
    return shelf, c2d, tuple(images)


def chunks(length: int, width: int) -> int:
    return (length + width - 1) // width


def image_read(t: Traffic) -> None:
    t.c2d(32)
    t.shelf(32)


def image_base(t: Traffic, image: Image) -> None:
    image_read(t)
    t.shelf(24)
    for _ in image.descriptors:
        t.shelf(8)


def string_record(t: Traffic, image: Image, wanted: int) -> int:
    for index, (offset, length) in enumerate(image.string_records):
        t.shelf(2)
        if offset == wanted:
            return length
    raise PricingError(f"image {image.ordinal} string offset absent: {wanted}")


def string_payload(t: Traffic, length: int, repeats: int = 1) -> None:
    for _ in range(repeats):
        left = length
        while left:
            n = min(16, left)
            t.shelf(n)
            left -= n


def decoder_workload(images: tuple[Image, ...]) -> tuple[dict[str, Traffic], dict[str, int]]:
    phases: dict[str, Traffic] = {}

    def phase(name: str) -> Traffic:
        phases[name] = Traffic()
        return phases[name]

    phase("00").c2d(48)
    phase("00b").c2d(48)
    p = phase("01"); p.shelf(32); p.shelf(192, 6)
    p = phase("02a-source-authoritative")
    p.other["record_reads"] = 18; p.other["record_bytes"] = 576
    p = phase("02b")
    for _ in images: p.c2d(5)

    p = phase("03")
    for image in images:
        p.shelf(32)
        for _ in range(2):
            p.shelf(image.code_bytes, chunks(image.code_bytes, 32))
            p.shelf(image.metadata_bytes, chunks(image.metadata_bytes, 32))

    p = phase("03b")
    for image in images:
        p.shelf(32)
        p.other["bank2_stage_calls"] = p.other.get("bank2_stage_calls", 0) + 1
        p.other["bank2_stage_bytes"] = p.other.get("bank2_stage_bytes", 0) + image.code_bytes
        p.other["minimum_bank2_crc_reads"] = p.other.get("minimum_bank2_crc_reads", 0) + chunks(image.code_bytes, 32)
        p.other["minimum_bank2_crc_bytes"] = p.other.get("minimum_bank2_crc_bytes", 0) + image.code_bytes

    p = phase("04")
    for image in images: image_read(p); p.shelf(24)

    p = phase("05a")
    for image in images:
        image_read(p); p.shelf(24)
        for _ in image.entries: p.shelf(16)

    p = phase("05b")
    for image in images:
        image_read(p); p.c2d(32); p.shelf(24)
        for _ in image.entries: p.shelf(16); p.c2d(10)

    p = phase("06a")
    for image in images:
        image_read(p); p.shelf(24)
        for entry in image.entries:
            p.shelf(16); p.shelf(7)
            literal_bytes = 2 * entry[7]
            if literal_bytes: p.shelf(literal_bytes, chunks(literal_bytes, 16))

    p = phase("06b")
    for image in images:
        image_read(p); p.shelf(24)
        for entry in image.entries:
            p.shelf(16)
            wanted = u16(entry, 8)
            if wanted != 0xffff:
                length = string_record(p, image, wanted)
                string_payload(p, length)

    p = phase("07")
    for image in images:
        image_base(p, image)
        for descriptor in image.descriptors:
            if descriptor[0] in (3, 7): p.write(2)

    p = phase("08")
    for image in images:
        image_base(p, image)
        for descriptor in image.descriptors:
            if descriptor[0] not in (3, 5, 7, 8): p.write(2)

    p = phase("09")
    for image in images:
        image_base(p, image)
        for descriptor in image.descriptors:
            if descriptor[0] == 3:
                length = string_record(p, image, u24(descriptor, 4))
                require(length == u16(descriptor, 2), "kind-3 string length drift")
                string_payload(p, length)
                p.c2d(2); p.write(2); p.allocations += 1

    p = phase("10")
    for image in images:
        image_base(p, image)
        for descriptor in image.descriptors:
            if descriptor[0] in (5, 8):
                length = string_record(p, image, u24(descriptor, 4))
                require(length == u16(descriptor, 2), "kind-5/8 string length drift")
                string_payload(p, length, 2)
                p.write(2)

    p = phase("11a")
    for image in images: image_base(p, image)

    p = phase("11b")
    for image in images:
        image_base(p, image)
        for descriptor in image.descriptors:
            if descriptor[0] != 7: continue
            for local in (u16(descriptor, 2), u24(descriptor, 4)):
                p.c2d(2)
                if image.descriptors[local][0] in (3, 7): p.c2d(2)
            p.c2d(2); p.write(2); p.allocations += 1

    p = phase("12")
    for image in images:
        image_base(p, image)
        for descriptor in image.descriptors:
            p.c2d(2)
            if descriptor[0] in (3, 7): p.c2d(2)

    total = Traffic()
    for value in phases.values(): total.add(value)
    expected = {
        "shelf_calls": 334739, "shelf_bytes": 1056299,
        "c2d_calls": 5144, "c2d_bytes": 18778,
        "c2d_write_calls": 3281, "c2d_write_bytes": 6562,
        "allocations": 352,
    }
    for name, value in expected.items():
        require(getattr(total, name) == value,
                f"decoder workload drift: {name}={getattr(total, name)} != {value}")
    return phases, expected


def publication_workload(images: tuple[Image, ...]) -> tuple[dict[str, Traffic], dict[str, int]]:
    phases: dict[str, Traffic] = {}
    named: list[int] = []

    scan = phases["publish-plan-scan"] = Traffic()
    for image in images:
        for entry in image.entries:
            scan.c2d(10); image_read(scan); scan.shelf(24); scan.shelf(16)
            wanted = u16(entry, 8)
            if wanted == 0xffff: continue
            length = next((length for offset, length in image.string_records
                           if offset == wanted), None)
            require(length is not None, "publish name absent from string pool")
            scan.shelf(2); scan.write(8); named.append(int(length))

    resolve = phases["publish-plan-resolve"] = Traffic()
    for length in named:
        resolve.c2d(8); string_payload(resolve, length); resolve.write(8)

    header = phases["publish-header"] = Traffic()
    header.c2d(64); header.write(48); header.c2d(48)

    exports = phases["publish-exports"] = Traffic()
    for _ in named:
        exports.c2d(8); exports.c2d(8); exports.write(4)
    exports.allocations = 1  # the single exported macro in this candidate

    total = Traffic()
    for value in phases.values(): total.add(value)
    expected = {
        "named_entries": 497, "name_bytes": 6600, "name_chunks": 650,
        "shelf_calls": 3412, "shelf_bytes": 61954,
        "c2d_calls": 3003, "c2d_bytes": 43750,
        "c2d_write_calls": 1492, "c2d_write_bytes": 9988,
        "allocations": 1,
    }
    observed = {
        "named_entries": len(named), "name_bytes": sum(named),
        "name_chunks": sum(chunks(length, 16) for length in named),
        "shelf_calls": total.shelf_calls, "shelf_bytes": total.shelf_bytes,
        "c2d_calls": total.c2d_calls, "c2d_bytes": total.c2d_bytes,
        "c2d_write_calls": total.c2d_write_calls,
        "c2d_write_bytes": total.c2d_write_bytes,
        "allocations": total.allocations,
    }
    require(observed == expected, f"publication workload drift: {observed}")
    return phases, expected


def source_contract() -> dict[str, Any]:
    runtime = RUNTIME.read_text(encoding="utf-8")
    decoder = DECODER.read_text(encoding="utf-8")
    v2 = V2_DECODER.read_text(encoding="utf-8")
    mapped = MAPPED.read_text(encoding="utf-8")
    required = {
        "libraries-marker-before-phase00": "LISP65_BOOT_PROGRESS_LIBRARIES();" in decoder,
        "cold-decode-before-publication": "if (!c2_decode_from(&c2_runtime, 0u)) return 0;" in runtime,
        "ready-publish-last": "c2_ready = 1;" in runtime,
        "shelf-uses-convergence": "return c2_physical_read_converged(base + offset" in runtime,
        "c2d-uses-convergence": "return vm_code_load_converged(" in runtime,
        "source-probe-per-byte": ".Lc2_d700_scan:" in mapped and ".Lc2_d705_scan:" in mapped,
        "source-probe-timeout-64": ".equ C2_TIMEOUT_FRAMES, 64" in mapped,
        "split-phases-present": all(token in decoder + v2 for token in (
            "c2_stream_phase_05a", "c2_stream_phase_05b",
            "c2_stream_phase_06a", "c2_stream_phase_06b",
            "c2_stream_phase_11a", "c2_stream_phase_11b")),
        "publication-plan-ordered": all(token in runtime for token in (
            "LISP65_C2_APPEND_PUBLISH_PLAN_SCAN_SLOT",
            "LISP65_C2_APPEND_PUBLISH_PLAN_RESOLVE_SLOT",
            "LISP65_C2_APPEND_HEADER_SLOT",
            "LISP65_C2_APPEND_PUBLISH_EXPORTS_SLOT")),
    }
    require(all(required.values()), f"linked source contract drift: {required}")
    return required


def timing_authorities() -> dict[str, Any]:
    oracle = load(ORACLE)
    hardware = ROOT / oracle["timeout_pricing"]["hardware_receipt"]
    timing = load(hardware)
    hz = float(timing["M4_time"]["frames_per_second"])
    known = int(oracle["timeout_pricing"]["known_boot_cold_convergence_ms"])
    margin = int(oracle["timeout_pricing"]["named_margin_ms"])
    timeout = int(oracle["timeout_pricing"]["selected_frames"])
    require(48 <= hz <= 52 and known == 714 and margin == 500 and timeout == 64,
            "timing authority drift")
    two = load(TWO_BYTE)
    scope = two["measurement"]["cost_constant_applicability"]
    require("one-byte c2_stream_c2d_read" in " ".join(scope["reference_only_not_directly_multipliable"])
            and "only for counted 2-byte vm_dma reads" in scope["R2_rule"],
            "two-byte non-transferability authority drift")
    return {"hardware": bind(hardware), "frames_per_second": hz,
            "timeout_frames": timeout, "known_boot_cold_convergence_ms": known,
            "named_margin_ms": margin, "two_byte_scope": bind(TWO_BYTE),
            "two_byte_path_equivalence": False}


def policy_gate(policy: dict[str, Any]) -> None:
    require(not policy["inherit_45_second_window"],
            "historical 45-second observation promoted to current timing bound")
    require(not policy["multiply_two_byte_vm_dma_cost"],
            "non-equivalent two-byte vm_dma cost multiplied into convergence path")
    require(policy["include_publication"], "post-decode publication omitted")
    require(policy["count_source_probe_per_payload_byte"],
            "convergence reduced to API-call count")
    require(not policy["authorize_fixed_wait_only_contact"],
            "fixed wait-only contact authorized without an operational bound")
    require(policy["require_progress_witness"], "implausibly high exit lacks witness")
    require(policy["witness_target_side"], "observer-side witness reintroduces crossing")
    require(policy["witness_phase_and_ordinal"],
            "counter-only witness cannot name the dominant phase/ordinal")


def mutations(policy: dict[str, Any]) -> list[str]:
    cases = {
        "inherit-old-45-second-window": ("inherit_45_second_window", True),
        "multiply-historical-two-byte-cost": ("multiply_two_byte_vm_dma_cost", True),
        "omit-publication": ("include_publication", False),
        "count-calls-not-byte-probes": ("count_source_probe_per_payload_byte", False),
        "authorize-another-fixed-wait": ("authorize_fixed_wait_only_contact", True),
        "drop-progress-witness": ("require_progress_witness", False),
        "external-progress-sampling": ("witness_target_side", False),
        "counter-without-phase-ordinal": ("witness_phase_and_ordinal", False),
    }
    rejected = []
    for name, (field, value) in cases.items():
        mutant = deepcopy(policy); mutant[field] = value
        try:
            policy_gate(mutant)
        except PricingError:
            rejected.append(name)
        else:
            raise PricingError(f"mutation survived: {name}")
    return rejected


def build_receipt() -> dict[str, Any]:
    card = load(CARD)
    shelf, c2d, images = parse_images()
    require(card["artifacts_after"]["elf"]["sha256"]
            == "339c52c08236cffc827834d6806150a0526b2ef840cba2ddae9217837c6f6af5",
            "Link-106 card identity drift")
    source = source_contract()
    decoder_phases, decoder_totals = decoder_workload(images)
    publish_phases, publish_totals = publication_workload(images)
    timing = timing_authorities()

    aggregate = {
        "shelf_calls": decoder_totals["shelf_calls"] + publish_totals["shelf_calls"],
        "shelf_bytes": decoder_totals["shelf_bytes"] + publish_totals["shelf_bytes"],
        "c2d_calls": decoder_totals["c2d_calls"] + publish_totals["c2d_calls"],
        "c2d_bytes": decoder_totals["c2d_bytes"] + publish_totals["c2d_bytes"],
        "c2d_write_calls": decoder_totals["c2d_write_calls"] + publish_totals["c2d_write_calls"],
        "c2d_write_bytes": decoder_totals["c2d_write_bytes"] + publish_totals["c2d_write_bytes"],
    }
    require(aggregate == {
        "shelf_calls": 338151, "shelf_bytes": 1118253,
        "c2d_calls": 8147, "c2d_bytes": 62528,
        "c2d_write_calls": 4773, "c2d_write_bytes": 16550,
    }, f"aggregate workload drift: {aggregate}")
    converged_calls = aggregate["shelf_calls"] + aggregate["c2d_calls"]
    payload_bytes = aggregate["shelf_bytes"] + aggregate["c2d_bytes"]
    require(converged_calls == 346298 and payload_bytes == 1180781,
            "convergence aggregate drift")
    frames = (converged_calls + payload_bytes) * timing["timeout_frames"]
    seconds = frames / timing["frames_per_second"]

    policy = {
        "inherit_45_second_window": False,
        "multiply_two_byte_vm_dma_cost": False,
        "include_publication": True,
        "count_source_probe_per_payload_byte": True,
        "authorize_fixed_wait_only_contact": False,
        "require_progress_witness": True,
        "witness_target_side": True,
        "witness_phase_and_ordinal": True,
    }
    policy_gate(policy)
    rejected = mutations(policy)

    kind_counts: dict[str, int] = {}
    for image in images:
        for row in image.descriptors:
            key = str(row[0]); kind_counts[key] = kind_counts.get(key, 0) + 1

    return {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "IMPLAUSIBLY-HIGH-PROTOCOL-BOUND; PROGRESS-WITNESS-REQUIRED",
        "authority": {
            "commission": git_authority(), "Link106_card": bind(CARD),
            "D1_first_red": bind(D1_RED), "Shelf": bind(SHELF), "C2D": bind(C2D),
            "decoder": bind(DECODER), "v2_decoder": bind(V2_DECODER),
            "runtime": bind(RUNTIME), "mapped_convergence": bind(MAPPED),
            "convergence_contract": bind(CONVERGENCE), "oracle_contract": bind(ORACLE),
            "driver": bind(DRIVER),
        },
        "scope": {
            "begin": "LISP65_BOOT_PROGRESS_LIBRARIES at entry to phase 00",
            "end": "c2_ready publish-last after phases 00..12 and export publication",
            "optional_D81_libraries_loaded_here": 0,
            "images": len(images), "entries": sum(len(i.entries) for i in images),
            "descriptors": sum(len(i.descriptors) for i in images),
            "canonical_roots": u16(c2d, 24), "named_exports": publish_totals["named_entries"],
            "descriptor_kind_counts": dict(sorted(kind_counts.items())),
            "code_bytes": sum(i.code_bytes for i in images),
            "metadata_bytes": sum(i.metadata_bytes for i in images),
            "source_contract": source,
        },
        "workload": {
            "decoder_by_phase": {name: value.result() for name, value in decoder_phases.items()},
            "decoder_exact_totals": decoder_totals,
            "publication_by_phase": {name: value.result() for name, value in publish_phases.items()},
            "publication_exact_totals": publish_totals,
            "standard_convergence_aggregate": {
                **aggregate, "converged_calls": converged_calls,
                "payload_bytes": payload_bytes,
            },
            "separate_bounded_work": {
                "phase02a_source_authoritative_record_reads": 18,
                "phase02a_record_bytes": 576,
                "phase03b_bank2_stage_calls": 6,
                "phase03b_stage_bytes": 46043,
                "phase03b_minimum_bank2_crc_reads": 1442,
                "phase03b_minimum_bank2_crc_bytes": 46043,
                "transported_phase_entries": 24,
            },
        },
        "timing": {
            "authorities": timing,
            "historical_45_seconds": {
                "classification": "observation floor for the pre-convergence boot, not a Link-106 upper bound",
                "usable_as_current_bound": False,
            },
            "rejected_cost_transfer": {
                "historical_value": "<20 us per two-byte vm_dma symbol read",
                "new_path": "mapped convergence source-byte probe plus marker job, compare, and optional primary copy",
                "path_equivalence_proved": False,
                "result": "no multiplication permitted",
            },
            "formal_success_ceiling_component": {
                "domain": "standard converged Shelf/C2D reads only; excludes CPU work, overlay transport, phase02a and phase03b",
                "formula": "(payload_bytes source probes + converged_calls possible primary waits) * 64 frames",
                "frames": frames,
                "seconds": round(seconds, 6),
                "hours": round(seconds / 3600.0, 6),
                "days": round(seconds / 86400.0, 6),
                "interpretation": "formal per-operation failure envelope, not expected duration",
            },
            "operational_upper_bound_seconds": None,
            "reason": "the only measured micro-cost is contractually non-portable to this path; the applicable correctness envelope yields 21.75 days for the read component alone",
        },
        "decision": {
            "commission_exit": "BOUND-IMPLAUSIBLY-HIGH",
            "product_hang_claim": False,
            "product_correctness_claim": False,
            "performance_finding": "the cold decoder now performs per-byte verified convergence on 1,180,781 payload bytes across 346,298 API calls; its device rate is unmeasured and cannot be hidden behind the old 45-second window",
            "wait_only_repeat_authorized": False,
            "next_contact_authorized": False,
            "required_next_step": "build and host-qualify a diagnostic progress witness before asking for contact authorization",
        },
        "progress_witness_contract": {
            "identity": "non-promotable diagnostic sibling; zero product-byte claim",
            "producer": "target-side only; no monitor, screenshot or host read while LOADING LIBRARIES is active",
            "monotonic_value": "32-bit count of successfully completed standard convergence reads",
            "location_tuple": ["decoder phase", "image", "entry-or-descriptor ordinal", "publication ordinal"],
            "sampling": "four commit-last target-owned ring slots at frame-separated times; one post-window stop and raw-first readback",
            "decision_rows": {
                "growing": "live; derive measured reads/s and a candidate-specific completion bound with margin",
                "fixed": "loop/stall; the phase/ordinal tuple names the neighborhood",
                "reaches_ready": "boot healthy; close D1 and continue D2-D5",
            },
            "preconditions": [
                "owned slots outside every boot-active owner and ownership-validated region",
                "32-bit no-ABA proof over the full sample horizon",
                "sampler cannot enter monitor, stop CPU, or invoke fail-closed observation path",
                "mapping-correct raw-first readback after the sole final stop",
            ],
        },
        "policy": policy,
        "mutations_rejected": rejected,
        "claim_limit": "This desk receipt binds Link-106 workload and proves that existing evidence cannot support a useful fixed wait-only upper bound. It does not prove a hang, estimate mean device time, authorize hardware contact, change product/media bytes, or open D2-D5.",
    }


def main() -> int:
    try:
        receipt = build_receipt()
        encoded = canonical(receipt)
        if len(sys.argv) == 2 and sys.argv[1] == "--check":
            require(RECEIPT.is_file() and RECEIPT.read_bytes() == encoded,
                    "stored pricing receipt drift")
        elif len(sys.argv) == 1:
            RECEIPT.write_bytes(encoded)
        else:
            raise PricingError("usage: c2_v20_loading_libraries_pricing.py [--check]")
        print("c2-v20-loading-libraries-pricing: PASS")
        print("workload: 346298 converged calls / 1180781 payload bytes")
        print("formal read-envelope component: 21.767428 days; expected time unpriced")
        print("decision: progress witness required; fixed wait-only repeat forbidden")
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError, PricingError) as error:
        print(f"c2-v20-loading-libraries-pricing: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
