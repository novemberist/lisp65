#!/usr/bin/env python3
"""Attribute the v1.5 Link-97 D3 `too many symbols` First Red.

The calculation deliberately starts from the hardware-read Link-92 symbol
pool, not from a source-only census.  It removes the two Link-92 library
loads, applies the exact Link-92 -> Link-97 static-manifest delta, then replays
the v1.5 D2/D3 simultaneous-live order.  The C2 decoder's symbol-node order is
used to name the first place-library symbol which cannot fit.

No product, medium, compiler, linker, emulator or device is run by this tool.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import mvp_vm_stdlib_boot_budget as BB  # noqa: E402


LINK92_POOL = ROOT / (
    "build/c2.3/v1.4.0-release/phase-d-split/d3-descope/"
    "d3-final-namepool.bin")
LINK92_NSYM = ROOT / (
    "build/c2.3/v1.4.0-release/phase-d-split/d3-descope/"
    "d3-final-nsym.bin")
LINK92_STATIC = ROOT / (
    "build/c2.3/v1.4.0-release/phase-c/profile-preflight-r5/"
    "static-plane/narrow-static/product/substitution-artifacts.json")
LINK97_STATIC = ROOT / (
    "build/c2.3/v1.5.0-candidate-product-link97/static-plane/"
    "narrow-static/product/substitution-artifacts.json")
OLD_INSPECT = ROOT / "build/post-promotion/v112/inspect/inspect.manifest.json"
INSPECT = ROOT / "build/c2.3/trace-core-abi/inspect.manifest.json"
STRING_EXTRA = ROOT / (
    "build/post-promotion/v112/string-extra/string-extra.manifest.json")
PLACE = ROOT / (
    "build/post-promotion/defstruct-v1/foundations/place.manifest.json")
DEFSTRUCT = ROOT / (
    "build/post-promotion/v110-performance/defstruct-candidate.manifest.json")
MEDIA = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-link97-media-closure-receipt.json")
ROWS = ROOT / "config/c2-v150-link97-device-rows.json"
SYMBOL_C = ROOT / "src/symbol.c"
DECODER_C = ROOT / "src/c2_product_decoder.c"
PREFLIGHT = ROOT / "tools/host-lisp/c2_v150_release_preflight.py"
ELF = ROOT / (
    "build/c2.3/v1.5.0-candidate-product-link97/final/"
    "lisp65-c2-substitution-linked.prg.elf")
CAPTURE_DIR = ROOT / "build/c2.3/v1.5.0-link97-symbol-capacity-first-red"
CURRENT_BANK0 = CAPTURE_DIR / "bank0-underlay.bin"
CURRENT_POOL = CAPTURE_DIR / "namepool.bin"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-link97-d3-symbol-capacity-first-red.json")

MAX_SYM = 752
NAMEPOOL = 10208
FORMAT = "lisp65-c2.3-v150-link97-d3-symbol-capacity-first-red-v1"


class CapacityError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CapacityError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(raw),
        "sha256": sha(raw),
    }


def manifest_names(path: Path) -> set[str]:
    named, literals = BB.manifest_symbols(load(path))
    return {str(name).lower() for name in named | literals}


def name_bytes(names: set[str]) -> int:
    return sum(len(name.encode("ascii")) + 1 for name in names)


def pool_names(path: Path) -> tuple[set[str], int]:
    raw = path.read_bytes()
    require(len(raw) == NAMEPOOL, "Link-92 namepool capture size drift")
    nonzero = [index for index, value in enumerate(raw) if value]
    require(nonzero, "Link-92 namepool capture is empty")
    used = nonzero[-1] + 2
    require(used <= len(raw) and raw[used - 1] == 0,
            "Link-92 namepool does not end at a NUL boundary")
    fields = raw[:used].split(b"\0")
    require(fields[-1] == b"", "Link-92 namepool terminator drift")
    names = {field.decode("ascii").lower() for field in fields[:-1]}
    require(len(names) == len(fields) - 1,
            "Link-92 namepool contains duplicate canonical names")
    require(name_bytes(names) == used,
            "Link-92 namepool set does not reproduce captured usage")
    return names, used


def static_names(index: dict[str, Any]) -> set[str]:
    manifests = index.get("manifests")
    require(isinstance(manifests, list) and len(manifests) == 6,
            "product static manifest list drift")
    result: set[str] = set()
    for row in manifests:
        result.update(manifest_names(ROOT / row["path"]))
    return result


def add_names(state: set[str], names: set[str]) -> dict[str, Any]:
    before_symbols = len(state)
    before_bytes = name_bytes(state)
    added = names - state
    state.update(names)
    return {
        "before": {"symbols": before_symbols, "namepool_bytes": before_bytes},
        "added": {"symbols": len(added), "namepool_bytes": name_bytes(added)},
        "after": {"symbols": len(state), "namepool_bytes": name_bytes(state)},
        "added_names": sorted(added),
    }


def replay(model: dict[str, Any] | None = None) -> dict[str, Any]:
    model = model or {}
    link92_names, link92_used = pool_names(LINK92_POOL)
    link92_nsym = int.from_bytes(LINK92_NSYM.read_bytes(), "little")
    require(link92_nsym == len(link92_names) == 690 and link92_used == 9646,
            "Link-92 hardware symbol/namepool authority drift")

    static92 = static_names(load(LINK92_STATIC))
    static97 = static_names(load(LINK97_STATIC))
    require(static92 <= link92_names,
            "Link-92 hardware pool lacks a static-manifest name")

    old_library = manifest_names(OLD_INSPECT) | manifest_names(STRING_EXTRA)
    # The package names are read from the physical require forms; they are
    # index labels, not C2I symbols in either library manifest.
    old_session_only = (old_library - static92) | {"inspect", "string-extra"}
    require(old_session_only <= link92_names,
            "Link-92 session-only subtraction is not hardware-backed")
    base92 = link92_names - old_session_only
    stable_nonstatic = base92 - static92
    require(stable_nonstatic == {
        "key", "other", "primitive", "save", "set-symbol-function", "shift", "t",
    }, "Link-92 non-static boot calibration drift")

    removed = static92 - static97
    added = static97 - static92
    require(removed == {"%c1-compile-form", "%lcc-consp", "lcc-compile-obj"}
            and added == {
                "%c2-direct-expression", "%c2-direct-expression-p",
                "%c2-run-expanded", "%c2-top-level-expand",
                "%c2-top-level-macro-p", "%c2-top-level-run-forms",
            }, "Link-92 -> Link-97 static semantic delta drift")
    state = (base92 - removed) | added
    require(len(state) == 636 and name_bytes(state) == 8681,
            "Link-97 cold-boot symbol reconstruction drift")
    cold97 = set(state)

    inspect_freight = {"inspect"} | manifest_names(INSPECT)
    string_freight = {"string-extra"} | manifest_names(STRING_EXTRA)
    trace_fixture = {"trace-probe", "x"}
    defstruct_chain = manifest_names(PLACE) | {"defstruct"} | manifest_names(
        DEFSTRUCT)

    stages: list[dict[str, Any]] = []
    stages.append({"stage": "D2 require inspect", **add_names(
        state, inspect_freight)})
    stages.append({"stage": "D2 require string-extra", **add_names(
        state, string_freight)})
    stages.append({"stage": "D2 define trace-probe", **add_names(
        state, trace_fixture)})
    require(len(state) == 710 and name_bytes(state) == 10019,
            "D2 simultaneous-live symbol state drift")
    d2 = {"symbols": len(state), "namepool_bytes": name_bytes(state),
          "symbol_headroom": MAX_SYM - len(state),
          "namepool_headroom": NAMEPOOL - name_bytes(state)}

    stages.append({"stage": "D3 reader interns defstruct", **add_names(
        state, {"defstruct"})})
    require(len(state) == 711 and name_bytes(state) == 10029,
            "D3 pre-place symbol state drift")

    place = load(PLACE)
    require(all(node.get("kind") == 4 for node in place["literal_nodes"]),
            "place literal-node domain drift")
    events: list[dict[str, Any]] = []
    failure: dict[str, Any] | None = None
    for ordinal, node in enumerate(place["literal_nodes"]):
        name = node.get("name")
        if not isinstance(name, str) or name.lower() in state:
            continue
        name = name.lower()
        cost = len(name.encode("ascii")) + 1
        before = name_bytes(state)
        event = {
            "domain": "place.literal_nodes", "ordinal": ordinal,
            "name": name, "cost": cost,
            "before": {"symbols": len(state), "namepool_bytes": before,
                       "namepool_headroom": NAMEPOOL - before},
        }
        if cost > NAMEPOOL - before:
            event["result"] = "rejected-before-write"
            failure = event
            events.append(event)
            break
        state.add(name)
        event["result"] = "interned"
        event["after"] = {"symbols": len(state),
                          "namepool_bytes": name_bytes(state)}
        events.append(event)
    require(failure is not None, "place literals unexpectedly fit namepool")
    require(failure == {
        "domain": "place.literal_nodes", "ordinal": 33,
        "name": "%setf-expand-list", "cost": 18,
        "before": {"symbols": 720, "namepool_bytes": 10205,
                   "namepool_headroom": 3},
        "result": "rejected-before-write",
    }, "first non-fitting place symbol drift")

    media = load(MEDIA)
    order = media["library"]["resolver_contracts"]["defstruct"]
    require(order["actual_resolver_order"] == [2, 3]
            and media["library"]["index_rows"][2]["name"] == "place"
            and media["library"]["index_rows"][3]["name"] == "defstruct",
            "D3 resolver no longer loads place before defstruct")
    row_values = load(ROWS)["rows"]
    require(row_values[7]["id"] == "d3-require-defstruct"
            and row_values[7]["form"] == "(require (quote defstruct))",
            "physical D3 row identity drift")

    symbol_source = SYMBOL_C.read_text(encoding="utf-8")
    decoder_source = DECODER_C.read_text(encoding="utf-8")
    require(
        "nsym >= MAX_SYM" in symbol_source
        and "NAMEPOOL - npool" in symbol_source
        and "LISP65_ERR_TOO_MANY_SYMBOLS" in symbol_source
        and "c2_stream_name_value(work.r[0]" in decoder_source
        and "++c->resolution_cursor; ++work.local" in decoder_source,
        "target allocator/decoder source binding drift")
    preflight_source = PREFLIGHT.read_text(encoding="utf-8")
    require('"symbol_space_is_not_an_input": True' in preflight_source,
            "v1.5 preflight missing-gate evidence drift")

    observed = model.get("observed")
    if observed is not None:
        require(observed == {"symbol_count": 720, "npool": 10205},
                "hardware post-error counters disagree with exact replay")

        bank0 = CURRENT_BANK0.read_bytes()
        pool = CURRENT_POOL.read_bytes()
        require(
            len(bank0) == 0xC000 and len(pool) == NAMEPOOL
            and int.from_bytes(bank0[0x5f:0x61], "little")
                == observed["symbol_count"]
            and int.from_bytes(bank0[0xbe14:0xbe16], "little")
                == observed["npool"],
            "stopped-state Bank-0 counter capture drift")
        fields = pool[:observed["npool"]].split(b"\0")
        require(fields[-1] == b"", "stopped-state namepool boundary drift")
        captured_names = {field.decode("ascii").lower()
                          for field in fields[:-1]}
        require(
            len(captured_names) == observed["symbol_count"]
            and name_bytes(captured_names) == observed["npool"]
            and captured_names == state,
            "stopped-state namepool content disagrees with exact replay")

    def capacity(names: set[str]) -> dict[str, int]:
        symbols = len(names)
        used = name_bytes(names)
        return {
            "symbols": symbols, "namepool_bytes": used,
            "symbol_headroom": MAX_SYM - symbols,
            "namepool_headroom": NAMEPOOL - used,
        }

    shipped_closure = (cold97 | inspect_freight | string_freight
                       | defstruct_chain)
    full_session = shipped_closure | trace_fixture
    require(capacity(shipped_closure) == {
        "symbols": 752, "namepool_bytes": 10812,
        "symbol_headroom": 0, "namepool_headroom": -604,
    } and capacity(full_session) == {
        "symbols": 754, "namepool_bytes": 10826,
        "symbol_headroom": -2, "namepool_headroom": -618,
    }, "full freight capacity projection drift")

    return {
        "hardware_baseline": {
            "link92_after_inspect_and_string_extra": {
                "symbols": link92_nsym, "namepool_bytes": link92_used,
            },
        },
        "static_delta": {
            "removed": sorted(removed), "added": sorted(added),
            "net": {"symbols": len(added) - len(removed),
                    "namepool_bytes": name_bytes(added) - name_bytes(removed)},
        },
        "stages": stages,
        "D2_postcondition": d2,
        "D3_pre_place": {"symbols": 711, "namepool_bytes": 10029,
                         "symbol_headroom": 41, "namepool_headroom": 179},
        "place_intern_events": events,
        "first_failure": failure,
        "observed": observed,
        "counter_addresses": {"nsym": "0x005F", "npool": "0xBE14"},
        "limits": {"symbols": MAX_SYM, "namepool_bytes": NAMEPOOL},
        "simultaneous_live_projection": {
            "all_shipped_library_roles_without_session_fixture":
                capacity(shipped_closure),
            "exact_D2_D3_session_freight": capacity(full_session),
            "defstruct_chain_without_inspect_or_string_extra":
                capacity(cold97 | defstruct_chain),
            "D2_without_defstruct_chain":
                capacity(cold97 | inspect_freight | string_freight
                         | trace_fixture),
            "full_session_without_inspect":
                capacity(cold97 | string_freight | trace_fixture
                         | defstruct_chain),
            "fit_only_minimum_delta": {
                "symbols": 2, "namepool_bytes": 618,
                "warning": "fit-only, not a user-headroom recommendation",
            },
        },
        "missing_release_gate": {
            "source": PREFLIGHT.relative_to(ROOT).as_posix(),
            "bound_setting": "symbol_space_is_not_an_input = true",
            "required_scope": (
                "simultaneous-live runtime symbols and name bytes for the "
                "ordered release-session freight"),
        },
        "excluded_first_limit": "MAX_SYM: 32 symbol slots remain at failure",
        "mechanism": (
            "simultaneous-live D2 freight leaves 179 name bytes before D3; "
            "the place dependency interns nine additional names, leaving "
            "three bytes, then new_symbol rejects the 18-byte %setf-expand-list "
            "record before any pool write"),
    }


def rejected_mutations() -> list[str]:
    cases: dict[str, Callable[[], None]] = {
        "drop-hardware-baseline": lambda: pool_names(ROOT / "missing"),
        "wrong-link92-nsym": lambda: require(
            int.from_bytes(LINK92_NSYM.read_bytes(), "little") == 689,
            "mutant accepted stale Link-92 nsym"),
        "individual-library-only": lambda: require(
            name_bytes(manifest_names(PLACE)) > NAMEPOOL,
            "mutant accepted per-library rather than simultaneous-live fit"),
        "skip-place-dependency": lambda: require(
            load(MEDIA)["library"]["resolver_contracts"]["defstruct"]
            ["actual_resolver_order"] == [3],
            "mutant skipped declared place dependency"),
        "blame-symbol-table": lambda: require(
            replay()["first_failure"]["before"]["symbols"] >= MAX_SYM,
            "mutant blamed MAX_SYM before NAMEPOOL"),
        "accept-next-name": lambda: require(
            replay()["first_failure"]["cost"]
            <= replay()["first_failure"]["before"]["namepool_headroom"],
            "mutant accepted non-fitting name"),
        "change-failure-name": lambda: require(
            replay()["first_failure"]["name"] == "%setf-expand",
            "mutant moved the first failure"),
        "ignore-physical-D2-freight": lambda: require(
            replay()["D2_postcondition"]["namepool_bytes"] < 9000,
            "mutant omitted simultaneous-live D2 freight"),
    }
    rejected: list[str] = []
    for name, run in cases.items():
        try:
            run()
        except (CapacityError, FileNotFoundError):
            rejected.append(name)
    require(rejected == list(cases), "capacity mutation survived")
    return rejected


def derive(observed: dict[str, int] | None) -> dict[str, Any]:
    result = replay({"observed": observed} if observed is not None else {})
    return {
        "format": FORMAT,
        "recorded_on": "2026-08-11",
        "status": ("D3-NAMEPOOL-EXHAUSTION-ATTRIBUTED"
                   if observed is not None else
                   "D3-NAMEPOOL-MODEL-PREPARED-AWAITING-COUNTERS"),
        "authority": {
            "link92_namepool": bind(LINK92_POOL),
            "link92_nsym": bind(LINK92_NSYM),
            "link92_static": bind(LINK92_STATIC),
            "link97_static": bind(LINK97_STATIC),
            "old_inspect": bind(OLD_INSPECT),
            "inspect": bind(INSPECT),
            "string_extra": bind(STRING_EXTRA),
            "place": bind(PLACE),
            "defstruct": bind(DEFSTRUCT),
            "media": bind(MEDIA),
            "rows": bind(ROWS),
            "symbol_allocator": bind(SYMBOL_C),
            "c2_decoder": bind(DECODER_C),
            "release_preflight": bind(PREFLIGHT),
            "product_ELF": bind(ELF),
            **({"stopped_bank0": bind(CURRENT_BANK0),
                "stopped_namepool": bind(CURRENT_POOL)}
               if observed is not None else {}),
            "checker": bind(Path(__file__)),
        },
        "attribution": result,
        "mutations_rejected": rejected_mutations(),
        "execution_accounting": {
            "device_memory_ranges_read": 0 if observed is None else 2,
            "failed_read_only_REPL_probes": 0 if observed is None else 5,
            "forms_retried": 0,
            "product_bytes_changed": 0,
            "product_links": 0,
            "media_builds": 0,
        },
        "claim_limit": (
            "The Link-97 D3 First Red is attributed to simultaneous-live "
            "namepool exhaustion while materializing place literal node 33. "
            "No fix, freight choice, new product build, media, D3 retry, D4, "
            "D5, Halt or release is authorized."),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--observed-symbol-count", type=int)
    parser.add_argument("--observed-npool-low", type=int)
    parser.add_argument("--observed-npool-high", type=int)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        result = replay()
        rejected = rejected_mutations()
        print("c2-v150-link97-symbol-capacity-attribution selftest: PASS "
              f"failure={result['first_failure']['name']} "
              f"mutations={len(rejected)}")
        return 0
    values = (args.observed_symbol_count, args.observed_npool_low,
              args.observed_npool_high)
    require(all(value is None for value in values)
            or all(value is not None for value in values),
            "all three observed counters are required together")
    observed = None
    if values[0] is not None:
        require(0 <= values[1] <= 255 and 0 <= values[2] <= 255,
                "npool bytes outside u8")
        observed = {"symbol_count": values[0],
                    "npool": values[1] | (values[2] << 8)}
    receipt = derive(observed)
    raw = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
    if args.write:
        RECEIPT.write_bytes(raw)
        print(f"wrote {RECEIPT.relative_to(ROOT)}")
    else:
        sys.stdout.buffer.write(raw)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CapacityError as exc:
        raise SystemExit(f"c2-v150-link97-symbol-capacity-attribution: FAIL: {exc}")
