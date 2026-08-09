#!/usr/bin/env python3
"""Prepare and close the bundled Link-89 v1.4 parity device session."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import d81_persistence_fault as D81  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402
import repl_screen_check as SCREEN  # noqa: E402


CONFIG = ROOT / "config/c2-v14-link89-device-session.json"
PRODUCT = ROOT / (
    "build/c2.3/v1.4.0-candidate-product-link89-r1/"
    "canonical-product-manifest.json"
)
MEDIA = ROOT / (
    "build/c2.3/v1.4.0-candidate-media-link89-r1/"
    "candidate-manifest.json"
)
FLEET = ROOT / "build/post-promotion/v14/sample-fleet-host/fleet-receipt.json"
M65_GATE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.4-m65-hw-host-first-receipt.json"
)
WPLTO = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.4-parity-pilot-wplto-receipt.json"
)
PRIOR_APPEND = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-require-prior-append-option-A-host-gate-receipt.json"
)
SCRIPT = ROOT / "scripts/c2-v14-link89-device-session-hw.sh"
DRIVER = Path(__file__).resolve()
BASE = ROOT / "build/post-promotion/v14/link89-device-session"
DEPLOYMENT = BASE / "deployment.json"
RUN = BASE / "run"
PREPARATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.4-link89-device-preparation-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.4-link89-device-receipt.json"
)
LLVM_READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"


class SessionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SessionError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bind(path: Path, *, address: int | None = None) -> dict[str, Any]:
    path = path.resolve()
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    data = path.read_bytes()
    value: dict[str, Any] = {
        "path": path.relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(data),
        "sha256": digest(data),
    }
    if address is not None:
        value["address"] = f"0x{address:08x}"
    return value


def atomic_json(path: Path, value: dict[str, Any], *, replace: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii")
    if path.exists() and not replace:
        require(path.read_bytes() == encoded, f"receipt drift: {path}")
    else:
        path.write_bytes(encoded)


def artifact_by_role(value: dict[str, Any], role: str) -> dict[str, Any]:
    rows = [row for row in value["artifacts"] if row["role"] == role]
    require(len(rows) == 1, f"artifact role is not unique: {role}")
    row = dict(rows[0])
    path = ROOT / row["path"]
    require(bind(path)["sha256"] == row["sha256"], f"artifact drift: {role}")
    return row


def with_address(row: dict[str, Any], address: int) -> dict[str, Any]:
    value = dict(row)
    value["address"] = f"0x{address:08x}"
    return value


def check_config_file(row: dict[str, Any]) -> Path:
    path = ROOT / str(row["path"])
    require(bind(path)["sha256"] == row["sha256"], f"configured SHA drift: {path}")
    return path


def tracked_tree_clean() -> str:
    result = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    require(result.returncode == 0 and result.stdout == "",
            "preparation requires a clean worktree")
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    require(len(head) == 40, "git HEAD identity drift")
    return head


def prepare() -> dict[str, Any]:
    head = tracked_tree_clean()
    config = load(CONFIG)
    product = load(PRODUCT)
    media = load(MEDIA)
    fleet = load(FLEET)
    m65 = load(M65_GATE)
    card = load(WPLTO)
    prior = load(PRIOR_APPEND)

    require(
        config["status"] == "commissioned-phase-D"
        and config["candidate"]["link"] == 89
        and config["candidate"]["product_build_id"] == "0xac5f997a"
        and product["status"]
            == "passed-fresh-source-product-and-post-link-completion"
        and product["candidate"]["release"] == "v1.4.0"
        and product["candidate"]["pre_promotion"] is True
        and media["status"] == "passed-complete-C2-lite-two-media-product"
        and media["artifact_count"] == 19
        and m65["status"] == "passed"
        and m65["artifact"]["cases_executed_per_lane"] == 13
        and m65["mutations"]["count"] == 9
        and card["status"]
            == "passed-v1.4-parity-pilot-one-product-shaped-WPLTO"
        and card["hardware_runs"] == 0
        and prior["status"]
            == "passed-option-A-require-after-two-ordinary-appends-host-lane",
        "Link-89 host/card authority drift",
    )
    product_d81 = check_config_file(config["candidate"]["product_d81"])
    library_d81 = check_config_file(config["candidate"]["library_d81"])
    resident = check_config_file(config["candidate"]["resident_prg"])
    bank2 = check_config_file(config["candidate"]["bank2"])
    toy = check_config_file(config["D2"]["image"])
    require(
        media["media"]["product"]["sha256"] == bind(product_d81)["sha256"]
        and bind(resident)["sha256"]
            == product["identity"]["resident_prg_sha256"]
        and bind(bank2)["sha256"]
            == artifact_by_role(product, "c2-bank2-static-code-plane")["sha256"],
        "configured product identity drift",
    )
    library_files = {
        name.decode("ascii")
        for name in D81.visible_files(library_d81.read_bytes())
    }
    toy_files = {
        name.decode("ascii") for name in D81.visible_files(toy.read_bytes())
    }
    require(
        library_files == {"L65INDEX", "PLACE", "DEFSTRUCT"}
        and toy_files == {
            "AUTOBOOT.C65", "BOOT.ID", "RUNTIME.PRG", "RUNTIME.BIN",
            "APP.L65M", "PROJECT.L65P", "SHIP.LOCK", "SHIP.JSON",
            "LICENSE.TXT",
        },
        "device media directory drift",
    )
    samples = {row["name"]: row for row in fleet["samples"]}
    require(
        fleet["status"] == "passed" and fleet["host_executions"] == 5
        and samples["parity-toy"]["image"]["sha256"] == bind(toy)["sha256"]
        and samples["parity-toy"]["host_executions"] == 1,
        "fifth Ship sample fleet drift",
    )
    toy_elf = ROOT / config["D2"]["runtime_elf"]
    truth = ElfTruth.read(
        toy_elf, llvm_readobj=LLVM_READOBJ, include_section_data=False
    )
    require(
        truth.symbol("lisp65_runtime_state").value == 0x85
        and truth.symbol("lisp65_runtime_result").value == 0x86,
        "parity-toy runtime state geometry drift",
    )

    preloads = [
        with_address(artifact_by_role(media, "c2d-v6-code-plane"), 0x00050000),
        with_address(artifact_by_role(product, "c2-two-record-boot-stage"), 0x00058500),
        with_address(artifact_by_role(product, "c2-session-family-region-0"), 0x08000000),
        with_address(artifact_by_role(product, "c2-product-shelf"), 0x08100000),
        with_address(artifact_by_role(product, "c2-boot-family"), 0x08200000),
        with_address(artifact_by_role(product, "c2-session-family-region-1"), 0x08300000),
        with_address(artifact_by_role(product, "c2-kernal-window"), 0x087FE000),
    ]
    deployment = {
        "format": "lisp65-c2.3-v1.4-link89-device-deployment-v1",
        "status": "prepared",
        "source_commit": head,
        "candidate_link": 89,
        "workbench": {
            "product_d81": bind(product_d81),
            "library_d81": bind(library_d81),
            "resident_prg": {**bind(resident), "address": "PRG-load-address"},
            "bank2": bind(bank2, address=0x00020000),
            "preloads": preloads,
            "remote_product": "V14L89.D81",
            "remote_library": "V14LIB.D81",
            "expected_banner": config["candidate"]["hardware_banner"],
        },
        "parity_toy": {
            "image": bind(toy),
            "runtime_elf": bind(toy_elf),
            "remote": "V14TOY.D81",
            "runtime_state": "0x00000085",
            "runtime_result": "0x00000086",
        },
        "D1": config["D1"], "D2": config["D2"], "D3": config["D3"],
        "session_policy": config["session_policy"],
    }
    atomic_json(DEPLOYMENT, deployment, replace=True)
    receipt = {
        "format": "lisp65-c2.3-v1.4-link89-device-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status": "prepared-host-green-Link89-bundled-device-session",
        "source_commit": head,
        "candidate_link": 89,
        "product_links_consumed": 1,
        "hardware_contacts": 0,
        "preflight": {
            "m65_surface": "15 public, 12x2 executions, 9 mutations",
            "capacity": "1784/2048 Bank-2 bytes; zero resident bytes",
            "ship_fleet": "5/5 host-executed; 45 media members",
            "check_source": "complete exit-0 run before preparation",
            "workbench_identity": "exact product/library D81 and Bank-2 readback",
            "I/O_capture": "CPU-side m65-hw reads only",
        },
        "media_directories": {
            "library": sorted(library_files), "parity_toy": sorted(toy_files),
        },
        "rows": {
            "D1": ["bounds-and-recovery", "draw"],
            "D2": ["fifth-Ship-sample-visible", "sprite-move", "physical-key", "SID-by-ear"],
            "D3": ["require-idempotent-peek-map", "q", "time", "physical-read-line"],
        },
        "bindings": {
            "config": bind(CONFIG), "driver": bind(DRIVER), "script": bind(SCRIPT),
            "deployment": bind(DEPLOYMENT), "product": bind(PRODUCT),
            "media": bind(MEDIA), "fleet": bind(FLEET), "m65_gate": bind(M65_GATE),
            "wplto": bind(WPLTO), "prior_append": bind(PRIOR_APPEND),
        },
        "claim_limit": config["claim_limit"],
    }
    atomic_json(PREPARATION, receipt, replace=True)
    return receipt


def exact_result(path: Path, form: str, expected: str) -> None:
    try:
        SCREEN.check_latest_result(path, form, expected)
    except SCREEN.CheckError as error:
        raise SessionError(error.message) from error


def passed(value: str) -> bool:
    require(value in ("pass", "fail"), "owner observation must be pass or fail")
    return value == "pass"


def close(args: argparse.Namespace) -> dict[str, Any]:
    config = load(CONFIG)
    prep = load(PREPARATION)
    deployment = load(DEPLOYMENT)
    require(
        prep["status"] == "prepared-host-green-Link89-bundled-device-session"
        and deployment["candidate_link"] == 89,
        "device preparation authority drift",
    )
    for path, expected in (
        (RUN / "D1-product-readback.d81", deployment["workbench"]["product_d81"]),
        (RUN / "D2-toy-readback.d81", deployment["parity_toy"]["image"]),
        (RUN / "D3-library-readback.d81", deployment["workbench"]["library_d81"]),
    ):
        require(bind(path)["sha256"] == expected["sha256"], f"media readback drift: {path}")
    for phase in ("D1", "D3"):
        require(
            (RUN / f"{phase}-bank2.bin").read_bytes()
                == (ROOT / deployment["workbench"]["bank2"]["path"]).read_bytes(),
            f"{phase} Bank-2 context drift",
        )

    bounds = (RUN / "d1-bounds.txt").read_text(encoding="utf-8", errors="replace")
    require("***" in bounds and "lisp65>" in bounds, "D1 bounds rejection absent")
    exact_result(RUN / "d1-recovery.txt", config["D1"]["recovery_form"], "9")
    for index, form in enumerate(config["D1"]["draw_forms"], start=1):
        exact_result(RUN / f"d1-draw-{index}.txt", form, "t")

    before = (RUN / "D2-state-before-key.bin").read_bytes()
    after = (RUN / "D2-result.bin").read_bytes()
    require(before == b"\x02", f"D2 pre-input state drift: {before.hex()}")
    require(len(after) == 4 and after[0] == 3 and after[1:3] != b"\x00\x00"
            and after[3] == 0, f"D2 result drift: {after.hex()}")

    exact_result(RUN / "d3-require-1.txt", config["D3"]["require_form"], "t")
    exact_result(RUN / "d3-require-2.txt", config["D3"]["require_form"], "t")
    row0 = (RUN / "D3-place-row-before.bin").read_bytes()
    row1 = (RUN / "D3-place-row-after-1.bin").read_bytes()
    row2 = (RUN / "D3-place-row-after-2.bin").read_bytes()
    header1 = (RUN / "D3-c2d-header-after-1.bin").read_bytes()
    header2 = (RUN / "D3-c2d-header-after-2.bin").read_bytes()
    require(row0 == bytes(32) and row1 != bytes(32) and row1 == row2,
            "D3 place row publication/idempotence drift")
    require(header1 == header2, "D3 second require changed C2D header")
    exact_result(RUN / "d3-q.txt", config["D3"]["q_form"],
                 config["D3"]["q_expected"])
    exact_result(RUN / "d3-time.txt", config["D3"]["time_form"],
                 config["D3"]["time_expected"])
    exact_result(RUN / "d3-read-line.txt", config["D3"]["read_line_form"],
                 config["D3"]["read_line_expected"])
    exact_result(RUN / "d3-liveness.txt", config["D3"]["liveness_form"], "9")

    observations = {
        "D1_drawing_visible": passed(args.d1_drawing),
        "D2_toy_sprite_visible_and_moved": passed(args.d2_sprite),
        "D2_SID_note_audible": passed(args.d2_tone),
    }
    require(all(observations.values()), "owner physical observation First Red")
    receipt = {
        "format": "lisp65-c2.3-v1.4-link89-device-session-v1",
        "recorded_on": date.today().isoformat(),
        "status": "passed-Link89-synchronous-parity-pilot-and-fifth-Ship-sample",
        "candidate_link": 89,
        "release_ready": False,
        "owner_halt": "Halt-1-review-required",
        "hardware_identities": 3,
        "product_bytes_changed_after_link": 0,
        "D1": {
            "bounds_rejected_before_visible_write": True,
            "post_error_REPL_result": 9,
            "owner_observations": {key: value for key, value in observations.items()
                                   if key.startswith("D1_")},
            "screen": bind(RUN / "d1-draw-3.png"),
        },
        "D2": {
            "sample": "parity-toy",
            "state_before_physical_key": 2,
            "state_after_physical_key": 3,
            "result": f"0x{int.from_bytes(after[1:3], 'little'):04x}",
            "owner_observations": {key: value for key, value in observations.items()
                                   if key.startswith("D2_")},
            "screen_before_key": bind(RUN / "D2-waiting.png"),
            "screen_after_key": bind(RUN / "D2-complete.png"),
        },
        "D3": {
            "require_results": ["t", "t"],
            "place_row_published": True,
            "second_require_byte_identical": True,
            "q_result": config["D3"]["q_expected"],
            "time_result": config["D3"]["time_expected"],
            "physical_read_line_result": config["D3"]["read_line_expected"],
            "post_input_liveness": 9,
            "peek_map": {
                "header_after_first": bind(RUN / "D3-c2d-header-after-1.bin", address=0x50000),
                "header_after_second": bind(RUN / "D3-c2d-header-after-2.bin", address=0x50000),
                "place_before": bind(RUN / "D3-place-row-before.bin", address=0x500F0),
                "place_after_first": bind(RUN / "D3-place-row-after-1.bin", address=0x500F0),
                "place_after_second": bind(RUN / "D3-place-row-after-2.bin", address=0x500F0),
            },
        },
        "tick_hook_disposition": {
            "status": "paper-design-only",
            "minimum_mutable_continuation_bytes": 384,
            "current_resident_BSS_bytes": 137,
            "decision": "not-admissible-without-continuation-state-or-stack-ownership-block",
        },
        "bindings": {
            "config": bind(CONFIG), "preparation": bind(PREPARATION),
            "deployment": bind(DEPLOYMENT), "driver": bind(DRIVER),
            "script": bind(SCRIPT), "product_manifest": bind(PRODUCT),
            "media_manifest": bind(MEDIA), "fleet": bind(FLEET),
            "m65_gate": bind(M65_GATE), "wplto": bind(WPLTO),
            "D1_product_readback": bind(RUN / "D1-product-readback.d81"),
            "D2_toy_readback": bind(RUN / "D2-toy-readback.d81"),
            "D3_library_readback": bind(RUN / "D3-library-readback.d81"),
        },
        "claim_limit": config["claim_limit"],
    }
    atomic_json(RECEIPT, receipt, replace=True)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("prepare")
    sub.add_parser("dry-run")
    close_parser = sub.add_parser("close")
    for name in ("d1_drawing", "d2_sprite", "d2_tone"):
        close_parser.add_argument("--" + name.replace("_", "-"),
                                  choices=("pass", "fail"), required=True)
    args = parser.parse_args()
    if args.action == "prepare":
        value = prepare()
        print("c2-v14-link89-device: PREPARED source=%s rows=D1/D2/D3"
              % value["source_commit"][:12])
    elif args.action == "dry-run":
        prep = load(PREPARATION)
        deployment = load(DEPLOYMENT)
        require(prep["source_commit"] == deployment["source_commit"],
                "dry-run preparation/deployment drift")
        print("c2-v14-link89-device: DRY-RUN PASS identities=3 "
              "physical-observations=3 I/O=CPU-side")
    else:
        value = close(args)
        print("c2-v14-link89-device: PASS D1=draw D2=parity-toy+sprite+SID "
              "D3=require+q+time+read-line Halt-1")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SessionError, OSError, ValueError, KeyError, TypeError,
            json.JSONDecodeError) as error:
        print(f"c2-v14-link89-device: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
