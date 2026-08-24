#!/usr/bin/env python3
"""Run the one authorized v1.6 R1 abort-driver relocation card."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_product_substitution_link as PRODUCT_LINK  # noqa: E402
import c2_v160_abort_driver_relocation as GATE  # noqa: E402
import c2_v160_abort_driver_relocation_config as R1  # noqa: E402
import c2_v160_comfort_input_fidelity as CANDIDATE  # noqa: E402
import c2_v21_wysiwyg_text_recovery_replacement_card as PRODUCT  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v1.6-abort-driver-relocation-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-abort-driver-relocation-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PROJECTED_OWNERSHIP = PREFLIGHT / "projected-ownership-contract.json"
PROJECTED_FULL_MAP = PREFLIGHT / "projected-full-map-authority.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
ABI_REPORT = BUILD / "wplto/c2-asm-leaf-abi.json"
R1_REPORT = BUILD / "abort-driver-relocation-host.json"
PRODUCT_ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PRODUCT_PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
RECEIPT = ARCH / "c2.3-v1.6-abort-driver-relocation-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-abort-driver-relocation-card-final-red.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "aa335881"
LINK = 117
FORMAT = "lisp65-c2-v160-abort-driver-relocation-card-v1"
STATUS = "PASS: V1.6 R1 ABORT-DRIVER RELOCATION GREEN"


class CardError(RuntimeError): pass
class DryLinkReached(RuntimeError): pass


def require(value: bool, message: str) -> None:
    if not value: raise CardError(message)


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


def roots(build: Path = BUILD, preflight: Path = PREFLIGHT) -> dict[str, str]:
    return {"build": build.relative_to(ROOT).as_posix(),
            "preflight": preflight.relative_to(ROOT).as_posix(),
            "projected_ownership": (preflight /
                "projected-ownership-contract.json").relative_to(ROOT).as_posix(),
            "projected_full_map": (preflight /
                "projected-full-map-authority.json").relative_to(ROOT).as_posix()}


def set_product_paths(build: Path = BUILD, preflight: Path = PREFLIGHT) -> None:
    PRODUCT.BUILD = build; PRODUCT.PREFLIGHT = preflight
    PRODUCT.PREFLIGHT_RECEIPT = preflight / "preflight.json"
    PRODUCT.SEMANTIC_RECEIPT = preflight / "semantic-repl-compile.json"
    PRODUCT.INVOCATION = preflight / "card-invocation.json"
    PRODUCT.PROJECTED_OWNERSHIP = preflight / "projected-ownership-contract.json"
    PRODUCT.PROJECTED_FULL_MAP = preflight / "projected-full-map-authority.json"
    PRODUCT.PRODUCER_RESULT = build / "producer-result.json"
    PRODUCT.SCOPE_RESULT = build / "owner-scope-result.json"
    PRODUCT.ACCEPTANCE_RESULT = build / "artifact-acceptance.json"
    PRODUCT.ABI_REPORT = build / "wplto/c2-asm-leaf-abi.json"
    PRODUCT.RECEIPT = build / "unused-product-receipt.json"
    PRODUCT.FINAL_RED = build / "unused-product-final-red.json"
    PRODUCT.DRIVER = DRIVER; PRODUCT.LINK = LINK


def bind_paths_only(build: Path = BUILD,
                    preflight: Path = PREFLIGHT) -> dict[str, str]:
    set_product_paths(build, preflight)
    PRODUCT.set_paths()
    current = CANDIDATE.output_root_snapshot()
    require(current == roots(build, preflight),
            "R1 output-root rebind did not reach the real producer")
    return current


def install(build: Path = BUILD, preflight: Path = PREFLIGHT) -> None:
    set_product_paths(build, preflight)
    PRODUCT.install()
    root = PRODUCT.BASE.PRODUCT.BASE
    R1.install_root_hook(root, root.PRODUCT)


def write_projections() -> None:
    root = PRODUCT.BASE.PRODUCT.BASE
    root.write_projections()
    ownership = load(PROJECTED_OWNERSHIP)
    full_map = load(PROJECTED_FULL_MAP)
    ownership, full_map = R1.project_contracts(ownership, full_map)
    PROJECTED_OWNERSHIP.write_bytes(canonical(ownership))
    PROJECTED_FULL_MAP.write_bytes(canonical(full_map))


def install_static(root: Path) -> dict[str, Any]:
    return CANDIDATE.install_candidate_static_plane_only(
        root / "static-plane/narrow-static")


def dry_child() -> None:
    build = PREFLIGHT / "real-producer-dry-build"
    preflight = PREFLIGHT / "real-producer-dry-preflight"
    install(build, preflight)
    static = install_static(build)
    bind_paths_only(build, preflight)

    # Bind the R1 globals to the dry target while retaining the installed hook.
    global PROJECTED_OWNERSHIP, PROJECTED_FULL_MAP
    old = PROJECTED_OWNERSHIP, PROJECTED_FULL_MAP
    PROJECTED_OWNERSHIP = preflight / "projected-ownership-contract.json"
    PROJECTED_FULL_MAP = preflight / "projected-full-map-authority.json"
    try:
        write_projections()
    finally:
        PROJECTED_OWNERSHIP, PROJECTED_FULL_MAP = old
    require(static["consumer_observed_bytes"] == 46043,
            "R1 dry candidate static plane drift")

    reached = False
    def stop(*_args: Any, **_kwargs: Any) -> None:
        nonlocal reached
        reached = True
        raise DryLinkReached("R1 real single_link reached")
    PRODUCT_LINK.single_link = stop
    try:
        PRODUCT.BASE.produce_child()
    except DryLinkReached:
        print("R1 REAL PRODUCER PREFLIGHT PASS single-link-reached WPLTO=0 link=0")
        return
    except Exception as error:
        elf = build / "wplto/lisp65-c2-substitution-linked.prg.elf"
        prg = build / "wplto/lisp65-c2-substitution-linked.prg"
        if (str(error) == "producer did not emit the linked candidate artifacts"
                and reached and not elf.exists() and not prg.exists()):
            print("R1 REAL PRODUCER PREFLIGHT PASS "
                  "single-link-sentinel-recorded WPLTO=0 link=0")
            return
        raise
    raise CardError("R1 dry producer missed real single_link")


def run_child(action: str) -> str:
    result = subprocess.run([sys.executable, str(DRIVER), action], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0, f"R1 child {action} red:\n{result.stdout}")
    return result.stdout


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "R1 card is one-shot")
    gate = GATE.derive(micro_root=ROOT / "build/c2.3/v1.6-r1-micro")
    gate["mutations_rejected"] = GATE.mutations(gate, False)
    PREFLIGHT.mkdir(parents=True)
    dry = run_child("_dry")
    value = {"format": "lisp65-c2-v160-abort-driver-relocation-preflight-v1",
        "recorded_on": "2026-08-18", "status": "PASS: R1 CARD ARMED 0/1",
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "media_builds": 0, "device_contacts": 0},
        "authority": {"owner": GATE.git_authority(),
            "study": bind(GATE.STUDY), "driver": bind(DRIVER),
            "configurator": bind(Path(R1.__file__)), "gate": bind(Path(GATE.__file__))},
        "gate": gate,
        "real_producer_lifecycle": {"status": "passed-to-single-link",
            "WPLTO_runs": 0, "product_links": 0,
            "witness": " ".join(dry.split())},
        "worst_state_claim": "active mapped-far bodies cannot reach abort cleanup",
        "claim_limit": "Preflight only; no WPLTO, product link, media or device."}
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("v1.6 R1: PREFLIGHT PASS card=0/1 facade=98 pad=10")


def produce_child() -> None:
    install()
    install_static(BUILD)
    bind_paths_only()
    write_projections()
    raise SystemExit(PRODUCT.BASE.produce_child())


def scope_child() -> None:
    install(); install_static(BUILD); bind_paths_only()
    raise SystemExit(PRODUCT.BASE.scope_child())


def acceptance_child() -> None:
    install(); install_static(BUILD); bind_paths_only()
    raise SystemExit(PRODUCT.BASE.acceptance_child())


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    values = {"ELF": bind(PRODUCT_ELF), "PRG": bind(PRODUCT_PRG)}
    for name, path in (("map", BUILD / "wplto/lisp65-c2-substitution-linked.map"),
                       ("lto", BUILD / "wplto/resident-island-seed.prg.lto.o")):
        if path.is_file(): values[name] = bind(path)
    return values


def card() -> None:
    require(PREFLIGHT_RECEIPT.is_file() and not BUILD.exists()
            and not INVOCATION.exists() and not RECEIPT.exists()
            and not FINAL_RED.exists(), "R1 card lifecycle drift")
    preflight_value = load(PREFLIGHT_RECEIPT)
    require(preflight_value["status"] == "PASS: R1 CARD ARMED 0/1"
            and preflight_value["real_producer_lifecycle"]["status"] ==
                "passed-to-single-link",
            "R1 persisted preflight drift")
    GATE.validate(preflight_value["gate"], False)
    require(preflight_value["gate"]["mutations_rejected"] ==
                GATE.mutations(preflight_value["gate"], False),
            "R1 preflight mutation receipt drift")
    INVOCATION.write_bytes(canonical({"status": "INVOKED", "card": "R1 1/1",
        "WPLTO_runs": 1, "product_links": 1,
        "exceptionless": True, "preflight": bind(PREFLIGHT_RECEIPT),
        "driver": bind(DRIVER)}))
    output = run_child("_produce")
    require(PRODUCT_ELF.is_file() and PRODUCT_PRG.is_file(),
            "R1 producer returned without linked product")
    before = frozen_artifacts()
    run_child("_scope")
    run_child("_accept")
    after = frozen_artifacts()
    require(before == after, "R1 qualification changed linked artifacts")

    host = GATE.derive(PRODUCT_ELF, BUILD / "r1-final-micro")
    host["mutations_rejected"] = GATE.mutations(host, True)
    R1_REPORT.write_bytes(canonical(host))
    abi = subprocess.run([sys.executable,
        str(HOST / "c2_asm_leaf_abi_gate.py"), "--elf", str(PRODUCT_ELF),
        "--out", str(ABI_REPORT)], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(abi.returncode == 0
            and "passed-all-assembler-leaf-abi-contracts" in abi.stdout,
            f"R1 transitive ABI/every-exit gate red:\n{abi.stdout}")
    abi_value = load(ABI_REPORT)
    transitive = abi_value["transitive_callee_saved_preservation"]
    exits = abi_value["contractual_mapped_far_exit_preservation"]
    require(transitive["status"].startswith("passed-")
            and transitive["model"]["unpreserved_callee_saved_writers"] == []
            and exits["status"] ==
                "passed-eight-contractual-service-exits-preserved",
            "R1 linked ABI/exit report drift")
    producer, scope, acceptance = (load(PRODUCER_RESULT), load(SCOPE_RESULT),
                                    load(ACCEPTANCE_RESULT))
    require(len({os.getpid(), producer["pid"], scope["pid"],
                 acceptance["pid"]}) == 4 and acceptance["status"] == "PASS",
            "R1 process isolation/acceptance drift")
    receipt = {"format": FORMAT, "recorded_on": "2026-08-18",
        "status": STATUS,
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "WPLTO_runs": 1, "product_links": 1, "media_builds": 0,
            "device_contacts": 0},
        "authority": {"owner": GATE.git_authority(),
            "study": bind(GATE.STUDY), "preflight": bind(PREFLIGHT_RECEIPT),
            "driver": bind(DRIVER)},
        "artifacts_before": before, "artifacts_after": after,
        "relocation": host["linked"], "host_gate": bind(R1_REPORT),
        "ABI_and_exit_gate": bind(ABI_REPORT),
        "process_isolation": {"parent": os.getpid(), "producer": producer["pid"],
            "owner_scope": scope["pid"], "acceptance": acceptance["pid"],
            "all_distinct": True},
        "stdout_tail": " ".join(output.split()[-30:]),
        "next": "independent review; input-fidelity reopen remains parked",
        "claim_limit": "R1 product card only; no Completion, media or device."}
    RECEIPT.write_bytes(canonical(receipt))
    print("v1.6 R1: CARD PASS card=1/1 service=1382 facade=98 E000-free=195")


def record_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists(): return
    artifacts = {name: bind(path) for name, path in
        (("ELF", PRODUCT_ELF), ("PRG", PRODUCT_PRG)) if path.is_file()}
    FINAL_RED.write_bytes(canonical({"format": FORMAT + "-final-red",
        "recorded_on": "2026-08-18",
        "status": "FINAL RED: R1 ABORT-DRIVER RELOCATION RETURNS TO OWNER",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            # Invocation authorizes and starts exactly one WPLTO/link attempt;
            # an early linker refusal can correctly leave no final artifact.
            "WPLTO_runs": 1, "product_link_attempts": 1,
            "media_builds": 0, "device_contacts": 0},
        "artifacts": artifacts, "retry_authorized": False,
        "owner_disposition_required": True,
        "input_fidelity_reopen_parked": True,
        "authority": {"preflight": bind(PREFLIGHT_RECEIPT),
                      "driver": bind(DRIVER)}}))


def check() -> None:
    if RECEIPT.exists(): print("v1.6 R1: CHECK PASS card=1/1")
    elif FINAL_RED.exists(): print("v1.6 R1: CHECK FINAL RED")
    elif PREFLIGHT_RECEIPT.exists(): print("v1.6 R1: CHECK ARMED")
    else: print("v1.6 R1: CHECK LOCKED")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "card", "check",
                                           "_dry", "_produce", "_scope",
                                           "_accept"))
    action = parser.parse_args().action
    {"preflight": preflight, "card": card, "check": check,
     "_dry": dry_child, "_produce": produce_child,
     "_scope": scope_child, "_accept": acceptance_child}[action]()
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: record_red(error)
            except Exception as receipt_error:
                print(f"R1 Final Red receipt failure: {receipt_error}", file=sys.stderr)
        print(f"v1.6 R1: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
