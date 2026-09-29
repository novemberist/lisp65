#!/usr/bin/env python3
"""IDE exit successor: pinned producer/ring source proof and real Lisp dispatch.

Preserves the predecessor's C-Space/M-x checks. This is a source-authority
check, not linked-product execution, emulator acceptance, or device evidence.
The ring model below is bound to the inspected source hashes; transport drift
must be reviewed rather than silently accepted by the model.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import c2_l_full_keymap_end_to_end_gate as BASE
import c2_ide_exit_keymap_20260928 as KEYMAP

ROOT = Path(__file__).resolve().parents[2]
BASE.KEYMAP = KEYMAP
BASE.CROSS_CHECK = ROOT / "config/c2-ide-exit-keymap-probe-20260928.json"
BASE.CORE_SNAPSHOT = ROOT / (
    "tests/bytecode/dialect-v2/fixtures/c2-ide-exit-core-source-snapshot-20260928.json")

# Filled from the inspected 2.5.0 transport, with only IDE exit comments changed.
SOURCE_GUARDS = {'src/optional/c2_kernal_input_capture.s': '67764adde6942fc7c9d1e65dedd448a363b7a6ebb27ded8df955db83c297b1aa',
 'src/c2_kernal_window.s': '4bf39318a2b21868a542ed2d6b2f0b4ee97c8beff9de44ae48b2d26f736ee650',
 'src/interrupt.c': '5abfbb90ae4dea852206cad87f7e5213527fd7221bd7b89025960ccde8f01a4c',
 'src/vm.c': 'adc0c2531d8daf9bc50a5f10c5e23c237e3b0d90aae7e93ccb2d133f5c10ca35',
 'src/key_event_object.h': '24f86da798898d2a927c37515f091b743844cdcfd4eb540b632a8330d2a24322',
 'src/petscii_normalization.h': 'a1f1df0728b9d7529d6764b9d3e5b048dc4f3835a78cb310d4a4f1477e17cff5',
 'tools/host-lisp/bytecode_p0_compiler.py': '21340c54a243f91018cfaf572d8545c3e6791a17be93647ee9d250dc89e97c98',
 'lib/ide-ui.lisp': '8a66f2ee227e528656222009fba59354203f64f3a90e3ed50615d016366acdf8'}
HISTORY = {'tools/host-lisp/c2_l_full_keymap_end_to_end_gate.py': 'e6b6cf7383837bf38b12ec10fa746c79e9030b60b18ccd47e4b3be568f59fe3f',
 'config/c2-l-full-keymap-probe.json': '4bb5f6fe8decb2c5a5eca3179295cfa73f7ccadf8d8ca2cc77a2a8a71d136ea2',
 'tests/bytecode/dialect-v2/fixtures/c2-l-full-keymap-core-source-snapshot.json': '75fac139bfc0a52d986ffaeff11e203f01b4c659774de87bd749e59e16bd0194'}
EXIT = {'id': 'cx-exit-q',
 'canonical_binding_source': 'config/v11-l-lite-keymap.json#bindings',
 'producer': [{'table': 'matrix_petscii_control', 'index': 23, 'modifiers': 4, 'raw': 24},
              {'table': 'matrix_petscii_normal', 'index': 62, 'modifiers': 0, 'raw': 81}],
 'ring_bytes': [24, 113],
 'poll_key_primitive': 14,
 'codes': [24, 113],
 'command': 1015,
 'route': 13}


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def source_bundle():
    bundle = BASE.source_bundle()
    bundle["exit_sources"] = {p: (ROOT / p).read_text() for p in SOURCE_GUARDS}
    bundle["history"] = {p: BASE.sha(ROOT / p) for p in HISTORY}
    return bundle


def ring_event(raw, modifiers):
    """capture_commit -> active ring decoder -> shared event normalizer."""
    if raw == 3:
        return None
    encoded = raw
    if raw == 0xA0 or 0xC1 <= raw <= 0xDA:
        encoded &= 0x7F
    elif 0x41 <= raw <= 0x5A:
        encoded |= 0x20
    if encoded == 255 and modifiers & 4:
        encoded = 160
    elif encoded == 120 and modifiers & 16:
        encoded = 193
    code, mask = encoded, 0
    if code == 160:
        code, mask = 255, 4
    elif code == 193:
        code, mask = 88, 16
    elif 0x41 <= code <= 0x5A:
        code |= 0x80
    return encoded, BASE.normalise(code, mask)


def validate_exit(bundle, *, run_lisp):
    BASE.require(bundle["history"] == HISTORY, "key-path predecessor drift")
    BASE.require({p: digest(s) for p, s in bundle["exit_sources"].items()}
                 == SOURCE_GUARDS, "inspected ring/poll-key source closure drift")
    BASE.require(bundle["cross_check"].get("exit_sequence") == EXIT,
                 "physical exit cross-check drift")
    contract = bundle["contract"]
    KEYMAP.validate(contract)
    BASE.require(bundle["generated"] == KEYMAP.render_lisp(contract),
                 "generated exit dispatch drift")
    row = next(r for r in contract["bindings"] if r["id"] == "cx-exit-q")
    BASE.require(row["codes"] == [24, 113] and row["command"] == 1015,
                 "C-x q authority drift")
    command = next(r for r in contract["commands"] if r["id"] == 1015)
    BASE.require(command["route"] == "exit" and KEYMAP.ROUTE_IDS["exit"] == 13,
                 "exit route drift")
    events, encoded = [], []
    for producer in EXIT["producer"]:
        raw = BASE.table_value(bundle["matrix"], producer["table"], producer["index"])
        BASE.require(raw == producer["raw"], "physical exit producer drift")
        byte, event = ring_event(raw, producer["modifiers"])
        encoded.append(byte)
        events.append(event)
    BASE.require(encoded == [24, 113] and events == [(24, ()), (113, ())],
                 "Ctrl-X/release-Ctrl/q active-ring chain drift")
    BASE.require(ring_event(3, 4) is None, "physical Ctrl-C must be drained")
    ctrl_q = BASE.table_value(bundle["matrix"], "matrix_petscii_control", 62)
    BASE.require(ctrl_q == 17 and ring_event(ctrl_q, 4)[1] == (17, ()),
                 "Ctrl-Q changed into an exit suffix")
    codes = [e[0] for e in events]
    cases = [
        {"name": "producer-ring-poll-key-cx-q-dispatch",
         "input": KEYMAP.sequence_expr(codes), "expect": "1015"},
        {"name": "producer-ring-poll-key-cx-q-clears-prefix",
         "input": KEYMAP.sequence_expr(codes)[:-1]
             + " (symbol-value (quote ide-event-command)))", "expect": "NIL"},
        {"name": "producer-exit-route",
         "input": "(%ide-command-route 1015)", "expect": "13"},
    ]
    if run_lisp:
        from mvp_prelude_m1_eval_oracle import (
            DEFAULT_PRELUDE, Env, check_case, load_prelude)
        load_prelude(DEFAULT_PRELUDE, reset=True)
        load_prelude(BASE.GENERATED, reset=False)
        # The generated dispatcher calls ide-event-code from the bound UI
        # source; load its real definition just as the full IDE oracle does.
        load_prelude(ROOT / "lib/ide-ui.lisp", reset=False)
        env = Env()
        for case in cases:
            ok, message = check_case(case, env)
            BASE.require(ok, message)
    return {"producer": EXIT["producer"], "ring_bytes": encoded,
            "poll_key_primitive": 14, "lisp_events": events,
            "command": 1015, "route": 13,
            "executed_lisp_cases": len(cases) if run_lisp else 0,
            "physical_control_c": "discarded-before-Lisp",
            "source_guards": SOURCE_GUARDS}


def mutation_tests(bundle):
    mutations = []
    for path in SOURCE_GUARDS:
        b = copy.deepcopy(bundle)
        b["exit_sources"][path] += "\nsource drift\n"
        mutations.append(("source-closure:" + path, b))
    for key in ("history",):
        b = copy.deepcopy(bundle)
        b[key][next(iter(b[key]))] = "0" * 64
        mutations.append((key, b))
    for codes in ([24, 113], [24, 3]):
        b = copy.deepcopy(bundle)
        b["contract"]["bindings"] = [r for r in b["contract"]["bindings"]
                                     if r["codes"] != codes]
        mutations.append(("missing-exit:" + str(codes), b))
    b = copy.deepcopy(bundle)
    b["cross_check"]["exit_sequence"]["producer"][1]["modifiers"] = 4
    mutations.append(("ctrl-not-released", b))
    for table, index, raw in (("matrix_petscii_normal", 62, "51"),
                              ("matrix_petscii_control", 23, "18")):
        import re
        b = copy.deepcopy(bundle)
        text = b["matrix"]
        start = text.index("signal " + table + " : key_matrix_t := (")
        tail, count = re.subn(rf'({index}\s*=>\s*x")' + raw + '"',
                             r'\g<1>00"', text[start:], count=1,
                             flags=re.IGNORECASE)
        BASE.require(count == 1, "cannot construct producer mutation")
        b["matrix"] = text[:start] + tail
        mutations.append(("producer:" + table, b))
    for name, b in mutations:
        try:
            validate_exit(b, run_lisp=False)
        except (BASE.GateError, KEYMAP.KeymapError):
            pass
        else:
            raise BASE.GateError("exit mutation survived: " + name)
    return len(mutations)


def main():
    bundle = source_bundle()
    inherited = BASE.validate(bundle, run_oracle=True)
    inherited["mutations_rejected"] = BASE.mutation_tests(bundle)
    # The historical status wording exceeds this source-only evidence boundary.
    inherited["status"] = "passed-source-chain-and-host-Lisp-oracle"
    result = {"status": "passed-IDE-exit-source-authority",
              "claim_limit": bundle["cross_check"]["claim_limit"],
              "inherited": inherited,
              "exit": validate_exit(bundle, run_lisp=True),
              "exit_mutations_rejected": mutation_tests(bundle),
              "history": HISTORY,
              "bindings": {str(p.relative_to(ROOT)): BASE.sha(p) for p in (
                  KEYMAP.CONTRACT, BASE.GENERATED, BASE.CROSS_CHECK,
                  BASE.CORE_SNAPSHOT, Path(__file__), Path(KEYMAP.__file__))}}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (BASE.GateError, KEYMAP.KeymapError, OSError, ValueError, KeyError) as exc:
        print("IDE exit key path: FAIL: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
