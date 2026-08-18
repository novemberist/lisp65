#!/usr/bin/env python3
"""Price the three owner-commissioned Link-107 CPU-reader call seams."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
FINAL_RED = ARCH / "c2.3-v2.1-cpu-transport-shrink-card-final-red.json"
RECEIPT = ARCH / "c2.3-v2.1-call-seam-pricing-receipt.json"
BUILD = ROOT / "build/c2.3/v2.1-cpu-transport-shrink-card/wplto"
ELF = BUILD / "lisp65-c2-substitution-linked.prg.elf"
MAP = BUILD / "lisp65-c2-substitution-linked.prg.map"
READER = ROOT / "src/optional/c2_map_cpu_read.s"
FACADE = ROOT / "src/c2_kernal_facade.s"
FACADE_EXT = ROOT / "src/c2_kernal_facade_reopen.s"
RUNTIME = ROOT / "src/c2_product_runtime.c"
RUNTIME_HEADER = ROOT / "src/c2_product_runtime.h"
PRODUCT = ROOT / "tools/host-lisp/c2_product_substitution_link.py"
OWNERSHIP = ROOT / "config/c2-full-map-ownership-contract.json"
BLACKBOX = ROOT / "config/c2-fail-closed-blackbox-contract.json"
DRIVER = Path(__file__).resolve()
LLVM = ROOT / "tools/llvm-mos/bin"
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402

AUTHORIZATION = "44b790b8"
RECORDED_ON = "2026-08-14"

VECTORS = (
    "c2_facade_vm_code_load",
    "c2_facade_c2_dma",
    "c2_facade_overlay_call_family",
    "c2_facade_c2e_cons",
    "c2_facade_c2e_overlay",
    "c2_facade_car",
    "c2_facade_cdr",
    "c2_facade_gc_collect",
    "c2_facade_str_open",
    "c2_facade_str_putc",
    "c2_facade_intern",
    "c2_facade_select_family",
    "c2_facade_gc_mark",
    "c2_facade_runtime_overlay_exec",
    "c2_facade_handle_normalize",
    "c2_facade_append_plan_walk",
)
VECTOR_BASE = 0xB5C4
VECTOR_STRIDE = 3


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


def run(*argv: str) -> str:
    return subprocess.run(argv, cwd=ROOT, check=True, text=True,
                          stdout=subprocess.PIPE).stdout


def git_blob(commit: str, path: Path) -> tuple[bytes, dict[str, Any]]:
    name = path.relative_to(ROOT).as_posix()
    full = run("git", "rev-parse", f"{commit}^{{commit}}").strip()
    raw = subprocess.run(["git", "show", f"{full}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    return raw, {"authority": "git-blob", "commit": full, "path": name,
                 "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    raw, authority = git_blob(AUTHORIZATION, PLAN)
    text = " ".join(raw.decode().split()).lower()
    for token in (
            "call-seam pricing commissioned",
            "ride an existing crossing",
            "a new fixed vector",
            "relocate the reader into the mapped far service",
            "no card, media or device before the seam is decided"):
        require(token in text, f"call-seam authorization token absent: {token}")
    return authority


def sections(truth: ElfTruth) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for row in truth.sections:
        require(row.name not in result, f"duplicate linked section: {row.name}")
        result[row.name] = {"address": row.address, "bytes": row.bytes}
    for name in (".text", ".lisp65_c2_mapped_far_facade",
                 ".lisp65_c2_mapped_far_service", ".lisp65_c2_host_facade",
                 ".lisp65_c2_kernal_io_reveal",
                 ".lisp65_c2_kernal_map_switch",
                 ".lisp65_c2_kernal_state", ".rodata"):
        require(name in result, f"linked section absent: {name}")
    return result


def symbols(truth: ElfTruth) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for name, rows in truth.symbols_by_name.items():
        if len(rows) == 1:
            result[name] = {"address": rows[0].value, "bytes": rows[0].bytes}
    for name in (*VECTORS, "c2_map_cpu_read", "c2_stream_c2d_read",
                 "c2_stream_shelf_read"):
        require(name in result, f"linked symbol absent: {name}")
    return result


def direct_transfers() -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    text = run(str(LLVM / "llvm-objdump"), "-d", str(ELF))
    addresses = {VECTOR_BASE + index * VECTOR_STRIDE: name
                 for index, name in enumerate(VECTORS)}
    refs = {name: [] for name in VECTORS}
    low_reader: list[dict[str, Any]] = []
    pattern = re.compile(
        r"^\s*([0-9a-fA-F]+):\s+(?:[0-9a-fA-F]{2}\s+)+"
        r"(jsr|jmp)\s+\$([0-9a-fA-F]+)\b", re.M)
    for match in pattern.finditer(text):
        source = int(match.group(1), 16)
        target = int(match.group(3), 16)
        row = {"source": f"0x{source:04x}", "instruction": match.group(2),
               "target": f"0x{target:04x}"}
        if target in addresses:
            refs[addresses[target]].append(row)
        if source >= 0xE000 and target == 0x2277:
            low_reader.append(row)
    require(low_reader == [
        {"source": "0xe326", "instruction": "jsr", "target": "0x2277"},
        {"source": "0xe84b", "instruction": "jsr", "target": "0x2277"}],
        "linked E000 CPU-reader edge identity drift")
    return refs, low_reader


def fixed_inventory(sec: dict[str, dict[str, int]],
                    sym: dict[str, dict[str, int]]) -> dict[str, Any]:
    host = sec[".lisp65_c2_host_facade"]
    following = sec[".lisp65_c2_kernal_io_reveal"]
    require(host == {"address": 0xB5C4, "bytes": 48}
            and following["address"] == 0xB5F4
            and host["address"] + host["bytes"] == following["address"],
            "fixed facade no-gap geometry drift")
    for index, name in enumerate(VECTORS):
        require(sym[name]["address"] == VECTOR_BASE + index * VECTOR_STRIDE,
                f"fixed vector address drift: {name}")
    source = FACADE.read_text(encoding="utf-8") + FACADE_EXT.read_text(encoding="utf-8")
    for name in VECTORS:
        require(f"{name}:" in source, f"fixed vector source identity absent: {name}")
    return {
        "status": "PASS: sixteen named vectors occupy every byte before IO reveal",
        "base": "0xb5c4", "vector_count": 16, "vector_bytes": 48,
        "end_exclusive": "0xb5f4", "next_owner": ".lisp65_c2_kernal_io_reveal",
        "next_owner_address": "0xb5f4", "contiguous_free_bytes": 0,
        "vectors": [{"name": name,
                     "address": f"0x{sym[name]['address']:04x}"}
                    for name in VECTORS],
    }


def source_domains() -> dict[str, Any]:
    header = RUNTIME_HEADER.read_text(encoding="utf-8")
    expected = {
        "C2D/Bank-5": ("LISP65_C2D_BANK", "5u"),
        "Shelf": ("LISP65_C2_SHELF_PHYSICAL", "0x08100000UL"),
        "Session": ("LISP65_C2_SESSION_PHYSICAL", "0x08400000UL"),
    }
    for _, (name, value) in expected.items():
        require(re.search(rf"#define\s+{name}\s+{re.escape(value)}\b", header),
                f"CPU source-domain authority drift: {name}")
    return {name: value for name, (_, value) in expected.items()}


def pricing(sec: dict[str, dict[str, int]], sym: dict[str, dict[str, int]],
            refs: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    text = sec[".text"]
    text_end = text["address"] + text["bytes"]
    ordinary_free = sec[".lisp65_c2_mapped_far_facade"]["address"] - text_end
    reader_bytes = sym["c2_map_cpu_read"]["bytes"]
    far = sec[".lisp65_c2_mapped_far_service"]
    ownership = load(OWNERSHIP)
    contract_far = next(row for row in ownership["generated_linker_requirements"]
                        ["final_section_inventory_additions"]
                        if row["name"] == ".lisp65_c2_mapped_far_service")
    require(ordinary_free == 1 and reader_bytes == 166
            and far == {"address": 0x78B2, "bytes": 874}
            and contract_far["bytes"] == 874,
            "linked capacity authority drift")

    selector_control_min = 7  # 2-byte compare + long conditional (2+3).
    existing = {
        "status": "REJECTED: preserving selector does not fit current ordinary text",
        "best_semantic_seam": "c2_facade_runtime_overlay_exec@0xb5eb",
        "why_best": "slot/context ABI is the only existing selector-shaped seam",
        "fixed_bytes_added": 0,
        "ordinary_control_lower_bound_bytes": selector_control_min,
        "ordinary_bytes_available": ordinary_free,
        "ordinary_deficit_lower_bound_bytes": selector_control_min - ordinary_free,
        "lower_bound_excludes": ["reader-ABI marshalling", "context storage",
                                 "selector setup at both E000 callers"],
        "direct_linked_references": len(refs["c2_facade_runtime_overlay_exec"]),
        "zero_direct_references_do_not_free_contract": True,
        "direct_reassignment_allowed": False,
        "reason": (
            "All sixteen addresses retain named semantic ABI identities. A direct "
            "retarget would retire runtime_overlay_exec, not share it. Preserving it "
            "requires at least compare plus long branch before the old path; nested "
            "overlay dispatch is also illegal from the transported E000 phase."),
    }
    new_vector = {
        "status": "REJECTED: three fixed bytes collide with the next fixed owner",
        "fixed_bytes_added": 3, "fixed_bytes_available": 0,
        "fixed_deficit_bytes": 3,
        "would_start": "0xb5f4",
        "collides_with": ".lisp65_c2_kernal_io_reveal@0xb5f4",
        "historical_precedent": bind(BLACKBOX),
        "risk": (
            "Insertion would reanchor IO reveal, MAP switch, fixed state and rodata; "
            "their pinned identities are not freight budgets."),
    }
    far_move = {
        "status": "REJECTED: owner-contract overflow and self-unmapping code",
        "ordinary_bytes_delta": -reader_bytes,
        "far_service_bytes_before": far["bytes"],
        "far_service_bytes_added": reader_bytes,
        "far_service_bytes_after": far["bytes"] + reader_bytes,
        "far_service_contract_bytes": contract_far["bytes"],
        "contract_overflow_bytes": reader_bytes,
        "execution_window": "CPU block 3 ($6000..$7fff)",
        "reader_target_window": "CPU block 2 ($4000..$5fff)",
        "disjoint_blocks_are_not_sufficient": True,
        "hidden_callee_proof": (
            "The reader first executes MAP with A=0,X=0,Z=$80, disabling every "
            "low block before changing the low-half megabyte selector. From block 3 "
            "its next instruction is therefore fetched outside its own body."),
        "shared_selector_proof": (
            "The body is installed at physical $02b8b2 while admitted sources span "
            "Bank 5 and physical $08100000/$08400000. One low-half megabyte selector "
            "cannot keep block 3 on the body while block 2 follows all source domains."),
    }
    return {
        "linked_capacity": {
            "ordinary_text_end_exclusive": f"0x{text_end:04x}",
            "mapped_far_facade_start": "0xb3b0",
            "ordinary_bytes_available": ordinary_free,
            "reader_address": f"0x{sym['c2_map_cpu_read']['address']:04x}",
            "reader_bytes": reader_bytes,
        },
        "candidate_1_existing_selector": existing,
        "candidate_2_new_fixed_vector": new_vector,
        "candidate_3_reader_in_far_service": far_move,
        "decision": {
            "status": "NONE-OF-THREE-FITS",
            "recommended_card": None,
            "owner_disposition_required": True,
            "least_expensive_preserving_shape": (
                "free at least six additional ordinary bytes, then multiplex the "
                "existing runtime-overlay-exec vector without changing its identity"),
            "separate_zero_byte_shape_requiring_new_authority": (
                "prove full shipped-world retirement of an unused fixed ABI identity, "
                "then reassign its three-byte vector; direct-reference absence alone "
                "is not retirement proof"),
        },
    }


def validate(value: dict[str, Any]) -> None:
    require(value["status"] == "PRICED: NONE OF THREE CALL SEAMS FITS"
            and value["attempt_accounting"] == {
                "cards_consumed": 0, "WPLTO_runs": 0, "product_links": 0,
                "media_builds": 0, "device_contacts": 0},
            "desk-only accounting drift")
    p = value["pricing"]
    require(p["candidate_1_existing_selector"]["status"].startswith("REJECTED:")
            and p["candidate_1_existing_selector"]["direct_reassignment_allowed"] is False
            and p["candidate_1_existing_selector"]["ordinary_deficit_lower_bound_bytes"] == 6
            and p["candidate_2_new_fixed_vector"]["status"].startswith("REJECTED:")
            and p["candidate_2_new_fixed_vector"]["fixed_deficit_bytes"] == 3
            and p["candidate_3_reader_in_far_service"]["status"].startswith("REJECTED:")
            and p["candidate_3_reader_in_far_service"]["contract_overflow_bytes"] == 166
            and p["decision"]["recommended_card"] is None
            and p["decision"]["owner_disposition_required"] is True,
            "call-seam result widened or weakened")
    require(value["fixed_facade"]["contiguous_free_bytes"] == 0
            and len(value["fixed_facade"]["vectors"]) == 16,
            "fixed facade occupancy weakened")


def mutations(value: dict[str, Any]) -> list[str]:
    cases = {
        "treat-zero-xref-vector-as-free": lambda x: x["pricing"]
            ["candidate_1_existing_selector"].update(direct_reassignment_allowed=True),
        "erase-selector-deficit": lambda x: x["pricing"]
            ["candidate_1_existing_selector"].update(ordinary_deficit_lower_bound_bytes=0),
        "invent-fixed-byte": lambda x: x["fixed_facade"].update(
            contiguous_free_bytes=1),
        "erase-new-vector-deficit": lambda x: x["pricing"]
            ["candidate_2_new_fixed_vector"].update(fixed_deficit_bytes=0),
        "erase-far-overflow": lambda x: x["pricing"]
            ["candidate_3_reader_in_far_service"].update(contract_overflow_bytes=0),
        "accept-self-unmap": lambda x: x["pricing"]
            ["candidate_3_reader_in_far_service"].update(
                status="ACCEPTED despite self-unmap"),
        "authorize-card": lambda x: x["pricing"]["decision"].update(
            recommended_card="candidate-1", owner_disposition_required=False),
        "invent-card-run": lambda x: x["attempt_accounting"].update(cards_consumed=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate(candidate)
        except PricingError:
            rejected.append(name)
    require(rejected == list(cases), "call-seam pricing mutation survived")
    return rejected


def derive() -> dict[str, Any]:
    red = load(FINAL_RED)
    require(red.get("status") == "FINAL RED: CPU-reader shrink card returns to owner"
            and red.get("retry_authorized") is False
            and red.get("owner_disposition_required") is True,
            "CPU-reader shrink Final Red authority drift")
    truth = ElfTruth.read(ELF, llvm_readobj=LLVM / "llvm-readobj")
    sec = sections(truth)
    sym = symbols(truth)
    refs, low_reader = direct_transfers()
    value = {
        "format": "lisp65-c2.3-v2.1-call-seam-pricing-v1",
        "recorded_on": RECORDED_ON,
        "status": "PRICED: NONE OF THREE CALL SEAMS FITS",
        "authority": {
            "commission": authorization(), "final_red": bind(FINAL_RED),
            "linked_ELF": bind(ELF), "linked_map": bind(MAP),
            "reader": bind(READER), "facade": bind(FACADE),
            "facade_extensions": bind(FACADE_EXT), "runtime": bind(RUNTIME),
            "runtime_header": bind(RUNTIME_HEADER), "ownership": bind(OWNERSHIP),
            "product_linker": bind(PRODUCT), "driver": bind(DRIVER),
        },
        "fixed_facade": fixed_inventory(sec, sym),
        "direct_vector_references": {
            name: {"count": len(rows), "rows": rows} for name, rows in refs.items()},
        "rejected_E000_edges": low_reader,
        "source_domains": source_domains(),
        "pricing": pricing(sec, sym, refs),
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
                               "product_links": 0, "media_builds": 0,
                               "device_contacts": 0},
        "claim_limit": (
            "Host/ELF pricing only. No facade retirement, source change, card, "
            "product, media, device or runtime claim."),
    }
    validate(value)
    value["mutations_rejected"] = mutations(value)
    return value


def main() -> int:
    value = derive()
    RECEIPT.write_bytes(canonical(value))
    print("c2-v2.1-call-seam-pricing: PASS none-fits mutations=8 cards=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
