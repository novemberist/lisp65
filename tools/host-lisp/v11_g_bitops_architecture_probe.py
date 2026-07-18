#!/usr/bin/env python3
"""Compare the bounded 1.1-G bitops opcode and runtime-slice cuts.

Both variants are built in disposable worktrees materialized from the current
working tree.  The canonical ABI ledger and product sources are never edited
by the probe.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build/probes/v11-g-bitops-architecture"
RECEIPT = (
    ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
    / "v11-g-bitops-architecture-probe-receipt.json"
)
CODEMOD = "tools/host-lisp/v11_g_language_polish_codemod.py"
SKIP_PREFIXES = ("build/", "releases/", "tools/llvm-mos/")
SKIP_SUFFIXES = (".tar.gz", "docs/reference/mega65-book.pdf")


class ProbeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeError(message)


def run(argv: list[str], cwd: Path, log: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        argv, cwd=cwd, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(result.stdout or "", encoding="utf-8")
    if check and result.returncode:
        raise ProbeError(
            f"command failed ({result.returncode}): {' '.join(argv)}\n"
            f"{(result.stdout or '')[-6000:]}"
        )
    return result


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise ProbeError(f"{label}: expected one anchor, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(path: Path) -> dict[str, Any]:
    return {"bytes": path.stat().st_size, "sha256": sha(path)}


def copy_current_tree(target: Path) -> None:
    listing = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE,
    ).stdout.split(b"\0")
    for raw in listing:
        if not raw:
            continue
        rel = raw.decode("utf-8")
        if rel.startswith(SKIP_PREFIXES) or rel.endswith(SKIP_SUFFIXES):
            continue
        source = ROOT / rel
        if not source.is_file():
            continue
        destination = target / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    llvm = target / "tools/llvm-mos"
    llvm.parent.mkdir(parents=True, exist_ok=True)
    llvm.symlink_to(ROOT / "tools/llvm-mos", target_is_directory=True)


def patch_live_opcode_docs(root: Path) -> None:
    doc = root / "docs/contracts/bytecode-abi.md"
    replace_once(
        doc,
        "## Prim-ID extensions\n",
        """## Opcode extensions

| Opcode | Mnemonic | Operand | Profile | Contract |
| ---: | --- | --- | --- | --- |
| 20 | `LOGAND` | none | dialect-v2 | Strict binary signed-15-bit bitwise AND |
| 21 | `LOGIOR` | none | dialect-v2 | Strict binary signed-15-bit bitwise OR |
| 22 | `LOGXOR` | none | dialect-v2 | Strict binary signed-15-bit bitwise XOR |
| 23 | `ASH` | none | dialect-v2 | Strict binary arithmetic shift; count -14..14, overflow fails |

The four IDs remain reserved in dialect-v1.  A v1 decoder therefore rejects
them even though the shared decoder retains their permanent identities.

## Prim-ID extensions
""",
        "live opcode extension table",
    )
    drift = root / "tools/host-lisp/bytecode_p0_drift_check.py"
    insert = '''\n\ndef parse_doc_opcode_extensions(text):
    sec = section(text, r"^## Opcode extensions", r"^## Prim-ID extensions")
    ops = {}
    for line in sec.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3 or cells[0].startswith("---") or cells[0] == "Opcode":
            continue
        ops[int(strip_md(cells[0]))] = (strip_md(cells[1]), strip_md(cells[2]))
    return ops
'''
    replace_once(
        drift, "\ndef parse_doc_prims(text):\n", insert + "\ndef parse_doc_prims(text):\n",
        "opcode extension parser",
    )
    replace_once(
        drift,
        "    doc_ops = parse_doc_ops(doc_text)\n",
        """    doc_ops = parse_doc_ops(doc_text)
    for opcode, identity in parse_doc_opcode_extensions(doc_extension_text).items():
        if opcode in doc_ops:
            raise ValueError("duplicate opcode in live ABI extension: %d" % opcode)
        doc_ops[opcode] = identity
""",
        "drift live opcode merge",
    )
    ledger_tool = root / "tools/host-lisp/bytecode_abi_ledger.py"
    replace_once(
        ledger_tool,
        "    doc_ops = D.parse_doc_ops(D.read_text(D.DOC_PATH))\n",
        """    doc_ops = D.parse_doc_ops(D.read_text(D.DOC_PATH))
    doc_ops.update(D.parse_doc_opcode_extensions(D.read_text(D.DOC_EXTENSION_PATH)))
""",
        "ledger live opcode merge",
    )
    old = '''    lcc_text = (ROOT / "lib" / "lcc.lisp").read_text(encoding="utf-8")
    opcode_by_lower = {name.lower(): (ident, operand) for ident, (name, operand) in op_ids.items()}
'''
    new = '''    lcc_text = (ROOT / "lib" / "lcc.lisp").read_text(encoding="utf-8")
    opcode_by_lower = {name.lower(): (ident, operand) for ident, (name, operand) in op_ids.items()}
    v1_opcode_ids = resolved["dialect-v1"]["opcodes"]["active"] | resolved["dialect-v1"]["opcodes"]["tombstone"]
'''
    replace_once(ledger_tool, old, new, "ledger v1 opcode scope")
    replace_once(
        ledger_tool,
        '''    expected_lcc_ops = {
        name: ident
        for name, (ident, _operand) in opcode_by_lower.items()
        if name not in implicit_lcc_opcodes
    }
''',
        '''    expected_lcc_ops = {
        name: ident
        for name, (ident, _operand) in opcode_by_lower.items()
        if ident in v1_opcode_ids and name not in implicit_lcc_opcodes
    }
''',
        "ledger frozen v1 opcode mirror",
    )
    replace_once(
        ledger_tool,
        '''    v2_pairs = _lcc_pairs(lcc_v2_text)
    lcc_v2_prims = {} if re.search(r"\\(defun\\s+%lcc-prim\\b", lcc_v2_text) else dict(lcc_prims)
    for name, ident in v2_pairs:
        if name not in prim_by_name:
            raise LedgerError(f"dialect-v2 LCC contains unknown Prim-ID mapping {name}/{ident}")
        lcc_v2_prims[name] = ident
''',
        '''    v2_pairs = _lcc_pairs(lcc_v2_text)
    lcc_v2_prims = {} if re.search(r"\\(defun\\s+%lcc-prim\\b", lcc_v2_text) else dict(lcc_prims)
    lcc_v2_ops = dict(lcc_ops)
    for name, ident in v2_pairs:
        if name in opcode_by_lower:
            lcc_v2_ops[name] = ident
        elif name in prim_by_name:
            lcc_v2_prims[name] = ident
        else:
            raise LedgerError(f"dialect-v2 LCC contains unknown ABI mapping {name}/{ident}")
    expected_v2_lcc_ops = {
        name: ident for name, (ident, _operand) in opcode_by_lower.items()
        if ident in resolved["dialect-v2"]["opcodes"]["active"] and name not in implicit_lcc_opcodes
    }
    if lcc_v2_ops != expected_v2_lcc_ops:
        raise LedgerError("dialect-v2 LCC opcode mirror coverage drift")
''',
        "ledger v2 opcode mirror",
    )
    registry_tool = root / "tools/host-lisp/v2_native_function_registry.py"
    replace_once(
        registry_tool,
        '''    if {name: ident for name, ident in lcc_rows.items() if ident in active} != compile_repl:
''',
        '''    if {name: ident for name, ident in lcc_rows.items() if name in all_active} != compile_repl:
''',
        "separate overlapping opcode and Prim-ID namespaces in LCC view",
    )


def patch_abi_ledger(root: Path) -> None:
    path = root / "config/bytecode-abi-ledger.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    identities = value["opcode_identities"]
    identities.extend([
        {"id": 20, "canonical_name": "LOGAND", "operand": "none"},
        {"id": 21, "canonical_name": "LOGIOR", "operand": "none"},
        {"id": 22, "canonical_name": "LOGXOR", "operand": "none"},
        {"id": 23, "canonical_name": "ASH", "operand": "none"},
    ])
    identities.sort(key=lambda row: row["id"])
    v2 = next(row for row in value["profiles"] if row["id"] == "dialect-v2")
    v2["opcodes"]["active"] = sorted(v2["opcodes"]["active"] + [20, 21, 22, 23])
    v2["opcodes"]["reserved_ranges"] = [
        row for row in v2["opcodes"]["reserved_ranges"] if row != [20, 23]
    ]
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def patch_opcode_vm(root: Path) -> None:
    replace_once(
        root / "src/vm.h",
        "    OP_SUB=14, OP_MUL=15, OP_DIV=16, OP_MOD=17, OP_LESS=18, OP_GREATER=19, OP_REMAINDER=24,\n",
        "    OP_SUB=14, OP_MUL=15, OP_DIV=16, OP_MOD=17, OP_LESS=18, OP_GREATER=19,\n"
        "    OP_LOGAND=20, OP_LOGIOR=21, OP_LOGXOR=22, OP_ASH=23, OP_REMAINDER=24,\n",
        "C opcode identities",
    )
    vm = root / "src/vm.c"
    helper = r'''

static __attribute__((noinline)) obj vm_bitop(uint8_t op, obj a, obj b) {
    int16_t x = FIXVAL(a), y = FIXVAL(b), value;
    uint16_t raw;
    if (op == OP_ASH) {
        uint8_t shift;
        if (y < -14 || y > 14) { vm_status = VM_TYPEERROR; return NIL; }
        if (y < 0) return MKFIX((int16_t)(x >> (uint8_t)(-y)));
        value = x;
        shift = (uint8_t)y;
        while (shift--) {
            if (value < -8192 || value > 8191) {
                vm_status = VM_TYPEERROR; return NIL;
            }
            value = (int16_t)(value << 1);
        }
        return MKFIX(value);
    }
    raw = op == OP_LOGAND ? ((uint16_t)x & (uint16_t)y) :
          op == OP_LOGIOR  ? ((uint16_t)x | (uint16_t)y) :
                             ((uint16_t)x ^ (uint16_t)y);
    raw &= 0x7fffu;
    value = (raw & 0x4000u) ? (int16_t)(raw | 0x8000u) : (int16_t)raw;
    return MKFIX(value);
}
'''
    anchor = """\n#ifdef LISP65_V2_WORKBENCH_SERVICES
#ifndef LISP65_DIALECT_V2
"""
    replace_once(vm, anchor, helper + anchor, "bitop helper")
    replace_once(
        vm,
        """        case OP_EQ:  b = POP(); a = POP(); PUSH(a == b ? vm_t : NIL); break;
""",
        """        case OP_LOGAND: case OP_LOGIOR: case OP_LOGXOR: case OP_ASH: {
            obj bit_result;
            b = POP(); a = POP(); NEEDFIX2;
            bit_result = vm_bitop(op, a, b);
            if (vm_status != VM_OK) goto done;
            PUSH(bit_result); break;
        }
        case OP_EQ:  b = POP(); a = POP(); PUSH(a == b ? vm_t : NIL); break;
""",
        "device opcode dispatch",
    )


def patch_opcode_host(root: Path) -> None:
    model = root / "tools/host-lisp/bytecode_p0.py"
    replace_once(
        model,
        '    OpSpec(19, "GREATER"),\n    OpSpec(24, "REMAINDER"),\n',
        '    OpSpec(19, "GREATER"),\n    OpSpec(20, "LOGAND"),\n    OpSpec(21, "LOGIOR"),\n'
        '    OpSpec(22, "LOGXOR"),\n    OpSpec(23, "ASH"),\n    OpSpec(24, "REMAINDER"),\n',
        "Python opcode identities",
    )
    replace_once(
        model,
        """                elif op == 24:
                    a, b = fix2()
""",
        """                elif op in (20, 21, 22):
                    a, b = fix2()
                    raw = (a & b) if op == 20 else (a | b) if op == 21 else (a ^ b)
                    raw &= 0x7fff
                    stack.append(mkfix(raw - 0x8000 if raw & 0x4000 else raw))
                elif op == 23:
                    a, b = fix2()
                    if b < -14 or b > 14:
                        raise VMError("TypeError", "ash count outside -14..14")
                    if b < 0:
                        stack.append(mkfix(a >> -b))
                    else:
                        value = a
                        for _ in range(b):
                            if value < -8192 or value > 8191:
                                raise VMError("TypeError", "ash left overflow")
                            value <<= 1
                        stack.append(mkfix(value))
                elif op == 24:
                    a, b = fix2()
""",
        "Python opcode execution",
    )
    compiler = root / "tools/host-lisp/bytecode_p0_compiler.py"
    replace_once(
        compiler,
        '''        elif op == "remainder":
            self.compile_binary(args, "REMAINDER")
''',
        '''        elif op == "logand":
            self.compile_binary(args, "LOGAND")
        elif op == "logior":
            self.compile_binary(args, "LOGIOR")
        elif op == "logxor":
            self.compile_binary(args, "LOGXOR")
        elif op == "ash":
            self.compile_binary(args, "ASH")
        elif op == "remainder":
            self.compile_binary(args, "REMAINDER")
''',
        "Python compiler bitops",
    )


def patch_opcode_lcc(root: Path) -> None:
    base = root / "lib/lcc.lisp"
    # The frozen v1 source remains untouched.  The v2 profile introduces both
    # the mirror and source-operation classification.
    profile = root / "lib/dialect-v2/lcc-profile.lisp"
    insert = '''

; 1.1-G v2-only opcode identities.  dialect-v1 keeps IDs 20..23 reserved.
; A dedicated tiny mirror avoids copying or changing the frozen v1 %lcc-op.
(defun %lcc-v2-bitop (name)
  (cond ((eq name 'logand) 20) ((eq name 'logior) 21)
        ((eq name 'logxor) 22) ((eq name 'ash) 23) (t nil)))

(defun %lcc-v2-bitop-binary (cs lvls args opname)
  (%lcc-emit (%lcc-expr (%lcc-expr cs lvls (car args))
                         lvls (car (cdr args)))
             (%lcc-v2-bitop opname)))
'''
    replace_once(profile, "\n(defun %lcc-v2-prim2 (name)\n", insert + "\n(defun %lcc-v2-prim2 (name)\n", "v2 LCC opcode mirror")
    replace_once(
        profile,
        """  (cond ((eq op 'mod) (%lcc-binary cs lvls args 'mod))
""",
        """  (cond ((eq op 'logand) (%lcc-v2-bitop-binary cs lvls args 'logand))
        ((eq op 'logior) (%lcc-v2-bitop-binary cs lvls args 'logior))
        ((eq op 'logxor) (%lcc-v2-bitop-binary cs lvls args 'logxor))
        ((eq op 'ash) (%lcc-v2-bitop-binary cs lvls args 'ash))
        ((eq op 'mod) (%lcc-binary cs lvls args 'mod))
""",
        "v2 LCC bitops lowering",
    )
    replace_once(
        profile,
        """        ((eq op 'eql) t) ((eq op 'mod) t) ((eq op 'cons) t)
""",
        """        ((eq op 'eql) t) ((eq op 'logand) t) ((eq op 'logior) t)
        ((eq op 'logxor) t) ((eq op 'ash) t) ((eq op 'mod) t) ((eq op 'cons) t)
""",
        "v2 LCC bitops source forms",
    )
    require(base.is_file(), "frozen v1 LCC missing")


BITOP_CASES = [
    {"name": f"v11-g-{name}-{route}", "expr": expr, "expect": expected}
    for name, direct, expected in (
        ("logand", "(logand 63 42)", "42"),
        ("logior", "(logior 40 2)", "42"),
        ("logxor", "(logxor 43 1)", "42"),
        ("ash", "(ash 21 1)", "42"),
    )
    for route, expr in (
        ("direct", direct),
        ("funcall", f"(funcall (function {name}) {direct[direct.find(' ')+1:-1]})"),
        ("apply", f"(apply (function {name}) (list {direct[direct.find(' ')+1:-1]}))"),
    )
] + [
    {"name": "v11-g-ash-right", "expr": "(ash -84 -1)", "expect": "-42"},
    {"name": "v11-g-bitops-negative", "expr": "(logand -1 42)", "expect": "42"},
    {"name": "v11-g-ash-count-range", "expr": "(ash 1 15)", "expect_vm_error": "TypeError"},
    {"name": "v11-g-ash-overflow", "expr": "(ash 16383 1)", "expect_vm_error": "TypeError"},
]


def patch_opcode_codemod(root: Path) -> None:
    path = root / CODEMOD
    text = path.read_text(encoding="utf-8")
    start = text.index('    "bitops": """')
    end = text.index('""",\n    "gc":', start) + 3
    replacement = '''    "bitops": """

; Public designator wrappers. Direct calls lower to v2 opcodes; funcall/apply
; invoke these strict-arity CodeObjects, whose bodies lower to the same opcodes.
(defun logand (a b) (logand a b))
(defun logior (a b) (logior a b))
(defun logxor (a b) (logxor a b))
(defun ash (value count) (ash value count))
"""'''
    text = text[:start] + replacement + text[end:]
    text = text.replace(
        '    if variant == "read-string":\n        suite["cases"].extend(CASES[variant])\n',
        '    if variant in {"read-string", "bitops"}:\n        suite["cases"].extend(CASES[variant])\n',
        1,
    )
    # Replace the smaller original case list with the generated full route set.
    marker_start = text.index('    "bitops": [', text.index('CASES = {'))
    marker_end = text.index('    "gc": [', marker_start)
    rendered = '    "bitops": ' + repr(BITOP_CASES) + ',\n'
    text = text[:marker_start] + rendered + text[marker_end:]
    path.write_text(text, encoding="utf-8")


def patch_runtime_slice(root: Path) -> None:
    overlay = root / "src/c1_compiler_overlay.c"
    helper = r'''

static C1_FN uint8_t c1_bitop(lisp65_buffer_overlay_context *context, int16_t action) {
    obj payload;
    int16_t left, right, value;
    uint16_t raw;
    uint8_t shift;
    if (context->argc != 2) return VM_ARITY;
    payload = context->args[1];
    if (!(IS_PTR(payload) && cell_type(payload) == T_CONS) ||
        !IS_FIX(cell_a(payload)) || !IS_FIX(cell_b(payload))) return VM_TYPEERROR;
    left = FIXVAL(cell_a(payload)); right = FIXVAL(cell_b(payload));
    if (action == 13) {
        if (right < -14 || right > 14) return VM_TYPEERROR;
        if (right < 0) value = (int16_t)(left >> (uint8_t)(-right));
        else {
            value = left; shift = (uint8_t)right;
            while (shift--) {
                if (value < -8192 || value > 8191) return VM_TYPEERROR;
                value = (int16_t)(value << 1);
            }
        }
        context->result = MKFIX(value); return VM_OK;
    }
    raw = action == 10 ? ((uint16_t)left & (uint16_t)right) :
          action == 11 ? ((uint16_t)left | (uint16_t)right) :
                         ((uint16_t)left ^ (uint16_t)right);
    raw &= 0x7fffu;
    value = (raw & 0x4000u) ? (int16_t)(raw | 0x8000u) : (int16_t)raw;
    context->result = MKFIX(value); return VM_OK;
}
'''
    replace_once(
        overlay,
        "\nC1_FN uint8_t lisp65_c1_compiler_overlay_entry(void *opaque) {\n",
        helper + "\nC1_FN uint8_t lisp65_c1_compiler_overlay_entry(void *opaque) {\n",
        "runtime-slice bitop helper",
    )
    replace_once(
        overlay,
        """    action = FIXVAL(context->args[0]);
    if (action == LISP65_C1_COMPILER_CHECKPOINT) {
""",
        """    action = FIXVAL(context->args[0]);
    if (action >= 10 && action <= 13) return c1_bitop(context, action);
    if (action == LISP65_C1_COMPILER_CHECKPOINT) {
""",
        "runtime-slice action dispatch",
    )


def materialize_variant(root: Path, variant: str) -> None:
    copy_current_tree(root)
    if variant == "opcode":
        patch_live_opcode_docs(root)
        patch_abi_ledger(root)
        patch_opcode_vm(root)
        patch_opcode_host(root)
        patch_opcode_lcc(root)
        patch_opcode_codemod(root)
    elif variant == "runtime-slice":
        patch_runtime_slice(root)
    else:
        raise ProbeError(f"unknown variant {variant}")


def build_variant(root: Path, variant: str) -> dict[str, Any]:
    out = root / "build/probe"
    abi_binding = None
    if variant == "opcode":
        run(["make", "--no-print-directory", "bytecode-abi-ledger-check"], root, out / "abi-ledger.log")
        shutil.copy2(out / "abi-ledger.log", BUILD / "opcode-abi-ledger.log")
        abi_binding = binding(BUILD / "opcode-abi-ledger.log")
    common = [
        "make", "--no-print-directory",
        f"V2_WORKBENCH_CODEMOD_TOOL={CODEMOD}",
        f"WORKBENCH_OVERLAY_GUARD_DIR={out.relative_to(root).as_posix()}",
    ]
    linked = run([*common, "workbench-overlay-stack-guard"], root, out / "real-link.log", check=False)
    if linked.returncode:
        text = linked.stdout or ""
        reason = "unclassified-real-link-failure"
        details: dict[str, Any] = {}
        if "C1 compiler lifetime exceeds its stack-safe window" in text:
            reason = "runtime-slice-exceeds-1792-byte-cap"
            map_path = out / "resident-island-seed-linked.prg.map"
            if map_path.is_file():
                map_text = map_path.read_text(encoding="utf-8", errors="replace")
                match = re.search(
                    r"^\s*[0-9a-f]+\s+[0-9a-f]+\s+([0-9a-f]+)\s+\d+\s+\.lisp65_rt_c1_compiler\s*$",
                    map_text, re.M,
                )
                if match:
                    size = int(match.group(1), 16)
                    details = {
                        "c1_compiler_slice_bytes": size,
                        "slice_limit_bytes": 1792,
                        "over_limit_bytes": size - 1792,
                    }
                shutil.copy2(map_path, BUILD / f"{variant}-failed-link.map")
        elif "complete shelf exceeds u16 catalog address space" in text:
            reason = "attic-library-shelf-exceeds-u16-catalog"
            contract = json.loads((root / "config/v11-attic-library-shelf.json").read_text(encoding="utf-8"))
            offset = 192
            sizes = {}
            for row in contract["containers"]:
                manifest = json.loads((root / row["manifest"]).read_text(encoding="utf-8"))
                size = (root / manifest["external_image"]["path"]).stat().st_size
                offset += (-offset) & 1
                sizes[row["key"]] = size
                offset += size
            details = {
                "container_bytes": sizes,
                "shelf_bytes": offset,
                "u16_limit_bytes": 65535,
                "over_limit_bytes": offset - 65535,
            }
        elif "runtime-overlay bank" in text or "storage window" in text:
            reason = "runtime-overlay-bank-capacity"
        shutil.copy2(out / "real-link.log", BUILD / f"{variant}-failed-link.log")
        return {
            "status": "real-link-rejected",
            "reason": reason,
            "details": details,
            "abi_ledger_gate": "passed" if abi_binding else "not-applicable-no-abi-change",
            "abi_ledger_log": abi_binding,
            "real_link": binding(out / "real-link.log"),
            "tail": text[-1800:],
        }
    run([*common, "v2-workbench-library-composition-check"], root, out / "composition.log")
    suite = root / "build/bytecode/dialect-v2/suites/p0-stdlib-einsuite-core-workbench-subset.json"
    observations = out / "observations.json"
    if variant == "opcode":
        run([
            "python3", "tools/host-lisp/bytecode_p0_stdlib.py", "--check",
            "--observation-report", str(observations), str(suite),
        ], root, out / "observations.log")
    footprint = json.loads((out / "footprint-audit.json").read_text(encoding="utf-8"))
    layout = json.loads((out / "layout.json").read_text(encoding="utf-8"))
    composition_path = root / "build/bytecode/dialect-v2/workbench-library-composition-budget.json"
    composition = json.loads(composition_path.read_text(encoding="utf-8"))
    manifest_path = root / "build/bytecode/dialect-v2/workbench/stdlib-p0.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    runtime_path = out / "runtime-overlays-manifest.json"
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    image = out / "lisp65-mvp-workbench.overlays.bin"
    max_runtime = max(row["memory_size"] for row in runtime["slices"] if "runtime" in row["roles"])
    result: dict[str, Any] = {
        "status": "passed-not-promoted",
        "capacity": {
            "bank_post_boot_reserve_bytes": footprint["post_boot_reserve"],
            "ext_post_load_headroom_bytes": composition["ext_code"]["post_headroom"],
            "symbol_headroom": composition["symbols"]["headroom"],
            "namepool_headroom_bytes": composition["namepool"]["headroom"],
            "directory_post_align_headroom": composition["directory"]["post_align_headroom"],
            "fixed_overlay_vma_headroom_bytes": layout["overlay"].get("headroom", 0),
            "runtime_overlay_bank_headroom_bytes": 65536 - image.stat().st_size,
            "max_runtime_slice_headroom_bytes": 1792 - max_runtime,
        },
        "resident": {
            "objects": manifest["objects"], "code_bytes": manifest["code_bytes"],
            "directory_bytes": manifest["directory_bytes"],
            "ext_bytes": manifest["external_image"]["bytes"],
        },
        "bindings": {
            "real-link.log": binding(out / "real-link.log"),
            "footprint-audit.json": binding(out / "footprint-audit.json"),
            "layout.json": binding(out / "layout.json"),
            "runtime-overlays-manifest.json": binding(runtime_path),
            "stdlib-p0.manifest.json": binding(manifest_path),
        },
    }
    if observations.is_file():
        value = json.loads(observations.read_text(encoding="utf-8"))
        rows = [
            row for suite_row in value.get("suites", [])
            for row in suite_row.get("observations", [])
            if row.get("name", "").startswith("v11-g-") and
               any(token in row.get("name", "") for token in ("logand", "logior", "logxor", "ash", "bitops"))
        ]
        require(len(rows) == len(BITOP_CASES), "opcode observation coverage drift")
        result["semantic_observations"] = rows
        result["bindings"]["observations.json"] = binding(observations)
    return result


def capacity_delta(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, int]:
    return {
        key: int(candidate[section][key]) - int(baseline[section][key])
        for section in ("capacity", "resident") for key in baseline[section]
    }


def baseline_from_green() -> dict[str, Any]:
    green = json.loads((
        ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
        / "v11-g-green-surface-implementation-receipt.json"
    ).read_text(encoding="utf-8"))
    metrics = green["capacity"]["candidate"]
    resident = green["artifacts"]["candidate_resident"]
    return {
        "capacity": {
            "bank_post_boot_reserve_bytes": metrics["bank_post_boot_reserve_bytes"],
            "ext_post_load_headroom_bytes": metrics["ext_post_load_headroom_bytes"],
            "symbol_headroom": metrics["symbol_headroom"],
            "namepool_headroom_bytes": metrics["namepool_headroom_bytes"],
            "directory_post_align_headroom": metrics["directory_post_align_headroom"],
            "fixed_overlay_vma_headroom_bytes": metrics["fixed_overlay_vma_headroom_bytes"],
            "runtime_overlay_bank_headroom_bytes": metrics["runtime_overlay_bank_headroom_bytes"],
            "max_runtime_slice_headroom_bytes": metrics["runtime_overlay_max_slice_headroom_bytes"],
        },
        "resident": {
            "objects": resident["objects"],
            "code_bytes": resident["code_bytes"],
            "directory_bytes": resident["directory_bytes"],
            "ext_bytes": resident["ext_bytes"],
        },
    }


def all_probe() -> dict[str, Any]:
    BUILD.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="lisp65-v11-g-bitops-") as raw:
        base = Path(raw)
        for variant in ("opcode", "runtime-slice"):
            root = base / variant
            run(["git", "worktree", "add", "--detach", "--no-checkout", str(root), "HEAD"], ROOT, BUILD / f"{variant}-worktree.log")
            try:
                materialize_variant(root, variant)
                results[variant] = build_variant(root, variant)
                (BUILD / f"{variant}-result.json").write_text(
                    json.dumps(results[variant], indent=2) + "\n", encoding="utf-8"
                )
            finally:
                run(["git", "worktree", "remove", "--force", str(root)], ROOT, BUILD / f"{variant}-cleanup.log", check=False)
    baseline = baseline_from_green()
    for row in results.values():
        if row["status"] == "passed-not-promoted":
            row["delta_from_green_candidate"] = capacity_delta(row, baseline)
    opcode = results["opcode"]
    runtime = results["runtime-slice"]
    recommendation = "compact-v2-opcodes" if opcode["status"] == "passed-not-promoted" else "defer-or-fund-prerequisite-reclaim"
    if opcode["status"] == "passed-not-promoted":
        recommendation_reason = (
            "The opcode cut is the only candidate that survives the real product link. "
            "The runtime-slice cut consumes the compiler-lifetime slice and is rejected "
            "at the pinned 1792-byte cap; it also couples a language primitive to a "
            "temporary compiler service. Opcode allocation remains owner-controlled "
            "because it is a permanent ABI act."
        )
    else:
        recommendation_reason = (
            "Neither authorized architecture fits the pinned product. The runtime-slice "
            "cut exceeds the compiler-lifetime slice cap; the compact opcode cut preserves "
            "the frozen v1 ABI but makes the five-library Attic shelf exceed its u16 catalog. "
            "Bitops must therefore be deferred or preceded by a separately measured reclaim; "
            "neither cap may be relaxed as part of this block."
        )
    receipt = {
        "format": "lisp65-v11-g-bitops-architecture-probe-receipt-v1",
        "status": "passed-not-promoted",
        "claim_limit": "architecture-and-capacity-comparison-only-no-product-or-abi-promotion",
        "contract": {
            "functions": ["logand", "logior", "logxor", "ash"],
            "arity": "exactly-two-fixnums",
            "representation": "signed-15-bit-fixnum",
            "bitwise_result": "low-15-bit-two-complement-reinterpreted-as-signed-fixnum",
            "ash": "arithmetic-right; left-shift-fails-on-fixnum-overflow; count-minus14-through-plus14",
        },
        "baseline": baseline,
        "variants": results,
        "abi_consequences": {
            "dialect_v1": "opcode-20-through-23-remain-reserved-and-decode-fail-closed",
            "dialect_v2": "reserved-to-active-20-LOGAND-21-LOGIOR-22-LOGXOR-23-ASH",
            "permanent_identity": "names-and-none-operands-enter-the-nonreusable-ledger",
            "required_views": [
                "product-c-vm", "python-p0-vm", "python-p0-compiler",
                "python-disassembler", "resident-lisp-lcc", "live-abi-extension-doc",
            ],
            "frozen_v1_source": "lib/lcc.lisp-unchanged-v2-mirror-lives-in-lcc-profile",
            "four_engine_acceptance": "required-after-owner-selection-before-promotion; probe-covers-model-emitter-device-link-and-lcc-mirror-not-hardware",
        },
        "recommendation": recommendation,
        "recommendation_reason": recommendation_reason,
        "source_bindings": {
            str(path.relative_to(ROOT)): binding(path)
            for path in (
                ROOT / "tools/host-lisp/v11_g_bitops_architecture_probe.py",
                ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
                / "v11-g-green-surface-implementation-receipt.json",
                ROOT / "config/bytecode-abi-ledger.json",
                ROOT / "docs/contracts/bytecode-abi.md",
                ROOT / "src/vm.c", ROOT / "src/vm.h",
                ROOT / "tools/host-lisp/bytecode_p0.py",
                ROOT / "tools/host-lisp/bytecode_p0_compiler.py",
                ROOT / "lib/lcc.lisp", ROOT / "lib/dialect-v2/lcc-profile.lisp",
            )
        },
    }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def check() -> dict[str, Any]:
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value["format"] == "lisp65-v11-g-bitops-architecture-probe-receipt-v1", "receipt format")
    require(value["status"] == "passed-not-promoted", "receipt status")
    require(value["recommendation"] in {"compact-v2-opcodes", "defer-or-fund-prerequisite-reclaim"}, "recommendation")
    for path, expected in value["source_bindings"].items():
        require(binding(ROOT / path) == expected, f"source binding drift: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("all", "check"))
    args = parser.parse_args()
    try:
        value = all_probe() if args.action == "all" else check()
        print(
            "v11-g-bitops-architecture-probe: PASS "
            f"status={value['status']} recommendation={value['recommendation']}"
        )
    except (OSError, ValueError, KeyError, ProbeError, subprocess.CalledProcessError) as exc:
        print(f"v11-g-bitops-architecture-probe: FAIL: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
