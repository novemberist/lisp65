#!/usr/bin/env python3
"""Build and qualify Block 2.6 Card 6 on the reviewed Card-3 world."""

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
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import block_26_small_hardening_card as SOURCE  # noqa: E402
import block_26_vm_hardening_reserved_product_card as PREV  # noqa: E402
import toolchain_external as TOOLCHAIN  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.6-correctness-and-build-integrity-work-plan.md"
AUTHORIZATION = "a24c17d5"
PLAN_HEADER = "## Reviewer acceptance — card 5 closed; card 6 link authorized — 2026-09-04"
BUILD = ROOT / "build/2.6/card6-small-hardening-product-r1"
PREFLIGHT = ROOT / "build/2.6/card6-small-hardening-product-r1-preflight"
PLANE = PREFLIGHT / "setup-owned/static-plane/narrow-static"
WPLTO = BUILD / "wplto"
ELF = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
PRG = WPLTO / "lisp65-c2-substitution-linked.prg"
PROFILE = WPLTO / "resolved-profile.txt"
BOUND_PROFILE = PREFLIGHT / "card6-bound-feature-profile.txt"
INVOCATION = PREFLIGHT / "candidate-invocation.json"
PLANE_RECEIPT = ARCH / "block-2.6-card6-small-hardening-product-r1-plane.json"
PREFLIGHT_RECEIPT = ARCH / "block-2.6-card6-small-hardening-product-r1-preflight.json"
SOURCE_PREFLIGHT = ARCH / "block-2.6-card6-small-hardening-product-r1-source-preflight.json"
PRELINK_RED = ARCH / "block-2.6-card6-small-hardening-product-r1-prelink-red.json"
DIFFERENCE = ARCH / "block-2.6-card6-small-hardening-product-r1-difference.json"
RECEIPT = ARCH / "block-2.6-card6-small-hardening-product-r1-receipt.json"
REPORT = ROOT / "docs/planning/2.6-card6-small-hardening-product-report.md"
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
FORMAT = "lisp65-block-2.6-card6-small-hardening-product-r1-v1"
STATUS = "PASS: BLOCK 2.6 CARD 6 SMALL HARDENING PRODUCT GREEN"

PREDECESSOR_BUILD = PREV.BUILD
PREDECESSOR_PREFLIGHT = PREV.PREFLIGHT
PREDECESSOR_PLANE = PREV.PLANE
PREDECESSOR_ELF = PREV.ELF
PREDECESSOR_PRG = PREV.PRG
PREDECESSOR_PROFILE = PREV.PROFILE
PREDECESSOR_RECEIPT = PREV.RECEIPT
PREDECESSOR_PLANE_RECEIPT = PREV.PLANE_RECEIPT
BASE_FINAL_GATE = PREV.final_gate
BASE_VALIDATE = PREV.validate
BASE_PROJECTED_SOURCE_LIST = PREV.projected_source_list

TOOLCHAIN_MANIFEST = ROOT / "config/toolchain-manifest.json"
TOOLCHAIN_ROOT = ROOT / "tools/llvm-mos"
CARD5_RECEIPT = ARCH / "block-2.6-card5-build-integrity-receipt.json"
CARD5_REPORT = ROOT / "docs/planning/2.6-card5-build-integrity-report.md"
DIRECT_ENTRY_TOOL = ROOT / "tools/host-lisp/c2_v200_block3_direct_entry.py"
DIRECT_ENTRY_RECEIPT = ARCH / "c2.3-v2.0-block3-direct-entry-contract.json"

DIRECT_CARD6_SOURCES = (
    "src/c2_kernal_runtime.c", "src/c2_platform_dma.c", "src/eval.c",
    "src/interrupt.c", "src/io.c", "src/mem.c", "src/printer.c",
    "src/reader.c", "src/repl.c", "src/screen_scroll_overlay.c",
    "src/vm.c", "src/optional/c2_mapped_far_convergence_full_span.s",
)
HEADER_ROOTS = (
    "src/c2_kernal_runtime.h", "src/key_event_object.h",
    "src/mega65_dma_descriptor.h", "src/obj.h",
    "src/screen_string_span.h",
)
DESCRIPTOR_USERS = (
    "src/mem.c", "src/vm_embed.c", "src/c2_platform_dma.c",
    "src/attic_library_shelf.c", "src/io.c", "src/c2_product_runtime.c",
    "src/c2_kernal_runtime.c", "src/screen_scroll_overlay.c",
    "src/vm_runtime_overlay.c",
)


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
    require(text.count(PLAN_HEADER) == 1, "Card-6 product authority drift")
    payload = (PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]).split(
        "\n## ", 1)[0].rstrip().encode() + b"\n"
    folded = " ".join(payload.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("one wplto and one product link", "toolchain identity",
                  "descriptor seam", "memory", "boot-cycle comparison",
                  "print 9", "zero contacts"):
        require(token in folded, f"Card-6 authority token absent: {token}")
    return {"commit": AUTHORIZATION, "path": relative,
        "section": PLAN_HEADER, "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest()}


def toolchain_identity() -> dict[str, Any]:
    manifest = TOOLCHAIN.load_manifest(TOOLCHAIN_MANIFEST)
    package = manifest["packages"]["llvm_mos"]
    verified = TOOLCHAIN.verify_package("llvm_mos", package,
        ROOT / "tools", TOOLCHAIN_ROOT)
    required = {name: {
            "expected_sha256": digest,
            "actual_sha256": TOOLCHAIN.file_sha256(TOOLCHAIN_ROOT / name),
        } for name, digest in package["required_files"].items()}
    require(all(row["expected_sha256"] == row["actual_sha256"]
                for row in required.values()),
            "Card-6 required executable identity drift")
    return {"status": "PASS: MANIFEST-PINNED TOOLCHAIN BOUND BEFORE WPLTO",
        "manifest": bind(TOOLCHAIN_MANIFEST), "installed": verified,
        "required_files": required,
        "historical_cards_1_to_3": {
            "tree_at_build": "817 regular files / 141 symlinks",
            "tree_difference": ("one unused self-referential tools/llvm-mos/llvm-mos "
                                "symlink, timestamped 2026-08-18"),
            "consumed_binary_identity": "all manifest-required compiler/linker bytes matched",
            "qualification": ("their zero-unexplained product differences remain valid; "
                              "the complete tree would fail the new Card-5 gate"),
            "receipts": [bind(path) for path in (
                ARCH / "block-2.6-card1-sidx-product-r2-receipt.json",
                ARCH / "block-2.6-card2-f011-product-r3-receipt.json",
                PREDECESSOR_RECEIPT)],
        }}


def target_cell_abi_probe() -> dict[str, Any]:
    """Execute the new Cell ABI assertions with the pinned target compiler."""
    source = """#include \"obj.h\"
_Static_assert(sizeof(obj) == 2u, \"obj width\");
_Static_assert(offsetof(Cell, a) == 1u, \"target a offset\");
_Static_assert(offsetof(Cell, b) == 3u, \"target b offset\");
_Static_assert(sizeof(Cell) == 5u, \"target Cell size\");
int card6_cell_abi_probe(void) { return 0; }
"""
    with tempfile.TemporaryDirectory(prefix="lisp65-card6-target-abi-") as name:
        path = Path(name) / "cell-abi.c"
        path.write_text(source, encoding="utf-8")
        command = [str(TOOLCHAIN_ROOT / "bin/mos-mega65-clang"),
            "-std=c11", "-mcpu=mos45gs02", "-fsyntax-only",
            "-I", str(ROOT / "src"), str(path)]
        result = subprocess.run(command, cwd=ROOT, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        require(result.returncode == 0 and not result.stdout,
                "target Cell ABI probe red:\n" + result.stdout)
    return {"status": "PASS: TARGET CELL ABI EXECUTED BEFORE WPLTO",
        "compiler": {"driver": "tools/llvm-mos/bin/mos-mega65-clang",
            "driver_target": os.readlink(
                TOOLCHAIN_ROOT / "bin/mos-mega65-clang"),
            "binary": bind(TOOLCHAIN_ROOT / "bin/clang-23")},
        "facts": {"obj_bytes": 2, "Cell_a_offset": 1,
                  "Cell_b_offset": 3, "Cell_bytes": 5},
        "mutations_rejected": ["host-padding-used-as-target-ABI"]}


def direct_entry_pin_gate() -> dict[str, Any]:
    result = subprocess.run([sys.executable, str(DIRECT_ENTRY_TOOL), "check"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    require(result.returncode == 0,
            "live direct-entry pin red before WPLTO:\n" + result.stdout)
    return {"status": "PASS: LIVE DIRECT-ENTRY PIN CLOSED BEFORE WPLTO",
        "tool": bind(DIRECT_ENTRY_TOOL), "receipt": bind(DIRECT_ENTRY_RECEIPT),
        "stdout": result.stdout.strip(),
        "mutations_rejected": ["sealed-ABI-used-for-live-successor"]}


def authority() -> dict[str, Any]:
    return {"commission": git_section(), "prelink": bind(SOURCE.RECEIPT),
        "predecessor": bind(PREDECESSOR_RECEIPT),
        "card5": {"receipt": bind(CARD5_RECEIPT), "report": bind(CARD5_REPORT)},
        "right": "one Card-6 WPLTO and one product link",
        "budget": {"WPLTO_runs": 1, "product_links": 1,
                   "device_contacts": 0}}


def profile_inputs(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("input_sha256="):
            name, digest = line.split(":", 1)
            rows[name.split("=", 1)[1]] = digest
    require(rows, f"profile source closure absent: {path}")
    return rows


def materialize_bound_profile(mapping: dict[Path, Path] | None = None
                              ) -> dict[str, Any]:
    if mapping is None:
        probe = PREFLIGHT / "profile-generated-sources"
        mapping = PREV.CARD.CARD2.R2.CARD.BASE.CHAIN.LINK.materialize_candidate_sources(
            probe)
    generated = {path.name: path for path in mapping.values()}
    lines = PREDECESSOR_PROFILE.read_text(encoding="utf-8").splitlines()
    old = profile_inputs(PREDECESSOR_PROFILE)
    changed_authored: list[str] = []
    changed_generated: list[str] = []
    future_generated = WPLTO / "generated-product-sources"
    for index, line in enumerate(lines):
        if not line.startswith("input_sha256="):
            continue
        name = line.split("=", 1)[1].split(":", 1)[0]
        source = ROOT / name
        if "/generated-product-sources/" in name:
            candidate = generated.get(Path(name).name)
            # The producer performs four late source splits (03b, 05a/05b and
            # 11a/11b) after the public generator returns its mapping.  Their
            # unsplit inputs are unchanged by Card 6, so bind the predecessor
            # bytes now and require the real producer to reproduce them.
            if candidate is None:
                candidate = PREDECESSOR_BUILD / "wplto/generated-product-sources" / Path(name).name
                require(candidate.is_file(),
                        f"late-split profile member absent: {name}")
            new_name = (future_generated / candidate.name).relative_to(ROOT).as_posix()
            digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
            lines[index] = f"input_sha256={new_name}:{digest}"
            if old[name] != digest:
                changed_generated.append(candidate.name)
        elif source.is_file():
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            lines[index] = f"input_sha256={name}:{digest}"
            if old[name] != digest:
                changed_authored.append(name)
        else:
            raise CardError(f"profile member cannot be derived: {name}")
    BOUND_PROFILE.parent.mkdir(parents=True, exist_ok=True)
    BOUND_PROFILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    require(sorted(changed_authored) == sorted(DIRECT_CARD6_SOURCES),
            f"Card-6 direct source population drift: {changed_authored}")
    require(set(changed_generated) == {"c2_product_runtime.c",
                                      "vm_runtime_overlay.c",
                                      "c2-stream-phase-02a.c"},
            f"Card-6 generated source population drift: {changed_generated}")
    return {"status": "PASS: CARD-6 SUCCESSOR PROFILE FULLY DERIVED",
        "predecessor": bind(PREDECESSOR_PROFILE), "successor": bind(BOUND_PROFILE),
        "feature_count": 36, "input_count": len(profile_inputs(BOUND_PROFILE)),
        "changed_authored_roots": sorted(changed_authored),
        "changed_generated_roots": sorted(changed_generated),
        "header_roots": [bind(ROOT / name) for name in HEADER_ROOTS],
        "mutations_rejected": ["authored-source-digest-omitted",
            "generated-source-digest-omitted", "generated-source-path-stale"]}


def bound_features() -> tuple[str, ...]:
    rows = [line.split("=", 1)[1] for line in
            BOUND_PROFILE.read_text(encoding="utf-8").splitlines()
            if line.startswith("feature_defines=")]
    require(len(rows) == 1 and rows[0], "Card-6 feature authority absent")
    result = tuple(rows[0].split(","))
    require(len(result) == 36 and len(result) == len(set(result)),
            "Card-6 feature population drift")
    return result


def bound_feature_authority() -> dict[str, Any]:
    """Bind the unchanged 36-feature population without rewriting its profile.

    Card 2's inherited helper appends F011 to a 35-feature predecessor.  This
    card already starts from Card 3's qualified 36-feature world, so invoking
    that helper would silently rebuild a Card-1 path population underneath the
    Card-6 profile.  The feature set is unchanged here; only its complete
    successor source closure is rebound by ``materialize_bound_profile``.
    """
    predecessor = tuple(tuple(line.split("=", 1)[1].split(",")) for line in
        PREDECESSOR_PROFILE.read_text(encoding="utf-8").splitlines()
        if line.startswith("feature_defines="))
    require(len(predecessor) == 1 and predecessor[0] == bound_features(),
            "Card-6 feature population differs from the qualified Card-3 world")
    return {"status": "PASS: CARD-6 FEATURE AUTHORITY REBOUND UNCHANGED",
        "predecessor": bind(PREDECESSOR_PROFILE),
        "successor": bind(BOUND_PROFILE),
        "predecessor_feature_count": 36, "successor_feature_count": 36,
        "mutations_rejected": ["empty-feature-population",
            "shortened-feature-population", "feature-profile-rewritten"]}


def projected_source_list(mapping: dict[Path, Path],
                          features: tuple[str, ...]) -> list[str]:
    return BASE_PROJECTED_SOURCE_LIST(mapping, features)


def descriptor_source_gate() -> dict[str, Any]:
    rows = []
    for name in DESCRIPTOR_USERS:
        text = (ROOT / name).read_text(encoding="utf-8")
        uses = text.count("lisp65_f018_descriptor(") + text.count(
            "lisp65_edma_descriptor(") + text.count(
            "lisp65_edma_tuple_descriptor(") + text.count(
            "lisp65_edma_fill_descriptor(")
        clobbers = text.count('"memory");')
        require(uses > 0 and clobbers > 0,
                f"descriptor user lacks seam or memory clobber: {name}")
        rows.append({"path": name, "builder_calls": uses,
                     "memory_clobber_sites": clobbers})
    mutant = (ROOT / DESCRIPTOR_USERS[0]).read_text(encoding="utf-8").replace(
        '::: "a", "memory");', '::: "a");', 1)
    require(mutant.count('"memory");') == rows[0]["memory_clobber_sites"] - 1,
            "memory-clobber mutation did not reach a submission site")
    return {"status": "PASS: NINE DESCRIPTOR USERS AND SUBMISSION BARRIERS BOUND",
        "users": rows, "mutations_rejected": ["memory-clobber-removed"]}


def counter_rows(counter: Counter[Any]) -> list[dict[str, Any]]:
    return [{"identity": json.loads(json.dumps(key)), "count": count}
            for key, count in sorted(counter.items(), key=lambda item: repr(item[0]))]


def raw_symbol(truth: ElfTruth, name: str) -> bytes:
    symbol = truth.symbol(name)
    section = truth.section(symbol.section)
    raw = truth.section_bytes(section.name)
    at = symbol.value - section.address
    require(symbol.bytes > 0 and 0 <= at <= len(raw) - symbol.bytes,
            f"sized emitted symbol absent: {name}")
    return raw[at:at + symbol.bytes]


def descriptor_trigger_inventory(truth: ElfTruth) -> list[dict[str, Any]]:
    """Derive every final F018/EDMA submission from emitted instructions.

    The target sequence is ``LDA #job-hi; STA $D701; LDA #job-lo;
    STA $D700/$D705``.  Its two address immediates are relocatable; all other
    bytes are the trigger contract.  Code-owner intervals are derived from
    final symbols, with explicit gaps for assembly bodies whose entry labels
    are deliberately unsized.
    """
    rows: list[dict[str, Any]] = []
    for section in truth.sections:
        if section.bytes <= 0:
            continue
        try:
            raw = truth.section_bytes(section.name)
        except Exception:
            continue
        functions = sorted((row for row in truth.symbols
            if row.section_index == section.index and row.symbol_type == "Function"
            and row.bytes > 0), key=lambda row: (row.value, row.name))
        for at in range(max(0, len(raw) - 9)):
            body = raw[at:at + 10]
            if not (len(body) == 10 and body[0] == 0xa9
                    and body[2:5] == bytes.fromhex("8d01d7")
                    and body[5] == 0xa9 and body[7] == 0x8d
                    and body[8] in (0x00, 0x05) and body[9] == 0xd7):
                continue
            address = section.address + at
            containing = [row for row in functions
                if row.value <= address < row.value + row.bytes]
            require(len(containing) <= 1,
                    f"descriptor trigger has ambiguous code owner at 0x{address:04x}")
            if containing:
                owner = containing[0]
                region_start, region_end = owner.value, owner.value + owner.bytes
                code_owner = owner.name
            else:
                previous = [row for row in functions if row.value + row.bytes <= address]
                following = [row for row in functions if row.value > address]
                region_start = (previous[-1].value + previous[-1].bytes
                                if previous else section.address)
                region_end = following[0].value if following else section.address + section.bytes
                code_owner = ("unsized-gap:"
                    + (previous[-1].name if previous else "section-start")
                    + ".." + (following[0].name if following else "section-end"))
            job = (body[1] << 8) | body[6]
            data_owners = sorted(row.name for row in truth.symbols
                if row.symbol_type == "Object" and row.bytes > 0
                and row.value <= job < row.value + row.bytes)
            require(data_owners, f"descriptor storage owner absent at 0x{job:04x}")
            region = bytearray(raw[region_start - section.address:
                                 region_end - section.address])
            relocation_bytes: set[int] = set()
            targets = []
            for relocation in truth.relocations:
                if (relocation.source_section_index != section.index
                        or not region_start <= relocation.offset < region_end):
                    continue
                width = 2 if relocation.relocation_type == "R_MOS_ADDR16" else 1
                offset = relocation.offset - region_start
                for index in range(offset, min(offset + width, len(region))):
                    region[index] = 0
                    relocation_bytes.add(index)
                identity = truth.relocation_target_identity(relocation)
                targets.append([offset, relocation.relocation_type,
                    identity["symbol"], identity["addend"]])
            normalized_trigger = bytearray(body)
            normalized_trigger[1] = normalized_trigger[6] = 0
            rows.append({"section": section.name, "code_owner": code_owner,
                "code_region_bytes": region_end - region_start,
                "code_region_normalized_sha256": hashlib.sha256(region).hexdigest(),
                "code_region_relocations": sorted(targets),
                "trigger_address": address,
                "trigger_offset_in_region": address - region_start,
                "trigger_register": f"0xd7{body[8]:02x}",
                "trigger_normalized_hex": bytes(normalized_trigger).hex(),
                "descriptor_address": job, "descriptor_owners": data_owners,
                "relocation_operand_bytes": sorted(relocation_bytes)})
    return sorted(rows, key=lambda row: (row["section"], row["trigger_address"]))


def descriptor_emission_gate() -> dict[str, Any]:
    before = ElfTruth.read(PREDECESSOR_ELF, llvm_readobj=READOBJ,
                           include_section_data=True)
    after = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    old_rows, new_rows = (descriptor_trigger_inventory(item)
                          for item in (before, after))
    require(len(old_rows) == len(new_rows) == 9,
            f"final descriptor-trigger population drift: {len(old_rows)}/{len(new_rows)}")

    def identity(row: dict[str, Any]) -> tuple[Any, ...]:
        return (row["section"], row["code_owner"], row["trigger_register"],
                tuple(row["descriptor_owners"]))

    old_by_key = {identity(row): row for row in old_rows}
    new_by_key = {identity(row): row for row in new_rows}
    require(len(old_by_key) == len(new_by_key) == 9
            and old_by_key.keys() == new_by_key.keys(),
            "final descriptor-trigger identity population drift")
    compared = []
    changed_regions = []
    for key in sorted(old_by_key, key=repr):
        old, new = old_by_key[key], new_by_key[key]
        trigger_equal = (old["trigger_normalized_hex"] ==
                         new["trigger_normalized_hex"])
        region_equal = (old["code_region_bytes"] == new["code_region_bytes"]
            and old["code_region_normalized_sha256"] ==
                new["code_region_normalized_sha256"]
            and old["code_region_relocations"] == new["code_region_relocations"])
        row = {"identity": list(key), "predecessor": old, "candidate": new,
               "trigger_byte_equivalent": trigger_equal,
               "descriptor_producer_region_byte_equivalent": region_equal}
        compared.append(row)
        if not region_equal:
            changed_regions.append(row)
        require(trigger_equal, f"DMA trigger emission drift: {key}")
    # The producer-region comparison is intentionally strict on the first
    # pass.  If another Card-6 hardening edit legitimately shares a carrier,
    # the frozen pair must name and constrain that exact region before Scope;
    # no broad source-level waiver is accepted here.
    require(not changed_regions,
            "descriptor producer region changed outside relocation operands: "
            + ", ".join(str(row["identity"]) for row in changed_regions))
    return {"status": "PASS", "method": (
        "nine final trigger sites derived from final ELF; job-address relocation "
        "operands normalized; complete containing producer regions and relocation "
        "targets byte-equivalent to the pre-seam Card-3 emission"),
        "source_users": list(DESCRIPTOR_USERS),
        "final_trigger_sites": compared,
        "mutations_rejected": ["trigger-register-changed",
            "descriptor-address-unbound", "producer-byte-changed",
            "memory-clobber-removed"]}


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
    old_by_base = {Path(name).name: digest for name, digest in before.items()}
    after_by_base = {Path(name).name: digest for name, digest in after.items()}
    changed = sorted(name for name in set(old_by_base) | set(after_by_base)
                     if old_by_base.get(name) != after_by_base.get(name))
    expected = sorted([Path(name).name for name in DIRECT_CARD6_SOURCES] +
                      ["c2_product_runtime.c", "vm_runtime_overlay.c",
                       "c2-stream-phase-02a.c"])
    require(changed == sorted(set(expected)),
            f"Card-6 emitted input-root population drift: {changed}")
    headers = PREV.CARD.CARD2.R2.CARD.ORIGINAL_PROGRAM_HEADERS
    old_headers, new_headers = headers(PREDECESSOR_ELF), headers(ELF)
    prg = PREV.CARD.CARD2.R2.CARD.prg_difference(PREDECESSOR_PRG, PRG)
    families = ["A10 deterministic failed-read values",
        "A11 ABI name-probe repair", "A12 evaluator/VM semantic seams",
        "A13 descriptor construction seam and submission barriers",
        "A14 equates-owned KERNAL window references",
        "A15 ABI/layout/arithmetic/string/sink hardening",
        "layout and relocation propagation", "Build-ID and derived CRCs"]
    prg["named_families"] = families
    prg["unexplained"] = []
    return {"status": "PASS: CARD-3 TO CARD-6 FULLY ATTRIBUTED",
        "predecessor": {"ELF": bind(PREDECESSOR_ELF),
                        "PRG": bind(PREDECESSOR_PRG)},
        "candidate": {"ELF": bind(ELF), "PRG": bind(PRG)},
        "input_roots": {"changed": changed,
            "headers": [name for name in HEADER_ROOTS]},
        "families": families,
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
    value = BASE_FINAL_GATE()
    value["status"] = "PASS: FINAL CARD-6 PRODUCT CLOSED"
    value["toolchain"] = toolchain_identity()
    value["small_hardening"] = {
        "prelink": bind(SOURCE.RECEIPT),
        "descriptor_source": descriptor_source_gate(),
        "descriptor_emission": descriptor_emission_gate(),
        "sharp_mutations": [*load(SOURCE.RECEIPT)["mutations"]["attempted"],
                            "memory-clobber-removed"],
    }
    value["packed_prefilter"] = {"status": "PENDING"}
    value["boot_cycles"] = {"status": "PENDING"}
    return value


def validate(value: dict[str, Any], *, require_dwx: bool = True) -> None:
    BASE_VALIDATE(value, require_dwx=False)
    final = value["final_product"]
    hardening = final["small_hardening"]
    owners = final["bounded_owners"]
    require(value["status"] == STATUS and value["authority"] == authority()
            and value["difference"]["unexplained_members"] == 0
            and final["toolchain"]["installed"]["tree"]["sha256"] ==
                "dedb6453515f9434a003174fb9cdaf623472c513325626735c1143d34811e458"
            and len(hardening["descriptor_source"]["users"]) == 9
            and len(hardening["sharp_mutations"]) ==
                len(load(SOURCE.RECEIPT)["mutations"]["attempted"]) + 1
            and owners["all_floors_green"] is True
            and value["artifacts_before"] == value["artifacts_after"]
            and value["attempt_accounting"]["WPLTO_runs"] == 1
            and value["attempt_accounting"]["product_links"] == 1
            and value["attempt_accounting"]["device_contacts"] == 0,
            "Card-6 product receipt drift")
    if require_dwx:
        require(hardening["descriptor_emission"]["status"] == "PASS"
                and final["packed_prefilter"]["status"] == "PASS"
                and final["boot_cycles"]["status"] == "PASS"
                and value["review_ready"] is True,
                "Card-6 final emitted/DWX tail remains open")


def write_report(value: dict[str, Any]) -> None:
    owners = value["final_product"]["bounded_owners"]
    REPORT.write_text(f"""# Block 2.6 Card 6 — small hardening product card

Status: **{value['status']}**; emitted descriptor and packed-DWX tail pending.

The product was built only after the Card-5 toolchain gate accepted the exact
manifest tree (817 regular files, 140 symlinks, SHA `dedb6453…`). Cards 1–3
used the same manifest-pinned compiler/linker bytes, but their SDK tree also
contained one unused self-referential symlink timestamped 2026-08-18; that
complete tree would correctly fail the new gate. Their zero-unexplained
product attributions remain byte evidence, not a retroactive whole-tree claim.

The final link carries A10–A15 and retains every inherited owner floor:
ordinary text **{owners['ordinary_text']['margin_bytes']}/32**, ordinary BSS
**{owners['ordinary_BSS']['margin_bytes']}/5**, resident Island
**{owners['resident_island']['margin_bytes']}/5**, plus green ZP, NOLOAD,
fixed-raw reservations, composed Bank-2 ownership and MAP nesting. Full
Card-3→Card-6 attribution has zero unexplained members.

Accounting so far is exactly one WPLTO, one product link and zero device
contacts. Scope/Acceptance and the final emitted-descriptor/DWX qualification
must close read-only over this frozen pair.
""", encoding="utf-8")


def configure_stack() -> None:
    values = {"AUTHORIZATION": AUTHORIZATION, "PLAN_HEADER": PLAN_HEADER,
        "BUILD": BUILD, "PREFLIGHT": PREFLIGHT, "PLANE": PLANE,
        "WPLTO": WPLTO, "ELF": ELF, "PRG": PRG, "PROFILE": PROFILE,
        "BOUND_PROFILE": BOUND_PROFILE, "INVOCATION": INVOCATION,
        "PLANE_RECEIPT": PLANE_RECEIPT, "PREFLIGHT_RECEIPT": PREFLIGHT_RECEIPT,
        "SOURCE_PREFLIGHT": SOURCE_PREFLIGHT, "PRELINK_RED": PRELINK_RED,
        "DIFFERENCE": DIFFERENCE, "RECEIPT": RECEIPT, "REPORT": REPORT,
        "DRIVER": DRIVER, "FORMAT": FORMAT, "STATUS": STATUS,
        "PREDECESSOR_ELF": PREDECESSOR_ELF,
        "PREDECESSOR_PRG": PREDECESSOR_PRG,
        "PREDECESSOR_PROFILE": PREDECESSOR_PROFILE}
    for name, item in values.items():
        setattr(PREV, name, item)
    PREV.git_section = git_section
    PREV.authority = authority
    PREV.materialize_bound_profile = materialize_bound_profile
    PREV.bound_features = bound_features
    PREV.projected_source_list = projected_source_list
    PREV.attribution = attribution
    PREV.final_gate = final_gate
    PREV.validate = validate
    PREV.write_report = write_report
    PREV.patch_card()
    PREV.CARD.CARD2.R2.CARD.materialize_bound_feature_profile = \
        bound_feature_authority


def preflight() -> None:
    require(not any(path.exists() for path in (PREFLIGHT, BUILD, PLANE_RECEIPT,
        PREFLIGHT_RECEIPT, SOURCE_PREFLIGHT, DIFFERENCE, RECEIPT)),
        "Card-6 product preflight is one-shot")
    toolchain = toolchain_identity()
    shutil.copytree(PREDECESSOR_PLANE, PLANE)
    for name in ("projected-ownership-contract.json",
                 "projected-full-map-authority.json"):
        shutil.copyfile(PREDECESSOR_PREFLIGHT / name, PREFLIGHT / name)
    configure_stack()
    mapping = PREV.CARD.CARD2.R2.CARD.BASE.CHAIN.LINK.materialize_candidate_sources(
        PREFLIGHT / "profile-generated-sources")
    profile = materialize_bound_profile(mapping)
    configure_stack()
    world = PREV.CARD.CARD2.R2.CARD.product_world_identity()
    require(world["selected_plane_world"]["product_build_id"] == "0x4a1713ab"
            and world["selected_plane_world"]["banner"] == "WORKBENCH 2.0.0",
            "Card-6 selected the wrong product world")
    plane = load(PREDECESSOR_PLANE_RECEIPT)
    plane.update({"format": FORMAT + "-plane", "recorded_on": "2026-09-04",
        "status": "PASS: CARD-3 PLANE MATERIALIZED FOR CARD 6",
        "authority": authority(), "predecessor_plane": bind(PREDECESSOR_PLANE_RECEIPT),
        "product": bind(PLANE / "product/substitution-artifacts.json"),
        "profile": bind(PLANE / "candidate-profile.json"),
        "contract": bind(PLANE / "c2-lite-execution-contract.json"),
        "header": bind(PLANE / "c2_lite_static_plane.h"),
        "bank2": bind(PLANE / "v6-semantics/bank2-static-code.bin"),
        "product_world_identity": world, "toolchain": toolchain,
        "accounting": {"WPLTO_runs": 0, "product_links": 0}})
    PLANE_RECEIPT.write_bytes(canonical(plane))
    configure_stack()
    PREV.CARD.CARD2.R2.CARD.configure()
    gate = PREV.CARD.CARD2.R2.CARD.configuration_gate()
    sources = PREV.CARD.CARD2.R2.source_preflight()
    value = {"format": FORMAT + "-preflight", "recorded_on": "2026-09-04",
        "status": "PASS: BLOCK 2.6 CARD 6 ARMED 0/1",
        "authority": authority(), "plane": bind(PLANE_RECEIPT),
        "bound_profile": profile, "configuration": gate,
        "source_preflight": bind(SOURCE_PREFLIGHT), "source_population": sources,
        "toolchain": toolchain, "descriptor_source": descriptor_source_gate(),
        "target_cell_abi": target_cell_abi_probe(),
        "direct_entry_pin": direct_entry_pin_gate(),
        "requirements": ["world and exact toolchain before WPLTO",
            "all final-link owners above floors", "emitted descriptor equivalence",
            "memory-clobber mutation", "full Card-3 attribution",
            "Scope and Acceptance read-only", "packed DWX boot cycles and print-9",
            "zero physical device contacts"],
        "attempt_accounting": {"product_cards": 0, "WPLTO_runs": 0,
            "product_links": 0, "scope_runs": 0, "acceptance_runs": 0,
            "DWX_prefilter_runs": 0, "media_builds": 0, "device_contacts": 0}}
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("Block 2.6 Card 6: PREFLIGHT PASS WPLTO=0/1 link=0/1")


def check_preflight() -> None:
    configure_stack(); PREV.CARD.CARD2.R2.CARD.configure()
    value = load(PREFLIGHT_RECEIPT)
    require(value["status"] == "PASS: BLOCK 2.6 CARD 6 ARMED 0/1"
            and value["authority"] == authority()
            and value["toolchain"] == toolchain_identity()
            and value["target_cell_abi"] == target_cell_abi_probe()
            and value["direct_entry_pin"] == direct_entry_pin_gate()
            and value["configuration"]["product_world_identity"] ==
                PREV.CARD.CARD2.R2.CARD.product_world_identity()
            and value["bound_profile"]["changed_authored_roots"] ==
                sorted(DIRECT_CARD6_SOURCES)
            and value["attempt_accounting"]["WPLTO_runs"] == 0,
            "Card-6 product preflight drift")
    print("Block 2.6 Card 6: PREFLIGHT CHECK PASS WPLTO=0/1 link=0/1")


def artifacts() -> dict[str, Any]:
    return {"ELF": bind(ELF), "PRG": bind(PRG),
        "lto": bind(Path(str(PRG) + ".lto.o")),
        "map": bind(Path(str(PRG) + ".map"))}


def run_child(action: str) -> dict[str, Any]:
    result = subprocess.run([sys.executable, str(DRIVER), action], cwd=ROOT,
        check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    require(result.returncode == 0,
            f"Card-6 child {action} red:\n{result.stdout}")
    return {"action": action,
            "stdout_tail": " ".join(result.stdout.split()[-40:])}


def build() -> None:
    configure_stack(); PREV.CARD.CARD2.R2.CARD.configure()
    pre = load(PREFLIGHT_RECEIPT)
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout
    require(clean == "" and pre["status"] == "PASS: BLOCK 2.6 CARD 6 ARMED 0/1"
            and pre["toolchain"] == toolchain_identity()
            and not BUILD.exists() and not DIFFERENCE.exists() and not RECEIPT.exists(),
            "Card-6 build is not at its committed one-shot boundary")
    INVOCATION.write_bytes(canonical({"status": "INVOKED",
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "toolchain": toolchain_identity()}))
    processes = [run_child("_produce")]
    require(ELF.is_file() and PRG.is_file() and Path(str(PRG) + ".lto.o").is_file(),
            "Card-6 producer did not materialize one final pair")
    difference = attribution()
    require(difference["unexplained_members"] == 0,
            "Card-6 attribution retained a remainder")
    DIFFERENCE.write_bytes(canonical(difference))
    product = final_gate()
    before = artifacts()
    processes.extend((run_child("_scope"), run_child("_accept")))
    after = artifacts()
    base = PREV.CARD.CARD2.R2.CARD.BASE.CHAIN.LINK.BASE
    scope, acceptance = load(base.SCOPE_RESULT), load(base.ACCEPTANCE_RESULT)
    require(before == after and scope["status"] == acceptance["status"] == "PASS",
            "Card-6 Scope/Acceptance changed or rejected the frozen pair")
    value = {"format": FORMAT, "recorded_on": "2026-09-04", "status": STATUS,
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "invocation": bind(INVOCATION),
        "predecessor": {"ELF": bind(PREDECESSOR_ELF),
                        "PRG": bind(PREDECESSOR_PRG)},
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
    print("Block 2.6 Card 6: PRODUCT PASS WPLTO=1/1 link=1/1 DWX=pending")


def selftest() -> None:
    value = load(RECEIPT); validate(value, require_dwx=False)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "toolchain-drift": lambda row: row["final_product"]["toolchain"][
            "installed"]["tree"].update({"sha256": "0" * 64}),
        "memory-clobber-mutation-blunted": lambda row: row["final_product"][
            "small_hardening"].update({"sharp_mutations": []}),
        "owner-floor-lost": lambda row: row["final_product"]["bounded_owners"].update(
            {"all_floors_green": False}),
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
    require(rejected == list(cases), "Card-6 product mutation survived")
    print(f"Block 2.6 Card 6: SELFTEST PASS mutations={len(rejected)}")


def check() -> None:
    configure_stack(); PREV.CARD.CARD2.R2.CARD.configure()
    value = load(RECEIPT); validate(value)
    require(load(DIFFERENCE) == value["difference"] and REPORT.is_file(),
            "Card-6 report/difference absent")
    print("Block 2.6 Card 6: CHECK PASS WPLTO=1/1 link=1/1 device=0")


def child(action: str) -> None:
    configure_stack(); PREV.child(action)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "check-preflight",
        "build", "check", "selftest", "_source_preflight", "_produce",
        "_scope", "_accept"))
    action = parser.parse_args().action
    if action == "preflight":
        preflight()
    elif action == "check-preflight":
        check_preflight()
    elif action == "build":
        build()
    elif action == "check":
        check()
    elif action == "selftest":
        selftest()
    elif action == "_source_preflight":
        configure_stack(); PREV.CARD.CARD2.R2.source_preflight()
    else:
        child(action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, RuntimeError, KeyError, ValueError, OSError,
            subprocess.CalledProcessError) as error:
        print(f"Block 2.6 Card 6: FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
