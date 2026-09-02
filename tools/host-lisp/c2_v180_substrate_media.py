#!/usr/bin/env python3
"""Pack artifact-only v1.8 substrate media and bind its owner D-session."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v170_release_media as BASE  # noqa: E402
import c2_v18_capture_hybrid_product_card as CARD  # noqa: E402
import evidence_era as ERA  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
RELOCATED_PLAN = ROOT / "docs/planning/v1.8.0-cycle-decisions.md"
PLAN_SEAL_ERA = "f886932d54c13fea77585f0d66ebc0f7e6f87b0f"
CARD_BUILD = CARD.BUILD
WPLTO = CARD_BUILD / "wplto"
SOURCE_STATIC = CARD.PLANE_ROOT
LIBRARY_SOURCE = BASE.INIT.BASELINE_ROOT / "static-plane/narrow-static/libs"
INPUT_ROOT = ROOT / "build/c2.3/v1.8.0-substrate-media-inputs"
STATIC = INPUT_ROOT / "static-plane"
BUILD = ROOT / "build/c2.3/v1.8.0-substrate-media"
ADAPTER = BUILD.parent / "v1.8.0-substrate-media-closure-adapter.json"
RECEIPT = ARCH / "c2.3-v1.8.0-substrate-media-receipt.json"
SESSION = ROOT / "config/c2-v180-substrate-d-session.json"
CLOSURE = CARD.RECEIPT
REPAIR = CARD.REPAIR_RECEIPT
FINAL_RED = ARCH / (
    "c2.3-v1.8-capture-hybrid-native-client-card-r1-final-red.json")
ACCEPTANCE = CARD.REPAIR_ACCEPTANCE_RESULT
SCOPE = CARD.REPAIR_SCOPE_RESULT
PRODUCT_REMOTE = "V180P.D81"
LIBRARY_REMOTE = "V180L.D81"
EXPECTED = {
    "PRG": (41566,
        "4a08b5a8e2cc1eb6924af0e43201fccaeea305bc56b7aa9ab37393d2e5e26123"),
    "ELF": (648612,
        "67f89b7354d0f473c3057508ed6a47af69edad29c0807bc1d6f031442daaceab"),
}
PRODUCT_ID = "0x2f688387"
STATUS = "PASS: V1.8.0 SUBSTRATE MEDIA AND D-SESSION READY"

_base_library_media = BASE.library_media
_base_product_manifest = BASE.product_manifest


class MediaError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise MediaError(message)


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


def owner_ratification_from(raw: bytes, path: str) -> dict[str, Any]:
    text = raw.decode("utf-8")
    header = "## Owner ratification — v1.8 substrate release and v1.9 client register — 2026-08-28"
    require(text.count(header) == 1, "substrate owner-ratification section drift")
    section = header + text.split(header, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    raw = section.encode()
    return {"path": path, "section": header,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def owner_ratification() -> dict[str, Any]:
    path = PLAN.relative_to(ROOT).as_posix()
    return owner_ratification_from(ERA.era_blob(PLAN_SEAL_ERA, path), path)


def era_separation_selftest() -> dict[str, Any]:
    """The sealed receipt must never consume a later planning location."""
    sealed = owner_ratification()
    expected = {
        "path": PLAN.relative_to(ROOT).as_posix(),
        "section": "## Owner ratification — v1.8 substrate release and v1.9 client register — 2026-08-28",
        "bytes": 1842,
        "sha256": "ab7a396d94cba41b37af74b985fc3f481d927446c77f665a2b3f37b1ba353d61",
    }
    require(sealed == expected, "sealed v1.8 owner-ratification identity drift")
    rejected = 0
    try:
        owner_ratification_from(
            PLAN.read_bytes(), PLAN.relative_to(ROOT).as_posix())
    except MediaError:
        rejected += 1
    relocated = owner_ratification_from(
        RELOCATED_PLAN.read_bytes(), RELOCATED_PLAN.relative_to(ROOT).as_posix())
    if relocated != expected:
        rejected += 1
    require(rejected == 2, "live/sealed planning-era mixing survived")
    return {"seal_commit": PLAN_SEAL_ERA, "mutations_rejected": rejected}


def accepted_pair() -> dict[str, Any]:
    pair = {"PRG": bind(WPLTO / "lisp65-c2-substitution-linked.prg"),
            "ELF": bind(WPLTO / "lisp65-c2-substitution-linked.prg.elf")}
    for role, (size, digest) in EXPECTED.items():
        require((pair[role]["bytes"], pair[role]["sha256"]) ==
                (size, digest), f"qualified substrate {role} drift")
    return pair


def lifecycle_gate() -> dict[str, Any]:
    elf = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
    truth = BASE.ElfTruth.read(
        elf, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=True)
    state = truth.section(".lisp65_c2_kernal_window.state")
    raw = truth.section_bytes(state.name)
    tail = truth.symbol("C2K_INPUT_RING_TAIL").value
    offset = tail - state.address
    require(len(raw) == 16 and offset == 13 and raw[offset] == 0xff,
            "substrate Capture lifecycle is not closed in the final ELF")
    return {"authority": "ElfTruth(final qualified substrate ELF)",
            "section": state.name, "section_address": state.address,
            "section_bytes": len(raw), "initial_bytes_hex": raw.hex(),
            "tail_symbol": tail, "tail_offset": offset,
            "initial_tail": raw[offset], "meaning": "closed/inert"}


def authority() -> dict[str, Any]:
    plan = ERA.era_blob(
        PLAN_SEAL_ERA, PLAN.relative_to(ROOT).as_posix()).decode("utf-8")
    closure = load(CLOSURE)
    repair = load(REPAIR)
    final_red = load(FINAL_RED)
    pair = accepted_pair()
    require("Owner ratification — v1.8 substrate release" in plan
            and "common `$28000` placement" in plan
            and "v1.5 fast-typing Known Issue remains open" in plan,
            "substrate release owner ratification drift")
    require(closure["status"] == CARD.STATUS
            and closure["artifacts_after"] == closure["artifacts_before"]
            and {name: closure["artifacts_after"][name]
                 for name in ("PRG", "ELF")} == pair,
            "qualified substrate closure drift")
    require(repair["status"] ==
                "PASS: ONE ROUTE REPAIR RESTORES RESPONSIVENESS WALL"
            and repair["frozen_pair_before"] ==
                repair["frozen_pair_after"] == pair,
            "responsiveness repair authority drift")
    require(final_red["status"] ==
                "FINAL RED: NATIVE CLIENT FALLS BACK TO V1.8 SUBSTRATE"
            and final_red["one_round_rule"]["v1_8_release"] ==
                "substrate-only"
            and final_red["one_round_rule"]["client_successor"] == "v1.9"
            and final_red["one_round_rule"]["retry_authorized"] is False,
            "one-round fallback authority drift")
    return {
        "owner_ratification": owner_ratification(),
        "qualified_product_card": bind(CLOSURE),
        "responsiveness_repair": bind(REPAIR),
        "client_final_red": bind(FINAL_RED),
        "scope": {"new_WPLTO_runs": 0, "new_product_links": 0,
                  "new_product_cards": 0, "artifact_only": True,
                  "device_contacts_during_build": 0},
    }


def closure_adapter() -> dict[str, Any]:
    closure = load(CLOSURE)
    repair = load(REPAIR)
    scope = load(SCOPE)
    acceptance = load(ACCEPTANCE)
    pair = accepted_pair()
    require(scope["status"] == acceptance["status"] == "PASS"
            and repair["frozen_pair_before"] ==
                repair["frozen_pair_after"] == pair,
            "substrate is not media-ready")
    value = {
        "format": "lisp65-v180-substrate-media-adapter-v1",
        # The inherited Completion consumer uses this established vocabulary;
        # the successor identity is carried by format and authorities.
        "status": "PASS: NESTED MAP ACCEPTANCE ACTIVE-REGISTRY UNION",
        "MAP_fix_closed": True,
        "frozen_pair_before": pair,
        "frozen_pair_after": pair,
        "product_card": bind(CLOSURE),
        "responsiveness_repair": bind(REPAIR),
        "scope": bind(SCOPE),
        "acceptance": bind(ACCEPTANCE),
        "review_authority": authority(),
        "completion_input_projection": BASE.MEDIA.prepare_static_inputs(),
        "rule": "artifact-only completion consumes the qualified substrate pair",
    }
    ADAPTER.parent.mkdir(parents=True, exist_ok=True)
    ADAPTER.write_bytes(canonical(value))
    return value


def library_media() -> dict[str, Any]:
    value = _base_library_media()
    value["variant"] = "v1.8.0-substrate-v16core"
    value["claim"] = (
        "same-world optional native library; Capture remains closed and "
        "Comfort remains absent")
    return value


def product_manifest(completion: dict[str, Any]) -> dict[str, Any]:
    value = _base_product_manifest(completion)
    value["static_plane"]["status"] = "passed-v1.8.0-substrate-static-plane"
    value["static_plane"]["membership_authority"] = (
        "v1.8 substrate final-ELF composed ownership")
    BASE.MEDIA.BASE.CAN.MANIFEST.write_bytes(canonical(value))
    BASE.MEDIA.BASE.CAN.check()
    return value


def session_config(product: Path, library: Path) -> dict[str, Any]:
    return {
        "format": "lisp65-c2-v180-substrate-d-session-v3",
        "recorded_on": "2026-08-28",
        "status": "ready-owner-Ship-contact",
        "claim_scope": {
            "accepts": ["v1.8.0-substrate-neutrality",
                        "v1.8.0-release-D5",
                        "v1.8.0-performance-smoke"],
            "host_qualified_only": [
                "Capture infrastructure present",
                "94/94 laboratory loss wall"],
            "excludes": ["Capture activation", "lossless user input",
                         "Comfort", "Matcher/Blink", "Block-3", "$22",
                         "publication"],
            "known_issue_stays_open": "v1.5 fast-typing input loss",
            "green_consequence": "owner Ship halt becomes decidable",
        },
        "media": {
            "product": {**bind(product), "remote_name": PRODUCT_REMOTE},
            "library": {**bind(library), "remote_name": LIBRARY_REMOTE},
        },
        "configuration": {
            "loaded_library_roles": [],
            "available_optional_roles": ["v16core"],
            "INIT_L65_on_product_or_library": False,
            "capture_initial_tail": 255,
            "capture_lifecycle": "closed/inert",
            "measurement_world": "v1.8.0 substrate-only release candidate",
            "cursor_navigation": (
                "not an acceptance row; the optional v16core library remains "
                "unloaded in the release-terminal measurement world"),
            "native_repl_input_boundary": (
                "the lisp65> C line collector has no Cursor Left/Right editor; "
                "unhandled PETSCII controls fail visibly as reader-invalid-token"),
        },
        "choreography": {
            "fresh_BASIC_first": True,
            "both_media_uploaded_and_read_back_before_boot": True,
            "product_mounted_last": True,
            "post_boot_automated_device_access": 0,
            "physical_owner_keyboard_only": True,
            "one_form_per_submission": True,
            "final_stops": 1,
            "physical_bank0_captures": 1,
        },
        "rows": [
            {"id": "S-boot-and-init-absence",
             "actions": ["cold boot the substrate product medium"],
             "expect": ["WORKBENCH 1.7.0", "native lisp65>",
                        "no INIT.L65 output or error before the banner"]},
            {"id": "S-native-line-input-and-delete",
             "actions": ["press Delete at the empty lisp65> input boundary",
                         "type (list 1 4 without Return",
                         "press Delete", "type 3)", "Return"],
             "expect": ["leading Delete is a boundary no-op",
                        "result is (1 3)", "native input remains responsive"]},
            {"id": "S-abort-recovery",
             "form": "(>= nil 32)",
             "expect": ["ordinary type error", "no red frame",
                        "native lisp65> returns practically immediately"],
             "follow_up": {"form": "(list 1 3)",
                           "oracle": {"kind": "exact", "value": "(1 3)"}}},
            {"id": "D-setup-published-call",
             "form": "(defun v18-perf-probe (x) (+ x 1))",
             "oracle": {"kind": "exact", "value": "v18-perf-probe"}},
            {"id": "D-list-read", "form": "(time (car (cdr (list 1 2))))",
             "oracle": {"kind": "time", "max_frames": 2, "value": "2"}},
            {"id": "D-list-write",
             "form": "(time ((lambda (x) (progn (rplaca x 9) x)) (list 1 2)))",
             "oracle": {"kind": "time", "max_frames": 2,
                        "value": "(9 2)"}},
            {"id": "D-string-op", "form": "(time (string-ref \"abc\" 1))",
             "oracle": {"kind": "time", "max_frames": 2, "value": "98"}},
            {"id": "D-published-call", "form": "(time (v18-perf-probe 41))",
             "oracle": {"kind": "time", "max_frames": 2, "value": "42"}},
        ],
        "headroom_postcondition": {
            "minimum": {"free_symbol_slots": 32, "free_name_bytes": 384},
            "counter_addresses": "derive nsym and npool from the substrate ELF",
            "counter_view": "one final physical Bank-0 stopped-state capture",
            "observation_point": "after all rows in the same fresh session",
        },
        "decision_table": {
            "all-neutrality-performance-and-D5-green": "owner may say Ship",
            "daily-use-blocker": "stop; no Ship",
            "Cursor-Left-at-native-lisp65-prompt": (
                "unsupported control at the raw C line collector; its visible "
                "reader-invalid-token is a session-protocol error, not a "
                "substrate product red"),
            "fast-typing-observation": (
                "not an acceptance row; Capture is deliberately closed"),
            "publication": "remains closed until later owner Publish",
        },
    }


def finish_media(media: dict[str, Any]) -> dict[str, Any]:
    BASE.PREP.configure_paths()
    BASE.PREP.MEDIA.check()
    product = BASE.PREP.MEDIA.PRODUCT_D81
    library = BASE.PREP.LIBRARY / "lisp65-library.d81"
    pair = BASE.PREP.PAIR.pair_identity(product, library)
    require(pair["product_build_id"] == PRODUCT_ID
            and pair["row_names"] == ["v16core"],
            "substrate product/library pair identity drift")
    visible_product = BASE.PREP.LIBMEDIA.L65I.D81.visible_files(
        product.read_bytes())
    visible_library = BASE.PREP.LIBMEDIA.L65I.D81.visible_files(
        library.read_bytes())
    require(b"INIT.L65" not in visible_product
            and b"INIT.L65" not in visible_library
            and b"REPL-COMFORT" not in visible_library,
            "substrate release media freight drift")
    config = session_config(product, library)
    SESSION.write_bytes(canonical(config))
    value = {
        "format": "lisp65-c2-v180-substrate-media-v1",
        "recorded_on": "2026-08-28",
        "status": STATUS,
        "authority": authority(),
        "accepted_pair": accepted_pair(),
        "completion": bind(BASE.PREP.CAN.RECEIPTS / "artifact-completion.json"),
        "media_closure": bind(BASE.PREP.MEDIA.MANIFEST),
        "media": {"product": bind(product),
                  "work": bind(BASE.PREP.MEDIA.WORK_D81),
                  "library": bind(library),
                  "library_index": bind(BASE.PREP.LIBRARY / "l65index")},
        "readback": {
            "product": "passed-packed-visible-file-and-role-identity-closure",
            "library": "passed-v16core-index-and-artifact-identity-closure"},
        "same_world_pair": pair,
        "packed_artifact_closure": {
            "stager_gate": media["stager"]["gate"],
            "product_entries": media["media"]["product"]["entries"],
            "artifact_count": media["artifact_count"]},
        "library_closure": {
            "D81": bind(library),
            "index": bind(BASE.PREP.LIBRARY / "l65index"),
            "artifacts": {"v16core": bind(
                BASE.PREP.LIBRARY / "v16core.l65s")},
            "row_names": ["v16core"], "Comfort_absent": True,
            "INIT_L65_absent": True},
        "substrate_lifecycle": {
            "Capture_present": True, "Hybrid_present": True,
            "initial_tail": 255, "activation_owner_present": False,
            "loss_wall_host_only": "94/94", "losslessness_claim": False,
            "known_issue": "v1.5 fast-typing input loss remains open",
            "final_ELF": lifecycle_gate()},
        "session": bind(SESSION),
        "claim_limit": config["claim_scope"],
        "execution_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "product_cards": 0, "artifact_completions": 1,
            "media_builds": 2, "device_contacts": 0},
    }
    RECEIPT.write_bytes(canonical(value))
    print("v1.8.0 substrate media: PASS product/library same-world Capture=closed")
    return value


def check_base_media() -> dict[str, Any]:
    value = load(RECEIPT)
    require(value["status"] == STATUS
            and value["substrate_lifecycle"]["initial_tail"] == 255
            and value["substrate_lifecycle"]["losslessness_claim"] is False
            and value["library_closure"]["Comfort_absent"] is True,
            "substrate media receipt drift")
    for row in [*value["accepted_pair"].values(), value["completion"],
                value["media_closure"], *value["media"].values(),
                value["session"]]:
        require(bind(ROOT / row["path"]) == row,
                f"substrate media artifact drift: {row['path']}")
    pair = BASE.PREP.PAIR.pair_identity(
        ROOT / value["media"]["product"]["path"],
        ROOT / value["media"]["library"]["path"])
    require(pair == value["same_world_pair"],
            "substrate pair identity drift")
    product = ROOT / value["media"]["product"]["path"]
    library = ROOT / value["media"]["library"]["path"]
    require(load(SESSION) == session_config(product, library),
            "substrate session semantics drift")
    require(value["substrate_lifecycle"]["final_ELF"] == lifecycle_gate(),
            "substrate lifecycle evidence drift")
    visible_product = BASE.PREP.LIBMEDIA.L65I.D81.visible_files(
        product.read_bytes())
    visible_library = BASE.PREP.LIBMEDIA.L65I.D81.visible_files(
        library.read_bytes())
    require(b"INIT.L65" not in visible_product
            and b"INIT.L65" not in visible_library
            and b"REPL-COMFORT" not in visible_library,
            "substrate visible-file closure drift")
    return value


def static_plane_gate() -> dict[str, Any]:
    path = BUILD / "canonical-product/canonical-product-manifest.json"
    value = load(path)
    plane = value["static_plane"]
    row = next(item for item in value["artifacts"]
               if item["role"] == "c2-bank2-static-code-plane")
    owners = plane["composed_owners"]
    require(plane["status"] == "passed-v1.8.0-substrate-static-plane"
            and plane["product_build_id"] == PRODUCT_ID
            and plane["bank2_static_code_bytes"] == row["bytes"] == 49105
            and owners[-1]["owner"] == "mapped-tenant-bank-end-reserve"
            and owners[-1]["bytes"] == 16431
            and bind(ROOT / row["path"])["sha256"] == row["sha256"]
                == plane["bank2_sha256"],
            "substrate packed Bank-2 composition drift")
    return {"manifest": bind(path), "static_plane": plane, "artifact": row,
            "rule": "every shipped Bank-2 byte has one composed owner"}


def configure() -> None:
    for name, value in {
        "CARD": CARD, "CARD_BUILD": CARD_BUILD, "WPLTO": WPLTO,
        "SOURCE_STATIC": SOURCE_STATIC, "LIBRARY_SOURCE": LIBRARY_SOURCE,
        "INPUT_ROOT": INPUT_ROOT, "STATIC": STATIC, "BUILD": BUILD,
        "ADAPTER": ADAPTER, "RECEIPT": RECEIPT, "SESSION": SESSION,
        "CLOSURE": CLOSURE, "RESUME": REPAIR, "ACCEPTANCE": ACCEPTANCE,
        "PRODUCT_REMOTE": PRODUCT_REMOTE, "LIBRARY_REMOTE": LIBRARY_REMOTE,
        "EXPECTED": EXPECTED, "PRODUCT_ID": PRODUCT_ID, "STATUS": STATUS,
    }.items():
        setattr(BASE, name, value)
    CARD.init_specs = BASE.INIT.init_specs
    for name, function in {
        "authority": authority,
        "closure_adapter": closure_adapter,
        "library_media": library_media,
        "product_manifest": product_manifest,
        "session_config": session_config,
        "finish_media": finish_media,
        "check_base_media": check_base_media,
        "static_plane_gate": static_plane_gate,
    }.items():
        setattr(BASE, name, function)
    BASE.configure_successor()


def seal_built_media() -> dict[str, Any]:
    """Seal the successor receipt after the historical wrapper vocabulary."""
    value = load(RECEIPT)
    completion = load(ROOT / value["completion"]["path"])
    require(value["status"] == STATUS
            and completion["compiler_runs"] == completion["linker_runs"] == 0,
            "artifact-only substrate output is not sealable")
    final_product = BUILD / "canonical-product/final/" \
        "lisp65-c2-substitution-linked.prg"
    final_elf = Path(str(final_product) + ".elf")
    value.update({
        "authority": authority(),
        "shipped_byte_facade": BASE.NESTED.REPAIR.packed_facade_gate(
            final_product, final_elf),
        "facade_mutations": BASE.NESTED.REPAIR.mutation_selftest(
            final_product, final_elf),
        "clean_static_plane": static_plane_gate(),
    })
    value["substrate_lifecycle"]["final_ELF"] = lifecycle_gate()
    RECEIPT.write_bytes(canonical(value))
    return value


def build() -> None:
    configure()
    if not RECEIPT.exists():
        try:
            BASE.MEDIA.MEDIA.build()
        except RuntimeError as error:
            # The inherited v1.6 wrapper expects its own intermediate status
            # after the successor's finish hook has already produced and
            # SHA-bound every output.  Seal that successor explicitly.
            require(str(error) ==
                    "artifact-only base media receipt is not sealable"
                    and RECEIPT.is_file(),
                    f"artifact-only substrate producer failed: {error}")
    seal_built_media()
    check()
    value = load(RECEIPT)
    print("v1.8.0 substrate media: BUILD PASS "
          f"product={value['media']['product']['sha256'][:12]} "
          f"library={value['media']['library']['sha256'][:12]} device=0")


def check() -> None:
    era_separation_selftest()
    configure()
    BASE.PREP.configure_paths()
    BASE.PREP.MEDIA.check()
    value = check_base_media()
    product = ROOT / value["media"]["product"]["path"]
    final_product = BUILD / "canonical-product/final/" \
        "lisp65-c2-substitution-linked.prg"
    final_elf = Path(str(final_product) + ".elf")
    require(value["authority"] == authority()
            and value["execution_accounting"] == {
                "WPLTO_runs": 0, "product_links": 0, "product_cards": 0,
                "artifact_completions": 1, "media_builds": 2,
                "device_contacts": 0}
            and value["packed_artifact_closure"]["artifact_count"] == 19
            and value["shipped_byte_facade"] ==
                BASE.NESTED.REPAIR.packed_facade_gate(final_product, final_elf)
            and value["facade_mutations"] ==
                BASE.NESTED.REPAIR.mutation_selftest(final_product, final_elf)
            and value["clean_static_plane"] == static_plane_gate()
            and bind(product) == value["media"]["product"],
            "substrate packed-media proof drift")
    static_plane_gate()
    print("v1.8.0 substrate media: CHECK PASS links=0 cards=0 device=0")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    {"build": build, "check": check}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.8.0 substrate media: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
