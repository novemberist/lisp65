#!/usr/bin/env python3
"""Price the sealed Capture/Hybrid substrate against the v1.7 release world.

This is a host-only inventory/pricing gate.  It never invokes WPLTO, a
product link, media tooling or a device.  Comfort remains outside its claim.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v160_input_drop_counters as COUNTERS  # noqa: E402
import c2_v160_input_service_hybrid_final_world as FINAL  # noqa: E402
import c2_v160_queue_single_owner_gate as SINGLE_OWNER  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SEALED_RECEIPT = ARCH / \
    "c2.3-v1.7-comfort-phase1b-variant-b-adapter-r1-receipt.json"
RELEASE_RECEIPT = ARCH / "c2.3-v1.7.0-release-card-r1-receipt.json"
D5_RECEIPT = ARCH / "c2.3-v1.7.0-release-d-session-result-receipt.json"
RELEASE_ELF = ROOT / \
    "build/c2.3/v1.7.0-release-card-r1/wplto/lisp65-c2-substitution-linked.prg.elf"
SEALED_ELF = ROOT / \
    "build/c2.3/v1.7-comfort-phase1b-variant-b-adapter-r1/wplto/lisp65-c2-substitution-linked.prg.elf"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
SEAL_COMMIT = "870e5f53"
CORE_SOURCES = (
    "src/optional/c2_kernal_input_capture.s",
    "src/optional/c2_kernal_input_consumer.s",
    "src/interrupt.c",
    "lib/repl-comfort.lisp",
)


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def sealed_blob(path: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{SEAL_COMMIT}:{path}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout


def source_inventory() -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for name in CORE_SOURCES:
        current = (ROOT / name).read_bytes()
        old = sealed_blob(name)
        rows[name] = {"current_sha256": sha(current),
                      "sealed_sha256": sha(old),
                      "byte_identical": current == old}
    require(all(row["byte_identical"] for row in rows.values()),
            "Capture core source changed since the accepted seal")
    repl = (ROOT / "src/repl.c").read_text(encoding="utf-8")
    require("C2K_INPUT_RING_TAIL = 0xff;" in repl,
            "native abort no longer closes capture")
    current_editor = (ROOT / "lib/stdlib-read-line.lisp").read_bytes()
    sealed_editor = sealed_blob("lib/stdlib-read-line.lisp")
    require(current_editor != sealed_editor and b"(defun %rl-poll" in current_editor,
            "expected post-seal Block-3 editor world not present")
    return {"core": rows,
            "native_abort_boundary": "C2K_INPUT_RING_TAIL = 0xff",
            "editor_worlds": {
                "sealed_sha256": sha(sealed_editor),
                "live_sha256": sha(current_editor),
                "same": False,
                "live_successor_member": "%rl-poll",
            }}


def feature_projection() -> dict[str, Any]:
    capture = PRODUCT.configure_input_capture()
    hybrid = PRODUCT.configure_input_hybrid()
    definitions = PRODUCT.input_capture_compile_profile(())
    sources = [Path(row).relative_to(ROOT).as_posix()
               for row in PRODUCT.source_list(definitions)
               if "c2_kernal_input_" in row]
    registry = PRODUCT.input_capture_inventory_registration(definitions)
    require(definitions == ("LISP65_V160_INPUT_CAPTURE",
                            "LISP65_V160_INPUT_HYBRID"),
            "feature fold did not materialize both members")
    require(sources == ["src/optional/c2_kernal_input_capture.s",
                        "src/optional/c2_kernal_input_consumer.s"],
            "real compiler source projection drift")
    require(registry["allocated"] == [
        ".lisp65_c2_kernal_window.input_capture_main",
        ".lisp65_c2_kernal_window.input_capture_helper",
        ".lisp65_c2_kernal_window.input_consumer"],
        "input-fidelity owner registry drift")
    return {"activation": {
                "capture": {"feature": capture["feature"],
                            "sections": capture["sections"]},
                "hybrid": {"feature": hybrid["feature"],
                           "sections": [hybrid["section"]]}},
            "definitions": list(definitions), "compiler_sources": sources,
            "registry": registry,
            "real_consumer": "single_link -> input_capture_compile_profile -> source_list"}


def placement() -> dict[str, Any]:
    current = ElfTruth.read(RELEASE_ELF, llvm_readobj=READOBJ)
    accepted = ElfTruth.read(SEALED_ELF, llvm_readobj=READOBJ)
    gap0 = current.section(".lisp65_c2_kernal_window.reopen_gap0")
    gap1 = current.section(".lisp65_c2_kernal_window.reopen_gap1")
    profile = current.section(".lisp65_c2_kernal_window.profile_rodata")
    state = current.section(".lisp65_c2_kernal_window.state")
    sizes = {name: accepted.section(name).bytes for name in (
        ".lisp65_c2_kernal_window.input_capture_main",
        ".lisp65_c2_kernal_window.input_capture_helper",
        ".lisp65_c2_kernal_window.input_consumer")}
    main_start = gap0.address + gap0.bytes
    helper_start = gap1.address + gap1.bytes
    consumer_start = helper_start + sizes[
        ".lisp65_c2_kernal_window.input_capture_helper"]
    main_free = profile.address - (main_start + sizes[
        ".lisp65_c2_kernal_window.input_capture_main"])
    tail_free = state.address - (consumer_start + sizes[
        ".lisp65_c2_kernal_window.input_consumer"])
    require((main_start, helper_start, consumer_start) ==
            (0xFD08, 0xFEE1, 0xFF09), "derived E000 placement drift")
    require((main_free, tail_free, main_free + tail_free) == (8, 49, 57),
            "derived E000 reserve drift")
    return {"sections": sizes, "total_section_bytes": sum(sizes.values()),
            "derived_addresses": {
                ".lisp65_c2_kernal_window.input_capture_main": main_start,
                ".lisp65_c2_kernal_window.input_capture_helper": helper_start,
                ".lisp65_c2_kernal_window.input_consumer": consumer_start,
            },
            "residual_holes": [{"bytes": main_free,
                                "end_exclusive": profile.address},
                               {"bytes": tail_free,
                                "end_exclusive": state.address}],
            "aggregate_residual_bytes": 57,
            "fixed_floor_bytes": 54, "watch_margin_bytes": 3,
            "ordinary_text_growth_bytes": 0,
            "fixed_state_growth_bytes": 0}


def linked_seal() -> dict[str, Any]:
    _truth, machine, membership = FINAL.linked_consumer(SEALED_ELF)
    normalization = FINAL.normalization_claim(machine, machine.symbols)
    loss = FINAL.loss_claim(machine, machine.symbols)
    return {"ELF": bind(SEALED_ELF), "membership": membership,
            "normalization": normalization,
            "loss": {key: loss[key] for key in (
                "linked_events_drained", "linked_ordered", "linked_dropped",
                "sixth_event", "linked_consumer_cycles")}}


def live_gate_boundary() -> dict[str, Any]:
    return {"status": "EXCLUDED-WORLD-BOUNDARY",
            "reason": "live Block-3 editor is not the sealed Comfort source world",
            "disposition": "product-only Block 2 must not compile or qualify Comfort"}


def derive() -> dict[str, Any]:
    sealed = load(SEALED_RECEIPT)
    release = load(RELEASE_RECEIPT)
    d5 = load(D5_RECEIPT)
    composed = release["final_product"]["recovery_quiescence"]["composed_bank2"]
    free = d5["D5"]["free"]
    require(free == {"symbol_slots": 113, "namepool_bytes": 1506},
            "published D5 world drift")
    require(composed["status"] == "PASS: COMPOSED BANK2 OWNERS ARE DISJOINT"
            and composed["largest_contiguous_hole"]["bytes"] == 16431,
            "published composed Bank-2 world drift")
    require(sealed["status"].endswith("FINAL GREEN"),
            "sealed Capture/Hybrid world is not green")
    shape = COUNTERS.linked_shape()
    require(shape["usable_events"] == 107,
            "live source ring capacity drift")
    queue = SINGLE_OWNER.derive()
    require(queue["status"] == "PASS: ARMED CAPTURE IS SOLE HARDWARE QUEUE OWNER",
            "source-level queue ownership drift")
    value = {
        "format": "lisp65-c2-v18-capture-reopening-pricing-v1",
        "recorded_on": "2026-08-27",
        "status": "HOST-GREEN: CAPTURE/HYBRID PRODUCT SUBSTRATE FITS; LINK CLOSED",
        "authorities": {"sealed_freight": bind(SEALED_RECEIPT),
                        "published_product": bind(RELEASE_RECEIPT),
                        "published_D5": bind(D5_RECEIPT)},
        "source_inventory": source_inventory(),
        "feature_projection": feature_projection(),
        "price": {
            "symbol_capacity_after": free,
            "symbol_floor": {"symbol_slots": 32, "namepool_bytes": 384},
            "symbol_margin_after": {"symbol_slots": 81,
                                    "namepool_bytes": 1122},
            "new_interned_names": [],
            "E000": placement(),
            "bank0_alias": {"base": 0xBC90, "physical_bytes": 112,
                            "ring_index_values": 108,
                            "usable_events": 107, "counter_bytes": 4,
                            "new_allocated_bytes": 0},
            "composed_bank2": {
                "static_plane_bytes": composed["static_plane"]["bytes"],
                "mapped_tenant_bytes": [row["bytes"] for row in
                                        composed["mapped_tenants"]],
                "largest_contiguous_hole_bytes":
                    composed["largest_contiguous_hole"]["bytes"],
                "overlaps": composed["overlaps"],
                "projected_delta_bytes": 0,
                "proof_status": "projection-only-until-authorized-final-link",
            }},
        "live_source_gates": {"counter_shape": shape,
                              "queue_single_owner": queue["model"],
                              "sealed_final_ELF": linked_seal(),
                              "legacy_full_hybrid_gate": live_gate_boundary()},
        "scope": {
            "included": ["LISP65_V160_INPUT_CAPTURE",
                         "LISP65_V160_INPUT_HYBRID",
                         "three native E000 sections", "ring/counter alias",
                         "queue single-owner guard"],
            "excluded": ["repl-comfort", "balanced multiline", "history",
                         "prompt", "display ownership", "Block-3 editor",
                         "media", "device acceptance"]},
        "blockers": [
            {"name": "final-product-materialization",
             "state": "closed",
             "reason": "no WPLTO/product-link authority in this pricing block"},
            {"name": "activation-owner",
             "state": "deferred-with-Comfort",
             "reason": "the sole bound atomic arm/disarm sequence lives in repl-comfort"},
            {"name": "public-key-event-while-armed",
             "state": "must-be-closed-before-user-visible-claim",
             "reason": "public modes 0/1 remain legitimate hardware-queue readers; intended lifecycle must prove capture closed before user evaluation"},
            {"name": "editor-source-authority",
             "state": "known-world-split",
             "reason": "live Block-3 editor cannot be substituted for the sealed Comfort editor"}],
        "recommended_next_card": {
            "kind": "one product-substrate reopening card",
            "requires_owner_link_authority": True,
            "configuration": ["configure_input_capture",
                              "configure_input_hybrid"],
            "must_prove": [
                "both features and both sources reach every real compiler process",
                "three sections occupy the final-image-derived E000 holes",
                "composed Bank-2/MAP owner map remains disjoint",
                "94/94 loss and 512/512 normalization execute on final ELF",
                "armed evaluator poll performs no queue read",
                "capture is closed before any public user evaluation"],
            "must_not_include": ["Comfort library", "Block-3 freight",
                                 "diagnostic freight"]},
        "accounting": {"WPLTO_runs": 0, "product_links": 0,
                       "media_builds": 0, "device_contacts": 0},
        "claim_limit": "host-only reopening price; no product, lossless-user, media or hardware claim",
    }
    return value


def validate(value: dict[str, Any]) -> None:
    require(value == derive(), "v1.8 Capture reopening receipt drift")


def selftest(value: dict[str, Any]) -> None:
    mutations = (
        lambda row: row["price"]["E000"].update(watch_margin_bytes=2),
        lambda row: row["price"]["symbol_capacity_after"].update(symbol_slots=112),
        lambda row: row["price"]["composed_bank2"]["overlaps"].append("x"),
        lambda row: row["scope"]["excluded"].remove("repl-comfort"),
    )
    rejected = 0
    for mutate in mutations:
        trial = copy.deepcopy(value)
        mutate(trial)
        try:
            validate(trial)
        except PricingError:
            rejected += 1
    require(rejected == len(mutations), "pricing mutation survived")


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in {"check", "selftest"},
            "usage: c2_v18_capture_reopening_pricing.py check|selftest")
    value = derive()
    validate(value)
    if sys.argv[1] == "selftest":
        selftest(value)
    print("v1.8 Capture reopening pricing: PASS "
          "E000=138B reserve=57/54+3 D5=113/1506 bank2-hole=16431 "
          "WPLTO=0 link=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError,
            PricingError) as error:
        print(f"v1.8 Capture reopening pricing: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
