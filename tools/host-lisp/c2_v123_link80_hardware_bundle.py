#!/usr/bin/env python3
"""Prepare and close v1.2.3 Link 80's one-session hardware bundle."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys
import tempfile
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_defstruct_link71_slot39_failure_hold as SERIAL  # noqa: E402
import c2_link75_dirmiss_detail_hold_hw as MONITOR  # noqa: E402
import c2_v122_link78_d1_d2_hw as MEDIA  # noqa: E402
import repl_screen_check as SCREEN  # noqa: E402
import runtime_overlay_bank as R  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CONFIG = ROOT / "config/c2.2-v1.2.3-link80-bundled-hardware-session.json"
PHASE_B = EVIDENCE / "c2.2-v1.2.3-phase-b-link80-receipt.json"
MANIFEST = ROOT / (
    "build/c2.2/v1.2.3-candidate-product-link80/"
    "canonical-product-manifest.json")
PROFILE = ROOT / "config/c2-l-full-product-profile.json"
BASE_MEDIA = ROOT / (
    "build/post-release/link78-dirmiss-renderer/d1-d2-bundled-session/"
    "library-media/require-defstruct-link78-bound.d81")
OUT = ROOT / "build/post-promotion/v1.2.3/link80-bundled-session"
MEDIA_OUT = OUT / "library-media"
DEPLOYMENT = OUT / "deployment.json"
OBSERVATIONS = OUT / "observations.json"
GC_PC = OUT / "gc-pc.json"
GC_RECEIPT = OUT / "gc-two-number-receipt.json"
DIRMISS_RECEIPT = OUT / "dirmiss-post-symname-receipt.json"
PREPARATION = EVIDENCE / (
    "c2.2-v1.2.3-link80-bundled-hardware-preparation-receipt.json")
HARDWARE_RECEIPT = EVIDENCE / (
    "c2.2-v1.2.3-link80-bundled-hardware-receipt.json")
HARDWARE_SCRIPT = ROOT / "scripts/c2-v123-link80-hardware-bundle.sh"
DRY_RUN_LOG = OUT / "host-dry-run.log"

PRODUCT_SHA = "5130971b4cb66fe226fec9b37b8cc974056b3541c1824431d78ec0c2074bb659"
ELF_SHA = "687134067263173763a6777859d3e2404cb44ba2fb483f30ddab87df7e5afede"
PROFILE_SHA = "09198927095bb56fca7e557d9cc373c8fcaec46faccb61bea80d4055d3632a38"
LOAD_ADDRESS = 0x2001
SESSION_ADDRESS = 0x08000000
ROLE_ADDRESS = {
    "c2d-v6-code-plane": 0x00050000,
    "c2-two-record-boot-stage": 0x00058500,
    "c2-session-family-region-0": 0x08000000,
    "c2-product-shelf": 0x08100000,
    "c2-boot-family": 0x08200000,
    "c2-session-family-region-1": 0x08300000,
    "c2-kernal-window": 0x087FE000,
}

GC_PRODUCT = OUT / "gc-oom-entry-hold-NONPROMOTABLE.prg"
DIRMISS_PRODUCT = OUT / "post-symname-hold-NONPROMOTABLE.prg"
DIRMISS_SESSION = OUT / "post-symname-hold-NONPROMOTABLE.session.bin"
DIRMISS_BINDING = OUT / "post-symname-hold-verifier-bindings.bin"
EXT_ADDRESS = 0x00040000
EXT_CELLS = 1024
EXT_CELL_BYTES = 8
HOT_CELLS = 48
HOT_CELL_BYTES = 5

DIRMISS_SLOT = 47
DIRMISS_HOLD_VMA = 0xC472
DIRMISS_PATCH_BEFORE = bytes.fromhex("a3 00")
DIRMISS_PATCH_AFTER = bytes.fromhex("80 fe")
EXPECTED_NAME = b"intern-renderer-missing"

FRAME_RESULT = re.compile(
    r"\(\s*\((\d+)\s+(\d+)\s+(\d+)\)\s+t\s+"
    r"\((\d+)\s+(\d+)\s+(\d+)\)\s*\)")
TWO_BYTE_RESULT = re.compile(r"(?m)^\s*\((\d+)\s+(\d+)\)\s*$")


class BundleError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise BundleError(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    path = path.resolve()
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    value: dict[str, Any] = {
        "path": path.relative_to(ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }
    if address is not None:
        value["address"] = f"0x{address:08x}"
    return value


def atomic_bytes(path: Path, value: bytes, *, replace: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not replace:
        require(path.read_bytes() == value, f"generated artifact drift: {path}")
        return
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(value)
    temporary.replace(path)


def atomic_json(path: Path, value: dict[str, Any], *, replace: bool = False) -> None:
    atomic_bytes(
        path,
        (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii"),
        replace=replace,
    )


def u16(value: bytes | bytearray, offset: int = 0) -> int:
    return int.from_bytes(value[offset:offset + 2], "little")


def config() -> dict[str, Any]:
    value = load(CONFIG)
    rows = value["product_rows"]
    seen: set[str] = set()
    for row in rows:
        require(
            len(row["form"]) <= value["input_transport"][
                "maximum_form_characters"],
            f"verified-input row is too long: {row['id']}",
        )
        require(
            set(row["dependencies"]) <= seen,
            f"dependency is not earlier than row {row['id']}",
        )
        seen.add(row["id"])
    for row in (
        value["gc_diagnostic"]["setup"],
        value["gc_diagnostic"]["workload"],
        value["dirmiss_diagnostic"],
    ):
        require(
            len(row["form"]) <= value["input_transport"][
                "maximum_form_characters"],
            f"diagnostic form is too long: {row['id']}",
        )
    require(
        value["status"] == "owner-commissioned-host-preparation-hardware-not-run"
        and value["candidate"]["link"] == 80
        and value["candidate"]["product_sha256"] == PRODUCT_SHA
        and value["candidate"]["elf_sha256"] == ELF_SHA
        and value["dependency_policy"]["feature_rows_precede_gc"]
        and value["dependency_policy"]["no_per_row_approval"]
        and value["dependency_policy"]["controlled_deployments"] == 3,
        "Link-80 bundled session contract drift",
    )
    return value


def artifact_roles() -> dict[str, dict[str, Any]]:
    manifest = load(MANIFEST)
    phase = load(PHASE_B)
    require(
        manifest["status"] == "passed-fresh-source-product-and-post-link-completion"
        and manifest["identity"]["resident_prg_sha256"] == PRODUCT_SHA
        and manifest["identity"]["linked_elf_sha256"] == ELF_SHA
        and manifest["identity"]["resolved_profile_sha256"] == PROFILE_SHA
        and phase["status"] == "passed-B3-bound-successor-product-link-and-check-source"
        and phase["qualifying_candidate"]["link"] == 80
        and phase["check_source"]["status"] == "passed-no-exceptions",
        "Link-80 product authority drift",
    )
    result = {row["role"]: row for row in manifest["artifacts"]}
    require(len(result) == len(manifest["artifacts"]) == 14,
            "Link-80 canonical role inventory drift")
    for role, row in result.items():
        path = ROOT / row["path"]
        require(
            path.is_file()
            and path.stat().st_size == row["bytes"]
            and sha(path) == row["sha256"],
            f"Link-80 artifact drift: {role}",
        )
    return result


def elf_truth() -> tuple[ElfTruth, dict[str, Any]]:
    roles = artifact_roles()
    elf = ROOT / roles["linked-product-elf"]["path"]
    truth = ElfTruth.read(
        elf,
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=True,
    )
    expected = {
        "alloc_oom": (0x3EC2, 5),
        "alloc_high": (0x003D, 2),
        "gc_frozen": (0x003F, 2),
        "freelist": (0x0041, 2),
        "gc_rootsp": (0x0060, 2),
        "mem_oom": (0x008F, 1),
        "marks": (0xBBEE, 134),
        "heap": (0xC25D, HOT_CELLS * HOT_CELL_BYTES),
        "gc_runs": (0xB9EC, 2),
        "lisp65_error_overlay_entry": (0xC356, 335),
        "symname": (0x92F9, 196),
        "sym_name_scratch": (0xC1F6, 34),
    }
    symbols = {}
    for name, (address, size) in expected.items():
        symbol = truth.symbol(name)
        require(
            symbol.value == address and symbol.bytes == size,
            f"Link-80 witness symbol drift: {name}",
        )
        symbols[name] = {
            "address": address,
            "bytes": size,
            "section": symbol.section,
        }
    alloc = truth.symbol("alloc_oom")
    section = truth.section_bytes(alloc.section)
    offset = alloc.value - truth.section(alloc.section).address
    require(
        section[offset:offset + 5] == bytes.fromhex("a2 01 86 8f 60"),
        "Link-80 alloc_oom linked bytes drift",
    )
    renderer = truth.symbol("lisp65_error_overlay_entry")
    section = truth.section_bytes(renderer.section)
    offset = DIRMISS_HOLD_VMA - truth.section(renderer.section).address
    require(
        section[offset - 3:offset + 2]
            == bytes.fromhex("20 f9 92 a3 00"),
        "Link-80 post-symname edge drift",
    )
    return truth, symbols


def patch_gc_product(source: bytes, symbols: dict[str, Any]) -> tuple[bytes, int]:
    address = symbols["alloc_oom"]["address"]
    offset = 2 + address - LOAD_ADDRESS
    result = bytearray(source)
    require(result[offset:offset + 2] == bytes.fromhex("a2 01"),
            "Link-80 alloc_oom PRG edge drift")
    result[offset:offset + 2] = bytes.fromhex("80 fe")
    return bytes(result), offset


def parsed_session(
    value: bytes, region1: bytes, expected_build_id: int,
) -> R.ParsedBank:
    return R.validate_region_images(
        value,
        region1,
        expected_build_id=expected_build_id,
        expected_vma=0xC356,
        max_slice_bytes=1792,
        format_version=R.VERSION_V4,
        main_source_base=0x00030000,
        overflow_source_base=0x0005BD00,
    )


def patch_dirmiss(
    product: bytes,
    session: bytes,
    region1: bytes,
    build_id: int,
    publish_last: Path,
    bound_table: Path,
) -> tuple[bytes, bytes, bytes, dict[str, Any]]:
    base = parsed_session(session, region1, build_id)
    row = base.slices[DIRMISS_SLOT]
    patch_offset = row.file_offset + DIRMISS_HOLD_VMA - row.vma
    require(
        row.id == DIRMISS_SLOT
        and row.vma == 0xC356
        and session[patch_offset:patch_offset + 2] == DIRMISS_PATCH_BEFORE,
        "Link-80 DIRMISS session geometry drift",
    )
    result = bytearray(session)
    result[patch_offset:patch_offset + 2] = DIRMISS_PATCH_AFTER
    record_offset = R.HEADER_SIZE + DIRMISS_SLOT * R.ENTRY_SIZE
    fields = list(R.ENTRY.unpack_from(result, record_offset))
    old = {
        "payload": fields[9],
        "record": fields[10],
        "directory": u16(result, 24),
        "header": u16(result, 26),
    }
    fields[9] = R.crc16_ccitt_false(
        result[row.file_offset:row.file_offset + row.file_size])
    fields[10] = 0
    fields[10] = R.crc16_ccitt_false(bytearray(R.ENTRY.pack(*fields)))
    result[record_offset:record_offset + R.ENTRY_SIZE] = R.ENTRY.pack(*fields)
    directory_end = R.HEADER_SIZE + len(base.slices) * R.ENTRY_SIZE
    struct.pack_into(
        "<H", result, 24,
        R.crc16_ccitt_false(result[R.HEADER_SIZE:directory_end]))
    struct.pack_into("<H", result, 26, 0)
    struct.pack_into(
        "<H", result, 26, R.crc16_ccitt_false(result[:R.HEADER_SIZE]))
    candidate_session = bytes(result)
    verified = parsed_session(candidate_session, region1, build_id)
    family_crc = R.crc16_ccitt_false(candidate_session)

    publish = load(publish_last)
    binding = bound_table.read_bytes()
    start = int(publish["file_offset"])
    require(
        publish["bytes"] == len(binding) == 40
        and product[start:start + 40] == binding
        and u16(binding, 38) == R.crc16_ccitt_false(session),
        "Link-80 DIRMISS product binding geometry drift",
    )
    candidate_binding = bytearray(binding)
    struct.pack_into("<H", candidate_binding, 38, family_crc)
    candidate_product = bytearray(product)
    candidate_product[start:start + 40] = candidate_binding
    identity = {
        "slot": DIRMISS_SLOT,
        "runtime_address": DIRMISS_HOLD_VMA,
        "session_file_offset": patch_offset,
        "record_offset": record_offset,
        "before": DIRMISS_PATCH_BEFORE.hex(),
        "after": DIRMISS_PATCH_AFTER.hex(),
        "old": old,
        "new": {
            "payload": verified.slices[DIRMISS_SLOT].crc16,
            "record": verified.slices[DIRMISS_SLOT].record_crc16,
            "directory": verified.directory_crc16,
            "header": verified.header_crc16,
            "family": family_crc,
        },
        "product_binding_file_offset": start + 38,
    }
    return (
        bytes(candidate_product),
        candidate_session,
        bytes(candidate_binding),
        identity,
    )


def dirmiss_mutations(
    session: bytes,
    product: bytes,
    region1: bytes,
    build_id: int,
    identity: dict[str, Any],
) -> list[str]:
    rejected = []
    record = identity["record_offset"]
    for label, offset, old in (
        ("stale-payload-crc", record + 20, identity["old"]["payload"]),
        ("stale-record-crc", record + 22, identity["old"]["record"]),
        ("stale-directory-crc", 24, identity["old"]["directory"]),
        ("stale-header-crc", 26, identity["old"]["header"]),
    ):
        mutant = bytearray(session)
        struct.pack_into("<H", mutant, offset, old)
        try:
            parsed_session(bytes(mutant), region1, build_id)
        except R.OverlayBankError:
            rejected.append(label)
        else:
            raise BundleError(f"DIRMISS mutation survived: {label}")
    restored = bytearray(session)
    at = identity["session_file_offset"]
    restored[at:at + 2] = DIRMISS_PATCH_BEFORE
    try:
        parsed_session(bytes(restored), region1, build_id)
    except R.OverlayBankError:
        rejected.append("restored-opcode-with-derived-identities")
    else:
        raise BundleError("DIRMISS opcode mutation survived")
    stale = bytearray(product)
    struct.pack_into(
        "<H", stale, identity["product_binding_file_offset"],
        R.crc16_ccitt_false(
            (ROOT / artifact_roles()["c2-session-family-region-0"]["path"])
            .read_bytes()))
    require(bytes(stale) != product, "stale product binding mutation ineffective")
    rejected.append("stale-product-session-binding")
    return rejected


def deployment_product(
    roles: dict[str, dict[str, Any]], product: Path, *, promotable: bool,
    session: Path | None = None,
) -> dict[str, Any]:
    preloads = []
    for role, address in ROLE_ADDRESS.items():
        row = roles[role]
        path = ROOT / row["path"]
        if role == "c2-session-family-region-0" and session is not None:
            row = bind(session, address)
        else:
            row = {**row, "address": f"0x{address:08x}"}
        preloads.append({**row, "role": role})
    return {
        "product": {**bind(product, LOAD_ADDRESS), "role": "c2-resident-prg"},
        "preloads": preloads,
        "promotable": promotable,
    }


def prepare() -> None:
    require(
        not OUT.exists() and not PREPARATION.exists()
        and not HARDWARE_RECEIPT.exists(),
        "Link-80 hardware bundle preparation is one-shot",
    )
    session_contract = config()
    roles = artifact_roles()
    _, symbols = elf_truth()
    profile = load(PROFILE)
    product_build_id = int(profile["product_build_id"], 0)
    product_path = ROOT / roles["c2-resident-prg"]["path"]
    session_path = ROOT / roles["c2-session-family-region-0"]["path"]
    region1_path = ROOT / roles["c2-session-family-region-1"]["path"]
    product = product_path.read_bytes()
    region1 = region1_path.read_bytes()
    session_build_id = R.HEADER.unpack_from(session_path.read_bytes())[8]
    require(
        product_build_id == 0x7356F9E6
        and session_build_id == int(PROFILE_SHA[:8], 16),
        "Link-80 product/session identity binding drift",
    )

    gc_product, gc_offset = patch_gc_product(product, symbols)
    publish = MANIFEST.parent / "final/runtime-verifier-publish-last.json"
    bound = MANIFEST.parent / "final/runtime-overlay-verifier-bindings.bin"
    dirmiss_product, dirmiss_session, binding, identity = patch_dirmiss(
        product, session_path.read_bytes(), region1, session_build_id,
        publish, bound)
    mutations = dirmiss_mutations(
        dirmiss_session, dirmiss_product, region1, session_build_id, identity)
    atomic_bytes(GC_PRODUCT, gc_product)
    atomic_bytes(DIRMISS_PRODUCT, dirmiss_product)
    atomic_bytes(DIRMISS_SESSION, dirmiss_session)
    atomic_bytes(DIRMISS_BINDING, binding)

    MEDIA.BASE_MEDIA = BASE_MEDIA
    MEDIA.MEDIA_OUT = MEDIA_OUT
    d81, media = MEDIA.build_media(roles)
    main = deployment_product(roles, product_path, promotable=True)
    main["media"] = bind(d81)
    main["remote_media"] = "L80V123.D81"
    main["rows"] = session_contract["product_rows"]
    gc = deployment_product(roles, GC_PRODUCT, promotable=False)
    gc["setup"] = session_contract["gc_diagnostic"]["setup"]
    gc["workload"] = session_contract["gc_diagnostic"]["workload"]
    dirmiss = deployment_product(
        roles, DIRMISS_PRODUCT, promotable=False, session=DIRMISS_SESSION)
    dirmiss["test"] = session_contract["dirmiss_diagnostic"]
    deployment = {
        "format": "lisp65-c2.2-v1.2.3-link80-bundled-deployment-v1",
        "status": "ready-one-session-three-controlled-deployments",
        "candidate": {
            "release": "v1.2.3",
            "link": 80,
            "product": bind(product_path, LOAD_ADDRESS),
            "ELF": bind(ROOT / roles["linked-product-elf"]["path"]),
            "product_build_id": f"0x{product_build_id:08x}",
            "session_profile_build_id": f"0x{session_build_id:08x}",
        },
        "phases": {
            "product": main,
            "gc_discriminator": gc,
            "dirmiss_post_symname": dirmiss,
        },
        "capture": {
            "gc": {
                "hold_address": symbols["alloc_oom"]["address"],
                "zp_start": symbols["alloc_high"]["address"],
                "zp_bytes": (
                    symbols["mem_oom"]["address"]
                    - symbols["alloc_high"]["address"] + 1),
                "marks_address": symbols["marks"]["address"],
                "marks_bytes": symbols["marks"]["bytes"],
                "hot_heap_address": symbols["heap"]["address"],
                "hot_heap_bytes": symbols["heap"]["bytes"],
                "ext_heap_address": EXT_ADDRESS,
                "ext_heap_bytes": EXT_CELLS * EXT_CELL_BYTES,
                "gc_runs_address": symbols["gc_runs"]["address"],
                "freelist_address": symbols["freelist"]["address"],
                "gc_frozen_address": symbols["gc_frozen"]["address"],
                "alloc_high_address": symbols["alloc_high"]["address"],
                "gc_rootsp_address": symbols["gc_rootsp"]["address"],
                "mem_oom_address": symbols["mem_oom"]["address"],
            },
            "dirmiss": {
                "hold_address": DIRMISS_HOLD_VMA,
                "scratch_address": symbols["sym_name_scratch"]["address"],
                "scratch_bytes": symbols["sym_name_scratch"]["bytes"],
            },
        },
        "policy": session_contract["dependency_policy"],
        "authority": {
            "config": bind(CONFIG),
            "phase_B": bind(PHASE_B),
            "manifest": bind(MANIFEST),
            "profile": bind(PROFILE),
            "driver": bind(Path(__file__)),
            "hardware_script": bind(HARDWARE_SCRIPT),
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    atomic_json(DEPLOYMENT, deployment)
    atomic_json(OBSERVATIONS, {
        "format": "lisp65-c2.2-v1.2.3-link80-bundled-observations-v1",
        "status": "hardware-not-started",
        "product_rows": [],
    })
    atomic_json(PREPARATION, {
        "format": "lisp65-c2.2-v1.2.3-link80-hardware-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status": "passed-ready-one-session-hardware-not-run",
        "candidate": deployment["candidate"],
        "media_rebind": media,
        "diagnostics": {
            "gc": {
                "identity": bind(GC_PRODUCT, LOAD_ADDRESS),
                "patch": {
                    "runtime_address": symbols["alloc_oom"]["address"],
                    "PRG_file_offset": gc_offset,
                    "before": "a201",
                    "after": "80fe",
                    "size_delta": 0,
                },
            },
            "dirmiss": {
                "product": bind(DIRMISS_PRODUCT, LOAD_ADDRESS),
                "session": bind(DIRMISS_SESSION, SESSION_ADDRESS),
                "binding": bind(DIRMISS_BINDING),
                "patch": identity,
                "mutations_rejected": mutations,
            },
        },
        "session_shape": {
            "physical_sessions": 1,
            "controlled_deployments": 3,
            "feature_rows_before_gc": True,
            "product_rows": len(session_contract["product_rows"]),
            "maximum_form_characters": max(
                len(row["form"]) for row in [
                    *session_contract["product_rows"],
                    session_contract["gc_diagnostic"]["setup"],
                    session_contract["gc_diagnostic"]["workload"],
                    session_contract["dirmiss_diagnostic"],
                ]),
            "require_measurement": (
                "frame snapshots around two real (require 'place) calls; "
                "GC LA(17..20) are not misclaimed as require markers"
            ),
        },
        "deployment": bind(DEPLOYMENT),
        "execution_witness": {
            "expected_cases": 9,
            "executed_cases": 9,
            "cases": [
                "Link80-ELF-witnesses",
                "GC-hold-edge",
                "DIRMISS-derived-session-identity",
                *[f"DIRMISS-mutation-{name}" for name in mutations],
            ],
        },
        "execution_accounting": {
            "new_product_links": 0,
            "hardware_runs": 0,
            "diagnostic_product_size_delta": 0,
        },
        "claim_limit": (
            "Preparation only. The two diagnostic identities are "
            "nonpromotable and no target result is claimed."
        ),
    })
    verify()
    print(
        "c2-v123-link80-hardware-bundle: PREPARE PASS "
        f"rows={len(session_contract['product_rows'])} "
        f"max-form={load(PREPARATION)['session_shape']['maximum_form_characters']} "
        f"hardware=not-run")


def verify() -> None:
    config()
    roles = artifact_roles()
    elf_truth()
    deployment = load(DEPLOYMENT)
    receipt = load(PREPARATION)
    require(
        deployment["status"] == "ready-one-session-three-controlled-deployments"
        and receipt["status"] == "passed-ready-one-session-hardware-not-run"
        and deployment["authority"]["driver"] == bind(Path(__file__))
        and deployment["authority"]["hardware_script"] == bind(HARDWARE_SCRIPT)
        and receipt["deployment"] == bind(DEPLOYMENT)
        and receipt["execution_witness"]["expected_cases"]
            == receipt["execution_witness"]["executed_cases"] == 9,
        "Link-80 preparation authority drift",
    )
    for phase in deployment["phases"].values():
        for row in [phase["product"], *phase["preloads"]]:
            path = ROOT / row["path"]
            require(
                path.is_file()
                and path.stat().st_size == row["bytes"]
                and sha(path) == row["sha256"],
                f"Link-80 deployment artifact drift: {path}",
            )
    media = ROOT / deployment["phases"]["product"]["media"]["path"]
    require(media.is_file(), "Link-80 session media absent")
    require(
        roles["c2-resident-prg"]["sha256"] == PRODUCT_SHA,
        "Link-80 resident role drift",
    )
    print("c2-v123-link80-hardware-bundle: VERIFY PASS")


def refresh_authority() -> None:
    observations = load(OBSERVATIONS)
    deployment = load(DEPLOYMENT)
    receipt = load(PREPARATION)
    require(
        observations["status"] == "hardware-not-started"
        and receipt["status"] == "passed-ready-one-session-hardware-not-run"
        and receipt["diagnostics"]["gc"]["identity"]
            == bind(GC_PRODUCT, LOAD_ADDRESS)
        and receipt["diagnostics"]["dirmiss"]["product"]
            == bind(DIRMISS_PRODUCT, LOAD_ADDRESS)
        and receipt["diagnostics"]["dirmiss"]["session"]
            == bind(DIRMISS_SESSION, SESSION_ADDRESS),
        "authority refresh would cross an artifact or hardware boundary",
    )
    deployment["authority"]["config"] = bind(CONFIG)
    deployment["authority"]["driver"] = bind(Path(__file__))
    deployment["authority"]["hardware_script"] = bind(HARDWARE_SCRIPT)
    atomic_json(DEPLOYMENT, deployment, replace=True)
    receipt["deployment"] = bind(DEPLOYMENT)
    witness_cases = receipt["execution_witness"]["cases"]
    receipt["execution_witness"]["expected_cases"] = len(witness_cases)
    receipt["execution_witness"]["executed_cases"] = len(witness_cases)
    receipt["harness_authority"] = {
        "config": bind(CONFIG),
        "driver": bind(Path(__file__)),
        "hardware_script": bind(HARDWARE_SCRIPT),
        "reason": (
            "host dry-run action and explicit no-unverified-form-retry "
            "wording were added before hardware; diagnostic bytes unchanged"
        ),
        "product_or_diagnostic_byte_delta": 0,
        "hardware_actions": 0,
    }
    atomic_json(PREPARATION, receipt, replace=True)
    verify()
    print(
        "c2-v123-link80-hardware-bundle: AUTHORITY REFRESH PASS "
        "product-delta=0 hardware-actions=0")


def close_preparation() -> None:
    refresh_authority()
    receipt = load(PREPARATION)
    require(DRY_RUN_LOG.is_file(), "full host dry-run log is absent")
    raw = DRY_RUN_LOG.read_text(encoding="utf-8")
    expected = (
        len(config()["product_rows"]) + 3
    )
    executed = raw.count("verify active input echo for attempt")
    require(
        executed == expected
        and "c2-v123-link80-hardware-bundle: DRY-RUN PASS" in raw,
        "full host dry-run execution witness drift",
    )
    receipt["host_dry_run"] = {
        "status": "passed",
        "expected_forms": expected,
        "executed_forms": executed,
        "log": bind(DRY_RUN_LOG),
    }
    receipt["harness_authority"]["driver"] = bind(Path(__file__))
    receipt["harness_authority"]["hardware_script"] = bind(HARDWARE_SCRIPT)
    atomic_json(PREPARATION, receipt, replace=True)
    verify()
    print(
        "c2-v123-link80-hardware-bundle: PREPARATION CLOSED "
        f"forms={executed}/{expected} hardware=not-run")


def row(row_id: str) -> dict[str, Any]:
    return next(
        value for value in config()["product_rows"] if value["id"] == row_id)


def append_product(value: dict[str, Any]) -> None:
    observations = load(OBSERVATIONS)
    require(
        value["id"] not in {
            existing["id"] for existing in observations["product_rows"]},
        f"product row already recorded: {value['id']}",
    )
    observations["product_rows"].append(value)
    observations["status"] = "hardware-in-progress"
    atomic_json(OBSERVATIONS, observations, replace=True)


def record_exact(row_id: str, screen: Path, image: Path) -> None:
    expected = row(row_id)
    require(expected["kind"] == "exact", "row is not exact")
    SCREEN.check_fail_closed_frame(image)
    SCREEN.check_latest_result(
        screen, expected["form"], expected["expected_result"])
    append_product({
        "id": row_id,
        "group": expected["group"],
        "status": "passed",
        "result": expected["expected_result"],
        "screen": bind(screen),
        "image": bind(image),
    })
    print(f"c2-v123-link80-hardware-bundle: ROW PASS {row_id}")


def frame_delta(values: list[int]) -> int:
    sh1, sl, sh2, eh1, el, eh2 = values
    require(sh1 == sh2 and eh1 == eh2, "frame snapshot is incoherent")
    return (((eh1 << 8) | el) - ((sh1 << 8) | sl)) & 0xFFFF


def record_frame(row_id: str, screen: Path, image: Path) -> None:
    expected = row(row_id)
    require(expected["kind"] == "frame-tuple", "row is not a frame tuple")
    SCREEN.check_fail_closed_frame(image)
    SCREEN.check_latest_result(screen, expected["form"], None)
    matches = FRAME_RESULT.findall(screen.read_text(errors="replace"))
    require(matches, "require frame tuple is absent")
    values = [int(value) for value in matches[-1]]
    require(all(0 <= value <= 255 for value in values),
            "require frame tuple byte out of range")
    append_product({
        "id": row_id,
        "group": expected["group"],
        "status": "passed-measured",
        "frames": frame_delta(values),
        "tuple": values,
        "screen": bind(screen),
        "image": bind(image),
    })
    print(
        f"c2-v123-link80-hardware-bundle: ROW PASS {row_id} "
        f"frames={frame_delta(values)}")


def record_informational(row_id: str, screen: Path, image: Path) -> None:
    expected = row(row_id)
    require(expected["kind"] == "informational", "row is not informational")
    SCREEN.check_fail_closed_frame(image)
    SCREEN.check_latest_result(screen, expected["form"], None)
    matches = TWO_BYTE_RESULT.findall(screen.read_text(errors="replace"))
    require(matches, "math-unit two-byte result is absent")
    values = [int(value) for value in matches[-1]]
    require(all(0 <= value <= 255 for value in values),
            "math-unit result byte out of range")
    append_product({
        "id": row_id,
        "group": expected["group"],
        "status": "measured-informational",
        "bytes": values,
        "screen": bind(screen),
        "image": bind(image),
    })
    print(
        f"c2-v123-link80-hardware-bundle: ROW INFO {row_id} "
        f"bytes={values}")


def record_red(
    row_id: str, screen: Path, image: Path, detail: str,
) -> None:
    SCREEN.check_fail_closed_frame(image)
    expected = row(row_id)
    append_product({
        "id": row_id,
        "group": expected["group"],
        "status": "row-local-first-red",
        "detail": detail,
        "screen": bind(screen),
        "image": bind(image),
    })
    print(f"c2-v123-link80-hardware-bundle: ROW-LOCAL RED {row_id}")


def record_skip(row_id: str, detail: str) -> None:
    expected = row(row_id)
    append_product({
        "id": row_id,
        "group": expected["group"],
        "status": "skipped-dependent",
        "detail": detail,
    })
    print(f"c2-v123-link80-hardware-bundle: ROW SKIP {row_id}")


def record_run_stop(screen: Path, image: Path) -> None:
    SCREEN.check_fail_closed_frame(image)
    raw = screen.read_text(errors="replace").lower()
    require(
        "*** stopped (run/stop)" in raw
        and re.search(r"(?m)^\s*lisp65>\s*$", raw),
        "RUN/STOP did not return to a live prompt",
    )
    append_product({
        "id": "while-run-stop",
        "group": "run-stop",
        "status": "passed",
        "result": "*** stopped (run/stop)",
        "screen": bind(screen),
        "image": bind(image),
    })
    print("c2-v123-link80-hardware-bundle: ROW PASS while-run-stop")


def monitor_command(fd: int, value: bytes, wait: float = 0.03) -> bytes:
    SERIAL.slow_write(fd, value + b"\r")
    time.sleep(wait)
    return SERIAL.serial_read(fd, 0.4)


def read_registers(fd: int, expected_pc: int) -> dict[str, str]:
    raw = monitor_command(fd, b"r", 0.05)
    match = re.search(
        rb"(?:^|\n)([0-9A-Fa-f]{4})"
        rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{2})"
        rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{2})"
        rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{4})",
        raw,
    )
    require(match is not None, "register row absent")
    pc = int(match.group(1), 16)
    require(pc == expected_pc,
            f"expected PC 0x{expected_pc:04x}, got 0x{pc:04x}")
    names = ("PC", "A", "X", "Y", "Z", "B", "SP")
    widths = (4, 2, 2, 2, 2, 2, 4)
    return {
        name: f"0x{int(match.group(index), 16):0{width}x}"
        for index, (name, width) in enumerate(zip(names, widths), 1)
    }


def capture_gc_pc() -> None:
    verify()
    require(not GC_PC.exists(), "GC PC capture is one-shot")
    hold = load(DEPLOYMENT)["capture"]["gc"]["hold_address"]
    fd = os.open(SERIAL.DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        SERIAL.configure_serial(fd)
        SERIAL.monitor_sync(fd, b"#c280gc\r")
        monitor_command(fd, b"t1", 0.05)
        registers = read_registers(fd, hold)
        patch = MONITOR.read_block(fd, hold, 2)
    finally:
        os.close(fd)
    require(patch == bytes.fromhex("80fe"), "live GC hold bytes drift")
    atomic_json(GC_PC, {
        "format": "lisp65-c2.2-v1.2.3-link80-gc-hold-pc-v1",
        "status": "stopped-at-alloc-oom-entry",
        "registers": registers,
        "live_patch": patch.hex(),
        "CPU_left_stopped": True,
    })
    print(f"c2-v123-link80-hardware-bundle: GC PC PASS 0x{hold:04x}")


def capture_values(index: int) -> dict[str, bytes]:
    geometry = load(DEPLOYMENT)["capture"]["gc"]
    directory = OUT / f"gc-capture-{index}"
    names = {
        "zp": geometry["zp_bytes"],
        "marks": geometry["marks_bytes"],
        "hot-heap": geometry["hot_heap_bytes"],
        "ext-heap": geometry["ext_heap_bytes"],
        "gc-runs": 2,
        "live-patch": 2,
    }
    result = {}
    for name, size in names.items():
        path = directory / f"{name}.bin"
        require(
            path.is_file() and path.stat().st_size == size,
            f"GC capture geometry drift: {path}",
        )
        result[name] = path.read_bytes()
    return result


def follow_freelist(
    head: int, hot: bytes, ext: bytes,
) -> tuple[list[int], str | None]:
    chain: list[int] = []
    seen: set[int] = set()
    current = head
    while current != 0:
        if current & 1:
            return chain, f"tagged/immediate freelist word 0x{current:04x}"
        index = current >> 1
        if not 0 < index < HOT_CELLS + EXT_CELLS:
            return chain, f"out-of-range freelist cell {index}"
        if index in seen:
            return chain, f"freelist cycle at cell {index}"
        seen.add(index)
        chain.append(index)
        if index < HOT_CELLS:
            current = u16(hot, index * HOT_CELL_BYTES + 1)
        else:
            current = u16(ext, (index - HOT_CELLS) * EXT_CELL_BYTES + 2)
    return chain, None


def evaluate_gc() -> None:
    require(GC_PC.is_file() and not GC_RECEIPT.exists(),
            "GC evaluation requires one fresh hold capture")
    geometry = load(DEPLOYMENT)["capture"]["gc"]
    captures = [capture_values(index) for index in range(1, 4)]
    require(
        all(
            captures[0][name] == captures[1][name] == captures[2][name]
            for name in captures[0]
        ),
        "GC witnesses changed across time-separated captures",
    )
    value = captures[0]
    zp_start = geometry["zp_start"]
    cell = lambda name: u16(  # noqa: E731
        value["zp"], geometry[f"{name}_address"] - zp_start)
    alloc_high = cell("alloc_high")
    frozen = cell("gc_frozen")
    freelist = cell("freelist")
    rootsp = cell("gc_rootsp")
    mem_oom = value["zp"][geometry["mem_oom_address"] - zp_start]
    marked = [
        index for index in range(1, HOT_CELLS + EXT_CELLS)
        if value["marks"][index >> 3] & (1 << (index & 7))
    ]
    chain, error = follow_freelist(
        freelist, value["hot-heap"], value["ext-heap"])
    runtime_ext_floor = max(frozen, HOT_CELLS - 1)
    eligible = set(range(1, HOT_CELLS))
    eligible.update(range(runtime_ext_floor + 1, alloc_high + 1))
    unmarked = sorted(eligible.difference(marked))
    if not chain and unmarked:
        classification = "sweep-or-freelist-return-failure"
    elif not chain:
        classification = "mark-root-retention-or-true-live-set-exhaustion"
    else:
        classification = "unexpected-alloc-oom-with-nonempty-freelist"
    receipt = {
        "format": "lisp65-c2.2-v1.2.3-link80-gc-two-number-hardware-v1",
        "recorded_on": date.today().isoformat(),
        "status": f"completed-{classification}",
        "promotable": False,
        "answer": {
            "marked_cells": len(marked),
            "cells_actually_returned_to_freelist": len(chain),
            "classification": classification,
        },
        "supporting_geometry": {
            "alloc_high": alloc_high,
            "gc_frozen": frozen,
            "gc_rootsp": rootsp,
            "mem_oom_at_hold": mem_oom,
            "gc_runs": u16(value["gc-runs"]),
            "freelist_head": f"0x{freelist:04x}",
            "freelist_error": error,
            "eligible_sweep_cells": len(eligible),
            "eligible_unmarked_cells": len(unmarked),
            "first_eligible_unmarked": unmarked[:16],
        },
        "captures": [
            {
                "index": index,
                **{
                    name: bind(OUT / f"gc-capture-{index}/{name}.bin")
                    for name in captures[0]
                },
            }
            for index in range(1, 4)
        ],
        "diagnostic_lifecycle": {
            "identity": bind(GC_PRODUCT, LOAD_ADDRESS),
            "eligible_for_promotion": False,
            "state": "discard-after-session",
        },
    }
    atomic_json(GC_RECEIPT, receipt)
    observations = load(OBSERVATIONS)
    observations["gc"] = {
        "status": receipt["status"],
        "marked": len(marked),
        "returned": len(chain),
        "receipt": bind(GC_RECEIPT),
    }
    atomic_json(OBSERVATIONS, observations, replace=True)
    print(
        "c2-v123-link80-hardware-bundle: GC COMPLETE "
        f"marked={len(marked)} returned={len(chain)} "
        f"class={classification}")


def record_gc_nonreproduction(screen: Path, image: Path) -> None:
    require(not GC_PC.exists() and not GC_RECEIPT.exists(),
            "GC nonreproduction requires no hold capture")
    test = config()["gc_diagnostic"]["workload"]
    SCREEN.check_fail_closed_frame(image)
    SCREEN.check_latest_result(
        screen, test["form"], test["expected_result_if_not_reproduced"])
    receipt = {
        "format": "lisp65-c2.2-v1.2.3-link80-gc-two-number-hardware-v1",
        "recorded_on": date.today().isoformat(),
        "status": "completed-oom-not-reproduced",
        "promotable": False,
        "answer": {
            "marked_cells": None,
            "cells_actually_returned_to_freelist": None,
            "classification": "oom-not-reproduced",
        },
        "observation": {
            "result": "600",
            "screen": bind(screen),
            "image": bind(image),
            "alloc_oom_hold_reached": False,
        },
        "diagnostic_lifecycle": {
            "identity": bind(GC_PRODUCT, LOAD_ADDRESS),
            "eligible_for_promotion": False,
            "state": "discard-after-session",
        },
    }
    atomic_json(GC_RECEIPT, receipt)
    observations = load(OBSERVATIONS)
    observations["gc"] = {
        "status": receipt["status"],
        "marked": None,
        "returned": None,
        "receipt": bind(GC_RECEIPT),
    }
    atomic_json(OBSERVATIONS, observations, replace=True)
    print("c2-v123-link80-hardware-bundle: GC COMPLETE oom-not-reproduced")


def record_gc_invalid(screen: Path, image: Path, detail: str) -> None:
    require(not GC_RECEIPT.exists(), "GC invalid result is already receipted")
    if image.is_file():
        SCREEN.check_fail_closed_frame(image)
    receipt = {
        "format": "lisp65-c2.2-v1.2.3-link80-gc-two-number-hardware-v1",
        "recorded_on": date.today().isoformat(),
        "status": "invalid-measurement-no-inference",
        "promotable": False,
        "answer": {
            "marked_cells": None,
            "cells_actually_returned_to_freelist": None,
            "classification": "invalid-no-inference",
        },
        "detail": detail,
        "screen": bind(screen) if screen.is_file() else None,
        "image": bind(image) if image.is_file() else None,
        "diagnostic_lifecycle": {
            "identity": bind(GC_PRODUCT, LOAD_ADDRESS),
            "eligible_for_promotion": False,
            "state": "discard-after-session",
        },
    }
    atomic_json(GC_RECEIPT, receipt)
    observations = load(OBSERVATIONS)
    observations["gc"] = {
        "status": receipt["status"],
        "marked": None,
        "returned": None,
        "receipt": bind(GC_RECEIPT),
    }
    atomic_json(OBSERVATIONS, observations, replace=True)
    print("c2-v123-link80-hardware-bundle: GC INVALID no-inference")


def capture_dirmiss() -> None:
    require(not DIRMISS_RECEIPT.exists(), "DIRMISS capture is one-shot")
    geometry = load(DEPLOYMENT)["capture"]["dirmiss"]
    fd = os.open(SERIAL.DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        SERIAL.configure_serial(fd)
        SERIAL.monitor_sync(fd, b"#c280post\r")
        monitor_command(fd, b"t1", 0.05)
        registers = read_registers(fd, geometry["hold_address"])
        rows = []
        for index, delay in enumerate((0, 1, 4), 1):
            if delay:
                time.sleep(delay)
            scratch = MONITOR.read_block(
                fd, geometry["scratch_address"], geometry["scratch_bytes"])
            patch = MONITOR.read_block(fd, geometry["hold_address"], 2)
            rows.append({
                "index": index,
                "scratch_hex": scratch.hex(),
                "scratch_name": scratch.split(b"\0", 1)[0].decode(
                    "ascii", errors="replace"),
                "matches_expected": scratch.startswith(EXPECTED_NAME + b"\0"),
                "live_patch": patch.hex(),
            })
    finally:
        os.close(fd)
    require(
        all(row["live_patch"] == DIRMISS_PATCH_AFTER.hex() for row in rows)
        and all(
            {key: value for key, value in row.items() if key != "index"}
            == {key: value for key, value in rows[0].items() if key != "index"}
            for row in rows
        ),
        "DIRMISS post-symname witnesses changed",
    )
    correct = all(row["matches_expected"] for row in rows)
    outcome = (
        "scratch-correct-after-symname"
        if correct else "scratch-damaged-after-symname")
    receipt = {
        "format": "lisp65-c2.2-v1.2.3-link80-post-symname-hardware-v1",
        "recorded_on": date.today().isoformat(),
        "status": outcome,
        "promotable": False,
        "registers": registers,
        "captures": rows,
        "answer": {
            "scratch_correct_after_symname": correct,
            "outcome": outcome,
        },
        "diagnostic_lifecycle": {
            "product": bind(DIRMISS_PRODUCT, LOAD_ADDRESS),
            "session": bind(DIRMISS_SESSION, SESSION_ADDRESS),
            "eligible_for_promotion": False,
            "state": "discarded-after-capture",
        },
    }
    atomic_json(DIRMISS_RECEIPT, receipt)
    observations = load(OBSERVATIONS)
    observations["dirmiss"] = {
        "status": outcome,
        "receipt": bind(DIRMISS_RECEIPT),
    }
    atomic_json(OBSERVATIONS, observations, replace=True)
    print(
        "c2-v123-link80-hardware-bundle: DIRMISS COMPLETE "
        f"scratch-correct={str(correct).lower()}")


def record_dirmiss_invalid(screen: Path, image: Path, detail: str) -> None:
    require(
        not DIRMISS_RECEIPT.exists(),
        "DIRMISS invalid result is already receipted",
    )
    if image.is_file():
        SCREEN.check_fail_closed_frame(image)
    receipt = {
        "format": "lisp65-c2.2-v1.2.3-link80-post-symname-hardware-v1",
        "recorded_on": date.today().isoformat(),
        "status": "invalid-diagnostic-no-inference",
        "promotable": False,
        "detail": detail,
        "screen": bind(screen) if screen.is_file() else None,
        "image": bind(image) if image.is_file() else None,
        "answer": {
            "scratch_correct_after_symname": None,
            "outcome": "invalid-no-inference",
        },
        "diagnostic_lifecycle": {
            "product": bind(DIRMISS_PRODUCT, LOAD_ADDRESS),
            "session": bind(DIRMISS_SESSION, SESSION_ADDRESS),
            "eligible_for_promotion": False,
            "state": "discarded-after-session",
        },
    }
    atomic_json(DIRMISS_RECEIPT, receipt)
    observations = load(OBSERVATIONS)
    observations["dirmiss"] = {
        "status": receipt["status"],
        "receipt": bind(DIRMISS_RECEIPT),
    }
    atomic_json(OBSERVATIONS, observations, replace=True)
    print("c2-v123-link80-hardware-bundle: DIRMISS INVALID no-inference")


def finalize() -> None:
    verify()
    deployment = load(DEPLOYMENT)
    observations = load(OBSERVATIONS)
    ids = {row["id"] for row in observations["product_rows"]}
    expected = {row["id"] for row in config()["product_rows"]}
    require(
        GC_RECEIPT.is_file() and DIRMISS_RECEIPT.is_file()
        and expected <= ids,
        "Link-80 bundled hardware evidence incomplete",
    )
    rows = observations["product_rows"]
    reds = [
        row for row in rows
        if row["status"] not in (
            "passed", "passed-measured", "measured-informational")
    ]
    frames = {
        row["id"]: row["frames"]
        for row in rows if row["id"] in ("require-first", "require-repeat")
        and "frames" in row
    }
    require(
        not (set(frames) - {"require-first", "require-repeat"}),
        "require frame accounting drift",
    )
    receipt = {
        "format": "lisp65-c2.2-v1.2.3-link80-bundled-hardware-v1",
        "recorded_on": date.today().isoformat(),
        "status": (
            "completed-one-session-all-product-rows-green"
            if not reds else "completed-with-row-local-first-reds"
        ),
        "candidate": deployment["candidate"],
        "product_rows": rows,
        "row_local_first_reds": reds,
        "require_fastpath": {
            "first_frames": frames.get("require-first"),
            "repeat_frames": frames.get("require-repeat"),
            "method": "live high-low-high frame snapshots around real require",
            "LA_17_20_not_used": True,
        },
        "GC": load(GC_RECEIPT),
        "DIRMISS": load(DIRMISS_RECEIPT),
        "device": {
            "core_id": bind(OUT / "device-core-id.bin"),
            "physical_sessions": 1,
            "controlled_deployments": 3,
        },
        "authority": {
            "config": bind(CONFIG),
            "preparation": bind(PREPARATION),
            "deployment": bind(DEPLOYMENT),
            "observations": bind(OBSERVATIONS),
        },
        "execution_accounting": {
            "physical_device_sessions": 1,
            "product_links": 0,
            "diagnostic_identities_promotable": 0,
        },
        "claim_limit": (
            "Claims only the listed Link-80 product rows and the two bounded "
            "diagnostic observations from this physical session."
        ),
    }
    atomic_json(HARDWARE_RECEIPT, receipt)
    observations["status"] = "completed-and-receipted"
    observations["receipt"] = bind(HARDWARE_RECEIPT)
    atomic_json(OBSERVATIONS, observations, replace=True)
    print("c2-v123-link80-hardware-bundle: FINAL PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=(
            "prepare", "refresh-authority", "close-preparation", "verify",
            "record-exact", "record-frame",
            "record-informational", "record-red", "record-skip",
            "record-run-stop",
            "capture-gc-pc", "evaluate-gc", "record-gc-nonreproduction",
            "record-gc-invalid", "capture-dirmiss",
            "record-dirmiss-invalid", "finalize",
        ),
    )
    parser.add_argument("--id")
    parser.add_argument("--screen", type=Path)
    parser.add_argument("--image", type=Path)
    parser.add_argument("--detail")
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
    elif args.action == "refresh-authority":
        refresh_authority()
    elif args.action == "close-preparation":
        close_preparation()
    elif args.action == "verify":
        verify()
    elif args.action == "record-exact":
        require(args.id and args.screen and args.image,
                "record-exact requires --id/--screen/--image")
        record_exact(args.id, args.screen, args.image)
    elif args.action == "record-frame":
        require(args.id and args.screen and args.image,
                "record-frame requires --id/--screen/--image")
        record_frame(args.id, args.screen, args.image)
    elif args.action == "record-informational":
        require(args.id and args.screen and args.image,
                "record-informational requires --id/--screen/--image")
        record_informational(args.id, args.screen, args.image)
    elif args.action == "record-red":
        require(args.id and args.screen and args.image and args.detail,
                "record-red requires --id/--screen/--image/--detail")
        record_red(args.id, args.screen, args.image, args.detail)
    elif args.action == "record-skip":
        require(args.id and args.detail,
                "record-skip requires --id/--detail")
        record_skip(args.id, args.detail)
    elif args.action == "record-run-stop":
        require(args.screen and args.image,
                "record-run-stop requires --screen/--image")
        record_run_stop(args.screen, args.image)
    elif args.action == "capture-gc-pc":
        capture_gc_pc()
    elif args.action == "evaluate-gc":
        evaluate_gc()
    elif args.action == "record-gc-nonreproduction":
        require(args.screen and args.image,
                "record-gc-nonreproduction requires --screen/--image")
        record_gc_nonreproduction(args.screen, args.image)
    elif args.action == "record-gc-invalid":
        require(args.screen and args.image and args.detail,
                "record-gc-invalid requires --screen/--image/--detail")
        record_gc_invalid(args.screen, args.image, args.detail)
    elif args.action == "capture-dirmiss":
        capture_dirmiss()
    elif args.action == "record-dirmiss-invalid":
        require(args.screen and args.image and args.detail,
                "record-dirmiss-invalid requires --screen/--image/--detail")
        record_dirmiss_invalid(args.screen, args.image, args.detail)
    elif args.action == "finalize":
        finalize()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BundleError as error:
        print(f"c2-v123-link80-hardware-bundle: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(1)
