#!/usr/bin/env python3
"""Single-comparison golden layout gate for the parked ownership programme."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import c2_stack_overlay_ownership as OWN  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
GOLDEN = ROOT / (
    "tests/bytecode/dialect-v2/golden-layout/"
    "c2-full-map-owned-layout-v1.json")
RECEIPT = EVIDENCE / "c2.3-golden-layout-inversion-review-receipt.json"
TERMINAL = ROOT / "build/post-promotion/v18/full-map-ownership-repair-wplto/wplto"
SEED_ELF = TERMINAL / "resident-island-seed.prg.elf"
FINAL_ELF = TERMINAL / "lisp65-c2-substitution-linked.prg.elf"
FINAL_PARK = ROOT / "docs/planning/1.9-full-map-recharter-final-park.md"
OWNER_PLAN = "docs/planning/post-v1.4.0-direction-plan.md"
OWNER_APPROVAL_COMMIT = "849dca0a9be6aefec36e14ec867036f97272fc40"
GOLDEN_SHA256 = "65a13501c36db615f356bb7f992dcbb1c6a6f932fcf1968bf34646f9cbc7b4f7"
SEED_ELF_SHA256 = "969c311350c4761f71c002aa59f9712d0bbf52a441f73e179b2ae4df9ec23e82"
FINAL_ELF_SHA256 = "64e269eaf820cdd1ee5f1eb35da32c404793bb4b2104be8290fa7483450c7fc4"
RECORDED_ON = "2026-08-09"

BOUNDARY_SYMBOLS = (
    "__basic_zp_end",
    "__basic_zp_size",
    "__basic_zp_start",
    "__bss_end",
    "__bss_size",
    "__bss_start",
    "__data_end",
    "__data_load_start",
    "__data_size",
    "__data_start",
    "__heap_start",
    "__lisp65_c2_mapped_far_service_end",
    "__lisp65_c2_mapped_far_service_load_end",
    "__lisp65_c2_mapped_far_service_load_start",
    "__lisp65_c2_mapped_far_service_start",
    "__lisp65_resident_island_end",
    "__lisp65_resident_island_limit",
    "__lisp65_resident_island_start",
    "__lisp65_workbench_noinit_end",
    "__lisp65_workbench_overlay_end",
    "__lisp65_workbench_overlay_min_start",
    "__lisp65_workbench_overlay_start",
    "__lisp65_workbench_runtime_overlay_vma",
    "__zp_bss_size",
    "__zp_bss_start",
    "__zp_data_load_start",
    "__zp_data_size",
    "__zp_data_start",
)


class GoldenLayoutError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GoldenLayoutError(message)


def sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        require(key not in value, f"duplicate JSON key: {key}")
        value[key] = item
    return value


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"regular JSON authority absent: {path}")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=strict_object)
    except json.JSONDecodeError as error:
        raise GoldenLayoutError(f"invalid JSON authority: {path}") from error
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"regular authority absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def git_binding(commit: str, path: str) -> dict[str, Any]:
    raw = subprocess.run(
        ["git", "show", f"{commit}:{path}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {
        "git_commit": commit,
        "path": path,
        "bytes": len(raw),
        "sha256": sha_bytes(raw),
    }


def layout_from_elf(path: Path) -> dict[str, Any]:
    truth, raw_sections, headers = OWN.read_elf(path)
    sections: list[dict[str, Any]] = []
    for section in truth.sections:
        if "SHF_ALLOC" not in section.flags:
            continue
        raw = raw_sections[section.index]
        lma: int | None = None
        if section.bytes:
            try:
                lma = OWN.section_lma(section, raw, headers)
            except OWN.OwnershipError:
                require(section.section_type == "SHT_NOBITS",
                        f"load address unresolved for file-backed section: "
                        f"{section.name}")
        sections.append({
            "alignment": int(raw["AddressAlignment"]),
            "bytes": section.bytes,
            "flags": sorted(section.flags),
            "lma": lma,
            "name": section.name,
            "section_type": section.section_type,
            "vma": section.address,
        })
    sections.sort(key=lambda row: row["name"])
    boundaries = {
        name: truth.symbol(name).value for name in BOUNDARY_SYMBOLS
    }
    return {
        "allocatable_sections": sections,
        "boundary_symbols": boundaries,
        "format": "lisp65-c2-full-map-golden-layout-v1",
    }


def audit_artifact(value: dict[str, Any]) -> None:
    require(set(value) == {
        "allocatable_sections", "boundary_symbols", "format"},
        "golden layout top-level shape drift")
    require(value["format"] == "lisp65-c2-full-map-golden-layout-v1",
            "golden layout format drift")
    sections = value["allocatable_sections"]
    require(isinstance(sections, list) and sections,
            "golden layout has no allocatable sections")
    names: list[str] = []
    for row in sections:
        require(isinstance(row, dict) and set(row) == {
            "alignment", "bytes", "flags", "lma", "name",
            "section_type", "vma"}, "golden section row shape drift")
        require(isinstance(row["name"], str) and row["name"],
                "golden section name is empty")
        require(isinstance(row["vma"], int) and row["vma"] >= 0,
                f"invalid section VMA: {row['name']}")
        require(isinstance(row["bytes"], int) and row["bytes"] >= 0,
                f"invalid section size: {row['name']}")
        require(isinstance(row["alignment"], int) and row["alignment"] > 0,
                f"invalid section alignment: {row['name']}")
        require(row["lma"] is None or
                isinstance(row["lma"], int) and row["lma"] >= 0,
                f"invalid section LMA: {row['name']}")
        require(isinstance(row["section_type"], str)
                and row["section_type"],
                f"invalid section type: {row['name']}")
        require(isinstance(row["flags"], list)
                and row["flags"] == sorted(set(row["flags"]))
                and all(isinstance(item, str) for item in row["flags"]),
                f"invalid section flags: {row['name']}")
        names.append(row["name"])
    require(names == sorted(set(names)),
            "golden section identities are duplicated or non-canonical")
    boundaries = value["boundary_symbols"]
    require(isinstance(boundaries, dict)
            and tuple(sorted(boundaries)) == BOUNDARY_SYMBOLS,
            "golden boundary-symbol closure drift")
    require(all(isinstance(item, int) and item >= 0
                for item in boundaries.values()),
            "invalid golden boundary-symbol value")


def golden_bytes() -> bytes:
    raw = GOLDEN.read_bytes()
    require(sha_bytes(raw) == GOLDEN_SHA256,
            "golden layout SHA-256 binding drift")
    value = load(GOLDEN)
    audit_artifact(value)
    require(canonical(value) == raw,
            "golden layout is not in canonical byte form")
    return raw


def compare_elf(path: Path) -> dict[str, Any]:
    expected = golden_bytes()
    candidate = canonical(layout_from_elf(path))
    require(candidate == expected,
            "linked product layout differs from the reviewed golden artifact")
    value = load(GOLDEN)
    return {
        "comparison": "byte-identical",
        "golden_sha256": GOLDEN_SHA256,
        "candidate_layout_sha256": sha_bytes(candidate),
        "allocatable_sections": len(value["allocatable_sections"]),
        "boundary_symbols": len(value["boundary_symbols"]),
    }


def source_layouts() -> tuple[dict[str, Any], dict[str, Any]]:
    require(sha(SEED_ELF) == SEED_ELF_SHA256,
            "terminal seed ELF binding drift")
    require(sha(FINAL_ELF) == FINAL_ELF_SHA256,
            "terminal final ELF binding drift")
    seed = layout_from_elf(SEED_ELF)
    final = layout_from_elf(FINAL_ELF)
    require(canonical(seed) == canonical(final),
            "the two proven-fitting terminal ELFs have different layouts")
    audit_artifact(seed)
    return seed, final


def reject(label: str, action: Callable[[], None],
           result: dict[str, str]) -> None:
    try:
        action()
    except GoldenLayoutError as error:
        result[label] = str(error)
    else:
        raise GoldenLayoutError(f"golden-layout mutation survived: {label}")


def require_exact(value: dict[str, Any], expected: bytes) -> None:
    audit_artifact(value)
    require(canonical(value) == expected,
            "candidate layout is not byte-identical to golden")


def mutation_selftest() -> dict[str, str]:
    raw = golden_bytes()
    base = load(GOLDEN)
    result: dict[str, str] = {}
    cases: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("section-deleted", lambda item: item["allocatable_sections"].pop()),
        ("section-added", lambda item: item["allocatable_sections"].append({
            **item["allocatable_sections"][-1], "name": ".stray"})),
        ("section-vma-moved", lambda item: item["allocatable_sections"][0]
         .__setitem__("vma", item["allocatable_sections"][0]["vma"] + 1)),
        ("section-lma-moved", lambda item: next(
            row for row in item["allocatable_sections"]
            if row["lma"] is not None).__setitem__("lma", 0)),
        ("section-size-changed", lambda item: item["allocatable_sections"][0]
         .__setitem__("bytes", item["allocatable_sections"][0]["bytes"] + 1)),
        ("section-alignment-changed", lambda item:
         item["allocatable_sections"][0].__setitem__("alignment", 2)),
        ("section-type-changed", lambda item:
         item["allocatable_sections"][0].__setitem__("section_type", "SHT_NOTE")),
        ("section-flags-changed", lambda item:
         item["allocatable_sections"][0]["flags"].append("SHF_WRITE")),
        ("boundary-deleted", lambda item: item["boundary_symbols"].pop(
            "__heap_start")),
        ("boundary-added", lambda item: item["boundary_symbols"].__setitem__(
            "__invented_boundary", 0)),
        ("boundary-moved", lambda item: item["boundary_symbols"].__setitem__(
            "__heap_start", item["boundary_symbols"]["__heap_start"] + 1)),
        ("format-changed", lambda item: item.__setitem__("format", "old")),
    ]
    for label, mutate in cases:
        candidate = deepcopy(base)
        mutate(candidate)
        reject(label, lambda candidate=candidate: require_exact(candidate, raw),
               result)
    reversed_rows = deepcopy(base)
    reversed_rows["allocatable_sections"].reverse()
    reversed_rows["allocatable_sections"].sort(key=lambda row: row["name"])
    require(canonical(reversed_rows) == raw,
            "source section ordering leaked into the golden artifact")
    return result


def build_receipt() -> dict[str, Any]:
    seed, final = source_layouts()
    raw = golden_bytes()
    require(canonical(seed) == raw and canonical(final) == raw,
            "reviewed golden does not reproduce both terminal layouts")
    mutations = mutation_selftest()
    return {
        "format": "lisp65-c2.3-golden-layout-inversion-review-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: awaiting one-time owner golden review",
        "claim": (
            "Host-only inversion of the parked ownership acceptance into "
            "one exact candidate-layout-versus-golden byte comparison; no "
            "product card, WPLTO, device, Link 91, parity or release claim."),
        "golden": {
            **bind(GOLDEN),
            "allocatable_sections": len(seed["allocatable_sections"]),
            "boundary_symbols": len(seed["boundary_symbols"]),
            "source_order_independent": True,
        },
        "source_authority": {
            "seed_elf": bind(SEED_ELF),
            "final_elf": bind(FINAL_ELF),
            "two_terminal_layouts_byteidentical": True,
            "proven_fitting_geometry": "zero-deficit-five-byte-non-freight-margin",
        },
        "acceptance_inversion": {
            "comparison_operations": 1,
            "comparison": "canonical-candidate-layout-bytes == SHA-bound-golden-bytes",
            "checker_pipeline_stages": 0,
            "external_checker_vocabularies": 0,
            "source_section_order_dependencies": 0,
            "candidate_expectations_read_from_candidate": 0,
        },
        "mutations_rejected": mutations,
        "execution_witness": {
            "terminal_elf_layout_extractions": 2,
            "golden_comparisons": 2,
            "mutations": len(mutations),
            "product_compiles": 0,
            "fresh_wplto": 0,
            "device_contacts": 0,
        },
        "authority": {
            "owner_approval": git_binding(OWNER_APPROVAL_COMMIT, OWNER_PLAN),
            "final_park_restart_wisdom": bind(FINAL_PARK),
            "gate": bind(Path(__file__).resolve()),
        },
        "next_gate": (
            "One-time owner review of the golden artifact. Only an accepted "
            "review may authorize the one product-shaped card."),
    }


def emit() -> None:
    require(not GOLDEN.exists(), "golden layout already exists")
    seed, final = source_layouts()
    require(canonical(seed) == canonical(final),
            "terminal layout reproduction drift")
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_bytes(canonical(seed))
    print("c2-golden-layout-inversion: EMIT PASS "
          f"sections={len(seed['allocatable_sections'])} "
          f"boundaries={len(seed['boundary_symbols'])} "
          f"sha256={sha(GOLDEN)}")


def review(write: bool) -> None:
    value = build_receipt()
    if write:
        RECEIPT.write_bytes(canonical(value))
    print("c2-golden-layout-inversion: REVIEW PASS "
          f"sections={value['golden']['allocatable_sections']} "
          f"boundaries={value['golden']['boundary_symbols']} "
          f"mutations={value['execution_witness']['mutations']} "
          "compiles=0 wplto=0 device=0 review=owner")


def check() -> None:
    require(RECEIPT.is_file(), "golden-layout review receipt absent")
    expected = build_receipt()
    require(canonical(load(RECEIPT)) == canonical(expected),
            "golden-layout review receipt drift")
    print("c2-golden-layout-inversion: CHECK PASS "
          f"golden={GOLDEN_SHA256} comparisons=1 "
          f"mutations={len(expected['mutations_rejected'])}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode", choices=("emit", "selftest", "review", "write-review",
                         "check", "compare"))
    parser.add_argument("--elf", type=Path)
    args = parser.parse_args()
    if args.mode == "emit":
        emit()
    elif args.mode == "selftest":
        source_layouts()
        mutations = mutation_selftest()
        print("c2-golden-layout-inversion: SELFTEST PASS "
              f"mutations={len(mutations)} order=independent")
    elif args.mode in ("review", "write-review"):
        review(args.mode == "write-review")
    elif args.mode == "check":
        check()
    else:
        require(args.elf is not None, "compare mode requires --elf")
        result = compare_elf(args.elf)
        print("c2-golden-layout-inversion: COMPARE PASS "
              f"sections={result['allocatable_sections']} "
              f"boundaries={result['boundary_symbols']} "
              f"sha256={result['candidate_layout_sha256']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GoldenLayoutError, OWN.OwnershipError, OSError, ValueError,
            KeyError, subprocess.CalledProcessError) as error:
        print(f"c2-golden-layout-inversion: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
