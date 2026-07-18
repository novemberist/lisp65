#!/usr/bin/env python3
"""Build and verify the bounded 1.1-G language-polish probes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build/probes/v11-g"
RECEIPT = (
    ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
    / "v11-g-language-polish-probe-receipt.json"
)
CODEMOD = "tools/host-lisp/v11_g_language_polish_codemod.py"
VARIANTS = ("baseline", "bitops", "gc", "room", "read-string", "restart", "tick")
DEFAULT_SRCS = tuple(
    path for path in sorted((ROOT / "src").glob("*.c"))
    if path.name not in {"vm.c", "compile.c", "compile_repl.c"}
)


class ProbeError(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeError(message)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ProbeError(f"{path}: JSON root must be an object")
    return value


def _run(argv: list[str], *, env: dict[str, str], log: Path) -> None:
    result = subprocess.run(
        argv, cwd=ROOT, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(result.stdout or "", encoding="utf-8")
    if result.returncode:
        raise ProbeError(
            f"command failed ({result.returncode}): {' '.join(argv)}\n"
            f"{(result.stdout or '')[-6000:]}"
        )


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    if source.count(old) != 1:
        raise ProbeError(f"{label}: expected one patch anchor, found {source.count(old)}")
    return source.replace(old, new, 1)


PROBE_HANDLER = r'''
#if defined(LISP65_V11_G_BITOPS_PROBE) || \
    defined(LISP65_V11_G_GC_PROBE) || \
    defined(LISP65_V11_G_ROOM_PROBE) || \
    defined(LISP65_V11_G_RESTART_PROBE)
static __attribute__((noinline)) obj vm_v11_g_probe(int16_t action, obj payload) {
#ifdef LISP65_V11_G_BITOPS_PROBE
    if (action >= 10 && action <= 13) {
        int16_t left, right, value;
        uint16_t raw;
        if (!(IS_PTR(payload) && cell_type(payload) == T_CONS) ||
            !IS_FIX(cell_a(payload)) || !IS_FIX(cell_b(payload))) {
            vm_status = VM_TYPEERROR; return NIL;
        }
        left = FIXVAL(cell_a(payload)); right = FIXVAL(cell_b(payload));
        if (action == 10) raw = (uint16_t)left & (uint16_t)right;
        else if (action == 11) raw = (uint16_t)left | (uint16_t)right;
        else if (action == 12) raw = (uint16_t)left ^ (uint16_t)right;
        else {
            uint8_t shift;
            if (right < -14 || right > 14) { vm_status = VM_TYPEERROR; return NIL; }
            if (right < 0) value = (int16_t)(left >> (uint8_t)(-right));
            else {
                value = left; shift = (uint8_t)right;
                while (shift--) {
                    if (value < -8192 || value > 8191) {
                        vm_status = VM_TYPEERROR; return NIL;
                    }
                    value = (int16_t)(value << 1);
                }
            }
            return MKFIX(value);
        }
        raw &= 0x7fffu;
        value = (raw & 0x4000u) ? (int16_t)(raw | 0x8000u) : (int16_t)raw;
        return MKFIX(value);
    }
#endif
#ifdef LISP65_V11_G_GC_PROBE
    if (action == 20) { gc_collect(); return vm_t; }
#endif
#ifdef LISP65_V11_G_ROOM_PROBE
    if (action == 21) {
        obj result = cons(MKFIX((int16_t)(gc_runs & 0x3fffu)), NIL);
        GC_PUSH(result);
        result = cons(MKFIX((int16_t)mem_free_cells()), gc_rootstack[GC_TOP]);
        GC_POPN(1);
        return result;
    }
#endif
#ifdef LISP65_V11_G_RESTART_PROBE
    if (action == 30) {
#ifdef LISP_REAL_MEM
        __asm__ volatile("jmp ($fffc)");
#endif
        return vm_t;
    }
#endif
    vm_status = VM_TYPEERROR; return NIL;
}
#endif

'''


def _patched_vm(variant: str) -> str:
    source = (ROOT / "src/vm.c").read_text(encoding="utf-8")
    if variant not in {"bitops", "gc", "room", "restart"}:
        return source
    anchor = "static __attribute__((noinline)) obj vm_callprim(uint8_t pid, obj *a, uint8_t n) {\n"
    source = _replace_once(source, anchor, PROBE_HANDLER + anchor, "probe handler")
    old = '''    case 66: /* %c1-control */
#endif
        return vm_buffer_call(pid, a, n);
'''
    macro = {
        "bitops": "LISP65_V11_G_BITOPS_PROBE",
        "gc": "LISP65_V11_G_GC_PROBE",
        "room": "LISP65_V11_G_ROOM_PROBE",
        "restart": "LISP65_V11_G_RESTART_PROBE",
    }[variant]
    new = f'''    case 66: /* %c1-control */
#endif
#ifdef {macro}
        if (n == 2 && IS_FIX(a[0]) && FIXVAL(a[0]) >= 10)
            return vm_v11_g_probe(FIXVAL(a[0]), a[1]);
#endif
        return vm_buffer_call(pid, a, n);
'''
    return _replace_once(source, old, new, "c1-control interception")


def _patched_interrupt(variant: str) -> str:
    source = (ROOT / "src/interrupt.c").read_text(encoding="utf-8")
    if variant != "tick":
        return source
    state = '''
#ifdef LISP65_V11_G_TICK_PROBE
/* Capacity floor only: observe the KERNAL frame source cooperatively.  This
 * does not claim that invoking Lisp from a nested VM poll is safe. */
static uint8_t v11_g_last_jiffy;
static uint16_t v11_g_seen_frames;
static void v11_g_tick_observe(void) {
#ifdef DEVICE
    uint8_t now = *(volatile unsigned char *)0x00a2u;
    if (now != v11_g_last_jiffy) {
        v11_g_last_jiffy = now;
        v11_g_seen_frames++;
    }
#endif
}
#endif

'''
    source = _replace_once(
        source, "void lisp_poll(void) {\n", state + "void lisp_poll(void) {\n",
        "tick state",
    )
    return _replace_once(
        source,
        "void lisp_poll(void) {\n#ifdef DEVICE\n",
        "void lisp_poll(void) {\n#ifdef LISP65_V11_G_TICK_PROBE\n    v11_g_tick_observe();\n#endif\n#ifdef DEVICE\n",
        "tick observation call",
    )


def _materialize_sources(variant: str) -> tuple[Path, tuple[Path, ...]]:
    out = BUILD / "source" / variant
    out.mkdir(parents=True, exist_ok=True)
    vm = out / "vm.c"
    interrupt = out / "interrupt.c"
    vm.write_text(_patched_vm(variant), encoding="utf-8")
    interrupt.write_text(_patched_interrupt(variant), encoding="utf-8")
    sources = tuple(interrupt if path.name == "interrupt.c" else path for path in DEFAULT_SRCS)
    return vm, sources


def _is_expected_vma_rejection(variant: str, log: Path) -> bool:
    if variant not in {"bitops", "room"} or not log.is_file():
        return False
    text = log.read_text(encoding="utf-8")
    return (
        "resident/noinit state overlaps the fixed runtime-overlay VMA" in text
        and ".bss range is" in text
        and ".lisp65_rt_l65c_00 range is" in text
    )


def build(variants: tuple[str, ...] = VARIANTS) -> None:
    restore_env = dict(os.environ)
    restore_env["LISP65_V11_G_VARIANT"] = "baseline"
    try:
        for variant in variants:
            out = BUILD / variant
            vm, sources = _materialize_sources(variant)
            env = dict(os.environ)
            env["LISP65_V11_G_VARIANT"] = "baseline" if variant == "tick" else variant
            macro = {
                "baseline": "",
                "bitops": "-DLISP65_V11_G_BITOPS_PROBE",
                "gc": "-DLISP65_V11_G_GC_PROBE",
                "room": "-DLISP65_V11_G_ROOM_PROBE",
                "read-string": "",
                "restart": "-DLISP65_V11_G_RESTART_PROBE",
                "tick": "-DLISP65_V11_G_TICK_PROBE",
            }[variant]
            common = [
                "make", "--no-print-directory",
                f"V2_WORKBENCH_CODEMOD_TOOL={CODEMOD}",
                f"VM_SRCS={_rel(vm)}",
                "SRCS=" + " ".join(_rel(path) for path in sources),
                f"WORKBENCH_C1_PHASE_PROBE_DEFINES={macro}",
            ]
            try:
                _run(
                    [*common, f"WORKBENCH_OVERLAY_GUARD_DIR={_rel(out)}",
                     "workbench-overlay-stack-guard"],
                    env=env, log=out / "real-link.log",
                )
            except ProbeError:
                if _is_expected_vma_rejection(variant, out / "real-link.log"):
                    continue
                raise
            if variant == "read-string":
                _run(
                    ["python3", "tools/host-lisp/bytecode_p0_stdlib.py", "--check",
                     "--observation-report", str(out / "observations.json"),
                     "build/bytecode/dialect-v2/suites/p0-stdlib-einsuite-core-workbench-subset.json"],
                    env=env, log=out / "observations.log",
                )
            _run(
                [*common, "v2-workbench-library-composition-check"],
                env=env, log=out / "composition.log",
            )
            for source, target in (
                (ROOT / "build/bytecode/dialect-v2/workbench/stdlib-p0.manifest.json", out / "stdlib-p0.manifest.json"),
                (ROOT / "build/bytecode/dialect-v2/workbench-library-composition-budget.json", out / "composition-budget.json"),
            ):
                target.write_bytes(source.read_bytes())
    finally:
        # The probe owns ignored generated files, but never leaves its variant
        # selected after success, an expected red link, or an unexpected stop.
        _run(["python3", CODEMOD], env=restore_env, log=BUILD / "restore.log")


def _variant(name: str) -> dict[str, Any]:
    root = BUILD / name
    log = root / "real-link.log"
    if _is_expected_vma_rejection(name, log):
        text = log.read_text(encoding="utf-8")
        bss = re.search(r"\.bss range is \[0x([0-9A-Fa-f]+), 0x([0-9A-Fa-f]+)\]", text)
        overlay = re.search(
            r"\.lisp65_rt_l65c_00 range is \[0x([0-9A-Fa-f]+),", text
        )
        _require(bss is not None and overlay is not None,
                 f"{name}: missing footprint and unclassified link failure")
        bss_end = int(bss.group(2), 16)
        overlay_start = int(overlay.group(1), 16)
        return {
            "status": "real-link-rejected",
            "failure": "resident-bss-overlaps-fixed-runtime-overlay-vma",
            "bss_end": bss_end,
            "fixed_overlay_vma": overlay_start,
            "overlap_bytes": bss_end - overlay_start,
            "bindings": {
                "real-link.log": {
                    "bytes": log.stat().st_size,
                    "sha256": _sha(log),
                }
            },
        }
    _require((root / "footprint-audit.json").is_file(),
             f"{name}: missing footprint and unclassified link failure")
    footprint = _load(root / "footprint-audit.json")
    layout = _load(root / "layout.json")
    composition = _load(root / "composition-budget.json")
    stdlib = _load(root / "stdlib-p0.manifest.json")
    overlays = _load(root / "runtime-overlays-manifest.json")
    _require(footprint.get("status") == "pass", f"{name}: footprint gate red")
    _require(composition.get("status") == "pass", f"{name}: composition gate red")
    image_bytes = (root / "lisp65-mvp-workbench.overlays.bin").stat().st_size
    installer = next(row for row in overlays["slices"] if row["name"] == "resident-island-installer")
    result = {
        "status": "passed" if name == "baseline" else "passed-not-promoted",
        "capacity": {
            "bank_post_boot_reserve_bytes": int(footprint["post_boot_reserve"]),
            "ext_post_load_headroom_bytes": int(composition["ext_code"]["post_headroom"]),
            "symbol_headroom": int(composition["symbols"]["headroom"]),
            "namepool_headroom_bytes": int(composition["namepool"]["headroom"]),
            "directory_post_align_headroom": int(composition["directory"]["post_align_headroom"]),
            "fixed_overlay_vma_headroom_bytes": int(layout["overlay"].get("headroom", 0)),
            "runtime_overlay_bank_headroom_bytes": 65536 - image_bytes,
            "installer_slice_headroom_bytes": 1792 - int(installer["memory_size"]),
        },
        "resident": {
            "objects": int(stdlib["objects"]),
            "code_bytes": int(stdlib["code_bytes"]),
            "directory_bytes": int(stdlib["directory_bytes"]),
            "ext_bytes": int(stdlib["external_image"]["bytes"]),
        },
        "bindings": {
            filename: {"bytes": (root / filename).stat().st_size, "sha256": _sha(root / filename)}
            for filename in (
                "footprint-audit.json", "layout.json", "composition-budget.json",
                "stdlib-p0.manifest.json", "runtime-overlays-manifest.json",
                "lisp65-workbench-overlay-linked.prg.elf",
            )
        },
    }
    if name == "read-string":
        observations = _load(root / "observations.json")
        rows = [
            row
            for suite in observations.get("suites", [])
            for row in suite.get("observations", [])
            if row.get("name", "").startswith("v11-g-read-from-string-")
        ]
        _require(
            len(rows) == 3
            and {row["name"].rsplit("-", 1)[-1] for row in rows}
            == {"direct", "funcall", "apply"}
            and all(row.get("result") == "42" for row in rows),
            "read-from-string route observations failed",
        )
        result["route_observations"] = rows
        result["bindings"]["observations.json"] = {
            "bytes": (root / "observations.json").stat().st_size,
            "sha256": _sha(root / "observations.json"),
        }
    return result


def _delta(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, int]:
    return {
        key: int(candidate["capacity"][key]) - int(baseline["capacity"][key])
        for key in baseline["capacity"]
    } | {
        "resident_objects": int(candidate["resident"]["objects"]) - int(baseline["resident"]["objects"]),
        "resident_code_bytes": int(candidate["resident"]["code_bytes"]) - int(baseline["resident"]["code_bytes"]),
        "resident_directory_bytes": int(candidate["resident"]["directory_bytes"]) - int(baseline["resident"]["directory_bytes"]),
        "resident_ext_bytes": int(candidate["resident"]["ext_bytes"]) - int(baseline["resident"]["ext_bytes"]),
    }


def check() -> dict[str, Any]:
    rows = {name: _variant(name) for name in VARIANTS}
    baseline = rows["baseline"]
    for name in VARIANTS[1:]:
        if rows[name]["status"] != "real-link-rejected":
            rows[name]["delta_from_baseline"] = _delta(rows[name], baseline)
    receipt = {
        "format": "lisp65-v11-g-language-polish-probe-receipt-v1",
        "status": "passed-not-promoted",
        "claim_limit": "capacity-and-architecture-probe-only-no-product-delivery-claim",
        "cost_interpretation": (
            "Each passing row is an absolute candidate-versus-baseline link. "
            "The probe-private dispatcher is conservative shared integration "
            "overhead, so gc and restart Bank deltas must not be added."
        ),
        "source_bindings": {
            _rel(path): {"bytes": path.stat().st_size, "sha256": _sha(path)}
            for path in (
                ROOT / "src/obj.h",
                ROOT / "src/error_overlay.c",
                ROOT / "config/error-code-contract.json",
                ROOT / "config/v11-g-language-polish-probe.json",
                ROOT / "config/v2-native-function-registry.json",
                ROOT / "docs/planning/development-plan-1.1.md",
            )
        },
        "variants": rows,
        "semantic_results": {
            "bitops": {
                "status": "resident-c-callprim-cut-rejected",
                "public_contract": "strict-binary-fixnum logand/logior/logxor and bounded ash",
                "next_architecture": "compact-vm-opcodes-or-funded-runtime-slice",
                "peekw_pokew": "design-stop-current-fixnum-cannot-represent-full-u16",
            },
            "introspection": {
                "gc": "real-link-passed-not-promoted",
                "read_from_string": "probe-viable-by-existing-reader-composition",
                "room": "resident-list-result-cut-rejected-contract-needs-counter-range-decision",
                "error": "design-stop-dynamic-user-payload-not-representable-in-current-numeric-error-context",
            },
            "tick_hook": {
                "status": "lower-bound-only-not-a-hook-candidate",
                "measured_part": "cooperative-kernal-jiffy-observation",
                "blocker": "calling-lisp-from-nested-vm-poll-is-not-reentrancy-safe-and-no-hook-scheduling-contract-is-pinned",
            },
            "restart_repl": {
                "status": "probe-viable-hardware-proof-required",
                "mechanism": "non-returning-indirect-jump-through-reset-vector-fffc",
                "required_acceptance": "attic-restage-and-repl-after-soft-reset-with-m65d-media-unchanged",
            },
        },
        "decisions_required": [
            "peekw/pokew representation or tombstone",
            "error payload contract (symbol, string, or stable user code)",
            "room result and counter overflow contract",
            "tick-hook scheduling/reentrancy contract",
        ],
    }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def selftest() -> None:
    original_vm = (ROOT / "src/vm.c").read_text(encoding="utf-8")
    original_interrupt = (ROOT / "src/interrupt.c").read_text(encoding="utf-8")
    for variant in VARIANTS:
        vm = _patched_vm(variant)
        interrupt = _patched_interrupt(variant)
        _require("vm_v11_g_probe" in vm if variant in {"bitops", "gc", "room", "restart"} else vm == original_vm,
                 f"{variant}: VM patch selftest")
        _require("v11_g_tick_observe" in interrupt if variant == "tick" else interrupt == original_interrupt,
                 f"{variant}: interrupt patch selftest")
    # Probe-model checks only.  They protect the source transform against a
    # transcription error; they are deliberately not product evidence.
    def fix15(value: int) -> int:
        value &= 0x7fff
        return value - 0x8000 if value & 0x4000 else value
    _require(fix15(63 & 42) == 42, "logand model")
    _require(fix15(40 | 2) == 42, "logior model")
    _require(fix15(43 ^ 1) == 42, "logxor model")
    _require((21 << 1) == 42 and (84 >> 1) == 42, "ash model")
    print("v11-g-language-polish-probe: SELFTEST PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("selftest", "build", "check", "all"))
    parser.add_argument("--variant", action="append", choices=VARIANTS)
    args = parser.parse_args()
    try:
        if args.action in {"selftest", "all"}:
            selftest()
        if args.action in {"build", "all"}:
            build(tuple(args.variant) if args.variant else VARIANTS)
        if args.action in {"check", "all"}:
            receipt = check()
            print(
                "v11-g-language-polish-probe: PASS "
                f"variants={len(receipt['variants'])} status={receipt['status']}"
            )
    except (OSError, ValueError, KeyError, ProbeError, subprocess.CalledProcessError) as exc:
        print(f"v11-g-language-polish-probe: FAIL: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
