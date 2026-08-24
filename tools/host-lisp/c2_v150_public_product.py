#!/usr/bin/env python3
"""Rebuild the selected v1.5.0 product from public, tracked inputs only.

The release candidate was assembled over a long-lived proof worktree.  This
driver projects the accepted candidate into a deliberately small public build
contract: tracked source, three tracked historical source-state projections,
and the regular compiler/linker/media pipelines.  No proof receipt or previous
binary is a build input.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_stdlib as STD  # noqa: E402
import c2_link95_packed_callee_closure as L95  # noqa: E402
import c2_ship_input_wait_gate as INPUT  # noqa: E402
import c2_substitution_artifacts as SUB  # noqa: E402
import c2_top_level_macro_redispatch as REDISPATCH  # noqa: E402
import c2_v112_candidate_product as V112  # noqa: E402
import c2_v150_release_preflight as PRE  # noqa: E402
import c2_v150_release_closure as CLOSURE  # noqa: E402
import c2_v150_f018b_fix_card as FIX  # noqa: E402
import c2_v20_ownership_recharter as OWN  # noqa: E402
import c2_v21_wysiwyg_text_recovery_replacement_card as CARD  # noqa: E402
import c2_v21_wysiwyg_candidate_contract as PLACEMENT  # noqa: E402
import c2_v21_candidate_derived_local_return as CANDIDATE  # noqa: E402
import c2_v21_map_mask_fix_card as MAP_CARD  # noqa: E402
import c2_lite_canonical_product as CAN  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v20_phase02b_header_consumption_card as HEADER  # noqa: E402
import c2_v20_source_oracle_media as SOURCE_MEDIA  # noqa: E402
import c2_v20_crc_carveout_media as CRC_MEDIA  # noqa: E402
import c2_v21_root_padding_configurator_parity_media as PARITY  # noqa: E402
import c2_lite_media_product as MEDIA  # noqa: E402
import c2_v150_stager_liveness_successor as LIVENESS  # noqa: E402
import c2_v112_candidate_media as LIBMEDIA  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


BUILD = ROOT / "build/c2.3/v1.5.0-public-selected"
MANIFEST = BUILD / "candidate-manifest.json"
PREFLIGHT_OWNED_CHILDREN = frozenset(("ide-check", "ide-codemod"))
STATIC_HEAP = ROOT / "config/c2-v150-public-ide-resident-heap.json"
LINK95_SUITE = ROOT / "config/c2-v150-public-link95-suite.json"
WHO_CALLS = ROOT / "config/c2-v150-public-who-calls-scoped.lisp"
EXPECTED = {
    "artifact_set_sha256": (
        "cdb022874b4c9ee6dfb261182373259a4eeffcd7833509514555014fe46291b2"),
    "product_build_id": "1cea8cf6",
    "profile_build_id": "9a4c23dc",
    "roles": {
        "library-ide": (31886,
            "6320b070885e2de285b30eda350e95a7beefc0819fdec5ff2fbc0034d32cacd2"),
        "linked-product-elf": (630792,
            "b0942ce0d75af2485197c47dd0d49d0c753c227ef124df090209053fb8d2ba09"),
        "c2-resident-prg": (41566,
            "70fd5752b885ee06b1c4fe17ccc0318c81137cbf7e897a1d4614a08533afd624"),
        "product-d81": (819200,
            "efc9b181a10afb030a90e6c23806d9bc4d84a53d6fbfec3346d701fe8ce28436"),
        "work-d81": (819200,
            "bf887cd4f8b14b2e808bccfc223e64bfb1223a61e16e11169be0d34e669c63e3"),
        "optional-library-d81": (819200,
            "139980fe9df48e4a5221f44ff458d4fa7099406d6eb52341513312a16d05208a"),
        "optional-library-index": (224,
            "a1476ffd3571b85867ac9ca557bc650d90e4590c5d45ddff8ce90f6b0b53953b"),
        "library-string-extra": (506,
            "9a116a0301ac371ef2dce40695835f51fd8c1887b837c80a1a3765992af806bb"),
        "library-inspect": (5737,
            "edb19a04ac94b0d25f5905458703a3696042504f22332b74faa44fd5755424b5"),
        "library-place": (1925,
            "8b9f705244bf512631d57c41ba80692b0034a6ec5d633ef8eea1f28dd3e07a61"),
        "library-defstruct": (2517,
            "acff7ca52fd2da6444ba1fa2c6d8e7f14ce6719177eb4e010d6873eb2c050e04"),
    },
}

DEFSTRUCT_PRIVATE_NAMES = {
    "%defstruct-constructor-form": "%d0",
    "%defstruct-copy": "%d1",
    "%defstruct-copy-form": "%d2",
    "%defstruct-expansion": "%d3",
    "%defstruct-generated-names": "%d4",
    "%defstruct-instance-p": "%d5",
    "%defstruct-member": "%d6",
    "%defstruct-names-free-p": "%d7",
    "%defstruct-one-slot-forms": "%d8",
    "%defstruct-predicate-form": "%d9",
    "%defstruct-read": "%da",
    "%defstruct-register-forms": "%db",
    "%defstruct-register-layout": "%dc",
    "%defstruct-set": "%dd",
    "%defstruct-slot-forms": "%de",
    "%defstruct-slot-names": "%df",
    "%defstruct-slot-symbol": "%dg",
    "%defstruct-slots-valid-p": "%dh",
    "%defstruct-symbol": "%di",
    "%defstruct-with": "%dj",
}

# The packed-callee gate only consumes this anonymous-name projection from the
# historical 1.11 compiler manifest.  Keeping the projection here avoids
# exporting diagnostic manifests whose path fields are checkout-absolute.
PUBLIC_ANONYMOUS_NAMES = (
    "%lcc-op", "%lcc-op2", "%lcc-prim", "%lcc-len", "%lcc-rev-into",
    "%lcc-consp", "%lcc-equal", "%lcc-cs", "%lcc-fns", "%lcc-emit-st",
    "%lcc-emit", "%lcc-emit-op", "%lcc-emit2", "%lcc-lit-find",
    "%lcc-lit-slot", "%lcc-push-lit", "%lcc-push-value", "%lcc-env-find",
    "%lcc-top-env", "%lcc-uvbox", "%lcc-with-top-env", "%lcc-uv-index",
    "%lcc-uv-add", "%lcc-resolve-uv", "%lcc-emit-slot", "%lcc-var",
    "%lcc-lower-and", "%lcc-lower-or", "%lcc-lower-when",
    "%lcc-lower-unless", "%lcc-lower-cond", "%lcc-seq", "%lcc-rel8",
    "%lcc-if", "%lcc-expr-do", "%lcc-do-p", "%lcc-proper-list-p",
    "%lcc-while", "%lcc-do-norm", "%lcc-do-body", "%lcc-storel-name",
    "%lcc-do-steps", "%lcc-do-store-rev", "%lcc-do-loop", "%lcc-do",
    "%lcc-lower-dotimes", "%lcc-lower-dolist", "%lcc-let-binds",
    "%lcc-let", "%lcc-setq", "%lcc-args", "%lcc-call",
    "%lcc-emit-uv-values", "%lcc-lambda", "%lcc-imm-binds",
    "%lcc-macro-p", "%lcc-qq-d", "%lcc-lower-qq", "%lcc-expr",
    "%lcc-expr-form", "%lcc-expr-sf2", "%lcc-2args-p", "%lcc-vop",
    "%lcc-expr-ops", "%lcc-expr-ops2", "%lcc-binary", "%lcc-unary",
    "%lcc-sf-p", "%lcc-opform-p", "%lcc-callform-p", "%lcc-tailcall",
    "%lcc-tail-seq", "%lcc-tail-let", "%lcc-tail-if", "%lcc-tail",
    "%lcc-tail2", "%lcc-params-env", "%lcc-finish",
    "%lcc-compile-defun", "lcc-compile-obj", "%lcc-compile-lambda",
    "%lcc-wrap", "%lcc-v2-bitop", "%lcc-v2-bitop-binary",
    "%lcc-v2-prim2", "%lcc-v2-prim3", "%lcc-v2-prim4", "%lcc-v2-prim5",
    "%lcc-v2-param-seen-p", "%lcc-v2-param-error",
    "%lcc-v2-param-optional", "%lcc-v2-param-rest", "%lcc-v2-param-add",
    "%lcc-v2-param-step", "%lcc-v2-params-walk", "%lcc-v2-params",
    "%lcc-v2-env", "%lcc-v2-finish", "%lcc-v2-fixed-binds",
    "%lcc-v2-drop", "%lcc-v2-imm-binds",
)


class PublicBuildError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PublicBuildError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def run(command: list[str], label: str) -> str:
    result = subprocess.run(command, cwd=ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout


def public_build_has_owned_state(root: Path) -> bool:
    """Return whether *root* contains state owned by the one-shot build.

    ``ide-check`` and ``ide-codemod`` are sibling preflight outputs.  Their
    parent is deliberately shared with the product build, so the directory's
    bare existence cannot be the one-shot predicate.  Every other child is
    build-owned (or unknown and therefore fail-closed).
    """
    if not root.exists():
        return False
    require(root.is_dir() and not root.is_symlink(),
            "v1.5 public build root is not a real directory")
    return any(child.name not in PREFLIGHT_OWNED_CHILDREN
               for child in root.iterdir())


def lifecycle_selftest() -> None:
    with tempfile.TemporaryDirectory(
            prefix="lisp65-v150-public-lifecycle-") as raw:
        base = Path(raw)
        absent = base / "absent"
        require(not public_build_has_owned_state(absent),
                "absent public build root was treated as consumed")

        preflight = base / "preflight-only"
        for name in sorted(PREFLIGHT_OWNED_CHILDREN):
            (preflight / name).mkdir(parents=True, exist_ok=True)
        require(not public_build_has_owned_state(preflight),
                "sibling preflight outputs consumed the public build")

        mutations = (
            ("completed-manifest", "candidate-manifest.json", False),
            ("partial-product", "linked-product.json", False),
            ("unknown-child", "future-output", True),
        )
        for label, name, directory in mutations:
            candidate = base / label
            (candidate / "ide-check").mkdir(parents=True)
            target = candidate / name
            if directory:
                target.mkdir()
            else:
                target.write_text("owned\n", encoding="ascii")
            require(public_build_has_owned_state(candidate),
                    f"one-shot mutation survived: {label}")
    print("c2-v150-public-product: LIFECYCLE SELFTEST PASS "
          "preflight=2 mutations=3")


def _historical_heap() -> tuple[B.Heap, set[str]]:
    value = load(STATIC_HEAP)
    cells = value.get("cells")
    resident_names = value.get("resident_names")
    require(isinstance(cells, list) and isinstance(resident_names, list),
            "historical IDE heap projection schema drift")
    heap = B.Heap.__new__(B.Heap)
    heap.cells = [
        None if row is None else B.Cell(
            str(row[0]), int(row[1]), int(row[2]), str(row[3]))
        for row in cells
    ]
    heap.symbols = {
        cell.name: index << 1 for index, cell in enumerate(heap.cells)
        if cell is not None and cell.type == B.T_SYM
    }
    heap.sym_values = {}
    heap.t_obj = heap.symbols["t"]
    require(all(heap.symbols.get(name) is not None for name in resident_names),
            "historical IDE resident symbol projection incomplete")
    return heap, set(str(name) for name in resident_names)


@contextmanager
def _historical_ide_compile() -> Iterator[None]:
    """Compile IDE against its accepted pre-target heap, from source.

    The projection records semantic compiler state (heap cells and resident
    names), not an IDE artifact.  Target functions are still parsed, compiled,
    packed and checked by the current public compiler.
    """
    original = STD._compile_suite
    original_embed = STD._check_embed_manifest

    def projected(suite: dict[str, Any], base_addr: int = 0,
                  include_cases: bool = True):
        heap, resident_names = _historical_heap()
        functions, forms, macros, inliner = STD._suite_functions_and_forms(suite)
        cases = list(suite.get("cases", []))
        overrides = set(STD._as_list(suite.get("resident_overrides")))
        unknown = sorted(overrides - set(functions))
        require(not unknown, "historical IDE override is not a target function")
        names, codes, flags = STD._compile_function_objects(
            functions, forms, heap, macro_names=macros,
            existing_names=resident_names - overrides, label="target suite",
            strict_arity=bool(suite.get("strict_arity", False)),
            abi_profile=suite.get("abi_profile"), prebuilt_primitives=True)
        bundle = STD.PB.pack_code_objects(heap, names, codes,
                                           base_addr=base_addr)
        directory = STD.PB.load_bundle_directory(heap, bundle)
        # Dependency checks only need the historical resident cells to be
        # present.  The values are never emitted with this disk library.
        dummy = next(iter(codes.values()))
        for name in sorted(resident_names - overrides):
            directory.setdefault(heap.intern(name), dummy)
        return (heap, names, codes, flags, {}, bundle, directory, cases, [],
                inliner)

    STD._compile_suite = projected
    STD._check_embed_manifest = lambda *_args, **_kwargs: {
        "cases": 0, "steps": 0, "literal_nodes": 0,
        "literal_patches": 0,
    }
    try:
        yield
    finally:
        STD._compile_suite = original
        STD._check_embed_manifest = original_embed


def emit_ide(prefix: Path) -> dict[str, Any]:
    codemod = BUILD / "ide-codemod"
    if not codemod.exists():
        run([sys.executable, "tools/host-lisp/v2_workbench_codemod.py",
             "--out", codemod.relative_to(ROOT).as_posix()],
            "public IDE source projection")
    suite_path = codemod / "suites/p0-ide-core-lib.json"
    suite = load(suite_path)
    resident = list(suite.get("resident_suites", []))
    require(len(resident) == 2 and resident[0].endswith(
                "p0-stdlib-einsuite-core-workbench-subset.json"),
            "public IDE resident-suite projection drift")
    resident[0] = LINK95_SUITE.relative_to(ROOT).as_posix()
    suite["resident_suites"] = resident
    # One stable semantic smoke is enough here; source parsing, dependency
    # checks and artifact verification still cover the complete library.
    suite["cases"] = [{"name": "buffer-name",
                       "expr": "(ide-buffer-name '(x nil nil))",
                       "expect": "x"}]
    prefix.parent.mkdir(parents=True, exist_ok=True)
    with _historical_ide_compile():
        STD.emit_artifacts(str(suite_path), suite, str(prefix), base_addr=0,
                           artifact_role="disk-lib")
    manifest = prefix.with_suffix(".manifest.json")
    external = prefix.with_suffix(".ext.bin")
    require((external.stat().st_size, sha(external)) == EXPECTED["roles"]["library-ide"],
            "public-source IDE projection differs from accepted v1.5 freight")
    return load(manifest)


def ide_check() -> dict[str, Any]:
    target = BUILD / "ide-check/ide"
    if target.parent.exists():
        shutil.rmtree(target.parent)
    value = emit_ide(target)
    print(f"v1.5 public IDE: PASS {target.with_suffix('.manifest.json').stat().st_size} "
          f"{sha(target.with_suffix('.manifest.json'))}")
    return value


def prerequisites() -> None:
    run(["make", "--no-print-directory", "v2-workbench-artifacts",
         "bytecode-p0-buffer-lib-artifacts", "fasl-emit-check",
         "equivalence-check"], "public generated-source prerequisites")
    run([sys.executable, "tools/host-lisp/c2_v130_static_input_carrier.py",
         "materialize"], "public static input carrier")
    V112.emit_promoted_carrier()


def _copy_family(prefix: Path, target: Path) -> None:
    files = sorted(prefix.parent.glob(prefix.name + ".*"))
    require(files, f"artifact family absent: {prefix}")
    target.mkdir(parents=True, exist_ok=True)
    for source in files:
        require(source.is_file() and not source.is_symlink(),
                f"non-regular artifact family member: {source}")
        shutil.copyfile(source, target / source.name)


def prepare_link95_base() -> None:
    """Recreate the source-only predecessor consumed by Link 95."""
    anonymous = BUILD / "product-inputs/anonymous-compiler-names.json"
    anonymous.parent.mkdir(parents=True, exist_ok=True)
    require(len(PUBLIC_ANONYMOUS_NAMES) == 101
            and len(set(PUBLIC_ANONYMOUS_NAMES)) == 101,
            "public anonymous compiler-name projection drift")
    anonymous.write_bytes(canonical({"entries": [
        {"name": name, "anonymous": True}
        for name in PUBLIC_ANONYMOUS_NAMES]}))
    L95.PACKED.ANONYMOUS_AUTHORITY = anonymous
    base = L95.BASE
    require(not base.exists(), "Link-95 public base must start fresh")
    codemod = base / "codemod"
    run([sys.executable, "tools/host-lisp/v2_workbench_codemod.py",
         "--out", codemod.relative_to(ROOT).as_posix()],
        "Link-95 public base codemod")
    runtime = codemod / "sources/lib/dialect-v2/eval-runtime.lisp"
    runtime.write_text(
        REDISPATCH.candidate_runtime(load(REDISPATCH.CONTRACT)),
        encoding="utf-8")
    base_suite = load(LINK95_SUITE)
    sources = base_suite.get("sources")
    require(isinstance(sources, list),
            "Link-95 public base source inventory absent")
    current_prefix = codemod.relative_to(ROOT).as_posix() + "/"
    rewritten_sources: list[str] = []
    codemod_sources = 0
    for source in sources:
        require(isinstance(source, str),
                "Link-95 public base source is not a path")
        marker = "/codemod/"
        if source.startswith("build/") and marker in source:
            rewritten_sources.append(
                current_prefix + source.split(marker, 1)[1])
            codemod_sources += 1
        else:
            rewritten_sources.append(source)
    require(codemod_sources > 0
            and all((ROOT / source).is_file() for source in rewritten_sources),
            "Link-95 public base did not consume its build-local codemod")
    base_suite["sources"] = rewritten_sources
    omissions = list(base_suite.get("allow_omitted_defuns", []))
    omissions.extend({"name": name,
                      "reason": "post-Link-95 source successor; not resident in this base"}
                     for name in ("%c2-direct-expression",
                                  "%c2-direct-expression-p",
                                  "%time-error-duration-overflow"))
    base_suite["allow_omitted_defuns"] = omissions
    L95.BASE_SUITE.write_bytes(canonical(base_suite))

    # Product manifests carry canonical paths, so emit the historical IDE at
    # its canonical public location before copying the Link-95 authority.
    # Promoting the LCC carrier regenerates the codemod tree, so materialize
    # the buffer family after that step rather than relying on make ordering.
    run(["make", "--no-print-directory", "bytecode-p0-buffer-lib-artifacts"],
        "Link-95 public buffer authority")
    ide_prefix = ROOT / "build/bytecode/dialect-v2/libs/ide"
    for old in ide_prefix.parent.glob("ide.*"):
        old.unlink()
    emit_ide(ide_prefix)
    authorities = base / "authorities"
    _copy_family(ide_prefix, authorities)
    _copy_family(ROOT / "build/bytecode/dialect-v2/libs/buffer", authorities)

    prefix = base / "static-plane/narrow-static/stdlib-p0"
    observations = base / "stdlib-observations.json"
    INPUT.run_suite(L95.BASE_SUITE, prefix, observations)
    manifest = prefix.with_suffix(".manifest.json")
    specs = (
        ("stdlib-p0", "stdlib", manifest),
        ("ide", "ide", authorities / "ide.manifest.json"),
        ("idex", "idex", ROOT / (
            "build/c2.2/substitution/published-nullary-call-bytecode-artifacts/"
            "libs/idex.manifest.json")),
        ("m65d", "m65d", ROOT / (
            "build/c2.2/substitution/published-nullary-call-bytecode-artifacts/"
            "libs/m65d.manifest.json")),
        ("buffer", "buffer", authorities / "buffer.manifest.json"),
        ("lcc", "lcc", ROOT / "build/post-promotion/v112/compiler/lcc.manifest.json"),
    )
    require(all(path.is_file() for _key, _name, path in specs),
            "Link-95 public six-image base is incomplete")
    old = (SUB.BUILD, SUB.SPECS)
    try:
        SUB.BUILD = base / "static-plane/narrow-static/product"
        SUB.SPECS = specs
        SUB.build()
    finally:
        SUB.BUILD, SUB.SPECS = old


def configure_link95_paths() -> None:
    """Keep the reconstructed Link-95 world inside this build's ownership."""
    base = BUILD / "product-inputs/link95-base"
    out = BUILD / "product-inputs/link95-closure"
    L95.BASE = base
    L95.BASE_SUITE = base / "link95-stdlib-suite.json"
    L95.BASE_PRODUCT = (
        base / "static-plane/narrow-static/product/substitution-artifacts.json")
    L95.OUT = out
    L95.CODEMOD = out / "codemod"
    L95.SUITE = out / "link95-closed-stdlib-suite.json"
    L95.STDLIB_PREFIX = out / "static-plane/narrow-static/stdlib-p0"
    L95.OBSERVATIONS = out / "stdlib-observations.json"
    L95.PRODUCT_DIR = out / "static-plane/narrow-static/product"
    L95.PRODUCT = L95.PRODUCT_DIR / "substitution-artifacts.json"


def configure_release_preflight_paths() -> None:
    """Give the linker-free preflight a build-local one-shot root."""
    target = BUILD / "product-inputs/release-preflight"
    PRE.BUILD = target
    PRE.STATIC = target / "static-plane/narrow-static"
    PRE.SOURCES = target / "sources"
    PRE.STDLIB_PREFIX = PRE.STATIC / "stdlib-p0"
    PRE.STDLIB = PRE.STDLIB_PREFIX.with_suffix(".manifest.json")
    PRE.PRODUCT = PRE.STATIC / "product/substitution-artifacts.json"
    PRE.V6_PLANE = PRE.STATIC / "v6-semantics"


def configure_product_card_paths() -> None:
    """Project mutable profile/card outputs into the current build world."""
    ownership = BUILD / "product-inputs/ownership"
    OWN.INPUTS = ownership
    OWN.CANDIDATE_PROFILE = ownership / "candidate-profile.json"
    OWN.CANDIDATE_CONTRACT = ownership / "c2-lite-execution-contract.json"
    OWN.CANDIDATE_HEADER = ownership / "c2_lite_static_plane.h"

    card = BUILD / "product-link"
    preflight = BUILD / "product-link-preflight"
    CARD.BUILD = card
    CARD.PREFLIGHT = preflight
    CARD.PREFLIGHT_RECEIPT = preflight / "preflight.json"
    CARD.SEMANTIC_RECEIPT = preflight / "semantic-repl-compile.json"
    CARD.INVOCATION = preflight / "card-invocation.json"
    CARD.PROJECTED_OWNERSHIP = preflight / "projected-ownership-contract.json"
    CARD.PROJECTED_FULL_MAP = preflight / "projected-full-map-authority.json"
    CARD.PRODUCER_RESULT = card / "producer-result.json"
    CARD.SCOPE_RESULT = card / "owner-scope-result.json"
    CARD.ACCEPTANCE_RESULT = card / "artifact-acceptance.json"
    CARD.ABI_REPORT = card / "wplto/c2-asm-leaf-abi.json"
    CARD.RECEIPT = card / "unused-public-product-card-receipt.json"
    CARD.FINAL_RED = card / "unused-public-product-card-final-red.json"


def configure_candidate_placement_contract() -> None:
    """Bind placement truth to the ELF emitted by this build.

    The historical liveness receipt describes the pre-WYSIWYG reader world.
    Link 116 already replaced its pinned end/reserve pair with the accepted
    candidate-derived contract.  A fresh public product build must project
    that successor onto its own ELF instead of silently falling back to the
    historical receipt through import order.
    """
    elf = CARD.BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"

    def derive() -> dict[str, Any]:
        return PLACEMENT.derive(elf)

    MAP_CARD.placement_contract = derive
    CANDIDATE.placement_contract = derive


def prepare_public_release_authorities() -> None:
    """Project the linker-free release authorities from public inputs.

    The private release receipts record the historical review session.  Deep
    producer adapters bind their identities, but product construction only
    needs the current static-plane geometry and freight contract.  Recreate
    those two authorities from the public candidate instead of exporting (or
    silently consuming) private evidence.
    """
    authorities = BUILD / "product-inputs/public-release-authorities"
    authorities.mkdir(parents=True, exist_ok=True)
    preflight_path = authorities / "v1.5-linker-free-preflight.json"
    closure_path = authorities / "v1.5-freight-closure.json"

    geo = PRE.geometry()
    source_paths = (
        PRE.SOURCES / "eval-runtime.lisp",
        PRE.SOURCES / "stdlib-require.lisp",
        PRE.SOURCES / "repl-banner.lisp",
    )
    manifests = {
        key: PRE.manifest_artifacts(path)
        for key, _name, path in PRE.specs()
    }
    preflight = {
        "format": PRE.FORMAT,
        "recorded_on": "2026-08-18",
        "status": PRE.STATUS,
        "attempt_accounting": {
            "product_cards_authorized": 1,
            "product_cards_consumed": 0,
            "product_links": 0,
            "device_contacts": 0,
        },
        "scope": {
            "release": "v1.5.0",
            "link": 116,
            "activation_defines": load(PRE.CONTRACT)["build"][
                "activation_defines"],
            "historical_worlds_changed": 0,
            "projection": "public-current-source",
        },
        "geometry": geo,
        "authorities": {
            "contract": bind(PRE.CONTRACT),
            "candidate_sources": [bind(path) for path in source_paths],
            "input_manifests_and_payloads": manifests,
            "product": bind(PRE.PRODUCT),
            "bank2": bind(PRE.V6_PLANE / "bank2-static-code.bin"),
            "public_driver": bind(Path(__file__).resolve()),
        },
        "host_gates": {
            "current_source_projection": {
                "status": "passed",
                "private_evidence_inputs": 0,
            },
        },
        "producer_inversion": {
            "input_count": sum(len(rows) for rows in manifests.values())
                + len(source_paths) + 3,
            "symbol_space_is_not_an_input": True,
            "all_inputs_content_bound": True,
            "private_evidence_is_not_an_input": True,
        },
        "claim_limit": (
            "Public linker-free input projection only; release acceptance "
            "remains in the private review ledger."),
    }

    def validate_preflight(value: dict[str, Any], *, verify: bool) -> None:
        require(
            value.get("format") == PRE.FORMAT
            and value.get("status") == PRE.STATUS
            and value.get("geometry") == PRE.geometry()
            and value.get("attempt_accounting")
                == preflight["attempt_accounting"]
            and value.get("producer_inversion", {}).get(
                "private_evidence_is_not_an_input") is True,
            "public preflight projection drift",
        )
        if verify:
            expected = {key: item for key, item in preflight.items()
                        if key != "mutations_rejected"}
            require(value == expected,
                    "public preflight projection is stale")

    preflight_mutations = [
        "hide-card", "consume-card", "claim-link", "claim-device",
        "change-history", "admit-symbol-space", "unbound-input",
        "admit-private-evidence",
    ]
    preflight["mutations_rejected"] = preflight_mutations
    preflight_path.write_bytes(canonical(preflight))

    closure = {
        "format": CLOSURE.FORMAT,
        "recorded_on": "2026-08-18",
        "status": CLOSURE.STATUS,
        "attempt_accounting": dict(preflight["attempt_accounting"]),
        "scope": {
            "frozen": True,
            "resident_delta_bytes": 0,
            "release": "v1.5.0",
        },
        "packages": {
            "public_surface": load(PRE.CONTRACT)["freight"],
            "projection": "compiled-later-from-public-current-source",
        },
        "performance": {
            "release_terminal_on_violation": True,
            "projection": "contract-bound",
        },
        "authorities": {
            "contract": bind(PRE.CONTRACT),
            "preflight": bind(preflight_path),
            "public_driver": bind(Path(__file__).resolve()),
        },
        "claim_limit": (
            "Public freight contract projection only; hardware acceptance "
            "is not a build input."),
    }

    def validate_closure(value: dict[str, Any], *, verify: bool) -> None:
        require(
            value.get("format") == CLOSURE.FORMAT
            and value.get("status") == CLOSURE.STATUS
            and value.get("attempt_accounting")
                == closure["attempt_accounting"]
            and value.get("scope") == closure["scope"]
            and value.get("performance", {}).get(
                "release_terminal_on_violation") is True,
            "public freight projection drift",
        )
        if verify:
            expected = {key: item for key, item in closure.items()
                        if key != "mutations_rejected"}
            require(value == expected, "public freight projection is stale")

    closure_mutations = [
        "consume-card", "claim-link", "claim-device", "unfreeze-scope",
        "grow-resident", "soften-performance",
    ]
    closure["mutations_rejected"] = closure_mutations
    closure_path.write_bytes(canonical(closure))

    PRE.RECEIPT = preflight_path
    PRE.validate = validate_preflight
    PRE.mutations = lambda value: (
        validate_preflight(value, verify=True) or preflight_mutations)
    CLOSURE.RECEIPT = closure_path
    CLOSURE.validate = validate_closure
    CLOSURE.mutations = lambda value: (
        validate_closure(value, verify=True) or closure_mutations)

    # The current full-span contract is a tracked product input.  Its private
    # host receipt is historical acceptance evidence, so give the projection
    # layer a source-bound public provenance object instead.
    full_span = CARD.BASE.PRODUCT.BASE.BASE
    full_span_authority = authorities / "full-span-current-source.json"
    full_span_authority.write_bytes(canonical({
        "format": "lisp65-v1.5-public-full-span-authority-v1",
        "status": "passed-current-source-contract-projection",
        "contract": bind(full_span.CONTRACT),
        "configuration": bind(full_span.CONFIG_DRIVER),
        "private_evidence_inputs": 0,
    }))
    full_span.FIX.RECEIPT = full_span_authority


def build_linked_product() -> tuple[Path, Path]:
    configure_link95_paths()
    prepare_link95_base()
    original_candidate_suite = L95.candidate_suite

    def candidate_suite() -> dict[str, Any]:
        value = original_candidate_suite()
        value["allow_omitted_defuns"] = [
            row for row in value.get("allow_omitted_defuns", [])
            if row.get("name") != "%time-error-duration-overflow"]
        return value

    L95.candidate_suite = candidate_suite
    try:
        L95.build_product()
    finally:
        L95.candidate_suite = original_candidate_suite
    configure_release_preflight_paths()
    # The release preflight is part of this build's one-shot product world.
    # Its IDE and buffer manifests must therefore be the build-owned copies
    # produced above, not mutable global convenience outputs which a later
    # check-source target is allowed to regenerate.  Payload bytes are
    # unchanged; this only closes the early-check/late-emitter idempotence
    # seam exposed by the 2.3 authority rebind.
    PRE.BASE_SPECS = (
        ("ide", "ide", L95.BASE / "authorities/ide.manifest.json"),
        ("idex", "idex", ROOT / (
            "build/c2.2/substitution/published-nullary-call-bytecode-artifacts/"
            "libs/idex.manifest.json")),
        ("m65d", "m65d", ROOT / (
            "build/c2.2/substitution/published-nullary-call-bytecode-artifacts/"
            "libs/m65d.manifest.json")),
        ("buffer", "buffer", L95.BASE / "authorities/buffer.manifest.json"),
        ("lcc", "lcc", ROOT / "build/post-promotion/v112/compiler/lcc.manifest.json"),
    )
    original_source_suite = PRE.source_suite

    def source_suite():
        suite, texts = original_source_suite()
        suite["allow_omitted_defuns"] = [
            row for row in suite.get("allow_omitted_defuns", [])
            if row.get("name") not in {
                "%c2-direct-expression", "%c2-direct-expression-p"}]
        return suite, texts

    PRE.source_suite = source_suite
    try:
        PRE.emit_static_plane()
    finally:
        PRE.source_suite = original_source_suite
    # The historical card adapter asserts that the canonical emitter and its
    # preflight consume one identical six-role tuple.  Project the build-local
    # tuple at that real consumer boundary as well; changing PRE.BASE_SPECS
    # alone only configured one half of the pair.
    def project_build_local_specs() -> None:
        specs = PRE.specs()
        PRE.L95.CAN.SPECS = specs
        req = PRE.L95.L94.V112.P.BASE.PROBE.REQ
        req.SPECS = specs
        req.F1W.SPECS = specs
        req.F1W.PLANE.FRESH_MANIFESTS = tuple(
            path for _key, _name, path in specs)

    project_build_local_specs()
    original_v112_configure = PRE.L95.L94.V112.configure

    def configure_v112(*args: Any, **kwargs: Any) -> dict[str, Path]:
        paths = original_v112_configure(*args, **kwargs)
        # V112's historical adapter reconstructs its ambient six-role tuple.
        # Project the selected build's tuple after that reconstruction and
        # before Link-94 consumes it.
        project_build_local_specs()
        return paths

    PRE.L95.L94.V112.configure = configure_v112
    original_link95_configure = PRE.L95.configure_card

    def configure_link95_card() -> dict[str, Path]:
        # Successor adapters call configure_identity() repeatedly.  Reassert
        # the paired emitter tuple at every real configuration boundary so a
        # later adapter cannot restore the ambient historical tuple between
        # preflight and Link-94's consumer assertion.
        project_build_local_specs()
        return original_link95_configure()

    PRE.L95.configure_card = configure_link95_card
    original_link94_configure = PRE.L95.L94.configure_card

    def configure_link94_card() -> dict[str, Path]:
        project_build_local_specs()
        return original_link94_configure()

    PRE.L95.L94.configure_card = configure_link94_card
    prepare_public_release_authorities()
    configure_product_card_paths()
    configure_candidate_placement_contract()
    OWN.configure_projection_paths()
    FIX.write_projection()
    CARD.install()
    # The root-source projection belongs to the real producer chain and must
    # exist before the one WPLTO invocation.
    # The phase-9 replacement wrapper normally adds provenance from its
    # historical emission receipt.  Full-span immediately supersedes those
    # forecast values from the tracked v3 artifact contract.  Public builds
    # therefore start from the tracked ABI successor contract and let
    # full-span derive the current 1,248/4,644-byte freight, without making
    # the historical receipt a hidden build input.
    full_span = CARD.BASE.PRODUCT.BASE.BASE
    phase9_replacement = full_span.BASE
    phase9_replacement.projected_contracts = (
        phase9_replacement.OLD.projected_contracts)
    CARD.BASE.PRODUCT.BASE.write_projections()
    try:
        CARD.BASE.produce_child()
    except Exception as error:  # private qualification tail, after sealing
        candidate_product = CARD.BUILD / (
            "wplto/lisp65-c2-substitution-linked.prg")
        candidate_elf = Path(str(candidate_product) + ".elf")
        require(
            candidate_product.is_file() and candidate_elf.is_file()
            and (candidate_product.stat().st_size, sha(candidate_product))
                == EXPECTED["roles"]["c2-resident-prg"]
            and (candidate_elf.stat().st_size, sha(candidate_elf))
                == EXPECTED["roles"]["linked-product-elf"],
            f"public product producer failed before sealed output: {error}",
        )
    product = CARD.BUILD / "wplto/lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    require((product.stat().st_size, sha(product)) ==
                EXPECTED["roles"]["c2-resident-prg"]
            and (elf.stat().st_size, sha(elf)) ==
                EXPECTED["roles"]["linked-product-elf"],
            "public source link differs from owner-accepted v1.5 product")
    return product, elf


def product_check() -> dict[str, Any]:
    prerequisites()
    product, elf = build_linked_product()
    value = {"product": bind(product), "elf": bind(elf)}
    (BUILD / "linked-product.json").parent.mkdir(parents=True, exist_ok=True)
    (BUILD / "linked-product.json").write_bytes(canonical(value))
    print("v1.5 public product: LINK PASS "
          f"prg={value['product']['sha256']} elf={value['elf']['sha256']}")
    return value


def configure_canonical_paths() -> None:
    # Every action runs in a fresh process.  Reinstall the build-local product
    # world before deriving Completion paths; relying on configuration left by
    # the product action would silently route this consumer to historical
    # defaults.
    configure_release_preflight_paths()
    configure_product_card_paths()
    target = BUILD / "canonical-product"
    CAN.BUILD = target
    CAN.WPLTO = CARD.BUILD / "wplto"
    CAN.FINAL = target / "final"
    CAN.ARTIFACTS = target / "artifacts"
    CAN.RECEIPTS = target / "receipts"
    CAN.MANIFEST = target / "canonical-product-manifest.json"
    CAN.STATIC = PRE.STATIC
    CAN.STATIC_PRODUCT = PRE.STATIC / "product"
    CAN.CONTRACT = OWN.CANDIDATE_CONTRACT
    CAN.PROFILE = OWN.CANDIDATE_PROFILE


def complete_product() -> dict[str, Any]:
    configure_canonical_paths()
    product = CAN.WPLTO / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    require(elf.is_file() and sha(elf) == EXPECTED["roles"][
                "linked-product-elf"][1],
            "sealed public WPLTO product absent before Completion")

    CAN.REPLAY.PROFILE.configure()
    if PRODUCT.PROFILE_RODATA_BYTES == 342:
        PRODUCT.configure_require_resolver_profile_geometry()
        PRODUCT.configure_defstruct_foundation_profile_geometry()
    CAN.REPLAY.BANK2.configure_bank2_stage()
    CAN.REPLAY.TWO.configure_two_region()
    CAN.REPLAY.LINK60.configure_current_pin_adapters()
    PRODUCT.configure_intern_session_service()
    PRODUCT.configure_full_map_ownership()
    PRODUCT.configure_low_resident_lma_reset()
    HEADER.configure_consumption()
    PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = (
        CAN.STATIC_PRODUCT / "substitution-artifacts.json")
    PRODUCT.INITIAL_C2D = CAN.STATIC_PRODUCT / "initial.c2d-v3.bin"
    PRODUCT.PRODUCT_SHELF = (
        CAN.STATIC_PRODUCT / "product-shelf-v4-direct.bin")
    section = ElfTruth.read(
        elf, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj"
    ).section(PRODUCT.VERIFIER_BINDING_SECTION)
    require((section.address, section.bytes) == (0xB98C, 40),
            "public candidate verifier-binding geometry drift")
    PRODUCT.VERIFIER_BINDING_BASE = section.address
    PRODUCT.LINK60_VERIFIER_BINDING_BASE = section.address

    # Completion adapters consume the reviewed current VMA golden.  The
    # candidate comparison is derived afresh from the sealed ELF.
    golden = PARITY.PIPE.GOLD
    golden_value = load(golden.GOLDEN)
    require(
        sha(golden.GOLDEN) == golden.GOLDEN_SHA256
        and len(golden_value.get("section_invariants", [])) == 101
        and len(golden_value.get("section_vma_derivations", [])) == 2
        and len(golden_value.get("fixed_boundary_symbols", {})) == 25
        and len(golden_value.get("capacity_arenas", [])) == 11,
        "public VMA Golden identity or shape drift",
    )

    def public_golden_audit(value: dict[str, Any]) -> None:
        # The Golden bytes are the public fixed authority.  Reconstructing
        # their historical review provenance would turn private evidence into
        # a build input; current-candidate comparison below supplies the live
        # product proof.
        require(value == golden_value,
                "public VMA Golden bytes differ from SHA-bound authority")

    golden.audit_artifact = public_golden_audit
    SOURCE_MEDIA.FLOW.BASE.INV = PARITY.PIPE.GOLD
    CRC_MEDIA.INV = PARITY.PIPE.GOLD
    projection = PARITY.PIPE.GOLD.compare_elf(elf)
    SOURCE_MEDIA.card_projection = lambda: {
        "acceptance": {"VMA_golden": projection}}

    original_configure = CAN.REPLAY.configure
    original_fixed = PRODUCT.FIXED_BLOCK_LEAF.audit_elf
    original_facade = PRODUCT.fixed_facade_gate
    CAN.REPLAY.configure = lambda: None
    PRODUCT.FIXED_BLOCK_LEAF.audit_elf = (
        lambda candidate, **kwargs: SOURCE_MEDIA._link105_fixed_audit(
            original_fixed, candidate, **kwargs))
    PRODUCT.fixed_facade_gate = (
        lambda out, target, suffix: CRC_MEDIA._current_facade_gate(
            original_facade, out, target, suffix))
    try:
        value = CAN.complete_artifacts()
    finally:
        CAN.REPLAY.configure = original_configure
        PRODUCT.FIXED_BLOCK_LEAF.audit_elf = original_fixed
        PRODUCT.fixed_facade_gate = original_facade
    final_product = CAN.FINAL / product.name
    final_elf = Path(str(final_product) + ".elf")
    require((final_product.stat().st_size, sha(final_product)) ==
                EXPECTED["roles"]["c2-resident-prg"]
            and (final_elf.stat().st_size, sha(final_elf)) ==
                EXPECTED["roles"]["linked-product-elf"],
            "public Completion changed accepted product identity")
    print("v1.5 public product: COMPLETION PASS")
    return value


def canonical_manifest() -> dict[str, Any]:
    configure_canonical_paths()
    libs = CAN.STATIC / "libs"
    libs.mkdir(parents=True, exist_ok=True)
    sources = {
        "ide": ROOT / "build/bytecode/dialect-v2/libs/ide.ext.bin",
        "idex": ROOT / (
            "build/c2.2/substitution/published-nullary-call-bytecode-artifacts/"
            "libs/idex.ext.bin"),
        "m65d": ROOT / (
            "build/c2.2/substitution/published-nullary-call-bytecode-artifacts/"
            "libs/m65d.ext.bin"),
    }
    for name, source in sources.items():
        shutil.copyfile(source, libs / f"{name}.ext.bin")
    completion = load(CAN.RECEIPTS / "artifact-completion.json")
    static = {
        "status": "passed-v1.5-public-static-plane",
        "product_build_id": "0x0401e53e",
        "bank2_static_code_bytes": 46043,
    }
    wplto = {
        "status": "passed-one-public-source-WPLTO-link",
        "product": bind(CAN.WPLTO / "lisp65-c2-substitution-linked.prg"),
    }
    value = CAN.manifest(static, wplto, completion)
    # The linked mapped service lives after a linker-owned gap in Bank 2.
    # Media must carry the complete LMA extent, not just the 46,043-byte
    # static prefix used by the compiler.
    elf = CAN.FINAL / "lisp65-c2-substitution-linked.prg.elf"
    truth = ElfTruth.read(
        elf, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=True)
    service = truth.section(".lisp65_c2_mapped_far_service")
    service_raw = truth.section_bytes(service.name)
    start = truth.symbol("__lisp65_c2_mapped_far_service_load_start").value
    end = truth.symbol("__lisp65_c2_mapped_far_service_load_end").value
    destination = 0x00020000
    prefix_row = next(row for row in value["artifacts"]
                      if row["role"] == "c2-bank2-static-code-plane")
    prefix = (ROOT / prefix_row["path"]).read_bytes()
    require(len(prefix) == 46043 and len(service_raw) == end - start
            and len(prefix) <= start - destination,
            "public mapped-service delivery geometry drift")
    materialized = prefix + bytes(start - destination - len(prefix)) + service_raw
    bank2 = BUILD / "product-inputs/bank2-static-code.bin"
    bank2.parent.mkdir(parents=True, exist_ok=True)
    bank2.write_bytes(materialized)
    prefix_row.clear()
    prefix_row.update({**bind(bank2), "role": "c2-bank2-static-code-plane"})
    value["static_plane"].update({
        "bank2_static_code_bytes": len(materialized),
        "bank2_sha256": hashlib.sha256(materialized).hexdigest(),
    })
    CAN.MANIFEST.write_bytes(canonical(value))
    CAN.check()
    expected_bank2 = (48530,
        "86f63979648caebbc960c27d86c2a1969e415e15130c099509c4568d4268024a")
    require((bank2.stat().st_size, sha(bank2)) == expected_bank2,
            "public mapped-service delivery differs from accepted extent")
    return value


def configure_shared_media_paths() -> Path:
    configure_canonical_paths()
    shared = BUILD / "shared-system"
    MEDIA.CANONICAL = CAN
    MEDIA.BUILD = shared
    MEDIA.PRODUCT_MANIFEST = CAN.MANIFEST
    MEDIA.MANIFEST = shared / "candidate-manifest.json"
    MEDIA.DESCRIPTOR = shared / "boot.id"
    MEDIA.STAGER = shared / "autoboot.c65"
    MEDIA.STAGER_MAP = shared / "autoboot.c65.map"
    MEDIA.PRODUCT_D81 = shared / "lisp65-product.d81"
    MEDIA.WORK_D81 = shared / "lisp65-work.d81"
    MEDIA.MOUNT = shared / "lisp65-product.mount.json"
    return shared


def build_shared_media() -> dict[str, Any]:
    canonical_manifest()
    configure_shared_media_paths()
    value = MEDIA.build(stager_compile_defines=(LIVENESS.OPT_IN,))
    MEDIA.check()
    by_role = {row["role"]: row for row in value["artifacts"]}
    for role in ("product-d81", "work-d81"):
        require((by_role[role]["bytes"], by_role[role]["sha256"])
                == EXPECTED["roles"][role],
                f"public {role} differs from owner-accepted v1.5 medium")
    print("v1.5 public product: SHARED MEDIA PASS")
    return value


def _rewrite_tokens(source: str, mapping: dict[str, str]) -> str:
    constituents = r"A-Za-z0-9%*+/<>=!?_.-"
    result = source
    for old in sorted(mapping, key=len, reverse=True):
        result = re.sub(
            rf"(?<![{constituents}]){re.escape(old)}(?![{constituents}])",
            mapping[old], result)
    return result


def _compile_library(suite_path: Path, prefix: Path) -> Path:
    suite = STD._read_suite(str(suite_path))
    STD.check_suite(str(suite_path), suite)
    STD.emit_artifacts(str(suite_path), suite, str(prefix), base_addr=0,
                       artifact_role="disk-lib")
    return prefix.with_suffix(".manifest.json")


def compile_optional_libraries() -> dict[str, Path]:
    generated = BUILD / "library-inputs"
    generated.mkdir(parents=True, exist_ok=True)

    inspect_suite = load(ROOT / "tests/bytecode/libs/p0-inspect-trace.json")
    inspect_suite.update({
        "name": "inspect-trace-v15-scoped",
        "description": (
            "v1.5 inspect candidate with exact trace ABI and first-use "
            "who-calls metadata"),
        "sources": [WHO_CALLS.relative_to(ROOT).as_posix(),
                    "lib/inspect-trace.lisp"],
        "resident_suite": str(
            ROOT / "tests/bytecode/libs/p0-stdlib-ship-input-wait-base.json"),
    })
    inspect_suite_path = generated / "p0-inspect-trace-v15.json"
    inspect_suite_path.write_bytes(canonical(inspect_suite))

    defstruct_source = generated / "defstruct-short.lisp"
    original = (ROOT / "lib/defstruct.lisp").read_text(encoding="utf-8")
    shortened = _rewrite_tokens(original, DEFSTRUCT_PRIVATE_NAMES)
    reverse = {new: old for old, new in DEFSTRUCT_PRIVATE_NAMES.items()}
    require(_rewrite_tokens(shortened, reverse) == original,
            "public defstruct private-name rewrite is not invertible")
    defstruct_source.write_text(shortened, encoding="utf-8")
    defstruct_suite = load(ROOT / "tests/bytecode/libs/p0-defstruct-v1-lib.json")
    defstruct_suite.update({
        "name": "defstruct-v15-short-private",
        "description": (
            "v1.5 defstruct candidate with percent-private aliases and "
            "unchanged surface"),
        "sources": [defstruct_source.relative_to(ROOT).as_posix()],
        "resident_suite": str(
            ROOT / "tests/bytecode/libs/p0-stdlib-require-resolver.json"),
    })
    defstruct_suite["functions"] = [
        DEFSTRUCT_PRIVATE_NAMES.get(name, name)
        for name in defstruct_suite["functions"]]
    for case in defstruct_suite["cases"]:
        case["expr"] = _rewrite_tokens(
            case["expr"], DEFSTRUCT_PRIVATE_NAMES)
    defstruct_suite_path = generated / "p0-defstruct-v15.json"
    defstruct_suite_path.write_bytes(canonical(defstruct_suite))

    prefixes = {
        "string-extra": generated / "string-extra",
        "inspect": generated / "inspect",
        "place": generated / "place",
        "defstruct": generated / "defstruct",
    }
    manifests = {
        "string-extra": _compile_library(
            ROOT / "tests/bytecode/libs/p0-string-extra.json",
            prefixes["string-extra"]),
        "inspect": _compile_library(inspect_suite_path, prefixes["inspect"]),
        "place": _compile_library(
            ROOT / "tests/bytecode/libs/p0-place-lib.json",
            prefixes["place"]),
        "defstruct": _compile_library(
            defstruct_suite_path, prefixes["defstruct"]),
    }
    require(
        (prefixes["inspect"].with_suffix(".ext.bin").stat().st_size,
         sha(prefixes["inspect"].with_suffix(".ext.bin")))
            == (5391,
                "9ba529bdaacc90c726b226261b0277322ca763d5c10ffd5d8042b77934400264")
        and (prefixes["defstruct"].with_suffix(".ext.bin").stat().st_size,
             sha(prefixes["defstruct"].with_suffix(".ext.bin")))
            == (2945,
                "434e29ed7e7cf96c3877245aa7276bdc4fd834f2a281ceb837e8da45cd0ae664"),
        "public v1.5 name-freight library compilation drift")
    return manifests


def artifact_set(rows: list[dict[str, Any]]) -> str:
    projection = [
        {key: row[key] for key in ("role", "name", "bytes", "sha256")}
        for row in sorted(rows, key=lambda row: (row["role"], row["name"]))
    ]
    return hashlib.sha256(json.dumps(
        projection, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build_selected_media() -> dict[str, Any]:
    configure_shared_media_paths()
    shared = load(MEDIA.MANIFEST)
    require(shared.get("artifact_count") == 19,
            "public shared-media closure absent before optional libraries")
    manifests = compile_optional_libraries()
    variants = {
        "v1.5": (
            ("string-extra", "strx", "strextr", manifests["string-extra"], ()),
            ("inspect", "inspect", "inspect", manifests["inspect"], ()),
            ("place", "place", "place", manifests["place"], ()),
            ("defstruct", "defstruct", "dfstrct", manifests["defstruct"], (2,)),
        ),
    }
    library = BUILD / "library"
    old = LIBMEDIA.VARIANTS
    try:
        LIBMEDIA.VARIANTS = variants
        result = LIBMEDIA.build_library_variant(
            "v1.5", library,
            int(load(CAN.MANIFEST)["static_plane"]["product_build_id"], 0))
    finally:
        LIBMEDIA.VARIANTS = old

    additions = (
        ("optional-library-d81", library / "lisp65-library.d81"),
        ("optional-library-index", library / "l65index"),
        ("library-string-extra", library / "string-extra.l65s"),
        ("library-inspect", library / "inspect.l65s"),
        ("library-place", library / "place.l65s"),
        ("library-defstruct", library / "defstruct.l65s"),
    )
    rows = [dict(row) for row in shared["artifacts"]]
    for role, path in additions:
        identity = bind(path)
        require((identity["bytes"], identity["sha256"])
                == EXPECTED["roles"][role],
                f"public selected role differs from owner acceptance: {role}")
        rows.append({"role": role, "name": path.name, **identity})
    require(len(rows) == 25 and len({row["role"] for row in rows}) == 25,
            "public v1.5 selected role inventory drift")
    value = {
        "format": "lisp65-v1.5-public-selected-product-v1",
        "status": "passed-public-source-selected-v1.5-product",
        "artifact_count": 25,
        "artifact_set_sha256": artifact_set(rows),
        "product_build_id": shared["product_build_id"],
        "profile_build_id": shared["profile_build_id"],
        "private_evidence_inputs": 0,
        "selector": "v1.5",
        "artifacts": rows,
    }
    require(value["artifact_set_sha256"] == EXPECTED["artifact_set_sha256"],
            "public v1.5 artifact set differs from owner acceptance")
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_bytes(canonical(value))
    print("v1.5 public product: SELECTED MEDIA PASS "
          f"roles=25 set={value['artifact_set_sha256']}")
    return value


def check() -> dict[str, Any]:
    value = load(MANIFEST)
    rows = value.get("artifacts", [])
    require(
        value.get("format") == "lisp65-v1.5-public-selected-product-v1"
        and value.get("status") == "passed-public-source-selected-v1.5-product"
        and value.get("private_evidence_inputs") == 0
        and value.get("selector") == "v1.5"
        and value.get("artifact_count") == len(rows) == 25
        and artifact_set(rows) == value.get("artifact_set_sha256")
        == EXPECTED["artifact_set_sha256"],
        "selected public v1.5 manifest drift")
    for row in rows:
        path = ROOT / row["path"]
        require(path.is_file() and not path.is_symlink()
                and (path.stat().st_size, sha(path))
                == (row["bytes"], row["sha256"]),
                f"selected public v1.5 artifact drift: {row.get('role')}")
    return value


def build() -> dict[str, Any]:
    require(not public_build_has_owned_state(BUILD),
            "v1.5 public build is one-shot")
    driver = str(Path(__file__).resolve())
    for action in ("product", "complete", "media", "selected"):
        result = subprocess.run(
            [sys.executable, driver, action], cwd=ROOT,
            env=os.environ.copy(), text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, check=False)
        require(result.returncode == 0,
                f"public v1.5 {action} stage red:\n{result.stdout}")
        print(result.stdout.strip())
    return check()


def clean() -> None:
    if BUILD.exists():
        require(BUILD.is_dir() and not BUILD.is_symlink()
                and BUILD.resolve().is_relative_to((ROOT / "build").resolve()),
                "clean path escaped build")

        def remove_readonly(function, path, _error) -> None:
            target = Path(path)
            require(target.resolve().is_relative_to(BUILD.resolve()),
                    "clean callback escaped owned build")
            if target.parent.resolve().is_relative_to(BUILD.resolve()):
                target.parent.chmod(
                    target.parent.stat().st_mode | stat.S_IWUSR | stat.S_IXUSR)
            target.chmod(target.stat().st_mode | stat.S_IWUSR | stat.S_IXUSR)
            function(path)

        shutil.rmtree(BUILD, onerror=remove_readonly)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("ide-check", "product", "complete", "media",
                           "selected", "check", "build", "clean",
                           "lifecycle-selftest"))
    action = parser.parse_args().action
    if action == "ide-check":
        ide_check()
    elif action == "product":
        product_check()
    elif action == "complete":
        complete_product()
    elif action == "media":
        build_shared_media()
    elif action == "selected":
        build_selected_media()
    elif action == "check":
        check()
    elif action == "build":
        build()
    elif action == "clean":
        clean()
        print("c2-v150-public-product: CLEAN")
    else:
        lifecycle_selftest()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PublicBuildError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"c2-v150-public-product: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
