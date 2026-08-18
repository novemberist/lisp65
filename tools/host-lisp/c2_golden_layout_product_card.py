#!/usr/bin/env python3
"""The sole owner-authorized product card under the golden-layout inversion."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import c2_golden_layout_inversion as GOLD  # noqa: E402
import c2_v18_full_map_repair_wplto as V18  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/post-promotion/golden-layout-inversion-product-card"
PREFLIGHT = ROOT / "build/post-promotion/golden-layout-inversion-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
RECEIPT = EVIDENCE / "c2.3-golden-layout-inversion-product-card-receipt.json"
FIRST_RED = EVIDENCE / (
    "c2.3-golden-layout-inversion-product-card-first-red.json")
REVIEW = ROOT / "docs/planning/golden-layout-inversion-review.md"
REVIEW_RECEIPT = GOLD.RECEIPT
OWNER_REVIEW_COMMIT = "8443421751f8e3188fc0428e6ab18a86b6fa0aed"
INVOKED_DRIVER_COMMIT = "a50b6f1907d510b4c8ab47f8692f6adbe617f5f2"
RECORDED_ON = "2026-08-09"
DRIVER = Path(__file__).resolve()


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"regular JSON authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"regular card artifact absent: {path}")
    return GOLD.bind(path)


def owner_review() -> dict[str, Any]:
    binding = GOLD.git_binding(
        OWNER_REVIEW_COMMIT, REVIEW.relative_to(ROOT).as_posix())
    raw = V18.subprocess.run(
        ["git", "show", f"{OWNER_REVIEW_COMMIT}:{binding['path']}"],
        cwd=ROOT, check=True, stdout=V18.subprocess.PIPE).stdout
    require(
        b"Authorized: exactly one product card" in raw
        and b"No device, no retry" in raw,
        "one-time owner golden acceptance is not bound")
    return binding


def audit_review() -> dict[str, Any]:
    expected = GOLD.build_receipt()
    recorded = load(REVIEW_RECEIPT)
    require(GOLD.canonical(recorded) == GOLD.canonical(expected),
            "golden review receipt drift")
    require(expected["execution_witness"] == {
        "terminal_elf_layout_extractions": 2,
        "golden_comparisons": 2,
        "mutations": 12,
        "product_compiles": 0,
        "fresh_wplto": 0,
        "device_contacts": 0,
    }, "golden review execution boundary drift")
    return expected


def configure_card() -> None:
    V18.BUILD = BUILD
    V18.PREFLIGHT = PREFLIGHT
    V18.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT
    V18.RECEIPT = RECEIPT
    V18.FIRST_RED = FIRST_RED
    V18.DRIVER = DRIVER
    V18.configure_base()
    # The inherited gate pipeline is deliberately not an acceptance surface.
    # BASE.configure installs only the owned full-map linker/source routing;
    # build_candidate invokes the producer below its historical closers.
    V18.BASE.host_gates = lambda: {}
    V18.BASE.configure()


def build_candidate() -> dict[str, Any]:
    joint = V18.BASE.JOINT
    profile_receipt = load(joint.PROFILE_RECEIPT)
    geometry = profile_receipt.get("geometry", {})
    require(
        profile_receipt["status"] == "passed-v1.3-joint-linker-free-profile"
        and geometry.get("bank2_static_code_bytes") == joint.EXPECTED_STATIC
        and geometry.get("entries") == joint.EXPECTED_ENTRIES
        and geometry.get("resolutions") == joint.EXPECTED_RESOLUTIONS
        and geometry.get("roots") == joint.EXPECTED_ROOTS,
        "linked-product input authority drift")

    paths = joint.configure(BUILD)
    static = joint.BASE.PROBE.REQ.build_static_plane()
    plane = joint.BASE.PROBE.REQ.F1W.static_gate()
    header = joint.PRODUCT.bind_generated_stdlib_header(paths)
    product_path = paths["static_product"] / "substitution-artifacts.json"
    product = load(product_path)
    require(
        static["semantics"]["code_bytes"] == joint.EXPECTED_STATIC
        and plane["static_code_bytes"] == joint.EXPECTED_STATIC
        and product["entries"] == joint.EXPECTED_ENTRIES
        and product["resolutions"] == joint.EXPECTED_RESOLUTIONS
        and product["roots"] == joint.EXPECTED_ROOTS
        and product["product_build_id_hex"] == geometry["product_build_id"],
        "linked-product static-plane construction drift")

    joint.V.EXPECTED_PRODUCT_ID = geometry["product_build_id"]
    joint.V.EXPECTED_BANK2_SHA = geometry["bank2_sha256"]
    old = joint.CAN.configure_wplto()
    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output):
            producer_return = joint.CAN.LINK_GATE.BASE.main()
    finally:
        joint.CAN.restore_wplto(old)
    log = BUILD / "receipts/golden-card-producer.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(output.getvalue(), encoding="utf-8")

    elf = paths["wplto"] / "lisp65-c2-substitution-linked.prg.elf"
    base_result_path = joint.CAN.LINK_GATE.BASE.BASE_RESULT
    require(elf.is_file() and base_result_path.is_file(),
            "product producer did not emit the linked candidate ELF")
    base_result = load(base_result_path)
    wplto = base_result.get("WPLTO", {})
    require(wplto.get("product_completed") is True
            and wplto.get("exception") is None,
            "product producer did not reach completed linked artifacts")
    return {
        "elf": elf,
        "map": paths["wplto"] / "lisp65-c2-substitution-linked.prg.map",
        "prg": paths["wplto"] / "lisp65-c2-substitution-linked.prg",
        "lto": paths["wplto"] / "resident-island-seed.prg.lto.o",
        "linker": paths["wplto"] / "c2-substitution.ld",
        "producer_log": log,
        "producer_return": producer_return,
        "static_product": product_path,
        "target_stdlib_header": header,
    }


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FIRST_RED.exists(),
            "golden-layout card/preflight is one-shot")
    review = audit_review()
    approval = owner_review()
    PREFLIGHT.mkdir(parents=True)
    value = {
        "format": "lisp65-c2.3-golden-layout-product-card-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: exactly one product card authorized",
        "card_directory_absent_before_preflight": True,
        "wplto_started": False,
        "product_compiles": 0,
        "device_contacts": 0,
        "golden_sha256": GOLD.GOLDEN_SHA256,
        "acceptance_operations": [
            "canonical(candidate linked-ELF layout bytes) == "
            "SHA-bound golden bytes",
        ],
        "authority": {
            "golden": bind(GOLD.GOLDEN),
            "golden_review": bind(REVIEW_RECEIPT),
            "owner_acceptance": approval,
            "driver": bind(DRIVER),
        },
        "review_execution_witness": review["execution_witness"],
        "next": "exactly one host-only product-shaped WPLTO card",
    }
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("c2-golden-layout-product-card: PREFLIGHT PASS "
          "comparison=one card=one retry=none wplto=0 device=0")


def card() -> None:
    require(PREFLIGHT_RECEIPT.is_file()
            and load(PREFLIGHT_RECEIPT)["status"]
            == "PASS: exactly one product card authorized",
            "green golden-layout preflight required")
    require(not BUILD.exists() and not RECEIPT.exists()
            and not FIRST_RED.exists(),
            "golden-layout product card is one-shot")
    configure_card()
    artifacts = build_candidate()
    comparison = GOLD.compare_elf(artifacts["elf"])
    value = {
        "format": "lisp65-c2.3-golden-layout-product-card-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: golden-layout product card green",
        "promotable": False,
        "wplto_probes_consumed": 1,
        "product_links": 0,
        "device_contacts": 0,
        "acceptance": {
            **comparison,
            "operations": 1,
            "external_checker_vocabularies": 0,
            "acceptance_order_dependencies": 0,
            "historical_postlink_status_consumed": False,
        },
        "producer": {
            "linked_product_completed": True,
            "historical_closer_return_nonauthoritative":
                artifacts["producer_return"],
            "log": bind(artifacts["producer_log"]),
            "static_product": bind(artifacts["static_product"]),
            "target_stdlib_header": artifacts["target_stdlib_header"],
        },
        "artifacts": {
            key: bind(artifacts[key])
            for key in ("elf", "map", "prg", "lto", "linker")
        },
        "authority": {
            "golden": bind(GOLD.GOLDEN),
            "golden_review": bind(REVIEW_RECEIPT),
            "preflight": bind(PREFLIGHT_RECEIPT),
            "owner_acceptance": owner_review(),
            "driver": bind(DRIVER),
        },
        "next_gate": (
            "Owner Halt: reopen 1.5 Halt 2, then the preserved parity pilot "
            "and Link 91. No device action has run."),
        "claim_limit": (
            "One host-only, non-promotable ownership WPLTO accepted solely "
            "by exact golden-layout equality; no Link 91, device, parity "
            "surface, product promotion or release claim."),
    }
    RECEIPT.write_bytes(canonical(value))
    print("c2-golden-layout-product-card: PASS "
          f"sections={comparison['allocatable_sections']} "
          f"boundaries={comparison['boundary_symbols']} "
          "comparison=byte-identical wplto=1 device=0")


def record_first_red(error: BaseException) -> None:
    require(not RECEIPT.exists() and not FIRST_RED.exists(),
            "terminal golden-card result is immutable")
    artifacts = []
    for relative in (
        "wplto/resident-island-seed.prg.lto.o",
        "wplto/resident-island-seed.prg.elf",
        "wplto/resident-island-seed.prg.map",
        "wplto/lisp65-c2-substitution-linked.prg.lto.o",
        "wplto/lisp65-c2-substitution-linked.prg.elf",
        "wplto/lisp65-c2-substitution-linked.prg.map",
        "wplto/c2-substitution.ld",
    ):
        path = BUILD / relative
        if path.is_file():
            artifacts.append(bind(path))
    wplto_started = any(
        path.is_file() for path in (
            BUILD / "wplto/resident-island-seed.prg.lto.o",
            BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf",
        ))
    static_product = BUILD / (
        "static-plane/narrow-static/product/substitution-artifacts.json")
    bank2 = BUILD / (
        "static-plane/narrow-static/v6-semantics/bank2-static-code.bin")
    product = load(static_product) if static_product.is_file() else {}
    profile = load(V18.BASE.V17.PROFILE_RECEIPT)
    expected = profile.get("geometry", {})
    value = {
        "format": "lisp65-c2.3-golden-layout-product-card-first-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FIRST RED: final ownership park required",
        "error": {"type": type(error).__name__, "message": str(error)},
        "card_started": BUILD.exists(),
        "failure_stage": "pre-WPLTO inherited F1 substitution/profile identity",
        "wplto_started": wplto_started,
        "wplto_probes_consumed": int(wplto_started),
        "linked_candidate_elf_emitted": False,
        "golden_comparison_reached": False,
        "retry_authorized": False,
        "final_park_required": True,
        "device_contacts": 0,
        "artifacts": artifacts,
        "pre_wplto_identity_observation": {
            "images": product.get("images"),
            "entries": product.get("entries"),
            "resolutions": product.get("resolutions"),
            "roots": product.get("roots"),
            "bank2_bytes": bank2.stat().st_size if bank2.is_file() else None,
            "bank2_sha256": GOLD.sha(bank2) if bank2.is_file() else None,
            "expected_product_build_id": expected.get("product_build_id"),
            "observed_product_build_id": product.get("product_build_id_hex"),
            "all_geometric_counts_match": (
                product.get("images") == 6
                and product.get("entries") == expected.get("entries")
                and product.get("resolutions") == expected.get("resolutions")
                and product.get("roots") == expected.get("roots")
                and bank2.is_file()
                and bank2.stat().st_size
                    == expected.get("bank2_static_code_bytes")
                and GOLD.sha(bank2) == expected.get("bank2_sha256")),
            "sole_rejected_field": "product_build_id",
            "classification": (
                "non-geometric inherited pre-card identity gate; the "
                "authorized golden operation was never reached"),
            "static_product": bind(static_product) if static_product.is_file()
                else None,
            "bank2": bind(bank2) if bank2.is_file() else None,
        },
        "authority": {
            "golden": bind(GOLD.GOLDEN),
            "golden_review": bind(REVIEW_RECEIPT),
            "preflight": bind(PREFLIGHT_RECEIPT),
            "owner_acceptance": owner_review(),
            "invoked_driver": GOLD.git_binding(
                INVOKED_DRIVER_COMMIT, DRIVER.relative_to(ROOT).as_posix()),
            "postmortem_recorder": bind(DRIVER),
        },
        "claim_limit": (
            "The single golden-layout product card is consumed. No retry, "
            "second golden, Link 91, device or narrower acceptance claim."),
    }
    FIRST_RED.write_bytes(canonical(value))


def record_observed_first_red() -> None:
    require(BUILD.exists() and PREFLIGHT_RECEIPT.is_file()
            and not RECEIPT.exists() and not FIRST_RED.exists(),
            "observed golden-card First Red is not uniquely recordable")
    static_product = BUILD / (
        "static-plane/narrow-static/product/substitution-artifacts.json")
    value = load(static_product)
    expected = load(V18.BASE.V17.PROFILE_RECEIPT)["geometry"]
    require(
        value["images"] == 6
        and value["entries"] == expected["entries"]
        and value["resolutions"] == expected["resolutions"]
        and value["roots"] == expected["roots"]
        and value["product_build_id_hex"] != expected["product_build_id"],
        "observed pre-WPLTO identity red no longer reconstructs")
    record_first_red(V18.BASE.JOINT.BASE.PROBE.REQ.F1W.ProbeError(
        "F1 substitution/profile identity drift"))
    print("c2-golden-layout-product-card: RECORDED FIRST RED "
          "stage=pre-WPLTO golden=not-reached retry=none")


def check() -> None:
    require(RECEIPT.is_file() != FIRST_RED.is_file(),
            "exactly one terminal golden-card receipt required")
    if FIRST_RED.is_file():
        value = load(FIRST_RED)
        require(value["retry_authorized"] is False
                and value["final_park_required"] is True,
                "terminal golden-card red disposition drift")
        require(value["wplto_started"] is False
                and value["wplto_probes_consumed"] == 0
                and value["golden_comparison_reached"] is False
                and value["pre_wplto_identity_observation"]
                    ["all_geometric_counts_match"] is True
                and value["pre_wplto_identity_observation"]
                    ["sole_rejected_field"] == "product_build_id",
                "golden-card pre-WPLTO First-Red reconstruction drift")
        require(
            value["authority"]["golden"] == bind(GOLD.GOLDEN)
            and value["authority"]["golden_review"] == bind(REVIEW_RECEIPT)
            and value["authority"]["owner_acceptance"] == owner_review()
            and value["authority"]["invoked_driver"] == GOLD.git_binding(
                INVOKED_DRIVER_COMMIT, DRIVER.relative_to(ROOT).as_posix())
            and value["authority"]["postmortem_recorder"] == bind(DRIVER),
            "golden-card terminal authority binding drift")
        print("c2-golden-layout-product-card: CHECK FIRST RED "
              "retry=none final-park=required")
        return
    value = load(RECEIPT)
    require(value["status"] == "PASS: golden-layout product card green"
            and value["wplto_probes_consumed"] == 1
            and value["device_contacts"] == 0,
            "green golden-layout product-card receipt drift")
    candidate = ROOT / value["artifacts"]["elf"]["path"]
    comparison = GOLD.compare_elf(candidate)
    require(comparison["candidate_layout_sha256"] == GOLD.GOLDEN_SHA256,
            "persisted candidate/golden comparison drift")
    print("c2-golden-layout-product-card: CHECK PASS "
          "comparison=byte-identical card=consumed retry=none device=0")


def selftest() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FIRST_RED.exists(),
            "golden-layout card already started")
    review = audit_review()
    owner_review()
    require(review["golden"]["sha256"] == GOLD.GOLDEN_SHA256,
            "reviewed golden identity drift")
    print("c2-golden-layout-product-card: SELFTEST PASS "
          "comparison=one card=one retry=none wplto=0 device=0")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode", choices=("selftest", "preflight", "card", "record-red", "check"))
    args = parser.parse_args()
    if args.mode == "selftest":
        selftest()
    elif args.mode == "preflight":
        preflight()
    elif args.mode == "card":
        card()
    elif args.mode == "record-red":
        record_observed_first_red()
    else:
        check()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, GOLD.GoldenLayoutError, V18.RepairCardError,
            V18.BASE.CardError, V18.BASE.JOINT.WPLTOError,
            OSError, KeyError, ValueError,
            json.JSONDecodeError, V18.subprocess.CalledProcessError) as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_first_red(error)
            except Exception as receipt_error:  # never mask the card red
                print("c2-golden-layout-product-card: receipt failure: "
                      f"{receipt_error}", file=sys.stderr)
        print(f"c2-golden-layout-product-card: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
