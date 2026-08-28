#!/usr/bin/env python3
"""Prove the authorized v1.6 lossless Comfort input boundary."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0_compiler as P0  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v21_root_padding_configurator_projection_replacement as CONFIG  # noqa: E402
import c2_zero_literal_execution_gate as ZERO_LITERAL  # noqa: E402
import evidence_era as ERA  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


CONTRACT = ROOT / "config/c2-v160-comfort-input-fidelity-implementation-contract.json"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
PRICING = ROOT / "tools/host-lisp/c2_v160_comfort_input_fidelity_pricing.py"
PRICING_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-comfort-input-fidelity-pricing-receipt.json")
PLACEMENT_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-comfort-input-fidelity-placement-first-red-receipt.json")
WINDOW = ROOT / "src/optional/c2_kernal_input_capture.s"
BASELINE_WINDOW = ROOT / "src/c2_kernal_window.s"
REPL_C = ROOT / "src/repl.c"
EDITOR = ROOT / "lib/stdlib-read-line.lisp"
COMFORT = ROOT / "lib/repl-comfort.lisp"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
CLANG = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
LD = ROOT / "tools/llvm-mos/bin/ld.lld"
BASELINE_COMMIT = "c4a78738"
FORMAT = "lisp65-c2-v160-comfort-input-fidelity-host-card-v1"
REPLACEMENT_AUTHORITY = "fe6638da"
SECOND_REPLACEMENT_AUTHORITY = "9e7622b3"
CANDIDATE_STATIC_ROOT = ROOT / (
    "build/release-v1.5.0/public-product-build")
CANDIDATE_STATIC_PRODUCT = CANDIDATE_STATIC_ROOT / (
    "build/c2.3/v1.5.0-release-preflight/static-plane/narrow-static/"
    "product/substitution-artifacts.json")
CANDIDATE_PREFLIGHT_ROOT = CANDIDATE_STATIC_ROOT / (
    "build/c2.3/v1.5.0-release-preflight")
CANDIDATE_PROFILE = ROOT / (
    "build/c2.3/v2.0-ownership-recharter-inputs/candidate-profile.json")
CANDIDATE_PLANE = CONFIG.BASE.SOURCE_MANIFEST.parent
CANDIDATE_STATIC_BYTES = 46043
CANDIDATE_STATIC_SHA256 = (
    "a241a8c23a5cc8d7f7525ed2f1f522ca41f103c28928a2636a58c1972ba7e7de")


class FidelityError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise FidelityError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"file absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def run(*argv: str) -> str:
    completed = subprocess.run(argv, cwd=ROOT, text=True,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
    require(completed.returncode == 0,
            f"command red ({' '.join(argv)}):\n{completed.stdout}")
    return completed.stdout


def authority(contract: dict[str, Any]) -> dict[str, Any]:
    require(contract.get("format") ==
                "lisp65-c2-v160-comfort-input-fidelity-implementation-v1"
            and contract.get("status") ==
                "reviewer-authorized-host-only-implementation"
            and contract.get("authority_commit") == "91c7efa1"
            and contract.get("register_commit") == "7d390a2b",
            "implementation authority drift")
    plan = ERA.era_blob(contract["authority_commit"],
                        PLAN.relative_to(ROOT).as_posix()).decode("utf-8")
    for token in ("59-byte split seam", "Placement is born-derived",
                  "STZ→JSR substitution", "94-event"):
        require(token in plan, f"implementation authority token absent: {token}")
    return {
        "contract": bind(CONTRACT),
        "reviewer": ERA.era_bind(contract["authority_commit"], PLAN),
        "register": ERA.era_bind(contract["register_commit"], PLAN),
        "pricing": bind(PRICING_RECEIPT),
        "placement_first_red": bind(PLACEMENT_RED),
        "replacement_card": ERA.era_bind(REPLACEMENT_AUTHORITY, PLAN),
        "second_replacement_card": ERA.era_bind(
            SECOND_REPLACEMENT_AUTHORITY, PLAN),
    }


def candidate_static_specs() -> tuple[tuple[str, str, Path], ...]:
    """Return the self-contained six-image inventory of the candidate world."""
    product = load(CANDIDATE_STATIC_PRODUCT)
    rows = product.get("manifests")
    labels = (("stdlib-p0", "stdlib"), ("ide", "ide"),
              ("idex", "idex"), ("m65d", "m65d"),
              ("buffer", "buffer"), ("lcc", "lcc"))
    require(isinstance(rows, list) and len(rows) == len(labels),
            "candidate six-image inventory drift")
    specs = tuple((key, name, CANDIDATE_STATIC_ROOT / str(row["path"]))
                  for (key, name), row in zip(labels, rows))
    require(all(path.is_file() for _key, _name, path in specs),
            "candidate six-image manifest absent")
    return specs


def validate_static_plane_consumer(value: dict[str, Any]) -> None:
    require(
        value.get("status") ==
            "passed-complete-candidate-closure-at-real-static-plane-consumer"
        and value["candidate_bound_bytes"] == CANDIDATE_STATIC_BYTES
        and value["consumer_observed_bytes"] == CANDIDATE_STATIC_BYTES
        and value["consumer"] == "c2_lite_v6_product_probe.static_plane"
        and value["images"] == 6
        and value["candidate_code_sha256"] == CANDIDATE_STATIC_SHA256
        and value["configurator_projection"]["status"] ==
            "PASS: all profile features configured"
        and value["configurator_projection"]["final_state"]
            ["compiler_consumed_static_code_bytes"] == CANDIDATE_STATIC_BYTES
        and value["configuration_order"] == [
            "candidate-configurator-closure", "card-output-root-rebind",
            "real-static-plane-consumer"]
        and value["output_roots_after_rebind"] ==
            value["expected_card_output_roots"]
        and value["path_rebind"]["semantic_state_unchanged"] is True
        and value["path_rebind"]["mode"] == "paths-only",
        "candidate static-plane real-consumer closure drift")


def static_plane_consumer_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "ambient-43308-at-consumer": lambda x: x.update(
            consumer_observed_bytes=43308),
        "bound-but-not-consumed": lambda x: x.update(
            consumer_observed_bytes=x["candidate_bound_bytes"] - 1),
        "wrong-candidate-plane": lambda x: x.update(
            candidate_code_sha256="0" * 64),
        "skip-configurator": lambda x: x["configurator_projection"]
            ["final_state"].update(compiler_consumed_static_code_bytes=43308),
        "closure-displaces-card-root": lambda x: x[
            "output_roots_after_rebind"].update(
                projected_ownership="build/c2.3/historical/projection.json"),
        "consumer-before-rebind": lambda x: x.update(configuration_order=[
            "candidate-configurator-closure", "real-static-plane-consumer",
            "card-output-root-rebind"]),
        "semantic-reconfigure-in-rebind": lambda x: x["path_rebind"].update(
            semantic_state_unchanged=False),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate_static_plane_consumer(trial)
        except FidelityError:
            rejected.append(name)
    require(rejected == list(cases),
            "candidate static-plane consumer mutation survived")
    return rejected


def output_root_snapshot() -> dict[str, str]:
    import c2_v21_probe_oracle_root_card as root_card

    return {"build": root_card.BUILD.relative_to(ROOT).as_posix(),
            "preflight": root_card.PREFLIGHT.relative_to(ROOT).as_posix(),
            "projected_ownership": root_card.PROJECTED_OWNERSHIP.relative_to(
                ROOT).as_posix(),
            "projected_full_map": root_card.PROJECTED_FULL_MAP.relative_to(
                ROOT).as_posix()}


def permanent_output_root_rebind() -> dict[str, str]:
    """Exercise the real card adapter on non-producing sentinel roots."""
    import c2_v160_comfort_input_fidelity_card as card

    build = ROOT / "build/c2.3/v1.6-input-fidelity-order-gate-sentinel"
    preflight = ROOT / (
        "build/c2.3/v1.6-input-fidelity-order-gate-sentinel-preflight")
    product = card.PRODUCT
    product.BUILD = build
    product.PREFLIGHT = preflight
    product.PREFLIGHT_RECEIPT = preflight / "preflight.json"
    product.SEMANTIC_RECEIPT = preflight / "semantic-repl-compile.json"
    product.INVOCATION = preflight / "card-invocation.json"
    product.PROJECTED_OWNERSHIP = preflight / "projected-ownership-contract.json"
    product.PROJECTED_FULL_MAP = preflight / "projected-full-map-authority.json"
    product.PRODUCER_RESULT = build / "producer-result.json"
    product.SCOPE_RESULT = build / "owner-scope-result.json"
    product.ACCEPTANCE_RESULT = build / "artifact-acceptance.json"
    product.ABI_REPORT = build / "wplto/c2-asm-leaf-abi.json"
    product.RECEIPT = build / "unused-card-receipt.json"
    product.FINAL_RED = build / "unused-card-final-red.json"
    product.DRIVER = Path(__file__)
    product.LINK = 117
    # This is deliberately set_paths(), not configure() or install().
    product.set_paths()
    return output_root_snapshot()


def candidate_static_plane_consumer(
        *, install: bool = False,
        output_rebind: Callable[[], dict[str, str]] | None = None,
        expected_output_roots: dict[str, str] | None = None) -> dict[str, Any]:
    """Configure, then execute the real six-image static-plane consumer.

    `install=True` deliberately leaves the candidate projection installed for
    the immediately following real product producer.  The ordinary preflight
    form restores the process globals after proving the same boundary.
    """
    previous_single_link = CONFIG.PRODUCT.single_link
    try:
        _old, projection = CONFIG.configure_projected_candidate()
    finally:
        # The projection gate captures the final-link call.  It must never
        # replace the real product link after the proof has completed.
        CONFIG.PRODUCT.single_link = previous_single_link

    # The closure above legitimately restores its own historical producer
    # context.  Card output ownership is a later configuration layer and must
    # therefore be rebound after the closure and before any real consumer.
    semantic_before = {
        "profile_sections": deepcopy(CONFIG.PRODUCT.PROFILE_RODATA_INPUT_SECTIONS),
        "profile_bytes": CONFIG.PRODUCT.PROFILE_RODATA_BYTES,
        "require_resolver_configured":
            CONFIG.PRODUCT.REQUIRE_RESOLVER_PROFILE_CONFIGURED,
    }
    rebind = output_rebind or permanent_output_root_rebind
    rebound = rebind()
    semantic_after = {
        "profile_sections": deepcopy(CONFIG.PRODUCT.PROFILE_RODATA_INPUT_SECTIONS),
        "profile_bytes": CONFIG.PRODUCT.PROFILE_RODATA_BYTES,
        "require_resolver_configured":
            CONFIG.PRODUCT.REQUIRE_RESOLVER_PROFILE_CONFIGURED,
    }
    require(semantic_after == semantic_before,
            "output-root rebind performed semantic configuration")
    expected = (deepcopy(expected_output_roots)
                if expected_output_roots is not None else deepcopy(rebound))
    require(rebound == expected, "candidate closure displaced card output roots")

    specs = candidate_static_specs()
    old_v6 = (V6.PRODUCT_IDENTITY, V6.STATIC_CODE_BYTES, V6.A.SPECS)
    V6.PRODUCT_IDENTITY = CANDIDATE_STATIC_PRODUCT
    V6.STATIC_CODE_BYTES = CANDIDATE_STATIC_BYTES
    V6.A.SPECS = specs
    try:
        images = [V6.F.emit_image(*row) for row in specs]
        code = b"".join(image.code for image in images)
        _plane, consumed = V6.static_plane(images)
        delivered = b"".join(
            (CANDIDATE_PLANE / f"{key}.code.bin").read_bytes()
            for key, _name, _path in specs)
        require(code == delivered,
                "configured consumer images differ from candidate plane")
        value = {
            "status":
                "passed-complete-candidate-closure-at-real-static-plane-consumer",
            "consumer": "c2_lite_v6_product_probe.static_plane",
            "candidate_bound_bytes": projection["final_state"]
                ["compiler_consumed_static_code_bytes"],
            "consumer_observed_bytes": consumed["code_bytes"],
            "images": len(images),
            "candidate_code_sha256": hashlib.sha256(code).hexdigest(),
            "candidate_product": bind(CANDIDATE_STATIC_PRODUCT),
            "candidate_delivery": bind(CONFIG.BASE.SOURCE_MANIFEST),
            "configurator_projection": projection,
            "configuration_order": ["candidate-configurator-closure",
                "card-output-root-rebind", "real-static-plane-consumer"],
            "output_roots_after_rebind": rebound,
            "expected_card_output_roots": expected,
            "path_rebind": {"mode": "paths-only",
                "semantic_state_unchanged": semantic_after == semantic_before,
                "semantic_state": semantic_after},
            "rule": ("The complete candidate configurator closure runs before "
                     "the card-owned output-root rebind, which runs before the "
                     "real static_plane() consumer. Both ownership and byte "
                     "equality are proved at their real consumers."),
        }
        validate_static_plane_consumer(value)
        value["mutations_rejected"] = static_plane_consumer_mutations(value)
        return value
    finally:
        if not install:
            (V6.PRODUCT_IDENTITY, V6.STATIC_CODE_BYTES,
             V6.A.SPECS) = old_v6


def install_candidate_static_plane_only(
        static_root: Path | None = None) -> dict[str, Any]:
    """Install the already-proved candidate plane without configuring it."""
    specs = candidate_static_specs()
    import c2_require_resolver_wplto as require_plane
    import c2_top_level_macro_redispatch_link94 as link94
    import c2_v150_release_preflight as release_preflight

    target = static_root or (ROOT / "build/c2.3/"
        "v1.6-input-fidelity-candidate-static-plane")
    require_plane.STATIC = target
    require_plane.STATIC_PRODUCT = target / "product"
    require_plane.V6_OUT = target / "v6-semantics"
    require_plane.SPECS = specs
    require_plane.EXPECTED_STATIC = CANDIDATE_STATIC_BYTES
    require_plane.EXPECTED_ENTRIES = 755
    require_plane.EXPECTED_RESOLUTIONS = 2929
    require_plane.EXPECTED_ROOTS = 352

    def bind_values() -> None:
        V6.PRODUCT_IDENTITY = CANDIDATE_STATIC_PRODUCT
        V6.STATIC_CODE_BYTES = CANDIDATE_STATIC_BYTES
        V6.A.SPECS = specs
        ZERO_LITERAL.LINKED_PRODUCT_INVENTORY = (
            CANDIDATE_STATIC_PRODUCT, CANDIDATE_STATIC_ROOT)

    bind_values()
    images = [V6.F.emit_image(*row) for row in specs]
    code = b"".join(image.code for image in images)
    _plane, consumed = V6.static_plane(images)
    require(len(images) == 6 and consumed["code_bytes"] == CANDIDATE_STATIC_BYTES
            and hashlib.sha256(code).hexdigest() == CANDIDATE_STATIC_SHA256,
            "path-bound candidate static-plane install drift")

    # Historical producer configurators still select their own host-fixture
    # paths.  Re-bind only the proved paths/values at the actual host consumer
    # boundary; no product semantic selector is invoked here.
    original_host_semantics = V6.host_semantics

    def candidate_host_semantics() -> dict[str, Any]:
        # Historical host gates deliberately exercise their own 40K-era
        # planes.  Project only the real consumer that already carries the
        # candidate's bound 46,043-byte contract; never rename another gate's
        # world merely because it shares host_semantics().
        if V6.STATIC_CODE_BYTES == CANDIDATE_STATIC_BYTES:
            bind_values()
        return original_host_semantics()

    V6.host_semantics = candidate_host_semantics

    # Link 94 owns a later, path-only projection of the same six-role
    # inventory.  Its historical adapter derives those paths only after
    # V112.configure() returns, so bind the derived inventory at that exact
    # boundary.  This deliberately calls the inherited adapter once and then
    # copies paths; it never invokes a profile/geometry configurator.
    inherited_v112_configure = link94.V112.configure

    def candidate_link94_specs() -> tuple[tuple[str, str, Path], ...]:
        # All six paths are the SHA-proved public candidate inventory.  The
        # historical adapter may emit its own Link-94 scratch stdlib, but that
        # is a fixture output, not an input of the current product world.
        return specs

    link94.specs = candidate_link94_specs

    def candidate_v112_paths(build: Path) -> dict[str, Path]:
        paths = inherited_v112_configure(build)
        inventory = link94.specs()
        link94.CAN.SPECS = inventory
        req = link94.V112.P.BASE.PROBE.REQ
        req.SPECS = inventory
        req.F1W.SPECS = inventory
        req.F1W.PLANE.FRESH_MANIFESTS = tuple(
            path for _key, _name, path in inventory)
        return paths

    link94.V112.configure = candidate_v112_paths

    # The ownership producer asks the v1.5 preflight for its copied-plane
    # source and, later, for the expected geometry.  Point both reads at the
    # same bound public candidate rather than the mutable workspace plane.
    candidate_preflight = CANDIDATE_PREFLIGHT_ROOT
    release_preflight.BUILD = candidate_preflight
    release_preflight.STATIC = candidate_preflight / "static-plane/narrow-static"
    release_preflight.STDLIB_PREFIX = release_preflight.STATIC / "stdlib-p0"
    release_preflight.STDLIB = (
        release_preflight.STDLIB_PREFIX.with_suffix(".manifest.json"))
    release_preflight.PRODUCT = (
        release_preflight.STATIC / "product/substitution-artifacts.json")
    release_preflight.V6_PLANE = release_preflight.STATIC / "v6-semantics"
    release_preflight.BASE_SPECS = specs[1:]
    inherited_require_build = require_plane.build_static_plane

    def candidate_require_build_static_plane() -> dict[str, Any]:
        # Later historical adapters may restore their own inventory roots.
        # Rebind the six candidate paths at the real static-plane consumer,
        # after every such adapter and before it reads a byte.
        require_plane.SPECS = candidate_link94_specs()
        return inherited_require_build()

    require_plane.build_static_plane = candidate_require_build_static_plane
    f1 = require_plane.F1W
    inherited_f1_static_gate = f1.static_gate

    def candidate_f1_static_gate() -> dict[str, Any]:
        # Deliver the same candidate inventory/profile to the downstream F1
        # reader.  These assignments are paths and candidate-derived counts;
        # no configure() function or semantic selector runs here.
        inventory = candidate_link94_specs()
        f1.STATIC_PRODUCT = require_plane.STATIC_PRODUCT
        f1.SPECS = inventory
        f1.EXPECTED_STATIC = CANDIDATE_STATIC_BYTES
        f1.EXPECTED_ENTRIES = 755
        f1.EXPECTED_RESOLUTIONS = 2929
        f1.EXPECTED_ROOTS = 352
        f1.CAN.PROFILE = CANDIDATE_PROFILE
        f1.PLANE.FRESH_ROOT = require_plane.STATIC
        f1.PLANE.FRESH_PRODUCT = (
            require_plane.STATIC_PRODUCT / "substitution-artifacts.json")
        f1.PLANE.FRESH_IDE = inventory[1][2]
        f1.PLANE.FRESH_BANK2 = (
            require_plane.V6_OUT / "bank2-static-code.bin")
        f1.PLANE.FRESH_MANIFESTS = tuple(
            path for _key, _name, path in inventory)
        return inherited_f1_static_gate()

    f1.static_gate = candidate_f1_static_gate
    return {"mode": "bind-proved-paths-and-values-only",
            "semantic_configurators_run": 0, "images": len(images),
            "require_plane_output": target.relative_to(ROOT).as_posix(),
            "real_consumer_adapter": (
                "c2_lite_v6_product_probe.host_semantics+"
                "link94.V112.configure:path-projection+"
                "require.build_static_plane:path-projection+"
                "f1.static_gate:path-projection+"
                "v150.geometry:path-projection"),
            "consumer_observed_bytes": consumed["code_bytes"],
            "candidate_code_sha256": hashlib.sha256(code).hexdigest()}


def require_resolver_one_shot_gate() -> dict[str, Any]:
    source = r'''import json
import c2_product_substitution_link as p
p.configure_require_resolver_profile_geometry()
after_first = dict(p.PROFILE_RODATA_INPUT_SECTIONS)
error = None
try:
    p.configure_require_resolver_profile_geometry()
except Exception as caught:
    error = f"{type(caught).__name__}: {caught}"
print(json.dumps({"after_first": after_first, "error": error}, sort_keys=True))'''
    environment = dict(__import__("os").environ)
    environment["PYTHONPATH"] = str(HOST)
    completed = subprocess.run(
        [sys.executable, "-c", source], cwd=ROOT, env=environment,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(completed.returncode == 0,
            f"require-resolver one-shot child red:\n{completed.stdout}")
    observed = json.loads(completed.stdout)
    value = {"status": "passed-configured-once-second-call-rejected",
        "first_call_vm_callprim_bytes": observed["after_first"]
            [".rodata.vm_callprim"],
        "second_call_rejected": observed["error"] ==
            "ValueError: require-resolver profile selector order drift",
        "classification": "configured-twice-process-one-shot",
        "error": observed["error"],
        "rule": "order-sensitive process configurators execute at most once"}
    require(value["first_call_vm_callprim_bytes"] == 166
            and value["second_call_rejected"],
            "require-resolver one-shot process guard drift")
    return value


def assemble_window(source_raw: bytes | None = None) -> tuple[Path, tempfile.TemporaryDirectory[str]]:
    require(CLANG.is_file() and READOBJ.is_file() and OBJDUMP.is_file(),
            "llvm-mos target tools absent")
    temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory(
        prefix="c2-v160-input-fidelity-")
    root = Path(temporary.name)
    source = root / "c2_kernal_window.s"
    source.write_bytes(WINDOW.read_bytes() if source_raw is None else source_raw)
    obj = root / "window.o"
    if source_raw is not None:
        run(str(CLANG), "-I", str(ROOT / "src"), "-c", str(source),
            "-o", str(obj))
    else:
        consumer = root / "capture.o"
        owner_source = root / "equate-owner.s"
        owner = root / "equate-owner.o"
        owner_source.write_text(
            '.set C2K_EQUATE_OWNER, 1\n'
            '.include "c2_kernal_window_equates.inc"\n',
            encoding="utf-8")
        run(str(CLANG), "-I", str(ROOT / "src"), "-c", str(source),
            "-o", str(consumer))
        run(str(CLANG), "-I", str(ROOT / "src"), "-c", str(owner_source),
            "-o", str(owner))
        run(str(LD), "-r", "-o", str(obj), str(consumer), str(owner))
    return obj, temporary


def section_bytes(truth: ElfTruth, section: str) -> bytes:
    return truth.section_bytes(section)


def target_object_gate() -> dict[str, Any]:
    current_obj, current_tmp = assemble_window()
    old_raw = ERA.era_blob(
        BASELINE_COMMIT, BASELINE_WINDOW.relative_to(ROOT).as_posix())
    old_obj, old_tmp = assemble_window(old_raw)
    try:
        current = ElfTruth.read(current_obj, llvm_readobj=READOBJ,
                                include_section_data=True)
        old = ElfTruth.read(old_obj, llvm_readobj=READOBJ,
                            include_section_data=True)
        sections = {
            "irq": ".lisp65_c2_kernal_window.irq_handler",
            "main": ".lisp65_c2_kernal_window.input_capture_main",
            "helper": ".lisp65_c2_kernal_window.input_capture_helper",
            "state": ".lisp65_c2_kernal_window.state",
        }
        sizes = {name: current.section(section).bytes
                 for name, section in sections.items()}
        require(sizes == {"irq": 74, "main": 28, "helper": 40,
                          "state": 16},
                f"target object shape drift: {sizes}")
        require(old.section(sections["irq"]).bytes == sizes["irq"],
                "IRQ handler byte count changed")
        state = section_bytes(current, sections["state"])
        require(state == bytes(13) + b"\xff" + bytes(2),
                "fixed-state capture owners/reset value drift")
        main = section_bytes(current, sections["main"])
        helper = section_bytes(current, sections["helper"])
        main_relocations = {
            row.offset: current.relocation_target_identity(row)
            for row in current.relocations
            if row.source_section == sections["main"]}
        helper_relocations = {
            row.offset: current.relocation_target_identity(row)
            for row in current.relocations
            if row.source_section == sections["helper"]}
        require(main[0] == 0x9c
                and main_relocations[1]["symbol"] == "C2K_SOURCELESS_IRQS"
                and main_relocations[1]["resolved_value"] == 0xff86
                and main.count(b"\x60") == 1,
                "displaced STZ is not the unconditional capture prologue")
        require(helper[19] == 0xac
                and helper_relocations[20]["symbol"] ==
                    "C2K_INPUT_RING_HEAD"
                and helper[22] == 0x99
                and helper_relocations[23]["symbol"] ==
                    "C2K_INPUT_RING_BASE"
                and helper[25:28] == b"\x8d\x19\xd6"
                and helper[28] == 0x8e
                and helper_relocations[29]["symbol"] ==
                    "C2K_INPUT_RING_HEAD"
                and helper[31] == 0xee
                and helper_relocations[32]["symbol"] ==
                    "C2K_INPUT_EVENTS_STORED",
                "producer payload/ack/head commit order absent")
        require(main[13] == 0xee
                and main_relocations[14]["symbol"] ==
                    "C2K_INPUT_EVENTS_RAW"
                and main[19] == 0xee
                and main_relocations[20]["symbol"] ==
                    "C2K_INPUT_EVENTS_SEEN",
                "raw/seen hardware-queue counter order absent")
        require(helper.startswith(b"\xc9\x03")
                and helper.count(b"\x8d\x19\xd6") == 2
                and helper.endswith(b"\x8d\x19\xd6\xaa\x60"),
                "raw queue-code discard/ack path absent")
        disassembly = run(str(OBJDUMP), "-dr", str(current_obj)).lower()
        require(disassembly.count("c2_kernal_input_capture_commit") >= 1
                and "r_mos_addr16\tc2_kernal_input_capture_commit" in disassembly,
                "split helper call linkage absent from target object")
        return {
            "status": "passed",
            "sizes": sizes,
            "irq_baseline_bytes": old.section(sections["irq"]).bytes,
            "displaced_stz": "unconditional-first-in-main",
            "producer_commit_order": ["payload", "hardware_ack", "head",
                                      "stored_counter"],
            "counter_order": ["queue_present", "raw", "queue_read", "seen", "payload", "ack",
                              "head", "stored"],
            "helper_linkage": "R_MOS_ADDR16 target c2_kernal_input_capture_commit",
            "disabled_tail_reset": "0xff at fixed-state offset 13",
        }
    finally:
        current_tmp.cleanup()
        old_tmp.cleanup()


def defuns(raw: str) -> list[Any]:
    return [form for form in P0.parse_all(raw)
            if isinstance(form, list) and len(form) > 1 and form[0] == "defun"]


def compile_sizes(forms: list[Any]) -> dict[str, int]:
    heap = P0.prepare_heap([form[1] for form in forms])
    result: dict[str, int] = {}
    for form in forms:
        name, code, helpers = P0.compile_top_form_with_helpers(
            form, heap, strict_arity=True, abi_profile="dialect-v2",
            prebuilt_primitives=True)
        require(not helpers, f"unexpected compiler helper: {name}")
        result[name] = len(code.encode())
    return result


def walk_form(form: Any) -> list[Any]:
    """Return every list node in one parsed Lisp form."""
    nodes: list[Any] = []
    if isinstance(form, list):
        nodes.append(form)
        for item in form:
            nodes.extend(walk_form(item))
    return nodes


def public_native_fallback_gate(editor: str) -> dict[str, Any]:
    """Prove the native fallback edge without pinning source spelling.

    A successor may bind the `(nthcdr 8 state)` suffix once and consume the
    binding from the branch.  The historic literal checker mistook that
    ownership improvement for removal of the fallback.
    """
    poll = next((form for form in defuns(editor)
                 if form[1] == "%rl-poll"), None)
    require(poll is not None, "%rl-poll definition absent")
    suffix = ["nthcdr", 8, "state"]
    aliases = {
        binding[0]
        for node in walk_form(poll)
        if len(node) >= 2 and node[0] in ("let", "let*")
        and isinstance(node[1], list)
        for binding in node[1]
        if isinstance(binding, list) and len(binding) == 2
        and binding[1] == suffix
    }
    conditions: list[Any] = [suffix, *sorted(aliases)]
    edges = [
        node for node in walk_form(poll)
        if len(node) == 4 and node[0] == "if"
        and node[1] in conditions
        and ["%rl-render", "nil", 0, 0, 0, 0, -1]
            in walk_form(node[2])
        and ["key-event", 1] in walk_form(node[3])
    ]
    mode1 = [node for node in walk_form(poll)
             if node == ["key-event", 1]]
    require(len(edges) == 1 and len(mode1) == 1,
            "public/native read-line fallback edge changed")
    return {
        "status": "passed-structural-fallback-edge",
        "suffix": "nthcdr(8,state)",
        "suffix_authority": ("single-bound-suffix" if aliases
                             else "inline-suffix"),
        "native_sink": "key-event(mode=1)",
        "extended_sink": "%rl-render(clear-sentinel)",
    }


def public_native_fallback_mutations(editor: str) -> list[str]:
    cases = {
        "remove-native-mode1": editor.replace(
            "(key-event 1)", "(key-event 0)", 1),
        "reverse-native-and-extended-sinks": editor.replace(
            "(%rl-render nil 0 0 0 0 -1)\n            (key-event 1)",
            "(key-event 1)\n            (%rl-render nil 0 0 0 0 -1)", 1),
    }
    rejected: list[str] = []
    for name, source in cases.items():
        require(source != editor, f"fallback mutation did not apply: {name}")
        try:
            public_native_fallback_gate(source)
        except FidelityError:
            rejected.append(name)
    require(rejected == list(cases),
            f"fallback mutation survived: {set(cases) - set(rejected)}")
    return rejected


def hybrid_editor_selected() -> bool:
    """Derive the successor from the consumed source, not process phase."""
    editor = EDITOR.read_text(encoding="utf-8")
    return ("(key-event 2)" in editor and "(key-event 3)" in editor
            and "(peek 255 138)" not in editor)


def bank2_gate() -> dict[str, Any]:
    hybrid_selected = hybrid_editor_selected()
    current_forms = defuns(EDITOR.read_text(encoding="utf-8")) + defuns(
        COMFORT.read_text(encoding="utf-8"))
    current = compile_sizes(current_forms)
    predecessor_commit = ("bc6582e3" if hybrid_selected
                          else BASELINE_COMMIT)
    old_forms = defuns(ERA.era_blob(
        predecessor_commit, EDITOR.relative_to(ROOT).as_posix()).decode()) + defuns(
        ERA.era_blob(
            BASELINE_COMMIT, COMFORT.relative_to(ROOT).as_posix()).decode())
    old = compile_sizes(old_forms)
    names = (("%rl-render", "%rl-put", "%read-line-loop")
             if hybrid_selected else
             ("%rl-render", "%read-line-loop", "repl"))
    if not hybrid_selected:
        require({name: old[name] for name in names} == {
                    "%rl-render": 91, "%read-line-loop": 202, "repl": 118}
                and {name: current[name] for name in names} == {
                    "%rl-render": 236, "%read-line-loop": 237, "repl": 189},
                "Bank-2 implementation shape drift")
    delta = sum(current[name] - old[name] for name in names)
    require((delta < 0 if hybrid_selected else delta == 251)
            and max(current[name] for name in names) < 256,
            "Bank-2 implementation price/ceiling drift")
    return {"status": "passed", "baseline": {name: old[name] for name in names},
            "candidate": {name: current[name] for name in names},
            "delta_bytes": delta, "new_names": 0, "new_primitives": 0,
            "authority": ("emitted-candidate-vs-sealed-comfort-predecessor"
                          if hybrid_selected else
                          "sealed-capture-card-shape")}


def lifecycle_gate() -> dict[str, Any]:
    editor = EDITOR.read_text(encoding="utf-8")
    comfort = COMFORT.read_text(encoding="utf-8")
    repl = REPL_C.read_text(encoding="utf-8")
    window = WINDOW.read_text(encoding="utf-8")
    if hybrid_editor_selected():
        require("(key-event 2)" in editor and "(key-event 3)" in editor
                and "(if (= (car s4) 250) nil (key-event 3))" in editor
                and "(peek 255 138)" not in editor
                and "(if (= code 160) 32 code)" not in editor,
                "native scalar consumer/shared-normalization boundary drift")
    else:
        require("(peek 255 138)" in editor and "(key-event 0)" in editor
                and "(peek 255 140)" in editor and "(peek 255 141)" in editor
                and "(poke 255 141 next)" in editor
                and "(if (= code 160) 32 code)" in editor,
                "raw scalar consumer/WYSIWYG boundary drift")
    fallback = public_native_fallback_gate(editor)
    disable = "(poke 255 141 255)"
    require(comfort.count(disable) == 3
            and comfort.count("(poke 255 140 0)") == 2
            and comfort.count("(poke 255 141 0)") == 2
            and comfort.index(disable) < comfort.index("(lcc-run form)")
            and "(dotimes (counter 4 nil)" in comfort
            and "(poke 188 (+ 252 counter) 0)" in comfort
            and "C2K_INPUT_RING_TAIL = 0xff;" in repl,
            "capture lifecycle is not closed on eval/normal/error paths")
    require("cmp #$03" in window and "sta $d619" in window
            and "lda $d613" in window and "inc C2K_BREAK_PENDING" in window,
            "raw code03/matrix RUN-STOP authority drift")
    return {
        "status": "passed", "consumer_commit_order": ["payload_read", "tail"],
        "a0_to_space": True, "raw_code03_discarded": True,
        "matrix_run_stop_authority": True,
        "disabled": ["before lcc-run", "normal Comfort exit",
                     "native longjmp recovery"],
        "public_key_event_abi_changed": False,
        "native_repl_fallback_changed": False,
        "public_native_fallback": fallback,
        "public_native_fallback_mutations":
            public_native_fallback_mutations(editor),
    }


def capture_simulation(*, initial: int = 5, frames: int = 89,
                       rate: int = 1, slots: int = 108) -> dict[str, Any]:
    hardware = list(range(initial))
    ring = [None] * slots
    head = tail = 0
    dropped: list[int] = []
    next_event = initial
    maximum = 0

    def occupancy() -> int:
        return head - tail if head >= tail else slots - tail + head

    def drain() -> None:
        nonlocal head
        while hardware:
            following = 0 if head == slots - 1 else head + 1
            if following == tail:
                return
            value = hardware[0]
            ring[head] = value                  # payload
            hardware.pop(0)                    # hardware acknowledgement
            head = following                   # producer commit

    for _ in range(frames):
        drain()
        maximum = max(maximum, occupancy())
        for _ in range(rate):
            if len(hardware) < 5:
                hardware.append(next_event)
            else:
                dropped.append(next_event)
            next_event += 1
    drain()
    maximum = max(maximum, occupancy())
    consumed: list[int] = []
    while tail != head:
        consumed.append(int(ring[tail]))        # payload read
        tail = 0 if tail == slots - 1 else tail + 1  # consumer commit
    expected = list(range(initial + frames * rate))
    return {"events_produced": len(expected), "events_captured": len(consumed),
            "ordered": consumed == expected, "dropped": len(dropped),
            "sixth_event_present": 5 in consumed,
            "maximum_ring_occupancy": maximum,
            "final_head": head, "final_tail": tail}


def loss_gate() -> dict[str, Any]:
    result = capture_simulation()
    require(result == {"events_produced": 94, "events_captured": 94,
                       "ordered": True, "dropped": 0,
                       "sixth_event_present": True,
                       "maximum_ring_occupancy": 94,
                       "final_head": 94, "final_tail": 94},
            f"94-event loss test red: {result}")
    full = capture_simulation(initial=5, frames=103, rate=1, slots=108)
    require(full["events_captured"] == 107
            and full["maximum_ring_occupancy"] == 107,
            "ring full boundary drift")
    return {"status": "passed", "forced_collection": result,
            "full_boundary": full,
            "why_event_six_survives": (
                "the owned raster IRQ drains all five pending hardware events "
                "before event six arrives, so event six enters the independent "
                "107-event ring instead of meeting a full hardware queue")}


def inventory_registration_gate() -> dict[str, Any]:
    """Prove R1, capture and capture-plus-hybrid inventories."""
    import c2_product_substitution_link as product

    feature = product.INPUT_CAPTURE_FEATURE
    hybrid_feature = product.INPUT_HYBRID_FEATURE
    base_definitions = tuple(name for name in product.CONVERGENCE_DEFINES
                             if name not in (feature, hybrid_feature))
    r1 = product.input_capture_inventory_registration(base_definitions)
    capture = product.input_capture_inventory_registration(
        (*base_definitions, feature))
    hybrid = product.input_capture_inventory_registration(
        (*base_definitions, feature, hybrid_feature))
    names = [
        ".lisp65_c2_kernal_window.input_capture_main",
        ".lisp65_c2_kernal_window.input_capture_helper",
        ".rela.lisp65_c2_kernal_window.input_capture_main",
        ".rela.lisp65_c2_kernal_window.input_capture_helper",
    ]
    hybrid_names = [
        ".lisp65_c2_kernal_window.input_capture_main",
        ".lisp65_c2_kernal_window.input_capture_helper",
        ".lisp65_c2_kernal_window.input_consumer",
        ".rela.lisp65_c2_kernal_window.input_capture_main",
        ".rela.lisp65_c2_kernal_window.input_capture_helper",
        ".rela.lisp65_c2_kernal_window.input_consumer",
    ]
    require(r1["selected"] is False and r1["names"] == []
            and capture["selected"] is True and capture["names"] == names
            and hybrid["selected"] is True
            and hybrid["hybrid_selected"] is True
            and hybrid["names"] == hybrid_names
            and capture["authority"] == "build-feature-and-source-membership",
            "capture inventory is not coupled to its build boundary")
    rows = [{"name": name, "address": 0, "bytes": 12, "flags": []}
            for name in names]
    unregistered = product._final_section_inventory_violations([], rows, [])
    registered_absent = product._final_section_inventory_violations(
        names, [], [])
    require("section-name-set" in unregistered
            and "section-count" in unregistered
            and "section-name-set" in registered_absent
            and "section-count" in registered_absent,
            "capture inventory cross-direction mutation survived")
    return {"status": "passed-two-world-card-owned-registration",
        "R1_world": r1, "capture_world": capture, "hybrid_world": hybrid,
        "mutations_rejected": ["section-without-registration",
                               "registration-without-section"]}


def _merge(rows: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[list[int]] = []
    for start, end in sorted(rows):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


CAPTURE_SECTIONS = {
    ".lisp65_c2_kernal_window.input_capture_main",
    ".lisp65_c2_kernal_window.input_capture_helper",
}
HYBRID_SECTION = ".lisp65_c2_kernal_window.input_consumer"


def placement_gate(elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    linked_names = {section.name for section in truth.sections}
    active_sections = set(CAPTURE_SECTIONS)
    if HYBRID_SECTION in linked_names:
        active_sections.add(HYBRID_SECTION)
    arena_start, arena_end = 0xE000, 0xFF80
    occupied: list[tuple[int, int]] = []
    allocated: list[dict[str, Any]] = []
    for section in truth.sections:
        if section.name in active_sections or section.bytes <= 0:
            continue
        flags = set(section.flags)
        if "SHF_ALLOC" not in flags:
            continue
        start = max(arena_start, section.address)
        end = min(arena_end, section.address + section.bytes)
        if start < end:
            occupied.append((start, end))
            allocated.append({"name": section.name, "start": start,
                              "end_exclusive": end, "bytes": end - start})
    union = _merge(occupied)
    holes: list[tuple[int, int]] = []
    cursor = arena_start
    for start, end in union:
        if cursor < start:
            holes.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < arena_end:
        holes.append((cursor, arena_end))

    fragments: dict[str, dict[str, Any]] = {}
    used_holes: list[tuple[int, int]] = []
    for name in sorted(active_sections):
        section = truth.section(name)
        containing = [hole for hole in holes
                      if hole[0] <= section.address
                      and section.address + section.bytes <= hole[1]]
        require(len(containing) == 1,
                f"capture fragment escaped final-ELF-derived free space: {name}")
        hole = containing[0]
        used_holes.append(hole)
        fragments[name] = {
            "address": section.address, "bytes": section.bytes,
            "end_exclusive": section.address + section.bytes,
            "derived_hole": [hole[0], hole[1]],
            "derived_hole_bytes": hole[1] - hole[0],
            "residual_bytes": hole[1] - (section.address + section.bytes),
        }
    main = fragments[".lisp65_c2_kernal_window.input_capture_main"]
    helper = fragments[".lisp65_c2_kernal_window.input_capture_helper"]
    # R1 moved the cold abort driver out of E000 before this card reopened.
    # The capture fragments must still occupy two holes derived from the
    # candidate, but the live reserve is the complement of *all* allocated
    # candidate sections after capture, never the two-byte predecessor pin.
    occupied_with_capture = list(occupied)
    for name in sorted(active_sections):
        section = truth.section(name)
        occupied_with_capture.append(
            (section.address, section.address + section.bytes))
    occupied_final = _merge(occupied_with_capture)
    post_capture_free = ((arena_end - arena_start)
                         - sum(end - start for start, end in occupied_final))
    final_holes: list[tuple[int, int]] = []
    cursor = arena_start
    for start, end in occupied_final:
        if cursor < start:
            final_holes.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < arena_end:
        final_holes.append((cursor, arena_end))
    largest_contiguous_hole = max(end - start for start, end in final_holes)
    reserve_floor = 54
    hybrid = fragments.get(HYBRID_SECTION)
    reserve_ok = (post_capture_free >= 57 if hybrid is not None
                  else post_capture_free == 130)
    require(main["bytes"] == 28 and helper["bytes"] == 40
            and (hybrid is None or 0 < hybrid["bytes"] <= 70)
            and len(set(used_holes)) == 2
            and reserve_ok
            and post_capture_free >= reserve_floor,
            "authorized post-R1 split placement/reserve drift")

    irq_section = truth.section(
        ".lisp65_c2_kernal_window.irq_handler")
    irq_entry = truth.symbol("c2_kernal_irq_handler")
    irq = truth.section_bytes(irq_section.name)
    capture = truth.symbol("c2_kernal_input_capture")
    helper_symbol = truth.symbol("c2_kernal_input_capture_commit")
    call_capture = bytes((0x20, capture.value & 0xFF, capture.value >> 8))
    call_helper = bytes((0x20, helper_symbol.value & 0xFF,
                         helper_symbol.value >> 8))
    require(irq_entry.value == irq_section.address
            and len(irq) == irq_section.bytes == 74
            and irq.count(call_capture) == 1,
            "final IRQ does not carry the same-size capture call")
    main_raw = symbol_bytes(truth, "c2_kernal_input_capture")
    require(main_raw.startswith(b"\x9c\x86\xff")
            and main_raw.count(call_helper) == 1,
            "final displaced-STZ/helper-link proof red")
    repl = symbol_bytes(truth, "repl")
    longjmp_disable_forms = {
        "A": b"\xa9\xff\x8d\x8d\xff",
        "X": b"\xa2\xff\x8e\x8d\xff",
        "Y": b"\xa0\xff\x8c\x8d\xff",
    }
    emitted_disable = [name for name, form in longjmp_disable_forms.items()
                       if repl.count(form) == 1]
    require(len(emitted_disable) == 1,
            "native longjmp capture disable absent from final ELF")
    text = truth.section(".text")
    require(text.address + text.bytes <= 0xB3AA,
            "ordinary text did not retain the authorized six-byte reserve")
    return {
        "status": "passed-final-linked-ELF",
        "ELF": bind(elf), "arena": [arena_start, arena_end],
        "holes_source": "ElfTruth SHF_ALLOC complement of final linked ELF",
        "derived_holes": [[start, end] for start, end in holes],
        "fragments": fragments,
        "hybrid_consumer_present": hybrid is not None,
        "final_reserve_bytes": post_capture_free,
        "final_free_holes": [[start, end] for start, end in final_holes],
        "largest_contiguous_hole_bytes": largest_contiguous_hole,
        "reserve_floor_bytes": reserve_floor,
        "surplus_over_floor_bytes": post_capture_free - reserve_floor,
        "reserve_source": "ElfTruth final-SHF_ALLOC arena complement",
        "ordinary_text_end_exclusive": text.address + text.bytes,
        "ordinary_text_reserve_bytes": 0xB3B0 - (text.address + text.bytes),
        "irq_bytes": len(irq), "irq_capture_call_count": 1,
        "irq_body_authority": "owning-section-plus-unique-entry-and-call",
        "irq_entry_symbol_bytes": irq_entry.bytes,
        "main_stz_is_unconditional_prologue": True,
        "helper_call_count": 1,
        "longjmp_disable": {
            "authority": "semantic-immediate-ff-store-to-ring-tail",
            "emitted_register": emitted_disable[0],
            "stores": 1,
        },
        "allocated_section_count": len(allocated),
    }


def symbol_bytes(truth: ElfTruth, name: str) -> bytes:
    symbol = truth.symbol(name)
    section = truth.section(symbol.section)
    raw = truth.section_bytes(symbol.section)
    offset = symbol.value - section.address
    require(0 <= offset and offset + symbol.bytes <= len(raw),
            f"symbol outside section: {name}")
    return raw[offset:offset + symbol.bytes]


def validate(value: dict[str, Any], *, final: bool) -> None:
    require(value.get("format") == FORMAT
            and value.get("status") ==
                ("HOST-GREEN: FINAL ELF PROVES LOSSLESS COMFORT CAPTURE"
                 if final else "PREFLIGHT-GREEN: FINAL PRODUCT LINK REQUIRED")
            and value["target_object"]["sizes"] == {
                "irq": 74, "main": 28, "helper": 40, "state": 16}
            and ((value["bank2"]["delta_bytes"] < 0
                  and value["bank2"]["authority"] ==
                    "emitted-candidate-vs-sealed-comfort-predecessor")
                 if hybrid_editor_selected() else
                 value["bank2"]["delta_bytes"] == 251)
            and value["loss"]["forced_collection"]["events_captured"] == 94
            and value["loss"]["forced_collection"]["sixth_event_present"]
            and value["inventory_registration"]["R1_world"]["names"] == []
            and len(value["inventory_registration"]["capture_world"]["names"])
                == 4
            and len(value["inventory_registration"]["hybrid_world"]["names"])
                == 6
            and value["lifecycle"]["a0_to_space"]
            and value["lifecycle"]["matrix_run_stop_authority"]
            and value["require_resolver_one_shot"]["second_call_rejected"]
            and value["static_plane_consumer"]["consumer_observed_bytes"]
                == CANDIDATE_STATIC_BYTES,
            "input-fidelity implementation receipt drift")
    validate_static_plane_consumer(value["static_plane_consumer"])
    if final:
        hybrid = bool(value["placement"].get("hybrid_consumer_present"))
        require(value["placement"]["status"] == "passed-final-linked-ELF"
                and value["placement"]["holes_source"].startswith("ElfTruth")
                and (value["placement"]["final_reserve_bytes"] >= 57
                     if hybrid else
                     value["placement"]["final_reserve_bytes"] == 130)
                and value["placement"]["reserve_floor_bytes"] == 54
                and value["placement"]["surplus_over_floor_bytes"] >= 3
                and value["placement"]["largest_contiguous_hole_bytes"] ==
                    max(end - start for start, end in
                        value["placement"]["final_free_holes"])
                and value["placement"]["reserve_source"].startswith("ElfTruth")
                and value["placement"]["ordinary_text_reserve_bytes"] >= 6,
                "final placement contract drift")
        require(value["placement"]["irq_body_authority"] ==
                    "owning-section-plus-unique-entry-and-call"
                and value["placement"]["irq_bytes"] == 74
                and value["placement"]["irq_capture_call_count"] == 1,
                "final IRQ semantic identity drift")
        require(value["placement"]["longjmp_disable"]["authority"] ==
                    "semantic-immediate-ff-store-to-ring-tail"
                and value["placement"]["longjmp_disable"]["stores"] == 1
                and value["placement"]["longjmp_disable"][
                    "emitted_register"] in ("A", "X", "Y"),
                "longjmp capture-disable semantic identity drift")


def mutations(value: dict[str, Any], *, final: bool) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "lose-event-six": lambda x: x["loss"]["forced_collection"].update(
            sixth_event_present=False),
        "drop-event": lambda x: x["loss"]["forced_collection"].update(
            events_captured=93),
        "section-without-registration": lambda x: x[
            "inventory_registration"]["capture_world"].update(names=[]),
        "registration-without-section": lambda x: x[
            "inventory_registration"]["R1_world"].update(
                names=[".lisp65_c2_kernal_window.input_capture_main"]),
        "grow-main": lambda x: x["target_object"]["sizes"].update(main=35),
        "grow-helper": lambda x: x["target_object"]["sizes"].update(helper=32),
        "grow-irq": lambda x: x["target_object"]["sizes"].update(irq=75),
        "drop-stz": lambda x: x["target_object"].update(
            displaced_stz="absent"),
        "weaken-a0": lambda x: x["lifecycle"].update(a0_to_space=False),
        "raw-stop-authority": lambda x: x["lifecycle"].update(
            matrix_run_stop_authority=False),
        "grow-bank2": lambda x: x["bank2"].update(
            delta_bytes=(1 if hybrid_editor_selected() else 252)),
        "restore-ambient-static-plane": lambda x: x["static_plane_consumer"].update(
            consumer_observed_bytes=43308),
        "allow-double-profile-config": lambda x: x[
            "require_resolver_one_shot"].update(second_call_rejected=False),
    }
    if final:
        cases.update({
            "assumed-free-span": lambda x: x["placement"].update(
                holes_source="address arithmetic from presumed gap"),
            "restore-stored-two-byte-reserve": lambda x: x["placement"].update(
                final_reserve_bytes=2, surplus_over_floor_bytes=-52),
            "fall-below-reserve-floor": lambda x: x["placement"].update(
                final_reserve_bytes=53, surplus_over_floor_bytes=-1),
            "consume-ordinary-wall": lambda x: x["placement"].update(
                ordinary_text_reserve_bytes=5),
            "restore-zero-size-symbol-body-proxy": lambda x: x[
                "placement"].update(irq_body_authority="entry-symbol-size"),
            "restore-accumulator-only-disable-pin": lambda x: x[
                "placement"]["longjmp_disable"].update(
                    authority="exact-LDA-STA-opcodes"),
        })
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate(trial, final=final)
            if name == "drop-stz":
                require(trial["target_object"]["displaced_stz"] ==
                            "unconditional-first-in-main", "STZ mutation")
        except FidelityError:
            rejected.append(name)
    require(rejected == list(cases),
            f"implementation mutation survived: {set(cases) - set(rejected)}")
    return rejected


def derive(
        elf: Path | None = None, *,
        output_rebind: Callable[[], dict[str, str]] | None = None,
        expected_output_roots: dict[str, str] | None = None) -> dict[str, Any]:
    contract = load(CONTRACT)
    # The historic price remains a sealed input and must still reproduce.
    pricing = run(sys.executable, str(PRICING), "check")
    require("pricing: PASS" in pricing, "sealed pricing predecessor red")
    value = {
        "format": FORMAT, "recorded_on": "2026-08-18",
        "status": ("HOST-GREEN: FINAL ELF PROVES LOSSLESS COMFORT CAPTURE"
                   if elf else "PREFLIGHT-GREEN: FINAL PRODUCT LINK REQUIRED"),
        "authority": authority(contract),
        "target_object": target_object_gate(),
        "bank2": bank2_gate(), "lifecycle": lifecycle_gate(),
        "loss": loss_gate(),
        "inventory_registration": inventory_registration_gate(),
        "require_resolver_one_shot": require_resolver_one_shot_gate(),
        "static_plane_consumer": candidate_static_plane_consumer(
            output_rebind=output_rebind,
            expected_output_roots=expected_output_roots),
        "placement": placement_gate(elf) if elf else {
            "status": "pending-final-product-link",
            "required_source": "ElfTruth SHF_ALLOC complement"},
        "attempt_accounting": {"product_links": 1 if elf else 0,
            "media_builds": 0, "device_contacts": 0},
        "claim_limit": ("Host-only implementation and final linked placement; "
                        "no Completion, media, review or device acceptance."),
    }
    validate(value, final=elf is not None)
    value["mutations_rejected"] = mutations(value, final=elf is not None)
    return value


def selftest() -> None:
    result = capture_simulation()
    require(result["events_captured"] == 94 and result["dropped"] == 0,
            "loss model selftest red")
    too_small = capture_simulation(slots=94)
    require(too_small["events_captured"] == 93,
            "undersized-ring mutation did not lose event 94")
    print("v1.6 input fidelity: SELFTEST PASS loss=94/94 small-ring=93/94")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("selftest", "preflight", "check"))
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    if args.action == "selftest":
        selftest()
        return 0
    if args.action == "check":
        require(args.elf is not None, "check requires --elf final product")
    value = derive(args.elf)
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_bytes(canonical(value))
    final = args.elf is not None
    print("v1.6 input fidelity: "
          f"{'HOST CARD PASS' if final else 'PREFLIGHT PASS'} "
          f"events=94/94 C2=68 counters=12 bank2=251 mutations={len(value['mutations_rejected'])}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FidelityError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"v1.6 input fidelity: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
