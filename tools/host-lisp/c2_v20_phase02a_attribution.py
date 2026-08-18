#!/usr/bin/env python3
"""Attribute the Link-v2.0 phase-02a E25 as far as host evidence permits.

The stopped-state row records only the decoder cutpoint.  This gate binds the
three delivered call sites, replays image zero from the shipped Shelf/C2D
bytes, prices the convergence wait against the recorded L10 envelope, and
audits the source-byte oracle used by both convergence transports.  It does
not turn a structural verifier defect into a claim about the unrecorded last
descriptor: one read-only row remains specified for that final distinction.
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
PREDECESSOR = EVIDENCE / "c2.3-v2.0-map-tuple-d1-e25-device-receipt.json"
RECEIPT = EVIDENCE / "c2.3-v2.0-phase02a-read-attribution-receipt.json"
ROW = ROOT / "config/c2-v20-phase02a-convergence-site-row.json"
ELF = ROOT / (
    "build/c2.3/v2.0-map-tuple-fix-replacement-card/final/"
    "lisp65-c2-substitution-linked.prg.elf")
DECODER = ROOT / (
    "build/c2.3/v2.0-map-tuple-fix-replacement-card/final/"
    "generated-product-sources/c2-stream-decoder.c")
RUNTIME = ROOT / (
    "build/c2.3/v2.0-map-tuple-fix-replacement-card/final/"
    "generated-product-sources/c2_product_runtime.c")
ASM = ROOT / "src/c2_mapped_far_convergence.s"
D700 = ROOT / "src/c2_platform_dma.c"
DMA_HEADER = ROOT / "src/c2_platform_dma.h"
SHELF = ROOT / (
    "build/c2.3/v2.0-map-tuple-fix-replacement-card/static-plane/"
    "narrow-static/product/product-shelf-v4-direct.bin")
C2D = ROOT / (
    "build/c2.3/v2.0-map-tuple-media/shared-system/"
    "c2d-v6-reset-domain.bin")
L10 = EVIDENCE / "c2.2-v1.2.4-phase-m-hardware-receipt.json"
D700_CURVE = EVIDENCE / (
    "c2.2-v1.2.4-chipram-visibility-curve-hardware-receipt.json")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
DRIVER = Path(__file__).resolve()

FORMAT = "lisp65-c2.3-v20-phase02a-read-attribution-v1"
STATUS = "HOST-NARROWED-TO-CONVERGENCE-ORACLE; EXACT-SITE-ROW-REQUIRED"
AUTHORIZATION_COMMIT = "f81127ca"

EXPECTED_IDENTITIES = {
    "candidate_ELF": "a481eff4acd32f04dde6660090aa2761a2f4a4b6307945cbcb2cda0f70435673",
    "decoder": "56af9971943bc263d7dbf84b06750aaca655ba05ab9e5f2a27af98aa72b8732e",
    "runtime": "f187612a73d501733a3407b117fb16164719b1377199b9d219481aa28c90a692",
    "assembler": "697fcc294e30512ccf62255f80ae79c3a75d9bd0ef6bc79c5f920903effcb166",
    "d700_source": "0e58051fd8ecc7780c03172d966b1ac621260705df47aa3350b1300fdc3e87cf",
    "dma_header": "4501703d7d85f78b8c48f76b55826ed1d0f6ecd5a2cb404e3c0a15d838d93b6d",
    "shelf": "0924fff5a35d2c72e830e90a949ba5f70a9937e17378db1f39a49844f31a795c",
    "c2d": "3010ec3807409338d119c57444c960d67f306a5b978ac346d5ed7ab119beee29",
    "L10": "b821f41a37426b97c701256f0b0abebf3e76196264210c756a697c639cadc724",
    "D700_curve": "d58b12e60176237978ee6e1772c6324d341aa4ae16d0ebed04a674a4f095f6ba",
    "predecessor": "9f729d35a2e1bcee4a8abca25f58478822d09f268bcae024523edf39e97dfc6a",
}

SYMBOLS = {
    "c2_dma_verify_done": (0x0087, 1),
    "c2_edma_probe_done": (0x0088, 1),
    "c2_dma_list": (0xB9D3, 12),
    "c2_dma_verify_list": (0xC000, 24),
    "c2_edma_probe_jobs": (0xC019, 40),
    "c2_edma_probe_value": (0xC041, 1),
    "c2_edma_job": (0xC0B2, 20),
    "c2_stream_phase_02a": (0xC356, 1665),
    "c2_stream_c2d_read": (0xE2DD, 86),
    "c2_stream_product_image_read": (0xE333, 1131),
    "c2_stream_shelf_read": (0xE79E, 194),
}


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


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


def exact_identity(name: str, path: Path) -> dict[str, Any]:
    value = bind(path)
    require(value["sha256"] == EXPECTED_IDENTITIES[name],
            f"{name} identity drift")
    return value


def require_in_order(text: str, tokens: list[str], label: str) -> None:
    cursor = -1
    for token in tokens:
        found = text.find(token, cursor + 1)
        require(found >= 0, f"{label} token absent: {token}")
        require(found > cursor, f"{label} token order drift: {token}")
        cursor = found


def media_model() -> dict[str, Any]:
    shelf = SHELF.read_bytes()
    c2d = C2D.read_bytes()
    require(len(shelf) == 93681, "Shelf byte count drift")
    require(len(c2d) == 50816 and c2d[:4] == b"C2D\0",
            "C2D reset-domain shape drift")
    image_offset = u16(c2d, 28)
    require(image_offset == 48, "C2D image offset drift")
    s = shelf[32:64]
    raw = c2d[image_offset:image_offset + 32]
    require(s.hex() == (
        "7374646c69620000e000005643bbb400264f0bce232ca686df848bcdaef60100"),
        "Shelf image-zero record drift")
    require(raw.hex() == (
        "000000000100000089010000a90300004400000000564300000000002d4b7172"),
        "C2D image-zero record drift")

    checks = {
        "kind_static": raw[0] == 0,
        "reserved_zero": raw[1] == 0 and raw[3] == 0,
        "source_ordinal_zero": raw[2] == 0,
        "generation_one": u16(raw, 4) == 1,
        "entry_first_zero": u16(raw, 6) == 0,
        "entry_count_393": u16(raw, 8) == 393,
        "resolution_first_zero": u16(raw, 10) == 0,
        "resolution_count_937": u16(raw, 12) == 937,
        "shelf_flags_valid": s[30] == 1 and s[31] == 0,
        "code_length_cross_bound": u16(s, 11) == u16(raw, 21),
        "code_in_bounds": u24(s, 8) + u16(s, 11) <= len(shelf),
        "metadata_in_bounds": u24(s, 13) + u16(s, 16) <= len(shelf),
    }
    require(all(checks.values()), "first image-pair semantic model is red")
    normalized = bytes((
        0, 0, raw[6], raw[7], raw[8], raw[9], raw[10], raw[11],
        raw[12], raw[13], s[8], s[9], s[10], s[13], s[14], s[15],
        raw[21], raw[22], s[16], s[17]))
    require(normalized.hex() == "0000000089010000a903e00000bbb4005643264f",
            "normalized image-zero view drift")
    return {
        "shelf_record_offset": 32,
        "c2d_record_offset": image_offset,
        "shelf_record_hex": s.hex(),
        "c2d_record_hex": raw.hex(),
        "normalized_20_byte_hex": normalized.hex(),
        "semantic_checks": checks,
        "result": "all image-reader and phase-02a layout checks pass",
    }


def latency_model() -> dict[str, Any]:
    l10 = load(L10)
    curve = l10["M2_L10"]["captures"]
    require([(x["elapsed_after_launch_ms"], x["nonmatching_bytes"])
             for x in curve] == [(2, 1132), (714, 0), (2414, 0)],
            "L10 curve drift")
    hz = float(l10["M4_time"]["frames_per_second"])
    require(abs(hz - 51.96615805290813) < 1e-12,
            "hardware frame-rate authority drift")
    timeout_frames = 64
    timeout_ms = timeout_frames * 1000.0 / hz
    margin_ms = timeout_ms - 714.0
    require(timeout_ms > 714.0 and margin_ms > 500.0,
            "bounded wait no longer exceeds recorded L10 convergence")
    d700 = load(D700_CURVE)
    measurement = d700["measurement"]
    require(measurement["immediate_repetitions"] == 20
            and measurement["immediate_mismatch_cycles"] == 0
            and measurement["curve_mismatch_points"] == 0,
            "D700 bounded-exoneration curve drift")
    return {
        "timeout_frames": timeout_frames,
        "measured_frame_hz": hz,
        "timeout_ms": round(timeout_ms, 3),
        "L10_D705_first_exact_ms": 714,
        "known_envelope_margin_ms": round(margin_ms, 3),
        "D700_immediate_exact_cycles": 20,
        "interpretation": (
            "the 64-frame wait exceeds the recorded D705 convergence point; "
            "a genuine >64-frame boot-cold event is not observed by these "
            "receipts and cannot be promoted from speculation"),
        "claim_limit": (
            "historical timing bounds do not prove that every future transfer "
            "converges within the bound"),
    }


def stale_oracle_model(shelf: bytes) -> dict[str, Any]:
    # Phase 01's catalog CRC reads six 32-byte rows.  Its final successful
    # source probe therefore leaves the final byte of row 5 in the shared
    # one-byte probe slot.  Phase 02a starts again at row 0.
    prior_probe = shelf[32 + 6 * 32 - 1]
    actual = shelf[32]
    require((prior_probe, actual) == (0x00, 0x73),
            "media-derived stale-oracle witness drift")
    retained_expected = prior_probe
    primary_destination_after_convergence = actual
    false_timeout = primary_destination_after_convergence != retained_expected
    require(false_timeout, "stale oracle no longer distinguishes real content")
    return {
        "previous_successful_Shelf_probe_byte": prior_probe,
        "next_phase02a_Shelf_source_byte": actual,
        "marker_visible_while_probe_value_stale": True,
        "retained_expected_byte": retained_expected,
        "primary_destination_after_real_convergence":
            primary_destination_after_convergence,
        "verifier_waits_for_stale_expected_until_timeout": false_timeout,
        "result": (
            "the delivered verifier can reject a correctly converged primary "
            "copy because its expected byte is itself marker-only"),
        "claim_limit": (
            "this deterministic host trace proves the defect and reproduces "
            "its failure shape; the stopped capture did not retain the probe "
            "value/descriptor needed to assert that this exact interleaving "
            "occurred in the device run"),
    }


def source_audit() -> dict[str, Any]:
    decoder = DECODER.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    asm = ASM.read_text(encoding="utf-8")
    d700 = D700.read_text(encoding="utf-8")
    dma_header = DMA_HEADER.read_text(encoding="utf-8")

    require_in_order(decoder, [
        "C2_SLICE(00) uint8_t c2_stream_phase_00",
        "c2_stream_c2d_read(0, h, sizeof(h))",
        "C2_SLICE(00b) uint8_t c2_stream_phase_00b",
        "c2_stream_c2d_read(0, h, sizeof(h))",
        "C2_SLICE(01) uint8_t c2_stream_phase_01",
        "c2_stream_shelf_read(0, h, sizeof(h))",
        "shelf_crc32(32u, catalog, &crc)",
        "c->phase = 2; return C2_STREAM_OK;",
        "C2_SLICE(02a) uint8_t c2_stream_phase_02a",
        "c2_stream_shelf_read(32u + (uint32_t)i * 32u, s, sizeof(s))",
        "|| !c2_image_read(c, i, d)",
        "return fail(c, C2_STREAM_ERR_IO);",
    ], "decoder call order")
    require_in_order(runtime, [
        "C2_KERNAL_RESIDENT uint8_t c2_stream_product_image_read",
        "c2_stream_c2d_read((uint16_t)(c->images_offset + image * 32u)",
        "if (raw[0] == 0u)",
        "c2_stream_shelf_read(32u + (uint32_t)raw[2] * 32u",
        "source[30] != 1u || source[31]",
        "c2_u16(source + 11) != c2_u16(raw + 21)",
    ], "product image-reader order")
    require_in_order(runtime, [
        "c2_edma_prepare(first, source,",
        "&c2_edma_probe_value",
        "c2_edma_prepare(second,",
        "&c2_edma_probe_marker",
        "&c2_edma_probe_done",
        "while (c2_edma_probe_done != c2_edma_probe_marker)",
        "*value = c2_edma_probe_value;",
    ], "D705 marker-only source oracle")
    require_in_order(d700, [
        "uint8_t *next = c2_dma_verify_list + 12u;",
        "c2_dma_verify_list[0] = 4u;",
        "&c2_dma_verify_marker",
        "&c2_dma_verify_done",
        "while (c2_dma_verify_done != c2_dma_verify_marker)",
        "*value = c2_dma_verify;",
    ], "D700 marker-only source oracle")
    require_in_order(asm, [
        ".Lc2_d705_source_byte:",
        "jsr .Lc2_d705_trigger_probe",
        ".Lc2_d705_probe_wait:",
        "cmp #C2_MARKER",
        ".Lc2_d705_probe_ok:",
        "lda c2_edma_probe_value",
        "sta __rc27",
        ".Lc2_d705_primary:",
        ".Lc2_d705_primary_wait:",
        "cmp __rc27",
    ], "linked D705 assembler oracle")
    require("#define C2_DMA_CONTENT_TIMEOUT_FRAMES 64u" in dma_header,
            "content timeout definition drift")
    return {
        "phase00_D700_header_read": True,
        "phase00b_D700_header_reread": True,
        "phase01_D705_header_and_catalog_reads": True,
        "phase01_reads_Shelf_record0": True,
        "captured_phase2_proves_prior_phases_returned": True,
        "boot_cold_first_service_read": False,
        "phase02a_candidates": [
            {
                "site": "phase02a outer Shelf record 0",
                "transport": "$D705",
                "source": "0x08100020",
                "length": 32,
            },
            {
                "site": "image-reader C2D image row 0",
                "transport": "$D700",
                "source": "Bank 5 offset 0x0030",
                "length": 32,
            },
            {
                "site": "image-reader Shelf cross-read record 0",
                "transport": "$D705",
                "source": "0x08100020",
                "length": 32,
            },
        ],
        "D700_expected_byte_oracle": "chained marker-only probe",
        "D705_expected_byte_oracle": "chained marker-only probe",
        "primary_wait_compares_against_probe_byte": True,
        "structural_defect": (
            "the expected-content oracle consumes completion metadata before "
            "the oracle byte has independently converged"),
    }


def derive() -> dict[str, Any]:
    predecessor = load(PREDECESSOR)
    row = load(ROW)
    require(predecessor["status"] == "D1-E25-DECODER-IO-PHASE-02A-IMAGE0",
            "predecessor cutpoint drift")
    runtime_state = predecessor["decoded_state"]["c2_runtime"]
    require(runtime_state["phase"] == 2 and runtime_state["error"] == 1
            and runtime_state["entry_cursor"] == 0
            and runtime_state["resolution_cursor"] == 0,
            "predecessor phase-02a tuple drift")
    require(row["status"] == "host-specified-owner-authorization-pending"
            and "specified, not authorized" in row["claim_limit"],
            "site-row authorization boundary drift")

    authorities = {
        "commission": git_bind(AUTHORIZATION_COMMIT, PLAN),
        "predecessor": exact_identity("predecessor", PREDECESSOR),
        "candidate_ELF": exact_identity("candidate_ELF", ELF),
        "decoder": exact_identity("decoder", DECODER),
        "runtime": exact_identity("runtime", RUNTIME),
        "assembler": exact_identity("assembler", ASM),
        "D700_source": exact_identity("d700_source", D700),
        "DMA_header": exact_identity("dma_header", DMA_HEADER),
        "Shelf": exact_identity("shelf", SHELF),
        "C2D": exact_identity("c2d", C2D),
        "L10": exact_identity("L10", L10),
        "D700_curve": exact_identity("D700_curve", D700_CURVE),
        "specified_row": bind(ROW),
        "driver": bind(DRIVER),
    }

    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    symbols = {}
    for name, (address, size) in SYMBOLS.items():
        symbol = truth.symbol(name)
        require((symbol.value, symbol.bytes) == (address, size),
                f"linked symbol drift: {name}")
        symbols[name] = {"address": f"0x{address:04x}", "bytes": size,
                         "section": symbol.section}

    media = media_model()
    latency = latency_model()
    audit = source_audit()
    oracle = stale_oracle_model(SHELF.read_bytes())

    return {
        "format": FORMAT,
        "recorded_on": "2026-08-13",
        "status": STATUS,
        "authority": authorities,
        "linked_symbols": symbols,
        "captured_cutpoint": {
            "phase": 2,
            "error": {"value": 1, "name": "C2_STREAM_ERR_IO"},
            "image": 0,
            "entry_cursor": 0,
            "resolution_cursor": 0,
        },
        "delivered_call_graph": audit,
        "first_image_pair_model": media,
        "latency_envelope": latency,
        "verifier_oracle_model": oracle,
        "decision": {
            "media_layout_checker": "EXONERATED",
            "true_timeout_under_recorded_envelope": "NOT-SUPPORTED",
            "verifier_oracle": "STRUCTURALLY-RED",
            "nature": "completion-marker-consumed-as-expected-content",
            "exact_site": "UNRESOLVED-BY-EXISTING-CAPTURE",
            "remaining_sites": [
                "phase02a outer D705 Shelf read",
                "image-reader D700 C2D image-row read",
                "image-reader inner D705 Shelf cross-read",
            ],
            "specified_next_evidence":
                ROW.relative_to(ROOT).as_posix(),
            "result": (
                "the shipped image bytes and their reader checks are correct; "
                "both convergence families derive their expected byte through "
                "an un-converged marker-only probe, which can turn a correct "
                "primary copy into C2_STREAM_ERR_IO. The existing stopped row "
                "did not capture the last descriptors, so it cannot identify "
                "which of the three calls emitted this instance."),
        },
        "claim_limit": (
            "Host evidence names a verifier-oracle defect and refutes the new-"
            "layout checker hypothesis. It does not prove the exact last call "
            "or the device interleaving, does not claim that every transfer "
            "fits 64 frames, and authorizes no fix, device access, repeat boot, "
            "resume, D2-D5 or release action. The one specified read-only row "
            "is the commissioned exit when host evidence cannot name the site."),
    }


def validate(value: dict[str, Any]) -> None:
    require(value.get("format") == FORMAT and value.get("status") == STATUS,
            "phase-02a attribution identity drift")
    cut = value["captured_cutpoint"]
    require(cut == {
        "phase": 2,
        "error": {"value": 1, "name": "C2_STREAM_ERR_IO"},
        "image": 0,
        "entry_cursor": 0,
        "resolution_cursor": 0,
    }, "captured cutpoint widened")
    graph = value["delivered_call_graph"]
    require(graph["boot_cold_first_service_read"] is False
            and graph["phase01_reads_Shelf_record0"] is True
            and len(graph["phase02a_candidates"]) == 3,
            "prior-read/candidate binding drift")
    require(graph["D700_expected_byte_oracle"] == "chained marker-only probe"
            and graph["D705_expected_byte_oracle"]
            == "chained marker-only probe"
            and graph["primary_wait_compares_against_probe_byte"] is True,
            "verifier-oracle defect lost")
    media = value["first_image_pair_model"]
    require(all(media["semantic_checks"].values())
            and media["result"]
            == "all image-reader and phase-02a layout checks pass",
            "media-reader exoneration drift")
    latency = value["latency_envelope"]
    require(latency["timeout_frames"] == 64
            and latency["L10_D705_first_exact_ms"] == 714
            and latency["timeout_ms"] > 1200
            and latency["known_envelope_margin_ms"] > 500,
            "latency-envelope interpretation drift")
    oracle = value["verifier_oracle_model"]
    require(oracle["previous_successful_Shelf_probe_byte"] == 0
            and oracle["next_phase02a_Shelf_source_byte"] == 0x73
            and oracle["marker_visible_while_probe_value_stale"] is True
            and oracle["retained_expected_byte"] == 0
            and oracle["primary_destination_after_real_convergence"] == 0x73
            and oracle["verifier_waits_for_stale_expected_until_timeout"]
            is True,
            "stale expected-byte model drift")
    decision = value["decision"]
    require(decision["media_layout_checker"] == "EXONERATED"
            and decision["true_timeout_under_recorded_envelope"]
            == "NOT-SUPPORTED"
            and decision["verifier_oracle"] == "STRUCTURALLY-RED"
            and decision["nature"]
            == "completion-marker-consumed-as-expected-content"
            and decision["exact_site"] == "UNRESOLVED-BY-EXISTING-CAPTURE"
            and decision["remaining_sites"] == [
            "phase02a outer D705 Shelf read",
            "image-reader D700 C2D image-row read",
            "image-reader inner D705 Shelf cross-read",
            ]
            and decision["specified_next_evidence"]
            == "config/c2-v20-phase02a-convergence-site-row.json"
            and decision["result"].startswith(
                "the shipped image bytes and their reader checks are correct"),
            "decision table widened")
    require("authorizes no fix" in value["claim_limit"]
            and "does not prove the exact last call" in value["claim_limit"],
            "claim limit widened")


def mutations() -> dict[str, Callable[[dict[str, Any]], None]]:
    return {
        "call-it-first-service-read": lambda x: x["delivered_call_graph"].update(
            boot_cold_first_service_read=True),
        "forget-prior-Shelf-record0": lambda x: x["delivered_call_graph"].update(
            phase01_reads_Shelf_record0=False),
        "drop-call-site": lambda x: x["delivered_call_graph"].update(
            phase02a_candidates=x["delivered_call_graph"]["phase02a_candidates"][:2]),
        "bless-D700-marker": lambda x: x["delivered_call_graph"].update(
            D700_expected_byte_oracle="content-converged probe"),
        "bless-D705-marker": lambda x: x["delivered_call_graph"].update(
            D705_expected_byte_oracle="content-converged probe"),
        "disconnect-primary-oracle": lambda x: x["delivered_call_graph"].update(
            primary_wait_compares_against_probe_byte=False),
        "invent-layout-error": lambda x: x["first_image_pair_model"].update(
            result="image-reader layout mismatch"),
        "dim-semantic-field": lambda x: x["first_image_pair_model"][
            "semantic_checks"].update(code_length_cross_bound=False),
        "short-timeout": lambda x: x["latency_envelope"].update(
            timeout_frames=32),
        "move-L10-point": lambda x: x["latency_envelope"].update(
            L10_D705_first_exact_ms=1414),
        "erase-envelope-margin": lambda x: x["latency_envelope"].update(
            known_envelope_margin_ms=0),
        "erase-stale-probe": lambda x: x["verifier_oracle_model"].update(
            marker_visible_while_probe_value_stale=False),
        "make-probe-correct": lambda x: x["verifier_oracle_model"].update(
            retained_expected_byte=0x73),
        "make-false-timeout-pass": lambda x: x["verifier_oracle_model"].update(
            verifier_waits_for_stale_expected_until_timeout=False),
        "blame-layout": lambda x: x["decision"].update(
            media_layout_checker="RED"),
        "claim-real-timeout": lambda x: x["decision"].update(
            true_timeout_under_recorded_envelope="PROVED"),
        "claim-exact-outer-site": lambda x: x["decision"].update(
            exact_site="phase02a outer D705 Shelf read"),
        "claim-exact-D700-site": lambda x: x["decision"].update(
            exact_site="image-reader D700 C2D image-row read"),
        "rewrite-result": lambda x: x["decision"].update(
            result="the verifier is fine"),
        "authorize-fix": lambda x: x.update(
            claim_limit=x["claim_limit"].replace("authorizes no fix",
                                                  "authorizes a fix")),
    }


def selftest(base: dict[str, Any]) -> None:
    rejected = []
    for name, mutate in mutations().items():
        candidate = deepcopy(base)
        mutate(candidate)
        try:
            validate(candidate)
        except (AttributionError, KeyError, TypeError):
            rejected.append(name)
    require(rejected == list(mutations()), f"mutation survived: {rejected}")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) == 2 else ""
    require(action in {"record", "check", "selftest"},
            "usage: c2_v20_phase02a_attribution.py record|check|selftest")
    value = derive()
    validate(value)
    selftest(value)
    if action == "record":
        RECEIPT.write_bytes(canonical(value))
    elif action == "check":
        require(load(RECEIPT) == value,
                "persisted phase-02a attribution receipt stale")
    print("v2.0 phase-02a attribution: PASS "
          f"nature=marker-oracle exact-site=row-required "
          f"mutations={len(mutations())}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError, TypeError,
            struct.error, subprocess.CalledProcessError) as error:
        print(f"v2.0 phase-02a attribution: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
