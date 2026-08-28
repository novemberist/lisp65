#!/usr/bin/env python3
"""Host-only reproduction of the sealed v1.7 Block-3 $22 first red."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_stdlib as STD  # noqa: E402
import c2_full_emission as F  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402
import c2_product_session_host as SESSION  # noqa: E402


PLANE = ROOT / ("build/c2.3/v1.7-ide-idle-blink-product-preflight-r10/"
                "setup-owned/static-plane/narrow-static")
C2D = PLANE / "v6-semantics/initial.c2d-v6.bin"
CODE = PLANE / "v6-semantics/bank2-static-code.bin"
STATIC_ARTIFACTS = PLANE / "product/substitution-artifacts.json"
LIBRARY_MANIFEST = ROOT / ("build/c2.3/v1.7-block3-banner-ordinal-acceptance-"
                           "media/library-inputs/v17core.manifest.json")
SEALED = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                 "c2.3-v1.7-block3-left-first-red-attribution.json")
SYMBOL_C = ROOT / "src/symbol.c"
SYMBOL_H = ROOT / "src/symbol.h"
VM_C = ROOT / "src/vm.c"
NATIVE_DISPATCH = ROOT / "src/v2_native_function_dispatch.h"
OUT = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
              "c2.3-v1.8-block1-symbol22-host-attribution.json")

ERR_TOO_MANY_SYMBOLS = 34
SYMBOL_NAME_MAX = 33


class AttributionError(RuntimeError):
    pass


class SymbolAbort(RuntimeError):
    def __init__(self, record: dict[str, Any]):
        super().__init__(record["reason"])
        self.record = record


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


class ProductSymbolPath:
    """Capacity-faithful model of intern/new_symbol in src/symbol.c."""

    def __init__(self, *, nsym: int, npool: int, max_sym: int,
                 namepool: int, known: set[str]) -> None:
        self.nsym = nsym
        self.npool = npool
        self.max_sym = max_sym
        self.namepool = namepool
        self.known = set(known)
        self.calls: list[dict[str, Any]] = []

    def intern(self, name: str, *, caller: str, source: str) -> str:
        encoded = name.encode("ascii")
        if name in self.known:
            self.calls.append({"caller": caller, "name": name,
                               "name_bytes_with_nul": len(encoded) + 1,
                               "source": source, "result": "existing"})
            return name
        return self.new_symbol(encoded + b"\0", caller=caller, source=source)

    def new_symbol(self, raw: bytes, *, caller: str, source: str) -> str:
        length = 0
        while length < len(raw) and raw[length] and length <= SYMBOL_NAME_MAX:
            length += 1
        terminated = length < len(raw) and raw[length] == 0
        reason = None
        if length > SYMBOL_NAME_MAX or not terminated:
            reason = "name length exceeds LISP65_SYMBOL_NAME_MAX"
        elif self.nsym >= self.max_sym:
            reason = "MAX_SYM exhausted"
        elif length + 1 > self.namepool - self.npool:
            reason = "NAMEPOOL exhausted"
        display = raw[:min(length, len(raw))].decode("ascii", errors="replace")
        record = {"caller": caller, "name": display, "observed_length": length,
                  "terminated_within_scan": terminated, "source": source}
        if reason is not None:
            record.update({"result": "LISP65_ERR_TOO_MANY_SYMBOLS",
                           "error_code_decimal": ERR_TOO_MANY_SYMBOLS,
                           "error_code_hex": "$22", "reason": reason,
                           "nsym": self.nsym, "npool": self.npool})
            self.calls.append(record)
            raise SymbolAbort(record)
        self.known.add(display)
        self.nsym += 1
        self.npool += length + 1
        record.update({"result": "new", "name_bytes_with_nul": length + 1,
                       "nsym_after": self.nsym, "npool_after": self.npool})
        self.calls.append(record)
        return display


def macro_names(name: str) -> list[str]:
    text = NATIVE_DISPATCH.read_text(encoding="utf-8")
    marker = f"#define {name}_ROWS(X)"
    require(marker in text, f"missing generated dispatch macro: {name}")
    block = text[text.index(marker):]
    block = block[:block.index("\n\n")]
    return re.findall(r'X\("([^"]+)"', block)


def apply_primitive_scan(symbols: ProductSymbolPath, target: str) -> dict[str, Any]:
    """Execute vm_apply_primitive's non-tree intern scan for one target."""
    scanned: list[str] = []
    for group in ("LISP65_V2_NATIVE_FUNCTION_FOLD_IDENTITY",
                  "LISP65_V2_NATIVE_FUNCTION_FOLD_REQUIRED"):
        for name in macro_names(group):
            scanned.append(name)
            symbols.intern(name, caller="vm_apply_primitive",
                           source=f"{group}_MATCH in src/vm.c")
            if name == target:
                return {"target": target, "matched": name,
                        "category": group, "comparisons": len(scanned)}
    for name in macro_names("LISP65_V2_NATIVE_FUNCTION_CALLPRIM"):
        scanned.append(name)
        resolved = symbols.intern(
            name, caller="vm_apply_primitive",
            source="generated_callprim from src/v2_native_function_dispatch.h")
        if resolved == target:
            return {"target": target, "matched": name,
                    "category": "CALLPRIM", "comparisons": len(scanned)}
    for name in macro_names("LISP65_V2_NATIVE_FUNCTION_OPFN"):
        scanned.append(name)
        resolved = symbols.intern(
            name, caller="vm_apply_primitive",
            source="generated_opfn from src/v2_native_function_dispatch.h")
        if resolved == target:
            return {"target": target, "matched": name,
                    "category": "OPFN", "comparisons": len(scanned)}
    for name in macro_names("LISP65_V2_NATIVE_FUNCTION_EXCLUSION"):
        scanned.append(name)
        resolved = symbols.intern(
            name, caller="vm_apply_primitive",
            source="generated_exclusions from src/v2_native_function_dispatch.h")
        if resolved == target:
            return {"target": target, "matched": name,
                    "category": "EXCLUSION", "comparisons": len(scanned)}
    raise AttributionError(
        f"trace CALLPRIM target absent from product dispatch: {target}")


def positive_control() -> dict[str, Any]:
    symbols = ProductSymbolPath(
        nsym=0, npool=0, max_sym=752, namepool=10208, known=set())
    raw = b"X" * (SYMBOL_NAME_MAX + 1) + b"\0"
    try:
        symbols.new_symbol(raw, caller="positive_control",
                           source="intentional 34-byte local test name")
    except SymbolAbort as error:
        require(error.record["error_code_decimal"] == ERR_TOO_MANY_SYMBOLS,
                "positive control returned wrong error")
        return {"passed": True, "input_bytes_before_nul": 34,
                "fault": error.record}
    raise AttributionError("overlength positive control did not produce $22")


def geometry() -> dict[str, int]:
    raw = C2D.read_bytes()
    u16 = lambda at: int.from_bytes(raw[at:at + 2], "little")
    value = {
        "generation": u16(10), "images": u16(12), "entries": u16(16),
        "resolutions": u16(20), "roots": u16(24),
        "code_bytes": len(CODE.read_bytes()), "immutable_images": u16(38),
        "catalog_crc32": int.from_bytes(raw[40:44], "little"),
        "build_id": int.from_bytes(raw[44:48], "little"),
    }
    require(value["entries"] == 788 and value["code_bytes"] == 52230,
            f"sealed Block-3 geometry drift: {value}")
    return value


class RecordingSymbols(SESSION.TargetSymbols):
    def __init__(self) -> None:
        self.attempts: list[dict[str, Any]] = []
        super().__init__()

    def intern(self, name: str) -> int:
        encoded = name.encode("ascii", errors="backslashreplace")
        self.attempts.append({"name": name, "bytes": len(encoded),
                              "source": "C2 descriptor/entry resolver"})
        require(len(encoded) <= 33,
                f"target new_symbol overlength: {name!r}/{len(encoded)}")
        return super().intern(name)


def exact_host(out: Path) -> SESSION.ProductSessionHost:
    host = SESSION.ProductSessionHost(geometry(), out)
    host.symbols = RecordingSymbols()
    host.raw_to_host = {host.symbols.intern("t"): host.heap.t_obj}
    c2d, code = C2D.read_bytes(), CODE.read_bytes()
    host.plane.c2d[:] = c2d
    host.plane.code[:len(code)] = code
    return host


def populate_static_directory(host: SESSION.ProductSessionHost) -> list[str]:
    artifacts = load(STATIC_ARTIFACTS)
    manifests = [ROOT / row["path"] for row in artifacts["manifests"]]
    loaded: list[str] = []
    for path in manifests:
        manifest = load(path)
        blob = (ROOT / manifest["blob"]).read_bytes()
        require(sha(blob) == manifest["blob_sha256"], f"blob drift: {path}")
        patches = {int(row["blob_offset"]): int(row["node"])
                   for row in manifest["literal_patches"]}
        for entry in manifest["entries"]:
            code = STD._patched_code_from_manifest_entry(
                host.heap, manifest, blob, entry, patches)
            symbol = host.heap.intern(entry["name"])
            host.directory[symbol] = code
            host.code_names[id(code)] = entry["name"]
            loaded.append(entry["name"])
    require(len(loaded) == 788, f"static directory population drift: {len(loaded)}")
    return loaded


def append_real_library(host: SESSION.ProductSessionHost) -> dict[str, Any]:
    image = F.emit_image("v17core", "v16core", LIBRARY_MANIFEST)
    def counters() -> dict[str, int]:
        return {"images": host.plane.images, "entries": host.plane.entries,
                "resolutions": host.plane.resolutions, "roots": host.plane.roots,
                "code_bytes": host.plane.code_low}
    before = counters()
    entry_base = host.plane.entries
    resolution_base = host.plane.resolutions
    for local, entry in enumerate(image.manifest["entries"]):
        _raw, symbol = host._sync_symbol(entry["name"])
        host.ordinal_to_symbol[entry_base + local] = symbol
        host.raw_to_host[SESSION.mk_bcode(entry_base + local)] = symbol
    appended = V6.append_image(
        host.plane, image, transient=False,
        direct_resolver=host._resolve_direct(image))
    host._bind_image_objects(image, resolution_base, entry_base)
    snapshots = []
    for local, entry in enumerate(image.manifest["entries"]):
        snap = host.snapshot_entry(entry_base + local)
        symbol = host.heap.intern(entry["name"])
        host.directory[symbol] = snap["code"]
        host.code_names[id(snap["code"])] = entry["name"]
        snapshots.append({key: value for key, value in snap.items()
                          if key != "code"})
    return {"before": before, "after": counters(),
            "append": {"entries": appended["entries"],
                       "handles": appended["handles"]},
            "entries": snapshots,
            "entry_names": [row["name"] for row in image.manifest["entries"]]}


def execute_first_left(host: SESSION.ProductSessionHost) -> dict[str, Any]:
    trace = SESSION.Trace()
    keys = [40, 108, 105, 115, 116, 32, 49, 32, 51, 41, 157, 13]
    vm = B.P0VM(
        heap=host.heap, directory=host.directory, trace=trace,
        code_names=host.code_names, max_steps=1_000_000, max_call_args=12,
        key_events=keys, private_key_event_modes=True,
        memory_read_sequences={0xff83: [0] * 256},
        abi_profile="dialect-v2", abi_ledger=host.ledger)
    entry = host.heap.intern("read-line")
    require(entry in host.directory, "external read-line was not published")
    result = vm.run(host.directory[entry], [])
    return {"result": host.heap.obj_to_text(result), "steps": vm.steps,
            "calls": trace.calls, "keys": keys}


def derive() -> dict[str, Any]:
    control = positive_control()
    sealed = load(SEALED)
    capacity = sealed["primary_error"]["capacity"]
    with tempfile.TemporaryDirectory(prefix="c2-v18-b1-", dir=ROOT / "build") as raw:
        host = exact_host(Path(raw))
        static = populate_static_directory(host)
        append = append_real_library(host)
        execution = execute_first_left(host)
        attempts = host.symbols.attempts
    callprim_calls = [row for row in execution["calls"]
                      if row.get("kind") == "CALLPRIM"]
    require(callprim_calls, "mixed-world execution did not reach CALLPRIM")
    trace_targets = [str(row["target"]) for row in callprim_calls]
    distinct_targets = list(dict.fromkeys(trace_targets))
    # Bytecode literal target identities are necessarily already present. All
    # other comparison identities are pessimistically treated as absent.
    product_symbols = ProductSymbolPath(
        nsym=int(capacity["symbol_slots_used"]),
        npool=int(capacity["name_bytes_used"]),
        max_sym=int(capacity["symbol_slots_limit"]),
        namepool=int(capacity["name_bytes_limit"]),
        known=set(distinct_targets))
    native_scans = [apply_primitive_scan(product_symbols, target)
                    for target in trace_targets]
    first_after = {"symbol_slots_used": product_symbols.nsym,
                   "name_bytes_used": product_symbols.npool}
    # Replaying the complete observed sequence must allocate nothing.
    calls_after_first = len(product_symbols.calls)
    replay_scans = [apply_primitive_scan(product_symbols, target)
                    for target in trace_targets]
    require(product_symbols.nsym == first_after["symbol_slots_used"]
            and product_symbols.npool == first_after["name_bytes_used"],
            "complete CALLPRIM replay was not allocation-idempotent")
    second_scan = product_symbols.calls[calls_after_first:]
    require(all(row["result"] == "existing" for row in second_scan),
            "complete CALLPRIM replay unexpectedly allocated a name")
    scan_capacity = {
        "before": {"symbol_slots_used": capacity["symbol_slots_used"],
                   "symbol_slots_limit": capacity["symbol_slots_limit"],
                   "name_bytes_used": capacity["name_bytes_used"],
                   "name_bytes_limit": capacity["name_bytes_limit"]},
        "after_first_pessimistic_scan": first_after,
        "free_after": {
            "symbol_slots": product_symbols.max_sym - product_symbols.nsym,
            "name_bytes": product_symbols.namepool - product_symbols.npool},
        "new_names": [row for row in product_symbols.calls[:calls_after_first]
                      if row["result"] == "new"],
        "complete_replay_all_existing": True,
    }
    return {
        "format": "lisp65-c2-v18-block1-symbol22-host-attribution-v2",
        "status": "TARGET-FAITHFUL NON-REPRODUCTION: POSITIVE CONTROL $22, REAL MIXED WORLD GREEN",
        "authority": {"sealed_first_red": bind(SEALED), "c2d": bind(C2D),
                      "code": bind(CODE), "static_artifacts": bind(STATIC_ARTIFACTS),
                      "library_manifest": bind(LIBRARY_MANIFEST),
                      "symbol_c": bind(SYMBOL_C), "symbol_h": bind(SYMBOL_H),
                      "vm_c": bind(VM_C),
                      "native_dispatch": bind(NATIVE_DISPATCH)},
        "positive_control": control,
        "static_entries_loaded": len(static), "library_append": append,
        "target_intern_attempts": attempts,
        "overlength_attempts": [row for row in attempts if row["bytes"] > 33],
        "execution": execution,
        "product_symbol_path": {
            "model": ("src/symbol.c new_symbol length/MAX_SYM/NAMEPOOL rules "
                      "plus src/vm.c generated vm_apply_primitive intern order"),
            "callprim_invocations_in_real_trace": len(callprim_calls),
            "trace_targets_in_order": trace_targets,
            "distinct_trace_targets_in_first_seen_order": distinct_targets,
            "first_pass_scans": native_scans,
            "replay_scans": replay_scans,
            "capacity": scan_capacity,
        },
        "mechanical_result": {
            "sealed_hardware_result": "LISP65_ERR_TOO_MANY_SYMBOLS ($22)",
            "host_result": execution["result"],
            "host_reproduced_$22": False,
            "exact_new_symbol_writer": None,
            "passed_name": None,
            "reason": ("the complete observed native scan sequence completes under "
                       "the pessimistic assumption that every comparison name "
                       "other than observed target literals is new; the full "
                       "observed CALLPRIM sequence and its replay complete"),
        },
        "conclusion": {
            "classification": "genuine host non-reproduction",
            "writer_named": False,
            "why_no_writer_is_claimed": (
                "the calibrated positive control proves the modeled product "
                "error edge, but no real mixed-world intern call reaches it"),
        },
        "budgets": {"device_contacts": 0, "WPLTO": 0, "product_links": 0},
        "claim_limit": ("Host-only target-capacity/native-scan non-reproduction. "
                        "It does not authorize a product repair."),
        "recorded_on": "2026-08-27",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    require(args.write != args.check, "choose exactly one mode")
    value = derive()
    raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    if args.write:
        OUT.write_bytes(raw)
    else:
        require(OUT.read_bytes() == raw, "Block-1 attribution receipt drift")
    print(value["status"], value["execution"]["result"],
          len(value["target_intern_attempts"]))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, SESSION.SessionHostError,
            F.FullError, V6.ProbeError) as error:
        print(f"v1.8 Block-1 attribution: FAIL: {error}")
        raise SystemExit(1)
