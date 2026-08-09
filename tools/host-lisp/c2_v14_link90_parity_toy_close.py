#!/usr/bin/env python3
"""Prepare/check the autonomous Link-90 parity-toy target close."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

from elf_truth import ElfTruth  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PRODUCT = ROOT / (
    "build/c2.3/v1.4.0-candidate-product-link90-r1/"
    "canonical-product-manifest.json")
MEDIA = ROOT / (
    "build/c2.3/v1.4.0-candidate-media-link90-r1/candidate-manifest.json")
CARD = EVIDENCE / "c2.3-v1.4-link90-vic-unlock-wplto-receipt.json"
M65_GATE = EVIDENCE / "c2.3-v1.4-m65-hw-host-first-receipt.json"
ATTRIBUTION = EVIDENCE / (
    "c2.3-v1.4-link89-vic-unlock-tailcall-attribution.json")
TOY_RECEIPT = ROOT / (
    "build/post-promotion/v14/sample-fleet-host-link90/"
    "parity-toy.receipt.json")
TOY = ROOT / (
    "build/post-promotion/v14/sample-fleet-host-link90/parity-toy.d81")
TOY_ELF = ROOT / (
    "build/post-promotion/v14/sample-fleet-host-link90/"
    "parity-toy.runtime.elf")
SCRIPT = ROOT / "scripts/c2-v14-link90-parity-toy-hw.sh"
DRIVER = Path(__file__).resolve()
BASE = ROOT / "build/post-promotion/v14/link90-parity-toy-close"
DEPLOYMENT = BASE / "deployment.json"
PREPARATION = EVIDENCE / (
    "c2.3-v1.4-link90-parity-toy-device-preparation-receipt.json")
LLVM_READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"


class CloseError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CloseError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    path = path.resolve()
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    data = path.read_bytes()
    return {
        "path": path.relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, indent=2, sort_keys=True)
                      + "\n").encode("ascii"))


def clean_head() -> str:
    result = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    require(result.returncode == 0 and result.stdout == "",
            "preparation requires a clean worktree")
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def prepare() -> int:
    head = clean_head()
    product = load(PRODUCT)
    media = load(MEDIA)
    card = load(CARD)
    gate = load(M65_GATE)
    attribution = load(ATTRIBUTION)
    toy = load(TOY_RECEIPT)
    require(
        product["status"]
            == "passed-fresh-source-product-and-post-link-completion"
        and product["static_plane"]["product_build_id"] == "0x293611ce"
        and product["static_plane"]["bank2_static_code_bytes"] == 47282
        and media["status"] == "passed-complete-C2-lite-two-media-product"
        and media["artifact_count"] == 19
        and card["status"]
            == "passed-v1.4-link90-vic-unlock-one-product-shaped-WPLTO"
        and gate["status"] == "passed"
        and gate["artifact"]["code_bytes"] == 1768
        and gate["artifact"]["cases_executed_per_lane"] == 13
        and gate["mutations"]["count"] == 10
        and attribution["status"]
            == "ATTRIBUTED AND HOST-FIXED; SUCCESSOR DEVICE PROOF REQUIRED"
        and toy["status"] == "passed"
        and toy["image"]["sha256"]
            == "640d115e01d238413821ab9cf5b59056abf553e96e27cf0c64d8db75ef8a2bde"
        and toy["runtime_audit"]["elf_sha256"]
            == "dcb415da6379d0fc68185a4a486ab07a72442524bbefbca0fc7b3cffda8e841f",
        "Link-90 target-close authority drift",
    )
    truth = ElfTruth.read(
        TOY_ELF, llvm_readobj=LLVM_READOBJ, include_section_data=False)
    state = truth.symbol("lisp65_runtime_state").value
    result = truth.symbol("lisp65_runtime_result").value
    status = truth.symbol("vm_status").value
    require(state == 0x85 and result == 0x86,
            "fixed parity-toy runtime geometry drift")
    deployment = {
        "format": "lisp65-c2.3-v1.4-link90-parity-toy-deployment-v1",
        "status": "prepared",
        "source_commit": head,
        "candidate_link": 90,
        "image": bind(TOY),
        "runtime_elf": bind(TOY_ELF),
        "remote": "V14L90T.D81",
        "runtime": {
            "state": f"0x{state:08x}",
            "result": f"0x{result:08x}",
            "vm_status": f"0x{status:08x}",
            "waiting": 2,
            "complete": 3,
        },
        "input_policy": (
            "No virtual input. Boot autonomously, then one physical key only "
            "after RUNTIME_WAITING_INPUT=2 is read."),
    }
    write_json(DEPLOYMENT, deployment)
    receipt = {
        "format": "lisp65-c2.3-v1.4-link90-parity-toy-device-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status": "prepared-host-green-Link90-autonomous-parity-toy-close",
        "source_commit": head,
        "candidate_link": 90,
        "product_links_consumed": 1,
        "hardware_contacts": 0,
        "preflight": {
            "m65_surface": "15 public, 13x2 executions, 10 mutations",
            "capacity": "1768/2048 Bank-2 bytes; zero resident bytes",
            "product": "Link 90 profile 0x293611ce; 19 media roles",
            "ship": "fixed parity-toy host-executed once; nine members",
            "input": "autonomous boot plus one physical key; no REPL forms",
        },
        "bindings": {
            "product": bind(PRODUCT),
            "media": bind(MEDIA),
            "wplto": bind(CARD),
            "m65_gate": bind(M65_GATE),
            "attribution": bind(ATTRIBUTION),
            "toy_receipt": bind(TOY_RECEIPT),
            "deployment": bind(DEPLOYMENT),
            "driver": bind(DRIVER),
            "script": bind(SCRIPT),
        },
        "claim_limit": (
            "Host/device preparation only. No fixed-target sprite, physical "
            "input or SID claim."),
    }
    write_json(PREPARATION, receipt)
    print("c2-v14-link90-parity-toy-close: PREPARED "
          "input=autonomous+physical-key virtual-chars=0")
    return 0


def dry_run() -> int:
    deployment = load(DEPLOYMENT)
    preparation = load(PREPARATION)
    require(
        deployment["status"] == "prepared"
        and deployment["candidate_link"] == 90
        and preparation["status"]
            == "prepared-host-green-Link90-autonomous-parity-toy-close",
        "Link-90 deployment state drift",
    )
    for row in preparation["bindings"].values():
        require(bind(ROOT / row["path"])["sha256"] == row["sha256"],
                f"bound artifact drift: {row['path']}")
    require(bind(ROOT / deployment["image"]["path"])["sha256"]
            == deployment["image"]["sha256"], "toy image drift")
    print("c2-v14-link90-parity-toy-close: DRY-RUN PASS "
          "cold-reset=1 FTP-guard=120 state=2 physical-key=1")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "dry-run"))
    args = parser.parse_args()
    return prepare() if args.action == "prepare" else dry_run()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CloseError, OSError, KeyError, ValueError,
            json.JSONDecodeError) as error:
        print(f"c2-v14-link90-parity-toy-close: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
