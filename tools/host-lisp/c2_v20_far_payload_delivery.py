#!/usr/bin/env python3
"""Deliver and close the v2.0 mapped far-service payload.

The linked product, its completion and the green geometry card are immutable
inputs.  This media-only successor extends the existing Bank-2 ``code.bin``
role through the linked far-service LMA, rebuilds the ordinary descriptor and
cold stager, and proves the bytes again from the packed D81.  It never enters
the product producer, compiler, linker, WPLTO or artifact completion.
"""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_lite_media_product as MEDIA  # noqa: E402
import c2_link95_world_bound_media as PAIR  # noqa: E402
import c2_v20_crc_carveout_media as PRODUCT  # noqa: E402
import c2_v20_crc_carveout_media_liveness as PREVIOUS  # noqa: E402
from elf_truth import ElfTruth, ElfTruthError  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v2.0-far-payload-delivery"
INPUTS = BUILD / "product-inputs"
SHARED = BUILD / "shared-system"
PRODUCT_MANIFEST = INPUTS / "canonical-product-manifest.json"
BANK2 = INPUTS / "bank2-static-code.bin"
MEDIA_MANIFEST = SHARED / "candidate-manifest.json"
DESCRIPTOR = SHARED / "boot.id"
STAGER = SHARED / "autoboot.c65"
STAGER_ELF = SHARED / "autoboot.c65.elf"
STAGER_MAP = SHARED / "autoboot.c65.map"
PRODUCT_D81 = SHARED / "lisp65-product.d81"
WORK_D81 = SHARED / "lisp65-work.d81"
MOUNT = SHARED / "lisp65-product.mount.json"
LIBRARY_D81 = PRODUCT.LIBRARY_D81
BASE_MANIFEST = PRODUCT.MANIFEST
ELF = PRODUCT.CARD.BUILD / "final/lisp65-c2-substitution-linked.prg.elf"
CONTRACT = ROOT / "config/c2-stack-overlay-ownership-contract.json"
MEDIA_CONTRACT = ROOT / "config/c2-lite-media-product.json"
ATTRIBUTION = EVIDENCE / (
    "c2.3-v2.0-mapped-far-return-attribution-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.3-v2.0-far-payload-delivery-closure-receipt.json")
SESSION = ROOT / "config/c2-v150-v20-far-payload-device-session.json"
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
FORMAT = "lisp65-c2.3-v20-far-payload-delivery-closure-v1"
STATUS = "V20-MAPPED-FAR-PAYLOAD-DELIVERED; D1-REPEAT-AUTHORIZED"
RECORDED_ON = "2026-08-12"
APPROVAL_COMMIT = "6f3831d5"
SERVICE_SECTION = ".lisp65_c2_mapped_far_service"
ROLE = "c2-bank2-static-code-plane"
VISIBLE_NAME = b"CODE.BIN"
OPT_IN = PREVIOUS.OPT_IN


class DeliveryError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise DeliveryError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha_bytes(raw)}


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    require(
        b"Far-payload delivery approved" in raw
        and b"media-side, no relink, no new card" in raw
        and b"extent/identity gate joins the media closure permanently" in raw,
        "owner delivery approval text drift")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": sha_bytes(raw)}


def truth() -> ElfTruth:
    return ElfTruth.read(
        ELF, llvm_readobj=READOBJ, include_section_data=True)


def role_destination() -> int:
    contract = load(MEDIA_CONTRACT)
    rows = [row for row in contract["media_entries"]
            if row.get("artifact_role") == ROLE]
    require(
        len(rows) == 1 and rows[0].get("role_id") == 1
        and rows[0].get("policy")
            == "stage-and-independent-target-readback",
        "Bank-2 media role contract drift")
    return int(rows[0]["destination"], 16)


def payload_authority(image: ElfTruth) -> list[dict[str, Any]]:
    contract = load(CONTRACT)
    model = contract["mapped_far_service"]
    section_name = contract["phase_c_owners"]["sections"]["far_service"]
    require(section_name == SERVICE_SECTION, "mapped payload section drift")
    section = image.section(section_name)
    start = image.symbol(
        "__lisp65_c2_mapped_far_service_load_start").value
    end = image.symbol(
        "__lisp65_c2_mapped_far_service_load_end").value
    raw = image.section_bytes(section_name)
    require(
        section.bytes == len(raw) == model["bank2"]["service_bytes"] == 874
        and start == int(model["bank2"]["service_physical_start"], 16)
        and end == int(
            model["bank2"]["service_physical_end_exclusive"], 16)
        and end - start == len(raw),
        "mapped far payload authority drift")
    return [{"name": section_name, "start": start, "end_exclusive": end,
             "bytes": len(raw), "sha256": sha_bytes(raw), "raw": raw}]


def base_artifacts() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    manifest = load(BASE_MANIFEST)
    banks = [row for row in manifest["artifacts"] if row["role"] == ROLE]
    elfs = [row for row in manifest["artifacts"]
            if row["role"] == "linked-product-elf"]
    require(
        len(banks) == len(elfs) == 1
        and ROOT / elfs[0]["path"] == ELF
        and elfs[0] == {**bind(ELF), "role": "linked-product-elf"},
        "frozen product manifest role authority drift")
    require(banks[0] == {**bind(ROOT / banks[0]["path"]), "role": ROLE},
            "frozen Bank-2 input drift")
    return manifest, banks[0], elfs[0]


def extent_identity_gate(
        image: ElfTruth, spans: list[tuple[int, bytes]]) -> dict[str, Any]:
    """Prove continuous delivery and ELF identity for every mapped payload."""
    payloads = payload_authority(image)
    destination = role_destination()
    require(spans, "mapped far delivery has no spans")
    spans = sorted(spans, key=lambda row: row[0])
    cursor = destination
    combined = bytearray()
    for start, raw in spans:
        require(start == cursor and raw,
                "gap or overlap before mapped far payload")
        combined.extend(raw)
        cursor += len(raw)
    required_end = max(row["end_exclusive"] for row in payloads)
    require(cursor >= required_end,
            "mapped far payload delivery extent is truncated")
    rows: list[dict[str, Any]] = []
    for payload in payloads:
        offset = payload["start"] - destination
        delivered = bytes(combined[offset:offset + payload["bytes"]])
        require(
            len(delivered) == payload["bytes"]
            and sha_bytes(delivered) == payload["sha256"]
            and delivered == payload["raw"],
            f"mapped far payload differs from linked ELF: {payload['name']}")
        rows.append({key: value for key, value in payload.items()
                     if key != "raw"})
    return {
        "result": "passed-contiguous-extent-and-linked-ELF-identity",
        "media_role": ROLE, "destination": f"0x{destination:08x}",
        "delivered_end_exclusive": f"0x{cursor:08x}",
        "payloads": rows, "payload_count": len(rows),
        "identity_mismatches": 0, "gaps": 0,
    }


def materialized_bytes() -> tuple[bytes, dict[str, Any]]:
    _manifest, bank, _elf = base_artifacts()
    old = (ROOT / bank["path"]).read_bytes()
    image = truth()
    payload = payload_authority(image)[0]
    destination = role_destination()
    offset = payload["start"] - destination
    require(
        len(old) == 46043 and len(old) <= offset
        and offset == 47282 and payload["end_exclusive"] - destination == 48156,
        "mapped far materialization geometry drift")
    padding = bytes(offset - len(old))
    result = old + padding + payload["raw"]
    gate = extent_identity_gate(image, [(destination, result)])
    return result, {
        "source_bank2": bank,
        "source_bytes_preserved": len(old),
        "zero_padding_bytes": len(padding),
        "padding_start": f"0x{destination + len(old):08x}",
        "payload_start": f"0x{payload['start']:08x}",
        "payload_bytes": payload["bytes"],
        "delivered_bytes": len(result),
        "delivered_sha256": sha_bytes(result),
        "gate": gate,
    }


def successor_manifest_value() -> tuple[dict[str, Any], dict[str, Any]]:
    base, _bank, _elf = base_artifacts()
    raw, delivery = materialized_bytes()
    require(BANK2.is_file() and BANK2.read_bytes() == raw,
            "materialized Bank-2 payload artifact drift")
    value = deepcopy(base)
    rows = [row for row in value["artifacts"] if row["role"] == ROLE]
    require(len(rows) == 1, "successor Bank-2 manifest role drift")
    rows[0].clear(); rows[0].update({**bind(BANK2), "role": ROLE})
    value["static_plane"].update({
        "bank2_static_code_bytes": len(raw),
        "bank2_sha256": sha_bytes(raw),
    })
    value["media_delivery_successor"] = {
        "authority": "owner-approved-media-only-far-payload-materialization",
        "predecessor_manifest": bind(BASE_MANIFEST),
        "linked_ELF": bind(ELF),
        "delivery": delivery,
        "product_relinked": False,
    }
    return value, delivery


def materialize_product_manifest(*, write: bool) -> dict[str, Any]:
    raw, _facts = materialized_bytes()
    if write:
        INPUTS.mkdir(parents=True, exist_ok=False)
        BANK2.write_bytes(raw)
    require(BANK2.is_file() and BANK2.read_bytes() == raw,
            "Bank-2 materialization write/readback drift")
    value, delivery = successor_manifest_value()
    if write:
        PRODUCT_MANIFEST.write_bytes(canonical(value))
    require(load(PRODUCT_MANIFEST) == value,
            "successor canonical product manifest drift")
    return delivery


def packed_far_payload_gate(path: Path = PRODUCT_D81) -> dict[str, Any]:
    visible = PAIR.L65I.D81.visible_files(path.read_bytes())
    require(VISIBLE_NAME in visible, "packed product lacks CODE.BIN")
    raw = visible[VISIBLE_NAME]
    manifest = load(MEDIA_MANIFEST)
    rows = [row for row in manifest["artifacts"] if row["role"] == ROLE]
    require(
        len(rows) == 1 and rows[0] == bind(BANK2)
        | {"role": ROLE, "name": BANK2.name}
        and raw == BANK2.read_bytes(),
        "packed/readback Bank-2 role differs from media manifest")
    value = extent_identity_gate(truth(), [(role_destination(), raw)])
    value["packed_D81"] = bind(path)
    value["packed_member"] = "CODE.BIN"
    value["packed_member_sha256"] = sha_bytes(raw)
    return value


PACKED_ARTIFACTS = {
    "autoboot.c65.elf": STAGER_ELF,
    "lisp65-product.d81/CODE.BIN": PRODUCT_D81,
}
PACKED_ARTIFACT_GATES: dict[str, Callable[[Path], dict[str, Any]]] = {
    "autoboot.c65.elf": PREVIOUS.LIVE.delivered_liveness_gate,
    "lisp65-product.d81/CODE.BIN": packed_far_payload_gate,
}


def run_packed_artifact_gates() -> dict[str, Any]:
    require(set(PACKED_ARTIFACTS) == set(PACKED_ARTIFACT_GATES),
            "media closure omits a registered packed-artifact gate")
    return {name: PACKED_ARTIFACT_GATES[name](PACKED_ARTIFACTS[name])
            for name in sorted(PACKED_ARTIFACTS)}


def extent_mutations() -> list[str]:
    raw, _facts = materialized_bytes()
    destination = role_destination()
    payload = payload_authority(truth())[0]
    gap_at = payload["start"] - destination - 1
    corrupt = bytearray(raw)
    corrupt[payload["start"] - destination] ^= 0x80
    cases = {
        "truncated-payload-extent": [(destination, raw[:-1])],
        "gap-before-payload": [
            (destination, raw[:gap_at]),
            (destination + gap_at + 1, raw[gap_at + 1:]),
        ],
        "payload-byte-differs-from-linked-ELF": [
            (destination, bytes(corrupt))],
    }
    rejected: list[str] = []
    for name, spans in cases.items():
        try:
            extent_identity_gate(truth(), spans)
        except DeliveryError:
            rejected.append(name)
    require(rejected == list(cases), "mapped far delivery mutation survived")
    return rejected


def configure() -> Any:
    _paths, can = PRODUCT.configure_candidate()
    can.MANIFEST = PRODUCT_MANIFEST
    MEDIA.CANONICAL = can
    MEDIA.BUILD = SHARED
    MEDIA.PRODUCT_MANIFEST = PRODUCT_MANIFEST
    MEDIA.MANIFEST = MEDIA_MANIFEST
    MEDIA.DESCRIPTOR = DESCRIPTOR
    MEDIA.STAGER = STAGER
    MEDIA.STAGER_MAP = STAGER_MAP
    MEDIA.PRODUCT_D81 = PRODUCT_D81
    MEDIA.WORK_D81 = WORK_D81
    MEDIA.MOUNT = MOUNT
    return can


def product_world_id() -> int:
    return int(load(PRODUCT_MANIFEST)["static_plane"]["product_build_id"], 0)


def library_facts() -> dict[str, Any]:
    return PRODUCT.library_facts(product_world_id(), existing=True)


def source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = source_override or DRIVER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body
                 if isinstance(node, ast.FunctionDef)}
    build = functions.get("build_action")
    facts_fn = functions.get("facts")
    require(build is not None and facts_fn is not None,
            "far-payload media lifecycle absent")
    build_text = ast.unparse(build)
    build_calls = [ast.unparse(node.func) for node in ast.walk(build)
                   if isinstance(node, ast.Call)]
    facts_calls = [ast.unparse(node.func) for node in ast.walk(facts_fn)
                   if isinstance(node, ast.Call)]
    forbidden = {
        "PRODUCT.complete_action", "PRODUCT.fresh_completion",
        "PRODUCT.CARD.card", "PRODUCT.PRODUCER.produce_candidate",
        "can.run_wplto", "PRODUCT.PRODUCT.single_link",
    }
    require(
        not (set(build_calls) & forbidden)
        and build_calls.count("materialize_product_manifest") == 1
        and build_calls.count("MEDIA.build") == 1
        and "stager_compile_defines=(OPT_IN,)" in build_text
        and build_calls.count("library_facts") == 1
        and facts_calls.count("run_packed_artifact_gates") == 1,
        "far-payload producer can relink/recomplete or omit a closure member")
    return {
        "result": "passed-media-only-regular-pipeline-delivery",
        "product_cards": 0, "WPLTO_runs": 0, "product_links": 0,
        "artifact_completions": 0, "shared_media_builds": 1,
        "library_media_builds": 0,
        "registered_packed_artifact_gates": sorted(PACKED_ARTIFACT_GATES),
    }


def source_mutations() -> list[str]:
    source = DRIVER.read_text(encoding="utf-8")
    anchor = (
        "    source_gate(); source_mutations(); extent_mutations()\n"
        "    configure()\n")
    require(anchor in source, "far-payload build mutation anchor absent")
    cases = {
        "omit-payload-materialization": source.replace(
            "    materialize_product_manifest(write=True)\n", "", 1),
        "drop-stager-opt-in": source.replace(
            "    shared = MEDIA.build(stager_compile_defines=(OPT_IN,))\n",
            "    shared = MEDIA.build(stager_compile_defines=())\n", 1),
        "omit-packed-gates": source.replace(
            "    packed = run_packed_artifact_gates()\n",
            "    packed = {}\n", 1),
        "reenter-completion": source.replace(
            anchor, anchor + "    PRODUCT.fresh_completion()\n", 1),
        "rebuild-library": source.replace(
            "    library_facts()\n", "    PRODUCT.library_facts(\n"
            "        product_world_id(), existing=False)\n", 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            source_gate(candidate)
        except (DeliveryError, SyntaxError):
            rejected.append(name)
    require(rejected == list(cases), "far-payload source mutation survived")
    return rejected


def session_value() -> dict[str, Any]:
    value = deepcopy(load(PREVIOUS.SESSION))
    value["format"] = "lisp65-c2-v150-v20-far-payload-device-session-v1"
    value["status"] = "prepared-D1-repeat-authorized"
    value["identity"] = {
        "product_medium": PRODUCT_D81.relative_to(ROOT).as_posix(),
        "library_medium": LIBRARY_D81.relative_to(ROOT).as_posix(),
    }
    value["authority"] = {
        "product_card": bind(PRODUCT.CARD.RECEIPT),
        "media_closure": RECEIPT.relative_to(ROOT).as_posix(),
        "release_contract": bind(PRODUCT.RELEASE_CONTRACT),
        "far_return_attribution": bind(ATTRIBUTION),
    }
    value["recontact_authorized"] = True
    value["D2_D5_open"] = False
    return value


def facts(*, configured: bool = False) -> dict[str, Any]:
    if not configured:
        configure()
    delivery = materialize_product_manifest(write=False)
    shared = MEDIA.check()
    library = library_facts()
    pair = PAIR.pair_identity(PRODUCT_D81, LIBRARY_D81)
    packed = run_packed_artifact_gates()
    require(
        shared["artifact_count"] == 19
        and shared["canonical_product"] == bind(PRODUCT_MANIFEST)
        and library["D81"] == bind(LIBRARY_D81)
        and pair["result"] == "same-world-pair"
        and pair["product_build_id"] == f"0x{product_world_id():08x}"
        and packed["autoboot.c65.elf"]["result"]
            == "passed-actual-linked-stager-prefix"
        and packed["lisp65-product.d81/CODE.BIN"]["identity_mismatches"] == 0
        and load(SESSION) == session_value(),
        "far-payload media/readback/pair/session closure red")
    return {"delivery": delivery, "shared": shared, "library": library,
            "pair": pair, "packed": packed}


def derive(*, configured: bool = False) -> dict[str, Any]:
    result = facts(configured=configured)
    attribution = load(ATTRIBUTION)
    require(
        attribution["mechanism"] == "MAPPED-FAR-SERVICE-PAYLOAD-UNDELIVERED"
        and attribution["root_cause_named"] is True,
        "far-payload delivery lacks named attribution authority")
    return {
        "format": FORMAT, "recorded_on": RECORDED_ON, "status": STATUS,
        "attempt_accounting": {
            "additional_product_cards": 0, "additional_WPLTO_runs": 0,
            "additional_product_links": 0, "artifact_completions": 0,
            "shared_system_builds": 1, "cold_stager_compiler_runs": 1,
            "library_builds": 0, "media_readbacks": 1,
            "hardware_runs": 0,
        },
        "authority": {
            "owner_approval": git_bind(
                APPROVAL_COMMIT,
                ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"),
            "attribution": bind(ATTRIBUTION),
            "predecessor_media": bind(PREVIOUS.RECEIPT),
            "frozen_linked_ELF": bind(ELF),
            "frozen_product_manifest": bind(BASE_MANIFEST),
            "producer": bind(DRIVER),
        },
        "predecessor_retirement": {
            "current_authority": False,
            "reason": "Bank-2 role ended before the linked far-service LMA",
        },
        "producer_gate": source_gate(),
        "producer_mutations_rejected": source_mutations(),
        "extent_identity_mutations_rejected": extent_mutations(),
        "materialization": result["delivery"],
        "packed_artifact_gate_registry": {
            "registered": sorted(PACKED_ARTIFACT_GATES),
            "executed": sorted(result["packed"]), "complete": True,
            "results": result["packed"],
        },
        "shared_system": {
            "artifact_count": result["shared"]["artifact_count"],
            "artifact_set_sha256": result["shared"]["artifact_set_sha256"],
            "manifest": bind(MEDIA_MANIFEST), "boot_id": bind(DESCRIPTOR),
            "autoboot": bind(STAGER), "autoboot_ELF": bind(STAGER_ELF),
            "product_D81": bind(PRODUCT_D81), "work_D81": bind(WORK_D81),
            "readback": "byteidentical",
        },
        "library": {"D81": result["library"]["D81"],
                    "rebuilt": False, "readback": "predecessor-bound"},
        "pair_identity": result["pair"],
        "hardware_handoff": {
            "D1_repeat_authorized": True, "D2_D5_open": False,
            "session": bind(SESSION),
            "conditions": {
                "regular_pipeline_delivery": True,
                "extent_and_identity_gate": True,
                "byteidentical_media_readback": True,
            },
        },
        "claim_limit": (
            "Media-only delivery closure. No relink, WPLTO, card, artifact "
            "completion or hardware run occurred. D1 is authorized but has "
            "not run; D2-D5 remain closed."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and value.get("attempt_accounting") == {
            "additional_product_cards": 0, "additional_WPLTO_runs": 0,
            "additional_product_links": 0, "artifact_completions": 0,
            "shared_system_builds": 1, "cold_stager_compiler_runs": 1,
            "library_builds": 0, "media_readbacks": 1,
            "hardware_runs": 0}
        and value["predecessor_retirement"]["current_authority"] is False
        and value["materialization"]["delivered_bytes"] == 48156
        and value["materialization"]["zero_padding_bytes"] == 1239
        and value["materialization"]["payload_bytes"] == 874
        and value["materialization"]["gate"]["identity_mismatches"] == 0
        and value["packed_artifact_gate_registry"]["complete"] is True
        and value["packed_artifact_gate_registry"]["registered"]
            == value["packed_artifact_gate_registry"]["executed"]
        and value["shared_system"]["artifact_count"] == 19
        and value["shared_system"]["readback"] == "byteidentical"
        and value["library"]["rebuilt"] is False
        and value["pair_identity"]["result"] == "same-world-pair"
        and all(value["hardware_handoff"]["conditions"].values())
        and value["hardware_handoff"]["D1_repeat_authorized"] is True
        and value["hardware_handoff"]["D2_D5_open"] is False,
        "far-payload delivery closure claim drift")
    if verify:
        require(value == derive(), "far-payload delivery receipt stale")


def receipt_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-card": lambda x: x["attempt_accounting"].update(
            additional_product_cards=1),
        "claim-link": lambda x: x["attempt_accounting"].update(
            additional_product_links=1),
        "promote-predecessor": lambda x: x["predecessor_retirement"].update(
            current_authority=True),
        "shrink-delivered-extent": lambda x: x["materialization"].update(
            delivered_bytes=48155),
        "hide-identity-mismatch": lambda x: x["materialization"]["gate"].update(
            identity_mismatches=1),
        "omit-packed-gate": lambda x: x["packed_artifact_gate_registry"].update(
            executed=["autoboot.c65.elf"]),
        "skip-readback": lambda x: x["shared_system"].update(readback="skipped"),
        "rebuild-library": lambda x: x["library"].update(rebuilt=True),
        "cross-world": lambda x: x["pair_identity"].update(result="mismatch"),
        "open-D2-D5": lambda x: x["hardware_handoff"].update(D2_D5_open=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate, verify=False)
        except DeliveryError:
            rejected.append(name)
    require(rejected == list(cases), "far-payload receipt mutation survived")
    return rejected


def build_action() -> int:
    require(
        not BUILD.exists() and not RECEIPT.exists() and not SESSION.exists(),
        "far-payload delivery successor is one-shot")
    source_gate(); source_mutations(); extent_mutations()
    configure()
    materialize_product_manifest(write=True)
    shared = MEDIA.build(stager_compile_defines=(OPT_IN,))
    require(shared["artifact_count"] == 19, "shared media role count drift")
    library_facts()
    SESSION.write_bytes(canonical(session_value()))
    value = derive(configured=True); validate(value, verify=False)
    value["mutations_rejected"] = receipt_mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("2.0 far payload delivery: PASS bytes=48156 payload=874 D1-ready")
    return 0


def close_action() -> int:
    """Rebind desk authorities without rebuilding any delivered artifact."""
    require(
        BUILD.is_dir() and PRODUCT_D81.is_file() and RECEIPT.is_file(),
        "far-payload delivery local closure is unavailable")
    configure()
    materialize_product_manifest(write=False)
    SESSION.write_bytes(canonical(session_value()))
    value = derive(configured=True); validate(value, verify=False)
    value["mutations_rejected"] = receipt_mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("2.0 far payload delivery: PASS authority-rebound artifacts-unchanged")
    return 0


def check() -> int:
    value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == receipt_mutations(value),
            "far-payload receipt mutation set drift")
    print("2.0 far payload delivery check: PASS extent identity readback D1-ready")
    return 0


def selftest() -> int:
    source_gate()
    require(len(source_mutations()) == 5 and len(extent_mutations()) == 3,
            "far-payload selftest mutation count drift")
    print("2.0 far payload delivery selftest: PASS source=5 extent=3")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("build", "check", "selftest", "_close"))
    action = parser.parse_args().action
    if action == "build":
        result = build_action()
        fresh = subprocess.run(
            [sys.executable, str(DRIVER), "check"], cwd=ROOT, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        require(fresh.returncode == 0,
                "fresh far-payload readback red:\n" + fresh.stdout)
        print(fresh.stdout.strip())
        return result
    return {"check": check, "selftest": selftest,
            "_close": close_action}[action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        DeliveryError, ElfTruthError, PREVIOUS.LivenessMediaError,
        PRODUCT.MediaClosureError, MEDIA.MediaError, RuntimeError, OSError,
        ValueError, KeyError, json.JSONDecodeError,
    ) as error:
        print("2.0 far payload delivery: FIRST RED: " + str(error),
              file=sys.stderr)
        raise SystemExit(2)
