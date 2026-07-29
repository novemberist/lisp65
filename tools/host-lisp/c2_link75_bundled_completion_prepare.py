#!/usr/bin/env python3
"""Prepare Link 75's product-first bundled completion appointment.

This creates no product link and performs no hardware action.  It binds the
canonical Link-75 deployment, prepares the zero-delta post-symname diagnostic
variant, and leaves the DMA variant unbuilt until the post-return capture
requires it.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link75_dirmiss_detail_hold_hw as OLD  # noqa: E402
import runtime_overlay_bank as R  # noqa: E402


BASE = ROOT / "build/post-promotion/link75-bound-compiler-carrier"
FINAL = BASE / "final"
OUT = BASE / "bundled-completion-session"
DIAG = OUT / "post-symname-hold-NONPROMOTABLE"
CONFIG = ROOT / "config/c2.2-link75-bundled-completion-session.json"
MANIFEST = BASE / "canonical-product-manifest.json"
BASE_DEPLOYMENT = BASE / "hardware-session/deployment.json"
PRODUCT = FINAL / "lisp65-c2-substitution-linked.prg"
ELF = FINAL / "lisp65-c2-substitution-linked.prg.elf"
SESSION = FINAL / "runtime-overlays-session-final.bin"
SESSION_JSON = FINAL / "runtime-overlays-session-final.json"
SESSION_REGION1 = FINAL / "runtime-overlays-session-final-region1.bin"
PRODUCT_PHASE_DEPLOYMENT = OUT / "product-phase-deployment.json"
C2D_PREFIX = FINAL / (
    "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin")
C2D_RESET_DOMAIN = OUT / "c2d-v6-reset-domain.bin"
DIAG_SESSION = DIAG / (
    "runtime-overlays-session-link75-post-symname-hold-"
    "NONPROMOTABLE.bin")
DIAG_SESSION_JSON = DIAG / (
    "runtime-overlays-session-link75-post-symname-hold-"
    "NONPROMOTABLE.json")
DIAG_PRODUCT = DIAG / (
    "lisp65-link75-post-symname-hold-NONPROMOTABLE.prg")
DIAG_BINDING = DIAG / "runtime-overlay-verifier-bindings.bin"
DIAG_DEPLOYMENT = DIAG / "deployment.json"
SOURCE_PARITY = OUT / "current-source-parity.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-bundled-completion-preparation-receipt.json")
LINK_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link75-bound-compiler-carrier-structural-receipt.json")
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-bound-carrier-dirmiss-hardware-first-red.json")
SOURCE_BINDINGS = BASE / (
    "receipts/bound-artifact-manifest-source-bindings.json")
CARRIER = BASE / "compiler-carrier/lcc.manifest.json"
TIER = BASE / "compiler-carrier/compiler-tier/tier-generation.json"
PRODUCT_IDENTITY = BASE / (
    "source-bound-product/substitution-artifacts.json")

SLOT = 47
SLOT_VMA = 0xC356
SLOT_FILE_OFFSET = 0xEA00
HOLD_VMA = 0xC472
PATCH_FILE_OFFSET = 0xEB1C
PATCH_BEFORE = bytes.fromhex("85 04")
PATCH_AFTER = bytes.fromhex("80 fe")
LOAD_ADDRESS = 0x2001
SESSION_ADDRESS = 0x08000000
C2D_ADDRESS = 0x00050000
C2D_PREFIX_BYTES = 33840
C2D_RESET_DOMAIN_BYTES = 50816


class PreparationError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PreparationError(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"bound artifact absent: {path}")
    value: dict[str, Any] = {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }
    if address is not None:
        value["address"] = f"0x{address:08x}"
    return value


def write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.read_bytes() == value, f"artifact drift: {path}")
        return
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(value)
    temporary.replace(path)


def write_json(path: Path, value: dict[str, Any]) -> None:
    write_bytes(
        path,
        (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii"),
    )


def complete_reset_domain() -> bytes:
    prefix = C2D_PREFIX.read_bytes()
    require(
        len(prefix) == C2D_PREFIX_BYTES,
        "canonical C2D prefix size drift",
    )
    return prefix + bytes(C2D_RESET_DOMAIN_BYTES - len(prefix))


def bind_complete_reset_domain(
        deployment: dict[str, Any]) -> dict[str, Any]:
    replacements = 0
    preloads = []
    for row in deployment["preloads"]:
        copy = dict(row)
        if copy["role"] == "c2d-v6-code-plane":
            require(
                copy["address"] == f"0x{C2D_ADDRESS:08x}"
                and copy["bytes"] == C2D_PREFIX_BYTES
                and copy["sha256"] == sha(C2D_PREFIX),
                "canonical C2D prefix preload drift",
            )
            copy = {
                **bind(C2D_RESET_DOMAIN, C2D_ADDRESS),
                "role": "c2d-v6-complete-reset-domain",
            }
            replacements += 1
        preloads.append(copy)
    require(replacements == 1, "C2D reset-domain replacement not unique")
    deployment["preloads"] = preloads
    deployment["cold_reset_contract"] = {
        "reset_domain": [0, C2D_RESET_DOMAIN_BYTES],
        "canonical_prefix": [0, C2D_PREFIX_BYTES],
        "zero_suffix": [C2D_PREFIX_BYTES, C2D_RESET_DOMAIN_BYTES],
        "c2j": [50752, 50816],
        "pre_run_readback_required": True,
    }
    return deployment


def patch_session(source: bytes) -> tuple[bytes, dict[str, Any]]:
    base = OLD.parsed_session(source)
    row = base.slices[SLOT]
    require(
        row.id == SLOT
        and row.vma == SLOT_VMA
        and row.file_offset == SLOT_FILE_OFFSET
        and PATCH_FILE_OFFSET
            == row.file_offset + HOLD_VMA - row.vma,
        "post-symname overlay geometry drift",
    )
    result = bytearray(source)
    require(
        result[PATCH_FILE_OFFSET:PATCH_FILE_OFFSET + 2] == PATCH_BEFORE,
        "post-symname return instruction drift",
    )
    result[PATCH_FILE_OFFSET:PATCH_FILE_OFFSET + 2] = PATCH_AFTER

    record_offset = R.HEADER_SIZE + SLOT * R.ENTRY_SIZE
    fields = list(R.ENTRY.unpack_from(result, record_offset))
    old_payload_crc = fields[9]
    old_record_crc = fields[10]
    fields[9] = R.crc16_ccitt_false(
        result[row.file_offset:row.file_offset + row.file_size])
    fields[10] = 0
    raw = bytearray(R.ENTRY.pack(*fields))
    fields[10] = R.crc16_ccitt_false(raw)
    require(fields[10] != 0, "derived v4 record CRC is forbidden zero")
    result[record_offset:record_offset + R.ENTRY_SIZE] = R.ENTRY.pack(*fields)

    directory_end = R.HEADER_SIZE + len(base.slices) * R.ENTRY_SIZE
    old_directory_crc = int.from_bytes(result[24:26], "little")
    old_header_crc = int.from_bytes(result[26:28], "little")
    struct.pack_into(
        "<H", result, 24,
        R.crc16_ccitt_false(result[R.HEADER_SIZE:directory_end]))
    struct.pack_into("<H", result, 26, 0)
    struct.pack_into(
        "<H", result, 26,
        R.crc16_ccitt_false(result[:R.HEADER_SIZE]))
    candidate = bytes(result)
    verified = OLD.parsed_session(candidate)
    derived = verified.slices[SLOT]
    require(
        derived.crc16 == fields[9]
        and derived.record_crc16 == fields[10],
        "post-symname session identity did not validate",
    )
    return candidate, {
        "record_offset": record_offset,
        "old_payload_crc16": f"0x{old_payload_crc:04x}",
        "new_payload_crc16": f"0x{fields[9]:04x}",
        "old_record_crc16": f"0x{old_record_crc:04x}",
        "new_record_crc16": f"0x{fields[10]:04x}",
        "old_directory_crc16": f"0x{old_directory_crc:04x}",
        "new_directory_crc16": f"0x{verified.directory_crc16:04x}",
        "old_header_crc16": f"0x{old_header_crc:04x}",
        "new_header_crc16": f"0x{verified.header_crc16:04x}",
        "old_family_crc16":
            f"0x{R.crc16_ccitt_false(source):04x}",
        "new_family_crc16":
            f"0x{R.crc16_ccitt_false(candidate):04x}",
    }


def session_catalog(
        source: dict[str, Any],
        candidate: bytes,
        identity: dict[str, Any],
) -> dict[str, Any]:
    value = deepcopy(source)
    value["schema"] = (
        "lisp65-runtime-overlay-bank-v4-link75-post-symname-hold-"
        "nonpromotable")
    value.setdefault("policy", {})["promotable"] = False
    value["policy"]["diagnostic_identity"] = (
        "Link75-DIRMISS-detail-post-symname-hold-NONPROMOTABLE")
    row = value["slices"][SLOT]
    payload = candidate[
        row["file_offset"]:row["file_offset"] + row["file_size"]]
    row["crc16"] = int(identity["new_payload_crc16"], 16)
    row["record_crc16"] = int(identity["new_record_crc16"], 16)
    row["sha256"] = sha_bytes(payload)
    value["catalog"]["directory_crc16"] = int(
        identity["new_directory_crc16"], 16)
    value["catalog"]["header_crc16"] = int(
        identity["new_header_crc16"], 16)
    value["storage"]["crc16"] = int(
        identity["new_family_crc16"], 16)
    value["storage"]["sha256"] = sha_bytes(candidate)
    value["storage"]["file"] = DIAG_SESSION.name
    return value


def reject_mutations(
        candidate: bytes,
        candidate_product: bytes,
        identity: dict[str, Any],
        binding: dict[str, Any],
) -> list[str]:
    rejected = []
    record_offset = int(identity["record_offset"])
    for label, offset, old in (
        ("stale-payload-crc", record_offset + 20,
         int(identity["old_payload_crc16"], 16).to_bytes(2, "little")),
        ("stale-record-crc", record_offset + 22,
         int(identity["old_record_crc16"], 16).to_bytes(2, "little")),
        ("stale-directory-crc", 24,
         int(identity["old_directory_crc16"], 16).to_bytes(2, "little")),
        ("stale-header-crc", 26,
         int(identity["old_header_crc16"], 16).to_bytes(2, "little")),
    ):
        mutant = bytearray(candidate)
        mutant[offset:offset + 2] = old
        try:
            OLD.parsed_session(bytes(mutant))
        except R.OverlayBankError:
            rejected.append(label)
        else:
            raise PreparationError(f"session mutation accepted: {label}")
    opcode = bytearray(candidate)
    opcode[PATCH_FILE_OFFSET:PATCH_FILE_OFFSET + 2] = PATCH_BEFORE
    try:
        OLD.parsed_session(bytes(opcode))
    except R.OverlayBankError:
        rejected.append("hold-opcode-restored-with-stale-derived-identity")
    else:
        raise PreparationError("post-symname hold mutation accepted")
    stale_product = bytearray(candidate_product)
    offset = int(binding["session_stage_crc_file_offset"])
    stale_product[offset:offset + 2] = int(
        binding["old_session_stage_crc16"], 16).to_bytes(2, "little")
    require(
        int.from_bytes(stale_product[offset:offset + 2], "little")
        != int(binding["new_session_stage_crc16"], 16),
        "stale product binding mutation ineffective")
    rejected.append("stale-product-session-stage-binding")
    return rejected


def run_source_parity() -> None:
    command = [
        sys.executable,
        "tools/host-lisp/c2_bound_artifact_source_parity.py",
        "--carrier-manifest", str(CARRIER),
        "--tier-receipt", str(TIER),
        "--product-identity", str(PRODUCT_IDENTITY),
        "--source-bindings", str(SOURCE_BINDINGS),
        "--receipt", str(SOURCE_PARITY),
    ]
    subprocess.run(command, cwd=ROOT, check=True)


def prepare() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "bundled completion preparation is one-shot")
    config = load(CONFIG)
    manifest = load(MANIFEST)
    base_deployment = load(BASE_DEPLOYMENT)
    first_red = load(FIRST_RED)
    link = load(LINK_RECEIPT)
    require(
        config["status"] == "owner-authorized-prepare-no-hardware"
        and config["policy"]["new_product_link"] is False
        and manifest["identity"]["resident_prg_sha256"] == sha(PRODUCT)
        and manifest["identity"]["linked_elf_sha256"] == sha(ELF)
        and link["status"]
            == "passed-Link75-source-bound-compiler-carrier-hardware-not-run"
        and [row["id"] for row in first_red["passed_before_first_red"]]
            == ["boot-watch", "define-is", "call-is", "intern-positive"],
        "Link75 bundled-completion authority drift",
    )
    OUT.mkdir(parents=True)
    write_bytes(C2D_RESET_DOMAIN, complete_reset_domain())
    run_source_parity()

    product_deployment = bind_complete_reset_domain(
        deepcopy(base_deployment))
    product_deployment["format"] = (
        "lisp65-c2.2-link75-bundled-product-phase-deployment-v1")
    product_deployment["status"] = "ready-product-phase-hardware-not-run"
    product_deployment["rows"] = config["product_phase"]["rows"]
    product_deployment["media_transport"] = (
        "upload/readback, run pre-mount product rows, manually mount the "
        "bound D81 and return with F3, then run every post-mount row")
    product_deployment["authority"]["bundled_config"] = bind(CONFIG)
    product_deployment["authority"]["current_source_parity"] = bind(
        SOURCE_PARITY)
    product_deployment["authority"]["predecessor_hardware_First_Red"] = bind(
        FIRST_RED)
    product_deployment["execution_accounting"] = {
        "new_product_links": 0,
        "hardware_runs": 0,
    }
    write_json(PRODUCT_PHASE_DEPLOYMENT, product_deployment)

    source_session = SESSION.read_bytes()
    source_product = PRODUCT.read_bytes()
    candidate_session, identity = patch_session(source_session)
    family_crc = R.crc16_ccitt_false(candidate_session)
    candidate_product, candidate_binding, binding = OLD.patch_product(
        source_product, family_crc)
    require(
        len(candidate_session) == len(source_session)
        and len(candidate_product) == len(source_product),
        "post-symname diagnostic changed artifact size")
    mutations = reject_mutations(
        candidate_session, candidate_product, identity, binding)

    write_bytes(DIAG_SESSION, candidate_session)
    write_bytes(DIAG_PRODUCT, candidate_product)
    write_bytes(DIAG_BINDING, candidate_binding)
    write_json(
        DIAG_SESSION_JSON,
        session_catalog(load(SESSION_JSON), candidate_session, identity))

    diagnostic_deployment = bind_complete_reset_domain(
        deepcopy(base_deployment))
    diagnostic_deployment["format"] = (
        "lisp65-c2.2-link75-post-symname-hold-deployment-v1")
    diagnostic_deployment["status"] = (
        "ready-nonpromotable-hardware-after-product-phase")
    diagnostic_deployment["promotable"] = False
    diagnostic_deployment["product"] = {
        **bind(DIAG_PRODUCT, LOAD_ADDRESS),
        "role": "c2-resident-prg",
    }
    replacements = 0
    preloads = []
    for row in diagnostic_deployment["preloads"]:
        copy = dict(row)
        if copy["role"] == "c2-session-family-region-0":
            copy = {
                **bind(DIAG_SESSION, SESSION_ADDRESS),
                "role": copy["role"],
            }
            replacements += 1
        preloads.append(copy)
    require(replacements == 1, "diagnostic session replacement not unique")
    diagnostic_deployment["preloads"] = preloads
    diagnostic_deployment["rows"] = [{
        "id": "post-symname-return-hold",
        "form": "(intern-renderer-missing)",
        "expect": "self-loop at $C472 before renderer consumption",
        "captures": 3,
    }]
    diagnostic_deployment["decision"] = {
        "scratch_correct":
            "renderer outcome R; stop and do not build DMA Stage 1",
        "scratch_damaged":
            "build conditional DMA Stage 1 for this same appointment",
    }
    diagnostic_deployment["authority"]["bundled_config"] = bind(CONFIG)
    diagnostic_deployment["execution_accounting"] = {
        "new_product_links": 0,
        "hardware_runs": 0,
    }
    write_json(DIAG_DEPLOYMENT, diagnostic_deployment)

    receipt = {
        "format":
            "lisp65-c2.2-link75-bundled-completion-preparation-v1",
        "recorded_on": "2026-07-28",
        "status":
            "passed-product-first-session-and-post-symname-variant-prepared",
        "product_candidate": {
            "link": 75,
            "product": bind(PRODUCT, LOAD_ADDRESS),
            "ELF": bind(ELF),
            "manifest": bind(MANIFEST),
            "product_delta_since_Link75": 0,
            "new_product_link": False,
            "reason":
                "current bound source closure passed against Link75",
        },
        "product_phase": {
            "deployment": bind(PRODUCT_PHASE_DEPLOYMENT),
            "rows": len(config["product_phase"]["rows"]),
            "first_purpose":
                "require defstruct, define point, call generated code",
        },
        "diagnostic_phase": {
            "position": "after product phase in the same device appointment",
            "identity": {
                "product": bind(DIAG_PRODUCT, LOAD_ADDRESS),
                "session_family": bind(DIAG_SESSION, SESSION_ADDRESS),
                "session_catalog": bind(DIAG_SESSION_JSON),
                "publish_last_binding": bind(DIAG_BINDING),
                "deployment": bind(DIAG_DEPLOYMENT),
                "promotable": False,
            },
            "patch": {
                "slot": SLOT,
                "runtime_address": f"0x{HOLD_VMA:04x}",
                "session_family_file_offset": PATCH_FILE_OFFSET,
                "before": PATCH_BEFORE.hex(),
                "after": PATCH_AFTER.hex(),
                "size_delta": 0,
                "ordering":
                    "after JSR symname, before STA __rc2 and renderer reads",
            },
            "identity_rebind": identity,
            "mutations_rejected": mutations,
            "stage1_DMA_built": False,
        },
        "authority": {
            "config": bind(CONFIG),
            "link_receipt": bind(LINK_RECEIPT),
            "prior_hardware_First_Red": bind(FIRST_RED),
            "current_source_parity": bind(SOURCE_PARITY),
            "driver": bind(Path(__file__).resolve()),
        },
        "execution_accounting": {
            "compiler_runs": 0,
            "product_links": 0,
            "hardware_runs": 0,
        },
        "claim_limit": (
            "Preparation only. Link75 remains the product identity; no "
            "hardware result, defstruct result, renderer attribution, DMA "
            "claim or product closure is made."),
    }
    write_json(RECEIPT, receipt)
    return {
        "status": receipt["status"],
        "product": receipt["product_candidate"]["product"]["sha256"],
        "rows": receipt["product_phase"]["rows"],
        "diagnostic_mutations":
            len(receipt["diagnostic_phase"]["mutations_rejected"]),
        "product_links": 0,
        "hardware_runs": 0,
    }


def verify() -> dict[str, Any]:
    receipt = load(RECEIPT)
    require(
        receipt["status"]
            == "passed-product-first-session-and-post-symname-variant-prepared"
        and receipt["product_candidate"]["product"]["sha256"] == sha(PRODUCT)
        and receipt["execution_accounting"]
            == {"compiler_runs": 0, "product_links": 0, "hardware_runs": 0},
        "bundled completion receipt drift")
    require(
        C2D_RESET_DOMAIN.read_bytes() == complete_reset_domain(),
        "complete C2D reset-domain artifact drift",
    )
    candidate_session, identity = patch_session(SESSION.read_bytes())
    family_crc = R.crc16_ccitt_false(candidate_session)
    candidate_product, candidate_binding, binding = OLD.patch_product(
        PRODUCT.read_bytes(), family_crc)
    require(
        DIAG_SESSION.read_bytes() == candidate_session
        and DIAG_PRODUCT.read_bytes() == candidate_product
        and DIAG_BINDING.read_bytes() == candidate_binding,
        "post-symname diagnostic artifact drift")
    mutations = reject_mutations(
        candidate_session, candidate_product, identity, binding)
    for deployment_path in (PRODUCT_PHASE_DEPLOYMENT, DIAG_DEPLOYMENT):
        deployment = load(deployment_path)
        reset_rows = [
            row for row in deployment["preloads"]
            if row["role"] == "c2d-v6-complete-reset-domain"
        ]
        if reset_rows:
            require(
                len(reset_rows) == 1
                and reset_rows[0]["bytes"] == C2D_RESET_DOMAIN_BYTES
                and reset_rows[0]["sha256"] == sha(C2D_RESET_DOMAIN),
                f"complete reset-domain binding drift: {deployment_path}",
            )
        else:
            prefix_rows = [
                row for row in deployment["preloads"]
                if row["role"] == "c2d-v6-code-plane"
            ]
            require(
                len(prefix_rows) == 1
                and prefix_rows[0]["bytes"] == C2D_PREFIX_BYTES,
                f"historical prefix-only binding drift: {deployment_path}",
            )
        for row in [
                deployment["product"], *deployment["preloads"]]:
            path = ROOT / row["path"]
            require(
                path.stat().st_size == row["bytes"]
                and sha(path) == row["sha256"],
                f"deployment artifact drift: {path}")
    return {
        "status": "verified",
        "product": sha(PRODUCT),
        "diagnostic_mutations": len(mutations),
        "product_links": 0,
        "hardware_runs": 0,
    }


def main() -> int:
    action = sys.argv[1:] or ["prepare"]
    require(
        action in (["prepare"], ["verify"]),
        "usage: c2_link75_bundled_completion_prepare.py [prepare|verify]")
    result = prepare() if action == ["prepare"] else verify()
    print("c2-link75-bundled-completion: " + json.dumps(
        result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        PreparationError, OLD.HoldError, OSError, ValueError, KeyError,
        json.JSONDecodeError, subprocess.SubprocessError,
    ) as error:
        print(
            "c2-link75-bundled-completion: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
