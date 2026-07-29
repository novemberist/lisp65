#!/usr/bin/env python3
"""Build the repeatable v1.2.1/Link-77 candidate product from source.

The public ``workbench-product`` entry is bound to the promoted v1.2.1
authority during release preparation.  This driver regenerates the accepted
random/while static plane, performs one current WPLTO closure, completes
publish-last artifacts without relinking, and emits the ordinary 14-role
canonical-product manifest in an isolated build tree.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_phase_v_random_while_wplto as V  # noqa: E402


BASE = V.BASE
CAN = BASE.CAN
BUILD = ROOT / "build/c2.2/v1.2.1-candidate-product"
MANIFEST = BUILD / "canonical-product-manifest.json"
DRIVER = Path(__file__).resolve()
RELEASE = "v1.2.1"
LINK = 77


class CandidateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CandidateError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"candidate artifact absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def run(command: list[str], label: str) -> str:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    require(
        result.returncode == 0,
        f"{label} red ({result.returncode}):\n{result.stdout}",
    )
    return result.stdout


def configure() -> dict[str, Path]:
    """Bind all producers and consumers to the current Link-77 freight."""
    V.configure_candidate()
    BASE.LINK = LINK
    BASE.ROOT_BUILD = BUILD
    BASE.PROBE_BUILD = BUILD
    BASE.LINK_BUILD = BUILD
    BASE.DRIVER = DRIVER
    paths = BASE.configure(BUILD)
    # BASE.configure reconstructs its predecessor plane.  The two accepted
    # Phase-V manifests are the final producer selection and therefore bind
    # after that reconstruction, exactly as in the qualified Link-77 WPLTO.
    V.bind_candidate_specs()
    os.environ.update(CAN.canonical_build_environment())
    return paths


def emit_inherited_manifests() -> dict[str, Any]:
    """Emit all six predecessor manifests without claiming a product plane.

    The tracked profile already names the Link-77 candidate plane, so using
    the old canonical-plane validator here would be circular.  This precursor
    performs only the source emissions that the current single-emitter needs;
    the candidate ``build_static_plane`` below creates and validates the sole
    product plane.
    """
    suites = tuple(CAN.SUITES)
    prefixes = tuple(CAN.PREFIXES)
    run(["make", "fasl-emit-check"], "v1.2.1 L65M emission oracle")
    CAN.COMPILER_TIER.generate(suites[-1])
    manifests: list[Path] = []
    for suite, (prefix, role, base) in zip(suites, prefixes):
        prefix.parent.mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable,
            "tools/host-lisp/bytecode_p0_stdlib.py",
            "--check",
            "--emit-artifacts",
            prefix.relative_to(ROOT).as_posix(),
        ]
        if role == "disk-lib":
            command += ["--artifact-role", role, "--base-addr", str(base)]
        command.append(suite.relative_to(ROOT).as_posix())
        run(command, f"emit inherited role {prefix.name}")
        manifests.append(prefix.with_suffix(".manifest.json"))
    require(
        len(manifests) == 6 and all(path.is_file() for path in manifests),
        "v1.2.1 inherited manifest inventory incomplete",
    )
    return {
        "status": "passed-six-source-emitted-predecessor-manifests",
        "manifests": [CAN.bind(path) for path in manifests],
    }


def bind_generated_stdlib_header(paths: dict[str, Path]) -> dict[str, Any]:
    """Bind the selected stdlib ABI header to the target compiler include.

    The single-emitter plane consumes manifests from their producing build
    trees.  The target C compilation has a deliberately narrower interface:
    it includes ``workbench/stdlib-p0.h`` from the active static-plane root.
    Historical local builds happened to leave that header behind.  A clean
    checkout must instead copy it from the selected random manifest's own
    declared output, so the header and packed stdlib have one producer.
    """
    manifest = load(V.RANDOM_MANIFEST)
    declared = manifest.get("header")
    require(
        isinstance(declared, str) and declared,
        "v1.2.1 random manifest has no declared stdlib header",
    )
    source = ROOT / declared
    target = paths["static"] / "workbench/stdlib-p0.h"
    require(
        source.is_file() and not source.is_symlink(),
        f"v1.2.1 selected stdlib header absent: {source}",
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    require(
        target.read_bytes() == source.read_bytes(),
        "v1.2.1 target stdlib header binding differs from selected producer",
    )
    return {
        "status": "passed-selected-manifest-header-to-target-include",
        "manifest": CAN.bind(V.RANDOM_MANIFEST),
        "source": CAN.bind(source),
        "target": CAN.bind(target),
    }


def complete_action() -> int:
    paths = configure()
    replay = CAN.REPLAY
    original = replay.configure

    def current_geometry() -> None:
        replay.PROFILE.configure()
        replay.BANK2.configure_bank2_stage()
        replay.TWO.configure_two_region()
        replay.LINK60.configure_current_pin_adapters()
        replay.P.configure_intern_session_service()
        replay.P.PRODUCT_ARTIFACTS_MANIFEST = (
            paths["static_product"] / "substitution-artifacts.json")
        require(
            replay.P.RUNTIME_OVERLAY_FORMAT_VERSION == 4
            and replay.P.VERIFIER_BINDING_BASE
                == replay.P.LINK60_VERIFIER_BINDING_BASE == 0xB98A
            and replay.P.PROFILE_RODATA_BYTES == 348
            and replay.P.runtime_binding_bytes() == 40
            and replay.P.total_publish_last_bytes() == 42
            and replay.P.INTERN_SESSION_SERVICE,
            "v1.2.1 artifact-completion geometry drift",
        )

    replay.configure = current_geometry
    try:
        completion = CAN.complete_artifacts()
    finally:
        replay.configure = original
    require(
        completion["status"]
            == "passed-no-relink-publish-last-artifact-completion"
        and completion["compiler_runs"] == completion["linker_runs"] == 0,
        "v1.2.1 artifact completion red",
    )
    print(
        "c2-v1.2.1-candidate-product: ARTIFACT COMPLETION PASS "
        f"product={completion['product']['sha256']} compiler=0 linker=0"
    )
    return 0


def complete_in_fresh_process() -> None:
    environment = os.environ.copy()
    environment.update(CAN.canonical_build_environment())
    result = subprocess.run(
        [sys.executable, str(DRIVER), "_complete"],
        cwd=ROOT,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    require(
        result.returncode == 0,
        "v1.2.1 fresh-process artifact completion red:\n" + result.stdout,
    )
    paths = BASE.paths(BUILD)
    (paths["receipts"] / "artifact-completion.log").write_text(
        result.stdout, encoding="utf-8")


def build_manifest(
    wplto: dict[str, Any],
    completion: dict[str, Any],
) -> dict[str, Any]:
    value = BASE.L69.BASE.build_manifest(wplto, completion)
    value["static_plane"].update({
        "status":
            "passed-v1.2.1-random-while-single-emitter-static-plane",
        "bank2_static_code_bytes": V.EXPECTED_STATIC,
        "entries": V.EXPECTED_ENTRIES,
        "resolutions": V.EXPECTED_RESOLUTIONS,
        "roots": V.EXPECTED_ROOTS,
        "direct_entry_refs": V.EXPECTED_DIRECT_REFS,
        "product_build_id": V.EXPECTED_PRODUCT_ID,
        "bank2_sha256": V.EXPECTED_BANK2_SHA,
        "compiler_carrier": CAN.bind(V.WHILE_MANIFEST),
        "random_manifest": CAN.bind(V.RANDOM_MANIFEST),
        "while_manifest": CAN.bind(V.WHILE_MANIFEST),
    })
    value["candidate"] = {
        "release": RELEASE,
        "pre_promotion": True,
        "public_build_authority_changed": False,
        "source_driver": CAN.bind(DRIVER),
    }
    value["session_service"] = {
        "name": "intern-session-service",
        "slot": 51,
        "bytes": 399,
        "catalog_records": 52,
    }
    MANIFEST.write_bytes(CAN.json_bytes(value))
    return value


def build_action() -> int:
    require(not BUILD.exists(), "v1.2.1 candidate product is one-shot")
    equivalence = run(
        ["make", "equivalence-check"],
        "v1.2.1 candidate equivalence/execution predecessor",
    )
    require(
        "equivalence-completion-canary: COMPLETE lanes=11 executed=447"
            in equivalence,
        "v1.2.1 candidate execution witness absent",
    )
    codemod = run(
        [sys.executable, "tools/host-lisp/v2_workbench_codemod.py"],
        "v1.2.1 candidate Workbench single-emitter suite generation",
    )
    require(
        "v2-workbench-codemod: PASS" in codemod,
        "v1.2.1 candidate generated Workbench suite absent",
    )
    # Emit the complete inherited six-role input set from this checkout before
    # replacing the two changed roles.  Local successor builds used to inherit
    # IDE/IDEX/M65D/buffer manifests from an earlier canonical build; a fresh
    # checkout has no such invisible predecessor.
    inherited_plane = emit_inherited_manifests()
    require(
        inherited_plane["status"]
            == "passed-six-source-emitted-predecessor-manifests",
        "v1.2.1 inherited static-plane source emission red",
    )
    features = V.feature_gates()
    paths = configure()
    static = BASE.PROBE.REQ.build_static_plane()
    plane = BASE.PROBE.REQ.F1W.static_gate()
    header_binding = bind_generated_stdlib_header(paths)
    identity = load(
        paths["static_product"] / "substitution-artifacts.json")
    require(
        static["semantics"]["code_bytes"] == V.EXPECTED_STATIC
        and plane["static_code_bytes"] == V.EXPECTED_STATIC
        and identity["product_build_id_hex"] == V.EXPECTED_PRODUCT_ID
        and identity["entries"] == V.EXPECTED_ENTRIES
        and identity["resolutions"] == V.EXPECTED_RESOLUTIONS
        and identity["roots"] == V.EXPECTED_ROOTS,
        "v1.2.1 source-emitted static plane differs from Link 77",
    )
    wplto = CAN.run_wplto()
    replacement = wplto["historical_checker_boundary"][
        "current_replacement_gates"]
    walls = replacement["walls"]
    capacity = replacement["capacity"]
    require(
        walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] >= 54
        and capacity["session_family_headroom_bytes"] >= 0,
        "v1.2.1 candidate capacity wall red",
    )
    complete_in_fresh_process()
    completion = load(paths["receipts"] / "artifact-completion.json")
    value = build_manifest(wplto, completion)
    checked = CAN.check()
    require(
        checked["identity"] == value["identity"]
        and completion["product"]["sha256"]
            == value["identity"]["resident_prg_sha256"],
        "v1.2.1 completed candidate identity red",
    )
    feature_receipt = {
        "status": "passed-current-source-feature-gates",
        "random": features["random"]["receipt"],
        "while": features["while"]["receipt"],
        "target_stdlib_header": header_binding,
    }
    (paths["receipts"] / f"{RELEASE}-feature-gates.json").write_bytes(
        CAN.json_bytes(feature_receipt))
    print(
        "c2-v1.2.1-candidate-product: PASS "
        f"prg={value['identity']['resident_prg_sha256']} "
        f"bank2={V.EXPECTED_STATIC} "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        f"session={capacity['session_family_headroom_bytes']}"
    )
    return 0


def check_action() -> int:
    configure()
    value = CAN.check()
    require(
        value.get("candidate", {}).get("release") == RELEASE
        and value["static_plane"]["bank2_static_code_bytes"]
            == V.EXPECTED_STATIC
        and value["static_plane"]["bank2_sha256"] == V.EXPECTED_BANK2_SHA,
        "v1.2.1 candidate manifest identity drift",
    )
    print(
        "c2-v1.2.1-candidate-product: CHECK PASS "
        f"prg={value['identity']['resident_prg_sha256']}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "check", "_complete"))
    args = parser.parse_args()
    environment = CAN.canonical_build_environment()
    if (
        args.action == "build"
        and any(os.environ.get(key) != value
                for key, value in environment.items())
    ):
        updated = os.environ.copy()
        updated.update(environment)
        os.execve(
            sys.executable,
            [sys.executable, str(DRIVER), "build"],
            updated,
        )
    if args.action == "_complete":
        return complete_action()
    if args.action == "check":
        return check_action()
    return build_action()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        CandidateError, RuntimeError, OSError, ValueError, KeyError,
        json.JSONDecodeError, subprocess.SubprocessError,
    ) as error:
        print(
            "c2-v1.2.1-candidate-product: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
