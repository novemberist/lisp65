#!/usr/bin/env python3
"""Link the v1.7 IDE idle/blink card against its fresh current Bank-2 plane."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_lite_v6_product_probe as V6  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_substitution_artifacts as SUB  # noqa: E402
import c2_top_level_macro_redispatch_link94 as L94  # noqa: E402
import c2_v160_clean_product_candidate as BASE  # noqa: E402
import c2_v160_comfort_input_fidelity as CANDIDATE  # noqa: E402
import c2_v17_ide_idle_blink_card as HOST_GATE  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
CONTRACT = ROOT / "config/c2-v17-ide-idle-blink-card-contract.json"
HOST_RECEIPT = ARCH / "c2.3-v1.7-ide-idle-blink-card-host-receipt.json"
FIRST_BUILD = ROOT / "build/c2.3/v1.7-ide-idle-blink-product-card"
FIRST_PREFLIGHT = ROOT / "build/c2.3/v1.7-ide-idle-blink-product-preflight"
SECOND_BUILD = ROOT / "build/c2.3/v1.7-ide-idle-blink-product-card-r1"
SECOND_PREFLIGHT = ROOT / "build/c2.3/v1.7-ide-idle-blink-product-preflight-r1"
THIRD_BUILD = ROOT / "build/c2.3/v1.7-ide-idle-blink-product-card-r2"
THIRD_PREFLIGHT = ROOT / "build/c2.3/v1.7-ide-idle-blink-product-preflight-r2"
FOURTH_BUILD = ROOT / "build/c2.3/v1.7-ide-idle-blink-product-card-r3"
FOURTH_PREFLIGHT = ROOT / "build/c2.3/v1.7-ide-idle-blink-product-preflight-r3"
FIFTH_BUILD = ROOT / "build/c2.3/v1.7-ide-idle-blink-product-card-r4"
FIFTH_PREFLIGHT = ROOT / "build/c2.3/v1.7-ide-idle-blink-product-preflight-r4"
SIXTH_BUILD = ROOT / "build/c2.3/v1.7-ide-idle-blink-product-card-r5"
SIXTH_PREFLIGHT = ROOT / "build/c2.3/v1.7-ide-idle-blink-product-preflight-r5"
SEVENTH_BUILD = ROOT / "build/c2.3/v1.7-ide-idle-blink-product-card-r6"
SEVENTH_PREFLIGHT = ROOT / "build/c2.3/v1.7-ide-idle-blink-product-preflight-r6"
BUILD = ROOT / "build/c2.3/v1.7-ide-idle-blink-product-card-r7"
PREFLIGHT = ROOT / "build/c2.3/v1.7-ide-idle-blink-product-preflight-r7"
PLANE = ROOT / "build/c2.3/v1.7-ide-idle-blink-current-plane"
PLANE_RECEIPT = PLANE / "plane-preflight.json"
RECEIPT = ARCH / "c2.3-v1.7-ide-idle-blink-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.7-ide-idle-blink-product-card-final-red.json"
FIRST_RED = ARCH / "c2.3-v1.7-ide-idle-blink-product-card-first-red.json"
SECOND_RED = ARCH / "c2.3-v1.7-ide-idle-blink-product-card-second-red.json"
THIRD_RED = ARCH / "c2.3-v1.7-ide-idle-blink-product-card-third-red.json"
FOURTH_RED = ARCH / "c2.3-v1.7-ide-idle-blink-product-card-fourth-red.json"
FIFTH_RED = ARCH / "c2.3-v1.7-ide-idle-blink-product-card-fifth-red.json"
SIXTH_RED = ARCH / "c2.3-v1.7-ide-idle-blink-product-card-sixth-red.json"
SEVENTH_RED = ARCH / "c2.3-v1.7-ide-idle-blink-product-card-seventh-red.json"
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
AUTHORIZATION = "f3f83db3"
FORMAT = "lisp65-c2-v17-ide-idle-blink-product-card-adapter-r7-v1"
STATUS = "PASS: V1.7 IDE IDLE BLINK FINAL LINK GREEN"
DRIVER = Path(__file__).resolve()
BUFFER = ROOT / "build/bytecode/dialect-v2/libs/buffer.manifest.json"
LCC = ROOT / "build/post-promotion/v112/compiler/lcc.manifest.json"
SUITES = (
    ROOT / "tests/bytecode/libs/p0-stdlib-ship-input-wait-base.json",
    ROOT / "build/bytecode/dialect-v2/suites/p0-ide-core-lib.json",
    ROOT / "build/bytecode/dialect-v2/suites/p0-ide-extra-lib.json",
    ROOT / "build/bytecode/dialect-v2/suites/p0-m65d-lib.json",
)

ORIGINAL_CONFIGURATION_GATE = BASE.configuration_gate
ORIGINAL_FINAL_GATE = BASE.final_gate


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


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


def run(command: list[str], label: str) -> str:
    result = subprocess.run(command, cwd=ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("card 3 is opened", "one fresh six-role bank-2 emission",
                  "exactly one real wplto/product link",
                  "the linked remainder", "hardware contact remain closed"):
        require(token in text, f"card-3 authority absent: {token}")
    return {"authority": "git-blob", "commit": AUTHORIZATION, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def prefixes(root: Path) -> tuple[tuple[Path, str, str | None], ...]:
    return (
        (root / "stdlib-p0", "stdlib", None),
        (root / "ide", "disk-lib", "0x000000"),
        (root / "idex", "disk-lib", "0x000000"),
        (root / "m65d", "disk-lib", "0x000000"),
    )


def specs(root: Path) -> tuple[tuple[str, str, Path], ...]:
    return (
        ("stdlib-p0", "stdlib", root / "stdlib-p0.manifest.json"),
        ("ide", "ide", root / "ide.manifest.json"),
        ("idex", "idex", root / "idex.manifest.json"),
        ("m65d", "m65d", root / "m65d.manifest.json"),
        ("buffer", "buffer", BUFFER),
        ("lcc", "lcc", LCC),
    )


def profile_bytes(profile: dict[str, Any]) -> bytes:
    return canonical(profile)


def derived_profile(root: Path, product: dict[str, Any], semantics: dict[str, Any]) -> Path:
    profile = load(ROOT / "config/c2-l-full-product-profile.json")
    static = semantics["static_bank2"]
    authority = dict(profile["authority"])
    authority.update({
        "product_manifest": (root / "product/substitution-artifacts.json")
            .relative_to(ROOT).as_posix(),
        "bank2_static_plane": (root / "v6-semantics/bank2-static-code.bin")
            .relative_to(ROOT).as_posix(),
        "compiled_ide_manifest": (root / "ide.manifest.json")
            .relative_to(ROOT).as_posix(),
        "compiled_stdlib_manifest": (root / "stdlib-p0.manifest.json")
            .relative_to(ROOT).as_posix(),
        "successor": {
            "kind": "fresh-card3-six-role-plane",
            "rule": ("current card-3 manifests are emitted once and consumed "
                     "by the real link"),
        },
    })
    profile.update({
        "recorded_on": "2026-08-26",
        "authority": authority,
        "product_build_id": product["product_build_id_hex"],
        "images": product["images"], "entries": product["entries"],
        "resolutions": product["resolutions"], "roots": product["roots"],
        "direct_entry_refs": L94.direct_entry_census(root / "product"),
        "bank2_static_code": {
            "bytes": static["code_bytes"],
            "sha256": static["code_sha256"],
            "headroom_bytes": static["headroom_bytes"],
        },
    })
    path = root / "candidate-profile.json"
    path.write_bytes(profile_bytes(profile))
    return path


def derived_contract(root: Path, code_bytes: int) -> Path:
    contract = load(ROOT / "config/c2-lite-execution-contract.json")
    code = contract["physical_planes"]["code"]
    code["static_use_bytes"] = code_bytes
    code["gross_headroom_bytes"] = 65536 - code_bytes
    path = root / "c2-lite-execution-contract.json"
    path.write_bytes(canonical(contract))
    return path


def derived_header(root: Path, code_bytes: int) -> Path:
    source = (ROOT / "src/c2_lite_static_plane.h").read_text(encoding="utf-8")
    source, count = re.subn(
        r"(#define LISP65_C2_LITE_STATIC_CODE_BYTES )\d+(UL)",
        rf"\g<1>{code_bytes}\2", source)
    require(count == 1, "static-plane byte macro not found exactly once")
    path = root / "c2_lite_static_plane.h"
    path.write_text(source, encoding="utf-8")
    return path


def emit_current_plane() -> dict[str, Any]:
    require(not PLANE.exists(), "card-3 current-plane preflight is one-shot")
    PLANE.mkdir(parents=True)
    run(["make", "v2-workbench-codemod"], "card-3 current codemod")
    for suite, (prefix, role, base) in zip(SUITES, prefixes(PLANE)):
        command = [sys.executable, "tools/host-lisp/bytecode_p0_stdlib.py",
                   "--check", "--emit-artifacts", str(prefix.relative_to(ROOT))]
        if role == "disk-lib":
            command += ["--artifact-role", role, "--base-addr", str(base)]
        command.append(str(suite.relative_to(ROOT)))
        run(command, f"emit current {prefix.name}")
    inventory = specs(PLANE)
    require(all(path.is_file() for _key, _name, path in inventory),
            "fresh six-role manifest inventory incomplete")
    old_sub = (SUB.BUILD, SUB.SPECS)
    old_v6 = (V6.OUT, V6.PRODUCT_IDENTITY, V6.STATIC_CODE_BYTES, V6.A.SPECS)
    try:
        SUB.BUILD = PLANE / "product"; SUB.SPECS = inventory
        product = SUB.build()
        total = sum(int(load(path)["code_bytes"])
                    for _key, _name, path in inventory)
        V6.OUT = PLANE / "v6-semantics"
        V6.PRODUCT_IDENTITY = PLANE / "product/substitution-artifacts.json"
        V6.STATIC_CODE_BYTES = total; V6.A.SPECS = inventory
        V6.OUT.mkdir(parents=True)
        semantics = V6.host_semantics()
    finally:
        SUB.BUILD, SUB.SPECS = old_sub
        V6.OUT, V6.PRODUCT_IDENTITY, V6.STATIC_CODE_BYTES, V6.A.SPECS = old_v6
    static = semantics["static_bank2"]
    require(product["images"] == 6 and static["code_bytes"] == total
            and static["headroom_bytes"] == 65536 - total
            and (PLANE / "v6-semantics/bank2-static-code.bin").stat().st_size == total,
            "fresh card-3 plane geometry drift")
    profile = derived_profile(PLANE, product, semantics)
    header = derived_header(PLANE, total)
    value = {
        "format": "lisp65-c2-v17-ide-idle-blink-plane-preflight-v1",
        "recorded_on": "2026-08-26",
        "status": "PASS: FRESH CARD3 SIX-ROLE PLANE ARMED 0/1",
        "authority": authority(), "host_gate": bind(HOST_RECEIPT),
        "manifests": [bind(path) for _key, _name, path in inventory],
        "product": bind(PLANE / "product/substitution-artifacts.json"),
        "profile": bind(profile), "header": bind(header),
        "bank2": bind(PLANE / "v6-semantics/bank2-static-code.bin"),
        "geometry": {"bytes": total, "headroom_bytes": 65536 - total,
            "images": product["images"], "entries": product["entries"],
            "resolutions": product["resolutions"], "roots": product["roots"],
            "product_build_id": product["product_build_id_hex"],
            "sha256": static["code_sha256"]},
        "accounting": {"WPLTO_runs": 0, "product_links": 0,
                       "media_builds": 0, "device_contacts": 0},
        "claim_limit": "fresh linker-free plane only; one real link remains",
    }
    PLANE_RECEIPT.write_bytes(canonical(value))
    return value


def _target_profile(target: Path, plane: dict[str, Any]) -> Path:
    path = target / "candidate-profile.json"
    shutil.copyfile(PLANE / "candidate-profile.json", path)
    return path


def candidate_compiler_header_authority(
        header: Path, bank2: Path) -> tuple[Path, dict[str, object], int]:
    """Derive the real compiler input from one candidate-owned plane."""
    plane = load(PLANE_RECEIPT)
    geometry = plane["geometry"]
    require(bind(bank2)["sha256"] == geometry["sha256"]
            and bank2.stat().st_size == int(geometry["bytes"]),
            "candidate compiler plane identity drift")
    header_binding = bind(header)
    values = re.findall(
        rb"^#define LISP65_C2_LITE_STATIC_CODE_BYTES ([0-9]+)UL$",
        header.read_bytes(), re.MULTILINE)
    require(values == [str(bank2.stat().st_size).encode()],
            "candidate compiler header is not plane-derived")
    return header, header_binding, bank2.stat().st_size


def bind_current_plane(target: Path) -> dict[str, Any]:
    """Bind an already materialized preflight-owned plane read-only."""
    plane = load(PLANE_RECEIPT)
    inventory = specs(PLANE)
    geometry = plane["geometry"]
    product_path = target / "product/substitution-artifacts.json"
    profile = target / "candidate-profile.json"
    header = target / "c2_lite_static_plane.h"
    contract = target / "c2-lite-execution-contract.json"
    bank2 = target / "v6-semantics/bank2-static-code.bin"
    product = load(product_path)
    require(bind(bank2)["sha256"] == geometry["sha256"]
            and bank2.stat().st_size == geometry["bytes"]
            and product["entries"] == geometry["entries"]
            and product["resolutions"] == geometry["resolutions"]
            and product["roots"] == geometry["roots"],
            "materialized link plane differs from preflight")

    V6.OUT = target / "v6-semantics"
    V6.PRODUCT_IDENTITY = product_path
    V6.STATIC_CODE_BYTES = int(geometry["bytes"])
    V6.A.SPECS = inventory

    # Bind the product compiler and all historical static-plane adapters to
    # this candidate-derived world.  Values are derived, never pinned.
    PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = product_path
    PRODUCT.INITIAL_C2D = ROOT / product["artifacts"]["initial_c2d"]["path"]
    PRODUCT.PRODUCT_SHELF = ROOT / product["artifacts"]["shelf"]["path"]
    PRODUCT.configure_compiler_consumed_static_header(
        header, bind(header), int(geometry["bytes"]))
    # Inherited configurators may still bind their sealed historical header
    # after this setup seam.  Resolve again at each of the two real
    # compile_link consumers so configuration order cannot replace the
    # candidate-owned path/value pair.
    PRODUCT.configure_compiler_consumed_static_header_resolver(
        lambda header=header, bank2=bank2:
            candidate_compiler_header_authority(header, bank2))
    CANDIDATE.ZERO_LITERAL.LINKED_PRODUCT_INVENTORY = (product_path, target)

    import c2_require_resolver_wplto as require_plane
    import c2_top_level_macro_redispatch_link94 as link94
    import c2_v150_release_preflight as release_preflight
    import c2_v20_ownership_recharter as ownership_qualifier

    # Profile and freight are one identity pair.  Rebinding only BUILD makes
    # the live ownership qualifier compare the card-3 plane with its sealed
    # v2.0 profile even though both candidate-owned sides are available.
    ownership_qualifier.CANDIDATE_PROFILE = profile
    ownership_qualifier.CANDIDATE_HEADER = header
    ownership_qualifier.CANDIDATE_CONTRACT = contract

    require_plane.STATIC = target
    require_plane.STATIC_PRODUCT = target / "product"
    require_plane.V6_OUT = target / "v6-semantics"
    require_plane.SPECS = inventory
    require_plane.EXPECTED_STATIC = int(geometry["bytes"])
    require_plane.EXPECTED_ENTRIES = int(geometry["entries"])
    require_plane.EXPECTED_RESOLUTIONS = int(geometry["resolutions"])
    require_plane.EXPECTED_ROOTS = int(geometry["roots"])

    inherited_v112_configure = link94.V112.configure
    link94.specs = lambda: inventory

    def current_v112_paths(build: Path) -> dict[str, Path]:
        paths = inherited_v112_configure(build)
        # Link-95 replaces link94.specs() at the real caller with its
        # candidate-owned copied-stdlib projection.  Consume that resolved
        # view rather than the earlier registration-time inventory.
        resolved = tuple(link94.specs())
        link94.CAN.SPECS = resolved
        req = link94.V112.P.BASE.PROBE.REQ
        req.SPECS = resolved; req.F1W.SPECS = resolved
        req.F1W.PLANE.FRESH_MANIFESTS = tuple(
            path for _k, _n, path in resolved)
        return paths

    link94.V112.configure = current_v112_paths
    release_preflight.BUILD = target.parent.parent
    release_preflight.STATIC = target
    release_preflight.STDLIB_PREFIX = target / "stdlib-p0"
    release_preflight.STDLIB = inventory[0][2]
    release_preflight.PRODUCT = product_path
    release_preflight.V6_PLANE = target / "v6-semantics"
    release_preflight.BASE_SPECS = inventory[1:]
    inherited_release_build = release_preflight.emit_static_plane

    def current_release_build_static_plane() -> dict[str, Any]:
        # This is the real consumer that historically reconstructs its own
        # six-role view.  Rebind immediately before it assigns V6.A.SPECS.
        release_preflight.STDLIB_PREFIX = target / "stdlib-p0"
        release_preflight.STDLIB = inventory[0][2]
        release_preflight.BASE_SPECS = inventory[1:]
        require(tuple(release_preflight.specs()) == inventory,
                "v1.5 release preflight did not consume card-3 specs")
        return inherited_release_build()

    release_preflight.emit_static_plane = current_release_build_static_plane

    inherited_build = require_plane.build_static_plane

    def current_build_static_plane() -> dict[str, Any]:
        require_plane.SPECS = inventory
        return inherited_build()

    require_plane.build_static_plane = current_build_static_plane
    f1 = require_plane.F1W
    inherited_f1 = f1.static_gate

    def current_f1_gate() -> dict[str, Any]:
        f1.STATIC_PRODUCT = target / "product"
        f1.SPECS = inventory
        f1.EXPECTED_STATIC = int(geometry["bytes"])
        f1.EXPECTED_ENTRIES = int(geometry["entries"])
        f1.EXPECTED_RESOLUTIONS = int(geometry["resolutions"])
        f1.EXPECTED_ROOTS = int(geometry["roots"])
        f1.CAN.PROFILE = profile
        f1.CAN.CONTRACT = contract
        f1.CAN.HEADER = header
        f1.PLANE.FRESH_ROOT = target
        f1.PLANE.FRESH_PRODUCT = product_path
        f1.PLANE.FRESH_IDE = inventory[1][2]
        f1.PLANE.FRESH_BANK2 = bank2
        f1.PLANE.FRESH_MANIFESTS = tuple(path for _k, _n, path in inventory)
        f1.PLANE.CONTRACT = contract
        f1.PLANE.HEADER = header
        return inherited_f1()

    f1.static_gate = current_f1_gate
    return {"consumer_observed_bytes": bank2.stat().st_size,
            "headroom_bytes": 65536 - bank2.stat().st_size,
            "sha256": bind(bank2)["sha256"],
            "product": bind(product_path), "profile": bind(profile),
            "contract": bind(contract), "header": bind(header),
            "bank2": bind(bank2)}


def install_current_plane(target: Path) -> dict[str, Any]:
    """Materialize the exact plane under the setup-owned preflight root."""
    plane = load(PLANE_RECEIPT)
    inventory = specs(PLANE)
    geometry = plane["geometry"]
    target.mkdir(parents=True)
    old_sub = (SUB.BUILD, SUB.SPECS)
    old_v6 = (V6.OUT, V6.PRODUCT_IDENTITY, V6.STATIC_CODE_BYTES, V6.A.SPECS)
    try:
        SUB.BUILD = target / "product"; SUB.SPECS = inventory
        product = SUB.build()
        product_path = target / "product/substitution-artifacts.json"
        derived_header(target, int(geometry["bytes"]))
        V6.OUT = target / "v6-semantics"
        V6.PRODUCT_IDENTITY = product_path
        V6.STATIC_CODE_BYTES = int(geometry["bytes"])
        V6.A.SPECS = inventory
        V6.OUT.mkdir(parents=True)
        semantics = V6.host_semantics()
        # Preserve byte-identical candidate-local manifest identities.  Their
        # artifact members remain SHA-bound to the preflight plane that
        # emitted them.
        for name in ("stdlib-p0", "ide", "idex", "m65d"):
            shutil.copyfile(PLANE / f"{name}.manifest.json",
                            target / f"{name}.manifest.json")
        derived_profile(target, product, semantics)
        derived_contract(target, int(geometry["bytes"]))
    finally:
        SUB.BUILD, SUB.SPECS = old_sub
        V6.OUT, V6.PRODUCT_IDENTITY, V6.STATIC_CODE_BYTES, V6.A.SPECS = old_v6
    require(product["entries"] == geometry["entries"],
            "setup-owned product materialization drift")
    return bind_current_plane(target)


def setup_plane(preflight: Path = PREFLIGHT) -> Path:
    return preflight / "setup-owned/static-plane/narrow-static"


def phase_output_root_gate(*, caller_root: Path, selected_root: Path) -> None:
    """Keep qualification output in the root owned by its real caller."""
    require(selected_root == caller_root,
            "V6 consumer redirected the phase-owned output root")


def install_final_v6_consumer(*, record: bool) -> None:
    """Bind the six roles at the actual V6 host-semantics consumption seam."""
    inventory = specs(PLANE)
    inherited = V6.host_semantics
    require(not getattr(inherited, "_card3_final_consumer", False),
            "card-3 final V6 consumer configured twice")
    events: list[dict[str, Any]] = []
    witness = PREFLIGHT / "real-static-plane-consumer.json"

    def rows(values: tuple[tuple[str, str, Path], ...]) -> list[dict[str, Any]]:
        return [{"key": key, "role": role,
                 "path": path.relative_to(ROOT).as_posix(),
                 "code_bytes": int(load(path)["code_bytes"])}
                for key, role, path in values]

    def current_host_semantics() -> dict[str, Any]:
        observed = tuple(V6.A.SPECS)
        target = setup_plane()
        caller_root = Path(V6.OUT)
        phase_output_root_gate(caller_root=caller_root,
                               selected_root=caller_root)
        V6.PRODUCT_IDENTITY = target / "product/substitution-artifacts.json"
        V6.STATIC_CODE_BYTES = int(load(PLANE_RECEIPT)["geometry"]["bytes"])
        V6.A.SPECS = inventory
        result = inherited()
        expected_output = caller_root / "initial.c2d-v6.bin"
        require(expected_output.is_file(),
                "V6 phase-owned output was not materialized by real consumer")
        mutation_rejected = False
        try:
            phase_output_root_gate(
                caller_root=caller_root,
                selected_root=target / "v6-semantics")
        except RuntimeError:
            mutation_rejected = True
        require(mutation_rejected,
                "setup-owned V6 output-root mutation survived")
        event = {"observed_before_consumer": rows(observed),
                 "consumed_at_consumer": rows(inventory),
                 "observed_bytes": sum(row["code_bytes"]
                                       for row in rows(observed)),
                 "consumed_bytes": sum(row["code_bytes"]
                                       for row in rows(inventory)),
                 "phase_owned_output_root":
                     caller_root.relative_to(ROOT).as_posix(),
                 "setup_owned_input_root": target.relative_to(ROOT).as_posix(),
                 "materialized_output": bind(expected_output),
                 "wrong_root_mutation_rejected": mutation_rejected}
        events.append(event)
        if record:
            witness.write_bytes(canonical({
                "status": "PASS: REAL V6 CONSUMER MATERIALIZED CARD3 SIX-ROLE PLANE",
                "events": events,
                "mutation": {"name": "retain-predecessor-V6.A.SPECS",
                             "rejected": event["observed_bytes"]
                                != event["consumed_bytes"]},
            }))
        return result

    current_host_semantics._card3_final_consumer = True  # type: ignore[attr-defined]
    V6.host_semantics = current_host_semantics


def setup_child(build: Path = BUILD,
                preflight: Path = PREFLIGHT, *, materialize: bool
                ) -> tuple[Any, dict[str, Any], dict[str, object]]:
    core, activation, product_cold = BASE.configure_clean_stack()
    target = setup_plane(preflight)
    static = (install_current_plane(target) if materialize
              else bind_current_plane(target))
    core.bind_paths_only(build, preflight)
    old_projection_paths = (core.PROJECTED_OWNERSHIP,
                            core.PROJECTED_FULL_MAP)
    core.PROJECTED_OWNERSHIP = preflight / "projected-ownership-contract.json"
    core.PROJECTED_FULL_MAP = preflight / "projected-full-map-authority.json"
    try:
        core.write_projections()
    finally:
        (core.PROJECTED_OWNERSHIP,
         core.PROJECTED_FULL_MAP) = old_projection_paths
    require(static["consumer_observed_bytes"] == load(PLANE_RECEIPT)["geometry"]["bytes"],
            "real product setup consumed another Bank-2 extent")
    require((not build.exists()) if materialize else build.is_dir(),
            ("setup-owned plane created the exclusive producer root"
             if materialize else
             "read-only qualification lost the producer-owned root"))
    return core, activation, product_cold


def child_binding_gate() -> dict[str, Any]:
    """Prove the actual child vocabulary and paths before any invocation."""
    expected = {
        "build": BUILD, "preflight": PREFLIGHT, "driver": DRIVER,
        "elf": ELF, "prg": PRG, "receipt": RECEIPT,
    }
    actual = {
        "build": BASE.BUILD, "preflight": BASE.PREFLIGHT,
        "driver": BASE.DRIVER, "elf": BASE.ELF, "prg": BASE.PRG,
        "receipt": BASE.RECEIPT,
    }
    require(actual == expected,
            "real card child did not consume the card-owned path vocabulary")
    saved = BASE.BUILD
    try:
        BASE.BUILD = FIRST_BUILD
        try:
            child_binding_gate()
        except RuntimeError as error:
            rejected = str(error)
        else:
            raise RuntimeError("stale child path mutation survived pre-card")
    finally:
        BASE.BUILD = saved
    return {
        "status": "PASS: REAL CHILD CONSUMES CARD PATH VOCABULARY",
        "paths": {key: path.relative_to(ROOT).as_posix()
                  for key, path in expected.items()},
        "mutation": {"name": "restore-predecessor-build-root",
                     "rejected": rejected},
    }


def record_first_red() -> dict[str, Any]:
    require((FIRST_PREFLIGHT / "preflight.json").is_file()
            and (FIRST_PREFLIGHT / "candidate-invocation.json").is_file()
            and not (FIRST_BUILD / "wplto").exists()
            and not (FIRST_BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf").exists()
            and not (FIRST_BUILD / "wplto/lisp65-c2-substitution-linked.prg").exists(),
            "adapter First Red lifecycle evidence drift")
    value = {
        "format": "lisp65-c2-v17-ide-idle-blink-product-card-first-red-v1",
        "recorded_on": "2026-08-26",
        "status": "FIRST RED: REAL CHILD MISSED CARD PATH VOCABULARY",
        "classification": {
            "family": "real-caller path/vocabulary adapter",
            "mechanism": ("the child process entered the inherited producer "
                          "before installing the card-owned build/preflight rebind"),
            "product_code_exonerated": True,
        },
        "observed": "R1 ownership predecessor geometry drift",
        "expected": "1248 / 0x7d92 / 98 consumed after card-owned rebind",
        "preflight": bind(FIRST_PREFLIGHT / "preflight.json"),
        "invocation": bind(FIRST_PREFLIGHT / "candidate-invocation.json"),
        "attempt_accounting": {
            "cards_consumed": 0, "WPLTO_runs": 0, "product_links": 0,
            "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0,
        },
        "replacement": ("same card, fresh roots, permanent real-child "
                        "path/vocabulary preflight rung"),
    }
    FIRST_RED.write_bytes(canonical(value))
    return value


def record_second_red() -> dict[str, Any]:
    require((SECOND_PREFLIGHT / "preflight.json").is_file()
            and (SECOND_PREFLIGHT / "candidate-invocation.json").is_file()
            and SECOND_BUILD.is_dir()
            and not (SECOND_BUILD / "wplto").exists()
            and not (SECOND_BUILD /
                     "wplto/lisp65-c2-substitution-linked.prg.elf").exists(),
            "setup-ownership Second Red lifecycle evidence drift")
    value = {
        "format": "lisp65-c2-v17-ide-idle-blink-product-card-second-red-v1",
        "recorded_on": "2026-08-26",
        "status": "SECOND RED: SETUP PRECREATED EXCLUSIVE PRODUCER ROOT",
        "classification": {
            "family": "phase/output single ownership",
            "mechanism": ("the fresh Static Plane was materialized below the "
                          "exclusive producer build root before invocation"),
            "guard_held": True,
            "product_code_exonerated": True,
        },
        "observed": "exclusive producer build directory was pre-created",
        "expected": ("setup inputs live below the preflight-owned root; only "
                     "the producer creates its build root"),
        "preflight": bind(SECOND_PREFLIGHT / "preflight.json"),
        "invocation": bind(SECOND_PREFLIGHT / "candidate-invocation.json"),
        "attempt_accounting": {
            "cards_consumed": 0, "WPLTO_runs": 0, "product_links": 0,
            "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0,
        },
        "replacement": ("same card, fresh roots, preflight-owned immutable "
                        "Static Plane input"),
    }
    SECOND_RED.write_bytes(canonical(value))
    return value


def record_third_red() -> dict[str, Any]:
    require((THIRD_PREFLIGHT / "preflight.json").is_file()
            and (THIRD_PREFLIGHT / "candidate-invocation.json").is_file()
            and THIRD_BUILD.is_dir()
            and not (THIRD_BUILD / "wplto").exists()
            and not (THIRD_BUILD /
                     "wplto/lisp65-c2-substitution-linked.prg.elf").exists(),
            "profile-projection Third Red lifecycle evidence drift")
    profile = THIRD_BUILD / "static-plane/narrow-static/candidate-profile.json"
    product_root = THIRD_BUILD / "static-plane/narrow-static/product"
    expected = int(load(profile)["direct_entry_refs"])
    observed = L94.direct_entry_census(product_root)
    require((expected, observed) == (674, 700),
            "profile-projection Third Red identity drift")
    value = {
        "format": "lisp65-c2-v17-ide-idle-blink-product-card-third-red-v1",
        "recorded_on": "2026-08-26",
        "status": "THIRD RED: CANDIDATE PROFILE OMITTED CURRENT DIRECT-ENTRY CENSUS",
        "classification": {
            "family": "candidate-derived projection completeness",
            "mechanism": ("the fresh profile updated bytes, entries, resolutions "
                          "and roots but retained the predecessor direct-entry census"),
            "product_code_exonerated": True,
        },
        "expected_profile_direct_entry_refs": expected,
        "observed_candidate_direct_entry_refs": observed,
        "preflight": bind(THIRD_PREFLIGHT / "preflight.json"),
        "invocation": bind(THIRD_PREFLIGHT / "candidate-invocation.json"),
        "attempt_accounting": {
            "cards_consumed": 0, "WPLTO_runs": 0, "product_links": 0,
            "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0,
        },
        "replacement": ("derive every qualification identity, including "
                        "direct-entry refs, from the materialized candidate"),
    }
    THIRD_RED.write_bytes(canonical(value))
    return value


def record_fourth_red() -> dict[str, Any]:
    require((FOURTH_PREFLIGHT / "preflight.json").is_file()
            and (FOURTH_PREFLIGHT / "candidate-invocation.json").is_file()
            and FOURTH_BUILD.is_dir()
            and not (FOURTH_BUILD / "wplto").exists(),
            "profile/freight pairing Fourth Red lifecycle evidence drift")
    import c2_v150_candidate_product as v150_qualifier
    predecessor_profile = ROOT / (
        "build/c2.3/v2.0-ownership-recharter-inputs/candidate-profile.json")
    candidate_profile = (FOURTH_BUILD /
        "static-plane/narrow-static/candidate-profile.json")
    predecessor = v150_qualifier.profile_geometry(predecessor_profile)
    candidate = v150_qualifier.freight_geometry(FOURTH_BUILD)
    require(v150_qualifier.profile_geometry(candidate_profile) == candidate
            and predecessor != candidate,
            "profile/freight pairing Fourth Red identities drift")
    value = {
        "format": "lisp65-c2-v17-ide-idle-blink-product-card-fourth-red-v1",
        "recorded_on": "2026-08-26",
        "status": "FOURTH RED: LIVE QUALIFIER PAIRED V2.0 PROFILE WITH CARD3 FREIGHT",
        "classification": {
            "family": "identity-scoped qualifier pairing",
            "mechanism": ("the ownership qualifier consumed the current freight "
                          "root while its profile path remained on the v2.0 world"),
            "product_code_exonerated": True,
        },
        "predecessor_profile": predecessor,
        "candidate_profile": candidate,
        "candidate_profile_self_consistent": True,
        "preflight": bind(FOURTH_PREFLIGHT / "preflight.json"),
        "invocation": bind(FOURTH_PREFLIGHT / "candidate-invocation.json"),
        "attempt_accounting": {
            "cards_consumed": 0, "WPLTO_runs": 0, "product_links": 0,
            "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0,
        },
        "replacement": ("bind candidate profile and candidate freight together "
                        "at the real ownership qualifier"),
    }
    FOURTH_RED.write_bytes(canonical(value))
    return value


def record_fifth_red() -> dict[str, Any]:
    require((FIFTH_PREFLIGHT / "preflight.json").is_file()
            and (FIFTH_PREFLIGHT / "candidate-invocation.json").is_file()
            and FIFTH_BUILD.is_dir()
            and not (FIFTH_BUILD / "wplto").exists(),
            "Link-94 specs Fifth Red lifecycle evidence drift")
    registered = [path.relative_to(ROOT).as_posix()
                  for _key, _role, path in specs(PLANE)]
    resolved = list(registered)
    resolved[0] = (FIFTH_BUILD /
        "static-plane/narrow-static/stdlib-p0.manifest.json").relative_to(
            ROOT).as_posix()
    require(registered != resolved
            and all((ROOT / path).is_file() for path in registered)
            and not (ROOT / resolved[0]).exists(),
            "Link-94 registered/resolved path evidence drift")
    value = {
        "format": "lisp65-c2-v17-ide-idle-blink-product-card-fifth-red-v1",
        "recorded_on": "2026-08-26",
        "status": "FIFTH RED: LINK94 COMPARED REGISTRATION VIEW TO RESOLVED VIEW",
        "classification": {
            "family": "real-caller materialized specification projection",
            "mechanism": ("Link-95 replaced link94.specs at the real caller "
                          "with its candidate-owned copied-stdlib view after "
                          "the adapter had stored the registration-time paths"),
            "product_code_exonerated": True,
        },
        "registered_paths": registered,
        "resolved_paths": resolved,
        "resolved_stdlib_present": False,
        "difference": {"role": "stdlib-p0", "index": 0},
        "preflight": bind(FIFTH_PREFLIGHT / "preflight.json"),
        "invocation": bind(FIFTH_PREFLIGHT / "candidate-invocation.json"),
        "attempt_accounting": {
            "cards_consumed": 0, "WPLTO_runs": 0, "product_links": 0,
            "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0,
        },
        "replacement": ("derive CAN.SPECS and every downstream consumer from "
                        "link94.specs() at the real V112 caller"),
    }
    FIFTH_RED.write_bytes(canonical(value))
    return value


def record_sixth_red() -> dict[str, Any]:
    require((SIXTH_PREFLIGHT / "preflight.json").is_file()
            and (SIXTH_PREFLIGHT / "candidate-invocation.json").is_file()
            and SIXTH_BUILD.is_dir()
            and not (SIXTH_BUILD / "wplto").exists(),
            "release-preflight specs Sixth Red lifecycle evidence drift")
    candidate = [(key, path.relative_to(ROOT).as_posix(),
                 int(load(path)["code_bytes"]))
                for key, _role, path in specs(PLANE)]
    require(sum(row[2] for row in candidate) == 52230,
            "release-preflight Sixth Red size decomposition drift")
    value = {
        "format": "lisp65-c2-v17-ide-idle-blink-product-card-sixth-red-v1",
        "recorded_on": "2026-08-26",
        "status": "SIXTH RED: RELEASE PREFLIGHT RECONSTRUCTED HISTORICAL SIX-ROLE PLANE",
        "classification": {
            "family": "bound-not-consumed at real static-plane consumer",
            "mechanism": ("v1.5 release_preflight.build_static_plane rebuilt "
                          "V6.A.SPECS from its historical module globals"),
            "product_code_exonerated": True,
        },
        "observed_consumer_bytes": 46475,
        "observed_consumer_paths": (
            "captured by the permanent real-static-plane-consumer witness "
            "on the successor run"),
        "candidate_specs": candidate,
        "candidate_bytes": 52230,
        "preflight": bind(SIXTH_PREFLIGHT / "preflight.json"),
        "invocation": bind(SIXTH_PREFLIGHT / "candidate-invocation.json"),
        "attempt_accounting": {
            "cards_consumed": 0, "WPLTO_runs": 0, "product_links": 0,
            "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0,
        },
        "replacement": ("bind all six roles at release_preflight."
                        "build_static_plane immediately before V6 consumption"),
    }
    SIXTH_RED.write_bytes(canonical(value))
    return value


def record_seventh_red() -> dict[str, Any]:
    require((SEVENTH_PREFLIGHT / "preflight.json").is_file()
            and (SEVENTH_PREFLIGHT / "candidate-invocation.json").is_file()
            and SEVENTH_BUILD.is_dir()
            and not (SEVENTH_BUILD / "wplto").exists(),
            "profile-authority Seventh Red lifecycle evidence drift")
    profile = load(SEVENTH_BUILD /
        "static-plane/narrow-static/candidate-profile.json")
    require(profile["authority"]["kind"] == "fresh-card3-six-role-plane",
            "profile-authority Seventh Red vocabulary drift")
    value = {
        "format": "lisp65-c2-v17-ide-idle-blink-product-card-seventh-red-v1",
        "recorded_on": "2026-08-26",
        "status": "SEVENTH RED: SUCCESSOR PROFILE REPLACED PUBLIC AUTHORITY VOCABULARY",
        "classification": {
            "family": "additive authority provenance",
            "mechanism": ("the candidate replaced the accepted public-build "
                          "authority kind instead of retaining it and adding "
                          "card-3 successor provenance"),
            "product_code_exonerated": True,
        },
        "observed_kind": profile["authority"]["kind"],
        "required_kind": "fresh-single-emitter-static-plane-dataflow",
        "successor_kind": "fresh-card3-six-role-plane",
        "preflight": bind(SEVENTH_PREFLIGHT / "preflight.json"),
        "invocation": bind(SEVENTH_PREFLIGHT / "candidate-invocation.json"),
        "attempt_accounting": {
            "cards_consumed": 0, "WPLTO_runs": 0, "product_links": 0,
            "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0,
        },
        "replacement": ("retain the public authority kind and add the card-3 "
                        "authority as nested successor provenance"),
    }
    SEVENTH_RED.write_bytes(canonical(value))
    return value


def probe_child() -> None:
    child_binding_gate()
    root = ROOT / "build/c2.3/v1.7-ide-idle-blink-real-child-probe"
    require(not root.exists(), "real-child probe root is not one-shot")
    try:
        setup_child(root / "build", root / "preflight", materialize=True)
        import c2_v150_candidate_product as v150_qualifier
        import c2_v20_ownership_recharter as ownership_qualifier
        candidate_profile = setup_plane(root / "preflight") / "candidate-profile.json"
        candidate_root = root / "preflight/setup-owned"
        require(ownership_qualifier.CANDIDATE_PROFILE == candidate_profile
                and v150_qualifier.profile_geometry(candidate_profile)
                    == v150_qualifier.freight_geometry(candidate_root),
                "real ownership qualifier did not pair candidate profile/freight")
        predecessor_profile = ROOT / (
            "build/c2.3/v2.0-ownership-recharter-inputs/candidate-profile.json")
        require(v150_qualifier.profile_geometry(predecessor_profile)
                    != v150_qualifier.freight_geometry(candidate_root),
                "predecessor-profile pairing mutation did not bite")
        projected = load(
            root / "preflight/projected-ownership-contract.json")
        service = projected["mapped_far_service"]
        require(service["bank2"]["service_bytes"] == 1382
                and service["map_tuple"]["mapped_service_cpu_end_exclusive"]
                    == "0x7e18"
                and service["resident"]["total_bytes"] == 98,
                "real-child predecessor projection did not reach R1 successor")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print("v1.7 IDE idle/blink product: REAL CHILD PREFLIGHT PASS "
          "R1=1248/0x7d92/98 WPLTO=0 link=0")


def configuration_gate() -> dict[str, Any]:
    HOST_GATE.main_check = True  # explicit marker: permanent host receipt is an input
    host = HOST_GATE.build_receipt()
    require(HOST_RECEIPT.read_bytes() == HOST_GATE.canonical(host),
            "card-3 host preflight receipt drift")
    plane = load(PLANE_RECEIPT)
    product = ORIGINAL_CONFIGURATION_GATE()
    require(plane["status"] == "PASS: FRESH CARD3 SIX-ROLE PLANE ARMED 0/1"
            and plane["geometry"]["headroom_bytes"] > 0,
            "card-3 fresh plane preflight red")
    return {**product, "card3": {"host": bind(HOST_RECEIPT),
        "plane_preflight": bind(PLANE_RECEIPT), "geometry": plane["geometry"],
        "device_timing_claim": False, "media_builds": 0, "device_contacts": 0}}


def card3_compiler_consumption() -> dict[str, Any]:
    """Put the candidate plane and both real compiler consumers side by side."""
    plane = load(PLANE_RECEIPT)
    geometry = plane["geometry"]
    target = setup_plane()
    bank2 = target / "v6-semantics/bank2-static-code.bin"
    consumption_paths = [
        BUILD / "wplto/resident-island-seed.prg.compiler-input-consumption.json",
        BUILD / "wplto/lisp65-c2-substitution-linked.prg.compiler-input-consumption.json",
    ]
    consumptions = [load(path) for path in consumption_paths]
    return {"candidate_plane": bind(bank2),
        "candidate_bytes": int(geometry["bytes"]),
        "candidate_sha256": geometry["sha256"],
        "consumers": [{"receipt": bind(path),
            "consumer": row["consumer"], "status": row["status"],
            "consumed_value": int(row["consumed_value"]),
            "bound_header": row["bound_header"],
            "actual_force_include_flags": row["actual_force_include_flags"]}
            for path, row in zip(consumption_paths, consumptions)],
        "all_consumers_current": all(
            row["consumed_value"] == geometry["bytes"]
            and row["status"] == "passed-bound-candidate-header-consumed"
            and row.get("materialized_value") == geometry["bytes"]
            and row.get("materialized_header") == row["bound_header"]
            for row in consumptions)}


def card3_final_gate() -> dict[str, Any]:
    """Qualify only card-3 freight over an already-linked candidate."""
    plane = load(PLANE_RECEIPT)
    geometry = plane["geometry"]
    target = setup_plane()
    consumption = card3_compiler_consumption()
    require(consumption["candidate_plane"]["bytes"] == geometry["bytes"]
            and consumption["candidate_plane"]["sha256"] == geometry["sha256"]
            and consumption["all_consumers_current"] is True,
            "real product compiler did not consume the fresh card-3 Bank-2 plane")
    bank2 = ROOT / consumption["candidate_plane"]["path"]
    headroom = 65536 - bank2.stat().st_size
    require(headroom == geometry["headroom_bytes"] and headroom > 0,
            "linked Bank-2 headroom arithmetic drift")
    return {
        "status": "PASS: IDE IDLE/BLINK PROVED THROUGH REAL PRODUCT LINK",
        "host_gate": bind(HOST_RECEIPT), "plane_preflight": bind(PLANE_RECEIPT),
        "static_product": bind(target / "product/substitution-artifacts.json"),
        "bank2": bind(bank2), "compiler_consumption": consumption,
        "bank2_capacity_bytes": 65536,
        "bank2_static_code_bytes": bank2.stat().st_size,
        "bank2_remaining_headroom_bytes": headroom,
        "compiler_consumers": [row["receipt"]
                               for row in consumption["consumers"]],
        "compiler_consumed_values": [row["consumed_value"]
                                     for row in consumption["consumers"]],
        "exact_three_card_object_freight_bytes": 5049,
        "name_capacity_after_card3": {"symbol_slots": 74, "namepool_bytes": 1076},
        "timing": "historical projection only; device proof deferred",
        "media_builds": 0, "device_contacts": 0,
    }


def final_gate() -> dict[str, Any]:
    product = ORIGINAL_FINAL_GATE()
    return {**product, "card3": card3_final_gate()}


def configure() -> None:
    BASE.BUILD = BUILD; BASE.PREFLIGHT = PREFLIGHT
    BASE.PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
    BASE.INVOCATION = PREFLIGHT / "candidate-invocation.json"
    BASE.ELF = ELF; BASE.PRG = PRG
    BASE.PROFILE = BUILD / "wplto/resolved-profile.txt"
    BASE.PRODUCER_RESULT = BUILD / "producer-result.json"
    BASE.SCOPE_RESULT = BUILD / "owner-scope-result.json"
    BASE.ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
    BASE.RECEIPT = RECEIPT; BASE.DRIVER = DRIVER
    BASE.AUTHORIZATION = AUTHORIZATION; BASE.FORMAT = FORMAT; BASE.STATUS = STATUS
    BASE.authority = authority
    BASE.configuration_gate = configuration_gate
    BASE.final_gate = final_gate


def preflight() -> None:
    require(not any(path.exists() for path in (BUILD, PREFLIGHT, RECEIPT)),
            "IDE idle/blink product card is one-shot")
    host = HOST_GATE.build_receipt()
    require(HOST_RECEIPT.read_bytes() == HOST_GATE.canonical(host),
            "IDE idle/blink host card not green")
    require(PLANE_RECEIPT.is_file(),
            "fresh card-3 plane preflight is absent")
    first_red = record_first_red()
    second_red = record_second_red()
    third_red = record_third_red()
    fourth_red = record_fourth_red()
    fifth_red = record_fifth_red()
    sixth_red = record_sixth_red()
    seventh_red = record_seventh_red()
    configure()
    probe = run([sys.executable, str(DRIVER), "_probe"],
                "real card-child path/vocabulary preflight")
    BASE.preflight()
    value = load(BASE.PREFLIGHT_RECEIPT)
    value["predecessor_First_Red"] = bind(FIRST_RED)
    value["predecessor_Second_Red"] = bind(SECOND_RED)
    value["predecessor_Third_Red"] = bind(THIRD_RED)
    value["predecessor_Fourth_Red"] = bind(FOURTH_RED)
    value["predecessor_Fifth_Red"] = bind(FIFTH_RED)
    value["predecessor_Sixth_Red"] = bind(SIXTH_RED)
    value["predecessor_Seventh_Red"] = bind(SEVENTH_RED)
    value["real_child_preflight"] = {
        "status": "PASS", "witness": " ".join(probe.split()),
        "path_vocabulary": child_binding_gate(),
        "attempt_accounting": second_red["attempt_accounting"],
    }
    require(first_red["attempt_accounting"] == second_red["attempt_accounting"]
            == third_red["attempt_accounting"]
            == fourth_red["attempt_accounting"]
            == fifth_red["attempt_accounting"]
            == sixth_red["attempt_accounting"]
            == seventh_red["attempt_accounting"],
            "pre-product red accounting diverged")
    BASE.PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("v1.7 IDE idle/blink product: PREFLIGHT PASS plane=fresh card=0/1")


def produce_child() -> None:
    child_binding_gate()
    core, _activation, _cold = setup_child(materialize=True)
    install_final_v6_consumer(record=True)
    raise SystemExit(core.PRODUCT.BASE.produce_child())


def scope_child() -> None:
    child_binding_gate()
    core, _activation, _cold = setup_child(materialize=False)
    install_final_v6_consumer(record=False)
    raise SystemExit(core.PRODUCT.BASE.scope_child())


def acceptance_child() -> None:
    child_binding_gate()
    core, _activation, _cold = setup_child(materialize=False)
    install_final_v6_consumer(record=False)
    os.environ["LISP65_R1_ACCEPTANCE_RESULT"] = str(BASE.ACCEPTANCE_RESULT)
    raise SystemExit(core.PRODUCT.BASE.acceptance_child())


def build() -> None:
    configure()
    BASE.build()
    print("v1.7 IDE idle/blink product: BUILD PASS WPLTO=1 link=1")


def semantic_attic_attribution() -> dict[str, Any]:
    generated = BUILD / "wplto/generated-product-sources/c2_product_runtime.c"
    text = generated.read_text(encoding="utf-8")
    entry = V6.c_function_definition(text, "c2_product_entry_read")
    truth = ElfTruth.read(ELF, llvm_readobj=BASE.READOBJ)
    owners = truth.symbols_by_name.get("c2_product_entry_read", [])
    require(len(owners) == 1 and owners[0].bytes > 0,
            "Final Red entry symbol identity drift")
    owner = owners[0]
    targets = sorted({row.target for row in truth.relocations
        if row.source_section_index == owner.section_index
        and owner.value <= row.offset < owner.value + owner.bytes})
    require("c2_map_cpu_read" in targets
            and "c2_stream_shelf_read" not in targets
            and "c2_dma_copy" not in targets
            and "c2_map_cpu_read" in entry
            and "((uint32_t)2u << 16)" in entry
            and "c2_facade_vm_code_load(2u" not in entry,
            "Final Red bank-2 semantic attribution drift")
    return {
        "classification": "source-form pin over semantically equivalent Bank-2 reader",
        "recorded_check": {
            "hot_entry_uses_bank2": False,
            "required_source_literal": "c2_facade_vm_code_load(2u",
        },
        "candidate_semantics": {
            "reader": "c2_map_cpu_read",
            "bank_expression": "((uint32_t)2u << 16)",
            "final_ELF_relocation_present": True,
            "forbidden_shelf_DMA_targets_absent": True,
            "relocation_targets": targets,
        },
        "standing_rule": "semantic equivalence, never mnemonic identity",
        "product_defect": False,
    }


def record_final_red() -> None:
    require(not FINAL_RED.exists() and ELF.is_file() and PRG.is_file()
            and not RECEIPT.exists(),
            "IDE idle/blink Final Red lifecycle drift")
    value = {
        "format": FORMAT + "-final-red",
        "recorded_on": "2026-08-26",
        "status": "FINAL RED: IDE IDLE/BLINK CARD RETURNS FOR REVIEW",
        "authority": authority(),
        "preflight": bind(BASE.PREFLIGHT_RECEIPT),
        "pre_product_reds": [bind(path) for path in (
            FIRST_RED, SECOND_RED, THIRD_RED, FOURTH_RED, FIFTH_RED,
            SIXTH_RED, SEVENTH_RED)],
        "real_static_plane_consumer": bind(
            PREFLIGHT / "real-static-plane-consumer.json"),
        "artifacts": {
            "ELF": bind(ELF), "PRG": bind(PRG),
            "map": bind(BUILD /
                "wplto/lisp65-c2-substitution-linked.prg.map"),
            "lto": bind(BUILD /
                "wplto/lisp65-c2-substitution-linked.prg.lto.o"),
        },
        "stopper": semantic_attic_attribution(),
        "attempt_accounting": {
            "cards_consumed": 1, "WPLTO_runs": 1, "product_links": 1,
            "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0,
        },
        "retry_authorized": False,
        "review_disposition_required": True,
        "recommended_successor": ("convert the no-runtime-Attic bank-2 check "
            "to source-plus-final-ELF semantic identity, then resume the "
            "qualification tail read-only over this frozen pair"),
    }
    FINAL_RED.write_bytes(canonical(value))
    print("v1.7 IDE idle/blink product: FINAL RED RECORDED "
          "WPLTO=1 link=1 review=required")


def check() -> None:
    configure()
    if FINAL_RED.exists() and not RECEIPT.exists():
        value = load(FINAL_RED)
        require(value["status"]
                    == "FINAL RED: IDE IDLE/BLINK CARD RETURNS FOR REVIEW"
                and value["attempt_accounting"] == {
                    "cards_consumed": 1, "WPLTO_runs": 1,
                    "product_links": 1, "scope_runs": 0,
                    "acceptance_runs": 0, "media_builds": 0,
                    "device_contacts": 0}
                and value["artifacts"]["ELF"] == bind(ELF)
                and value["artifacts"]["PRG"] == bind(PRG)
                and value["stopper"] == semantic_attic_attribution(),
                "IDE idle/blink Final Red receipt drift")
        print("v1.7 IDE idle/blink product: CHECK FINAL RED "
              "semantic-bank2=true source-pin=false review=required")
        return
    BASE.check()
    value = load(RECEIPT)
    card = value["final_product"]["card3"]
    require(value["status"] == STATUS
            and card["status"] ==
                "PASS: IDE IDLE/BLINK PROVED THROUGH REAL PRODUCT LINK"
            and card["bank2_remaining_headroom_bytes"]
                == 65536 - card["bank2_static_code_bytes"]
            and card["exact_three_card_object_freight_bytes"] == 5049
            and value["attempt_accounting"] == {
                "WPLTO_runs": 1, "product_links": 1, "scope_runs": 1,
                "acceptance_runs": 1, "media_builds": 0, "device_contacts": 0},
            "IDE idle/blink final receipt drift")
    print("v1.7 IDE idle/blink product: CHECK PASS "
          f"bank2={card['bank2_static_code_bytes']} "
          f"headroom={card['bank2_remaining_headroom_bytes']} device=0")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "preflight", "build", "check", "record-red", "_probe", "_produce",
        "_scope", "_accept"))
    action = parser.parse_args().action
    configure()
    {"preflight": preflight, "build": build, "check": check,
     "record-red": record_final_red,
     "_probe": probe_child,
     "_produce": produce_child, "_scope": scope_child,
     "_accept": acceptance_child}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.7 IDE idle/blink product: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
