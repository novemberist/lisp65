#!/usr/bin/env python3
"""Prepare fresh same-world media for liveness plus the Comfort prompt."""

from __future__ import annotations

import argparse
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

import c2_v160_items12_device_preparation as BASE  # noqa: E402
import c2_v160_hybrid_live_stack_replacement_card as HYBRID  # noqa: E402
import c2_v160_liveness_capture_guard_card as LIVE  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-liveness-prompt-device-preparation-r1"
CARD = ROOT / "build/c2.3/v1.6-liveness-capture-guard-card"
WPLTO = CARD / "wplto"
STATIC = CARD / "static-plane/narrow-static"
RECEIPT = ARCH / "c2.3-v1.6-liveness-prompt-device-preparation-receipt.json"
SESSION = ROOT / "config/c2-v160-liveness-prompt-device-session.json"
LIVENESS = ARCH / "c2.3-v1.6-liveness-call-indir-replay-receipt.json"
PROMPT = ARCH / "c2.3-v1.6-comfort-prompt-card-receipt.json"
EXPECTED = {
    "PRG": (41566, "0410005035ee42463cc51d14fc2510528910a808358bb194a8e6e8c893ffd8d8"),
    "ELF": (632508, "102eac84ab25ec57b39990377d4808c3287746b94c65617cca3259fd43f73bcd"),
}
AUTHORIZATION = "dae56d6e"
MEDIA_AUTHORIZATION = "847eca2b"
PROMPT_AUTHORITY_TOKENS = ("one small prompt card", "prompt row",
    "native prompt visible after the abort row")
PROMPT_STATUS = "PASS: V1.6 COMFORT PROMPT GREEN"
PRODUCT_REMOTE = "V16P3.D81"
LIBRARY_REMOTE = "V16L3.D81"
L65_BUILD = ROOT / "build/c2.3/v1.6-l65-prompt-device-preparation-r1"
L65_RECEIPT = ARCH / "c2.3-v1.6-l65-prompt-device-preparation-receipt.json"
L65_SESSION = ROOT / "config/c2-v160-l65-prompt-device-session.json"
L65_PROMPT = ARCH / "c2.3-v1.6-comfort-prompt-l65-card-receipt.json"
L65_AUTHORIZATION = "8debd7b9"


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    rows = {}
    for label, ref, tokens in (
        ("prompt", AUTHORIZATION, PROMPT_AUTHORITY_TOKENS),
        ("same_world_media", MEDIA_AUTHORIZATION, ("media preparation",
            "same-world successor", "no old medium is reused"))):
        commit = subprocess.run(["git", "rev-parse", f"{ref}^{{commit}}"],
            cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
        raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
            check=True, stdout=subprocess.PIPE).stdout
        text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
        for token in tokens:
            require(token in text, f"liveness/prompt media authority absent: {token}")
        rows[label] = {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    return rows


def configure() -> None:
    BASE.BUILD = BUILD; BASE.CARD = CARD; BASE.WPLTO = WPLTO; BASE.STATIC = STATIC
    BASE.TARGET = BUILD / "canonical-product"
    BASE.SHARED = BUILD / "shared-system"; BASE.LIBRARY = BUILD / "library"
    BASE.RECEIPT = RECEIPT; BASE.SESSION = SESSION; BASE.EXPECTED = EXPECTED
    BASE.configure_candidate = configure_candidate
    BASE.complete = complete
    BASE.session_config = session_config


def install_l65_successor() -> None:
    """Select a fresh output closure for the authorized `l65>` successor."""
    global BUILD, RECEIPT, SESSION, PROMPT, AUTHORIZATION
    global PROMPT_AUTHORITY_TOKENS, PROMPT_STATUS
    global PRODUCT_REMOTE, LIBRARY_REMOTE
    BUILD = L65_BUILD
    RECEIPT = L65_RECEIPT
    SESSION = L65_SESSION
    PROMPT = L65_PROMPT
    AUTHORIZATION = L65_AUTHORIZATION
    PROMPT_AUTHORITY_TOKENS = ("prompt decided", "l65> now",
        "one small successor card")
    PROMPT_STATUS = "PASS: V1.6 L65 PROMPT GREEN"
    PRODUCT_REMOTE = "V16P4.D81"
    LIBRARY_REMOTE = "V16L4.D81"


def configure_candidate() -> None:
    """Reconstruct the exact active liveness successor without compiling."""
    HYBRID.install()
    HYBRID.configure_module()
    LIVE.configure_module()
    core, _activation = BASE.REOPEN.configure_stack(LIVE.BUILD, LIVE.PREFLIGHT)
    core.PRODUCT.BASE.configure()
    BASE.CAN.REPLAY.PROFILE.configure()
    if BASE.PRODUCT.PROFILE_RODATA_BYTES == 342:
        BASE.PRODUCT.configure_require_resolver_profile_geometry()
        BASE.PRODUCT.configure_defstruct_foundation_profile_geometry()
    BASE.CAN.REPLAY.BANK2.configure_bank2_stage()
    BASE.CAN.REPLAY.TWO.configure_two_region()
    BASE.CAN.REPLAY.LINK60.configure_current_pin_adapters()
    BASE.PRODUCT.configure_intern_session_service()
    BASE.PRODUCT.configure_full_map_ownership()
    BASE.PRODUCT.configure_low_resident_lma_reset()
    BASE.HEADER.configure_consumption()
    BASE.PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = STATIC / "product/substitution-artifacts.json"
    BASE.PRODUCT.INITIAL_C2D = STATIC / "product/initial.c2d-v3.bin"
    BASE.PRODUCT.PRODUCT_SHELF = STATIC / "product/product-shelf-v4-direct.bin"
    elf = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
    section = ElfTruth.read(elf,
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj").section(
            BASE.PRODUCT.VERIFIER_BINDING_SECTION)
    BASE.PRODUCT.VERIFIER_BINDING_BASE = section.address
    BASE.PRODUCT.LINK60_VERIFIER_BINDING_BASE = section.address
    require(section.bytes == 40, "candidate verifier-binding size drift")


def complete() -> dict[str, Any]:
    BASE.configure_paths()
    product = WPLTO / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    require((product.stat().st_size, BASE.sha(product)) == EXPECTED["PRG"]
            and (elf.stat().st_size, BASE.sha(elf)) == EXPECTED["ELF"],
            "accepted liveness pair drift")
    configure_candidate()
    closure = load(LIVENESS); historical = load(BASE.HISTORICAL_ACCEPTANCE)
    projection = historical["acceptance"]["VMA_golden"]
    require(closure["status"] == "PASS: V1.6 RETIREMENT LIVENESS CONTRACT CLOSED"
            and closure["artifacts_before"] == closure["artifacts_after"]
            and closure["final_liveness_gate"]["capacity"]["far_service_bytes"] == 1425
            and closure["active_candidate_capture_guard"]["candidate"]
                ["post_capture_free_bytes"] == 69,
            "accepted liveness closure drift")

    class AcceptedProjection:
        @staticmethod
        def compare_elf(candidate: Path) -> dict[str, Any]:
            require((candidate.stat().st_size, BASE.sha(candidate)) == EXPECTED["ELF"],
                    "Completion adapter received a different liveness ELF")
            return projection

    accepted = AcceptedProjection()
    BASE.SOURCE_MEDIA.FLOW.BASE.INV = accepted
    BASE.CRC_MEDIA.INV = accepted
    BASE.SOURCE_MEDIA.card_projection = lambda: {"acceptance": {"VMA_golden": projection}}
    original_configure = BASE.CAN.REPLAY.configure
    original_fixed = BASE.PRODUCT.FIXED_BLOCK_LEAF.audit_elf
    original_facade = BASE.PRODUCT.fixed_facade_gate

    def fixed(candidate: Path, **kwargs: Any) -> dict[str, Any]:
        return BASE.SOURCE_MEDIA._link105_fixed_audit(original_fixed, candidate, **kwargs)

    def facade(out: Path, target: Path, suffix: str) -> dict[str, Any]:
        return BASE.CRC_MEDIA._current_facade_gate(original_facade, out, target, suffix)

    BASE.CAN.REPLAY.configure = lambda: None
    BASE.PRODUCT.FIXED_BLOCK_LEAF.audit_elf = fixed
    BASE.PRODUCT.fixed_facade_gate = facade
    try:
        value = BASE.CAN.complete_artifacts()
    finally:
        BASE.CAN.REPLAY.configure = original_configure
        BASE.PRODUCT.FIXED_BLOCK_LEAF.audit_elf = original_fixed
        BASE.PRODUCT.fixed_facade_gate = original_facade
    final_product = BASE.CAN.FINAL / product.name
    final_elf = Path(str(final_product) + ".elf")
    require((final_product.stat().st_size, BASE.sha(final_product)) == EXPECTED["PRG"]
            and (final_elf.stat().st_size, BASE.sha(final_elf)) == EXPECTED["ELF"]
            and value["compiler_runs"] == value["linker_runs"] == 0,
            "Completion changed accepted liveness identity")
    return value


def session_config(product: Path, library: Path) -> dict[str, Any]:
    value = BASE.session_config_original(product, library)
    value["format"] = "lisp65-c2-v160-liveness-prompt-device-session-v1"
    value["media"]["product"]["remote_name"] = PRODUCT_REMOTE
    value["media"]["library"]["remote_name"] = LIBRARY_REMOTE
    value["rows"][0]["expect"][-1] = "distinct l65> prompt"
    value["rows"].insert(1, {"id": "D2-prompt",
        "action": "after (repl), observe before typing",
        "expect": "l65> is visible as the Comfort readiness/layer marker"})
    value["rows"][-1] = {"id": "D2-abort-liveness",
        "action": "at l65>, submit (car 1) to trigger a VM type abort",
        "expect": ("error is reported without a red frame; retirement repairs the "
                   "continuation and control returns to the distinct native lisp65> prompt")}
    value["liveness_witness"] = {"class": "retirement-before-wipe",
        "trigger": "(car 1)", "comfort_prompt": "l65>",
        "recovery_prompt": "lisp65>", "red_frame": False}
    return value


BASE.session_config_original = BASE.session_config


def preflight() -> None:
    configure(); auth = authority(); prompt = load(PROMPT); live = load(LIVENESS)
    require(not BUILD.exists() and not RECEIPT.exists() and not SESSION.exists()
            and prompt["status"] == PROMPT_STATUS
            and prompt["library"]["price"]["new_symbol_names"] == []
            and live["status"] == "PASS: V1.6 RETIREMENT LIVENESS CONTRACT CLOSED",
            "liveness/prompt media preflight drift")
    product = WPLTO / "lisp65-c2-substitution-linked.prg"; elf = Path(str(product) + ".elf")
    require((product.stat().st_size, BASE.sha(product)) == EXPECTED["PRG"]
            and (elf.stat().st_size, BASE.sha(elf)) == EXPECTED["ELF"],
            "liveness/prompt candidate pair drift")
    print("v1.6 liveness/prompt preparation: PREFLIGHT PASS "
          f"authority={auth['prompt']['commit'][:8]} media=0 device=0")


def build() -> None:
    configure(); value = BASE.build(); value["successor_authority"] = authority()
    value["liveness_closure"] = bind(LIVENESS); value["prompt_card"] = bind(PROMPT)
    value["status"] = "PASS: V1.6 LIVENESS/PROMPT DEVICE CONTACT READY"
    RECEIPT.write_bytes(canonical(value))
    print("v1.6 liveness/prompt preparation: PASS media=2 contact=ready")


def check() -> dict[str, Any]:
    configure()
    value = load(RECEIPT)
    require(value["status"] == "PASS: V1.6 LIVENESS/PROMPT DEVICE CONTACT READY",
            "liveness/prompt preparation receipt drift")
    for row in [*value["accepted_pair"].values(), value["completion"],
                value["media_closure"], *value["media"].values(),
                value["session"], value["liveness_closure"],
                value["prompt_card"]]:
        require(bind(ROOT / row["path"]) == row,
                f"liveness/prompt artifact identity drift: {row['path']}")
    pair = BASE.PAIR.pair_identity(ROOT / value["media"]["product"]["path"],
                                   ROOT / value["media"]["library"]["path"])
    require(pair == value["same_world_pair"],
            "liveness/prompt persisted pair identity drift")
    session = load(SESSION)
    require(session["media"]["product"]["remote_name"] == PRODUCT_REMOTE
            and session["media"]["library"]["remote_name"] == LIBRARY_REMOTE
            and session["rows"][1]["expect"].startswith("l65>")
            and session["liveness_witness"]["comfort_prompt"] == "l65>"
            and session["liveness_witness"]["recovery_prompt"] == "lisp65>",
            "liveness/prompt successor session drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "build", "check",
        "l65-preflight", "l65-build", "l65-check"))
    action = parser.parse_args().action
    if action.startswith("l65-"):
        install_l65_successor()
        action = action.removeprefix("l65-")
    if action == "preflight": preflight()
    elif action == "build": build()
    else:
        check()
        print("v1.6 liveness/prompt preparation: CHECK PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
