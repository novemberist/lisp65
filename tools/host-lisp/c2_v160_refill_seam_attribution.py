#!/usr/bin/env python3
"""Reconstruct the v1.6 `%repl-step` return/refill seam in the host VM."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_stdlib as P  # noqa: E402


COMFORT = ROOT / (
    "build/c2.3/v1.6-display-ownership-device-preparation/library-inputs/"
    "repl-comfort.manifest.json")
V16CORE = ROOT / (
    "build/c2.3/v1.6-display-ownership-device-preparation/library-inputs/"
    "v16core.manifest.json")
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-display-entry-first-red-attribution.json")
ELF = ROOT / (
    "build/c2.3/v1.6-display-ownership-device-preparation/canonical-product/"
    "final/lisp65-c2-substitution-linked.prg.elf")
VM_SOURCE = ROOT / "src/vm.c"
HOST_VM = ROOT / "tools/host-lisp/bytecode_p0.py"
SUITE = ROOT / "tests/bytecode/libs/p0-repl-comfort.json"
OUT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-refill-seam-attribution.json")
VM_CODEBUF = 56
SEAM_PC = 0x45


class SeamError(RuntimeError):
    pass


class SeamReached(Exception):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SeamError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def manifest_directory(heap: B.Heap, path: Path) \
        -> tuple[dict[int, B.CodeObject], dict[int, str]]:
    manifest = load(path)
    blob_path = ROOT / manifest["blob"]
    blob = blob_path.read_bytes()
    require(len(blob) == manifest["code_bytes"]
            and sha(blob) == manifest["blob_sha256"],
            f"manifest/blob drift: {path}")
    patches = {int(row["blob_offset"]): int(row["node"])
               for row in manifest["literal_patches"]}
    directory: dict[int, B.CodeObject] = {}
    names: dict[int, str] = {}
    for entry in manifest["entries"]:
        code = P._patched_code_from_manifest_entry(
            heap, manifest, blob, entry, patches)
        symbol = heap.intern(entry["name"])
        require(symbol not in directory, f"duplicate function: {entry['name']}")
        directory[symbol] = code
        names[id(code)] = entry["name"]
    return directory, names


class SeamTrace:
    """Model the linked 56-byte target window over a real host-VM call."""

    def __init__(self, *, fail_refill: bool = False,
                 wrong_window: bool = False) -> None:
        self.fail_refill = fail_refill
        self.wrong_window = wrong_window
        self.owner: int | None = None
        self.win = 0
        self.winlen = 0
        self.streaming = False
        self.frames: list[tuple[str, B.CodeObject]] = []
        self.calls: list[dict[str, Any]] = []
        self.seam: dict[str, Any] | None = None

    @staticmethod
    def capacity(code: B.CodeObject) -> int:
        return VM_CODEBUF - (7 + 2 * len(code.littab))

    def enter(self, name: str, code: B.CodeObject, _args: list[int]) -> None:
        capacity = self.capacity(code)
        require(capacity >= 3, f"header exceeds target window: {name}")
        self.frames.append((name, code))
        self.owner = id(code)
        self.win = 0
        self.winlen = min(len(code.payload), capacity)
        self.streaming = self.winlen < len(code.payload)

    def exit(self, name: str, code: B.CodeObject) -> None:
        require(self.frames and self.frames[-1] == (name, code),
                "host trace frame mismatch")
        self.frames.pop()
        # Target vmr_* globals still describe the callee here.  The caller is
        # restored by BUF_ENSURE_MINE only after the nested return.

    def call(self, caller: str, kind: str, target: str, argc: int,
             pc: int | None = None, resolved: bool = False) -> None:
        self.calls.append({"caller": caller, "kind": kind, "target": target,
                           "argc": argc, "pc": pc, "resolved": resolved})

    def instruction_state(self, name: str, code: B.CodeObject, pc: int,
                          *, operand_depth: int, frame_slots: int) -> None:
        owner_before = self.owner
        restore = owner_before != id(code)
        if restore:
            self.owner = id(code)
            self.win = pc
            self.winlen = 0
            self.streaming = True
        need = min(len(code.payload), pc + 3)
        refill = self.streaming and (
            pc < self.win or self.win + self.winlen < need)
        if refill:
            self.win = pc
            self.winlen = min(len(code.payload) - pc, self.capacity(code))
        if name == "%repl-step" and pc == SEAM_PC:
            require(restore and refill, "seam did not require caller restore/refill")
            start = pc + (1 if self.wrong_window else 0)
            expected = bytes(code.payload[pc:pc + self.winlen])
            observed = bytes(code.payload[start:start + self.winlen])
            success = not self.fail_refill
            exact = success and observed == expected
            self.seam = {
                "logical_pc": pc,
                "owner_before": "nested-callee",
                "owner_after": name,
                "header_bytes": 7 + 2 * len(code.littab),
                "payload_bytes": len(code.payload),
                "window_capacity": self.capacity(code),
                "requested_window": [pc, pc + self.winlen],
                "refill_success": success,
                "expected_sha256": sha(expected),
                "observed_sha256": sha(observed) if success else None,
                "restored_window_exact": exact,
                "operand_depth_before_drop": operand_depth,
                "frame_slots": frame_slots,
            }
            raise SeamReached

    def instruction(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def native_frame(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def native_stack(self, *_args: Any, **_kwargs: Any) -> None:
        pass


def run_world(*, fail_refill: bool = False,
              wrong_window: bool = False) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    suite = P._read_suite(str(SUITE))
    (heap, _names, _code, _entry_flags, _resident_flags, _bundle, directory,
     _cases, _entries, _inliner) = P._compile_suite(suite)
    code_names = {id(code): heap.symbol_name(symbol)
                  for symbol, code in directory.items()
                  if heap.symbolp(symbol)}
    for path in (V16CORE, COMFORT):
        entries, names = manifest_directory(heap, path)
        for symbol, code in entries.items():
            directory[symbol] = code
        code_names.update(names)
    trace = SeamTrace(fail_refill=fail_refill, wrong_window=wrong_window)
    abi_profile, abi_ledger = P._suite_abi(suite)
    vm = B.P0VM(heap=heap, directory=directory, max_steps=200000,
                trace=trace, abi_profile=abi_profile,
                abi_ledger=abi_ledger, private_key_event_modes=True)
    vm.code_names.update(code_names)
    step = directory[heap.intern("%repl-step")]
    try:
        vm.run(step, [B.NIL, heap.string_from_text(""), B.mkfix(0)])
    except SeamReached:
        pass
    require(trace.seam is not None, "host VM did not reach the bound seam")
    return trace.seam, trace.calls


def audit(value: dict[str, Any]) -> None:
    seam = value["host_reconstruction"]
    require(seam["logical_pc"] == 0x45
            and seam["header_bytes"] == 35
            and seam["payload_bytes"] == 220
            and seam["window_capacity"] == 21
            and seam["requested_window"] == [0x45, 0x5A]
            and seam["refill_success"] is True
            and seam["restored_window_exact"] is True
            and seam["operand_depth_before_drop"] == 1,
            "host seam decision drift")
    require(value["decision"]["class"] == "REAL TARGET REFILL FAILURE"
            and value["decision"]["split_calling_convention"] == "EXCLUDED",
            "binary decision drift")


def derive() -> dict[str, Any]:
    first = load(FIRST_RED)
    require(first["status"] ==
            "ATTRIBUTED TO CALLER RETURN/REFILL SEAM; MECHANISM SPLIT OPEN",
            "First-Red predecessor drift")
    seam, calls = run_world()
    require(any(row == {"caller": "%repl-step", "kind": "CALL",
                        "target": "%rl-screen-tail", "argc": 6,
                        "pc": 0x42, "resolved": True} for row in calls),
            "identical nested call was not executed")
    failed, _ = run_world(fail_refill=True)
    wrong, _ = run_world(wrong_window=True)
    require(failed["refill_success"] is False
            and failed["restored_window_exact"] is False,
            "failed-refill control did not separate")
    require(wrong["refill_success"] is True
            and wrong["restored_window_exact"] is False
            and wrong["expected_sha256"] != wrong["observed_sha256"],
            "wrong-window control did not separate")

    value = {
        "format": "lisp65-c2.3-v1.6-refill-seam-attribution-v1",
        "recorded_on": "2026-08-22",
        "status": "ATTRIBUTED: REAL TARGET CALLER REFILL FAILED",
        "inputs": {name: bind(path) for name, path in {
            "first_red": FIRST_RED, "candidate_ELF": ELF,
            "comfort_manifest": COMFORT, "v16core_manifest": V16CORE,
            "host_suite": SUITE,
            "target_VM": VM_SOURCE, "host_VM": HOST_VM,
            "attribution_tool": Path(__file__).resolve(),
        }.items()},
        "identical_call": {"caller": "%repl-step", "call_pc": 0x42,
                           "callee": "%rl-screen-tail", "argc": 6,
                           "return_pc": 0x45},
        "host_reconstruction": seam,
        "controls": {"failed_refill": failed, "wrong_window": wrong},
        "decision": {
            "class": "REAL TARGET REFILL FAILURE",
            "reason": ("the same emitted caller/callee world returns with one operand, "
                       "successfully refills $45..$59 and restores those bytes exactly; "
                       "the stopped target recorded the same requested window plus "
                       "VM_BAD_BYTECODE, so the unresolved bit is the real refill result"),
            "split_calling_convention": "EXCLUDED",
            "wrong_restored_window": "EXCLUDED",
            "code_window_family": "CONFIRMED",
        },
        "permanent_gate_form": {
            "fixture": ("streamed 255-byte caller, 14 literals, 21-byte window, "
                        "nested CALL at $42 and post-return DROP at $45"),
            "claims": ["refill return is success", "restored bytes equal source",
                       "operand depth at $45 is exactly one"],
            "mutations": ["refill returns failure", "successful refill starts at $46",
                          "post-CALL result omitted"],
        },
        "claim_limit": ("Decides the commissioned binary attribution and names the old "
                        "code-window/refill family. It authorizes no fix, card, link, "
                        "medium or device contact."),
    }
    audit(value)
    return value


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in {"check", "write"},
            "usage: c2_v160_refill_seam_attribution.py check|write")
    value = derive()
    encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if sys.argv[1] == "write":
        OUT.write_text(encoded, encoding="utf-8")
    else:
        require(OUT.is_file() and OUT.read_text(encoding="utf-8") == encoded,
                "refill-seam attribution receipt drift")
    print("v1.6 refill seam: PASS refill=success exact=1 depth=1 "
          "target-class=refill-failure")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SeamError, B.VMError, OSError, ValueError, KeyError,
            StopIteration) as error:
        print(f"v1.6 refill seam: FAIL: {error}", file=sys.stderr)
        raise SystemExit(2)
