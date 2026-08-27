#!/usr/bin/env python3
"""Price the native-only v1.7 INIT.L65 boot hook.

The study is deliberately host-only.  It compiles a candidate banner in a
temporary directory, target-compiles the three resident seam changes, and
executes one external append over the exact final A0 static-plane geometry.
It never edits a product source and never invokes WPLTO or a product link.
"""

from __future__ import annotations

import argparse
import copy
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

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_stdlib as STD  # noqa: E402
import evidence_era as ERA  # noqa: E402
from c2_product_session_host import (  # noqa: E402
    ProductSessionHost, SessionHostError,
)
from elf_truth import ElfTruth  # noqa: E402


CONTRACT = ROOT / "config/c2-v17-init-l65-pricing-contract.json"
SUITE = ROOT / "tests/bytecode/libs/p0-stdlib-require-resolver.json"
BANNER = ROOT / "lib/repl-banner.lisp"
REPL = ROOT / "src/repl.c"
COMPILE_REPL = ROOT / "src/compile_repl.c"
VM = ROOT / "src/vm.c"
LOAD = ROOT / "lib/stdlib-load.lisp"
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
A0_ROOT = ROOT / "build/c2.3/v1.7-recovery-quiescence-card-r3-a0"
PLANE_ROOT = A0_ROOT / "static-plane/narrow-static"
C2D = PLANE_ROOT / "v6-semantics/initial.c2d-v6.bin"
CODE = PLANE_ROOT / "v6-semantics/bank2-static-code.bin"
MANIFEST = PLANE_ROOT / "stdlib-p0.manifest.json"
A0_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.7-recovery-quiescence-card-r3-a0-receipt.json")
OUT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.7-init-l65-pricing-receipt.json")
CLANG = ROOT / "tools/llvm-mos/bin/mos-clang"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
FORMAT = "lisp65-c2-v17-init-l65-pricing-receipt-v1"
SEALED_COMMIT = "46c2019b"


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def banner_candidate() -> str:
    source = BANNER.read_text(encoding="utf-8")
    needle = "(defun %repl-banner ()\n  (%banner-runs)"
    replacement = (
        "(defun %repl-banner ()\n"
        "  (load \"init.l65\")\n"
        "  (%banner-runs)")
    require(source.count(needle) == 1, "repl-banner seam drift")
    return source.replace(needle, replacement)


def manifest_entry(manifest: dict[str, Any], name: str) -> dict[str, Any]:
    rows = [row for row in manifest["entries"] if row["name"] == name]
    require(len(rows) == 1, f"manifest entry cardinality: {name}")
    return rows[0]


def bank2_price() -> dict[str, Any]:
    accepted = load_json(MANIFEST)
    require(int(accepted["code_bytes"]) == 15491
            and len(CODE.read_bytes()) == 46043,
            "A0 stdlib/static-plane code authority drift")
    old_banner = manifest_entry(accepted, "%repl-banner")
    require(int(old_banner["length"]) == 145,
            "accepted repl-banner size drift")
    suite = STD._read_suite(str(SUITE))
    sources = list(suite["sources"])
    indexes = [index for index, path in enumerate(sources)
               if path.endswith("/lib/repl-banner.lisp")]
    require(len(indexes) == 1, "resolved suite has no unique repl-banner owner")
    with tempfile.TemporaryDirectory(prefix="c2-v17-init-price-") as raw:
        temp = Path(raw)
        candidate_source = temp / "repl-banner.lisp"
        candidate_source.write_text(banner_candidate(), encoding="utf-8")
        candidate_suite = copy.deepcopy(suite)
        candidate_suite["sources"][indexes[0]] = str(candidate_source)
        prefix = temp / "stdlib-p0"
        STD.emit_artifacts(str(SUITE), candidate_suite, str(prefix))
        candidate = load_json(prefix.with_suffix(".manifest.json"))
        new_banner = manifest_entry(candidate, "%repl-banner")
        candidate_blob = (temp / "stdlib-p0.blob.bin").read_bytes()
        banner_at = int(new_banner["blob_offset"])
        banner_end = banner_at + int(new_banner["length"])
        result = {
            "baseline": {
                "objects": int(accepted["objects"]),
                "code_bytes": int(accepted["code_bytes"]),
                "repl_banner_bytes": int(old_banner["length"]),
            },
            "candidate": {
                "objects": int(candidate["objects"]),
                "code_bytes": int(candidate["code_bytes"]),
                "repl_banner_bytes": int(new_banner["length"]),
                "repl_banner_sha256": sha(candidate_blob[banner_at:banner_end]),
            },
        }
    result["delta"] = {
        "objects": result["candidate"]["objects"]
            - result["baseline"]["objects"],
        "code_bytes": result["candidate"]["code_bytes"]
            - result["baseline"]["code_bytes"],
        "repl_banner_bytes": result["candidate"]["repl_banner_bytes"]
            - result["baseline"]["repl_banner_bytes"],
        "new_product_symbol_slots": 0,
        "new_product_name_bytes": 0,
    }
    require(result["delta"] == {
        "objects": 0, "code_bytes": 10, "repl_banner_bytes": 10,
        "new_product_symbol_slots": 0, "new_product_name_bytes": 0,
    }, f"INIT banner price drift: {result['delta']}")
    require(result["candidate"]["repl_banner_bytes"] < 255,
            "candidate banner exceeds bytecode object ceiling")
    return result


PROTOTYPES = r'''
typedef unsigned char u8;
typedef unsigned short obj;
extern u8 vm_status;
extern u8 vm_status_error_code(u8);
extern obj lisp65_error_render_code(u8, obj);
extern void lisp_abort_code(u8);
extern void emit(char);
extern void emit_str(const char *);
extern obj compile_run_top_form(obj);
extern obj read_expr_stream(void);
extern u8 reader_status;
extern char reader_skip_peek(void);
extern void (*crepl_progress)(void);
extern u8 io_disk_load_chain(u8, u8);

__attribute__((noinline, used))
u8 price_banner_old(void) {
  if (vm_status != 0 && vm_status != 1) {
    emit_str("*** ");
    (void)lisp65_error_render_code(vm_status_error_code(vm_status), 0);
    emit('\n');
    return 0;
  }
  return 1;
}
__attribute__((noinline, used))
u8 price_banner_new(void) {
  if (vm_status != 0 && vm_status != 1)
    lisp_abort_code(vm_status_error_code(vm_status));
  return 1;
}
__attribute__((noinline, used))
void price_stream_old(void) {
  for (;;) {
    obj form;
    if (reader_skip_peek() == '\0') return;
    form = read_expr_stream();
    if (reader_status != 0) return;
    compile_run_top_form(form);
    if (crepl_progress) crepl_progress();
  }
}
__attribute__((noinline, used))
void price_stream_new(void) {
  for (;;) {
    obj form;
    if (reader_skip_peek() == '\0') return;
    form = read_expr_stream();
    if (reader_status != 0) return;
    compile_run_top_form(form);
    if (vm_status != 0 && vm_status != 1) return;
    if (crepl_progress) crepl_progress();
  }
}
__attribute__((noinline, used))
obj price_load_old(obj t, obj s) {
  return io_disk_load_chain((u8)(t >> 1), (u8)(s >> 1)) ? 2 : 0;
}
__attribute__((noinline, used))
obj price_load_new(obj t, obj s) {
  if (!io_disk_load_chain((u8)(t >> 1), (u8)(s >> 1)))
    lisp_abort_code(18);
  return 2;
}
'''


def resident_price() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="c2-v17-init-resident-") as raw:
        temp = Path(raw)
        source, obj = temp / "price.c", temp / "price.o"
        source.write_text(PROTOTYPES, encoding="utf-8")
        run = subprocess.run(
            [str(CLANG), "-Os", "-mcpu=mos45gs02", "-c", str(source),
             "-o", str(obj)], cwd=ROOT, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        require(run.returncode == 0,
                "INIT resident micro-compile red:\n" + run.stdout)
        truth = ElfTruth.read(obj, llvm_readobj=READOBJ)
        sizes = {name: truth.symbol(name).bytes for name in (
            "price_banner_old", "price_banner_new", "price_stream_old",
            "price_stream_new", "price_load_old", "price_load_new")}
    old = sizes["price_banner_old"] + sizes["price_stream_old"] \
        + sizes["price_load_old"]
    new = sizes["price_banner_new"] + sizes["price_stream_new"] \
        + sizes["price_load_new"]
    require(new <= old, f"resident target forecast grew: {old} -> {new}")
    return {
        "compiler": bind(CLANG.resolve()),
        "exact_isolated_function_bytes": sizes,
        "old_total_bytes": old,
        "candidate_total_bytes": new,
        "projected_delta_bytes": new - old,
        "implementation_bar": (
            "final linked resident delta <= 0; isolated target prices are a "
            "forecast and confer no byte credit"),
    }


def static_geometry() -> dict[str, int]:
    raw = C2D.read_bytes()
    require(raw[:4] == b"C2D\0" and raw[4] == 6 and len(raw) >= 32,
            "final A0 C2D header drift")
    u16 = lambda at: int.from_bytes(raw[at:at + 2], "little")
    geometry = {
        "generation": u16(10), "images": u16(12),
        "entries": u16(16), "resolutions": u16(20), "roots": u16(24),
        "code_bytes": len(CODE.read_bytes()), "immutable_images": u16(38),
        "catalog_crc32": int.from_bytes(raw[40:44], "little"),
        "build_id": int.from_bytes(raw[44:48], "little"),
    }
    require(geometry["entries"] == 755 and geometry["roots"] == 352
            and geometry["code_bytes"] == 46043,
            f"final A0 geometry drift: {geometry}")
    return geometry


def populate_static_directory(host: ProductSessionHost) -> int:
    manifest = load_json(MANIFEST)
    blob = (ROOT / manifest["blob"]).read_bytes()
    require(sha(blob) == manifest["blob_sha256"], "stdlib blob drift")
    patches = {int(row["blob_offset"]): int(row["node"])
               for row in manifest["literal_patches"]}
    for entry in manifest["entries"]:
        code = STD._patched_code_from_manifest_entry(
            host.heap, manifest, blob, entry, patches)
        symbol = host.heap.intern(entry["name"])
        host.directory[symbol] = code
        host.code_names[id(code)] = entry["name"]
    require(host.heap.intern("list") in host.directory,
            "final static stdlib does not publish list")
    return len(manifest["entries"])


def exact_final_host(geometry: dict[str, Any], out: Path) -> ProductSessionHost:
    host = ProductSessionHost(geometry, out)
    c2d = C2D.read_bytes()
    code = CODE.read_bytes()
    require(len(host.plane.c2d) == len(c2d)
            and len(host.plane.code) >= len(code),
            "Session host cannot hold final A0 plane")
    host.plane.c2d[:] = c2d
    host.plane.code[:len(code)] = code
    require(bytes(host.plane.c2d) == c2d
            and bytes(host.plane.code[:len(code)]) == code,
            "Session host did not consume exact final A0 bytes")
    return host


def reject(label: str, fn: Callable[[], None]) -> dict[str, str]:
    try:
        fn()
    except Exception as exc:  # exact rejection class is itself recorded
        return {"name": label, "result": "rejected",
                "exception": type(exc).__name__}
    raise PricingError(f"negative external-append fixture survived: {label}")


def external_append_gate() -> dict[str, Any]:
    geometry = static_geometry()
    source = "(defun %init-external-proof () (list 17 65))"
    with tempfile.TemporaryDirectory(
            prefix="c2-v17-init-append-", dir=ROOT / "build") as raw:
        host = exact_final_host(geometry, Path(raw) / "positive")
        static_entries = populate_static_directory(host)
        before = {key: int(getattr(host.plane, attr)) for key, attr in (
            ("images", "images"), ("entries", "entries"),
            ("resolutions", "resolutions"), ("roots", "roots"),
            ("code_bytes", "code_low"))}
        appended = host.append_definition(source, "%init-external-proof")
        executed = host.execute("%init-external-proof", [])
        after = appended["after"]
        require(before == {"images": 6, "entries": 755,
                            "resolutions": 2929, "roots": 352,
                            "code_bytes": 46043},
                f"external append seed drift: {before}")
        require(after == {"images": 7, "entries": 756,
                           "resolutions": 2930, "roots": 352,
                           "code_bytes": 46059}
                and appended["handle"] == 755
                and executed["result_text"] == "(17 65)"
                and executed["steps"] == 5
                and executed["calls"] == [{
                    "caller": "%init-external-proof", "kind": "TAILCALL",
                    "target": "list", "argc": 2, "pc": 4,
                    "resolved": True}],
                "external append did not resolve through final static owner")

        missing = exact_final_host(geometry, Path(raw) / "missing")
        populate_static_directory(missing)
        missing_reject = reject(
            "external-entry-not-published",
            lambda: missing.execute("%init-external-proof", []))

        no_owner = exact_final_host(geometry, Path(raw) / "no-owner")
        populate_static_directory(no_owner)
        no_owner.append_definition(source, "%init-external-proof")
        del no_owner.directory[no_owner.heap.intern("list")]
        owner_reject = reject(
            "external-caller-loses-final-static-owner",
            lambda: no_owner.execute("%init-external-proof", []))
    return {
        "authority": {
            "initial_c2d": bind(C2D), "bank2_code": bind(CODE),
            "stdlib_manifest": bind(MANIFEST),
        },
        "static_directory_entries_loaded": static_entries,
        "before": before, "after": after,
        "published_handle": appended["handle"],
        "execution": executed,
        "mutations": [missing_reject, owner_reject],
        "status": "PASS: EXTERNAL APPEND RESOLVES OVER FINAL STATIC PLANE",
    }


def boot_model() -> dict[str, Any]:
    expected = {
        "absent": ["setjmp", "active", "screen", "init-absent",
                   "banner", "lisp65>"],
        "valid": ["setjmp", "active", "screen", "init-evaluated",
                  "banner", "lisp65>"],
        "reader-error": ["setjmp", "active", "screen", "init-reader-error",
                         "longjmp", "error", "lisp65>"],
        "vm-error": ["setjmp", "active", "screen", "init-vm-error",
                     "longjmp", "error", "lisp65>"],
        "load-error": ["setjmp", "active", "screen", "init-load-error",
                       "longjmp", "error", "lisp65>"],
        "run-stop": ["setjmp", "active", "screen", "init-run-stop",
                     "longjmp", "error", "lisp65>"],
    }
    for name, events in expected.items():
        require(events.index("setjmp") < events.index("screen"),
                f"unsafe init ordering: {name}")
        require(events[-1] == "lisp65>" and events.count("lisp65>") == 1,
                f"scenario does not end at one native prompt: {name}")
        require(not (name == "absent" and "error" in events),
                "missing init became an error")
        if name.endswith("error") or name == "run-stop":
            require(events.index("longjmp") < events.index("lisp65>"),
                    f"error bypassed recovery: {name}")
    mutations = {
        "hook-before-setjmp": ["init-evaluated", "setjmp", "screen"],
        "missing-file-treated-as-error": ["setjmp", "screen", "error",
                                           "lisp65>"],
        "failure-returns-from-repl": ["setjmp", "screen", "init-vm-error",
                                      "return"],
        "retry-init-after-abort": ["setjmp", "screen", "init-vm-error",
                                   "longjmp", "init-evaluated", "lisp65>"],
        "later-form-masks-earlier-vm-error": ["setjmp", "screen",
                                              "init-vm-error",
                                              "init-evaluated", "lisp65>"],
    }
    rejected = []
    for name, events in mutations.items():
        safe = (
            events and events[0] == "setjmp"
            and events[-1] == "lisp65>"
            and not (name == "missing-file-treated-as-error"
                     and "error" in events)
            and not (name == "retry-init-after-abort"
                     and events.count("init-evaluated"))
            and not (name == "later-form-masks-earlier-vm-error"
                     and events.index("init-vm-error")
                         < events.index("init-evaluated"))
            and "return" not in events)
        require(not safe, f"boot mutation survived: {name}")
        rejected.append(name)
    return {"scenarios": expected, "mutations_rejected": rejected,
            "init_attempts_per_boot": 1,
            "error_destination": "native lisp65>"}


def source_seam() -> dict[str, Any]:
    repl = REPL.read_text(encoding="utf-8")
    compile_repl = COMPILE_REPL.read_text(encoding="utf-8")
    load = LOAD.read_text(encoding="utf-8")
    setjmp_at = repl.index("if (setjmp(lisp_toplevel))")
    active_at = repl.index("lisp_toplevel_active = 1;")
    screen_at = repl.index("scr_init();")
    banner_at = repl.index("vm_run_dir(LISP65_BYTECODE_STDLIB_REPL_BANNER_ENTRY")
    prompt_at = repl.index("emit_str(\"lisp65> \"")
    require(setjmp_at < active_at < screen_at < banner_at < prompt_at,
            "native boot/recovery ordering drift")
    require("if (!aborted)" in repl[screen_at - 80:banner_at]
            and "return;" in repl[banner_at:prompt_at],
            "current banner failure seam is not the priced predecessor")
    require("compile_run_top_form(form);" in compile_repl
            and "if (vm_status != VM_OK" not in compile_repl[
                compile_repl.index("void load_source_stream"):
                compile_repl.index("void crepl_boot_init")],
            "stream predecessor already has a VM-status stop")
    require("(defun load (name)" in load and "%disk-load-file" in load,
            "delivered Lisp load seam drift")
    return {
        "current_order": ["setjmp", "active", "screen", "banner", "prompt"],
        "selected_hook": "%repl-banner first form",
        "attempt_guard": "existing if (!aborted) banner guard",
        "necessary_resident_conversions": [
            "banner VM error returns through lisp_abort_code",
            "load_source_stream stops after first VM error",
            "found-but-unloadable source raises existing LOAD_OPEN error 18",
        ],
        "absence_authority": "delivered Lisp load returns NIL when name absent",
    }


def derive() -> dict[str, Any]:
    contract = load_json(CONTRACT)
    bank2 = bank2_price()
    resident = resident_price()
    external = external_append_gate()
    boot = boot_model()
    seam = source_seam()
    a0 = load_json(A0_RECEIPT)["final_product"]["recovery_quiescence"]
    composed = a0["composed_bank2"]
    projected_plane = len(CODE.read_bytes()) + bank2["delta"]["code_bytes"]
    projected_end = composed["bank"]["start"] + projected_plane
    next_owner = min(row["start"] for row in composed["mapped_tenants"])
    require(projected_plane == 46053 and next_owner - projected_end == 1229,
            "INIT composed Bank-2 projection drift")
    require(resident["projected_delta_bytes"] <= 0,
            "INIT selected form lacks zero-resident target price")
    return {
        "format": FORMAT,
        "recorded_on": "2026-08-27",
        "status": "PASS: NATIVE INIT.L65 HOOK PRICED; IMPLEMENTATION NOT OPEN",
        "authority": {
            "contract": bind(CONTRACT), "pre_plan": bind(PLAN),
            "repl": bind(REPL), "compile_repl": bind(COMPILE_REPL),
            "vm": bind(VM), "load_library": bind(LOAD),
            "A0_product_receipt": bind(A0_RECEIPT),
            "pricing_tool": bind(Path(__file__)),
        },
        "selected_form": {
            "name": "banner-owned Bank-2 native init hook",
            "expression": "(load \"init.l65\")",
            "new_named_helpers": [],
            "new_product_symbol_slots": 0,
            "new_product_name_bytes": 0,
            "new_resident_state_bytes": 0,
            "comfort_dependency": False,
            "canonical_prompt_swap": False,
        },
        "source_seam": seam,
        "boot_semantics": boot,
        "bank2_price": bank2,
        "resident_price": resident,
        "composed_capacity_projection": {
            "bank_start": composed["bank"]["start"],
            "candidate_static_plane_bytes": projected_plane,
            "candidate_static_plane_end_exclusive": projected_end,
            "next_mapped_owner_start": next_owner,
            "gap_to_next_owner_bytes": next_owner - projected_end,
            "largest_contiguous_hole_bytes":
                composed["largest_contiguous_hole"]["bytes"],
            "aggregate_free_bytes": composed["aggregate_free_bytes"] - 10,
            "overlaps": [],
            "MAP_congruence_required": False,
        },
        "symbol_capacity": {
            "baseline_free_slots": 105, "baseline_free_name_bytes": 1413,
            "candidate_free_slots": 105, "candidate_free_name_bytes": 1413,
            "floor_slots": contract["capacity_floors"]["free_symbol_slots"],
            "floor_name_bytes":
                contract["capacity_floors"]["free_name_bytes"],
            "note": "init.l65 is a bytecode string literal, not a name-pool symbol",
        },
        "external_library_append": external,
        "all_mutations_rejected": (
            boot["mutations_rejected"]
            + [row["name"] for row in external["mutations"]]),
        "implementation_obligations": [
            "final linked resident delta is <= 0",
            "candidate banner remains one object below 255 bytes",
            "missing INIT.L65 is silent and attempted once",
            "reader/load/evaluation/RUN-STOP errors end at live native lisp65>",
            "stream loader cannot mask an earlier VM error with a later form",
            "external append fixture runs over the candidate final static plane",
            "composed Bank-2 owner map remains disjoint",
            "full double-green check-source closure before media",
        ],
        "claim_limit": (
            "Host-only price and executable boundary proof. No product repair, "
            "WPLTO, link, medium, device result, prompt swap, or Comfort reopen."),
        "budgets": {"WPLTO": 0, "product_links": 0, "media": 0,
                    "device_contacts": 0},
    }


def check_sealed_receipt() -> dict[str, Any]:
    """Keep the accepted price in its own pre-implementation world."""
    require(OUT.is_file() and not OUT.is_symlink(),
            "INIT.L65 pricing receipt absent")
    raw = OUT.read_bytes()
    require(raw == ERA.era_blob(
                SEALED_COMMIT, OUT.relative_to(ROOT).as_posix()),
            "sealed INIT.L65 pricing receipt was rewritten")
    value = json.loads(raw)
    require(value.get("format") == FORMAT
            and value.get("status") ==
                "PASS: NATIVE INIT.L65 HOOK PRICED; IMPLEMENTATION NOT OPEN"
            and value.get("bank2_price", {}).get("delta") == {
                "objects": 0, "code_bytes": 10,
                "repl_banner_bytes": 10,
                "new_product_symbol_slots": 0,
                "new_product_name_bytes": 0},
            "sealed INIT.L65 pricing identity drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.write:
        value = derive()
        raw = canonical(value)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_bytes(raw)
    else:
        value = check_sealed_receipt()
    print(value["status"])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PricingError, SessionHostError) as exc:
        print(f"INIT.L65 pricing: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
