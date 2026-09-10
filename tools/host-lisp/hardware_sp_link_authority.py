"""Fail-closed ABS threshold binding; no product build or measurement here."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
RESTART_ERA = "b7b744d131a3361c18d6251fe5706450acbf2829"
RESTART = ROOT / "tests/bytecode/dialect-v2/evidence/post-release/v210-comfort-stack-restart-seal.json"

GUARD = "LISP65_HARDWARE_SP_GUARD"
AUTHORITY = "LISP65_HARDWARE_SP_LINK_AUTHORITY"
SYMBOL = "lisp65_hardware_sp_threshold"
CHECKPOINTS = ("vm_run_inner", "vm_native_call", "print_obj")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def bind(path):
    path = Path(path)
    raw = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def measured_threshold(measurement, seed_elf, expected_rows):
    """Validate a witness result, including its source evidence, not a price.

    The witness producer owes executed traces; this consumer cannot promote
    a synthetic fixture to a measurement. Source lines identify the exact
    records used for each measured component. Final remeasurement is separate.
    """
    require(measurement["elf"] == bind(seed_elf), "measurement ELF identity drift")
    require(measurement["kind"] == "executed-candidate-stack-envelope",
            "threshold requires executed candidate evidence")
    require(measurement["checkpoints"] == list(CHECKPOINTS), "checkpoint population drift")
    rows = measurement["rows"]
    require(expected_rows and len(expected_rows) == len(set(expected_rows)),
            "empty/duplicate session authority")
    require(len(rows) == len(expected_rows)
            and {r["id"] for r in rows} == set(expected_rows), "session population drift")

    def evidence_value(row):
        value = row["bytes"]
        require(type(value) is int and 0 <= value <= 255, "invalid measured stack consumption")
        evidence = row["evidence"]
        path = Path(evidence["path"])
        require(evidence == bind(path), "stack evidence identity drift")
        lines = path.read_text().splitlines()
        line = row["line"]
        require(type(line) is int and 1 <= line <= len(lines), "missing evidence line")
        # The witness emits one JSON record per line. Bind the numeric source,
        # not just a filename accompanied by an independently entered number.
        source = json.loads(lines[line - 1])
        require(source["bytes"] == value and source["component"] == row["component"],
                "measured component differs from cited record")
        require(source["elf_sha256"] == measurement["elf"]["sha256"],
                "component belongs to another candidate")
        if "id" in row:
            require(source["id"] == row["id"], "component belongs to another session row")
        return value

    after = []
    for row in rows:
        require(row["component"] == "post-checkpoint", "wrong session component")
        require(row["wrapped"] is False and row["completed"] is True,
                "incomplete/wrapped session cannot price a threshold")
        after.append(evidence_value(row))
    irq = measurement["irq_nmi"]
    abort = measurement["abort"]
    require(irq["component"] == "capture-irq-plus-one-nmi", "IRQ context drift")
    require(abort["component"] == "abort-reserve", "abort component drift")
    threshold = max(after) + evidence_value(irq) + evidence_value(abort) + 8
    require(1 <= threshold <= 255, "measured threshold cannot fit hardware SP")
    require(measurement["threshold"] == threshold, "threshold differs from measured sum")
    return threshold


def link_flags(target, definitions, resolver):
    raw_names = [d.split("=", 1)[0] for d in definitions]
    require(raw_names.count(GUARD) <= 1 and raw_names.count(AUTHORITY) <= 1,
            "ambiguous SP feature definitions")
    names = {d.split("=", 1)[0]: d.split("=", 1)[1] if "=" in d else "1"
             for d in definitions}
    enabled = names.get(GUARD) == "1"
    if not enabled:
        require(GUARD not in names, "unsupported SP feature value")
        require(AUTHORITY not in names, "threshold authority without guard")
        return [], None
    require(names.get(AUTHORITY) == "1", "explicit SP link authority missing")
    require(callable(resolver), "SP threshold resolver missing; defaults forbidden")
    record = resolver(Path(target))
    require(record["target"] == str(Path(target).resolve()), "threshold target drift")
    require(record["symbol"] == SYMBOL, "threshold symbol drift")
    value = record["threshold"]
    require(type(value) is int, "threshold is not an integer")
    if record["stage"] == "measurement-seed":
        require(Path(target).name == "resident-island-seed.prg" and value == 0,
                "zero threshold is confined to the measurement seed")
        require(record["qualification_claim"] is False, "measurement seed promoted")
    else:
        require(record["stage"] == "final-product" and 1 <= value <= 255,
                "invalid final threshold")
        require(Path(target).name == "lisp65-c2-substitution-linked.prg", "final target drift")
        path = Path(record["measurement"]["path"])
        require(record["measurement"] == bind(path), "measurement receipt drift")
        measured = measured_threshold(json.loads(path.read_text()),
                                      record["seed_elf"], record["session_rows"])
        require(value == measured, "link threshold differs from measured authority")
    return ["-Wl,--defsym=" + SYMBOL + "=" + str(value)], record


def inspect_emission(elf, readobj, threshold):
    """The ABS authority and the instruction operand must both consume T."""
    from elf_truth import ElfTruth
    require(type(threshold) is int and 0 <= threshold <= 255, "invalid expected threshold")
    truth = ElfTruth.read(Path(elf), llvm_readobj=Path(readobj),
                          include_section_data=True,
                          absolute_markers={SYMBOL: threshold})
    helper = truth.symbol("lisp_hardware_stack_low")
    section = truth.section(helper.section)
    offset = helper.value - section.address
    emitted = truth.section_bytes(section.name)[offset:offset + helper.bytes]
    expected = bytes([0xBA, 0xE0, threshold, 0xA9, 0, 0x2A, 0x49, 1, 0x60])
    require(emitted == expected, "SP helper does not consume the bound threshold")
    return {"elf": bind(elf), "threshold": threshold, "helper_address": helper.value,
            "helper_bytes": emitted.hex(), "absolute_symbol": SYMBOL,
            "scope": "emitted threshold consumption only, not reserve or timing"}


def observer_binding(elf, readobj):
    """Derive the scope's unwind level, including the shared wrapper.

    Counting only the predicate JSR would close the observer at the wrapper's
    RTS, before the protected body executes. Accept exactly the emitted
    frame-free wrapper; a changed prologue is a measurement halt.
    """
    from elf_truth import ElfTruth
    truth = ElfTruth.read(Path(elf), llvm_readobj=Path(readobj), include_section_data=True)
    helper = truth.symbol("lisp_hardware_stack_low")
    wrapper = truth.symbol("lisp_hardware_stack_require")
    abort = truth.symbol("lisp_abort_code")
    section = truth.section(wrapper.section)
    offset = wrapper.value - section.address
    raw = truth.section_bytes(wrapper.section)[offset:offset + wrapper.bytes]
    address = lambda n: bytes((n & 255, n >> 8))
    expected = b"\x20" + address(helper.value) + bytes.fromhex("aa f0 07 a9 27 20") + address(abort.value) + bytes.fromhex("80 fe 60")
    require(raw == expected, "guard wrapper frame/return contract changed; remeasure before use")
    # One body->wrapper JSR and the proven wrapper->predicate JSR, no PHA/PHX.
    caller_gap = 2 * (1 + 1)
    vm = truth.symbol("vm_run_dir")
    main = truth.symbol("main")
    return {"elf": bind(elf), "wrapper_bytes": raw.hex(), "caller_gap": caller_gap,
            "environment": f"{main.value:x},{vm.value:x},{vm.value+vm.bytes:x},{helper.value:x},{caller_gap}",
            "scope": "predicate SP through protected body, not merely through wrapper return"}


def selftest():
    """Synthetic consumer mutations, explicitly not candidate measurements."""
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        elf = root / "seed.elf"
        elf.write_bytes(b"synthetic-test-not-an-ELF")
        trace = root / "trace.jsonl"
        components = [("post-checkpoint", 7), ("capture-irq-plus-one-nmi", 15),
                      ("abort-reserve", 12)]
        trace.write_text("".join(json.dumps(dict(component=c, bytes=n, id="test-row",
                                                elf_sha256=bind(elf)["sha256"])) + "\n"
                                 for c, n in components))
        def component(i):
            return dict(component=components[i][0], bytes=components[i][1],
                        evidence=bind(trace), line=i + 1)
        measure = dict(kind="executed-candidate-stack-envelope", elf=bind(elf),
                       checkpoints=list(CHECKPOINTS),
                       rows=[dict(id="test-row", completed=True, wrapped=False, **component(0))],
                       irq_nmi=component(1), abort=component(2), threshold=42)
        require(measured_threshold(measure, elf, ["test-row"]) == 42, "control")
        rejected = []
        for name, change in (
            ("threshold-low", lambda m: m.update(threshold=41)),
            ("threshold-high", lambda m: m.update(threshold=43)),
            ("row-omitted", lambda m: m.update(rows=[])),
            ("checkpoint-omitted", lambda m: m["checkpoints"].pop()),
            ("source-value-changed", lambda m: m["irq_nmi"].update(bytes=13)),
            ("wrapped-row", lambda m: m["rows"][0].update(wrapped=True)),
            ("unfinished-row", lambda m: m["rows"][0].update(completed=False)),
        ):
            mutant = deepcopy(measure)
            change(mutant)
            try:
                measured_threshold(mutant, elf, ["test-row"])
            except ValueError:
                rejected.append(name)
            else:
                raise ValueError("surviving mutation: " + name)
        defs = (GUARD, AUTHORITY)
        seed = root / "resident-island-seed.prg"
        def seed_record(target):
            return dict(target=str(target.resolve()), symbol=SYMBOL, threshold=0,
                        stage="measurement-seed", qualification_claim=False)
        require(link_flags(seed, defs, seed_record)[0] ==
                ["-Wl,--defsym=" + SYMBOL + "=0"], "seed control")
        for name, target, flags, resolver in (
            ("resolver-omitted", seed, defs, None),
            ("authority-omitted", seed, (GUARD,), seed_record),
            ("zero-final", root / "lisp65-c2-substitution-linked.prg", defs, seed_record),
            ("guard-disabled-value", seed, (GUARD + "=0",), None),
            ("guard-duplicated", seed, defs + (GUARD,), seed_record),
        ):
            try:
                link_flags(target, flags, resolver)
            except ValueError:
                rejected.append(name)
            else:
                raise ValueError("surviving mutation: " + name)
        return {"status": "threshold-consumer-selftest-pass", "rejected": rejected,
                "candidate_measurement": False, "product_builds": 0}


def restart_sources():
    from evidence_era import era_bind
    paths = subprocess.check_output([
        "git", "diff", "--name-only", "ca98451e7c4e9214490d70855d80dacb90da597b",
        RESTART_ERA, "--", "src", "lib", "config/bytecode-abi-ledger.json"], cwd=ROOT
    ).decode().splitlines()
    paths += ["tools/host-lisp/comfort_entry_service_gate.py",
              "tools/host-lisp/comfort_entry_context_gate.py",
              "tools/host-lisp/hardware_sp_link_authority.py",
              "tools/host-lisp/bytecode_abi_ledger.py",
              "tools/host-lisp/bytecode_p0.py", "docs/contracts/bytecode-abi.md",
              "docs/planning/v2.1-comfort-stack-product-report.md"]
    require(len(paths) == len(set(paths)), "duplicate restart source")
    return [era_bind(RESTART_ERA, path) for path in sorted(paths)]


def verify_restart(value):
    require(value.get("format") == "lisp65-comfort-stack-historical-restart-v1"
            and value.get("source_era") == RESTART_ERA
            and value.get("current_product_claim") is False
            and value.get("status") == "SEALED RESTART EVIDENCE; NOT LIVE ACCEPTANCE",
            "restart evidence promoted or era changed")
    require(value["sources"] == restart_sources(), "restart source population/identity drift")
    require(bool(value["witnesses"]), "restart witnesses absent")
    for row in value["witnesses"]:
        # Historical build evidence remains in its existing owner directory.
        # Seal and verify the exact bytes; never rerun a producer here.
        raw = (ROOT / row["path"]).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == row["sha256"]
                and len(raw) == row["bytes"], "restart witness changed")


def restart_seal(write=False):
    if write:
        require(not RESTART.exists(), "restart seal already exists")
        roots = ("build/v2.1/comfort-stack-composition-r1",
                 "build/v2.1/comfort-buffered-repair-device-r1/stack-repair-pricing-r1",
                 "build/v2.1/hardware-sp-seed-medium-r1/threshold-feasibility",
                 "build/v2.1/hardware-sp-seed-medium-r1/refusal-recovery-r2",
                 "build/v2.1/hardware-sp-seed-medium-r1/native-envelope-r2",
                 "build/v2.1/hardware-sp-seed-medium-r1/reserve")
        paths = sorted(p for root in roots for p in (ROOT / root).glob("*.json"))
        require(all(any(p.parent == ROOT / root for p in paths) for root in roots),
                "restart witness family absent")
        value = dict(format="lisp65-comfort-stack-historical-restart-v1",
                     source_era=RESTART_ERA, current_product_claim=False,
                     status="SEALED RESTART EVIDENCE; NOT LIVE ACCEPTANCE",
                     sources=restart_sources(), witnesses=[dict(
                         path=p.relative_to(ROOT).as_posix(), bytes=p.stat().st_size,
                         sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths])
        verify_restart(value)
        RESTART.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    value = json.loads(RESTART.read_text())
    verify_restart(value)
    for change in (lambda v: v.update(current_product_claim=True),
                   lambda v: v["sources"].pop(),
                   lambda v: v["witnesses"][0].update(sha256="0" * 64)):
        trial = deepcopy(value); change(trial)
        try:
            verify_restart(trial)
        except ValueError:
            pass
        else:
            raise ValueError("restart mutation survived")
    print(f"COMFORT RESTART SEAL PASS sources={len(value['sources'])} witnesses={len(value['witnesses'])} mutations=3 live-claim=false")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--restart-check", action="store_true")
    parser.add_argument("--record-restart", action="store_true")
    args = parser.parse_args()
    if args.restart_check or args.record_restart:
        restart_seal(args.record_restart)
    print(json.dumps(selftest(), indent=2))
