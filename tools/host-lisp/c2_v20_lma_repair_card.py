#!/usr/bin/env python3
"""Run the sole owner-authorized v2.0 low-resident LMA repair card."""

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
import c2_v17_state_ownership_phase_b as LMA  # noqa: E402
import c2_v20_candidate_media as MEDIA  # noqa: E402
import c2_v20_invariant_golden as INV  # noqa: E402
import c2_v20_invariant_golden_card as PRIOR  # noqa: E402
import c2_v20_ownership_recharter as PRODUCER  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
OWNER_COMMIT = "cf2b489e8041e3d8d7034dc4bfd0bfd053131b54"
BUILD = ROOT / "build/c2.3/v2.0-low-resident-lma-repair-card"
PREFLIGHT = ROOT / "build/c2.3/v2.0-low-resident-lma-repair-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
RECEIPT = EVIDENCE / "c2.3-v2.0-low-resident-lma-repair-card-receipt.json"
FINAL_RED = EVIDENCE / "c2.3-v2.0-low-resident-lma-repair-card-final-red.json"
DRIVER = Path(__file__).resolve()
RECORDED_ON = date.today().isoformat()
FORMAT = "lisp65-c2.3-v20-low-resident-lma-repair-card-v1"


class RepairCardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RepairCardError(message)


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
        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
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


def authorization() -> dict[str, Any]:
    authority = git_bind(OWNER_COMMIT, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{OWNER_COMMIT}:{authority['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode("utf-8").split())
    require(
        "LMA-chain repair authorized" in text
        and "the narrow LMA-chain repair and one new product card" in text
        and "the four sections regain LMA=VMA in the existing resident PRG"
            in text
        and "plus the new delivered-bytes gate" in text,
        "low-resident LMA repair authorization absent")
    return authority


def prior_authority() -> dict[str, Any]:
    card = load(PRIOR.RECEIPT)
    red = load(MEDIA.FIRST_RED)
    require(
        card.get("status")
            == "PASS: owned v1.5 plus F018B candidate satisfies invariant golden"
        and red.get("status")
            == "FIRST-RED: BOOT-CRITICAL-LOW-RESIDENT-SECTIONS-NOT-DELIVERED"
        and len(red.get("mutations_rejected", [])) == 7,
        "green geometry or seven-mutation delivery First Red absent")
    return {
        "green_geometry_card": bind(PRIOR.RECEIPT),
        "delivery_first_red": bind(MEDIA.FIRST_RED),
        "invariant_golden": bind(INV.GOLDEN),
        "invariant_review": bind(INV.RECEIPT),
    }


def expected_delivery_gate(elf: Path, prg: Path) -> dict[str, Any]:
    truth = ElfTruth.read(
        elf, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=True)
    image = prg.read_bytes()
    require(len(image) >= 2, "resident PRG is truncated")
    load_address = int.from_bytes(image[:2], "little")
    rows: list[dict[str, Any]] = []
    for name in PRODUCT.LOW_RESIDENT_LMA_SECTIONS:
        section = truth.section(name)
        expected = truth.section_bytes(name)
        lma = LMA.section_lma(elf, name)
        offset = 2 + section.address - load_address
        inside = (offset >= 2 and offset + len(expected) <= len(image))
        actual = image[offset:offset + len(expected)] if inside else b""
        rows.append({
            "section": name,
            "vma": f"0x{section.address:04x}",
            "lma": f"0x{lma:04x}",
            "bytes": section.bytes,
            "resident_prg_offset": offset if inside else None,
            "elf_bytes_sha256": hashlib.sha256(expected).hexdigest(),
            "resident_prg_bytes_sha256": hashlib.sha256(actual).hexdigest(),
            "lma_equals_vma": lma == section.address,
            "exact_bytes_delivered": inside and actual == expected,
        })
    return {
        "status": "passed",
        "resident_prg": bind(prg),
        "candidate_elf": bind(elf),
        "load_address": f"0x{load_address:04x}",
        "delivery_role": "existing-resident-prg",
        "new_staging_roles": 0,
        "sections": rows,
    }


def validate_delivery_gate(value: dict[str, Any], elf: Path, prg: Path) -> None:
    expected = expected_delivery_gate(elf, prg)
    require(value == expected, "delivered-bytes evidence drift")
    rows = value["sections"]
    require(
        len(rows) == 4
        and [row["section"] for row in rows]
            == list(PRODUCT.LOW_RESIDENT_LMA_SECTIONS)
        and all(row["lma_equals_vma"] for row in rows)
        and all(row["exact_bytes_delivered"] for row in rows)
        and all(row["elf_bytes_sha256"] == row["resident_prg_bytes_sha256"]
                for row in rows)
        and value["new_staging_roles"] == 0,
        "boot-critical bytes are not exact in the existing resident PRG")


def delivery_mutations(value: dict[str, Any], elf: Path, prg: Path) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "drop-section": lambda x: x["sections"].pop(),
        "rewrite-vma": lambda x: x["sections"][0].update(vma="0xb4a4"),
        "rewrite-lma": lambda x: x["sections"][0].update(lma="0x2f4a3"),
        "rewrite-elf-bytes": lambda x: x["sections"][0].update(
            elf_bytes_sha256="0" * 64),
        "rewrite-prg-bytes": lambda x: x["sections"][0].update(
            resident_prg_bytes_sha256="0" * 64),
        "claim-nonexact": lambda x: x["sections"][0].update(
            exact_bytes_delivered=False),
        "replace-resident-role": lambda x: x.update(new_staging_roles=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate_delivery_gate(candidate, elf, prg)
        except RepairCardError:
            rejected.append(name)
    require(rejected == list(cases), "delivered-bytes mutation survived")
    return rejected


def validate_preflight(value: dict[str, Any]) -> None:
    reset_mutations = PRODUCT.low_resident_lma_reset_mutation_selftest()
    require(
        value.get("format")
            == "lisp65-c2.3-v20-low-resident-lma-repair-preflight-v1"
        and value.get("status") == "PASS: one LMA-repair card armed"
        and value.get("execution_accounting") == {
            "cards_consumed": 0, "product_links": 0,
            "wplto_runs": 0, "device_contacts": 0}
        and value.get("authority", {}).get("owner_authorization")
            == authorization()
        and value["authority"].get("prior") == prior_authority()
        and value["authority"].get("product_linker")
            == bind(Path(PRODUCT.__file__).resolve())
        and value["authority"].get("driver") == bind(DRIVER)
        and value.get("repair") == {
            "kind": "explicit-AT-VMA-chain-reset",
            "sections": list(PRODUCT.LOW_RESIDENT_LMA_SECTIONS),
            "new_staging_roles": 0,
            "linker_mutations_rejected": list(reset_mutations),
        }
        and value.get("acceptance") == {
            "fixed": "invariant-golden",
            "derived": "candidate-freight-validation",
            "delivery": "exact-ELF-bytes-in-existing-resident-PRG",
            "delivery_mutations": 7,
            "other_acceptance": 0,
        },
        "LMA-repair preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "detach-authorization": lambda x: x["authority"][
            "owner_authorization"].update(sha256="0" * 64),
        "change-linker": lambda x: x["authority"]["product_linker"].update(
            sha256="0" * 64),
        "add-staging-role": lambda x: x["repair"].update(new_staging_roles=1),
        "drop-section": lambda x: x["repair"]["sections"].pop(),
        "replace-golden": lambda x: x["acceptance"].update(
            fixed="snapshot-layout"),
        "drop-delivery": lambda x: x["acceptance"].update(delivery=None),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate_preflight(candidate)
        except RepairCardError:
            rejected.append(name)
    require(rejected == list(cases), "LMA-repair preflight mutation survived")
    return rejected


def build_preflight() -> dict[str, Any]:
    reset_mutations = PRODUCT.low_resident_lma_reset_mutation_selftest()
    return {
        "format": "lisp65-c2.3-v20-low-resident-lma-repair-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: one LMA-repair card armed",
        "execution_accounting": {
            "cards_consumed": 0, "product_links": 0,
            "wplto_runs": 0, "device_contacts": 0},
        "authority": {
            "owner_authorization": authorization(),
            "prior": prior_authority(),
            "product_linker": bind(Path(PRODUCT.__file__).resolve()),
            "driver": bind(DRIVER),
        },
        "repair": {
            "kind": "explicit-AT-VMA-chain-reset",
            "sections": list(PRODUCT.LOW_RESIDENT_LMA_SECTIONS),
            "new_staging_roles": 0,
            "linker_mutations_rejected": list(reset_mutations),
        },
        "acceptance": {
            "fixed": "invariant-golden",
            "derived": "candidate-freight-validation",
            "delivery": "exact-ELF-bytes-in-existing-resident-PRG",
            "delivery_mutations": 7,
            "other_acceptance": 0,
        },
    }


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "LMA-repair preflight is one-shot")
    value = build_preflight()
    validate_preflight(value)
    value["mutations_rejected"] = preflight_mutations(value)
    PREFLIGHT.mkdir(parents=True)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("2.0 low-resident LMA repair: PREFLIGHT PASS "
          "linker-mutations=7 preflight-mutations=6 cards=0")


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
            "LMA-repair preflight mutation receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "LMA-repair product card is one-shot")
    INVOCATION.write_bytes(canonical({
        "format": "lisp65-c2.3-v20-low-resident-lma-repair-invocation-v1",
        "recorded_on": RECORDED_ON,
        "status": "INVOKED: terminal outcome required",
        "authorization": authorization(),
        "preflight": bind(PREFLIGHT_RECEIPT),
        "driver": bind(DRIVER),
    }))
    artifacts = produce_candidate()
    linker_gate = PRODUCT.low_resident_lma_reset_gate(
        artifacts["linker"].read_text(encoding="utf-8"))
    comparison = INV.compare_elf(artifacts["elf"])
    delivery = expected_delivery_gate(artifacts["elf"], artifacts["prg"])
    validate_delivery_gate(delivery, artifacts["elf"], artifacts["prg"])
    rejected = delivery_mutations(delivery, artifacts["elf"], artifacts["prg"])
    receipt = {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "PASS: invariant geometry and resident delivery exact",
        "attempt_accounting": {
            "cards_authorized": 1, "cards_consumed": 1,
            "wplto_runs": 1, "product_link_attempts": 1,
            "device_contacts": 0},
        "acceptance": {
            "invariant_golden": comparison,
            "low_resident_linker_reset": linker_gate,
            "delivered_bytes": delivery,
            "delivery_mutations_rejected": rejected,
            "operations": 2,
            "other_acceptance_operations": 0,
        },
        "artifacts": {key: bind(artifacts[key]) for key in (
            "elf", "prg", "map", "lto", "linker")},
        "authority": {
            "owner_authorization": authorization(),
            "preflight": bind(PREFLIGHT_RECEIPT),
            "invocation": bind(INVOCATION),
            "driver": bind(DRIVER),
            "invariant_golden": bind(INV.GOLDEN),
        },
        "next_gate": (
            "Regenerate current-world media closure and loudly retire the "
            "Link-97 closure before D1-D5."),
        "claim_limit": (
            "One host-only replacement card; no media, device, release, "
            "publication or parity claim."),
    }
    RECEIPT.write_bytes(canonical(receipt))
    print("2.0 low-resident LMA repair card: PASS "
          "sections=4 exact-bytes=4 mutations=7 wplto=1 device=0")


def record_final_red(error: BaseException) -> None:
    require(not RECEIPT.exists() and not FINAL_RED.exists(),
            "LMA-repair terminal result is immutable")
    artifacts: dict[str, dict[str, Any]] = {}
    for name, relative in {
        "elf": "wplto/lisp65-c2-substitution-linked.prg.elf",
        "prg": "wplto/lisp65-c2-substitution-linked.prg",
        "map": "wplto/lisp65-c2-substitution-linked.prg.map",
        "lto": "wplto/resident-island-seed.prg.lto.o",
        "linker": "wplto/c2-substitution.ld",
        "producer_log": "receipts/v20-producer.log",
    }.items():
        path = BUILD / relative
        if path.is_file():
            artifacts[name] = bind(path)
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v20-low-resident-lma-repair-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: LMA-repair card returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {
            "cards_authorized": 1, "cards_consumed": 1,
            "wplto_runs": int((BUILD / "wplto").exists()),
            "product_link_attempts": int((BUILD / "wplto").exists()),
            "device_contacts": 0},
        "retry_authorized": False,
        "owner_disposition_required": True,
        "artifacts": artifacts,
        "authority": {
            "owner_authorization": authorization(),
            "preflight": bind(PREFLIGHT_RECEIPT),
            "invocation": bind(INVOCATION),
            "driver": bind(DRIVER),
        },
        "claim_limit": "The sole authorized replacement card is consumed.",
    }))


def selftest() -> None:
    authorization(); prior_authority()
    require(len(PRODUCT.low_resident_lma_reset_mutation_selftest()) == 7,
            "LMA-reset mutation count drift")
    print("2.0 low-resident LMA repair: SELFTEST PASS "
          "linker-mutations=7 delivery-mutations=7")


def check() -> None:
    selftest()
    require(not (RECEIPT.exists() and FINAL_RED.exists()),
            "LMA-repair card has two terminal outcomes")
    if FINAL_RED.exists():
        red = load(FINAL_RED)
        require(red.get("retry_authorized") is False
                and red.get("owner_disposition_required") is True,
                "LMA-repair final-red disposition drift")
        print("2.0 low-resident LMA repair: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        print("2.0 low-resident LMA repair: CHECK ARMED card=unused")
        return
    value = load(RECEIPT)
    require(value.get("status")
            == "PASS: invariant geometry and resident delivery exact"
            and value.get("attempt_accounting", {}).get("cards_consumed") == 1,
            "green LMA-repair receipt drift")
    artifacts = value["artifacts"]
    for role in ("elf", "prg", "map", "lto", "linker"):
        require(artifacts[role] == bind(ROOT / artifacts[role]["path"]),
                f"LMA-repair artifact drift: {role}")
    elf = ROOT / artifacts["elf"]["path"]
    prg = ROOT / artifacts["prg"]["path"]
    comparison = value["acceptance"]["invariant_golden"]
    require(INV.compare_elf(elf) == comparison,
            "persisted invariant-golden comparison drift")
    delivery = value["acceptance"]["delivered_bytes"]
    validate_delivery_gate(delivery, elf, prg)
    require(value["acceptance"]["delivery_mutations_rejected"]
            == delivery_mutations(delivery, elf, prg),
            "persisted delivered-bytes mutation set drift")
    linker = ROOT / artifacts["linker"]["path"]
    require(PRODUCT.low_resident_lma_reset_gate(
                linker.read_text(encoding="utf-8"))
            == value["acceptance"]["low_resident_linker_reset"],
            "persisted linker LMA reset drift")
    print("2.0 low-resident LMA repair: CHECK PASS "
          "golden=green delivered=4/4")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("selftest", "preflight", "card", "check"))
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
                print("2.0 low-resident LMA repair: receipt failure: "
                      f"{receipt_error}", file=sys.stderr)
        print(f"2.0 low-resident LMA repair: FINAL RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
