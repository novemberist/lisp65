#!/usr/bin/env python3
"""Run the one owner-authorized source-authoritative-oracle product card.

The producer, owner-scope inventory and artifact acceptance each run in a
fresh process.  Only the producer child may enter WPLTO or the product linker.
The acceptance child reads the frozen candidate and proves the standing VMA,
delivery, MAP-tuple and far-payload contracts plus the linked phase-02a oracle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_v20_map_tuple_fix_card as BASE  # noqa: E402
import c2_v20_map_tuple_fix_replacement_card as REPLACEMENT  # noqa: E402
import c2_v20_source_authoritative_oracle as ORACLE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
BUILD = ROOT / "build/c2.3/v2.0-source-authoritative-oracle-card"
PREFLIGHT = ROOT / "build/c2.3/v2.0-source-authoritative-oracle-card-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
RECEIPT = EVIDENCE / "c2.3-v2.0-source-authoritative-oracle-card-receipt.json"
FINAL_RED = EVIDENCE / "c2.3-v2.0-source-authoritative-oracle-card-final-red.json"
AUTHORIZATION_COMMIT = "8145e0ac"
RECORDED_ON = "2026-08-13"
LINK = 102
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
SERVICE_SECTION = ".lisp65_c2_mapped_far_service"
PHASE02A_SECTION = ".lisp65_rt_c2d_02a"


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


def git_authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{AUTHORIZATION_COMMIT}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION_COMMIT}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    text = " ".join(raw.decode().split()).lower()
    require(
        "card go" in text and "go: exactly one product card" in text
        and "far-payload extent gate" in text
        and "green proceeds: media regeneration" in text,
        "owner card-Go text drift")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def host_authority() -> dict[str, Any]:
    value = load(ORACLE.RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    ORACLE.validate(value)
    require(
        rejected == ORACLE.mutations(value)
        and value["card_boundary"] == {
            "authorized": 1, "consumed": 0,
            "owner_veto_open_before_run": True}
        and value["target_codegen"]["phase02a_bytes"] == 1671
        and value["timeout_pricing"]["selected_frames"] == 64,
        "host oracle/card boundary drift")
    return {"receipt": bind(ORACLE.RECEIPT), "mutations": len(rejected),
            "phase02a_bytes": 1671, "timeout_frames": 64}


def artifact_paths() -> dict[str, Path]:
    base = BUILD / "wplto"
    return {
        "elf": base / "lisp65-c2-substitution-linked.prg.elf",
        "prg": base / "lisp65-c2-substitution-linked.prg",
        "map": base / "lisp65-c2-substitution-linked.prg.map",
        "lto": base / "lisp65-c2-substitution-linked.prg.lto.o",
        "linker": base / "c2-substitution.ld",
        "resolved_profile": base / "resolved-profile.txt",
        "publish_last": base / "kernal-window-publish-last.json",
        "generated_phase02a": (
            base / "generated-product-sources/c2-stream-phase-02a.c"),
        "generated_decoder": (
            base / "generated-product-sources/c2-stream-decoder.c"),
    }


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    return {name: bind(path) for name, path in artifact_paths().items()}


def preflight_value() -> dict[str, Any]:
    return {
        "format": "lisp65-c2.3-v20-source-oracle-card-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: exactly one source-oracle product card armed",
        "attempt_accounting": {"cards_consumed": 0, "wplto_runs": 0,
                               "product_links": 0, "device_contacts": 0},
        "configuration": {"link": LINK, "full_map_ownership": True,
            "low_resident_LMA_reset": True,
            "MAP_tuple": {"A": "0x40", "X": "0x82"},
            "oracle_timeout_frames": 64, "new_staging_roles": 0},
        "acceptance": {"VMA_invariants": 103, "fixed_boundaries": 27,
            "candidate_derived_validation": True,
            "publish_last_CRC_operands": 2,
            "far_payload_extent_identity": True,
            "linked_delivery_oracle": True, "cards_authorized": 1},
        "authority": {"owner_go": git_authority(),
            "oracle_host_gate": host_authority(),
            "VMA_golden": bind(BASE.INV.GOLDEN),
            "map_tuple_fix": bind(BASE.FIX.RECEIPT), "driver": bind(DRIVER)},
    }


def validate_preflight(value: dict[str, Any]) -> None:
    require(value == preflight_value(), "source-oracle card preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "authorize-two": lambda x: x["acceptance"].update(cards_authorized=2),
        "drop-full-map": lambda x: x["configuration"].update(full_map_ownership=False),
        "drop-LMA-reset": lambda x: x["configuration"].update(low_resident_LMA_reset=False),
        "restore-old-MAP-A": lambda x: x["configuration"]["MAP_tuple"].update(A="0x80"),
        "undersize-timeout": lambda x: x["configuration"].update(oracle_timeout_frames=63),
        "drop-far-extent": lambda x: x["acceptance"].update(far_payload_extent_identity=False),
        "detach-oracle": lambda x: x["authority"]["oracle_host_gate"]["receipt"].update(sha256="0" * 64),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = json.loads(json.dumps(value)); mutate(candidate)
        try:
            validate_preflight(candidate)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases), "card preflight mutation survived")
    return rejected


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "source-oracle card/preflight is one-shot")
    value = preflight_value(); validate_preflight(value)
    value["mutations_rejected"] = preflight_mutations(value)
    PREFLIGHT.mkdir(parents=True)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("2.0 source-oracle card: PREFLIGHT PASS card=0 oracle=13")


def produce_child() -> int:
    require(BUILD.is_dir() and not PRODUCER_RESULT.exists(),
            "producer child lifecycle drift")
    BASE.configure_fix_source()
    BASE.PRODUCER.LINK = LINK
    BASE.PRODUCER.BUILD = BUILD
    BASE.PRODUCER.FINAL_RED = BUILD / "producer-internal-first-red.json"
    BASE.PRODUCT.configure_full_map_ownership()
    BASE.PRODUCT.configure_low_resident_lma_reset()
    artifacts = BASE.PRODUCER.produce_candidate()
    expected = artifact_paths()
    require(all(artifacts[key] == expected[key]
                for key in ("elf", "prg", "map", "lto", "linker",
                            "resolved_profile")),
            "producer artifact path drift")
    PRODUCER_RESULT.write_bytes(canonical({"status": "PASS", "pid": os.getpid(),
                                           "artifacts": frozen_artifacts()}))
    return 0


def scope_child() -> int:
    require(BUILD.is_dir() and not SCOPE_RESULT.exists(),
            "scope child lifecycle drift")
    gate = REPLACEMENT.single_implementation_gate()
    SCOPE_RESULT.write_bytes(canonical({"status": "PASS", "pid": os.getpid(),
                                        "gate": gate}))
    return 0


def crc16(raw: bytes) -> int:
    value = 0xFFFF
    for byte in raw:
        value ^= byte << 8
        for _ in range(8):
            value = ((value << 1) ^ 0x1021) & 0xFFFF \
                if value & 0x8000 else (value << 1) & 0xFFFF
    return value


def linked_oracle_gate(elf: Path) -> dict[str, Any]:
    shelf_path = BUILD / "static-plane/narrow-static/product/product-shelf-v4-direct.bin"
    c2d_path = BUILD / "static-plane/narrow-static/v6-semantics/initial.c2d-v6.bin"
    shelf = shelf_path.read_bytes(); c2d = c2d_path.read_bytes()
    records = shelf[7]; images = struct.unpack_from("<H", c2d, 28)[0]
    require(records == 6 and struct.unpack_from("<H", c2d, 12)[0] == 6,
            "linked-oracle delivery domain drift")
    shelf_values = [crc16(shelf[32 + i * 32:64 + i * 32]) for i in range(6)]
    c2d_values = [crc16(c2d[images + i * 32:images + (i + 1) * 32])
                  for i in range(6)]
    needle = b"".join(struct.pack("<H", value)
                      for value in shelf_values + c2d_values)
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    section = truth.section(PHASE02A_SECTION)
    linked = truth.section_bytes(PHASE02A_SECTION)
    generated = artifact_paths()["generated_phase02a"]
    decoder = artifact_paths()["generated_decoder"]
    source = generated.read_text(encoding="utf-8")
    decoder_source = decoder.read_text(encoding="utf-8")
    require(
        section.bytes == len(linked) <= 1792 and linked.find(needle) >= 0
        and decoder_source.count("#define C2_PHASE02A_DELIVERY_ORACLE 1") == 1
        and decoder_source.count("#define C2_PHASE02A_TIMEOUT_FRAMES 64u") == 1
        and source.count("c2_phase02a_shelf_crc16:") == 1
        and source.count("c2_phase02a_c2d_crc16:") == 1
        and all(f".short 0x{value:04x}" in source
                for value in shelf_values + c2d_values),
        "linked phase-02a delivery oracle drift")
    return {"status": "passed-linked-delivery-bound-CRC-oracle",
            "section": PHASE02A_SECTION, "VMA": f"0x{section.address:04x}",
            "bytes": section.bytes, "capacity": 1792,
            "reserve": 1792 - section.bytes, "records_per_image": 6,
            "shelf_crc16": [f"0x{x:04x}" for x in shelf_values],
            "c2d_crc16": [f"0x{x:04x}" for x in c2d_values],
            "oracle_offset": linked.find(needle), "timeout_frames": 64,
            "delivery_inputs": [bind(shelf_path), bind(c2d_path)],
            "generated_owner": bind(generated),
            "generated_decoder": bind(decoder)}


def far_payload_gate(elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    section = truth.section(SERVICE_SECTION)
    raw = truth.section_bytes(SERVICE_SECTION)
    start = truth.symbol("__lisp65_c2_mapped_far_service_load_start").value
    end = truth.symbol("__lisp65_c2_mapped_far_service_load_end").value
    require(section.bytes == len(raw) == end - start == 874,
            "linked far-payload extent/identity drift")
    return {"status": "passed-linked-far-payload-extent-identity",
            "section": SERVICE_SECTION, "VMA": f"0x{section.address:04x}",
            "LMA_start": f"0x{start:08x}", "LMA_end_exclusive": f"0x{end:08x}",
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def acceptance_child() -> int:
    require(BUILD.is_dir() and not ACCEPTANCE_RESULT.exists(),
            "acceptance child lifecycle drift")
    paths = artifact_paths()
    BASE.PRODUCT.configure_e000_reopening()
    BASE.PRODUCT.configure_full_map_ownership()
    BASE.PRODUCT.configure_low_resident_lma_reset()
    BASE.CRC.BUILD = BUILD
    comparison = BASE.INV.compare_elf(paths["elf"])
    linker = BASE.PRODUCT.low_resident_lma_reset_gate(
        paths["linker"].read_text(encoding="utf-8"))
    delivery = BASE.CRC.delivered_bytes_gate(paths["elf"], paths["prg"])
    BASE.CRC.validate_delivery(delivery, paths["elf"], paths["prg"])
    tuple_gate = BASE.linked_tuple_gate(paths["elf"])
    value = {"status": "PASS", "pid": os.getpid(),
        "VMA_golden": comparison, "low_resident_LMA_reset": linker,
        "delivered_bytes": delivery,
        "delivery_mutations_rejected": BASE.CRC.delivery_mutations(
            delivery, paths["elf"], paths["prg"]),
        "linked_MAP_tuple": tuple_gate,
        "linked_MAP_mutations_rejected": BASE.linked_mutations(tuple_gate, paths["elf"]),
        "far_payload": far_payload_gate(paths["elf"]),
        "source_authoritative_oracle": linked_oracle_gate(paths["elf"])}
    require(comparison["allocatable_sections"] == 103
            and comparison["fixed_boundary_symbols"] == 27,
            "VMA invariant cardinality drift")
    ACCEPTANCE_RESULT.write_bytes(canonical(value))
    return 0


def run_child(action: str) -> None:
    result = subprocess.run([sys.executable, str(DRIVER), action], cwd=ROOT,
                            text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"fresh card child {action} red:\n{result.stdout}")


def card() -> None:
    value = load(PREFLIGHT_RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate_preflight(value)
    require(rejected == preflight_mutations(value),
            "preflight mutation receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "source-oracle product card is one-shot")
    INVOCATION.write_bytes(canonical({"status": "INVOKED", "link": LINK,
        "owner_go": git_authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "driver": bind(DRIVER)}))
    BUILD.mkdir(parents=True)
    run_child("_produce")
    before = frozen_artifacts()
    run_child("_scope")
    run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "read-only acceptance changed candidate artifacts")
    producer = load(PRODUCER_RESULT); scope = load(SCOPE_RESULT)
    acceptance = load(ACCEPTANCE_RESULT)
    require(len({os.getpid(), producer["pid"], scope["pid"], acceptance["pid"]}) == 4,
            "producer/scope/acceptance process isolation drift")
    receipt = {
        "format": "lisp65-c2.3-v20-source-oracle-card-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: source-authoritative oracle product card green",
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "wplto_runs": 1, "product_links": 1, "media_builds": 0,
            "device_contacts": 0},
        "authority": {"owner_go": git_authority(),
            "preflight": bind(PREFLIGHT_RECEIPT),
            "oracle_host_gate": bind(ORACLE.RECEIPT), "driver": bind(DRIVER)},
        "process_isolation": {"parent": os.getpid(), "producer": producer["pid"],
            "owner_scope": scope["pid"], "acceptance": acceptance["pid"],
            "all_distinct": True},
        "artifacts_before": before, "artifacts_after": after,
        "acceptance": {key: item for key, item in acceptance.items()
                       if key not in ("status", "pid")},
        "owner_scope": scope["gate"],
        "next": "regenerate current-world media, then D1",
        "claim_limit": "Card and linked artifacts only; media and device have not run.",
    }
    RECEIPT.write_bytes(canonical(receipt))
    print("2.0 source-oracle card: PASS card=1/1 WPLTO=1 link=1 VMA=103")


def record_final_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {}
    for name, path in artifact_paths().items():
        if path.is_file() and not path.is_symlink():
            artifacts[name] = bind(path)
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v20-source-oracle-card-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: source-oracle card returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "wplto_runs": 1 if PRODUCER_RESULT.exists() or artifacts else 0,
            "product_link_attempts": 1 if PRODUCER_RESULT.exists() or artifacts else 0,
            "media_builds": 0, "device_contacts": 0},
        "artifacts": artifacts, "retry_authorized": False,
        "owner_disposition_required": True,
        "authority": {"owner_go": git_authority(),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
    }))


def selftest() -> None:
    value = preflight_value(); validate_preflight(value)
    require(len(preflight_mutations(value)) == 7,
            "source-oracle card selftest mutation drift")
    print("2.0 source-oracle card: SELFTEST PASS preflight=7 card=unused")


def check() -> None:
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value["retry_authorized"] is False
                and value["owner_disposition_required"] is True,
                "source-oracle Final Red drift")
        print("2.0 source-oracle card: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        print("2.0 source-oracle card: CHECK ARMED card=unused")
        return
    value = load(RECEIPT)
    require(value["status"] == "PASS: source-authoritative oracle product card green"
            and value["attempt_accounting"]["cards_consumed"] == 1
            and value["artifacts_before"] == frozen_artifacts()
            and value["artifacts_after"] == value["artifacts_before"]
            and value["process_isolation"]["all_distinct"] is True
            and value["acceptance"]["VMA_golden"]["allocatable_sections"] == 103
            and value["acceptance"]["source_authoritative_oracle"]["timeout_frames"] == 64
            and value["acceptance"]["far_payload"]["bytes"] == 874,
            "green source-oracle card receipt drift")
    print("2.0 source-oracle card: CHECK PASS card=1/1 WPLTO=1 link=1")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("selftest", "preflight", "card", "check",
                                           "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    {"selftest": selftest, "preflight": preflight, "card": card,
     "check": check, "_produce": produce_child, "_scope": scope_child,
     "_accept": acceptance_child}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_final_red(error)
            except Exception as receipt_error:
                print(f"source-oracle Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"2.0 source-oracle card: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
