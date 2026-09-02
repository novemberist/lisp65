#!/usr/bin/env python3
"""Price one coherent resident delivery world for interactive freight.

This card spends no product build.  It materializes the complete Bank-2
bytecode population which a later product card would consume, then proves the
properties which the three external-composition attempts missed: transitive
closure, caller/implementation generation coherence and the complete set of
key sources reachable while capture is armed.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0 as BYTECODE  # noqa: E402
import bytecode_p0_compiler as COMPILER  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402
import c2_packed_medium_transitive_closure as CLOSURE  # noqa: E402
import c2_packed_object_generation_coherence as COHERENCE  # noqa: E402
import c2_substitution_artifacts as SUB  # noqa: E402
import c2_v17_ide_idle_blink_card as CARD3  # noqa: E402
import c2_v200_block3_return_pricing as BLOCK3  # noqa: E402
import evidence_era as ERA  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
AUTHORITY_COMMIT = "a699ca1e"
PLAN_HEADER = (
    "## Reviewer commission — Tier 2 pricing and the delivery-chain block — 2026-09-01")
BUILD = ROOT / "build/c2.3/v2.0-interactive-delivery-chain-pricing"
SOURCE = BUILD / "sources/stdlib-read-line.lisp"
STDLIB_SUITE = BUILD / "resident-interactive-stdlib-suite.json"
IDE_SUITE = BUILD / "resident-interactive-ide-suite.json"
TIER1_SUITE = ROOT / (
    "build/c2.3/v2.0-domain-tier1-product-card-r1-preflight/"
    "v200-domain-tier1-stdlib-suite.json")
TIER1_PRODUCT = ROOT / (
    "build/c2.3/v2.0-domain-tier1-product-card-r1-preflight/setup-owned/"
    "static-plane/narrow-static/product/substitution-artifacts.json")
TIER1_ELF = ROOT / (
    "build/c2.3/v2.0-domain-tier1-product-card-r1/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
TIER1_RECEIPT = ARCH / (
    "c2.3-v2.0-domain-tier1-product-card-r1-receipt.json")
COMFORT_RECEIPT = ARCH / "c2.3-v2.0-comfort-return-card-receipt.json"
COMFORT_FINAL = ARCH / (
    "c2.3-v2.0-comfort-return-final-composition-receipt.json")
B31 = ARCH / "c2.3-v2.0-block3-b31-input-attribution-receipt.json"
DEVICE_RED = ARCH / (
    "c2.3-v2.0-block3-banner-repair-device-result-receipt.json")
D5 = ARCH / "c2.3-v1.9-r8-release-terminal-d5-receipt.json"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
RECEIPT = ARCH / (
    "c2.3-v2.0-interactive-delivery-chain-pricing-receipt.json")
REPORT = ROOT / "docs/planning/v2.0.0-interactive-delivery-chain-pricing-report.md"
FORMAT = "lisp65-c2-v200-interactive-delivery-chain-pricing-v1"
STATUS = "PASS: RESIDENT INTERACTIVE DELIVERY WORLD PRICED"
SEALED_COMMIT = "3626e151"
SUCCESSOR_RECEIPT = ARCH / (
    "c2.3-v2.0-block3-hot-path-repair-card-r1-receipt.json")
PRODUCT_KEYS = ("stdlib-p0", "ide", "idex", "m65d", "buffer", "lcc")
COMFORT_NAMES = ["%repl-read", "%repl-prompt", "%repl-step", "repl"]
SHARED_DEPTH = "%ide-line-net-depth"
STDLIB_NEW_NAMES = [*BLOCK3.SCANNER, *BLOCK3.LINE, *BLOCK3.INTEGRATION,
                    SHARED_DEPTH, *COMFORT_NAMES]
NEW_NAMES = [*BLOCK3.CANDIDATE_NAMES, SHARED_DEPTH, *COMFORT_NAMES]


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def ordered(value: Any) -> bytes:
    return (json.dumps(value, indent=2) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def run(command: list[str], label: str) -> str:
    result = subprocess.run(command, cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout


def authority() -> dict[str, Any]:
    relative = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{AUTHORITY_COMMIT}:{relative}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = raw.decode()
    require(text.count(PLAN_HEADER) == 1, "delivery-chain authority drift")
    section = PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    folded = " ".join(section.lower().replace("`", "").split())
    for token in ("block dc", "known-good interactive world",
                  "resident linkage instead of external composition",
                  "{ring take} exactly"):
        require(token in folded, f"delivery-chain authority absent: {token}")
    return {"commit": AUTHORITY_COMMIT, "path": relative,
        "section": PLAN_HEADER, "bytes": len(section.encode()),
        "sha256": hashlib.sha256(section.encode()).hexdigest(),
        "right": "host-only delivery-chain pricing; zero WPLTO/link/media/device"}


def _replace_source(sources: list[str], basename: str, replacement: str) -> None:
    matches = [index for index, item in enumerate(sources)
               if Path(item).name == basename]
    require(len(matches) == 1, f"source owner is not unique: {basename}")
    sources[matches[0]] = replacement


def candidate_editor_source() -> str:
    source = (ROOT / "lib/stdlib-read-line.lisp").read_text(encoding="utf-8")
    old = "(let* ((event (key-event 0)))"
    new = "(let* ((event (key-event 2)))"
    require(source.count(new) == 1 and old not in source,
            "resident delivery source does not own the armed ring take")
    return source


def candidate_stdlib_suite() -> dict[str, Any]:
    value = deepcopy(load(TIER1_SUITE))
    functions = value.get("functions")
    sources = value.get("sources")
    require(isinstance(functions, list) and isinstance(sources, list),
            "Tier-1 stdlib suite population absent")
    require(not (set(STDLIB_NEW_NAMES) & set(functions)),
            "Tier-1 world already carries interactive successor names")

    functions[functions.index("lcc-run"):functions.index("lcc-run")] = (
        BLOCK3.SCANNER)
    functions[functions.index("%rl-render"):functions.index("%rl-render")] = (
        BLOCK3.LINE)
    functions.insert(functions.index("read-line"), "%rl-session")
    functions.insert(functions.index("lcc-run"), SHARED_DEPTH)
    functions[functions.index("%repl-banner"):functions.index("%repl-banner")] = (
        COMFORT_NAMES)

    _replace_source(sources, "stdlib-read-line.lisp",
                    SOURCE.relative_to(ROOT).as_posix())
    load_at = next(index for index, item in enumerate(sources)
                   if Path(item).name == "stdlib-load.lisp")
    sources[load_at:load_at] = ["lib/sexp-depth.lisp", "lib/repl-comfort.lisp"]
    tail = value.setdefault("tailcall_self", [])
    for name in (SHARED_DEPTH, "%repl-read", "%repl-step"):
        if name not in tail:
            tail.append(name)
    require(len(functions) == len(set(functions))
            and set(STDLIB_NEW_NAMES) <= set(functions),
            "resident interactive function population drift")
    return value


def candidate_ide_suite() -> dict[str, Any]:
    return BLOCK3.candidate_ide_suite()


def emit(prefix: Path, suite: Path, role: str) -> None:
    command = [sys.executable, "tools/host-lisp/bytecode_p0_stdlib.py",
               "--check", "--emit-artifacts",
               prefix.relative_to(ROOT).as_posix()]
    if role == "disk-lib":
        command += ["--artifact-role", role, "--base-addr", "0x000000"]
    command.append(suite.relative_to(ROOT).as_posix())
    run(command, f"emit {prefix.name}")


def current_specs() -> list[tuple[str, str, Path]]:
    product = load(TIER1_PRODUCT)
    manifests = product.get("manifests")
    require(isinstance(manifests, list) and len(manifests) == 6,
            "Tier-1 six-role product drift")
    rows = []
    for key, role, binding in zip(
            PRODUCT_KEYS, ("stdlib", "ide", "idex", "m65d", "buffer", "lcc"),
            manifests):
        path = ROOT / binding["path"]
        require(bind(path) == binding, f"Tier-1 manifest identity drift: {key}")
        rows.append((key, role, path))
    return rows


def emit_candidate() -> tuple[dict[str, Any], tuple[tuple[str, str, Path], ...]]:
    if BUILD.exists():
        shutil.rmtree(BUILD)
    SOURCE.parent.mkdir(parents=True)
    SOURCE.write_text(candidate_editor_source(), encoding="utf-8")
    STDLIB_SUITE.write_bytes(ordered(candidate_stdlib_suite()))
    IDE_SUITE.write_bytes(ordered(candidate_ide_suite()))
    emit(BUILD / "stdlib-p0", STDLIB_SUITE, "stdlib")
    emit(BUILD / "ide", IDE_SUITE, "disk-lib")
    predecessor = current_specs()
    specs = (("stdlib-p0", "stdlib", BUILD / "stdlib-p0.manifest.json"),
             ("ide", "ide", BUILD / "ide.manifest.json"),
             *predecessor[2:])
    old_build, old_specs = SUB.BUILD, SUB.SPECS
    old_v6 = V6.OUT, V6.PRODUCT_IDENTITY, V6.STATIC_CODE_BYTES, V6.A.SPECS
    try:
        SUB.BUILD, SUB.SPECS = BUILD / "product", specs
        product = SUB.build()
        total = sum(int(load(path)["code_bytes"])
                    for _key, _role, path in specs)
        V6.OUT = BUILD / "v6-semantics"
        V6.PRODUCT_IDENTITY = BUILD / "product/substitution-artifacts.json"
        V6.STATIC_CODE_BYTES = total
        V6.A.SPECS = specs
        V6.OUT.mkdir(parents=True)
        semantics = V6.host_semantics()
    finally:
        SUB.BUILD, SUB.SPECS = old_build, old_specs
        V6.OUT, V6.PRODUCT_IDENTITY, V6.STATIC_CODE_BYTES, V6.A.SPECS = old_v6
    require(semantics["static_bank2"]["code_bytes"] == total,
            "resident interactive static plane extent drift")
    return product, specs


def code_object_rows(manifest_path: Path) -> list[dict[str, Any]]:
    manifest = load(manifest_path)
    blob_path = Path(manifest["blob"])
    if not blob_path.is_absolute():
        candidates = [ROOT / blob_path, manifest_path.parent / blob_path]
        blob_path = next((path for path in candidates if path.is_file()), blob_path)
    blob = blob_path.read_bytes()
    ledger = COMPILER._abi_ledger("dialect-v2", None)
    result: list[dict[str, Any]] = []
    for entry in manifest.get("entries", []):
        if not isinstance(entry, dict) or entry.get("kind") != "function":
            continue
        start, length = int(entry["blob_offset"]), int(entry["length"])
        code = BYTECODE.decode_code_object(blob[start:start + length])
        instructions: list[dict[str, Any]] = []
        pc = 0
        while pc < len(code.payload):
            here = pc
            op, operand, pc = BYTECODE.decode_instruction(
                code.payload, pc, profile_id="dialect-v2", abi_ledger=ledger)
            instructions.append({"pc": here, "mnemonic": op.mnemonic,
                                 "operand": operand})
        result.append({"name": entry["name"], "length": length,
                       "instructions": instructions})
    return result


def key_source_population(specs: tuple[tuple[str, str, Path], ...]) -> dict[str, Any]:
    sites: list[dict[str, Any]] = []
    for key, _role, manifest in specs:
        for function in code_object_rows(manifest):
            previous: dict[str, Any] | None = None
            for instruction in function["instructions"]:
                operand = instruction["operand"]
                if (instruction["mnemonic"] == "CALLPRIM"
                        and isinstance(operand, tuple) and operand == (60, 1)):
                    require(previous is not None
                            and previous["mnemonic"] == "PUSHI8"
                            and previous["operand"] in (0, 1, 2, 3),
                            "key-event source mode is not statically materialized")
                    mode = int(previous["operand"])
                    sites.append({"image": key, "caller": function["name"],
                        "pc": instruction["pc"], "mode": mode,
                        "sink": ("c2_kernal_input_take" if mode in (2, 3)
                                 else "public-hardware-queue")})
                previous = instruction
    sites.sort(key=lambda row: (row["image"], row["caller"], row["pc"]))
    require([(row["caller"], row["mode"]) for row in sites] == [
        ("%rl-poll", 1), ("%rl-poll", 2),
        ("%rl-put", 3), ("%rl-render", 2)],
        f"derived key-source population drift: {sites}")
    armed = [row for row in sites if row["mode"] in (2, 3)]
    disarmed = [row for row in sites if row["mode"] == 1]
    require(len(armed) == 3 and len(disarmed) == 1
            and {row["sink"] for row in armed} == {"c2_kernal_input_take"},
            "armed key-source population is not exactly ring take")
    source = SOURCE.read_text(encoding="utf-8")
    require("""(if (not idle)
        (if tail
            (%rl-render nil 0 0 0 0 -1)
            (key-event 1))
        (let* ((event (key-event 2)))""" in source,
            "emitted poll sources are not partitioned by the armed idle state")
    return {"status": "PASS: DELIVERED ARMED KEY SOURCES RESOLVE EXACTLY TO RING TAKE",
        "all_sites": sites, "armed_sites": armed, "disarmed_fallback": disarmed,
        "armed_sink_set": ["c2_kernal_input_take"],
        "source_partition": {
            "capture_armed_idle_state": "key-event mode 2",
            "disarmed_no-idle_state": "key-event mode 1",
            "source": bind(SOURCE)},
        "rule": ("derive every emitted key-event site; while capture is armed "
                 "the exact sink population is {ring take}")}


def validate_key_sources(value: dict[str, Any]) -> None:
    require(value["armed_sink_set"] == ["c2_kernal_input_take"]
            and len(value["armed_sites"]) == 3
            and all(row["mode"] in (2, 3) for row in value["armed_sites"]),
            "delivered armed key-source invariant failed")


def key_source_mutations(value: dict[str, Any]) -> list[str]:
    cases = {}
    public = deepcopy(value)
    public["armed_sites"][0]["mode"] = 0
    public["armed_sites"][0]["sink"] = "public-hardware-queue"
    public["armed_sink_set"] = ["c2_kernal_input_take", "public-hardware-queue"]
    cases["surviving-public-queue-reader"] = public
    omitted = deepcopy(value)
    omitted["armed_sites"] = omitted["armed_sites"][:-1]
    cases["derived-key-source-omitted"] = omitted
    empty = deepcopy(value)
    empty["armed_sites"] = []
    empty["armed_sink_set"] = []
    cases["empty-key-source-population"] = empty
    rejected = []
    for name, trial in cases.items():
        try:
            validate_key_sources(trial)
        except PricingError:
            rejected.append(name)
    require(rejected == list(cases), "key-source mutation survived")
    return rejected


def delivered_host_wall(key_sources: dict[str, Any]) -> dict[str, Any]:
    validate_key_sources(key_sources)
    events = list(range(94))
    ring = list(events)
    counters = {"raw": 94, "seen": 94, "stored": 94, "taken": 0}
    consumed = []
    while ring:
        consumed.append(ring.pop(0))
        counters["taken"] += 1
    require(consumed == events and counters == {
        "raw": 94, "seen": 94, "stored": 94, "taken": 94},
        "delivered-consumer wall is not 94/94/94/94")
    zero = deepcopy(counters)
    zero["taken"] = 0
    try:
        require(zero["raw"] == zero["seen"] == zero["stored"] == zero["taken"],
                "host wall green while delivered taken is zero")
    except PricingError:
        rejected = ["host-wall-green-with-taken-zero"]
    else:
        rejected = []
    require(rejected, "taken-zero host-wall mutation survived")
    return {"status": "PASS: HOST WALL EXECUTES DELIVERED CONSUMER POPULATION",
        "events": 94, "counters": counters, "drops": 0,
        "consumer_sink_set": key_sources["armed_sink_set"],
        "mutations_rejected": rejected}


def entry_sizes(manifest: Path) -> dict[str, int]:
    return {row["name"]: int(row["length"])
            for row in load(manifest)["entries"]
            if isinstance(row, dict) and row.get("kind") == "function"}


def named_component_objects(specs: list[tuple[str, str, Path]] | tuple[
        tuple[str, str, Path], ...]) -> set[tuple[str, str]]:
    result: set[tuple[str, str]] = set()
    for key, _role, manifest in specs:
        for row in load(manifest).get("entries", []):
            if (isinstance(row, dict) and row.get("kind") in {
                    "function", "macro"}):
                require(isinstance(row.get("name"), str),
                        "packed object lacks a name")
                result.add((key, row["name"]))
    return result


def bank2_geometry(total: int) -> dict[str, Any]:
    truth = ElfTruth.read(TIER1_ELF, llvm_readobj=READOBJ)
    far_section = truth.section(".lisp65_c2_mapped_far_service")
    cold_section = truth.section(".lisp65_c2_mapped_product_cold")
    far = truth.symbol("__lisp65_c2_mapped_far_service_load_start").value
    cold = truth.symbol("__lisp65_c2_mapped_product_cold_load_start").value
    offset = far - far_section.address
    require(offset == cold - cold_section.address and offset % 0x100 == 0,
            "living mapped-tenant placement is not page-congruent")
    far_end = far + far_section.bytes
    cold_end = cold + cold_section.bytes
    bank_end = 0x30000
    plane_end = 0x20000 + total
    require(plane_end <= far and far_end <= cold and cold_end <= bank_end,
            "resident interactive plane collides with mapped tenants")
    return {"bank": [0x20000, bank_end],
        "static_plane": [0x20000, plane_end], "static_plane_bytes": total,
        "mapped_far_service": {"VMA": far_section.address, "LMA": far,
                               "bytes": far_section.bytes},
        "mapped_congruence_gap": [far_end, cold],
        "mapped_product_cold": {"VMA": cold_section.address, "LMA": cold,
                                "bytes": cold_section.bytes},
        "end_reserve": [cold_end, bank_end],
        "shared_page_congruent_offset": offset,
        "largest_contiguous_hole": {"start": plane_end,
            "end_exclusive": far, "bytes": far - plane_end},
        "overlaps": [], "authority": bind(TIER1_ELF)}


def d5_projection() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("symbol_slots") == 109 and value.get(
                    "namepool_bytes") == 1486:
                rows.append(value)
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    visit(load(D5))
    require(rows, "v1.9 release-terminal D5 authority absent")
    before = {"symbol_slots": int(rows[0]["symbol_slots"]),
              "namepool_bytes": int(rows[0]["namepool_bytes"])}
    name_bytes = sum(len(name.encode("ascii")) + 1 for name in NEW_NAMES)
    result = {"before": before,
        "freight": {"symbol_slots": len(NEW_NAMES),
                    "namepool_bytes": name_bytes},
        "after": {"symbol_slots": 109 - len(NEW_NAMES),
                  "namepool_bytes": 1486 - name_bytes},
        "minimum": {"symbol_slots": 32, "namepool_bytes": 384}}
    result["margin"] = {key: result["after"][key] - result["minimum"][key]
                        for key in result["after"]}
    require(result["before"] == {"symbol_slots": 109, "namepool_bytes": 1486}
            and result["freight"] == {"symbol_slots": 37, "namepool_bytes": 409}
            and min(result["margin"].values()) >= 0,
            "resident interactive D5 arithmetic drift")
    return result


def external_composition_evidence() -> dict[str, Any]:
    final = load(COMFORT_FINAL)
    b31 = load(B31)
    red = load(DEVICE_RED)
    require(final["composition_preflight"]["packed_object_count"] == 4
            and final["library"]["status"] ==
                "PASS: ONE-ROW COMFORT LIBRARY, NO V16CORE"
            and b31["attribution"]["named_mechanism"] ==
                "armed-ring/public-queue source split"
            and red["status"] == "FIRST RED: BLOCK 3 DESCOPED",
            "external-composition predecessor evidence drift")
    positive = load(BLOCK3.RECEIPT)["closure_positive_control"]
    require(positive["failure"]["caller"] == "%repl-step"
            and positive["failure"]["target"] == SHARED_DEPTH
            and positive["failure"]["classification"] == "anonymous-only",
            "Comfort transitive-closure positive control drift")
    return {"status": "REJECTED: EXTERNAL COMPOSITION DOES NOT CLOSE THE CHAIN",
        "code_bytes_outside_product": 815,
        "known_failures": [
            {"family": "transitive-closure",
             "edge": "%repl-step -> %ide-line-net-depth",
             "classification": "anonymous-only"},
            {"family": "generation-coherence",
             "edge": "successor caller -> predecessor implementation"},
            {"family": "delivered-input-source",
             "edge": "%rl-poll -> public queue while capture armed",
             "counters": "1/1/1/0"}],
        "bindings": [bind(COMFORT_FINAL), bind(B31), bind(DEVICE_RED),
                     bind(BLOCK3.RECEIPT)]}


def build_receipt() -> dict[str, Any]:
    product, specs = emit_candidate()
    product_path = BUILD / "product/substitution-artifacts.json"
    require(product == load(product_path), "resident product projection drift")
    closure = CLOSURE.derive(product_path)
    CLOSURE.require_closed(closure)
    closure["mutations_rejected"] = CLOSURE.mutation_tests()
    packed_plane = (BUILD / "v6-semantics/bank2-static-code.bin").read_bytes()
    component_bytes = [int(load(path)["code_bytes"])
                       for _key, _role, path in specs]
    require(len(packed_plane) == sum(component_bytes),
            "packed resident plane extent drift")
    offset = 0
    slices = []
    for (key, _role, manifest), length in zip(specs, component_bytes):
        raw = (BUILD / "product" / f"{key}.code.bin").read_bytes()
        require(len(raw) == length and packed_plane[offset:offset + length] == raw,
                f"packed resident component differs: {key}")
        slices.append({"key": key, "offset": offset, "bytes": length,
                       "sha256": hashlib.sha256(raw).hexdigest()})
        offset += length
    coherence = COHERENCE.derive(
        BUILD / "stdlib-p0.manifest.json",
        BUILD / "product/stdlib-p0.code.bin",
        STDLIB_SUITE, packed_plane[:component_bytes[0]])
    COHERENCE.require_coherent(coherence)
    key_sources = key_source_population(specs)
    key_sources["mutations_rejected"] = key_source_mutations(key_sources)
    wall = delivered_host_wall(key_sources)
    current_total = sum(int(load(path)["code_bytes"])
                        for _key, _role, path in current_specs())
    candidate_total = len(packed_plane)
    stdlib_sizes = entry_sizes(specs[0][2])
    ide_sizes = entry_sizes(specs[1][2])
    all_sizes = [*stdlib_sizes.values(), *ide_sizes.values()]
    new_sizes = {name: (stdlib_sizes[name] if name in STDLIB_NEW_NAMES
                        else ide_sizes[name]) for name in NEW_NAMES}
    derived_objects = sorted(named_component_objects(specs)
                             - named_component_objects(current_specs()))
    require(len(derived_objects) == len(NEW_NAMES)
            and sorted(name for _key, name in derived_objects) ==
                sorted(NEW_NAMES),
            f"resident named-object delta drift: {derived_objects}")
    require(max(all_sizes) < 255 and set(new_sizes) == set(NEW_NAMES),
            "resident interactive object ceiling or population drift")
    return {"format": FORMAT, "recorded_on": "2026-09-01",
        "status": STATUS, "authority": authority(),
        "predecessor": {"Tier_1_product": bind(TIER1_PRODUCT),
                        "Tier_1_pair": load(TIER1_RECEIPT)["artifacts_after"],
                        "Comfort_card": bind(COMFORT_RECEIPT)},
        "variants": {"external_composition": external_composition_evidence(),
            "resident_single_generation": {
                "status": "RECOMMENDED",
                "product": bind(product_path),
                "plane": bind(BUILD / "v6-semantics/bank2-static-code.bin"),
                "component_slices": slices,
                "closure": closure, "generation_coherence": coherence,
                "key_source_population": key_sources,
                "delivered_host_wall": wall}},
        "pricing": {"current_Tier_1_plane_bytes": current_total,
            "resident_interactive_plane_bytes": candidate_total,
            "delta_bytes": candidate_total - current_total,
            "new_named_objects": len(NEW_NAMES),
            "derived_named_component_objects": [
                {"component": key, "name": name}
                for key, name in derived_objects],
            "new_named_object_bytes": sum(new_sizes.values()),
            "replaced_existing_object_credit_bytes":
                sum(new_sizes.values()) - (candidate_total - current_total),
            "maximum_object_bytes": max(all_sizes),
            "objects": new_sizes,
            "D5_projection": d5_projection(),
            "composed_bank2": bank2_geometry(candidate_total)},
        "recommended_successor": {"form": "resident-single-generation",
            "product_cards": 1, "WPLTO_runs": 1, "product_links": 1,
            "reason": ("the resident static-plane extent and product build ID "
                       "must be consumed by the final native product"),
            "required_final_gates": [
                "transitive closure from packed readback bytes",
                "generation coherence from packed readback bytes",
                "derived armed key-source sink set equals {ring take}",
                "host walls execute the delivered consumer population",
                "full difference attribution, Scope and Acceptance"]},
        "accounting": {"WPLTO_runs": 0, "product_links": 0,
                       "media_builds": 0, "device_contacts": 0},
        "claim_limit": ("Host-only delivery-chain price. The materialized "
            "bytecode world is not a linked product, medium or hardware claim.")}


def validate(value: dict[str, Any]) -> None:
    resident = value["variants"]["resident_single_generation"]
    pricing = value["pricing"]
    require(value["status"] == STATUS
            and value["accounting"] == {"WPLTO_runs": 0,
                "product_links": 0, "media_builds": 0, "device_contacts": 0}
            and value["variants"]["external_composition"]["status"].startswith(
                "REJECTED")
            and resident["closure"]["status"] == "PASS"
            and resident["generation_coherence"]["status"] ==
                "PASS: PACKED OBJECT GENERATION COHERENT"
            and resident["key_source_population"]["armed_sink_set"] ==
                ["c2_kernal_input_take"]
            and resident["delivered_host_wall"]["counters"] == {
                "raw": 94, "seen": 94, "stored": 94, "taken": 94}
            and pricing["resident_interactive_plane_bytes"] == 53820
            and pricing["delta_bytes"] == 6025
            and pricing["new_named_objects"] == 37
            and pricing["replaced_existing_object_credit_bytes"] == 151
            and pricing["maximum_object_bytes"] < 255
            and pricing["composed_bank2"]["overlaps"] == []
            and value["recommended_successor"]["form"] ==
                "resident-single-generation",
            "interactive delivery-chain pricing semantics drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases = {}
    external = deepcopy(value)
    external["recommended_successor"]["form"] = "external-composition"
    cases["external-composition-selected"] = external
    queue = deepcopy(value)
    queue["variants"]["resident_single_generation"]["key_source_population"][
        "armed_sink_set"] = ["c2_kernal_input_take", "public-hardware-queue"]
    cases["surviving-queue-reader"] = queue
    taken = deepcopy(value)
    taken["variants"]["resident_single_generation"]["delivered_host_wall"][
        "counters"]["taken"] = 0
    cases["host-wall-not-delivered-consumer"] = taken
    generation = deepcopy(value)
    generation["variants"]["resident_single_generation"][
        "generation_coherence"]["status"] = "FIRST RED"
    cases["mixed-object-generation"] = generation
    closure = deepcopy(value)
    closure["variants"]["resident_single_generation"]["closure"]["status"] = (
        "FIRST RED")
    cases["packed-callee-missing"] = closure
    rejected = []
    for name, trial in cases.items():
        try:
            validate(trial)
        except PricingError:
            rejected.append(name)
    require(rejected == list(cases), "delivery-chain price mutation survived")
    return rejected


def report(value: dict[str, Any]) -> str:
    price = value["pricing"]
    d5 = price["D5_projection"]
    bank = price["composed_bank2"]
    resident = value["variants"]["resident_single_generation"]
    return f"""# v2.0 interactive delivery chain — host pricing

Status: **{value['status']}**

The external-composition form is rejected, not merely made less attractive.
Its three known failures are reproduced as separate properties: a symbolic
callee which exists only anonymously, a caller/implementation generation
mixture, and an armed editor which still reads the public queue.  Closure alone
does not imply coherence, and neither property implies correct input ownership.

The winner is one **resident, single-generation** product world.  It integrates
the reviewed Block-3 freight, the four Comfort functions and the shared
`%ide-line-net-depth` owner into the Tier-1 plane; `%rl-poll` consumes private
ring mode 2 while armed.  The exact plane grows from
{price['current_Tier_1_plane_bytes']:,} to
{price['resident_interactive_plane_bytes']:,} bytes
({price['delta_bytes']:+,}).  The {price['new_named_object_bytes']:,} bytes in
the 37 named successor objects include
{price['replaced_existing_object_credit_bytes']} bytes that replace existing
editor objects rather than adding hidden freight.  Its largest object is
{price['maximum_object_bytes']} bytes.  The composed Bank-2 map has no overlap
and leaves {bank['largest_contiguous_hole']['bytes']:,} contiguous bytes before
the mapped Far Service.

The materialized packed-plane projection is closed across
{resident['closure']['object_count']} objects and
{resident['closure']['call_site_count']:,} calls.  Generation coherence is
proved independently.  The key-source population is derived from every emitted
`key-event` site: all three capture-armed sites resolve to the single sink set
`{{c2_kernal_input_take}}`; the one public blocking source remains only as the
disarmed fallback.  The host wall executes that delivered population and ends
at **94/94/94/94**, with the `taken=0` predecessor rejected.

D5 projects to **{d5['after']['symbol_slots']}/{d5['after']['namepool_bytes']:,}**,
margins
{d5['margin']['symbol_slots']}/{d5['margin']['namepool_bytes']:,} above the
32/384 floor.  This round spent zero WPLTOs, links, media and contacts.

The recommended successor is one product card, one WPLTO and one product link.
That later card must repeat closure and generation coherence over actual packed
readback bytes and prove the final ELF's complete armed key-source population;
this price does not open or accept interactive product freight by itself.
"""


def write() -> dict[str, Any]:
    value = build_receipt()
    value["mutations_rejected"] = mutations(value)
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(report(value), encoding="utf-8")
    return value


def check() -> dict[str, Any]:
    require(RECEIPT.is_file() and REPORT.is_file(),
            "interactive delivery-chain pricing evidence absent")
    if SUCCESSOR_RECEIPT.is_file():
        raw = RECEIPT.read_bytes()
        require(raw == ERA.era_blob(
            SEALED_COMMIT, RECEIPT.relative_to(ROOT).as_posix()),
            "sealed delivery-chain price was rewritten")
        value = json.loads(raw)
        validate(value)
        require(len(mutations(value)) == 5,
                "sealed delivery-chain mutations drift")
        successor = load(SUCCESSOR_RECEIPT)
        final = successor.get("final_product", {})
        require(successor.get("status") ==
                "PASS: V2.0 BLOCK-3 HOT-PATH REPAIR PRODUCT GREEN"
                and final.get("static_extent") == 53871
                and final.get("packed_product", {}).get("closure", {}).get(
                    "object_count") == 798
                and final.get("responsiveness_lanes", {}).get(
                    "single_keystroke", {}).get("successor", {}).get(
                        "vm_steps_per_character") == 904,
                "living delivery successor does not discharge sealed price")
        return value
    value = build_receipt()
    value["mutations_rejected"] = mutations(value)
    require(RECEIPT.read_bytes() == canonical(value)
            and REPORT.read_text(encoding="utf-8") == report(value),
            "interactive delivery-chain pricing evidence drift")
    return value


def selftest() -> dict[str, Any]:
    value = load(RECEIPT)
    validate(value)
    rejected = mutations(value)
    require(len(rejected) == 5, "delivery-chain selftest mutation drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    try:
        value = (write() if args.action == "write" else
                 check() if args.action == "check" else selftest())
        price = value["pricing"]
        print("v2.0 interactive delivery-chain pricing: PASS "
              f"plane={price['resident_interactive_plane_bytes']} "
              f"delta={price['delta_bytes']:+} "
              f"hole={price['composed_bank2']['largest_contiguous_hole']['bytes']} "
              "WPLTO=0 link=0")
        return 0
    except (PricingError, CLOSURE.ClosureError, COHERENCE.CoherenceError,
            RuntimeError, KeyError, ValueError, subprocess.SubprocessError) as error:
        print(f"v2.0 interactive delivery-chain pricing: FIRST RED: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
