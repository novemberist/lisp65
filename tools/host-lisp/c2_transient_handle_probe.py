#!/usr/bin/env python3
"""Bounded host/design probe for the C2D-v5 transient-handle contract.

This probe emits only host-model evidence and one target relocatable used for
capacity projection.  It never edits product sources, links a product closure,
or runs hardware.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
TOOLCHAIN = ROOT / "tools/llvm-mos/bin"
CONTRACT = ROOT / "config/c2-transient-handle-contract.json"
ADDENDUM = ROOT / "docs/planning/c2.2-transient-handle-contract.md"
SOURCE = ROOT / "scripts/c2-transient-handle-capacity-main.c"
OLD_CONTRACT = ROOT / "config/c2-nested-append-unwind-contract.json"
OLD_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-nested-append-unwind-contract-probe-receipt.json")
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-nested-append-capacity-placement-first-red-receipt.json")
LINK32 = ROOT / "build/c2.2/substitution/product-link-32-preinstall-island-guard"
PRODUCT = LINK32 / "lisp65-c2-substitution-linked.prg"
ELF = LINK32 / "lisp65-c2-substitution-linked.prg.elf"
SESSION_MANIFEST = LINK32 / "runtime-overlays-session-final.json"
DEFAULT_OUT = ROOT / "build/c2.2/transient-handle-contract-probe"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-transient-handle-contract-probe-receipt.json")

EXPECTED_PRODUCT_SHA = (
    "189548ea52b9af748217a0da94b7dc1d5daa5f17d190f5817f2fb4af486a676a")
PERSISTENT_CAP = 2048
HANDLE_CAP = 4096
MAX_DEPTH = 4
INVALID = 0xFFFF


class ProbeError(RuntimeError):
    pass


class FormatError(ProbeError):
    pass


class CapacityError(ProbeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def run(command: list[str]) -> str:
    proc = subprocess.run(command, cwd=ROOT, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode:
        raise ProbeError("command failed: " + " ".join(command)
                         + "\n" + proc.stdout + proc.stderr)
    return proc.stdout


def section_sizes(obj: Path) -> dict[str, int]:
    output = run([str(TOOLCHAIN / "llvm-size"), "-A", str(obj)])
    result: dict[str, int] = {}
    for line in output.splitlines():
        match = re.match(r"^(\.\S+)\s+(\d+)\s+\d+\s*$", line)
        if match:
            result[match.group(1)] = int(match.group(2))
    return result


def symbol_sizes(elf: Path) -> dict[str, int]:
    output = run([str(TOOLCHAIN / "llvm-nm"), "--defined-only",
                  "--print-size", "--numeric-sort", str(elf)])
    result: dict[str, int] = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 4 and re.fullmatch(r"[0-9a-fA-F]+", fields[1]):
            result[fields[-1]] = int(fields[1], 16)
    return result


def align(value: int, quantum: int = 256) -> int:
    return (value + quantum - 1) & ~(quantum - 1)


@dataclass
class Record:
    count: int
    generation: int
    physical_base: int


@dataclass
class Plane:
    persistent: int = 588
    generation: int = 7
    records: list[Record] = field(default_factory=list)
    watermark: int = HANDLE_CAP
    journal_started: bool = False
    target_mutations: int = 0

    def clone(self) -> "Plane":
        return Plane(self.persistent, self.generation,
                     [Record(r.count, r.generation, r.physical_base)
                      for r in self.records],
                     self.watermark, self.journal_started,
                     self.target_mutations)

    @property
    def transient_count(self) -> int:
        return HANDLE_CAP - self.watermark

    def validate(self) -> None:
        if not 0 <= self.persistent <= PERSISTENT_CAP:
            raise FormatError("persistent count")
        if not PERSISTENT_CAP <= self.watermark <= HANDLE_CAP:
            raise FormatError("transient watermark")
        if len(self.records) > MAX_DEPTH:
            raise FormatError("transient depth")
        expected = PERSISTENT_CAP
        total = 0
        for record in self.records:
            if record.count <= 0 or record.generation != self.generation:
                raise FormatError("transient record identity")
            expected -= record.count
            if record.physical_base != expected:
                raise FormatError("transient record contiguity")
            total += record.count
        if total != self.transient_count or self.persistent + total > PERSISTENT_CAP:
            raise FormatError("low/high edge mismatch")

    def normalize(self, handle: int) -> int:
        if not 0 <= handle < HANDLE_CAP:
            return INVALID
        if handle < PERSISTENT_CAP:
            return handle if handle < self.persistent else INVALID
        if handle < self.watermark:
            return INVALID
        return handle - PERSISTENT_CAP

    def lookup(self, handle: int) -> bool:
        physical = self.normalize(handle)
        if physical == INVALID:
            return False
        if handle < PERSISTENT_CAP:
            return physical < self.persistent
        hits = sum(record.physical_base <= physical
                   < record.physical_base + record.count
                   for record in self.records)
        if hits > 1:
            raise FormatError("overlapping transient records")
        return hits == 1

    def push(self, count: int, *, stop_before_publish: bool = False) -> list[int]:
        if count <= 0 or len(self.records) >= MAX_DEPTH:
            raise CapacityError("invalid transient reservation")
        if self.persistent + self.transient_count + count > PERSISTENT_CAP:
            raise CapacityError("persistent/transient collision")
        old_watermark = self.watermark
        physical_base = old_watermark - PERSISTENT_CAP - count
        logical_base = old_watermark - count
        self.journal_started = True
        self.target_mutations += count
        self.records.append(Record(count, self.generation, physical_base))
        handles = list(range(logical_base, old_watermark))
        if stop_before_publish:
            return handles
        self.watermark = logical_base
        self.journal_started = False
        return handles

    def publish_staged(self, count: int) -> None:
        require(self.journal_started and self.records[-1].count == count,
                "no staged transient record")
        self.watermark -= count
        self.journal_started = False

    def pop(self, *, stop_after_unpublish: bool = False) -> list[int]:
        if not self.records:
            raise CapacityError("pop without transient")
        record = self.records[-1]
        old_handles = list(range(self.watermark,
                                 self.watermark + record.count))
        self.watermark += record.count
        if stop_after_unpublish:
            return old_handles
        self.records.pop()
        self.target_mutations -= record.count
        return old_handles

    def finish_pop_wipe(self) -> None:
        require(self.records, "no unpublished record to wipe")
        record = self.records[-1]
        require(self.watermark == HANDLE_CAP
                - sum(r.count for r in self.records[:-1]),
                "watermark was not raised before wipe")
        self.records.pop()
        self.target_mutations -= record.count

    def abort(self) -> list[int]:
        handles = list(range(self.watermark, HANDLE_CAP))
        self.watermark = HANDLE_CAP
        self.records.clear()
        self.journal_started = False
        self.target_mutations = 0
        return handles

    def restage(self) -> tuple[list[int], "Plane"]:
        handles = list(range(self.watermark, HANDLE_CAP))
        self.watermark = HANDLE_CAP
        replacement = Plane(self.persistent, self.generation + 1)
        return handles, replacement


def expect(error: type[BaseException], action: Callable[[], Any]) -> None:
    try:
        action()
    except error:
        return
    raise ProbeError(f"expected {error.__name__}")


def run_model() -> list[dict[str, str]]:
    cases: list[dict[str, str]] = []

    def passed(name: str, detail: str) -> None:
        cases.append({"name": name, "status": "passed", "detail": detail})

    p = Plane()
    p.validate()
    require(p.normalize(0) == 0 and p.normalize(587) == 587,
            "persistent identity mapping")
    passed("persistent-identity", "logical and physical ordinals are identical")
    require(not p.lookup(588) and not p.lookup(2048) and not p.lookup(4095),
            "inactive holes accepted")
    passed("inactive-hole", "neither low hole nor inactive high namespace is callable")

    p = Plane()
    outer = p.push(2)
    inner = p.push(3)
    p.validate()
    require(outer == [4094, 4095] and inner == [4091, 4092, 4093],
            "logical high allocation")
    require([p.normalize(h) for h in outer + inner]
            == [2046, 2047, 2043, 2044, 2045], "constant translation")
    passed("nested-high-handles", "logical and physical fronts descend in lockstep")
    require(all(p.lookup(h) for h in outer + inner), "active handle rejected")
    passed("nested-active-lookup", "both active extents are callable")
    stale_inner = p.pop()
    p.validate()
    require(all(not p.lookup(h) for h in stale_inner)
            and all(p.lookup(h) for h in outer), "inner pop visibility")
    passed("inner-pop-stale", "inner handles die while outer handles remain live")
    stale_outer = p.abort()
    p.validate()
    require(all(not p.lookup(h) for h in stale_outer), "abort left callable handle")
    passed("abort-kills-all", "watermark reset rejects every old transient handle")

    p = Plane()
    staged = p.push(2, stop_before_publish=True)
    require(all(not p.lookup(h) for h in staged), "pre-publish handle visible")
    passed("publish-last-before", "staged records are invisible before watermark store")
    p.publish_staged(2)
    require(all(p.lookup(h) for h in staged), "published handles absent")
    passed("publish-last-after", "one watermark store publishes the complete extent")
    removed = p.pop(stop_after_unpublish=True)
    require(all(not p.lookup(h) for h in removed), "removed handle visible before wipe")
    passed("unpublish-before-wipe", "raised watermark kills handles before bytes are wiped")
    p.finish_pop_wipe()
    p.validate()

    p = Plane()
    old = p.push(1)
    stale, p = p.restage()
    require(stale == old and all(not p.lookup(h) for h in stale)
            and p.generation == 8, "restage stale handle")
    passed("restage-invalidates-first", "inactive watermark precedes generation change")

    for value, label in ((2047, "below-domain"), (4097, "above-domain")):
        p = Plane(watermark=value)
        expect(FormatError, p.validate)
        passed(f"malformed-watermark-{label}", "format validation rejects the header")

    p = Plane()
    p.push(1)
    p.records[0].generation += 1
    expect(FormatError, p.validate)
    passed("stale-record-generation", "record/header generation mismatch rejected")
    p = Plane()
    p.push(1)
    p.records[0].physical_base -= 1
    expect(FormatError, p.validate)
    passed("noncontiguous-record", "record/high-front mismatch rejected")
    p = Plane()
    for _ in range(MAX_DEPTH):
        p.push(1)
    before = p.clone()
    expect(CapacityError, lambda: p.push(1))
    require(p == before, "fifth depth mutated state")
    passed("fifth-depth", "rejected before mutation")

    p = Plane(persistent=2047)
    h = p.push(1)
    p.validate()
    require(p.normalize(h[0]) == 2047, "exact meet translation")
    passed("f2-exact-meet", "2047 persistent plus one transient is legal")
    before = p.clone()
    expect(CapacityError, lambda: p.push(1))
    require(p == before and not p.journal_started, "F2 +1 mutated state")
    passed("f2-plus-one", "one entry beyond the meet fails before journal/target mutation")
    p = Plane(persistent=2048)
    before = p.clone()
    expect(CapacityError, lambda: p.push(1))
    require(p == before, "full persistent plane accepted transient")
    passed("f2-full-persistent", "a full low edge rejects the first high entry")

    p = Plane()
    high = p.push(3)
    p.persistent += 5
    p.validate()
    require(all(p.lookup(h) for h in high), "persistent descendant moved high handles")
    passed("persistent-descendant-stability", "low-edge growth does not renumber high handles")

    require(len(cases) == 19, f"model case count drift: {len(cases)}")
    return cases


def product_source_lists_do_not_name_probe() -> bool:
    needle = SOURCE.name
    paths = [ROOT / "Makefile", *sorted((ROOT / "mk").glob("*.mk"))]
    return all(needle not in path.read_text(encoding="utf-8", errors="replace")
               for path in paths if path.is_file())


def run_probe(out: Path) -> dict[str, Any]:
    require(not out.exists(), f"output already exists: {out}")
    for path in (CONTRACT, ADDENDUM, SOURCE, OLD_CONTRACT, OLD_RECEIPT,
                 FIRST_RED, PRODUCT, ELF, SESSION_MANIFEST):
        require(path.is_file(), f"required input absent: {path}")
    require(sha(PRODUCT) == EXPECTED_PRODUCT_SHA, "Link-32 product identity drift")
    require(product_source_lists_do_not_name_probe(), "sizing source entered a product list")
    contract = load(CONTRACT)
    require(contract["status"] == "owner-authorized-bounded-contract-and-design-probe",
            "handle contract is not owner-authorized")
    old = load(OLD_RECEIPT)
    require(old["status"] == "passed-host-contract-probe-product-work-not-authorized",
            "nested semantic probe is not green")
    first_red = load(FIRST_RED)
    require(first_red["status"] == "first-red-e000-product-unchanged",
            "bound capacity first red drift")

    cases = run_model()
    out.mkdir(parents=True)
    obj = out / "c2-transient-handle-capacity-main.o"
    command = [
        str(TOOLCHAIN / "mos-mega65-clang"), "-Oz", "-Wall", "-Wextra",
        "-fno-lto", "-ffunction-sections", "-fdata-sections", "-c",
        str(SOURCE), "-o", str(obj),
    ]
    run(command)
    sections = section_sizes(obj)
    expected_sections = {
        ".probe.handle.lookup-base", ".probe.handle.lookup-normalized",
        ".probe.handle.normalizer", ".probe.handle.state-publish",
    }
    require(expected_sections <= sections.keys(), "sizing seam inventory incomplete")
    real_lookup = symbol_sizes(ELF)["c2_entry_records"]
    baseline = sections[".probe.handle.lookup-base"]
    calibration = real_lookup - baseline
    require(abs(calibration) <= 16, "lookup calibration exceeds 16 bytes")

    normalized = sections[".probe.handle.lookup-normalized"]
    normalizer = sections[".probe.handle.normalizer"]
    state_publish = sections[".probe.handle.state-publish"]
    e000_delta = normalized - baseline
    first_capacity = first_red["capacity_and_placement"]
    walls = load(OLD_CONTRACT)["capacity_gate_before_product_work"]
    abort_facade = first_capacity["resident_island"]["abort_facade_bytes"]
    require(e000_delta <= 0, "handle contract still grows closed E000")
    require(normalizer + abort_facade <= walls["resident_island_headroom_bytes"],
            "normalizer and abort facade exceed Island")

    manifest = load(SESSION_MANIFEST)
    old_storage = manifest["storage"]["size"]
    abort_bytes = first_red["costs"]["longjmp_abort_cleanup"][
        "transported_cleanup_slice_bytes"]
    abort_offset = align(old_storage)
    projected_storage = abort_offset + abort_bytes
    require(state_publish <= first_red["costs"]["gc_high_tail"][
        "control_bytes_per_publish_or_remove_copy"],
        "watermark publication exceeds already priced control seam")

    capacity = {
        "bank0_text": {
            "link32_headroom_bytes": walls["bank0_text_headroom_bytes"],
            "nested_serial_and_abort_projection_headroom_bytes": first_capacity[
                "bank0_text"]["projected_headroom_bytes"],
            "handle_contract_delta_bytes": 0,
            "status": "unchanged from green non-lookup seams",
        },
        "ordinary_bank0_bss": {
            "link32_headroom_bytes": walls["ordinary_bank0_bss_headroom_bytes"],
            "delta_bytes": 0,
            "status": "unchanged",
        },
        "cpu_e000_window": {
            "link32_margin_bytes": walls["e000_headroom_bytes"],
            "lookup_baseline_target_bytes": baseline,
            "lookup_normalized_target_bytes": normalized,
            "delta_bytes": e000_delta,
            "projected_margin_bytes": walls["e000_headroom_bytes"] - e000_delta,
            "policy": "closed to new tenants; replacement delta must be <=0",
            "status": "passed exact-zero-or-credit gate",
        },
        "resident_island": {
            "link32_headroom_bytes": walls["resident_island_headroom_bytes"],
            "handle_normalizer_bytes": normalizer,
            "already_projected_abort_facade_bytes": abort_facade,
            "combined_bytes": normalizer + abort_facade,
            "projected_headroom_bytes": (
                walls["resident_island_headroom_bytes"] - normalizer - abort_facade),
            "status": "fits target-object projection",
        },
        "runtime_overlay_session_bank": {
            "link32_bytes": old_storage,
            "transient_tail_lookup_slice_bytes": 0,
            "abort_cleanup_slice_bytes": abort_bytes,
            "abort_cleanup_offset": abort_offset,
            "watermark_control_bytes": state_publish,
            "watermark_control_storage_delta_bytes": 0,
            "projected_storage_bytes": projected_storage,
            "projected_storage_delta_bytes": projected_storage - old_storage,
            "projected_headroom_bytes": 65536 - projected_storage,
            "slice_count_before": len(manifest["slices"]),
            "slice_count_after": len(manifest["slices"]) + 1,
            "status": "fits target-object projection",
        },
        "bank5_session_plane": {
            "c2d_header_delta_bytes": 0,
            "c2d_record_width_delta_bytes": 0,
            "unwind_journal_bytes": 64,
            "ordinary_c_bss_delta_bytes": 0,
            "status": "same-width v5 contract",
        },
    }

    report = {
        "format": "lisp65-c2-transient-handle-contract-probe-receipt-v1",
        "recorded_on": "2026-07-20",
        "status": "passed-contract-and-capacity-probe-product-work-not-authorized",
        "scope": {
            "host_model_cases": len(cases),
            "target_objects_compiled": 1,
            "product_source_files_changed_by_probe": 0,
            "product_closure_links": 0,
            "hardware_execution": "prohibited",
            "performance_claim": "none",
        },
        "bindings": {
            "contract": bind(CONTRACT),
            "addendum": bind(ADDENDUM),
            "nested_append_contract": bind(OLD_CONTRACT),
            "nested_append_contract_receipt": bind(OLD_RECEIPT),
            "capacity_first_red_receipt": bind(FIRST_RED),
            "link32_product": bind(PRODUCT),
            "link32_elf": bind(ELF),
            "link32_session_manifest": bind(SESSION_MANIFEST),
            "sizing_source": bind(SOURCE),
            "target_object": bind(obj),
            "target_compiler": bind(TOOLCHAIN / "mos-mega65-clang"),
        },
        "format_decision": {
            "c2d_version": 5,
            "header_and_record_delta_bytes": 0,
            "logical_persistent_domain": [0, 2047],
            "logical_transient_domain": [2048, 4095],
            "physical_translation": "logical-2048",
            "inactive_watermark": 4096,
            "depth": "derived from contiguous source-kind-2 records; maximum four",
            "single_runtime_visibility_value": "transient_handle_watermark_u16",
            "unshipped_version_rule": "v4-to-v5 is free only before first C2 product seal",
        },
        "model": {
            "cases": cases,
            "passed": len(cases),
            "failed": 0,
            "stale_after_abort": "rejected by watermark alone before wipe",
            "f2_collision": "exact meet accepted; +1 rejected before journal/target mutation",
        },
        "target_capacity_projection": capacity,
        "compiler": {
            "command": command,
            "mode": "llvm-mos target relocatable, -Oz, no LTO",
            "lookup_calibration": {
                "link32_lto_symbol_bytes": real_lookup,
                "target_object_baseline_bytes": baseline,
                "difference_bytes": calibration,
            },
        },
        "gc_transport": {
            "link32_blocks_per_collection": 18,
            "transient_high_edge_blocks_per_collection": 96,
            "additional_blocks_per_collection": 78,
            "status": "capacity-neutral; performance not accepted",
            "next_hardware_presmoke": "separate GC time/frame line required",
        },
        "fallbacks": {
            "option_1_in_place_reclaim": "not entered because handle design is green",
            "option_3_reopen_e000": "not eligible; would require a separate owner floor decision",
        },
        "claim_limit": (
            "Bounded contract, host-state and target-object capacity projection only. "
            "No product implementation, LTO link, hardware result, GC-latency "
            "acceptance or promotion is claimed."),
        "next_gate": (
            "Before any successor product link, perform the commissioned cross-invariant "
            "quick pass for B2, E1, C2, B5 and D1 against this stable contract."),
    }
    (out / "model-cases.json").write_text(
        json.dumps(cases, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "section-sizes.json").write_text(
        json.dumps(sections, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "compile-command.txt").write_text(" ".join(command) + "\n",
                                              encoding="utf-8")
    (out / "contract-probe-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def protect_tree(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        os.chmod(path, 0o555 if path.is_dir() else 0o444)
    os.chmod(root, 0o555)


def check_receipt() -> dict[str, Any]:
    require(RECEIPT.is_file(), "transient-handle receipt absent")
    value = load(RECEIPT)
    require(value["status"]
            == "passed-contract-and-capacity-probe-product-work-not-authorized",
            "receipt status drift")
    require(value["scope"]["product_closure_links"] == 0
            and value["scope"]["product_source_files_changed_by_probe"] == 0,
            "receipt scope drift")
    require(value["target_capacity_projection"]["cpu_e000_window"]["delta_bytes"] <= 0,
            "closed E000 gate drift")
    for item in value["bindings"].values():
        path = ROOT / item["path"]
        require(path.is_file() and path.stat().st_size == item["bytes"]
                and sha(path) == item["sha256"],
                f"bound artifact drift: {item['path']}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check"))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    try:
        if args.action == "check":
            report = check_receipt()
            verb = "CHECK PASS"
        else:
            report = run_probe(args.out.resolve())
            encoded = canonical(report)
            if RECEIPT.exists():
                require(RECEIPT.read_bytes() == encoded,
                        "refusing to overwrite divergent receipt")
            else:
                RECEIPT.write_bytes(encoded)
            os.chmod(RECEIPT, 0o444)
            protect_tree(args.out.resolve())
            verb = "PASS"
        cap = report["target_capacity_projection"]
        print("c2-transient-handle: " + verb
              + f" cases={report['model']['passed']}/{report['scope']['host_model_cases']}"
              + f" e000-delta={cap['cpu_e000_window']['delta_bytes']}"
              + f" island-free={cap['resident_island']['projected_headroom_bytes']}"
              + " product-links=0")
        print("c2-transient-handle: receipt_sha256=" + sha(RECEIPT))
        return 0
    except (ProbeError, OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"c2-transient-handle: FAIL {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
