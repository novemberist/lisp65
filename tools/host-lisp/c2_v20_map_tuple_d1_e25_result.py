#!/usr/bin/env python3
"""Bind the authorised stopped-state E25 discriminator result.

The row distinguishes decoder failure from export-publication failure.  The
captured decoder tuple additionally binds the failure to phase 02a's first
Shelf/C2D image pair, but deliberately does not invent a finer provenance
than the shipped code records.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402

EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
ROW = ROOT / "config/c2-v20-map-tuple-d1-e25-capture-row.json"
FIRST_RED = EVIDENCE / "c2.3-v2.0-map-tuple-d1-e25-first-red-receipt.json"
MEDIA = EVIDENCE / "c2.3-v2.0-map-tuple-media-closure-receipt.json"
ELF = ROOT / (
    "build/c2.3/v2.0-map-tuple-fix-replacement-card/final/"
    "lisp65-c2-substitution-linked.prg.elf")
DECODER = ROOT / (
    "build/c2.3/v2.0-map-tuple-fix-replacement-card/final/"
    "generated-product-sources/c2-stream-decoder.c")
RUNTIME_SOURCE = ROOT / (
    "build/c2.3/v2.0-map-tuple-fix-replacement-card/final/"
    "generated-product-sources/c2_product_runtime.c")
RESET_DOMAIN = ROOT / (
    "build/c2.3/v2.0-map-tuple-media/shared-system/"
    "c2d-v6-reset-domain.bin")
CAPTURE = ROOT / "build/c2.3/v2.0-map-tuple-d1/e25-stopped-state/capture.json"
CAPTURE_DRIVER = ROOT / "tools/host-lisp/c2_v20_map_tuple_d1_e25_capture.py"
RECEIPT = EVIDENCE / "c2.3-v2.0-map-tuple-d1-e25-device-receipt.json"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
DRIVER = Path(__file__).resolve()

FORMAT = "lisp65-c2.3-v20-map-tuple-d1-e25-device-result-v1"
STATUS = "D1-E25-DECODER-IO-PHASE-02A-IMAGE0"
AUTHORIZATION_COMMIT = "7478ce73"
CAPTURE_SHA256 = "320cc81c2dff3cbc0fb3655107202be32ba6f7dd7b7d34a624e32e50a23567ef"
ELF_SHA256 = "a481eff4acd32f04dde6660090aa2761a2f4a4b6307945cbcb2cda0f70435673"
DECODER_SHA256 = "56af9971943bc263d7dbf84b06750aaca655ba05ab9e5f2a27af98aa72b8732e"
RUNTIME_SOURCE_SHA256 = "f187612a73d501733a3407b117fb16164719b1377199b9d219481aa28c90a692"
RESET_DOMAIN_SHA256 = "3010ec3807409338d119c57444c960d67f306a5b978ac346d5ed7ab119beee29"
MEDIA_SHA256 = "3b020a0c28c7e446e869d33af6231eb55e58a9019df28616350cc581b0d9e71c"

TUPLE = {
    "PC": "0xe096", "A": "0x02", "X": "0x64", "Y": "0x01",
    "Z": "0x00", "B": "0x00", "SP": "0x01e4",
    "MAPH": "0x8000", "MAPL": "0x0000",
    "suffix": "4C96E0  00     04 .....I.. ...P 15 -  00 - ..c..lhc",
}
READS = {
    "boot-publication-zp": (0x002E, 9, "000000000ce0ffe025"),
    "roots-ready-oom-zp": (0x008A, 6, "000000000000"),
    "pending-error-pointer": (0xBFEF, 2, "88b9"),
    "c2-boot-runtime": (
        0xC080, 50,
        "000084c0f16d010067324f5f308401000600f302710b300030083058307860"
        "01000000000000000000100000000002000100"),
}

SYMBOLS = {
    "c2_journal_count": 0x002E,
    "pending_code": 0x0036,
    "c2_pending_roots": 0x008A,
    "c2_ready": 0x008C,
    "mem_oom": 0x008F,
    "lisp_error_msg": 0xBFEF,
    "c2_committed_roots": 0xC080,
    "c2_decode_active": 0xC082,
    "c2_runtime": 0xC084,
}


class ResultError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResultError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"file absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": sha(raw)}


def u16(raw: bytes, offset: int) -> int:
    return struct.unpack_from("<H", raw, offset)[0]


def u24(raw: bytes, offset: int) -> int:
    return int.from_bytes(raw[offset:offset + 3], "little")


def u32(raw: bytes, offset: int) -> int:
    return struct.unpack_from("<I", raw, offset)[0]


def captured_rows() -> dict[str, Any]:
    return {
        name: {"physical_address": f"0x{address:08x}", "bytes": count,
               "observed_hex": observed}
        for name, (address, count, observed) in READS.items()
    }


def runtime_fields() -> dict[str, int]:
    whole = bytes.fromhex(READS["c2-boot-runtime"][2])
    require(len(whole) == 50, "captured runtime range length drift")
    raw = whole[4:]
    require(len(raw) == 46, "c2_runtime length drift")
    return {
        "shelf_bytes": u32(raw, 0),
        "catalog_crc32": u32(raw, 4),
        "c2d_bytes": u16(raw, 8),
        "generation": u16(raw, 10),
        "image_count": u16(raw, 12),
        "entry_count": u16(raw, 14),
        "resolution_count": u16(raw, 16),
        "images_offset": u16(raw, 18),
        "entries_offset": u16(raw, 20),
        "resolutions_offset": u16(raw, 22),
        "roots_offset": u16(raw, 24),
        "root_count": u16(raw, 26),
        "entry_cursor": u16(raw, 28),
        "resolution_cursor": u16(raw, 30),
        "root_cursor": u16(raw, 32),
        "image_first": u16(raw, 34),
        "entry_first": u16(raw, 36),
        "resolution_first": u16(raw, 38),
        "root_first": u16(raw, 40),
        "phase": raw[42], "finished": raw[43],
        "error": raw[44], "reserved": raw[45],
    }


def derive() -> dict[str, Any]:
    first_red = load(FIRST_RED)
    row = load(ROW)
    elf = bind(ELF)
    decoder = bind(DECODER)
    runtime_source = bind(RUNTIME_SOURCE)
    reset = bind(RESET_DOMAIN)
    media = bind(MEDIA)
    require(elf["sha256"] == ELF_SHA256, "candidate ELF identity drift")
    require(decoder["sha256"] == DECODER_SHA256,
            "candidate decoder source identity drift")
    require(runtime_source["sha256"] == RUNTIME_SOURCE_SHA256,
            "candidate runtime source identity drift")
    require(reset["sha256"] == RESET_DOMAIN_SHA256,
            "candidate reset-domain identity drift")
    require(media["sha256"] == MEDIA_SHA256,
            "candidate media authority drift")
    require(first_red["status"] == "D1-FIRST-RED-E25; SUBMECHANISM-UNDECIDED",
            "first-red predecessor drift")
    require(row["decision_rows"]["decoder-failure"].startswith(
        "error is nonzero"), "decoder decision row drift")

    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    found = {name: truth.symbol(name).value for name in SYMBOLS}
    require(found == SYMBOLS, f"candidate symbol layout drift: {found!r}")
    owners = sorted(section.name for section in truth.sections_at_vma(0xE096))
    require(owners, "sampled PC has no candidate ELF owner")

    source = DECODER.read_text(encoding="utf-8")
    runtime_text = RUNTIME_SOURCE.read_text(encoding="utf-8")
    require("C2_SLICE(02a) uint8_t c2_stream_phase_02a" in source
            and "return fail(c, C2_STREAM_ERR_IO);" in source
            and "c->reserved = 0x2au;" in source,
            "phase-02a provenance source drift")
    require("LISP65_C2_PHASE_02A_SLOT" in runtime_text
            and "LISP65_C2_PHASE_02B_SLOT" in runtime_text,
            "phase-02a/02b dispatch source drift")

    reset_raw = RESET_DOMAIN.read_bytes()
    require(len(reset_raw) == 50816 and reset_raw[:4] == b"C2D\0",
            "reset-domain format drift")
    image_offset = u16(reset_raw, 28)
    image0 = reset_raw[image_offset:image_offset + 32]
    require(len(image0) == 32 and image0[0] == 0 and image0[2] == 0,
            "first immutable image row identity drift")
    image0_counts = {
        "entry_count": u16(image0, 8),
        "resolution_count": u16(image0, 12),
    }
    require(image0_counts["entry_count"] > 0
            and image0_counts["resolution_count"] > 0,
            "first image must advance both phase-02 cursors")

    fields = runtime_fields()
    require(fields["images_offset"] == image_offset,
            "captured/reset image-offset mismatch")
    publication = bytes.fromhex(READS["boot-publication-zp"][2])
    roots = bytes.fromhex(READS["roots-ready-oom-zp"][2])
    runtime_range = bytes.fromhex(READS["c2-boot-runtime"][2])
    state = {
        "journal_count": u16(publication, 0),
        "pending_code": publication[8],
        "pending_roots": u16(roots, 0),
        "ready": roots[2],
        "mem_oom": roots[5],
        "lisp_error_msg": u16(bytes.fromhex(
            READS["pending-error-pointer"][2]), 0),
        "committed_roots": u16(runtime_range, 0),
        "decode_active": u16(runtime_range, 2),
    }

    return {
        "format": FORMAT, "recorded_on": "2026-08-13", "status": STATUS,
        "authority": {
            "authorization": git_bind(AUTHORIZATION_COMMIT, PLAN),
            "capture_contract": bind(ROW), "first_red": bind(FIRST_RED),
            "media_closure": media, "candidate_ELF": elf,
            "candidate_decoder_source": decoder,
            "candidate_runtime_source": runtime_source,
            "reset_domain": reset, "capture_driver": bind(CAPTURE_DRIVER),
            "result_driver": bind(DRIVER),
            "raw_capture": {"path": CAPTURE.relative_to(ROOT).as_posix(),
                            "sha256": CAPTURE_SHA256},
        },
        "device": {
            "discipline": {"stops": 1, "resumes": 0, "runs": 0,
                           "resets": 0, "tuple_before_memory": True,
                           "CPU_left_stopped": True,
                           "D2_D5_executed": False},
            "tuple": TUPLE, "physical_bank0": captured_rows(),
            "code_identity": {"sampled_PC": "0xe096",
                              "candidate_ELF_owners": owners,
                              "classification": "bound fail-loop context"},
        },
        "decoded_state": {"publication": state, "c2_runtime": fields},
        "first_pair_authority": {
            "reset_domain_image_offset": f"0x{image_offset:04x}",
            "image_ordinal": 0, "source_kind": image0[0],
            "source_ordinal": image0[2], **image0_counts,
            "inference": (
                "both captured phase-02 cursors are zero while image 0 would "
                "advance both; no image pair completed before the IO failure"),
        },
        "decision": {
            "selected_row": "decoder-failure",
            "decoder_cutpoint": "c2_stream_phase_02a:first-image-pair",
            "error": {"value": 1, "name": "C2_STREAM_ERR_IO"},
            "publication_excluded": True,
            "mechanism_space": [
                "first Shelf record read did not converge",
                "first C2D image-row read did not converge",
                "the product image reader rejected the first target row or its Shelf cross-read",
            ],
            "result": (
                "E25 is an early decoder phase-02a IO failure on image 0, "
                "before roots, publication, journal activity or READY"),
        },
        "exonerations": [
            "c2_publish_exports_from was not reached",
            "no export publication or rollback journal activity occurred",
            "no allocator OOM was present",
            "D2-D5 were not executed",
        ],
        "claim_limit": (
            "The authorised row selects decoder phase 02a and its first image "
            "pair.  It does not distinguish the two convergence reads from "
            "the image-reader validation returns that share C2_STREAM_ERR_IO; "
            "it authorizes no fix, repeat boot, resume, D2-D5 or release claim."),
    }


def validate(value: dict[str, Any]) -> None:
    require(value.get("format") == FORMAT and value.get("status") == STATUS,
            "E25 device-result identity drift")
    discipline = value["device"]["discipline"]
    require(discipline == {
        "stops": 1, "resumes": 0, "runs": 0, "resets": 0,
        "tuple_before_memory": True, "CPU_left_stopped": True,
        "D2_D5_executed": False}, "stopped-state discipline drift")
    require(value["device"]["tuple"] == TUPLE, "captured tuple drift")
    require(value["device"]["physical_bank0"] == captured_rows(),
            "captured physical rows drift")
    state = value["decoded_state"]
    require(state["publication"] == {
        "journal_count": 0, "pending_code": 0x25,
        "pending_roots": 0, "ready": 0, "mem_oom": 0,
        "lisp_error_msg": 0xB988, "committed_roots": 0,
        "decode_active": 0xC084}, "publication-state decode drift")
    runtime = state["c2_runtime"]
    require(runtime["phase"] == 2 and runtime["finished"] == 0
            and runtime["error"] == 1 and runtime["reserved"] == 0,
            "decoder terminal tuple drift")
    require(runtime["entry_cursor"] == 0
            and runtime["resolution_cursor"] == 0,
            "phase-02 cursor provenance drift")
    first = value["first_pair_authority"]
    require(first["image_ordinal"] == 0 and first["source_ordinal"] == 0
            and first["entry_count"] > 0
            and first["resolution_count"] > 0,
            "first-image authority drift")
    decision = value["decision"]
    require(decision["selected_row"] == "decoder-failure"
            and decision["decoder_cutpoint"]
            == "c2_stream_phase_02a:first-image-pair"
            and decision["error"] == {
                "value": 1, "name": "C2_STREAM_ERR_IO"}
            and decision["publication_excluded"] is True,
            "E25 decision drift")
    require(len(decision["mechanism_space"]) == 3
            and "does not distinguish" in value["claim_limit"]
            and "no fix" in value["claim_limit"],
            "claim boundary widened")


def mutations() -> dict[str, Callable[[dict[str, Any]], None]]:
    return {
        "wrong-E25": lambda x: x["decoded_state"]["publication"].update(
            pending_code=0x24),
        "publish-ready": lambda x: x["decoded_state"]["publication"].update(
            ready=1),
        "invent-roots": lambda x: x["decoded_state"]["publication"].update(
            committed_roots=1),
        "invent-journal": lambda x: x["decoded_state"]["publication"].update(
            journal_count=1),
        "invent-OOM": lambda x: x["decoded_state"]["publication"].update(
            mem_oom=1),
        "successful-phase": lambda x: x["decoded_state"]["c2_runtime"].update(
            phase=13, finished=1, error=0),
        "phase-02b-marker": lambda x: x["decoded_state"]["c2_runtime"].update(
            reserved=0x2A),
        "advance-entry": lambda x: x["decoded_state"]["c2_runtime"].update(
            entry_cursor=1),
        "zero-first-count": lambda x: x["first_pair_authority"].update(
            entry_count=0),
        "claim-publication": lambda x: x["decision"].update(
            selected_row="export-publication-failure"),
        "collapse-mechanisms": lambda x: x["decision"].update(
            mechanism_space=x["decision"]["mechanism_space"][:1]),
        "resume": lambda x: x["device"]["discipline"].update(resumes=1),
        "open-D2-D5": lambda x: x["device"]["discipline"].update(
            D2_D5_executed=True),
    }


def selftest(base: dict[str, Any]) -> None:
    rejected = []
    for name, mutate in mutations().items():
        candidate = deepcopy(base)
        mutate(candidate)
        try:
            validate(candidate)
        except (ResultError, KeyError, TypeError):
            rejected.append(name)
    require(rejected == list(mutations()), f"mutation survived: {rejected}")


def verify_capture() -> None:
    require(bind(CAPTURE)["sha256"] == CAPTURE_SHA256,
            "raw E25 capture identity drift")
    value = load(CAPTURE)
    require(value["tuple"] == TUPLE, "raw capture tuple drift")
    require(value["discipline"] == {
        "stops": 1, "resumes": 0, "runs": 0, "resets": 0,
        "tuple_before_memory": True, "CPU_left_stopped": True,
        "D2_D5_executed": False}, "raw capture discipline drift")
    observed = {
        item["name"]: {"physical_address": item["physical_address"],
                       "bytes": item["bytes"],
                       "observed_hex": item["observed_hex"]}
        for item in value["reads"]
    }
    require(observed == captured_rows(), "raw capture physical rows drift")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) == 2 else ""
    require(action in {"record", "check", "selftest"},
            "usage: c2_v20_map_tuple_d1_e25_result.py record|check|selftest")
    value = derive()
    validate(value)
    selftest(value)
    if action == "record":
        verify_capture()
        RECEIPT.write_bytes(canonical(value))
    elif action == "check":
        require(load(RECEIPT) == value, "persisted E25 device receipt stale")
    print("v2.0 E25 device result: PASS "
          f"decoder=02a/image0 mutations={len(mutations())}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ResultError, OSError, ValueError, KeyError, TypeError,
            struct.error, subprocess.CalledProcessError) as error:
        print(f"v2.0 E25 device result: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
