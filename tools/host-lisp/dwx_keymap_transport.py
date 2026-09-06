"""Generate and execute the DWX typed-event population from the product keymap."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = ROOT / "config/v11-l-lite-keymap.json"
HEADER = "targets/mega65/dwx_keymap_generated.h"


def population() -> list[tuple[int, int]]:
    keymap = json.loads(AUTHORITY.read_text())
    events = {(code, 0) for row in keymap["bindings"] for code in row["codes"]}
    events |= {(row["code"], 0) for row in keymap["repl_line_projection"]["legacy_aliases"]}
    events.add((keymap["event_model"]["prefix_code"], 0))
    masks = keymap["event_model"]["modifier_masks"]
    for row in keymap["modifier_bindings"]:
        modifier = 0
        for name in row["required_modifiers"]:
            modifier |= masks[name]
        events.add((row["raw_petscii"], modifier))
        events.add((row["normalized_code"], modifier))
    if not events or any(not 0 < code < 256 or not 0 <= mod < 256 for code, mod in events):
        raise ValueError("keymap event population missing or out of range")
    return sorted(events)


def render(events: list[tuple[int, int]]) -> str:
    cases = "\n".join(f"    case 0x{mod:02x}{code:02x}: return 1;" for code, mod in events)
    return ("/* Generated from config/v11-l-lite-keymap.json; do not hand-edit. */\n"
            "#ifndef DWX_KEYMAP_GENERATED_H\n#define DWX_KEYMAP_GENERATED_H\n"
            "static int dwx_keymap_event(unsigned code, unsigned mod) {\n"
            "  switch (code | (mod << 8)) {\n" + cases +
            "\n    default: return 0;\n  }\n}\n#endif\n")


def executed_check(root: Path, header: str) -> None:
    """Compile the actual patched queue writers, not a Python transport model."""
    source = (root / "targets/mega65/input_devices.c").read_text()
    start = source.index("static void add_hwa_fake_key_unprotected (")
    end = source.index("const char *hwa_kbd_add_string", start)
    body = source[start:end]
    expected = population()
    tests = []
    for code, mod in expected:
        tests.append(f"queue_pos=0; if (!dwx_hwa_event({code},{mod}) || queue_pos!=1 || kbd_queue[0] != ({code}u | ({code}u<<8) | ({mod}u<<16))) return 1;")
        if mod == 0 and (code < 32 or code > 127) and code not in (10, 13):
            tests.append(f"queue_pos=0; add_hwa_fake_key_unprotected({code},0); if(queue_pos!=1 || ((kbd_queue[0]>>8)&255)!={code}) return 2;")
    tests += ["queue_pos=1; if(dwx_hwa_event(0,0) || queue_pos!=1) return 3;",
              "queue_pos=16; if(dwx_hwa_event(13,0) || queue_pos!=16) return 4;"]
    model = json.loads(AUTHORITY.read_text())["event_model"]
    for code in range(model["printable_min"], model["printable_max"] + 1):
        tests.append(f"queue_pos=0; add_hwa_fake_key_unprotected({code},0); if(queue_pos!=1) return 5;")
    program = ("#include <stdint.h>\n#include <string.h>\ntypedef uint8_t Uint8;\n"
               "#define MODKEY_LSHIFT 1\n#define IS_QUEUE_FULL() (queue_pos>=16)\n"
               "static unsigned kbd_queue[16]; static unsigned queue_pos;\n" + header + body +
               "\nint main(void){\n" + "\n".join(tests) + "\nreturn 0;}\n")
    with tempfile.TemporaryDirectory(prefix="dwx-keymap-") as directory:
        src = Path(directory) / "probe.c"
        binary = Path(directory) / "probe"
        src.write_text(program)
        subprocess.run(["cc", "-std=c99", "-Wall", "-Werror", str(src), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


def generate_and_check(root: Path, *, generate: bool = True) -> dict:
    events = population()
    header = render(events)
    if generate:
        (root / HEADER).write_text(header)
    elif (root / HEADER).read_text() != header:
        raise ValueError("bound navigation header differs from keymap authority")
    executed_check(root, header)
    fallen = []
    for event in events:
        try:
            executed_check(root, render([item for item in events if item != event]))
        except subprocess.CalledProcessError:
            fallen.append(list(event))
        else:
            raise ValueError(f"dropped keymap event survived: {event}")
    return {"authority": {"path": str(AUTHORITY.relative_to(ROOT)),
                           "sha256": hashlib.sha256(AUTHORITY.read_bytes()).hexdigest()},
            "events": [list(item) for item in events], "dropped_event_mutations": fallen,
            "oracle": "executed patched C queue writers; exact PETSCII/modifier tuple",
            "header": {"path": HEADER, "sha256": hashlib.sha256(header.encode()).hexdigest()}}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", required=True)
    parser.parse_args()
    import dwx_prefilter_blind_spot_contract as BLIND
    manifest = json.loads(BLIND.CYCLE_MANIFEST_PATH.read_text())
    result = generate_and_check(BLIND.CYCLE_MANIFEST_PATH.parent, generate=False)
    if result != manifest["keymap_transport"]:
        raise ValueError("navigation build proof and current executed proof differ")
    print(f"DWX keymap transport PASS tuples={len(result['events'])} dropped-mutations={len(result['dropped_event_mutations'])} printable-range=PASS")
