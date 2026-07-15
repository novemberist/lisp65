#!/usr/bin/env python3
"""Measure the final D68F-to-F011-write window from the linked product."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys


FUNCTION = re.compile(r"^[0-9a-f]+ <([^>]+)>:$")
INSTRUCTION = re.compile(
    r"^\s*([0-9a-f]+):\s+(?:[0-9a-f]{2}\s+)+\s*([a-z0-9]+)(?:\s+([^;]+?))?\s*(?:;.*)?$",
    re.I,
)


class AuditError(RuntimeError):
    pass


def disassemble(objdump: Path, elf: Path) -> dict[str, list[tuple[int, str, str]]]:
    run = subprocess.run(
        [str(objdump), "-d", str(elf)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if run.returncode:
        raise AuditError(f"objdump failed:\n{run.stdout}")
    functions: dict[str, list[tuple[int, str, str]]] = {}
    current: list[tuple[int, str, str]] | None = None
    for raw in run.stdout.splitlines():
        header = FUNCTION.fullmatch(raw.strip())
        if header:
            current = []
            functions[header.group(1)] = current
            continue
        match = INSTRUCTION.match(raw)
        if match and current is not None:
            current.append(
                (int(match.group(1), 16), match.group(2).lower(), (match.group(3) or "").strip().lower())
            )
    return functions


def compact_operand(value: str) -> str:
    return value.replace(" ", "")


def audit(functions: dict[str, list[tuple[int, str, str]]]) -> dict[str, object]:
    guard = functions.get("lisp65_f011_mount_token_op")
    issuer = functions.get("f011_issue_write_guarded")
    if not guard or not issuer:
        raise AuditError("linked product is missing guard/issuer symbols")

    start = next(
        (index for index, (_, op, arg) in enumerate(guard)
         if op == "lda" and compact_operand(arg).startswith("$d68b,x")),
        None,
    )
    if start is None:
        raise AuditError("guard has no ascending D68B..D68F read loop")
    sequence = guard[start:start + 11]
    expected_ops = ["lda", "cmp", "bne", "inx", "cpx", "bne", "pla", "cmp", "bne", "lda", "sta"]
    if [item[1] for item in sequence] != expected_ops:
        raise AuditError("last-token-read to write-trigger instruction sequence drift")
    args = [compact_operand(item[2]) for item in sequence]
    if not args[0].startswith("$d68b,x") or not args[1].endswith(",x"):
        raise AuditError("mount-token compare operands drift")
    if args[4] not in {"#$5", "#5"} or args[7] not in {"#$2", "#2"}:
        raise AuditError("mount-token loop/mode constants drift")
    if args[9] != "#$84" or not args[10].startswith("$d081"):
        raise AuditError("guard no longer issues the F011 write trigger")

    issuer_pairs = [(op, compact_operand(arg)) for _, op, arg in issuer]
    caller_ok = any(
        issuer_pairs[index][0] == "lda"
        and issuer_pairs[index][1] in {"#$2", "#2"}
        and issuer_pairs[index + 1][0] == "jsr"
        and "lisp65_f011_mount_token_op" in issuer_pairs[index + 1][1]
        for index in range(len(issuer_pairs) - 1)
    )
    if not caller_ok:
        raise AuditError("write issuer does not select atomic guard mode 2")

    # Successful final loop iteration, including the D68F read and completion
    # of the D081 store. All indexed operands stay within their source page.
    cycles = [4, 4, 2, 2, 2, 2, 4, 2, 2, 2, 4]
    inclusive = sum(cycles)
    return {
        "format": "lisp65-f011-mount-window-audit-v1",
        "status": "pass-measured-owner-accepted-contract-limit",
        "source": "final-linked-product-disassembly",
        "guard_symbol": "lisp65_f011_mount_token_op",
        "issuer_symbol": "f011_issue_write_guarded",
        "last_token_register": "D68F",
        "write_trigger_register": "D081",
        "cycles_including_last_read_and_trigger_store": inclusive,
        "cycles_after_last_read_completion_through_trigger_store": inclusive - cycles[0],
        "nominal_nanoseconds_at_40_5_mhz": round(inclusive * 1_000_000_000 / 40_500_000, 3),
        "instruction_addresses": {
            "token_read": f"0x{sequence[0][0]:04x}",
            "write_trigger": f"0x{sequence[-1][0]:04x}",
        },
        "preemption_classification": "non-atomic-hypervisor-freezer-can-interpose-at-instruction-boundary",
        "release_consequence": "stock-core-compatible-owner-accepted-known-boundary",
    }


def selftest() -> None:
    good = {
        "lisp65_f011_mount_token_op": [
            (0x1000, "lda", "$d68b,x"), (0x1003, "cmp", "$2000,x"),
            (0x1006, "bne", "$1020"), (0x1008, "inx", ""),
            (0x1009, "cpx", "#$5"), (0x100B, "bne", "$1000"),
            (0x100D, "pla", ""), (0x100E, "cmp", "#$2"),
            (0x1010, "bne", "$1018"), (0x1012, "lda", "#$84"),
            (0x1014, "sta", "$d081"),
        ],
        "f011_issue_write_guarded": [
            (0x2000, "lda", "#$2"),
            (0x2002, "jsr", "$1000 <lisp65_f011_mount_token_op>"),
        ],
    }
    report = audit(good)
    if report["cycles_including_last_read_and_trigger_store"] != 30:
        raise AuditError("cycle-count selftest drift")
    bad = {key: list(value) for key, value in good.items()}
    bad["lisp65_f011_mount_token_op"][-1] = (0x1014, "sta", "$d080")
    try:
        audit(bad)
    except AuditError:
        pass
    else:
        raise AuditError("mutated trigger survived")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--objdump", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        if args.selftest:
            selftest()
            print("f011-mount-window: SELFTEST PASS cases=2")
            return 0
        if not args.elf or not args.objdump or not args.out:
            raise AuditError("--elf, --objdump and --out are required")
        report = audit(disassemble(args.objdump, args.elf))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            "f011-mount-window: PASS cycles=%d release=owner-accepted-contract-limit report=%s"
            % (report["cycles_including_last_read_and_trigger_store"], args.out)
        )
        return 0
    except (AuditError, OSError, UnicodeError) as exc:
        print(f"f011-mount-window: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
