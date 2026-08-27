#!/usr/bin/env python3
"""Resurrect and qualify the frozen Block-3 r9 pair without rebuilding it."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v17_block3_r8_r9_attribution as ATTR  # noqa: E402
import c2_v17_ide_idle_blink_product_card as CARD  # noqa: E402
import c2_v17_ide_idle_blink_product_card_r9 as R9  # noqa: E402
import c2_v160_r1_graph_conversions as GRAPH  # noqa: E402
import c2_v160_r1_stored_world_conversions as ACCEPT  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
BUILD = ROOT / "build/c2.3/v1.7-block3-r9-candidate-resume"
PHASE_BUILD = BUILD / "phase-owned-build"
PHASE_PREFLIGHT = BUILD / "phase-owned-preflight"
SCOPE = PHASE_BUILD / "owner-scope-result.json"
ACCEPTANCE = PHASE_BUILD / "artifact-acceptance.json"
RECEIPT = ARCH / "c2.3-v1.7-block3-r9-candidate-resume.json"
REPORT = ROOT / "docs/planning/v1.7.0-block3-r9-candidate-resume.md"
FINAL_RED = ARCH / "c2.3-v1.7-block3-r9-candidate-resume-final-red.json"
RED_REPORT = ROOT / "docs/planning/v1.7.0-block3-r9-candidate-resume-final-red.md"
AUTHORIZATION = "05e1ca3e"
FORMAT = "lisp65-c2-v17-block3-r9-candidate-resume-v1"
STATUS = "PASS: BLOCK3 R9 RESURRECTED AND QUALIFIED READ-ONLY"
PHASE_ELF = PHASE_BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PHASE_PRG = PHASE_BUILD / "wplto/lisp65-c2-substitution-linked.prg"


class ResumeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResumeError(message)


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
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{AUTHORIZATION}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("r9 candidate resurrection and media authority",
                  "no r10 wplto or product link", "candidate scope",
                  "qualification/acceptance", "eight owners pairwise disjoint",
                  "same-world media"):
        require(token in text, f"r9 resurrection authority absent: {token}")
    return {"authority": "git-blob", "commit": AUTHORIZATION, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def pair(elf: Path = R9.ELF, prg: Path = R9.PRG) -> dict[str, Any]:
    return {"ELF": bind(elf), "PRG": bind(prg)}


def same_pair(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """A projected pair retains byte identity while gaining its own paths."""
    return all(left[name]["bytes"] == right[name]["bytes"]
               and left[name]["sha256"] == right[name]["sha256"]
               for name in ("ELF", "PRG"))


def composed_gate() -> dict[str, Any]:
    value = R9.composed(R9.ELF)
    require(value["status"] == "PASS: COMPOSED BANK2 OWNERS ARE DISJOINT"
            and len(value["owners"]) == 8 and not value["overlaps"]
            and value["largest_contiguous_hole"]["bytes"] == 11494
            and value["anchor"] == {
                "kind": "bank2-top-derived",
                "product_cold_end_equals_bank_end": True,
                "far_service_end_equals_product_cold_start": True}
            and all(row["VMA"] == R9.expected_vmas()[row["owner"]]
                    for row in value["mapped_tenants"]),
            "candidate composed Bank-2 gate red")
    return value


def prepare_phase_projection() -> None:
    require(not RECEIPT.exists() and not REPORT.exists(),
            "r9 candidate resume is one-shot")
    if BUILD.exists():
        require(not SCOPE.exists() and not ACCEPTANCE.exists(),
                "candidate execution already began before projection retry")
        shutil.rmtree(BUILD)
    shutil.copytree(R9.BUILD, PHASE_BUILD)
    shutil.copytree(R9.PREFLIGHT, PHASE_PREFLIGHT)
    for directory, directories, _files in os.walk(BUILD):
        Path(directory).chmod(Path(directory).stat().st_mode | 0o200)
        for name in directories:
            path = Path(directory) / name
            path.chmod(path.stat().st_mode | 0o200)
    for path in (SCOPE, ACCEPTANCE):
        if path.exists():
            path.unlink()
    require(same_pair(pair(PHASE_ELF, PHASE_PRG), pair()),
            "phase projection is not the frozen r9 pair")


def setup_child() -> Any:
    R9.install()
    core, _activation, _cold = R9.setup_child()
    core.bind_paths_only(PHASE_BUILD, PHASE_PREFLIGHT)
    CARD.install_final_v6_consumer(record=False)
    return core


def scope_child() -> None:
    core = setup_child()
    raise SystemExit(core.PRODUCT.BASE.scope_child())


def acceptance_child() -> None:
    core = setup_child()
    os.environ["LISP65_R1_ACCEPTANCE_RESULT"] = str(ACCEPTANCE)
    raise SystemExit(core.PRODUCT.BASE.acceptance_child())


def run_child(action: str) -> dict[str, Any]:
    result = subprocess.run([sys.executable, str(Path(__file__).resolve()), action],
                            cwd=ROOT, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    require(result.returncode == 0,
            f"r9 candidate {action} red:\n{result.stdout}")
    return {"action": action, "status": "PASS",
            "witness": " ".join(result.stdout.split())}


def render(value: dict[str, Any]) -> str:
    geometry = value["composed_bank2"]
    pair_value = value["frozen_pair_after"]
    return f"""# Block 3 r9 candidate resume

Status: **{value['status']}**

The fully attributed r9 pair is resurrected without a WPLTO or product link.
Candidate Scope and Qualification/Acceptance both pass over a phase-owned
projection whose ELF and PRG are byte-identical to the frozen evidence pair.
The earlier diagnostic Scope probe remains separately named and is not counted
as candidate qualification.

The candidate composed preflight proves all **{len(geometry['owners'])}** Bank-2
owners disjoint, both mapped VMAs unchanged, and the largest contiguous hole
as **{geometry['largest_contiguous_hole']['bytes']:,} bytes**.  Aggregate free
space is not used as placement capacity.

- ELF: `{pair_value['ELF']['sha256']}`
- PRG: `{pair_value['PRG']['sha256']}`

Accounting for this resume is zero WPLTOs, zero links, one candidate Scope and
one candidate Qualification/Acceptance.  Media remains a separate successor.
"""


def tuple_attribution() -> dict[str, Any]:
    R9.install(); R9.setup_child()
    golden = ACCEPT.acceptance_golden_gate(R9.ELF)
    require(golden["comparison"]["comparison"] ==
                "dependent-address-plus-freight-boundaries-exact"
            and golden["additive_card_freight"]["mapped_LMA_successor"]
                ["status"] == "passed",
            "pre-tuple Acceptance adapters are not green")
    registry_mutations = ACCEPT.additive_freight_mutations(R9.ELF)
    relocation_mutations = ACCEPT.mapped_lma_successor_mutations(R9.ELF)
    tuple_red = False
    try:
        GRAPH.linked_tuple_gate(R9.ELF)
    except RuntimeError as error:
        require(str(error) == "semantic MAP entry/arena relation drift",
                "MAP tuple failed for an unattributed reason")
        tuple_red = True
    require(tuple_red, "relocated r9 unexpectedly passed the historical tuple")

    truth = R9.ElfTruth.read(R9.ELF, llvm_readobj=R9.READOBJ,
                             include_section_data=True)
    enter = truth.symbol("c2_mapped_far_enter")
    section = truth.section(enter.section)
    raw = truth.section_bytes(enter.section)[
        enter.value - section.address:enter.value - section.address + enter.bytes]
    model = GRAPH._interpret_trampoline(raw)
    operation = model["map_operations"][0]
    decoded = GRAPH.MAP.decode_low(operation["A"], operation["X"])
    far = truth.section(".lisp65_c2_mapped_far_service")
    service = truth.symbol("c2_mapped_far_vm_code_load_converged")
    load_start = truth.symbol(
        "__lisp65_c2_mapped_far_service_load_start").value
    observed = GRAPH.MAP.map_low(service.value, decoded)
    expected = load_start + service.value - far.address
    require(operation == {"A": 0x40, "X": 0x82, "Y": 0, "Z": 0x80}
            and decoded["physical_offset"] == "0x24000"
            and observed == 0x2BA31 and expected == 0x2FA6B
            and expected - observed == 0x403A,
            "r9 MAP tuple attribution arithmetic drift")
    return {
        "status": "ATTRIBUTED: R9 LMA MOVE OUTRUNS EMITTED MAP TUPLE",
        "adapter_preconditions": {
            "product_cold_registry": "candidate-derived bank2-top placement",
            "v5_golden": "unchanged; one additive LMA boundary projected",
            "registry_mutations_rejected": registry_mutations,
            "relocation_mutations_rejected": relocation_mutations,
        },
        "emitted_tuple": {name: operation[name] for name in "AXYZ"},
        "decoded_tuple": decoded,
        "far_service": {"VMA": far.address, "bytes": far.bytes,
                        "LMA": load_start},
        "service_entry": {"VMA": service.value,
                          "tuple_physical": observed,
                          "candidate_required_physical": expected,
                          "difference_bytes": expected - observed},
        "mechanism": ("the upper-anchor link moves the Far-Service load image, "
                      "but c2_mapped_far_enter retains the historical MAP offset"),
        "product_defect_not_exonerated": True,
    }


def render_red(value: dict[str, Any]) -> str:
    result = value["MAP_tuple_attribution"]
    service = result["service_entry"]
    return f"""# Block 3 r9 candidate Qualification Final Red

Status: **{value['status']}**

Candidate Scope passes, and the composed Bank-2 gate proves eight disjoint
owners with an 11,494-byte largest hole.  Acceptance first exposed and closed
two stored-world adapters: Product-Cold's old physical-start registration and
v5's one fixed Far-Service load-start boundary.  The Golden itself remains
unchanged and both conversions carry reintroduction mutations.

Acceptance then reaches a genuine product mismatch.  The linked MAP entry
still emits tuple `A=$40/X=$82`, mapping the service VMA to
`${service['tuple_physical']:06X}`.  The relocated final-ELF LOADADDR requires
`${service['candidate_required_physical']:06X}`; the difference is
`${service['difference_bytes']:04X}` bytes.  Thus the upper-anchor linker move
relocated the Far-Service bytes without changing the runtime mapping that
makes those bytes visible.

No WPLTO or product link ran during resurrection.  One candidate Scope passed;
three read-only Acceptance attempts successively exposed the registry pin,
the Golden-boundary pin and this product defect.  No medium was built and no
device was contacted.  The r9 pair returns to review as frozen, unqualified
evidence; no fix or r10 is authorized by this receipt.
"""


def record_red() -> None:
    require(not RECEIPT.exists() and not FINAL_RED.exists()
            and SCOPE.is_file() and not ACCEPTANCE.exists()
            and load(SCOPE).get("status") == "PASS",
            "r9 candidate Final-Red lifecycle drift")
    before = pair(); projected = pair(PHASE_ELF, PHASE_PRG)
    require(same_pair(before, projected),
            "r9 Final-Red projection differs from frozen pair")
    result = tuple_attribution()
    after = pair()
    require(before == after, "Final-Red attribution changed frozen r9 pair")
    value = {
        "format": FORMAT + "-final-red", "recorded_on": "2026-08-26",
        "status": "FINAL RED: R9 SCOPE GREEN; MAP TUPLE MISSES RELOCATED SERVICE",
        "authority": authority(), "attribution": bind(ATTR.RECEIPT),
        "frozen_pair_before": before, "frozen_pair_after": after,
        "phase_projection": projected, "composed_bank2": composed_gate(),
        "candidate_scope": {"status": "PASS", "receipt": bind(SCOPE)},
        "candidate_qualification": {
            "status": "RED", "receipt_emitted": False,
            "failing_gate": "linked semantic MAP entry/arena relation"},
        "MAP_tuple_attribution": result,
        "attempt_accounting": {
            "prior_r9_WPLTO_runs": 1, "prior_r9_product_links": 1,
            "new_WPLTO_runs": 0, "new_product_links": 0,
            "candidate_scope_runs": 1, "candidate_acceptance_attempts": 3,
            "media_builds": 0, "device_contacts": 0},
        "pair_disposition": "FROZEN-UNQUALIFIED-PRODUCT-EVIDENCE",
        "next": "review disposition; no fix, r10, media or device authorized",
    }
    FINAL_RED.write_bytes(canonical(value))
    RED_REPORT.write_text(render_red(value), encoding="utf-8")
    print("Block3 r9 candidate: FINAL RED tuple=02ba31 expected=02fa6b "
          "WPLTO=0 link=0 media=0")


def check_red() -> None:
    value = load(FINAL_RED)
    require(value["status"] ==
                "FINAL RED: R9 SCOPE GREEN; MAP TUPLE MISSES RELOCATED SERVICE"
            and value["authority"] == authority()
            and value["frozen_pair_before"] == value["frozen_pair_after"] == pair()
            and value["composed_bank2"] == composed_gate()
            and value["MAP_tuple_attribution"] == tuple_attribution()
            and value["candidate_scope"]["receipt"] == bind(SCOPE)
            and value["attempt_accounting"]["new_WPLTO_runs"] == 0
            and value["attempt_accounting"]["new_product_links"] == 0
            and value["attempt_accounting"]["media_builds"] == 0
            and RED_REPORT.read_text(encoding="utf-8") == render_red(value),
            "r9 candidate Final-Red evidence drift")
    print("Block3 r9 candidate: FINAL RED CHECK PASS product-defect=open")


def resume() -> None:
    attribution = load(ATTR.RECEIPT)
    require(attribution["status"] ==
                "PASS: R8/R9 FROZEN PAIR FULLY ATTRIBUTED; OUTPUT ROOT REBOUND"
            and attribution["pair_disposition"] ==
                "FROZEN-EVIDENCE-AWAITING-REVIEW"
            and attribution["counterfactual_link_required"] is False,
            "r9 resurrection attribution authority drift")
    original_before = pair(); geometry_before = composed_gate()
    if not BUILD.exists():
        prepare_phase_projection()
    else:
        require(SCOPE.is_file() and not ACCEPTANCE.exists()
                and load(SCOPE).get("status") == "PASS"
                and same_pair(pair(PHASE_ELF, PHASE_PRG), original_before),
                "candidate resume retry is not the green-Scope/acceptance-red seam")
    projected_before = pair(PHASE_ELF, PHASE_PRG)
    processes = [{"action": "_scope", "status": "PASS",
                  "witness": "persisted candidate Scope from first tail attempt"},
                 run_child("_accept")]
    scope = load(SCOPE); acceptance = load(ACCEPTANCE)
    original_after = pair(); projected_after = pair(PHASE_ELF, PHASE_PRG)
    require(original_before == original_after
            and projected_before == projected_after
            and same_pair(original_after, projected_after)
            and scope.get("status") == acceptance.get("status") == "PASS",
            "read-only candidate qualification changed or rejected r9")
    geometry_after = composed_gate()
    require(geometry_before == geometry_after,
            "composed candidate geometry changed during qualification")
    output = (PHASE_BUILD /
              "wplto/fresh-c2-lite-prelink-gates/v6-semantics/"
              "initial.c2d-v6.bin")
    require(output.is_file(), "candidate phase-owned semantics output absent")
    value = {
        "format": FORMAT, "recorded_on": "2026-08-26", "status": STATUS,
        "authority": authority(), "attribution": bind(ATTR.RECEIPT),
        "frozen_pair_before": original_before,
        "frozen_pair_after": original_after,
        "phase_projection_before": projected_before,
        "phase_projection_after": projected_after,
        "composed_bank2": geometry_after,
        "diagnostic_scope_probe": {
            "receipt": attribution["read_only_scope_probe"]["receipt"],
            "classification": "diagnostic only; not reused as candidate Scope"},
        "candidate_scope": {"status": scope["status"], "receipt": bind(SCOPE)},
        "candidate_qualification": {
            "status": acceptance["status"], "receipt": bind(ACCEPTANCE)},
        "phase_owned_semantics": bind(output), "processes": processes,
        "attempt_accounting": {
            "prior_r9_WPLTO_runs": 1, "prior_r9_product_links": 1,
            "new_WPLTO_runs": 0, "new_product_links": 0,
            "diagnostic_scope_probes": 1, "candidate_scope_runs": 1,
            "candidate_qualification_runs": 1, "media_builds": 0,
            "device_contacts": 0},
        "pair_disposition": "RESURRECTED-BLOCK3-R9-CANDIDATE",
        "media_authorized_by_review": True,
        "claim_limit": "Candidate host qualification; no media/device claim.",
    }
    RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(render(value), encoding="utf-8")
    print("Block3 r9 candidate: PASS Scope=PASS Qualification=PASS "
          "owners=8 hole=11494 WPLTO=0 link=0")


def validate(value: dict[str, Any], *, live: bool) -> None:
    require(value["status"] == STATUS
            and value["authority"] == authority()
            and value["pair_disposition"] == "RESURRECTED-BLOCK3-R9-CANDIDATE"
            and value["frozen_pair_before"] == value["frozen_pair_after"]
            and value["phase_projection_before"] ==
                value["phase_projection_after"]
            and value["candidate_scope"]["status"] == "PASS"
            and value["candidate_qualification"]["status"] == "PASS"
            and value["attempt_accounting"]["new_WPLTO_runs"] == 0
            and value["attempt_accounting"]["new_product_links"] == 0
            and len(value["composed_bank2"]["owners"]) == 8
            and not value["composed_bank2"]["overlaps"]
            and value["composed_bank2"]["largest_contiguous_hole"]["bytes"]
                == 11494,
            "r9 candidate resume receipt drift")
    if live:
        require(value["frozen_pair_after"] == pair()
                and value["phase_projection_after"] == pair(
                    PHASE_ELF, PHASE_PRG)
                and value["composed_bank2"] == composed_gate()
                and value["candidate_scope"]["receipt"] == bind(SCOPE)
                and value["candidate_qualification"]["receipt"] ==
                    bind(ACCEPTANCE)
                and REPORT.read_text(encoding="utf-8") == render(value),
                "r9 live candidate evidence drift")


def check() -> None:
    value = load(RECEIPT); validate(value, live=True)
    print("Block3 r9 candidate: CHECK PASS pair=resurrected media=authorized")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("resume", "check", "record-red",
                                           "check-red", "_scope", "_accept"))
    action = parser.parse_args().action
    {"resume": resume, "check": check, "record-red": record_red,
     "check-red": check_red, "_scope": scope_child,
     "_accept": acceptance_child}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Block3 r9 candidate: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
