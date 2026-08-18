#!/usr/bin/env python3
"""Run/check the single commissioned v1.5 F018B content-safe-read card."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_f018b_content_safe_reads as SAFE  # noqa: E402
import c2_v150_candidate_product as BASE  # noqa: E402


LINK = 98
BUILD = ROOT / "build/c2.3/v1.5.0-f018b-content-safe-link98-r3"
MANIFEST = BUILD / "canonical-product-manifest.json"
BASE_RECEIPT = BUILD / "base-product-card-receipt.json"
PROFILE_ROOT = ROOT / "build/c2.3/v1.5.0-f018b-content-safe-link98-r3-inputs"
CANDIDATE_PROFILE = PROFILE_ROOT / "candidate-profile.json"
HISTORICAL_PROFILE = ROOT / "config/c2-l-full-product-profile.json"
CANDIDATE_CONTRACT = PROFILE_ROOT / "c2-lite-execution-contract.json"
HISTORICAL_CONTRACT = ROOT / "config/c2-lite-execution-contract.json"
CANDIDATE_HEADER = PROFILE_ROOT / "c2_lite_static_plane.h"
HISTORICAL_HEADER = ROOT / "src/c2_lite_static_plane.h"
GUARD_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-link98-terminal-guard-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-link98-f018b-content-safe-card-receipt.json")
ORIGINAL_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-link98-f018b-content-safe-card-first-red.json")
REPLACEMENT_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-link98-f018b-content-safe-replacement-first-red.json")
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-link98-f018b-content-safe-additional-card-first-red.json")
DRIVER = Path(__file__).resolve()
FORMAT = "lisp65-c2.3-v150-link98-f018b-content-safe-card-v1"
STATUS = "LINK98-F018B-CONTENT-SAFE-HOST-PRODUCT-GREEN; MEDIA-PENDING"


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


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
    return {"path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def profile_geometry(value: dict[str, Any]) -> dict[str, Any]:
    code = value["bank2_static_code"]
    return {
        "static_code_bytes": int(code["bytes"]),
        "bank2_headroom_bytes": int(code["headroom_bytes"]),
        "bank2_sha256": str(code["sha256"]),
        "entries": int(value["entries"]),
        "resolutions": int(value["resolutions"]),
        "roots": int(value["roots"]),
        "direct_entry_refs": int(value["direct_entry_refs"]),
        "product_build_id": str(value["product_build_id"]),
    }


def projected_contract() -> dict[str, Any]:
    value = load(HISTORICAL_CONTRACT)
    geometry = BASE.PRE.geometry()
    value["physical_planes"]["code"].update({
        "static_use_bytes": geometry["static_code_bytes"],
        "gross_headroom_bytes": geometry["bank2_headroom_bytes"],
    })
    return value


def projected_header() -> str:
    text = HISTORICAL_HEADER.read_text(encoding="utf-8")
    expected = BASE.PRE.geometry()["static_code_bytes"]
    replaced, count = re.subn(
        r"(#define LISP65_C2_LITE_STATIC_CODE_BYTES )\d+(UL)",
        rf"\g<1>{expected}\2", text)
    require(count == 1, "static-plane header projection cardinality drift")
    return replaced


def projected_binding(path: Path, raw: bytes) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def projected_profile() -> dict[str, Any]:
    value = load(HISTORICAL_PROFILE)
    geometry = BASE.PRE.geometry()
    value.update({
        "recorded_on": str(date.today()),
        "bank2_static_code": {
            "bytes": geometry["static_code_bytes"],
            "headroom_bytes": geometry["bank2_headroom_bytes"],
            "sha256": geometry["bank2_sha256"],
        },
        "entries": geometry["entries"],
        "resolutions": geometry["resolutions"],
        "roots": geometry["roots"],
        "direct_entry_refs": geometry["direct_entry_refs"],
        "product_build_id": geometry["product_build_id"],
    })
    contract_raw = canonical(projected_contract())
    header_raw = projected_header().encode()
    value["authority"]["candidate_projection"] = {
        "kind": "build-local-projection-from-current-candidate-preflight",
        "authorization": "da816c8b",
        "additive_provenance_authorization": "43ad331e",
        "preflight": bind(BASE.PRE.RECEIPT),
        "historical_profile_ancestry": bind(HISTORICAL_PROFILE),
        "companions": {
            "execution_contract": projected_binding(
                CANDIDATE_CONTRACT, contract_raw),
            "static_plane_header": projected_binding(
                CANDIDATE_HEADER, header_raw),
        },
        "rule": (
            "Candidate profile identity derives from this candidate's "
            "SHA-bound preflight, never from a prior link world."),
    }
    return value


def validate_projection(value: dict[str, Any]) -> None:
    historical_authority = load(HISTORICAL_PROFILE)["authority"]
    authority = value.get("authority", {})
    projection = authority.get("candidate_projection", {})
    contract_raw = canonical(projected_contract())
    header_raw = projected_header().encode()
    require(
        profile_geometry(value) == BASE.PRE.geometry()
        and {key: authority.get(key) for key in historical_authority}
            == historical_authority
        and projection.get("authorization") == "da816c8b"
        and projection.get("additive_provenance_authorization") == "43ad331e"
        and projection.get("preflight")
            == bind(BASE.PRE.RECEIPT)
        and projection.get("companions") == {
            "execution_contract": projected_binding(
                CANDIDATE_CONTRACT, contract_raw),
            "static_plane_header": projected_binding(
                CANDIDATE_HEADER, header_raw)},
        "build-local candidate profile is not the current preflight identity")


def projection_mutations(value: dict[str, Any]) -> list[str]:
    historical = load(HISTORICAL_PROFILE)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "consume-historical-profile": lambda x: x.update({
            "bank2_static_code": deepcopy(historical["bank2_static_code"]),
            "entries": historical["entries"],
            "resolutions": historical["resolutions"],
            "roots": historical["roots"],
            "direct_entry_refs": historical["direct_entry_refs"],
            "product_build_id": historical["product_build_id"],
        }),
        "substitute-public-authority-kind": lambda x: x["authority"].update(
            kind="build-local-projection-from-current-candidate-preflight"),
        "detach-preflight-SHA": lambda x: x["authority"][
            "candidate_projection"].update(preflight={
                **x["authority"]["candidate_projection"]["preflight"],
                "sha256": "0" * 64}),
        "detach-contract-SHA": lambda x: x["authority"][
            "candidate_projection"]["companions"][
                "execution_contract"].update(sha256="0" * 64),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate_projection(candidate)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases), "candidate-profile mutation survived")
    return rejected


def write_projection() -> dict[str, Any]:
    require(not CANDIDATE_PROFILE.exists(),
            "replacement candidate profile already exists")
    value = projected_profile()
    validate_projection(value)
    value["mutations_rejected"] = projection_mutations(value)
    PROFILE_ROOT.mkdir(parents=True, exist_ok=False)
    CANDIDATE_CONTRACT.write_bytes(canonical(projected_contract()))
    CANDIDATE_HEADER.write_text(projected_header(), encoding="utf-8")
    CANDIDATE_PROFILE.write_bytes(canonical(value))
    return value


def consume_profile(profile: Path, contract: Path, header: Path) -> dict[str, Any]:
    """Run the real static-plane consumer in an isolated temporary card."""
    with tempfile.TemporaryDirectory(
            prefix="c2-v150-f018b-real-consumer-",
            dir=ROOT / "build") as temporary:
        scratch = Path(temporary) / "card"
        scratch.mkdir()
        shutil.copytree(BASE.PRE.BUILD / "static-plane", scratch / "static-plane")
        BASE.BUILD = scratch
        BASE.MANIFEST = scratch / "canonical-product-manifest.json"
        BASE.RECEIPT = scratch / "card-receipt.json"
        BASE.GUARD_RECEIPT = scratch / "guard-receipt.json"
        BASE.PROFILE = profile
        BASE.HEADER = header
        plane_module = BASE.L95.BASE.PROBE.REQ.F1W.PLANE
        plane_module.CONTRACT = contract
        plane_module.HEADER = header
        BASE.configure(profile)
        static = BASE.L95.BASE.PROBE.REQ.build_static_plane()
        plane = BASE.L95.BASE.PROBE.REQ.F1W.static_gate()
        expected = BASE.PRE.geometry()["static_code_bytes"]
        require(static["semantics"]["code_bytes"] == expected
                and plane["static_code_bytes"] == expected,
                "real static-plane consumer differs from projected preflight")
        return {"status": "passed-real-fresh-static-plane-bundle-consumer",
                "static_code_bytes": expected}


def run_consumer_process(profile: Path, contract: Path, header: Path,
                         *, expect_green: bool) -> dict[str, Any]:
    environment = os.environ.copy()
    environment.update(BASE.L95.CAN.canonical_build_environment())
    result = subprocess.run(
        [sys.executable, str(DRIVER), "_consume-profile",
         "--profile", str(profile), "--contract", str(contract),
         "--header", str(header)],
        cwd=ROOT, env=environment, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    if expect_green:
        require(result.returncode == 0,
                "real projected-profile consumer red:\n" + result.stdout)
    else:
        require(result.returncode != 0
                and "public build authority" in result.stdout,
                "substituted public authority survived the real consumer")
    raw = result.stdout.encode()
    return {"return_code": result.returncode, "output_bytes": len(raw),
            "output_sha256": hashlib.sha256(raw).hexdigest()}


def configure_base() -> None:
    BASE.LINK = LINK
    BASE.BUILD = BUILD
    BASE.MANIFEST = MANIFEST
    BASE.RECEIPT = BASE_RECEIPT
    BASE.FIRST_RED = FIRST_RED
    BASE.GUARD_RECEIPT = GUARD_RECEIPT
    BASE.DRIVER = DRIVER
    BASE.FORMAT = "lisp65-c2.3-v150-link98-base-product-card-v1"
    BASE.STATUS = "V150-LINK98-BASE-HOST-PRODUCT-GREEN; MEDIA-PENDING"
    BASE.REPLAY_FIRST_RED = BUILD / "unused-post-link-first-red"
    BASE.REPLAY_PREVIOUS_RED = BUILD / "unused-post-link-previous-red"
    BASE.REPLAY = BUILD / "unused-post-link-replay"
    BASE.REPLAY_PROFILE = BASE.REPLAY / "candidate-profile.json"
    BASE.REPLAY_INTERNAL = BASE.REPLAY / "wplto-internal.json"
    BASE.REPLAY_LINKED_GATE = BASE.REPLAY / "single-submit-linked-gates.json"
    BASE.PROFILE = CANDIDATE_PROFILE
    BASE.HEADER = CANDIDATE_HEADER
    plane_module = BASE.L95.BASE.PROBE.REQ.F1W.PLANE
    plane_module.CONTRACT = CANDIDATE_CONTRACT
    plane_module.HEADER = CANDIDATE_HEADER

    original_guard = BASE.guard_result

    def guarded_with_content(elf: Path, prg: Path) -> dict[str, Any]:
        value = original_guard(elf, prg)
        content = SAFE.postlink(elf)
        # Work and final ELF paths differ while their bytes and semantics must
        # be identical.  Retain the identity, not the staging position.
        content["ELF"].pop("path", None)
        value["f018b_content_safe_reads"] = content
        return value

    BASE.guard_result = guarded_with_content


def derive() -> dict[str, Any]:
    base = load(BASE_RECEIPT)
    paths = BASE.completed_paths()
    final_elf = paths["final"] / "lisp65-c2-substitution-linked.prg.elf"
    final_prg = paths["final"] / "lisp65-c2-substitution-linked.prg"
    content = SAFE.postlink(final_elf)
    walls = base["geometry"]["walls"]
    require(
        base["attempt_accounting"] == {
            "product_cards_authorized": 1,
            "product_cards_consumed": 1,
            "product_closure_links": 1,
            "hardware_runs": 0,
        }
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] >= 54
        and walls["ordinary_bank0_bss_headroom_bytes"] >= 0
        and walls["resident_island_headroom_bytes"] >= 0
        and content["all_three_route_to_linked_convergence"] is True,
        "Link-98 base card or content-safe geometry red")
    return {
        "format": FORMAT,
        "recorded_on": str(date.today()),
        "status": STATUS,
        "attempt_accounting": {
            "product_cards_authorized": 1,
            "product_cards_consumed": 1,
            "WPLTO_runs": 1,
            "product_links": 1,
            "hardware_contacts": 0,
        },
        "selection": {
            "winner": "verified-convergence-per-all-three-open-reader-families",
            "cpu_28bit": "rejected-by-bound-target-evidence",
            "reader_families": 3,
            "already_independently_protected_consumers": 8,
        },
        "content_safe_postlink": content,
        "geometry": base["geometry"],
        "artifacts": {
            "product": bind(final_prg),
            "ELF": bind(final_elf),
            "map": bind(paths["final"] / "lisp65-c2-substitution-linked.prg.map"),
            "manifest": bind(MANIFEST),
            "completion": bind(paths["receipts"] / "artifact-completion.json"),
            "base_card": bind(BASE_RECEIPT),
        },
        "authorities": {
            "pricing": bind(SAFE.RECEIPT),
            "contract": bind(SAFE.CONTRACT),
            "preflight": bind(BASE.PRE.RECEIPT),
            "freight_closure": bind(BASE.CLOSURE.RECEIPT),
            "driver": bind(DRIVER),
            "candidate_profile": bind(CANDIDATE_PROFILE),
            "first_red": bind(ORIGINAL_FIRST_RED),
            "replacement_first_red": bind(REPLACEMENT_FIRST_RED),
        },
        "hardware_handoff": {
            "status": "media-regeneration-pending",
            "standing_D1_to_D5_order": True,
        },
        "claim_limit": (
            "One host-green content-safe product card. Media regeneration, "
            "device acceptance, release and publication remain unclaimed."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and value.get("attempt_accounting") == {
            "product_cards_authorized": 1, "product_cards_consumed": 1,
            "WPLTO_runs": 1, "product_links": 1, "hardware_contacts": 0}
        and value.get("selection", {}).get("reader_families") == 3
        and value.get("content_safe_postlink", {}).get(
            "all_three_route_to_linked_convergence") is True
        and value.get("hardware_handoff", {}).get("status")
            == "media-regeneration-pending",
        "Link-98 F018B card claim drift")
    if verify:
        require(value == derive(), "Link-98 F018B card receipt is stale")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "hide-card": lambda x: x["attempt_accounting"].update(
            product_cards_consumed=0),
        "hide-link": lambda x: x["attempt_accounting"].update(product_links=0),
        "claim-device": lambda x: x["attempt_accounting"].update(
            hardware_contacts=1),
        "drop-reader": lambda x: x["selection"].update(reader_families=2),
        "trust-completion": lambda x: x["content_safe_postlink"].update(
            all_three_route_to_linked_convergence=False),
        "claim-media": lambda x: x["hardware_handoff"].update(status="ready"),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate(candidate, verify=False)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases), "Link-98 card mutation survived")
    return rejected


def first_red(error: Exception) -> None:
    value = {
        "format": "lisp65-c2.3-v150-link98-f018b-card-first-red-v1",
        "recorded_on": str(date.today()),
        "status": "FIRST-RED; ADDITIONAL-CARD-CONSUMED",
        "error": str(error),
        "attempt_accounting": {
            "additional_cards_authorized": 1,
            "additional_cards_consumed": 1,
            "hardware_contacts": 0,
        },
        "pricing": bind(SAFE.RECEIPT),
        "claim_limit": "No retry and no product or hardware claim.",
    }
    FIRST_RED.parent.mkdir(parents=True, exist_ok=True)
    FIRST_RED.write_bytes(canonical(value))


def build() -> int:
    require(ORIGINAL_FIRST_RED.is_file() and REPLACEMENT_FIRST_RED.is_file()
            and not BUILD.exists()
            and not PROFILE_ROOT.exists()
            and not RECEIPT.exists() and not FIRST_RED.exists()
            and not GUARD_RECEIPT.exists(),
            "Link-98 replacement card is not at its one-shot boundary")
    try:
        write_projection()
        projection_selftest()
        BASE.build()
        value = derive()
        validate(value, verify=False)
        value["mutations_rejected"] = mutations(value)
        RECEIPT.write_bytes(canonical(value))
    except Exception as error:
        first_red(error)
        raise
    print("Link-98 F018B content-safe card: PASS "
          f"text={value['geometry']['walls']['bank0_text_headroom_bytes']} "
          f"e000={value['geometry']['walls']['e000_headroom_bytes']} "
          f"resident={value['geometry']['walls']['resident_island_headroom_bytes']}")
    return 0


def check() -> int:
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == mutations(value), "Link-98 card mutation receipt drift")
    print("Link-98 F018B content-safe card check: PASS")
    return 0


def projection_selftest() -> int:
    value = (load(CANDIDATE_PROFILE) if CANDIDATE_PROFILE.is_file()
             else projected_profile())
    validate_projection(value)
    require(projection_mutations(value) == [
                "consume-historical-profile",
                "substitute-public-authority-kind",
                "detach-preflight-SHA",
                "detach-contract-SHA"],
            "candidate-profile projection mutation set drift")
    require(profile_geometry(load(HISTORICAL_PROFILE)) != BASE.PRE.geometry(),
            "historical-profile mutation no longer exercises a prior world")
    with tempfile.TemporaryDirectory(
            prefix="c2-v150-profile-selftest-", dir=ROOT / "build") as temporary:
        root = Path(temporary)
        good = root / "candidate-profile.json"
        bad = root / "substituted-authority-profile.json"
        contract = root / "c2-lite-execution-contract.json"
        header = root / "c2_lite_static_plane.h"
        good.write_bytes(canonical(value))
        contract.write_bytes(canonical(projected_contract()))
        header.write_text(projected_header(), encoding="utf-8")
        mutant = deepcopy(value)
        mutant["authority"]["kind"] = (
            "build-local-projection-from-current-candidate-preflight")
        bad.write_bytes(canonical(mutant))
        real_green = run_consumer_process(
            good, contract, header, expect_green=True)
        real_red = run_consumer_process(
            bad, contract, header, expect_green=False)
    print("Link-98 additive profile projection: PASS "
          "mutations=4 real-consumer=green substituted-kind=red")
    require(real_green["return_code"] == 0 and real_red["return_code"] != 0,
            "real-consumer result accounting drift")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("build", "_complete", "check", "projection-selftest",
                           "_consume-profile"))
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--header", type=Path)
    args = parser.parse_args()
    action = args.action
    configure_base()
    if action == "_complete":
        os.environ.update(BASE.L95.CAN.canonical_build_environment())
        return BASE.complete_action()
    if action == "build":
        environment = BASE.L95.CAN.canonical_build_environment()
        if any(os.environ.get(key) != value for key, value in environment.items()):
            updated = os.environ.copy()
            updated.update(environment)
            os.execve(sys.executable,
                      [sys.executable, str(DRIVER), "build"], updated)
        return build()
    if action == "projection-selftest":
        projection_selftest()
        return 0
    if action == "_consume-profile":
        require(args.profile is not None and args.contract is not None
                and args.header is not None,
                "--profile, --contract and --header required")
        consume_profile(args.profile, args.contract, args.header)
        print("real fresh_static_plane_bundle consumer: PASS")
        return 0
    return check()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, SAFE.FixError, BASE.CardError, OSError, ValueError,
            KeyError, json.JSONDecodeError) as error:
        print(f"Link-98 F018B content-safe card: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
