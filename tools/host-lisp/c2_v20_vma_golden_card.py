#!/usr/bin/env python3
"""Run the sole reviewer-authorized 2.0 VMA-golden product card."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
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

import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v20_invariant_golden_card as HISTORICAL_CARD  # noqa: E402
import c2_v20_lma_repair_card as LMA_CARD  # noqa: E402
import c2_v20_ownership_recharter as PRODUCER  # noqa: E402
import c2_v20_vma_invariant_golden as INV  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
OWNER_COMMIT = "df944cde5f7cd6160db826bafbc7259fe52cb748"
BUILD = ROOT / "build/c2.3/v2.0-vma-golden-card"
PREFLIGHT = ROOT / "build/c2.3/v2.0-vma-golden-card-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
RECEIPT = EVIDENCE / "c2.3-v2.0-vma-golden-card-receipt.json"
FINAL_RED = EVIDENCE / "c2.3-v2.0-vma-golden-card-final-red.json"
DRIVER = Path(__file__).resolve()
RECORDED_ON = date.today().isoformat()
FORMAT = "lisp65-c2.3-v20-vma-golden-card-v1"


class VmaGoldenCardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise VmaGoldenCardError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"regular JSON authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"regular artifact absent: {path}")
    raw = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{relative}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {
        "authority": "git-blob", "commit": commit, "path": relative,
        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
    }


def reviewer_acceptance() -> dict[str, Any]:
    authority = git_bind(OWNER_COMMIT, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{OWNER_COMMIT}:{authority['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode("utf-8").split())
    require(
        "One-time VMA-golden review" in text
        and "ACCEPTED" in text
        and "review_accepted flips true" in text
        and "Exactly one card is authorized" in text
        and "15 golden/candidate and 4 closer mutations green" in text,
        "one-time VMA-golden reviewer acceptance is absent")
    review = load(INV.RECEIPT)
    require(
        review.get("status")
            == "PASS: awaiting one-time reviewer VMA-golden review"
        and review.get("card_lock") == {
            "review_accepted": False,
            "card_authorized_by_this_receipt": False,
            "wplto_allowed": False,
        }
        and review.get("vma_invariant_golden", {}).get("sha256")
            == INV.GOLDEN_SHA256,
        "review package is not the locked package accepted by the reviewer")
    return {
        "reviewer_commit": authority,
        "review_package": bind(INV.RECEIPT),
        "VMA_golden": bind(INV.GOLDEN),
        "accepted_card_count": 1,
    }


def prior_authority() -> dict[str, Any]:
    red = load(LMA_CARD.FINAL_RED)
    historical = load(HISTORICAL_CARD.RECEIPT)
    require(
        red.get("status") == "FINAL RED: LMA-repair card returns to owner"
        and red.get("retry_authorized") is False
        and historical.get("status")
            == "PASS: owned v1.5 plus F018B candidate satisfies invariant golden",
        "prior green geometry or terminal LMA-repair evidence is absent")
    return {
        "historical_green_geometry_card": bind(HISTORICAL_CARD.RECEIPT),
        "LMA_repair_final_red": bind(LMA_CARD.FINAL_RED),
        "VMA_golden_review": bind(INV.RECEIPT),
    }


def acceptance_contract() -> dict[str, Any]:
    return {
        "fixed_authority": "VMA-only-invariant-golden-v3",
        "candidate_derived": [
            "section-sizes-against-fixed-capacity-arenas",
            "numeric-LMAs-complete-and-non-overlapping",
            "overlay-end-from-candidate-section-extent",
        ],
        "delivery": "four-low-resident-sections-exact-in-resident-PRG",
        "delivery_mutations": 7,
        "mechanical_completion": "producer-owned-not-an-acceptance-operation",
        "historical_qualifiers": 0,
    }


def validate_preflight(value: dict[str, Any]) -> None:
    require(
        value.get("format") == "lisp65-c2.3-v20-vma-golden-preflight-v1"
        and value.get("status") == "PASS: exactly one VMA-golden card armed"
        and value.get("execution_accounting") == {
            "cards_consumed": 0,
            "product_links": 0,
            "wplto_runs": 0,
            "device_contacts": 0,
        }
        and value.get("authority", {}).get("reviewer_acceptance")
            == reviewer_acceptance()
        and value["authority"].get("prior") == prior_authority()
        and value["authority"].get("producer")
            == bind(Path(PRODUCER.__file__).resolve())
        and value["authority"].get("product_linker")
            == bind(Path(PRODUCT.__file__).resolve())
        and value["authority"].get("driver") == bind(DRIVER)
        and value.get("producer_configuration") == {
            "full_map_ownership": True,
            "low_resident_LMA_reset": True,
            "new_staging_roles": 0,
        }
        and value.get("acceptance") == acceptance_contract(),
        "VMA-golden card preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "detach-review": lambda x: x["authority"][
            "reviewer_acceptance"]["reviewer_commit"].update(sha256="0" * 64),
        "replace-golden": lambda x: x["authority"][
            "reviewer_acceptance"]["VMA_golden"].update(sha256="0" * 64),
        "change-producer": lambda x: x["authority"]["producer"].update(
            sha256="0" * 64),
        "drop-LMA-reset": lambda x: x["producer_configuration"].update(
            low_resident_LMA_reset=False),
        "add-staging-role": lambda x: x["producer_configuration"].update(
            new_staging_roles=1),
        "add-historical-qualifier": lambda x: x["acceptance"].update(
            historical_qualifiers=1),
        "make-completion-acceptor": lambda x: x["acceptance"].update(
            mechanical_completion="acceptance-operation"),
        "authorize-two-cards": lambda x: x["authority"][
            "reviewer_acceptance"].update(accepted_card_count=2),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate_preflight(candidate)
        except VmaGoldenCardError:
            rejected.append(name)
    require(rejected == list(cases), "VMA-golden preflight mutation survived")
    return rejected


def build_preflight() -> dict[str, Any]:
    return {
        "format": "lisp65-c2.3-v20-vma-golden-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: exactly one VMA-golden card armed",
        "execution_accounting": {
            "cards_consumed": 0,
            "product_links": 0,
            "wplto_runs": 0,
            "device_contacts": 0,
        },
        "authority": {
            "reviewer_acceptance": reviewer_acceptance(),
            "prior": prior_authority(),
            "producer": bind(Path(PRODUCER.__file__).resolve()),
            "product_linker": bind(Path(PRODUCT.__file__).resolve()),
            "driver": bind(DRIVER),
        },
        "producer_configuration": {
            "full_map_ownership": True,
            "low_resident_LMA_reset": True,
            "new_staging_roles": 0,
        },
        "acceptance": acceptance_contract(),
    }


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "VMA-golden preflight/card is one-shot")
    value = build_preflight()
    validate_preflight(value)
    value["mutations_rejected"] = preflight_mutations(value)
    PREFLIGHT.mkdir(parents=True)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("2.0 VMA-golden card: PREFLIGHT PASS "
          "mutations=8 cards=0 wplto=0 device=0")


def produce_candidate() -> dict[str, Any]:
    PRODUCER.BUILD = BUILD
    PRODUCER.FINAL_RED = BUILD / "producer-internal-first-red.json"
    PRODUCT.configure_full_map_ownership()
    PRODUCT.configure_low_resident_lma_reset()
    return PRODUCER.produce_candidate()


def card() -> None:
    value = load(PREFLIGHT_RECEIPT)
    mutations = value.pop("mutations_rejected", None)
    validate_preflight(value)
    require(mutations == preflight_mutations(value),
            "VMA-golden preflight mutation receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "VMA-golden product card is one-shot")
    INVOCATION.write_bytes(canonical({
        "format": "lisp65-c2.3-v20-vma-golden-invocation-v1",
        "recorded_on": RECORDED_ON,
        "status": "INVOKED: terminal outcome required",
        "reviewer_acceptance": reviewer_acceptance(),
        "preflight": bind(PREFLIGHT_RECEIPT),
        "driver": bind(DRIVER),
    }))
    artifacts = produce_candidate()
    comparison = INV.compare_elf(artifacts["elf"])
    delivery = LMA_CARD.expected_delivery_gate(
        artifacts["elf"], artifacts["prg"])
    LMA_CARD.validate_delivery_gate(
        delivery, artifacts["elf"], artifacts["prg"])
    delivery_rejected = LMA_CARD.delivery_mutations(
        delivery, artifacts["elf"], artifacts["prg"])
    headroom = {
        row["id"]: row["candidate_headroom_bytes"]
        for row in comparison["capacity_measurements"]}
    receipt = {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "PASS: VMA geometry, candidate freight and delivery exact",
        "attempt_accounting": {
            "cards_authorized": 1,
            "cards_consumed": 1,
            "wplto_runs": 1,
            "product_link_attempts": 1,
            "device_contacts": 0,
        },
        "acceptance": {
            "VMA_golden": comparison,
            "delivered_bytes": delivery,
            "delivery_mutations_rejected": delivery_rejected,
            "fixed_comparison_operations": 1,
            "candidate_derived_validation": True,
            "delivery_operations": 1,
            "historical_qualifiers": 0,
        },
        "producer": {
            "mechanical_completion_only": True,
            "historical_return_nonauthoritative": artifacts["producer_return"],
            "log": bind(artifacts["producer_log"]),
            "resolved_profile": bind(artifacts["resolved_profile"]),
            "target_stdlib_header": artifacts["target_stdlib_header"],
        },
        "artifacts": {
            key: bind(artifacts[key])
            for key in ("elf", "prg", "map", "lto", "linker")},
        "authority": {
            "reviewer_acceptance": reviewer_acceptance(),
            "preflight": bind(PREFLIGHT_RECEIPT),
            "invocation": bind(INVOCATION),
            "driver": bind(DRIVER),
            "VMA_golden": bind(INV.GOLDEN),
        },
        "narrow_margins_are_not_budgets": {
            "ordinary_chain": headroom["low-resident-and-ordinary-chain"],
            "runtime_overlay": headroom["runtime-overlay-slices"],
            "bank0_state": headroom["owned-bank0-state"],
        },
        "next_gate": (
            "Regenerate the current-world media closure and loudly retire "
            "the Link-97 closure before the D1-D5 session."),
        "claim_limit": (
            "One host-only card.  No media, device, release, publication "
            "or parity claim."),
    }
    RECEIPT.write_bytes(canonical(receipt))
    print("2.0 VMA-golden card: PASS "
          f"sections={comparison['allocatable_sections']} "
          f"boundaries={comparison['fixed_boundary_symbols']} "
          "delivery=4/4 "
          f"margins={headroom['low-resident-and-ordinary-chain']}/"
          f"{headroom['runtime-overlay-slices']}/"
          f"{headroom['owned-bank0-state']} wplto=1 device=0")


def record_final_red(error: BaseException) -> None:
    require(not RECEIPT.exists() and not FINAL_RED.exists(),
            "VMA-golden terminal result is immutable")
    artifacts: dict[str, dict[str, Any]] = {}
    for name, relative in {
        "elf": "wplto/lisp65-c2-substitution-linked.prg.elf",
        "prg": "wplto/lisp65-c2-substitution-linked.prg",
        "map": "wplto/lisp65-c2-substitution-linked.prg.map",
        "lto": "wplto/resident-island-seed.prg.lto.o",
        "linker": "wplto/c2-substitution.ld",
        "resolved_profile": "wplto/resolved-profile.txt",
        "producer_log": "receipts/v20-producer.log",
        "producer_first_red": "producer-internal-first-red.json",
    }.items():
        path = BUILD / relative
        if path.is_file():
            artifacts[name] = bind(path)
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v20-vma-golden-card-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: sole VMA-golden card returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {
            "cards_authorized": 1,
            "cards_consumed": 1,
            "wplto_runs": int((BUILD / "wplto").exists()),
            "product_link_attempts": int((BUILD / "wplto").exists()),
            "device_contacts": 0,
        },
        "retry_authorized": False,
        "owner_disposition_required": True,
        "artifacts": artifacts,
        "authority": {
            "reviewer_acceptance": reviewer_acceptance(),
            "preflight": bind(PREFLIGHT_RECEIPT),
            "invocation": bind(INVOCATION),
            "driver": bind(DRIVER),
        },
        "claim_limit": "The sole authorized VMA-golden card is consumed.",
    }))


def selftest() -> None:
    reviewer_acceptance()
    prior_authority()
    INV.selftest()
    require(len(PRODUCT.low_resident_lma_reset_mutation_selftest()) == 7,
            "LMA-reset mutation count drift")
    require(len(PRODUCT._kernal_crc_call_binding_model_selftest()) == 4,
            "closer CRC mutation count drift")
    print("2.0 VMA-golden card: SELFTEST PASS "
          "golden=VMA-only preflight-mutations=8 card=one")


def check() -> None:
    selftest()
    require(not (RECEIPT.exists() and FINAL_RED.exists()),
            "VMA-golden card has two terminal outcomes")
    if FINAL_RED.exists():
        red = load(FINAL_RED)
        require(red.get("retry_authorized") is False
                and red.get("owner_disposition_required") is True,
                "VMA-golden Final-Red disposition drift")
        print("2.0 VMA-golden card: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        print("2.0 VMA-golden card: CHECK ARMED card=unused")
        return
    value = load(RECEIPT)
    require(
        value.get("status")
            == "PASS: VMA geometry, candidate freight and delivery exact"
        and value.get("attempt_accounting", {}).get("cards_consumed") == 1,
        "green VMA-golden card receipt drift")
    for role in ("elf", "prg", "map", "lto", "linker"):
        require(value["artifacts"][role]
                == bind(ROOT / value["artifacts"][role]["path"]),
                f"VMA-golden card artifact drift: {role}")
    elf = ROOT / value["artifacts"]["elf"]["path"]
    prg = ROOT / value["artifacts"]["prg"]["path"]
    require(value["acceptance"]["VMA_golden"] == INV.compare_elf(elf),
            "persisted VMA-golden comparison drift")
    delivery = value["acceptance"]["delivered_bytes"]
    LMA_CARD.validate_delivery_gate(delivery, elf, prg)
    require(value["acceptance"]["delivery_mutations_rejected"]
            == LMA_CARD.delivery_mutations(delivery, elf, prg),
            "persisted delivered-bytes mutation closure drift")
    print("2.0 VMA-golden card: CHECK PASS "
          "golden=green delivery=4/4 wplto=1 device=0")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("selftest", "preflight", "card", "check"))
    action = parser.parse_args().action
    {"selftest": selftest, "preflight": preflight,
     "card": card, "check": check}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_final_red(error)
            except Exception as receipt_error:
                print("2.0 VMA-golden card: receipt failure: "
                      f"{receipt_error}", file=sys.stderr)
        print(f"2.0 VMA-golden card: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
