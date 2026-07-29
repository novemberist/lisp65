#!/usr/bin/env python3
"""Qualify the two-row G2 target symbol-value timing fixture.

The gate executes the compiler carrier actually bound by Link 78.  It proves
that the two complete self-timed forms differ in one byte only: CALLPRIM 57
(`boundp`) versus CALLPRIM 19 (`symbol-value`).  No product is built or
changed, and no target observation is manufactured.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import c2_link75_require_defstruct_host_attribution as ATTR  # noqa: E402


CONFIG = ROOT / "config/c2.2-v1.2.2-g2-symbol-value-cost-session.json"
LINK78 = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link78-dirmiss-renderer-structural-receipt.json"
)
G2 = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.2-g2-gc-work-attribution-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.2-g2-symbol-value-cost-preparation-receipt.json"
)
VM = ROOT / "src/vm.c"
SYMBOL = ROOT / "src/symbol.c"
VM_EMBED = ROOT / "src/vm_embed.c"
WORKBENCH = ROOT / "config/workbench.mk"
FORMAT = "lisp65-c2.2-v1.2.2-g2-symbol-value-cost-preparation-v1"


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"bound input absent: {path}")
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def root_path(row: dict[str, Any], label: str) -> Path:
    path = (ROOT / row["path"]).resolve()
    require(path.is_file(), f"{label} absent: {path}")
    require(sha(path) == row["sha256"], f"{label} SHA drift")
    return path


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def validate_contract(value: dict[str, Any]) -> None:
    require(
        value.get("format")
        == "lisp65-c2.2-v1.2.2-g2-symbol-value-cost-session-v1",
        "measurement format drift",
    )
    require(value.get("iterations") == 1000, "iteration count drift")
    clock = value.get("clock", {})
    require(
        clock.get("low_address") == "$FF83"
        and clock.get("high_address") == "$FF84"
        and clock.get("snapshot") == "high-low-high"
        and "16-bit" in clock.get("delta", ""),
        "16-bit stable frame clock contract drift",
    )
    rows = value.get("rows", [])
    require(
        len(rows) == 2
        and [row.get("id") for row in rows]
        == ["g2-boundp-control-1000", "g2-symbol-value-1000"],
        "two-row order drift",
    )
    require(
        rows[0]["primitive"] == {
            "name": "boundp",
            "id": 57,
            "target_path": "resident symbnd bitmap",
        },
        "matched control primitive drift",
    )
    require(
        rows[1]["primitive"] == {
            "name": "symbol-value",
            "id": 19,
            "target_path":
                "sym_value -> symval_get -> one 2-byte Bank-5 DMA",
        },
        "measured primitive drift",
    )
    setup = value.get("setup_forms", [])
    transport = value.get("input_transport", {})
    require(
        setup == [{
            "id": "g2-frame-snapshot",
            "form":
                "(defun %f()(list(peek 255 132)(peek 255 131)(peek 255 132)))",
            "result": "%f",
        }]
        and transport.get("maximum_form_characters") == 76
        and all(
            len(row["form"]) <= transport["maximum_form_characters"]
            for row in rows
        ),
        "verified-input transport or frame-snapshot setup drift",
    )
    for row in rows:
        form = row.get("form", "")
        require(
            form.count("(%f)") == 2
            and "(dotimes(i 1000)" in form
            and row.get("result_tuple")
            == (
                "((start-high-1 start-low start-high-2) "
                "(end-high-1 end-low end-high-2))"
            ),
            f"unstable or incomplete frame tuple: {row.get('id')}",
        )
    adjudication = value.get("adjudication", {})
    require(
        adjudication.get("whole_collection_authority_frames") == 89
        and adjudication.get("majority_threshold_frames") == 44.5
        and adjudication.get("excess_frames_per_read")
            == "(measured_frames - control_frames) / 1000"
        and adjudication.get("excess_microseconds_per_1000")
            == "(measured_frames - control_frames) * 20000"
        and adjudication.get("excess_microseconds_per_read")
            == "(measured_frames - control_frames) * 20"
        and "<delta*20>us/read" in
            adjudication.get("required_value_string", "")
        and "* 480 / 1000" in
            adjudication.get("projected_480_read_excess_frames", "")
        and "not named as the absolute cost" in
            adjudication.get("claim_limit", ""),
        "adjudication or claim boundary drift",
    )
    applicability = value.get("cost_constant_applicability", {})
    require(
        applicability.get("directly_comparable_2_byte_vm_dma_reads")
        == ["symval_get", "nameoff_get", "symfn_ext_get"]
        and len(applicability.get(
            "reference_only_not_directly_multipliable", [])) == 2
        and "not calculated from this constant" in
            applicability.get("R2_rule", ""),
        "per-read cost applicability boundary drift",
    )
    policy = value.get("policy", {})
    require(
        policy.get("product_bytes") == 0
        and policy.get("new_product_links") == 0
        and policy.get("dedicated_hardware_sessions") == 0
        and policy.get("g3_remains_closed_until_result") is True,
        "zero-product-byte or G3-closed policy drift",
    )


def link78_carrier() -> tuple[Path, Path, dict[str, Any]]:
    link = load(LINK78)
    require(
        link.get("status") == "passed-Link78-D1-renderer-hardware-not-run"
        and link.get("link_number") == 78,
        "Link-78 structural authority drift",
    )
    compiler = link["gates"]["compiler_tier"]
    carrier = root_path(compiler["carrier"], "Link-78 bound compiler carrier")
    generated = compiler.get("generated_outputs", [])
    suite_rows = [
        row for row in generated if row["path"].endswith("/suite.json")
    ]
    require(len(suite_rows) == 1, "Link-78 compiler suite binding drift")
    suite = root_path(suite_rows[0], "Link-78 compiler suite")
    tier = suite.parent / "tier-generation.json"
    require(tier.is_file(), "Link-78 compiler tier receipt absent")
    require(
        link["product"]["sha256"]
        == load(CONFIG)["candidate_binding"]["product_sha256"]
        and link["ELF"]["sha256"]
        == load(CONFIG)["candidate_binding"]["elf_sha256"],
        "measurement candidate does not bind Link 78",
    )
    return carrier, tier, link


def compile_rows(
    contract: dict[str, Any], carrier: Path, tier: Path
) -> dict[str, Any]:
    ATTR.CARRIER = carrier
    ATTR.TIER = tier
    compiler = ATTR.BoundCarrierCompiler()
    outputs = []
    for row in contract["rows"]:
        source = f"(defun %{row['id']}(){row['form']})"
        result = compiler.compile(source)
        outputs.append(result)
    control = outputs[0]["code"]
    measured = outputs[1]["code"]
    require(
        (
            control.nargs, control.nlocals, control.flags,
            control.littab, len(control.payload),
        )
        == (
            measured.nargs, measured.nlocals, measured.flags,
            measured.littab, len(measured.payload),
        ),
        "bound compiler changed header, literals or payload length",
    )
    differences = [
        (index, before, after)
        for index, (before, after)
        in enumerate(zip(control.payload, measured.payload))
        if before != after
    ]
    require(
        differences == [(27, 57, 19)]
        and control.payload[26] == measured.payload[26] == 61
        and control.payload[28] == measured.payload[28] == 1,
        f"bound compiler forms are not one CALLPRIM-ID apart: {differences}",
    )
    shape = contract["compiled_shape_contract"]
    require(
        shape["payload_bytes"] == len(control.payload)
        and shape["only_payload_difference"]
        == {
            "offset": 27,
            "control": 57,
            "measured": 19,
            "preceded_by": "CALLPRIM",
            "followed_by_argc": 1,
        },
        "recorded bound-carrier shape drift",
    )
    return {
        "status":
            "passed-actual-bound-carrier-one-byte-measurement-pair",
        "carrier": bind(carrier),
        "tier": bind(tier),
        "control": outputs[0]["summary"],
        "measured": outputs[1]["summary"],
        "payload_differences": [
            {"offset": i, "control": a, "measured": b}
            for i, a, b in differences
        ],
        "executed_compiler_cases": 2,
    }


def target_path_gate() -> dict[str, Any]:
    vm = VM.read_text(encoding="utf-8")
    symbol = SYMBOL.read_text(encoding="utf-8")
    embed = VM_EMBED.read_text(encoding="utf-8")
    workbench = WORKBENCH.read_text(encoding="utf-8")
    require(
        "case 19:  /* symbol-value */" in vm
        and "return sym_value(a[0]);" in vm
        and "case 57: /* boundp" in vm
        and "return sym_boundp(a[0]) ? vm_t : NIL;" in vm,
        "VM primitive path drift",
    )
    require(
        "obj  sym_value(obj s)              { return symval_get(sidx(s)); }"
        in symbol
        and "uint8_t sym_boundp(obj s)" in symbol
        and "symbnd[i >> 3]" in symbol,
        "symbol access path drift",
    )
    require(
        "obj symval_get(uint16_t i)" in embed
        and "SYMVAL_EXT_BANK" in embed
        and "SYMVAL_EXT_OFF + i * 2u" in embed
        and "uint16_t nameoff_get(uint16_t i)" in embed
        and "NAMEOFF_EXT_OFF + i * 2u" in embed
        and "obj symfn_ext_get(uint16_t i)" in embed
        and "SYMFN_EXT_OFF + i * 2u" in embed
        and "vm_dma(" in embed
        and ", 0, 2);" in embed
        and "-DLISP65_SYMVAL_EXT" in workbench,
        "target Bank-5 two-byte symval path drift",
    )
    return {
        "status": "passed-target-control-and-measured-paths",
        "control": "CALLPRIM 57 -> sym_boundp -> resident symbnd bitmap",
        "measured":
            "CALLPRIM 19 -> sym_value -> symval_get -> 2-byte Bank-5 DMA",
        "same_shape_consumers": [
            "nameoff_get: 2-byte Bank-5 vm_dma",
            "symfn_ext_get: 2-byte Bank-5 vm_dma",
        ],
        "reference_only_consumers": [
            "sympool_read/symname: variable-length bulk vm_dma",
            "Prim-67 %c2d-byte: c2_stream_c2d_read",
        ],
        "sources": [
            bind(VM), bind(SYMBOL), bind(VM_EMBED), bind(WORKBENCH)
        ],
    }


def mutation_gate(contract: dict[str, Any]) -> list[str]:
    accepted: list[str] = []

    def reject(name: str, mutate: Any) -> None:
        value = copy.deepcopy(contract)
        mutate(value)
        try:
            validate_contract(value)
        except (GateError, KeyError, TypeError):
            accepted.append(name)

    reject("iteration-count-drift", lambda c: c.update(iterations=999))
    reject(
        "control-primitive-drift",
        lambda c: c["rows"][0]["primitive"].update(id=19),
    )
    reject(
        "measured-primitive-drift",
        lambda c: c["rows"][1]["primitive"].update(id=57),
    )
    reject(
        "one-byte-clock-substitution",
        lambda c: c["clock"].update(delta="unsigned low-byte delta"),
    )
    reject(
        "unstable-start-snapshot",
        lambda c: c["rows"][0].update(
            form=c["rows"][0]["form"].replace(
                "(%f)", "nil", 1)),
    )
    reject(
        "target-read-count-drift",
        lambda c: c["adjudication"].update(
            projected_480_read_excess_frames=
                "(measured_frames - control_frames) * 479 / 1000"),
    )
    reject(
        "whole-envelope-authority-drift",
        lambda c: c["adjudication"].update(
            whole_collection_authority_frames=88),
    )
    reject(
        "majority-threshold-drift",
        lambda c: c["adjudication"].update(
            majority_threshold_frames=44),
    )
    reject(
        "absolute-cost-overclaim",
        lambda c: c["adjudication"].update(
            claim_limit="This is the absolute cost of symval_get."),
    )
    reject(
        "microsecond-conversion-drift",
        lambda c: c["adjudication"].update(
            excess_microseconds_per_read=
                "(measured_frames - control_frames) * 20000"),
    )
    reject(
        "Prim67-transfer-overclaim",
        lambda c: c["cost_constant_applicability"].update(
            R2_rule=(
                "Multiply all 399 Prim-67 reads by this constant directly.")),
    )
    reject(
        "product-byte-creep",
        lambda c: c["policy"].update(product_bytes=1),
    )
    require(len(accepted) == 12, "mutation selftest did not reject 12/12")
    return accepted


def main() -> None:
    contract = load(CONFIG)
    validate_contract(contract)
    carrier, tier, link = link78_carrier()
    compiled = compile_rows(contract, carrier, tier)
    target = target_path_gate()
    prior = load(G2)
    require(
        prior.get("format")
        == "lisp65-c2.2-v1.2.2-g2-gc-work-attribution-v1"
        and prior["target_binding"]["proven_DMA_job_lower_bound"]
            ["composition"]["Bank5_symval_2_byte_reads"] == 480
        and prior["target_binding"]["target_phase_frames"]
            ["whole_collection_authority"] == 89,
        "prior G2 480-read or 89-frame authority drift",
    )
    mutations = mutation_gate(contract)
    receipt = {
        "format": FORMAT,
        "recorded_on": "2026-07-29",
        "status":
            "passed-host-qualified-two-row-measurement-awaiting-bundled-session",
        "inputs": {
            "measurement_contract": bind(CONFIG),
            "prior_G2_attribution": bind(G2),
            "Link78_structural_authority": bind(LINK78),
            "Link78_product": link["product"],
            "Link78_ELF": link["ELF"],
        },
        "bound_carrier_execution": compiled,
        "target_dataflow": target,
        "measurement": {
            "rows": 2,
            "iterations_per_row": 1000,
            "frame_counter": "$FF84/$FF83/$FF84",
            "frame_width_bits": 16,
            "accepted_target_symbol_reads": 480,
            "accepted_whole_collection_frames": 89,
            "projected_share_formula":
                "(symbol_value_frames - boundp_frames) * 480 / 1000",
            "required_per_read_report": {
                "excess_frames_per_1000":
                    "symbol_value_frames - boundp_frames",
                "excess_frames_per_read":
                    "(symbol_value_frames - boundp_frames) / 1000",
                "excess_microseconds_per_read":
                    "(symbol_value_frames - boundp_frames) * 20",
                "value_string":
                    "symval-minus-boundp=<delta>f/1000 = "
                    "<delta/1000>f/read = <delta*20>us/read; "
                    "projected-480=<delta*480/1000>f/89f",
            },
            "cost_constant_applicability":
                contract["cost_constant_applicability"],
            "dominance_threshold_frames": 44.5,
            "hardware_results": None,
        },
        "mutations_rejected": mutations,
        "execution_witnesses": {
            "bound_carrier_cases": 2,
            "negative_mutations": len(mutations),
        },
        "product_delta": {
            "bytes": 0,
            "links": 0,
            "dedicated_hardware_sessions": 0,
        },
        "G3": {
            "status": "closed-until-measurement",
            "reason":
                "No block-read or other GC cut is authorized by host counts.",
        },
        "claim_limit": (
            "The host gate proves an actual-bound-carrier, one-byte-matched "
            "target timing pair and its target dataflows. It does not supply "
            "hardware frames and does not call the delta the absolute cost "
            "of symval_get."
        ),
    }
    atomic_json(RECEIPT, receipt)
    print(
        "c2-v1.2.2-g2-symbol-value-cost: PASS "
        "carrier_cases=2 payload_diffs=1 mutations=12/12 "
        "product_bytes=0 links=0 hardware=queued"
    )


if __name__ == "__main__":
    try:
        main()
    except (GateError, ATTR.AttributionError, KeyError, TypeError) as exc:
        raise SystemExit(
            f"c2-v1.2.2-g2-symbol-value-cost: FIRST RED: {exc}")
