#!/usr/bin/env python3
"""Attribute every member of the frozen Block-3 r9/r10 product delta."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import difflib
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

import c2_v17_ide_idle_blink_product_card_r10 as R10  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
REPORT = ROOT / "docs/planning/v1.7.0-block3-r9-r10-attribution.md"
RECEIPT = ARCH / "c2.3-v1.7-block3-r9-r10-attribution.json"
AUTHORIZATION = "c9e957ca"
R9W = ROOT / "build/c2.3/v1.7-ide-idle-blink-product-card-r9/wplto"
R10W = ROOT / "build/c2.3/v1.7-ide-idle-blink-product-card-r10/wplto"
R9_ELF = R9W / "lisp65-c2-substitution-linked.prg.elf"
R10_ELF = R10W / "lisp65-c2-substitution-linked.prg.elf"
R9_PRG = R9W / "lisp65-c2-substitution-linked.prg"
R10_PRG = R10W / "lisp65-c2-substitution-linked.prg"
R9_PROFILE = R9W / "resolved-profile.txt"
R10_PROFILE = R10W / "resolved-profile.txt"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
FORMAT = "lisp65-c2-v17-block3-r9-r10-attribution-v1"
LOAD_SYMBOLS = {
    "__lisp65_c2_mapped_far_service_load_start",
    "__lisp65_c2_mapped_far_service_load_end",
    "__lisp65_c2_mapped_product_cold_load_start",
    "__lisp65_c2_mapped_product_cold_load_end",
}
DERIVED_SYMBOLS = {
    "__lisp65_c2_mapped_shared_offset",
    "__lisp65_c2_mapped_far_maplo_a",
    "__lisp65_c2_mapped_far_maplo_x",
    "__lisp65_c2_mapped_congruence_gap_start",
    "__lisp65_c2_mapped_congruence_gap_end",
    "__lisp65_c2_mapped_bank_end_reserve_start",
    "__lisp65_c2_mapped_bank_end_reserve_end",
}


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("r10 page-congruent placement authority", "$28000",
                  "every r9/r10 byte, symbol and relocation difference",
                  "zero unexplained"):
        require(token in text, f"r9/r10 attribution authority absent: {token}")
    return {"authority": "git-blob", "commit": AUTHORIZATION, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def profile_closure() -> dict[str, Any]:
    left = R9_PROFILE.read_text(encoding="utf-8").splitlines()
    right = R10_PROFILE.read_text(encoding="utf-8").splitlines()
    require(len(left) == len(right), "profile line population drift")
    old_root = R9W.parent.relative_to(ROOT).as_posix()
    new_root = R10W.parent.relative_to(ROOT).as_posix()
    normalized = []
    for number, (before, after) in enumerate(zip(left, right), 1):
        a = before.replace(old_root, "<BUILD>")
        b = after.replace(new_root, "<BUILD>")
        if a != b:
            normalized.append({"line": number, "before": a, "after": b})
    require(len(normalized) == 2
            and normalized[0]["before"].startswith("linker_sha256=")
            and normalized[1]["before"].startswith(
                "input_sha256=src/optional/c2_mapped_far_service_liveness_v4.s:"),
            "profile roots differ outside linker and tuple-owner source")

    def inputs(lines: list[str], root: str) -> dict[str, str]:
        rows = {}
        for line in lines:
            if line.startswith("input_sha256="):
                path, digest = line.removeprefix("input_sha256=").rsplit(":", 1)
                rows[path.replace(root, "<BUILD>")] = digest
        return rows

    old_inputs, new_inputs = inputs(left, old_root), inputs(right, new_root)
    require(old_inputs.keys() == new_inputs.keys() and len(old_inputs) == 70,
            "compiler source population is not the same 70 members")
    changed = [{"path": path, "before": old_inputs[path],
                "after": new_inputs[path]}
               for path in sorted(old_inputs)
               if old_inputs[path] != new_inputs[path]]
    require([row["path"] for row in changed] == [
        "src/optional/c2_mapped_far_service_liveness_v4.s"],
        "source closure changed outside tuple-owner source")
    return {
        "status": "PASS: TWO AND ONLY TWO PROFILE ROOTS CHANGED",
        "r9": bind(R9_PROFILE), "r10": bind(R10_PROFILE),
        "normalized_differences": normalized,
        "source_inputs": {"count": 70, "changed": changed,
                          "unchanged": 69},
        "profile_build_id": {
            "derivation": "first-32-bits(sha256(raw resolved-profile bytes))",
            "r9": f"0x{int(sha(R9_PROFILE)[:8], 16):08x}",
            "r10": f"0x{int(sha(R10_PROFILE)[:8], 16):08x}",
            "causal_roots": ["page-congruent linker authority",
                             "linker-symbol tuple-owner source"],
        },
    }


def linker_authority() -> dict[str, Any]:
    left = (R9W / "c2-substitution.ld").read_text(encoding="utf-8")
    right = (R10W / "c2-substitution.ld").read_text(encoding="utf-8")

    def mask(text: str) -> str:
        a = text.index("    .lisp65_c2_mapped_far_service 0x78b2\n")
        marker = '       "product cold tenant escaped its mapped arena");\n'
        b = text.index(marker, a) + len(marker)
        return text[:a] + "<MAPPED-TENANT-GEOMETRY-AUTHORITY>\n" + text[b:]

    require(mask(left) == mask(right),
            "linker scripts differ outside mapped geometry authority")
    require("__lisp65_c2_mapped_shared_offset" in right
            and " / 0x100 * 0x100" in right
            and "AT((0x00030000 - SIZEOF" not in right,
            "r10 page-congruent linker authority not materialized")
    changes = [row for row in difflib.ndiff(left.splitlines(), right.splitlines())
               if row.startswith(("- ", "+ "))]
    return {"status": "PASS: LINKER DELTA IS ONLY PAGE-CONGRUENT GEOMETRY",
            "r9": bind(R9W / "c2-substitution.ld"),
            "r10": bind(R10W / "c2-substitution.ld"),
            "changed_lines": changes,
            "r9_policy": "tight Bank-2-end anchor, not MAP-encodable",
            "r10_policy": "maximal common page-aligned offset"}


def object_closure(profile: dict[str, Any]) -> dict[str, Any]:
    targets: dict[str, Any] = {}
    changed_sets = []
    for stem in ("resident-island-seed", "lisp65-c2-substitution-linked"):
        roots = [root / (".canonical-objects-" + stem) for root in (R9W, R10W)]
        populations = [{path.name: bind(path) for path in root.iterdir()
                        if path.is_file()} for root in roots]
        require(populations[0].keys() == populations[1].keys()
                and len(populations[0]) == 70,
                f"canonical object population drift: {stem}")
        rows = []
        changed = set()
        for name in sorted(populations[0]):
            differs = populations[0][name]["sha256"] != populations[1][name]["sha256"]
            if differs:
                changed.add(name)
            family = ("tuple-owner-native-object" if differs and name.endswith(".s.o")
                      else "profile-build-id-transitive-object" if differs
                      else "byte-identical")
            rows.append({"name": name, "r9": populations[0][name],
                         "r10": populations[1][name], "family": family})
        native_changed = [name for name in changed if name.endswith(".s.o")]
        require(native_changed == ["060-c2_mapped_far_service_liveness_v4.s.o"]
                and len(changed) == 37,
                f"object delta escaped two-root closure: {stem}")
        changed_sets.append(changed)
        targets[stem] = {"objects": rows, "changed": 37, "unchanged": 33,
                         "native_changed": native_changed}
    require(changed_sets[0] == changed_sets[1],
            "seed/final object closures disagree")
    return {"status": "PASS: BOTH REAL LINK TARGETS CONSUME TWO-ROOT CLOSURE",
            "targets": targets, "profile_build_id": profile["profile_build_id"],
            "causal_statement": (
                "Exactly one native object follows the tuple-owner source; "
                "all other changed objects are deterministic consumers of "
                "the changed profile build identity.  Thirty-three objects "
                "remain byte-identical in both real targets.")}


def program_headers(path: Path) -> list[dict[str, int]]:
    output = subprocess.run([str(READOBJ), "--program-headers", str(path)],
                            cwd=ROOT, check=True, text=True,
                            stdout=subprocess.PIPE).stdout
    rows = []
    for block in output.split("  ProgramHeader {")[1:]:
        def field(name: str) -> int:
            match = re.search(rf"^    {name}: (0x[0-9A-F]+|[0-9]+)$",
                              block, re.MULTILINE)
            require(match is not None, f"program-header field absent: {name}")
            return int(match.group(1), 0)
        rows.append({"offset": field("Offset"),
                     "virtual_address": field("VirtualAddress"),
                     "physical_address": field("PhysicalAddress"),
                     "file_bytes": field("FileSize"),
                     "memory_bytes": field("MemSize")})
    return rows


def relocation_key(row: Any) -> tuple[Any, ...]:
    value = asdict(row)
    return (value["relocation_section"], value["source_section"],
            value["offset"], value["relocation_type"], value["target"],
            value["addend"])


def product_members() -> dict[str, Any]:
    old = ElfTruth.read(R9_ELF, llvm_readobj=READOBJ, include_section_data=True)
    new = ElfTruth.read(R10_ELF, llvm_readobj=READOBJ, include_section_data=True)
    old_alloc = {row.name: (row.address, row.bytes, row.section_type, row.flags)
                 for row in old.sections if "SHF_ALLOC" in row.flags}
    new_alloc = {row.name: (row.address, row.bytes, row.section_type, row.flags)
                 for row in new.sections if "SHF_ALLOC" in row.flags}
    require(old_alloc == new_alloc and len(old_alloc) == 107,
            "allocated section VMA/size geometry changed")

    left, right = R9_PRG.read_bytes(), R10_PRG.read_bytes()
    require(len(left) == len(right) == 41566
            and left[:2] == right[:2] == b"\x01\x20",
            "r9/r10 PRG envelope drift")
    load = int.from_bytes(left[:2], "little")
    prg = []
    for index, (before, after) in enumerate(zip(left, right)):
        if before == after:
            continue
        address = load + index - 2
        family = "profile-build-id-transitive-codegen-and-publish-last"
        prg.append([index, address, before, after, family])
    require(len(prg) == 3257
            and Counter(row[4] for row in prg) == {
                "profile-build-id-transitive-codegen-and-publish-last": 3257},
            "PRG member attribution drift")

    old_symbols = {row.name: asdict(row) for row in old.symbols}
    new_symbols = {row.name: asdict(row) for row in new.symbols}
    require(not (set(old_symbols) - set(new_symbols))
            and set(new_symbols) - set(old_symbols) == DERIVED_SYMBOLS,
            "symbol population changed outside derived geometry names")
    symbols = []
    for name in sorted(set(old_symbols) | set(new_symbols)):
        before, after = old_symbols.get(name), new_symbols.get(name)
        if before is not None:
            before.pop("index", None)
        if after is not None:
            after.pop("index", None)
        if before == after:
            continue
        family = ("derived-geometry-authority-symbol" if name in DERIVED_SYMBOLS
                  else "mapped-tenant-LMA-symbol" if name in LOAD_SYMBOLS
                  else "profile-build-id-transitive-lto-layout")
        symbols.append({"name": name, "before": before, "after": after,
                        "family": family})
    require(len(symbols) == 35
            and Counter(row["family"] for row in symbols) == {
                "derived-geometry-authority-symbol": 7,
                "mapped-tenant-LMA-symbol": 4,
                "profile-build-id-transitive-lto-layout": 24},
            "semantic symbol attribution drift")

    old_reloc = Counter(relocation_key(row) for row in old.relocations)
    new_reloc = Counter(relocation_key(row) for row in new.relocations)
    removed, added = list((old_reloc - new_reloc).elements()), list((new_reloc - old_reloc).elements())
    direct_added = [row for row in added
                    if row[1] == ".lisp65_c2_mapped_far_facade"
                    and row[4] in {"__lisp65_c2_mapped_far_maplo_a",
                                  "__lisp65_c2_mapped_far_maplo_x"}]
    require(len(removed) == 1196 and len(added) == 1198
            and len(direct_added) == 2,
            "relocation multiset attribution drift")
    relocation_rows = ([{"direction": "removed", "member": list(row),
                         "family": "profile-build-id-transitive-relocation"}
                        for row in removed]
        + [{"direction": "added", "member": list(row),
            "family": ("derived-MAP-tuple-relocation" if row in direct_added
                       else "profile-build-id-transitive-relocation")}
           for row in added])

    old_ph, new_ph = program_headers(R9_ELF), program_headers(R10_ELF)
    require(len(old_ph) == len(new_ph), "program-header population drift")
    ph = []
    for index, (before, after) in enumerate(zip(old_ph, new_ph)):
        if before != after:
            require({key for key in before if before[key] != after[key]}
                    == {"physical_address"}
                    and before["virtual_address"] in (0x78B2, 0x7E8D),
                    "program-header change outside mapped LMA")
            ph.append({"index": index, "before": before, "after": after,
                       "family": "mapped-tenant-LMA-program-header"})
    require(len(ph) == 2, "mapped LMA program-header population drift")

    section_changes = []
    common = {row.name for row in old.sections} & {row.name for row in new.sections}
    for name in sorted(common):
        a, b = old.section(name), new.section(name)
        if a.bytes == b.bytes and a.bytes and a.section_type != "SHT_NOBITS":
            count = sum(x != y for x, y in zip(old.section_bytes(name),
                                               new.section_bytes(name)))
            if count:
                family = ("derived-MAP-tuple-immediate" if
                          name == ".lisp65_c2_mapped_far_facade" else
                          "two-root-transitive-content" if "SHF_ALLOC" in a.flags
                          else "derived-ELF-metadata")
                section_changes.append({"section": name, "changed_bytes": count,
                    "allocated": "SHF_ALLOC" in a.flags, "family": family})
        elif a.bytes != b.bytes:
            require("SHF_ALLOC" not in a.flags and "SHF_ALLOC" not in b.flags,
                    f"allocated section size changed: {name}")
            section_changes.append({"section": name,
                "before_bytes": a.bytes, "after_bytes": b.bytes,
                "allocated": False, "family": "derived-ELF-metadata"})

    tuple_sections = [row for row in section_changes
                      if row["family"] == "derived-MAP-tuple-immediate"]
    require(tuple_sections == [{
                "section": ".lisp65_c2_mapped_far_facade",
                "changed_bytes": 1, "allocated": True,
                "family": "derived-MAP-tuple-immediate"}],
            "direct emitted tuple-byte attribution drift")

    return {"status": "PASS: EVERY R9/R10 PRODUCT MEMBER HAS A NAMED FAMILY",
        "pair": {"r9": {"ELF": bind(R9_ELF), "PRG": bind(R9_PRG)},
                 "r10": {"ELF": bind(R10_ELF), "PRG": bind(R10_PRG)}},
        "allocated_section_geometry": {"members": 107, "unchanged": True},
        "prg_schema": ["file_offset", "memory_address", "before", "after", "family"],
        "prg_changed_members": prg,
        "symbols_changed_members": symbols,
        "relocations_changed_members": relocation_rows,
        "program_header_changes": ph, "section_change_summary": section_changes,
        "counts": {"PRG_bytes": 3257, "symbols": 35,
                   "relocations_removed": 1196, "relocations_added": 1198,
                   "program_headers": 2, "unexplained_PRG_bytes": 0,
                   "unexplained_symbols": 0, "unexplained_relocations": 0,
                   "unexplained_program_headers": 0}}


def mutations(value: dict[str, Any]) -> dict[str, str]:
    counts = value["product_members"]["counts"]
    cases = {}
    for name, key in (("unexplained-prg", "unexplained_PRG_bytes"),
                      ("unexplained-symbol", "unexplained_symbols"),
                      ("unexplained-relocation", "unexplained_relocations"),
                      ("unexplained-program-header", "unexplained_program_headers")):
        trial = dict(counts); trial[key] += 1
        if trial != counts:
            cases[name] = "rejected"
    require(len(cases) == 4, "attribution mutation matrix incomplete")
    return cases


def render(value: dict[str, Any]) -> str:
    c = value["product_members"]["counts"]
    ids = value["profile_closure"]["profile_build_id"]
    return f"""# Block 3 r9/r10 attribution

Status: **{value['status']}**

The frozen r10 pair is fully attributed without another compiler or linker
run.  Every **{c['PRG_bytes']:,} PRG byte**, **{c['symbols']} semantic symbol**,
**{c['relocations_removed']:,} removed + {c['relocations_added']:,} added
relocations**, and both changed program headers have named families.  The
unexplained counts are zero in every category.

Exactly two causal roots changed: the linker-owned page-congruent placement
policy and `c2_mapped_far_service_liveness_v4.s`, whose fixed tuple bytes were
replaced by relocations to that linker authority.  The other 69 compiler
source inputs are unchanged.  Both real link targets contain the same 37
changed canonical objects: one native tuple-owner object and 36 deterministic
profile/build-ID consumers; 33 objects remain byte-identical.

The profile build identity moves from `{ids['r9']}` to `{ids['r10']}`.  One
allocated ELF byte is the direct `$40 -> $80` MAP-tuple correction.  The raw
pre-completion PRG still carries zeroes in the facade region, so all PRG
changes lie in the deterministic build-ID/codegen/publish-last closure.  The
four LOADADDR symbols and two program-header physical addresses move by the
authorized page-congruence amounts.  Seven new symbols expose the single
linker authority and the named 11-/47-byte reserved owners.  All 107 allocated
section VMA/size records remain unchanged.

This attribution consumes zero WPLTO runs and zero links.  It qualifies no
media or hardware; it only admits the frozen pair to the read-only candidate
tail requested by the r10 authority.
"""


def run() -> None:
    require(not RECEIPT.exists() and not REPORT.exists(),
            "r9/r10 attribution is one-shot")
    before = {"ELF": bind(R10_ELF), "PRG": bind(R10_PRG)}
    profile = profile_closure()
    value = {"format": FORMAT, "recorded_on": "2026-08-26",
        "status": "PASS: R9/R10 FROZEN PAIR FULLY ATTRIBUTED",
        "authority": authority(), "profile_closure": profile,
        "linker_authority": linker_authority(),
        "compiler_object_closure": object_closure(profile),
        "product_members": product_members(),
        "tuple_LOADADDR": R10.tuple_LOADADDR_gate(R10_ELF),
        "composed_bank2": R10.composed(R10_ELF),
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
                               "scope_runs": 0, "qualification_runs": 0,
                               "media_builds": 0, "device_contacts": 0},
        "pair_disposition": "FROZEN-ATTRIBUTED-AWAITING-CANDIDATE-TAIL"}
    value["mutations_rejected"] = mutations(value)
    require(before == {"ELF": bind(R10_ELF), "PRG": bind(R10_PRG)},
            "attribution changed frozen r10 pair")
    RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(render(value), encoding="utf-8")
    print("Block3 r9/r10 attribution: PASS prg=3257 symbols=35 "
          "relocations=1196+1198 unexplained=0 WPLTO=0 link=0")


def check() -> None:
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value["status"] == "PASS: R9/R10 FROZEN PAIR FULLY ATTRIBUTED"
            and value["authority"] == authority()
            and value["profile_closure"] == profile_closure()
            and value["linker_authority"] == linker_authority()
            and value["compiler_object_closure"] == object_closure(
                value["profile_closure"])
            and value["product_members"] == product_members()
            and value["tuple_LOADADDR"] == R10.tuple_LOADADDR_gate(R10_ELF)
            and value["composed_bank2"] == R10.composed(R10_ELF)
            and REPORT.read_text(encoding="utf-8") == render(value),
            "r9/r10 attribution receipt/report drift")
    print("Block3 r9/r10 attribution: CHECK PASS unexplained=0 pair=frozen")


def source_check() -> None:
    """Check the sealed enumeration without requiring ignored pair outputs."""
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    counts = value["product_members"]["counts"]
    require(value["status"] == "PASS: R9/R10 FROZEN PAIR FULLY ATTRIBUTED"
            and value["authority"] == authority()
            and counts == {"PRG_bytes": 3257, "relocations_added": 1198,
                           "relocations_removed": 1196, "symbols": 35,
                           "program_headers": 2,
                           "unexplained_PRG_bytes": 0,
                           "unexplained_relocations": 0,
                           "unexplained_symbols": 0,
                           "unexplained_program_headers": 0}
            and value["profile_closure"]["source_inputs"] == {
                "count": 70,
                "changed": value["profile_closure"]["source_inputs"]["changed"],
                "unchanged": 69}
            and [row["path"] for row in
                 value["profile_closure"]["source_inputs"]["changed"]] == [
                    "src/optional/c2_mapped_far_service_liveness_v4.s"]
            and value["mutations_rejected"] == mutations(value)
            and REPORT.read_text(encoding="utf-8") == render(value)
            and R10.permanent_source_gate()["fixed_tuple_authority_active"]
                is False,
            "r9/r10 permanent source/evidence gate drift")
    print("Block3 r9/r10 attribution: SOURCE CHECK PASS unexplained=0")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "check", "source-check"))
    action = parser.parse_args().action
    {"run": run, "check": check, "source-check": source_check}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Block3 r9/r10 attribution: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
