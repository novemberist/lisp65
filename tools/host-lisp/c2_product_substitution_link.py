#!/usr/bin/env python3
"""Build the first real C2 product-substitution link, stopping on first red."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys

from c2_product_profile_parity import (
    canonical_v2_product_defines,
    mutation_selftest as v2_profile_mutation_selftest,
    profile_report as v2_profile_report,
    require_exact_v2_profile,
)
import c2_crc_codegen_gate as CRC_CODEGEN
import c2_crc_asm_leaf_gate as CRC_ASM_LEAF
import c2_asm_leaf_abi_gate as ASM_LEAF_ABI
import c2_fixed_block_leaf_gate as FIXED_BLOCK_LEAF
import f011_mount_window as F011_WINDOW
from elf_truth import ElfTruth, ElfTruthError


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "build/c2.2/substitution/product-link"
PRODUCT_ARTIFACTS_MANIFEST = (
    ROOT / "build/c2.2/substitution/substitution-artifacts.json")
INITIAL_C2D = ROOT / "build/c2.2/substitution/initial.c2d-v3.bin"
PRODUCT_SHELF = ROOT / "build/c2.2/substitution/product-shelf-v4-direct.bin"
TOOLCHAIN = ROOT / "tools/llvm-mos/bin"
PROFILE = "c2-product-substitution-v1"
RUNTIME_VMA = "0xc356"
KERNAL_WINDOW_STAGE = 0x087FE000
KERNAL_WINDOW_BASE = 0xE000
KERNAL_WINDOW_BYTES = 0x2000
RUNTIME_LOAD_BASE = 0x010000
RUNTIME_LOAD_BYTES = 0x020000
KERNAL_WINDOW_LOAD_BASE = 0x040000
HANDOFF_BASE = 0xB4A3
HANDOFF_BYTES = 0x121
HOST_FACADE_BASE = 0xB5C4
HOST_FACADE_STRIDE = 3
FIXED_ZP_BASE = 0x89
FIXED_ZP_BYTES = 7
FIXED_BANK0_BASE = 0xC080
FIXED_BANK0_BYTES = 408
FIXED_BANK0_CODE_BASE = 0xC218
FIXED_BANK0_CODE_BYTES = 66
FIXED_BANK0_HEADROOM_BYTES = 273
FIXED_BANK0_HOT_BSS_BASE = FIXED_BANK0_CODE_BASE + FIXED_BANK0_CODE_BYTES
FIXED_BANK0_HOT_BSS_BYTES = 240
FIXED_BANK0_NOINIT_BYTES = 6
SESSION_EMITTER_STATE_BYTES = 346
SESSION_EMITTER_STATE_BASE: int | None = None
LINK60_FINAL_GEOMETRY = False
E000_REOPENING = False
BSS_TRIAGE = False
FULL_MAP_OWNERSHIP = False
LOW_RESIDENT_LMA_RESET = False
FULL_MAP_OWNERSHIP_CONTRACT = (
    ROOT / "config/c2-full-map-ownership-contract.json")
APPEND_PLAN_FACADE = False
INPUT_CAPTURE_BUILD_CONFIGURATION = {
    "name": "v160-input-capture",
    "feature": "LISP65_V160_INPUT_CAPTURE",
    "source": ROOT / "src/optional/c2_kernal_input_capture.s",
    "base_source": ROOT / "src/c2_kernal_irq_base.s",
    "allocated": (
        ".lisp65_c2_kernal_window.input_capture_main",
        ".lisp65_c2_kernal_window.input_capture_helper",
    ),
}
INPUT_CAPTURE_FEATURE = str(INPUT_CAPTURE_BUILD_CONFIGURATION["feature"])
INPUT_CAPTURE_ENABLED = False
INPUT_HYBRID_BUILD_CONFIGURATION = {
    "name": "v160-input-hybrid-consumer",
    "feature": "LISP65_V160_INPUT_HYBRID",
    "source": ROOT / "src/optional/c2_kernal_input_consumer.s",
    "allocated": (
        ".lisp65_c2_kernal_window.input_consumer",
    ),
}
INPUT_HYBRID_FEATURE = str(INPUT_HYBRID_BUILD_CONFIGURATION["feature"])
INPUT_HYBRID_ENABLED = False
INPUT_HYBRID_SOURCE = Path(INPUT_HYBRID_BUILD_CONFIGURATION["source"])
INPUT_CAPTURE_SOURCE = Path(INPUT_CAPTURE_BUILD_CONFIGURATION["source"])
INPUT_CAPTURE_BASE_SOURCE = Path(
    INPUT_CAPTURE_BUILD_CONFIGURATION["base_source"])
REFILL_WITNESS_BUILD_CONFIGURATION = {
    "name": "v160-refill-boundary-witness",
    "feature": "LISP65_C2_REFILL_BOUNDARY_WITNESS",
    "source": ROOT / "src/optional/c2_refill_boundary_witness.s",
    "allocated": (".lisp65_c2_mapped_diagnostic",),
    "cpu_start": 0x7E8D,
    "physical_start": 0x0002BE8D,
    "capacity_bytes": 371,
}
REFILL_WITNESS_FEATURE = str(REFILL_WITNESS_BUILD_CONFIGURATION["feature"])
REFILL_WITNESS_SOURCE = Path(REFILL_WITNESS_BUILD_CONFIGURATION["source"])
REFILL_WITNESS_ENABLED = False
PRODUCT_COLD_BUILD_CONFIGURATION = {
    "name": "v160-product-cold-disk-chain",
    "feature": "LISP65_C2_PRODUCT_COLD_DISK_CHAIN",
    "source": ROOT / "src/optional/c2_product_cold_disk_chain.s",
    "allocated": (".lisp65_c2_mapped_product_cold",),
    "cpu_start": 0x7E8D,
    "physical_start": 0x0002BE8D,
    "capacity_bytes": 371,
}
PRODUCT_COLD_FEATURE = str(PRODUCT_COLD_BUILD_CONFIGURATION["feature"])
PRODUCT_COLD_SOURCE = Path(PRODUCT_COLD_BUILD_CONFIGURATION["source"])
PRODUCT_COLD_ENABLED = False
KERNAL_EQUATES_INCLUDE = ROOT / "src/c2_kernal_window_equates.inc"
E000_REOPEN_DEBIT_CAP = 450
E000_FINAL_FLOOR_BYTES = 63
HOST_FACADE_EXTENSION_BASE = HOST_FACADE_BASE + 13 * HOST_FACADE_STRIDE
HOST_FACADE_EXTENSION_SYMBOLS: tuple[str, ...] = ()
PROFILE_RODATA_SECTION = ".lisp65_c2_kernal_window.profile_rodata"
PROFILE_RODATA_INPUT_SECTIONS = {
    ".rodata.eval_v2_workbench_service": 32,
    ".rodata.vm_callprim": 164,
    ".rodata.vm_native_call": 146,
}
PROFILE_RODATA_BYTES = sum(PROFILE_RODATA_INPUT_SECTIONS.values())
REQUIRE_RESOLVER_PROFILE_CONFIGURED = False
PROFILE_RODATA_BASE = 0xFD12
SEALED_V2_PROFILE_PARITY_IDENTITY: str | None = None
SEALED_C2_ARTIFACTS_IDENTITY: str | None = None
C2_LITE_HYBRID_E000_FLOOR_BYTES = 54
C2_LITE_HYBRID_PROFILE_RODATA_BASE = 0xFD2C
# Current post-promotion product geometry.  Historical Link-60/66 replay
# drivers retain their own $B972 authority; new product-shaped WPLTO consumes
# this one current pin.
LINK60_VERIFIER_BINDING_BASE = 0xB98A
VERIFIER_BINDING_SECTION = ".lisp65_runtime_overlay_verifier_bindings"
VERIFIER_BINDING_BYTES = 32


def configure_full_map_ownership() -> None:
    """Select the v1.8 contract-owned ordinary CRT section chain.

    llvm-mos' platform script includes ``c.ld`` by search path.  The selected
    full-map row therefore shadows that include with one generated owner for
    rodata/data/BSS/noinit instead of trying to move inherited outputs with a
    later INSERT command.  This selector is intentionally one-way for a
    product-shaped process.
    """
    global FULL_MAP_OWNERSHIP
    FULL_MAP_OWNERSHIP = True


LOW_RESIDENT_LMA_SECTIONS = (
    ".lisp65_c2_kernal_handoff",
    ".lisp65_c2_host_facade",
    ".lisp65_c2_kernal_io_reveal",
    ".lisp65_c2_kernal_map_switch",
)


def configure_low_resident_lma_reset() -> None:
    """Reset the post-far-service LMA chain at existing resident outputs.

    The mapped far service deliberately has a Bank-2 LMA.  These four later
    ``INSERT AFTER .text`` outputs are ordinary boot-critical PRG material;
    without an explicit reset lld inherits the mapped service's LMA/VMA
    delta.  This selector is one-way and product-card-local so historical
    linker worlds remain byte-identical.
    """
    global LOW_RESIDENT_LMA_RESET
    if not FULL_MAP_OWNERSHIP:
        raise RuntimeError(
            "low-resident LMA reset requires full-map ownership")
    LOW_RESIDENT_LMA_RESET = True


def apply_low_resident_lma_reset(layout: str) -> str:
    """Give exactly the four resident outputs an explicit LMA equal to VMA."""
    result = layout
    for name in LOW_RESIDENT_LMA_SECTIONS:
        pattern = re.compile(
            rf"(?m)^(\s*{re.escape(name)}\s+)(0x[0-9a-f]+)\s+:\s+\{{$")
        matches = list(pattern.finditer(result))
        if len(matches) != 1:
            raise RuntimeError(
                f"low-resident LMA reset section template drift: {name}")
        address = matches[0].group(2)
        result = pattern.sub(
            rf"\g<1>{address} : AT({address}) {{", result, count=1)
    result += "\n/* Reset the inherited Bank-2 LMA delta at the existing " \
              "resident PRG chain. */\n"
    for name in LOW_RESIDENT_LMA_SECTIONS:
        result += (
            f"ASSERT(LOADADDR({name}) == ADDR({name}),\n"
            f'       "{name} escaped the resident PRG LMA chain");\n')
    return result


def low_resident_lma_reset_gate(script: str) -> dict[str, str]:
    """Require the exact four LMA=VMA resets and reject a broader rewrite."""
    explicit = re.findall(
        r"(?m)^\s*(\.lisp65_c2_[A-Za-z0-9_.]+)\s+"
        r"(0x[0-9a-f]+)\s+:\s+AT\((0x[0-9a-f]+)\)\s+\{", script)
    rows = {name: (vma, lma) for name, vma, lma in explicit
            if name in LOW_RESIDENT_LMA_SECTIONS}
    if set(rows) != set(LOW_RESIDENT_LMA_SECTIONS):
        raise RuntimeError("low-resident LMA reset set is incomplete")
    if any(vma != lma for vma, lma in rows.values()):
        raise RuntimeError("low-resident LMA reset does not equal its VMA")
    for name in LOW_RESIDENT_LMA_SECTIONS:
        assertion = f"ASSERT(LOADADDR({name}) == ADDR({name}),"
        if script.count(assertion) != 1:
            raise RuntimeError(
                f"low-resident LMA assertion absent or duplicated: {name}")
    forbidden: set[str] = set()
    for name, vma, lma in explicit:
        if (name.startswith(".lisp65_c2_kernal_")
                or name == ".lisp65_c2_host_facade") \
                and name not in LOW_RESIDENT_LMA_SECTIONS and vma == lma:
            forbidden.add(name)
    if forbidden:
        raise RuntimeError(
            "low-resident LMA reset broadened beyond four outputs: "
            + ", ".join(sorted(forbidden)))
    return {name: rows[name][0] for name in LOW_RESIDENT_LMA_SECTIONS}


def low_resident_lma_reset_mutation_selftest() -> dict[str, str]:
    fixture = """SECTIONS {
    .lisp65_c2_kernal_handoff 0xb4a3 : {
    }
    .lisp65_c2_host_facade 0xb5c4 : {
    }
    .lisp65_c2_kernal_io_reveal 0xb5f4 : {
    }
    .lisp65_c2_kernal_map_switch 0xb5ff : {
    }
    .lisp65_c2_kernal_state 0xb609 (NOLOAD) : {
    }
}
"""
    valid = apply_low_resident_lma_reset(fixture)
    low_resident_lma_reset_gate(valid)
    cases = {
        "missing-handoff-reset": valid.replace(
            "0xb4a3 : AT(0xb4a3)", "0xb4a3 :", 1),
        "missing-facade-reset": valid.replace(
            "0xb5c4 : AT(0xb5c4)", "0xb5c4 :", 1),
        "missing-reveal-reset": valid.replace(
            "0xb5f4 : AT(0xb5f4)", "0xb5f4 :", 1),
        "missing-map-reset": valid.replace(
            "0xb5ff : AT(0xb5ff)", "0xb5ff :", 1),
        "wrong-handoff-lma": valid.replace(
            "AT(0xb4a3)", "AT(0x02f4a3)", 1),
        "broaden-to-state": valid.replace(
            ".lisp65_c2_kernal_state 0xb609 (NOLOAD) : {",
            ".lisp65_c2_kernal_state 0xb609 : AT(0xb609) {", 1),
        "duplicate-handoff-assertion": valid + (
            "ASSERT(LOADADDR(.lisp65_c2_kernal_handoff) == "
            "ADDR(.lisp65_c2_kernal_handoff), \"duplicate\");\n"),
    }
    result: dict[str, str] = {}
    for name, mutant in cases.items():
        try:
            low_resident_lma_reset_gate(mutant)
        except RuntimeError:
            result[name] = "rejected"
        else:
            result[name] = "accepted"
    if set(result.values()) != {"rejected"}:
        raise RuntimeError("low-resident LMA reset mutation survived")
    return result


def full_map_platform_c_ld() -> str:
    """Return the owned replacement for llvm-mos' inherited ``c.ld``.

    Expected addresses are contract constants selected in v1.8 Phase B.  The
    permanent Phase-C gate binds those values independently; this renderer is
    never its own oracle.
    """
    if not FULL_MAP_OWNERSHIP:
        raise RuntimeError("full-map platform linker requested before selection")
    return r'''/* Generated v1.8 full-map owner.  This file deliberately
 * replaces the platform c.ld include; it is not an INSERT overlay. */
INCLUDE zp.ld
.text 0x2023 : {
    INCLUDE text-sections.ld
} >c_readonly

.rodata 0xb61d : {
    INCLUDE rodata-sections.ld
} >c_readonly

.lisp65_runtime_overlay_verifier_bindings 0xb98c : {
    __lisp65_rtov_binding_section_start = .;
    KEEP(*(.lisp65_runtime_overlay_verifier_bindings))
    __lisp65_rtov_binding_section_end = .;
} >c_writeable

.data 0xb9b4 : AT(0xb9b4) {
    INCLUDE data-sections.ld
} >c_writeable
INCLUDE data-symbols.ld

.bss 0xb9ca (NOLOAD) : {
    INCLUDE bss-sections.ld
} >c_writeable
INCLUDE bss-symbols.ld

/* The sole .noinit-namespace resident is extracted by the named static-stack
 * owner before this empty ordinary owner.  The old six-byte interval is a
 * named gap, not padding and not duplicate state. */
.noinit 0xc34d (NOLOAD) : {
    INCLUDE noinit-sections.ld
} >c_writeable
__lisp65_c2_ordinary_noinit_end = ADDR(.noinit) + SIZEOF(.noinit);
__heap_start = 0xc354;
'''


def full_map_platform_commodore_ld() -> str:
    """Return the small parent include that fixes the PRG predecessor too.

    lld assigns address-less outputs after later explicit outputs in the same
    region.  Once the ordinary chain has contract VMAs, the platform's
    address-less BASIC header would otherwise drift behind it.  Shadowing the
    parent include gives that existing predecessor its already-proven $2001
    VMA; no input ownership or runtime semantics change.
    """
    if not FULL_MAP_OWNERSHIP:
        raise RuntimeError("full-map parent linker requested before selection")
    return r'''/* Generated v1.8 parent for the owned platform c.ld. */
__rc0 = __basic_zp_start;
INCLUDE imag-regs.ld
__basic_zp_size = __basic_zp_end - __basic_zp_start;
MEMORY { zp : ORIGIN = __rc31 + 1, LENGTH = __basic_zp_end - (__rc31 + 1) }
INPUT(basic-header.o)
REGION_ALIAS("c_readonly", ram)
REGION_ALIAS("c_writeable", ram)
SECTIONS {
    .basic_header 0x2001 : { *(.basic_header) }
    INCLUDE c.ld
}
'''


def full_map_platform_zp_data_ld() -> str:
    """Preserve the existing ZP initializer LMA under explicit later VMAs."""
    if not FULL_MAP_OWNERSHIP:
        raise RuntimeError("full-map ZP linker requested before selection")
    return r'''.zp.data : AT(0x2017) {
    INCLUDE zp-data-sections.ld
} >zp
INCLUDE zp-data-symbols.ld
'''


def full_map_rewrite_product_linker(script: str) -> str:
    """Own the non-platform pieces of the selected ordinary chain.

    The replacement platform ``c.ld`` owns the verifier table's contract VMA
    as part of the ordinary chain.  Remove the former product-local INSERT and
    strengthen the old predecessor-only assertions into the complete
    simultaneous-live ledger.
    """
    if not FULL_MAP_OWNERSHIP:
        return script
    binding_block = (
        "SECTIONS {\n"
        "    .lisp65_runtime_overlay_verifier_bindings : {\n"
        "        __lisp65_rtov_binding_section_start = .;\n"
        "        KEEP(*(.lisp65_runtime_overlay_verifier_bindings))\n"
        "        __lisp65_rtov_binding_section_end = .;\n"
        "    } >ram\n"
        "} INSERT AFTER .rodata;\n\n")
    if script.count(binding_block) != 1:
        raise RuntimeError("full-map verifier binding template drift")
    script = script.replace(binding_block, "", 1)
    inherited_noinit = re.compile(
        r"ASSERT\(ADDR\(\.noinit\) == 0x[0-9a-f]+ &&\n"
        r"       SIZEOF\(\.noinit\) == [0-9]+ &&\n"
        r"       __lisp65_workbench_overlay_min_start == 0x[0-9a-f]+ &&\n"
        r"       __lisp65_workbench_overlay_min_start <=\n"
        r"           __lisp65_workbench_runtime_overlay_vma,\n"
        r"       \"C2 inherited noinit/fixed-block geometry drift\"\);\n")
    script, replacements = inherited_noinit.subn(
        "ASSERT(ADDR(.noinit) == 0xc34d &&\\n"
        "       SIZEOF(.noinit) == 0 &&\\n"
        "       __heap_start == 0xc354 &&\\n"
        "       __lisp65_workbench_overlay_min_start == 0xc354 &&\\n"
        "       __lisp65_workbench_overlay_min_start <=\\n"
        "           __lisp65_workbench_runtime_overlay_vma,\\n"
        "       \"C2 full-map empty-noinit/heap geometry drift\");\\n",
        script, count=1)
    if replacements != 1:
        raise RuntimeError("full-map inherited noinit assertion drift")
    return script + r'''

/* v1.8 full-map simultaneous-live closure.  All addresses are duplicated in
 * the independent Phase-B contract and checked by the permanent gate. */
ASSERT(ADDR(.rodata) == 0xb61d && SIZEOF(.rodata) == 879 &&
       ADDR(.lisp65_runtime_overlay_verifier_bindings) == 0xb98c &&
       SIZEOF(.lisp65_runtime_overlay_verifier_bindings) == 40 &&
       ADDR(.data) == 0xb9b4 && LOADADDR(.data) == 0xb9b4 &&
       SIZEOF(.data) == 22 &&
       ADDR(.bss) == 0xb9ca && SIZEOF(.bss) == 1585 &&
       ADDR(.bss) + SIZEOF(.bss) == 0xbffb,
       "ordinary full-map chain drift");
ASSERT(ADDR(.lisp65_c2_convergence_state) == 0xc000 &&
       ADDR(.lisp65_c2_static_stack) == 0xc074 &&
       SIZEOF(.lisp65_c2_static_stack) == 6 &&
       ADDR(.lisp65_c2_fixed_bank0) == 0xc080 &&
       ADDR(.lisp65_c2_fixed_bank0_hot_bss) +
           SIZEOF(.lisp65_c2_fixed_bank0_hot_bss) == 0xc34d &&
       ADDR(.noinit) == 0xc34d && SIZEOF(.noinit) == 0 &&
       __heap_start == 0xc354 &&
       __lisp65_workbench_overlay_min_start == 0xc354 &&
       __lisp65_workbench_runtime_overlay_vma >= __heap_start,
       "fixed/full-map/heap/overlay simultaneous-live relation drift");
ASSERT(0xc000 - (ADDR(.bss) + SIZEOF(.bss)) == 5,
       "five-byte validation margin drifted; it is not capacity");
'''


def write_product_linker_sources(
        out: Path, probe_definitions: tuple[str, ...] = ()) -> None:
    """Write every linker source selected for one product-shaped link."""
    write(out / "c2-substitution.ld", linker_script(
        ownership_opt_in=ownership_scope_selected(probe_definitions)))
    if FULL_MAP_OWNERSHIP:
        include_dir = out / "full-map-linker"
        include_dir.mkdir(parents=True, exist_ok=True)
        write(include_dir / "c.ld", full_map_platform_c_ld())
        write(include_dir / "commodore.ld", full_map_platform_commodore_ld())
        write(include_dir / "zp-data.ld", full_map_platform_zp_data_ld())


def configure_require_resolver_profile_geometry() -> None:
    """Bind the append-only Prim-ID 67 table growth before linker rendering.

    The complete-profile CALLPRIM table carries one uint16 entry per active
    identity.  Activating private Prim-ID 67 therefore changes only that
    canonical table from 164 to 166 bytes.  This named selector keeps the
    released Link-67 geometry as the module default and forbids an arbitrary
    caller-selected profile width.
    """
    global PROFILE_RODATA_BYTES, REQUIRE_RESOLVER_PROFILE_CONFIGURED
    if REQUIRE_RESOLVER_PROFILE_CONFIGURED:
        # Preserve the historical public diagnostic while making its cause an
        # explicit process one-shot state rather than an incidental width
        # comparison.  The permanent gate classifies this branch as
        # configured-twice.
        raise ValueError("require-resolver profile selector order drift")
    if (PROFILE_RODATA_INPUT_SECTIONS[".rodata.eval_v2_workbench_service"] != 32
            or PROFILE_RODATA_INPUT_SECTIONS[".rodata.vm_callprim"] != 164
            or PROFILE_RODATA_INPUT_SECTIONS[".rodata.vm_native_call"] != 146):
        raise ValueError("require-resolver profile selector order drift")
    REQUIRE_RESOLVER_PROFILE_CONFIGURED = True
    PROFILE_RODATA_INPUT_SECTIONS[".rodata.vm_callprim"] = 166
    PROFILE_RODATA_BYTES = sum(PROFILE_RODATA_INPUT_SECTIONS.values())


def configure_defstruct_foundation_profile_geometry() -> None:
    """Bind public Prim-ID 68 after the require-resolver geometry selector.

    `intern` is public in both the CALLPRIM dispatch table and the native
    function-designator table.  Each canonical surface therefore gains one
    uint16 row.  The selector is deliberately order-sensitive: a product
    carrying the defstruct foundations must first select the accepted
    Prim-ID-67 geometry and may then append exactly these two bound rows.
    """
    global PROFILE_RODATA_BYTES
    if (PROFILE_RODATA_INPUT_SECTIONS[".rodata.eval_v2_workbench_service"] != 32
            or PROFILE_RODATA_INPUT_SECTIONS[".rodata.vm_callprim"] != 166
            or PROFILE_RODATA_INPUT_SECTIONS[".rodata.vm_native_call"] != 146):
        raise ValueError("defstruct-foundation profile selector order drift")
    PROFILE_RODATA_INPUT_SECTIONS[".rodata.vm_callprim"] = 168
    PROFILE_RODATA_INPUT_SECTIONS[".rodata.vm_native_call"] = 148
    PROFILE_RODATA_BYTES = sum(PROFILE_RODATA_INPUT_SECTIONS.values())
FAMILY_STAGE_BINDINGS = False
FAMILY_STAGE_BINDING_BYTES = 8
VERIFIER_BINDING_BASE = 0xB954
KERNAL_CRC_BINDING_HIGH_ADDRESS = 0xB4F4
KERNAL_CRC_BINDING_LOW_ADDRESS = 0xB4FA
KERNAL_CRC_BINDING_BYTES = 2
TOTAL_PUBLISH_LAST_BYTES = VERIFIER_BINDING_BYTES + KERNAL_CRC_BINDING_BYTES
KERNAL_CRC_BINDING_SENTINEL = 0xA55A
VERIFIER_BINDING_SENTINELS = (
    0xA100, 0xA101, 0xA102, 0xA103,
    0xA110, 0xA111, 0xA112, 0xA113,
    0xB100, 0xB101, 0xB102, 0xB103,
    0xB110, 0xB111, 0xB112, 0xB113,
)
FAMILY_STAGE_BINDING_SENTINELS = (0xC100, 0xC101, 0xC110, 0xC111)
RUNTIME_OVERLAY_FORMAT_VERSION = 3
SESSION_REGION1_SLICE_NAMES: set[str] = set()
EXTRA_INCLUDE_DIRS: tuple[Path, ...] = ()
COMPILER_CONSUMED_STATIC_HEADER: Path | None = None
COMPILER_CONSUMED_STATIC_HEADER_BINDING: dict[str, object] | None = None
COMPILER_CONSUMED_STATIC_CODE_BYTES: int | None = None
COMPILER_CONSUMED_FEATURE_PROFILE: Path | None = None
COMPILER_CONSUMED_FEATURE_PROFILE_BINDING: dict[str, object] | None = None
COMPILER_CONSUMED_FEATURES: tuple[str, ...] = ()


def configure_compiler_consumed_static_header(
        header: Path, binding: dict[str, object], code_bytes: int) -> None:
    """Force and verify the candidate static-plane header in real compiles.

    Binding an input in a preflight receipt is not enough: the compiler must
    receive that exact path.  ``compile_link`` force-includes the bound header
    and a build-local assertion after it for every C/assembler participant.
    A successful link therefore proves both path consumption and macro value.
    """
    global COMPILER_CONSUMED_STATIC_HEADER
    global COMPILER_CONSUMED_STATIC_HEADER_BINDING
    global COMPILER_CONSUMED_STATIC_CODE_BYTES
    raw = header.read_bytes()
    actual = {
        "path": header.relative_to(ROOT).as_posix(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    values = re.findall(
        rb"^#define LISP65_C2_LITE_STATIC_CODE_BYTES ([0-9]+)UL$",
        raw, re.MULTILINE)
    if actual != binding or values != [str(code_bytes).encode()]:
        raise RuntimeError(
            "bound candidate static header identity/value mismatch")
    COMPILER_CONSUMED_STATIC_HEADER = header
    COMPILER_CONSUMED_STATIC_HEADER_BINDING = dict(binding)
    COMPILER_CONSUMED_STATIC_CODE_BYTES = code_bytes


def compiler_consumed_static_header_flags(
        out: Path, target: Path) -> tuple[list[str], dict[str, object] | None]:
    """Return the actual force-include flags and their build-local proof."""
    if COMPILER_CONSUMED_STATIC_HEADER is None:
        if (COMPILER_CONSUMED_STATIC_HEADER_BINDING is not None
                or COMPILER_CONSUMED_STATIC_CODE_BYTES is not None):
            raise RuntimeError("partial compiler-consumed header state")
        return [], None
    header = COMPILER_CONSUMED_STATIC_HEADER
    binding = COMPILER_CONSUMED_STATIC_HEADER_BINDING
    code_bytes = COMPILER_CONSUMED_STATIC_CODE_BYTES
    if binding is None or code_bytes is None:
        raise RuntimeError("partial compiler-consumed header contract")
    raw = header.read_bytes()
    actual = {
        "path": header.relative_to(ROOT).as_posix(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    if actual != binding:
        raise RuntimeError("compiler-consumed candidate header drift")
    assertion = out / (target.stem + ".compiler-input-assert.h")
    write(assertion, "\n".join([
        "#ifndef LISP65_C2_LITE_STATIC_CODE_BYTES",
        '#error "bound candidate static-plane header was not consumed"',
        "#endif",
        f"#if LISP65_C2_LITE_STATIC_CODE_BYTES != {code_bytes}UL",
        '#error "consumed static-plane extent differs from bound candidate"',
        "#endif", "",
    ]))
    flags = [
        "-include", header.relative_to(ROOT).as_posix(),
        "-include", assertion.relative_to(ROOT).as_posix(),
    ]
    return flags, {
        "format": "lisp65-real-compiler-input-consumption-v1",
        "status": "passed-bound-candidate-header-consumed",
        "consumer": "c2_product_substitution_link.compile_link",
        "target": target.relative_to(ROOT).as_posix(),
        "bound_header": binding,
        "macro": "LISP65_C2_LITE_STATIC_CODE_BYTES",
        "consumed_value": code_bytes,
        "force_include_order": [
            header.relative_to(ROOT).as_posix(),
            assertion.relative_to(ROOT).as_posix(),
        ],
        "compile_time_assertion": {
            "path": assertion.relative_to(ROOT).as_posix(),
            "bytes": assertion.stat().st_size,
            "sha256": hashlib.sha256(assertion.read_bytes()).hexdigest(),
        },
        "historical_same_basename_accepted": False,
    }


def configure_compiler_consumed_feature_profile(
        profile: Path, binding: dict[str, object],
        features: tuple[str, ...]) -> tuple[
            Path | None, dict[str, object] | None, tuple[str, ...]]:
    """Bind a resolved feature profile to the actual compiler command."""
    global COMPILER_CONSUMED_FEATURE_PROFILE
    global COMPILER_CONSUMED_FEATURE_PROFILE_BINDING
    global COMPILER_CONSUMED_FEATURES
    raw = profile.read_bytes()
    actual = {
        "path": profile.relative_to(ROOT).as_posix(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    rows = [line.split("=", 1)[1].split(",")
            for line in raw.decode("utf-8").splitlines()
            if line.startswith("feature_defines=")]
    if (actual != binding or len(rows) != 1
            or tuple(rows[0]) != features or not features
            or len(features) != len(set(features))):
        raise RuntimeError("bound compiler feature-profile identity/value mismatch")
    old = (COMPILER_CONSUMED_FEATURE_PROFILE,
           COMPILER_CONSUMED_FEATURE_PROFILE_BINDING,
           COMPILER_CONSUMED_FEATURES)
    COMPILER_CONSUMED_FEATURE_PROFILE = profile
    COMPILER_CONSUMED_FEATURE_PROFILE_BINDING = dict(binding)
    COMPILER_CONSUMED_FEATURES = tuple(features)
    return old


def restore_compiler_consumed_feature_profile(
        state: tuple[Path | None, dict[str, object] | None,
                     tuple[str, ...]]) -> None:
    global COMPILER_CONSUMED_FEATURE_PROFILE
    global COMPILER_CONSUMED_FEATURE_PROFILE_BINDING
    global COMPILER_CONSUMED_FEATURES
    (COMPILER_CONSUMED_FEATURE_PROFILE,
     COMPILER_CONSUMED_FEATURE_PROFILE_BINDING,
     COMPILER_CONSUMED_FEATURES) = state


def compiler_consumed_feature_profile_gate(
        compile_flags: list[str], target: Path) -> dict[str, object] | None:
    """Prove every bound profile feature occurs once in real compiler flags."""
    profile = COMPILER_CONSUMED_FEATURE_PROFILE
    binding = COMPILER_CONSUMED_FEATURE_PROFILE_BINDING
    features = COMPILER_CONSUMED_FEATURES
    if profile is None:
        if binding is not None or features:
            raise RuntimeError("partial compiler feature-profile state")
        return None
    if binding is None or not features:
        raise RuntimeError("partial compiler feature-profile contract")
    raw = profile.read_bytes()
    actual = {
        "path": profile.relative_to(ROOT).as_posix(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    rows = [line.split("=", 1)[1].split(",")
            for line in raw.decode("utf-8").splitlines()
            if line.startswith("feature_defines=")]
    if actual != binding or len(rows) != 1 or tuple(rows[0]) != features:
        raise RuntimeError("compiler feature-profile authority drift")
    definitions = [flag[2:] for flag in compile_flags if flag.startswith("-D")]
    names = [item.split("=", 1)[0] for item in definitions]
    missing = [name for name in features if name not in names]
    non_unique = [name for name in features if names.count(name) != 1]
    if missing or non_unique:
        raise RuntimeError(
            "bound compiler feature escaped real command: "
            f"missing={missing} non_unique={non_unique}")
    return {
        "format": "lisp65-real-compiler-feature-consumption-v1",
        "status": "passed-bound-feature-profile-consumed",
        "consumer": "c2_product_substitution_link.compile_link",
        "target": target.relative_to(ROOT).as_posix(),
        "bound_profile": binding,
        "bound_features": list(features),
        "bound_feature_count": len(features),
        "consumed_features": list(features),
        "consumed_feature_count": len(features),
        "missing_features": [],
        "non_unique_features": [],
        "actual_definition_count": len(names),
    }


def runtime_binding_bytes() -> int:
    return VERIFIER_BINDING_BYTES + (
        FAMILY_STAGE_BINDING_BYTES if FAMILY_STAGE_BINDINGS else 0)


def total_publish_last_bytes() -> int:
    return runtime_binding_bytes() + KERNAL_CRC_BINDING_BYTES
KERNAL_CONTRACT = ROOT / "config/c2-kernal-unmap-contract.json"
FINAL_SECTION_INVENTORY_PIN = (
    ROOT / "config/c2-final-section-inventory-pin.txt")
DIRECT_ENTRY_CONTRACT_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-direct-entry-encoding-correction-contract-receipt.json")
PROFILE_DATA_WRAPPER_REPLAY_ROOT = (
    ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/artifacts/"
    "c2-link28-v2-profile-data-placement-wrapper-inventory-order-first-red-"
    "20260720/root")
PROFILE_DATA_WRAPPER_REPLAY_TREE_SHA256 = (
    "76b30ab24d650c831840bd46c267c52459a2cb25540791efb71fc900aa9a65a1")
PROFILE_DATA_WRAPPER_REPLAY_ELF_SHA256 = (
    "92b9eac60ba766a0ba30cee97ca34c07a28076e6e00800ca1c62a740f3acb339")
PROFILE_DATA_WRAPPER_REPLAY_LTO_SHA256 = (
    "7fd609bbffdca8ec0dcab9d53494222bfb9fa7f8dbd052864ea7ae5edb536223")
HOST_FACADE_SYMBOLS = (
    "c2_facade_vm_code_load",
    "c2_facade_c2_dma",
    "c2_facade_overlay_call_family",
    "c2_facade_c2e_cons",
    "c2_facade_c2e_overlay",
    "c2_facade_car",
    "c2_facade_cdr",
    "c2_facade_gc_collect",
    "c2_facade_str_open",
    "c2_facade_str_putc",
    "c2_facade_intern",
    "c2_facade_select_family",
    "c2_facade_gc_mark",
)
ORPHAN_ALLOWLIST = (
    ".comment",
    ".symtab",
    ".strtab",
    ".shstrtab",
    ".lisp65_error_callsites",
)

LEGACY_C = {
    "attic_library_shelf.c",
    "c1_compiler_overlay.c",
    "c1_phase_probe.c",
    "l65m_commit_overlay.c",
    "l65m_validate.c",
    "lcc_install_overlay.c",
    "vm_boot_fastpath.c",
    "vm_embed.c",
    "c2_product_decoder.c",
}

C2_PHASE_SOURCES = [
    ROOT / "scripts/c2-stream-init.c",
    ROOT / "scripts/c2-stream-phase-00.c",
    ROOT / "scripts/c2-stream-phase-00b.c",
    ROOT / "scripts/c2-stream-phase-01.c",
    ROOT / "scripts/c2-stream-phase-02a.c",
    ROOT / "scripts/c2-stream-phase-02b.c",
    ROOT / "scripts/c2-stream-phase-03.c",
    ROOT / "scripts/c2-stream-phase-04.c",
    ROOT / "scripts/c2-stream-phase-05.c",
    ROOT / "scripts/c2-stream-phase-06a.c",
    ROOT / "scripts/c2-stream-phase-06b.c",
    ROOT / "scripts/c2-stream-v2-phase-07.c",
    ROOT / "scripts/c2-stream-v2-phase-08.c",
    ROOT / "scripts/c2-stream-v2-phase-09.c",
    ROOT / "scripts/c2-stream-v2-phase-10.c",
    ROOT / "scripts/c2-stream-v2-phase-11.c",
    ROOT / "scripts/c2-stream-v2-phase-12.c",
    ROOT / "scripts/c2-stream-v2-phase-13.c",
]

CONVERGENCE_FEATURE = "LISP65_CODE_WINDOW_CONVERGENCE"
CONVERGENCE_DEFINES = (
    CONVERGENCE_FEATURE,
    "LISP65_DMA_CONTENT_CONVERGENCE",
    "LISP65_C2_ASM_CONVERGENCE",
)
CONVERGENCE_SOURCES = (
    ROOT / "src/c2_mapped_far_service.s",
    ROOT / "src/c2_mapped_far_convergence.s",
)
TERMINAL_RETURN_GUARD_FEATURE = "LISP65_C2_TERMINAL_RETURN_GUARD"
OWNERSHIP_CONTRACT = ROOT / "config/c2-stack-overlay-ownership-contract.json"
SOURCE_OWNER_SCOPES = ({
    "name": "mapped-far-content-convergence",
    "trigger": CONVERGENCE_FEATURE,
    "defines": CONVERGENCE_DEFINES,
    "sources": CONVERGENCE_SOURCES,
}, {
    "name": "map-cpu-library-read",
    "trigger": "LISP65_C2_MAP_CPU_TRANSPORT",
    "defines": ("LISP65_C2_MAP_CPU_TRANSPORT",),
    "sources": (ROOT / "src/optional/c2_map_cpu_read.s",),
}, {
    "name": "v160-input-capture",
    "trigger": INPUT_CAPTURE_FEATURE,
    "defines": (INPUT_CAPTURE_FEATURE,),
    "sources": (INPUT_CAPTURE_SOURCE,),
}, {
    "name": "v160-input-hybrid",
    "trigger": INPUT_HYBRID_FEATURE,
    "defines": (INPUT_HYBRID_FEATURE,),
    "sources": (INPUT_HYBRID_SOURCE,),
}, {
    "name": "v160-refill-boundary-witness",
    "trigger": REFILL_WITNESS_FEATURE,
    "defines": (REFILL_WITNESS_FEATURE,),
    "sources": (REFILL_WITNESS_SOURCE,),
}, {
    "name": "v160-product-cold-disk-chain",
    "trigger": PRODUCT_COLD_FEATURE,
    "defines": (PRODUCT_COLD_FEATURE,),
    "sources": (PRODUCT_COLD_SOURCE,),
})


def ownership_scope_selected(
        extra_definitions: tuple[str, ...] = ()) -> bool:
    """Return whether the parked ownership/Link-91 closure is selected."""
    return FULL_MAP_OWNERSHIP or CONVERGENCE_FEATURE in extra_definitions


def ownership_link_flags(
        extra_definitions: tuple[str, ...] = ()) -> tuple[str, ...]:
    """Return the complete linker-flag side of the ownership opt-in seam."""
    if not ownership_scope_selected(extra_definitions):
        return ()
    flags = [
        "-Wl,--no-check-sections",
        "-Wl,--defsym=__lisp65_c2_mapped_far_required_param=1",
    ]
    if "LISP65_C2_MUTABLE_CPU_READS" in extra_definitions:
        flags.append(
            "-Wl,--defsym="
            "__lisp65_c2_mapped_far_facade_padding_required_param=1")
    return tuple(flags)

C2_DECODER_SLICES = [
    ("00", "c2_stream_phase_00"),
    ("00b", "c2_stream_phase_00b"),
    ("01", "c2_stream_phase_01"),
    ("02a", "c2_stream_phase_02a"),
    ("02b", "c2_stream_phase_02b"),
    ("03", "c2_stream_phase_03"),
    ("04", "c2_stream_phase_04"),
    ("05", "c2_stream_phase_05"),
    ("06a", "c2_stream_phase_06a"),
    ("06b", "c2_stream_phase_06b"),
    ("07", "c2_stream_phase_07"),
    ("08", "c2_stream_phase_08"),
    ("09", "c2_stream_phase_09"),
    ("10", "c2_stream_phase_10"),
    ("11", "c2_stream_phase_11"),
    ("12", "c2_stream_phase_12"),
    ("13", "c2_stream_phase_13"),
]
C2_DECODER_LINK28_SLICES = list(C2_DECODER_SLICES)

C2_EMITTER_SLICES = [
    ("prepare", "c2_session_emit_prepare_phase"),
    ("name", "c2_session_emit_name_phase"),
    ("literal_prep", "c2_session_emit_literal_prep_phase"),
    ("literal_atom", "c2_session_emit_literal_atom_phase"),
    ("literal_append", "c2_session_emit_literal_append_phase"),
    ("code", "c2_session_emit_code_phase"),
    ("final_meta", "c2_session_emit_final_meta_phase"),
    ("final_crc", "c2_session_emit_final_crc_phase"),
]

C2_APPEND_LINK28_SLICES = [
    ("envelope", "c2_append_envelope_phase"),
    ("crc", "c2_append_crc_phase"),
    ("metadata", "c2_append_metadata_phase"),
    ("capacity", "c2_append_capacity_phase"),
    ("stage", "c2_append_stage_phase"),
    ("image", "c2_append_image_phase"),
    ("entries", "c2_append_entries_phase"),
    ("header", "c2_append_header_phase"),
    ("publish_names", "c2_append_publish_names_phase"),
    ("publish_cells", "c2_append_publish_cells_phase"),
    ("rollback", "c2_append_rollback_phase"),
]
C2_APPEND_SLICES = list(C2_APPEND_LINK28_SLICES)

C2_APPEND_V5_SLICES = [
    ("envelope", "c2_append_envelope_phase"),
    ("crc", "c2_append_crc_phase"),
    ("metadata", "c2_append_metadata_phase"),
    ("roots", "c2_append_roots_phase"),
    ("fronts", "c2_append_fronts_phase"),
    ("reserve_transient", "c2_append_reserve_transient_phase"),
    ("reserve_persistent", "c2_append_reserve_persistent_phase"),
    ("journal_clear", "c2_append_journal_clear_phase"),
    ("journal_write", "c2_append_journal_write_phase"),
    ("journal_validate", "c2_append_journal_validate_phase"),
    ("journal_reconstruct", "c2_append_journal_reconstruct_phase"),
    ("rollback_prepare", "c2_append_rollback_prepare_phase"),
    ("stage", "c2_append_stage_phase"),
    ("image", "c2_append_image_phase"),
    ("entries", "c2_append_entries_phase"),
    ("header", "c2_append_header_phase"),
    ("publish_names", "c2_append_publish_names_phase"),
    ("publish_cells", "c2_append_publish_cells_phase"),
    ("rollback_unpublish", "c2_append_rollback_unpublish_phase"),
    ("rollback_finalize", "c2_append_rollback_finalize_phase"),
]

BOOT_DECODER_SLICES = C2_DECODER_SLICES[:6]
SESSION_DECODER_SLICES = C2_DECODER_SLICES[6:]
BANK3_STAGING_SLICES = False
BOOT_BANK3_STAGE_SLOT = 2 + len(BOOT_DECODER_SLICES)
BOOT_ISLAND_SLOT = 2 + len(BOOT_DECODER_SLICES)
BOOT_ISLAND_CARRIER_SLOT = BOOT_ISLAND_SLOT + 1
SESSION_EMITTER_SLOT_BASE = 2 + len(SESSION_DECODER_SLICES)
SESSION_APPEND_SLOT_BASE = SESSION_EMITTER_SLOT_BASE + len(C2_EMITTER_SLICES)
SESSION_SERVICE_SLOT_BASE = SESSION_APPEND_SLOT_BASE + len(C2_APPEND_SLICES)
INTERN_SESSION_SERVICE = False

VERIFIER_SPECS = [
    "0:catalog-verifier:.lisp65_rt_rtov_catalog:__lisp65_rt_rtov_catalog_start:__lisp65_rt_rtov_catalog_end:__lisp65_rt_rtov_catalog_entry:runtime+reusable:1:0:vm_runtime_overlay_catalog_verifier",
    "1:record-verifier:.lisp65_rt_rtov_record:__lisp65_rt_rtov_record_start:__lisp65_rt_rtov_record_end:__lisp65_rt_rtov_record_entry:runtime+reusable:1:0:vm_runtime_overlay_record_verifier",
]


def session_service_specs() -> list[str]:
    rows = [
        f"{SESSION_SERVICE_SLOT_BASE}:error-text-renderer:.lisp65_rt_l65e:__lisp65_rt_l65e_start:__lisp65_rt_l65e_end:__lisp65_rt_l65e_entry:runtime+reusable:1:0:lisp65_error_overlay_entry",
        f"{SESSION_SERVICE_SLOT_BASE + 1}:first-class-buffer-read:.lisp65_rt_buffer_read:__lisp65_rt_buffer_read_start:__lisp65_rt_buffer_read_end:__lisp65_rt_buffer_read_entry:runtime+reusable:1:0:lisp65_buffer_overlay_read_entry",
        f"{SESSION_SERVICE_SLOT_BASE + 2}:first-class-buffer-write:.lisp65_rt_buffer_write:__lisp65_rt_buffer_write_start:__lisp65_rt_buffer_write_end:__lisp65_rt_buffer_write_entry:runtime+reusable:1:0:lisp65_buffer_overlay_write_entry",
        f"{SESSION_SERVICE_SLOT_BASE + 3}:first-class-buffer-alloc:.lisp65_rt_buffer_alloc:__lisp65_rt_buffer_alloc_start:__lisp65_rt_buffer_alloc_end:__lisp65_rt_buffer_alloc_entry:runtime+reusable:1:0:lisp65_buffer_overlay_alloc_entry",
    ]
    if INTERN_SESSION_SERVICE:
        rows.append(
            f"{SESSION_SERVICE_SLOT_BASE + 4}:intern-session-service:.lisp65_rt_intern_service:__lisp65_rt_intern_service_start:__lisp65_rt_intern_service_end:__lisp65_rt_intern_service_entry:runtime+reusable:1:0:lisp65_intern_service_entry")
    return rows


def checked_public_projection(names: list[str]) -> dict[str, str]:
    """Project internal C identifiers once at the public L65R boundary."""
    projected: dict[str, str] = {}
    owners: dict[str, str] = {}
    for internal in names:
        public = internal.replace("_", "-")
        previous = owners.get(public)
        if previous is not None and previous != internal:
            raise RuntimeError(
                f"public slice-name projection collision: {previous!r} and "
                f"{internal!r} both map to {public!r}")
        owners[public] = internal
        projected[internal] = public
    return projected


def session_region_suffix(name: str) -> str:
    """Append the strict-v4 region field only to named overflow residents."""
    return ":1" if name in SESSION_REGION1_SLICE_NAMES else ""


EMITTER_PUBLIC_NAMES = checked_public_projection(
    [name for name, _entry in C2_EMITTER_SLICES])
APPEND_PUBLIC_NAMES = checked_public_projection(
    [name for name, _entry in C2_APPEND_SLICES])

BOOT_SLICE_SPECS = VERIFIER_SPECS + [
    f"{index + 2}:c2-decode-{name}:.lisp65_rt_c2d_{name}:__lisp65_rt_c2d_{name}_start:__lisp65_rt_c2d_{name}_end:__lisp65_rt_c2d_{name}_entry:runtime+reusable:1:0:{entry}"
    for index, (name, entry) in enumerate(BOOT_DECODER_SLICES)
] + [
    f"{BOOT_ISLAND_SLOT}:resident-island-installer:.lisp65_rt_island_00:__lisp65_rt_island_00_start:__lisp65_rt_island_00_end:__lisp65_rt_island_00_entry:boot:1:0:vm_resident_island_install"
]
BOOT_DATA_SPECS = [
    f"{BOOT_ISLAND_CARRIER_SLOT}:resident-island-image:.lisp65_resident_island:"
    "__lisp65_resident_island_start:__lisp65_resident_island_end:"
    "boot+data:0x1800:0"
]

SESSION_SLICE_SPECS = VERIFIER_SPECS + [
    f"{index + 2}:c2-decode-{name}:.lisp65_rt_c2d_{name}:__lisp65_rt_c2d_{name}_start:__lisp65_rt_c2d_{name}_end:__lisp65_rt_c2d_{name}_entry:runtime+reusable:1:0:{entry}"
    for index, (name, entry) in enumerate(SESSION_DECODER_SLICES)
] + [
    f"{SESSION_EMITTER_SLOT_BASE + index}:c2-emit-{EMITTER_PUBLIC_NAMES[name]}:.lisp65_rt_c2emit_{name}:__lisp65_rt_c2emit_{name}_start:__lisp65_rt_c2emit_{name}_end:__lisp65_rt_c2emit_{name}_entry:runtime+reusable:1:0:{entry}"
    for index, (name, entry) in enumerate(C2_EMITTER_SLICES)
] + [
    f"{SESSION_APPEND_SLOT_BASE + index}:c2-append-{APPEND_PUBLIC_NAMES[name]}:.lisp65_rt_c2append_{name}:__lisp65_rt_c2append_{name}_start:__lisp65_rt_c2append_{name}_end:__lisp65_rt_c2append_{name}_entry:runtime+reusable:1:0:{entry}{session_region_suffix(name)}"
    for index, (name, entry) in enumerate(C2_APPEND_SLICES)
] + session_service_specs()

UNIQUE_SLICE_COUNT = (2 + len(C2_DECODER_SLICES) + len(C2_EMITTER_SLICES)
                      + len(C2_APPEND_SLICES) + 5
                      + (1 if INTERN_SESSION_SERVICE else 0))


def assert_unique_public_specs() -> None:
    names = [spec.split(":", 2)[1]
             for spec in BOOT_SLICE_SPECS + BOOT_DATA_SPECS + SESSION_SLICE_SPECS]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    # The two family-local verifier names intentionally repeat across distinct
    # lifetime catalogs.  Every other published name is globally unique.
    expected = {"catalog-verifier", "record-verifier"}
    if set(duplicates) != expected:
        raise RuntimeError(
            f"unexpected public slice-name collision set: {duplicates}")


assert_unique_public_specs()


def configure_append_slices(slices: list[tuple[str, str]]) -> None:
    """Select one complete append ABI before constructing a product link.

    Historical callers retain the legacy eleven-slice default.  A successor
    that changes the append ABI must opt in once, before any linker script,
    profile definition, or runtime-family manifest is generated.
    """
    global C2_APPEND_SLICES, SESSION_SERVICE_SLOT_BASE
    global APPEND_PUBLIC_NAMES, SESSION_SLICE_SPECS, UNIQUE_SLICE_COUNT
    C2_APPEND_SLICES = list(slices)
    APPEND_PUBLIC_NAMES = checked_public_projection(
        [name for name, _entry in C2_APPEND_SLICES])
    SESSION_SERVICE_SLOT_BASE = SESSION_APPEND_SLOT_BASE + len(C2_APPEND_SLICES)
    SESSION_SLICE_SPECS = VERIFIER_SPECS + [
        f"{index + 2}:c2-decode-{name}:.lisp65_rt_c2d_{name}:__lisp65_rt_c2d_{name}_start:__lisp65_rt_c2d_{name}_end:__lisp65_rt_c2d_{name}_entry:runtime+reusable:1:0:{entry}"
        for index, (name, entry) in enumerate(SESSION_DECODER_SLICES)
    ] + [
        f"{SESSION_EMITTER_SLOT_BASE + index}:c2-emit-{EMITTER_PUBLIC_NAMES[name]}:.lisp65_rt_c2emit_{name}:__lisp65_rt_c2emit_{name}_start:__lisp65_rt_c2emit_{name}_end:__lisp65_rt_c2emit_{name}_entry:runtime+reusable:1:0:{entry}"
        for index, (name, entry) in enumerate(C2_EMITTER_SLICES)
    ] + [
        f"{SESSION_APPEND_SLOT_BASE + index}:c2-append-{APPEND_PUBLIC_NAMES[name]}:.lisp65_rt_c2append_{name}:__lisp65_rt_c2append_{name}_start:__lisp65_rt_c2append_{name}_end:__lisp65_rt_c2append_{name}_entry:runtime+reusable:1:0:{entry}{session_region_suffix(name)}"
        for index, (name, entry) in enumerate(C2_APPEND_SLICES)
    ] + session_service_specs()
    UNIQUE_SLICE_COUNT = (2 + len(C2_DECODER_SLICES)
                          + len(C2_EMITTER_SLICES)
                          + len(C2_APPEND_SLICES) + 5
                          + (1 if INTERN_SESSION_SERVICE else 0))
    assert_unique_public_specs()


def configure_intern_session_service() -> None:
    """Add the stateless, on-demand Session service exactly once."""
    global INTERN_SESSION_SERVICE
    if INTERN_SESSION_SERVICE:
        return
    INTERN_SESSION_SERVICE = True
    configure_append_slices(list(C2_APPEND_SLICES))


def configure_runtime_overlay_v4(region1_names: set[str]) -> None:
    """Select strict two-region L65R-v4 as one indivisible product ABI."""
    global RUNTIME_OVERLAY_FORMAT_VERSION, SESSION_REGION1_SLICE_NAMES
    if not region1_names:
        raise RuntimeError("L65R-v4 requires at least one Region-1 slice")
    known = {name for name, _entry in C2_APPEND_SLICES}
    unknown = sorted(set(region1_names) - known)
    if unknown:
        raise RuntimeError(f"unknown Session Region-1 slices: {unknown}")
    RUNTIME_OVERLAY_FORMAT_VERSION = 4
    SESSION_REGION1_SLICE_NAMES = set(region1_names)
    configure_append_slices(list(C2_APPEND_SLICES))


def configure_journal_prepare_co_residence() -> None:
    """Fuse rollback preparation and the following C2J write physically.

    The current v6 profile has already fused roots/fronts and publish/clear.
    This final aggregate-only diet retains both logical operations behind one
    fail-closed entry and removes exactly one 256-byte Session record quantum.
    """
    rows = list(C2_APPEND_SLICES)
    names = [name for name, _entry in rows]
    if names.count("journal_prepare") == 1:
        return
    if names.count("journal_write") != 1 or names.count("rollback_prepare") != 1:
        raise RuntimeError("journal/prepare co-residence anchors absent")
    write_at = names.index("journal_write")
    rows[write_at] = (
        "journal_prepare", "c2_append_journal_prepare_phase")
    names = [name for name, _entry in rows]
    rows.pop(names.index("rollback_prepare"))
    configure_append_slices(rows)


def configure_bank3_staging_slices() -> None:
    """Install the cold C2-lite Bank-3 stage records exactly once.

    Boot staging is an external pre-family L65O record.  Session staging is
    the final Boot-family runtime slice, after decoder phase 03 and before the
    resident-island installer.  It therefore adds one family record without
    changing any Session-family dense slot.
    """
    global BANK3_STAGING_SLICES, BOOT_BANK3_STAGE_SLOT
    global BOOT_ISLAND_SLOT, BOOT_ISLAND_CARRIER_SLOT
    global BOOT_SLICE_SPECS, BOOT_DATA_SPECS, UNIQUE_SLICE_COUNT
    BANK3_STAGING_SLICES = True
    BOOT_BANK3_STAGE_SLOT = 2 + len(BOOT_DECODER_SLICES)
    BOOT_ISLAND_SLOT = BOOT_BANK3_STAGE_SLOT + 1
    BOOT_ISLAND_CARRIER_SLOT = BOOT_ISLAND_SLOT + 1
    BOOT_SLICE_SPECS = VERIFIER_SPECS + [
        f"{index + 2}:c2-decode-{name}:.lisp65_rt_c2d_{name}:__lisp65_rt_c2d_{name}_start:__lisp65_rt_c2d_{name}_end:__lisp65_rt_c2d_{name}_entry:runtime+reusable:1:0:{entry}"
        for index, (name, entry) in enumerate(BOOT_DECODER_SLICES)
    ] + [
        f"{BOOT_BANK3_STAGE_SLOT}:bank3-stage-session:.lisp65_rt_bank3_stage_session:__lisp65_rt_bank3_stage_session_start:__lisp65_rt_bank3_stage_session_end:__lisp65_rt_bank3_stage_session_entry:boot:1:0:c2_lite_stage_session_family",
        f"{BOOT_ISLAND_SLOT}:resident-island-installer:.lisp65_rt_island_00:__lisp65_rt_island_00_start:__lisp65_rt_island_00_end:__lisp65_rt_island_00_entry:boot:1:0:vm_resident_island_install",
    ]
    BOOT_DATA_SPECS = [
        f"{BOOT_ISLAND_CARRIER_SLOT}:resident-island-image:.lisp65_resident_island:"
        "__lisp65_resident_island_start:__lisp65_resident_island_end:"
        "boot+data:0x1800:0"
    ]
    UNIQUE_SLICE_COUNT = (2 + len(C2_DECODER_SLICES)
                          + len(C2_EMITTER_SLICES)
                          + len(C2_APPEND_SLICES) + 6
                          + (1 if INTERN_SESSION_SERVICE else 0))
    assert_unique_public_specs()


def configure_session_emitter_state(bytes_: int) -> None:
    """Select the explicit E000 scalar-state geometry for a bounded probe.

    The released C2 seed keeps the historical 346-byte default.  A placement
    probe that moves immutable emitter descriptors to the Session Bank must
    opt into its smaller, still explicitly placed scalar state before the
    linker script is rendered.
    """
    global SESSION_EMITTER_STATE_BYTES, SESSION_EMITTER_STATE_BASE
    if bytes_ <= 0 or bytes_ > 346:
        raise ValueError(f"invalid session-emitter state geometry: {bytes_}")
    SESSION_EMITTER_STATE_BYTES = bytes_
    SESSION_EMITTER_STATE_BASE = None


def configure_c2_lite_hybrid_e000_geometry() -> None:
    """Select the owner-bound 2026-07-22 C2-lite Hybrid geometry.

    This is deliberately a named profile transition rather than a generic
    floor setter.  With the ten-byte session-emitter state already selected,
    moving the predecessor-bound profile data from $FD12 to $FD2C places the
    state at $FD22: the 128-byte reopen_gap0 then ends exactly at its start.
    The active floor becomes 54 bytes and cannot be lowered by callers.
    Historical Link-35/36 geometry remains the module default until this
    explicit current-profile selector is invoked.
    """
    global E000_FINAL_FLOOR_BYTES, PROFILE_RODATA_BASE
    global SESSION_EMITTER_STATE_BYTES, SESSION_EMITTER_STATE_BASE
    if LINK60_FINAL_GEOMETRY:
        # The two-region driver can select its current geometry before an
        # inherited wrapper reaches this historical Hybrid hook.  Reassert
        # the current zero-byte union anchor instead of resurrecting the old
        # ten-byte output; configuration order is not an authority source.
        E000_FINAL_FLOOR_BYTES = C2_LITE_HYBRID_E000_FLOOR_BYTES
        PROFILE_RODATA_BASE = C2_LITE_HYBRID_PROFILE_RODATA_BASE
        SESSION_EMITTER_STATE_BYTES = 0
        SESSION_EMITTER_STATE_BASE = 0xFD22
        return
    if SESSION_EMITTER_STATE_BYTES != 10:
        raise ValueError(
            "C2-lite Hybrid geometry requires the 10-byte session-emitter state")
    E000_FINAL_FLOOR_BYTES = C2_LITE_HYBRID_E000_FLOOR_BYTES
    PROFILE_RODATA_BASE = C2_LITE_HYBRID_PROFILE_RODATA_BASE
    SESSION_EMITTER_STATE_BASE = 0xFD22


def configure_link60_final_geometry() -> None:
    """Select the owner-authorized 2026-07-24 Link-60 successor pins.

    Whole-program zero-page allocation made ``rtov_fail`` three bytes longer.
    The fixed code therefore ends at $C25D; the intact 240-byte heap and the
    inherited six-byte .noinit chain follow at $C25D/$C34D.  The inherited
    overlay alignment yields $C354, leaving two bytes before the immutable
    $C356 overlay VMA.

    The already-proved c2e_work_state lifetime union makes the old ten-byte
    E000 output an explicit zero-byte anchor at $FD22.  Profile RODATA remains
    predecessor-pinned at $FD2C; this is not an adjacency inference.
    """
    global FIXED_BANK0_CODE_BYTES, FIXED_BANK0_HOT_BSS_BASE
    global SESSION_EMITTER_STATE_BYTES, SESSION_EMITTER_STATE_BASE
    global E000_FINAL_FLOOR_BYTES, PROFILE_RODATA_BASE
    global VERIFIER_BINDING_BASE
    global LINK60_FINAL_GEOMETRY
    E000_FINAL_FLOOR_BYTES = C2_LITE_HYBRID_E000_FLOOR_BYTES
    PROFILE_RODATA_BASE = C2_LITE_HYBRID_PROFILE_RODATA_BASE
    FIXED_BANK0_CODE_BYTES = 69
    FIXED_BANK0_HOT_BSS_BASE = 0xC25D
    SESSION_EMITTER_STATE_BYTES = 0
    SESSION_EMITTER_STATE_BASE = 0xFD22
    VERIFIER_BINDING_BASE = LINK60_VERIFIER_BINDING_BASE
    LINK60_FINAL_GEOMETRY = True
    FIXED_BLOCK_LEAF.configure_link60_geometry()


def run(argv: list[str], *, capture: bool = False) -> str:
    completed = subprocess.run(
        argv, cwd=ROOT, check=True, text=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return completed.stdout if capture else ""


def _orphan_warning_lines(stderr: str) -> list[str]:
    return [
        line.strip() for line in stderr.splitlines()
        if re.match(
            r"^ld\.lld: (?:warning|error): .+:\(\.[^)]+\) "
            r"is being placed in '\.[^']+'$", line.strip())
    ]


def _orphan_wrapper_violations(stderr: str, lto_object: Path) -> list[str]:
    try:
        origin = lto_object.relative_to(ROOT).as_posix()
    except ValueError:
        origin = str(lto_object)
    expected = (
        f"ld.lld: warning: {origin}:(.llvm_sympart) "
        "is being placed in '.llvm_sympart'")
    observed = _orphan_warning_lines(stderr)
    violations: list[str] = []
    if len(observed) != 1:
        violations.append("orphan-diagnostic-count")
    if observed != [expected]:
        violations.append("orphan-diagnostic-wording-or-origin")
    return violations


def _orphan_wrapper_model_selftest() -> dict[str, str]:
    origin = Path("/tmp/c2-product.lto.o")
    valid = (
        "clang: warning: unrelated source warning\n"
        "ld.lld: warning: /tmp/c2-product.lto.o:(.llvm_sympart) "
        "is being placed in '.llvm_sympart'\n")
    if _orphan_wrapper_violations(valid, origin):
        raise AssertionError("valid exact orphan-wrapper diagnostic rejected")
    cases = {
        "zero-orphan-diagnostics": (
            "clang: warning: unrelated source warning\n",
            "orphan-diagnostic-count"),
        "two-orphan-diagnostics": (valid + valid.splitlines()[-1] + "\n",
                                   "orphan-diagnostic-count"),
        "wrong-origin-object": (
            valid.replace("c2-product.lto.o", "other.lto.o"),
            "orphan-diagnostic-wording-or-origin"),
        "wrong-section": (
            valid.replace(".llvm_sympart", ".unknown", 1),
            "orphan-diagnostic-wording-or-origin"),
    }
    for name, (stderr, expected) in cases.items():
        if expected not in _orphan_wrapper_violations(stderr, origin):
            raise AssertionError(f"orphan-wrapper mutation accepted: {name}")
    return {"exact-single-diagnostic": "passed",
            **{name: "rejected" for name in cases}}


def run_link_with_exact_orphan_wrapper(
        out: Path, target: Path, argv: list[str]) -> None:
    completed = subprocess.run(
        argv, cwd=ROOT, check=False, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    write(Path(str(target) + ".link.stdout.txt"), stdout)
    write(Path(str(target) + ".link.stderr.txt"), stderr)
    if stdout:
        sys.stdout.write(stdout)
    if stderr:
        sys.stderr.write(stderr)
    lto_object = Path(str(target) + ".lto.o")
    lto_sha = None
    if lto_object.is_file():
        lto_sha = hashlib.sha256(lto_object.read_bytes()).hexdigest()
        lto_object.chmod(0o444)
    if completed.returncode != 0:
        raise RuntimeError(
            f"link command failed before orphan-wrapper acceptance: "
            f"exit={completed.returncode}")
    violations = _orphan_wrapper_violations(stderr, lto_object)
    if violations:
        raise RuntimeError(f"exact orphan wrapper red: {violations}")
    report = {
        "format": "lisp65-c2-exact-lto-orphan-warning-wrapper-v1",
        "status": "passed",
        "expected_diagnostic_count": 1,
        "observed_diagnostics": _orphan_warning_lines(stderr),
        "section": ".llvm_sympart",
        "origin_object": str(lto_object.relative_to(ROOT)),
        "origin_object_sha256": lto_sha,
        "origin_object_mode": "0444",
        "all_other_orphans": "hard-error-by-exact-diagnostic-gate",
        "zero_diagnostics": "hard-error-tool-behavior-changed",
        "negative_matrix": _orphan_wrapper_model_selftest(),
        "stderr_sha256": hashlib.sha256(stderr.encode("utf-8")).hexdigest(),
    }
    write(out / f"exact-orphan-wrapper-{target.name}.json",
          json.dumps(report, indent=2, sort_keys=True) + "\n")


def write(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data, encoding="ascii")
    else:
        path.write_bytes(data)


def crc16(data: bytes) -> int:
    value = 0xffff
    for byte in data:
        value ^= byte << 8
        for _ in range(8):
            value = (((value << 1) ^ 0x1021) & 0xffff
                     if value & 0x8000 else (value << 1) & 0xffff)
    return value


def canonical_evidence_tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        file_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        digest.update(f"{file_sha}  {relative}\n".encode("ascii"))
    return digest.hexdigest()


KERNAL_SECTIONS = [
    ".lisp65_c2_kernal_window.typed_queue_driver",
    ".lisp65_c2_kernal_window.irq_handler",
    ".lisp65_c2_kernal_window.nmi_and_freezer_return",
    ".lisp65_c2_kernal_window.map_switch_and_guards",
    ".lisp65_c2_kernal_window.post_startup_output_seam",
    ".lisp65_c2_kernal_window.c2_resident",
    ".lisp65_c2_kernal_window.session_emitter_state",
    PROFILE_RODATA_SECTION,
    ".lisp65_c2_kernal_window.state",
    ".lisp65_c2_vectors",
]


def configure_input_capture() -> dict[str, object]:
    """Activate only the reopened v1.6 input-fidelity file member."""
    global INPUT_CAPTURE_ENABLED, CONVERGENCE_DEFINES
    names = tuple(INPUT_CAPTURE_BUILD_CONFIGURATION["allocated"])
    if INPUT_CAPTURE_ENABLED:
        if (INPUT_CAPTURE_FEATURE not in CONVERGENCE_DEFINES
                or any(name not in KERNAL_SECTIONS for name in names)):
            raise RuntimeError("input-capture activation identity drift")
        selected = {Path(path).resolve()
                    for path in source_list(CONVERGENCE_DEFINES)}
        if (INPUT_CAPTURE_SOURCE.resolve() not in selected
                or INPUT_CAPTURE_BASE_SOURCE.resolve() in selected):
            raise RuntimeError("input-capture source membership drift")
        return {"feature": INPUT_CAPTURE_FEATURE,
                "sections": list(names),
                "source": INPUT_CAPTURE_SOURCE.relative_to(ROOT).as_posix(),
                "already_active": True}
    if INPUT_CAPTURE_FEATURE in CONVERGENCE_DEFINES:
        raise RuntimeError("input-capture feature exists without activation")
    INPUT_CAPTURE_ENABLED = True
    CONVERGENCE_DEFINES = (*CONVERGENCE_DEFINES, INPUT_CAPTURE_FEATURE)
    for name in names:
        if name in KERNAL_SECTIONS:
            raise RuntimeError(f"input-capture section already active: {name}")
        KERNAL_SECTIONS.append(name)
    selected = {Path(path).resolve()
                for path in source_list(CONVERGENCE_DEFINES)}
    if (INPUT_CAPTURE_SOURCE.resolve() not in selected
            or INPUT_CAPTURE_BASE_SOURCE.resolve() in selected):
        raise RuntimeError("input-capture file activation was not consumed")
    return {"feature": INPUT_CAPTURE_FEATURE,
            "sections": list(names),
            "source": INPUT_CAPTURE_SOURCE.relative_to(ROOT).as_posix(),
            "already_active": False}


def configure_input_hybrid() -> dict[str, object]:
    """Add the v1.6 native scalar consumer to the capture world."""
    global INPUT_HYBRID_ENABLED, CONVERGENCE_DEFINES
    section = str(INPUT_HYBRID_BUILD_CONFIGURATION["allocated"][0])
    if not INPUT_CAPTURE_ENABLED:
        raise RuntimeError("input hybrid requires configured input capture")
    if INPUT_HYBRID_ENABLED:
        if (INPUT_HYBRID_FEATURE not in CONVERGENCE_DEFINES
                or section not in KERNAL_SECTIONS):
            raise RuntimeError("input-hybrid activation identity drift")
        return {"feature": INPUT_HYBRID_FEATURE, "section": section,
                "already_active": True}
    if INPUT_HYBRID_FEATURE in CONVERGENCE_DEFINES or section in KERNAL_SECTIONS:
        raise RuntimeError("input-hybrid feature exists without activation")
    INPUT_HYBRID_ENABLED = True
    CONVERGENCE_DEFINES = (*CONVERGENCE_DEFINES, INPUT_HYBRID_FEATURE)
    KERNAL_SECTIONS.append(section)
    selected = {Path(path).resolve()
                for path in source_list(CONVERGENCE_DEFINES)}
    if INPUT_HYBRID_SOURCE.resolve() not in selected:
        raise RuntimeError("input-hybrid source membership was not consumed")
    return {"feature": INPUT_HYBRID_FEATURE, "section": section,
            "already_active": False}


def configure_refill_boundary_witness() -> dict[str, object]:
    """Select the temporary refill witness from one build authority."""
    global REFILL_WITNESS_ENABLED, CONVERGENCE_DEFINES
    if REFILL_WITNESS_ENABLED:
        if REFILL_WITNESS_FEATURE not in CONVERGENCE_DEFINES:
            raise RuntimeError("refill witness enabled without its feature")
        return refill_witness_inventory_registration()
    if REFILL_WITNESS_FEATURE in CONVERGENCE_DEFINES:
        raise RuntimeError("refill witness feature exists without activation")
    REFILL_WITNESS_ENABLED = True
    CONVERGENCE_DEFINES = (*CONVERGENCE_DEFINES, REFILL_WITNESS_FEATURE)
    selected = {Path(path).resolve()
                for path in source_list(CONVERGENCE_DEFINES)}
    if REFILL_WITNESS_SOURCE.resolve() not in selected:
        raise RuntimeError("refill witness source was bound but not consumed")
    return refill_witness_inventory_registration()


def product_cold_inventory_registration(
        definitions: tuple[str, ...] | None = None) -> dict[str, object]:
    """Project product-cold ownership from the clean-world feature."""
    selected_definitions = (tuple(CONVERGENCE_DEFINES)
                            if definitions is None else tuple(definitions))
    selected = PRODUCT_COLD_FEATURE in selected_definitions
    if definitions is None and selected != PRODUCT_COLD_ENABLED:
        raise RuntimeError("product-cold inventory/build activation disagree")
    allocated = (tuple(PRODUCT_COLD_BUILD_CONFIGURATION["allocated"])
                 if selected else ())
    relocations = tuple(f".rela{name}" for name in allocated)
    linked = {Path(path).resolve() for path in source_list(selected_definitions)}
    if (PRODUCT_COLD_SOURCE.resolve() in linked) != selected:
        raise RuntimeError("product-cold owner was not compiler-consumed")
    return {
        "feature": PRODUCT_COLD_FEATURE,
        "selected": selected,
        "source": PRODUCT_COLD_SOURCE.relative_to(ROOT).as_posix(),
        "allocated": list(allocated),
        "relocations": list(relocations),
        "names": [*allocated, *relocations],
        "cpu_start": PRODUCT_COLD_BUILD_CONFIGURATION["cpu_start"],
        "physical_start": PRODUCT_COLD_BUILD_CONFIGURATION["physical_start"],
        "capacity_bytes": PRODUCT_COLD_BUILD_CONFIGURATION["capacity_bytes"],
        "authority": "PRODUCT_COLD_BUILD_CONFIGURATION",
    }


def select_clean_product_world() -> dict[str, object]:
    """Replace temporary diagnostic freight with its product-owned tenant.

    Historical diagnostic cards remain sealed evidence.  The live acceptance
    world removes their feature at both configuration and real-consumer
    boundaries, then selects the product-owned cold disk-chain source.
    """
    global CONVERGENCE_DEFINES, REFILL_WITNESS_ENABLED
    global PRODUCT_COLD_ENABLED, single_link
    CONVERGENCE_DEFINES = tuple(
        item for item in CONVERGENCE_DEFINES
        if item != REFILL_WITNESS_FEATURE)
    REFILL_WITNESS_ENABLED = False
    while getattr(single_link, "_v160_refill_witness_consumer", False):
        single_link = single_link._v160_refill_witness_delegate
    if PRODUCT_COLD_FEATURE not in CONVERGENCE_DEFINES:
        CONVERGENCE_DEFINES = (*CONVERGENCE_DEFINES, PRODUCT_COLD_FEATURE)
    PRODUCT_COLD_ENABLED = True
    current = single_link
    if not getattr(current, "_v160_clean_product_consumer", False):
        def clean_product_single_link(*args: object, **kwargs: object) -> object:
            definitions = tuple(kwargs.get("probe_definitions", ()))
            definitions = tuple(
                item for item in definitions
                if item != REFILL_WITNESS_FEATURE)
            if PRODUCT_COLD_FEATURE not in definitions:
                definitions = (*definitions, PRODUCT_COLD_FEATURE)
            kwargs["probe_definitions"] = definitions
            return current(*args, **kwargs)

        clean_product_single_link._v160_clean_product_consumer = True  # type: ignore[attr-defined]
        clean_product_single_link._v160_clean_product_delegate = current  # type: ignore[attr-defined]
        if getattr(current, "_v160_active_frame_liveness", False):
            clean_product_single_link._v160_active_frame_liveness = True  # type: ignore[attr-defined]
            clean_product_single_link._v160_active_frame_delegate = current  # type: ignore[attr-defined]
        single_link = clean_product_single_link
    registration = product_cold_inventory_registration()
    if refill_witness_inventory_registration()["selected"]:
        raise RuntimeError("diagnostic witness survived product-world selection")
    return registration


def configure_e000_reopening() -> None:
    """Select the one owner-authorized Link-33 residency reopening."""
    global E000_REOPENING, HOST_FACADE_EXTENSION_SYMBOLS, KERNAL_SECTIONS
    E000_REOPENING = True
    HOST_FACADE_EXTENSION_SYMBOLS = ("c2_facade_runtime_overlay_exec",)
    for section in (
            ".lisp65_c2_kernal_window.reopen_gap0",
            ".lisp65_c2_kernal_window.reopen_gap1",
            ".lisp65_c2_kernal_window.reopen_gap2"):
        if section not in KERNAL_SECTIONS:
            KERNAL_SECTIONS.append(section)


def configure_bss_triage() -> None:
    """Select the one owner-authorized ordinary-BSS placement probe."""
    global BSS_TRIAGE, HOST_FACADE_EXTENSION_SYMBOLS
    if not E000_REOPENING:
        raise RuntimeError("BSS triage requires the formal E000 reopening")
    BSS_TRIAGE = True
    HOST_FACADE_EXTENSION_SYMBOLS = (
        "c2_facade_runtime_overlay_exec",
        "c2_facade_handle_normalize",
    )


def configure_append_plan_facade() -> None:
    """Select the owner-authorized C2-lite sixteenth facade vector.

    This is a current-product contract transition, not a generic vector
    allocator.  The two owned-window append callsites may reach the fixed
    resident-Island plan walker only through the one pinned seam at $B5F1.
    The following low-resident chain moves together by exactly three bytes.
    """
    global APPEND_PLAN_FACADE, HOST_FACADE_EXTENSION_SYMBOLS
    if not E000_REOPENING or not BSS_TRIAGE:
        raise RuntimeError(
            "append-plan facade requires the Link-33 reopening/BSS geometry")
    expected = (
        "c2_facade_runtime_overlay_exec",
        "c2_facade_handle_normalize",
    )
    if HOST_FACADE_EXTENSION_SYMBOLS != expected:
        raise RuntimeError("append-plan facade predecessor vector set drift")
    APPEND_PLAN_FACADE = True
    HOST_FACADE_EXTENSION_SYMBOLS = (*expected, "c2_facade_append_plan_walk")


def e000_reopening_section_names() -> tuple[str, ...]:
    """Return the complete purpose-bound reopening payload inventory."""
    return (
        ".lisp65_c2_kernal_window.reopen_gap0",
        ".lisp65_c2_kernal_window.reopen_gap1",
        ".lisp65_c2_kernal_window.reopen_gap2",
    )


def host_facade_vector_addresses() -> dict[str, int]:
    result = {
        name: HOST_FACADE_BASE + index * HOST_FACADE_STRIDE
        for index, name in enumerate(HOST_FACADE_SYMBOLS)
    }
    result.update({
        name: HOST_FACADE_EXTENSION_BASE + index * HOST_FACADE_STRIDE
        for index, name in enumerate(HOST_FACADE_EXTENSION_SYMBOLS)
    })
    return result


def host_facade_bytes() -> int:
    return ((len(HOST_FACADE_SYMBOLS) + len(HOST_FACADE_EXTENSION_SYMBOLS))
            * HOST_FACADE_STRIDE)


def fixed_bank0_contract_end() -> int:
    if BSS_TRIAGE:
        noinit_end = (FIXED_BANK0_HOT_BSS_BASE
                      + FIXED_BANK0_HOT_BSS_BYTES
                      + FIXED_BANK0_NOINIT_BYTES)
        # The inherited workbench linker script starts the first overlay at
        # ALIGN(__noinit_end + 1, 2), not directly at __noinit_end.
        return (noinit_end + 2) & ~1
    return FIXED_BANK0_CODE_BASE + FIXED_BANK0_CODE_BYTES


def fixed_bank0_headroom_bytes() -> int:
    return int(RUNTIME_VMA, 16) - fixed_bank0_contract_end()


def e000_reopening_debit(sections: dict[str, dict[str, int]]) -> int:
    """Price every byte admitted by the formal one-time reopening."""
    return (sum(sections.get(name, {}).get("bytes", 0)
                for name in e000_reopening_section_names())
            + len(HOST_FACADE_EXTENSION_SYMBOLS) * HOST_FACADE_STRIDE)


def kernal_header_values(crc: int, sha256: str) -> bytes:
    return (
        "/* generated from the integrated C2 product window */\n"
        "#ifndef LISP65_C2_KERNAL_WINDOW_GENERATED_H\n"
        "#define LISP65_C2_KERNAL_WINDOW_GENERATED_H\n"
        f"#define C2_KERNAL_WINDOW_STAGE_PHYSICAL 0x{KERNAL_WINDOW_STAGE:08x}UL\n"
        f"#define C2_KERNAL_WINDOW_CPU_BASE 0x{KERNAL_WINDOW_BASE:04x}UL\n"
        f"#define C2_KERNAL_WINDOW_BYTES {KERNAL_WINDOW_BYTES}u\n"
        f"#define C2_KERNAL_WINDOW_CRC16 0x{crc:04x}u\n"
        f"#define C2_KERNAL_WINDOW_SHA256 \"{sha256}\"\n"
        "#endif\n"
    ).encode("ascii")


def kernal_header(data: bytes) -> bytes:
    return kernal_header_values(crc16(data), hashlib.sha256(data).hexdigest())


def kernal_window_identity_pin() -> dict[str, object]:
    contract = json.loads(KERNAL_CONTRACT.read_text(encoding="utf-8"))
    pin = contract.get("product_window_identity")
    if not isinstance(pin, dict) or pin.get("bytes") != KERNAL_WINDOW_BYTES:
        raise RuntimeError("C2 KERNAL window identity pin is absent or malformed")
    if not re.fullmatch(r"[0-9a-f]{64}", str(pin.get("sha256", ""))):
        raise RuntimeError("C2 KERNAL window identity SHA-256 is malformed")
    crc = pin.get("crc16")
    if not isinstance(crc, str) or not re.fullmatch(r"0x[0-9a-f]{4}", crc):
        raise RuntimeError("C2 KERNAL window identity CRC-16 is malformed")
    return pin


def verify_kernal_window_pin_source(out: Path,
                                    pin: dict[str, object]) -> dict[str, object]:
    source = ROOT / str(pin["source_elf"])
    if (not source.exists() or
            hashlib.sha256(source.read_bytes()).hexdigest()
            != pin["source_elf_sha256"]):
        raise RuntimeError("C2 KERNAL window identity source ELF is unavailable or changed")
    temporary = out / "c2-kernal-window-pin-source.tmp.bin"
    command = [str(TOOLCHAIN / "llvm-objcopy"), "-O", "binary", "--gap-fill=0"]
    command.extend(f"--only-section={section}" for section in KERNAL_SECTIONS)
    command.extend([str(source), str(temporary)])
    run(command)
    data = temporary.read_bytes()
    temporary.unlink()
    actual_sha = hashlib.sha256(data).hexdigest()
    actual_crc = crc16(data)
    if (len(data) != pin["bytes"] or actual_sha != pin["sha256"] or
            actual_crc != int(str(pin["crc16"]), 16)):
        raise RuntimeError("C2 KERNAL window identity pin does not match its source ELF")
    return {
        "source_elf": str(source.relative_to(ROOT)),
        "source_elf_sha256": pin["source_elf_sha256"],
        "bytes": len(data),
        "crc16": f"0x{actual_crc:04x}",
        "sha256": actual_sha,
        "status": "verified",
    }


def extract_pinned_kernal_window(out: Path, target: Path,
                                 pin: dict[str, object]) -> Path:
    image = out / "c2-product-kernal-window.bin"
    temporary = out / "c2-product-kernal-window.tmp.bin"
    command = [str(TOOLCHAIN / "llvm-objcopy"), "-O", "binary", "--gap-fill=0"]
    command.extend(f"--only-section={section}" for section in KERNAL_SECTIONS)
    command.extend([str(target) + ".elf", str(temporary)])
    run(command)
    data = temporary.read_bytes()
    if len(data) != KERNAL_WINDOW_BYTES:
        raise RuntimeError(
            f"C2 KERNAL window is {len(data)} bytes, expected {KERNAL_WINDOW_BYTES}")
    expected_sha = str(pin["sha256"])
    expected_crc = int(str(pin["crc16"]), 16)
    actual_sha = hashlib.sha256(data).hexdigest()
    actual_crc = crc16(data)
    if actual_sha != expected_sha or actual_crc != expected_crc:
        raise RuntimeError(
            "C2 KERNAL window drift against the pre-link identity pin: "
            f"sha={actual_sha} crc=0x{actual_crc:04x}")
    expected_header = kernal_header_values(expected_crc, expected_sha)
    header = out / "c2-kernal-window.generated.h"
    if not header.exists() or header.read_bytes() != expected_header:
        raise RuntimeError("C2 KERNAL window pre-link identity-header drift")
    write(image, data)
    temporary.unlink()
    return image


def _prg_file_offset(image: bytes, address: int, size: int) -> int:
    if len(image) < 2:
        raise RuntimeError("product PRG lacks its load address")
    load_address = image[0] | (image[1] << 8)
    file_offset = 2 + address - load_address
    if file_offset < 2 or file_offset + size > len(image):
        raise RuntimeError(
            f"publish-last address 0x{address:04x}+{size} lies outside product PRG")
    return file_offset


def _machine_instruction_records(lines: list[str]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for line in lines:
        match = re.match(
            r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s+)+)"
            r"([a-z][a-z0-9]*)\s*(.*?)\s*$", line)
        if not match:
            continue
        operand = match.group(4).split(";", 1)[0].strip()
        records.append({
            "address": int(match.group(1), 16),
            "encoding": bytes.fromhex(match.group(2)),
            "mnemonic": match.group(3),
            "operand": operand,
        })
    return records


def _jsr_targets_address(record: dict[str, object], address: int) -> bool:
    """Bind a JSR to its encoded target, never objdump's display label.

    LLVM may render an address using a nearby linker symbol rather than the
    exact local callee name.  The machine operand and the ELF symbol value are
    the contract; the pretty-printed operand is deliberately irrelevant.
    """
    encoding = bytes(record["encoding"])
    return (
        record["mnemonic"] == "jsr"
        and len(encoding) == 3
        and encoding[0] == 0x20
        and (encoding[1] | (encoding[2] << 8)) == address
    )


def _kernal_crc_call_binding_model_selftest() -> dict[str, str]:
    target = 0xA12B
    base = {
        "address": 0xB4F0,
        "encoding": bytes((0x20, 0x2B, 0xA1)),
        "mnemonic": "jsr",
        "operand": "$a12b <an_unrelated_rendered_symbol+0x250f>",
    }
    cases = {
        "encoded-target-with-unrelated-display-label": (
            base, True),
        "display-name-with-wrong-encoded-target": ({
            **base,
            "encoding": bytes((0x20, 0x2C, 0xA1)),
            "operand": "$a12b <c2k_crc16>",
        }, False),
        "non-jsr-with-matching-bytes": ({**base, "mnemonic": "jmp"}, False),
        "truncated-jsr": ({**base, "encoding": bytes((0x20, 0x2B))}, False),
    }
    result: dict[str, str] = {}
    for name, (record, expected) in cases.items():
        observed = _jsr_targets_address(record, target)
        if observed != expected:
            raise RuntimeError(
                f"KERNAL CRC call binding mutation survived: {name}")
        result[name] = "passed" if observed else "rejected"
    return result


def _kernal_crc_binding_locations(elf: Path) -> dict[str, int]:
    disassembly = run([
        str(TOOLCHAIN / "llvm-objdump"), "-d",
        "--disassemble-symbols=c2_kernal_take_ownership", str(elf)
    ], capture=True)
    nodes, _section_lines = _sectioned_disassembly(disassembly)
    ownership = [row for row in nodes.values()
                 if "c2_kernal_take_ownership" in row["names"]]
    if len(ownership) != 1:
        raise RuntimeError("KERNAL CRC binding ownership function is not unique")
    records = _machine_instruction_records(ownership[0]["lines"])
    symbols = defined_symbols(elf)
    crc16_address = symbols.get("c2k_crc16")
    if crc16_address is None:
        raise RuntimeError("KERNAL CRC binding callee c2k_crc16 is absent")
    candidates: list[tuple[dict[str, object], dict[str, object]]] = []
    for call_index in range(len(records) - 4):
        call = records[call_index]
        if not _jsr_targets_address(call, crc16_address):
            continue
        first = records[call_index + 1]
        branch_a = records[call_index + 2]
        if not (
            first["mnemonic"] == "cpx"
            and branch_a["mnemonic"] == "bne"
            and first["encoding"][0] == 0xE0
            and len(first["encoding"]) == 2
            and re.fullmatch(r"#\$[0-9a-f]{1,2}", str(first["operand"]))
        ):
            continue
        # llvm-mos may normalize the C boolean result register between the
        # high- and low-byte comparisons.  Bind the two immediate operands
        # to the unique c2k_crc16 call rather than requiring adjacency.
        for second_index in range(call_index + 3,
                                  min(call_index + 6, len(records) - 1)):
            second = records[second_index]
            branch_b = records[second_index + 1]
            middle = records[call_index + 3:second_index]
            if (
                second["mnemonic"] == "cmp"
                and branch_b["mnemonic"] == "bne"
                and second["encoding"][0] == 0xC9
                and len(second["encoding"]) == 2
                and re.fullmatch(
                    r"#\$[0-9a-f]{1,2}", str(second["operand"]))
                and all(
                    row["mnemonic"] in {"lda", "ldx", "ldy"}
                    and re.fullmatch(
                        r"#\$[0-9a-f]{1,2}", str(row["operand"]))
                    for row in middle
                )
            ):
                candidates.append((first, second))
    if len(candidates) != 1:
        raise RuntimeError(
            f"KERNAL CRC binding compare sequence count is {len(candidates)}, expected 1")
    high, low = candidates[0]
    result = {
        "high_address": int(high["address"]) + 1,
        "low_address": int(low["address"]) + 1,
        "compiled_crc16": (high["encoding"][1] << 8) | low["encoding"][1],
    }
    if (result["high_address"] != KERNAL_CRC_BINDING_HIGH_ADDRESS
            or result["low_address"] != KERNAL_CRC_BINDING_LOW_ADDRESS):
        raise RuntimeError(f"KERNAL CRC binding address drift: {result}")
    sections = section_table(elf)
    handoff = sections.get(".lisp65_c2_kernal_handoff")
    if not handoff:
        raise RuntimeError("KERNAL CRC binding handoff section is absent")
    handoff_end = handoff["address"] + handoff["bytes"]
    if not all(handoff["address"] <= result[key] < handoff_end
               for key in ("high_address", "low_address")):
        raise RuntimeError("KERNAL CRC binding operands escaped the handoff section")
    return result


def _publish_last_domain_errors(
        before: bytes, after: bytes,
        domains: list[dict[str, object]]) -> list[str]:
    errors: list[str] = []
    if len(before) != len(after):
        return ["product-size-changed-after-link"]
    allowed: set[int] = set()
    for domain in domains:
        offset = int(domain["file_offset"])
        expected = bytes(domain["expected"])
        span = set(range(offset, offset + len(expected)))
        if allowed & span:
            errors.append("publish-last-domains-overlap")
        allowed |= span
        if after[offset:offset + len(expected)] != expected:
            errors.append(f"binding-content-mismatch:{domain['name']}")
    changed = {index for index, (old, new) in enumerate(zip(before, after))
               if old != new}
    if changed - allowed:
        errors.append("post-link-change-outside-declared-domain")
    return errors


def publish_kernal_window_binding(out: Path, target: Path) -> dict[str, object]:
    """Bind the sole product link's window through two post-link operands."""
    elf = Path(str(target) + ".elf")
    original = target.read_bytes()
    unbound = out / "lisp65-c2-substitution-unbound.prg"
    if unbound.exists():
        raise RuntimeError("publish-last unbound product already exists")
    write(unbound, original)

    extract_provisional_kernal_window(out, target)
    window = out / "c2-product-kernal-window.bin"
    window_data = window.read_bytes()
    window_crc = crc16(window_data)
    window_sha = hashlib.sha256(window_data).hexdigest()
    binding = _kernal_crc_binding_locations(elf)
    high_offset = _prg_file_offset(
        original, int(binding["high_address"]), 1)
    low_offset = _prg_file_offset(original, int(binding["low_address"]), 1)
    compiled = int(binding["compiled_crc16"])
    if (original[high_offset] != compiled >> 8
            or original[low_offset] != compiled & 0xFF):
        raise RuntimeError("compiled KERNAL CRC operands differ from disassembly")

    patched = bytearray(original)
    patched[high_offset] = window_crc >> 8
    patched[low_offset] = window_crc & 0xFF
    domains = [
        {"name": "kernal-window-crc-high",
         "file_offset": high_offset, "expected": bytes([window_crc >> 8])},
        {"name": "kernal-window-crc-low",
         "file_offset": low_offset, "expected": bytes([window_crc & 0xFF])},
    ]
    if errors := _publish_last_domain_errors(original, bytes(patched), domains):
        raise RuntimeError(f"KERNAL publish-last range red: {errors}")

    outside = bytearray(patched)
    outside_offset = next(index for index in range(2, len(outside))
                          if index not in {high_offset, low_offset})
    outside[outside_offset] ^= 0x01
    if "post-link-change-outside-declared-domain" not in _publish_last_domain_errors(
            original, bytes(outside), domains):
        raise AssertionError("out-of-domain post-link mutation was accepted")
    wrong_crc = bytearray(patched)
    wrong_crc[high_offset] ^= 0x01
    if not any(error.startswith("binding-content-mismatch:")
               for error in _publish_last_domain_errors(
                   original, bytes(wrong_crc), domains)):
        raise AssertionError("mutated KERNAL CRC binding was accepted")

    write(target, bytes(patched))
    header = out / "c2-kernal-window.generated.h"
    prior_header_sha = hashlib.sha256(header.read_bytes()).hexdigest()
    write(header, kernal_header_values(window_crc, window_sha))
    changed = [index for index, (old, new) in enumerate(zip(original, patched))
               if old != new]
    report = {
        "format": "lisp65-c2-kernal-window-publish-last-v1",
        "status": "passed",
        "single_product_link_window": {
            "path": str(window.relative_to(ROOT)),
            "bytes": len(window_data),
            "crc16": f"0x{window_crc:04x}",
            "sha256": window_sha,
        },
        "binding_operands": [
            {"name": "kernal-window-crc-high",
             "address": int(binding["high_address"]),
             "file_offset": high_offset, "bytes": 1,
             "compiled_value": compiled >> 8,
             "published_value": window_crc >> 8},
            {"name": "kernal-window-crc-low",
             "address": int(binding["low_address"]),
             "file_offset": low_offset, "bytes": 1,
             "compiled_value": compiled & 0xFF,
             "published_value": window_crc & 0xFF},
        ],
        "declared_mutation_domain_bytes": KERNAL_CRC_BINDING_BYTES,
        "actual_changed_bytes": len(changed),
        "changed_file_offsets": changed,
        "changed_range_confined": True,
        "unbound_product_sha256": hashlib.sha256(original).hexdigest(),
        "window_bound_product_sha256": hashlib.sha256(bytes(patched)).hexdigest(),
        "generated_header_prior_sha256": prior_header_sha,
        "generated_header_bound_sha256": hashlib.sha256(header.read_bytes()).hexdigest(),
        "negative_matrix": {
            "mutation-outside-two-byte-domain": "rejected",
            "mutated-published-crc": "rejected",
        },
        "claim_limit": (
            "Publish-last identity binding over one already-linked product. "
            "No compiler, linker, hardware, promotion or release claim."),
    }
    write(out / "kernal-window-publish-last.json",
          json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def extract_provisional_kernal_window(out: Path, target: Path) -> dict[str, object]:
    """Extract one probe window without pretending it matches the old pin."""
    image = out / "c2-product-kernal-window.bin"
    temporary = out / "c2-product-kernal-window.tmp.bin"
    command = [str(TOOLCHAIN / "llvm-objcopy"), "-O", "binary", "--gap-fill=0"]
    command.extend(f"--only-section={section}" for section in KERNAL_SECTIONS)
    command.extend([str(target) + ".elf", str(temporary)])
    run(command)
    data = temporary.read_bytes()
    temporary.unlink()
    if len(data) != KERNAL_WINDOW_BYTES:
        raise RuntimeError(
            f"provisional C2 KERNAL window is {len(data)} bytes, "
            f"expected {KERNAL_WINDOW_BYTES}")
    write(image, data)
    return {
        "path": str(image.relative_to(ROOT)),
        "bytes": len(data),
        "crc16": f"0x{crc16(data):04x}",
        "sha256": hashlib.sha256(data).hexdigest(),
        "identity_status": "provisional-unpinned-hardware-prohibited",
    }


def replace_region(text: str, start: str, end: str, replacement: str) -> str:
    first = text.index(start)
    last = text.index(end, first)
    return text[:first] + replacement + text[last:]


def linker_script(*, ownership_opt_in: bool = False) -> str:
    text = (ROOT / "scripts/lisp65-mega65-workbench-overlay.ld").read_text(
        encoding="utf-8"
    )
    ownership_selected = ownership_opt_in or FULL_MAP_OWNERSHIP
    ownership: dict[str, object] | None = None
    if ownership_selected:
        contract = json.loads(OWNERSHIP_CONTRACT.read_text(encoding="utf-8"))
        ownership = contract["mapped_far_service"]
        geometry = contract["geometry"]
        overlay_floor = int(geometry["overlay_floor"], 0)
        old_floor = (
            "__lisp65_workbench_overlay_min_start = "
            "ALIGN(__lisp65_workbench_noinit_end + 1, 2);")
        if text.count(old_floor) != 1:
            raise RuntimeError("derived overlay-floor template drift")
        text = text.replace(
            old_floor,
            f"__lisp65_workbench_overlay_min_start = 0x{overlay_floor:04x};",
            1)
    overlay_start = "    OVERLAY __lisp65_workbench_runtime_overlay_vma : NOCROSSREFS {"
    overlay_end = "    } >ram\n} INSERT AFTER .noinit;"
    sections = [
        "        .lisp65_workbench_overlay { KEEP(*(.lisp65_boot .lisp65_boot.*)) }",
        "        .lisp65_rt_rtov_catalog { KEEP(*(.lisp65_rt_rtov_catalog)) }",
        "        .lisp65_rt_rtov_record { KEEP(*(.lisp65_rt_rtov_record)) }",
    ]
    if BANK3_STAGING_SLICES:
        sections.insert(1,
            "        .lisp65_boot_bank3_stage { KEEP(*(.lisp65_boot_bank3_stage_prefix)) KEEP(*(.lisp65_boot_bank3_stage)) }")
    sections.extend(
        f"        .lisp65_rt_c2d_{name} {{ KEEP(*(.lisp65_rt_c2d_{name})) }}"
        for name, _entry in C2_DECODER_SLICES
    )
    if BANK3_STAGING_SLICES:
        sections.append(
            "        .lisp65_rt_bank3_stage_session { KEEP(*(.lisp65_rt_bank3_stage_session)) }")
    sections.extend(
        f"        .lisp65_rt_c2emit_{name} {{ KEEP(*(.lisp65_rt_c2emit_{name})) }}"
        for name, _entry in C2_EMITTER_SLICES
    )
    sections.extend(
        f"        .lisp65_rt_c2append_{name} {{ KEEP(*(.lisp65_rt_c2append_{name})) }}"
        for name, _entry in C2_APPEND_SLICES
    )
    sections.extend([
        "        .lisp65_rt_l65e { KEEP(*(.lisp65_rt_l65e)) KEEP(*(.lisp65_rt_l65e_data)) }",
        "        .lisp65_rt_island_00 { KEEP(*(.lisp65_rt_island_00)) KEEP(*(.lisp65_rt_island_00_data)) }",
        "        .lisp65_rt_buffer_read { KEEP(*(.lisp65_rt_buffer_read)) }",
        "        .lisp65_rt_buffer_write { KEEP(*(.lisp65_rt_buffer_write)) }",
        "        .lisp65_rt_buffer_alloc { KEEP(*(.lisp65_rt_buffer_alloc)) }",
    ])
    if INTERN_SESSION_SERVICE:
        sections.append(
            "        .lisp65_rt_intern_service { KEEP(*(.lisp65_rt_intern_service)) }")
    new_overlay = (
        "    OVERLAY __lisp65_workbench_runtime_overlay_vma : NOCROSSREFS "
        "AT(ORIGIN(c2_runtime_load)) {\n"
        + "\n".join(sections) + "\n"
    )
    text = replace_region(text, overlay_start, overlay_end, new_overlay)
    final_runtime_section = (
        ".lisp65_rt_intern_service"
        if INTERN_SESSION_SERVICE else ".lisp65_rt_buffer_alloc")
    text = re.sub(
        r"__lisp65_resident_island_seed_lma =\n\s+ALIGN\(LOADADDR\(\.lisp65_rt_c1_compiler\) \+ SIZEOF\(\.lisp65_rt_c1_compiler\), 0x100\);",
        "__lisp65_resident_island_seed_lma =\n"
        f"    ALIGN(LOADADDR({final_runtime_section}) + "
        f"SIZEOF({final_runtime_section}), 0x100);",
        text,
    )
    symbol_start = "__lisp65_rt_rtov_catalog_start ="
    symbol_end = "__lisp65_resident_island_start ="
    symbols = [
        "__lisp65_rt_rtov_catalog_start = ADDR(.lisp65_rt_rtov_catalog); __lisp65_rt_rtov_catalog_end = ADDR(.lisp65_rt_rtov_catalog) + SIZEOF(.lisp65_rt_rtov_catalog);",
        "__lisp65_rt_rtov_record_start = ADDR(.lisp65_rt_rtov_record); __lisp65_rt_rtov_record_end = ADDR(.lisp65_rt_rtov_record) + SIZEOF(.lisp65_rt_rtov_record);",
    ]
    if BANK3_STAGING_SLICES:
        symbols[0:0] = [
            "__lisp65_workbench_overlay_len = SIZEOF(.lisp65_workbench_overlay);",
            "__lisp65_boot_bank3_stage_start = ADDR(.lisp65_boot_bank3_stage); __lisp65_boot_bank3_stage_end = ADDR(.lisp65_boot_bank3_stage) + SIZEOF(.lisp65_boot_bank3_stage);",
            "__lisp65_rt_bank3_stage_session_start = ADDR(.lisp65_rt_bank3_stage_session); __lisp65_rt_bank3_stage_session_end = ADDR(.lisp65_rt_bank3_stage_session) + SIZEOF(.lisp65_rt_bank3_stage_session);",
        ]
    symbols.extend(
        f"__lisp65_rt_c2d_{name}_start = ADDR(.lisp65_rt_c2d_{name}); __lisp65_rt_c2d_{name}_end = ADDR(.lisp65_rt_c2d_{name}) + SIZEOF(.lisp65_rt_c2d_{name});"
        for name, _entry in C2_DECODER_SLICES
    )
    symbols.extend(
        f"__lisp65_rt_c2emit_{name}_start = ADDR(.lisp65_rt_c2emit_{name}); __lisp65_rt_c2emit_{name}_end = ADDR(.lisp65_rt_c2emit_{name}) + SIZEOF(.lisp65_rt_c2emit_{name});"
        for name, _entry in C2_EMITTER_SLICES
    )
    symbols.extend(
        f"__lisp65_rt_c2append_{name}_start = ADDR(.lisp65_rt_c2append_{name}); __lisp65_rt_c2append_{name}_end = ADDR(.lisp65_rt_c2append_{name}) + SIZEOF(.lisp65_rt_c2append_{name});"
        for name, _entry in C2_APPEND_SLICES
    )
    symbols.extend([
        "__lisp65_rt_l65e_start = ADDR(.lisp65_rt_l65e); __lisp65_rt_l65e_end = ADDR(.lisp65_rt_l65e) + SIZEOF(.lisp65_rt_l65e);",
        "__lisp65_rt_buffer_read_start = ADDR(.lisp65_rt_buffer_read); __lisp65_rt_buffer_read_end = ADDR(.lisp65_rt_buffer_read) + SIZEOF(.lisp65_rt_buffer_read);",
        "__lisp65_rt_buffer_write_start = ADDR(.lisp65_rt_buffer_write); __lisp65_rt_buffer_write_end = ADDR(.lisp65_rt_buffer_write) + SIZEOF(.lisp65_rt_buffer_write);",
        "__lisp65_rt_buffer_alloc_start = ADDR(.lisp65_rt_buffer_alloc); __lisp65_rt_buffer_alloc_end = ADDR(.lisp65_rt_buffer_alloc) + SIZEOF(.lisp65_rt_buffer_alloc);",
    ])
    if INTERN_SESSION_SERVICE:
        symbols.append(
            "__lisp65_rt_intern_service_start = ADDR(.lisp65_rt_intern_service); "
            "__lisp65_rt_intern_service_end = ADDR(.lisp65_rt_intern_service) + "
            "SIZEOF(.lisp65_rt_intern_service);")
    text = replace_region(text, symbol_start, symbol_end, "\n".join(symbols) + "\n")
    entry_start = "__lisp65_rt_rtov_catalog_entry ="
    entry_end = "__lisp65_rt_island_00_entry ="
    entries = [
        "__lisp65_rt_rtov_catalog_entry = vm_runtime_overlay_catalog_verifier;",
        "__lisp65_rt_rtov_record_entry = vm_runtime_overlay_record_verifier;",
    ]
    if BANK3_STAGING_SLICES:
        entries[0:0] = [
            "__lisp65_boot_bank3_stage_entry = vm_bank3_boot_stage_entry;",
            "__lisp65_rt_bank3_stage_session_entry = c2_lite_stage_session_family;",
        ]
    entries.extend(
        f"__lisp65_rt_c2d_{name}_entry = {entry};"
        for name, entry in C2_DECODER_SLICES
    )
    entries.extend(
        f"__lisp65_rt_c2emit_{name}_entry = {entry};"
        for name, entry in C2_EMITTER_SLICES
    )
    entries.extend(
        f"__lisp65_rt_c2append_{name}_entry = {entry};"
        for name, entry in C2_APPEND_SLICES
    )
    entries.extend([
        "__lisp65_rt_l65e_entry = lisp65_error_overlay_entry;",
        "__lisp65_rt_buffer_read_entry = lisp65_buffer_overlay_read_entry;",
        "__lisp65_rt_buffer_write_entry = lisp65_buffer_overlay_write_entry;",
        "__lisp65_rt_buffer_alloc_entry = lisp65_buffer_overlay_alloc_entry;",
    ])
    if INTERN_SESSION_SERVICE:
        entries.append(
            "__lisp65_rt_intern_service_entry = lisp65_intern_service_entry;")
    text = replace_region(text, entry_start, entry_end, "\n".join(entries) + "\n")
    assert_start = "ASSERT(SIZEOF(.lisp65_rt_rtov_catalog)"
    assert_end = "ASSERT(SIZEOF(.lisp65_rt_island_00)"
    assertions = [
        "ASSERT(SIZEOF(.lisp65_rt_rtov_catalog) > 0 && SIZEOF(.lisp65_rt_rtov_catalog) <= 1792 && __lisp65_rt_rtov_catalog_end <= __lisp65_workbench_runtime_overlay_limit, \"runtime overlay catalog verifier exceeds its stack-safe window\");",
        "ASSERT(SIZEOF(.lisp65_rt_rtov_record) > 0 && SIZEOF(.lisp65_rt_rtov_record) <= 1792 && __lisp65_rt_rtov_record_end <= __lisp65_workbench_runtime_overlay_limit, \"runtime overlay record verifier exceeds its stack-safe window\");",
    ]
    if BANK3_STAGING_SLICES:
        assertions[0:0] = [
            "ASSERT(SIZEOF(.lisp65_boot_bank3_stage) > 0 && SIZEOF(.lisp65_boot_bank3_stage) <= 1792 && __lisp65_boot_bank3_stage_end <= __lisp65_workbench_runtime_overlay_limit, \"Bank-3 pre-family stage record exceeds its stack-safe window\");",
            "ASSERT(__lisp65_boot_bank3_stage_entry >= __lisp65_boot_bank3_stage_start + 18 && __lisp65_boot_bank3_stage_entry < __lisp65_boot_bank3_stage_end, \"Bank-3 pre-family stage entry escaped its descriptor-safe record body\");",
            "ASSERT(SIZEOF(.lisp65_rt_bank3_stage_session) > 0 && SIZEOF(.lisp65_rt_bank3_stage_session) <= 1792 && __lisp65_rt_bank3_stage_session_end <= __lisp65_workbench_runtime_overlay_limit, \"Bank-3 Session stage slice exceeds its stack-safe window\");",
            "ASSERT(__lisp65_rt_bank3_stage_session_entry >= __lisp65_rt_bank3_stage_session_start && __lisp65_rt_bank3_stage_session_entry < __lisp65_rt_bank3_stage_session_end, \"Bank-3 Session stage entry escaped its slice\");",
        ]
    assertions.extend(
        f"ASSERT(SIZEOF(.lisp65_rt_c2d_{name}) > 0 && SIZEOF(.lisp65_rt_c2d_{name}) <= 1792 && __lisp65_rt_c2d_{name}_end <= __lisp65_workbench_runtime_overlay_limit, \"C2 decoder phase {name} exceeds its stack-safe window\");"
        for name, _entry in C2_DECODER_SLICES
    )
    assertions.extend(
        f"ASSERT(SIZEOF(.lisp65_rt_c2emit_{name}) > 0 && SIZEOF(.lisp65_rt_c2emit_{name}) <= 1792 && __lisp65_rt_c2emit_{name}_end <= __lisp65_workbench_runtime_overlay_limit, \"C2 emitter phase {name} exceeds its stack-safe window\");"
        for name, _entry in C2_EMITTER_SLICES
    )
    assertions.extend(
        f"ASSERT(SIZEOF(.lisp65_rt_c2append_{name}) > 0 && SIZEOF(.lisp65_rt_c2append_{name}) <= 1792 && __lisp65_rt_c2append_{name}_end <= __lisp65_workbench_runtime_overlay_limit, \"C2 append phase {name} exceeds its stack-safe window\");"
        for name, _entry in C2_APPEND_SLICES
    )
    assertions.extend([
        "ASSERT(SIZEOF(.lisp65_rt_l65e) > 0 && SIZEOF(.lisp65_rt_l65e) <= 1792 && __lisp65_rt_l65e_end <= __lisp65_workbench_runtime_overlay_limit, \"L65E renderer exceeds its stack-safe window\");",
        "ASSERT(SIZEOF(.lisp65_rt_l65e) <= __lisp65_error_overlay_max_bytes, \"L65E renderer exceeds its product budget\");",
        "ASSERT(SIZEOF(.lisp65_rt_buffer_read) > 0 && SIZEOF(.lisp65_rt_buffer_read) <= 1792 && __lisp65_rt_buffer_read_end <= __lisp65_workbench_runtime_overlay_limit, \"buffer reader exceeds its stack-safe window\");",
        "ASSERT(SIZEOF(.lisp65_rt_buffer_write) > 0 && SIZEOF(.lisp65_rt_buffer_write) <= 1792 && __lisp65_rt_buffer_write_end <= __lisp65_workbench_runtime_overlay_limit, \"buffer writer exceeds its stack-safe window\");",
        "ASSERT(SIZEOF(.lisp65_rt_buffer_alloc) > 0 && SIZEOF(.lisp65_rt_buffer_alloc) <= 1792 && __lisp65_rt_buffer_alloc_end <= __lisp65_workbench_runtime_overlay_limit, \"buffer allocator exceeds its stack-safe window\");",
    ])
    if INTERN_SESSION_SERVICE:
        assertions.append(
            "ASSERT(SIZEOF(.lisp65_rt_intern_service) > 0 && "
            "SIZEOF(.lisp65_rt_intern_service) <= 1792 && "
            "__lisp65_rt_intern_service_end <= "
            "__lisp65_workbench_runtime_overlay_limit, "
            "\"intern Session service exceeds its stack-safe window\");")
    text = replace_region(text, assert_start, assert_end, "\n".join(assertions) + "\n")
    memory_layout = (
        "MEMORY {\n"
        f"    c2_runtime_load (!rwx) : ORIGIN = 0x{RUNTIME_LOAD_BASE:06x}, "
        f"LENGTH = 0x{RUNTIME_LOAD_BYTES:06x}\n"
        "    c2_kernal_window (!rwx) : ORIGIN = 0xe000, LENGTH = 0x2000\n"
        f"    c2_kernal_window_load (!rwx) : ORIGIN = 0x{KERNAL_WINDOW_LOAD_BASE:06x}, "
        "LENGTH = 0x002000\n"
        "}\n\n"
    )
    binding_bytes = runtime_binding_bytes()
    stage_assert = ""
    if FAMILY_STAGE_BINDINGS:
        stage_assert = f"""
ASSERT(__lisp65_rtov_family_stage_bindings_start ==
           __lisp65_rtov_binding_section_start + {VERIFIER_BINDING_BYTES} &&
       rtov_family_stage_bindings ==
           __lisp65_rtov_family_stage_bindings_start &&
       __lisp65_rtov_family_stage_bindings_end ==
           __lisp65_rtov_binding_section_end,
       \"runtime-family stage binding order or labels drifted\");
"""
    binding_layout = f"""/* Four verifier tuples retain their historical
 * 32-byte prefix.  C2-lite Bank-3 staging appends two size/CRC tuples in the
 * same non-LTO publish-last section without renumbering the verifier ABI. */
SECTIONS {{
    .lisp65_runtime_overlay_verifier_bindings : {{
        __lisp65_rtov_binding_section_start = .;
        KEEP(*(.lisp65_runtime_overlay_verifier_bindings))
        __lisp65_rtov_binding_section_end = .;
    }} >ram
}} INSERT AFTER .rodata;

ASSERT(SIZEOF(.lisp65_runtime_overlay_verifier_bindings) == {binding_bytes} &&
       __lisp65_rtov_binding_section_end -
       __lisp65_rtov_binding_section_start == {binding_bytes},
       "runtime-overlay publish-last binding table has the wrong width");
ASSERT(__lisp65_rtov_verifier_bindings_start ==
           __lisp65_rtov_binding_section_start &&
       rtov_boot_verifiers == __lisp65_rtov_binding_section_start &&
       rtov_verifiers == __lisp65_rtov_binding_section_start + 16 &&
       __lisp65_rtov_verifier_bindings_end ==
           __lisp65_rtov_binding_section_start + {VERIFIER_BINDING_BYTES},
       "runtime-overlay verifier tuple order or labels drifted");
{stage_assert}"""
    kernal_layout = r"""/* Product-resident handoff code is ordinary PRG material.  Name it here so
 * neither fixed-VMA artifact can capture an orphan section. */
SECTIONS {
    .lisp65_c2_kernal_handoff 0xb4a3 : {
        KEEP(*(.lisp65_c2_kernal_handoff))
    } >ram
    .lisp65_c2_host_facade 0xb5c4 : {
        KEEP(*(.lisp65_c2_host_facade))
    } >ram
    .lisp65_c2_kernal_io_reveal 0xb5eb : {
        KEEP(*(.lisp65_c2_kernal_io_reveal))
    } >ram
    .lisp65_c2_kernal_map_switch 0xb5f6 : {
        KEEP(*(.lisp65_c2_kernal_map_switch))
    } >ram
    .lisp65_c2_kernal_state 0xb602 (NOLOAD) : {
        KEEP(*(.lisp65_c2_kernal_state))
    } >ram
} INSERT AFTER .text;

/* Every state cell referenced by the owned window has a declared address.
 * These are storage contracts, not ordinary whole-program allocation. */
SECTIONS {
    .lisp65_c2_fixed_zp 0x89 (NOLOAD) : {
        __lisp65_c2_fixed_zp_phase_owner = .;
        KEEP(*(.lisp65_c2_fixed_zp.phase_owner))
        __lisp65_c2_fixed_zp_pending_roots = .;
        KEEP(*(.lisp65_c2_fixed_zp.pending_roots))
        __lisp65_c2_fixed_zp_ready = .;
        KEEP(*(.lisp65_c2_fixed_zp.ready))
        __lisp65_c2_fixed_zp_str_building = .;
        KEEP(*(.lisp65_c2_fixed_zp.str_building))
        __lisp65_c2_fixed_zp_mem_oom = .;
        KEEP(*(.lisp65_c2_fixed_zp.mem_oom))
    } >zp
} INSERT AFTER .zp;

SECTIONS {
    .lisp65_c2_fixed_bank0 0xc080 (NOLOAD) : {
        __lisp65_c2_fixed_bank0_committed_roots = .;
        KEEP(*(.lisp65_c2_fixed_bank0.committed_roots))
        __lisp65_c2_fixed_bank0_decode_active = .;
        KEEP(*(.lisp65_c2_fixed_bank0.decode_active))
        __lisp65_c2_fixed_bank0_runtime = .;
        KEEP(*(.lisp65_c2_fixed_bank0.runtime))
        __lisp65_c2_fixed_bank0_edma_job = .;
        KEEP(*(.lisp65_c2_fixed_bank0.edma_job))
        __lisp65_c2_fixed_bank0_phase_scratch = .;
        KEEP(*(.lisp65_c2_fixed_bank0.phase_scratch))
        __lisp65_c2_fixed_bank0_sym_name_scratch = .;
        KEEP(*(.lisp65_c2_fixed_bank0.sym_name_scratch))
    } >ram
    .lisp65_c2_fixed_bank0_code 0xc218 : {
        __lisp65_c2_fixed_bank0_code_start = .;
        __lisp65_c2_fixed_bank0_code_kb_cursor_off = .;
        KEEP(*(.lisp65_c2_fixed_bank0_code.kb_cursor_off))
        __lisp65_c2_fixed_bank0_code_c2e_cons = .;
        KEEP(*(.lisp65_c2_fixed_bank0_code.c2e_cons))
        __lisp65_c2_fixed_bank0_code_rtov_fail = .;
        KEEP(*(.lisp65_c2_fixed_bank0_code.rtov_fail))
        __lisp65_c2_fixed_bank0_code_end = .;
    } >ram
} INSERT AFTER .bss;

/* The owned CPU window has its own load-image counter.  Preserve VMA-relative
 * holes in the LMA so objcopy emits one exact 8-KiB window image. */
SECTIONS {
    .lisp65_c2_kernal_window.typed_queue_driver 0xe000 :
        AT(ORIGIN(c2_kernal_window_load) + 0x0000) {
        KEEP(*(.lisp65_c2_kernal_window.typed_queue_driver))
    } >c2_kernal_window
    .lisp65_c2_kernal_window.irq_handler
        ADDR(.lisp65_c2_kernal_window.typed_queue_driver) +
        SIZEOF(.lisp65_c2_kernal_window.typed_queue_driver) :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.irq_handler) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.irq_handler))
    } >c2_kernal_window
    .lisp65_c2_kernal_window.nmi_and_freezer_return
        ADDR(.lisp65_c2_kernal_window.irq_handler) +
        SIZEOF(.lisp65_c2_kernal_window.irq_handler) :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.nmi_and_freezer_return) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.nmi_and_freezer_return))
    } >c2_kernal_window
    .lisp65_c2_kernal_window.map_switch_and_guards
        ADDR(.lisp65_c2_kernal_window.nmi_and_freezer_return) +
        SIZEOF(.lisp65_c2_kernal_window.nmi_and_freezer_return) :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.map_switch_and_guards) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.map_switch_and_guards))
    } >c2_kernal_window
    .lisp65_c2_kernal_window.post_startup_output_seam
        ADDR(.lisp65_c2_kernal_window.map_switch_and_guards) +
        SIZEOF(.lisp65_c2_kernal_window.map_switch_and_guards) :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.post_startup_output_seam) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.post_startup_output_seam))
    } >c2_kernal_window
    .lisp65_c2_kernal_window.session_emitter_code
        ADDR(.lisp65_c2_kernal_window.post_startup_output_seam) +
        SIZEOF(.lisp65_c2_kernal_window.post_startup_output_seam) :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.session_emitter_code) - 0xe000) {
        __lisp65_c2_session_emitter_code_start = .;
        KEEP(*(.lisp65_c2_kernal_window.session_emitter_code))
        __lisp65_c2_session_emitter_code_end = .;
    } >c2_kernal_window
    .lisp65_c2_kernal_window.c2_resident
        ADDR(.lisp65_c2_kernal_window.session_emitter_code) +
        SIZEOF(.lisp65_c2_kernal_window.session_emitter_code) :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.c2_resident) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.c2_resident))
    } >c2_kernal_window
    .lisp65_c2_kernal_window.session_emitter_state
        ADDR(.lisp65_c2_kernal_window.c2_resident) +
        SIZEOF(.lisp65_c2_kernal_window.c2_resident) (NOLOAD) :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.session_emitter_state) - 0xe000) {
        __lisp65_c2_session_emitter_state_start = .;
        KEEP(*(.lisp65_c2_kernal_window.session_emitter_state))
        __lisp65_c2_session_emitter_state_end = .;
    } >c2_kernal_window
    .lisp65_c2_kernal_window.state 0xff80 :
        AT(ORIGIN(c2_kernal_window_load) + 0x1f80) {
        KEEP(*(.lisp65_c2_kernal_window.state))
    } >c2_kernal_window
    .lisp65_c2_vectors 0xfffa :
        AT(ORIGIN(c2_kernal_window_load) + 0x1ffa) {
        KEEP(*(.lisp65_c2_vectors))
    } >c2_kernal_window
} INSERT AFTER .lisp65_resident_island_annex;

/* The complete v2 profile adds three immutable service-dispatch tables.  They
 * are post-ownership data, not ordinary Bank-0 state.  Match the three exact
 * input sections before the inherited generic .rodata wildcard can claim
 * them; no other constant becomes an implicit E000 tenant. */
SECTIONS {
    .lisp65_c2_kernal_window.profile_rodata 0xfd12 :
        AT(ORIGIN(c2_kernal_window_load) + 0x1d12) {
        __lisp65_c2_profile_rodata_start = .;
        __lisp65_c2_profile_rodata_eval_start = .;
        KEEP(*(.rodata.eval_v2_workbench_service))
        __lisp65_c2_profile_rodata_eval_end = .;
        __lisp65_c2_profile_rodata_callprim_start = .;
        KEEP(*(.rodata.vm_callprim))
        __lisp65_c2_profile_rodata_callprim_end = .;
        __lisp65_c2_profile_rodata_native_start = .;
        KEEP(*(.rodata.vm_native_call))
        __lisp65_c2_profile_rodata_native_end = .;
        __lisp65_c2_profile_rodata_end = .;
    } >c2_kernal_window
} INSERT BEFORE .rodata;

ASSERT(ADDR(.basic_header) == 0x2001,
       "C2 load domains moved the product PRG header");
ASSERT(LOADADDR(.lisp65_workbench_overlay) == ORIGIN(c2_runtime_load),
       "C2 runtime-slice load domain did not start at its own origin");
ASSERT(__lisp65_resident_island_seed_lma + SIZEOF(.lisp65_resident_island) <=
       ORIGIN(c2_runtime_load) + LENGTH(c2_runtime_load),
       "C2 runtime-slice load domain exhausted");
ASSERT(LOADADDR(.lisp65_c2_kernal_window.typed_queue_driver) ==
       ORIGIN(c2_kernal_window_load),
       "C2 KERNAL-window load domain did not start at its own origin");
ASSERT(LOADADDR(.lisp65_c2_vectors) + SIZEOF(.lisp65_c2_vectors) ==
       ORIGIN(c2_kernal_window_load) + LENGTH(c2_kernal_window_load),
       "C2 KERNAL-window load image is not exactly 8 KiB");
ASSERT(ADDR(.lisp65_c2_kernal_handoff) < 0xe000 &&
       ADDR(.lisp65_c2_host_facade) < 0xe000 &&
       ADDR(.lisp65_c2_kernal_io_reveal) < 0xe000 &&
       ADDR(.lisp65_c2_kernal_map_switch) < 0xe000 &&
       ADDR(.lisp65_c2_kernal_state) < 0xe000,
       "C2 low-resident handoff escaped the PRG domain");
ASSERT(ADDR(.lisp65_c2_kernal_handoff) == 0xb4a3 &&
       ADDR(.lisp65_c2_kernal_handoff) + SIZEOF(.lisp65_c2_kernal_handoff) <= 0xb5c4,
       "C2 handoff overlaps the fixed host facade");
ASSERT(ADDR(.lisp65_c2_host_facade) == 0xb5c4 &&
       SIZEOF(.lisp65_c2_host_facade) == 39,
       "C2 fixed host-facade geometry drift");
ASSERT(c2_facade_vm_code_load == 0xb5c4 && c2_facade_c2_dma == 0xb5c7 &&
       c2_facade_overlay_call_family == 0xb5ca && c2_facade_c2e_cons == 0xb5cd &&
       c2_facade_c2e_overlay == 0xb5d0 && c2_facade_car == 0xb5d3 &&
       c2_facade_cdr == 0xb5d6 && c2_facade_gc_collect == 0xb5d9 &&
       c2_facade_str_open == 0xb5dc && c2_facade_str_putc == 0xb5df &&
       c2_facade_intern == 0xb5e2 && c2_facade_select_family == 0xb5e5 &&
       c2_facade_gc_mark == 0xb5e8,
       "C2 fixed host-facade vector address drift");
ASSERT(ADDR(.lisp65_c2_kernal_io_reveal) == 0xb5eb &&
       SIZEOF(.lisp65_c2_kernal_io_reveal) == 11 &&
       c2_kernal_reveal_io == 0xb5eb &&
       ADDR(.lisp65_c2_kernal_map_switch) == 0xb5f6 &&
       SIZEOF(.lisp65_c2_kernal_map_switch) == 10 &&
       ADDR(.lisp65_c2_kernal_map_switch) +
           SIZEOF(.lisp65_c2_kernal_map_switch) <= 0xb602 &&
       ADDR(.lisp65_c2_kernal_state) == 0xb602,
       "C2 fixed low-resident handoff geometry drift");

ASSERT(ADDR(.zp) + SIZEOF(.zp) <= 0x89,
       "ordinary zero-page storage overlaps fixed C2 state");
ASSERT(ADDR(.lisp65_c2_fixed_zp) == 0x89 &&
       SIZEOF(.lisp65_c2_fixed_zp) == 7 &&
       __lisp65_c2_fixed_zp_phase_owner == 0x89 &&
       __lisp65_c2_fixed_zp_pending_roots == 0x8a &&
       __lisp65_c2_fixed_zp_ready == 0x8c &&
       __lisp65_c2_fixed_zp_str_building == 0x8d &&
       __lisp65_c2_fixed_zp_mem_oom == 0x8f,
       "C2 fixed zero-page state geometry drift");
ASSERT(ADDR(.bss) + SIZEOF(.bss) <= 0xc080,
       "ordinary Bank-0 state overlaps fixed C2 state");
ASSERT(ADDR(.lisp65_c2_fixed_bank0) == 0xc080 &&
       SIZEOF(.lisp65_c2_fixed_bank0) == 408 &&
       __lisp65_c2_fixed_bank0_committed_roots == 0xc080 &&
       __lisp65_c2_fixed_bank0_decode_active == 0xc082 &&
       __lisp65_c2_fixed_bank0_runtime == 0xc084 &&
       __lisp65_c2_fixed_bank0_edma_job == 0xc0b2 &&
       __lisp65_c2_fixed_bank0_phase_scratch == 0xc0c6 &&
       __lisp65_c2_fixed_bank0_sym_name_scratch == 0xc1f6,
       "C2 fixed Bank-0 state geometry drift");
ASSERT(ADDR(.lisp65_c2_fixed_bank0) + SIZEOF(.lisp65_c2_fixed_bank0) <=
       ADDR(.lisp65_c2_fixed_bank0_code) &&
       ADDR(.lisp65_c2_fixed_bank0_code) == 0xc218 &&
       SIZEOF(.lisp65_c2_fixed_bank0_code) == 66 &&
       __lisp65_c2_fixed_bank0_code_start == 0xc218 &&
       __lisp65_c2_fixed_bank0_code_kb_cursor_off == 0xc218 &&
       __lisp65_c2_fixed_bank0_code_c2e_cons == 0xc21d &&
       __lisp65_c2_fixed_bank0_code_rtov_fail == 0xc245 &&
       __lisp65_c2_fixed_bank0_code_end == 0xc25a &&
       ADDR(.lisp65_c2_fixed_bank0_code) +
       SIZEOF(.lisp65_c2_fixed_bank0_code) <=
       __lisp65_workbench_runtime_overlay_vma,
       "C2 fixed Bank-0 state overlaps the runtime overlay");

ASSERT(ADDR(.lisp65_c2_kernal_window.c2_resident) +
       SIZEOF(.lisp65_c2_kernal_window.c2_resident) <= 0xff80,
       "C2-owned KERNAL-window residents overlap state");
ASSERT(SIZEOF(.lisp65_c2_kernal_window.session_emitter_code) == 0 &&
       SIZEOF(.lisp65_c2_kernal_window.session_emitter_state) == 346,
       "C2 session-only E000 residency geometry drift");
ASSERT(ADDR(.lisp65_c2_kernal_window.session_emitter_state) +
       SIZEOF(.lisp65_c2_kernal_window.session_emitter_state) ==
       ADDR(.lisp65_c2_kernal_window.profile_rodata) &&
       ADDR(.lisp65_c2_kernal_window.profile_rodata) == 0xfd12,
       "C2 profile rodata is not adjacent to session state");
ASSERT(__lisp65_c2_profile_rodata_eval_end -
       __lisp65_c2_profile_rodata_eval_start == 32 &&
       __lisp65_c2_profile_rodata_callprim_end -
       __lisp65_c2_profile_rodata_callprim_start == 164 &&
       __lisp65_c2_profile_rodata_native_end -
       __lisp65_c2_profile_rodata_native_start == 146 &&
       SIZEOF(.lisp65_c2_kernal_window.profile_rodata) == 342,
       "C2 complete-profile immutable-data geometry drift");
ASSERT(ADDR(.lisp65_c2_kernal_window.profile_rodata) +
       SIZEOF(.lisp65_c2_kernal_window.profile_rodata) <= 0xff80,
       "C2 complete-profile immutable data overlaps owned state");
ASSERT(ADDR(.lisp65_c2_kernal_window.state) == 0xff80 &&
       SIZEOF(.lisp65_c2_kernal_window.state) == 16,
       "C2 KERNAL-window state geometry drift");
ASSERT(ADDR(.lisp65_c2_vectors) == 0xfffa && SIZEOF(.lisp65_c2_vectors) == 6,
       "C2 owned vector geometry drift");
"""
    callprim_profile_bytes = PROFILE_RODATA_INPUT_SECTIONS[
        ".rodata.vm_callprim"]
    native_profile_bytes = PROFILE_RODATA_INPUT_SECTIONS[
        ".rodata.vm_native_call"]
    if (callprim_profile_bytes != 164
            or native_profile_bytes != 146
            or PROFILE_RODATA_BYTES != 342):
        kernal_layout = kernal_layout.replace(
            "__lisp65_c2_profile_rodata_callprim_start == 164",
            "__lisp65_c2_profile_rodata_callprim_start == "
            f"{callprim_profile_bytes}",
            1)
        kernal_layout = kernal_layout.replace(
            "__lisp65_c2_profile_rodata_native_start == 146",
            "__lisp65_c2_profile_rodata_native_start == "
            f"{native_profile_bytes}",
            1)
        kernal_layout = kernal_layout.replace(
            "SIZEOF(.lisp65_c2_kernal_window.profile_rodata) == 342",
            "SIZEOF(.lisp65_c2_kernal_window.profile_rodata) == "
            f"{PROFILE_RODATA_BYTES}",
            1)
    if E000_REOPENING:
        # The fourteenth vector is appended to the sole facade output.  Moving
        # the following low-resident seams keeps every pre-existing vector
        # address stable while avoiding a second fixed-LMA output domain.
        kernal_layout = kernal_layout.replace(
            ".lisp65_c2_kernal_io_reveal 0xb5eb",
            ".lisp65_c2_kernal_io_reveal 0xb5ee")
        kernal_layout = kernal_layout.replace(
            ".lisp65_c2_kernal_map_switch 0xb5f6",
            ".lisp65_c2_kernal_map_switch 0xb5f9")
        kernal_layout = kernal_layout.replace(
            ".lisp65_c2_kernal_state 0xb602",
            ".lisp65_c2_kernal_state 0xb606")
        kernal_layout = kernal_layout.replace(
            "SIZEOF(.lisp65_c2_host_facade) == 39",
            "SIZEOF(.lisp65_c2_host_facade) == 42")
        kernal_layout = kernal_layout.replace("0xb5eb", "0xb5ee")
        # Restore the appended facade vector after the broad seam-address
        # replacement above; the original thirteen still end at $b5eb.
        kernal_layout = kernal_layout.replace(
            "c2_facade_gc_mark == 0xb5e8,",
            "c2_facade_gc_mark == 0xb5e8 &&\n"
            "       c2_facade_runtime_overlay_exec == 0xb5eb,")
        kernal_layout = kernal_layout.replace("0xb5f6", "0xb5f9")
        kernal_layout = kernal_layout.replace("0xb602", "0xb606")

    if BSS_TRIAGE:
        # The fifteenth vector consumes the three-byte alignment pocket after
        # the shifted MAP helper.  State and the predecessor-bound ordinary
        # data chain therefore retain their established addresses.
        kernal_layout = kernal_layout.replace(
            ".lisp65_c2_kernal_io_reveal 0xb5ee",
            ".lisp65_c2_kernal_io_reveal 0xb5f1")
        kernal_layout = kernal_layout.replace(
            ".lisp65_c2_kernal_map_switch 0xb5f9",
            ".lisp65_c2_kernal_map_switch 0xb5fc")
        kernal_layout = kernal_layout.replace(
            "SIZEOF(.lisp65_c2_host_facade) == 42",
            "SIZEOF(.lisp65_c2_host_facade) == 45")
        kernal_layout = kernal_layout.replace(
            "c2_facade_runtime_overlay_exec == 0xb5eb,",
            "c2_facade_runtime_overlay_exec == 0xb5eb &&\n"
            "       c2_facade_handle_normalize == 0xb5ee,")
        kernal_layout = kernal_layout.replace(
            "ADDR(.lisp65_c2_kernal_io_reveal) == 0xb5ee",
            "ADDR(.lisp65_c2_kernal_io_reveal) == 0xb5f1")
        kernal_layout = kernal_layout.replace(
            "c2_kernal_reveal_io == 0xb5ee",
            "c2_kernal_reveal_io == 0xb5f1")
        kernal_layout = kernal_layout.replace(
            "ADDR(.lisp65_c2_kernal_map_switch) == 0xb5f9",
            "ADDR(.lisp65_c2_kernal_map_switch) == 0xb5fc")

    if APPEND_PLAN_FACADE:
        # The sixteenth vector consumes $B5F1..$B5F3.  Unlike the fifteenth
        # vector, there is no alignment pocket: I/O reveal, MAP switch, the
        # low-resident state, and their predecessor-bound ordinary-data chain
        # move together by exactly three bytes.  Fixed points from $C080 on do
        # not move.
        if not BSS_TRIAGE:
            raise RuntimeError("append-plan facade lacks BSS-triage geometry")
        kernal_layout = kernal_layout.replace(
            ".lisp65_c2_kernal_io_reveal 0xb5f1",
            ".lisp65_c2_kernal_io_reveal 0xb5f4")
        kernal_layout = kernal_layout.replace(
            ".lisp65_c2_kernal_map_switch 0xb5fc",
            ".lisp65_c2_kernal_map_switch 0xb5ff")
        kernal_layout = kernal_layout.replace(
            ".lisp65_c2_kernal_state 0xb606",
            ".lisp65_c2_kernal_state 0xb609")
        kernal_layout = kernal_layout.replace(
            "SIZEOF(.lisp65_c2_host_facade) == 45",
            "SIZEOF(.lisp65_c2_host_facade) == 48")
        kernal_layout = kernal_layout.replace(
            "c2_facade_handle_normalize == 0xb5ee,",
            "c2_facade_handle_normalize == 0xb5ee &&\n"
            "       c2_facade_append_plan_walk == 0xb5f1,")
        kernal_layout = kernal_layout.replace(
            "ADDR(.lisp65_c2_kernal_io_reveal) == 0xb5f1",
            "ADDR(.lisp65_c2_kernal_io_reveal) == 0xb5f4")
        kernal_layout = kernal_layout.replace(
            "c2_kernal_reveal_io == 0xb5f1",
            "c2_kernal_reveal_io == 0xb5f4")
        kernal_layout = kernal_layout.replace(
            "ADDR(.lisp65_c2_kernal_map_switch) == 0xb5fc",
            "ADDR(.lisp65_c2_kernal_map_switch) == 0xb5ff")
        kernal_layout = kernal_layout.replace(
            "SIZEOF(.lisp65_c2_kernal_map_switch) <= 0xb606",
            "SIZEOF(.lisp65_c2_kernal_map_switch) <= 0xb609")
        kernal_layout = kernal_layout.replace(
            "ADDR(.lisp65_c2_kernal_state) == 0xb606",
            "ADDR(.lisp65_c2_kernal_state) == 0xb609")

    if LINK60_FINAL_GEOMETRY:
        replacements = (
            ("SIZEOF(.lisp65_c2_fixed_bank0_code) == 66",
             "SIZEOF(.lisp65_c2_fixed_bank0_code) == 69"),
            ("__lisp65_c2_fixed_bank0_code_end == 0xc25a",
             "__lisp65_c2_fixed_bank0_code_end == 0xc25d"),
        )
        for old, new in replacements:
            if kernal_layout.count(old) != 1:
                raise RuntimeError(f"Link-60 fixed-code template drift: {old}")
            kernal_layout = kernal_layout.replace(old, new, 1)

    if LOW_RESIDENT_LMA_RESET:
        kernal_layout = apply_low_resident_lma_reset(kernal_layout)

    bss_triage_layout = ""
    if BSS_TRIAGE:
        hot_end = FIXED_BANK0_HOT_BSS_BASE + FIXED_BANK0_HOT_BSS_BYTES
        noinit_end = hot_end + FIXED_BANK0_NOINIT_BYTES
        overlay_floor = (noinit_end + 2) & ~1
        bss_triage_layout = f"""
/* Owner-authorized BSS triage.  The direct hot heap is the sole new fixed
 * tenant; it is reinitialized by mem_init because this NOLOAD section is not
 * part of the CRT ordinary-BSS wipe. */
SECTIONS {{
    .lisp65_c2_fixed_bank0_hot_bss 0x{FIXED_BANK0_HOT_BSS_BASE:04x} (NOLOAD) : {{
        __lisp65_c2_fixed_bank0_hot_bss_start = .;
        __lisp65_c2_fixed_bank0_hot_bss_heap = .;
        KEEP(*(.lisp65_c2_fixed_bank0_hot_bss.heap))
        __lisp65_c2_fixed_bank0_hot_bss_end = .;
    }} >ram
}} INSERT AFTER .lisp65_c2_fixed_bank0_code;

ASSERT(ADDR(.lisp65_c2_fixed_bank0_hot_bss) == 0x{FIXED_BANK0_HOT_BSS_BASE:04x} &&
       SIZEOF(.lisp65_c2_fixed_bank0_hot_bss) == {FIXED_BANK0_HOT_BSS_BYTES} &&
       heap == 0x{FIXED_BANK0_HOT_BSS_BASE:04x} &&
       __lisp65_c2_fixed_bank0_hot_bss_end == 0x{hot_end:04x} &&
       __lisp65_c2_fixed_bank0_hot_bss_end <=
           __lisp65_workbench_runtime_overlay_vma,
       "C2 hot-BSS fixed-block geometry drift");
ASSERT(ADDR(.noinit) == 0x{hot_end:04x} &&
       SIZEOF(.noinit) == {FIXED_BANK0_NOINIT_BYTES} &&
       __lisp65_workbench_overlay_min_start == 0x{overlay_floor:04x} &&
       __lisp65_workbench_overlay_min_start <=
           __lisp65_workbench_runtime_overlay_vma,
       "C2 inherited noinit/fixed-block geometry drift");

/* The llvm-mos .rodata output is inherited from the platform script.  Bind it
 * to the preceding explicit low-resident state rather than to a free-standing
 * location-counter assignment (which does not place inherited outputs). */
ASSERT(ADDR(.rodata) ==
           ADDR(.lisp65_c2_kernal_state) +
           SIZEOF(.lisp65_c2_kernal_state) &&
       LOADADDR(.rodata) == ADDR(.rodata),
       "ordinary rodata predecessor/VMA/LMA relation drift");
"""
    reopen_layout = ""
    if E000_REOPENING:
        capture_main_layout = r"""
    .lisp65_c2_kernal_window.input_capture_main
        ADDR(.lisp65_c2_kernal_window.reopen_gap0) +
        SIZEOF(.lisp65_c2_kernal_window.reopen_gap0) :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.input_capture_main) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.input_capture_main))
    } >c2_kernal_window""" if INPUT_CAPTURE_ENABLED else ""
        capture_helper_layout = r"""
    .lisp65_c2_kernal_window.input_capture_helper
        ADDR(.lisp65_c2_kernal_window.reopen_gap1) +
        SIZEOF(.lisp65_c2_kernal_window.reopen_gap1) :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.input_capture_helper) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.input_capture_helper))
    } >c2_kernal_window""" if INPUT_CAPTURE_ENABLED else ""
        input_consumer_layout = r"""
    .lisp65_c2_kernal_window.input_consumer
        ADDR(.lisp65_c2_kernal_window.input_capture_helper) +
        SIZEOF(.lisp65_c2_kernal_window.input_capture_helper) :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.input_consumer) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.input_consumer))
    } >c2_kernal_window""" if INPUT_HYBRID_ENABLED else ""
        capture_assertions = r"""
ASSERT(SIZEOF(.lisp65_c2_kernal_window.input_capture_main) > 0,
       "card-owned seed section is zero bytes; missing source owner=v160-input-capture section=.lisp65_c2_kernal_window.input_capture_main");
ASSERT(SIZEOF(.lisp65_c2_kernal_window.input_capture_main) == 28 &&
       ADDR(.lisp65_c2_kernal_window.input_capture_main) ==
           ADDR(.lisp65_c2_kernal_window.reopen_gap0) +
           SIZEOF(.lisp65_c2_kernal_window.reopen_gap0) &&
       ADDR(.lisp65_c2_kernal_window.input_capture_main) +
           SIZEOF(.lisp65_c2_kernal_window.input_capture_main) <=
           ADDR(.lisp65_c2_kernal_window.profile_rodata),
       "Comfort input capture main escaped its final-image-derived hole");
ASSERT(SIZEOF(.lisp65_c2_kernal_window.input_capture_helper) > 0,
       "card-owned seed section is zero bytes; missing source owner=v160-input-capture section=.lisp65_c2_kernal_window.input_capture_helper");
ASSERT(SIZEOF(.lisp65_c2_kernal_window.input_capture_helper) == 40 &&
       ADDR(.lisp65_c2_kernal_window.input_capture_helper) ==
           ADDR(.lisp65_c2_kernal_window.reopen_gap1) +
           SIZEOF(.lisp65_c2_kernal_window.reopen_gap1) &&
       ADDR(.lisp65_c2_kernal_window.input_capture_helper) +
           SIZEOF(.lisp65_c2_kernal_window.input_capture_helper) <=
           ADDR(.lisp65_c2_kernal_window.state),
       "Comfort input capture helper escaped its final-image-derived hole");
ASSERT((ADDR(.lisp65_c2_kernal_window.profile_rodata) -
            (ADDR(.lisp65_c2_kernal_window.input_capture_main) +
             SIZEOF(.lisp65_c2_kernal_window.input_capture_main))) +
       (ADDR(.lisp65_c2_kernal_window.state) -
            (ADDR(.lisp65_c2_kernal_window.input_capture_helper) +
             SIZEOF(.lisp65_c2_kernal_window.input_capture_helper))) == 2,
       "Comfort input capture final C2 reserve is not two bytes");""" \
            if INPUT_CAPTURE_ENABLED else ""
        if INPUT_HYBRID_ENABLED:
            capture_assertions = capture_assertions.replace(
                "SIZEOF(.lisp65_c2_kernal_window.input_capture_helper))) == 2",
                "SIZEOF(.lisp65_c2_kernal_window.input_capture_helper))) >= 57").replace(
                    "Comfort input capture final C2 reserve is not two bytes",
                    "adaptive input capture breached the 54-byte floor plus 3-byte watch")
        hybrid_assertions = r"""
ASSERT(SIZEOF(.lisp65_c2_kernal_window.input_consumer) > 0 &&
       SIZEOF(.lisp65_c2_kernal_window.input_consumer) <= 70 &&
       ADDR(.lisp65_c2_kernal_window.input_consumer) ==
           ADDR(.lisp65_c2_kernal_window.input_capture_helper) +
           SIZEOF(.lisp65_c2_kernal_window.input_capture_helper) &&
       ADDR(.lisp65_c2_kernal_window.input_consumer) +
           SIZEOF(.lisp65_c2_kernal_window.input_consumer) <=
           ADDR(.lisp65_c2_kernal_window.state),
       "adaptive input consumer escaped its final-image-derived hole");
ASSERT((ADDR(.lisp65_c2_kernal_window.profile_rodata) -
            (ADDR(.lisp65_c2_kernal_window.input_capture_main) +
             SIZEOF(.lisp65_c2_kernal_window.input_capture_main))) +
       (ADDR(.lisp65_c2_kernal_window.state) -
            (ADDR(.lisp65_c2_kernal_window.input_consumer) +
       SIZEOF(.lisp65_c2_kernal_window.input_consumer))) >= 57,
       "adaptive input consumer breached the 54-byte floor plus 3-byte watch");""" \
            if INPUT_HYBRID_ENABLED else ""
        reopen_layout = r"""
/* One-time owner-authorized Link-33 reopening.  The three holes are explicit:
 * no wildcard and no unrelated input section can become a tenant. */
SECTIONS {
    .lisp65_c2_kernal_window.reopen_gap0
        ADDR(.lisp65_c2_kernal_window.c2_resident) +
        SIZEOF(.lisp65_c2_kernal_window.c2_resident) :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.reopen_gap0) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.reopen_gap0))
    } >c2_kernal_window
{capture_main_layout}
    .lisp65_c2_kernal_window.reopen_gap1
        ADDR(.lisp65_c2_kernal_window.profile_rodata) +
        SIZEOF(.lisp65_c2_kernal_window.profile_rodata) :
        AT(ORIGIN(c2_kernal_window_load) +
           ADDR(.lisp65_c2_kernal_window.reopen_gap1) - 0xe000) {
        KEEP(*(.lisp65_c2_kernal_window.reopen_gap1))
    } >c2_kernal_window
{capture_helper_layout}
{input_consumer_layout}
    .lisp65_c2_kernal_window.reopen_gap2 0xff90 :
        AT(ORIGIN(c2_kernal_window_load) + 0x1f90) {
        KEEP(*(.lisp65_c2_kernal_window.reopen_gap2))
    } >c2_kernal_window
} INSERT AFTER .lisp65_resident_island_annex;

ASSERT(SIZEOF(.lisp65_c2_kernal_window.reopen_gap0) > 0 &&
       ADDR(.lisp65_c2_kernal_window.reopen_gap0) +
       SIZEOF(.lisp65_c2_kernal_window.reopen_gap0) <=
       ADDR(.lisp65_c2_kernal_window.session_emitter_state),
       "C2 reopening gap0 overlaps session-emitter state");
ASSERT(SIZEOF(.lisp65_c2_kernal_window.reopen_gap1) > 0 &&
       ADDR(.lisp65_c2_kernal_window.reopen_gap1) +
       SIZEOF(.lisp65_c2_kernal_window.reopen_gap1) <=
       ADDR(.lisp65_c2_kernal_window.state),
       "C2 reopening gap1 overlaps owned state");
{capture_assertions}
{hybrid_assertions}
ASSERT(SIZEOF(.lisp65_c2_kernal_window.reopen_gap2) > 0 &&
       ADDR(.lisp65_c2_kernal_window.reopen_gap2) +
       SIZEOF(.lisp65_c2_kernal_window.reopen_gap2) <=
       ADDR(.lisp65_c2_vectors),
       "C2 reopening gap2 overlaps vectors");
ASSERT(SIZEOF(.lisp65_c2_host_facade) == 45 &&
       c2_facade_runtime_overlay_exec == 0xb5eb &&
       c2_facade_handle_normalize == 0xb5ee,
       "C2 reopening appended facade vector drift");
ASSERT(SIZEOF(.lisp65_c2_kernal_window.reopen_gap0) +
       SIZEOF(.lisp65_c2_kernal_window.reopen_gap1) +
       SIZEOF(.lisp65_c2_kernal_window.reopen_gap2) +
       6 <= 450,
       "C2 formal E000 reopening exceeds the owner debit cap");
"""
        reopen_layout = reopen_layout.replace(
            "{capture_main_layout}", capture_main_layout).replace(
            "{capture_helper_layout}", capture_helper_layout).replace(
            "{input_consumer_layout}", input_consumer_layout).replace(
            "{capture_assertions}", capture_assertions).replace(
            "{hybrid_assertions}", hybrid_assertions)
        if APPEND_PLAN_FACADE:
            reopen_layout = reopen_layout.replace(
                "SIZEOF(.lisp65_c2_host_facade) == 45",
                "SIZEOF(.lisp65_c2_host_facade) == 48")
            reopen_layout = reopen_layout.replace(
                "c2_facade_handle_normalize == 0xb5ee,",
                "c2_facade_handle_normalize == 0xb5ee &&\n"
                "       c2_facade_append_plan_walk == 0xb5f1,")
            reopen_layout = reopen_layout.replace(
                "       6 <= 450,", "       9 <= 450,")
    metadata_sections = []
    required_metadata = {".lisp65_error_callsites"}
    for name in ORPHAN_ALLOWLIST:
        keep = f"KEEP(*({name}))" if name in required_metadata else f"*({name})"
        metadata_sections.append(f"    {name} 0 (INFO) : {{ {keep} }}")
    metadata_layout = (
        "\n/* Exact non-ALLOC orphan allowlist.  Unknown section names remain fatal. */\n"
        "SECTIONS {\n" + "\n".join(metadata_sections) + "\n}\n"
        "ASSERT(SIZEOF(.lisp65_error_callsites) > 0,\n"
        "       \"required error-callsite evidence section is absent\");\n"
        "ASSERT(ADDR(.lisp65_error_callsites) == 0,\n"
        "       \"error-callsite evidence section moved from address zero\");\n"
        "\n/* Pinned lld diagnoses this LTO bookkeeping input as an orphan even\n"
        " * when named.  The exact-warning wrapper and final inventory are\n"
        " * therefore the compensating gates for this one INFO section. */\n"
        "SECTIONS {\n"
        "    .llvm_sympart 0 (INFO) : { KEEP(*(.llvm_sympart)) }\n"
        "}\n"
        "ASSERT(SIZEOF(.llvm_sympart) > 0,\n"
        "       \"required LTO partition metadata section is absent\");\n"
        "ASSERT(ADDR(.llvm_sympart) == 0,\n"
        "       \"LTO partition metadata moved from address zero\");\n"
    )
    owned_layout = ""
    if ownership_selected:
        if ownership is None:
            raise RuntimeError("selected ownership contract is absent")
        cpu = ownership["cpu_window"]
        bank2 = ownership["bank2"]
        mapping = ownership["map_tuple"]
        resident = ownership["resident"]
        owned_layout = f"""/* Halt-1-selected stack/state/far-service owners.
 * Expected addresses live in the reviewed ownership contract; the permanent
 * gate compares this generated script and the final ELF against that
 * independent authority. */
SECTIONS {{
    .lisp65_c2_convergence_zp 0x87 (NOLOAD) : {{
        KEEP(*(.lisp65_c2_convergence_zp.*))
    }} >zp
}} INSERT AFTER .lisp65_c2_fixed_zp;

SECTIONS {{
    .lisp65_c2_convergence_state 0xc000 (NOLOAD) : {{
        KEEP(*(.lisp65_c2_convergence_state.*))
    }} >ram
    .lisp65_c2_static_stack 0xc074 (NOLOAD) : {{
        KEEP(*(.noinit..Lstatic_stack*))
    }} >ram
}} INSERT BEFORE .noinit;

SECTIONS {{
    .lisp65_c2_mapped_far_facade {int(resident['start'], 0):#06x} : {{
        KEEP(*(.lisp65_c2_mapped_far_facade.entries))
        KEEP(*(.lisp65_c2_mapped_far_facade.abort))
        __lisp65_c2_mapped_far_facade_padding_start = .;
        KEEP(*(.lisp65_c2_mapped_far_facade.padding))
        __lisp65_c2_mapped_far_facade_padding_end = .;
        KEEP(*(.lisp65_c2_mapped_far_facade.*))
    }} >ram
    .lisp65_c2_mapped_far_service {int(mapping['mapped_service_cpu_start'], 0):#06x}
        : AT({int(bank2['service_physical_start'], 0):#010x}) {{
        KEEP(*(.lisp65_c2_mapped_far_service))
        KEEP(*(.lisp65_c2_mapped_far_service.*))
    }} >ram
}} INSERT AFTER .text;

__lisp65_c2_mapped_far_required =
    DEFINED(__lisp65_c2_mapped_far_required_param)
        ? __lisp65_c2_mapped_far_required_param : 0;
__lisp65_c2_mapped_far_facade_padding_required =
    DEFINED(__lisp65_c2_mapped_far_facade_padding_required_param)
        ? __lisp65_c2_mapped_far_facade_padding_required_param : 0;
__lisp65_c2_mapped_far_service_start =
    ADDR(.lisp65_c2_mapped_far_service);
__lisp65_c2_mapped_far_service_end =
    ADDR(.lisp65_c2_mapped_far_service) +
    SIZEOF(.lisp65_c2_mapped_far_service);
__lisp65_c2_mapped_far_service_load_start =
    LOADADDR(.lisp65_c2_mapped_far_service);
__lisp65_c2_mapped_far_service_load_end =
    LOADADDR(.lisp65_c2_mapped_far_service) +
    SIZEOF(.lisp65_c2_mapped_far_service);

ASSERT(ADDR(.lisp65_c2_static_stack) == 0xc074 &&
       SIZEOF(.lisp65_c2_static_stack) <= 12 &&
       ADDR(.lisp65_c2_static_stack) +
           SIZEOF(.lisp65_c2_static_stack) <= 0xc080,
       "compiler static stack escaped its owned 12-byte arena");
ASSERT(__lisp65_workbench_overlay_min_start == 0xc354,
       "runtime overlay floor drifted from its owner contract");
ASSERT(__lisp65_c2_mapped_far_required == 0 ||
       (ADDR(.lisp65_c2_convergence_zp) == 0x87 &&
        SIZEOF(.lisp65_c2_convergence_zp) == 2 &&
        ADDR(.lisp65_c2_convergence_state) == 0xc000 &&
        SIZEOF(.lisp65_c2_convergence_state) == 66),
       "convergence state escaped its named owners");
ASSERT(__lisp65_c2_mapped_far_required == 0 ||
       (ADDR(.lisp65_c2_mapped_far_facade) == {int(resident['start'], 0):#06x} &&
        SIZEOF(.lisp65_c2_mapped_far_facade) == {int(resident['total_bytes'])} &&
        ADDR(.lisp65_c2_mapped_far_facade) +
            SIZEOF(.lisp65_c2_mapped_far_facade) <= {int(resident['end_exclusive'], 0):#06x}),
       "mapped far facade escaped its resident wall");
ASSERT(__lisp65_c2_mapped_far_facade_padding_required == 0 ||
       (DEFINED(__lisp65_c2_mapped_far_facade_padding_contract_bytes) &&
        __lisp65_c2_mapped_far_facade_padding_end -
            __lisp65_c2_mapped_far_facade_padding_start ==
                __lisp65_c2_mapped_far_facade_padding_contract_bytes &&
        __lisp65_c2_mapped_far_facade_padding_contract_bytes == 19),
       "mapped far facade explicit padding drift");
ASSERT(__lisp65_c2_mapped_far_required == 0 ||
       (ADDR(.lisp65_c2_mapped_far_service) == {int(mapping['mapped_service_cpu_start'], 0):#06x} &&
        LOADADDR(.lisp65_c2_mapped_far_service) == {int(bank2['service_physical_start'], 0):#010x} &&
        SIZEOF(.lisp65_c2_mapped_far_service) == {int(bank2['service_bytes'])} &&
        __lisp65_c2_mapped_far_service_end == {int(mapping['mapped_service_cpu_end_exclusive'], 0):#06x} &&
        __lisp65_c2_mapped_far_service_load_end == {int(bank2['service_physical_end_exclusive'], 0):#010x}),
       "mapped far body escaped its Bank-2 owner");
ASSERT(__lisp65_c2_mapped_far_required == 0 ||
       ADDR(.text) + SIZEOF(.text) <= {int(resident['start'], 0):#06x},
       "ordinary text displaced the mapped far facade");
ASSERT({int(cpu['start'], 0):#06x} == 0x6000 &&
       {int(cpu['end_exclusive'], 0):#06x} == 0x8000,
       "mapped CPU slab contract drifted");
"""
    if REFILL_WITNESS_ENABLED and PRODUCT_COLD_ENABLED:
        raise RuntimeError("diagnostic and product-cold arenas overlap")
    if REFILL_WITNESS_ENABLED or PRODUCT_COLD_ENABLED:
        mapped = (REFILL_WITNESS_BUILD_CONFIGURATION
                  if REFILL_WITNESS_ENABLED
                  else PRODUCT_COLD_BUILD_CONFIGURATION)
        section_name = str(mapped["allocated"][0])
        cpu_start = int(mapped["cpu_start"])
        physical_start = int(mapped["physical_start"])
        capacity = int(mapped["capacity_bytes"])
        prefix = ("__lisp65_c2_mapped_diagnostic" if REFILL_WITNESS_ENABLED
                  else "__lisp65_c2_mapped_product_cold")
        label = ("refill witness" if REFILL_WITNESS_ENABLED
                 else "product cold tenant")
        owned_layout += f"""
SECTIONS {{
    {section_name} {cpu_start:#06x}
        : AT({physical_start:#010x}) {{
        KEEP(*({section_name}))
        KEEP(*({section_name}.*))
    }} >ram
}} INSERT AFTER .text;

{prefix}_start = ADDR({section_name});
{prefix}_end = ADDR({section_name}) + SIZEOF({section_name});
{prefix}_load_start = LOADADDR({section_name});
{prefix}_load_end = LOADADDR({section_name}) + SIZEOF({section_name});

ASSERT(ADDR({section_name}) == {cpu_start:#06x} &&
       LOADADDR({section_name}) == {physical_start:#010x} &&
       SIZEOF({section_name}) > 0 &&
       SIZEOF({section_name}) <= {capacity} &&
       {prefix}_end <= 0x8000,
       "{label} escaped its mapped arena");
"""
    result = (memory_layout + text + "\n" + binding_layout + kernal_layout
              + owned_layout + bss_triage_layout + reopen_layout
              + metadata_layout).replace(
        "directly after Slot 37", "directly after the final C2 runtime slice")
    result = full_map_rewrite_product_linker(result)
    if PROFILE_RODATA_BASE != 0xFD12:
        replacements = (
            (".lisp65_c2_kernal_window.profile_rodata 0xfd12",
             ".lisp65_c2_kernal_window.profile_rodata "
             f"0x{PROFILE_RODATA_BASE:04x}"),
            ("AT(ORIGIN(c2_kernal_window_load) + 0x1d12)",
             "AT(ORIGIN(c2_kernal_window_load) + "
             f"0x{PROFILE_RODATA_BASE - KERNAL_WINDOW_BASE:04x})"),
            ("ADDR(.lisp65_c2_kernal_window.profile_rodata) == 0xfd12,",
             "ADDR(.lisp65_c2_kernal_window.profile_rodata) == "
             f"0x{PROFILE_RODATA_BASE:04x},"),
        )
        for old, new in replacements:
            if result.count(old) != 1:
                raise RuntimeError(
                    f"profile-rodata placement template drift: {old}")
            result = result.replace(old, new, 1)
    if BSS_TRIAGE:
        occupied = " +\n       ".join(
            f"SIZEOF({name})" for name in KERNAL_SECTIONS)
        result += (
            "\n/* Final owner-bound E000 floor: no third reopening. */\n"
            f"ASSERT({occupied} <= "
            f"{KERNAL_WINDOW_BYTES - E000_FINAL_FLOOR_BYTES},\n"
            f'       "C2 final E000 floor below {E000_FINAL_FLOOR_BYTES} bytes");\n'
        )
    if SESSION_EMITTER_STATE_BYTES != 346:
        old_placement = """    .lisp65_c2_kernal_window.session_emitter_state
        ADDR(.lisp65_c2_kernal_window.c2_resident) +
        SIZEOF(.lisp65_c2_kernal_window.c2_resident) (NOLOAD) :"""
        state_base = (
            SESSION_EMITTER_STATE_BASE
            if SESSION_EMITTER_STATE_BASE is not None
            else PROFILE_RODATA_BASE - SESSION_EMITTER_STATE_BYTES)
        new_placement = (
            "    .lisp65_c2_kernal_window.session_emitter_state "
            f"0x{state_base:04x} "
            "(NOLOAD) :")
        if old_placement not in result:
            raise RuntimeError("session-emitter placement template drift")
        result = result.replace(old_placement, new_placement, 1)
        result = result.replace(
            "SIZEOF(.lisp65_c2_kernal_window.session_emitter_state) == 346,",
            "SIZEOF(.lisp65_c2_kernal_window.session_emitter_state) == "
            f"{SESSION_EMITTER_STATE_BYTES},",
            1,
        )
        if SESSION_EMITTER_STATE_BYTES == 0:
            old_adjacency = """ASSERT(ADDR(.lisp65_c2_kernal_window.session_emitter_state) +
       SIZEOF(.lisp65_c2_kernal_window.session_emitter_state) ==
       ADDR(.lisp65_c2_kernal_window.profile_rodata) &&
       ADDR(.lisp65_c2_kernal_window.profile_rodata) == """
            new_adjacency = (
                "ASSERT(ADDR(.lisp65_c2_kernal_window.session_emitter_state) == "
                f"0x{state_base:04x} &&\n"
                "       SIZEOF(.lisp65_c2_kernal_window.session_emitter_state) == 0 &&\n"
                "       ADDR(.lisp65_c2_kernal_window.profile_rodata) == ")
            if result.count(old_adjacency) != 1:
                raise RuntimeError(
                    "zero-byte session-emitter anchor assertion template drift")
            result = result.replace(old_adjacency, new_adjacency, 1)
    return result


def source_list(extra_definitions: tuple[str, ...] = ()) -> list[str]:
    sources = [
        str(path) for path in sorted((ROOT / "src").glob("*.c"))
        if path.name not in LEGACY_C
    ]
    sources.extend(str(path) for path in C2_PHASE_SOURCES)
    selected_definitions = set(scoped_probe_definitions(extra_definitions))
    kernal_irq_source = (
        INPUT_CAPTURE_SOURCE
        if INPUT_CAPTURE_FEATURE in selected_definitions
        else INPUT_CAPTURE_BASE_SOURCE)
    sources.extend([
        str(ROOT / "src/mega65_math.s"),
        str(ROOT / "src/f011_guarded_write.s"),
        str(ROOT / "src/runtime_overlay_verifier_bindings.s"),
        str(ROOT / "src/c2_kernal_facade.s"),
        str(ROOT / "src/c2_kernal_map.s"),
        str(ROOT / "src/c2_kernal_window.s"),
        str(kernal_irq_source),
        str(ROOT / "src/rtov_crc_mem.s"),
        str(ROOT / "src/c2_completion_mode_length.s"),
        str(ROOT / "src/lisp65_ash_tagged.s"),
        str(ROOT / "src/l65e_bcode_ordinal.s"),
        str(ROOT / "src/c2_append_plan_walk.s"),
    ])
    if "LISP65_C2_REQUIRE_RESOLVER" in extra_definitions:
        sources.append(str(ROOT / "src/vm_c2d_byte.s"))
    if "LISP65_C2_LITE_V6_JOURNAL_PREPARE_CORESIDENT" in extra_definitions:
        sources.append(str(ROOT / "src/c2_journal_prepare_select.s"))
    if "LISP65_RTOV_DMA_COMPLETION_FENCE" in extra_definitions:
        sources.append(str(ROOT / "src/rtov_dma_completion.s"))
    selected_scope_sources: list[Path] = []
    for scope in SOURCE_OWNER_SCOPES:
        if str(scope["trigger"]) in selected_definitions:
            selected_scope_sources.extend(Path(path) for path in scope["sources"])
    # The selected KERNAL IRQ owner was already inserted at its stable source
    # ordinal.  Other optional owners are appended through their scopes.
    sources.extend(str(path) for path in dict.fromkeys(selected_scope_sources)
                   if path.resolve() != kernal_irq_source.resolve())
    if BANK3_STAGING_SLICES:
        sources.append(str(ROOT / "src/c2_lite_bank3_stage_entry.s"))
        sources.append(str(ROOT / "src/c2_boot_chain_commit.s"))
    if E000_REOPENING:
        sources.append(str(ROOT / "src/c2_kernal_facade_reopen.s"))
    return sources


def scoped_probe_definitions(
        extra_definitions: tuple[str, ...] = ()) -> tuple[str, ...]:
    """Close every opt-in define bundle over its source-owner trigger."""
    if len(extra_definitions) != len(set(extra_definitions)):
        raise RuntimeError("duplicate probe definition")
    result = list(extra_definitions)
    if FULL_MAP_OWNERSHIP and CONVERGENCE_FEATURE not in result:
        result.append(CONVERGENCE_FEATURE)
    for scope in SOURCE_OWNER_SCOPES:
        trigger = str(scope["trigger"])
        companions = set(scope["defines"]) - {trigger}
        if trigger not in result:
            if companions.intersection(result):
                raise RuntimeError(
                    f"source-owner companion escaped trigger: {scope['name']}")
            continue
        for item in scope["defines"]:
            if item not in result:
                result.append(str(item))
    return tuple(result)


def source_owner_scope_gate(
        base_definitions: list[str], extra_definitions: tuple[str, ...],
        sources: list[str]) -> dict[str, object]:
    """Prove optional defines and their source owners share one scope."""
    base = set(base_definitions)
    scoped = set(scoped_probe_definitions(extra_definitions))
    linked_sources = {Path(path).resolve() for path in sources}
    rows: list[dict[str, object]] = []
    for scope in SOURCE_OWNER_SCOPES:
        defines = set(scope["defines"])
        owners = {path.resolve() for path in scope["sources"]}
        if base.intersection(defines):
            raise RuntimeError(
                f"optional source-owned define leaked into base: {scope['name']}")
        selected = str(scope["trigger"]) in scoped
        if (defines <= scoped) != selected:
            raise RuntimeError(
                f"optional define bundle is partial: {scope['name']}")
        if (owners <= linked_sources) != selected:
            raise RuntimeError(
                f"optional source-owner bundle is partial: {scope['name']}")
        rows.append({
            "name": scope["name"],
            "selected": selected,
            "defines": sorted(defines),
            "sources": sorted(path.relative_to(ROOT).as_posix()
                              for path in owners),
        })
    return {"status": "passed-define-and-source-owner-scope-closure",
            "scopes": rows}


def materialized_feature_gate(
        registered_definitions: tuple[str, ...],
        profile_definitions: tuple[str, ...],
        compiler_sources: tuple[str, ...],
        seed_objects: tuple[dict[str, object], ...], *,
        owner_scopes: tuple[dict[str, object], ...] | None = None
        ) -> dict[str, object]:
    """Prove every registered source-owned feature at its real consumers.

    Registration is only the claim source.  The resolved profile, real
    compiler processes and their emitted seed objects are the three
    materialized consumers that make the claim true.
    """
    registered = set(registered_definitions)
    profile = set(profile_definitions)
    compiled = {Path(path).resolve() for path in compiler_sources}
    objects = {
        Path(str(row["source"])).resolve(): row
        for row in seed_objects
        if bool(row.get("exists")) and int(row.get("bytes", 0)) > 0
    }
    rows: list[dict[str, object]] = []
    scopes = SOURCE_OWNER_SCOPES if owner_scopes is None else owner_scopes
    for scope in scopes:
        trigger = str(scope["trigger"])
        if trigger not in registered:
            continue
        defines = {str(item) for item in scope["defines"]}
        owners = {Path(path).resolve() for path in scope["sources"]}
        # The trigger is the compile-profile feature.  Companion definitions
        # in an owner scope describe its closure and may intentionally remain
        # scoped rather than becoming global compiler flags.
        missing_profile = [] if trigger in profile else [trigger]
        missing_sources = sorted(
            path.relative_to(ROOT).as_posix() for path in owners - compiled)
        missing_objects = sorted(
            path.relative_to(ROOT).as_posix() for path in owners - objects.keys())
        if missing_profile or missing_sources or missing_objects:
            raise RuntimeError(
                f"registered feature was not materialized: {scope['name']} "
                f"profile={missing_profile} sources={missing_sources} "
                f"objects={missing_objects}")
        rows.append({
            "name": str(scope["name"]),
            "trigger": trigger,
            "defines": sorted(defines),
            "sources": sorted(path.relative_to(ROOT).as_posix()
                              for path in owners),
            "profile_materialized": True,
            "compiler_materialized": True,
            "seed_objects_materialized": True,
        })
    if not rows:
        raise RuntimeError("no registered source-owned feature was materialized")
    return {
        "status": "passed-feature-generic-real-consumer-materialization",
        "registered_feature_count": len(rows),
        "features": rows,
        "consumers": ["resolved-profile", "compiler-source-list",
                      "seed-object-inventory"],
    }


def source_owner_scope_selftest() -> dict[str, object]:
    dummy = {
        "product_build_id_hex": "0x00000000",
        "artifacts": {"shelf": {"bytes": 0}},
    }
    base = definitions(dummy)
    base_sources = source_list()
    ordinary = source_owner_scope_gate(base, (), base_sources)
    selected = source_owner_scope_gate(
        base, (CONVERGENCE_FEATURE,),
        source_list((CONVERGENCE_FEATURE,)))
    capture_sources = source_list((INPUT_CAPTURE_FEATURE,))
    capture_selected = source_owner_scope_gate(
        base, (INPUT_CAPTURE_FEATURE,), capture_sources)
    ordinary_paths = {Path(path).resolve() for path in base_sources}
    capture_paths = {Path(path).resolve() for path in capture_sources}
    if (INPUT_CAPTURE_BASE_SOURCE.resolve() not in ordinary_paths
            or INPUT_CAPTURE_SOURCE.resolve() in ordinary_paths
            or INPUT_CAPTURE_SOURCE.resolve() not in capture_paths
            or INPUT_CAPTURE_BASE_SOURCE.resolve() in capture_paths):
        raise RuntimeError(
            "input-capture configuration did not change real link inputs")
    rejected: dict[str, str] = {}
    mutations = {
        "parked-defines-restored-in-base": (
            [*base, *CONVERGENCE_DEFINES], (), base_sources),
        "selected-owner-source-removed": (
            base, (CONVERGENCE_FEATURE,),
            [path for path in source_list((CONVERGENCE_FEATURE,))
             if Path(path).resolve() != CONVERGENCE_SOURCES[0].resolve()]),
        "companion-define-without-trigger": (
            base, (CONVERGENCE_DEFINES[1],), base_sources),
        "capture-source-without-trigger": (
            base, (), [*base_sources, str(INPUT_CAPTURE_SOURCE)]),
        "capture-trigger-with-base-source": (
            base, (INPUT_CAPTURE_FEATURE,), base_sources),
    }
    for name, (mutant_base, mutant_extra, mutant_sources) in mutations.items():
        try:
            source_owner_scope_gate(
                mutant_base, mutant_extra, mutant_sources)
        except RuntimeError as error:
            rejected[name] = str(error)
        else:
            raise RuntimeError(f"source-owner scope mutation survived: {name}")
    if len(rejected) != 5:
        raise RuntimeError("source-owner mutation accounting drift")
    return {
        "status": "passed-source-owner-scope-selftest",
        "ordinary": ordinary,
        "selected": selected,
        "input_capture": {
            "status": "passed-real-link-input-membership-toggle",
            "ordinary_owner": INPUT_CAPTURE_BASE_SOURCE.relative_to(
                ROOT).as_posix(),
            "capture_owner": INPUT_CAPTURE_SOURCE.relative_to(ROOT).as_posix(),
            "ordinary_contains_capture": False,
            "capture_contains_base": False,
            "scope": capture_selected,
        },
        "mutations": rejected,
        "mutations_rejected": len(rejected),
    }


def definitions(artifacts: dict[str, object]) -> list[str]:
    result = [
        *canonical_v2_product_defines(),
        "LISP65_VM", "LISP65_EMBED_STDLIB", "LISP65_EMBED_DMA", "LISP65_REPL",
        "HEAP_CELLS=48", "LISP65_MEGA65_MATH_OVERRIDE", "LISP65_F011_GUARD_ASM",
        "VM_CODEBUF=56", "LISP65_SYMPOOL_EXT", "LISP65_SYMVAL_EXT",
        "LISP65_NAMEOFF_EXT", "GC_ROOTS=128", "LISP65_MARK_BITMAP", "LISP65_EXT_HEAP",
        "LISP65_SCREEN_DRIVER", "LISP65_VM_SCREEN_PRIMS", "LISP65_VM_STDLIB_IO_WRAPPERS",
        "LISP65_VM_GLOBAL_PRIMS", "LISP65_MACROEXPAND_PRIM", "LISP65_TREEWALK_STDLIB_BRIDGES",
        "LISP65_OUTPUT_WRAPPERS_IN_STDLIB", "LISP65_SCREEN_BULK_P_IN_STDLIB",
        "LISP65_TREEWALK_STRIP", "MEGA65_F011_LOAD", "MEGA65_F011_WRITE", "IO_BUF_MAX=1",
        "EXT_CELLS=1024", "LISP65_NURSERY_HYSTERESIS=192", "LISP65_STRING_ARENA",
        "LISP65_FIRST_CLASS_BUFFER", "STR_ARENA_SIZE=0x2480", "DISK_EXT_BASE=0x6900",
        "DISK_EXT_FILE_MAX=0x9600", "LISP65_COMPILE_STRING", "LISP65_SYMFN_EXT",
        "SYMPOOL_EXT_OFF=0xc680", "NAMEPOOL=10208", "MAX_SYM=752", "VM_DIR_MAX=608",
        "REPL_BUF_MAX=192", "HIST_MAX=64", "LISP65_REPL_HISTORY_IN_BUF",
        "LISP65_REPL_BANNER_REQUIRED", "LISP65_STDLIB_BOOT_OVERLAY_CODE",
        "LISP65_STAGED_BOOT_OVERLAY", "LISP65_RUNTIME_OVERLAY",
        "LISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES",
        "LISP65_C2_RUNTIME_LIFETIME_FAMILIES", "LISP65_STACK_GUARD",
        "LISP65_C2_PRODUCT_CUT", "LISP65_C2_SLICED_APPEND", "C2_STREAM_PRODUCT_V3=1",
        "LISP65_C2_KERNAL_UNMAP",
        f"LISP65_C2_PRODUCT_BUILD_ID={artifacts['product_build_id_hex']}UL",
        f"LISP65_C2_PRODUCT_SHELF_BYTES={artifacts['artifacts']['shelf']['bytes']}UL",
        "LISP65_ERROR_OVERLAY",
        f"LISP65_ERROR_OVERLAY_SLOT={SESSION_SERVICE_SLOT_BASE}",
        f"LISP65_RUNTIME_ISLAND_INSTALL_SLOT={BOOT_ISLAND_SLOT}",
        f"LISP65_RUNTIME_ISLAND_CARRIER_SLOT={BOOT_ISLAND_CARRIER_SLOT}",
        f"LISP65_BUFFER_OVERLAY_READ_SLOT={SESSION_SERVICE_SLOT_BASE + 1}",
        f"LISP65_BUFFER_OVERLAY_WRITE_SLOT={SESSION_SERVICE_SLOT_BASE + 2}",
        f"LISP65_BUFFER_OVERLAY_ALLOC_SLOT={SESSION_SERVICE_SLOT_BASE + 3}",
    ]
    if INTERN_SESSION_SERVICE:
        result.extend([
            "LISP65_INTERN_SESSION_SERVICE",
            f"LISP65_INTERN_SERVICE_SLOT={SESSION_SERVICE_SLOT_BASE + 4}",
        ])
    if BANK3_STAGING_SLICES:
        result.append(
            f"LISP65_C2_BANK3_STAGE_SESSION_SLOT={BOOT_BANK3_STAGE_SLOT}")
    return result


def compile_link(out: Path, name: str, headers: list[Path],
                 artifacts: dict[str, object], *,
                 probe_definitions: tuple[str, ...] = (),
                 final_inventory: bool = True,
                 deterministic_object_prefix: list[dict[str, object]] | None =
                 None,
                 deterministic_object_directory: Path | None = None) -> Path:
    def checkout_arg(path: Path) -> str:
        """Keep Clang's implicit include buffer independent of checkout path."""
        try:
            return path.relative_to(ROOT).as_posix()
        except ValueError:
            return str(path)

    target = out / name
    target_arg = checkout_arg(target)
    product_definitions = definitions(artifacts)
    scoped_definitions = scoped_probe_definitions(probe_definitions)
    compiler_sources = source_list(probe_definitions)
    input_capture_consumption_closure(
        probe_definitions, compiler_sources)
    source_owner_scope_gate(
        product_definitions, probe_definitions, compiler_sources)
    require_exact_v2_profile(product_definitions)
    compiler = str(TOOLCHAIN / "mos-mega65-clang")
    compile_flags = [
        "-Oz", "-Wall",
        # Clang otherwise injects the absolute current checkout into cc1 as
        # its file/debug/coverage compilation directory.  llvm-mos encodes
        # that directory-dependent SourceLocation space in inline-assembly
        # !srcloc metadata, which is enough to perturb full-LTO layout.
        "-ffile-compilation-dir=.",
        "-fdebug-compilation-dir=.",
        "-fcoverage-compilation-dir=.",
    ]
    link_flags: list[str] = []
    lto_rng_seed = os.environ.get("LISP65_LTO_RNG_SEED")
    if lto_rng_seed is not None:
        if not lto_rng_seed.isdecimal():
            raise RuntimeError(
                "LISP65_LTO_RNG_SEED must be an unsigned decimal integer")
        # llvm-mos uses a randomized worklist in both the per-module and LTO
        # optimizer pipelines.  A source-identical whole-program link can
        # otherwise choose a different zero-page allocation.  Bind both
        # processes: -mllvm reaches clang -cc1, while the linker form reaches
        # the full-LTO backend owned by ld.lld.
        compile_flags.extend(["-mllvm", f"-rng-seed={lto_rng_seed}"])
        link_flags.extend([
            "-Wl,-mllvm", f"-Wl,-rng-seed={lto_rng_seed}"])
    lto_threads = os.environ.get("LISP65_LTO_THREADS")
    if lto_threads is not None:
        if not lto_threads.isdecimal() or int(lto_threads) < 1:
            raise RuntimeError(
                "LISP65_LTO_THREADS must be a positive decimal integer")
        link_flags.extend([
            f"-Wl,--threads={lto_threads}",
            f"-Wl,--lto-partitions={lto_threads}",
        ])
    compile_flags.extend(
        f"-D{item}" for item in (*product_definitions, *scoped_definitions))
    consumed_flags, consumed_report = compiler_consumed_static_header_flags(
        out, target)
    compile_flags.extend(consumed_flags)
    for header in headers:
        compile_flags.extend(["-include", checkout_arg(header)])
    compile_flags.extend([
        "-I", checkout_arg(ROOT / "src"),
        "-I", checkout_arg(ROOT / "scripts"),
        "-I", checkout_arg(ROOT / "build/c2.2/substitution"),
        "-I", checkout_arg(out),
        "-I", checkout_arg(ROOT / "build/bytecode"),
    ])
    for directory in EXTRA_INCLUDE_DIRS:
        compile_flags.extend(["-I", checkout_arg(directory)])
    feature_consumption_report = compiler_consumed_feature_profile_gate(
        compile_flags, target)
    link_flags.extend([
        "-Wl,--icf=all",
        "-Wl,--emit-relocs",
        "-Wl,--lto-obj-path=" + target_arg + ".lto.o",
        "-Wl,--orphan-handling=warn",
        "-Wl,--defsym=__udivhi3=lisp65_hw_udivhi3",
        "-Wl,--defsym=__umodhi3=lisp65_hw_umodhi3",
        "-Wl,--defsym=__udivmodhi4=lisp65_hw_udivmodhi4",
        "-Wl,--defsym=__mulhi3=lisp65_hw_mulhi3",
        "-Wl,--defsym=__divhi3=lisp65_hw_divhi3",
        "-Wl,--defsym=__modhi3=lisp65_hw_modhi3",
    ])
    if FULL_MAP_OWNERSHIP:
        # The platform link.ld includes c.ld by search path.  Put the generated
        # full-map owner before llvm-mos' common/lib directory so the inherited
        # ordinary stanzas do not exist in this link at all.
        link_flags.append(
            "-Wl,-L," + checkout_arg(out / "full-map-linker"))
    link_flags.extend([
        "-Wl,-T," + checkout_arg(out / "c2-substitution.ld"),
        "-Wl,--defsym=__lisp65_workbench_required_boot_stack_param=512",
        "-Wl,--defsym=__lisp65_workbench_required_runtime_stack_param=1450",
        "-Wl,--defsym=__lisp65_workbench_required_post_boot_reserve_param=1024",
        "-Wl,--defsym=__lisp65_workbench_runtime_overlay_vma_param=" + RUNTIME_VMA,
        "-Wl,--defsym=__lisp65_workbench_runtime_overlay_max_vma_param=" + RUNTIME_VMA,
        "-Wl,--defsym=__lisp65_error_overlay_max_bytes_param=1320",
        "-Wl,--defsym=__lisp65_workbench_screen_base_param=0x0800",
        "-Wl,--defsym=__lisp65_workbench_screen_columns_param=80",
        "-Wl,--defsym=__lisp65_workbench_screen_rows_param=50",
        "-Wl,--defsym=__lisp65_workbench_screen_cell_bytes_param=1",
        "-Wl,--defsym=__lisp65_resident_island_base_param=0x1800",
        "-Wl,--defsym=__lisp65_resident_island_limit_param=0x2000",
        "-Wl,--defsym=__lisp65_resident_island_payload_capacity_param=2048",
        "-Wl,-Map=" + target_arg + ".map",
        "-o", target_arg,
    ])
    # The selected far service deliberately shares CPU VMA $6000..$7fff with
    # the ordinary Bank-0 underlay and has a distinct physical Bank-2 LMA.
    # The complete flag pair is part of the same opt-in closure as its sources
    # and linker layout; the canonical scope receives neither flag.
    link_flags.extend(ownership_link_flags(probe_definitions))
    deterministic_objects = (
        os.environ.get("LISP65_DETERMINISTIC_OBJECTS") == "1")
    if deterministic_objects:
        object_root = (deterministic_object_directory
                       if deterministic_object_directory is not None
                       else out / (".canonical-objects-" + target.stem))
        if object_root.parent != out:
            raise RuntimeError(
                "deterministic object directory escaped producer output")
        sources = [Path(item) for item in compiler_sources]
        resumed_names: set[str] = set()
        if deterministic_object_prefix is None:
            object_root.mkdir()
        else:
            if not object_root.is_dir() or object_root.is_symlink():
                raise RuntimeError(
                    "deterministic object-prefix directory absent")
            expected_names = [
                f"{index:03d}-{source.stem}{source.suffix}.o"
                for index, source in enumerate(
                    sources[:len(deterministic_object_prefix)])
            ]
            supplied_names = [str(row.get("name"))
                              for row in deterministic_object_prefix]
            existing_names = sorted(
                path.name for path in object_root.iterdir()
                if path.is_file() and not path.is_symlink())
            if (supplied_names != expected_names
                    or existing_names != expected_names):
                raise RuntimeError(
                    "deterministic object prefix is not exact and contiguous")
            for row, name_expected in zip(
                    deterministic_object_prefix, expected_names, strict=True):
                path = object_root / name_expected
                raw = path.read_bytes()
                if (int(row.get("bytes", -1)) != len(raw)
                        or str(row.get("sha256")) !=
                            hashlib.sha256(raw).hexdigest()):
                    raise RuntimeError(
                        f"deterministic object prefix identity drift: {path}")
                resumed_names.add(name_expected)
        bitcode_objects: list[str] = []
        native_objects: list[str] = []
        for index, source in enumerate(sources):
            source_arg = source.relative_to(ROOT).as_posix()
            object_path = object_root / (
                f"{index:03d}-{source.stem}{source.suffix}.o")
            object_arg = object_path.relative_to(ROOT).as_posix()
            if object_path.name not in resumed_names:
                source_flags = (
                    ["-Qunused-arguments", *compile_flags]
                    if source.suffix == ".s" else compile_flags)
                run([
                    compiler, *source_flags, "-c", source_arg,
                    "-o", object_arg,
                ])
            if source.suffix == ".c":
                bitcode_objects.append(object_arg)
            else:
                native_objects.append(object_arg)

        # Full LTO over a list of bytecode modules is not reproducible in the
        # llvm-mos 0.1.0 toolchain even with one backend thread and a fixed
        # RNG seed: byte-identical input objects produced different zero-page
        # allocation and text layout on consecutive links.  Canonical media
        # must not inherit that private ordering truth.  Merge the fixed,
        # ordered C modules into one bitcode module first, then perform the
        # same whole-program LTO over that single module plus the assembler
        # objects.  This preserves cross-TU optimization while removing the
        # unstable multi-module worklist.
        llvm_link = Path(
            os.environ.get("LISP65_LLVM_LINK", "/usr/bin/llvm-link"))
        if not llvm_link.is_file() or not os.access(llvm_link, os.X_OK):
            raise RuntimeError(
                f"deterministic LLVM bitcode linker absent: {llvm_link}")
        combined_path = object_root / "combined-c.bc"
        combined_arg = combined_path.relative_to(ROOT).as_posix()
        run([
            str(llvm_link), *bitcode_objects, "-o", combined_arg,
        ])
        command = [
            compiler, "-Oz", combined_arg, *native_objects, *link_flags,
        ]
    else:
        command = [
            compiler, *compile_flags, *compiler_sources,
            *link_flags,
        ]
    if os.environ.get("LISP65_DISABLE_LINK_ASLR") == "1":
        setarch = Path("/usr/bin/setarch")
        if not setarch.is_file() or not os.access(setarch, os.X_OK):
            raise RuntimeError(
                f"deterministic link ASLR wrapper absent: {setarch}")
        command = [
            str(setarch), os.uname().machine, "-R", *command,
        ]
    run_link_with_exact_orphan_wrapper(out, target, command)
    input_capture_seed_size_witness(
        _readobj_sections(Path(str(target) + ".elf")), probe_definitions)
    if consumed_report is not None:
        expected_flags = [
            "-include", consumed_report["force_include_order"][0],
            "-include", consumed_report["force_include_order"][1],
        ]
        positions = [
            index for index in range(len(compile_flags) - 3)
            if compile_flags[index:index + 4] == expected_flags]
        if len(positions) != 1:
            raise RuntimeError(
                "bound candidate header escaped the real compiler flags")
        consumed_report["actual_force_include_flags"] = expected_flags
        receipt = Path(str(target) + ".compiler-input-consumption.json")
        write(receipt, json.dumps(
            consumed_report, indent=2, sort_keys=True) + "\n")
    if feature_consumption_report is not None:
        receipt = Path(str(target) + ".compiler-feature-consumption.json")
        write(receipt, json.dumps(
            feature_consumption_report, indent=2, sort_keys=True) + "\n")
    if final_inventory:
        final_section_inventory_gate(out, target)
    lto_partition_metadata_gate(out, target)
    return target


def write_v2_profile_report(out: Path, artifacts: dict[str, object]) -> dict[str, object]:
    report = v2_profile_report(definitions(artifacts))
    write(out / "v2-product-profile-parity.json",
          json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def tool(name: str, *args: str) -> None:
    run([sys.executable, str(ROOT / "tools/host-lisp" / name), *args])


def _resolved_profile_value(path: Path, name: str) -> str:
    rows = [
        line.split("=", 1)[1]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith(name + "=")
    ]
    if len(rows) != 1:
        raise RuntimeError(
            f"resolved profile has no unique {name} row: {path}")
    return rows[0]


def _boot_inventory_rows(specs: list[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for spec in specs:
        fields = spec.split(":")
        if len(fields) < 3:
            raise RuntimeError(f"malformed Boot inventory spec: {spec}")
        rows.append({
            "id": int(fields[0], 0),
            "name": fields[1],
            "section": fields[2],
        })
    return rows


def _function_rows(
        truth: ASM_LEAF_ABI.ElfTruth, rows: list[dict[str, object]],
        name: str) -> list[dict[str, object]]:
    symbol = truth.symbol(name)
    return [
        row for row in rows
        if row["section"] == symbol.section
        and symbol.value <= int(row["address"]) < symbol.value + symbol.bytes
    ]


def _linked_function_closure(
        truth: ASM_LEAF_ABI.ElfTruth, rows: list[dict[str, object]],
        entry_name: str) -> set[str]:
    """Derive the direct-control closure rooted at a linked function."""
    functions = {
        symbol.value: symbol.name for symbol in truth.symbols
        if symbol.symbol_type == "Function" and symbol.bytes > 0
        and symbol.section not in ("", "Undefined", "Absolute")
    }
    pending = [entry_name]
    visited: set[str] = set()
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        visited.add(name)
        for row in _function_rows(truth, rows, name):
            if row["opcode"] not in ("jsr", "jmp"):
                continue
            match = re.match(r"^\$([0-9a-f]+)\b", str(row["operand"]))
            target = functions.get(int(match.group(1), 16)) if match else None
            if target is not None and target not in visited:
                pending.append(target)
    return visited


def _validate_linked_seam_owners(
        entry_name: str, closure: set[str],
        calls: list[dict[str, object]]) -> str:
    if not calls:
        raise RuntimeError("Boot installer closure lacks linked family seam")
    owners = {str(row["owner"]) for row in calls}
    if len(owners) != 1 or not owners <= closure:
        raise RuntimeError(
            f"Boot family seam has absent or foreign owners: {sorted(owners)}")
    return next(iter(owners))


def _linked_seam_owner_mutations(
        entry_name: str, closure: set[str],
        calls: list[dict[str, object]]) -> dict[str, str]:
    cases = {
        "missing-seam-owner": [],
        "foreign-seam-owner": [
            *calls, {"owner": "foreign_owner", "address": 0}],
    }
    rejected: dict[str, str] = {}
    for name, mutant in cases.items():
        try:
            _validate_linked_seam_owners(entry_name, closure, mutant)
        except RuntimeError:
            rejected[name] = "rejected"
    if len(rejected) != len(cases):
        raise RuntimeError(
            f"Boot seam-owner mutation survived: {set(cases) - set(rejected)}")
    # The semantic owner is derived from the linked closure.  Historical
    # candidates placed the seam in a successor body; the nested-MAP repair
    # lawfully restores it to the entry body.  Pinning either topology as the
    # only valid one must be mutation-red while missing/foreign owners remain
    # rejected above.
    if {str(row["owner"]) for row in calls} == {entry_name}:
        rejected["successor-owner-pin"] = "rejected"
    else:
        rejected["old-entry-symbol-pin"] = "rejected"
    return rejected


def _linked_c2_lite_boot_slot_evidence(elf: Path) -> dict[str, object]:
    """Read the two compiled Boot slot constants from the final ELF.

    These values are deliberately obtained from the code the linker emitted,
    not reconstructed from the packer inventory.  The installer call passes
    its slot through __rc3; the cold Island body compares the authenticated
    carrier record id before accepting DATA_ONLY.  Both operations are unique
    in the strict C2-lite product.
    """
    symbols = defined_symbols(elf)
    required = (
        "vm_runtime_overlay_install_island",
        "vm_runtime_overlay_exec_family",
        "vm_resident_island_install",
        "__rc3",
    )
    missing = [name for name in required if name not in symbols]
    if missing:
        raise RuntimeError(
            f"Boot inventory linked-slot symbols absent: {missing}")
    truth = ASM_LEAF_ABI.ElfTruth.read(
        elf, llvm_readobj=TOOLCHAIN / "llvm-readobj")
    completed = run([
        str(TOOLCHAIN / "llvm-objdump"), "-d", "--no-show-raw-insn",
        str(elf),
    ], capture=True)
    rows = CRC_CODEGEN.disassembly_rows(completed)

    entry_name = "vm_runtime_overlay_install_island"
    closure = _linked_function_closure(truth, rows, entry_name)
    seam = symbols["vm_runtime_overlay_exec_family"]
    seam_calls: list[dict[str, object]] = []
    for owner in sorted(closure):
        for row in _function_rows(truth, rows, owner):
            if row["opcode"] == "jsr" \
                    and re.match(rf"^\${seam:x}\b", str(row["operand"])):
                seam_calls.append({"owner": owner, "address": row["address"]})
    owner = _validate_linked_seam_owners(entry_name, closure, seam_calls)
    install_body = _function_rows(truth, rows, owner)
    call_indices = [index for index, row in enumerate(install_body)
                    if int(row["address"]) == int(seam_calls[0]["address"])]
    if len(call_indices) != 1:
        raise RuntimeError("Boot family seam is not unique in its linked owner")
    call_index = call_indices[0]
    rc3 = symbols["__rc3"]
    stores = [
        index for index, row in enumerate(install_body[:call_index])
        if row["opcode"] == "stx"
        and re.match(rf"^\${rc3:x}\b", str(row["operand"]))
    ]
    if not stores:
        raise RuntimeError(
            "Boot installer lacks linked __rc3 slot writer")
    store_index = stores[-1]
    x_writers = [
        row for row in install_body[:store_index]
        if row["opcode"] in ("ldx", "plx", "tax")
    ]
    if not x_writers or x_writers[-1]["opcode"] != "ldx" \
            or not re.fullmatch(r"#\$[0-9a-f]+",
                                str(x_writers[-1]["operand"])):
        raise RuntimeError(
            "Boot installer slot is not one dominating linked immediate")
    install_slot = int(str(x_writers[-1]["operand"])[2:], 16)

    carrier = truth.symbol("vm_resident_island_install")
    carrier_body = [
        row for row in rows
        if row["section"] == carrier.section
        and carrier.value <= int(row["address"]) < carrier.value + carrier.bytes
    ]
    carrier_compares = [
        int(str(row["operand"])[2:], 16)
        for row in carrier_body
        if row["opcode"] == "cmp"
        and re.fullmatch(r"#\$[0-9a-f]+", str(row["operand"]))
    ]
    # Slot ids are dense and the carrier follows the installer.  Requiring
    # exactly one comparison against that successor avoids treating unrelated
    # format constants as identities.
    carrier_slot = install_slot + 1
    if carrier_compares.count(carrier_slot) != 1:
        raise RuntimeError(
            "Boot carrier slot lacks one exact linked compare: "
            f"installer={install_slot} compares={carrier_compares}")
    return {"slots": {"installer": install_slot, "carrier": carrier_slot},
        "entry": entry_name, "closure": sorted(closure),
        "seam_owner": owner,
        "owner_projection": "derived from final linked entry closure",
        "seam_calls": [{"owner": str(row["owner"]),
                         "address": f"0x{int(row['address']):04x}"}
                        for row in seam_calls],
        "mutations_rejected": _linked_seam_owner_mutations(
            entry_name, closure, seam_calls)}


def _linked_c2_lite_boot_slots(elf: Path) -> dict[str, int]:
    evidence = _linked_c2_lite_boot_slot_evidence(elf)
    return {name: int(value) for name, value in evidence["slots"].items()}


def _validate_boot_inventory_model(
        profile_count: int, features: tuple[str, ...],
        expected: list[dict[str, object]],
        observed: list[dict[str, object]],
        linked_slots: dict[str, int] | None) -> None:
    if profile_count != len(expected):
        raise RuntimeError(
            "Boot profile/spec count divergence: "
            f"profile={profile_count} specs={len(expected)}")
    if expected != observed:
        raise RuntimeError(
            "Boot spec/packed-record inventory divergence: "
            f"expected={expected} observed={observed}")
    ids = [int(row["id"]) for row in expected]
    if ids != list(range(len(expected))):
        raise RuntimeError(f"Boot slots are not dense and ordered: {ids}")
    if "LISP65_C2_LITE_BANK2_STAGING" not in features:
        return
    names = [str(row["name"]) for row in expected]
    required_tail = [
        "c2-decode-03b",
        "bank3-stage-session",
        "resident-island-installer",
        "resident-island-image",
    ]
    if profile_count != 12 or names[-4:] != required_tail:
        raise RuntimeError(
            "C2-lite Bank-2 Boot inventory tail/count drift: "
            f"count={profile_count} tail={names[-4:]}")
    if linked_slots != {"installer": 10, "carrier": 11}:
        raise RuntimeError(
            f"linked Boot installer/carrier slots drift: {linked_slots}")


def boot_inventory_truth_gate(
        out: Path, target: Path, profile: Path, manifest: Path,
        suffix: str) -> dict[str, object]:
    """Bind profile shape, packer records and final linked slots together."""
    features = tuple(
        item for item in _resolved_profile_value(
            profile, "feature_defines").split(",") if item)
    profile_count = int(_resolved_profile_value(
        profile, "boot_family_slice_count"), 0)
    expected = _boot_inventory_rows(BOOT_SLICE_SPECS + BOOT_DATA_SPECS)
    packed = json.loads(manifest.read_text(encoding="utf-8"))
    observed = [{
        "id": int(row["id"]),
        "name": str(row["name"]),
        "section": str(row["section"]),
    } for row in packed["slices"]]
    linked_slots = (
        _linked_c2_lite_boot_slots(Path(str(target) + ".elf"))
        if "LISP65_C2_LITE_BANK2_STAGING" in features else None)
    _validate_boot_inventory_model(
        profile_count, features, expected, observed, linked_slots)

    mutations: dict[str, tuple[
        int, tuple[str, ...], list[dict[str, object]],
        list[dict[str, object]], dict[str, int] | None]] = {
        "profile-count-minus-one": (
            profile_count - 1, features, expected, observed, linked_slots),
        "missing-phase03b": (
            profile_count, features, expected,
            [row for row in observed if row["name"] != "c2-decode-03b"],
            linked_slots),
        "installer-carrier-swapped": (
            profile_count, features, expected,
            [
                ({**row, "name": "resident-island-image"}
                 if row["name"] == "resident-island-installer" else
                 {**row, "name": "resident-island-installer"}
                 if row["name"] == "resident-island-image" else row)
                for row in observed
            ], linked_slots),
        "unregistered-extra-record": (
            profile_count, features, expected,
            [*observed, {"id": len(observed), "name": "extra",
                         "section": ".extra"}],
            linked_slots),
        "linked-installer-slot-minus-one": (
            profile_count, features, expected, observed,
            ({"installer": linked_slots["installer"] - 1,
              "carrier": linked_slots["carrier"]}
             if linked_slots else None)),
    }
    rejected: dict[str, str] = {}
    if "LISP65_C2_LITE_BANK2_STAGING" in features:
        for name, arguments in mutations.items():
            try:
                _validate_boot_inventory_model(*arguments)
            except RuntimeError:
                rejected[name] = "rejected"
        if len(rejected) != len(mutations):
            raise RuntimeError(
                f"Boot inventory mutation survived: {set(mutations) - set(rejected)}")

    report = {
        "format": "lisp65-boot-inventory-one-truth-v1",
        "status": "passed-profile-record-and-linked-slot-one-truth",
        "profile_boot_family_slice_count": profile_count,
        "feature_defines": list(features),
        "records": observed,
        "linked_slots": linked_slots,
        "mutations_rejected": rejected,
        "invariant": (
            "The resolved compiler profile count, the packer's exact named "
            "record inventory and the linked installer/carrier slots consume "
            "one Boot inventory truth. Missing, extra, renamed or shifted "
            "records stop before publication."),
    }
    write(
        out / f"boot-inventory-one-truth-{suffix}.json",
        json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def overlay_pack_family(out: Path, target: Path, contract: Path,
                        family: str, suffix: str) -> tuple[Path, Path]:
    nm = str(TOOLCHAIN / "llvm-nm")
    elf = Path(str(target) + ".elf")
    try:
        runtime_vma = ElfTruth.read(
            elf, llvm_readobj=TOOLCHAIN / "llvm-readobj").symbol(
                "__lisp65_workbench_runtime_overlay_vma")
    except ElfTruthError as error:
        raise RuntimeError("missing runtime-overlay VMA") from error
    if runtime_vma.section in ("Undefined", ""):
        raise RuntimeError("undefined runtime-overlay VMA")
    args = [
        "pack", "--elf", str(elf), "--nm", nm,
        "--objcopy", str(TOOLCHAIN / "llvm-objcopy"), "--profile", PROFILE,
        "--abi-contract", str(contract), "--vma", hex(runtime_vma.value),
        "--max-slice-bytes", "1792", "--format-version",
        str(RUNTIME_OVERLAY_FORMAT_VERSION),
    ]
    if RUNTIME_OVERLAY_FORMAT_VERSION == 4:
        # v4 records bind the already-resolved runtime source, not a region
        # choice for the hot dispatcher.  Boot consumes its staged Attic
        # family; Session consumes the verified Bank-3 plane.
        args.extend([
            "--main-source-base",
            "0x08200000" if family == "boot" else "0x00030000",
            "--overflow-source-base", "0x0005bd00",
        ])
    specs = BOOT_SLICE_SPECS if family == "boot" else SESSION_SLICE_SPECS
    for spec in specs:
        args.extend(["--slice", spec])
    if family == "boot":
        for spec in BOOT_DATA_SPECS:
            args.extend(["--data-slice", spec])
    image = out / f"runtime-overlays-{family}-{suffix}.bin"
    overflow_image = (
        out / f"runtime-overlays-{family}-{suffix}-region1.bin")
    manifest = out / f"runtime-overlays-{family}-{suffix}.json"
    temporary_header = out / f"runtime-overlay-{family}-{suffix}.h"
    args.extend([
        "--image", str(image), "--manifest", str(manifest),
        "--header", str(temporary_header), "--header-mode", "write",
    ])
    if RUNTIME_OVERLAY_FORMAT_VERSION == 4:
        args.extend(["--overflow-image", str(overflow_image)])
    tool("runtime_overlay_bank.py", *args)
    value = json.loads(manifest.read_text(encoding="utf-8"))
    value["lifetime_family"] = family
    value["storage"]["address"] = 0x08200000 if family == "boot" else 0x08000000
    value["storage"]["lifetime"] = (
        "generation-invalid-through-phase-3" if family == "boot"
        else "post-phase-3-session"
    )
    if RUNTIME_OVERLAY_FORMAT_VERSION == 4:
        value["overflow_storage"]["lifetime"] = (
            "unused-empty-region" if family == "boot"
            else "post-phase-3-session")
    write(manifest, json.dumps(value, indent=2, sort_keys=True) + "\n")
    if family == "boot":
        boot_inventory_truth_gate(
            out, target, contract, manifest, suffix)
    return image, manifest


def _verifier_tuple(manifest: dict[str, object], slot: int) -> tuple[int, int, int, int]:
    records = manifest["slices"]
    record = next(item for item in records if item["id"] == slot)
    return (record["file_offset"], record["file_size"],
            record["entry_offset"], record["crc16"])


def verifier_binding_bytes(boot_manifest: Path,
                           session_manifest: Path) -> bytes:
    boot = json.loads(boot_manifest.read_text(encoding="utf-8"))
    session = json.loads(session_manifest.read_text(encoding="utf-8"))
    values: list[int] = []
    for manifest in (boot, session):
        for slot in (0, 1):
            values.extend(_verifier_tuple(manifest, slot))
    if len(values) != 16 or any(not 0 <= value <= 0xffff for value in values):
        raise RuntimeError("runtime verifier tuple lies outside its 32-byte table")
    return struct.pack("<16H", *values)


def family_stage_binding_bytes(boot_manifest: Path,
                               session_manifest: Path) -> bytes:
    values: list[int] = []
    for path in (boot_manifest, session_manifest):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        storage = manifest["storage"]
        values.extend((int(storage["size"]), int(storage["crc16"])))
    if len(values) != 4 or any(not 1 <= value <= 0xffff for value in values):
        raise RuntimeError("runtime-family stage tuple lies outside positive u16")
    return struct.pack("<4H", *values)


def _validate_family_artifact(image: Path, manifest: dict[str, object],
                              label: str) -> None:
    data = image.read_bytes()
    region_data = {0: data}
    overflow = manifest.get("overflow_storage")
    if overflow is not None:
        overflow_path = image.parent / str(overflow["file"])
        if not overflow_path.is_file():
            raise RuntimeError(f"{label}: overflow image absent")
        overflow_data = overflow_path.read_bytes()
        if overflow["used"] != len(overflow_data):
            raise RuntimeError(f"{label}: overflow used size mismatch")
        if overflow["sha256"] != hashlib.sha256(overflow_data).hexdigest():
            raise RuntimeError(f"{label}: overflow SHA-256 mismatch")
        if overflow["crc16"] != crc16(overflow_data):
            raise RuntimeError(f"{label}: overflow CRC-16 mismatch")
        region_data[1] = overflow_data
    storage = manifest["storage"]
    if storage["size"] != len(data):
        raise RuntimeError(f"{label}: storage size does not match image")
    if storage["sha256"] != hashlib.sha256(data).hexdigest():
        raise RuntimeError(f"{label}: storage SHA-256 does not match image")
    if storage["crc16"] != crc16(data):
        raise RuntimeError(f"{label}: storage CRC-16 does not match image")
    for record in manifest["slices"]:
        region_id = int(record.get("region_id", 0))
        if region_id not in region_data:
            raise RuntimeError(
                f"{label}: slice {record['id']} names absent region {region_id}")
        selected = region_data[region_id]
        start = record["file_offset"]
        end = start + record["file_size"]
        if start < 0 or end > len(selected) or end <= start:
            raise RuntimeError(f"{label}: slice {record['id']} range is invalid")
        payload = selected[start:end]
        if record["sha256"] != hashlib.sha256(payload).hexdigest():
            raise RuntimeError(f"{label}: slice {record['id']} SHA-256 mismatch")
        if record["crc16"] != crc16(payload):
            raise RuntimeError(f"{label}: slice {record['id']} CRC-16 mismatch")


def _family_identity_equal(reference_image: Path, reference_manifest: Path,
                           candidate_image: Path, candidate_manifest: Path,
                           label: str) -> int:
    reference_data = reference_image.read_bytes()
    candidate_data = candidate_image.read_bytes()
    reference = json.loads(reference_manifest.read_text(encoding="utf-8"))
    candidate = json.loads(candidate_manifest.read_text(encoding="utf-8"))
    _validate_family_artifact(reference_image, reference, label + ":reference")
    _validate_family_artifact(candidate_image, candidate, label + ":candidate")
    if reference["slices"] != candidate["slices"]:
        raise RuntimeError(f"{label}: runtime-family record field drift")
    if reference_data != candidate_data:
        raise RuntimeError(f"{label}: runtime-family payload drift")
    for side, image, manifest in (
            ("reference", reference_image, reference),
            ("candidate", candidate_image, candidate)):
        overflow = manifest.get("overflow_storage")
        if overflow is not None:
            payload = (image.parent / str(overflow["file"])).read_bytes()
            if side == "reference":
                reference_overflow = payload
            else:
                candidate_overflow = payload
    reference_overflow_storage = reference.get("overflow_storage")
    candidate_overflow_storage = candidate.get("overflow_storage")
    normalized_reference = (
        {key: value for key, value in reference_overflow_storage.items()
         if key != "file"} if reference_overflow_storage is not None else None)
    normalized_candidate = (
        {key: value for key, value in candidate_overflow_storage.items()
         if key != "file"} if candidate_overflow_storage is not None else None)
    if normalized_reference != normalized_candidate:
        raise RuntimeError(f"{label}: overflow storage field drift")
    if reference.get("overflow_storage") is not None and (
            reference_overflow != candidate_overflow):
        raise RuntimeError(f"{label}: overflow payload drift")
    return len(reference["slices"])


def _family_identity_negative_selftest(image: Path, manifest: Path) -> str:
    value = json.loads(manifest.read_text(encoding="utf-8"))
    record = value["slices"][-1]
    region_id = int(record.get("region_id", 0))
    selected = (
        image if region_id == 0
        else image.parent / str(value["overflow_storage"]["file"]))
    data = bytearray(selected.read_bytes())
    offset = record["file_offset"] + record["file_size"] // 2
    data[offset] ^= 0x01
    mutated = selected.with_name(selected.name + ".negative")
    write(mutated, bytes(data))
    try:
        mutated_manifest = json.loads(json.dumps(value))
        if region_id == 0:
            mutated_manifest["storage"]["file"] = mutated.name
        else:
            mutated_manifest["overflow_storage"]["file"] = mutated.name
        _validate_family_artifact(
            mutated if region_id == 0 else image, mutated_manifest,
                                  "mutated-payload-negative")
    except RuntimeError:
        mutated.unlink(missing_ok=True)
        return "rejected"
    mutated.unlink(missing_ok=True)
    raise AssertionError("mutated runtime-family payload was accepted")


def runtime_family_identity_gate(
        out: Path,
        unbound_boot: tuple[Path, Path], unbound_session: tuple[Path, Path],
        final_boot: tuple[Path, Path], final_session: tuple[Path, Path]
) -> dict[str, object]:
    boot_records = _family_identity_equal(
        unbound_boot[0], unbound_boot[1], final_boot[0], final_boot[1], "boot")
    session_records = _family_identity_equal(
        unbound_session[0], unbound_session[1],
        final_session[0], final_session[1], "session")
    negative = _family_identity_negative_selftest(final_session[0], final_session[1])
    report = {
        "format": "lisp65-runtime-family-total-identity-v1",
        "status": "passed",
        "comparison": "all-record-fields-and-all-payload-bytes",
        "boot_records": boot_records,
        "session_records": session_records,
        "record_occurrences": boot_records + session_records,
        "mutated_payload_negative": negative,
        "claim_limit": (
            "Pack/repack identity from one ELF and a pinned negative mutation; "
            "hardware execution is not claimed."
        ),
    }
    write(out / "runtime-family-total-identity.json",
          json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def patch_verifier_binding_table(out: Path, target: Path,
                                 boot_manifest: Path,
                                 session_manifest: Path, *,
                                 expected_base: int = VERIFIER_BINDING_BASE
                                 ) -> dict[str, object]:
    elf = Path(str(target) + ".elf")
    sections = section_table(elf)
    symbols = defined_symbols(elf)
    section = sections.get(VERIFIER_BINDING_SECTION)
    binding_bytes_count = runtime_binding_bytes()
    if not section or section["bytes"] != binding_bytes_count:
        raise RuntimeError(f"verifier binding section geometry red: {section}")
    start = section["address"]
    if start != expected_base:
        raise RuntimeError(
            f"verifier binding address drift 0x{start:04x} != "
            f"0x{expected_base:04x}")
    expected_symbols = {
        "__lisp65_rtov_verifier_bindings_start": start,
        "rtov_boot_verifiers": start,
        "rtov_verifiers": start + 16,
        "__lisp65_rtov_verifier_bindings_end": start + VERIFIER_BINDING_BYTES,
    }
    if FAMILY_STAGE_BINDINGS:
        expected_symbols.update({
            "__lisp65_rtov_family_stage_bindings_start":
                start + VERIFIER_BINDING_BYTES,
            "rtov_family_stage_bindings": start + VERIFIER_BINDING_BYTES,
            "__lisp65_rtov_family_stage_bindings_end":
                start + binding_bytes_count,
        })
    for name, expected in expected_symbols.items():
        if symbols.get(name) != expected:
            raise RuntimeError(
                f"verifier binding symbol drift {name}: "
                f"{symbols.get(name)} != {expected}")

    original = target.read_bytes()
    file_offset = _prg_file_offset(original, start, binding_bytes_count)
    sentinel_words = VERIFIER_BINDING_SENTINELS + (
        FAMILY_STAGE_BINDING_SENTINELS if FAMILY_STAGE_BINDINGS else ())
    placeholder = struct.pack("<" + "H" * len(sentinel_words), *sentinel_words)
    if original[file_offset:file_offset + binding_bytes_count] != placeholder:
        raise RuntimeError("verifier binding placeholder bytes drifted")

    write(out / "lisp65-c2-substitution-window-bound.prg", original)
    binding = verifier_binding_bytes(boot_manifest, session_manifest)
    if FAMILY_STAGE_BINDINGS:
        binding += family_stage_binding_bytes(boot_manifest, session_manifest)
    write(out / "runtime-overlay-verifier-bindings.bin", binding)
    patched = bytearray(original)
    patched[file_offset:file_offset + binding_bytes_count] = binding
    write(target, bytes(patched))
    changed = [index for index, (before, after) in
               enumerate(zip(original, patched)) if before != after]
    allowed = set(range(file_offset, file_offset + binding_bytes_count))
    if not changed or not set(changed) <= allowed:
        raise RuntimeError("publish-last patch escaped its 32-byte section")
    if target.read_bytes()[file_offset:file_offset + binding_bytes_count] != binding:
        raise RuntimeError("published verifier binding does not match manifests")

    report = {
        "format": "lisp65-runtime-verifier-publish-last-v1",
        "status": "passed",
        "section": VERIFIER_BINDING_SECTION,
        "address": start,
        "expected_address": expected_base,
        "file_offset": file_offset,
        "bytes": binding_bytes_count,
        "changed_bytes": len(changed),
        "changed_range_confined": True,
        "tuple_order": [
            "boot-catalog", "boot-record", "session-catalog", "session-record"
        ] + (["boot-stage-size-crc", "session-stage-size-crc"]
             if FAMILY_STAGE_BINDINGS else []),
        "pre_overlay_binding_sha256": hashlib.sha256(original).hexdigest(),
        "bound_sha256": hashlib.sha256(bytes(patched)).hexdigest(),
        "binding_sha256": hashlib.sha256(binding).hexdigest(),
    }
    write(out / "runtime-verifier-publish-last.json",
          json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def total_publish_last_gate(
        out: Path, target: Path,
        window_binding: dict[str, object],
        overlay_binding: dict[str, object], *,
        expected_verifier_base: int = VERIFIER_BINDING_BASE
        ) -> dict[str, object]:
    before_path = out / "lisp65-c2-substitution-unbound.prg"
    if not before_path.is_file():
        raise RuntimeError("total publish-last gate lacks the unbound product")
    before = before_path.read_bytes()
    after = target.read_bytes()
    table = (out / "runtime-overlay-verifier-bindings.bin").read_bytes()
    binding_bytes_count = runtime_binding_bytes()
    declared_publish_bytes = total_publish_last_bytes()
    if len(table) != binding_bytes_count:
        raise RuntimeError("runtime verifier binding payload size drift")

    operands = window_binding["binding_operands"]
    if not isinstance(operands, list) or len(operands) != 2:
        raise RuntimeError("KERNAL publish-last operand inventory drift")
    domains = [{
        "name": "runtime-overlay-verifier-bindings",
        "address": int(overlay_binding["address"]),
        "file_offset": int(overlay_binding["file_offset"]),
        "expected": table,
    }]
    for operand in operands:
        domains.append({
            "name": str(operand["name"]),
            "address": int(operand["address"]),
            "file_offset": int(operand["file_offset"]),
            "expected": bytes([int(operand["published_value"])]),
        })
    if sum(len(bytes(domain["expected"])) for domain in domains) != declared_publish_bytes:
        raise RuntimeError(
            f"total publish-last domain is not exactly {declared_publish_bytes} bytes")
    expected_addresses = {
        "runtime-overlay-verifier-bindings": expected_verifier_base,
        "kernal-window-crc-high": KERNAL_CRC_BINDING_HIGH_ADDRESS,
        "kernal-window-crc-low": KERNAL_CRC_BINDING_LOW_ADDRESS,
    }
    if {str(domain["name"]): int(domain["address"]) for domain in domains} != expected_addresses:
        raise RuntimeError("total publish-last address inventory drift")
    if errors := _publish_last_domain_errors(before, after, domains):
        raise RuntimeError(f"total publish-last gate red: {errors}")

    allowed = {
        index for domain in domains
        for index in range(int(domain["file_offset"]),
                           int(domain["file_offset"]) + len(bytes(domain["expected"])))
    }
    outside = bytearray(after)
    outside_offset = next(index for index in range(2, len(outside))
                          if index not in allowed)
    outside[outside_offset] ^= 0x01
    if "post-link-change-outside-declared-domain" not in _publish_last_domain_errors(
            before, bytes(outside), domains):
        raise AssertionError("mutation outside the 34-byte product domain was accepted")
    corrupt_crc = bytearray(after)
    crc_domain = domains[1]
    corrupt_crc[int(crc_domain["file_offset"])] ^= 0x01
    if not any(error == "binding-content-mismatch:kernal-window-crc-high"
               for error in _publish_last_domain_errors(
                   before, bytes(corrupt_crc), domains)):
        raise AssertionError("corrupt published KERNAL CRC was accepted")

    changed = [index for index, (old, new) in enumerate(zip(before, after))
               if old != new]
    report_domains = []
    for domain in domains:
        report_domains.append({
            "name": domain["name"],
            "address": f"0x{int(domain['address']):04x}",
            "file_offset": int(domain["file_offset"]),
            "bytes": len(bytes(domain["expected"])),
        })
    report = {
        "format": "lisp65-c2-total-publish-last-domain-v1",
        "status": "passed",
        "declared_domains": report_domains,
        "declared_domain_bytes": declared_publish_bytes,
        "actual_changed_bytes": len(changed),
        "changed_file_offsets": changed,
        "changes_outside_declared_domains": 0,
        "unbound_product_sha256": hashlib.sha256(before).hexdigest(),
        "bound_product_sha256": hashlib.sha256(after).hexdigest(),
        "negative_matrix": {
            "mutation-outside-34-byte-domain": "rejected",
            "mutated-kernal-crc-operand": "rejected",
        },
        "rule": (
            "These 32 verifier-table bytes and two named handoff operands are "
            "the complete post-link mutable product-byte set. Any addition is "
            "a contract change."),
    }
    write(out / "total-publish-last-domain.json",
          json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def render_prepared_family_header(source: Path, destination: Path) -> None:
    text = source.read_text(encoding="ascii")
    marker = "#endif /* LISP65_RUNTIME_OVERLAY_BANK_CONFIG_H */"
    insertion = "\n".join([
        "#define LISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES 1",
        "#define LISP65_RUNTIME_OVERLAY_BOOT_STORAGE_BASE 0x08200000UL",
        "#define LISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_FILE_OFF LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_OFF",
        "#define LISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_FILE_SIZE LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_SIZE",
        "#define LISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_ENTRY_OFFSET LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_ENTRY_OFFSET",
        "#define LISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_CRC16 LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_CRC16",
        "#define LISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_FILE_OFF LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_FILE_OFF",
        "#define LISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_FILE_SIZE LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_FILE_SIZE",
        "#define LISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_ENTRY_OFFSET LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_ENTRY_OFFSET",
        "#define LISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_CRC16 LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_CRC16",
        "",
    ])
    write(destination, text.replace(marker, insertion + marker))


def section_table(elf: Path) -> dict[str, dict[str, int]]:
    """Return unique ELF section geometry from the shared truth layer."""
    truth = ElfTruth.read(elf, llvm_readobj=TOOLCHAIN / "llvm-readobj")
    result: dict[str, dict[str, int]] = {}
    for row in truth.sections:
        if not row.name:
            continue
        if row.name in result:
            raise ElfTruthError(f"duplicate section identity: {row.name}")
        result[row.name] = {"bytes": row.bytes, "address": row.address}
    return result


def defined_symbols(elf: Path) -> dict[str, int]:
    """Return unambiguous defined symbol values from structured ELF truth."""
    truth = ElfTruth.read(elf, llvm_readobj=TOOLCHAIN / "llvm-readobj")
    result: dict[str, int] = {}
    for name, rows in truth.symbols_by_name.items():
        defined = [row for row in rows if row.section != "Undefined"]
        values = {row.value for row in defined}
        if len(values) > 1:
            raise ElfTruthError(
                f"defined symbol has conflicting values: {name} {sorted(values)}")
        if values:
            result[name] = next(iter(values))
    return result


def _readobj_sections(elf: Path) -> list[dict[str, object]]:
    """Compatibility shape for inventory gates, backed only by ElfTruth."""
    truth = ElfTruth.read(elf, llvm_readobj=TOOLCHAIN / "llvm-readobj")
    return [{
        "name": row.name,
        "address": row.address,
        "bytes": row.bytes,
        "flags": list(row.flags),
    } for row in truth.sections if row.name]


def _final_section_inventory_base_pin() -> list[str]:
    names = [
        line.strip() for line in FINAL_SECTION_INVENTORY_PIN.read_text(
            encoding="ascii").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if len(names) != 140 or len(set(names)) != len(names):
        raise RuntimeError(
            "final section inventory pin must contain 140 unique names")
    if names[-1] != ".llvm_sympart":
        raise RuntimeError("final section inventory does not end in .llvm_sympart")
    return names


def _full_map_final_section_owners() -> list[dict[str, object]]:
    """Read the independent v1.8 owner rows used by the final inventory.

    The checked ELF is deliberately absent from this derivation.  Phase C
    binds the same contract against the SHA-owned v1.7 replay before a fresh
    product card is permitted.
    """
    contract = json.loads(
        FULL_MAP_OWNERSHIP_CONTRACT.read_text(encoding="utf-8"))
    raw = contract["generated_linker_requirements"][
        "final_section_inventory_additions"]
    if not isinstance(raw, list) or len(raw) != 7:
        raise RuntimeError(
            "full-map final-section contract must own exactly seven rows")
    owners: list[dict[str, object]] = []
    for value in raw:
        if not isinstance(value, dict):
            raise RuntimeError("full-map final-section owner is not an object")
        flags = value.get("required_flags")
        if not isinstance(flags, list) or not flags:
            raise RuntimeError("full-map final-section flags are absent")
        name = str(value["name"])
        is_relocation = name.startswith(".rela.")
        policy = value.get("size_policy")
        if policy is None:
            policy = (
                "candidate-derived-relocation-records"
                if is_relocation else "fixed-contract")
        if policy not in ("fixed-contract",
                          "candidate-derived-relocation-records",
                          "candidate-derived-section-bytes"):
            raise RuntimeError(
                f"unknown full-map section-size policy: {name} {policy}")
        owners.append({
            "name": name,
            "address": int(str(value["address"]), 0),
            "bytes": int(value["bytes"]),
            "flags": tuple(str(flag) for flag in flags),
            "size_policy": policy,
            "capacity_bytes": int(value.get("capacity_bytes", value["bytes"])),
        })
    names = [str(row["name"]) for row in owners]
    if len(set(names)) != len(names):
        raise RuntimeError("full-map final-section owners are not unique")
    return owners


def _append_inventory_names(
        slices: list[tuple[str, str]]) -> tuple[list[str], list[str]]:
    allocated = [f".lisp65_rt_c2append_{name}" for name, _entry in slices]
    relocations = [f".rela{name}" for name in allocated]
    return allocated, relocations


def _decoder_inventory_names(
        slices: list[tuple[str, str]]) -> tuple[list[str], list[str]]:
    allocated = [f".lisp65_rt_c2d_{name}" for name, _entry in slices]
    relocations = [f".rela{name}" for name in allocated]
    return allocated, relocations


def input_capture_inventory_registration(
        definitions: tuple[str, ...] | None = None) -> dict[str, object]:
    """Derive all input-card inventory from the real build selection."""
    selected_definitions = (tuple(CONVERGENCE_DEFINES)
                            if definitions is None else tuple(definitions))
    selected = INPUT_CAPTURE_FEATURE in selected_definitions
    hybrid_selected = INPUT_HYBRID_FEATURE in selected_definitions
    if definitions is None and selected != INPUT_CAPTURE_ENABLED:
        raise RuntimeError(
            "input-capture inventory and build activation disagree")
    if definitions is None and hybrid_selected != INPUT_HYBRID_ENABLED:
        raise RuntimeError(
            "input-hybrid inventory and build activation disagree")
    if hybrid_selected and not selected:
        raise RuntimeError("input-hybrid inventory requires capture owner")
    capture_allocated = (tuple(INPUT_CAPTURE_BUILD_CONFIGURATION["allocated"])
                         if selected else ())
    hybrid_allocated = (tuple(INPUT_HYBRID_BUILD_CONFIGURATION["allocated"])
                        if hybrid_selected else ())
    allocated = (*capture_allocated, *hybrid_allocated)
    relocations = tuple(f".rela{name}" for name in allocated)
    return {
        "feature": INPUT_CAPTURE_FEATURE,
        "selected": selected,
        "hybrid_feature": INPUT_HYBRID_FEATURE,
        "hybrid_selected": hybrid_selected,
        "source": INPUT_CAPTURE_SOURCE.relative_to(ROOT).as_posix(),
        "hybrid_source": (INPUT_HYBRID_SOURCE.relative_to(ROOT).as_posix()
                          if hybrid_selected else None),
        "allocated": list(allocated),
        "relocations": list(relocations),
        "names": [*allocated, *relocations],
        "authority": "build-feature-and-source-membership",
    }


def refill_witness_inventory_registration(
        definitions: tuple[str, ...] | None = None) -> dict[str, object]:
    """Project witness source, layout and final inventory from one feature."""
    selected_definitions = (tuple(CONVERGENCE_DEFINES)
                            if definitions is None else tuple(definitions))
    selected = REFILL_WITNESS_FEATURE in selected_definitions
    if definitions is None and selected != REFILL_WITNESS_ENABLED:
        raise RuntimeError("refill witness inventory/build activation disagree")
    allocated = (tuple(REFILL_WITNESS_BUILD_CONFIGURATION["allocated"])
                 if selected else ())
    relocations = tuple(f".rela{name}" for name in allocated)
    linked = {Path(path).resolve() for path in source_list(selected_definitions)}
    consumed = REFILL_WITNESS_SOURCE.resolve() in linked
    if consumed != selected:
        raise RuntimeError("refill witness layout owner was not compiler-consumed")
    return {
        "feature": REFILL_WITNESS_FEATURE,
        "selected": selected,
        "source": REFILL_WITNESS_SOURCE.relative_to(ROOT).as_posix(),
        "allocated": list(allocated),
        "relocations": list(relocations),
        "names": [*allocated, *relocations],
        "cpu_start": REFILL_WITNESS_BUILD_CONFIGURATION["cpu_start"],
        "physical_start": REFILL_WITNESS_BUILD_CONFIGURATION["physical_start"],
        "capacity_bytes": REFILL_WITNESS_BUILD_CONFIGURATION["capacity_bytes"],
        "authority": "REFILL_WITNESS_BUILD_CONFIGURATION",
    }


def active_card_freight_registries() -> list[dict[str, object]]:
    """Project every active card registry from the live build authority.

    Consumers receive one union-producing catalog rather than enumerating
    registries themselves.  Adding another active registry therefore changes
    this projection at the producer boundary and cannot silently create a
    third Acceptance category.
    """
    candidates = (
        ("input-fidelity", input_capture_inventory_registration(),
         "candidate-predecessor-end"),
        ("refill-boundary-witness", refill_witness_inventory_registration(),
         "mapped-arena-contract"),
        ("product-cold-disk-chain", product_cold_inventory_registration(),
         "mapped-arena-contract"),
    )
    active: list[dict[str, object]] = []
    for registry, registration, placement_gate in candidates:
        if not bool(registration["selected"]):
            continue
        allocated = [str(name) for name in registration["allocated"]]
        if not allocated:
            raise RuntimeError(f"active card registry is empty: {registry}")
        active.append({"registry": registry, "registration": registration,
                       "allocated": allocated,
                       "placement_gate": placement_gate})
    names = [name for row in active for name in row["allocated"]]
    if len(names) != len(set(names)):
        raise RuntimeError("active card registries have double authority")
    return active


def input_capture_consumption_closure(
        definitions: tuple[str, ...], sources: list[str], *,
        layout_selected: bool | None = None) -> dict[str, object]:
    """Bind layout, inventory and real compiler inputs to one selection."""
    registration = input_capture_inventory_registration(definitions)
    selected = bool(registration["selected"])
    layout = INPUT_CAPTURE_ENABLED if layout_selected is None else layout_selected
    linked = {Path(path).resolve() for path in sources}
    capture = INPUT_CAPTURE_SOURCE.resolve() in linked
    base = INPUT_CAPTURE_BASE_SOURCE.resolve() in linked
    hybrid_selected = bool(registration["hybrid_selected"])
    hybrid = INPUT_HYBRID_SOURCE.resolve() in linked
    if selected != layout:
        raise RuntimeError(
            "input-capture layout selection escaped build configuration")
    if capture != selected or base == selected:
        owner = str(INPUT_CAPTURE_BUILD_CONFIGURATION["name"])
        raise RuntimeError(
            f"layout-bound section owner was not consumed by real compiler "
            f"profile: {owner}")
    if hybrid != hybrid_selected:
        owner = str(INPUT_HYBRID_BUILD_CONFIGURATION["name"])
        raise RuntimeError(
            f"layout-bound section owner was not consumed by real compiler "
            f"profile: {owner}")
    return {
        "status": "passed-layout-inventory-compiler-consumption-closure",
        "authority": "INPUT_CAPTURE_BUILD_CONFIGURATION",
        "owner": INPUT_CAPTURE_BUILD_CONFIGURATION["name"],
        "feature": INPUT_CAPTURE_FEATURE,
        "selected": selected,
        "hybrid_selected": hybrid_selected,
        "layout_selected": layout,
        "inventory_names": list(registration["names"]),
        "compiler_source": registration["source"] if selected else
            INPUT_CAPTURE_BASE_SOURCE.relative_to(ROOT).as_posix(),
    }


def input_capture_compile_profile(
        definitions: tuple[str, ...]) -> tuple[str, ...]:
    """Project card membership at the real single-link consumer."""
    feature = str(INPUT_CAPTURE_BUILD_CONFIGURATION["feature"])
    count = definitions.count(feature)
    if INPUT_CAPTURE_ENABLED:
        if count == 0:
            definitions = (*definitions, feature)
        elif count != 1:
            raise RuntimeError("duplicate input-capture compiler feature")
    elif count:
        raise RuntimeError(
            "input-capture compiler feature exists without layout selection")
    hybrid_count = definitions.count(INPUT_HYBRID_FEATURE)
    if INPUT_HYBRID_ENABLED:
        if hybrid_count == 0:
            definitions = (*definitions, INPUT_HYBRID_FEATURE)
        elif hybrid_count != 1:
            raise RuntimeError("duplicate input-hybrid compiler feature")
    elif hybrid_count:
        raise RuntimeError(
            "input-hybrid compiler feature exists without layout selection")
    return definitions


def input_capture_seed_size_witness(
        sections: list[dict[str, object]], definitions: tuple[str, ...]
        ) -> dict[str, object]:
    """Reject an empty card-owned seed section as a missing source owner."""
    registration = input_capture_inventory_registration(definitions)
    if not registration["selected"]:
        return {"status": "not-selected", "owners_checked": 0}
    actual = {str(row["name"]): int(row["bytes"]) for row in sections}
    sizes: dict[str, int] = {}
    for name in registration["allocated"]:
        owner = str(
            INPUT_HYBRID_BUILD_CONFIGURATION["name"]
            if name in INPUT_HYBRID_BUILD_CONFIGURATION["allocated"]
            else INPUT_CAPTURE_BUILD_CONFIGURATION["name"])
        size = actual.get(str(name), 0)
        if size == 0:
            raise RuntimeError(
                f"card-owned seed section is zero bytes; missing source "
                f"owner={owner} section={name}")
        sizes[str(name)] = size
    return {"status": "passed-card-owned-seed-sections-nonzero",
            "owners": sorted({
                str(INPUT_CAPTURE_BUILD_CONFIGURATION["name"]),
                *([str(INPUT_HYBRID_BUILD_CONFIGURATION["name"])]
                  if registration["hybrid_selected"] else [])}),
            "sizes": sizes,
            "owners_checked": len(sizes)}


def final_section_inventory_expectation() -> dict[str, object]:
    """Derive the exact inventory from the configured product profile.

    The Link-28 pin remains the profile-independent envelope.  Append ABI,
    formal E000 reopening and BSS-triage sections are the only profile-shaped
    members and therefore come from the same configured globals that render
    the linker script and runtime-family catalog.  Nothing is learned from the
    ELF being checked.
    """
    base = _final_section_inventory_base_pin()
    old_decoder, old_decoder_relocations = _decoder_inventory_names(
        C2_DECODER_LINK28_SLICES)
    new_decoder, new_decoder_relocations = _decoder_inventory_names(
        C2_DECODER_SLICES)
    old_allocated, old_relocations = _append_inventory_names(
        C2_APPEND_LINK28_SLICES)
    new_allocated, new_relocations = _append_inventory_names(C2_APPEND_SLICES)
    replaced = set((*old_decoder, *old_decoder_relocations,
                    *old_allocated, *old_relocations))
    typed_queue_profile = (
        ".lisp65_c2_kernal_window.typed_queue_driver" in KERNAL_SECTIONS
        and ".lisp65_c2_kernal_window.frame_source" not in KERNAL_SECTIONS
        and ".lisp65_c2_kernal_window.event_poll" not in KERNAL_SECTIONS
    )
    if typed_queue_profile:
        replaced.update({
            ".lisp65_c2_kernal_window.frame_source",
            ".lisp65_c2_kernal_window.event_poll",
            ".rela.lisp65_c2_kernal_window.event_poll",
        })
    expected = [name for name in base if name not in replaced]
    insert_at = expected.index(".llvm_sympart")
    profile_names = [*new_decoder, *new_decoder_relocations,
                     *new_allocated, *new_relocations]
    if E000_REOPENING:
        gaps = list(e000_reopening_section_names())
        profile_names.extend(gaps)
        profile_names.extend(f".rela{name}" for name in gaps)
    if BSS_TRIAGE:
        profile_names.append(".lisp65_c2_fixed_bank0_hot_bss")
    if FAMILY_STAGE_BINDINGS:
        bank3_stage_sections = [
            ".lisp65_boot_bank3_stage",
            ".lisp65_rt_bank3_stage_session",
        ]
        profile_names.extend(bank3_stage_sections)
        profile_names.extend(
            f".rela{name}" for name in bank3_stage_sections)
    if INTERN_SESSION_SERVICE:
        service_sections = [".lisp65_rt_intern_service"]
        profile_names.extend(service_sections)
        profile_names.extend(
            f".rela{name}" for name in service_sections)
    if typed_queue_profile:
        profile_names.append(
            ".rela.lisp65_c2_kernal_window.typed_queue_driver")
    capture_inventory = input_capture_inventory_registration()
    profile_names.extend(str(name) for name in capture_inventory["names"])
    witness_inventory = refill_witness_inventory_registration()
    profile_names.extend(str(name) for name in witness_inventory["names"])
    product_cold_inventory = product_cold_inventory_registration()
    profile_names.extend(
        str(name) for name in product_cold_inventory["names"])
    if FULL_MAP_OWNERSHIP:
        profile_names.extend(
            str(row["name"]) for row in _full_map_final_section_owners())
    if len(profile_names) != len(set(profile_names)):
        raise RuntimeError(
            "profile-derived final-section names are not unique")
    expected[insert_at:insert_at] = profile_names
    if len(expected) != len(set(expected)):
        raise RuntimeError(
            "profile-derived final-section inventory is not unique")
    removed = [name for name in base if name not in expected]
    added = [name for name in expected if name not in base]
    return {
        "names": expected,
        "base_pin_names": len(base),
        "expected_names": len(expected),
        "removed_from_link28": removed,
        "added_by_configured_profile": added,
        "append_slices": [name for name, _entry in C2_APPEND_SLICES],
        "decoder_slices": [name for name, _entry in C2_DECODER_SLICES],
        "e000_reopening": E000_REOPENING,
        "bss_triage": BSS_TRIAGE,
        "family_stage_bindings": FAMILY_STAGE_BINDINGS,
        "session_service": (
            "intern-session-service"
            if INTERN_SESSION_SERVICE else None),
        "typed_queue_profile": typed_queue_profile,
        "input_capture_registration": capture_inventory,
        "refill_witness_registration": witness_inventory,
        "product_cold_registration": product_cold_inventory,
        "derivation": (
            "Link-28 stable envelope minus its append ABI, plus the configured "
            "decoder/append ABIs and the exact E000-reopening/BSS-triage "
            "section sets and, when enabled by the same product profile, the "
            "two Bank-3 stage sections or one Session-service section with "
            "their relocation sections; the "
            "configured typed-queue profile replaces the retired frame-source "
            "and event-poll members and adds its actual relocation section; "
            "the selected input-capture file contributes its two card-owned "
            "sections and their relocation sections; "
            "the selected product-cold feature contributes its mapped disk-"
            "chain section and relocation from the same build authority; "
            "the selected full-map profile adds its five named owned sections "
            "and two relocation sections from the independent v1.8 contract; "
            "the target ELF is never an expectation source"),
    }


def _final_section_inventory_pin() -> list[str]:
    return list(final_section_inventory_expectation()["names"])


def _final_section_inventory_violations(
        expected: list[str], sections: list[dict[str, object]],
        full_map_owners: list[dict[str, object]] | None = None
        ) -> list[str]:
    actual = [str(row["name"]) for row in sections]
    violations: list[str] = []
    if len(actual) != len(expected):
        violations.append("section-count")
    if set(actual) != set(expected):
        violations.append("section-name-set")
    partitions = [row for row in sections
                  if row["name"] == ".llvm_sympart"]
    if len(partitions) != 1:
        violations.append("final-sympart-count")
    else:
        partition = partitions[0]
        if int(partition["bytes"]) != 15:
            violations.append("final-sympart-size")
        if int(partition["address"]) != 0:
            violations.append("final-sympart-address")
        if "SHF_ALLOC" in partition["flags"]:
            violations.append("final-sympart-alloc")
    owners = (
        _full_map_final_section_owners()
        if full_map_owners is None and FULL_MAP_OWNERSHIP
        else (full_map_owners or []))
    for owner in owners:
        name = str(owner["name"])
        matches = [row for row in sections if row["name"] == name]
        if len(matches) != 1:
            violations.append(f"full-map-owner-count:{name}")
            continue
        row = matches[0]
        if int(row["address"]) != int(owner["address"]):
            violations.append(f"full-map-owner-address:{name}")
        if owner.get("size_policy") == "candidate-derived-relocation-records":
            # A relocation section's count follows the emitted freight.  Its
            # identity, VMA and flags remain owner contract; the candidate's
            # SHT_RELA extent is well-formed iff it contains whole ELF32 RELA
            # records.  No historical record count is an acceptance input.
            if (row.get("type") not in (None, "SHT_RELA")
                    or int(row["bytes"]) <= 0
                    or int(row["bytes"]) % 12 != 0):
                violations.append(f"full-map-owner-relocation-shape:{name}")
        elif owner.get("size_policy") == "candidate-derived-section-bytes":
            if (int(row["bytes"]) <= 0
                    or int(row["bytes"]) > int(owner["capacity_bytes"])):
                violations.append(f"full-map-owner-capacity:{name}")
        elif int(row["bytes"]) != int(owner["bytes"]):
            violations.append(f"full-map-owner-size:{name}")
        if set(str(flag) for flag in row["flags"]) != set(owner["flags"]):
            violations.append(f"full-map-owner-flags:{name}")
    return violations


def _final_section_inventory_model_selftest() -> dict[str, str]:
    owners = _full_map_final_section_owners()
    expected = [".text", *(str(row["name"]) for row in owners),
                ".llvm_sympart"]
    valid: list[dict[str, object]] = [
        {"name": ".text", "address": 0x2001, "bytes": 2,
         "flags": ["SHF_ALLOC"]},
        *[{"name": row["name"], "address": row["address"],
           "bytes": row["bytes"],
           "type": ("SHT_RELA" if str(row["name"]).startswith(".rela.")
                    else "SHT_PROGBITS"),
           "flags": list(row["flags"])}
          for row in owners],
        {"name": ".llvm_sympart", "address": 0, "bytes": 15,
         "flags": []},
    ]
    if _final_section_inventory_violations(expected, valid, owners):
        raise AssertionError("valid final section inventory rejected")
    cases = {
        "missing-section": (valid[:-1], "section-count"),
        "additional-section": (
            valid + [{"name": ".unknown", "address": 0, "bytes": 1,
                      "flags": []}], "section-count"),
        "allocated-sympart": (
            [*valid[:-1], {**valid[-1], "flags": ["SHF_ALLOC"]}],
            "final-sympart-alloc"),
        "loaded-address-sympart": (
            [*valid[:-1], {**valid[-1], "address": 0x2000}],
            "final-sympart-address"),
        "resized-sympart": (
            [*valid[:-1], {**valid[-1], "bytes": 16}],
            "final-sympart-size"),
    }
    for name, (sections, expected_violation) in cases.items():
        if expected_violation not in _final_section_inventory_violations(
                expected, sections, owners):
            raise AssertionError(f"section-inventory mutation accepted: {name}")
    deletion_mutations: dict[str, str] = {}
    movement_mutations: dict[str, str] = {}
    for owner in owners:
        section = str(owner["name"])
        deleted = [row for row in valid if row["name"] != section]
        if not _final_section_inventory_violations(
                expected, deleted, owners):
            raise AssertionError(
                f"full-map deleted-section mutation accepted: {section}")
        deletion_mutations[section] = "rejected"
        moved = [
            ({**row, "address": int(row["address"]) + 1}
             if row["name"] == section else dict(row))
            for row in valid]
        marker = f"full-map-owner-address:{section}"
        if marker not in _final_section_inventory_violations(
                expected, moved, owners):
            raise AssertionError(
                f"full-map moved-section mutation accepted: {section}")
        movement_mutations[section] = "rejected"
        if owner.get("size_policy") == "candidate-derived-relocation-records":
            resized = [
                ({**row, "bytes": int(row["bytes"]) - 12}
                 if row["name"] == section else dict(row))
                for row in valid]
            if _final_section_inventory_violations(
                    expected, resized, owners):
                raise AssertionError(
                    f"candidate-derived relocation count rejected: {section}")
            malformed = [
                ({**row, "bytes": int(row["bytes"]) - 1}
                 if row["name"] == section else dict(row))
                for row in valid]
            marker = f"full-map-owner-relocation-shape:{section}"
            if marker not in _final_section_inventory_violations(
                    expected, malformed, owners):
                raise AssertionError(
                    f"malformed relocation extent accepted: {section}")
        if owner.get("size_policy") == "candidate-derived-section-bytes":
            resized = [
                ({**row, "bytes": max(1, int(row["bytes"]) - 1)}
                 if row["name"] == section else dict(row))
                for row in valid]
            if _final_section_inventory_violations(
                    expected, resized, owners):
                raise AssertionError(
                    f"candidate-derived section size rejected: {section}")
            overflow = [
                ({**row, "bytes": int(owner["capacity_bytes"]) + 1}
                 if row["name"] == section else dict(row))
                for row in valid]
            marker = f"full-map-owner-capacity:{section}"
            if marker not in _final_section_inventory_violations(
                    expected, overflow, owners):
                raise AssertionError(
                    f"candidate-derived section overflow accepted: {section}")
    stray = [*valid, {"name": ".lisp65_unowned_stray", "address": 0,
                      "bytes": 1, "flags": ["SHF_ALLOC"]}]
    if "section-name-set" not in _final_section_inventory_violations(
            expected, stray, owners):
        raise AssertionError("full-map unowned-stray mutation accepted")
    if _final_section_inventory_violations(
            expected, list(reversed(valid)), owners):
        raise AssertionError("non-semantic section reordering was rejected")
    return {"exact-pinned-inventory": "passed",
            "reordered-sections": "passed-provenance-only",
            **{name: "rejected" for name in cases},
            "full-map-deleted-sections":
                f"rejected-{len(deletion_mutations)}-of-{len(owners)}",
            "full-map-moved-sections":
                f"rejected-{len(movement_mutations)}-of-{len(owners)}",
            "full-map-unowned-stray": "rejected"}


def final_section_inventory_check(target: Path) -> dict[str, object]:
    """Check one immutable target without writing beside it."""
    elf = Path(str(target) + ".elf")
    expectation = final_section_inventory_expectation()
    expected = list(expectation["names"])
    sections = _readobj_sections(elf)
    # Preserve the long-standing report schema while giving the relocation
    # shape check the real emitted section types.  Type is an acceptance
    # input, not a new field in every historical inventory report.
    truth = ElfTruth.read(elf, llvm_readobj=TOOLCHAIN / "llvm-readobj")
    section_types = {row.name: row.section_type for row in truth.sections
                     if row.name}
    checked_sections = [
        {**row, "type": section_types.get(str(row["name"]))}
        for row in sections]
    violations = _final_section_inventory_violations(
        expected, checked_sections)
    if violations:
        actual = [str(row["name"]) for row in sections]
        missing = [name for name in expected if name not in actual]
        additional = [name for name in actual if name not in expected]
        raise RuntimeError(
            f"final section inventory red: {violations}; "
            f"missing={missing}; additional={additional}")
    partition = next(row for row in sections
                     if row["name"] == ".llvm_sympart")
    report = {
        "format": "lisp65-c2-final-elf-section-inventory-v1",
        "status": "passed",
        "target": str(target.relative_to(ROOT)),
        "final_elf_sha256": hashlib.sha256(elf.read_bytes()).hexdigest(),
        "pin": {
            "path": str(FINAL_SECTION_INVENTORY_PIN.relative_to(ROOT)),
            "sha256": hashlib.sha256(
                FINAL_SECTION_INVENTORY_PIN.read_bytes()).hexdigest(),
            "expected_sections": len(expected),
            "profile_derivation": expectation,
        },
        "actual_sections": sections,
        "actual_section_order": [str(row["name"]) for row in sections],
        "actual_section_order_sha256": hashlib.sha256(
            ("\n".join(str(row["name"]) for row in sections) + "\n").encode(
                "ascii")).hexdigest(),
        "order_semantics": "provenance-only-not-an-acceptance-predicate",
        "full_map_owner_size_semantics": [{
            "name": str(owner["name"]),
            "policy": str(owner["size_policy"]),
            "contract_snapshot_bytes": int(owner["bytes"]),
            "candidate_bytes": int(next(
                row["bytes"] for row in sections
                if row["name"] == owner["name"])),
            "candidate_records": (
                int(next(row["bytes"] for row in sections
                         if row["name"] == owner["name"])) // 12
                if owner["size_policy"] ==
                    "candidate-derived-relocation-records" else None),
        } for owner in (
            _full_map_final_section_owners() if FULL_MAP_OWNERSHIP else [])],
        "llvm_sympart": {
            **partition,
            "runtime_load_bytes": 0,
            "outside_every_load_domain": True,
            "classification": "seventh known metadata class; LTO-only INFO",
        },
        "unknown_sections": [],
        "missing_sections": [],
        "negative_matrix": _final_section_inventory_model_selftest(),
    }
    return report


def final_section_inventory_gate(out: Path, target: Path) -> dict[str, object]:
    report = final_section_inventory_check(target)
    write(out / f"final-section-inventory-{target.name}.json",
          json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def _lto_partition_metadata_violations(
        lto_sections: list[dict[str, object]],
        final_sections: list[dict[str, object]]) -> list[str]:
    violations: list[str] = []
    partitions = [row for row in lto_sections
                  if row["name"] == ".llvm_sympart"]
    if len(partitions) != 1:
        violations.append("lto-sympart-count")
    else:
        section = partitions[0]
        if int(section["bytes"]) <= 0:
            violations.append("lto-sympart-empty")
        if int(section["address"]) != 0:
            violations.append("lto-sympart-address")
        if "SHF_ALLOC" in section["flags"]:
            violations.append("lto-sympart-alloc")
    final_partitions = [row for row in final_sections
                        if row["name"] == ".llvm_sympart"]
    if len(final_partitions) != 1:
        violations.append("final-sympart-count")
    else:
        final_partition = final_partitions[0]
        if int(final_partition["bytes"]) != 15:
            violations.append("final-sympart-size")
        if int(final_partition["address"]) != 0:
            violations.append("final-sympart-address")
        if "SHF_ALLOC" in final_partition["flags"]:
            violations.append("final-sympart-alloc")
    if not any(str(row["name"]).startswith((".rel", ".rela"))
               for row in final_sections):
        violations.append("final-relocations-absent")
    return violations


def _lto_partition_metadata_model_selftest() -> dict[str, str]:
    valid_lto = [{"name": ".llvm_sympart", "address": 0,
                  "bytes": 15, "flags": ["SHF_EXCLUDE"]}]
    valid_final = [
        {"name": ".rela.text", "address": 0, "bytes": 12, "flags": []},
        {"name": ".llvm_sympart", "address": 0,
         "bytes": 15, "flags": []},
    ]
    if _lto_partition_metadata_violations(valid_lto, valid_final):
        raise AssertionError("valid LTO partition discard model was rejected")
    cases = {
        "missing-lto-sympart": ([], valid_final, "lto-sympart-count"),
        "alloc-lto-sympart": (
            [{"name": ".llvm_sympart", "address": 0, "bytes": 15,
              "flags": ["SHF_ALLOC"]}], valid_final, "lto-sympart-alloc"),
        "missing-final-sympart": (
            valid_lto, valid_final[:-1], "final-sympart-count"),
        "allocated-final-sympart": (
            valid_lto, [valid_final[0], {**valid_final[1],
                                         "flags": ["SHF_ALLOC"]}],
            "final-sympart-alloc"),
        "missing-final-relocations": (
            valid_lto, [valid_final[1]],
            "final-relocations-absent"),
    }
    for name, (lto, final, expected) in cases.items():
        if expected not in _lto_partition_metadata_violations(lto, final):
            raise AssertionError(f"LTO partition mutation accepted: {name}")
    return {"valid-saved-input-retained-final-info": "passed",
            **{name: "rejected" for name in cases}}


def lto_partition_metadata_gate(out: Path, target: Path) -> dict[str, object]:
    lto_object = Path(str(target) + ".lto.o")
    final_elf = Path(str(target) + ".elf")
    if not lto_object.is_file() or not final_elf.is_file():
        raise RuntimeError(
            "LTO partition metadata red: saved LTO object or final ELF absent")
    lto_sections = _readobj_sections(lto_object)
    final_sections = _readobj_sections(final_elf)
    violations = _lto_partition_metadata_violations(
        lto_sections, final_sections)
    if violations:
        raise RuntimeError(
            f"LTO partition metadata red: {violations}")
    partition = next(row for row in lto_sections
                     if row["name"] == ".llvm_sympart")
    relocation_sections = [row for row in final_sections
                           if str(row["name"]).startswith((".rel", ".rela"))]
    lto_sha = hashlib.sha256(lto_object.read_bytes()).hexdigest()
    lto_object.chmod(0o444)
    report = {
        "format": "lisp65-c2-lto-partition-metadata-disposition-v1",
        "status": "passed",
        "target": str(target.relative_to(ROOT)),
        "saved_lto_object": {
            "path": str(lto_object.relative_to(ROOT)),
            "bytes": lto_object.stat().st_size,
            "sha256": lto_sha,
            "mode": "0444",
            "required_section": partition,
        },
        "final_elf": {
            "path": str(final_elf.relative_to(ROOT)),
            "sha256": hashlib.sha256(final_elf.read_bytes()).hexdigest(),
            "llvm_sympart_sections": 1,
            "llvm_sympart": next(
                row for row in final_sections
                if row["name"] == ".llvm_sympart"),
            "retained_relocation_sections": len(relocation_sections),
        },
        "disposition": (
            "required non-ALLOC LTO partition metadata is SHA-bound in the "
            "saved intermediate and retained as a zero-runtime INFO section "
            "under the exact-warning and complete-inventory gates"
        ),
        "negative_matrix": _lto_partition_metadata_model_selftest(),
    }
    report_path = out / f"lto-partition-metadata-{target.name}.json"
    write(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def _classify_fixed_facade_low_edges(
        rows: list[dict[str, object]], facade_targets: set[int],
        irq_tail_target: int | None, irq_tail_section: str
        ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    bad: list[dict[str, object]] = []
    owned: list[dict[str, object]] = []
    for row in rows:
        destination = int(str(row["target"]), 16)
        if destination in facade_targets:
            continue
        if (irq_tail_target is not None
                and row["section"] == irq_tail_section
                and destination == irq_tail_target):
            owned.append(row)
        else:
            bad.append(row)
    if irq_tail_target is not None and len(owned) != 1:
        raise RuntimeError(
            "fixed facade red: retired-window IRQ tail ownership drift "
            f"{owned}")
    if bad:
        raise RuntimeError(
            f"fixed facade red: E000 code bypasses the fixed vectors {bad}")
    return owned, bad


def _fixed_facade_low_edge_selftest() -> list[str]:
    facade = {0xB5C4}; tail = 0x222D
    section = ".lisp65_c2_kernal_window.irq_handler"
    base = [
        {"section": section, "target": "0x222d", "instruction": "jmp $222d"},
        {"section": ".lisp65_c2_kernal_window.other", "target": "0xb5c4",
         "instruction": "jsr $b5c4"},
    ]
    _classify_fixed_facade_low_edges(base, facade, tail, section)
    rejected: list[str] = []
    for name, rows in {
            "foreign-low-edge": [*base, {"section": section,
                "target": "0x3333", "instruction": "jmp $3333"}],
            "foreign-owner-for-tail": [{**base[0], "section":
                ".lisp65_c2_kernal_window.other"}, base[1]],
            "missing-owned-tail": [base[1]],
            }.items():
        try:
            _classify_fixed_facade_low_edges(rows, facade, tail, section)
        except RuntimeError:
            rejected.append(name)
    if rejected != ["foreign-low-edge", "foreign-owner-for-tail",
                    "missing-owned-tail"]:
        raise RuntimeError("fixed facade IRQ-tail mutation survived")
    return rejected


def fixed_facade_gate(out: Path, target: Path, suffix: str) -> dict[str, object]:
    """Pin every cross-domain call and state operand used by the E000 slab."""
    elf = Path(str(target) + ".elf")
    fixed_leaf = FIXED_BLOCK_LEAF.audit_elf(
        elf, out=out / f"fixed-block-rtov-fail-{suffix}.json",
        require_hot_bss=BSS_TRIAGE,
        full_map_ownership=FULL_MAP_OWNERSHIP)
    sections = section_table(elf)
    symbols = defined_symbols(elf)
    required_sections = {
        ".lisp65_c2_host_facade": (HOST_FACADE_BASE,
                                    host_facade_bytes()),
        ".lisp65_c2_fixed_zp": (FIXED_ZP_BASE, FIXED_ZP_BYTES),
        ".lisp65_c2_fixed_bank0": (FIXED_BANK0_BASE, FIXED_BANK0_BYTES),
        ".lisp65_c2_fixed_bank0_code": (FIXED_BANK0_CODE_BASE,
                                          FIXED_BANK0_CODE_BYTES),
        ".lisp65_c2_kernal_window.session_emitter_state": (
            sections.get(".lisp65_c2_kernal_window.session_emitter_state", {}).get(
                "address", -1), SESSION_EMITTER_STATE_BYTES),
    }
    if BSS_TRIAGE:
        required_sections[".lisp65_c2_fixed_bank0_hot_bss"] = (
            FIXED_BANK0_HOT_BSS_BASE, FIXED_BANK0_HOT_BSS_BYTES)
        if FULL_MAP_OWNERSHIP:
            required_sections[".noinit"] = (
                FIXED_BANK0_HOT_BSS_BASE + FIXED_BANK0_HOT_BSS_BYTES, 0)
            required_sections[FIXED_BLOCK_LEAF.OWNED_STACK_SECTION] = (
                FIXED_BLOCK_LEAF.OWNED_STACK_ADDRESS,
                FIXED_BLOCK_LEAF.OWNED_STACK_BYTES)
        else:
            required_sections[".noinit"] = (
                FIXED_BANK0_HOT_BSS_BASE + FIXED_BANK0_HOT_BSS_BYTES,
                FIXED_BANK0_NOINIT_BYTES)
    for name, (address, size) in required_sections.items():
        row = sections.get(name)
        if row != {"address": address, "bytes": size}:
            raise RuntimeError(
                f"fixed facade red: {name} is {row}, expected "
                f"address=0x{address:04x} bytes={size}")

    vector_addresses = host_facade_vector_addresses()
    drift = {
        name: {"actual": symbols.get(name), "expected": address}
        for name, address in vector_addresses.items()
        if symbols.get(name) != address
    }
    if drift:
        raise RuntimeError(f"fixed facade red: vector address drift {drift}")

    fixed_state = {
        "__lisp65_c2_fixed_zp_phase_owner": 0x89,
        "__lisp65_c2_fixed_zp_pending_roots": 0x8A,
        "__lisp65_c2_fixed_zp_ready": 0x8C,
        "__lisp65_c2_fixed_zp_str_building": 0x8D,
        "__lisp65_c2_fixed_zp_mem_oom": 0x8F,
        "__lisp65_c2_fixed_bank0_committed_roots": 0xC080,
        "__lisp65_c2_fixed_bank0_decode_active": 0xC082,
        "__lisp65_c2_fixed_bank0_runtime": 0xC084,
        "__lisp65_c2_fixed_bank0_edma_job": 0xC0B2,
        "__lisp65_c2_fixed_bank0_phase_scratch": 0xC0C6,
        "__lisp65_c2_fixed_bank0_sym_name_scratch": 0xC1F6,
        "__lisp65_c2_fixed_bank0_code_start": FIXED_BANK0_CODE_BASE,
        "__lisp65_c2_fixed_bank0_code_kb_cursor_off": FIXED_BANK0_CODE_BASE,
        "__lisp65_c2_fixed_bank0_code_c2e_cons": FIXED_BANK0_CODE_BASE + 5,
        "__lisp65_c2_fixed_bank0_code_rtov_fail":
            FIXED_BANK0_CODE_BASE + 45,
        "rtov_fail": FIXED_BANK0_CODE_BASE + 45,
        "__lisp65_c2_fixed_bank0_code_end": (
            FIXED_BANK0_CODE_BASE + FIXED_BANK0_CODE_BYTES),
    }
    if BSS_TRIAGE:
        fixed_state.update({
            "__lisp65_c2_fixed_bank0_hot_bss_start": FIXED_BANK0_HOT_BSS_BASE,
            "__lisp65_c2_fixed_bank0_hot_bss_heap": FIXED_BANK0_HOT_BSS_BASE,
            "__lisp65_c2_fixed_bank0_hot_bss_end": (
                FIXED_BANK0_HOT_BSS_BASE + FIXED_BANK0_HOT_BSS_BYTES),
        })
    state_drift = {
        name: {"actual": symbols.get(name), "expected": address}
        for name, address in fixed_state.items()
        if symbols.get(name) != address
    }
    if state_drift:
        raise RuntimeError(f"fixed facade red: state address drift {state_drift}")

    facade_targets = set(vector_addresses.values())
    low_window_edges: list[dict[str, object]] = []
    irq_tail_target = symbols.get("retired_window_brk_classifier")
    irq_tail_section = ".lisp65_c2_kernal_window.irq_handler"
    for section in KERNAL_SECTIONS:
        if section in {".lisp65_c2_kernal_window.state", ".lisp65_c2_vectors",
                       PROFILE_RODATA_SECTION}:
            continue
        disassembly = run([
            str(TOOLCHAIN / "llvm-objdump"), "-d", f"--section={section}", str(elf)
        ], capture=True).lower()
        for match in re.finditer(r"\b(?:jsr|jmp)\s+\$([0-9a-f]{4})\b", disassembly):
            destination = int(match.group(1), 16)
            if destination < KERNAL_WINDOW_BASE and destination not in facade_targets:
                low_window_edges.append({
                    "section": section,
                    "target": f"0x{destination:04x}",
                    "instruction": match.group(0),
                })
    owned_irq_tail_edges, bad_window_edges = _classify_fixed_facade_low_edges(
        low_window_edges, facade_targets, irq_tail_target, irq_tail_section)
    facade_edge_mutations = _fixed_facade_low_edge_selftest()

    report = {
        "format": "lisp65-c2-fixed-host-facade-link-v1",
        "status": "passed",
        "link_stage": suffix,
        "vector_contract": {
            "base": HOST_FACADE_BASE,
            "stride_bytes": HOST_FACADE_STRIDE,
            "bytes": host_facade_bytes(),
            "segments": ({
                "original": {
                    "base": HOST_FACADE_BASE,
                    "bytes": len(HOST_FACADE_SYMBOLS) * HOST_FACADE_STRIDE,
                },
                "formal_reopening_extension": {
                    "base": HOST_FACADE_EXTENSION_BASE,
                    "bytes": (len(HOST_FACADE_EXTENSION_SYMBOLS)
                              * HOST_FACADE_STRIDE),
                },
            } if E000_REOPENING else {
                "original": {
                    "base": HOST_FACADE_BASE,
                    "bytes": len(HOST_FACADE_SYMBOLS) * HOST_FACADE_STRIDE,
                },
            }),
            "symbols": vector_addresses,
        },
        "fixed_state_contract": {
            "zero_page": {"base": FIXED_ZP_BASE, "bytes": FIXED_ZP_BYTES},
            "bank0": {"base": FIXED_BANK0_BASE, "bytes": FIXED_BANK0_BYTES},
            "bank0_code": {
                "base": FIXED_BANK0_CODE_BASE,
                "bytes": FIXED_BANK0_CODE_BYTES,
                "headroom_to_runtime_overlay_bytes": (
                    0xC356 - fixed_bank0_contract_end()),
            },
            "bank0_hot_bss": ({
                "base": FIXED_BANK0_HOT_BSS_BASE,
                "bytes": FIXED_BANK0_HOT_BSS_BYTES,
                "end_exclusive": (
                    FIXED_BANK0_HOT_BSS_BASE + FIXED_BANK0_HOT_BSS_BYTES),
                "following_noinit_bytes": (
                    0 if FULL_MAP_OWNERSHIP else FIXED_BANK0_NOINIT_BYTES),
                "owned_static_stack": ({
                    "section": FIXED_BLOCK_LEAF.OWNED_STACK_SECTION,
                    "base": FIXED_BLOCK_LEAF.OWNED_STACK_ADDRESS,
                    "bytes": FIXED_BLOCK_LEAF.OWNED_STACK_BYTES,
                } if FULL_MAP_OWNERSHIP else None),
                "geometry_authority": (
                    "full-map-state-ownership"
                    if FULL_MAP_OWNERSHIP else "historical-inherited-noinit"),
                "contract_end_exclusive": (
                    0xC354 if FULL_MAP_OWNERSHIP
                    else fixed_bank0_contract_end()),
                "headroom_to_runtime_overlay_bytes": (
                    2 if FULL_MAP_OWNERSHIP
                    else 0xC356 - fixed_bank0_contract_end()),
            } if BSS_TRIAGE else {"status": "not-selected"}),
            "symbols": fixed_state,
        },
        "fixed_block_rtov_fail_leaf": fixed_leaf,
        "window_direct_low_edges_outside_facade": owned_irq_tail_edges,
        "owned_IRQ_tail_contract": ({
            "owner_section": irq_tail_section,
            "target_symbol": "retired_window_brk_classifier",
            "target": f"0x{irq_tail_target:04x}",
            "edge_count": len(owned_irq_tail_edges),
            "authority": "final linked symbol identity plus exact IRQ owner",
        } if irq_tail_target is not None else {"status": "not-present"}),
        "owned_IRQ_tail_mutations_rejected": facade_edge_mutations,
        "claim_limit": (
            "Structural fixed-address and edge gate; only the exact owned IRQ "
            "tail continuation may bypass the ordinary host facade. Hardware "
            "behavior is not claimed."
        ),
    }
    write(out / f"fixed-host-facade-{suffix}.json",
          json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def _sectioned_disassembly(text: str) -> tuple[
        dict[tuple[str, int], dict[str, object]], dict[str, list[str]]]:
    """Parse functions without pretending a VMA identifies an overlay node."""
    nodes: dict[tuple[str, int], dict[str, object]] = {}
    section_lines: dict[str, list[str]] = {}
    section: str | None = None
    current: dict[str, object] | None = None
    for raw_line in text.lower().splitlines():
        section_header = re.match(r"^disassembly of section ([^:]+):$",
                                  raw_line.strip())
        if section_header:
            section = section_header.group(1)
            section_lines.setdefault(section, [])
            current = None
            continue
        if section is None:
            continue
        section_lines[section].append(raw_line)
        function_header = re.match(r"^([0-9a-f]+) <([^>]+)>:$",
                                   raw_line.strip())
        if function_header:
            address = int(function_header.group(1), 16)
            key = (section, address)
            current = nodes.setdefault(key, {
                "section": section,
                "address": address,
                "names": [],
                "lines": [],
            })
            name = function_header.group(2)
            if name not in current["names"]:
                current["names"].append(name)
            continue
        if current is not None:
            current["lines"].append(raw_line)
    return nodes, section_lines


def _direct_call_targets(lines: list[str]) -> list[int]:
    return [int(match.group(1), 16) for line in lines
            if (match := re.search(r"\b(?:jsr|jmp)\s+\$([0-9a-f]{4})\b",
                                   line))]


def _machine_instructions(lines: list[str]) -> list[tuple[str, str]]:
    instructions: list[tuple[str, str]] = []
    for line in lines:
        match = re.match(
            r"^\s*[0-9a-f]+:\s+(?:[0-9a-f]{2}\s+)+([a-z][a-z0-9]*)\s*(.*?)\s*$",
            line)
        if match:
            operand = match.group(2).split(";", 1)[0].strip()
            instructions.append((match.group(1), operand))
    return instructions


def _handoff_z_abi_errors(ownership_lines: list[str], copy_lines: list[str],
                          reveal_lines: list[str],
                          map_lines: list[str], *,
                          reveal_address: int = 0xB5EB) -> list[str]:
    """Bind both firmware-to-product ABI invariants before any I/O store."""
    ownership = _machine_instructions(ownership_lines)
    errors: list[str] = []
    if len(ownership) < 2 or ownership[0][0] != "sei":
        errors.append("ownership-first-instruction-is-not-sei")
    if (len(ownership) < 2 or ownership[1][0] != "ldz"
            or not re.fullmatch(r"#\$(?:0+)", ownership[1][1])):
        errors.append("ownership-does-not-normalize-z-immediately-after-sei")
    if (len(ownership) < 3 or ownership[2][0] != "jsr"
            or not re.fullmatch(
                rf"\${reveal_address:04x}(?:\s+<[^>]+>)?",
                ownership[2][1])):
        errors.append("ownership-does-not-reveal-mega65-io-before-register-access")

    reveal = _machine_instructions(reveal_lines)
    expected_reveal = [
        ("lda", "#$47"), ("sta", "$d02f"),
        ("lda", "#$53"), ("sta", "$d02f"), ("rts", ""),
    ]
    if reveal != expected_reveal:
        errors.append("mega65-io-knock-sequence-drift")

    # EOM is encoded as $ea and llvm-objdump renders it as NOP.  The sequence
    # deliberately derives A/X/Y=0 from the boundary-owned Z=0 invariant.
    map_switch = _machine_instructions(map_lines)
    expected_map_switch = [
        ("tza", ""), ("tax", ""), ("tay", ""), ("ldz", "#$80"),
        ("map", ""), ("nop", ""), ("ldz", "#$0"), ("rts", ""),
    ]
    if map_switch != expected_map_switch:
        errors.append("kernal-map-operand-sequence-drift")

    copy = _machine_instructions(copy_lines)
    stores = {(mnemonic, operand) for mnemonic, operand in copy}
    if ("stz", "$d702") not in stores:
        errors.append("fixed-handoff-size-payment-missing:$d702")
    if any(operand == "$d704" for _mnemonic, operand in copy):
        errors.append("redundant-d704-write-returned")
    return errors


def _handoff_z_abi_model_selftest() -> dict[str, str]:
    good = [
        "    b4a3: 78            sei",
        "    b4a4: a3 00         ldz #$0",
        "    b4a6: 20 eb b5      jsr $b5eb",
        "    b4a9: 9c 0e dd      stz $dd0e",
    ]
    copy = [
        "    b542: 9c 02 d7      stz $d702",
    ]
    reveal = [
        "    b5eb: a9 47         lda #$47",
        "    b5ed: 8d 2f d0      sta $d02f",
        "    b5f0: a9 53         lda #$53",
        "    b5f2: 8d 2f d0      sta $d02f",
        "    b5f5: 60            rts",
    ]
    map_switch = [
        "    b5f6: 6b            tza",
        "    b5f7: aa            tax",
        "    b5f8: a8            tay",
        "    b5f9: a3 80         ldz #$80",
        "    b5fb: 5c            map",
        "    b5fc: ea            nop",
        "    b5fd: a3 00         ldz #$0",
        "    b5ff: 60            rts",
    ]
    if _handoff_z_abi_errors(good, copy, reveal, map_switch):
        raise AssertionError("valid handoff boundary was rejected")
    mutations = {
        "missing-z-normalization": [good[0], good[2], good[3]],
        "late-z-normalization": [good[0], good[2], good[1], good[3]],
        "nonzero-z-normalization": [good[0],
                                    "    b482: a3 06         ldz #$6",
                                    good[2], good[3]],
        "missing-io-reveal-call": [good[0], good[1], good[3]],
        "late-io-reveal-call": [good[0], good[1], good[3], good[2]],
        "missing-size-payment": good,
        "redundant-d704-write": good,
    }
    for name, ownership in mutations.items():
        candidate_copy = [] if name == "missing-size-payment" else copy
        if name == "redundant-d704-write":
            candidate_copy = copy + [
                "    b545: 9c 04 d7      stz $d704",
            ]
        if not _handoff_z_abi_errors(
                ownership, candidate_copy, reveal, map_switch):
            raise AssertionError(f"handoff mutation accepted: {name}")
    reveal_mutations = {
        "missing-first-knock": reveal[1:],
        "wrong-second-knock": reveal[:2] + [
            "    b5ed: a9 52         lda #$52", *reveal[3:]],
    }
    for name, candidate_reveal in reveal_mutations.items():
        if not _handoff_z_abi_errors(
                good, copy, candidate_reveal, map_switch):
            raise AssertionError(f"handoff I/O mutation accepted: {name}")
    map_mutations = {
        "wrong-map-register-source": [
            "    b5f6: a9 01         lda #$1", *map_switch[1:]],
        "c000-plus-e000-map-mask": [
            *map_switch[:3], "    b5f6: a3 c0         ldz #$c0",
            *map_switch[4:]],
    }
    for name, bad_map_switch in map_mutations.items():
        if not _handoff_z_abi_errors(good, copy, reveal, bad_map_switch):
            raise AssertionError(f"handoff MAP-operand mutation accepted: {name}")
    return {
        "valid-sei-ldz-zero-prefix": "passed",
        "valid-mega65-io-knock": "passed",
        "missing-z-normalization": "rejected",
        "late-z-normalization": "rejected",
        "nonzero-z-normalization": "rejected",
        "missing-io-reveal-call": "rejected",
        "late-io-reveal-call": "rejected",
        "missing-first-knock": "rejected",
        "wrong-second-knock": "rejected",
        "missing-fixed-size-payment": "rejected",
        "redundant-d704-write": "rejected",
        "wrong-map-register-source": "rejected",
        "c000-plus-e000-map-mask": "rejected",
    }


def handoff_z_abi_gate(out: Path, target: Path,
                       suffix: str) -> dict[str, object]:
    elf = Path(str(target) + ".elf")
    disassembly = run([
        str(TOOLCHAIN / "llvm-objdump"), "-d", str(elf)
    ], capture=True)
    nodes, _section_lines = _sectioned_disassembly(disassembly)
    ownership = [row for row in nodes.values()
                 if "c2_kernal_take_ownership" in row["names"]]
    copy = [row for row in nodes.values() if "c2k_copy" in row["names"]]
    reveal = [row for row in nodes.values()
              if "c2_kernal_reveal_io" in row["names"]]
    map_switch = [row for row in nodes.values()
                  if "c2_kernal_map_window" in row["names"]]
    if (len(ownership) != 1 or len(copy) != 1 or len(reveal) != 1
            or len(map_switch) != 1):
        raise RuntimeError(
            "handoff ABI red: ownership/copy/reveal/map function is not unique")
    errors = _handoff_z_abi_errors(
        ownership[0]["lines"], copy[0]["lines"], reveal[0]["lines"],
        map_switch[0]["lines"],
        reveal_address=int(reveal[0]["address"]))
    if errors:
        raise RuntimeError(f"handoff ABI red: {errors}")
    sections = section_table(elf)
    handoff = sections.get(".lisp65_c2_kernal_handoff")
    if not handoff:
        raise RuntimeError("handoff ABI red: handoff section absent")
    report = {
        "format": "lisp65-c2-handoff-boundary-abi-v3",
        "status": "passed",
        "link_stage": suffix,
        "boundary": (
            "firmware-owned-state-to-llvm-mos-mega65-io-and-c2-ownership-order"
        ),
        "required_prefix": [
            "sei", "ldz #$00",
            f"jsr ${int(reveal[0]['address']):04x}",
        ],
        "observed_prefix": [
            f"{mnemonic} {operand}".rstrip()
            for mnemonic, operand in _machine_instructions(
                ownership[0]["lines"])[:3]
        ],
        "io_reveal_sequence": [
            f"{mnemonic} {operand}".rstrip()
            for mnemonic, operand in _machine_instructions(reveal[0]["lines"])
        ],
        "map_operand_sequence": [
            f"{mnemonic} {operand}".rstrip()
            for mnemonic, operand in _machine_instructions(
                map_switch[0]["lines"])
        ],
        "mapped_cpu_domain": (
            "0xe000-0xffff to physical bank-0; block-6 remains un-MAP so "
            "0xd000 I/O stays visible"
        ),
        "fixed_handoff_section": handoff,
        "size_payment": {
            "kept": "stz $d702",
            "omitted_as_controller-defined_side_effect": "write $d702 clears $d704",
        },
        "negative_matrix": _handoff_z_abi_model_selftest(),
        "hardware_origin": {
            "link_19": {
                "observed_z": "0x06",
                "effect": "C zero stores wrote 0x06 into IRQ controls and the DMA descriptor",
            },
            "link_20": {
                "observed_d700_cpu_view": "all zero / not MEGA65 I/O",
                "effect": "the correct descriptor was never triggered until the $47/$53 knock was repeated",
            },
            "link_23": {
                "observed_map_high": "0xc000",
                "effect": (
                    "mapping block 6 hid $d000 I/O behind Bank-0 RAM; the real "
                    "VIC raster IRQ could not be acknowledged and stormed"
                ),
            },
        },
        "claim_limit": (
            "Disassembly and mutation proof of the firmware-to-product Z and "
            "I/O-personality normalization boundary. Hardware execution is a separate gate."
        ),
    }
    write(out / f"handoff-z-abi-{suffix}.json",
          json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def _pre_ownership_violations(
        records: list[tuple[str, int, list[str]]], *,
        code_start: int, code_end: int, state_start: int, state_end: int,
        c2e_vector: int) -> list[dict[str, object]]:
    violations: list[dict[str, object]] = []
    for label, address, lines in records:
        if code_start <= address < code_end:
            violations.append({"node": label,
                               "reason": "session-code-in-boot-closure"})
        for line in lines:
            call = re.search(r"\b(?:jsr|jmp)\s+\$([0-9a-f]{4})\b", line)
            if call and code_start <= int(call.group(1), 16) < code_end:
                violations.append({"node": label,
                                   "reason": "session-code-edge-from-boot-closure",
                                   "instruction": line.strip()})
            operands = [int(item, 16)
                        for item in re.findall(r"\$([0-9a-f]{2,4})\b", line)]
            if any(state_start <= operand < state_end for operand in operands):
                violations.append({"node": label,
                                   "reason": "session-state-in-boot-closure",
                                   "instruction": line.strip()})
            if c2e_vector in operands:
                violations.append({"node": label,
                                   "reason": "session-cons-vector-in-boot-closure",
                                   "instruction": line.strip()})
    return violations


def _pre_handoff_fixed_domain_violations(
        records: list[tuple[str, int, list[str]]], *,
        fixed_start: int, fixed_end: int,
        window_start: int, window_end: int) -> list[dict[str, object]]:
    """Reject every C2 fixed-domain consumer before the ownership call."""
    violations: list[dict[str, object]] = []
    domains = (
        ("fixed-bank0", fixed_start, fixed_end),
        ("kernal-window", window_start, window_end),
    )
    for label, address, lines in records:
        for domain, start, end in domains:
            if start <= address < end:
                violations.append({
                    "node": label,
                    "reason": f"pre-handoff-node-in-{domain}",
                    "address": f"0x{address:04x}",
                })
        for line in lines:
            instructions = _machine_instructions([line])
            if not instructions:
                continue
            _mnemonic, operand = instructions[0]
            if operand.startswith("#"):
                continue
            addresses = [int(item, 16)
                         for item in re.findall(r"\$([0-9a-f]{4})\b", operand)]
            for domain, start, end in domains:
                if any(start <= value < end for value in addresses):
                    violations.append({
                        "node": label,
                        "reason": f"pre-handoff-operand-in-{domain}",
                        "instruction": line.strip(),
                    })
    return violations


def _relocation_records(text: str) -> list[dict[str, object]]:
    """Parse synthetic relocation fixtures without inferring code edges.

    Product gates use ``_structured_relocation_records`` below.  This parser
    remains only as the mutation-fixture adapter so no rendered tool output
    participates in a product claim.
    """
    current: str | None = None
    records: list[dict[str, object]] = []
    for raw in text.splitlines():
        section = re.match(r"^\s*Section \(\d+\) (\S+) \{$", raw)
        if section:
            current = section.group(1)
            continue
        if raw.strip() == "}":
            current = None
            continue
        if current is None:
            continue
        fields = raw.split()
        if len(fields) < 4 or not fields[0].startswith("0x"):
            continue
        try:
            offset = int(fields[0], 0)
            addend = int(fields[3], 0)
        except ValueError:
            continue
        source = current
        if source.startswith(".rela"):
            source = source[5:]
        elif source.startswith(".rel"):
            source = source[4:]
        records.append({
            "relocation_section": current,
            "source_section": source,
            "offset": offset,
            "type": fields[1],
            "target": fields[2],
            "addend": addend,
        })
    return records


def _structured_relocation_records(elf: Path) -> list[dict[str, object]]:
    """Return retained relocations with source-section provenance intact."""
    truth = ElfTruth.read(elf, llvm_readobj=TOOLCHAIN / "llvm-readobj")
    return [{
        "relocation_section": row.relocation_section,
        "source_section": row.source_section,
        "offset": row.offset,
        "type": row.relocation_type,
        "target": row.target,
        "addend": row.addend,
    } for row in truth.relocations]


def _sized_function_intervals(elf: Path) -> list[dict[str, object]]:
    """Return section-qualified STT_FUNC intervals from structured ELF."""
    truth = ElfTruth.read(elf, llvm_readobj=TOOLCHAIN / "llvm-readobj")
    return [{
        "section": row.section,
        "name": row.name.lower(),
        "address": row.start,
        "bytes": row.bytes,
        "end_exclusive": row.end_exclusive,
    } for row in truth.sized_intervals()]


def _bind_relocation_function_provenance(
        records: list[dict[str, object]], *,
        function_intervals: list[dict[str, object]],
        pre_handoff_intervals: list[dict[str, object]]) -> tuple[
            list[dict[str, object]], list[dict[str, object]]]:
    violations: list[dict[str, object]] = []
    bound: list[dict[str, object]] = []
    for record in records:
        offset = int(record["offset"])
        source_section = str(record["source_section"])
        unsized = [row for row in function_intervals
                   if row["section"] == source_section
                   and int(row["address"]) == offset
                   and int(row["bytes"]) == 0]
        candidates = [row for row in function_intervals
                      if row["section"] == source_section
                      and int(row["bytes"]) > 0
                      and int(row["address"]) <= offset
                      < int(row["end_exclusive"])]
        if unsized:
            violations.append({
                "reason": "source-function-unsized",
                "record": record,
                "symbols": unsized,
            })
        if len(candidates) != 1:
            violations.append({
                "reason": ("source-function-unresolved" if not candidates
                           else "source-function-overlap"),
                "record": record,
                "candidate_functions": candidates,
            })
            continue
        function = candidates[0]
        item = {**record, "source_function": function}
        bound.append(item)
        pre_matches = [interval for interval in pre_handoff_intervals
                       if interval["section"] == source_section
                       and int(interval["address"]) <= offset
                       < int(interval["end_exclusive"])]
        if pre_matches:
            violations.append({
                "reason": "pre-handoff-function-reference-to-profile-data",
                "record": item,
                "pre_handoff_intervals": pre_matches,
            })
    return violations, bound


def _profile_data_reference_violations(
        records: list[dict[str, object]], *,
        symbols: dict[str, int],
        component_ranges: dict[str, tuple[int, int]],
        function_intervals: list[dict[str, object]],
        pre_handoff_intervals: list[dict[str, object]]) -> tuple[
            list[dict[str, object]], list[dict[str, object]], set[str]]:
    """Classify every relocation whose resolved target is moved profile data."""
    violations: list[dict[str, object]] = []
    matched: list[dict[str, object]] = []
    covered: set[str] = set()
    profile_start = min(start for start, _end in component_ranges.values())
    profile_end = max(end for _start, end in component_ranges.values())
    for record in records:
        target = str(record["target"])
        addend = int(record["addend"])
        target_address = symbols.get(target)
        if target_address is not None:
            target_address += addend
        component: str | None = None
        if target in component_ranges:
            component = target
        elif target_address is not None and profile_start <= target_address < profile_end:
            for name, (start, end) in component_ranges.items():
                if start <= target_address < end:
                    component = name
                    break
        if component is None:
            continue
        matched.append({**record, "component": component})
        covered.add(component)
    provenance_violations, bound = _bind_relocation_function_provenance(
        matched, function_intervals=function_intervals,
        pre_handoff_intervals=pre_handoff_intervals)
    violations.extend(provenance_violations)
    missing = sorted(set(component_ranges) - covered)
    for component in missing:
        violations.append({
            "reason": "moved-profile-data-component-has-no-retained-reference",
            "component": component,
        })
    return violations, bound, covered


def _profile_data_reference_model_selftest() -> dict[str, str]:
    synthetic = """\
Relocations [
  Section (10) .rela.text.vm_callprim {
    0x1 R_MOS_ADDR16 .rodata.vm_callprim 0x0
  }
  Section (11) .rela.text.vm_native_call {
    0x2 R_MOS_ADDR8_LO .rodata.vm_native_call 0x0
  }
  Section (12) .rela.text.eval_v2_workbench_service {
    0x3 R_MOS_ADDR8_HI .rodata.eval_v2_workbench_service 0x0
  }
]
"""
    records = _relocation_records(synthetic)
    ranges = {
        ".rodata.eval_v2_workbench_service": (0xFD12, 0xFD32),
        ".rodata.vm_callprim": (0xFD32, 0xFDD6),
        ".rodata.vm_native_call": (0xFDD6, 0xFE68),
    }
    functions = [
        {"section": ".text.vm_callprim", "name": "vm_callprim",
         "address": 0, "bytes": 2, "end_exclusive": 2},
        {"section": ".text.vm_native_call", "name": "vm_native_call",
         "address": 2, "bytes": 2, "end_exclusive": 4},
        {"section": ".text.eval_v2_workbench_service",
         "name": "eval_v2_workbench_service",
         "address": 3, "bytes": 2, "end_exclusive": 5},
    ]
    violations, _matched, covered = _profile_data_reference_violations(
        records, symbols={}, component_ranges=ranges,
        function_intervals=functions, pre_handoff_intervals=[])
    if violations or covered != set(ranges):
        raise AssertionError("valid post-ownership data references were rejected")
    output_record = [{
        "relocation_section": ".rela.text.vm_callprim",
        "source_section": ".text.vm_callprim",
        "offset": 1,
        "type": "R_MOS_ADDR16",
        "target": PROFILE_RODATA_SECTION,
        "addend": 0x20,
    }]
    violations, _matched, output_covered = _profile_data_reference_violations(
        output_record, symbols={PROFILE_RODATA_SECTION: PROFILE_RODATA_BASE},
        component_ranges={".rodata.vm_callprim": (
            PROFILE_RODATA_BASE + 0x20, PROFILE_RODATA_BASE + 0xC4)},
        function_intervals=functions,
        pre_handoff_intervals=[{
            "section": ".text.vm_callprim", "name": "pre",
            "address": 0, "end_exclusive": 2,
        }])
    if output_covered != {".rodata.vm_callprim"}:
        raise AssertionError("output-section plus addend did not resolve")
    if not any(row["reason"] ==
               "pre-handoff-function-reference-to-profile-data"
               for row in violations):
        raise AssertionError("pre-handoff function reference was accepted")
    violations, _matched, _covered = _profile_data_reference_violations(
        records[:-1], symbols={}, component_ranges=ranges,
        function_intervals=functions, pre_handoff_intervals=[])
    if not any(row["reason"] ==
               "moved-profile-data-component-has-no-retained-reference"
               for row in violations):
        raise AssertionError("unreferenced moved component was accepted")
    unknown = [{**output_record[0], "offset": 9}]
    violations, _matched, _covered = _profile_data_reference_violations(
        unknown, symbols={PROFILE_RODATA_SECTION: PROFILE_RODATA_BASE},
        component_ranges={".rodata.vm_callprim": (
            PROFILE_RODATA_BASE + 0x20, PROFILE_RODATA_BASE + 0xC4)},
        function_intervals=functions, pre_handoff_intervals=[])
    if not any(row["reason"] == "source-function-unresolved"
               for row in violations):
        raise AssertionError("unknown source function was accepted")
    overlapping = functions + [{
        "section": ".text.vm_callprim", "name": "alias",
        "address": 1, "bytes": 1, "end_exclusive": 2,
    }]
    violations, _matched, _covered = _profile_data_reference_violations(
        output_record, symbols={PROFILE_RODATA_SECTION: 0xFD12},
        component_ranges={".rodata.vm_callprim": (0xFD32, 0xFDD6)},
        function_intervals=overlapping, pre_handoff_intervals=[])
    if not any(row["reason"] == "source-function-overlap"
               for row in violations):
        raise AssertionError("overlapping function provenance was accepted")
    unsized = functions + [{
        "section": ".text.vm_callprim", "name": "unsized",
        "address": 1, "bytes": 0, "end_exclusive": 1,
    }]
    violations, _matched, _covered = _profile_data_reference_violations(
        output_record, symbols={PROFILE_RODATA_SECTION: 0xFD12},
        component_ranges={".rodata.vm_callprim": (0xFD32, 0xFDD6)},
        function_intervals=unsized, pre_handoff_intervals=[])
    if not any(row["reason"] == "source-function-unsized"
               for row in violations):
        raise AssertionError("unsized function provenance was accepted")
    return {
        "post-ownership-absolute-reference": "passed",
        "post-ownership-low-immediate-reference": "passed",
        "post-ownership-high-immediate-reference": "passed",
        "output-section-plus-addend-reference": "passed",
        "pre-handoff-function-reference": "rejected",
        "unknown-source-function": "rejected",
        "overlapping-function-provenance": "rejected",
        "unsized-function-provenance": "rejected",
        "missing-component-reference": "rejected",
    }


def _source_ownership_order_errors(source: str) -> list[str]:
    # Gate executable source, not explanatory prose that may name the same
    # call.  String literals in this narrow main.c region do not contain any
    # of the bound call tokens.
    source = re.sub(r"/\*.*?\*/|//[^\n]*", "", source,
                    flags=re.DOTALL)
    calls = {
        "ownership": "c2_kernal_take_ownership()",
        "overlay-install": "vm_install_staged_boot_overlay()",
        "prepare": "c2_product_prepare_boot()",
        "boot": "c2_product_boot()",
        "repl": "repl()",
    }
    positions: dict[str, int] = {}
    errors: list[str] = []
    for name, token in calls.items():
        if source.count(token) != 1:
            errors.append(f"source-call-not-unique:{name}")
        else:
            positions[name] = source.index(token)
    if len(positions) == len(calls):
        if positions["ownership"] > positions["overlay-install"]:
            errors.append("overlay-install-precedes-ownership")
        if positions["ownership"] > positions["prepare"]:
            errors.append("prepare-precedes-ownership")
        if positions["ownership"] > positions["boot"]:
            errors.append("boot-precedes-ownership")
        if positions["ownership"] > positions["repl"]:
            errors.append("repl-precedes-ownership")
    return errors


def _pre_ownership_model_selftest() -> dict[str, str]:
    synthetic = """\
Disassembly of section .boot-a:
0000c356 <root_a>:
    c356: 60            rts
Disassembly of section .boot-b:
0000c356 <root_b>:
    c356: 60            rts
"""
    nodes, _lines = _sectioned_disassembly(synthetic)
    if set(nodes) != {(".boot-a", 0xC356), (".boot-b", 0xC356)}:
        raise AssertionError("section-qualified same-VMA roots collapsed")

    mutations = {
        "boot-edge-to-session-code": "    c356: 20 9e e0      jsr $e09e",
        "boot-operand-to-session-state": "    c356: ad 5f f1      lda $f15f",
        "boot-edge-to-c2e-cons-vector": "    c356: 20 cd b5      jsr $b5cd",
    }
    expected = {
        "boot-edge-to-session-code": "session-code-edge-from-boot-closure",
        "boot-operand-to-session-state": "session-state-in-boot-closure",
        "boot-edge-to-c2e-cons-vector": "session-cons-vector-in-boot-closure",
    }
    for name, instruction in mutations.items():
        reasons = {row["reason"] for row in _pre_ownership_violations(
            [(name, 0xC356, [instruction])], code_start=0xE09E,
            code_end=0xE0C6, state_start=0xF15F, state_end=0xF2B9,
            c2e_vector=0xB5CD)}
        if expected[name] not in reasons:
            raise AssertionError(f"pre-ownership mutation accepted: {name}")
    boundary_mutations = {
        "pre-handoff-edge-to-kernal-window": (
            "    4600: 20 6f e1      jsr $e16f",
            "pre-handoff-operand-in-kernal-window"),
        "pre-handoff-edge-to-vm-logical-pc-helper": (
            "    4600: 20 20 e8      jsr $e820",
            "pre-handoff-operand-in-kernal-window"),
        "pre-handoff-edge-to-c2-root-walker": (
            "    4600: 20 80 e9      jsr $e980",
            "pre-handoff-operand-in-kernal-window"),
        "pre-handoff-operand-to-fixed-state": (
            "    4600: 9c b2 c0      stz $c0b2",
            "pre-handoff-operand-in-fixed-bank0"),
    }
    for name, (instruction, expected_reason) in boundary_mutations.items():
        reasons = {row["reason"] for row in
                   _pre_handoff_fixed_domain_violations(
                       [(name, 0x4600, [instruction])],
                       fixed_start=FIXED_BANK0_BASE,
                       fixed_end=fixed_bank0_contract_end(),
                       window_start=KERNAL_WINDOW_BASE,
                       window_end=KERNAL_WINDOW_BASE + KERNAL_WINDOW_BYTES)}
        if expected_reason not in reasons:
            raise AssertionError(f"pre-handoff mutation accepted: {name}")
    source_good = """
if (!c2_kernal_take_ownership()) return 1;
if (!vm_install_staged_boot_overlay()) return 1;
if (!c2_product_prepare_boot()) return 1;
if (!c2_product_boot()) return 1;
repl();
"""
    if _source_ownership_order_errors(source_good):
        raise AssertionError("valid ownership source order was rejected")
    source_mutations = {
        "overlay-install-before-ownership": """
if (!vm_install_staged_boot_overlay()) return 1;
if (!c2_kernal_take_ownership()) return 1;
if (!c2_product_prepare_boot()) return 1;
if (!c2_product_boot()) return 1;
repl();
""",
        "prepare-before-ownership": """
if (!c2_product_prepare_boot()) return 1;
if (!c2_kernal_take_ownership()) return 1;
if (!vm_install_staged_boot_overlay()) return 1;
if (!c2_product_boot()) return 1;
repl();
""",
        "boot-before-ownership": """
if (!c2_product_boot()) return 1;
if (!c2_kernal_take_ownership()) return 1;
if (!vm_install_staged_boot_overlay()) return 1;
if (!c2_product_prepare_boot()) return 1;
repl();
""",
        "repl-before-ownership": """
repl();
if (!c2_kernal_take_ownership()) return 1;
if (!vm_install_staged_boot_overlay()) return 1;
if (!c2_product_prepare_boot()) return 1;
if (!c2_product_boot()) return 1;
""",
    }
    for name, candidate in source_mutations.items():
        if not _source_ownership_order_errors(candidate):
            raise AssertionError(f"ownership-order mutation accepted: {name}")
    return {
        "same-vma-section-identity": "passed",
        "boot-edge-to-session-code": "rejected",
        "boot-operand-to-session-state": "rejected",
        "boot-edge-to-c2e-cons-vector": "rejected",
        "pre-handoff-edge-to-kernal-window": "rejected",
        "pre-handoff-edge-to-vm-logical-pc-helper": "rejected",
        "pre-handoff-edge-to-c2-root-walker": "rejected",
        "pre-handoff-operand-to-fixed-state": "rejected",
        "overlay-install-before-ownership": "rejected",
        "prepare-before-ownership": "rejected",
        "boot-before-ownership": "rejected",
        "repl-before-ownership": "rejected",
    }


def pre_ownership_gate(out: Path, target: Path, suffix: str) -> dict[str, object]:
    """Prove ownership precedes fixed-domain use and isolates session state."""
    elf = Path(str(target) + ".elf")
    sections = section_table(elf)
    symbols = defined_symbols(elf)
    code = sections.get(".lisp65_c2_kernal_window.session_emitter_code")
    state = sections.get(".lisp65_c2_kernal_window.session_emitter_state")
    resident = sections.get(".lisp65_c2_kernal_window.c2_resident")
    if ((code is not None and code["bytes"] != 0) or not state or
            state["bytes"] != SESSION_EMITTER_STATE_BYTES):
        raise RuntimeError(
            f"pre-ownership red: session E000 geometry code={code} state={state}")
    code = code or {"address": 0, "bytes": 0}
    if not resident or not resident["bytes"]:
        raise RuntimeError("pre-ownership red: C2 resident window absent")
    post_handoff_helpers = {
        name: symbols.get(name) for name in (
            "vm_logical_relative_target", "c2_product_gc_mark_roots")
    }
    helper_drift = {
        name: address for name, address in post_handoff_helpers.items()
        if address is None or not (
            resident["address"] <= address
            < resident["address"] + resident["bytes"])
    }
    if helper_drift:
        raise RuntimeError(
            f"pre-ownership red: post-handoff helper placement {helper_drift}")

    disassembly = run([
        str(TOOLCHAIN / "llvm-objdump"), "-d", str(elf)
    ], capture=True)
    nodes, section_lines = _sectioned_disassembly(disassembly)
    function_intervals = _sized_function_intervals(elf)
    boot_contract = [(fields[2].lower(), fields[-1].lower())
                     for spec in BOOT_SLICE_SPECS
                     if len(fields := spec.split(":")) == 10]
    if len(boot_contract) != len(BOOT_SLICE_SPECS):
        raise RuntimeError("pre-ownership red: malformed generated boot slice spec")
    root_nodes: list[tuple[str, int]] = []
    missing_roots: list[dict[str, str]] = []
    for section, entry in boot_contract:
        matches = [key for key, row in nodes.items()
                   if key[0] == section and entry in row["names"]]
        if len(matches) != 1:
            missing_roots.append({"section": section, "entry": entry,
                                  "matches": str(len(matches))})
        else:
            root_nodes.append(matches[0])
    if missing_roots:
        raise RuntimeError(f"pre-ownership red: boot roots unresolved {missing_roots}")

    runtime_sections = {spec.split(":")[2].lower()
                        for spec in (BOOT_SLICE_SPECS + BOOT_DATA_SPECS
                                     + SESSION_SLICE_SPECS)}
    runtime_sections.add(".lisp65_workbench_overlay")
    if BANK3_STAGING_SLICES:
        runtime_sections.add(".lisp65_boot_bank3_stage")
    ordinary_nodes = {
        key: row for key, row in nodes.items()
        if key[0] not in runtime_sections and not key[0].startswith(".lisp65_rt_")
    }
    address_to_ordinary: dict[int, list[tuple[str, int]]] = {}
    for key in ordinary_nodes:
        address_to_ordinary.setdefault(key[1], []).append(key)

    main_nodes = [key for key, row in ordinary_nodes.items()
                  if "main" in row["names"]]
    ownership_address = symbols.get("c2_kernal_take_ownership")
    if len(main_nodes) != 1 or ownership_address is None:
        raise RuntimeError("pre-ownership red: main or ownership symbol absent")
    main_node = main_nodes[0]
    main_lines: list[str] = ordinary_nodes[main_node]["lines"]
    main_prefix: list[str] = []
    handoff_seen = False
    ownership_call_address: int | None = None
    for line in main_lines:
        call = re.search(r"\b(?:jsr|jmp)\s+\$([0-9a-f]{4})\b", line)
        if call and int(call.group(1), 16) == ownership_address:
            instruction = re.match(r"^\s*([0-9a-f]+):", line)
            if not instruction:
                raise RuntimeError(
                    "pre-ownership red: ownership instruction address absent")
            ownership_call_address = int(instruction.group(1), 16)
            handoff_seen = True
            break
        main_prefix.append(line)
    if not handoff_seen or ownership_call_address is None:
        raise RuntimeError("pre-ownership red: main has no explicit ownership cutpoint")

    boot_records: list[tuple[str, int, list[str]]] = []
    boot_pending: list[tuple[str, int]] = []
    for section, _entry in boot_contract:
        geometry = sections.get(section)
        lines = section_lines.get(section)
        if geometry is None or lines is None:
            raise RuntimeError(f"pre-ownership red: boot section absent {section}")
        boot_records.append((f"boot-section:{section}", geometry["address"], lines))
        section_end = geometry["address"] + geometry["bytes"]
        for target_address in _direct_call_targets(lines):
            if geometry["address"] <= target_address < section_end:
                continue
            boot_pending.extend(address_to_ordinary.get(target_address, []))
    pre_handoff_pending: list[tuple[str, int]] = []
    for target_address in _direct_call_targets(main_prefix):
        pre_handoff_pending.extend(address_to_ordinary.get(target_address, []))

    def collect_closure(pending: list[tuple[str, int]]) -> set[tuple[str, int]]:
        closure: set[tuple[str, int]] = set()
        pending = pending.copy()
        while pending:
            key = pending.pop()
            if key in closure:
                continue
            closure.add(key)
            for target_address in _direct_call_targets(
                    ordinary_nodes[key]["lines"]):
                pending.extend(candidate for candidate in
                               address_to_ordinary.get(target_address, [])
                               if candidate not in closure)
        return closure

    pre_handoff_closure = collect_closure(pre_handoff_pending)
    closure = collect_closure(boot_pending + pre_handoff_pending)

    def interval_for_node(key: tuple[str, int]) -> dict[str, object]:
        names = set(str(name) for name in ordinary_nodes[key]["names"])
        candidates = [
            row for row in function_intervals
            if row["section"] == key[0]
            and int(row["address"]) == key[1]
            and str(row["name"]) in names
            and int(row["bytes"]) > 0
        ]
        if len(candidates) != 1:
            raise RuntimeError(
                f"pre-ownership red: ambiguous sized function interval "
                f"for {key} names={sorted(names)} candidates={candidates}")
        return candidates[0]

    pre_handoff_function_intervals = [
        {**interval_for_node(key), "ownership_class": "pre-handoff-closure"}
        for key in sorted(pre_handoff_closure)
    ]
    main_interval = interval_for_node(main_node)
    if not (int(main_interval["address"]) < ownership_call_address
            <= int(main_interval["end_exclusive"])):
        raise RuntimeError(
            "pre-ownership red: main ownership cutpoint outside sized main")
    pre_handoff_function_intervals.append({
        **main_interval,
        "end_exclusive": ownership_call_address,
        "bytes": ownership_call_address - int(main_interval["address"]),
        "ownership_class": "main-prefix-before-ownership-call",
    })
    for index, left in enumerate(pre_handoff_function_intervals):
        for right in pre_handoff_function_intervals[index + 1:]:
            if (left["section"] == right["section"]
                    and int(left["address"]) < int(right["end_exclusive"])
                    and int(right["address"]) < int(left["end_exclusive"])):
                raise RuntimeError(
                    "pre-ownership red: overlapping provenance intervals "
                    f"{left} {right}")

    records = boot_records + [
        (f"{key[0]}:{'/'.join(ordinary_nodes[key]['names'])}", key[1],
         ordinary_nodes[key]["lines"])
        for key in sorted(closure)
    ]
    records.append(("main-before-c2-kernal-take-ownership",
                    main_node[1], main_prefix))
    pre_handoff_records = [
        (f"{key[0]}:{'/'.join(ordinary_nodes[key]['names'])}", key[1],
         ordinary_nodes[key]["lines"])
        for key in sorted(pre_handoff_closure)
    ]
    pre_handoff_records.append(("main-before-c2-kernal-take-ownership",
                                main_node[1], main_prefix))
    boundary_violations = _pre_handoff_fixed_domain_violations(
        pre_handoff_records,
        fixed_start=FIXED_BANK0_BASE,
        fixed_end=fixed_bank0_contract_end(),
        window_start=KERNAL_WINDOW_BASE,
        window_end=KERNAL_WINDOW_BASE + KERNAL_WINDOW_BYTES)
    if boundary_violations:
        raise RuntimeError(
            f"pre-ownership red: fixed-domain use before handoff "
            f"{boundary_violations}")
    violations = _pre_ownership_violations(
        records, code_start=code["address"],
        code_end=code["address"] + code["bytes"],
        state_start=state["address"],
        state_end=state["address"] + state["bytes"],
        c2e_vector=symbols.get("c2_facade_c2e_cons", -1))
    if violations:
        raise RuntimeError(f"pre-ownership red: {violations}")

    main_source = (ROOT / "src/main.c").read_text(encoding="utf-8")
    source_order_errors = _source_ownership_order_errors(main_source)
    if source_order_errors:
        raise RuntimeError(
            f"pre-ownership red: source handoff order drift {source_order_errors}")

    negative_matrix = _pre_ownership_model_selftest()
    report = {
        "format": "lisp65-c2-pre-ownership-closure-v3",
        "status": "passed",
        "link_stage": suffix,
        "node_identity": "section-and-vma",
        "boot_roots": [
            {"section": section, "entry": entry,
             "vma": next(key[1] for key in root_nodes if key[0] == section)}
            for section, entry in boot_contract
        ],
        "boot_section_count": len(boot_records),
        "ordinary_closure_function_count": len(closure),
        "pre_handoff_closure_function_count": len(pre_handoff_closure),
        "pre_handoff_function_intervals": pre_handoff_function_intervals,
        "main_ownership_call_address": ownership_call_address,
        "pre_handoff_source_sections": sorted(
            {key[0] for key in pre_handoff_closure} | {main_node[0]}),
        "pre_handoff_fixed_domain": {
            "fixed_bank0": (
                f"0x{FIXED_BANK0_BASE:04x}-"
                f"0x{fixed_bank0_contract_end() - 1:04x}"
            ),
            "kernal_window": "0xe000-0xffff",
            "consumer_count": 0,
        },
        "post_handoff_only_helpers": {
            name: f"0x{address:04x}"
            for name, address in post_handoff_helpers.items()
        },
        "session_emitter_code": code,
        "session_emitter_state": state,
        "session_code_edges_from_boot_closure": 0,
        "session_state_operands_from_boot_closure": 0,
        "session_cons_vector_edges_from_boot_closure": 0,
        "negative_matrix": negative_matrix,
        "source_order": (
            "c2_kernal_take_ownership-before-overlay-install-"
            "c2_product_prepare_boot-c2_product_boot-and-repl"
        ),
        "claim_limit": (
            "Section-qualified direct pre-handoff and boot-phase closures plus "
            "source-order gate; hardware behavior and unresolved indirect call "
            "targets are not claimed."
        ),
    }
    write(out / f"pre-ownership-closure-{suffix}.json",
          json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def profile_data_reference_gate(
        out: Path, target: Path, suffix: str,
        pre_ownership: dict[str, object]) -> dict[str, object]:
    """Prove moved immutable profile data has no pre-handoff reader.

    This is deliberately independent of the owned-window control-flow gate:
    retained relocations cover absolute and split low/high address formation,
    while the pre-ownership closure supplies only the reachability boundary.
    """
    elf = Path(str(target) + ".elf")
    sections = section_table(elf)
    symbols = defined_symbols(elf)
    geometry = sections.get(PROFILE_RODATA_SECTION)
    expected_geometry = {
        "address": PROFILE_RODATA_BASE,
        "bytes": PROFILE_RODATA_BYTES,
    }
    if geometry != expected_geometry:
        raise RuntimeError(
            f"profile-data reference red: geometry {geometry} != {expected_geometry}")
    marker_names = {
        ".rodata.eval_v2_workbench_service": (
            "__lisp65_c2_profile_rodata_eval_start",
            "__lisp65_c2_profile_rodata_eval_end"),
        ".rodata.vm_callprim": (
            "__lisp65_c2_profile_rodata_callprim_start",
            "__lisp65_c2_profile_rodata_callprim_end"),
        ".rodata.vm_native_call": (
            "__lisp65_c2_profile_rodata_native_start",
            "__lisp65_c2_profile_rodata_native_end"),
    }
    component_ranges: dict[str, tuple[int, int]] = {}
    for component, (start_name, end_name) in marker_names.items():
        start = symbols.get(start_name)
        end = symbols.get(end_name)
        expected = PROFILE_RODATA_INPUT_SECTIONS[component]
        if start is None or end is None or end - start != expected:
            raise RuntimeError(
                f"profile-data reference red: component geometry {component} "
                f"start={start} end={end} expected={expected}")
        component_ranges[component] = (start, end)

    records = _structured_relocation_records(elf)
    pre_intervals = pre_ownership.get("pre_handoff_function_intervals", [])
    if not pre_intervals:
        raise RuntimeError(
            "profile-data reference red: pre-handoff function intervals absent")
    symbols[PROFILE_RODATA_SECTION] = int(geometry["address"])
    function_intervals = _sized_function_intervals(elf)
    violations, matched, covered = _profile_data_reference_violations(
        records, symbols=symbols, component_ranges=component_ranges,
        function_intervals=function_intervals,
        pre_handoff_intervals=pre_intervals)
    if violations:
        raise RuntimeError(
            f"profile-data reference red: relocation violations {violations}")

    report = {
        "format": "lisp65-c2-profile-data-reference-v1",
        "status": "passed",
        "link_stage": suffix,
        "owned_data_section": PROFILE_RODATA_SECTION,
        "geometry": geometry,
        "components": {
            name: {"address": start, "bytes": end - start}
            for name, (start, end) in component_ranges.items()
        },
        "proof_model": (
            "all retained relocations resolving through input names or the "
            "owned output-section base plus addend are bound to exactly one "
            "positive-sized section-qualified function interval and checked "
            "against explicit pre-handoff function intervals"
        ),
        "pre_handoff_function_intervals": pre_intervals,
        "function_interval_count": len(function_intervals),
        "matched_relocation_count": len(matched),
        "matched_relocations": matched,
        "covered_components": sorted(covered),
        "pre_handoff_references": 0,
        "negative_matrix": _profile_data_reference_model_selftest(),
        "claim_limit": (
            "Static relocation and direct pre-handoff closure proof. Indirect "
            "runtime-computed addresses not represented by an ELF relocation "
            "and hardware execution are not claimed."
        ),
    }
    write(out / f"profile-data-reference-{suffix}.json",
          json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def _owned_edge_violation(
        opcode: str, source_node: tuple[str, int], target: int,
        instruction_owners: dict[int, tuple[str, int]],
        function_entries: set[int],
        owned_tail_continuations: set[tuple[tuple[str, int], int]] | None = None
        ) -> str | None:
    """Classify one direct edge into the owned CPU window.

    Function entries are deliberately T/t-only.  Absolute and weak aliases are
    not passed to this function and can therefore never manufacture ownership.
    """
    target_node = instruction_owners.get(target)
    if target_node is None:
        return "target-not-owned-executable-instruction"
    if opcode == "jsr":
        return None if target in function_entries else "jsr-not-function-entry"
    if opcode != "jmp":
        return "unsupported-direct-edge-opcode"
    if ((source_node, target)
            in (owned_tail_continuations or set())):
        return None
    if target_node == source_node:
        return None
    return None if target in function_entries else "inter-function-jmp-not-entry"


def _owned_control_flow_model_selftest() -> dict[str, str]:
    first = (".owned.code", 0xE000)
    second = (".owned.code", 0xE010)
    instruction_owners = {
        0xE000: first,
        0xE003: first,
        0xE010: second,
        0xE011: second,
    }
    function_entries = {0xE000, 0xE010}
    owned_tail = {(first, 0xE011)}
    cases = {
        "same-function-symbol-less-basic-block": (
            "jmp", first, 0xE003, None),
        "same-function-mid-instruction": (
            "jmp", first, 0xE002,
            "target-not-owned-executable-instruction"),
        "owned-state-or-data-target": (
            "jmp", first, 0xFF80,
            "target-not-owned-executable-instruction"),
        "inter-function-non-entry-offset": (
            "jmp", first, 0xE011,
            "inter-function-jmp-not-entry"),
        "owned-tail-continuation": (
            "jmp", first, 0xE011, None),
        "jsr-to-internal-basic-block": (
            "jsr", first, 0xE003, "jsr-not-function-entry"),
        # $ffd2 is deliberately imagined to exist in an unfiltered nm alias
        # set.  It is absent from T/t executable entries and must stay red.
        "absolute-weak-alias-disguised-exit": (
            "jmp", first, 0xFFD2,
            "target-not-owned-executable-instruction"),
    }
    result: dict[str, str] = {}
    for name, (opcode, source, target, expected) in cases.items():
        actual = _owned_edge_violation(
            opcode, source, target, instruction_owners, function_entries,
            owned_tail if name == "owned-tail-continuation" else set())
        if actual != expected:
            raise AssertionError(
                f"owned-control-flow selftest {name}: {actual} != {expected}")
        result[name] = "passed" if expected is None else "rejected"
    return result


def _require_named_model_matrix(name: str, observed: dict[str, str],
                                expected: dict[str, str]) -> dict[str, object]:
    """Require both matrix membership and outcomes, with a two-sided report."""
    missing = sorted(set(expected) - set(observed))
    unexpected = sorted(set(observed) - set(expected))
    mismatched = {
        member: {"expected": expected[member], "observed": observed[member]}
        for member in sorted(set(expected) & set(observed))
        if expected[member] != observed[member]
    }
    report: dict[str, object] = {
        "expected": dict(sorted(expected.items())),
        "observed": dict(sorted(observed.items())),
        "missing": missing,
        "unexpected": unexpected,
        "mismatched": mismatched,
    }
    if missing or unexpected or mismatched:
        raise RuntimeError(f"{name} drift: {json.dumps(report, sort_keys=True)}")
    return report


def _owned_control_flow_matrix_contract_selftest(
        observed: dict[str, str]) -> dict[str, str]:
    expected = {
        "absolute-weak-alias-disguised-exit": "rejected",
        "inter-function-non-entry-offset": "rejected",
        "jsr-to-internal-basic-block": "rejected",
        "owned-state-or-data-target": "rejected",
        "owned-tail-continuation": "passed",
        "same-function-mid-instruction": "rejected",
        "same-function-symbol-less-basic-block": "passed",
    }
    _require_named_model_matrix("owned-control-flow matrix", observed, expected)
    mutations: dict[str, str] = {}
    for mutation, candidate in {
        "missing-authorized-case": {
            key: value for key, value in observed.items()
            if key != "owned-tail-continuation"
        },
        "unregistered-extra-case": {**observed, "unregistered": "passed"},
        "wrong-case-outcome": {**observed, "owned-tail-continuation": "rejected"},
    }.items():
        try:
            _require_named_model_matrix(
                f"owned-control-flow mutation {mutation}", candidate, expected)
        except RuntimeError as exc:
            text = str(exc)
            if not all(token in text for token in
                       ("expected", "observed", "missing", "unexpected",
                        "mismatched")):
                raise AssertionError(
                    f"owned-control-flow mutation lacks two-sided report: {text}")
            mutations[mutation] = "rejected"
        else:
            raise AssertionError(
                f"owned-control-flow mutation survived: {mutation}")
    return mutations


def _owned_control_flow_gate(elf: Path, sections: dict[str, dict[str, int]],
                             objdump: str,
                             truth: ElfTruth) -> dict[str, object]:
    non_executable = {
        ".lisp65_c2_kernal_window.session_emitter_state",
        PROFILE_RODATA_SECTION,
        ".lisp65_c2_kernal_window.state",
        ".lisp65_c2_vectors",
    }
    executable_sections = {
        name for name in KERNAL_SECTIONS
        if name not in non_executable and sections.get(name, {}).get("bytes", 0)
    }
    nodes, _section_lines = _sectioned_disassembly(objdump)
    owned_nodes = {
        key: row for key, row in nodes.items() if key[0] in executable_sections
    }
    instruction_owners: dict[int, tuple[str, int]] = {}
    for key, row in owned_nodes.items():
        for line in row["lines"]:
            match = re.match(r"^\s*([0-9a-f]+):\s", line)
            if not match:
                continue
            address = int(match.group(1), 16)
            previous = instruction_owners.get(address)
            if previous is not None and previous != key:
                raise RuntimeError(
                    f"KERNAL freedom red: ambiguous instruction owner at 0x{address:04x}")
            instruction_owners[address] = key

    function_entries: dict[int, str] = {}
    ignored_aliases: list[str] = []
    for symbol in truth.symbols:
        address = symbol.value
        name = symbol.name
        if not KERNAL_WINDOW_BASE <= address < KERNAL_WINDOW_BASE + KERNAL_WINDOW_BYTES:
            continue
        if (symbol.symbol_type == "Function"
                and symbol.section in executable_sections
                and address in instruction_owners):
            function_entries[address] = name
        elif symbol.section == "Absolute" or symbol.binding == "Weak":
            ignored_aliases.append(name)

    violations: list[dict[str, object]] = []
    classifier = truth.symbols_by_name.get("retired_window_brk_classifier", [])
    irq_return = truth.symbols_by_name.get("c2_kernal_irq_return", [])
    owned_tail_continuations: set[tuple[tuple[str, int], int]] = set()
    if len(classifier) == 1 and len(irq_return) == 1:
        owned_tail_continuations.add(
            ((classifier[0].section, classifier[0].value),
             irq_return[0].value))
    observed_owned_tail_continuations: list[dict[str, object]] = []
    internal_basic_block_jumps = 0
    entry_edges = 0
    direct_window_edges = 0
    audited_pre_main_chrout = 0
    for source_node, row in nodes.items():
        for line in row["lines"]:
            edge = re.search(
                r"\b(jsr|jmp)\s+\$([ef][0-9a-f]{3})\b", line)
            if not edge:
                continue
            opcode = edge.group(1)
            target = int(edge.group(2), 16)
            direct_window_edges += 1
            if (opcode == "jsr" and target == 0xFFD2 and
                    "shift" in row["names"]):
                audited_pre_main_chrout += 1
                continue
            reason = _owned_edge_violation(
                opcode, source_node, target, instruction_owners,
                set(function_entries), owned_tail_continuations)
            if reason is not None:
                violations.append({
                    "source_section": source_node[0],
                    "source_function_address": f"0x{source_node[1]:04x}",
                    "opcode": opcode,
                    "target": f"0x{target:04x}",
                    "reason": reason,
                    "instruction": line.strip(),
                })
            elif ((source_node, target) in owned_tail_continuations):
                observed_owned_tail_continuations.append({
                    "source_section": source_node[0],
                    "source_function_address": f"0x{source_node[1]:04x}",
                    "opcode": opcode,
                    "target": f"0x{target:04x}",
                    "target_symbol": "c2_kernal_irq_return",
                })
            elif (opcode == "jmp" and
                  instruction_owners.get(target) == source_node and
                  target not in function_entries):
                internal_basic_block_jumps += 1
            else:
                entry_edges += 1
    if audited_pre_main_chrout != 1:
        violations.append({
            "reason": "audited-pre-main-chrout-count",
            "actual": audited_pre_main_chrout,
            "expected": 1,
        })
    if (owned_tail_continuations
            and len(observed_owned_tail_continuations) != 1):
        violations.append({
            "reason": "retired-window-owned-tail-count",
            "actual": len(observed_owned_tail_continuations),
            "expected": 1,
        })
    if violations:
        raise RuntimeError(f"KERNAL freedom red: qualified edge violations {violations}")

    return {
        "model": "section-qualified-function-and-instruction-boundary-v1",
        "executable_sections": sorted(executable_sections),
        "owned_function_entries": dict(sorted(function_entries.items())),
        "ignored_absolute_or_weak_alias_count": len(set(ignored_aliases)),
        "direct_window_edges": direct_window_edges,
        "entry_edges": entry_edges,
        "same_function_basic_block_jumps": internal_basic_block_jumps,
        "audited_pre_main_chrout_edges": audited_pre_main_chrout,
        "owned_tail_continuation_edges": observed_owned_tail_continuations,
        "violations": [],
        "matrix": _owned_control_flow_model_selftest(),
    }


def kernal_freedom_gate(out: Path, final: Path) -> dict[str, object]:
    elf = Path(str(final) + ".elf")
    truth = ElfTruth.read(elf, llvm_readobj=TOOLCHAIN / "llvm-readobj")
    sections = section_table(elf)
    missing = [name for name in KERNAL_SECTIONS if name not in sections]
    if missing:
        raise RuntimeError(f"KERNAL freedom red: missing owned sections {missing}")
    live_window = {
        name: row for name, row in sections.items()
        if KERNAL_WINDOW_BASE <= row["address"] < KERNAL_WINDOW_BASE + KERNAL_WINDOW_BYTES
        and row["bytes"]
    }
    unknown = sorted(set(live_window) - set(KERNAL_SECTIONS))
    if unknown:
        raise RuntimeError(f"KERNAL freedom red: unnamed window occupants {unknown}")

    objdump = run([str(TOOLCHAIN / "llvm-objdump"), "-d", str(elf)], capture=True).lower()
    undefined = {
        symbol.name for symbol in truth.symbols
        if symbol.section == "Undefined"
    }
    if undefined & {
            "cbm_k_getin", "cbm_k_chrout", "cbm_k_open", "cbm_k_load"}:
        raise RuntimeError("KERNAL freedom red: CBM-I/O member remains unresolved")
    if re.search(r"\b(?:jsr|jmp)\s+\$ffe4\b", objdump):
        raise RuntimeError("KERNAL freedom red: post-startup GETIN edge")
    if re.search(r"\b(?:lda|ldx|ldy|sta|stx|sty|inc|dec|bit)\s+\$91\b", objdump):
        raise RuntimeError("KERNAL freedom red: retired STKEY operand")
    chrout_edges = len(re.findall(r"\bjsr\s+\$ffd2\b", objdump))
    if chrout_edges != 1:
        raise RuntimeError(
            f"KERNAL freedom red: expected one audited pre-main CHROUT, found {chrout_edges}")

    window_dis = run([
        str(TOOLCHAIN / "llvm-objdump"), "-d",
        "--section=.lisp65_c2_kernal_window.typed_queue_driver", str(elf)
    ], capture=True).lower()
    if window_dis.count("$d60a") != 1 or window_dis.count("$d619") != 2:
        raise RuntimeError("KERNAL freedom red: typed queue is not one-head/one-dequeue")

    control_flow = _owned_control_flow_gate(
        elf, sections, objdump, truth)

    category_sections = {
        "typed_queue_driver": [
            ".lisp65_c2_kernal_window.typed_queue_driver"],
        "irq_handler": [".lisp65_c2_kernal_window.irq_handler"],
        "nmi_and_freezer_return": [".lisp65_c2_kernal_window.nmi_and_freezer_return"],
        "frame_source": [],
        "map_switch_and_guards": [
            ".lisp65_c2_kernal_window.map_switch_and_guards",
            ".lisp65_c2_kernal_handoff", ".lisp65_c2_kernal_io_reveal",
            ".lisp65_c2_kernal_map_switch"],
        "post_startup_output_seam": [
            ".lisp65_c2_kernal_window.post_startup_output_seam"],
        "alignment_and_vectors": [
            ".lisp65_c2_kernal_window.state", ".lisp65_c2_vectors"],
    }
    categories = {
        name: sum(sections.get(section, {}).get("bytes", 0) for section in names)
        for name, names in category_sections.items()
    }
    replacement = sum(categories.values())
    relocated = sum(
        sections[name]["bytes"] for name in (
            ".lisp65_c2_kernal_window.c2_resident",
            ".lisp65_c2_kernal_window.session_emitter_state",
        ))
    if relocated < 3639:
        raise RuntimeError(
            f"KERNAL freedom red: relocated C2 residents {relocated} < deficit 3639")
    contract_future = KERNAL_WINDOW_BYTES - 3639 - replacement
    actual_live = sum(row["bytes"] for row in live_window.values())
    actual_future = KERNAL_WINDOW_BYTES - actual_live
    reopening_debit = e000_reopening_debit(sections) if E000_REOPENING else 0
    if E000_REOPENING and reopening_debit > E000_REOPEN_DEBIT_CAP:
        raise RuntimeError(
            f"KERNAL freedom red: formal reopening debit {reopening_debit} "
            f"> owner cap {E000_REOPEN_DEBIT_CAP}")
    ordinary_bss = sections.get(".bss")
    if not ordinary_bss:
        raise RuntimeError("KERNAL freedom red: ordinary Bank-0 BSS absent")
    ordinary_bss_end = ordinary_bss["address"] + ordinary_bss["bytes"]
    ordinary_bss_headroom = FIXED_BANK0_BASE - ordinary_bss_end
    if ordinary_bss_headroom < 0:
        raise RuntimeError(
            f"KERNAL freedom red: ordinary Bank-0 headroom "
            f"{ordinary_bss_headroom}")
    if contract_future <= 0 or actual_future <= 0:
        raise RuntimeError(
            f"KERNAL freedom red: future margins contract={contract_future} actual={actual_future}")
    if BSS_TRIAGE and actual_future < E000_FINAL_FLOOR_BYTES:
        raise RuntimeError(
            f"KERNAL freedom red: final E000 floor {actual_future} "
            f"< {E000_FINAL_FLOOR_BYTES}")

    report = {
        "format": "lisp65-c2-kernal-freedom-link-v2",
        "status": "passed",
        "orphan_policy": {
            "mode": "warn-with-exact-single-lto-exception-and-total-inventory",
            "exact_non_alloc_allowlist": list(ORPHAN_ALLOWLIST),
            "error_callsites_required": True,
            "retained_relocation_symbol_partition_required": True,
            "lto_partition_exception": ".llvm_sympart from exact target LTO object",
            "final_section_inventory_pin": str(
                FINAL_SECTION_INVENTORY_PIN.relative_to(ROOT)),
            "all_other_orphans": "hard-error-by-wrapper",
        },
        "owned_sections": live_window,
        "control_flow_ownership": control_flow,
        "forbidden_edges": {"getin": 0, "stkey": 0,
                            "unowned_window_targets": 0,
                            "audited_pre_main_chrout": chrout_edges},
        "source_census": {"typed_input_paths": 1, "abort_sources": 1,
                          "frame_owners": 1},
        "capacity": {
            "gross_window_bytes": KERNAL_WINDOW_BYTES,
            "fixed_resident_deficit_bytes": 3639,
            "replacement_categories": categories,
            "replacement_resident_bytes": replacement,
            "contract_future_margin_bytes": contract_future,
            "relocated_c2_resident_bytes": relocated,
            "complete_profile_immutable_data_bytes": sections[
                PROFILE_RODATA_SECTION]["bytes"],
            "actual_live_window_bytes": actual_live,
            "actual_future_margin_bytes": actual_future,
            "formal_reopening": ({
                "status": "passed-final-floor-bound",
                "debit_cap_bytes": E000_REOPEN_DEBIT_CAP,
                "actual_total_debit_bytes": reopening_debit,
                "purpose_bound_sections": {
                    name: sections.get(name, {}).get("bytes", 0)
                    for name in e000_reopening_section_names()
                },
                "final_floor_bytes": E000_FINAL_FLOOR_BYTES,
                "actual_future_margin_bytes": actual_future,
                "headroom_above_final_floor_bytes": (
                    actual_future - E000_FINAL_FLOOR_BYTES),
                "third_opening": "forbidden",
                "future_resident_demand": "automatic-C2-lite",
            } if E000_REOPENING else {
                "status": "not-selected",
            }),
            "ordinary_bank0_bss": {
                "address": ordinary_bss["address"],
                "bytes": ordinary_bss["bytes"],
                "end_exclusive": ordinary_bss_end,
                "fixed_c2_start": FIXED_BANK0_BASE,
                "headroom_bytes": ordinary_bss_headroom,
                "growth_policy": "full-no-new-resident-growth-budget",
            },
            "growth_policy": ((
                "terminal-63-byte-floor-after-owner-authorized-CRC-retry-"
                "debit; no-third-opening; any successor resident-or-window-"
                "demand-selects-C2-lite-automatically"
            ) if E000_REOPENING else (
                "closed-to-new-tenants-after-the-complete-v2-profile-data-cut; "
                "remaining bytes are contingency reserve for existing occupants"
            )),
        },
        "window_artifact": {
            "path": str((out / "c2-product-kernal-window.bin").relative_to(ROOT)),
            "bytes": KERNAL_WINDOW_BYTES,
            "sha256": hashlib.sha256(
                (out / "c2-product-kernal-window.bin").read_bytes()).hexdigest(),
        },
    }
    write(out / "kernal-freedom-link.json",
          json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def substitution_balance(out: Path, final: Path,
                         kernal: dict[str, object]) -> dict[str, object]:
    boot = json.loads((out / "runtime-overlays-boot-final.json").read_text())
    session = json.loads((out / "runtime-overlays-session-final.json").read_text())
    artifacts = json.loads(
        PRODUCT_ARTIFACTS_MANIFEST.read_text(encoding="utf-8"))
    c2d = ROOT / artifacts["artifacts"]["initial_c2d"]["path"]
    shelf = ROOT / artifacts["artifacts"]["shelf"]["path"]
    sections = section_table(Path(str(final) + ".elf"))
    bank0 = sum(
        row["bytes"] for name, row in sections.items()
        if name in {".lisp65_c2_kernal_handoff", ".lisp65_c2_host_facade",
                    ".lisp65_c2_kernal_io_reveal",
                    ".lisp65_c2_kernal_map_switch", ".lisp65_c2_kernal_state",
                    ".lisp65_c2_fixed_bank0", ".lisp65_c2_fixed_bank0_code",
                    ".lisp65_c2_fixed_bank0_hot_bss",
                    ".lisp65_c2_fixed_zp"})
    report = {
        "format": "lisp65-c2-product-substitution-balance-v1",
        "status": "passed",
        "projection_vs_actual": {
            "retirements": {
                "l65m_materializer": {"projected_runtime_bank_bytes": 36744,
                                      "actual_legacy_closure_edges": 0},
                "l65m_runtime_slices": {"projected_count": 28,
                                        "actual_remaining_count": 0},
                "old_directory_arrays": {"projected_bank0_credit_bytes": 697,
                                         "actual_remaining_legacy_arrays": 0},
                "kernal_window": {"projected_cpu_window_bytes": 8192,
                                  "actual_owned_cpu_window_bytes": 8192},
            },
            "arrivals": {
                "c2_decoder_emitter_append_and_services": {
                    "boot_family_image_bytes": boot["storage"]["size"],
                    "session_family_image_bytes": session["storage"]["size"],
                    "boot_slices": len(boot["slices"]),
                    "session_slices": len(session["slices"]),
                },
                "c2d_mutable_plane": {"bytes": c2d.stat().st_size},
                "immutable_shelf": {"bytes": shelf.stat().st_size},
                "resident_facades_and_state": {
                    "bank0_and_fixed_zp_bytes": bank0,
                    "fixed_host_vector_bytes": host_facade_bytes(),
                    "fixed_bank0_state_bytes": FIXED_BANK0_BYTES,
                    "fixed_bank0_code_bytes": FIXED_BANK0_CODE_BYTES,
                    "fixed_bank0_headroom_bytes": fixed_bank0_headroom_bytes(),
                    "fixed_zero_page_state_bytes": FIXED_ZP_BYTES,
                    "non_lto_verifier_binding_bytes": VERIFIER_BINDING_BYTES,
                },
                "typed_queue_irq_nmi_and_window": kernal["capacity"],
            },
        },
        "currencies": {
            "runtime_overlay_bank": {
                "retired_l65m_bytes": 36744,
                "boot_image_bytes": boot["storage"]["size"],
                "session_image_bytes": session["storage"]["size"],
                "session_region1_bytes": (
                    session.get("overflow_storage", {}).get("used", 0)),
                "session_region1_capacity_bytes": (
                    session.get("overflow_storage", {}).get("capacity", 0)),
                "session_region1_headroom_bytes": (
                    session.get("overflow_storage", {}).get("capacity", 0)
                    - session.get("overflow_storage", {}).get("used", 0)),
                "c2d_append_scratch_floor_bytes": (
                    14544 if RUNTIME_OVERLAY_FORMAT_VERSION == 4 else None),
                "worst_case_dynamic_entry_credit_rows": (
                    -25 if RUNTIME_OVERLAY_FORMAT_VERSION == 4 else 0),
                "families_are_lifetime_exclusive": True,
            },
            "bank5_mutable_plane": {"c2d_bytes": c2d.stat().st_size,
                                    "capacity_bytes": 65536,
                                    "headroom_bytes": 65536 - c2d.stat().st_size},
            "attic_immutable": {"shelf_bytes": shelf.stat().st_size},
            "bank0": {"retired_directory_projection_bytes": 697,
                      "new_kernal_facade_and_state_bytes": bank0,
                      "fixed_host_vector_bytes": host_facade_bytes(),
                      "fixed_bank0_state_bytes": FIXED_BANK0_BYTES,
                      "fixed_bank0_code_bytes": FIXED_BANK0_CODE_BYTES,
                      "fixed_bank0_headroom_bytes": fixed_bank0_headroom_bytes(),
                      "fixed_zero_page_state_bytes": FIXED_ZP_BYTES},
            "publish_last_binding": {
                "retired_embedded_tuple_bytes": VERIFIER_BINDING_BYTES,
                "non_lto_table_bytes": VERIFIER_BINDING_BYTES,
                "net_resident_bytes": 0,
            },
            "cpu_e000_window": kernal["capacity"],
        },
    }
    write(out / "substitution-balance.json",
          json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def closure_gate(out: Path, final: Path) -> None:
    forbidden_sources = sorted(LEGACY_C | {"l65m_batch_repeat.s"})
    maps = (Path(str(final) + ".map").read_text(encoding="utf-8", errors="replace"))
    bad_sources = [name for name in forbidden_sources if name in maps]
    try:
        truth = ElfTruth.read(
            Path(str(final) + ".elf"),
            llvm_readobj=TOOLCHAIN / "llvm-readobj")
    except ElfTruthError as error:
        raise RuntimeError("cannot load closure ELF truth") from error
    forbidden_pattern = re.compile(
        r"^(?:l65m_|lcc_install_|vm_boot_fastpath_|l65s_|lisp65_c1_)\w+$")
    forbidden_symbols = [
        symbol.name for symbol in truth.symbols
        if symbol.section not in ("Undefined", "")
        and forbidden_pattern.match(symbol.name)
    ]
    payloads = [
        final, out / "runtime-overlays-final.bin",
        out / "runtime-overlays-boot-final.bin",
        out / "runtime-overlays-session-final.bin",
        INITIAL_C2D,
        PRODUCT_SHELF,
    ]
    region1 = out / "runtime-overlays-session-final-region1.bin"
    if RUNTIME_OVERLAY_FORMAT_VERSION == 4:
        payloads.append(region1)
    magic_hits = [str(path) for path in payloads if b"L65M" in path.read_bytes()]
    if bad_sources or forbidden_symbols or magic_hits:
        raise RuntimeError(
            f"one-truth closure red: sources={bad_sources} "
            f"symbols={sorted(set(forbidden_symbols))} magic={magic_hits}"
        )
    report = {
        "format": "lisp65-c2-one-truth-closure-v1",
        "legacy_sources_in_map": [],
        "legacy_symbols": [],
        "l65m_magic_payloads": [],
        "runtime_slice_count_unique": UNIQUE_SLICE_COUNT,
        "runtime_families": {
            "boot": len(BOOT_SLICE_SPECS) + len(BOOT_DATA_SPECS),
            "session": len(SESSION_SLICE_SPECS),
        },
        "status": "passed",
    }
    write(out / "one-truth-closure.json", json.dumps(report, indent=2, sort_keys=True) + "\n")


def finish_single_link(out: Path, final: Path, contract: Path) -> None:
    """Finish an already emitted sole product link without relinking it."""
    crc_codegen = CRC_CODEGEN.audit_elf(
        Path(str(final) + ".elf"), out=out / "c2-crc-codegen-gate.json")
    crc_asm_leaf = CRC_ASM_LEAF.audit_elf(
        Path(str(final) + ".elf"), out=out / "c2-crc-asm-leaf-gate.json")
    asm_leaf_abi = ASM_LEAF_ABI.audit_elf(
        Path(str(final) + ".elf"),
        out=out / "c2-asm-leaf-abi-dataflow-gate.json",
        require_bank3_chain=FAMILY_STAGE_BINDINGS)
    f011_window = F011_WINDOW.audit(F011_WINDOW.disassemble(
        TOOLCHAIN / "llvm-objdump", Path(str(final) + ".elf")))
    write(out / "c2-f011-mount-window-gate.json",
          json.dumps(f011_window, indent=2, sort_keys=True) + "\n")
    window_binding = publish_kernal_window_binding(out, final)
    handoff_z_abi_gate(out, final, "final")
    pre_ownership = pre_ownership_gate(out, final, "final")
    profile_data_reference_gate(out, final, "final", pre_ownership)
    fixed_facade_gate(out, final, "final")
    unbound_boot = overlay_pack_family(
        out, final, contract, "boot", "unbound")
    unbound_session = overlay_pack_family(
        out, final, contract, "session", "unbound")
    binding = patch_verifier_binding_table(
        out, final, unbound_boot[1], unbound_session[1])
    total_binding = total_publish_last_gate(
        out, final, window_binding, binding)
    final_boot = overlay_pack_family(out, final, contract, "boot", "final")
    final_session = overlay_pack_family(
        out, final, contract, "session", "final")
    family_identity = runtime_family_identity_gate(
        out, unbound_boot, unbound_session, final_boot, final_session)
    _boot_image, _boot_manifest = final_boot
    session_image, _session_manifest = final_session
    write(out / "runtime-overlays-final.bin", session_image.read_bytes())
    if RUNTIME_OVERLAY_FORMAT_VERSION == 4:
        region1 = out / "runtime-overlays-session-final-region1.bin"
        write(out / "runtime-overlays-final-region1.bin",
              region1.read_bytes())
    closure_gate(out, final)
    kernal = kernal_freedom_gate(out, final)
    balance = substitution_balance(out, final, kernal)
    write(out / "product-substitution-link.json", json.dumps({
        "format": "lisp65-c2-product-substitution-link-v2",
        "link_label": out.name,
        "status": "passed",
        "product": str(final.relative_to(ROOT)),
        "product_sha256": hashlib.sha256(final.read_bytes()).hexdigest(),
        "identity_gate": "passed",
        "identity_components": {
            "kernal_window_publish_last": window_binding["status"],
            "verifier_publish_last_32_bytes": binding["status"],
            "crc_assembler_leaf": crc_asm_leaf["status"],
            "assembler_leaf_abi_dataflow": asm_leaf_abi["status"],
            "total_post_link_mutable_product_bytes": total_binding[
                "declared_domain_bytes"],
            "total_publish_last_domain_gate": total_binding["status"],
            "all_runtime_family_records_and_payloads": family_identity["status"],
            "mutated_payload_negative": family_identity["mutated_payload_negative"],
        },
        "kernal_window_identity_source": {
            "mode": "single-product-link-then-publish-last",
            "window_sha256": window_binding["single_product_link_window"]["sha256"],
            "window_crc16": window_binding["single_product_link_window"]["crc16"],
            "binding_report": "kernal-window-publish-last.json",
        },
        "product_closure_link_count": 1,
        "resident_island_seed_link_count": 1,
        "capacity_gate": "passed",
        "crc_codegen_gate": crc_codegen["status"],
        "assembler_leaf_abi_gate": asm_leaf_abi["status"],
        "f011_mount_window_gate": f011_window["status"],
        "one_truth_gate": "passed",
        "direct_entry_encoding_gate": "passed-637-of-637-fixnum-values-zero",
        "kernal_freedom_gate": "passed",
        "fixed_host_facade_gate": "passed",
        "pre_ownership_gate": "passed",
        "handoff_z_abi_gate": "passed",
        "fixed_bank0_headroom_bytes": fixed_bank0_headroom_bytes(),
        "substitution_balance": "passed",
        "actual_e000_future_margin_bytes": kernal["capacity"]["actual_future_margin_bytes"],
        "ordinary_bank0_bss_headroom_bytes": kernal["capacity"][
            "ordinary_bank0_bss"]["headroom_bytes"],
        "runtime_family_headroom_bytes": {
            "boot": 65536 - balance["currencies"]["runtime_overlay_bank"]["boot_image_bytes"],
            "session": 65536 - balance["currencies"]["runtime_overlay_bank"]["session_image_bytes"],
        },
        "claim_limit": (
            "Real single-product-closure C2 substitution link and structural "
            "closure only; the prerequisite resident-island seed materializer "
            "is separately counted. No hardware acceptance or promotion claim."
        ),
    }, indent=2, sort_keys=True) + "\n")
    print("c2-product-substitution-link: PASS "
          f"prg={final} families=boot:{len(BOOT_SLICE_SPECS) + len(BOOT_DATA_SPECS)},"
          f"session:{len(SESSION_SLICE_SPECS)} "
          f"e000-margin={kernal['capacity']['actual_future_margin_bytes']}")


def whole_phase_facade_probe(out: Path) -> None:
    """One bounded capacity/control-flow probe; never a product candidate."""
    manifest_path = PRODUCT_ARTIFACTS_MANIFEST
    artifacts = json.loads(manifest_path.read_text(encoding="utf-8"))
    old_window_pin = kernal_window_identity_pin()
    out.mkdir(parents=True, exist_ok=True)
    old_window_source = verify_kernal_window_pin_source(out, old_window_pin)
    write_product_linker_sources(out)
    contract_lines = [
        "profile=" + PROFILE,
        "mode=link24-latency-whole-phase-facade-capacity-probe",
        "hardware_execution=prohibited-unpinned-window",
        "c2_artifacts_sha256="
        + hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "linker_sha256="
        + hashlib.sha256((out / "c2-substitution.ld").read_bytes()).hexdigest(),
        "slice_count_unique=" + str(UNIQUE_SLICE_COUNT),
        "boot_family_slice_count=" + str(len(BOOT_SLICE_SPECS) + len(BOOT_DATA_SPECS)),
        "session_family_slice_count=" + str(len(SESSION_SLICE_SPECS)),
        "baseline_kernal_window_identity_sha256=" + str(old_window_pin["sha256"]),
        "baseline_kernal_window_identity_crc16=" + str(old_window_pin["crc16"]),
        "product_closure_link_count=1",
    ]
    for path in source_list():
        item = Path(path)
        contract_lines.append(
            f"input_sha256={item.relative_to(ROOT)}:"
            f"{hashlib.sha256(item.read_bytes()).hexdigest()}")
    contract = out / "resolved-profile.txt"
    write(contract, "\n".join(contract_lines) + "\n")

    runtime_prepared_standard = out / "runtime-overlay.prepare-standard.h"
    runtime_prepared = out / "runtime-overlay.prepare.h"
    island_prepared = out / "resident-island.prepare.h"
    island_header = out / "resident-island.h"
    stage_header = out / "stage-config.h"
    error_header = out / "error-text-table.h"
    kernal_header_path = out / "c2-kernal-window.generated.h"

    # The probe intentionally compiles against the last accepted header while
    # measuring a new provisional window.  It can prove capacity and control
    # flow, but it cannot run on hardware or claim identity until a separately
    # authorized pin/link cycle publishes that new window.
    write(kernal_header_path, kernal_header_values(
        int(str(old_window_pin["crc16"]), 16), str(old_window_pin["sha256"])))
    tool("runtime_overlay_bank.py", "prepare", "--abi-contract", str(contract),
         "--header", str(runtime_prepared_standard), "--profile", PROFILE,
         "--format-version", str(RUNTIME_OVERLAY_FORMAT_VERSION))
    render_prepared_family_header(runtime_prepared_standard, runtime_prepared)
    tool("resident_island.py", "prepare", "--abi-contract", str(contract),
         "--header", str(island_prepared))
    build_id = int(hashlib.sha256(contract.read_bytes()).hexdigest()[:8], 16)
    tool("error_text_table.py", "prepare",
         "--spec", str(ROOT / "config/error-texts.json"),
         "--profile", "workbench", "--build-id", hex(build_id),
         "--header", str(error_header),
         "--binary", str(out / "error-text-table.bin"))
    write(stage_header, "\n".join([
        "#ifndef LISP65_WORKBENCH_OVERLAY_STAGE_H",
        "#define LISP65_WORKBENCH_OVERLAY_STAGE_H",
        "#define LISP65_BOOT_OVERLAY_STAGE_BANK 0x05u",
        "#define LISP65_BOOT_OVERLAY_STAGE_OFF 0x8500u",
        f"#define LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID 0x{build_id:08x}UL",
        "#endif", "",
    ]))
    common = [stage_header, runtime_prepared, island_prepared, error_header]
    seed = compile_link(out, "resident-island-seed.prg", common, artifacts)
    tool("resident_island.py", "materialize", "--elf", str(seed) + ".elf",
         "--nm", str(TOOLCHAIN / "llvm-nm"),
         "--objcopy", str(TOOLCHAIN / "llvm-objcopy"),
         "--abi-contract", str(contract), "--header", str(island_header))
    final = compile_link(
        out, "whole-phase-facade-probe.prg",
        [stage_header, runtime_prepared, island_header,
         error_header, kernal_header_path], artifacts)

    provisional_window = extract_provisional_kernal_window(out, final)
    handoff_z_abi_gate(out, final, "probe")
    pre_ownership = pre_ownership_gate(out, final, "probe")
    profile_data_reference_gate(out, final, "probe", pre_ownership)
    fixed_facade_gate(out, final, "probe")
    unbound_boot = overlay_pack_family(
        out, final, contract, "boot", "unbound")
    unbound_session = overlay_pack_family(
        out, final, contract, "session", "unbound")
    binding = patch_verifier_binding_table(
        out, final, unbound_boot[1], unbound_session[1])
    final_boot = overlay_pack_family(out, final, contract, "boot", "final")
    final_session = overlay_pack_family(
        out, final, contract, "session", "final")
    family_identity = runtime_family_identity_gate(
        out, unbound_boot, unbound_session, final_boot, final_session)
    write(out / "runtime-overlays-final.bin", final_session[0].read_bytes())
    closure_gate(out, final)
    kernal = kernal_freedom_gate(out, final)
    balance = substitution_balance(out, final, kernal)

    sections = section_table(Path(str(final) + ".elf"))
    phases = {
        name: sections[f".lisp65_rt_c2d_{name}"]["bytes"]
        for name, _entry in C2_DECODER_SLICES
    }
    largest_name = max(phases, key=phases.get)
    smallest_headroom = 1792 - phases[largest_name]
    baseline_path = (ROOT / "build/c2.2/substitution/"
                     "product-link-24-ownership-io-safe-map/"
                     "kernal-freedom-link.json")
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline_window = baseline["capacity"]
    new_window = kernal["capacity"]
    baseline_transports = 21068
    whole_phase_boot_transports = 14
    baseline_seconds = 12 * 60
    projected_transport_seconds = (
        baseline_seconds * whole_phase_boot_transports / baseline_transports)

    report = {
        "format": "lisp65-c2-link24-whole-phase-facade-capacity-probe-v1",
        "recorded_on": "2026-07-20",
        "status": "passed-capacity-and-structural-probe-only",
        "scope": {
            "trigger": "Link 24 eventually reached phase 13 and the REPL but cold boot took about twelve minutes",
            "product_links": 1,
            "resident_island_seed_links": 1,
            "hardware_execution": "prohibited",
            "promotion": "not-authorized",
            "link25": "not-created",
        },
        "identities": {
            "probe_prg": str(final.relative_to(ROOT)),
            "probe_prg_sha256": hashlib.sha256(final.read_bytes()).hexdigest(),
            "probe_elf_sha256": hashlib.sha256(
                Path(str(final) + ".elf").read_bytes()).hexdigest(),
            "baseline_window_pin": old_window_pin,
            "baseline_window_pin_source": old_window_source,
            "provisional_window": provisional_window,
            "identity_claim": "none; a fresh pin/link authorization is required",
        },
        "decoder_transport": {
            "before": {
                "slices": 25,
                "minimum_boot_transports": baseline_transports,
                "cursor_work_state": "resident ordinary Bank-0 BSS",
            },
            "after": {
                "slices": len(C2_DECODER_SLICES),
                "boot_transports": whole_phase_boot_transports,
                "cursor_work_state": "retired",
                "logical_phases": [name for name, _entry in C2_DECODER_SLICES],
            },
            "validation_semantics": "unchanged catalog, record and payload verification once per transported logical phase",
        },
        "slice_capacity": {
            "cap_bytes": 1792,
            "phase_bytes": phases,
            "largest_phase": largest_name,
            "largest_phase_bytes": phases[largest_name],
            "smallest_headroom_bytes": smallest_headroom,
            "all_phases_fit": all(value <= 1792 for value in phases.values()),
        },
        "kernal_window_capacity": {
            "baseline_live_bytes": baseline_window["actual_live_window_bytes"],
            "baseline_future_margin_bytes": baseline_window["actual_future_margin_bytes"],
            "probe_live_bytes": new_window["actual_live_window_bytes"],
            "probe_future_margin_bytes": new_window["actual_future_margin_bytes"],
            "helper_facade_delta_bytes": (
                new_window["actual_live_window_bytes"]
                - baseline_window["actual_live_window_bytes"]),
            "control_flow_gate": "passed",
        },
        "runtime_overlay_bank": {
            "boot_image_bytes": balance["currencies"]["runtime_overlay_bank"]["boot_image_bytes"],
            "boot_headroom_bytes": 65536 - balance["currencies"]["runtime_overlay_bank"]["boot_image_bytes"],
            "session_image_bytes": balance["currencies"]["runtime_overlay_bank"]["session_image_bytes"],
            "session_headroom_bytes": 65536 - balance["currencies"]["runtime_overlay_bank"]["session_image_bytes"],
        },
        "fresh_gates": {
            "slice_caps": "passed",
            "fixed_facade": "passed",
            "pre_ownership": "passed",
            "handoff_z_and_io": "passed",
            "owned_window_control_flow": "passed",
            "one_truth_closure": "passed",
            "kernal_freedom": "passed",
            "runtime_family_total_identity": family_identity["status"],
            "mutated_payload_negative": family_identity["mutated_payload_negative"],
            "publish_last_verifier_binding": binding["status"],
        },
        "boot_time_projection": {
            "model": "linear redundant-transport component only",
            "link24_observed_seconds_approx": baseline_seconds,
            "link24_minimum_transport_count": baseline_transports,
            "probe_transport_count": whole_phase_boot_transports,
            "projected_redundant_transport_component_seconds": round(
                projected_transport_seconds, 3),
            "falsifiable_expectation": "cold C2 decode should move from minutes to the seconds class; the next receipt-less hardware pre-smoke measures the real total",
            "performance_claim": "not-run-not-passed",
        },
        "claim_limit": "One owner-authorized non-product capacity and structural probe. The provisional window is deliberately unpinned and must not be deployed. No Link 25, hardware acceptance, promotion or release claim.",
    }
    receipt = (ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
               "c2.2-link24-whole-phase-facade-capacity-probe-receipt.json")
    write(receipt, json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("c2-whole-phase-facade-probe: PASS "
          f"largest={largest_name}:{phases[largest_name]}/1792 "
          f"e000-margin={new_window['actual_future_margin_bytes']} "
          f"transports={baseline_transports}->{whole_phase_boot_transports}")


def coarse_split_capacity_probe(out: Path) -> None:
    """Measure 02a/02b/06a/06b in the product-shaped seed link only."""
    manifest_path = PRODUCT_ARTIFACTS_MANIFEST
    artifacts = json.loads(manifest_path.read_text(encoding="utf-8"))
    out.mkdir(parents=True, exist_ok=True)
    write_product_linker_sources(out)
    contract_lines = [
        "profile=" + PROFILE,
        "mode=link24-phase-02-06-coarse-split-capacity-probe",
        "hardware_execution=prohibited-non-product-seed",
        "c2_artifacts_sha256="
        + hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "linker_sha256="
        + hashlib.sha256((out / "c2-substitution.ld").read_bytes()).hexdigest(),
        "slice_count_unique=" + str(UNIQUE_SLICE_COUNT),
        "boot_family_slice_count=" + str(len(BOOT_SLICE_SPECS) + len(BOOT_DATA_SPECS)),
        "session_family_slice_count=" + str(len(SESSION_SLICE_SPECS)),
        "product_closure_link_count=0",
        "resident_island_seed_link_count=1",
    ]
    for path in source_list():
        item = Path(path)
        contract_lines.append(
            f"input_sha256={item.relative_to(ROOT)}:"
            f"{hashlib.sha256(item.read_bytes()).hexdigest()}")
    contract = out / "resolved-profile.txt"
    write(contract, "\n".join(contract_lines) + "\n")

    runtime_prepared_standard = out / "runtime-overlay.prepare-standard.h"
    runtime_prepared = out / "runtime-overlay.prepare.h"
    island_prepared = out / "resident-island.prepare.h"
    stage_header = out / "stage-config.h"
    error_header = out / "error-text-table.h"
    kernal_header_path = out / "c2-kernal-window.generated.h"
    old_window_pin = kernal_window_identity_pin()
    write(kernal_header_path, kernal_header_values(
        int(str(old_window_pin["crc16"]), 16), str(old_window_pin["sha256"])))
    tool("runtime_overlay_bank.py", "prepare", "--abi-contract", str(contract),
         "--header", str(runtime_prepared_standard), "--profile", PROFILE,
         "--format-version", str(RUNTIME_OVERLAY_FORMAT_VERSION))
    render_prepared_family_header(runtime_prepared_standard, runtime_prepared)
    tool("resident_island.py", "prepare", "--abi-contract", str(contract),
         "--header", str(island_prepared))
    build_id = int(hashlib.sha256(contract.read_bytes()).hexdigest()[:8], 16)
    tool("error_text_table.py", "prepare",
         "--spec", str(ROOT / "config/error-texts.json"),
         "--profile", "workbench", "--build-id", hex(build_id),
         "--header", str(error_header),
         "--binary", str(out / "error-text-table.bin"))
    write(stage_header, "\n".join([
        "#ifndef LISP65_WORKBENCH_OVERLAY_STAGE_H",
        "#define LISP65_WORKBENCH_OVERLAY_STAGE_H",
        "#define LISP65_BOOT_OVERLAY_STAGE_BANK 0x05u",
        "#define LISP65_BOOT_OVERLAY_STAGE_OFF 0x8500u",
        f"#define LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID 0x{build_id:08x}UL",
        "#endif", "",
    ]))
    seed = compile_link(
        out, "coarse-split-capacity-seed.prg",
        [stage_header, runtime_prepared, island_prepared, error_header], artifacts)
    sections = section_table(Path(str(seed) + ".elf"))
    phases = {
        name: sections[f".lisp65_rt_c2d_{name}"]["bytes"]
        for name, _entry in C2_DECODER_SLICES
    }
    split_names = ("02a", "02b", "06a", "06b")
    split_bytes = {name: phases[name] for name in split_names}
    all_fit = all(value <= 1792 for value in split_bytes.values())
    if not all_fit:
        raise RuntimeError(
            "coarse split capacity first-red: "
            + ", ".join(f"{name}={split_bytes[name]}" for name in split_names))
    phase13 = phases["13"]
    if phase13 > 1792:
        raise RuntimeError(f"phase 13 watch first-red: {phase13}/1792")

    report = {
        "format": "lisp65-c2-link24-phase-02-06-coarse-split-capacity-probe-v1",
        "recorded_on": "2026-07-20",
        "status": "passed-non-product-capacity-probe-only",
        "scope": {
            "resident_island_seed_links": 1,
            "product_closure_links": 0,
            "hardware_execution": "prohibited",
            "promotion": "not-authorized",
        },
        "identity": {
            "seed_prg": str(seed.relative_to(ROOT)),
            "seed_prg_sha256": hashlib.sha256(seed.read_bytes()).hexdigest(),
            "seed_elf_sha256": hashlib.sha256(
                Path(str(seed) + ".elf").read_bytes()).hexdigest(),
            "resolved_profile_sha256": hashlib.sha256(
                contract.read_bytes()).hexdigest(),
        },
        "semantic_cuts": {
            "02a": "all shelf-to-C2D image-record cross-bindings",
            "02b": "entry/resolution totals close, cursor reset, phase-3 publication",
            "06a": "normalized code structure and zero literal slots",
            "06b": "canonical export-name validation and phase-7 publication",
            "fail_closed_cutpoint_markers": {
                "02": "reserved 0x00 -> 0x2a -> 0x00",
                "06": "reserved 0x00 -> 0x6a -> 0x00",
                "skip_reorder_or_replay": "rejected",
            },
        },
        "slice_capacity": {
            "cap_bytes": 1792,
            "split_phase_bytes": split_bytes,
            "split_phase_headroom_bytes": {
                name: 1792 - value for name, value in split_bytes.items()
            },
            "all_four_split_phases_fit": True,
            "all_decoder_phase_bytes": phases,
            "phase_13_watch": {
                "bytes": phase13,
                "headroom_bytes": 1792 - phase13,
                "status": "narrowest-known-phase-watch",
            },
        },
        "transport_projection": {
            "link24_minimum_cursor_transports": 21068,
            "coarse_boot_decode_transports_excluding_phase13_materialization": 16,
            "performance_claim": "projected-only-not-run-not-passed",
        },
        "next_gate": (
            "A separately named regular product link with the complete identity, "
            "capacity, one-truth, KERNAL-freedom and structural gate set."
        ),
        "claim_limit": (
            "Owner-authorized product-shaped seed capacity probe only. It proves "
            "that the four new transported halves fit the unchanged 1792-byte "
            "cap; it is not a product link, identity pin, hardware acceptance, "
            "promotion or release claim."
        ),
    }
    receipt = (ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
               "c2.2-link24-phase-02-06-coarse-split-capacity-probe-receipt.json")
    write(receipt, json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("c2-coarse-split-capacity-probe: PASS "
          + " ".join(f"{name}={split_bytes[name]}/1792" for name in split_names)
          + f" phase13={phase13}/1792 product-links=0")


def v2_profile_data_placement_probe(out: Path) -> None:
    """Run the one authorized Link-28 immutable-data placement probe."""
    manifest_path = PRODUCT_ARTIFACTS_MANIFEST
    artifacts = json.loads(manifest_path.read_text(encoding="utf-8"))
    out.mkdir(parents=True, exist_ok=True)
    profile = write_v2_profile_report(out, artifacts)
    write_product_linker_sources(out)
    contract_lines = [
        "profile=" + PROFILE,
        "mode=link28-v2-profile-data-placement-probe",
        "hardware_execution=prohibited-non-product-seed",
        "c2_artifacts_sha256="
        + hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "linker_sha256="
        + hashlib.sha256((out / "c2-substitution.ld").read_bytes()).hexdigest(),
        "v2_profile_parity_sha256="
        + hashlib.sha256((out / "v2-product-profile-parity.json").read_bytes()).hexdigest(),
        "slice_count_unique=" + str(UNIQUE_SLICE_COUNT),
        "boot_family_slice_count=" + str(len(BOOT_SLICE_SPECS) + len(BOOT_DATA_SPECS)),
        "session_family_slice_count=" + str(len(SESSION_SLICE_SPECS)),
        "product_closure_link_count=0",
        "resident_island_seed_link_count=1",
    ]
    for path in source_list():
        item = Path(path)
        contract_lines.append(
            f"input_sha256={item.relative_to(ROOT)}:"
            f"{hashlib.sha256(item.read_bytes()).hexdigest()}")
    contract = out / "resolved-profile.txt"
    write(contract, "\n".join(contract_lines) + "\n")

    runtime_standard = out / "runtime-overlay.prepare-standard.h"
    runtime_prepared = out / "runtime-overlay.prepare.h"
    island_prepared = out / "resident-island.prepare.h"
    stage_header = out / "stage-config.h"
    error_header = out / "error-text-table.h"
    kernal_header = out / "c2-kernal-window.generated.h"
    old_window_pin = kernal_window_identity_pin()
    write(kernal_header, kernal_header_values(
        int(str(old_window_pin["crc16"]), 16), str(old_window_pin["sha256"])))
    tool("runtime_overlay_bank.py", "prepare", "--abi-contract", str(contract),
         "--header", str(runtime_standard), "--profile", PROFILE,
         "--format-version", str(RUNTIME_OVERLAY_FORMAT_VERSION))
    render_prepared_family_header(runtime_standard, runtime_prepared)
    tool("resident_island.py", "prepare", "--abi-contract", str(contract),
         "--header", str(island_prepared))
    build_id = int(hashlib.sha256(contract.read_bytes()).hexdigest()[:8], 16)
    tool("error_text_table.py", "prepare",
         "--spec", str(ROOT / "config/error-texts.json"),
         "--profile", "workbench", "--build-id", hex(build_id),
         "--header", str(error_header),
         "--binary", str(out / "error-text-table.bin"))
    write(stage_header, "\n".join([
        "#ifndef LISP65_WORKBENCH_OVERLAY_STAGE_H",
        "#define LISP65_WORKBENCH_OVERLAY_STAGE_H",
        "#define LISP65_BOOT_OVERLAY_STAGE_BANK 0x05u",
        "#define LISP65_BOOT_OVERLAY_STAGE_OFF 0x8500u",
        f"#define LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID 0x{build_id:08x}UL",
        "#endif", "",
    ]))
    seed = compile_link(
        out, "v2-profile-data-placement-seed.prg",
        [stage_header, runtime_prepared, island_prepared, error_header,
         kernal_header], artifacts)
    elf = Path(str(seed) + ".elf")
    sections = section_table(elf)
    baseline_elf = (ROOT / "build/c2.2/substitution/"
                    "product-link-27-vm-gc-e000/resident-island-seed.prg.elf")
    baseline_sections = section_table(baseline_elf)

    slice_names = sorted({
        spec.split(":")[2]
        for spec in BOOT_SLICE_SPECS + BOOT_DATA_SPECS + SESSION_SLICE_SPECS
    })
    slice_bytes = {
        name: sections.get(name, {}).get("bytes", 0) for name in slice_names
    }
    over_cap = {name: value for name, value in slice_bytes.items()
                if value <= 0 or value > 1792}
    text = sections.get(".text", {})
    text_end = text.get("address", 0) + text.get("bytes", 0)
    text_headroom = HANDOFF_BASE - text_end
    bss = sections.get(".bss", {})
    bss_end = bss.get("address", 0) + bss.get("bytes", 0)
    bss_headroom = FIXED_BANK0_BASE - bss_end
    e000_live = sum(sections.get(name, {}).get("bytes", 0)
                    for name in KERNAL_SECTIONS)
    e000_margin = KERNAL_WINDOW_BYTES - e000_live
    status = "passed-capacity-and-placement-probe-only"
    if over_cap or text_headroom < 0 or bss_headroom < 0 or e000_margin < 0:
        status = "first-red"

    changed_sections: dict[str, dict[str, int]] = {}
    for name in sorted(set(sections) | set(baseline_sections)):
        before = baseline_sections.get(name, {}).get("bytes", 0)
        after = sections.get(name, {}).get("bytes", 0)
        if before != after:
            changed_sections[name] = {
                "link27_bytes": before,
                "probe_bytes": after,
                "delta_bytes": after - before,
            }
    report: dict[str, object] = {
        "format": "lisp65-c2-link28-v2-profile-data-placement-probe-v1",
        "recorded_on": "2026-07-20",
        "status": status,
        "scope": {
            "authorized_capacity_placement_probes": 1,
            "actual_capacity_placement_probes": 1,
            "resident_island_seed_links": 1,
            "product_closure_links": 0,
            "hardware_execution": "prohibited",
            "promotion": "not-authorized",
        },
        "profile_parity": profile,
        "identity": {
            "seed_prg": str(seed.relative_to(ROOT)),
            "seed_prg_sha256": hashlib.sha256(seed.read_bytes()).hexdigest(),
            "seed_elf_sha256": hashlib.sha256(elf.read_bytes()).hexdigest(),
            "baseline_link27_seed_elf_sha256": hashlib.sha256(
                baseline_elf.read_bytes()).hexdigest(),
            "resolved_profile_sha256": hashlib.sha256(
                contract.read_bytes()).hexdigest(),
        },
        "capacity": {
            "bank0_text": {
                "address": text.get("address"),
                "bytes": text.get("bytes"),
                "end": text_end,
                "fixed_handoff": HANDOFF_BASE,
                "headroom_bytes": text_headroom,
            },
            "bank0_ordinary_bss": {
                "address": bss.get("address"),
                "bytes": bss.get("bytes"),
                "end": bss_end,
                "fixed_c2_start": FIXED_BANK0_BASE,
                "headroom_bytes": bss_headroom,
                "link27_failed_overlap_bytes": 323,
            },
            "cpu_e000_window": {
                "gross_bytes": KERNAL_WINDOW_BYTES,
                "live_bytes": e000_live,
                "future_margin_bytes": e000_margin,
                "link27_future_margin_bytes": 728,
                "margin_delta_bytes": e000_margin - 728,
                "growth_policy": "closed-to-new-tenants-after-this-cut",
            },
            "runtime_slices": {
                "cap_bytes": 1792,
                "section_bytes": slice_bytes,
                "over_cap_or_missing": over_cap,
            },
        },
        "link27_to_probe_section_deltas": changed_sections,
        "attribution": {
            "atomic_bundle": list(canonical_v2_product_defines()),
            "exact_link_delta_policy": (
                "The real LTO link provides exact per-section deltas. Per-define "
                "byte attribution is not claimed because the eight switches are "
                "interdependent and carrier-cut switches also remove code."
            ),
            "semantic_roles": {
                "LISP65_DIALECT_V2": "v2 code-object and VM semantics",
                "LISP65_V2_CARRIER_CUT": "forbid legacy carrier fallbacks",
                "LISP65_VM_NATIVE_APPLY": "native apply/funcall execution",
                "LISP65_V2_NATIVE_CAPABILITIES": "v2 native capability cases including peek/poke",
                "LISP65_V2_NATIVE_STRING_CODECS": "v2 string codec cases",
                "LISP65_V2_SERVICE_REGISTRY_CLOSED": "closed service registry contract",
                "LISP65_V2_WORKBENCH_SERVICES": "Workbench service CALLPRIM cases",
                "LISP65_V2_TREE_PRIMITIVE_VIEW": "tree primitive view bound to the same registry",
            },
        },
        "next_gate": (
            "Only a green result may proceed to the separately counted, already "
            "authorized maximum-one successor product link."
        ),
        "claim_limit": (
            "One owner-authorized product-shaped seed capacity/placement probe. "
            "It is not a product link, hardware acceptance, promotion or release claim."
        ),
    }
    report_path = out / "v2-profile-data-placement-probe.json"
    write(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
    if status != "passed-capacity-and-placement-probe-only":
        raise RuntimeError(
            "v2 profile data placement first-red: "
            f"slices={over_cap} text_headroom={text_headroom} "
            f"bss_headroom={bss_headroom} "
            f"e000_margin={e000_margin}")

    extract_provisional_kernal_window(out, seed)
    handoff_z_abi_gate(out, seed, "v2-profile-probe")
    pre_ownership = pre_ownership_gate(out, seed, "v2-profile-data-probe")
    data_references = profile_data_reference_gate(
        out, seed, "v2-profile-probe", pre_ownership)
    fixed_facade_gate(out, seed, "v2-profile-probe")
    boot = overlay_pack_family(out, seed, contract, "boot", "v2-profile-probe")
    session = overlay_pack_family(
        out, seed, contract, "session", "v2-profile-probe")
    kernal = kernal_freedom_gate(out, seed)
    report["capacity"]["runtime_overlay_bank"] = {
        "boot_image_bytes": boot[0].stat().st_size,
        "boot_headroom_bytes": 65536 - boot[0].stat().st_size,
        "session_image_bytes": session[0].stat().st_size,
        "session_headroom_bytes": 65536 - session[0].stat().st_size,
    }
    report["fresh_structural_gates"] = {
        "handoff_z_and_io": "passed",
        "pre_ownership": "passed",
        "profile_data_references": "passed",
        "profile_data_relocation_count": data_references[
            "matched_relocation_count"],
        "fixed_facade": "passed",
        "kernal_freedom": "passed",
        "owned_control_flow_edges": kernal["control_flow_ownership"][
            "direct_window_edges"],
    }
    write(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("c2-v2-profile-data-placement-probe: PASS "
          f"text-headroom={text_headroom} bss-headroom={bss_headroom} "
          f"e000-margin={e000_margin} "
          f"largest-slice={max(slice_bytes.values())}/1792 product-links=0")


def replay_v2_profile_data_placement(out: Path) -> None:
    """Replay corrected gates over the immutable wrapper-probe ELF."""
    if out.exists():
        raise RuntimeError(f"replay output already exists: {out}")
    out.mkdir(parents=True)
    source_root = PROFILE_DATA_WRAPPER_REPLAY_ROOT
    target = source_root / "v2-profile-data-placement-seed.prg"
    elf = Path(str(target) + ".elf")
    lto_object = Path(str(target) + ".lto.o")
    contract = source_root / "resolved-profile.txt"
    wrapper_report = source_root / (
        "exact-orphan-wrapper-v2-profile-data-placement-seed.prg.json")
    required = (target, elf, lto_object, contract, wrapper_report)
    if not all(path.is_file() for path in required):
        raise RuntimeError("immutable wrapper-probe replay source is incomplete")
    tree_sha = canonical_evidence_tree_sha256(source_root)
    elf_sha = hashlib.sha256(elf.read_bytes()).hexdigest()
    lto_sha = hashlib.sha256(lto_object.read_bytes()).hexdigest()
    if tree_sha != PROFILE_DATA_WRAPPER_REPLAY_TREE_SHA256:
        raise RuntimeError(f"wrapper-probe archive tree drift: {tree_sha}")
    if elf_sha != PROFILE_DATA_WRAPPER_REPLAY_ELF_SHA256:
        raise RuntimeError(f"wrapper-probe ELF drift: {elf_sha}")
    if lto_sha != PROFILE_DATA_WRAPPER_REPLAY_LTO_SHA256:
        raise RuntimeError(f"wrapper-probe LTO object drift: {lto_sha}")
    bad_modes = [
        str(path.relative_to(source_root))
        for path in source_root.rglob("*")
        if ((path.is_file() and path.stat().st_mode & 0o777 != 0o444)
            or (path.is_dir() and path.stat().st_mode & 0o777 != 0o555))
    ]
    if bad_modes:
        raise RuntimeError(f"wrapper-probe archive protection drift: {bad_modes}")
    wrapper = json.loads(wrapper_report.read_text(encoding="ascii"))
    if (wrapper.get("status") != "passed"
            or len(wrapper.get("observed_diagnostics", [])) != 1
            or wrapper.get("origin_object_sha256") != lto_sha):
        raise RuntimeError("saved exact-warning wrapper evidence is not green")

    inventory = final_section_inventory_gate(out, target)
    lto = lto_partition_metadata_gate(out, target)
    sections = section_table(elf)
    baseline_elf = (ROOT / "build/c2.2/substitution/"
                    "product-link-27-vm-gc-e000/resident-island-seed.prg.elf")
    baseline_sections = section_table(baseline_elf)
    slice_names = sorted({
        spec.split(":")[2]
        for spec in BOOT_SLICE_SPECS + BOOT_DATA_SPECS + SESSION_SLICE_SPECS
    })
    slice_bytes = {
        name: sections.get(name, {}).get("bytes", 0) for name in slice_names
    }
    over_cap = {name: value for name, value in slice_bytes.items()
                if value <= 0 or value > 1792}
    text = sections.get(".text", {})
    text_end = text.get("address", 0) + text.get("bytes", 0)
    text_headroom = HANDOFF_BASE - text_end
    bss = sections.get(".bss", {})
    bss_end = bss.get("address", 0) + bss.get("bytes", 0)
    bss_headroom = FIXED_BANK0_BASE - bss_end
    e000_live = sum(sections.get(name, {}).get("bytes", 0)
                    for name in KERNAL_SECTIONS)
    e000_margin = KERNAL_WINDOW_BYTES - e000_live
    if (over_cap or text_headroom < 0 or bss_headroom != 19
            or e000_margin != 386):
        raise RuntimeError(
            "immutable placement replay capacity red: "
            f"slices={over_cap} text={text_headroom} "
            f"bss={bss_headroom} e000={e000_margin}")

    changed_sections: dict[str, dict[str, int]] = {}
    for name in sorted(set(sections) | set(baseline_sections)):
        before = baseline_sections.get(name, {}).get("bytes", 0)
        after = sections.get(name, {}).get("bytes", 0)
        if before != after:
            changed_sections[name] = {
                "link27_bytes": before,
                "replay_source_bytes": after,
                "delta_bytes": after - before,
            }

    window = extract_provisional_kernal_window(out, target)
    handoff_z_abi_gate(out, target, "v2-profile-replay")
    pre_ownership = pre_ownership_gate(
        out, target, "v2-profile-data-replay")
    data_references = profile_data_reference_gate(
        out, target, "v2-profile-replay", pre_ownership)
    fixed_facade_gate(out, target, "v2-profile-replay")
    boot = overlay_pack_family(
        out, target, contract, "boot", "v2-profile-replay")
    session = overlay_pack_family(
        out, target, contract, "session", "v2-profile-replay")
    kernal = kernal_freedom_gate(out, target)

    report_files = sorted(path for path in out.iterdir() if path.is_file())
    report = {
        "format": "lisp65-c2-link28-v2-profile-data-placement-gate-replay-v1",
        "recorded_on": "2026-07-20",
        "status": "passed-existing-immutable-elf-no-new-link",
        "execution_accounting": {
            "compiler_invocations": 0,
            "linker_invocations": 0,
            "new_seed_links": 0,
            "new_product_links": 0,
            "gate_replays": 1,
        },
        "immutable_source": {
            "root": str(source_root.relative_to(ROOT)),
            "canonical_tree_sha256": tree_sha,
            "elf_sha256": elf_sha,
            "lto_object_sha256": lto_sha,
            "all_file_modes": "0444",
            "all_directory_modes": "0555",
            "exact_warning_wrapper_report_sha256": hashlib.sha256(
                wrapper_report.read_bytes()).hexdigest(),
        },
        "inventory": {
            "status": inventory["status"],
            "expected_and_actual_sections": len(
                inventory["actual_section_order"]),
            "missing": 0,
            "additional": 0,
            "order_semantics": inventory["order_semantics"],
            "actual_order_sha256": inventory[
                "actual_section_order_sha256"],
            "llvm_sympart": inventory["llvm_sympart"],
        },
        "lto_and_relocations": {
            "status": lto["status"],
            "retained_relocation_sections": lto["final_elf"][
                "retained_relocation_sections"],
        },
        "capacity": {
            "bank0_text_headroom_bytes": text_headroom,
            "bank0_ordinary_bss_headroom_bytes": bss_headroom,
            "e000_future_margin_bytes": e000_margin,
            "e000_growth_policy": "closed-to-new-tenants",
            "largest_runtime_slice_bytes": max(slice_bytes.values()),
            "runtime_slice_cap_bytes": 1792,
            "runtime_overlay_bank": {
                "boot_image_bytes": boot[0].stat().st_size,
                "boot_headroom_bytes": 65536 - boot[0].stat().st_size,
                "session_image_bytes": session[0].stat().st_size,
                "session_headroom_bytes": 65536 - session[0].stat().st_size,
            },
        },
        "link27_to_replay_source_section_deltas": changed_sections,
        "fresh_gate_results": {
            "final_section_inventory": "passed-membership-and-count",
            "lto_partition_metadata": "passed",
            "final_relocations": "passed-retained",
            "handoff_z_and_io": "passed",
            "pre_ownership": "passed",
            "profile_data_references": "passed",
            "profile_data_relocation_count": data_references[
                "matched_relocation_count"],
            "fixed_facade": "passed",
            "kernal_freedom": "passed",
            "owned_control_flow_edges": kernal[
                "control_flow_ownership"]["direct_window_edges"],
        },
        "provisional_window": window,
        "evidence_reports": {
            str(path.relative_to(out)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in report_files
        },
        "next_gate": (
            "The already-authorized maximum-one Link 28 may start only from "
            "a separately pinned provisional-window identity and remains "
            "subject to first-red discipline."),
        "claim_limit": (
            "Gate replay over one immutable product-shaped seed ELF. This is "
            "not a new build, product link, hardware acceptance, promotion or "
            "release claim."),
    }
    write(out / "v2-profile-data-placement-gate-replay.json",
          json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("c2-v2-profile-data-placement-replay: PASS "
          f"sections={len(inventory['actual_section_order'])} "
          f"relocs={lto['final_elf']['retained_relocation_sections']} "
          f"data-refs={data_references['matched_relocation_count']} "
          f"bss-headroom={bss_headroom} e000-margin={e000_margin} "
          "new-links=0")


def single_link(out: Path, *,
                probe_definitions: tuple[str, ...] = (),
                direct_entry_receipt: Path = DIRECT_ENTRY_CONTRACT_RECEIPT,
                direct_entry_check_tool: str = "c2_direct_entry_contract.py",
                extra_contract_lines: tuple[str, ...] = (),
                seed_only: bool = False) -> Path | None:
    probe_definitions = input_capture_compile_profile(probe_definitions)
    extra_contract_lines = tuple(
        ("feature_defines=" + ",".join(probe_definitions)
         if line.startswith("feature_defines=") else line)
        for line in extra_contract_lines)
    manifest_path = PRODUCT_ARTIFACTS_MANIFEST
    artifacts = json.loads(manifest_path.read_text(encoding="utf-8"))
    tool(direct_entry_check_tool, "check")
    if not direct_entry_receipt.is_file():
        raise RuntimeError(
            f"direct-entry contract receipt absent: {direct_entry_receipt}")
    direct_entry_identity = os.environ.get(
        "LISP65_DIRECT_ENTRY_IDENTITY_SHA256")
    if direct_entry_identity is None:
        direct_entry_identity = hashlib.sha256(
            direct_entry_receipt.read_bytes()).hexdigest()
    elif (os.environ.get("LISP65_PUBLIC_CLEAN_BUILD") != "1"
          or re.fullmatch(r"[0-9a-f]{64}", direct_entry_identity) is None):
        raise RuntimeError(
            "direct-entry identity override is valid only for a canonical "
            "public clean build and must be one lowercase SHA-256")
    out.mkdir(parents=True, exist_ok=True)
    write_v2_profile_report(out, artifacts)
    current_parity_identity = hashlib.sha256(
        (out / "v2-product-profile-parity.json").read_bytes()).hexdigest()
    if (SEALED_V2_PROFILE_PARITY_IDENTITY is not None
            and os.environ.get("LISP65_PUBLIC_CLEAN_BUILD") != "1"):
        raise RuntimeError(
            "sealed v2 profile-parity identity is valid only for the "
            "canonical public clean build")
    profile_parity_identity = (
        SEALED_V2_PROFILE_PARITY_IDENTITY or current_parity_identity)
    if (len(profile_parity_identity) != 64
            or any(character not in "0123456789abcdef"
                   for character in profile_parity_identity)):
        raise RuntimeError("sealed v2 profile-parity identity is invalid")
    write_product_linker_sources(out, probe_definitions)
    current_artifacts_identity = hashlib.sha256(
        manifest_path.read_bytes()).hexdigest()
    if (SEALED_C2_ARTIFACTS_IDENTITY is not None
            and os.environ.get("LISP65_PUBLIC_CLEAN_BUILD") != "1"):
        raise RuntimeError(
            "sealed C2-artifacts identity is valid only for the canonical "
            "public clean build")
    artifacts_identity = (
        SEALED_C2_ARTIFACTS_IDENTITY or current_artifacts_identity)
    if (len(artifacts_identity) != 64
            or any(character not in "0123456789abcdef"
                   for character in artifacts_identity)):
        raise RuntimeError("sealed C2-artifacts identity is invalid")
    contract_lines = [
        "profile=" + PROFILE,
        "lto_rng_seed=" + os.environ.get("LISP65_LTO_RNG_SEED", "unbound"),
        "lto_threads=" + os.environ.get("LISP65_LTO_THREADS", "unbound"),
        "deterministic_objects="
        + os.environ.get("LISP65_DETERMINISTIC_OBJECTS", "unbound"),
        "deterministic_compilation_dir="
        + ("." if os.environ.get("LISP65_DETERMINISTIC_OBJECTS") == "1"
           else "unbound"),
        "deterministic_link_paths="
        + ("relative" if os.environ.get("LISP65_DETERMINISTIC_OBJECTS") == "1"
           else "unbound"),
        "deterministic_llvm_link="
        + os.environ.get("LISP65_LLVM_LINK", "unbound"),
        "link_aslr_disabled="
        + os.environ.get("LISP65_DISABLE_LINK_ASLR", "unbound"),
        "c2_artifacts_sha256=" + artifacts_identity,
        "direct_entry_contract_sha256="
        + direct_entry_identity,
        "linker_sha256=" + hashlib.sha256((out / "c2-substitution.ld").read_bytes()).hexdigest(),
        "slice_count_unique=" + str(UNIQUE_SLICE_COUNT),
        "boot_family_slice_count=" + str(len(BOOT_SLICE_SPECS) + len(BOOT_DATA_SPECS)),
        "session_family_slice_count=" + str(len(SESSION_SLICE_SPECS)),
        "kernal_window_identity=post-link-publish-last",
        f"kernal_window_crc_binding_sentinel=0x{KERNAL_CRC_BINDING_SENTINEL:04x}",
        "v2_profile_parity_sha256="
        + profile_parity_identity,
        "product_closure_link_count=1",
        *extra_contract_lines,
    ]
    if os.environ.get("LISP65_DETERMINISTIC_OBJECTS") == "1":
        llvm_link = Path(
            os.environ.get("LISP65_LLVM_LINK", "/usr/bin/llvm-link"))
        if not llvm_link.is_file():
            raise RuntimeError(
                f"deterministic LLVM bitcode linker absent: {llvm_link}")
        contract_lines.append(
            "deterministic_llvm_link_sha256="
            + hashlib.sha256(llvm_link.read_bytes()).hexdigest())
    for path in source_list(probe_definitions):
        item = Path(path)
        contract_lines.append(f"input_sha256={item.relative_to(ROOT)}:{hashlib.sha256(item.read_bytes()).hexdigest()}")
    contract_lines.append(
        "input_sha256="
        f"{KERNAL_EQUATES_INCLUDE.relative_to(ROOT)}:"
        f"{hashlib.sha256(KERNAL_EQUATES_INCLUDE.read_bytes()).hexdigest()}")
    contract = out / "resolved-profile.txt"
    write(contract, "\n".join(contract_lines) + "\n")
    runtime_prepared_standard = out / "runtime-overlay.prepare-standard.h"
    runtime_prepared = out / "runtime-overlay.prepare.h"
    island_prepared = out / "resident-island.prepare.h"
    island_header = out / "resident-island.h"
    stage_header = out / "stage-config.h"
    error_header = out / "error-text-table.h"
    kernal_header_path = out / "c2-kernal-window.generated.h"
    # The sole product link creates the owned-window truth.  Its runtime CRC
    # operands and the host SHA header are published only after that link;
    # this sentinel is never an accepted product identity.  Runtime-family
    # tuples likewise remain assembler sentinels until publish-last.
    write(kernal_header_path, kernal_header_values(
        KERNAL_CRC_BINDING_SENTINEL, "0" * 64))
    tool("runtime_overlay_bank.py", "prepare", "--abi-contract", str(contract),
         "--header", str(runtime_prepared_standard), "--profile", PROFILE,
         "--format-version", str(RUNTIME_OVERLAY_FORMAT_VERSION))
    render_prepared_family_header(runtime_prepared_standard, runtime_prepared)
    tool("resident_island.py", "prepare", "--abi-contract", str(contract),
         "--header", str(island_prepared))
    build_id = int(hashlib.sha256(contract.read_bytes()).hexdigest()[:8], 16)
    tool("error_text_table.py", "prepare", "--spec", str(ROOT / "config/error-texts.json"),
         "--profile", "workbench", "--build-id", hex(build_id),
         "--header", str(error_header), "--binary", str(out / "error-text-table.bin"))
    write(stage_header, "\n".join([
        "#ifndef LISP65_WORKBENCH_OVERLAY_STAGE_H",
        "#define LISP65_WORKBENCH_OVERLAY_STAGE_H",
        "#define LISP65_BOOT_OVERLAY_STAGE_BANK 0x05u",
        "#define LISP65_BOOT_OVERLAY_STAGE_OFF 0x8500u",
        f"#define LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID 0x{build_id:08x}UL",
        "#endif", "",
    ]))
    common = [stage_header, runtime_prepared, island_prepared, error_header]
    seed = compile_link(out, "resident-island-seed.prg", common, artifacts,
                        probe_definitions=probe_definitions)
    environment_seed_only = (
        os.environ.get("LISP65_CANONICAL_SCOPE_SEED_ONLY") == "1")
    if seed_only or environment_seed_only:
        leaked = sorted(set(probe_definitions) & set(CONVERGENCE_DEFINES))
        if FULL_MAP_OWNERSHIP or leaked:
            raise RuntimeError(
                "canonical opt-out seed closure selected parked ownership: "
                f"full_map={FULL_MAP_OWNERSHIP} defines={leaked}")
        selected_sources = {
            Path(path).resolve() for path in source_list(probe_definitions)
        }
        leaked_sources = sorted(
            path.relative_to(ROOT).as_posix()
            for path in CONVERGENCE_SOURCES if path.resolve() in selected_sources)
        if leaked_sources or ownership_link_flags(probe_definitions):
            raise RuntimeError(
                "canonical opt-out seed closure retained parked ownership "
                f"sources/flags: sources={leaked_sources} "
                f"flags={ownership_link_flags(probe_definitions)}")
        linker = out / "c2-substitution.ld"
        linker_text = linker.read_text(encoding="utf-8")
        forbidden = (
            ".lisp65_c2_convergence_zp",
            ".lisp65_c2_convergence_state",
            ".lisp65_c2_static_stack",
            ".lisp65_c2_mapped_far_facade",
            ".lisp65_c2_mapped_far_service",
            "compiler static stack escaped its owned 12-byte arena",
            "runtime overlay floor drifted from its owner contract",
        )
        present = [token for token in forbidden if token in linker_text]
        if present:
            raise RuntimeError(
                "canonical opt-out seed linker retained ownership tokens: "
                f"{present}")
        derived_floor = (
            "__lisp65_workbench_overlay_min_start = "
            "ALIGN(__lisp65_workbench_noinit_end + 1, 2);")
        if linker_text.count(derived_floor) != 1:
            raise RuntimeError(
                "canonical opt-out seed lost its derived overlay floor")
        receipt_path_raw = os.environ.get(
            "LISP65_CANONICAL_SCOPE_SEED_RECEIPT")
        if environment_seed_only and receipt_path_raw is None:
            raise RuntimeError(
                "canonical seed-only environment lacks its receipt path")
        if receipt_path_raw is not None:
            receipt_path = Path(receipt_path_raw)
            if not receipt_path.is_absolute():
                receipt_path = ROOT / receipt_path
            artifacts_bound = {}
            for name, path in (
                    ("seed_prg", seed),
                    ("seed_elf", Path(str(seed) + ".elf")),
                    ("seed_map", Path(str(seed) + ".map")),
                    ("linker", linker),
                    ("profile", contract)):
                if not path.is_file():
                    raise RuntimeError(
                        f"canonical seed artifact absent: {path}")
                artifacts_bound[name] = {
                    "path": path.relative_to(ROOT).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            final = out / "lisp65-c2-substitution-linked.prg"
            report = {
                "format": "lisp65-c2-v112-canonical-opt-out-seed-v1",
                "recorded_on": "2026-08-07",
                "status": "passed-canonical-scope-seed-link-opt-out",
                "ownership_opt_in": False,
                "full_map_ownership": False,
                "parked_defines": leaked,
                "parked_sources": leaked_sources,
                "parked_link_flags": [],
                "derived_overlay_floor_instances": 1,
                "seed_links": 1,
                "product_links": 0,
                "product_completed": False,
                "final_product_absent": not final.exists(),
                "artifacts": artifacts_bound,
                "claim_limit": (
                    "Canonical opt-out seed-link closure only; no materialized "
                    "island, final product link, media, device, Link-92 card, "
                    "Halt or release claim."),
            }
            write(receipt_path,
                  json.dumps(report, indent=2, sort_keys=True) + "\n")
        if environment_seed_only:
            # SystemExit deliberately crosses the successor-driver stack: its
            # Exception handlers must not turn this successful pre-product
            # terminal condition into a card result or continue to a final
            # link.
            raise SystemExit(0)
        return seed
    tool("resident_island.py", "materialize", "--elf", str(seed) + ".elf",
         "--nm", str(TOOLCHAIN / "llvm-nm"), "--objcopy", str(TOOLCHAIN / "llvm-objcopy"),
         "--abi-contract", str(contract), "--header", str(island_header))
    final = compile_link(out, "lisp65-c2-substitution-linked.prg",
                         [stage_header, runtime_prepared, island_header,
                          error_header, kernal_header_path], artifacts,
                         probe_definitions=probe_definitions)
    finish_single_link(out, final, contract)
    return None


def resume_single_link(out: Path) -> None:
    """Resume only gates/packing after a tool-only first red; never relink."""
    final = out / "lisp65-c2-substitution-linked.prg"
    contract = out / "resolved-profile.txt"
    required = [final, Path(str(final) + ".elf"), Path(str(final) + ".map"),
                contract]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"existing-link resume inputs absent: {missing}")
    if (out / "lisp65-c2-substitution-unbound.prg").exists():
        raise RuntimeError(
            "existing-link resume refuses an already publish-last-patched product")
    if out.name != "product-link-28":
        raise RuntimeError("this bounded artifact-only resume is for product-link-28")
    expected = {
        final: "692729011bca541c82af4698f65d79396e16c47d18bda6479102b4758420442f",
        Path(str(final) + ".elf"): (
            "976c0a98356b430f4ec5a3dd56a23a12d2562d40dd9da6e4fb778ca1a43bc400"),
        contract: "59878262a1f0cfee742ab284b658a4f5cf6d0283e1ab8afe4301d33ce346ae30",
    }
    for path, digest in expected.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"Link-28 First-Red artifact drift: {path}")
    finish_single_link(out, final, contract)


def verify_link18_replay_inputs(out: Path) -> dict[str, object]:
    receipt_path = (ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                    "c2.2-product-substitution-link-18-first-red-receipt.json")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("status") != "first-red":
        raise RuntimeError("Link-18 replay source receipt is not first-red")
    for name, item in receipt["evidence"].items():
        for path_key, sha_key in (
                ("path", "sha256"),
                ("image_path", "image_sha256"),
                ("manifest_path", "manifest_sha256")):
            if path_key not in item:
                continue
            path = ROOT / item[path_key]
            actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
            if actual != item[sha_key]:
                raise RuntimeError(
                    f"Link-18 replay input drift {name}:{path_key}: {actual}")
    expected_out = ROOT / "build/c2.2/substitution/product-link-18"
    if out != expected_out:
        raise RuntimeError(f"Link-18 replay must use {expected_out}")
    for forbidden in (
            "kernal-freedom-link.json", "substitution-balance.json",
            "eighteenth-substitution-link.json", "link-18-gate-replay.json"):
        if (out / forbidden).exists():
            raise RuntimeError(f"Link-18 replay output already exists: {forbidden}")
    return {
        "receipt": str(receipt_path.relative_to(ROOT)),
        "receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
        "verified_evidence_entries": len(receipt["evidence"]),
        "status": "passed",
    }


def replay_link18(out: Path) -> None:
    replay_inputs = verify_link18_replay_inputs(out)
    final = out / "lisp65-c2-substitution-linked.prg"
    kernal = kernal_freedom_gate(out, final)
    balance = substitution_balance(out, final, kernal)
    report = {
        "format": "lisp65-c2-eighteenth-substitution-link-v1",
        "status": "passed",
        "product": str(final.relative_to(ROOT)),
        "product_sha256": hashlib.sha256(final.read_bytes()).hexdigest(),
        "replay": {
            "mode": "artifact-only-gate-replay",
            "new_product_links": 0,
            "inputs": replay_inputs,
        },
        "identity_gate": "passed",
        "capacity_gate": "passed",
        "one_truth_gate": "passed",
        "kernal_freedom_gate": "passed",
        "fixed_host_facade_gate": "passed",
        "pre_ownership_gate": "passed",
        "runtime_family_total_identity_gate": "passed",
        "mutated_payload_negative": "rejected",
        "control_flow_ownership": kernal["control_flow_ownership"],
        "fixed_bank0_headroom_bytes": fixed_bank0_headroom_bytes(),
        "substitution_balance": "passed",
        "actual_e000_future_margin_bytes": kernal["capacity"]["actual_future_margin_bytes"],
        "runtime_family_headroom_bytes": {
            "boot": 65536 - balance["currencies"]["runtime_overlay_bank"]["boot_image_bytes"],
            "session": 65536 - balance["currencies"]["runtime_overlay_bank"]["session_image_bytes"],
        },
        "claim_limit": (
            "SHA-bound artifact-only structural closure of Link 18. No new "
            "product link, hardware acceptance or promotion claim."
        ),
    }
    write(out / "eighteenth-substitution-link.json",
          json.dumps(report, indent=2, sort_keys=True) + "\n")
    write(out / "link-18-gate-replay.json", json.dumps({
        "format": "lisp65-c2-link-18-gate-replay-v1",
        "status": "passed",
        "new_product_links": 0,
        "source_receipt": replay_inputs,
        "kernal_freedom_report_sha256": hashlib.sha256(
            (out / "kernal-freedom-link.json").read_bytes()).hexdigest(),
        "substitution_balance_sha256": hashlib.sha256(
            (out / "substitution-balance.json").read_bytes()).hexdigest(),
        "final_structural_report_sha256": hashlib.sha256(
            (out / "eighteenth-substitution-link.json").read_bytes()).hexdigest(),
    }, indent=2, sort_keys=True) + "\n")
    print("c2-product-substitution-link: REPLAY PASS "
          f"prg={final} new-links=0 "
          f"e000-margin={kernal['capacity']['actual_future_margin_bytes']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--single-link", action="store_true")
    parser.add_argument("--whole-phase-facade-probe", action="store_true")
    parser.add_argument("--coarse-split-capacity-probe", action="store_true")
    parser.add_argument("--v2-profile-data-placement-probe", action="store_true")
    parser.add_argument("--replay-v2-profile-data-placement", action="store_true")
    parser.add_argument("--resume-existing", action="store_true")
    parser.add_argument("--replay-link-18", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        lma_reset_matrix = low_resident_lma_reset_mutation_selftest()
        assert len(lma_reset_matrix) == 7
        assert set(lma_reset_matrix.values()) == {"rejected"}
        profile_matrix = v2_profile_mutation_selftest()
        assert profile_matrix["missing_define_mutations_rejected"] == 8
        assert list(profile_matrix["overbroad_define_mutation"].values()) == ["rejected"]
        dummy_artifacts = {
            "product_build_id_hex": "0x00000000",
            "artifacts": {"shelf": {"bytes": 0}},
        }
        require_exact_v2_profile(definitions(dummy_artifacts))
        z_matrix = _handoff_z_abi_model_selftest()
        assert len(z_matrix) == 13
        assert z_matrix["valid-sei-ldz-zero-prefix"] == "passed"
        assert z_matrix["valid-mega65-io-knock"] == "passed"
        assert z_matrix["nonzero-z-normalization"] == "rejected"
        assert z_matrix["wrong-map-register-source"] == "rejected"
        assert z_matrix["c000-plus-e000-map-mask"] == "rejected"
        matrix = _pre_ownership_model_selftest()
        assert len(matrix) == 12
        assert matrix["same-vma-section-identity"] == "passed"
        assert matrix["prepare-before-ownership"] == "rejected"
        assert matrix["pre-handoff-edge-to-vm-logical-pc-helper"] == "rejected"
        assert matrix["pre-handoff-edge-to-c2-root-walker"] == "rejected"
        assert matrix["repl-before-ownership"] == "rejected"
        assert matrix["pre-handoff-operand-to-fixed-state"] == "rejected"
        control_matrix = _owned_control_flow_model_selftest()
        control_mutations = _owned_control_flow_matrix_contract_selftest(
            control_matrix)
        assert set(control_mutations.values()) == {"rejected"}
        data_matrix = _profile_data_reference_model_selftest()
        assert len(data_matrix) == 9
        assert data_matrix["output-section-plus-addend-reference"] == "passed"
        assert data_matrix["pre-handoff-function-reference"] == "rejected"
        assert data_matrix["unknown-source-function"] == "rejected"
        assert data_matrix["overlapping-function-provenance"] == "rejected"
        assert data_matrix["unsized-function-provenance"] == "rejected"
        assert data_matrix["missing-component-reference"] == "rejected"
        lto_matrix = _lto_partition_metadata_model_selftest()
        assert len(lto_matrix) == 6
        assert lto_matrix["valid-saved-input-retained-final-info"] == "passed"
        assert lto_matrix["missing-lto-sympart"] == "rejected"
        assert lto_matrix["alloc-lto-sympart"] == "rejected"
        assert lto_matrix["missing-final-sympart"] == "rejected"
        assert lto_matrix["allocated-final-sympart"] == "rejected"
        assert lto_matrix["missing-final-relocations"] == "rejected"
        orphan_matrix = _orphan_wrapper_model_selftest()
        assert len(orphan_matrix) == 5
        assert orphan_matrix["exact-single-diagnostic"] == "passed"
        assert orphan_matrix["zero-orphan-diagnostics"] == "rejected"
        assert orphan_matrix["two-orphan-diagnostics"] == "rejected"
        assert orphan_matrix["wrong-origin-object"] == "rejected"
        assert orphan_matrix["wrong-section"] == "rejected"
        inventory_matrix = _final_section_inventory_model_selftest()
        assert len(inventory_matrix) == 10
        assert inventory_matrix["exact-pinned-inventory"] == "passed"
        assert inventory_matrix["missing-section"] == "rejected"
        assert inventory_matrix["additional-section"] == "rejected"
        assert inventory_matrix["reordered-sections"] == "passed-provenance-only"
        assert inventory_matrix["allocated-sympart"] == "rejected"
        assert inventory_matrix["full-map-deleted-sections"] == (
            "rejected-7-of-7")
        assert inventory_matrix["full-map-moved-sections"] == (
            "rejected-7-of-7")
        assert inventory_matrix["full-map-unowned-stray"] == "rejected"
        assert len(_final_section_inventory_pin()) == 138
        publish_before = bytes(80)
        publish_domains = [
            {"name": "runtime-overlay-verifier-bindings",
             "file_offset": 8, "expected": bytes(range(32))},
            {"name": "kernal-window-crc-high",
             "file_offset": 48, "expected": b"\x12"},
            {"name": "kernal-window-crc-low",
             "file_offset": 52, "expected": b"\x34"},
        ]
        publish_after = bytearray(publish_before)
        for domain in publish_domains:
            offset = int(domain["file_offset"])
            expected = bytes(domain["expected"])
            publish_after[offset:offset + len(expected)] = expected
        assert not _publish_last_domain_errors(
            publish_before, bytes(publish_after), publish_domains)
        outside = bytearray(publish_after); outside[70] = 1
        assert "post-link-change-outside-declared-domain" in (
            _publish_last_domain_errors(
                publish_before, bytes(outside), publish_domains))
        corrupt = bytearray(publish_after); corrupt[48] ^= 1
        assert "binding-content-mismatch:kernal-window-crc-high" in (
            _publish_last_domain_errors(
                publish_before, bytes(corrupt), publish_domains))
        assert TOTAL_PUBLISH_LAST_BYTES == 34
        assert VERIFIER_BINDING_BASE == 0xB954
        assert KERNAL_CRC_BINDING_HIGH_ADDRESS == 0xB4F4
        assert KERNAL_CRC_BINDING_LOW_ADDRESS == 0xB4FA
        crc_call_matrix = _kernal_crc_call_binding_model_selftest()
        assert len(crc_call_matrix) == 4
        assert crc_call_matrix[
            "encoded-target-with-unrelated-display-label"] == "passed"
        assert crc_call_matrix[
            "display-name-with-wrong-encoded-target"] == "rejected"
        try:
            checked_public_projection(["literal_prep", "literal-prep"])
        except RuntimeError:
            pass
        else:
            raise AssertionError("slice-name projection collision was accepted")
        generated = linker_script()
        assert ".lisp65_rt_c2d_13" in generated
        assert ".lisp65_rt_c2d_13b" not in generated
        assert ".lisp65_rt_l65m_00" not in generated
        assert ".lisp65_c2_kernal_window.c2_resident" in generated
        assert ".lisp65_c2_kernal_window.frame_source" not in generated
        assert ".lisp65_c2_kernal_window.event_poll" not in generated
        assert f"{PROFILE_RODATA_SECTION} 0xfd12" in generated
        assert "SIZEOF(.lisp65_c2_kernal_window.profile_rodata) == 342" in generated
        assert PROFILE_RODATA_BYTES == 342
        assert ".lisp65_c2_host_facade 0xb5c4" in generated
        assert ".lisp65_c2_fixed_zp 0x89" in generated
        assert ".lisp65_c2_fixed_bank0 0xc080" in generated
        assert ".lisp65_c2_fixed_bank0_code 0xc218" in generated
        assert ".lisp65_runtime_overlay_verifier_bindings" in generated
        assert "SIZEOF(.lisp65_runtime_overlay_verifier_bindings) == 32" in generated
        assert ".lisp65_c2_kernal_handoff 0xb4a3" in generated
        assert ".lisp65_c2_kernal_handoff 0xb4a3 : AT(" not in generated
        assert ".lisp65_c2_kernal_io_reveal 0xb5eb" in generated
        assert ".lisp65_c2_kernal_map_switch 0xb5f6" in generated
        assert "SIZEOF(.lisp65_c2_kernal_window.session_emitter_code) == 0" in generated
        assert ".lisp65_c2_kernal_window.session_emitter_state" in generated
        assert len(HOST_FACADE_SYMBOLS) == 13
        assert len(set(HOST_FACADE_SYMBOLS)) == 13
        assert HOST_FACADE_BASE + len(HOST_FACADE_SYMBOLS) * HOST_FACADE_STRIDE == 0xb5eb
        layout_header = (ROOT / "src/c2_kernal_layout.h").read_text(encoding="utf-8")
        mem_header = (ROOT / "src/mem.h").read_text(encoding="utf-8")
        mem_source = (ROOT / "src/mem.c").read_text(encoding="utf-8")
        assert "#define LISP65_C2_ZP __zp" in layout_header
        assert "extern uint8_t LISP65_C2_ZP mem_oom" in mem_header
        assert 'LISP65_C2_FIXED_ZP("mem_oom") mem_oom' in mem_source
        repl_source = (ROOT / "src/repl.c").read_text(encoding="utf-8")
        assert 'LISP65_C2_FIXED_BANK0_CODE("kb_cursor_off")' in repl_source
        emitter_source = (ROOT / "src/c2_session_emitter.c").read_text(
            encoding="utf-8")
        assert 'LISP65_C2_FIXED_BANK0_CODE("c2e_cons")' in emitter_source
        binding_source = (ROOT / "src/runtime_overlay_verifier_bindings.s").read_text(
            encoding="utf-8")
        assert "rtov_boot_verifiers:" in binding_source
        assert "rtov_verifiers:" in binding_source
        assert "0xff80" in generated
        assert "AT(ORIGIN(c2_runtime_load))" in generated
        assert generated.count("(!rwx)") == 3
        assert generated.count("(INFO)") == len(ORPHAN_ALLOWLIST) + 1
        assert "KEEP(*(.lisp65_error_callsites))" in generated
        assert "SIZEOF(.lisp65_error_callsites) > 0" in generated
        assert ".llvm_sympart 0 (INFO)" in generated
        assert "KEEP(*(.llvm_sympart))" in generated
        assert "SIZEOF(.llvm_sympart) > 0" in generated
        assert "/DISCARD/ : { *(.llvm_sympart) }" not in generated
        assert generated.index("MEMORY {") < generated.index(
            "AT(ORIGIN(c2_runtime_load))")
        assert "INSERT AFTER .lisp65_resident_island_annex" in generated
        assert UNIQUE_SLICE_COUNT == 43
        assert len(BOOT_SLICE_SPECS) == 9
        assert len(BOOT_DATA_SPECS) == 1
        assert len(SESSION_SLICE_SPECS) == 36
        decoder_source = (ROOT / "scripts/c2-stream-decoder.c").read_text(
            encoding="utf-8")
        assert "c->reserved = 0x2au" in decoder_source
        assert "c->reserved != 0x2au" in decoder_source
        assert "c->reserved = LISP65_C2_PHASE_06A_COMPLETE" in decoder_source
        assert "c->reserved != LISP65_C2_PHASE_06A_COMPLETE" in decoder_source
        print("c2-product-substitution-link: SELFTEST PASS "
              "unique-slices=43 boot-records=10 session=36")
        return 0
    if sum((args.single_link, args.whole_phase_facade_probe,
            args.coarse_split_capacity_probe,
            args.v2_profile_data_placement_probe,
            args.replay_v2_profile_data_placement,
            args.resume_existing,
            args.replay_link_18)) != 1:
        parser.error("choose exactly one link, whole-phase facade probe, "
                     "existing-link resume or Link-18 replay mode")
    if args.single_link:
        single_link(args.out.resolve())
    elif args.whole_phase_facade_probe:
        whole_phase_facade_probe(args.out.resolve())
    elif args.coarse_split_capacity_probe:
        coarse_split_capacity_probe(args.out.resolve())
    elif args.v2_profile_data_placement_probe:
        v2_profile_data_placement_probe(args.out.resolve())
    elif args.replay_v2_profile_data_placement:
        replay_v2_profile_data_placement(args.out.resolve())
    elif args.resume_existing:
        resume_single_link(args.out.resolve())
    else:
        replay_link18(args.out.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
