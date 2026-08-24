#!/usr/bin/env python3
"""Build the owner-directed v1.6 product world without diagnostic freight."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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
import c2_transitive_map_nesting_gate as MAP_NEST  # noqa: E402
import c2_v160_boot_refill_dma_closure as DMA  # noqa: E402
import c2_v160_boot_refill_selector_bypass as BYPASS  # noqa: E402
import c2_v160_boot_refill_selector_bypass_media as CHAIN  # noqa: E402
import c2_v160_display_ownership as DISPLAY  # noqa: E402
import c2_v160_execution_boundary_backstop as BACKSTOP  # noqa: E402
import c2_v160_input_service_hybrid_final_world as HYBRID  # noqa: E402
import c2_v160_queue_single_owner_card as QUEUE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-clean-product-candidate-r1"
PREFLIGHT = ROOT / "build/c2.3/v1.6-clean-product-candidate-r1-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "candidate-invocation.json"
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
PROFILE = BUILD / "wplto/resolved-profile.txt"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
RECEIPT = ARCH / "c2.3-v1.6-clean-product-candidate-r1-receipt.json"
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
AUTHORIZATION = "4ddc957a"
FORMAT = "lisp65-c2-v160-clean-product-candidate-v1"
STATUS = "PASS: V1.6 CLEAN PRODUCT WORLD FINAL GREEN"


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{AUTHORIZATION}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("*", "").replace(
        "`", "").split())
    for token in ("the clean product candidate", "only product freight",
                  "removed: all diagnostic freight",
                  "diagnostic freight lives in diagnostic worlds",
                  "full check-source green on this world"):
        require(token in text, f"clean-product authority absent: {token}")
    return {"authority": "git-blob", "commit": AUTHORIZATION, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def configure_clean_stack() -> tuple[Any, dict[str, Any], dict[str, object]]:
    """Reconstruct the latest fix stack, then select its product projection."""
    CHAIN.ENGINE.TOP = CHAIN.TOP
    CHAIN.ENGINE.configure_live_chain()
    reopen = CHAIN.ENGINE.BASE.BASE.REOPEN
    core, activation = reopen.configure_stack(BUILD, PREFLIGHT)
    product_cold = PRODUCT.select_clean_product_world()
    require(PRODUCT.INPUT_CAPTURE_ENABLED
            and PRODUCT.INPUT_HYBRID_ENABLED
            and not PRODUCT.REFILL_WITNESS_ENABLED
            and PRODUCT.PRODUCT_COLD_ENABLED,
            "clean product configuration did not select items 1+2 only")
    return core, activation, product_cold


def configure_full_candidate() -> tuple[Any, dict[str, Any], dict[str, object]]:
    core, activation, product_cold = configure_clean_stack()
    core.PRODUCT.BASE.configure()
    base = CHAIN.ENGINE.BASE.BASE
    base.CAN.REPLAY.PROFILE.configure()
    if PRODUCT.PROFILE_RODATA_BYTES == 342:
        PRODUCT.configure_require_resolver_profile_geometry()
        PRODUCT.configure_defstruct_foundation_profile_geometry()
    base.CAN.REPLAY.BANK2.configure_bank2_stage()
    base.CAN.REPLAY.TWO.configure_two_region()
    base.CAN.REPLAY.LINK60.configure_current_pin_adapters()
    PRODUCT.configure_intern_session_service()
    PRODUCT.configure_full_map_ownership()
    PRODUCT.configure_low_resident_lma_reset()
    base.HEADER.configure_consumption()
    return core, activation, product_cold


def setup_child() -> tuple[Any, dict[str, Any], dict[str, object]]:
    core, activation, product_cold = configure_clean_stack()
    core.install_static(BUILD)
    core.bind_paths_only(BUILD, PREFLIGHT)
    core.write_projections()
    return core, activation, product_cold


def configuration_gate() -> dict[str, Any]:
    _core, activation, product_cold = configure_clean_stack()
    definitions = tuple(PRODUCT.CONVERGENCE_DEFINES)
    sources = tuple(Path(path).relative_to(ROOT).as_posix()
                    for path in PRODUCT.source_list(definitions))
    editor = (ROOT / "lib/stdlib-read-line.lisp").read_text(encoding="utf-8")
    forbidden_editor = ("Diagnostic refill-trace origin", "(poke 188 138 255)",
                        "(poke 188 135 0)", "(poke 188 136 0)",
                        "(poke 188 137 0)", "(poke 188 139 165)")
    require(PRODUCT.REFILL_WITNESS_FEATURE not in definitions
            and PRODUCT.PRODUCT_COLD_FEATURE in definitions
            and "src/optional/c2_refill_boundary_witness.s" not in sources
            and product_cold["source"] in sources
            and not any(token in editor for token in forbidden_editor),
            "diagnostic freight remains in clean configuration")
    registries = PRODUCT.active_card_freight_registries()
    require([row["registry"] for row in registries] == [
                "input-fidelity", "product-cold-disk-chain"],
            "acceptance product world has a diagnostic or missing registry")
    return {"world": "product", "capture": activation,
        "features": list(definitions), "compiler_sources": list(sources),
        "active_registries": registries,
        "removed": {"feature": PRODUCT.REFILL_WITNESS_FEATURE,
            "source": "src/optional/c2_refill_boundary_witness.s",
            "section": ".lisp65_c2_mapped_diagnostic",
            "trace_origin_tokens": list(forbidden_editor)},
        "product_cold_successor": product_cold,
        "rule": "diagnostic freight lives in diagnostic worlds; acceptance runs product world"}


def preflight() -> None:
    require(not any(path.exists() for path in
                    (BUILD, PREFLIGHT, RECEIPT)),
            "clean product candidate is one-shot")
    gate = configuration_gate()
    PREFLIGHT.mkdir(parents=True)
    value = {"format": FORMAT + "-preflight", "recorded_on": "2026-08-24",
        "status": "PASS: V1.6 CLEAN PRODUCT WORLD ARMED 0/1",
        "authority": authority(), "configuration": gate,
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "scope_runs": 0, "acceptance_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "claim_limit": "Configuration only; no WPLTO, link, media or device."}
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("v1.6 clean product: PREFLIGHT PASS diagnostic-features=0 card=0/1")


def produce_child() -> None:
    core, _activation, _product_cold = setup_child()
    raise SystemExit(core.PRODUCT.BASE.produce_child())


def scope_child() -> None:
    core, _activation, _product_cold = setup_child()
    raise SystemExit(core.PRODUCT.BASE.scope_child())


def acceptance_child() -> None:
    core, _activation, _product_cold = setup_child()
    os.environ["LISP65_R1_ACCEPTANCE_RESULT"] = str(ACCEPTANCE_RESULT)
    raise SystemExit(core.PRODUCT.BASE.acceptance_child())


def run_child(action: str) -> dict[str, Any]:
    run = subprocess.run([sys.executable, str(DRIVER), action], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(run.returncode == 0,
            f"clean product child {action} red:\n{run.stdout}")
    return {"action": action, "status": "PASS",
            "witness": " ".join(run.stdout.split())}


def artifacts() -> dict[str, dict[str, Any]]:
    return {"ELF": bind(ELF), "PRG": bind(PRG),
        "map": bind(BUILD / "wplto/lisp65-c2-substitution-linked.prg.map"),
        "lto": bind(BUILD / "wplto/lisp65-c2-substitution-linked.prg.lto.o")}


def profile_gate() -> dict[str, Any]:
    lines = PROFILE.read_text(encoding="utf-8").splitlines()
    feature_rows = [line.split("=", 1)[1] for line in lines
                    if line.startswith("feature_defines=")]
    require(len(feature_rows) == 1, "clean profile feature row is not unique")
    features = tuple(item for item in feature_rows[0].split(",") if item)
    sources = tuple(line.split(":", 1)[0].split("=", 1)[1]
                    for line in lines if line.startswith("input_sha256="))
    object_names = sorted(path.name for path in (
        BUILD / "wplto/.canonical-objects-lisp65-c2-substitution-linked").glob("*.o"))
    require(PRODUCT.REFILL_WITNESS_FEATURE not in features
            and PRODUCT.PRODUCT_COLD_FEATURE in features
            and not any(name.endswith("c2_refill_boundary_witness.s")
                        for name in sources)
            and any(name.endswith("c2_product_cold_disk_chain.s")
                    for name in sources)
            and not any("refill_boundary_witness" in name for name in object_names)
            and any("product_cold_disk_chain" in name for name in object_names),
            "real compiler consumed a diagnostic or missed a product owner")
    return {"features": list(features), "sources": list(sources),
            "objects": object_names,
            "real_consumer": "resolved profile plus canonical object inventory"}


def final_gate() -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    sections = {row.name: row for row in truth.sections}
    symbols = {row.name: row for row in truth.symbols}
    cold = sections.get(".lisp65_c2_mapped_product_cold")
    require(".lisp65_c2_mapped_diagnostic" not in sections
            and "c2_refill_trace_read" not in symbols
            and cold is not None and cold.address == 0x7E8D
            and 0 < cold.bytes <= 371
            and symbols["disk_chain_to_scratch"].bytes == 12
            and symbols["disk_chain_to_scratch_far"].section == cold.name,
            "final ELF contains diagnostic freight or lost product-cold body")
    nested = MAP_NEST.check(ELF)
    dma = DMA.linked_read_model(ELF); DMA.validate_final(dma)
    bypass = BYPASS.linked_read_model(ELF); BYPASS.validate_final(bypass)
    backstop = BACKSTOP.final_gate(ELF)
    hybrid = HYBRID.derive(ELF)
    queue = QUEUE.linked_owner_gate(ELF)
    display = DISPLAY.derive()
    require(nested["violations"] == []
            and dma["unsafe_content_DMA_count"] == 0
            and bypass["unsafe_content_DMA_count"] == 0
            and backstop["recovery_sanitization"]["dominates_longjmp"] is True
            and hybrid["status"] == "PASS: HYBRID CLAIMS PROVED ON FINAL ELF"
            and queue["dominated_calls"] == 1
            and display["status"] ==
                "PASS: COMFORT DISPLAY HAS ONE OWNER AND DEFINED HANDOFF",
            "standing final-product wall regressed")
    return {"diagnostic_freight_absent": True,
        "mapped_product_cold": {"address": f"0x{cold.address:04x}",
            "bytes": cold.bytes, "capacity_bytes": 371,
            "free_bytes": 371 - cold.bytes},
        "profile": profile_gate(), "nested_MAP": nested,
        "DMA": dma, "selector_bypass": bypass,
        "execution_backstop": backstop, "hybrid": hybrid,
        "queue_single_owner": queue,
        "display": {"status": display["status"],
            "result_tail_blank": display["composed_framebuffer"][
                "result_tail_blank"]}}


def build() -> None:
    pre = load(PREFLIGHT_RECEIPT)
    require(pre["status"] == "PASS: V1.6 CLEAN PRODUCT WORLD ARMED 0/1"
            and not BUILD.exists() and not RECEIPT.exists()
            and not INVOCATION.exists(),
            "clean product persisted preflight or lifecycle drift")
    INVOCATION.write_bytes(canonical({"status": "INVOKED",
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT)}))
    runs = [run_child("_produce")]
    before = artifacts()
    runs.extend((run_child("_scope"), run_child("_accept")))
    after = artifacts()
    require(before == after, "scope or acceptance changed clean artifacts")
    scope, acceptance = load(SCOPE_RESULT), load(ACCEPTANCE_RESULT)
    require(scope["status"] == "PASS" and acceptance["status"] == "PASS",
            "clean product scope or acceptance red")
    gate = final_gate()
    value = {"format": FORMAT, "recorded_on": "2026-08-24",
        "status": STATUS, "authority": authority(),
        "preflight": bind(PREFLIGHT_RECEIPT), "invocation": bind(INVOCATION),
        "configuration": pre["configuration"], "final_product": gate,
        "producer": bind(PRODUCER_RESULT), "scope": bind(SCOPE_RESULT),
        "acceptance": bind(ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": runs,
        "attempt_accounting": {"WPLTO_runs": 1, "product_links": 1,
            "scope_runs": 1, "acceptance_runs": 1, "media_builds": 0,
            "device_contacts": 0},
        "media_authorized": False,
        "next": "full check-source self-certification, then fresh same-world media"}
    RECEIPT.write_bytes(canonical(value))
    check()
    print("v1.6 clean product: BUILD PASS product-world=green diagnostic=absent")


def check() -> None:
    value = load(RECEIPT)
    require(value["status"] == STATUS
            and value["authority"] == authority()
            and value["artifacts_before"] == artifacts()
            and value["artifacts_after"] == value["artifacts_before"]
            and value["final_product"]["diagnostic_freight_absent"] is True
            and value["attempt_accounting"] == {"WPLTO_runs": 1,
                "product_links": 1, "scope_runs": 1,
                "acceptance_runs": 1, "media_builds": 0,
                "device_contacts": 0},
            "clean product receipt drift")
    print("v1.6 clean product: CHECK PASS final-world=product diagnostic=absent")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "build", "check",
                                           "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    {"preflight": preflight, "build": build, "check": check,
     "_produce": produce_child, "_scope": scope_child,
     "_accept": acceptance_child}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.6 clean product: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
