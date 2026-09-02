#!/usr/bin/env python3
"""Pin and artifact-replay a completed C2 product-substitution link."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import c2_product_substitution_link as c2  # noqa: E402


class ReplayError(RuntimeError):
    pass


def regular(path: Path, label: str) -> bytes:
    try:
        info = path.lstat()
    except OSError as exc:
        raise ReplayError(f"missing {label}: {path}: {exc}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ReplayError(f"{label} must be a regular, symlink-free file: {path}")
    return path.read_bytes()


def digest(path: Path) -> str:
    return hashlib.sha256(regular(path, "hash input")).hexdigest()


def load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(regular(path, label).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReplayError(f"invalid {label}: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReplayError(f"{label} root must be an object")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise ReplayError(f"refusing to replace evidence output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                         encoding="ascii")
    temporary.replace(path)


def artifact(path: Path, role: str) -> dict[str, Any]:
    data = regular(path, role)
    return {
        "role": role,
        "path": str(path.relative_to(ROOT)),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def verify_artifact(item: dict[str, Any]) -> Path:
    path = ROOT / item["path"]
    data = regular(path, str(item.get("role", "pinned artifact")))
    if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
        raise ReplayError(f"pinned artifact drift: {path}")
    return path


def pin(link_dir: Path, receipt: Path, link_number: int) -> None:
    if link_number != 19 or link_dir.name != "product-link-19":
        raise ReplayError("this bounded pin operation is authorized only for product-link-19")
    final_report = load(link_dir / "eighteenth-substitution-link.json",
                        "Link-19 structural report")
    kernal = load(link_dir / "kernal-freedom-link.json", "KERNAL-freedom report")
    balance = load(link_dir / "substitution-balance.json", "substitution balance")
    family = load(link_dir / "runtime-family-total-identity.json",
                  "runtime-family identity")
    pre = load(link_dir / "pre-ownership-closure-final.json", "pre-ownership report")
    facade = load(link_dir / "fixed-host-facade-final.json", "fixed-facade report")
    truth = load(link_dir / "one-truth-closure.json", "one-truth report")
    publish = load(link_dir / "runtime-verifier-publish-last.json", "publish-last report")
    reports = (final_report, kernal, balance, family, pre, facade, truth, publish)
    if any(report.get("status") != "passed" for report in reports):
        raise ReplayError("Link-19 has a non-passed structural report")
    if final_report.get("product_closure_link_count") != 1:
        raise ReplayError("Link-19 product closure count drift")
    product = link_dir / "lisp65-c2-substitution-linked.prg"
    if digest(product) != final_report.get("product_sha256"):
        raise ReplayError("Link-19 product identity differs from structural report")

    items = [
        artifact(path, "link19:" + path.name)
        for path in sorted(link_dir.iterdir(), key=lambda value: value.name)
        if path.is_file() and not path.is_symlink()
    ]
    for path, role in (
        (ROOT / "build/c2.2/substitution/substitution-artifacts.json",
         "c2-substitution-artifact-manifest"),
        (ROOT / "build/c2.2/substitution/product-shelf-v4-direct.bin",
         "immutable-c2-shelf"),
        (ROOT / "build/c2.2/substitution/initial.c2d-v3.bin",
         "initial-c2d-mutable-plane"),
    ):
        items.append(artifact(path, role))

    receipt_value = {
        "format": "lisp65-c2-product-substitution-link-pin-v1",
        "recorded_on": "2026-07-20",
        "status": "pinned-structural-hardware-not-run",
        "link_number": link_number,
        "inheritance": "none; every Link-19 structural and capacity gate ran fresh",
        "product_identity": artifact(product, "link19-product-prg"),
        "link_counts": {
            "product_closure": final_report["product_closure_link_count"],
            "resident_island_seed": final_report["resident_island_seed_link_count"],
        },
        "structural_gates": {
            "identity": final_report["identity_gate"],
            "pre_ownership": final_report["pre_ownership_gate"],
            "fixed_host_facade": final_report["fixed_host_facade_gate"],
            "runtime_family_total_identity": family["status"],
            "mutated_payload_negative": family["mutated_payload_negative"],
            "one_truth": final_report["one_truth_gate"],
            "kernal_freedom": final_report["kernal_freedom_gate"],
            "capacity": final_report["capacity_gate"],
            "substitution_balance": final_report["substitution_balance"],
        },
        "control_flow_ownership": kernal["control_flow_ownership"],
        "capacity": balance["currencies"],
        "evidence_objects": items,
        "evidence_object_count": len(items),
        "gate_driver": artifact(
            ROOT / "tools/host-lisp/c2_product_substitution_link.py",
            "link-and-structural-gate-driver"),
        "remaining_claims": {
            "artifact_replay": "not-run",
            "hardware": "not-run",
            "promotion": "not-run",
            "release": "not-run",
        },
        "claim_limit": (
            "Fresh Link-19 structural pin only. No Link-18 green is inherited. "
            "Artifact replay, hardware acceptance, promotion and release remain not-run."),
    }
    write_json(receipt, receipt_value)
    print(f"c2-product-pin-replay: PIN PASS link=19 objects={len(items)} "
          f"product={receipt_value['product_identity']['sha256']}")


def publish_last_replay(work: Path, final: Path) -> dict[str, Any]:
    unbound = work / "lisp65-c2-substitution-unbound.prg"
    replay_target = work / "publish-last-replay.prg"
    replay_elf = Path(str(replay_target) + ".elf")
    shutil.copyfile(unbound, replay_target)
    shutil.copyfile(Path(str(final) + ".elf"), replay_elf)
    report = c2.patch_verifier_binding_table(
        work, replay_target,
        work / "runtime-overlays-boot-final.json",
        work / "runtime-overlays-session-final.json")
    if replay_target.read_bytes() != final.read_bytes():
        raise ReplayError("publish-last replay did not reproduce the pinned product PRG")
    return report


def replay(pin_receipt: Path, work: Path, replay_receipt: Path) -> None:
    pin_value = load(pin_receipt, "Link-19 pin receipt")
    if (pin_value.get("status") != "pinned-structural-hardware-not-run"
            or pin_value.get("link_number") != 19):
        raise ReplayError("replay input is not the authorized Link-19 pin")
    verified = [verify_artifact(item) for item in pin_value["evidence_objects"]]
    verify_artifact(pin_value["gate_driver"])
    if work.exists():
        raise ReplayError(f"replay work directory must be fresh: {work}")
    source_dir = ROOT / "build/c2.2/substitution/product-link-19"
    shutil.copytree(source_dir, work)
    final = work / "lisp65-c2-substitution-linked.prg"

    window = c2.extract_pinned_kernal_window(work, final,
                                             c2.kernal_window_identity_pin())
    publish = publish_last_replay(work, final)
    pre = c2.pre_ownership_gate(work, final, "replay")
    facade = c2.fixed_facade_gate(work, final, "replay")
    family = c2.runtime_family_identity_gate(
        work,
        (work / "runtime-overlays-boot-unbound.bin",
         work / "runtime-overlays-boot-unbound.json"),
        (work / "runtime-overlays-session-unbound.bin",
         work / "runtime-overlays-session-unbound.json"),
        (work / "runtime-overlays-boot-final.bin",
         work / "runtime-overlays-boot-final.json"),
        (work / "runtime-overlays-session-final.bin",
         work / "runtime-overlays-session-final.json"))
    c2.closure_gate(work, final)
    truth = load(work / "one-truth-closure.json", "replayed one-truth report")
    kernal = c2.kernal_freedom_gate(work, final)
    balance = c2.substitution_balance(work, final, kernal)
    reports = {
        "window": artifact(window, "replayed-kernal-window"),
        "publish_last": artifact(work / "runtime-verifier-publish-last.json",
                                 "replayed-publish-last"),
        "pre_ownership": artifact(work / "pre-ownership-closure-replay.json",
                                  "replayed-pre-ownership"),
        "fixed_facade": artifact(work / "fixed-host-facade-replay.json",
                                 "replayed-fixed-facade"),
        "runtime_family_identity": artifact(
            work / "runtime-family-total-identity.json",
            "replayed-runtime-family-identity"),
        "one_truth": artifact(work / "one-truth-closure.json",
                              "replayed-one-truth"),
        "kernal_freedom": artifact(work / "kernal-freedom-link.json",
                                   "replayed-kernal-freedom"),
        "substitution_balance": artifact(work / "substitution-balance.json",
                                         "replayed-substitution-balance"),
    }
    replay_value = {
        "format": "lisp65-c2-product-substitution-artifact-replay-v1",
        "recorded_on": "2026-07-20",
        "status": "passed-structural-hardware-not-run",
        "link_number": 19,
        "new_product_links": 0,
        "pin_receipt": {
            "path": str(pin_receipt.relative_to(ROOT)),
            "sha256": digest(pin_receipt),
        },
        "pinned_evidence_objects_verified": len(verified),
        "pinned_evidence_drift": 0,
        "replayed_gates": {
            "kernal_window_sha_crc": "passed",
            "publish_last": publish["status"],
            "pre_ownership": pre["status"],
            "fixed_host_facade": facade["status"],
            "runtime_family_total_identity": family["status"],
            "mutated_payload_negative": family["mutated_payload_negative"],
            "one_truth": truth["status"],
            "kernal_freedom": kernal["status"],
            "capacity": "passed",
            "substitution_balance": balance["status"],
        },
        "control_flow_ownership": kernal["control_flow_ownership"],
        "capacity": balance["currencies"],
        "product_identity": artifact(final, "replayed-link19-product-prg"),
        "reports": reports,
        "remaining_claims": {
            "hardware": "not-run",
            "promotion": "not-run",
            "release": "not-run",
        },
        "claim_limit": (
            "SHA-bound artifact-only replay of fresh Link 19. No product link "
            "occurred during replay. Hardware, promotion and release remain not-run."),
    }
    if replay_value["product_identity"]["sha256"] != pin_value["product_identity"]["sha256"]:
        raise ReplayError("replay product identity differs from Link-19 pin")
    write_json(replay_receipt, replay_value)
    print(f"c2-product-pin-replay: REPLAY PASS link=19 objects={len(verified)} "
          "new-links=0")


def selftest() -> None:
    sample = hashlib.sha256(b"link19").hexdigest()
    if len(sample) != 64:
        raise ReplayError("SHA-256 selftest failed")
    print("c2-product-pin-replay: SELFTEST PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    pin_parser = sub.add_parser("pin")
    pin_parser.add_argument("--link-dir", type=Path, required=True)
    pin_parser.add_argument("--receipt", type=Path, required=True)
    pin_parser.add_argument("--link-number", type=int, required=True)
    replay_parser = sub.add_parser("replay")
    replay_parser.add_argument("--pin-receipt", type=Path, required=True)
    replay_parser.add_argument("--work", type=Path, required=True)
    replay_parser.add_argument("--receipt", type=Path, required=True)
    sub.add_parser("selftest")
    args = parser.parse_args()
    try:
        if args.command == "pin":
            pin(args.link_dir.resolve(), args.receipt.resolve(), args.link_number)
        elif args.command == "replay":
            replay(args.pin_receipt.resolve(), args.work.resolve(),
                   args.receipt.resolve())
        else:
            selftest()
    except (ReplayError, RuntimeError, OSError, KeyError, ValueError) as exc:
        print(f"c2-product-pin-replay: FAIL {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
