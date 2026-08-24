#!/usr/bin/env python3
"""Repair the missing shipped far facade and prepare replacement trace media."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_refill_boundary_witness_device_preparation as RED  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


BASE = RED.BASE
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-refill-boundary-witness-media-repair-replacement"
RECEIPT = ARCH / "c2.3-v1.6-refill-boundary-witness-media-repair-receipt.json"
SESSION = ROOT / "config/c2-v160-refill-boundary-witness-media-repair-session.json"
RED_RECEIPT = RED.RECEIPT
AUTHORIZATION = "fb149737"
PRODUCT_REMOTE = "V16WFR.D81"
LIBRARY_REMOTE = "V16WLR.D81"
FACADE_SECTION = ".lisp65_c2_mapped_far_facade"
FACADE_BYTES = 98


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


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


def authority() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("the medium never had the facade", "from elftruth",
                  "final packed prg", "artifact-only replacement media",
                  "claim chain ends at the shipped byte"):
        require(token in text, f"facade-repair authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def facade_truth(elf: Path) -> tuple[int, bytes]:
    truth = ElfTruth.read(
        elf, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=True)
    section = truth.section(FACADE_SECTION)
    raw = truth.section_bytes(FACADE_SECTION)
    require(section.bytes == len(raw) == FACADE_BYTES,
            "linked far-facade geometry drift")
    return section.address, raw


def prg_span(product: Path, address: int, count: int) -> tuple[bytearray, int]:
    raw = bytearray(product.read_bytes())
    require(len(raw) >= 2, "resident PRG lacks load address")
    load = int.from_bytes(raw[:2], "little")
    offset = 2 + address - load
    require(2 <= offset and offset + count <= len(raw),
            "far facade lies outside resident PRG")
    return raw, offset


def packed_facade_gate(product: Path, elf: Path) -> dict[str, Any]:
    address, expected = facade_truth(elf)
    raw, offset = prg_span(product, address, len(expected))
    observed = bytes(raw[offset:offset + len(expected)])
    require(observed == expected,
            "shipped-byte facade differs from final ELF")
    return {
        "status": "passed-packed-prg-facade-byte-equals-final-elf",
        "section": FACADE_SECTION,
        "address": address,
        "bytes": len(expected),
        "file_offset": offset,
        "sha256": hashlib.sha256(expected).hexdigest(),
        "source": "ElfTruth(final linked ELF)",
        "consumer": "final packed resident PRG",
    }


def materialize_facade(product: Path, elf: Path, out: Path) -> dict[str, Any]:
    address, expected = facade_truth(elf)
    raw, offset = prg_span(product, address, len(expected))
    before = bytes(raw[offset:offset + len(expected)])
    require(before == bytes(len(expected)),
            "seed facade is neither the attributed null span nor final truth")
    before_sha = hashlib.sha256(raw).hexdigest()
    raw[offset:offset + len(expected)] = expected
    product.write_bytes(raw)
    report = packed_facade_gate(product, elf)
    report.update({
        "format": "lisp65-v1.6-packed-facade-materialization-v1",
        "before": {"classification": "all-zero-seed-span",
                   "sha256": hashlib.sha256(before).hexdigest()},
        "before_product_sha256": before_sha,
        "after_product_sha256": hashlib.sha256(raw).hexdigest(),
        "changed_bytes": sum(a != b for a, b in zip(before, expected)),
    })
    out.write_bytes(canonical(report))
    return report


def materialize_publish_predecessors(final: Path, product: Path,
                                     elf: Path) -> dict[str, Any]:
    """Put the facade before both existing publish-last mutations.

    The frozen WPLTO remains evidence. Completion owns these copies, so its
    unbound predecessor and its KERNAL-bound product receive the same
    ELF-derived facade before the verifier table is published. The KERNAL
    receipt's identities are derived values and rebind only in this owned
    world; its two-byte mutation domain and payload remain unchanged.
    """
    unbound = final / "lisp65-c2-substitution-unbound.prg"
    receipt_path = final / "kernal-window-publish-last.json"
    require(unbound.is_file() and receipt_path.is_file(),
            "Completion publish-last predecessors are absent")
    prior_receipt_raw = receipt_path.read_bytes()
    prior = load(receipt_path)
    prior_unbound = bind(unbound)
    prior_window = bind(product)
    unbound_report = materialize_facade(
        unbound, elf, final / "packed-prg-unbound-facade-materialization.json")
    window_report = materialize_facade(
        product, elf, final / "packed-prg-facade-materialization.json")

    operands = prior.get("binding_operands")
    require(isinstance(operands, list) and len(operands) == 2,
            "KERNAL publish-last operand inventory drift")
    before = unbound.read_bytes()
    after = product.read_bytes()
    allowed: set[int] = set()
    for operand in operands:
        offset = int(operand["file_offset"])
        require(after[offset] == int(operand["published_value"]),
                f"KERNAL operand content drift: {operand['name']}")
        allowed.add(offset)
    changed = {index for index, pair in enumerate(zip(before, after))
               if pair[0] != pair[1]}
    require(changed == allowed,
            "facade predecessor escaped the original two-byte KERNAL domain")

    prior["unbound_product_sha256"] = hashlib.sha256(before).hexdigest()
    prior["window_bound_product_sha256"] = hashlib.sha256(after).hexdigest()
    prior["completion_facade_predecessor"] = {
        "authority": AUTHORIZATION,
        "source": FACADE_SECTION,
        "bytes": FACADE_BYTES,
        "frozen_receipt_sha256": hashlib.sha256(prior_receipt_raw).hexdigest(),
        "frozen_unbound": prior_unbound,
        "frozen_window_bound": prior_window,
        "completion_unbound_sha256": prior["unbound_product_sha256"],
        "completion_window_bound_sha256": prior["window_bound_product_sha256"],
        "rule": "facade precedes KERNAL and verifier publish-last",
    }
    receipt_path.write_bytes(canonical(prior))
    report = {
        "format": "lisp65-v1.6-facade-publish-predecessor-rebind-v1",
        "status": "passed-completion-owned-predecessors-only",
        "unbound": unbound_report,
        "window_bound": window_report,
        "kernal_changed_offsets": sorted(changed),
        "kernal_declared_domain_bytes": len(allowed),
        "frozen_wplto_unchanged": True,
    }
    (final / "packed-prg-facade-predecessor-rebind.json").write_bytes(
        canonical(report))
    return report


def mutation_selftest(product: Path, elf: Path) -> dict[str, Any]:
    address, expected = facade_truth(elf)
    rejected: list[str] = []
    with tempfile.TemporaryDirectory(prefix="c2-v160-packed-facade-") as temp:
        good = Path(temp) / "good.prg"
        shutil.copyfile(product, good)
        good_raw, good_offset = prg_span(good, address, len(expected))
        good_raw[good_offset:good_offset + len(expected)] = expected
        good.write_bytes(good_raw)
        packed_facade_gate(good, elf)
        raw, offset = prg_span(good, address, len(expected))
        cases = {
            "null-facade": bytes(len(expected)),
            "partial-facade": expected[:-1] + b"\x00",
        }
        for name, replacement in cases.items():
            candidate = Path(temp) / f"{name}.prg"
            altered = bytearray(raw)
            altered[offset:offset + len(expected)] = replacement
            candidate.write_bytes(altered)
            try:
                packed_facade_gate(candidate, elf)
            except RuntimeError:
                rejected.append(name)
    require(rejected == ["null-facade", "partial-facade"],
            "packed-facade mutation survived")
    return {"cases": 2, "rejected": rejected}


def complete() -> dict[str, Any]:
    """Run canonical Completion with one pre-gate shipped-byte materializer."""
    original = BASE.CAN.complete_artifacts

    def materializing_completion() -> dict[str, Any]:
        original_gate = BASE.PRODUCT.fixed_facade_gate

        def shipped_gate(out: Path, target: Path, suffix: str) -> dict[str, Any]:
            elf = Path(str(target) + ".elf")
            report_path = out / "packed-prg-facade-materialization.json"
            if not report_path.exists():
                materialize_publish_predecessors(out, target, elf)
            value = original_gate(out, target, suffix)
            value["packed_PRG_facade"] = packed_facade_gate(target, elf)
            return value

        BASE.PRODUCT.fixed_facade_gate = shipped_gate
        try:
            return original()
        finally:
            BASE.PRODUCT.fixed_facade_gate = original_gate

    BASE.CAN.complete_artifacts = materializing_completion
    try:
        value = RED.complete()
    finally:
        BASE.CAN.complete_artifacts = original
    product = BASE.CAN.FINAL / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    gate = packed_facade_gate(product, elf)
    require(gate["bytes"] == FACADE_BYTES,
            "Completion did not deliver the fixed facade")
    return value


def session_config(product: Path, library: Path) -> dict[str, Any]:
    value = RED.session_config(product, library)
    value["format"] = "lisp65-c2-v160-refill-witness-media-repair-session-v1"
    value["media"]["product"]["remote_name"] = PRODUCT_REMOTE
    value["media"]["library"]["remote_name"] = LIBRARY_REMOTE
    value["shipped_byte_facade"] = {
        "section": FACADE_SECTION, "address": "0xB3B0", "bytes": FACADE_BYTES,
        "gate": "packed PRG byte-equal to final ELF before media build"}
    return value


def configure() -> None:
    RED.BUILD = BUILD
    RED.RECEIPT = RECEIPT
    RED.SESSION = SESSION
    RED.PRODUCT_REMOTE = PRODUCT_REMOTE
    RED.LIBRARY_REMOTE = LIBRARY_REMOTE
    RED.configure()
    # RED.configure() projects the successor paths into BASE; materialize that
    # projection for read-only checks as well as for BASE.build().
    BASE.configure_paths()
    BASE.complete = complete
    BASE.session_config = session_config


def preflight() -> None:
    configure()
    require(not BUILD.exists() and not RECEIPT.exists() and not SESSION.exists(),
            "facade-repair media preparation is one-shot")
    red = load(RED_RECEIPT)
    require(red["status"] == "PASS: V1.6 REFILL TRACE CONTACT READY",
            "attributed predecessor media receipt drift")
    mutation = mutation_selftest(
        RED.WPLTO / "lisp65-c2-substitution-linked.prg",
        RED.WPLTO / "lisp65-c2-substitution-linked.prg.elf")
    require(mutation["cases"] == 2, "packed-facade preflight drift")
    print(f"v1.6 shipped facade repair: PREFLIGHT PASS authority={authority()['commit'][:8]}")


def build() -> None:
    configure()
    value = BASE.build()
    product = BASE.CAN.FINAL / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    value.update({
        "format": "lisp65-c2-v160-refill-witness-media-repair-v1",
        "recorded_on": "2026-08-22",
        "successor_authority": authority(),
        "red_predecessor": bind(RED_RECEIPT),
        "shipped_byte_facade": packed_facade_gate(product, elf),
        "mutations": mutation_selftest(product, elf),
        "accounting": {"WPLTO_runs": 0, "product_links": 0,
                       "product_cards": 0, "replacement_media_builds": 2,
                       "device_contacts": 0},
        "status": "PASS: V1.6 REPAIRED FACADE TRACE CONTACT READY",
    })
    RECEIPT.write_bytes(canonical(value))
    print("v1.6 shipped facade repair: PASS media=2 contact=trace-read-ready")


def check() -> dict[str, Any]:
    configure()
    value = load(RECEIPT)
    require(value["status"] == "PASS: V1.6 REPAIRED FACADE TRACE CONTACT READY"
            and value["successor_authority"] == authority()
            and value["red_predecessor"] == bind(RED_RECEIPT),
            "facade-repair receipt drift")
    for row in [value["completion"], value["media_closure"],
                *value["media"].values(), value["session"]]:
        require(bind(ROOT / row["path"]) == row,
                f"facade-repair artifact drift: {row['path']}")
    product = BASE.CAN.FINAL / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    require(value["shipped_byte_facade"] == packed_facade_gate(product, elf)
            and value["mutations"] == mutation_selftest(product, elf),
            "permanent shipped-byte facade gate drift")
    pair = BASE.PAIR.pair_identity(ROOT / value["media"]["product"]["path"],
                                   ROOT / value["media"]["library"]["path"])
    require(pair == value["same_world_pair"], "repaired media pair drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "build", "check"))
    action = parser.parse_args().action
    if action == "preflight":
        preflight()
    elif action == "build":
        build()
    else:
        check()
        print("v1.6 shipped facade repair: CHECK PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
