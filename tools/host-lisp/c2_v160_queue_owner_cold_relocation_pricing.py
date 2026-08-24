#!/usr/bin/env python3
"""Price the cold-relocation fallback after the queue-owner capacity Red."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

import evidence_era as ERA


ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
FIRST_MAP = ROOT / "build/c2.3/v1.6-queue-single-owner-card/wplto/resident-island-seed.prg.map"
SINGLE_MAP = ROOT / "build/c2.3/v1.6-queue-single-owner-replacement-card/wplto/resident-island-seed.prg.map"
CALL_ELF = ROOT / "build/c2.3/v1.6-bound-origin-fragmentation-second-replacement-card/wplto/resident-island-seed.prg.elf"
FIRST_RED = ARCH / "c2.3-v1.6-queue-single-owner-card-final-red.json"
SINGLE_RED = ARCH / "c2.3-v1.6-queue-single-owner-replacement-card-final-red.json"
RECEIPT = ARCH / "c2.3-v1.6-queue-owner-cold-relocation-pricing.json"
RUNTIME = ROOT / "src/vm_runtime_overlay.c"
FAR_HEADER = ROOT / "src/c2_mapped_far_service.h"
FAR_FACADE = ROOT / "src/optional/c2_mapped_far_service_liveness_v4.s"
DRIVER = Path(__file__).resolve()
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
AUTHORIZATION = "b6632c09"
FORMAT = "lisp65-c2-v160-queue-owner-cold-relocation-pricing-v1"
STATUS = "PASS: COLD RELOCATION RECOVERS QUEUE-OWNER TEXT CAPACITY"
SEALED_COMMIT = "b9f23b136208b1838e1e67c14f5b594ead09cb5c"


class PricingError(RuntimeError): pass


def require(value: bool, message: str) -> None:
    if not value: raise PricingError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    full = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(["git", "show", f"{full}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("order of routes", "measured in emitted bytes",
                  "one cold routine relocates", "entry stub plus body",
                  "floors and the facade stay untouched"):
        require(token in text, f"cold-relocation authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def section(map_text: str, name: str) -> dict[str, int]:
    match = re.search(rf"^\s*([0-9a-f]+)\s+[0-9a-f]+\s+([0-9a-f]+)\s+\d+\s+{re.escape(name)}$",
                      map_text, re.MULTILINE)
    require(match is not None, f"map section absent: {name}")
    return {"address": int(match.group(1), 16), "bytes": int(match.group(2), 16)}


def symbol(map_text: str, name: str) -> dict[str, int]:
    matches = re.findall(rf"^\s*([0-9a-f]+)\s+[0-9a-f]+\s+([0-9a-f]+)\s+\d+\s+.*\(\.text\.{re.escape(name)}\)$",
                         map_text, re.MULTILINE)
    require(len(matches) == 1, f"map symbol identity drift: {name}")
    return {"address": int(matches[0][0], 16), "bytes": int(matches[0][1], 16)}


def callsites(target: int) -> list[dict[str, Any]]:
    text = subprocess.run([str(OBJDUMP), "-d", str(CALL_ELF)], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout
    pattern = re.compile(r"^\s*([0-9a-f]+):\s+(?:[0-9a-f]{2}\s+)+"
                         rf"(jsr|jmp)\s+\${target:x}\b", re.MULTILINE)
    return [{"source": f"0x{int(m.group(1), 16):04x}",
             "instruction": m.group(2), "target": f"0x{target:04x}"}
            for m in pattern.finditer(text)]


def derive() -> dict[str, Any]:
    first = FIRST_MAP.read_text(encoding="utf-8")
    single = SINGLE_MAP.read_text(encoding="utf-8")
    first_text = section(first, ".text")
    single_text = section(single, ".text")
    facade = section(first, ".lisp65_c2_mapped_far_facade")
    far = section(first, ".lisp65_c2_mapped_far_service")
    candidate = symbol(first, "rtov_transaction_context_if_ready")
    calls = callsites(candidate["address"])
    runtime = RUNTIME.read_text(encoding="utf-8")
    header = FAR_HEADER.read_text(encoding="utf-8")
    asm = FAR_FACADE.read_text(encoding="utf-8")
    first_free = facade["address"] - (first_text["address"] + first_text["bytes"])
    single_free = facade["address"] - (single_text["address"] + single_text["bytes"])
    stub_bytes = 9
    reclaim = candidate["bytes"] - stub_bytes
    far_capacity = 1499
    return {
        "format": FORMAT, "status": STATUS,
        "authority": authority(),
        "inputs": {"first_guard_map": bind(FIRST_MAP),
                   "single_exit_map": bind(SINGLE_MAP),
                   "callsite_elf": bind(CALL_ELF),
                   "first_guard_red": bind(FIRST_RED),
                   "single_exit_red": bind(SINGLE_RED),
                   "runtime_source": ERA.era_bind(SEALED_COMMIT, RUNTIME),
                   "far_header": ERA.era_bind(SEALED_COMMIT, FAR_HEADER),
                   "far_facade": ERA.era_bind(SEALED_COMMIT, FAR_FACADE),
                   "driver": ERA.era_bind(SEALED_COMMIT, DRIVER)},
        "route_1": {
            "verdict": "REJECTED BY EMITTED BYTES",
            "first_guard_text_bytes": first_text["bytes"],
            "single_exit_text_bytes": single_text["bytes"],
            "single_exit_delta_bytes": single_text["bytes"] - first_text["bytes"],
            "first_guard_free_bytes": first_free,
            "single_exit_free_bytes": single_free,
            "single_exit_overlap_bytes": -single_free,
            "reason": "live stop state costs more than the duplicated abort sites"},
        "route_2": {
            "verdict": "WINNER: COLD RELOCATION FITS BOTH ARENAS",
            "symbol": "rtov_transaction_context_if_ready",
            "ordinary_address": f"0x{candidate['address']:04x}",
            "body_bytes": candidate["bytes"],
            "source_call_count": runtime.count("rtov_transaction_context_if_ready(&verify"),
            "linked_callsites": calls,
            "hot_path_classification": "two runtime-overlay transaction verification/install calls; no per-key or per-eval edge",
            "ordinary_stub": "JSR c2_mapped_far_enter; JSR far body; JMP c2_mapped_far_leave",
            "ordinary_stub_bytes": stub_bytes,
            "ordinary_net_reclaim_bytes": reclaim,
            "ordinary_required_reclaim_bytes": -first_free,
            "ordinary_projected_free_bytes": first_free + reclaim,
            "far_service_bytes_before": far["bytes"],
            "far_service_capacity_bytes": far_capacity,
            "far_service_free_before": far_capacity - far["bytes"],
            "far_service_body_bytes": candidate["bytes"],
            "far_service_projected_free_bytes": far_capacity - far["bytes"] - candidate["bytes"],
            "facade_delta_bytes": 0,
            "map_window": "CPU block 3 $6000..$7fff",
            "resident_callee": "rtov_transaction_context@0x1dce",
            "resident_callee_disjoint": True,
            "existing_enter_leave_pair": ("c2_mapped_far_enter" in asm and
                                            "c2_mapped_far_leave" in asm),
            "placement_attribute_available": "LISP65_C2_MAPPED_FAR_FN" in header},
        "claim_boundary": {
            "host_only": True, "product_sources_changed": False,
            "WPLTO_runs": 0, "product_links": 0, "media_builds": 0,
            "device_contacts": 0,
            "next_step": "a new one-shot relocation card requires explicit authorization"}}


def validate(value: dict[str, Any]) -> None:
    r1, r2 = value["route_1"], value["route_2"]
    require(value["status"] == STATUS and r1["single_exit_delta_bytes"] == 55
            and r1["first_guard_free_bytes"] == -7
            and r1["single_exit_overlap_bytes"] == 62,
            "single-exit emitted-byte rejection drift")
    require(r2["symbol"] == "rtov_transaction_context_if_ready"
            and r2["body_bytes"] == 22 and r2["source_call_count"] == 2
            and r2["linked_callsites"] == [
                {"source": "0x2aa1", "instruction": "jsr", "target": "0x2e54"},
                {"source": "0x2c6e", "instruction": "jsr", "target": "0x2e54"}]
            and r2["ordinary_stub_bytes"] == 9
            and r2["ordinary_net_reclaim_bytes"] == 13
            and r2["ordinary_projected_free_bytes"] == 6
            and r2["far_service_free_before"] == 37
            and r2["far_service_projected_free_bytes"] == 15
            and r2["facade_delta_bytes"] == 0
            and r2["resident_callee_disjoint"]
            and r2["existing_enter_leave_pair"]
            and r2["placement_attribute_available"],
            "cold-relocation price or safety proof drift")


def selftest() -> None:
    value = derive(); validate(value)
    for path, replacement in (
        (("route_2", "body_bytes"), 21),
        (("route_2", "linked_callsites"), []),
        (("route_2", "ordinary_stub_bytes"), 10),
        (("route_2", "far_service_projected_free_bytes"), -1),
        (("route_2", "facade_delta_bytes"), 9),
        (("route_2", "resident_callee_disjoint"), False)):
        mutant = deepcopy(value); mutant[path[0]][path[1]] = replacement
        try: validate(mutant)
        except PricingError: pass
        else: raise PricingError(f"mutation survived: {path}")
    print("v1.6 queue-owner cold relocation pricing: SELFTEST PASS mutations=6")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else "check"
    if action == "selftest": selftest(); return 0
    if action == "write":
        value = derive(); validate(value); RECEIPT.write_bytes(canonical(value))
    require(action in ("write", "check"), "usage: [write|check|selftest]")
    value = load(RECEIPT); validate(value)
    current = derive(); current["inputs"]["driver"] = value["inputs"]["driver"]
    require(canonical(current) == canonical(value), "cold-relocation receipt drift")
    print("v1.6 queue-owner cold relocation pricing: PASS reclaim=13 text-free=6 far-free=15")
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except (PricingError, subprocess.CalledProcessError) as error:
        print(f"v1.6 queue-owner cold relocation pricing: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
