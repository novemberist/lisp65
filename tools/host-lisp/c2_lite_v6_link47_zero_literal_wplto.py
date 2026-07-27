#!/usr/bin/env python3
"""Nonpromotable WPLTO for valid zero-literal C2D-v6 execution.

The probe starts from immutable product Link 47 and removes the accidental
``literal_count != 0`` validity rule.  It binds the real %lcc-consp row to the
generated reader and to the final vm_run_dir -> entry_length -> entry_record
ELF chain.  It creates no promotable product candidate and runs no hardware.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link47_l65e_transient_successor_link as BASE  # noqa: E402
import c2_zero_literal_execution_gate as ZERO  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BASE_DIR = ROOT / (
    "build/c2.2/substitution/"
    "product-link-47-c2-lite-v6-l65e-transient-callability")
BASE_PRODUCT = BASE_DIR / "lisp65-c2-substitution-linked.prg"
BASE_RECEIPT = EVIDENCE / (
    "c2.2-product-link47-c2-lite-v6-l65e-transient-callability-"
    "structural-receipt.json")
HARDWARE_FIRST_RED = EVIDENCE / (
    "c2.2-product-link47-zero-literal-entry-hardware-first-red.json")
OUT = ROOT / "build/c2.2/substitution/link47-zero-literal-wplto"
INTERNAL = EVIDENCE / "c2.2-link47-zero-literal-wplto-internal.json"
RECEIPT = EVIDENCE / "c2.2-link47-zero-literal-wplto-receipt.json"

BASE_PRODUCT_SHA = (
    "c7e57a7004b309a7f4d2836d135d342e4015c5c1127eac6414ace5359c016739")
BASE_RECEIPT_SHA = (
    "78afacdadcd8794f698b6cd9a2ab349379caef5a64ada763c68f9357eb4ccf11")
HARDWARE_FIRST_RED_SHA = (
    "4b96c62a98b12a7649d1fd0246615f2ac2d4d80f1b6c2d1c706cc77e72ce8d31")


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"evidence absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def prerequisites() -> dict[str, Any]:
    for path, digest in {
            BASE_PRODUCT: BASE_PRODUCT_SHA,
            BASE_RECEIPT: BASE_RECEIPT_SHA,
            HARDWARE_FIRST_RED: HARDWARE_FIRST_RED_SHA}.items():
        require(path.is_file() and sha(path) == digest,
                f"Link-47 zero-literal authority drift: {path}")
    baseline = json.loads(BASE_RECEIPT.read_text(encoding="utf-8"))
    first_red = json.loads(HARDWARE_FIRST_RED.read_text(encoding="utf-8"))
    require(
        baseline["link_number"] == 47
        and baseline["product_identity"]["product"]["sha256"] ==
            BASE_PRODUCT_SHA,
        "Link-47 rollback candidate is not authoritative")
    require(
        first_red["status"] ==
            "first-red-valid-zero-literal-c2d-entry-rejected-by-runtime-reader"
        and first_red["accounting"]
            ["line1_product_first_red_budget_before_run"] == "2/3"
        and first_red["accounting"]["line1_boot"] == "passed"
        and first_red["accounting"]["completed_latency_measurements"] ==
            "0/2",
        "zero-literal hardware First Red or counters drift")
    return {
        "link47_rollback_product": {**bind(BASE_PRODUCT),
                                    "status": "untouched"},
        "link47_structural_authority": bind(BASE_RECEIPT),
        "link47_zero_literal_hardware_first_red": bind(HARDWARE_FIRST_RED),
        "zero_literal_gate": bind(ZERO.__file__ and Path(ZERO.__file__)),
        "canonical_product_profile": BASE.PROFILE.check(),
        "driver": bind(Path(__file__)),
    }


def run_probe() -> dict[str, Any]:
    require(not OUT.exists() and not INTERNAL.exists() and not RECEIPT.exists(),
            "Link-47 zero-literal WPLTO probe is one-shot")
    old = {
        "out": BASE.OUT, "receipt": BASE.RECEIPT,
        "number": BASE.LINK_NUMBER,
        "wplto": BASE.WPLTO_REPLAY,
        "wplto_sha": BASE.WPLTO_REPLAY_SHA,
        "prerequisites": BASE.prerequisites,
        "base_product": BASE.PROBE.BASE_PRODUCT,
        "base_product_sha": BASE.PROBE.BASE_PRODUCT_SHA,
        "base_receipt": BASE.PROBE.BASE_RECEIPT,
        "base_receipt_sha": BASE.PROBE.BASE_RECEIPT_SHA,
        "hardware_first_red": BASE.PROBE.HARDWARE_FIRST_RED,
        "hardware_first_red_sha": BASE.PROBE.HARDWARE_FIRST_RED_SHA,
        "transient_source": BASE.TRANSIENT.source_gate,
        "transient_linked": BASE.TRANSIENT.linked_gate,
        "single_link": BASE.LINK44.P.single_link,
    }

    def transient_source(*args: Any, **kwargs: Any) -> dict[str, Any]:
        value = old["transient_source"](*args, **kwargs)
        value["zero_literal_execution"] = ZERO.source_gate(
            generated_runtime=kwargs.get("generated_runtime"))
        return value

    def transient_linked(elf: Path) -> dict[str, Any]:
        value = old["transient_linked"](elf)
        c2d = OUT / "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin"
        value["zero_literal_execution"] = ZERO.linked_gate(elf, c2d)
        return value

    def single_link(*args: Any, **kwargs: Any) -> Any:
        lines = tuple(
            line for line in kwargs.get("extra_contract_lines", ())
            if not line.startswith(("mode=", "source_baseline=",
                                    "promotable=",
                                    "line1_first_red_budget=",
                                    "latency_measurement_attempts=")))
        kwargs["extra_contract_lines"] = (
            "mode=link47-zero-literal-product-shaped-wplto",
            "source_baseline=product-link47-l65e-transient-callability",
            "promotable=no-capacity-placement-probe-only",
            "c2d_v6_literal_count=zero-is-valid-count-not-validity-marker",
            "zero_literal_fixture=ordinal489-lcc-consp-code-length38",
            "line1_first_red_budget=2-of-3-consumed",
            "latency_measurement_attempts=0-of-2-consumed",
            *lines)
        return old["single_link"](*args, **kwargs)

    try:
        BASE.OUT = OUT
        BASE.RECEIPT = INTERNAL
        BASE.LINK_NUMBER = 47
        BASE.WPLTO_REPLAY = BASE_RECEIPT
        BASE.WPLTO_REPLAY_SHA = BASE_RECEIPT_SHA
        BASE.prerequisites = prerequisites
        BASE.PROBE.BASE_PRODUCT = BASE_PRODUCT
        BASE.PROBE.BASE_PRODUCT_SHA = BASE_PRODUCT_SHA
        BASE.PROBE.BASE_RECEIPT = BASE_RECEIPT
        BASE.PROBE.BASE_RECEIPT_SHA = BASE_RECEIPT_SHA
        BASE.PROBE.HARDWARE_FIRST_RED = HARDWARE_FIRST_RED
        BASE.PROBE.HARDWARE_FIRST_RED_SHA = HARDWARE_FIRST_RED_SHA
        BASE.TRANSIENT.source_gate = transient_source
        BASE.TRANSIENT.linked_gate = transient_linked
        BASE.LINK44.P.single_link = single_link
        result = BASE.main()
    finally:
        BASE.OUT = old["out"]
        BASE.RECEIPT = old["receipt"]
        BASE.LINK_NUMBER = old["number"]
        BASE.WPLTO_REPLAY = old["wplto"]
        BASE.WPLTO_REPLAY_SHA = old["wplto_sha"]
        BASE.prerequisites = old["prerequisites"]
        BASE.PROBE.BASE_PRODUCT = old["base_product"]
        BASE.PROBE.BASE_PRODUCT_SHA = old["base_product_sha"]
        BASE.PROBE.BASE_RECEIPT = old["base_receipt"]
        BASE.PROBE.BASE_RECEIPT_SHA = old["base_receipt_sha"]
        BASE.PROBE.HARDWARE_FIRST_RED = old["hardware_first_red"]
        BASE.PROBE.HARDWARE_FIRST_RED_SHA = old["hardware_first_red_sha"]
        BASE.TRANSIENT.source_gate = old["transient_source"]
        BASE.TRANSIENT.linked_gate = old["transient_linked"]
        BASE.LINK44.P.single_link = old["single_link"]

    if result != 0:
        value = {
            "format": "lisp65-c2-lite-v6-zero-literal-wplto-first-red-v1",
            "recorded_on": "2026-07-22",
            "status": "FIRST RED: zero-literal WPLTO stopped",
            "promotable": False,
            "internal_receipt": bind(INTERNAL),
            "link47_rollback": {**bind(BASE_PRODUCT), "status": "untouched"},
            "execution_accounting": {
                "whole_program_lto_closure_links": 1,
                "promotable_product_links": 0, "hardware_runs": 0},
            "next_gate": "stop; return measured First Red to Class-C review",
        }
        write(RECEIPT, value)
        os.chmod(RECEIPT, 0o444)
        return value

    internal = json.loads(INTERNAL.read_text(encoding="utf-8"))
    gates = internal["fresh_replacement_gates"]
    zero_source = gates["transient_execution_lookup"]["source"][
        "zero_literal_execution"]
    zero_linked = gates["transient_execution_lookup"]["linked"][
        "zero_literal_execution"]
    walls = gates["walls"]
    capacity = gates["capacity"]
    require(
        zero_source["status"] == "passed-zero-literal-source-contract"
        and zero_source["generated_sources"]["status"] ==
            "passed-generated-zero-literal-reader"
        and zero_linked["status"] ==
            "passed-linked-vm-run-dir-zero-literal-chain"
        and walls["e000_headroom_bytes"] >= 115
        and all(int(walls[name]) >= 0 for name in (
            "bank0_text_headroom_bytes",
            "ordinary_bank0_bss_headroom_bytes",
            "fixed_hot_block_headroom_bytes",
            "resident_island_headroom_bytes"))
        and capacity["session_family_bytes"] <= 65536,
        "zero-literal WPLTO did not complete fully green")
    product = ROOT / internal["product_identity"]["product"]["path"]
    value = {
        "format": "lisp65-c2-lite-v6-link47-zero-literal-wplto-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-product-shaped-WPLTO-no-hardware-no-product-candidate",
        "promotable": False,
        "claim_limit": (
            "Host fixture, generated source, final ELF chain and WPLTO "
            "placement only; no hardware result inherited."),
        "authority": prerequisites(),
        "zero_literal_execution": {
            "source": zero_source, "linked": zero_linked},
        "walls": walls,
        "capacity": capacity,
        "product_shaped_identity": {**bind(product), "nonpromotable": True},
        "internal_structural_receipt": bind(INTERNAL),
        "link47_rollback": {**bind(BASE_PRODUCT), "status": "untouched"},
        "execution_accounting": {
            "whole_program_lto_closure_links": 1,
            "promotable_product_links": 0, "hardware_runs": 0},
        "counters": {"line1_product_first_reds": "2/3",
                     "completed_latency_measurements": "0/2"},
        "next_gate": "authorized successor product link",
    }
    write(RECEIPT, value)
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-link47-zero-literal-wplto: PASS "
          f"text={walls['bank0_text_headroom_bytes']} "
          f"e000={walls['e000_headroom_bytes']} "
          f"session={capacity['session_family_bytes']} "
          "promotable=no hardware=not-run")
    return value


def main() -> int:
    try:
        run_probe()
        return 0
    except (GateError, ZERO.GateError, OSError, RuntimeError, ValueError,
            json.JSONDecodeError) as error:
        print("c2-lite-v6-link47-zero-literal-wplto: FAIL: " + str(error),
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
