#!/usr/bin/env python3
"""Prove the resident-entry hot-refill trust boundary before one seed link."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_hot_refill_contract as OLD  # noqa: E402
import c2_stream_decoder as V1  # noqa: E402
import c2_stream_decoder_v2 as STAGE  # noqa: E402


BUILD = ROOT / "build/c2.2/hot-refill-resident-contract"
SHELF = ROOT / "build/c2.2/substitution/product-shelf-v4-direct.bin"
C2D = ROOT / (
    "build/c2.2/hardware-presmoke-link29-direct-entry-encoding/"
    "first-red-latency/c2d-after-two-identical-forms.bin")
STAGE_SHELF = ROOT / "build/c2.1/streaming-decoder-v2/shelf.bin"
STAGE_C2D = ROOT / "build/c2.1/streaming-decoder-v2/c2d-v2.bin"
HELPER = ROOT / "src/c2_hot_literal.c"
RUNTIME = ROOT / "src/c2_product_runtime.c"
PHASE = ROOT / "scripts/c2-stream-v2-decoder.c"
HEADER = ROOT / "scripts/c2-stream-decoder.h"
HOT_HOST = ROOT / "scripts/c2-hot-entry-host-main.c"
STAGE_HOST = ROOT / "scripts/c2-stream-v2-host-main.c"
CONTRACT = ROOT / "config/c2-hot-refill-single-source-contract.json"
DOCUMENT = ROOT / "docs/planning/c2.2-hot-refill-single-source-addendum.md"
LINK29_SOURCE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/artifacts/"
    "c2-link27-protected-pin-20260720/root/src/c2_product_runtime.c")
AMENDED_CONTRACT = ROOT / "config/c2-hot-refill-link29-seams-amendment.json"
AMENDED_DOCUMENT = ROOT / (
    "docs/planning/c2.2-hot-refill-link29-seams-amendment.md")
OLD_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-hot-refill-single-source-contract-probe-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-hot-refill-link29-seams-contract-probe-receipt.json")
FAILED_CAPACITY_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-hot-refill-resident-entry-capacity-first-red-receipt.json")


class ContractError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def run(argv: list[str], *, expected: int = 0,
        timeout: int = 180) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                            check=False, timeout=timeout)
    if result.returncode != expected:
        raise ContractError(
            f"{Path(argv[0]).name} returned {result.returncode}, expected "
            f"{expected}: {(result.stderr or result.stdout).strip()}")
    return result


def u16(data: bytes | bytearray, at: int) -> int:
    return struct.unpack_from("<H", data, at)[0]


def u24(data: bytes | bytearray, at: int) -> int:
    return data[at] | data[at + 1] << 8 | data[at + 2] << 16


def descriptor(shelf: bytes | bytearray, wanted: int) -> tuple[int, int, int]:
    ordinal = 0
    for image in range(6):
        record = 32 + image * 32
        metadata = u24(shelf, record + 13)
        count = u16(shelf, metadata + 12)
        literals = u16(shelf, metadata + 16)
        for local in range(count):
            at = metadata + literals + local * 8
            if shelf[at] == wanted:
                return image, at, ordinal + local
        ordinal += count
    raise ContractError(f"descriptor kind {wanted} absent")


def function_source(text: str, name: str) -> str:
    start = text.index(name + "(")
    start = text.rfind("\n", 0, start) + 1
    brace = text.index("{", start)
    depth = 0
    for at in range(brace, len(text)):
        if text[at] == "{": depth += 1
        elif text[at] == "}":
            depth -= 1
            if depth == 0:
                return text[start:at + 1]
    raise ContractError(f"unterminated function {name}")


def normalized_source(text: str, *, externalize: bool = False) -> str:
    if externalize:
        text = text.replace("static C2_KERNAL_RESIDENT", "C2_KERNAL_RESIDENT", 1)
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s*([(),{};\[\]])\s*", r"\1", text)


def source_gate() -> dict[str, str]:
    helper = HELPER.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    phase = PHASE.read_text(encoding="utf-8")
    header = HEADER.read_text(encoding="utf-8")
    link29 = LINK29_SOURCE.read_text(encoding="utf-8")
    direct = runtime.split("uint8_t c2_product_entry_read(", 1)[1].split(
        "void c2_product_gc_mark_roots", 1)[0]
    boot = runtime.split("uint8_t c2_product_boot(void)", 1)[1].split(
        "uint8_t c2_product_prepare_boot", 1)[0]
    record = runtime.split("C2_KERNAL_RESIDENT uint8_t c2_entry_records(", 1)[1].split(
        "uint16_t c2_product_dir_count", 1)[0]
    materializer = helper.split(
        "C2_HOT_MATERIALIZER uint8_t c2_stream_product_materialize_entry(", 1
    )[1].split("#endif", 1)[0]
    rows = {
        "one_materializer_definition": (
            helper.count("c2_stream_product_materialize_entry(") == 1),
        "one_record_definition": (
            runtime.count("C2_KERNAL_RESIDENT uint8_t c2_entry_records(") == 1),
        "link29_child_source_retained": (
            normalized_source(function_source(
                runtime, "c2_stream_product_child_value"))
            == normalized_source(function_source(
                link29, "c2_stream_product_child_value"))),
        "link29_record_algorithm_retained": (
            normalized_source(function_source(runtime, "c2_entry_records"))
            == normalized_source(function_source(
                link29, "c2_entry_records"), externalize=True)),
        "link29_entry_length_source_retained": (
            normalized_source(function_source(runtime, "c2_product_entry_length"))
            == normalized_source(function_source(
                link29, "c2_product_entry_length"))),
        "child_resolver_not_duplicated_in_island": (
            "c2_stream_product_child_value(" not in helper.split(
                "c2_stream_product_materialize_entry(", 1)[0]),
        "materializer_uses_record_seam": materializer.count("c2_entry_records(") == 1,
        "materializer_uses_lean_child": (
            materializer.count("c2_stream_product_child_value(") == 1),
        "no_hot_content_validator": (
            "switch (" not in helper
            and "C2_STREAM_ERR_DESCRIPTOR" not in helper
            and "MK_BCODE" not in helper),
        "vm_refill_calls_one_materializer": (
            direct.count("c2_stream_product_materialize_entry(") == 1),
        "vm_fallback_transport_remains_probe_guarded": (
            direct.count("c2_overlay_call(LISP65_C2_PHASE_13_SLOT") == 1
            and "#ifndef LISP65_C2_DIRECT_HOT_REFILL" in direct),
        "phase13_calls_same_materializer": (
            "return c2_stream_product_materialize_entry(\n"
            "        work->stream, work->directory_ordinal" in phase),
        "old_span_materializer_absent": (
            "c2_stream_product_materialize_literals" not in helper + runtime + phase + header),
        "record_requires_published_context": (
            "!c2_ready" in record
            and "c2_u16(directory + 8) != c2_runtime.generation" in record),
        "materializer_requires_finished_phase13": (
            "!c->finished" in materializer and "c->phase != 13u" in materializer),
        "boot_publishes_ready_after_decode": (
            boot.index("if (!c2_decode_from(&c2_runtime, 0u)) return 0;")
            < boot.index("c2_ready = 1;")),
        "contract_header_has_one_public_materializer": (
            header.count("c2_stream_product_materialize_entry(") == 1),
    }
    require(all(rows.values()), f"source single-truth gate red: {rows}")
    return {key: "passed" for key in rows}


def compile_hot() -> Path:
    target = BUILD / "c2-hot-entry-host"
    result = run([
        "cc", "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
        "-DC2_STREAM_PRODUCT_V3=1", "-I", str(ROOT / "src"),
        "-I", str(ROOT / "scripts"), str(HELPER), str(HOT_HOST),
        "-o", str(target),
    ])
    require(not result.stdout and not result.stderr, "hot host diagnostics")
    return target


def hot_semantics(target: Path) -> tuple[Path, dict[str, Any]]:
    case_raw, facts = OLD.collect_cases(SHELF.read_bytes(), C2D.read_bytes())
    cases = BUILD / "hot-entry-cases.bin"; cases.write_bytes(case_raw)
    result = run([str(target), str(SHELF), str(C2D), str(cases)])
    expected = "c2-hot-entry: PASS entries=588 literals=1931 negatives=5 nested=1\n"
    require(result.stdout == expected and not result.stderr,
            f"hot semantic closure drift: {result.stdout!r} {result.stderr!r}")
    facts = {key: value for key, value in facts.items()
             if key != "mutation_locations"}
    return cases, {
        **facts,
        "published_entries": "588/588 exact",
        "literal_values": "1931/1931 exact",
        "nested_caller_rematerialization": "passed",
        "local_range_negatives": 3,
        "post_publication_transport_failures": {
            "descriptor_read": "failed-closed",
            "resolution_read": "failed-closed",
        },
    }


def compile_stage() -> Path:
    target = BUILD / "c2-stage-boundary-host"
    result = run([
        "cc", "-std=c99", "-Os", "-Wall", "-Wextra", "-Werror",
        "-I", str(ROOT / "scripts"), "-I", str(ROOT / "src"),
        *map(str, STAGE.SOURCES), str(STAGE_HOST), "-o", str(target),
    ])
    require(not result.stdout and not result.stderr, "stage host diagnostics")
    return target


def stage_execute(target: Path, shelf: bytes, c2d: bytes,
                  mode: str | None = None) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory(prefix="lisp65-c2-hot-stage-") as raw:
        directory = Path(raw)
        shelf_path = directory / "shelf.bin"; shelf_path.write_bytes(shelf)
        c2d_path = directory / "c2d.bin"; c2d_path.write_bytes(c2d)
        argv = [str(target), str(shelf_path), str(c2d_path)]
        if mode: argv.append(mode)
        return subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                              check=False, timeout=120)


def stage_reachability(target: Path) -> dict[str, Any]:
    shelf = STAGE_SHELF.read_bytes(); c2d = STAGE_C2D.read_bytes()
    positive = stage_execute(target, shelf, c2d)
    require(positive.returncode == 0 and positive.stderr == ""
            and positive.stdout.startswith("c2-stream-v2: PASS "),
            "stage positive closure failed")
    rows: list[dict[str, Any]] = []

    image, at, _ordinal = descriptor(shelf, 2)
    mutated_shelf = bytearray(shelf); mutated_c2d = bytearray(c2d)
    mutated_shelf[at] = 9
    V1.repair_image(mutated_shelf, mutated_c2d, image)
    result = stage_execute(target, mutated_shelf, mutated_c2d)
    require(result.returncode == 6
            and result.stderr.startswith(
                "c2-stream-v2: FAIL phase=7 status=6 finished=0"),
            "unknown descriptor reached publication")
    rows.append({"case": "unknown-descriptor-kind", "caught_at": "stage-7",
                 "status": 6, "published": False})

    _image, _at, entry_ordinal = descriptor(shelf, 4)
    result = stage_execute(target, shelf, c2d,
                           f"post-resolution:{entry_ordinal}:0")
    require(result.returncode == 7
            and result.stderr.startswith(
                "c2-stream-v2: FAIL phase=12 status=7 finished=0"),
            "non-BCODE direct resolution reached publication")
    rows.append({"case": "entry-resolution-not-bcode", "caught_at": "stage-12",
                 "status": 7, "published": False})

    _image, _at, root_ordinal = descriptor(shelf, 3)
    root_count = u16(c2d, 24)
    result = stage_execute(target, shelf, c2d,
                           f"resolution:{root_ordinal}:{root_count}")
    require(result.returncode == 7
            and "finished=0" in result.stderr,
            "out-of-range root ordinal reached publication")
    match = re.search(r"phase=(\d+) status=7", result.stderr)
    require(match is not None, "root ordinal rejection diagnostics")
    rows.append({"case": "root-ordinal-out-of-range",
                 "caught_at": f"stage-{match.group(1)}", "status": 7,
                 "published": False})

    result = stage_execute(target, shelf, c2d, "root:0:3")
    require(result.returncode == 7
            and result.stderr.startswith(
                "c2-stream-v2: FAIL phase=12 status=7 finished=0"),
            "non-pointer root reached publication")
    rows.append({"case": "root-value-not-pointer", "caught_at": "stage-12",
                 "status": 7, "published": False})
    return {
        "positive_full_stage": "passed",
        "content_mutations": rows,
        "content_mutations_reaching_hot_path": 0,
        "transport_fault_classification": (
            "Descriptor/resolution read faults after publication are transport "
            "failures, not content mutations; the hot fixture rejects both."),
    }


def build() -> dict[str, Any]:
    require(AMENDED_CONTRACT.is_file() and AMENDED_DOCUMENT.is_file(),
            "amended contract inputs absent")
    contract = json.loads(AMENDED_CONTRACT.read_text(encoding="utf-8"))
    require(contract["status"]
            == "owner-authorized-amended-resident-island-seed-probe",
            "owner authorization status absent")
    if BUILD.exists(): shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True)
    source = source_gate()
    hot = compile_hot(); cases, semantics = hot_semantics(hot)
    stage = compile_stage(); reachability = stage_reachability(stage)
    return {
        "format": "lisp65-c2-hot-refill-link29-seams-contract-probe-v1",
        "recorded_on": "2026-07-20",
        "status": "passed-non-product-contract-stage-and-semantic-probe",
        "scope": {"product_links": 0, "resident_island_seed_links": 0,
                  "hardware_execution": "none", "promotion": "not-authorized",
                  "performance_claim": "none"},
        "inputs": {
            "contract": bind(AMENDED_CONTRACT), "addendum": bind(AMENDED_DOCUMENT),
            "link29_shelf": bind(SHELF), "link29_c2d_capture": bind(C2D),
            "stage_shelf": bind(STAGE_SHELF), "stage_c2d": bind(STAGE_C2D),
            "helper_source": bind(HELPER), "runtime_source": bind(RUNTIME),
            "protected_link29_source_predecessor": bind(LINK29_SOURCE),
            "phase_source": bind(PHASE), "contract_header": bind(HEADER),
            "hot_fixture": bind(HOT_HOST), "stage_fixture": bind(STAGE_HOST),
            "historical_overvalidation_probe": bind(OLD_RECEIPT),
            "historical_first_attempt_contract": bind(CONTRACT),
            "historical_first_attempt_addendum": bind(DOCUMENT),
            "historical_first_red_capacity": bind(FAILED_CAPACITY_RECEIPT),
        },
        "generated": {"hot_host": bind(hot), "stage_host": bind(stage),
                      "cases": bind(cases)},
        "single_truth_source_gate": source,
        "stage_to_hot_reachability": reachability,
        "hot_semantic_closure": semantics,
        "why_hot_path_does_not_revalidate": (
            "The hot materializer is reachable only through c2_entry_records after the "
            "stage/decode path has validated and identity-bound the immutable descriptor "
            "stream and published the generation-bound resolution/root planes. The four "
            "content mutations are rejected with finished=0 and therefore cannot reach "
            "the hot consumer. Repeating those checks in refill would create a second "
            "validator rather than strengthen the publication boundary."),
        "single_materializer_claim": (
            "The Link-29 child resolver, record algorithm and entry-length seam are "
            "retained; Phase 13 and c2_product_entry_read share "
            "c2_stream_product_materialize_entry through c2_entry_records; no second "
            "product materializer is present in source."),
        "claim_limit": (
            "Host-only source, stage-reachability and semantic proof. It makes no "
            "capacity, placement, product-link, hardware, latency, promotion or "
            "performance claim."),
        "next_gate": (
            "Exactly one amended product-shaped Resident-Island seed capacity/placement "
            "probe may run. Its hard pass condition includes exact $E000 delta 0 bytes. "
            "Any red currency or structure gate stops before a product link; Link 29 "
            "remains untouched."),
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    try:
        data = canonical(build())
        if args.action == "write":
            RECEIPT.parent.mkdir(parents=True, exist_ok=True)
            if RECEIPT.exists(): os.chmod(RECEIPT, 0o644)
            RECEIPT.write_bytes(data); os.chmod(RECEIPT, 0o444); verb = "WROTE"
        elif args.action == "check":
            require(RECEIPT.read_bytes() == data, "amended contract receipt drift")
            verb = "PASS"
        else:
            verb = "SELFTEST PASS"
        print("c2-hot-refill-link29-seams-contract: " + verb
              + " entries=588 literals=1931 stage-mutations=4 transport-faults=2")
        return 0
    except (OSError, ValueError, KeyError, ContractError) as error:
        print(f"c2-hot-refill-link29-seams-contract: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
