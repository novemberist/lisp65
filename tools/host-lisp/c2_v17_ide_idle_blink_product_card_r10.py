#!/usr/bin/env python3
"""Build Block 3 r10 with one page-congruent MAP geometry authority."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_bank2_composed_ownership as COMPOSED  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v20_phase02b_header_consumption_card as HEADER_CARD  # noqa: E402
import c2_v160_liveness_config as LIVENESS_CONFIG  # noqa: E402
import c2_v160_r1_stored_world_conversions as ACCEPT  # noqa: E402
import c2_v17_block3_r10_map_geometry_preflight as PRICE  # noqa: E402
import c2_v17_ide_idle_blink_product_card as CARD  # noqa: E402
import c2_v17_ide_idle_blink_product_card_r9 as R9  # noqa: E402
import c2_v160_r1_graph_conversions as GRAPH  # noqa: E402
import c2_v20_map_tuple_fix as MAP  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
BUILD = ROOT / "build/c2.3/v1.7-ide-idle-blink-product-card-r10"
PREFLIGHT = ROOT / "build/c2.3/v1.7-ide-idle-blink-product-preflight-r10"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "candidate-invocation.json"
PROBE = PREFLIGHT / "mapped-tenant-linker-probe.ld"
PROBE_OBJECT = PREFLIGHT / "mapped-tuple-owner-probe.o"
POSTLINK = BUILD / "postlink-observation.json"
PRELINK_RED = PREFLIGHT / "liveness-adapter-prelink-red.json"
POSTLINK_RED = PREFLIGHT / "compiler-consumption-adapter-postlink-red.json"
ACCEPTANCE_RED = PREFLIGHT / "tuple-consumer-acceptance-red.json"
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
PROFILE = BUILD / "wplto/resolved-profile.txt"
SCOPE = BUILD / "owner-scope-result.json"
ACCEPTANCE = BUILD / "artifact-acceptance.json"
RECEIPT = ARCH / "c2.3-v1.7-ide-idle-blink-product-card-r10-receipt.json"
REPORT = ROOT / "docs/planning/v1.7.0-ide-idle-blink-card-r10-report.md"
ATTRIBUTION = ARCH / "c2.3-v1.7-block3-r9-r10-attribution.json"
SOURCE = ROOT / "src/optional/c2_mapped_far_service_liveness_v4.s"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "c9e957ca"
FORMAT = "lisp65-c2-v17-ide-idle-blink-product-card-r10-v1"
STATUS = "PASS: V1.7 BLOCK3 PAGE-CONGRUENT R10 GREEN"
READOBJ = CARD.BASE.READOBJ
TOOLCHAIN = ROOT / "tools/llvm-mos/bin"
R9_ELF = R9.ELF
R9_PRG = R9.PRG
R9_PROFILE = R9.PROFILE
R9_PREFLIGHT = R9.PREFLIGHT


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


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


def run(command: list[str], label: str) -> str:
    result = subprocess.run(command, cwd=ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("r10 page-congruent placement authority", "$28000",
                  "a=$80/x=$82", "11-byte congruence gap", "47-byte",
                  "single r10 wplto", "every r9/r10"):
        require(token in text, f"r10 placement authority absent: {token}")
    return {"authority": "git-blob", "commit": AUTHORIZATION, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def setup_plane() -> Path:
    return PREFLIGHT / "setup-owned/static-plane/narrow-static"


def setup_child() -> tuple[Any, dict[str, Any], dict[str, object]]:
    core, activation, cold = R9.ORIGINAL_R8_SETUP()
    PRODUCT.configure_mapped_tenant_lma_policy("map-page-top")
    return core, activation, cold


def install() -> None:
    R9.BUILD = BUILD; R9.PREFLIGHT = PREFLIGHT
    R9.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT; R9.INVOCATION = INVOCATION
    R9.POSTLINK = POSTLINK; R9.ELF = ELF; R9.PRG = PRG; R9.PROFILE = PROFILE
    R9.SCOPE = SCOPE; R9.ACCEPTANCE = ACCEPTANCE
    R9.RECEIPT = RECEIPT; R9.REPORT = REPORT
    R9.DRIVER = DRIVER; R9.AUTHORIZATION = AUTHORIZATION
    R9.FORMAT = FORMAT; R9.STATUS = STATUS
    R9.authority = authority; R9.setup_plane = setup_plane
    R9.setup_child = setup_child
    R9.install()
    HEADER_CARD.consumption_receipts = candidate_consumption_receipts
    ACCEPT.linked_tuple_gate = tuple_LOADADDR_gate
    ACCEPT.EMITTED.acceptance_position_mutations = lambda: [
        "move-LMA-without-tuple-follow", "mutate-tuple-without-LMA-reason",
        "non-page-congruent-LOADADDR"]


def _consumption_rows() -> dict[str, tuple[Path, dict[str, Any]]]:
    paths = {
        "seed": BUILD / "wplto/resident-island-seed.prg.compiler-input-consumption.json",
        "final": BUILD / ("wplto/lisp65-c2-substitution-linked.prg."
                           "compiler-input-consumption.json"),
    }
    return {name: (path, load(path)) for name, path in paths.items()}


def _validate_candidate_consumption(
        rows: dict[str, tuple[Path, dict[str, Any]]]) -> None:
    header = setup_plane() / "c2_lite_static_plane.h"
    header_binding = bind(header)
    plane = setup_plane() / "v6-semantics/bank2-static-code.bin"
    expected = plane.stat().st_size
    require(expected == 52230, "candidate compiler plane extent drift")
    for name, (_path, value) in rows.items():
        flags = value.get("actual_force_include_flags", [])
        require(value.get("status") == "passed-bound-candidate-header-consumed"
                and value.get("bound_header") == header_binding
                and value.get("materialized_header") == header_binding
                and value.get("consumed_value") == expected
                and value.get("materialized_value") == expected
                and value.get("historical_same_basename_accepted") is False
                and len(flags) == 4 and flags[:2] == [
                    "-include", header.relative_to(ROOT).as_posix()]
                and flags[2] == "-include"
                and flags[3] == value["compile_time_assertion"]["path"],
                f"candidate-derived compiler consumption red: {name}")


def candidate_consumption_receipts() -> dict[str, dict[str, Any]]:
    rows = _consumption_rows()
    _validate_candidate_consumption(rows)
    return {name: {"binding": bind(path), "result": value}
            for name, (path, value) in rows.items()}


def consumption_adapter_mutations() -> list[str]:
    rows = _consumption_rows()
    rejected: list[str] = []
    for name, mutate in (
            ("reintroduce-stored-46043", lambda value: value.update(
                consumed_value=46043)),
            ("path-value-diverge", lambda value: value["bound_header"].update(
                path="build/c2.3/v2.0-phase02b-header-consumption-preflight/"
                     "setup-owned/c2_lite_static_plane.h"))):
        trial = {key: (path, json.loads(json.dumps(value)))
                 for key, (path, value) in rows.items()}
        mutate(trial["seed"][1])
        try:
            _validate_candidate_consumption(trial)
        except CardError:
            rejected.append(name)
    require(rejected == ["reintroduce-stored-46043", "path-value-diverge"],
            "compiler-consumption adapter mutation survived")
    return rejected


def static_images() -> list[dict[str, Any]]:
    rows = []
    for key, name, path in CARD.specs(setup_plane()):
        value = load(path)
        rows.append({"name": name, "key": key,
                     "bytes": int(value["code_bytes"]),
                     "authority": bind(path)})
    require(len(rows) == 6 and sum(row["bytes"] for row in rows) == 52230,
            "r10 six-image static owner inventory drift")
    return rows


def expected_vmas() -> dict[str, int]:
    truth = ElfTruth.read(R9_ELF, llvm_readobj=READOBJ,
                          include_section_data=False)
    return {name: truth.section(name).address for name, _prefix in COMPOSED.MAPPED}


def composed(elf: Path = ELF) -> dict[str, Any]:
    value = COMPOSED.derive(
        elf=elf, plane=setup_plane() / "v6-semantics/bank2-static-code.bin",
        readobj=READOBJ, static_images=static_images(),
        expected_vmas=expected_vmas(),
        placement_policy="map-page-top-derived")
    require(len(value["owners"]) == 10 and len(value["reserved_owners"]) == 2
            and [row["bytes"] for row in value["reserved_owners"]] == [11, 47]
            and value["aggregate_free_bytes"] == 11436
            and value["largest_contiguous_hole"]["bytes"] == 11436,
            "r10 named-reserve composed geometry drift")
    return value


def emitted_tuple(truth: ElfTruth) -> tuple[dict[str, int], dict[str, Any]]:
    enter = truth.symbol("c2_mapped_far_enter")
    section = truth.section(enter.section)
    raw = truth.section_bytes(enter.section)[
        enter.value - section.address:enter.value - section.address + enter.bytes]
    operation = GRAPH._interpret_trampoline(raw)["map_operations"][0]
    return ({name: operation[name] for name in "AXYZ"},
            MAP.decode_low(operation["A"], operation["X"]))


def tuple_LOADADDR_gate(elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    operation, decoded = emitted_tuple(truth)
    far = truth.section(".lisp65_c2_mapped_far_service")
    cold = truth.section(".lisp65_c2_mapped_product_cold")
    far_lma = truth.symbol("__lisp65_c2_mapped_far_service_load_start").value
    cold_lma = truth.symbol("__lisp65_c2_mapped_product_cold_load_start").value
    offset = truth.symbol("__lisp65_c2_mapped_shared_offset").value
    map_a = truth.symbol("__lisp65_c2_mapped_far_maplo_a").value
    map_x = truth.symbol("__lisp65_c2_mapped_far_maplo_x").value
    expected = PRICE.encode(offset)
    require(expected is not None and operation == expected
            and (map_a, map_x) == (expected["A"], expected["X"])
            and offset == far_lma - far.address == cold_lma - cold.address
            and MAP.map_low(far.address, decoded) == far_lma
            and MAP.map_low(cold.address, decoded) == cold_lma
            and MAP.map_low(0x3185, decoded) == 0x3185,
            "final emitted MAP tuple differs from LOADADDR authority")
    return {"status": "PASS: EMITTED MAP TUPLE EQUALS LINKER LOADADDR",
        "tuple": operation, "decode": decoded, "shared_offset": offset,
        "linker_symbols": {"maplo_a": map_a, "maplo_x": map_x},
        "tenants": [
            {"section": far.name, "VMA": far.address, "LMA": far_lma,
             "bytes": far.bytes},
            {"section": cold.name, "VMA": cold.address, "LMA": cold_lma,
             "bytes": cold.bytes}],
        "relation": "tuple maps every tenant VMA exactly to final LOADADDR",
        "old_fixed_tuple_authority_active": False}


def tuple_mutations(elf: Path) -> dict[str, str]:
    value = tuple_LOADADDR_gate(elf)
    offset = value["shared_offset"]
    expected = PRICE.encode(offset)
    require(expected is not None, "valid r10 tuple did not encode")
    far = value["tenants"][0]
    require(not PRICE.relation(far["VMA"], far["LMA"] + 0x100, expected),
            "LMA-without-tuple mutation survived")
    mutant = {**expected, "A": (expected["A"] + 1) & 0xff}
    require(not PRICE.relation(far["VMA"], far["LMA"], mutant),
            "tuple-without-LMA mutation survived")
    require(PRICE.encode(offset + 1) is None,
            "non-page-congruent offset mutation survived")
    return {"move-LMA-without-tuple-follow": "rejected",
            "mutate-tuple-without-LMA-reason": "rejected",
            "non-page-congruent-LOADADDR": "rejected"}


def assembler_probe() -> dict[str, Any]:
    source = SOURCE.read_text(encoding="utf-8")
    require("lda #0x40" not in source and "ldx #0x82" not in source
            and "#mos16lo(__lisp65_c2_mapped_far_maplo_a)" in source
            and "#mos16lo(__lisp65_c2_mapped_far_maplo_x)" in source,
            "active source retains the fixed v2 tuple authority")
    output = run([str(TOOLCHAIN / "mos-mega65-clang"), "-Wall", "-I", "src",
                  "-c", str(SOURCE.relative_to(ROOT)), "-o",
                  str(PROBE_OBJECT.relative_to(ROOT))],
                 "r10 assembler effectiveness probe")
    relocations = run([str(TOOLCHAIN / "llvm-readobj"), "--relocations",
                       str(PROBE_OBJECT.relative_to(ROOT))],
                      "r10 assembler relocation probe")
    for symbol in ("__lisp65_c2_mapped_far_maplo_a",
                   "__lisp65_c2_mapped_far_maplo_x"):
        require(relocations.count("R_MOS_ADDR16_LO " + symbol) == 1,
                f"assembler did not consume linker tuple authority: {symbol}")
    return {"status": "PASS: .s ASSEMBLER CONSUMES LINKER SYMBOLS",
            "source": bind(SOURCE), "object": bind(PROBE_OBJECT),
            "relocations": ["R_MOS_ADDR16_LO __lisp65_c2_mapped_far_maplo_a",
                            "R_MOS_ADDR16_LO __lisp65_c2_mapped_far_maplo_x"],
            "compiler_output": " ".join(output.split()),
            "cpp_required": False}


def projected_geometry() -> dict[str, Any]:
    price = load(PRICE.RECEIPT)["priced_MAP_encodable_successor"]
    require(price["status"] == "PRICED-NOT-AUTHORIZED"
            and price["shared_offset"] == 0x28000
            and price["largest_contiguous_hole_bytes"] == 11436,
            "accepted r10 placement price drift")
    return {**price, "status": "PASS: AUTHORIZED PAGE-CONGRUENT PROJECTION"}


def probe_linker() -> dict[str, Any]:
    setup_child()
    script = PRODUCT.linker_script(ownership_opt_in=True)
    PROBE.write_text(script, encoding="utf-8")
    tokens = (
        "__lisp65_c2_mapped_shared_offset =",
        "__lisp65_c2_mapped_far_maplo_a =",
        "__lisp65_c2_mapped_far_maplo_x =",
        "__lisp65_c2_mapped_congruence_gap_start =",
        "__lisp65_c2_mapped_bank_end_reserve_start =",
        "/ 0x100 * 0x100",
    )
    require(all(script.count(token) == 1 for token in tokens[:-1])
            and script.count(tokens[-1]) == 2
            and "AT(0x0002f8b2)" not in script
            and "AT(0x0002fe8d)" not in script,
            "real linker consumer did not materialize one derived authority")
    return {"status": "PASS: REAL LINKER PROJECTS ONE MAP GEOMETRY AUTHORITY",
            "linker_script": bind(PROBE), "derived_tokens": list(tokens),
            "stored_successor_LMA_literals_absent": True,
            "mutations": {"non-page-congruent-LMA": "rejected",
                          "unowned-congruence-gap": "rejected",
                          "unowned-bank-end-reserve": "rejected",
                          "fixed-tuple-source-literal": "rejected"}}


def preflight() -> None:
    require(not any(path.exists() for path in
                    (BUILD, PREFLIGHT, RECEIPT, REPORT)),
            "Block3 r10 is one-shot")
    auth = authority()
    predecessor = load(PRICE.RECEIPT)
    require(predecessor["status"] == PRICE.STATUS
            and predecessor["disposition"]["r10_link_authority_consumed"] is False,
            "r10 representability predecessor drift")
    source = R9_PREFLIGHT / "setup-owned/static-plane/narrow-static"
    setup_plane().parent.mkdir(parents=True)
    shutil.copytree(source, setup_plane())
    linker = probe_linker()
    assembler = assembler_probe()
    value = {"format": FORMAT + "-preflight", "recorded_on": "2026-08-26",
        "status": "PASS: BLOCK3 R10 PAGE-CONGRUENT LINK ARMED 0/1",
        "authority": auth, "representability_predecessor": bind(PRICE.RECEIPT),
        "r9_pair": {"ELF": bind(R9_ELF), "PRG": bind(R9_PRG)},
        "projected_geometry": projected_geometry(),
        "real_linker_projection": linker, "assembler_effectiveness": assembler,
        "static_plane": bind(setup_plane() /
                             "v6-semantics/bank2-static-code.bin"),
        "static_owners": static_images(),
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "scope_runs": 0, "qualification_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "claim_limit": "Link-free r10 placement preflight; media/device closed."}
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("v1.7 Block3 r10: PREFLIGHT PASS offset=0x28000 link=0")


def run_child(action: str) -> dict[str, Any]:
    output = run([sys.executable, str(DRIVER), action], f"r10 child {action}")
    return {"action": action, "status": "PASS",
            "witness": " ".join(output.split())}


def link() -> None:
    pre = load(PREFLIGHT_RECEIPT)
    require(pre["status"] == "PASS: BLOCK3 R10 PAGE-CONGRUENT LINK ARMED 0/1"
            and not BUILD.exists()
            and (not INVOCATION.exists() or PRELINK_RED.exists()),
            "r10 link lifecycle drift")
    if not INVOCATION.exists():
        INVOCATION.write_bytes(canonical({"status": "INVOKED",
            "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
            "budget": {"WPLTO_runs": 1, "product_links": 1}}))
    process = run_child("_produce")
    geometry = composed()
    tuple_value = tuple_LOADADDR_gate(ELF)
    value = {"format": FORMAT + "-postlink", "recorded_on": "2026-08-26",
        "status": "PASS: R10 LINK PAGE-CONGRUENT; ATTRIBUTION PENDING",
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "invocation": bind(INVOCATION), "process": process,
        "r9_pair": {"ELF": bind(R9_ELF), "PRG": bind(R9_PRG)},
        "r10_pair": {"ELF": bind(ELF), "PRG": bind(PRG)},
        "composed_bank2": geometry, "tuple_LOADADDR": tuple_value,
        "tuple_mutations": tuple_mutations(ELF),
        "prelink_adapter_stop": (bind(PRELINK_RED)
                                 if PRELINK_RED.exists() else None),
        "attempt_accounting": {"WPLTO_runs": 1, "product_links": 1,
            "scope_runs": 0, "qualification_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "pair_disposition": "FROZEN-AWAITING-FULL-R9-R10-ATTRIBUTION"}
    POSTLINK.write_bytes(canonical(value))
    print("v1.7 Block3 r10: LINK PASS tuple=80/82 owners=10 attribution=pending")


def record_prelink_red() -> None:
    require(INVOCATION.is_file() and BUILD.is_dir() and not ELF.exists()
            and not PRG.exists() and not PRELINK_RED.exists(),
            "r10 prelink-adapter red lifecycle drift")
    # Reconstruct the exact pre-link configuration layer on which the first
    # attempt stopped.  setup_child() is intentionally earlier than the
    # liveness successor and therefore cannot prove this adapter.
    CARD.BASE.configure_full_candidate()
    PRODUCT.configure_mapped_tenant_lma_policy("map-page-top")
    configured = LIVENESS_CONFIG.configure(PRODUCT)
    # Exercise the real liveness configurator over the page-congruent linker
    # projection; this was the caller that rejected the first attempt.
    script = PRODUCT.linker_script(ownership_opt_in=True)
    require("SIZEOF(.lisp65_c2_mapped_far_service) <= 1499" in script
            and "__lisp65_c2_mapped_shared_offset" in script
            and "__lisp65_c2_mapped_far_service_load_end == 0x0002be18"
                not in script,
            "semantic liveness adapter did not preserve active geometry")
    value = {"status": "PRELINK RED CONVERTED: LIVENESS STRING PIN",
        "authority": authority(), "invocation": bind(INVOCATION),
        "mechanism": ("liveness configurator matched one complete historical "
                      "load-end spelling instead of widening only its owned "
                      "capacity predicates"),
        "conversion": ("capacity predicates are widened structurally; the "
                       "active LOADADDR relation is retained byte-for-byte"),
        "real_consumer_probe": "PASS",
        "configured_successor": configured,
        "mutation": "historical-complete-predicate-string-rejected",
        "accounting": {"WPLTO_runs": 0, "product_links": 0}}
    PRELINK_RED.write_bytes(canonical(value))
    print("v1.7 Block3 r10: PRELINK RED RECORDED WPLTO=0 link=0")


def resume_postlink() -> None:
    require(ELF.is_file() and PRG.is_file() and not POSTLINK.exists(),
            "r10 read-only postlink resume lifecycle drift")
    before = {"ELF": bind(ELF), "PRG": bind(PRG)}
    rows = _consumption_rows()
    _validate_candidate_consumption(rows)
    observed = {name: {
        "receipt": bind(path),
        "bound_header": value["bound_header"],
        "consumed_value": value["consumed_value"],
        "materialized_value": value["materialized_value"],
    } for name, (path, value) in rows.items()}
    POSTLINK_RED.write_bytes(canonical({
        "status": "POSTLINK RED CONVERTED: STORED COMPILER EXTENT",
        "authority": authority(),
        "historical_adapter_expectation": {
            "source": HEADER_CARD.DRIVER.relative_to(ROOT).as_posix(),
            "consumed_value": 46043,
        },
        "candidate_derived_expectation": {
            "source": bind(setup_plane() /
                           "v6-semantics/bank2-static-code.bin"),
            "consumed_value": 52230,
        },
        "observed_real_consumers": observed,
        "classification": "known-derived-not-pinned adapter family",
        "mutations_rejected": consumption_adapter_mutations(),
        "pair_before": before,
        "accounting": {"WPLTO_runs": 0, "product_links": 0},
    }))
    geometry = composed()
    tuple_value = tuple_LOADADDR_gate(ELF)
    value = {"format": FORMAT + "-postlink", "recorded_on": "2026-08-26",
        "status": "PASS: R10 LINK PAGE-CONGRUENT; ATTRIBUTION PENDING",
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "invocation": bind(INVOCATION),
        "process": {"action": "read-only-postlink-resume", "status": "PASS"},
        "r9_pair": {"ELF": bind(R9_ELF), "PRG": bind(R9_PRG)},
        "r10_pair": {"ELF": bind(ELF), "PRG": bind(PRG)},
        "composed_bank2": geometry, "tuple_LOADADDR": tuple_value,
        "tuple_mutations": tuple_mutations(ELF),
        "prelink_adapter_stop": bind(PRELINK_RED),
        "postlink_adapter_stop": bind(POSTLINK_RED),
        "attempt_accounting": {"WPLTO_runs": 1, "product_links": 1,
            "scope_runs": 0, "qualification_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "pair_disposition": "FROZEN-AWAITING-FULL-R9-R10-ATTRIBUTION"}
    require(before == {"ELF": bind(ELF), "PRG": bind(PRG)},
            "read-only postlink resume changed frozen pair")
    POSTLINK.write_bytes(canonical(value))
    print("v1.7 Block3 r10: POSTLINK RESUME PASS tuple=80/82 link=unchanged")


def check_postlink() -> None:
    value = load(POSTLINK)
    require(value["status"] ==
                "PASS: R10 LINK PAGE-CONGRUENT; ATTRIBUTION PENDING"
            and value["authority"] == authority()
            and value["composed_bank2"] == composed()
            and value["tuple_LOADADDR"] == tuple_LOADADDR_gate(ELF)
            and value["attempt_accounting"]["WPLTO_runs"] == 1,
            "r10 postlink evidence drift")
    print("v1.7 Block3 r10: POSTLINK CHECK PASS attribution=pending")


def frozen_pair() -> dict[str, Any]:
    return {"ELF": bind(ELF), "PRG": bind(PRG)}


def render_report(value: dict[str, Any]) -> str:
    pair = value["frozen_pair_after"]
    geometry = value["composed_bank2"]
    return f"""# v1.7 Block 3 page-congruent r10 report

Status: **{value['status']}**

The final ELF derives one shared page-congruent MAP offset, `$28000`, and the
emitted Far-Service entry consumes tuple `A=$80/X=$82`.  The physical tenants
are `$02F8B2..$02FE82` and `$02FE8D..$02FFD1`; their 11-byte congruence gap
and 47-byte Bank-2 end reserve are named owners.  The largest usable hole is
**{geometry['largest_contiguous_hole']['bytes']:,} bytes**.

The frozen r9/r10 attribution names all 3,257 PRG-byte, 35 semantic-symbol,
1,196 removed-relocation, 1,198 added-relocation and two program-header
differences, with zero unexplained members.  The direct roots are the linker
geometry policy and the assembler tuple-owner source; every transitive member
belongs to their deterministic profile/build-ID closure.

The first pre-link stop converted a historical liveness assertion spelling;
the post-link stop converted the inherited 46,043-byte compiler-consumption
equality.  Both real compiler consumers record and enforce the candidate's
52,230-byte header/plane pair.  Neither conversion rebuilt the frozen pair.

Scope and Acceptance pass read-only over:

- ELF: `{pair['ELF']['sha256']}`
- PRG: `{pair['PRG']['sha256']}`

Accounting is one WPLTO/product link, one Scope and one Acceptance.  No medium
was built and no device was contacted.  Media may proceed only from this
SHA-bound candidate and the permanent composed/Tuple=LOADADDR gates.
"""


def _finish_qualification(before: dict[str, Any],
                          processes: list[dict[str, Any]]) -> None:
    attribution = load(ATTRIBUTION)
    scope, acceptance = load(SCOPE), load(ACCEPTANCE)
    after = frozen_pair()
    geometry = composed()
    tuple_value = tuple_LOADADDR_gate(ELF)
    require(before == after
            and attribution["status"] ==
                "PASS: R9/R10 FROZEN PAIR FULLY ATTRIBUTED"
            and scope.get("status") == "PASS"
            and acceptance.get("status") == "PASS"
            and len(geometry["owners"]) == 10
            and geometry["largest_contiguous_hole"]["bytes"] == 11436
            and tuple_value["shared_offset"] == 0x28000,
            "r10 read-only candidate tail red")
    value = {"format": FORMAT, "recorded_on": "2026-08-26",
        "status": STATUS, "authority": authority(),
        "preflight": bind(PREFLIGHT_RECEIPT), "postlink": bind(POSTLINK),
        "attribution": bind(ATTRIBUTION),
        "scope": bind(SCOPE), "acceptance": bind(ACCEPTANCE),
        "scope_status": scope["status"],
        "acceptance_status": acceptance["status"],
        "processes": processes, "tuple_LOADADDR": tuple_value,
        "composed_bank2": geometry,
        "compiler_consumption": candidate_consumption_receipts(),
        "adapter_mutations": consumption_adapter_mutations(),
        "acceptance_tuple_adapter_stop": (bind(ACCEPTANCE_RED)
                                           if ACCEPTANCE_RED.exists() else None),
        "frozen_pair_before": before, "frozen_pair_after": after,
        "attempt_accounting": {"WPLTO_runs": 1, "product_links": 1,
            "scope_runs": 1, "qualification_runs": 1,
            "media_builds": 0, "device_contacts": 0},
        "claim_limit": "Host-qualified r10 product pair; no media/device claim."}
    RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(render_report(value), encoding="utf-8")


def qualify() -> None:
    post = load(POSTLINK)
    attribution = load(ATTRIBUTION)
    require(post["status"] ==
                "PASS: R10 LINK PAGE-CONGRUENT; ATTRIBUTION PENDING"
            and attribution["status"] ==
                "PASS: R9/R10 FROZEN PAIR FULLY ATTRIBUTED"
            and attribution["product_members"]["counts"][
                "unexplained_PRG_bytes"] == 0
            and attribution["product_members"]["counts"][
                "unexplained_symbols"] == 0
            and attribution["product_members"]["counts"][
                "unexplained_relocations"] == 0
            and not RECEIPT.exists() and not REPORT.exists()
            and not SCOPE.exists() and not ACCEPTANCE.exists(),
            "r10 qualification lifecycle drift")
    before = frozen_pair()
    processes = [run_child("_scope"), run_child("_accept")]
    _finish_qualification(before, processes)
    print("v1.7 Block3 r10: FINAL GREEN scope=1 acceptance=1 media=0 device=0")


def resume_acceptance() -> None:
    require(SCOPE.is_file() and load(SCOPE).get("status") == "PASS"
            and not ACCEPTANCE.exists() and not RECEIPT.exists()
            and not REPORT.exists() and not ACCEPTANCE_RED.exists(),
            "r10 acceptance-resume lifecycle drift")
    before = frozen_pair()
    old_expected = {"A": 0x40, "X": 0x82, "Y": 0, "Z": 0x80}
    actual = tuple_LOADADDR_gate(ELF)
    require(actual["tuple"] != old_expected
            and actual["tuple"] == {"A": 0x80, "X": 0x82,
                                     "Y": 0, "Z": 0x80},
            "acceptance tuple-adapter attribution drift")
    ACCEPTANCE_RED.write_bytes(canonical({
        "status": "ACCEPTANCE RED CONVERTED: STORED MAP TUPLE",
        "authority": authority(), "pair": before,
        "historical_expected_tuple": old_expected,
        "candidate_derived_tuple": actual,
        "consumer": "c2_v160_r1_graph_conversions.linked_tuple_gate",
        "conversion": ("derive the encodable tuple from final Far-Service "
                       "VMA and LOADADDR instead of expecting $40/$82"),
        "mutations_rejected": ["move-LMA-without-tuple-follow",
                               "mutate-tuple-without-LMA-reason",
                               "non-page-congruent-LOADADDR"],
        "accounting": {"WPLTO_runs": 0, "product_links": 0,
                       "scope_runs": 0},
    }))
    process = run_child("_accept")
    _finish_qualification(before, [
        {"action": "_scope", "status": "PASS",
         "mode": "already-completed-read-only"}, process])
    print("v1.7 Block3 r10: ACCEPTANCE RESUME PASS pair=unchanged")


def check_qualified() -> None:
    value = load(RECEIPT)
    require(value["status"] == STATUS and value["authority"] == authority()
            and value["postlink"] == bind(POSTLINK)
            and value["attribution"] == bind(ATTRIBUTION)
            and value["scope"] == bind(SCOPE)
            and value["acceptance"] == bind(ACCEPTANCE)
            and value["tuple_LOADADDR"] == tuple_LOADADDR_gate(ELF)
            and value["composed_bank2"] == composed()
            and value["compiler_consumption"] == candidate_consumption_receipts()
            and value["frozen_pair_before"] == frozen_pair()
            and value["frozen_pair_after"] == frozen_pair()
            and REPORT.read_text(encoding="utf-8") == render_report(value),
            "r10 qualified receipt/report drift")
    print("v1.7 Block3 r10: CHECK PASS pair=frozen media=0 device=0")


def permanent_source_gate() -> dict[str, Any]:
    """Prove the living derivation without requiring ignored link outputs."""
    assembler = SOURCE.read_text(encoding="utf-8")
    linker = (ROOT / "tools/host-lisp/c2_product_substitution_link.py").read_text(
        encoding="utf-8")
    composed = (ROOT / "tools/host-lisp/c2_bank2_composed_ownership.py").read_text(
        encoding="utf-8")
    require("lda #mos16lo(__lisp65_c2_mapped_far_maplo_a)" in assembler
            and "ldx #mos16lo(__lisp65_c2_mapped_far_maplo_x)" in assembler
            and "lda #0x40" not in assembler,
            "fixed MAP tuple authority returned to assembler source")
    for token in ("map-page-top", "__lisp65_c2_mapped_shared_offset",
                  "__lisp65_c2_mapped_far_maplo_a",
                  "__lisp65_c2_mapped_far_maplo_x", "/ 0x100 * 0x100"):
        require(token in linker, f"linker MAP derivation absent: {token}")
    for token in ("mapped-tenant-congruence-gap",
                  "mapped-tenant-bank-end-reserve",
                  "offset is not page-encodable"):
        require(token in composed, f"composed MAP law absent: {token}")
    return {"status": "PASS: PAGE ENCODABILITY IS A PLACEMENT LAW",
            "tuple_owner": SOURCE.relative_to(ROOT).as_posix(),
            "placement_authority": "linker-derived shared offset",
            "reserved_owners": ["mapped-tenant-congruence-gap",
                                "mapped-tenant-bank-end-reserve"],
            "fixed_tuple_authority_active": False}


def source_check() -> None:
    value = load(RECEIPT)
    gap = value["composed_bank2"]["reserved_owners"]
    require(value["status"] == STATUS and value["authority"] == authority()
            and value["scope_status"] == value["acceptance_status"] == "PASS"
            and value["tuple_LOADADDR"]["shared_offset"] == 0x28000
            and value["tuple_LOADADDR"]["tuple"] == {
                "A": 0x80, "X": 0x82, "Y": 0, "Z": 0x80}
            and value["tuple_LOADADDR"]["old_fixed_tuple_authority_active"]
                is False
            and value["composed_bank2"]["anchor"]["offset_mod_0x100"] == 0
            and [(row["owner"], row["bytes"]) for row in gap] == [
                ("mapped-tenant-congruence-gap", 11),
                ("mapped-tenant-bank-end-reserve", 47)]
            and value["composed_bank2"]["largest_contiguous_hole"]["bytes"]
                == 11436
            and REPORT.read_text(encoding="utf-8") == render_report(value)
            and permanent_source_gate()["fixed_tuple_authority_active"] is False,
            "r10 permanent source/evidence gate drift")
    print("v1.7 Block3 r10: SOURCE CHECK PASS offset=0x28000 owners=10")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "link", "check-postlink",
                                           "record-prelink-red", "resume-postlink",
                                           "qualify", "check-qualified",
                                           "source-check",
                                           "resume-acceptance",
                                           "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    install()
    {"preflight": preflight, "link": link, "check-postlink": check_postlink,
     "record-prelink-red": record_prelink_red,
     "resume-postlink": resume_postlink,
     "qualify": qualify, "check-qualified": check_qualified,
     "source-check": source_check,
     "resume-acceptance": resume_acceptance,
     "_produce": R9.R8.produce_child, "_scope": R9.R8.scope_child,
     "_accept": R9.R8.acceptance_child}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.7 Block3 r10: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
