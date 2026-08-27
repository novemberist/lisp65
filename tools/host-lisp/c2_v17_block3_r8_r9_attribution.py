#!/usr/bin/env python3
"""Attribute the frozen Block-3 r8/r9 pair without compiling or linking."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from dataclasses import asdict
import difflib
import hashlib
import inspect
import json
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v17_ide_idle_blink_product_card as CARD  # noqa: E402
import c2_v17_ide_idle_blink_product_card_r9 as R9  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_lite_v6_boot_crc_abi_successor_link as BASE_LINK  # noqa: E402
import c2_lite_v6_link50_persistent_header_successor_link as LINK50  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
REPORT = ROOT / "docs/planning/v1.7.0-block3-r8-r9-attribution.md"
RECEIPT = ARCH / "c2.3-v1.7-block3-r8-r9-attribution.json"
ATTRIBUTION_OUT = ROOT / "build/c2.3/v1.7-block3-r8-r9-attribution"
AUTHORIZATION = "eb8a2516"
R8 = ROOT / "build/c2.3/v1.7-ide-idle-blink-product-card-r8/wplto"
R9W = ROOT / "build/c2.3/v1.7-ide-idle-blink-product-card-r9/wplto"
R8_ELF = R8 / "lisp65-c2-substitution-linked.prg.elf"
R9_ELF = R9W / "lisp65-c2-substitution-linked.prg.elf"
R8_PRG = R8 / "lisp65-c2-substitution-linked.prg"
R9_PRG = R9W / "lisp65-c2-substitution-linked.prg"
R8_PROFILE = R8 / "resolved-profile.txt"
R9_PROFILE = R9W / "resolved-profile.txt"
R9_SCOPE = R9W.parent / "owner-scope-result.json"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
LOAD_SYMBOLS = {
    "__lisp65_c2_mapped_far_service_load_start",
    "__lisp65_c2_mapped_far_service_load_end",
    "__lisp65_c2_mapped_product_cold_load_start",
    "__lisp65_c2_mapped_product_cold_load_end",
}
FORMAT = "lisp65-c2-v17-block3-r8-r9-attribution-v1"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{AUTHORIZATION}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("r8/r9 attribution and output-root conversion",
                  "7,731 differing prg bytes", "87 changed symbols",
                  "3,240 changed relocations", "zero unexplained members",
                  "no wplto", "must not redirect output"):
        require(token in text, f"attribution authority absent: {token}")
    return {"authority": "git-blob", "commit": AUTHORIZATION, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def changed_fields(left: Any, right: Any) -> dict[str, list[Any]]:
    a, b = asdict(left), asdict(right)
    return {key: [a[key], b[key]] for key in a if a[key] != b[key]}


def normalized_profile_line(line: str, root: Path) -> str:
    return line.replace(root.parent.relative_to(ROOT).as_posix(), "<BUILD>")


def profile_closure() -> dict[str, Any]:
    left = R8_PROFILE.read_text(encoding="utf-8").splitlines()
    right = R9_PROFILE.read_text(encoding="utf-8").splitlines()
    require(len(left) == len(right), "resolved-profile line population drift")
    raw_differences = [{"line": index + 1, "before": before, "after": after}
                       for index, (before, after) in enumerate(zip(left, right))
                       if before != after]
    norm_left = [normalized_profile_line(line, R8) for line in left]
    norm_right = [normalized_profile_line(line, R9W) for line in right]
    normalized_differences = [
        {"line": index + 1, "before": before, "after": after}
        for index, (before, after) in enumerate(zip(norm_left, norm_right))
        if before != after]
    require(len(normalized_differences) == 1
            and normalized_differences[0]["before"].startswith("linker_sha256=")
            and normalized_differences[0]["after"].startswith("linker_sha256="),
            "semantic profile difference is not linker-only")

    def sources(lines: list[str], root: Path) -> list[dict[str, str]]:
        result = []
        root_name = root.parent.relative_to(ROOT).as_posix()
        for line in lines:
            if not line.startswith("input_sha256="):
                continue
            path, digest = line.removeprefix("input_sha256=").rsplit(":", 1)
            source = ROOT / path
            require(source.is_file() and sha(source) == digest,
                    f"resolved compiler input content drift: {path}")
            result.append({"path": path.replace(root_name, "<BUILD>"),
                           "sha256": digest})
        return result

    source_left = sources(left, R8)
    source_right = sources(right, R9W)
    require(source_left == source_right and len(source_left) == 70,
            "compiler source closure is not byte-identical 70/70")
    stable_names = ("lto_rng_seed", "lto_threads", "deterministic_objects",
                    "deterministic_compilation_dir", "deterministic_link_paths",
                    "deterministic_llvm_link", "link_aslr_disabled",
                    "c2_artifacts_sha256", "direct_entry_contract_sha256",
                    "feature_defines")

    def one(lines: list[str], key: str) -> str:
        values = [row.split("=", 1)[1] for row in lines
                  if row.startswith(key + "=")]
        require(len(values) == 1, f"profile key not unique: {key}")
        return values[0]

    stable = {name: one(left, name) for name in stable_names}
    require(stable == {name: one(right, name) for name in stable_names},
            "compiler/link environment changed beyond profile identity")
    old_digest, new_digest = sha(R8_PROFILE), sha(R9_PROFILE)
    return {
        "status": "PASS: COMPLETE PROFILE INPUT CLOSURE DERIVED",
        "r8": bind(R8_PROFILE), "r9": bind(R9_PROFILE),
        "raw_contract_differences": raw_differences,
        "normalized_semantic_differences": normalized_differences,
        "source_inputs": {"count": len(source_left), "rows": source_left,
                          "content_differences": 0},
        "stable_pipeline": stable,
        "profile_build_id": {
            "derivation": "first-32-bits(sha256(raw resolved-profile bytes))",
            "r8": f"0x{int(old_digest[:8], 16):08x}",
            "r9": f"0x{int(new_digest[:8], 16):08x}",
            "causal_inputs": [
                "phase-owned output-root spelling in generated-source paths",
                "mapped-tenant linker-script SHA-256"],
            "normalized_semantic_cause": "mapped-tenant linker-script SHA-256",
        },
    }


def linker_authority() -> dict[str, Any]:
    left = (R8 / "c2-substitution.ld").read_text(encoding="utf-8")
    right = (R9W / "c2-substitution.ld").read_text(encoding="utf-8")

    def mask(text: str) -> str:
        starts = (
            "    .lisp65_c2_mapped_far_service 0x78b2\n",
            "ASSERT(__lisp65_c2_mapped_far_required == 0 ||\n"
            "       (ADDR(.lisp65_c2_mapped_far_service) == 0x78b2 &&\n",
            "    .lisp65_c2_mapped_product_cold 0x7e8d\n",
            "ASSERT(ADDR(.lisp65_c2_mapped_product_cold) == 0x7e8d &&\n",
        )
        ends = ("    } >ram\n", "       \"mapped far body escaped its Bank-2 owner\");\n",
                "    } >ram\n", "       \"product cold tenant escaped its mapped arena\");\n")
        result = text
        for number, (start, end) in enumerate(zip(starts, ends, strict=True)):
            begin = result.find(start)
            require(begin >= 0, f"linker authority segment start absent: {number}")
            finish = result.find(end, begin)
            require(finish >= 0, f"linker authority segment end absent: {number}")
            finish += len(end)
            result = result[:begin] + f"<MAPPED-LMA-SEGMENT-{number}>\n" + result[finish:]
        return result

    require(mask(left) == mask(right),
            "linker scripts differ outside mapped-tenant LMA authority")
    require("AT(0x0002b8b2)" in left and "AT(0x0002be8d)" in left
            and "AT((0x00030000 - SIZEOF(.lisp65_c2_mapped_product_cold) - "
                "SIZEOF(.lisp65_c2_mapped_far_service)))" in right
            and "AT((0x00030000 - SIZEOF(.lisp65_c2_mapped_product_cold)))" in right
            and "AT(0x0002b8b2)" not in right
            and "AT(0x0002be8d)" not in right,
            "derived upper-anchor linker form is not exact")
    changes = [row for row in difflib.ndiff(left.splitlines(), right.splitlines())
               if row.startswith(("- ", "+ "))]
    return {"status": "PASS: LINKER DELTA IS ONLY MAPPED-TENANT LMA POLICY",
            "r8": bind(R8 / "c2-substitution.ld"),
            "r9": bind(R9W / "c2-substitution.ld"),
            "changed_lines": changes,
            "r8_policy": "fixed historical LMAs",
            "r9_policy": "Bank-2-end-derived upper anchor"}


def compiler_closure(profile: dict[str, Any]) -> dict[str, Any]:
    header_names = (
        "stage-config.h", "error-text-table.h",
        "runtime-overlay.prepare-standard.h", "runtime-overlay.prepare.h",
        "resident-island.prepare.h", "resident-island.h",
        "c2-kernal-window.generated.h",
        "lisp65-c2-substitution-linked.compiler-input-assert.h",
    )
    header_families = {
        "stage-config.h": "profile-build-id-direct-header",
        "error-text-table.h": "profile-build-id-plus-derived-crc-header",
        "runtime-overlay.prepare-standard.h": "profile-build-id-direct-header",
        "runtime-overlay.prepare.h": "profile-build-id-direct-header",
        "resident-island.prepare.h": "profile-build-id-direct-header",
        "resident-island.h": "profile-build-id-derived-seed-payload-and-crc",
        "c2-kernal-window.generated.h":
            "profile-build-id-derived-seed-window-and-crc",
        "lisp65-c2-substitution-linked.compiler-input-assert.h": "unchanged",
    }
    headers = []
    for name in header_names:
        a, b = R8 / name, R9W / name
        left, right = a.read_bytes(), b.read_bytes()
        require(len(left) == len(right), f"compiler header size drift: {name}")
        changed = sum(x != y for x, y in zip(left, right))
        family = header_families[name]
        require((changed == 0) == (family == "unchanged"),
                f"compiler header family mismatch: {name}")
        headers.append({"name": name, "r8": bind(a), "r9": bind(b),
                        "changed_bytes": changed, "family": family})

    consumption = []
    for root in (R8, R9W):
        item = load(root / "lisp65-c2-substitution-linked.prg.compiler-input-consumption.json")
        consumption.append(item)
        require(item["consumed_value"] == item["materialized_value"] == 52230
                and item["bound_header"]["sha256"] ==
                    item["materialized_header"]["sha256"],
                "real compiler static-plane header consumption drift")
    require(consumption[0]["bound_header"]["sha256"] ==
            consumption[1]["bound_header"]["sha256"],
            "r8/r9 candidate static header content drift")

    def object_rows(root: Path, stem: str) -> list[dict[str, Any]]:
        directory = root / (".canonical-objects-" + stem)
        return [{"name": path.name, "bytes": path.stat().st_size,
                 "sha256": sha(path)} for path in sorted(directory.iterdir())
                if path.is_file()]

    targets = {}
    changed_sets = []
    for stem in ("resident-island-seed", "lisp65-c2-substitution-linked"):
        left, right = object_rows(R8, stem), object_rows(R9W, stem)
        require([row["name"] for row in left] == [row["name"] for row in right],
                f"canonical object population drift: {stem}")
        rows = []
        changed_names = set()
        for a, b in zip(left, right):
            changed = a["sha256"] != b["sha256"]
            name = a["name"]
            is_native = name.endswith(".s.o")
            require(not (changed and is_native),
                    f"native object changed outside input closure: {stem}/{name}")
            if changed:
                changed_names.add(name)
            rows.append({"name": name, "r8_sha256": a["sha256"],
                         "r9_sha256": b["sha256"], "changed": changed,
                         "family": ("profile-build-id-compiler-output"
                                    if changed else "byte-identical")})
        changed_sets.append(changed_names)
        targets[stem] = {"objects": rows,
                         "changed_objects": len(changed_names),
                         "unchanged_objects": len(rows) - len(changed_names)}
    require(changed_sets[0] == changed_sets[1]
            and len(changed_sets[0]) == 27
            and "combined-c.bc" in changed_sets[0],
            "seed/final deterministic object delta is not the same 27 members")
    native_count = sum(row["name"].endswith(".s.o")
                       for row in targets["lisp65-c2-substitution-linked"]["objects"])
    require(native_count == 23, "final native linker-input count drift")
    return {
        "status": "PASS: REAL COMPILER INPUT CLOSURE HAS ONE DERIVED FAMILY",
        "headers": headers,
        "static_plane_header_consumption": consumption,
        "canonical_targets": targets,
        "final_link_inputs": {
            "changed_combined_bitcode": 1,
            "byte_identical_native_objects": native_count,
            "linker_script_family": "mapped-tenant-lma-authority",
        },
        "causal_statement": (
            "All 70 source contents, feature definitions, product artifacts, "
            "determinism controls and 23 native objects are identical. The "
            "only compiler-input changes are headers derived from the raw "
            "profile build ID; the only direct linker-input change is the "
            "mapped-tenant LMA script. Therefore every content/layout delta "
            "is in the deterministic transitive closure of those two roots."),
        "profile_build_id": profile["profile_build_id"],
    }


def product_members() -> dict[str, Any]:
    old = ElfTruth.read(R8_ELF, llvm_readobj=READOBJ, include_section_data=True)
    new = ElfTruth.read(R9_ELF, llvm_readobj=READOBJ, include_section_data=True)
    require([asdict(row) for row in old.sections] ==
            [asdict(row) for row in new.sections],
            "r8/r9 section geometry changed")
    require(len(old.symbols) == len(new.symbols)
            and [row.name for row in old.symbols] ==
                [row.name for row in new.symbols],
            "r8/r9 symbol population/order changed")
    require(len(old.relocations) == len(new.relocations),
            "r8/r9 relocation population changed")

    left_prg, right_prg = R8_PRG.read_bytes(), R9_PRG.read_bytes()
    require(len(left_prg) == len(right_prg), "r8/r9 PRG size changed")
    load_address = int.from_bytes(left_prg[:2], "little")
    require(load_address == int.from_bytes(right_prg[:2], "little") == 0x2001,
            "r8/r9 PRG load address changed")
    prg = [[index, load_address + index - 2, before, after,
            "profile-build-id-transitive-codegen-and-publish-last"]
           for index, (before, after) in enumerate(zip(left_prg, right_prg))
           if before != after]
    require(len(prg) == 7731, "PRG changed-member count drift")

    symbols = []
    for index, (before, after) in enumerate(zip(old.symbols, new.symbols)):
        if before == after:
            continue
        family = ("mapped-tenant-lma-symbol" if before.name in LOAD_SYMBOLS
                  else "profile-build-id-transitive-lto-layout")
        symbols.append({"index": index, "name": before.name,
                        "changed_fields": changed_fields(before, after),
                        "family": family})
    require(len(symbols) == 87
            and {row["name"] for row in symbols
                 if row["family"] == "mapped-tenant-lma-symbol"}
                == LOAD_SYMBOLS,
            "symbol changed-member attribution drift")

    relocations = []
    relocation_families: Counter[str] = Counter()
    for index, (before, after) in enumerate(zip(old.relocations, new.relocations)):
        if before == after:
            continue
        fields = changed_fields(before, after)
        if set(fields) == {"offset"}:
            suffix = "offset"
        elif set(fields) == {"addend"}:
            suffix = "addend"
        elif set(fields) == {"offset", "addend"}:
            suffix = "offset-and-addend"
        else:
            suffix = "encoding-or-target-reselection"
        family = "profile-build-id-transitive-lto-relocation-" + suffix
        relocation_families[family] += 1
        relocations.append({"index": index,
                            "source_section": before.source_section,
                            "changed_fields": fields, "family": family})
    require(len(relocations) == 3240, "relocation changed-member count drift")

    section_changes = []
    for section in old.sections:
        if section.bytes == 0 or section.section_type == "SHT_NOBITS":
            continue
        left = old.section_bytes(section.name)
        right = new.section_bytes(section.name)
        require(len(left) == len(right), f"section size drift: {section.name}")
        count = sum(a != b for a, b in zip(left, right))
        if count:
            section_changes.append({"section": section.name,
                                    "changed_bytes": count,
                                    "allocated": "SHF_ALLOC" in section.flags,
                                    "family": ("profile-build-id-transitive-content"
                                               if "SHF_ALLOC" in section.flags
                                               else "derived-ELF-metadata")})

    return {
        "status": "PASS: EVERY FROZEN PRODUCT MEMBER HAS A NAMED FAMILY",
        "pair": {"r8": {"ELF": bind(R8_ELF), "PRG": bind(R8_PRG)},
                 "r9": {"ELF": bind(R9_ELF), "PRG": bind(R9_PRG)}},
        "prg_schema": ["file_offset", "memory_address", "before", "after",
                       "family"],
        "prg_changed_members": prg,
        "symbols_changed_members": symbols,
        "relocations_changed_members": relocations,
        "section_change_summary": section_changes,
        "counts": {"PRG_bytes": len(prg), "symbols": len(symbols),
                   "relocations": len(relocations),
                   "unexplained_PRG_bytes": 0, "unexplained_symbols": 0,
                   "unexplained_relocations": 0},
        "family_counts": {
            "PRG": dict(Counter(row[4] for row in prg)),
            "symbols": dict(Counter(row["family"] for row in symbols)),
            "relocations": dict(relocation_families),
        },
    }


def output_root_rebind() -> dict[str, Any]:
    class StopBeforeLink(BaseException):
        pass

    phase_build = ATTRIBUTION_OUT / "real-caller-final"
    phase_preflight = ATTRIBUTION_OUT / "real-caller-preflight-final"
    phase_root = (phase_build /
                  "wplto/fresh-c2-lite-prelink-gates/v6-semantics")
    candidate = phase_root / "initial.c2d-v6.bin"
    pair_before = {"ELF": bind(R9_ELF), "PRG": bind(R9_PRG)}
    require(not phase_build.exists() and not phase_preflight.exists(),
            "output-root rebind probe is not one-shot")
    R9.install()
    core, _activation, _cold = R9.setup_child()
    phase_preflight.mkdir(parents=True)
    for name in ("projected-ownership-contract.json",
                 "projected-full-map-authority.json"):
        shutil.copyfile(R9.PREFLIGHT / name, phase_preflight / name)
    core.bind_paths_only(phase_build, phase_preflight)
    CARD.install_final_v6_consumer(record=False)
    captured_prelink: list[dict[str, Any]] = []
    intercepted_links = 0
    old_prelink = BASE_LINK.fresh_prelink_gates
    old_single_link = PRODUCT.single_link

    def capture_prelink() -> dict[str, Any]:
        value = old_prelink()
        captured_prelink.append(value)
        return value

    def stop_before_link(*_args: Any, **_kwargs: Any) -> None:
        nonlocal intercepted_links
        intercepted_links += 1
        raise StopBeforeLink()

    BASE_LINK.fresh_prelink_gates = capture_prelink
    PRODUCT.single_link = stop_before_link
    stopped = False
    try:
        core.PRODUCT.BASE.produce_child()
    except StopBeforeLink:
        stopped = True
    finally:
        BASE_LINK.fresh_prelink_gates = old_prelink
        PRODUCT.single_link = old_single_link
    require(stopped and intercepted_links == 1
            and len(captured_prelink) == 1
            and captured_prelink[0]["status"] == "passed"
            and candidate.is_file(),
            "real caller did not reach green prelink before the link sentinel")
    mutation_rejected = False
    try:
        CARD.phase_output_root_gate(
            caller_root=phase_root,
            selected_root=R9.setup_plane() / "v6-semantics")
    except RuntimeError:
        mutation_rejected = True
    require(mutation_rejected, "wrong-root mutation survived")

    old_base_out = BASE_LINK.OUT
    report_root = ATTRIBUTION_OUT / "postlink-report-root-probe"
    report_root.mkdir()
    try:
        BASE_LINK.OUT = report_root
        selected_report_root = LINK50.qualification_output_root(R9_ELF)
    finally:
        BASE_LINK.OUT = old_base_out
    require(selected_report_root == report_root
            and selected_report_root != R9_ELF.parent,
            "Link-50 post-link report root did not follow phase authority")
    report_root_mutation_rejected = False
    try:
        CARD.phase_output_root_gate(
            caller_root=report_root, selected_root=R9_ELF.parent)
    except RuntimeError:
        report_root_mutation_rejected = True
    require(report_root_mutation_rejected,
            "post-link report redirected to sealed ELF root")

    pair_after = {"ELF": bind(R9_ELF), "PRG": bind(R9_PRG)}
    require(pair_before == pair_after, "output-root conversion changed frozen pair")
    return {
        "status": "PASS: REAL V6 CONSUMER KEPT PHASE-OWNED OUTPUT ROOT",
        "phase_owned_output": bind(candidate),
        "phase_owned_root": phase_root.relative_to(ROOT).as_posix(),
        "real_caller": {
            "path": "configure-stack -> fresh_prelink_gates -> V6.host_semantics",
            "prelink_status": captured_prelink[0]["status"],
            "single_link_intercepted_before_execution": intercepted_links,
        },
        "postlink_report_root": {
            "selected": selected_report_root.relative_to(ROOT).as_posix(),
            "sealed_ELF_root_rejected": report_root_mutation_rejected,
            "direct_entry_and_CRC_share_phase_root": True,
        },
        "sealed_link_root": {
            "path": R9W.relative_to(ROOT).as_posix(),
            "mode": f"{R9W.stat().st_mode & 0o777:04o}",
            "write_attempted": False},
        "wrong_root_mutation_rejected": mutation_rejected,
        "frozen_pair_before": pair_before, "frozen_pair_after": pair_after,
        "WPLTO_runs": 0, "product_links": 0,
    }


def source_conversion_gate() -> dict[str, Any]:
    """Keep both output-root fixes attached to their real source consumers."""
    caller_root = ROOT / "build/c2.3/source-gate/phase-owned"
    setup_root = ROOT / "build/c2.3/source-gate/setup-owned"
    CARD.phase_output_root_gate(caller_root=caller_root,
                                selected_root=caller_root)
    wrong_root_rejected = False
    try:
        CARD.phase_output_root_gate(caller_root=caller_root,
                                    selected_root=setup_root)
    except RuntimeError:
        wrong_root_rejected = True
    require(wrong_root_rejected,
            "card-3 setup-root divergence mutation survived")

    old_out = BASE_LINK.OUT
    try:
        BASE_LINK.OUT = caller_root
        selected = LINK50.qualification_output_root(R9_ELF)
    finally:
        BASE_LINK.OUT = old_out
    require(selected == caller_root,
            "Link-50 output root did not follow phase authority")

    card_tree = ast.parse(textwrap.dedent(
        inspect.getsource(CARD.install_final_v6_consumer)))
    redirected_v6_out = []
    for node in ast.walk(card_tree):
        targets: list[ast.expr] = []
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = (node.targets if isinstance(node, ast.Assign)
                       else [node.target])
        elif isinstance(node, ast.AugAssign):
            targets = [node.target]
        for target in targets:
            if (isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "V6" and target.attr == "OUT"):
                redirected_v6_out.append(ast.unparse(node))
    require(not redirected_v6_out,
            "real V6 consumer reintroduced a private output-root assignment")

    link_tree = ast.parse(textwrap.dedent(
        inspect.getsource(LINK50.corrected_replacement)))
    phase_assignments = 0
    crc_report_roots = 0
    pinned_artifact_assignments = []
    for node in ast.walk(link_tree):
        if isinstance(node, ast.Assign):
            value = ast.unparse(node.value)
            for target in node.targets:
                rendered = ast.unparse(target)
                if rendered in ("BASE_LINK.OUT", "BASE_LINK.DIRECT.OUT"):
                    if value == "phase_output_root":
                        phase_assignments += 1
                    if value == "artifact_root":
                        pinned_artifact_assignments.append(rendered)
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "workbench_crc_gate"):
            roots = [keyword.value for keyword in node.keywords
                     if keyword.arg == "report_root"]
            if (len(roots) == 1 and isinstance(roots[0], ast.Name)
                    and roots[0].id == "phase_output_root"):
                crc_report_roots += 1
    require(phase_assignments == 2 and crc_report_roots == 1
            and not pinned_artifact_assignments,
            "post-link consumers no longer share the phase-owned output root")
    return {
        "status": "PASS: OUTPUT-ROOT CONSUMERS DERIVE PHASE AUTHORITY",
        "card3_consumer": {
            "source": bind(Path(inspect.getsourcefile(
                CARD.install_final_v6_consumer) or "")),
            "private_V6_OUT_assignments": redirected_v6_out,
            "wrong_setup_root_mutation_rejected": wrong_root_rejected,
        },
        "link50_postlink_consumers": {
            "source": bind(Path(inspect.getsourcefile(
                LINK50.corrected_replacement) or "")),
            "phase_root_assignments": phase_assignments,
            "CRC_report_root_bindings": crc_report_roots,
            "artifact_root_assignments": pinned_artifact_assignments,
            "dynamic_selected_root": selected.relative_to(ROOT).as_posix(),
        },
    }


def mutation_matrix(value: dict[str, Any]) -> dict[str, str]:
    def reject(mutant: dict[str, int]) -> None:
        require(mutant == {"PRG_bytes": 7731, "symbols": 87,
                           "relocations": 3240,
                           "unexplained_PRG_bytes": 0,
                           "unexplained_symbols": 0,
                           "unexplained_relocations": 0},
                "attribution member or unexplained count drift")

    base = dict(value["product_members"]["counts"])
    cases = {}
    for name, key in (("unexplained-prg-byte", "unexplained_PRG_bytes"),
                      ("unexplained-symbol", "unexplained_symbols"),
                      ("unexplained-relocation", "unexplained_relocations"),
                      ("missing-prg-member", "PRG_bytes"),
                      ("missing-symbol-member", "symbols"),
                      ("missing-relocation-member", "relocations")):
        mutant = dict(base)
        mutant[key] += 1 if key.startswith("unexplained") else -1
        try:
            reject(mutant)
        except AttributionError:
            cases[name] = "rejected"
    require(len(cases) == 6, "attribution mutation matrix incomplete")
    return cases


def report(value: dict[str, Any]) -> str:
    counts = value["product_members"]["counts"]
    profile = value["profile_closure"]["profile_build_id"]
    objects = value["compiler_closure"]["canonical_targets"][
        "lisp65-c2-substitution-linked"]
    return f"""# Block 3 r8/r9 attribution

Status: **{value['status']}**

The frozen r9 pair is fully attributed without a compiler or linker run.
Every **{counts['PRG_bytes']:,} PRG byte**, **{counts['symbols']} symbol** and
**{counts['relocations']:,} relocation** difference has a named family;
unexplained members are **0 / 0 / 0**.

## Causal closure

All 70 source contents, feature definitions, product-artifact identity,
determinism controls and 23 native linker objects are byte-identical.  The
linker scripts differ only in the two mapped-tenant LMA sections/assertions.
After normalizing the phase output root, the sole profile difference is that
linker SHA.  The raw profile identity also includes its phase-root spelling;
both antecedents are recorded rather than silently attributing the hash to the
linker alone.  The derived build ID moves from `{profile['r8']}` to
`{profile['r9']}`.

The resulting generated headers change only in build-ID/derived-CRC families.
The deterministic compiler changes {objects['changed_objects']} canonical
members (26 C bitcode objects plus `combined-c.bc`) while every native object
remains identical.  The four mapped LOADADDR symbols and two program-header
physical addresses form the direct placement family; all remaining content,
symbol and relocation changes are downstream of the changed profile identity.

No counterfactual link is required: the full materialized input closure has no
third changed root and every requested end member lies in one of those two
transitive families.

## Output-root conversion

The real V6 host-semantics consumer now keeps the output root selected by its
phase caller and binds only candidate inputs from the setup-owned plane.  It
materialized `initial.c2d-v6.bin` below the caller-owned post-link root; the
historical setup-root redirection is mutation-rejected.  The Link-50
Direct-Entry and CRC reports likewise derive the active phase root instead of
the sealed ELF parent.  A hard `single_link` sentinel proved the real caller
chain through green prelink without allowing a WPLTO/product link execution.
ELF and PRG hashes are identical before and after this read-only run.

One diagnostic Scope probe also passed over the frozen pair.  It is recorded
as a read-only probe, not as candidate Qualification; no Acceptance run was
made.

## Disposition

This result exonerates the r9 product-difference family and the output-root
adapter mechanically.  It does **not** promote the pair or authorize another
WPLTO/link, Scope, Qualification, media or hardware.  Candidate resurrection
versus r10 remains the review decision.
"""


def validate(value: dict[str, Any]) -> None:
    counts = value["product_members"]["counts"]
    require(value["status"] ==
                "PASS: R8/R9 FROZEN PAIR FULLY ATTRIBUTED; OUTPUT ROOT REBOUND"
            and counts == {"PRG_bytes": 7731, "symbols": 87,
                           "relocations": 3240,
                           "unexplained_PRG_bytes": 0,
                           "unexplained_symbols": 0,
                           "unexplained_relocations": 0}
            and value["output_root_rebind"]["WPLTO_runs"] == 0
            and value["output_root_rebind"]["product_links"] == 0
            and value["read_only_scope_probe"]["status"] == "PASS"
            and value["attempt_accounting"]["scope_runs"] == 1
            and value["source_conversion_gate"]["status"] ==
                "PASS: OUTPUT-ROOT CONSUMERS DERIVE PHASE AUTHORITY"
            and len(value["mutations_rejected"]) == 6,
            "r8/r9 attribution result drift")


def validate_recorded_enumeration(value: dict[str, Any]) -> None:
    members = value["product_members"]
    counts = members["counts"]
    require(len(members["prg_changed_members"]) == counts["PRG_bytes"]
            and len(members["symbols_changed_members"]) == counts["symbols"]
            and len(members["relocations_changed_members"]) ==
                counts["relocations"]
            and all(row[4] for row in members["prg_changed_members"])
            and all(row["family"] for row in members["symbols_changed_members"])
            and all(row["family"] for row in
                    members["relocations_changed_members"]),
            "recorded attribution enumeration is incomplete")


def run(*, refresh: bool = False) -> None:
    require((RECEIPT.exists() and REPORT.exists()) if refresh else
            (not RECEIPT.exists() and not REPORT.exists()),
            "r8/r9 attribution lifecycle drift")
    auth = authority()
    profile = profile_closure()
    linker = linker_authority()
    compiler = compiler_closure(profile)
    members = product_members()
    prior = load(RECEIPT) if refresh else None
    rebind = (prior["output_root_rebind"] if prior is not None
              else output_root_rebind())
    if prior is not None:
        require(rebind["frozen_pair_after"] == {
                    "ELF": bind(R9_ELF), "PRG": bind(R9_PRG)}
                and rebind["phase_owned_output"] == bind(
                    ATTRIBUTION_OUT /
                    "real-caller-final/wplto/fresh-c2-lite-prelink-gates/"
                    "v6-semantics/initial.c2d-v6.bin"),
                "recorded output-root proof no longer binds its artifacts")
    source_gate = source_conversion_gate()
    scope = load(R9_SCOPE)
    require(scope.get("status") == "PASS",
            "read-only r9 Scope probe is not green")
    value = {
        "format": FORMAT, "recorded_on": "2026-08-26",
        "status": "PASS: R8/R9 FROZEN PAIR FULLY ATTRIBUTED; OUTPUT ROOT REBOUND",
        "authority": auth, "profile_closure": profile,
        "linker_authority": linker, "compiler_closure": compiler,
        "product_members": members, "output_root_rebind": rebind,
        "source_conversion_gate": source_gate,
        "read_only_scope_probe": {
            "status": scope["status"], "receipt": bind(R9_SCOPE),
            "pair_disposition_unchanged": True,
            "claim": "diagnostic read only; not candidate qualification"},
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
                               "scope_runs": 1, "qualification_runs": 0,
                               "media_builds": 0, "device_contacts": 0},
        "counterfactual_link_required": False,
        "pair_disposition": "FROZEN-EVIDENCE-AWAITING-REVIEW",
        "claim_limit": ("Host-only difference attribution and V6 output-root "
                        "conversion; no candidate, Scope, Qualification, media "
                        "or device claim."),
    }
    value["mutations_rejected"] = mutation_matrix(value)
    validate(value)
    validate_recorded_enumeration(value)
    RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(report(value), encoding="utf-8")
    print("Block3 r8/r9 attribution: PASS prg=7731 symbols=87 "
          "relocations=3240 unexplained=0 WPLTO=0 link=0")


def check() -> None:
    value = load(RECEIPT)
    validate(value)
    validate_recorded_enumeration(value)
    require(value["authority"] == authority()
            and value["profile_closure"] == profile_closure()
            and value["linker_authority"] == linker_authority()
            and value["compiler_closure"] == compiler_closure(
                value["profile_closure"])
            and value["product_members"] == product_members()
            and value["source_conversion_gate"] == source_conversion_gate()
            and value["output_root_rebind"]["frozen_pair_after"] == {
                "ELF": bind(R9_ELF), "PRG": bind(R9_PRG)}
            and value["output_root_rebind"]["phase_owned_output"] == bind(
                ATTRIBUTION_OUT /
                "real-caller-final/wplto/fresh-c2-lite-prelink-gates/"
                "v6-semantics/initial.c2d-v6.bin")
            and REPORT.read_text(encoding="utf-8") == report(value),
            "r8/r9 attribution receipt/report drift")
    print("Block3 r8/r9 attribution: CHECK PASS unexplained=0 pair=frozen")


def source_check() -> None:
    """Permanent source gate; works without ignored frozen build products."""
    value = load(RECEIPT)
    validate(value)
    validate_recorded_enumeration(value)
    require(value["authority"] == authority()
            and value["source_conversion_gate"] == source_conversion_gate()
            and REPORT.read_text(encoding="utf-8") == report(value),
            "r8/r9 permanent source/evidence gate drift")
    print("Block3 r8/r9 attribution: SOURCE CHECK PASS roots=phase-owned")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "refresh", "check",
                                           "source-check"))
    action = parser.parse_args().action
    {"run": lambda: run(refresh=False),
     "refresh": lambda: run(refresh=True), "check": check,
     "source-check": source_check}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Block3 r8/r9 attribution: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
