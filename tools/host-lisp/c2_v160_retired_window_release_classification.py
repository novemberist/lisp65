#!/usr/bin/env python3
"""Classify the retired-window backstop as regression or inherited defect."""

from __future__ import annotations

from collections import defaultdict, deque
import copy
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

from elf_truth import ElfTruth  # noqa: E402


AUTHORITY = "46ddd514"
FORMAT = "lisp65-c2.3-v1.6-retired-window-release-classification-v1"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
V15_ELF = ROOT / ("build/release-v1.5.0/pack-product-b/lisp65-1.5.0/"
                  "proof/product/lisp65-c2-lite-product.elf")
V16_ELF = ROOT / ("build/c2.3/v1.6-bound-origin-fragmentation-second-"
                  "replacement-card/wplto/lisp65-c2-substitution-linked.prg.elf")
PUBLICATION = ROOT / ("tests/bytecode/dialect-v2/evidence/post-release/"
                      "v150-public-publication-receipt-20260818.json")
INVERSION = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                    "c2.3-v1.6-retired-window-carrier-inversion-study.json")
OUT = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
              "c2.3-v1.6-retired-window-release-classification.json")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
V15_SHA = "4f899d1e0c9bcc89d14c9d13c5384e6a843c4093ba9d1029b321820a11bf4942"
V16_SHA = "8bb00fd560ddfef9b4f1da5d6269e134de8dc6548a33e3659eb79fc580fecd45"


class ClassificationError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ClassificationError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def authority() -> dict[str, Any]:
    path = PLAN.relative_to(ROOT).as_posix()
    commit = subprocess.run(
        ["git", "rev-parse", f"{AUTHORITY}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().split())
    for token in ("regression or a pre-existing product defect",
                  "can the backstop be smaller",
                  "only if 1 says \"blocks\" and 2 does not fit",
                  "decide from the shipped v1.5 artifacts"):
        require(token in text, f"commission token absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": path,
            "bytes": len(raw), "sha256": sha(raw)}


def symbol_bytes(truth: ElfTruth, name: str) -> bytes:
    symbol = truth.symbol(name)
    section = truth.section(symbol.section)
    start = symbol.value - section.address
    return truth.section_bytes(symbol.section)[start:start + symbol.bytes]


def call_graph(truth: ElfTruth) -> tuple[dict[str, set[str]], dict[tuple[str, str], list[int]]]:
    functions = [row for row in truth.symbols
                 if row.symbol_type == "Function" and row.bytes]
    by_section: dict[str, list[Any]] = defaultdict(list)
    by_identity: dict[tuple[str, int], list[Any]] = defaultdict(list)
    for row in functions:
        by_section[row.section].append(row)
        by_identity[(row.section, row.value)].append(row)
    for rows in by_section.values():
        rows.sort(key=lambda item: item.value)

    def owner(section: str, pc: int) -> Any | None:
        return next((row for row in by_section.get(section, ())
                     if row.value <= pc < row.value + row.bytes), None)

    edges: dict[str, set[str]] = defaultdict(set)
    sites: dict[tuple[str, str], list[int]] = defaultdict(list)
    for relocation in truth.relocations:
        identity = truth.relocation_target_identity(relocation)
        value = identity.get("resolved_value")
        section = identity.get("section")
        key = (section, value)
        if not isinstance(section, str) or not isinstance(value, int) \
                or len(by_identity.get(key, ())) != 1:
            continue
        source = owner(relocation.source_section, relocation.offset - 1)
        if source is None:
            continue
        target = by_identity[key][0]
        edges[source.name].add(target.name)
        sites[(source.name, target.name)].append(relocation.offset - 1)
    return edges, sites


def shortest_path(edges: dict[str, set[str]], start: str,
                  goals: set[str]) -> list[str]:
    queue = deque([(start, [start])])
    seen = {start}
    while queue:
        node, path = queue.popleft()
        if node in goals and node != start:
            return path
        for successor in sorted(edges.get(node, ())):
            if successor not in seen:
                seen.add(successor)
                queue.append((successor, path + [successor]))
    raise ClassificationError(f"no call path from {start} to {sorted(goals)}")


def target_origins(truth: ElfTruth, target: int) -> list[dict[str, Any]]:
    result = []
    for row in truth.relocations:
        identity = truth.relocation_target_identity(row)
        if identity.get("resolved_value") != target:
            continue
        section = truth.section(row.source_section)
        data = truth.section_bytes(row.source_section)
        pc = row.offset - 1
        at = pc - section.address
        result.append({"section": row.source_section, "opcode_address": pc,
                       "relocation": row.offset,
                       "opcode": data[at] if 0 <= at < len(data) else None})
    return result


def derive() -> dict[str, Any]:
    inputs = {"v1.5_shipped_ELF": bind(V15_ELF),
              "v1.6_first_red_ELF": bind(V16_ELF),
              "v1.5_publication_receipt": bind(PUBLICATION),
              "inversion_study": bind(INVERSION)}
    require(inputs["v1.5_shipped_ELF"]["sha256"] == V15_SHA,
            "shipped v1.5 ELF identity drift")
    require(inputs["v1.6_first_red_ELF"]["sha256"] == V16_SHA,
            "v1.6 First-Red ELF identity drift")
    published = json.loads(PUBLICATION.read_text(encoding="utf-8"))
    require(published["product_authority"]["linked_elf_sha256"] == V15_SHA,
            "publication receipt does not bind the inspected v1.5 ELF")

    v15 = ElfTruth.read(V15_ELF, llvm_readobj=READOBJ,
                        include_section_data=True)
    v16 = ElfTruth.read(V16_ELF, llvm_readobj=READOBJ,
                        include_section_data=True)
    start15 = v15.symbol("__lisp65_workbench_overlay_start").value
    end15 = v15.symbol("__lisp65_workbench_overlay_end").value
    start16 = v16.symbol("__lisp65_workbench_overlay_start").value
    end16 = v16.symbol("__lisp65_workbench_overlay_end").value
    require((start15, end15) == (start16, end16) == (0xC356, 0xCA91),
            "runtime-overlay interval differs")

    phase = "c2_append_reserve_transient_code_phase"
    phase15 = symbol_bytes(v15, phase)
    phase16 = symbol_bytes(v16, phase)
    overlay15 = symbol_bytes(v15, "c2_overlay_call")
    overlay16 = symbol_bytes(v16, "c2_overlay_call")
    require(phase15 == phase16 and len(phase15) == 1470,
            "transient reserve phase is not byte-identical")
    require(overlay15 == overlay16 and len(overlay15) == 29,
            "resident overlay-call seam is not byte-identical")
    origin15 = target_origins(v15, 0xC8B5)
    origin16 = target_origins(v16, 0xC8B5)
    expected_origin = [{"section": ".lisp65_rt_c2append_reserve_transient_code",
                        "opcode_address": 0xC7EB, "relocation": 0xC7EC,
                        "opcode": 0x4C}]
    require(origin15 == origin16 == expected_origin,
            "0xc8b5 origin differs between release worlds")

    edges15, sites15 = call_graph(v15)
    error_path = shortest_path(edges15, phase,
                               {"lisp_abort_code", "lisp_abort_symbol"})
    require(error_path == [phase, "c2_stage_crc", "ext_disk_get",
                           "ext_dma_read_or_abort", "lisp_abort_code"],
            "shipped overlay-to-abort path drift")
    required_sites = {
        "lisp_abort_to_cleanup": sites15[("lisp_abort_symbol",
                                           "c2_product_abort_cleanup")],
        "cleanup_to_wipe": sites15[("c2_product_abort_cleanup", "rtov_wipe")],
        "cleanup_to_abort_driver": sites15[("c2_product_abort_cleanup",
                                             "c2_abort_driver")],
        "abort_driver_to_overlay": sites15[("c2_abort_driver",
                                             "c2_overlay_call")],
        "abort_driver_to_overlay_range": sites15[("c2_abort_driver",
                                                   "c2_overlay_call_range")],
        "ordinary_eval_error": sites15[("eval", "lisp_abort_code")],
    }
    require(required_sites == {
        "lisp_abort_to_cleanup": [0x2E8C],
        "cleanup_to_wipe": [0x2EA7],
        "cleanup_to_abort_driver": [0x2EC3],
        "abort_driver_to_overlay": [0xFF2D],
        "abort_driver_to_overlay_range": [0xFF43],
        "ordinary_eval_error": [0xA204],
    }, "shipped v1.5 cleanup/overlay choreography drift")
    require(v15.symbol("c2_abort_driver").bytes
            == v16.symbol("c2_abort_driver").bytes == 134,
            "abort-driver body size drift")
    require("c2_rtov_retire_continuations" not in v15.symbols_by_name
            and "c2_rtov_retire_continuations" in v16.symbols_by_name,
            "liveness successor direction drift")

    return {
        "format": FORMAT,
        "recorded_on": "2026-08-21",
        "status": "PRE-EXISTING V1.5 PRODUCT DEFECT; NOT A V1.6 REGRESSION",
        "authority": authority(),
        "inputs": inputs,
        "decision": {
            "question_1": "pre-existing-product-defect",
            "v1.6_release_effect": "items 1 and 2 are not blocked by this class",
            "known_issue": "required for v1.6 release documentation",
            "successor": "v1.7 constructive-retirement backstop",
            "question_2": "SKIPPED: question 1 made v1.6 capacity pricing unnecessary",
            "question_3": "SKIPPED: question 1 did not say blocks",
        },
        "same_mechanism": {
            "overlay_interval": [start15, end15],
            "transient_phase": {"bytes": len(phase15), "sha256": sha(phase15),
                                "byte_identical": True},
            "resident_overlay_call": {"bytes": len(overlay15),
                                      "sha256": sha(overlay15),
                                      "byte_identical": True},
            "c8b5_static_origins_v1.5": origin15,
            "c8b5_static_origins_v1.6": origin16,
            "abort_driver_bytes_both": 134,
        },
        "v1.5_reachability": {
            "ordinary_eval_error_site": "eval+0x4c2@0xa204 -> lisp_abort_code",
            "overlay_error_path": error_path,
            "cleanup_and_reentry_sites": required_sites,
            "proof": ("the shipped final ELF can enter the byte-identical "
                      "transient phase, reach the ordinary abort path, wipe "
                      "the active window, and run the abort driver's overlay "
                      "calls; it has no retirement-liveness sanitizer or "
                      "execution-boundary backstop"),
        },
        "v1.6_delta_classification": {
            "new_prevention": "continuation/active-frame sanitation, incomplete but protective",
            "relocation": "same 134-byte abort driver moved from E000 to far service",
            "new_trigger_needed": False,
            "reason": ("ordinary undefined-function evaluation and the "
                       "abort/overlay choreography already exist in v1.5"),
        },
        "claim_limit": ("Host/ELF reachability classification only. The exact "
                        "0xc8b5 device symptom was observed on v1.6, not replayed "
                        "on v1.5 hardware. No product fix, link, media or device "
                        "action is authorized."),
        "execution": {"WPLTO_runs": 0, "product_links": 0,
                      "media_builds": 0, "device_contacts": 0},
    }


def validate(value: dict[str, Any]) -> None:
    require(value["format"] == FORMAT,
            "release-classification format drift")
    decision = value["decision"]
    require(decision["question_1"] == "pre-existing-product-defect"
            and "SKIPPED" in decision["question_2"]
            and "SKIPPED" in decision["question_3"],
            "ordered decision drift")
    mechanism = value["same_mechanism"]
    require(mechanism["overlay_interval"] == [0xC356, 0xCA91]
            and mechanism["transient_phase"]["bytes"] == 1470
            and mechanism["transient_phase"]["byte_identical"] is True
            and mechanism["resident_overlay_call"]["bytes"] == 29
            and mechanism["resident_overlay_call"]["byte_identical"] is True
            and mechanism["c8b5_static_origins_v1.5"]
                == mechanism["c8b5_static_origins_v1.6"],
            "same-mechanism proof drift")
    reach = value["v1.5_reachability"]
    require(reach["overlay_error_path"][-1] == "lisp_abort_code"
            and reach["cleanup_and_reentry_sites"]["cleanup_to_wipe"]
            and reach["cleanup_and_reentry_sites"]["abort_driver_to_overlay"],
            "v1.5 reachability proof drift")
    require(value["execution"] == {"WPLTO_runs": 0, "product_links": 0,
                                    "media_builds": 0, "device_contacts": 0},
            "host-only boundary drift")


def selftest(value: dict[str, Any]) -> int:
    mutations = []
    for name, mutate in (
        ("call-it-v1.6-regression",
         lambda row: row["decision"].__setitem__("question_1", "v1.6-regression")),
        ("price-question-2-anyway",
         lambda row: row["decision"].__setitem__("question_2", "RUN")),
        ("drop-byte-identity",
         lambda row: row["same_mechanism"]["transient_phase"].__setitem__(
             "byte_identical", False)),
        ("drop-v1.5-abort-path",
         lambda row: row["v1.5_reachability"].__setitem__(
             "overlay_error_path", ["c2_append_reserve_transient_code_phase"])),
    ):
        candidate = copy.deepcopy(value)
        mutate(candidate)
        try:
            validate(candidate)
        except ClassificationError:
            mutations.append(name)
    require(len(mutations) == 4, "release-classification mutation escaped")
    return len(mutations)


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in {"write", "check", "selftest"},
            "usage: c2_v160_retired_window_release_classification.py write|check|selftest")
    if sys.argv[1] == "write":
        value = derive()
        OUT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    else:
        require(OUT.is_file(), "sealed release-classification receipt absent")
        value = json.loads(OUT.read_text(encoding="utf-8"))
    validate(value)
    mutations = selftest(value) if sys.argv[1] == "selftest" else 0
    suffix = f" mutations={mutations}" if mutations else ""
    print("v1.6 retired-window release classification: PASS "
          f"verdict=pre-existing-v1.5 q2=skip q3=skip{suffix}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ClassificationError, OSError, KeyError, ValueError,
            subprocess.CalledProcessError) as error:
        print(f"v1.6 retired-window release classification: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
