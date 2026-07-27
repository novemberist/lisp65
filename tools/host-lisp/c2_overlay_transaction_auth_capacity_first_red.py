#!/usr/bin/env python3
"""Bind the transaction-auth capacity probe's first linker red."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / (
    "build/c2.2/substitution/overlay-transaction-auth-capacity-probe")
BASE = ROOT / "build/c2.2/substitution/product-link-30-hot-refill"
STEM = PROBE / "overlay-transaction-auth-capacity-seed.prg"
MAP = Path(str(STEM) + ".map")
LTO = Path(str(STEM) + ".lto.o")
STDERR = Path(str(STEM) + ".link.stderr.txt")
BASE_MAP = BASE / "resident-island-seed.prg.map"
BASE_LTO = BASE / "resident-island-seed.prg.lto.o"
CONTRACT_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-overlay-transaction-auth-contract-probe-receipt.json")
OUTPUT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-overlay-transaction-auth-capacity-first-red-receipt.json")
NM = ROOT / "tools/llvm-mos/bin/llvm-nm"


class ReceiptError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReceiptError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def section(path: Path, name: str) -> tuple[int, int]:
    pattern = re.compile(
        rf"^\s*([0-9a-f]+)\s+[0-9a-f]+\s+([0-9a-f]+)\s+\d+\s+"
        + re.escape(name) + r"\s*$", re.MULTILINE)
    found = pattern.search(path.read_text(encoding="utf-8", errors="replace"))
    require(found is not None, f"missing {name} in {path}")
    return int(found.group(1), 16), int(found.group(2), 16)


def symbols(path: Path) -> dict[str, tuple[int, str]]:
    result = subprocess.run(
        [str(NM), "--defined-only", "--print-size", str(path)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    require(result.returncode == 0, "llvm-nm failed")
    rows: dict[str, tuple[int, str]] = {}
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 4:
            try:
                rows[fields[-1]] = (int(fields[1], 16), fields[2])
            except ValueError:
                pass
    return rows


def build() -> dict[str, Any]:
    required = (MAP, LTO, STDERR, BASE_MAP, BASE_LTO, CONTRACT_RECEIPT)
    require(all(path.is_file() for path in required),
            "first-red evidence set incomplete")
    stderr = STDERR.read_text(encoding="utf-8", errors="replace")
    require("workbench overlay moved below the heap floor" in stderr
            and "ordinary Bank-0 state overlaps fixed C2 state" in stderr
            and "section .text virtual address range overlaps" in stderr,
            "expected first-red linker diagnostics absent")
    text_at, text_bytes = section(MAP, ".text")
    base_text_at, base_text_bytes = section(BASE_MAP, ".text")
    bss_at, bss_bytes = section(MAP, ".bss")
    base_bss_at, base_bss_bytes = section(BASE_MAP, ".bss")
    text_end = text_at + text_bytes
    base_text_end = base_text_at + base_text_bytes
    bss_end = bss_at + bss_bytes
    base_bss_end = base_bss_at + base_bss_bytes
    require((text_at, base_text_at) == (0x2023, 0x2023),
            "text origins drift")
    require((base_text_bytes, text_bytes, text_bytes - base_text_bytes)
            == (0x9398, 0x963e, 678), "text delta drift")
    require((base_bss_bytes, bss_bytes, bss_bytes - base_bss_bytes)
            == (0x723, 0x72a, 7), "BSS delta drift")
    require(0xB481 - base_text_end == 198
            and 0xB481 - text_end == -480,
            "text headroom arithmetic drift")
    require(0xC080 - base_bss_end == 19
            and 0xC080 - bss_end == -466,
            "BSS headroom arithmetic drift")

    old = symbols(BASE_LTO)
    new = symbols(LTO)
    named: dict[str, dict[str, int]] = {}
    for name in sorted(set(old) | set(new)):
        before = old.get(name, (0, ""))
        after = new.get(name, (0, ""))
        delta = after[0] - before[0]
        if delta and (before[1].lower() == "t" or after[1].lower() == "t"):
            named[name] = {
                "link30_bytes": before[0],
                "probe_bytes": after[0],
                "delta_bytes": delta,
            }
    gross = sum(row["delta_bytes"] for row in named.values())
    require(gross == 688, f"named text attribution drift: {gross}")
    expected = {
        "vm_runtime_overlay_exec_family": 242,
        "eval_v2_workbench_service": 158,
        "vm_runtime_overlay_transaction_begin": 103,
        "vm_callprim": 69,
        "vm_runtime_overlay_transaction_end": 54,
        "rtov_fail": 21,
        "vm_runtime_overlay_abort_cleanup": 21,
        "vm_runtime_overlay_select_family": 12,
        "vm_runtime_overlay_catalog_verifier": 10,
        "vm_key_event": -2,
    }
    require({name: row["delta_bytes"] for name, row in named.items()}
            == expected, "named attribution set drift")

    return {
        "format": "lisp65-c2-overlay-transaction-auth-capacity-first-red-v1",
        "recorded_on": "2026-07-20",
        "status": "first-red-before-product-link-capacity-and-structure-not-reached",
        "scope": {
            "authorized_product_shaped_seed_links": 1,
            "actual_product_shaped_seed_link_attempts": 1,
            "completed_seed_links": 0,
            "product_closure_links": 0,
            "hardware_runs": 0,
            "product_sha_changes": 0,
            "link30_candidate": "unchanged",
        },
        "prerequisite": bind(CONTRACT_RECEIPT),
        "failed_attempt": {
            "map": bind(MAP),
            "lto_object": bind(LTO),
            "link_stderr": bind(STDERR),
            "resolved_profile": bind(PROBE / "resolved-profile.txt"),
        },
        "first_red": {
            "bank0_text": {
                "link30_bytes": base_text_bytes,
                "probe_bytes": text_bytes,
                "net_delta_bytes": text_bytes - base_text_bytes,
                "link30_headroom_bytes": 0xB481 - base_text_end,
                "probe_headroom_bytes": 0xB481 - text_end,
                "overlap_bytes": text_end - 0xB481,
            },
            "bank0_bss": {
                "link30_bytes": base_bss_bytes,
                "probe_bytes": bss_bytes,
                "direct_state_delta_bytes": bss_bytes - base_bss_bytes,
                "link30_headroom_bytes": 0xC080 - base_bss_end,
                "probe_headroom_bytes": 0xC080 - bss_end,
                "overlap_bytes": bss_end - 0xC080,
                "note": (
                    "The seven direct state bytes are small; the text growth also "
                    "moves the following data/BSS image by 478 bytes."
                ),
            },
            "named_text_attribution": named,
            "named_text_gross_delta_bytes": gross,
            "linked_text_net_delta_bytes": text_bytes - base_text_bytes,
            "layout_or_icf_credit_bytes": gross - (text_bytes - base_text_bytes),
        },
        "not_reached": {
            "runtime_slice_caps": "n/a-linker-stopped-first",
            "resident_island_capacity": "n/a-linker-stopped-first",
            "e000_exact_zero_delta": "n/a-linker-stopped-first",
            "pre_ownership": "n/a-linker-stopped-first",
            "profile_data_references": "n/a-linker-stopped-first",
            "fixed_facade": "n/a-linker-stopped-first",
            "kernal_freedom": "n/a-linker-stopped-first",
        },
        "diagnosis": {
            "host_semantics": "remain passed and independently bound",
            "capacity": (
                "The direct outer transaction implementation is structurally too "
                "large for the closed resident layout. Most cost is code growth in "
                "the generic transport and duplicated inlined product call paths, "
                "not the seven-byte trust cache itself."
            ),
            "measured_candidate_direction_not_authorized": (
                "A separately reviewed follow-up could test a noinline/single-call "
                "product wrapper and/or place transaction control in the 497-byte "
                "Resident-Island headroom, while keeping E000 delta exactly zero."
            ),
        },
        "claim_limit": (
            "One failed non-product seed link attempt. Host semantics remain green, "
            "but capacity and every later structure gate are unpassed. No product "
            "candidate, hardware, latency, promotion or release claim."
        ),
        "next_gate": (
            "Stop for review. No automatic follow-up, no product link and no "
            "capacity-limit relaxation are authorized."
        ),
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    try:
        value = build()
        data = canonical(value)
        if OUTPUT.exists():
            if OUTPUT.read_bytes() != data:
                raise ReceiptError("refusing to overwrite divergent first-red receipt")
        else:
            OUTPUT.write_bytes(data)
        os.chmod(OUTPUT, 0o444)
        print("c2-overlay-transaction-auth-first-red: PASS "
              "host=green text=+678 bss=+7 product-links=0 "
              f"receipt={sha(OUTPUT)}")
        return 0
    except (OSError, ValueError, KeyError, ReceiptError) as exc:
        print(f"c2-overlay-transaction-auth-first-red: FAIL {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
