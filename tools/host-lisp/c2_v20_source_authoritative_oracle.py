#!/usr/bin/env python3
"""Qualify the phase-02a delivery-authoritative convergence oracle.

This is deliberately a host/pre-card gate.  It executes the real source
generator and target compiler, but no WPLTO, product link, media build or
device contact.  The owner-veto boundary remains closed after a green run.
"""

from __future__ import annotations

from copy import deepcopy
import ast
import functools
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_lite_v6_product_probe as V6  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CONTRACT = ROOT / "config/c2-v20-source-authoritative-oracle-contract.json"
PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
RECEIPT = ARCH / "c2.3-v2.0-source-authoritative-oracle-receipt.json"
SOURCE_REBIND = ARCH / (
    "c2.3-v2.0-source-authoritative-oracle-rebind-2026-08-14.json")
SOURCE = ROOT / "scripts/c2-stream-decoder.c"
GENERATOR = ROOT / "tools/host-lisp/c2_lite_v6_product_probe.py"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "5ebd8ed5"
INTEGRATION_AUTHORIZATION = "50bddcd6"
RECORDED_ON = "2026-08-13"
FORMAT = "lisp65-c2.3-v20-source-authoritative-oracle-v1"
MAX_SLICE_BYTES = 1792


class OracleError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise OracleError(message)


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


def git_authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{AUTHORIZATION}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    text = " ".join(raw.decode().split()).lower()
    require("source-authoritative oracle fix" in text
            and "delivery-bound truth" in text
            and "owner veto open before the card runs" in text,
            "oracle-fix owner authority drift")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def git_integration_authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{INTEGRATION_AUTHORIZATION}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    full = subprocess.run(
        ["git", "rev-parse", f"{INTEGRATION_AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True,
        stdout=subprocess.PIPE).stdout.strip()
    text = " ".join(raw.decode().split()).lower()
    require("replacement card ii authorized" in text
            and "one owning translation unit" in text
            and "real multi-tu build" in text,
            "oracle integration authority drift")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def crc16(raw: bytes) -> int:
    crc = 0xffff
    for value in raw:
        crc ^= value << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xffff \
                if crc & 0x8000 else (crc << 1) & 0xffff
    return crc


def u16(raw: bytes, offset: int) -> int:
    return int.from_bytes(raw[offset:offset + 2], "little")


def u24(raw: bytes, offset: int) -> int:
    return int.from_bytes(raw[offset:offset + 3], "little")


def delivery_rows(contract: dict[str, Any]) -> dict[str, Any]:
    truth = contract["delivery_truth"]
    shelf_path = ROOT / truth["shelf"]
    c2d_path = ROOT / truth["c2d"]
    shelf = shelf_path.read_bytes(); c2d = c2d_path.read_bytes()
    count = int(truth["records"]); width = int(truth["record_bytes"])
    images_offset = u16(c2d, 28)
    shelf_payload = u24(shelf, 10)
    shelf_total = u24(shelf, 13)
    generation = u16(c2d, 10)
    require(width == 32 and count == 6
            and shelf[:7] == b"L65S\x04\x20\x20"
            and shelf[7] == count and u16(shelf, 8) == 32
            and u16(shelf, 16) == count * width
            and shelf_payload == 32 + count * width
            and shelf_total == len(shelf)
            and c2d[:8] == b"C2D\0\x06\x30\x20\x0a"
            and generation != 0 and u16(c2d, 12) == count
            and images_offset == 48,
            "delivery record domain drift")
    shelf_rows = [shelf[32 + i * width:32 + (i + 1) * width]
                  for i in range(count)]
    c2d_rows = [c2d[images_offset + i * width:
                    images_offset + (i + 1) * width] for i in range(count)]
    require(all(len(row) == width for row in (*shelf_rows, *c2d_rows)),
            "truncated delivery record")
    entry = resolution = 0
    semantic_rows = []
    for i, (shelf_row, c2d_row) in enumerate(zip(shelf_rows, c2d_rows)):
        code = u24(shelf_row, 8); code_bytes = u16(shelf_row, 11)
        meta = u24(shelf_row, 13); meta_bytes = u16(shelf_row, 16)
        require(c2d_row[0:4] == bytes((0, 0, i, 0))
                and u16(c2d_row, 4) == generation
                and u16(c2d_row, 6) == entry
                and u16(c2d_row, 10) == resolution
                and u16(c2d_row, 21) == code_bytes
                and code_bytes != 0 and meta_bytes != 0
                and code + code_bytes <= shelf_total
                and meta + meta_bytes <= shelf_total
                and shelf_row[30:32] == b"\x01\x00",
                f"delivery semantic cross-binding drift: row {i}")
        semantic_rows.append({
            "image": i, "entry_first": entry,
            "resolution_first": resolution,
            "code_offset": code, "code_bytes": code_bytes,
            "metadata_offset": meta, "metadata_bytes": meta_bytes,
            "shelf_crc16": f"0x{crc16(shelf_row):04x}",
            "c2d_crc16": f"0x{crc16(c2d_row):04x}",
        })
        entry += u16(c2d_row, 8)
        resolution += u16(c2d_row, 12)
    require(entry == u16(c2d, 16) and resolution == u16(c2d, 20),
            "delivery cursor totals drift")
    zero_crc = crc16(bytes(width))
    require(all(crc16(row) != zero_crc
                for row in (*shelf_rows, *c2d_rows)),
            "zero poison collides with a delivery oracle")
    return {"shelf": bind(shelf_path), "c2d": bind(c2d_path),
            "images_offset": images_offset, "rows": semantic_rows,
            "final_entry_cursor": entry,
            "final_resolution_cursor": resolution,
            "pre_submit_poison_crc16": f"0x{zero_crc:04x}",
            "raw": {"shelf": shelf_rows, "c2d": c2d_rows}}


def timeout_pricing(contract: dict[str, Any]) -> dict[str, Any]:
    policy = contract["timeout_pricing"]
    evidence_path = ROOT / policy["hardware_receipt"]
    evidence = load(evidence_path)
    hz = float(evidence["M4_time"]["frames_per_second"])
    captures = evidence["M2_L10"]["captures"]
    exact = [row for row in captures if row["matches_expected"]]
    observed = min(int(row["elapsed_after_launch_ms"]) for row in exact)
    require(observed == int(policy["known_boot_cold_convergence_ms"])
            and 48.0 <= hz <= 52.0,
            "L10 timing authority drift")
    margin = int(policy["named_margin_ms"])
    selected = int(policy["selected_frames"])
    minimum = math.ceil((observed + margin) * hz / 1000.0)
    bound_ms = selected * 1000.0 / hz
    require(minimum == selected == 64 and bound_ms - observed >= margin,
            "boot-cold timeout no longer clears L10 plus named margin")
    return {"authority": bind(evidence_path), "measured_hz": hz,
            "known_convergence_ms": observed, "named_margin_ms": margin,
            "minimum_frames": minimum, "selected_frames": selected,
            "selected_bound_ms": round(bound_ms, 6),
            "actual_margin_ms": round(bound_ms - observed, 6)}


def generated_source(rows: dict[str, Any]) -> dict[str, Any]:
    static = Path(rows["shelf"]["path"]).parent.parent
    old = (V6.OUT, V6.PRODUCT_IDENTITY)
    try:
        V6.OUT = ROOT / static / "v6-semantics"
        V6.PRODUCT_IDENTITY = ROOT / static / "product/substitution-artifacts.json"
        with tempfile.TemporaryDirectory(prefix="lisp65-oracle-") as name:
            out = Path(name)
            mapping = V6.generated_product_sources(out)
            generated = next(iter(mapping.values())).parent
            decoder = generated / SOURCE.name
            owner = generated / "c2-stream-phase-02a.c"
            require(decoder.is_file() and owner.is_file(),
                    "real generator omitted decoder/table owner")
            return {"decoder": decoder.read_text(encoding="utf-8"),
                    "owner": owner.read_text(encoding="utf-8"),
                    "wrappers": sorted(path.name for path in mapping.values()
                                       if path.name.startswith("c2-stream"))}
    finally:
        V6.OUT, V6.PRODUCT_IDENTITY = old


def source_gate(rows: dict[str, Any]) -> dict[str, Any]:
    generated = generated_source(rows)
    source = SOURCE.read_text(encoding="utf-8")
    expected_shelf = [row["shelf_crc16"] for row in rows["rows"]]
    expected_c2d = [row["c2d_crc16"] for row in rows["rows"]]
    decoder = generated["decoder"]; owner = generated["owner"]
    require("#define C2_PHASE02A_TIMEOUT_FRAMES 64u" in decoder
            and all(f".short {value}" in owner for value in expected_shelf)
            and all(f".short {value}" in owner for value in expected_c2d)
            and owner.count(".short 0x") == 12
            and owner.count("c2_phase02a_shelf_crc16:") == 1
            and owner.count("c2_phase02a_c2d_crc16:") == 1
            and "c2_phase02a_shelf_crc16:" not in decoder
            and "c2_phase02a_c2d_crc16:" not in decoder,
            "generated delivery oracle differs from bound records")
    oracle_branch = source.split("#ifdef C2_PHASE02A_DELIVERY_ORACLE", 1)[1]
    oracle_branch = oracle_branch.split("#else", 1)[0]
    require(oracle_branch.count("c2_phase02a_record_read(") == 4
            and "rtov_crc_mem(target, 32u) == expected" in oracle_branch
            and "target[i] = 0u" in oracle_branch
            and "c2_product_physical_copy(" in oracle_branch
            and "c2_facade_vm_code_load(" in oracle_branch
            and "c2_stream_shelf_read(" not in oracle_branch
            and "c2_image_read(" not in oracle_branch
            and "c2_physical_source_byte" not in oracle_branch
            and "all static field relationships remain independently host-gated"
                in oracle_branch
            and "sample obtained through either guarded DMA channel is never an oracle"
                in oracle_branch,
            "phase-02a source-authoritative implementation drift")
    producer = GENERATOR.read_text(encoding="utf-8")
    require("shelf_path = PRODUCT_IDENTITY.parent" in producer
            and "c2d_path = OUT / \"initial.c2d-v6.bin\"" in producer
            and "record_crc16s" in producer,
            "producer oracle is not traceable to its delivery inputs")
    return {"status": "passed-real-generator-and-consumer-source",
            "generated_crc16s": {"shelf": expected_shelf, "c2d": expected_c2d},
            "three_calls": ["outer-D705", "D700-image", "inner-D705"],
            "probe_as_oracle_absent": True,
            "symbol_ownership": {
                "owner": "c2-stream-phase-02a.c", "definitions": 2,
                "shared_decoder_definitions": 0,
                "phase_wrappers": len(generated["wrappers"])},
            "delivery_trace": [rows["shelf"], rows["c2d"]]}


def real_consumer_source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = DRIVER.read_text(encoding="utf-8") \
        if source_override is None else source_override
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body
                 if isinstance(node, ast.FunctionDef)}
    target = functions.get("target_codegen")
    require(target is not None, "target codegen consumer absent")
    loops = [ast.unparse(node.iter) for node in ast.walk(target)
             if isinstance(node, ast.For)]
    calls = [(ast.unparse(node.func), ast.unparse(node.args[0]) if node.args else "")
             for node in ast.walk(target) if isinstance(node, ast.Call)]
    body = ast.unparse(target)
    require(
        "PRODUCT.C2_PHASE_SOURCES" in loops
        and ("subprocess.run", "link_command") in calls
        and "duplicate-definition mutation did not fail the real multi-TU link"
            in body,
        "target gate does not execute the real multi-TU consumer")
    return {"status": "passed-real-multi-TU-consumer-gate",
            "source_count_authority": "PRODUCT.C2_PHASE_SOURCES",
            "relocatable_link": True, "duplicate_link_mutation": True}


def real_consumer_source_mutations() -> list[str]:
    source = DRIVER.read_text(encoding="utf-8")
    loop = "            for original in PRODUCT.C2_PHASE_SOURCES:\n"
    link = "            subprocess.run(link_command, cwd=ROOT, check=True,\n"
    require(source.count(loop) == source.count(link) == 1,
            "real-consumer mutation anchor drift")
    cases = {
        "single-TU-stand-in": source.replace(
            loop, "            for original in (PRODUCT.C2_PHASE_SOURCES[3],):\n", 1),
        "omit-real-link": source.replace(
            link, "            subprocess.run([], cwd=ROOT, check=True,\n", 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            real_consumer_source_gate(candidate)
        except OracleError:
            rejected.append(name)
    require(rejected == list(cases), "real-consumer source mutation survived")
    return rejected


def target_codegen(rows: dict[str, Any]) -> dict[str, Any]:
    static = ROOT / Path(rows["shelf"]["path"]).parent.parent
    product_identity = static / "product/substitution-artifacts.json"
    old = (V6.OUT, V6.PRODUCT_IDENTITY)
    try:
        V6.OUT = static / "v6-semantics"; V6.PRODUCT_IDENTITY = product_identity
        with tempfile.TemporaryDirectory(prefix="lisp65-oracle-codegen-") as name:
            out = Path(name); mapping = V6.generated_product_sources(out)
            generated = next(iter(mapping.values())).parent
            require((generated / SOURCE.name).is_file(),
                    "real generator omitted target phase decoder")
            artifacts = load(product_identity)
            prior = ROOT / "build/c2.3/v2.0-map-tuple-fix-replacement-card/wplto"
            profile = (prior / "resolved-profile.txt").read_text().splitlines()
            features = tuple(next(row for row in profile
                                  if row.startswith("feature_defines="))
                             .split("=", 1)[1].split(","))
            definitions = (*PRODUCT.definitions(artifacts),
                           *PRODUCT.scoped_probe_definitions(features))
            compiler = str(ROOT / "tools/llvm-mos/bin/mos-mega65-clang")
            command = [compiler, "-Oz", "-Wall", "-fno-lto"]
            command.extend(f"-D{item}" for item in definitions)
            for header in ("runtime-overlay.prepare.h", "resident-island.prepare.h",
                           "stage-config.h", "error-text-table.h",
                           "c2-kernal-window.generated.h"):
                command.extend(("-include", str(prior / header)))
            for include in (ROOT / "src", ROOT / "scripts",
                            ROOT / "build/c2.2/substitution", prior,
                            ROOT / "build/bytecode", generated):
                command.extend(("-I", str(include)))
            objects: list[Path] = []
            for original in PRODUCT.C2_PHASE_SOURCES:
                source_path = mapping[original]
                target = out / (source_path.name + ".o")
                subprocess.run([*command, "-c", str(source_path), "-o", str(target)],
                               cwd=ROOT, check=True, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
                objects.append(target)
            combined = out / "phase-wrappers.combined.o"
            link_command = [str(ROOT / "tools/llvm-mos/bin/ld.lld"), "-r",
                            "-o", str(combined), *(str(path) for path in objects)]
            subprocess.run(link_command, cwd=ROOT, check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # The real link, not a schema stand-in, must reject a second owner.
            owner_path = generated / "c2-stream-phase-02a.c"
            owner_source = owner_path.read_text(encoding="utf-8")
            owner_preamble = owner_source.split("#define C2_STREAM_PHASE", 1)[0]
            duplicate_source = out / "c2-stream-phase-00-duplicate-owner.c"
            duplicate_source.write_text(
                owner_preamble
                + (generated / "c2-stream-phase-00.c").read_text(encoding="utf-8"),
                encoding="utf-8")
            duplicate_object = out / "duplicate-owner.o"
            subprocess.run([*command, "-c", str(duplicate_source),
                            "-o", str(duplicate_object)], cwd=ROOT, check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            negative_objects = [duplicate_object, *objects[1:]]
            negative = subprocess.run(
                [str(ROOT / "tools/llvm-mos/bin/ld.lld"), "-r", "-o",
                 str(out / "must-not-link.o"),
                 *(str(path) for path in negative_objects)],
                cwd=ROOT, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            require(negative.returncode != 0
                    and "duplicate symbol" in negative.stderr.lower(),
                    "duplicate-definition mutation did not fail the real multi-TU link")
            truth = ElfTruth.read(
                combined,
                llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
            size = truth.section(".lisp65_rt_c2d_02a").bytes
            require(size <= MAX_SLICE_BYTES,
                    f"phase-02a target code {size} exceeds "
                    f"runtime-overlay capacity {MAX_SLICE_BYTES}")
            return {"status": "passed-real-multi-TU-non-LTO-target-link",
                    "phase02a_bytes": size,
                    "headroom_bytes": MAX_SLICE_BYTES - size,
                    "maximum_bytes": MAX_SLICE_BYTES,
                    "translation_units": len(objects),
                    "unique_table_owner": "c2-stream-phase-02a.c",
                    "duplicate_definition_mutation": "rejected-by-real-link",
                    "real_consumer_source_gate": real_consumer_source_gate(),
                    "real_consumer_source_mutations_rejected":
                        real_consumer_source_mutations(),
                    "wplto_runs": 0, "product_links": 0}
    finally:
        V6.OUT, V6.PRODUCT_IDENTITY = old


def verifier_model(site: str, delivered: bytes, expected: int,
                   timeout: int = 64, oracle_source: str = "delivery",
                   match_before_timeout: bool = True) -> dict[str, Any]:
    require(len(delivered) == 32, "model record width drift")
    trace = [bytes(32), delivered[:16] + bytes(16), delivered]
    accepted = False
    for frame, target in enumerate(trace):
        actual = crc16(target)
        if match_before_timeout and actual == expected:
            accepted = True; break
        if frame >= timeout:
            break
        if not match_before_timeout and frame >= timeout:
            break
    return {"site": site, "oracle_source": oracle_source,
            "expected_crc16": expected, "accepted": accepted,
            "accepted_only_at_exact_delivery": accepted and target == delivered,
            "timeout_frames": timeout,
            "match_checked_before_timeout": match_before_timeout}


def equivalence(contract: dict[str, Any], rows: dict[str, Any],
                pricing: dict[str, Any]) -> dict[str, Any]:
    sites = contract["verifier_sites"]
    raw = rows["raw"]
    records = [raw["shelf"][0], raw["c2d"][0], raw["shelf"][0]]
    models = [verifier_model(site, record, crc16(record))
              for site, record in zip(sites, records)]
    require(all(row["accepted"] and row["accepted_only_at_exact_delivery"]
                for row in models)
            and pricing["selected_frames"] == 64,
            "three-site host equivalence failed")
    return {"status": "passed-three-site-delayed-convergence-equivalence",
            "sites": models,
            "old_failure_shape": {
                "probe_byte": "0x00", "delivered_first_byte": "0x73",
                "result": "old comparator can wait on the wrong value after delivery"
            }}


@functools.lru_cache(maxsize=1)
def value() -> dict[str, Any]:
    contract = load(CONTRACT)
    require(contract["accepted_by"] == AUTHORIZATION
            and contract["card"] == {"authorized": 1, "consumed": 0,
                                      "owner_veto_open_before_run": True},
            "contract/card boundary drift")
    rows = delivery_rows(contract)
    pricing = timeout_pricing(contract)
    source = source_gate(rows)
    codegen = target_codegen(rows)
    model = equivalence(contract, rows, pricing)
    rows.pop("raw")
    return {
        "format": FORMAT, "recorded_on": RECORDED_ON,
        "status": "PASS: source-authoritative phase-02a fix host green; card locked",
        "scope": contract["scope"],
        "delivery_truth": rows, "timeout_pricing": pricing,
        "source_gate": source, "target_codegen": codegen,
        "host_equivalence": model,
        "attempt_accounting": {"product_cards": 0, "wplto_runs": 0,
                               "product_links": 0, "media_builds": 0,
                               "device_contacts": 0},
        "card_boundary": contract["card"],
        "authority": {"owner_commission": git_authority(),
                      "integration_repair": git_integration_authority(),
                      "contract": bind(CONTRACT), "source": bind(SOURCE),
                      "generator": bind(GENERATOR), "driver": bind(DRIVER)},
        "claim_limit": (
            "Host/source/target-codegen qualification only. The one product "
            "card remains locked at the owner's explicit veto boundary."),
    }


def validate(candidate: dict[str, Any]) -> None:
    expected = value()
    if candidate == expected:
        return
    require(SOURCE_REBIND.is_file(),
            "source-authoritative oracle receipt drift")
    rebind = load(SOURCE_REBIND)
    require(
        rebind.get("status") ==
            "PASS: loud semantic-preserving oracle source rebind"
        and rebind["change"]["semantic_claims_changed"] is False
        and rebind["change"]["historical_receipt_rewritten"] is False,
        "source-authoritative oracle rebind authority drift",
    )
    normalized = deepcopy(candidate)
    pairs = (
        ("source", rebind["authority"]["historical_source"],
         rebind["authority"]["current_source"]),
        ("driver", rebind["authority"]["historical_driver"],
         rebind["authority"]["current_driver"]),
    )
    for field, historical, current in pairs:
        require(normalized["authority"][field] == historical,
                f"oracle {field} is neither current nor authorized historical")
        normalized["authority"][field] = current
    require(normalized == expected,
            "source-authoritative oracle receipt drift beyond dated rebind")


def mutations(base: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "drop-outer-D705": lambda x: x["host_equivalence"]["sites"].pop(0),
        "drop-D700-image": lambda x: x["host_equivalence"]["sites"].pop(1),
        "drop-inner-D705": lambda x: x["host_equivalence"]["sites"].pop(2),
        "outer-probe-as-oracle": lambda x: x["host_equivalence"]["sites"][0].update(oracle_source="guarded-probe"),
        "D700-probe-as-oracle": lambda x: x["host_equivalence"]["sites"][1].update(oracle_source="guarded-probe"),
        "inner-probe-as-oracle": lambda x: x["host_equivalence"]["sites"][2].update(oracle_source="guarded-probe"),
        "detach-shelf-truth": lambda x: x["source_gate"]["delivery_trace"][0].update(sha256="0" * 64),
        "detach-C2D-truth": lambda x: x["source_gate"]["delivery_trace"][1].update(sha256="0" * 64),
        "corrupt-oracle": lambda x: x["source_gate"]["generated_crc16s"]["shelf"].__setitem__(0, "0x0000"),
        "undersize-63": lambda x: x["timeout_pricing"].update(selected_frames=63),
        "undersize-32": lambda x: x["timeout_pricing"].update(selected_frames=32),
        "timeout-before-match": lambda x: x["host_equivalence"]["sites"][0].update(match_checked_before_timeout=False),
        "consume-card": lambda x: x["attempt_accounting"].update(product_cards=1),
        "duplicate-table-owner": lambda x: x["source_gate"][
            "symbol_ownership"].update(definitions=4),
        "single-TU-stand-in": lambda x: x["target_codegen"].update(
            translation_units=1),
    }
    rejected = []
    for name, mutate in cases.items():
        candidate = deepcopy(base); mutate(candidate)
        try:
            validate(candidate)
        except OracleError:
            rejected.append(name)
    require(rejected == list(cases), "oracle mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "oracle receipt already exists")
    result = value(); result["mutations_rejected"] = mutations(result)
    RECEIPT.write_bytes(canonical(result))
    print("2.0 source-authoritative oracle: RECORD PASS sites=3 timeout=64 "
          f"phase02a={result['target_codegen']['phase02a_bytes']} card=0")


def rebind() -> None:
    require(RECEIPT.is_file(), "oracle receipt absent for integration rebind")
    result = value(); result["mutations_rejected"] = mutations(result)
    RECEIPT.write_bytes(canonical(result))
    print("2.0 source-authoritative oracle: REBIND PASS multi-TU=18 "
          f"mutations={len(result['mutations_rejected'])} card=external")


def check() -> None:
    result = load(RECEIPT)
    rejected = result.pop("mutations_rejected", None)
    validate(result)
    require(rejected == mutations(result), "oracle mutation receipt drift")
    print("2.0 source-authoritative oracle: PASS sites=3 timeout=64 "
          f"phase02a={result['target_codegen']['phase02a_bytes']} card=0")


def selftest() -> None:
    result = value(); validate(result)
    require(len(mutations(result)) == 15,
            "oracle mutation count drift")
    print("2.0 source-authoritative oracle: SELFTEST PASS mutations=15 card=0")


def main() -> None:
    require(len(sys.argv) == 2
            and sys.argv[1] in {"record", "rebind", "check", "selftest"},
            "usage: c2_v20_source_authoritative_oracle.py "
            "record|rebind|check|selftest")
    {"record": record, "rebind": rebind, "check": check,
     "selftest": selftest}[sys.argv[1]]()


if __name__ == "__main__":
    try:
        main()
    except (OracleError, KeyError, ValueError, subprocess.CalledProcessError) as error:
        print(f"c2-v20-source-authoritative-oracle: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
