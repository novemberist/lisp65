#!/usr/bin/env python3
"""Price the v1.6 nested-MAP witness repair without building a product."""

from __future__ import annotations

from copy import deepcopy
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

import c2_transitive_map_nesting_gate as NEST  # noqa: E402
import evidence_era as ERA  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = ARCH / "c2.3-v1.6-nested-map-repricing.json"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
ELF = ROOT / ("build/c2.3/v1.6-refill-boundary-witness-media-repair-"
              "replacement/canonical-product/final/"
              "lisp65-c2-substitution-linked.prg.elf")
WITNESS = ROOT / "src/optional/c2_refill_boundary_witness.s"
RUNTIME = ROOT / "src/vm_runtime_overlay.c"
IO = ROOT / "src/io.c"
PROGRESS = ROOT / "src/optional/c2_map_cpu_read.s"
CLANG = ROOT / "tools/llvm-mos/bin/mos-clang"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
RECORDED_ON = "2026-08-22"
STATUS = "PRICED: VISIBLE INSTALLER VIA COLD DISK-CHAIN SWAP"
SEALED_COMMIT = "c1c08bb2"


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def bind_git_blob(commit: str, path: Path) -> dict[str, Any]:
    relative = path.relative_to(ROOT).as_posix()
    completed = subprocess.run(
        ["git", "show", f"{commit}:{relative}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    raw = completed.stdout
    return {"authority": "git-blob", "commit": commit, "path": relative,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def sealed_tool_authorities() -> dict[str, dict[str, Any]]:
    """Reconstruct historical producer identities in their sealing era."""
    return {
        "witness_source": ERA.era_bind(SEALED_COMMIT, WITNESS),
        "runtime_source": ERA.era_bind(SEALED_COMMIT, RUNTIME),
        "disk_source": ERA.era_bind(SEALED_COMMIT, IO),
        "progress_source": ERA.era_bind(SEALED_COMMIT, PROGRESS),
        "transitive_gate": ERA.era_bind(
            SEALED_COMMIT,
            ROOT / "tools/host-lisp/c2_transitive_map_nesting_gate.py"),
        "pricing_tool": ERA.era_bind(SEALED_COMMIT, Path(__file__).resolve()),
    }


def sealed_tool_authority_gate(authority: dict[str, Any]) -> None:
    require(all(authority.get(name) == binding
                for name, binding in sealed_tool_authorities().items()),
            "sealed pricing tool identity collapsed onto the living tree")


def sealed_tool_authority_mutation() -> str:
    authority: dict[str, Any] = sealed_tool_authorities()
    authority["disk_source"] = bind(IO)
    try:
        sealed_tool_authority_gate(authority)
    except PricingError:
        return "collapse-sealed-disk-source-to-working-tree"
    raise PricingError("living-source collapse mutation survived")


def sealed_receipt_gate(raw: bytes) -> None:
    """Keep the accepted pricing witness byte-identical to its sealing era.

    The candidate enumeration is a historical observation made by the graph
    implementation of that era.  Later domain-aware graph work may derive a
    different closure over the same frozen ELF; that living derivation belongs
    to the current graph gates, not to this sealed pricing witness.
    """
    require(raw == ERA.era_blob(SEALED_COMMIT,
                                RECEIPT.relative_to(ROOT).as_posix()),
            "sealed nested-MAP pricing receipt was rewritten")


def sealed_receipt_mutation() -> str:
    raw = RECEIPT.read_bytes()
    try:
        sealed_receipt_gate(raw + b"\n")
    except PricingError:
        return "rewrite-sealed-pricing-witness"
    raise PricingError("sealed pricing witness rewrite mutation survived")


def _depth_counter_price() -> dict[str, Any]:
    source = r'''
.section .text,"ax",@progbits
.globl priced_enter
.type priced_enter,@function
priced_enter:
 pha
 lda priced_depth
 bne .Lnested
 inc priced_depth
 phx
 phy
 lda #$40
 ldx #$82
 ldy #$00
 ldz #$80
 map
 eom
 ply
 plx
 bra .Lenter_done
.Lnested:
 inc priced_depth
.Lenter_done:
 pla
 ldz #$00
 rts
.size priced_enter,.-priced_enter
.globl priced_leave
.type priced_leave,@function
priced_leave:
 pha
 dec priced_depth
 bne .Lleave_done
 lda #$00
 ldx #$00
 ldy #$00
 ldz #$80
 map
 eom
.Lleave_done:
 pla
 ldz #$00
 rts
.size priced_leave,.-priced_leave
.section .bss,"aw",@nobits
priced_depth: .space 1
'''
    with tempfile.TemporaryDirectory(prefix="c2-map-depth-price-") as raw:
        root = Path(raw)
        asm, obj = root / "depth.s", root / "depth.o"
        asm.write_text(source, encoding="utf-8")
        completed = subprocess.run(
            [str(CLANG), "-c", "-mcpu=mos45gs02", str(asm), "-o", str(obj)],
            cwd=ROOT, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)
        require(completed.returncode == 0,
                "depth counter assembly red:\n" + completed.stdout)
        truth = NEST.ElfTruth.read(obj, llvm_readobj=READOBJ)
    enter, leave = truth.symbol("priced_enter"), truth.symbol("priced_leave")
    require((enter.bytes, leave.bytes) == (32, 20),
            "depth counter emitted size drift")
    return {
        "enter_bytes": enter.bytes,
        "leave_bytes": leave.bytes,
        "current_enter_leave_bytes": 19 + 15,
        "facade_growth_bytes": enter.bytes + leave.bytes - 34,
        "state_bytes": 1,
        "outer_pair_incremental_cycles": 23,
        "cycle_basis": ("absolute LDA/INC plus not-taken BNE and BRA on enter; "
                        "absolute DEC plus not-taken BNE on leave"),
        "facade_padding_bytes": 0,
        "verdict": ("DOMINATED: +18 fixed-facade bytes do not fit, one new "
                    "state byte is required, and every ordinary MAP pair pays "
                    "+23 cycles before any nesting benefit"),
    }


def _closure(graph: dict[str, Any], root: str) -> set[str]:
    seen: set[str] = set()
    pending = [root]
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        pending.extend(set(graph["edges"].get(name, ())) - seen)
    return seen


def _candidate_rows(graph: dict[str, Any]) -> list[dict[str, Any]]:
    truth = graph["truth"]
    values = []
    for symbol in truth.symbols:
        if symbol.symbol_type != "Function" or symbol.section != ".text" \
                or not 211 <= symbol.bytes <= 371:
            continue
        closure = _closure(graph, symbol.name)
        nested = NEST.paths_to_map(graph, [symbol.name])
        hidden = sorted(name for name in closure if name != symbol.name
                        and 0x6000 <= truth.symbol(name).value < 0x8000)
        values.append({
            "symbol": symbol.name,
            "address": f"0x{symbol.value:04x}",
            "bytes": symbol.bytes,
            "incoming_owners": sorted({row["owner"]
                                        for row in graph["incoming"].get(
                                            symbol.name, [])}),
            "closure_functions": len(closure),
            "nested_MAP_paths": nested,
            "hidden_callees": hidden,
            "structurally_eligible": not nested and not hidden,
        })
    return sorted(values, key=lambda row: (row["bytes"], row["symbol"]))


def compute() -> dict[str, Any]:
    graph = NEST.linked_graph(ELF)
    current = NEST.analyze(ELF)
    installer = graph["truth"].symbol("vm_runtime_overlay_install_island_far")
    disk = graph["truth"].symbol("disk_chain_to_scratch")
    require(installer.bytes == 211 and installer.section ==
            ".lisp65_c2_mapped_diagnostic", "installer final identity drift")
    require(disk.bytes == 324 and disk.section == ".text",
            "disk-chain swap candidate identity drift")
    require(len(current["violations"]) == 2
            and {row["terminal"] for row in current["violations"]}
            == {NEST.ENTER, NEST.LEAVE}
            and {row["mapped_body"] for row in current["violations"]}
            == {installer.name}, "current nested-MAP mechanism drift")
    disk_paths = NEST.paths_to_map(graph, [disk.name])
    disk_closure = _closure(graph, disk.name)
    hidden = sorted(name for name in disk_closure if name != disk.name
                    and 0x6000 <= graph["truth"].symbol(name).value < 0x8000)
    require(disk_paths == [] and hidden == [] and len(disk_closure) == 4,
            "disk-chain swap is not MAP-blind")

    current_text_free = 3
    stub_bytes = 9
    proposed_text_free = (current_text_free - installer.bytes + stub_bytes
                          + disk.bytes - stub_bytes)
    proposed_diagnostic_used = disk.bytes
    proposed_diagnostic_free = 371 - proposed_diagnostic_used
    require(proposed_text_free == 116 and proposed_diagnostic_free == 47,
            "structural swap arithmetic drift")

    # Simulate the post-swap mapped population: the service tenants stay;
    # installer leaves the population and disk-chain becomes the sole tenant
    # of the diagnostic arena.
    service = [name for name in graph["tenants"]
               if graph["truth"].symbol(name).section ==
               ".lisp65_c2_mapped_far_service"]
    proposed_tenants = sorted({*service, disk.name})
    proposed_violations = NEST.paths_to_map(graph, proposed_tenants)
    require(proposed_violations == [], "proposed swap retains MAP nesting")
    injected = NEST.paths_to_map(
        graph, [disk.name], injected_edges={disk.name: {NEST.ENTER}})
    require(bool(injected), "transitive nested-MAP mutation survived")

    candidates = _candidate_rows(graph)
    by_name = {row["symbol"]: row for row in candidates}
    require(by_name[disk.name]["structurally_eligible"]
            and by_name["gc_mark1"]["structurally_eligible"]
            and by_name["vm_fixbinop"]["structurally_eligible"],
            "candidate enumeration drift")

    progress = PROGRESS.read_text(encoding="utf-8")
    require("sta $0b3a" in progress and "adc #$30" in progress
            and "LISP65_BOOT_PROGRESS_LIBRARIES" not in progress,
            "visible-zero writer attribution drift")
    io_source = IO.read_text(encoding="utf-8")
    require(io_source.count("disk_chain_to_scratch(") >= 4
            and "while (t)" in io_source, "disk-chain source role drift")

    depth = _depth_counter_price()
    result = {
        "format": "lisp65-c2.3-v1.6-nested-map-repricing-v1",
        "recorded_on": RECORDED_ON,
        "status": STATUS,
        "authority": {
            "review_plan": bind_git_blob("2ee49053", PLAN),
            "final_candidate_ELF": bind(ELF),
            **sealed_tool_authorities(),
        },
        "current_final_world": {
            "derived_wrappers": current["wrappers"],
            "derived_mapped_sections": current["mapped_sections"],
            "derived_tenant_count": current["tenant_count"],
            "derived_tenants": current["tenants"],
            "violations": current["violations"],
            "mechanism": ("mapped installer reaches the ordinary transaction "
                          "wrapper, whose inner leave restores baseline before "
                          "the installer resumes at $7EF0"),
        },
        "candidate_enumeration": candidates,
        "winner": {
            "form": "cold ordinary-body swap",
            "visible_body": {
                "symbol": "vm_runtime_overlay_install_island",
                "restored_body_bytes": installer.bytes,
                "old_stub_bytes_removed": stub_bytes,
                "placement": "ordinary text; permanently visible",
            },
            "mapped_replacement": {
                "symbol": disk.name,
                "body_bytes": disk.bytes,
                "ordinary_stub_bytes": stub_bytes,
                "incoming_owners": by_name[disk.name]["incoming_owners"],
                "transitive_closure": sorted(disk_closure),
                "nested_MAP_paths": disk_paths,
                "hidden_callees": hidden,
                "temperature": ("one wrapper per disk-chain staging request; "
                                "no refill, key, arithmetic or evaluator edge"),
            },
            "post_swap_capacity": {
                "ordinary_text_free_bytes": proposed_text_free,
                "mapped_diagnostic_used_bytes": proposed_diagnostic_used,
                "mapped_diagnostic_free_bytes": proposed_diagnostic_free,
                "mapped_far_service_free_bytes": 15,
                "largest_E000_hole_bytes": 49,
                "facade_bytes": 98,
                "facade_padding_bytes": 0,
            },
            "post_swap_mapped_tenants": proposed_tenants,
            "post_swap_nested_MAP_paths": proposed_violations,
        },
        "depth_counting_alternative": depth,
        "permanent_gate": {
            "population": ("wrapper-derived body sections and every sized "
                           "function tenant in those sections"),
            "claim": "no mapped tenant transitively reaches MAP enter/leave",
            "current_red_paths": len(current["violations"]),
            "proposed_paths": len(proposed_violations),
            "mutations_rejected": [
                "reachable-nested-enter",
                "restore-installer-as-mapped-tenant",
            ],
            "linked_ownership_dependency": ("existing gate rejects direct "
                                            "entry into mapped body sections "
                                            "without a derived wrapper"),
        },
        "visible_zero_attribution": {
            "status": "ATTRIBUTED: EARLY PRODUCT-LIVENESS ORDINAL",
            "writer": "c2_map_cpu_read",
            "store": "$0B3A (row 10, column 26)",
            "value": ("phase 0 follows the numeric path and emits screen-code "
                      "$30, visibly '0'"),
            "lifetime": ("the ordinal writer can run during BUILDING HEAP, "
                         "before LOADING LIBRARIES owns row 10; successful boot "
                         "later supplies the line and finally clears the cell"),
            "classification": ("separate screen-lease ordering symptom exposed "
                               "by the boot stop; not a byte-delivery or IRQ fault"),
            "fix_scope": "not part of the MAP placement successor",
        },
        "card_lock": {"product_sources_changed": 0, "WPLTO_runs": 0,
                      "product_links": 0, "media_builds": 0,
                      "device_contacts": 0},
        "claim_boundary": ("Pricing and permanent gate design only.  The "
                           "post-swap geometry is arithmetic over final-ELF "
                           "emission; no product fix or linked candidate is "
                           "claimed."),
    }
    validate(result)
    return result


def validate(value: dict[str, Any]) -> None:
    require(value["status"] == STATUS
            and value["winner"]["post_swap_capacity"] == {
                "ordinary_text_free_bytes": 116,
                "mapped_diagnostic_used_bytes": 324,
                "mapped_diagnostic_free_bytes": 47,
                "mapped_far_service_free_bytes": 15,
                "largest_E000_hole_bytes": 49,
                "facade_bytes": 98,
                "facade_padding_bytes": 0,
            }, "pricing winner drift")
    require(value["winner"]["post_swap_nested_MAP_paths"] == []
            and value["depth_counting_alternative"]["verdict"].startswith(
                "DOMINATED"), "pricing verdict drift")
    require(value["card_lock"] == {"product_sources_changed": 0,
            "WPLTO_runs": 0, "product_links": 0, "media_builds": 0,
            "device_contacts": 0}, "host-only card lock drift")
    sealed_tool_authority_gate(value["authority"])


def mutations(value: dict[str, Any]) -> list[str]:
    cases = {
        "accept-nested-path": lambda row: row["winner"].update(
            post_swap_nested_MAP_paths=[{"path": ["disk", NEST.ENTER]}]),
        "restore-hot-depth-default": lambda row: row[
            "depth_counting_alternative"].update(verdict="WINNER"),
        "pin-old-installer-placement": lambda row: row["winner"][
            "visible_body"].update(placement="$7E8D"),
        "erase-visible-zero": lambda row: row.update(
            visible_zero_attribution={}),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate(trial)
            require(trial["winner"]["visible_body"]["placement"] ==
                    "ordinary text; permanently visible",
                    "installer placement is not visible")
            require(trial["visible_zero_attribution"]["status"].startswith(
                    "ATTRIBUTED"), "visible zero attribution absent")
        except (PricingError, KeyError):
            rejected.append(name)
    require(rejected == list(cases), "pricing mutation survived")
    return rejected


def write() -> None:
    value = compute()
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")


def check() -> None:
    raw = RECEIPT.read_bytes()
    sealed_receipt_gate(raw)
    observed = json.loads(raw)
    observed_mutations = observed.pop("mutations_rejected", None)
    validate(observed)
    require(observed_mutations == mutations(observed),
            "nested-MAP pricing mutations drift")
    require(sealed_tool_authority_mutation() ==
            "collapse-sealed-disk-source-to-working-tree",
            "sealed-evidence mutation drift")
    require(sealed_receipt_mutation() == "rewrite-sealed-pricing-witness",
            "sealed receipt mutation drift")


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in ("check", "write", "selftest"):
        print("usage: c2_v160_nested_map_repricing.py check|write|selftest",
              file=sys.stderr)
        return 2
    try:
        if argv[1] == "write":
            write()
        elif argv[1] == "selftest":
            require(sealed_tool_authority_mutation() ==
                    "collapse-sealed-disk-source-to-working-tree",
                    "sealed-evidence mutation drift")
            require(sealed_receipt_mutation() ==
                    "rewrite-sealed-pricing-witness",
                    "sealed receipt mutation drift")
        else:
            check()
    except (PricingError, NEST.GateError, OSError,
            subprocess.CalledProcessError, KeyError, json.JSONDecodeError) as error:
        print(f"v1.6 nested-MAP repricing: FAIL: {error}", file=sys.stderr)
        return 1
    print("v1.6 nested-MAP repricing: PASS winner=disk-chain-swap "
          "text-free=116 diagnostic-free=47 depth=dominated mutations=4 "
          f"era={SEALED_COMMIT} witness=sealed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
