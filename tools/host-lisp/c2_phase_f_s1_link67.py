#!/usr/bin/env python3
"""Bind, validate, and receive the one-session Link-67 F1/F2 S1 run."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_f4_s1_freight_session_gate as F4  # noqa: E402
import repl_screen_check as SCREEN  # noqa: E402


CONTRACT = ROOT / "config/c2.2-s1-freight-session.json"
LINK_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link67-f1-f2-structural-receipt.json")
PREP_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-f4-s1-freight-session-preparation-receipt.json")
MANIFEST = ROOT / "build/post-promotion/link67-f1-f2/canonical-product-manifest.json"
M65 = ROOT / "tools/m65tools/m65"
ATTEMPT1 = ROOT / "build/post-promotion/link67-f1-f2/s1-hardware"
OUT = ROOT / "build/post-promotion/link67-f1-f2/s1-hardware-attempt2"
DEPLOYMENT = OUT / "deployment.json"
OBSERVATIONS = OUT / "observed-rows.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link67-f1-f2-s1-hardware-receipt.json")
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link67-f1-f2-s1-attempt1-harness-first-red.json")

PRODUCT_SHA = "1b6fb1a524a71a63489848531b30e1d399b871ed5b863c93be7232f3362e44f3"
ELF_SHA = "25e563ba41283fb1ce21624a84f618b2337f889510dee19261509dc29e465f32"
ROLE_ADDRESS = {
    "c2d-v6-code-plane": 0x00050000,
    "c2-two-record-boot-stage": 0x00058500,
    "c2-session-family-region-0": 0x08000000,
    "c2-product-shelf": 0x08100000,
    "c2-boot-family": 0x08200000,
    "c2-session-family-region-1": 0x08300000,
    "c2-kernal-window": 0x087FE000,
}
PRE_FREEZER_IDS = tuple(F4.ROW_IDS[:10])


class S1Error(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise S1Error(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
    temporary.replace(path)


def artifacts_by_role() -> dict[str, dict[str, Any]]:
    manifest = load(MANIFEST)
    require(
        manifest["format"] == "lisp65-c2-lite-canonical-product-manifest-v1"
        and manifest["status"] == "passed-fresh-source-product-and-post-link-completion"
        and manifest["identity"]["resident_prg_sha256"] == PRODUCT_SHA
        and manifest["identity"]["linked_elf_sha256"] == ELF_SHA,
        "Link-67 canonical manifest identity drift",
    )
    rows = manifest["artifacts"]
    result = {row["role"]: row for row in rows}
    require(len(result) == 14 == len(rows), "canonical role inventory drift")
    for role, row in result.items():
        path = ROOT / row["path"]
        require(
            path.is_file()
            and path.stat().st_size == row["bytes"]
            and sha(path) == row["sha256"],
            f"canonical role binding drift: {role}",
        )
    require(
        result["c2-resident-prg"]["sha256"] == PRODUCT_SHA
        and result["linked-product-elf"]["sha256"] == ELF_SHA
        and result["c2-bank2-static-code-plane"]["bytes"] == 34990
        and result["c2-session-family-region-0"]["bytes"] == 64926
        and result["c2-session-family-region-1"]["bytes"] == 1956,
        "S1 candidate geometry drift",
    )
    return result


def source_authority() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    contract = load(CONTRACT)
    rows = F4.validate(contract)
    require(F4.mutation_tests(contract) == 10, "S1 mutation count drift")
    link = load(LINK_RECEIPT)
    require(
        contract["status"]
            == "link67-bound-attempt2-owner-authorized-hardware-not-run"
        and contract["session_policy"]["attempt_2_authorized"] is True
        and contract["candidate"]["link"] == 67
        and contract["candidate"]["product_sha256"] == PRODUCT_SHA
        and contract["candidate"]["elf_sha256"] == ELF_SHA
        and link["status"]
            == "passed-Link67-F1-F2-product-identity-hardware-not-run"
        and link["product"]["sha256"] == PRODUCT_SHA
        and link["ELF"]["sha256"] == ELF_SHA
        and link["execution_accounting"]["whole_program_product_links"] == 1
        and link["execution_accounting"]["hardware_runs"] == 0,
        "S1 Link-67 authority drift",
    )
    return rows, artifacts_by_role()


def deployment_value() -> dict[str, Any]:
    session, roles = source_authority()
    preloads = []
    for role, address in ROLE_ADDRESS.items():
        row = roles[role]
        preloads.append({
            **row,
            "address": f"0x{address:08x}",
        })
    spans = {
        "c2d_before_boot_stage": (
            ROLE_ADDRESS["c2d-v6-code-plane"]
            + roles["c2d-v6-code-plane"]["bytes"]
            <= ROLE_ADDRESS["c2-two-record-boot-stage"]),
        "session_before_shelf": (
            ROLE_ADDRESS["c2-session-family-region-0"]
            + roles["c2-session-family-region-0"]["bytes"]
            <= ROLE_ADDRESS["c2-product-shelf"]),
        "shelf_before_boot": (
            ROLE_ADDRESS["c2-product-shelf"]
            + roles["c2-product-shelf"]["bytes"]
            <= ROLE_ADDRESS["c2-boot-family"]),
        "boot_before_region1": (
            ROLE_ADDRESS["c2-boot-family"]
            + roles["c2-boot-family"]["bytes"]
            <= ROLE_ADDRESS["c2-session-family-region-1"]),
        "region1_before_window": (
            ROLE_ADDRESS["c2-session-family-region-1"]
            + roles["c2-session-family-region-1"]["bytes"]
            <= ROLE_ADDRESS["c2-kernal-window"]),
        "window_ends_at_attic_limit": (
            ROLE_ADDRESS["c2-kernal-window"]
            + roles["c2-kernal-window"]["bytes"] == 0x08800000),
    }
    require(all(spans.values()), "S1 preload span overlap")
    return {
        "format": "lisp65-c2.2-link67-f1-f2-s1-deployment-v1",
        "status": "ready-one-session-hardware-not-run",
        "product": {
            **roles["c2-resident-prg"],
            "address": "0x00002001",
        },
        "elf": roles["linked-product-elf"],
        "preloads": preloads,
        "span_checks": spans,
        "session": {
            "row_ids": list(F4.ROW_IDS),
            "row_count": session["row_count"],
            "mutations_rejected": 10,
            "first_red": True,
            "physical_freezer_return_key": "F3",
        },
        "tool": bind(M65),
        "authority": {
            "contract": bind(CONTRACT),
            "preparation_receipt": bind(PREP_RECEIPT),
            "link_receipt": bind(LINK_RECEIPT),
            "manifest": bind(MANIFEST),
            "driver": bind(Path(__file__)),
        },
        "execution_accounting": {
            "new_product_links": 0,
            "hardware_runs": 0,
        },
        "claim_limit": (
            "A SHA-bound plan only. No S1 hardware, timing, bitops-on-metal, "
            "acceptance, promotion or release claim exists before finalization."
        ),
    }


def prepare() -> None:
    require(not OUT.exists(), f"S1 output directory must be fresh: {OUT}")
    value = deployment_value()
    OUT.mkdir(parents=True)
    atomic_json(DEPLOYMENT, value)
    atomic_json(OBSERVATIONS, {
        "format": "lisp65-c2.2-link67-S1-observations-v1",
        "status": "hardware-not-started",
        "rows": [],
    })
    verify()
    print(
        "c2-phase-f-s1-link67: PREPARE PASS "
        f"product={PRODUCT_SHA} rows=12 mutations=10 hardware=not-run")


def record_first_red() -> None:
    contract = load(CONTRACT)
    require(
        contract["session_policy"]["hardware_attempts_so_far"] == 1
        and contract["session_policy"]["accepted_product_rows_so_far"] == 0,
        "attempt-1 disposition is not authorized by the S1 contract",
    )
    old_deployment = load(ATTEMPT1 / "deployment.json")
    old_observations = load(ATTEMPT1 / "observed-rows.json")
    require(
        old_deployment["product"]["sha256"] == PRODUCT_SHA
        and old_deployment["elf"]["sha256"] == ELF_SHA
        and not old_observations["rows"],
        "attempt-1 candidate or zero-row disposition drift",
    )
    readbacks = []
    for item in old_deployment["preloads"]:
        source = ROOT / item["path"]
        target = ATTEMPT1 / f"readback-{source.name}"
        require(
            target.is_file()
            and target.stat().st_size == source.stat().st_size
            and sha(target) == sha(source) == item["sha256"],
            f"attempt-1 upload readback drift: {item['role']}",
        )
        readbacks.append({
            "role": item["role"],
            "source": bind(source),
            "readback": bind(target),
            "byteidentical": True,
        })
    boot = ATTEMPT1 / "boot.txt"
    row = ATTEMPT1 / "row-boot-watch.txt"
    core = ATTEMPT1 / "device-core-id.bin"
    require(
        "lisp65>" in boot.read_text(errors="replace")
        and "(7 5 7)" in row.read_text(errors="replace")
        and core.stat().st_size == 4,
        "attempt-1 screen/core evidence drift",
    )
    value = {
        "format": "lisp65-c2.2-link67-S1-harness-first-red-v1",
        "recorded_on": "2026-07-27",
        "status": "harness-first-red-invalid-fixed-delay-zero-product-rows",
        "candidate": {
            "product": old_deployment["product"],
            "elf": old_deployment["elf"],
        },
        "device": {
            "core_identity": {**bind(core), "hex": core.read_bytes().hex()},
            "m65_tool": old_deployment["tool"],
        },
        "uploads": readbacks,
        "observation": {
            "reported_counter": {
                "raw": "(7 5 7)",
                "frames": 1797,
                "nominal_milliseconds": 35940,
                "limit_frames": 1500,
            },
            "autorun_probe_mtime_ns":
                (ATTEMPT1 / "autorun-probe.txt").stat().st_mtime_ns,
            "boot_capture_mtime_ns": boot.stat().st_mtime_ns,
            "row_capture_mtime_ns": row.stat().st_mtime_ns,
            "configured_fixed_boot_wait_seconds": 28,
            "configured_fixed_row_wait_seconds": 5,
            "accepted_product_rows": 0,
        },
        "diagnosis": {
            "class": "harness-timing-model",
            "cause": (
                "The harness inserted fixed waits before reading an absolute "
                "since-boot frame counter, so the counter included the "
                "harness delay and could not prove boot-to-REPL."),
            "correction": (
                "Poll once per second for the first visible REPL and submit "
                "the boot-watch immediately with a one-second result wait."),
            "product_claim": "none",
            "hardware_replay_authorized": False,
        },
        "evidence": {
            "deployment": bind(ATTEMPT1 / "deployment.json"),
            "observations": bind(ATTEMPT1 / "observed-rows.json"),
            "autorun_screen": bind(ATTEMPT1 / "autorun-probe.txt"),
            "boot_screen": bind(boot),
            "row_screen": bind(row),
            "contract": bind(CONTRACT),
            "driver": bind(Path(__file__)),
        },
        "execution_accounting": {
            "hardware_attempts": 1,
            "accepted_product_rows": 0,
            "F1_rows_run": 0,
            "F2_rows_run": 0,
            "Freezer_roundtrips": 0,
        },
        "claim_limit": (
            "This receipt proves an invalid attempt-1 harness delay, exact "
            "candidate uploads and a visible REPL only. It makes no F1, F2, "
            "timing, Freezer, acceptance, promotion or release claim."
        ),
    }
    atomic_json(FIRST_RED, value)
    print(
        "c2-phase-f-s1-link67: ATTEMPT1 FIRST RED BOUND "
        "cause=fixed-harness-delay accepted-product-rows=0 replay=not-authorized")


def rebind() -> None:
    observations = load(OBSERVATIONS)
    require(
        not observations["rows"]
        and observations["status"] == "hardware-not-started"
        and not (OUT / "device-core-id.bin").exists(),
        "S1 deployment may only be rebound before hardware starts",
    )
    atomic_json(DEPLOYMENT, deployment_value())
    verify()
    print("c2-phase-f-s1-link67: REBIND PASS hardware=not-run")


def verify() -> None:
    expected = deployment_value()
    actual = load(DEPLOYMENT)
    require(actual == expected, "S1 deployment plan is not canonical")
    observations = load(OBSERVATIONS)
    require(
        observations["format"] == "lisp65-c2.2-link67-S1-observations-v1"
        and [row["id"] for row in observations["rows"]]
            == list(F4.ROW_IDS[:len(observations["rows"])]),
        "S1 observation order drift",
    )
    print(
        "c2-phase-f-s1-link67: VERIFY PASS "
        f"observed={len(observations['rows'])}/12 hardware="
        f"{'started' if observations['rows'] else 'not-run'}")


def screen_lines(path: Path) -> list[str]:
    raw = path.read_text(errors="replace")
    return [SCREEN._screen_content(line) for line in raw.splitlines()]


def latest_result(path: Path, form: str) -> list[str]:
    lines = screen_lines(path)
    prompts = [
        index for index, line in enumerate(lines)
        if line.lstrip().startswith(SCREEN.PROMPT)]
    require(len(prompts) >= 2, "latest REPL segment is not visible")
    start, end = prompts[-2], prompts[-1]
    require(
        lines[end].strip() == SCREEN.PROMPT.rstrip()
        and not any(line.strip() for line in lines[end + 1:]),
        "trailing REPL prompt is not clean",
    )
    actual, echo_rows = SCREEN._reconstruct_echo(lines, start, form)
    require(actual == form, f"REPL echo drift: {actual!r}")
    result = lines[start + echo_rows:end]
    if (len(SCREEN.PROMPT) + len(form)) % SCREEN.SCREEN_WIDTH == 0:
        require(result and not result[0].strip(), "missing echo wrap row")
        result = result[1:]
    visible = [line.strip() for line in result if line.strip()]
    require(visible, "REPL result is absent")
    return visible


def timed_result(value: str, result_pattern: str, limit: int) -> dict[str, Any]:
    match = re.fullmatch(result_pattern, value)
    require(match is not None, f"malformed timed result: {value}")
    start = int(match.group("start"))
    end = int(match.group("end"))
    frames = (end - start) & 0xFF
    require(frames <= limit, f"timing First Red: {frames} > {limit} frames")
    return {
        "start": start,
        "end": end,
        "frames": frames,
        "nominal_milliseconds": frames * 20,
        "limit_frames": limit,
        "value_string": f"{frames}f/{frames * 20}ms<={limit}f",
    }


def validate_row(row: dict[str, Any], screen: Path) -> dict[str, Any]:
    row_id = row["id"]
    form = row.get("form")
    require(isinstance(form, str), f"row has no executable form: {row_id}")
    visible = latest_result(screen, form)
    joined = " | ".join(visible)
    result = visible[-1]
    timing = None
    if row_id == "boot-watch":
        match = re.fullmatch(r"\((\d+) (\d+) (\d+)\)", result)
        require(match is not None, f"malformed boot watch: {result}")
        high_a, low, high_b = map(int, match.groups())
        frames = high_a * 256 + low
        require(
            high_a == high_b and frames <= row["limit_frames"],
            f"boot watch First Red: {result} -> {frames} frames",
        )
        timing = {
            "frames": frames,
            "nominal_milliseconds": frames * 20,
            "limit_frames": row["limit_frames"],
            "value_string": (
                f"{frames}f/{frames * 20}ms<={row['limit_frames']}f"),
        }
    elif row_id in ("f1-nary-cold", "f1-nary-warm"):
        timing = timed_result(
            result,
            r"\(\(7 \. 8\) (?P<start>\d+) (?P<end>\d+)\)",
            row["limit_frames"],
        )
    elif row_id in ("nullary-cold-regression", "nullary-warm-regression"):
        timing = timed_result(
            result,
            r"\(t (?P<start>\d+) (?P<end>\d+)\)",
            row["limit_frames"],
        )
    elif row_id == "f2-bitops-type-negative":
        require(
            any(line.startswith("*** ") and "type" in line.lower()
                for line in visible),
            f"expected type error absent: {joined}",
        )
    else:
        expected = {
            "f1-define-fixed": "%s1n",
            "nullary-define-regression": "%s1z",
            "f2-bitops-positive": "(42 -43 -44 -42 16382)",
            "post-error-repl": "3",
            "post-freezer-repl": "9",
        }[row_id]
        require(
            not any(line.startswith("*** ") for line in visible)
            and result == expected,
            f"{row_id} First Red: expected {expected!r}, got {joined!r}",
        )
    return {
        "id": row_id,
        "status": "passed",
        "form": form,
        "visible_result": visible,
        "timing": timing,
        "screen": bind(screen),
    }


def observe_row(row_id: str, screen: Path) -> None:
    contract = load(CONTRACT)
    row_map = {row["id"]: row for row in contract["rows"]}
    require(row_id in row_map and row_id != "idle-freezer-roundtrip",
            f"unknown/non-form row: {row_id}")
    observations = load(OBSERVATIONS)
    rows = observations["rows"]
    expected = F4.ROW_IDS[len(rows)]
    require(row_id == expected, f"S1 row order: expected {expected}, got {row_id}")
    observed = validate_row(row_map[row_id], screen)
    rows.append(observed)
    observations["status"] = (
        "awaiting-physical-freezer-roundtrip"
        if len(rows) == len(PRE_FREEZER_IDS)
        else "hardware-session-in-progress")
    atomic_json(OBSERVATIONS, observations)
    timing = observed["timing"]
    suffix = f" {timing['value_string']}" if timing else ""
    print(f"c2-phase-f-s1-link67: ROW PASS {row_id}{suffix}")


def bind_capture_set(prefix: str) -> dict[str, Any]:
    result = {}
    for name in ("bank2", "bank3", "bank5", "e000"):
        path = OUT / f"{prefix}-{name}.bin"
        require(path.is_file(), f"missing Freezer capture: {path}")
        result[name] = bind(path)
    return result


def observe_freezer() -> None:
    observations = load(OBSERVATIONS)
    require(
        tuple(row["id"] for row in observations["rows"]) == PRE_FREEZER_IDS,
        "Freezer row reached before ten pre-Freezer rows passed",
    )
    before = bind_capture_set("pre-freezer")
    after = bind_capture_set("post-freezer")
    for name in before:
        require(
            before[name]["bytes"] == after[name]["bytes"]
            and before[name]["sha256"] == after[name]["sha256"],
            f"Freezer identity First Red: {name}",
        )
    observations["rows"].append({
        "id": "idle-freezer-roundtrip",
        "status": "passed",
        "operator_action": "physical Freezer; return with F3",
        "identity_before": before,
        "identity_after": after,
    })
    observations["status"] = "freezer-passed-awaiting-final-row"
    atomic_json(OBSERVATIONS, observations)
    print("c2-phase-f-s1-link67: FREEZER PASS bank2/bank3/bank5/e000 byteidentical")


def finalize() -> None:
    verify()
    observations = load(OBSERVATIONS)
    require(
        tuple(row["id"] for row in observations["rows"]) == F4.ROW_IDS,
        "S1 cannot finalize before all twelve rows pass",
    )
    core = OUT / "device-core-id.bin"
    require(core.is_file() and core.stat().st_size == 4,
            "four-byte device core identity missing")
    observations["status"] = "passed-complete"
    atomic_json(OBSERVATIONS, observations)
    deployment = load(DEPLOYMENT)
    receipt = {
        "format": "lisp65-c2.2-link67-f1-f2-s1-hardware-receipt-v1",
        "recorded_on": "2026-07-27",
        "status": "passed-Link67-F1-F2-S1-one-session-hardware",
        "product": deployment["product"],
        "elf": deployment["elf"],
        "device": {
            "core_identity": {
                **bind(core),
                "hex": core.read_bytes().hex(),
            },
            "m65_tool": deployment["tool"],
            "hardware_sessions": 1,
        },
        "rows": observations["rows"],
        "summary": {
            "rows_passed": 12,
            "mutations_rejected_before_hardware": 10,
            "F1_nary_direct_call_on_metal": "passed",
            "F2_bitops_on_metal": "passed",
            "F3": "parked-not-in-product",
            "Freezer": "passed-F3-return-with-byteidentical-identities",
        },
        "execution_accounting": {
            "product_links": 1,
            "hardware_sessions": 1,
            "hardware_retries": 0,
        },
        "authority": {
            "deployment": bind(DEPLOYMENT),
            "observations": bind(OBSERVATIONS),
            "contract": bind(CONTRACT),
            "preparation_receipt": bind(PREP_RECEIPT),
            "link_receipt": bind(LINK_RECEIPT),
            "manifest": bind(MANIFEST),
            "driver": bind(Path(__file__)),
        },
        "claim_limit": (
            "Claims only the twelve reviewed S1 rows on the bound Link-67 "
            "candidate and recorded device/tool identity. It does not claim "
            "acceptance, promotion, release, F3, while, catch/throw or C2.3."
        ),
    }
    atomic_json(RECEIPT, receipt)
    print(
        "c2-phase-f-s1-link67: HARDWARE PASS rows=12/12 "
        f"core={core.read_bytes().hex()} product={PRODUCT_SHA}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=(
            "prepare", "record-first-red", "rebind", "verify", "observe-row",
            "observe-freezer", "finalize"))
    parser.add_argument("--id")
    parser.add_argument("--screen", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            prepare()
        elif args.action == "record-first-red":
            record_first_red()
        elif args.action == "rebind":
            rebind()
        elif args.action == "verify":
            verify()
        elif args.action == "observe-row":
            require(args.id is not None and args.screen is not None,
                    "observe-row needs --id and --screen")
            observe_row(args.id, args.screen.resolve())
        elif args.action == "observe-freezer":
            observe_freezer()
        else:
            finalize()
    except (
        OSError, ValueError, KeyError, json.JSONDecodeError, S1Error,
        F4.GateError,
    ) as error:
        print(f"c2-phase-f-s1-link67: FIRST RED: {error}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
