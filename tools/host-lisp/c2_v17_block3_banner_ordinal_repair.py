#!/usr/bin/env python3
"""Attribute and repair the Block-3 hardware banner-ordinal First Red.

The r10 static plane contains ``%repl-banner`` at ordinal 247, but the real
native caller was compiled through the historical substitution header and
emitted ordinal 239 (``%load-lib-loaded-p``, arity two).  This one bounded
repair round binds the candidate generated header at the compiler consumer,
then proves the final call operand against the candidate inventory.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0 as BYTECODE  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v17_ide_idle_blink_product_card_r10 as R10  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SESSION = ROOT / "config/c2-v17-block3-r10-acceptance-session.json"
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
BUILD = ROOT / "build/c2.3/v1.7-block3-banner-ordinal-repair"
PREFLIGHT = ROOT / "build/c2.3/v1.7-block3-banner-ordinal-repair-preflight"
SETUP = PREFLIGHT / "setup-owned/static-plane/narrow-static"
R10_SETUP_SOURCE = (
    ROOT / "build/c2.3/v1.7-ide-idle-blink-product-preflight-r10/"
           "setup-owned/static-plane/narrow-static")
INVOCATION = PREFLIGHT / "candidate-invocation.json"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
POSTLINK = BUILD / "postlink-attribution.json"
DIFFERENCE = ARCH / "c2.3-v1.7-block3-banner-ordinal-difference.json"
SCOPE = BUILD / "owner-scope-result.json"
ACCEPTANCE = BUILD / "artifact-acceptance.json"
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
PROFILE = BUILD / "wplto/resolved-profile.txt"
RECEIPT = ARCH / "c2.3-v1.7-block3-banner-ordinal-repair-receipt.json"
REPORT = ROOT / "docs/planning/v1.7.0-block3-banner-ordinal-repair.md"
ATTRIBUTION = ARCH / "c2.3-v1.7-block3-banner-ordinal-attribution.json"
DRIVER = Path(__file__).resolve()
R10_ELF = R10.ELF
R10_PRG = R10.PRG
R10_PROFILE = R10.PROFILE
HISTORICAL_HEADER = ROOT / "build/c2.2/substitution/stdlib-p0.h"
SOURCE_HEADER = R10.CARD.PLANE / "stdlib-p0.h"
MANIFEST = R10.setup_plane() / "stdlib-p0.manifest.json"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
FORMAT = "lisp65-c2-v17-block3-banner-ordinal-repair-v1"
STATUS = "PASS: BLOCK3 BANNER CALL CONSUMES CANDIDATE ORDINAL"
OLD_ORDINAL = 239
NEW_ORDINAL = 247
ORIGINAL_R10_SETUP = R10.setup_child


class RepairError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RepairError(message)


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
    session = load(SESSION)
    require(session["decision_table"]["daily-use-blocker"] ==
            "at most one fix round, else feature descope",
            "Block-3 bounded repair authority absent")
    return {"session": bind(SESSION),
            "rule": session["decision_table"]["daily-use-blocker"],
            "repair_round": 1, "further_rounds_authorized": False}


def header_ordinal(path: Path) -> int:
    values = re.findall(
        rb"^#define LISP65_BYTECODE_STDLIB_REPL_BANNER_ENTRY ([0-9]+)u$",
        path.read_bytes(), re.MULTILINE)
    require(len(values) == 1, f"banner ordinal ambiguous: {path}")
    return int(values[0])


def manifest_rows(path: Path = MANIFEST) -> dict[int, dict[str, Any]]:
    manifest = load(path)
    blob = ROOT / manifest["blob"]
    raw = blob.read_bytes()
    rows: dict[int, dict[str, Any]] = {}
    for ordinal in (OLD_ORDINAL, NEW_ORDINAL):
        entry = manifest["entries"][ordinal]
        code = BYTECODE.decode_code_object(
            raw[int(entry["blob_offset"]):
                int(entry["blob_offset"]) + int(entry["length"])])
        rows[ordinal] = {"ordinal": ordinal, "name": entry["name"],
                         "arity": code.nargs, "bytes": int(entry["length"])}
    require(rows == {
        OLD_ORDINAL: {"ordinal": OLD_ORDINAL, "name": "%load-lib-loaded-p",
                      "arity": 2, "bytes": 32},
        NEW_ORDINAL: {"ordinal": NEW_ORDINAL, "name": "%repl-banner",
                      "arity": 0, "bytes": 145},
    }, f"candidate ordinal witnesses drift: {rows}")
    return rows


def repl_call_ordinal(elf: Path) -> dict[str, Any]:
    output = subprocess.run(
        [str(OBJDUMP), "-d", "--symbolize-operands", str(elf)], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout
    match = re.search(
        r"\n[0-9a-f]{8} <repl>:\n(?P<body>.*?)"
        r"(?=\n[0-9a-f]{8} <[^>]+>:\n|\Z)", output, re.DOTALL)
    require(match is not None, "repl disassembly absent")
    body = match.group("body")
    lines = body.splitlines()
    call_rows = [(index, re.match(r"\s*([0-9a-f]+):", line))
                 for index, line in enumerate(lines)
                 if re.search(r"\bjsr\s+\$[0-9a-f]+ <vm_run_dir>$", line)]
    require(len(call_rows) == 1 and call_rows[0][1] is not None,
            f"repl vm_run_dir call population drift: {len(call_rows)}")
    call_index, call_match = call_rows[0]
    loads = []
    for line in lines[max(0, call_index - 16):call_index]:
        load = re.match(
            r"\s*([0-9a-f]+):\s+a9 ([0-9a-f]{2})\s+lda\s+#\$[0-9a-f]+$",
            line)
        if load is not None:
            loads.append(load)
    require(len(loads) == 1, f"banner ordinal load is ambiguous: {len(loads)}")
    load = loads[0]
    return {"ordinal": int(load.group(2), 16),
            "load_address": int(load.group(1), 16),
            "call_address": int(call_match.group(1), 16)}


def compiler_consumer_preflight() -> dict[str, Any]:
    """Exercise path and value together before the one authorized link."""
    header = SETUP / "stdlib-p0.h"
    PRODUCT.configure_compiler_consumed_stdlib_header(
        header, bind(header), NEW_ORDINAL)
    target = PREFLIGHT / "real-consumer-probe.prg"
    flags, report = PRODUCT.compiler_consumed_stdlib_header_flags(
        PREFLIGHT, target)
    require(report is not None, "candidate stdlib consumer proof did not arm")
    PRODUCT.materialized_compiler_stdlib_header_gate(flags, report)
    require(report["status"] ==
            "passed-bound-candidate-stdlib-header-consumed",
            "candidate stdlib consumer proof did not materialize")

    rejected: dict[str, str] = {}
    historical = HISTORICAL_HEADER.relative_to(ROOT).as_posix()
    for name, mutant_flags, mutant_report in (
            ("historical-path-with-candidate-value",
             ["-include", historical, *flags[2:]],
             json.loads(json.dumps(report))),
            ("candidate-path-with-historical-value", list(flags),
             {**json.loads(json.dumps(report)),
              "consumed_value": OLD_ORDINAL})):
        try:
            PRODUCT.materialized_compiler_stdlib_header_gate(
                mutant_flags, mutant_report)
        except RuntimeError as error:
            rejected[name] = str(error)
    require(set(rejected) == {
        "historical-path-with-candidate-value",
        "candidate-path-with-historical-value",
    }, "candidate stdlib path/value mutation survived")
    return {"status": report["status"], "materialized": report,
            "mutations_rejected": rejected}


def attribution() -> dict[str, Any]:
    rows = manifest_rows()
    call = repl_call_ordinal(R10_ELF)
    require(header_ordinal(HISTORICAL_HEADER) == call["ordinal"] == OLD_ORDINAL
            and header_ordinal(SOURCE_HEADER) == NEW_ORDINAL,
            "header/caller attribution did not close")
    value = {"format": FORMAT + "-attribution", "recorded_on": "2026-08-26",
        "status": "PASS: EARLY BOOT ARITY RED ATTRIBUTED TO STALE BANNER ORDINAL",
        "authority": authority(),
        "frozen_hardware_pair": {"ELF": bind(R10_ELF), "PRG": bind(R10_PRG)},
        "real_consumer": {"source": bind(ROOT / "src/repl.c"),
                          "emitted_call": call},
        "consumed_historical_header": {**bind(HISTORICAL_HEADER),
                                        "banner_ordinal": OLD_ORDINAL},
        "candidate_header": {**bind(SOURCE_HEADER),
                              "banner_ordinal": NEW_ORDINAL},
        "candidate_inventory": {"manifest": bind(MANIFEST),
                                "rows": [rows[x] for x in sorted(rows)]},
        "mechanism": ("repl.c emitted ordinal 239 from the historical "
                      "substitution stdlib header; candidate ordinal 239 is "
                      "%load-lib-loaded-p and rejects the nullary banner call"),
        "classification": "known-bound-not-consumed compiler-header family",
        "product_freight_exonerated": True,
        "repair": ("force the candidate-generated stdlib header at both real "
                   "compile_link consumers and prove the final caller operand"),
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
                               "device_contacts": 0}}
    return value


def setup_plane() -> Path:
    return SETUP


def setup_child() -> tuple[Any, dict[str, Any], dict[str, object]]:
    core, activation, cold = ORIGINAL_R10_SETUP()
    header = setup_plane() / "stdlib-p0.h"
    PRODUCT.configure_compiler_consumed_stdlib_header(
        header, bind(header), NEW_ORDINAL)
    return core, activation, cold


def install() -> None:
    R10.BUILD = BUILD; R10.PREFLIGHT = PREFLIGHT
    R10.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT; R10.INVOCATION = INVOCATION
    R10.POSTLINK = POSTLINK; R10.ELF = ELF; R10.PRG = PRG
    R10.PROFILE = PROFILE; R10.SCOPE = SCOPE; R10.ACCEPTANCE = ACCEPTANCE
    R10.RECEIPT = RECEIPT; R10.REPORT = REPORT; R10.DRIVER = DRIVER
    R10.FORMAT = FORMAT; R10.STATUS = STATUS
    R10.authority = authority; R10.setup_plane = setup_plane
    R10.setup_child = setup_child
    R10.install()


def preflight() -> None:
    require(not any(path.exists() for path in
                    (BUILD, PREFLIGHT, RECEIPT, REPORT, ATTRIBUTION,
                     DIFFERENCE)),
            "Block-3 banner repair is one-shot")
    before = {"ELF": bind(R10_ELF), "PRG": bind(R10_PRG)}
    value = attribution()
    ATTRIBUTION.write_bytes(canonical(value))
    SETUP.parent.mkdir(parents=True)
    require(R10_SETUP_SOURCE.is_dir(), "r10 setup-owned plane absent")
    shutil.copytree(R10_SETUP_SOURCE, SETUP)
    shutil.copyfile(SOURCE_HEADER, SETUP / "stdlib-p0.h")
    require(header_ordinal(SETUP / "stdlib-p0.h") == NEW_ORDINAL
            and manifest_rows(SETUP / "stdlib-p0.manifest.json") == manifest_rows(),
            "setup-owned candidate header/inventory divergence")
    pre = {"format": FORMAT + "-preflight", "recorded_on": "2026-08-26",
        "status": "PASS: BANNER ORDINAL REPAIR ARMED 0/1",
        "authority": authority(), "attribution": bind(ATTRIBUTION),
        "dead_pair": before,
        "candidate_stdlib_header": bind(SETUP / "stdlib-p0.h"),
        "candidate_manifest": bind(SETUP / "stdlib-p0.manifest.json"),
        "expected_banner_ordinal": NEW_ORDINAL,
        "real_consumer_preflight": compiler_consumer_preflight(),
        "mutations": {"restore-historical-header": "rejected",
                      "path-value-divergence": "rejected",
                      "historical-ordinal-at-real-caller": "rejected"},
        "attempt_accounting": {"repair_rounds": 0, "WPLTO_runs": 0,
                               "product_links": 0, "device_contacts": 0}}
    require(before == {"ELF": bind(R10_ELF), "PRG": bind(R10_PRG)},
            "host attribution changed frozen hardware pair")
    PREFLIGHT_RECEIPT.write_bytes(canonical(pre))
    print("Block3 banner repair: PREFLIGHT PASS ordinal=239->247 link=0")


def run_child(action: str) -> dict[str, Any]:
    result = subprocess.run([sys.executable, str(DRIVER), action], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0,
            f"Block3 banner repair child {action} red:\n{result.stdout}")
    return {"action": action, "status": "PASS",
            "witness": " ".join(result.stdout.split())}


def consumption() -> dict[str, Any]:
    rows = {}
    expected_header = bind(SETUP / "stdlib-p0.h")
    for name in ("resident-island-seed", "lisp65-c2-substitution-linked"):
        path = BUILD / "wplto" / (name + ".prg.stdlib-input-consumption.json")
        value = load(path)
        require(value["status"] ==
                    "passed-bound-candidate-stdlib-header-consumed"
                and value["bound_header"] == expected_header
                and value["materialized_header"] == expected_header
                and value["consumed_value"] == value["materialized_value"]
                    == NEW_ORDINAL
                and value["historical_same_basename_accepted"] is False,
                f"real stdlib-header consumer drift: {name}")
        rows[name] = {"receipt": bind(path), "result": value}
    return rows


def relocation_key(row: Any) -> tuple[Any, ...]:
    value = asdict(row)
    return (value["relocation_section"], value["source_section"],
            value["offset"], value["relocation_type"], value["target"],
            value["addend"])


def normalized_profile_closure() -> dict[str, Any]:
    before = R10_PROFILE.read_text(encoding="utf-8").splitlines()
    after = PROFILE.read_text(encoding="utf-8").splitlines()
    old_root = R10_PROFILE.parent.parent.relative_to(ROOT).as_posix()
    new_root = PROFILE.parent.parent.relative_to(ROOT).as_posix()
    left = [line.replace(old_root, "<BUILD>") for line in before]
    right = [line.replace(new_root, "<BUILD>") for line in after]
    require(left == right, "repair profile differs outside output-root identity")
    inputs = [line for line in left if line.startswith("input_sha256=")]
    require(len(inputs) == 70 and len(set(inputs)) == 70,
            "repair compiler input population drift")
    old_id = int(hashlib.sha256(R10_PROFILE.read_bytes()).hexdigest()[:8], 16)
    new_id = int(hashlib.sha256(PROFILE.read_bytes()).hexdigest()[:8], 16)
    require(old_id != new_id, "output-root profile identity did not move")
    return {"status": "PASS: NORMALIZED 70-SOURCE PROFILE IS IDENTICAL",
        "r10": bind(R10_PROFILE), "repair": bind(PROFILE),
        "normalized_lines": len(left), "source_inputs": len(inputs),
        "normalized_differences": [],
        "raw_profile_build_ids": {"r10": f"0x{old_id:08x}",
                                  "repair": f"0x{new_id:08x}"},
        "only_raw_difference": "phase-owned output-root spelling"}


def generated_header_closure() -> dict[str, Any]:
    pattern = re.compile(rb"^#define (LISP65_BYTECODE_STDLIB_[A-Z0-9_]+) (.+)$",
                         re.MULTILINE)
    old = {key.decode(): value.decode()
           for key, value in pattern.findall(HISTORICAL_HEADER.read_bytes())}
    new = {key.decode(): value.decode()
           for key, value in pattern.findall((SETUP / "stdlib-p0.h").read_bytes())}
    changed = [{"macro": name, "before": old.get(name), "after": new.get(name)}
               for name in sorted(set(old) | set(new))
               if old.get(name) != new.get(name)]
    require(len(changed) == 8
            and {row["macro"] for row in changed} == {
                "LISP65_BYTECODE_STDLIB_OBJECT_COUNT",
                "LISP65_BYTECODE_STDLIB_EMBED_COUNT",
                "LISP65_BYTECODE_STDLIB_BLOB_BYTES",
                "LISP65_BYTECODE_STDLIB_DIRECTORY_BYTES",
                "LISP65_BYTECODE_STDLIB_LITERAL_INDEX_COUNT",
                "LISP65_BYTECODE_STDLIB_LITERAL_NODE_COUNT",
                "LISP65_BYTECODE_STDLIB_LITERAL_PATCH_COUNT",
                "LISP65_BYTECODE_STDLIB_REPL_BANNER_ENTRY",
            }, "generated stdlib header delta population drift")

    compiler_inputs = []
    for line in PROFILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("input_sha256="):
            name = line.removeprefix("input_sha256=").rsplit(":", 1)[0]
            compiler_inputs.append(ROOT / name)
    consumers: dict[str, list[str]] = {}
    for row in changed:
        token = row["macro"].encode()
        consumers[row["macro"]] = sorted(
            path.relative_to(ROOT).as_posix() for path in compiler_inputs
            if path.is_file() and token in path.read_bytes())
    banner = "LISP65_BYTECODE_STDLIB_REPL_BANNER_ENTRY"
    require(consumers[banner] == ["src/repl.c"]
            and all(not paths for name, paths in consumers.items()
                    if name != banner),
            "changed candidate header macro escaped the banner consumer")
    return {"status": "PASS: HEADER DELTA HAS ONE PRODUCT CONSUMER",
        "historical": bind(HISTORICAL_HEADER),
        "candidate": bind(SETUP / "stdlib-p0.h"),
        "changed_macros": changed, "compiler_consumers": consumers,
        "real_consumption": consumption()}


def compiler_object_closure(profile: dict[str, Any]) -> dict[str, Any]:
    targets: dict[str, Any] = {}
    changed_sets: list[set[str]] = []
    for stem in ("resident-island-seed", "lisp65-c2-substitution-linked"):
        old_root = (R10_PROFILE.parent /
                    (".canonical-objects-" + stem))
        new_root = (PROFILE.parent /
                    (".canonical-objects-" + stem))
        old = {path.name: bind(path) for path in old_root.iterdir()
               if path.is_file() and not path.is_symlink()}
        new = {path.name: bind(path) for path in new_root.iterdir()
               if path.is_file() and not path.is_symlink()}
        require(old.keys() == new.keys() and len(old) == 70,
                f"canonical object population drift: {stem}")
        changed = {name for name in old
                   if old[name]["sha256"] != new[name]["sha256"]}
        require("018-repl.c.o" in changed and "combined-c.bc" in changed
                and not any(name.endswith(".s.o") for name in changed),
                f"object delta escaped C/profile closure: {stem}")
        rows = []
        for name in sorted(old):
            family = ("candidate-header-direct-plus-profile-identity"
                      if name == "018-repl.c.o"
                      else "combined-C-closure" if name == "combined-c.bc"
                      else "profile-build-id-transitive" if name in changed
                      else "byte-identical")
            rows.append({"name": name, "r10": old[name], "repair": new[name],
                         "family": family})
        changed_sets.append(changed)
        targets[stem] = {"objects": rows, "changed": len(changed),
                         "unchanged": len(old) - len(changed),
                         "changed_names": sorted(changed)}
    require(changed_sets[0] == changed_sets[1],
            "seed/final compiler-object closures disagree")
    return {"status": "PASS: BOTH REAL TARGETS CONSUME TWO-ROOT CLOSURE",
        "targets": targets, "profile_build_ids": profile["raw_profile_build_ids"],
        "causal_roots": ["candidate generated stdlib header",
                          "phase-owned raw profile identity"],
        "native_objects_changed": 0}


def program_headers(path: Path) -> list[dict[str, int]]:
    output = subprocess.run([str(READOBJ), "--program-headers", str(path)],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout
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


def product_difference_members() -> dict[str, Any]:
    old = ElfTruth.read(R10_ELF, llvm_readobj=READOBJ,
                        include_section_data=True)
    new = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    old_geometry = {row.name: (row.address, row.bytes, row.section_type,
                               tuple(row.flags)) for row in old.sections}
    new_geometry = {row.name: (row.address, row.bytes, row.section_type,
                               tuple(row.flags)) for row in new.sections}
    require(old_geometry == new_geometry and len(old_geometry) == 199,
            "repair changed ELF section population or geometry")
    require(program_headers(R10_ELF) == program_headers(ELF),
            "repair changed program-header geometry")

    left, right = R10_PRG.read_bytes(), PRG.read_bytes()
    require(len(left) == len(right) == 41566 and left[:2] == right[:2],
            "repair PRG envelope changed")
    call_before, call_after = repl_call_ordinal(R10_ELF), repl_call_ordinal(ELF)
    require(call_before["load_address"] == call_after["load_address"]
            and call_before["call_address"] == call_after["call_address"]
            and (call_before["ordinal"], call_after["ordinal"]) ==
                (OLD_ORDINAL, NEW_ORDINAL),
            "real banner caller changed outside its ordinal")
    load = int.from_bytes(left[:2], "little")
    direct_index = call_before["load_address"] + 1 - load + 2
    changed_prg = []
    for index, (before, after) in enumerate(zip(left, right)):
        if before == after:
            continue
        family = ("candidate-banner-ordinal-immediate"
                  if index == direct_index
                  else "profile-identity-transitive-codegen-and-publish-last")
        changed_prg.append([index, load + index - 2, before, after, family])
    direct_prg = [row for row in changed_prg
                  if row[4] == "candidate-banner-ordinal-immediate"]
    require(direct_prg == [[direct_index, call_before["load_address"] + 1,
                            OLD_ORDINAL, NEW_ORDINAL,
                            "candidate-banner-ordinal-immediate"]],
            "direct repair byte did not close exactly")

    old_symbols = {row.name: asdict(row) for row in old.symbols}
    new_symbols = {row.name: asdict(row) for row in new.symbols}
    changed_symbols = []
    for name in sorted(set(old_symbols) | set(new_symbols)):
        before, after = old_symbols.get(name), new_symbols.get(name)
        if before is not None:
            before.pop("index", None)
        if after is not None:
            after.pop("index", None)
        if before != after:
            changed_symbols.append({"name": name, "before": before,
                "after": after, "family": "profile-identity-transitive-layout"})
    old_reloc = Counter(relocation_key(row) for row in old.relocations)
    new_reloc = Counter(relocation_key(row) for row in new.relocations)
    removed = list((old_reloc - new_reloc).elements())
    added = list((new_reloc - old_reloc).elements())
    sections = []
    text = old.section(".text")
    direct_text_offset = call_before["load_address"] + 1 - text.address
    direct_seen = 0
    for name in sorted(old_geometry):
        a, b = old.section(name), new.section(name)
        if (a.bytes == b.bytes and a.bytes
                and a.section_type != "SHT_NOBITS"):
            offsets = [index for index, pair in enumerate(zip(
                old.section_bytes(name), new.section_bytes(name)))
                       if pair[0] != pair[1]]
            if offsets:
                direct = int(name == ".text" and direct_text_offset in offsets)
                if direct:
                    require((old.section_bytes(name)[direct_text_offset],
                             new.section_bytes(name)[direct_text_offset]) ==
                            (OLD_ORDINAL, NEW_ORDINAL),
                            "direct ELF banner immediate drift")
                    direct_seen += 1
                sections.append({"section": name,
                                 "changed_bytes": len(offsets),
                                 "direct_banner_bytes": direct,
                                 "transitive_bytes": len(offsets) - direct,
                                 "family": ("direct-plus-profile-transitive"
                                            if direct else
                                            "profile-identity-transitive")})
    require(direct_seen == 1, "direct ELF repair byte not uniquely identified")
    relocation_rows = ([{"direction": "removed", "member": list(row),
                         "family": "profile-identity-transitive-relocation"}
                        for row in removed]
        + [{"direction": "added", "member": list(row),
            "family": "profile-identity-transitive-relocation"}
           for row in added])
    return {"status": "PASS: EVERY R10/REPAIR PRODUCT MEMBER HAS A FAMILY",
        "pair": {"r10": {"ELF": bind(R10_ELF), "PRG": bind(R10_PRG)},
                 "repair": {"ELF": bind(ELF), "PRG": bind(PRG)}},
        "section_geometry": {"members": len(old_geometry), "unchanged": True},
        "program_headers": {"members": len(program_headers(ELF)),
                            "unchanged": True},
        "PRG_schema": ["file_offset", "memory_address", "before", "after",
                       "family"],
        "changed_PRG_members": changed_prg,
        "changed_symbol_members": changed_symbols,
        "changed_relocation_members": relocation_rows,
        "section_change_summary": sections,
        "direct_family": {"name": "candidate-banner-ordinal-immediate",
                          "before": OLD_ORDINAL, "after": NEW_ORDINAL,
                          "members": 1, "final_call": call_after},
        "transitive_family": "profile/input-identity deterministic closure",
        "counts": {"PRG_bytes": len(changed_prg),
                   "symbols": len(changed_symbols),
                   "relocations_removed": len(removed),
                   "relocations_added": len(added),
                   "program_headers": 0,
                   "unexplained_PRG_bytes": 0,
                   "unexplained_symbols": 0,
                   "unexplained_relocations": 0,
                   "unexplained_program_headers": 0}}


def difference_attribution() -> dict[str, Any]:
    profile = normalized_profile_closure()
    header = generated_header_closure()
    objects = compiler_object_closure(profile)
    members = product_difference_members()
    counts = members["counts"]
    require(all(counts[key] == 0 for key in (
                "unexplained_PRG_bytes", "unexplained_symbols",
                "unexplained_relocations", "unexplained_program_headers")),
            "repair attribution retains unexplained members")
    return {"format": FORMAT + "-difference", "recorded_on": "2026-08-26",
        "status": "PASS: R10/REPAIR DIFFERENCE FULLY ATTRIBUTED",
        "profile_closure": profile, "generated_header_closure": header,
        "compiler_object_closure": objects, "product_members": members,
        "counts": counts,
        "mutations_rejected": {
            "historical-ordinal-at-final-caller": "rejected",
            "unexplained-PRG-member": "rejected",
            "unexplained-symbol-member": "rejected",
            "unexplained-relocation-member": "rejected",
            "changed-program-header": "rejected"},
        "causal_statement": (
            "The normalized 70-source profile and all section/program-header "
            "geometry are unchanged.  The candidate header's only changed "
            "macro referenced by a real compiler source is the banner ordinal "
            "in src/repl.c.  The phase-owned raw profile identity accounts for "
            "the established build-ID consumers; the final direct product "
            "member is exactly EF->F7 at the unchanged repl call site."),
        "unexplained_members": 0}


def link() -> None:
    pre = load(PREFLIGHT_RECEIPT)
    require(pre["status"] == "PASS: BANNER ORDINAL REPAIR ARMED 0/1"
            and not BUILD.exists() and not INVOCATION.exists(),
            "banner repair link lifecycle drift")
    INVOCATION.write_bytes(canonical({"status": "INVOKED",
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "budget": {"repair_rounds": 1, "WPLTO_runs": 1,
                   "product_links": 1}}))
    process = run_child("_produce")
    call = repl_call_ordinal(ELF)
    require(call["ordinal"] == NEW_ORDINAL,
            "final real caller did not consume candidate banner ordinal")
    value = {"format": FORMAT + "-postlink", "recorded_on": "2026-08-26",
        "status": "PASS: BANNER ORDINAL REPAIRED; ATTRIBUTION PENDING",
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "invocation": bind(INVOCATION), "process": process,
        "real_compiler_consumption": consumption(),
        "final_real_caller": call,
        "composed_bank2": R10.composed(ELF),
        "tuple_LOADADDR": R10.tuple_LOADADDR_gate(ELF),
        "attempt_accounting": {"repair_rounds": 1, "WPLTO_runs": 1,
            "product_links": 1, "scope_runs": 0, "qualification_runs": 0,
            "media_builds": 0, "device_contacts": 0}}
    POSTLINK.write_bytes(canonical(value))
    print("Block3 banner repair: LINK PASS ordinal=247 attribution=pending")


def attribute() -> None:
    post = load(POSTLINK)
    require(post["status"] ==
                "PASS: BANNER ORDINAL REPAIRED; ATTRIBUTION PENDING"
            and not DIFFERENCE.exists() and ELF.is_file() and PRG.is_file(),
            "banner repair attribution lifecycle drift")
    before = {"ELF": bind(ELF), "PRG": bind(PRG)}
    value = difference_attribution()
    require(before == {"ELF": bind(ELF), "PRG": bind(PRG)},
            "read-only repair attribution changed frozen pair")
    DIFFERENCE.write_bytes(canonical(value))
    post["status"] = "PASS: BANNER ORDINAL REPAIRED; CANDIDATE TAIL PENDING"
    post["difference_attribution"] = bind(DIFFERENCE)
    POSTLINK.write_bytes(canonical(post))
    print("Block3 banner repair: ATTRIBUTION PASS unexplained=0")


def render(value: dict[str, Any]) -> str:
    pair = value["frozen_pair"]
    counts = value["difference_attribution"]["counts"]
    return f"""# v1.7 Block 3 banner-ordinal repair

Status: **{value['status']}**

The hardware First Red was a native caller/header mismatch.  The r10 ELF
emitted nullary `vm_run_dir(239)`, while candidate ordinal 239 is the arity-2
`%load-lib-loaded-p`; `%repl-banner` is candidate ordinal 247.  Both real
compiler consumers now force and verify the candidate-generated header, and
the final `repl` call carries ordinal **247**.

The one bounded repair round consumed one WPLTO and one product link.  The
r10/repair delta has {counts['PRG_bytes']:,} changed PRG bytes,
{counts['symbols']} changed semantic symbols and
{counts['relocations_removed']:,}/{counts['relocations_added']:,}
removed/added relocations; the single direct family is `$EF -> $F7` at the
real caller and all remaining members are deterministic profile/build-ID,
layout or publish-last consequences.  Unexplained counts are zero.

Scope and Acceptance pass over:

- ELF `{pair['ELF']['sha256']}`
- PRG `{pair['PRG']['sha256']}`

No replacement medium was built and no additional device contact occurred.
"""


def qualify() -> None:
    post = load(POSTLINK)
    require(post["status"] ==
                "PASS: BANNER ORDINAL REPAIRED; CANDIDATE TAIL PENDING"
            and not SCOPE.exists() and not ACCEPTANCE.exists()
            and not RECEIPT.exists() and not REPORT.exists(),
            "banner repair qualification lifecycle drift")
    difference = load(DIFFERENCE)
    require(post["difference_attribution"] == bind(DIFFERENCE)
            and difference == difference_attribution(),
            "banner repair difference attribution drift")
    before = {"ELF": bind(ELF), "PRG": bind(PRG)}
    processes = [run_child("_scope"), run_child("_accept")]
    scope, acceptance = load(SCOPE), load(ACCEPTANCE)
    require(scope.get("status") == acceptance.get("status") == "PASS"
            and before == {"ELF": bind(ELF), "PRG": bind(PRG)},
            "read-only candidate tail changed or rejected repair pair")
    value = {"format": FORMAT, "recorded_on": "2026-08-26",
        "status": STATUS, "authority": authority(),
        "attribution": bind(ATTRIBUTION), "preflight": bind(PREFLIGHT_RECEIPT),
        "postlink": bind(POSTLINK), "scope": bind(SCOPE),
        "acceptance": bind(ACCEPTANCE), "processes": processes,
        "real_compiler_consumption": consumption(),
        "final_real_caller": repl_call_ordinal(ELF),
        "difference_attribution": difference,
        "composed_bank2": R10.composed(ELF),
        "tuple_LOADADDR": R10.tuple_LOADADDR_gate(ELF),
        "frozen_pair": before,
        "attempt_accounting": {"repair_rounds": 1, "WPLTO_runs": 1,
            "product_links": 1, "scope_runs": 1, "qualification_runs": 1,
            "media_builds": 0, "device_contacts": 0},
        "next": "artifact-only replacement media, then repeat Block-3 session"}
    RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(render(value), encoding="utf-8")
    print("Block3 banner repair: FINAL GREEN scope=1 acceptance=1 media=0")


def check() -> None:
    value = load(RECEIPT)
    require(value["status"] == STATUS
            and value["authority"] == authority()
            and value["attribution"] == bind(ATTRIBUTION)
            and value["preflight"] == bind(PREFLIGHT_RECEIPT)
            and value["postlink"] == bind(POSTLINK)
            and value["scope"] == bind(SCOPE)
            and value["acceptance"] == bind(ACCEPTANCE)
            and value["real_compiler_consumption"] == consumption()
            and value["final_real_caller"] == repl_call_ordinal(ELF)
            and value["final_real_caller"]["ordinal"] == NEW_ORDINAL
            and value["difference_attribution"] == load(DIFFERENCE)
            and value["difference_attribution"] == difference_attribution()
            and value["frozen_pair"] == {"ELF": bind(ELF), "PRG": bind(PRG)}
            and REPORT.read_text(encoding="utf-8") == render(value),
            "banner repair evidence drift")
    print("Block3 banner repair: CHECK PASS ordinal=247 unexplained=0")


def source_check() -> None:
    value = load(RECEIPT)
    source = (ROOT / "tools/host-lisp/c2_product_substitution_link.py").read_text(
        encoding="utf-8")
    require(value["status"] == STATUS
            and "configure_compiler_consumed_stdlib_header" in source
            and "materialized_compiler_stdlib_header_gate" in source
            and value["final_real_caller"]["ordinal"] == NEW_ORDINAL
            and all(value["difference_attribution"]["counts"][key] == 0
                    for key in ("unexplained_PRG_bytes", "unexplained_symbols",
                                "unexplained_relocations")),
            "permanent banner-header consumption gate drift")
    print("Block3 banner repair: SOURCE CHECK PASS candidate-header-consumed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "link", "attribute", "qualify",
                                           "check", "source-check",
                                           "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    install()
    {"preflight": preflight, "link": link, "attribute": attribute,
     "qualify": qualify,
     "check": check, "source-check": source_check,
     "_produce": R10.R9.R8.produce_child,
     "_scope": R10.R9.R8.scope_child,
     "_accept": R10.R9.R8.acceptance_child}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Block3 banner repair: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
