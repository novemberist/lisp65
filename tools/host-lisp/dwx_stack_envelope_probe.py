#!/usr/bin/env python3
"""Execute synthetic observer controls headlessly; never a product measurement."""
import argparse
import json
import os
from pathlib import Path
import re

import dwx_retroactive_red_replay as R
from elf_truth import ElfTruth
from dwx_stack_envelope_tool import ROOT, OUT


def main():
    medium = ROOT / "build/v2.1/f011-buffered-repair-r1/packed-prefilter/comfort/lisp65-v2.1-f011-comfort.d81"
    elf = ROOT / "build/v2.1/f011-buffered-repair-r1/wplto/lisp65-c2-substitution-linked.prg.elf"
    truth = ElfTruth.read(elf, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    main_pc, vm = truth.symbol("main").value, truth.symbol("vm_run_dir")
    helper = 0x200
    binding = f"{main_pc:x},{vm.value:x},{vm.value + vm.bytes:x},{helper:x},2"
    previous = os.environ.get("LISP65_DWX_STACK_BIND")
    os.environ["LISP65_DWX_STACK_BIND"] = binding
    output = OUT / "synthetic-controls"
    output.mkdir(exist_ok=False)
    args = argparse.Namespace(xemu=OUT / "build/bin/xmega65.native",
        rom=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM')),
        sd_image=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img')), timeout=120)
    run = None
    results = []
    try:
        run = R.start_run("envelope-control", medium, output, args)
        monitor = run["monitor"]
        def put(address, data):
            for i in range(0, len(data), 16):
                monitor.command(f"s {address + i:08x} " + " ".join(f"{v:02x}" for v in data[i:i+16]))
            assert monitor.memory_range(address, len(data)) == data
        def step():
            raw = monitor.command("t")
            match = re.search(r"^\s*([0-9a-f]{4})\s+([0-9a-f]{2})\s+", raw, re.I | re.M)
            assert match, raw
            return int(match[1], 16)
        for name, with_checkpoint in (("ten-push-control", True), ("checkpoint-omitted", False)):
            monitor.command("t1")
            put(helper, bytes([0xBA, 0xE0, 0, 0xA9, 0, 0x2A, 0x49, 1, 0x60]))
            # Bring SP above every old product frame before the synthetic
            # scope. Neither these bytes nor this stack state are a product.
            code = bytearray([0x78, 0xA2, 250, 0x9A, 0xEA, 0xA2, 120, 0x9A, 0xEA])
            reset_pc = 0x220 + len(code)
            if with_checkpoint:
                code.extend([0x20, 0, 2])
            code.extend([0x48] * 10 + [0x68] * 10)
            stop = 0x220 + len(code)
            code.extend([0x4C, stop & 255, stop >> 8])
            put(0x220, code)
            monitor.command("g 0220")
            for _ in range(12):
                if step() == reset_pc:
                    break
            else:
                raise RuntimeError("synthetic setup did not reach reset point")
            monitor.command("~stackreset")
            for _ in range(50):
                if step() == stop:
                    break
            else:
                raise RuntimeError("synthetic control did not complete")
            raw = monitor.command("~stackenvelope")
            fields = {key: int(value) for key, value in re.findall(
                r"\b(bound|post|irq|min|hits|scopes|wraps|invalid)=([0-9]+)", raw)}
            passed = (fields["bound"] == 1 and fields["post"] == 8
                      and fields["hits"] == 1 and fields["min"] == 110
                      and fields["wraps"] == 0 and fields["invalid"] == 0)
            results.append(dict(case=name, monitor=raw, fields=fields, passes_oracle=passed))
            assert passed == with_checkpoint, results[-1]
    finally:
        if run is not None:
            run["monitor"].command("t1")
            outputs = R.finish_run(run)
        else:
            outputs = None
        if previous is None:
            os.environ.pop("LISP65_DWX_STACK_BIND", None)
        else:
            os.environ["LISP65_DWX_STACK_BIND"] = previous
        (output / "receipt.json").write_text(json.dumps(dict(
            kind="synthetic-observer-controls", rows=results, outputs=outputs,
            binary=R.bind(args.xemu), existing_medium=R.bind(medium), environment_binding=binding,
            guest_product_measurement=False, product_builds=0, new_host_images=0,
            device_contacts=0), indent=2) + "\n")
    print("PASS: synthetic observer control and omitted-checkpoint mutation; no candidate measurement")


if __name__ == "__main__":
    main()
