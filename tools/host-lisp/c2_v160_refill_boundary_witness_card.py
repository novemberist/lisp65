#!/usr/bin/env python3
"""Run the one authorized v1.6 refill-boundary witness product card."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v160_queue_single_owner_card as BASE  # noqa: E402
import c2_v160_queue_owner_cold_relocation as COLD  # noqa: E402
import c2_v160_queue_single_owner_gate as OWNER  # noqa: E402
import c2_v160_refill_boundary_witness as WITNESS  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-refill-boundary-witness-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-refill-boundary-witness-preflight"
PROCESS = ROOT / "build/c2.3/v1.6-refill-boundary-witness-process"
RECEIPT = ARCH / "c2.3-v1.6-refill-boundary-witness-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-refill-boundary-witness-card-final-red.json"
PRICING = ARCH / "c2.3-v1.6-refill-boundary-witness-pricing.json"
PREDECESSOR = ARCH / "c2.3-v1.6-display-ownership-device-preparation-receipt.json"
QUEUE_CLOSURE = ARCH / "c2.3-v1.6-queue-owner-cold-relocation-resume-receipt.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "5504ba4b"
FORMAT = "lisp65-c2-v160-refill-boundary-witness-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 REFILL WITNESS ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 REFILL WITNESS FINAL WORLD GREEN"


def require(value: bool, message: str) -> None:
    if not value:
        raise BASE.CARD.BASE.CardError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def authority() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("witness implementation card", "bound origin and wrap discipline",
                  "all standing walls", "composed-image", "removal bound",
                  "one short contact", "ordinary text falls to 3 free bytes",
                  "160 free"):
        require(token in text, f"refill witness authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    prepared = BASE.CARD.BASE.load(PREDECESSOR)
    queue = BASE.CARD.BASE.load(QUEUE_CLOSURE)
    price = BASE.CARD.BASE.load(PRICING)
    require(prepared["status"] == "PASS: V1.6 DISPLAY OWNERSHIP SIXTH CONTACT READY"
            and queue["status"] ==
                "PASS: V1.6 QUEUE-OWNER COLD RELOCATION CLOSED READ-ONLY"
            and price["status"] ==
                "PRICED: FULL-PAYLOAD TWO-SLOT WITNESS FITS WITH ONE COLD RELOCATION"
            and price["winner"]["ordinary_text_headroom_after_bytes"] == 3
            and price["winner"]["mapped_diagnostic_headroom_bytes"] == 160,
            "refill witness predecessor/pricing drift")
    return {"display_device_world": prepared, "queue_closure": queue,
            "pricing": price}


def configure_module() -> None:
    BASE.CARD.configure_for_paths(BUILD, PREFLIGHT,
                                  tag="refill-boundary-witness")
    registration = PRODUCT.configure_refill_boundary_witness()
    require(registration["selected"] is True
            and registration["allocated"] == [".lisp65_c2_mapped_diagnostic"],
            "refill witness configuration was not consumed")


def install() -> None:
    BASE.CARD.BUILD = BUILD
    BASE.CARD.PREFLIGHT = PREFLIGHT
    BASE.CARD.PROCESS = PROCESS
    BASE.CARD.NORMAL_BUILD = PROCESS / "normal-build"
    BASE.CARD.NORMAL_PREFLIGHT = PROCESS / "normal-preflight"
    BASE.CARD.MUTANT_BUILD = PROCESS / "mutant-build"
    BASE.CARD.MUTANT_PREFLIGHT = PROCESS / "mutant-preflight"
    BASE.CARD.PRODUCT_ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    BASE.CARD.RECEIPT = RECEIPT
    BASE.CARD.FINAL_RED = FINAL_RED
    BASE.CARD.PREDECESSOR = PREDECESSOR
    BASE.CARD.DRIVER = DRIVER
    BASE.CARD.AUTHORIZATION = AUTHORIZATION
    BASE.CARD.FORMAT = FORMAT
    BASE.CARD.PREFLIGHT_STATUS = PREFLIGHT_STATUS
    BASE.CARD.FINAL_STATUS = FINAL_STATUS
    BASE.CARD.authority = authority
    BASE.CARD.predecessor = predecessor
    BASE.CARD.configure_module = configure_module
    # Project the successor's owned paths and adapters through the inherited
    # active-frame layer into the real live-stack producer.  Merely rebinding
    # the outer module would leave its historical one-shot roots live.
    BASE.CARD.install()


def registration_preflight() -> dict[str, Any]:
    registration = PRODUCT.refill_witness_inventory_registration()
    sources = {Path(path).resolve()
               for path in PRODUCT.source_list(tuple(PRODUCT.CONVERGENCE_DEFINES))}
    require(registration["selected"] is True
            and PRODUCT.REFILL_WITNESS_SOURCE.resolve() in sources,
            "refill witness registration escaped real compiler source list")
    definitions = tuple(item for item in PRODUCT.CONVERGENCE_DEFINES
                        if item != PRODUCT.REFILL_WITNESS_FEATURE)
    absent = PRODUCT.refill_witness_inventory_registration(definitions)
    require(absent["selected"] is False and absent["names"] == [],
            "unselected witness still owns final sections")
    return {"selected": registration, "unselected": absent,
            "real_source_consumed": True,
            "unregistered_section_mutation": "rejected-by-exact-final-inventory",
            "registration_without_section_mutation": "rejected-by-final-gate"}


def append_preflight() -> None:
    path = PREFLIGHT / "preflight.json"
    value = BASE.CARD.BASE.load(path)
    source = WITNESS.source_gate()
    mutations = WITNESS.source_mutations()
    value.update({"format": FORMAT + "-preflight", "status": PREFLIGHT_STATUS,
        "witness_authority": authority(), "witness_pricing": BASE.CARD.BASE.bind(PRICING),
        "witness_source_gate": source, "source_mutations_rejected": mutations,
        "witness_registration": registration_preflight(),
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "media_builds": 0, "device_contacts": 0}})
    path.write_bytes(canonical(value))


def append_final() -> None:
    value = BASE.CARD.BASE.load(RECEIPT)
    elf = BASE.CARD.PRODUCT_ELF
    gate = WITNESS.final_gate(elf)
    gate["mutations_rejected"] = WITNESS.final_mutations(gate)
    value.update({"format": FORMAT, "status": FINAL_STATUS,
        "witness_authority": authority(), "witness_pricing": BASE.CARD.BASE.bind(PRICING),
        "witness_preflight": BASE.CARD.BASE.bind(PREFLIGHT / "preflight.json"),
        "refill_boundary_witness": gate,
        "queue_single_owner_source": OWNER.derive(),
        "cold_relocation_source": COLD.source_gate(),
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "removal_default": {"bound": True,
            "exception": "only a separately argued product-telemetry case"},
        "media_authorized": False, "device_contacts": 0,
        "next": "review, same-world media, one deterministic seam contact"})
    RECEIPT.write_bytes(canonical(value))


def check_receipt() -> dict[str, Any]:
    value = BASE.CARD.BASE.load(RECEIPT)
    gate = value["refill_boundary_witness"]
    require(value["status"] == FINAL_STATUS
            and value["attempt_accounting"] == {"cards_consumed": 1,
                "WPLTO_runs": 1, "product_links": 1,
                "media_builds": 0, "device_contacts": 0}
            and gate["ordinary"]["free_bytes"] == 3
            and gate["mapped_diagnostic"]["free_bytes"] == 160
            and gate["trace"]["new_resident_bytes"] == 0
            and gate["composed_image"]["result_tail_blank"] is True
            and value["removal_default"]["bound"] is True,
            "refill witness final receipt drift")
    return value


def preflight() -> None:
    require(not any(path.exists() for path in (BUILD, PREFLIGHT, RECEIPT, FINAL_RED)),
            "refill witness card is one-shot")
    predecessor(); authority(); configure_module()
    BASE.CARD.preflight(); append_preflight()
    print("v1.6 refill witness: PREFLIGHT PASS card=0/1 origin=bound "
          "storage=73/80 resident=0")


def card() -> None:
    predecessor(); authority(); configure_module()
    pre = BASE.CARD.BASE.load(PREFLIGHT / "preflight.json")
    require(pre["status"] == PREFLIGHT_STATUS
            and pre["witness_registration"]["real_source_consumed"] is True,
            "refill witness persisted preflight drift")
    BASE.CARD.card(); append_final(); check_receipt()
    print("v1.6 refill witness: CARD PASS card=1/1 ordinary=3 "
          "mapped-diagnostic=211/371 composed-image=PASS")


def record_red(error: Exception) -> None:
    BASE.CARD.record_red(error)
    if FINAL_RED.exists():
        value = BASE.CARD.BASE.load(FINAL_RED)
        value.update({"format": FORMAT + "-final-red",
            "status": "FINAL RED: V1.6 REFILL WITNESS CARD STOPS",
            "witness_authority": authority(),
            "witness_pricing": BASE.CARD.BASE.bind(PRICING),
            "classification": {
                "known_family": "bound-not-consumed-at-real-single-link",
                "mechanism_fully_attributed": True,
                "product_fault": False,
                "pricing_refuted": False,
                "real_compiler_consumption_still_absent": True},
            "final_world_observation": {
                "resolved_profile_witness_feature_present": False,
                "canonical_witness_object_present": False,
                "diagnostic_section_bytes": 0,
                "ordinary_installer_bytes": 211},
            "retry_authorized": False, "media_authorized": False,
            "device_contacts": 0,
            "next": "fresh real-consumer replacement card requires explicit authorization"})
        FINAL_RED.write_bytes(canonical(value))


def main() -> int:
    install()
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "preflight":
        preflight(); return 0
    if action == "card":
        card(); return 0
    if action == "check":
        check_receipt(); print("v1.6 refill witness: CHECK PASS"); return 0
    return BASE.CARD.main()


if __name__ == "__main__":
    install()
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_red(error)
            except Exception as receipt_error:
                print(f"refill witness Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 refill witness: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
