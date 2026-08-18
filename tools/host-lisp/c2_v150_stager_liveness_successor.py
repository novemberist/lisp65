#!/usr/bin/env python3
"""Rebuild only the v1.5 media contract with the delivered stager opt-in."""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))
import c2_lite_media_product as MEDIA  # noqa: E402
import c2_link95_world_bound_media as PAIR  # noqa: E402
import c2_v150_candidate_media as BASE  # noqa: E402
import c2_v150_candidate_product as CARD  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


BUILD = ROOT / "build/c2.3/v1.5.0-candidate-media-link97-stager-liveness"
SHARED = BUILD / "shared-system"
MANIFEST = SHARED / "candidate-manifest.json"
DESCRIPTOR = SHARED / "boot.id"
STAGER = SHARED / "autoboot.c65"
STAGER_ELF = SHARED / "autoboot.c65.elf"
STAGER_MAP = SHARED / "autoboot.c65.map"
PRODUCT_D81 = SHARED / "lisp65-product.d81"
WORK_D81 = SHARED / "lisp65-work.d81"
MOUNT = SHARED / "lisp65-product.mount.json"
LIBRARY_D81 = BASE.LIBRARY_D81
PREDECESSOR_ELF = BASE.SHARED / "autoboot.c65.elf"
PREDECESSOR_RECEIPT = BASE.RECEIPT
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-link97-stager-liveness-media-receipt.json")
FORMAT = "lisp65-c2.3-v150-link97-stager-liveness-media-v1"
STATUS = "V150-LINK97-STAGER-LIVENESS-MEDIA-GREEN; FRESH-D1-PENDING"
OPT_IN = "-DLISP65_STARTUP_REQUIRE_EXPERIENCE"
MESSAGE = b"LISP65: STAGING MEDIA"
ROW_BASE = 0x0800 + 8 * 80


class SuccessorError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SuccessorError(message)


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


def configure() -> None:
    BASE.configure()
    MEDIA.BUILD = SHARED
    MEDIA.MANIFEST = MANIFEST
    MEDIA.DESCRIPTOR = DESCRIPTOR
    MEDIA.STAGER = STAGER
    MEDIA.STAGER_MAP = STAGER_MAP
    MEDIA.PRODUCT_D81 = PRODUCT_D81
    MEDIA.WORK_D81 = WORK_D81
    MEDIA.MOUNT = MOUNT


def producer_gate(source_override: str | None = None) -> dict[str, Any]:
    source = source_override or Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body
                 if isinstance(node, ast.FunctionDef)}
    build = functions.get("build_action")
    configure_node = functions.get("configure")
    require(build is not None and configure_node is not None,
            "successor producer lifecycle absent")
    build_text = ast.unparse(build)
    configure_text = ast.unparse(configure_node)
    calls = [ast.unparse(node.func) for node in ast.walk(build)
             if isinstance(node, ast.Call)]
    require(
        calls.count("MEDIA.build") == 1
        and "stager_compile_defines=(OPT_IN,)" in build_text
        and "CARD.build" not in calls
        and "CARD.post_link_replay" not in calls
        and "BASE.LIB.build_library_variant" not in calls
        and all(token in configure_text for token in (
            "MEDIA.BUILD = SHARED", "MEDIA.MANIFEST = MANIFEST",
            "MEDIA.DESCRIPTOR = DESCRIPTOR", "MEDIA.STAGER = STAGER",
            "MEDIA.PRODUCT_D81 = PRODUCT_D81")),
        "successor producer can omit the real opt-in or escape media-only scope")
    return {"result": "passed", "shared_media_builds": 1,
            "library_builds": 0, "product_links": 0, "WPLTO_runs": 0}


def producer_mutations() -> list[str]:
    source = Path(__file__).read_text(encoding="utf-8")
    anchor = (
        "    configure()\n"
        "    shared = MEDIA.build(stager_compile_defines=(OPT_IN,))")
    cases = {
        "drop-real-stager-opt-in": source.replace(
            anchor, "    configure()\n"
            "    shared = MEDIA.build(stager_compile_defines=())", 1),
        "reenter-product-card": source.replace(
            anchor, "    configure()\n    CARD.build()\n"
            "    shared = MEDIA.build(stager_compile_defines=(OPT_IN,))", 1),
        "rebuild-library": source.replace(
            anchor, "    configure()\n    BASE.LIB.build_library_variant()\n"
            "    shared = MEDIA.build(stager_compile_defines=(OPT_IN,))", 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            producer_gate(candidate)
        except SuccessorError:
            rejected.append(name)
    require(rejected == list(cases), "successor producer source mutation survived")
    return rejected


def _main_bytes(elf: Path) -> tuple[int, bytes]:
    truth = ElfTruth.read(
        elf, llvm_readobj=MEDIA.CANONICAL.COMPILER.parent / "llvm-readobj",
        include_section_data=True)
    main = truth.symbol("main")
    section = truth.section(main.section)
    data = truth.section_bytes(main.section)
    offset = main.value - section.address
    require(main.bytes > 0 and 0 <= offset < len(data), "stager main is unbound")
    return main.value, data[offset:offset + main.bytes]


def _signed(byte: int) -> int:
    return byte - 256 if byte & 0x80 else byte


def delivered_liveness_gate(elf: Path) -> dict[str, Any]:
    """Execute the linked main prefix until its first I/O-enable store."""
    main_vma, code = _main_bytes(elf)
    marker = bytes.fromhex("a200a0008416a0188417a9208004")
    require(code.count(marker) == 1,
            "actual stager ELF lacks the unique liveness-prefix entry")
    pc = code.index(marker)
    a = x = y = 0
    zp = bytearray(256)
    screen: dict[int, int] = {}
    zero = False
    steps = 0
    first_io: int | None = None
    while pc < len(code) and steps < 512:
        steps += 1
        op = code[pc]
        if op in (0xA9, 0xA2, 0xA0):
            value = code[pc + 1]
            if op == 0xA9: a = value
            elif op == 0xA2: x = value
            else: y = value
            zero = value == 0; pc += 2
        elif op in (0xA5, 0xA6, 0xA4):
            value = zp[code[pc + 1]]
            if op == 0xA5: a = value
            elif op == 0xA6: x = value
            else: y = value
            zero = value == 0; pc += 2
        elif op in (0x85, 0x86, 0x84):
            zp[code[pc + 1]] = {0x85: a, 0x86: x, 0x84: y}[op]
            pc += 2
        elif op in (0x8D, 0x8E, 0x8C):
            address = code[pc + 1] | code[pc + 2] << 8
            value = {0x8D: a, 0x8E: x, 0x8C: y}[op]
            if address == 0xD02F:
                first_io = main_vma + pc
                break
            if ROW_BASE <= address < ROW_BASE + 28:
                screen[address] = value
            pc += 3
        elif op == 0x9D:
            address = (code[pc + 1] | code[pc + 2] << 8) + x
            if ROW_BASE <= address < ROW_BASE + 28:
                screen[address] = a
            pc += 3
        elif op == 0x80:
            pc += 2 + _signed(code[pc + 1])
        elif op == 0xD0:
            pc = pc + 2 + (_signed(code[pc + 1]) if not zero else 0)
        elif op == 0xE0:
            zero = x == code[pc + 1]; pc += 2
        elif op == 0xE8:
            x = (x + 1) & 0xFF; zero = x == 0; pc += 1
        elif op == 0xCA:
            x = (x - 1) & 0xFF; zero = x == 0; pc += 1
        elif op == 0x88:
            y = (y - 1) & 0xFF; zero = y == 0; pc += 1
        elif op == 0x8A:
            a = x; zero = a == 0; pc += 1
        else:
            raise SuccessorError(
                f"unsupported opcode ${op:02X} in actual liveness prefix")
    delivered = bytes(screen.get(ROW_BASE + index, 0) for index in range(28))
    require(
        first_io is not None and delivered == MESSAGE + b" " * (28 - len(MESSAGE)),
        "actual packed stager ELF does not deliver STAGING MEDIA before $D02F")
    return {
        "result": "passed-actual-linked-stager-prefix",
        "elf": bind(elf), "main_vma": f"0x{main_vma:04x}",
        "first_io_enable_store": f"0x{first_io:04x}",
        "screen_row": 8, "screen_bytes_hex": delivered.hex(),
        "oracle": "linked-main execution prefix, not source or micro-fixture",
    }


def artifact_mutations() -> list[str]:
    rejected: list[str] = []
    try:
        delivered_liveness_gate(PREDECESSOR_ELF)
    except SuccessorError:
        rejected.append("predecessor-packed-ELF-without-opt-in")
    require(rejected == ["predecessor-packed-ELF-without-opt-in"],
            "packed-ELF delivery mutation survived")
    return rejected


def facts(*, configured: bool = False) -> dict[str, Any]:
    if not configured:
        configure()
    shared = MEDIA.check()
    build_id = BASE.product_build_id()
    library = BASE.library_facts(build_id)
    pair = PAIR.pair_identity(PRODUCT_D81, LIBRARY_D81)
    liveness = delivered_liveness_gate(STAGER_ELF)
    require(
        shared["artifact_count"] == 19
        and shared["canonical_product"] == bind(CARD.MANIFEST)
        and pair["result"] == "same-world-pair"
        and pair["product_build_id"] == f"0x{build_id:08x}"
        and library["D81"] == bind(LIBRARY_D81),
        "successor media/readback/same-world closure red")
    return {"shared": shared, "library": library, "pair": pair,
            "liveness": liveness}


def derive(*, configured: bool = False) -> dict[str, Any]:
    result = facts(configured=configured)
    predecessor = load(PREDECESSOR_RECEIPT)
    require(predecessor["attempt_accounting"]["product_links"] == 0,
            "predecessor media authority drift")
    return {
        "format": FORMAT, "recorded_on": "2026-08-11", "status": STATUS,
        "attempt_accounting": {
            "product_links": 0, "WPLTO_runs": 0,
            "qualification_replays": 0, "cold_stager_compiler_runs": 1,
            "shared_system_builds": 1, "library_builds": 0,
            "media_readbacks": 1, "hardware_runs": 0,
        },
        "authority": {
            "approval": {"commit": "739c5436"},
            "predecessor_first_red_media": bind(PREDECESSOR_RECEIPT),
            "frozen_product_manifest": bind(CARD.MANIFEST),
            "release_contract": bind(BASE.CONTRACT),
            "producer": bind(Path(__file__)),
            "media_engine": bind(ROOT / "tools/host-lisp/c2_lite_media_product.py"),
        },
        "producer_gate": producer_gate(),
        "producer_mutations_rejected": producer_mutations(),
        "actual_packed_ELF_gate": result["liveness"],
        "artifact_mutations_rejected": artifact_mutations(),
        "regenerated_contract_members": {
            "autoboot": bind(STAGER), "boot_id": bind(DESCRIPTOR),
            "candidate_manifest": bind(MANIFEST),
            "product_D81": bind(PRODUCT_D81), "work_D81": bind(WORK_D81),
            "regular_pipeline": True,
        },
        "shared_system": {
            "artifact_count": result["shared"]["artifact_count"],
            "artifact_set_sha256": result["shared"]["artifact_set_sha256"],
            "readback": "passed",
        },
        "library": {"D81": result["library"]["D81"],
                    "rebuilt": False, "readback": "predecessor-bound"},
        "pair_identity": result["pair"],
        "hardware_handoff": {
            "status": "fresh-D1-only",
            "required_visible_signs": [
                "LISP65: STAGING MEDIA", "LISP65: BUILDING HEAP",
                "LISP65: LOADING LIBRARIES"],
            "D2_D5_open": False,
        },
        "claim_limit": (
            "Host/media repair only. Link-97 product bytes are frozen; no "
            "hardware, D1 green, D2-D5, Halt, release or publication claim."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and value.get("attempt_accounting") == {
            "product_links": 0, "WPLTO_runs": 0,
            "qualification_replays": 0, "cold_stager_compiler_runs": 1,
            "shared_system_builds": 1, "library_builds": 0,
            "media_readbacks": 1, "hardware_runs": 0}
        and value.get("actual_packed_ELF_gate", {}).get("result")
            == "passed-actual-linked-stager-prefix"
        and value.get("regenerated_contract_members", {}).get(
            "regular_pipeline") is True
        and value.get("pair_identity", {}).get("result") == "same-world-pair"
        and value.get("hardware_handoff", {}).get("D2_D5_open") is False,
        "successor media claim drift")
    if verify:
        require(value == derive(), "successor media receipt stale")


def receipt_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-product-link": lambda x: x["attempt_accounting"].update(
            product_links=1),
        "claim-WPLTO": lambda x: x["attempt_accounting"].update(WPLTO_runs=1),
        "skip-actual-ELF-gate": lambda x: x["actual_packed_ELF_gate"].update(
            result="source-only"),
        "patch-contract-member": lambda x: x["regenerated_contract_members"].update(
            regular_pipeline=False),
        "cross-world": lambda x: x["pair_identity"].update(result="mismatch"),
        "open-D2-early": lambda x: x["hardware_handoff"].update(D2_D5_open=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate, verify=False)
        except SuccessorError:
            rejected.append(name)
    require(rejected == list(cases), "successor media receipt mutation survived")
    return rejected


def build_action() -> int:
    require(not BUILD.exists() and not RECEIPT.exists(),
            "successor media build is one-shot")
    producer_gate(); producer_mutations()
    frozen_before = bind(CARD.MANIFEST)
    configure()
    shared = MEDIA.build(stager_compile_defines=(OPT_IN,))
    require(shared["artifact_count"] == 19, "successor shared role count drift")
    require(bind(CARD.MANIFEST) == frozen_before,
            "Link-97 product manifest moved during media-only repair")
    value = derive(configured=True); validate(value, verify=False)
    value["mutations_rejected"] = receipt_mutations(value)
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_bytes(canonical(value))
    print("v1.5 stager-liveness media: PASS actual-ELF roles=19 no-link")
    return 0


def fresh_readback() -> None:
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "check"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            "successor media fresh readback red:\n" + result.stdout)
    print(result.stdout.strip())


def check() -> int:
    value = load(RECEIPT); mutations = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(mutations == receipt_mutations(value),
            "successor media receipt mutation set drift")
    print("v1.5 stager-liveness media check: PASS actual-ELF roles=19 no-link")
    return 0


def selftest() -> int:
    require(len(producer_mutations()) == 3,
            "successor producer mutation count drift")
    artifact_mutations()
    print("v1.5 stager-liveness media selftest: PASS source=3 artifact=1")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "check", "selftest"))
    action = parser.parse_args().action
    if action == "build":
        result = build_action(); fresh_readback(); return result
    return {"check": check, "selftest": selftest}[action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SuccessorError, MEDIA.MediaError, RuntimeError, OSError,
            ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"v1.5 stager-liveness media: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
