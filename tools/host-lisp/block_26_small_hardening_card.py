#!/usr/bin/env python3
"""Prelink proof for Block 2.6 Card 6: small C hardening and provenance."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = ARCH / "block-2.6-card6-small-hardening-omission-prelink-receipt.json"
PLAN = ROOT / "docs/planning/2.6-correctness-and-build-integrity-work-plan.md"
AUTHORIZATION = "02479883"
PATCH_HEADERS = {
    "tools/xemu-patches/mega65-f011-io-buffer-select.patch": (
        "40dfef0d1d5f56be2469492715c12bdb32c75b67", "GPL-2.0-or-later"),
    "tools/xemu-patches/mega65-dwx-headless-input.patch": (
        "40dfef0d1d5f56be2469492715c12bdb32c75b67", "GPL-2.0-or-later"),
    "tools/xemu-patches/mega65-dwx-cycle-counter.patch": (
        "40dfef0d1d5f56be2469492715c12bdb32c75b67", "GPL-2.0-or-later"),
    "tools/xemu-patches/mega65-f011-buffered-read-eq.patch": (
        "40dfef0d1d5f56be2469492715c12bdb32c75b67", "GPL-2.0-or-later"),
    "patches/mega65-tools-keybuffer-drain.patch": (
        "c5bf0ccd7ec6398290176f8af928d0780482577f", "GPL-3.0-only"),
}
SOURCE_PATHS = (
    "src/mem.c", "src/io.c", "src/attic_library_shelf.c",
    "src/eval.c", "src/vm.c", "src/vm_embed.c",
    "src/c2_platform_dma.c", "src/c2_product_runtime.c",
    "src/c2_kernal_runtime.c", "src/c2_kernal_runtime.h",
    "src/c2_mapped_far_convergence.s",
    "src/optional/c2_mapped_far_convergence_full_span.s",
    "src/interrupt.c", "src/repl.c", "src/obj.h", "src/reader.c",
    "src/printer.c", "src/screen_scroll_overlay.c",
    "src/vm_runtime_overlay.c", "src/mega65_dma_descriptor.h",
    "src/key_event_object.h", "src/screen_string_span.h",
    ".gitignore", "THIRD-PARTY-NOTICES.md",
    "config/dwx-prefilter-blind-spot-contract.json",
    "docs/upstream-issue-drafts.md",
    "docs/planning/2.6-card6-small-hardening-omission-prelink-report.md",
    "tools/host-lisp/block_26_small_hardening_card.py",
    "tools/host-lisp/c2_mapped_far_asm_equivalence.py",
    *PATCH_HEADERS,
)


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def texts() -> dict[str, str]:
    return {name: (ROOT / name).read_text(encoding="utf-8")
            for name in SOURCE_PATHS}


def authority() -> dict[str, Any]:
    raw = subprocess.run(
        ["git", "show", f"{AUTHORIZATION}:{PLAN.relative_to(ROOT).as_posix()}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout.decode()
    require("Reviewer disposition — card 6 A13 descriptor red; repair round and last link" in raw,
            "Card 6 A13 repair authority absent")
    section = raw.split(
        "## Reviewer disposition — card 6 A13 descriptor red; repair round and last link", 1)[1]
    section = section.split("\n## ", 1)[0]
    for token in ("Tuple-faithful builder", "Executed descriptor value comparison",
                  "byte-2 `$20` mutation", "one replacement WPLTO"):
        require(token in section, f"Card 6 repair authority token absent: {token}")
    return {
        "commit": AUTHORIZATION,
        "plan": PLAN.relative_to(ROOT).as_posix(),
        "section_sha256": hashlib.sha256(section.encode()).hexdigest(),
        "right": "one A13 tuple-fidelity repair round; replacement-link authority separate",
    }


def validate(source: dict[str, str]) -> dict[str, Any]:
    mem = source["src/mem.c"]
    io = source["src/io.c"]
    shelf = source["src/attic_library_shelf.c"]
    vm = source["src/vm.c"]
    eval_c = source["src/eval.c"]
    reader = source["src/reader.c"]
    obj_h = source["src/obj.h"]
    printer = source["src/printer.c"]
    kernal_h = source["src/c2_kernal_runtime.h"]

    require("static uint8_t ext_dma_read_or_abort" in mem
            and "? ext_stg1 : 0xffu" in mem
            and mem.count("? (obj)ext_stg : NIL") == 2
            and "ext_disk_get(uint16_t off){ return ext_dma_read_or_abort" in mem
            and "? ext_stg1 : 0u; }" in mem
            and "? str_stg1 : 0u" in mem
            and "for (i = 0; i < len; i++) dst[i] = 0u" in mem,
            "failed extended reads can still expose stale staging bytes")
    require("unsigned char io_attic_load_lib_name_probe(const char *name)" in io
            and "unsigned char io_attic_load_lib(obj name)" in shelf,
            "attic loader probe still collides with the product ABI")

    descriptor_users = (
        "src/mem.c", "src/vm_embed.c", "src/c2_platform_dma.c",
        "src/c2_product_runtime.c", "src/c2_kernal_runtime.c", "src/io.c",
        "src/attic_library_shelf.c", "src/screen_scroll_overlay.c",
        "src/vm_runtime_overlay.c",
    )
    for path in descriptor_users:
        require('#include "mega65_dma_descriptor.h"' in source[path]
                and ("lisp65_f018_descriptor(" in source[path]
                     or "lisp65_edma_descriptor(" in source[path]
                     or "lisp65_edma_fill_descriptor(" in source[path]),
                f"DMA descriptor user bypasses the canonical seam: {path}")
    descriptor = source["src/mega65_dma_descriptor.h"]
    require(descriptor.count("always_inline") == 4,
            "descriptor seam must expose exactly four inline builders")
    require("job[11] = value" in descriptor
            and "job[19] = 0u" in descriptor
            and "job[2] = (uint8_t)(source_megabyte_bank >> 8);" in descriptor
            and "job[13] = (uint8_t)source_megabyte_bank;" in descriptor,
            "canonical descriptor builders lost the byte contract")
    rtov = source["src/vm_runtime_overlay.c"]
    require("lisp65_edma_tuple_descriptor(rtov_edma_job" in rtov
            and "((uint32_t)source_high << 16)" not in rtov,
            "runtime-overlay source tuple is recomposed as an ordinary address")

    require("lisp65_key_event_object(" in eval_c
            and "lisp65_key_event_object(" in vm
            and "lisp65_screen_write_string_span(" in eval_c
            and "lisp65_screen_write_string_span(" in vm,
            "tree and VM exact primitive semantics are not shared")

    raw_window = "\n".join(source[name] for name in (
        "src/c2_kernal_runtime.c", "src/c2_kernal_runtime.h",
        "src/c2_mapped_far_convergence.s",
        "src/optional/c2_mapped_far_convergence_full_span.s",
        "src/interrupt.c", "src/repl.c"))
    for literal in ("0xff83", "0xff84", "0xff87", "0xff88", "0xff8a", "0xff8d"):
        require(literal not in raw_window.lower(),
                f"KERNAL-window literal escaped the equates authority: {literal}")
    require("c2_kernal_window_equates.inc" in raw_window
            and raw_window.count(".extern C2K_FRAME_LO") == 2
            and raw_window.count(".extern C2K_FRAME_HI") == 2
            and "extern volatile uint8_t C2K_INPUT_RING_TAIL" in kernal_h,
            "KERNAL-window consumers are not bound to the equates authority")
    require("#ifdef LISP65_C2_KERNAL_UNMAP\n        C2K_INPUT_RING_TAIL" in
            source["src/repl.c"],
            "non-unmap REPL can still write the mapped ring-tail cell")

    require("_Static_assert(sizeof(obj) == 2u" in obj_h
            and "_Static_assert(offsetof(Cell, a) == 1u" in obj_h
            and "_Static_assert(sizeof(Cell) == 5u" in obj_h
            and "_Static_assert(offsetof(Cell, a) == 2u" in obj_h
            and "_Static_assert(sizeof(Cell) == 6u" in obj_h
            and "_Static_assert(sizeof(lisp65_buffer_overlay_context) <= VM_CODEBUF" in vm,
            "ABI reinterpretation is missing a compile-time layout assertion")
    require("switch (reader_error_code)" in reader
            and "code - READER_ERR_UNCLOSED_STRING" not in reader,
            "reader errors still depend on enum arithmetic")
    require("(int32_t)x + (int32_t)y" in vm
            and "(int32_t)x * (int32_t)y" in vm,
            "fixnum arithmetic still overflows signed int16 intermediates")
    require("if (s == NIL || s != str_building) return 0;" not in mem
            and "if (s == str_building) str_building = NIL;" not in mem
            and "obj str_close(obj s) { str_building = NIL; return s; }" in mem,
            "omitted A15 string-builder latch was silently restored")
    require("if (tpos < sizeof tsink_buf)" in printer,
            "Xemu test printer sink remains unbounded")

    ignore = source[".gitignore"].splitlines()
    require("*.elf" in ignore and "*.o" in ignore,
            "generated object/ELF extensions are not ignored")
    tracked = subprocess.run(
        ["git", "ls-files", "spike/**/*.elf", "spike/**/*.o"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, check=True).stdout.splitlines()
    # Index deletions count as tracked until commit; accept exactly the paths
    # staged for deletion and reject every live tracked spike binary.
    live_tracked = [name for name in tracked if (ROOT / name).exists()]
    require(not live_tracked,
            f"compiled spike binaries remain tracked and present: {live_tracked}")
    notices = source["THIRD-PARTY-NOTICES.md"]
    for token in ("## MEGA65 tools", "c5bf0ccd7ec6398290176f8af928d0780482577f",
                  "GPL version 3", "## Xemu", "GPL version 2",
                  "## cc65 spike", "zlib licence"):
        require(token in notices, f"third-party notice token absent: {token}")
    for path, (commit, license_id) in PATCH_HEADERS.items():
        patch = source[path]
        require(f"# Base-Commit: {commit}" in patch
                and f"# Upstream-License: {license_id}" in patch,
                f"patch provenance header absent: {path}")
    contract = json.loads(source["config/dwx-prefilter-blind-spot-contract.json"])
    live_patches = {row["path"]: row["sha256"]
                    for row in contract["qualified_tool_identity"]["patches"]}
    retired = {row["path"]: row for row in contract.get("retired_patch_evidence", [])}
    require(not (set(live_patches) & set(retired)), "patch is both active and retired")
    for path in PATCH_HEADERS:
        if path.startswith("tools/xemu-patches/"):
            if path in retired:
                from evidence_era import era_bind
                row=retired[path]
                require(row['authority_commit']=='566c2e23'
                        and era_bind(row['authority_commit'],path)['sha256']==row['sha256']==sha(ROOT/path),
                        "retired patch lost its sealed withdrawal authority")
                continue
            require(live_patches.get(path) == sha(ROOT / path),
                    f"active DWX identity did not consume patch header: {path}")

    return {
        "failed_read_contract": "status-returned; stale staging never consumed",
        "attic_loader_public_signatures": 1,
        "canonical_descriptor_users": len(descriptor_users),
        "shared_tree_vm_exact_semantics": ["key-event", "screen-write-string"],
        "kernal_window_numeric_duplicates": 0,
        "abi_static_assertions": 6,
        "spike_object_or_elf_files_present": 0,
        "provenance_patch_headers": len(PATCH_HEADERS),
    }


def mutations(clean: dict[str, str]) -> list[str]:
    trials: list[tuple[str, str, str, str]] = [
        ("failed-read-uses-stale-stage", "src/mem.c",
         "? ext_stg1 : 0u", "; return ext_stg1"),
        ("duplicate-attic-loader-signature", "src/io.c",
         "io_attic_load_lib_name_probe", "io_attic_load_lib"),
        ("descriptor-user-bypasses-seam", "src/mem.c",
         "lisp65_f018_descriptor(ext_dl", "legacy_descriptor(ext_dl"),
        ("encoded-source-tuple-recomposed", "src/vm_runtime_overlay.c",
         "lisp65_edma_tuple_descriptor(rtov_edma_job, 4u, source_low, source_high,",
         "lisp65_edma_descriptor(rtov_edma_job, 4u,\n"
         "        ((uint32_t)source_high << 16) | source_low,"),
        ("eval-key-event-duplicates-semantics", "src/eval.c",
         "lisp65_key_event_object(c", "duplicate_key_event(c"),
        ("vm-screen-span-duplicates-semantics", "src/vm.c",
         "lisp65_screen_write_string_span(x", "duplicate_screen_span(x"),
        ("raw-kernal-address-restored", "src/repl.c",
         "#define BUF_MAX REPL_BUF_MAX", "#define BUF_MAX REPL_BUF_MAX\n#define OLD (*(volatile unsigned char *)0xff8d)"),
        ("non-unmap-ring-write-restored", "src/repl.c",
         "#ifdef LISP65_C2_KERNAL_UNMAP\n        C2K_INPUT_RING_TAIL",
         "#if 1\n        C2K_INPUT_RING_TAIL"),
        ("cell-layout-assert-removed", "src/obj.h",
         "_Static_assert(sizeof(Cell) == 5u", "REMOVED_ASSERT(sizeof(Cell) == 5u"),
        ("reader-enum-arithmetic-restored", "src/reader.c",
         "switch (reader_error_code)", "code - READER_ERR_UNCLOSED_STRING"),
        ("omitted-string-latch-restored", "src/mem.c",
         "uint8_t str_putc(obj s, uint8_t c) {",
         "uint8_t str_putc(obj s, uint8_t c) {\n    if (s == NIL || s != str_building) return 0;"),
        ("xemu-sink-unbounded", "src/printer.c",
         "if (tpos < sizeof tsink_buf) TSINK[tpos++] = (uint8_t)c;",
         "TSINK[tpos++] = (uint8_t)c;"),
        ("xemu-patch-license-header-removed",
         "tools/xemu-patches/mega65-dwx-cycle-counter.patch",
         "# Upstream-License: GPL-2.0-or-later (LICENSE)", "# license removed"),
        ("object-ignore-removed", ".gitignore", "*.o", "*.not-an-object"),
        ("mega65-tools-notice-removed", "THIRD-PARTY-NOTICES.md",
         "## MEGA65 tools", "## missing tools notice"),
    ]
    rejected: list[str] = []
    for name, path, old, new in trials:
        require(old in clean[path], f"mutation anchor absent: {name}")
        changed = deepcopy(clean)
        changed[path] = changed[path].replace(old, new, 1)
        try:
            validate(changed)
        except CardError:
            rejected.append(name)
    survived = [name for name, *_ in trials if name not in rejected]
    require(not survived, f"Card 6 mutations survived: {survived}")
    return rejected


def descriptor_oracle() -> dict[str, str]:
    program = r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "mega65_dma_descriptor.h"
int main(void) {
    uint8_t f[12], e[20], t[20], z[20];
    static const uint8_t fe[12] = {4,0x56,0x34,0x12,0x78,0x9a,0xbc,0xf0,0xde,0,0,0};
    static const uint8_t ee[20] = {0x0b,0x80,1,0x81,0,0x85,1,0,4,0x57,0x13,0x56,0x34,2,0xef,0xcd,0x0b,0,0,0};
    static const uint8_t te[20] = {0x0b,0x80,0x82,0x81,0,0x85,1,0,4,0x67,5,0,0x40,0,0x56,0xc3,0,0,0,0};
    static const uint8_t ze[20] = {0x0b,0x80,0,0x81,0,0x85,1,0,3,1,0,0xa5,0,0,0xef,0xcd,0x0b,0,0,0};
    lisp65_f018_descriptor(f,4,0x7812,0x9a,0xf0bc,0xde,0x3456);
    lisp65_edma_descriptor(e,4,0x123456,0x0bcdef,0x1357);
    lisp65_edma_tuple_descriptor(t,4,0x4000,0x8200,0xc356,0x0567);
    lisp65_edma_fill_descriptor(z,3,0xa5,0x0bcdef,1);
    if (memcmp(f,fe,12)||memcmp(e,ee,20)||memcmp(t,te,20)||memcmp(z,ze,20)) return 1;
    puts("descriptor-oracle PASS F018=12 EDMA=20 tuple=20 fill=20");
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix="lisp65-card6-") as name:
        root = Path(name)
        source = root / "oracle.c"
        binary = root / "oracle"
        source.write_text(program, encoding="utf-8")
        built = subprocess.run(
            ["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
             "-I", str(ROOT / "src"), str(source), "-o", str(binary)],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        require(built.returncode == 0, f"descriptor oracle compile red:\n{built.stdout}")
        ran = subprocess.run([str(binary)], text=True, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
        require(ran.returncode == 0 and "PASS" in ran.stdout,
                f"descriptor oracle red:\n{ran.stdout}")
        return {"status": "PASS", "output": ran.stdout.strip()}


def run(command: list[str], label: str) -> str:
    completed = subprocess.run(command, cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(completed.returncode == 0, f"{label} red:\n{completed.stdout}")
    return completed.stdout.strip()


def check(write: bool) -> dict[str, Any]:
    from evidence_era import era_bind, era_blob
    clean = texts()
    facts = validate(clean)
    rejected = mutations(clean)
    descriptor = descriptor_oracle()
    dwx_selftest = run(
        [sys.executable, "tools/host-lisp/dwx_prefilter_blind_spot_contract.py", "--selftest"],
        "DWX identity selftest")
    dwx_check = run(
        [sys.executable, "tools/host-lisp/dwx_prefilter_blind_spot_contract.py", "--check"],
        "DWX identity check")
    # Execute the live fork gates above. Their console wording is not a
    # historical Card-6 identity; preserve that field in its sealing era.
    sealed_identity=json.loads(era_blob('534ed453',str(RECEIPT.relative_to(ROOT))))['dwx_identity']
    receipt = {
        "format": "lisp65-block-2.6-card6-small-hardening-dma-tuple-repair-prelink-v1",
        "status": "PRELINK-GREEN-A13-EDMA-TUPLE-FAITHFUL",
        "authority": authority(),
        "facts": facts,
        "descriptor_oracle": descriptor,
        "dwx_identity": sealed_identity,
        "mutations": {"attempted": rejected, "survived": []},
        # Historical identity only; validate(), descriptor execution and
        # the current DWX fork contract remain live above.
        "inputs": [era_bind("534ed453", name) for name in SOURCE_PATHS],
        "budget": {
            "wplto_runs": 0,
            "product_links": 0,
            "device_contacts": 0,
            "final_link_required": True,
            "reason": "A13 tuple repair changes product code; executed values and codegen shape must be measured at the final link",
        },
        "claim_limit": (
            "A13 tuple fidelity, provenance, sharp recomposition mutation and descriptor bytes are prelink-green. "
            "No resident/plane delta, owner-floor result, product attribution, Scope or Acceptance is claimed."
        ),
    }
    data = canonical(receipt)
    if write:
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_bytes(data)
    else:
        require(RECEIPT.is_file() and RECEIPT.read_bytes() == data,
                "registered Card 6 prelink receipt differs from derived result")
    print(f"block-2.6 card6 PRELINK PASS mutations={len(rejected)} descriptor-users=9 WPLTO=0 links=0")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("selftest", "build", "check"))
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            clean = texts()
            validate(clean)
            rejected = mutations(clean)
            descriptor_oracle()
            print(f"block-2.6 card6 SELFTEST PASS mutations={len(rejected)}")
        else:
            check(args.action == "build")
    except (OSError, UnicodeError, json.JSONDecodeError, CardError,
            subprocess.CalledProcessError) as error:
        print(f"block-2.6 card6: FAIL: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
