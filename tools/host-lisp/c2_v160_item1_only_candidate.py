#!/usr/bin/env python3
"""Build the owner-selected v1.6 item-1-only product world."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_clean_product_candidate as BASE  # noqa: E402
import c2_v160_repl_cursor_navigation as CURSOR  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-item1-only-candidate-r1"
PREFLIGHT = ROOT / "build/c2.3/v1.6-item1-only-candidate-r1-preflight"
RECEIPT = ARCH / "c2.3-v1.6-item1-only-candidate-r1-receipt.json"
AUTHORIZATION = "3c60ab50"
DRIVER = Path(__file__).resolve()
FORMAT = "lisp65-c2-v160-item1-only-product-r1-v1"
STATUS = "PASS: V1.6 ITEM 1 ONLY R1 PRODUCT FINAL GREEN"


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{name}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("v1.6 ships item 1 alone", "repl-comfort and the capture/hybrid",
                  "navigation semantics correct", "d5 without repl-comfort"):
        require(token in text, f"item-1-only authority absent: {token}")
    return {"authority": "git-blob", "commit": AUTHORIZATION, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def configure_item1_stack() -> tuple[Any, dict[str, Any], dict[str, object]]:
    BASE.CHAIN.ENGINE.TOP = BASE.CHAIN.TOP
    BASE.CHAIN.ENGINE.configure_live_chain()
    reopen = BASE.CHAIN.ENGINE.BASE.BASE.REOPEN
    core, activation = reopen.configure_stack(
        BUILD, PREFLIGHT, activate_capture=False)
    product_cold = BASE.PRODUCT.select_clean_product_world()
    require(not BASE.PRODUCT.INPUT_CAPTURE_ENABLED
            and not BASE.PRODUCT.INPUT_HYBRID_ENABLED
            and not BASE.PRODUCT.REFILL_WITNESS_ENABLED
            and BASE.PRODUCT.PRODUCT_COLD_ENABLED,
            "item-1 product did not exclude all Comfort product freight")
    return core, activation, product_cold


def configuration_gate() -> dict[str, Any]:
    _core, activation, product_cold = configure_item1_stack()
    definitions = tuple(BASE.PRODUCT.CONVERGENCE_DEFINES)
    sources = tuple(Path(path).relative_to(ROOT).as_posix()
                    for path in BASE.PRODUCT.source_list(definitions))
    forbidden_features = (BASE.PRODUCT.INPUT_CAPTURE_FEATURE,
                          BASE.PRODUCT.INPUT_HYBRID_FEATURE,
                          BASE.PRODUCT.REFILL_WITNESS_FEATURE)
    forbidden_sources = {
        BASE.PRODUCT.INPUT_CAPTURE_SOURCE.relative_to(ROOT).as_posix(),
        BASE.PRODUCT.INPUT_HYBRID_SOURCE.relative_to(ROOT).as_posix(),
        BASE.PRODUCT.REFILL_WITNESS_SOURCE.relative_to(ROOT).as_posix(),
    }
    registries = BASE.PRODUCT.active_card_freight_registries()
    require(not any(item in definitions for item in forbidden_features)
            and BASE.PRODUCT.PRODUCT_COLD_FEATURE in definitions
            and not forbidden_sources.intersection(sources)
            and [row["registry"] for row in registries] ==
                ["product-cold-disk-chain"],
            "item-1 configuration retained Comfort or diagnostic freight")
    return {
        "world": "item-1-only",
        "activation": activation,
        "features": list(definitions),
        "compiler_sources": list(sources),
        "active_registries": registries,
        "removed": {
            "features": list(forbidden_features[:2]),
            "sources": sorted(forbidden_sources)[:2],
            "library": "repl-comfort",
            "claims": ["lossless input", "Comfort prompt", "Comfort display"],
        },
        "product_cold_successor": product_cold,
        "rule": "item 1 and standalone fixes only; all Comfort freight moves to v1.7",
    }


def profile_gate() -> dict[str, Any]:
    lines = BASE.PROFILE.read_text(encoding="utf-8").splitlines()
    feature_rows = [line.split("=", 1)[1] for line in lines
                    if line.startswith("feature_defines=")]
    require(len(feature_rows) == 1, "item-1 profile feature row is not unique")
    features = tuple(item for item in feature_rows[0].split(",") if item)
    sources = tuple(line.split(":", 1)[0].split("=", 1)[1]
                    for line in lines if line.startswith("input_sha256="))
    objects = sorted(path.name for path in (
        BUILD / "wplto/.canonical-objects-lisp65-c2-substitution-linked").glob("*.o"))
    forbidden_features = (BASE.PRODUCT.INPUT_CAPTURE_FEATURE,
                          BASE.PRODUCT.INPUT_HYBRID_FEATURE,
                          BASE.PRODUCT.REFILL_WITNESS_FEATURE)
    forbidden_names = ("c2_kernal_input_capture", "c2_kernal_input_consumer",
                       "c2_refill_boundary_witness")
    require(not any(item in features for item in forbidden_features)
            and BASE.PRODUCT.PRODUCT_COLD_FEATURE in features
            and not any(any(token in name for token in forbidden_names)
                        for name in (*sources, *objects))
            and any(name.endswith("c2_product_cold_disk_chain.s")
                    for name in sources)
            and any("product_cold_disk_chain" in name for name in objects),
            "real compiler retained Comfort freight or missed product-cold owner")
    return {"features": list(features), "sources": list(sources),
            "objects": objects,
            "real_consumer": "resolved profile plus canonical object inventory"}


def final_gate() -> dict[str, Any]:
    truth = ElfTruth.read(BASE.ELF, llvm_readobj=BASE.READOBJ,
                          include_section_data=True)
    sections = {row.name: row for row in truth.sections}
    symbols = {row.name: row for row in truth.symbols}
    cold = sections.get(".lisp65_c2_mapped_product_cold")
    forbidden_sections = {
        *map(str, BASE.PRODUCT.INPUT_CAPTURE_BUILD_CONFIGURATION["allocated"]),
        *map(str, BASE.PRODUCT.INPUT_HYBRID_BUILD_CONFIGURATION["allocated"]),
        ".lisp65_c2_mapped_diagnostic",
    }
    require(not forbidden_sections.intersection(sections)
            and "c2_kernal_input_take" not in symbols
            and "c2_refill_trace_read" not in symbols
            and cold is not None and cold.address == 0x7E8D
            and 0 < cold.bytes <= 371
            and symbols["disk_chain_to_scratch"].bytes == 12
            and symbols["disk_chain_to_scratch_far"].section == cold.name,
            "final item-1 ELF retained Comfort freight or lost product fixes")
    nested = BASE.MAP_NEST.check(BASE.ELF)
    dma = BASE.DMA.linked_read_model(BASE.ELF); BASE.DMA.validate_final(dma)
    bypass = BASE.BYPASS.linked_read_model(BASE.ELF); BASE.BYPASS.validate_final(bypass)
    backstop = BASE.BACKSTOP.final_gate(BASE.ELF)
    queue = BASE.QUEUE.linked_owner_gate(BASE.ELF)
    cursor = BASE.load(CURSOR.RECEIPT)
    require(nested["violations"] == []
            and dma["unsafe_content_DMA_count"] == 0
            and bypass["unsafe_content_DMA_count"] == 0
            and backstop["recovery_sanitization"]["dominates_longjmp"] is True
            and queue["dominated_calls"] == 1
            and cursor["status"] ==
                "PASS: v1.6 REPL cursor navigation host-qualified"
            and cursor["artifacts"]["execution_lanes"] == 3
            and cursor["artifacts"]["public_only_key_event_modes"] == [0, 1],
            "item-1 or standing final-product wall regressed")
    return {
        "world": "item-1-only-r1",
        "diagnostic_freight_absent": True,
        "Comfort_product_freight_absent": True,
        "mapped_product_cold": {"address": f"0x{cold.address:04x}",
            "bytes": cold.bytes, "capacity_bytes": 371,
            "free_bytes": 371 - cold.bytes},
        "profile": profile_gate(),
        "nested_MAP": nested,
        "DMA": dma,
        "selector_bypass": bypass,
        "execution_backstop": backstop,
        "queue_single_owner": queue,
        "cursor_navigation": BASE.bind(CURSOR.RECEIPT),
        "first_red_fix": {
            "failure": "public read-line called private key-event mode 3 after first printable byte",
            "rule": "features project compiler input; private Comfort calls are absent from the public library artifact",
            "delivery_seam": "v16core library source projection",
            "public_execution_modes": [0, 1],
            "canonical_comfort_hot_path": "unchanged and requalified",
        },
        "acceptance_bar": "navigation semantics plus no regression versus v1.5",
    }


def configure() -> None:
    BASE.BUILD = BUILD
    BASE.PREFLIGHT = PREFLIGHT
    BASE.PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
    BASE.INVOCATION = PREFLIGHT / "candidate-invocation.json"
    BASE.ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    BASE.PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
    BASE.PROFILE = BUILD / "wplto/resolved-profile.txt"
    BASE.PRODUCER_RESULT = BUILD / "producer-result.json"
    BASE.SCOPE_RESULT = BUILD / "owner-scope-result.json"
    BASE.ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
    BASE.RECEIPT = RECEIPT
    BASE.DRIVER = DRIVER
    BASE.AUTHORIZATION = AUTHORIZATION
    BASE.FORMAT = FORMAT
    BASE.STATUS = STATUS
    BASE.authority = authority
    BASE.configure_clean_stack = configure_item1_stack
    BASE.configuration_gate = configuration_gate
    BASE.profile_gate = profile_gate
    BASE.final_gate = final_gate


def run(action: str) -> None:
    configure()
    {"preflight": BASE.preflight, "build": BASE.build, "check": BASE.check,
     "_produce": BASE.produce_child, "_scope": BASE.scope_child,
     "_accept": BASE.acceptance_child}[action]()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "build", "check",
                                           "_produce", "_scope", "_accept"))
    run(parser.parse_args().action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.6 item-1-only candidate: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
