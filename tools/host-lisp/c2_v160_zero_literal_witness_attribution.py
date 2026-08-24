#!/usr/bin/env python3
"""Attribute the R1 zero-literal drift without rebuilding the product."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_comfort_input_fidelity as FIDELITY  # noqa: E402
import c2_zero_literal_execution_gate as ZERO  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
FINAL_RED = ARCH / (
    "c2.3-v1.6-abort-driver-relocation-equate-owner-card-final-red.json")
RECEIPT = ARCH / "c2.3-v1.6-zero-literal-witness-attribution-receipt.json"
BUILD = ROOT / "build/c2.3/v1.6-abort-driver-relocation-equate-owner-card"
LOCAL_STDLIB = BUILD / "static-plane/narrow-static/stdlib-p0.manifest.json"
PRODUCT = BUILD / "static-plane/narrow-static/product/substitution-artifacts.json"
C2D = BUILD / (
    "wplto/fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin")
CODE = BUILD / (
    "wplto/fresh-c2-lite-prelink-gates/v6-semantics/bank2-static-code.bin")
R1_WORLDS = (
    "v1.6-abort-driver-relocation-card",
    "v1.6-abort-driver-relocation-replacement-card",
    "v1.6-abort-driver-relocation-second-replacement-card",
    "v1.6-abort-driver-relocation-file-membership-card",
    "v1.6-abort-driver-relocation-equate-owner-card",
)


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"file absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def witness(specs: tuple[tuple[str, str, Path], ...]) -> dict[str, Any]:
    old = ZERO.CANONICAL_SPECS
    ZERO.CANONICAL_SPECS = specs
    try:
        value = ZERO.canonical_witness()
    finally:
        ZERO.CANONICAL_SPECS = old
    return value


def row_view(value: dict[str, Any]) -> dict[str, Any]:
    row = bytes(value["row"])
    return {
        "ordinal": value["ordinal"],
        "local_ordinal": value["local_ordinal"],
        "image": value["image"],
        "name": value["name"],
        "kind": value["kind"],
        "literal_count": value["literal_count"],
        "code_length": value["code_length"],
        "row_hex": row.hex(),
        "image_entry_counts": value["image_entry_counts"],
        "entry_count": value["entry_count"],
        "resolution_limit": value["resolution_limit"],
        "code_sha256": hashlib.sha256(bytes(value["code_bytes"])).hexdigest(),
    }


def derive() -> dict[str, Any]:
    red = load(FINAL_RED)
    require(red["status"] == "FINAL RED: R1 EQUATE-OWNER CARD RETURNS TO OWNER",
            "R1 equate-owner Final Red drift")
    product = load(PRODUCT)
    rows = product["manifests"]
    labels = ZERO.SPEC_ROLES
    require(len(rows) == len(labels), "product manifest inventory drift")
    product_specs = tuple(
        (key, role, ROOT / str(row["path"]))
        for (key, role), row in zip(labels, rows))
    require(all(path.is_file() and sha(path) == row["sha256"]
                for (_key, _role, path), row in zip(product_specs, rows)),
            "product manifest binding drift")

    local_specs = (
        (labels[0][0], labels[0][1], LOCAL_STDLIB),
        *product_specs[1:],
    )
    product_witness = witness(product_specs)
    gate_witness = witness(local_specs)
    product_view = row_view(product_witness)
    gate_view = row_view(gate_witness)
    require(product_view["ordinal"] == 658
            and product_view["row_hex"] == "0500b49626007c090100"
            and gate_view["ordinal"] == 609
            and gate_view["row_hex"] == "0500fd8b2600f5080100",
            "reconstructed zero-literal witness drift")

    c2d = C2D.read_bytes()
    gate_at = ZERO.ENTRY_OFFSET + ZERO.ENTRY_BYTES * gate_view["ordinal"]
    product_at = ZERO.ENTRY_OFFSET + ZERO.ENTRY_BYTES * product_view["ordinal"]
    observed = c2d[gate_at:gate_at + ZERO.ENTRY_BYTES]
    delivered = c2d[product_at:product_at + ZERO.ENTRY_BYTES]
    require(observed.hex() == "030101845400cb080100"
            and delivered == bytes(product_witness["row"]),
            "linked C2D row reconstruction drift")
    code = CODE.read_bytes()
    code_offset = int.from_bytes(delivered[2:4], "little")
    code_length = int.from_bytes(delivered[4:6], "little")
    delivered_code = code[code_offset:code_offset + code_length]
    require(delivered_code == ZERO.WITNESS_CODE_BYTES
            == bytes(product_witness["code_bytes"]),
            "delivered zero-literal code witness drift")

    local_manifest = load(LOCAL_STDLIB)
    product_manifest = load(product_specs[0][2])
    local_entries = len(local_manifest["entries"])
    product_entries = len(product_manifest["entries"])
    require(local_entries == 344 and product_entries == 393
            and product_entries - local_entries == 49
            and gate_view["ordinal"] + 49 == product_view["ordinal"],
            "stdlib inventory delta does not explain the ordinal drift")
    require(all(sha(left[2]) == sha(right[2])
                for left, right in zip(local_specs[1:], product_specs[1:])),
            "more than the stdlib input differs between witness worlds")

    world_rows = []
    for name in R1_WORLDS:
        path = ROOT / "build/c2.3" / name / (
            "wplto/fresh-c2-lite-prelink-gates/v6-semantics/"
            "initial.c2d-v6.bin")
        world_rows.append({"world": name, **bind(path)})
    require(len({row["sha256"] for row in world_rows}) == 1
            and world_rows[-1]["sha256"] == sha(C2D),
            "R1 C2D changed across the relocation family")

    elf = Path(str(C2D.parents[2] / "lisp65-c2-substitution-linked.prg.elf"))
    old_specs = ZERO.CANONICAL_SPECS
    try:
        ZERO.CANONICAL_SPECS = local_specs
        try:
            ZERO.linked_gate(elf, C2D)
        except ZERO.GateError as error:
            mixed_red = str(error)
        else:
            raise AttributionError("mixed-inventory real consumer passed")
        ZERO.CANONICAL_SPECS = product_specs
        product_pass = ZERO.linked_gate(elf, C2D)
    finally:
        ZERO.CANONICAL_SPECS = old_specs
    require(mixed_red == ZERO.witness_drift_message(
                ordinal=gate_view["ordinal"],
                expected=bytes(gate_witness["row"]), observed=observed)
            and product_pass["status"] ==
                "passed-linked-vm-run-dir-zero-literal-chain",
            "real linked-consumer counterprobe drift")

    report = ZERO.drift_report_selftest()
    return {
        "format": "lisp65-c2-v160-zero-literal-witness-attribution-v1",
        "recorded_on": "2026-08-19",
        "status": "ATTRIBUTED: STORED-WORLD WITNESS; ZERO-LITERAL REGRESSION ABSENT",
        "authority": {
            "commission": "4ad1d129",
            "Final_Red": bind(FINAL_RED),
            "driver": bind(Path(__file__)),
            "zero_literal_gate": bind(Path(ZERO.__file__)),
        },
        "decision": {
            "classification": "cross-inventory stored-world witness",
            "successor_shape": "derived-not-pinned consumer conversion",
            "successor_card_authorized": False,
            "genuine_zero_literal_regression": False,
            "R1_relocation_moved_C2D": False,
        },
        "reconstructed_gate_comparison": {
            "expected": gate_view,
            "observed_at_expected_ordinal": {
                "ordinal": gate_view["ordinal"],
                "row_hex": observed.hex(),
                "decoded_image": observed[0],
                "decoded_literal_count": observed[1],
                "decoded_code_length": int.from_bytes(observed[4:6], "little"),
            },
            "diagnostic": ZERO.witness_drift_message(
                ordinal=gate_view["ordinal"],
                expected=bytes(gate_witness["row"]), observed=observed),
        },
        "linked_product_truth": {
            "witness": product_view,
            "observed_row_hex": delivered.hex(),
            "row_matches": delivered == bytes(product_witness["row"]),
            "code_offset": code_offset,
            "code_length": code_length,
            "code_matches_canonical_38_bytes": True,
            "C2D": bind(C2D),
            "bank2_static_code": bind(CODE),
        },
        "moving_input": {
            "role": "stdlib-p0 manifest",
            "gate_side": {"entries": local_entries, **bind(LOCAL_STDLIB)},
            "product_side": {"entries": product_entries,
                             **bind(product_specs[0][2])},
            "entry_delta": product_entries - local_entries,
            "ordinal_delta": product_view["ordinal"] - gate_view["ordinal"],
            "other_five_manifest_SHAs_identical": True,
            "mechanism": ("the gate derived a global ordinal and row from the "
                "local emitted stdlib inventory, then indexed a C2D emitted "
                "from the bound product inventory"),
        },
        "R1_family_C2D_identity": world_rows,
        "real_linked_consumer_counterprobe": {
            "ELF": bind(elf),
            "mixed_inventory": {"status": "rejected", "message": mixed_red},
            "product_inventory": {
                "status": product_pass["status"],
                "witness": product_pass["c2d_witness"],
            },
            "product_bytes_changed_between_probes": False,
        },
        "permanent_gate_rule": {
            "rule": "every drift report carries ordinal, expected and observed",
            "selftest": report,
        },
        "attempt_accounting": {
            "product_source_changes": 0,
            "WPLTO_runs": 0,
            "product_links": 0,
            "media_builds": 0,
            "device_contacts": 0,
        },
        "claim_limit": ("Host-only attribution. It proves the historical gate "
            "mixed inventories and that the linked C2D contains the canonical "
            "zero-literal witness; it does not authorize a successor card."),
        "next": "owner disposition: authorize conversion or keep R1 parked",
    }


def validate(value: dict[str, Any]) -> None:
    require(value["status"].startswith("ATTRIBUTED: STORED-WORLD")
            and value["decision"]["genuine_zero_literal_regression"] is False
            and value["decision"]["R1_relocation_moved_C2D"] is False
            and value["moving_input"]["entry_delta"] == 49
            and value["moving_input"]["ordinal_delta"] == 49
            and value["linked_product_truth"]["row_matches"] is True
            and value["linked_product_truth"]
                ["code_matches_canonical_38_bytes"] is True
            and len({row["sha256"] for row in
                     value["R1_family_C2D_identity"]}) == 1
            and value["real_linked_consumer_counterprobe"]
                ["mixed_inventory"]["status"] == "rejected"
            and value["real_linked_consumer_counterprobe"]
                ["product_inventory"]["status"] ==
                    "passed-linked-vm-run-dir-zero-literal-chain"
            and value["real_linked_consumer_counterprobe"]
                ["product_bytes_changed_between_probes"] is False
            and value["attempt_accounting"] == {
                "product_source_changes": 0, "WPLTO_runs": 0,
                "product_links": 0, "media_builds": 0,
                "device_contacts": 0},
            "zero-literal attribution receipt drift")


def selftest() -> None:
    value = derive()
    validate(value)
    mutations = []
    for name, mutate in (
        ("call-it-regression", lambda x: x["decision"].update(
            genuine_zero_literal_regression=True)),
        ("lose-row-match", lambda x: x["linked_product_truth"].update(
            row_matches=False)),
        ("lose-code-match", lambda x: x["linked_product_truth"].update(
            code_matches_canonical_38_bytes=False)),
        ("dim-entry-delta", lambda x: x["moving_input"].update(entry_delta=48)),
    ):
        candidate = json.loads(json.dumps(value))
        mutate(candidate)
        try:
            validate(candidate)
        except AttributionError:
            mutations.append(name)
    require(len(mutations) == 4, "attribution mutation survived")
    print("v1.6 zero-literal attribution: SELFTEST PASS mutations=4")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "check", "selftest"))
    action = parser.parse_args().action
    if action == "run":
        require(not RECEIPT.exists(), "attribution receipt already exists")
        value = derive(); validate(value)
        RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
        print("v1.6 zero-literal attribution: STORED-WORLD delta=49")
    elif action == "check":
        validate(load(RECEIPT))
        print("v1.6 zero-literal attribution: CHECK PASS")
    else:
        selftest()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, ZERO.GateError) as error:
        print(f"v1.6 zero-literal attribution: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
