#!/usr/bin/env python3
"""Bound, read-only Comfort r2 prefilter; stop at the first unmatched oracle."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import c2_v210_comfort_media_card as CARD
import dwx_retroactive_red_replay as R
import dwx_prefilter_blind_spot_contract as BLIND
from elf_truth import ElfTruth

ROOT = Path(__file__).resolve().parents[2]
SESSION = ROOT / "config/c2-v200-comfort-return-device-session-r2.json"


def active(screen: str) -> str:
    return R.ROWS.decoded_framebuffer(screen).splitlines()[-1].replace("{$A0}", " ").strip()


def fresh_result(before: str, after: str, line: str | None) -> bool:
    if line is None:
        return True
    needle = line.upper()
    return (R.ROWS.decoded_framebuffer(after).splitlines().count(needle) >
            R.ROWS.decoded_framebuffer(before).splitlines().count(needle))


def selftest() -> None:
    before = "(7 8)\nL65> (LIST 7 8)\n"
    stale = "(7 8)\nLISP65>\nL65>\n"
    emitted = "(7 8)\n(7 8)\nL65>\n"
    R.require(not fresh_result(before, stale, "(7 8)"), "stale output accepted as new evaluation")
    R.require(fresh_result(before, emitted, "(7 8)"), "new output rejected")
    R.require(fresh_result("ABCDEFG\n", "ABCDEFG\n7", "7"), "last-row result rejected")
    R.require(not fresh_result("7", "7", "7"), "stale last-row result accepted")
    print("Comfort result oracle PASS stale-output mutation=RED fresh-output=GREEN")


def execute(out: Path, repair_receipt: Path | None = None, calibrate_collection: bool = False,
            successor_receipt: Path | None = None) -> dict:
    BLIND.validate_contract(BLIND.load_json(BLIND.CONTRACT_PATH))
    R.check()
    contract = R.load(R.CONTRACT_PATH)
    binary = R.verify_binding(contract["inputs"]["cycle_probe_binary"], "navigation fork")
    if successor_receipt is not None:
        import f011_status_comfort_prefilter as SUCCESSOR
        R.require(repair_receipt is None and successor_receipt.resolve()==SUCCESSOR.RECEIPT.resolve(), 'unbound successor')
        media, product_elf = SUCCESSOR.check()
    elif repair_receipt is None:
        media = CARD.MEDIUM
        R.require(R.sha256(media) == "d7c5f6deea29eb554bda3d41118197c76a687b517abbc3a75e14c3919eb5287b", "r2 medium changed")
    else:
        import c2_v210_comfort_display_repair as REPAIR
        repair_receipt = repair_receipt.resolve()
        R.require(repair_receipt.resolve() == REPAIR.RECEIPT.resolve(), "unbound repair receipt")
        REPAIR.check()
        media = R.verify_binding(R.load(repair_receipt)["media"]["medium"], "repaired packed medium")
    if successor_receipt is None:
        product_elf = CARD.PRODUCT_ELF
        R.require(R.sha256(product_elf) == "f02d6997e33ae6c1059be1a9f81711d219f430c26e3144772124fd9a979366cf", "r2 product changed")
    out.mkdir(parents=True, exist_ok=False)
    args = argparse.Namespace(xemu=binary, rom=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM')),
                              sd_image=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img')), timeout=300)
    truth = ElfTruth.read(product_elf, llvm_readobj=Path("/usr/bin/llvm-readobj"), include_section_data=True)
    symbols = {name: truth.symbol(name) for name in
               ("nsym", "npool", "gc_runs", "lisp65_symbol22_latch_state", "c2_symbol22_repl_buf")}
    run = R.start_run("comfort", media, out, args)
    m = run["monitor"]
    results = []
    stopped = {}
    calibration = None
    session_rows = {row["id"]: row for row in R.load(SESSION)["rows"]}

    def snapshot(name: str) -> str:
        screen = m.screen()
        path = out / (name + "-framebuffer.txt")
        path.write_text(screen)
        results.append({"id": name, "framebuffer": R.bind(path), "active": active(screen)})
        return R.ROWS.decoded_framebuffer(screen)

    def wait_active(expected: str) -> None:
        # Ring take acknowledges consumption, not completion of the handler's
        # screen writes. Observe the bound visible oracle after the take.
        deadline = time.monotonic() + 12
        while active(m.screen()) != expected:
            R.require(time.monotonic() < deadline, "active-row rendering did not converge")
            time.sleep(.02)

    def step(name: str, text: str, prompt: str, line: str | None = None) -> None:
        before = m.screen()
        m.type_text(text)
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            screen = m.screen()
            decoded = R.ROWS.decoded_framebuffer(screen)
            if active(screen) == prompt and fresh_result(before, screen, line):
                break
            time.sleep(.03)
        decoded = snapshot(name)
        R.require(results[-1]["active"] == prompt and
                  fresh_result(before, decoded, line), f"{name}: framebuffer oracle red")
        results[-1]["result"] = "PASS"
        print(name + " PASS", flush=True)

    try:
        step("C1-require", "(require 'repl-comfort)\n", "LISP65>", "T")
        if successor_receipt is not None and truth.section('.noinit.lisp65_f011_status').bytes == 0:
            import f011_buffered_repair_product_card as BUFFERED
            R.require(product_elf.resolve()==BUFFERED.ELF.resolve(), 'unbound witness-free successor')
            BUFFERED.witness_absent(truth)
            results.append({'id':'F011-instrument-absent','bytes':0,'result':'PASS',
                            'meaning':'no status-record claim; emitted absence proved'})
        elif successor_receipt is not None:
            R.require(truth.section('.noinit.lisp65_f011_status').bytes==3,
                      'unexpected instrument generation in Comfort world')
            address=truth.section('.noinit.lisp65_f011_status').address
            m.command('t1')
            first=m.memory_range(address,3)
            (out/'f011-first-success-raw.bin').write_bytes(first)
            R.require(first[0]==1 and (first[1]&0x7c)==0x60,'clean require did not retain first-success record')
            results.append({'id':'F011-first-success','address':address,'raw':first.hex(),'result':'PASS',
                            'evidence':R.bind(out/'f011-first-success-raw.bin')})
            m.command('t0')
        step("C1-entry", "(repl)\n", "L65>")
        step("C1-empty-return", "\n", "LISP65>", "NIL")
        step("C1-reentry", "(repl)\n", "L65>")
        step("C2-balanced", "(list 1 3)\n", "L65>", "(1 3)")
        step("C2-multiline-open", "(+ 10\n", "")
        step("C2-multiline-result", "32)\n", "L65>", "42")
        step("C2-history-seed", "(list 7 8)\n", "L65>", "(7 8)")
        keymap = R.load(ROOT / "config/v11-l-lite-keymap.json")
        up = next(row for row in keymap["bindings"] if row["id"] == "cursor-up")["codes"]
        for code in up:
            R.require("DWX keyevent queued" in m.command(f"~keyevent {code:02x} 00"), "Up tuple rejected")
        m.wait_screen(["L65> (LIST 7 8)"])
        recalled = snapshot("C2-history-recalled")
        R.require(results[-1]["active"] == "L65> (LIST 7 8)", "history did not populate active row")
        step("C2-history-evaluated", "\n", "L65>", "(7 8)")
        step("C2-overclose", ")\n", "L65>", "*** READER: UNMATCHED CLOSE PARENTHESIS")
        step("C3-abort", session_rows["C3"]["trigger"]["form"] + "\n", "LISP65>", "*** VM: TYPE ERROR")
        step("C3-reentry", "(repl)\n", "L65>")
        capture = session_rows["C4"]["collection"]
        m.type_text(capture["controller"] + "\n")
        deadline = time.monotonic() + 12
        while not (m.memory16(0xFF8D)[0] != 255 and m.memory16(0xBCFC)[:4] == bytes(4)):
            R.require(time.monotonic() < deadline, "nested Capture origin not reached")
            time.sleep(.02)
        counter = 0
        if calibrate_collection:
            import dwx_comfort_collection_calibration as CAL
            CAL.selftest()
            def calibration_pass(name, authority):
                nonlocal counter
                counter = m.type_and_wait_counters(capture["pattern"], counter)
                wait_active(capture["pattern"])
                snapshot(name + "-typed")
                typed = CAL.sample(m, authority, out, name + "-typed")
                counter = m.type_and_wait_counters("\x08" * capture["delete_events_per_pass"], counter)
                wait_active("")
                snapshot(name + "-deleted")
                deleted = CAL.sample(m, authority, out, name + "-deleted")
                return typed, deleted
            calibration = CAL.calibrate(m, truth, out, capture, calibration_pass, product_elf)
            R.require(counter == 0, "warmup changed counter origin")
            print("C4 warmup derived: " + str(calibration["plan"]["warmup_passes"]), flush=True)
        gc_before = int.from_bytes(m.memory16(symbols["gc_runs"].value)[:2], "little")
        (out / "capture-origin.json").write_text(json.dumps({
            "gc_runs_address": symbols["gc_runs"].value,
            "gc_runs": gc_before,
            "capture_raw": m.memory16(0xBCFC)[:4].hex(),
            "passes": capture["passes"], "warmup_passes": calibration["plan"]["warmup_passes"] if calibration else 0}, indent=2) + "\n")
        counter = 0
        for index in range(capture["passes"]):
            counter = m.type_and_wait_counters(capture["pattern"], counter)
            wait_active(capture["pattern"])
            snapshot(f"C4-pass-{index+1}-typed")
            R.require(results[-1]["active"] == capture["pattern"], "Capture pattern mismatch")
            counter = m.type_and_wait_counters("\x08" * capture["delete_events_per_pass"], counter)
            wait_active("")
            snapshot(f"C4-pass-{index+1}-deleted")
            R.require(results[-1]["active"] == "", "Capture delete did not empty row")
        if calibration:
            calibration["end"] = CAL.sample(m, calibration["plan"]["authority"], out, "measured-window-end")
            CAL.validate_window(calibration["origin"], calibration["start"], calibration["end"])
            print("C4 Collection inside typing window PASS", flush=True)
        before_final = m.screen()
        counter = m.type_and_wait_counters(capture["final_text"] + "\n", counter)
        deadline = time.monotonic() + 12
        while not fresh_result(before_final, m.screen(), str(len(capture["final_text"]))):
            R.require(time.monotonic() < deadline, "fresh Capture length result missing")
            time.sleep(.02)
        m.command("t1")
        stopped = {name: {"address": symbol.value, "raw": m.memory_range(symbol.value, 34 if name == "c2_symbol22_repl_buf" else symbol.bytes).hex()}
                   for name, symbol in symbols.items()}
        stopped["capture"] = {"address": 0xBCFC, "raw": m.memory16(0xBCFC)[:4].hex()}
        (out / "stopped-raw.json").write_text(json.dumps(stopped, indent=2) + "\n")
        snapshot("C4-C6-C7-final-stopped")
        R.require(counter == capture["event_arithmetic"]["expected_each_modulo_256"] and
                  stopped["capture"]["raw"] == bytes([counter]*4).hex(), "final Capture counter mismatch")
        gc_after = int.from_bytes(bytes.fromhex(stopped["gc_runs"]["raw"]), "little")
        nsym = int.from_bytes(bytes.fromhex(stopped["nsym"]["raw"]), "little")
        npool = int.from_bytes(bytes.fromhex(stopped["npool"]["raw"]), "little")
        stopped["derived"] = {"free_slots": 752-nsym, "free_name_bytes": 10208-npool,
                               "gc_runs_before": gc_before, "gc_runs_after": gc_after,
                               "collections": (gc_after-gc_before) % 65536}
        R.require((gc_after-gc_before) % 65536 > 0, "no executed Collection")
        R.require(stopped["lisp65_symbol22_latch_state"]["raw"] == "0000000000", "$22 latch nonzero")
        R.require(752-nsym >= 32 and 10208-npool >= 384, "D5 floor red")
        status = "EXECUTED ROWS PASS; COMPOSED DISPLAY REVIEW REQUIRED"
    except Exception as error:
        status = "STOP: " + str(error)
        m.command("t1")
        snapshot("first-stop")
    outputs = R.finish_run(run)
    receipt = {"format": "lisp65-dwx-comfort-resume-v1", "status": status,
               "executor": R.bind(Path(__file__)),
               "repair_card": R.bind(repair_receipt) if repair_receipt else None,
               "product": R.bind(product_elf), "medium": R.bind(media), "fork": R.bind(binary),
               "successor_card": R.bind(successor_receipt) if successor_receipt else None,
               "session_counterparts": R.bind(SESSION), "rows": results, "stopped": stopped,
               "collection_calibration": calibration,
               "calibration_executor": R.bind(Path(CAL.__file__)) if calibrate_collection else None,
               "outputs": outputs, "device_acceptance_claimed": False,
               "claim_limit": "Functional UART/HWA prefilter only; physical history, timing and feeling remain device mandatory."}
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(status, flush=True)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--repair-receipt", type=Path)
    parser.add_argument("--calibrate-collection", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
    else:
        R.require(args.out is not None, "--out required")
        execute(args.out.resolve(), args.repair_receipt, args.calibrate_collection)
