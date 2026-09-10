#!/usr/bin/env python3
"""Native seed envelope over the explicitly authorized, staged seed image."""
import argparse
import json
import os
from pathlib import Path
import re
import time

import dwx_retroactive_red_replay as R
import dwx_comfort_resume as C
import hardware_sp_link_authority as SP
from dwx_stack_envelope_tool import ROOT, OUT
from elf_truth import ElfTruth


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packed_receipt", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--threshold-probe", type=Path,
                        help="RAM-only feasibility probe of measured T; never final ELF qualification")
    args = parser.parse_args()
    packed = json.loads(args.packed_receipt.read_text())
    assert packed['status']=='PACKED SEED MEASUREMENT IMAGE; NOT PRODUCT OR DEVICE ACCEPTANCE'
    assert packed['authority']['commit']=='44f48798'
    elf=Path(packed['elf']['path']);assert SP.bind(elf)==packed['elf']
    prg=Path(packed['artifacts']['c2-resident-prg']['path'])
    assert SP.bind(prg)==packed['artifacts']['c2-resident-prg']
    SP.inspect_emission(elf, ROOT / "tools/llvm-mos/bin/llvm-readobj", 0)
    binding = SP.observer_binding(elf, ROOT / "tools/llvm-mos/bin/llvm-readobj")
    threshold=0
    if args.threshold_probe:
        measured=json.loads(args.threshold_probe.read_text())
        threshold=SP.measured_threshold(measured,elf,[r['id'] for r in measured['rows']])
    truth = ElfTruth.read(elf, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
                          include_section_data=True)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    medium=Path(packed['medium']['path']);assert SP.bind(medium)==packed['medium']
    session_path = ROOT / "config/v2.1-comfort-buffered-repair-device-session.json"
    session = json.loads(session_path.read_text())
    smokes = next(r for r in session["rows"] if r["id"] == "G7")["performance_forms"]
    controls = [("define-probe", "(defun v20-perf-probe (x) (+ x 1))", "V20-PERF-PROBE")]
    controls += [("smoke-" + str(i+1), row["form"], expected)
                 for i, (row, expected) in enumerate(zip(smokes, ("2", "(9 2)", "98", "42"), strict=True))]
    controls += [("define-list", "(defun sp-list (n xs) (if (= n 0) xs (sp-list (- n 1) (cons 7 xs))))", "SP-LIST")]
    for n in (20, 50):
        controls += [(f"list-setup-{n}", f"(progn (setq sp-xs (sp-list {n} nil)) 777)", "777"),
                     (f"mapcar-{n}", "(length (mapcar (function abs) sp-xs))", str(n)),
                     (f"append-{n}", "(length (append sp-xs sp-xs))", str(2*n))]
    # A bounded successful depth is an envelope row, not a new safe-depth claim.
    # The final nonzero-threshold world separately owes the overflow/refusal rows.
    controls += [("define-depth", "(defun sp-depth (n) (if (= n 0) 0 (+ 1 (sp-depth (- n 1)))))", "SP-DEPTH"),
                 ("recursion-bounded", "(sp-depth 3)", "3"),
                 ("printer-bounded", "(progn (print '(((7)))) (terpri) 811)", "811"),
                 ("terminal-d5-marker", "(+ 4 5)", "9")]
    (output / "row-contract.json").write_text(json.dumps(dict(rows=controls,
        smokes_authority=R.bind(session_path), threshold=threshold, final_refusal_rows_pending=True), indent=2)+"\n")
    env = os.environ.get("LISP65_DWX_STACK_BIND")
    os.environ["LISP65_DWX_STACK_BIND"] = binding["environment"]
    runtime = argparse.Namespace(xemu=OUT / "build/bin/xmega65.native",
        rom=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM')),
        sd_image=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img')),
        timeout=420)
    run = None
    rows = []
    error = None
    try:
        run = R.start_run("native-seed", medium, output, runtime)
        m = run["monitor"]
        def snapshot(name, form=None, okay=True):
            raw = m.command("~stackenvelope")
            (output / (name+"-envelope.txt")).write_text(raw)
            screen = m.screen()
            (output / (name+"-screen.txt")).write_text(screen)
            fields = {k:int(v) for k,v in re.findall(r"\b(bound|post|irq|min|hits|scopes|wraps|invalid)=([0-9]+)", raw)}
            row = dict(id=name, form=form, completed=okay, fields=fields,
                       wrapped=bool(fields["wraps"]), component="post-checkpoint",
                       bytes=fields["post"], elf_sha256=R.sha256(elf))
            rows.append(row)
            print(json.dumps(row), flush=True)
            assert fields["bound"] == 1 and not fields["invalid"] and not fields["wraps"] and okay, row
        # Witness the loaded seed, not the PRG file's name alone.
        m.command("t1")
        for name in ("lisp_hardware_stack_low", "lisp_hardware_stack_require", "c2_map_cpu_selector"):
            sym = truth.symbol(name)
            section = truth.section(sym.section)
            off = sym.value-section.address
            expected = truth.section_bytes(sym.section)[off:off+sym.bytes]
            assert m.memory_range(sym.value, len(expected)) == expected, "loaded seed identity mismatch: "+name
        snapshot("boot")
        if threshold:
            operand=truth.symbol('lisp_hardware_stack_low').value+2
            assert m.memory_range(operand,1)==b'\0'
            m.command(f's {operand:08x} {threshold:02x}')
            assert m.memory_range(operand,1)==bytes([threshold])
            (output/'ram-probe-mutation.json').write_text(json.dumps(dict(
                address=operand,before=0,after=threshold,measurement=SP.bind(args.threshold_probe),
                limitation='Boot ran at T=0; following forms run with this one RAM operand changed. Frozen ELF/PRG unchanged.'),indent=2)+'\n')
        m.command("t0")
        for name, form, result in controls:
            before = m.screen()
            m.command("~stackreset")
            m.type_text(form+"\n")
            deadline = time.monotonic()+25
            okay = False
            while time.monotonic() < deadline:
                screen = m.screen()
                if form.startswith("(time "):
                    matched = any(C.fresh_result(before, screen, str(n)+" "+result) for n in range(10))
                else:
                    matched = C.fresh_result(before, screen, result)
                okay = C.active(screen) == "LISP65>" and matched
                if okay or R.ROWS.decoded_framebuffer(screen).count("*** E29") >= 2:
                    break
                time.sleep(.03)
            m.command("t1")
            snapshot(name, form, okay)
            if name != "terminal-d5-marker":
                m.command("t0")
        d5 = {}
        for name in ("nsym", "npool"):
            sym = truth.symbol(name)
            raw = m.memory_range(sym.value, sym.bytes)
            d5[name] = dict(address=sym.value, raw=raw.hex(), value=int.from_bytes(raw,"little"))
        (output / "d5-raw.json").write_text(json.dumps(d5, indent=2)+"\n")
    except Exception as exc:
        error = repr(exc)
        raise
    finally:
        outputs = None
        if run is not None:
            run["monitor"].command("t1")
            outputs = R.finish_run(run)
        if env is None:
            os.environ.pop("LISP65_DWX_STACK_BIND", None)
        else:
            os.environ["LISP65_DWX_STACK_BIND"] = env
        (output / "receipt.json").write_text(json.dumps(dict(
            status="HALT" if error else "NATIVE SEED ENVELOPE; NOT FINAL QUALIFICATION",
            error=error, rows=rows, binding=binding, observer=R.bind(runtime.xemu),
            prg=SP.bind(prg), medium=SP.bind(medium), packed_receipt=SP.bind(args.packed_receipt),outputs=outputs,
            new_images_in_this_execution=0, device_contacts=0, threshold=threshold,
            ram_only_probe=bool(threshold)), indent=2)+"\n")


if __name__ == "__main__":
    main()
