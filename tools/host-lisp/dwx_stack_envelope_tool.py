#!/usr/bin/env python3
"""Build the host-only, candidate-address-bound stack measurement observer.

This derives from the diagnostic watermark fork, not from a product image.
No product compiler, media packer, device tool or GUI input is invoked.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "build/dwx/xemu-stack-watermark-diagnostic-r3"
OUT = ROOT / "build/dwx/xemu-stack-envelope-diagnostic-r2"
HEADER = ROOT / "tools/host-lisp/fixtures/dwx_stack_envelope.h"
EXPECTED = {
    "xemu/cpu65.c": "935915ab0907a117c083f60f34510e045278bfeb41c2c1356cb6da37e11265bb",
    "targets/mega65/uart_monitor.c": "1ee28feac38e800ce1819a5ae0d5463ab07e0101cbdf5353b0d42406f2f5ee37",
}


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError("observer patch anchor absent/ambiguous: " + old[:80])
    return text.replace(old, new)


def prepare():
    if OUT.exists():
        raise RuntimeError("observer destination already exists; never overwrite a measured tool")
    for name, digest in EXPECTED.items():
        if hashlib.sha256((BASE / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError("diagnostic base identity drift: " + name)
    shutil.copytree(BASE, OUT)
    shutil.copyfile(HEADER, OUT / "xemu/dwx_stack_envelope.h")
    cpu = (OUT / "xemu/cpu65.c").read_text()
    cpu = replace_once(cpu, "/* Diagnostic-only host observer. Never writes emulated RAM or CPU state. */", r'''
/* Candidate-bound observer. All guest addresses come from the ELF-bound
 * runner environment. Missing/invalid binding leaves the observer unarmed. */
#include <stdlib.h>
#include <stdio.h>
#include "dwx_stack_envelope.h"
dwx_sp_envelope dwx_envelope;
unsigned dwx_stack_main_pc, dwx_stack_vm_start, dwx_stack_vm_end, dwx_stack_helper_pc;
int dwx_stack_bound;
static unsigned dwx_stack_binding_read;
static void dwx_stack_bind_environment(void) {
    if (dwx_stack_binding_read) return;
    dwx_stack_binding_read = 1;
    dwx_sp_init(&dwx_envelope);
    const char *raw = getenv("LISP65_DWX_STACK_BIND");
    int consumed = 0;
    if (raw && sscanf(raw, "%x,%x,%x,%x,%u%n", &dwx_stack_main_pc,
            &dwx_stack_vm_start, &dwx_stack_vm_end, &dwx_stack_helper_pc,
            &dwx_envelope.caller_gap, &consumed) == 5 && !raw[consumed]
            && dwx_envelope.caller_gap >= 2 && dwx_envelope.caller_gap <= 255 && dwx_stack_main_pc > 0
            && dwx_stack_main_pc < 65536 && dwx_stack_vm_start > 0
            && dwx_stack_vm_end > dwx_stack_vm_start && dwx_stack_vm_end <= 65536
            && dwx_stack_helper_pc > 0 && dwx_stack_helper_pc < 65536)
        dwx_stack_bound = 1;
}
''')
    cpu = replace_once(cpu, "void dwx_stack_reset(void) {\n    unsigned i;",
                       "void dwx_stack_reset(void) {\n    unsigned i;\n    dwx_sp_row_reset(&dwx_envelope);")
    cpu = replace_once(cpu,
        "(dwx_stack_instruction_pc>=0x455e && dwx_stack_instruction_pc<0x4628)",
        "(dwx_stack_instruction_pc>=dwx_stack_vm_start && dwx_stack_instruction_pc<dwx_stack_vm_end)")
    cpu = replace_once(cpu, "    dwx_stack_observe(1);", """    dwx_stack_observe(1);
    if (dwx_stack_boot_started && !in_hypervisor)
        dwx_sp_before_push(&dwx_envelope, CPU65.s);""")
    old = """    /* Addresses bound to diagnostic ELF 9c9aa484..., checked by the driver. */
    if (!in_hypervisor && CPU65.pc==0xa5e8 && !dwx_stack_boot_started) {
        dwx_stack_boot_started=1; dwx_stack_reset();
    }
    if (!in_hypervisor && CPU65.pc==0x455e) dwx_stack_last_di=CPU65.a | (CPU65.x<<8);
    dwx_stack_observe(0);"""
    new = """    dwx_stack_bind_environment();
    if (dwx_stack_bound && !in_hypervisor && CPU65.pc==dwx_stack_main_pc && !dwx_stack_boot_started) {
        dwx_stack_boot_started=1; dwx_stack_reset();
    }
    if (dwx_stack_bound && !in_hypervisor && CPU65.pc==dwx_stack_vm_start)
        dwx_stack_last_di=CPU65.a | (CPU65.x<<8);
    dwx_stack_observe(0);
    if (dwx_stack_boot_started && !in_hypervisor) {
        if (!CPU65.pf_e || CPU65.sphi != 0x100) dwx_envelope.invalid = 1;
        else if (CPU65.pc == dwx_stack_helper_pc)
            dwx_sp_checkpoint(&dwx_envelope, CPU65.s, CPU65.pc);
        else dwx_sp_sample(&dwx_envelope, CPU65.s, CPU65.pc);
    }"""
    cpu = replace_once(cpu, old, new)
    for callback in ("cpu65_nmi_debug_callback", "cpu65_irq_debug_callback"):
        anchor = "\t\tDO_CPU65_EXECUTION_CALLBACK(" + callback + ");"
        cpu = replace_once(cpu, anchor, anchor + """
#ifdef MEGA65
        if (dwx_stack_boot_started && !in_hypervisor)
            dwx_sp_interrupt_enter(&dwx_envelope, CPU65.s);
#endif""")
    cpu = replace_once(cpu, "\tcase 0x40:\t/* RTI Implied */\n\t\t\tcpu65_set_pf(pop());\n\t\t\tCPU65.pc = popWord();",
        "\tcase 0x40:\t/* RTI Implied */\n\t\t\tcpu65_set_pf(pop());\n\t\t\tCPU65.pc = popWord();" + """
#ifdef MEGA65
            if (dwx_stack_boot_started && !in_hypervisor)
                dwx_sp_interrupt_exit(&dwx_envelope);
#endif""")
    monitor = (OUT / "targets/mega65/uart_monitor.c").read_text()
    monitor = replace_once(monitor, "extern unsigned dwx_stack_enabled, dwx_stack_min, dwx_stack_wraps;", """
#include "xemu/dwx_stack_envelope.h"
extern dwx_sp_envelope dwx_envelope;
extern unsigned dwx_stack_main_pc, dwx_stack_vm_start, dwx_stack_vm_end, dwx_stack_helper_pc;
extern int dwx_stack_bound;
extern unsigned dwx_stack_enabled, dwx_stack_min, dwx_stack_wraps;""")
    anchor = '            } else if (!strcmp(cmd, "stackwater")) {'
    monitor = replace_once(monitor, anchor, """            } else if (!strcmp(cmd, "stackenvelope")) {
                umon_printf("DWX envelope bound=%d main=%04X vm=%04X..%04X helper=%04X post=%u irq=%u min=%u hits=%u scopes=%u wraps=%u invalid=%u peak_pc=%04X origin_pc=%04X",
                    dwx_stack_bound, dwx_stack_main_pc, dwx_stack_vm_start, dwx_stack_vm_end, dwx_stack_helper_pc,
                    dwx_envelope.max_post, dwx_envelope.max_irq, dwx_envelope.minimum_sp,
                    dwx_envelope.checkpoints, dwx_envelope.count, dwx_envelope.wraps,
                    dwx_envelope.invalid, dwx_envelope.post_pc, dwx_envelope.post_origin_pc);
""" + anchor)
    # Mechanical, version-bound transformations; base and header identities
    # are written alongside the resulting tool and every future trace binds it.
    (OUT / "xemu/cpu65.c").write_text(cpu)
    (OUT / "targets/mega65/uart_monitor.c").write_text(monitor)
    report = {"status": "PREPARED; NOT EXECUTION-QUALIFIED", "base": EXPECTED,
              "header_sha256": hashlib.sha256(HEADER.read_bytes()).hexdigest(),
              "sources": {name: hashlib.sha256((OUT / name).read_bytes()).hexdigest()
                          for name in EXPECTED},
              "product_builds": 0, "host_images": 0, "device_contacts": 0}
    (OUT / "envelope-tool.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def build():
    report = json.loads((OUT / "envelope-tool.json").read_text())
    for name, digest in report["sources"].items():
        if hashlib.sha256((OUT / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError("prepared observer source changed: " + name)
    sdk = ROOT / "build/dwx/stack-envelope-host-sdk/root/usr/include/SDL2"
    if not (sdk / "SDL_endian.h").is_file():
        raise RuntimeError("matching local SDL2 headers missing")
    gtk_flags = subprocess.check_output(["pkg-config", "--cflags", "gtk+-3.0"], text=True).strip()
    gtk_libs = subprocess.check_output(["pkg-config", "--libs", "gtk+-3.0"], text=True).strip()
    runtime = Path("/usr/lib64/libSDL2-2.0.so.0").resolve(strict=True)
    command = ["make", "-C", str(OUT / "targets/mega65"), "-j2",
               "SDL2_CFLAGS=-I" + str(sdk) + " -D_GNU_SOURCE=1 -D_REENTRANT",
               "SDL2_LIBS=" + str(runtime),
               "GTK3_CFLAGS=" + gtk_flags, "XEMUGUI_CFLAGS=" + gtk_flags,
               "GTK3_LIBS=" + gtk_libs, "XEMUGUI_LIBS=" + gtk_libs]
    # Derived host dependency paths replace copied configure paths. This is
    # solely the observer build, never a replacement product toolchain.
    with (OUT / "envelope-build.log").open("wb") as log:
        run = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    report["build_command"] = command
    report["build_exit"] = run.returncode
    report["host_compiler"] = subprocess.check_output(["cc", "--version"], text=True)
    report["sdl_runtime"] = {"path": str(runtime),
                             "sha256": hashlib.sha256(runtime.read_bytes()).hexdigest()}
    if run.returncode == 0:
        binary = OUT / "build/bin/xmega65.native"
        report["binary"] = {"path": str(binary), "sha256": hashlib.sha256(binary.read_bytes()).hexdigest()}
        report["status"] = "BUILT; NOT EXECUTION-QUALIFIED"
    (OUT / "envelope-tool.json").write_text(json.dumps(report, indent=2) + "\n")
    if run.returncode:
        raise RuntimeError("observer build failed; see " + str(OUT / "envelope-build.log"))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "build"])
    args = parser.parse_args()
    print(json.dumps({"prepare": prepare, "build": build}[args.action](), indent=2))
