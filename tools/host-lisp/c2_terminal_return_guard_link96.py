#!/usr/bin/env python3
"""Build the commissioned Link-96 terminal-return-guard product once."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_link95_product_card as L95  # noqa: E402
import c2_lite_v6_real_abi_direct_entry_contract as DIRECT  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_terminal_return_guard_gate as GUARD  # noqa: E402


RELEASE = "post-v1.4-terminal-return-guard"
LINK = 96
DRIVER = Path(__file__).resolve()
BUILD = ROOT / "build/c2.3/terminal-return-guard-link96"
MANIFEST = BUILD / "canonical-product-manifest.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link96-terminal-return-guard-product-receipt.json"
)
GUARD_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link96-terminal-return-guard-elf-receipt.json"
)
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link96-terminal-return-guard-completion-first-red.json"
)
GATES = ROOT / "mk/gates.mk"
BROKEN_COMPLETION_DRIVER = {
    "path": "tools/host-lisp/c2_terminal_return_guard_link96.py",
    "bytes": 15893,
    "sha256": "7529a5d9645407529e1e72cac38b3c9a1aac9bae12b610320fd22e515d0c0f77",
}


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    data = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"receipt absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def run(command: list[str], label: str) -> dict[str, Any]:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    output = result.stdout.encode()
    return {"status": "passed", "output_bytes": len(output),
            "output_sha256": hashlib.sha256(output).hexdigest()}


def configure_identity() -> None:
    """Bind Link-96 identity without invoking an inherited configure pass."""
    # Reuse the already accepted Link-95 static world; only the runtime feature
    # define changes.  Its current direct-entry receipt is checked explicitly,
    # rather than falling through to the retired v2 predecessor default.
    L95.RELEASE = RELEASE
    L95.LINK = LINK
    L95.DRIVER = DRIVER
    L95.BUILD = BUILD
    L95.MANIFEST = MANIFEST
    L95.RECEIPT = RECEIPT


def configure() -> dict[str, Path]:
    configure_identity()
    paths = L95.configure_card()
    inherited = L95.L94.PRODUCT_LINK.single_link

    def guarded_single_link(
        out: Path, *, probe_definitions: tuple[str, ...] = (),
        direct_entry_receipt: Path = DIRECT.RECEIPT,
        direct_entry_check_tool: str =
            "c2_lite_v6_real_abi_direct_entry_contract.py",
        extra_contract_lines: tuple[str, ...] = (),
    ) -> None:
        features = tuple(dict.fromkeys((
            *probe_definitions, PRODUCT.TERMINAL_RETURN_GUARD_FEATURE)))
        return inherited(
            out, probe_definitions=features,
            direct_entry_receipt=DIRECT.RECEIPT,
            direct_entry_check_tool=
                "c2_lite_v6_real_abi_direct_entry_contract.py",
            extra_contract_lines=(
                *extra_contract_lines,
                "terminal_return_guard=shadow-restore-first-signature",
                "terminal_return_guard_owner_free=0xb582..0xb592",
                "terminal_return_guard_resident_delta=0",
            ),
        )

    L95.L94.PRODUCT_LINK.single_link = guarded_single_link
    return paths


def completed_paths() -> dict[str, Path]:
    return L95.BASE.paths(BUILD)


def fresh_guard_result(elf: Path, prg: Path) -> dict[str, Any]:
    value = GUARD.audit(elf, prg)
    rejected = GUARD.mutation_selftest(elf, prg)
    value["mutations_rejected"] = rejected
    value["mutation_count"] = len(rejected)
    return value


def guard_semantic_identity(value: dict[str, Any]) -> bytes:
    normalized = deepcopy(value)
    for role in ("ELF", "product_PRG"):
        normalized["authorities"][role].pop("path", None)
    # The audit above has already re-run the terminal-return source model,
    # linked-ELF checks and all mutations.  Preserve the source identity while
    # allowing unrelated additions elsewhere in the shared runtime file.
    runtime = normalized["authorities"]["runtime"]
    normalized["authorities"]["runtime"] = {"path": runtime["path"]}
    return canonical(normalized)


def complete_action() -> int:
    # L95.complete_action() reaches the one configure_card() owned by the
    # inherited closer.  Calling configure() here would select the append-only
    # require geometry twice in one process.
    configure_identity()
    return L95.complete_action()


def complete_in_fresh_process() -> None:
    environment = os.environ.copy()
    environment.update(L95.CAN.canonical_build_environment())
    result = subprocess.run(
        [sys.executable, str(DRIVER), "_complete"], cwd=ROOT, env=environment,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            "Link-96 fresh-process completion red:\n" + result.stdout)
    paths = completed_paths()
    (paths["receipts"] / "artifact-completion.log").write_text(
        result.stdout, encoding="utf-8")


def build_manifest(wplto: dict[str, Any], completion: dict[str, Any]) -> dict[str, Any]:
    value = L95.build_manifest(wplto, completion)
    value["candidate"].update({
        "release": RELEASE,
        "source_driver": bind(DRIVER),
        "terminal_return_guard": True,
    })
    value["terminal_return_guard"] = {
        "feature": PRODUCT.TERMINAL_RETURN_GUARD_FEATURE,
        "ELF_gate": bind(GUARD_RECEIPT),
        "resident_delta_bytes": 0,
        "hardware_status": "pending",
    }
    MANIFEST.write_bytes(L95.CAN.json_bytes(value))
    return value


def reconstruct_wplto() -> dict[str, Any]:
    """Reconstruct the completed WPLTO claim without another link."""
    paths = completed_paths()
    internal = load(paths["receipts"] / "wplto-internal.json")
    qualification = load(paths["receipts"] / "wplto-qualification.json")
    base_result = load(paths["receipts"] / "wplto-base-result.json")
    raw = load(paths["receipts"] / "wplto-raw.json")
    # configure_wplto() is a path/authority binder as well as the link setup.
    # Enter it without invoking its driver so the read-only replacement gates
    # see this card's frozen receipts rather than their historical defaults.
    old = L95.CAN.configure_wplto()
    try:
        PRODUCT.configure_intern_session_service()
        replacement = L95.CAN.fresh_current_product_postlink_gate()
        linked_gate = bind(L95.CAN.LINK_GATE.LINKED_GATE)
        linked_receipt = load(L95.CAN.LINK_GATE.LINKED_GATE)
    finally:
        L95.CAN.restore_wplto(old)
    require(
        internal.get("status")
            == "passed-new-c2-lite-real-abi-identity-hardware-not-run"
        and base_result.get("status")
            == "FIRST RED: product-shaped two-region package did not close"
        and base_result.get("WPLTO", {}).get("return_code") == 2
        and base_result.get("WPLTO", {}).get("product_completed") is True
        and base_result.get("WPLTO", {}).get("exception") is None
        and raw.get("status")
            == "FIRST RED: historical checker stopped current-product L-full keymap WPLTO"
        and raw.get("error")
            == "historical post-WPLTO qualification checker red"
        and qualification.get("status")
            == "FIRST RED: final E000-S1 map or qualification did not close"
        and replacement["status"]
            == "passed-current-v4-pre-publish-WPLTO-closure",
        "Link-96 frozen WPLTO reconstruction red")
    require(
        linked_receipt["status"]
            == "passed-single-submit-local-observation-and-complete-leaf-ABI"
        and linked_receipt["completion"]["status"]
            == "passed-linked-stateless-mode-derived-completion-length"
        and linked_receipt["assembler_ABI"]["status"]
            == "passed-all-assembler-leaf-abi-contracts",
        "Link-96 frozen linked completion/ABI receipt red")
    return {
        "status": (
            "passed-one-current-WPLTO-closure-at-typed-historical-"
            "qualification-boundary"),
        "publish_last_authority":
            f"0x{PRODUCT.LINK60_VERIFIER_BINDING_BASE:04x}",
        "historical_profile_label":
            "0xb94e retained only inside the sealed legacy profile text",
        "historical_checker_boundary": {
            "classification":
                "qualification-model-only-not-a-product-or-link-red",
            "raw_status": raw["status"],
            "raw_error": raw["error"],
            "captured_driver_log": bind(
                paths["receipts"] / "wplto-historical-driver.log"),
            "current_replacement_gates": replacement,
        },
        "qualification": bind(paths["receipts"] / "wplto-qualification.json"),
        "linked_gate": linked_gate,
    }


def frozen_wplto_artifacts() -> dict[str, Any]:
    return {
        "product": bind(BUILD / "wplto/lisp65-c2-substitution-linked.prg"),
        "ELF": bind(BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"),
        "map": bind(BUILD / "wplto/lisp65-c2-substitution-linked.prg.map"),
        "internal": bind(BUILD / "receipts/wplto-internal.json"),
        "guard": bind(GUARD_RECEIPT),
    }


def record_completion_first_red() -> dict[str, Any]:
    value = {
        "format": "lisp65-c2.3-link96-terminal-guard-completion-first-red-v1",
        "recorded_on": "2026-08-11",
        "status": "FIRST RED: artifact closer configured append geometry twice",
        "error": "require-resolver profile selector order drift",
        "product_link_completed": True,
        "artifact_completion_completed": False,
        "product_relink_authorized": False,
        "broken_driver": BROKEN_COMPLETION_DRIVER,
        "frozen_wplto_artifacts": frozen_wplto_artifacts(),
        "repair": (
            "The fresh-process completion entry binds Link-96 identity and "
            "lets the inherited closer own its single configure_card call."),
        "claim_limit": (
            "The guarded product link and ELF gate completed. Artifact "
            "completion, manifest closure, media and hardware did not."),
    }
    if FIRST_RED.exists():
        require(load(FIRST_RED) == value, "Link-96 completion First Red drift")
    else:
        FIRST_RED.parent.mkdir(parents=True, exist_ok=True)
        FIRST_RED.write_bytes(canonical(value))
    return value


def derive_receipt() -> dict[str, Any]:
    paths = completed_paths()
    internal = load(paths["receipts"] / "wplto-internal.json")
    replacement = internal["fresh_replacement_gates"]
    walls = replacement["walls"]
    capacity = replacement["capacity"]
    completion = load(paths["receipts"] / "artifact-completion.json")
    manifest = load(MANIFEST)
    require(
        internal["execution_accounting"]["product_closure_links"] == 1
        and replacement["status"] == "passed"
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] >= 54
        and walls["resident_island_headroom_bytes"] >= 0
        and capacity["session_family_headroom_bytes"] >= 0
        and completion["status"]
            == "passed-no-relink-publish-last-artifact-completion"
        and manifest["terminal_return_guard"]["resident_delta_bytes"] == 0,
        "Link-96 guarded product closure did not close")
    return {
        "format": "lisp65-c2.3-link96-terminal-return-guard-product-v1",
        "recorded_on": "2026-08-11",
        "status": "LINK96-HOST-GREEN; POINT-HARDWARE-ROW-PENDING",
        "attempt_accounting": {
            "product_cards_authorized": 1,
            "product_cards_consumed": 1,
            "product_closure_links": 1,
            "hardware_runs": 0,
        },
        "feature": {
            "define": PRODUCT.TERMINAL_RETURN_GUARD_FEATURE,
            "guard": bind(GUARD_RECEIPT),
            "guarded_transfers": 4,
            "resident_delta_bytes": 0,
            "overlay_quantum_growth_bytes": 0,
            "owner_free_shadow_bytes": 16,
            "clean_cycles_per_transfer": 98,
            "clean_cycles_per_nine_append_defstruct": 3528,
        },
        "geometry": {"walls": walls, "session_capacity": capacity},
        "artifacts": {
            "completion_first_red": bind(FIRST_RED),
            "manifest": bind(MANIFEST),
            "product": bind(paths["final"] / "lisp65-c2-substitution-linked.prg"),
            "ELF": bind(paths["final"] / "lisp65-c2-substitution-linked.prg.elf"),
            "map": bind(paths["final"] / "lisp65-c2-substitution-linked.prg.map"),
            "profile": bind(paths["final"] / "resolved-profile.txt"),
            "completion": bind(paths["receipts"] / "artifact-completion.json"),
            "internal": bind(paths["receipts"] / "wplto-internal.json"),
        },
        "hardware_handoff": {
            "status": "authorized-pending-media",
            "forms": ["(require 'defstruct)", "(defstruct point x y)",
                      "(make-point 3 4)"],
            "expected": "(point 3 4)",
            "readback": "0x0000b582..0x0000b591",
        },
        "claim_limit": (
            "One host-green guarded product. No device completion, defstruct "
            "surface, release or writer attribution is claimed."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("format")
            == "lisp65-c2.3-link96-terminal-return-guard-product-v1"
        and value.get("status")
            == "LINK96-HOST-GREEN; POINT-HARDWARE-ROW-PENDING"
        and value.get("attempt_accounting") == {
            "product_cards_authorized": 1, "product_cards_consumed": 1,
            "product_closure_links": 1, "hardware_runs": 0}
        and value["feature"] == {
            "define": PRODUCT.TERMINAL_RETURN_GUARD_FEATURE,
            "guard": bind(GUARD_RECEIPT), "guarded_transfers": 4,
            "resident_delta_bytes": 0, "overlay_quantum_growth_bytes": 0,
            "owner_free_shadow_bytes": 16, "clean_cycles_per_transfer": 98,
            "clean_cycles_per_nine_append_defstruct": 3528}
        and value["hardware_handoff"]["status"]
            == "authorized-pending-media",
        "Link-96 guarded product claim drift")
    if verify:
        require(value == derive_receipt(), "Link-96 product receipt is stale")
        paths = completed_paths()
        current_guard = fresh_guard_result(
            paths["final"] / "lisp65-c2-substitution-linked.prg.elf",
            paths["final"] / "lisp65-c2-substitution-linked.prg")
        require(guard_semantic_identity(load(GUARD_RECEIPT))
                    == guard_semantic_identity(current_guard),
                "Link-96 terminal guard receipt is stale")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "hide-card": lambda x: x["attempt_accounting"].update(
            product_cards_consumed=0),
        "hide-link": lambda x: x["attempt_accounting"].update(
            product_closure_links=0),
        "claim-hardware": lambda x: x["attempt_accounting"].update(
            hardware_runs=1),
        "grow-resident": lambda x: x["feature"].update(
            resident_delta_bytes=1),
        "grow-overlay-quantum": lambda x: x["feature"].update(
            overlay_quantum_growth_bytes=256),
        "drop-transfer": lambda x: x["feature"].update(guarded_transfers=3),
        "claim-point": lambda x: x["hardware_handoff"].update(status="passed"),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate, verify=False)
        except CardError:
            rejected.append(name)
    require(len(rejected) == len(cases), "Link-96 card mutation survived")
    return rejected


def build_action() -> int:
    require(not BUILD.exists() and not RECEIPT.exists()
            and not GUARD_RECEIPT.exists(), "Link-96 product card is one-shot")
    # Validate the inherited static world before changing the driver's live
    # globals; its historical preflight must retain Link-95 as its authority.
    L95.validate_preflight(load(L95.PREFLIGHT_RECEIPT), verify=True)
    inherited_freight = L95.freight_gates()
    BUILD.mkdir(parents=True)
    shutil.copytree(L95.PREFLIGHT / "static-plane", BUILD / "static-plane")
    paths = configure()
    static = L95.BASE.PROBE.REQ.build_static_plane()
    plane = L95.BASE.PROBE.REQ.F1W.static_gate()
    header = L95.CORE.bind_generated_stdlib_header(paths)
    require(
        static["semantics"]["code_bytes"] == L95.EXPECTED_STATIC
        and plane["static_code_bytes"] == L95.EXPECTED_STATIC
        and header["manifest"] == bind(L95.STDLIB),
        "Link-96 copied static plane failed its inherited gate")
    wplto = L95.CAN.run_wplto()
    # The canonical WPLTO constructs and checks a build-local direct-entry
    # authority after it has installed the current product plane.  Checking
    # the historical module defaults before configure_wplto() would instead
    # compare today's ABI constructor with a July evidence plane and stop
    # before the commissioned card existed.
    direct_receipt = paths["receipts"] / "fresh-direct-entry-contract.json"
    require(direct_receipt.is_file(),
            "Link-96 build-local direct-entry authority absent")
    work_elf = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    work_prg = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
    precompletion_guard = fresh_guard_result(work_elf, work_prg)
    GUARD_RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    GUARD_RECEIPT.write_bytes(canonical(precompletion_guard))
    try:
        complete_in_fresh_process()
    except CardError:
        record_completion_first_red()
        raise
    return finalize_action(
        wplto=wplto, inherited_freight=inherited_freight,
        direct_receipt=direct_receipt, header=header,
        precompletion_guard=precompletion_guard)


def finalize_action(*, wplto: dict[str, Any],
                    inherited_freight: dict[str, Any],
                    direct_receipt: Path, header: dict[str, Any],
                    precompletion_guard: dict[str, Any]) -> int:
    paths = completed_paths()
    final_elf = paths["final"] / "lisp65-c2-substitution-linked.prg.elf"
    final_prg = paths["final"] / "lisp65-c2-substitution-linked.prg"
    require(guard_semantic_identity(fresh_guard_result(final_elf, final_prg))
                == guard_semantic_identity(precompletion_guard),
            "artifact completion changed the terminal guard proof")
    completion = load(paths["receipts"] / "artifact-completion.json")
    manifest = build_manifest(wplto, completion)
    checked = L95.CAN.check()
    require(checked["identity"] == manifest["identity"],
            "Link-96 completed product identity red")
    feature = {
        "status": "passed-Link96-terminal-return-guard-feature-gates",
        "inherited_Link95_freight": inherited_freight,
        "direct_entry": bind(direct_receipt),
        "target_stdlib_header": header,
        "guard": bind(GUARD_RECEIPT),
    }
    (paths["receipts"] / f"{RELEASE}-feature-gates.json").write_bytes(
        canonical(feature))
    value = derive_receipt()
    validate(value, verify=False)
    RECEIPT.write_bytes(canonical(value))
    print("Link-96 terminal return guard: PASS "
          f"text={value['geometry']['walls']['bank0_text_headroom_bytes']} "
          f"e000={value['geometry']['walls']['e000_headroom_bytes']} "
          f"session={value['geometry']['session_capacity']['session_family_headroom_bytes']}")
    return 0


def resume_action() -> int:
    require(BUILD.is_dir() and not RECEIPT.exists()
            and GUARD_RECEIPT.is_file(),
            "Link-96 completion resume boundary absent")
    first_red = record_completion_first_red()
    frozen = first_red["frozen_wplto_artifacts"]
    require(frozen_wplto_artifacts() == frozen,
            "Link-96 frozen WPLTO artifacts changed before resume")
    # Preserve Link-95's historical driver identity while its inherited
    # freight authority is checked; only then rebind the live Link-96 paths.
    inherited_freight = L95.freight_gates()
    # Parent-side configuration binds paths and read-only reconstruction.  The
    # fresh child owns the closer's one and only configure_card invocation.
    paths = configure()
    wplto = reconstruct_wplto()
    direct_receipt = paths["receipts"] / "fresh-direct-entry-contract.json"
    require(direct_receipt.is_file(),
            "Link-96 build-local direct-entry authority absent on resume")
    header = L95.CORE.bind_generated_stdlib_header(paths)
    precompletion_guard = load(GUARD_RECEIPT)
    completion_path = paths["receipts"] / "artifact-completion.json"
    if not completion_path.exists():
        complete_in_fresh_process()
    else:
        completion = load(completion_path)
        require(
            completion["status"]
                == "passed-no-relink-publish-last-artifact-completion"
            and completion["compiler_runs"] == completion["linker_runs"] == 0,
            "Link-96 persisted artifact completion is not resume-safe")
    require(frozen_wplto_artifacts() == frozen,
            "Link-96 completion replay changed a frozen WPLTO artifact")
    return finalize_action(
        wplto=wplto, inherited_freight=inherited_freight,
        direct_receipt=direct_receipt, header=header,
        precompletion_guard=precompletion_guard)


def check_action() -> int:
    validate(load(RECEIPT), verify=True)
    print("Link-96 terminal return guard check: PASS")
    return 0


def selftest() -> int:
    GUARD.semantic_cases()
    guard_mutations = GUARD.mutation_selftest()
    count = 0
    if RECEIPT.is_file():
        value = load(RECEIPT); validate(value, verify=False)
        count = len(mutations(value))
    gates = GATES.read_text(encoding="utf-8")
    require("c2-terminal-return-guard-link96-check:" in gates,
            "Link-96 terminal guard gate is not permanent")
    print("Link-96 terminal return guard selftest: PASS "
          f"guard-mutations={len(guard_mutations)} card-mutations={count}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("build", "resume", "_complete", "check", "selftest"))
    action = parser.parse_args().action
    if action == "_complete":
        os.environ.update(L95.CAN.canonical_build_environment())
        return complete_action()
    if action == "build":
        environment = L95.CAN.canonical_build_environment()
        if any(os.environ.get(key) != value for key, value in environment.items()):
            updated = os.environ.copy(); updated.update(environment)
            os.execve(sys.executable, [sys.executable, str(DRIVER), "build"], updated)
        return build_action()
    if action == "resume":
        environment = L95.CAN.canonical_build_environment()
        if any(os.environ.get(key) != value for key, value in environment.items()):
            updated = os.environ.copy(); updated.update(environment)
            os.execve(sys.executable, [sys.executable, str(DRIVER), "resume"], updated)
        return resume_action()
    if action == "check":
        return check_action()
    return selftest()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, GUARD.GateError, RuntimeError, OSError, ValueError,
            KeyError, json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"Link-96 terminal return guard: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
