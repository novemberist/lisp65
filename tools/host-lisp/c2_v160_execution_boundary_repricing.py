#!/usr/bin/env python3
"""Reprice the v1.6 retired-window execution-boundary backstop."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))
import c2_transitive_map_nesting_gate as MAP_GATE  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
ELF = ROOT / ("build/c2.3/v1.6-boot-refill-generator-template-card/wplto/"
              "lisp65-c2-substitution-linked.prg.elf")
MEMBERSHIP = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                     "c2.3-v1.6-boot-path-followup-result.json")
OLD_PRICE = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                    "c2.3-v1.6-retired-window-carrier-inversion-study.json")
OUT = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
              "c2.3-v1.6-execution-boundary-repricing.json")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
CLANG = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
AUTHORITY = "d168fc82"
FORMAT = "lisp65-c2.3-v1.6-execution-boundary-repricing-v1"
EXPECTED_ELF = "02209a9ddda93b49bc3025f6b0caa9b2d88cb96b2504167b3ccc98d6f9ffba99"
WINDOW = (0xC356, 0xCA91)
E000 = (0xE000, 0xFF80)


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    full = subprocess.run(["git", "rev-parse", f"{AUTHORITY}^{{commit}}"],
                          cwd=ROOT, check=True, text=True,
                          stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(["git", "show", f"{full}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    compact = " ".join(raw.decode().lower().split())
    for token in ("execution-boundary backstop moves into v1.6",
                  "host-only re-pricing first", "minimal in-range pc test",
                  "reusing the existing recovery path", "transitive map-nesting gate"):
        require(token in compact, f"pricing authority token absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": sha(raw)}


def source(truth: ElfTruth) -> str:
    sym = {name: truth.symbol(name).value for name in (
        "rtov_busy", "rtov_loaded_len", "lisp_toplevel_active", "pending_code",
        "pending_symbol", "lisp_toplevel", "longjmp")}
    start, end = (truth.symbol(name).value for name in (
        "__lisp65_workbench_overlay_start", "__lisp65_workbench_overlay_end"))
    require((start, end) == WINDOW, "candidate overlay interval drift")
    # The hardware frame is observed after the IRQ handler's A/X/Y/Z pushes:
    # P at SP+5 and continuation low/high at SP+6/+7.  Subtracting the first
    # valid continuation (window_start+2) makes the interval test nine bytes
    # smaller than the historical branch ladder while preserving both edges.
    return f"""
        .section .text.retired_window_brk_classifier,"ax",@progbits
        .globl retired_window_brk_classifier
        .type retired_window_brk_classifier,@function
retired_window_brk_classifier:
        tsx
        lda $0105,x
        and #$10
        beq .Lnot_ours
        lda ${sym['rtov_busy']:02x}
        ora ${sym['rtov_loaded_len']:02x}
        ora ${sym['rtov_loaded_len'] + 1:02x}
        bne .Lnot_ours
        lda ${sym['lisp_toplevel_active']:02x}
        beq .Lnot_ours
        lda $0106,x
        sec
        sbc #${(start + 2) & 0xff:02x}
        tay
        lda $0107,x
        sbc #${(start + 2) >> 8:02x}
        bcc .Lnot_ours
        cmp #${(end - start) >> 8:02x}
        bcc .Laccept
        bne .Lnot_ours
        cpy #${(end - start) & 0xff:02x}
        bcs .Lnot_ours
.Laccept:
        lda #mos16lo(retired_window_resume)
        sta $0106,x
        lda #mos16hi(retired_window_resume)
        sta $0107,x
        jmp retired_window_irq_return
.Lnot_ours:
        jmp c2_kernal_fail_closed
        .size retired_window_brk_classifier, .-retired_window_brk_classifier

        .section .text.retired_window_resume,"ax",@progbits
        .globl retired_window_resume
        .type retired_window_resume,@function
retired_window_resume:
        lda ${sym['pending_code']:02x}
        bne .Lpending
        lda #62
        sta ${sym['pending_code']:02x}
        stz ${sym['pending_symbol']:04x}
        stz ${sym['pending_symbol'] + 1:04x}
.Lpending:
        lda #mos16lo(${sym['lisp_toplevel']:04x})
        sta $04
        lda #mos16hi(${sym['lisp_toplevel']:04x})
        sta $05
        lda #1
        ldx #0
        jmp ${sym['longjmp']:04x}
        .size retired_window_resume, .-retired_window_resume
"""


def assembled(truth: ElfTruth) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="c2-v160-backstop-price-") as raw:
        root = Path(raw); asm = root / "price.s"; obj = root / "price.o"
        asm.write_text(source(truth), encoding="utf-8")
        subprocess.run([str(CLANG), "-c", str(asm), "-o", str(obj)], cwd=ROOT,
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        priced = ElfTruth.read(obj, llvm_readobj=READOBJ, include_section_data=True)
        classifier = priced.symbol("retired_window_brk_classifier")
        landing = priced.symbol("retired_window_resume")
        return {"classifier_bytes": classifier.bytes,
                "cleanup_free_landing_bytes": landing.bytes,
                "gross_ordinary_text_bytes": classifier.bytes + landing.bytes,
                "new_E000_bytes": 0, "new_far_service_bytes": 0,
                "new_state_bytes": 0,
                "classifier_sha256": sha(priced.section_bytes(classifier.section)),
                "landing_sha256": sha(priced.section_bytes(landing.section))}


def e000_geometry(truth: ElfTruth) -> dict[str, Any]:
    rows = sorted((max(E000[0], row.address), min(E000[1], row.address + row.bytes),
                   row.name) for row in truth.sections
                  if "SHF_ALLOC" in row.flags and row.bytes
                  and row.address < E000[1] and row.address + row.bytes > E000[0])
    merged: list[list[int]] = []
    for first, last, _name in rows:
        if merged and first <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], last)
        else:
            merged.append([first, last])
    holes = []
    cursor = E000[0]
    for first, last in merged:
        if cursor < first:
            holes.append([cursor, first])
        cursor = max(cursor, last)
    if cursor < E000[1]:
        holes.append([cursor, E000[1]])
    return {"free_total_bytes": sum(last - first for first, last in holes),
            "largest_contiguous_hole_bytes": max(last - first for first, last in holes),
            "holes": [{"first": f"0x{first:04x}", "last_exclusive": f"0x{last:04x}",
                       "bytes": last - first} for first, last in holes]}


def classify(*, stacked_p: int, continuation: int, busy: int,
             loaded_len: int, active: int) -> str:
    opcode = (continuation - 2) & 0xffff
    if (stacked_p & 0x10 and not busy and not loaded_len and active
            and WINDOW[0] <= opcode < WINDOW[1]):
        return "recover-to-prompt"
    return "existing-fail-closed-policy"


def cases() -> list[dict[str, Any]]:
    definitions = [
        ("boot-holder-at-window-entry", 0x32, 0xC358, 0, 0, 1, "recover-to-prompt"),
        ("last-window-byte", 0x32, 0xCA92, 0, 0, 1, "recover-to-prompt"),
        ("below-window", 0x32, 0xC357, 0, 0, 1, "existing-fail-closed-policy"),
        ("above-window", 0x32, 0xCA93, 0, 0, 1, "existing-fail-closed-policy"),
        ("hardware-irq", 0x22, 0xC358, 0, 0, 1, "existing-fail-closed-policy"),
        ("live-window", 0x32, 0xC358, 1, 100, 1, "existing-fail-closed-policy"),
        ("no-toplevel", 0x32, 0xC358, 0, 0, 0, "existing-fail-closed-policy"),
    ]
    result = []
    for name, p, pc, busy, length, active, expected in definitions:
        observed = classify(stacked_p=p, continuation=pc, busy=busy,
                            loaded_len=length, active=active)
        require(observed == expected, f"boundary case drift: {name}")
        result.append({"name": name, "expected": expected, "observed": observed})
    return result


def derive() -> dict[str, Any]:
    inputs = {"ELF": bind(ELF), "membership": bind(MEMBERSHIP),
              "historical_price": bind(OLD_PRICE)}
    require(inputs["ELF"]["sha256"] == EXPECTED_ELF, "candidate ELF drift")
    require(load(MEMBERSHIP)["membership_decision"]["instance_ordinal"] == 3,
            "owner decision lacks third-instance premise")
    old = load(OLD_PRICE)["assembled_price"]
    require(old["classifier_E000_bytes"] == 69
            and old["cleanup_free_landing_ordinary_text_bytes"] == 29,
            "historical backstop price drift")
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    price = assembled(truth)
    require(price == {"classifier_bytes": 60, "cleanup_free_landing_bytes": 29,
                      "gross_ordinary_text_bytes": 89, "new_E000_bytes": 0,
                      "new_far_service_bytes": 0, "new_state_bytes": 0,
                      "classifier_sha256": price["classifier_sha256"],
                      "landing_sha256": price["landing_sha256"]},
            "assembled current-world price drift")
    text = truth.section(".text")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    ordinary_free = facade.address - (text.address + text.bytes)
    e000 = e000_geometry(truth)
    far = truth.section(".lisp65_c2_mapped_far_service")
    require(ordinary_free == 117 and e000["free_total_bytes"] == 57
            and e000["largest_contiguous_hole_bytes"] == 49
            and 1499 - far.bytes == 15, "current capacity world drift")
    require(ordinary_free - price["gross_ordinary_text_bytes"] == 28,
            "ordinary fit arithmetic drift")

    fail = truth.symbol("c2_kernal_fail_closed")
    irq_section = truth.section(".lisp65_c2_kernal_window.irq_handler")
    edges = [row for row in truth.relocations
             if row.source_section == irq_section.name
             and truth.relocation_target_identity(row).get("resolved_value") == fail.value]
    require(len(edges) == 1 and edges[0].offset == 0xE07B,
            "IRQ fail-closed seam drift")
    irq_raw = truth.section_bytes(irq_section.name)
    require(irq_raw[0xE07A - irq_section.address] == 0x4c,
            "IRQ seam is not a same-size JMP")
    map_result = MAP_GATE.check(ELF)
    require(map_result["violations"] == [], "current transitive MAP gate red")

    return {
        "format": FORMAT, "status": "PRICED: FITS ORDINARY TEXT WITH 28 BYTES FREE",
        "recorded_on": "2026-08-23", "authority": authority(), "inputs": inputs,
        "assembled_price": price,
        "price_delta_from_historical": {
            "classifier": "69 E000 -> 60 ordinary bytes",
            "landing": "29 ordinary bytes unchanged",
            "gross": "98 -> 89 bytes",
            "reason": ("subtract-and-range comparison saves nine classifier bytes; the existing "
                       "same-size IRQ JMP is retargeted, so E000 grows by zero"),
        },
        "placement": {
            "winner": "both classifier and cleanup-free longjmp adapter in ordinary .text",
            "IRQ_change": "retarget existing three-byte JMP; zero section growth",
            "ordinary_before_free_bytes": ordinary_free,
            "ordinary_after_free_bytes": ordinary_free - price["gross_ordinary_text_bytes"],
            "E000": e000, "E000_delta_bytes": 0,
            "far_service_free_bytes": 1499 - far.bytes, "far_service_delta_bytes": 0,
            "why_visible": ("ordinary text is permanently visible; non-baseline MAP readers "
                            "already exclude IRQs, and the transitive MAP gate remains an input"),
        },
        "semantics": {
            "classifier": ("B=1, retired state busy|loaded_len == 0, active toplevel, and "
                           "stacked continuation-2 in candidate-derived [$c356,$ca91)"),
            "recovery": ("rewrite stacked continuation to an ordinary-text adapter; preserve an "
                         "existing pending error or synthesize E3e, then enter the existing "
                         "longjmp path directly without recursive cleanup"),
            "negative_domain": ("hardware IRQs, live-window BRKs, out-of-range BRKs and no-"
                                "toplevel states retain fail-closed behavior"),
            "cases": cases(),
        },
        "standing_walls": {
            "transitive_MAP_gate": map_result,
            "final_ELF_required": True,
            "candidate_derived_addresses": True,
            "carrier_prevention_retained": True,
            "recursive_cleanup_forbidden": True,
        },
        "execution": {"WPLTO_runs": 0, "product_links": 0,
                      "media_builds": 0, "device_contacts": 0},
        "claim_limit": ("Host-only assembled repricing. It proves fit and the implementation "
                        "shape; it does not itself emit or qualify a product."),
    }


def selftest() -> None:
    value = derive()
    mutations = [
        lambda row: row["placement"].update(E000_delta_bytes=1),
        lambda row: row["placement"].update(ordinary_after_free_bytes=-1),
        lambda row: row["semantics"]["cases"][2].update(observed="recover-to-prompt"),
    ]
    for mutate in mutations:
        trial = json.loads(json.dumps(value)); mutate(trial)
        accepted = (trial["placement"]["E000_delta_bytes"] == 0
                    and trial["placement"]["ordinary_after_free_bytes"] >= 0
                    and trial["semantics"]["cases"][2]["observed"]
                        == "existing-fail-closed-policy")
        require(not accepted, "repricing mutation accepted")
    print(f"v1.6 execution-boundary repricing: SELFTEST PASS mutations={len(mutations)}")


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in {"write", "check", "selftest"},
            "usage: c2_v160_execution_boundary_repricing.py write|check|selftest")
    if sys.argv[1] == "selftest":
        selftest(); return 0
    value = derive(); encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if sys.argv[1] == "write":
        OUT.write_text(encoded, encoding="utf-8")
    else:
        require(OUT.is_file() and OUT.read_text(encoding="utf-8") == encoded,
                "execution-boundary repricing receipt drift")
    print("v1.6 execution-boundary repricing: PASS price=89B ordinary-free=28")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PricingError, OSError, ValueError, KeyError,
            subprocess.CalledProcessError) as error:
        print(f"v1.6 execution-boundary repricing: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
