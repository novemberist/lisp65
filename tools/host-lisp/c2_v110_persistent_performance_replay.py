#!/usr/bin/env python3
"""Verify the closed 1.10 receipt without rewriting historical authorities."""

from __future__ import annotations

import hashlib
import builtins
from contextlib import contextmanager
import io
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_v110_persistent_performance as V110  # noqa: E402


HISTORICAL_COMMIT = "d13bd166"
REBOUND_ON = "2026-08-09"
AUTHORITY_KEYS = ("closing_plan", "gate_wiring", "driver", "phase_A_driver")
FIXTURE_COMMIT = "2d8195eb9d9fbd1e89c051c93eafc783c9dd25d9"
FIXTURE = "tests/bytecode/dialect-v2/v111-locality-replay-inputs"


class ReplayError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplayError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git_bytes(commit: str, path: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{commit}:{path}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE,
    ).stdout


def defstruct_inputs() -> dict[Path, bytes]:
    """The nine-publication oracle consumes its sealed macro, not Set A's group."""
    binding = json.loads(V110.RECEIPT.read_text())["authorities"]["candidate_source"]
    path = ROOT / binding['path']
    raw = git_bytes(HISTORICAL_COMMIT, binding['path'])
    def validate(data):
        require(len(data) == binding['bytes'] and sha(data) == binding['sha256'],
                'historical defstruct source differs from its executed authority')
    validate(raw)
    for mutant in (raw + b' ', path.read_bytes()):
        require(mutant != raw, 'live-path mutation no longer distinguishes the group world')
        try:
            validate(mutant)
        except ReplayError:
            pass
        else:
            raise ReplayError('historical defstruct mutation survived')
    return {path: raw}


def carrier_inputs() -> dict[Path, bytes]:
    """Resolve the Link-82 carrier and its resident closure, never rolling output.

    The baseline-carrier fixture is independently checked against Link 82's
    while receipt. The resident fixture is the already sealed locality replay
    closure. Original logical paths are retained, so hashes and content reads
    consume the same era without modifying shared build output or receipts.
    """
    phase = V110.PHASE_A
    receipt_raw = git_bytes(
        phase.EXPECTED_SOURCE_COMMIT,
        phase.WHILE_RECEIPT.relative_to(ROOT).as_posix())
    receipt = json.loads(receipt_raw)
    require(receipt.get("format") == phase.WHILE_RECEIPT_FORMAT,
            "historical carrier receipt format drift")
    bindings = receipt["bound_device_carrier"]
    result = {phase.WHILE_RECEIPT: receipt_raw, **defstruct_inputs()}
    values = {}
    for role, filename in (("manifest", "manifest.json"),
                           ("blob", "blob.bin"), ("tier_suite", "suite.json")):
        raw = git_bytes(FIXTURE_COMMIT, f"{FIXTURE}/baseline-carrier/{filename}")
        binding = bindings[role]
        require(len(raw) == binding["bytes"] and sha(raw) == binding["sha256"],
                f"recovered Link-82 input differs from its authority: {role}")
        result[ROOT / binding["path"]] = raw
        values[role] = raw
    manifest, suite = (json.loads(values[key]) for key in ("manifest", "tier_suite"))
    require(manifest["suite"] == bindings["tier_suite"]["path"]
            and manifest["blob"] == bindings["blob"]["path"]
            and manifest["blob_sha256"] == bindings["blob"]["sha256"],
            "carrier transitive path/SHA binding drift")
    resident_raw = git_bytes(FIXTURE_COMMIT, f"{FIXTURE}/resident/suite.json")
    result[ROOT / suite["resident_suite"]] = resident_raw
    require(not suite.get("resident_suites"), "unexpected second resident closure")
    for source in json.loads(resident_raw)["sources"]:
        prefix = "build/bytecode/dialect-v2/sources/"
        require(source.startswith(prefix), "resident source escaped sealed closure")
        result[ROOT / source] = git_bytes(
            FIXTURE_COMMIT, f"{FIXTURE}/resident/sources/{source[len(prefix):]}")
    return result


@contextmanager
def carrier_world(inputs: dict[Path, bytes]):
    """Process-local read-only input view; unmapped transitive reads fail closed."""
    original, original_io = builtins.open, io.open
    reads = {}
    protected = (ROOT / "build/post-promotion/phase-v/while/gate",
                 ROOT / "build/bytecode/dialect-v2/sources",
                 ROOT / "build/bytecode/dialect-v2/suites")

    def opened(file, mode="r", *args, **kwargs):
        path = Path(file).resolve() if isinstance(file, (str, Path)) else None
        if path not in inputs:
            require(path is None or not any(path.is_relative_to(p) for p in protected),
                    f"unbound historical carrier input: {path}")
            return original(file, mode, *args, **kwargs)
        require(mode in ("r", "rt", "rb"), "write to historical carrier input")
        raw = inputs[path]
        reads[path.relative_to(ROOT).as_posix()] = {"bytes": len(raw), "sha256": sha(raw)}
        if "b" in mode:
            return io.BytesIO(raw)
        return io.TextIOWrapper(io.BytesIO(raw), encoding=kwargs.get("encoding") or "utf-8")

    builtins.open = io.open = opened
    try:
        yield reads
    finally:
        builtins.open, io.open = original, original_io


def carrier_controls(inputs: dict[Path, bytes]) -> int:
    phase = V110.PHASE_A
    expected = inputs[phase.COMPILER_MANIFEST]
    with carrier_world(inputs):
        require(phase.COMPILER_MANIFEST.read_bytes() == expected
                and phase.bind(phase.COMPILER_MANIFEST)["sha256"] == sha(expected),
                "carrier content/binding world divergence")
    rejected = 0
    for path, mode in ((phase.COMPILER_MANIFEST, "w"),
                       (phase.COMPILER_MANIFEST.parent / "unbound.json", "r")):
        try:
            with carrier_world(inputs):
                with path.open(mode):
                    pass
        except ReplayError:
            rejected += 1
    # Substitute later-world bytes at the old rolling path and a corrupt fixture;
    # both must be rejected by the carrier's executed identity guard.
    later = git_bytes(FIXTURE_COMMIT, f"{FIXTURE}/accepted-candidate/manifest.json")
    for raw in (later, expected + b" "):
        require(raw != expected, "rolling-path regression control is not divergent")
        mutated = dict(inputs)
        mutated[phase.COMPILER_MANIFEST] = raw
        try:
            with carrier_world(mutated):
                phase.HistoricalCarrier()
        except phase.PhaseAError:
            rejected += 1
    mutated = dict(inputs)
    del mutated[phase.COMPILER_MANIFEST]
    try:
        with carrier_world(mutated):
            phase.HistoricalCarrier()
    except ReplayError:
        rejected += 1
    require(rejected == 5, "historical carrier controls drift")
    return rejected


def legacy_replay_check() -> dict[str, object]:
    recorded = json.loads(V110.RECEIPT.read_text(encoding="utf-8"))
    V110.audit_result(recorded)
    require(len(recorded.get("mutations_rejected", {})) == 22,
            "historical 1.10 mutation closure drift")

    for key in AUTHORITY_KEYS:
        binding = recorded["authorities"][key]
        raw = git_bytes(HISTORICAL_COMMIT, binding["path"])
        require(len(raw) == binding["bytes"] and sha(raw) == binding["sha256"],
                f"historical 1.10 authority no longer resolves: {key}")

    historical_plan = git_bytes(
        HISTORICAL_COMMIT, recorded["authorities"]["closing_plan"]["path"])
    current_plan = V110.PLAN.read_bytes()
    require(current_plan.startswith(historical_plan),
            "current 1.10 plan is not an append-only extension of its receipt")
    require(b"Loud dated replay rebind -- 2026-08-07" in current_plan,
            "1.10 loud dated replay-rebind record absent")

    inputs = carrier_inputs()
    controls = carrier_controls(inputs)
    with carrier_world(inputs) as reads:
        current = V110.derive()
    require(set(reads) == {p.relative_to(ROOT).as_posix() for p in inputs},
            "sealed carrier input population not fully consumed")
    for key in ("closing_plan", "gate_wiring", "phase_A_driver"):
        current["authorities"][key] = recorded["authorities"][key]
    # Link 95 intentionally changes the surrounding packed stdlib.  The
    # historical defstruct carrier remains semantically identical, but the
    # live symbol allocator moves its generated manifest SHA and the absolute
    # window-schedule SHA. The closed input world now reproduces that schedule
    # exactly: the former schedule exception is removed. Only the previously
    # approved candidate manifest container-identity exception remains;
    # every count, price, form result, freight byte and transaction witness
    # remains subject to the full receipt equality below.
    require(
        current["authorities"]["candidate_manifest"]
            != recorded["authorities"]["candidate_manifest"],
        "candidate manifest container rebind no longer differs",
    )
    current["authorities"]["candidate_manifest"] = (
        recorded["authorities"]["candidate_manifest"]
    )
    require(current == recorded,
            "current host reconstruction differs beyond historical authorities")
    return {
        "status": "passed-current-execution-historical-authority-replay",
        "historical_commit": subprocess.run(
            ["git", "rev-parse", f"{HISTORICAL_COMMIT}^{{commit}}"],
            cwd=ROOT, check=True, stdout=subprocess.PIPE, text=True,
        ).stdout.strip(),
        "rebound_on": REBOUND_ON,
        "historical_receipt_rewritten": False,
        "normalized_authorities": [
            "closing_plan", "gate_wiring", "candidate_manifest",
            "phase_A_driver",
        ],
        "mutations": 22,
        "carrier_controls": controls,
        "carrier_input_reads": reads,
        "carrier_era": V110.PHASE_A.EXPECTED_SOURCE_COMMIT,
        "resident_fixture_era": FIXTURE_COMMIT,
    }


def selftest() -> None:
    check()


def check() -> int:
    from historical_receipt_seal import check as seal_check
    return seal_check('v110')


def main() -> int:
    return check()


def legacy_replay_main() -> int:
    try:
        value = legacy_replay_check()
        print(
            "c2-v110-persistent-performance-replay: PASS "
            f"historical={str(value['historical_commit'])[:8]} "
            "current-execution=byteidentical receipt-rewritten=no mutations=22 "
            f"carrier-controls={value['carrier_controls']} "
            f"sealed-inputs={len(value['carrier_input_reads'])}"
        )
        return 0
    except (ReplayError, V110.PerformanceError, OSError, ValueError,
            KeyError, subprocess.SubprocessError) as error:
        print(f"c2-v110-persistent-performance-replay: FAIL: {error}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
