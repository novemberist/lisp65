#!/usr/bin/env python3
"""Build and close a non-promotable cold-stager failure breadcrumb medium."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_defstruct_terminal_ingress_sister as SISTER  # noqa: E402
import c2_lite_media_product as MEDIA  # noqa: E402
import c2_v150_stager_liveness_successor as LIVE  # noqa: E402
import c2_v21_loading_libraries_progress_media_repair as REPAIR  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CONTACT = ARCH / (
    "c2.3-v2.1-loading-libraries-progress-media-recontact-receipt.json")
BUILD = ROOT / "build/c2.3/v2.1-loading-libraries-stage-breadcrumb-media"
STAGER = BUILD / "autoboot.c65"
STAGER_MAP = BUILD / "autoboot.c65.map"
CONTROL = BUILD / "control-autoboot.c65"
CONTROL_MAP = BUILD / "control-autoboot.c65.map"
PRODUCT_D81 = BUILD / "lisp65-loading-libraries-stage-breadcrumb.d81"
READBACK = BUILD / "readback"
RECEIPT = ARCH / (
    "c2.3-v2.1-loading-libraries-stage-breadcrumb-media-receipt.json")
FORMAT = "lisp65-c2.3-v2.1-loading-libraries-stage-breadcrumb-media-v1"
TRACE_OPT_IN = "-DLISP65_V21_STAGE_TRACE"
COMMIT = 0xA5


class BreadcrumbError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise BreadcrumbError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def packed_medium_gate(path: Path) -> dict[str, Any]:
    roles = SISTER.medium_roles(path, READBACK)
    paths = SISTER.role_paths(roles)
    descriptor = paths["boot.id"].read_bytes()
    rows, build_id, profile_id = SISTER.descriptor_rows(descriptor, paths)
    SISTER.target_descriptor_check(descriptor, rows,
                                   descriptor_build_id=build_id,
                                   stager_build_id=build_id)
    require(paths["autoboot.c65"].read_bytes() == STAGER.read_bytes(),
            "packed breadcrumb stager differs from closed artifact")
    source_roles = SISTER.medium_roles(REPAIR.PRODUCT_D81,
                                       READBACK / "source")
    source_paths = SISTER.role_paths(source_roles)
    for row in rows:
        name = row["name"]
        require(paths[name].read_bytes() == source_paths[name].read_bytes(),
                f"breadcrumb builder changed product role: {name}")
    return {"result": "passed-same-product-roles-and-traced-stager",
            "roles": len(roles), "descriptor_rows": len(rows),
            "build_id": f"0x{build_id:08x}",
            "profile_id": f"0x{profile_id:08x}"}


def trace_source_gate() -> dict[str, Any]:
    source = MEDIA.STAGER_C.read_text(encoding="utf-8")
    reasons = (
        "C2_V21_TRACE_MEDIA_IDENTITY", "C2_V21_TRACE_DESCRIPTOR_LOAD",
        "C2_V21_TRACE_DESCRIPTOR_VALIDATE", "C2_V21_TRACE_ROLE_DOMAIN",
        "C2_V21_TRACE_ROLE_FLAG", "C2_V21_TRACE_LENGTH_RANGE",
        "C2_V21_TRACE_STAGE_DOMAIN", "C2_V21_TRACE_FIND_FILE",
        "C2_V21_TRACE_F011_READ", "C2_V21_TRACE_CHAIN_TERMINATOR",
        "C2_V21_TRACE_LENGTH_OVERFLOW",
        "C2_V21_TRACE_CONVERGENCE_TIMEOUT",
        "C2_V21_TRACE_CHAIN_POINTER", "C2_V21_TRACE_CHAIN_FUEL",
        "C2_V21_TRACE_FINAL_LENGTH", "C2_V21_TRACE_FINAL_CRC",
        "C2_V21_TRACE_NONSTAGE_SCAN", "C2_V21_TRACE_PRODUCT_RECORD",
        "C2_V21_TRACE_PRODUCT_SCAN", "C2_V21_TRACE_CHAIN_RETURN",
    )
    require(
        "#ifdef LISP65_V21_STAGE_TRACE" in source
        and "volatile uint8_t c2_v21_stage_trace[32];" in source
        and "c2_v21_stage_trace[31] = 0xa5u;" in source
        and all(source.count(reason) >= 2 for reason in reasons),
        "stage breadcrumb source coverage drift")
    return {"status": "passed-20-distinct-failure-reasons-and-commit-last",
            "failure_reasons": len(reasons), "record_bytes": 32,
            "commit_offset": 31, "commit": f"0x{COMMIT:02x}"}


def build() -> dict[str, Any]:
    require(not BUILD.exists(), "stage breadcrumb build is one-shot")
    contact = load(CONTACT)
    require(contact.get("status") ==
            "INSTRUMENT-MEDIA-RED; CPU-RATE-UNMEASURED"
            and contact.get("progress_ring", {}).get("arm") == "0x00"
            and contact.get("stopped_code_identity", {}).get("symbol") ==
                "show_disk_error",
            "stage breadcrumb lacks the bound repaired-contact First Red")
    BUILD.mkdir(parents=True)
    roles = SISTER.medium_roles(REPAIR.PRODUCT_D81, BUILD / "source-roles")
    paths = SISTER.role_paths(roles)
    descriptor = paths["boot.id"].read_bytes()
    rows, build_id, profile_id = SISTER.descriptor_rows(descriptor, paths)

    control_gate = MEDIA.compile_stager(
        build_id, rows, build_dir=BUILD / "control-build",
        stager=CONTROL, stager_map=CONTROL_MAP,
        compile_defines=(LIVE.OPT_IN,))
    require(CONTROL.read_bytes() == REPAIR.STAGER.read_bytes()
            and Path(str(CONTROL) + ".elf").read_bytes() ==
                Path(str(REPAIR.STAGER) + ".elf").read_bytes(),
            "trace-off canonical stager is not byteidentical")
    trace_gate = MEDIA.compile_stager(
        build_id, rows, build_dir=BUILD / "trace-build",
        stager=STAGER, stager_map=STAGER_MAP,
        compile_defines=(LIVE.OPT_IN, TRACE_OPT_IN))
    truth = ElfTruth.read(
        Path(str(STAGER) + ".elf"),
        llvm_readobj=MEDIA.CANONICAL.COMPILER.parent / "llvm-readobj",
        include_section_data=True)
    record = truth.symbol("c2_v21_stage_trace")
    require(record.bytes == 32 and record.section == ".bss",
            "linked stage breadcrumb record drift")

    shutil.copyfile(REPAIR.PRODUCT_D81, PRODUCT_D81)
    subprocess.run(["c1541", "-attach", str(PRODUCT_D81),
                    "-delete", "autoboot.c65", "-write", str(STAGER),
                    "autoboot.c65"], cwd=ROOT, check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    gates: dict[str, Callable[[Path], dict[str, Any]]] = {
        "autoboot.c65.elf": LIVE.delivered_liveness_gate,
        "diagnostic-product.d81": packed_medium_gate,
    }
    closure = MEDIA.close_packed_artifacts(
        {"autoboot.c65.elf": Path(str(STAGER) + ".elf"),
         "diagnostic-product.d81": PRODUCT_D81}, gates)
    require(closure.get("complete") is True,
            "stage breadcrumb packed-artifact closure incomplete")

    value = {
        "format": FORMAT, "recorded_on": "2026-08-15",
        "status": (
            "HOST-GREEN; STAGE-BREADCRUMB-MEDIA-CLOSED; "
            "CONTACT-NOT-AUTHORIZED"),
        "authority": {"contact_first_red": bind(CONTACT),
                      "repaired_medium": bind(REPAIR.RECEIPT)},
        "trace": {"compile_opt_in": TRACE_OPT_IN,
                  "source_gate": trace_source_gate(),
                  "record": {"address": f"0x{record.value:04x}",
                             "bytes": record.bytes,
                             "section": record.section,
                             "commit_offset": 31,
                             "commit": f"0x{COMMIT:02x}"},
                  "stager": bind(STAGER),
                  "stager_ELF": bind(Path(str(STAGER) + ".elf")),
                  "linked_gate": trace_gate},
        "control": {"trace_off_stager": bind(CONTROL),
                    "trace_off_ELF": bind(Path(str(CONTROL) + ".elf")),
                    "byteidentical_to_repaired_stager": True,
                    "linked_gate": control_gate},
        "media": {"product_D81": bind(PRODUCT_D81),
                  "library_D81": REPAIR.check()["media"]["library_D81"],
                  "build_id": f"0x{build_id:08x}",
                  "profile_id": f"0x{profile_id:08x}",
                  "product_bytes_changed": 0},
        "packed_artifact_gate_registry": closure,
        "decision_table": {
            "commit-absent": "failure before the trace owner initializes",
            "reason-01-05": "media/descriptor/role contract rejection",
            "reason-10-1a": "exact scan, F011, convergence, chain or CRC edge",
            "reason-20-23": "post-stage verification, product or handoff edge",
        },
        "claim_limit": (
            "Host-only non-promotable breadcrumb medium. It changes no "
            "product byte and authorizes no device contact."),
    }
    value["mutations"] = mutations(value)
    audit(value)
    RECEIPT.write_bytes(canonical(value))
    return value


def audit(value: dict[str, Any]) -> None:
    registry = value.get("packed_artifact_gate_registry", {})
    record = value.get("trace", {}).get("record", {})
    require(
        value.get("status") ==
            "HOST-GREEN; STAGE-BREADCRUMB-MEDIA-CLOSED; CONTACT-NOT-AUTHORIZED"
        and value.get("trace", {}).get("compile_opt_in") == TRACE_OPT_IN
        and record.get("bytes") == 32 and record.get("commit_offset") == 31
        and record.get("commit") == "0xa5"
        and value.get("control", {}).get(
            "byteidentical_to_repaired_stager") is True
        and value.get("media", {}).get("product_bytes_changed") == 0
        and registry.get("complete") is True
        and registry.get("registered") == registry.get("executed") ==
            ["autoboot.c65.elf", "diagnostic-product.d81"],
        "stage breadcrumb medium closure drift")


def mutations(base: dict[str, Any]) -> list[str]:
    cases = {
        "drop-trace-opt-in": lambda x: x["trace"].update(compile_opt_in=""),
        "move-commit": lambda x: x["trace"]["record"].update(
            commit_offset=30),
        "grow-record": lambda x: x["trace"]["record"].update(bytes=33),
        "change-product": lambda x: x["media"].update(product_bytes_changed=1),
        "omit-stager-gate": lambda x: x["packed_artifact_gate_registry"]
            ["executed"].remove("autoboot.c65.elf"),
        "omit-medium-gate": lambda x: x["packed_artifact_gate_registry"]
            ["executed"].remove("diagnostic-product.d81"),
        "authorize-contact": lambda x: x.update(status="CONTACT-AUTHORIZED"),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(base); mutate(trial)
        try:
            audit(trial)
        except BreadcrumbError:
            rejected.append(name)
    require(len(rejected) == len(cases),
            "stage breadcrumb mutation survived")
    return sorted(rejected)


def check() -> dict[str, Any]:
    value = load(RECEIPT); audit(value)
    require(value["authority"]["contact_first_red"] == bind(CONTACT)
            and value["authority"]["repaired_medium"] == bind(REPAIR.RECEIPT)
            and value["trace"]["source_gate"] == trace_source_gate()
            and value["trace"]["stager"] == bind(STAGER)
            and value["trace"]["stager_ELF"] ==
                bind(Path(str(STAGER) + ".elf"))
            and value["control"]["trace_off_stager"] == bind(CONTROL)
            and CONTROL.read_bytes() == REPAIR.STAGER.read_bytes()
            and value["media"]["product_D81"] == bind(PRODUCT_D81),
            "stage breadcrumb authority/artifact drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "check"))
    args = parser.parse_args()
    value = build() if args.action == "build" else check()
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (BreadcrumbError, MEDIA.MediaError, OSError, KeyError, ValueError,
            subprocess.CalledProcessError) as error:
        print(f"LINK 107 STAGE BREADCRUMB: {error}", file=sys.stderr)
        raise SystemExit(1)
