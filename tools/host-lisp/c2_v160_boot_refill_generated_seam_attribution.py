#!/usr/bin/env python3
"""Attribute why the candidate source repair did not reach the boot refill."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_boot_refill_dma_closure as CLOSURE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
GENERATOR = ROOT / "tools/host-lisp/c2_lite_v6_product_probe.py"
BUILD = ROOT / "build/c2.3/v1.6-boot-refill-map-cpu-replacement-card"
GENERATED = BUILD / "wplto/generated-product-sources/c2_product_runtime.c"
PROFILE = BUILD / "wplto/resolved-profile.txt"
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
FIRST_RED = ARCH / "c2.3-v1.6-boot-refill-map-cpu-card-final-red.json"
SECOND_RED = ARCH / (
    "c2.3-v1.6-boot-refill-map-cpu-replacement-card-final-red.json")
RECEIPT = ARCH / (
    "c2.3-v1.6-boot-refill-generated-seam-attribution.json")


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def c_function(text: str, name: str) -> str:
    marker = name + "("
    at = text.find(marker)
    require(at >= 0, f"function absent: {name}")
    start = text.rfind("\n", 0, at) + 1
    brace = text.find("{", at)
    require(brace >= 0, f"function body absent: {name}")
    depth = 0
    for end in range(brace, len(text)):
        if text[end] == "{":
            depth += 1
        elif text[end] == "}":
            depth -= 1
            if depth == 0:
                return text[start:end + 1]
    raise AttributionError(f"unterminated function: {name}")


def attribution() -> dict[str, Any]:
    generated = GENERATED.read_text(encoding="utf-8")
    generator = GENERATOR.read_text(encoding="utf-8")
    profile = PROFILE.read_text(encoding="utf-8")
    source_read = c_function(generated, "c2_source_read")
    entry = c_function(generated, "c2_product_entry_read")
    model = CLOSURE.linked_read_model(ELF)
    generator_raw = (
        'runtime_source = replace_c_function(runtime_source, '
        '"c2_product_entry_read"' in generator
        and "c2_facade_vm_code_load(2u" in generator)
    feature_bound = "LISP65_C2_MAP_CPU_TRANSPORT" in profile
    source_seam_fixed = ("return c2_facade_map_cpu_read(" in source_read
                         and "#ifdef LISP65_C2_MAP_CPU_TRANSPORT" in source_read)
    emitted_entry_raw = ("c2_facade_vm_code_load(2u" in entry
                         and "return 1;" in entry
                         and "c2_facade_map_cpu_read" not in entry)
    require(feature_bound and source_seam_fixed and generator_raw
            and emitted_entry_raw
            and model["product_entry"]["raw_read_edges"] == 1
            and model["product_entry"]["MAP_CPU_edges"] == 0
            and model["unsafe_content_DMA_count"] >= 1,
            "generated boot-refill counterproof drift")
    return {
        "format": "lisp65-c2-v160-boot-refill-generated-seam-attribution-v1",
        "recorded_on": "2026-08-23",
        "status": "ATTRIBUTED: GENERATOR REINTRODUCES RAW BOOT REFILL",
        "evidence": {"generator": bind(GENERATOR),
            "candidate_generated_runtime": bind(GENERATED),
            "resolved_profile": bind(PROFILE), "final_ELF": bind(ELF),
            "first_Final_Red": bind(FIRST_RED),
            "replacement_Final_Red": bind(SECOND_RED)},
        "hop_proof": {
            "MAP_CPU_feature_reached_real_profile": feature_bound,
            "authored_common_source_seam_fixed": source_seam_fixed,
            "generator_replaces_product_entry_read": generator_raw,
            "generated_product_entry_is_raw_pass_through": emitted_entry_raw,
            "final_ELF": model,
        },
        "decision": {
            "class": "generated-successor-overrides-authored-source-fix",
            "exact_writer": "c2_lite_v6_product_probe.generate_sources",
            "exact_replacement": "c2_product_entry_read",
            "product_fix_location": "generated producer template",
            "required_transport": "MAP CPU with returned failure propagated",
            "pre_card_gate": (
                "inspect the emitted candidate function, not the authored "
                "function that the producer replaces"),
        },
        "qualification_red": {
            "reported": "real configurator projection drift",
            "expected_and_observed_persisted": False,
            "claim": (
                "separate qualification-mechanics Red; the frozen evidence "
                "cannot identify its failed conjunct without a retry"),
            "required_repair": (
                "future projection drift reports persist the named conjunct "
                "and both values before any new card runs"),
        },
        "claim_limit": (
            "Host-only attribution over the consumed final ELF and generated "
            "source. No product build, media build, or device contact."),
        "execution_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "cards_consumed": 0, "media_builds": 0, "device_contacts": 0},
        "successor_authorized": False,
    }


def main() -> int:
    value = attribution()
    if len(sys.argv) > 1 and sys.argv[1] == "write":
        require(not RECEIPT.exists(), "generated-seam attribution exists")
        RECEIPT.write_bytes(canonical(value))
    elif len(sys.argv) > 1 and sys.argv[1] == "check":
        require(RECEIPT.read_bytes() == canonical(value),
                "generated-seam attribution drift")
    else:
        raise AttributionError("usage: write|check")
    print("boot-refill generated seam: ATTRIBUTED producer-template raw edge")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, KeyError, ValueError,
            json.JSONDecodeError) as error:
        print(f"boot-refill generated seam: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
