"""Bind the seven owner-approved Comfort rows without touching a device."""
from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path

import c2_v210_comfort_display_repair as REPAIR
import dwx_comfort_collection_row as COLLECTION
from elf_truth import ElfTruth
from evidence_era import stable_recorded_on

BASE = REPAIR.BASE
ROOT = BASE.ROOT
OUT = ROOT / "config/c2-v210-comfort-device-session.json"
RUNTIME = ROOT / "build/v2.1/comfort-collection-calibration-r2"


def derive():
    REPAIR.check()
    collection = COLLECTION.derive(RUNTIME)
    BASE.require(BASE.load(RUNTIME / "collection-row-binding.json") == collection,
                 "calibrated Collection row not bound")
    previous = BASE.load(ROOT / "config/c2-v200-comfort-return-device-session-r2.json")
    old = {row["id"]: deepcopy(row) for row in previous["rows"]}
    release = BASE.load(ROOT / "config/c2-v200-release-strip-device-session.json")
    smoke = next(row for row in release["rows"] if "performance_forms" in row)
    truth = ElfTruth.read(BASE.PRODUCT_ELF, llvm_readobj=Path("/usr/bin/llvm-readobj"))
    def symbol(name, size=None):
        s = truth.symbol(name)
        return {"symbol": name, "address": s.value, "bytes": size or s.bytes, "encoding": "little-endian"}
    state = symbol("lisp65_symbol22_latch_state")
    payload = symbol("c2_symbol22_repl_buf", 34)
    gc = symbol("gc_runs")
    counters = {"address": 0xBCFC, "bytes": 4, "owner": "reserved Raw-Input",
                "layout": ["raw", "seen", "stored", "taken"]}
    files = BASE.V17.LIBMEDIA.L65I.D81.visible_files(REPAIR.MEDIUM.read_bytes())
    BASE.require(b"INIT.L65" not in files and b"V16CORE" not in files and b"REPL-COMFORT" in files,
                 "single-medium boot/library population drift")
    entry = old["C1"]
    entry.update(id="G2", actions=["At the native prompt submit (require 'repl-comfort).",
        "Submit (repl). At l65> submit one empty balanced line; then enter (repl) again."])
    evaluation = old["C2"]; evaluation["id"] = "G3"
    recovery = old["C3"]
    # Keep the executed error form, but bind its domain authority live.
    domain_path = ROOT / "config/public-surface-domain-contract.json"
    domain = BASE.load(domain_path)
    cell = next(r for r in domain["rows"] if r["name"] == recovery["trigger"]["function"])["cells"][recovery["trigger"]["domain"]]
    BASE.require(cell["classification"] == "error-raised", "abort probe no longer belongs to error-raised domain")
    recovery["trigger"].update(authority=BASE.bind(domain_path),
        classification=cell["classification"], error=cell["error"], detail=cell["detail"])
    recovery.update(id="G4", actions=["At l65> submit (+ nil 32). Observe recovery and the complete diagnostic.",
        "Before any further key, checkpoint LATCH reads state and payload raw-first.",
        "If tag is zero, resume and re-enter Comfort with (repl). Otherwise stop the session."])
    display = old["C5"]; display["id"] = "G5"
    display["expect"].append("The entire diagnostic, including its first eight characters, survives on its own output row.")
    capture = deepcopy(collection["row"]); capture["id"] = "G6"
    capture["binding_limit"] = "Physical counterpart: only owner keys; the explicit checkpoints below authorize read-only stops/resumes, never input injection."
    capture["expect"].append("Single-key and fast typing feel like the hardware-green v1.9 route; owner observation is mandatory.")
    capture["actions"] = [
        "Submit " + capture["collection"]["controller"],
        "On the blank nested row, checkpoint GC-ORIGIN; resume without pressing a key.",
        "Perform the derived warmup passes: each time type the exact 32-character pattern, then delete all 32 characters to blank. Do not press Return between passes.",
        "Checkpoint GC-START after warmup; its GC counter must equal GC-ORIGIN. Resume.",
        "Perform the six measured passes, ordinary pace for 1-2 and fast for 3-6. Observe each exact typed row and each empty deleted row. Do not press Return between passes.",
        "Checkpoint GC-END before typing the final oracle: GC must have increased since GC-START. Resume.",
        "Type abcdefg and Return. At visible 7, no further key; checkpoint CAPTURE reads all four counters, latch and payload.",
        "If green, resume. Let the existing wait finish naturally; do not inject keys or change wait/product state."]
    def point(name, when, reads, resume):
        return {"id": name, "when": when, "read_only": True, "raw_first": True,
                "reads": reads, "resume_if_green": resume,
                "on_red": "remain stopped, no further input; attribute before any action"}
    checkpoints = [
        point("LATCH", "after abort cleanup and native prompt, before any further input", [state,payload], True),
        point("GC-ORIGIN", "blank nested row before any warmup input", [gc,counters], True),
        point("GC-START", "blank row after all warmup passes", [gc,counters], True),
        point("GC-END", "blank row after measured passes, before final text/Return", [gc,counters], True),
        point("CAPTURE", "visible numeric 7 during wait, before next prompt or input", [counters,state,payload], True),
        point("D5", "after performance smokes, final loaded configuration, before any further key", [symbol("nsym"),symbol("npool"),state,payload], False)]
    rows = [{"id": "G1", "group": "native boot without optional libraries",
             "actions": ["Freshly restore the single bound D81, read back and verify SHA before a fresh BASIC boot. No disk swap during boot."],
             "expect": ["WORKBENCH 2.0.0 banner and native lisp65> prompt", "INIT.L65 absence is silent"],
             "failure_attribution": "Boot/D082 failure is a Card-2/product finding, not a Comfort feature finding"},
            entry,evaluation,recovery,display,capture,
            {"id": "G7", "group": "loaded Comfort D5 and performance",
             "actions": ["After the capture wait completes, define (defun v20-perf-probe (x) (+ x 1)).",
                         "Run each performance form once, one submission at a time.",
                         "Checkpoint D5 is terminal and observes repl-comfort plus all session definitions."],
             "performance_forms": smoke["performance_forms"],
             "D5": {"slot_capacity": 752, "name_byte_capacity": 10208,
                    "free_slot_floor": 32, "free_name_byte_floor": 384,
                    "prefilter_before_smoke_definitions_only": {"free_slots": 104,"free_name_bytes":1433}}}]
    value = {"format": "lisp65-v210-comfort-device-session-v1", "recorded_on": stable_recorded_on(OUT),
        "status": "BOUND; OWNER CONTACT NOT STARTED", "authority_commit": "8b22d361",
        "media": {"combined": dict(BASE.bind(REPAIR.MEDIUM), remote_name="V21CFP.D81")},
        "world": BASE.product_identity(), "packed_gates": BASE.bind(REPAIR.RECEIPT),
        "prefilter": BASE.bind(RUNTIME / "receipt.json"),
        "collection_binding": BASE.bind(RUNTIME / "collection-row-binding.json"),
        "claim_scope": {"accepts": ["Comfort semantics", "Comfort composed display"],
            "excludes": ["Matcher/Blink", "Block 3", "B-full canonical prompt swap", "release acceptance"]},
        "choreography": {"single_medium": True, "freezer_operations": 0,
            "fresh_restore_and_SHA_readback_before_each_qualifying_cold_boot": True,
            "physical_owner_keyboard_only_after_boot": True, "automated_input": False,
            "stops": len(checkpoints), "resumes_if_all_green": sum(p["resume_if_green"] for p in checkpoints),
            "no_reset_or_product_memory_writes_after_boot": True},
        "rows": rows, "execution_order": [r["id"] for r in rows], "checkpoints": checkpoints,
        "gc_acceptance": "GC-ORIGIN == GC-START; 0 < (GC-END - GC-START) modulo 65536 < 32768",
        "capture_acceptance": "each visible row exact; GC-START counters 00; GC-END counters 80; CAPTURE counters 88, four identical nonzero bytes",
        "decision_table": {"all-seven-green": "Comfort hardware accepted",
            "daily-use-Comfort-red": "Comfort descopes; feature repair round already spent",
            "rare-cosmetic": "Known Issue with evidence", "tag-nonzero": "stop and read bound payload, no further input",
            "unexpected-error-at-any-row": "no further key; stop and use the LATCH checkpoint's bound state/payload ranges",
            "GC-window-unproved": "not accepted; no inferred Collection", "tool-or-composition-red": "attribute separately; never relabel it as a feature finding"}}
    value["world"]["PRG"] = BASE.bind(BASE.PRODUCT_ELF.with_suffix(""))
    BASE.require(len(rows) == 7 and value["choreography"]["stops"] == 6, "checkpoint population drift")
    return value


def selftest(value):
    mutations = []
    for name in ("missing-GC-start", "GC-after-final-evaluation", "old-payload-address",
                 "missing-warmup", "unbound-medium", "automated-keys", "feature-round-reset"):
        bad = deepcopy(value)
        if name == "missing-GC-start":
            bad["checkpoints"] = [p for p in bad["checkpoints"] if p["id"] != "GC-START"]
        elif name == "GC-after-final-evaluation":
            bad["checkpoints"][3]["when"] = "after final Return and evaluation"
        elif name == "old-payload-address":
            bad["checkpoints"][0]["reads"][1]["address"] = 0xBC89
        elif name == "missing-warmup":
            bad["rows"][5]["collection"]["warmup_passes"] = 0
        elif name == "unbound-medium":
            bad["media"]["combined"]["sha256"] = "0"*64
        elif name == "automated-keys":
            bad["choreography"]["automated_input"] = True
        else:
            bad["decision_table"]["daily-use-Comfort-red"] = "one more repair round"
        try:
            BASE.require(bad == value, "Comfort device binding drift")
        except BASE.CardError:
            mutations.append(name)
        else:
            raise BASE.CardError("session mutation survived: " + name)
    return mutations


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("emit", "check"))
    args = parser.parse_args()
    value = derive()
    selftest(value)
    if args.action == "emit":
        BASE.write(OUT, value)
    else:
        BASE.require(BASE.load(OUT) == value, "Comfort device binding drift")
    print("Comfort device binding PASS rows=7 stops=6 resumes=5 device-contacts=0")
