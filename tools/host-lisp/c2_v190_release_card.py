#!/usr/bin/env python3
"""Build and qualify the v1.9.0 banner successor over accepted r8 A+B."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_v180_release_card as OLD  # noqa: E402
import c2_v190_block_a_delivered_consumer_repair as R8  # noqa: E402


BASE = R8.BASE
CARD = R8.CARD
RELEASE = OLD.RELEASE
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.9.0-pre-plan.md"
REPORT = ROOT / "docs/planning/v1.9.0-release-card-report.md"
BUILD = ROOT / "build/c2.3/v1.9.0-release-card-r1"
PREFLIGHT = ROOT / "build/c2.3/v1.9.0-release-card-r1-preflight"
PLANE_ROOT = PREFLIGHT / "setup-owned/static-plane/narrow-static"
PLANE_RECEIPT = PREFLIGHT / "v190-release-static-plane.json"
CLIENT_SOURCE = PREFLIGHT / "sources/stdlib-read-line.lisp"
C2D = PLANE_ROOT / "v6-semantics/initial.c2d-v6.bin"
CODE = PLANE_ROOT / "v6-semantics/bank2-static-code.bin"
MANIFEST = PLANE_ROOT / "stdlib-p0.manifest.json"
HEADER = PLANE_ROOT / "stdlib-p0.h"
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
PROFILE = BUILD / "wplto/resolved-profile.txt"
INVOCATION = PREFLIGHT / "candidate-invocation-release-r1.json"
PREFLIGHT_RECEIPT = ARCH / "c2.3-v1.9.0-release-card-r1-preflight.json"
DIFFERENCE = ARCH / "c2.3-v1.9.0-release-card-r1-difference.json"
RECEIPT = ARCH / "c2.3-v1.9.0-release-card-r1-receipt.json"
FIRST_RED = ARCH / "c2.3-v1.9.0-release-card-r1-first-red.json"
R8_ELF = R8.ELF
R8_PRG = R8.PRG
R8_PROFILE = R8.PROFILE
R8_CODE = R8.CODE
R8_MANIFEST = R8.MANIFEST
R8_RECEIPT = R8.RECEIPT
R8_STATUS = R8.STATUS
DEVICE_RESULT = ARCH / "c2.3-v1.9-block-a-delivered-consumer-r8-device-result.json"
D5_RECEIPT = ARCH / "c2.3-v1.9-r8-release-terminal-d5-receipt.json"
BANNER = ROOT / "lib/repl-banner.lisp"
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
FORMAT = "lisp65-c2-v190-release-product-card-v1"
STATUS = "PASS: V1.9.0 RELEASE PRODUCT CARD FINAL GREEN"
EXPECTED_BANNER = "WORKBENCH 1.9.0"
PREDECESSOR_BANNER = "WORKBENCH 1.8.0"


class ReleaseError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReleaseError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def section_bind(header: str) -> dict[str, Any]:
    text = PLAN.read_text(encoding="utf-8")
    require(text.count(header) == 1, f"plan section drift: {header}")
    section = header + text.split(header, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    raw = section.encode()
    return {"path": PLAN.relative_to(ROOT).as_posix(), "section": header,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    predecessor = load(R8_RECEIPT)
    device = load(DEVICE_RESULT)
    d5 = load(D5_RECEIPT)
    require(predecessor["status"] == R8_STATUS
            and device["status"] == "PASS: V1.9 BLOCK A HARDWARE ACCEPTED"
            and device["stopped_state"]["counters"] == {
                "raw": 136, "seen": 136, "stored": 136, "taken": 136}
            and d5["status"] ==
                "PASS: V1.9 R8 RELEASE-TERMINAL D5 GREEN AND DELTA ATTRIBUTED"
            and d5["D5"]["free"] == {
                "symbol_slots": 109, "namepool_bytes": 1486}
            and d5["decision"]["owner_Ship_halt"] == "DECIDABLE",
            "v1.9 release authority drift")
    return {
        "accepted_r8_product": bind(R8_RECEIPT),
        "accepted_Block_A_device_result": bind(DEVICE_RESULT),
        "release_terminal_D5": bind(D5_RECEIPT),
        "hardware_result_section": section_bind(
            "## Block A delivered-consumer hardware result — 2026-08-30"),
        "D5_closure_section": section_bind(
            "## r8 release-terminal D5 and delta closure — 2026-08-30"),
        "budget": {"WPLTO_runs": 1, "product_links": 1,
                   "media_builds": 0, "device_contacts": 0},
        "owner_halts": {"Ship": "decidable-not-inferred",
                        "Publish": "closed"},
    }


def _set_paths() -> None:
    for name, value in {
        "BUILD": BUILD, "PREFLIGHT": PREFLIGHT,
        "PREFLIGHT_RECEIPT": PREFLIGHT_RECEIPT,
        "PLANE_ROOT": PLANE_ROOT, "PLANE_RECEIPT": PLANE_RECEIPT,
        "CLIENT_SOURCE": CLIENT_SOURCE, "C2D": C2D, "CODE": CODE,
        "MANIFEST": MANIFEST, "HEADER": HEADER, "ELF": ELF, "PRG": PRG,
        "PROFILE": PROFILE, "INVOCATION": INVOCATION,
        "DIFFERENCE": DIFFERENCE, "RECEIPT": RECEIPT, "REPORT": REPORT,
        "DRIVER": DRIVER, "FORMAT": FORMAT, "STATUS": STATUS,
    }.items():
        setattr(R8, name, value)


def configure() -> None:
    _set_paths()
    R8.configure()
    BASE.INVOCATION = INVOCATION
    BASE.DRIVER = DRIVER
    BASE.FORMAT = FORMAT
    BASE.STATUS = STATUS
    BASE.authority = authority
    BASE.configuration_gate = configuration_gate
    BASE.final_gate = final_gate
    CARD.authority = authority
    RELEASE.EXPECTED_BANNER = EXPECTED_BANNER
    RELEASE.PREDECESSOR_BANNER = PREDECESSOR_BANNER
    for name, value in {
        "BUILD": BUILD, "PREFLIGHT": PREFLIGHT, "RECEIPT": RECEIPT,
        "ELF": ELF, "PRG": PRG, "PROFILE": PROFILE,
        "PLANE_ROOT": PLANE_ROOT, "PLANE_RECEIPT": PLANE_RECEIPT,
        "C2D": C2D, "CODE": CODE, "MANIFEST": MANIFEST,
        "BANNER": BANNER, "DRIVER": DRIVER, "FORMAT": FORMAT,
        "STATUS": STATUS,
    }.items():
        setattr(RELEASE, name, value)
    for name, value in {
        "CARD": R8.CLIENT.SUBSTRATE, "BASE": BASE, "RELEASE": RELEASE,
        "HYBRID": R8.CLIENT.HYBRID, "QUEUE": R8.CLIENT.QUEUE,
        "BUILD": BUILD, "PREFLIGHT": PREFLIGHT, "RECEIPT": RECEIPT,
        "REPORT": REPORT, "ELF": ELF, "PRG": PRG, "PROFILE": PROFILE,
        "PLANE_ROOT": PLANE_ROOT, "PLANE_RECEIPT": PLANE_RECEIPT,
        "C2D": C2D, "CODE": CODE, "MANIFEST": MANIFEST,
        "PREDECESSOR_ELF": R8_ELF, "PREDECESSOR_PRG": R8_PRG,
        "PREDECESSOR_PROFILE": R8_PROFILE, "PREDECESSOR_CODE": R8_CODE,
        "PREDECESSOR_MANIFEST": R8_MANIFEST,
        "PREDECESSOR_RECEIPT": R8_RECEIPT,
        "PREDECESSOR_STATUS": R8_STATUS, "DRIVER": DRIVER,
        "FORMAT": FORMAT, "STATUS": STATUS,
        "EXPECTED_BANNER": EXPECTED_BANNER,
        "PREDECESSOR_BANNER": PREDECESSOR_BANNER,
    }.items():
        setattr(OLD, name, value)
    OLD.plane_successor_gate = plane_successor_gate


def banner_gate() -> dict[str, Any]:
    value = OLD.banner_gate()
    require(value["final_composed_literal"] in (None, EXPECTED_BANNER)
            and value["emitted"]["direct_object_bytes"] == 65,
            "v1.9 banner emission drift")
    value["status"] = "PASS: WORKBENCH 1.9.0 IS THE UNIQUE EMITTED BANNER"
    return value


def plane_successor_gate() -> dict[str, Any]:
    before_code, after_code = R8_CODE.read_bytes(), CODE.read_bytes()
    require(before_code == after_code,
            "v1.9 banner successor changed static code bytes")
    old, new = load(R8_MANIFEST), load(MANIFEST)
    old_banner = next(row for row in old["entries"]
                      if row["name"] == "%repl-banner")
    new_banner = next(row for row in new["entries"]
                      if row["name"] == "%repl-banner")
    old_other = [row for row in old["entries"]
                 if row["name"] != "%repl-banner"]
    new_other = [row for row in new["entries"]
                 if row["name"] != "%repl-banner"]
    require(old_other == new_other
            and old_banner["length"] == new_banner["length"] == 155
            and old_banner["literals"][-1] == {"string": PREDECESSOR_BANNER}
            and new_banner["literals"][-1] == {"string": EXPECTED_BANNER},
            "v1.9 release plane changed outside the banner literal")

    def delta(relative: str) -> list[dict[str, int]]:
        before = (R8_MANIFEST.parent / relative).read_bytes()
        after = (MANIFEST.parent / relative).read_bytes()
        require(len(before) == len(after),
                f"v1.9 banner successor changed {relative} extent")
        return [{"offset": index, "before": left, "after": right}
                for index, (left, right) in enumerate(zip(before, after))
                if left != right]

    ext = delta("stdlib-p0.ext.bin")
    c2i = delta("product/stdlib-p0.c2i.bin")
    c2d = delta("v6-semantics/initial.c2d-v6.bin")
    shelf = delta("product/product-shelf-v4-direct.bin")
    digit = {"before": ord("8"), "after": ord("9")}
    require(len(ext) == len(c2i) == 1
            and {key: ext[0][key] for key in digit} == digit
            and {key: c2i[0][key] for key in digit} == digit
            and len(c2d) == 8 and len(shelf) == 17
            and {key: shelf[-1][key] for key in digit} == digit,
            "v1.9 banner payload/derived identity delta is not closed")
    return {
        "status": "PASS: BANNER BYTE AND DERIVED IDENTITIES FULLY ATTRIBUTED",
        "predecessor": bind(R8_CODE), "candidate": bind(CODE),
        "code_differences": 0,
        "banner": {"before": PREDECESSOR_BANNER, "after": EXPECTED_BANNER},
        "payload_differences": {"stdlib_ext": ext, "product_c2i": c2i,
                                "product_shelf_literal": [shelf[-1]]},
        "derived_identity_differences": {"c2d_v6": c2d,
                                         "product_shelf_header": shelf[:-1]},
        "families": {"banner_payload": 3,
                     "derived_identity": len(c2d) + len(shelf) - 1,
                     "unattributed": 0},
    }


def configuration_gate() -> dict[str, Any]:
    value = R8.R7.configuration_gate()
    value.update({
        "world": "v1.9.0-release-banner-successor",
        "release_banner": banner_gate(),
        "release_freight": ["armed Capture client", "native prompt editor",
                            "native INIT.L65", "A0 recovery fast path",
                            "WORKBENCH-1.9.0-banner"],
        "excluded": ["repl-comfort", "Matcher/Blink", "$22 diagnosis",
                     "domain findings", "diagnostic-client"],
    })
    return value


def attribution() -> dict[str, Any]:
    value = OLD.attribution()
    require(all(count == 0 for name, count in value["counts"].items()
                if name.startswith("unexplained_")),
            "v1.9 release attribution retained an unexplained member")
    value["status"] = "PASS: R8 TO RELEASE DIFFERENCE FULLY ATTRIBUTED"
    return value


def final_gate() -> dict[str, Any]:
    value = R8.final_gate()
    before = ElfTruth.read(R8_ELF, llvm_readobj=READOBJ)
    after = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    delivered = value["v1_9_Block_B_light"]["native_prompt_final_ELF"]
    counters = delivered["delivered_consumption"]["delivered_host_wall"][
        "counters"]
    d5 = load(D5_RECEIPT)
    require(counters == {"raw": 94, "seen": 94, "stored": 94, "taken": 94}
            and delivered["ordinary_text"]["free_bytes"] >= 32
            and before.section(".text").bytes == after.section(".text").bytes
            and before.section(".bss").bytes == after.section(".bss").bytes
            and R8_CODE.read_bytes() == CODE.read_bytes(),
            "v1.9 banner successor changed an accepted product wall")
    value["release_v1_9_0"] = {
        "status": "PASS: HARDWARE-ACCEPTED A+B PLUS BANNER SUCCESSOR",
        "banner": banner_gate(), "plane_successor": plane_successor_gate(),
        "hardware_authority": {
            "Block_A": bind(DEVICE_RESULT), "release_terminal_D5": bind(D5_RECEIPT),
            "free": d5["D5"]["free"]},
        "delivered_consumer_wall": counters,
        "resident_extents": {"text_before": before.section(".text").bytes,
            "text_after": after.section(".text").bytes,
            "bss_before": before.section(".bss").bytes,
            "bss_after": after.section(".bss").bytes},
        "claim_boundary": {
            "ships": ["lossless native-prompt input across forced collection",
                "native prompt editor", "native INIT.L65",
                "A0 recovery fast path"],
            "excludes": ["type-ahead during evaluation", "Comfort",
                "Matcher/Blink", "$22 mechanism", "domain findings"],
            "pensioned_known_issues": ["v1.5 fast typing can lose input",
                "v1.8 native prompt rejects cursor controls"],
        },
    }
    return value


def write_report(value: dict[str, Any]) -> None:
    diff = value["attribution"]["counts"]
    pair = value["artifacts_after"]
    release = value["final_product"]["release_v1_9_0"]
    REPORT.write_text(f"""# v1.9.0 release product card

Status: **{value['status']}**

The one producer run materialized the hardware-accepted r8 A+B world with the
unique banner `{EXPECTED_BANNER}`.  `lib/repl-banner.lisp` is the only authored
release root; the {R8_CODE.stat().st_size:,}-byte static code plane is
byte-identical to r8.  The banner payload and every derived C2D/shelf identity
field are fully attributed.

The complete r8-to-release attribution names {diff['PRG_bytes']} PRG bytes,
{diff['ELF_bytes']} ELF bytes, {diff['symbols_removed']} removed plus
{diff['symbols_added']} added symbols, and {diff['relocations_removed']} removed
plus {diff['relocations_added']} added relocations, with zero unexplained
members.  The qualified pair is ELF `{pair['ELF']['sha256']}` / PRG
`{pair['PRG']['sha256']}`; resident text/BSS remain
{release['resident_extents']['text_after']}/
{release['resident_extents']['bss_after']} bytes.

The final ELF retains the delivered 94/94/94/94 consumer wall, the native
prompt editor and every Block-A/B ownership, responsiveness, placement and
recovery gate.  Hardware authority is the r8 forced-collection result
136/136/136/136 plus release-terminal D5 **109 slots / 1,486 name bytes**.

The release claims lossless native-prompt input across a forced collection and
the editor at `lisp65>`.  Type-ahead during evaluation, Comfort, Matcher/Blink,
the `$22` mechanism and domain findings remain outside the claim.  No medium
was built and no device was contacted.  This green card makes the owner's
explicit `Ship` halt decidable; `Publish` remains closed.
""", encoding="utf-8")


def preflight() -> None:
    require(not any(path.exists() for path in
                    (BUILD, PREFLIGHT, PREFLIGHT_RECEIPT, RECEIPT, DIFFERENCE)),
            "v1.9 release card is one-shot")
    configure()
    plane = R8.emit_plane()
    frame = R8.R7.full_framebuffer_gate()
    R8.R7.R6.setup_child()
    order = R8.R7.R6.configuration_order_gate()
    linker = R8.R7.PRODUCT.linker_script(ownership_opt_in=True)
    pins = R8.R7.R6.known_pin_inventory(linker)
    consumption = R8.consumption_preflight(R8_ELF)
    successor = plane_successor_gate()
    value = {"format": FORMAT + "-preflight-v1", "recorded_on": "2026-08-30",
        "status": "PASS: V1.9.0 RELEASE CARD ARMED 0/1",
        "authority": authority(), "plane": bind(PLANE_RECEIPT),
        "banner_successor": successor, "framebuffer": frame,
        "delivered_consumption": consumption, "configuration_order": order,
        "known_pin_inventory": pins,
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "next": "commit the zero-link preflight, then spend the authorized 1/1"}
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("v1.9.0 release: PREFLIGHT PASS banner=1.9.0 WPLTO=0/1 link=0/1")


def check_preflight() -> None:
    configure()
    value = load(PREFLIGHT_RECEIPT)
    require(value["status"] == "PASS: V1.9.0 RELEASE CARD ARMED 0/1"
            and value["authority"] == authority()
            and value["banner_successor"] == plane_successor_gate()
            and value["delivered_consumption"]["delivered_host_wall"][
                "counters"] == {"raw": 94, "seen": 94,
                                "stored": 94, "taken": 94}
            and value["attempt_accounting"]["WPLTO_runs"] == 0,
            "v1.9 release preflight receipt drift")
    print("v1.9.0 release: PREFLIGHT CHECK PASS banner=1.9.0")


def frozen_artifacts() -> dict[str, Any]:
    return BASE.artifacts()


def run_child(action: str) -> dict[str, Any]:
    result = subprocess.run([sys.executable, str(DRIVER), action], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0,
            f"release child {action} red:\n{result.stdout}")
    return {"action": action,
            "stdout_tail": " ".join(result.stdout.split()[-30:])}


def build() -> None:
    configure()
    pre = load(PREFLIGHT_RECEIPT)
    require(pre["status"] == "PASS: V1.9.0 RELEASE CARD ARMED 0/1"
            and not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not DIFFERENCE.exists(),
            "v1.9 release preflight/build lifecycle drift")
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, check=True).stdout
    require(clean == "", "v1.9 release WPLTO requires committed clean sources")
    INVOCATION.write_bytes(canonical({"status": "INVOKED",
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "budget": {"WPLTO_runs": 1, "product_links": 1}}))
    processes = [run_child("_produce")]
    before = frozen_artifacts()
    diff = attribution()
    DIFFERENCE.write_bytes(canonical(diff))
    gate = final_gate()
    processes.extend((run_child("_scope"), run_child("_accept")))
    after = frozen_artifacts()
    scope, acceptance = load(BASE.SCOPE_RESULT), load(BASE.ACCEPTANCE_RESULT)
    require(before == after and scope["status"] == acceptance["status"] == "PASS",
            "v1.9 release qualification tail red")
    value = {"format": FORMAT, "recorded_on": "2026-08-30",
        "status": STATUS, "authority": authority(),
        "preflight": bind(PREFLIGHT_RECEIPT), "invocation": bind(INVOCATION),
        "attribution": diff, "attribution_receipt": bind(DIFFERENCE),
        "final_product": gate, "producer": bind(BASE.PRODUCER_RESULT),
        "scope": bind(BASE.SCOPE_RESULT),
        "acceptance": bind(BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": processes,
        "attempt_accounting": {"WPLTO_runs": 1, "product_links": 1,
            "scope_runs": 1, "acceptance_runs": 1,
            "media_builds": 0, "device_contacts": 0},
        "owner_Ship": "DECIDABLE-NOT-INFERRED", "owner_Publish": "CLOSED",
        "media_authorized": False,
        "next": "independent review and explicit owner Ship"}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    check()
    print("v1.9.0 release: BUILD PASS WPLTO=1/1 link=1/1 banner=1.9.0")


def record_first_red() -> None:
    configure()
    require(ELF.is_file() and PRG.is_file() and INVOCATION.is_file()
            and not FIRST_RED.exists() and not DIFFERENCE.exists()
            and not RECEIPT.exists() and not BASE.SCOPE_RESULT.exists()
            and not BASE.ACCEPTANCE_RESULT.exists(),
            "v1.9 release First-Red lifecycle drift")
    pair = frozen_artifacts()
    value = {"format": FORMAT + "-first-red-v1",
        "recorded_on": "2026-08-30",
        "status": "POST-LINK RED: RELEASE ATTRIBUTION ADAPTER OWNER",
        "error": ("c2_v190_native_prompt_editor_card has no attribute "
                  "profile"),
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "invocation": bind(INVOCATION), "frozen_pair": pair,
        "classification": {
            "family": "real-owner adapter vocabulary",
            "mechanism": ("the release wrapper projected profile/member_diff "
                "through the B-light card module although those operations "
                "belong to the Capture substrate module"),
            "product_defect_established": False,
            "conversion": ("bind attribution operations to their real "
                "Capture-substrate owner; leave the frozen pair untouched")},
        "attempt_accounting": {"WPLTO_runs": 1, "product_links": 1,
            "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "retry_authorized": False,
        "resume_right": ("read-only attribution, Scope and Acceptance over "
                         "the SHA-bound pair; zero WPLTO and links")}
    FIRST_RED.write_bytes(canonical(value))
    print("v1.9.0 release: FIRST RED RECORDED pair=frozen")


def resume() -> None:
    configure()
    red = load(FIRST_RED)
    require(red["status"] ==
                "POST-LINK RED: RELEASE ATTRIBUTION ADAPTER OWNER"
            and red["frozen_pair"] == frozen_artifacts()
            and not DIFFERENCE.exists() and not RECEIPT.exists()
            and not BASE.SCOPE_RESULT.exists()
            and not BASE.ACCEPTANCE_RESULT.exists(),
            "v1.9 release Resume lifecycle drift")
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, check=True).stdout
    require(clean == "", "v1.9 release Resume requires committed conversion")
    before = frozen_artifacts()
    tree_before = R8.R7.tree_fingerprint(BUILD / "wplto")
    diff = attribution()
    DIFFERENCE.write_bytes(canonical(diff))
    gate = final_gate()
    processes = [run_child("_scope"), run_child("_accept")]
    after = frozen_artifacts()
    tree_after = R8.R7.tree_fingerprint(BUILD / "wplto")
    scope, acceptance = load(BASE.SCOPE_RESULT), load(BASE.ACCEPTANCE_RESULT)
    require(before == after and tree_before == tree_after
            and scope["status"] == acceptance["status"] == "PASS",
            "v1.9 release read-only Resume red")
    value = {"format": FORMAT, "recorded_on": "2026-08-30",
        "status": STATUS, "authority": authority(),
        "preflight": bind(PREFLIGHT_RECEIPT), "invocation": bind(INVOCATION),
        "first_red": bind(FIRST_RED), "attribution": diff,
        "attribution_receipt": bind(DIFFERENCE), "final_product": gate,
        "producer": bind(BASE.PRODUCER_RESULT),
        "scope": bind(BASE.SCOPE_RESULT),
        "acceptance": bind(BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "wplto_tree_before": tree_before, "wplto_tree_after": tree_after,
        "processes": processes,
        "attempt_accounting": {"WPLTO_runs": 1, "product_links": 1,
            "scope_runs": 1, "acceptance_runs": 1,
            "media_builds": 0, "device_contacts": 0},
        "resume_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "new_cards_consumed": 0},
        "owner_Ship": "DECIDABLE-NOT-INFERRED", "owner_Publish": "CLOSED",
        "media_authorized": False,
        "next": "independent review and explicit owner Ship"}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    check()
    print("v1.9.0 release: RESUME PASS WPLTO=0 link=0 banner=1.9.0")


def validate(value: dict[str, Any]) -> None:
    configure()
    diff = value["attribution"]["counts"]
    release = value["final_product"]["release_v1_9_0"]
    require(value["status"] == STATUS and value["authority"] == authority()
            and value["artifacts_before"] == value["artifacts_after"] ==
                frozen_artifacts()
            and canonical(value["attribution"]) == canonical(attribution())
            and all(count == 0 for name, count in diff.items()
                    if name.startswith("unexplained_"))
            and release["banner"]["final_composed_literal"] == EXPECTED_BANNER
            and release["delivered_consumer_wall"] == {
                "raw": 94, "seen": 94, "stored": 94, "taken": 94}
            and release["hardware_authority"]["free"] == {
                "symbol_slots": 109, "namepool_bytes": 1486}
            and release["claim_boundary"] == {
                "ships": ["lossless native-prompt input across forced collection",
                    "native prompt editor", "native INIT.L65",
                    "A0 recovery fast path"],
                "excludes": ["type-ahead during evaluation", "Comfort",
                    "Matcher/Blink", "$22 mechanism", "domain findings"],
                "pensioned_known_issues": ["v1.5 fast typing can lose input",
                    "v1.8 native prompt rejects cursor controls"]}
            and value["attempt_accounting"] == {"WPLTO_runs": 1,
                "product_links": 1, "scope_runs": 1, "acceptance_runs": 1,
                "media_builds": 0, "device_contacts": 0}
            and value["owner_Ship"] == "DECIDABLE-NOT-INFERRED"
            and value["owner_Publish"] == "CLOSED" and REPORT.is_file(),
            "v1.9 release receipt drift")


def check() -> None:
    validate(load(RECEIPT))
    print("v1.9.0 release: CHECK PASS banner=WORKBENCH-1.9.0")


def selftest() -> None:
    value = load(RECEIPT)
    cases = {
        "claim-Comfort": lambda x: x["final_product"]["release_v1_9_0"][
            "claim_boundary"]["ships"].append("Comfort"),
        "hide-byte": lambda x: x["attribution"]["counts"].update(
            unexplained_PRG_bytes=1),
        "stale-banner": lambda x: x["final_product"]["release_v1_9_0"][
            "banner"].update(final_composed_literal=PREDECESSOR_BANNER),
        "lose-consumer": lambda x: x["final_product"]["release_v1_9_0"].update(
            delivered_consumer_wall={"raw": 94, "seen": 94,
                                     "stored": 94, "taken": 0}),
        "infer-Ship": lambda x: x.update(owner_Ship="YES"),
        "spend-second-link": lambda x: x["attempt_accounting"].update(
            product_links=2),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate(trial)
        except ReleaseError:
            rejected.append(name)
    require(rejected == list(cases), "v1.9 release mutation survived")
    print(f"v1.9.0 release: SELFTEST PASS mutations={len(rejected)}")


def child(action: str) -> None:
    configure()
    if action == "_profile_probe":
        R8.CLIENT.SUBSTRATE.profile_probe_child()
    elif action == "_release_probe":
        R8.CLIENT.SUBSTRATE.release_probe_child()
    elif action == "_produce":
        BASE.produce_child()
    elif action == "_scope":
        BASE.scope_child()
    elif action == "_accept":
        BASE.acceptance_child()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "check-preflight",
        "build", "record-first-red", "resume", "check", "selftest",
        "_profile_probe", "_release_probe", "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    if action == "preflight":
        preflight()
    elif action == "check-preflight":
        check_preflight()
    elif action == "build":
        build()
    elif action == "record-first-red":
        record_first_red()
    elif action == "resume":
        resume()
    elif action == "check":
        check()
    elif action == "selftest":
        selftest()
    else:
        child(action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.9.0 release: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
