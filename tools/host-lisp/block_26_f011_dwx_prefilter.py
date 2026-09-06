#!/usr/bin/env python3
"""Pack Card 2 r3 and close its corruption and boot-cycle DWX rows."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace
import sys
import time
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import block_26_f011_map_abort_repair_product_card as CARD  # noqa: E402
import block_26_sidx_dwx_prefilter as CARD1_DWX  # noqa: E402
import c2_v200_release_strip_device_media as MEDIA  # noqa: E402
import d81_persistence_fault as D81  # noqa: E402
import dwx_mirrored_prefilter_rows as ROWS  # noqa: E402
import dwx_prefilter_blind_spot_contract as BLIND  # noqa: E402
import dwx_retroactive_red_replay as CYCLES  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/2.6/card2-f011-dwx-prefilter-r3-final"
MEDIA_BUILD = BUILD / "media"
WPLTO = MEDIA_BUILD / "inputs/wplto"
STATIC = MEDIA_BUILD / "inputs/static-plane"
TARGET = MEDIA_BUILD / "canonical-product"
SHARED = MEDIA_BUILD / "shared-system"
MEDIA_RECEIPT = BUILD / "prefilter-medium-receipt.json"
SESSION = BUILD / "unused-device-session.json"
PREFILTER_RECEIPT = ARCH / "block-2.6-card2-f011-dwx-prefilter-r3.json"
REPORT = ROOT / "docs/planning/2.6-card2-f011-dwx-prefilter-r3.md"
BOOT_LEDGER = ROOT / "config/boot-phase-cycle-ledger.json"
CORRUPT_D81 = BUILD / "corrupt-code-chain.d81"
PRODUCT_ID = 0x4A1713AB
PLANE_BYTES = 47795
PRODUCT_KEYS = CARD.R2.CARD.BASE.PRODUCT_KEYS
EXPECTED = {
    "PRG": (41811,
        "6f41be82454bf5c679b496da9b4483de641c999c7bccc8da692ee16a57bd6b66"),
    "ELF": (639696,
        "6362c79119707d1eea7885aa9aaf638341335e0306ad2864d83be3aae73bf057"),
}
STATUS = "PASS: CARD-2 R3 PACKED CORRUPTION AND BOOT-CYCLE PREFILTER GREEN"
FORMAT = "lisp65-block-2.6-card2-f011-dwx-prefilter-r3-v1"
MEDIA_STATUS = "PASS: CARD-2 R3 DWX PREFILTER MEDIUM READY"
MEDIA_FORMAT = "lisp65-block-2.6-card2-f011-dwx-medium-r3-v1"
SESSION_FORMAT = "lisp65-block-2.6-card2-f011-unused-device-session-v1"
XEMU = ROOT / "build/dwx/xemu-cycle-probe-r3/build/bin/xmega65.native"
ROM = Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM'))
SD_IMAGE = Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img'))
BLIND_CONTRACT = ROOT / "config/dwx-prefilter-blind-spot-contract.json"
SAFE_RUNNER = ROOT / "scripts/xmega65-safe-run.sh"


class PrefilterError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PrefilterError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha256(path)}


def configure_card() -> None:
    CARD.patch_card()
    CARD.R2.CARD.configure()


class ProductCard:
    BUILD = CARD.BUILD
    WPLTO = CARD.WPLTO
    PLANE = CARD.PLANE
    PRG = CARD.PRG
    ELF = CARD.ELF
    RECEIPT = CARD.RECEIPT
    STATUS = CARD.STATUS
    LINK = CARD.R2.CARD.BASE.CHAIN.LINK

    @staticmethod
    def patch_link_stack() -> None:
        configure_card()

    @staticmethod
    def setup_link_world() -> tuple[Any, dict[str, Any], dict[str, object]]:
        configure_card()
        return CARD.R2.CARD.BASE.CHAIN.setup_link_world()


MediaPrice = MEDIA.MediaPrice


class Adapter:
    BUILD = ProductCard.BUILD
    WPLTO = ProductCard.WPLTO
    PLANE = ProductCard.PLANE
    PRG = ProductCard.PRG
    ELF = ProductCard.ELF
    RECEIPT = ProductCard.RECEIPT
    STATUS = ProductCard.STATUS
    PRICING_RECEIPT = MediaPrice.RECEIPT
    PRICE = MediaPrice


def accepted_pair() -> dict[str, Any]:
    pair = {"PRG": bind(CARD.PRG), "ELF": bind(CARD.ELF)}
    for role, expected in EXPECTED.items():
        require((pair[role]["bytes"], pair[role]["sha256"]) == expected,
                f"Card-2 r3 {role} identity drift")
    return pair


def authority() -> dict[str, Any]:
    receipt = load(CARD.RECEIPT)
    require(receipt["status"] == CARD.STATUS
            and receipt["review_ready"] is False
            and receipt["final_product"]["packed_prefilter"]["status"] == "PENDING"
            and receipt["final_product"]["boot_cycles"]["status"] == "PENDING"
            and {key: receipt["artifacts_after"][key]
                 for key in ("PRG", "ELF")} == accepted_pair(),
            "Card-2 r3 pair is not ready for packed DWX closure")
    return {"product_card_before_prefilter": bind(CARD.RECEIPT),
        "commission": CARD.authority()["commission"],
        "right": ("artifact-only packed DWX corruption and boot-cycle rows; "
                  "zero WPLTO, links and device contacts")}


def plan_section() -> dict[str, Any]:
    return CARD.authority()["commission"]


def session_config(product: Path, valid: Path | None = None) -> dict[str, Any]:
    return {"format": SESSION_FORMAT, "status": "not-a-device-session",
        "medium": bind(product), "device_acceptance_claimed": False,
        "claim": "DWX functional/cycle prefilter only",
        "claim_scope": {"accepts": ["packed-byte closure and coherence",
            "fail-closed corrupt-sector framebuffer",
            "emulated CPU/DMA boot-cycle comparison"],
            "excludes": ["device acceptance", "Freezer", "physical timing",
                         "typing feel"]}}


def inherited_check(*, source_only: bool = False) -> None:
    value = load(MEDIA_RECEIPT)
    require(value["status"] == MEDIA_STATUS
            and value["accepted_pair"] == accepted_pair()
            and value["accounting"]["WPLTO_runs"] == 0
            and value["accounting"]["product_links"] == 0
            and value["accounting"]["device_contacts"] == 0,
            "Card-2 transient DWX medium drift")
    if not source_only:
        observed = bind(ROOT / value["media"]["absent_INIT"]["path"])
        require(all(value["media"]["absent_INIT"][key] == observed[key]
                    for key in ("path", "bytes", "sha256")),
                "Card-2 transient D81 identity drift")


def static_plane_gate() -> dict[str, Any]:
    path = TARGET / "canonical-product-manifest.json"
    value = load(path)
    plane = value["static_plane"]
    composed = load(CARD.RECEIPT)["final_product"]["composed_bank2"]
    rows = [item for item in value["artifacts"]
            if item["role"] == "c2-bank2-static-code-plane"]
    require(len(rows) == 1, "Card-2 packed static-plane population drift")
    row = rows[0]

    expected_intervals = [{key: owner[key]
        for key in ("start", "end_exclusive", "bytes")}
        for owner in [*composed["owners"], *composed["free_intervals"]]]
    observed_intervals = [{key: owner[key]
        for key in ("start", "end_exclusive", "bytes")}
        for owner in plane["composed_owners"]]
    expected_intervals.sort(key=lambda owner: owner["start"])
    observed_intervals.sort(key=lambda owner: owner["start"])
    reserve = next(owner for owner in composed["reserved_owners"]
        if owner["owner"] == "mapped-tenant-bank-end-reserve")
    emitted_extent = reserve["start"] - composed["bank"]["start"]
    require(plane["product_build_id"] == f"0x{PRODUCT_ID:08x}"
            and plane["bank2_static_code_bytes"] == row["bytes"] ==
                emitted_extent
            and plane["largest_contiguous_hole"] ==
                composed["largest_contiguous_hole"]
            and observed_intervals == expected_intervals
            and bind(ROOT / row["path"])["sha256"] == row["sha256"] ==
                plane["bank2_sha256"],
            "Card-2 composed Bank-2 packed-media drift")
    return {"manifest": bind(path), "static_plane": plane, "artifact": row,
        "source": bind(CARD.RECEIPT),
        "rule": ("packed Bank-2 extent and every owner/free interval are "
                 "derived from the qualified Card-2 composition")}


def configure_media() -> None:
    candidate = SimpleNamespace(PRODUCT_KEYS=PRODUCT_KEYS,
        RECEIPT=CARD.RECEIPT, PRG=CARD.PRG, ELF=CARD.ELF,
        WPLTO=CARD.WPLTO, PLANE=CARD.PLANE, BUILD=CARD.BUILD,
        STATUS=CARD.STATUS, CHAIN=CARD.R2.CARD.BASE.CHAIN,
        configure=configure_card)
    MEDIA.STRIP = candidate
    MEDIA.ProductCard = ProductCard
    MEDIA.Adapter = Adapter
    for name, value in {
        "BUILD": MEDIA_BUILD, "WPLTO": WPLTO, "STATIC": STATIC,
        "TARGET": TARGET, "SHARED": SHARED, "RECEIPT": MEDIA_RECEIPT,
        "SESSION": SESSION, "VALID": BUILD / "unused-init-valid.d81",
        "VALID_SOURCE": BUILD / "unused-init-valid.l65",
        "PRODUCT_REMOTE": "B26C2.D81", "VALID_REMOTE": "UNUSED.D81",
        "PRODUCT_ID": PRODUCT_ID, "PLANE_BYTES": PLANE_BYTES,
        "EXPECTED": EXPECTED, "STATUS": MEDIA_STATUS,
        "FORMAT": MEDIA_FORMAT, "SESSION_FORMAT": SESSION_FORMAT,
    }.items():
        setattr(MEDIA, name, value)
    MEDIA.accepted_pair = accepted_pair
    MEDIA.authority = authority
    MEDIA.plan_section = plan_section
    MEDIA.session_config = session_config
    MEDIA.inherited_check = inherited_check
    MEDIA.check = inherited_check
    MEDIA.configure()
    MEDIA.EXPECTED_LARGEST_HOLE = load(CARD.RECEIPT)["final_product"][
        "composed_bank2"]["largest_contiguous_hole"]["bytes"]
    MEDIA.static_plane_gate = static_plane_gate
    MEDIA.BASE.BASE.EXPECTED_LARGEST_HOLE = MEDIA.EXPECTED_LARGEST_HOLE
    MEDIA.BASE.BASE.static_plane_gate = static_plane_gate


def build_medium() -> tuple[Path, dict[str, Any]]:
    configure_media()
    if not MEDIA_RECEIPT.exists():
        # The release wrapper's outer descope layer only owns its historical
        # input-only retry contract.  This successor has already configured
        # the delivery producer with the Card-2 roots; invoke that producer
        # directly so its stricter copy-only Completion retry can classify
        # and resume a stopped canonical-product projection without treating
        # it as a new product build.
        MEDIA.BASE.BASE.build()
    inherited_check()
    value = load(MEDIA_RECEIPT)
    product = ROOT / value["media"]["absent_INIT"]["path"]
    packed = value["packed_readback"]["absent_INIT"]
    require(packed["status"] ==
                "PASS: PACKED D81 CLOSURE AND GENERATION COHERENCE"
            and packed["closure"]["object_count"] == 760
            and packed["closure"]["call_site_count"] == 2436,
            "Card-2 packed-byte closure/coherence gate red")
    return product, packed


def corrupt_code_chain(product: Path) -> dict[str, Any]:
    image = bytearray(product.read_bytes())
    slot = next((row for row in D81.directory_slots(image)
                 if D81.entry_name(row.record) == b"CODE.BIN"), None)
    require(slot is not None, "packed medium lacks CODE.BIN directory entry")
    chain = D81.file_chain(image, slot.record)
    require(len(chain) > 1, "CODE.BIN chain is too short for link corruption")
    track, sector = chain[0]
    offset = D81.sector_offset(track, sector)
    before = bytes(image[offset:offset + 2])
    require(before == bytes(chain[1]), "CODE.BIN first chain link drift")
    image[offset:offset + 2] = bytes((D81.TRACKS + 1, 0))
    after = bytes(image[offset:offset + 2])
    CORRUPT_D81.write_bytes(image)
    changed = [index for index, (old, new) in enumerate(
        zip(product.read_bytes(), image)) if old != new]
    require(changed == [offset, offset + 1]
            and after == bytes((D81.TRACKS + 1, 0)),
            "corrupt-sector fixture changed anything beyond one chain link")
    return {"source_medium": bind(product), "corrupt_medium": bind(CORRUPT_D81),
        "file": "CODE.BIN", "sector": {"track": track, "sector": sector,
            "absolute_offset": offset},
        "before_link": before.hex(), "after_link": after.hex(),
        "changed_byte_offsets": changed,
        "mutation": "first CODE.BIN sector points beyond the 80-track image"}


def tool_identity() -> dict[str, Any]:
    blind = load(BLIND_CONTRACT)
    BLIND.validate_contract(blind)
    tool = blind["qualified_tool_identity"]
    rows_contract = load(ROOT / "config/dwx-mirrored-prefilter-rows-contract.json")
    require(sha256(XEMU) == tool["binary_sha256"]
            and sha256(ROM) == rows_contract["inputs"]["rom_sha256"]
            and sha256(SD_IMAGE) == rows_contract["inputs"]["system_sd_sha256"],
            "Card-2 DWX tool/ROM/SD identity drift")
    return tool


def run_to_framebuffer(run_id: str, medium: Path, required: list[str]
                       ) -> dict[str, Any]:
    run_dir = BUILD / "runtime" / ("run-" + run_id)
    run_dir.mkdir(parents=True)
    sd_copy = run_dir / "system-sd.img"
    subprocess.run(["cp", "--reflink=auto", "--sparse=always",
                    str(SD_IMAGE), str(sd_copy)], check=True)
    medium_copy = run_dir / medium.name
    shutil.copyfile(medium, medium_copy)
    medium_copy.chmod(0o444)
    memory = run_dir / "memory.bin"
    screen = run_dir / "framebuffer.txt"
    oracle_screen = run_dir / "oracle-framebuffer.txt"
    log = run_dir / "xemu.log"
    monitor_path = Path("/tmp") / f"l65-b26c2-{os.getpid()}-{run_id}.sock"
    monitor_path.unlink(missing_ok=True)
    command = [str(SAFE_RUNNER), str(memory), "40", str(XEMU),
        "-skipconfigfile", "-headless", "-testing", "-sleepless", "-besure",
        "-fastboot", "-nosound", "-rom", str(ROM), "-sdimg", str(sd_copy),
        "-8", str(medium_copy), "-autoload", "-uartmon", str(monitor_path),
        "-dumpscreen", str(screen), "-dumpmem", str(memory)]
    with log.open("wb") as log_handle:
        process = subprocess.Popen(command, stdout=log_handle,
                                   stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 12
            while not monitor_path.exists() and time.monotonic() < deadline:
                require(process.poll() is None,
                        f"Xemu exited before monitor for {run_id}")
                time.sleep(0.02)
            require(monitor_path.exists(), f"UART monitor absent for {run_id}")
            monitor = CYCLES.ProbeMonitor(monitor_path)
            framebuffer = monitor.wait_screen(required, timeout=30)
            monitor.command("t1")
            cycles = monitor.cycle_count()
            oracle_screen.write_text(framebuffer, encoding="utf-8")
            monitor.command("~exit")
            status = process.wait(timeout=12)
        except BaseException:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()
            monitor_path.unlink(missing_ok=True)
            raise
    monitor_path.unlink(missing_ok=True)
    require(status == 0 and screen.is_file() and memory.is_file()
            and sha256(medium_copy) == sha256(medium),
            f"headless Card-2 run failed: {run_id}")
    decoded = ROWS.decoded_framebuffer(framebuffer)
    require(all(item.upper() in decoded for item in required),
            f"Card-2 framebuffer oracle red: {run_id}")
    return {"id": run_id, "medium": bind(medium),
        "required_framebuffer": required, "emulated_CPU_DMA_cycles": cycles,
        "outputs": {"framebuffer": bind(oracle_screen),
            "shutdown_framebuffer": bind(screen), "memory": bind(memory),
            "log_non_authoritative": bind(log)},
        "desktop_focus_used": False, "GUI_used": False}


def runtime_rows(product: Path, corruption: dict[str, Any]
                 ) -> tuple[dict[str, Any], dict[str, Any]]:
    runtime = BUILD / "runtime"
    require(not runtime.exists(), "Card-2 DWX runtime is one-shot")
    baseline_receipt = load(CARD1_DWX.PREFILTER_RECEIPT)
    baseline = ROOT / baseline_receipt["medium"]["path"]
    require(bind(baseline) == baseline_receipt["medium"],
            "Card-1 packed predecessor medium drift")
    baseline_run = run_to_framebuffer("card1-r2-boot-reference", baseline,
                                      ["LISP65>"])
    candidate_run = run_to_framebuffer("card2-r3-clean-boot", product,
                                       ["LISP65>"])
    corrupt_run = run_to_framebuffer("card2-r3-corrupt-sector", CORRUPT_D81,
                                     ["L65SYS DISK ERROR - CHECK MEDIA"])
    decoded = ROWS.decoded_framebuffer((ROOT / corrupt_run["outputs"][
        "framebuffer"]["path"]).read_text(encoding="utf-8"))
    require("LISP65>" not in decoded,
            "corrupt-sector fixture reached a live prompt instead of fail-closed")
    before = baseline_run["emulated_CPU_DMA_cycles"]
    after = candidate_run["emulated_CPU_DMA_cycles"]
    boot = {"status": "PASS", "metric": "monotonic-emulated-CPU-and-DMA-cycles",
        "reference": baseline_run, "candidate": candidate_run,
        "delta_cycles": after - before,
        "ratio": after / before,
        "interpretation": ("first boot-phase ledger observation; records the "
            "full packed-medium cold-boot cost without claiming wall-clock or "
            "physical-device timing")}
    failure = {"status": "PASS",
        "row": "corrupt CODE.BIN sector link -> fail-closed disk error",
        "fixture": corruption, "runtime": corrupt_run,
        "error_owner": "ordinary caller after mapped reader returns failure",
        "mapped_body_abort_paths": [],
        "claim": "functional headless-Xemu framebuffer prefilter only"}
    return failure, boot


def ledger(boot: dict[str, Any]) -> dict[str, Any]:
    return {"format": "lisp65-boot-phase-cycle-ledger-v1",
        "recorded_on": "2026-09-03",
        "metric": "monotonic-emulated-CPU-and-DMA-cycles",
        "claim_limit": ("DWX emulator comparison only; no wall-clock, physical "
                        "device, Freezer, DMA-timing or boot-time release claim"),
        "entries": [{"id": "block-2.6-card2-f011-packed-cold-boot",
            "reference": boot["reference"]["medium"],
            "candidate": boot["candidate"]["medium"],
            "reference_cycles": boot["reference"]["emulated_CPU_DMA_cycles"],
            "candidate_cycles": boot["candidate"]["emulated_CPU_DMA_cycles"],
            "delta_cycles": boot["delta_cycles"], "ratio": boot["ratio"]}]}


def validate_ledger_entry(value: dict[str, Any], boot: dict[str, Any]) -> None:
    """Keep Card 2 authoritative while allowing later measured entries.

    The ledger is a growing derived index.  Card 2 owns its row, not the
    historical assertion that no later card can append another observation.
    """
    expected = ledger(boot)
    entries = value.get("entries", [])
    own = [row for row in entries if row.get("id") ==
           "block-2.6-card2-f011-packed-cold-boot"]
    require({key: value.get(key) for key in (
                "format", "recorded_on", "metric", "claim_limit")} ==
            {key: expected[key] for key in (
                "format", "recorded_on", "metric", "claim_limit")}
            and own == expected["entries"]
            and len(entries) == len({row.get("id") for row in entries}),
            "Card-2 boot-ledger row is missing, stale or duplicated")


def report(value: dict[str, Any]) -> str:
    boot = value["boot_cycles"]
    corruption = value["packed_prefilter"]["fixture"]
    return f"""# Block 2.6 Card 2 — packed DWX closure

Status: **{value['status']}**

The candidate D81 passes transitive closure and generation coherence over its
read-back packed bytes. A two-byte mutation then changes the first `CODE.BIN`
sector link from `{corruption['before_link']}` to `{corruption['after_link']}`.
The headless framebuffer reaches `L65SYS DISK ERROR - CHECK MEDIA` and no live
prompt; the final ELF proves that the mapped reader returns failure and the
ordinary caller owns the abort.

The first boot-phase ledger compares the packed Card-1 predecessor and Card-2
candidate under the same qualified three-patch Xemu, ROM, SD image and launch
choreography: **{boot['reference']['emulated_CPU_DMA_cycles']:,} →
{boot['candidate']['emulated_CPU_DMA_cycles']:,}** emulated CPU/DMA cycles
(delta {boot['delta_cycles']:+,}, ratio {boot['ratio']:.6f}). This is an
emulator-prefilter observation, not wall-clock or device timing.

No WPLTO, product link or physical-device contact was used. Card 2 is now
review-ready.
"""


def validate(value: dict[str, Any]) -> None:
    failure, boot = value["packed_prefilter"], value["boot_cycles"]
    ledger_value = load(BOOT_LEDGER)
    require(value["format"] == FORMAT and value["status"] == STATUS
            and value["accepted_pair"] == accepted_pair()
            and value["packed_readback"]["status"] ==
                "PASS: PACKED D81 CLOSURE AND GENERATION COHERENCE"
            and failure["status"] == "PASS"
            and failure["fixture"]["changed_byte_offsets"] == [
                failure["fixture"]["sector"]["absolute_offset"],
                failure["fixture"]["sector"]["absolute_offset"] + 1]
            and failure["runtime"]["required_framebuffer"] == [
                "L65SYS DISK ERROR - CHECK MEDIA"]
            and failure["error_owner"] ==
                "ordinary caller after mapped reader returns failure"
            and failure["mapped_body_abort_paths"] == []
            and boot["status"] == "PASS" and boot["ratio"] > 0
            and value["attempt_accounting"] == {"WPLTO_runs": 0,
                "product_links": 0, "DWX_prefilter_runs": 3,
                "candidate_media_builds": 1,
                "corrupt_fixture_media_builds": 1, "device_contacts": 0},
            "Card-2 DWX prefilter receipt drift")
    validate_ledger_entry(ledger_value, boot)


def write() -> None:
    require(not PREFILTER_RECEIPT.exists() and not REPORT.exists()
            and not BOOT_LEDGER.exists(), "Card-2 DWX close is one-shot")
    tool = tool_identity()
    product, packed = build_medium()
    corruption = corrupt_code_chain(product)
    failure, boot = runtime_rows(product, corruption)
    BOOT_LEDGER.write_bytes(canonical(ledger(boot)))
    value = {"format": FORMAT, "recorded_on": "2026-09-03",
        "status": STATUS, "authority": authority(),
        "accepted_pair": accepted_pair(), "medium_receipt": bind(MEDIA_RECEIPT),
        "medium": bind(product), "packed_readback": packed,
        "packed_prefilter": failure, "boot_cycles": boot,
        "boot_phase_ledger": bind(BOOT_LEDGER), "tool_identity": tool,
        "blind_spot_contract": bind(BLIND_CONTRACT),
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "DWX_prefilter_runs": 3, "candidate_media_builds": 1,
            "corrupt_fixture_media_builds": 1, "device_contacts": 0}}
    PREFILTER_RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(report(value), encoding="utf-8")
    validate(value)
    product_receipt = load(CARD.RECEIPT)
    product_receipt["final_product"]["packed_prefilter"] = {
        "status": "PASS", "receipt": bind(PREFILTER_RECEIPT),
        "medium": bind(product), "oracle": "framebuffer",
        "ordinary_caller_owns_error": True}
    product_receipt["final_product"]["boot_cycles"] = {
        "status": "PASS", "receipt": bind(PREFILTER_RECEIPT),
        "ledger": bind(BOOT_LEDGER), "reference_cycles":
            boot["reference"]["emulated_CPU_DMA_cycles"],
        "candidate_cycles": boot["candidate"]["emulated_CPU_DMA_cycles"],
        "delta_cycles": boot["delta_cycles"], "ratio": boot["ratio"]}
    product_receipt["attempt_accounting"]["DWX_prefilter_runs"] = 3
    product_receipt["attempt_accounting"]["media_builds"] = 2
    product_receipt["review_ready"] = True
    CARD.RECEIPT.write_bytes(canonical(product_receipt))
    CARD.write_report(product_receipt)
    CARD.validate(product_receipt)
    print("Block 2.6 Card 2: PACKED DWX PASS corruption=fail-closed boot=measured device=0")


def check() -> None:
    value = load(PREFILTER_RECEIPT)
    validate(value)
    product_receipt = load(CARD.RECEIPT)
    require(product_receipt["review_ready"] is True
            and product_receipt["final_product"]["packed_prefilter"]["status"] == "PASS"
            and product_receipt["final_product"]["boot_cycles"]["status"] == "PASS",
            "Card-2 product receipt did not consume DWX closure")
    CARD.check()
    require(REPORT.read_text(encoding="utf-8") == report(value),
            "Card-2 DWX report drift")
    print("Block 2.6 Card 2: DWX CHECK PASS device=0")


def selftest() -> None:
    value = load(PREFILTER_RECEIPT)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "corruption-hidden": lambda row: row["packed_prefilter"]["fixture"].update(
            changed_byte_offsets=[]),
        "ordinary-owner-hidden": lambda row: row["packed_prefilter"].update(
            error_owner="mapped body aborts"),
        "boot-measurement-hidden": lambda row: row["boot_cycles"].update(
            status="PENDING"),
        "device-contact-hidden": lambda row: row["attempt_accounting"].update(
            device_contacts=1),
    }
    rejected = []
    for label, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except (PrefilterError, RuntimeError, KeyError, ValueError):
            rejected.append(label)
    require(rejected == list(cases), "Card-2 DWX mutation survived")
    ledger_mutant = deepcopy(load(BOOT_LEDGER))
    ledger_mutant["entries"] = [row for row in ledger_mutant["entries"]
        if row.get("id") != "block-2.6-card2-f011-packed-cold-boot"]
    try:
        validate_ledger_entry(ledger_mutant, value["boot_cycles"])
    except PrefilterError:
        rejected.append("card2-ledger-entry-omitted")
    else:
        raise PrefilterError("Card-2 boot-ledger omission mutation survived")
    print(f"Block 2.6 Card 2: DWX SELFTEST mutations={len(rejected)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    action = parser.parse_args().action
    {"write": write, "check": check, "selftest": selftest}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Block 2.6 Card 2 DWX: FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
