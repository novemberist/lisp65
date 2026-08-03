#!/usr/bin/env python3
"""Prepare and close the Link-84 Ship/read-line/editor hardware session."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402
import c2_link75_library_media_successor as MEDIA  # noqa: E402
import c2_require_resolver_gate as L65I  # noqa: E402
import c2_require_prior_append_option_a_gate as OPTION_A  # noqa: E402
import repl_screen_check as SCREEN  # noqa: E402


CONFIG = ROOT / "config/c2-ship-builder-v1-hardware-session.json"
PLAN = ROOT / "docs/planning/1.3-ship-builder-work-plan.md"
CARD = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-bank2-read-line-wplto-receipt.json"
)
BANNER = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-banner-identity-rebind-receipt.json"
)
CANDIDATE = ROOT / (
    "build/c2.3/v1.3.0-candidate-product-link84-r1/"
    "canonical-product-manifest.json"
)
MEDIA_MANIFEST = ROOT / (
    "build/c2.3/v1.3.0-candidate-media-r1/candidate-manifest.json"
)
FLEET = ROOT / "build/ship-builder/v13/final-fleet-bank2/fleet-receipt.json"
BASE_DEFSTRUCT = ROOT / (
    "build/post-release/link78-dirmiss-renderer/d1-d2-bundled-session/"
    "library-media/require-defstruct-link78-bound.d81"
)
DRIVER = Path(__file__).resolve()
SCRIPT = ROOT / "scripts/c2-v13-closing-hw.sh"
OUT = ROOT / "build/ship-builder/v13/closing-device-session"
DEPLOYMENT = OUT / "deployment.json"
PREPARATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-link84-closing-device-preparation-receipt.json"
)
HARDWARE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-link84-closing-device-receipt.json"
)
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
RANDOM_SUITE = ROOT / "tests/bytecode/libs/p0-stdlib-random-base.json"
Q_CONTRACT = ROOT / "config/c2-q-contract.json"
Q_HARDWARE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.4-phase-m-hardware-receipt.json"
)
RANDOM_Q_SOURCE = ROOT / "examples/ship/random-q/main.l65"


class SessionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SessionError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    path = path.resolve()
    require(path.is_file(), f"bound file absent: {path}")
    value: dict[str, Any] = {
        "path": path.relative_to(ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }
    if address is not None:
        value["address"] = f"0x{address:08x}"
    return value


def check_binding(row: dict[str, Any]) -> Path:
    path = ROOT / row["path"]
    require(
        path.is_file()
        and ("bytes" not in row or path.stat().st_size == row["bytes"])
        and sha(path) == row["sha256"],
        f"binding drift: {path}",
    )
    return path


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def rebind_defstruct_media(build_id: int) -> Path:
    require(BASE_DEFSTRUCT.is_file(), "base defstruct medium absent")
    out = OUT / "library-media"
    out.mkdir(parents=True, exist_ok=True)
    locators = L65I.d81_locators(BASE_DEFSTRUCT)
    artifacts, rows = MEDIA.expected_artifacts(build_id, locators)
    visible0 = L65I.D81.visible_files(BASE_DEFSTRUCT.read_bytes())
    artifact_paths: list[tuple[Path, str]] = []
    for name, data in artifacts.items():
        old = visible0[name.upper().encode("ascii")]
        require(
            len(old) == len(data) and old[64:] == data[64:]
            and struct.unpack_from("<I", data, 22)[0] == build_id,
            f"library artifact changed outside identity envelope: {name}",
        )
        path = out / f"{name}.l65s"
        path.write_bytes(data)
        artifact_paths.append((path, name))
    index = L65I.encode_index(rows)
    require(index == visible0[b"L65INDEX"], "library index drift")
    index_path = out / "l65index"
    index_path.write_bytes(index)
    decoded = L65I.decode_index(
        index, artifacts, artifact_build_id=build_id)
    require(
        L65I.resolve(decoded, "defstruct", 7, [], L65I.CAPACITY) == [0, 1]
        and len(L65I.mutation_gate(
            index, artifacts, artifact_build_id=build_id)) >= 6,
        "library resolution proof drift",
    )
    d81 = out / "require-defstruct-link84-bound.d81"
    L65I.build_d81(d81, index_path, artifact_paths)
    visible = L65I.D81.visible_files(d81.read_bytes())
    require(
        visible[b"PLACE"] == artifacts["place"]
        and visible[b"DEFSTRUCT"] == artifacts["defstruct"],
        "rebuilt library medium verification failed",
    )
    return d81


def random_q_target_oracle(config: dict[str, Any], fleet: dict[str, Any]
                           ) -> dict[str, Any]:
    """Bind the target result independently of the incomplete Ship host I/O.

    The native Ship runner models keyboard, screen and the frame counter.  It
    does not model the MEGA65 math-unit MMIO surface, so its q contribution is
    intentionally zero.  The target expectation must instead compose the
    independently proved random vector with the Q8.7 contract.
    """
    random_suite = load(RANDOM_SUITE)
    q_contract = load(Q_CONTRACT)
    q_hardware = load(Q_HARDWARE)
    source = RANDOM_Q_SOURCE.read_text(encoding="utf-8")
    cases = {row["name"]: row for row in random_suite["cases"]}
    random_value = int(cases["random-rejection-path"]["expect"])
    require(
        random_value == 179
        and q_contract["representation"]["scale"] == 128
        and q_hardware["M1_math_register_semantics"]["status"]
            == "passed-after-atomic-harness-correction"
        and "(random-seed 7286)" in source
        and "(random 1000)" in source
        and "(q->int (q* (q 3) (q 4)))" in source,
        "random-q target-oracle authority drift",
    )
    q_integer = (3 * 128 * (4 * 128) // 128) // 128
    value = random_value + q_integer
    tagged = (value << 1) | 1
    row = next(item for item in config["D1"]
               if item["id"] == "ship-random-q")
    fleet_row = next(item for item in fleet["samples"]
                     if item["name"] == "random-q")
    require(
        value == 191 and tagged == 0x017F
        and int(row["expected_result"], 16) == tagged
        and "result=0x0167" in fleet_row["host_output"],
        "random-q target/host expectation drift",
    )
    return {
        "random_value": random_value,
        "q_integer": q_integer,
        "target_value": value,
        "target_tagged_word": f"0x{tagged:04x}",
        "native_host_observed_word": "0x0167",
        "native_host_claim_limit": (
            "The Ship native host runner does not model the MEGA65 math-unit "
            "MMIO registers; its q contribution is zero. It proves the real "
            "VM path, not this target result."
        ),
        "authorities": {
            "random_suite": bind(RANDOM_SUITE),
            "q_contract": bind(Q_CONTRACT),
            "q_target_registers": bind(Q_HARDWARE),
            "sample_source": bind(RANDOM_Q_SOURCE),
        },
    }


def validate_exact_library_media(medium: Path, build_id: int) -> dict[str, Any]:
    geometry, _generated, _receipt = OPTION_A.configure_current()
    require(geometry["build_id"] == build_id,
            "Link-84 resolver geometry/build identity drift")
    rows = []
    for prior in (False, True):
        row = OPTION_A.run_case(
            label=f"link84-exact-prior-appends-{int(prior) * 2}",
            media=medium,
            prior_helpers=prior,
        )
        require(
            row["result"] == "t"
            and len(row["loader_attempts"]) == 1
            and len(row["published_appends"]) == 1,
            "exact Link-84 library medium failed host resolver execution",
        )
        rows.append({
            "prior_persistent_appends": 2 if prior else 0,
            "result": row["result"],
            "steps": row["steps"],
            "loader_attempts": len(row["loader_attempts"]),
            "published_appends": len(row["published_appends"]),
        })
    return {
        "status": "passed-exact-Link84-medium-baseline-and-two-appends",
        "rows": rows,
        "medium": bind(medium),
    }


def candidate_binding(config: dict[str, Any]) -> dict[str, Any]:
    link = int(config.get("candidate_link", 84))
    media = load(MEDIA_MANIFEST)
    product = load(CANDIDATE)
    require(
        media["status"] == "passed-complete-C2-lite-two-media-product"
        and media["artifact_count"] == 19
        and product["candidate"]["release"] == "v1.3.0"
        and product["static_plane"]["product_build_id"] == "0x74e2765d"
        and product["static_plane"]["bank2_static_code_bytes"] == 45514,
        f"Link-{link} product/media authority drift",
    )
    by_role = {row["role"]: row for row in media["artifacts"]}
    required = {
        "linked-product-elf", "c2-resident-prg", "product-d81",
        "c2d-v6-code-plane", "c2-two-record-boot-stage",
        "c2-session-family-region-0", "c2-product-shelf",
        "c2-boot-family", "c2-session-family-region-1", "c2-kernal-window",
    }
    require(required <= by_role.keys(),
            f"Link-{link} media role inventory incomplete")
    addresses = {
        "c2d-v6-code-plane": 0x00050000,
        "c2-two-record-boot-stage": 0x00058500,
        "c2-session-family-region-0": 0x08000000,
        "c2-product-shelf": 0x08100000,
        "c2-boot-family": 0x08200000,
        "c2-session-family-region-1": 0x08300000,
        "c2-kernal-window": 0x087FE000,
    }
    preloads = []
    for role, address in addresses.items():
        row = by_role[role]
        path = check_binding(row)
        preloads.append({**bind(path, address), "name": row["name"], "role": role})
    zero = OUT / "zero-c2j.bin"
    zero.parent.mkdir(parents=True, exist_ok=True)
    zero.write_bytes(bytes(64))
    preloads.append({
        **bind(zero, 0x0005C640), "name": zero.name,
        "role": "harness-zero-C2J-baseline",
    })
    # L65S headers bind the product's embedded static-plane build identity,
    # not the outer media/profile receipt identity.  Using profile_build_id
    # here produces a structurally valid D81 which the real resolver must
    # reject after it reaches the target.
    library = rebind_defstruct_media(
        int(product["static_plane"]["product_build_id"], 0))
    return {
        "release": "v1.3.0", "link": link,
        "product_build_id": media["product_build_id"],
        "profile_build_id": media["profile_build_id"],
        "artifact_set_sha256": media["artifact_set_sha256"],
        "product": {**bind(check_binding(by_role["c2-resident-prg"]), 0x2001),
                    "role": "c2-resident-prg"},
        "ELF": {**bind(check_binding(by_role["linked-product-elf"])),
                "role": "linked-product-elf"},
        "package_medium": bind(check_binding(by_role["product-d81"])),
        "library_medium": bind(library),
        "remote_media": config["D3"]["remote_media"],
        "remote_library_media": config["D3"]["remote_library_media"],
        "preloads": preloads,
    }


def prepare() -> dict[str, Any]:
    config = load(CONFIG)
    link = int(config.get("candidate_link", 84))
    commissioned_status = (
        f"owner-commissioned-link{link}-full-reset-closing-session"
        if link != 84 else "owner-commissioned-link84-closing-session"
    )
    require(
        config["status"] == commissioned_status
        and config["admission"]["hardware_authorized_now"] is True
        and config["policy"]["cold_reset_before_every_identity"]
        and config["policy"]["persistent_forms_are_quiet"]
        and not config["policy"]["screenshot_polling_around_persistent_forms"],
        f"Link-{link} closing-session policy drift",
    )
    require(
        config["D3"]["keys"] in (30, 64)
        and config["D3"]["transport_mode"] == "one-key-per-invocation"
        and config["D3"]["transport_inter_key_seconds"] == 1,
        "quiet editor transport pacing drift",
    )
    card = load(CARD)
    banner = load(BANNER)
    require(
        card["inherited_native_geometry"]["status"] == "restored-exactly"
        and banner["status"]
            == "passed-linker-free-regular-v1.3-banner-identity-rebind",
        f"Link-{link} card/banner admission drift",
    )
    fleet = load(FLEET)
    require(
        fleet["status"] == "passed" and fleet["sample_count"] == 4
        and fleet["host_executions"] == 4
        and fleet["media_members_verified"] == 36,
        "four-sample host fleet drift",
    )
    target_oracle = (
        random_q_target_oracle(config, fleet)
        if any(row["id"] == "ship-random-q" for row in config["D1"])
        else {
            "status": "not-applicable-row-not-in-successor-session",
            "hardware_claim": "none",
        }
    )
    fleet_rows = {row["name"]: row for row in fleet["samples"]}
    d1 = []
    for row in config["D1"]:
        name = row["id"].removeprefix("ship-")
        require(name in fleet_rows, f"unbound Ship sample: {row['id']}")
        image = ROOT / row["image"]
        elf = ROOT / row["elf"]
        require(
            sha(image) == fleet_rows[name]["image"]["sha256"],
            f"Ship image drift: {row['id']}",
        )
        truth = ElfTruth.read(elf, llvm_readobj=READOBJ)
        runtime = {
            symbol: truth.symbol(symbol).value
            for symbol in (
                "lisp65_runtime_state", "lisp65_runtime_result",
                "lisp65_runtime_preload_detail",
            )
        }
        require(
            runtime["lisp65_runtime_result"]
                == runtime["lisp65_runtime_state"] + 1
            and runtime["lisp65_runtime_preload_detail"]
                == runtime["lisp65_runtime_state"] + 3,
            f"Ship result span drift: {row['id']}",
        )
        d1.append({
            **row, "image": bind(image), "ELF": bind(elf),
            "addresses": {key: f"0x{value:08x}" for key, value in runtime.items()},
        })
    candidate = candidate_binding(config)
    library_host = validate_exact_library_media(
        ROOT / candidate["library_medium"]["path"],
        int(product_build_id := load(CANDIDATE)["static_plane"]
            ["product_build_id"], 0),
    )
    require(product_build_id == "0x74e2765d",
            f"Link-{link} embedded product identity drift")
    d3 = {
        **candidate,
        **{key: config["D3"][key] for key in (
            "deployment",
            "editor_form", "character", "keys", "transport_mode",
            "transport_inter_key_seconds", "quiet_seconds",
            "query_form", "expected")},
    }
    preparation_status = (
        "prepared-four-ship-samples-link84-D3-D4"
        if link == 84
        else f"prepared-{len(d1)}-ship-samples-link{link}-D3-D4"
    )
    value = {
        "format": "lisp65-c2.3-v1.3-closing-deployment-v1",
        "recorded_on": date.today().isoformat(),
        "status": f"prepared-host-green-link{link}-closing-session",
        "D1": d1, "D3": d3, "D4": config["D4"],
        "policy": config["policy"],
    }
    write_json(DEPLOYMENT, value)
    prep = {
        "format": "lisp65-c2.3-v1.3-closing-device-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status": preparation_status,
        "promotable": False, "hardware_runs": 0,
        "rows": {
            "D1": [row["id"] for row in d1],
            "D2": "not-retried-concluded-product-first-red",
            "D3": ["quiet-editor-typing", "buffer-length", "post-stop-repl"],
            "D4": [row["id"] for row in config["D4"]],
        },
        "safety": {
            "cold_reset_before_every_identity": True,
            "ftp_progress_guard_seconds": 120,
            "quiet_persistent_and_typing_windows": True,
            "zero_C2J_preload": bind(OUT / "zero-c2j.bin", 0x0005C640),
        },
        "authorities": {
            "config": bind(CONFIG), "plan": bind(PLAN), "card": bind(CARD),
            "banner": bind(BANNER), "candidate": bind(CANDIDATE),
            "candidate_media": bind(MEDIA_MANIFEST), "fleet": bind(FLEET),
            "driver": bind(DRIVER), "script": bind(SCRIPT),
            "shared_driver": bind(
                ROOT / "scripts/c2-v13-closing-device.py"),
            "shared_script": bind(ROOT / "scripts/c2-v13-closing-hw.sh"),
            "deployment": bind(DEPLOYMENT),
        },
        "target_oracles": {"random_q": target_oracle},
        "D4_exact_medium_host_execution": library_host,
        "next_gate": "one physical closing session, then Halt #2",
        "claim_limit": "Host preparation only; no device or release claim.",
    }
    write_json(PREPARATION, prep)
    return value


def read_result(path: Path) -> bytes:
    data = path.read_bytes()
    require(len(data) == 4, f"Ship result width drift: {path}")
    return data


def record_first_red() -> dict[str, Any]:
    """Bind the completed contact without laundering tool rows into product.

    This recorder is deliberately separate from ``evaluate``: the corrected
    random oracle and D4 medium were learned after the physical contact, while
    D3 produced a release-terminal semantic-liveness failure.
    """
    deployment = load(DEPLOYMENT)
    preparation = load(PREPARATION)
    run = OUT / "run"
    expected_raw = {
        "ship-hello": bytes.fromhex("03550000"),
        "ship-random-q": bytes.fromhex("037f0100"),
        "ship-long-runner": bytes.fromhex("03c15d00"),
        "ship-interactive": bytes.fromhex("02000000"),
    }
    d1_rows = []
    for row in deployment["D1"]:
        identifier = row["id"]
        raw_path = run / f"{identifier}-result.bin"
        raw = read_result(raw_path)
        require(raw == expected_raw[identifier],
                f"recorded Ship result drift: {identifier}")
        source = ROOT / row["image"]["path"]
        readback = run / f"{identifier}-package-readback.d81"
        require(source.read_bytes() == readback.read_bytes(),
                f"recorded Ship medium drift: {identifier}")
        SCREEN.check_fail_closed_frame(run / f"{identifier}.png")
        status = (
            "unclaimed-input-injected-before-runtime-ready"
            if identifier == "ship-interactive"
            else "passed-exact-target-result"
        )
        d1_rows.append({
            "id": identifier,
            "status": status,
            "raw_state_and_result": raw.hex(),
            "result": bind(raw_path,
                           int(row["addresses"]["lisp65_runtime_state"], 16)),
            "screen": bind(run / f"{identifier}.png"),
            "screen_text": bind(run / f"{identifier}.txt"),
            "package_readback": bind(readback),
        })

    quiet_text = (run / "editor-quiet-end.txt").read_text(
        encoding="utf-8", errors="replace")
    retained = max((len(item) for item in re.findall(r"a+", quiet_text)),
                   default=0)
    stopped = (run / "editor-stopped.txt").read_text(
        encoding="utf-8", errors="replace")
    query = (run / "editor-query.txt").read_text(
        encoding="utf-8", errors="replace")
    post = (run / "editor-post-stop.txt").read_text(
        encoding="utf-8", errors="replace")
    require(
        retained == 30
        and "*** stopped (run/stop)" in stopped
        and "lisp65>" in stopped
        and "*** vm: undefined function #0ab" in query
        and "(+ 4 5)" in post
        and "*** vm: undefined function #0ab" in post,
        "D3 First-Red evidence drift",
    )
    for name in ("editor-quiet-end", "editor-stopped", "editor-query",
                 "editor-post-stop"):
        SCREEN.check_fail_closed_frame(run / f"{name}.png")

    d4_readback = run / "D4-package-readback.d81"
    visible = L65I.D81.visible_files(d4_readback.read_bytes())
    old_ids = {
        name: f"0x{struct.unpack_from('<I', visible[name], 22)[0]:08x}"
        for name in (b"PLACE", b"DEFSTRUCT")
    }
    require(
        set(old_ids.values()) == {"0xd1ebda49"}
        and sha(d4_readback)
            != preparation["D4_exact_medium_host_execution"]["medium"]["sha256"],
        "D4 wrong-identity attribution drift",
    )
    require(
        "*** vm: bad bytecode" in (run / "standing-require-place.txt").read_text(
            encoding="utf-8", errors="replace"),
        "D4 recorded error drift",
    )
    result = {
        "format": "lisp65-c2.3-v1.3-link84-closing-device-first-red-v1",
        "recorded_on": date.today().isoformat(),
        "status": "FIRST-RED-Link84-editor-semantic-liveness-owner-review",
        "promotable": False,
        "release_ready": False,
        "product_links_created": 0,
        "D1": {
            "status": "three-passed-one-tool-unclaimed",
            "rows": d1_rows,
            "random_q_oracle_correction":
                preparation["target_oracles"]["random_q"],
        },
        "D3": {
            "status": "FIRST-RED-post-stop-REPL-not-semantically-live",
            "requested_keys": deployment["D3"]["keys"],
            "visibly_retained_keys": retained,
            "delivery_cardinality_claimed": False,
            "delivery_limit": (
                "The one-call delayed multi-key helper remained "
                "unacknowledged and retained only 30 visible keys."
            ),
            "independent_product_failure": (
                "RUN/STOP returned a visible prompt, but the bound editor "
                "query failed with VM DIRMISS #0ab and the following trivial "
                "(+ 4 5) failed identically; semantic REPL liveness is red."
            ),
            "evidence": {
                name: bind(run / f"{name}{suffix}")
                for name, suffix in (
                    ("editor-quiet-end", ".png"),
                    ("editor-stopped", ".png"),
                    ("editor-query", ".txt"),
                    ("editor-post-stop", ".txt"),
                )
            },
        },
        "D4": {
            "status": "tool-invalid-wrong-L65S-product-identity-no-product-claim",
            "observed_L65S_build_ids": {
                key.decode("ascii").lower(): value
                for key, value in old_ids.items()
            },
            "required_embedded_product_build_id": "0x74e2765d",
            "corrected_medium_host_execution":
                preparation["D4_exact_medium_host_execution"],
            "first_error": bind(run / "standing-require-place.txt"),
            "dependent_rows_unclaimed": ["standing-q", "standing-time"],
            "package_readback": bind(d4_readback),
        },
        "tool_first_reds": [
            "D3 manual deployment raced candidate AUTOBOOT",
            "D3 fixed 20-second AUTOBOOT wait ended before measured convergence",
            "D3 unacknowledged multi-character keyboard transport lost keys",
            "D1 random-q host oracle omitted target math-unit MMIO",
            "D1 interactive input was injected before runtime state 2",
            "D4 library artifacts were rebound to profile_build_id instead of the embedded product_build_id",
        ],
        "corrected_unrun_rows": [
            "ship-interactive runtime-state-gated input",
            "D3 one-key-per-invocation quiet transport",
            "D4 exact-product-identity require/q/time",
        ],
        "bindings": {
            "preparation": bind(PREPARATION),
            "deployment": bind(DEPLOYMENT),
            "driver": bind(DRIVER),
            "script": bind(SCRIPT),
        },
        "next_gate": (
            "Owner disposition of the release-terminal D3 semantic-liveness "
            "First Red before any further hardware contact or v1.3 release."
        ),
        "claim_limit": (
            "This receipt binds one Link-84 closing contact. It proves three "
            "standalone target results and one D3 semantic-liveness First Red. "
            "The interactive Ship row and all D4 rows remain unclaimed because "
            "their harness preconditions were wrong; no acceptance or release "
            "claim is made."
        ),
    }
    write_json(HARDWARE, result)
    return result


def evaluate() -> dict[str, Any]:
    deployment = load(DEPLOYMENT)
    preparation = load(PREPARATION)
    link = int(deployment["D3"]["link"])
    expected_preparation = (
        "prepared-four-ship-samples-link84-D3-D4"
        if link == 84 else
        f"prepared-{len(deployment['D1'])}-ship-samples-link{link}-D3-D4"
    )
    require(preparation["status"] == expected_preparation,
            "closing preparation drift")
    run = OUT / "run"
    ships = []
    for row in deployment["D1"]:
        raw = read_result(run / f"{row['id']}-result.bin")
        expected = int(row["expected_result"], 16)
        require(raw == bytes((3, expected & 0xff, expected >> 8, 0)),
                f"Ship result drift: {row['id']} got={raw.hex()}")
        SCREEN.check_fail_closed_frame(run / f"{row['id']}.png")
        if row["id"] == "ship-interactive":
            text = (run / f"{row['id']}.txt").read_text(errors="ignore")
            require(row["expected_screen_text"] in text,
                    "interactive Ship response absent")
        source = ROOT / row["image"]["path"]
        readback = run / f"{row['id']}-package-readback.d81"
        require(source.read_bytes() == readback.read_bytes(),
                f"Ship medium readback drift: {row['id']}")
        ships.append({
            "id": row["id"], "result": row["expected_result"],
            "readback": bind(run / f"{row['id']}-result.bin",
                             int(row["addresses"]["lisp65_runtime_state"], 16)),
            "screen": bind(run / f"{row['id']}.png"),
            "package_readback": bind(readback),
        })
    SCREEN.check_fail_closed_frame(run / "editor-quiet-end.png")
    SCREEN.check_latest_result(
        run / "editor-query.txt", deployment["D3"]["query_form"],
        deployment["D3"]["expected"], allow_editor_status_tail=True)
    SCREEN.check_latest_result(
        run / "editor-post-stop.txt", "(+ 4 5)", "9",
        allow_editor_status_tail=True)
    for row in deployment["D4"]:
        SCREEN.check_latest_result(
            run / f"{row['id']}.txt", row["form"], row["expected"])
        SCREEN.check_fail_closed_frame(run / f"{row['id']}.png")
    result = {
        "format": "lisp65-c2.3-v1.3-closing-device-receipt-v1",
        "recorded_on": date.today().isoformat(),
        "status": f"passed-link{link}-ship-samples-editor-and-D4",
        "hardware_sessions": int(load(CONFIG).get(
            "expected_hardware_sessions", 2)),
        "tool_first_reds": ([{
            "id": "D3-manual-load-raced-candidate-autoboot",
            "contact": 1,
            "classification": "harness-deployment-order",
            "mechanism": (
                "The mounted candidate medium owns AUTOBOOT.C65; the old "
                "runner manually reloaded the product while AUTOBOOT was "
                "already taking ownership. m65 reported an undrained BASIC "
                "key buffer and the REPL precondition never formed."
            ),
            "product_rows_executed": 0,
            "screen": bind(run / "D3-boot.png"),
            "screen_text": bind(run / "D3-boot.txt"),
            "transport_log": bind(run / "D3-upload.log"),
        }, {
            "id": "D3-autoboot-convergence-timeout",
            "contact": 2,
            "classification": "harness-boot-wait",
            "mechanism": (
                "The canonical AUTOBOOT path was still on the BASIC 65 "
                "splash at the runner's fixed 20-second check and reached "
                "the WORKBENCH 1.3.0 REPL roughly 14 seconds later."
            ),
            "product_rows_executed": 0,
            "early_screen": bind(run / "D3-retry-boot.png"),
            "late_screen": bind(run / "D3-retry-late.png"),
            "late_screen_text": bind(run / "D3-retry-late.txt"),
            "transport_log": bind(run / "D3-retry-upload.log"),
        }, {
            "id": "D3-unpaced-virtual-keyboard-and-status-tail",
            "contact": 2,
            "classification": "harness-input-transport-and-classifier",
            "mechanism": (
                "The known unacknowledged multi-character virtual-keyboard "
                "transport delivered 23 of 64 requested characters. The "
                "subsequent query classifier then rejected the cached IDE "
                "status tail although the evaluator already permits it."
            ),
            "product_rows_executed": (
                "Editor entered, 23 keys retained, 60-second quiet window "
                "survived and RUN/STOP returned a live REPL; the 64-key "
                "postcondition remained unclaimed."
            ),
            "quiet_screen": bind(run / "editor-quiet-end.png"),
            "stopped_screen": bind(run / "editor-stopped.png"),
            "rejected_query_screen": bind(
                run / "editor-query-input-input-attempt-1.png"),
        }] if link == 84 else []),
        "D1": {"status": f"passed-{len(ships)}-standalone-images",
               "rows": ships},
        "D2": {"status": "not-retried-concluded-product-first-red"},
        "D3": {"status": "passed-quiet-editor-typing",
               "keys": deployment["D3"]["keys"]},
        "D4": {"status": "passed-require-q-time",
               "rows": [row["id"] for row in deployment["D4"]]},
        "bindings": {"preparation": bind(PREPARATION),
                     "deployment": bind(DEPLOYMENT)},
        "claim_limit": (
            f"The bound session proves {len(ships)} Ship image(s) and the "
            f"listed Link-{link} D3/D4 rows. Acceptance and release remain "
            "unclaimed."
        ),
    }
    write_json(HARDWARE, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=("prepare", "dry-run", "evaluate", "record-first-red"))
    args = parser.parse_args()
    try:
        if args.action in {"prepare", "dry-run"}:
            value = prepare()
        elif args.action == "record-first-red":
            value = record_first_red()
        else:
            value = evaluate()
        if args.action == "dry-run":
            print("c2-v13-closing-device: DRY-RUN PASS")
            print("D1:", ", ".join(row["id"] for row in value["D1"]))
            print(f"D3 quiet keys: {value['D3']['keys']}")
            print("D4:", ", ".join(row["id"] for row in value["D4"]))
        elif args.action == "record-first-red":
            print(f"c2-v13-closing-device: RECORDED status={value['status']}")
        else:
            print(f"c2-v13-closing-device: PASS status={value['status']}")
        return 0
    except (
        SessionError, SCREEN.CheckError, OSError, ValueError, KeyError,
        TypeError, json.JSONDecodeError,
    ) as error:
        print(f"c2-v13-closing-device: FIRST RED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
