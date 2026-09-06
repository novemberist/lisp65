"""Successor C4 binding: instructions and arithmetic consume the measured plan."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import dwx_comfort_collection_calibration as C


def derive(out):
    value = C.row_binding(out)
    row = value["row"]
    c = row["collection"]
    events_per_pass = len(c["pattern"]) + c["delete_events_per_pass"]
    warm_events = c["warmup_passes"] * events_per_pass
    measured_events = c["passes"] * events_per_pass + len(c["final_text"]) + 1
    c["event_arithmetic"] = {"warmup_physical_events": warm_events,
        "measured_physical_events_including_oracle_return": measured_events,
        "total_physical_events": warm_events + measured_events,
        "counter_modulus": 256, "expected_each_modulo_256": (warm_events+measured_events)%256}
    row["actions"] = [
        "At l65> submit " + c["controller"],
        f"On the blank nested row perform {c['warmup_passes']} warmup passes: type {c['pattern']}, then delete {c['delete_events_per_pass']} characters to blank. These include the two calibration samples in the prefilter.",
        "Record the GC counter at the measured-window start; it must equal the warmup-origin value. Do not zero any product counter.",
        f"Perform {c['passes']} measured passes with the same pattern and deletion: ordinary pace first, fast pace thereafter. Every typed row must match and every deleted row must be blank.",
        "Record GC before the final text/Return: it must have increased inside these measured typing passes, not only before or after them.",
        f"Type {c['final_text']} and Return; expect {len(c['final_text'])}. Touch no further key; read all four Capture counters at the stopped cutpoint.",
    ]
    row["binding_limit"] = ("Qualified-fork UART/HWA prefilter row. This is a proposed device counterpart, "
        "not authorization for additional physical stop/resume operations. Physical choreography must explicitly bind its GC read points before contact.")
    value["instruction_producer"] = C.R.bind(Path(__file__))
    return value


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("bind", "check"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    C.selftest()
    value = derive(args.out)
    path = args.out / "collection-row-binding.json"
    if args.action == "bind":
        path.write_text(json.dumps(value, indent=2) + "\n")
    else:
        C.R.require(C.R.load(path) == value, "world-derived C4 instructions/arithmetic drift")
    print(value["status"])
