#!/usr/bin/env python3
"""Prove that LOADING LIBRARIES returns its ordinal cell before the REPL."""

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
REPL = ROOT / "src/repl.c"
MEDIA = ARCH / "c2.3-v2.1-phase9-abi-completion-media-receipt.json"
RECEIPT = ARCH / "c2.3-v2.1-terminal-screen-lease-preflight-receipt.json"
DRIVER = Path(__file__).resolve()
CLANG = ROOT / "tools/llvm-mos/bin/mos-clang"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
AUTHORIZATION = "81d2b9cb"
RECORDED_ON = "2026-08-16"
SECTION = ".text.c2_map_cpu_read"
SCREEN_ADDRESS = 0x0B3A
EXPECTED_PROGRESS_RELOCATABLE = bytes.fromhex(
    "ad0000c90d9002a929c90ab00469308002e9098d3a0b")
EXPECTED_LINKED_PROGRESS = bytes.fromhex(
    "adaec0c90d9002a929c90ab00469308002e9098d3a0b")


class LeaseError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise LeaseError(message)


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


def git_binding(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    value = git_binding(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{value['commit']}:{value['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout.decode()
    text = " ".join(raw.lower().split())
    for token in ("cosmetic repair", "ordinal output is suppressed",
                  "cell cleared before the prompt", "one card"):
        require(token in text, f"screen-lease authority absent: {token}")
    return value


def predecessor() -> dict[str, Any]:
    value = load(MEDIA)
    require(
        value.get("status") ==
            "PASS: phase-9 ABI candidate completed and media closed; D1 ready"
        and value.get("media", {}).get("roles") == 19
        and value.get("media", {}).get("same_world") is True
        and value.get("media", {}).get("readback") == "byteidentical",
        "functional-boot predecessor media drift")
    return value


def assemble(source: str) -> bytes:
    with tempfile.TemporaryDirectory(prefix="c2-v21-screen-lease-") as raw:
        work = Path(raw)
        assembly = work / "reader.s"
        obj = work / "reader.o"
        assembly.write_text(source, encoding="utf-8")
        result = subprocess.run(
            [str(CLANG), "-c", "-mcpu=mos45gs02", str(assembly),
             "-o", str(obj)], cwd=ROOT, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, check=False)
        require(result.returncode == 0,
                f"screen-lease reader assembly red:\n{result.stdout}")
        truth = ElfTruth.read(obj, llvm_readobj=READOBJ,
                              include_section_data=True)
        return truth.section_bytes(SECTION)


def render(value: int) -> int:
    if value >= 13:
        value = 0x29
    if value < 10:
        return value + 0x30
    return value - 9


def source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = (SOURCE.read_text(encoding="utf-8")
              if source_override is None else source_override)
    handback = (
        "\tcmp #$0d\n"
        "\tbcc .Lc2_progress_phase_valid\n"
        "\tlda #$29\n")
    require(
        handback in source
        and "\tsta $0b3a                   ; row 10, column 26\n" in source
        and "private $fe handoff clears the ordinal" in source
        and "\tlda #0\n" not in source[source.index("ordinary product owns"):
                                         source.index("\tlda __rc7")],
        "terminal screen-cell hand-back source absent")
    body = assemble(source)
    require(
        len(body) == 189 and body[12:34] == EXPECTED_PROGRESS_RELOCATABLE,
        "emitted screen-lease sequence is not the exact size-neutral repair")
    codes = {f"0x{value:02x}": f"0x{render(value):02x}"
             for value in (*range(13), 0xFE, 0xFF)}
    require(
        all(render(value) != 0x20 for value in range(13))
        and render(0xFE) == render(0xFF) == 0x20,
        "post-phase ordinal remains visible")
    return {
        "status": "PASS: phase ordinal owns its cell only during phases 0..a",
        "reader_bytes": len(body), "progress_offset": 12,
        "progress_bytes": body[12:34].hex(),
        "screen": {"row": 10, "column": 26,
                   "address": f"0x{SCREEN_ADDRESS:04x}"},
        "active_phase_codes": codes,
        "post_phase_code": "0x20", "post_phase_visible": False,
        "state_bytes": 0, "instruction_delta_bytes": 0,
    }


def repl_order_gate() -> dict[str, Any]:
    source = REPL.read_text(encoding="utf-8")
    begin = source.index("void repl(void)")
    body = source[begin:source.index("for (;;) {", begin)]
    clear = body.index("scr_init();")
    banner = body.index("vm_run_dir(LISP65_BYTECODE_STDLIB_REPL_BANNER_ENTRY")
    prompt = source.index('emit_str("lisp65> ")', begin)
    require(clear < banner and begin + banner < prompt,
            "REPL clear/banner/prompt order drift")
    return {"status": "PASS: final banner read is between clear and prompt",
            "order": ["scr_init", "banner-vm-read", "prompt"],
            "required_banner_read_effect": "screen-code 0x20 at 0x0b3a"}


def derive() -> dict[str, Any]:
    predecessor()
    value = {
        "format": "lisp65-c2.3-v2.1-terminal-screen-lease-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "HOST-GREEN: terminal ordinal cell returned before prompt",
        "authority": {"owner": authorization(), "predecessor_media": bind(MEDIA),
                      "source": bind(SOURCE), "repl": bind(REPL),
                      "driver": bind(DRIVER)},
        "implementation": source_gate(), "terminal_order": repl_order_gate(),
        "card_lock": {"cards_authorized": 1, "cards_consumed": 0,
                      "WPLTO_runs": 0, "product_links": 0,
                      "completion_runs": 0, "media_builds": 0,
                      "device_contacts": 0},
        "claim_limit": "Host preflight only; the one product card has not run.",
    }
    return value


def validate(value: dict[str, Any], expected: dict[str, Any]) -> None:
    require(value == expected, "terminal screen-lease preflight drift")


def receipt_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "restore-visible-zero": lambda x: x["implementation"].update(
            post_phase_code="0x30", post_phase_visible=True),
        "claim-late-liveness": lambda x: x["implementation"].update(
            post_phase_visible=True),
        "move-cell": lambda x: x["implementation"]["screen"].update(
            address="0x0b8a"),
        "spend-card": lambda x: x["card_lock"].update(cards_consumed=1),
        "claim-device": lambda x: x["card_lock"].update(device_contacts=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate(trial, value)
        except LeaseError:
            rejected.append(name)
    require(rejected == list(cases), "screen-lease receipt mutation survived")
    return rejected


def source_mutations() -> list[str]:
    source = SOURCE.read_text(encoding="utf-8")
    cases = {
        "restore-post-phase-zero": source.replace("\tlda #$29\n", "\tlda #0\n", 1),
        "emit-visible-post-phase-digit": source.replace(
            "\tlda #$29\n", "\tlda #$39\n", 1),
        "drop-phase-end-clamp": source.replace(
            "\tcmp #$0d\n\tbcc .Lc2_progress_phase_valid\n\tlda #$29\n", "", 1),
        "move-owned-cell": source.replace("$0b3a", "$0b8a", 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            source_gate(candidate)
        except LeaseError:
            rejected.append(name)
    require(rejected == list(cases), "screen-lease source mutation survived")
    return rejected


def write() -> None:
    require(not RECEIPT.exists(), "terminal screen-lease receipt already exists")
    value = derive()
    value["mutations_rejected"] = {
        "receipt": receipt_mutations(value), "source": source_mutations()}
    RECEIPT.write_bytes(canonical(value))
    print("terminal screen lease: PASS post-phase=blank bytes=189 delta=0")


def check() -> None:
    value = derive()
    expected = deepcopy(value)
    expected["mutations_rejected"] = {
        "receipt": receipt_mutations(value), "source": source_mutations()}
    require(load(RECEIPT) == expected, "terminal screen-lease receipt stale")
    print("terminal screen lease check: PASS mutations=5+4")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else "check"
    require(action in ("write", "check", "selftest"),
            "usage: c2_v21_terminal_screen_lease.py [write|check|selftest]")
    if action == "write":
        write()
    elif action == "check":
        check()
    else:
        source_gate()
        require(len(source_mutations()) == 4,
                "terminal screen-lease mutation count drift")
        print("terminal screen lease selftest: PASS mutations=4")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"terminal screen lease: FAIL: {error}", file=sys.stderr)
        raise SystemExit(2)
