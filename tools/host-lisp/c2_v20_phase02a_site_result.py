#!/usr/bin/env python3
"""Bind the raw-first phase-02a convergence-site rescue row.

The preserved descriptors and the linked software-stack geometry identify the
outer phase-02a Shelf read exactly.  The stopped bytes also prove that the
source probe and primary destination eventually converged.  They do not retain
the byte latched by the CPU at the earlier comparison boundary, so the device
instance cannot honestly be split between a stale expected byte and a primary
copy that exceeded the 64-frame bound.  The independently proven verifier
oracle defect remains structural; this receipt neither assigns nor exonerates
it for this one run.
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
ROW = ROOT / "config/c2-v20-phase02a-convergence-site-row.json"
PREDECESSOR = EVIDENCE / "c2.3-v2.0-phase02a-read-attribution-receipt.json"
ELF = ROOT / (
    "build/c2.3/v2.0-map-tuple-fix-replacement-card/final/"
    "lisp65-c2-substitution-linked.prg.elf")
ASM = ROOT / "src/c2_mapped_far_convergence.s"
CAPTURE = ROOT / "build/c2.3/v2.0-map-tuple-d1/phase02a-site-row/capture.json"
CHECKPOINT = ROOT / (
    "build/c2.3/v2.0-map-tuple-d1/phase02a-site-row/static-checkpoint.json")
CAPTURE_DRIVER = ROOT / "tools/host-lisp/c2_v20_phase02a_site_capture.py"
RECEIPT = EVIDENCE / "c2.3-v2.0-phase02a-site-device-receipt.json"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
DRIVER = Path(__file__).resolve()

FORMAT = "lisp65-c2.3-v20-phase02a-site-device-result-v1"
STATUS = "PHASE02A-OUTER-D705-PRIMARY-BOUND-EXCEEDED; LATE-CONVERGENCE"
AUTHORIZATION_COMMIT = "97c4ae61"
CAPTURE_SHA256 = "f76604d44881a97908a5756d040b3075ddf805a2067dac3f04475ffd129f216f"
CHECKPOINT_SHA256 = "b2ed8e93e48bc0fdc1ea1d6e4d29aa4cccabfd2b99e5c7d89deb593460747c78"
ELF_SHA256 = "a481eff4acd32f04dde6660090aa2761a2f4a4b6307945cbcb2cda0f70435673"
ROW_SHA256 = "1699c0e8522dca71f45a1b9abcf7181cc6c0ab3cdaa18a89989a1fcd2e67d9ab"
PREDECESSOR_SHA256 = "49bb0fb031905e2829ced621449314e00a56dbc7dc3721666ebb536fabde8b5d"
ASM_SHA256 = "697fcc294e30512ccf62255f80ae79c3a75d9bd0ef6bc79c5f920903effcb166"

TUPLE = {
    "PC": "0xe096", "A": "0x02", "X": "0x64", "Y": "0x01",
    "Z": "0x00", "B": "0x00", "SP": "0x01e4",
    "MAPH": "0x8000", "MAPL": "0x0000",
    "suffix": "4C96E0  00     04 .....I.. ...P 15 -  00 - ..c..lhc",
}

STATIC = {
    "compiler-static-stack-and-pseudo-registers": (
        0x0002, 30, "00d0190000cf03b60000b99201c904000100532d00186220001008731a00"),
    "convergence-done-markers": (0x0087, 2, "a5a5"),
    "D700-primary-descriptor": (0xB9D3, 12, "002000000003a3cf00000000"),
    "D700-source-probe-descriptors": (
        0xC000, 24, "04010024000518c0000000000001002eb700870000000000"),
    "D705-source-probe-descriptors-and-value": (
        0xC019, 41,
        "0b8081810085010004010020000041c000000000"
        "0b800081008501000001002fb70088000000000073"),
    "D705-primary-descriptor": (
        0xC0B2, 20, "0b808181008501000020002000006dcf00000000"),
}

DYNAMIC = {
    "first-difference-target": (0x0000CF6D, 1, "73"),
    "immutable-source": (0x08100020, 1, "73"),
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


def exact(path: Path, expected: str, label: str) -> dict[str, Any]:
    value = bind(path)
    require(value["sha256"] == expected, f"{label} identity drift")
    return value


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    require(b"raw-first rule" in raw and b"without a further `t1`" in raw,
            "raw-first authorization language absent")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": sha(raw)}


def edma(raw: bytes) -> dict[str, int]:
    require(len(raw) == 20, "Enhanced-DMA descriptor length drift")
    return {
        "command": raw[8], "length": struct.unpack_from("<H", raw, 9)[0],
        "source": (raw[11] | raw[12] << 8 | (raw[13] & 0x0F) << 16
                   | raw[2] << 20),
        "target": (raw[14] | raw[15] << 8 | (raw[16] & 0x0F) << 16
                   | raw[4] << 20),
    }


def d700(raw: bytes) -> dict[str, int]:
    require(len(raw) == 12, "ordinary-DMA descriptor length drift")
    return {
        "command": raw[0], "length": struct.unpack_from("<H", raw, 1)[0],
        "source": raw[3] | raw[4] << 8 | raw[5] << 16,
        "target": raw[6] | raw[7] << 8 | raw[8] << 16,
    }


def captured_rows(rows: dict[str, tuple[int, int, str]]) -> dict[str, Any]:
    return {name: {"physical_address": f"0x{address:08x}", "bytes": count,
                   "observed_hex": observed}
            for name, (address, count, observed) in rows.items()}


def symbol_bytes(truth: ElfTruth, name: str) -> bytes:
    symbol = truth.symbol(name)
    section = truth.section(symbol.section)
    raw = truth.section_bytes(symbol.section)
    offset = symbol.value - section.address
    require(0 <= offset and offset + symbol.bytes <= len(raw),
            f"symbol bytes escape section: {name}")
    return raw[offset:offset + symbol.bytes]


def linked_geometry(truth: ElfTruth) -> dict[str, Any]:
    expected = {
        "main": (0xA423, 613),
        "c2_facade_target_overlay_call_family": (0x2473, 88),
        "vm_runtime_overlay_exec_family": (0x281F, 1262),
        "c2_stream_phase_02a": (0xC356, 1665),
        "c2_stream_product_image_read": (0xE333, 1131),
        "c2_stream_shelf_read": (0xE79E, 194),
        "c2_physical_read_converged": (0xB3B9, 9),
        "c2_mapped_far_physical_read_converged": (0x7BBA, 98),
        "__rc27": (0x001D, 0),
    }
    symbols = {}
    for name, identity in expected.items():
        row = truth.symbol(name)
        require((row.value, row.bytes) == identity,
                f"linked symbol drift: {name}")
        symbols[name] = {"address": f"0x{row.value:04x}",
                         "bytes": row.bytes, "section": row.section}

    main = symbol_bytes(truth, "main")
    target = symbol_bytes(truth, "c2_facade_target_overlay_call_family")
    runtime = symbol_bytes(truth, "vm_runtime_overlay_exec_family")
    phase = symbol_bytes(truth, "c2_stream_phase_02a")
    image = symbol_bytes(truth, "c2_stream_product_image_read")
    require(main[:12].hex() == "18a50269d08502a50369ff85",
            "main -48-byte frame encoding drift")
    require(target[1:14].hex() == "18a50269ff8502a50369ff8503",
            "target-facade -1-byte frame encoding drift")
    require(runtime[1:14].hex() == "18a50269be8502a50369ff8503",
            "runtime-overlay -66-byte frame encoding drift")
    require(phase[0x38:0x45].hex() == "18a50269b88502a50369ff8503",
            "phase-02a -72-byte frame encoding drift")
    require(phase[0xF6:0x102].hex() == "a50269288506a50369008507",
            "phase-02a outer-buffer +40 encoding drift")
    require(image[1:14].hex() == "18a50269bb8502a50369ff8503",
            "image-reader -69-byte frame encoding drift")
    require(image[0x2AB:0x2B7].hex() == "a50269058516a50369008517",
            "image-reader inner-buffer +5 encoding drift")

    initial = 0xD000
    main_frame = (initial - 48) & 0xFFFF
    facade_frame = (main_frame - 1) & 0xFFFF
    runtime_frame = (facade_frame - 66) & 0xFFFF
    phase_frame = (runtime_frame - 72) & 0xFFFF
    outer = (phase_frame + 40) & 0xFFFF
    inner = (phase_frame - 69 + 5) & 0xFFFF
    require((main_frame, facade_frame, runtime_frame, phase_frame,
             outer, inner) == (0xCFD0, 0xCFCF, 0xCF8D, 0xCF45,
                               0xCF6D, 0xCF05),
            "linked software-stack geometry drift")
    return {
        "symbols": symbols,
        "initial_static_stack": "0xd000",
        "frame_deltas": {
            "main": -48, "target_facade": -1,
            "runtime_overlay_exec_family": -66, "phase02a": -72,
            "image_reader_if_reached": -69,
        },
        "outer_Shelf_target": "0xcf6d",
        "inner_image_reader_Shelf_target": "0xcf05",
        "target_separation_bytes": 104,
        "proof": (
            "the retained D705 primary target equals the linked outer local "
            "buffer exactly and differs from the inner call's linked target "
            "by 104 bytes"),
    }


def derive() -> dict[str, Any]:
    predecessor = load(PREDECESSOR)
    require(predecessor["decision"]["verifier_oracle"] == "STRUCTURALLY-RED",
            "structural verifier-oracle predecessor drift")
    authority = {
        "authorization": git_bind(AUTHORIZATION_COMMIT, PLAN),
        "site_row": exact(ROW, ROW_SHA256, "site row"),
        "predecessor": exact(PREDECESSOR, PREDECESSOR_SHA256, "predecessor"),
        "candidate_ELF": exact(ELF, ELF_SHA256, "candidate ELF"),
        "assembler": exact(ASM, ASM_SHA256, "assembler"),
        "capture_driver": bind(CAPTURE_DRIVER), "result_driver": bind(DRIVER),
        "raw_capture": {"path": CAPTURE.relative_to(ROOT).as_posix(),
                        "bytes": 10728, "sha256": CAPTURE_SHA256},
        "raw_static_checkpoint": {
            "path": CHECKPOINT.relative_to(ROOT).as_posix(),
            "bytes": 8008, "sha256": CHECKPOINT_SHA256},
    }
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    geometry = linked_geometry(truth)

    static = {name: bytes.fromhex(row[2]) for name, row in STATIC.items()}
    markers = static["convergence-done-markers"]
    d700_primary = d700(static["D700-primary-descriptor"])
    d700_rows = static["D700-source-probe-descriptors"]
    d700_probe, d700_marker = d700(d700_rows[:12]), d700(d700_rows[12:])
    d705_rows = static["D705-source-probe-descriptors-and-value"]
    d705_probe, d705_marker = edma(d705_rows[:20]), edma(d705_rows[20:40])
    retained_probe = d705_rows[40]
    d705_primary = edma(static["D705-primary-descriptor"])
    pseudo = static["compiler-static-stack-and-pseudo-registers"]
    stopped_rc27 = pseudo[0x1D - 0x02]

    require(markers == bytes((0xA5, 0xA5)), "done-marker row drift")
    require(d705_probe == {"command": 4, "length": 1,
                           "source": 0x08100020, "target": 0xC041},
            "D705 source-probe descriptor drift")
    require(d705_marker == {"command": 0, "length": 1,
                            "source": 0xB72F, "target": 0x0088},
            "D705 marker descriptor drift")
    require(d705_primary == {"command": 0, "length": 32,
                             "source": 0x08100020, "target": 0xCF6D},
            "D705 primary descriptor drift")
    require(retained_probe == stopped_rc27 == 0x73,
            "stopped probe/pseudo-register value drift")
    require(d700_probe["source"] == 0x00050024
            and d700_primary["source"] == 0x00030000,
            "D700 retained descriptor drift")

    asm = ASM.read_text(encoding="utf-8")
    for token in (
        ".Lc2_d705_probe_ok:", "lda c2_edma_probe_value", "sta __rc27",
        ".Lc2_d705_primary:", ".Lc2_d705_primary_wait:", "cmp __rc27",
        ".Lc2_d705_primary_not_yet:", "jsr .Lc2_far_timed_out",
    ):
        require(token in asm, f"D705 linked-source token absent: {token}")

    return {
        "format": FORMAT, "recorded_on": "2026-08-13", "status": STATUS,
        "authority": authority,
        "contact": {
            "tuple_first": TUPLE,
            "discipline": {"stops": 0, "resumes": 0, "runs": 0,
                           "resets": 0, "tuple_before_memory": True,
                           "raw_persisted_before_interpretation": True,
                           "static_before_dynamic": True,
                           "CPU_left_stopped": True,
                           "D2_D5_executed": False},
            "static_reads": captured_rows(STATIC),
            "dynamic_reads": captured_rows(DYNAMIC),
        },
        "decoded_descriptors": {
            "D700": {"done": markers[0], "probe": d700_probe,
                     "marker": d700_marker, "primary": d700_primary},
            "D705": {"done": markers[1], "probe": d705_probe,
                     "marker": d705_marker, "primary": d705_primary,
                     "retained_probe_at_stop": retained_probe},
            "stopped_pseudo_register_rc27": stopped_rc27,
        },
        "linked_stack_geometry": geometry,
        "late_state": {
            "immutable_source": 0x73,
            "retained_probe_slot": 0x73,
            "primary_first_difference_target": 0x73,
            "all_equal_at_stopped_read": True,
            "interpretation": (
                "the source-probe slot and primary target both converged by "
                "the later stopped-state read"),
        },
        "decision": {
            "exact_site": "phase02a outer D705 Shelf read",
            "source_probe": "completed and primary descriptor was submitted",
            "bounded_failure": "D705 primary comparator exceeded 64 frames",
            "post_timeout_state": "probe and primary later converged to 0x73",
            "device_instance_nature": (
                "UNRESOLVED-BETWEEN-STALE-LATCHED-ORACLE-AND-"
                "GENUINE-PRIMARY-LATENCY"),
            "structural_verifier_oracle": "REMAINS-RED-INDEPENDENTLY",
            "result": (
                "the outer phase-02a Shelf read submitted its primary D705 "
                "copy and returned C2_STREAM_ERR_IO after the comparator's "
                "64-frame bound; both the probe slot and target reached the "
                "correct 0x73 later"),
        },
        "provenance_limit": {
            "retained_probe_slot": (
                "C041 is a DMA destination and may change after the CPU has "
                "latched it"),
            "stopped_rc27": (
                "0x1d is a compiler pseudo-register, not a dedicated shadow "
                "witness; later linked paths may overwrite it"),
            "consequence": (
                "the stopped state does not preserve the expected byte used "
                "at the failed comparison, so it cannot assign this device "
                "instance to stale-oracle versus genuine-latency"),
        },
        "claim_limit": (
            "This closes the authorized read-only site row and proves the "
            "outer D705 site, bounded primary-comparison failure and eventual "
            "convergence. It does not assign the structural oracle defect to "
            "this instance, does not exonerate that defect, and authorizes no "
            "fix, further device access, resume, D2-D5 or release claim."),
    }


def validate(value: dict[str, Any]) -> None:
    require(value.get("format") == FORMAT and value.get("status") == STATUS,
            "site result identity drift")
    contact = value["contact"]
    require(contact["tuple_first"] == TUPLE, "tuple-first drift")
    require(contact["discipline"] == {
        "stops": 0, "resumes": 0, "runs": 0, "resets": 0,
        "tuple_before_memory": True,
        "raw_persisted_before_interpretation": True,
        "static_before_dynamic": True, "CPU_left_stopped": True,
        "D2_D5_executed": False}, "raw-first/contact discipline drift")
    require(contact["static_reads"] == captured_rows(STATIC)
            and contact["dynamic_reads"] == captured_rows(DYNAMIC),
            "bound raw rows drift")
    d705 = value["decoded_descriptors"]["D705"]
    require(d705["done"] == 0xA5
            and d705["probe"]["source"] == 0x08100020
            and d705["primary"] == {
                "command": 0, "length": 32,
                "source": 0x08100020, "target": 0xCF6D}
            and d705["retained_probe_at_stop"] == 0x73,
            "D705 descriptor conclusion drift")
    geometry = value["linked_stack_geometry"]
    require(geometry["outer_Shelf_target"] == "0xcf6d"
            and geometry["inner_image_reader_Shelf_target"] == "0xcf05"
            and geometry["target_separation_bytes"] == 104,
            "outer/inner geometry distinction drift")
    require(value["late_state"] == {
        "immutable_source": 0x73,
        "retained_probe_slot": 0x73,
        "primary_first_difference_target": 0x73,
        "all_equal_at_stopped_read": True,
        "interpretation": (
            "the source-probe slot and primary target both converged by the "
            "later stopped-state read")}, "late-convergence state drift")
    decision = value["decision"]
    require(decision["exact_site"] == "phase02a outer D705 Shelf read"
            and decision["source_probe"]
            == "completed and primary descriptor was submitted"
            and decision["bounded_failure"]
            == "D705 primary comparator exceeded 64 frames"
            and decision["post_timeout_state"]
            == "probe and primary later converged to 0x73"
            and decision["device_instance_nature"]
            == "UNRESOLVED-BETWEEN-STALE-LATCHED-ORACLE-AND-GENUINE-PRIMARY-LATENCY"
            and decision["structural_verifier_oracle"]
            == "REMAINS-RED-INDEPENDENTLY",
            "decision boundary drift")
    require("does not assign" in value["claim_limit"]
            and "does not exonerate" in value["claim_limit"]
            and "authorizes no fix" in value["claim_limit"],
            "claim limit widened")


def mutations() -> dict[str, Callable[[dict[str, Any]], None]]:
    return {
        "add-stop": lambda x: x["contact"]["discipline"].update(stops=1),
        "resume": lambda x: x["contact"]["discipline"].update(resumes=1),
        "drop-raw-first": lambda x: x["contact"]["discipline"].update(
            raw_persisted_before_interpretation=False),
        "open-D2-D5": lambda x: x["contact"]["discipline"].update(
            D2_D5_executed=True),
        "move-tuple": lambda x: x["contact"]["tuple_first"].update(PC="0xe097"),
        "mutate-static-byte": lambda x: x["contact"]["static_reads"][
            "convergence-done-markers"].update(observed_hex="5aa5"),
        "mutate-dynamic-byte": lambda x: x["contact"]["dynamic_reads"][
            "immutable-source"].update(observed_hex="00"),
        "clear-D705-marker": lambda x: x["decoded_descriptors"]["D705"].update(
            done=0x5A),
        "move-D705-source": lambda x: x["decoded_descriptors"]["D705"][
            "probe"].update(source=0x08100021),
        "move-D705-target": lambda x: x["decoded_descriptors"]["D705"][
            "primary"].update(target=0xCF05),
        "collapse-target-separation": lambda x: x["linked_stack_geometry"].update(
            target_separation_bytes=0),
        "claim-inner-site": lambda x: x["decision"].update(
            exact_site="image-reader inner D705 Shelf cross-read"),
        "claim-probe-timeout": lambda x: x["decision"].update(
            source_probe="timed out"),
        "claim-no-bound-failure": lambda x: x["decision"].update(
            bounded_failure="none"),
        "erase-late-convergence": lambda x: x["late_state"].update(
            all_equal_at_stopped_read=False),
        "claim-stale-instance": lambda x: x["decision"].update(
            device_instance_nature="STALE-ORACLE-PROVED"),
        "claim-genuine-instance": lambda x: x["decision"].update(
            device_instance_nature="GENUINE-LATENCY-PROVED"),
        "exonerate-structural-oracle": lambda x: x["decision"].update(
            structural_verifier_oracle="EXONERATED"),
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
        except (ResultError, KeyError, TypeError):
            rejected.append(name)
    require(rejected == list(mutations()), f"mutation survived: {rejected}")


def verify_capture() -> None:
    require(exact(CAPTURE, CAPTURE_SHA256, "raw capture")["bytes"] == 10728,
            "raw capture byte count drift")
    require(exact(CHECKPOINT, CHECKPOINT_SHA256,
                  "raw static checkpoint")["bytes"] == 8008,
            "raw checkpoint byte count drift")
    capture = load(CAPTURE)
    checkpoint = load(CHECKPOINT)
    require(capture["tuple"] == checkpoint["tuple"] == TUPLE,
            "capture/checkpoint tuple drift")
    require(capture["discipline"] == {
        "stops": 0, "resumes": 0, "runs": 0, "resets": 0,
        "tuple_before_memory": True, "static_before_dynamic": True,
        "CPU_left_stopped": True, "D2_D5_executed": False},
        "raw capture discipline drift")
    require(checkpoint["discipline"] == {
        "stops": 0, "resumes": 0, "runs": 0, "resets": 0,
        "tuple_before_memory": True, "CPU_left_stopped": True,
        "D2_D5_executed": False}, "checkpoint discipline drift")
    observed = {row["name"]: {"physical_address": row["physical_address"],
                               "bytes": row["bytes"],
                               "observed_hex": row["observed_hex"]}
                for row in capture["reads"]}
    checkpoint_observed = {
        row["name"]: {"physical_address": row["physical_address"],
                      "bytes": row["bytes"],
                      "observed_hex": row["observed_hex"]}
        for row in checkpoint["reads"]}
    require(observed == checkpoint_observed == captured_rows(STATIC),
            "raw-first static rows drift")
    dynamic = {row["name"]: {"physical_address": row["physical_address"],
                             "bytes": row["bytes"],
                             "observed_hex": row["observed_hex"]}
               for row in capture["dynamic_reads"]}
    require(dynamic == captured_rows(DYNAMIC), "raw dynamic rows drift")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) == 2 else ""
    require(action in {"record", "check", "selftest"},
            "usage: c2_v20_phase02a_site_result.py record|check|selftest")
    value = derive()
    validate(value)
    selftest(value)
    if action == "record":
        verify_capture()
        RECEIPT.write_bytes(canonical(value))
    elif action == "check":
        require(load(RECEIPT) == value,
                "persisted phase-02a site result stale")
    print("v2.0 phase-02a site result: PASS "
          f"site=outer-D705 nature=late-convergence-ambiguous "
          f"mutations={len(mutations())}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ResultError, OSError, ValueError, KeyError, TypeError,
            struct.error, subprocess.CalledProcessError) as error:
        print(f"v2.0 phase-02a site result: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
