#!/usr/bin/env python3
"""Preflight product-owned LOADING LIBRARIES phase liveness.

The retired diagnostic ring is not inherited.  The synchronous MAP reader is
already executed by every ordinary-product Shelf/C2D read.  It renders the
current decoder phase into the first free screen cell after the existing
LOADING LIBRARIES line, using the linker-owned runtime-context base.  The
preflight assembles the real source, proves the exact 22-byte delta and stops
before WPLTO/card/media/device work.
"""

from __future__ import annotations

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

from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
SOURCE = ROOT / "src/optional/c2_map_cpu_read.s"
CONTEXT = ROOT / "scripts/c2-stream-decoder.h"
CONTROL_ELF = ROOT / (
    "build/c2.3/v2.1-dependent-vma-replacement-card/final/"
    "lisp65-c2-substitution-linked.prg.elf")
CONTROL_OBJECT = ROOT / (
    "build/c2.3/v2.1-dependent-vma-replacement-card/final/"
    ".canonical-objects-lisp65-c2-substitution-linked/"
    "061-c2_map_cpu_read.s.o")
CARD = ARCH / "c2.3-v2.1-dependent-vma-replacement-card-receipt.json"
OLD_RING = ARCH / "c2.3-v2.1-loading-libraries-progress-ring-receipt.json"
OLD_CONTACT = ARCH / (
    "c2.3-v2.1-loading-libraries-stage-breadcrumb-contact-receipt.json")
RECEIPT = ARCH / "c2.3-v2.1-product-loading-liveness-preflight-receipt.json"
DRIVER = Path(__file__).resolve()

AUTHORIZATION = "b83f419e"
FORMAT = "lisp65-c2.3-v2.1-product-loading-liveness-preflight-v1"
RECORDED_ON = "2026-08-15"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
CLANG = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
SECTION = ".text.c2_map_cpu_read"
RUNTIME_SYMBOL = "__lisp65_c2_fixed_bank0_runtime"
PHASE_OFFSET = 42
SCREEN_ADDRESS = 0x0B3A
FACADE = 0xB3B0


class LivenessError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise LivenessError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": digest(raw)}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().split()).lower()
    for token in ("product-liveness ordinal", "ordinary product medium",
                  "diagnostic staging path is retired",
                  "contact later by separate release"):
        require(token in text, f"product-liveness authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": digest(raw)}


def strip_progress(source: str) -> str:
    begin = source.index("\t; The ordinary product owns its LOADING LIBRARIES progress.")
    end_token = "\tsta $0b3a                   ; row 10, column 26\n"
    end = source.index(end_token, begin) + len(end_token)
    return source[:begin] + source[end:]


def assemble(source: str) -> tuple[bytes, int]:
    with tempfile.TemporaryDirectory(prefix="c2-v21-product-life-") as raw:
        work = Path(raw); assembly = work / "reader.s"; obj = work / "reader.o"
        assembly.write_text(source, encoding="utf-8")
        result = subprocess.run(
            [str(CLANG), "-c", "-mcpu=mos45gs02", str(assembly), "-o", str(obj)],
            cwd=ROOT, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, check=False)
        require(result.returncode == 0, f"liveness reader assembly red:\n{result.stdout}")
        truth = ElfTruth.read(obj, llvm_readobj=READOBJ, include_section_data=True)
        return truth.section_bytes(SECTION), truth.section(SECTION).bytes


def phase_model(value: int) -> str:
    phase = value if value < 13 else 0
    return "0123456789ABCDEF"[phase]


def phase_screen_code(value: int) -> int:
    phase = value if value < 13 else 0
    return 0x30 + phase if phase < 10 else phase - 9


def source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = SOURCE.read_text(encoding="utf-8") if source_override is None else source_override
    require(
        f"\t.globl {RUNTIME_SYMBOL}" in source
        and f"\tlda {RUNTIME_SYMBOL}+{PHASE_OFFSET}" in source
        and "\tsta $0b3a" in source
        and "$c0ae" not in source
        and "LISP65_STARTUP_REQUIRE_EXPERIENCE" not in source
        and "#ifdef DIAGNOSTIC" not in source
        and "diagnostic" in source[source.index("ordinary product owns"):
                                    source.index("\tlda __rc7")]
        and source.index("\tsta __rc11") < source.index("ordinary product owns")
        < source.index("\tlda __rc7"),
        "product phase liveness source is pinned, conditional or misplaced")
    without = strip_progress(source)
    before, before_bytes = assemble(without)
    after, after_bytes = assemble(source)
    control_truth = ElfTruth.read(CONTROL_OBJECT, llvm_readobj=READOBJ,
                                  include_section_data=True)
    control = control_truth.section_bytes(SECTION)
    require(before == control and before_bytes == 166,
            "progress-free source is not byteidentical to Link-107 reader")
    require(after_bytes == 188 and after[:12] == before[:12]
            and after[34:] == before[12:],
            "phase-liveness instruction delta is not the exact 22-byte insertion")
    return {"status": "PASS: ordinary product phase ordinal source exact",
            "progress_free_reader_bytes": before_bytes,
            "progress_reader_bytes": after_bytes, "delta_bytes": 22,
            "runtime_base": RUNTIME_SYMBOL, "phase_offset": PHASE_OFFSET,
            "screen": {"row": 10, "column": 26,
                       "address": f"0x{SCREEN_ADDRESS:04x}"},
            "rendering": {f"0x{value:02x}": {
                "visible": phase_model(value),
                "screen_code": f"0x{phase_screen_code(value):02x}"}
                for value in (*range(13), 0xFE)},
            "state_bytes": 0, "IRQ_hooks": 0, "diagnostic_identity": False}


def context_gate() -> dict[str, Any]:
    source = CONTEXT.read_text(encoding="utf-8")
    require("uint8_t phase;" in source and "uint8_t reserved;" in source,
            "decoder context phase ABI absent")
    program = f'''#include <stddef.h>\n
#define C2_STREAM_PRODUCT_V3 1\n
#include "{CONTEXT.relative_to(ROOT).as_posix()}"\n
_Static_assert(offsetof(c2_stream_context, phase) == {PHASE_OFFSET}, "phase");\n
_Static_assert(sizeof(c2_stream_context) == 46, "size");\n
int main(void) {{ return 0; }}\n'''
    result = subprocess.run(
        [str(CLANG), "-std=c11", "-mcpu=mos45gs02", "-I", str(ROOT),
         "-x", "c", "-", "-fsyntax-only"],
        cwd=ROOT, input=program, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0, f"decoder phase ABI compile red:\n{result.stdout}")
    return {"status": "PASS: real context phase ABI independently compiled",
            "context_bytes": 46, "phase_offset": PHASE_OFFSET,
            "address_derivation": f"{RUNTIME_SYMBOL}+{PHASE_OFFSET}"}


def capacity_gate() -> dict[str, Any]:
    truth = ElfTruth.read(CONTROL_ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    text = truth.section(".text")
    reader = truth.symbol("c2_map_cpu_read")
    runtime = truth.symbol(RUNTIME_SYMBOL)
    require(reader.bytes == 166 and runtime.value == 0xC084
            and text.address + text.bytes == 0xB398,
            "Link-107 product capacity authority drift")
    projected_end = text.address + text.bytes + 22
    require(projected_end == 0xB3AE and projected_end <= FACADE,
            "phase liveness does not fit before mapped-far facade")
    return {"control_text_end_exclusive": "0xb398",
            "phase_liveness_delta_bytes": 22,
            "projected_text_end_exclusive": f"0x{projected_end:04x}",
            "mapped_far_facade": f"0x{FACADE:04x}",
            "projected_free_bytes": FACADE - projected_end,
            "margin_class": "measured candidate reserve; not a reusable budget"}


def predecessor_gate() -> dict[str, Any]:
    card = load(CARD); ring = load(OLD_RING); contact = load(OLD_CONTACT)
    require(
        card.get("status") == "PASS: sole dependent-VMA replacement card green"
        and ring.get("status") ==
            "HOST-GREEN; LINK107-CPU-TRANSPORT-RING; CONTACT-AUTHORIZED"
        and contact.get("status") == "BREADCRUMB-COMMITTED",
        "product-liveness predecessor authority drift")
    return {"product_card": bind(CARD), "retired_diagnostic_ring": bind(OLD_RING),
            "retirement_trigger": bind(OLD_CONTACT)}


def derive() -> dict[str, Any]:
    value = {
        "format": FORMAT, "recorded_on": RECORDED_ON,
        "status": "HOST-GREEN-PRODUCT-LIVENESS; PRODUCT-CARD-LOCKED",
        "authority": authority(),
        "inputs": {"source": bind(SOURCE), "context": bind(CONTEXT),
                   "control_ELF": bind(CONTROL_ELF),
                   "control_object": bind(CONTROL_OBJECT), "driver": bind(DRIVER)},
        "predecessor": predecessor_gate(),
        "implementation": source_gate(), "context_ABI": context_gate(),
        "capacity": capacity_gate(),
        "measurement_route": {
            "medium": "ordinary product medium",
            "visible_line": "LISP65: LOADING LIBRARIES <hex-phase>",
            "updates": "at every successful or attempted MAP-reader entry",
            "diagnostic_media_retired": True,
            "separate_media_builder": False},
        "card_lock": {"product_cards_authorized": 0, "WPLTO_runs": 0,
                      "product_links": 0, "media_builds": 0,
                      "device_contacts": 0},
        "claim_limit": (
            "Host preflight only. The source is ready, but no product card, "
            "medium or device contact is authorized by this receipt.")}
    value["mutations"] = mutations(value); audit(value); return value


def audit(value: dict[str, Any]) -> None:
    impl = value.get("implementation", {})
    cap = value.get("capacity", {})
    rendering = impl.get("rendering", {})
    require(
        value.get("status") == "HOST-GREEN-PRODUCT-LIVENESS; PRODUCT-CARD-LOCKED"
        and impl.get("delta_bytes") == 22 and impl.get("state_bytes") == 0
        and impl.get("IRQ_hooks") == 0
        and impl.get("diagnostic_identity") is False
        and rendering.get("0x09") == {"visible": "9", "screen_code": "0x39"}
        and rendering.get("0x0a") == {"visible": "A", "screen_code": "0x01"}
        and rendering.get("0xfe") == {"visible": "0", "screen_code": "0x30"}
        and cap.get("projected_free_bytes") == 2
        and value.get("measurement_route", {}).get("diagnostic_media_retired") is True
        and value.get("measurement_route", {}).get("separate_media_builder") is False
        and value.get("card_lock") == {"product_cards_authorized": 0,
            "WPLTO_runs": 0, "product_links": 0, "media_builds": 0,
            "device_contacts": 0}
        and value.get("claim_limit", "").startswith("Host preflight only"),
        "product-liveness preflight drift")


def mutations(base: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "authorize-card": lambda x: x["card_lock"].update(
            product_cards_authorized=1),
        "spend-wplto": lambda x: x["card_lock"].update(WPLTO_runs=1),
        "restore-diagnostic-medium": lambda x: x["measurement_route"].update(
            diagnostic_media_retired=False),
        "invent-free-state": lambda x: x["implementation"].update(state_bytes=1),
        "invent-reserve": lambda x: x["capacity"].update(projected_free_bytes=24),
        "authorize-device": lambda x: x.update(claim_limit="Device authorized."),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(base); mutate(candidate)
        try: audit(candidate)
        except LivenessError: rejected.append(name)
    require(rejected == list(cases), "product-liveness receipt mutation survived")
    return rejected


def source_mutations() -> list[str]:
    source = SOURCE.read_text(encoding="utf-8")
    cases = {
        "pin-runtime-address": source.replace(
            f"{RUNTIME_SYMBOL}+{PHASE_OFFSET}", "$c0ae", 1),
        "wrong-screen-row": source.replace("$0b3a", "$0b8a", 1),
        "remove-fe-clamp": source.replace(
            "\tcmp #$0d\n\tbcc .Lc2_progress_phase_valid\n\tlda #0\n", "", 1),
        "add-diagnostic-conditional": source.replace(
            "\t; The ordinary product owns", "#ifdef DIAGNOSTIC\n\t; The ordinary product owns", 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try: source_gate(candidate)
        except LivenessError: rejected.append(name)
    require(rejected == list(cases), "product-liveness source mutation survived")
    return rejected


def write() -> None:
    value = derive(); value["source_mutations"] = source_mutations()
    RECEIPT.write_bytes(canonical(value))
    print("product loading liveness: PASS phase-ordinal card-locked")


def check() -> None:
    value = derive(); value["source_mutations"] = source_mutations()
    require(load(RECEIPT) == value, "product-liveness receipt stale")
    print("product loading liveness check: PASS mutations=6+4")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else "check"
    if action == "write": write()
    elif action == "check": check()
    elif action == "selftest":
        value = derive(); require(len(value["mutations"]) == 6, "mutation drift")
        require(len(source_mutations()) == 4, "source mutation drift")
        print("product loading liveness selftest: PASS mutations=6+4")
    else: raise LivenessError(f"unknown action: {action}")
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except LivenessError as error:
        print(f"product loading liveness: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
