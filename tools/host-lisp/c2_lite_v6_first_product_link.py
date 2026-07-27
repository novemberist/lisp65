#!/usr/bin/env python3
"""Build and bind the first owner-authorized C2-lite product link.

Link 37 starts from the immutable Link-35 rollback product, consumes the
green co-resident C2-lite WPLTO profile, projects the exact C2D-v6/Chip-RAM
sources into the sole product closure link, and reruns every ordinary and
C2-lite replacement gate.  It never runs hardware.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link33_bss_triage_product_link as BASE  # noqa: E402
import c2_lite_root_surrogate as ROOT_GATE  # noqa: E402
import c2_lite_v6_coresident_diet_probe as DIET  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


P = BASE.P
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / "build/c2.2/substitution/product-link-37-c2-lite-v6"
RECEIPT = EVIDENCE / "c2.2-product-link37-c2-lite-v6-structural-receipt.json"
AUTHORITY = EVIDENCE / (
    "c2.2-c2-lite-v6-coresident-diet-successor-gate-replay3-receipt.json")
AUTHORITY_SHA = "411617ecd2b1def91a4708de1887b09a77e5d3037efdd6bf8a3395a28cc83406"
LINK35_REPLAY = EVIDENCE / (
    "c2.2-product-link35-dma-completion-first-status-pure-replay-receipt.json")
LINK35_REPLAY_SHA = "10bc82583a9b6f80c805a6770769792047e838e93e07d92a4735b673bd2fd13d"
LINK35 = ROOT / "build/c2.2/substitution/product-link-35-dma-completion-first-status"
LINK35_PRODUCT = LINK35 / "lisp65-c2-substitution-linked.prg"
LINK35_PRODUCT_SHA = "54c731559fdb72d5d1cb8478b9da7e78a422741e4e5267d64b07fe4c6f763a65"
CONTRACT = ROOT / "config/c2-lite-execution-contract.json"
ADDENDUM = ROOT / "docs/planning/c2-lite-execution-contract-addendum.md"
MEMO = ROOT / "docs/planning/c2-lite-rebuild-memo.md"
CAP = 1792
BANK_BYTES = 65536
E000_FLOOR = 115


class LinkError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise LinkError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"Link-37 artifact absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def tree(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    return {item.relative_to(path).as_posix(): {
                "bytes": item.stat().st_size, "sha256": sha(item)}
            for item in sorted(path.rglob("*")) if item.is_file()}


def protect() -> None:
    if OUT.is_dir():
        BASE.protect(OUT)
    if RECEIPT.is_file():
        os.chmod(RECEIPT, 0o444)


def configure() -> tuple[str, ...]:
    """Install the exact green co-resident profile into the product driver."""
    BASE.configure()
    DIET.configure_coresident_diet()
    P.E000_FINAL_FLOOR_BYTES = E000_FLOOR
    base = tuple(item for item in BASE.FEATURES if item not in (
        "LISP65_RTOV_CRC_CONVERGENCE",
        "LISP65_RTOV_DMA_COMPLETION_FENCE",
        "LISP65_C2_PHASE11_SPLIT",
        "LISP65_C2_LITE_COLD_EVICTION",
        "LISP65_C2_LITE_V6_SEMANTIC_SPLITS",
        "LISP65_C2_LITE_V6_CORESIDENT_DIET",
        "LISP65_C2_LITE_CHIP_RAM",
    ))
    features = (*base,
        "LISP65_C2_PHASE11_SPLIT",
        "LISP65_C2_LITE_COLD_EVICTION",
        "LISP65_C2_LITE_V6_SEMANTIC_SPLITS",
        "LISP65_C2_LITE_V6_CORESIDENT_DIET",
        "LISP65_C2_LITE_CHIP_RAM")
    require(len(features) == len(set(features)), "C2-lite feature duplication")
    require(len(P.C2_DECODER_SLICES) == 19
            and len(P.C2_APPEND_SLICES) == 24
            and len(P.SESSION_SLICE_SPECS) == 51
            and P.UNIQUE_SLICE_COUNT == 58
            and P.E000_FINAL_FLOOR_BYTES == 115,
            "C2-lite product profile drift")
    return features


def prerequisites() -> dict[str, Any]:
    expected = {
        AUTHORITY: AUTHORITY_SHA,
        LINK35_REPLAY: LINK35_REPLAY_SHA,
        LINK35_PRODUCT: LINK35_PRODUCT_SHA,
    }
    for path, digest in expected.items():
        require(path.is_file() and sha(path) == digest,
                f"Link-37 prerequisite drift: {path}")
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    require(authority.get("status") ==
            "passed-pure-gate-replay-no-compiler-no-link-no-hardware"
            and authority["co_resident_capacity"]["session_family_bytes"] == 65438
            and authority["co_resident_capacity"]["session_family_headroom_bytes"] == 98
            and authority["whole_program_lto_reconstruction"]["walls"] == {
                "bank0_text_headroom_bytes": 70,
                "e000_headroom_bytes": 528,
                "fixed_hot_block_headroom_bytes": 33,
                "ordinary_bank0_bss_headroom_bytes": 144,
                "resident_island_headroom_bytes": 170,
            }, "C2-lite green WPLTO authority drift")
    predecessor = json.loads(LINK35_REPLAY.read_text(encoding="utf-8"))
    require(predecessor.get("status") ==
            "passed-artifact-only-link35-preinstall-dataflow-replay"
            and predecessor["product_identity"]["product"]["sha256"] ==
                LINK35_PRODUCT_SHA,
            "Link-35 rollback authority is not green")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    require(contract.get("status") ==
            "class-c-approved-first-product-link-authorized"
            and contract["scope"]["product_links_authorized"] == 1
            and contract["decision"]["e000_active_floor_bytes"] == 115
            and contract["coresident_aggregate_diet"]["modeled_headroom_bytes"] == 98
            and contract["first_product_link_authorization"]["count"] == 1
            and contract["first_product_link_authorization"]
                ["source_baseline"] == "Link 35",
            "C2-lite first-product-link contract is not authorized")
    require("exactly one first C2-lite product link authorized" in
            ADDENDUM.read_text(encoding="utf-8"),
            "C2-lite addendum authorization text absent")
    return {
        "green_wplto_gate_replay": bind(AUTHORITY),
        "link35_structural_rollback": bind(LINK35_REPLAY),
        "link35_product_rollback": bind(LINK35_PRODUCT),
        "c2_lite_contract": bind(CONTRACT),
        "c2_lite_addendum": bind(ADDENDUM),
        "reconstruction_memo": bind(MEMO),
        "driver": bind(Path(__file__)),
    }


def fresh_host_replacement_gates() -> dict[str, Any]:
    """Re-run v6 semantics and every split/fusion model before the link."""
    gate_root = OUT / "fresh-c2-lite-prelink-gates"
    gate_root.mkdir(parents=True)
    old_v6_out = V6.OUT
    old_diet_out = DIET.OUT
    old_emitter = V6._ENTRY_EMITTER
    old_emitter_path = V6._ENTRY_EMITTER_PATH
    try:
        V6.OUT = gate_root / "v6-semantics"
        V6.OUT.mkdir()
        V6._ENTRY_EMITTER = None
        V6._ENTRY_EMITTER_PATH = None
        host = V6.host_semantics()
        lifetime = V6.bank3_lifetime()
        DIET.OUT = gate_root / "slice-and-publication"
        DIET.OUT.mkdir()
        source = DIET.source_contract_gate()
        cutpoints = DIET.cutpoint_gates()
        shared = DIET.shared_semantics_gate()
        root = ROOT_GATE.collect()
    finally:
        V6.OUT = old_v6_out
        DIET.OUT = old_diet_out
        V6._ENTRY_EMITTER = old_emitter
        V6._ENTRY_EMITTER_PATH = old_emitter_path
    require(host["status"] == "passed"
            and host["rollback"]["count"] == 8
            and host["stale_generation"]["old_handles_rejected"] > 0
            and lifetime["status"] == "passed-lifetime-exclusive"
            and source["status"] == cutpoints["status"]
                == shared["status"] == "passed"
            and root["status"] == "pass",
            "fresh C2-lite replacement prelink gate is red")
    return {
        "status": "passed",
        "c2d_v6_host_semantics": host,
        "bank3_lifetime_model": lifetime,
        "source_contract": source,
        "semantic_split_and_fusion_cutpoints": cutpoints,
        "stage_before_publish_and_one_emitter": shared,
        "root_surrogate_complete_domain": root,
    }


def walls_and_family(elf: Path) -> tuple[dict[str, int], dict[str, Any]]:
    sections = P.section_table(elf)
    text = sections[".text"]
    bss = sections[".bss"]
    walls = {
        "bank0_text_headroom_bytes": P.HANDOFF_BASE
            - text["address"] - text["bytes"],
        "ordinary_bank0_bss_headroom_bytes": P.FIXED_BANK0_BASE
            - bss["address"] - bss["bytes"],
        "fixed_hot_block_headroom_bytes": P.fixed_bank0_headroom_bytes(),
        "resident_island_headroom_bytes": 2048 - sum(
            sections.get(name, {}).get("bytes", 0) for name in
            (".lisp65_resident_island", ".lisp65_resident_island_annex")),
        "e000_headroom_bytes": P.KERNAL_WINDOW_BYTES - sum(
            sections[name]["bytes"] for name in P.KERNAL_SECTIONS),
    }
    require(all(value >= 0 for key, value in walls.items()
                if key != "e000_headroom_bytes")
            and walls["e000_headroom_bytes"] >= E000_FLOOR,
            f"C2-lite product wall red: {walls}")
    slice_sections = {spec.split(":")[2] for spec in
                      P.BOOT_SLICE_SPECS + P.SESSION_SLICE_SPECS}
    slice_sizes = {name: sections.get(name, {}).get("bytes", 0)
                   for name in slice_sections}
    bad = {name: size for name, size in slice_sizes.items()
           if size <= 0 or size > CAP}
    require(not bad, f"C2-lite runtime slice wall red: {bad}")
    boot_path = OUT / "runtime-overlays-boot-final.bin"
    session_path = OUT / "runtime-overlays-session-final.bin"
    boot = json.loads((OUT / "runtime-overlays-boot-final.json").read_text())
    session = json.loads(
        (OUT / "runtime-overlays-session-final.json").read_text())
    require(boot_path.stat().st_size == boot["storage"]["size"] <= BANK_BYTES
            and session_path.stat().st_size == session["storage"]["size"]
                <= BANK_BYTES,
            "C2-lite Bank-3 family pack red")
    family = {
        "runtime_slices": {
            "count": len(slice_sizes), "cap_bytes": CAP,
            "largest_bytes": max(slice_sizes.values()),
            "minimum_headroom_bytes": CAP - max(slice_sizes.values()),
        },
        "successor_bank3_pack": {
            "boot": {**bind(boot_path), "bytes": boot_path.stat().st_size,
                     "headroom_bytes": BANK_BYTES - boot_path.stat().st_size},
            "session": {**bind(session_path),
                        "bytes": session_path.stat().st_size,
                        "headroom_bytes": BANK_BYTES
                            - session_path.stat().st_size},
        },
    }
    return walls, family


def no_runtime_attic_gate(elf: Path, generated: Path) -> dict[str, Any]:
    """Bind the hot source and retained relocation closure to Chip RAM only."""
    hot_text = (generated / "c2_hot_literal.c").read_text(encoding="utf-8")
    runtime_text = (generated / "c2_product_runtime.c").read_text(
        encoding="utf-8")
    rtov_text = (generated / "vm_runtime_overlay.c").read_text(
        encoding="utf-8")
    entry = V6.c_function_definition(runtime_text, "c2_product_entry_read")
    materializer = V6.c_function_definition(
        hot_text, "c2_stream_product_materialize_entry")
    rtov_read = V6.c_function_definition(rtov_text, "rtov_read")
    checks = {
        "hot_literal_has_no_shelf_read": "c2_stream_shelf_read" not in materializer,
        "hot_entry_has_no_shelf_or_dma_read":
            "c2_stream_shelf_read" not in entry and "c2_dma_copy" not in entry,
        "hot_entry_uses_bank2": "c2_facade_vm_code_load(2u" in entry,
        "native_refill_uses_bank3": "c2_facade_vm_code_load(3u" in rtov_read,
        "native_refill_has_no_attic_completion_path":
            "rtov_dma_submit_wait" not in rtov_read,
        "retired_runtime_retry_defines_absent": True,
    }
    truth = ElfTruth.read(elf, llvm_readobj=P.TOOLCHAIN / "llvm-readobj")
    hot_symbols = (
        "c2_product_entry_read", "c2_stream_product_materialize_entry",
        "c2_product_entry_record", "c2_product_entry_length")
    forbidden_targets = {
        "c2_stream_shelf_read", "c2_dma_copy", "rtov_dma_submit_wait"}
    relocation_rows = []
    bad = []
    for name in hot_symbols:
        matches = truth.symbols_by_name.get(name, [])
        require(len(matches) == 1 and matches[0].bytes > 0,
                f"hot C2-lite symbol is not a unique sized ELF citizen: {name}")
        owner = matches[0]
        for row in truth.relocations:
            if (row.source_section_index == owner.section_index
                    and owner.value <= row.offset < owner.value + owner.bytes):
                relocation_rows.append({
                    "owner": name, "target": row.target,
                    "type": row.relocation_type, "offset": row.offset})
                if row.target in forbidden_targets:
                    bad.append(relocation_rows[-1])
    require(all(checks.values()) and not bad,
            f"no-runtime-Attic closure red: checks={checks} edges={bad}")
    return {
        "status": "passed-source-and-linked-relocation-closure",
        "checks": checks,
        "hot_symbols": list(hot_symbols),
        "retained_hot_relocations_examined": len(relocation_rows),
        "forbidden_control_or_data_edges": bad,
        "bank2_loader_callsites": entry.count("c2_facade_vm_code_load(2u"),
        "bank3_loader_callsites": rtov_read.count("c2_facade_vm_code_load(3u"),
    }


def c2_lite_product_gates(product: Path, elf: Path,
                          host: dict[str, Any]) -> dict[str, Any]:
    walls, family = walls_and_family(elf)
    wplto_shape = {
        "walls": walls,
        "runtime_slices": family["runtime_slices"],
        "successor_bank3_pack": family["successor_bank3_pack"],
    }
    capacity = DIET.capacity_gate(wplto_shape, elf)
    semantics = DIET.semantic_product_gate(wplto_shape, product, elf)
    no_attic = no_runtime_attic_gate(
        elf, OUT / "generated-product-sources")
    root = ROOT_GATE.collect()
    require(root["status"] == "pass", "product root-surrogate gate red")
    stage = host["stage_before_publish_and_one_emitter"]
    v6 = host["c2d_v6_host_semantics"]
    chip = {
        "status": "passed",
        "bank1": "untouched",
        "bank2": {
            "code_bytes": V6.STATIC_CODE_BYTES,
            "headroom_bytes": BANK_BYTES - V6.STATIC_CODE_BYTES,
            "persistent_transient_edges_disjoint":
                v6["nested"]["low_and_high_edges_disjoint"],
        },
        "bank3": family["successor_bank3_pack"],
        "boot_session_simultaneously_callable": False,
    }
    generation = {
        "status": "passed",
        "old_handles_rejected":
            v6["stale_generation"]["old_handles_rejected"],
        "physical_bytes_retained_on_generation_change":
            v6["stale_generation"]["physical_bytes_retained"],
        "boot_binding_invalidated_before_session":
            host["bank3_lifetime_model"]["invalidation_before_overwrite"],
    }
    require(capacity["session_family_bytes"] <= BANK_BYTES
            and semantics["status"] == "passed"
            and no_attic["status"].startswith("passed")
            and stage["status"] == "passed"
            and generation["old_handles_rejected"] > 0,
            "C2-lite product replacement gate set red")
    return {
        "status": "passed",
        "capacity": capacity,
        "walls": walls,
        "runtime_family": family,
        "product_semantics": semantics,
        "no_runtime_attic": no_attic,
        "chip_bank_ownership": chip,
        "stage_before_publish": stage,
        "watermarks_and_generation": generation,
        "root_surrogate": root,
    }


def first_red(error: BaseException, authority: dict[str, Any]) -> dict[str, Any]:
    value = {
        "format": "lisp65-c2-lite-product-link37-first-red-v1",
        "recorded_on": "2026-07-21",
        "status": "FIRST RED: first C2-lite product link stopped",
        "promotable": False,
        "diagnostic": {"type": type(error).__name__, "message": str(error)},
        "execution_accounting": {
            "product_closure_links": int(
                (OUT / "lisp65-c2-substitution-linked.prg").is_file()),
            "hardware_runs": 0,
        },
        "authority": authority,
        "evidence": tree(OUT),
        "rollback_line": {**bind(LINK35_PRODUCT), "status": "untouched"},
        "next_gate": "return to Class-C review; no retry and no hardware",
    }
    write_json(RECEIPT, value)
    protect()
    return value


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "Link 37 is one-shot and already has output")
    features = configure()
    authority = prerequisites()
    OUT.mkdir(parents=True)
    original_sources = P.source_list
    try:
        host = fresh_host_replacement_gates()
        nested = BASE.PRE.check(OUT / "fresh-v5-b2-prelink-gates")
        require(nested["status"] == "passed-prelink-product-link-not-run"
                and nested["b2_model"]["cases"] == 18,
                "fresh B2/RUN-STOP prelink gate red")
        mapping = V6.generated_product_sources(OUT)

        def projected_sources(
                extra_definitions: tuple[str, ...] = ()) -> list[str]:
            return [str(mapping.get(Path(path).resolve(), Path(path)))
                    for path in original_sources(extra_definitions)]

        P.source_list = projected_sources
        P.single_link(
            OUT, probe_definitions=features,
            direct_entry_receipt=BASE.DIRECT.RECEIPT,
            direct_entry_check_tool="c2_hot_refill_direct_entry_contract.py",
            extra_contract_lines=(
                "mode=link37-first-c2-lite-v6-product",
                "source_baseline=link35",
                "feature_defines=" + ",".join(features),
                "c2d_version=6",
                "runtime_refill_source=chip-bank2",
                "native_family_source=chip-bank3",
                "bank1_user_graphics=untouched",
                "bank2_static_code_bytes=34403",
                "session_catalog_records=51",
                "runtime_slice_count_unique=58",
                "final_e000_floor_bytes=115",
                "no_runtime_attic=required",
                "green_inheritance=none",
                "c2_lite_authority_sha256=" + AUTHORITY_SHA,
            ))
    except Exception as error:
        P.source_list = original_sources
        return first_red(error, authority)
    finally:
        P.source_list = original_sources

    product = OUT / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    try:
        structure = json.loads(
            (OUT / "product-substitution-link.json").read_text())
        total = json.loads(
            (OUT / "total-publish-last-domain.json").read_text())
        required = (
            "identity_gate", "capacity_gate", "one_truth_gate",
            "kernal_freedom_gate", "fixed_host_facade_gate",
            "pre_ownership_gate", "handoff_z_abi_gate")
        require(structure.get("status") == "passed"
                and structure.get("product_closure_link_count") == 1
                and all(str(structure.get(name, "")).startswith("pass")
                        for name in required),
                "generic Link-37 product closure is not fully green")
        require(total.get("status") == "passed"
                and total.get("declared_domain_bytes") == 34,
                "Link-37 publish-last domain is not the complete 34-byte set")
        replacement = c2_lite_product_gates(product, elf, host)
        overlay = BASE.LINK33_BASE.final_overlay_closure(elf)
        preinstall = BASE.ISLAND.static_elf_gate(elf)
        require(overlay["status"] == "passed-final-elf-overlay-closure"
                and preinstall["status"] ==
                    "passed-static-preinstallation-Island-gate",
                "fresh overlay/preinstallation gate red")
        require(sha(product) != LINK35_PRODUCT_SHA,
                "first C2-lite link did not create a new identity")
        require(sha(LINK35_PRODUCT) == LINK35_PRODUCT_SHA,
                "Link-35 rollback product changed during Link 37")
        generic = {name: structure[name] for name in required}
        generic.update({
            "direct_entry_encoding": structure["direct_entry_encoding_gate"],
            "runtime_family_identity": structure["identity_components"]
                ["all_runtime_family_records_and_payloads"],
            "total_publish_last": total["status"],
            "overlay_closure": overlay["status"],
            "preinstallation_island": preinstall["status"],
        })
        require(all("pass" in str(status) for status in generic.values()),
                f"fresh generic gate set red: {generic}")
        value = {
            "format": "lisp65-c2-lite-product-link37-structural-v1",
            "recorded_on": "2026-07-21",
            "status": "passed-new-c2-lite-product-identity-hardware-not-run",
            "promotable": False,
            "link_number": 37,
            "inheritance": "none; every structural, capacity and replacement gate ran freshly",
            "execution_accounting": {
                "resident_island_seed_links": 1,
                "product_closure_links": 1,
                "hardware_runs": 0,
            },
            "authority": authority,
            "product_identity": {
                "product": bind(product), "elf": bind(elf),
                "map": bind(Path(str(product) + ".map")),
                "resolved_profile": bind(OUT / "resolved-profile.txt"),
                "predecessor_link35_sha256": LINK35_PRODUCT_SHA,
                "new_identity": True,
            },
            "fresh_generic_gates": generic,
            "fresh_c2_lite_replacement_gates": replacement,
            "fresh_prelink_semantics": host,
            "fresh_b2_run_stop_cases": nested["b2_model"]["cases"],
            "post_link_identity": {
                "declared_mutable_product_bytes": total["declared_domain_bytes"],
                "actual_changed_bytes": total["actual_changed_bytes"],
                "status": total["status"],
            },
            "rollback_line": {
                **bind(LINK35_PRODUCT), "status": "untouched-and-readable"},
            "claim_limit": (
                "Fresh first C2-lite product identity and complete structural, "
                "capacity and replacement-gate closure only. Hardware, boot, "
                "latency, refill timing, GC cost, Freezer identity, nested eval, "
                "promotion and acceptance remain not-run."),
            "next_gate": "owner-authorized seven-line receipt-less hardware presmoke from line 1",
        }
        report = OUT / "link37-c2-lite-v6-structural.json"
        write_json(report, value)
        receipt = {**value, "structural_report": bind(report),
                   "evidence_file_count": len(tree(OUT))}
        write_json(RECEIPT, receipt)
        protect()
        return receipt
    except Exception as error:
        return first_red(error, authority)


def check() -> dict[str, Any]:
    require(RECEIPT.is_file(), "Link-37 receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status") in {
        "passed-new-c2-lite-product-identity-hardware-not-run",
        "FIRST RED: first C2-lite product link stopped"},
        "Link-37 receipt status unknown")
    require(sha(LINK35_PRODUCT) == LINK35_PRODUCT_SHA,
            "Link-35 rollback product drift")
    if value["status"].startswith("passed"):
        for name in ("product", "elf", "map", "resolved_profile"):
            row = value["product_identity"][name]
            require(bind(ROOT / row["path"]) == row,
                    f"Link-37 identity drift: {name}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "check"))
    args = parser.parse_args()
    value = build() if args.action == "run" else check()
    print("c2-lite-v6-first-product-link: " + value["status"])
    return 2 if value["status"].startswith("FIRST RED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
