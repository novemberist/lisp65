#!/usr/bin/env python3
"""Read-only Phase-A inventory for the v1.7 state-ownership block."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402


READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
LINK90_ELF = ROOT / (
    "build/post-promotion/v14/link90-vic-unlock-wplto/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
FAILED = ROOT / "build/post-promotion/v15/mapped-far-ownership-wplto/wplto"
FAILED_LTO = FAILED / "resident-island-seed.prg.lto.o"
FAILED_MAP = FAILED / "resident-island-seed.prg.map"
FAILED_LINKER = FAILED / "c2-substitution.ld"
FAILED_STDERR = FAILED / "resident-island-seed.prg.link.stderr.txt"
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-stack-overlay-mapped-far-service-wplto-first-red.json")
V15_CONTRACT = ROOT / "config/c2-stack-overlay-ownership-contract.json"
PLAN = ROOT / "docs/planning/1.7-state-ownership-work-plan.md"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.7-state-ownership-phase-a-inventory-receipt.json")


class FirstRed(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FirstRed(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def parse_output_sections(path: Path) -> dict[str, dict[str, int]]:
    rows: dict[str, dict[str, int]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 5 or not parts[4].startswith("."):
            continue
        try:
            address, lma, size, alignment = (int(item, 16) for item in parts[:4])
        except ValueError:
            continue
        name = parts[4]
        require(name not in rows, f"duplicate output section in map: {name}")
        rows[name] = {
            "vma": address,
            "lma": lma,
            "bytes": size,
            "alignment": alignment,
        }
    return rows


def category(name: str) -> str | None:
    if name.startswith(".bss."):
        return "ordinary-bank0-bss"
    if name in (".zp.data", ".zp.bss", ".zp.noinit"):
        return "ordinary-zero-page"
    if name.startswith(".lisp65_c2_convergence_state."):
        return "convergence-bank0-state"
    if name.startswith(".lisp65_c2_convergence_zp."):
        return "convergence-zero-page"
    if name == ".noinit..Lstatic_stack":
        return "compiler-static-stack"
    if (name.startswith(".lisp65_c2_fixed_bank0")
            and "_code" not in name):
        return "fixed-c2-bank0-state"
    if name == ".lisp65_c2_mapped_far_service":
        return "mapped-far-service-body"
    return None


def provenance(name: str) -> tuple[str, list[str]]:
    if name.startswith((".bss.", ".zp.")):
        return "ordinary-LTO-section-order", []
    if name == ".noinit..Lstatic_stack":
        return "compiler-generated-static-stack", []
    if name.startswith(".lisp65_c2_convergence_"):
        return "explicit-linker-section", ["code-window-convergence"]
    if name.startswith(".lisp65_c2_fixed_bank0"):
        return "explicit-linker-section", ["c2-fixed-bank0"]
    if name == ".lisp65_c2_mapped_far_service":
        return "explicit-linker-section", ["mapped-bank2-far-service"]
    raise FirstRed(f"unclassified state provenance: {name}")


def input_rows(truth: ElfTruth) -> list[dict[str, Any]]:
    rows = []
    for section in truth.sections:
        family = category(section.name)
        if section.bytes == 0 or family is None:
            continue
        placement, owners = provenance(section.name)
        symbols = sorted(
            symbol.name for symbol in truth.symbols
            if symbol.section_index == section.index and symbol.bytes > 0)
        rows.append({
            "id": section.name,
            "family": family,
            "bytes": section.bytes,
            "alignment": 1,
            "symbols": symbols,
            "placement_provenance": placement,
            "semantic_owners": owners,
            "artifact": "failed-product-LTO-object",
        })
    # This assembler-owned state is visible only in the failed final map, not
    # in the whole-program LTO object.  It remains ordinary/unowned state.
    rows.append({
        "id": ".bss.f011_guard@canonical-asm-object",
        "family": "ordinary-bank0-bss",
        "bytes": 9,
        "alignment": 1,
        "symbols": ["f011_guard"],
        "placement_provenance": "ordinary-assembler-section-order",
        "semantic_owners": [],
        "artifact": "failed-final-map",
    })
    return sorted(rows, key=lambda row: row["id"])


def interval(row: dict[str, int]) -> dict[str, Any]:
    return {
        "start": f"0x{row['vma']:04x}",
        "end_exclusive": f"0x{row['vma'] + row['bytes']:04x}",
        "bytes": row["bytes"],
        "alignment": row["alignment"],
    }


def overlap(left: dict[str, int], right: dict[str, int]) -> int:
    return max(0, min(left["vma"] + left["bytes"],
                      right["vma"] + right["bytes"])
               - max(left["vma"], right["vma"]))


def family_summary(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    names = (
        "ordinary-bank0-bss", "ordinary-zero-page",
        "convergence-bank0-state", "convergence-zero-page",
        "fixed-c2-bank0-state", "compiler-static-stack",
        "mapped-far-service-body",
    )
    return {
        name: {
            "input_sections": sum(row["family"] == name for row in rows),
            "bytes": sum(row["bytes"] for row in rows if row["family"] == name),
        }
        for name in names
    }


def build() -> dict[str, Any]:
    first_red = load(FIRST_RED)
    contract = load(V15_CONTRACT)
    link90 = ElfTruth.read(LINK90_ELF, llvm_readobj=READOBJ)
    failed_lto = ElfTruth.read(FAILED_LTO, llvm_readobj=READOBJ)
    outputs = parse_output_sections(FAILED_MAP)
    rows = input_rows(failed_lto)
    families = family_summary(rows)

    needed = (
        ".zp.data", ".zp.bss", ".zp", ".lisp65_c2_fixed_zp",
        ".lisp65_c2_convergence_zp", ".bss",
        ".lisp65_c2_convergence_state", ".lisp65_c2_static_stack",
        ".lisp65_c2_fixed_bank0", ".lisp65_c2_fixed_bank0_code",
        ".lisp65_c2_fixed_bank0_hot_bss", ".noinit",
        ".lisp65_workbench_overlay", ".lisp65_c2_mapped_far_service",
    )
    require(all(name in outputs for name in needed), "failed map state row absent")
    out = {name: outputs[name] for name in needed}
    bss = out[".bss"]
    convergence = out[".lisp65_c2_convergence_state"]
    stack = out[".lisp65_c2_static_stack"]
    fixed = {
        "vma": out[".lisp65_c2_fixed_bank0"]["vma"],
        "bytes": (out[".lisp65_c2_fixed_bank0"]["bytes"]
                  + out[".lisp65_c2_fixed_bank0_code"]["bytes"]
                  + out[".lisp65_c2_fixed_bank0_hot_bss"]["bytes"]),
        "alignment": 1,
    }
    overlay = out[".lisp65_workbench_overlay"]
    baseline_sections = {
        name: interval({"vma": link90.section(name).address,
                        "bytes": link90.section(name).bytes,
                        "alignment": 1})
        for name in (".zp.data", ".zp.bss", ".zp", ".bss",
                     ".lisp65_c2_fixed_bank0",
                     ".lisp65_c2_fixed_bank0_code",
                     ".lisp65_c2_fixed_bank0_hot_bss", ".noinit")
    }
    baseline_state_symbols = sorted(
        {symbol.name for symbol in link90.symbols
         if symbol.bytes > 0 and symbol.section in baseline_sections})
    expected_far = contract["mapped_far_service"]["bank2"]["service_bytes"]
    actual_far = out[".lisp65_c2_mapped_far_service"]["bytes"]
    ordinary_limit = int(
        contract["geometry"]["ordinary_bss_limit"], 0)
    zp_limit = int(first_red["live_set"]["zero_page"]["available_end"], 0)
    zp_owned_end = out[".lisp65_c2_convergence_zp"]["vma"] + 2

    value = {
        "format": "lisp65-c2.3-v1.7-state-ownership-phase-a-inventory-v1",
        "recorded_on": date.today().isoformat(),
        "status": "passed-read-only-state-truth",
        "claim": "Inventory and exact deficit truth only; no layout candidate, product build, WPLTO, source annotation, link identity or hardware claim.",
        "authorities": {
            "plan": bind(PLAN),
            "link90_final_ELF": bind(LINK90_ELF),
            "failed_product_LTO_object": bind(FAILED_LTO),
            "failed_final_map": bind(FAILED_MAP),
            "failed_generated_linker": bind(FAILED_LINKER),
            "failed_link_stderr": bind(FAILED_STDERR),
            "phase_D_First_Red": bind(FIRST_RED),
            "v15_ownership_contract": bind(V15_CONTRACT),
            "tool": bind(Path(__file__).resolve()),
        },
        "execution_witness": {
            "input_sections_enumerated": len(rows),
            "families_reconciled": len(families),
            "link90_state_symbols_bound": len(baseline_state_symbols),
            "negative_mutations": 5,
        },
        "failed_product_input_state": rows,
        "families": families,
        "link90_baseline": {
            "sections": baseline_sections,
            "state_symbols": baseline_state_symbols,
        },
        "failed_product_live_set": {
            "ordinary_bank0_bss": {
                **interval(bss),
                "contract_limit": f"0x{ordinary_limit:04x}",
                "available_before_limit": ordinary_limit - bss["vma"],
                "overshoot_bytes": bss["vma"] + bss["bytes"] - ordinary_limit,
            },
            "convergence_state": interval(convergence),
            "static_stack": interval(stack),
            "fixed_c2_bank0_including_code": interval(fixed),
            "workbench_overlay": interval(overlay),
            "overlaps": {
                "ordinary_bss_with_convergence": overlap(bss, convergence),
                "ordinary_bss_with_static_stack": overlap(bss, stack),
                "ordinary_bss_with_fixed_c2": overlap(bss, fixed),
                "ordinary_bss_with_overlay": overlap(bss, overlay),
            },
            "zero_page": {
                "ordinary_bytes": families["ordinary-zero-page"]["bytes"],
                "fixed_start": f"0x{out['.lisp65_c2_fixed_zp']['vma']:02x}",
                "fixed_bytes": out[".lisp65_c2_fixed_zp"]["bytes"],
                "unallocated_gap": "0x87..0x89 (2 bytes)",
                "convergence_start": f"0x{out['.lisp65_c2_convergence_zp']['vma']:02x}",
                "convergence_bytes": 2,
                "available_end_exclusive": f"0x{zp_limit:02x}",
                "owned_end_exclusive": f"0x{zp_owned_end:02x}",
                "overflow_bytes": zp_owned_end - zp_limit,
            },
            "far_service": {
                "vma": f"0x{out['.lisp65_c2_mapped_far_service']['vma']:04x}",
                "lma": f"0x{out['.lisp65_c2_mapped_far_service']['lma']:08x}",
                "actual_bytes": actual_far,
                "contract_bytes": expected_far,
                "delta_bytes": actual_far - expected_far,
                "status": "optimizer-sized-contract-drift",
            },
            "overlay_floor": {
                "contract": contract["geometry"]["overlay_floor"],
                "failed_map": first_red["live_set"]["overlay_floor"]["actual"],
                "drift_bytes": first_red["live_set"]["overlay_floor"]["drift_bytes"],
            },
        },
        "raw_geometry_observations_for_phase_B": {
            "not_layout_claims": True,
            "baseline_bss_start_to_convergence_start": {
                "start": baseline_sections[".bss"]["start"],
                "end_exclusive": "0xc000",
                "capacity_bytes": 0xC000 - link90.section(".bss").address,
                "failed_input_demand_bytes": families["ordinary-bank0-bss"]["bytes"],
                "raw_remainder_bytes": (0xC000 - link90.section(".bss").address
                                        - families["ordinary-bank0-bss"]["bytes"]),
            },
            "zero_page_gap_0x87_0x89": {
                "capacity_bytes": 2,
                "convergence_demand_bytes": 2,
            },
            "bank0_gaps": [
                {"start": "0xc042", "end_exclusive": "0xc074", "bytes": 50},
                {"start": "0xc07a", "end_exclusive": "0xc080", "bytes": 6},
                {"start": "0xc34d", "end_exclusive": "0xc354", "bytes": 7},
            ],
            "far_contract_slack_is_not_identity": 66,
        },
        "phase_B_obligations": [
            "Assign every currently ordinary/unowned input state section exactly one semantic owner and arena.",
            "Bind zero/init/preservation semantics for every arena; placement alone is insufficient.",
            "Price Bank-0 and ZP as simultaneous-live maps, including deliberate gaps.",
            "Make far-body code identity and size optimizer-independent; a smaller LTO result is still contract-red.",
            "Use independent contract constants as gate expectations, never values read from the linker under test.",
        ],
    }
    validate(value)
    return value


def validate(value: dict[str, Any]) -> None:
    families = value["families"]
    expected = {
        "ordinary-bank0-bss": (54, 1585),
        "ordinary-zero-page": (3, 101),
        "convergence-bank0-state": (4, 66),
        "convergence-zero-page": (2, 2),
        "fixed-c2-bank0-state": (7, 648),
        "compiler-static-stack": (1, 6),
        "mapped-far-service-body": (1, 1433),
    }
    require(set(families) == set(expected), "state family missing or added")
    for name, (sections, size) in expected.items():
        require((families[name]["input_sections"], families[name]["bytes"])
                == (sections, size), f"state family reconciliation drift: {name}")
    rows = value["failed_product_input_state"]
    require(len({row["id"] for row in rows}) == len(rows),
            "duplicate state input identity")
    require(all(len(row["semantic_owners"]) <= 1 for row in rows),
            "state input has multiple semantic owners")
    live = value["failed_product_live_set"]
    require(live["ordinary_bank0_bss"]["overshoot_bytes"] == 1089,
            "Bank-0 deficit truth drift")
    require(live["zero_page"]["overflow_bytes"] == 2,
            "zero-page deficit truth drift")
    far = live["far_service"]
    require((far["actual_bytes"], far["contract_bytes"], far["delta_bytes"],
             far["status"]) ==
            (1433, 1499, -66, "optimizer-sized-contract-drift"),
            "far-body contract drift hidden")
    require(live["overlaps"] == {
        "ordinary_bss_with_convergence": 66,
        "ordinary_bss_with_static_stack": 6,
        "ordinary_bss_with_fixed_c2": 717,
        "ordinary_bss_with_overlay": 363,
    }, "simultaneous-live overlap truth drift")


def selftest() -> None:
    base = build()
    mutations = []
    row = deepcopy(base)
    del row["families"]["ordinary-bank0-bss"]
    mutations.append(("missing-family", row))
    row = deepcopy(base)
    row["failed_product_input_state"][0]["semantic_owners"] = ["one", "two"]
    mutations.append(("double-owner", row))
    row = deepcopy(base)
    row["failed_product_live_set"]["ordinary_bank0_bss"]["overshoot_bytes"] = 0
    mutations.append(("hidden-bank0-deficit", row))
    row = deepcopy(base)
    row["failed_product_live_set"]["zero_page"]["overflow_bytes"] = 0
    mutations.append(("hidden-zp-deficit", row))
    row = deepcopy(base)
    row["failed_product_live_set"]["far_service"].update(
        {"actual_bytes": 1499, "delta_bytes": 0, "status": "exact"})
    mutations.append(("optimizer-size-called-exact", row))
    rejected = 0
    for name, row in mutations:
        try:
            validate(row)
        except FirstRed:
            rejected += 1
        else:
            raise FirstRed(f"selftest mutation survived: {name}")
    require(rejected == 5, "selftest execution count drift")
    print("c2-v17-state-ownership-phase-a: SELFTEST PASS mutations=5")


def run() -> None:
    value = build()
    RECEIPT.write_bytes(canonical(value))
    print("c2-v17-state-ownership-phase-a: PASS "
          f"inputs={value['execution_witness']['input_sections_enumerated']} "
          "families=7 bank0-deficit=1089 zp-deficit=2 far-delta=-66")


def check() -> None:
    value = build()
    require(RECEIPT.is_file() and RECEIPT.read_bytes() == canonical(value),
            "Phase-A inventory receipt drift")
    print("c2-v17-state-ownership-phase-a: PASS "
          f"inputs={value['execution_witness']['input_sections_enumerated']} "
          "families=7 bank0-deficit=1089 zp-deficit=2 far-delta=-66")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) == 2 else ""
    try:
        if action == "selftest":
            selftest()
        elif action == "run":
            run()
        elif action == "check":
            check()
        else:
            print(f"usage: {Path(sys.argv[0]).name} <selftest|run|check>",
                  file=sys.stderr)
            return 2
    except (FirstRed, KeyError, ValueError, OSError) as error:
        print(f"c2-v17-state-ownership-phase-a: FIRST RED: {error}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
