#!/usr/bin/env python3
"""Pack artifact-only v2.0 Comfort media and bind its owner session."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v17_comfort_phase1b_acceptance_media as V17  # noqa: E402
import c2_v190_release_terminal_d5 as D5  # noqa: E402
import c2_v200_comfort_return_card as CARD  # noqa: E402
import c2_v200_symbol22_build_id_device_media as R4_MEDIA  # noqa: E402
import c2_v200_symbol22_build_id_rebind as R4  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
PLAN_HEADER = (
    "## Independent review — Comfort return card and device-session authority — 2026-08-31")
DOMAIN = ROOT / "config/public-surface-domain-contract.json"
CARD_RECEIPT = CARD.RECEIPT
R4_MEDIA_RECEIPT = ARCH / (
    "c2.3-v2.0-symbol22-build-id-device-media-receipt.json")
SOURCE_PRODUCT = R4_MEDIA.BUILD / "shared-system/lisp65-product.d81"
V16_MANIFEST = R4_MEDIA.BUILD / "library-inputs/v17core.manifest.json"
COMFORT_MANIFEST = CARD.LIBRARY.with_suffix(".manifest.json")
BUILD = ROOT / "build/c2.3/v2.0-comfort-return-media"
PRODUCT = BUILD / "shared-system/lisp65-product.d81"
LIBRARY = BUILD / "library"
LIBRARY_D81 = LIBRARY / "lisp65-library.d81"
INDEX = LIBRARY / "l65index"
RECEIPT = ARCH / "c2.3-v2.0-comfort-return-media-receipt.json"
SESSION = ROOT / "config/c2-v200-comfort-return-device-session.json"
PRODUCT_REMOTE = "V20CFRP.D81"
LIBRARY_REMOTE = "V20CFRL.D81"
PRODUCT_ID = 0x8C6CC520
FORMAT = "lisp65-c2-v200-comfort-return-media-v1"
SESSION_FORMAT = "lisp65-c2-v200-comfort-return-device-session-v1"
STATUS = "PASS: V2.0 COMFORT RETURN MEDIA AND SESSION READY"
EVIDENCE_ERA = "0e846eb0"
PRODUCT_D81_SHA256 = (
    "e20c161509f790aeecd1f6fa008e84bd2020f303a26500a41df49b9c980b0d0c")

PATTERN = "01234567012345670123456701234567"
PASSES = 6
FINAL_TEXT = "abcdefg"
CONTROLLER = (
    "(progn (setq s (read-line)) (print (string-length s)) (wait 16383))")
NURSERY_CELLS = 192
CELLS_PER_PRINTABLE = 1
PRINTABLE_INSERTIONS = PASSES * len(PATTERN) + len(FINAL_TEXT)
DELETE_EVENTS = PASSES * len(PATTERN)
RETURN_EVENTS = 1
PHYSICAL_EVENTS = PRINTABLE_INSERTIONS + DELETE_EVENTS + RETURN_EVENTS
EXPECTED_COUNTER = PHYSICAL_EVENTS % 256


class ComfortMediaError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ComfortMediaError(message)


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


def evidence_era_json(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    relative = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{EVIDENCE_ERA}:{relative}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    value = json.loads(raw)
    require(isinstance(value, dict), f"evidence-era JSON object required: {path}")
    return value, {"path": relative, "bytes": len(raw),
                   "sha256": hashlib.sha256(raw).hexdigest()}


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(canonical(value))
    temporary.replace(path)


def section_authority() -> dict[str, Any]:
    text = PLAN.read_text(encoding="utf-8")
    require(text.count(PLAN_HEADER) == 1, "Comfort media authority drift")
    section = PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    folded = " ".join(section.lower().replace("`", "").replace(
        "*", "").split())
    for token in ("artifact-only media", "seven pre-bound groups",
                  "error-raised", "raw = seen = stored = taken",
                  "five $22 latch state bytes", "32/384"):
        require(token in folded, f"Comfort media authority absent: {token}")
    raw = section.encode()
    return {"path": PLAN.relative_to(ROOT).as_posix(),
            "section": PLAN_HEADER, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def accepted_pair() -> dict[str, Any]:
    return CARD.accepted_pair()


def card_authority() -> dict[str, Any]:
    card = load(CARD_RECEIPT)
    pair = accepted_pair()
    require(card["status"] == CARD.STATUS
            and card["artifacts_before"] == card["artifacts_after"] == pair
            and card["accounting"] == {"WPLTO_runs": 0, "product_links": 0,
                "media_builds": 0, "device_contacts": 0}
            and card["source_world"]["cases"] == 9
            and card["input"]["loss"]["linked_events_drained"] == 94
            and card["input"]["responsiveness"]["margin_percent"] >= 25.0
            and card["capacity"]["after_loading_comfort"]
                == {"symbol_slots": 105, "namepool_bytes": 1435},
            "Comfort card is not media-ready")
    return {"independent_review": section_authority(),
            "product_card": bind(CARD_RECEIPT),
            "right": "artifact-only media and one bounded seven-group session",
            "accounting": {"WPLTO_runs": 0, "product_links": 0,
                           "product_cards": 0, "device_contacts": 0}}


def product_projection() -> dict[str, Any]:
    source_receipt = load(R4_MEDIA_RECEIPT)
    source = source_receipt["media"]["product"]
    require(source_receipt["status"] == R4_MEDIA.STATUS
            and source_receipt["accepted_pair"] == accepted_pair()
            and source_receipt["same_world_pair"]["result"] == "same-world-pair"
            and bind(SOURCE_PRODUCT) == source
            and source["sha256"] == PRODUCT_D81_SHA256,
            "r4 product medium is not a qualified projection source")
    PRODUCT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE_PRODUCT, PRODUCT)
    require(bind(PRODUCT)["sha256"] == source["sha256"],
            "artifact-only product projection changed a byte")
    return {"source_media_receipt": bind(R4_MEDIA_RECEIPT),
            "source_product": source, "projected_product": bind(PRODUCT),
            "operation": "byte-identical artifact copy; no product media rebuild"}


def library_media() -> dict[str, Any]:
    card = load(CARD_RECEIPT)
    comfort = card["library"]
    require(bind(COMFORT_MANIFEST) == comfort["manifest"]
            and comfort["objects"] == 4 and comfort["code_bytes"] == 815
            and comfort["new_interned_names"]
                == ["%repl-prompt", "%repl-read", "%repl-step", "repl",
                    "repl-comfort"],
            "requalified Comfort artifact drift")
    require(load(V16_MANIFEST)["provides"] == ["v16core"],
            "current-plane v16core manifest drift")

    specs = (
        ("v16core", "v16core", "v16core", V16_MANIFEST, ()),
        ("repl-comfort", "repl", "repl", COMFORT_MANIFEST, (0,)),
    )
    LIBRARY.mkdir(parents=True, exist_ok=True)
    placeholder: list[dict[str, Any]] = []
    artifacts: dict[str, bytes] = {}
    paths: list[tuple[Path, str]] = []
    for ordinal, spec in enumerate(specs):
        row, artifact = V17.LIBMEDIA.measured(
            spec, (1, ordinal + 1), PRODUCT_ID)
        name = spec[0]
        placeholder.append(row)
        artifacts[name] = artifact
        path = LIBRARY / f"{name}.l65s"
        path.write_bytes(artifact)
        paths.append((path, name))

    seed_index = LIBRARY / "l65index.seed"
    seed_index.write_bytes(V17.LIBMEDIA.L65I.encode_index(placeholder))
    seed = LIBRARY / "library.seed.d81"
    V17.LIBMEDIA.build_library_d81(seed, seed_index, paths)
    locators = V17.LIBMEDIA.L65I.d81_locators(seed)
    rows: list[dict[str, Any]] = []
    for spec in specs:
        row, artifact = V17.LIBMEDIA.measured(
            spec, locators[spec[0]], PRODUCT_ID)
        require(artifact == artifacts[spec[0]],
                f"library artifact changed with locator: {spec[0]}")
        rows.append(row)
    encoded = V17.LIBMEDIA.L65I.encode_index(rows)
    INDEX.write_bytes(encoded)
    decoded = V17.LIBMEDIA.L65I.decode_index(
        encoded, artifacts, artifact_build_id=PRODUCT_ID)
    V17.LIBMEDIA.build_library_d81(LIBRARY_D81, INDEX, paths)
    visible = V17.LIBMEDIA.L65I.D81.visible_files(LIBRARY_D81.read_bytes())
    require(visible == {b"L65INDEX": encoded,
                        **{name.upper().encode(): raw
                           for name, raw in artifacts.items()}},
            "Comfort library visible-file truth drift")
    contracts = {name: V17.LIBMEDIA.resolver_contract(decoded, name)
                 for name in artifacts}
    require(contracts["repl-comfort"]["actual_resolver_order"] == [0, 1],
            "Comfort dependency closure drift")
    mutant = deepcopy(decoded)
    mutant[1]["dependencies"] = []
    mutations = V17.LIBMEDIA.resolver_contract_mutation_gate(
        mutant, "repl-comfort")
    seed.unlink(); seed_index.unlink()
    return {"status": "PASS: CURRENT-PLANE COMFORT LIBRARY PACKED",
        "product_build_id": f"0x{PRODUCT_ID:08x}",
        "D81": bind(LIBRARY_D81), "index": bind(INDEX),
        "artifacts": {name: bind(LIBRARY / f"{name}.l65s")
                      for name in artifacts},
        "manifests": {"v16core": bind(V16_MANIFEST),
                      "repl-comfort": bind(COMFORT_MANIFEST)},
        "index_rows": decoded, "resolver_contracts": contracts,
        "resolver_mutations_rejected": mutations,
        "visible_files": sorted(name.decode() for name in visible)}


def pair_identity() -> dict[str, Any]:
    R4_MEDIA.configure()
    value = R4_MEDIA.BASE.MEDIA.PREP.PAIR.pair_identity(PRODUCT, LIBRARY_D81)
    require(value["result"] == "same-world-pair"
            and value["product_build_id"] == f"0x{PRODUCT_ID:08x}"
            and value["index_rows"] == 2
            and value["row_names"] == ["v16core", "repl-comfort"]
            and set(value["library_build_ids"].values())
                == {f"0x{PRODUCT_ID:08x}"},
            "Comfort product/library world mismatch")
    return value


def error_trigger() -> dict[str, Any]:
    # This media/session receipt is sealed in its own pre-Tier-1 world.  Its
    # trigger remains valid, but its authority must not silently cross into the
    # living successor contract merely because the path name is unchanged.
    contract, authority = evidence_era_json(DOMAIN)
    rows = [row for row in contract["rows"] if row["name"] == "+"]
    require(len(rows) == 1, "domain-contract + population drift")
    cell = rows[0]["cells"]["nil"]
    require(cell["classification"] == "error-raised"
            and cell["error"] == "TypeError",
            "selected abort stimulus is not guaranteed error-raised")
    return {"form": "(+ nil 32)", "function": "+", "domain": "nil",
            "classification": cell["classification"], "error": cell["error"],
            "detail": cell["detail"], "authority": authority,
            "forbidden_surrogate": "(>= nil 32)"}


def read_ranges() -> dict[str, Any]:
    truth = ElfTruth.read(R4.ELF,
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    names = {
        "raw": "C2K_INPUT_EVENTS_RAW", "seen": "C2K_INPUT_EVENTS_SEEN",
        "stored": "C2K_INPUT_EVENTS_STORED",
        "taken": "C2K_INPUT_EVENTS_TAKEN",
    }
    counters = {key: truth.symbol(name).value for key, name in names.items()}
    latch = truth.symbol("lisp65_symbol22_latch_state").value
    payload = truth.symbol("c2_symbol22_repl_buf").value
    nsym = truth.symbol("nsym").value
    npool = truth.symbol("npool").value
    require(counters == {"raw": 0xBCFC, "seen": 0xBCFD,
                         "stored": 0xBCFE, "taken": 0xBCFF}
            and (latch, payload, nsym, npool)
                == (0xC34D, 0xBC89, 0x005A, 0xBE1A),
            "r4 stopped-state address world drift")
    return {
        "input_counters": {key: f"0x{value:04X}"
                           for key, value in counters.items()},
        "latch": {"address": f"0x{latch:04X}", "bytes": 5,
            "layout": ["tag", "caller-lo", "caller-hi", "name-lo", "name-hi"],
            "committed_tag": "0xA5"},
        "conditional_latch_payload": {"address": f"0x{payload:04X}",
            "bytes": 34, "when": "read in the same stop if tag is 0xA5"},
        "D5": {"nsym": {"address": f"0x{nsym:04X}", "bytes": 2},
               "npool": {"address": f"0x{npool:04X}", "bytes": 2},
               "encoding": "little-endian"},
    }


def forced_collection() -> dict[str, Any]:
    require(len(CONTROLLER) == 67 and len(PATTERN) == 32
            and PRINTABLE_INSERTIONS == 199
            and PRINTABLE_INSERTIONS * CELLS_PER_PRINTABLE > NURSERY_CELLS
            and PHYSICAL_EVENTS == 392 and EXPECTED_COUNTER == 136,
            "forced-collection arithmetic drift")
    return {
        "controller": CONTROLLER,
        "controller_purpose": (
            "nested read-line establishes one counter origin; print is the "
            "numeric oracle; wait holds the stopped cutpoint"),
        "nursery_cells": NURSERY_CELLS,
        "heap_cells_per_printable": CELLS_PER_PRINTABLE,
        "required_printable_insertions_independent_of_incoming_phase": 193,
        "printable_insertions": PRINTABLE_INSERTIONS,
        "proof": "199 * 1 > 192; at least one collection under armed Capture",
        "passes": PASSES, "pattern": PATTERN,
        "visible_groups": [PATTERN[index:index + 8]
                           for index in range(0, len(PATTERN), 8)],
        "delete_events_per_pass": 32,
        "pace": {"passes_1_to_2": "ordinary", "passes_3_to_6": "fast"},
        "final_text": FINAL_TEXT, "numeric_oracle": 7,
        "event_arithmetic": {"printable": PRINTABLE_INSERTIONS,
            "delete": DELETE_EVENTS, "return": RETURN_EVENTS,
            "physical": PHYSICAL_EVENTS, "counter_width_bits": 8,
            "wraps": 1, "expected_each_modulo_256": EXPECTED_COUNTER}}


def session_config() -> dict[str, Any]:
    ranges = read_ranges()
    collection = forced_collection()
    trigger = error_trigger()
    return {
        "format": SESSION_FORMAT, "recorded_on": "2026-08-31",
        "status": "READY: OWNER V2.0 COMFORT RETURN CONTACT",
        "claim_scope": {
            "accepts": ["v2.0-Comfort-return-hardware-acceptance"],
            "green_consequence": "Comfort accepted; Block 3 may open",
            "excludes": ["Block-3-acceptance", "latch-retention-decision",
                         "release", "domain-fixes"],
        },
        "media": {
            "product": {**bind(PRODUCT), "remote_name": PRODUCT_REMOTE},
            "library": {**bind(LIBRARY_D81), "remote_name": LIBRARY_REMOTE},
        },
        "world": {"qualified_pair": accepted_pair(),
                  "same_world_pair": pair_identity(),
                  "sealed_comfort_commit": CARD.SEALED_COMFORT_COMMIT,
                  "product_build_id": f"0x{PRODUCT_ID:08x}"},
        "choreography": {
            "fresh_BASIC_first": True,
            "both_media_uploaded_and_read_back_before_boot": True,
            "library_mounted_physically_through_freezer": True,
            "product_mounted_last": True,
            "physical_owner_keyboard_only_after_boot": True,
            "one_form_per_submission": True,
            "automated_device_access": "one final stop and read-only ranges",
            "stops": 1, "resumes_after_stop": 0,
        },
        "execution_order": ["C1", "C2", "C3", "C5", "C4", "C6", "C7"],
        "rows": [
            {"id": "C1", "group": "entry and prompts", "actions": [
                "cold boot product and mount the prepared library physically",
                "at lisp65> submit (require 'repl-comfort), then (repl)",
                "at l65> submit one empty line; at lisp65> submit (repl) again"],
             "expect": ["require returns t", "Comfort prompt is l65>",
                        "empty balanced line returns to one native lisp65>",
                        "second entry returns to l65>"]},
            {"id": "C2", "group": "evaluation, multiline, history, over-close",
             "actions": [
                "submit (list 1 3)",
                "submit (+ 10 on one physical line and 32) on the next",
                "submit (list 7 8), then press Up and Return",
                "submit one unmatched closing parenthesis"],
             "expect": ["(1 3)", "42", "(7 8) is recalled and evaluated again",
                        "over-close is rejected before evaluation and l65> remains live"]},
            {"id": "C3", "group": "A0 abort recovery", "trigger": trigger,
             "actions": [f"at l65> submit {trigger['form']}",
                         "after native recovery submit (repl) once"],
             "expect": ["*** vm: type error", "no red frame",
                        "one native lisp65> appears practically immediately",
                        "Comfort re-entry shows l65>"]},
            {"id": "C4", "group": "lossless fast typing over forced collection",
             "collection": collection,
             "actions": [
                f"at l65> submit {CONTROLLER}",
                (f"on the blank nested row type {PATTERN} six times; after each "
                 "pass delete exactly four groups of eight until blank"),
                "use ordinary pace for passes 1-2 and fast pace for passes 3-6",
                f"type {FINAL_TEXT} and press Return; touch no further key"],
             "expect": ["each token stays exact and each 32nd deletion empties the row",
                        "visible numeric oracle is 7",
                        "wait holds the counters before another prompt can re-zero them"]},
            {"id": "C5", "group": "composed display", "actions": [
                "during C1/C2 inspect the active Comfort row and result handoff"],
             "expect": ["l65> prompt, editable input and cursor share one row",
                        "evaluated (1 3) row has no stale input tail",
                        "next l65> has one cursor and no second positioning model"]},
            {"id": "C6", "group": "$22 latch at final cutpoint", "ranges": {
                "state": ranges["latch"],
                "conditional_payload": ranges["conditional_latch_payload"]},
             "actions": ["Codex stops the CPU once while wait is active",
                         "read five state bytes raw-first; if tag=A5 read payload now"],
             "expect": ["00 00 00 00 00 is the clean no-recurrence branch",
                        "A5 plus caller/name and NUL payload names the writer"]},
            {"id": "C7", "group": "loaded-world counters and D5",
             "ranges": {"input": ranges["input_counters"], "D5": ranges["D5"]},
             "actions": ["in the same stop read BCFC..BCFF, nsym and npool"],
             "expect": ["raw=seen=stored=taken=136 (0x88), all nonzero",
                        "752-nsym >= 32", "10208-npool >= 384"],
             "projection_only": {"free_symbol_slots": 105,
                                 "free_name_bytes": 1435}},
        ],
        "decision_table": {
            "all-seven-groups-green": "Comfort hardware-accepted; Block 3 opens",
            "counter-or-visible-input-mismatch": "input path red at named arc",
            "tag-A5": "stop; latch names writer and repair is priced",
            "daily-use-blocker": "one bounded repair round, then Comfort descope",
            "rare-or-cosmetic": "Known Issue plus v2.0 register row",
            "claim-expansion": "forbidden during this contact",
        },
        "evidence_limit": (
            "one fresh contact and one bound session; the earlier phase-0 "
            "non-recurrence is not a sweep"),
    }


def validate(value: dict[str, Any]) -> None:
    session = value["session_value"]
    require(value["format"] == FORMAT and value["status"] == STATUS
            and value["accepted_pair_before"] == value["accepted_pair_after"]
            and value["product_projection"]["source_product"]["sha256"]
                == value["product_projection"]["projected_product"]["sha256"]
                == PRODUCT_D81_SHA256
            and value["library"]["visible_files"]
                == ["L65INDEX", "REPL-COMFORT", "V16CORE"]
            and value["same_world_pair"]["row_names"]
                == ["v16core", "repl-comfort"]
            and value["same_world_pair"]["result"] == "same-world-pair"
            and session["format"] == SESSION_FORMAT
            and len(session["rows"]) == 7
            and value["error_trigger"] == error_trigger()
            and session["rows"][2]["trigger"] == error_trigger()
            and session["rows"][3]["collection"]["event_arithmetic"]
                ["expected_each_modulo_256"] == 136
            and session["rows"][5]["ranges"]["state"]["address"] == "0xC34D"
            and session["rows"][6]["ranges"]["input"]["taken"] == "0xBCFF"
            and session["rows"][6]["projection_only"]
                == {"free_symbol_slots": 105, "free_name_bytes": 1435}
            and value["accounting"] == {"WPLTO_runs": 0, "product_links": 0,
                "product_cards": 0, "artifact_only_product_copies": 1,
                "library_media_builds": 1, "device_contacts": 0},
            "Comfort media/session semantic wall red")


def derive_receipt(product: dict[str, Any], library: dict[str, Any]) -> dict[str, Any]:
    session = session_config()
    write(SESSION, session)
    value = {"format": FORMAT, "recorded_on": "2026-08-31",
        "status": STATUS, "authority": card_authority(),
        "accepted_pair_before": accepted_pair(),
        "accepted_pair_after": accepted_pair(),
        "product_projection": product, "library": library,
        "same_world_pair": pair_identity(), "error_trigger": error_trigger(),
        "read_ranges": read_ranges(), "session": bind(SESSION),
        "session_value": session,
        "accounting": {"WPLTO_runs": 0, "product_links": 0,
            "product_cards": 0, "artifact_only_product_copies": 1,
            "library_media_builds": 1, "device_contacts": 0},
        "claim_limit": ("Media and bound owner contact only; no device result, "
                        "Block-3 acceptance, latch retention or release claim.")}
    validate(value)
    return value


def build() -> None:
    require(not BUILD.exists() and not RECEIPT.exists() and not SESSION.exists(),
            "Comfort return media is one-shot")
    card_authority()
    product = product_projection()
    library = library_media()
    value = derive_receipt(product, library)
    write(RECEIPT, value)
    check()
    print("v2.0 Comfort return media: BUILD PASS product="
          f"{value['product_projection']['projected_product']['sha256']} "
          f"library={value['library']['D81']['sha256']} device=0")


def check() -> None:
    require(RECEIPT.is_file() and SESSION.is_file(),
            "Comfort return media output absent")
    value = load(RECEIPT)
    validate(value)
    require(value["authority"] == card_authority()
            and value["accepted_pair_before"] == accepted_pair()
            and value["accepted_pair_after"] == accepted_pair()
            and value["session_value"] == session_config()
            and bind(SESSION) == value["session"]
            and bind(PRODUCT) == value["product_projection"]["projected_product"]
            and bind(LIBRARY_D81) == value["library"]["D81"]
            and pair_identity() == value["same_world_pair"],
            "Comfort media persisted-world drift")
    print("v2.0 Comfort return media: CHECK PASS rows=7 same-world device=0")


def source_check() -> None:
    require(RECEIPT.is_file() and SESSION.is_file(),
            "Comfort return media source closure absent")
    value = load(RECEIPT)
    session = load(SESSION)
    validate(value)
    require(value["authority"] == card_authority()
            and value["accepted_pair_before"] == accepted_pair()
            and value["accepted_pair_after"] == accepted_pair()
            and value["error_trigger"] == error_trigger()
            and value["read_ranges"] == read_ranges()
            and value["session_value"] == session
            and bind(SESSION) == value["session"]
            and session["rows"][2]["trigger"] == error_trigger()
            and session["rows"][3]["collection"] == forced_collection(),
            "Comfort media source-only closure drift")
    print("v2.0 Comfort return media: SOURCE CHECK PASS rows=7 device=0")


def selftest() -> None:
    value = load(RECEIPT)
    mutations = {
        "product-byte-drift": lambda x: x["product_projection"]
            ["projected_product"].update(sha256="0" * 64),
        "comfort-row-omitted": lambda x: x["same_world_pair"].update(
            row_names=["v16core"]),
        "error-not-guaranteed": lambda x: x["session_value"]["rows"][2]
            ["trigger"].update(classification="silently-wrong"),
        "counter-remainder-drift": lambda x: x["session_value"]["rows"][3]
            ["collection"]["event_arithmetic"].update(
                expected_each_modulo_256=135),
        "latch-address-drift": lambda x: x["session_value"]["rows"][5]
            ["ranges"]["state"].update(address="0xC34E"),
        "consumer-counter-omitted": lambda x: x["session_value"]["rows"][6]
            ["ranges"]["input"].update(taken="0x0000"),
        "loaded-D5-projection-drift": lambda x: x["session_value"]["rows"][6]
            .update(projection_only={"free_symbol_slots": 31,
                                     "free_name_bytes": 1435}),
        "domain-authority-crosses-evidence-era": lambda x: (
            x["error_trigger"].update(authority=bind(DOMAIN)),
            x["session_value"]["rows"][2]["trigger"].update(
                authority=bind(DOMAIN))),
        "product-pair-changed": lambda x: x["accepted_pair_after"]["ELF"]
            .update(sha256="0" * 64),
    }
    rejected = []
    for name, mutate in mutations.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except ComfortMediaError:
            rejected.append(name)
    require(rejected == list(mutations), "Comfort media mutation survived")
    print(f"v2.0 Comfort return media: SELFTEST PASS mutations={len(rejected)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("build", "check", "source-check", "selftest"))
    action = parser.parse_args().action
    {"build": build, "check": check, "source-check": source_check,
     "selftest": selftest}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ComfortMediaError, OSError, ValueError, KeyError,
            subprocess.SubprocessError,
            json.JSONDecodeError) as error:
        print(f"v2.0 Comfort return media: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
