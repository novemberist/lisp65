#!/usr/bin/env python3
"""Comfort's one display repair: no native-prompt writer on output rows."""
from __future__ import annotations

import argparse
from contextlib import contextmanager

import c2_v210_comfort_media_card as BASE
import c2_v190_native_prompt_editor_display_repair_r7 as DISPLAY
import evidence_era as ERA

ROOT = BASE.ROOT
BUILD = ROOT / "build/v2.1/comfort-display-repair-r1"
RAW = BUILD / "raw/repl-comfort.manifest.json"
MANIFEST = BUILD / "repl-comfort.manifest.json"
MEDIUM = BUILD / "lisp65-v2.1-comfort.d81"
RECEIPT = BUILD / "receipt.json"
SOURCE = ROOT / "lib/repl-comfort.lisp"


@contextmanager
def world():
    replacements = {"BUILD": BUILD, "MANIFEST": MANIFEST,
                    "BLOB": BUILD / "repl-comfort.blob.bin",
                    "ARTIFACT": BUILD / "repl-comfort.l65s", "INDEX": BUILD / "l65index",
                    "MEDIUM": MEDIUM, "HOST_BUILD": BUILD / "host-execution"}
    previous = {name: getattr(BASE, name) for name in replacements}
    try:
        for name, value in replacements.items():
            setattr(BASE, name, value)
        yield
    finally:
        for name, value in previous.items():
            setattr(BASE, name, value)


def source_gate() -> dict:
    before = ERA.era_blob("bcbcbf41", "lib/repl-comfort.lisp").decode()
    old = "(progn\n            (%rl-screen-tail nil 0 0 (- row 1) 0 -2)\n                  (%repl-prompt row))"
    BASE.require(before.count(old) == 1, "sealed handoff occurrence drift")
    expected = before.replace(old, "(%repl-prompt row)")
    BASE.require(BASE.C.parse_all(SOURCE.read_text()) == BASE.C.parse_all(expected),
                 "repair exceeds the single handoff deletion")
    for tag in ("row = -1", "row = -2", "-34 <= row < -2", "row < -34"):
        BASE.require(tag in SOURCE.read_text(), "row protocol documentation incomplete")
    return {"predecessor": ERA.era_bind("bcbcbf41", SOURCE), "source": BASE.bind(SOURCE),
            "changed_form": "%repl-step", "new_tags": 0, "new_helpers": 0}


def emit() -> dict:
    suite = BASE.STD._read_suite(str(BASE.COMFORT_SUITE))
    # This carrier compiles objects only. All nine behavior cases run below
    # over the product-derived directory, not this historical resident suite.
    suite["cases"] = [{"name": "emission-only-no-behavior-claim", "expr": "nil", "expect": "nil"}]
    BASE.STD.emit_artifacts(str(BASE.COMFORT_SUITE), suite,
                            str(RAW.with_suffix("").with_suffix("")), artifact_role="disk-lib")
    with world():
        value, blob = BASE.composed_value(RAW)
        BASE.write(BASE.BLOB, blob)
        BASE.write(MANIFEST, value)
    old = BASE.F.emit_image("old", "repl", BASE.PREDECESSOR_COMFORT)
    new = BASE.F.emit_image("new", "repl", RAW)
    changes = []
    for a, b in zip(old.manifest["entries"], new.manifest["entries"]):
        a_raw = old.code[a["blob_offset"]:a["blob_offset"]+a["length"]]
        b_raw = new.code[b["blob_offset"]:b["blob_offset"]+b["length"]]
        BASE.require(a["name"] == b["name"] and b["length"] < 255, "object population/ceiling drift")
        changed = a_raw != b_raw
        BASE.require(changed == (a["name"] == "%repl-step"), "unexpected object difference")
        changes.append({"name": a["name"], "before": len(a_raw), "after": len(b_raw),
                        "byte_identical": not changed})
    BASE.require(len(changes) == 4, "Comfort object population drift")
    return {"objects": changes, "before_bytes": len(old.code), "after_bytes": len(new.code),
            "resident_bytes": 0, "new_names": 0}


class AtInput(Exception):
    pass


class FrameVM(DISPLAY.TargetFrameVM):
    """Reuse the B-light 25-row driver model; stop at the input seam."""
    def _callprim(self, prim_id, argc, stack, pc=None, native_base=0, frame_slots=0):
        if prim_id == 60:
            raise AtInput
        # B-light's sequential driver semantics are retained, but its old
        # result-return stop is not the seam of this witness.
        if prim_id == 45 and argc:
            self.sequential(BASE.B.fixval(stack[-1]))
        dispatch = (self.historical_screen_dispatch
                    if prim_id in (11, 12) and self.historical_screen_dispatch
                    else BASE.B.P0VM._callprim)
        return dispatch(self, prim_id, argc, stack, pc=pc,
                                     native_base=native_base, frame_slots=frame_slots)

    def _invoke_primitive_name(self, name, args, native_base=0):
        if name == "key-event":
            raise AtInput
        return super()._invoke_primitive_name(name, args, native_base=native_base)


def frame(host, entry="%repl-step") -> dict:
    vm = FrameVM(heap=host.heap, directory=host.directory,
                 historical_screen_era=DISPLAY.DISPLAY.SCREEN_ORACLE_ERA,
                 code_names=host.code_names, max_steps=100000,
                 private_key_event_modes=True, abi_profile="dialect-v2", abi_ledger=host.ledger)
    for row in range(24):
        text = f"row {row:02d}: protected output".ljust(80)
        vm.screen_cells[row*80:(row+1)*80] = list(text.encode())
    message = "*** reader: unmatched close parenthesis".ljust(80)
    vm.screen_cells[23*80:24*80] = list(message.encode())
    vm.screen_cells[24*80:] = [32]*80
    before = bytes(vm.screen_cells)
    args = [BASE.B.obj_from_json(host.heap, x) for x in [None, {"string": ""}, 0]] if entry == "%repl-step" else []
    try:
        vm.run(host.directory[host.heap.intern(entry)], args)
    except AtInput:
        pass
    else:
        raise RuntimeError("framebuffer witness did not reach input seam")
    after = bytes(vm.screen_cells)
    return {"before": before.decode(), "after": after.decode(),
            "protected_rows_unchanged": before[:24*80] == after[:24*80],
            "prompt_row": after[24*80:].decode(), "surface_bytes": len(after)}


def host_gate() -> dict:
    old_host = BASE.product_host(BUILD / "frame-old")
    BASE.append_manifest(old_host)
    with world():
        host = BASE.product_host(BUILD / "frame-new")
        append = BASE.append_manifest(host)
        good = frame(host)
        native = frame(host, "%native-read-line")
        explicit = frame(host, "read-line")
        cases = [BASE.execute_case(host, case, i) for i, case in enumerate(BASE.load(BASE.COMFORT_SUITE)["cases"])]
    bad = frame(old_host)
    old_explicit = frame(old_host, "read-line")
    BASE.require(good["protected_rows_unchanged"] and good["prompt_row"] == "l65> ".ljust(80)
                 and native["protected_rows_unchanged"] and native["prompt_row"] == "lisp65> ".ljust(80),
                 "25-row handoff/prompt ownership red")
    BASE.require(not bad["protected_rows_unchanged"] and
                 bad["after"][23*80:24*80] == "lisp65> er: unmatched close parenthesis".ljust(80),
                 "old eight-cell-overwrite mutation did not reproduce")
    BASE.require(explicit == old_explicit, "explicit read-line framebuffer changed")
    return {"framebuffer": good, "native": native,
            "old_overwrite_mutation": bad, "mutation_rejected": True,
            "explicit_read_line_identical_at_input": True, "host_cases": cases, "append": append}


def packed_gate() -> dict:
    with world():
        files = BASE.V17.LIBMEDIA.L65I.D81.visible_files(MEDIUM.read_bytes())
        actual = files[b"REPL-COMFORT"]
        expected = BASE.V17.LIBMEDIA.measured(("repl-comfort", "repl", "repl", MANIFEST, ()),
                                             (1, 1), BASE.PRODUCT_BUILD_ID)[1]
        def require_generation(payload):
            BASE.require(payload == expected, "packed bytes do not equal the proved manifest world")
        require_generation(actual)
        closure = BASE.CLOSURE.derive(BASE.PRODUCT_MANIFEST, [MANIFEST])
        BASE.CLOSURE.require_closed(closure)
        candidate = BASE.F.emit_image("candidate", "repl", MANIFEST)
        raw = BASE.F.emit_image("raw", "repl", RAW)
        _, support, _ = BASE._selected_support()
        ide = BASE.F.emit_image("ide", "ide", BASE.product_ide_manifest())
        offset, size = support["blob_offset"], support["length"]
        BASE.require(candidate.code[:size] == ide.code[offset:offset+size] and
                     candidate.code[size:] == raw.code and files.get(b"V16CORE") is None,
                     "packed generation/owner coherence red")
        mutant = bytearray(actual); mutant[-1] ^= 1
        try:
            require_generation(bytes(mutant))
        except BASE.CardError:
            pass
        else:
            raise BASE.CardError("packed-byte mutation survived")
        return {"closure": closure, "artifact": BASE.bind(BASE.ARTIFACT),
                "packed_equals_proved_generation": True, "anonymous_support_equals_product": True,
                "changed_packed_byte_rejected": True, "v16core": False}


def build() -> None:
    source = source_gate()
    attribution = emit()
    host = host_gate()
    # No medium is packed before the full-framebuffer and old-state mutation.
    with world():
        media = BASE.build_medium()
    packed = packed_gate()
    receipt = {"status": "HOST AND PACK GATES GREEN; DWX PENDING", "recorded_on": ERA.stable_recorded_on(RECEIPT),
               "source": source, "attribution": attribution, "host": host,
               "media": media, "packed": packed, "product": BASE.product_identity(),
               "budget": {"product_wplto": 0, "product_links": 0, "repair_media": 1, "device_contacts": 0}}
    BASE.write(RECEIPT, receipt)
    print("Comfort repair HOST/PACK PASS; DWX pending", flush=True)


@ERA.in_host_source_world("520352a6")
def check() -> None:
    value = BASE.load(RECEIPT)
    BASE.require(value["source"] == source_gate() and value["product"] == BASE.product_identity()
                 and value["packed"] == packed_gate(), "repair authority/product/pack drift")
    BASE.require(value["host"] == host_gate(), "repair host witness drift")
    print("Comfort display repair CHECK PASS")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "check"))
    args = parser.parse_args()
    build() if args.action == "build" else check()
