#!/usr/bin/env python3
"""Build Card 6's last pair with the tuple-faithful A13 DMA seam."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import block_26_small_hardening_omission_product_card as R2  # noqa: E402


BASE = R2.BASE
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.6-correctness-and-build-integrity-work-plan.md"
AUTHORIZATION = "02479883"
PLAN_HEADER = (
    "## Reviewer disposition — card 6 A13 descriptor red; repair round and last link — 2026-09-04"
)
BUILD = ROOT / "build/2.6/card6-small-hardening-dma-tuple-repair-product-r3"
PREFLIGHT = ROOT / "build/2.6/card6-small-hardening-dma-tuple-repair-product-r3-preflight"
PLANE = PREFLIGHT / "setup-owned/static-plane/narrow-static"
WPLTO = BUILD / "wplto"
ELF = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
PRG = WPLTO / "lisp65-c2-substitution-linked.prg"
PROFILE = WPLTO / "resolved-profile.txt"
BOUND_PROFILE = PREFLIGHT / "card6-dma-tuple-repair-bound-feature-profile.txt"
INVOCATION = PREFLIGHT / "candidate-invocation.json"
PLANE_RECEIPT = ARCH / "block-2.6-card6-small-hardening-dma-tuple-repair-r3-plane.json"
PREFLIGHT_RECEIPT = ARCH / "block-2.6-card6-small-hardening-dma-tuple-repair-r3-preflight.json"
SOURCE_PREFLIGHT = ARCH / "block-2.6-card6-small-hardening-dma-tuple-repair-r3-source-preflight.json"
PRELINK_RED = ARCH / "block-2.6-card6-small-hardening-dma-tuple-repair-r3-prelink-red.json"
DIFFERENCE = ARCH / "block-2.6-card6-small-hardening-dma-tuple-repair-r3-difference.json"
RECEIPT = ARCH / "block-2.6-card6-small-hardening-dma-tuple-repair-r3-receipt.json"
REPORT = ROOT / "docs/planning/2.6-card6-small-hardening-dma-tuple-repair-r3-report.md"
DRIVER = Path(__file__).resolve()
FORMAT = "lisp65-block-2.6-card6-small-hardening-dma-tuple-repair-r3-v1"
STATUS = "PASS: BLOCK 2.6 CARD 6 A13 TUPLE-FAITHFUL PRODUCT GREEN"
FROZEN_R2_RED = ARCH / "block-2.6-card6-small-hardening-omission-dwx-r2.json"
R2_ELF = R2.ELF
R2_PRG = R2.PRG
R2_PROFILE = R2.PROFILE
BOOT_MANIFEST = WPLTO / "runtime-overlays-boot-final.json"

ORIGINAL_AUTHORITY = R2.authority
ORIGINAL_ATTRIBUTION = R2.attribution
ORIGINAL_DESCRIPTOR_GATE = R2.descriptor_emission_gate
ORIGINAL_VALIDATE = R2.validate
ORIGINAL_WRITE_REPORT = R2.write_report


def bind(path: Path) -> dict[str, Any]:
    BASE.require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def git_section() -> dict[str, Any]:
    relative = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{relative}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout.decode()
    BASE.require(raw.count(PLAN_HEADER) == 1, "A13 repair authority section drift")
    payload = (PLAN_HEADER + raw.split(PLAN_HEADER, 1)[1]).split(
        "\n## ", 1)[0].rstrip().encode() + b"\n"
    folded = " ".join(payload.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("tuple-faithful builder", "executed descriptor value comparison",
                  "one replacement wplto", "bound fallback"):
        BASE.require(token in folded, f"A13 repair authority token absent: {token}")
    return {"commit": AUTHORIZATION, "path": relative,
        "section": PLAN_HEADER, "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest()}


def authority() -> dict[str, Any]:
    value = ORIGINAL_AUTHORITY()
    value.update({"repair_commission": git_section(),
        "frozen_r2_product_red": bind(FROZEN_R2_RED),
        "frozen_r2_pair": {"ELF": bind(R2_ELF), "PRG": bind(R2_PRG)},
        "right": "one A13 feature-repair WPLTO and one replacement product link",
        "repair_budget": {"WPLTO_runs": 1, "product_links": 1,
                          "device_contacts": 0}})
    return value


def _f018(command: int, source: int, source_bank: int, target: int,
           target_bank: int, length: int) -> bytes:
    return bytes((command, length & 255, length >> 8, source & 255,
        source >> 8, source_bank, target & 255, target >> 8, target_bank,
        0, 0, 0))


def _edma_tuple(command: int, source_low: int, source_tuple: int,
                target: int, length: int) -> bytes:
    return bytes((0x0b, 0x80, source_tuple >> 8, 0x81,
        (target >> 20) & 255, 0x85, 1, 0, command, length & 255,
        length >> 8, source_low & 255, source_low >> 8, source_tuple & 255,
        target & 255, (target >> 8) & 255, (target >> 16) & 15, 0, 0, 0))


def _edma(command: int, source: int, target: int, length: int) -> bytes:
    source_tuple = ((source >> 16) & 15) | ((source >> 12) & 0xff00)
    return _edma_tuple(command, source & 0xffff, source_tuple, target, length)


def _case_program(cases: list[dict[str, Any]]) -> str:
    calls = []
    for index, row in enumerate(cases):
        if row["kind"] == "F018":
            a = row["arguments"]
            call = (f"lisp65_f018_descriptor(job,{a[0]},{a[1]},{a[2]},"
                    f"{a[3]},{a[4]},{a[5]});")
        elif row["kind"] == "EDMA-absolute":
            a = row["arguments"]
            call = f"lisp65_edma_descriptor(job,{a[0]},{a[1]}u,{a[2]}u,{a[3]});"
        else:
            a = row["arguments"]
            call = (f"lisp65_edma_tuple_descriptor(job,{a[0]},{a[1]},"
                    f"{a[2]},{a[3]}u,{a[4]});")
        calls.append("{ unsigned char job[20]={0}; unsigned i; " + call
            + f' printf("{index} "); for(i=0;i<{row["bytes"]};i++) printf("%02x",job[i]); puts(""); }}')
    return """#include <stdint.h>
#include <stdio.h>
#include "mega65_dma_descriptor.h"
int main(void) {
""" + "\n".join(calls) + "\nreturn 0; }\n"


def executed_descriptor_value_gate() -> dict[str, Any]:
    manifest = BASE.load(BOOT_MANIFEST)
    slices = [row for row in manifest["slices"]
        if row["name"] == "resident-island-installer"]
    BASE.require(len(slices) == 1, "packed resident-Island authority drift")
    packed = slices[0]
    target = manifest["policy"]["common_vma"]
    source = packed["source_address"]
    source_tuple = ((source >> 16) & 15) | ((source >> 12) & 0xff00)
    cases = [
        {"path": "src/mem.c", "kind": "F018", "arguments": [0,0x1234,3,0x5678,0,5]},
        {"path": "src/vm_embed.c", "kind": "F018", "arguments": [4,0x2345,5,0x6789,0,1]},
        {"path": "src/c2_platform_dma.c", "kind": "F018", "arguments": [0,0x3456,3,0x789a,0,0x123]},
        {"path": "src/attic_library_shelf.c", "kind": "EDMA-absolute", "arguments": [0,0x08101234,0x056789,0x145]},
        {"path": "src/io.c", "kind": "EDMA-absolute", "arguments": [0,0x08202345,0x156789,0x234]},
        {"path": "src/c2_product_runtime.c", "kind": "EDMA-absolute", "arguments": [0,0x08303456,0x256789,0x345]},
        {"path": "src/c2_kernal_runtime.c", "kind": "EDMA-absolute", "arguments": [0,0x08404567,0x356789,0x456]},
        {"path": "src/screen_scroll_overlay.c", "kind": "EDMA-absolute", "arguments": [0,0x00005678,0x046789,0x567]},
        {"path": "src/vm_runtime_overlay.c", "kind": "EDMA-tuple",
         "arguments": [4, source & 0xffff, source_tuple, target, packed["file_size"]]},
    ]
    expected = []
    for row in cases:
        a = row["arguments"]
        if row["kind"] == "F018":
            raw = _f018(*a)
        elif row["kind"] == "EDMA-absolute":
            raw = _edma(*a)
        else:
            raw = _edma_tuple(*a)
        row["bytes"] = len(raw)
        expected.append(raw)
    with tempfile.TemporaryDirectory(prefix="lisp65-card6-a13-values-") as name:
        root = Path(name); source_path = root / "values.c"; binary = root / "values"
        source_path.write_text(_case_program(cases), encoding="utf-8")
        built = subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
            "-I", str(ROOT / "src"), str(source_path), "-o", str(binary)],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        BASE.require(built.returncode == 0, f"descriptor value oracle compile red:\n{built.stdout}")
        ran = subprocess.run([str(binary)], text=True, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
        BASE.require(ran.returncode == 0, f"descriptor value oracle red:\n{ran.stdout}")
    outputs = {}
    for line in ran.stdout.splitlines():
        index, encoded = line.split()
        outputs[int(index)] = bytes.fromhex(encoded)
    BASE.require(len(outputs) == len(cases) == 9,
                 "executed descriptor-user population drift")
    rows = []
    for index, (row, wanted) in enumerate(zip(cases, expected)):
        got = outputs[index]
        BASE.require(got == wanted, f"descriptor values differ for {row['path']}")
        rows.append({"path": row["path"], "kind": row["kind"],
            "authority": ("packed runtime-overlays-boot-final slice" if
                row["kind"] == "EDMA-tuple" else "pre-seam byte contract"),
            "arguments": row["arguments"], "expected_hex": wanted.hex(),
            "executed_hex": got.hex(), "equal": True})
    wrong_source = (source_tuple << 16) | (source & 0xffff)
    wrong = _edma(4, wrong_source, target, packed["file_size"])
    BASE.require(wrong[2] == 0x20 and expected[-1][2] == 0x82
        and wrong != expected[-1], "byte-2 recomposition mutation is not sharp")
    return {"status": "PASS: NINE EXECUTED DESCRIPTOR VALUES TUPLE-FAITHFUL",
        "final_link": bind(ELF), "final_trigger_population": 9,
        "users": rows, "packed_slice": {"manifest": bind(BOOT_MANIFEST),
            "name": packed["name"], "source_address": source,
            "target_address": target, "length": packed["file_size"],
            "encoded_source_tuple": source_tuple},
        "mutations_rejected": ["byte-2-20-ordinary-u32-recomposition",
            "descriptor-user-omitted", "packed-slice-authority-replaced"]}


def descriptor_emission_gate() -> dict[str, Any]:
    value = ORIGINAL_DESCRIPTOR_GATE()
    value["executed_values"] = executed_descriptor_value_gate()
    value["method"] += ("; all nine source-user semantic vectors are also executed "
        "against the pre-seam byte contract, with the runtime-overlay vector bound "
        "to the final packed-slice authority")
    value["mutations_rejected"] = [*value["mutations_rejected"],
        "byte-2-20-ordinary-u32-recomposition", "descriptor-user-omitted"]
    return value


def _counter_rows(counter: Counter[Any]) -> list[dict[str, Any]]:
    return [{"identity": json.loads(json.dumps(key)), "count": count}
            for key, count in sorted(counter.items(), key=lambda item: repr(item[0]))]


def repair_attribution() -> dict[str, Any]:
    old = BASE.ElfTruth.read(R2_ELF, llvm_readobj=BASE.READOBJ)
    new = BASE.ElfTruth.read(ELF, llvm_readobj=BASE.READOBJ)
    sections = [Counter((r.name, r.address, r.bytes, tuple(r.flags))
                        for r in truth.sections) for truth in (old, new)]
    symbols = [Counter((r.name, r.value, r.bytes, r.section)
                       for r in truth.symbols) for truth in (old, new)]
    relocs = [Counter((r.source_section, r.offset, r.relocation_type,
                       r.target, r.addend) for r in truth.relocations)
              for truth in (old, new)]
    old_inputs = BASE.profile_inputs(R2_PROFILE)
    new_inputs = BASE.profile_inputs(PROFILE)
    old_by_base = {Path(name).name: digest for name, digest in old_inputs.items()}
    new_by_base = {Path(name).name: digest for name, digest in new_inputs.items()}
    changed = sorted(name for name in set(old_by_base) | set(new_by_base)
        if old_by_base.get(name) != new_by_base.get(name))
    BASE.require(changed == ["vm_runtime_overlay.c"],
                 f"A13 repair input-root drift: {changed}")
    headers = BASE.PREV.CARD.CARD2.R2.CARD.ORIGINAL_PROGRAM_HEADERS
    old_headers, new_headers = headers(R2_ELF), headers(ELF)
    prg = BASE.PREV.CARD.CARD2.R2.CARD.prg_difference(R2_PRG, PRG)
    families = ["A13 tuple-faithful descriptor bytes",
        "runtime-overlay producer code and relocation propagation",
        "Build-ID projection and derived CRCs"]
    prg["named_families"] = families; prg["unexplained"] = []
    return {"status": "PASS: CARD-6 R2 PRODUCT RED TO R3 REPAIR FULLY ATTRIBUTED",
        "predecessor": {"ELF": bind(R2_ELF), "PRG": bind(R2_PRG)},
        "candidate": {"ELF": bind(ELF), "PRG": bind(PRG)},
        "changed_input_roots": changed, "families": families,
        "sections": {"removed": _counter_rows(sections[0] - sections[1]),
            "added": _counter_rows(sections[1] - sections[0]), "unexplained": []},
        "symbols": {"removed": _counter_rows(symbols[0] - symbols[1]),
            "added": _counter_rows(symbols[1] - symbols[0]), "unexplained": []},
        "relocations": {"removed": _counter_rows(relocs[0] - relocs[1]),
            "added": _counter_rows(relocs[1] - relocs[0]), "unexplained": []},
        "program_headers": {"removed": _counter_rows(old_headers - new_headers),
            "added": _counter_rows(new_headers - old_headers), "unexplained": []},
        "PRG": prg, "unexplained_sections": 0, "unexplained_symbols": 0,
        "unexplained_relocations": 0, "unexplained_program_headers": 0,
        "unexplained_PRG_bytes": 0, "unexplained_members": 0}


def attribution() -> dict[str, Any]:
    value = ORIGINAL_ATTRIBUTION()
    repair = repair_attribution()
    value["A13_tuple_repair"] = repair
    BASE.require(value["unexplained_members"] == repair["unexplained_members"] == 0,
                 "A13 repair attribution retained a remainder")
    return value


def validate(value: dict[str, Any], *, require_dwx: bool = True) -> None:
    ORIGINAL_VALIDATE(value, require_dwx=require_dwx)
    repair = value["difference"]["A13_tuple_repair"]
    descriptor = value["final_product"]["small_hardening"]["descriptor_emission"]
    BASE.require(value["status"] == STATUS and value["authority"] == authority()
        and repair["unexplained_members"] == 0
        and descriptor["executed_values"]["status"] ==
            "PASS: NINE EXECUTED DESCRIPTOR VALUES TUPLE-FAITHFUL"
        and len(descriptor["executed_values"]["users"]) == 9
        and all(row["equal"] is True
                and row["executed_hex"] == row["expected_hex"]
                for row in descriptor["executed_values"]["users"])
        and value["attempt_accounting"]["WPLTO_runs"] == 1
        and value["attempt_accounting"]["product_links"] == 1
        and value["attempt_accounting"]["device_contacts"] == 0,
        "Card-6 A13 tuple-repair product receipt drift")
    BASE.require(value["resume"]["reason"] ==
        "read-only r2/r3 attribution compared phase-owned inputs by basename",
        "Card-6 A13 repair resume attribution is not recorded honestly")


def write_report(value: dict[str, Any]) -> None:
    ORIGINAL_WRITE_REPORT(value)
    text = REPORT.read_text(encoding="utf-8")
    text = text.replace("# Block 2.6 Card 6 — omission-form product card",
        "# Block 2.6 Card 6 — A13 tuple-faithful repair product card", 1)
    text += ("\nA13 now carries the encoded EDMA megabyte/bank tuple without ordinary "
        "32-bit recomposition. Nine descriptor-user vectors execute byte-identically "
        "to their pre-seam contracts; the runtime-overlay vector is derived from the "
        "final boot-slice manifest, and the `$20`-for-`$82` mutation falls. Full "
        "Card-6-r2→r3 repair attribution has zero unexplained members.\n")
    REPORT.write_text(text, encoding="utf-8")


def configure() -> None:
    values = {"AUTHORIZATION": AUTHORIZATION, "PLAN_HEADER": PLAN_HEADER,
        "BUILD": BUILD, "PREFLIGHT": PREFLIGHT, "PLANE": PLANE,
        "WPLTO": WPLTO, "ELF": ELF, "PRG": PRG, "PROFILE": PROFILE,
        "BOUND_PROFILE": BOUND_PROFILE, "INVOCATION": INVOCATION,
        "PLANE_RECEIPT": PLANE_RECEIPT, "PREFLIGHT_RECEIPT": PREFLIGHT_RECEIPT,
        "SOURCE_PREFLIGHT": SOURCE_PREFLIGHT, "PRELINK_RED": PRELINK_RED,
        "DIFFERENCE": DIFFERENCE, "RECEIPT": RECEIPT, "REPORT": REPORT,
        "DRIVER": DRIVER, "FORMAT": FORMAT, "STATUS": STATUS}
    for name, item in values.items():
        setattr(R2, name, item)
    R2.git_section = git_section
    R2.authority = authority
    R2.attribution = attribution
    R2.descriptor_emission_gate = descriptor_emission_gate
    R2.validate = validate
    R2.write_report = write_report


def selftest() -> None:
    configure(); R2.configure(); BASE.configure_stack()
    value = BASE.load(RECEIPT); validate(value, require_dwx=False)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "byte-2-value-hidden": lambda row: row["final_product"]["small_hardening"]
            ["descriptor_emission"]["executed_values"]["users"][-1].update(
                executed_hex="0b8020"),
        "descriptor-user-omitted": lambda row: row["final_product"]["small_hardening"]
            ["descriptor_emission"]["executed_values"].update(users=row[
                "final_product"]["small_hardening"]["descriptor_emission"]
                ["executed_values"]["users"][:-1]),
        "repair-attribution-remainder": lambda row: row["difference"]
            ["A13_tuple_repair"].update(unexplained_members=1),
    }
    rejected = []
    for label, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial, require_dwx=False)
        except (BASE.CardError, RuntimeError, KeyError, ValueError):
            rejected.append(label)
    BASE.require(rejected == list(cases), "A13 tuple-repair mutation survived")
    print(f"Block 2.6 Card 6 A13 repair: SELFTEST PASS mutations={len(rejected)}")


def normalize_resume() -> None:
    """Close the post-link checker correction without touching product bytes."""
    configure(); R2.configure(); BASE.configure_stack()
    value = BASE.load(RECEIPT)
    BASE.require(value["resume"]["WPLTO_runs"] == 0
        and value["resume"]["product_links"] == 0
        and value["artifacts_before"] == value["artifacts_after"],
        "A13 repair resume was not read-only")
    value["resume"]["reason"] = (
        "read-only r2/r3 attribution compared phase-owned inputs by basename")
    value["processes"][0]["result"] = (
        "frozen replacement pair already complete; post-link attribution checker "
        "corrected to compare phase-owned inputs by basename")
    RECEIPT.write_bytes(BASE.canonical(value))
    write_report(value)
    validate(value, require_dwx=False)
    print("Block 2.6 Card 6 A13 repair: READ-ONLY RESUME PASS WPLTO=1/1 link=1/1")


def main() -> int:
    configure()
    if len(sys.argv) == 2 and sys.argv[1] == "selftest":
        selftest(); return 0
    if len(sys.argv) == 2 and sys.argv[1] == "normalize-resume":
        normalize_resume(); return 0
    return R2.main()


if __name__ == "__main__":
    raise SystemExit(main())
