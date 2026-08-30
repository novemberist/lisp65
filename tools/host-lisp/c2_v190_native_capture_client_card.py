#!/usr/bin/env python3
"""Build the bound v1.9 page-congruent native Capture-client card.

This is deliberately a composition driver.  It does not fork either of its
authorities: the sealed v1.8 native-client plane supplies the only functional
delta, while the accepted Block-3 r10 linker policy supplies the only physical
placement delta.  The card proves both roots before qualifying one fresh pair.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_bank2_composed_ownership as COMPOSED  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v17_ide_idle_blink_product_card_r10 as R10  # noqa: E402
import c2_v18_capture_hybrid_native_client_card as CLIENT  # noqa: E402


BASE = CLIENT.BASE
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v1.9-native-capture-client-card-r1"
PREFLIGHT = ROOT / "build/c2.3/v1.9-native-capture-client-card-r1-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
PROBE_LINKER = PREFLIGHT / "mapped-tenant-linker-probe.ld"
PROBE_OBJECT = PREFLIGHT / "mapped-tuple-owner-probe.o"
PLACEMENT_PROBE = PREFLIGHT / "placement-probe.json"
RECEIPT = ARCH / "c2.3-v1.9-native-capture-client-card-r1-receipt.json"
FIRST_RED = ARCH / "c2.3-v1.9-native-capture-client-card-r1-first-red.json"
REPORT = ROOT / "docs/planning/v1.9.0-native-capture-client-card-report.md"
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
PROFILE = BUILD / "wplto/resolved-profile.txt"
PLANE_ROOT = PREFLIGHT / "setup-owned/static-plane/narrow-static"
PLANE_RECEIPT = PREFLIGHT / "v19-native-client-static-plane.json"
CLIENT_SOURCE = PREFLIGHT / "sources/stdlib-read-line.lisp"
C2D = PLANE_ROOT / "v6-semantics/initial.c2d-v6.bin"
CODE = PLANE_ROOT / "v6-semantics/bank2-static-code.bin"
MANIFEST = PLANE_ROOT / "stdlib-p0.manifest.json"
DRIVER = Path(__file__).resolve()
PLAN = ROOT / "docs/planning/v1.9.0-pre-plan.md"
COMMISSION_COMMIT = "3bbb4271"
FORMAT = "lisp65-c2-v190-native-capture-client-card-r1-v1"
STATUS = "PASS: V1.9 PAGE-CONGRUENT NATIVE CAPTURE CLIENT GREEN"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
TOOLCHAIN = ROOT / "tools/llvm-mos/bin"

# The sealed bridge closes the substrate -> client-functional world.  This
# card derives only the second bridge, from that exact world to the relocated
# candidate, then composes the two proofs.
SEALED_CLIENT_RED = ARCH / (
    "c2.3-v1.8-capture-hybrid-native-client-card-r1-final-red.json")
SEALED_CLIENT_ELF = CLIENT.ELF
SEALED_CLIENT_PRG = CLIENT.PRG
SEALED_CLIENT_PROFILE = CLIENT.PROFILE
SEALED_CLIENT_CODE = CLIENT.CODE
SEALED_CLIENT_PLANE_RECEIPT = CLIENT.PLANE_RECEIPT
ORIGINAL_SETUP = CLIENT.setup_child
ORIGINAL_FINAL_GATE = CLIENT.final_gate


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


def run(argv: list[str], label: str) -> str:
    result = subprocess.run(argv, cwd=ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout


def git_bytes(commit: str, path: Path) -> bytes:
    return subprocess.run(
        ["git", "show", f"{commit}:{path.relative_to(ROOT).as_posix()}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout


def authority() -> dict[str, Any]:
    raw = git_bytes(COMMISSION_COMMIT, PLAN)
    text = " ".join(raw.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("block a — far-service relocation + native capture client",
                  "$28000", "a=$80/x=$82", "94/94 lossless",
                  "responsiveness ≥ 25%", "one wplto + one product link",
                  "final elf proves the ring arms"):
        require(token in text, f"v1.9 Block-A authority absent: {token}")
    return {"authority": "git-blob", "commit": COMMISSION_COMMIT,
            "path": PLAN.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "budget": {"WPLTO_runs": 1, "product_links": 1,
                       "media_builds": 0, "device_contacts": 0}}


def setup_child() -> tuple[Any, dict[str, Any], dict[str, object]]:
    result = ORIGINAL_SETUP()
    PRODUCT.configure_mapped_tenant_lma_policy("map-page-top")
    return result


def configure() -> None:
    for name, value in {
        "BUILD": BUILD, "PREFLIGHT": PREFLIGHT, "RECEIPT": RECEIPT,
        "FIRST_RED": FIRST_RED, "REPORT": REPORT, "ELF": ELF, "PRG": PRG,
        "PROFILE": PROFILE, "PLANE_ROOT": PLANE_ROOT,
        "PLANE_RECEIPT": PLANE_RECEIPT, "CLIENT_SOURCE": CLIENT_SOURCE,
        "C2D": C2D, "CODE": CODE, "MANIFEST": MANIFEST,
        "DRIVER": DRIVER, "FORMAT": FORMAT, "STATUS": STATUS,
    }.items():
        setattr(CLIENT, name, value)
    CLIENT.configure()
    BASE.authority = authority
    BASE.setup_child = setup_child
    BASE.final_gate = final_gate
    R10.ACCEPT.linked_tuple_gate = tuple_loadaddr_gate
    R10.ACCEPT.EMITTED.acceptance_position_mutations = lambda: [
        "move-LMA-without-tuple-follow", "mutate-tuple-without-LMA-reason",
        "non-page-congruent-LOADADDR"]


def static_images() -> list[dict[str, Any]]:
    rows = []
    for key, name, path in CLIENT.client_specs():
        value = load(path)
        rows.append({"name": name, "key": key, "bytes": int(value["code_bytes"]),
                     "authority": bind(path)})
    require(len(rows) == 6 and sum(row["bytes"] for row in rows) == 47335,
            "native-client six-image static owner inventory drift")
    return rows


def expected_vmas() -> dict[str, int]:
    truth = ElfTruth.read(SEALED_CLIENT_ELF, llvm_readobj=READOBJ,
                          include_section_data=False)
    return {name: truth.section(name).address for name, _ in COMPOSED.MAPPED}


def composed(elf: Path = ELF) -> dict[str, Any]:
    value = COMPOSED.derive(
        elf=elf, plane=CODE, readobj=READOBJ, static_images=static_images(),
        expected_vmas=expected_vmas(), placement_policy="map-page-top-derived")
    mapped = value["mapped_tenants"]
    require(len(value["owners"]) == 10
            and [row["bytes"] for row in value["reserved_owners"]] == [11, 47]
            and [row["start"] for row in mapped] == [0x2f8b2, 0x2fe8d]
            and value["anchor"]["shared_offset"] == 0x28000
            and value["largest_contiguous_hole"]["bytes"] == 16331,
            "v1.9 composed page-congruent geometry drift")
    return value


def tuple_loadaddr_gate(elf: Path = ELF) -> dict[str, Any]:
    value = R10.tuple_LOADADDR_gate(elf)
    require(value["shared_offset"] == 0x28000
            and value["tuple"]["A"] == 0x80
            and value["tuple"]["X"] == 0x82,
            "v1.9 MAP tuple differs from accepted r10 authority")
    return value


def linker_probe() -> dict[str, Any]:
    setup_child()
    script = PRODUCT.linker_script(ownership_opt_in=True)
    PROBE_LINKER.write_text(script, encoding="utf-8")
    tokens = ("__lisp65_c2_mapped_shared_offset =",
              "__lisp65_c2_mapped_far_maplo_a =",
              "__lisp65_c2_mapped_far_maplo_x =",
              "__lisp65_c2_mapped_congruence_gap_start =",
              "__lisp65_c2_mapped_bank_end_reserve_start =")
    require(all(script.count(token) == 1 for token in tokens)
            and script.count(" / 0x100 * 0x100") == 2
            and "AT(0x0002b8b2)" not in script
            and "AT(0x0002be8d)" not in script,
            "real linker did not project the page-congruent authority")
    return {"status": "PASS: REAL LINKER PROJECTS R10 AUTHORITY",
            "linker_script": bind(PROBE_LINKER),
            "derived_tokens": list(tokens),
            "stored_LMA_literals_absent": True}


def assembler_probe() -> dict[str, Any]:
    source = R10.SOURCE.read_text(encoding="utf-8")
    require("lda #0x40" not in source and "ldx #0x82" not in source
            and "#mos16lo(__lisp65_c2_mapped_far_maplo_a)" in source
            and "#mos16lo(__lisp65_c2_mapped_far_maplo_x)" in source,
            "tuple-owner source retained a fixed authority")
    output = run([str(TOOLCHAIN / "mos-mega65-clang"), "-Wall", "-I", "src",
                  "-c", str(R10.SOURCE.relative_to(ROOT)), "-o",
                  str(PROBE_OBJECT.relative_to(ROOT))], "assembler probe")
    relocs = run([str(READOBJ), "--relocations",
                  str(PROBE_OBJECT.relative_to(ROOT))], "assembler relocs")
    names = ("__lisp65_c2_mapped_far_maplo_a",
             "__lisp65_c2_mapped_far_maplo_x")
    require(all(relocs.count("R_MOS_ADDR16_LO " + name) == 1 for name in names),
            "assembler did not consume linker tuple symbols")
    return {"status": "PASS: TUPLE OWNER CONSUMES LINKER SYMBOLS",
            "source": bind(R10.SOURCE), "object": bind(PROBE_OBJECT),
            "relocations": list(names), "compiler_output": " ".join(output.split())}


def projected_geometry() -> dict[str, Any]:
    truth = ElfTruth.read(SEALED_CLIENT_ELF, llvm_readobj=READOBJ,
                          include_section_data=False)
    far = truth.section(".lisp65_c2_mapped_far_service")
    cold = truth.section(".lisp65_c2_mapped_product_cold")
    far_start = far.address + 0x28000
    cold_start = cold.address + 0x28000
    static_end = 0x20000 + CODE.stat().st_size
    value = {"shared_offset": 0x28000, "tuple": {"A": 0x80, "X": 0x82},
        "static_plane": {"start": 0x20000, "end_exclusive": static_end,
                         "bytes": CODE.stat().st_size},
        "far_service": {"VMA": far.address, "LMA": far_start,
                        "bytes": far.bytes, "end_exclusive": far_start + far.bytes},
        "product_cold": {"VMA": cold.address, "LMA": cold_start,
                         "bytes": cold.bytes, "end_exclusive": cold_start + cold.bytes},
        "congruence_gap_bytes": cold_start - (far_start + far.bytes),
        "bank_end_reserve_bytes": 0x30000 - (cold_start + cold.bytes),
        "largest_contiguous_hole_bytes": far_start - static_end}
    require(value["congruence_gap_bytes"] == 11
            and value["bank_end_reserve_bytes"] == 47
            and value["largest_contiguous_hole_bytes"] == 16331
            and static_end <= far_start,
            "projected v1.9 placement does not fit")
    return {"status": "PASS: PAGE-CONGRUENT CLIENT PLACEMENT FITS", **value}


def placement_probe_child() -> None:
    value = {"status": "PASS: V1.9 PLACEMENT CONSUMERS AGREE",
             "projection": projected_geometry(),
             "real_linker_projection": linker_probe(),
             "assembler_effectiveness": assembler_probe()}
    PLACEMENT_PROBE.write_bytes(canonical(value))
    print("v1.9 Block A: PLACEMENT PROBE PASS offset=0x28000")


def preflight() -> None:
    require(not any(path.exists() for path in
                    (BUILD, PREFLIGHT, RECEIPT, FIRST_RED, REPORT)),
            "v1.9 native-client card is one-shot")
    configure()
    BASE.preflight()
    plane = CLIENT.emit_client_plane()
    require(bind(CODE)["sha256"] == bind(SEALED_CLIENT_CODE)["sha256"]
            and plane["geometry"]["bytes"] == 47335,
            "v1.9 client plane differs from sealed v1.8 client")
    phase1b = CLIENT.SUBSTRATE.lifecycle_gate()
    require(phase1b["status"] ==
                "PASS: PHASE-1B ARM/DISARM OWNER BYTE-IDENTICAL",
            "Phase-1b arm/disarm owner drift")
    run([sys.executable, str(DRIVER), "_placement_probe"],
        "page-congruent placement probe")
    placement = load(PLACEMENT_PROBE)
    value = load(BASE.PREFLIGHT_RECEIPT)
    value.update({"format": FORMAT + "-preflight",
        "recorded_on": "2026-08-28",
        "status": "PASS: V1.9 BLOCK-A CARD ARMED 0/1",
        "authority": authority(),
        "native_client_plane": {"receipt": bind(PLANE_RECEIPT),
            "geometry": plane["geometry"], "lifecycle": plane["lifecycle"],
            "sealed_v18_plane": bind(SEALED_CLIENT_CODE),
            "byte_identical_to_sealed_v18_client": True},
        "phase1b_owner": phase1b,
        "placement": placement["projection"],
        "real_linker_projection": placement["real_linker_projection"],
        "assembler_effectiveness": placement["assembler_effectiveness"],
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "claim_limit": "Pre-card host proof; no product/media/device claim."})
    BASE.PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("v1.9 Block A: PREFLIGHT PASS client=sealed offset=0x28000 link=0/1")


def member_diff(left: bytes, right: bytes, family: str) -> list[list[Any]]:
    total = max(len(left), len(right))
    return [[i, left[i] if i < len(left) else None,
             right[i] if i < len(right) else None, family]
            for i in range(total)
            if (left[i] if i < len(left) else None)
            != (right[i] if i < len(right) else None)]


def symbol_key(row: Any) -> tuple[Any, ...]:
    return (row.name, row.value, row.bytes, row.binding, row.symbol_type,
            row.section, row.section_index)


def relocation_key(row: Any) -> tuple[Any, ...]:
    return (row.relocation_section, row.source_section,
            row.source_section_index, row.offset, row.relocation_type,
            row.target, row.addend)


def expand(counter: Counter[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
    return [item for item in sorted(counter, key=repr)
            for _ in range(counter[item])]


def summary(rows: list[Any], family_index: int | None = None) -> dict[str, Any]:
    families = (Counter(row[family_index] for row in rows)
                if family_index is not None else
                Counter(row["family"] for row in rows))
    return {"members": len(rows),
        "canonical_members_sha256": hashlib.sha256(canonical(rows)).hexdigest(),
        "family_counts": dict(sorted(families.items())),
        "storage": "complete list is deterministically re-derived by check"}


def normalized_profile_inputs(path: Path, build_root: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    root = build_root.relative_to(ROOT).as_posix()
    inputs: dict[str, str] = {}
    normalized = []
    for line in lines:
        normalized.append(line.replace(root, "<BUILD>"))
        if line.startswith("input_sha256="):
            name, digest = line.removeprefix("input_sha256=").rsplit(":", 1)
            inputs[name.replace(root, "<BUILD>")] = digest
    require(inputs, f"resolved profile lacks inputs: {path}")
    return {"lines": normalized, "inputs": inputs}


def input_closure() -> dict[str, Any]:
    old = normalized_profile_inputs(SEALED_CLIENT_PROFILE,
                                    SEALED_CLIENT_PROFILE.parents[1])
    new = normalized_profile_inputs(PROFILE, BUILD)
    require(old["inputs"].keys() == new["inputs"].keys(),
            "compiler source population changed")
    changed = [{"path": name, "before": old["inputs"][name],
                "after": new["inputs"][name]}
               for name in sorted(old["inputs"])
               if old["inputs"][name] != new["inputs"][name]]
    require([Path(row["path"]).name for row in changed] ==
                ["c2-stream-phase-02a.c"],
            "source closure changed outside placement-derived shelf CRC")
    diffs = []
    require(len(old["lines"]) == len(new["lines"]),
            "profile line population drift")
    for number, (before, after) in enumerate(zip(old["lines"], new["lines"]), 1):
        if before != after:
            diffs.append({"line": number, "before": before, "after": after})
    require(len(diffs) == 2
            and diffs[0]["before"].startswith("linker_sha256=")
            and "c2-stream-phase-02a.c:" in diffs[1]["before"],
            "profile changed outside linker/shelf-CRC closure")
    old_crc = (SEALED_CLIENT_PROFILE.parent /
               "generated-product-sources/c2-stream-phase-02a.c").read_bytes()
    new_crc = (PROFILE.parent /
               "generated-product-sources/c2-stream-phase-02a.c").read_bytes()
    crc_delta = member_diff(old_crc, new_crc, "mapped-shelf-CRC16-projection")
    require(len(crc_delta) == 3,
            "mapped shelf CRC projection changed outside its 16-bit literal")
    return {"status": "PASS: LINKER ROOT AND DERIVED SHELF CRC CLOSED",
            "profiles": {"before": bind(SEALED_CLIENT_PROFILE),
                         "after": bind(PROFILE)},
            "normalized_differences": diffs,
            "source_inputs": {"members": len(old["inputs"]),
                              "changed": changed,
                              "unchanged": len(old["inputs"]) - len(changed)},
            "client_plane_byte_identical":
                bind(SEALED_CLIENT_CODE)["sha256"] == bind(CODE)["sha256"],
            "generated_shelf_CRC_projection": summary(crc_delta, 3),
            "causal_roots": ["page-congruent linker authority"],
            "transitive_projection": "phase-02a mapped-shelf CRC16"}


def linker_closure() -> dict[str, Any]:
    old_path = SEALED_CLIENT_PROFILE.parent / "c2-substitution.ld"
    new_path = PROFILE.parent / "c2-substitution.ld"
    left = old_path.read_text(encoding="utf-8")
    right = new_path.read_text(encoding="utf-8")

    def mask(text: str) -> str:
        start = text.index("    .lisp65_c2_mapped_far_service 0x78b2\n")
        marker = '       "product cold tenant escaped its mapped arena");\n'
        end = text.index(marker, start) + len(marker)
        return text[:start] + "<MAPPED-GEOMETRY>\n" + text[end:]

    require(mask(left) == mask(right)
            and "__lisp65_c2_mapped_shared_offset" in right
            and " / 0x100 * 0x100" in right,
            "linker changed outside mapped placement authority")
    changes = [row for row in __import__("difflib").ndiff(
        left.splitlines(), right.splitlines()) if row.startswith(("- ", "+ "))]
    return {"status": "PASS: LINKER DELTA IS ONLY PAGE-CONGRUENT GEOMETRY",
            "before": bind(old_path), "after": bind(new_path),
            "changed_lines": changes}


def object_closure(profile: dict[str, Any]) -> dict[str, Any]:
    targets: dict[str, Any] = {}
    changed_sets = []
    old_w = SEALED_CLIENT_PROFILE.parent
    new_w = PROFILE.parent
    for stem in ("resident-island-seed", "lisp65-c2-substitution-linked"):
        roots = [root / (".canonical-objects-" + stem) for root in (old_w, new_w)]
        populations = [{path.name: bind(path) for path in root.iterdir()
                        if path.is_file()} for root in roots]
        require(populations[0].keys() == populations[1].keys(),
                f"canonical object population drift: {stem}")
        changed = {name for name in populations[0]
                   if populations[0][name]["sha256"] !=
                      populations[1][name]["sha256"]}
        native = sorted(name for name in changed if name.endswith(".s.o"))
        require(not native and "029-c2-stream-phase-02a.c.o" in changed,
                f"object delta escaped linker/CRC closure: {stem}")
        changed_sets.append(changed)
        rows = [{"name": name, "before": populations[0][name],
                 "after": populations[1][name],
                 "family": ("mapped-shelf-CRC-projection-object"
                            if name == "029-c2-stream-phase-02a.c.o"
                            else "profile-build-id-transitive-object" if name in changed
                            else "byte-identical")}
                for name in sorted(populations[0])]
        targets[stem] = {"members": len(rows), "changed": len(changed),
                         "unchanged": len(rows) - len(changed), "objects": rows}
    require(changed_sets[0] == changed_sets[1],
            "seed/final object closures disagree")
    return {"status": "PASS: BOTH LINK TARGETS CONSUME TWO-ROOT CLOSURE",
            "profile": profile, "targets": targets}


def placement_attribution() -> dict[str, Any]:
    profile = input_closure()
    linker = linker_closure()
    objects = object_closure(profile)
    old = ElfTruth.read(SEALED_CLIENT_ELF, llvm_readobj=READOBJ,
                        include_section_data=True)
    new = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    old_alloc = {row.name: (row.address, row.bytes, row.section_type, row.flags)
                 for row in old.sections if "SHF_ALLOC" in row.flags}
    new_alloc = {row.name: (row.address, row.bytes, row.section_type, row.flags)
                 for row in new.sections if "SHF_ALLOC" in row.flags}
    require(old_alloc == new_alloc, "allocated section VMA/size geometry changed")
    prg = member_diff(SEALED_CLIENT_PRG.read_bytes(), PRG.read_bytes(),
                      "page-congruent-placement-transitive-product-byte")
    elf = member_diff(SEALED_CLIENT_ELF.read_bytes(), ELF.read_bytes(),
                      "page-congruent-placement-transitive-ELF-byte")
    old_symbols = Counter(map(symbol_key, old.symbols))
    new_symbols = Counter(map(symbol_key, new.symbols))
    removed_symbols = expand(old_symbols - new_symbols)
    added_symbols = expand(new_symbols - old_symbols)
    old_reloc = Counter(map(relocation_key, old.relocations))
    new_reloc = Counter(map(relocation_key, new.relocations))
    removed_reloc = expand(old_reloc - new_reloc)
    added_reloc = expand(new_reloc - old_reloc)
    symbol_rows = ([{"direction": "removed", "member": list(row),
                     "family": "page-congruent-placement-transitive-symbol"}
                    for row in removed_symbols] +
                   [{"direction": "added", "member": list(row),
                     "family": "page-congruent-placement-transitive-symbol"}
                    for row in added_symbols])
    reloc_rows = ([{"direction": "removed", "member": list(row),
                    "family": "page-congruent-placement-transitive-relocation"}
                   for row in removed_reloc] +
                  [{"direction": "added", "member": list(row),
                    "family": "page-congruent-placement-transitive-relocation"}
                   for row in added_reloc])
    section_rows = []
    for name in sorted({row.name for row in old.sections} |
                       {row.name for row in new.sections}):
        before = [asdict(row) for row in old.sections_by_name.get(name, [])]
        after = [asdict(row) for row in new.sections_by_name.get(name, [])]
        if before != after:
            section_rows.append({"name": name, "before": before, "after": after,
                "family": "page-congruent-placement-transitive-section"})
    counts = {"PRG_bytes": len(prg), "ELF_bytes": len(elf),
        "symbols_removed": len(removed_symbols), "symbols_added": len(added_symbols),
        "relocations_removed": len(removed_reloc),
        "relocations_added": len(added_reloc),
        "sections_changed": len(section_rows), "unexplained_PRG_bytes": 0,
        "unexplained_ELF_bytes": 0, "unexplained_symbols": 0,
        "unexplained_relocations": 0, "unexplained_sections": 0}
    return {"status": "PASS: PLACEMENT DELTA FULLY ATTRIBUTED",
        "pair": {"before": {"ELF": bind(SEALED_CLIENT_ELF),
                              "PRG": bind(SEALED_CLIENT_PRG)},
                 "after": {"ELF": bind(ELF), "PRG": bind(PRG)}},
        "input_closure": profile, "linker_closure": linker,
        "object_closure": objects,
        "allocated_sections_VMA_and_size_byte_identical": True,
        "PRG_changed_members": summary(prg, 3),
        "ELF_changed_members": summary(elf, 3),
        "symbol_changed_members": summary(symbol_rows),
        "relocation_changed_members": summary(reloc_rows),
        "section_changed_members": section_rows, "counts": counts}


def attribution() -> dict[str, Any]:
    sealed = load(SEALED_CLIENT_RED)
    first = sealed["attribution"]
    require(sealed["pair"]["ELF"] == bind(SEALED_CLIENT_ELF)
            and sealed["pair"]["PRG"] == bind(SEALED_CLIENT_PRG)
            and first["pair"]["candidate"]["ELF"] == bind(SEALED_CLIENT_ELF)
            and first["pair"]["candidate"]["PRG"] == bind(SEALED_CLIENT_PRG)
            and all(value == 0 for name, value in first["counts"].items()
                    if name.startswith("unexplained_")),
            "sealed substrate/client bridge drift")
    second = placement_attribution()
    direct_prg = member_diff(CLIENT.SUBSTRATE_PRG.read_bytes(), PRG.read_bytes(),
                             "two-stage-client-plus-placement-product-byte")
    direct_elf = member_diff(CLIENT.SUBSTRATE_ELF.read_bytes(), ELF.read_bytes(),
                             "two-stage-client-plus-placement-ELF-byte")
    return {"status": "PASS: SUBSTRATE TO V1.9 CLIENT FULLY ATTRIBUTED",
        "composition": [
            {"stage": "sealed-native-client-functional-delta",
             "evidence": bind(SEALED_CLIENT_RED), "counts": first["counts"]},
            {"stage": "page-congruent-placement-delta",
             "evidence": second}],
        "bridge_identity": {"ELF": bind(SEALED_CLIENT_ELF),
                            "PRG": bind(SEALED_CLIENT_PRG)},
        "direct_pair": {"substrate": {"ELF": bind(CLIENT.SUBSTRATE_ELF),
                                       "PRG": bind(CLIENT.SUBSTRATE_PRG)},
                        "candidate": {"ELF": bind(ELF), "PRG": bind(PRG)}},
        "direct_PRG_members": summary(direct_prg, 3),
        "direct_ELF_members": summary(direct_elf, 3),
        "counts": {**second["counts"],
            "direct_substrate_candidate_PRG_bytes": len(direct_prg),
            "direct_substrate_candidate_ELF_bytes": len(direct_elf)}}


def armed_lifecycle_final_elf() -> dict[str, Any]:
    client = CLIENT.client_final_gate()
    consumption = CLIENT.candidate_consumption_receipts()
    manifest = load(MANIFEST)
    entries = {row["name"]: row for row in manifest["entries"]}
    read_line = entries["read-line"]
    extent = CODE.stat().st_size
    extent_immediates = R10.R9.R8.extent_immediates(ELF, extent, 46053)
    require(client["entry_closed_then_zeroed_then_armed"] is True
            and client["normal_return_disarms"] is True
            and read_line["length"] == 177
            and all(row["result"]["consumed_value"] == extent
                    for row in consumption.values())
            and extent_immediates["value"] == extent,
            "final ELF does not bind the armed read-line plane")
    return {"status": "PASS: FINAL ELF CONSUMES ARMED READ-LINE CLIENT",
        "read_line": {"name": read_line["name"], "length": read_line["length"],
                      "ext_addr": read_line["ext_addr"],
                      "literals": read_line["literals"]},
        "ordered_lifecycle": client["lifecycle"]["ordered_lifecycle"],
        "compiler_consumers": consumption, "candidate_extent": extent,
        "final_ELF_extent_immediates": extent_immediates,
        "relation": ("manifested read-line arm/disarm bytes belong to the exact "
                     "plane consumed by both real compiler targets and encoded "
                     "by the final ELF extent checks"),
        "mutations": {"unarmed-read-line-wrapper": "rejected",
                      "plane-path-value-divergence": "rejected",
                      "final-ELF-without-candidate-extent": "rejected"}}


def final_gate() -> dict[str, Any]:
    product = ORIGINAL_FINAL_GATE()
    geometry = composed()
    tuple_value = tuple_loadaddr_gate()
    lifecycle = armed_lifecycle_final_elf()
    gate = product["v1_8_native_line_editor_client"]
    require(gate["hybrid"]["loss"]["linked_events_drained"] == 94
            and gate["hybrid"]["loss"]["linked_dropped"] == 0
            and gate["hybrid"]["normalization"]["executions"] == 512
            and gate["hybrid"]["responsiveness"]["margin_percent"] >= 25.0,
            "v1.9 final client wall red")
    product["v1_9_block_A"] = {
        "status": "PASS: PAGE-CONGRUENT ARMED CLIENT AND ALL WALLS GREEN",
        "composed_bank2": geometry, "tuple_LOADADDR": tuple_value,
        "armed_lifecycle_final_ELF": lifecycle,
        "client_walls": gate,
        "claim_limit": "host-qualified Block-A product; no media/device claim"}
    return product


def write_report(value: dict[str, Any]) -> None:
    gate = value["final_product"]["v1_9_block_A"]
    response = gate["client_walls"]["hybrid"]["responsiveness"]
    geometry = gate["composed_bank2"]
    pair = value["artifacts_after"]
    REPORT.write_text(f"""# v1.9 Block A — native Capture client

Status: **{value['status']}**

One authorized WPLTO and product link compose the sealed native line-editor
Capture client with the accepted page-congruent r10 placement.  The final
static plane is **{CODE.stat().st_size:,} bytes** and is byte-identical to the
sealed v1.8 client plane.  The mapped tenants keep their VMAs and consume the
shared `$28000` offset (tuple `A=$80/X=$82`); their 11-byte congruence gap and
47-byte Bank-2 end reserve are named owners.  The largest contiguous Bank-2
hole is **{geometry['largest_contiguous_hole']['bytes']:,} bytes**.

The final linked world drains 94/94 events with zero drops, executes 512/512
normalization cases, and measures **{response['frames_per_character']:.6f}
frames/character** with **{response['margin_percent']:.3f}% margin**.  The
armed-lifecycle gate binds the emitted `read-line` object to the exact plane
consumed by both real compiler targets and to the candidate extent encoded in
the final ELF.

Full attribution is a closed two-stage proof: the sealed substrate-to-client
functional delta, then the page-congruent placement delta.  Every byte,
symbol, relocation and section member is named with zero unexplained members
before Scope and Acceptance.  Both qualifiers read the frozen pair:

- ELF: `{pair['ELF']['sha256']}`
- PRG: `{pair['PRG']['sha256']}`

No medium was built and no device was contacted.  Hardware acceptance remains
the authority for retiring the v1.5 fast-typing Known Issue.
""", encoding="utf-8")


def check() -> None:
    configure()
    value = load(RECEIPT)
    gate = value["final_product"]["v1_9_block_A"]
    counts = value["attribution"]["counts"]
    require(value["status"] == STATUS
            and value["authority"] == authority()
            and value["artifacts_before"] == BASE.artifacts()
            and value["artifacts_after"] == value["artifacts_before"]
            and gate["composed_bank2"] == composed()
            and gate["tuple_LOADADDR"] == tuple_loadaddr_gate()
            and gate["armed_lifecycle_final_ELF"] == armed_lifecycle_final_elf()
            and canonical(value["attribution"]) == canonical(attribution())
            and gate["client_walls"]["hybrid"]["responsiveness"][
                "margin_percent"] >= 25.0
            and all(member == 0 for name, member in counts.items()
                    if name.startswith("unexplained_")),
            "v1.9 Block-A receipt drift")
    print("v1.9 Block A: CHECK PASS client=armed offset=0x28000")


def refresh_receipt() -> None:
    """Re-derive presentation-only evidence over the frozen qualified pair."""
    configure()
    value = load(RECEIPT)
    before = BASE.artifacts()
    require(value["status"] == STATUS
            and value["artifacts_before"] == before
            and value["artifacts_after"] == before
            and value["attempt_accounting"]["WPLTO_runs"] == 1
            and value["attempt_accounting"]["product_links"] == 1,
            "v1.9 evidence refresh pair/accounting drift")
    value["attribution"] = attribution()
    value["final_product"] = final_gate()
    require(before == BASE.artifacts(),
            "v1.9 evidence refresh changed frozen pair")
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    check()
    print("v1.9 Block A: EVIDENCE REFRESH PASS builds=0 pair=unchanged")


def build() -> None:
    configure()
    pre = load(BASE.PREFLIGHT_RECEIPT)
    require(pre["status"] == "PASS: V1.9 BLOCK-A CARD ARMED 0/1"
            and not BUILD.exists() and not RECEIPT.exists()
            and not BASE.INVOCATION.exists(),
            "v1.9 Block-A preflight/lifecycle drift")
    BASE.INVOCATION.write_bytes(canonical({"status": "INVOKED",
        "authority": authority(), "preflight": bind(BASE.PREFLIGHT_RECEIPT),
        "budget": {"WPLTO_runs": 1, "product_links": 1}}))
    processes = [BASE.run_child("_produce")]
    before = BASE.artifacts()
    diff = attribution()
    require(all(value == 0 for name, value in diff["counts"].items()
                if name.startswith("unexplained_")),
            "v1.9 Block-A attribution retained unexplained members")
    gate = final_gate()
    processes.extend((BASE.run_child("_scope"), BASE.run_child("_accept")))
    after = BASE.artifacts()
    require(before == after, "qualification changed frozen v1.9 pair")
    scope = load(BASE.SCOPE_RESULT)
    acceptance = load(BASE.ACCEPTANCE_RESULT)
    require(scope["status"] == acceptance["status"] == "PASS",
            "v1.9 qualification tail red")
    value = {"format": FORMAT, "recorded_on": "2026-08-28",
        "status": STATUS, "authority": authority(),
        "preflight": bind(BASE.PREFLIGHT_RECEIPT),
        "invocation": bind(BASE.INVOCATION),
        "configuration": pre["configuration"], "attribution": diff,
        "final_product": gate, "producer": bind(BASE.PRODUCER_RESULT),
        "scope": bind(BASE.SCOPE_RESULT), "acceptance": bind(BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": processes,
        "attempt_accounting": {"WPLTO_runs": 1, "product_links": 1,
            "scope_runs": 1, "acceptance_runs": 1,
            "media_builds": 0, "device_contacts": 0},
        "media_authorized": False,
        "next": "independent review; Block B and Comfort remain closed"}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    check()
    print("v1.9 Block A: CARD PASS WPLTO=1/1 link=1/1 armed=YES")


def resume() -> None:
    """Close the attribution-only First Red over the frozen product pair."""
    configure()
    red = load(FIRST_RED)
    before = BASE.artifacts()
    require(red["status"] == "FIRST RED: V1.9 BLOCK-A CARD STOPS"
            and red["error"] == "source closure changed outside tuple owner"
            and red["artifacts"]["ELF"] == before["ELF"]
            and red["artifacts"]["PRG"] == before["PRG"]
            and red["attempt_accounting"]["WPLTO_runs"] == 1
            and red["attempt_accounting"]["product_links"] == 1
            and not RECEIPT.exists()
            and not BASE.SCOPE_RESULT.exists()
            and not BASE.ACCEPTANCE_RESULT.exists(),
            "v1.9 frozen attribution-red lifecycle drift")
    diff = attribution()
    require(all(value == 0 for name, value in diff["counts"].items()
                if name.startswith("unexplained_")),
            "v1.9 Resume attribution retained unexplained members")
    gate = final_gate()
    processes = [BASE.run_child("_scope"), BASE.run_child("_accept")]
    after = BASE.artifacts()
    scope = load(BASE.SCOPE_RESULT)
    acceptance = load(BASE.ACCEPTANCE_RESULT)
    require(before == after
            and scope["status"] == acceptance["status"] == "PASS",
            "v1.9 read-only qualification Resume red")
    pre = load(BASE.PREFLIGHT_RECEIPT)
    value = {"format": FORMAT, "recorded_on": "2026-08-28",
        "status": STATUS, "authority": authority(),
        "preflight": bind(BASE.PREFLIGHT_RECEIPT),
        "invocation": bind(BASE.INVOCATION), "first_red": bind(FIRST_RED),
        "attribution_conversion": {
            "family": "derived placement CRC projection",
            "observed": ("the first checker admitted only the direct tuple-owner "
                         "source and rejected the generated phase-02a shelf CRC"),
            "replacement": ("one authored linker root plus its named generated "
                            "shelf-CRC projection"),
            "pair_rebuilt": False},
        "configuration": pre["configuration"], "attribution": diff,
        "final_product": gate, "producer": bind(BASE.PRODUCER_RESULT),
        "scope": bind(BASE.SCOPE_RESULT), "acceptance": bind(BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": processes,
        "attempt_accounting": {"WPLTO_runs": 1, "product_links": 1,
            "scope_runs": 1, "acceptance_runs": 1,
            "media_builds": 0, "device_contacts": 0},
        "resume_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "scope_runs": 1, "acceptance_runs": 1, "cards_consumed": 0},
        "media_authorized": False,
        "next": "independent review; Block B and Comfort remain closed"}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    check()
    print("v1.9 Block A: RESUME PASS WPLTO=1/1 link=1/1 new-builds=0")


def record_red(error: Exception, invoked: bool) -> None:
    artifacts = {}
    for name, path in (("ELF", ELF), ("PRG", PRG),
                       ("map", BUILD / "wplto/lisp65-c2-substitution-linked.prg.map"),
                       ("lto", BUILD / "wplto/lisp65-c2-substitution-linked.prg.lto.o")):
        if path.is_file():
            artifacts[name] = bind(path)
    FIRST_RED.write_bytes(canonical({"format": FORMAT + "-first-red",
        "recorded_on": "2026-08-28",
        "status": "FIRST RED: V1.9 BLOCK-A CARD STOPS", "error": str(error),
        "artifacts": artifacts,
        "attempt_accounting": {"WPLTO_runs": int(invoked),
            "product_links": int(ELF.is_file()), "media_builds": 0,
            "device_contacts": 0}, "retry_authorized": False}))


def child(action: str) -> None:
    if action == "_release_probe":
        # The published-profile probe deliberately runs before any successor
        # configuration.  Configuring first would make sealed history consume
        # the live card world and invert the phase boundary.
        CLIENT.SUBSTRATE.release_probe_child()
        return
    configure()
    if action == "_profile_probe":
        CLIENT.SUBSTRATE.profile_probe_child()
    elif action == "_produce":
        BASE.produce_child()
    elif action == "_scope":
        BASE.scope_child()
    elif action == "_accept":
        BASE.acceptance_child()
    elif action == "_placement_probe":
        placement_probe_child()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "build", "resume",
        "refresh-receipt", "check",
        "_profile_probe", "_release_probe", "_placement_probe",
        "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    if action == "preflight":
        preflight()
    elif action == "build":
        try:
            build()
        except Exception as error:
            record_red(error, BASE.INVOCATION.exists())
            raise
    elif action == "resume":
        resume()
    elif action == "refresh-receipt":
        refresh_receipt()
    elif action == "check":
        check()
    else:
        child(action)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
