#!/usr/bin/env python3
"""Prepare and receive Link 77's one-session Phase-I/Phase-V/K2 run."""

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
import repl_screen_check as SCREEN  # noqa: E402


CONTRACT = ROOT / "config/c2.2-link77-phase-v-bundled-hardware-session.json"
LINK_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link77-random-while-structural-receipt.json")
MANIFEST = (
    ROOT / "build/post-promotion/link77-random-while/"
    "canonical-product-manifest.json")
OUT = (
    ROOT / "build/post-promotion/link77-random-while/"
    "phase-v-bundled-hardware")
DEPLOYMENT = OUT / "deployment.json"
OBSERVATIONS = OUT / "observed-rows.json"
PREPARATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link77-phase-v-bundled-hardware-preparation-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link77-phase-v-bundled-hardware-receipt.json")
IRQ_CONFIG = ROOT / "config/c2-interrupt-ownership-hardware-session.json"
WHILE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v2-while-four-view-receipt.json")
RANDOM_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1-random-base-host-first-receipt.json")
OLD_DIRMISS = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-post-symname-hardware-v2-receipt.json")
OLD_SESSION = ROOT / (
    "build/post-promotion/link75-bound-compiler-carrier/final/"
    "runtime-overlays-session-final.bin")
OLD_SESSION_JSON = ROOT / (
    "build/post-promotion/link75-bound-compiler-carrier/final/"
    "runtime-overlays-session-final.json")
NEW_SESSION = ROOT / (
    "build/post-promotion/link77-random-while/final/"
    "runtime-overlays-session-final.bin")
NEW_SESSION_JSON = ROOT / (
    "build/post-promotion/link77-random-while/final/"
    "runtime-overlays-session-final.json")
M65 = ROOT / "tools/m65tools/m65"

PRODUCT_SHA = "9e8999c0de31e306ee957f4912b7fa0baa52c55d58dfe8a933b1c02462e1faa3"
ELF_SHA = "ede88619d0e9711b8d5144495ca84f0414ee38352f882df8aadf5372504e9889"
RENDERER_SHA = "7ddf36a80772dcd8028a91bd2a8b65341bc2414e01a3b3501cfb41c2558e2021"
ROLE_ADDRESS = {
    "c2d-v6-code-plane": 0x00050000,
    "c2-two-record-boot-stage": 0x00058500,
    "c2-session-family-region-0": 0x08000000,
    "c2-product-shelf": 0x08100000,
    "c2-boot-family": 0x08200000,
    "c2-session-family-region-1": 0x08300000,
    "c2-kernal-window": 0x087FE000,
}
ROW_IDS = (
    "boot-repl",
    "while-zero",
    "while-multiple",
    "while-nonboolean-truth",
    "while-long-constant-stack",
    "while-allocation-gc",
    "while-run-stop",
    "post-run-stop-repl",
    "random-state-width",
    "random-rejection-path",
    "random-seed-reproducible",
    "random-range",
    "irq-mask-readback",
    "dirmiss-full-name",
    "post-dirmiss-repl",
)


class HardwareError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise HardwareError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    if not path.is_absolute():
        path = ROOT / path
    path = path.resolve()
    require(path.is_file(), f"artifact absent: {path}")
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


def rows() -> list[dict[str, Any]]:
    contract = load(CONTRACT)
    value = contract["rows"]
    require(
        contract["format"]
            == "lisp65-c2.2-link77-phase-v-bundled-hardware-session-v1"
        and contract["status"]
            == "owner-authorized-link77-bound-hardware-not-run"
        and tuple(row["id"] for row in value) == ROW_IDS
        and len(value) == len(set(ROW_IDS)) == 15
        and all(row["first_red"] is True for row in value),
        "Link-77 hardware row inventory drift",
    )
    return value


def artifacts_by_role() -> dict[str, dict[str, Any]]:
    manifest = load(MANIFEST)
    require(
        manifest["status"]
            == "passed-fresh-source-product-and-post-link-completion"
        and manifest["identity"]["resident_prg_sha256"] == PRODUCT_SHA
        and manifest["identity"]["linked_elf_sha256"] == ELF_SHA
        and manifest["static_plane"]["bank2_static_code_bytes"] == 41485
        and manifest["static_plane"]["entries"] == 696
        and manifest["static_plane"]["resolutions"] == 2760
        and manifest["static_plane"]["roots"] == 340,
        "Link-77 canonical product identity drift",
    )
    result = {row["role"]: row for row in manifest["artifacts"]}
    require(
        len(result) == len(manifest["artifacts"]) == 14,
        "Link-77 canonical role inventory drift",
    )
    for role, row in result.items():
        path = ROOT / row["path"]
        require(
            path.stat().st_size == row["bytes"]
            and sha(path) == row["sha256"],
            f"Link-77 canonical role drift: {role}",
        )
    return result


def renderer_prefix(image_path: Path,
                    manifest_path: Path) -> bytes:
    manifest = load(manifest_path)
    row = next(row for row in manifest["slices"] if row["id"] == 47)
    require(
        row["name"] == "error-text-renderer"
        and row["vma"] == 0xC356
        and row["file_offset"] == 0xEA00
        and row["file_size"] == 1210,
        "DIRMISS renderer slice geometry drift",
    )
    image = image_path.read_bytes()
    return image[row["file_offset"]:row["file_offset"] + 339]


def source_authority() -> tuple[list[dict[str, Any]],
                                dict[str, dict[str, Any]]]:
    contract = load(CONTRACT)
    link = load(LINK_RECEIPT)
    irq = load(IRQ_CONFIG)
    while_receipt = load(WHILE_RECEIPT)
    random_receipt = load(RANDOM_RECEIPT)
    old = load(OLD_DIRMISS)
    old_renderer = renderer_prefix(OLD_SESSION, OLD_SESSION_JSON)
    new_renderer = renderer_prefix(NEW_SESSION, NEW_SESSION_JSON)
    require(
        contract["candidate"]["product_sha256"] == PRODUCT_SHA
        and contract["candidate"]["elf_sha256"] == ELF_SHA
        and link["status"]
            == "passed-Link77-random-while-hardware-not-run"
        and link["product"]["sha256"] == PRODUCT_SHA
        and link["ELF"]["sha256"] == ELF_SHA
        and link["execution_accounting"]["whole_program_product_links"] == 1
        and link["execution_accounting"]["hardware_runs"] == 0
        and irq["expected"] == "(0 0 0)"
        and while_receipt["bound_device_carrier"]["result"] == 3
        and random_receipt["status"]
            == "passed-random-base-host-first-and-capacity-projection"
        and old["status"]
            == "R-post-symname-scratch-correct-renderer-consumption"
        and old_renderer == new_renderer
        and sha_bytes(old_renderer) == RENDERER_SHA,
        "Link-77 feature/IRQ/DIRMISS authority drift",
    )
    return rows(), artifacts_by_role()


def deployment_value() -> dict[str, Any]:
    session_rows, roles = source_authority()
    preloads = [
        {
            **roles[role],
            "address": f"0x{address:08x}",
        }
        for role, address in ROLE_ADDRESS.items()
    ]
    spans = {
        "c2d_before_boot_stage": (
            ROLE_ADDRESS["c2d-v6-code-plane"]
            + roles["c2d-v6-code-plane"]["bytes"]
            <= ROLE_ADDRESS["c2-two-record-boot-stage"]
        ),
        "session_before_shelf": (
            ROLE_ADDRESS["c2-session-family-region-0"]
            + roles["c2-session-family-region-0"]["bytes"]
            <= ROLE_ADDRESS["c2-product-shelf"]
        ),
        "shelf_before_boot": (
            ROLE_ADDRESS["c2-product-shelf"]
            + roles["c2-product-shelf"]["bytes"]
            <= ROLE_ADDRESS["c2-boot-family"]
        ),
        "boot_before_region1": (
            ROLE_ADDRESS["c2-boot-family"]
            + roles["c2-boot-family"]["bytes"]
            <= ROLE_ADDRESS["c2-session-family-region-1"]
        ),
        "region1_before_window": (
            ROLE_ADDRESS["c2-session-family-region-1"]
            + roles["c2-session-family-region-1"]["bytes"]
            <= ROLE_ADDRESS["c2-kernal-window"]
        ),
        "window_ends_at_attic_limit": (
            ROLE_ADDRESS["c2-kernal-window"]
            + roles["c2-kernal-window"]["bytes"] == 0x08800000
        ),
    }
    require(all(spans.values()), "Link-77 deployment spans overlap")
    return {
        "format": "lisp65-c2.2-link77-phase-v-deployment-v1",
        "status": "ready-one-bundled-session-hardware-not-run",
        "product": {
            **roles["c2-resident-prg"],
            "address": "0x00002001",
        },
        "elf": roles["linked-product-elf"],
        "preloads": preloads,
        "span_checks": spans,
        "session": {
            "row_ids": [row["id"] for row in session_rows],
            "row_count": len(session_rows),
            "physical_RUN_STOP": True,
            "first_red": True,
        },
        "tool": bind(M65),
        "authority": {
            "contract": bind(CONTRACT),
            "link_receipt": bind(LINK_RECEIPT),
            "manifest": bind(MANIFEST),
            "IRQ_line": bind(IRQ_CONFIG),
            "while": bind(WHILE_RECEIPT),
            "random": bind(RANDOM_RECEIPT),
            "DIRMISS_prior_hold": bind(OLD_DIRMISS),
            "driver": bind(Path(__file__)),
        },
        "execution_accounting": {
            "new_product_links": 0,
            "hardware_runs": 0,
        },
        "claim_limit": (
            "SHA-bound deployment only; no hardware claim before all rows "
            "are recorded and finalized."
        ),
    }


def prepare() -> None:
    require(
        not OUT.exists() and not PREPARATION.exists() and not RECEIPT.exists(),
        "Link-77 hardware preparation is one-shot",
    )
    value = deployment_value()
    OUT.mkdir(parents=True)
    atomic_json(DEPLOYMENT, value)
    atomic_json(OBSERVATIONS, {
        "format": "lisp65-c2.2-link77-phase-v-observations-v1",
        "status": "hardware-not-started",
        "rows": [],
    })
    atomic_json(PREPARATION, {
        "format":
            "lisp65-c2.2-link77-phase-v-hardware-preparation-v1",
        "recorded_on": "2026-07-29",
        "status": "passed-one-session-preparation-hardware-not-run",
        "candidate": {
            "product_sha256": PRODUCT_SHA,
            "elf_sha256": ELF_SHA,
        },
        "rows": len(ROW_IDS),
        "groups": ["while", "random", "interrupt-ownership", "diagnostic"],
        "DIRMISS": {
            "method": "ordinary product error row",
            "diagnostic_product_delta": 0,
            "renderer_bytes_byteidentical_to_prior_post_symname_hold": 339,
            "renderer_sha256": RENDERER_SHA,
        },
        "deployment": bind(DEPLOYMENT),
        "execution_accounting": {
            "compiler_runs": 0,
            "linker_runs": 0,
            "product_links": 0,
            "hardware_runs": 0,
        },
        "next_gate": "one physical device session in exact row order",
    })
    verify()
    print(
        "c2-phase-v-link77-hw: PREPARE PASS "
        f"product={PRODUCT_SHA} rows={len(ROW_IDS)} hardware=not-run"
    )


def rebind_harness() -> None:
    observations = load(OBSERVATIONS)
    require(
        [row["id"] for row in observations["rows"]]
        == list(ROW_IDS[:len(observations["rows"])])
        and len(observations["rows"]) == 5,
        "Link-77 harness rebind requires the five pre-GC rows",
    )
    correction = {
        "kind": "test-harness-only",
        "product_delta_bytes": 0,
        "product_redeployments": 0,
        "path_binding": (
            "Relative evidence paths are normalized against the workspace "
            "before receipt binding."
        ),
        "allocation_row": {
            "rejected_form":
                "(let((i 0)(kept nil))(progn(while(car(cons(< i 5000)nil))"
                "(setq kept(cons i kept))(setq i(+ i 1)))(+ i(car kept))))",
            "observed": "*** vm: out of memory",
            "attribution": (
                "The rejected row retained 5000 cons cells, but the bound "
                "target has only 48 hot plus 1024 extended cells."
            ),
            "replacement": row_by_id("while-allocation-gc")["form"],
            "replacement_expected": "600",
            "proof": row_by_id("while-allocation-gc")[
                "target_capacity_proof"],
        },
    }
    observations["harness_corrections"] = [correction]
    atomic_json(OBSERVATIONS, observations)

    atomic_json(DEPLOYMENT, deployment_value())
    preparation = load(PREPARATION)
    preparation["deployment"] = bind(DEPLOYMENT)
    preparation["harness_corrections"] = [correction]
    preparation["execution_accounting"]["hardware_runs"] = 1
    preparation["next_gate"] = (
        "resume the same physical session at the corrected allocation row"
    )
    atomic_json(PREPARATION, preparation)
    verify()
    print(
        "c2-phase-v-link77-hw: HARNESS REBIND PASS "
        "rows=5 product_delta=0 redeployments=0"
    )


def verify() -> None:
    source_authority()
    deployment = load(DEPLOYMENT)
    observations = load(OBSERVATIONS)
    require(
        deployment["product"]["sha256"] == PRODUCT_SHA
        and deployment["elf"]["sha256"] == ELF_SHA
        and deployment["session"]["row_ids"] == list(ROW_IDS)
        and all(deployment["span_checks"].values())
        and len(observations["rows"]) <= len(ROW_IDS),
        "Link-77 prepared deployment drift",
    )
    for row in [deployment["product"], *deployment["preloads"]]:
        path = ROOT / row["path"]
        require(
            path.stat().st_size == row["bytes"]
            and sha(path) == row["sha256"],
            f"Link-77 deployment artifact drift: {path}",
        )
    require(
        [row["id"] for row in observations["rows"]]
        == list(ROW_IDS[:len(observations["rows"])]),
        "Link-77 observed row order drift",
    )
    print(
        "c2-phase-v-link77-hw: VERIFY PASS "
        f"observed={len(observations['rows'])}/{len(ROW_IDS)}"
    )


def row_by_id(row_id: str) -> dict[str, Any]:
    return next(row for row in rows() if row["id"] == row_id)


def append_observation(value: dict[str, Any]) -> None:
    observations = load(OBSERVATIONS)
    index = len(observations["rows"])
    require(
        index < len(ROW_IDS) and value["id"] == ROW_IDS[index],
        "Link-77 hardware row order violation",
    )
    observations["rows"].append(value)
    observations["status"] = (
        "all-rows-observed-awaiting-finalization"
        if len(observations["rows"]) == len(ROW_IDS)
        else "hardware-in-progress"
    )
    atomic_json(OBSERVATIONS, observations)


def record_row(row_id: str, screen: Path, image: Path) -> None:
    row = row_by_id(row_id)
    require(row_id != "while-run-stop", "use record-run-stop")
    SCREEN.check_fail_closed_frame(image)
    if "expected_result" in row:
        SCREEN.check_latest_result(
            screen, row["form"], row["expected_result"])
        outcome = row["expected_result"]
    else:
        raw = screen.read_text(errors="replace")
        lines = [line.strip() for line in raw.splitlines()]
        errors = [
            line for line in lines
            if line.startswith(row["expected_error_prefix"])
        ]
        require(
            len(errors) == 1
            and errors[0].split(":", 1)[1].strip()
                == row["expected_symbol"]
            and sum(line.startswith("lisp65>") for line in lines) >= 2
            and lines[-1] in ("", "lisp65>"),
            "DIRMISS did not render the complete missing symbol at a live prompt",
        )
        outcome = errors[0]
    append_observation({
        "id": row_id,
        "group": row["group"],
        "outcome": outcome,
        "screen": bind(screen),
        "image": bind(image),
    })
    print(f"c2-phase-v-link77-hw: ROW PASS {row_id} -> {outcome}")


def record_run_stop(screen: Path, image: Path) -> None:
    row = row_by_id("while-run-stop")
    SCREEN.check_fail_closed_frame(image)
    raw = screen.read_text(errors="replace").lower()
    require(
        row["expected_status"] in raw
        and re.search(r"(?m)^\\s*lisp65>\\s*$", raw) is not None,
        "RUN/STOP did not return the empty-body while to a live prompt",
    )
    append_observation({
        "id": row["id"],
        "group": row["group"],
        "outcome": row["expected_status"],
        "screen": bind(screen),
        "image": bind(image),
    })
    print("c2-phase-v-link77-hw: ROW PASS while-run-stop")


def record_allocation_red(screen: Path, image: Path) -> None:
    observations = load(OBSERVATIONS)
    deployment = load(DEPLOYMENT)
    raw = screen.read_text(errors="replace")
    SCREEN.check_fail_closed_frame(image)
    require(
        [row["id"] for row in observations["rows"]] == list(ROW_IDS[:5])
        and re.search(r"(?m)^\s*600\s*$", raw) is not None
        and "*** vm: out of memory" in raw
        and re.search(r"(?m)^\s*lisp65>\s*$", raw) is not None,
        "allocation/GC First Red evidence is incomplete",
    )
    red = {
        "id": "while-allocation-gc",
        "group": "while",
        "outcome": "600 followed by *** vm: out of memory",
        "classification": (
            "product First Red: the result completes, but the final "
            "allocation leaves mem_oom set despite a transient live set"
        ),
        "screen": bind(screen),
        "image": bind(image),
        "fail_closed_frame": False,
        "live_prompt": True,
    }
    observations["status"] = "first-red-while-allocation-gc"
    observations["first_red"] = red
    atomic_json(OBSERVATIONS, observations)
    value = {
        "format": "lisp65-c2.2-link77-phase-v-hardware-receipt-v1",
        "recorded_on": "2026-07-29",
        "status": "first-red-while-allocation-gc-oom",
        "candidate": {
            "product": deployment["product"],
            "elf": deployment["elf"],
        },
        "passed_rows": observations["rows"],
        "first_red": red,
        "harness_corrections": observations["harness_corrections"],
        "remaining_rows_not_run": list(ROW_IDS[5:]),
        "authority": {
            "contract": bind(CONTRACT),
            "preparation": bind(PREPARATION),
            "link": bind(LINK_RECEIPT),
            "observations": bind(OBSERVATIONS),
        },
        "execution_accounting": {
            "physical_device_sessions": 1,
            "product_deployments": 1,
            "product_links": 0,
            "diagnostic_deployments": 0,
        },
        "claim_limit": (
            "The five listed rows passed.  The corrected allocation row "
            "returned 600 but set mem_oom; RUN/STOP, random, IRQ readback "
            "and DIRMISS were not run."
        ),
    }
    atomic_json(RECEIPT, value)
    print(
        "c2-phase-v-link77-hw: FIRST RED RECEIPTED "
        "while-allocation-gc outcome='600 + VM_OOM'"
    )


def finalize() -> None:
    verify()
    observations = load(OBSERVATIONS)
    deployment = load(DEPLOYMENT)
    core = OUT / "device-core-id.bin"
    require(
        [row["id"] for row in observations["rows"]] == list(ROW_IDS)
        and core.stat().st_size == 4,
        "Link-77 hardware rows or core identity incomplete",
    )
    readbacks = []
    for row in deployment["preloads"]:
        source = ROOT / row["path"]
        target = OUT / f"readback-{source.name}"
        require(
            target.stat().st_size == source.stat().st_size
            and sha(target) == sha(source) == row["sha256"],
            f"Link-77 upload readback drift: {row['role']}",
        )
        readbacks.append({
            "role": row["role"],
            "source": bind(source),
            "readback": bind(target),
            "byteidentical": True,
        })
    value = {
        "format": "lisp65-c2.2-link77-phase-v-hardware-receipt-v1",
        "recorded_on": "2026-07-29",
        "status":
            "passed-Link77-while-random-IRQ-DIRMISS-one-session",
        "candidate": {
            "product": deployment["product"],
            "elf": deployment["elf"],
        },
        "device": {
            "core_id": bind(core),
            "m65": bind(M65),
        },
        "rows": observations["rows"],
        "groups": {
            "while": "passed",
            "random": "passed",
            "interrupt_ownership": "passed-(0 0 0)",
            "DIRMISS": "passed-full-symbol-and-live-prompt",
        },
        "upload_readbacks": readbacks,
        "authority": {
            "contract": bind(CONTRACT),
            "preparation": bind(PREPARATION),
            "link": bind(LINK_RECEIPT),
            "observations": bind(OBSERVATIONS),
        },
        "execution_accounting": {
            "physical_device_sessions": 1,
            "product_links": 0,
            "diagnostic_deployments": 0,
        },
        "claim_limit": (
            "Only the fifteen listed Link-77 rows and upload identities are "
            "claimed; no defstruct/require, streamed-loop timing or random "
            "entropy-quality claim is made."
        ),
    }
    atomic_json(RECEIPT, value)
    observations["status"] = "passed-and-receipted"
    observations["receipt"] = bind(RECEIPT)
    atomic_json(OBSERVATIONS, observations)
    print(
        "c2-phase-v-link77-hw: FINAL PASS "
        f"rows={len(ROW_IDS)}/{len(ROW_IDS)} one-session"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=(
            "prepare", "rebind-harness", "verify", "record-row", "record-run-stop",
            "record-allocation-red", "finalize",
        ),
    )
    parser.add_argument("--id")
    parser.add_argument("--screen", type=Path)
    parser.add_argument("--image", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
    elif args.action == "rebind-harness":
        rebind_harness()
    elif args.action == "verify":
        verify()
    elif args.action == "record-row":
        require(
            args.id is not None
            and args.screen is not None
            and args.image is not None,
            "record-row requires --id, --screen and --image",
        )
        record_row(args.id, args.screen, args.image)
    elif args.action == "record-run-stop":
        require(
            args.screen is not None and args.image is not None,
            "record-run-stop requires --screen and --image",
        )
        record_run_stop(args.screen, args.image)
    elif args.action == "record-allocation-red":
        require(
            args.screen is not None and args.image is not None,
            "record-allocation-red requires --screen and --image",
        )
        record_allocation_red(args.screen, args.image)
    else:
        finalize()


if __name__ == "__main__":
    try:
        main()
    except (HardwareError, SCREEN.CheckError, OSError, ValueError,
            KeyError, json.JSONDecodeError) as error:
        print(f"c2-phase-v-link77-hw: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
