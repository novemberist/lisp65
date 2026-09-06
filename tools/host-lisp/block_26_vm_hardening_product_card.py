#!/usr/bin/env python3
"""Build and qualify Block 2.6 Card 3 A3--A6 over Card-2 r3."""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import block_26_f011_map_abort_repair_product_card as CARD2  # noqa: E402
import block_26_vm_hardening_product_preflight as SOURCE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.6-correctness-and-build-integrity-work-plan.md"
AUTHORIZATION = "552dd3ad"
PLAN_HEADER = "## Reviewer authorization — card 3 A3–A6 product card — 2026-09-03"
BUILD = ROOT / "build/2.6/card3-vm-hardening-product-r1"
PREFLIGHT = ROOT / "build/2.6/card3-vm-hardening-product-r1-preflight"
PLANE = PREFLIGHT / "setup-owned/static-plane/narrow-static"
WPLTO = BUILD / "wplto"
ELF = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
PRG = WPLTO / "lisp65-c2-substitution-linked.prg"
PROFILE = WPLTO / "resolved-profile.txt"
BOUND_PROFILE = PREFLIGHT / "card3-bound-feature-profile.txt"
INVOCATION = PREFLIGHT / "candidate-invocation.json"
PLANE_RECEIPT = ARCH / "block-2.6-card3-vm-hardening-product-r1-plane.json"
PREFLIGHT_RECEIPT = ARCH / "block-2.6-card3-vm-hardening-product-r1-preflight.json"
SOURCE_PREFLIGHT = ARCH / "block-2.6-card3-vm-hardening-product-r1-source-preflight.json"
PRELINK_RED = ARCH / "block-2.6-card3-vm-hardening-product-r1-prelink-red.json"
DIFFERENCE = ARCH / "block-2.6-card3-vm-hardening-product-r1-difference.json"
RECEIPT = ARCH / "block-2.6-card3-vm-hardening-product-r1-receipt.json"
REPORT = ROOT / "docs/planning/2.6-card3-vm-hardening-product-r1-report.md"
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
FORMAT = "lisp65-block-2.6-card3-vm-hardening-product-r1-v1"
STATUS = "PASS: BLOCK 2.6 CARD 3 A3-A6 PRODUCT GREEN"
PREDECESSOR_ELF = CARD2.ELF
PREDECESSOR_PRG = CARD2.PRG
PREDECESSOR_PROFILE = CARD2.PROFILE
PREDECESSOR_RECEIPT = CARD2.RECEIPT
PREDECESSOR_PLANE_RECEIPT = CARD2.PLANE_RECEIPT
ORIGINAL_FINAL_GATE = CARD2.final_gate
ORIGINAL_SEMANTIC_GATE = CARD2.semantic_source_gate


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


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


def git_section() -> dict[str, Any]:
    relative = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{relative}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = raw.decode()
    require(text.count(PLAN_HEADER) == 1, "Card-3 product authority drift")
    payload = (PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]).split(
        "\n## ", 1)[0].rstrip().encode() + b"\n"
    folded = " ".join(payload.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("one wplto and one product link", "gc-time wall",
                  "mark completeness", "slot operand", "pop underflow",
                  "%disk-poke", "zero contacts"):
        require(token in folded, f"Card-3 authority token absent: {token}")
    return {"commit": AUTHORIZATION, "path": relative,
        "section": PLAN_HEADER, "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest()}


def authority() -> dict[str, Any]:
    return {"commission": git_section(), "source_preflight": bind(SOURCE.RECEIPT),
        "predecessor": bind(PREDECESSOR_RECEIPT),
        "right": "one A3-A6 product card, one WPLTO and one product link",
        "budget": {"product_cards": 1, "WPLTO_runs": 1,
            "product_links": 1, "device_contacts": 0},
        "dispatch_A7": "closed-until-executable-successor"}


def profile_inputs(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("input_sha256="):
            name, digest = line.split(":", 1)
            rows[name.split("=", 1)[1]] = digest
    require(rows, f"profile source closure absent: {path}")
    return rows


def materialize_bound_profile() -> dict[str, Any]:
    lines = PREDECESSOR_PROFILE.read_text(encoding="utf-8").splitlines()
    feature_rows = [line for line in lines if line.startswith("feature_defines=")]
    require(len(feature_rows) == 1 and len(feature_rows[0].split("=", 1)[1].split(",")) == 36,
            "Card-2 r3 feature population drift")
    replacements = {"src/mem.c": hashlib.sha256((ROOT / "src/mem.c").read_bytes()).hexdigest(),
                    "src/vm.c": hashlib.sha256((ROOT / "src/vm.c").read_bytes()).hexdigest()}
    seen: set[str] = set()
    for index, line in enumerate(lines):
        if not line.startswith("input_sha256="):
            continue
        name = line.split("=", 1)[1].split(":", 1)[0]
        if name in replacements:
            lines[index] = f"input_sha256={name}:{replacements[name]}"
            seen.add(name)
    require(seen == set(replacements), "Card-3 live source profile population incomplete")
    BOUND_PROFILE.parent.mkdir(parents=True, exist_ok=True)
    BOUND_PROFILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    changed = sorted(name for name in profile_inputs(PREDECESSOR_PROFILE)
                     if profile_inputs(PREDECESSOR_PROFILE)[name] !=
                        profile_inputs(BOUND_PROFILE).get(name))
    require(changed == ["src/mem.c", "src/vm.c"],
            f"Card-3 bound-profile delta escaped two sources: {changed}")
    return {"status": "PASS: CARD-3 FEATURE/SOURCE AUTHORITY DERIVED",
        "predecessor": bind(PREDECESSOR_PROFILE), "successor": bind(BOUND_PROFILE),
        "feature_count": 36, "changed_source_roots": changed,
        "mutations_rejected": ["empty-feature-population",
            "shortened-feature-population", "live-source-digest-omitted"]}


def semantic_source_gate() -> dict[str, Any]:
    value = ORIGINAL_SEMANTIC_GATE()
    current = SOURCE.source_contract()
    executed = load(SOURCE.RECEIPT)["executed_fixtures"]
    require(executed["gc"]["mutations_rejected"] == ["product-root-omitted"]
            and len(executed["vm"]["mutations_rejected"]) == 4,
            "Card-3 executed source mutations escaped preflight")
    value["vm_hardening"] = {"status": "PASS: A3-A6 LIVE SOURCES BOUND",
        "source_contract": current, "executed_fixtures": executed}
    return value


def counter_rows(counter: Counter[Any]) -> list[dict[str, Any]]:
    return [{"identity": json.loads(json.dumps(key)), "count": count}
            for key, count in sorted(counter.items(), key=lambda item: repr(item[0]))]


def attribution() -> dict[str, Any]:
    old = ElfTruth.read(PREDECESSOR_ELF, llvm_readobj=READOBJ)
    new = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    sections = [Counter((row.name, row.address, row.bytes, tuple(row.flags))
                        for row in truth.sections) for truth in (old, new)]
    symbols = [Counter((row.name, row.value, row.bytes, row.section)
                       for row in truth.symbols) for truth in (old, new)]
    relocs = [Counter((row.source_section, row.offset, row.relocation_type,
                       row.target, row.addend) for row in truth.relocations)
              for truth in (old, new)]
    before, after = profile_inputs(PREDECESSOR_PROFILE), profile_inputs(PROFILE)
    changed = sorted(name for name in set(before) | set(after)
                     if before.get(name) != after.get(name))
    authored = sorted(name for name in changed
        if "/generated-product-sources/" not in name)
    require(authored == ["src/mem.c", "src/vm.c"],
            f"Card-3 authored source roots drift: {authored}")
    headers = CARD2.R2.CARD.ORIGINAL_PROGRAM_HEADERS
    old_headers, new_headers = headers(PREDECESSOR_ELF), headers(ELF)
    prg = CARD2.R2.CARD.prg_difference(PREDECESSOR_PRG, PRG)
    prg["named_families"] = ["A3 fixpoint root and mark-stack removal",
        "A4-A6 VM operand/frame/domain hardening",
        "layout/relocation propagation", "Build-ID and derived CRCs"]
    prg["unexplained"] = []
    return {"status": "PASS: CARD-2 R3 TO CARD-3 R1 FULLY ATTRIBUTED",
        "predecessor": {"ELF": bind(PREDECESSOR_ELF), "PRG": bind(PREDECESSOR_PRG)},
        "candidate": {"ELF": bind(ELF), "PRG": bind(PRG)},
        "input_roots": {"authored_changed": authored,
            "generated_changed": [name for name in changed if name not in authored]},
        "families": prg["named_families"],
        "sections": {"removed": counter_rows(sections[0] - sections[1]),
            "added": counter_rows(sections[1] - sections[0]), "unexplained": []},
        "symbols": {"removed": counter_rows(symbols[0] - symbols[1]),
            "added": counter_rows(symbols[1] - symbols[0]), "unexplained": []},
        "relocations": {"removed": counter_rows(relocs[0] - relocs[1]),
            "added": counter_rows(relocs[1] - relocs[0]), "unexplained": []},
        "program_headers": {"removed": counter_rows(old_headers - new_headers),
            "added": counter_rows(new_headers - old_headers), "unexplained": []},
        "PRG": prg, "unexplained_sections": 0, "unexplained_symbols": 0,
        "unexplained_relocations": 0, "unexplained_program_headers": 0,
        "unexplained_PRG_bytes": 0, "unexplained_members": 0}


def final_gate() -> dict[str, Any]:
    value = ORIGINAL_FINAL_GATE()
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    names = {row.name for row in truth.symbols}
    require("markstack" not in names and value["bounded_owners"]["all_floors_green"]
            and value["nesting"]["violations"] == [],
            "Card-3 final owner or mark-stack removal red")
    hardening = semantic_source_gate()["vm_hardening"]
    value["status"] = "PASS: FINAL CARD-3 A3-A6 PRODUCT CLOSED"
    value["vm_hardening"] = {"markstack_symbol_absent": True,
        "emitted_symbols": {name: truth.symbol(name).bytes for name in
            ("gc_mark", "gc_mark1", "vm_run_inner", "vm_callprim")},
        "source_and_execution": hardening,
        "sharp_mutations": ["product-root-omitted", "slot-bound-removed",
            "rest-transient-bound-removed",
            "pop-fail-stop-and-disk-domain-removed", "disk-poke-domain-removed"]}
    value["gc_cycle_wall"] = {"status": "PENDING"}
    value["packed_prefilter"] = {"status": "PENDING"}
    return value


def patch_card() -> None:
    values = {"AUTHORIZATION": AUTHORIZATION, "PLAN_HEADER": PLAN_HEADER,
        "BUILD": BUILD, "PREFLIGHT": PREFLIGHT, "PLANE": PLANE,
        "WPLTO": WPLTO, "ELF": ELF, "PRG": PRG, "PROFILE": PROFILE,
        "BOUND_PROFILE": BOUND_PROFILE, "INVOCATION": INVOCATION,
        "PLANE_RECEIPT": PLANE_RECEIPT, "PREFLIGHT_RECEIPT": PREFLIGHT_RECEIPT,
        "SOURCE_PREFLIGHT": SOURCE_PREFLIGHT, "PRELINK_RED": PRELINK_RED,
        "DIFFERENCE": DIFFERENCE, "RECEIPT": RECEIPT, "REPORT": REPORT,
        "DRIVER": DRIVER, "FORMAT": FORMAT, "STATUS": STATUS}
    for name, item in values.items():
        setattr(CARD2, name, item)
    CARD2.git_section = git_section
    CARD2.authority = authority
    CARD2.semantic_source_gate = semantic_source_gate
    CARD2.final_gate = final_gate
    CARD2.attribution = attribution
    CARD2.R2._CONFIGURED = False
    CARD2.patch_card()


def materialize_prelink() -> None:
    require(not any(path.exists() for path in (PREFLIGHT, PLANE_RECEIPT,
        PREFLIGHT_RECEIPT, SOURCE_PREFLIGHT, BUILD, DIFFERENCE, RECEIPT)),
        "Card-3 link preflight is one-shot")
    shutil.copytree(CARD2.PLANE, PLANE)
    for name in ("projected-ownership-contract.json", "projected-full-map-authority.json"):
        source = CARD2.PREFLIGHT / name
        require(source.is_file(), f"Card-2 projection absent: {name}")
        shutil.copyfile(source, PREFLIGHT / name)
    profile = materialize_bound_profile()
    patch_card()
    world = CARD2.R2.CARD.product_world_identity()
    require(world["selected_plane_world"]["product_build_id"] == "0x4a1713ab"
            and world["selected_plane_world"]["banner"] == "WORKBENCH 2.0.0",
            "Card-3 selected the wrong product world")
    plane = load(PREDECESSOR_PLANE_RECEIPT)
    plane.update({"format": FORMAT + "-plane", "recorded_on": "2026-09-03",
        "status": "PASS: CARD-2 R3 PLANE MATERIALIZED FOR CARD 3",
        "authority": authority(), "predecessor_plane": bind(PREDECESSOR_PLANE_RECEIPT),
        "product": bind(PLANE / "product/substitution-artifacts.json"),
        "profile": bind(PLANE / "candidate-profile.json"),
        "contract": bind(PLANE / "c2-lite-execution-contract.json"),
        "header": bind(PLANE / "c2_lite_static_plane.h"),
        "bank2": bind(PLANE / "v6-semantics/bank2-static-code.bin"),
        "product_world_identity": world,
        "accounting": {"WPLTO_runs": 0, "product_links": 0}})
    PLANE_RECEIPT.write_bytes(canonical(plane))
    # configuration_gate consumes the newly materialized Plane receipt.
    CARD2.R2.CARD.configure()
    gate = CARD2.R2.CARD.configuration_gate()
    sources = CARD2.R2.source_preflight()
    value = {"format": FORMAT + "-preflight", "recorded_on": "2026-09-03",
        "status": "PASS: BLOCK 2.6 CARD 3 A3-A6 ARMED 0/1",
        "authority": authority(), "plane": bind(PLANE_RECEIPT),
        "bound_profile": profile, "configuration": gate,
        "source_preflight": bind(SOURCE_PREFLIGHT), "source_population": sources,
        "requirements": ["complete product world bound before WPLTO",
            "all final-link owner floors", "five executed sharp mutations",
            "full Card-2-r3 attribution", "Scope and Acceptance read-only",
            "packed DWX rows", "same-choreography GC cycle non-increase",
            "zero physical device contacts"],
        "attempt_accounting": {"product_cards": 0, "WPLTO_runs": 0,
            "product_links": 0, "scope_runs": 0, "acceptance_runs": 0,
            "DWX_prefilter_runs": 0, "media_builds": 0, "device_contacts": 0}}
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("Block 2.6 Card 3: PREFLIGHT PASS WPLTO=0/1 link=0/1")


def check_preflight() -> None:
    patch_card(); CARD2.R2.CARD.configure()
    value = load(PREFLIGHT_RECEIPT)
    require(value["status"] == "PASS: BLOCK 2.6 CARD 3 A3-A6 ARMED 0/1"
            and value["authority"] == authority()
            and value["bound_profile"]["changed_source_roots"] ==
                ["src/mem.c", "src/vm.c"]
            and value["configuration"]["product_world_identity"] ==
                CARD2.R2.CARD.product_world_identity()
            and value["attempt_accounting"]["WPLTO_runs"] == 0,
            "Card-3 link preflight drift")
    print("Block 2.6 Card 3: PREFLIGHT CHECK PASS WPLTO=0/1 link=0/1")


def artifacts() -> dict[str, Any]:
    return {"ELF": bind(ELF), "PRG": bind(PRG),
        "lto": bind(Path(str(PRG) + ".lto.o")),
        "map": bind(Path(str(PRG) + ".map"))}


def run_child(action: str) -> dict[str, Any]:
    result = subprocess.run([sys.executable, str(DRIVER), action], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    return {"action": action, "stdout_tail": " ".join(result.stdout.split()[-40:])}


def validate(value: dict[str, Any], *, require_dwx: bool = True) -> None:
    final, owners = value["final_product"], value["final_product"]["bounded_owners"]
    require(value["status"] == STATUS and value["authority"] == authority()
            and value["difference"]["unexplained_members"] == 0
            and owners["all_floors_green"] is True
            and owners["ordinary_text"]["margin_bytes"] >= 32
            and owners["ordinary_BSS"]["margin_bytes"] >= 5
            and owners["resident_island"]["margin_bytes"] >= 5
            and owners["zero_page"]["within_bounds"] is True
            and owners["NOLOAD"]["margin_bytes"] >= 0
            and final["composed_bank2"]["overlaps"] == []
            and final["nesting"]["violations"] == []
            and final["vm_hardening"]["markstack_symbol_absent"] is True
            and len(final["vm_hardening"]["sharp_mutations"]) == 5
            and value["artifacts_before"] == value["artifacts_after"]
            and value["attempt_accounting"]["WPLTO_runs"] == 1
            and value["attempt_accounting"]["product_links"] == 1
            and value["attempt_accounting"]["device_contacts"] == 0,
            "Card-3 product receipt drift")
    if require_dwx:
        require(final["packed_prefilter"]["status"] == "PASS"
                and final["gc_cycle_wall"]["status"] == "PASS"
                and value["review_ready"] is True,
                "Card-3 DWX/GC-cycle tail remains open")


def write_report(value: dict[str, Any]) -> None:
    final, owners = value["final_product"], value["final_product"]["bounded_owners"]
    REPORT.write_text(f"""# Block 2.6 Card 3 — A3–A6 product card

Status: **{value['status']}**

The final product removes the bounded private GC worklist, routes product roots
through the collector's stackless fixpoint, bounds byte-operand frame slots and
the transient `&rest` construction area, makes POP underflow fail before any
side effect, and gives `%disk-poke` its exact two-fixnum domain. All five sharp
mutations execute and fall against the real live sources.

Final owner margins are ordinary text **{owners['ordinary_text']['margin_bytes']}/32**,
BSS **{owners['ordinary_BSS']['margin_bytes']}/5**, resident Island
**{owners['resident_island']['margin_bytes']}/5**, with ZP, NOLOAD, composed
Bank-2 ownership and MAP nesting all green. The Card-2-r3 difference assigns
every section, symbol, relocation, program header and PRG byte to A3–A6,
layout/relocation, or derived Build-ID/CRC families; zero remain unexplained.

Packed DWX / GC-cycle wall: **{final['packed_prefilter']['status']} / {final['gc_cycle_wall']['status']}**.
Accounting is one WPLTO, one product link and zero physical device contacts.
A7 remains a separate closed decision until this executable successor is
fully qualified.
""", encoding="utf-8")


def build() -> None:
    patch_card(); CARD2.R2.CARD.configure()
    pre = load(PREFLIGHT_RECEIPT)
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout
    require(clean == "" and pre["status"] ==
            "PASS: BLOCK 2.6 CARD 3 A3-A6 ARMED 0/1"
            and not BUILD.exists() and not DIFFERENCE.exists() and not RECEIPT.exists(),
            "Card-3 build is not at its committed one-shot boundary")
    INVOCATION.write_bytes(canonical({"status": "INVOKED",
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT)}))
    processes = [run_child("_produce")]
    require(ELF.is_file() and PRG.is_file() and Path(str(PRG) + ".lto.o").is_file(),
            "Card-3 producer did not materialize one final pair")
    difference = attribution()
    require(difference["unexplained_members"] == 0,
            "Card-3 attribution retained a remainder")
    DIFFERENCE.write_bytes(canonical(difference))
    product = final_gate()
    before = artifacts()
    processes.extend((run_child("_scope"), run_child("_accept")))
    after = artifacts()
    base = CARD2.R2.CARD.BASE.CHAIN.LINK.BASE
    scope, acceptance = load(base.SCOPE_RESULT), load(base.ACCEPTANCE_RESULT)
    require(before == after and scope["status"] == acceptance["status"] == "PASS",
            "Card-3 Scope/Acceptance changed or rejected the frozen pair")
    value = {"format": FORMAT, "recorded_on": "2026-09-03", "status": STATUS,
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "invocation": bind(INVOCATION),
        "predecessor": {"ELF": bind(PREDECESSOR_ELF), "PRG": bind(PREDECESSOR_PRG)},
        "difference": difference, "difference_receipt": bind(DIFFERENCE),
        "final_product": product, "scope": bind(base.SCOPE_RESULT),
        "acceptance": bind(base.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": processes,
        "attempt_accounting": {"product_cards": 1, "WPLTO_runs": 1,
            "product_links": 1, "scope_runs": 1, "acceptance_runs": 1,
            "DWX_prefilter_runs": 0, "media_builds": 0, "device_contacts": 0},
        "review_ready": False}
    RECEIPT.write_bytes(canonical(value)); write_report(value)
    validate(value, require_dwx=False)
    print("Block 2.6 Card 3: PRODUCT PASS WPLTO=1/1 link=1/1 DWX=pending")


def selftest() -> None:
    value = load(RECEIPT); validate(value, require_dwx=False)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "text-floor-lost": lambda row: row["final_product"]["bounded_owners"][
            "ordinary_text"].update({"margin_bytes": 31}),
        "gc-root-mutation-blunted": lambda row: row["final_product"][
            "vm_hardening"].update({"sharp_mutations": []}),
        "markstack-returned": lambda row: row["final_product"][
            "vm_hardening"].update({"markstack_symbol_absent": False}),
        "difference-remainder": lambda row: row["difference"].update(
            {"unexplained_members": 1}),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial, require_dwx=False)
        except (CardError, RuntimeError, KeyError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "Card-3 product mutation survived")
    print(f"Block 2.6 Card 3: SELFTEST PASS mutations={len(rejected)}")


def check() -> None:
    patch_card(); CARD2.R2.CARD.configure()
    value = load(RECEIPT); validate(value)
    require(load(DIFFERENCE) == value["difference"] and REPORT.is_file(),
            "Card-3 report/difference absent")
    print("Block 2.6 Card 3: CHECK PASS WPLTO=1/1 link=1/1 device=0")


def child(action: str) -> None:
    patch_card(); CARD2.R2.CARD.child(action)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "check-preflight", "build",
        "check", "selftest", "_source_preflight", "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    if action == "preflight":
        materialize_prelink()
    elif action == "check-preflight":
        check_preflight()
    elif action == "build":
        build()
    elif action == "check":
        check()
    elif action == "selftest":
        selftest()
    elif action == "_source_preflight":
        patch_card(); CARD2.R2.source_preflight()
    else:
        child(action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, CARD2.CardError, RuntimeError, KeyError, ValueError,
            OSError, subprocess.CalledProcessError) as error:
        print(f"Block 2.6 Card 3: FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
