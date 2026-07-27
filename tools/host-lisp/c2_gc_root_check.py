#!/usr/bin/env python3
"""Verify the C2 mutable-resolution GC-root decision inputs."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_full_emission as F  # noqa: E402

PROPOSAL = ROOT / "config/c2-gc-root-proposal.json"
DOCUMENT = ROOT / "docs/planning/c2.1-gc-root-addendum.md"
FULL = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.1-full-emission-receipt.json"
)
STREAM = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.1-streaming-decoder-link-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2-gc-root-proposal-receipt.json"
)
MEMORY = ROOT / "src/mem.c"


class RootError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RootError(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(data), "sha256": sha(data)}


def collect() -> dict[str, Any]:
    proposal = json.loads(PROPOSAL.read_text(encoding="utf-8"))
    full = json.loads(FULL.read_text(encoding="utf-8"))
    stream = json.loads(STREAM.read_text(encoding="utf-8"))
    images, shelf, c2d, facts = F.build_all()
    counts = Counter(item.kind for image in images for item in image.descriptors)
    roots = counts[3] + counts[7]
    root_bytes = roots * 2
    new_total = len(c2d) + root_bytes
    region = 50816
    full_scan = facts["c2i_v2_descriptors"] * 2

    require(proposal["status"] == "product-substitution-blocked-owner-decision-required",
            "GC-root proposal status drift")
    require(full["facts"]["c2i_v2_descriptors"] == 2249
            and stream["full_execution"]["descriptors"] == 2249,
            "full/streaming descriptor receipts disagree")
    require(dict(sorted(counts.items())) == {0: 1, 2: 260, 3: 116, 4: 725,
                                             7: 168, 8: 979},
            "descriptor-kind root census drift")
    require(len(shelf) == 69754 and len(c2d) == 10480 and roots == 284
            and root_bytes == 568 and new_total == 11048
            and region - new_total == 39768, "C2D root arithmetic drift")
    require(full_scan == 4498 and (full_scan + 31) // 32 == 141
            and (root_bytes + 31) // 32 == 18, "GC transfer arithmetic drift")
    require(proposal["measured"]["kind_counts"] == {
        "0_nil": 1, "2_fixnum": 260, "3_immutable_string": 116,
        "4_local_entry": 725, "5_export_edge": 0,
        "7_cons_pair": 168, "8_general_symbol": 979,
    }, "proposal kind census drift")
    option = proposal["options"][1]
    require(option["id"] == "c2d-v2-contiguous-root-vector"
            and option["c2d_bytes"] == new_total
            and option["bank5_session_headroom_bytes"] == region - new_total,
            "recommended option arithmetic drift")
    memory = MEMORY.read_text(encoding="utf-8")
    require("for (i = 0; i < gc_rootsp; i++) gc_mark1(gc_rootstack[i]);" in memory
            and "gc_mark1(sym_value(sym));" in memory,
            "current collector root-source evidence drift")

    return {
        "format": "lisp65-c2-gc-root-proposal-receipt-v1",
        "version": 1,
        "recorded_on": "2026-07-19",
        "status": "product-substitution-blocked-owner-decision-required",
        "claim_limit": (
            "This receipt binds the complete descriptor census, current GC root sources "
            "and the three architecture options. It changes no product byte, authorizes "
            "no capacity and does not claim a C2 product link or device execution."
        ),
        "bindings": {
            "proposal": bind(PROPOSAL), "document": bind(DOCUMENT),
            "full_emission": bind(FULL), "streaming_decoder": bind(STREAM),
            "collector": bind(MEMORY), "verifier": bind(Path(__file__)),
        },
        "verified": {
            "images": len(images), "shelf_bytes": len(shelf),
            "resolution_count": facts["c2i_v2_descriptors"],
            "kind_counts": {str(key): counts[key] for key in sorted(counts)},
            "additional_root_values": roots, "additional_root_bytes": root_bytes,
            "full_resolution_scan_bytes": full_scan,
            "full_resolution_scan_reads_32": (full_scan + 31) // 32,
            "compact_root_scan_reads_32": (root_bytes + 31) // 32,
            "c2d_v1_bytes": len(c2d), "c2d_v2_projected_bytes": new_total,
            "bank5_session_headroom_after_v2": region - new_total,
            "product_bytes_changed": 0,
        },
        "recommendation": "Option B: C2D-v2 contiguous root vector",
        "next_action": "Owner decision before changing C2D, the streaming decoder or any product-layout source",
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    try:
        value = collect()
        if args.action == "selftest":
            require(value["verified"]["additional_root_values"] == 284,
                    "GC-root selftest closure")
            print("c2-gc-root: SELFTEST PASS roots=284 options=3 product-bytes=0")
            return 0
        data = canonical(value)
        if args.action == "write":
            RECEIPT.parent.mkdir(parents=True, exist_ok=True)
            RECEIPT.write_bytes(data); verb = "WROTE"
        else:
            require(RECEIPT.is_file() and RECEIPT.read_bytes() == data,
                    "C2 GC-root proposal receipt drift; regenerate with write")
            verb = "PASS"
        print(f"c2-gc-root: {verb} roots=284 c2d-v2=11048 owner-decision=required")
        return 0
    except (OSError, ValueError, RootError, F.FullError) as error:
        print(f"c2-gc-root: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
