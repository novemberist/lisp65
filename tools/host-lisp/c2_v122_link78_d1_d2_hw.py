#!/usr/bin/env python3
"""Prepare and receive Link 78's one-session D1/D2 hardware question."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link75_library_media_successor as MEDIA  # noqa: E402
import c2_require_resolver_gate as L65I  # noqa: E402
import repl_screen_check as SCREEN  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CONFIG = ROOT / "config/c2.2-link78-d1-d2-bundled-hardware-session.json"
LINK = EVIDENCE / (
    "c2.2-product-link78-dirmiss-renderer-structural-receipt.json")
WPLTO = EVIDENCE / (
    "c2.2-v1.2.2-dirmiss-renderer-wplto-receipt.json")
MANIFEST = ROOT / (
    "build/post-release/link78-dirmiss-renderer/"
    "canonical-product-manifest.json")
PROFILE = ROOT / "config/c2-l-full-product-profile.json"
BASE_MEDIA = ROOT / (
    "build/post-promotion/link75-bound-compiler-carrier/"
    "bundled-completion-session/library-media-successor/"
    "require-defstruct-link75-bound.d81")
OUT = ROOT / (
    "build/post-release/link78-dirmiss-renderer/"
    "d1-d2-bundled-session")
MEDIA_OUT = OUT / "library-media"
DEPLOYMENT = OUT / "deployment.json"
OBSERVATIONS = OUT / "observed-rows.json"
PREPARATION = EVIDENCE / (
    "c2.2-link78-d1-d2-bundled-hardware-preparation-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.2-link78-d1-d2-bundled-hardware-receipt.json")
M65 = ROOT / "tools/m65tools/m65"
HARDWARE_SCRIPT = ROOT / "scripts/c2-v122-link78-d1-d2-hw.sh"
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
    "dirmiss-full-name",
    "post-dirmiss-repl",
    "require-defstruct",
    "define-point",
    "construct-point",
)
PRODUCT_SHA = (
    "77f1c734e0818e5765d893627e4f7f514d62ca312a22b8123ead5d1c3ab40c36")
ELF_SHA = (
    "763cb2a9acd5275b618e13ce10a9f9acddbc2980a97d417b6b3f8b6e7e30c7d9")
PROFILE_SHA = (
    "7a6a1015e0f0c1682c5b589db2aadb9300364fb7c7275827175a2e0d4c20b3e1")


class HardwareError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise HardwareError(message)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    if not path.is_absolute():
        path = ROOT / path
    path = path.resolve()
    require(
        path.is_file() and not path.is_symlink(),
        f"evidence absent: {path}",
    )
    return {
        "path": path.relative_to(ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent, delete=False,
    ) as handle:
        temporary = Path(handle.name)
        handle.write(data)
    temporary.replace(path)


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def config_rows() -> list[dict[str, Any]]:
    config = load(CONFIG)
    rows = config["rows"]
    require(
        config["format"]
            == "lisp65-c2.2-link78-d1-d2-bundled-hardware-session-v1"
        and config["status"]
            == "owner-authorized-one-session-hardware-not-run"
        and tuple(row["id"] for row in rows) == ROW_IDS
        and [row["group"] for row in rows] == [
            "D1", "D1", "D2", "D2", "D2"]
        and config["policy"]["d2_is_a_question_not_an_investigation"]
        and config["policy"]["no_per_row_approval"],
        "Link-78 D1/D2 session contract drift",
    )
    return rows


def artifact_roles() -> dict[str, dict[str, Any]]:
    manifest = load(MANIFEST)
    link = load(LINK)
    wplto = load(WPLTO)
    config = load(CONFIG)
    require(
        manifest["status"]
            == "passed-fresh-source-product-and-post-link-completion"
        and manifest["identity"]["resident_prg_sha256"] == PRODUCT_SHA
        and manifest["identity"]["linked_elf_sha256"] == ELF_SHA
        and manifest["identity"]["resolved_profile_sha256"] == PROFILE_SHA
        and link["status"]
            == "passed-Link78-D1-renderer-hardware-not-run"
        and link["product"]["sha256"] == PRODUCT_SHA
        and link["ELF"]["sha256"] == ELF_SHA
        and link["execution_accounting"]["whole_program_product_links"] == 1
        and link["execution_accounting"]["hardware_runs"] == 0
        and wplto["status"]
            == "passed-D1-full-name-renderer-one-product-shaped-WPLTO"
        and wplto["walls"]["e000_headroom_bytes"] == 54
        and wplto["fix"]["resident_delta_bytes"] == 0
        and wplto["fix"]["bank2_delta_bytes"] == 0
        and config["candidate"]["product_sha256"] == PRODUCT_SHA
        and config["candidate"]["elf_sha256"] == ELF_SHA,
        "Link-78 product/WPLTO authority drift",
    )
    rows = manifest["artifacts"]
    result = {row["role"]: row for row in rows}
    require(
        len(rows) == len(result) == 14,
        "Link-78 canonical role inventory drift",
    )
    for role, row in result.items():
        path = ROOT / row["path"]
        require(
            path.is_file()
            and path.stat().st_size == row["bytes"]
            and sha(path) == row["sha256"],
            f"Link-78 artifact drift: {role}",
        )
    return result


def current_build_id(roles: dict[str, dict[str, Any]]) -> int:
    profile = load(PROFILE)
    build_id = int(profile["product_build_id"], 0)
    c2d = (ROOT / roles["c2d-v6-code-plane"]["path"]).read_bytes()
    require(
        len(c2d) == 33840
        and int.from_bytes(c2d[44:48], "little") == build_id,
        "Link-78 profile/C2D product identity drift",
    )
    return build_id


def build_media(
    roles: dict[str, dict[str, Any]],
) -> tuple[Path, dict[str, Any]]:
    build_id = current_build_id(roles)
    require(BASE_MEDIA.is_file(), "predecessor defstruct D81 absent")
    locators = L65I.d81_locators(BASE_MEDIA)
    artifacts, rows = MEDIA.expected_artifacts(build_id, locators)
    old_visible = L65I.D81.visible_files(BASE_MEDIA.read_bytes())
    MEDIA_OUT.mkdir(parents=True, exist_ok=True)
    artifact_paths: list[tuple[Path, str]] = []
    envelope_deltas: dict[str, list[int]] = {}
    for name, data in artifacts.items():
        old = old_visible[name.upper().encode("ascii")]
        delta = [
            index
            for index, (before, after) in enumerate(zip(old, data))
            if before != after
        ]
        require(
            len(old) == len(data)
            and old[64:] == data[64:]
            and set(delta) <= set(range(18, 26))
            and struct.unpack_from("<I", data, 22)[0] == build_id
            and data[32:40] == b"SESS\0\0\0\0",
            f"{name} changed outside its product-bound envelope",
        )
        path = MEDIA_OUT / f"{name}.l65s"
        write_bytes(path, data)
        artifact_paths.append((path, name))
        envelope_deltas[name] = delta

    old_index = old_visible[b"L65INDEX"]
    index = L65I.encode_index(rows)
    require(index == old_index, "Link-78 media rebind changed L65I")
    index_path = MEDIA_OUT / "l65index"
    write_bytes(index_path, index)
    decoded = L65I.decode_index(
        index, artifacts, artifact_build_id=build_id)
    require(
        L65I.resolve(decoded, "defstruct", 7, [], L65I.CAPACITY)
            == [0, 1],
        "Link-78 defstruct dependency order drift",
    )
    mutations = L65I.mutation_gate(
        index, artifacts, artifact_build_id=build_id)

    d81 = MEDIA_OUT / "require-defstruct-link78-bound.d81"
    L65I.build_d81(d81, index_path, artifact_paths)
    visible = L65I.D81.visible_files(d81.read_bytes())
    require(
        L65I.d81_locators(d81) == locators
        and visible[b"L65INDEX"] == index
        and visible[b"PLACE"] == artifacts["place"]
        and visible[b"DEFSTRUCT"] == artifacts["defstruct"],
        "Link-78 D81 visible-file/locator truth drift",
    )
    changed = [
        offset
        for offset, (before, after) in enumerate(
            zip(BASE_MEDIA.read_bytes(), d81.read_bytes()))
        if before != after
    ]
    require(
        BASE_MEDIA.stat().st_size == d81.stat().st_size
        and len(changed)
            == sum(len(offsets) for offsets in envelope_deltas.values()),
        "Link-78 D81 changed outside its two L65S envelopes",
    )
    return d81, {
        "product_build_id": f"0x{build_id:08x}",
        "record_identity": "SESS",
        "source_media": bind(BASE_MEDIA),
        "D81": bind(d81),
        "index": bind(index_path),
        "place": bind(MEDIA_OUT / "place.l65s"),
        "defstruct": bind(MEDIA_OUT / "defstruct.l65s"),
        "envelope_changed_offsets": envelope_deltas,
        "D81_changed_bytes": len(changed),
        "code_and_C2I": "byte-identical-to-predecessor-media",
        "L65I": "byte-identical-to-predecessor-media",
        "index_mutations_rejected": len(mutations),
    }


def span_checks(
    roles: dict[str, dict[str, Any]],
) -> dict[str, bool]:
    return {
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


def deployment_value(
    roles: dict[str, dict[str, Any]],
    d81: Path,
) -> dict[str, Any]:
    spans = span_checks(roles)
    require(all(spans.values()), "Link-78 preload span overlap")
    return {
        "format": "lisp65-c2.2-link78-d1-d2-deployment-v1",
        "status": "ready-one-bundled-session-hardware-not-run",
        "product": {
            **roles["c2-resident-prg"],
            "address": "0x00002001",
        },
        "elf": roles["linked-product-elf"],
        "media": {
            **bind(d81),
            "role": "Link78-bound-L65I-v1-defstruct-media",
        },
        "remote_media": "L78D12.D81",
        "preloads": [
            {
                **roles[role],
                "address": f"0x{address:08x}",
            }
            for role, address in ROLE_ADDRESS.items()
        ],
        "span_checks": spans,
        "rows": config_rows(),
        "authority": {
            "config": bind(CONFIG),
            "link": bind(LINK),
            "WPLTO": bind(WPLTO),
            "manifest": bind(MANIFEST),
            "profile": bind(PROFILE),
            "driver": bind(Path(__file__)),
            "hardware_script": bind(HARDWARE_SCRIPT),
        },
        "execution_accounting": {
            "new_product_links": 0,
            "hardware_runs": 0,
        },
        "claim_limit": (
            "SHA-bound preparation only. D1 and D2 remain unclaimed until "
            "the exact rows complete on one physical device."
        ),
    }


def prepare() -> None:
    require(
        not OUT.exists()
        and not PREPARATION.exists()
        and not RECEIPT.exists(),
        "Link-78 D1/D2 hardware package is one-shot",
    )
    roles = artifact_roles()
    d81, media = build_media(roles)
    deployment = deployment_value(roles, d81)
    atomic_json(DEPLOYMENT, deployment)
    atomic_json(OBSERVATIONS, {
        "format": "lisp65-c2.2-link78-d1-d2-observations-v1",
        "status": "hardware-not-started",
        "rows": [],
    })
    atomic_json(PREPARATION, {
        "format":
            "lisp65-c2.2-link78-d1-d2-hardware-preparation-v1",
        "recorded_on": "2026-07-29",
        "status":
            "passed-Link78-D1-D2-one-session-preparation-hardware-not-run",
        "candidate": {
            "link": 78,
            "product_sha256": PRODUCT_SHA,
            "elf_sha256": ELF_SHA,
        },
        "media_rebind": media,
        "groups": {
            "D1": [
                "complete missing name",
                "live REPL after diagnostic",
            ],
            "D2": [
                "require defstruct",
                "define point",
                "construct point",
            ],
        },
        "D2_stop_rule": (
            "Any unexpected D2 result returns the observation to Class C "
            "without a device-side diagnostic, capture campaign or retry."
        ),
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
        "c2-v122-link78-d1-d2-hw: PREPARE PASS "
        f"product={PRODUCT_SHA} rows={len(ROW_IDS)} "
        f"media={sha(d81)} hardware=not-run"
    )


def rebind_harness_authority() -> None:
    deployment = load(DEPLOYMENT)
    observations = load(OBSERVATIONS)
    require(
        observations["status"]
            == "D2-returned-to-Class-C-without-investigation"
        and observations["stop"]["id"] == "define-point",
        "harness rebind requires the completed D2 stop",
    )
    deployment["authority"]["driver"] = bind(Path(__file__))
    deployment["authority"]["hardware_script"] = bind(HARDWARE_SCRIPT)
    atomic_json(DEPLOYMENT, deployment)
    preparation = load(PREPARATION)
    preparation["deployment"] = bind(DEPLOYMENT)
    preparation["harness_corrections"] = [{
        "kind": "receipt-and-classification-only",
        "product_delta_bytes": 0,
        "product_redeployments": 0,
        "hardware_actions": 0,
        "change": (
            "The D2 stop distinguishes an observed red fail-closed frame "
            "from an ordinary polling timeout and binds core/media/preload "
            "readbacks in the terminal receipt."
        ),
        "driver": bind(Path(__file__)),
        "hardware_script": bind(HARDWARE_SCRIPT),
    }]
    atomic_json(PREPARATION, preparation)
    print(
        "c2-v122-link78-d1-d2-hw: HARNESS REBIND PASS "
        "product-delta=0 redeployments=0 hardware-actions=0"
    )


def verify() -> None:
    roles = artifact_roles()
    rows = config_rows()
    deployment = load(DEPLOYMENT)
    observations = load(OBSERVATIONS)
    require(
        deployment["product"]["sha256"] == PRODUCT_SHA
        and deployment["elf"]["sha256"] == ELF_SHA
        and deployment["rows"] == rows
        and all(deployment["span_checks"].values())
        and [row["id"] for row in observations["rows"]]
            == list(ROW_IDS[:len(observations["rows"])])
        and len(observations["rows"]) <= len(ROW_IDS),
        "Link-78 prepared session drift",
    )
    for row in [
        deployment["product"], deployment["media"],
        *deployment["preloads"],
    ]:
        path = ROOT / row["path"]
        require(
            path.stat().st_size == row["bytes"]
            and sha(path) == row["sha256"],
            f"Link-78 deployment artifact drift: {path}",
        )
    require(
        roles["c2-resident-prg"]["sha256"] == PRODUCT_SHA,
        "Link-78 product role drift",
    )
    print(
        "c2-v122-link78-d1-d2-hw: VERIFY PASS "
        f"observed={len(observations['rows'])}/{len(ROW_IDS)}"
    )


def row_by_id(row_id: str) -> dict[str, Any]:
    return next(row for row in config_rows() if row["id"] == row_id)


def append_observation(value: dict[str, Any]) -> None:
    observations = load(OBSERVATIONS)
    position = len(observations["rows"])
    require(
        position < len(ROW_IDS) and value["id"] == ROW_IDS[position],
        "Link-78 D1/D2 row order violation",
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
    SCREEN.check_fail_closed_frame(image)
    if row_id == "dirmiss-full-name":
        raw = screen.read_text(errors="replace")
        lines = [line.strip() for line in raw.splitlines()]
        expected = (
            row["expected_error_prefix"] + " " + row["expected_symbol"])
        require(
            expected in lines
            and sum(line.startswith("lisp65>") for line in lines) >= 2
            and lines[-1] in ("", "lisp65>"),
            "D1 did not render the complete name at a live prompt",
        )
        outcome = expected
    else:
        SCREEN.check_latest_result(
            screen, row["form"], row["expected_result"])
        outcome = row["expected_result"]
    append_observation({
        "id": row_id,
        "group": row["group"],
        "form": row["form"],
        "outcome": outcome,
        "screen": bind(screen),
        "image": bind(image),
        "status": "passed-exact-screen-result",
    })
    print(f"c2-v122-link78-d1-d2-hw: ROW PASS {row_id} -> {outcome}")


def record_stop(
    row_id: str,
    screen: Path,
    image: Path,
    detail: str,
) -> None:
    row = row_by_id(row_id)
    observations = load(OBSERVATIONS)
    require(
        row_id == ROW_IDS[len(observations["rows"])],
        "Link-78 stop row order drift",
    )
    stop = {
        "id": row_id,
        "group": row["group"],
        "form": row["form"],
        "detail": detail,
        "screen": bind(screen),
        "image": bind(image),
        "diagnostic_actions_after_stop": 0,
        "automatic_retries_after_stop": 0,
    }
    if row["group"] == "D2":
        status = "D2-returned-to-Class-C-without-investigation"
        stop["classification"] = (
            "D2 answered red or unexpectedly; no mechanism is inferred")
    else:
        status = "D1-hardware-first-red-D2-not-run"
        stop["classification"] = (
            "D1 product smoke did not meet its exact screen contract")
    observations["status"] = status
    observations["stop"] = stop
    atomic_json(OBSERVATIONS, observations)
    deployment = load(DEPLOYMENT)
    media = ROOT / deployment["media"]["path"]
    uploaded = OUT / "uploaded-media-readback.d81"
    core = OUT / "device-core-id.bin"
    require(
        uploaded.is_file()
        and uploaded.read_bytes() == media.read_bytes()
        and core.is_file()
        and core.stat().st_size == 4,
        "Link-78 stopped session media/core evidence incomplete",
    )
    readbacks = []
    for preload in deployment["preloads"]:
        source = ROOT / preload["path"]
        target = OUT / f"readback-{source.name}"
        require(
            target.is_file()
            and target.read_bytes() == source.read_bytes(),
            f"Link-78 stopped-session preload drift: {preload['role']}",
        )
        readbacks.append({
            "role": preload["role"],
            "source": bind(source),
            "readback": bind(target),
            "byteidentical": True,
        })
    atomic_json(RECEIPT, {
        "format": "lisp65-c2.2-link78-d1-d2-hardware-receipt-v1",
        "recorded_on": "2026-07-29",
        "status": status,
        "candidate": {
            "product": deployment["product"],
            "elf": deployment["elf"],
            "media": deployment["media"],
        },
        "device": {
            "core_id": {**bind(core), "hex": core.read_bytes().hex()},
            "physical_devices": 1,
            "physical_sessions": 1,
        },
        "passed_rows": observations["rows"],
        "stop": stop,
        "remaining_rows_not_run": list(
            ROW_IDS[len(observations["rows"]) + 1:]),
        "upload_readbacks": readbacks,
        "authority": {
            "config": bind(CONFIG),
            "preparation": bind(PREPARATION),
            "link": bind(LINK),
            "deployment": bind(DEPLOYMENT),
            "observations": bind(OBSERVATIONS),
            "uploaded_media": bind(uploaded),
        },
        "execution_accounting": {
            "physical_device_sessions": 1,
            "product_links": 0,
            "diagnostic_deployments": 0,
            "diagnostic_actions_after_stop": 0,
        },
        "claim_limit": (
            "Only the listed passed rows and the exact stopped screen are "
            "claimed. No cause, IRQ-source attribution or D2 fix is claimed."
        ),
    })
    print(
        "c2-v122-link78-d1-d2-hw: SESSION STOP "
        f"id={row_id} status={status}"
    )


def finalize() -> None:
    verify()
    deployment = load(DEPLOYMENT)
    observations = load(OBSERVATIONS)
    require(
        [row["id"] for row in observations["rows"]] == list(ROW_IDS),
        "Link-78 D1/D2 row closure incomplete",
    )
    media = ROOT / deployment["media"]["path"]
    uploaded = OUT / "uploaded-media-readback.d81"
    core = OUT / "device-core-id.bin"
    require(
        uploaded.is_file()
        and uploaded.read_bytes() == media.read_bytes()
        and core.is_file()
        and core.stat().st_size == 4,
        "Link-78 media/core evidence incomplete",
    )
    readbacks = []
    for row in deployment["preloads"]:
        source = ROOT / row["path"]
        target = OUT / f"readback-{source.name}"
        require(
            target.is_file()
            and target.stat().st_size == source.stat().st_size
            and sha(target) == sha(source) == row["sha256"],
            f"Link-78 preload readback drift: {row['role']}",
        )
        readbacks.append({
            "role": row["role"],
            "source": bind(source),
            "readback": bind(target),
            "byteidentical": True,
        })
    atomic_json(RECEIPT, {
        "format": "lisp65-c2.2-link78-d1-d2-hardware-receipt-v1",
        "recorded_on": "2026-07-29",
        "status": "passed-Link78-D1-and-D2-one-session",
        "candidate": {
            "product": deployment["product"],
            "elf": deployment["elf"],
            "media": deployment["media"],
        },
        "device": {
            "core_id": {**bind(core), "hex": core.read_bytes().hex()},
            "physical_devices": 1,
            "physical_sessions": 1,
        },
        "rows": observations["rows"],
        "groups": {
            "D1": (
                "passed-complete-DIRMISS-name-and-live-REPL"),
            "D2": (
                "passed-require-defstruct-definition-and-constructor"),
        },
        "D2_disposition": {
            "library_era": "reopened",
            "R_1": "closed-after-Link76-interrupt-ownership-hardening",
            "attribution_boundary": (
                "The prior red frame no longer reproduces after the "
                "Ethernet/Auto-IEC/Audio-DMA ownership policy. This binds "
                "the source class, not one individual firing source."
            ),
        },
        "upload_readbacks": readbacks,
        "evidence": {
            "config": bind(CONFIG),
            "preparation": bind(PREPARATION),
            "link": bind(LINK),
            "WPLTO": bind(WPLTO),
            "deployment": bind(DEPLOYMENT),
            "observations": bind(OBSERVATIONS),
            "uploaded_media": bind(uploaded),
            "driver": bind(Path(__file__)),
        },
        "execution_accounting": {
            "physical_device_sessions": 1,
            "product_links": 0,
            "diagnostic_deployments": 0,
        },
        "claim_limit": (
            "Only the five named Link-78 D1/D2 rows and byte-identical "
            "deployment uploads are claimed; no wider library claim is made."
        ),
    })
    observations["status"] = "passed-and-receipted"
    observations["receipt"] = bind(RECEIPT)
    atomic_json(OBSERVATIONS, observations)
    print(
        "c2-v122-link78-d1-d2-hw: FINAL PASS "
        f"rows={len(ROW_IDS)}/{len(ROW_IDS)} D1=green D2=green"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=(
            "prepare", "rebind-harness", "verify", "record-row",
            "record-stop", "finalize"),
    )
    parser.add_argument("--id")
    parser.add_argument("--screen", type=Path)
    parser.add_argument("--image", type=Path)
    parser.add_argument("--detail", default="unexpected screen result")
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
    elif args.action == "rebind-harness":
        rebind_harness_authority()
    elif args.action == "verify":
        verify()
    elif args.action == "finalize":
        finalize()
    else:
        require(
            args.id is not None
            and args.screen is not None
            and args.image is not None,
            f"{args.action} requires --id, --screen and --image",
        )
        if args.action == "record-row":
            record_row(args.id, args.screen, args.image)
        else:
            record_stop(
                args.id, args.screen, args.image, args.detail)


if __name__ == "__main__":
    try:
        main()
    except (
        HardwareError,
        SCREEN.CheckError,
        MEDIA.SuccessorError,
        MEDIA.FOUNDATION.FoundationError,
        L65I.GateError,
        L65I.S.ProbeError,
        KeyError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-v122-link78-d1-d2-hw: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        raise SystemExit(1)
